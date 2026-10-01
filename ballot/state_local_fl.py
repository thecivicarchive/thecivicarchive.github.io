"""
ballot/state_local_fl.py - Florida's state races, and its county and local races, on the November 3, 2026 ballot, into
ballot_local_2026.sqlite. The state part comes first; the county and local part is described further down.

The state part: Florida's state races on the November 3, 2026 ballot
(Florida's rows only; the federal ballot database, ballot_2026.sqlite, is never opened here):

  - Governor (with the Lieutenant Governor on one ticket), Attorney General, Chief Financial Officer and Commissioner
    of Agriculture, the four offices elected statewide (the Secretary of State is appointed);
  - the 20 even-numbered seats of the Florida Senate (senators serve four years; the even-numbered districts are
    elected in years that are not multiples of four, Article III, section 15(a) of the Florida Constitution) and any
    Senate or House seat the Division lists a special election for on November 3 (this year Senate District 21, for the
    rest of its term);
  - all 120 seats of the Florida House (two-year terms);
  - the retention votes for the Supreme Court and the District Courts of Appeal, and the circuit judge seats that go to
    a November runoff because no one won a majority on August 18 (section 105.051, Florida Statutes);
with each party's August 18, 2026 primary field and its official votes, and the circuit judges' August 18 nonpartisan
election (stored as primary-NP). Which offices and seats are up is read from the Division's own list, and checked: the
Senate seats on the 2026 list must be exactly the even-numbered districts, and the Division's 2024 list must carry the
odd-numbered ones.

Sources, all official:
  - the Division of Elections' Candidate Tracking System (dos.elections.myflorida.com/candidates/downloadcanlist.asp),
    the same download the federal loader (ballot/lists/fl.py) uses for Congress: a POST to extractCanList.asp answers
    with a tab-separated file, one row per candidate. Read here for the 2026 Election (20261103-GEN), offices "Governor
    and Cabinet", "Senate and House" and "Judicial Offices", every status, state candidates; every November 3 special
    election the form offers (20261103-S01, "2026 Special: Senate 21"); and the 2024 Election's "Senate and House", only
    for which Senate districts were elected that year.
  - the Division's official results of the August 18, 2026 Primary Election (results.elections.myflorida.com): the
    Data Download Utility's results extract (08182026Election.txt, fetched and kept by the federal loader in
    ballot_cache/fl/, OfficialResults=Y), one row per county, party, contest and candidate; and the Summary Reports
    for "Governor and Cabinet" and "Senate and House" (Republican and Democratic) and "Judicial Offices"
    (nonpartisan), each headed "Official Results". Every candidate's county rows must add up to the Summary Report's
    Total and its "% Votes" must equal the share computed here; every precinct must have reported; the statewide
    contests must list all 67 counties.
  - the Division's list of political parties (dos.fl.gov/elections/candidates-committees/political-parties/), for a
    party the candidate list names by code only (MGT, the MGTOW Party).
  - the Florida Statutes (Online Sunshine, www.leg.state.fl.us): section 26.021 (the counties of each judicial circuit)
    and sections 35.02 to 35.044 (the circuits of each appellate district), for the counties a court race reaches.
    Each circuit's counties are checked against the counties its August 18 contests were counted in.
  - the Census Bureau's 2024 cartographic boundary files (states_cache/census/): counties (five-digit codes), and the
    State Senate and State House districts. Which counties a district reaches is worked out by laying the district
    over the counties on a grid of about 220 metres, counting only cells more than about half a kilometre inside a
    county (so the slivers two generalised boundary files leave along a shared line are not counted); derived, and
    said so. Every district with a primary contest must reach exactly the counties the official results count it in.
Who holds each seat comes from the Open States roster in state_fl.sqlite (legislators serving now, by chamber and
district; the officials table for Governor and Attorney General, the only elected statewide offices it carries): ids,
names and party only. A candidate is the incumbent when the name fits the seat's holder (same chamber and district,
one fit only); a candidate for another seat gets the member's id, and a note, only when the name fits exactly one
sitting member or official of the same party. A judge standing for retention is by law the sitting judge of that seat.

Privacy. The candidate list carries voter ID numbers, account numbers, addresses, cities, ZIP codes, counties of
residence, telephone numbers, treasurers' names and e-mail. Each download is held in memory only long enough to find
its column headings and cut every row down to twelve columns, by heading: ElectionID, OfficeCode, OfficeDesc,
Juris1num, Juris2num, StatusCode, StatusDesc, PartyCode, PartyDesc, NameLast, NameFirst, NameMiddle. The rest is never
read, printed, logged, cached or stored; the file is never saved, even to scratch (its SHA-256 as received is kept, so
the copy read can be named). The cut-down rows are cached as JSON in ballot_cache/fl/. An error names the list, the
contest or the check, never a row. The results, the Summary Reports, the party list and the statutes carry no contact
details. The roster's contact columns are never selected. Before anything is written every stored name, party and note
is checked for anything that looks like a contact detail, and the load stops (without showing it) if one does.

Ballot order. The list prints none (Florida orders names by party under section 101.151, Florida Statutes), so no
ballot_order is stored. Florida's primaries are closed, one per party; a party with one qualified candidate holds none.
Where every candidate who qualified is of one party, the primary was open to every voter (a universal primary,
Article VI, section 5(b)) and its winner is elected without appearing on the November ballot. An unopposed candidate
is not printed on the November ballot (status Unopposed; stored as a general election row with outcome "unopposed").

The county and local part (added 2026-10-01)
--------------------------------------------
Besides the state rows above, the loader writes Florida's county, school board, county court and special district
contests on the November 3 ballot (levels county, school, soil_water, hospital and other; county judges, and the state
attorney and public defender a notice names, under court), and the two tables that say what is missing (sl_gaps) and
how the lists read (sl_notes). Three official sources, each doing one job:

  what is to be filled   the Secretary of State's Notices of General Election, one PDF for each of the 67 counties
                         (dos.fl.gov/elections/for-voters/notices-of-general-election/): every county office, school
                         board district, county judge's group and special district seat, by name. A district in a
                         notice's first block (before the county offices) reaches more than one county and is one
                         place. The notices name no candidate and carry no contact detail; the files are kept as
                         published, and one is downloaded again only when its address on the Division's page changes.
  who is running         the Division's Candidate Tracking System download, Type "Local Candidates", 2026 Election
                         (the same form as above), with its "Special Districts" list of state candidates (the
                         districts of more than one county, whose candidates qualify with the Division) and its
                         "State Attorney / Public Defender" list. The Division offers the system as an unofficial
                         reference and sends readers to the county supervisors of elections for county candidates. A
                         row gives the office (BCC, SCB, COJ, DEV ...), the seat, the status, the party and the name:
                         no county, and no district's name. Qualified is the November ballot; Unopposed is kept with
                         a note (section 101.151); Defeated, Withdrew, Did Not Qualify and Deceased are counted and
                         left out. The file's accented letters are single Windows-1252 bytes; pull() reads them as
                         such (the state lists above have none).
  where                  each county supervisor of elections' own candidate page (one layout for all 67, at
                         voterfocus.com/CampaignFinance/candidate_pr.php?c=<county>), the reporting group for the
                         2026 election and any special election it keeps apart for November 3: office headings, and
                         under each the candidates with a status. A row of the Division's list is placed in the
                         county and district whose page has the same name (the family name and a given name that
                         fits), an office of the same kind and the same seat number. A district's name as a
                         supervisor words it ("ALVA FIRE-2", "VCDD 12", "Lake Asbury MSBD") is matched to the
                         notice's name by spelling (explain()), and must fit one district only. A row that fits
                         nothing, or two contests, is not placed; it is counted, and said in sl_gaps.
The list's address block carries a county code as well. It is the candidate's own (empty where the address is
withheld), so it is never read: that is why the supervisors' pages are needed.

What the list's statuses mean was checked against the supervisors' pages. An "Unopposed" row whose rivals are marked
"Defeated" won on August 18 (the supervisors say "Elected"); with no rival it was unopposed from the start. School
board and county judge contests reach November only as a runoff of two, or when a write-in candidate has qualified
(section 105.051). A candidate one list shows on the ballot and the other does not is said in a note or a gap, never
settled here. A seat with no candidate is kept with a note; it is marked "not here yet" (a gap) when candidates of its
kind and seat number could not be placed and either its county's page shows no district of that kind, or those
candidates are at least a quarter as many as the seats of that kind and number left empty.

Not loaded: city, town and village offices (they file with city clerks; a supervisor's page shows some, without saying
which vote on November 3), ballot questions, the printed ballot order, local primaries, and names on a supervisor's
page that the Division's list does not have.

Privacy, the local part. The local download has the same contact columns as the state lists and is cut down in memory
to the same twelve; a kept cell that reads like a contact detail is emptied and counted. A supervisor's page is cut
down in memory to its office headings, candidate names, party marks and statuses (soe_cut): its campaign money columns
and its links to finance reports are never kept, and only that cut-down copy is cached (JSON, in
ballot_cache/fl/local/soe/). No candidate's name is ever used to ask a site for anything. Local candidates get no
roster link and no incumbent mark: name, office, place, party and the list's status, nothing more.

    python -m ballot.state_local_fl <path to a test database> [--refresh]
"""

import collections
import csv
import datetime as dt
import hashlib
import html as H
import io
import json
import math
import os
import re
import sqlite3
import sys
import time
import urllib.parse
import zipfile
from urllib.request import Request, urlopen

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from ballot.check_local import EXTRA_SCHEMA, contact_like  # noqa: E402
from ballot.common import CACHE, fold, name_parts, party_code  # noqa: E402
from ballot.lists.fl import (PAGE, POST, RES_DOWNLOAD, RES_HEAD, RES_TITLE, RESULTS, Blocked, ask, ballot_name,  # noqa: E402
                             pick, results_files)
from ballot.match import fits  # noqa: E402

STATE, FIPS, NAME = "FL", "12", "Florida"
GENERAL, PRIMARY = "2026-11-03", "2026-08-18"
RES_DATE = "8/18/2026"
FOLDER = os.path.join(CACHE, "fl")
ROSTER = os.path.join(HERE, "state_fl.sqlite")
CENSUS = os.path.join(HERE, "states_cache", "census")
COUNTY_ZIP = os.path.join(CENSUS, "cb_2024_us_county_500k.zip")
SLDU_ZIP = os.path.join(CENSUS, f"cb_2024_{FIPS}_sldu_500k.zip")
SLDL_ZIP = os.path.join(CENSUS, f"cb_2024_{FIPS}_sldl_500k.zip")
CENSUS_URL = "https://www2.census.gov/geo/tiger/GENZ2024/shp/"
TOTAL_COUNTIES, SENATE_SEATS, HOUSE_SEATS, CIRCUITS, DCAS = 67, 40, 120, 20, 6
AGENCY = "Florida Department of State, Division of Elections"

LISTS_FILE = "fl_2026_sl_candidate_lists.json"                  # the cut-down rows only (twelve columns)
GEN_ID, CHECK_2024 = "20261103-GEN", "20241105-GEN"
OFFICES = ("CAB", "LEG", "JUD")                                   # Governor and Cabinet; Senate and House; Judicial Offices
KEEP = ("ElectionID", "OfficeCode", "OfficeDesc", "Juris1num", "Juris2num", "StatusCode", "StatusDesc", "PartyCode", "PartyDesc",
        "NameLast", "NameFirst", "NameMiddle")
SUMMARIES = (("CAB", "REP"), ("CAB", "DEM"), ("LEG", "REP"), ("LEG", "DEM"), ("JUD", "NOP"))
SUM_FILE = "fl_2026_primary_official_summary_{race}_{party}.html"
SUM_URL = RESULTS + "/SummaryRpt.asp?ElectionDate=" + RES_DATE + "&Race={race}&Party={party}&DATAMODE="
PARTIES_URL = "https://dos.fl.gov/elections/candidates-committees/political-parties/"
PARTIES_FILE = "fl_dos_political_parties.html"
STATUTE_URL = "http://www.leg.state.fl.us/statutes/index.cfm?App_mode=Display_Statute&URL=0000-0099/{ch}/Sections/{sec}.html"
STATUTES = ("0026.021", "0035.02", "0035.03", "0035.04", "0035.042", "0035.043", "0035.044")

SRC_LISTS, SRC_RESULTS = "fl-dos-2026-sl-candidate-lists", "fl-dos-2026-sl-primary-results"
SRC_SUM = "fl-dos-2026-sl-primary-summary-{race}-{party}"
SRC_PARTIES, SRC_STATUTES = "fl-dos-political-parties", "fl-leg-statutes-courts"
SRC_ROSTER, SRC_COUNTY, SRC_SLD = "fl-openstates-roster", "fl-census-2024-county-codes", "fl-census-2024-legislative-districts"

ON_BALLOT = ("Qualified", "Unopposed")
OFF_BALLOT = ("Defeated", "Withdrew", "Did Not Qualify", "Removed", "Deceased", "Transferred to Local")
PRIMARY_PARTIES = ("REP", "DEM", "LPF", "GRE")

# the statewide offices: list office code -> (race key, office_kind, office shown, results race code, roster office)
STATEWIDE = {
    "GOV": ("GOV", "governor", "Governor", "GOV", "governor"),
    "ATG": ("AG", "attorney_general", "Attorney General", "ATG", "attorney general"),
    "CFO": ("CFO", "chief_financial_officer", "Chief Financial Officer", "CFO", None),
    "AGR": ("AGR", "agriculture_commissioner", "Commissioner of Agriculture", "AGR", None),
}
OFFICE_DESC = {"GOV": "Governor", "ATG": "Attorney General", "CFO": "Chief Financial Officer", "AGR": "Commissioner of Agriculture",
               "STS": "State Senator", "STR": "State Representative", "SCJ": "Supreme Court Justice", "DCA": "District Court of Appeal",
               "CTJ": "Circuit Judge"}
ORDINAL = {1: "First", 2: "Second", 3: "Third", 4: "Fourth", 5: "Fifth", 6: "Sixth"}
WORD_NUM = {w: i for i, w in enumerate(("first second third fourth fifth sixth seventh eighth ninth tenth eleventh twelfth thirteenth "
                                        "fourteenth fifteenth sixteenth seventeenth eighteenth nineteenth twentieth").split(), 1)}
NONPARTISAN, NP_CODE = "Nonpartisan office", "N"

# a last look before anything is written
CONTACT = re.compile(r"@|https?:|www\.|\.(?:com|org|net|gov|us)\b|\d{3}|P\.?\s?O\.?\s+Box|\bSuite\b", re.I)
CONTACT_NOTE = re.compile(r"@|https?:|www\.|\b\d{3}[-.)\s]\s?\d{3}[-.\s]\d{4}\b|\bP\.?\s?O\.?\s+Box\b|\bSuite\b|\b\d{5}(?:-\d{4})?\b", re.I)

GOV_NOTE = ("Florida elects its governor and lieutenant governor together, on one ticket; the Division's candidate list names the "
            "candidates for Governor only.")
SENATE_NOTE = ("Florida senators serve four years; the 20 even-numbered districts are elected in 2026 and the odd-numbered ones in "
               "2028 (Article III, section 15(a), Florida Constitution).")
UNOPPOSED_NOTE = "Unopposed. Florida law (section 101.151) leaves an unopposed candidate off the general election ballot."
SEAT_UNOPPOSED = "Elected without opposition: no name is printed on the November ballot for this seat."
WRITE_IN_NOTE = "Write-in candidate: the name is not printed on the ballot."
RETENTION_NOTE = ("A retention vote: voters answer Yes or No on whether this {who} stays in office for another six-year term "
                  "(Article V, section 10, Florida Constitution).")
RUNOFF_RACE_NOTE = ("No candidate won a majority in the August 18 nonpartisan election, so the two with the most votes are on the "
                    "November ballot (section 105.051, Florida Statutes).")
UNIVERSAL_NOTE = ("A universal primary: every candidate who qualified for this seat was {party}, so every voter could vote in it, "
                  "whatever their party (Article VI, section 5(b), Florida Constitution).")
NO_HOLDER = "The roster used here does not list who holds this office."


class Stop(SystemExit):
    pass


def stop(msg):
    raise Stop(f"Florida (state races): {msg}")


# ------------------------------------------------------------------------------------------------ the candidate lists

def form_elections():
    """[(elecID, label)] offered by the download form for November 3, 2026: the general election and its specials."""
    from states import net
    page = ask("the Candidate Tracking System's download form", lambda: net.get(PAGE, accept="text/html"),
               lambda d: b"extractCanList.asp" in d and b"elecID" in d).decode("cp1252", "replace")
    sel = re.search(r'(?is)<select[^>]*name="?elecID"?[^>]*>(.*?)</select>', page)
    if not sel:
        stop("the download form no longer offers a list of elections")
    opts = [(v, re.sub(r"\s+", " ", H.unescape(t)).strip())
            for v, t in re.findall(r'(?is)<option[^>]*value="?([^">]*)"?[^>]*>(.*?)</option>', sel.group(1))]
    ids = dict(opts)
    if GEN_ID not in ids or CHECK_2024 not in ids:
        stop(f"the download form no longer offers {GEN_ID} or {CHECK_2024}")
    return [(GEN_ID, ids[GEN_ID])] + sorted((v, t) for v, t in opts if re.fullmatch(r"20261103-S\d\d", v)), ids[CHECK_2024]


def cut_down(data, what):
    """The rows of one downloaded list, each cut down on the spot to the twelve columns in KEEP, found by heading. The
    download itself is never kept; nothing from the other columns is ever looked at."""
    text = data.decode("utf-8", "replace")
    rows = csv.reader(io.StringIO(text), delimiter="\t")
    head = [h.strip() for h in next(rows, [])]
    missing = [k for k in KEEP if k not in head]
    if missing:
        stop(f"{what} no longer has the column(s) {', '.join(missing)}")
    idx = [(k, head.index(k)) for k in KEEP]
    out = []
    for r in rows:
        if not any(x.strip() for x in r):
            continue
        out.append({k: (r[i].strip() if i < len(r) else "") for k, i in idx})
    del text, rows
    return out


def pull_list(elec, office):
    """(rows cut down to KEEP, SHA-256 of the file as received, its size) for one election and office."""
    from states import net
    form = {"elecID": elec, "office": office, "status": "All", "cantype": "STA"}

    def go():
        req = Request(POST, data=urllib.parse.urlencode(form).encode(), method="POST",
                      headers={"User-Agent": net.UA, "Referer": PAGE, "Content-Type": "application/x-www-form-urlencoded"})
        with urlopen(req, timeout=180) as r:
            return r.read()
    data = ask(f"the candidate list ({elec}, {office})", go, lambda d: b"NameLast" in d[:600] and b"OfficeDesc" in d[:600])
    digest, size = hashlib.sha256(data).hexdigest(), len(data)
    rows = cut_down(data, f"the candidate list ({elec}, {office})")
    del data
    return rows, digest, size


def candidate_lists(folder, say, refresh=False, max_age_days=2):
    """The cut-down lists, from the JSON cache when it is fresh; otherwise downloaded again (one request at a time)."""
    path = os.path.join(folder, LISTS_FILE)
    if not refresh and os.path.exists(path) and time.time() - os.path.getmtime(path) < max_age_days * 86400:
        got = json.load(open(path, encoding="utf-8"))
        if got.get("keep") == list(KEEP):
            return got, path
    from states import net
    net.patient_lookups()
    try:
        elections, label_2024 = form_elections()
        lists = []
        for elec, label in elections:
            for office in (OFFICES if elec == GEN_ID else ("All",)):
                time.sleep(1.0)
                rows, digest, size = pull_list(elec, office)
                lists.append({"elecID": elec, "label": label, "office": office, "sha256": digest, "bytes": size, "rows": rows})
        time.sleep(1.0)
        rows, digest, size = pull_list(CHECK_2024, "LEG")
        lists.append({"elecID": CHECK_2024, "label": label_2024, "office": "LEG", "sha256": digest, "bytes": size,
                      "rows": [{k: r[k] for k in ("ElectionID", "OfficeCode", "Juris1num", "StatusDesc")} for r in rows]})
    except Blocked as e:
        if os.path.exists(path):
            say(f"    Florida (state races): could not refresh the candidate lists ({e}); using {path}")
            return json.load(open(path, encoding="utf-8")), path
        stop(f"the candidate lists could not be had ({e}); a person can open {PAGE} in a browser, but its file carries contact "
             "columns, so it must be read by this loader and never saved whole")
    got = {"keep": list(KEEP), "fetched": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "form": PAGE, "post": POST, "lists": lists}
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(got, fh, ensure_ascii=False, indent=0)
    os.replace(tmp, path)
    return got, path


# ------------------------------------------------------------------------------------------------ the official results

def summaries(folder, say, max_age_days=30):
    """{(race, party): path} for the five Summary Reports, fetched when the cached copies are older than max_age_days."""
    from states import net
    paths = {k: os.path.join(folder, SUM_FILE.format(race=k[0].lower(), party=k[1].lower())) for k in SUMMARIES}
    have = all(os.path.exists(p) and os.path.getsize(p) > 0 for p in paths.values())
    if have and all(time.time() - os.path.getmtime(p) < max_age_days * 86400 for p in paths.values()):
        return paths
    got = {}
    try:
        for k in SUMMARIES:
            time.sleep(1.0)
            got[k] = ask(f"the {k[1]} Summary Report for {k[0]}", lambda k=k: net.get(SUM_URL.format(race=k[0], party=k[1]), accept="text/html"),
                         lambda d: f"<TITLE>{RES_TITLE}</TITLE>".encode() in d)
    except Blocked as e:
        if have:
            say(f"    Florida (state races): could not refresh the Summary Reports ({e}); using the copies in {folder}")
            return paths
        stop(f"the official Summary Reports could not be had ({e})")
    for k, data in got.items():
        open(paths[k], "wb").write(data)
    return paths


def summary(path, race, party):
    """(official?, {(race code, district, group): {"names", "totals", "pcts", "note"}}) from one Summary Report page."""
    t = open(path, "rb").read().decode("cp1252", "replace")
    if f"<TITLE>{RES_TITLE}</TITLE>" not in t:
        stop(f"{os.path.basename(path)} is not a Summary Report of the {RES_TITLE}")
    head = re.search(r'(?is)CLASS="OfficialHeading">\s*(.*?)\s*<', t)
    official = bool(head) and head.group(1).strip() == "Official Results"
    cells = lambda pat, s: [re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", x))).strip() for x in re.findall(pat, s)]
    out = {}
    for tab in re.findall(r"(?is)<TABLE[^>]*>(.*?)</TABLE>", t):
        m = re.search(r"(?i)DetailRpt\.Asp\?ELECTIONDATE=([\d/]+)&RACE=(\w+)&PARTY=(\w+)&DIST=(\d*)&GRP=(\d*)", tab)
        if not m:
            continue
        if m.group(1) != RES_DATE or m.group(3).upper() != party:
            stop(f"the {party} Summary Report for {race} lists a contest of another election or party")
        names = cells(r'(?is)CLASS="tableheaderright"[^>]*>(.*?)</TD>', tab)
        tot = re.search(r'(?is)CLASS="ColumnHeaders">\s*Total\s*</TD>(.*?)</TR>', tab)
        pct = re.search(r'(?is)CLASS="ColumnHeaders">\s*% Votes\s*</TD>(.*?)</TR>', tab)
        note = cells(r'(?is)CLASS="RunoffIndicator"[^>]*>(.*?)</td>', tab)
        totals = [int(x.replace(",", "")) for x in cells(r'(?is)CLASS="tablecellright"[^>]*>(.*?)</TD>', tot.group(1))] if tot else []
        pcts = [float(x.rstrip("%")) for x in cells(r'(?is)CLASS="tablecellright"[^>]*>(.*?)</TD>', pct.group(1))] if pct else []
        if not names or len(totals) != len(names) or len(pcts) != len(names):
            stop(f"a contest on the {party} Summary Report for {race} ({m.group(2)} {m.group(4)} {m.group(5)}) could not be read")
        key = (m.group(2).upper(), int(m.group(4) or 0), int(m.group(5) or 0))
        if key in out:
            stop(f"the {party} Summary Report for {race} lists {key} twice")
        out[key] = {"names": names, "totals": totals, "pcts": pcts, "note": " ".join(n for n in note if n)}
    return official, out


RACE_CODES = ("GOV", "ATG", "CFO", "AGR", "STS", "STR", "CTJ")
RES_COLS = ("ElectionDate", "PartyCode", "RaceCode", "CountyName", "Juris1num", "Juris2num", "Precincts", "PrecinctsReporting",
            "CanNameLast", "CanNameFirst", "CanNameMiddle", "CanVotes")


def extract(path):
    """{(race code, district, group, party code): {(last, first, middle): {"votes", "counties"}}} for the state contests
    in the results extract, and a list of the checks that failed."""
    raw = open(path, "rb").read()
    if not raw.startswith(RES_HEAD):
        stop(f"{os.path.basename(path)} is not the results extract")
    rows = csv.DictReader(io.StringIO(raw.decode("cp1252", "replace")), delimiter="\t")
    missing = [c for c in RES_COLS if c not in (rows.fieldnames or [])]
    if missing:
        stop(f"the results extract no longer has the columns {', '.join(missing)}")
    out, differ, partial, other = {}, [], set(), set()
    for r in rows:
        r = {k: (r.get(k) or "").strip() for k in RES_COLS}
        if r["RaceCode"] not in RACE_CODES:
            other.add(r["RaceCode"])
            continue
        if r["ElectionDate"] != RES_DATE:
            stop(f"a row of the results extract is dated {r['ElectionDate']!r}, not {RES_DATE}")
        key = (r["RaceCode"], int(r["Juris1num"] or 0), int(r["Juris2num"] or 0), r["PartyCode"])
        if r["Precincts"] != r["PrecinctsReporting"]:
            partial.add((key, r["CountyName"]))
        c = out.setdefault(key, {}).setdefault((r["CanNameLast"], r["CanNameFirst"], r["CanNameMiddle"]), {"votes": 0, "counties": set()})
        if r["CountyName"] in c["counties"]:
            differ.append(f"{key}: {r['CanNameFirst']} {r['CanNameLast']} has two rows for {r['CountyName']}")
        c["votes"] += int(r["CanVotes"] or 0)
        c["counties"].add(r["CountyName"])
    for key, county in sorted(partial):
        differ.append(f"{key}: not every precinct reported in {county}")
    for key, cands in out.items():
        if len({frozenset(c["counties"]) for c in cands.values()}) != 1:
            differ.append(f"{key}: the candidates are not listed for the same counties")
        if key[0] in ("GOV", "ATG", "CFO", "AGR") and any(len(c["counties"]) != TOTAL_COUNTIES for c in cands.values()):
            differ.append(f"{key}: a candidate is not listed for all {TOTAL_COUNTIES} counties")
    return out, differ, other


# ------------------------------------------------------------------------------------------------ parties, statutes

def cached_page(path, url, valid, what, say, max_age_days=30):
    from states import net
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < max_age_days * 86400:
        return open(path, "rb").read()
    try:
        data = ask(what, lambda: net.get(url, accept="text/html"), valid)
    except Blocked as e:
        if os.path.exists(path):
            say(f"    Florida (state races): could not refresh {what} ({e}); using {path}")
            return open(path, "rb").read()
        stop(f"{what} could not be had ({e})")
    open(path, "wb").write(data)
    time.sleep(1.0)
    return data


def party_names(folder, say):
    """{code: name} from the Division's list of political parties (major and minor, current and ended)."""
    path = os.path.join(folder, PARTIES_FILE)
    data = cached_page(path, PARTIES_URL, lambda d: b"Minor Political Parties" in d, "the Division's list of political parties", say)
    out = {}
    for li in re.findall(r"(?is)<li[^>]*>(.*?)</li>", data.decode("utf-8", "replace")):
        t = re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", li))).strip()
        m = re.fullmatch(r"(.+?)\s*\(([A-Z]{3})\)", t)
        if m:
            out.setdefault(m.group(2), m.group(1).strip())
    for code, want in (("REP", "Republican Party of Florida"), ("DEM", "Florida Democratic Party")):
        if out.get(code) != want:
            stop(f"the Division's list of political parties no longer reads {want} ({code})")
    return out, path


def statutes(folder, say, county_names):
    """({circuit: {county names}}, {appellate district: [circuits]}, [paths]) from the Florida Statutes."""
    os.makedirs(os.path.join(folder, "statutes"), exist_ok=True)
    texts, paths = {}, []
    for sec in STATUTES:
        url = STATUTE_URL.format(ch=sec.split(".")[0], sec=sec)
        path = os.path.join(folder, "statutes", f"{sec}.html")
        data = cached_page(path, url, lambda d, s=sec: f"{s.lstrip('0')}&#x2003;".encode() in d or f"{s.lstrip('0')} ".encode() in d,
                           f"section {sec.lstrip('0')}, Florida Statutes", say)
        texts[sec] = re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", data.decode("utf-8", "replace"))))
        paths.append((sec, url, path))
    circuits = {}
    for n, body in re.findall(r"\((\d{1,2})\)\s*The \w+ circuit is composed of (.*?) Count(?:y|ies)\.", texts["0026.021"]):
        names = [x.strip() for x in re.split(r",\s*(?:and\s+)?|\s+and\s+", body) if x.strip()]
        circuits[int(n)] = set(names)
    if sorted(circuits) != list(range(1, CIRCUITS + 1)):
        stop("section 26.021 could not be read as twenty circuits")
    named = [c for s in circuits.values() for c in s]
    key = lambda s: re.sub(r"[^a-z]", "", s.lower())
    if len(named) != TOTAL_COUNTIES or {key(c) for c in named} != {key(c) for c in county_names}:
        stop("section 26.021 does not name each of Florida's 67 counties exactly once")
    dcas = {}
    for sec in STATUTES[1:]:
        m = re.search(r"The (\w+) Appellate District is composed of the (.*?) Judicial Circuits?\.", texts[sec])
        if not m or m.group(1).lower() not in WORD_NUM:
            stop(f"section {sec.lstrip('0')} could not be read")
        words = [w.lower() for w in re.split(r",\s*(?:and\s+)?|\s+and\s+", m.group(2)) if w.strip()]
        if any(w not in WORD_NUM for w in words):
            stop(f"section {sec.lstrip('0')} names a circuit this loader cannot read")
        dcas[WORD_NUM[m.group(1).lower()]] = sorted(WORD_NUM[w] for w in words)
    got = sorted(c for v in dcas.values() for c in v)
    if sorted(dcas) != list(range(1, DCAS + 1)) or got != list(range(1, CIRCUITS + 1)):
        stop("sections 35.02 to 35.044 do not place each of the twenty circuits in exactly one of six appellate districts")
    return circuits, dcas, paths


# ------------------------------------------------------------------------------------------------ places

def county_key(text):
    return re.sub(r"[^a-z]", "", re.sub(r"\s+County$", "", str(text or "").strip(), flags=re.I).lower())


def read_shapes(path, keyf):
    import shapefile                                                     # pyshp, in the kit's environment
    z = zipfile.ZipFile(path)
    part = lambda ext: io.BytesIO(z.read(next(n for n in z.namelist() if n.endswith(ext))))
    r = shapefile.Reader(shp=part(".shp"), dbf=part(".dbf"), shx=part(".shx"))
    out = {}
    for sr in r.iterShapeRecords():
        rec = sr.record.as_dict()
        if rec["STATEFP"] != FIPS:
            continue
        pts, parts = sr.shape.points, list(sr.shape.parts) + [len(sr.shape.points)]
        out[keyf(rec)] = [pts[parts[i]:parts[i + 1]] for i in range(len(parts) - 1)]
    return out


def district_reach(county_shapes, districts, res=0.002, edge=5, least=25):
    """{district: {county GEOID: interior cells}}: each district laid over the counties on a grid of res degrees of
    latitude (about 220 m), the counties' own boundaries drawn edge cells wide and not counted (so the slivers two
    generalised files leave along a shared line fall away), and a county kept when at least `least` cells of it lie
    inside the district."""
    from PIL import Image, ImageDraw
    keys = sorted(county_shapes)
    pts = [p for rings in county_shapes.values() for ring in rings for p in ring]
    lon0, lon1 = min(p[0] for p in pts), max(p[0] for p in pts)
    lat0, lat1 = min(p[1] for p in pts), max(p[1] for p in pts)
    k = math.cos(math.radians((lat0 + lat1) / 2))
    W, Ht = int((lon1 - lon0) * k / res) + 3, int((lat1 - lat0) / res) + 3
    xy = lambda p: ((p[0] - lon0) * k / res + 1, (lat1 - p[1]) / res + 1)
    img = Image.new("L", (W, Ht), 0)
    d = ImageDraw.Draw(img)
    for i, key in enumerate(keys):
        for ring in county_shapes[key]:
            d.polygon([xy(p) for p in ring], fill=i + 1)
    for key in keys:
        for ring in county_shapes[key]:
            d.line([xy(p) for p in ring] + [xy(ring[0])], fill=0, width=edge)
    out = {}
    for n, rings in districts.items():
        q = [xy(p) for ring in rings for p in ring]
        x0, y0 = int(min(a for a, _b in q)) - 1, int(min(b for _a, b in q)) - 1
        x1, y1 = int(max(a for a, _b in q)) + 2, int(max(b for _a, b in q)) + 2
        mask = Image.new("L", (x1 - x0, y1 - y0), 0)
        md = ImageDraw.Draw(mask)
        for ring in rings:
            md.polygon([(a - x0, b - y0) for a, b in (xy(p) for p in ring)], fill=255)
        h = img.crop((x0, y0, x1, y1)).histogram(mask=mask)
        out[n] = {keys[i - 1]: h[i] for i in range(1, len(keys) + 1) if h[i] >= least}
    return out


# ------------------------------------------------------------------------------------------------ the roster

def roster(path):
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
    """The same family name and a given name that fits; both sides must carry a given name."""
    cand = name_parts(name)
    return bool(cand[0]) and any(fits(cand, f) for f in forms(p) if f[0])


OFFICIAL_WORDS = {"governor": "Governor", "lt_governor": "Lieutenant Governor", "attorney general": "Attorney General",
                  "secretary of state": "Secretary of State"}


def where(p):
    if p.get("office"):
        return f"as {OFFICIAL_WORDS.get(p['office'], p['office'])}"
    return f"in the Florida {'Senate' if p['chamber'] == 'Senate' else 'House'}, District {int(p['district'])}"


# ------------------------------------------------------------------------------------------------ helpers

def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def mtime(path):
    return dt.datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d")


def shown_name(r):
    return " ".join(x for x in (r["NameFirst"], r["NameMiddle"], r["NameLast"]) if x)


def family_key(r):
    fam = name_parts(f"{r['NameFirst']} {r['NameLast']}")[1]
    return re.sub(r"[^A-Z]", "", fam.upper())


def ordinal(n):
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


# ================================================================ the county and local part
# (see the docstring: the Division's local list for who is running, each county supervisor's own page for where, the
# Secretary of State's notices of the general election for what is to be filled)

LOCAL_LISTS_FILE = "fl_2026_local_candidate_lists.json"
LOCAL_PULLS = (("local", "All", "LOC"), ("districts", "SPD", "STA"), ("circuit", "ATT", "STA"))      # (what, office, type) on the download form
NOTICE_INDEX = "https://dos.fl.gov/elections/for-voters/notices-of-general-election/"
NOTICE_HOST = "https://dos.fl.gov"
NOTICE_LINK = re.compile(r'(?i)href\s*=\s*["\'](/media/\d+/2026_nge_([a-z]{3})_english\.pdf(?:\?v=[\d.]+)?)["\']')
SOE_PAGE = "https://www.voterfocus.com/CampaignFinance/candidate_pr.php"

SRC_LOCAL, SRC_SPD, SRC_ATT = "fl-dos-2026-local-candidate-list", "fl-dos-2026-district-candidate-list", "fl-dos-2026-circuit-candidate-list"
SRC_NGE_INDEX, SRC_NGE, SRC_SOE = "fl-dos-2026-nge-index", "fl-dos-2026-nge-{code}", "fl-soe-{code}-2026-candidates"
LOCAL_LEVELS = ("county", "soil_water", "city", "township", "school", "hospital", "other")
OFF_LOCAL = ("Defeated", "Withdrew", "Did Not Qualify", "Deceased", "Removed", "Transferred to Local")
COUNTY_CODES = ("BCC", "SCB", "COJ", "COC", "SOE", "TAX", "COF")

ELECTED_NOTE = ("Unopposed in November: the others who ran for this seat are marked as defeated on the Division's list, after the August 18 "
                "election. Florida law (section 101.151) leaves an unopposed candidate off the general election ballot.")
SEAT_ELECTED = ("Settled before November: the Division's list marks one candidate as unopposed and the others as defeated after the August 18 "
                "election, so no name is printed on the November ballot for this seat.")
NOT_ON_NOTICE = "On the county supervisor's candidate list, but not on the Secretary of State's notice of the general election."


class LocalStop(SystemExit):
    pass


def lstop(msg):
    raise LocalStop(f"Florida (county and local races): {msg}")


# ---------------------------------------------------------------- the Division's lists

def pull(elec, office, cantype):
    """(rows cut down to KEEP, SHA-256 of the file as received, its size, how its letters were read) for one election,
    office group and type. The Division's file writes an accented letter (an n with a tilde, an e with an accent) as one
    Windows-1252 byte, which is not UTF-8: such a file is read as Windows-1252, so the letter is kept, before cut_down
    sees it."""
    from states import net
    form = {"elecID": elec, "office": office, "status": "All", "cantype": cantype}

    def go():
        req = Request(POST, data=urllib.parse.urlencode(form).encode(), method="POST",
                      headers={"User-Agent": net.UA, "Referer": PAGE, "Content-Type": "application/x-www-form-urlencoded"})
        with urlopen(req, timeout=180) as r:
            return r.read()
    what = f"the candidate list ({elec}, {office}, {cantype})"
    data = ask(what, go, lambda d: b"NameLast" in d[:600] and b"OfficeDesc" in d[:600])
    digest, size = hashlib.sha256(data).hexdigest(), len(data)
    try:
        data.decode("utf-8")
        letters = "utf-8"
    except UnicodeDecodeError:
        data, letters = data.decode("cp1252", "replace").encode("utf-8"), "windows-1252"
    rows = cut_down(data, what)
    del data
    return rows, digest, size, letters


def clean_cells(rows):
    """A kept cell that reads like a contact detail (typed into the wrong column), or holds a letter that could not be
    read, is emptied on the spot and counted, never shown. Returns how many cells were emptied."""
    n = 0
    for r in rows:
        for k in ("OfficeDesc", "Juris1num", "Juris2num", "PartyDesc", "NameLast", "NameFirst", "NameMiddle"):
            if r.get(k) and (contact_like(r[k], True) or "�" in r[k] or (k.startswith("Name") and CONTACT.search(r[k]))):
                r[k] = ""
                n += 1
    return n


def local_lists(folder, say, refresh=False, max_age_days=2):
    """The Division's lists the local part reads, cut down to KEEP and cached as JSON: local candidates (every county
    office and single-county district), the multi-county special districts and the state attorneys and public defenders."""
    from states import net
    path = os.path.join(folder, LOCAL_LISTS_FILE)
    if not refresh and os.path.exists(path) and time.time() - os.path.getmtime(path) < max_age_days * 86400:
        got = json.load(open(path, encoding="utf-8"))
        if got.get("keep") == list(KEEP) and [x["what"] for x in got.get("lists", [])] == [w for w, _o, _t in LOCAL_PULLS] \
                and all(x.get("letters") for x in got["lists"]):
            return got, path
    net.patient_lookups()
    try:
        lists = []
        for what, office, cantype in LOCAL_PULLS:
            time.sleep(1.0)
            rows, digest, size, letters = pull(GEN_ID, office, cantype)
            emptied = clean_cells(rows)
            lists.append({"what": what, "elecID": GEN_ID, "office": office, "type": cantype, "sha256": digest, "bytes": size, "letters": letters,
                          "emptied": emptied, "rows": rows})
    except Blocked as e:
        if os.path.exists(path):
            say(f"    Florida (county and local races): could not refresh the Division's lists ({e}); using {path}")
            return json.load(open(path, encoding="utf-8")), path
        lstop(f"the Division's local candidate list could not be had ({e}); it carries contact columns, so it is read only by this loader and "
              "never saved whole")
    got = {"keep": list(KEEP), "fetched": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "form": PAGE, "post": POST, "lists": lists}
    os.makedirs(folder, exist_ok=True)
    with open(path + ".tmp", "w", encoding="utf-8") as fh:
        json.dump(got, fh, ensure_ascii=False, indent=0)
    os.replace(path + ".tmp", path)
    return got, path


# ---------------------------------------------------------------- the notices of the general election

def notice_set(folder, say, refresh=False, max_age_days=7):
    """{"index": {...}, "notices": {code: {"url", "file", "sha256", "bytes", "fetched"}}}: the English notice of each of
    the 67 counties, as linked from the Division's page. The notices name offices only (no candidate, no contact detail),
    so the files are kept as published. A notice is downloaded again only when its address on the page has changed."""
    from states import net
    nd = os.path.join(folder, "notices")
    os.makedirs(nd, exist_ok=True)
    mpath = os.path.join(nd, "manifest.json")
    old = json.load(open(mpath, encoding="utf-8")) if os.path.exists(mpath) else None
    have = bool(old) and len(old.get("notices", {})) == 67 and all(os.path.exists(os.path.join(nd, v["file"])) for v in old["notices"].values())
    if have and not refresh and time.time() - os.path.getmtime(mpath) < max_age_days * 86400:
        return old, nd
    try:
        net.patient_lookups()
        raw = ask("the Division's Notices of General Election page", lambda: net.get(NOTICE_INDEX, accept="text/html"),
                  lambda d: b"2026_nge_" in d)
        links = {}
        for href, code in NOTICE_LINK.findall(raw.decode("utf-8", "replace")):
            links.setdefault(code.lower(), set()).add(H.unescape(href))
        if len(links) != 67 or any(len(v) != 1 for v in links.values()):
            raise Blocked(f"the Notices of General Election page links {len(links)} counties' English notices, not one for each of 67")
        notices = {}
        for code in sorted(links):
            url = NOTICE_HOST + next(iter(links[code]))
            name = f"2026_nge_{code}_english.pdf"
            was = (old or {}).get("notices", {}).get(code)
            if was and was["url"] == url and os.path.exists(os.path.join(nd, name)):
                notices[code] = was
                continue
            time.sleep(1.0)
            data = ask(f"the notice for {code.upper()}", lambda u=url: net.get(u), lambda d: d.startswith(b"%PDF"))
            with open(os.path.join(nd, name), "wb") as fh:
                fh.write(data)
            notices[code] = {"url": url, "file": name, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data),
                             "fetched": dt.date.today().isoformat()}
    except Blocked as e:
        if have:
            say(f"    Florida (county and local races): could not read the Notices of General Election page again ({e}); using the notices in {nd}")
            return old, nd
        lstop(f"the notices of the general election could not be had ({e})")
    got = {"index": {"url": NOTICE_INDEX, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw), "read": dt.date.today().isoformat()},
           "notices": notices}
    with open(mpath + ".tmp", "w", encoding="utf-8") as fh:
        json.dump(got, fh, indent=1)
    os.replace(mpath + ".tmp", mpath)
    return got, nd


MONTHS = {m: i for i, m in enumerate("January February March April May June July August September October November December".split(), 1)}


def read_notice(path):
    """{"county", "amended", "given", "entries": [(line number, text)]} from one notice: the lines between "to fill the
    following offices:" and the Secretary's "GIVEN under my hand", a line that runs on to the next joined to it."""
    from ballot import pdftext
    county, amended, given, entries, last, body, tail = None, False, None, [], None, False, ""
    for n, (page, y, text) in enumerate(pdftext.lines(path), start=1):
        t = re.sub(r"\s+", " ", text).strip()
        if not t or re.fullmatch(r"Page \d+ of \d+", t):
            continue
        if t == "**OFFICIAL**":
            body = False
            continue
        if "NOTICE OF GENERAL ELECTION" in t:
            amended = amended or t.startswith("AMENDED")
            continue
        m = re.search(r"will be held in (.+?) County", t)
        if m:
            county = m.group(1)
        if t.endswith("to fill the following offices:"):
            body, last = True, None
            continue
        if t.startswith("GIVEN under my hand"):
            body, tail = False, t
            continue
        if not body:
            if tail and not given:
                tail += " " + t
                m = re.search(r"this (\d+)(?:st|nd|rd|th) day of (\w+) A\.D\. of (\d{4})", tail)
                if m and m.group(2) in MONTHS:
                    given = f"{int(m.group(3)):04d}-{MONTHS[m.group(2)]:02d}-{int(m.group(1)):02d}"
            continue
        if last and last[0] == page and last[1] - y < 18 and entries:
            entries[-1] = (entries[-1][0], entries[-1][1] + " " + t)
        else:
            entries.append((n, t))
        last = (page, y)
    return {"county": county, "amended": amended, "given": given, "entries": entries}


STATE_LINE = re.compile(r"^(United States Senator|Representative in Congress|Florida Cabinet|State Senator|State Representative|Circuit Judge|"
                        r"State Attorney|Public Defender|Justice of the Supreme Court|Judge of the District Court of Appeal|"
                        r"District Court of Appeal)\b")
COUNTY_OFFICES = {            # the notice's words -> (Division office code, level, office_kind, office as shown)
    "County Commissioner": ("BCC", "county", "county_commissioner", "County Commissioner"),
    "County Council": ("BCC", "county", "county_council", "County Council Member"),
    "School Board": ("SCB", "school", "school_board", "School Board Member"),
    "County Judge": ("COJ", "court", "county_court", "County Judge"),
    "Clerk of the Circuit Court": ("COC", "county", "clerk_of_court", "Clerk of the Circuit Court"),
    "Clerk of the Circuit Court and Comptroller": ("COC", "county", "clerk_of_court", "Clerk of the Circuit Court and Comptroller"),
    "Supervisor of Elections": ("SOE", "county", "supervisor_of_elections", "Supervisor of Elections"),
    "Tax Collector": ("TAX", "county", "tax_collector", "Tax Collector"),
    # offices filled in presidential years; a notice names one only to fill a vacancy. The Division's code for each was not
    # seen, so none is given: such a contest is kept from the notice, and its candidates wait (a gap) until the code is known
    "Property Appraiser": ("(property appraiser)", "county", "property_appraiser", "Property Appraiser"),
    "Sheriff": ("(sheriff)", "county", "sheriff", "Sheriff"),
    "Superintendent of Schools": ("(superintendent)", "school", "school_superintendent", "Superintendent of Schools"),
    "County Attorney": ("COF", "county", "county_attorney", "County Attorney"),
    "County Mayor": ("COF", "county", "county_executive", "County Mayor"),
}
NUMS = r"(\d+(?:, \d+)*(?:,? and \d+)?)"
TERRITORY = r"(?:North|South|East|West|Central|Northeast|Northwest|Southeast|Southwest)(?: Territory)?|Group [A-Z]"


def items_of(rest):
    """The contests one line of a notice names, from the words after the colon: [{"district", "seat", "num", "tag",
    "choose"}]; None when the wording is one this loader has no rule for."""
    t = rest.strip()
    nums = lambda s: [int(n) for n in re.findall(r"\d+", s)]
    it = lambda district=None, seat=None, num=None, tag="", choose=1: dict(district=district, seat=seat, num=num, tag=tag, choose=choose)
    if not t:
        return [it()]
    m = re.fullmatch(r"(\d+) Members?", t)
    if m:
        return [it(choose=int(m.group(1)))]
    m = re.fullmatch(rf"Districts? {NUMS}", t)
    if m:
        return [it(district=str(n), num=n) for n in nums(m.group(1))]
    m = re.fullmatch(rf"Seats? {NUMS}", t)
    if m:
        return [it(seat=str(n), num=n) for n in nums(m.group(1))]
    m = re.fullmatch(rf"Groups? {NUMS}", t)
    if m:
        return [it(seat=f"Group {n}", num=n) for n in nums(m.group(1))]
    m = re.fullmatch(rf"(Zone|Area)s? {NUMS}", t)
    if m:
        return [it(district=f"{m.group(1)} {n}", num=n) for n in nums(m.group(2))]
    m = re.fullmatch(rf"({TERRITORY}) Seats? {NUMS}", t)
    if m:
        return [it(district=m.group(1), seat=str(n), num=n, tag=m.group(1)) for n in nums(m.group(2))]
    m = re.fullmatch(r"Districts ((?:\d+, )+)and (At Large|Chairman)(?:, (Group|District) (\d+))?", t)
    if m:
        out = [it(district=str(n), num=n) for n in nums(m.group(1))]
        if m.group(2) == "Chairman":
            out.append(it(seat="Chairman", tag="CHR"))
        elif not m.group(3):
            out.append(it(seat="At Large", tag="ATL"))
        elif m.group(3) == "Group":
            out.append(it(district="At Large", seat=f"Group {int(m.group(4))}", num=int(m.group(4)), tag="ATL"))
        else:
            out.append(it(district=str(int(m.group(4))), seat="At Large", num=int(m.group(4)), tag="ATL"))
        return out
    return None


def district_kind(head):
    """(level, office_kind, office as shown, letter of the place id) for a district as a notice names it."""
    h = head.lower()
    if "soil and water conservation" in h:
        return "soil_water", "soil_water", "Soil and Water Conservation District Supervisor", "X"
    if "hospital" in h:
        return "hospital", "hospital_board", "Hospital Board Member", "H"
    if re.search(r"community development district|\bcdd\b", h):
        return "other", "community_development_board", "Community Development District Supervisor", "X"
    if "fire" in h:
        return "other", "fire_board", "Fire District Board Member", "X"
    if "mosquito" in h:
        return "other", "mosquito_control_board", "Mosquito Control District Board Member", "X"
    if "airport" in h:
        return "other", "airport_board", "Airport Authority Member", "X"
    if re.search(r"port authority|^port of [\w ]+ district$|\bport,", h) and not re.search(r"improvement|development|recreation", h):
        return "other", "port_board", "Port Board Member", "X"
    if "library" in h:
        return "other", "library_board", "Library District Board Member", "X"
    if re.search(r"water control|drainage|water district|water and sewer|wastewater|environmental control", h):
        return "other", "water_board", "Water District Board Member", "X"
    if "utilit" in h:
        return "other", "utility_board", "Utility Board Member", "X"
    return "other", "special_district_board", "Board Member", "X"      # improvement, stewardship, recreation, dependent and other districts


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", re.sub(r"['’]", "", (text or "").lower())).strip("-")


# ---------------------------------------------------------------- matching a supervisor's wording to a notice's name

ABBR = {"dist": "district", "dst": "district", "distr": "district", "cdd": "community development district", "ccd": "community development district",
        "comm": "community", "dev": "development", "devel": "development", "rd": "road", "co": "county", "cnty": "county", "grp": "group",
        "spec": "special", "cont": "control", "res": "rescue", "prot": "protection", "cons": "conservation", "conserv": "conservation",
        "mosq": "mosquito", "st": "saint", "bd": "board", "sch": "school", "crt": "court", "ft": "fort", "fd": "fire district",
        "sd": "special district",
        "n": "north", "s": "south", "e": "east", "w": "west", "ne": "northeast", "nw": "northwest",
        "i": "1", "ii": "2", "iii": "3", "iv": "4", "v": "5", "vi": "6", "no": "", "number": ""}
STOP_WORDS = {"the", "of", "at", "and", "a", "in", "on", "office", "member", "members", "supervisor", "supervisors", "seat", "board", "trustee",
              "trustees", "commissioner", "commissioners", "commission", "inc"}
KIND_WORDS = {"district", "community", "development", "authority", "special", "dependent", "independent", "tax", "county", "control", "fire",
              "rescue", "protection", "service", "services", "soil", "water", "conservation", "mosquito", "improvement", "hospital", "public",
              "airport", "port", "library", "recreation", "maintenance", "stewardship", "municipal", "utility", "prevention", "treatment",
              "emergency", "medical", "benefit", "facilities", "common", "management"}
LOOSE_KIND = {"special", "district", "authority", "dependent", "independent"}      # a supervisor's loose word for the kind of district
TERR_PAT = {"Northeast": r"\b(?:NE|Northeast(?:ern)?)\b", "Northwest": r"\b(?:NW|Northwest(?:ern)?)\b", "Southeast": r"\b(?:SE|Southeast(?:ern)?)\b",
            "Southwest": r"\b(?:SW|Southwest(?:ern)?)\b", "Central": r"\bCentral\b", "North": r"\bNorth(?:ern)?\b", "South": r"\bSouth(?:ern)?\b",
            "East": r"\bEast(?:ern)?\b", "West": r"\bWest(?:ern)?\b"}
TERR_CODE = {"Northeast": "NET", "Northwest": "NWT", "Central": "CEN", "North": "NRT", "South": "STH"}      # the Division's own codes for them


def toks(text):
    t = text.lower().replace("&", " and ").replace("/", " ").replace("#", " ")
    t = re.sub(r"['’.]", "", t)
    out = []
    for w in re.sub(r"[^a-z0-9]+", " ", t).split():
        out += ABBR[w].split() if w in ABBR else [w]
    return [w for w in out if w not in STOP_WORDS]


def explain(s_toks, n_toks):
    """How a supervisor's wording fits the name a notice gives a district: None when it does not, else (inexact, left):
    how many of its words fit only loosely, and how many of the notice's own distinctive words it leaves unsaid. Each of
    the supervisor's words must be a word of the notice's name, two words run together or one word split in two, the
    same word with or without a final s, or (for a kind word such as "conservation") its beginning."""
    left, s, i, loose = list(n_toks), list(s_toks), 0, 0
    while i < len(s):
        w = s[i]
        if w in left:
            left.remove(w)
            i += 1
            continue
        if i + 1 < len(s) and (w + s[i + 1]) in left:                                      # "village walk" for "villagewalk"
            left.remove(w + s[i + 1])
            i, loose = i + 2, loose + 1
            continue
        run = [(k, n) for k in range(len(left)) for n in (2, 3) if len(w) >= 6 and w == "".join(left[k:k + n])]      # "crosscreek" for "cross creek"
        if run:
            del left[run[0][0]:run[0][0] + run[0][1]]
            i, loose = i + 1, loose + 1
            continue
        plural = [x for x in left if len(w) >= 4 and (x == w + "s" or w == x + "s")]
        if plural:
            left.remove(plural[0])
            i, loose = i + 1, loose + 1
            continue
        pre = [x for x in left if x in KIND_WORDS and len(w) >= 4 and x.startswith(w)]
        if pre:
            left.remove(pre[0])
            i, loose = i + 1, loose + 1
            continue
        if w == "1" or w in LOOSE_KIND:                 # "Brooks I" where the notice numbers only the second; "SD" for a district the notice
            i, loose = i + 1, loose + 1                 # calls by its full kind
            continue
        return None
    return loose, sum(1 for x in left if x not in KIND_WORDS)


def spellings(wording, name):
    """The supervisor's wording as it is, and with each run of capitals that is the initials of words in a row in the
    notice's name spelled out ("ECUA", "VCDD 4", "Northern PBC")."""
    words = re.sub(r"[^A-Za-z0-9 ]", " ", name.replace("&", " and ")).split()
    cores = [w for w in words if w.lower() not in ("of", "and", "the", "at")]
    out = [wording]
    for m in re.finditer(r"\b[A-Z]{2,6}\b", wording):
        a = m.group(0)
        for k in range(len(cores) - len(a) + 1):
            if "".join(w[0].upper() for w in cores[k:k + len(a)]) == a:
                out.append(wording[:m.start()] + " ".join(cores[k:k + len(a)]) + wording[m.end():])
    return out


TERM_NOTE = re.compile(r"\(\s*(\d+)\s*-?\s*(?:yr|year)s?\.?\s*term\s*\)", re.I)


def clean_office(office):
    """A supervisor's office heading without the page's own label, a note in brackets at its end and words about the
    election."""
    t = re.sub(r"^Office:\s*", "", office or "").strip()
    t = re.sub(r"(\s*\([^()]*\))+\s*$", "", t)                      # "(2-yr term)", "(NO LONGER ON BALLOT-APPTMT)"
    t = re.sub(r"\s*-\s*Gen(eral)?\.?\s*Election Only\s*$", "", t, flags=re.I)
    t = re.sub(r"\s*-\s*(At Large|Single M\w*|Single Member|AT LRG)\s*$", "", t, flags=re.I)
    return t.strip(" ,-")


def strip_seat(office):
    """(the name part, the seat number or letter or None) of a supervisor's office heading."""
    t = clean_office(office)
    m = re.search(r"[\s,-]*(?:\b(?:Seat|Group|Grp|District|Dist|Dst|Zone|Area|Pct|Ward)\b\.?\s*#?\s*)?0*(\d+)\s*$", t, flags=re.I)
    if m and m.start() > 0:
        return t[:m.start()].strip(" ,-"), int(m.group(1))
    m = re.search(r"[\s,-]+(?:Seat|Group)\s+([A-Z])\s*$", t)
    if m:
        return t[:m.start()].strip(" ,-"), m.group(1)
    return t, None


def bracket_forms(name):
    """A district's name as a supervisor words it, with what its brackets hold kept and left out: "Islands at Doral (SW)
    CDD" names the district, "Greater Naples FD (E Naples Division)" adds a note."""
    kept = re.sub(r"[()]", " ", name)
    cut = re.sub(r"\s*\([^()]*\)", " ", name)
    return [kept] if kept.split() == cut.split() else [kept, cut]


# ---------------------------------------------------------------- the county supervisors' pages

SOE_NOT_CANDIDATES = re.compile(r"committee|part(y|ies)\b|executive|municipal|recall|special|office accounts|rep reports|\bclub\b|\bPAC\b|\bECO\b|"
                                r"^(city|town|village) of\b|\b2028\b", re.I)
SOE_SPECIAL = re.compile(r"\bspecial\b.*\(11/3/2026\)\s*$", re.I)
SOE_NOT_SPECIAL = re.compile(r"committee|part(y|ies)\b|executive|recall|\bclub\b", re.I)
PARTY_MARK = re.compile(r"\s*\(\s*([A-Za-z/]{2,4})\s*\)\s*$")
cell_text = lambda s: re.sub(r"\s+", " ", H.unescape(re.sub(r"(?s)<[^>]+>", " ", s))).strip()


def soe_groups(page):
    """[(value, selected?, label)] of the reporting groups a supervisor's page offers."""
    sel = re.search(r"(?is)<select[^>]*name=[\"']?el[\"']?[^>]*>(.*?)</select>", page)
    out = []
    for attrs, label in re.findall(r"(?is)<option([^>]*)>(.*?)</option>", sel.group(1) if sel else ""):
        v = re.search(r"value\s*=\s*['\"]?([^'\"\s>]+)", attrs)
        out.append((v.group(1) if v else "", bool(re.search(r"\bselected\b", attrs, re.I)), cell_text(label)))
    return out


def soe_cut(page):
    """A supervisor's page cut down, in memory, to what is kept: each office heading and, under it, each candidate's
    name (the party mark beside it set apart) and status. The page's money columns and links are never looked at.
    Returns (groups, how many kept cells were emptied because they read like contact details)."""
    groups, emptied = [], 0
    for g in re.split(r'(?i)<div class="col-xs-12 officegroup">', page)[1:]:
        m = re.search(r'(?is)class="col-xs-12 officename"[^>]*>(.*?)</div>', g)
        office = cell_text(m.group(1)) if m else ""
        if contact_like(office, True):
            office, emptied = "", emptied + 1
        cands = []
        for r in re.split(r'(?i)<div class="col-xs-12 detailrow candidate', g)[1:]:
            nm = re.search(r'(?is)class="col-xs-7 no-gutter bold cf_indent"[^>]*>(.*?)</div>', r)
            st = re.search(r'(?is)<span class="for-screen-reader">status</span>(.*?)<span class=.statustext[^>]*>(.*?)</span>(.*?)</div>', r)
            name = cell_text(nm.group(1)) if nm else ""
            if name and (contact_like(name, True) or CONTACT.search(name)):
                name, emptied = "", emptied + 1
            status = cell_text(st.group(2)) if st else ""
            if status == "Inactive" and st:
                status = re.sub(r"^[-\s]+|[\s)]+$", "", cell_text(st.group(3))) or status
            pm = PARTY_MARK.search(name)
            cands.append({"name": PARTY_MARK.sub("", name).strip(), "mark": pm.group(1).upper() if pm else "", "status": status})
        groups.append({"office": office, "cands": cands})
    return groups, emptied


def supervisor_pages(folder, keys, say, refresh=False, max_age_days=2):
    """{county key: the cut-down page, or None}: each county supervisor's candidate page for the 2026 election, read one
    request at a time and kept only as cut down by soe_cut (JSON). A county whose page cannot be read keeps its earlier
    copy; with none, it is None and said as a gap. A refusal from the host ends the asking for this run."""
    from states import net
    sd = os.path.join(folder, "soe")
    os.makedirs(sd, exist_ok=True)
    out, blocked = {}, None
    for key in keys:
        path = os.path.join(sd, key + ".json")
        fresh = os.path.exists(path) and time.time() - os.path.getmtime(path) < max_age_days * 86400
        if fresh and not refresh:
            out[key] = json.load(open(path, encoding="utf-8"))
            continue
        got = None
        if not blocked:
            try:
                net.patient_lookups()
                is_page = lambda d: b"officegroup" in d or b'name="el"' in d or b"name='el'" in d
                time.sleep(1.0)
                url = f"{SOE_PAGE}?c={key}"
                raw = ask(f"the {key} supervisor's candidate page", lambda u=url: net.get(u, accept="text/html"), is_page)
                page = raw.decode("utf-8", "replace")
                opts = soe_groups(page)
                chosen = [o for o in opts if o[1]]
                if not (len(chosen) == 1 and "2026" in chosen[0][2] and not SOE_NOT_CANDIDATES.search(chosen[0][2])):
                    fit = [o for o in opts if "2026" in o[2] and not SOE_NOT_CANDIDATES.search(o[2])]
                    if len(fit) != 1:
                        raise Blocked(f"the {key} supervisor's page offers {len(fit)} reporting groups for the 2026 candidates, not one")
                    time.sleep(1.0)
                    url = f"{SOE_PAGE}?el={fit[0][0]}&c={key}"
                    raw = ask(f"the {key} supervisor's candidate page", lambda u=url: net.get(u, accept="text/html"), is_page)
                    page = raw.decode("utf-8", "replace")
                    chosen = [o for o in soe_groups(page) if o[1]]
                    if len(chosen) != 1 or chosen[0][0] != fit[0][0]:
                        raise Blocked(f"the {key} supervisor's page did not answer with the reporting group asked for")
                groups, emptied = soe_cut(page)
                more = []                                 # a special election the supervisor keeps apart, for the same day
                for value, _sel, label in soe_groups(page):
                    if value != chosen[0][0] and SOE_SPECIAL.search(label) and not SOE_NOT_SPECIAL.search(label):
                        time.sleep(1.0)
                        url2 = f"{SOE_PAGE}?el={value}&c={key}"
                        raw2 = ask(f"the {key} supervisor's candidate page", lambda u=url2: net.get(u, accept="text/html"), is_page)
                        page2 = raw2.decode("utf-8", "replace")
                        if [o[0] for o in soe_groups(page2) if o[1]] != [value]:
                            raise Blocked(f"the {key} supervisor's page did not answer with the reporting group asked for")
                        groups2, emptied2 = soe_cut(page2)
                        more.append({"url": url2, "el": value, "label": label, "sha256": hashlib.sha256(raw2).hexdigest(), "bytes": len(raw2),
                                     "emptied": emptied2, "groups": groups2})
                        del page2
                del page
                got = {"county_key": key, "url": url, "el": chosen[0][0], "label": chosen[0][2], "sha256": hashlib.sha256(raw).hexdigest(),
                       "bytes": len(raw), "fetched": dt.date.today().isoformat(), "emptied": emptied, "groups": groups, "more": more}
                with open(path + ".tmp", "w", encoding="utf-8") as fh:
                    json.dump(got, fh, ensure_ascii=False, indent=0)
                os.replace(path + ".tmp", path)
            except Blocked as e:
                if "HTTP 403" in str(e) or "challenge" in str(e):
                    blocked = str(e)
                say(f"    Florida (county and local races): {e}" + ("; using the copy read earlier" if os.path.exists(path) else ""))
        out[key] = got or (json.load(open(path, encoding="utf-8")) if os.path.exists(path) else None)
    return out, sd


# ---------------------------------------------------------------- placing the list's rows

BCC_WORDS = re.compile(r"\b(?:county|co|cnty)\.?\s+(?:commission(?:er)?s?|comm\b|council)", re.I)
OFFICE_WORDS = {"BCC": BCC_WORDS, "SCB": re.compile(r"\bschool\b|\bsch\.?\s+b", re.I), "COJ": re.compile(r"\bjudge\b", re.I),
                "COC": re.compile(r"\bclerk\b", re.I), "SOE": re.compile(r"supervisor of elections", re.I), "TAX": re.compile(r"tax collector", re.I),
                "COF": re.compile(r"\bcounty (?:mayor|attorney|chair)", re.I)}
CITY_WORDS = re.compile(r"\b(?:city|town|village)\b|\bcouncil\b|\bmayor\b|\bmarshal\b|\bward\b", re.I)
DISTRICT_WORDS = re.compile(r"\bcdd\b|\bccd\b|\bcomm(?:unity|\.)?\s+dev|\bauthority\b|\b(?:improvement|fire|control|water|sewer|special|dependent|"
                            r"independent|stewardship|recreation|hospital|library|mosquito|inlet|tax|facilities|services?|management|drainage|"
                            r"erosion|conservation|park|development|utility|benefit|rescue)\s+dist", re.I)      # "district" in a district's own name,
#                                                                                                                 not a council's "District 2"
NOT_AN_OFFICE = re.compile(r"^test\b", re.I)
CODE_WORDS = {"FPD": r"fire|\bfd\b", "MCD": r"mosq", "HAD": r"hospital", "ARP": r"airport", "LIB": r"library", "PTA": r"\bport\b|inlet",
              "ERS": r"erosion"}                         # a district code whose headings always carry a word of its own
SOE_ON = ("Qualified", "Advanced", "Runoff", "Qualified Write-In", "Unopposed", "Elected")      # a supervisor's words for someone still in or elected
SOE_STILL = SOE_ON + ("Filed", "Incumbent", "")
SOE_OFF_WORDS = {"Withdrawn": "withdrawn", "Did not qualify": "not qualified", "Defeated": "defeated", "Unopposed": "unopposed",
                 "Elected": "elected"}


def office_code(wording):
    """The Division office code a supervisor's heading reads as: a county office's code, "SWD", "DST" (some other
    district) or "CITY" (a city, town or village office)."""
    t = clean_office(wording)
    cityish = bool(CITY_WORDS.search(t)) and not BCC_WORDS.search(t) and not re.search(r"\bcounty (?:mayor|judge|court)\b", t, re.I)
    if re.search(r"\bsoil\b|\bs\s*&\s*w\b", t, re.I):
        return "SWD"
    if cityish and not DISTRICT_WORDS.search(t):
        return "CITY"
    for code in ("SCB", "COJ", "SOE", "TAX", "COF", "COC", "BCC"):
        if OFFICE_WORDS[code].search(t) and not (code in ("COC", "TAX") and cityish):
            if code == "BCC" and re.search(r"school|judge|port|inlet|airport|mosquito|charter|fire|hospital|cdd|community dev", t, re.I):
                continue
            return code
    return "DST"


def office_fits(code, wording):
    got = office_code(wording)
    if code in COUNTY_CODES or code == "SWD":
        return got == code
    return got == "DST"


def seat_of(r):
    """(number or None, tag, territory code) of a row of the Division's list: Juris2num is the seat ("002", or "ATL",
    "AD6", "AT2", "CHR"); a few rows carry it in Juris1num, which otherwise holds a hospital board's territory."""
    j2, j1 = (r.get("Juris2num") or "").strip().upper(), (r.get("Juris1num") or "").strip().upper()
    if j2.isdigit():
        return int(j2), "", ("" if j1.isdigit() else j1)
    if j2:
        d = re.sub(r"\D", "", j2)
        return (int(d) if d else None), j2, ("" if j1.isdigit() else j1)
    if j1.isdigit():
        return int(j1), "", ""
    return None, "", j1


def item_fits(it, num, tag):
    if tag:
        if tag == "CHR":
            return it["tag"] == "CHR"
        return it["tag"] == "ATL" and (num is None or it["num"] is None or it["num"] == num)
    if num is not None:
        return it["num"] == num
    return it["num"] is None and not it["tag"]


def list_parts(r):
    return name_parts(f"{r['NameLast']}, {r['NameFirst']} {r['NameMiddle']}")


def place_rows(lists, nset, nd, pages, counties, say=print):
    """Reads the notices and the supervisors' pages and finds, for each row of the Division's local list, the contest it
    belongs to. Returns everything local_part builds its rows from. A contest is named by a tuple:
      ("O", county code, the notice's office, item key, special)       a county office on the notice
      ("OX", county code, office code, number, tag, special)           a county office the notice does not list
      ("D", (county code, the notice's name), item key, special)       a district seat on the notice
      ("DX", (county code, the notice's name), number, special)        a seat the notice does not list for a district it lists
      ("DN", county code, the supervisor's name for it, number, special)   a district the notice does not list"""
    count = collections.Counter()
    by_what = {x["what"]: x for x in lists["lists"]}
    local_rows, spd_rows, att_rows = by_what["local"]["rows"], by_what["districts"]["rows"], by_what["circuit"]["rows"]

    # ---- 1. the notices: each county's offices and districts
    cty, offices, dist, parent, att_lines = {}, collections.defaultdict(list), {}, {}, collections.defaultdict(set)
    for code, meta in sorted(nset["notices"].items()):
        n = read_notice(os.path.join(nd, meta["file"]))
        key = county_key(n["county"] or "")
        if key not in counties:
            lstop(f"{meta['file']} names a county the Census Bureau's county file does not have")
        geoid, name = counties[key]
        cty[code] = dict(code=code, key=key, geoid=geoid, name=name, amended=n["amended"], given=n["given"], meta=meta, contests=0,
                         page=pages.get(key))
        parsed, first_office = [], None
        for line, text in n["entries"]:
            head, _, rest = text.partition(":")
            head = re.sub(r"\s+", " ", head).strip()
            if STATE_LINE.match(head):
                m = re.fullmatch(r"Judicial Circuit (\d+)", rest.strip())
                if head in ("State Attorney", "Public Defender") and m:
                    att_lines[(head, int(m.group(1)))].add(geoid)
                continue
            items = items_of(rest)
            if items is None:
                lstop(f"line {line} of {meta['file']}: the words after the office are of a kind this loader has no rule for")
            if contact_like(head, True) or len(head) < 4:
                lstop(f"line {line} of {meta['file']}: the office's name cannot be kept as it reads")
            if head in COUNTY_OFFICES and first_office is None:
                first_office = len(parsed)
            parsed.append((line, head, items))
        if first_office is None:
            lstop(f"{meta['file']} names no county office, so its districts cannot be told from the districts of several counties")
        for i, (line, head, items) in enumerate(parsed):
            cty[code]["contests"] += len(items)
            if head in COUNTY_OFFICES:
                ocode = COUNTY_OFFICES[head][0]
                for it in items:
                    offices[(code, ocode)].append((head, (it["district"], it["seat"]), it))
                continue
            d = dist.setdefault((code, head), {"block": "multi" if i < first_office else "single", "items": {}, "line": line})
            for it in items:
                ik = (it["district"], it["seat"])
                if ik in d["items"]:
                    lstop(f"line {line} of {meta['file']}: a seat named twice")
                d["items"][ik] = it
            parent[(code, head)] = (code, head)
    if len(cty) != 67 or len({c["geoid"] for c in cty.values()}) != 67:
        lstop("the notices do not cover each of the 67 counties once")

    def find(k):
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    by_head = collections.defaultdict(list)
    for (code, head), d in dist.items():
        if d["block"] == "multi":
            by_head[head].append((code, head))
    for head, ks in by_head.items():                      # a district in the notices' first block is one district in every county that lists it
        for k in ks[1:]:
            union(ks[0], k)

    # ---- 2. the supervisors' pages: where each candidate runs
    sup_rows, sup_groups = [], {}
    for code, c in sorted(cty.items()):
        pg = c["page"]
        if not pg:
            continue
        every = [(g, 0) for g in pg["groups"]] + [(g, 1) for m in pg.get("more", []) for g in m["groups"]]
        for gi, (g, special) in enumerate(every):
            if not g["office"].startswith("Office:") or NOT_AN_OFFICE.search(clean_office(g["office"])):
                continue
            sup_groups[(code, gi)] = {"office": g["office"], "rows": [], "targets": collections.Counter(), "special": special}
            for x in g["cands"]:
                if not x["name"]:
                    count["names on supervisors' pages that could not be kept"] += 1
                    continue
                s = dict(cty=code, gi=gi, office=g["office"], name=x["name"], status=x["status"], parts=name_parts(x["name"]), claims=[],
                         special=special)
                sup_rows.append(s)
                sup_groups[(code, gi)]["rows"].append(s)
    by_fam = collections.defaultdict(list)
    for s in sup_rows:
        for w in set(s["parts"][1].split()):
            by_fam[w].append(s)

    def office_target(code, ocode, num, tag, sp=0):
        its = [(head, ik) for head, ik, it in offices.get((code, ocode), []) if item_fits(it, num, tag)]
        if not its and num is None and not tag and len(offices.get((code, ocode), [])) == 1:      # the county's one seat of this office
            its = [(h, ik) for h, ik, _it in offices[(code, ocode)]]
        return ("O", code, its[0][0], its[0][1], sp) if len(its) == 1 else None

    def district_target(code, wording, num, terr, ocode="", sp=0):
        """The district seat a supervisor's heading names, on the notice or (for a district the notice names for certain)
        beside it; None when no district of the county's notice fits, or more than one does."""
        name, _wnum = strip_seat(wording)
        fit = []
        for (c2, head), d in dist.items():
            if c2 != code:
                continue
            variants = []
            for form in bracket_forms(name):
                variants.append((form, ""))
                for tg in sorted({it["tag"] for it in d["items"].values() if it["tag"]}):
                    first = tg if tg.startswith("Group") else tg.split()[0]
                    pat = (r"\b" + re.escape(tg) + r"\b") if tg.startswith("Group") else TERR_PAT.get(first)
                    if pat and re.search(pat, form, re.I):
                        if terr and (terr != tg.split()[-1] if tg.startswith("Group") else TERR_CODE.get(first, terr) != terr):
                            continue
                        variants.append((re.sub(r"[\s,-]*" + pat + r"(?:\s+(?:District|Territory)\b)?", " ", form, count=1, flags=re.I), tg))
            best = None
            for v, tg in variants:
                for sp_ in spellings(v, head):
                    sc = explain(toks(sp_), toks(head))
                    if sc is not None and (best is None or (sc, tg == "") < best[:2]):
                        best = (sc, tg == "", tg)
            if best is None:
                continue
            tags = {it["tag"] for it in d["items"].values() if it["tag"]}
            items = [ik for ik, it in d["items"].items() if it["num"] == num and (not tags or it["tag"] == best[2])]
            fit.append((best[0], head, items))
        if not fit and ocode == "SWD":                    # "Soil & Water District 1": the county's one conservation district
            only = [(h, d) for (c2, h), d in dist.items() if c2 == code and "soil and water conservation" in h.lower()]
            if len(only) == 1:
                fit = [((0, 0), only[0][0], [ik for ik, it in only[0][1]["items"].items() if it["num"] == num])]
        if not fit:
            return None
        sure = [f for f in fit if f[0] == (0, 0)]
        pool = sure if sure else [f for f in fit if len(f[2]) == 1]
        if sure and len({f[1] for f in sure}) > 1:
            pool = [f for f in sure if len(f[2]) == 1]
        if not pool:
            return None
        low = min(f[0] for f in pool)
        top = [f for f in pool if f[0] == low]
        if len({f[1] for f in top}) != 1:
            return None
        _sc, head, items = top[0]
        if len(items) == 1:
            return ("D", (code, head), items[0], sp)
        return ("DX", (code, head), num, sp) if sure and not items else None

    norm = lambda t: (t[0], find(t[1])) + t[2:] if t and t[0] in ("D", "DX") else t

    def target_of(s, ocode, num, tag, terr):
        """(the contest a supervisor's row is in for a list row of this office and seat, the seat number used)."""
        _nm, wnum = strip_seat(s["office"])
        n_eff = num if num is not None else (wnum if isinstance(wnum, int) else None)
        sp = int(bool(TERM_NOTE.search(s["office"])))
        if ocode in COUNTY_CODES:
            t = office_target(s["cty"], ocode, n_eff, tag, sp)
            return t or ("OX", s["cty"], ocode, n_eff, tag, sp), n_eff
        t = district_target(s["cty"], s["office"], n_eff, terr, ocode, sp)
        return t or ("DN", s["cty"], district_words(strip_seat(s["office"])[0]), n_eff, sp), n_eff

    def seat_agrees(s, num):
        wnum = strip_seat(s["office"])[1]
        return num is None or not isinstance(wnum, int) or wnum == num

    # ---- 3. each row of the Division's local list: the supervisor's row with the same name, office and seat
    placed, unplaced, torn = {}, {}, {}
    statuses = {r["StatusDesc"] for r in local_rows + spd_rows + att_rows}
    if statuses - set(ON_BALLOT) - set(OFF_LOCAL):
        lstop(f"the Division's lists carry a status this loader does not know: {sorted(statuses - set(ON_BALLOT) - set(OFF_LOCAL))}")

    def take(i, hits):
        t = norm(hits[0][1])
        placed[i] = (t, [h[0] for h in hits])
        for h in hits:
            h[0]["claims"].append(i)
            sup_groups[(h[0]["cty"], h[0]["gi"])]["targets"][t] += 1

    for i, r in enumerate(local_rows):
        if r["ElectionID"] != GEN_ID:
            lstop("a row of the local list is filed under another election")
        if not r["NameLast"]:
            unplaced[i] = "the name cell could not be kept"
            continue
        num, tag, terr = seat_of(r)
        ocode = r["OfficeCode"]
        parts = list_parts(r)
        pool = {id(s): s for w in parts[1].split() for s in by_fam.get(w, [])}
        hits = []
        for s in pool.values():
            if fits(parts, s["parts"]) and office_fits(ocode, s["office"]) and seat_agrees(s, num):
                hits.append((s,) + target_of(s, ocode, num, tag, terr))
        if not hits:
            unplaced[i] = "not on a supervisor's page"
            continue
        if len({norm(h[1]) for h in hits}) > 1:
            same = [h for h in hits if h[0]["parts"][0][:1] + [h[0]["parts"][1]] == parts[0][:1] + [parts[1]]]
            backed = [h for h in (same or hits) if h[1][0] in ("O", "D")]
            hits = backed or same or hits
            ds = sorted({h[1] for h in hits if h[1][0] == "D"}, key=str)
            if len(ds) > 1 and len({(t[1][1],) + t[2:] for t in ds}) == 1 and all(dist[t[1]]["block"] == "single" for t in ds):
                for t in ds[1:]:                          # one person on two counties' pages for a district of one name and seat: one district
                    union(ds[0][1], t[1])
        if len({norm(h[1]) for h in hits}) != 1:
            unplaced[i] = "fits candidates for more than one contest"
            torn[i] = hits
            continue
        take(i, hits)

    # rows off the ballot that fit the same two contests alike (two people of one name, each lost a seat of the same number):
    # one is given to each contest, which changes nothing that is stored
    alike = collections.defaultdict(list)
    for i, hits in torn.items():
        r = local_rows[i]
        if r["StatusDesc"] not in ON_BALLOT:
            alike[(r["OfficeCode"], r["Juris1num"], r["Juris2num"], r["StatusDesc"], r["PartyCode"], frozenset(norm(h[1]) for h in hits))].append(i)
    for sig, idxs in alike.items():
        ts = sorted(sig[-1], key=str)
        if len(idxs) == len(ts):
            for i, t in zip(sorted(idxs), ts):
                del unplaced[i]
                take(i, [h for h in torn[i] if norm(h[1]) == t])
                count["rows off the ballot that fit two contests alike, one given to each"] += 1

    # a second look for a row whose given name is written differently: the family name, the office and the seat fit one
    # supervisor's row that no list row took, the given names begin alike, and the two lists do not contradict each other
    exact = collections.defaultdict(list)
    for s in sup_rows:
        if not s["claims"]:
            exact[s["parts"][1]].append(s)
    for i, why in sorted(unplaced.items()):
        r = local_rows[i]
        if why != "not on a supervisor's page":
            continue
        num, tag, terr = seat_of(r)
        ocode = r["OfficeCode"]
        parts = list_parts(r)
        on = r["StatusDesc"] in ON_BALLOT
        pool = [s for s in exact.get(parts[1], []) if not s["claims"] and office_fits(ocode, s["office"]) and strip_seat(s["office"])[1] == num
                and (ocode not in CODE_WORDS or re.search(CODE_WORDS[ocode], s["office"], re.I))
                and parts[0] and s["parts"][0] and parts[0][0][:1] == s["parts"][0][0][:1] and (not on or s["status"] in SOE_STILL)]
        if len(pool) == 1 and num is not None:
            hit = (pool[0],) + target_of(pool[0], ocode, num, tag, terr)
            if hit[1][0] in ("O", "D", "DX"):
                del unplaced[i]
                take(i, [hit])
                count["rows placed by the family name and the first letter of the given name"] += 1

    # ---- 4. the multi-county districts' candidates, from the Division's own list of them (they qualify with the Division)
    spd_placed, spd_unplaced = {}, {}
    heads = sorted({h for (_c, h), d in dist.items() if d["block"] == "multi"})
    for i, r in enumerate(spd_rows):
        num, tag, _terr = seat_of(r)
        fitting = []
        for h in heads:
            sc = explain(toks(r["OfficeDesc"]), toks(h))
            if sc is not None:
                fitting.append((sc, h))
        top = [h for sc, h in fitting if sc == min(f[0] for f in fitting)] if fitting else []
        keys = sorted(k for k in dist if k[1] == top[0]) if len(top) == 1 else []
        iks = sorted({ik for k in keys for ik, it in dist[k]["items"].items() if it["num"] == num})
        if not r["NameLast"] or len(top) != 1:
            spd_unplaced[i] = "the district is not on a notice under a name that fits"
        elif len(iks) == 1:
            spd_placed[i] = ("D", find(keys[0]), iks[0], 0)
        elif not iks:
            spd_placed[i] = ("DX", find(keys[0]), num, 0)
        else:
            spd_unplaced[i] = "the seat is named twice on the notices"
    return dict(cty=cty, offices=offices, dist=dist, find=find, placed=placed, unplaced=unplaced, sup_rows=sup_rows, sup_groups=sup_groups,
                local_rows=local_rows, spd_rows=spd_rows, att_rows=att_rows, att_lines=att_lines, norm=norm, office_target=office_target,
                district_target=district_target, count=count, spd_placed=spd_placed, spd_unplaced=spd_unplaced)


SMALL_WORDS = {"of", "at", "the", "and", "on", "in", "by"}
KEEP_CAPS = {"CDD", "II", "III", "IV", "VI", "VII", "SD", "MSBU", "MSBD", "MSD", "CID", "ISD", "FD", "NE", "NW", "SE", "SW"}


def district_words(name):
    """A district's name as a supervisor's page words it, for a district no notice names: the brackets' words kept,
    capitals set as a name is written, "CDD" spelled out. Nothing else is changed."""
    t = re.sub(r"\s+", " ", name).strip(" ,-")
    if t.isupper():
        t = " ".join(w if w in KEEP_CAPS or re.fullmatch(r"\(?[A-Z]{1,2}\)?", w) else (w.lower() if w.lower() in SMALL_WORDS else w.capitalize())
                     for w in t.split())
    t = re.sub(r"\bC[CD]D\b", "Community Development District", t)
    return re.sub(r"^(?:Supervisor|Trustee|Member),\s*", "", t)


# ---------------------------------------------------------------- the rows

EXTRA_OFFICE = {"BCC": "County Commissioner", "SCB": "School Board", "COJ": "County Judge", "COC": "Clerk of the Circuit Court",
                "SOE": "Supervisor of Elections", "TAX": "Tax Collector"}
PARTISAN_BY_LAW = ("county_commissioner", "county_council", "clerk_of_court", "supervisor_of_elections", "tax_collector", "sheriff",
                   "property_appraiser")
CODE_KINDS = {"BCC": {"county_commissioner", "county_council"}, "SCB": {"school_board"}, "COJ": {"county_court"}, "SWD": {"soil_water"},
              "FPD": {"fire_board"}, "DEV": {"community_development_board"}, "MCD": {"mosquito_control_board"}, "HAD": {"hospital_board"},
              "PTA": {"port_board"}, "ARP": {"airport_board"}, "LIB": {"library_board"}, "WCD": {"water_board"}, "COC": {"clerk_of_court"},
              "SOE": {"supervisor_of_elections"}, "TAX": {"tax_collector"}, "STD": {"special_district_board"}, "WST": {"water_board"},
              "ERS": {"special_district_board"}, "CMB": {"special_district_board", "charter_review_board"}}      # what each office code usually is
NO_CANDIDATE = "The county supervisor's page shows no candidate for this seat, and none on the Division's list could be placed here."
FACES_WRITE_IN = "The Division's list shows one candidate and a qualified write-in candidate for this seat."
NONE_QUALIFIED = "No candidate on the Division's list is marked as qualified for this seat."
MAY_BE_UNPLACED = ("The Division's list has candidates for a seat of this kind and number whose county it does not give and whose names are on no "
                   "county supervisor's page, so they could not be placed; this seat may be theirs.")
# the page's own guard for a number followed soon after by a street word; a little wider than the check's
STREETISH = re.compile(r"\b\d{1,6}\s+(?:[NSEW]\.?\s+)?[A-Za-z0-9.' -]{1,40}?\s(?:St|Street|Ave|Avenue|Rd|Road|Blvd|Boulevard|Dr|Drive|Ln|Lane|Way|"
                       r"Ct|Court|Cir|Circle|Pkwy|Parkway|Hwy|Highway|Trl|Trail|Pl|Place|Ter|Terrace)\b\.?", re.I)


def reads_like_contact(text):
    return bool(text) and (contact_like(text, True) or bool(STREETISH.search(str(text))))


def plural(n, one, many=None):
    return f"{n:,} {one if n == 1 else (many or one + 's')}"


def local_part(lists, nset, nd, pages, counties, parties, circuit_geo, say=print):
    """Florida's county, school, county court and special district contests on November 3, 2026 -> the rows to write
    (races, candidates, places, gaps, notes, sources) and the counts that reconcile them. Nothing is written here.

    counties: {county_key(name): (GEOID, name)} from the Census county file; parties: the Division's party names by
    code; circuit_geo: {circuit: [GEOID]} from section 26.021."""
    P = place_rows(lists, nset, nd, pages, counties, say)
    cty, offices, dist, find, norm = P["cty"], P["offices"], P["dist"], P["find"], P["norm"]
    rows, placed, unplaced, spd_rows = P["local_rows"], P["placed"], P["unplaced"], P["spd_rows"]
    sup_groups, count, checks, gaps = P["sup_groups"], P["count"], [], []
    by_what = {x["what"]: x for x in lists["lists"]}
    geo = {code: c["geoid"] for code, c in cty.items()}
    cname = {code: c["name"] for code, c in cty.items()}
    groups = collections.defaultdict(list)
    for k in sorted(dist):
        groups[find(k)].append(k)

    # ---- 5. the contests: every seat on a notice, then what the supervisors' pages add
    races = {}

    def district_base(key):
        root = find(key)
        mem, head = groups[root], root[1]
        m = re.fullmatch(r"(.+) County Charter Review Board", head)
        if m and len(mem) == 1 and county_key(m.group(1)) == cty[mem[0][0]]["key"]:      # a board of the county itself, listed among its districts
            code = mem[0][0]
            return dict(level="county", kind="charter_review_board", office="Charter Review Board Member", jur=f"{cname[code]} County",
                        jid=geo[code], cids=[geo[code]], pkind=None, src=SRC_NGE.format(code=code), codes=[code])
        level, kind, office, letter = district_kind(head)
        jid = f"{STATE}-{letter}-{slug(head)}" if len(mem) > 1 else f"{STATE}-{letter}-{geo[mem[0][0]][2:]}-{slug(head)}"
        return dict(level=level, kind=kind, office=office, jur=head, jid=jid, cids=sorted({geo[c] for c, _h in mem}),
                    pkind="hospital" if letter == "H" else "special", src=SRC_NGE.format(code=mem[0][0]), codes=[c for c, _h in mem])

    def office_base(code, head):
        _oc, level, kind, office = COUNTY_OFFICES[head]
        if level == "school":
            jur = f"{cname[code]} County School District"
            return dict(level=level, kind=kind, office=office, jur=jur, jid=f"{STATE}-S-{geo[code][2:]}-{slug(jur)}", cids=[geo[code]],
                        pkind="school", src=SRC_NGE.format(code=code), codes=[code])
        return dict(level=level, kind=kind, office=office, jur=f"{cname[code]} County", jid=geo[code], cids=[geo[code]], pkind=None,
                    src=SRC_NGE.format(code=code), codes=[code])

    def add(t, base, it, **kw):
        race = dict(base, target=t, district=it["district"], seat=it["seat"], choose=it["choose"], num=it["num"], special=0, on_notice=True,
                    rows=[], notes=[], sup_only=0, term=None)
        race.update(kw)
        races[t] = race
        return race

    for (code, _ocode), entries in sorted(offices.items()):
        for head, ik, it in entries:
            add(("O", code, head, ik, 0), office_base(code, head), it)
    for key in sorted(dist):
        for _ik, it in sorted(dist[key]["items"].items(), key=str):
            t = ("D", find(key), (it["district"], it["seat"]), 0)
            if t not in races:
                add(t, district_base(key), it)
    on_notice = len(races)

    def race_for(t, on, heading=""):
        """The contest a placed row belongs to; one the notices do not list is made only for a candidate still on the ballot."""
        if t in races or not on:
            return races.get(t)
        kind, sp = t[0], t[-1]
        item = lambda **kw: dict(dict(district=None, seat=None, num=None, tag="", choose=1), **kw)
        term = TERM_NOTE.search(heading or "")
        more = dict(special=sp, on_notice=False, term=int(term.group(1)) if term else None)
        if kind in ("O", "D") and sp:                     # the same seat, for another term
            base = races.get(t[:-1] + (0,))
            if base is None:
                return None
            keep = {k: base[k] for k in ("level", "kind", "office", "jur", "jid", "cids", "pkind", "src", "codes")}
            return add(t, keep, item(district=base["district"], seat=base["seat"], num=base["num"]), **more)
        if kind == "DX":
            key, num = t[1], t[2]
            sample = next(iter(dist[key]["items"].values()))
            if sample["district"] and sample["district"].isdigit() and not sample["seat"]:
                it = item(district=str(num), num=num)
            elif sample["seat"] and sample["seat"].startswith("Group "):
                it = item(seat=f"Group {num}", num=num)
            elif sample["district"] and re.match(r"(Zone|Area) \d", sample["district"]) and not sample["seat"]:
                it = item(district=f"{sample['district'].split()[0]} {num}", num=num)
            elif num is not None and not any(x["tag"] for x in dist[key]["items"].values()):
                it = item(seat=str(num), num=num)
            else:
                return None
            return add(t, district_base(key), it, **more)
        if kind == "DN":
            code, name, num = t[1], t[2], t[3]
            if len(name) < 4 or reads_like_contact(name):
                return None
            level, k2, office, letter = district_kind(name)
            base = dict(level=level, kind=k2, office=office, jur=name, jid=f"{STATE}-{letter}-{geo[code][2:]}-{slug(name)}", cids=[geo[code]],
                        pkind="hospital" if letter == "H" else "special", src=SRC_SOE.format(code=code), codes=[code])
            return add(t, base, item(seat=str(num) if num is not None else None, num=num), **more)
        if kind == "OX":
            code, ocode, num, tag = t[1], t[2], t[3], t[4]
            if ocode not in EXTRA_OFFICE or tag:
                return None
            if ocode in ("BCC", "SCB") and num is not None:
                it = item(district=str(num), num=num)
            elif ocode == "COJ" and num is not None:
                it = item(seat=f"Group {num}", num=num)
            elif num is None and ocode in ("COC", "SOE", "TAX"):
                it = item()
            else:
                return None
            return add(t, office_base(code, EXTRA_OFFICE[ocode]), it, **more)
        return None

    for i, (t, hits) in sorted(placed.items()):
        r = rows[i]
        race = race_for(norm(t), r["StatusDesc"] in ON_BALLOT, hits[0]["office"])
        if race is None:
            if r["StatusDesc"] in ON_BALLOT:
                unplaced[i] = "on a supervisor's page under an office the notices do not list and this loader cannot name"
            else:
                count["rows off the ballot whose contest is on no notice"] += 1
            continue
        race["rows"].append(dict(i=i, r=r, hits=hits, src=SRC_LOCAL))
        if r["StatusDesc"] in ON_BALLOT and any(h["special"] for h in hits):
            race["special"] = 1
    spd_left = dict(P["spd_unplaced"])
    for i, t in sorted(P["spd_placed"].items()):
        r = spd_rows[i]
        race = race_for(norm(t), r["StatusDesc"] in ON_BALLOT)
        if race is None:
            if r["StatusDesc"] in ON_BALLOT:
                spd_left[i] = "the seat is not on a notice"
            continue
        race["rows"].append(dict(i=None, r=r, hits=[], src=SRC_SPD))

    # a district only a supervisor's page names is not made when it may be one the notice names in other words
    for t, race in sorted(races.items(), key=str):
        if t[0] != "DN":
            continue
        mine = {w for w in toks(race["jur"]) if w not in KIND_WORDS}
        twin = [x for x in races.values() if x["target"][0] == "D" and t[1] in x["codes"] and x["num"] == race["num"] and not x["rows"]
                and mine & {w for w in toks(x["jur"]) if w not in KIND_WORDS}]
        if twin:
            for e in race["rows"]:
                unplaced[e["i"]] = "on a supervisor's page under a district the notice may name in other words"
            del races[t]

    # ---- 6. names on a supervisor's page that the Division's list does not have
    not_loaded, page_kinds = collections.Counter(), collections.defaultdict(set)      # page_kinds: the kinds of contest a county's page shows
    for (code, gi), g in sorted(sup_groups.items()):
        free = [s for s in g["rows"] if not s["claims"] and s["status"] in SOE_ON]
        ocode = office_code(g["office"])
        if g["targets"]:
            seen = collections.Counter()
            for t0, n0 in g["targets"].items():
                seen[norm(t0)] += n0
            if len(seen) > 1:
                checks.append(f"{cname[code]} County: one heading of the supervisor's page holds candidates this loader placed in "
                              f"{len(seen)} contests")
            t = seen.most_common(1)[0][0]
        elif ocode == "CITY":
            t = None
        else:
            _nm, wnum = strip_seat(g["office"])
            n = wnum if isinstance(wnum, int) else None
            sp = int(bool(TERM_NOTE.search(g["office"])))
            if ocode in COUNTY_CODES:
                tag = "ATL" if re.search(r"at[\s-]*large|at lrg", g["office"], re.I) else "CHR" if re.search(r"\bchair", g["office"], re.I) else ""
                t = P["office_target"](code, ocode, n, tag, sp) or (P["office_target"](code, ocode, n, "", sp) if tag else None)
            else:
                t = norm(P["district_target"](code, g["office"], n, "", ocode, sp))
        g["race"] = races.get(t) if t else None
        if g["race"] is None:
            not_loaded["city headings" if ocode == "CITY" else "other headings"] += 1
            not_loaded["city candidates" if ocode == "CITY" else "other candidates"] += len(free)
            continue
        page_kinds[code].add(g["race"]["kind"])
        if free:
            g["race"]["sup_only"] += len(free)
            if g["special"]:
                g["race"]["special"] = 1

    # ---- 7. candidates, notes and whether each contest is partisan
    kinds_of = collections.defaultdict(set)
    for race in races.values():
        for e in race["rows"]:
            kinds_of[e["r"]["OfficeCode"]].add(race["kind"])
    # (kind of contest, seat number) of the candidates still on the ballot that could not be placed: by the kind the list's
    # office code usually means (waiting), and by every kind rows of that code were placed in (waiting_any)
    waiting, waiting_any = collections.Counter(), collections.Counter()
    for i, why in unplaced.items():
        r = rows[i]
        if r["StatusDesc"] in ON_BALLOT:
            num = seat_of(r)[0]
            for k in CODE_KINDS.get(r["OfficeCode"]) or kinds_of.get(r["OfficeCode"], set()):
                waiting[(k, num)] += 1
            for k in kinds_of.get(r["OfficeCode"], set()) | CODE_KINDS.get(r["OfficeCode"], set()):
                waiting_any[(k, num)] += 1
    no_rows = collections.Counter((race["kind"], race["num"]) for race in races.values() if not race["rows"])

    def may_be_unplaced(race):
        """Whether a seat with no candidate may belong to a candidate the list could not place: the list has such
        candidates for this kind of seat and number, and either the county's page shows no district of the kind at all, or
        they are at least a quarter as many as the seats of that kind and number left empty."""
        both = lambda w: w[(race["kind"], race["num"])] + (w[(race["kind"], None)] if race["num"] is not None else 0)
        if both(waiting_any) and any(race["kind"] not in page_kinds[c] for c in race["codes"]):
            return True
        return 4 * both(waiting) >= no_rows[(race["kind"], race["num"])] > 0 and both(waiting) > 0

    nonpartisan_boards = {}
    for race in races.values():                           # a county whose commission the list shows without parties
        if race["kind"] in ("county_commissioner", "county_council") and race["rows"]:
            codes = {e["r"]["PartyCode"] for e in race["rows"]}
            nonpartisan_boards.setdefault(race["jid"], []).append(not (codes - {"NOP", "WRI"}))

    def rid_of(race):
        jkey = race["jid"][len(STATE) + 1:] if race["jid"].startswith(STATE + "-") else race["jid"]
        bits, d, s = [], race["district"], race["seat"]
        if d:
            bits.append("d" + d if d.isdigit() else slug(d))
        if s:
            bits.append("seat" + s if s.isdigit() else ("g" + s.split()[1] if re.fullmatch(r"Group \d+", s) else slug(s)))
        return "-".join([f"2026-{STATE}", jkey, race["kind"].replace("_", "-")] + bits) + ("-S" if race["special"] else "")

    race_rows, cand_rows, ids = [], [], {}
    stored_i, dup_i, skipped_i, lone, mixed, contradictions, write_in_only, unshown, disagreements = set(), set(), set(), 0, 0, 0, 0, 0, 0
    for t, race in sorted(races.items(), key=str):
        kept = []
        for e in race["rows"]:                            # one candidacy entered twice (two counties' supervisors each enter a shared district's)
            name, mine, sups = shown_name(e["r"]), list_parts(e["r"]), {id(h) for h in e["hits"]}
            letters = lambda s: re.sub(r"[^a-z]", "", s.lower())
            twin = next((k for k in kept if k["r"]["StatusDesc"] == e["r"]["StatusDesc"] and k["r"]["PartyCode"] == e["r"]["PartyCode"]
                         and (letters(shown_name(k["r"])) == letters(name)
                              or (sups & {id(h) for h in k["hits"]} and fits(mine, list_parts(k["r"])) and fits(list_parts(k["r"]), mine)))), None)
            if twin is not None:
                twin["hits"] = twin["hits"] + e["hits"]
                if e["i"] is not None and e["r"]["StatusDesc"] in ON_BALLOT:
                    dup_i.add(e["i"])
                continue
            kept.append(e)
        # a name the Division's list marks off the ballot while the supervisor's page shows it qualified (a special election
        # called after no one qualified, say): said, never settled here
        doubt = [e for e in kept if (e["r"]["StatusDesc"] in ("Did Not Qualify", "Withdrew") and any(h["status"] in SOE_ON for h in e["hits"]))
                 or (e["r"]["StatusDesc"] == "Defeated" and any(h["status"] in ("Advanced", "Runoff", "Elected") for h in e["hits"]))]
        if any(h["special"] and h["status"] in SOE_ON for e in doubt for h in e["hits"]):
            race["special"] = 1
        rid = rid_of(race)
        if not re.fullmatch(rf"2026-{STATE}-[A-Za-z0-9-]+", rid):
            lstop(f"a race id that is not letters, digits and hyphens (a {race['kind']} contest in {race['codes'][0].upper()})")
        if rid in ids:
            lstop(f"two contests share the race id {rid}")
        ids[rid] = t
        race["rid"] = rid
        codes = {e["r"]["PartyCode"] for e in kept}
        if kept:
            partisan = int(bool(codes - {"NOP", "WRI"}))
        elif race["kind"] in ("county_commissioner", "county_council") and nonpartisan_boards.get(race["jid"]):
            partisan = int(not all(nonpartisan_boards[race["jid"]]))
        else:
            partisan = int(race["kind"] in PARTISAN_BY_LAW)
        if partisan and "NOP" in codes:
            mixed += 1
            checks.append(f"{rid}: the list gives parties to some candidates and marks others as candidates for a nonpartisan office")
        on = [e for e in kept if e["r"]["StatusDesc"] == "Qualified"]
        un = [e for e in kept if e["r"]["StatusDesc"] == "Unopposed"]
        lost = [e for e in kept if e["r"]["StatusDesc"] == "Defeated"]
        note = []
        if race["choose"] > 1:
            note.append(f"Voters choose {race['choose']}.")
        if race["term"]:
            note.append(f"An election for a {race['term']}-year term, as the county supervisor's page words it.")
        elif race["special"]:
            note.append("The county supervisor's page lists this contest as a special election.")
        if not race["on_notice"]:
            note.append(NOT_ON_NOTICE)
        seats = race["choose"]
        printed = [e for e in on if e["r"]["PartyCode"] != "WRI"]
        if un and not on:
            if len(un) > seats:
                checks.append(f"{rid}: {len(un)} candidates marked Unopposed for {plural(seats, 'seat')}")
            if lost:
                note.append(SEAT_ELECTED)
            else:
                note.append(SEAT_UNOPPOSED if len(un) == 1 else
                            "Elected without opposition: no names are printed on the November ballot for these seats.")
        elif on:
            if un and printed:
                contradictions += 1
                checks.append(f"{rid}: the list marks some candidates Qualified and others Unopposed")
            elif un or (len(printed) == 1 and len(on) > 1 and seats == 1):
                write_in_only += 1
                note.append(FACES_WRITE_IN)
            if race["kind"] in ("school_board", "county_court") and lost and len(printed) == 2 and seats == 1 and not un:
                note.append(RUNOFF_RACE_NOTE)
            if len(printed) == 1 and len(on) == 1 and seats == 1 and not un:
                lone += 1
                note.append("Only one candidate on the Division's list is marked as qualified for this seat.")
        elif kept:
            note.append(NONE_QUALIFIED)
        elif may_be_unplaced(race):
            note.append("No candidate for this seat could be placed here.")
            gaps.append((STATE, "race", rid, f"{race['office']}, {race['jur']}", "candidates for this seat", MAY_BE_UNPLACED, PAGE))
        else:
            note.append(NO_CANDIDATE)
        if race["sup_only"]:
            n = race["sup_only"]
            note.append(f"The county supervisor's own page names {plural(n, 'more candidate')} for this seat whose "
                        f"{'name' if n == 1 else 'names'} could not be found on the Division's list.")
            url = (cty[race["codes"][0]]["page"] or {}).get("url")
            gaps.append((STATE, "race", rid, f"{race['office']}, {race['jur']}", "a candidate named only on the county supervisor's page" if n == 1
                         else "candidates named only on the county supervisor's page",
                         f"The county supervisor's own page shows {plural(n, 'more candidate')} for this seat as qualified, advanced, unopposed or "
                         f"elected, but {'that name' if n == 1 else 'those names'} could not be found on the Division's list, which this page "
                         f"follows for who is on the ballot; {'it is' if n == 1 else 'they are'} left out until the two lists agree.", url))
        if doubt:
            n = len(doubt)
            disagreements += n
            note.append(f"The county supervisor's own page marks {plural(n, 'candidate')} for this seat as qualified or elected whom the Division's "
                        "list marks as not qualified, withdrawn or defeated.")
            gaps.append((STATE, "race", rid, f"{race['office']}, {race['jur']}", "a candidate the two lists disagree about" if n == 1
                         else "candidates the two lists disagree about",
                         f"The county supervisor's own page shows {plural(n, 'candidate')} for this seat as qualified, advanced or elected, while "
                         f"the Division's list, which this page follows for who is on the ballot, marks {'that name' if n == 1 else 'those names'} "
                         f"as not qualified, withdrawn or defeated; {'it is' if n == 1 else 'they are'} left out until the two lists agree.",
                         (cty[race["codes"][0]]["page"] or {}).get("url")))
        race["partisan"], race["n_on"], race["n_un"] = partisan, len(on), len(un)
        text = " ".join(note) or None
        if any(reads_like_contact(cell) for cell in (race["office"], race["jur"], race["district"], race["seat"], text)):
            unshown += 1                                  # a name or note that reads like a contact detail is never stored: the contest is left out
            skipped_i.update(e["i"] for e in on + un if e["i"] is not None)
            checks.append(f"a {race['kind']} contest in {cname[race['codes'][0]]} County has a name the contact-detail check refuses; it is left out")
            gaps[:] = [g for g in gaps if g[2] != rid]
            del race["rid"]
            continue
        for e in on + un:
            r = e["r"]
            name = shown_name(r)
            if not r["NameFirst"] and not r["NameMiddle"]:
                checks.append(f"{rid}: a candidate is listed by one name only")
            write_in = int(r["PartyCode"] == "WRI")
            if reads_like_contact(name) or CONTACT.search(name):
                checks.append(f"{rid}: a candidate's name reads like a contact detail (not shown); the candidate is left out")
                gaps.append((STATE, "race", rid, f"{race['office']}, {race['jur']}", "a candidate whose name could not be read",
                             "A name cell for this seat on the Division's list holds something other than a name, so that candidate is left "
                             "out until the list is corrected.", PAGE))
                if e["i"] is not None:
                    skipped_i.add(e["i"])
                continue
            if partisan:
                party = r["PartyDesc"] or parties.get(r["PartyCode"], "")
                if r["PartyCode"] == "NOP":
                    party = "No Party Affiliation"
                if not party:
                    checks.append(f"{rid}: a candidate's party code ({r['PartyCode']}) is not named by the Division; the candidate is left out")
                    gaps.append((STATE, "race", rid, f"{race['office']}, {race['jur']}", "a candidate whose party the list does not name",
                                 "The Division's list gives one candidate for this seat a party code that neither the list nor the Division's "
                                 "list of political parties spells out, so that candidate is left out until it does.", PAGE))
                    if e["i"] is not None:
                        skipped_i.add(e["i"])
                    continue
                code = "W" if write_in else party_code(party)
            else:
                party, code = NONPARTISAN, NP_CODE
            unopposed = r["StatusDesc"] == "Unopposed" and not on      # with a qualified candidate beside it, the name is on the ballot
            said = sorted({SOE_OFF_WORDS[h["status"]] for h in e["hits"] if h["status"] in ("Withdrawn", "Did not qualify", "Defeated")
                           or (r["StatusDesc"] == "Qualified" and h["status"] in ("Unopposed", "Elected"))})
            cnote = [(ELECTED_NOTE if lost else UNOPPOSED_NOTE) if unopposed else "", WRITE_IN_NOTE if write_in else "",
                     "The Division's list marks this candidate as unopposed and another as qualified for the same seat."
                     if r["StatusDesc"] == "Unopposed" and printed else "",
                     f"The county supervisor's own page marks this candidate as {' and '.join(said)}." if said else ""]
            if said:
                count["candidates the supervisor's page marks otherwise"] += 1
            cand_rows.append([rid, "general", GENERAL, name, party, code, None, 0, write_in, None, None, "unopposed" if unopposed else None, None,
                              e["src"], " ".join(x for x in cnote if x) or None])
            if e["i"] is not None:
                stored_i.add(e["i"])
        race_rows.append([rid, STATE, race["level"], race["kind"], race["office"], race["jur"], race["jid"], json.dumps(race["cids"]),
                          race["district"], race["seat"], race["special"], partisan, None, None, None, GENERAL, text])
    keys = [(c[0], c[3]) for c in cand_rows]
    if len(keys) != len(set(keys)):
        lstop("two candidate rows share a race and a name")

    # ---- 8. the state attorney and public defender a notice names (state candidates, on the Division's own list)
    court_places = []
    for (head, c), geoids in sorted(P["att_lines"].items()):
        if c not in circuit_geo:
            checks.append(f"{head}, circuit {c}: on a notice, but section 26.021 gives no such circuit; not loaded")
            continue
        if sorted(geoids) != sorted(circuit_geo[c]):
            checks.append(f"{head}, circuit {c}: on the notices of {len(geoids)} counties, while section 26.021 gives the circuit "
                          f"{len(circuit_geo[c])}")
        code = {"State Attorney": "STA", "Public Defender": "PUB"}[head]
        rid = f"2026-{STATE}-{'SA' if code == 'STA' else 'PD'}{c}"
        mine = [r for r in P["att_rows"] if r["OfficeCode"] == code and r["Juris1num"].strip().isdigit() and int(r["Juris1num"]) == c
                and r["NameLast"]]
        on = [r for r in mine if r["StatusDesc"] in ON_BALLOT]
        alone = len(on) == 1 and on[0]["StatusDesc"] == "Unopposed"
        note = [f"On the Secretary of State's notices of the general election for the {plural(len(geoids), 'county', 'counties')} of the circuit."]
        note.append(SEAT_UNOPPOSED if alone else "" if on else "No candidate for this office is on the Division's list.")
        race_rows.append([rid, STATE, "court", "state_attorney" if code == "STA" else "public_defender", head, f"{ordinal(c)} Judicial Circuit",
                          f"JC{c}", json.dumps(sorted(circuit_geo[c])), str(c), None, 0, 1, None, None, None, GENERAL,
                          " ".join(x for x in note if x)])
        place = ("judicial", f"{STATE}-JC{c}", f"{ordinal(c)} Judicial Circuit", json.dumps(sorted(circuit_geo[c])))
        if place not in court_places:
            court_places.append(place)
        for r in on:
            party = r["PartyDesc"] or parties.get(r["PartyCode"], "")
            write_in = int(r["PartyCode"] == "WRI")
            if not party or reads_like_contact(shown_name(r)) or CONTACT.search(shown_name(r)):
                checks.append(f"{rid}: a candidate could not be stored (party or name)")
                continue
            unopposed = r["StatusDesc"] == "Unopposed"
            cnote = " ".join(x for x in (UNOPPOSED_NOTE if unopposed else "", WRITE_IN_NOTE if write_in else "") if x) or None
            cand_rows.append([rid, "general", GENERAL, shown_name(r), party, "W" if write_in else party_code(party), None, 0, write_in, None, None,
                              "unopposed" if unopposed else None, None, SRC_ATT, cnote])

    # ---- 9. places: every district the contests use, and each county's school district
    place_list, seen_place = [], {}
    for t, race in sorted(races.items(), key=str):
        if not race["pkind"] or "rid" not in race:
            continue
        key = (race["pkind"], race["jid"])
        if key in seen_place:
            if seen_place[key] != race["jur"]:
                lstop(f"two districts share the place id {race['jid']}")
            continue
        seen_place[key] = race["jur"]
        place_list.append((race["pkind"], race["jid"], race["jur"], json.dumps(race["cids"]), race["src"]))

    # ---- 10. what is not here, and why
    local = [r for r in race_rows if r[2] in LOCAL_LEVELS]
    county_court = [r for r in race_rows if r[3] == "county_court"]
    lids = {r[0] for r in local} | {r[0] for r in county_court}
    n_cands = sum(1 for c in cand_rows if c[0] in lids)
    off = collections.Counter(r["StatusDesc"] for r in rows if r["StatusDesc"] not in ON_BALLOT)
    on_rows = {i for i, r in enumerate(rows) if r["StatusDesc"] in ON_BALLOT}
    left_i = {i for i in unplaced if i in on_rows}
    left = collections.Counter(rows[i]["OfficeDesc"] or rows[i]["OfficeCode"] for i in left_i)
    n_left = len(left_i)
    if stored_i & dup_i or (stored_i | dup_i | skipped_i) & left_i or len(on_rows) != len(stored_i) + len(dup_i) + len(skipped_i) + n_left:
        lstop(f"the list's {len(on_rows)} qualified and unopposed rows are not its {len(stored_i)} stored, {len(dup_i)} repeated, "
              f"{len(skipped_i)} left out and {n_left} unplaced rows")
    for i, why in spd_left.items():
        if spd_rows[i]["StatusDesc"] in ON_BALLOT:
            checks.append("a candidate on the Division's list of multi-county districts could not be placed: " + why)
    dup_rows = len(dup_i)
    by_kind_words = ", ".join(f"{k} {n}" for k, n in sorted(left.items(), key=lambda kv: (-kv[1], kv[0])))
    no_page = sorted(c["name"] for c in cty.values() if not c["page"])
    city_counties = len({code for (code, _gi), g in sup_groups.items() if g.get("race") is None and office_code(g["office"]) == "CITY"})
    gaps.append((STATE, "state", STATE, "Florida", "city, town and village races",
                 "Florida's cities, towns and villages take their own candidates' filings and vote on days their charters set; the Division of "
                 "Elections' list has no city offices, and no one official list covers them. Some county supervisors' pages do show city "
                 f"candidates ({plural(not_loaded['city headings'] + not_loaded['other headings'], 'heading')} for offices on neither the "
                 f"notices nor the Division's list were seen and left out, nearly all of them city offices), but not which are on the "
                 "November 3 ballot.", "https://dos.elections.myflorida.com/candidates/"))
    gaps.append((STATE, "state", STATE, "Florida", "the order of names on the printed ballot",
                 "Neither the Division's list nor a county supervisor's candidate page states the order in which names are printed; each "
                 "county's sample ballot does, and those are not read here yet.", NOTICE_INDEX))
    if n_left:
        gaps.append((STATE, "state", STATE, "Florida", "candidates whose county the Division's list does not give",
                     "The Division's list gives each candidate's office and seat but not the county or the district, so a candidate is placed "
                     "only when the same name, office and seat is on a county supervisor's own page. "
                     f"{plural(n_left, 'candidate')} still on the ballot or elected unopposed could not be placed that way ({by_kind_words}) and "
                     f"{'is' if n_left == 1 else 'are'} left out; the seats they filed for show here without a candidate.", PAGE))
    for name in no_page:
        code = next(c["code"] for c in cty.values() if c["name"] == name)
        gaps.append((STATE, "county", geo[code], f"{name} County", "candidates for county and district offices",
                     "The county supervisor of elections' candidate page could not be read, and the Division's list does not say which "
                     "county a candidate runs in, so this county's contests are shown without candidates for now.",
                     f"{SOE_PAGE}?c={cty[code]['key']}"))
    for g in gaps:
        if contact_like(g[3], False) or contact_like(g[4], False) or contact_like(g[5], False):
            lstop("a gap's text reads like a contact detail (not shown)")

    # ---- 11. the notes and the sources
    total = len(cty)
    day = lambda iso: f"{dt.date.fromisoformat(iso):%B} {dt.date.fromisoformat(iso).day}, {dt.date.fromisoformat(iso).year}"
    nk = collections.Counter(r[3] for r in race_rows)
    with_kind = collections.defaultdict(set)
    for r in race_rows:
        with_kind[r[3]].update(json.loads(r[7]))
    n_districts = len({r[6] for r in local if r[2] in ("soil_water", "hospital", "other")})
    decided = sum(1 for r in race_rows if r[0] in lids and (r[16] or "").find(SEAT_ELECTED) >= 0)
    unopposed_seats = sum(1 for r in race_rows if r[0] in lids and "Elected without opposition" in (r[16] or ""))
    contested = len({c[0] for c in cand_rows if c[0] in lids and c[11] is None})
    other_words = {"clerk_of_court": "clerk of the circuit court", "tax_collector": "tax collector",
                   "supervisor_of_elections": "supervisor of elections", "county_attorney": "county attorney", "county_executive": "county mayor",
                   "charter_review_board": "charter review board", "sheriff": "sheriff", "property_appraiser": "property appraiser",
                   "school_superintendent": "superintendent of schools"}
    others = sorted(k for k in other_words if nk[k])
    district_seats = sum(1 for r in local if r[2] in ("soil_water", "hospital", "other"))
    calendar = (
        f"On November 3, 2026 the Secretary of State's notices of the general election list {nk['county_commissioner'] + nk['county_council']:,} "
        f"county commission and county council seats in {len(with_kind['county_commissioner'] | with_kind['county_council'])} of Florida's "
        f"{total} counties, {nk['school_board']:,} school board seats, {nk['county_court']:,} county judgeships and "
        f"{district_seats:,} seats on the boards of {n_districts:,} "
        "special districts (community development, fire, soil and water conservation and others)"
        + (f", and in a few counties a {', '.join(other_words[k] for k in others[:-1])}{' or ' if len(others) > 1 else ''}"
           f"{other_words[others[-1]]}" if others else "")
        + ". School board members and county judges are nonpartisan and are voted on first at the August 18 primary election; a seat is on "
        "the November ballot only when no one won a majority then, or when a write-in candidate has qualified. Sheriffs, property "
        "appraisers, tax collectors, clerks, school superintendents and supervisors of elections are otherwise elected in presidential "
        "years, next in 2028, and cities, towns and villages vote on days their own charters set.")
    lst = by_what["local"]
    coverage = (
        f"Loaded from the Florida Division of Elections' candidate list for local offices as read on {day(lists['fetched'][:10])}, which the "
        "Division offers as an unofficial reference (it sends readers to the county supervisors of elections for county candidates): "
        f"{n_cands:,} candidates in {len(lids):,} contests for county commissions, school boards, county judgeships, a few other county "
        "offices and special districts. The contests are those the Secretary of State's notices of the general election name, and each "
        "candidate is placed in a county and district by finding the same name, office and seat on that county supervisor's own page. "
        f"In {unopposed_seats:,} contests the candidate is unopposed and in {decided:,} the August 18 election settled the seat, so no name is "
        f"printed in November; {contested:,} contests have a name on the ballot. Not loaded: city, town and village offices; "
        + (f"{plural(n_left, 'candidate')} whose county could not be found; " if n_left else "")
        + f"the {sum(off.values()):,} candidates the list marks as defeated, withdrawn, not qualified or deceased; ballot questions; "
        "the printed ballot order; and local primaries.")
    notes = [(STATE, "local_calendar", calendar,
              "Florida Division of Elections, Notices of General Election for 2026 (one for each county); Florida Statutes, sections 100.041, "
              "98.015 and 105.051", NOTICE_INDEX),
             (STATE, "local_coverage", coverage,
              "Florida Division of Elections, Candidate Tracking System (candidate list, Local Candidates, 2026 Election); the Secretary of "
              "State's Notices of General Election; the candidate pages of the 67 county supervisors of elections", PAGE)]
    for n in notes:
        if contact_like(n[2], False) or contact_like(n[3], False):
            lstop("a note's text reads like a contact detail (not shown)")

    status_n = collections.Counter(r["StatusDesc"] for r in rows)
    placed_n = sum(1 for i in placed if i not in unplaced)
    by_letter = count["rows placed by the family name and the first letter of the given name"]
    kept_cols = ", ".join(KEEP)
    cut_words = (f"The file was held in memory only to cut every row down, by heading, to {kept_cols}; voter ID and account numbers, addresses, "
                 "cities, ZIP codes, the address block's county code, telephone numbers, treasurers and e-mail were never read or kept, and the "
                 "file was not saved (the SHA-256 is of the file as received).")
    sources = [
        (SRC_LOCAL, STATE, "candidate list (unofficial reference)", AGENCY,
         "Candidate Tracking System: candidate list, 2026 Election, Local Candidates, all offices and statuses", PAGE, "", lists["fetched"][:10],
         lst["sha256"], len(rows),
         "Answered by the Division's download form as a tab-separated file. The Division offers its tracking system as an unofficial reference "
         f"and sends readers to the county supervisors of elections for county candidates. {cut_words} "
         f"{lst['emptied']} kept cells that read like contact details were emptied"
         + ("; the file's accented letters are Windows-1252 and are read as such" if lst.get("letters") == "windows-1252" else "")
         + f". Of {len(rows):,} rows, "
         + ", ".join(f"{k} {v:,}" for k, v in sorted(status_n.items()))
         + f". The list names an office and a seat but no county and no district, so each row is placed by finding the same name, office and "
         f"seat on a county supervisor's own page: {placed_n:,} were placed ({by_letter} of them by the family name, the office, the seat and "
         f"the first letter of the given name), and {len(unplaced):,} were not "
         f"({n_left} of those still on the ballot or elected unopposed). {dup_rows} rows repeat a candidacy entered twice. Qualified rows are "
         "the November ballot; Unopposed rows are kept with a note; the rest are counted and left out. No ballot order is given, so none "
         "is stored."),
        (SRC_SPD, STATE, "candidate list (unofficial reference)", AGENCY,
         "Candidate Tracking System: candidate list, 2026 Election, State Candidates, Special Districts (districts of more than one county)",
         PAGE, "", lists["fetched"][:10], by_what["districts"]["sha256"], len(spd_rows),
         f"The candidates of special districts that reach more than one county qualify with the Division, which names each district. {cut_words} "
         f"{len(spd_rows) - len(spd_left)} of {len(spd_rows)} rows were matched by the district's name to a district on the notices."),
        (SRC_NGE_INDEX, STATE, "official notice", AGENCY, "Notices of General Election, 2026: the page that links each county's notice",
         NOTICE_INDEX, "", nset["index"]["read"], nset["index"]["sha256"], len(nset["notices"]),
         "Read only for the address of each county's notice in English; the notices themselves are the sources that follow."),
    ]
    if P["att_lines"]:
        sources.append((SRC_ATT, STATE, "candidate list (unofficial reference)", AGENCY,
                        "Candidate Tracking System: candidate list, 2026 Election, State Candidates, State Attorney / Public Defender", PAGE, "",
                        lists["fetched"][:10], by_what["circuit"]["sha256"], len(P["att_rows"]),
                        f"Read for the state attorney and public defender the notices of the general election name. {cut_words}"))
    per_cty = collections.Counter()
    for t, race in races.items():
        if "rid" in race and race["on_notice"]:
            for code in race["codes"]:
                per_cty[code] += 1
    placed_cty = collections.Counter(h["cty"] for _t, hits in placed.values() for h in hits[:1])
    for code, c in sorted(cty.items()):
        m = c["meta"]
        sources.append((SRC_NGE.format(code=code), STATE, "official notice", AGENCY,
                        f"{'Amended ' if c['amended'] else ''}Notice of General Election, {c['name']} County, for November 3, 2026", m["url"],
                        c["given"] or "", m["fetched"], m["sha256"], per_cty[code],
                        "Signed by the Secretary of State: the offices to be filled in the county. The lines for county offices, the school "
                        f"board, county judges and special districts are read ({per_cty[code]} contests); federal and state offices are left "
                        "to the lists read for them. The notice names no candidate and carries no contact detail, so the file is kept as "
                        "published."))
        pg = c["page"]
        if not pg:
            continue
        n_rows = sum(len(g["cands"]) for g in pg["groups"])
        sources.append((SRC_SOE.format(code=code), STATE, "county candidate list", f"{c['name']} County Supervisor of Elections",
                        f"Candidate reports page, reporting group \"{pg['label']}\"", pg["url"], "", pg["fetched"], pg["sha256"], n_rows,
                        "The supervisor's own page of candidates for county and local offices. Read: each office heading and, under it, each "
                        "candidate's name, the party mark beside it and the status; the page's campaign money columns and its links are "
                        "never kept, and it shows no addresses, telephone numbers or e-mail (the SHA-256 is of the page as received; only "
                        f"the cells named here are saved). Used to find the county and district of the Division's candidates: "
                        f"{placed_cty[code]} were placed here."
                        + (f" {pg['emptied']} cells that read like contact details were emptied." if pg.get("emptied") else "")))
        for k, more in enumerate(pg.get("more", []), start=1):
            sources.append((SRC_SOE.format(code=code) + f"-special-{k}", STATE, "county candidate list",
                            f"{c['name']} County Supervisor of Elections",
                            f"Candidate reports page, reporting group \"{more['label']}\"", more["url"], "", pg["fetched"], more["sha256"],
                            sum(len(g["cands"]) for g in more["groups"]),
                            "A special election the supervisor's page keeps apart from the general election's candidates; read in the same "
                            "way, the same cells only."))
    for s in sources:
        if any(contact_like(x, False) for x in (s[3], s[4], s[10])):
            lstop(f"the source row {s[0]} reads like a contact detail (not shown)")

    local_ids, court_ids = {r[0] for r in local}, {r[0] for r in county_court}
    counts = dict(list_rows=len(rows), spd_rows=len(spd_rows), statuses=dict(status_n), placed=placed_n, unplaced=len(unplaced),
                  skipped=len(skipped_i), unplaced_on_ballot=n_left, left_by_kind=dict(left), stored=len(stored_i), off=dict(off), dup_rows=dup_rows,
                  races=len(race_rows), local_races=len(local), county_court=len(county_court),
                  local_cands=sum(1 for c in cand_rows if c[0] in local_ids), court_cands=sum(1 for c in cand_rows if c[0] in court_ids),
                  on_notice=on_notice, by_kind=dict(nk),
                  by_level=dict(collections.Counter(r[2] for r in race_rows)), counties_reached=len({g for r in local for g in json.loads(r[7])}),
                  unopposed_seats=unopposed_seats, decided=decided, contested=contested, lone=lone, write_in_only=write_in_only,
                  contradictions=contradictions, disagreements=disagreements, unshown=unshown, mixed=mixed, not_loaded=dict(not_loaded),
                  city_counties=city_counties, race_gaps=sum(1 for g in gaps if g[1] == "race"),
                  no_page=no_page, more=dict(count))
    return dict(races=race_rows, cands=cand_rows, places=place_list, court_places=court_places, gaps=gaps, notes=notes, sources=sources,
                checks=checks, counts=counts, detail=dict(P=P, races=races, unplaced=unplaced, stored_i=stored_i, page_kinds=page_kinds,
                                                           kinds_of=kinds_of, waiting=waiting, spd_left=spd_left))


# ------------------------------------------------------------------------------------------------ loading

def load(db_path, say=print, folder=FOLDER, roster_db=ROSTER, refresh=False, local_folder=None):
    from states import net
    net.patient_lookups()
    os.makedirs(folder, exist_ok=True)
    checks, matched = [], []

    # 0. the sources
    lists, lists_path = candidate_lists(folder, say, refresh=refresh)
    parties, parties_path = party_names(folder, say)
    res_files, blocked = results_files(folder, say)
    if not res_files:
        stop(f"the official primary results could not be had ({blocked})")
    sum_paths = summaries(folder, say)
    legs, offs = roster(roster_db)
    counties_shp = read_shapes(COUNTY_ZIP, lambda r: (r["GEOID"], r["NAME"]))
    if len(counties_shp) != TOTAL_COUNTIES:
        stop(f"the Census county file has {len(counties_shp)} Florida counties, not {TOTAL_COUNTIES}")
    geo_of = {county_key(n): g for g, n in counties_shp}
    all_geoids = sorted(g for g, _n in counties_shp)
    circuits, dcas, statute_paths = statutes(folder, say, [n for _g, n in counties_shp])
    circuit_geo = {c: sorted(geo_of[county_key(n)] for n in names) for c, names in circuits.items()}

    # 1. the lists: which offices and seats are up, and the rows on them
    gen = [x for x in lists["lists"] if x["elecID"] == GEN_ID]
    specials = [x for x in lists["lists"] if x["elecID"].startswith("20261103-S")]
    old = [x for x in lists["lists"] if x["elecID"] == CHECK_2024]
    if sorted(x["office"] for x in gen) != sorted(OFFICES) or len(old) != 1:
        stop(f"{lists_path} does not hold the three 2026 lists and the 2024 list")
    rows = [dict(r, _list=x["elecID"], _special=0) for x in gen for r in x["rows"]]
    rows += [dict(r, _list=x["elecID"], _special=1, _label=x["label"]) for x in specials for r in x["rows"]]
    statuses = {r["StatusDesc"] for r in rows}
    unknown = statuses - set(ON_BALLOT) - set(OFF_BALLOT)
    if unknown:
        stop(f"the candidate lists carry a status this loader does not know: {sorted(unknown)}")
    for r in rows:
        if r["ElectionID"] != r["_list"]:
            stop(f"a row of the {r['_list']} list is filed under the election {r['ElectionID']!r}")
        if r["OfficeCode"] not in OFFICE_DESC or OFFICE_DESC[r["OfficeCode"]] != r["OfficeDesc"]:
            stop(f"the {r['_list']} list carries an office this loader does not read: {r['OfficeCode']} {r['OfficeDesc']!r}")
        if r["_special"] and r["OfficeCode"] not in ("STS", "STR"):
            stop(f"the special election list {r['_list']} carries an office other than the Legislature ({r['OfficeCode']})")
        if not r["NameLast"]:
            stop(f"a row of the {r['_list']} list for {r['OfficeCode']} {r['Juris1num']} has no family name")
        if not r["PartyDesc"] and r["PartyCode"] in parties:
            r["PartyDesc"], r["_party_from"] = parties[r["PartyCode"]], True
        if not r["PartyDesc"]:
            stop(f"a candidate for {r['OfficeCode']} {r['Juris1num']} has a party code ({r['PartyCode']}) the Division's party list does not name")
    senate_2026 = sorted({int(r["Juris1num"]) for r in rows if r["OfficeCode"] == "STS" and not r["_special"]})
    senate_2024 = sorted({int(r["Juris1num"]) for r in old[0]["rows"] if r["OfficeCode"] == "STS"})
    if senate_2026 != list(range(2, SENATE_SEATS + 1, 2)):
        stop(f"the Senate seats on the 2026 list are not the twenty even-numbered districts: {senate_2026}")
    if senate_2024 != list(range(1, SENATE_SEATS + 1, 2)):
        stop(f"the Senate seats on the 2024 list are not the twenty odd-numbered districts: {senate_2024}")
    house_2026 = sorted({int(r["Juris1num"]) for r in rows if r["OfficeCode"] == "STR" and not r["_special"]})
    if house_2026 != list(range(1, HOUSE_SEATS + 1)):
        checks.append(f"the House seats on the 2026 list are not all 120 districts (missing {sorted(set(range(1, 121)) - set(house_2026))})")
    for r in rows:
        if r["OfficeCode"] == "STS" and r["_special"] and int(r["Juris1num"]) in senate_2026:
            stop(f"a special election for Senate District {int(r['Juris1num'])}, which is also up for a full term")

    # 2. the official results
    contests, differ, _other = extract(res_files["extract"])
    res_checks, bad = [f"results extract: {d}" for d in differ], set()
    for d in differ:
        if d.startswith("("):
            bad.add(next(k for k in contests if d.startswith(str(k))))
    sums, official, sum_rows = {}, True, {}
    for (race, party), path in sum_paths.items():
        ok, got = summary(path, race, party)
        official = official and ok
        sum_rows[(race, party)] = sum(len(s["names"]) for s in got.values())
        for key, s in got.items():
            sums[key + (party,)] = s
    if not official:
        stop("a Summary Report is not headed \"Official Results\"; unofficial figures are never stored")
    for key, cands in contests.items():                  # the county sums against the Division's own totals
        s = sums.get(key)
        if s is None:
            res_checks.append(f"{key}: in the results extract but on no Summary Report")
            bad.add(key)
            continue
        mine = {ballot_name(first, middle, last): v["votes"] for (last, first, middle), v in cands.items()}
        total = sum(mine.values())
        theirs = {" ".join(fold(n).split()): (t, p) for n, t, p in zip(s["names"], s["totals"], s["pcts"])}
        if set(mine) != set(theirs):
            res_checks.append(f"{key}: the Summary Report names {sorted(set(theirs) - set(mine))}, the extract {sorted(set(mine) - set(theirs))}")
            bad.add(key)
            continue
        for n, v in mine.items():
            if theirs[n][0] != v:
                res_checks.append(f"{key}: {n}'s counties add to {v}, the Summary Report's Total is {theirs[n][0]}")
                bad.add(key)
            if total and abs(theirs[n][1] - 100 * v / total) > 0.051:
                res_checks.append(f"{key}: {n}'s share on the Summary Report is {theirs[n][1]}%, computed {100 * v / total:.2f}%")
                bad.add(key)
    for key in sums:
        if key not in contests:
            res_checks.append(f"{key}: on a Summary Report but not in the results extract")
    checks += res_checks

    # 3. the races, each with who holds it today
    races = {}

    def add_race(rid, **kw):
        if rid in races:
            return races[rid]
        base = dict(race_id=rid, state=STATE, jurisdiction=None, jurisdiction_id=None, county_ids=None, district=None, seat=None,
                    special=0, partisan=1, holder_id=None, holder_name=None, holder_party=None, election_date=GENERAL, note=[], _holder=None)
        base.update(kw)
        races[rid] = base
        return base

    def legislative(code, d, special, label=None):
        senate = code == "STS"
        rid = f"2026-{STATE}-{'SS' if senate else 'SH'}{d}"
        chamber = "Senate" if senate else "House"
        hs = [p for p in legs if p["chamber"] == chamber and str(p["district"]).strip() == str(d)]
        h = hs[0] if len(hs) == 1 else None
        note = []
        if senate and not special:
            note.append(SENATE_NOTE)
        if special:
            note.append(f"A special election for the rest of the current term, as the Division lists it (\"{label}\")"
                        + ("; odd-numbered Senate districts were last elected in 2024, for terms that end in 2028." if senate and d % 2 else "."))
        if len(hs) > 1:
            checks.append(f"{rid}: {len(hs)} sitting members in the roster for this seat; none is taken as the holder")
        if h is None:
            note.append("The roster shows no one holding this seat today.")
        return add_race(rid, level="legislature", office_kind="state_senate" if senate else "state_house",
                        office="State Senator" if senate else "State Representative", jurisdiction=f"{chamber} District {d}",
                        jurisdiction_id=str(d), district=str(d), special=special, holder_id=h["id"] if h else None,
                        holder_name=h["full"] if h else None, holder_party=h["party"] if h else None, note=note, _holder=h,
                        _chamber=chamber)

    for code, (key, kind, office, _rc, roster_office) in STATEWIDE.items():
        h = offs.get(roster_office) if roster_office else None
        add_race(f"2026-{STATE}-{key}", level="statewide", office_kind=kind, office=office, jurisdiction=NAME, jurisdiction_id=FIPS,
                 county_ids=json.dumps(all_geoids), holder_id=h["id"] if h else None, holder_name=h["full"] if h else None,
                 holder_party=h["party"] if h else None, _holder=h,
                 note=([GOV_NOTE] if code == "GOV" else []) + ([] if h else [NO_HOLDER]))
    for d in senate_2026:
        legislative("STS", d, 0)
    for d in range(1, HOUSE_SEATS + 1):
        legislative("STR", d, 0)
    for r in rows:
        if r["_special"]:
            legislative(r["OfficeCode"], int(r["Juris1num"]), 1, r["_label"])

    # the courts on the November ballot: retention votes, and the circuit judge runoffs
    runoffs = {}
    for r in rows:
        if r["OfficeCode"] == "CTJ" and r["StatusDesc"] in ON_BALLOT and r["StatusDesc"] == "Qualified":
            runoffs.setdefault((int(r["Juris1num"]), int(r["Juris2num"])), []).append(r)
    for (c, g), rs in sorted(runoffs.items()):
        rid = f"2026-{STATE}-CC{c}-{g}"
        add_race(rid, level="court", office_kind="circuit_court", office="Circuit Judge", jurisdiction=f"{ordinal(c)} Judicial Circuit",
                 jurisdiction_id=f"JC{c}", district=str(c), seat=f"Group {g}", partisan=0, county_ids=json.dumps(circuit_geo[c]),
                 note=[RUNOFF_RACE_NOTE, "The roster used here does not carry judges."], _circuit=c)
        if len(rs) != 2:
            checks.append(f"{rid}: {len(rs)} qualified candidates for a November runoff, not two")
    for r in rows:
        if r["OfficeCode"] not in ("SCJ", "DCA") or r["StatusDesc"] not in ON_BALLOT:
            continue
        sc = r["OfficeCode"] == "SCJ"
        fam = family_key(r)
        if sc:
            rid, office, jur, jid, geo = f"2026-{STATE}-SCRET-{fam}", "Justice of the Supreme Court (retention vote)", NAME, FIPS, all_geoids
        else:
            n = int(r["Juris1num"])
            if n not in dcas:
                stop(f"a District Court of Appeal judge on the list is filed under district {r['Juris1num']!r}")
            rid = f"2026-{STATE}-DCA{n}RET-{fam}"
            office = f"Judge, {ORDINAL[n]} District Court of Appeal (retention vote)"
            jur, jid = f"{ORDINAL[n]} Appellate District", f"DCA{n}"
            geo = sorted(g for c in dcas[n] for g in circuit_geo[c])
        if rid in races:
            stop(f"two judges standing for retention share the race key {rid}")
        who = shown_name(r)
        add_race(rid, level="court", office_kind="supreme_court_retention" if sc else "court_of_appeals_retention", office=office,
                 jurisdiction=jur, jurisdiction_id=jid, district=None if sc else str(int(r["Juris1num"])), partisan=0,
                 county_ids=json.dumps(geo), holder_name=who, note=[RETENTION_NOTE.format(who="justice" if sc else "judge")], _judge=who)

    def race_of(r):
        oc = r["OfficeCode"]
        if oc in STATEWIDE:
            return f"2026-{STATE}-{STATEWIDE[oc][0]}"
        if oc in ("STS", "STR"):
            return f"2026-{STATE}-{'SS' if oc == 'STS' else 'SH'}{int(r['Juris1num'])}"
        if oc == "CTJ":
            rid = f"2026-{STATE}-CC{int(r['Juris1num'])}-{int(r['Juris2num'])}"
            return rid if rid in races else None
        if oc == "SCJ":
            return f"2026-{STATE}-SCRET-{family_key(r)}"
        return f"2026-{STATE}-DCA{int(r['Juris1num'])}RET-{family_key(r)}"

    for r in rows:
        r["_race"] = race_of(r)

    # 4. who is who
    people = legs + [dict(p, chamber=None, district=None) for p in offs.values()]

    def identify(rid, name, party):
        """(incumbent, state_member_id, note) for one name in a race."""
        race = races[rid]
        if race.get("_judge"):
            return (1, None, None) if name == race["_judge"] else (0, None, None)
        h = race["_holder"]
        if h is not None and person_fits(name, h):
            return 1, h["id"], None
        pool = [p for p in people if person_fits(name, p) and party_code(p["party"] or "") == party_code(party or "")]
        if len(pool) == 1:
            return 0, pool[0]["id"], f"Serves today {where(pool[0])}."
        return 0, None, None

    # 5. the November ballot
    cands = []
    for r in rows:
        rid = r["_race"]
        if rid is None or r["StatusDesc"] not in ON_BALLOT:
            continue
        race = races[rid]
        name = shown_name(r)
        write_in = int(r["PartyCode"] == "WRI")
        if race["partisan"]:
            party, code = r["PartyDesc"], party_code(r["PartyDesc"])
        else:
            if r["PartyCode"] not in ("NOP", "WRI"):
                checks.append(f"{rid}: a candidate for a nonpartisan office is listed under the party code {r['PartyCode']}")
            party, code = NONPARTISAN, NP_CODE
        if write_in:
            code = "W"
        inc, mid, n2 = identify(rid, name, party)
        unopposed = r["StatusDesc"] == "Unopposed"
        note = " ".join(x for x in (UNOPPOSED_NOTE if unopposed else "", WRITE_IN_NOTE if write_in else "", n2 or "") if x) or None
        cands.append([rid, "general", GENERAL, name, party, code, None, inc, write_in, None, None, "unopposed" if unopposed else None,
                      mid, SRC_LISTS, note])
    for rid, race in races.items():
        on = [c for c in cands if c[0] == rid]
        if not on:
            checks.append(f"{rid}: no candidate on the Division's list for November")
            race["note"].append("No candidate for this seat is on the Division's candidate list.")
        elif all(c[11] == "unopposed" for c in on):
            race["note"].append(SEAT_UNOPPOSED)
            if len(on) > 1:
                checks.append(f"{rid}: {len(on)} candidates on the list are all marked Unopposed")
        if race["partisan"]:
            for code in ("R", "D"):
                n = sum(1 for c in on if c[5] == code and not c[8])
                if n > 1:
                    checks.append(f"{rid}: {n} candidates of one party ({code}) on the November list")
        elif race["office_kind"] == "circuit_court" and len(on) != 2:
            checks.append(f"{rid}: {len(on)} candidates for a runoff on the November list")
        if race["level"] == "legislature":
            inc = [c for c in on if c[7]]
            if len(inc) > 1:
                for c in inc:
                    c[7], c[12] = 0, None
                checks.append(f"{rid}: more than one name on the list fits the sitting member; none is marked")

    # 6. the primary fields, with the official votes
    code_of = {"GOV": "GOV", "AG": "ATG", "CFO": "CFO", "AGR": "AGR"}

    def contest_key(rid, party):
        race = races[rid]
        if race["level"] == "statewide":
            return (code_of[rid.split("-")[-1]], 0, 0, party)
        if race["level"] == "legislature":
            return ("STS" if race["office_kind"] == "state_senate" else "STR", int(race["district"]), 0, party)
        return ("CTJ", race["_circuit"], int(race["seat"].split()[-1]), "NOP")

    listed, fields = {}, {}
    for r in rows:
        if r["_race"] is None or r["_special"]:
            continue
        listed.setdefault((r["_race"], r["PartyCode"]), []).append(r)
        if r["StatusDesc"] in ON_BALLOT + ("Defeated",) and (r["PartyCode"] in PRIMARY_PARTIES):
            fields.setdefault((r["_race"], r["PartyCode"]), []).append(r)
    used_contests = set()
    nfields, universal, unmatched, disagree = 0, 0, [], []
    for (rid, pc) in sorted(set(k for k, v in fields.items() if len(v) > 1)):
        key = contest_key(rid, pc)
        res = contests.get(key)
        field = fields[(rid, pc)]
        nfields += 1
        party = field[0]["PartyDesc"]
        # a universal primary: every candidate who qualified for the seat is of this party (no one withdrew from another)
        others = [r for r in rows if r["_race"] == rid and not r["_special"] and r["PartyCode"] != pc and r["StatusDesc"] != "Did Not Qualify"]
        uni = UNIVERSAL_NOTE.format(party={"REP": "a Republican", "DEM": "a Democrat"}.get(pc, f"of the {party}")) if not others else None
        universal += bool(uni)
        if not res or key in bad:
            checks.append(f"{rid} {pc}: " + ("the official results for this field do not reconcile" if res else
                                             "a primary field on the candidate list with no contest in the official results")
                          + "; stored without votes")
            used_contests.add(key)
            for r in field:
                inc, mid, n2 = identify(rid, shown_name(r), party)
                cands.append([rid, f"primary-{pc}", PRIMARY, shown_name(r), party, party_code(party), None, inc, 0, None, None,
                              "lost" if r["StatusDesc"] == "Defeated" else "advanced", mid, SRC_LISTS, " ".join(x for x in (uni, n2) if x) or None])
            continue
        used_contests.add(key)
        total = sum(v["votes"] for v in res.values())
        ranked = sorted(res.items(), key=lambda kv: -kv[1]["votes"])
        tie = len(ranked) > 1 and ranked[0][1]["votes"] == ranked[1][1]["votes"]
        if tie:
            checks.append(f"{rid} {pc}: the top two have the same number of votes; no one is marked as advanced")
        used = set()
        pool = [dict(first=r["NameFirst"], last=r["NameLast"], r=r) for r in listed.get((rid, pc), [])]
        for rank, ((last, first, middle), v) in enumerate(ranked):
            c = pick([p for p in pool if p["r"] in field], first, last) or pick(pool, first, last)
            if c is None:
                unmatched.append(f"{rid} {pc}: {first} {last}")
                name, status = " ".join(x for x in (first, middle.strip("'\""), last) if x), None
            else:
                if id(c["r"]) in used:
                    stop(f"two names in the {rid} {pc} results fit one candidate on the list")
                used.add(id(c["r"]))
                name, status = shown_name(c["r"]), c["r"]["StatusDesc"]
            won = rank == 0 and not tie
            note = []
            if status is not None and won != (status in ON_BALLOT) and status in ON_BALLOT + ("Defeated",):
                disagree.append(f"{rid} {pc}: {name} has {'the most' if rank == 0 else 'not the most'} votes but is \"{status}\" on the list")
            if won and status not in ON_BALLOT:
                note.append("Won the primary, but is not on the November list" + (f" (the list gives the status \"{status}\")." if status else "."))
            if status is None:
                note.append("Named as in the official results: not found on the Division's candidate list.")
            if uni:
                note.append(uni)
            inc, mid, n2 = identify(rid, name, party)
            if n2:
                note.append(n2)
            cands.append([rid, f"primary-{pc}", PRIMARY, name, party, party_code(party), None, inc, 0, v["votes"],
                          round(100 * v["votes"] / total, 1) if total else None, "advanced" if won else "lost", mid, SRC_RESULTS,
                          " ".join(note) or None])
        for r in field:
            if id(r) not in used:
                checks.append(f"{rid} {pc}: {shown_name(r)} (\"{r['StatusDesc']}\") is in the field on the list but not in the official results")

    # the circuit judges' August 18 election, for the seats in a November runoff
    for rid, race in races.items():
        if race["office_kind"] != "circuit_court":
            continue
        key = contest_key(rid, "NOP")
        res = contests.get(key)
        s = sums.get(key)
        if not res or key in bad:
            checks.append(f"{rid}: " + ("the official results of its August 18 contest do not reconcile; not stored" if res else
                                        "no August 18 contest in the official results"))
            continue
        used_contests.add(key)
        nfields += 1
        if s and "runoff" not in s["note"].lower():
            checks.append(f"{rid}: the Summary Report does not mark this contest for a runoff ({s['note']!r})")
        total = sum(v["votes"] for v in res.values())
        ranked = sorted(res.items(), key=lambda kv: -kv[1]["votes"])
        if ranked[0][1]["votes"] * 2 > total:
            checks.append(f"{rid}: the leader won a majority on August 18, yet the seat is in a runoff")
        if len(ranked) > 2 and ranked[1][1]["votes"] == ranked[2][1]["votes"]:
            checks.append(f"{rid}: second and third place have the same number of votes")
        pool = [dict(first=r["NameFirst"], last=r["NameLast"], r=r) for r in rows if r["OfficeCode"] == "CTJ" and r["_race"] == rid]
        pool += [dict(first=r["NameFirst"], last=r["NameLast"], r=r) for r in rows if r["OfficeCode"] == "CTJ" and r["_race"] is None
                 and (int(r["Juris1num"]), int(r["Juris2num"])) == (key[1], key[2])]
        on_nov = {shown_name(r) for r in rows if r["_race"] == rid and r["StatusDesc"] in ON_BALLOT}
        for rank, ((last, first, middle), v) in enumerate(ranked):
            c = pick(pool, first, last)
            name = shown_name(c["r"]) if c else " ".join(x for x in (first, middle.strip("'\""), last) if x)
            went = rank < 2
            if went != (name in on_nov):
                disagree.append(f"{rid}: {name} placed {rank + 1} on August 18 but is {'' if name in on_nov else 'not '}on the November list")
            if c is None:
                unmatched.append(f"{rid}: {first} {last}")
            cands.append([rid, "primary-NP", PRIMARY, name, NONPARTISAN, NP_CODE, None, 0, 0, v["votes"],
                          round(100 * v["votes"] / total, 1) if total else None, "advanced" if went else "lost", None, SRC_RESULTS,
                          None if c else "Named as in the official results: not found on the Division's candidate list."])
        got_counties = {geo_of.get(county_key(n)) for c in res.values() for n in c["counties"]}
        if got_counties != set(circuit_geo[race["_circuit"]]):
            checks.append(f"{rid}: the August 18 contest was counted in other counties than section 26.021 gives the circuit")

    # every circuit contest in the results sits in the counties the statute gives its circuit
    decided_ctj = 0
    for key, res in contests.items():
        if key[0] == "CTJ":
            got_counties = {geo_of.get(county_key(n)) for c in res.values() for n in c["counties"]}
            if got_counties != set(circuit_geo.get(key[1], [])):
                checks.append(f"circuit {key[1]} group {key[2]}: counted in other counties than section 26.021 gives the circuit")
            if key not in used_contests:
                decided_ctj += 1
    for key, res in contests.items():
        if key not in used_contests and key[0] != "CTJ" and len(res) > 1:
            checks.append(f"{key}: a contest in the official results with no field on the candidate list")

    # 7. the counties each district reaches: laid over the counties, and checked against the results
    senate_shp = read_shapes(SLDU_ZIP, lambda r: int(r["SLDUST"]))
    house_shp = read_shapes(SLDL_ZIP, lambda r: int(r["SLDLST"]))
    if sorted(senate_shp) != list(range(1, SENATE_SEATS + 1)) or sorted(house_shp) != list(range(1, HOUSE_SEATS + 1)):
        stop("the Census legislative district files do not hold 40 Senate and 120 House districts")
    geo_shapes = {g: rings for (g, _n), rings in counties_shp.items()}
    reach = {"STS": district_reach(geo_shapes, senate_shp), "STR": district_reach(geo_shapes, house_shp)}
    compared = 0
    for key, res in contests.items():
        if key[0] in ("STS", "STR"):
            got_counties = {geo_of.get(county_key(n)) for c in res.values() for n in c["counties"]}
            compared += 1
            if got_counties != set(reach[key[0]][key[1]]):
                checks.append(f"{key[0]} {key[1]}: the official results count it in {sorted(got_counties)}, the boundary files give "
                              f"{sorted(reach[key[0]][key[1]])}; the results' counties are used")
                reach[key[0]][key[1]] = {g: 1 for g in got_counties}
    for rid, race in races.items():
        if race["level"] == "legislature":
            code = "STS" if race["office_kind"] == "state_senate" else "STR"
            geo = sorted(reach[code][int(race["district"])])
            if not geo:
                checks.append(f"{rid}: the boundary files place this district in no county")
            race["county_ids"] = json.dumps(geo) if geo else None

    # 8. the last look at every stored text: nothing that looks like a contact detail reaches the database
    for c in cands:
        if CONTACT.search(c[3]) or CONTACT.search(c[4] or "") or (c[14] and CONTACT_NOTE.search(c[14])):
            stop(f"a stored cell for {c[0]} failed the contact-detail check (not shown); read the list again")
    for race in races.values():
        if CONTACT_NOTE.search(" ".join(race["note"])) or CONTACT.search(race["holder_name"] or ""):
            stop(f"the note or holder for {race['race_id']} failed the contact-detail check (not shown)")
    keys = [(c[0], c[1], c[3]) for c in cands]
    if len(keys) != len(set(keys)):
        dup = sorted({k for k in keys if keys.count(k) > 1})
        stop(f"two candidate rows share race, election and name ({dup[:3]})")
    on_list = sum(1 for r in rows if r["_race"] is not None and r["StatusDesc"] in ON_BALLOT)
    stored = sum(1 for c in cands if c[1] == "general")
    if on_list != stored:
        stop(f"{on_list} rows on the lists are qualified or unopposed for a stored race, {stored} stored")
    # every qualified or unopposed row on the lists is either stored or belongs to a seat not on the November ballot
    left_out = [r for r in rows if r["_race"] is None and r["StatusDesc"] in ON_BALLOT]
    if any(r["OfficeCode"] != "CTJ" for r in left_out):
        stop("a qualified row on the lists belongs to no race")

    # 8b. the county and local part: county offices, school boards, county judges and special districts (nothing above is changed by it)
    local_folder = local_folder or os.path.join(folder, "local")
    os.makedirs(local_folder, exist_ok=True)
    county_of = {county_key(n): (g, n) for g, n in counties_shp}
    local_listing, _local_path = local_lists(local_folder, say, refresh=refresh)
    notices, notice_dir = notice_set(local_folder, say, refresh=refresh)
    pages, _pages_dir = supervisor_pages(local_folder, sorted(county_of), say, refresh=refresh)
    local = local_part(local_listing, notices, notice_dir, pages, county_of, parties, circuit_geo, say)
    clash = sorted(set(races) & {r[0] for r in local["races"]})
    if clash:
        stop(f"a local race id is also a state race id ({clash[:3]})")

    # 9. write Florida's rows only, in one transaction
    cols = ("race_id", "state", "level", "office_kind", "office", "jurisdiction", "jurisdiction_id", "county_ids", "district", "seat",
            "special", "partisan", "holder_id", "holder_name", "holder_party", "election_date", "note")
    race_rows = [tuple((" ".join(r["note"]) or None) if k == "note" else r[k] for k in cols) for r in races.values()]
    place_rows = [("county", g, f"{n} County", json.dumps([g]), SRC_COUNTY) for g, n in sorted(counties_shp)]
    for rid, r in sorted(races.items()):
        if r["level"] == "legislature":
            place_rows.append(("senate" if r["office_kind"] == "state_senate" else "house", f"{STATE}-{r['district']}", r["jurisdiction"],
                               r["county_ids"], SRC_SLD))
    for c in sorted({r["_circuit"] for r in races.values() if r["office_kind"] == "circuit_court"}):
        place_rows.append(("judicial", f"{STATE}-JC{c}", f"{ordinal(c)} Judicial Circuit", json.dumps(circuit_geo[c]), SRC_STATUTES))
    for n in sorted({int(r["district"]) for r in races.values() if r["office_kind"] == "court_of_appeals_retention"}):
        place_rows.append(("appellate_district", f"{STATE}-DCA{n}", f"{ORDINAL[n]} Appellate District",
                           json.dumps(sorted(g for c in dcas[n] for g in circuit_geo[c])), SRC_STATUTES))
    if len({(p[0], p[1]) for p in place_rows}) != len(place_rows):
        stop("two places share a kind and id")
    have_place = {(p[0], p[1]) for p in place_rows}
    place_rows += [p + (SRC_STATUTES,) for p in local["court_places"] if (p[0], p[1]) not in have_place]
    place_rows += local["places"]
    if len({(p[0], p[1]) for p in place_rows}) != len(place_rows):
        stop("a local place shares a kind and id with another place")

    gen_c = [c for c in cands if c[1] == "general"]
    prim = [c for c in cands if c[1] != "general"]
    lists_note = "; ".join(f"{x['label']} ({x['elecID']}), {x['office']}: {len(x['rows'])} rows, {x['bytes']:,} bytes as received, SHA-256 "
                           f"{x['sha256']}" for x in lists["lists"])
    off_counts = {}
    for r in rows:
        if r["StatusDesc"] not in ON_BALLOT:
            off_counts[r["StatusDesc"]] = off_counts.get(r["StatusDesc"], 0) + 1
    decided_ctj_listed = len(left_out)
    from_party_list = sorted({r["PartyCode"] for r in rows if r.get("_party_from")})
    sources = [
        (SRC_LISTS, STATE, "official candidate list", AGENCY,
         "Candidate Tracking System: candidate lists, 2026 Election (Governor and Cabinet; Senate and House; Judicial Offices) and the "
         "November 3, 2026 special elections, state candidates, all statuses", PAGE, "", lists["fetched"][:10],
         hashlib.sha256(json.dumps(lists["lists"], sort_keys=True).encode()).hexdigest(), sum(len(x["rows"]) for x in lists["lists"]),
         f"Posted to {POST} (tab-separated). Each file was held in memory only to cut every row down, by heading, to ElectionID, "
         "OfficeCode, OfficeDesc, Juris1num, Juris2num, StatusCode, StatusDesc, PartyCode, PartyDesc, NameLast, NameFirst and NameMiddle; "
         "voter ID and account numbers, addresses, cities, ZIP codes, counties of residence, telephone numbers, treasurers and e-mail "
         "were never read or kept, and the files were not saved (the SHA-256 above is of the kept columns; each file's own is listed "
         f"here). {lists_note}. Qualified or Unopposed rows are the November ballot; not on it: "
         + ", ".join(f"{k} {v}" for k, v in sorted(off_counts.items()))
         + f"; {decided_ctj_listed} circuit judges elected unopposed or on August 18 are not stored (not on the November ballot). "
         "The 2024 list is read only for which Senate districts were elected that year (the odd-numbered ones). No ballot order is "
         "printed, so none is stored."
         + (f" Party names for the code(s) {', '.join(from_party_list)} are from the Division's list of political parties "
            f"({SRC_PARTIES})." if from_party_list else "")),
        (SRC_RESULTS, STATE, "official results", AGENCY,
         f"Election Results Reporting System: {RES_TITLE}, Data Download Utility (official results extract): state offices",
         RES_DOWNLOAD, "", mtime(res_files["extract"]), sha(res_files["extract"]), sum(1 for c in prim if c[13] == SRC_RESULTS),
         "The same file the federal loader keeps (OfficialResults=Y), one row per county, party, contest and candidate; the Governor and "
         "Cabinet, Senate, House and circuit judge contests are read. Votes are the county rows summed, checked against the Division's "
         "Summary Reports (" + ", ".join(SRC_SUM.format(race=r.lower(), party=p.lower()) for r, p in SUMMARIES) + ")"
         + ("; every candidate's county sum equals the statewide Total there and every precinct reported." if not res_checks else
            "; differences (fields stored without votes): " + "; ".join(res_checks) + ".")
         + " The results carry no write-in line (write-in candidates are not on a Florida primary ballot), so shares are of the "
         "candidates' votes. The names stored are the candidate list's. A field is a party primary with two candidates or more; "
         f"{decided_ctj} circuit judge contests decided on August 18 are not stored."),
        (SRC_PARTIES, STATE, "party list", AGENCY, "Political Parties (major and minor political parties registered in Florida)", PARTIES_URL,
         "", mtime(parties_path), sha(parties_path), len(parties),
         "Read for a party the candidate list names by its code alone."),
        (SRC_STATUTES, STATE, "statute", "The Florida Legislature (Online Sunshine)",
         "Florida Statutes, sections 26.021 (judicial circuits) and 35.02 to 35.044 (appellate districts)",
         STATUTE_URL.format(ch="0026", sec="0026.021"), "", mtime(statute_paths[0][2]),
         hashlib.sha256(b"".join(open(p, "rb").read() for _s, _u, p in statute_paths)).hexdigest(), len(statute_paths),
         "The counties of each of the twenty circuits and the circuits of each of the six appellate districts, for the counties a court "
         "race reaches; for every circuit with an August 18 contest, the statute's counties are exactly those the contest was counted in. "
         "Pages: "
         + "; ".join(u for _s, u, _p in statute_paths)),
        (SRC_ROSTER, STATE, "member roster", "Open States people project (CC0), as loaded into state_fl.sqlite",
         "Sitting Florida legislators and statewide officials", "https://github.com/openstates/people", "", mtime(roster_db), sha(roster_db),
         len(legs) + len(offs), "Who holds each seat today, and which candidate is a sitting member (same chamber and district, the name "
         "fits, one fit only; a member of another seat only when the name fits exactly one sitting legislator or official of the same "
         "party, with a note). The roster's elected statewide officials are the Governor and the Attorney General; the Chief Financial "
         "Officer's and the Commissioner of Agriculture's holders are left empty. Names, party and ids only. Not an official record."),
        (SRC_COUNTY, STATE, "county codes", "U.S. Census Bureau", "Cartographic boundary file, counties, 2024 (1:500,000)",
         CENSUS_URL + "cb_2024_us_county_500k.zip", "2024", mtime(COUNTY_ZIP), sha(COUNTY_ZIP), TOTAL_COUNTIES,
         "Five-digit county codes (GEOID) for Florida's 67 counties, matched by name to the results' county rows and the statute's names."),
        (SRC_SLD, STATE, "district boundaries", "U.S. Census Bureau",
         "Cartographic boundary files, State Legislative Districts (upper and lower chambers), Florida, 2024 (1:500,000)",
         CENSUS_URL + f"cb_2024_{FIPS}_sldu_500k.zip", "2024", mtime(SLDU_ZIP),
         hashlib.sha256(open(SLDU_ZIP, "rb").read() + open(SLDL_ZIP, "rb").read()).hexdigest(), SENATE_SEATS + HOUSE_SEATS,
         "Which counties each district reaches (derived): each district laid over the county file on a grid of about 220 metres, counting "
         "only cells more than about half a kilometre inside a county, and a county kept with at least 25 such cells (about 1.2 square "
         f"kilometres). Checked against the official results for the {compared} districts with a primary contest: "
         + ("every one agrees." if not any("boundary files give" in c for c in checks) else "differences are listed in the loader's report, "
            "and the results' counties are used for them.")
         + f" Lower chamber file: {CENSUS_URL}cb_2024_{FIPS}_sldl_500k.zip"),
    ]
    for (race, party), path in sum_paths.items():
        sources.append((SRC_SUM.format(race=race.lower(), party=party.lower()), STATE, "official results", AGENCY,
                        f"Election Results Reporting System: {RES_TITLE}, "
                        + {"REP": "Republican Primary", "DEM": "Democratic Primary", "NOP": "Nonpartisan"}[party]
                        + ", Summary Report, " + {"CAB": "Governor and Cabinet", "LEG": "Senate and House", "JUD": "Judicial Offices"}[race]
                        + " (Official Results)", SUM_URL.format(race=race, party=party), "", mtime(path), sha(path),
                        sum_rows[(race, party)],
                        "Headed \"Official Results\". Statewide totals per candidate, used to check the county sums of the results extract "
                        f"({SRC_RESULTS}); the line under a contest (\"Runoff Election Indicated\") marks a circuit judge runoff."))

    sources += local["sources"]
    if len({s[0] for s in sources}) != len(sources):
        stop("two sources share an id")
    gap_rows = list({(g[0], g[1], g[2], g[4]): g for g in local["gaps"]}.values())
    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA + EXTRA_SCHEMA)
    with con:
        con.execute("DELETE FROM sl_candidates WHERE race_id IN (SELECT race_id FROM sl_races WHERE state = ?) OR race_id LIKE ?",
                    (STATE, f"2026-{STATE}-%"))
        con.execute("DELETE FROM sl_races WHERE state = ?", (STATE,))
        con.execute("DELETE FROM sl_sources WHERE state = ?", (STATE,))
        con.execute("DELETE FROM sl_places WHERE source_id LIKE ?", (f"{STATE.lower()}-%",))
        con.execute("DELETE FROM sl_gaps WHERE state = ?", (STATE,))
        con.execute("DELETE FROM sl_notes WHERE state = ?", (STATE,))
        con.executemany("INSERT INTO sl_races VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", race_rows + [tuple(r) for r in local["races"]])
        con.executemany("INSERT INTO sl_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        [tuple(c) for c in cands] + [tuple(c) for c in local["cands"]])
        con.executemany("INSERT INTO sl_gaps VALUES (?,?,?,?,?,?,?)", gap_rows)
        con.executemany("INSERT INTO sl_notes VALUES (?,?,?,?,?)", local["notes"])
        con.executemany("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", sources)
        con.executemany("INSERT INTO sl_places VALUES (?,?,?,?,?)", place_rows)
    con.close()

    # 10. say what happened
    by = lambda rows_, kind: sum(1 for c in rows_ if races[c[0]]["office_kind"] == kind)
    lvl = lambda rows_, level: sum(1 for c in rows_ if races[c[0]]["level"] == level)
    nk = lambda kind: sum(1 for r in races.values() if r["office_kind"] == kind)
    unopp = sum(1 for c in gen_c if c[11] == "unopposed")
    nlevel = lambda level: sum(1 for r in races.values() if r["level"] == level)
    say(f"    Florida state offices: {len(races)} races ({nlevel('statewide')} statewide; "
        f"{nk('state_senate')} Senate incl. {sum(1 for r in races.values() if r['special'])} special; {nk('state_house')} House; "
        f"{nlevel('court')} court: {nk('supreme_court_retention')} Supreme Court and "
        f"{nk('court_of_appeals_retention')} appeal court retention votes, {nk('circuit_court')} circuit runoffs); {len(gen_c)} November "
        f"candidates (statewide {lvl(gen_c, 'statewide')}, Senate {by(gen_c, 'state_senate')}, House {by(gen_c, 'state_house')}, court "
        f"{lvl(gen_c, 'court')}; {unopp} unopposed, off the ballot); {nfields} primary fields ({universal} universal), {len(prim)} "
        f"primary rows (statewide {lvl(prim, 'statewide')}, Senate {by(prim, 'state_senate')}, House {by(prim, 'state_house')}, court "
        f"{lvl(prim, 'court')}), " + ("official votes reconciled" if not res_checks else f"{len(res_checks)} results checks failed"))
    for c in cands:
        if c[12]:
            matched.append(f"{c[0]} {c[1]}: {c[3]} -> {c[12]}{' (holds this seat)' if c[7] else ''}")
    for line in matched:
        say(f"      matched: {line}")
    for line in [f"not matched to the candidate list: {u}" for u in unmatched] + disagree + checks:
        say(f"      check: {line}")
    lc = local["counts"]
    by_level = ", ".join(f"{k} {v:,}" for k, v in sorted(lc["by_level"].items()))
    off_words = ", ".join(f"{k} {v}" for k, v in sorted(lc["off"].items()))
    say(f"    Florida county and local offices: {lc['local_races']:,} contests and {lc['county_court']} county judgeships ({by_level}), "
        f"{lc['local_cands'] + lc['court_cands']:,} candidates, a contest in {lc['counties_reached']} of {TOTAL_COUNTIES} counties; the local "
        f"list has {lc['list_rows']:,} rows: {lc['placed']:,} placed, {lc['stored']:,} stored, {lc['dup_rows']} repeated, "
        f"{sum(lc['off'].values()):,} off the ballot ({off_words}), {lc['unplaced_on_ballot']} on the ballot but not placed; "
        f"{lc['unopposed_seats']:,} seats unopposed, {lc['decided']} settled on August 18, {lc['contested']} with a name on the ballot; "
        f"{len(gap_rows)} gaps ({lc['race_gaps']} of them contests)")
    for line in local["checks"]:
        say(f"      check: {line}")
    return dict(races=len(races), general=len(gen_c), primary=len(prim), fields=nfields, checks=checks + disagree + unmatched, local=lc,
                local_checks=local["checks"])


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


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Florida's state, county and local races on the November 3, 2026 ballot")
    ap.add_argument("db", help="the state-and-local ballot database to write Florida's rows into")
    ap.add_argument("--refresh", action="store_true",
                    help="download the candidate lists, the notices' page and the supervisors' pages again even when the cached copies are fresh")
    a = ap.parse_args()
    load(a.db, refresh=a.refresh)
