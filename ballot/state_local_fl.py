"""
ballot/state_local_fl.py - Florida's state races on the November 3, 2026 ballot, into ballot_local_2026.sqlite
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

    python -m ballot.state_local_fl <path to a test database> [--refresh]
"""

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


# ------------------------------------------------------------------------------------------------ loading

def load(db_path, say=print, folder=FOLDER, roster_db=ROSTER, refresh=False):
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
    return dict(races=len(races), general=len(gen_c), primary=len(prim), fields=nfields, checks=checks + disagree + unmatched)


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
    ap = argparse.ArgumentParser(description="Florida's state races on the November 3, 2026 ballot")
    ap.add_argument("db", help="the state-and-local ballot database to write Florida's rows into")
    ap.add_argument("--refresh", action="store_true", help="download the candidate lists again even when the cached copy is fresh")
    a = ap.parse_args()
    load(a.db, refresh=a.refresh)
