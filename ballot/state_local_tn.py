"""
ballot/state_local_tn.py - Tennessee's state races on the November 3, 2026 ballot, into ballot_local_2026.sqlite:

  - Governor, the one statewide office Tennessee's voters elect (the attorney general is appointed by the Supreme
    Court; the secretary of state, treasurer and comptroller are elected by the General Assembly; the lieutenant
    governor is the Senate's speaker, chosen by the Senate). No running mate shares the ticket.
  - the seventeen odd-numbered Senate seats. Senators serve four years, half the chamber every two: the odd-numbered
    districts were elected in 2022 and are up in 2026, the even-numbered in 2028 (states/places.py records the same,
    and the roster agrees: eight odd-district senators first took office after the 2022 election, none after 2024).
    A Senate seat the Secretary's list or results name for the rest of a term is added as a special election.
  - all 99 seats of the House of Representatives (two-year terms);
with each party's August 6 primary field and its official votes. The federal ballot database is never opened here.

Sources. The Secretary of State's sites (sos.tn.gov, its file host sos-prod.tnsosgovfiles.com and elections.tn.gov)
answer this tool's honest User-Agent with "403 Request blocked" from CloudFront (seen again 2026-09-30), so this loader
downloads nothing: it reads what is saved from a browser into ballot_cache/tn/, the folder the federal loader
(ballot/lists/tn.py) reads.
  - The Division of Elections' candidate lists for the November 3, 2026 General Election, linked from
    sos.tn.gov/elections/2026-candidate-lists: Governor (Governor_Nov2026.pdf), Tennessee Senate and Tennessee House of
    Representatives. They are found by what they say they are, whatever the files are called: a PDF whose title reads
    "Candidates for Governor" (or for the Tennessee Senate, or the Tennessee House of Representatives) and says
    November 3, 2026 above its first table; or a workbook whose heading row names Office (or District), Name and Party
    and which says it is the November list in a title row, its sheet name or its file name. The federal lists in the
    same folder are left to the federal loader, and a list from before the primary is refused. The layout is the
    federal loader's (the Division's lists of 2022 and 2024): each district's table headed "District N" (an office or
    district column is read instead where the table has one), a heading row naming Name (or Candidate) and Party, then
    the contact columns. When both a PDF and a workbook of one list are there, the workbook is used (its cells hold the
    whole name) and the PDF is checked against it.
  - The official results by county of the August 6, 2026 primaries, one PDF per party, 20260806RepublicanPrimarybyCounty.pdf
    and 20260806DemocraticPrimarybyCounty.pdf (sos.tn.gov/elections/results): each office a section, its candidates
    numbered in ballot order, a row per county and a TOTALS row. Every section's county rows must add up to its TOTALS
    row, and the Governor's must have all 95 counties. Only the Republican and Democratic parties hold primaries.
Who holds each seat comes from the Open States roster in state_tn.sqlite (legislators, is_current = 1; the officials
table for the Governor): names, party and ids only. County codes come from the Census Bureau's 2024 county file
(states_cache/census/), matched by name to the results' county rows; the counties a district reaches are the ones its
primary sections list (derived, and said so).

Until the November lists are saved, every seat is written with its holder and no candidates, and its note says the
list is not loaded; primary fields are written from whatever results file is there, the top vote-getter advancing
(Tennessee nominates by plurality) unless the November list names someone else.

Privacy. From a list only the office, district, name and party cells are ever turned into text (and, in a workbook, a
Status column where one exists). Column edges come from the table's own heading row; every cell from
the first contact column on (address, city, ZIP, telephone, e-mail, website, filing dates) is never joined, printed,
logged, cached or stored, and this loader copies or saves no file. An error names the file and the check, never the
row. The results carry names and votes only. Before anything is written, every stored text is checked for anything
that looks like a contact detail, and the load stops (without showing it) if one does.

Ballot order. The lists print no order numbers, so no November ballot_order is stored; the primary rows follow the
other loaders (ordered by votes, ballot_order empty).

    python -m ballot.state_local_tn <path to a test database>
"""

import datetime as dt
import glob
import hashlib
import io
import json
import os
import re
import sqlite3
import sys
import zipfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from ballot.common import CACHE, fold, name_parts, party_code  # noqa: E402
from ballot.lists.tn import (CANDIDATE, CAPS, CAPS_RESULTS, CODE, COLUMNS, COUNTY, DATE, FILES, FOOTER, FURNITURE,  # noqa: E402
                             GENERAL_TEXT, LIST_PAGE, NOT_ON_LIST, PRIMARY_TEXT, RESULTS, RESULTS_PAGE, TOTAL_COUNTIES, TOTALS,
                             WRITE_IN, WRITE_IN_WON, cells, iso, party_of, pick, shown)
from ballot.match import fits  # noqa: E402
from ballot.pdftext import PDF, join, lines, rows as pdf_rows  # noqa: E402

STATE, FIPS = "TN", "47"
GENERAL, PRIMARY = "2026-11-03", "2026-08-06"
FOLDER = os.path.join(CACHE, "tn")
ROSTER = os.path.join(HERE, "state_tn.sqlite")
COUNTY_ZIP = os.path.join(HERE, "states_cache", "census", "cb_2024_us_county_500k.zip")
COUNTY_URL = "https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_county_500k.zip"
SENATE_SEATS, HOUSE_SEATS = 33, 99
SENATE_UP = list(range(1, SENATE_SEATS + 1, 2))        # the odd half in 2026 (states/places.py: {"odd": 2026, "even": 2028})
SRC_ROSTER, SRC_COUNTY = "tn-openstates-roster", "tn-census-2024-county-codes"
AGENCY = "Tennessee Secretary of State, Division of Elections"

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

KINDS = ("governor", "state_senate", "state_house")
KIND_WORDS = {"governor": "Governor", "state_senate": "Tennessee Senate", "state_house": "Tennessee House of Representatives"}

# office titles, as a list's title, a workbook's Office cell or a results section prints them
FEDERAL = re.compile(r"^United States\b|\bCongress\b|\bU\.\s?S\.\s", re.I)
PARTY_OFFICE = re.compile(r"Executive Committee|Committee(?:wo)?m[ae]n\b|\bDelegate", re.I)
GOV_T = re.compile(r"^Governor\b(?P<rest>.*)$", re.I)
SENATE_T = re.compile(r"^(?:Tennessee\s+)?(?:State\s+)?Senat(?:e|or|orial)\b[\s,]*(?:District\s*)?(?:No\.?\s*)?(?P<d>\d{1,2})?\b(?P<rest>.*)$", re.I)
HOUSE_T = re.compile(r"^(?:Tennessee\s+)?(?:State\s+)?(?:House\s+of\s+Representatives|Representative|House)\b[\s,]*(?:District\s*)?"
                     r"(?:No\.?\s*)?(?P<d>\d{1,2})?\b(?P<rest>.*)$", re.I)
SPECIAL = re.compile(r"^[\s,:(–-]*(?:Unexpired(?:\s+Term)?|Special(?:\s+Election)?|(?:To\s+)?Fill\s+(?:the\s+)?Unexpired\s+Term)[\s)]*$", re.I)
STATEWIDE = re.compile(r"^[\s,:(–-]*Statewide[\s)]*$", re.I)
DISTRICT_LINE = re.compile(r"^(?:(?:Tennessee\s+|State\s+)?(?:Senate|Senatorial|House(?:\s+of\s+Representatives)?|Representative)\s+)?"
                           r"District\s*(?:No\.?\s*)?(?P<d>\d{1,2})\b(?P<rest>.*)$", re.I)
TITLE_LINE = re.compile(r"^Candidates for (?P<o>.+)$", re.I)

# a list's table headings, lower case
HEAD_NAME = {"candidate", "candidate name", "candidates", "name", "name of candidate", "candidate's name"}
HEAD_PARTY = {"party", "party affiliation", "political party", "affiliation"}
HEAD_DISTRICT = {"district", "dist", "dist.", "district no.", "district number"}
HEAD_OFFICE = {"office", "office name", "contest", "office title"}
HEAD_STATUS = {"status", "candidate status"}
LIST_FURNITURE = re.compile(rf"{DATE}|General Election|^Page \d+(?: of \d+)?$|^(Juri\w*|Statewide|None)\b", re.I)
NONE_ROW = re.compile(r"^(No Candidates?(?: Qualified| Filed)?|None Qualified|None|Vacant)$", re.I)
OFF_BALLOT = re.compile(r"withdr|disqual|did not qualify|not qualified|removed|deceased", re.I)
CONTACT = re.compile(r"@|https?:|www\.|\.(?:com|org|net|gov|us)\b|\d{3}|P\.?\s?O\.?\s+Box|\bSuite\b", re.I)

NO_LIST = "Tennessee's official November candidate list for this office is not loaded yet."
NONE_ON_LIST = "No candidate for this seat is on the Secretary of State's November list."
NONE_QUALIFIED = "The Secretary of State's November list says no candidate qualified for this seat."
SENATE_NOTE = "Tennessee senators serve four years; the odd-numbered districts are elected in 2026, the even-numbered in 2028."
SPECIAL_NOTE = "An election for the rest of the term, as the Secretary of State's {what} names it."
SPECIAL_GUESS = ("This even-numbered seat is not due until 2028; it is on the Secretary of State's {what}, so it is shown as an "
                 "election for the rest of the term (the {what} does not say so).")
GOV_NOTE = ("Tennessee elects its governor alone: the attorney general is appointed by the Supreme Court, the secretary of state, "
            "treasurer and comptroller are elected by the General Assembly, and the lieutenant governor is the Senate's speaker.")


class NotTheList(Exception):
    pass


class Unknown(Exception):
    pass


def office_parts(text, district=None):
    """(kind, district or None, special) for an office as printed, with a district from elsewhere when the office has
    none; None for a federal or party office (not this loader's); Unknown for anything else."""
    t = re.sub(r"\s+", " ", text or "").strip()
    if not t or FEDERAL.search(t) or PARTY_OFFICE.search(t):
        return None
    m = GOV_T.match(t)
    if m:
        rest = m.group("rest")
        if rest.strip() and not STATEWIDE.match(rest):
            raise Unknown(t)
        return "governor", None, 0
    for pat, kind in ((SENATE_T, "state_senate"), (HOUSE_T, "state_house")):
        m = pat.match(t)
        if not m:
            continue
        d, rest, special = m.group("d"), m.group("rest").strip(), 0
        if rest:
            if not SPECIAL.match(rest):
                raise Unknown(t)
            special = 1
        d = d or (district_number(district) if district not in (None, "") else None)
        top = SENATE_SEATS if kind == "state_senate" else HOUSE_SEATS
        if d is not None and not 1 <= int(d) <= top:
            raise Unknown(t)
        return kind, (int(d) if d is not None else None), special
    raise Unknown(t)


def district_number(cell):
    """12 from '12', '12.0' (a workbook number), 'District 12' or 'District 12 (Unexpired Term)'."""
    s = re.sub(r"\s+", " ", str(cell)).strip()
    if re.fullmatch(r"\d{1,2}(?:\.0)?", s):
        return int(float(s))
    m = DISTRICT_LINE.match(s)
    if m and (not m.group("rest").strip() or SPECIAL.match(m.group("rest"))):
        return int(m.group("d"))
    raise Unknown(s)


def race_id(kind, district):
    return f"2026-{STATE}-GOV" if kind == "governor" else f"2026-{STATE}-{'SS' if kind == 'state_senate' else 'SH'}{int(district)}"


def title_kind(text):
    """What a "Candidates for ..." title line names: a kind of KINDS, 'federal', 'other'; None if it is not a title line."""
    m = TITLE_LINE.match(re.sub(r"\s+", " ", text or "").strip())
    if not m:
        return None
    o = m.group("o").strip()
    if FEDERAL.search(o):
        return "federal"
    try:
        got = office_parts(re.split(r"\s+[-–,]\s+|\s+(?=" + DATE + ")", o)[0])
    except Unknown:
        return "other"
    return got[0] if got else "other"


def head_kind(text):
    """What a line above a list's first table names as the list's office: a "Candidates for ..." title, or a line that is
    nothing but an office (Governor, Tennessee Senate, Tennessee House of Representatives, United States Senate ...)."""
    t = title_kind(text)
    if t or len(text) > 60:
        return t
    if re.match(r"^United States (?:Senate|House of Representatives)\b", text, re.I):
        return "federal"
    try:
        o = office_parts(text)
    except Unknown:
        return None
    return o[0] if o and o[1] is None else None


def key(text):
    return " ".join(fold(text).split())


# ------------------------------------------------------------------------------------------------ the November lists

def within(cs, lo, hi):
    """The text of the cells that start between two column edges; nothing outside them is joined."""
    return join([r for x, rs in cs if lo <= x < hi for r in rs])


def pdf_columns(cs):
    """Column edges from a table's heading row (a row of headings, so joining it reads no one's details): the name and
    party columns, where the contact columns begin, and a district or office column left of the name if there is one."""
    texts = [(x, join(rs).strip().lower().rstrip(":")) for x, rs in cs]
    name = [x for x, t in texts if t in HEAD_NAME]
    party = [x for x, t in texts if t in HEAD_PARTY]
    if len(name) != 1 or len(party) != 1 or party[0] <= name[0]:
        return None
    later = [x for x, _t in texts if x > party[0] + 1]
    between = [x for x, _t in texts if name[0] + 1 < x < party[0]]         # a column between the name and the party is never read
    left = sorted([(x - 8, "district") for x, t in texts if t in HEAD_DISTRICT and x < name[0]][:1]
                  + [(x - 8, "office") for x, t in texts if t in HEAD_OFFICE and x < name[0]][:1])
    cols = {"name": name[0] - 8, "name_end": (min(between) if between else party[0]) - 8, "party": party[0] - 8,
            "end": (min(later) if later else 10 ** 6) - 8}
    for j, (x, what) in enumerate(left):
        cols[what] = (x, left[j + 1][0] if j + 1 < len(left) else cols["name"])
    return cols


def pdf_list(path):
    """{"title", "printed", "rows": [(kind, district, special, name, party)], "empty": [(kind, district, special)]} from
    one of the Division's candidate-list PDFs. Only the office, district, name and party cells are turned into text."""
    base = os.path.basename(path)
    pdf = PDF(open(path, "rb").read())
    head, cols, kind, district, special, first_title = [], None, None, None, 0, None
    got, empty = [], []

    def stop(why):
        raise SystemExit(f"Tennessee: {base}: {why}; read the list again (no row is shown here)")

    for page, res in pdf.pages():
        for _y, runs in pdf_rows(pdf, page, res):
            cs = cells(runs)
            if cols is None:                                   # above the first table: the title, the date, a note
                c = pdf_columns(cs) if len(cs) > 1 else None
                if c:
                    if kind is None:
                        raise NotTheList("no title naming Governor, the Tennessee Senate or the House of Representatives above its first table")
                    if GENERAL_TEXT not in " ".join(head):
                        raise NotTheList(f"its heading does not say {GENERAL_TEXT} (a list from before the primary?)")
                    cols = c
                    continue
                if len(head) >= 15:
                    raise NotTheList("no table headed Name (or Candidate) and Party near the top of the first page")
                if len(cs) > 2:                                # a row of a table with no heading row: counted, never joined
                    head.append("")
                    continue
                text = join(runs)
                head.append(text)
                t = head_kind(text)
                if t == "federal":
                    raise NotTheList("a list of federal candidates (the federal loader's)")
                if t == "other":
                    raise NotTheList(f"a list for an office this loader does not read ({TITLE_LINE.match(text).group('o')[:60]})")
                if t and kind is not None and t != kind:
                    raise NotTheList("two different offices named above its first table")
                if t:
                    kind, first_title = t, first_title or text
                    continue
                m = DISTRICT_LINE.match(text)
                if m and len(text) < 45 and (not m.group("rest").strip() or SPECIAL.match(m.group("rest"))):
                    district, special = int(m.group("d")), int(bool(m.group("rest").strip()))
                continue
            name = within(cs, cols["name"], cols["name_end"])
            party = within(cs, cols["party"], cols["end"])
            if name.lower() in HEAD_NAME and party.lower() in HEAD_PARTY:   # a table's heading row again
                cols = pdf_columns(cs) or cols
                continue
            if len(cs) == 1 and cs[0][0] < cols["end"]:          # one piece left of the contact columns: a title, a district, a note
                text = join(cs[0][1])
                t = title_kind(text)
                if t:                                           # a combined list's next office; a federal one is skipped
                    kind, district, special = (t if t in KINDS else None), None, 0
                    continue
                if kind is None:
                    continue
                m = DISTRICT_LINE.match(text)
                if m and len(text) < 45 and (not m.group("rest").strip() or SPECIAL.match(m.group("rest"))):
                    district, special = int(m.group("d")), int(bool(m.group("rest").strip()))
                    continue
                if NONE_ROW.match(text) or NONE_ROW.match(name):
                    empty.append((kind, district, special))
                    continue
                if cs[0][0] < cols["name"] or LIST_FURNITURE.search(text) or len(text) > 45 or text.endswith("."):
                    continue
                stop("a line of one piece that is not a name with a party, a district or a heading")
            if "office" in cols:
                cell = within(cs, *cols["office"])
                if cell:
                    try:
                        o = office_parts(cell)
                    except Unknown:
                        stop("an Office cell this loader does not know")
                    if o is None:
                        kind = None                             # a federal or party office: not this loader's
                    else:
                        kind, district, special = o[0], (o[1] if o[1] is not None else district), o[2]
            if kind is None:
                continue
            if "district" in cols:
                cell = within(cs, *cols["district"])
                if cell:
                    try:
                        district, special = district_number(cell), int(bool(SPECIAL.search(cell)))
                    except Unknown:
                        stop("a District cell that is not a district number")
            elif "office" not in cols:
                lead = within(cs, -10 ** 6, cols["name"])          # a district printed beside the first candidate
                m = DISTRICT_LINE.match(lead) if lead else None
                if m and (not m.group("rest").strip() or SPECIAL.match(m.group("rest"))):
                    district, special = int(m.group("d")), int(bool(m.group("rest").strip()))
            if name and party:
                if kind != "governor" and district is None:
                    stop("a candidate row before any district heading")
                got.append((kind, None if kind == "governor" else district, special, name, party))
            elif name and NONE_ROW.match(name):
                empty.append((kind, district, special))
            elif name or party:
                stop("a row with a name or a party but not both")
    if cols is None:
        raise NotTheList("no table headed Name (or Candidate) and Party")
    for k, d, *_rest in got + empty:
        top = SENATE_SEATS if k == "state_senate" else HOUSE_SEATS
        if k != "governor" and (d is None or not 1 <= int(d) <= top):
            stop(f"a {KIND_WORDS[k]} row with no district, or one outside 1 to {top}")
    m = re.search(rf"as of ({DATE})", " ".join(head))
    return {"title": first_title, "printed": m.group(1) if m else "", "rows": got, "empty": empty}


def xlsx_list(path):
    """The same from a candidate-list workbook: only the Office, District, Name, Party and Status columns (by heading)
    are read; every other column is never touched."""
    import openpyxl
    base = os.path.basename(path)
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    got, empty, found, titles, dropped = [], [], False, [], 0
    for ws in wb.worksheets:
        it = ws.iter_rows(values_only=True)
        idx, above = None, []
        for k, r in enumerate(it):
            heads = [str(c).strip().lower().rstrip(":") if c is not None else "" for c in r]
            at = lambda words: [j for j, h in enumerate(heads) if h in words]
            name, party, office, dist = at(HEAD_NAME), at(HEAD_PARTY), at(HEAD_OFFICE), at(HEAD_DISTRICT)
            if len(name) == 1 and len(party) == 1 and (office or dist):
                idx = {"name": name[0], "party": party[0], "office": office[0] if office else None, "district": dist[0] if dist else None,
                       "status": (at(HEAD_STATUS) or [None])[0]}
                break
            filled = [c for c in r if c is not None and str(c).strip()]
            if len(filled) == 1:                               # a title row above the headings
                above.append(str(filled[0]).strip())
            if k > 10:
                break
        if not idx:
            continue
        dated = (GENERAL_TEXT in " ".join(above) or re.search(r"\bnov", ws.title, re.I)
                 or re.search(r"nov\w*[ _.-]*2026|2026[ _.-]*nov", base, re.I))
        if not dated:
            raise NotTheList("a workbook that does not say it is the November 3, 2026 list (in a title row, its sheet name or its file name)")
        default = next((t for t in (title_kind(a) for a in above) if t), None)
        if default in ("federal", "other"):
            raise NotTheList("a workbook of another office's list")
        found = True
        titles += [a for a in above if title_kind(a)]
        cell = lambda r, what: (str(r[idx[what]]).strip() if idx[what] is not None and len(r) > idx[what] and r[idx[what]] is not None else "")
        for r in it:
            office, dcell, name, party = cell(r, "office"), cell(r, "district"), cell(r, "name"), cell(r, "party")
            if not (office or name):
                continue
            try:
                if office:
                    o = office_parts(office, dcell or None)
                elif default in KINDS:
                    o = (default, district_number(dcell) if dcell else None, int(bool(SPECIAL.search(dcell))))
                else:
                    raise Unknown("")
            except Unknown:
                raise SystemExit(f"Tennessee: {base}: an Office or District cell this loader does not know"
                                 + (f" ({office[:60]})" if office and not CONTACT.search(office) else "") + "; read the workbook again")
            if o is None:
                continue                                        # a federal or party office: the federal loader's, or nobody's
            k, d, sp = o
            if k != "governor" and d is None:
                raise SystemExit(f"Tennessee: {base}: a {KIND_WORDS[k]} row with no district; read the workbook again")
            if idx["status"] is not None and OFF_BALLOT.search(cell(r, "status")):
                dropped += 1
                continue
            if name and NONE_ROW.match(name):
                empty.append((k, d, sp))
            elif name and party:
                got.append((k, d, sp, name, party))
            elif name or party:
                raise SystemExit(f"Tennessee: {base}: a row with a name or a party but not both; read the workbook again")
    wb.close()
    if not found:
        raise NotTheList("no sheet with Office (or District), Name and Party headings")
    return {"title": titles[0] if titles else "", "printed": "", "rows": got, "empty": empty, "dropped": dropped}


def find_lists(folder):
    """({path: (kind of file, parsed)}, [(file, why not read)]) for every state November list in the folder."""
    found, skipped = {}, []
    for path in sorted(glob.glob(os.path.join(folder, "*"))):
        base = os.path.basename(path)
        if base in RESULTS.values() or not base.lower().endswith((".pdf", ".xlsx")):
            continue
        magic = open(path, "rb").read(5)
        try:
            if base.lower().endswith(".pdf"):
                if magic != b"%PDF-":
                    raise NotTheList("not a PDF (a saved error page?)")
                found[path] = ("pdf", pdf_list(path))
            else:
                if magic[:2] != b"PK":
                    raise NotTheList("not a workbook (a saved error page?)")
                found[path] = ("xlsx", xlsx_list(path))
        except NotTheList as e:
            skipped.append((base, str(e)))
    return found, skipped


# ------------------------------------------------------------------------------------------------- the primary results

def primary_sections(path, party):
    """(date issued, [section]) for every section of one party's results by county: {"office", "names": [(number, name)],
    "counties": {county: [votes]}, "totals": [votes]}. Each section's county rows must add up to its TOTALS row. The
    reading is the federal loader's, which also follows a title printed on two lines onto a later page."""
    base = os.path.basename(path)
    L = lines(path)
    words = {t for _p, _y, t in L[:6]}
    if f"{party} Primary" not in words or PRIMARY_TEXT not in words or "State of Tennessee" not in words:
        raise SystemExit(f"Tennessee: {base} is not the {PRIMARY_TEXT} {party} Primary results by county")
    issued, state, cur, sections, page, partial = "", "head", None, [], None, ""
    for p, _y, t in L:
        if p != page:
            page, state, partial = p, "head", ""
        m = FOOTER.match(t)
        if m:
            issued = issued or m.group(1)
            continue
        if FURNITURE.match(t):
            continue
        if state == "head":
            if cur and not cur.get("done"):
                title = f"{partial} {t}".strip()
                if title == cur["office"]:
                    state, cur["again"], partial = "cands", [], ""      # the section carried over: its candidates are printed again
                elif cur["office"].startswith(title + " "):
                    partial = title                                     # a two-line title, printed again
                else:
                    raise SystemExit(f"Tennessee: {base}: {cur['office']} has no TOTALS row")
                continue
            cur = {"office": t, "names": [], "counties": {}, "totals": None}
            sections.append(cur)
            state = "cands"
            continue
        if state == "cands":
            m = CANDIDATE.match(t)
            if not m and not cur["names"] and "again" not in cur and (
                    re.match(r"^District \d{1,2}\b", t) or not (COLUMNS.match(t) or TOTALS.match(t) or COUNTY.match(t))):
                cur["office"] += " " + t                                # a title printed on two lines ("District 3" is not a county)
                continue
            if m:
                target = cur["again"] if "again" in cur else cur["names"]
                num = int(m.group(1))
                if target and num <= target[-1][0]:
                    raise SystemExit(f"Tennessee: {base}: the candidates under {cur['office']} are not numbered in order")
                target.append((num, re.sub(r"\s+", " ", m.group(2)).strip()))
                continue
            if "again" in cur and cur.pop("again") != cur["names"]:
                raise SystemExit(f"Tennessee: {base}: {cur['office']} lists different candidates on a later page")
            state = "counties"
            if COLUMNS.match(t):
                if not {int(x) for x in t.split()} <= {num for num, _n in cur["names"]}:
                    raise SystemExit(f"Tennessee: {base}: the column numbers under {cur['office']} do not match its candidates")
                continue
        m = TOTALS.match(t)
        if m and state == "counties":
            cur["totals"] = [int(x.replace(",", "")) for x in m.group(2).split()]
            cur["done"], state = True, "head"
            continue
        m = COUNTY.match(t)
        if m and state == "counties":
            nums = [int(x.replace(",", "")) for x in m.group(2).split()]
            if len(nums) != len(cur["names"]) or m.group(1) in cur["counties"]:
                raise SystemExit(f"Tennessee: {base}: a county row under {cur['office']} does not fit its candidates")
            cur["counties"][m.group(1)] = nums
            continue
        raise SystemExit(f"Tennessee: {base}: a line under {cur['office'] if cur else 'the first page'} was not understood; read the file again")
    if cur and not cur.get("done"):
        raise SystemExit(f"Tennessee: {base}: {cur['office']} has no TOTALS row")
    for s in sections:
        n = len(s["names"])
        if len(s["totals"]) != n:
            raise SystemExit(f"Tennessee: {base}: the TOTALS row of {s['office']} does not fit its candidates")
        summed = [sum(v[k] for v in s["counties"].values()) for k in range(n)]
        if summed != s["totals"]:
            raise SystemExit(f"Tennessee: {base}: the counties of {s['office']} add up to {summed}, its TOTALS row says {s['totals']}")
    return issued, sections


# ------------------------------------------------------------------------------------------------------- the roster

def roster(path):
    """Sitting legislators and the Governor: ids, names, party, chamber and district only (the roster's contact columns
    are never selected)."""
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    legs = [dict(zip(("id", "first", "last", "full", "other", "party", "chamber", "district"), r)) for r in con.execute(
        "SELECT bioguide_id, first_name, last_name, official_full, other_names, party_name, chamber, district FROM legislators "
        "WHERE is_current = 1")]
    offs = {r[1]: dict(zip(("id", "office", "full", "first", "last", "party"), r)) for r in con.execute(
        "SELECT bioguide_id, office, official_full, first_name, last_name, party_name FROM officials")}
    con.close()
    return legs, offs


def person_fits(name, p):
    """A listed name fits a roster person: the same family name and a given name that fits (the roster's own, or a full
    form of it the roster keeps among other names)."""
    cand = name_parts(name)
    forms = [(fold(p["first"] or "").split(), key(p["last"] or ""))]
    forms += [name_parts(o.strip()) for o in (p.get("other") or "").split(";") if o.strip() and "," not in o and "." not in o]
    return any(f[1] and fits(cand, f) for f in forms)


def chamber_words(p):
    return f"Tennessee {'Senate' if p['chamber'] == 'Senate' else 'House'}, District {int(p['district'])}"


# ----------------------------------------------------------------------------------------------------------- helpers

def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def mtime(path):
    return dt.datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d")


def census_counties(path):
    """{folded county name: (GEOID, name)} for Tennessee from the Census Bureau's county file."""
    import shapefile                                                     # pyshp, in the kit's environment
    z = zipfile.ZipFile(path)
    dbf = next(n for n in z.namelist() if n.endswith(".dbf"))
    rdr = shapefile.Reader(dbf=io.BytesIO(z.read(dbf)))
    return {key(r["NAME"]): (r["GEOID"], r["NAME"]) for r in (x.as_dict() for x in rdr.iterRecords()) if r["STATEFP"] == FIPS}


def list_source_id(path):
    return "tn-sos-2026-sl-list-" + re.sub(r"[^a-z0-9]+", "-", os.path.basename(path).lower()).strip("-")


# ----------------------------------------------------------------------------------------------------------- loading

def load(db_path, say=print, folder=FOLDER, roster_db=ROSTER, county_zip=COUNTY_ZIP):
    os.makedirs(folder, exist_ok=True)
    legs, offs = roster(roster_db)
    counties = census_counties(county_zip)
    if len(counties) != TOTAL_COUNTIES:
        raise SystemExit(f"Tennessee: the Census county file has {len(counties)} Tennessee counties, not {TOTAL_COUNTIES}")
    checks, matched = [], []

    # 1. the seats on the ballot, each with who holds it today
    races = {}

    def holder_of(kind, district):
        if kind == "governor":
            return offs.get("governor")
        chamber = "Senate" if kind == "state_senate" else "House"
        hs = [p for p in legs if p["chamber"] == chamber and str(p["district"]).strip() == str(district)]
        return hs[0] if len(hs) == 1 else None

    def add_race(kind, district, special=0, why=None):
        rid = race_id(kind, district)
        if rid in races:
            return rid
        h = holder_of(kind, district)
        note = [GOV_NOTE] if kind == "governor" else ([SENATE_NOTE] if kind == "state_senate" else [])
        if special:
            note.append(why)
        if h is None:
            checks.append(f"{rid}: no sitting member in the roster for this seat")
            note.append("The roster shows no one holding this seat today.")
        if kind == "governor":
            office, jur, jur_id = "Governor", "Tennessee", FIPS
        else:
            office = "State Senator" if kind == "state_senate" else "State Representative"
            jur, jur_id = f"{'Senate' if kind == 'state_senate' else 'House'} District {district}", str(district)
        races[rid] = {"race_id": rid, "state": STATE, "level": "statewide" if kind == "governor" else "legislature", "office_kind": kind,
                      "office": office, "jurisdiction": jur, "jurisdiction_id": jur_id, "county_ids": None,
                      "district": None if kind == "governor" else str(district), "seat": None, "special": int(bool(special)), "partisan": 1,
                      "holder_id": h["id"] if h else None, "holder_name": h["full"] if h else None, "holder_party": h["party"] if h else None,
                      "election_date": GENERAL, "note": note, "_holder": h, "_kind": kind}
        return rid

    add_race("governor", None)
    for d in SENATE_UP:
        add_race("state_senate", d)
    for d in range(1, HOUSE_SEATS + 1):
        add_race("state_house", d)

    def seat_of(kind, district, special, what):
        """The race a list or results row belongs to, adding a Senate seat for the rest of a term when one is named."""
        rid = race_id(kind, district)
        if rid in races:
            if special and not races[rid]["special"]:
                checks.append(f"{rid}: the {what} names this seat as an unexpired term, but its full term is on the 2026 ballot anyway")
            return rid
        if kind == "state_senate":
            if not special:
                checks.append(f"{rid}: on the {what} but not due until 2028, and not marked as an unexpired term; shown as a special election")
            return add_race(kind, district, 1, (SPECIAL_NOTE if special else SPECIAL_GUESS).format(what=what))
        raise SystemExit(f"Tennessee: the {what} names {rid}, which is not on the 2026 ballot")

    def identify(rid, name, party):
        """(incumbent, state_member_id, note) for one name in a race."""
        h = races[rid]["_holder"]
        if h is not None and person_fits(name, h):
            return 1, h["id"], None
        pool = [p for p in legs if person_fits(name, p) and (p["party"] or "") == (party or "")]
        if len(pool) == 1 and not (h is not None and pool[0]["id"] == h["id"]):
            return 0, pool[0]["id"], f"Serves today in the {chamber_words(pool[0])}."
        return 0, None, None

    # 2. the November lists
    lists, skipped = find_lists(folder)
    listed = [(path, row) for path, (_k, got) in lists.items() for row in got["rows"]]
    kinds_listed = {row[0] for _p, row in listed} | {e[0] for _p, (_k, got) in lists.items() for e in got["empty"]}
    by_race = {}
    for path, (k, d, sp, name, party) in listed:
        rid = seat_of(k, d, sp, "November list")
        by_race.setdefault(rid, {}).setdefault(path, []).append((name, party))
    empty_on_list = set()
    for path, (_k, got) in lists.items():
        for k, d, sp in got["empty"]:
            empty_on_list.add(seat_of(k, d, sp, "November list"))
    def rank(path):
        """Which copy of a list is used: a workbook first (its cells hold the whole name), then the one printed latest."""
        return lists[path][0] != "xlsx", -int(iso(lists[path][1]["printed"]).replace("-", "") or 0), path

    general, differ = [], []
    for rid in sorted(by_race):
        copies = sorted(by_race[rid].items(), key=lambda kv: rank(kv[0]))
        first = copies[0][1]
        for path, other in copies[1:]:
            if [(key(n), party_of(p)) for n, p in other] != [(key(n), party_of(p)) for n, p in first]:
                differ.append(f"{rid} ({os.path.basename(copies[0][0])} used, {os.path.basename(path)} differs)")
        for raw, party in first:
            name, note = shown(raw, CAPS)
            general.append({"race_id": rid, "name": name, "party": party_of(party), "note": note, "path": copies[0][0]})
    twice = sorted({(g["race_id"], g["party"]) for g in general if g["party"] in CODE
                    and sum(1 for x in general if (x["race_id"], x["party"]) == (g["race_id"], g["party"])) > 1})
    if twice:
        raise SystemExit(f"Tennessee: more than one nominee of one party for one seat on the November list: {twice}")
    nominee = {(g["race_id"], g["party"]): g["name"] for g in general}

    cands = []
    for g in general:
        inc, mid, n2 = identify(g["race_id"], g["name"], g["party"])
        cands.append([g["race_id"], "general", GENERAL, g["name"], g["party"], party_code(g["party"]), None, inc, 0, None, None, None, mid,
                      list_source_id(g["path"]), " ".join(x for x in (g["note"], n2) if x) or None])

    # 3. the August 6 primaries: official votes, each section reconciled
    fields, read, issued, race_counties, unknown = 0, {}, {}, {}, []
    for party, base in RESULTS.items():
        path = os.path.join(folder, base)
        if not os.path.exists(path):
            continue
        if open(path, "rb").read(5) != b"%PDF-":
            raise SystemExit(f"Tennessee: {base} is not a PDF (a saved error page?)")
        issued[party], sections = primary_sections(path, party)
        code, mine = CODE[party], {}
        for s in sections:
            try:
                o = office_parts(s["office"])
            except Unknown:
                unknown.append(f"{base}: {s['office']}")
                continue
            if o is None:
                continue
            k, d, sp = o
            if k != "governor" and d is None:
                unknown.append(f"{base}: {s['office']}")
                continue
            if k == "governor" and len(s["counties"]) != TOTAL_COUNTIES:
                raise SystemExit(f"Tennessee: {base}: the Governor's section has {len(s['counties'])} counties, not {TOTAL_COUNTIES}")
            rid = seat_of(k, d, sp, f"{party} primary results")
            if rid in mine:
                raise SystemExit(f"Tennessee: {base}: {s['office']} appears twice")
            mine[rid] = s
            for c in s["counties"]:
                if key(c) not in counties:
                    raise SystemExit(f"Tennessee: {base}: a county row named {c!r} is not a Tennessee county in the Census file")
                race_counties.setdefault(rid, {}).setdefault(counties[key(c)][0], f"tn-sos-2026-sl-primary-{code.lower()}")
        read[party] = mine
        for rid, s in sorted(mine.items()):
            names = []
            for (_num, raw), votes in zip(s["names"], s["totals"]):
                if raw.strip().lower() == "no candidate qualified":
                    continue
                w = WRITE_IN.match(raw)
                names.append((w.group(1).strip() if w else raw, votes, bool(w)))
            printed = [c for c in names if not c[2]]
            total = sum(v for _n, v, _w in names)
            nom = nominee.get((rid, party))
            k = pick(nom, [n for n, _v, _w in names])
            top = max(range(len(names)), key=lambda j: names[j][1]) if names else None
            tie = names and sum(1 for _n, v, _w in names if v == names[top][1]) > 1
            if nom and k is None:
                checks.append(f"{rid} {party}: the November nominee ({nom}) is not among the primary's candidates")
            elif nom and names and names[k][1] != names[top][1]:
                checks.append(f"{rid} {party}: the November nominee ({nom}) is not the primary's top vote-getter")
            if races[rid]["_kind"] in kinds_listed and not nom and printed:
                checks.append(f"{rid} {party}: the primary had a winner but the November list has no {party} candidate")
            if not nom and names:
                k = None if tie else top
                if tie:
                    checks.append(f"{rid} {party}: a tie at the top of the primary and no November nominee to settle it; outcome left blank")
            if len(printed) < 2:
                continue
            fields += 1
            for j in sorted(range(len(names)), key=lambda j: -names[j][1]):
                raw, votes, write_in = names[j]
                won = k is not None and j == k
                if write_in and not won:
                    continue                                        # counted in the total, not listed
                name, note = shown(raw, CAPS_RESULTS)
                if won and not nom and races[rid]["_kind"] in kinds_listed:
                    note = " ".join(x for x in (note, NOT_ON_LIST) if x)
                if write_in:
                    note = " ".join(x for x in (note, WRITE_IN_WON) if x)
                inc, mid, n2 = identify(rid, name, party)
                cands.append([rid, f"primary-{code}", PRIMARY, name, party, party_code(party), None, inc, int(write_in), votes,
                              round(100 * votes / total, 1) if total else None, None if k is None else ("advanced" if won else "lost"), mid,
                              f"tn-sos-2026-sl-primary-{code.lower()}", " ".join(x for x in (note, n2) if x) or None])

    # 4. per race: its counties, and what its note says about the list
    for rid, r in races.items():
        if r["_kind"] == "governor":
            r["county_ids"] = json.dumps(sorted(g for g, _n in counties.values()))
        elif rid in race_counties:
            r["county_ids"] = json.dumps(sorted(race_counties[rid]))
        on_list = any(c[0] == rid and c[1] == "general" for c in cands)
        if r["_kind"] not in kinds_listed:
            r["note"].append(NO_LIST)
        elif rid in empty_on_list and not on_list:
            r["note"].append(NONE_QUALIFIED)
        elif not on_list:
            r["note"].append(NONE_ON_LIST)
            checks.append(f"{rid}: no candidates on the November list")
    for party in read:
        gone = [rid.split(f"-{STATE}-")[1] for rid, r in races.items() if rid not in read[party] and not r["special"]]
        if gone:
            checks.append(f"no section in the {party} primary results for {len(gone)} seats on the ballot: {', '.join(gone)}")
    # one sitting member to a race, never two
    for rid in races:
        inc = [c for c in cands if c[0] == rid and c[1] == "general" and c[7]]
        if len(inc) > 1:
            for c in inc:
                c[7], c[12] = 0, None
            checks.append(f"{rid}: more than one name on the list fits the sitting member; none is marked")

    # 5. the last look at every stored text: nothing that looks like a contact detail reaches the database
    for c in cands:
        if CONTACT.search(c[3]) or CONTACT.search(c[4] or "") or (c[14] and re.search(r"@|www\.|https?:", c[14])):
            raise SystemExit(f"Tennessee: a stored cell for {c[0]} failed the contact-detail check (not shown); read the file again")
    keys = [(c[0], c[1], c[3]) for c in cands]
    if len(keys) != len(set(keys)):
        raise SystemExit("Tennessee: two candidate rows share race, election and name")
    # the November rows stored are exactly the rows of the lists used, list by list
    used_rows = sum(len(by_race[rid][min(by_race[rid], key=rank)]) for rid in by_race)
    if used_rows != sum(1 for c in cands if c[1] == "general"):
        raise SystemExit("Tennessee: the November rows stored do not match the rows of the lists read")

    # 6. write Tennessee's rows only, in one transaction
    race_rows = [tuple(" ".join(r["note"]) or None if k == "note" else r[k] for k in (
        "race_id", "state", "level", "office_kind", "office", "jurisdiction", "jurisdiction_id", "county_ids", "district", "seat", "special",
        "partisan", "holder_id", "holder_name", "holder_party", "election_date", "note")) for r in races.values()]
    place_rows = [("county", g, f"{n} County", json.dumps([g]), SRC_COUNTY) for g, n in sorted(counties.values())]
    for rid, r in sorted(races.items()):
        if r["_kind"] == "governor":
            continue
        srcs = sorted(set(race_counties.get(rid, {}).values()))
        place_rows.append(("senate" if r["_kind"] == "state_senate" else "house", f"TN-{r['district']}", r["jurisdiction"], r["county_ids"],
                           srcs[0] if srcs else SRC_ROSTER))
    gen = [c for c in cands if c[1] == "general"]
    prim = [c for c in cands if c[1] != "general"]
    sources = [
        (SRC_ROSTER, STATE, "member roster", "Open States people project (CC0), as loaded into state_tn.sqlite",
         "Sitting Tennessee legislators and the Governor", "https://github.com/openstates/people", "", mtime(roster_db), sha(roster_db),
         len(legs) + len(offs), "Who holds each seat today, and which candidate is a sitting member (same chamber and district, the name "
         "fits, one fit only; a member of another seat only when the name fits exactly one sitting legislator of the same party). "
         "Names, party and ids only."),
        (SRC_COUNTY, STATE, "county codes", "U.S. Census Bureau", "Cartographic boundary file, counties, 2024 (1:500,000)", COUNTY_URL,
         "2024", mtime(county_zip), sha(county_zip), len(counties),
         "Five-digit county codes (GEOID) for Tennessee's 95 counties, matched by name to the primary results' county rows. The counties "
         "a district reaches are those its primary sections list (derived)."),
    ]
    for path, (kind, got) in lists.items():
        base = os.path.basename(path)
        used = sum(1 for g in general if g["path"] == path)
        state_rows = len(got["rows"])
        sources.append((
            list_source_id(path), STATE, "official candidate list", AGENCY,
            (got["title"] or "Candidates for " + " and ".join(KIND_WORDS[k] for k in KINDS if k in {r[0] for r in got["rows"]}))
            + f", {GENERAL_TEXT} General Election (file {base})", LIST_PAGE, iso(got["printed"]), mtime(path), sha(path), state_rows,
            f"The Secretary of State's sites refuse scripts; the file ({base}) was saved from a browser. "
            + ("Name and party cells only (and the office or district); address, city, ZIP and every column after the party are never read. "
               if kind == "pdf" else "Office, District, Name and Party columns only (and Status where present); every other "
               "column is never read. ")
            + "The list prints no ballot order, so none is stored. It leaves out anyone who withdrew or did not qualify"
            + (f" (a Status column marked {got['dropped']} more as off the ballot, left off)" if got.get("dropped") else "")
            + f". State rows read: {state_rows}; used: {used}"
            + ("" if used == state_rows else " (the rest are another copy of the same list, checked against the one used)") + "."))
    for party, mine in read.items():
        code, base = CODE[party], RESULTS[party]
        path = os.path.join(folder, base)
        n = sum(1 for c in prim if c[1] == f"primary-{code}")
        sources.append((
            f"tn-sos-2026-sl-primary-{code.lower()}", STATE, "official results", AGENCY,
            f"August 6, 2026 {party} Primary, State of Tennessee: results by county" + (f" (issued {issued[party]})" if issued[party] else "")
            + " - Governor, Tennessee Senate and Tennessee House of Representatives sections", FILES + base, iso(issued[party]), mtime(path),
            sha(path), n,
            f"Linked from {RESULTS_PAGE}; saved from a browser (the Secretary's sites refuse scripts). {len(mine)} state sections read; every "
            "section's county rows add up to its TOTALS row, and the Governor's has all 95 counties. Votes from the TOTALS row; a share is of "
            "the printed and the certified write-in candidates' votes; a certified write-in candidate is listed only if one won. A field is "
            "two or more printed candidates; the November list's nominee advanced, or, before the list is loaded, the top vote-getter "
            "(Tennessee nominates by plurality)."))
    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA)
    with con:
        con.execute("DELETE FROM sl_candidates WHERE race_id IN (SELECT race_id FROM sl_races WHERE state = ?) OR race_id LIKE ?",
                    (STATE, f"2026-{STATE}-%"))
        con.execute("DELETE FROM sl_races WHERE state = ?", (STATE,))
        con.execute("DELETE FROM sl_sources WHERE state = ?", (STATE,))
        con.execute("DELETE FROM sl_places WHERE source_id LIKE ?", (f"{STATE.lower()}-%",))
        con.executemany("INSERT INTO sl_races VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", race_rows)
        con.executemany("INSERT INTO sl_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", cands)
        con.executemany("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", sources)
        con.executemany("INSERT INTO sl_places VALUES (?,?,?,?,?)", place_rows)
    con.close()

    # 7. say what happened, and what is still waiting
    per = lambda kind, rows: sum(1 for c in rows if races[c[0]]["_kind"] == kind)
    n_ss = sum(1 for r in races.values() if r["_kind"] == "state_senate")
    specials = sorted(rid for rid, r in races.items() if r["special"])
    say(f"    Tennessee state offices: {len(races)} races (Governor, {n_ss} Senate{' incl. ' + ', '.join(specials) if specials else ''}, "
        f"{HOUSE_SEATS} House); {len(gen)} candidates on the November lists (Governor {per('governor', gen)}, Senate "
        f"{per('state_senate', gen)}, House {per('state_house', gen)}; {sum(1 for c in gen if c[7])} sitting members); {fields} primary "
        f"fields, {len(prim)} primary rows (Governor {per('governor', prim)}, Senate {per('state_senate', prim)}, House {per('state_house', prim)})")
    waiting = [KIND_WORDS[k] for k in KINDS if k not in kinds_listed]
    if waiting:
        say(f"      waiting: the November 3, 2026 candidate lists for {', '.join(waiting)} (from {LIST_PAGE}; sos.tn.gov answers scripts "
            f"with 403, so save them from a browser into {folder}, as PDF or workbook, any file name)")
    for party, base in RESULTS.items():
        if party not in read:
            say(f"      waiting: {base} (from {RESULTS_PAGE}: {FILES}{base}), saved from a browser into {folder}")
    for path, (kind, got) in sorted(lists.items()):
        n = {k: sum(1 for r in got["rows"] if r[0] == k) for k in KINDS}
        say(f"      list read: {os.path.basename(path)} ({kind}{', as of ' + got['printed'] if got['printed'] else ''}): {len(got['rows'])} "
            f"state rows (Governor {n['governor']}, Senate {n['state_senate']}, House {n['state_house']})"
            + (f", {len(got['empty'])} seats printed with no candidate" if got["empty"] else "")
            + (f", {got['dropped']} marked off the ballot" if got.get("dropped") else ""))
    for party, mine in read.items():
        say(f"      results read: {RESULTS[party]} (issued {issued[party] or 'date not printed'}): {len(mine)} state sections reconciled "
            f"to their TOTALS rows")
    for base, why in skipped:
        say(f"      not read as a state November list: {base} ({why})")
    for line in unknown:
        say(f"      check: a results section this loader does not know, left out: {line}")
    if differ:
        say("      check: the PDF and the workbook of one list disagree for " + "; ".join(differ))
    for c in cands:
        if c[12]:
            matched.append(f"{c[0]} {c[1]}: {c[3]} -> {c[12]}{' (holds this seat)' if c[7] else ''}")
    for line in matched:
        say(f"      matched: {line}")
    for line in checks:
        say(f"      check: {line}")
    return len(gen)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m ballot.state_local_tn <database>")
    load(sys.argv[1])
