"""
ballot/state_local_ne.py - Nebraska's state races on the November 3, 2026 ballot, into ballot_local_2026.sqlite (never
ballot_2026.sqlite): the seats of the one-house Legislature up this year (the 24 even-numbered districts, and District
41 for a two-year term), Governor with Lieutenant Governor (one ticket, one vote), Secretary of State, State Treasurer,
Attorney General, Auditor of Public Accounts, the Public Service Commission seat, the State Board of Education seats and
the University of Nebraska Board of Regents seats on this year's list, with the May 12 primaries that chose the nominees.

Sources, the Secretary of State's own, the same two files the federal loader (ballot/lists/ne.py) reads:

  - Final Statewide General Candidate List, November 3, 2026 General Election (PDF, linked from sos.nebraska.gov/
    elections). A table printed on its side: each candidate is a strip across the page and the column headings sit in a
    strip of their own on the left. Only the bands under Office, District Name, Term, Vote For, Party, Candidate Name and
    Incumbency Status are ever turned into text; City of Residence, Mailing Address and Phone/Email stay inside the file
    and are never read, printed, logged or stored. The federal loader's cached copy is read when it is fresh; otherwise
    the list is fetched into memory and never written to disk whole. What was read (the allowed cells of the state
    offices' strips) is kept as a small JSON extract with the file's SHA-256. The list also carries local district
    boards (natural resources, public power, community colleges, educational service units and the like); they are
    counted and left for the local pages.
  - Official Report of the Board of State Canvassers, Primary Election, May 12, 2026 (the canvass book, PDF, linked as
    "Primary Election Official Results"). Names and vote counts by county only, so it is read from the federal
    loader's cached copy (fetched if missing).

What the record says, and what the loader does with it:
  - The Legislature is nonpartisan: candidates carry no party on either ballot, so party is "Nonpartisan office"
    (code N). The primary is one nonpartisan contest for all voters and the top two advance (the canvass book's own
    rule); a contest appears on the primary ballot however many filed, so every seat has official primary figures. A
    primary becomes a field (election "primary-NP") when two or more candidates were on it. The State Board of Education
    and the Board of Regents work the same way. The seats are stored with
    office_kind state_senate and race ids 2026-NE-SS<district> (the roster files them under the chamber "Legislature").
  - Governor, Secretary of State, Treasurer, Attorney General, Auditor and the Public Service Commission are partisan:
    each party's primary nominates its top vote-getter (primary-REP, primary-DEM, primary-LMN ...). The nominee for
    Governor then chose a running mate; the November list names each ticket, the candidate for Governor first.
  - Who advanced is the one the canvass book checks; every county column is added up and must equal the printed Total,
    and the checks must fall on the top vote-getters. A write-in candidate the report names is kept with write_in 1;
    "Write-In Scatterings" are not a candidate, but they are votes in the contest, so percentages are of every vote
    the report counts in it.
  - The list prints no ballot order. In partisan races candidates are numbered in the list's own order (by party, as
    the federal loader numbers them); nonpartisan candidates get no number, since the list's order is not a stated
    ballot position.
  - Today's holders come from state_ne.sqlite (the Open States roster): senators by district, and the officials table
    for Governor, Attorney General and Secretary of State. The roster does not carry the Treasurer, the Auditor, the
    Public Service Commission, the State Board of Education or the Regents; for those the list's own "Incumbent" mark
    is kept (incumbent 1, no roster id) and the race shows no holder. Only names, parties, districts and ids are read
    from the roster; its e-mail, phone and address columns never are.
  - A candidate is the sitting member (incumbent 1, state_member_id) only when the name fits the seat's holder one to
    one; the list's incumbency mark must agree. A candidate who holds another seat or office in the roster is given
    that id with incumbent 0 and a note, again only when exactly one roster person fits.

Usage: python ballot/state_local_ne.py <database file> [--cache <folder>] [--keep <folder for the list extract>]
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
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from ballot.common import fold, name_parts, party_code          # noqa: E402
from ballot.match import fits                                   # noqa: E402
from ballot.pdftext import PDF, join, page_runs, rows as pdf_rows   # noqa: E402
from states import net                                          # noqa: E402

STATE, FIPS, NAME = "NE", "31", "Nebraska"
GENERAL, PRIMARY = "2026-11-03", "2026-05-12"
PAGE = "https://sos.nebraska.gov/elections"
CACHE = os.path.join(HERE, "ballot_cache")
ROSTER_DB = os.path.join(HERE, "state_ne.sqlite")
COUNTY_ZIP = os.path.join(HERE, "states_cache", "census", "cb_2024_us_county_500k.zip")
LIST_FILE = "ne_2026_general_candidate_filing_list.pdf"
BOOK_FILE = "ne_2026_primary_canvass_book.pdf"
EXTRACT_FILE = "sl_ne_general_list_extract.json"

SRC_LIST = "ne-sos-2026-sl-general-list"
SRC_BOOK = "ne-sos-2026-sl-primary-canvass"
SRC_ROSTER = "ne-openstates-roster-2026"
SRC_COUNTIES = "ne-census-cb-2024-county"

# the only bands of the list ever turned into text; City of Residence, Mailing Address and Phone/Email never are
LIST_KEEP = ("Office", "District Name (if applicable)", "Term", "Vote For", "Party (if applicable)", "Candidate Name",
             "Incumbency Status")
NONPARTISAN = "Nonpartisan office"
CODES = {"Republican": "REP", "Democratic": "DEM", "Libertarian": "LIB", "Legal Marijuana NOW": "LMN"}
CHECK = "✓"

# office -> (race key, level, office_kind, office shown, partisan, by district, roster office, usual term in years)
OFFICES = {
    "governor": ("GOV", "statewide", "governor", "Governor and Lieutenant Governor", 1, False, "governor", 4),
    "sos": ("SOS", "statewide", "secretary_of_state", "Secretary of State", 1, False, "secretary of state", 4),
    "treas": ("TREAS", "statewide", "state_treasurer", "State Treasurer", 1, False, None, 4),
    "ag": ("AG", "statewide", "attorney_general", "Attorney General", 1, False, "attorney general", 4),
    "aud": ("AUD", "statewide", "state_auditor", "Auditor of Public Accounts", 1, False, None, 4),
    "psc": ("PSC", "statewide", "public_service_commissioner", "Public Service Commissioner", 1, True, None, 6),
    "leg": ("SS", "legislature", "state_senate", "Member of the Legislature", 0, True, None, 4),
    "sboe": ("SBOE", "statewide", "state_board_of_education", "Member of the State Board of Education", 0, True, None, 4),
    "regent": ("REG", "statewide", "university_board", "Member of the University of Nebraska Board of Regents", 0, True, None, 6),
}
# the office as the list writes it, and as the canvass book heads it
LIST_OFFICE = {"For Governor and Lt. Governor": "governor", "For Secretary of State": "sos", "For State Treasurer": "treas",
               "For Attorney General": "ag", "For Auditor of Public Accounts": "aud",
               "For Public Service Commissioner": "psc", "For Member of the Legislature": "leg",
               "For Member of the State Board of Education": "sboe", "For University of Nebraska Board of Regents": "regent"}
BOOK_OFFICE = {"Governor": "governor", "Secretary of State": "sos", "State Treasurer": "treas", "Attorney General": "ag",
               "Auditor of Public Accounts": "aud", "Public Service Commissioner": "psc", "Member of the Legislature": "leg",
               "Member of the State Board of Education": "sboe",
               "Member of the Board of Regents of the University of Nebraska": "regent"}
FEDERAL = {"For United States Senator", "For Representative in Congress"}

TITLE = re.compile(r"^(?P<party>.+?)\s*Party\s*Nomination\s*(?:\((?P<contest>[^)]*)\))?\s*(?P<cont>[—–-]\s*continued)?$")
NONE = re.compile(r"^(?P<party>.+?)\s*Party\s*did not make a nomination", re.I)
DISTRICT = re.compile(r"^(?:Legislative\s*)?District\s*(?P<d>\d+)\s*(?:[—–-]\s*(?P<term>.+))?$")
NUMBER = re.compile(r"^\d{1,3}(?:,\d{3})*$")
TERM_WORDS = {"Two": 2, "Four": 4, "Six": 6}

SCHEMA = """
CREATE TABLE IF NOT EXISTS sl_races (race_id TEXT PRIMARY KEY, state TEXT NOT NULL, level TEXT NOT NULL, office_kind TEXT NOT NULL, office TEXT NOT NULL, jurisdiction TEXT, jurisdiction_id TEXT, county_ids TEXT, district TEXT, seat TEXT, special INTEGER NOT NULL DEFAULT 0, partisan INTEGER NOT NULL, holder_id TEXT, holder_name TEXT, holder_party TEXT, election_date TEXT NOT NULL, note TEXT);
CREATE TABLE IF NOT EXISTS sl_candidates (race_id TEXT NOT NULL, election TEXT NOT NULL, election_date TEXT, name TEXT NOT NULL, party TEXT, party_code TEXT, ballot_order INTEGER, incumbent INTEGER NOT NULL DEFAULT 0, write_in INTEGER NOT NULL DEFAULT 0, votes INTEGER, pct REAL, outcome TEXT, state_member_id TEXT, source_id TEXT, note TEXT, PRIMARY KEY (race_id, election, name));
CREATE TABLE IF NOT EXISTS sl_sources (source_id TEXT PRIMARY KEY, state TEXT, kind TEXT, agency TEXT, title TEXT, url TEXT, published TEXT, fetched TEXT, sha256 TEXT, rows INTEGER, note TEXT);
CREATE TABLE IF NOT EXISTS sl_places (kind TEXT NOT NULL, id TEXT NOT NULL, name TEXT NOT NULL, county_ids TEXT, source_id TEXT, PRIMARY KEY (kind, id));
"""


def fail(msg):
    raise SystemExit(f"Nebraska (state races): {msg}")


def race_id(office, district=None):
    key = OFFICES[office][0]
    return f"2026-{STATE}-{key}{district or ''}"


def cells(runs):
    """A printed row's pieces grouped into table cells, [(x0, runs, text, x1)]: a gap wider than six points starts the
    next cell (the federal loader's rule)."""
    out = []
    for r in sorted(runs, key=lambda r: r[0]):
        if out and r[0] - out[-1][2] <= 6:
            out[-1][1].append(r)
            out[-1][2] = max(out[-1][2], r[4])
        else:
            out.append([r[0], [r], r[4]])
    return [(x, rs, join(rs), end) for x, rs, end in out]


# ---------- the November list: allowed bands only ----------

def read_list(data):
    """(printed date, [record]) for every candidate strip of the list; a record holds only the LIST_KEEP bands. The
    City of Residence, Mailing Address and Phone/Email bands are never joined into text."""
    pdf = PDF(data)
    out, printed, titled = [], "", False
    for page, res in pdf.pages():
        runs = page_runs(pdf, page, res)
        heads = {}
        for x0, y0, _s, t, _x1 in runs:
            if 55 <= x0 < 76 and t.strip():
                heads.setdefault(round(y0), []).append((x0, t.strip()))
            elif x0 < 55 and re.fullmatch(r"\d{1,2}/\d{1,2}/20\d\d", t.strip()) and not printed:
                mo, d, y = t.strip().split("/")
                printed = f"{y}-{int(mo):02d}-{int(d):02d}"
            elif x0 < 55 and "November 3, 2026 General Election" in t:
                titled = True
        fields = sorted((y, " ".join(t for _x, t in sorted(v))) for y, v in heads.items())
        names = [n for _y, n in fields]
        if not all(k in names for k in LIST_KEEP):
            fail("the candidate list's column headings changed")
        bands = [(y - 3, (fields[i + 1][0] - 3) if i + 1 < len(fields) else 1e9, n) for i, (y, n) in enumerate(fields)]
        band = lambda y: next((n for lo, hi, n in bands if lo <= y < hi), None)
        starts = sorted({round(x0, 1) for x0, y0, _s, _t, _x1 in runs if x0 >= 76 and band(y0) == "Vote For"})
        for i, sx in enumerate(starts):
            ex = starts[i + 1] if i + 1 < len(starts) else sx + 21
            got = {}
            for x0, y0, _s, t, _x1 in sorted(runs, key=lambda r: (round(r[0], 1), r[1])):
                if sx - 0.5 <= x0 < ex - 0.5:
                    k = band(y0)
                    if k in LIST_KEEP:
                        got.setdefault(k, []).append(t.strip())
            out.append({k: re.sub(r"\s+", " ", " ".join(v)).strip() for k, v in got.items()})
    if not titled:
        fail("the candidate list is no longer the November 3, 2026 General Election")
    return printed, out


def list_links(say):
    """The list's and the canvass book's addresses from the Elections page (the federal loader's own lookup)."""
    from ballot.lists import ne as fed
    for attempt in range(3):
        try:
            return fed.links()
        except (Exception, SystemExit) as e:
            if attempt == 2:
                say(f"    Nebraska (state races): could not read {PAGE} ({e}); the Elections page is given as the address")
                return {}
            time.sleep(3)


def get_list(cache, keep, url, max_age_days, say):
    """The November list's state records: from the federal loader's cached copy when fresh, else fetched into memory
    (never saved whole), else from the saved extract. Returns (printed, all strips counted, state records, local strips,
    sha256, fetched, how)."""
    cached = os.path.join(cache, "ne", LIST_FILE)
    extract = os.path.join(keep, EXTRACT_FILE)
    data = fetched = how = None
    if os.path.exists(cached) and time.time() - os.path.getmtime(cached) < max_age_days * 86400:
        data = open(cached, "rb").read()
        fetched, how = dt.date.fromtimestamp(os.path.getmtime(cached)).isoformat(), "the federal loader's cached copy"
    elif url:
        try:
            data = net.get(url)
            fetched, how = dt.date.today().isoformat(), "fetched into memory, not saved"
        except OSError as e:
            say(f"    Nebraska (state races): the list could not be fetched ({e})")
    if data is None and os.path.exists(cached):
        data = open(cached, "rb").read()
        fetched, how = dt.date.fromtimestamp(os.path.getmtime(cached)).isoformat(), "the federal loader's cached copy (older)"
    if data is None:
        if not os.path.exists(extract):
            fail("the November candidate list could not be read, and no extract of it is kept")
        ex = json.load(open(extract, encoding="utf-8"))
        say(f"    Nebraska (state races): using the saved extract of the list ({ex['fetched']})")
        return ex["printed"], ex["strips"], ex["rows"], ex["local"], ex["sha256"], ex["fetched"], "the saved extract"
    printed, recs = read_list(data)
    sha = hashlib.sha256(data).hexdigest()
    del data
    state, local, unknown = [], 0, []
    for r in recs:
        office = r.get("Office", "")
        if office in LIST_OFFICE:
            state.append({k: r.get(k, "") for k in LIST_KEEP})
        elif office in FEDERAL:
            continue
        elif office.startswith("For "):
            unknown.append(office)
        else:
            local += 1                  # a local district board: left for the local pages
    if unknown:
        fail(f"offices on the list the loader does not know: {sorted(set(unknown))}")
    os.makedirs(keep, exist_ok=True)
    with open(extract, "w", encoding="utf-8") as fh:       # the allowed cells of the state strips only
        json.dump({"url": url or PAGE, "sha256": sha, "fetched": fetched, "printed": printed, "strips": len(recs),
                   "local": local, "columns": list(LIST_KEEP), "rows": state}, fh, ensure_ascii=False, indent=0)
    return printed, len(recs), state, local, sha, fetched, how


# ---------- the canvass book ----------

def book_names(heads, first, lo, hi, where):
    """[(name, checked, kind)] for a table's heading cells; given names sit on the line above where they wrap. kind is
    'cand', 'writein' (a write-in candidate the report names) or 'scatter' (Write-In Scatterings)."""
    pool = [f for f in (first or []) if lo <= f[0] < hi]
    used, out = set(), []
    for c in heads:
        given = ""
        over = [(min(c[3], f[3]) - max(c[0], f[0]), i) for i, f in enumerate(pool)]
        over = [o for o in over if o[0] > 0]
        if over:
            i = max(over)[1]
            if i in used:
                fail(f"a given name in the canvass book sits over two candidates ({where})")
            used.add(i)
            given = pool[i][2]
        family = c[2]
        checked = family.endswith(CHECK)
        family = family.rstrip(CHECK).strip()
        if family == "Scatterings":
            out.append(("Write-in scatterings", False, "scatter"))
        elif family == "(Write-In)":
            out.append((given, checked, "writein"))
        else:
            name = given + family if given.endswith("-") else f"{given} {family}"
            out.append((re.sub(r"\s+", " ", name).strip(), checked, "cand"))
    if len(used) != len(pool):
        fail(f"a given name in the canvass book belongs to no candidate ({where})")
    return out


def canvass(path):
    """({(race, party or None): table}, {race: term words}, {race: set of county names}) for the state offices in the
    canvass book. A table is {"names": [(name, checked, kind)], "total": [...], "sum": [...]}."""
    pdf = PDF(open(path, "rb").read())
    tables, terms, places = {}, {}, defaultdict(set)
    started, office, ctx_district = False, None, None
    for n, (page, res) in enumerate(pdf.pages(), start=1):
        rows = [(y, cells(runs)) for y, runs in pdf_rows(pdf, page, res)]
        texts = [" ".join(c[2] for c in cs) for _y, cs in rows]
        if not started:
            started = any(t == "Statewide Constitutional Offices" for t in texts)
            if not started:
                continue
        if any(t.startswith("Member of Board of Governors") for t in texts):
            break                                   # community colleges and after: local offices
        if any("Auto-advance Rules" in t for t in texts):
            continue                                # the pages that explain each office's rules
        cols = []
        for (y, cs), text in zip(rows, texts):
            where = f"page {n}"
            if re.search(r"Page \| ?\d+$", text):
                continue
            if len(cs) == 1 and text in BOOK_OFFICE:
                office, ctx_district, cols = BOOK_OFFICE[text], None, []
                continue
            kinds = []
            for c in cs:
                t = c[2]
                if NONE.match(t):
                    kinds.append(("none", None))
                elif TITLE.match(t):
                    kinds.append(("title", TITLE.match(t)))
                elif DISTRICT.match(t):
                    kinds.append(("district", DISTRICT.match(t)))
                else:
                    kinds.append((None, None))
            if any(k for k, _m in kinds):
                if not all(k for k, _m in kinds):
                    fail(f"a heading row in the canvass book could not be read ({where}: {text!r})")
                if any(k == "none" for k, _m in kinds):
                    cols = []
                    continue
                new = []
                for i, ((kind, m), c) in enumerate(zip(kinds, cs)):
                    lo = (cs[i - 1][3] + c[0]) / 2 if i else -1e9
                    hi = (c[3] + cs[i + 1][0]) / 2 if i + 1 < len(cs) else 1e9
                    if kind == "district":
                        if office is None:
                            fail(f"a district heading before any office ({where})")
                        d = str(int(m.group("d")))
                        rid = race_id(office, d)
                        if m.group("term"):
                            terms[rid] = m.group("term").strip()
                        if OFFICES[office][4]:                  # partisan: the party tables below carry the district
                            if len(cs) != 1:
                                fail(f"two district headings side by side for a partisan office ({where})")
                            ctx_district = d
                            continue
                        new.append({"lo": lo, "hi": hi, "key": (rid, None), "subs": None, "first": None})
                    else:
                        party = m.group("party").strip()
                        if m.group("contest"):
                            contest = m.group("contest").strip()
                            if contest not in BOOK_OFFICE:
                                fail(f"an unknown contest in the canvass book ({contest!r}, {where})")
                            office, ctx_district = BOOK_OFFICE[contest], None
                        if office is None or not OFFICES[office][4]:
                            fail(f"a party's table for an office that is not partisan ({where}: {text!r})")
                        if OFFICES[office][5] and not ctx_district:
                            fail(f"a party's table with no district heading above it ({where}: {text!r})")
                        new.append({"lo": lo, "hi": hi, "key": (race_id(office, ctx_district if OFFICES[office][5] else None), party),
                                    "subs": None, "first": None})
                cols = new
                continue
            for col in cols:
                part = [c for c in cs if col["lo"] <= c[0] < col["hi"]]
                if not part:
                    continue
                key = col["key"]
                labels = [c for c in part if c[2] == "County"]
                if labels:
                    xs = [c[0] for c in labels]
                    subs = []
                    for i, x in enumerate(xs):
                        lo, hi = x - 3, (xs[i + 1] - 3) if i + 1 < len(xs) else col["hi"]
                        heads = [c for c in part if lo <= c[0] < hi and c[2] != "County"]
                        names = book_names(heads, col["first"], lo, hi, f"{where}, {key[0]}")
                        subs.append((lo, hi, names))
                        t = tables.setdefault(key, {"names": names, "total": None, "sum": [0] * len(names)})
                        if t["names"] != names:
                            fail(f"the canvass table for {key} names different candidates in different places")
                    col["subs"], col["first"] = subs, None
                    continue
                if col["subs"] is None:
                    if any(NUMBER.match(c[2]) for c in part):
                        fail(f"figures before a table's headings in the canvass book ({where}, {key[0]})")
                    col["first"] = part             # given names, on the line above the family names
                    continue
                for lo, hi, names in col["subs"]:
                    sub = [c for c in part if lo <= c[0] < hi]
                    if not sub:
                        continue
                    label, nums = sub[0][2], [c[2] for c in sub[1:]]
                    if NUMBER.match(label) or len(nums) != len(names) or not all(NUMBER.match(v) for v in nums):
                        fail(f"a canvass row for {key} does not line up with its candidates ({where}, {len(nums)} figures)")
                    vals = [int(v.replace(",", "")) for v in nums]
                    t = tables[key]
                    if label == "Total":
                        if t["total"] is not None:
                            fail(f"two Total rows for {key}")
                        t["total"] = vals
                    else:
                        t["sum"] = [a + b for a, b in zip(t["sum"], vals)]
                        places[key[0]].add(label)
    if not tables:
        fail("no state tables were found in the canvass book")
    for key, t in tables.items():
        if t["total"] is None:
            fail(f"no Total row for {key}")
        if t["total"] != t["sum"]:
            fail(f"the counties for {key} add up to {t['sum']}, the report's Total is {t['total']}")
        cand = [(v, i) for i, ((_n, _c, kind), v) in enumerate(zip(t["names"], t["total"])) if kind != "scatter"]
        marks = {i for i, (_n, c, _k) in enumerate(t["names"]) if c}
        k = 1 if key[1] else 2                      # a party nominates one; a nonpartisan primary advances two
        want = min(k, len(cand))
        top = sorted(cand, reverse=True)
        if len(marks) != want or any(v < top[want - 1][0] for v, i in cand if i in marks):
            fail(f"the check marks for {key} are not on the top {want} vote-getter(s)")
    return tables, terms, places


# ---------- the roster: names, parties, districts and ids only ----------

def roster():
    con = sqlite3.connect(ROSTER_DB)
    seats = defaultdict(list)
    for bid, first, last, full, party, district in con.execute(
            "SELECT bioguide_id, first_name, last_name, official_full, party_name, district FROM legislators "
            "WHERE is_current = 1 AND chamber = 'Legislature'"):
        seats[str(district)].append({"id": bid, "first": first or "", "last": last or "", "full": full or f"{first} {last}",
                                     "party": party, "district": str(district), "label": None})
    offices = {}
    for bid, first, last, full, office, label, party in con.execute(
            "SELECT bioguide_id, first_name, last_name, official_full, office, office_label, party_name FROM officials"):
        offices[office] = {"id": bid, "first": first or "", "last": last or "", "full": full or f"{first} {last}",
                           "party": party, "district": None, "label": label}
    as_of = (con.execute("SELECT MAX(updated_at) FROM legislators").fetchone()[0] or "")[:10]
    con.close()
    return seats, offices, as_of


def person_fits(name, p):
    cand = name_parts(name)
    return fits(cand, (fold(p["first"]).split(), fold(p["last"]))) or fits(cand, name_parts(p["full"]))


def same_person(a, b):
    return fold(a) == fold(b) or fits(name_parts(a), name_parts(b))


def ticket_head(name):
    """'Jim Pillen and Joe Kelly' -> 'Jim Pillen' (the list names the candidate for Governor first)."""
    return re.split(r"\s+(?:&|and)\s+", name, maxsplit=1)[0]


def counties(path=COUNTY_ZIP):
    """{folded county name: (GEOID, "Adams County")} for Nebraska from the Census Bureau's cartographic county file."""
    import shapefile                                   # pyshp
    z = zipfile.ZipFile(path)
    base = next(n[:-4] for n in z.namelist() if n.endswith(".dbf"))
    rdr = shapefile.Reader(dbf=io.BytesIO(z.read(base + ".dbf")))
    fields = [f[0] for f in rdr.fields[1:]]
    out = {}
    for rec in rdr.iterRecords():
        rec = dict(zip(fields, rec))
        if str(rec.get("STATEFP")) == FIPS:
            out[fold(str(rec["NAME"]))] = (str(rec["GEOID"]), str(rec["NAMELSAD"]))
    if len(out) != 93:
        fail(f"the county file gives {len(out)} Nebraska counties, not 93")
    return out


def sha_of(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest() if path and os.path.exists(path) else ""


def mdate(path):
    return dt.date.fromtimestamp(os.path.getmtime(path)).isoformat() if os.path.exists(path) else ""


# ---------- the load ----------

def load(db_path, say=print, cache=CACHE, keep=None):
    keep = keep or os.path.join(cache, "ne")
    seats, offices, as_of = roster()
    url = list_links(say)
    book_path = os.path.join(cache, "ne", BOOK_FILE)
    if not os.path.exists(book_path):
        if not url.get("canvass"):
            fail("the canvass book is not cached and its address could not be found")
        net.download(url["canvass"], book_path, max_age_days=30, say=say)
    printed, strips, listed, local, list_sha, list_fetched, list_how = get_list(cache, keep, url.get("list"), 7, say)
    tables, terms, places = canvass(book_path)
    cmap = counties()
    checks = []

    # ---- races: every state contest on the November list
    races, gen = {}, defaultdict(list)
    for r in listed:
        office = LIST_OFFICE[r["Office"]]
        key, level, kind, shown, partisan, by_district, roster_office, usual = OFFICES[office]
        d = None
        if by_district:
            m = re.fullmatch(r"District 0*(\d+)", r["District Name (if applicable)"])
            if not m:
                fail(f"a district the loader cannot read for {shown}: {r['District Name (if applicable)']!r}")
            d = m.group(1)
        elif r["District Name (if applicable)"]:
            fail(f"a district on a statewide office's strip ({shown})")
        if r["Vote For"] != "1" or not r["Candidate Name"]:
            fail(f"a candidate strip for {shown} {d or ''} did not read whole")
        if bool(partisan) != bool(r["Party (if applicable)"]):
            fail(f"a strip for {shown} {d or ''} {'has no party' if partisan else 'carries a party'}")
        if r["Incumbency Status"] not in ("Incumbent", "Nonincumbent"):
            fail(f"an incumbency mark the loader does not know ({shown} {d or ''})")
        rid = race_id(office, d)
        term = int(r["Term"]) if r["Term"].isdigit() else None
        info = races.setdefault(rid, {"office": office, "level": level, "office_kind": kind, "shown": shown,
                                      "partisan": partisan, "district": d, "roster": roster_office, "usual": usual,
                                      "term": term})
        if info["term"] != term:
            fail(f"the candidates for {rid} are listed with different terms")
        gen[rid].append(r)

    # ---- holders
    holders, notes = {}, defaultdict(list)
    for rid, i in races.items():
        if i["office"] == "leg":
            holders[rid] = seats.get(i["district"], [])
            if not holders[rid]:
                notes[rid].append(f"The Open States roster ({as_of}) lists no sitting senator for this district.")
        elif i["roster"]:
            h = offices.get(i["roster"])
            holders[rid] = [h] if h else []
            if not h:
                notes[rid].append("The Open States roster lists no holder of this office today.")
        else:
            holders[rid] = []
            notes[rid].append("The Open States roster this site uses does not carry this office, so today's holder is not "
                              "shown; the Secretary of State's list marks which candidate, if any, is the incumbent.")

    # ---- terms and special elections, from the list, checked against the canvass book's headings
    for rid, i in races.items():
        t, book = i["term"], terms.get(rid)
        book_years = TERM_WORDS.get(book.split()[0]) if book else None
        if book and book_years != t:
            checks.append(f"{rid}: the November list gives a {t}-year term, the canvass book's heading says \"{book}\"")
            notes[rid].append(f"The Secretary of State's November list gives this seat a {t}-year term; the canvass book's "
                              f"heading for the May 12 primary says \"{book}\".")
            i["special"] = 0
        else:
            i["special"] = 1 if t and t < i["usual"] else 0
            if i["special"]:
                notes[rid].append(f"An election for a {t}-year term, not the usual {i['usual']} years (the November list and "
                                  "the canvass book both say so).")
    for rid, i in races.items():
        if i["office"] == "leg":
            notes[rid].insert(0, "Nebraska's Legislature has one house, elected on a nonpartisan ballot: candidates carry no "
                                 "party. The top two from the May 12 primary are on the November ballot.")
        elif not i["partisan"]:
            notes[rid].insert(0, "A nonpartisan office: the top two from the May 12 primary are on the November ballot.")
    notes[race_id("governor")].insert(0, "Nebraska elects the Governor and Lieutenant Governor together, on one vote. A "
                                         "party's winner in the May 12 primary then chose a running mate (the canvass book's "
                                         "rule, section 32-619.01); the list names each ticket, the candidate for Governor first.")

    everyone = [p for ps in seats.values() for p in ps] + list(offices.values())

    def where_serves(p):
        return (f"Serves today in the Nebraska Legislature, District {p['district']}." if p["district"]
                else f"Serves today as {p['label']}.")

    def sitting(rid, names):
        """{name: (member id, incumbent, note)}: a one-to-one fit with the seat's holders; else exactly one other roster
        person (another district's senator, or a statewide official)."""
        out, hs = {}, holders[rid]
        heads = {n: ticket_head(n) if rid.endswith("-GOV") else n for n in names}
        pairs = [(n, h) for n in names for h in hs if person_fits(heads[n], h)]
        for n, h in pairs:
            if sum(1 for a, _ in pairs if a == n) == 1 and sum(1 for _, b in pairs if b["id"] == h["id"]) == 1:
                out[n] = (h["id"], 1, None)
        for n in names:
            if n in out:
                continue
            got = [p for p in everyone if not any(p["id"] == h["id"] for h in hs) and person_fits(heads[n], p)]
            if len(got) == 1:
                out[n] = (got[0]["id"], 0, where_serves(got[0]))
        return out

    cand = []

    # ---- the November ballot
    list_inc = {}                                           # race -> the name the list marks Incumbent
    for rid, rows in gen.items():
        i = races[rid]
        names = [r["Candidate Name"] for r in rows]
        if len(set(fold(n) for n in names)) != len(names):
            fail(f"the same name twice on the list for {rid}")
        fit = sitting(rid, names)
        order = 0
        for r in rows:
            name = r["Candidate Name"]
            marked = r["Incumbency Status"] == "Incumbent"
            if marked:
                list_inc[rid] = name
            mid, inc, note = fit.get(name, (None, 0, None))
            n = [note] if note else []
            if holders[rid]:
                if marked != bool(inc):
                    checks.append(f"{rid}: the list marks {name} {'Incumbent' if marked else 'Nonincumbent'}, the roster "
                                  f"{'does not agree' if marked else 'fits the seat holder'}")
            elif marked:
                inc = 1
                n.append("Marked as the incumbent on the Secretary of State's list.")
            if i["partisan"]:
                party = r["Party (if applicable)"]
                code = party_code(party)
                order += 1
                bo = order
                pc = CODES.get(party)
                t = tables.get((rid, party))
                if t is None:
                    n.append(f"There was no {party} primary for this office on May 12; named afterwards (the list does not "
                             "say how).")
                elif not any(c and same_person(ticket_head(name), nm) for nm, c, _k in t["names"]):
                    n.append(f"Not the nominee the canvass book checks in the May 12 {party} primary.")
                    checks.append(f"{rid}: {name} ({party}) on the November list is not the checked nominee of the primary")
            else:
                party, code, bo = NONPARTISAN, "N", None
            cand.append((rid, "general", GENERAL, name, party, code, bo, inc, 0, None, None, None, mid, SRC_LIST,
                         " ".join(n) or None))

    # ---- the May 12 primaries
    unused = sorted(set(k[0] for k in tables) - set(races))
    if unused:
        checks.append(f"the canvass book has state tables for contests not on the November list: {unused}")
    fields = Counter()
    for (rid, party), t in sorted(tables.items(), key=lambda kv: (kv[0][0], kv[0][1] or "")):
        if rid not in races:
            continue
        i = races[rid]
        real = [(nm, c, k, v) for (nm, c, k), v in zip(t["names"], t["total"]) if k != "scatter"]
        total = sum(t["total"])
        # the November list must carry every one who advanced (a partisan nominee for Governor heads a ticket)
        on_list = [r["Candidate Name"] for r in gen[rid] if (not party or r["Party (if applicable)"] == party)]
        for nm, c, k, _v in real:
            there = any(same_person(nm, ticket_head(x)) for x in on_list)
            if c and not there:
                checks.append(f"{rid}: {nm} advanced from the {party or 'nonpartisan'} primary but is not on the November list")
            if not c and there and not party:
                checks.append(f"{rid}: {nm} lost the primary but is on the November list")
        if not party and len(on_list) != sum(1 for _nm, c, _k, _v in real if c):
            checks.append(f"{rid}: {len(on_list)} on the November list, {sum(1 for x in real if x[1])} advanced from the primary")
        if len(real) < 2:
            continue
        fields[i["office_kind"] if i["office"] == "leg" else "statewide"] += 1
        fit = sitting(rid, [nm for nm, *_ in real])
        code = CODES.get(party) or re.sub(r"[^A-Z]", "", (party or "").upper())[:3] if party else "NP"
        for nm, c, k, v in real:
            mid, inc, note = fit.get(nm, (None, 0, None))
            n = [note] if note else []
            if not holders[rid] and rid in list_inc and same_person(nm, list_inc[rid]):
                inc = 1
            if c and party and not any(same_person(nm, ticket_head(x)) for x in on_list):
                n.append("Won the nomination; not on the Secretary of State's final list of candidates for November.")
            cand.append((rid, f"primary-{code}", PRIMARY, nm, party or NONPARTISAN, party_code(party) if party else "N",
                         None, inc, 1 if k == "writein" else 0, v, round(100 * v / total, 1) if total else None,
                         "advanced" if c else "lost", mid, SRC_BOOK, " ".join(n) or None))

    # ---- checks on the whole
    keys = Counter((c[0], c[1], c[3]) for c in cand)
    dup = [k for k, v in keys.items() if v > 1]
    if dup:
        fail(f"the same name twice in one election: {dup}")
    gen_rows = [c for c in cand if c[1] == "general"]
    if len(gen_rows) != len(listed):
        fail(f"{len(gen_rows)} November rows written for {len(listed)} state strips on the list")
    leg = sorted(int(i["district"]) for i in races.values() if i["office"] == "leg" and not i["special"])
    if leg != list(range(2, 49, 2)):
        checks.append(f"the regular Legislature seats on the list are not the 24 even-numbered districts: {leg}")
    extra = sorted(int(i["district"]) for i in races.values() if i["office"] == "leg" and i["special"])
    missing_statewide = sorted(k for k in ("governor", "sos", "treas", "ag", "aud") if race_id(k) not in races)
    if missing_statewide:
        checks.append(f"statewide offices not on the list: {missing_statewide}")
    no_primary = sorted(rid for rid, i in races.items() if not i["partisan"] and (rid, None) not in tables)
    if no_primary:
        checks.append(f"nonpartisan contests with no table in the canvass book: {no_primary}")

    race_rows = []
    for rid, i in sorted(races.items()):
        hs = holders[rid]
        cids = None
        if i["district"]:
            got = places.get(rid, set())
            unknown = sorted(p for p in got if fold(p) not in cmap)
            if unknown:
                fail(f"county names in the canvass book not in the Census file: {unknown}")
            if got:
                cids = ",".join(sorted({cmap[fold(p)][0] for p in got}))
            else:
                checks.append(f"{rid}: no county rows in the canvass book, so no counties for the race")
        hparty = ", ".join(dict.fromkeys(h["party"] for h in hs if h["party"])) or None
        if i["partisan"] and hparty == "Nonpartisan":
            checks.append(f"{rid}: the roster gives the holder's party as Nonpartisan for a partisan office; left empty")
            hparty = None
        race_rows.append((rid, STATE, i["level"], i["office_kind"], i["shown"], NAME, FIPS, cids, i["district"], None,
                          i["special"], i["partisan"], ",".join(h["id"] for h in hs) or None,
                          " and ".join(h["full"] for h in hs) or None, hparty, GENERAL, " ".join(notes[rid]) or None))

    place_rows = [("county", geoid, full, None, SRC_COUNTIES) for geoid, full in sorted(cmap.values())]
    n_book = sum(len([x for x in t["names"] if x[2] != "scatter"]) for k, t in tables.items() if k[0] in races)
    src = [
        (SRC_LIST, STATE, "official candidate list", "Nebraska Secretary of State",
         "Final Statewide General Candidate List, November 3, 2026 General Election", url.get("list") or PAGE, printed,
         list_fetched, list_sha, len(listed),
         f"Read from {list_how}. Of {strips} candidate strips, the {len(listed)} for state offices and the Legislature are kept "
         "(Office, District Name, Term, Vote For, Party, Candidate Name, Incumbency Status only); City of Residence, Mailing "
         f"Address and Phone/Email are never read. {local} strips for local district boards are left for the local pages, and "
         "Congress for the federal pages. The list prints no ballot order: partisan candidates are numbered in the list's "
         "order, nonpartisan ones are not numbered. It has no withdrawn or write-in entries."),
        (SRC_BOOK, STATE, "official results", "Nebraska Board of State Canvassers (compiled by the Secretary of State)",
         "Official Report of the Board of State Canvassers: Primary Election, May 12, 2026", url.get("canvass") or PAGE, "",
         mdate(book_path), sha_of(book_path), n_book,
         f"{sum(1 for k in tables if k[0] in races)} state tables read (statewide offices, the Public Service Commission, the "
         "Legislature, the State Board of Education and the Regents); every county column adds up to the printed Total. The one "
         "the report checks advanced (one per party; two in a nonpartisan primary). Percentages are of every vote the report "
         "counts in the contest, write-in scatterings included. Community college boards and later sections are local and "
         "not read."),
        (SRC_ROSTER, STATE, "roster", "Open States people project (CC0)",
         "Nebraska legislators and statewide officials, as loaded into state_ne.sqlite", "https://github.com/openstates/people",
         as_of, as_of, "", sum(len(v) for v in seats.values()) + len(offices),
         "Today's holder of each seat and office (names, parties, districts and ids only). The roster does not carry the "
         "Treasurer, the Auditor, the Public Service Commission, the State Board of Education or the Regents."),
        (SRC_COUNTIES, STATE, "boundaries", "U.S. Census Bureau",
         "Cartographic boundary file, counties, 2024, 1:500,000 (cb_2024_us_county_500k)",
         "https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_county_500k.zip", "", mdate(COUNTY_ZIP),
         sha_of(COUNTY_ZIP), len(place_rows),
         "Nebraska's 93 counties: names and GEOIDs only. A district race's county_ids are the counties the canvass book lists "
         "under it."),
    ]

    con = sqlite3.connect(db_path)
    try:
        con.executescript(SCHEMA)
        with con:
            con.execute("DELETE FROM sl_candidates WHERE race_id IN (SELECT race_id FROM sl_races WHERE state = ?) OR race_id LIKE ?",
                        (STATE, f"2026-{STATE}-%"))
            con.execute("DELETE FROM sl_races WHERE state = ?", (STATE,))
            con.execute("DELETE FROM sl_sources WHERE state = ?", (STATE,))
            con.execute("DELETE FROM sl_places WHERE source_id LIKE 'ne-%'")
            con.executemany("INSERT INTO sl_races VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", race_rows)
            con.executemany("INSERT INTO sl_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", cand)
            con.executemany("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", src)
            con.executemany("INSERT INTO sl_places VALUES (?,?,?,?,?)", place_rows)
    finally:
        con.close()

    # ---- the report: counts only
    kind_of = lambda rid: races[rid]["office_kind"] if races[rid]["office"] == "leg" else "statewide"
    by = Counter(kind_of(rid) for rid in races)
    g = Counter(kind_of(c[0]) for c in gen_rows)
    per = Counter(c[0] for c in gen_rows)
    one = Counter(kind_of(rid) for rid, v in per.items() if v == 1)
    inc = Counter(kind_of(c[0]) for c in gen_rows if c[7])
    say(f"    Nebraska (state races): {by['state_senate']} Legislature seats (even districts"
        + (f", and District {', '.join(map(str, extra))} for a shorter term" if extra else "")
        + f"), {by['statewide']} statewide and state-board races; {len(gen_rows)} candidates on the November ballot "
        f"(Legislature {g['state_senate']}, statewide and boards {g['statewide']}; one candidate only: Legislature "
        f"{one['state_senate']}, statewide and boards {one['statewide']}); incumbent on the ballot: Legislature "
        f"{inc['state_senate']}, statewide and boards {inc['statewide']}; primary fields: Legislature "
        f"{fields['state_senate']}, statewide and boards {fields['statewide']}, votes from the official canvass")
    for c in checks:
        say(f"    CHECK Nebraska (state races): {c}")
    return len(cand)


if __name__ == "__main__":
    args = sys.argv[1:]
    opts = {}
    for flag in ("--cache", "--keep"):
        if flag in args:
            i = args.index(flag)
            opts[flag[2:]] = args[i + 1]
            del args[i:i + 2]
    if len(args) != 1:
        raise SystemExit("usage: python ballot/state_local_ne.py <database file> [--cache <folder>] [--keep <folder>]")
    load(args[0], cache=opts.get("cache", CACHE), keep=opts.get("keep"))
