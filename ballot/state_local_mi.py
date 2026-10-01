"""
Michigan: the state offices on the November 3, 2026 ballot, from the same two reports the federal loader reads
(ballot/lists/mi.py): the Department of State's Official Candidate Listing for the General Election and for the August 4
Primary, published from the Bureau of Elections' filing system (mi-boe.entellitrak.com, "All State and Judicial
Offices"). Each report is one HTML page: a heading per office, then a row per candidate with five cells: a status mark
(DISQ disqualified, WITHD withdrawn, blank otherwise), "Party / Incumbent" (the party; a judge's incumbency mark), the
name written "Last, First", the filing date and the filing method. The report carries no addresses, telephones,
websites or e-mail; this loader reads only the heading, the status mark, the party and the name, and uses the date cell
only to recognise a candidate row (it is never kept).

Read here: Governor and Lieutenant Governor (elected together, written as the ticket, governor first), Secretary of
State, Attorney General, the State Board of Education and the three university boards (all partisan in Michigan, two
seats each), every State Senate seat (all 38: four-year terms, all elected in 2026) and every State House seat (all 110),
and the two state courts elected statewide or by appeals district (Justice of Supreme Court, Judge of Court of Appeals;
nonpartisan on the ballot, so the party is "Nonpartisan office", and the listing's own incumbency mark is kept).

The November ballot is every candidate without a status mark, in the listing's order (by party, as the ballot prints
them); a nonpartisan race gets no ballot order, since the listing does not say how the ballot orders those names. A
party's primary field is its unmarked candidates on the August listing (two or more); the one on the November listing
for that party advanced. The Department's results site refuses scripts, so the fields say who advanced and carry no
votes. Sitting members come from state_mi.sqlite (the Open States roster): the member for the same chamber and district
whose name fits exactly one candidate is marked incumbent.

The local level (from 2026-10-01)
---------------------------------
Two parts, written into the same database beside the state rows.

1. Circuit, district and probate judges, from the same Official Candidate Listing (level "court", like the Supreme
   Court and the Court of Appeals). Which counties a circuit or a district court district reaches is read from the
   law that draws them, the Revised Judicature Act (MCL 600.501 to 600.550a and 600.8101 to 600.8163), in the
   Legislature's own PDF of each chapter (the Legislature's site allows scripts, one request a second, and offers
   these files for the purpose). A circuit is the counties the act names; the 57 circuits must cover the 83 counties
   once each, or the loader says so. A district is the counties the act names for it; where the act names only
   cities, the county or counties the Census Bureau's list puts those cities in; and a city the act takes out of a
   county's own district ("the county of Oakland except the cities of ... Northville") is counted in the district
   that names it. An election division is read the same way. A probate judge's county is in the listing's heading.

2. County by county: there is no statewide list of county, city, village, township, school, college and library
   candidates in Michigan (they file with county, city and township clerks), so each county clerk's own November 3,
   2026 list is read, largest counties first, as far as the twelve largest in this pass. The table COUNTIES names
   each list's address, read by hand on the clerk's own page, and the reader for its layout. Most of these lists
   carry candidates' addresses, and some carry telephone numbers and e-mail. Those columns are never read: every
   reader takes cells by position or by heading (office and jurisdiction headings, the party cell, the name cell and
   the status mark: withdrew, disqualified, qualified write-in), in memory, and only that cut-down copy is kept, as
   JSON, in ballot_cache/mi/local/ with the day it was fetched and the SHA-256 of the file as it came. A kept cell
   that reads like contact details is blanked and counted, never printed. A list that no longer fits its reader
   stops that county only: the loader names the county, the page and the check, never the line, and goes on with
   the copy on disk or, with none, a gap.
   The state, legislative and federal contests on a county's list are left to the statewide listing; its judges are
   used only to check part 1 (every court contest a county prints must be one the statute puts in that county).
   A contest printed on two counties' lists (a school district, a college, a village across a county line) is one
   race, counted once, with every county in county_ids; the list of the district's own county is read first, and
   where two lists disagree (a term, how many to vote for, a name on one and not the other) the run says so.
   Withdrawn, disqualified and resigned candidates are left off and counted; a mark a list does not explain
   (Muskegon's "(W)") leaves the name off and becomes a race-scope gap. Local ballot questions are not loaded.
   Three of the twelve largest counties have no reader yet (Genesee, Washtenaw, Livingston: no November list a
   script can reach); each is a county-scope gap with its own reason, and the table names the file to save by hand.

Places: counties from the Census Bureau's county file the kit keeps; cities, townships and villages by the Census
Bureau's 2020 code lists (a name must match exactly one entry of the right kind in the county, else the place gets
the county's code and a slug of its name); school districts by the state's own district code, from the Center for
Educational Performance and Information's Educational Entity Master (the public data set its page offers; only the
district code, names, county and status columns are kept: the file's street, telephone, e-mail and administrator
columns are never read); a community college by its name alone (a college district is no one county's, and no two
colleges share a name: MI-X-delta-college); a district library, which has no official code here, by the three-digit code
of the first county whose list prints it and a slug of its name (MI-X-163-plymouth-district-library).

Each county's reader goes on only if the file's own heading names the November 2026 election (an address can come to
hold another election's list), and a list saved by hand in ballot_cache/mi/local/<county>/ is read when the county's
site does not answer.

Writes only rows for Michigan (state = 'MI') in the database it is given; never touches ballot_2026.sqlite.
"""

import collections
import csv
import datetime as dt
import difflib
import hashlib
import http.cookiejar
import io
import json
import os
import re
import sqlite3
import time
import unicodedata
import urllib.parse
import zipfile
import html as H
from urllib.request import HTTPCookieProcessor, Request, build_opener

from ballot import pdftext
from ballot.check_local import EXTRA_SCHEMA, contact_like
from ballot.common import HERE, fold, name_parts, party_code
from ballot.lists.mi import BASE, first_last
from ballot.match import fits
from ballot.pdftext import Font, Ref, _mul, _ops
from states import net

STATE = "MI"
GENERAL = "2026-11-03"
PRIMARY = "2026-08-04"
CACHE = os.path.join(HERE, "ballot_cache")
ROSTER = os.path.join(HERE, "state_mi.sqlite")
SRC_GEN = "mi-sos-2026-general-listing"
SRC_PRI = "mi-sos-2026-primary-listing"
SRC_ROSTER = "mi-openstates-roster"
PRIMARY_CODE = {"Democratic Party": "DEM", "Republican Party": "REP"}

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

# heading -> (race key, level, office_kind, office, partisan); district offices take the district from the heading
STATEWIDE = [
    (r"^Governor / Lt\. Governor\b", "GOV", "statewide", "governor", "Governor and Lieutenant Governor", 1),
    (r"^Secretary of State\b", "SOS", "statewide", "secretary_of_state", "Secretary of State", 1),
    (r"^Attorney General\b", "AG", "statewide", "attorney_general", "Attorney General", 1),
    (r"^Member of the State Board of Education\b", "SBOE", "statewide", "state_board_of_education", "Member of the State Board of Education", 1),
    (r"^Regent of the University of Michigan\b", "UMREG", "statewide", "university_board", "Regent of the University of Michigan", 1),
    (r"^Trustee of Michigan State University\b", "MSUTR", "statewide", "university_board", "Trustee of Michigan State University", 1),
    (r"^Governor of Wayne State University\b", "WSUGOV", "statewide", "university_board", "Governor of Wayne State University", 1),
    (r"^Justice of Supreme Court\b", "SC", "court", "supreme_court", "Justice of Supreme Court", 0),
]
ORD = r"(\d+)(?:st|nd|rd|th) District"
NUMBER = {1: "One", 2: "Two", 3: "Three", 4: "Four", 5: "Five"}
LOCAL_COURTS = re.compile(r"Judge of (Circuit|District|Probate) Court\b")
OUT_OF_SCOPE = re.compile(r"Representative in Congress|^U\.S\. Senate")


def classify(head):
    """One heading of the report -> a race dict, or None (federal offices and local courts are not read here)."""
    seats = re.search(r"\((\d+)\) Positions?\b", head)
    seats = int(seats.group(1)) if seats else 1
    term = re.search(r"(\d+) Year Terms?", head)
    partial = re.search(r"Partial Term(?: - \d+ Years)? Ending (\d\d/\d\d/\d{4})", head)
    bits = []
    if term and not partial:
        bits.append(f"{term.group(1)}-year term")
    if partial:
        bits.append(f"Partial term ending {partial.group(1)}")
    if seats > 1:
        bits.append(f"{NUMBER.get(seats, seats)} seats; each voter may choose up to {seats}")
    race = None
    m = re.match(ORD + r" State Senator\b", head)
    if m:
        d = str(int(m.group(1)))
        race = dict(key=f"SS{d}", level="legislature", office_kind="state_senate", office="State Senator", district=d, partisan=1, chamber="Senate")
    m = m or re.match(ORD + r" Representative in State Legislature\b", head)
    if m and not race:
        d = str(int(m.group(1)))
        race = dict(key=f"SH{d}", level="legislature", office_kind="state_house", office="Representative in State Legislature", district=d,
                    partisan=1, chamber="House")
    if not race:
        m = re.match(ORD + r" Judge of Court of Appeals (Incumbent|Non-Incumbent)\b", head)
        if m:
            d = str(int(m.group(1)))
            key = f"COA{d}" + ("-NI" if m.group(2) == "Non-Incumbent" else "") + ("-PT" if partial else "")
            bits.insert(0, f"{m.group(2)} position" + ("s" if seats > 1 else ""))
            race = dict(key=key, level="court", office_kind="court_of_appeals", office="Judge of Court of Appeals", district=d, partisan=0)
    if not race:
        for pat, key, level, kind, office, partisan in STATEWIDE:
            if re.match(pat, head):
                race = dict(key=key + ("-PT" if partial else ""), level=level, office_kind=kind, office=office, district=None, partisan=partisan)
                break
    if not race:
        return None
    if race["key"] == "GOV":
        bits.append("Governor and Lieutenant Governor are elected together; each ticket is written governor first")
    race.update(seats=seats, special=1 if partial else 0, note="; ".join(bits) or None, heading=head)
    return race


def read_listing(path):
    """[(heading, status, party cell, name)] for every candidate row, in the report's order. Only these cells are read."""
    text = open(path, encoding="utf-8", errors="replace").read()
    if "Official Candidate Listing" not in text:
        raise SystemExit(f"Michigan: {os.path.basename(path)} is not the Official Candidate Listing report")
    total = re.search(r"(\d+) Candidates as of (\w{3}) (\w{3}) (\d\d) ", text)
    head, out = None, []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", text, re.S):
        h = re.search(r'<a id="[^"]*"></a><span[^>]*>([^<]+)</span>', tr)
        if h:
            head = re.sub(r"\s+", " ", H.unescape(h.group(1))).strip()
            continue
        cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        if len(cells) != 8:
            continue
        clean = lambda i: re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", "", cells[i])).replace("\xa0", " ")).strip()
        if not re.fullmatch(r"\d\d/\d\d/\d{4}", clean(5)):        # the column-heading row; the date itself is not kept
            continue
        out.append((head, clean(1), clean(3), clean(4)))
    published = ""
    if total:
        month = dt.datetime.strptime(total.group(3), "%b").month
        published = f"2026-{month:02d}-{int(total.group(4)):02d}"
    return out, (int(total.group(1)) if total else None), published


def ballot_name(raw):
    """'Benson, Jocelyn  / Brinks, Winnie' -> 'Jocelyn Benson / Winnie Brinks'; 'Gilchrist II, Garlin' -> 'Garlin Gilchrist II'."""
    return " / ".join(re.sub(r"\s+", " ", first_last(part.strip())) for part in raw.split(" / "))


def roster():
    """Sitting legislators by (chamber, district) and statewide officials by office. Names, party and id only."""
    con = sqlite3.connect(f"file:{ROSTER}?mode=ro", uri=True)
    members = {}
    for mid, full, first, last, party, district, chamber in con.execute(
            "SELECT bioguide_id, official_full, first_name, last_name, party_name, district, chamber FROM legislators WHERE is_current = 1"):
        members.setdefault((chamber, str(district)), []).append(dict(id=mid, name=full or f"{first} {last}", first=first, last=last, party=party))
    officials = {}
    for oid, full, office, party in con.execute("SELECT bioguide_id, official_full, office, party_name FROM officials"):
        officials[office] = dict(id=oid, name=full, party=party)
    con.close()
    return members, officials


def member_parts(m):
    g, f = name_parts(m["name"])
    if m.get("last"):
        f = fold(m["last"])
        g = [w for w in fold(m.get("first") or "").split()] or g
    return g, f


LOOSE = []      # (race, candidate, member) matched by the looser rule, printed for reading


def find_incumbent(names, member, rid=None):
    """The one name in the race that fits the member, or None (none fit, or more than one). When no name fits, a
    candidate whose family name is the member's and unique in the race, with given names that begin with the same two
    letters, is taken (Jasper for Jaz, Timothy for Timmy), and listed for reading."""
    if not member:
        return None
    mp = member_parts(member)
    parts = {n: name_parts(n.split(" / ")[0]) for n in names}
    hits = [n for n in names if fits(parts[n], mp)]
    if not hits:
        same = [n for n in names if parts[n][1] == mp[1]]
        if len(same) == 1 and parts[same[0]][0] and mp[0] and parts[same[0]][0][0][:2] == mp[0][0][:2]:
            hits = same
            LOOSE.append((rid, same[0], member["name"]))
    return hits[0] if len(hits) == 1 else None


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def fetched(path):
    return dt.datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d")


# =====================================================================================================================
# The local level
# =====================================================================================================================

LOCAL = os.path.join(CACHE, "mi", "local")
FIPS = "26"
NONPARTISAN = "Nonpartisan office"
LOCAL_MAX_AGE_DAYS = 3                  # a county's cut-down list is used again for three days
COUNTY_ZIP = os.path.join(HERE, "states_cache", "census", "cb_2024_us_county_500k.zip")
COUNTY_URL = "https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_county_500k.zip"
COUSUB_URL = "https://www2.census.gov/geo/docs/reference/codes2020/cousub/st26_mi_cousub2020.txt"
PLACE_URL = "https://www2.census.gov/geo/docs/reference/codes2020/place/st26_mi_place2020.txt"
MCL_PDF = "https://www.legislature.mi.gov/documents/mcl/pdf/MCL-236-1961-{}.pdf"
MCL_ACT = "https://www.legislature.mi.gov/Laws/MCL?objectName=mcl-Act-116-of-1954"
EEM_URL = "https://cepi.state.mi.us/eem/PublicDatasets.aspx"
SRC_COUNTIES, SRC_COUSUB, SRC_PLACE = "mi-census-2024-counties", "mi-census-2020-cousub", "mi-census-2020-place"
SRC_MCL5, SRC_MCL81, SRC_EEM = "mi-mcl-600-chapter-5", "mi-mcl-600-chapter-81", "mi-cepi-eem-districts"
# the page builder's own last check is a little wider than the trial check's (it also stops at Court and Place)
BUILDER_STREET = re.compile(r"\b\d{1,6}\s+(?:[NSEW]\.?\s+)?[A-Za-z0-9.' -]{1,40}?\s(?:St|Street|Ave|Avenue|Rd|Road|Blvd|Boulevard|Dr|Drive|Ln|Lane|Way|Ct|Court|"
                            r"Cir|Circle|Pkwy|Parkway|Hwy|Highway|Trl|Trail|Pl|Place|Ter|Terrace)\b\.?", re.I)
MONTHS = "January February March April May June July August September October November December".split()


class LayoutError(Exception):
    """A list that no longer fits its reader. The message names the page and the check, never the text."""


def reads_like_contact(text, strict=True):
    return bool(text) and (contact_like(text, strict) or bool(strict and BUILDER_STREET.search(str(text))))


def squeeze(text):
    return re.sub(r"\s+", " ", text or "").strip()


def slug(text):
    t = unicodedata.normalize("NFKD", text or "")
    return re.sub(r"[^a-z0-9]+", "-", "".join(ch for ch in t if not unicodedata.combining(ch)).lower()).strip("-")


def ordinal(n):
    n = int(n)
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def and_names(items):
    items = list(items)
    if not items:
        return ""
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def long_date(mm, dd, yyyy):
    return f"{MONTHS[int(mm) - 1]} {int(dd)}, {yyyy}"


def today():
    return dt.date.today().isoformat()


def age_days(day):
    try:
        return (dt.date.today() - dt.date.fromisoformat(day)).days
    except (TypeError, ValueError):
        return 10 ** 6


def write_json(path, doc):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".part", "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=1)
    os.replace(path + ".part", path)


def read_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


# ---------------------------------------------------------------- text of a PDF, cell by cell

def runs_of(pdf, page, res, depth_limit=6):
    """Every text run of a page in the order the page draws it: (x, y, size, text, x_end, fresh). ballot/pdftext.py
    reads a page's own content stream; several county lists draw each page inside a form, so this follows forms too.
    fresh is True for the first run after the page positions the text anew."""
    runs = []

    def walk(data, res, ctm, depth):
        fonts = {}
        rdict = pdf.get(res) or {}
        fres = pdf.get(rdict.get("Font")) or {}
        xres = pdf.get(rdict.get("XObject")) or {}
        saved = []
        tm = tlm = [1, 0, 0, 1, 0, 0]
        font, size, tc, tw, th, tl, rise = None, 1.0, 0.0, 0.0, 1.0, 0.0, 0.0
        fresh = True

        def show(s):
            nonlocal tm, fresh
            if font is None:
                return
            text, codes = font.decode(s if isinstance(s, (bytes, bytearray)) else b"")
            trm = _mul([size * th, 0, 0, size, 0, rise], _mul(tm, ctm))
            adv = 0.0
            for code in codes:
                adv += (font.width(code) * size + tc + (tw if (not font.two and code == 32) else 0)) * th
            x0, y0 = trm[4], trm[5]
            tm = _mul([1, 0, 0, 1, adv, 0], tm)
            x1 = _mul([size * th, 0, 0, size, 0, rise], _mul(tm, ctm))[4]
            if text.strip():
                runs.append((x0, y0, abs(trm[3]) or size, text, x1, fresh))
            fresh = False

        for op, a in _ops(data):
            if op == "q":
                saved.append((ctm[:], font, size, tc, tw, th, tl, rise))
            elif op == "Q":
                if saved:
                    ctm, font, size, tc, tw, th, tl, rise = saved.pop()
            elif op == "cm" and len(a) == 6:
                ctm = _mul([float(x) for x in a], ctm)
            elif op == "BT":
                tm = tlm = [1, 0, 0, 1, 0, 0]
                fresh = True
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
                tx, ty = float(a[0]), float(a[1])
                if op == "TD":
                    tl = -ty
                tlm = _mul([1, 0, 0, 1, tx, ty], tlm)
                tm = tlm
                fresh = True
            elif op == "Tm" and len(a) == 6:
                tm = tlm = [float(x) for x in a]
                fresh = True
            elif op == "T*":
                tlm = _mul([1, 0, 0, 1, 0, -tl], tlm)
                tm = tlm
                fresh = True
            elif op == "Tj" and a:
                show(a[-1])
            elif op in ("'", '"') and a:
                tlm = _mul([1, 0, 0, 1, 0, -tl], tlm)
                tm = tlm
                fresh = True
                if op == '"' and len(a) == 3:
                    tw, tc = float(a[0]), float(a[1])
                show(a[-1])
            elif op == "TJ" and a and isinstance(a[-1], list):
                for item in a[-1]:
                    if isinstance(item, (bytes, bytearray)):
                        show(item)
                    elif isinstance(item, (int, float)):
                        tm = _mul([1, 0, 0, 1, -float(item) / 1000.0 * size * th, 0], tm)
            elif op == "Do" and a and depth < depth_limit:
                ref = xres.get(str(a[0]))
                form = pdf.get(ref)
                if isinstance(form, dict) and form.get("Subtype") == "Form" and isinstance(ref, Ref):
                    m = pdf.get(form.get("Matrix"))
                    inner = _mul([float(pdf.get(x)) for x in m], ctm) if isinstance(m, list) and len(m) == 6 else ctm[:]
                    walk(pdf.stream(ref) or b"", form.get("Resources") or res, inner, depth + 1)

    contents = pdf.get(page.get("Contents"))
    parts = contents if isinstance(contents, list) else [page.get("Contents")]
    data = b"\n".join(pdf.stream(p) or b"" for p in parts if isinstance(p, Ref))
    walk(data, res, [1, 0, 0, 1, 0, 0], 0)
    return runs


def cells_of(runs, anchors=(), tol=1.0):
    """Cells in the order the page draws them. A new cell starts on a new baseline, after a gap wider than 0.6 of the
    type size, after a jump back, or when a freshly positioned run begins at a column's own left edge (so a long name
    never runs on into the column beside it)."""
    out, cur = [], None
    for x0, y, size, text, x1, fresh in runs:
        gap = (x0 - cur["x1"]) / max(size, 1.0) if cur else 0.0
        at_anchor = fresh and any(abs(x0 - a) <= tol for a in anchors)
        if (cur and abs(y - cur["y"]) <= 0.6 and abs(size - cur["size"]) < 0.05 and -0.15 <= gap <= 0.6
                and not (at_anchor and x0 - cur["x"] > 2)):
            if gap > 0.18 and not cur["text"].endswith(" ") and not text.startswith(" "):
                cur["text"] += " "
            cur["text"] += text
            cur["x1"] = max(cur["x1"], x1)
        else:
            cur = {"x": x0, "y": y, "size": size, "text": text, "x1": x1}
            out.append(cur)
    for c in out:
        c["text"] = squeeze(c["text"])
    return [c for c in out if c["text"]]


def lines_of(cells, tol=2.0):
    """[(y, [cells left to right])], top to bottom."""
    out = []
    for c in sorted(cells, key=lambda c: (-c["y"], c["x"])):
        if out and abs(out[-1][0] - c["y"]) <= tol:
            out[-1][1].append(c)
        else:
            out.append([c["y"], [c]])
    for line in out:
        line[1].sort(key=lambda c: c["x"])
    return out


def pdf_lines(raw, anchors=()):
    """(page number, [(y, cells)]) for each page of a text PDF held in memory."""
    if raw[:5] != b"%PDF-":
        raise LayoutError("the file is not a PDF")
    pdf = pdftext.PDF(raw)
    pages = pdf.pages()
    if not pages:
        raise LayoutError("the PDF has no pages this reader can follow")
    for pn, (page, res) in enumerate(pages, 1):
        yield pn, lines_of(cells_of(runs_of(pdf, page, res), anchors))


# ---------------------------------------------------------------- what the county readers hand on

VOTE_FOR = re.compile(r"^Vote for not more than (\d+)$", re.I)
TERM_CELL = re.compile(r"^(?=.{1,70}$)(?:.*\b(?:Term|Terms|Year|Years)\b.*)$", re.I)
POSITION = re.compile(r"^(Non-?incumbent|Incumbent) Position$", re.I)
DATE = re.compile(r"^\d{1,2}/\d{1,2}/\d{2,4}$")
PARTY_MARK = re.compile(r"^(Dem|Rep|Lib|Ust|Grn|Nlp|Wc|Wcp|Npa|Np|Incumbent|Non-Incumbent)$", re.I)
NONE_FILED = re.compile(r"^no candidates?( have)? filed\b", re.I)
NAME_MARK = re.compile(r"\s*\((withdrew|withdrawn|disqualified|deceased|removed|incumbent|i|write-?in|w)\)", re.I)
NAME_PREFIX_MARK = re.compile(r"^(disqualified|withdrawn|withdrew)\s+\d{1,2}/\d{1,2}/\d{2,4}\s+(.+)$", re.I)
PROPOSALS = re.compile(r"^(proposal section|proposals?|state proposals?|county proposals?|proposal \d[\d-]*)$", re.I)
SECTIONS = {"STATE", "CONGRESSIONAL", "LEGISLATIVE", "STATE BOARDS", "COUNTY", "TOWNSHIP", "TOWNSHIPS", "JUDICIAL", "COMMUNITY COLLEGE", "CITY", "CITIES",
            "VILLAGE", "VILLAGES", "LOCAL SCHOOL DISTRICT", "LOCAL SCHOOL DISTRICTS", "SCHOOL DISTRICT", "SCHOOL DISTRICTS", "DISTRICT LIBRARY",
            "DISTRICT LIBRARIES", "LIBRARY DISTRICT", "LIBRARY DISTRICTS", "PARTISAN SECTION", "NONPARTISAN SECTION", "NON-PARTISAN SECTION"}
FURNITURE = re.compile(r"^(Updated\b|November 2026 General Election$|November 3, 2026 General Election$|Page \d+ of \d+$|\(Continued on next page\)$)", re.I)
JUDGE_MARK = re.compile(r"^(Justice|Judge) of\b", re.I)
ELECTION_WORDS = re.compile(r"\bNovember\s+(?:3,\s*)?2026\b", re.I)      # a list must say which election it is for: an address can be used again


def new_doc(title="", updated=""):
    return {"title": title, "updated": updated, "election": False, "contests": [], "counts": collections.Counter()}


def published_day(text):
    """'Updated 9/25/2026 12:37 PM' -> '2026-09-25': the day a list says it was last changed, or '' when it does not say."""
    m = re.search(r"(?<!\d)(\d{1,2})/(\d{1,2})/(\d{4})", text or "")
    if not m:
        return ""
    mm, dd, yyyy = (int(x) for x in m.groups())
    return f"{yyyy:04d}-{mm:02d}-{dd:02d}" if 1 <= mm <= 12 and 1 <= dd <= 31 and yyyy == 2026 else ""


def new_contest(doc, title, *, jur=None, section=None, term=None, vote=None, pos=None, sub=None, page=None):
    c = {"title": squeeze(title), "jur": squeeze(jur) or None, "section": squeeze(section) or None, "term": squeeze(term) or None, "vote": vote,
         "pos": squeeze(pos) or None, "sub": squeeze(sub) or None, "page": page, "cands": [], "none": False}
    doc["contests"].append(c)
    return c


def add_candidate(doc, contest, name, party="", mark=""):
    """One candidate row, three cells: the name, the party cell and the status mark. A cell that reads like contact
    details is blanked and counted (a free-text cell can hold what belongs in another column); it is never printed."""
    doc["counts"]["rows"] += 1
    name, party, mark = squeeze(name), squeeze(party), squeeze(mark)
    if NONE_FILED.match(name):
        contest["none"] = True
        doc["counts"]["no candidate filed"] += 1
        return
    m = NAME_PREFIX_MARK.match(name)                                  # Ingham: "DISQUALIFIED 7/15/26 First Last"
    if m:
        mark, name = mark or m.group(1).lower(), squeeze(m.group(2))
    for m in NAME_MARK.finditer(name):                                # Macomb "(Withdrew)", Oakland "(Write-in)" and "(Incumbent)", Saginaw "(I)", Muskegon "(W)"
        word = m.group(1).lower()
        if word in ("incumbent", "i"):
            continue
        mark = mark or ("marked w" if word == "w" else "write-in" if word.startswith("write") else word)
    name = squeeze(NAME_MARK.sub(" ", name))
    if not name or re.search(r"\d", name) or reads_like_contact(name) or len(name) > 60:
        doc["counts"]["name cells blanked"] += 1
        return
    if party and (reads_like_contact(party) or len(party) > 30 or re.search(r"\d", party)):
        doc["counts"]["party cells blanked"] += 1
        party = ""
    if mark and not DATE.match(mark) and (reads_like_contact(mark) or len(mark) > 30 or not re.fullmatch(r"[A-Za-z /-]+", mark)):
        doc["counts"]["status cells blanked"] += 1
        mark = "unreadable"
    contest["cands"].append([name, party, mark])


def kept_text(doc, text, what, limit=160):
    """An office or jurisdiction heading, kept only if it does not read like contact details."""
    text = squeeze(text)
    if reads_like_contact(text) or len(text) > limit:
        doc["counts"][f"{what} blanked"] += 1
        raise LayoutError(f"a {what} reads like contact details or is too long")
    return text


# ---------------------------------------------------------------- reader: the "Vote for not more than" reports
# Oakland, Kent, Muskegon and Saginaw publish the same kind of report: a line for the office with "Vote for not more
# than N" and the term, then a row per candidate (party mark at the left edge, then the name, then address, city, ZIP,
# sometimes telephone and e-mail, the filing method and date, and a withdrawal column). Read: the left cell, the name
# cell and the right-most status cell of a candidate row; every cell of a heading line that is an office, a "Vote for"
# count, a term or an incumbent mark. The columns between the name and the status column are never read.

def read_vote_for(raw, spec):
    doc = new_doc()
    left_x, name_x, wd_x = spec["left_x"], spec["name_x"], spec["wd_x"]
    section = jur = cur = None
    titles = []
    for pn, lines in pdf_lines(raw, spec["anchors"]):
        if pn > spec.get("last_page", 10 ** 6):
            break
        for _y, line in lines:
            if len(line) == 1 and PROPOSALS.match(line[0]["text"]):
                doc["counts"]["pages read"] = pn
                return finish(doc, titles)
            left = next((c for c in line if abs(c["x"] - left_x) <= 3), None)
            name = next((c for c in line if abs(c["x"] - name_x) <= 2.5), None)
            if left and FURNITURE.match(left["text"]):
                if left["text"].lower().startswith("updated"):
                    doc["updated"] = doc["updated"] or kept_text(doc, left["text"], "page heading", 60)
                doc["election"] = doc["election"] or bool(ELECTION_WORDS.search(left["text"]))
                continue
            if name:
                if cur is None:
                    raise LayoutError(f"page {pn}: a candidate row before any contest heading")
                status = next((c["text"] for c in line if c["x"] >= wd_x - 8), "")
                add_candidate(doc, cur, name["text"], left["text"] if left else "", status)
                continue
            vote = term = pos = None
            unread = 0
            for c in line:
                if c is left:
                    continue
                m = VOTE_FOR.match(c["text"])
                if m:
                    vote = int(m.group(1))
                elif POSITION.match(c["text"]):
                    pos = c["text"]
                elif TERM_CELL.match(c["text"]) and not reads_like_contact(c["text"]):
                    term = c["text"]
                else:
                    unread += 1
            if left and PARTY_MARK.match(left["text"]) and not vote and not term:
                doc["counts"]["party lines with no candidate"] += 1       # a party's line in a partisan contest nobody of that party filed for
                continue
            if left and (vote or term):
                cur = new_contest(doc, kept_text(doc, left["text"], "office heading"), jur=jur, section=section, term=term, vote=vote, pos=pos, page=pn)
                if unread:
                    doc["counts"]["heading cells not read"] += unread
            elif left and len(line) == 1:
                text = kept_text(doc, left["text"], "heading")
                if text.upper() in SECTIONS:
                    section, jur = text, None
                else:
                    jur = text
                cur = None
            elif vote and not left and cur is not None and cur["vote"] is None and not cur["cands"]:
                cur["vote"] = vote                                       # Kent prints the count on a line of its own under the office
            elif not left and len(line) == 1 and line[0]["x"] > left_x + 100:
                titles.append(line[0]["text"])                           # a centred line: the report's own title lines
            elif left:
                doc["counts"]["lines not understood"] += 1
    doc["counts"]["pages read"] = pn
    return finish(doc, titles)


def finish(doc, titles):
    seen = []
    for t in titles:
        doc["election"] = doc["election"] or bool(len(t) <= 80 and ELECTION_WORDS.search(t))
        if t not in seen and not reads_like_contact(t) and len(t) <= 60 and not FURNITURE.match(t):
            seen.append(t)
    doc["title"] = doc["title"] or "; ".join(seen[:3])
    return doc


# ---------------------------------------------------------------- reader: Wayne County
# One PDF: a centred heading per contest ("MAYOR - CITY OF ECORSE - 2 YEAR TERM (1) POSITION"), then a row per
# candidate under the column headings PARTY, CANDIDATE, ADDRESS, CITY, STATE, ZIP, FILING DATE, METHOD, WITHDRAWAL
# DATE. Read: the heading, the party cell (left of x=100), the candidate cell (which starts at x=112 and ends before
# x=280) and the withdrawal cell (right of x=815). The address, city, state, ZIP, date and method cells are never read.

WAYNE_HEAD = re.compile(r"^(?P<body>.+?)\s*\((?P<n>\d+)\)\s*POSITIONS?$")
WAYNE_TERM = re.compile(r"^(?:\d+ YEAR TERMS?|PARTIAL TERM\b.*|TERM ENDING\b.*)$", re.I)


def read_wayne(raw, spec):
    doc = new_doc()
    items = []                                                        # ("head", page, text) and ("row", page, y, name, party, status), in the list's order
    for pn, lines in pdf_lines(raw, (23.0, 33.0, 112.0, 280.0)):
        for y, line in lines:
            size = line[0]["size"]
            if abs(size - 15.0) < 0.2:                                # the page's own heading: the clerk's office, the election, "Official Candidate List"
                doc["title"] = doc["title"] or kept_text(doc, "; ".join(c["text"] for c in line), "page heading", 160)
                continue
            if abs(size - 13.0) > 0.2:                                # the day and time the list was printed, the page number
                if len(line) == 1 and DATE.match(line[0]["text"]):
                    doc["updated"] = doc["updated"] or line[0]["text"]
                continue
            texts = [c["text"] for c in line]
            name = next((c for c in line if 105 <= c["x"] <= 130), None)
            if not name and any(t in ("PARTY", "CANDIDATE", "PARTY CANDIDATE", "WITHDRAWAL", "DATE") for t in texts):
                continue                                              # the column headings
            party = next((c for c in line if c["x"] < 100), None)
            if name or party:
                if name and name["x1"] > 279:
                    doc["counts"]["name cells that reach the next column"] += 1
                status = next((c["text"] for c in line if c["x"] >= 815), "")
                items.append(["row", pn, y, name["text"] if name else None, party["text"] if party else None, status])
                continue
            if line[0]["x"] < 140:
                raise LayoutError(f"page {pn}: a line that is neither a heading nor a candidate row")
            items.append(["head", pn, squeeze(" ".join(texts))])
    # a row whose name sits a little above or below the rest of its cells comes as two lines: put them back together
    for i, it in enumerate(items):
        if it[0] == "row" and it[3] and it[4] is None:
            for j in (i - 1, i + 1):
                if 0 <= j < len(items) and items[j][0] == "row" and items[j][3] is None and items[j][1] == it[1] and abs(items[j][2] - it[2]) <= 9:
                    it[4], it[5] = items[j][4], it[5] or items[j][5]
                    items[j][0] = "used"
                    break
    cur, last_head = None, None
    for it in items:
        if it[0] == "head":
            if it[2] == last_head and cur is not None:
                continue                                              # the same heading again at the top of a page: the contest goes on
            m = WAYNE_HEAD.match(it[2])
            if not m:
                raise LayoutError(f"page {it[1]}: a centred line that is not a contest heading")
            parts = [p.strip() for p in re.split(r"\s+-\s+|(?<=INCUMBENT)-\s+", m.group("body")) if p.strip()]
            terms = [p for p in parts if WAYNE_TERM.match(p)]
            rest = [p for p in parts if not WAYNE_TERM.match(p)]
            if not rest:
                raise LayoutError(f"page {it[1]}: a contest heading with no office")
            last_head = it[2]
            cur = new_contest(doc, kept_text(doc, rest[0], "office heading"), jur=kept_text(doc, rest[1], "heading") if len(rest) > 1 else None,
                              sub=kept_text(doc, " - ".join(rest[2:]), "heading") if len(rest) > 2 else None,
                              term=kept_text(doc, "; ".join(terms), "term") if terms else None, vote=int(m.group("n")), page=it[1])
        elif it[0] == "row":
            if cur is None:
                raise LayoutError(f"page {it[1]}: a candidate row before any contest heading")
            if not it[3]:
                doc["counts"]["rows with no name cell"] += 1
                continue
            add_candidate(doc, cur, it[3], it[4] or "", it[5])
    return doc


# ---------------------------------------------------------------- reader: Macomb County
# A published sheet, read as CSV, six cells a row: OFFICE AND CANDIDATES, PARTY, ADDRESS, CITY/TWP, a state cell and a
# ZIP cell. A heading row has dots in the fifth cell (the sheet's colour key); an office under a city, village or
# township has its term in the third cell. Read: the first two cells of a candidate row; the first, third (only when it
# is a term) and fourth (only "Files With ...") cells of a heading row. The address, city, state and ZIP cells of a
# candidate row are never read.

MACOMB_TERM = re.compile(r"^(One|Two|Three|Four|Five|Six|Seven|Eight|Nine) (\d+-year|partial) terms?\b[^@]{0,40}$", re.I)


def read_macomb(raw, spec):
    doc = new_doc()
    rows = list(csv.reader(io.StringIO(raw.decode("utf-8-sig", "replace"))))
    if not rows or any(len(r) != 6 for r in rows):
        raise LayoutError("the sheet no longer has six cells a row")
    started = False
    section = jur = cur = None
    for n, r in enumerate(rows, 1):
        c = [squeeze(x) for x in r]
        if not any(c):
            continue
        if c[0].upper().startswith("OFFICIAL CANDIDATE LIST"):
            doc["title"] = kept_text(doc, c[0], "page heading", 120)
            continue
        if c[0].upper() in ("PARTISAN SECTION", "NONPARTISAN SECTION"):
            started, section, jur, cur = True, c[0], None, None
            continue
        if not started or c[1] == "PARTY":
            continue
        dots = bool(re.fullmatch(r"[.]+", c[4]))
        if c[0] and not c[1] and not c[5] and dots:
            title = kept_text(doc, c[0], "office heading")
            m = re.match(r"^(.*?)\s*\(([^()]*)\)\s*$", title)
            if m:
                files = c[3] if re.fullmatch(r"(Files With )?[A-Za-z. ]+ County|Files With State", c[3]) else None
                cur = new_contest(doc, m.group(1), jur=None, section=section, term=m.group(2), page=n, sub=files)
                jur = None
            else:
                jur, cur = title, None
            continue
        if c[0] and not c[1] and MACOMB_TERM.match(c[2]) and not c[3] and not c[4] and not c[5]:
            if not jur:
                raise LayoutError(f"row {n}: an office with no city, village or township above it")
            cur = new_contest(doc, kept_text(doc, c[0], "office heading"), jur=jur, section=section, term=c[2], page=n)
            continue
        if c[0] and not any(c[1:]) and JUDGE_MARK.match(c[0]):
            continue                                                  # the words the ballot prints under a sitting judge's name
        if not c[0]:
            doc["counts"]["rows with no name cell"] += 1
            continue
        if cur is None:
            raise LayoutError(f"row {n}: a candidate row before any contest heading")
        add_candidate(doc, cur, c[0], c[1], "")
    if not started:
        raise LayoutError("the sheet has no PARTISAN SECTION row")
    return doc


# ---------------------------------------------------------------- reader: Kalamazoo County
# One PDF laid out as a table: the office, "Vote for not more than", the term, the party, the first name and the last
# name, then address, city, state, ZIP, e-mail, telephone, filing date and method. Read: the six cells at the left
# (found by where each column starts). Nothing from the address column on is read.

KZOO = (20.0, 142.0, 182.0, 295.0, 355.0, 411.0)


def read_kalamazoo(raw, spec):
    doc = new_doc()
    section = jur = cur = None
    last_office = None
    for pn, lines in pdf_lines(raw, KZOO + (465.0, 575.0, 622.0, 661.0, 709.0, 800.0, 834.0, 866.0)):
        for _y, line in lines:
            if len(line) == 1 and line[0]["x"] > 150 and PROPOSALS.match(line[0]["text"]):
                return doc
            col = {}
            for c in line:
                for a in KZOO:
                    if abs(c["x"] - a) <= 3:
                        col[a] = c["text"]
            if not col:
                if len(line) == 1 and line[0]["x"] > 150 and not doc["title"] and re.search(r"General Election", line[0]["text"]):
                    doc["title"] = kept_text(doc, line[0]["text"], "page heading", 80)
                continue
            office, vote, term, party, first, last = (col.get(a, "") for a in KZOO)
            if office and FURNITURE.match(office):
                if office.lower().startswith("updated"):
                    doc["updated"] = doc["updated"] or kept_text(doc, office, "page heading", 60)
                continue
            if cur is None and section is None and jur is None and not (office and office.upper() in SECTIONS):
                continue                                              # the notes above the first section
            heads = bool(office or term or (vote and vote.isdigit()))
            if office.upper() in SECTIONS and not first and not last:
                section, jur, cur, last_office = kept_text(doc, office, "heading"), None, None, None      # a section's line can carry stray cells of the row under it
                continue
            if heads and office.lower() != "resigned":
                if office and not vote and not term and not first and not last:
                    text = kept_text(doc, office, "heading")
                    if len(line) > 1:
                        doc["counts"]["lines not understood"] += 1
                        continue
                    if text.upper() in SECTIONS:
                        section, jur = text, None
                    else:
                        jur = text
                    cur = last_office = None
                    continue
                if not office and not last_office:
                    raise LayoutError(f"page {pn}: a term with no office above it")
                last_office = kept_text(doc, office, "office heading") if office else last_office
                if vote and not vote.isdigit():
                    raise LayoutError(f"page {pn}: a contest whose vote-for cell is not a number")
                if not (TERM_CELL.match(term) or re.fullmatch(r"\d+ [Yy]ears?", term)) and term:
                    raise LayoutError(f"page {pn}: a contest whose term cell is not a term")
                cur = new_contest(doc, last_office, jur=jur, section=section, term=term or None, vote=int(vote) if vote else None, page=pn)
            if first and last:
                if cur is None:
                    raise LayoutError(f"page {pn}: a candidate row before any contest heading")
                mark = "resigned" if office.lower() == "resigned" else ""
                add_candidate(doc, cur, f"{first} {last}", party if not PARTY_MARK.match(vote or "") else (party or vote), mark)
            elif first and not last:
                if JUDGE_MARK.match(first):
                    continue                                          # the words the ballot prints under a sitting judge's name
                doc["counts"]["rows with no last-name cell"] += 1
    return doc


# ---------------------------------------------------------------- reader: Ottawa County
# One PDF, a table under the headings Jurisdiction, Office, District, Party, Term, Positions, Incumbent, First Name,
# Last Name, Address, ..., Filing Date, Filing Method (cells centred under their headings). Read: the cells centred
# under the first nine headings, the Incumbent one only to know a row is a candidate's. Nothing from Address on is read.

OTTAWA_COLS = ("Jurisdiction", "Office", "District", "Party", "Term", "Positions", "Incumbent", "First Name", "Last Name")


def read_ottawa(raw, spec):
    doc = new_doc()
    by_key = {}
    for pn, lines in pdf_lines(raw):
        edges, limit = None, None
        for _y, line in lines:
            texts = [c["text"] for c in line]
            if "Jurisdiction" in texts and "Office" in texts:
                mids = sorted(((c["x"] + c["x1"]) / 2, c["text"]) for c in line)
                edges = []
                for i, (mid, text) in enumerate(mids):
                    lo = (mids[i - 1][0] + mid) / 2 if i else 0.0
                    hi = (mid + mids[i + 1][0]) / 2 if i + 1 < len(mids) else 10 ** 6
                    edges.append((text, lo, hi))
                limit = max((hi for text, lo, hi in edges if text in OTTAWA_COLS), default=0)
                if not all(any(t == want for t, _lo, _hi in edges) for want in OTTAWA_COLS[:6]):
                    raise LayoutError(f"page {pn}: the table's headings are not the ones this reader knows")
                continue
            if not edges:
                if len(line) == 1 and line[0]["x"] > 150 and re.search(r"General Election$|Candidate Listing$", line[0]["text"]) and len(doc["title"]) < 80:
                    doc["title"] = squeeze(doc["title"] + "; " + kept_text(doc, line[0]["text"], "page heading", 80)).strip("; ")
                continue
            row = {}
            for c in line:
                mid = (c["x"] + c["x1"]) / 2
                if mid >= limit:
                    continue                                          # the address column and everything right of it
                for text, lo, hi in edges:
                    if lo <= mid < hi and text in OTTAWA_COLS:
                        row[text] = squeeze(row.get(text, "") + " " + c["text"])
            if not row.get("Office") or not row.get("Jurisdiction"):
                continue
            district = row.get("District", "")
            if re.fullmatch(r"at[- ]large|statewide", district, re.I):
                district = ""                                         # the whole jurisdiction votes: no district to name
            # the table of offices on the first pages and the table of candidates word a contest alike but for capitals and hyphens
            m = re.match(r"(\d+) positions?$", row.get("Positions", ""), re.I)
            key = tuple(fold(x) for x in (row["Jurisdiction"], row["Office"], district, row.get("Term", ""))) + (m.group(1) if m else "",)
            cur = by_key.get(key)
            if cur is None:
                cur = by_key[key] = new_contest(doc, kept_text(doc, row["Office"], "office heading"), jur=kept_text(doc, row["Jurisdiction"], "heading"),
                                                 sub=kept_text(doc, district, "heading") or None, term=row.get("Term") or None,
                                                 vote=int(m.group(1)) if m else None, pos=row.get("Party") or None, page=pn)
            if row.get("First Name") or row.get("Last Name"):
                if not (row.get("First Name") and row.get("Last Name")):
                    doc["counts"]["rows with one name cell"] += 1
                add_candidate(doc, cur, squeeze(row.get("First Name", "") + " " + row.get("Last Name", "")), row.get("Party", ""), "")
    if not doc["contests"]:
        raise LayoutError("no table with the headings Jurisdiction and Office was found")
    return doc


# ---------------------------------------------------------------- reader: Ingham County
# One PDF: a centred heading per contest ("DANSVILLE SCHOOL BOARD - 6 YEAR TERM - VOTE FOR NOT MORE THAN 3"), then a
# row per candidate under CANDIDATE NAME, STREET ADDRESS, CITY, STATE, ZIP, PARTY AFFILIATION, PHONE, EMAIL. Read: the
# heading, the name cell (the cell that starts left of x=205) and the party cell (the cell that starts between x=440
# and x=500). The address, city, state, ZIP, telephone and e-mail cells are never read.

INGHAM_HEAD = re.compile(r"^(?P<body>.+?)\s*-\s*VOTE FOR NOT MORE THAN (?P<n>\d+)\b(?P<tail>.*)$")


def read_ingham(raw, spec):
    doc = new_doc()
    by_title = {}
    cur = section = None
    for pn, lines in pdf_lines(raw):
        for _y, line in lines:
            first = line[0]
            if len(line) == 1:
                text = first["text"]
                m = INGHAM_HEAD.match(text)
                if m:
                    text = kept_text(doc, text, "office heading", 220)
                    parts = [p.strip() for p in re.split(r"\s+-\s*", m.group("body")) if p.strip()]
                    recall = parts[0].upper() == "RECALL ELECTION"
                    parts = parts[1:] if recall else parts
                    key = text.upper()
                    cur = by_title.get(key)
                    if cur is None:
                        tail = squeeze(m.group("tail")).strip("() ")
                        cur = by_title[key] = new_contest(doc, parts[0], section=section, term="; ".join(parts[1:] + ([tail] if tail else [])) or None,
                                                           vote=int(m.group("n")), pos="Recall election" if recall else None, page=pn)
                elif first["size"] > 11 and "Ballot" in text:
                    section, cur = kept_text(doc, text, "heading"), None
                elif first["size"] > 12.5 and not reads_like_contact(text) and len(doc["title"]) < 70:
                    doc["title"] = squeeze(doc["title"] + "; " + text).strip("; ")
                elif text.startswith("Revised:"):
                    doc["updated"] = doc["updated"] or kept_text(doc, text, "page heading", 60)
                elif first["x"] < 205 and first["x1"] < 230 and not FURNITURE.match(text):
                    doc["counts"]["one-cell lines at the left, not read"] += 1
                continue
            name = next((c for c in line if c["x"] < 205), None)
            if not name or name["text"].upper() == "CANDIDATE NAME":
                continue
            if cur is None:
                raise LayoutError(f"page {pn}: a candidate row before any contest heading")
            party = next((c["text"] for c in line if 440 <= c["x"] < 500), "")
            add_candidate(doc, cur, name["text"], party, "")
    if not doc["contests"]:
        raise LayoutError("no contest heading was found")
    return doc


# ---------------------------------------------------------------- the county lists: where each is, and how it is read
# By population (2020 census), largest first. Each address was read by hand on the clerk's own page, named in "page".

COUNTIES = [
    dict(code="wayne", fips="26163", name="Wayne County", agency="Wayne County Clerk, Elections Division", reader=read_wayne,
         url="https://www.waynecountymi.gov/files/assets/mainsite/v/1/clerk/documents/elections/official-candidate-list_november-3-2026.pdf",
         page="https://www.waynecountymi.gov/Government/Elected-Officials/Clerk/Elections/Election-Results-Candidates/November-3rd-2026-General-Election",
         label="Official Candidate List, November 3, 2026 General Election",
         read="the contest heading, the party cell, the candidate cell and the withdrawal cell", never="address, city, state, ZIP, filing date and method"),
    dict(code="oakland", fips="26125", name="Oakland County", agency="Oakland County Clerk/Register of Deeds, Elections Division", reader=read_vote_for,
         url="https://cdn.oaklandcountymi.gov/oakland-sitefinity-prod/docs/default-source/clerk/clerk-elections/elections-voting/11032026-candidate-list.pdf",
         page="https://elections.oaklandcountymi.gov/government/clerk-register-of-deeds/elections-voting",
         label="Official Candidate List, November 3, 2026 General Election", left_x=20.0, name_x=46.0, wd_x=912.0, anchors=(20.0, 46.0, 232.5, 500.0, 747.0, 856.0, 912.0),
         read="the office and jurisdiction headings, the party mark, the name cell and the withdrawal cell", never="address, city, filing method and date"),
    dict(code="macomb", fips="26099", name="Macomb County", agency="Macomb County Clerk / Register of Deeds, Elections Department", reader=read_macomb,
         url="https://docs.google.com/spreadsheets/d/e/2PACX-1vQ9JgxHZKKd6iz_O--ApmW-mlfT7j31dVCK0FSeyI_A1VoqW93sPJl8K4Ti7xXqV7WYTHyhKYe3oHhi/pub?output=csv",
         page="https://www.macombgov.org/departments/clerk-register-deeds/elections",
         label="Official Candidate List for November 2026 Election (the clerk's published sheet, read as CSV)",
         read="the first two cells of each row (office or candidate, and party) and the term beside an office", never="address, city or township, state and ZIP"),
    dict(code="kent", fips="26081", name="Kent County", agency="Kent County Clerk, Elections", reader=read_vote_for,
         url="https://www.accesskent.com/DocumentCenter/View/8870", page="https://www.accesskent.com/Departments/Elections/",
         label="Official Candidates and Proposals List, November 3, 2026 General Election", left_x=66.0, name_x=101.0, wd_x=675.0,
         anchors=(66.0, 101.0, 133.0, 220.0, 343.0, 401.0, 421.0, 444.0, 638.0, 675.0),
         read="the office and jurisdiction headings, the party mark, the name cell and the status cell (Withdrew, Disqualified, Qualified Write-In)",
         never="address, city, state, ZIP, telephone, filing method and date; the proposals' pages are not read"),
    dict(code="genesee", fips="26049", name="Genesee County", agency="Genesee County Clerk, Election Division", reader=None,
         page="https://www.geneseecountymi.gov/departments/county_clerk/election_division.php",
         saved="genesee_2026_november_candidate_list.pdf",
         why="The Genesee County Clerk's election page posts an August 2026 candidate list but no November list; for November it sends readers to the state's "
             "ballot preview, which shows one precinct at a time and turns scripts away."),
    dict(code="washtenaw", fips="26161", name="Washtenaw County", agency="Washtenaw County Clerk/Register of Deeds, Elections Division", reader=None,
         page="https://www.washtenaw.org/current-election-information", saved="washtenaw_2026_general_candidates.pdf",
         why="The Washtenaw County Clerk's Current Election Information page fills in its links by script after it opens, so a plain download does not see "
             "where the November candidate list is; a person's browser does."),
    dict(code="ottawa", fips="26139", name="Ottawa County", agency="Ottawa County Clerk/Register of Deeds, Elections Division", reader=read_ottawa,
         url="https://app.miottawa.org/ElectionManagement/viewPublicFile.action?viewFile=%2Fmnt%2Fottawa-apps%2Fcontent%2FappImages%2FElectionManagement%2FcandidateFile-226.pdf",
         page="https://miottawa.org/clerk/elections/",
         label="Unofficial Candidate Listing, 2026 Election Cycle: November 3, 2026 General Election",
         read="the cells under Jurisdiction, Office, District, Party, Term, Positions, First Name and Last Name", never="address, filing date and method",
         extra="The clerk's elections page answers scripts with a refusal (403), so this file's address was found through a search index of the county's own file "
               "server, which answers plain requests; the loader goes on only if the file's own heading names the November 3, 2026 election."),
    dict(code="ingham", fips="26065", name="Ingham County", agency="Ingham County Clerk", reader=read_ingham,
         url="https://www.dropbox.com/scl/fi/5b4627tqe8txa3n6x8jxs/Ingham-November-Candidate-List-2026.pdf?rlkey=c667w1wrw04pglk94aoxujrws&st=oj9qryxa&dl=1",
         page="https://clerk.ingham.org/departments_and_officials/county_clerk/candidates.php",
         label="Candidate List, November 3, 2026 General Election",
         read="the contest heading, the candidate name cell and the party cell", never="street address, city, state, ZIP, telephone and e-mail",
         whole_ballot=False,
         extra="The list covers offices that file with the county clerk or a city or township clerk in the county; the clerk posts the file on a file-sharing host."),
    dict(code="kalamazoo", fips="26077", name="Kalamazoo County", agency="Kalamazoo County Clerk/Register of Deeds, Elections", reader=read_kalamazoo,
         url="https://www.kalcounty.gov/DocumentCenter/View/6469", page="https://www.kalcounty.gov/447/Elections-Voting",
         label="Official Candidate and Proposals list, November 3, 2026 General Election",
         read="the office, vote-for, term, party, first name and last name cells", never="address, city, state, ZIP, e-mail, telephone, filing date and method"),
    dict(code="livingston", fips="26093", name="Livingston County", agency="Livingston County Clerk, Elections", reader=None,
         page="https://milivcounty.gov/elections/upcoming-elections/", saved="Candidate-Filings-November-2026.pdf",
         why="The Livingston County Clerk posts a list of November 2026 candidate filings, but the county's site answers scripts with a refusal (403), for the "
             "page and for the file alike."),
    dict(code="saginaw", fips="26145", name="Saginaw County", agency="Saginaw County Clerk, Elections Division", reader=read_vote_for,
         url="https://saginawcounty.com/media/pz0jrngr/unofficial-saginaw-county-november-2026-candidate-list.pdf",
         page="https://saginawcounty.com/departments/county-clerk/elections/2026-november-general-election/",
         label="Unofficial Candidate & Proposal Listing, November 3, 2026 General Election", left_x=17.0, name_x=42.0, wd_x=691.0,
         anchors=(17.0, 42.0, 183.0, 365.0, 416.0, 578.0, 645.0, 691.0),
         read="the office and jurisdiction headings, the party mark, the name cell and the withdrawal cell", never="address, ZIP, e-mail, filing method and date; "
              "the proposals' pages are not read"),
    dict(code="muskegon", fips="26121", name="Muskegon County", agency="Muskegon County Clerk, Elections Division", reader=read_vote_for,
         url="https://co.muskegon.mi.us/DocumentCenter/View/21864/November-Unofficial-Candidate-List---for-website",
         page="https://co.muskegon.mi.us/502/Election-Information",
         label="Unofficial Candidate List, November 3, 2026 General Election", left_x=15.0, name_x=46.0, wd_x=729.0,
         anchors=(15.0, 46.0, 192.0, 367.0, 382.0, 384.0, 472.0, 616.0, 683.0, 729.0),
         read="the office and jurisdiction headings, the party mark, the name cell and the withdrawal cell", never="address, ZIP, e-mail, filing method and date"),
]


def saved_copy(spec, folder):
    """A county's list saved by hand in ballot_cache/mi/local/<county>/ (for a site that turns scripts away): the file
    the table names, else the only file in that folder. None when there is no such file."""
    here = os.path.join(folder, spec["code"])
    named = os.path.join(here, spec.get("saved") or os.path.basename(urllib.parse.urlparse(spec.get("url", "")).path) or "list")
    if os.path.isfile(named):
        return named
    files = [os.path.join(here, f) for f in (os.listdir(here) if os.path.isdir(here) else []) if os.path.isfile(os.path.join(here, f))]
    return files[0] if len(files) == 1 else None


def county_doc(spec, folder, say=print, refresh=False, fetch=True):
    """One county's list, cut down to the allowed cells. Returns (doc or None, why not). The cut-down copy on disk is
    used for three days. When the county's site does not answer, or answers with something that is not its November
    list, a copy saved by hand in the county's folder is read if it is there (and no older than the cut-down copy);
    else the cut-down copy is used again; else the county becomes a gap. The run always goes on."""
    path = os.path.join(folder, f"{spec['code']}_2026_general_list.json")
    old = read_json(path)
    if old and not refresh and (not fetch or age_days(old.get("fetched")) < LOCAL_MAX_AGE_DAYS):
        return old, None
    if not fetch:
        return None, "the list was not asked for on this run and no copy is on disk"

    def read(raw, where, day):
        doc = spec["reader"](raw, spec)
        if not (doc.get("election") or ELECTION_WORDS.search(doc.get("title") or "")):
            raise LayoutError("the file does not say it is the November 2026 list")
        if not doc["contests"]:
            raise LayoutError("no contest was found in the file")
        doc["counts"] = dict(doc["counts"])
        doc.update(code=spec["code"], url=spec["url"], fetched=day, sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw), how=where,
                   kept="office and jurisdiction headings, terms, vote-for counts, party cells, names and status marks; no other cell")
        return doc

    doc, why, short = None, None, None
    try:
        time.sleep(1.0)                                               # one request at a time, a second apart
        doc = read(net.get(spec["url"], timeout=180), "fetched", today())
    except LayoutError as err:
        why, short = f"the county's list no longer fits the reader written for it ({err})", f"the list no longer fits its reader ({err})"
    except Exception as err:  # noqa: BLE001  out of reach
        why, short = f"the county's list could not be fetched on this run ({type(err).__name__})", f"the list did not answer ({type(err).__name__})"
    if doc is None:
        saved = saved_copy(spec, folder)
        if saved and (not old or fetched(saved) >= (old.get("fetched") or "")):
            try:
                with open(saved, "rb") as fh:
                    doc = read(fh.read(), "saved by hand", fetched(saved))
                say(f"      {spec['name']}: {short}; reading the copy saved by hand on {doc['fetched']}")
            except Exception as err:  # noqa: BLE001  the page and the check are named, never the text
                say(f"      {spec['name']}: the copy saved by hand could not be read ({err if isinstance(err, LayoutError) else type(err).__name__})")
    if doc is None:
        if old:
            say(f"      {spec['name']}: {short}; using the copy of {old.get('fetched')} on disk")
            return old, None
        return None, why
    write_json(path, doc)
    return doc, None


# ---------------------------------------------------------------- official place lists

def census_counties(say=print):
    """{county name without 'County': (five-digit code, name with its kind word)} for Michigan, from the attribute
    table of the Census Bureau's county file the kit keeps (no shapes are read)."""
    if not os.path.exists(COUNTY_ZIP):
        net.download(COUNTY_URL, COUNTY_ZIP, 3650, say=say)
    import shapefile                                                  # pyshp
    z = zipfile.ZipFile(COUNTY_ZIP)
    dbf = [n for n in z.namelist() if n.lower().endswith(".dbf")]
    if len(dbf) != 1:
        raise SystemExit("Michigan: the Census county file does not hold exactly one attribute table")
    out = {}
    for rec in shapefile.Reader(dbf=io.BytesIO(z.read(dbf[0]))).iterRecords():
        d = rec.as_dict()
        if str(d.get("STATEFP")) == FIPS:
            out[str(d["NAME"])] = (str(d["GEOID"]), str(d["NAMELSAD"]))
    if len(out) != 83 or any(not re.fullmatch(FIPS + r"\d{3}", f) for f, _full in out.values()):
        raise SystemExit(f"Michigan: the Census county file gives {len(out)} counties for the state, not 83")
    return out


def county_key(name):
    """'St. Clair', 'ST. CLAIR', 'St Clair County' -> 'st clair'."""
    t = re.sub(r"\bcounty\b", " ", fold(name))
    return " ".join(re.sub(r"\bsaint\b", "st", t).split())


WORDS_SET_ASIDE = {"charter", "township", "twp", "city", "village", "of", "the"}


def bare(text):
    """A place's name for comparing only: kind words set aside, Saint and Mount written out ('CHARTER TOWNSHIP OF
    NORTHVILLE', 'Northville township' -> 'northville'; 'Mt. Clemens' -> 'mount clemens')."""
    t = fold(re.sub(r"\bSt\.?(?=\s)", "Saint", re.sub(r"\bMt\.?(?=\s)", "Mount", text or "", flags=re.I), flags=re.I))
    words = [w for w in t.split() if w not in WORDS_SET_ASIDE and not difflib.SequenceMatcher(None, w, "township").ratio() >= 0.8]
    return " ".join(words)


def census_places(folder, say=print, fetch=True):
    """Cities, townships and villages by the Census Bureau's 2020 codes: two plain code lists, kept whole (they carry
    names and codes only)."""
    paths = {"cousub": os.path.join(folder, "census_st26_mi_cousub2020.txt"), "place": os.path.join(folder, "census_st26_mi_place2020.txt")}
    for k, url in (("cousub", COUSUB_URL), ("place", PLACE_URL)):
        if fetch or not os.path.exists(paths[k]):
            net.download(url, paths[k], 3650, say=say)
    P = {"paths": paths, "township": {}, "city": {}, "village": {}, "name": {}, "counties": collections.defaultdict(set), "kind": {}}
    with open(paths["cousub"], encoding="utf-8", errors="replace") as fh:
        head = fh.readline().rstrip("\r\n").split("|")
        if head[:8] != ["STATE", "STATEFP", "COUNTYFP", "COUNTYNAME", "COUSUBFP", "COUSUBNS", "COUSUBNAME", "CLASSFP"]:
            raise SystemExit("Michigan: the Census county subdivision list's header is not the one this loader was checked against")
        for line in fh:
            f = line.rstrip("\r\n").split("|")
            if len(f) < 8 or f[1] != FIPS or f[7] not in ("T1", "C5"):
                continue
            kind = "township" if f[7] == "T1" else "city"
            P[kind].setdefault((f[2], bare(f[6])), []).append(f[4])
            P["name"][f[4]], P["kind"][f[4]] = f[6], kind
            P["counties"][f[4]].add(FIPS + f[2])
    with open(paths["place"], encoding="utf-8", errors="replace") as fh:
        head = fh.readline().rstrip("\r\n").split("|")
        if head != ["STATE", "STATEFP", "PLACEFP", "PLACENS", "PLACENAME", "TYPE", "CLASSFP", "FUNCSTAT", "COUNTIES"]:
            raise SystemExit("Michigan: the Census place list's header is not the one this loader was checked against")
        names = {}
        for line in fh:
            f = line.rstrip("\r\n").split("|")
            if len(f) == 9 and f[1] == FIPS and f[6] == "C1":
                names[f[2]] = (f[4], [c.strip() for c in f[8].split("~~~") if c.strip()])
    P["village_rows"] = names
    return P


def place_counties(P, counties, code):
    """Every county a village lies in, by the place list's own county names."""
    return {counties[county_key(c)] for c in P["village_rows"][code][1] if county_key(c) in counties}


def resolve_mcd(P, cmap, fips5, jtype, text):
    """(code, Census name, kind, {county codes}) for a city, village or township named on a county's list: the one
    entry of that kind in that county whose name is the same, kind words set aside. None when there is no such single
    entry. With no kind given, a name must be one thing only in the county (a city, or a village, or a township)."""
    c3, b = fips5[2:], bare(text)
    if not b:
        return None
    found = {}
    if jtype in ("township", None):
        hits = P["township"].get((c3, b), [])
        if len(hits) == 1:
            found["township"] = hits[0]
    if jtype in ("city", None):
        hits = P["city"].get((c3, b), [])
        if len(hits) == 1:
            found["city"] = hits[0]
    if jtype in ("village", None):
        hits = [code for code, (name, _cs) in P["village_rows"].items() if bare(name) == b and fips5 in place_counties(P, cmap, code)]
        if len(hits) == 1:
            found["village"] = hits[0]
    if len(found) != 1:
        return None
    kind, code = next(iter(found.items()))
    if kind == "village":
        return code, P["village_rows"][code][0], kind, place_counties(P, cmap, code)
    return code, P["name"][code], kind, set(P["counties"][code])


# ---------------------------------------------------------------- school districts: the state's own codes

EEM_KEEP = ("DistrictCode", "DistrictOfficialName", "DistrictCommonName", "EntityCountyCode", "EntityCountyName", "EntityStatus")
SCHOOL_GENERIC = {"school", "schools", "sch", "district", "public", "community", "area", "city", "of", "the", "consolidated", "system", "no",
                  "agricultural", "rural", "unified", "board", "education", "member", "comm", "dist"}


def eem_districts(folder, say=print, fetch=True):
    """Michigan's school districts with the state's own district codes, from the Center for Educational Performance and
    Information's Educational Entity Master: its Public Data Sets page, entity type "LEA District", format CSV, asked
    as the page's own Download button asks (the page's session cookie carried from the first request to the second).
    The answer has 61 columns, among them each district office's street, telephone, e-mail and administrator's name;
    six columns are read, by their headings, and only those are kept (as JSON)."""
    path = os.path.join(folder, "cepi_eem_lea_districts.json")
    old = read_json(path)
    if old and (not fetch or age_days(old.get("fetched")) < 30):
        return path, old
    try:
        opener = build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))
        time.sleep(1.0)
        with opener.open(Request(EEM_URL, headers={"User-Agent": net.UA, "Accept": "*/*"}), timeout=90) as r:
            page = r.read().decode("utf-8", "replace")
        fields = {m.group(1): H.unescape(m.group(2)) for m in re.finditer(r'<input type="hidden" name="([^"]+)" id="[^"]*" value="([^"]*)"', page)}
        box = re.search(r'<input id="(ctl00_cphMain_cblEntityTypes_\d+)" type="checkbox" name="([^"]+)"[^>]*/?>\s*<label for="\1">LEA District</label>', page)
        fmt = re.search(r'<select\b[^>]*name="(ctl00\$cphMain\$ddlFormat)"[^>]*>(.*?)</select>', page, re.S)
        csv_value = re.search(r'<option[^>]*value="([^"]*)"[^>]*>\s*CSV\s*</option>', fmt.group(2)) if fmt else None
        button = re.search(r'<input type="submit" name="([^"]+)" value="(Download Data Set)"', page)
        if not (box and csv_value and button):
            raise ValueError("the Public Data Sets form is not the one this loader was checked against")
        fields.update({box.group(2): "on", fmt.group(1): csv_value.group(1), button.group(1): button.group(2)})
        time.sleep(1.0)
        req = Request(EEM_URL, data=urllib.parse.urlencode(fields).encode(), method="POST",
                      headers={"User-Agent": net.UA, "Content-Type": "application/x-www-form-urlencoded", "Referer": EEM_URL})
        with opener.open(req, timeout=180) as r:
            raw = r.read()
        rows = list(csv.reader(io.StringIO(raw.decode("utf-8-sig", "replace"))))
        head = rows[0] if rows else []
        if any(k not in head for k in EEM_KEEP):
            raise ValueError("the data set's columns are not the ones this loader was checked against")
        idx = [head.index(k) for k in EEM_KEEP]
        kept = [[r[i].strip() for i in idx] for r in rows[1:] if len(r) == len(head)]
        doc = {"title": "Educational Entity Master, Public Data Sets: LEA District (CSV)", "url": EEM_URL, "fetched": today(),
               "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw), "columns": list(EEM_KEEP), "rows": kept}
        del raw, rows
    except Exception as err:  # noqa: BLE001  out of reach or changed: the copy on disk, else none (districts are then keyed by name)
        if old:
            say(f"      Michigan: the school district list did not answer ({type(err).__name__}); using the copy of {old.get('fetched')} on disk")
            return path, old
        say(f"      Michigan: the school district list could not be read ({type(err).__name__}); school districts are keyed by name on this run")
        return None, None
    write_json(path, doc)
    return path, doc


def school_tokens(name):
    t = fold(re.sub(r"#\s*", " no ", re.sub(r"\bSch\.", "School", name or "")))
    return [w for w in t.split()]


def school_core(name):
    return tuple(w for w in school_tokens(name) if w not in SCHOOL_GENERIC
                 and not any(difflib.SequenceMatcher(None, w, g).ratio() >= 0.84 for g in ("community", "schools", "district", "public")))


class Schools:
    """Matches a school district as a county's list names it to one district of the state's list."""

    def __init__(self, doc, counties):
        self.rows, self.close = [], []
        for code, official, common, ccode, cname, status in (doc or {}).get("rows", []):
            if status == "Closed" or not re.fullmatch(r"\d{5}", code):
                continue
            hint = re.search(r"\(([^()]+)\)\s*$", official)
            plain = re.sub(r"\s*\([^()]*\)\s*$", "", official)
            if ", " in plain:
                a, b = plain.split(", ", 1)
                if re.search(r"\bof$", b):                            # "Hazel Park, School District of the City of"; not "Redford Union Schools, District No. 1"
                    plain = f"{b} {a}"
            said = re.search(r"\bCounties of (.+)$", plain)           # "Brandon School District in the Counties of Oakland and Lapeer"
            also = {counties[county_key(n)] for n in list_names(said.group(1)) if county_key(n) in counties} if said else set()
            self.rows.append({"code": code, "name": squeeze(plain) + (f" ({hint.group(1)})" if hint else ""), "exact": " ".join(school_tokens(plain)),
                              "core": school_core(plain), "common": tuple(fold(common).split()), "county": counties.get(county_key(cname)),
                              "also": also, "active": status == "Open-Active"})

    @staticmethod
    def one(hits, fips_hints):
        """The one district among several of one name: the one whose own county is the list's county (or the county the
        list says it files with), and of those the one still operating."""
        if len(hits) > 1 and any(r["county"] in fips_hints for r in hits):
            hits = [r for r in hits if r["county"] in fips_hints]
        if len(hits) > 1 and any(r["active"] for r in hits):
            hits = [r for r in hits if r["active"]]
        return hits[0] if len(hits) == 1 else None

    def match(self, text, fips_hints):
        """The one district this name means, or None. The exact name first; then the name with the words every district
        shares set aside (Public, Community, Schools, District ...), and with digits set aside; then, among the
        districts of the list's own county only, a name one or two letters off (a list's misprint), noted for reading."""
        exact, core = " ".join(school_tokens(text)), school_core(text)
        bare_core = tuple(w for w in core if not w.isdigit())
        for test in (lambda r: r["exact"] == exact, lambda r: r["core"] == core and core,
                     lambda r: bare_core and tuple(w for w in r["core"] if not w.isdigit()) == bare_core,
                     lambda r: bare_core and r["common"] == bare_core):
            hits = [r for r in self.rows if test(r)]
            if hits:
                return self.one(hits, fips_hints)
        want = " ".join(bare_core)
        near = [r for r in self.rows if r["county"] in fips_hints and want
                and difflib.SequenceMatcher(None, want, " ".join(w for w in r["core"] if not w.isdigit())).ratio() >= 0.9]
        if len(near) == 1:
            self.close.append((squeeze(text), near[0]["name"]))
            return near[0]
        return None


# ---------------------------------------------------------------- the courts: which counties a circuit or district reaches

UNITS = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9}
TEENS = {"tenth": 10, "eleventh": 11, "twelfth": 12, "thirteenth": 13, "fourteenth": 14, "fifteenth": 15, "sixteenth": 16, "seventeenth": 17,
         "eighteenth": 18, "nineteenth": 19}
TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}
TENTHS = {"twentieth": 20, "thirtieth": 30, "fortieth": 40, "fiftieth": 50, "sixtieth": 60, "seventieth": 70, "eightieth": 80, "ninetieth": 90}
ORDWORD = (r"(?:(?:twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety)-)?(?:first|second|third|fourth|fifth|sixth|seventh|eighth|ninth)|tenth|eleventh|twelfth|"
           r"thirteenth|fourteenth|fifteenth|sixteenth|seventeenth|eighteenth|nineteenth|twentieth|thirtieth|fortieth|fiftieth|sixtieth|seventieth|eightieth|ninetieth")
PLACE_NAME = r"[A-Z][A-Za-z']*(?: [A-Z][A-Za-z']*)*"
PLACE_LIST = rf"{PLACE_NAME}(?:(?:, and |, | and ){PLACE_NAME})*"


def word_number(words):
    w = re.sub(r"\s+", "", words.lower())
    if w in TEENS:
        return TEENS[w]
    if w in TENTHS:
        return TENTHS[w]
    if w in UNITS:
        return UNITS[w]
    tens, _, unit = w.partition("-")
    return TENS[tens] + UNITS[unit]


def list_names(text):
    return [n.strip() for n in re.split(r", and |, | and ", text) if n.strip()]


def statute_sections(path):
    """[(section number, its text)] of one chapter of the Revised Judicature Act, and the public act the copy is complete through."""
    lines = pdftext.lines(path)
    text = " ".join(x[2] for x in lines)
    through = re.search(r"Complete Through PA (\d+ of \d{4})", text)
    text = re.sub(r"Michigan Compiled Laws Complete Through PA \d+ of \d{4} Rendered \w+, \w+ \d+, \d{4} Page \d+ of \d+ Courtesy of (?:www\.)?legislature\.mi\.gov", " ", text)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\b(St|Mt)\. ", r"\1 ", text)                      # St. Clair, Mt. Morris: no full stop inside a name while sentences are cut
    out = []
    for s in re.split(r"(?=\b600\.\d+[a-z]? [A-Z][^.]{3,160}\. Sec\. \d+[a-z]?\.)", text):
        m = re.match(r"(600\.\d+[a-z]?) ", s)
        if m:
            body = s.split("History:")[0]
            body = re.sub(r"(\w)- (\w)", r"\1-\2", body)              # "fifty- fifth", broken at a line end
            out.append((m.group(1), body))
    return out, (through.group(1) if through else "")


def read_statute(folder, say=print, fetch=True):
    """The circuits and district court districts as the Revised Judicature Act draws them. Two PDFs from the
    Legislature's own file directory, kept whole (statute text)."""
    paths = {ch: os.path.join(folder, f"mcl-236-1961-{ch}.pdf") for ch in ("5", "81")}
    for ch, p in paths.items():
        if fetch or not os.path.exists(p):
            net.download(MCL_PDF.format(ch), p, 30, say=say)
    s5, through5 = statute_sections(paths["5"])
    s81, through81 = statute_sections(paths["81"])
    circuits = {}
    one = rf"(?:{PLACE_NAME}|schoolcraft)"
    for sec, body in s5:
        for m in re.finditer(rf"the ({ORDWORD}) judicial circuit(?: court)? consists of the count(?:y|ies) of ({one}(?:(?:, and |, | and ){one})*)", body, re.I):
            names = re.match(rf"({one}(?:(?:, and |, | and ){one})*)", m.group(2))        # the list stops at the first word that is not a name
            circuits[word_number(m.group(1))] = (sec, list_names(names.group(1)))           # the last statement in a section is the one in force
    districts, divisions, excepted = {}, {}, collections.defaultdict(set)
    every = collections.defaultdict(list)                             # every statement of a district, in the act's order
    unsettled = set()                                                 # districts the act lets local governments consolidate: which version is in force is not in the act
    for sec, body in s81:
        if not re.match(r"600\.81[1-6]\d", sec):
            continue
        for m in re.finditer(rf"consolidation of the ((?:(?:{ORDWORD})(?:-[a-c])?(?:, and |, | and )?)+) districts", body, re.I):
            for o in re.finditer(rf"({ORDWORD})(-[a-c])?", m.group(1), re.I):
                unsettled.add(str(word_number(o.group(1))) + (o.group(2) or "").strip("-").upper())
        for m in re.finditer(rf"the ({ORDWORD})(-[a-cA-C])? district consists of (.*?)(?:,? is a district|,? and is a district| and has \d+ judges?|\. )", body, re.I):
            words = m.group(3).strip()
            if not re.search(r"\bcount(y|ies) of|\bcit(y|ies) of|\btownships? of", words):
                continue
            label = str(word_number(m.group(1))) + (m.group(2) or "").strip("-").upper()
            d = {"words": words, "counties": [], "cities": [], "townships": []}
            every[label].append(d)
            parts = re.split(r",? except(?: for)? ", words, maxsplit=1)
            for kind, pat in (("counties", r"count(?:y|ies) of "), ("cities", r"(?:cit(?:y|ies)|villages?) of "), ("townships", r"townships? of ")):
                for mm in re.finditer(pat + rf"({PLACE_LIST})", parts[0]):
                    d[kind] += list_names(mm.group(1))
            if len(parts) > 1 and d["counties"]:
                for mm in re.finditer(rf"cit(?:y|ies) of ({PLACE_LIST})", parts[1]):
                    for city in list_names(mm.group(1)):
                        excepted[bare(city)].update(d["counties"])
                for mm in re.finditer(rf"townships? of ({PLACE_LIST})", parts[1]):
                    for town in list_names(mm.group(1)):
                        excepted["township " + bare(town)].update(d["counties"])
            districts[label] = (sec, d)
        cur = None
        for m in re.finditer(rf"the ({ORDWORD})(-[a-cA-C])? district consists of|the (first|second|third|fourth|fifth) division consists of (.*?)(?: and has \d+ judges?|\. )"
                             rf"|the (first|second|third|fourth|fifth) division also includes (.*?)\. ", body, re.I):
            if m.group(1):
                cur = str(word_number(m.group(1))) + (m.group(2) or "").strip("-").upper()
            elif m.group(3) and cur:
                divisions[(cur, UNITS[m.group(3).lower()])] = [sec, m.group(4).strip().rstrip(","), ""]
            elif m.group(5) and cur and (cur, UNITS[m.group(5).lower()]) in divisions:
                divisions[(cur, UNITS[m.group(5).lower()])][2] = m.group(6).strip()
    for label in unsettled & set(districts):                          # either version may be in force: every county either one names, and no sentence of its words
        d = districts[label][1]
        d["unsettled"] = True
        for other in every[label]:
            for kind in ("counties", "cities", "townships"):
                d[kind] += [x for x in other[kind] if x not in d[kind]]
    return {"paths": paths, "through": (through5, through81), "circuits": circuits, "districts": districts, "divisions": divisions, "excepted": excepted}


def statute_words(words):
    return re.sub(r"\b(St|Mt) (?=[A-Z])", r"\1. ", words)


def court_contest(head):
    """A circuit, district or probate court heading of the Official Candidate Listing -> what it says, or None."""
    m = re.match(r"^(.+?) Judge of (Circuit|District|Probate) Court (Incumbent|Non-Incumbent)\b", head)
    if not m:
        return None
    where, court, pos = m.groups()
    seats = re.search(r"\((\d+) ?\) Positions?\b", head)
    seats = int(seats.group(1)) if seats else 1
    term = re.search(r"(\d+) Year Terms?", head)
    partial = re.search(r"Partial Term(?: - \d+ Years)? Ending (\d\d)/(\d\d)/(\d{4})", head)
    c = {"court": court, "pos": pos, "seats": seats, "term": int(term.group(1)) if term and not partial else None,
         "partial": partial.groups() if partial else None, "label": None, "div": None, "county": None, "head": head}
    if court == "Circuit":
        n = re.fullmatch(r"(\d+)(?:st|nd|rd|th) Circuit", where)
        if not n:
            return None
        c["label"] = str(int(n.group(1)))
    elif court == "District":
        n = re.fullmatch(r"(\d+)(?:st|nd|rd|th)?([A-Z])? District(?: - (\d+)(?:st|nd|rd|th) Division)?", where)
        if not n:
            return None
        c["label"], c["div"] = str(int(n.group(1))) + (n.group(2) or ""), int(n.group(3)) if n.group(3) else None
    else:
        c["county"] = where
    return c


def court_rows(gen, statute, cmap, cfull, P, say=print):
    """The circuit, district and probate judges on the November listing, as rows ready to write."""
    by_key, order, problems, off, notes_dropped = {}, [], [], [], 0
    for head, status, party, raw in gen:
        if not LOCAL_COURTS.search(head or "") or classify(head):
            continue
        c = court_contest(head)
        if not c:
            problems.append(f"a court heading on the listing this loader cannot read: {head}")
            continue
        key = ({"Circuit": "CC", "District": "DC", "Probate": "PC"}[c["court"]]
               + (c["label"] or "") + (f"-{c['div']}" if c["div"] else ""))
        if c["court"] == "Probate":
            hit = cmap.get(county_key(c["county"]))
            if not hit:
                problems.append(f"a probate court heading names a county the Census county file does not have: {head}")
                continue
            key += hit[2:]
            c["fips"] = hit
        key += ("-NI" if c["pos"] == "Non-Incumbent" else "") + (f"-PT{c['partial'][2]}" if c["partial"] else "")
        rid = f"2026-{STATE}-{key}"
        if rid in by_key and by_key[rid]["head"] != head:
            problems.append(f"{rid}: two headings share this race id")
            continue
        if rid not in by_key:
            by_key[rid] = c
            c["rows"] = []
            order.append(rid)
        name = ballot_name(raw)
        if status:
            off.append((rid, status, name))
        else:
            by_key[rid]["rows"].append((name, party))

    fips_of = lambda names: {cmap[county_key(n)] for n in names if county_key(n) in cmap}
    cities = collections.defaultdict(set)                             # a city's name, kind words set aside -> the counties it lies in
    for (c3, b), codes in P["city"].items():
        cities[b].add(FIPS + c3)
    several = set()

    def district_counties(label, div):
        hit = statute["districts"].get(label)
        if not hit:
            return None, None, None
        sec, d = hit
        base = fips_of(d["counties"])
        cs = set(base)
        for city in d["cities"]:
            b = bare(city)
            cs |= fips_of(statute["excepted"].get(b, ()))             # a city another county's district leaves out belongs to this one
            if not d["counties"]:
                if not cities.get(b):
                    return None, None, None
                cs |= cities[b]
                if len(cities[b]) > 1:
                    several.add(f"{label}: {city} city lies in {and_names(sorted(cfull[f] for f in cities[b]))}")
        for town in d["townships"]:
            if d["counties"]:
                continue                                              # "the townships of ... in the county of Wayne": the county is named
            got = fips_of(statute["excepted"].get("township " + bare(town), ()))      # a township a county's own district leaves out
            if not got:
                here = [FIPS + c3 for (c3, b) in P["township"] if b == bare(town)]
                got = set(here) if len(here) == 1 else set()         # else the one township of that name in the state
            if not got:
                return None, None, None
            cs |= got
        words = statute_words(d["words"])
        plain = d.get("unsettled") or (bool(d["counties"]) and not d["cities"] and not d["townships"] and " except" not in d["words"])
        if div:
            dv = statute["divisions"].get((label, div))
            if not dv:
                return cs or None, sec, None
            named = set()
            for text in (dv[1], dv[2]):
                for mm in re.finditer(rf"count(?:y|ies) of ({PLACE_LIST})", text):
                    named |= fips_of(list_names(mm.group(1)))
            cs = (named or base or cs) | (named & set(cmap.values()))
            if not re.search(r"count(?:y|ies) of", dv[1]):
                cs |= base
            sentence = f"By state law this election division consists of {statute_words(dv[1])}." + (f" It also includes {statute_words(dv[2])}." if dv[2] else "")
            return cs or None, dv[0], sentence
        return cs or None, sec, (None if plain else f"By state law the district consists of {words}.")

    races, cands, places, gaps = [], [], {}, []
    for rid in order:
        c = by_key[rid]
        bits = [f"{c['pos']} position" + ("s" if c["seats"] > 1 else "")]
        if c["term"]:
            bits.append(f"{c['term']}-year term")
        if c["partial"]:
            bits.append(f"Partial term ending {'/'.join(c['partial'])}")
        if c["seats"] > 1:
            bits.append(f"{NUMBER.get(c['seats'], c['seats'])} seats; each voter may choose up to {c['seats']}")
        sentence, sec, cs = None, None, None
        if c["court"] == "Circuit":
            hit = statute["circuits"].get(int(c["label"]))
            if hit:
                sec, cs = hit[0], fips_of(hit[1])
                if len(cs) != len(hit[1]):
                    cs = None
            jur, jid, kind, district, seat = f"{ordinal(c['label'])} Circuit Court", f"{STATE}-CC{c['label']}", "circuit_court", f"{ordinal(c['label'])} Circuit", None
        elif c["court"] == "District":
            cs, sec, sentence = district_counties(c["label"], c["div"])
            n = re.match(r"\d+", c["label"]).group()
            words = f"{ordinal(n)} District" if c["label"] == n else f"{c['label']} District"      # as the listing words it: 36th District, 2A District
            jur = f"{words} Court" + (f", {ordinal(c['div'])} Division" if c["div"] else "")
            jid = f"{STATE}-DC{c['label']}" + (f"-{c['div']}" if c["div"] else "")
            kind, district, seat = "district_court", words, (f"{ordinal(c['div'])} Division" if c["div"] else None)
        else:
            cs, name = {c["fips"]}, cfull[c["fips"]]
            jur, jid, kind, district, seat = f"{name} Probate Court", f"{STATE}-PC{c['fips'][2:]}", "probate_court", None, None
        if not cs:
            problems.append(f"{rid}: the counties this court reaches could not be read from the statute; the race is stored without them")
            gaps.append((STATE, "race", rid, jur, "which counties this court contest is on the ballot in",
                         "The Revised Judicature Act's words for this circuit or district could not be read by this loader, so the contest is shown with the "
                         "judges of the whole state and not under any county.", MCL_PDF.format("81" if c["court"] == "District" else "5")))
        note = "; ".join(bits)
        if sentence:
            longer = f"{note}. {sentence}"
            if reads_like_contact(longer):
                notes_dropped += 1
            else:
                note = longer
        races.append((rid, STATE, "court", kind, f"Judge of {c['court']} Court", jur, jid, json.dumps(sorted(cs)) if cs else None, district, seat,
                      1 if c["partial"] else 0, 0, None, None, None, GENERAL, note))
        if cs:
            src = SRC_MCL5 if c["court"] == "Circuit" else SRC_MCL81 if c["court"] == "District" else SRC_GEN
            places[jid] = ("judicial", jid, jur, json.dumps(sorted(cs)), src)
        if not c["rows"]:
            problems.append(f"{rid}: no candidate on the November ballot")
        seen = set()
        for name, party in c["rows"]:
            if name in seen:
                problems.append(f"{rid}: the same name twice on the November list")
                continue
            seen.add(name)
            cands.append((rid, "general", GENERAL, name, NONPARTISAN, "N", None, int(party == "INCUMBENT"), 0, None, None, None, None, SRC_GEN, None))
    covered = collections.Counter(f for _sec, names in statute["circuits"].values() for f in fips_of(names))
    if set(covered) != set(cmap.values()) or any(n != 1 for n in covered.values()):
        problems.append(f"the statute's circuits do not cover the 83 counties once each ({len(covered)} counties named, "
                        f"{sum(1 for n in covered.values() if n > 1)} more than once)")
    return {"races": races, "cands": cands, "places": list(places.values()), "gaps": gaps, "problems": problems, "off": off, "by_key": by_key,
            "several": sorted(several), "notes_dropped": notes_dropped,
            "by_kind": collections.Counter(r[3] for r in races)}


# ---------------------------------------------------------------- what a county's contest is

PARTIES = [
    (re.compile(r"^(dem|democrat|democratic)( party)?$", re.I), "Democratic Party"),
    (re.compile(r"^(rep|republican)( party)?$", re.I), "Republican Party"),
    (re.compile(r"^(lib|libertarian)( party)?$", re.I), "Libertarian Party"),
    (re.compile(r"^(grn|green)( party)?$", re.I), "Green Party"),
    (re.compile(r"^(ust|u\.?\s?s\.?\s?taxpayers'?)( party)?$", re.I), "U.S. Taxpayers Party"),
    (re.compile(r"^(wc|wcp|working class)( party)?$", re.I), "Working Class Party"),
    (re.compile(r"^(nlp|natural law)( party)?$", re.I), "Natural Law Party"),
]
NO_AFFILIATION = re.compile(r"^(npa|no party affiliation)$", re.I)
NOT_A_PARTY = re.compile(r"^(|np|nonpartisan|non-partisan|non partisan|partisan|incum\.?|incumbent|non-incumbent|n/a|na)$", re.I)
STATE_OFFICE = re.compile(r"\b(governor|secretary of state|attorney general|united states|u\.\s?s\.?|congress|state senat|state representative|"
                          r"representative in state legislature|^senator$|^representative$|state board of education|regents?\b|"
                          r"michigan state university|wayne state university|supreme court|court of appeals|judge of appeals|precinct delegate)", re.I)
COURT_OFFICE = re.compile(r"\b(circuit|district court|probate|judge)\b", re.I)
NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9}
SUFFIX = re.compile(r"^(jr|sr|ii|iii|iv|v)\.?$", re.I)
MISPRINTS = {"NORTHILLE DISTRICT LIBRARY": "NORTHVILLE DISTRICT LIBRARY"}      # a list's own misprint, read by hand; the race's note says so
# A college whose board has seats for each of its counties, every one of them voted on by the whole college district. Read
# by hand on the college's own board page (Delta College, 2026-10-01: each trustee "is elected by ballots cast in all
# three counties"). Such a contest is filed under every county of the college; any other college with county seats is
# filed under the seat's county and the county whose list prints it, and the run asks for a hand check.
WHOLE_DISTRICT_SEATS = {"delta-college": "Delta College says each trustee is elected by ballots cast in all three of its counties."}


def party_words(cell):
    """(party as the state rows write it, colour code), ('', 'N') for a cell that names no party, (None, None) for one this loader does not know."""
    cell = squeeze(cell)
    for pat, words in PARTIES:
        if pat.match(cell):
            return words, party_code(words)
    if NO_AFFILIATION.match(cell):
        return "No Party Affiliation", "I"
    if NOT_A_PARTY.match(cell):
        return "", "N"
    return None, None


def title_case(text):
    """Ordinary capitals for a heading or a name a list prints in capitals."""
    def word(w):
        if SUFFIX.match(w) and w.upper().rstrip(".") in ("II", "III", "IV"):
            return w.upper()
        if re.fullmatch(r"[A-Z]\.?", w):
            return w
        parts = re.split(r"([-'’/])", w.lower())
        out = "".join(p.capitalize() if i % 2 == 0 else p for i, p in enumerate(parts))
        return re.sub(r"^Mc([a-z])", lambda m: "Mc" + m.group(1).upper(), out)
    small = {"of", "the", "and", "for", "in"}
    words = [word(w) for w in squeeze(text).split(" ")]
    return " ".join(w.lower() if i and w.lower() in small else w for i, w in enumerate(words))


def plain_case(text):
    return title_case(text) if text and text.upper() == text and re.search(r"[A-Z]{3}", text) else squeeze(text)


def person_name(raw):
    """The name as filed, in ordinary capitals: 'Last, First' turned round, a list's capitals lowered."""
    raw = squeeze(raw)
    head, _, tail = raw.rpartition(",")
    if head and tail.strip() and not SUFFIX.match(tail.strip()):
        raw = squeeze(first_last(raw))
    return title_case(raw) if raw.upper() == raw and re.search(r"[A-Z]{2}", raw) else raw


def parse_term(text):
    """{'years': n or None, 'end': (mm, dd, yyyy) or None, 'partial': bool, 'seats': n or None, 'mixed': bool} from a list's term words."""
    t = squeeze(text)
    years = re.findall(r"(\d+)\s*-?\s*years?\b", t, re.I)
    end = re.search(r"(?:end(?:ing|s)?|expir(?:es|ing))\s*(\d{1,2})[/-](\d{1,2})[/-](\d{4})", t, re.I)
    seats = re.match(r"(one|two|three|four|five|six|seven|eight|nine)\b", t, re.I)
    partial = bool(end) or bool(re.search(r"\bpartial\b|\bunexpired\b", t, re.I))
    mixed = bool((len(set(years)) > 1) or (years and end) or re.search(r"highest|lowest", t, re.I))
    return {"years": int(years[0]) if years else None, "end": tuple(end.groups()) if end else None, "partial": partial and not (years and end),
            "seats": NUMBER_WORDS.get(seats.group(1).lower()) if seats else None, "mixed": mixed, "words": t}


TOWN_OFFICES = [
    (r"supervisor", "town_supervisor", "Township Supervisor"), (r"clerk", "town_clerk", "Township Clerk"), (r"treasurer", "town_treasurer", "Township Treasurer"),
    (r"trustee", "town_trustee", "Township Trustee"), (r"parks? (commission|board)\w*", "park_commissioner", "Township Park Commissioner"),
    (r"library board\b.*", "library_board", "Library Board Member"), (r"constable", "constable", "Constable"),
]
CITY_OFFICES = [
    (r"mayor", "mayor", "Mayor"), (r"clerk", "city_clerk", "City Clerk"), (r"treasurer", "city_treasurer", "City Treasurer"), (r"assessor", "city_assessor", "City Assessor"),
    (r"constable", "constable", "Constable"), (r"charter commission\w*", "charter_commission", "Charter Commission Member"),
    (r"library board\b.*", "library_board", "Library Board Member"), (r"(city )?comptroller", "city_comptroller", "City Comptroller"),
    (r"(city )?commission\w*", "council", "City Commissioner"), (r"(city )?council\b.*", "council", "City Council Member"),
]
VILLAGE_OFFICES = [
    (r"president", "village_president", "Village President"), (r"clerk", "city_clerk", "Village Clerk"), (r"treasurer", "city_treasurer", "Village Treasurer"),
    (r"trustee", "council", "Village Trustee"), (r"council\b.*", "council", "Village Council Member"), (r"library board\b.*", "library_board", "Library Board Member"),
]
# on the party part of the ballot by law (MCL 168.358: township offices but the library board; county offices), so a contest nobody filed for is still partisan
PARTISAN_BY_LAW = {"county_executive", "county_commissioner", "town_supervisor", "town_clerk", "town_treasurer", "town_trustee", "park_commissioner", "constable"}


def split_district(text):
    """('At Large' or None, 'District 1' / '1st Ward' or None, what is left) from an office's words."""
    t = squeeze(text)
    seat = district = None
    m = re.search(r"\bat[- ]large\b", t, re.I)
    if m:
        seat, t = "At Large", squeeze(t[:m.start()] + " " + t[m.end():])
    m = re.search(r"\b(?:(district|ward) (\d+)|(\d+)(?:st|nd|rd|th) (district|ward))\b", t, re.I)
    if m:
        word, n = (m.group(1) or m.group(4)).title(), int(m.group(2) or m.group(3))
        district, t = f"{word} {n}", squeeze(t[:m.start()] + " " + t[m.end():])
    return seat, district, t.strip(" -")


def understand(spec, c):
    """One contest of a county's list -> None for a state, federal or court contest, else a dict: jtype (county,
    township, city, village, school, college, library), jname (the jurisdiction as the list words it), office words,
    district and seat. Raises ValueError for a contest it cannot place."""
    title, jur, sub = c["title"], c["jur"] or "", c["sub"] or ""
    T, J = title.upper(), MISPRINTS.get(jur.upper(), jur.upper())
    out = {"jtype": None, "jname": None, "office": None, "district": None, "seat": None, "files": None, "misprint": jur if J != jur.upper() else None}
    if T in MISPRINTS or any(k in T for k in MISPRINTS):
        for k, v in MISPRINTS.items():
            if k in T:
                out["misprint"], T = title, T.replace(k, v)
    # a state, federal or court contest: the statewide listing carries it (a municipal judge is not on that listing, so it goes on and is counted as not placed)
    if J in ("STATE OF MICHIGAN", "UNITED STATES") or STATE_OFFICE.search(title) or (COURT_OFFICE.search(title) and not re.search(r"\bDISTRICT LIBRARY\b|SCHOOL|MUNICIPAL", T)):
        return None
    if spec["code"] == "macomb" and sub:
        out["files"] = re.sub(r"^Files With ", "", sub)
        sub = ""
    # ---- the title carries the jurisdiction
    m = (re.match(r"^BOARD MEMBER\s+(.+)$", T) or re.match(r"^(.+?)\s*-\s*BOARD MEMBER$", T) or re.match(r"^(.+\bSCHOOLS?\b.*?)\s+BOARD MEMBER$", T)
         or re.match(r"^(.+?) SCHOOL BOARD$", T))
    if m and not re.search(r"LIBRARY", m.group(1)):
        name = m.group(1)
        t2 = re.match(r"^(.*?)\s*-\s*((?:PARTIAL )?TERM (?:ENDING|EXPIRING)\b.*)$", name)
        if t2:                                                        # Kent types one partial term into the office's own words
            name, out["term"] = t2.group(1), t2.group(2)
        out.update(jtype="school", jname=name, office="school board")
        return out
    m = re.match(r"^(.+ (?:DISTRICT LIBRARY|LIBRARY DISTRICT|PUBLIC LIBRARY)) BOARD MEMBER$", T)
    if m:
        out.update(jtype="library", jname=m.group(1), office="library board")
        return out
    m = re.match(r"^BOARD OF TRUSTEES?(?: MEMBER)?\s+(.+? COLLEGE)(?:\s*-\s*(.+ COUNTY))?$", T) or re.match(r"^(.+ COLLEGE) TRUSTEE()$", T)
    if m:
        out.update(jtype="college", jname=m.group(1), office="trustee", district=title_case(m.group(2)) if m.group(2) else None)
        return out
    m = re.match(r"^(?:COUNTY )?COMMISSIONER\b[\s-]*(.*)$", T)
    if m and (T.startswith("COUNTY") or re.search(r"\bCOUNTY$", J)) and not J.startswith(("CITY", "VILLAGE")):
        _seat, district, _rest = split_district(m.group(1))
        out.update(jtype="county", jname=spec["name"], office="county commissioner", district=district.split()[-1] if district else None)
        if sub:
            _s, d2, _r = split_district(sub)
            out["district"] = out["district"] or (d2.split()[-1] if d2 else None)
        return out
    if T == "COUNTY EXECUTIVE":
        out.update(jtype="county", jname=spec["name"], office="county executive")
        return out
    m = re.match(r"^(.+? (?:CHARTER )?TOWNSHIP) (TRUSTEE|CLERK|TREASURER|SUPERVISOR)$", T)
    if m and not J:
        out.update(jtype="township", jname=m.group(1), office=m.group(2))
        return out
    m = re.match(r"^(.+?) CITY (COUNCIL|MAYOR)$", T)
    if m and not J:
        out.update(jtype="city", jname=m.group(1), office=m.group(2))
        return out
    m = re.match(r"^VILLAGE OF (.+?) (PRESIDENT|TRUSTEE|CLERK|TREASURER)$", T)
    if m and not J:
        out.update(jtype="village", jname=m.group(1), office=m.group(2))
        return out
    if not J:
        raise ValueError("a contest with no jurisdiction this loader can read")
    # ---- the jurisdiction is given beside the office
    section = (c.get("section") or "").upper()
    recall = J.endswith(" RECALL")
    J2 = J[:-7] if recall else J
    if re.search(r"\bCOLLEGE\b", J2):
        jtype = "college"
    elif re.search(r"\bLIBRARY\b", J2):
        jtype = "library"
    elif re.search(r"\bSCHOOLS?\b", J2) or section.startswith("LOCAL SCHOOL"):
        jtype = "school"
    elif re.search(r"\bCOUNTY$", J2) and not re.search(r"\bTOW", J2):
        jtype = "county"
    elif re.search(r"\bTOW\w*P\b", J2) or section.startswith("TOWNSHIP"):
        jtype = "township"
    elif re.search(r"^VILLAGE OF\b|\bVILLAGE$", J2) or section.startswith("VILLAGE"):
        jtype = "village"
    elif re.search(r"^CITY OF\b|\bCITY$", J2) or section in ("CITY", "CITIES"):
        jtype = "city"
    else:
        jtype = None                                                  # a bare name: the Census lists say what it is
    name = re.sub(r"^(CITY OF|VILLAGE OF|(?:CHARTER )?TOWNSHIP OF)\s+", "", J2) if jtype in ("city", "village", "township") else J2
    if recall:
        out["recall"] = True
    office = re.sub(r"^(TOWNSHIP|VILLAGE|CITY)\s*(?=[A-Z])", "", T) if jtype in ("township", "village", "city", None) and not T.startswith(("CITY COUNCIL", "CITY COMM", "CITY COMPT")) else T
    office = re.sub(r"\s*\([^()]*\)\s*$", "", office)                 # a recall's office names the officer: the name is not kept
    seat, district, office = split_district(office)
    if sub:
        s2, d2, rest = split_district(sub)
        seat, district = seat or s2, district or d2
        if rest and jtype == "college" and re.search(r"COUNTY$", rest.upper()):
            district = title_case(rest)
    out.update(jtype=jtype, jname=name, office=office, district=district, seat=seat)
    return out


def classify_local(jtype, office):
    """(level, office_kind, office title) for an office of one kind of jurisdiction, or None."""
    o = squeeze(office).lower()
    if jtype == "county":
        if o == "county executive":
            return "county", "county_executive", "County Executive"
        if o == "county commissioner":
            return "county", "county_commissioner", "County Commissioner"
        return None
    if jtype == "school":
        return ("school", "school_board", "School Board Member") if re.fullmatch(r"(school )?board( member)?|school board member|board of education( member)?", o) else None
    if jtype == "college":
        return ("other", "college_board", "Community College Trustee") if re.fullmatch(r"(board of )?trustees?( member)?", o) else None
    if jtype == "library":
        return ("other", "library_board", "Library Board Member") if re.fullmatch(r"(library )?(board( member)?|trustee|board director)", o) else None
    table = {"township": TOWN_OFFICES, "city": CITY_OFFICES, "village": VILLAGE_OFFICES}.get(jtype)
    for pat, kind, words in table or []:
        if re.fullmatch(pat + r"( member| director)?", o):
            return ("township" if jtype == "township" else "city"), kind, words
    return None


# ---------------------------------------------------------------- the county lists into races

def local_level(folder, gen, say=print, refresh=False, fetch=True, only=None):
    """Michigan's local contests: the courts from the statewide listing, then each county's own list. Returns rows ready
    to write (races, candidates, places, sources, gaps, notes) and the counts behind them. Nothing here touches the
    database."""
    os.makedirs(folder, exist_ok=True)
    counties = census_counties(say)
    cmap = {county_key(n): f for n, (f, _full) in counties.items()}
    cfull = {f: full for f, full in counties.values()}
    P = census_places(folder, say, fetch)
    statute = read_statute(folder, say, fetch)
    courts = court_rows(gen, statute, cmap, cfull, P, say)
    eem_path, eem = eem_districts(folder, say, fetch)
    schools = Schools(eem, cmap)
    problems = list(courts["problems"])

    races, places, docs, gaps = {}, {}, {}, list(courts["gaps"])
    by_county = {}
    special_keys, county_seats = {}, set()                            # a district library's key by its name; colleges whose county seats the whole district votes on
    court_seen = collections.defaultdict(set)                         # county -> the court contests its own list prints
    unplaced = collections.defaultdict(list)
    w_marked = {}
    for spec in COUNTIES:
        if only and spec["code"] not in only:
            continue
        if not spec.get("reader"):
            continue
        doc, why = county_doc(spec, folder, say, refresh, fetch)
        if not doc:
            by_county[spec["code"]] = {"why": why}
            continue
        docs[spec["code"]] = doc
        fips5 = spec["fips"]
        tally = collections.Counter()
        src = f"mi-{spec['code']}-2026-general-list"
        recalls, recall_n = collections.Counter(), collections.Counter()     # recall contests for one office of one place: told apart by their order on the list
        for c in doc["contests"]:
            try:
                u0 = understand(spec, c)
            except ValueError:
                continue
            if u0 and (u0.get("recall") or (c.get("pos") or "").lower().startswith("recall")):
                recalls[(bare(u0["jname"]), squeeze(u0["office"]).lower())] += 1
        for c in doc["contests"]:
            n_rows = len(c["cands"])
            try:
                u = understand(spec, c)
            except ValueError as err:
                unplaced[spec["code"]].append((c, str(err)))
                tally["rows in contests not placed"] += n_rows
                continue
            if u is None:
                tally["state, federal and court contests left to the statewide listing"] += 1
                tally["rows of state, federal and court contests"] += n_rows
                m = COURT_OFFICE.search(c["title"])
                if m:
                    court_seen[fips5].add(court_label(c))
                continue
            kind = classify_local(u["jtype"], u["office"]) if u["jtype"] else None
            hit, row, jtype = None, None, u["jtype"]
            if jtype in ("township", "city", "village", None):
                hit = resolve_mcd(P, cmap, fips5, jtype, u["jname"])
                if hit and not jtype:
                    jtype = hit[2]
                    kind = classify_local(jtype, u["office"])
            if not kind:
                unplaced[spec["code"]].append((c, "an office this loader does not know"))
                tally["rows in contests not placed"] += n_rows
                continue
            level, office_kind, office = kind
            if office_kind == "council" and jtype == "city" and re.search(r"commission", u["office"], re.I):
                office = "City Commissioner"
            term = parse_term(u.get("term") or c["term"] or "")
            note = []
            # ---- the place
            if jtype == "county":
                pid, pname, pkind, pcounties, psrc = fips5, cfull[fips5], "county", {fips5}, SRC_COUNTIES
                key = fips5
            elif jtype in ("township", "city", "village"):
                if hit:
                    mcd_code, pname, _k, pcounties = hit
                    pid, pkind, psrc, key = f"{STATE}-M-{mcd_code}", "mcd", (SRC_PLACE if jtype == "village" else SRC_COUSUB), f"M-{mcd_code}"
                    pcounties = set(pcounties) | {fips5}
                else:
                    words = {"township": "township", "city": "city", "village": "village"}[jtype]
                    pname = f"{plain_case(u['jname'])} {words}"
                    key = f"M-{fips5[2:]}-{slug(pname)}"
                    pid, pkind, pcounties, psrc = f"{STATE}-{key}", "mcd", {fips5}, src
                    tally["places named from the list (no single Census entry)"] += 1
            elif jtype == "school":
                hints = {fips5} | ({cmap[county_key(u["files"])]} if u.get("files") and county_key(u["files"]) in cmap else set())
                row = schools.match(u["jname"], hints)
                if row:
                    pname, key = row["name"], f"S-{row['code']}"
                    pid, pkind, psrc = f"{STATE}-{key}", "school", SRC_EEM
                    pcounties = hints | ({row["county"]} if row["county"] else set()) | row["also"]      # the list's county, the district's own, any its name states
                else:
                    pname = plain_case(u["jname"])
                    key = f"S-{fips5[2:]}-{slug(pname)}"
                    pid, pkind, pcounties, psrc = f"{STATE}-{key}", "school", set(hints), src
                    tally["school districts named from the list (no single entry in the state's list)"] += 1
            else:
                pname = plain_case(u["jname"])
                if u.get("misprint"):
                    pname = title_case(MISPRINTS.get(u["jname"].upper(), u["jname"]))
                if jtype == "college":                                # a college district is no one county's, and no two colleges share a name: its name alone
                    key = "X-" + slug(" ".join(w for w in fold(pname).split() if w not in ("community", "district", "the")))
                else:                                                 # a district library has no official code: the first county whose list prints it, and its name
                    key = special_keys.setdefault(slug(pname), f"X-{fips5[2:]}-{slug(pname)}")
                pid, pkind, psrc = f"{STATE}-{key}", "special", src
                pcounties = {fips5}
                if u.get("district") and county_key(u["district"]) in cmap and jtype == "college":
                    pcounties.add(cmap[county_key(u["district"])])
                    if key[2:] in WHOLE_DISTRICT_SEATS:
                        county_seats.add(pid)
                        note.append(f"This seat is the one for {u['district']}. {WHOLE_DISTRICT_SEATS[key[2:]]}")
                    else:
                        note.append(f"Printed on {spec['name']}'s list; the seat is the one for {u['district']}.")
                        problems.append(f"{pname}: a seat for one county ({u['district']}) printed on {spec['name']}'s list; check by hand whether the whole college "
                                        "district votes on it")
                if u.get("files") and county_key(u["files"]) in cmap:
                    pcounties.add(cmap[county_key(u["files"])])
            # ---- the race
            token, special, mixed = term_token(term)
            if u.get("recall") or (c.get("pos") or "").lower().startswith("recall"):
                special, token = 1, (token or "term") + "-recall"
                note.append("A recall election, as the county's list titles it.")
                rk = (bare(u["jname"]), squeeze(u["office"]).lower())
                if recalls[rk] > 1:                                   # the list tells them apart by the officer's name, which is not kept
                    recall_n[rk] += 1
                    u["seat"] = f"Recall contest {recall_n[rk]}"
                    note.append(f"The county's list prints {recalls[rk]} recall contests for this office, each for one seat; this is number {recall_n[rk]} in the list's order.")
            dtoken = slug(" ".join(x for x in (u["district"], u["seat"]) if x))
            rid = f"2026-{STATE}-{key}-{office_kind.replace('_', '-')}" + (f"-{dtoken}" if dtoken else "") + (f"-{token}" if token else "") + ("-S" if special else "")
            seats = c["vote"] or term["seats"]
            if seats and seats > 1:
                note.append(f"Voters choose {seats}.")
            if term["end"] and special:
                note.append(f"For the rest of a term that ends {long_date(*term['end'])}.")
            elif special and "recall" not in token:
                note.append("For the rest of an unexpired term.")
            if mixed:
                words = f"The county's list words the term this way: \"{term['words']}\"."
                if not reads_like_contact(words):
                    note.append(words)
            if u.get("misprint"):
                note.append(f"The county's list prints this name as \"{plain_case(u['misprint'])}\".")
            cand_rows, real_party = [], False
            for name, pcell, mark in c["cands"]:
                words, code = party_words(pcell)
                if words is None:
                    problems.append(f"{spec['name']}: a party cell this loader does not know in {rid}; the candidate is kept with no party")
                    words, code = "", "N"
                m = mark.lower()
                if m and (DATE.match(mark) or m in OFF_MARKS):
                    tally["withdrawn, disqualified or resigned, left off"] += 1
                    continue
                if m == "marked w":
                    tally["marked (W), left off"] += 1
                    w_marked[rid] = (pname, spec)
                    continue
                write_in = 1 if "write" in m else 0
                if m and not write_in:
                    problems.append(f"{spec['name']}: a status mark this loader does not know in {rid}; the candidate is left off")
                    tally["withdrawn, disqualified or resigned, left off"] += 1
                    continue
                real_party = real_party or (code not in ("N", "I"))
                cand_rows.append([person_name(name), words, code, write_in])
            partisan = 1 if real_party or (office_kind in PARTISAN_BY_LAW and jtype in ("county", "township")) else 0
            race = races.get(rid)
            if race is None:
                home = row["county"] if jtype == "school" and row else (fips5 if jtype == "county" else None)
                race = races[rid] = {"rid": rid, "level": level, "kind": office_kind, "office": office, "jur": pname, "jid": pid, "counties": set(), "district": u["district"],
                                     "seat": u["seat"], "special": special, "partisan": 0, "by_list": {}, "seats": {}, "notes": {}, "none": {}, "home": home,
                                     "term": f"{term['years']} years" if term["years"] else "no term"}
            elif race["jid"] != pid:
                problems.append(f"{rid}: two different contests share this race id ({spec['name']}); the second is left out")
                tally["rows in contests not placed"] += n_rows
                continue
            lcode = spec["code"]
            if lcode in race["by_list"]:
                problems.append(f"{rid}: printed twice on {spec['name']}'s list under the same office and term; the candidates are put together")
            else:
                tally["contests placed"] += 1
            race["partisan"] = max(race["partisan"], partisan)
            race["counties"] |= set(pcounties)
            race["by_list"].setdefault(lcode, []).extend(cand_rows)
            race["seats"].setdefault(lcode, seats)
            race["notes"].setdefault(lcode, note)
            race["none"][lcode] = race["none"].get(lcode, False) or c["none"]
            if pid not in places:
                places[pid] = {"kind": pkind, "id": pid, "name": pname, "counties": set(), "src": psrc}
            places[pid]["counties"] |= set(pcounties)
        by_county[spec["code"]] = {"tally": tally, "doc": doc, "src": src}

    fips_code = {s["fips"]: s["code"] for s in COUNTIES}
    name_of = {s["code"]: s["name"] for s in COUNTIES}
    # ---- one office of one place that two counties print with different full terms is still one contest (one list has a slip):
    # the first county's term is kept, and the race says the lists disagree. A list that prints both itself has two contests.
    same_office = collections.defaultdict(list)
    for rid, race in races.items():
        if not race["special"]:
            same_office[(race["jid"], race["kind"], race["district"], race["seat"])].append(rid)
    for rids in same_office.values():
        lists = [set(races[r]["by_list"]) for r in rids]
        if len(rids) < 2 or any(a & b for i, a in enumerate(lists) for b in lists[i + 1:]):
            continue
        keep = races[rids[0]]
        for rid in rids[1:]:
            other = races.pop(rid)
            a, b = next(iter(keep["by_list"])), next(iter(other["by_list"]))
            said = f"The lists disagree on this office's term: {name_of[a]}'s says {keep['term']}, {name_of[b]}'s {other['term']}."
            for code, rows in other["by_list"].items():
                keep["by_list"][code] = rows
                keep["seats"][code], keep["none"][code] = other["seats"][code], other["none"][code]
                keep["notes"][code] = [n for n in other["notes"][code]] + [said]
            keep["notes"][a] = keep["notes"][a] + [said]
            keep["counties"] |= other["counties"]
            keep["partisan"] = max(keep["partisan"], other["partisan"])
            problems.append(f"{rids[0]}: {name_of[b]}'s list prints this office with another term ({other['term']}, against {keep['term']}); one contest is kept")

    # ---- one race from the lists that print it: the list of the district's own county first, then the others in the order read
    for rid, race in races.items():
        codes = list(race["by_list"])
        first = fips_code.get(race["home"]) if fips_code.get(race["home"]) in codes else codes[0]
        codes = [first] + [c_ for c_ in codes if c_ != first]
        race["lists"], race["cands"] = codes, {}
        for code in codes:
            tally, src = by_county[code]["tally"], by_county[code]["src"]
            mine = [r[0] for r in race["by_list"][code]]
            seen_here = set()
            for name, words, pcode, write_in in race["by_list"][code]:
                if fold(name) in seen_here:
                    problems.append(f"{rid}: the same name twice on {name_of[code]}'s list")
                    tally["rows repeated within a contest"] += 1
                    continue
                seen_here.add(fold(name))
                if code == first:
                    race["cands"][name] = {"party": words, "code": pcode, "write_in": write_in, "src": src, "list": code, "also": []}
                    tally["candidates placed"] += 1
                    continue
                theirs = [k for k, cd in race["cands"].items() if cd["list"] != code]
                same = [k for k in theirs if same_person(name, k, mine, theirs)]
                if len(same) == 1:
                    race["cands"][same[0]]["also"].append(code)
                    tally["counted once across counties"] += 1
                else:
                    race["cands"][name] = {"party": words, "code": pcode, "write_in": write_in, "src": src, "list": code, "also": []}
                    tally["candidates placed"] += 1
        if len(codes) > 1:
            for name, cd in race["cands"].items():
                missing = [code for code in codes if code != cd["list"] and code not in cd["also"]]
                if missing:
                    problems.append(f"{rid}: a candidate on {name_of[cd['list']]}'s list is not on {and_names(name_of[m] for m in missing)}'s (the lists differ, or were updated on different days)")
            if len(set(race["seats"].values())) > 1:
                problems.append(f"{rid}: the lists disagree on how many to vote for ({', '.join(f'{name_of[k]} {v}' for k, v in race['seats'].items())}); {name_of[first]}'s is used")
            if (race["kind"] == "library_board" and race["level"] == "other" and all(race["by_list"][c_] for c_ in codes)
                    and not any(cd["also"] for cd in race["cands"].values())):
                problems.append(f"{rid}: the lists of {and_names(name_of[c_] for c_ in codes)} print a library of this name with no candidate in common; "
                                "they may be two libraries of one name (read it)")

    # a college's county seats that its whole district votes on: every county of the college
    for race in races.values():
        places[race["jid"]]["counties"] |= race["counties"]
    for race in races.values():
        if race["jid"] in county_seats:
            race["counties"] = set(places[race["jid"]]["counties"])

    # the courts, checked against what each county prints
    court_by_county = collections.defaultdict(set)
    for r in courts["races"]:
        for f in json.loads(r[7] or "[]"):
            court_by_county[f].add(court_key_of(r[0]))
    whole = {s["fips"] for s in COUNTIES if s.get("whole_ballot", True)}
    for f, seen in sorted(court_seen.items()):
        extra = sorted(k for k in seen if k and k not in court_by_county[f])
        absent = sorted(k for k in court_by_county[f] if k not in seen) if f in whole else []
        if extra:
            problems.append(f"{cfull[f]}'s list prints court contests the statute does not put in the county: {', '.join(extra)}")
        if absent:
            problems.append(f"{cfull[f]}'s list does not print court contests the statute puts in the county: {', '.join(absent)}")

    for rid, (pname, spec) in sorted(w_marked.items()):
        gaps.append((STATE, "race", rid, pname, "a name the county's list marks (W)",
                     f"{spec['name']}'s list prints a name in this contest with the mark (W) and does not say what the mark means (a write-in candidate, or one who "
                     "withdrew), so the name is left off rather than guessed.", spec["page"]))

    # ---- rows
    race_rows, cand_rows = [], []
    for rid, race in sorted(races.items()):
        first = race["lists"][0]
        notes = list(race["notes"][first])
        for code in race["lists"][1:]:
            notes += [n for n in race["notes"][code] if n not in notes and not n.startswith("Voters choose")]
        if not race["cands"]:
            notes.append("The county's list shows no candidate filed for this contest." if any(race["none"].values())
                         else "The county's list names no candidate for this contest.")
        if len(race["lists"]) > 1:
            notes.append(f"Printed on the lists of {and_names(name_of[code] for code in race['lists'])}.")
        note = " ".join(dict.fromkeys(notes)) or None
        race_rows.append((rid, STATE, race["level"], race["kind"], race["office"], race["jur"], race["jid"], json.dumps(sorted(race["counties"])), race["district"],
                          race["seat"], race["special"], race["partisan"], None, None, None, GENERAL, note))
        for name, cd in sorted(race["cands"].items()):
            if race["partisan"]:
                party, code = (cd["party"] or "No party shown on the county's list"), (cd["code"] if cd["party"] else "O")
            else:
                party, code = NONPARTISAN, "N"
            cand_rows.append((rid, "general", GENERAL, name, party, code, None, 0, cd["write_in"], None, None, None, None, cd["src"],
                              "A declared write-in candidate, as the county's list marks it." if cd["write_in"] else None))
    place_rows =[("county", f, full, json.dumps([f]), SRC_COUNTIES) for f, full in sorted(cfull.items())]
    place_rows += [(p["kind"], p["id"], p["name"], json.dumps(sorted(p["counties"])), p["src"]) for _id, p in sorted(places.items()) if p["kind"] != "county"]
    place_rows += courts["places"]
    return {"courts": courts, "races": race_rows, "cands": cand_rows, "places": place_rows, "gaps": gaps, "problems": problems, "by_county": by_county,
            "unplaced": unplaced, "docs": docs, "counties": counties, "cfull": cfull, "statute": statute, "census": P, "eem": (eem_path, eem), "folder": folder,
            "schools_known": len(schools.rows), "close": sorted(set(schools.close))}


OFF_MARKS = {"withdrew", "withdrawn", "disqualified", "resigned", "deceased", "removed", "unreadable"}


def term_token(term):
    """(the term's part of a race id, 1 for an unexpired term, True when the list's own words are worth quoting)."""
    years, end = term["years"], term["end"]
    if end and (not years or re.match(r"\s*(partial\b|term end|one partial|two partial|three partial)", term["words"], re.I)
                or re.search(r"\bpartial terms? (ending|-)", term["words"], re.I) and not re.search(r"highest|lowest", term["words"], re.I)):
        return "p" + f"{end[2]}{int(end[0]):02d}{int(end[1]):02d}", 1, False
    if years:
        return f"{years}y", 0, term["mixed"]
    if term["partial"]:
        return "partial", 1, False
    return "", 0, False


def name_suffix(name):
    words = fold(name).split()
    return words[-1] if words and words[-1] in ("jr", "sr", "ii", "iii", "iv") else ""


def same_person(a, b, list_a, list_b):
    """Two counties' lists print one candidate of a shared contest: the same name; or names that fit (a middle initial
    more or less); or the same family name, the only one of that family name on either list, with given names that
    begin alike (Jackie on one list, Jacalyn on the other). A Jr. is never a Sr. or a plain name."""
    if fold(a) == fold(b):
        return True
    if name_suffix(a) != name_suffix(b):
        return False
    pa, pb = name_parts(a), name_parts(b)
    if fits(pa, pb):
        return True
    alone = lambda fam, names: sum(1 for n in names if name_parts(n)[1] == fam) == 1
    return bool(pa[1] and pa[1] == pb[1] and pa[0] and pb[0] and pa[0][0][:1] == pb[0][0][:1] and alone(pa[1], list_a) and alone(pb[1], list_b))


def court_label(c):
    """A court contest on a county's list -> 'CC16', 'DC52-1', 'PC' (the same keys court_key_of gives), or '' for the
    Supreme Court and the Court of Appeals."""
    text = squeeze(" ".join(x for x in (c["title"], c.get("jur") or "", c.get("sub") or "", c.get("term") or "") if x)).upper()
    title = c["title"].upper()
    if re.search(r"SUPREME|APPEALS", text):
        return ""
    if "PROBATE" in text:
        return "PC"
    if "CIRCUIT" in title:
        m = re.search(r"(\d+)(?:ST|ND|RD|TH)? (?:CIRCUIT|DISTRICT)", text)
        return f"CC{int(m.group(1))}" if m else "?"
    m = re.search(r"\b(\d+)-(\d+) DISTRICT", text)
    if m:
        return f"DC{int(m.group(1))}-{int(m.group(2))}"
    m = re.search(r"\b(\d+)(?:ST|ND|RD|TH)?-?([A-C])? DISTRICT(?:,? ?-? ?(\d+)(?:ST|ND|RD|TH) DIVISION)?", text)
    if m:
        return f"DC{int(m.group(1))}{m.group(2) or ''}" + (f"-{int(m.group(3))}" if m.group(3) else "")
    return "?"


def court_key_of(rid):
    """'2026-MI-DC52-1-NI' -> 'DC52-1'; '2026-MI-PC163' -> 'PC'; '2026-MI-CC3-PT2031' -> 'CC3'."""
    k = rid.split("-", 2)[2]
    k = re.sub(r"-(NI|PT\d{4})", "", k)
    return "PC" if k.startswith("PC") else k


def local_words(local, gen_pub, say=print):
    """sl_gaps, sl_notes and sl_sources for the local level, and the last look for anything that reads like contact details."""
    cfull, by_county = local["cfull"], local["by_county"]
    loaded = [s for s in COUNTIES if s["code"] in by_county and "doc" in by_county[s["code"]]]
    gaps = list(local["gaps"])
    what = "county, city, village, township, school, college and library board races"
    for s in COUNTIES:
        if s in loaded:
            continue
        info = by_county.get(s["code"], {})
        if s.get("reader"):
            reason = (f"The {s['agency']} posts this county's November 3, 2026 candidate list, but {info.get('why', 'it was not read on this run')}; "
                      "the circuit, district and probate judges on this county's ballot are loaded from the state's own listing.")
        else:
            reason = (f"{s['why']} The county's list is not loaded yet; the circuit, district and probate judges on this county's ballot are loaded "
                      "from the state's own listing.")
            if saved_copy(s, local["folder"]):
                reason += " A copy saved by hand is on this computer, and a reader for its layout is still to be written."
        gaps.append((STATE, "county", s["fips"], s["name"], what, reason, s["page"]))
    named = {s["fips"] for s in COUNTIES}
    for f, full in sorted(cfull.items()):
        if f not in named:
            gaps.append((STATE, "county", f, full, what,
                         "This county's November 3, 2026 list is not loaded yet: Michigan has no statewide list of local candidates, and each county clerk's "
                         "election office publishes its own. The circuit, district and probate judges on this county's ballot are loaded from the state's own listing.",
                         None))
    for code, items in sorted(local["unplaced"].items()):
        s = next(x for x in COUNTIES if x["code"] == code)
        gaps.append((STATE, "county", s["fips"], s["name"], f"{len(items)} contest{'s' if len(items) != 1 else ''} on the county's list",
                     f"{len(items)} contest{'s' if len(items) != 1 else ''} on the county clerk's list could not be placed by this loader (an office or a "
                     "jurisdiction it does not know yet) and are left out rather than guessed.", s["page"]))
    gaps.append((STATE, "state", STATE, "Michigan", "local ballot questions",
                 "Millage, bond and charter questions are on many November ballots; the county lists print them, and this loader reads candidates only.", None))
    gaps.append((STATE, "state", STATE, "Michigan", "write-in candidates",
                 "A write-in candidate must file a declaration of intent by the second Friday before the election, after most county lists are printed; only "
                 "the declared write-ins a county's own list already carries are shown.", MCL_ACT))

    n_by_level = collections.Counter(r[2] for r in local["races"])
    n_loaded = len(loaded)
    courts = local["courts"]
    notes = [
        (STATE, "local_calendar",
         "On November 3, 2026 Michigan voters elect school board members in every school district, community college trustees, district library boards and the "
         "circuit, district and probate judges whose terms are up, all without party labels; villages and the cities whose charters put their elections in "
         "even years elect their officers; and vacancies on county boards and township boards are filled for the rest of a term, with a county executive in "
         "the counties that elect one this year. County clerks, treasurers, registers of deeds, prosecuting attorneys, sheriffs and drain commissioners, county "
         "commissioners and township boards were elected for four years in 2024 and are next elected in 2028, and most cities elect in November of odd-numbered years.",
         "Michigan Election Law, MCL 168.642 and 168.642c (cities, villages and school boards), 168.200 and 168.358 (county and township officers), and MCL 46.410 "
         "(county commissioners); the Department of State's Official Candidate Listing (judges)", MCL_ACT),
        (STATE, "local_coverage",
         f"Loaded: the {len(courts['races'])} circuit, district and probate court contests on the Department of State's Official Candidate Listing, each filed "
         f"under the counties state law puts in its circuit or district; and the county clerks' own November lists for {n_loaded} of the 12 largest counties "
         f"({and_names(s['name'].replace(' County', '') for s in loaded)}): {len(local['races'])} contests ({n_by_level.get('school', 0)} school board, "
         f"{n_by_level.get('city', 0)} city and village, {n_by_level.get('township', 0)} township, {n_by_level.get('county', 0)} county, {n_by_level.get('other', 0)} college and "
         f"library board) with {len(local['cands'])} candidates. Michigan has no statewide list of local candidates, so the other counties are not loaded yet and are "
         "named among the gaps. Left out everywhere: ballot questions, and candidates a list marks as withdrawn or disqualified. A school "
         "district that crosses a county line is shown for the counties whose lists print it, its home county and any county its official name states, and a "
         "college or a district library for the "
         "counties whose lists print it and any county a seat is named for; any of them may reach other counties. No ballot order is given: none of the lists "
         "states the order the ballot prints names in.",
         "County clerks' candidate lists for the November 3, 2026 general election; Michigan Department of State, Official Candidate Listing; Revised Judicature Act, "
         "MCL 600.501 to 600.550a and 600.8101 to 600.8163", BASE + "GEN"),
    ]

    P, statute = local["census"], local["statute"]
    sources = [
        (SRC_COUNTIES, STATE, "official boundaries (attributes)", "U.S. Census Bureau", "Cartographic boundary file, counties, 1:500,000 (2024)", COUNTY_URL, "",
         fetched(COUNTY_ZIP), sha(COUNTY_ZIP), len(cfull), "County names and five-digit codes for Michigan, read from the file's attribute table (the kit's copy; no shapes are read here)."),
        (SRC_COUSUB, STATE, "official place codes", "U.S. Census Bureau", "2020 county subdivision codes, Michigan (st26_mi_cousub2020.txt)", COUSUB_URL, "",
         fetched(P["paths"]["cousub"]), sha(P["paths"]["cousub"]), len(P["name"]),
         "Names and codes of townships and cities, by county. A place on a county's list is given its code only when one entry of the right kind in that county has "
         "the same name; which counties a city lies in is read here too."),
        (SRC_PLACE, STATE, "official place codes", "U.S. Census Bureau", "2020 place codes, Michigan (st26_mi_place2020.txt)", PLACE_URL, "",
         fetched(P["paths"]["place"]), sha(P["paths"]["place"]), len(P["village_rows"]), "Names and codes of villages, with the counties each lies in."),
        (SRC_MCL5, STATE, "statute", "Michigan Legislature, Legislative Service Bureau", "Revised Judicature Act of 1961, Chapter 5, Circuit Courts (MCL 600.501 to 600.563)",
         MCL_PDF.format("5"), "", fetched(statute["paths"]["5"]), sha(statute["paths"]["5"]), len(statute["circuits"]),
         f"Which counties each judicial circuit consists of (the statement in force in each section); complete through Public Act {statute['through'][0]}. "
         "The Legislature's own PDF of the chapter, kept whole: statute text."),
        (SRC_MCL81, STATE, "statute", "Michigan Legislature, Legislative Service Bureau",
         "Revised Judicature Act of 1961, Chapter 81, District Court: Establishment; Districts (MCL 600.8101 to 600.8181)", MCL_PDF.format("81"), "",
         fetched(statute["paths"]["81"]), sha(statute["paths"]["81"]), len(statute["districts"]),
         f"Which counties, cities and townships each district court district and election division consists of; complete through Public Act {statute['through'][1]}. "
         "A district the act describes by cities alone is filed under the county or counties the Census Bureau's list puts those cities in, and a city a county's own "
         "district leaves out is counted in the district that names it. The Legislature's own PDF of the chapter, kept whole: statute text."),
    ]
    eem_path, eem = local["eem"]
    if eem:
        sources.append((SRC_EEM, STATE, "official list", "Michigan Center for Educational Performance and Information",
                        "Educational Entity Master, Public Data Sets: LEA District", EEM_URL, "", eem["fetched"], eem["sha256"], len(eem["rows"]),
                        "The state's own five-digit school district codes and official names, asked as the page's own Download button asks (CSV). Six columns are read, by "
                        "their headings: district code, official and common name, county code and name, and status. The file's street, telephone, e-mail and "
                        "administrator columns are never read, and only the six are kept on disk; the fingerprint is of the answer as it came."))
    for s in loaded:
        info = by_county[s["code"]]
        doc, t = info["doc"], info["tally"]
        counts = doc.get("counts", {})
        blanked = sum(v for k, v in counts.items() if "blanked" in k)
        title = doc.get("title") or s["label"]
        sources.append((info["src"], STATE, "county candidate list", s["agency"], f"{s['name']}: {s['label']}", s["url"], published_day(doc.get("updated")),
                        doc["fetched"], doc["sha256"], counts.get("rows", 0),
                        "Linked from the clerk's own page"
                        + ("; read here from a copy saved by hand, because the county's site did not answer the loader" if doc.get("how") == "saved by hand" else "")
                        + f". Read: {s['read']}. Never read: {s['never']}. Only the cut-down copy is kept on disk; the fingerprint is of "
                        f"the file as it came. {counts.get('rows', 0)} candidate rows: {t['candidates placed']} placed in {t['contests placed']} local contests, "
                        f"{t['rows of state, federal and court contests']} in state, federal and court contests (left to the statewide listing), "
                        f"{t['withdrawn, disqualified or resigned, left off']} marked withdrawn, disqualified or resigned (left off), "
                        f"{counts.get('no candidate filed', 0)} saying no candidate filed"
                        + (f", {t['counted once across counties']} already counted from another county's list" if t["counted once across counties"] else "")
                        + (f", {t['rows in contests not placed']} in contests this loader could not place" if t["rows in contests not placed"] else "")
                        + (f"; {blanked} cells read like contact details and were blanked" if blanked else "") + ". "
                        + (s.get("extra", "") + " " if s.get("extra") else "") + "The list gives no ballot order."))

    # the last look before anything is written: nothing that reads like contact details, by the trial check's own test and the page builder's
    dropped = collections.Counter()
    court_races = [r for r in local["courts"]["races"]]
    for table, strict, items in (("sl_races", True, [(r[0], (r[4], r[5], r[8], r[9], r[16])) for r in local["races"]]),
                                 ("sl_candidates", True, [(c[0], (c[3], c[4], c[14])) for c in local["cands"]]),
                                 ("sl_places", True, [(p[1], (p[2],)) for p in local["places"]]),
                                 ("sl_gaps", False, [(g[2], (g[3], g[4], g[5])) for g in gaps]),
                                 ("sl_notes", False, [(x[1], (x[2], x[3])) for x in notes]),
                                 ("sl_sources", False, [(s[0], (s[3], s[4], s[10])) for s in sources])):
        for ident, texts in items:
            if any(t and reads_like_contact(t, strict) for t in texts):
                raise SystemExit(f"Michigan: a text for {table} ({ident}) reads like contact details; stopping (the text is not printed)")
    for r in court_races:
        if any(t and contact_like(t, True) for t in (r[4], r[5], r[8], r[9])):
            raise SystemExit(f"Michigan: a text for sl_races ({r[0]}) reads like contact details; stopping (the text is not printed)")
    return gaps, notes, sources, dropped


def load(db_path, say=print, cache=CACHE, fetch=True, local_fetch=True, local_refresh=False, local_dir=None, only=None):
    paths = {k: os.path.join(cache, f"mi_candidate_listing_2026_{k.lower()}.html") for k in ("GEN", "PRI")}
    if fetch:
        net.patient_lookups()
        for k, p in paths.items():
            net.download(BASE + k, p, max_age_days=2, say=say)
    gen, gen_total, gen_pub = read_listing(paths["GEN"])
    pri, pri_total, pri_pub = read_listing(paths["PRI"])
    problems, left_out = [], {}
    LOOSE.clear()

    # the report's own count: a ticket counts as two candidates
    for label, rows, total in (("General", gen, gen_total), ("Primary", pri, pri_total)):
        counted = sum(1 + r[3].count(" / ") for r in rows)
        if total is not None and counted != total:
            problems.append(f"{label} listing: {counted} candidates read, the report says {total}")

    members, officials = roster()
    races, cands = {}, []
    gen_by_race, off_ballot = {}, []
    for head, status, party, raw in gen:
        race = classify(head)
        if not race:
            if not OUT_OF_SCOPE.search(head or ""):
                left_out[("local court" if LOCAL_COURTS.search(head or "") else "other")] = left_out.get(
                    "local court" if LOCAL_COURTS.search(head or "") else "other", 0) + 1
            continue
        rid = f"2026-{STATE}-{race['key']}"
        races.setdefault(rid, race)
        name = ballot_name(raw)
        rec = dict(status=status, party=party, name=name)
        gen_by_race.setdefault(rid, []).append(rec)
        if status:
            off_ballot.append((rid, status, name))

    race_rows = []
    for rid, race in races.items():
        holder = None
        if race.get("chamber"):
            sitting = members.get((race["chamber"], race["district"]), [])
            holder = sitting[0] if len(sitting) == 1 else None
            if len(sitting) != 1:
                problems.append(f"{rid}: {len(sitting)} sitting members on the roster for this seat")
        elif race["key"] == "GOV":
            holder = officials.get("governor")
        elif race["key"] == "SOS":
            holder = officials.get("secretary of state")
        elif race["key"] == "AG":
            holder = officials.get("attorney general")
        note = race["note"]
        if race["key"] == "GOV" and officials.get("lt_governor"):
            note = (note + "; " if note else "") + f"Lieutenant Governor today: {officials['lt_governor']['name']}"
        race["holder"] = holder
        race_rows.append((rid, STATE, race["level"], race["office_kind"], race["office"], None if race["district"] else "Michigan",
                          None if race["district"] else "26", None, race["district"], None, race["special"], race["partisan"],
                          holder["id"] if holder else None, holder["name"] if holder else None, holder["party"] if holder else None,
                          GENERAL, note))

        on = [c for c in gen_by_race[rid] if not c["status"]]
        if not on:
            problems.append(f"{rid}: no candidate on the November ballot")
        inc_name = find_incumbent([c["name"] for c in on], holder, rid) if race.get("chamber") or race["key"] in ("SOS", "AG") else None
        order = 0
        seen = set()
        for c in on:
            if race["partisan"]:
                if not c["party"] or c["party"] == "INCUMBENT":
                    problems.append(f"{rid}: a candidate with no party on the listing ({c['name']})")
                order += 1
                party, code, inc = c["party"], party_code(c["party"]), int(c["name"] == inc_name)
                bo = order
            else:
                party, code, bo = "Nonpartisan office", "N", None
                inc = int(c["party"] == "INCUMBENT")
            if c["name"] in seen:
                problems.append(f"{rid}: the same name twice on the November list ({c['name']})")
            seen.add(c["name"])
            cands.append((rid, "general", GENERAL, c["name"], party, code, bo, inc, 0, None, None, None,
                          holder["id"] if inc and holder and race["partisan"] else None, SRC_GEN, None))

    # primary fields: unmarked candidates on the August list, two or more for one party in one race
    fields, pri_off, pri_counts = {}, 0, {}
    for head, status, party, raw in pri:
        race = classify(head)
        if not race:
            continue
        rid = f"2026-{STATE}-{race['key']}"
        if status:
            pri_off += 1
            continue
        if rid not in races:
            problems.append(f"{rid}: on the August list but not the November list")
            continue
        fields.setdefault((rid, party), []).append(ballot_name(raw))
        pri_counts[rid] = pri_counts.get(rid, 0) + 1
    n_fields = 0
    for (rid, party), names in fields.items():
        if len(names) < 2:
            continue
        if party not in PRIMARY_CODE:
            problems.append(f"{rid}: a primary field for {party!r}, which has no code here")
            continue
        n_fields += 1
        race = races[rid]
        nominees = [c["name"].split(" / ")[0] for c in gen_by_race[rid] if c["party"] == party]
        won = [n for n in names if any(fold(n) == fold(x) or fits(name_parts(n), name_parts(x)) for x in nominees)]
        if len(won) != 1:
            problems.append(f"{rid} {PRIMARY_CODE[party]} primary: {len(won)} of {len(names)} names found on the November list "
                            f"({'nominee not in the field: nominated another way' if nominees and not won else 'read again'})")
        inc_name = find_incumbent(names, race["holder"], rid) if race.get("chamber") else None
        for name in names:
            outcome = "advanced" if name in won and len(won) == 1 else ("lost" if len(won) == 1 or (nominees and not won) else None)
            inc = int(name == inc_name)
            cands.append((rid, f"primary-{PRIMARY_CODE[party]}", PRIMARY, name, party, party_code(party), None, inc, 0, None, None, outcome,
                          race["holder"]["id"] if inc else None, SRC_PRI, None))

    # checks against the seats that must be on the ballot
    for chamber, key, seats in (("Senate", "SS", 38), ("House", "SH", 110)):
        missing = [str(d) for d in range(1, seats + 1) if f"2026-{STATE}-{key}{d}" not in races]
        extra = [r for r in races if r.startswith(f"2026-{STATE}-{key}") and not (1 <= int(r.split(key)[1]) <= seats)]
        if missing or extra:
            problems.append(f"{chamber}: districts missing from the November list {missing}; unexpected {extra}")
    keys = [(c[0], c[1], c[3]) for c in cands]
    if len(keys) != len(set(keys)):
        problems.append("two candidate rows share race, election and name")

    # the local level: the courts, then the county clerks' own lists
    local = local_level(local_dir or os.path.join(cache, "mi", "local"), gen, say, refresh=local_refresh, fetch=local_fetch, only=only)
    courts = local["courts"]
    n_court_rows = len(courts["cands"]) + len(courts["off"])
    if n_court_rows != left_out.get("local court", 0):
        problems.append(f"local courts: {left_out.get('local court', 0)} rows on the listing, {n_court_rows} placed in a court race or marked off")
    local_gaps, local_notes, local_sources, _dropped = local_words(local, gen_pub, say)
    all_ids = [r[0] for r in race_rows] + [r[0] for r in courts["races"]] + [r[0] for r in local["races"]]
    if len(all_ids) != len(set(all_ids)):
        raise SystemExit("Michigan: two races share a race id; stopping")
    bad = [i for i in all_ids if not re.fullmatch(rf"2026-{STATE}-[A-Za-z0-9.-]+", i)]
    if bad:
        raise SystemExit(f"Michigan: {len(bad)} race ids are not letters, digits and hyphens; stopping")

    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA)
    con.executescript(EXTRA_SCHEMA)
    with con:
        con.execute("DELETE FROM sl_candidates WHERE race_id IN (SELECT race_id FROM sl_races WHERE state = ?) OR race_id LIKE ?",
                    (STATE, f"2026-{STATE}-%"))
        con.execute("DELETE FROM sl_races WHERE state = ?", (STATE,))
        con.execute("DELETE FROM sl_sources WHERE state = ?", (STATE,))
        con.execute("DELETE FROM sl_places WHERE source_id LIKE 'mi-%'")
        con.execute("DELETE FROM sl_gaps WHERE state = ?", (STATE,))
        con.execute("DELETE FROM sl_notes WHERE state = ?", (STATE,))
        con.executemany("INSERT INTO sl_races VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", race_rows + courts["races"] + local["races"])
        con.executemany("INSERT INTO sl_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", cands + courts["cands"] + local["cands"])
        con.executemany("INSERT INTO sl_places VALUES (?,?,?,?,?)", local["places"])
        con.executemany("INSERT INTO sl_gaps VALUES (?,?,?,?,?,?,?)", local_gaps)
        con.executemany("INSERT INTO sl_notes VALUES (?,?,?,?,?)", local_notes)
        n_gen = sum(len(v) for v in gen_by_race.values())
        con.execute("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", (
            SRC_GEN, STATE, "official candidate list", "Michigan Department of State, Bureau of Elections",
            "Official Candidate Listing, All State and Judicial Offices, General Election, Tuesday, November 3, 2026", BASE + "GEN",
            gen_pub, fetched(paths["GEN"]), sha(paths["GEN"]), n_gen + n_court_rows,
            f"Read: the state offices, both chambers and the Supreme Court and Court of Appeals ({n_gen} rows); marked disqualified or "
            f"withdrawn and left off: {len(off_ballot)}. Also read: the circuit, district and probate judges ({n_court_rows} rows in "
            f"{len(courts['races'])} contests; {len(courts['off'])} marked disqualified or withdrawn and left off), filed under the counties state law puts in "
            "each circuit or district. Nonpartisan races carry no ballot order. Only the office, status, party and name cells are read; the report has no "
            "contact columns."))
        con.execute("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", (
            SRC_PRI, STATE, "official candidate list", "Michigan Department of State, Bureau of Elections",
            "Official Candidate Listing, All State and Judicial Offices, Primary Election, Tuesday, August 4, 2026", BASE + "PRI",
            pri_pub, fetched(paths["PRI"]), sha(paths["PRI"]), sum(pri_counts.values()),
            "Who advanced is read from the November listing; the primary's vote counts are not loaded (the Department's results "
            "site refuses scripts)."))
        con.execute("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", (
            SRC_ROSTER, STATE, "member roster", "Open States people project (CC0), via state_mi.sqlite",
            "Sitting Michigan legislators and statewide officials", "https://github.com/openstates/people",
            "", fetched(ROSTER), "", sum(len(v) for v in members.values()) + len(officials),
            "Used for who holds each seat today and to mark incumbents; names, party and ids only. The holder is the member "
            "elected for that district number (Senate 2022, House 2024); where lines have been redrawn since, the same number may "
            "cover different ground."))
        con.executemany("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", local_sources)
    con.close()

    gen_rows = [c for c in cands if c[1] == "general"]
    ss = sum(1 for c in gen_rows if "-SS" in c[0])
    sh = sum(1 for c in gen_rows if "-SH" in c[0])
    other = len(gen_rows) - ss - sh
    say(f"    Michigan state offices: {len(races)} races, {len(gen_rows)} candidates on the November ballot "
        f"(Senate {ss} in {sum(1 for r in races if '-SS' in r)} seats, House {sh} in {sum(1 for r in races if '-SH' in r)} seats, "
        f"statewide and courts {other}); {len(off_ballot)} disqualified or withdrawn left off; {n_fields} party primaries with a field")
    for rid, cand, member in sorted(set(LOOSE)):
        say(f"    incumbent by the looser rule (read it): {rid} {cand} = {member}")
    bk = courts["by_kind"]
    say(f"    Michigan local courts: {len(courts['races'])} contests (circuit {bk.get('circuit_court', 0)}, district {bk.get('district_court', 0)}, probate "
        f"{bk.get('probate_court', 0)}), {len(courts['cands'])} candidates; {len(courts['off'])} disqualified or withdrawn left off; "
        f"check: {left_out.get('local court', 0)} rows on the listing = {len(courts['cands'])} + {len(courts['off'])}")
    for line in courts["several"]:
        say(f"      note: a district the statute describes by cities alone, in more than one county: {line}")
    by_level = collections.Counter(r[2] for r in local["races"])
    say(f"    Michigan county lists: {len(local['races'])} local contests, {len(local['cands'])} candidates ("
        + ", ".join(f"{k} {v}" for k, v in sorted(by_level.items())) + ")")
    for s in COUNTIES:
        info = local["by_county"].get(s["code"])
        if not info:
            say(f"      {s['name']}: not loaded ({'no list a script can reach' if not s.get('reader') else 'not asked for'})")
            continue
        if "doc" not in info:
            say(f"      {s['name']}: not loaded ({info['why']})")
            continue
        t, counts = info["tally"], info["doc"].get("counts", {})
        rows = counts.get("rows", 0)
        accounted = (t["candidates placed"] + t["rows of state, federal and court contests"] + t["withdrawn, disqualified or resigned, left off"]
                     + counts.get("no candidate filed", 0) + t["rows in contests not placed"] + t["counted once across counties"]
                     + t["rows repeated within a contest"] + t["marked (W), left off"] + sum(v for k, v in counts.items() if "name cells blanked" in k))
        say(f"      {s['name']} (list of {info['doc'].get('fetched')}): {t['contests placed']} local contests, {t['candidates placed']} candidates placed; check: {rows} rows = "
            f"{t['candidates placed']} placed + {t['rows of state, federal and court contests']} state, federal and court + "
            f"{t['withdrawn, disqualified or resigned, left off']} off + {counts.get('no candidate filed', 0)} no-candidate rows + "
            f"{t['counted once across counties']} counted in another county + {t['rows in contests not placed']} not placed"
            + (f" + {t['marked (W), left off']} marked (W)" if t["marked (W), left off"] else "")
            + (f" + {t['rows repeated within a contest']} repeated" if t["rows repeated within a contest"] else "")
            + (f" + {counts.get('name cells blanked', 0)} blanked" if counts.get("name cells blanked") else "")
            + ("" if accounted == rows else f"  (DOES NOT ADD UP: {accounted})"))
        if accounted != rows:
            problems.append(f"{s['name']}: {rows} candidate rows read, {accounted} accounted for")
        odd = {k: v for k, v in counts.items() if k not in ("rows", "no candidate filed", "pages read", "party lines with no candidate") and v}
        if odd:
            say(f"        reader's notes: {', '.join(f'{k} {v}' for k, v in sorted(odd.items()))}")
        for k in ("places named from the list (no single Census entry)", "school districts named from the list (no single entry in the state's list)"):
            if t[k]:
                say(f"        {k}: {t[k]}")
    for code, items in sorted(local["unplaced"].items()):
        say(f"      {code}: {len(items)} contests not placed")
    for listed, official in local["close"]:
        say(f"      school district matched by close spelling (read it): the list's \"{plain_case(listed)}\" = {official}")
    for p in problems + local["problems"]:
        say(f"    CHECK {p}")
    return dict(races=len(races), general=len(gen_rows), senate=ss, house=sh, other=other, off=off_ballot, fields=n_fields,
                problems=problems + local["problems"], left_out=left_out, primary_off=pri_off,
                local=dict(courts=len(courts["races"]), court_candidates=len(courts["cands"]), races=len(local["races"]), candidates=len(local["cands"]),
                           by_level=dict(by_level), gaps=len(local_gaps)))


def show(code, folder=None):
    """The contests of one county's cut-down list, for reading against the source: headings and counts, no names."""
    doc = read_json(os.path.join(folder or LOCAL, f"{code}_2026_general_list.json"))
    if not doc:
        print("no cut-down copy on disk")
        return
    spec = next(s for s in COUNTIES if s["code"] == code)
    print(f"{spec['name']}: {doc.get('title')} | {doc.get('updated')} | fetched {doc.get('fetched')} | {len(doc['contests'])} contests | {doc.get('counts')}")
    for c in doc["contests"]:
        try:
            u = understand(spec, c)
            kind = "state, federal or court" if u is None else f"{u['jtype']} | {u['jname']} | {u['office']} | {u['district'] or ''} {u['seat'] or ''}"
        except ValueError as err:
            kind = f"NOT PLACED: {err}"
        marks = collections.Counter(m or "on the ballot" for _n, _p, m in c["cands"])
        print(f"  [{c['section'] or ''}] [{c['jur'] or ''}] {c['title']} | {c['sub'] or ''} | term {c['term']} | vote {c['vote']} | {c['pos'] or ''} | {dict(marks)}"
              f"{' | none filed' if c['none'] else ''}  ->  {kind}")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", help="the state-and-local ballot database to write Michigan's rows into")
    ap.add_argument("--no-fetch", action="store_true", help="use the cached state listings as they are")
    ap.add_argument("--no-local-fetch", action="store_true", help="use the cut-down county lists and place lists on disk as they are")
    ap.add_argument("--refresh-local", action="store_true", help="ask every county for its list again, even when the copy on disk is fresh")
    ap.add_argument("--show", help="print one county's contests from its cut-down copy (headings and counts, no names)")
    a = ap.parse_args()
    if a.show:
        show(a.show)
    elif a.db:
        load(a.db, fetch=not a.no_fetch, local_fetch=not a.no_local_fetch, local_refresh=a.refresh_local)
    else:
        ap.error("--db or --show is needed")
