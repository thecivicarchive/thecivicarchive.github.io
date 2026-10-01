"""
ballot/state_local_sc.py - South Carolina's state races on the November 3, 2026 ballot, into ballot_local_2026.sqlite:

  - the seven statewide races of a midterm year (four-year terms, all last elected in 2022): Governor and Lieutenant
    Governor (one ticket to a party), Secretary of State, State Treasurer, Attorney General, Comptroller General, State
    Superintendent of Education and Commissioner of Agriculture;
  - all 124 seats of the House of Representatives (two-year terms).
The Senate's 46 seats are elected for four years in presidential years (last in 2024, next in 2028), and the
Commission's office list for the November 3 election offers no State Senate office, so no regular Senate seat is
stored; a State Senate office on that list stops the loader. Which offices are up is a fixed list checked against the
Commission's own: every office above must be on the general election's office list, and a state office there that is
not above stops the loader. The federal ballot database is never opened here.

The county and local part (from "the county and local part" down) adds every other contest between people that the
Commission lists for November 3, 2026:
  - from the statewide general election's own list: county offices (county council, auditor, treasurer, probate
    judge, sheriff, coroner, clerk of court, register of deeds, supervisor), the circuit solicitors, soil and water
    district commissioners, school boards, and watershed, fire, public service and public works districts;
  - from the elections the Commission lists as elections of their own on the same day (its page's "Local Elections"
    and "Special Elections" kinds): city and town offices, a few school districts, and special elections. One of them
    is a state race, the special election for State Senate District 15, stored with the Legislature.
Each election's list is read twice by two routes, the whole list (office "All") and office type by office type, and
the two must hold the same rows; the set of elections is checked against the Commission's 2026 Election Calendar (a
PDF of election numbers, names, kinds and counties). The list names a school board only by its county and a district
or seat number (the four York County districts and the districts with elections of their own are named), so a
school contest is filed under the county in the list's own words and no school district is guessed. A city or town is
the one incorporated place of the Census Bureau's 2020 place codes that the election's name names among the places of
its counties. The list never says how many seats a contest fills and gives no ballot order; write-in candidates,
ballot questions and local primaries are not loaded. What could not be loaded goes to sl_gaps, and two plain notes
(which local offices are elected when, and what the list covers) to sl_notes.
Levels: county offices (probate judge and clerk of court among them) are level county, filed under the county's
five-digit code; a soil and water commission is its county's; a circuit solicitor is elected by a judicial circuit of
several counties, which is neither a county nor a court of this state's rows, so it is level other with a place of
kind special (SC-X-judicial-circuit-<n>); watershed, fire, public service and public works districts are level other;
a town is an incorporated municipality, so level city. The Commission's table of municipal elections (a workbook of
every city's and town's election day) gives the counts in the calendar note and names the towns it says vote in
November of even years that have no November 3, 2026 election on the Commission's lists.

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
contact detail, and the load stops (without showing it) if one does. The local part keeps five cells of a row
(Office, Associated Counties, Name on Ballot, Party, Candidate Status) in ballot_cache/sc/local/; a name cell that
holds anything but a name is blanked before it is kept, and counted. The calendar, the Commission's table of
municipal elections and the Census place codes carry no personal details.

    python -m ballot.state_local_sc <path to a test database>
"""

import collections
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
import unicodedata
import uuid
import zipfile
import xml.etree.ElementTree as ET
from urllib.parse import urlencode

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from ballot.check_local import EXTRA_SCHEMA, contact_like  # noqa: E402
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

# the office list: local offices (county, school, circuit and special districts), which the state part sets aside and
# the county and local part below reads
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
SENATE_SPECIAL_NOTE = ("A special election for the rest of the term (the Election Commission's list: \"Unexpired Term\"), which the "
                       "Commission lists as an election of its own held with the November 3 general election. Who holds the seat today "
                       "is not shown here, because a seat filled by special election may be vacant. The primary that chose the nominees "
                       "is not shown.")


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


# ================================================================================================ the county and local part

LOCAL_FILE = "sc_2026_local_candidate_lists.json"
LOCAL_KEEP = ("Office", "Associated Counties", "Name on Ballot", "Party", "Candidate Status")
ELECTION_KINDS = ("General", "Local", "Special")              # the election page's own three kinds, asked in this order
PLACE_FILE = "census_st45_sc_place2020.txt"
PLACE_URL = "https://www2.census.gov/geo/docs/reference/codes2020/place/st45_sc_place2020.txt"
PLACE_HEAD = ["STATE", "STATEFP", "PLACEFP", "PLACENS", "PLACENAME", "TYPE", "CLASSFP", "FUNCSTAT", "COUNTIES"]
CALENDAR_FILE = "sc_2026_election_calendar.pdf"
CALENDAR_URL = "https://scvotes.gov/wp-content/uploads/2026/09/2026-9-28.pdf"
MUNI_FILE = "sc_2026_municipal_elections.xlsx"
MUNI_URL = "https://scvotes.gov/wp-content/uploads/2026/05/2026-05-12-Municipal-Elections-scVOTES.xlsx"
MUNI_HEAD = ("County", "Municipality", "Odd Year Election", "Even Year Election", "Election Day", "Who Does Work of Conducting Election?",
             "Partisan or Non-Partisan?")
CODE_URL = "https://www.scstatehouse.gov/code/t07c013.php"
SRC_LOCAL, SRC_OWN = "sc-sec-2026-local-general-list", "sc-sec-2026-local-elections-lists"
SRC_SENATE = "sc-sec-2026-sl-senate-special-list"
SRC_CALENDAR, SRC_MUNI, SRC_PLACE = "sc-sec-2026-election-calendar", "sc-sec-2026-municipal-elections-table", "sc-census-2020-places"
LOCAL_LEVELS = ("county", "soil_water", "city", "township", "school", "hospital", "other")
NONPARTISAN = "Nonpartisan office"
KNOWN_KINDS = {"county_commissioner", "sheriff", "county_attorney", "county_auditor", "county_treasurer", "county_auditor_treasurer",
               "county_recorder", "county_surveyor", "county_park", "soil_water", "mayor", "council", "city_clerk", "city_treasurer",
               "city_clerk_treasurer", "town_supervisor", "town_clerk", "town_treasurer", "town_clerk_treasurer", "school_board",
               "hospital_board", "utility_board", "sanitary_board"}                 # the kinds the pages already know

# county offices: the general election's office type -> (office kind, the office in plain words)
COUNTY_OFFICES = {"Sheriff": ("sheriff", "Sheriff"), "Probate Judge": ("probate_judge", "Probate Judge"),
                  "Clerk of Court": ("clerk_of_court", "Clerk of Court"), "Coroner": ("coroner", "Coroner"),
                  "Auditor": ("county_auditor", "Auditor"), "County Treasurer": ("county_treasurer", "County Treasurer"),
                  "County Supervisor": ("county_executive", "County Supervisor"), "Register of Deeds": ("register_of_deeds", "Register of Deeds"),
                  "County Council Chair": ("county_board_chair", "County Council Chair")}
SCHOOL_TYPE = re.compile(r"^(Board of Education|School )")
MUNI_TYPE = re.compile(r"^(Mayor|Town Council|City Council)")
SCHOOL_PREFIX = (("Board of Education District, ", "Board of Education"), ("Board of Education, ", "Board of Education"),
                 ("School Trustee District, ", "School Trustee"), ("School Trustee, ", "School Trustee"),
                 ("School Board District, ", "School Board"), ("School Board, ", "School Board"),
                 ("School District At Large, ", "School Board"))
# an office type a city or town election offers with no candidate under it: (office kind, the office, what the type elects by)
EMPTY_TYPES = {"Mayor": ("mayor", "Mayor", None), "Town Council": ("council", "Town Council", None),
               "Town Council Ward": ("council", "Town Council", "ward"), "City Council Seat": ("council", "City Council", None),
               "City Council Seat at Large": ("council", "City Council", "At Large"), "City Council at Large": ("council", "City Council", "At Large"),
               "City Council District": ("council", "City Council", "district"), "City Council Ward": ("council", "City Council", "ward"),
               "Commissioner of Public Works": ("utility_board", "Commissioner of Public Works", None)}
ONE_SEAT = {"mayor", "sheriff", "probate_judge", "clerk_of_court", "coroner", "county_auditor", "county_treasurer", "county_executive",
            "register_of_deeds", "county_board_chair", "solicitor"}
UNEXPIRED = re.compile(r"\s*\(Unexpired Term\)", re.I)
LOCAL_NOT_A_NAME = re.compile(r"@|https?:|www\.|\.(?:com|org|net|gov|us)\b|\d(?!(?:nd|rd|th)\b)", re.I)
# what the page's own guard refuses in a note: a number followed soon after by a street word (Court and Place included)
PAGE_STREET = re.compile(r"\b\d{1,6}\s+(?:[NSEW]\.?\s+)?[A-Za-z0-9.' -]{1,40}?\s(?:St|Street|Ave|Avenue|Rd|Road|Blvd|Boulevard|Dr|Drive|Ln|"
                         r"Lane|Way|Ct|Court|Cir|Circle|Pkwy|Parkway|Hwy|Highway|Trl|Trail|Pl|Place|Ter|Terrace)\b\.?", re.I)
CAL_LINE = re.compile(r"^(\d{2})/(\d{2})/(\d{4}) (\d{5}) (?:\d{2}-([A-Z]+)|(ALL)) (.+?) (General|Special|Primary|Referendum)( \*)? "
                      r"(?:\d{1,2}/\d{1,2}/\d{4} - \d{1,2}/\d{1,2}/\d{4}|-)$")

SEATS_NOTE = "The Election Commission's list does not say how many seats this contest fills."
SCHOOL_NOTE = ("The Election Commission's list names this school board only by its county and a district or seat number, and does not say "
               "how many seats the contest fills.")
UNEXPIRED_NOTE = "An election for the rest of an unexpired term, as the Election Commission's list titles it."
OWN_SPECIAL_NOTE = "A special election, which the Election Commission lists as an election of its own held with the November 3 general election."
NO_CANDIDATE_NOTE = "No candidate is on the Election Commission's list for this office."
OWN_ELECTION_NOTE = ("The Commission's table of municipal elections says the town conducts its own election, so its candidates may be on "
                     "file with the town only.")
OTHER_PARTY_NOTE = "The Election Commission's list gives this candidate's party as \"{}\"."


class LocalError(SystemExit):
    pass


def flat(text):
    return re.sub(r"\s+", " ", str(text or "")).strip()


def slug(text):
    t = unicodedata.normalize("NFKD", str(text or ""))
    t = "".join(c for c in t if not unicodedata.combining(c)).replace("'", "").replace("’", "")
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")


def spell(text):
    """A name as it is compared: capitals, a hyphen as a space, no other punctuation."""
    return flat(re.sub(r"[^A-Z0-9 ]", "", str(text or "").upper().replace("-", " ")))


def and_list(items):
    items = [i for i in items if i]
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1] if items else ""


def day_words(iso):
    d = dt.date.fromisoformat(iso)
    return f"{d:%B} {d.day}, {d.year}"


def local_name(raw):
    """A local candidate's name as filed, or "" when the cell holds something other than a name (a digit that is not an
    ordinal, "@", a web address, or anything ballot.check_local reads as contact details). Never printed either way."""
    name = flat(raw)
    return "" if not name or LOCAL_NOT_A_NAME.search(name) or contact_like(name, True) else name


def state_or_federal(office):
    """An office (the form's office type, or a row's office) that the state part or the federal pages read."""
    o = flat(office)
    return bool(FEDERAL.match(o) or o.startswith(HOUSE_LABEL) or any(o in v[2] for v in STATEWIDE.values()))


# ---------------------------------------------------------------------------------------- reading the Commission's lists

def local_grid(body, where):
    """([{kept column: cell}], how many cells were blanked) from one search answer. Columns are taken by heading and only
    the five kept cells of a row are made into text; Running Mate and Location of Filing are never kept. A name cell that
    holds anything but a name, and any other kept cell that reads like an e-mail, a telephone or a web address, is blanked
    before it is kept, and counted. A layout that no longer fits stops the loader, which names the answer and the row's
    number, never the row."""
    t = body.decode("utf-8", "replace")
    head = [flat(re.sub(r"<[^>]+>", " ", h)) for h in re.findall(r"<th[^>]*>(.*?)</th>", t, re.S)]
    missing = [k for k in LOCAL_KEEP if k not in head]
    if missing:
        raise LocalError(f"South Carolina (local races): the candidate search's columns changed for {where} (no {', '.join(missing)})")
    idx = {k: head.index(k) for k in LOCAL_KEEP}
    rows, blanked = [], 0
    for m in re.finditer(r"<tr([^>]*)>(.*?)</tr>", t, re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", m.group(2), re.S)
        if not cells:
            continue
        at = re.search(r'data-index="(\d+)"', m.group(1))
        if len(cells) != len(head) or not at or int(at.group(1)) != len(rows):
            raise LocalError(f"South Carolina (local races): row {len(rows) + 1} of the answer for {where} does not fit the table's "
                             "header or its numbering (the row is not shown)")
        rec = {k: flat(html.unescape(re.sub(r"<[^>]+>", " ", cells[i]))) for k, i in idx.items()}
        del cells
        for k in LOCAL_KEEP:                                 # a cell that reads like an e-mail, a telephone or a web address is not kept
            if k != "Name on Ballot" and contact_like(rec[k], False):
                rec[k] = ""
                blanked += 1
        rec["Name on Ballot"] = local_name(rec["Name on Ballot"])
        blanked += not rec["Name on Ballot"]
        rows.append(rec)
    del t
    return rows, blanked


def read_election(s, token, kind, eid, display, name):
    """One election of the Candidate Tracking System, read twice: the whole list (office "All") and office type by office
    type. The two routes must hold the same rows. Only the kept cells are returned; for the statewide general election the
    state and federal rows (read elsewhere) are counted and dropped."""
    page = s.ask(CTS_PAGE, urlencode({"ElectionKindSid": kind, "ElectionYear": "2026", "ElectionID": eid,
                                      "__RequestVerificationToken": token}).encode(),
                 ctype="application/x-www-form-urlencoded").decode("utf-8", "replace")
    form = re.search(r'<form id="searchForm">(.*?)</form>', page, re.S)
    if not form or f'name="ElectionId" value="{eid}"' not in form.group(1):
        raise LocalError(f"South Carolina (local races): the candidate search for election {eid} ({display}) did not open")
    export = re.search(r'name="ExportFileName" value="([^"]*)"', form.group(1))

    def options(select_id):
        sel = re.search(rf'<select[^>]*id="{select_id}"[^>]*>(.*?)</select>', form.group(1), re.S)
        return [(a, flat(html.unescape(b))) for a, b in re.findall(r'<option[^>]*value="([^"]*)"[^>]*>([^<]*)', sel.group(1))] if sel else []

    def search(value):
        fields = [("ElectionId", eid), ("ExportFileName", export.group(1) if export else ""), ("SelectedOffice", value),
                  ("CandidateFirstName", ""), ("CandidateLastName", ""), ("SelectedCandidateStatus", "All"),
                  ("SelectedPoliticalParty", "All"), ("SelectedFilingLocation", "All")]
        b = "----sc" + uuid.uuid4().hex
        data = "".join(f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n' for k, v in fields) + f"--{b}--\r\n"
        return s.ask(f"{CTS}/Candidate/CandidateSearch/", data.encode(), ctype=f"multipart/form-data; boundary={b}")

    opts = {label: value for value, label in options("SelectedOffice")}
    rec = {"id": eid, "kind": kind, "display": display, "name": name, "url": f"{CTS}/Candidate/CandidateSearch?electionId={eid}",
           "offered": [o for o in opts if o != "All"], "counties": [label for _v, label in options("SelectedAssociatedCounties")],
           "types": {}}
    if not rec["offered"]:
        return rec                                          # no office at all: a question put to the voters
    if "All" not in opts:
        raise LocalError(f"South Carolina (local races): the candidate search for {display} no longer offers every office at once")
    body = search(opts["All"])
    whole, blanked = local_grid(body, f"{display}, every office")
    rest = [r for r in whole if not (kind == "General" and state_or_federal(r["Office"]))]
    rec["all"] = {"sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body), "rows": len(whole),
                  "state_and_federal_rows": len(whole) - len(rest), "blanked": blanked}
    del body
    typed = []
    for o in rec["offered"]:
        if kind == "General" and state_or_federal(o):
            continue
        body = search(opts[o])
        rows, blanked = local_grid(body, f"{display}, {o}")
        rec["types"][o] = {"sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body), "blanked": blanked, "rows": rows}
        typed += rows
        del body
    key = lambda r: tuple(r[k] for k in LOCAL_KEEP)
    if collections.Counter(map(key, rest)) != collections.Counter(map(key, typed)):
        raise LocalError(f"South Carolina (local races): the whole list of {display} and its lists office by office do not hold the "
                         f"same rows ({len(rest)} against {len(typed)}); read it again")
    return rec


def read_local_lists(part, say):
    """Every election the Candidate Tracking System dates November 3, 2026, each read by read_election. The elections already
    read in a run that stopped part-way (within six hours) are not asked for again."""
    s = Session()
    seen, todo = set(), []
    for kind in ELECTION_KINDS:
        for e in json.loads(s.ask(f"{CTS}/Candidate/GetElections?electionType={kind}&year=2026", accept="application/json")):
            eid = str(e.get("electionId"))
            if str(e.get("electionDate", "")).startswith(GENERAL) and eid not in seen:
                seen.add(eid)
                todo.append((kind, eid, flat(e.get("displayName")), flat(e.get("electionName"))))
    statewide = [t for t in todo if t[0] == "General"]
    if len(statewide) != 1 or statewide[0][2] != LISTS["general"][0]:
        raise LocalError(f"South Carolina (local races): the Candidate Tracking System lists {len(statewide)} statewide elections on "
                         f"{GENERAL}, not the one named {LISTS['general'][0]!r}")
    tok = re.search(r'name="__RequestVerificationToken" type="hidden" value="([^"]+)"', s.ask(CTS_PAGE).decode("utf-8", "replace"))
    if not tok:
        raise LocalError("South Carolina (local races): the Candidate Tracking System's election page changed (no form token)")
    done = {}
    if os.path.exists(part) and time.time() - os.path.getmtime(part) < 6 * 3600:
        done = {e["id"]: e for e in json.load(open(part, encoding="utf-8")).get("elections", [])}
    out = {"read": dt.date.today().isoformat(), "page": CTS_PAGE, "kept": list(LOCAL_KEEP), "elections": []}
    for kind, eid, display, name in todo:
        rec = done.get(eid)
        if rec is None or rec.get("display") != display:
            rec = read_election(s, tok.group(1), kind, eid, display, name)
        out["elections"].append(rec)
        with open(part, "w", encoding="utf-8") as fh:
            json.dump(out, fh, ensure_ascii=False)
    say(f"      Candidate Tracking System: {len(out['elections'])} elections dated November 3 read, each whole and office by office")
    return out


def local_lists(folder, say, max_age_days=2):
    """(path, the kept cells of every November 3 election's list). Read afresh after two days; if it cannot be read again
    the copy on disk is used and the caller is told."""
    path = os.path.join(folder, LOCAL_FILE)
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < max_age_days * 86400:
        return path, json.load(open(path, encoding="utf-8"))
    part = path + ".part"
    try:
        out = read_local_lists(part, say)
    except (SystemExit, OSError) as e:
        if os.path.exists(path):
            say(f"      could not read the local candidate lists again ({e}); using the copy read earlier")
            return path, json.load(open(path, encoding="utf-8"))
        raise
    with open(part, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=0)
    os.replace(part, path)
    return path, out


def census_places(path):
    """({name in capitals: [(place code, name as the Bureau writes it, kind word, {county keys})]}, how many) for South
    Carolina's incorporated cities and towns, from the Census Bureau's 2020 place codes."""
    with open(path, encoding="utf-8-sig", errors="replace") as fh:
        lines = fh.read().splitlines()
    if not lines or lines[0].split("|") != PLACE_HEAD:
        raise LocalError(f"South Carolina (local races): {os.path.basename(path)} does not begin with the header this loader was checked against")
    out, n = collections.defaultdict(list), 0
    for ln in lines[1:]:
        f = ln.split("|")
        if len(f) < 9 or f[1] != FIPS or not f[5].upper().startswith("INCORPORATED"):
            continue
        base, _, kind = f[4].rpartition(" ")
        if kind not in ("city", "town") or not re.fullmatch(r"\d{5}", f[2]):
            raise LocalError(f"South Carolina (local races): line {n + 2} of {os.path.basename(path)} is an incorporated place that is "
                             "neither a city nor a town, or has no five-digit code")
        out[spell(base)].append((f[2], f[4], kind, {county_key(c) for c in f[8].split("~~~") if c.strip()}))
        n += 1
    return out, n


def election_calendar(folder, say):
    """The Commission's 2026 Election Calendar (election numbers, names, kinds and counties; no personal details):
    {"dated", "lines", "elections": {number: {"date", "name", "type", "counties", "multiple"}}}, or None when it cannot be
    read (the caller says so and goes on without the cross-check)."""
    from states import net
    path = os.path.join(folder, CALENDAR_FILE)
    try:
        net.download(CALENDAR_URL, path, max_age_days=3650, say=say)
        if open(path, "rb").read(5) != b"%PDF-":
            os.remove(path)
            raise OSError("the address did not give a PDF")
        from ballot import pdftext
        lines = [flat(t) for _pg, _y, t in pdftext.lines(path)]
    except (OSError, ValueError, KeyError, IndexError) as e:
        say(f"      the Commission's 2026 Election Calendar could not be read ({e}); the elections are not cross-checked against it")
        return None
    out, bad, dated = {}, 0, ""
    for ln in lines:
        m = re.match(r"^(\d{2})/(\d{2})/(\d{4}) SOUTH CAROLINA Page \d+ Of \d+$", ln)
        if m:
            dated = f"{m.group(3)}-{m.group(1)}-{m.group(2)}"
            continue
        if not re.match(r"^\d{2}/\d{2}/\d{4} \d{5} ", ln):
            continue
        m = CAL_LINE.match(ln)
        if not m:
            bad += 1
            continue
        e = out.setdefault(m.group(4), {"date": f"{m.group(3)}-{m.group(1)}-{m.group(2)}", "name": flat(m.group(7)), "type": m.group(8),
                                        "counties": [], "multiple": bool(m.group(9))})
        e["counties"].append(m.group(5) or m.group(6))
    if bad or not out:
        say(f"      {bad} lines of the Commission's 2026 Election Calendar do not fit the layout this loader was checked against; the "
            "elections are not cross-checked against it")
        return None
    return {"path": path, "dated": dated, "lines": sum(len(e["counties"]) for e in out.values()), "elections": out}


def municipal_table(folder, say):
    """The Commission's table of municipal elections (one row a city or town: county, name, odd or even year, election day,
    who conducts the election, partisan or not; no personal details): {"path", "rows": [{"county", "name", "odd", "even",
    "day", "own", "partisan"}]}, or None when it cannot be read."""
    import warnings
    from states import net
    path = os.path.join(folder, MUNI_FILE)
    try:
        net.download(MUNI_URL, path, max_age_days=3650, say=say)
        if open(path, "rb").read(2) != b"PK":
            os.remove(path)
            raise OSError("the address did not give a workbook")
        import openpyxl
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
            grid = [[flat(c) if c is not None else "" for c in r] for r in wb.worksheets[0].iter_rows(values_only=True)]
    except (OSError, ValueError, KeyError, IndexError) as e:
        say(f"      the Commission's table of municipal elections could not be read ({e}); the towns that vote in November are not "
            "checked against it")
        return None
    head = grid[0] if grid else []
    if any(h not in head for h in MUNI_HEAD):
        say("      the Commission's table of municipal elections no longer has the headings this loader was checked against; it is not used")
        return None
    idx = {h: head.index(h) for h in MUNI_HEAD}
    rows = [{"county": r[idx["County"]], "name": r[idx["Municipality"]], "odd": bool(r[idx["Odd Year Election"]]),
             "even": bool(r[idx["Even Year Election"]]), "day": r[idx["Election Day"]],
             "own": r[idx["Who Does Work of Conducting Election?"]].lower() == "city",
             "partisan": r[idx["Partisan or Non-Partisan?"]].lower() == "partisan"} for r in grid[1:] if r[idx["Municipality"]]]
    return {"path": path, "rows": rows}


# ---------------------------------------------------------------------------------------- what each contest is

def school_rule(otype, o, out):
    """A school board office string -> its parts, in the list's own numbers; None when no rule fits."""
    sch = lambda **kw: out(family="school", level="school", kind="school_board", **kw)
    n = lambda x: str(int(x))
    m = re.fullmatch(r"(.+ School District) Trustees?(?: (?:Seat (\d+)|(At[- ]Large)))?", o)
    if m:                                                    # the list names the district itself (York County's four)
        return sch(title="School District Trustee", name=m.group(1), seat=n(m.group(2)) if m.group(2) else ("At Large" if m.group(3) else None))
    if o == "Board of Education Chair":
        return sch(title="Board of Education Chair")
    if o == "School Board At Large":
        return sch(title="School Board", seat="At Large")
    m = re.fullmatch(r"School Board At Large District (\d+)|School Board District (\d+) At Large", o)
    if m:
        return sch(title="School Board", district=n(m.group(1) or m.group(2)), seat="At Large")
    m = re.fullmatch(r"School Board of Trustees District (\d+)", o)
    if m:
        return sch(title="School Board of Trustees", district=n(m.group(1)))
    m = re.fullmatch(r"District (\d+)", o)
    if m and otype.startswith("School Board District"):       # "District 5 (Unexpired Term)": the office type says whose district
        return sch(title="School Board", district=n(m.group(1)))
    for prefix, title in SCHOOL_PREFIX:
        if not o.startswith(prefix):
            continue
        rest = o[len(prefix):]
        m = re.fullmatch(r"(?:District )?(\d+),? Seat (\d+)", rest)
        if m:
            return sch(title=title, district=n(m.group(1)), seat=n(m.group(2)))
        m = re.fullmatch(r"District (\d+) (Area \d+)", rest)
        if m:
            return sch(title=title, district=n(m.group(1)), seat=m.group(2))
        m = re.fullmatch(r"District (\d+) At[- ]Large", rest)
        if m:
            return sch(title=title, district=n(m.group(1)), seat="At Large")
        m = re.fullmatch(r"(?:District|School Board Trustee District|School Board District) (\d+)", rest)
        if m:
            return sch(title=title, district=n(m.group(1)), seat="At Large" if prefix.startswith("School District At Large") else None)
        m = re.fullmatch(r"(\d+) (.+) County", rest)
        if m:
            return sch(title=title, district=n(m.group(1)), named_county=m.group(2))
        return None
    return None


def muni_rule(otype, o, out):
    """A city or town office string -> its parts; None when no rule fits. The council is called what the list calls it."""
    mun = lambda **kw: out(family="muni", level="city", **kw)
    n = lambda x: str(int(x))
    head, _, tail = o.partition(", ")
    if otype == "Mayor":
        return mun(kind="mayor", title="Mayor", name=tail) if head == "Mayor" and tail else None
    if head == "Town Council Ward" and re.fullmatch(r"\d+", tail):
        return mun(kind="council", title="Town Council", district=f"Ward {n(tail)}")
    if head in ("Town Council", "City Council Seat") and tail:
        return mun(kind="council", title=head.replace(" Seat", ""), name=tail)
    if head in ("City Council Seat at Large", "City Council at Large") and tail:
        return mun(kind="council", title="City Council", seat="At Large", name=tail)
    if head == "City Council Ward":
        m = re.fullmatch(r"(?:(.+) )?(Town|City) Council Ward (\d+)", tail)
        return mun(kind="council", title=f"{m.group(2)} Council", district=f"Ward {n(m.group(3))}", name=m.group(1)) if m else None
    if head in ("City Council", "City Council District") and tail:
        if re.fullmatch(r"\d+", tail):
            return mun(kind="council", title="City Council", district=n(tail))
        m = re.fullmatch(r"(.+) City Council Dist(?:rict)? (\d+)", tail)
        if m:
            return mun(kind="council", title="City Council", district=n(m.group(2)), name=m.group(1))
        return mun(kind="council", title="City Council", name=tail)
    return None


def classify(otype, office):
    """What one contest of a list is, from its office type (the search form's own) and its office string: family, level,
    office kind, the office in plain words, district, seat, the district's or town's name where the string carries one, and
    whether the string says "Unexpired Term". None when no rule fits: the caller leaves the contest out and says so."""
    special = bool(UNEXPIRED.search(office))
    o = flat(UNEXPIRED.sub("", office))
    out = lambda **kw: dict(dict(district=None, seat=None, special=special, name=None, named_county=None, word=None), **kw)
    n = lambda x: str(int(x))
    if otype == "State Senate":
        m = re.fullmatch(r"State Senate District (\d+)", o)
        return out(family="senate", level="legislature", kind="state_senate", title="State Senator", district=n(m.group(1))) if m else None
    m = re.fullmatch(r"Solicitor Circuit (\d+)", otype)
    if m:
        return out(family="circuit", level="other", kind="solicitor", title="Solicitor", name=n(m.group(1))) if o == otype else None
    if otype in COUNTY_OFFICES:
        kind, title = COUNTY_OFFICES[otype]
        return out(family="county", level="county", kind=kind, title=title) if o == otype else None
    if otype.startswith("County Council"):
        council = lambda **kw: out(family="county", level="county", kind="county_commissioner", title="County Council", **kw)
        m = re.fullmatch(r"County Council(?: District)?,? District (\d+)", o)
        if m:
            return council(district=n(m.group(1)))
        if o.lower() == "county council at large":
            return council(seat="At Large")
        m = re.fullmatch(r"County Council (.+ Township)", o)          # an at-large seat the list names by township
        return council(seat=m.group(1)) if m else None
    if otype == "Soil and Water District Commission":
        return out(family="soil", level="soil_water", kind="soil_water", title="Soil and Water District Commissioner") if o == otype else None
    if otype == "Watershed Conservation District":
        m = re.fullmatch(r"Watershed Conservation District, (.+)", o)
        return out(family="district", level="other", kind="watershed_board", title="Watershed Conservation District Director",
                   name=m.group(1), word="watershed conservation district") if m else None
    if otype == "Fire District Commissioner":
        m = re.fullmatch(r"Fire District Commissioner, (.+?)(?: Commissioners)?", o)
        return out(family="district", level="other", kind="fire_board", title="Fire District Commissioner", name=m.group(1),
                   word="fire district") if m else None
    if otype == "Public Service District":
        psd = lambda **kw: out(family="district", level="other", kind="public_service_board", title="Public Service District Commissioner",
                               word="public service district", **kw)
        m = re.fullmatch(r"Public Service District, (.+?)(?: District (\d+))?", o)
        if m:
            return psd(name=m.group(1), district=n(m.group(2)) if m.group(2) else None)
        m = re.fullmatch(r"(.+ Public Service District)(?: (Section \d+|At Large))?", o)
        return psd(name=m.group(1), seat=m.group(2)) if m else None
    if otype == "Commissioner of Public Works":
        m = re.fullmatch(r"Commissioner of Public Works, (.+?)(?: (Area \w+))?", o)
        return out(family="works", level="other", kind="utility_board", title="Commissioner of Public Works", name=m.group(1),
                   seat=m.group(2), word="public works commission") if m else None
    if SCHOOL_TYPE.match(otype):
        return school_rule(otype, o, out)
    if MUNI_TYPE.match(otype):
        return muni_rule(otype, o, out)
    return None


def municipality(election_name, ckeys, places):
    """The one incorporated place an election's name names, among the places of the election's counties: (code, name as
    the Bureau writes it, kind word), or None. A name the Commission shortens ("Hilton Head") is taken only when it begins
    exactly one such place's name."""
    words = spell(election_name)
    near = [(base, code, name, kind) for base, entries in places.items() for code, name, kind, cset in entries if cset & ckeys]
    hits = [h for h in near if re.search(rf"\b{re.escape(h[0])}\b", words)]
    if hits:
        longest = max(len(h[0]) for h in hits)
        best = [h for h in hits if len(h[0]) == longest]
        return best[0][1:] if len(best) == 1 else None
    core = flat(re.sub(r"\b(TOWN OF|CITY OF|GENERAL|SPECIAL|SPEC|ELECTION|ELECT|ELEC|TOWN|CITY|COUNCIL|MAYOR)\b", " ", words))
    best = [h for h in near if core and h[0].startswith(core + " ")]
    return best[0][1:] if len(best) == 1 else None


def local_part(lists, counties, places, n_places, cal, muni, say):
    """The lists' local contests -> the rows to write (races, candidates, places, gaps, notes, sources) and the counts
    that reconcile them with the lists. Nothing is written here. The contests for a State Senate seat are handed back
    apart, for the state part to store with the Legislature."""
    cname = {k: n for k, (_g, n) in counties.items()}
    geoid = {k: g for k, (g, _n) in counties.items()}
    words_of = lambda keys: (cname[keys[0]] + " County") if len(keys) == 1 else and_list([cname[k] for k in keys]) + " counties"
    checks, gaps = [], []
    elections = lists["elections"]
    statewide = next(e for e in elections if e["kind"] == "General")
    own = [e for e in elections if e["kind"] != "General"]
    cal_e = (cal or {}).get("elections", {})

    # 0. the elections themselves, against the Commission's calendar
    if cal:
        on_day = {k for k, v in cal_e.items() if v["date"] == GENERAL}
        listed = {e["id"] for e in elections}
        if on_day != listed:
            checks.append(f"the calendar dated {cal['dated']} and the Candidate Tracking System do not list the same November 3 elections "
                          f"(calendar only: {sorted(on_day - listed)}; system only: {sorted(listed - on_day)})")
        for e in elections:
            c = cal_e.get(e["id"])
            if c and c["counties"] != ["ALL"] and e["counties"] and sorted(c["counties"]) != sorted(x.upper() for x in e["counties"]):
                checks.append(f"election {e['id']} ({e['name']}): the calendar and the candidate search name different counties")

    def is_special(e):
        by_name = bool(re.search(r"\bSpec(?:ial)?\b", e["name"], re.I))
        c = cal_e.get(e["id"])
        if c and (c["type"] == "Special") != by_name:
            checks.append(f"election {e['id']} ({e['name']}): the calendar calls it {c['type']}; its name is followed")
        return by_name

    # 1. every contest, in the lists' own order: one for each office string and set of counties under an office type
    contests, questions, empties, rows_read = [], [], [], 0
    for e in elections:
        if not e["offered"]:
            questions.append(e)
            continue
        e_special = e["kind"] != "General" and is_special(e)
        for otype, t in e["types"].items():
            rows_read += len(t["rows"])
            if not t["rows"]:
                empties.append((e, otype, e_special))
                continue
            groups = {}
            for r in t["rows"]:
                groups.setdefault((r["Office"], r["Associated Counties"]), []).append(r)
            for (office, where_text), rows in groups.items():
                contests.append({"e": e, "otype": otype, "office": office, "where": where_text, "rows": rows, "e_special": e_special})

    left_rows = 0

    def leave(c, what, reason):
        nonlocal left_rows
        left_rows += len(c["rows"])
        gaps.append((STATE, "race", "contest-" + slug(f"{c['e']['id']} {c['office']} {c['where']}"),
                     f"{c['office']} ({c['where'].title()})", what, reason, c["e"]["url"]))

    # 2. what each contest is, and which counties its ballot reaches
    found = []
    for c in contests:
        keys = [county_key(x) for x in c["where"].split(",") if x.strip()]
        parties = {r["Party"] for r in c["rows"]}
        if not keys or any(k not in geoid for k in keys):
            leave(c, "a contest whose counties could not be read",
                  "The Election Commission's list names a county for this contest that the Census Bureau's county file does not have, so "
                  "it is not loaded until the list is corrected.")
            continue
        if "Nonpartisan" in parties and len(parties) > 1:
            leave(c, "a contest whose rows disagree about party",
                  "Some rows of this contest in the Election Commission's list say Nonpartisan and others name a party, so it is not "
                  "loaded until they agree.")
            continue
        k = classify(c["otype"], c["office"])
        if k is None:
            leave(c, "a contest this loader has no rule for",
                  "The Election Commission's list names this office in a way this loader has no rule for yet; it is left out rather than "
                  "guessed at.")
            continue
        c.update(k, keys=sorted(keys), partisan=int("Nonpartisan" not in parties))
        c["special"] = int(k["special"] or c["e_special"])
        found.append(c)
    senate = [c for c in found if c["family"] == "senate"]
    found = [c for c in found if c["family"] != "senate"]

    unknown = sorted({r["Candidate Status"] for c in contests for r in c["rows"]} - KNOWN)
    if unknown:
        checks.append(f"statuses on the local lists that the loader does not know, left off the ballot: {unknown}")

    # 3. the jurisdiction of each contest: a county, a judicial circuit, a city or town, a school board, a named district
    muni_of = {}
    for e in own:
        if any(MUNI_TYPE.match(o) for o in e["offered"]):
            ckeys = {county_key(x) for x in e["counties"]}
            hit = municipality(e["name"], ckeys, places)
            if hit:
                muni_of[e["id"]] = dict(code=hit[0], name=hit[1], kind=hit[2], base=spell(hit[1].rpartition(" ")[0]))
            else:                                           # not one place of the Census list: named as the election names it, no code
                w = spell(e["name"])
                core = flat(re.sub(r"\b(TOWN OF|CITY OF|GENERAL|SPECIAL|SPEC|ELECTION|ELECT|ELEC|COUNCIL|MAYOR|DIS(?:T|TRICT)? \d+)\b", " ", w)).title()
                kind = "town" if re.search(r"\bTOWN\b", w) else "city" if re.search(r"\bCITY\b", w) else ""
                muni_of[e["id"]] = dict(code=None, name=flat(f"{core} {kind}"), kind=kind, base=spell(core))
                checks.append(f"election {e['id']} ({e['name']}): its name does not name exactly one incorporated place of its counties "
                              "in the Census Bureau's place codes; the town is named as the election names it, with no place code")
    single_titles = collections.defaultdict(set)             # county -> the school titles of its one-county, unnamed contests
    for c in found:
        if c["family"] == "school" and not c["name"] and len(c["keys"]) == 1 and c["e"]["kind"] == "General":
            single_titles[c["keys"][0]].add(c["title"])
    named_school = {}                                        # an election of its own that names a school district in its title
    for e in own:
        m = re.match(r"^(.*?School Dist(?:rict)?\.? \d+)\b", e["name"])
        if m and all(SCHOOL_TYPE.match(o) for o in e["offered"]):
            named_school[e["id"]] = flat(re.sub(r"\bDist\.?(?= \d)", "District", m.group(1)))

    for c in found:
        fam, keys = c["family"], c["keys"]
        if fam in ("county", "soil"):
            if len(keys) != 1:
                c["bad"] = ("a county office listed under more than one county",
                            "The Election Commission's list files this county office under more than one county, so it cannot be placed "
                            "until the list is corrected.")
                continue
            c.update(jtype="county", jid=geoid[keys[0]], jname=f"{cname[keys[0]]} County")
        elif fam == "circuit":
            c.update(jtype="special", jname=f"Judicial Circuit {c['name']}", jgroup=("circuit", c["name"]), jslug=f"judicial-circuit-{c['name']}", jcode=False)
        elif fam == "muni" or (fam == "works" and c["e"]["id"] in muni_of):
            town = muni_of.get(c["e"]["id"])
            if not town:
                c["bad"] = ("a city or town office in an election that names no town",
                            "The Election Commission lists this city or town office in an election whose offices are not all a town's, so "
                            "the town cannot be told and the contest is not loaded.")
                continue
            tail = spell(re.sub(r"^(Town|City) of ", "", c["name"] or "", flags=re.I))
            if tail and not town["base"].startswith(tail) and not tail.startswith(town["base"]):
                checks.append(f"election {c['e']['id']} ({c['e']['name']}): an office string names another place than the election does; "
                              "the election's town is kept")
            c.update(level="city", jtype="mcd", jname=town["name"], jid=(f"{STATE}-M-{town['code']}" if town["code"] else None),
                     jgroup=("mcd", town["name"]), jslug=slug(town["name"]), jcode=True)
        elif fam == "school":
            if c["name"]:                                    # the string names the district
                c.update(jtype="school", jname=c["name"], jgroup=("school", c["name"]), jslug=slug(c["name"]), jcode=True)
            elif c["e"]["id"] in named_school:               # the election's own name does
                jn = named_school[c["e"]["id"]]
                if c["district"] and re.search(rf"\bSchool District {c['district']}$", jn):
                    c["district"] = None                     # "District 3 Seat 1" in Florence School District 3's own election: Seat 1
                c.update(jtype="school", jname=jn, jgroup=("school", jn), jslug=slug(jn), jcode=True)
            else:                                            # filed under the county, in the list's own words
                home = None
                if c["named_county"]:
                    nk = county_key(c["named_county"])
                    home = nk if nk in keys else None
                elif len(keys) == 1:
                    home = keys[0]
                else:
                    fits_ = [k for k in keys if c["title"] in single_titles.get(k, set())]
                    home = fits_[0] if len(fits_) == 1 else None
                if home is None:
                    jn = f"School boards ({words_of(keys)})"
                    c.update(jtype="school", jname=jn, jgroup=("school", jn), jslug=slug(jn), jcode=False)
                else:
                    jn = f"{cname[home]} County school boards"
                    c.update(jtype="school", jname=jn, jgroup=("school", jn), jslug=slug(jn), jcode=True, home=home)
        else:                                                # a district the list names: watershed, fire, public service, public works
            base = c["name"]
            has = re.search(r"\bDistrict\b", base, re.I) if c["kind"] != "public_service_board" else re.search(r"Public Service District", base, re.I)
            jn = base if has else f"{base} ({c['word']})"
            c.update(jtype="special", jname=jn, jgroup=("special", c["kind"], jn), jslug=slug(jn), jcode=True)
    for c in [c for c in found if c.get("bad")]:
        leave(c, *c["bad"])
    found = [c for c in found if not c.get("bad")]

    # one place for each named thing: contests that share a name and a county are one district, whatever counties each
    # lists; the same name in counties that do not touch (Beaverdam Creek in Edgefield and in Oconee) is two districts
    groups = collections.defaultdict(list)
    for c in found:
        if "jgroup" in c:
            groups[c["jgroup"]].append(c)
    for group, members in groups.items():
        clusters = []                                        # [{county keys}, [contests]]
        for c in members:
            home = {c["home"]} if c.get("home") else set(c["keys"])
            hit = [cl for cl in clusters if cl[0] & home]
            for cl in hit[1:]:
                hit[0][0] |= cl[0]
                hit[0][1] += cl[1]
                clusters.remove(cl)
            if hit:
                hit[0][0] |= home
                hit[0][1].append(c)
            else:
                clusters.append([home, [c]])
        letter = {"mcd": "M", "school": "S"}.get(group[0], "X")
        for keys_, cs in clusters:
            jid = cs[0].get("jid")
            if not jid:
                code = f"{geoid[min(keys_)][2:]}-" if cs[0]["jcode"] and len(keys_) == 1 else ""
                jid = f"{STATE}-{letter}-{code}{cs[0]['jslug']}"
            for c in cs:
                c["jid"] = jid

    # 4. races and candidates
    def rid_of(jid, office, district, seat, special):
        """2026-SC-<the jurisdiction's key>-<the office>[-d<district>][-seat<n>][-S]: the same on every run."""
        jkey = jid[len(STATE) + 1:] if jid.startswith(STATE + "-") else jid
        bits = [f"2026-{STATE}", jkey, slug(office), (("d" + district) if district.isdigit() else slug(district)) if district else "",
                (("seat" + seat) if seat.isdigit() else slug(seat)) if seat else ""]
        return "-".join(b for b in bits if b) + ("-S" if special else "")

    races, cands, ids = [], [], {}
    place_reach, place_name = collections.defaultdict(set), {}
    status_left, placed_rows, merged, names_dropped, no_active = collections.Counter(), 0, 0, 0, 0
    for c in found:
        # a named district's race is keyed by the office kind (its name already says what it is), every other by the office's own words
        rid = rid_of(c["jid"], c["kind"] if c["jtype"] == "special" else c["title"], c["district"], c["seat"], c["special"])
        if not re.fullmatch(rf"2026-{STATE}-[A-Za-z0-9-]+", rid):
            raise LocalError(f"South Carolina (local races): a race id that is not letters, digits and hyphens ({rid!r})")
        if rid in ids:
            raise LocalError(f"South Carolina (local races): two contests of the lists share the race id {rid}")
        cids = sorted(geoid[k] for k in c["keys"])
        on = [r for r in c["rows"] if r["Candidate Status"] in ON]
        twice = collections.Counter((fold(r["Name on Ballot"]), r["Party"] if c["partisan"] else "") for r in on if r["Name on Ballot"])
        if any(v > 1 for v in twice.values()):               # two rows the page could not tell apart: left out, never merged by guess
            leave(c, "a contest listing one name twice",
                  "The Election Commission's list gives the same name twice in this contest" + (" for one party" if c["partisan"] else "")
                  + ", so it is not loaded until the list is corrected.")
            continue
        ids[rid] = c
        for r in c["rows"]:
            if r["Candidate Status"] not in ON:
                status_left[r["Candidate Status"]] += 1
        note = []
        if c["family"] == "circuit":
            note.append(f"Voters throughout {words_of(c['keys'])} elect the solicitor, the judicial circuit's prosecutor.")
        if c["family"] == "school" and c.get("home") and len(c["keys"]) > 1:
            note.append(f"The Election Commission's list files this contest under {words_of(c['keys'])}.")
        if c["e_special"]:
            note.append(OWN_SPECIAL_NOTE)
        if UNEXPIRED.search(c["office"]):
            note.append(UNEXPIRED_NOTE)
        grouped = {}
        for r in on:
            if not r["Name on Ballot"]:
                names_dropped += 1
                continue
            grouped.setdefault(fold(r["Name on Ballot"]), []).append(r)
        lost = sum(1 for r in on if not r["Name on Ballot"])
        if lost:
            note.append(("One name" if lost == 1 else f"{lost} names") + " on the Election Commission's list for this contest could not be read "
                        "as a name and " + ("is" if lost == 1 else "are") + " left out.")
            gaps.append((STATE, "race", rid, f"{c['title']}, {c['jname']}", "a candidate whose name cell could not be read",
                         "A name cell for this contest in the Election Commission's list held something other than a name, so that "
                         "candidate is left out until the list is corrected.", c["e"]["url"]))
        if not on:
            no_active += 1
            sts = sorted({r["Candidate Status"] for r in c["rows"]})
            note.append("Nobody the Election Commission's list names for this office is on the ballot: the list gives the status "
                        + and_list([f"\"{s}\"" for s in sts]) + ".")
        elif c["family"] == "school" and (c["jname"].endswith(" school boards") or c["jname"].startswith("School boards (")):
            note.append(SCHOOL_NOTE)
        elif c["kind"] not in ONE_SEAT and not (c["kind"] in ("county_commissioner", "council") and c["district"]):
            note.append(SEATS_NOTE)
        races.append([rid, STATE, c["level"], c["kind"], c["title"], c["jname"], c["jid"], json.dumps(cids), c["district"], c["seat"],
                      c["special"], c["partisan"], None, None, None, GENERAL, " ".join(note) or None])
        src = SRC_LOCAL if c["e"]["kind"] == "General" else SRC_OWN
        for rs in grouped.values():
            name, caps = shown(rs[0]["Name on Ballot"])
            cnote = [CAPS_NOTE] if caps else []
            if c["partisan"]:
                parties = [r["Party"] for r in rs]                        # more than one row: nominated by more than one party
                party = ", ".join(p for p in parties if p) or "No party given"
                code = "I" if parties[0] == "Petition" else party_code(parties[0])
                if len(parties) > 1:
                    cnote.append("Nominated by more than one party; the Election Commission's list has a row for each ("
                                 + ", then ".join(parties) + ").")
                if "Petition" in parties:
                    cnote.append(PETITION_NOTE)
                if any(re.search(r"Not Specified", p) for p in parties) or not parties[0]:
                    cnote.append(OTHER_PARTY_NOTE.format(parties[0] or "blank"))
            else:
                party, code = NONPARTISAN, "N"
            merged += len(rs) - 1
            placed_rows += len(rs)
            cands.append([rid, "general", GENERAL, name, party, code, None, 0, 0, None, None, None, None, src, " ".join(cnote) or None])
        if c["jtype"] != "county":
            place_reach[c["jid"]].update(cids)
            coded = bool(re.fullmatch(rf"{STATE}-M-\d{{5}}", c["jid"]))
            place_name.setdefault(c["jid"], (c["jtype"], c["jname"], SRC_PLACE if coded else src))

    # an office type a town's election offers with nobody under it: kept, with a note
    town_row = {spell(r["name"]): r for r in (muni or {}).get("rows", [])}
    empty_races = 0
    for e, otype, e_special in empties:
        town = muni_of.get(e["id"])
        if otype not in EMPTY_TYPES or not town:
            gaps.append((STATE, "race", "office-" + slug(f"{e['id']} {otype}"), f"{otype} ({e['name']})", "an office with no candidate listed",
                         "The Election Commission's candidate system shows this office for the election but lists no candidate under it, "
                         "and without one this loader cannot tell which board or seat it is.", e["url"]))
            continue
        kind, title, by = EMPTY_TYPES[otype]
        district = {"ward": "By ward", "district": "By district"}.get(by)
        seat = by if by == "At Large" else None
        jid = f"{STATE}-M-{town['code']}" if town["code"] else None
        if not jid:
            ckeys = sorted(county_key(x) for x in e["counties"])
            jid = f"{STATE}-M-{geoid[ckeys[0]][2:] + '-' if len(ckeys) == 1 else ''}{slug(town['name'])}"
        rid = rid_of(jid, title, district, seat, int(e_special))
        if rid in ids:
            raise LocalError(f"South Carolina (local races): an office with no candidate shares the race id {rid} with another contest")
        ids[rid] = None
        cids = sorted(geoid[county_key(x)] for x in e["counties"])
        siblings = {r[11] for r in races if r[6] == jid}
        listed_town = town_row.get(town["base"], {})
        partisan = siblings.pop() if len(siblings) == 1 else int(listed_town.get("partisan", False))
        note = [NO_CANDIDATE_NOTE]
        if district:
            note.append(f"The list shows the office for this election without naming a {by}.")
        if listed_town.get("own"):
            note.append(OWN_ELECTION_NOTE)
        if e_special:
            note.append(OWN_SPECIAL_NOTE)
        races.append([rid, STATE, "city", kind, title, town["name"], jid, json.dumps(cids), district, seat, int(e_special), partisan,
                      None, None, None, GENERAL, " ".join(note)])
        place_reach[jid].update(cids)
        place_name.setdefault(jid, ("mcd", town["name"], SRC_PLACE if town["code"] else SRC_OWN))
        empty_races += 1

    keys_ = [(c[0], c[3]) for c in cands]
    if len(keys_) != len(set(keys_)):
        raise LocalError("South Carolina (local races): two local candidate rows share a race and a name")
    senate_rows = sum(len(c["rows"]) for c in senate)
    off_rows = sum(status_left.values())
    if rows_read != senate_rows + left_rows + off_rows + placed_rows + names_dropped:
        raise LocalError(f"South Carolina (local races): {rows_read} rows read, but {senate_rows} for the State Senate, {placed_rows} placed, "
                         f"{off_rows} left off by status, {names_dropped} without a readable name and {left_rows} left out do not add to that")

    # 5. places: every jurisdiction the races use that is not a county
    place_rows = [(jtype, jid, name, json.dumps(sorted(place_reach[jid])), src) for jid, (jtype, name, src) in sorted(place_name.items())]

    # 6. the towns the Commission's table says vote in November of even years, against the general elections it lists
    n_muni = n_odd = n_even = n_nov = 0
    if muni:
        rows_m = muni["rows"]
        n_muni, n_odd, n_even = len(rows_m), sum(1 for r in rows_m if r["odd"]), sum(1 for r in rows_m if r["even"])
        have = {muni_of[e["id"]]["base"] for e in own if e["id"] in muni_of and not re.search(r"\bSpec(?:ial)?\b", e["name"], re.I)}
        for r in rows_m:
            if not (r["even"] and re.search(r"after 1st Mon\. in Nov", r["day"], re.I)):
                continue
            n_nov += 1
            base = spell(r["name"])
            if base in have:
                continue
            entry = places.get(base, [])
            label = entry[0][1] if len(entry) == 1 else r["name"].title()
            for cn in [x.strip() for x in r["county"].split(",") if x.strip()]:
                if county_key(cn) not in geoid:
                    continue
                gaps.append((STATE, "county", geoid[county_key(cn)], f"{cname[county_key(cn)]} County", f"{label} election, if one is due this year",
                             f"The State Election Commission's table of municipal elections says {label.rpartition(' ')[0] if len(entry) == 1 else label} "
                             "votes in November of even-numbered years, but neither its candidate system nor its 2026 election calendar lists "
                             "a November 3, 2026 election for it, so there is nothing to load; a town that elects all its officers every "
                             "four years may simply not be due this year.", MUNI_URL))

    # 7. the counts, the gaps of the whole state and the two notes
    local = [r for r in races if r[2] in LOCAL_LEVELS]
    by_level = collections.Counter(r[2] for r in local)
    by_kind = collections.Counter(r[3] for r in local)
    with_kind = collections.defaultdict(set)
    for r in local:
        with_kind[r[3]].update(json.loads(r[7]))
    school_counties = {g for r in local if r[2] == "school" for g in json.loads(r[7])}
    reached = {g for r in local for g in json.loads(r[7])}
    total = len(counties)
    lids = {r[0] for r in local}
    n_cands = sum(1 for c in cands if c[0] in lids)
    towns = {r[6] for r in local if r[2] == "city"}
    n_own_general = sum(1 for e in own if e["offered"] and not re.search(r"\bSpec(?:ial)?\b", e["name"], re.I) and not any(c["e"] is e for c in senate))
    n_own_special = sum(1 for e in own if e["offered"] and re.search(r"\bSpec(?:ial)?\b", e["name"], re.I) and not any(c["e"] is e for c in senate))
    other_general = sorted(k for k, v in cal_e.items() if v["type"] == "General" and v["date"] != GENERAL) if cal else []
    gaps.append((STATE, "state", STATE, NAME, "offices nobody filed for",
                 "The State Election Commission's list for the general election has a row for each candidate, so a county, school or "
                 "district office that drew no candidate does not appear in it; a county's own sample ballot is the place to check for one.",
                 statewide["url"]))
    cnt = lambda kind: len(with_kind[kind])
    county_of = {g: n for _k, (g, n) in counties.items()}
    np_council = sorted({county_of[r[6]] for r in local if r[3] == "county_commissioner" and not r[11]})
    party_school = sorted({county_of[g] for r in local if r[2] == "school" and r[11] for g in json.loads(r[7])})
    calendar = (
        "On November 3, 2026 South Carolina's general election ballot carries county council seats in "
        + (f"all {total}" if cnt("county_commissioner") == total else f"{cnt('county_commissioner')} of the {total}")
        + f" counties and, where the term ends this year, the probate judge ({cnt('probate_judge')} counties), auditor "
        f"({cnt('county_auditor')}), treasurer ({cnt('county_treasurer')}), sheriff ({cnt('sheriff')}), coroner ({cnt('coroner')}), clerk of "
        f"court ({cnt('clerk_of_court')}), register of deeds ({cnt('register_of_deeds')}) and county supervisor ({cnt('county_executive')}), "
        f"with {by_kind['solicitor']} of the sixteen circuit solicitors, all on party lines"
        + (f" except the council of {and_list(np_council)} County" if len(np_council) == 1 else
           f" except the councils of {and_list(np_council)} counties" if np_council else "")
        + f"; and soil and water district commissioners, school board seats reaching {len(school_counties)} counties"
        + (f" (on party lines in {and_list(party_school)} {'County' if len(party_school) == 1 else 'counties'} only)" if party_school else "")
        + " and watershed, fire, public service and public works districts, without parties. "
        + (f"Cities and towns set their own election day by ordinance (of {n_muni} municipalities {n_odd} vote in odd-numbered years and "
           f"{n_even} in even-numbered years, {n_nov} of those in November), and the Election Commission lists " if muni else
           "Cities and towns set their own election day by ordinance, and most vote in odd-numbered years; the Election Commission lists ")
        + f"{n_own_general} city, town and school district general elections and {n_own_special} local special elections as elections of "
          "their own on November 3"
        + (f", with {len(other_general)} more local general elections on other days of 2026" if cal else "")
        + ". State law sets the election of sheriffs, coroners and clerks of court for presidential years, next in 2028, and solicitors "
          "serve four years, so most counties and ten circuits do not elect them this year.")
    coverage = (
        f"Loaded from the State Election Commission's Candidate Tracking System as read on {day_words(lists['read'])}: every county, school "
        f"and district contest on its list for the November 3 statewide general election, and the {n_own_general + n_own_special} city, town "
        f"and school district elections it lists for the same day: {len(local):,} contests and {n_cands:,} candidates, with a local contest in "
        + (f"all {total} counties" if len(reached) == total else f"{len(reached)} of the {total} counties")
        + f". The list gives each candidate a status, and only those marked Active are shown; {off_rows:,} others, who lost a primary, "
          "withdrew or did not qualify, are left off. It gives no ballot order and never says how many seats a contest fills. It names a "
          "school board by its county and a district or seat number, so those contests are filed under the county in the list's own words "
          "and the school district is not named unless the list names it. Write-in candidates, local primaries and ballot questions "
        + (f"(the Commission lists {len(questions)} referendums that day) " if questions else "")
        + "are not loaded, and a city or town that runs its own election may not be on the Commission's list at all."
        + (f" {sum(1 for g in gaps if g[1] == 'race')} contests or offices could not be placed and are listed as gaps." if any(g[1] == "race" for g in gaps) else ""))
    notes = [(STATE, "local_calendar", calendar,
              "S.C. Code sections 7-13-10, 5-15-50, 23-11-10, 17-5-10, 14-17-10, 1-7-310, 14-5-610, 48-9-1220 and 48-11-100 (South Carolina "
              "Legislature); the State Election Commission's 2026 Election Calendar and its table of municipal elections; counts from the "
              "Commission's candidate lists", CODE_URL),
             (STATE, "local_coverage", coverage, "South Carolina State Election Commission, Candidate Tracking System: the statewide general "
              "election and the local elections of November 3, 2026", CTS_PAGE)]

    # 8. the last look: nothing that reads like contact details is stored, in the check's words or the page's
    for r in races:
        if any(v and contact_like(v, True) for v in (r[4], r[5], r[8], r[9], r[16])) or (r[16] and PAGE_STREET.search(r[16])):
            raise LocalError(f"South Carolina (local races): a stored cell of {r[0]} failed the contact-detail check (not shown)")
    for c in cands:
        if not local_name(c[3]) or contact_like(c[4], True) or (c[14] and (contact_like(c[14], True) or PAGE_STREET.search(c[14]))):
            raise LocalError(f"South Carolina (local races): a stored name, party or note in {c[0]} failed the contact-detail check (not shown)")
    for p in place_rows:
        if contact_like(p[2], True):
            raise LocalError(f"South Carolina (local races): the name of place {p[1]} failed the contact-detail check (not shown)")
    for g in gaps:
        if any(v and contact_like(v, False) for v in g[3:6]):
            raise LocalError(f"South Carolina (local races): a gap for {g[2]} failed the contact-detail check (not shown)")
    for nt in notes:
        if contact_like(nt[2], False) or contact_like(nt[3], False):
            raise LocalError(f"South Carolina (local races): the note {nt[1]} failed the contact-detail check (not shown)")

    own_read = [e for e in own if e["offered"] and not any(c["e"] is e for c in senate)]
    return dict(races=races, cands=cands, places=place_rows, gaps=gaps, notes=notes, checks=checks, senate=senate,
                local=len(local), local_cands=n_cands, by_level=dict(by_level), by_kind=dict(by_kind), reached=len(reached), counties=total,
                partisan=sum(1 for r in local if r[11]), rows_read=rows_read, senate_rows=senate_rows, placed_rows=placed_rows,
                merged=merged, off_rows=off_rows, status_left=dict(status_left), left_rows=left_rows, names_dropped=names_dropped,
                no_active=no_active, empty_races=empty_races, questions=[e["name"] for e in questions], towns=len(towns),
                towns_coded=sum(1 for j, (jt, _n, _s) in place_name.items() if jt == "mcd" and re.fullmatch(rf"{STATE}-M-\d{{5}}", j)),
                towns_all=sum(1 for _j, (jt, _n, _s) in place_name.items() if jt == "mcd"),
                own_elections=len(own_read), own_general=n_own_general, own_special=n_own_special,
                general_rows=sum(len(t["rows"]) for t in statewide["types"].values()),
                own_rows=sum(len(t["rows"]) for e in own_read for t in e["types"].values()),
                general_cands=sum(1 for c in cands if c[13] == SRC_LOCAL), own_cands=sum(1 for c in cands if c[13] == SRC_OWN),
                general_all=statewide["all"], own_digest=hashlib.sha256("\n".join(f"{e['id']} {e['all']['sha256']}" for e in sorted(own_read, key=lambda x: x["id"])).encode()).hexdigest(),
                new_kinds=sorted(set(by_kind) - KNOWN_KINDS), n_places=n_places, muni=dict(all=n_muni, odd=n_odd, even=n_even, nov=n_nov),
                other_general=len(other_general))


# ------------------------------------------------------------------------------------------------ loading

def load(db_path, say=print, folder=FOLDER, roster_db=ROSTER, county_zip=COUNTY_ZIP, local_folder=None):
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

    # 8b. the county and local part: every other November 3 contest the same system lists (nothing above is changed by it)
    local_folder = local_folder or os.path.join(folder, "local")
    os.makedirs(local_folder, exist_ok=True)
    _llpath, llists = local_lists(local_folder, say)
    ppath = os.path.join(local_folder, PLACE_FILE)
    net.download(PLACE_URL, ppath, max_age_days=3650, say=say)
    places, n_places = census_places(ppath)
    cal = election_calendar(local_folder, say)
    muni = municipal_table(local_folder, say)
    local = local_part(llists, counties, places, n_places, cal, muni, say)
    clash = sorted({f"2026-{STATE}-{k}" for k in list(STATEWIDE) + [f"SH{d}" for d in range(1, HOUSE_SEATS + 1)]} & {r[0] for r in local["races"]})
    if clash:
        raise SystemExit(f"South Carolina: a local race id is also a state race id ({clash[:3]})")

    # 8c. a State Senate seat with a special election of its own on November 3: stored with the Legislature, beside the
    # rows above. Who holds the seat is left empty (a seat filled by special election may be vacant, whatever the roster says).
    extra_races, extra_cands, extra_places, senate_said = [], [], [], []
    holding_now = {c[12] for c in cands if c[7] and c[12]}
    for sc in local["senate"]:
        d = sc["district"]
        rid = f"2026-{STATE}-SS{d}"
        if rid in races or any(r[0] == rid for r in extra_races):
            raise SystemExit(f"South Carolina (state races): two contests for State Senate District {d} on the November 3 lists")
        cids = sorted(counties[k][0] for k in sc["keys"])
        on = [r for r in sc["rows"] if r["Candidate Status"] in ON]
        unknown_s = sorted({r["Candidate Status"] for r in sc["rows"]} - KNOWN)
        if unknown_s:
            raise SystemExit(f"South Carolina (state races): statuses on the Senate special election's list the loader does not read: {unknown_s}")
        note = [SENATE_SPECIAL_NOTE] + ([] if on else [NONE_ON_LIST])
        extra_races.append((rid, STATE, "legislature", "state_senate", "State Senator", f"Senate District {d}", f"{STATE}-{d}", json.dumps(cids),
                            d, None, 1, int(sc["partisan"]), None, None, None, GENERAL, " ".join(note)))
        grouped_s = {}
        for r in on:
            if not r["Name on Ballot"]:
                checks.append(f"{rid}: a name cell on the special election's list could not be read as a name; that candidate is left out")
                continue
            grouped_s.setdefault(fold(r["Name on Ballot"]), []).append(r)
        for rs in grouped_s.values():
            name, caps = shown(rs[0]["Name on Ballot"])
            parties = [r["Party"] for r in rs]
            cnote = [CAPS_NOTE] if caps else []
            if len(parties) > 1:
                cnote.append(f"Nominated by more than one party; the Election Commission's list has a row for each ({', then '.join(parties)}).")
            if "Petition" in parties:
                cnote.append(PETITION_NOTE)
            pool = [p for p in people if p["id"] not in holding_now and (p["party"] or "") == parties[0] and person_fits(name, p)]
            mid = pool[0]["id"] if len(pool) == 1 else None
            if mid:
                cnote.append(f"Serves today {where(pool[0])}.")
            elif len(pool) > 1:
                checks.append(f"{rid}: {name} fits {len(pool)} sitting members of the same party; none is taken")
            extra_cands.append((rid, "general", GENERAL, name, ", ".join(p for p in parties if p) or None,
                                "I" if parties[0] == "Petition" else party_code(parties[0]), None, 0, 0, None, None, None, mid, SRC_SENATE,
                                " ".join(cnote) or None))
        extra_places.append(("senate", f"{STATE}-{d}", f"Senate District {d}", json.dumps(cids), SRC_SENATE))
        senate_said.append(f"State Senate District {d} ({sc['e']['name']}): {len(grouped_s)} candidates on the list, "
                           f"{len(sc['rows']) - len(on)} rows with other statuses left off")
    for row in extra_races:
        if CONTACT_NOTE.search(row[16]) or PAGE_STREET.search(row[16]):
            raise SystemExit(f"South Carolina (state races): the note for {row[0]} failed the contact-detail check (not shown)")
    for c in extra_cands:
        if CONTACT.search(c[3]) or CONTACT.search(c[4] or "") or (c[14] and CONTACT_NOTE.search(c[14])):
            raise SystemExit(f"South Carolina (state races): a stored cell for {c[0]} failed the contact-detail check (not shown)")

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
    # the local part's sources, after the state part's own (no address or site name in a note: the address has its own column)
    ga, L = local["general_all"], local
    statewide_e = next(e for e in llists["elections"] if e["kind"] == "General")
    left_words = "; ".join(f"{k}: {v}" for k, v in sorted(L["status_left"].items())) or "none"
    sources += [
        (SRC_LOCAL, STATE, "official candidate list", AGENCY,
         "Candidate Tracking System: 11/3/2026 Statewide General Election, county, school and district offices", statewide_e["url"], "",
         llists["read"], ga["sha256"], L["general_rows"],
         "Read through the page's own search twice: once for every office at once and once for each of the "
         f"{len(statewide_e['types'])} county, school and district office types the election offers; the two routes hold the same rows. "
         f"The SHA-256 is of the whole answer as fetched ({ga['bytes']:,} bytes, {ga['rows']:,} rows: {ga['state_and_federal_rows']:,} state "
         f"and federal rows read elsewhere, {L['general_rows']:,} read here); each office type's answer has its own SHA-256 beside the kept "
         "cells. Columns taken by heading; kept: Office, Associated Counties, Name on Ballot, Party, Candidate Status. Running Mate and "
         "Location of Filing are never kept; the table has no contact columns, and the detail pages that do are never asked for, nor the "
         f"export. Status Active is on the November ballot: {L['general_cands']:,} candidates from this list. The list gives no ballot "
         "positions, no number of seats and no write-in candidates, and names a school board by county and number only."),
        (SRC_OWN, STATE, "official candidate list", AGENCY,
         f"Candidate Tracking System: the {L['own_elections']} city, town and school district elections listed as elections of their own on "
         "November 3, 2026", CTS_PAGE, "", llists["read"], L["own_digest"], L["own_rows"],
         f"Each of the {L['own_elections']} elections ({L['own_general']} general, {L['own_special']} special) is chosen on the page and read "
         "the same two ways, the same five cells kept; the two routes hold the same rows for every one. The SHA-256 here is of the list of "
         "election numbers with each whole answer's own SHA-256, in number order; the answers' fingerprints are kept beside the kept cells. "
         f"{L['own_cands']:,} candidates marked Active come from these lists. A city or town is the one incorporated place the election's "
         f"name names among the places of its counties ({L['towns_coded']} of {L['towns_all']} matched to a Census place code). "
         + (f"The Commission also lists {len(L['questions'])} elections that day with no office ({', '.join(L['questions'])}): questions put "
            "to the voters, which are not loaded." if L["questions"] else "")),
        (SRC_PLACE, STATE, "official place codes", "U.S. Census Bureau", "2020 place codes, South Carolina (st45_sc_place2020.txt)", PLACE_URL,
         "2020", mtime(ppath), sha(ppath), n_places,
         f"Names and five-digit place codes of South Carolina's {n_places} incorporated cities and towns, with the counties each lies in. "
         "Used to name each city or town as the Bureau writes it; the file holds no personal details."),
    ]
    if local["senate"]:
        se = [sc["e"] for sc in local["senate"]]
        sources.append((SRC_SENATE, STATE, "official candidate list", AGENCY,
                        "Candidate Tracking System: " + "; ".join(e["display"] for e in se), se[0]["url"], "", llists["read"],
                        se[0]["all"]["sha256"], sum(len(sc["rows"]) for sc in local["senate"]),
                        "A special election for a State Senate seat, listed as an election of its own and read the same two ways as the "
                        "local elections; the same five cells kept. Status Active is on the November ballot. The SHA-256 is of the whole "
                        "answer as fetched. The primary that chose the nominees is not read."))
    if cal:
        sources.append((SRC_CALENDAR, STATE, "official calendar", AGENCY, "2026 Election Calendar (report RP0110)", CALENDAR_URL, cal["dated"],
                        mtime(cal["path"]), sha(cal["path"]), cal["lines"],
                        f"A PDF with a text layer: {cal['lines']} lines, one for each election in each county that holds it (date, election "
                        f"number, county, name, kind and filing period), {len(cal['elections'])} elections in 2026. Read to check that the "
                        "Candidate Tracking System and the calendar list the same November 3 elections, and for the count of local general "
                        "elections on other days. It names no candidate."))
    if muni:
        sources.append((SRC_MUNI, STATE, "official list", AGENCY, "Municipal Elections (table of every city's and town's election day)",
                        MUNI_URL, "2026-05-12", mtime(muni["path"]), sha(muni["path"]), len(muni["rows"]),
                        "One row a city or town. Columns read: County, Municipality, Odd Year Election, Even Year Election, Election Day, "
                        "Who Does Work of Conducting Election? and Partisan or Non-Partisan?. Used for the counts of towns voting in odd and "
                        "even years, for whether an office with no candidate listed is on the ballot with parties and whether the town "
                        "conducts its own election, and to name the towns it says vote in November of even years that have no November 3, "
                        "2026 election on the Commission's lists. It names no candidate and holds no personal details."))

    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA + EXTRA_SCHEMA)
    with con:
        con.execute("DELETE FROM sl_candidates WHERE race_id IN (SELECT race_id FROM sl_races WHERE state = ?) OR race_id LIKE ?",
                    (STATE, f"2026-{STATE}-%"))
        con.execute("DELETE FROM sl_races WHERE state = ?", (STATE,))
        con.execute("DELETE FROM sl_sources WHERE state = ?", (STATE,))
        con.execute("DELETE FROM sl_places WHERE source_id LIKE ? OR (kind = 'county' AND id LIKE ?) OR id LIKE ?",
                    (f"{STATE.lower()}-%", f"{FIPS}___", f"{STATE}-%"))
        con.execute("DELETE FROM sl_gaps WHERE state = ?", (STATE,))
        con.execute("DELETE FROM sl_notes WHERE state = ?", (STATE,))
        con.executemany("INSERT INTO sl_races VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", race_rows + extra_races + [tuple(r) for r in local["races"]])
        con.executemany("INSERT INTO sl_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        [tuple(c) for c in cands] + extra_cands + [tuple(c) for c in local["cands"]])
        con.executemany("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", sources)
        con.executemany("INSERT INTO sl_places VALUES (?,?,?,?,?)", place_rows + extra_places + local["places"])
        con.executemany("INSERT INTO sl_gaps VALUES (?,?,?,?,?,?,?)", local["gaps"])
        con.executemany("INSERT INTO sl_notes VALUES (?,?,?,?,?)", local["notes"])
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
    for line in senate_said:
        say(f"      also on the November 3 ballot, a special election of its own: {line}")
    for c in extra_cands:
        if c[12]:
            say(f"      matched: {c[0]} general: {c[3]} -> {c[12]}")
    lv = L["by_level"]
    say(f"    South Carolina county and local offices: {L['local']:,} races ("
        + ", ".join(f"{k.replace('_', ' ')} {lv[k]:,}" for k in LOCAL_LEVELS if lv.get(k)) + f"), {L['local_cands']:,} candidates, a local "
        f"contest in {L['reached']} of {L['counties']} counties; {L['partisan']:,} partisan and {L['local'] - L['partisan']:,} nonpartisan")
    say(f"      rows read: {L['rows_read']:,} ({L['general_rows']:,} of the statewide general election's local offices, {L['own_rows']:,} of "
        f"{L['own_elections']} elections of their own, {L['senate_rows']} of a State Senate special election), by two routes that agree; "
        f"{L['placed_rows']:,} placed, each in exactly one race ({L['local_cands']:,} candidates), {L['off_rows']:,} left off by status "
        f"({left_words}), {L['names_dropped']} without a readable name, {L['left_rows']} left out with their contests")
    say(f"      {L['no_active']} contests whose listed names are all off the ballot and {L['empty_races']} town offices with no candidate "
        f"listed are kept with a note; cities and towns matched to a Census place code: {L['towns_coded']} of {L['towns_all']}; office kinds: "
        + ", ".join(f"{k} {v:,}" for k, v in sorted(L["by_kind"].items())))
    if L["new_kinds"]:
        say(f"      office kinds the pages do not know yet: {', '.join(L['new_kinds'])}")
    for g in L["gaps"]:
        say(f"      gap ({g[1]}): {g[3]}: {g[4]}")
    for line in checks + L["checks"]:
        say(f"      check: {line}")
    return dict(races=len(races), general=len(gen), primary=len(prim), fields=fields, runoffs=nrunoffs, checks=checks + L["checks"],
                senate_special=len(extra_races), senate_special_candidates=len(extra_cands),
                local={k: v for k, v in L.items() if k not in ("races", "cands", "places", "gaps", "notes", "checks", "senate", "general_all")},
                local_gaps=[g[:5] for g in L["gaps"]])


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="South Carolina's state races on the November 3, 2026 ballot")
    ap.add_argument("db", help="the state-and-local ballot database to write South Carolina's rows into")
    a = ap.parse_args()
    load(a.db)
