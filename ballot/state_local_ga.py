"""
ballot/state_local_ga.py - Georgia's state races on the November 3, 2026 ballot, into ballot_local_2026.sqlite:

  - the eight constitutional officers elected statewide for four years (all last elected in 2022): Governor,
    Lieutenant Governor (elected on its own, not as a ticket), Secretary of State, Attorney General, Commissioner of
    Agriculture, Commissioner of Insurance, State School Superintendent and Commissioner of Labor;
  - the two seats of the Public Service Commission on this year's ballot, Districts 3 and 5 (a commissioner must live
    in the district, but every voter in the state votes for every seat);
  - all 56 Senate seats and all 180 House seats of the General Assembly (two-year terms: the whole legislature is
    elected every even year);
with each party's primary field (May 19, 2026) and runoff (June 16, 2026) and their official votes. Which offices are
up is taken from a fixed list and checked against the official primary results: every office above must have a party
primary there, and a state office in the results that is not above stops the loader.

Not on the November ballot, so not stored here: the Supreme Court and Court of Appeals seats (nonpartisan, elected on
May 19, 2026 and decided that day: no appellate seat is in the June 16 runoff results), superior court judges and
district attorneys (local), the party questions, and the special election for the rest of Senate District 7's term
(May 19, runoff June 16; it is named in that seat's note). The federal ballot database is never opened here.

Sources, all the Secretary of State's own:
  - the official results of the May 19, 2026 General Primary and of the June 16, 2026 General Primary Runoff, the
    "Total Votes Excel" report of each on results.sos.ga.gov, fetched and cached in ballot_cache/ga/ by the federal
    loader (ballot/lists/ga.py, election_records, which takes only elections the site marks official). Its "Total
    Votes" sheet gives per contest each candidate's ballot name, party and votes and a Total Votes line; its "County
    Results" sheet the same per county. Every state contest is reconciled: the Total Votes line equals the sum of its
    candidates, and every candidate's county figures, and the county Total Votes lines, add up to the statewide figures.
    The results mark an incumbent "(I)"; the mark is taken off the name and used as a check on the roster's holder.
    Georgia nominates by majority: a candidate with more than half the votes advanced; otherwise the two in the runoff
    advanced, and the runoff (stored as runoff-REP, runoff-DEM) was won by the one with more votes. The runoff's pair
    must be the primary's top two.
  - the November ballot: the "Qualified Candidates" download of the Secretary of State's Qualifying Candidate
    Information page (mvp.sos.ga.gov/s/qualifying-candidate-information). Its search runs only after a reCAPTCHA check,
    which only a person answers, so a script never asks it. A person runs the search for the November 3, 2026 General
    Election and presses "Download Qualified candidates"; the CSV (or several) goes in ballot_cache/ga/20261103/, the
    folder the federal loader reads, and this loader reads the state offices in whatever is there. Until then every
    seat is written with its holder and no November candidates, and its note names the nominees the official results
    give (the list would add Libertarian, independent and write-in candidates, and drop anyone who withdrew).
Who holds each seat comes from the Open States roster in state_ga.sqlite (legislators is_current = 1 by chamber and
district; the officials table for Governor, Lieutenant Governor, Secretary of State and Attorney General, the only
statewide offices it carries): ids, names and party only. County codes come from the Census Bureau's 2024 county file
(states_cache/census/), matched by name to the results' county rows; the counties a district reaches are the ones its
primary contests were counted in (derived, and said so).

Privacy. From the qualified-candidates CSV only four columns are ever read, by their headings: CONTEST NAME, CANDIDATE
NAME, CANDIDATE STATUS and POLITICAL PARTY. COUNTY, MUNICIPALITY, QUALIFIED DATE, INCUMBENT, OCCUPATION, EMAIL ADDRESS
and WEBSITE are never read, printed, logged, cached or stored, and the file is never copied. An error names the file,
the contest or the check, never a row. The results carry names, parties and votes only. The roster's contact columns
are never selected. Before anything is written every stored name, party and note is checked for anything that looks
like a contact detail, and the load stops (without showing it) if one does.

Ballot order. Neither source prints the order of names on the November ballot, so no ballot_order is stored.

    python -m ballot.state_local_ga <path to a test database> [--hand <folder with the saved CSV>]
"""

import csv
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
from ballot.lists.ga import ABBR, GONE, LIST_COLS, MVP, bare, election_records, same_person, sheet, shown  # noqa: E402
from ballot.match import fits  # noqa: E402

STATE, FIPS, NAME = "GA", "13", "Georgia"
GENERAL, PRIMARY, RUNOFF = "2026-11-03", "2026-05-19", "2026-06-16"
FOLDER = os.path.join(CACHE, "ga")
HAND = os.path.join(FOLDER, "20261103")
ROSTER = os.path.join(HERE, "state_ga.sqlite")
COUNTY_ZIP = os.path.join(HERE, "states_cache", "census", "cb_2024_us_county_500k.zip")
COUNTY_URL = "https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_county_500k.zip"
TOTAL_COUNTIES = 159
SENATE_SEATS, HOUSE_SEATS = 56, 180
PSC_UP = (3, 5)
AGENCY = "Georgia Secretary of State, Elections Division"
SRC = {"primary": "ga-sos-2026-sl-primary-results", "runoff": "ga-sos-2026-sl-runoff-results"}
SRC_ROSTER, SRC_COUNTY, SRC_LIST = "ga-openstates-roster", "ga-census-2024-county-codes", "ga-sos-2026-sl-general-qualified"
PARTY = {"REP": "Republican", "DEM": "Democratic"}

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

# the statewide offices: results office name -> (race key, office_kind, office shown, roster office in state_ga.sqlite)
STATEWIDE = {
    "Governor": ("GOV", "governor", "Governor", "governor"),
    "Lieutenant Governor": ("LTG", "lieutenant_governor", "Lieutenant Governor", "lt_governor"),
    "Secretary of State": ("SOS", "secretary_of_state", "Secretary of State", "secretary of state"),
    "Attorney General": ("AG", "attorney_general", "Attorney General", "attorney general"),
    "Commissioner of Agriculture": ("AGR", "agriculture_commissioner", "Commissioner of Agriculture", None),
    "Commissioner of Insurance": ("INS", "insurance_commissioner", "Commissioner of Insurance", None),
    "State School Superintendent": ("SPI", "superintendent_of_public_instruction", "State School Superintendent", None),
    "Commissioner of Labor": ("LAB", "labor_commissioner", "Commissioner of Labor", None),
}
OFFICIAL_WORDS = {"governor": "Governor", "lt_governor": "Lieutenant Governor", "secretary of state": "Secretary of State",
                  "attorney general": "Attorney General"}

# results office names: "State Senate - District 5/ Senador Estatal del Distrito 5 - Dem", "PSC - District 3 - Rep"
RESULT_OFFICE = re.compile(r"^(?P<o>.+?)(?: - (?P<p>Rep|Dem))?$")
R_SENATE = re.compile(r"^State Senate - District (\d{1,2})$")
R_HOUSE = re.compile(r"^State House of Representatives - District (\d{1,3})$")
R_PSC = re.compile(r"^PSC - District (\d)$")
R_COURT = re.compile(r"^(Justice - Supreme Court of Georgia|Judge - Court of Appeals of Georgia)\b")
R_LEFT_OUT = re.compile(r"^(US |District Attorney - |Judge - Superior Court - |Party Question \d+)")

# the qualified-candidates list's contest names (its wording for state offices is not known in advance, so several
# forms are read; a contest that looks like a state office but cannot be read stops the loader)
L_FEDERAL = re.compile(r"^(U\.? ?S\.?|United States)\b|\b(Representative in Congress|Congressional District|U\.? ?S\.? (Senate|House))\b", re.I)
L_SPECIAL = re.compile(r"\s*[,(-]?\s*\b(Special(?: Election)?|Unexpired(?: Term)?)\b\s*\)?\s*", re.I)
L_DIST = r"[\s,:-]*(?:District|Dist\.?|No\.?)?\s*(\d{1,3})"
L_SENATE = re.compile(r"^(?:Georgia\s+)?(?:State\s+Senat(?:e|or)|Senat(?:e|or),?\s+State)" + L_DIST + r"$", re.I)
L_HOUSE = re.compile(r"^(?:Georgia\s+)?(?:State\s+(?:House(?:\s+of\s+Representatives)?|Representative)|"
                     r"(?:House\s+of\s+Representatives|Representative),?\s+State)" + L_DIST + r"$", re.I)
L_PSC = re.compile(r"^(?:Georgia\s+)?(?:Public\s+Service\s+Commission(?:er)?|PSC)" + L_DIST + r"$", re.I)
L_STATEWIDE = {
    "GOV": re.compile(r"^(?:Georgia\s+)?Governor$", re.I),
    "LTG": re.compile(r"^(?:Lieutenant|Lt\.?)\s+Governor$", re.I),
    "SOS": re.compile(r"^Secretary\s+of\s+State$", re.I),
    "AG": re.compile(r"^Attorney\s+General$", re.I),
    "AGR": re.compile(r"^(?:Commissioner\s+of\s+Agriculture|Agriculture\s+Commissioner)$", re.I),
    "INS": re.compile(r"^(?:Commissioner\s+of\s+Insurance|Insurance\s+Commissioner)$", re.I),
    "SPI": re.compile(r"^(?:State\s+School\s+Superintendent|Superintendent\s+of\s+Schools,?\s+State)$", re.I),
    "LAB": re.compile(r"^(?:Commissioner\s+of\s+Labor|Labor\s+Commissioner)$", re.I),
}
L_STATE_LIKE = re.compile(r"\b(State\s+Senat|State\s+House|State\s+Representative|Public\s+Service|PSC\b|Governor|Secretary\s+of\s+State|"
                          r"Attorney\s+General|Commissioner\s+of\s+(Agriculture|Insurance|Labor)|School\s+Superintendent|"
                          r"Supreme\s+Court|Court\s+of\s+Appeals)", re.I)

# a last look before anything is written
CONTACT = re.compile(r"@|https?:|www\.|\.(?:com|org|net|gov|us)\b|\d{3}|P\.?\s?O\.?\s+Box|\bSuite\b", re.I)
CONTACT_NOTE = re.compile(r"@|https?:|www\.|\b\d{3}[-.)\s]\s?\d{3}[-.\s]\d{4}\b|\bP\.?\s?O\.?\s+Box\b|\bSuite\b", re.I)

SENATE_NOTE = "Georgia's senators serve two-year terms; all 56 seats are on the ballot in 2026."
LTG_NOTE = "Georgia elects its lieutenant governor on his or her own, not on a ticket with the governor."
PSC_NOTE = "Every voter in Georgia votes for this seat; the commissioner must live in District {d}."
NO_LIST = "The Secretary of State's list of candidates qualified for the November 3 ballot is not loaded yet."
NONE_ON_LIST = "No candidate for this seat is on the Secretary of State's list of qualified candidates."
SPECIAL_NOTE = "An election for the rest of the current term, as the Secretary of State's list names it."
RUNOFF_NOTE = "Went to the June 16, 2026 runoff: no candidate won a majority on May 19."
MARK_NOTE = "Marked as the incumbent in the official results."
NOT_ON_LIST = "Not on the Secretary of State's list of qualified candidates for November 3."
WRITE_IN_NOTE = "Write-in candidate: the name is not printed on the ballot."
CAPS_NOTE = "Georgia's list prints names in capitals; they are shown here in ordinary capitals."


class Unknown(Exception):
    pass


# ------------------------------------------------------------------------------------------------ the results

def result_office(text):
    """(race key, party code or None, special) for a state office as the results name it; 'court' for an appellate seat,
    'out' for an office this loader leaves out (federal, local, party questions); Unknown for anything else."""
    t = re.sub(r"\s+", " ", str(text or "")).strip()
    if not t or R_LEFT_OUT.match(t):
        return "out"
    if R_COURT.match(t):
        return "court"
    m = RESULT_OFFICE.match(t)
    base, code = m.group("o"), (m.group("p") or "").upper() or None
    base = base.split("/")[0].strip()                     # the Spanish translation some contests carry after a slash
    special = 0
    if base.startswith("Special "):
        base, special = base[len("Special "):].strip(), 1
    if base in STATEWIDE:
        return STATEWIDE[base][0], code, special
    for pat, key, top in ((R_SENATE, "SS", SENATE_SEATS), (R_HOUSE, "SH", HOUSE_SEATS), (R_PSC, "PSC", 5)):
        m = pat.match(base)
        if m:
            d = int(m.group(1))
            if not 1 <= d <= top:
                raise Unknown(t)
            return f"{key}{d}", code, special
    raise Unknown(t)


def contests(path):
    """({(key, code, special): {"office", "cands": [(name, votes, marked)], "total", "counties"}}, [differences],
    {"court": n, "out": n}) for every state contest in one results workbook. The differences list the checks that
    failed: the Total Votes line, the county sums, the party column."""
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    out, differ, skipped = {}, [], {"court": [], "out": 0}
    for r in sheet(wb, "Total Votes", ("Office Name", "Ballot Name", "Party", "Total")):
        office = str(r["Office Name"] or "").strip()
        if not office:
            continue
        try:
            got = result_office(office)
        except Unknown:
            raise SystemExit(f"Georgia (state races): an office in {os.path.basename(path)} this loader does not know: {office!r}")
        if got == "court":
            if office not in skipped["court"]:
                skipped["court"].append(office)
            continue
        if got == "out":
            skipped["out"] += 1
            continue
        c = out.setdefault(got, {"office": office, "cands": [], "total": None, "counties": set()})
        raw = str(r["Ballot Name"] or "")
        name, votes = bare(raw), int(r["Total"] or 0)
        if name == "Total Votes":
            c["total"] = votes
            continue
        if got[1] and str(r["Party"] or "").strip() != got[1]:
            differ.append(f"{office}: {name} is listed under party {r['Party']!r}")
        c["cands"].append((name, votes, bool(re.search(r"\(I\)\s*$", raw.strip()))))
    by_office = {c["office"]: k for k, c in out.items()}
    county, county_total = {}, {}
    for r in sheet(wb, "County Results", ("County", "Office Name", "Ballot Name", "Total")):
        k = by_office.get(str(r["Office Name"] or "").strip())
        if not k or not r["County"]:
            continue
        out[k]["counties"].add(str(r["County"]).strip())
        name, votes = bare(r["Ballot Name"]), int(r["Total"] or 0)
        if name == "Total Votes":
            county_total[k] = county_total.get(k, 0) + votes
        elif name != "Ballots Cast":
            county[(k, name)] = county.get((k, name), 0) + votes
    for k, c in out.items():
        s = sum(v for _n, v, _m in c["cands"])
        if c["total"] != s:
            differ.append(f"{c['office']}: Total Votes {c['total']} is not the sum of its candidates ({s})")
        if county_total.get(k) != c["total"]:
            differ.append(f"{c['office']}: the counties add to {county_total.get(k)}, the statewide total is {c['total']}")
        for name, votes, _m in c["cands"]:
            if county.get((k, name)) != votes:
                differ.append(f"{c['office']}: {name}'s counties add to {county.get((k, name))}, statewide {votes}")
        names = [n for n, _v, _m in c["cands"]]
        if len(names) != len(set(names)):
            differ.append(f"{c['office']}: the same ballot name twice")
    return out, differ, skipped


# ------------------------------------------------------------------------------------------------ the November list

def list_office(contest):
    """(race key, special) for a state office as the qualified-candidates list names it; None for a federal or local
    contest (not this loader's); Unknown for a contest that looks like a state office but cannot be read."""
    t = re.sub(r"\s+", " ", contest or "").strip()
    t = t.split("/")[0].strip()
    if not t or L_FEDERAL.search(t):
        return None
    special = int(bool(L_SPECIAL.search(t)))
    base = L_SPECIAL.sub(" ", t).strip(" ,-")
    base = re.sub(r"\s+", " ", base)
    for key, pat in L_STATEWIDE.items():
        if pat.match(base):
            return key, special
    for pat, key, top in ((L_SENATE, "SS", SENATE_SEATS), (L_HOUSE, "SH", HOUSE_SEATS), (L_PSC, "PSC", 5)):
        m = pat.match(base)
        if m:
            d = int(m.group(1))
            if not 1 <= d <= top:
                raise Unknown(t)
            return f"{key}{d}", special
    if L_STATE_LIKE.search(t) and not re.search(r"\bCounty\b|\bCity\b|\bState Court\b|\bMagistrate\b|\bProbate\b", t, re.I):
        raise Unknown(t)
    return None


def november_list(folder):
    """(files, [(file, race key, special, raw name, party as printed, status)]) in the files' own order, from every CSV
    saved in folder; the same row in two files is read once. Only the four columns in LIST_COLS are read, by heading."""
    out, seen = [], set()
    files = sorted(glob.glob(os.path.join(folder, "*.csv"))) if os.path.isdir(folder) else []
    other = 0
    for path in files:
        raw = open(path, "rb").read()
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = raw.decode("cp1252", "replace")
        del raw
        rows = csv.reader(io.StringIO(text))
        head = [h.strip().upper() for h in next(rows, [])]
        if not all(k in head for k in LIST_COLS):
            raise SystemExit(f"Georgia (state races): {os.path.basename(path)} is not the Qualified Candidates download "
                             f"(no {', '.join(LIST_COLS)} columns)")
        idx = {k: head.index(k) for k in LIST_COLS}
        for r in rows:
            rec = {k: (r[i].strip() if i < len(r) else "") for k, i in idx.items()}
            del r
            if not rec["CANDIDATE NAME"]:
                continue
            try:
                got = list_office(rec["CONTEST NAME"])
            except Unknown:
                raise SystemExit(f"Georgia (state races): a contest on {os.path.basename(path)} that looks like a state office but "
                                 f"cannot be read: {re.sub(chr(10), ' ', rec['CONTEST NAME'])[:80]!r}")
            if got is None:
                other += 1
                continue
            k = (got[0], got[1], rec["CANDIDATE NAME"], rec["POLITICAL PARTY"], rec["CANDIDATE STATUS"])
            if k in seen:
                continue
            seen.add(k)
            out.append((os.path.basename(path),) + k)
        del text
    return files, out, other


# ------------------------------------------------------------------------------------------------ the roster

def roster(path):
    """Sitting legislators and the statewide officials the roster carries: ids, names, party, chamber and district
    only (the roster's contact columns are never selected)."""
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    legs = [dict(zip(("id", "first", "last", "full", "other", "party", "chamber", "district"), r)) for r in con.execute(
        "SELECT bioguide_id, first_name, last_name, official_full, other_names, party_name, chamber, district FROM legislators "
        "WHERE is_current = 1")]
    offs = {r[1]: dict(zip(("id", "office", "full", "first", "last", "party"), r)) for r in con.execute(
        "SELECT bioguide_id, office, official_full, first_name, last_name, party_name FROM officials")}
    con.close()
    return legs, offs


def forms(p):
    out = [(fold(p["first"] or "").split(), " ".join(fold(p["last"] or "").split()))]
    if p.get("full"):
        out.append(name_parts(p["full"]))
    out += [name_parts(o.strip()) for o in (p.get("other") or "").split(";") if o.strip() and "," not in o and "." not in o]
    return [f for f in out if f[1]]


def person_fits(name, p):
    """A name on the results or the list fits a roster person: the same family name and a given name that fits. Both
    sides must carry a given name (the roster's other names include the family name alone, which would fit anyone)."""
    cand = name_parts(name)
    return bool(cand[0]) and any(fits(cand, f) for f in forms(p) if f[0])


def same_family(name, p):
    fam = name_parts(name)[1]
    return any(fits((["x"], fam), (["x"], f[1])) for f in forms(p))


def where(p):
    if p.get("office"):
        return f"as {OFFICIAL_WORDS.get(p['office'], p['office'])}"
    return f"in the Georgia {'Senate' if p['chamber'] == 'Senate' else 'House'}, District {int(p['district'])}"


# ------------------------------------------------------------------------------------------------ helpers

def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def mtime(path):
    return dt.datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d")


def county_key(text):
    return re.sub(r"[^a-z]", "", re.sub(r"\s+County$", "", str(text or "").strip(), flags=re.I).lower())


def census_counties(path):
    """{county key: (GEOID, name)} for Georgia from the Census Bureau's county file."""
    import shapefile                                                     # pyshp, in the kit's environment
    z = zipfile.ZipFile(path)
    dbf = next(n for n in z.namelist() if n.endswith(".dbf"))
    rdr = shapefile.Reader(dbf=io.BytesIO(z.read(dbf)))
    return {county_key(r["NAME"]): (r["GEOID"], r["NAME"]) for r in (x.as_dict() for x in rdr.iterRecords()) if r["STATEFP"] == FIPS}


def words_list(items):
    items = list(items)
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


# ------------------------------------------------------------------------------------------------ loading

def load(db_path, say=print, folder=FOLDER, hand=HAND, roster_db=ROSTER, county_zip=COUNTY_ZIP):
    from states import net
    net.patient_lookups()
    os.makedirs(folder, exist_ok=True)
    meta = election_records(folder, say)                 # the cached official workbooks (refetched only when a month old)
    legs, offs = roster(roster_db)
    counties = census_counties(county_zip)
    if len(counties) != TOTAL_COUNTIES:
        raise SystemExit(f"Georgia (state races): the Census county file has {len(counties)} Georgia counties, not {TOTAL_COUNTIES}")
    checks, matched = [], []

    book, differ, skipped = {}, {}, {}
    for kind in ("primary", "runoff"):
        path = os.path.join(folder, meta[kind]["file"])
        if meta[kind].get("sha256") and sha(path) != meta[kind]["sha256"]:
            checks.append(f"{meta[kind]['file']}: its SHA-256 is not the one recorded when it was fetched")
        book[kind], differ[kind], skipped[kind] = contests(path)
    for kind in book:
        for d in differ[kind]:
            checks.append(f"{kind} results: {d}")

    # 1. the seats on the ballot, each with who holds it today
    races = {}

    def add_race(key, special=0, why=None):
        rid = f"2026-{STATE}-{key}" + ("-SPECIAL" if special else "")
        if rid in races:
            return rid
        note, h = [], None
        if key in {v[0] for v in STATEWIDE.values()}:
            _o, (k2, kind, office, roster_office) = next((o, v) for o, v in STATEWIDE.items() if v[0] == key)
            level, jur, jur_id, district, seat = "statewide", NAME, FIPS, None, None
            h = offs.get(roster_office) if roster_office else None
            if kind == "lieutenant_governor":
                note.append(LTG_NOTE)
        elif key.startswith("PSC"):
            d = int(key[3:])
            kind, office, level, jur, jur_id, district, seat = ("public_service_commissioner", "Public Service Commissioner", "statewide",
                                                                NAME, FIPS, None, f"District {d}")
            note.append(PSC_NOTE.format(d=d))
        else:
            d = int(key[2:])
            senate = key.startswith("SS")
            kind = "state_senate" if senate else "state_house"
            office = "State Senator" if senate else "State Representative"
            level, jur, jur_id, district, seat = "legislature", f"{'Senate' if senate else 'House'} District {d}", str(d), str(d), None
            hs = [p for p in legs if p["chamber"] == ("Senate" if senate else "House") and str(p["district"]).strip() == str(d)]
            h = hs[0] if len(hs) == 1 else None
            if len(hs) > 1:
                checks.append(f"{rid}: {len(hs)} sitting members in the roster for this seat; none is taken as the holder")
            if senate and not special:
                note.append(SENATE_NOTE)
            if h is None:
                if not special:
                    checks.append(f"{rid}: no sitting member in the roster for this seat")
                note.append("The roster shows no one holding this seat today.")
        if special:
            note.append(why or SPECIAL_NOTE)
        races[rid] = {"race_id": rid, "state": STATE, "level": level, "office_kind": kind, "office": office, "jurisdiction": jur,
                      "jurisdiction_id": jur_id, "county_ids": None, "district": district, "seat": seat, "special": int(bool(special)),
                      "partisan": 1, "holder_id": h["id"] if h else None, "holder_name": h["full"] if h else None,
                      "holder_party": h["party"] if h else None, "election_date": GENERAL, "note": note, "_holder": h, "_kind": kind,
                      "_key": key}
        return rid

    for _o, (key, *_r) in STATEWIDE.items():
        add_race(key)
    for d in PSC_UP:
        add_race(f"PSC{d}")
    for d in range(1, SENATE_SEATS + 1):
        add_race(f"SS{d}")
    for d in range(1, HOUSE_SEATS + 1):
        add_race(f"SH{d}")

    # every race must have a party primary in the results, and every state contest there must be a race
    in_primary = {f"2026-{STATE}-{k}" for (k, code, sp) in book["primary"] if not sp}
    for rid in races:
        if rid not in in_primary:
            checks.append(f"{rid}: no party primary for this seat in the May 19 results (no one filed in either party)")
    for kind in book:
        for (k, code, sp) in book[kind]:
            if not sp and f"2026-{STATE}-{k}" not in races:
                raise SystemExit(f"Georgia (state races): the {kind} results have a contest for {k}, which is not on this loader's list "
                                 "of offices on the 2026 ballot")
            if not sp and code is None:
                raise SystemExit(f"Georgia (state races): the {kind} results have a contest for {k} with no party")

    # special elections held before November (the rest of a term): named in the seat's note, not stored as a race
    for (k, code, sp), c in book["primary"].items():
        if not sp:
            continue
        rid = f"2026-{STATE}-{k}"
        r = book["runoff"].get((k, code, sp))
        final = r or c
        ranked = sorted(final["cands"], key=lambda x: -x[1])
        clean = lambda n: re.sub(r"\s*\((?:Rep|Dem|Lib|Ind|NP)\)\s*$", "", n).strip()
        decided = len(ranked) >= 2 and ranked[0][1] > ranked[1][1] and (r or ranked[0][1] * 2 > final["total"])
        if rid in races:
            races[rid]["note"].append(
                f"A special election for the rest of the current term was held on May 19, 2026{', with a runoff on June 16' if r else ''}"
                + (f"; the official results show {clean(ranked[0][0])} won it" if decided else "")
                + ". This race is for the full term that begins in January 2027.")
        if not decided:
            checks.append(f"{rid}: the special election's winner cannot be read from the official results")

    # 2. who is who: the holder, the results' incumbent mark, another sitting member
    people = legs + [dict(p, chamber=None, district=None) for p in offs.values()]

    def identify(rid, name, party, marked=False):
        """(incumbent, state_member_id, note) for one name in a race."""
        r = races[rid]
        h = r["_holder"]
        if h is not None and person_fits(name, h):
            return 1, h["id"], None
        if h is not None and marked and same_family(name, h):
            matched.append(f"{rid}: {name} = {h['full']} (the results' incumbent mark and the family name)")
            return 1, h["id"], None
        if h is None and marked:
            return 1, None, MARK_NOTE
        pool = [p for p in people if person_fits(name, p) and (p["party"] or "") == (party or "")]
        if len(pool) == 1:
            return 0, pool[0]["id"], f"Serves today {where(pool[0])}."
        return 0, None, None

    # 3. the primary fields and runoffs, official votes
    cands, nominee, fields, nrunoffs = [], {}, 0, 0
    for (k, code, sp), c in sorted(book["primary"].items(), key=lambda x: (x[0][0], x[0][1] or "")):
        if sp:
            continue
        rid, party = f"2026-{STATE}-{k}", PARTY[code]
        total, ranked = c["total"], sorted(c["cands"], key=lambda x: -x[1])
        h = races[rid]["_holder"]
        for name, _v, marked in c["cands"]:
            if h is not None and marked and not (person_fits(name, h) or same_family(name, h)):
                checks.append(f"{rid}: the results mark {name} as the incumbent, but the roster's holder is {h['full']}")
        if len(c["cands"]) == 1:
            nominee[(rid, code)] = (c["cands"][0][0], False)
            continue
        fields += 1
        went = set()
        if ranked[0][1] * 2 > total:
            winners = {ranked[0][0]}
            nominee[(rid, code)] = (ranked[0][0], False)
        else:
            r = book["runoff"].get((k, code, 0))
            if not r:
                checks.append(f"{rid} {party}: no majority on May 19 and no runoff in the June 16 results")
                winners = set()
            else:
                pair = {n for n, _v, _m in r["cands"]}
                if pair != {ranked[0][0], ranked[1][0]}:
                    checks.append(f"{rid} {party}: the runoff's pair {sorted(pair)} is not the primary's top two")
                winners = went = pair
        for name, votes, marked in c["cands"]:
            inc, mid, n2 = identify(rid, name, party, marked)
            note = " ".join(x for x in (RUNOFF_NOTE if name in went else None, n2) if x) or None
            cands.append([rid, f"primary-{code}", PRIMARY, name, party, party_code(party), None, inc, 0, votes,
                          round(100 * votes / total, 1) if total else None, "advanced" if name in winners else "lost", mid,
                          SRC["primary"], note])
    for (k, code, sp), c in sorted(book["runoff"].items(), key=lambda x: (x[0][0], x[0][1] or "")):
        if sp:
            continue
        rid, party = f"2026-{STATE}-{k}", PARTY[code]
        p = book["primary"].get((k, code, 0))
        if not p:
            checks.append(f"{rid} {party}: a runoff with no May 19 contest")
        elif sorted(p["cands"], key=lambda x: -x[1])[0][1] * 2 > p["total"]:
            checks.append(f"{rid} {party}: a runoff although the May 19 leader had a majority")
        ranked = sorted(c["cands"], key=lambda x: -x[1])
        if len(ranked) != 2 or ranked[0][1] == ranked[1][1]:
            checks.append(f"{rid} {party}: the runoff has {len(ranked)} candidates or a tie")
            continue
        nrunoffs += 1
        nominee[(rid, code)] = (ranked[0][0], True)
        for name, votes, marked in c["cands"]:
            inc, mid, n2 = identify(rid, name, party, marked)
            cands.append([rid, f"runoff-{code}", RUNOFF, name, party, party_code(party), None, inc, 0, votes,
                          round(100 * votes / c["total"], 1) if c["total"] else None, "advanced" if name == ranked[0][0] else "lost", mid,
                          SRC["runoff"], n2])

    # 4. the November ballot, from the qualified-candidates list saved by hand
    files, listed, other_rows = november_list(hand)
    ids = {os.path.basename(f): SRC_LIST + (f"-{i + 1}" if len(files) > 1 else "") for i, f in enumerate(files)}
    general, gone, kinds_listed = [], [], set()
    for src, key, special, raw, printed, status in listed:
        rid = f"2026-{STATE}-{key}" + ("-SPECIAL" if special else "")
        if rid not in races:
            if not special:
                raise SystemExit(f"Georgia (state races): the list names {key}, which is not on this loader's list of offices")
            add_race(key, 1)
        kinds_listed.add(races[rid]["_kind"])
        st = status.lower()
        if any(g in st for g in GONE):
            gone.append((rid, status))
            continue
        write_in = int("write" in (printed + " " + status).lower())
        if not (st.startswith("qualif") or write_in):
            raise SystemExit(f"Georgia (state races): a candidate for {rid} on the list has the status {status!r}; read the list again")
        name, caps = shown(raw)
        p = printed.strip()
        party = ABBR.get(p.upper(), p) or None
        if party is None and not write_in:
            checks.append(f"{rid}: a candidate with no party on the list ({name})")
        inc, mid, n2 = identify(rid, name, party)
        note = " ".join(n for n in (CAPS_NOTE if caps else "", WRITE_IN_NOTE if write_in else "", n2 or "") if n) or None
        general.append([rid, "general", GENERAL, name, party, party_code(party) if party else ("W" if write_in else "O"), None, inc,
                        write_in, None, None, None, mid, ids[src], note])
    if general:
        for rid in {g[0] for g in general}:
            for code in ("R", "D"):
                two = [g[3] for g in general if g[0] == rid and g[5] == code and not g[8]]
                if len(two) > 1:
                    raise SystemExit(f"Georgia (state races): the saved list has {len(two)} candidates of one party for {rid}; it looks "
                                     "like a primary's list, not the November 3 general election's")
        covered = {g[0] for g in general} | {x[0] for x in gone}
        for (rid, code), (name, _ro) in sorted(nominee.items()):
            if rid not in covered:                      # a seat the saved list does not reach is reported below, not marked
                continue
            on = [g[3] for g in general if g[0] == rid and g[5] == code[0] and not g[8]]
            if any(same_person(x, name) for x in on):
                continue
            checks.append(f"{rid}: the official results' {PARTY[code]} nominee, {name}, is not on the November list"
                          + (f" (the list's {PARTY[code]} candidate is {on[0]})" if on else ""))
            final = f"runoff-{code}" if any(c[0] == rid and c[1] == f"runoff-{code}" for c in cands) else f"primary-{code}"
            for c in cands:
                if c[0] == rid and c[1] == final and c[3] == name:
                    c[14] = " ".join(x for x in (c[14], NOT_ON_LIST) if x)
        for rid in covered:
            inc = [g for g in general if g[0] == rid and g[7]]
            if len(inc) > 1:
                for g in inc:
                    g[7], g[12] = 0, None
                checks.append(f"{rid}: more than one name on the list fits the sitting member; none is marked")
        cands = general + cands

    # 5. per race: its counties, and what its note says about the list
    unmatched_counties = set()
    all_geoids = sorted(g for g, _n in counties.values())
    for rid, r in races.items():
        if r["level"] == "statewide":
            r["county_ids"] = json.dumps(all_geoids)
        else:
            seen = set()
            for (k, code, sp), c in book["primary"].items():
                if f"2026-{STATE}-{k}" == rid.replace("-SPECIAL", ""):
                    seen |= c["counties"]
            geo = set()
            for n in seen:
                g = counties.get(county_key(n))
                if g:
                    geo.add(g[0])
                else:
                    unmatched_counties.add(n)
            r["county_ids"] = json.dumps(sorted(geo)) if geo else None
        if r["_holder"] is None and r["level"] == "statewide":
            marks = sorted({n for (k, code, sp), c in book["primary"].items() if not sp and f"2026-{STATE}-{k}" == rid
                            for n, _v, m in c["cands"] if m})
            r["note"].append("The roster used here does not list who holds this office"
                             + (f"; the official primary results mark {words_list(marks)} as the incumbent." if marks else "."))
        on_list = any(c[0] == rid and c[1] == "general" for c in cands)
        if r["_kind"] not in kinds_listed:
            r["note"].append(NO_LIST)
            noms = [(code, nominee[(rid, code)]) for code in ("REP", "DEM") if (rid, code) in nominee]
            if noms:
                r["note"].append("The official primary results name the parties' nominees: " + "; ".join(
                    f"{n} ({PARTY[code]}{', after the June 16 runoff' if ro else ''})" for code, (n, ro) in noms)
                    + ". The list would add any Libertarian, independent and write-in candidates.")
        elif not on_list:
            r["note"].append(NONE_ON_LIST)
            checks.append(f"{rid}: no candidates on the November list")
    for n in sorted(unmatched_counties):
        checks.append(f"a results county row the Census file does not name: {n}")

    # 6. the last look at every stored text: nothing that looks like a contact detail reaches the database
    for c in cands:
        if CONTACT.search(c[3]) or CONTACT.search(c[4] or "") or (c[14] and CONTACT_NOTE.search(c[14])):
            raise SystemExit(f"Georgia (state races): a stored cell for {c[0]} failed the contact-detail check (not shown); read the file again")
    for r in races.values():
        if CONTACT_NOTE.search(" ".join(r["note"])) or CONTACT.search(r["holder_name"] or ""):
            raise SystemExit(f"Georgia (state races): the note or holder for {r['race_id']} failed the contact-detail check (not shown)")
    keys = [(c[0], c[1], c[3]) for c in cands]
    if len(keys) != len(set(keys)):
        raise SystemExit("Georgia (state races): two candidate rows share race, election and name")
    on_ballot = len(listed) - len(gone)
    if on_ballot != len(general):
        raise SystemExit(f"Georgia (state races): {on_ballot} qualified rows read from the list, {len(general)} stored")

    # 7. write Georgia's rows only, in one transaction
    race_rows = [tuple(" ".join(r["note"]) or None if k == "note" else r[k] for k in (
        "race_id", "state", "level", "office_kind", "office", "jurisdiction", "jurisdiction_id", "county_ids", "district", "seat", "special",
        "partisan", "holder_id", "holder_name", "holder_party", "election_date", "note")) for r in races.values()]
    place_rows = [("county", g, f"{n} County", json.dumps([g]), SRC_COUNTY) for g, n in sorted(counties.values())]
    for rid, r in sorted(races.items()):
        if r["level"] == "legislature" and not r["special"]:
            place_rows.append(("senate" if r["_kind"] == "state_senate" else "house", f"{STATE}-{r['district']}", r["jurisdiction"],
                               r["county_ids"], SRC["primary"] if r["county_ids"] else SRC_ROSTER))
    gen = [c for c in cands if c[1] == "general"]
    prim = [c for c in cands if c[1] != "general"]
    courts = skipped["primary"]["court"]
    court_runoff = skipped["runoff"]["court"]
    sources = [
        (SRC_ROSTER, STATE, "member roster", "Open States people project (CC0), as loaded into state_ga.sqlite",
         "Sitting Georgia legislators and statewide officials", "https://github.com/openstates/people", "", mtime(roster_db), sha(roster_db),
         len(legs) + len(offs), "Who holds each seat today, and which candidate is a sitting member (same chamber and district, the name "
         "fits, one fit only; the results' incumbent mark with the same family name is also taken, and listed; a member of another seat "
         "only when the name fits exactly one sitting legislator or official of the same party). The roster's statewide officials are the "
         "Governor, Lieutenant Governor, Secretary of State and Attorney General only; for the other statewide offices the holder is left "
         "empty and the results' incumbent mark is used. Names, party and ids only."),
        (SRC_COUNTY, STATE, "county codes", "U.S. Census Bureau", "Cartographic boundary file, counties, 2024 (1:500,000)", COUNTY_URL,
         "2024", mtime(county_zip), sha(county_zip), len(counties),
         "Five-digit county codes (GEOID) for Georgia's 159 counties, matched by name to the results' county rows. The counties a "
         "district reaches are those its May 19 primary contests were counted in (derived)."),
    ]
    for kind in ("primary", "runoff"):
        m = meta[kind]
        path = os.path.join(folder, m["file"])
        n = sum(1 for c in prim if c[13] == SRC[kind])
        sources.append((
            SRC[kind], STATE, "official results", AGENCY,
            f"Georgia Election Results: {m['name']}, Total Votes (official results): state offices", m["url"],
            (m.get("last_updated") or "")[:10], mtime(path), sha(path), n,
            f"The \"Total Votes Excel\" report of {m['page']}, marked official on the results site; the same file the federal loader "
            f"reads. {len(book[kind])} state contests read (statewide offices, Public Service Commission, State Senate, State House); "
            "each contest's Total Votes line equals the sum of its candidates, and every candidate's county figures add up to the "
            "statewide figure" + (" (except as listed in the loader's report)" if differ[kind] else "") + ". The results carry no "
            "write-in line; the incumbent mark \"(I)\" is taken off the names. A field is a party primary with two candidates or more."
            + (f" Not on the November ballot and not stored: {len(courts)} appellate court seats elected on May 19 (nonpartisan), "
               f"{'none' if not court_runoff else len(court_runoff)} of them in the June 16 runoff; superior court judges, district "
               "attorneys and the party questions are local or not offices." if kind == "primary" else "")))
    for path in files:
        base = os.path.basename(path)
        n = sum(1 for x in listed if x[0] == base)
        sources.append((
            ids[base], STATE, "official candidate list", AGENCY,
            "Qualifying Candidate Information: November 3, 2026 General Election (Qualified Candidates download): state offices", MVP,
            "", mtime(path), sha(path), n,
            "Saved by hand from the page's own Download button: the search is behind reCAPTCHA, which only a person answers. Columns read, "
            "by heading: contest name, candidate name, candidate status, political party; county, municipality, qualified date, "
            "incumbent, occupation, e-mail and website are never read. No ballot order is printed, so none is stored. Withdrawn or "
            f"disqualified, left off: {len(gone)}."))
    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA)
    with con:
        con.execute("DELETE FROM sl_candidates WHERE race_id IN (SELECT race_id FROM sl_races WHERE state = ?) OR race_id LIKE ?",
                    (STATE, f"2026-{STATE}-%"))
        con.execute("DELETE FROM sl_races WHERE state = ?", (STATE,))
        con.execute("DELETE FROM sl_sources WHERE state = ?", (STATE,))
        con.execute("DELETE FROM sl_places WHERE source_id LIKE ?", (f"{STATE.lower()}-%",))
        con.executemany("INSERT INTO sl_races VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", race_rows)
        con.executemany("INSERT INTO sl_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [tuple(c) for c in cands])
        con.executemany("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", sources)
        con.executemany("INSERT INTO sl_places VALUES (?,?,?,?,?)", place_rows)
    con.close()

    # 8. say what happened, and what is still waiting
    per = lambda level, rows: sum(1 for c in rows if races[c[0]]["level"] == level)
    kind_n = lambda k: sum(1 for c in prim if races[c[0]]["_kind"] == k)
    n_state = sum(1 for r in races.values() if r["level"] == "statewide")
    say(f"    Georgia state offices: {len(races)} races ({n_state} statewide incl. PSC {', '.join(map(str, PSC_UP))}; "
        f"{sum(1 for r in races.values() if r['_kind'] == 'state_senate')} Senate; {sum(1 for r in races.values() if r['_kind'] == 'state_house')} "
        f"House); {len(gen)} candidates on the November list (statewide {per('statewide', gen)}, Senate "
        f"{sum(1 for c in gen if races[c[0]]['_kind'] == 'state_senate')}, House {sum(1 for c in gen if races[c[0]]['_kind'] == 'state_house')}); "
        f"{fields} primary fields and {nrunoffs} runoffs, {len(prim)} primary rows (statewide {per('statewide', prim)}, Senate "
        f"{kind_n('state_senate')}, House {kind_n('state_house')}), official votes reconciled")
    if not files:
        say(f"      waiting: the November 3, 2026 list. The Secretary of State's Qualifying Candidate Information search ({MVP}) is "
            f"behind reCAPTCHA; a person searches the November 3, 2026 General Election, presses \"Download Qualified candidates\" and "
            f"saves the CSV in {hand}")
    else:
        say(f"      list read: {len(files)} file(s), {len(listed)} state rows ({len(gone)} withdrawn or disqualified left off), "
            f"{other_rows} federal or local rows not read here")
    say(f"      not on the November ballot: {len(courts)} appellate court seats (decided May 19); the Senate District 7 special election "
        "(decided June 16)")
    for c in cands:
        if c[12]:
            line = f"{c[0]} {c[1]}: {c[3]} -> {c[12]}{' (holds this seat)' if c[7] else ''}"
            if line not in matched:
                matched.append(line)
    for line in matched:
        say(f"      matched: {line}")
    for line in checks:
        say(f"      check: {line}")
    return dict(races=len(races), general=len(gen), primary=len(prim), fields=fields, runoffs=nrunoffs, checks=checks, files=files)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Georgia's state races on the November 3, 2026 ballot")
    ap.add_argument("db", help="the state-and-local ballot database to write Georgia's rows into")
    ap.add_argument("--hand", default=HAND, help="the folder holding the saved Qualified Candidates CSV")
    a = ap.parse_args()
    load(a.db, hand=a.hand)
