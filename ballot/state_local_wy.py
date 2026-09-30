"""
ballot/state_local_wy.py - Wyoming's state races on the November 3, 2026 ballot: the State Senate seats up this year
(the sixteen odd-numbered districts, whose four-year terms end in January, and District 6, filled early), all 62 State
House seats (one member a district, two-year terms), and the five statewide offices Wyoming elects: Governor, Secretary
of State, State Auditor, State Treasurer and Superintendent of Public Instruction (Wyoming has no Lieutenant Governor,
and its Attorney General is appointed). Every one of these offices is partisan.

Sources, the Secretary of State's own (Elections Division, sos.wyo.gov) and nothing else:

  - The "2026 General Election Candidate Roster" (PDF), the same file ballot/lists/wy.py reads for Congress. Its columns
    are Office Sought, Party Affiliation, Candidate Name, Mailing Address, Date Filed and Campaign Telephone, with City,
    State & ZIP, Date Withdrawn and Email on each entry's second line. The column edges come from the page's own
    headings; only the office, the party and the name cells, and a date under Date Withdrawn, are ever joined into text
    or kept. Addresses, cities, ZIP codes, telephones and e-mail stay in the file and are never read, printed or stored.
    The loader reads the copy the federal loader keeps (ballot_cache/wy/); if there is none it holds a fresh copy in
    memory only, never on disk. The state rows it reads are kept, allowed columns only, as
    ballot_cache/wy/wy_2026_state_roster.json. The roster gives no ballot order (Wyoming's county clerks print the
    ballots), so no ballot order is stored. A candidate with a withdrawal date is left off.
  - The August 18 primary: "2026 Primary Results Summaries - OFFICIAL.xlsx" in the zip of data files on the 2026
    Official Primary Election Results page (the federal loader's cached copy). Its sheets "Statewide Candidates",
    "Statewide Senate Odd" and "Statewide House" give each office's candidates by party, with Write-Ins, Overvotes and
    Undervotes and a Total row. The workbook also holds a sheet "Statewide Senate Even" (districts 2 to 30, even) whose
    districts are not on the 2026 roster, are not in the county precinct-by-precinct results, and whose District 6 block
    differs from the one in "Statewide Senate Odd": it is set aside, and every summary block is kept only when the
    county precinct-by-precinct results add up to it, candidate by candidate. The sheets BLANKSS and BLANKSH say they
    are blank reference sheets and are not read.
  - The same zip's "2026 Primary County PbP Results - OFFICIAL.xlsx" and "2026 Primary County PbP Total Ballots Cast -
    OFFICIAL.xlsx", used as checks: every precinct's figures for a block are summed and must equal the summary's; the
    party ballots cast in the precincts where a race was on the ballot must equal its candidates' votes plus write-ins,
    overvotes and undervotes; and the counties where a district's race was on the ballot are its county_ids. Some
    counties' precinct numbers (01-02) were stored by the spreadsheet as dates; they are read back as month-day.

A party primary is a field when two or more names were printed on that party's ballot (a candidate who withdrew after
the ballots were printed, "* Withdrawn Candidate" in the sheets and named in a footnote, is kept with the votes the
summary counts and a note). Write-ins count toward the share but are not listed; over- and undervotes are left out.
Who advanced is the party's candidate on the November roster, checked against the most votes. The minor parties
(Libertarian, Constitution) nominate outside the primary; independents file by petition.

Today's holders come from state_wy.sqlite (the Open States roster): current legislators by chamber and district, and
the officials table for Governor and Secretary of State (the roster does not carry the Auditor, the Treasurer or the
Superintendent). Only names, parties, districts, ids and term starts are read from it. A candidate is marked as the
sitting member (incumbent 1, state_member_id) only when the name fits that seat's holder, one to one. A candidate who
sits today in the other chamber, in a district that shares a precinct with this one in the primary results, or (for a
statewide race) who holds any seat or office in the roster, gets state_member_id with incumbent 0 and a note, again
only when exactly one roster person fits.

Usage: python ballot/state_local_wy.py <database file> [--cache <folder>]
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
import zipfile
from collections import Counter, OrderedDict, defaultdict
from urllib.error import HTTPError, URLError

import openpyxl

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from ballot.common import fold, name_parts, party_code                     # noqa: E402
from ballot.lists.wy import BOOK, DATE, LIST_URL, PRINTED, RESULTS_URL, cells, iso   # noqa: E402
from ballot.match import fits, initials_clash                               # noqa: E402
from ballot.pdftext import PDF, join, rows as pdf_rows                      # noqa: E402
from states import net                                                      # noqa: E402

STATE, FIPS, NAME = "WY", "56", "Wyoming"
GENERAL, PRIMARY = "2026-11-03", "2026-08-18"
ROSTER_DB = os.path.join(HERE, "state_wy.sqlite")
CACHE = os.path.join(HERE, "ballot_cache", "wy")
COUNTY_ZIP = os.path.join(HERE, "states_cache", "census", "cb_2024_us_county_500k.zip")
COUNTY_URL = "https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_county_500k.zip"
PRECINCT_BOOK = "2026 Primary County PbP Results - OFFICIAL.xlsx"
BALLOTS_BOOK = "2026 Primary County PbP Total Ballots Cast - OFFICIAL.xlsx"

# the roster's office words -> (race key, office_kind, office shown, roster office, the results sheets' words)
STATEWIDE = {
    "GOVERNOR": ("GOV", "governor", "Governor", "governor", "Governor"),
    "SECRETARY OF STATE": ("SOS", "secretary_of_state", "Secretary of State", "secretary of state", "Secretary of State"),
    "STATE AUDITOR": ("AUD", "state_auditor", "State Auditor", None, "State Auditor"),
    "STATE TREASURER": ("TREAS", "state_treasurer", "State Treasurer", None, "State Treasurer"),
    "SUPERINTENDENT OF PUBLIC INSTRUCTION": ("SPI", "superintendent_of_public_instruction", "Superintendent of Public Instruction",
                                             None, "Superintendent of Public Instruction"),
}
FEDERAL = ("UNITED STATES SENATOR", "UNITED STATES REPRESENTATIVE")          # the federal loader's
LEG_ROSTER = re.compile(r"STATE (SENATOR|REPRESENTATIVE) 0*(\d+)")
LEG_RESULTS = re.compile(r"(Senate|House) District 0*(\d+)")
OFFICE_ANY = re.compile(r"^(United States (Senator|Representative)|Governor|Secretary of State|State Auditor|State Treasurer|"
                        r"Superintendent of Public Instruction|(Senate|House) District \d+)(, Continued)?$")
CONT = re.compile(r", Continued$")
TALLY = ("Write-Ins", "Overvotes", "Undervotes")
WITHDRAWN_LABEL = "* Withdrawn Candidate"
WITHDREW = re.compile(r"^\*\s*(?P<name>.+?) withdrew (?:his|her|their) candidacy after official ballots had been printed"
                      r"(?: by (?P<county>[A-Z][A-Za-z ]+?) County)?", re.I)
CHAMBER = {"Senate": ("SS", "state_senate", "State Senator"), "House": ("SH", "state_house", "State Representative")}
CHAMBER_WORDS = {"Senate": "the Wyoming Senate", "House": "the Wyoming House of Representatives"}
FIELD_CODE = {"Republican": "REP", "Democratic": "DEM"}

SRC_GENERAL = "wy-sos-2026-state-general-roster"
SRC_PRIMARY = "wy-sos-2026-state-primary-summary"
SRC_PRECINCTS = "wy-sos-2026-state-primary-precincts"
SRC_ROSTER = "wy-openstates-roster"
SRC_COUNTIES = "wy-census-cb-2024-county"

SCHEMA = """
CREATE TABLE IF NOT EXISTS sl_races (race_id TEXT PRIMARY KEY, state TEXT NOT NULL, level TEXT NOT NULL, office_kind TEXT NOT NULL, office TEXT NOT NULL, jurisdiction TEXT, jurisdiction_id TEXT, county_ids TEXT, district TEXT, seat TEXT, special INTEGER NOT NULL DEFAULT 0, partisan INTEGER NOT NULL, holder_id TEXT, holder_name TEXT, holder_party TEXT, election_date TEXT NOT NULL, note TEXT);
CREATE TABLE IF NOT EXISTS sl_candidates (race_id TEXT NOT NULL, election TEXT NOT NULL, election_date TEXT, name TEXT NOT NULL, party TEXT, party_code TEXT, ballot_order INTEGER, incumbent INTEGER NOT NULL DEFAULT 0, write_in INTEGER NOT NULL DEFAULT 0, votes INTEGER, pct REAL, outcome TEXT, state_member_id TEXT, source_id TEXT, note TEXT, PRIMARY KEY (race_id, election, name));
CREATE TABLE IF NOT EXISTS sl_sources (source_id TEXT PRIMARY KEY, state TEXT, kind TEXT, agency TEXT, title TEXT, url TEXT, published TEXT, fetched TEXT, sha256 TEXT, rows INTEGER, note TEXT);
CREATE TABLE IF NOT EXISTS sl_places (kind TEXT NOT NULL, id TEXT NOT NULL, name TEXT NOT NULL, county_ids TEXT, source_id TEXT, PRIMARY KEY (kind, id));
"""


def fail(msg):
    raise SystemExit(f"Wyoming (state races): {msg}")


def sha_of(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest() if path and os.path.exists(path) else ""


def mdate(path):
    return dt.date.fromtimestamp(os.path.getmtime(path)).isoformat() if path and os.path.exists(path) else ""


# ---------- the November roster: office, party, name and a withdrawal date only ----------

def roster_rows(data):
    """([office, party, name, withdrawn date] for every entry, printed date). Only those cells are joined into text."""
    pdf = PDF(data)
    out, office, printed, titled = [], None, "", False
    for page, res in pdf.pages():
        edges, body = {}, False
        for _y, runs in pdf_rows(pdf, page, res):
            row = [(x, rs) for x, rs in cells(runs) if x < 600]      # the Division's own address block sits at the right
            if not body:      # the title and the two heading lines; the column edges come from the headings
                heads = {join(rs): x for x, rs in row}
                titled = titled or "2026 General Election Candidate Roster" in heads
                if {"Party Affiliation", "Candidate Name", "Mailing Address"} <= set(heads):
                    edges.update(party=heads["Party Affiliation"] - 12, name=heads["Candidate Name"] - 12, addr=heads["Mailing Address"] - 12)
                elif "Date Withdrawn" in heads and edges:
                    edges.update(wd=heads["Date Withdrawn"] - 12, email=heads.get("Email", 10 ** 6) - 12)
                    body = True
                continue
            left = join([r for x, rs in row if x < edges["party"] for r in rs])
            party = join([r for x, rs in row if edges["party"] <= x < edges["name"] for r in rs])
            name = join([r for x, rs in row if edges["name"] <= x < edges["addr"] for r in rs])
            if party or name:
                if not (party and name):
                    fail(f"a roster entry under {office} has a party or a name but not both; read the roster again")
                if left:
                    fail(f"a roster entry under {office} has text in the office column; read the roster again")
                out.append([office, party, re.sub(r"\s+", " ", name), ""])
                continue
            if left:
                m = PRINTED.match(left)
                if m:
                    printed = re.sub(r" 0(\d),", r" \1,", m.group(1))
                else:
                    office = left
                continue
            # an entry's second line: only a date under Date Withdrawn is looked for (city, ZIP and e-mail are never joined)
            dates = [join(rs) for x, rs in row if edges["wd"] <= x < edges["email"]]
            dates = [d for d in dates if DATE.fullmatch(d)]
            if dates and out:
                out[-1][3] = dates[0]
    if not titled:
        fail("the file is not the 2026 General Election Candidate Roster")
    return out, printed


def read_roster(cache, say=print):
    """The state rows of the roster (allowed columns only), from the federal loader's copy or a fresh copy held in memory;
    the kept JSON if neither can be read. Returns (rows, printed, fetched, sha256, how, all_rows)."""
    pdf_path = os.path.join(cache, "wy_2026_general_candidate_roster.pdf")
    json_path = os.path.join(cache, "wy_2026_state_roster.json")
    data, how, fetched = None, "", ""
    if os.path.exists(pdf_path):
        data, how, fetched = open(pdf_path, "rb").read(), "the copy the federal loader keeps in ballot_cache/wy/", mdate(pdf_path)
    else:
        last = None
        for attempt in range(3):
            try:
                data = net.get(LIST_URL, accept="application/pdf")
                break
            except (HTTPError, URLError, OSError) as e:
                last = e
                if attempt < 2:
                    time.sleep(5 * (attempt + 1))
        if data is None:
            say(f"    Wyoming (state races): the roster could not be read ({last})")
        how, fetched = "read afresh and held in memory only (the PDF is not saved)", dt.date.today().isoformat()
    if data is not None and not data.startswith(b"%PDF"):
        say("    Wyoming (state races): the roster address answered without a PDF (a bot check or a changed page)")
        data = None
    if data is None:
        if not os.path.exists(json_path):
            fail("no roster to read, and no kept copy of its state rows; stopped")
        got = json.load(open(json_path, encoding="utf-8"))
        return got["rows"], got["printed"], got["fetched"], got["sha256"], f"the state rows kept on {got['fetched']}", got["all_rows"]
    rows, printed = roster_rows(data)
    state_rows = [r for r in rows if r[0] not in FEDERAL]
    sha = hashlib.sha256(data).hexdigest()
    os.makedirs(cache, exist_ok=True)
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump({"url": LIST_URL, "fetched": fetched, "printed": printed, "sha256": sha, "all_rows": len(rows),
                   "columns": ["office", "party", "name", "withdrawn"], "rows": state_rows}, fh, ensure_ascii=False, indent=0)
    return state_rows, printed, fetched, sha, how, len(rows)


# ---------- the primary workbooks (results only: no contact columns in them) ----------

def txt(c):
    return re.sub(r"\s+", " ", str(c)).strip() if c is not None else ""


def num(c):
    """A figure; None for '-' (the race was not on that ballot) or an empty cell."""
    if c is None:
        return None
    if isinstance(c, bool):
        fail("a figure cell holds a true/false value")
    if isinstance(c, (int, float)):
        return int(c)
    s = txt(c).replace(",", "")
    if s in ("", "-"):
        return None
    if s.isdigit():
        return int(s)
    fail("a figure cell holds something other than a number")


def pkey(v):
    """A precinct number as printed; the spreadsheet stored some (01-02) as dates, read back as month-day."""
    if isinstance(v, (dt.datetime, dt.date)):
        return f"{v.month:02d}-{v.day:02d}"
    return txt(v)


def left_of(row, j, floor=0):
    k = next((k for k in range(min(j, len(row) - 1), floor - 1, -1) if txt(row[k])), None)
    return (k, txt(row[k])) if k is not None else (None, "")


def columns(offices, parties, names):
    """[(column, office, party or None, label)] for every named column. A block of columns starts under an office heading
    or after an empty column; its party is the one party heading printed over the block, None when the sheet leaves it
    out (the caller settles that, never by guessing)."""
    blocks, cur = [], None
    for j in range(1, len(names)):
        label = txt(names[j])
        if j < len(offices) and txt(offices[j]):
            cur = None                                       # a new office heading starts a new block
        if not label:
            cur = None
            continue
        if cur is None:
            _oc, office = left_of(offices, j)
            if not OFFICE_ANY.match(office):
                fail(f"column {j + 1} of a results sheet sits under {office!r}, not an office heading")
            cur = {"office": CONT.sub("", office), "cols": []}
            blocks.append(cur)
        cur["cols"].append((j, label))
    out = []
    for b in blocks:
        lo, hi = b["cols"][0][0], b["cols"][-1][0]
        heads = [txt(parties[k]) for k in range(lo, min(hi, len(parties) - 1) + 1) if txt(parties[k])]
        if len(heads) > 1:
            fail(f"two party headings over one block of {b['office']} ({heads})")
        out += [(j, b["office"], heads[0] if heads else None, label) for j, label in b["cols"]]
    return out


def lev(a, b):
    """Edit distance between two short words."""
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def near(a, b):
    """Two spellings of one candidate within one race's block: the names fit, or the family names differ by one letter and
    the given names fit (Marilyn Connoly for Marilyn Connolly)."""
    ga, fa = name_parts(a)
    gb, fb = name_parts(b)
    return fits((ga, fa), (gb, fb)) or (bool(fa) and bool(fb) and lev(fa, fb) <= 1 and fits((ga, fb), (gb, fb)))


def summary_blocks(wb):
    """{sheet: {(office, party): {"labels": [...], "votes": {label: n}, "withdrawn": (name, county) or None}}} for every sheet
    whose title begins "Statewide " (the ballots-cast sheet aside), and the titles of the sheets not read."""
    out, skipped = OrderedDict(), []
    for ws in wb.worksheets:
        if not ws.title.startswith("Statewide ") or ws.title == "Statewide Total Ballots Cast":
            skipped.append(ws.title)
            continue
        g = [list(r) for r in ws.iter_rows(values_only=True)]
        oi = next((i for i, r in enumerate(g) if any(OFFICE_ANY.match(txt(c)) for c in r)), None)
        if oi is None:
            fail(f"the summary sheet {ws.title!r} has no office headings")
        ti = next((i for i in range(oi + 3, len(g)) if g[i] and txt(g[i][0]) == "Total"), None)
        if ti is None:
            fail(f"the summary sheet {ws.title!r} has no Total row")
        offices, parties, names, totals = g[oi], g[oi + 1], g[oi + 2], g[ti]
        notes = [(j, txt(c)) for r in g[ti + 1:] for j, c in enumerate(r) if txt(c).startswith("*")]
        blocks = OrderedDict()
        for j, office, party, label in columns(offices, parties, names):
            if party is None:
                fail(f"the summary sheet {ws.title!r} has no party heading over a block of {office}")
            b = blocks.setdefault((office, party), {"labels": [], "votes": {}, "withdrawn": None})
            if label in b["votes"]:
                fail(f"{ws.title}: {office} {party} lists {label!r} twice")
            v = num(totals[j]) if j < len(totals) else None
            if v is None:
                fail(f"{ws.title}: {office} {party} has no Total for column {j + 1}")
            b["labels"].append(label)
            b["votes"][label] = v
        for (office, party), b in blocks.items():
            if WITHDRAWN_LABEL in b["votes"]:
                said = [WITHDREW.match(n) for k, n in notes if CONT.sub("", left_of(offices, k)[1]) == office]
                said = [m for m in said if m]
                if len(said) == 1:
                    b["withdrawn"] = (said[0].group("name").strip(), said[0].group("county"))
        out[ws.title] = blocks
    return out, skipped


def precinct_cells(wb):
    """[(county, precinct, office, party or None, label, votes)] for every figure in every county's precinct rows, each
    column checked against the county's own Total row. Returns (cells, problems)."""
    out, problems = [], []
    for ws in wb.worksheets:
        county = ws.title
        g = [list(r) for r in ws.iter_rows(values_only=True)]
        heads = [i for i, r in enumerate(g) if r and txt(r[0]) == "Precinct"]
        if not heads:
            fail(f"the precinct results for {county} have no Precinct heading")
        for i in heads:
            cols = columns(g[i - 2], g[i - 1], g[i])
            colsum = Counter()
            total = None
            for r in g[i + 1:]:
                a = txt(r[0]) if r else ""
                if a == "Total":
                    total = r
                    break
                if a == "" or a.startswith("Precincts Continue") or a == "Precinct":
                    continue
                p = pkey(r[0])
                for j, office, party, label in cols:
                    v = num(r[j]) if j < len(r) else None
                    if v is None:
                        continue
                    out.append((county, p, office, party, label, v))
                    colsum[j] += v
            if total is None:
                fail(f"the precinct results for {county} have no Total row")
            for j, office, party, label in cols:
                tv = num(total[j]) if j < len(total) else None
                if (tv or 0) != colsum[j]:
                    problems.append(f"{county}, {office} {party} {label}: precincts add to {colsum[j]:,}, the county Total says {tv}")
    return out, problems


def settle_parties(cells, sheets):
    """A block a county's precinct sheet prints without a party heading is given the one party the summary has for that
    office that the same county's sheet does not label; the sums checked afterwards must confirm it. Returns (cells,
    [what was settled], [what could not be])."""
    in_summary = defaultdict(set)
    for blocks in sheets.values():
        for office, party in blocks:
            in_summary[office].add(party)
    labelled = defaultdict(set)
    for county, _p, office, party, _l, _v in cells:
        if party:
            labelled[(county, office)].add(party)
    settled, unsettled, pick = [], [], {}
    for county, office in sorted({(c, o) for c, _p, o, pa, _l, _v in cells if pa is None}):
        left = in_summary[office] - labelled[(county, office)]
        if len(left) == 1:
            pick[(county, office)] = left.pop()
            settled.append(f"{county} County's precinct sheet prints one block of {office} without a party heading; read as "
                           f"{pick[(county, office)]}, the one party the sheet does not otherwise label there")
        else:
            unsettled.append(f"{county}, {office}: a block with no party heading")
    return ([(c, p, o, pa or pick[(c, o)], l, v) for c, p, o, pa, l, v in cells if pa or (c, o) in pick], settled, unsettled)


def label_map(pre_labels, sum_labels):
    """{precinct label: summary label}, allowing another spelling of one candidate in a county's sheet; None when a label
    fits no summary label, or more than one."""
    out = {}
    for lab in pre_labels:
        if lab in sum_labels:
            out[lab] = lab
            continue
        if lab in TALLY or lab == WITHDRAWN_LABEL:
            return None
        got = [s for s in sum_labels if s not in TALLY and s != WITHDRAWN_LABEL and near(lab, s)]
        if len(got) != 1:
            return None
        out[lab] = got[0]
    return out


def ballots_cast(wb):
    """{county: {precinct: {party: ballots}}} from the precinct ballots-cast book, each county checked against its Total row."""
    out, problems = {}, []
    for ws in wb.worksheets:
        county = ws.title
        g = [list(r) for r in ws.iter_rows(values_only=True)]
        hi = next((i for i, r in enumerate(g) if r and txt(r[0]) == "Precinct"), None)
        if hi is None:
            fail(f"the ballots-cast sheet for {county} has no Precinct heading")
        head = [txt(c) for c in g[hi]]
        want = [h for h in head[1:] if h]
        rows, sums = {}, Counter()
        for r in g[hi + 1:]:
            a = txt(r[0]) if r else ""
            if a == "Total":
                for h in want:
                    if (num(r[head.index(h)]) or 0) != sums[h]:
                        problems.append(f"{county} ballots cast, {h}: precincts add to {sums[h]:,}, the Total says {num(r[head.index(h)])}")
                break
            if a == "" or a.startswith("Precincts Continue"):
                continue
            p = pkey(r[0])
            if p in rows:
                fail(f"the ballots-cast sheet for {county} lists precinct {p} twice")
            rows[p] = {h: num(r[head.index(h)]) or 0 for h in want}
            for h in want:
                sums[h] += rows[p][h]
        out[county] = rows
    return out, problems


def statewide_ballots(wb):
    g = [list(r) for r in wb["Statewide Total Ballots Cast"].iter_rows(values_only=True)]
    head = next(r for r in g if "Republican" in [txt(c) for c in r])
    total = next(r for r in g if r and txt(r[0]) == "Total")
    return {txt(c): num(total[j]) or 0 for j, c in enumerate(head) if txt(c)}


# ---------- the roster of sitting members: names, parties, districts, ids and term starts only ----------

def roster():
    con = sqlite3.connect(ROSTER_DB)
    seats = defaultdict(list)
    for bid, first, last, full, party, district, chamber, start in con.execute(
            "SELECT bioguide_id, first_name, last_name, official_full, party_name, district, chamber, term_start "
            "FROM legislators WHERE is_current = 1"):
        seats[(chamber, str(district))].append({"id": bid, "first": first or "", "last": last or "", "full": full or f"{first} {last}",
                                                "party": party, "chamber": chamber, "district": str(district), "start": start or ""})
    offices = {}
    for bid, first, last, full, office, label, party in con.execute(
            "SELECT bioguide_id, first_name, last_name, official_full, office, office_label, party_name FROM officials"):
        offices[office] = {"id": bid, "first": first or "", "last": last or "", "full": full or f"{first} {last}", "party": party,
                           "label": label, "chamber": None, "district": None}
    as_of = (con.execute("SELECT MAX(updated_at) FROM legislators").fetchone()[0] or "")[:10]
    con.close()
    return seats, offices, as_of


def counties():
    """{folded county name: (GEOID, 'Albany County')} for Wyoming from the Census Bureau's cartographic county file."""
    import shapefile                                   # pyshp
    z = zipfile.ZipFile(COUNTY_ZIP)
    base = next(n[:-4] for n in z.namelist() if n.endswith(".dbf"))
    rdr = shapefile.Reader(dbf=io.BytesIO(z.read(base + ".dbf")))
    fields = [f[0] for f in rdr.fields[1:]]
    out = {}
    for rec in rdr.iterRecords():
        rec = dict(zip(fields, rec))
        if str(rec.get("STATEFP")) == FIPS:
            out[fold(str(rec["NAME"]))] = (str(rec["GEOID"]), str(rec["NAMELSAD"]))
    if len(out) != 23:
        fail(f"the county file gives {len(out)} Wyoming counties, not 23")
    return out


def forms(parts):
    """A name's (given names, family name), and the same with initials written together (J.D. Williams as JD Williams)."""
    g, f = parts
    out = [(g, f)]
    if len(g) > 1 and all(len(w) == 1 for w in g):
        out.append((["".join(g)], f))
    return out


def person_fits(name, p):
    for cand in forms(name_parts(name)):
        for reg0 in ((fold(p["first"]).split(), fold(p["last"])), name_parts(p["full"])):
            for reg in forms(reg0):
                if reg[1] and fits(cand, reg) and not initials_clash(name, reg):
                    return True
    return False


def same_person(a, b):
    return fold(a) == fold(b) or fits(name_parts(a), name_parts(b))


def long_date(iso_date):
    d = dt.date.fromisoformat(iso_date)
    return f"{d.day} {d.strftime('%B')} {d.year}"


# ---------- the load ----------

def race_of_roster(office):
    """(race_id, info) for a state office as the roster writes it."""
    if office in STATEWIDE:
        key, kind, shown, roster_office, sheet = STATEWIDE[office]
        return f"2026-{STATE}-{key}", {"level": "statewide", "office_kind": kind, "office": shown, "district": None, "chamber": None,
                                       "roster": roster_office, "results": sheet}
    m = LEG_ROSTER.fullmatch(office or "")
    if m:
        chamber = "Senate" if m.group(1) == "SENATOR" else "House"
        key, kind, shown = CHAMBER[chamber]
        d = str(int(m.group(2)))
        return f"2026-{STATE}-{key}{d}", {"level": "legislature", "office_kind": kind, "office": shown, "district": d, "chamber": chamber,
                                          "roster": None, "results": f"{chamber} District {d}"}
    fail(f"an office the loader does not know on the roster: {office!r}")


def race_of_results(office):
    """race_id for an office heading in the results, or None for the federal offices (the federal loader's)."""
    if office.startswith("United States "):
        return None
    for key, kind, shown, roster_office, sheet in STATEWIDE.values():
        if office == sheet:
            return f"2026-{STATE}-{key}"
    m = LEG_RESULTS.fullmatch(office)
    if m:
        return f"2026-{STATE}-{CHAMBER[m.group(1)][0]}{int(m.group(2))}"
    fail(f"an office heading the loader does not know in the results: {office!r}")


def load(db_path, say=print, cache=CACHE):
    seats, offices, as_of = roster()
    cmap = counties()
    checks = []

    # ---- the November roster
    rrows, printed, r_fetched, r_sha, r_how, r_all = read_roster(cache, say)
    races = OrderedDict()
    for office, party, name, wd in rrows:
        rid, info = race_of_roster(office)
        races.setdefault(rid, info)

    # ---- the primary: the summary, checked against the precinct files
    zpath = os.path.join(cache, "wy_2026_primary_results.zip")
    if not os.path.exists(zpath):
        net.download(RESULTS_URL, zpath, max_age_days=30, say=say)
    with zipfile.ZipFile(zpath) as z:
        names_in = z.namelist()
        for need in (BOOK, PRECINCT_BOOK, BALLOTS_BOOK):
            if need not in names_in:
                fail(f"{need} is not in the primary results zip")
        wb_sum = openpyxl.load_workbook(io.BytesIO(z.read(BOOK)), read_only=True, data_only=True)
        wb_pre = openpyxl.load_workbook(io.BytesIO(z.read(PRECINCT_BOOK)), read_only=True, data_only=True)
        wb_bal = openpyxl.load_workbook(io.BytesIO(z.read(BALLOTS_BOOK)), read_only=True, data_only=True)
    sheets, not_read = summary_blocks(wb_sum)
    state_ballots = statewide_ballots(wb_sum)
    raw_cells, pre_problems = precinct_cells(wb_pre)
    bal, bal_problems = ballots_cast(wb_bal)
    pcells, settled, unsettled = settle_parties(raw_cells, sheets)
    checks += pre_problems + bal_problems + unsettled
    county_names = {ws.title for ws in wb_pre.worksheets}
    unknown_c = sorted(c for c in county_names if fold(c) not in cmap)
    if unknown_c or len(county_names) != 23:
        fail(f"the precinct results' county sheets do not match the Census file's 23 counties ({unknown_c})")
    missing_p = sorted({f"{c} {p}" for c, p, _o, _pa, _l, _v in pcells if p not in bal.get(c, {})})
    if missing_p:
        checks.append(f"precincts in the results not in the ballots-cast file: {', '.join(missing_p[:12])}")
    pre = defaultdict(lambda: {"votes": defaultdict(Counter), "precincts": set(), "counties": set()})
    for c, p, office, party, lab, v in pcells:
        b = pre[(office, party)]
        b["votes"][lab][c] += v
        b["precincts"].add((c, p))
        b["counties"].add(c)

    fields_src = {}                                          # (race, party) -> summary block confirmed by the precincts
    set_aside = defaultdict(list)                            # sheet -> blocks the precinct files do not confirm
    spellings = []
    for sheet, blocks in sheets.items():
        for (office, party), b in blocks.items():
            rid = race_of_results(office)
            if rid is None:
                continue
            p = pre.get((office, party))
            m = label_map(list(p["votes"]), b["labels"]) if p else None
            sums = Counter()
            for lab, by_county in (p["votes"].items() if m else []):
                sums[m[lab]] += sum(by_county.values())
            if not m or set(sums) != set(b["votes"]) or any(sums[k] != v for k, v in b["votes"].items()):
                set_aside[sheet].append(f"{office} {party}")
                continue
            if (rid, party) in fields_src:
                fail(f"{office} {party} is confirmed twice in the summary")
            for lab, s_lab in m.items():
                if lab != s_lab:
                    spellings.append(f"{office} {party}: \"{lab}\" in {', '.join(sorted(p['votes'][lab]))} County's sheet for "
                                     f"\"{s_lab}\"")
            fields_src[(rid, party)] = dict(b, sheet=sheet, office=office, precincts=p["precincts"], counties=p["counties"])
    wanted = {(race_of_results(o), pa) for (o, pa) in pre if race_of_results(o)}
    unconfirmed = sorted(f"{r} {pa}" for r, pa in wanted - set(fields_src))
    if unconfirmed:
        checks.append(f"precinct-file blocks with no matching summary block: {', '.join(unconfirmed)}")

    # precinct by precinct, each chamber's votes (with write-ins, overvotes and undervotes) against the party's ballots cast:
    # every voter has one House race and every statewide race; the Senate is only half the state this year
    per = defaultdict(int)
    house_of = defaultdict(set)
    for c, p, office, party, _lab, v in pcells:
        if office.startswith("United States "):
            continue
        kind = office.split(" District")[0] if " District " in office else office
        per[(c, p, kind, party)] += v
        if kind == "House":
            house_of[(c, p)].add(office)
    split = {k for k, v in house_of.items() if len(v) > 1}
    unreconciled, senate_short, senate_short_split = [], 0, 0
    for (c, p, kind, party), v in sorted(per.items()):
        cast = bal.get(c, {}).get(p, {}).get(party)
        if cast is None:
            continue
        if kind == "Senate":
            if v > cast:
                unreconciled.append(f"{c} {p} Senate {party} ({v:,} against {cast:,} ballots)")
            elif v < cast:
                senate_short += 1
                senate_short_split += (c, p) in split
        elif v != cast:
            unreconciled.append(f"{c} {p} {kind} {party} ({v:,} against {cast:,} ballots)")
    if senate_short != senate_short_split:
        checks.append(f"{senate_short - senate_short_split} precinct Senate totals short of the ballots cast in precincts the "
                      "results do not split between House districts")
    for (rid, party), f in sorted(fields_src.items()):
        if races.get(rid, {}).get("level") == "statewide" and state_ballots.get(party) != sum(f["votes"].values()):
            unreconciled.append(f"{rid} {party} ({sum(f['votes'].values()):,} against the statewide sheet's "
                                f"{state_ballots.get(party)} ballots)")
    if unreconciled:
        checks.append("primary figures that do not add up to the ballots cast: " + "; ".join(unreconciled))
    n_prec = len({(c, p) for c, p, *_ in pcells})

    # which races the primary had, and the roster's seats against them
    primary_races = {rid for rid, _pa in fields_src}
    not_on_roster = sorted(primary_races - set(races))
    if not_on_roster:
        checks.append(f"on the August 18 primary ballot but no candidate on the November roster: {', '.join(not_on_roster)}")
    no_primary = sorted(rid for rid in races if rid not in primary_races)
    if no_primary:
        checks.append(f"on the November roster but not in the August 18 primary results: {', '.join(no_primary)}")
    house = sorted(int(i["district"]) for i in races.values() if i["chamber"] == "House")
    if house != list(range(1, 63)):
        checks.append(f"State House districts on the roster are not 1 to 62: missing {sorted(set(range(1, 63)) - set(house))}")
    sen = sorted(int(i["district"]) for i in races.values() if i["chamber"] == "Senate")
    parity = Counter(d % 2 for d in sen).most_common(1)[0][0] if sen else 1
    regular = [d for d in sen if d % 2 == parity]
    if regular != list(range(2 - parity, 32, 2)):
        checks.append(f"the regular State Senate seats on the roster are not every {'odd' if parity else 'even'} district: {regular}")
    early = [d for d in sen if d % 2 != parity]
    for (ch, d), hs in seats.items():
        if len(hs) != 1:
            checks.append(f"the roster lists {len(hs)} sitting members for {ch} District {d}")

    # ---- holders and notes
    holders, notes, special, county_ids = {}, {}, {}, {}
    for rid, i in races.items():
        if i["level"] == "legislature":
            hs = seats.get((i["chamber"], i["district"]), [])
            holders[rid] = hs
            if not hs:
                notes[rid] = f"The Open States roster ({as_of}) lists no sitting member for this seat."
            got = set()
            for party in ("Republican", "Democratic"):
                got |= fields_src.get((rid, party), {}).get("counties", set())
            county_ids[rid] = ",".join(sorted(cmap[fold(c)][0] for c in got)) or None
            if not got:
                checks.append(f"{rid}: no precinct rows in the primary results, so no counties")
        else:
            h = offices.get(i["roster"]) if i["roster"] else None
            holders[rid] = [h] if h else []
            if not h:
                notes[rid] = "The Open States roster this site uses does not carry this office, so today's holder is not shown."
    for d in early:
        rid = f"2026-{STATE}-SS{d}"
        special[rid] = 1
        hs = holders.get(rid, [])
        since = f" The Open States roster shows today's member serving since {long_date(hs[0]['start'])}." if hs and hs[0]["start"] else ""
        notes[rid] = ((notes[rid] + " ") if rid in notes else "") + (
            f"Senate District {d} is the one {'even' if parity else 'odd'}-numbered Senate district on this year's roster; "
            f"the other Senate seats up this year are {'odd' if parity else 'even'}-numbered, and Wyoming senators serve four "
            f"years.{since} It is treated here as an election for the rest of the term; the roster itself does not say so in words.")
        checks.append(f"{rid} marked special (off-cycle seat on the roster){since}")

    # other-chamber districts that share a precinct with each legislative race, from the primary results
    prec_of = defaultdict(set)
    for (rid, _party), f in fields_src.items():
        prec_of[rid] |= f["precincts"]
    everyone = [p for ps in seats.values() for p in ps] + list(offices.values())
    # every name each race carries this year (the roster and the primary), and each roster person's own race on the ballot
    names_in = defaultdict(set)
    for office, _party, name, _wd in rrows:
        names_in[race_of_roster(office)[0]].add(name)
    for (rid, _party), f in fields_src.items():
        names_in[rid] |= {lab for lab in f["labels"] if lab not in TALLY and lab != WITHDRAWN_LABEL}
        if f["withdrawn"]:
            names_in[rid].add(f["withdrawn"][0])
    own_race = {}
    for rid, i in races.items():
        for h in holders[rid]:
            own_race[h["id"]] = rid

    def running_at_home(p, rid):
        """True when the person's own seat or office is on this year's ballot with a candidate of that name: then a candidate
        of the same name in another race is taken to be someone else."""
        home = own_race.get(p["id"])
        return bool(home and home != rid and any(person_fits(n, p) for n in names_in[home]))

    def sitting(rid, names):
        i, out = races[rid], {}
        hs = holders[rid]
        pairs = [(n, h) for n in names for h in hs if person_fits(n, h)]
        for n, h in pairs:
            if sum(1 for a, _ in pairs if a == n) == 1 and sum(1 for _, b in pairs if b["id"] == h["id"]) == 1:
                out[n] = (h["id"], 1, None)
        for n in names:
            if n in out:
                continue
            if i["level"] == "legislature":
                other = "House" if i["chamber"] == "Senate" else "Senate"
                touching = {r2 for r2 in prec_of if r2 != rid and races.get(r2, {}).get("chamber") == other and prec_of[r2] & prec_of[rid]}
                pool = [p for r2 in touching for p in seats.get((other, races[r2]["district"]), [])]
            else:
                pool = [p for p in everyone if not any(p["id"] == h["id"] for h in hs)]
            got = [p for p in pool if person_fits(n, p)]
            if len(got) == 1 and not running_at_home(got[0], rid):
                p = got[0]
                out[n] = (p["id"], 0, f"Serves today in {CHAMBER_WORDS[p['chamber']]}, District {p['district']}." if p["chamber"]
                          else f"Serves today as {p['label']}.")
        return out

    cand = []

    # ---- the November ballot
    on_ballot, shown, withdrawn = defaultdict(list), defaultdict(list), []
    for office, party, name, wd in rrows:
        rid, _ = race_of_roster(office)
        shown[(rid, party)].append(name)
        if wd:
            withdrawn.append(rid)
            continue
        on_ballot[rid].append((party, name))
    for rid, rows in on_ballot.items():
        fit = sitting(rid, [n for _p, n in rows])
        for party, name in rows:
            mid, inc, note = fit.get(name, (None, 0, None))
            n = [note] if note else []
            f = fields_src.get((rid, party))
            if party in FIELD_CODE and not any(same_person(name, x) for x in (f["labels"] if f else []) + (
                    [f["withdrawn"][0]] if f and f["withdrawn"] else [])):
                n.append(f"Not printed on the August 18 {party} primary ballot for this seat; the roster does not say how the "
                         "nomination was made.")
            if inc and holders[rid]:
                h = next(h for h in holders[rid] if h["id"] == mid)
                if h["party"] and h["party"] != party:
                    checks.append(f"{rid}: sitting member listed as {h['party']}, on the roster as {party}")
            cand.append((rid, "general", GENERAL, name, party, party_code(party), None, inc, 0, None, None, None, mid, SRC_GENERAL,
                         " ".join(n) or None))

    # ---- the August 18 primary fields
    fields = Counter()
    upset, open_ = [], []
    for (rid, party), f in sorted(fields_src.items()):
        if rid not in races:
            continue
        people = [lab for lab in f["labels"] if lab not in TALLY]
        if len(people) < 2:
            continue
        if party not in FIELD_CODE:
            fail(f"a primary field for a party the loader does not know: {party}")
        entries = []
        for lab in people:
            if lab == WITHDRAWN_LABEL:
                if not f["withdrawn"]:
                    checks.append(f"{rid} {party}: a withdrawn candidate's votes with no name in the footnote; left out of the field")
                    continue
                who, where = f["withdrawn"]
                note = (f"Withdrew after {where} County's primary ballots had been printed; the official summary counts the votes cast "
                        f"for this candidate in {where} County." if where else
                        "Withdrew after the primary ballots had been printed; the official summary still counts the votes cast for this "
                        "candidate.")
                entries.append((who, f["votes"][lab], note))
            else:
                entries.append((lab, f["votes"][lab], None))
        counted = sum(v for _n, v, _x in entries) + f["votes"].get("Write-Ins", 0)
        noms = [x for x in shown.get((rid, party), [])]
        won = [e for e in entries if any(same_person(e[0], x) for x in noms)]
        top = sorted(entries, key=lambda e: -e[1])
        tie = len(top) > 1 and top[0][1] == top[1][1]
        if len(won) == 1:
            winner = won[0][0]
            if tie or top[0][0] != winner:
                upset.append(f"{rid} {party}")
        elif not won and not tie:
            winner = top[0][0]
            open_.append(f"{rid} {party} (the most votes: {winner}; not on the November roster)")
        else:
            winner = None
            open_.append(f"{rid} {party} ({len(won)} names fit the November roster)")
        fields[races[rid]["office_kind"] if races[rid]["level"] == "legislature" else "statewide"] += 1
        fit = sitting(rid, [e[0] for e in entries])
        for who, votes, note in entries:
            mid, inc, snote = fit.get(who, (None, 0, None))
            extra = []
            if winner and who == winner and not won:
                extra.append("Won the most votes in the primary; not on the November roster (the roster does not say why).")
            cand.append((rid, f"primary-{FIELD_CODE[party]}", PRIMARY, who, party, party_code(party), None, inc, 0, votes,
                         round(100 * votes / counted, 1) if counted else None,
                         None if winner is None else ("advanced" if who == winner else "lost"), mid, SRC_PRIMARY,
                         " ".join(x for x in [snote, note] + extra if x) or None))

    # ---- checks on the whole
    keys = Counter((c[0], c[1], c[3]) for c in cand)
    dup = [k for k, v in keys.items() if v > 1]
    if dup:
        fail(f"the same name twice in one election: {dup}")
    gen_by_race = Counter(c[0] for c in cand if c[1] == "general")
    if gen_by_race.total() + len(withdrawn) != len(rrows):
        fail("November rows written plus withdrawn do not equal the roster's state rows")
    empty = sorted(rid for rid in races if gen_by_race[rid] == 0)

    race_rows = []
    for rid, i in races.items():
        hs = holders[rid]
        jur = f"{i['chamber']} District {i['district']}" if i["level"] == "legislature" else NAME
        race_rows.append((rid, STATE, i["level"], i["office_kind"], i["office"], jur, FIPS, county_ids.get(rid), i["district"], None,
                          special.get(rid, 0), 1, ",".join(h["id"] for h in hs) or None, " and ".join(h["full"] for h in hs) or None,
                          ", ".join(dict.fromkeys(h["party"] for h in hs if h["party"])) or None, GENERAL, notes.get(rid)))
    place_rows = [("county", geoid, full, None, SRC_COUNTIES) for geoid, full in sorted(cmap.values())]

    n_field_rows = sum(1 for c in cand if c[1] != "general")
    aside = "; ".join(f"{s}: {len(v)} blocks" for s, v in set_aside.items())
    src = [
        (SRC_GENERAL, STATE, "official candidate list", "Wyoming Secretary of State, Elections Division",
         "2026 General Election Candidate Roster" + (f" (printed {printed})" if printed else "") + ": state offices and the Legislature",
         LIST_URL, iso(printed), r_fetched, r_sha, len(rrows),
         f"Every office on the roster ({r_all} entries, read from {r_how}); the {len(rrows)} for state offices and the Legislature kept "
         "(the two federal races are the federal loader's). Office, party and name only, and a date under Date Withdrawn; the "
         "mailing address, city, state and ZIP, telephone and e-mail columns are never read. The kept rows, those columns only, are "
         "ballot_cache/wy/wy_2026_state_roster.json; the fingerprint is of the PDF. The roster gives no ballot order (county clerks "
         f"print the ballots), so none is stored. Withdrawn, left off the November ballot: {len(withdrawn)}."),
        (SRC_PRIMARY, STATE, "official results", "Wyoming Secretary of State, Elections Division",
         "2026 Official Primary Election Results (August 18, 2026): Statewide Candidates, Statewide Senate and Statewide House Official "
         "Summaries, from the zip file of data files (\"2026 Primary Results Summaries - OFFICIAL.xlsx\")", RESULTS_URL, "", mdate(zpath),
         sha_of(zpath), n_field_rows,
         "Votes from each office's Total row; a party primary is a field when two or more names were printed on its ballot. Write-ins "
         "count in the share but are not listed; over- and undervotes are left out. A candidate who withdrew after the ballots were "
         "printed is kept with the votes the summary counts. Every block kept equals the county precinct-by-precinct results, "
         "candidate by candidate. Set aside, because the precinct results do not add up to them: "
         + (aside or "nothing") + ("; the sheet \"Statewide Senate Even\" names districts 2 to 30, even, none of which but District 6 is "
         "on the 2026 roster, none of which is in the precinct results, and its District 6 block differs from the one the precinct "
         "results confirm in \"Statewide Senate Odd\"" if "Statewide Senate Even" in set_aside else "") + ". Not read: "
         + ", ".join(not_read) + ". "
         + ("Every figure adds up to the party ballots cast, precinct by precinct." if not unreconciled
            else "Did not add up: " + "; ".join(unreconciled) + ".")),
        (SRC_PRECINCTS, STATE, "official results (used as a check)", "Wyoming Secretary of State, Elections Division",
         "2026 Primary County PbP Results - OFFICIAL.xlsx and 2026 Primary County PbP Total Ballots Cast - OFFICIAL.xlsx, from the same zip",
         RESULTS_URL, "", mdate(zpath), sha_of(zpath), sum(len(v) for v in bal.values()),
         f"Every county's precinct rows ({n_prec} precincts) summed and checked against the county's Total row, and each summary "
         "block confirmed from them. Precinct by precinct, the votes, write-ins, overvotes and undervotes in each statewide race and "
         "in the House races together equal that party's ballots cast; in the Senate, only half the state votes this year, and "
         f"{senate_short} precinct totals fall short of the ballots cast, {'all' if senate_short == senate_short_split else senate_short_split} "
         "of them in precincts the results split between House districts. A district's counties (county_ids) are those where its "
         "race was on the ballot. Precinct numbers the spreadsheet stored as dates are read as month-day. "
         + (" ".join(s_ + "." for s_ in settled) + " " if settled else "")
         + (("Another spelling of a candidate in one county's sheet, counted with the summary's: " + "; ".join(spellings) + ". ")
            if spellings else "")
         + (f"Problems: {len(pre_problems) + len(bal_problems) + len(unsettled)}." if pre_problems or bal_problems or unsettled
            else "No problems.")),
        (SRC_ROSTER, STATE, "roster", "Open States people project (CC0)",
         "Wyoming legislators and statewide officials, as loaded into state_wy.sqlite", "https://github.com/openstates/people",
         as_of, as_of, "", sum(len(v) for v in seats.values()) + len(offices),
         "Today's holder of each seat and office (names, parties, districts, ids and term starts only). The roster does not carry the "
         "Auditor, the Treasurer or the Superintendent of Public Instruction."),
        (SRC_COUNTIES, STATE, "official boundaries", "U.S. Census Bureau",
         "Cartographic boundary file, counties, 2024, 1:500,000 (cb_2024_us_county_500k)", COUNTY_URL, "", mdate(COUNTY_ZIP),
         sha_of(COUNTY_ZIP), len(place_rows), "Wyoming's 23 counties: names and GEOIDs only."),
    ]

    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA)
    with con:
        con.execute("DELETE FROM sl_candidates WHERE race_id IN (SELECT race_id FROM sl_races WHERE state = ?) OR race_id LIKE ?",
                    (STATE, f"2026-{STATE}-%"))
        con.execute("DELETE FROM sl_races WHERE state = ?", (STATE,))
        con.execute("DELETE FROM sl_places WHERE source_id LIKE 'wy-%' OR (kind = 'county' AND id GLOB '56[0-9][0-9][0-9]')")
        con.execute("DELETE FROM sl_sources WHERE state = ?", (STATE,))
        con.executemany("INSERT INTO sl_races VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", race_rows)
        con.executemany("INSERT INTO sl_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", cand)
        con.executemany("INSERT INTO sl_places VALUES (?,?,?,?,?)", place_rows)
        con.executemany("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", src)
    con.close()

    # ---- the report: counts only
    kind_of = lambda rid: races[rid]["office_kind"] if races[rid]["level"] == "legislature" else "statewide"
    by = Counter(kind_of(rid) for rid in races)
    gen = Counter(kind_of(c[0]) for c in cand if c[1] == "general")
    alone = Counter(kind_of(rid) for rid, v in gen_by_race.items() if v == 1)
    inc = Counter(kind_of(c[0]) for c in cand if c[1] == "general" and c[7])
    say(f"    Wyoming (state races): {by['state_senate']} Senate seats ({len(early)} off-cycle), {by['state_house']} House seats, "
        f"{by['statewide']} statewide offices; {gen.total()} candidates on the November ballot (Senate {gen['state_senate']}, House "
        f"{gen['state_house']}, statewide {gen['statewide']}; {len(withdrawn)} withdrawn left off; unopposed: Senate "
        f"{alone['state_senate']}, House {alone['state_house']}, statewide {alone['statewide']}); sitting member on the ballot: Senate "
        f"{inc['state_senate']}, House {inc['state_house']}, statewide {inc['statewide']}; primary fields: Senate "
        f"{fields['state_senate']}, House {fields['state_house']}, statewide {fields['statewide']} ({n_field_rows} rows, official "
        f"votes, each confirmed from the precinct results)")
    for label, items in (("no candidate on the November roster", empty),
                         ("summary blocks set aside (the precinct results do not add up to them)",
                          [f"{s} ({len(v)})" for s, v in set_aside.items()]),
                         ("the November nominee is not the primary's top vote-getter", upset), ("primary fields left open", open_)):
        if items:
            say(f"    CHECK Wyoming (state races): {label}: {', '.join(items)}")
    for c in checks:
        say(f"    CHECK Wyoming (state races): {c}")
    return len(cand)


if __name__ == "__main__":
    args = sys.argv[1:]
    cache = CACHE
    if "--cache" in args:
        i = args.index("--cache")
        cache = args[i + 1]
        del args[i:i + 2]
    if len(args) != 1:
        raise SystemExit("usage: python ballot/state_local_wy.py <database file> [--cache <folder>]")
    load(args[0], cache=cache)
