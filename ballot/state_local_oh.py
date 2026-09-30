"""
ballot/state_local_oh.py - Ohio's state races on the November 3, 2026 ballot: Governor and Lieutenant Governor (one
ticket), Attorney General, Auditor of State, Secretary of State, Treasurer of State, the two seats on the Supreme Court
(party labels are printed for the court in Ohio), the seventeen odd-numbered State Senate seats (four-year terms; the odd
half is up in 2026, as the May canvass confirms) and all 99 seats of the Ohio House, with each party's May 5 primary field
and its official votes.

Sources, every one official, every one already cached; this loader downloads nothing:
  - The county boards' candidate lists the federal loader reads (ballot/lists/oh.py, cached in ballot_cache/oh/): Franklin,
    Cuyahoga, Lake, Lorain, Stark, Wood, Butler, Union's 46-day notice and Hamilton's 46-day notice. The Secretary of State's
    site and the boards hosted on boe.ohio.gov answer scripts with a Cloudflare challenge and are not read. Each board's
    list carries the statewide races and the legislative districts that reach its county. A race is taken from the first
    list in the order above that carries it; every other list that carries it is checked against it (family names and
    parties). A district that no list read here carries is kept, with the reason in its note and its primary fields, and
    no November candidates: they are never guessed from the primary.
  - The Secretary of State's official canvass of the May 5, 2026 primary, one "Summary Level Official Results" workbook per
    party (Democratic, Republican, Libertarian; carried out of the Browser pane for the federal loader): the Statewide
    Offices, Justice of the Supreme Court and General Assembly sheets. Every candidate column's 88 county rows must add up
    to its Total row. A field is a party's primary with two printed candidates or more (as on the federal side); write-in
    votes count toward its total, and the top vote-getter advanced. The county rows also give the counties a district
    reaches: those where any candidate of any party's primary for it received a vote (Census codes from the Bureau's
    2024 county file).
  - Holders from the Open States roster in state_oh.sqlite (legislators, is_current = 1; the officials table for Governor,
    Lieutenant Governor, Attorney General and Secretary of State). The roster carries no Auditor, Treasurer or justices.

Privacy. The county lists print candidates' addresses, cities, ZIP codes, telephones, e-mail and websites beside the
names. Only these cells are ever turned into kept text: office headings, name, party, status and write-in marks (and
Franklin's term band for the court seats). Each reader takes the cells by position; a name cell stops at the first piece
that begins with a digit (Lake's list can start an address inside its name column), and a name that still holds a
digit, "Box", "@" or a web address stops the loader, which names the list, the race and the row number, never the text.
Nothing but name, office, district, party and write-in marks is stored; no ballot order (Ohio rotates names from precinct
to precinct, R.C. 3505.03, and the lists print them in different orders).

    python -m ballot.state_local_oh --db <path to a test database>
"""

import datetime as dt
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

from ballot.common import fold, name_parts, party_code  # noqa: E402
from ballot.lists import oh as fed  # noqa: E402
from ballot.lists.tx import proper  # noqa: E402
from ballot.match import fits  # noqa: E402
from ballot.pdftext import PDF, join, page_runs  # noqa: E402

STATE, FIPS = "OH", "39"
GENERAL, PRIMARY = "2026-11-03", "2026-05-05"
CACHE = os.path.join(HERE, "ballot_cache")
FOLDER = os.path.join(CACHE, "oh")
ROSTER = os.path.join(HERE, "state_oh.sqlite")
COUNTY_ZIP = os.path.join(HERE, "states_cache", "census", "cb_2024_us_county_500k.zip")
COUNTY_URL = "https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_county_500k.zip"
SRC_COUNTY, SRC_ROSTER = "oh-census-2024-county-codes", "oh-openstates-roster"
ORDER = ("franklin", "cuyahoga", "lake", "lorain", "stark", "wood", "butler", "union", "hamilton")

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

# key -> (level, office_kind, office, roster office)
STATEWIDE = {
    "GOV": ("statewide", "governor", "Governor and Lieutenant Governor", "governor"),
    "AG": ("statewide", "attorney_general", "Attorney General", "attorney general"),
    "AUD": ("statewide", "state_auditor", "Auditor of State", None),
    "SOS": ("statewide", "secretary_of_state", "Secretary of State", "secretary of state"),
    "TREAS": ("statewide", "state_treasurer", "Treasurer of State", None),
}
COURT = {"SC-20270101": "Full term commencing January 1, 2027", "SC-20270102": "Full term commencing January 2, 2027"}
SENATE_UP = list(range(1, 34, 2))
HOUSE_SEATS = 99
PARTY_OF = {"DEM": "Democratic", "REP": "Republican", "LIB": "Libertarian"}
CODE_OF = {v: k for k, v in PARTY_OF.items()}
WRITE_IN_NOTE = "Write-in candidate: the name is not printed on the ballot."
CAPS_NOTE = "Union County's notice prints names in capitals; they are shown here in ordinary capitals."
NO_LIST = ("None of the county boards' candidate lists read here carries this district (the boards on the state's shared "
           "elections site and the Secretary of State's own site answer scripts with a Cloudflare challenge), so its November "
           "candidates are not shown yet; the May 5 primary is shown from the Secretary of State's official canvass.")


class ListError(SystemExit):
    pass


# ---------------------------------------------------------------- the office a heading names

EXCLUDE = re.compile(r"CONGRESS|UNITEDSTATES|U\.?S\.?SENAT|COUNTY|COMMONPLEAS|COURTOFAPPEALS|PROBATE|MUNICIPAL|CITY|VILLAGE|TOWNSHIP|"
                     r"COUNCIL|COMMISSIONER|SCHOOL|CENTRALCOMMITTEE|JUDGE|ISSUE")
DISTRICT = re.compile(r"(\d{1,2})(?:ST|ND|RD|TH)?(?:STATESENATE|OHIOSENATE|OHIOHOUSE|HOUSE|SENATE)?DISTRICT|DISTRICT(\d{1,2})(?!\d)")


def classify(text):
    """The race a heading names (2026-OH-GOV, 2026-OH-SS5, 2026-OH-SH44, 2026-OH-SC-20270101), or None for any other
    office. A court or legislative heading whose seat cannot be read stops the loader rather than being dropped."""
    t = re.sub(r"\s+", "", (text or "").upper())
    if not t or EXCLUDE.search(t):
        return None
    if "SUPREMECOURT" in t:
        m = re.search(r"0?1[/-]0?([12])[/-](?:20)?27", t)
        if not m:
            raise ListError(f"Ohio: a Supreme Court heading without its term date ({len(t)} characters)")
        return f"2026-{STATE}-SC-2027010{m.group(1)}"
    for key, pat in (("SS", r"STATESENAT"), ("SH", r"STATEREPRESENTATIVE|HOUSEOFREPRESENTATIVES|OHIOHOUSE")):
        if re.search(pat, t):
            m = DISTRICT.search(t)
            if not m:
                raise ListError(f"Ohio: a legislative heading without a district number ({key})")
            d = int(m.group(1) or m.group(2))
            if (key == "SS" and d not in SENATE_UP) or (key == "SH" and not 1 <= d <= HOUSE_SEATS):
                raise ListError(f"Ohio: a {key} district {d} that is not on the 2026 ballot")
            return f"2026-{STATE}-{key}{d}"
    if "GOVERNOR" in t:
        return f"2026-{STATE}-GOV"
    if "ATTORNEYGENERAL" in t:
        return f"2026-{STATE}-AG"
    if "SECRETARYOFSTATE" in t:
        return f"2026-{STATE}-SOS"
    if re.search(r"AUDITOR", t):
        return f"2026-{STATE}-AUD"
    if re.search(r"TREASURER", t):
        return f"2026-{STATE}-TREAS"
    return None


# ---------------------------------------------------------------- names: only a name ever leaves a reader

NAME_OK = re.compile(r"^[A-Za-z\u00c0-\u024f][A-Za-z\u00c0-\u024f.'\u2019\- ,\"]*$")
NOT_A_NAME = re.compile(r"\d|@|www|\.com|\.org|\.net|\bbox\b|\bp\.?\s?o\.?\b|\bsuite\b|\bste\b", re.I)


def clean_name(text, where):
    """Spaces tidied, a ticket written 'Governor and Lieutenant Governor', and checked to be a name. The text is never
    shown when the check fails."""
    t = re.sub(r"\s+", " ", (text or "").replace("\u00a0", " ")).strip()
    t = re.sub(r"\s*(?:&|/)\s*|\s+(?:AND|And)\s+", " and ", t).strip()
    t = re.sub(r"\s+and$", "", t)
    if not t or NOT_A_NAME.search(t) or not NAME_OK.match(t):
        raise ListError(f"Ohio: {where} holds something other than a name (the text is not shown); the list's layout may have changed")
    return t


def cut_name(runs, lo, hi):
    """A name cell from the runs between lo and hi: stops at the first piece that starts with a digit or after a wide
    gap, so an address that begins inside the column is never taken in."""
    kept, end = [], None
    for r in sorted((r for r in runs if lo <= r[0] < hi), key=lambda r: r[0]):
        if r[3].strip()[:1].isdigit() or (end is not None and r[0] - end > 18):
            break
        kept.append(r)
        end = r[4]
    return re.split(r"\s\d", join(kept))[0].strip()


def party_word(p, write_in=False):
    p = re.sub(r"\s+", " ", (p or "").strip().strip('"').strip())
    p = fed.WORDS.get(p.upper(), p)
    if re.fullmatch(r"(?i)non-?party(?: candidate)?", p):
        p = "Nonparty"
    if re.fullmatch(r"(?i)other[- ]party(?: candidate)?", p):
        p = "Other-party"
    return p or ("Write-in" if write_in else "No party")


def cand(race, name, party, write_in=False, gone=False, note=None):
    return {"race": race, "name": name, "party": party_word(party, write_in), "write_in": bool(write_in), "gone": bool(gone), "note": note}


# ---------------------------------------------------------------- the nine readers

def franklin(path):
    """Printed turned on its side: each column is a band across the page, each candidate a position along it. Only the
    Name on Ballot, Party, Office, Write-In and term bands are read. A ticket's governor sits on the line before the
    line that carries the office; a name the printer broke into pieces is joined along the band."""
    pdf = PDF(open(path, "rb").read())
    keys = ("Name on Ballot", "Party", "Office", "Write-In", "Full Or Unexpired Term", "Term Commencing")
    band, out = {}, []
    for n, (page, res) in enumerate(pdf.pages(), start=1):
        runs = page_runs(pdf, page, res)
        if not band:
            band = {r[3].strip(): r[1] for r in runs if r[0] < 70 and r[3].strip() in keys}
            if len(band) != len(keys) or not band["Name on Ballot"] < band["Party"] < band["Office"]:
                raise ListError(f"Ohio franklin: the list's bands changed (found {sorted(band)})")

        def cells(k):
            return [(r[0], r[3].strip()) for r in runs if abs(r[1] - band[k]) < 3 and r[0] >= 60 and r[3].strip() != k]
        office, party, wi, term = cells("Office"), cells("Party"), cells("Write-In"), cells("Term Commencing")
        lo, hi = band["Name on Ballot"] - 3, band["Party"] - 3
        pieces = {}
        for r in runs:
            if r[0] >= 60 and lo <= r[1] < hi and r[3].strip() != "Name on Ballot":
                x = next((x for x in pieces if abs(x - r[0]) < 1.5), r[0])
                pieces.setdefault(x, []).append((r[1], r[3]))
        names = {x: re.sub(r"\s+", " ", "".join(t for _y, t in sorted(v))).strip() for x, v in pieces.items()}
        oxs = [x for x, _t in office]
        lead = {}      # office x -> a governor line printed just before it
        for x in names:
            if any(abs(x - ox) < 3 for ox in oxs):
                continue
            nxt = [ox for ox in oxs if 0 < ox - x <= 13]
            if nxt:
                lead[min(nxt)] = names[x]
        for i, (x, text) in enumerate(office):
            tm = [t for x2, t in term if abs(x2 - x) < 3]
            race = classify(text + " " + " ".join(tm))
            if not race:
                continue
            here = [t for x2, t in names.items() if abs(x2 - x) < 3]
            pty = [t for x2, t in party if abs(x2 - x) < 3]
            if len(here) != 1 or len(pty) > 1:
                raise ListError(f"Ohio franklin: row {i + 1} of page {n} does not line up across the list's bands ({race})")
            name = ((lead.get(x, "") + " ") if lead.get(x) else "") + here[0]
            w = any(abs(x2 - x) < 3 and t == "Yes" for x2, t in wi)
            out.append(cand(race, clean_name(name, f"franklin page {n} row {i + 1} ({race})"), pty[0] if pty else "", w))
    return out


def cuyahoga(path):
    """Candidate Name, Party, Filed and Valid columns (the list prints no contact details); each office's heading is a
    'For ...' line with its district and term on the lines under it."""
    out, head, race = [], [], None
    for p, _y, rs in fed.printed_rows(path):
        left = fed.col(rs, 0, 230)
        filed = fed.col(rs, 390, 470)
        if left.startswith("For "):
            head, race = [left], None
            continue
        if head and left.startswith("(") and not re.fullmatch(r"\d{1,2}/\d{1,2}/\d{4}", filed):
            head.append(left)
            continue
        if not re.fullmatch(r"\d{1,2}/\d{1,2}/\d{4}", filed) or not head:
            continue
        if race is None:
            race = classify(" ".join(head)) or ""
        if not race:
            continue
        valid = fed.col(rs, 470, 700)
        name = clean_name(fed.col(rs, 30, 230), f"cuyahoga page {p} ({race})")
        party = fed.col(rs, 230, 390).split("|")[0].strip()
        out.append(cand(race, name, party, "Write-In" in valid, not valid.startswith("Yes")))
    return out


LAKE_PARTY = {"D", "R", "L", "G", "Nonparty", "Non-Party", "Other-party", "Other Party", "Independent"}


def lake(path):
    """Office, Party and Name columns; the address and city columns to the right are never taken in (a name cell stops
    at the first piece that starts with a digit). Offices are grouped under FEDERAL, STATE, COUNTY, JUDICIAL and
    MUNICIPAL OFFICES; only the STATE and JUDICIAL groups are read. A heading's lines run down the first column above
    and beside its PARTY / NAME row; a running mate follows on a line of its own that begins 'and'."""
    out, section, pending, race = [], None, [], None
    table = list(fed.printed_rows(path))
    for i, (p, y, rs) in enumerate(table):
        mid = re.sub(r"\s+", "", cut_name(rs, 250, 500)).upper()
        sec = re.fullmatch(r"(FEDERAL|STATE|COUNTY|JUDICIAL|MUNICIPAL|TOWNSHIP|SCHOOL|VILLAGE|CITY)OFFICES(?:CONTINUED)?", mid)
        if sec:
            section, pending, race = sec.group(1), [], None
            continue
        left, party = fed.col(rs, 0, 185), fed.col(rs, 185, 250)
        if party.replace(" ", "") == "PARTY":
            below = [fed.col(r2, 0, 185) for p2, y2, r2 in table[i + 1:i + 3] if p2 == p and 0 < y - y2 <= 16]
            label = " ".join(pending + [left] + below)
            race = classify(label) if section in ("STATE", "JUDICIAL") else None
            pending = []
            continue
        if party and party not in LAKE_PARTY:
            party = ""      # a long heading spilling into the party column
        name = cut_name(rs, 250, 500) if (party or race) else ""
        if not party and not name:
            if left:
                pending.append(left)
            continue
        pending = []
        if not race:
            continue
        where = f"lake page {p} ({race})"
        if not party and name.lower().startswith("and ") and out and out[-1]["race"] == race:
            out[-1]["name"] = clean_name(out[-1]["name"] + " " + name, where)
            continue
        wi = bool(re.search(r"\(\s*Write-?\s*in\s*\)", name, re.I))
        name = re.sub(r"\s*\(\s*Write-?\s*in\s*\)", "", name, flags=re.I)
        out.append(cand(race, clean_name(name, where), party, wi))
    return out


LORAIN_PARTY = fed.LORAIN_PARTY


def lorain(path):
    """Candidate and Party columns (the contact column is never read). Candidates start at the left margin; an office
    heading is set in a little and may run across the columns (read no further than the Filed column). A ticket's
    name can break after its slash onto the next row, which repeats the party."""
    out, race = [], None
    for p, _y, rs in fed.printed_rows(path):
        x0 = rs[0][0]
        if 25 <= x0 < 40:
            race = classify(fed.col(rs, 0, 520))
            continue
        if x0 >= 25:
            continue
        name, party = fed.col(rs, 15, 185), fed.col(rs, 185, 300)
        if not race or not name:
            continue
        if party not in LORAIN_PARTY:
            raise ListError(f"Ohio lorain: a candidate for {race} with a party the loader does not know (page {p})")
        where = f"lorain page {p} ({race})"
        if out and out[-1]["race"] == race and out[-1]["_open"]:
            out[-1]["name"] = clean_name(out[-1]["_raw"] + " " + name, where)
            out[-1]["_open"] = False
            continue
        wi = party == "Write-In"
        c = cand(race, "", "" if wi else party, wi)
        c["_raw"], c["_open"] = name, name.rstrip().endswith("/")
        c["name"] = name if c["_open"] else clean_name(name, where)
        out.append(c)
    for c in out:
        if c.pop("_open"):
            raise ListError(f"Ohio lorain: a ticket for {c['race']} breaks off at the end of the list")
        c.pop("_raw")
    return out


def stark(path):
    """Status and Name columns under a party heading (the address and telephone columns are never read). A name can wrap
    onto the next line (a line with no status just under a candidate); an office heading has text in the status
    column."""
    out, race, party, last, at = [], None, "", None, None
    for p, y, rs in fed.printed_rows(path):
        left, name = fed.col(rs, 0, 150), fed.col(rs, 150, 280)
        if re.fullmatch(r"\d{1,2}/\d{1,2}/\d{4} \d{1,2}:\d\d:\d\d [AP]M|Page \d+.*", left):
            continue
        if left in fed.STARK_ON or left in fed.STARK_OFF:
            last = None
            if race and name:
                wi = left == "Write In"
                last = cand(race, name, "" if wi else party, wi, left in fed.STARK_OFF)
                out.append(last)
                at = (p, y)
            continue
        if left:
            race, party, last = classify(join([r for r in rs if r[0] < 600])), "", None
            continue
        if not name:
            continue
        if last is not None and at[0] == p and 0 < at[1] - y < 12:
            last["name"] += " " + name
            at = (p, y)
            continue
        party, last = name, None
    for i, c in enumerate(out):
        c["name"] = clean_name(c["name"], f"stark candidate {i + 1} ({c['race']})")
    return out


WOOD_PARTY = re.compile(r"^(Democratic|Republican|Libertarian|Green|Independent|Other-party candidate|Nonparty candidate|Write-In Candidate)$")


def wood(path):
    """A party (or Write-In Candidate) in the first column, the name after it (a running mate in a second name column);
    addresses sit on the next row, which has no party, and are never read."""
    out, race = [], None
    for p, _y, rs in fed.printed_rows(path):
        left = fed.col(rs, 0, 190)
        if WOOD_PARTY.match(left):
            if race:
                wi = left == "Write-In Candidate"
                where = f"wood page {p} ({race})"
                if race.endswith("-GOV"):
                    name = fed.col(rs, 190, 330) + " and " + fed.col(rs, 330, 480)
                else:
                    name = fed.col(rs, 190, 480)
                out.append(cand(race, clean_name(name, where), "" if wi else left, wi))
            continue
        if left and not re.match(r"(Mon|Tues|Wednes|Thurs|Fri|Satur|Sun)day, ", left):
            race = classify(join([r for r in rs if r[0] < 700]))
    return out


def butler(path):
    """One line per candidate: (party) name, then where the candidate files or the petition dates, and Withdrawn.
    Write-in candidates the report prints without names are not read; the report prints its blocks twice."""
    out, race = [], None
    for p, _y, rs in fed.printed_rows(path):
        text = join(rs)
        if not text.startswith("(") and re.search(r"Vote\s*for\s*not", text, re.I):
            race = classify(text)
            continue
        m = re.match(r"^\((\w)\) (.+?)(?: Files with .*| \(P\) .*)?$", text)
        if not (m and race):
            continue
        name = m.group(2).strip()
        name = re.sub(r"\s+Withdrawn$", "", name)
        if name == "Write-in Candidate":
            continue
        letter = m.group(1).upper()
        out.append(cand(race, clean_name(name, f"butler page {p} ({race})"), "" if letter == "N" else letter, False, "Withdrawn" in text))
    seen, kept = {}, []
    for c in out:
        k = (c["race"], c["name"])
        if k in seen:
            if seen[k]["gone"] != c["gone"]:
                raise ListError(f"Ohio butler: the two printings of {c['race']} disagree on who withdrew")
            continue
        seen[k] = c
        kept.append(c)
    return kept


def union(path):
    """The notice's Name of Candidate (Party) and Office columns; each office's block opens on the row that names its
    precincts. Write-in candidates follow a WRITE-IN CANDIDATES line, each after a bullet, a long one wrapping onto the
    next line. The notice prints only the governor's name for a ticket. Reading stops at the issues."""
    blocks = []
    for _p, _y, rs in fed.printed_rows(path):
        name = fed.col(rs, 30, 245)
        if re.match(r"(State|District) Issues?\b", name):
            break
        right = join([r for r in rs if r[0] >= 245])
        if re.search(r"Precincts$", right) and "Name of Candidate" not in join(rs):
            blocks.append({"office": [], "names": []})
        if not blocks:
            continue
        blocks[-1]["office"].append(re.sub(r"\s*All Precincts$", "", right))
        if name:
            blocks[-1]["names"].append(name)
    out = []
    for b in blocks:
        race = classify(" ".join(b["office"]))
        if not race:
            continue
        wi, items = False, []
        for line in b["names"]:
            if line.upper().startswith("WRITE-IN CANDIDATES"):
                wi = True
                continue
            bullet = bool(re.match(r"^[\u2022\x95\ufffd\u00b7]", line))
            line = re.sub(r"^[\u2022\x95\ufffd\u00b7]\s*", "", line)
            if wi and not bullet and items and items[-1][1]:
                items[-1][0] += " " + line
                continue
            items.append([line, wi])
        for i, (line, w) in enumerate(items):
            m = re.match(r"^(.+?)\s*\((Dem|Rep|Lib|Grn)\)$", line)
            name = clean_name(proper(m.group(1) if m else line), f"union {race} row {i + 1}")
            out.append(cand(race, name, m.group(2) if m else "", w, note=CAPS_NOTE))
    return out


HAM_OFFICE = re.compile(r"^(U\.\s?S\.|State |Judge|Justice|Member|County|Governor|Attorney|Auditor|Secretary|Treasurer|Ohio )")


def hamilton(path):
    """The notice's name (x 38-175), office (175-295) and party (295-385) columns; the precinct column is never read.
    Sections open with a title and a 'Name of Candidate' row; an office's block opens where its title starts. A name or
    party that wraps continues on the line just under it; candidates are about two lines apart. Reading stops at the
    county courts."""
    rows = []
    for p, y, rs in fed.printed_rows(path):
        whole = join([r for r in rs if r[0] < 385])
        if re.match(r"County Court|County Offices|Municipal|Township|School", whole):
            break
        rows.append((p, y, fed.col(rs, 38, 175), fed.col(rs, 175, 295), fed.col(rs, 295, 385), "Name of Candidate" in whole))
    drop = set()
    for i, (p, y, *_rest, header) in enumerate(rows):
        if header:
            drop.add(i)
            for j in range(i - 1, -1, -1):      # a section's title lines just above its header row
                if rows[j][0] != p or rows[j][1] - y > 50:
                    break
                drop.add(j)
    blocks, last = [], None
    for i, (p, y, name, office, party, header) in enumerate(rows):
        if i in drop:
            if header:
                last = None
            continue
        if office and HAM_OFFICE.match(office):
            blocks.append({"office": [], "cands": []})
            last = None
        if not blocks:
            continue
        b = blocks[-1]
        if office:
            b["office"].append(office)
        if name:
            if last is not None and last[0] == p and 0 < last[1] - y < 15:
                b["cands"][-1][0] += " " + name
            else:
                b["cands"].append([name, party])
            last = (p, y)
        elif party and b["cands"]:
            b["cands"][-1][1] = (b["cands"][-1][1] + " " + party).strip()
    out = []
    for b in blocks:
        race = classify(" ".join(b["office"]))
        if not race:
            continue
        for k, (name, party) in enumerate(b["cands"]):
            name = re.sub(r"\(Write-\s+In\)", "(Write-In)", name)
            wi = bool(re.search(r"\(Write-?\s?In\)", name, re.I))
            name = re.sub(r"\s*\(Write-?\s?In\)\s*", " ", name, flags=re.I).strip()
            out.append(cand(race, clean_name(name, f"hamilton {race} row {k + 1}"), party, wi))
    return out


READERS = {"franklin": franklin, "cuyahoga": cuyahoga, "lake": lake, "lorain": lorain, "stark": stark, "wood": wood,
           "butler": butler, "union": union, "hamilton": hamilton}


# ---------------------------------------------------------------- the May 5 canvass

SHEETS = ("Statewide Offices", "Justice of the Supreme Court", "General Assembly")


def canvass_race(office):
    o = re.sub(r"\s+", " ", office).strip()
    m = re.fullmatch(r"State Senator - District (\d+)", o)
    if m:
        return f"2026-{STATE}-SS{int(m.group(1))}"
    m = re.fullmatch(r"State Representative - District (\d+)", o)
    if m:
        return f"2026-{STATE}-SH{int(m.group(1))}"
    m = re.fullmatch(r"Justice of the Supreme Court Term Commencing 01/0([12])/2027", o)
    if m:
        return f"2026-{STATE}-SC-2027010{m.group(1)}"
    words = {"Governor and Lieutenant Governor": "GOV", "Attorney General": "AG", "Auditor of State": "AUD",
             "Secretary of State": "SOS", "Treasurer of State": "TREAS"}
    return f"2026-{STATE}-{words[o]}" if o in words else None


def canvass(problems):
    """{(race, party code): [(name, votes, write_in)]}, {race: set of county names}, and the workbooks read. Every
    candidate column's county rows must add up to its Total row."""
    import openpyxl
    fields, counties, files, cols = {}, {}, {}, 0
    for pcode, (fname, url) in fed.PRIMARY_BOOKS.items():
        path = os.path.join(FOLDER, fname)
        if not os.path.exists(path):
            problems.append(f"the {PARTY_OF[pcode]} canvass workbook is not in {FOLDER}")
            continue
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        n = 0
        for sheet in SHEETS:
            if sheet not in wb.sheetnames:
                continue
            rows = [list(r) for r in wb[sheet].iter_rows(values_only=True)]
            head, names, total = rows[0], rows[1], rows[2]
            if "Official Canvass" not in str(head[0]) or str(total[0]).strip() != "Total" or str(names[0]).strip() != "County Name":
                raise ListError(f"Ohio: {fname} sheet {sheet} does not open with the official canvass, County Name and Total rows")
            body = [r for r in rows[4:] if r and r[0] not in (None, "")]
            if len(body) != 88:
                raise ListError(f"Ohio: {fname} sheet {sheet} has {len(body)} county rows, not 88")
            office = None
            for i in range(6, len(names)):
                if i < len(head) and head[i]:
                    office = re.sub(r"\s+", " ", str(head[i])).strip()
                if not names[i] or office is None:
                    continue
                race = canvass_race(office)
                if not race:
                    problems.append(f"canvass {pcode} {sheet}: an office the loader does not know ({office})")
                    continue
                label = re.sub(r"\s+", " ", str(names[i])).strip()
                wi = "(WI)" in label
                if not re.search(r"\((R|D|L)\)$", label):
                    raise ListError(f"Ohio: a candidate heading in {fname} ({sheet}) does not end with a party mark")
                person = re.sub(r"\s*\(WI\)\s*\*?|\s*\((?:R|D|L)\)$", " ", label).strip(" *")
                person = re.sub(r"\s*-\s+|\s+-\s*", "-", re.sub(r"\s+", " ", person))
                votes = int(total[i] or 0)
                county_sum = sum(int(r[i] or 0) for r in body)
                cols += 1
                if county_sum != votes:
                    problems.append(f"canvass {pcode} {race} {person}: county rows add to {county_sum}, Total row says {votes}")
                counties.setdefault(race, set()).update(str(r[0]).strip() for r in body if int(r[i] or 0) > 0)
                fields.setdefault((race, pcode), []).append((clean_name(person, f"canvass {pcode} {race}"), votes, wi))
                n += 1
        files[pcode] = (path, url, n)
    return fields, counties, files, cols


# ---------------------------------------------------------------- roster, counties, matching

def roster(path=ROSTER):
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    members = {}
    for mid, full, first, last, other, party, district, chamber in con.execute(
            "SELECT bioguide_id, official_full, first_name, last_name, other_names, party_name, district, chamber "
            "FROM legislators WHERE is_current = 1"):
        members.setdefault((chamber, str(int(district))), []).append(
            dict(id=mid, name=full or f"{first} {last}", first=first or "", last=last or "", other=other or "", party=party))
    officials = {o: dict(id=i, name=n, party=p) for i, n, o, p in con.execute(
        "SELECT bioguide_id, official_full, office, party_name FROM officials")}
    con.close()
    return members, officials


def census_counties(path=COUNTY_ZIP):
    import shapefile
    z = zipfile.ZipFile(path)
    base = next(n for n in z.namelist() if n.endswith(".dbf"))
    rdr = shapefile.Reader(dbf=io.BytesIO(z.read(base)))
    return {r["NAME"]: r["GEOID"] for r in (x.as_dict() for x in rdr.iterRecords()) if r["STATEFP"] == FIPS}


def person(name):
    """The first person of a ticket, as (given names, family name)."""
    return name_parts(re.split(r"\s+and\s+", name)[0])


def member_forms(m):
    forms = [(fold(m["first"]).split(), fold(m["last"]))] if m.get("last") else []
    forms.append(name_parts(m["name"]))
    for o in (m.get("other") or "").split(";"):
        o = o.strip()
        if o and not re.search(r"\b[A-Z]\.$|^[A-Z]\.", o):
            forms.append(name_parts(o))
    return forms


def find_incumbent(names, member):
    """The one name that fits the sitting member, or None."""
    if not member:
        return None
    forms = member_forms(member)
    hits = [n for n in names if any(fits(person(n), f) for f in forms)]
    return hits[0] if len(set(hits)) == 1 else None


def same_person(a, b):
    return fits(person(a), person(b)) or fold(a) == fold(b)


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def fetched(path):
    return dt.datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d")


# ---------------------------------------------------------------- the load

def load(db_path, say=print, roster_db=ROSTER, county_zip=COUNTY_ZIP):
    problems, checks = [], []

    # 1. the county lists, each read only for its state races
    got, paths = {}, {}
    for key in ORDER:
        path = os.path.join(FOLDER, fed.CARRIED.get(key, f"oh_{key}_2026_general.pdf"))
        paths[key] = path
        if not os.path.exists(path):
            problems.append(f"the {key} list is not in {FOLDER} (the federal loader keeps it there)")
            continue
        got[key] = READERS[key](path)
        if not any(c["race"].endswith("-GOV") for c in got[key]):
            problems.append(f"no Governor race read from the {key} list; its layout may have changed")

    def printed(cands):
        return sorted({(person(c["name"])[1], party_code(c["party"]) if party_code(c["party"]) in "DRLG" else "-")
                       for c in cands if not c["write_in"]})

    chosen, carried = {}, {}
    for key in ORDER:
        if key not in got:
            continue
        on = [c for c in got[key] if not c["gone"]]
        for race in sorted({c["race"] for c in got[key]}):
            carried.setdefault(race, []).append(key)
            here = [c for c in on if c["race"] == race]
            if race not in chosen:
                chosen[race] = (key, here)
                continue
            first_key, first = chosen[race]
            if printed(first) != printed(here):
                checks.append(f"{race}: {first_key} prints {printed(first)}, {key} prints {printed(here)}")
            extra = {person(c["name"])[1] for c in here if c["write_in"]} - {person(c["name"])[1] for c in first if c["write_in"]}
            if extra and key != "butler":
                checks.append(f"{race}: {key} names write-in candidates {sorted(extra)} that {first_key} does not")

    # 2. the canvass, the counties and the roster
    fields, reach, books, ncols = canvass(problems)
    counties = census_counties(county_zip)
    members, officials = roster(roster_db)
    senate_in_canvass = sorted({int(r.split("SS")[1]) for (r, _p) in fields if "-SS" in r})
    if senate_in_canvass != SENATE_UP:
        problems.append(f"the canvass's State Senate districts {senate_in_canvass} are not the odd seventeen")

    # 3. the races
    all_races = [f"2026-{STATE}-{k}" for k in STATEWIDE] + [f"2026-{STATE}-{k}" for k in COURT] + \
                [f"2026-{STATE}-SS{d}" for d in SENATE_UP] + [f"2026-{STATE}-SH{d}" for d in range(1, HOUSE_SEATS + 1)]
    unknown = sorted(set(chosen) - set(all_races))
    if unknown:
        problems.append(f"races read that are not on the 2026 ballot: {unknown}")
    race_rows, cands, holders = {}, [], {}
    for rid in all_races:
        key = rid.split(f"-{STATE}-", 1)[1]
        note, seat, district, cids, holder = [], None, None, None, None
        if key in STATEWIDE:
            level, kind, office, rk = STATEWIDE[key]
            holder = officials.get(rk) if rk else None
            if not rk:
                note.append("The member roster used here (Open States) does not carry this office, so today's holder is not shown.")
            if key == "GOV":
                note.append("The Governor and Lieutenant Governor are elected together, one ticket to a party; each ticket is written "
                            "governor first, as the Secretary of State's canvass writes it.")
                if officials.get("lt_governor"):
                    note.append(f"Lieutenant Governor today: {officials['lt_governor']['name']}.")
        elif key in COURT:
            level, kind, office, seat = "court", "supreme_court", "Justice of the Supreme Court", COURT[key]
            note.append(f"{seat}. Ohio prints the candidates' parties on the ballot for this court. The member roster used here "
                        "does not carry the justices, so today's holder is not shown.")
        else:
            chamber = "Senate" if key.startswith("SS") else "House"
            district = key[2:]
            level, kind = "legislature", ("state_senate" if chamber == "Senate" else "state_house")
            office = "State Senator" if chamber == "Senate" else "State Representative"
            sitting = members.get((chamber, district), [])
            holder = sitting[0] if len(sitting) == 1 else None
            if not sitting:
                note.append("The seat is vacant on the member roster.")
            elif len(sitting) > 1:
                problems.append(f"{rid}: {len(sitting)} sitting members on the roster")
            names = sorted(reach.get(rid, ()))
            bad = [n for n in names if n not in counties]
            if bad:
                raise ListError(f"Ohio: county names in the canvass that are not in the Census file: {bad}")
            cids = json.dumps(sorted(counties[n][2:] for n in names)) if names else None
            if not names:
                problems.append(f"{rid}: no county in the canvass carries this district")
        if rid not in chosen:
            note.append(NO_LIST)
        holders[rid] = holder
        race_rows[rid] = [rid, STATE, level, kind, office, None if district else "Ohio", None if district else FIPS, cids, district,
                          seat, 0, 1, holder["id"] if holder else None, holder["name"] if holder else None,
                          holder["party"] if holder else None, GENERAL, " ".join(note) or None]

    # 4. November candidates
    for rid, (key, here) in sorted(chosen.items()):
        if rid not in race_rows:
            continue
        if not here:
            problems.append(f"{rid}: the {key} list carries the race with no candidate on it")
        holder = holders[rid]
        inc = find_incumbent([c["name"] for c in here], holder) if holder and "-SC-" not in rid else None
        seen = set()
        for c in here:
            if c["name"] in seen:
                problems.append(f"{rid}: {c['name']} twice on the {key} list")
                continue
            seen.add(c["name"])
            note = "; ".join(x for x in (c["note"], WRITE_IN_NOTE if c["write_in"] else None) if x) or None
            code = "W" if c["write_in"] and c["party"] == "Write-in" else fed.code(c["party"])
            is_inc = int(c["name"] == inc)
            cands.append([rid, "general", GENERAL, c["name"], c["party"], code, None, is_inc, int(c["write_in"]), None, None, None,
                          holder["id"] if is_inc else None, f"oh-{key}-2026-general-list", note])

    # 5. primary fields, and every November party nominee checked against the canvass
    nfields = 0
    for (rid, pcode), field in sorted(fields.items()):
        party = PARTY_OF[pcode]
        listed = [c for c in chosen.get(rid, ("", []))[1] if c["party"] == party]
        if listed and not any(same_person(c["name"], n) for c in listed for n, _v, _w in field):
            checks.append(f"{rid} {pcode}: the November list names {[c['name'] for c in listed]}, not among the primary's "
                          f"{[n for n, _v, _w in field]} (a replacement nominee?)")
            if rid in race_rows:
                won = max(field, key=lambda f: f[1])[0]
                extra = (f"The {party} candidate on the November list ({', '.join(c['name'] for c in listed)}) is not the candidate the "
                         f"May 5 primary nominated ({won}); the files read here do not say how the change was made.")
                race_rows[rid][16] = " ".join(x for x in (race_rows[rid][16], extra) if x)
        if sum(1 for _n, _v, wi in field if not wi) < 2:
            continue
        nfields += 1
        total = sum(v for _n, v, _w in field)
        top = max(field, key=lambda f: f[1])
        if sum(1 for f in field if f[1] == top[1]) > 1:
            problems.append(f"{rid} {pcode}: a tie at the top of the primary")
        replaced = bool(listed) and not any(same_person(c["name"], top[0]) for c in listed)
        holder = holders.get(rid)
        inc = find_incumbent([n for n, _v, _w in field], holder) if holder and rid in race_rows and "-SC-" not in rid else None
        for name, votes, wi in field:
            won = name == top[0]
            note = "; ".join(x for x in (
                "Write-in candidate: the name was not printed on the primary ballot." if wi else None,
                f"Won the primary; the November list names {listed[0]['name']} as the party's candidate instead." if won and replaced else None)
                if x) or None
            is_inc = int(name == inc)
            cands.append([rid, f"primary-{pcode}", PRIMARY, name, party, party_code(party), None, is_inc, int(wi), votes,
                          round(100 * votes / total, 1) if total else None, "advanced" if won else "lost",
                          holder["id"] if is_inc else None, f"oh-sos-2026-primary-{pcode.lower()}", note])
    for rid, (key, here) in chosen.items():
        for c in here:
            pc = CODE_OF.get(c["party"])
            if pc and (rid, pc) not in fields:
                checks.append(f"{rid}: {c['name']} is the {c['party']} candidate on the {key} list, but the canvass has no "
                              f"{c['party']} primary for the race")

    # 6. the last look at every stored text: no contact detail can reach the database
    keys = [(c[0], c[1], c[3]) for c in cands]
    if len(keys) != len(set(keys)):
        problems.append("two candidate rows share race, election and name")
    for c in cands:
        if NOT_A_NAME.search(c[3]) or (c[14] and re.search(r"@|www|\d{3}", c[14])):
            raise ListError(f"Ohio: a stored cell for {c[0]} failed the contact-detail check (not shown)")

    # 7. write
    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA)
    with con:
        con.execute("DELETE FROM sl_candidates WHERE race_id IN (SELECT race_id FROM sl_races WHERE state = ?) OR race_id LIKE ?",
                    (STATE, f"2026-{STATE}-%"))
        con.execute("DELETE FROM sl_races WHERE state = ?", (STATE,))
        con.execute("DELETE FROM sl_sources WHERE state = ?", (STATE,))
        con.execute("DELETE FROM sl_places WHERE source_id LIKE ?", (f"{STATE.lower()}-%",))
        con.executemany("INSERT INTO sl_races VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", list(race_rows.values()))
        con.executemany("INSERT INTO sl_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", cands)
        con.executemany("INSERT INTO sl_places VALUES (?,?,?,?,?)",
                        [("county", g, n, json.dumps([g[2:]]), SRC_COUNTY) for n, g in sorted(counties.items())])
        used = {}
        for rid, (key, _h) in chosen.items():
            used.setdefault(key, []).append(rid)
        for key in ORDER:
            if key not in got:
                continue
            board, title, url = fed.LISTS[key]
            mine = sorted(used.get(key, []))
            also = sorted(r for r in {c["race"] for c in got[key]} if r not in mine)
            gone = sum(1 for c in got[key] if c["gone"])
            note = (f"State races taken from this list: {', '.join(short(r) for r in mine) or 'none'}"
                    + (f"; also carries {', '.join(short(r) for r in also)}, checked against the list used" if also else "")
                    + ". Only the office headings and the name, party, status and write-in cells are kept, chosen by position; the "
                      "addresses, cities, telephones, e-mail and websites on the same pages are dropped as the page is read and never "
                      "kept, printed or stored." + (f" Marked withdrawn or removed, left off: {gone}." if gone else "")
                    + (" Write-in candidates the report prints without names are not read." if key == "butler" else "")
                    + (" Carried out of the Browser pane for the federal loader: the board's site answers scripts with a Cloudflare challenge."
                       if key in fed.CARRIED else " Read from the federal loader's cached copy; this loader downloads nothing."))
            con.execute("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", (
                f"oh-{key}-2026-general-list", STATE, "official candidate list", board, title, url, fed.printed_on(key, paths[key]),
                fetched(paths[key]), sha(paths[key]), len(got[key]), note))
        for pcode, (path, url, n) in books.items():
            con.execute("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", (
                f"oh-sos-2026-primary-{pcode.lower()}", STATE, "official results", "Ohio Secretary of State",
                f"Summary Level Official Results for 2026 Primary Election - {PARTY_OF[pcode]} (Official Canvass, May 5, 2026; "
                "Statewide Offices, Justice of the Supreme Court and General Assembly sheets)", url, PRIMARY, fetched(path), sha(path), n,
                "Each candidate's statewide Total row; every column's 88 county rows reconciled to it. A field is two printed candidates "
                "or more; write-in votes count toward its total and the top vote-getter advanced. The counties a district reaches are "
                "those where any of its candidates in any party's primary received a vote (derived). Carried out of the Browser pane for "
                "the federal loader: the Secretary of State's file host answers scripts with a Cloudflare challenge."))
        con.execute("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", (
            SRC_COUNTY, STATE, "county codes", "U.S. Census Bureau", "Cartographic boundary file, counties, 2024 (1:500,000)", COUNTY_URL,
            "2024", fetched(county_zip), sha(county_zip), len(counties),
            "Five-digit county codes (GEOID) for Ohio's 88 counties, matched by name to the canvass's county rows."))
        con.execute("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", (
            SRC_ROSTER, STATE, "member roster", "Open States people project (CC0), via state_oh.sqlite",
            "Sitting Ohio legislators and statewide officials", "https://github.com/openstates/people", "", fetched(roster_db), "",
            sum(len(v) for v in members.values()) + len(officials),
            "Who holds each seat today and which candidate is the sitting member (same chamber and district, the name fits, one fit "
            "only); names, party and ids only. The roster carries no Auditor of State, Treasurer of State or justices."))
    con.close()

    # 8. say what happened
    gen = [c for c in cands if c[1] == "general"]
    ss_on = sorted(r for r in chosen if "-SS" in r)
    sh_on = sorted(r for r in chosen if "-SH" in r)
    sw = [r for r in chosen if "-SS" not in r and "-SH" not in r]
    say(f"    Ohio state offices: {len(race_rows)} races; November lists for {len(sw)} of 7 statewide and court races, "
        f"{len(ss_on)} of 17 Senate seats and {len(sh_on)} of 99 House seats, from {len(set(k for k, _ in chosen.values()))} county "
        f"boards' lists; {len(gen)} candidates on the November ballot ({sum(1 for c in gen if c[8])} certified write-ins, "
        f"{sum(1 for c in gen if c[7])} sitting members); {nfields} party primaries with a field, official votes "
        f"({ncols} canvass columns reconciled)")
    missing_ss = [r.split("SS")[1] for r in race_rows if "-SS" in r and r not in chosen]
    missing_sh = [r.split("SH")[1] for r in race_rows if "-SH" in r and r not in chosen]
    if missing_ss or missing_sh:
        say(f"      no reachable list: Senate {', '.join(missing_ss) or 'none'}; House {', '.join(missing_sh) or 'none'}")
    for c in checks:
        say(f"      check: {c}")
    for p in problems:
        say(f"      CHECK {p}")
    return dict(races=len(race_rows), general=len(gen), senate_lists=len(ss_on), house_lists=len(sh_on), statewide_lists=len(sw),
                fields=nfields, missing_senate=missing_ss, missing_house=missing_sh, checks=checks, problems=problems,
                by_chamber={k: sum(1 for c in gen if k in c[0]) for k in ("-SS", "-SH")})


def short(rid):
    return rid.split(f"-{STATE}-", 1)[1]


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", required=True, help="the state-and-local ballot database to write Ohio's rows into")
    a = ap.parse_args()
    load(a.db)
