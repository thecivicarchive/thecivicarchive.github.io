"""
ballot/state_local_sc.py - South Carolina's state races on the November 3, 2026 ballot, into ballot_local_2026.sqlite:

  - the seven statewide races of a midterm year (four-year terms, all last elected in 2022): Governor and Lieutenant
    Governor (one ticket to a party), Secretary of State, State Treasurer, Attorney General, Comptroller General, State
    Superintendent of Education and Commissioner of Agriculture;
  - all 124 seats of the House of Representatives (two-year terms).
The Senate's 46 seats are elected for four years in presidential years (last in 2024, next in 2028), and the
Commission's office list for the November 3 election offers no State Senate office, so no Senate seat is stored; a
State Senate office on that list stops the loader. Solicitors (one per judicial circuit) and county, school and special
district offices are local and left out. Which offices are up is a fixed list checked against the Commission's own:
every office above must be on the general election's office list, and a state office there that is not above stops
the loader. The federal ballot database is never opened here.

Sources, all the State Election Commission's own, the same two systems the federal loader reads (ballot/lists/sc.py):
  - the November ballot: the Candidate Tracking System (vrems.scvotes.sc.gov/Candidate/SelectElection), through the
    page's own calls: the list of 2026 elections, the election chosen ("11/3/2026 Statewide General Election"), then
    the search (a POST to /Candidate/CandidateSearch/) for each state office, every status, party and filing
    location. The "6/9/2026 Statewide Primary" list is read the same way to check the primary results. The answer's
    table has the columns Office, Associated Counties, Name on Ballot, Running Mate, Party, Location of Filing and
    Candidate Status; columns are taken by heading. Office, Name on Ballot, Running Mate (a name and its status),
    Party and Candidate Status are kept per row, with the row's own candidate number; Associated Counties names the
    counties an office covers and is the same on every row of an office (checked), so it is kept once per office.
    Location of Filing is never kept. Only those cells go into ballot_cache/sc/sc_2026_state_candidate_lists.json,
    with each answer's SHA-256. Each row links a detail page with contact details; those pages are never asked for,
    and the page's export link is not used. Candidates whose status is Active (after the election, Elected or
    Defeated in Election) are on the November ballot; every other status is left off and counted. The list gives no
    ballot positions (it is sorted by surname), so no ballot_order is stored, and it carries no write-in candidates.
  - the primary fields: the Commission's official results site (www.enr-scvotes.org, Clarity Elections), the
    detail and summary reports of "Statewide Primaries" (June 9), "Statewide Primary Runoffs" (June 23) and
    "Primaries Recount" (June 12), fetched and cached in ballot_cache/sc/ by the federal loader's fetch_results, which
    stores a site only when it is headed "Official Results" and all its counties are completely reported and marked
    certified. Every state contest is reconciled: each candidate's vote types and counties add to the statewide
    total, every precinct reported, and the summary report gives the same totals. A contest in the recount replaces
    the June 9 figures (the June 9 count is named in the note). The results carry no write-in line, so a field's
    total is the sum of its candidates' votes. A party nominates by majority: a candidate with more than half the
    votes advanced; otherwise the two in the runoff advanced, and the runoff (stored as runoff-REP, runoff-DEM) was
    won by the one with more votes. The runoff's pair must be the primary's top two. South Carolina prints no
    uncontested primary, so a field is a party's primary with two candidates or more.
Who holds each seat comes from the Open States roster in state_sc.sqlite (legislators is_current = 1 by chamber and
district; the officials table for Governor, Lieutenant Governor and Attorney General, the only elected statewide
offices it carries): ids, names and party only. County codes come from the Census Bureau's 2024 county file
(states_cache/census/), matched by name to the list's Associated Counties.

Privacy. From the candidate list only the cells named above are kept or read; Location of Filing is never kept, and
the detail pages (addresses, telephone, e-mail) are never asked for. The results carry names, parties and votes only.
The roster's contact columns are never selected. An error names the office, the file or the check, never a row of
contact data. Before anything is written every stored name, party and note is checked for anything that looks like a
contact detail, and the load stops (without showing it) if one does.

    python -m ballot.state_local_sc <path to a test database>
"""

import csv
import datetime as dt
import hashlib
import html
import io
import json
import os
import re
import sqlite3
import sys
import time
import uuid
import zipfile
import xml.etree.ElementTree as ET
from urllib.parse import urlencode

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from ballot.common import CACHE, fold, name_parts, party_code  # noqa: E402
from ballot.lists.sc import BEFORE, CTS, CTS_PAGE, KNOWN, ON, RESULTS_PAGE, Session, fetch_results  # noqa: E402
from ballot.lists.tx import proper  # noqa: E402
from ballot.match import fits  # noqa: E402
from states.money_mn import given_fits  # noqa: E402

STATE, FIPS, NAME = "SC", "45", "South Carolina"
GENERAL, PRIMARY, RUNOFF, RECOUNT = "2026-11-03", "2026-06-09", "2026-06-23", "2026-06-12"
FOLDER = os.path.join(CACHE, "sc")
LIST_FILE = "sc_2026_state_candidate_lists.json"
ROSTER = os.path.join(HERE, "state_sc.sqlite")
COUNTY_ZIP = os.path.join(HERE, "states_cache", "census", "cb_2024_us_county_500k.zip")
COUNTY_URL = "https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_county_500k.zip"
TOTAL_COUNTIES, HOUSE_SEATS = 46, 124
AGENCY = "South Carolina State Election Commission"
SRC_GENERAL, SRC_PRIMARY_LIST = "sc-sec-2026-sl-general-list", "sc-sec-2026-sl-primary-list"
SRC = {"primary": "sc-sec-2026-sl-primary-results", "runoff": "sc-sec-2026-sl-runoff-results",
       "recount": "sc-sec-2026-sl-recount-results"}
SRC_ROSTER, SRC_COUNTY = "sc-openstates-roster", "sc-census-2024-county-codes"
PARTY = {"REP": "Republican", "DEM": "Democratic"}
LIST_CODE = {"Republican": "REP", "Democratic": "DEM"}

# the Candidate Tracking System's elections read: kind -> (display name, date)
LISTS = {"general": ("11/3/2026 Statewide General Election", "2026-11-03"),
         "primary": ("6/9/2026 Statewide Primary", "2026-06-09")}
KEEP = ("Office", "Associated Counties", "Name on Ballot", "Running Mate", "Party", "Candidate Status")

# the statewide offices: key -> (office_kind, office shown, the list's labels, the results' label, roster office)
STATEWIDE = {
    "GOV": ("governor", "Governor and Lieutenant Governor", ("Governor and Lieutenant Governor", "Governor"), "Governor", "governor"),
    "SOS": ("secretary_of_state", "Secretary of State", ("Secretary of State",), "Secretary of State", None),
    "TREAS": ("state_treasurer", "State Treasurer", ("State Treasurer",), "State Treasurer", None),
    "AG": ("attorney_general", "Attorney General", ("Attorney General",), "Attorney General", "attorney general"),
    "COMP": ("comptroller", "Comptroller General", ("Comptroller General",), "Comptroller General", None),
    "SPI": ("superintendent_of_public_instruction", "State Superintendent of Education", ("State Superintendent of Education",),
            "State Superintendent of Education", None),
    "AGR": ("agriculture_commissioner", "Commissioner of Agriculture", ("Commissioner of Agriculture",), "Commissioner of Agriculture", None),
}
HOUSE_LABEL = "State House of Representatives"
OFFICIAL_WORDS = {"governor": "Governor", "lt_governor": "Lieutenant Governor", "attorney general": "Attorney General"}

# the office list: local offices this loader leaves out (county, school, circuit and special districts)
LOCAL = re.compile(r"^(Solicitor|Sheriff|Probate Judge|Clerk of Court|Coroner|Auditor|County |Register of Deeds|Soil and Water|"
                   r"Board of Education|School |Watershed|Fire District|Public Service District|Commissioner of Public Works)")
FEDERAL = re.compile(r"^U\.S\. ")

# the results' contest names: "Governor - REP", "State  House of Representatives, District  36 - REP"
R_CONTEST = re.compile(r"^(?P<o>.+?) - (?P<p>[A-Z]{3})$")
R_HOUSE = re.compile(r"^State House of Representatives, District (\d{1,3})$")
R_SENATE = re.compile(r"^State Senate\b")
R_OUT = re.compile(r"^(U\.S\. |Advisory Question \d+$)")
R_ANNOT = re.compile(r"\s*-\s*\*([^*]+)\*\s*$")             # "Jacqueline Hicks DuBose - *Decertified before Primary*"
L_HOUSE = re.compile(r"^State House of Representatives, District (\d{1,3})$")
MATE = re.compile(r"^(?P<n>.+?)\s*\((?P<s>[^()]+)\)$")

# a last look before anything is written
CONTACT = re.compile(r"@|https?:|www\.|\.(?:com|org|net|gov|us)\b|\d{3}|P\.?\s?O\.?\s+Box|\bSuite\b", re.I)
CONTACT_NOTE = re.compile(r"@|https?:|www\.|\b\d{3}[-.)\s]\s?\d{3}[-.\s]\d{4}\b|\bP\.?\s?O\.?\s+Box\b|\bSuite\b|\b\d{5}(?:-\d{4})?\b", re.I)

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

HOUSE_NOTE = "South Carolina's representatives serve two-year terms; all 124 House seats are on the ballot in 2026."
GOV_NOTE = ("The Governor and Lieutenant Governor are elected together, one ticket to a party; the Election Commission's list names "
            "each ticket's candidate for Lieutenant Governor on the Governor's row.")
NO_HOLDER = "The roster used here does not list who holds this office."
NONE_ON_LIST = "No candidate for this seat is on the Election Commission's November list."
RUNOFF_NOTE = "Went to the June 23, 2026 runoff: no candidate won a majority on June 9."
PETITION_NOTE = "On the ballot by voters' petition, as the Election Commission's list says (\"Petition\"), not a party's nomination."
CAPS_NOTE = "South Carolina's list prints this name in capitals; it is shown here in ordinary capitals."


class Unknown(Exception):
    pass


# ------------------------------------------------------------------------------------------------ the candidate lists

def grid(body):
    """([(candidate number, {kept row column: cell})], {office: associated counties}) from one search answer; columns
    are taken by heading, Location of Filing is never kept."""
    t = body.decode("utf-8", "replace")
    head = [re.sub(r"<[^>]+>|\s+", " ", h).strip() for h in re.findall(r"<th[^>]*>(.*?)</th>", t, re.S)]
    missing = [k for k in KEEP if k not in head]
    if missing:
        raise SystemExit(f"South Carolina (state races): the candidate search's columns changed (no {', '.join(missing)})")
    idx = {k: head.index(k) for k in KEEP}
    rows, counties, n = [], {}, 0
    for m in re.finditer(r"<tr([^>]*)>(.*?)</tr>", t, re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", m.group(2), re.S)
        if not cells:
            continue
        if len(cells) != len(head):
            raise SystemExit("South Carolina (state races): a row of the candidate search does not match its header")
        key = re.search(r'data-key="(\d+)"', m.group(1))
        at = re.search(r'data-index="(\d+)"', m.group(1))
        if not key or not at or int(at.group(1)) != n:
            raise SystemExit("South Carolina (state races): the candidate search's rows are not numbered as expected")
        n += 1
        rec = {k: html.unescape(re.sub(r"<[^>]+>|\s+", " ", cells[i])).strip() for k, i in idx.items()}
        del cells
        office, where = rec.pop("Office"), rec.pop("Associated Counties")
        if counties.setdefault(office, where) != where:
            raise SystemExit(f"South Carolina (state races): the list gives two sets of counties for {office}")
        rows.append((key.group(1), dict(Office=office, **rec)))
    return rows, counties


def state_lists(folder, say):
    """{"elections": {kind: {"id", "display", "url", "offered", "offices": {label: {"sha256", "rows", "counties"}}}}} for the
    general election and the June 9 primary, the state offices only, the kept cells only. Asked afresh after two days."""
    path = os.path.join(folder, LIST_FILE)
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < 2 * 86400:
        return path, json.load(open(path, encoding="utf-8"))
    s = Session()
    elections = json.loads(s.ask(f"{CTS}/Candidate/GetElections?electionType=General&year=2026", accept="application/json"))
    out = {"read": dt.date.today().isoformat(), "page": CTS_PAGE, "elections": {}}
    for kind, (display, date) in LISTS.items():
        found = [e for e in elections if e.get("displayName") == display and str(e.get("electionDate", "")).startswith(date)]
        if len(found) != 1:
            raise SystemExit(f"South Carolina (state races): the Candidate Tracking System lists {len(found)} elections named {display!r}")
        eid = str(found[0]["electionId"])
        first = s.ask(CTS_PAGE).decode("utf-8", "replace")
        tok = re.search(r'name="__RequestVerificationToken" type="hidden" value="([^"]+)"', first)
        if not tok:
            raise SystemExit("South Carolina (state races): the Candidate Tracking System's election page changed (no form token)")
        page = s.ask(CTS_PAGE, urlencode({"ElectionKindSid": "General", "ElectionYear": "2026", "ElectionID": eid,
                                          "__RequestVerificationToken": tok.group(1)}).encode(),
                     ctype="application/x-www-form-urlencoded").decode("utf-8", "replace")
        form = re.search(r'<form id="searchForm">(.*?)</form>', page, re.S)
        if not form or f'name="ElectionId" value="{eid}"' not in form.group(1):
            raise SystemExit(f"South Carolina (state races): the candidate search for {display} did not open")
        export = re.search(r'name="ExportFileName" value="([^"]*)"', form.group(1))
        sel = re.search(r'<select[^>]*id="SelectedOffice"[^>]*>(.*?)</select>', form.group(1), re.S)
        opts = {html.unescape(b).strip(): a for a, b in re.findall(r'<option[^>]*value="([^"]*)"[^>]*>([^<]*)', sel.group(1))}
        offered = [o for o in opts if o != "All"]
        rec = {"id": eid, "display": display, "url": f"{CTS}/Candidate/CandidateSearch?electionId={eid}", "offered": offered,
               "offices": {}}
        wanted = [o for o in offered if o == HOUSE_LABEL or any(o in v[2] for v in STATEWIDE.values())]
        for office in wanted:
            fields = [("ElectionId", eid), ("ExportFileName", export.group(1) if export else ""), ("SelectedOffice", opts[office]),
                      ("CandidateFirstName", ""), ("CandidateLastName", ""), ("SelectedCandidateStatus", "All"),
                      ("SelectedPoliticalParty", "All"), ("SelectedFilingLocation", "All")]
            b = "----sc" + uuid.uuid4().hex
            data = "".join(f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n' for k, v in fields) + f"--{b}--\r\n"
            body = s.ask(f"{CTS}/Candidate/CandidateSearch/", data.encode(), ctype=f"multipart/form-data; boundary={b}")
            rows, counties = grid(body)
            bad = [r["Office"] for _k, r in rows if not r["Office"].startswith(office)]
            if bad:
                raise SystemExit(f"South Carolina (state races): the search for {office} answered rows for another office")
            rec["offices"][office] = {"sha256": hashlib.sha256(body).hexdigest(), "counties": counties,
                                      "rows": [dict(r, id=k) for k, r in rows]}
            del body
        out["elections"][kind] = rec
        say(f"      {display}: {sum(len(o['rows']) for o in rec['offices'].values())} candidates for state offices on the list")
    json.dump(out, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return path, out


def list_office(text):
    """The race key for an office as the candidate list names it."""
    t = re.sub(r"\s+", " ", text or "").strip()
    for key, v in STATEWIDE.items():
        if t in v[2]:
            return key
    m = L_HOUSE.match(t)
    if m and 1 <= int(m.group(1)) <= HOUSE_SEATS:
        return f"SH{int(m.group(1))}"
    raise Unknown(t)


# ------------------------------------------------------------------------------------------------ the results

def result_contest(text):
    """(race key, party code) for a state contest of the results; None for a federal contest or an advisory question;
    Unknown for anything else."""
    t = re.sub(r"\s+", " ", text or "").strip()
    m = R_CONTEST.match(t)
    base = m.group("o") if m else t
    if R_OUT.match(base):
        return None
    if not m:
        raise Unknown(t)
    code = m.group("p")
    for key, v in STATEWIDE.items():
        if base == v[3]:
            return key, code
    h = R_HOUSE.match(base)
    if h and 1 <= int(h.group(1)) <= HOUSE_SEATS:
        return f"SH{int(h.group(1))}", code
    raise Unknown(t)


def bare(raw):
    """(name, the results' own mark or None): "X - *Decertified before Primary*" -> ("X", "Decertified before Primary")."""
    t = re.sub(r"\s+", " ", raw or "").strip()
    m = R_ANNOT.search(t)
    return (t[:m.start()].strip(), m.group(1).strip()) if m else (t, None)


def contests(folder, rec):
    """({(key, code): {"office", "cands": [(name, votes, mark)], "counties": {county names}}}, [checks]) for every state
    contest of one results site, each checked: every precinct reported, vote types and counties add to the total, the
    party on every line, no write-in line, and the summary report's totals the same."""
    root = ET.fromstring(zipfile.ZipFile(os.path.join(folder, rec["detail"])).read("detail.xml"))
    if root.findtext("ElectionDate") != rec["date"]:
        raise SystemExit(f"South Carolina (state races): the detail report of {rec['label']} is dated {root.findtext('ElectionDate')}")
    out, checks = {}, []
    for c in root.findall("Contest"):
        try:
            key = result_contest(c.get("text"))
        except Unknown as e:
            raise SystemExit(f"South Carolina (state races): a contest in {rec['label']} this loader does not read: {e}")
        if not key:
            continue
        label = re.sub(r"\s+", " ", c.get("text")).strip()
        if key[1] not in PARTY:
            raise SystemExit(f"South Carolina (state races): a party in the results that is not read ({label})")
        if c.get("precinctsReported") != c.get("precinctsParticipating") or c.get("countiesReported") != c.get("countiesParticipating"):
            checks.append(f"{label} ({rec['label']}): not every precinct or county reported")
        field, counties = [], set()
        for ch in c.findall("Choice"):
            name, mark = bare(ch.get("text"))
            total = int(ch.get("totalVotes"))
            by_type = sum(int(vt.get("votes")) for vt in ch.findall("VoteType"))
            by_county = sum(int(cc.get("votes")) for vt in ch.findall("VoteType") for cc in vt.findall("County"))
            counties |= {cc.get("name") for vt in ch.findall("VoteType") for cc in vt.findall("County")}
            if by_type != total or by_county != total:
                checks.append(f"{label} ({rec['label']}): {name}'s vote types or counties do not add to the total")
            if re.search(r"(?i)write[- ]?in", name):
                raise SystemExit(f"South Carolina (state races): {label} reports write-in votes; read how the total is made")
            if ch.get("party") != key[1]:
                checks.append(f"{label} ({rec['label']}): {name} is reported under {ch.get('party')}")
            field.append((name, total, mark))
        if key in out:
            raise SystemExit(f"South Carolina (state races): {label} appears twice in {rec['label']}")
        if len({fold(n) for n, _v, _m in field}) != len(field):
            checks.append(f"{label} ({rec['label']}): the same name twice")
        out[key] = {"office": label, "cands": field, "counties": counties}
    z = zipfile.ZipFile(os.path.join(folder, rec["summary"]))
    rows = list(csv.reader(io.StringIO(z.read("summary.csv").decode("utf-8-sig", "replace"))))
    ci, ni, vi = rows[0].index("contest name"), rows[0].index("choice name"), rows[0].index("total votes")
    seen = {}
    for r in rows[1:]:
        if not r:
            continue
        try:
            key = result_contest(re.sub(r" \(Vote For \d+\)$", "", re.sub(r"\s+", " ", r[ci]).strip()))
        except Unknown:
            key = None
        if key:
            seen.setdefault(key, {})[fold(bare(r[ni])[0])] = int(r[vi])
    if seen != {k: {fold(n): v for n, v, _m in c["cands"]} for k, c in out.items()}:
        checks.append(f"{rec['label']}: the summary and detail reports differ for the state contests")
    return out, checks


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


def middles(p):
    """{(first given name, initial of the second)} from every way the roster writes the person (initials included)."""
    out = set()
    for o in [p.get("full") or ""] + (p.get("other") or "").split(";"):
        o = o.strip()
        if o and "," not in o:
            g, _f = name_parts(o)
            if len(g) >= 2:
                out.add((g[0], g[1][:1]))
    return out


def person_fits(name, p):
    """The same family name and a given name that fits; both sides must carry a given name; and a second given name on
    the ballot must not contradict the roster's (Robert Larry Williams is not Robert Q. Williams)."""
    cand = name_parts(name)
    if not cand[0] or not any(fits(cand, f) for f in forms(p) if f[0]):
        return False
    if len(cand[0]) < 2:
        return True
    second = cand[0][1]
    words = {w for o in [p.get("full") or "", p.get("first") or ""] + (p.get("other") or "").split(";") if "," not in o
             for w in name_parts(o.strip())[0] if len(w) > 1} | set(fold(p.get("first") or "").split())
    if any(given_fits(second, w) for w in words):
        return True                                   # the ballot's second name is one the roster uses (Richard Richie Yow)
    ms = {m for first, m in middles(p) if first[:1] == cand[0][0][:1]}
    return not ms or second[:1] in ms


def where(p):
    if p.get("office"):
        return f"as {OFFICIAL_WORDS.get(p['office'], p['office'])}"
    return f"in the South Carolina {'Senate' if p['chamber'] == 'Senate' else 'House'}, District {int(p['district'])}"


# ------------------------------------------------------------------------------------------------ helpers

def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def mtime(path):
    return dt.datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d")


def county_key(text):
    return re.sub(r"[^a-z]", "", re.sub(r"\s+County$", "", str(text or "").strip(), flags=re.I).lower())


def census_counties(path):
    """{county key: (GEOID, name)} for South Carolina from the Census Bureau's county file."""
    import shapefile                                                     # pyshp, in the kit's environment
    z = zipfile.ZipFile(path)
    dbf = next(n for n in z.namelist() if n.endswith(".dbf"))
    rdr = shapefile.Reader(dbf=io.BytesIO(z.read(dbf)))
    return {county_key(r["NAME"]): (r["GEOID"], r["NAME"]) for r in (x.as_dict() for x in rdr.iterRecords()) if r["STATEFP"] == FIPS}


def shown(raw):
    name = re.sub(r"\s+", " ", raw or "").strip()
    caps = any(c.isalpha() for c in name) and name == name.upper()
    return (proper(name) if caps else name), caps


def pct(v, total):
    return round(100 * v / total, 1) if total else None


# ------------------------------------------------------------------------------------------------ loading

def load(db_path, say=print, folder=FOLDER, roster_db=ROSTER, county_zip=COUNTY_ZIP):
    from states import net
    net.patient_lookups()
    os.makedirs(folder, exist_ok=True)
    lpath, lists = state_lists(folder, say)
    meta = fetch_results(folder, say)                   # the federal loader's cached official reports (refetched after 30 days)
    legs, offs = roster(roster_db)
    counties = census_counties(county_zip)
    if len(counties) != TOTAL_COUNTIES:
        raise SystemExit(f"South Carolina (state races): the Census county file has {len(counties)} counties, not {TOTAL_COUNTIES}")
    checks, matched = [], []
    gen_list, pri_list = lists["elections"]["general"], lists["elections"]["primary"]

    # 0. which offices are up: the general election's own office list, read against the fixed list above
    offered = gen_list["offered"]
    state_offered = [o for o in offered if not FEDERAL.match(o) and not LOCAL.match(o)]
    for o in state_offered:
        if o != HOUSE_LABEL and not any(o in v[2] for v in STATEWIDE.values()):
            raise SystemExit(f"South Carolina (state races): the November 3 office list offers {o!r}, a state office this loader does not "
                             "read (a State Senate special election, or a new office): read the list again")
    for key, v in STATEWIDE.items():
        if not any(lab in offered for lab in v[2]):
            raise SystemExit(f"South Carolina (state races): the November 3 office list does not offer {v[1]}")
    if HOUSE_LABEL not in offered:
        raise SystemExit("South Carolina (state races): the November 3 office list does not offer the State House of Representatives")
    senate_offered = [o for o in offered if R_SENATE.match(o)]

    def listed(e):
        """[(race key, row)] of one election's list, every state office, in the list's own order."""
        out = []
        for lab, o in e["offices"].items():
            for r in o["rows"]:
                try:
                    out.append((list_office(r["Office"]), r))
                except Unknown:
                    raise SystemExit(f"South Carolina (state races): an office on the {e['display']} list that is not read: {r['Office']!r}")
        return out

    unknown = sorted({r["Candidate Status"] for e in (gen_list, pri_list) for _k, r in listed(e)} - KNOWN)
    if unknown:
        raise SystemExit(f"South Carolina (state races): statuses on the candidate list the loader does not read: {unknown}")

    # 1. the official results, the recount standing in for the June 9 count where there is one
    book, rep = {}, {}
    for kind in ("primary", "runoff", "recount"):
        m = meta["sites"][kind]
        book[kind], ch = contests(folder, m)
        checks += ch
    replaced = {}
    for key, c in book["recount"].items():
        if key not in book["primary"]:
            checks.append(f"{c['office']}: in the June 12 recount but not in the June 9 results")
            continue
        before = book["primary"][key]
        if {fold(n) for n, _v, _m in before["cands"]} != {fold(n) for n, _v, _m in c["cands"]}:
            checks.append(f"{c['office']}: the recount's candidates are not the June 9 candidates")
        replaced[key] = before
        book["primary"][key] = dict(c, counties=before["counties"] | c["counties"])

    # 2. the seats on the ballot, each with who holds it today
    races = {}

    def add_race(key):
        rid = f"2026-{STATE}-{key}"
        note, h = [], None
        if key in STATEWIDE:
            kind, office, _labs, _res, roster_office = STATEWIDE[key]
            level, jur, jur_id, district = "statewide", NAME, FIPS, None
            h = offs.get(roster_office) if roster_office else None
            if kind == "governor":
                note.append(GOV_NOTE)
                lt = offs.get("lt_governor")
                if lt:
                    note.append(f"Today's Lieutenant Governor, from the roster: {lt['full']}.")
            if h is None:
                note.append(NO_HOLDER)
        else:
            d = int(key[2:])
            kind, office, level = "state_house", "State Representative", "legislature"
            jur, jur_id, district = f"House District {d}", f"{STATE}-{d}", str(d)
            hs = [p for p in legs if p["chamber"] == "House" and str(p["district"]).strip() == str(d)]
            h = hs[0] if len(hs) == 1 else None
            if len(hs) > 1:
                checks.append(f"{rid}: {len(hs)} sitting members in the roster for this seat; none is taken as the holder")
            if h is None:
                checks.append(f"{rid}: no sitting member in the roster for this seat")
                note.append("The roster shows no one holding this seat today.")
            note.append(HOUSE_NOTE)
        races[rid] = {"race_id": rid, "state": STATE, "level": level, "office_kind": kind, "office": office, "jurisdiction": jur,
                      "jurisdiction_id": jur_id, "county_ids": None, "district": district, "seat": None, "special": 0,
                      "partisan": 1, "holder_id": h["id"] if h else None, "holder_name": h["full"] if h else None,
                      "holder_party": h["party"] if h else None, "election_date": GENERAL, "note": note, "_holder": h, "_kind": kind,
                      "_key": key}
        return rid

    for key in STATEWIDE:
        add_race(key)
    for d in range(1, HOUSE_SEATS + 1):
        add_race(f"SH{d}")
    for kind in book:
        for (k, code) in book[kind]:
            if f"2026-{STATE}-{k}" not in races:
                raise SystemExit(f"South Carolina (state races): the {kind} results have a contest for {k}, not on this loader's list")

    # 3. who is who: the seat's holder here; another sitting member of the same party once every row is read (step 6)
    people = legs + [dict(p, chamber=None, district=None) for p in offs.values()]

    def identify(rid, name):
        """(incumbent, state_member_id) for one name in a race: the seat's holder only."""
        h = races[rid]["_holder"]
        if h is not None and person_fits(name, h):
            return 1, h["id"]
        return 0, None

    # 4. the November ballot: status Active on the general election's list
    general, off, by_status, mates = [], {}, {}, []
    printed = {}                                      # fold(name) -> the list's spelling, for the results' names
    active = [(k, r) for k, r in listed(gen_list) if r["Candidate Status"] in ON]
    for k, r in listed(gen_list):
        by_status[r["Candidate Status"]] = by_status.get(r["Candidate Status"], 0) + 1
        printed.setdefault((f"2026-{STATE}-{k}", fold(r["Name on Ballot"])), r["Name on Ballot"])
        if r["Candidate Status"] not in ON:
            off[(f"2026-{STATE}-{k}", fold(r["Name on Ballot"]))] = r["Candidate Status"]
    for k, r in listed(pri_list):
        printed.setdefault((f"2026-{STATE}-{k}", fold(r["Name on Ballot"])), r["Name on Ballot"])
    grouped = {}
    for k, r in active:
        rid = f"2026-{STATE}-{k}"
        grouped.setdefault((rid, fold(r["Name on Ballot"])), []).append(r)
    for (rid, _f), rs in grouped.items():
        r0 = rs[0]
        name, caps = shown(r0["Name on Ballot"])
        parties = []
        for r in rs:
            p = r["Party"].strip()
            if not p:
                checks.append(f"{rid}: a candidate with no party on the list ({name})")
            if p in parties:
                raise SystemExit(f"South Carolina (state races): {name} is on the November list twice for one party ({rid})")
            parties.append(p)
        party = ", ".join(p for p in parties if p) or None
        code = "I" if parties[0] == "Petition" else party_code(parties[0])
        note = []
        if caps:
            note.append(CAPS_NOTE)
        if len(parties) > 1:
            note.append(f"Nominated by more than one party; the Election Commission's list has a row for each ({', then '.join(parties)}).")
        if "Petition" in parties:
            note.append(PETITION_NOTE)
        if races[rid]["_kind"] == "governor":
            m = MATE.match(r0["Running Mate"] or "")
            if not m or m.group("n").strip().lower() == "not designated":
                checks.append(f"{rid}: the ticket of {name} names no candidate for Lieutenant Governor")
            else:
                mate, st = m.group("n").strip(), m.group("s").strip()
                pool = [p for p in people if (p["party"] or "") == parties[0] and person_fits(shown(mate)[0], p)]
                note.append(f"Running mate for Lieutenant Governor: {shown(mate)[0]}"
                            + (f", who serves today {where(pool[0])}." if len(pool) == 1 else "."))
                mates.append(f"{name} / {shown(mate)[0]}")
                if st not in ON:
                    checks.append(f"{rid}: {name}'s running mate has the status {st!r}")
        elif any((r["Running Mate"] or "") not in ("", "Not Designated") for r in rs):
            checks.append(f"{rid}: a running mate on a row for an office without one")
        inc, mid = identify(rid, name)
        general.append([rid, "general", GENERAL, name, party, code, None, inc, 0, None, None, None, mid, SRC_GENERAL, note])
    for rid in races:
        for p in PARTY.values():
            two = [g[3] for g in general if g[0] == rid and p in (g[4] or "").split(", ")]
            if len(two) > 1:
                checks.append(f"{rid}: the November list has {len(two)} candidates of one party ({', '.join(two)})")
        inc = [g for g in general if g[0] == rid and g[7]]
        if len(inc) > 1:
            for g in inc:
                g[7], g[12] = 0, None
            checks.append(f"{rid}: more than one name on the list fits the sitting member; none is marked")

    # 5. the primary results against the Commission's lists: who was on each party's ballot. The June 9 list holds only
    # the contested primaries, and not all of them; the general election's list holds every candidate of the year for
    # each office, with a status. A name in the results must be on one of the two for its seat and party.
    ballot, before, on_primary_list = {}, {}, set()
    for e in (pri_list, gen_list):
        for k, r in listed(e):
            rid = f"2026-{STATE}-{k}"
            code = LIST_CODE.get(r["Party"].strip())
            if not code:
                continue                              # the other parties nominate by convention; no primary
            if e is pri_list:
                on_primary_list.add((rid, code))
            if r["Candidate Status"] in BEFORE:
                before[(rid, code, fold(r["Name on Ballot"]))] = r["Candidate Status"]
                continue
            ballot.setdefault((rid, code), set()).add(fold(r["Name on Ballot"]))
    in_results = {(f"2026-{STATE}-{k}", code) for kind in ("primary", "runoff") for (k, code) in book[kind]}
    omitted = sorted(f"{rid} {PARTY[code]}" for rid, code in in_results - on_primary_list)
    for (k, code), c in book["primary"].items():
        rid = f"2026-{STATE}-{k}"
        names = ballot.get((rid, code), set())
        for n, _v, mark in c["cands"]:
            f = fold(n)
            if f in names:
                continue
            if (rid, code, f) in before:
                if mark != before[(rid, code, f)]:
                    checks.append(f"{c['office']}: {n} is {before[(rid, code, f)]!r} on the list but is in the June 9 results"
                                  + (f" marked {mark!r}" if mark else " unmarked"))
                continue
            checks.append(f"{c['office']}: {n} is in the June 9 results but on neither of the Commission's lists")
        counted = {fold(n) for n, _v, _m in c["cands"]}
        if names - counted:
            checks.append(f"{c['office']}: on the Commission's lists for this primary but not in the results: {sorted(names - counted)}")
    for (rid, code), names in ballot.items():
        if (rid, code) not in in_results and len(names) > 1:
            checks.append(f"{rid} {PARTY[code]}: the lists name {len(names)} candidates of the party but the results hold no primary")
    for e in (pri_list, gen_list):
        for k, r in listed(e):
            if r["Candidate Status"] == "Defeated In Primary":
                rid = f"2026-{STATE}-{k}"
                code = LIST_CODE.get(r["Party"].strip())
                if not any(fold(r["Name on Ballot"]) == fold(n) for kind in ("primary", "runoff")
                           for n, _v, _m in book[kind].get((k, code), {"cands": []})["cands"]):
                    checks.append(f"{rid}: {r['Name on Ballot']} is marked Defeated In Primary but is in no primary result")

    # 6. the primary fields and runoffs, official votes
    cands, nominee, fields, nrunoffs = [], {}, 0, 0
    for (k, code), c in sorted(book["primary"].items(), key=lambda x: (x[0][0], x[0][1])):
        rid, party = f"2026-{STATE}-{k}", PARTY[code]
        total = sum(v for _n, v, _m in c["cands"])
        ranked = sorted(c["cands"], key=lambda x: -x[1])
        if len(c["cands"]) < 2:
            nominee[(rid, code)] = c["cands"][0][0] if c["cands"] else None
            continue
        fields += 1
        went, winners = set(), set()
        counted_total = sum(v for _n, v, m in c["cands"] if not m)
        if ranked[0][1] * 2 > total:
            winners = {ranked[0][0]}
            nominee[(rid, code)] = ranked[0][0]
        else:
            r = book["runoff"].get((k, code))
            if not r:
                checks.append(f"{rid} {party}: no majority on June 9 and no runoff in the June 23 results")
            else:
                pair = {fold(n) for n, _v, _m in r["cands"]}
                if pair != {fold(ranked[0][0]), fold(ranked[1][0])}:
                    checks.append(f"{rid} {party}: the runoff's pair is not the primary's top two")
                winners = went = {n for n, _v, _m in c["cands"] if fold(n) in pair}
        if (ranked[0][1] * 2 > total) != (ranked[0][1] * 2 > counted_total) and not ranked[0][2]:
            checks.append(f"{rid} {party}: whether the leader had a majority depends on counting the votes of a name the results mark")
        for name, votes, mark in c["cands"]:
            inc, mid = identify(rid, name)
            shown_name, caps = shown(printed.get((rid, fold(name)), name))
            note = []
            if name in went:
                note.append(RUNOFF_NOTE)
            if mark:
                note.append(f"The official results mark this name \"{mark}\"; the votes are as the results report them.")
            if (k, code) in replaced:
                old = {fold(n): v for n, v, _m in replaced[(k, code)]["cands"]}
                was = old.get(fold(name))
                note.append("Votes after the June 12, 2026 recount; " + (
                    "the June 9 count was the same." if was == votes else f"the June 9 count gave {shown_name} {was:,}."))
            if caps:
                note.append(CAPS_NOTE)
            cands.append([rid, f"primary-{code}", PRIMARY, shown_name, party, party_code(party), None, inc, 0, votes, pct(votes, total),
                          "advanced" if name in winners else "lost", mid, SRC["recount"] if (k, code) in replaced else SRC["primary"],
                          note])
    for (k, code), c in sorted(book["runoff"].items(), key=lambda x: (x[0][0], x[0][1])):
        rid, party = f"2026-{STATE}-{k}", PARTY[code]
        p = book["primary"].get((k, code))
        if not p:
            checks.append(f"{rid} {party}: a runoff with no June 9 contest")
        elif sorted(p["cands"], key=lambda x: -x[1])[0][1] * 2 > sum(v for _n, v, _m in p["cands"]):
            checks.append(f"{rid} {party}: a runoff although the June 9 leader had a majority")
        total = sum(v for _n, v, _m in c["cands"])
        ranked = sorted(c["cands"], key=lambda x: -x[1])
        if len(ranked) != 2 or ranked[0][1] == ranked[1][1]:
            checks.append(f"{rid} {party}: the runoff has {len(ranked)} candidates or a tie")
            continue
        nrunoffs += 1
        nominee[(rid, code)] = ranked[0][0]
        for name, votes, _mark in c["cands"]:
            inc, mid = identify(rid, name)
            shown_name, caps = shown(printed.get((rid, fold(name)), name))
            note = [CAPS_NOTE] if caps else []
            cands.append([rid, f"runoff-{code}", RUNOFF, shown_name, party, party_code(party), None, inc, 0, votes, pct(votes, total),
                          "advanced" if name == ranked[0][0] else "lost", mid, SRC["runoff"], note])

    # each party's nominee must be its candidate on the November list; one who is not keeps "advanced", with a note
    gone = []
    for (rid, code), name in sorted(nominee.items()):
        if not name:
            continue
        on = [g[3] for g in general if g[0] == rid and PARTY[code] in (g[4] or "").split(", ")]
        if any(fold(x) == fold(name) for x in on):
            continue
        st = off.get((rid, fold(name)))
        text = ("Won the party's nomination but is not on the Election Commission's November list"
                + (f", which gives the status \"{st}\"." if st else ".")
                + (f" The list's {PARTY[code]} candidate is {on[0]}." if on else ""))
        final = f"runoff-{code}" if any(c[0] == rid and c[1] == f"runoff-{code}" for c in cands) else f"primary-{code}"
        for c in cands:
            if c[0] == rid and c[1] == final and fold(c[3]) == fold(name):
                c[14].append(text)
        gone.append(f"{name} ({rid}, {st or 'not on the list'})")
        if not st:
            checks.append(f"{rid}: the {PARTY[code]} nominee, {name}, is not on the November list at all")

    # a candidate who serves today in another seat or office: the name fits exactly one sitting legislator or official of
    # the same party, who is not a candidate for their own seat this year
    rows = general + cands
    holding = {c[12] for c in rows if c[7] and c[12]}
    for c in rows:
        if c[7] or c[12]:
            continue
        party = (c[4] or "").split(", ")[0]
        pool = [p for p in people if p["id"] not in holding and (p["party"] or "") == party and person_fits(c[3], p)]
        if len(pool) == 1:
            c[12] = pool[0]["id"]
            c[14].append(f"Serves today {where(pool[0])}.")
        elif len(pool) > 1:
            checks.append(f"{c[0]}: {c[3]} fits {len(pool)} sitting members of the same party; none is taken")
    cands = [c[:14] + [" ".join(c[14]) or None] for c in rows]

    # 7. per race: its counties (the list's Associated Counties, checked against the counties the results counted in)
    all_geoids = sorted(g for g, _n in counties.values())
    reach, unmatched = {}, set()
    for lab, o in gen_list["offices"].items():
        for office, where_text in o["counties"].items():
            k = list_office(office)
            if k in STATEWIDE:
                continue
            geo = set()
            for n in [x.strip() for x in where_text.split(",") if x.strip()]:
                g = counties.get(county_key(n))
                if g:
                    geo.add(g[0])
                else:
                    unmatched.add(n)
            reach[f"2026-{STATE}-{k}"] = geo
    for n in sorted(unmatched):
        checks.append(f"a county on the list the Census file does not name: {n}")
    for rid, r in races.items():
        if r["level"] == "statewide":
            r["county_ids"] = json.dumps(all_geoids)
            continue
        geo = reach.get(rid)
        r["county_ids"] = json.dumps(sorted(geo)) if geo else None
        if not geo:
            checks.append(f"{rid}: the list gives no counties for this district")
        counted = set()
        for kind in ("primary", "runoff"):
            for (k, code), c in book[kind].items():
                if f"2026-{STATE}-{k}" == rid:
                    counted |= {counties[county_key(n)][0] for n in c["counties"] if county_key(n) in counties}
        if geo and counted - geo:
            checks.append(f"{rid}: the results count votes in counties the list does not name for the district")
    for rid, r in races.items():
        if not any(c[0] == rid and c[1] == "general" for c in cands):
            r["note"].append(NONE_ON_LIST)
            checks.append(f"{rid}: no candidates on the November list")

    # 8. the last look at every stored text: nothing that looks like a contact detail reaches the database
    for c in cands:
        if CONTACT.search(c[3]) or CONTACT.search(c[4] or "") or (c[14] and CONTACT_NOTE.search(c[14])):
            raise SystemExit(f"South Carolina (state races): a stored cell for {c[0]} failed the contact-detail check (not shown)")
    for r in races.values():
        if CONTACT_NOTE.search(" ".join(r["note"])) or CONTACT.search(r["holder_name"] or ""):
            raise SystemExit(f"South Carolina (state races): the note or holder for {r['race_id']} failed the contact-detail check (not shown)")
    keys = [(c[0], c[1], c[3]) for c in cands]
    if len(keys) != len(set(keys)):
        raise SystemExit("South Carolina (state races): two candidate rows share race, election and name")
    gen = [c for c in cands if c[1] == "general"]
    prim = [c for c in cands if c[1] != "general"]
    if len(active) != sum(len(rs) for rs in grouped.values()) or len(gen) != len(grouped):
        raise SystemExit(f"South Carolina (state races): {len(active)} Active rows on the list, {len(gen)} candidates stored")
    for kind in ("primary", "runoff"):
        want = sum(len(c["cands"]) for c in book[kind].values() if kind == "runoff" or len(c["cands"]) > 1)
        got = sum(1 for c in prim if c[1].startswith(kind + "-"))
        if want != got and not (kind == "runoff" and got < want):
            checks.append(f"{kind}: {want} result lines, {got} stored")

    # 9. write South Carolina's rows only, in one transaction
    race_rows = [tuple(" ".join(r["note"]) or None if k == "note" else r[k] for k in (
        "race_id", "state", "level", "office_kind", "office", "jurisdiction", "jurisdiction_id", "county_ids", "district", "seat", "special",
        "partisan", "holder_id", "holder_name", "holder_party", "election_date", "note")) for r in races.values()]
    place_rows = [("county", g, f"{n} County", json.dumps([g]), SRC_COUNTY) for g, n in sorted(counties.values())]
    for rid, r in sorted(races.items(), key=lambda x: (x[1]["level"], int(x[1]["district"] or 0))):
        if r["level"] == "legislature":
            place_rows.append(("house", r["jurisdiction_id"], r["jurisdiction"], r["county_ids"], SRC_GENERAL))
    status_words = "; ".join(f"{k}: {v}" for k, v in sorted(by_status.items()))
    sites = meta["sites"]
    sources = [
        (SRC_GENERAL, STATE, "official candidate list", AGENCY,
         "Candidate Tracking System: 11/3/2026 Statewide General Election, state offices", gen_list["url"], "", mtime(lpath), sha(lpath),
         sum(len(o["rows"]) for o in gen_list["offices"].values()),
         f"Read through the page's own search ({CTS_PAGE}, then /Candidate/CandidateSearch/) for {len(gen_list['offices'])} state offices "
         f"({', '.join(gen_list['offices'])}), every status, party and filing location. Columns taken by heading; kept: Office, Name on "
         "Ballot, Running Mate, Party, Candidate Status, and Associated Counties once per office (the counties a district covers). "
         "Location of Filing is never kept; the detail pages with contact details are never asked for, nor the export. Status Active "
         f"is on the November ballot. Every status on the list: {status_words}. The list gives no ballot positions (it is sorted by "
         "surname), so no ballot order is stored; it carries no write-in candidates. The office list for this election offers no "
         "State Senate office: the Senate is elected in presidential years. The SHA-256 is of the kept cells; each search answer's own "
         "SHA-256 is kept with them."),
        (SRC_PRIMARY_LIST, STATE, "official candidate list", AGENCY,
         "Candidate Tracking System: 6/9/2026 Statewide Primary, state offices", pri_list["url"], "", mtime(lpath), sha(lpath),
         sum(len(o["rows"]) for o in pri_list["offices"].values()),
         "Read the same way, the same cells kept, to check the primary results. It holds only contested primaries"
         + (f", and not all of them: it omits {', '.join(omitted)}, whose candidates are on the general election's list (Active or "
            "Defeated In Primary) and agree with the results" if omitted else "")
         + ". Every name in the results must be on this list or the general election's for its seat and party, every candidate either "
         "list marks Defeated In Primary must be in the results, and a party with two candidates or more on the lists must have a "
         "primary in the results. Not stored as rows of its own."),
        (SRC_ROSTER, STATE, "member roster", "Open States people project (CC0), as loaded into state_sc.sqlite",
         "Sitting South Carolina legislators and statewide officials", "https://github.com/openstates/people", "", mtime(roster_db),
         sha(roster_db), len(legs) + len(offs),
         "Who holds each seat today, and which candidate is a sitting member (same chamber and district, the name fits, one fit only; a "
         "member of another seat only when the name fits exactly one sitting legislator or official of the same party). The roster's "
         "elected statewide officials are the Governor, Lieutenant Governor and Attorney General only; for the other statewide offices "
         "the holder is left empty. Names, party and ids only."),
        (SRC_COUNTY, STATE, "county codes", "U.S. Census Bureau", "Cartographic boundary file, counties, 2024 (1:500,000)", COUNTY_URL,
         "2024", mtime(county_zip), sha(county_zip), len(counties),
         "Five-digit county codes (GEOID) for South Carolina's 46 counties, matched by name to the candidate list's Associated Counties."),
    ]
    for kind in ("primary", "runoff", "recount"):
        m = sites[kind]
        n = sum(1 for c in prim if c[13] == SRC[kind])
        up = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", m.get("updated") or "")
        body = (f"The Commission's results site ({m['page']}, hosted by Clarity Elections, linked as \"{m['label']}\" from {RESULTS_PAGE}), "
                f"headed \"{m['heading']}\", version {m['version']}, last updated {m['updated']}; {m['counties']} counties completely "
                f"reported and marked certified; the same file the federal loader reads. {len(book[kind])} state contests read. Every "
                "candidate's vote types and counties add up to the statewide total, and the summary report (summary.csv) gives the same "
                "totals. No write-in line is reported, so a field's total is the sum of its candidates' votes.")
        if kind == "recount":
            body += (" Its contests replace the June 9 figures: " + "; ".join(c["office"] for c in book["recount"].values()) + ".")
        if kind == "primary":
            body += (" Federal contests and the parties' advisory questions are left out. A name the results mark (\"Decertified before "
                     "Primary\") is kept with its votes and the mark in its note.")
        sources.append((SRC[kind], STATE, "official results", AGENCY, f"{m['name']} ({m['date']}), Official Results: detail report (XML), "
                        "state offices", m["detail_url"],
                        f"{up.group(3)}-{int(up.group(1)):02d}-{int(up.group(2)):02d}" if up else "",
                        mtime(os.path.join(folder, m["detail"])), sha(os.path.join(folder, m["detail"])), n, body))
    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA)
    with con:
        con.execute("DELETE FROM sl_candidates WHERE race_id IN (SELECT race_id FROM sl_races WHERE state = ?) OR race_id LIKE ?",
                    (STATE, f"2026-{STATE}-%"))
        con.execute("DELETE FROM sl_races WHERE state = ?", (STATE,))
        con.execute("DELETE FROM sl_sources WHERE state = ?", (STATE,))
        con.execute("DELETE FROM sl_places WHERE source_id LIKE ? OR (kind = 'county' AND id LIKE ?) OR id LIKE ?",
                    (f"{STATE.lower()}-%", f"{FIPS}___", f"{STATE}-%"))
        con.executemany("INSERT INTO sl_races VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", race_rows)
        con.executemany("INSERT INTO sl_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [tuple(c) for c in cands])
        con.executemany("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", sources)
        con.executemany("INSERT INTO sl_places VALUES (?,?,?,?,?)", place_rows)
    con.close()

    # 10. say what happened
    per = lambda level, rows: sum(1 for c in rows if races[c[0]]["level"] == level)
    n_state = sum(1 for r in races.values() if r["level"] == "statewide")
    n_house = sum(1 for r in races.values() if r["_kind"] == "state_house")
    left_off = sum(v for k, v in by_status.items() if k not in ON)
    say(f"    South Carolina state offices: {len(races)} races ({n_state} statewide, {n_house} House; the Senate is not up in 2026"
        + (f", but the office list offers {senate_offered}" if senate_offered else "") + f"); {len(gen)} candidates on the November list "
        f"(statewide {per('statewide', gen)}, House {per('legislature', gen)}; {left_off} rows with other statuses left off); {fields} "
        f"primary fields and {nrunoffs} runoffs, {len(prim)} primary rows (statewide {per('statewide', prim)}, House "
        f"{per('legislature', prim)}), official votes reconciled" + (f"; recount figures for {len(replaced)} contest(s)" if replaced else ""))
    if mates:
        say("      Governor tickets: " + "; ".join(mates))
    if gone:
        say("      nominees not on the November list: " + "; ".join(gone))
    if omitted:
        say(f"      the June 9 list omits {len(omitted)} contested primaries ({', '.join(omitted)}); their names were checked against the "
            "general election's list instead")
    for c in cands:
        if c[12]:
            line = f"{c[0]} {c[1]}: {c[3]} -> {c[12]}{' (holds this seat)' if c[7] else ''}"
            matched.append(line)
    say(f"      matched to the roster: {len(matched)} candidate rows ({sum(1 for c in gen if c[7])} November candidates hold their seat)")
    for line in matched:
        if " (holds this seat)" not in line:
            say(f"      matched: {line}")
    for line in checks:
        say(f"      check: {line}")
    return dict(races=len(races), general=len(gen), primary=len(prim), fields=fields, runoffs=nrunoffs, checks=checks)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="South Carolina's state races on the November 3, 2026 ballot")
    ap.add_argument("db", help="the state-and-local ballot database to write South Carolina's rows into")
    a = ap.parse_args()
    load(a.db)
