"""
ballot/state_local_vt.py - Vermont's state races on the November 3, 2026 ballot: the six statewide offices (Governor,
Lieutenant Governor, State Treasurer, Secretary of State, Auditor of Accounts and Attorney General, each elected on its
own for two years) and every seat of the General Assembly (all 30 senators from 16 senate districts and all 150
representatives from 109 house districts, all with two-year terms, so the whole Legislature is on every November
ballot), with each party's August 11 primary field and its official votes.

Sources, all the Secretary of State's (Elections Division), the same files the federal loader reads (ballot/lists/vt.py):
  - "2026 General Election Candidate Listing/Financial Disclosure" (candidates/2026_general_election_qualified_candidates
    .xlsx, the Candidates page): one row per qualified candidate for every office on the ballot. Columns are taken by
    name, and only Contest, District Name, Name On Ballot, Party and Vote for Count are ever read. Districts are written
    in the Secretary's codes (ADD 1, CHI SE 1, WDR ORA 1); each is turned into the Legislature's own district name
    (Addison, Chittenden Southeast, Windsor-Orange-1) through the county abbreviations below, and must name exactly one
    district of the Open States roster, with the same number of seats. The list gives no ballot positions; Vermont
    prints each office's candidates in alphabetical order by surname (17 V.S.A. 2472(b)(2)), which is the list's own
    order: the loader checks it and stores it as the ballot order.
  - "2026 Primary Election Candidate Listing/Financial Disclosure" (2026_statewide_primary_qualified_candidates.xlsx):
    who was printed on each party's primary ballot (DEMOCRATIC, PROGRESSIVE and REPUBLICAN sheets, the same five
    columns) and the REGISTERED WRITE-IN sheet (office, the two district columns and the three name columns only).
  - The Secretary's official results for the August 11 primary, "2026 August Primary Election Results" on
    electionresults.vermont.gov (marked official), read from the files that site's own page fetches from
    static.electionresults.vermont.gov: the election list, the election's index, and its statewide, senate and house
    files. Every town's candidates, write-ins, blank votes and spoiled ballots add up to its total, and the towns add up
    to the district-wide (or statewide) row, which is the one kept. The results carry write-in names as the towns
    reported them; a write-in name is kept only when it won the nomination (the results then list it among the
    candidates) or fits a registered write-in candidate for that office and district and was recorded in one party's
    primary only (the registration names no party). Every other write-in name is added into one figure at once and is
    never cached, printed or stored.
  - Controls: the "2026 August Primary Winner Listing" (xlsx: Winner, Name on Ballot, Party, Office Name, District,
    Votes and Percent(%) only) must give every candidate the same votes and winner mark as the results, and the
    canvassing committee's report that opens the "2026 August Primary Official Canvass - Town by Town" (PDF, results
    only, kept by the federal loader) must give the statewide offices the same figures.
Holders come from the Open States roster in state_vt.sqlite (legislators with is_current = 1 by chamber and district;
the officials table for Governor, Lieutenant Governor, Secretary of State and Attorney General). The roster does not
carry the Treasurer or the Auditor, and the list names no incumbents, so those two races carry no holder.
Which counties each district reaches comes from the results' own town table, named by the Census Bureau's county file.

Privacy: the candidate workbooks also carry town of residence, mailing address, city, state, ZIP, phones, e-mail, website
and financial disclosure, and the winner listing carries addresses and a phone. Workbooks are read in memory and never
saved; the header row is found by its first cell, columns are taken by name from it, and only the columns named above
are read. What is cached (ballot_cache/vt/vt_2026_sl_*.json) is those columns of the state-office rows, the results'
kept figures and each file's SHA-256. Nothing is printed while loading but counts, race ids, and the names of candidates
(a match to a sitting member, or a check that needs reading); never a write-in name that is not shown.

A primary is a field when more candidates were on the party's primary than it nominates (two or more for one seat).
A field's total is its candidates' votes plus every write-in vote (blank votes and spoiled ballots left out), as on the
federal page; the Secretary's winner listing prints percentages of all votes counted, blanks included, so the two differ.

    python -m ballot.state_local_vt <path to a test database>
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

import openpyxl

from ballot.common import CACHE, HERE, fold, name_parts, party_code
from ballot.match import fits
from ballot.pdftext import PDF, page_runs
from states import net
from states.places import place

STATE, FIPS = "VT", "50"
GENERAL, PRIMARY = "2026-11-03", "2026-08-11"
CANDIDATES_PAGE = "https://sos.vermont.gov/elections/election-info-resources/candidates/"
RESULTS_PAGE = "https://sos.vermont.gov/elections/election-info-resources/elections-results-data/"
FILES = "https://outside.vermont.gov/dept/sos/Elections_Division/election_info_resources/"
GENERAL_XLSX = FILES + "candidates/2026_general_election_qualified_candidates.xlsx"
PRIMARY_XLSX = FILES + "candidates/2026_statewide_primary_qualified_candidates.xlsx"
WINNERS_XLSX = FILES + "elections_results_data/2026-august-primary-winner-listing.xlsx"
CANVASS_PDF = FILES + "elections_results_data/2026-august-primary-official-canvass-town-by-town.pdf"
ENR_SITE = "https://electionresults.vermont.gov/"
ENR_STATIC = "https://static.electionresults.vermont.gov/"
ENR_LIST = ENR_STATIC + "elections/elections.json"
COUNTY_ZIP = os.path.join(HERE, "states_cache", "census", "cb_2024_us_county_500k.zip")
ROSTER = os.path.join(HERE, "state_vt.sqlite")

SRC_GEN, SRC_PRI, SRC_ENR = "vt-sos-2026-state-general-list", "vt-sos-2026-state-primary-list", "vt-sos-2026-state-primary-results"
SRC_WIN, SRC_CANVASS = "vt-sos-2026-state-primary-winners", "vt-sos-2026-state-primary-canvass"
SRC_ROSTER, SRC_COUNTY = "vt-openstates-roster", "vt-census-2024-county-codes"

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

# The Secretary's contest names: (race suffix, office_kind, office as shown, roster office).
STATEWIDE = {
    "GOVERNOR": ("GOV", "governor", "Governor", "governor"),
    "LIEUTENANT GOVERNOR": ("LTG", "lieutenant_governor", "Lieutenant Governor", "lt_governor"),
    "STATE TREASURER": ("TREAS", "state_treasurer", "State Treasurer", None),
    "SECRETARY OF STATE": ("SOS", "secretary_of_state", "Secretary of State", "secretary of state"),
    "AUDITOR OF ACCOUNTS": ("AUD", "state_auditor", "Auditor of Accounts", None),
    "ATTORNEY GENERAL": ("AG", "attorney_general", "Attorney General", "attorney general"),
}
SENATE, HOUSE = "STATE SENATOR", "STATE REPRESENTATIVE"
LEGISLATURE = {SENATE: ("SS", "state_senate", "State Senator", "Senate"), HOUSE: ("SH", "state_house", "State Representative", "House")}
FEDERAL = ("REPRESENTATIVE TO CONGRESS",)
NOT_LOADED = ("PROBATE JUDGE", "ASSISTANT JUDGE", "STATE'S ATTORNEY", "SHERIFF", "HIGH BAILIFF", "JUSTICE OF THE PEACE")
WRITE_OFFICE = {"GOVERNOR": "GOVERNOR", "LIEUTENANT GOVERNOR": "LIEUTENANT GOVERNOR", "STATE TREASURER": "STATE TREASURER",
                "SECRETARY OF STATE": "SECRETARY OF STATE", "AUDITOR OF ACCOUNTS": "AUDITOR OF ACCOUNTS", "ATTORNEY GENERAL": "ATTORNEY GENERAL",
                "STATE SENATE": SENATE, "STATE SENATOR": SENATE, "STATE REPRESENTATIVE": HOUSE}

KEEP = ("Contest", "District Name", "Name On Ballot", "Party", "Vote for Count")
WRITE_KEEP = ("OFFICE", "SENATE DISTRICT", "REPRESENTATIVE (HOUSE) DISTRICT", "FIRST NAME", "MIDDLE NAME", "LAST NAME")
WIN_KEEP = ("Winner", "Name on Ballot", "Party", "Office Name", "District", "Votes", "Percent(%)")
PARTY_SHEETS = ("DEMOCRATIC", "PROGRESSIVE", "REPUBLICAN")
CODE = {"DEMOCRATIC": "DEM", "REPUBLICAN": "REP", "PROGRESSIVE": "PRO"}          # primary-DEM, primary-REP, primary-PRO, as the federal loader
SHORT = {"DEM": "Democratic", "REP": "Republican", "PROG": "Progressive"}          # the list's short forms in joint nominations
PARTY_CODE = {"Democratic": "DEM", "Republican": "REP", "Progressive": "PRO"}      # a party as written out -> its primary's code
COUNT = {"ONE": 1, "TWO": 2, "THREE": 3}

# The Secretary's county abbreviations in district codes, and the words after a senate district's county.
COUNTY_ABBR = {"ADD": "Addison", "BEN": "Bennington", "CAL": "Caledonia", "CHI": "Chittenden", "ESX": "Essex", "FRA": "Franklin",
               "GI": "Grand Isle", "LAM": "Lamoille", "ORA": "Orange", "ORL": "Orleans", "RUT": "Rutland", "WAS": "Washington",
               "WDH": "Windham", "WDR": "Windsor"}
SENATE_PART = {"CT": "Central", "N": "North", "SE": "Southeast"}
LABEL = {"WRITE-IN": "Write-In", "OVERVOTES": "Overvotes", "BLANK VOTES": "Blank votes", "TOTAL VOTES COUNTED": "Total"}
NUMBER = re.compile(r"\d{1,3}(?:,\d{3})+|\d+")

CAPS = "Vermont's list prints names in capitals; they are shown here in ordinary capitals."
WRITE_WON = "Write-in candidate: the name was not printed on this party's primary ballot; the write-in votes won the nomination."
WRITE_WON_REG = ("Registered write-in candidate: the name was not printed on this party's primary ballot; the write-in votes won the "
                 "nomination.")
WRITE_REG = "Registered write-in candidate: the name was not printed on the primary ballot."
WRITE_NOV = "Registered write-in candidate: the name is not printed on the November ballot."


def squash(value):
    return re.sub(r"\s+", " ", str(value if value is not None else "").replace("\xa0", " ")).strip()


def dkey(text):
    """A district's spelling for comparison only: letters and digits, lower case, nothing else."""
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def today():
    return dt.date.today().isoformat()


# ------------------------------------------------------------------------------------------------ the workbooks

def book(url):
    """A workbook of the Secretary's, read in memory (it carries contact columns, so it is never saved), with its
    fingerprint."""
    raw = net.get(url)
    if raw[:2] != b"PK":
        raise SystemExit(f"Vermont: {url} is not a workbook")
    return openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True), sha(raw)


def sheet_rows(ws, keep, first):
    """The rows under a sheet's header row (the first row whose first cell is `first`): the kept columns only, by name.
    No other cell of a row is ever read."""
    rows = ws.iter_rows(values_only=True)
    for r in rows:
        if r and squash(r[0]) == first:
            head = [squash(h) for h in r]
            break
    else:
        raise SystemExit(f"Vermont: no header row beginning {first!r} on the sheet {ws.title!r}")
    missing = [k for k in keep if k not in head]
    if missing:
        raise SystemExit(f"Vermont: the sheet {ws.title!r} no longer has the columns {missing}")
    idx = {k: head.index(k) for k in keep}
    out = []
    for r in rows:
        row = {k: squash(r[i]) if i < len(r) else "" for k, i in idx.items()}
        if any(row.values()):
            out.append(row)
    return out


def updated(wb, sheet):
    """The "Last Updated: M/D/YYYY" line of a workbook's criteria sheet as YYYY-MM-DD; nothing else on it is kept."""
    if sheet not in wb.sheetnames:
        return ""
    for r in wb[sheet].iter_rows(values_only=True):
        for c in r:
            m = re.fullmatch(r"Last Updated:\s*(\d{1,2})/(\d{1,2})/(\d{4})", squash(c))
            if m:
                return f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
    return ""


def filled(rows):
    """A contest is named once, on its first row; the rows below it carry it on."""
    contest = ""
    for r in rows:
        contest = r["Contest"] = r["Contest"] or contest
    return rows


def known(contest, where):
    c = contest.upper()
    if c in STATEWIDE or c in LEGISLATURE or c in NOT_LOADED or c.replace("U.S. ", "") in FEDERAL:
        return c in STATEWIDE or c in LEGISLATURE
    raise SystemExit(f"Vermont: an office this loader does not know is on the {where}: {contest!r}")


def write_in_rows(wb, where):
    """State-office rows of the registered write-in sheets: office, the two district columns, the three name columns."""
    out = []
    for name in wb.sheetnames:
        if "WRITE-IN" in name.upper():
            for r in sheet_rows(wb[name], WRITE_KEEP, "OFFICE"):
                office = r["OFFICE"].upper().replace("U.S. ", "")
                if office in FEDERAL or office in NOT_LOADED:
                    continue
                if office not in WRITE_OFFICE:
                    raise SystemExit(f"Vermont: a registered write-in for an office this loader does not know on the {where}: {office!r}")
                out.append(r)
    return out


def kept(path, max_age_days, fetch):
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < max_age_days * 86400:
        return json.load(open(path, encoding="utf-8"))
    data = fetch()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(data, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return data


def general_list():
    wb, digest = book(GENERAL_XLSX)
    sheet = "Candidate Listing"
    if sheet not in wb.sheetnames:
        raise SystemExit(f"Vermont: the general list has no {sheet!r} sheet ({wb.sheetnames})")
    for s in wb.sheetnames:
        if s not in (sheet, "Selection Criteria") and "WRITE-IN" not in s.upper():
            raise SystemExit(f"Vermont: the general list has a sheet that is not read ({s!r})")
    rows = filled(sheet_rows(wb[sheet], KEEP, "Contest"))
    others = Counter(r["Contest"] for r in rows if not known(r["Contest"], "general list"))
    return {"url": GENERAL_XLSX, "sha256": digest, "fetched": today(), "updated": updated(wb, "Selection Criteria"),
            "rows_read": len(rows), "state": [r for r in rows if known(r["Contest"], "general list")], "others": dict(others),
            "write_in": write_in_rows(wb, "general list")}


def primary_list():
    wb, digest = book(PRIMARY_XLSX)
    parties = {}
    for sheet in wb.sheetnames:
        if sheet.upper() in PARTY_SHEETS:
            rows = filled(sheet_rows(wb[sheet], KEEP, "Contest"))
            parties[sheet.upper()] = [r for r in rows if known(r["Contest"], f"primary list ({sheet})")]
        elif "WRITE-IN" not in sheet.upper() and sheet != "Last Updated":
            raise SystemExit(f"Vermont: the primary list has a sheet that is not read ({sheet!r})")
    if set(parties) != set(PARTY_SHEETS):
        raise SystemExit(f"Vermont: the primary list's party sheets changed ({sorted(parties)})")
    return {"url": PRIMARY_XLSX, "sha256": digest, "fetched": today(), "updated": updated(wb, "Last Updated"), "parties": parties,
            "write_in": write_in_rows(wb, "primary list")}


def winner_listing():
    wb, digest = book(WINNERS_XLSX)
    rows = sheet_rows(wb["Winner Listing"], WIN_KEEP, "Winner")
    crit = {}
    if "Selection Criteria" in wb.sheetnames:
        for r in wb["Selection Criteria"].iter_rows(values_only=True):
            cells = [squash(c) for c in r if c is not None]
            if len(cells) == 2 and cells[0].endswith(":"):
                crit[cells[0].rstrip(":")] = cells[1]
    state = [r for r in rows if known(r["Office Name"], "winner listing")]
    return {"url": WINNERS_XLSX, "sha256": digest, "fetched": today(), "criteria": crit, "rows": state}


# ---------------------------------------------------------------------------------------- the official results

def enr_results(registered):
    """The August 11 primary from the Secretary's results site: for every party, office and district, the district-wide
    (statewide) figures, after every town has been added up and checked. `registered` is [(office, district key or '',
    (given, family))] for the registered write-in candidates: only their write-in names, and write-ins that won, are
    kept; every other write-in name is added into `other_write_in` here and goes no further."""
    elections = json.loads(net.get(ENR_LIST))
    mine = [e for e in elections if str(e.get("electionDate", "")).startswith(PRIMARY) and e.get("isStateWideElection")
            and e.get("electionTypeCode") == "P"]
    if len(mine) != 1:
        raise SystemExit(f"Vermont: the results site lists {len(mine)} statewide primaries on {PRIMARY}")
    guid = mine[0]["electionGuid"]
    index_raw = net.get(f"{ENR_STATIC}elections/{guid}.json")
    index = json.loads(index_raw)
    det = index["electionDetails"]
    if not det.get("isOfficial") or det.get("electionName") != "AUGUST PRIMARY":
        raise SystemExit(f"Vermont: the results site's {PRIMARY} primary is not marked official ({det.get('electionName')!r})")
    files = {"index": {"url": f"{ENR_STATIC}elections/{guid}.json", "sha256": sha(index_raw)}}
    contests, problems, won_in = [], [], defaultdict(set)
    for part in ("stateWide", "senate", "house"):
        url = ENR_STATIC + index[part]["path"].replace("\\", "/")
        raw = net.get(url)
        files[part] = {"url": url, "sha256": sha(raw)}
        for p in json.loads(raw)["d"]:
            pn = p["pn"]
            if pn not in PARTY_SHEETS:
                raise SystemExit(f"Vermont: the results carry a party that is not read ({pn!r})")
            for o in p["o"]:
                on, dc = squash(o["on"]), squash(o.get("dc") or "")
                if on not in STATEWIDE and on not in LEGISLATURE:
                    raise SystemExit(f"Vermont: the {part} results carry an office that is not read ({on!r})")
                where = f"{pn} {on} {dc}".strip()
                wide = [c for c in o["cs"] if c["tid"] == 0]
                towns = [c for c in o["cs"] if c["tid"] != 0]
                if len(wide) != 1 or not towns:
                    raise SystemExit(f"Vermont: {where}: {len(wide)} district-wide rows and {len(towns)} town rows")
                w = wide[0]

                def total(c):
                    return sum(x["vc"] for x in c["rc"]) + sum(x["vc"] for x in c["wc"]) + c["bv"] + c["sv"]
                for c in o["cs"]:
                    if total(c) != c["sc"]:
                        problems.append(f"{where}: a row's candidates, write-ins, blanks and spoiled ballots do not add up to its total")
                for k in ("sc", "bv", "sv"):
                    if sum(c[k] for c in towns) != w[k]:
                        problems.append(f"{where}: the towns do not add up to the district-wide {k}")
                summed, wideset = Counter(), Counter()
                for c in towns:
                    for x in c["rc"] + c["wc"]:
                        summed[(x["cid"], squash(x["cn"]))] += x["vc"]
                for x in w["rc"] + w["wc"]:
                    wideset[(x["cid"], squash(x["cn"]))] += x["vc"]
                if +summed != +wideset:
                    problems.append(f"{where}: the towns' candidate and write-in votes do not add up to the district-wide row")
                printed = [[squash(x["cn"]), x["vc"], bool(x["isWinner"]), bool(x["isWriteIn"])] for x in w["rc"]]
                reg = [(g, f) for off, dk, (g, f) in registered if off == on and (on in STATEWIDE or dk == dkey(dc))]
                for x in w["rc"]:                                            # a registered write-in who won this party's nomination
                    hit = [i for i, (g, f) in enumerate(reg) if fits(name_parts(squash(x["cn"])), (g, f)) and name_parts(squash(x["cn"]))[1] == f]
                    if x["isWriteIn"] and len(hit) == 1:
                        won_in[(on, dc, hit[0])].add(pn)
                writes, other = defaultdict(lambda: [0, 0, False]), 0
                for x in w["wc"]:
                    name = squash(x["cn"])
                    hit = [i for i, (g, f) in enumerate(reg) if x["cid"] and fits(name_parts(name), (g, f)) and name_parts(name)[1] == f]
                    if x["isWinner"] or len(hit) == 1:
                        k = hit[0] if len(hit) == 1 else name
                        writes[k][0] += x["vc"]
                        writes[k][1] += 1
                        writes[k][2] = writes[k][2] or bool(x["isWinner"])
                    else:
                        other += x["vc"]
                kept_w = [[i if isinstance(i, int) else None, (squash(i) if isinstance(i, str) else None), v, n, won]
                          for i, (v, n, won) in writes.items()]
                contests.append({"party": pn, "office": on, "dc": dc, "vf": o["vf"], "towns": len(towns), "total": w["sc"], "blank": w["bv"],
                                 "spoiled": w["sv"], "printed": printed, "write_ins": kept_w, "other_write_in": other,
                                 "write_in_all": sum(x["vc"] for x in w["wc"])})
    if problems:
        raise SystemExit("Vermont: the official results do not reconcile:\n  " + "\n  ".join(problems[:20]))
    # The registration names no party: a registered write-in recorded in two parties' primaries is named in neither.
    parties_of = defaultdict(set, {k: set(v) for k, v in won_in.items()})
    for c in contests:
        for w in c["write_ins"]:
            if w[0] is not None:
                parties_of[(c["office"], c["dc"], w[0])].add(c["party"])
    two = {k for k, v in parties_of.items() if len(v) > 1}
    for c in contests:
        keep = []
        for w in c["write_ins"]:
            if w[0] is not None and (c["office"], c["dc"], w[0]) in two and not w[4]:
                c["other_write_in"] += w[2]
            else:
                keep.append(w)
        c["write_ins"] = keep
    counties = defaultdict(set)
    for t in index["townDistricts"]:
        counties[("house", squash(t["repDistrictCode"]))].add(squash(t["countyName"]))
        counties[("senate", squash(t["senDistrictCode"]))].add(squash(t["countyName"]))
    return {"guid": guid, "election": det["electionDateWithName"], "official": det["isOfficial"], "updated": index.get("lastUpdatedDate", ""),
            "towns_reporting": index.get("townsReporting", ""), "fetched": today(), "files": files, "contests": contests,
            "registered_in_two_parties": len(two),
            "counties": {f"{k[0]}|{k[1]}": sorted(v) for k, v in counties.items()}}


def committee_report(path):
    """The canvassing committee's figures for the statewide offices: {office: {party: {label: votes}}} and the starred
    winners {(office, party, label)}. Only the report's pages are read (they come before the town tabulation)."""
    raw = open(path, "rb").read()
    if raw[:5] != b"%PDF-":
        raise SystemExit("Vermont: the canvass is not a PDF")
    pdf = PDF(raw)
    out, stars, office, party, attested = {}, set(), None, None, False
    for n, (page, res) in enumerate(pdf.pages(), start=1):
        runs = page_runs(pdf, page, res)
        if any(re.fullmatch(r"Page \d+ of \d+", r[3].strip()) for r in runs):
            break                                                            # the town-by-town tabulation begins
        text = " ".join(r[3] for r in runs)
        attested = attested or ("17 V.S.A. 2368-2371" in text and "08/11/2026 - AUGUST PRIMARY" in text)
        # The report is printed turned on its side: each column is one printed line, x fixed, read along y. A long name runs
        # on in a second piece on the same line (H. / BROOKE PAIGE), and the winner's star follows the name's end.
        events = [(r[0], "office", r[3].strip()) for r in runs if 115 <= r[1] <= 125 and r[3].strip().startswith("FOR ")]
        for r in runs:
            if 165 <= r[1] <= 175:
                more = [s for s in runs if abs(s[0] - r[0]) <= 1 and 175 < s[1] < 410 and s[3].strip() not in ("*", "")]
                events.append((r[0], "column", " ".join(s[3].strip() for s in sorted([r] + more, key=lambda s: s[1]))))
        for x, kind, label in sorted(events):
            if kind == "office":
                office, party = label[4:], None
                continue
            if office not in STATEWIDE:
                continue
            if label.endswith(" PARTY"):
                party = label[:-6]
                out.setdefault(office, {}).setdefault(party, {})
                continue
            vals = [NUMBER.fullmatch(r[3].strip()) for r in runs if 415 <= r[1] <= 425 and abs(r[0] - x) <= 3]
            vals = [int(m.group(0).replace(",", "")) for m in vals if m]
            if party is None or len(vals) != 1:
                raise SystemExit(f"Vermont: canvass page {n}: the committee's column {label!r} is not read")
            out[office][party][LABEL.get(label, label)] = vals[0]
            if any(r[3].strip() == "*" and 175 < r[1] < 410 and abs(r[0] - x) <= 3 for r in runs):
                stars.add((office, party, LABEL.get(label, label)))
    if not attested:
        raise SystemExit("Vermont: the canvass does not open with the canvassing committee's report of the August 11 primary")
    return out, stars


# ------------------------------------------------------------------------------------------------- districts

def district_name(code, chamber):
    """The Secretary's district code as the Legislature names the district: ADD 1 -> Addison (Senate) or Addison-1
    (House); CHI SE 1 -> Chittenden Southeast; WDR ORA 1 -> Windsor-Orange-1; GI CHI -> Grand Isle-Chittenden."""
    words = code.split()
    if chamber == "Senate":
        if not words or words[0] not in COUNTY_ABBR or words[-1] != "1" or len(words) > 3:
            raise SystemExit(f"Vermont: a senate district code that is not read: {code!r}")
        mid = words[1:-1]
        if mid and mid[0] not in SENATE_PART:
            raise SystemExit(f"Vermont: a senate district code that is not read: {code!r}")
        return " ".join([COUNTY_ABBR[words[0]]] + [SENATE_PART[m] for m in mid])
    parts = []
    for w in words:
        if w in COUNTY_ABBR:
            parts.append(COUNTY_ABBR[w])
        elif w.isdigit():
            parts.append(w)
        else:
            raise SystemExit(f"Vermont: a house district code that is not read: {code!r}")
    return "-".join(parts)


def race_id(contest, district=None):
    if contest in STATEWIDE:
        return f"2026-{STATE}-{STATEWIDE[contest][0]}"
    return f"2026-{STATE}-{LEGISLATURE[contest][0]}{district.upper().replace(' ', '-')}"


# ------------------------------------------------------------------------------------------------- the roster

def roster(path):
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    legs = [dict(zip(("id", "first", "last", "full", "other", "party", "chamber", "district"), r)) for r in con.execute(
        "SELECT bioguide_id, first_name, last_name, official_full, other_names, party_name, chamber, district FROM legislators WHERE is_current = 1")]
    offs = {r[1]: dict(zip(("id", "office", "full", "first", "last", "party"), r)) for r in con.execute(
        "SELECT bioguide_id, office, official_full, first_name, last_name, party_name FROM officials")}
    con.close()
    return legs, offs


def person_forms(p):
    forms = [(fold(p["first"] or "").split(), " ".join(fold(p["last"] or "").split()))]
    forms += [name_parts(o.strip()) for o in (p.get("other") or "").split(";") if o.strip() and "," not in o and "." not in o]
    return [f for f in forms if f[1]]


def person_fits(name, p):
    cand = name_parts(name)
    return any(fits(cand, f) for f in person_forms(p))


def as_person(name):
    given, family = name_parts(name)
    return {"first": " ".join(given), "last": family, "other": ""}


def parties_meet(label, roster_party):
    a = {w for w in re.split(r"[/ ]+", (label or "").lower()) if w}
    b = {w for w in re.split(r"[/ ]+", (roster_party or "").lower()) if w}
    return bool(a & b)


def surname_order(names):
    """True when the names can be read as alphabetical by surname: each name's surname is taken as its last word or its
    last words (Ram Hinsdale, St Marthe, Allen-Pennebaker), and some choice of them must never go backwards."""
    prev = ""
    for n in names:
        words = [w for w in re.sub(r'"[^"]*"', " ", n).upper().replace(".", " ").split() if w not in ("JR", "SR", "II", "III", "IV")]
        options = sorted(" ".join(words[i:]) for i in range(1, len(words))) or [" ".join(words)]
        ok = [o for o in options if o >= prev]
        if not ok:
            return False
        prev = ok[0]
    return True


def ordinary(caps):
    """A name printed in capitals in ordinary capitals: each word and each part of a hyphened word begins with a capital
    (Van Oort, Bos-Lun), McLaren, O'Brien, initials stay capitals (A.M.), Jr. and Sr. as words, II and III kept."""
    out = []
    for i, w in enumerate(squash(caps).split()):
        if re.fullmatch(r"(JR|SR)\.?", w):
            out.append(w.title())
        elif i and re.fullmatch(r"[IVX]+", w):
            out.append(w)
        elif re.fullmatch(r"(?:[A-Z]\.)+[A-Z]?\.?", w):
            out.append(w)
        else:
            parts = []
            for p in w.split("-"):
                p2 = p[:1] + p[1:].lower()
                p2 = re.sub(r"^Mc([a-z])", lambda m: "Mc" + m.group(1).upper(), p2)
                p2 = re.sub(r"^([\"'(]?)([a-z])", lambda m: m.group(1) + m.group(2).upper(), p2)
                p2 = re.sub(r"^([\"'(]?)O'([a-z])", lambda m: m.group(1) + "O'" + m.group(2).upper(), p2)
                parts.append(p2)
            out.append("-".join(parts))
    return " ".join(out)


def party_words(label):
    """DEMOCRATIC -> Democratic; REP/DEM -> Republican/Democratic; WOMEN'S LIBERATION VEGI-ARYAN -> Women's Liberation Vegi-Aryan."""
    out = []
    for p in (label or "").split("/"):
        p = p.strip()
        if p in SHORT:
            out.append(SHORT[p])
            continue
        words = []
        for i, w in enumerate(p.split()):
            if i and w in ("AND", "OF", "THE", "FOR"):
                words.append(w.lower())
            else:
                words.append("-".join(x[:1] + x[1:].lower() for x in w.split("-")))
        out.append(" ".join(words))
    return "/".join(out)


def census_counties(path):
    import shapefile                                                        # pyshp, in the kit's environment
    z = zipfile.ZipFile(path)
    base = next(n for n in z.namelist() if n.endswith(".dbf"))
    rdr = shapefile.Reader(dbf=io.BytesIO(z.read(base)))
    return {r["NAME"].upper(): (r["GEOID"], r["NAME"]) for r in (x.as_dict() for x in rdr.iterRecords()) if r["STATEFP"] == FIPS}


def file_facts(path):
    raw = open(path, "rb").read()
    return sha(raw), dt.datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------------------------------- loading

def load(db_path, say=print, cache=CACHE, roster_db=ROSTER, county_zip=COUNTY_ZIP):
    net.patient_lookups()
    folder = os.path.join(cache, "vt")
    gpath = os.path.join(folder, "vt_2026_sl_general_list.json")
    ppath = os.path.join(folder, "vt_2026_sl_primary_list.json")
    wpath = os.path.join(folder, "vt_2026_sl_primary_winner_listing.json")
    epath = os.path.join(folder, "vt_2026_sl_primary_results.json")
    cpath = os.path.join(folder, "vt_2026_primary_official_canvass_town_by_town.pdf")      # the federal loader's copy; results only
    gen = kept(gpath, 2, general_list)
    pri = kept(ppath, 30, primary_list)
    win = kept(wpath, 30, winner_listing)
    legs, offs = roster(roster_db)
    counties = census_counties(county_zip)
    report = []

    # ---- districts: the list's codes, the roster's names, seats
    seats = defaultdict(list)
    for p in legs:
        seats[(p["chamber"], p["district"])].append(p)
    by_key = {(ch, dkey(d)): d for ch, d in seats}

    def district_of(contest, code):
        chamber = LEGISLATURE[contest][3]
        name = district_name(code, chamber)
        d = by_key.get((chamber, dkey(name)))
        if d is None:
            raise SystemExit(f"Vermont: the list's {chamber} district {code!r} ({name}) is not a district of the roster")
        return d

    # registered write-ins: office, district key, name parts
    def reg_district(r, office):
        if office in STATEWIDE:
            return ""
        chamber = LEGISLATURE[office][3]
        text = r["SENATE DISTRICT"] if office == SENATE else r["REPRESENTATIVE (HOUSE) DISTRICT"]
        hits = {d for (ch, k), d in by_key.items() if ch == chamber and k == dkey(text)}
        if len(hits) != 1:
            raise SystemExit(f"Vermont: a registered write-in's {chamber} district is not read ({text!r})")
        return hits.pop()

    registered = []                                                            # (office, roster district, shown name, parts)
    for r in pri["write_in"]:
        office = WRITE_OFFICE[r["OFFICE"].upper()]
        d = reg_district(r, office)
        caps = " ".join(x for x in (r["FIRST NAME"], r["MIDDLE NAME"], r["LAST NAME"]) if x)
        registered.append((office, d, caps, (fold(r["FIRST NAME"]).split(), " ".join(fold(r["LAST NAME"]).split()))))

    code_of = {}                                                               # roster district -> the Secretary's code (for the results)

    def enr_fetch():
        # The results carry districts by the Secretary's codes; a registered write-in's district is keyed by that code.
        reg = []
        for office, d, _caps, parts in registered:
            reg.append((office, "" if office in STATEWIDE else dkey(code_of[(office, d)]), parts))
        return enr_results(reg)

    # ---- the November list
    groups = {}                                                                # (contest, district or None) -> [rows in list order]
    for r in gen["state"]:
        contest = r["Contest"].upper()
        if contest in STATEWIDE:
            if r["District Name"] not in ("N/A", ""):
                raise SystemExit(f"Vermont: a statewide office row names a district ({r['District Name']!r})")
            key = (contest, None)
        else:
            d = district_of(contest, r["District Name"])
            prev = code_of.setdefault((contest, d), r["District Name"])
            if prev != r["District Name"]:
                raise SystemExit(f"Vermont: two codes on the list for the {contest} district {d}")
            key = (contest, d)
        if r["Vote for Count"] not in COUNT:
            raise SystemExit(f"Vermont: a Vote for Count that is not read ({r['Vote for Count']!r})")
        groups.setdefault(key, []).append(r)
    for (ch, d), members in seats.items():
        contest = SENATE if ch == "Senate" else HOUSE
        if (contest, d) not in code_of:
            report.append(f"{race_id(contest, d)}: no candidate on the November list for this district")
    # the primary list's codes for districts nobody filed for in November
    for sheet, rows in pri["parties"].items():
        for r in rows:
            c = r["Contest"].upper()
            if c in LEGISLATURE:
                code_of.setdefault((c, district_of(c, r["District Name"])), r["District Name"])
    for r in win["rows"]:
        c = r["Office Name"].upper()
        if c in LEGISLATURE:
            code_of.setdefault((c, district_of(c, r["District"])), r["District"])
    for office, d, _caps, _parts in registered:
        if office in LEGISLATURE and (office, d) not in code_of:
            raise SystemExit(f"Vermont: a registered write-in's district ({d}) is on none of the Secretary's lists")

    enr = kept(epath, 30, enr_fetch)

    missing = [c for c in STATEWIDE if (c, None) not in groups]
    if missing:
        raise SystemExit(f"Vermont: statewide offices missing from the November list: {missing}")
    sen_d = sorted(d for c, d in groups if c == SENATE)
    house_d = sorted(d for c, d in groups if c == HOUSE)
    all_sen = sorted(d for ch, d in seats if ch == "Senate")
    all_house = sorted(d for ch, d in seats if ch == "House")
    if sum(len(seats[("Senate", d)]) for d in all_sen) != 30 or sum(len(seats[("House", d)]) for d in all_house) != 150:
        report.append("the roster does not seat 30 senators and 150 representatives")

    # names as shown: the roster's own capitals where its words are the same words
    fixed = {}
    for p in legs + list(offs.values()):
        for form in (p["full"], f"{p['first']} {p['last']}"):
            if form:
                fixed[fold(form)] = form

    def shown(caps):
        caps = squash(caps)
        if fold(caps) in fixed:
            return fixed[fold(caps)]
        return ordinary(caps)

    colours = {k: v[0] for k, v in (place(STATE).get("parties") or {}).items()}

    def colour(label):
        """The one-letter colour code the state pages give the party (states/places.py), else the kit's own rule."""
        return colours.get(label) or party_code(label.split("/")[0])

    def holders(contest, d):
        if contest in STATEWIDE:
            rk = STATEWIDE[contest][3]
            return [offs[rk]] if rk and rk in offs else []
        return sorted(seats.get((LEGISLATURE[contest][3], d), []), key=lambda p: (fold(p["last"] or ""), fold(p["first"] or "")))

    def identify(contest, d, name, party):
        """(incumbent, state_member_id, note) for one listed name."""
        here = [h for h in holders(contest, d) if person_fits(name, h)]
        if len(here) == 1:
            return 1, here[0]["id"], None
        if len(here) > 1:
            report.append(f"{race_id(contest, d)}: {name} fits more than one holder; no member is linked")
            return 0, None, None
        pool = [p for p in legs if person_fits(name, p) and parties_meet(party, p["party"])]
        pool += [p for p in offs.values() if person_fits(name, p) and parties_meet(party, p["party"])]
        if len(pool) == 1:
            p = pool[0]
            where = (f"the {p['chamber']} ({p['district']})" if p in legs else f"the office of {p['office'].replace('_', ' ').replace('lt ', 'lieutenant ')}")
            return 0, p["id"], f"Serves today in {where}."
        return 0, None, None

    races, cands, general_n = {}, [], Counter()
    for (contest, d), rows in groups.items():
        rid = race_id(contest, d)
        vf = {COUNT[r["Vote for Count"]] for r in rows}
        if len(vf) != 1:
            raise SystemExit(f"Vermont: {rid} has two Vote for Counts on the list")
        vf = vf.pop()
        hs = holders(contest, d)
        note = []
        if contest in STATEWIDE:
            okind, office = STATEWIDE[contest][1:3]
            level, jur, jid, cids, dist = "statewide", "Vermont", FIPS, None, None
            if vf != 1:
                raise SystemExit(f"Vermont: {rid} elects {vf} on the list")
            if not hs:
                note.append("The roster used here does not list who holds this office today.")
        else:
            okind, office, chamber = LEGISLATURE[contest][1:]
            level, dist = "legislature", d
            jur = f"{d} {'Senate' if chamber == 'Senate' else 'House'} District"
            jid = f"{STATE}-{d.upper().replace(' ', '-')}"
            names = enr["counties"].get(f"{'senate' if chamber == 'Senate' else 'house'}|{code_of[(contest, d)]}", [])
            bad = [n for n in names if n not in counties]
            if not names or bad:
                raise SystemExit(f"Vermont: {rid}: the results' town table gives no counties, or names a county not in the Census file ({bad})")
            cids = ",".join(sorted(counties[n][0] for n in names))
            if len(hs) != vf:
                report.append(f"{rid}: the list elects {vf}; the roster seats {len(hs)} here today")
            if vf > 1:
                word = {2: "two", 3: "three"}[vf]
                title = "senators" if chamber == "Senate" else "representatives"
                note.append(f"{word.capitalize()} seats: the district elects {word} {title}, each voter may vote for {word}, and the {word} "
                            "with the most votes win.")
            if not hs:
                note.append("The roster used here lists nobody in this district today.")
        races[rid] = {"row": [rid, STATE, level, okind, office, jur, jid, cids, dist, None, 0, 1,
                              "; ".join(h["id"] for h in hs) or None, "; ".join(h["full"] for h in hs) or None,
                              "; ".join(h["party"] or "" for h in hs) or None, GENERAL, None],
                      "note": note, "contest": contest, "d": d, "vf": vf, "hs": hs}
        if len(rows) < vf:
            report.append(f"{rid}: {len(rows)} candidate(s) on the November list for {vf} seat(s)")
        ordered = surname_order([r["Name On Ballot"] for r in rows])
        if not ordered:
            report.append(f"{rid}: the list's names are not in alphabetical order by surname; no ballot order is stored")
        for i, r in enumerate(rows, start=1):
            if not r["Party"]:
                raise SystemExit(f"Vermont: a candidate in {rid} has no party on the list")
            party = party_words(r["Party"])
            name = shown(r["Name On Ballot"])
            incb, mid, n2 = identify(contest, d, name, party)
            cands.append([rid, "general", GENERAL, name, party, colour(party), i if ordered else None, incb, 0,
                          None, None, None, mid, SRC_GEN, " ".join(x for x in (CAPS, n2) if x)])
            general_n[okind] += 1
    for r in gen["write_in"]:                                                    # none on the list today; kept if one appears
        office = WRITE_OFFICE[r["OFFICE"].upper()]
        d = reg_district(r, office)
        rid = race_id(office, d if office in LEGISLATURE else None)
        if rid not in races:
            raise SystemExit(f"Vermont: a registered November write-in for a race with nobody on the list ({rid})")
        caps = " ".join(x for x in (r["FIRST NAME"], r["MIDDLE NAME"], r["LAST NAME"]) if x)
        cands.append([rid, "general", GENERAL, shown(caps), "Write-in", "W", None, 0, 1, None, None, None, None, SRC_GEN,
                      f"{WRITE_NOV} {CAPS}"])

    # ---- the August 11 primary
    printed = defaultdict(list)                                                # (party, contest, district or None) -> [printed names]
    for sheet, rows in pri["parties"].items():
        for r in rows:
            c = r["Contest"].upper()
            d = None if c in STATEWIDE else district_of(c, r["District Name"])
            printed[(sheet, c, d)].append(r["Name On Ballot"])
    listing = defaultdict(dict)
    for r in win["rows"]:
        c = r["Office Name"].upper()
        d = None if c in STATEWIDE else district_of(c, r["District"])
        listing[(r["Party"], c, d)][fold(r["Name on Ballot"])] = (int(r["Votes"].replace(",", "")), bool(r["Winner"]))
    if win["criteria"].get("Election Name") != "08/11/2026 - AUGUST PRIMARY":
        raise SystemExit(f"Vermont: the winner listing is for {win['criteria'].get('Election Name')!r}")

    committee, stars = committee_report(cpath) if os.path.exists(cpath) else ({}, set())
    if not committee:
        report.append("the canvass PDF is not in the cache (the federal loader keeps it); the statewide figures were not compared with it")

    fields, primary_rows, checked, placed_reg = Counter(), 0, 0, Counter()
    reg_seen = Counter()
    visited = set()
    for c in enr["contests"]:
        contest, pn = c["office"], c["party"]
        d = None if contest in STATEWIDE else district_of(contest, c["dc"])
        rid = race_id(contest, d)
        where = f"{rid} {pn.title()} primary"
        visited.add((pn, contest, d))
        if rid not in races:
            if c["printed"] or c["write_ins"]:
                report.append(f"{where}: in the results, but the race has nobody on the November list")
            continue
        if c["vf"] != races[rid]["vf"]:
            raise SystemExit(f"Vermont: {where}: the results elect {c['vf']}, the November list {races[rid]['vf']}")
        on_ballot = {fold(n) for n in printed.get((pn, contest, d), [])}
        in_results = {fold(n) for n, _v, _w, wi in c["printed"] if not wi}
        if on_ballot != in_results:
            raise SystemExit(f"Vermont: {where}: the results' printed candidates are not the primary list's")
        # control: the winner listing
        lst = listing.get((pn, contest, d), {})
        mine = {fold(n): (v, w) for n, v, w, _wi in c["printed"]}
        if lst != mine:
            diff = sorted(set(lst) ^ set(mine)) or sorted(k for k in mine if lst.get(k) != mine[k])
            raise SystemExit(f"Vermont: {where}: the winner listing and the results differ ({len(diff)} names)")
        checked += 1
        # control: the canvassing committee (statewide offices)
        if contest in STATEWIDE and committee:
            cm = committee.get(contest, {}).get(pn)
            if cm is None:
                raise SystemExit(f"Vermont: {where}: not in the canvassing committee's report")
            want = {fold(n): v for n, v, _w, _wi in c["printed"]}
            got = {fold(k): v for k, v in cm.items() if k not in ("Write-In", "Overvotes", "Blank votes", "Total")}
            if want != got or cm.get("Write-In") != c["write_in_all"] or cm.get("Overvotes") != c["spoiled"] \
                    or cm.get("Blank votes") != c["blank"] or cm.get("Total") != c["total"]:
                raise SystemExit(f"Vermont: {where}: the canvassing committee's figures differ from the results")
            starred = {fold(k) for (o, p, k) in stars if o == contest and p == pn}
            if starred != {fold(n) for n, _v, w, _wi in c["printed"] if w}:
                raise SystemExit(f"Vermont: {where}: the committee's starred winners are not the results' winners")
        # the field: the results' candidate rows (printed names and write-ins who won), then registered write-ins
        regs_here = [r for r in registered if r[0] == contest and (contest in STATEWIDE or r[1] == d)]
        people = []                                                          # (name, votes, won, write-in, entries, registered)
        for n, v, w, wi in c["printed"]:
            reg = None
            if wi:
                hits = [r for r in regs_here if fits(name_parts(n), r[3]) and name_parts(n)[1] == r[3][1]]
                reg = hits[0] if len(hits) == 1 else None
            people.append((reg[2] if reg else n, v, w, bool(wi), None, reg))
        for idx, name, v, n_entries, won in c["write_ins"]:
            if idx is None:                                                  # a write-in winner outside the candidate rows: not expected
                report.append(f"{where}: a winning write-in not among the results' candidates; left out")
                continue
            reg = regs_here[idx]
            if any(p[5] is not None and p[5][:3] == reg[:3] for p in people):
                report.append(f"{where}: a registered write-in who won has more write-in entries besides the winner's row; they are left out")
                continue
            people.append((reg[2], v, won, True, n_entries, reg))
        pool = sum(p[1] for p in people if p[4] is None) + c["write_in_all"]         # candidates' rows plus every write-in vote
        winners = [p for p in people if p[2]]
        if len(winners) > c["vf"]:
            raise SystemExit(f"Vermont: {where}: {len(winners)} winners for {c['vf']} seats")
        if len(people) <= c["vf"]:
            continue
        fields[races[rid]["row"][3]] += 1
        nov = [x for x in cands if x[0] == rid and x[1] == "general"]
        code = CODE[pn]
        for name, v, won, wi, n_entries, reg in sorted(people, key=lambda p: -p[1]):
            if reg is not None:
                reg_seen[reg[:3]] += 1
            label = party_words(pn)
            if wi:
                same = [x[3] for x in nov if person_fits(x[3], as_person(name))]
                nm = same[0] if len(same) == 1 else shown(name)                 # as the November list prints it, else as filed or counted
            else:
                nm = shown(next((x for x in printed.get((pn, contest, d), []) if fold(x) == fold(name)), name))
            incb, mid, n2 = identify(contest, d, nm, label)
            note = [CAPS]
            if wi and n_entries is None:
                note.insert(0, WRITE_WON_REG if reg is not None else WRITE_WON)
            elif wi:
                note.insert(0, WRITE_REG + (f" Votes added from {n_entries} entries in the results, where towns reported the name "
                                            "under the same or a fitting spelling." if n_entries > 1 else ""))
            if won:
                on_nov = [x for x in nov if person_fits(x[3], as_person(nm)) and code in {PARTY_CODE.get(p) for p in x[4].split("/")}]
                if not on_nov:
                    note.insert(0, f"Won the primary; not on the November list as the {label} candidate.")
                    report.append(f"{where}: {nm} won but is not on the November list as the {label} candidate")
            if n2:
                note.append(n2)
            cands.append([rid, f"primary-{code}", PRIMARY, nm, label, colour(label), None, incb, int(wi), v,
                          round(100 * v / pool, 1) if pool else None, "advanced" if won else "lost", mid, SRC_ENR, " ".join(note)])
            primary_rows += 1
    unread = [k for k in listing if k not in visited]
    if unread:
        raise SystemExit(f"Vermont: the winner listing has {len(unread)} party primaries the results do not carry")
    for office, d, caps, _parts in registered:
        if not reg_seen[(office, d, caps)]:
            placed_reg["not named"] += 1
        else:
            placed_reg["named"] += 1

    # every November candidate of a party that held a primary field should be among that field
    for x in cands:
        if x[1] != "general":
            continue
        for part in x[4].split("/"):
            code = PARTY_CODE.get(part)
            if not code:
                continue
            field = [y for y in cands if y[0] == x[0] and y[1] == f"primary-{code}"]
            if field and not any(fits(name_parts(y[3]), name_parts(x[3])) and y[11] == "advanced" for y in field):
                report.append(f"{x[0]}: {x[3]} ({part}) is on the November list but did not win that party's primary field")

    seen = set()
    for x in cands:
        k = (x[0], x[1], x[3])
        if k in seen:
            raise SystemExit(f"Vermont: {x[3]} is listed twice in {x[0]} {x[1]}")
        seen.add(k)

    # ---- the roster's party for a holder against the party the November list prints for the same person
    for rid, race in races.items():
        for h in race["hs"]:
            same = [x for x in cands if x[0] == rid and x[1] == "general" and x[12] == h["id"]]
            for x in same:
                if not parties_meet(x[4], h["party"]):
                    report.append(f"{rid}: the roster gives {h['full']} the party {h['party']!r}; the November list prints {x[4]!r}")

    for rid, race in races.items():
        race["row"][16] = " ".join(race["note"]) or None
    general = [x for x in cands if x[1] == "general"]
    place_rows = [("county", g, n, g, SRC_COUNTY) for g, n in sorted(counties.values())]
    for rid, race in sorted(races.items()):
        r = race["row"]
        if r[2] == "legislature":
            place_rows.append(("senate" if r[3] == "state_senate" else "house", r[6], r[5], r[7], SRC_ENR))

    gen_sha, pri_sha, win_sha = gen["sha256"], pri["sha256"], win["sha256"]
    roster_sha, roster_date = file_facts(roster_db)
    county_sha, county_date = file_facts(county_zip)
    enr_sha = "; ".join(f"{k} {v['sha256']}" for k, v in enr["files"].items())
    m = re.match(r"(\d\d)/(\d\d)/(\d{4})", enr.get("updated", ""))
    enr_published = f"{m.group(3)}-{m.group(1)}-{m.group(2)}" if m else ""
    sources = [
        (SRC_GEN, STATE, "official candidate list", "Vermont Secretary of State, Elections Division",
         "2026 General Election Candidate Listing/Financial Disclosure (qualified candidates): statewide offices and the General Assembly",
         GENERAL_XLSX, gen["updated"], gen["fetched"], gen_sha, len(general),
         f"Linked from the Candidates page ({CANDIDATES_PAGE}). Workbook read in memory, never saved; columns taken by name, only Contest, "
         "District Name, Name On Ballot, Party and Vote for Count. Town of residence, addresses, phones, e-mail, websites and financial "
         "disclosures never read. The list gives no ballot positions; its order, alphabetical by surname as 17 V.S.A. 2472(b)(2) prints the "
         "ballot, is stored as the ballot order. No status column, so a withdrawn candidate, no longer listed, cannot be counted. The "
         "Secretary's district codes are shown as the Legislature's district names. Offices on the list not loaded here: "
         + ", ".join(f"{k.title()} ({v})" for k, v in sorted(gen["others"].items())) + "."),
        (SRC_PRI, STATE, "official candidate list", "Vermont Secretary of State, Elections Division",
         "2026 Primary Election Candidate Listing/Financial Disclosure (qualified candidates): statewide offices and the General Assembly",
         PRIMARY_XLSX, pri["updated"], pri["fetched"], pri_sha, sum(len(v) for v in pri["parties"].values()) + len(pri["write_in"]),
         "Who was printed on each party's August 11 primary ballot (the results' printed candidates must be exactly these) and the registered "
         f"write-in candidates ({len(pri['write_in'])} for these offices; the registration names no party). The same five columns only, and "
         "the write-in sheet's office, district and name columns."),
        (SRC_ENR, STATE, "official results", "Vermont Secretary of State, Elections Division",
         "2026 August Primary Election Results (official), statewide offices, State Senate and State Representative",
         ENR_SITE, enr_published, enr["fetched"], enr_sha, primary_rows,
         f"Linked from the Elections Results & Data page ({RESULTS_PAGE}); read from the files the results site's own page fetches "
         f"({ENR_STATIC}elections/...), marked official, {enr.get('towns_reporting', '')} towns reporting. Every town's candidates, write-ins, "
         "blank votes and spoiled ballots add up to its total, and the towns to the district-wide and statewide rows. A field is a party "
         "primary with more candidates than seats; its total is the candidates' votes plus every write-in vote (blanks and spoiled ballots "
         "left out). Write-in names are shown only for a write-in who won the nomination, or a registered write-in candidate recorded in "
         "one party's primary for that office and district; every other write-in is counted in the total and never named "
         f"({enr.get('registered_in_two_parties', 0)} registered write-ins were recorded in more than one party's primary, so in neither "
         "is the name shown). The results' town table gives the counties each district reaches."),
        (SRC_WIN, STATE, "official results", "Vermont Secretary of State, Elections Division",
         "2026 August Primary Winner Listing", WINNERS_XLSX, "", win["fetched"], win_sha, len(win["rows"]),
         f"Control: every candidate's votes and winner mark agree with the results ({checked} party primaries compared). Workbook read in "
         "memory, never saved; Winner, Name on Ballot, Party, Office Name, District, Votes and Percent(%) only; addresses and phones never "
         "read. Its percentages are of all votes counted, blank votes included."),
    ]
    if committee:
        c_sha, c_date = file_facts(cpath)
        sources.append((SRC_CANVASS, STATE, "official results", "Vermont Secretary of State, Elections Division",
                        "2026 August Primary Official Canvass - Town by Town: the Official Report of the Canvassing Committee (17 V.S.A. 2368-2371)",
                        CANVASS_PDF, "", c_date, c_sha, sum(len(v) for v in committee.values()),
                        "Control for the six statewide offices: every candidate's votes, the write-in, overvote, blank and total figures and the "
                        "starred winners equal the results site's statewide rows. Only the committee's report pages are read."))
    sources += [
        (SRC_ROSTER, STATE, "roster", "Open States people project (CC0), as loaded into state_vt.sqlite",
         "Sitting legislators and statewide officials", "https://github.com/openstates/people", "", roster_date, roster_sha, len(legs) + len(offs),
         "Who holds each seat today, and which candidates serve now. The roster does not carry the State Treasurer or the Auditor of Accounts."),
        (SRC_COUNTY, STATE, "county codes", "U.S. Census Bureau", "Cartographic boundary file, counties, 2024 (1:500,000)",
         "https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_county_500k.zip", "2024", county_date, county_sha, len(counties),
         "Five-digit county codes (GEOID) for Vermont's fourteen counties, named as the results' town table names them."),
    ]

    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA)
    mine_src = [s[0] for s in sources] + [SRC_CANVASS]
    with con:
        con.execute("DELETE FROM sl_candidates WHERE race_id IN (SELECT race_id FROM sl_races WHERE state = ?)", (STATE,))
        con.execute("DELETE FROM sl_candidates WHERE race_id LIKE ?", (f"2026-{STATE}-%",))
        con.execute("DELETE FROM sl_races WHERE state = ?", (STATE,))
        con.execute(f"DELETE FROM sl_places WHERE source_id IN ({','.join('?' * len(mine_src))})", mine_src)
        con.execute("DELETE FROM sl_places WHERE id LIKE ?", (f"{STATE}-%",))
        con.execute("DELETE FROM sl_sources WHERE state = ?", (STATE,))
        con.executemany("INSERT INTO sl_races VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [r["row"] for r in races.values()])
        con.executemany("INSERT INTO sl_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", cands)
        con.executemany("INSERT INTO sl_places VALUES (?,?,?,?,?)", place_rows)
        con.executemany("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", sources)
    con.close()

    n_sw = sum(1 for r in races.values() if r["row"][2] == "statewide")
    say(f"    Vermont: {len(races)} races ({len(sen_d)} Senate districts, {len(house_d)} House districts, {n_sw} statewide); "
        f"{len(general)} candidates on the November list (Senate {general_n['state_senate']}, House {general_n['state_house']}, statewide "
        f"{len(general) - general_n['state_senate'] - general_n['state_house']}); primary fields: Senate {fields['state_senate']}, House "
        f"{fields['state_house']}, statewide {sum(v for k, v in fields.items() if k not in ('state_senate', 'state_house'))}; "
        f"{primary_rows} primary rows ({placed_reg['named']} of {len(registered)} registered write-in candidates named in a field); "
        f"{checked} party primaries checked against the winner listing")
    for x in cands:
        if x[12]:
            say(f"      matched: {x[0]} {x[1]}: {x[3]} -> {x[12]}{' (holds this seat)' if x[7] else ''}")
    for line in report:
        say(f"      check: {line}")
    return {"races": len(races), "general": len(general), "by_kind": dict(general_n), "fields": dict(fields), "primary_rows": primary_rows,
            "report": report}


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        raise SystemExit("usage: python -m ballot.state_local_vt <database> [cache folder]")
    load(sys.argv[1], cache=sys.argv[2] if len(sys.argv) > 2 else CACHE)
