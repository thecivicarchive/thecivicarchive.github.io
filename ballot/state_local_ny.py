"""
New York: the state offices on the November 3, 2026 ballot, from the same two files of the State Board of Elections that
the federal loader reads (ballot/lists/ny.py), into the state-and-local ballot database (ballot_local_2026.sqlite). The
federal ballot database (ballot_2026.sqlite) is never opened here, and Representative in Congress is left to the
federal pages.

    python ballot/state_local_ny.py --db test.sqlite            builds New York's rows in the database named
    python ballot/state_local_ny.py --db test.sqlite --no-fetch  uses the cached files as they are

What is read, and what never is
-------------------------------
The Board's Certification for the November 3, 2026 General Election (the amended accessible PDF, dated September 17,
2026; cached as ballot_cache/ny_2026_general_ballot_certification.pdf), read with ballot/pdftext.py. Each office is a
table: "Office:", "District:", "Counties:" (a long list wraps onto lines of its own until "Vote For:"), "Vote For:", a
heading row ("Party", "Candidate Name"; the Governor's table has two name columns, Governor and Lt. Governor), then one
block per party line: the party on the left, the candidate's given names printed above the party's row and the family
name below it (a long party name wraps onto the family-name row). A line with no candidate is left blank. The file
carries offices, districts, counties, party lines and names only; no addresses, telephones, websites or e-mail are
printed in it, and nothing but those cells is read.

Read here: Governor and Lieutenant Governor (one vote for the pair in November, stored as the ticket, governor first),
Comptroller, Attorney General, every State Senate seat (all 63: two-year terms, all elected in 2026), every Assembly seat
(all 150, likewise), and Justice of the Supreme Court in the judicial districts that have seats on the list (in New
York the Supreme Court is the trial court of general jurisdiction, elected by judicial district; it is stored with
level "court" and office_kind "trial_court", a kind named here, so that it is never mistaken for a state's highest
court). The Secretary of State, Treasurer and Auditor are not elected in New York, so no such race exists.

New York lets several parties nominate one person (fusion): a candidate is stored once per race, with every line they
hold ("Democratic, Working Families"), in the order the lines appear on the list; ballot_order is the order of each
candidate's first line. Where several seats are filled at once (the Supreme Court), each party prints one row per seat.

The June 23, 2026 primaries: the Board's workbook of the primary's results (ballot_cache/ny/2026-june-primary-vote-
results-08312026.xlsx), one sheet per contest the primary held (New York prints a party primary only when it is
contested). Sheets for the Senate and the Assembly are laid out as the federal loader describes (a "Candidate Name
(Party)" heading row, one column per county or part of a county, "Total Votes by Party", "Total Votes by Candidate";
rows for each candidate, Blank, Void, Scattering and "Total Votes by County"); a statewide sheet (the Comptroller) is
turned the other way (a "County" heading row with one column per candidate, then Blank, Void, Scattering and "Total Votes
by County"; one row per county, then "Total Votes by Party" and "Total Votes by Candidate"). Every figure is checked
both ways; anything that does not add up is reported and named in the source's note. Congressional sheets are the
federal loader's; judicial delegates and state committee members are party positions, not offices, and are left alone.
A field is a party primary with two or more candidates on its ballot; shares are of the candidates' votes plus write-ins
(Scattering), blank and void ballots left out; the most votes advanced (New York nominates by plurality; no runoffs).
The workbook carries names and votes only.

Sitting members come from state_ny.sqlite (the Open States roster; only ids, names, other spellings of the name, party,
chamber and district are selected): the member for the same chamber and district whose name fits exactly one candidate
is marked incumbent. The roster carries the Governor, Lieutenant Governor and Attorney General, but no Comptroller and
no judges. County codes come from the Census Bureau's 2024 county file (five-digit FIPS), matched by name to the
certification's "Counties:" lines, which also give the counties each district reaches (sl_places).

Writes only New York's rows (state = 'NY'; places whose source ids begin ny-, and county ids 36xxx).
"""

import datetime as dt
import hashlib
import io
import json
import os
import re
import sqlite3
import zipfile
from collections import Counter, OrderedDict

import openpyxl

from ballot.common import HERE, fold, name_parts, party_code
from ballot.lists.ny import (CANDIDATE, OTHER_ROWS, PAGE as CERT_PAGE, PRIMARY_URL, RESULTS_PAGE, SAVED, TOTAL_ROW,
                             URL as CERT_URL, _clean, _num, _stamp, primary_workbook, same_person)
from ballot.match import PARTICLES, fits
from ballot.pdftext import PDF, join, rows

STATE, FIPS, NAME = "NY", "36", "New York"
GENERAL, PRIMARY = "2026-11-03", "2026-06-23"
CACHE = os.path.join(HERE, "ballot_cache")
CERT_FILE = "ny_2026_general_ballot_certification.pdf"
ROSTER = os.path.join(HERE, "state_ny.sqlite")
COUNTY_ZIP = os.path.join(HERE, "states_cache", "census", "cb_2024_us_county_500k.zip")
COUNTY_URL = "https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_county_500k.zip"
SRC_CERT, SRC_PRI = "ny-sboe-2026-general-cert", "ny-sboe-2026-primary-results"
SRC_ROSTER, SRC_COUNTY = "ny-openstates-roster", "ny-census-counties-2024"
AGENCY = "New York State Board of Elections"
SEATS = {"SS": 63, "SH": 150}
TOTAL_COUNTIES = 62

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

# the certification's office -> (race key, level, office_kind, office as shown, roster office)
OFFICES = {
    "Governor and Lt. Governor": ("GOV", "statewide", "governor", "Governor and Lieutenant Governor", "governor"),
    "Comptroller": ("COMP", "statewide", "comptroller", "Comptroller", None),
    "Attorney General": ("AG", "statewide", "attorney_general", "Attorney General", "attorney general"),
    "State Senator": ("SS", "legislature", "state_senate", "State Senator", None),
    "Member of Assembly": ("SH", "legislature", "state_house", "Member of Assembly", None),
    "Supreme Court Justice": ("SCJ", "court", "trial_court", "Justice of the Supreme Court", None),
}
FEDERAL = ("Representative in Congress", "United States Senator")
HEADER_WORDS = {"Party", "Governor Lt. Governor"}
FOOTER = re.compile(r"^Certification for the November 3, 2026 General Election - Page \d+ of \d+$")
BLOCK_GAP = 18.0          # points between one party line's block and the next (rows inside a block are 7.7 or 15.5 apart)

# the primary workbook
PARTIES = {"Democratic": "DEM", "Republican": "REP", "Conservative": "CON", "Working Families": "WOR"}
TITLE = re.compile(r"^(?P<head>.+?) - (?P<party>[A-Z][A-Za-z .'-]*?)(?: - | )Primary Election(?: -)? "
                   r"(?P<date>\d{1,2}/\d{1,2}/\d{4}|[A-Z][a-z]+ \d{1,2}, \d{4})$")
PRINTED = "June 23, 2026"
PARTY_POSITION = re.compile(r"\bJudicial Delegates\b|\bState Committee\b|\bDistrict Leader\b|\bCounty Committee\b")
COUNTY_ROW = re.compile(r"^[A-Z][A-Za-z. ]* County$")
WRITE_IN = re.compile(r"\s*-\s*Write[- ]?In$", re.I)      # "Joshua Blumenthal-Write In (CON)": a write-in the Board names with its votes
COUNTY_HEAD = re.compile(r"^(?:Part of )?[A-Z][A-Za-z. ]*? (?:County ?)?Vote Results$")      # 118th AD REP: "Part of Otsego Vote Results"

NOTES = {
    "GOV": "New York elects the Governor and Lieutenant Governor together in November, one vote for the pair; each ticket is "
           "written governor first.",
    "COMP": "The Open States roster this site uses does not carry the Comptroller, so today's holder is not shown.",
    "SS": "New York elects all 63 members of the State Senate every two years.",
    "SH": "New York elects all 150 members of the Assembly every two years.",
    "SCJ": "In New York the Supreme Court is the trial court of general jurisdiction, not the state's highest court (that is the "
           "Court of Appeals, whose judges are appointed); its justices are elected by judicial district, for fourteen-year terms, "
           "and each party names its candidates at a judicial district convention rather than in a primary. The roster this site "
           "uses does not carry judges, so today's holders are not shown.",
}
NO_HOLDER = "The roster shows no one holding this seat today."
NOT_ON_LIST = "Won the primary, but is not on the November ballot on this party's line."
NO_VOTES = "The Board's results workbook shows no votes in this primary; who advanced is taken from the November ballot."

# the last look at every stored text: nothing that looks like a contact detail reaches the database
CONTACT = re.compile(r"@|https?://|\bwww\.|\.(?:com|org|net|gov|us)\b|\(?\b\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}\b|\b\d{5}(?:-\d{4})?\b|"
                     r"\b\d{1,6}\s+\w+(?:\s\w+)?\s(?:St|Street|Ave|Avenue|Rd|Road|Blvd|Drive|Dr|Lane|Ln|Place|Pl|Way)\b", re.I)


def ordinal(n):
    n = int(n)
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def fetched(path):
    return dt.datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d")


def county_key(text):
    t = re.sub(r"\s+County$", "", str(text or "").strip(), flags=re.I).lower()
    return re.sub(r"[^a-z]", "", re.sub(r"^saint\b", "st", t))          # the certification writes St. Lawrence both ways


def census_counties(path):
    """{county key: (GEOID, name)} for New York from the Census Bureau's county file."""
    import shapefile                                                     # pyshp, in the kit's environment
    z = zipfile.ZipFile(path)
    dbf = next(n for n in z.namelist() if n.endswith(".dbf"))
    rdr = shapefile.Reader(dbf=io.BytesIO(z.read(dbf)))
    return {county_key(r["NAME"]): (r["GEOID"], r["NAME"]) for r in (x.as_dict() for x in rdr.iterRecords()) if r["STATEFP"] == FIPS}


# ------------------------------------------------------------------------------------------------ the certification

def _groups(rs, gap=10.0):
    """One printed row as groups of touching runs: [(x0, text)], split where the gap is wider than `gap` points."""
    out = []
    for r in sorted(rs, key=lambda r: r[0]):
        if out and r[0] - out[-1][2] <= gap:
            out[-1][1].append(r)
            out[-1][2] = max(out[-1][2], r[4])
        else:
            out.append([r[0], [r], r[4]])
    return [(x0, join(g)) for x0, g, _x1 in out]


def _col(x, cols):
    return max(i for i, c in enumerate(cols) if x >= c - 4)


STRAY = []      # pages whose "Office:" heading carries stray letters before it


def read_certification(path):
    """[{office, district, counties, vote_for, cols, blocks: [{page, rows: [(party text, [name text per column])]}]}], the
    date the certification was signed, the number of pages. Only the table cells are kept."""
    pdf = PDF(open(path, "rb").read())
    STRAY.clear()
    tables, cur, mode, dated, npages = [], None, None, None, 0
    for pno, (page, res) in enumerate(pdf.pages(), start=1):
        npages = pno
        body = []
        for y, rs in rows(pdf, page, res):
            text = join(rs)
            if not text or FOOTER.match(text):
                continue
            m = re.match(r"^([A-Za-z]{0,4}?)Office:\s*(.+)$", text)      # page 98 prints "SteOffice:" (stray letters before the word)
            if m:
                if m.group(1):
                    STRAY.append(pno)
                cur = {"office": m.group(2).strip(), "district": None, "counties": [], "vote_for": None, "cols": None, "blocks": [],
                       "page": pno}
                tables.append(cur)
                mode = "head"
                continue
            if cur is None:                                      # the cover page and the version history
                m = re.match(r"^Dated:\s*([A-Z][a-z]+ \d{1,2}, \d{4})$", text)
                if m:
                    dated = dt.datetime.strptime(m.group(1), "%B %d, %Y").strftime("%Y-%m-%d")
                continue
            if mode in ("head", "counties"):
                m = re.match(r"^(District|Counties|Vote For)(?::\s*|\s+)(.*)$", text)      # SD 54 prints "Counties" without a colon
                if m:
                    k, v = m.group(1), m.group(2).strip()
                    if k == "District":
                        cur["district"], mode = v, "head"
                    elif k == "Counties":
                        cur["counties"].append(v)
                        mode = "counties"
                    else:
                        if not re.fullmatch(r"\d+", v):
                            raise SystemExit(f"New York (state races): page {pno}: a \"Vote For\" that is not a number")
                        cur["vote_for"], mode = int(v), "head"
                    continue
                if mode == "counties":                           # a long list of counties wraps onto lines of its own
                    cur["counties"].append(text)
                    continue
                g = _groups(rs)
                starts = [x for x, t in g if t == "Candidate Name"]
                if starts:
                    if any(t not in ("Party", "Candidate Name") for _x, t in g):
                        raise SystemExit(f"New York (state races): page {pno}: the heading row of {cur['office']} is not laid out as expected")
                    cur["cols"], mode = starts, "body"
                    continue
                if text not in HEADER_WORDS:
                    raise SystemExit(f"New York (state races): page {pno}: an unexpected heading above the {cur['office']} table")
                continue
            cols = cur["cols"]
            left = join([r for r in rs if r[0] < cols[0] - 4])
            right = [join([r for r in rs if r[0] >= cols[0] - 4 and _col(r[0], cols) == i]) for i in range(len(cols))]
            body.append((y, cur, left, right))
        prev = None
        for y, t, left, right in body:                          # a party line's block: rows closer than BLOCK_GAP
            if prev is None or prev[1] is not t or prev[0] - y > BLOCK_GAP:
                t["blocks"].append({"page": pno, "rows": []})
            t["blocks"][-1]["rows"].append((left, right))
            prev = (y, t)
    return tables, dated, npages


def party_lines(t):
    """[(party, [name per column] or None)] for each party line of one table, in the Board's order."""
    out = []
    for b in t["blocks"]:
        party = re.sub(r"\s+", " ", " ".join(l for l, _r in b["rows"] if l)).strip()
        named = [r for _l, r in b["rows"] if any(r)]
        where = f"page {b['page']}, {t['office']} {t['district']}"
        if not party:
            raise SystemExit(f"New York (state races): {where}: a block of names with no party beside it")
        if not named:
            out.append((party, None))
            continue
        if len(named) not in (1, 2) or not all(all(c for c in r) for r in named):
            raise SystemExit(f"New York (state races): {where}: a party line whose names are not printed as given names above and "
                             f"family name below, or whole on the party's row ({len(named)} name rows)")
        # given names above and family name below; a short name is printed whole on the party's own row (AD 77)
        out.append((party, [re.sub(r"\s+", " ", " ".join(r[i] for r in named)).strip() for i in range(len(t["cols"]))]))
    return out


def county_list(parts, counties, where):
    """The certification's "Counties:" words -> sorted five-digit FIPS codes; None for "All"."""
    text = re.sub(r"\s+", " ", " ".join(parts)).strip()
    if text == "All":
        return None
    out = set()
    for piece in re.split(r"\s*,\s*|\s+&\s+|\s+and\s+", text):
        piece = re.sub(r"^Part of\s+", "", piece.strip())
        k = county_key(piece)
        if k not in counties:
            raise SystemExit(f"New York (state races): {where}: the county {piece!r} is not in the Census county file")
        out.add(counties[k][0])
    return sorted(out)


# ------------------------------------------------------------------------------------------------ the primary workbook

def classify_head(head):
    """The part of a sheet's title before the party -> a race key (SS12, SH120, COMP ...), "federal" or "party position"."""
    m = re.fullmatch(r"State Senator (\d+)(?:st|nd|rd|th) Senate District", head)
    if m:
        return f"SS{int(m.group(1))}"
    m = re.fullmatch(r"Member of Assembly (\d+)(?:st|nd|rd|th) Assembly District", head)
    if m:
        return f"SH{int(m.group(1))}"
    fixed = {"State Comptroller": "COMP", "Comptroller": "COMP", "Governor": "GOV", "Lieutenant Governor": "LTG", "Attorney General": "AG"}
    if head in fixed:
        return fixed[head]
    if head.startswith("Representative in Congress") or head.startswith("United States Senator"):
        return "federal"
    if PARTY_POSITION.search(head):
        return "party position"
    return None


def _standard(grid, hi, where, label):
    """A district sheet: candidates down the side, counties across. -> (cands, others, total, counties, wrong)."""
    head = [_clean(c) for c in grid[hi]]
    counties = [k for k, h in enumerate(head) if COUNTY_HEAD.match(h)]
    if "Total Votes by Party" not in head or not counties:
        raise SystemExit(f"New York (state races): the heading row of {where} is not laid out as expected")
    by_party = head.index("Total Votes by Party")
    by_cand = head.index("Total Votes by Candidate") if "Total Votes by Candidate" in head else None
    unread = [h for k, h in enumerate(head) if k and h and k not in counties and k not in (by_party, by_cand)]
    if unread:
        raise SystemExit(f"New York (state races): {where} has columns the loader does not read: {unread}")
    cands, others, total, wrong = [], {}, None, []
    for r in grid[hi + 1:]:
        lab = _clean(r[0]) if r else ""
        if not lab:
            if any(_clean(c) for c in r):
                raise SystemExit(f"New York (state races): a row of {where} has figures but no label")
            continue
        if total is not None:
            raise SystemExit(f"New York (state races): {where} has rows after its {TOTAL_ROW} row")
        vals = [_num(r[k] if k < len(r) else None, where) for k in counties]
        tot = _num(r[by_party] if by_party < len(r) else None, where)
        if sum(vals) != tot:
            wrong.append(f"{label}, {lab}: the counties add up to {sum(vals):,}, the total says {tot:,}")
        if lab == TOTAL_ROW:
            total = (vals, tot)
        elif lab in OTHER_ROWS:
            if lab in others:
                raise SystemExit(f"New York (state races): {where} has two {lab} rows")
            others[lab] = (vals, tot)
        else:
            cm = CANDIDATE.match(lab)
            if not cm:
                raise SystemExit(f"New York (state races): a row of {where} is neither a candidate \"Name (PTY)\" nor Blank, Void, Scattering")
            if by_cand is not None and by_cand < len(r) and r[by_cand] is not None and _num(r[by_cand], where) != tot:
                wrong.append(f"{label}, {lab}: Total Votes by Candidate says {_num(r[by_cand], where):,}, Total Votes by Party "
                             f"{tot:,} (the party's figure, which the county cells add up to, is used)")
            name = cm.group("name").strip()
            if any(c[0] == name for c in cands):
                raise SystemExit(f"New York (state races): {name} is listed twice in {where}")
            cands.append((name, cm.group("code"), tot, vals))
    if total is None or "Scattering" not in others:
        raise SystemExit(f"New York (state races): {where} has no Scattering row or no {TOTAL_ROW} row")
    every = [c[3] for c in cands] + [v for v, _t in others.values()]
    for j, k in enumerate(counties):
        s = sum(v[j] for v in every)
        if s != total[0][j]:
            wrong.append(f"{label}, {head[k]}: the rows add up to {s:,}, {TOTAL_ROW} says {total[0][j]:,}")
    s = sum(c[2] for c in cands) + sum(t for _v, t in others.values())
    if s != total[1]:
        wrong.append(f"{label}: the rows add up to {s:,}, {TOTAL_ROW} says {total[1]:,}")
    return [(n, c, t) for n, c, t, _v in cands], {k: t for k, (_v, t) in others.items()}, total[1], len(counties), wrong


def _transposed(grid, hi, where, label):
    """A statewide sheet: candidates across, counties down the side. -> (cands, others, total, counties, wrong)."""
    head = [_clean(c) for c in grid[hi]]
    if "Total Votes by County" not in head:
        raise SystemExit(f"New York (state races): the heading row of {where} has no Total Votes by County column")
    tcol = head.index("Total Votes by County")
    ccols, ocols = [], {}
    for k, h in enumerate(head):
        if k == 0 or k == tcol or not h:
            continue
        if h in OTHER_ROWS:
            ocols[h] = k
            continue
        cm = CANDIDATE.match(h)
        if not cm:
            raise SystemExit(f"New York (state races): a column of {where} is neither a candidate \"Name (PTY)\" nor Blank, Void, Scattering")
        ccols.append((cm.group("name").strip(), cm.group("code"), k))
    if "Scattering" not in ocols or not ccols:
        raise SystemExit(f"New York (state races): {where} has no Scattering column or no candidate columns")
    cols = [k for _n, _c, k in ccols] + list(ocols.values())
    wrong, county_rows, by_party, by_cand = [], [], None, None
    for r in grid[hi + 1:]:
        lab = _clean(r[0]) if r else ""
        if not lab:
            if any(_clean(c) for c in r):
                raise SystemExit(f"New York (state races): a row of {where} has figures but no label")
            continue
        cell = lambda k: r[k] if k < len(r) else None
        if lab == "Total Votes by Party":
            by_party = {k: _num(cell(k), where) for k in cols + [tcol]}
        elif lab == "Total Votes by Candidate":
            by_cand = {k: _num(cell(k), where) for k in cols if cell(k) is not None}
        elif COUNTY_ROW.match(lab):
            if by_party is not None:
                raise SystemExit(f"New York (state races): {where} has a county row after its totals")
            vals = {k: _num(cell(k), where) for k in cols}
            tot = _num(cell(tcol), where)
            if sum(vals.values()) != tot:
                wrong.append(f"{label}, {lab}: the columns add up to {sum(vals.values()):,}, Total Votes by County says {tot:,}")
            county_rows.append((lab, vals, tot))
        else:
            raise SystemExit(f"New York (state races): a row of {where} is neither a county nor a total")
    if by_party is None:
        raise SystemExit(f"New York (state races): {where} has no Total Votes by Party row")
    for k in cols:
        s = sum(v[k] for _l, v, _t in county_rows)
        if s != by_party[k]:
            wrong.append(f"{label}, {head[k]}: the counties add up to {s:,}, Total Votes by Party says {by_party[k]:,}")
        if by_cand is not None and k in by_cand and by_cand[k] != by_party[k]:
            wrong.append(f"{label}, {head[k]}: Total Votes by Candidate says {by_cand[k]:,}, Total Votes by Party {by_party[k]:,} "
                         "(the party's figure, which the county cells add up to, is used)")
    grand = sum(t for _l, _v, t in county_rows)
    if grand != by_party[tcol] or sum(by_party[k] for k in cols) != grand:
        wrong.append(f"{label}: the county totals add up to {grand:,}, the sheet's grand total says {by_party[tcol]:,}")
    names = [n for n, _c, _k in ccols]
    if len(names) != len(set(names)):
        raise SystemExit(f"New York (state races): a name is listed twice in {where}")
    return ([(n, c, by_party[k]) for n, c, k in ccols], {h: by_party[k] for h, k in ocols.items()}, by_party[tcol], len(county_rows), wrong)


def read_primaries(path):
    """({(race key, party code): contest}, [what does not add up], Counter of sheets left alone by kind)."""
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    out, wrong, skipped = {}, [], Counter()
    for ws in wb.worksheets:
        grid = [list(r) for r in ws.iter_rows(values_only=True)]
        title = next((str(c) for r in grid[:3] for c in r if isinstance(c, str) and c.strip()), "")
        first = _clean(title.strip().split("\n")[0])
        where = f"the sheet {ws.title.strip()!r} of the primary results"
        m = TITLE.match(first)
        if not m:
            raise SystemExit(f"New York (state races): {where} is titled {first!r}, which the loader cannot read")
        when = m.group("date")
        if "/" in when:
            mm, dd, yy = when.split("/")
            when = dt.date(int(yy), int(mm), int(dd)).strftime("%B %d, %Y").replace(" 0", " ")
        if when != PRINTED:
            raise SystemExit(f"New York (state races): {where} is for the primary of {when}, not {PRINTED}")
        key = classify_head(m.group("head"))
        if key is None:
            raise SystemExit(f"New York (state races): {where} is for an office the loader does not know ({m.group('head')!r})")
        if key in ("federal", "party position"):
            skipped[key] += 1
            continue
        party = m.group("party")
        if party not in PARTIES:
            raise SystemExit(f"New York (state races): a {party} primary in {where}; its election code is not set (PARTIES)")
        code = PARTIES[party]
        if (key, code) in out:
            raise SystemExit(f"New York (state races): two sheets of the primary results for {key}'s {party} primary")
        label = f"{key} {code}"
        hi = next((i for i, r in enumerate(grid) if r and _clean(r[0]) == "Candidate Name (Party)"), None)
        ht = next((i for i, r in enumerate(grid) if r and _clean(r[0]) == "County"), None)
        if hi is not None:
            cands, others, total, n, w = _standard(grid, hi, where, label)
        elif ht is not None:
            cands, others, total, n, w = _transposed(grid, ht, where, label)
        else:
            raise SystemExit(f"New York (state races): {where} has neither a \"Candidate Name (Party)\" nor a \"County\" heading row")
        wrong += w
        cands = [(WRITE_IN.sub("", n).strip(), c, v, bool(WRITE_IN.search(n))) for n, c, v in cands]
        if len({n for n, *_r in cands}) != len(cands):
            raise SystemExit(f"New York (state races): a name is listed twice in {where}")
        out[(key, code)] = {"party": party, "sheet": ws.title.strip(), "cands": cands, "scattering": others.get("Scattering", 0),
                            "blank": others.get("Blank", 0), "void": others.get("Void", 0), "total": total, "counties": n}
    wb.close()
    return out, wrong, skipped


def saved_workbook(folder):
    saved = [f for f in os.listdir(folder) if SAVED.match(f)] if os.path.isdir(folder) else []
    if not saved:
        return ""
    path = os.path.join(folder, max(saved, key=lambda f: (_stamp(f), os.path.getmtime(os.path.join(folder, f)))))
    if open(path, "rb").read(4) != b"PK\x03\x04":
        raise SystemExit(f"New York (state races): {os.path.basename(path)} is not an Excel workbook")
    return path


# ------------------------------------------------------------------------------------------------ the roster

def roster(path):
    """Sitting legislators by (chamber, district) and statewide officials by office. Ids, names and party only."""
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    legs = {}
    for mid, full, first, last, other, party, district, chamber in con.execute(
            "SELECT bioguide_id, official_full, first_name, last_name, other_names, party_name, district, chamber "
            "FROM legislators WHERE is_current = 1"):
        d = re.sub(r"^0+(?=\d)", "", str(district or "").strip())
        legs.setdefault((chamber, d), []).append(dict(id=mid, name=full or f"{first} {last}", first=first, last=last, other=other,
                                                      party=party))
    offs = {office: dict(id=oid, name=full, party=party, first=first, last=last, other=None) for oid, full, first, last, office, party in
            con.execute("SELECT bioguide_id, official_full, first_name, last_name, office, party_name FROM officials")}
    con.close()
    return legs, offs


def variants(m):
    """Every reading of a member's name the roster gives: (given names, family name)."""
    out = [name_parts(m["name"])]
    if m.get("last"):
        out.append((fold(m.get("first") or "").split(), fold(m["last"])))
    for o in (m.get("other") or "").split(";"):
        g, f = name_parts(o.strip())
        if f and g:
            out.append((g, f))
    return [v for v in out if v[1]]


def parts_of(name):
    """name_parts, with a particle printed apart kept with the family name (Joseph P. De Stefano -> de stefano)."""
    g, f = name_parts(name)
    g = list(g)
    while len(g) > 1 and g[-1] in PARTICLES:
        f = g.pop() + " " + f
    return g, f


LOOSE = []      # (race, candidate, member) matched by the looser rule, printed for reading


def find_incumbent(names, member, rid):
    """The one name in the race that fits the member, or None (none fit, or more than one). When none fits, a candidate
    whose family name is the member's and unique in the race, with given names beginning with the same two letters, is
    taken and listed for reading."""
    if not member:
        return None
    vs = variants(member)
    parts = {n: parts_of(n.split(" / ")[0]) for n in names}
    joined = lambda p, v: p[1].replace(" ", "") == v[1].replace(" ", "") and fits((p[0], v[1]), v)      # De Stefano, DeStefano
    hits = [n for n in names if any(fits(parts[n], v) or joined(parts[n], v) for v in vs)]
    if not hits:
        fam = {v[1].replace(" ", "") for v in vs}
        same = [n for n in names if parts[n][1].replace(" ", "") in fam]
        if len(same) == 1 and parts[same[0]][0] and any(v[0] and parts[same[0]][0][0][:2] == v[0][0][:2] for v in vs):
            hits = same
            LOOSE.append((rid, same[0], member["name"]))
    return hits[0] if len(hits) == 1 else None


# ------------------------------------------------------------------------------------------------ loading

def load(db_path, say=print, cache=CACHE, fetch=True, roster_db=ROSTER, county_zip=COUNTY_ZIP):
    cert = os.path.join(cache, CERT_FILE)
    if fetch:
        from states import net
        net.patient_lookups()
        net.download(CERT_URL, cert, max_age_days=30, tries=3, say=say)      # one ask and two more; a refusal keeps the cached copy
    if not os.path.exists(cert):
        raise SystemExit(f"New York (state races): {CERT_FILE} is not in {cache}; the federal loader (ballot/lists/ny.py) saves it")
    folder = os.path.join(cache, "ny")
    wpath = saved_workbook(folder)
    why = ""
    if not wpath and fetch:
        wpath, why = primary_workbook(folder, say)
    counties = census_counties(county_zip)
    if len(counties) != TOTAL_COUNTIES:
        raise SystemExit(f"New York (state races): the Census county file has {len(counties)} New York counties, not {TOTAL_COUNTIES}")
    legs, offs = roster(roster_db)
    LOOSE.clear()
    checks, matched = [], []

    # 1. the November list
    tables, dated, npages = read_certification(cert)
    races, gen, federal_tables, empty_lines, named_lines = OrderedDict(), OrderedDict(), 0, [], 0
    for t in tables:
        office = t["office"]
        if office in FEDERAL:
            federal_tables += 1
            continue
        if office not in OFFICES:
            raise SystemExit(f"New York (state races): the certification has an office the loader does not know: {office!r} (page {t['page']})")
        key, level, kind, shown, roster_office = OFFICES[office]
        d = t["district"] or ""
        if key in ("SS", "SH", "SCJ"):
            if not re.fullmatch(r"\d+", d):
                raise SystemExit(f"New York (state races): {office} on page {t['page']} has the district {d!r}")
            d = str(int(d))
            rid = f"2026-{STATE}-{key}{d}"
        else:
            if d != "Statewide":
                raise SystemExit(f"New York (state races): {office} on page {t['page']} is not statewide ({d!r})")
            d, rid = None, f"2026-{STATE}-{key}"
        if rid in races:
            raise SystemExit(f"New York (state races): {rid} appears twice in the certification")
        if not t["cols"] or t["vote_for"] is None:
            raise SystemExit(f"New York (state races): the {office} table on page {t['page']} has no heading row or no \"Vote For\"")
        if (len(t["cols"]) == 2) != (key == "GOV"):
            raise SystemExit(f"New York (state races): the {office} table on page {t['page']} has {len(t['cols'])} name columns")
        cids = county_list(t["counties"], counties, f"{rid} (page {t['page']})")
        lines_ = party_lines(t)
        per_party = Counter(p for p, _n in lines_)
        off = {p: n for p, n in per_party.items() if n != t["vote_for"]}
        if off:
            checks.append(f"{rid}: party lines not printed once per seat ({t['vote_for']}): " + ", ".join(f"{p} {n}" for p, n in off.items()))
        people = OrderedDict()
        for party, names in lines_:
            if names is None:
                empty_lines.append((rid, party))
                continue
            named_lines += 1
            nm = " / ".join(names)
            if party in people.get(nm, []):
                checks.append(f"{rid}: {nm} printed twice on the {party} line")
            people.setdefault(nm, []).append(party)
        # a person printed two ways on two lines would be two candidates: say so
        plist = list(people)
        for i, a in enumerate(plist):
            for b in plist[i + 1:]:
                if same_person(a.split(" / ")[0], b.split(" / ")[0]) and fold(a) != fold(b):
                    checks.append(f"{rid}: {a} and {b} may be the same person printed two ways")
        if key in ("SS", "SH"):
            chamber = "Senate" if key == "SS" else "House"
            sitting = legs.get((chamber, d), [])
            holder = sitting[0] if len(sitting) == 1 else None
            if len(sitting) > 1:
                checks.append(f"{rid}: {len(sitting)} sitting members in the roster for this seat; none is taken as the holder")
            jur, jur_id = f"{'Senate' if key == 'SS' else 'Assembly'} District {d}", f"{STATE}-{d}"
        elif key == "SCJ":
            holder, jur, jur_id = None, f"{ordinal(d)} Judicial District", f"{STATE}-JD{d}"
        else:
            holder, jur, jur_id = offs.get(roster_office) if roster_office else None, NAME, FIPS
        note = [NOTES[key]] if key in NOTES else []
        if key == "GOV" and offs.get("lt_governor"):
            note.append(f"Lieutenant Governor today: {offs['lt_governor']['name']}.")
        if key == "SCJ" and t["vote_for"] > 1:
            note.append(f"Voters choose up to {t['vote_for']}.")
        if key in ("SS", "SH") and holder is None:
            note.append(NO_HOLDER)
            checks.append(f"{rid}: no sitting member in the roster for this seat")
        if not people:
            checks.append(f"{rid}: no candidate on the November list")
            note.append("No candidate is printed for this seat on the Board's certification.")
        races[rid] = {"race_id": rid, "state": STATE, "level": level, "office_kind": kind, "office": shown, "jurisdiction": jur,
                      "jurisdiction_id": jur_id, "county_ids": json.dumps(cids) if cids else None, "district": d, "seat": None,
                      "special": 0, "partisan": 1, "holder_id": holder["id"] if holder else None,
                      "holder_name": holder["name"] if holder else None, "holder_party": holder["party"] if holder else None,
                      "election_date": GENERAL, "note": note, "_key": key, "_holder": holder, "_seats": t["vote_for"], "_cids": cids}
        gen[rid] = people

    # every seat that must be on the ballot
    for key, seats in SEATS.items():
        have = {int(r.split(f"-{key}")[1]) for r in races if re.fullmatch(rf"2026-{STATE}-{key}\d+", r)}
        missing, extra = sorted(set(range(1, seats + 1)) - have), sorted(have - set(range(1, seats + 1)))
        if missing or extra:
            checks.append(f"{'Senate' if key == 'SS' else 'Assembly'}: districts missing from the certification {missing}; unexpected {extra}")
    for key in ("GOV", "COMP", "AG"):
        if f"2026-{STATE}-{key}" not in races:
            checks.append(f"2026-{STATE}-{key}: not on the certification")

    cands = []
    for rid, people in gen.items():
        r = races[rid]
        h = r["_holder"]
        inc_name = find_incumbent(list(people), h, rid) if h else None
        if h and inc_name is None:
            matched.append(f"{rid}: {h['name']}, who holds the seat, is not among the names on the list")
        for k, (nm, held) in enumerate(people.items(), start=1):
            first_major = next((p for p in held if party_code(p) in ("D", "R")), held[0])
            inc = int(nm == inc_name)
            note = (f"On the ballot on {len(held)} party lines: {', '.join(held)}." if len(held) > 1 else None)
            cands.append([rid, "general", GENERAL, nm, ", ".join(held), party_code(first_major), k, inc, 0, None, None, None,
                          h["id"] if inc else None, SRC_CERT, note])
    n_general = len(cands)
    if sum(len(held) for people in gen.values() for held in people.values()) != named_lines:
        checks.append(f"the party lines held by the stored candidates do not add up to the {named_lines} named lines read")

    # 2. the June 23 primaries
    contests, wrong, skipped = ({}, [], Counter())
    fields, single, upset, silent = Counter(), [], [], []
    if wpath:
        contests, wrong, skipped = read_primaries(wpath)
    for (key, code), c in sorted(contests.items()):
        rid = f"2026-{STATE}-{key}"
        party = c["party"]
        if key == "LTG" and rid not in races:
            races[rid] = {"race_id": rid, "state": STATE, "level": "statewide", "office_kind": "lieutenant_governor",
                          "office": "Lieutenant Governor", "jurisdiction": NAME, "jurisdiction_id": FIPS, "county_ids": None,
                          "district": None, "seat": None, "special": 0, "partisan": 1,
                          "holder_id": (offs.get("lt_governor") or {}).get("id"), "holder_name": (offs.get("lt_governor") or {}).get("name"),
                          "holder_party": (offs.get("lt_governor") or {}).get("party"), "election_date": GENERAL,
                          "note": ["Nominated in each party's own primary on June 23; in November the Lieutenant Governor is elected jointly "
                                   f"with the Governor, on the tickets listed under 2026-{STATE}-GOV."],
                          "_key": "LTG", "_holder": offs.get("lt_governor"), "_seats": 1, "_cids": None}
            gen[rid] = OrderedDict()
        if rid not in races:
            raise SystemExit(f"New York (state races): the primary results have a {party} primary for {rid}, which is not on the November list")
        if len(c["cands"]) < 2:
            single.append(f"{rid} {code}")
            continue
        fields[code] += 1
        part = 1 if key == "LTG" else 0
        ticket_src = gen.get(f"2026-{STATE}-GOV") if key in ("GOV", "LTG") else gen[rid]
        noms = [nm.split(" / ")[part if " / " in nm else 0] for nm, held in (ticket_src or {}).items() if party in held]
        names = [n for n, _pc, _v, _w in c["cands"]]
        picked = [k for k, n in enumerate(names) if any(same_person(n, x) for x in noms)]
        if len(picked) > 1:
            raise SystemExit(f"New York (state races): a November nominee fits more than one name in the {rid} {party} primary")
        base = sum(v for _n, _c, v, _w in c["cands"]) + c["scattering"]
        if base:
            ranked = sorted(range(len(names)), key=lambda k: -c["cands"][k][2])
            if c["cands"][ranked[0]][2] == c["cands"][ranked[1]][2]:
                raise SystemExit(f"New York (state races): the {rid} {party} primary is a tie in the results workbook; read who the Board certified")
            winner = ranked[0]
            if winner not in picked:
                upset.append(f"{rid} {code}")
        else:
            winner = picked[0] if picked else None
            silent.append(f"{rid} {code}")
        h = races[rid]["_holder"]
        inc_name = find_incumbent(names, h, rid) if h else None
        for k, (name, _pc, votes, wi) in enumerate(c["cands"]):
            notes = []
            if wi:
                notes.append("A write-in candidate, named in the Board's results with the votes counted for this name.")
            if not base:
                notes.append(NO_VOTES)
            elif k == winner and winner not in picked:
                notes.append(NOT_ON_LIST)
            inc = int(name == inc_name)
            cands.append([rid, f"primary-{code}", PRIMARY, name, party, party_code(party), None, inc, int(wi),
                          votes if base else None, round(100 * votes / base, 1) if base else None,
                          None if winner is None else "advanced" if k == winner else "lost", h["id"] if inc else None, SRC_PRI,
                          " ".join(notes) or None])
    for rid in races:
        if races[rid]["_key"] == "GOV" and not any(k[0] in ("GOV", "LTG") for k in contests):
            races[rid]["note"].append("The Board's June 23 primary results hold no contest for either office." if wpath else
                                      "The June 23 primary results are not loaded yet.")

    # 3. checks, and the last look at every stored text
    keys = [(c[0], c[1], c[3]) for c in cands]
    if len(keys) != len(set(keys)):
        raise SystemExit("New York (state races): two candidate rows share race, election and name")
    for c in cands:
        if CONTACT.search(c[3]) or CONTACT.search(c[4] or "") or (c[14] and CONTACT.search(c[14])):
            raise SystemExit(f"New York (state races): a stored cell for {c[0]} failed the contact-detail check (not shown); read the file again")
    for r in races.values():
        if CONTACT.search(" ".join(r["note"])) or CONTACT.search(r["holder_name"] or "") or CONTACT.search(r["jurisdiction"] or ""):
            raise SystemExit(f"New York (state races): the note, holder or jurisdiction of {r['race_id']} failed the contact-detail check (not shown)")
    for w in wrong:
        checks.append(f"primary results: {w}")
    for x in upset:
        checks.append(f"{x}: the primary's winner is not on the November ballot on the party's line")

    # 4. places: counties, and the districts with the counties each reaches (from the certification's "Counties:" lines)
    place_rows = [("county", g, f"{n} County", json.dumps([g]), SRC_COUNTY) for g, n in sorted(counties.values())]
    for rid, r in races.items():
        if r["_key"] in ("SS", "SH", "SCJ"):
            kind = {"SS": "senate", "SH": "house", "SCJ": "judicial"}[r["_key"]]
            place_rows.append((kind, r["jurisdiction_id"], r["jurisdiction"], json.dumps(r["_cids"]) if r["_cids"] else None, SRC_CERT))
    pk = [(p[0], p[1]) for p in place_rows]
    if len(pk) != len(set(pk)):
        raise SystemExit("New York (state races): two places share a kind and id")

    # 5. write New York's rows only, in one transaction
    race_rows = [tuple(" ".join(r["note"]) or None if k == "note" else r[k] for k in (
        "race_id", "state", "level", "office_kind", "office", "jurisdiction", "jurisdiction_id", "county_ids", "district", "seat",
        "special", "partisan", "holder_id", "holder_name", "holder_party", "election_date", "note")) for r in races.values()]
    prim = [c for c in cands if c[1] != "general"]
    by_level = Counter(races[c[0]]["_key"] if races[c[0]]["_key"] in ("SS", "SH", "SCJ") else "statewide" for c in cands if c[1] == "general")
    fusion = sum(1 for c in cands if c[1] == "general" and ", " in c[4])
    sources = [
        (SRC_CERT, STATE, "official candidate list", AGENCY,
         "Certification for the November 3, 2026 General Election (amended, " + (dated or "undated") + "): state offices", CERT_URL,
         dated or "", fetched(cert), sha(cert), n_general,
         f"Listed on {CERT_PAGE}; the same file the federal loader reads ({npages} pages). Read: Governor and Lieutenant Governor, "
         f"Comptroller, Attorney General, all 63 State Senate and 150 Assembly seats, and Justice of the Supreme Court in "
         f"{sum(1 for r in races.values() if r['_key'] == 'SCJ')} judicial districts ("
         + ", ".join(str(r["district"]) for r in races.values() if r["_key"] == "SCJ") + f"); {federal_tables} congressional tables are "
         f"left to the federal pages. Only the office, district, counties, seats, party and name cells are read; the file prints no "
         f"contact details. Several parties may nominate one candidate (fusion): {fusion} candidates hold more than one line, and "
         f"{len(empty_lines)} party lines are printed with no candidate. Ballot order is the order of each candidate's first line on the "
         f"list. The counties each district reaches are the certification's own \"Counties\" lines."),
        (SRC_ROSTER, STATE, "member roster", "Open States people project (CC0), as loaded into state_ny.sqlite",
         "Sitting New York legislators and statewide officials", "https://github.com/openstates/people", "", fetched(roster_db), sha(roster_db),
         sum(len(v) for v in legs.values()) + len(offs),
         "Who holds each seat today, and which candidate is a sitting member (same chamber and district, the name or one of the roster's "
         "other spellings fits, one fit only). The roster's statewide officials are the Governor, Lieutenant Governor and Attorney "
         "General; it carries no Comptroller and no judges. Ids, names, party, chamber and district only."),
        (SRC_COUNTY, STATE, "county codes", "U.S. Census Bureau", "Cartographic boundary file, counties, 2024 (1:500,000)", COUNTY_URL,
         "2024", fetched(county_zip), sha(county_zip), len(counties),
         "Five-digit county codes (GEOID) for New York's 62 counties, matched by name to the certification's \"Counties\" lines."),
    ]
    if wpath:
        sources.append((
            SRC_PRI, STATE, "official results", AGENCY,
            "June 23, 2026 Primary Election: vote results (" + os.path.basename(wpath) + "): state offices", PRIMARY_URL,
            "2026-08-31" if "08312026" in wpath else "", fetched(wpath), sha(wpath), len(prim),
            f"Linked from {RESULTS_PAGE}; the copy saved in ballot_cache/ny/ (elections.ny.gov answers scripts with a Cloudflare challenge), "
            f"the same file the federal loader reads. {len(contests)} state contests read (Comptroller, State Senate, Assembly); "
            f"{skipped.get('federal', 0)} congressional sheets are the federal loader's and {skipped.get('party position', 0)} sheets for "
            "judicial delegates and state committee members (party positions, not offices) are left alone. "
            + ("Every sheet's counties and rows add up to its totals. " if not wrong else "Did not add up: " + "; ".join(wrong) + ". ")
            + "Shares are of the candidates' votes plus write-ins (Scattering); blank and void ballots are left out. The most votes wins "
              "a New York primary (no runoffs). The workbook carries names and votes only."
            + (f" Contests with one name on the ballot (no field): {', '.join(single)}." if single else "")
            + (f" Winner not on the November ballot on the party's line: {', '.join(upset)}." if upset else "")))
    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA)
    with con:
        con.execute("DELETE FROM sl_candidates WHERE race_id IN (SELECT race_id FROM sl_races WHERE state = ?) OR race_id LIKE ?",
                    (STATE, f"2026-{STATE}-%"))
        con.execute("DELETE FROM sl_races WHERE state = ?", (STATE,))
        con.execute("DELETE FROM sl_sources WHERE state = ?", (STATE,))
        con.execute("DELETE FROM sl_places WHERE source_id LIKE ? OR (kind = 'county' AND id GLOB ?)", (f"{STATE.lower()}-%", f"{FIPS}[0-9][0-9][0-9]"))
        con.executemany("INSERT INTO sl_races VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", race_rows)
        con.executemany("INSERT INTO sl_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [tuple(c) for c in cands])
        con.executemany("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", sources)
        con.executemany("INSERT INTO sl_places VALUES (?,?,?,?,?)", place_rows)
    con.close()

    # 6. say what happened
    n_ss = sum(1 for r in races if "-SS" in r)
    n_sh = sum(1 for r in races if "-SH" in r)
    n_scj = sum(1 for r in races if "-SCJ" in r)
    say(f"    New York state offices: {len(races)} races (statewide {sum(1 for r in races.values() if r['level'] == 'statewide')}, Senate {n_ss}, "
        f"Assembly {n_sh}, Supreme Court {n_scj} judicial districts); {n_general} candidates on the November list (statewide "
        f"{by_level['statewide']}, Senate {by_level['SS']}, Assembly {by_level['SH']}, Supreme Court {by_level['SCJ']}; {fusion} on more "
        f"than one line); "
        + (f"June 23 primaries: {sum(fields.values())} fields (" + ", ".join(f"{n} {k}" for k, n in sorted(fields.items())) + f"), "
           f"{len(prim)} rows, official votes " + ("reconciled" if not wrong else "with differences (see checks)")
           if wpath else f"the June 23 primaries wait for the Board's results workbook ({why or 'not in ' + folder})"))
    incs = sum(1 for c in cands if c[1] == "general" and c[7])
    say(f"      incumbents marked on the November list: {incs}; one-name primary contests (no field): {', '.join(single) or 'none'}")
    for rid, cand, member in sorted(set(LOOSE)):
        say(f"      incumbent by the looser rule (read it): {rid} {cand} = {member}")
    for line in matched:
        say(f"      holder: {line}")
    if STRAY:
        say(f"      read past stray letters printed before \"Office:\" on page(s) {', '.join(map(str, STRAY))}")
    for line in checks:
        say(f"      check: {line}")
    return dict(races=len(races), general=n_general, senate=by_level["SS"], assembly=by_level["SH"], statewide=by_level["statewide"],
                court=by_level["SCJ"], primary=len(prim), fields=dict(fields), single=single, upset=upset, checks=checks,
                empty_lines=len(empty_lines), fusion=fusion)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", required=True, help="the state-and-local ballot database to write New York's rows into")
    ap.add_argument("--no-fetch", action="store_true", help="use the cached files as they are")
    a = ap.parse_args()
    load(a.db, fetch=not a.no_fetch)
