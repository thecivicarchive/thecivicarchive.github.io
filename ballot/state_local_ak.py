"""
ballot/state_local_ak.py - Alaska's state races on the November 3, 2026 ballot, from the Division of Elections' own lists,
ballots and official results (elections.alaska.gov; the Division is part of the Office of the Lieutenant Governor), into
ballot_local_2026.sqlite. The federal ballot database (ballot_2026.sqlite) is never opened here; the U.S. Senator and U.S.
Representative rows of the same files are left to ballot/lists/ak.py and only counted.

    python -m ballot.state_local_ak <database>

What is on the ballot
---------------------
  - Governor and Lieutenant Governor, one ticket (the lists, the ballots and the results all print each candidate for
    Governor with a running mate): race 2026-AK-GOV, the candidate is the name for Governor and the running mate is named
    in the candidate's note. Alaska's Attorney General and other executive officers are appointed, so no other statewide
    office is on the list.
  - Ten of the twenty Senate seats (four-year terms, half elected every two years): the ten the 2026 lists name (A, C, E,
    G, I, K, M, O, Q, S). Control: the Division's 2024 General Election list names the other ten, and the two together
    are all twenty.
  - All forty House seats (two-year terms).
  - The judicial retention votes on the list (Yes or No on keeping a judge): one Justice of the Supreme Court
    (statewide), judges of the Superior Court and of the District Court (each voted on in its own judicial district).

Sources, all the Division's own
-------------------------------
  General list   "2026 General Election" candidates, www.elections.alaska.gov/candidates/?election=26genr, read through its own
                 pager (frm-page-407=1, 2, 3; every page repeats the judicial sections, which must agree). One section per
                 office (GOVERNOR / LIEUTENANT GOVERNOR, SENATE DISTRICT A, HOUSE DISTRICT 01, SUPREME COURT, STATE SUPERIOR
                 COURT 01 ...), each a table whose columns are Candidate Name on Ballot, Campaign Address (or Address), Contact
                 and Election Pamphlet Information. Only the Candidate Name on Ballot cell is ever turned into text, found by
                 its heading: the name as printed, the registration and the status in brackets, the red "Certified Write-In"
                 mark and the "Incumbent" mark. The address, contact and pamphlet cells are never read, printed or kept; the
                 cache (ballot_cache/ak/sl_ak_2026_general_state.json) holds only the name cells' fields for the state
                 sections, a count of the federal rows and each page's SHA-256.
  Primary list   "2026 Primary Election" candidates, ...?election=26prim: one flat table, five cells a row, of which only the
                 first two are read and each must have the shape expected (office|district; name|registration|status|Yes or
                 No for incumbent); the address, contact and pamphlet cells are never turned into text. Cached as the kept
                 cells of the state rows only.
  Results        the August 18, 2026 primary's official results, the files the federal loader finds on the results page
                 (which must say "Results Status: Official") and caches: "Results Per Precinct" (GA_ENR_Precinct_State_of_
                 Alaska.csv; columns taken by name: Precinct_name, Contest_title, candidate_name, Candidate_Type, Party_Code,
                 total_votes) and the "Summary" (ElectionSummaryReportRPT.pdf, "OFFICIAL RESULTS", read with ballot/pdftext.py).
                 Every candidate's precinct sum and every contest's total must equal the Summary's figures exactly.
  Sample ballots the 2026 General Election's ranked-choice sample ballots, one per house district (two where a house district
                 lies in two judicial districts: 46 PDFs, all linked from www.elections.alaska.gov/sample-ballots/ballot/zk4o0).
                 They print candidates' names and registrations only. Controls: each ballot's own house and judicial district;
                 its Governor, State Senator and State Representative names are exactly the general list's printed (not
                 write-in) candidates, with the same registrations; its retention questions are exactly the list's judges for
                 its judicial district. The ballots also give the House ballot order (see below) and which house districts
                 vote in each Senate race and each judicial district.
  Primary ballot the 2026 Primary Election sample ballot for House District 1 (election/2026/Primary/SampleBallots/HD1.pdf, the
                 Division's own address for it; the primary's sample ballot page is no longer listed). Read for the Governor /
                 Lieutenant Governor contest only, which is statewide: its tickets must be exactly the results'; it names the one
                 ticket the primary list no longer carries (the results print surnames only).
  2024 list      "2024 General Election" candidates (...?election=24genr): only the section headings are read, for which Senate
                 seats were elected in 2024. No name, address or contact cell of that list is turned into text.
  Roster         who holds each seat today, from the Open States roster in state_ak.sqlite (legislators with is_current = 1, by
                 chamber and district; officials for the Governor and Lieutenant Governor). Only ids, names, other name forms,
                 party, chamber and district are selected.

Alaska's primary is top-four: every candidate, of every registration, is on one primary ballot, and the four with the most
votes advance to the ranked-choice general election. The primary takes no write-in votes, so a field's total is its
candidates' votes. A primary field (election "primary") is stored where two or more candidates were on the August ballot,
with official votes; the top four are "advanced". When the November list names a later finisher (a top-four finisher
withdrew and another primary candidate was put on the ballot in that place), that candidate is also "advanced" and the
notes on both say only what the lists show. Certified write-in candidates on the November list are stored with write_in 1;
their names are not printed on the ballot.

Ballot order: the sample ballot page says each house district gets its own ballot, candidates for state representative are
listed in a random alphabetical order the Division determines, candidates for state senate are in one order in odd house
districts and rotate in even ones, and all other candidates begin in alphabetical order in House District 1 and rotate from
there. So ballot_order is stored for House races only, as printed on that district's sample ballot; Senate, Governor and
retention rows have none (the page shows them by surname).

Names are turned round from "Last, First" as in ballot/lists/ak.py; registrations are shown as the list prints them
(Registered Republican, Nonpartisan, Undeclared ...). Retention votes are nonpartisan offices ("Nonpartisan office", N).

Privacy: only office, district, candidate name, registration, ballot order, status, write-in and incumbent marks and votes are
read. No address, city, ZIP code, phone, website, e-mail or treasurer is read, printed, logged, cached or stored, and no photo,
age, biography or money reaches the database.
"""

import collections
import csv
import datetime as dt
import hashlib
import html as H
import json
import os
import re
import sqlite3
import sys
import time
from urllib.error import HTTPError
from urllib.parse import urljoin

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from ballot.common import CACHE, fold, name_parts  # noqa: E402
from ballot.lists import ak as A  # noqa: E402
from ballot.match import fits  # noqa: E402
from ballot.pdftext import PDF, join, lines, page_runs  # noqa: E402
from states import net  # noqa: E402

STATE = "AK"
NAME = "Alaska"
GENERAL, PRIMARY = "2026-11-03", A.PRIMARY
ROSTER = os.path.join(HERE, "state_ak.sqlite")
AGENCY = A.AGENCY
PAGER = "frm-page-407"
LIST_2024 = A.SITE + "/candidates/?election=24genr"
PRIMARY_BALLOT = A.SITE + "/election/2026/Primary/SampleBallots/HD1.pdf"
SRC_GEN, SRC_PRI = "ak-doe-2026-sl-general-list", "ak-doe-2026-sl-primary-list"
SRC_CSV, SRC_SUM = "ak-doe-2026-sl-primary-precinct", "ak-doe-2026-sl-primary-summary"
SRC_BALLOTS, SRC_PBALLOT = "ak-doe-2026-sl-sample-ballots", "ak-doe-2026-sl-primary-sample-ballot-hd1"
SRC_2024, SRC_ROSTER = "ak-doe-2024-sl-general-list-headings", "ak-openstates-roster"
NONPARTISAN = "Nonpartisan office"
SENATE_LETTERS = [chr(c) for c in range(ord("A"), ord("T") + 1)]
HOUSE_SEATS = 40
ORDINAL_JD = {"1": "First", "2": "Second", "3": "Third", "4": "Fourth"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS sl_races (race_id TEXT PRIMARY KEY, state TEXT NOT NULL, level TEXT NOT NULL, office_kind TEXT NOT NULL, office TEXT NOT NULL,
  jurisdiction TEXT, jurisdiction_id TEXT, county_ids TEXT, district TEXT, seat TEXT, special INTEGER NOT NULL DEFAULT 0, partisan INTEGER NOT NULL,
  holder_id TEXT, holder_name TEXT, holder_party TEXT, election_date TEXT NOT NULL, note TEXT);
CREATE TABLE IF NOT EXISTS sl_candidates (race_id TEXT NOT NULL, election TEXT NOT NULL, election_date TEXT, name TEXT NOT NULL, party TEXT, party_code TEXT,
  ballot_order INTEGER, incumbent INTEGER NOT NULL DEFAULT 0, write_in INTEGER NOT NULL DEFAULT 0, votes INTEGER, pct REAL, outcome TEXT,
  state_member_id TEXT, source_id TEXT, note TEXT, PRIMARY KEY (race_id, election, name));
CREATE TABLE IF NOT EXISTS sl_sources (source_id TEXT PRIMARY KEY, state TEXT, kind TEXT, agency TEXT, title TEXT, url TEXT, published TEXT, fetched TEXT, sha256 TEXT, rows INTEGER, note TEXT);
CREATE TABLE IF NOT EXISTS sl_places (kind TEXT NOT NULL, id TEXT NOT NULL, name TEXT NOT NULL, county_ids TEXT, source_id TEXT, PRIMARY KEY (kind, id));
"""

TOP_FOUR = ("Alaska's primary is top-four: every candidate, of every registration, was on one August 18 ballot, and the four with the "
            "most votes advanced to the November ballot, which is ranked-choice. Alaska prints each candidate's party registration, or "
            "Nonpartisan or Undeclared; it is not a party's nomination.")
SENATE_NOTE = ("Alaska's senators serve four-year terms and half the Senate is elected every two years. This seat is on the 2026 ballot: "
               "the Division's 2026 lists name it, and its 2024 General Election list named the other ten seats.")
HOUSE_NOTE = "Alaska's representatives serve two-year terms, so all forty House seats are on the ballot every even year."
GOV_NOTE = ("The Governor and Lieutenant Governor are elected together: the Division's lists, ballots and results print each candidate "
            "for Governor with a running mate for Lieutenant Governor, and one vote (one ranking) goes to the pair. The running mate is "
            "named in each candidate's note.")
RETENTION_NOTE = ("A retention vote: voters answer Yes or No on keeping this judge in office. A nonpartisan office: no party is printed "
                  "on the ballot.")
ORDER_HOUSE = ("Ballot order as printed on the Division's sample ballot for House District {d}, where the Division lists candidates for "
               "state representative in a random alphabetical order of its choosing.")
ORDER_NONE = ("No ballot order is stored: {why} (the Division's sample ballot page says so), so the page shows the candidates by "
              "surname.")
WHY_SENATE = "candidates for state senate are listed in one order in odd house districts and rotate in even ones"
WHY_OTHER = "these candidates begin in alphabetical order in House District 1 and rotate from district to district"
WRITE_IN = "Certified write-in candidate: the name is not printed on the ballot."

OFFICE_HEAD = re.compile(r"(GOVERNOR / LIEUTENANT GOVERNOR)|SENATE DISTRICT ([A-T])|HOUSE DISTRICT (\d{2})|(SUPREME COURT)|"
                         r"STATE (SUPERIOR|DISTRICT) COURT (0[1-4])|(UNITED STATES (?:SENATOR|REPRESENTATIVE))")
CONTEST = re.compile(r"(Governor / Lieutenant Governor)|Senate District ([A-T])|House District (\d{1,2})")
BALLOT_HEAD = re.compile(r"(Governor / Lieutenant Governor)|State Senator District ([A-T])|State Representative District (\d{1,2})|"
                         r"(United States Senator|United States Representative)")
SKIP_LINE = re.compile(r"\d(?: \d)*|\d(?:st|nd|rd|th)|Choice|\(Vote for \w+\)")
RETAIN = re.compile(r"Shall (.+?) be retained as (judge|justice) of the (superior|district|supreme) court for (\w+) years\?")


class Report(list):
    def add(self, line):
        self.append(line)


# ------------------------------------------------------------------------------------------------------------ helpers

def fresh(path, days):
    return os.path.exists(path) and time.time() - os.path.getmtime(path) < days * 86400


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def mtime(path):
    return dt.datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d")


def fetch(url, say, accept="text/html"):
    """One request, asked at most twice more on a refusal or a server error; a challenge page is never worked around."""
    for attempt in range(3):
        try:
            return net.get(url, accept=accept)
        except HTTPError as e:
            if e.code not in (403, 429, 500, 502, 503, 504) or attempt == 2:
                raise SystemExit(f"Alaska (state races): {url} answered HTTP {e.code}; stopping (a browser would be needed to go further)")
            say(f"      {url}: HTTP {e.code}; asking again in {10 * (attempt + 1)} s")
            time.sleep(10 * (attempt + 1))


text, straight, turn, code_of = A.text, A.straight, A.turn, A.code_of


def reg_norm(label):
    return re.sub(r"\s*/\s*", "/", (label or "").strip())


def split_ticket(name):
    parts = [p.strip() for p in straight(name).split("/")]
    if len(parts) != 2 or not all(parts):
        raise SystemExit(f"Alaska (state races): a Governor / Lieutenant Governor name that is not two names ({len(parts)} parts)")
    return parts


def surname_key(part):
    """The family name of 'Last, First' or of a results surname ('Parkin IV'), suffixes set aside, folded."""
    last = straight(part).split(",")[0]
    words = [w for w in fold(last).split() if w not in ("jr", "sr", "ii", "iii", "iv", "v")]
    return " ".join(words)


def ticket_key(name):
    gov, ltg = split_ticket(name)
    return surname_key(gov), surname_key(ltg)


def person_key(race, name):
    return ticket_key(name) if race == f"2026-{STATE}-GOV" else fold(straight(name))


def turned_ticket(name):
    gov, ltg = split_ticket(name)
    return turn(gov), turn(ltg)


def judge_parts(name):
    """(given names, family name) of a judge written "First M. Last "Nickname"" (the nickname set aside)."""
    return name_parts(re.sub(r'"[^"]*"', " ", straight(name)))


def judge_key(name):
    given, fam = judge_parts(name)
    return fam, given[0] if given else ""


def split_regs(label, n=2):
    parts = [p.strip() for p in (label or "").split("/")]
    return parts if len(parts) == n else [label.strip()] * n


# ------------------------------------------------------------------------------------------------------- the lists

def general_list(folder, say):
    """The state sections of the general list, the name cell only, every page through the list's own pager."""
    path = os.path.join(folder, "sl_ak_2026_general_state.json")
    if fresh(path, 2):
        return path, json.load(open(path, encoding="utf-8"))
    rows, federal, pages_sha, judicial, seen = [], 0, [], None, set()
    page_no, last = 1, 1
    while page_no <= last:
        raw = fetch(f"{A.GENERAL_URL}&{PAGER}={page_no}", say)
        pages_sha.append(hashlib.sha256(raw).hexdigest())
        page = raw.decode("utf-8", "replace")
        if "<h2>2026 General Election</h2>" not in page:
            raise SystemExit(f"Alaska (state races): {A.GENERAL_URL} is no longer the 2026 General Election candidate list")
        nums = [int(n) for n in re.findall(PAGER + r"=(\d+)", page)]
        last = max([last] + nums)
        page_judicial = []
        for sec in re.findall(r'<section class="candidates-table">(.*?)</section>', page, re.S):
            head = re.search(r"<h4[^>]*>(.*?)</h4>", sec, re.S)
            office = text(head.group(1)) if head else ""
            m = OFFICE_HEAD.fullmatch(office)
            if not m:
                raise SystemExit(f"Alaska (state races): a section of the general list this loader does not know: {office!r}")
            table = re.search(r"<table[^>]*>(.*?)</table>", sec, re.S)
            heads = [text(h) for h in re.findall(r"<th[^>]*>(.*?)</th>", table.group(1), re.S)] if table else []
            if heads.count(A.NAME_COL) != 1:
                raise SystemExit(f"Alaska (state races): the {office} table no longer has one '{A.NAME_COL}' column")
            k = heads.index(A.NAME_COL)
            body = [tr for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", table.group(1), re.S) if "<th" not in tr]
            if m.group(7):                                           # the federal races: counted only
                federal += len(body)
                continue
            is_court = bool(m.group(4) or m.group(5))
            if not is_court:
                if office in seen:
                    raise SystemExit(f"Alaska (state races): the general list has two sections headed {office}")
                seen.add(office)
            for tr in body:
                cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
                if len(cells) != len(heads):
                    raise SystemExit(f"Alaska (state races): a row of the {office} table does not line up with its headings")
                cell = cells[k]                                      # the name cell only; the others are never turned into text
                name = re.search(r"<strong>(.*?)</strong>", cell, re.S)
                small = re.search(r"<small>(.*?)</small>", cell, re.S)
                marks = [t for t in (text(x) for x in re.findall(r'<span style="color: #e50000; font-weight: bold;">(.*?)</span>', cell, re.S)) if t]
                if not name or not small:
                    raise SystemExit(f"Alaska (state races): a name in the {office} table could not be read")
                groups = [g.strip() for g in re.findall(r"\(([^()]*)\)", text(small.group(1)))]
                if any(x != "Certified Write-In" for x in marks):
                    raise SystemExit(f"Alaska (state races): a mark on the {office} list that is not read ({marks})")
                if is_court:
                    if len(groups) != 1:
                        raise SystemExit(f"Alaska (state races): a judge's status on the {office} list could not be read")
                    party, status = "", groups[0]
                else:
                    if len(groups) != 2 or not groups[0]:
                        raise SystemExit(f"Alaska (state races): a registration and status for {office} could not be read")
                    party, status = groups
                row = {"office": office, "name": straight(text(name.group(1))), "party": party, "status": status,
                       "write_in": bool(marks), "incumbent": bool(re.search(r"<em>\s*Incumbent\s*</em>", cell))}
                (page_judicial if is_court else rows).append(row)
        if judicial is None:
            judicial = page_judicial
        elif page_judicial != judicial:
            raise SystemExit("Alaska (state races): the judicial sections differ from page to page of the general list")
        page_no += 1
        time.sleep(1)
    kept = {"title": "2026 General Election", "url": A.GENERAL_URL, "pages": last, "page_sha256": pages_sha,
            "federal_rows": federal, "read": dt.date.today().isoformat(), "rows": rows + (judicial or [])}
    json.dump(kept, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    say(f"      2026 General Election list: {last} pages, {len(kept['rows'])} state rows kept, {federal} federal rows counted")
    return path, kept


def primary_list(folder, say):
    """The state rows of the primary list, the first two cells only."""
    path = os.path.join(folder, "sl_ak_2026_primary_state.json")
    if fresh(path, 30):
        return path, json.load(open(path, encoding="utf-8"))
    raw = fetch(A.PRIMARY_URL, say)
    page = raw.decode("utf-8", "replace")
    if "<h2>2026 Primary Election</h2>" not in page:
        raise SystemExit(f"Alaska (state races): {A.PRIMARY_URL} is no longer the 2026 Primary Election candidate list")
    if re.search(PAGER + r"=\d", page):
        raise SystemExit("Alaska (state races): the primary list now has pages; this loader reads one")
    m = re.search(r"last updated at:\s*(?:<[^>]+>\s*)*([A-Z][a-z]+ \d{1,2}, 20\d\d)", page)
    updated = time.strftime("%Y-%m-%d", time.strptime(m.group(1), "%B %d, %Y")) if m else ""
    table = re.search(r'<table id="cand"[^>]*>(.*?)</table>', page, re.S)
    if not table:
        raise SystemExit("Alaska (state races): the primary list's table is gone")
    rows, total, federal = [], 0, 0
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", table.group(1), re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        if len(cells) != 5:
            raise SystemExit(f"Alaska (state races): a row of the primary list has {len(cells)} cells, not five")
        total += 1
        where = [text(x) for x in cells[0].split("|")]               # office | district
        who = [text(x) for x in cells[1].split("|")]                 # name | registration | status | incumbent
        if len(where) != 2 or len(who) != 4 or who[3] not in ("Yes", "No") or not (who[2] in A.STATUSES or A.OFF.search(who[2])):
            raise SystemExit("Alaska (state races): a row of the primary list no longer has the shape read")
        if where[0].startswith("UNITED STATES"):
            federal += 1
            continue
        if where[0] not in ("GOVERNOR / LIEUTENANT GOVERNOR", "STATE SENATOR", "STATE REPRESENTATIVE"):
            raise SystemExit(f"Alaska (state races): an office on the primary list this loader does not know: {where[0]!r}")
        rows.append({"office": where[0], "district": where[1], "name": straight(who[0]), "party": who[1], "status": who[2],
                     "incumbent": who[3] == "Yes"})
    kept = {"title": "2026 Primary Election", "url": A.PRIMARY_URL, "updated": updated, "items": total, "federal_rows": federal,
            "page_sha256": hashlib.sha256(raw).hexdigest(), "read": dt.date.today().isoformat(), "rows": rows}
    json.dump(kept, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    say(f"      2026 Primary Election list: {total} rows, {len(rows)} state rows kept")
    return path, kept


def senate_2024(folder, say):
    """The Senate sections the 2024 General Election list heads; headings only."""
    path = os.path.join(folder, "sl_ak_2024_general_headings.json")
    if fresh(path, 365):
        return path, json.load(open(path, encoding="utf-8"))
    heads, page_no, last, pages_sha = [], 1, 1, []
    while page_no <= last:
        raw = fetch(f"{LIST_2024}&{PAGER}={page_no}", say)
        pages_sha.append(hashlib.sha256(raw).hexdigest())
        page = raw.decode("utf-8", "replace")
        if "<h2>2024 General Election</h2>" not in page:
            raise SystemExit(f"Alaska (state races): {LIST_2024} is no longer the 2024 General Election candidate list")
        last = max([last] + [int(n) for n in re.findall(PAGER + r"=(\d+)", page)])
        for h in re.findall(r'<section class="candidates-table">\s*<h4[^>]*>(.*?)</h4>', page, re.S):
            heads.append(text(h))
        page_no += 1
        time.sleep(1)
    senate = sorted({m.group(1) for h in heads for m in [re.fullmatch(r"SENATE DISTRICT ([A-T])", h)] if m})
    kept = {"url": LIST_2024, "pages": last, "page_sha256": pages_sha, "read": dt.date.today().isoformat(), "senate": senate,
            "sections": len(heads)}
    json.dump(kept, open(path, "w", encoding="utf-8"), indent=1)
    say(f"      2024 General Election list: {last} pages, Senate seats {''.join(senate)}")
    return path, kept


# ----------------------------------------------------------------------------------------------------- the results

def precinct_votes(path):
    """{contest title: {key: [name as printed, party code, votes]}} for the state contests, summed over every precinct."""
    out, precincts = {}, set()
    with open(path, encoding="utf-8-sig", newline="") as fh:
        rd = csv.reader(fh)
        heads = [h.strip() for h in next(rd)]
        if not all(heads.count(k) == 1 for k in A.CSV_KEEP):
            raise SystemExit("Alaska (state races): the precinct file's columns changed")
        idx = {k: heads.index(k) for k in A.CSV_KEEP}
        for r in rd:
            title = r[idx["Contest_title"]].strip()
            m = CONTEST.fullmatch(title)
            if not m:
                continue
            if r[idx["Candidate_Type"]].strip() != "C":
                raise SystemExit(f"Alaska (state races): a {title} row of the precinct file with a candidate type not read")
            name = re.sub(r"\s+", " ", straight(r[idx["candidate_name"]])).strip()
            rid = race_of_contest(m)
            key = person_key(rid, name)
            code = r[idx["Party_Code"]].strip()
            cell = out.setdefault(rid, {}).setdefault(key, [name, code, 0])
            if cell[1] != code or cell[0] != name:
                raise SystemExit(f"Alaska (state races): {name} ({title}) has two spellings or party codes in the precinct file")
            cell[2] += int(r[idx["total_votes"]] or 0)
            precincts.add(r[idx["Precinct_name"]].strip())
    return out, len(precincts)


def race_of_contest(m):
    if m.group(1):
        return f"2026-{STATE}-GOV"
    if m.group(2):
        return f"2026-{STATE}-SS{m.group(2)}"
    return f"2026-{STATE}-SH{int(m.group(3))}"


def summary_tables(path):
    """{race: {"figures": [(votes, pct)], "total": n}} for the state contests of the official Summary, and its date."""
    got = lines(path)
    head = [t for p, _y, t in got if p == 1]
    for need in ("2026 PRIMARY ELECTION", "August 18, 2026", "OFFICIAL RESULTS"):
        if need not in head:
            raise SystemExit(f"Alaska (state races): the Summary is no longer the official report of the 2026 primary (no '{need}')")
    printed = next((re.search(r"(\d{1,2})/(\d{1,2})/(20\d\d)", t) for t in head if t.startswith("Page: 1 of")), None)
    found, race = {}, None
    for _p, _y, t in got:
        m = re.fullmatch(r"(.+) \(Vote for 1\)", t)
        if m:
            c = CONTEST.fullmatch(m.group(1))
            race = race_of_contest(c) if c else None
            if race:
                if race in found:
                    raise SystemExit(f"Alaska (state races): the Summary prints {m.group(1)} twice")
                found[race] = {"figures": [], "total": None}
            continue
        if race is None:
            continue
        m = re.fullmatch(r"Total Votes (\d{1,3}(?:,\d{3})*)", t)
        if m:
            found[race]["total"] = int(m.group(1).replace(",", ""))
            race = None
            continue
        if t.startswith(("Times Cast", "Precincts Reported")):
            continue
        m = re.search(r"(?:^| )(\d{1,3}(?:,\d{3})*) (\d{1,3}\.\d\d)%$", t)
        if m:
            found[race]["figures"].append((int(m.group(1).replace(",", "")), float(m.group(2))))
    date = f"{printed.group(3)}-{int(printed.group(1)):02d}-{int(printed.group(2)):02d}" if printed else ""
    return found, date


# ------------------------------------------------------------------------------------------------------ the ballots

def ballot_lines(data):
    """Every text line of a sample ballot, in the order the ballot's own content streams write them (which keeps each
    column's lines together), as (page, x, text). The text sits in form objects; the page streams are read too."""
    pdf = PDF(data)

    def forms(res, depth=0):
        for _n, ref in (pdf.get((pdf.get(res) or {}).get("XObject")) or {}).items():
            d = pdf.get(ref)
            if isinstance(d, dict) and d.get("Subtype") == "Form" and depth < 6:
                yield ref, d
                yield from forms(d.get("Resources"), depth + 1)

    out = []
    for pno, (page, res) in enumerate(pdf.pages(), 1):
        streams = [(page, res)] + [({"Contents": ref}, d.get("Resources")) for ref, d in forms(res)]
        for holder, rs in streams:
            cur = []
            for r in page_runs(pdf, holder, rs):
                if cur and (abs(cur[-1][1] - r[1]) > max(1.5, 0.35 * r[2]) or r[0] < cur[-1][0] - 1):
                    out.append((pno, round(cur[0][0], 1), join(cur).strip()))
                    cur = []
                cur.append(r)
            if cur:
                out.append((pno, round(cur[0][0], 1), join(cur).strip()))
    return [o for o in out if o[2]]


def read_ballot(data):
    """{"hd", "jd", "contests": {heading: [(name, registration, incumbent)]}, "retention": [(name, court, years)]}."""
    got = ballot_lines(data)
    hd = {m.group(1) for _p, _x, t in got for m in [re.fullmatch(r"(?:State of Alaska Official Ballot )?House District (\d{1,2})", t)] if m}
    jd = {m.group(1) for _p, _x, t in got for m in [re.fullmatch(r"Judicial (\d)", t)] if m}
    contests, cur, col, last = {}, None, None, None
    for _p, x, t in got:
        m = BALLOT_HEAD.fullmatch(t)
        if m:
            if t in contests:
                raise ValueError(f"the ballot prints {t} twice")
            cur, col, last = t, None, None
            contests[cur] = []
            continue
        if cur is None:
            continue
        if t.startswith("Write-in:"):
            cur = None
            continue
        if SKIP_LINE.fullmatch(t):
            continue
        if col is not None and abs(x - col) > 2:
            cur = None
            continue
        t = re.sub(r"(?: \d)+$", "", t).strip()
        if t.startswith("(") and last is not None and last[1] == "":
            m2 = re.fullmatch(r"\(([^()]*)\)( Incumbent)?", t)
            if not m2:
                raise ValueError(f"a registration line on the ballot could not be read under {cur}")
            last[1], last[2] = reg_norm(m2.group(1)), last[2] or bool(m2.group(2))
            continue
        m2 = re.fullmatch(r"(.+?)(?: \(([^()]*)\))?( Incumbent)?", t)
        last = [straight(m2.group(1)), reg_norm(m2.group(2) or ""), bool(m2.group(3))]
        contests[cur].append(last)
        col = x if col is None else col
    retention, buf, held = [], None, 0
    for _p, _x, t in got:
        if t.startswith("Shall "):
            buf, held = t, 1
        elif buf is not None:
            buf, held = buf + " " + t, held + 1
        if buf is not None and buf.endswith("?"):
            m = RETAIN.fullmatch(re.sub(r"\s+", " ", buf))
            if m:
                retention.append((straight(m.group(1)), m.group(3), m.group(4)))
            buf = None
        elif held > 4:
            buf = None
    return {"hd": hd, "jd": jd, "contests": {k: [tuple(v) for v in vs] for k, vs in contests.items()}, "retention": retention}


def sample_ballots(folder, say):
    """The 46 general-election sample ballots, as linked from the Division's sample ballot page; kept 30 days."""
    sub = os.path.join(folder, "sample_2026_general")
    os.makedirs(sub, exist_ok=True)
    rec_path = os.path.join(sub, "links.json")
    if fresh(rec_path, 30):
        links = json.load(open(rec_path, encoding="utf-8"))
    else:
        page = fetch(A.SAMPLE_PAGE, say).decode("utf-8", "replace")
        if "2026 General Election" not in page:
            raise SystemExit(f"Alaska (state races): {A.SAMPLE_PAGE} is no longer the 2026 General Election sample ballots page")
        links = []
        for href, lab in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', page, re.S):
            m = re.fullmatch(r"House District (\d{1,2})(?: \W Judicial Dist\. (\d))?", text(lab))
            if m:
                links.append({"label": text(lab), "hd": m.group(1), "jd": m.group(2), "url": urljoin(A.SAMPLE_PAGE, H.unescape(href))})
        json.dump(links, open(rec_path, "w", encoding="utf-8"), indent=1)
    out = []
    for ln in links:
        m = re.search(r"/(HD(\d{1,2})-JD(\d))\.pdf$", ln["url"])
        if not m or m.group(2) != ln["hd"] or (ln["jd"] and ln["jd"] != m.group(3)):
            raise SystemExit(f"Alaska (state races): a sample ballot link whose address does not fit its label ({ln['label']})")
        path = os.path.join(sub, m.group(1) + ".pdf")
        if not fresh(path, 30):
            if os.path.exists(path):
                os.remove(path)
            net.download(ln["url"], path, max_age_days=30, tries=3, say=say)
            time.sleep(1)
        if open(path, "rb").read(4) != b"%PDF":
            raise SystemExit(f"Alaska (state races): {os.path.basename(path)} is not a PDF; delete it and run again")
        out.append((ln, path, m.group(3)))
    return out


def primary_ballot(folder, say):
    path = os.path.join(folder, "ak_2026_primary_sample_ballot_hd1.pdf")
    if not os.path.exists(path):
        net.download(PRIMARY_BALLOT, path, max_age_days=3650, tries=3, say=say)
    if open(path, "rb").read(4) != b"%PDF":
        raise SystemExit("Alaska (state races): the primary sample ballot is not a PDF; delete it and run again")
    return path


# ------------------------------------------------------------------------------------------------------- the roster

def roster(path):
    """Sitting legislators and the Governor and Lieutenant Governor: ids, names, party, chamber and district only."""
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    legs = [dict(zip(("id", "first", "last", "full", "other", "party", "chamber", "district"), r)) for r in con.execute(
        "SELECT bioguide_id, first_name, last_name, official_full, other_names, party_name, chamber, district "
        "FROM legislators WHERE is_current = 1")]
    offs = {r[0]: dict(zip(("office", "id", "first", "last", "full", "party"), r)) for r in con.execute(
        "SELECT office, bioguide_id, first_name, last_name, official_full, party_name FROM officials "
        "WHERE office IN ('governor', 'lt_governor')")}
    con.close()
    for p in legs:
        d = str(p["district"] or "")
        p["district"] = str(int(d)) if d.isdigit() else d
    return legs, offs


def person_fits(name, p):
    """A listed name ("Last, First "Nick"") fits a roster person: same family name and a given name that fits the roster's
    first name or one of the other forms of the name it keeps (a nickname in quotation marks counts as a given name)."""
    name = straight(name)
    nick = re.findall(r'"([^"]+)"', name)
    plain = re.sub(r'"[^"]*"|\([^)]*\)', " ", name)
    readings = [name_parts(name), name_parts(plain)]
    fam = name_parts(plain)[1]
    readings += [(fold(n).split(), fam) for n in nick]
    forms = [(fold(p["first"] or "").split(), " ".join(fold(p["last"] or "").split()))]
    forms += [name_parts(o.strip()) for o in (p.get("other") or "").split(";") if o.strip() and "," not in o and "." not in o]
    return any(f[1] and r[1] and fits(r, f) for r in readings for f in forms)


# ------------------------------------------------------------------------------------------------------------ loading

def load(db_path, say=print, cache=CACHE, roster_db=ROSTER):
    net.patient_lookups()
    folder = os.path.join(cache, "ak")
    os.makedirs(folder, exist_ok=True)
    report = Report()

    gpath, gen = general_list(folder, say)
    ppath, pri = primary_list(folder, say)
    p24, y24 = senate_2024(folder, say)
    rec, csv_path, pdf_path = A.results_files(folder, say)
    votes, precincts = precinct_votes(csv_path)
    summary, published = summary_tables(pdf_path)
    ballots = sample_ballots(folder, say)
    pb_path = primary_ballot(folder, say)
    legs, offs = roster(roster_db)

    # ---- the races, from the general list
    races, listed, off_list = {}, collections.defaultdict(list), []
    for r in gen["rows"]:
        m = OFFICE_HEAD.fullmatch(r["office"])
        if m.group(1):
            rid = f"2026-{STATE}-GOV"
            race = dict(level="statewide", office_kind="governor", office="Governor and Lieutenant Governor", jurisdiction=NAME,
                        jurisdiction_id=STATE, district=None, partisan=1, chamber=None)
        elif m.group(2):
            d = m.group(2)
            rid = f"2026-{STATE}-SS{d}"
            race = dict(level="legislature", office_kind="state_senate", office="State Senator", jurisdiction=f"Senate District {d}",
                        jurisdiction_id=f"{STATE}-{d}", district=d, partisan=1, chamber="Senate",
                        place=("senate", f"{STATE}-{d}", f"Senate District {d}"))
        elif m.group(3):
            d = str(int(m.group(3)))
            rid = f"2026-{STATE}-SH{d}"
            race = dict(level="legislature", office_kind="state_house", office="State Representative", jurisdiction=f"House District {d}",
                        jurisdiction_id=f"{STATE}-{d}", district=d, partisan=1, chamber="House",
                        place=("house", f"{STATE}-{d}", f"House District {d}"))
        else:
            fam = re.sub(r"[^A-Z]", "", judge_parts(r["name"])[1].upper())
            if m.group(4):
                rid = f"2026-{STATE}-SCRET-{fam}"
                race = dict(level="court", office_kind="supreme_court_retention", office="Justice of the Supreme Court (retention vote)",
                            jurisdiction=NAME, jurisdiction_id=STATE, district=None, partisan=0, chamber=None, court="supreme", jd=None)
            else:
                jd = str(int(m.group(6)))
                sup = m.group(5) == "SUPERIOR"
                rid = f"2026-{STATE}-{'SUPRET' if sup else 'DCRET'}-JD{jd}-{fam}"
                race = dict(level="court", office_kind="superior_court_retention" if sup else "district_court_retention",
                            office=f"Judge of the {'Superior' if sup else 'District'} Court (retention vote)",
                            jurisdiction=f"{ORDINAL_JD[jd]} Judicial District", jurisdiction_id=f"{STATE}-JD{jd}", district=jd, partisan=0,
                            chamber=None, court="superior" if sup else "district", jd=jd,
                            place=("judicial_district", f"{STATE}-JD{jd}", f"{ORDINAL_JD[jd]} Judicial District"))
            if rid in races:
                raise SystemExit(f"Alaska (state races): two retention votes would share the id {rid}")
        if A.OFF.search(r["status"]):
            off_list.append(f"{turn(r['name'])} ({r['office'].title()})")
            continue
        if r["status"] != "Certified":
            raise SystemExit(f"Alaska (state races): a status on the general list that is not read ({r['status']!r}, {r['office']})")
        races.setdefault(rid, dict(race_id=rid, **race))
        listed[rid].append(r)

    # ---- which seats: ten Senate seats not elected in 2024, all forty House seats
    sen26 = sorted(r["district"] for r in races.values() if r["office_kind"] == "state_senate")
    sen24 = y24["senate"]
    if set(sen26) & set(sen24):
        report.add(f"Senate seats on the 2026 list that the 2024 list also named: {sorted(set(sen26) & set(sen24))}")
    if set(sen26) | set(sen24) != set(SENATE_LETTERS):
        report.add(f"the 2026 and 2024 lists' Senate seats together are not all twenty: {sorted(set(SENATE_LETTERS) - set(sen26) - set(sen24))} missing")
    house = {int(r["district"]) for r in races.values() if r["office_kind"] == "state_house"}
    if house != set(range(1, HOUSE_SEATS + 1)):
        report.add(f"House seats with no candidate on the general list: {sorted(set(range(1, HOUSE_SEATS + 1)) - house)}")

    # ---- the primary list: who was on the August ballot, and who was not
    filed, withdrew, dupes, gid = collections.defaultdict(dict), [], 0, f"2026-{STATE}-GOV"
    for r in pri["rows"]:
        if r["office"].startswith("GOVERNOR"):
            rid = f"2026-{STATE}-GOV"
        elif r["office"] == "STATE SENATOR":
            rid = f"2026-{STATE}-SS{r['district']}"
        else:
            rid = f"2026-{STATE}-SH{int(r['district'])}"
        if r["status"] == "Certified":
            key = person_key(rid, r["name"])
            if key in filed[rid]:
                if (filed[rid][key]["name"], filed[rid][key]["party"]) != (r["name"], r["party"]):
                    raise SystemExit(f"Alaska (state races): two different rows for one candidate on the primary list ({rid})")
                dupes += 1
                continue
            filed[rid][key] = r
        elif A.OFF.search(r["status"]):
            bare = re.sub(r" *[(][^)]*[)]", "", r["name"])
            who = " with ".join(turned_ticket(bare)) if rid == gid else turn(bare)
            withdrew.append(f"{who} ({rid[8:]}, {r['status'].replace('DeniedNo', 'Denied, no')})")
        else:
            raise SystemExit(f"Alaska (state races): a status on the primary list that is not read ({r['status']!r})")

    # ---- the official results: precinct sums against the Summary
    unreconciled = []
    for rid, cands in votes.items():
        f = summary.get(rid)
        mine = sorted(v for _n, _c, v in cands.values())
        if not f or f["total"] is None:
            unreconciled.append(f"{rid}: no whole table in the Summary")
            continue
        if sorted(v for v, _p in f["figures"]) != mine or f["total"] != sum(mine):
            unreconciled.append(f"{rid}: the precinct sums {mine} are not the Summary's {sorted(v for v, _p in f['figures'])} (total {f['total']})")
        for v, pct in f["figures"]:
            if f["total"] and abs(round(100 * v / f["total"], 2) - pct) > 0.006:
                unreconciled.append(f"{rid}: a Summary percentage does not follow from its figures ({v}, {pct}%)")
    for rid in set(summary) - set(votes):
        unreconciled.append(f"{rid}: in the Summary but not in the precinct file")
    for rid in sorted(set(votes) - set(races)):
        report.add(f"{rid}: in the primary results, but nobody for it on the general list")
    for rid in sorted(set(r for r in races if races[r]["partisan"]) - set(votes)):
        report.add(f"{rid}: a partisan race on the general list with no primary results")

    # ---- the primary ballot: the Governor tickets, for the one the primary list no longer carries
    pballot = read_ballot(open(pb_path, "rb").read())
    ptickets = {ticket_key(n): (n, p) for n, p, _i in pballot["contests"].get("Governor / Lieutenant Governor", [])}
    if set(ptickets) != set(votes.get(gid, {})):
        report.add(f"the primary sample ballot's Governor tickets are not the results' ({sorted(set(ptickets) ^ set(votes.get(gid, {})))})")
    ballot_only = []
    for key, (n, p) in ptickets.items():
        if key in votes.get(gid, {}) and key not in filed[gid]:
            filed[gid][key] = {"office": "GOVERNOR / LIEUTENANT GOVERNOR", "district": "All", "name": n, "party": p.replace("/", " / "), "status": "Certified",
                               "incumbent": False, "from_ballot": True}
            ballot_only.append(turned_ticket(n)[0])

    # ---- the sample ballots: every printed name against the general list; House ballot order
    printed_names = {rid: {person_key(rid, r["name"]): r for r in rows if not r["write_in"]} for rid, rows in listed.items()}
    order, senate_hds, jd_hds, hd_seen, ballot_rows, ballot_sha = {}, collections.defaultdict(set), collections.defaultdict(set), set(), 0, []
    for ln, path, jd in ballots:
        ballot_sha.append(sha(path))
        try:
            b = read_ballot(open(path, "rb").read())
        except ValueError as e:
            report.add(f"sample ballot {ln['label']}: {e}")
            continue
        hd = ln["hd"]
        hd_seen.add(int(hd))
        if b["hd"] != {hd} or b["jd"] != {jd}:
            report.add(f"sample ballot {ln['label']}: the ballot names house district {sorted(b['hd'])} and judicial district {sorted(b['jd'])}")
        jd_hds[jd].add(int(hd))
        for head, rows in b["contests"].items():
            m = BALLOT_HEAD.fullmatch(head)
            if m.group(4):
                continue
            rid = gid if m.group(1) else f"2026-{STATE}-SS{m.group(2)}" if m.group(2) else f"2026-{STATE}-SH{int(m.group(3))}"
            if m.group(2):
                senate_hds[m.group(2)].add(int(hd))
            if m.group(3) and m.group(3) != hd:
                report.add(f"sample ballot {ln['label']}: prints the contest {head}")
            want = printed_names.get(rid, {})
            got = {person_key(rid, n): (n, p, inc) for n, p, inc in rows}
            ballot_rows += len(rows)
            if set(got) != set(want) or len(got) != len(rows):
                report.add(f"sample ballot {ln['label']}: the names printed for {head} are not the general list's "
                           f"(ballot only {sorted(set(got) - set(want))}; list only {sorted(set(want) - set(got))})")
            for k, (n, p, inc) in got.items():
                if k in want:
                    if p and p != reg_norm(want[k]["party"]):
                        report.add(f"sample ballot {ln['label']}: {n}'s registration is {p!r} on the ballot and {want[k]['party']!r} on the list")
                    if not p:
                        report.add(f"sample ballot {ln['label']}: {n} is printed with no registration")
                    if inc and not want[k]["incumbent"]:
                        report.add(f"sample ballot {ln['label']}: the ballot marks {n} as the incumbent and the list does not")
            if m.group(3):
                seq = [person_key(rid, n) for n, _p, _i in rows]
                if rid in order and order[rid] != seq:
                    report.add(f"{rid}: the House ballot order differs between this district's two sample ballots")
                order[rid] = seq
        # retention
        want = {judge_key(listed[r][0]["name"]) for r, x in races.items() if x["level"] == "court" and (x["jd"] is None or x["jd"] == jd)}
        got = {judge_key(n) for n, _c, _y in b["retention"]}
        if got != want or len(got) != len(b["retention"]):
            report.add(f"sample ballot {ln['label']}: its retention questions are not the list's judges for judicial district {jd}")
        for n, court, years in b["retention"]:
            for rid, x in races.items():
                if x["level"] == "court" and judge_key(listed[rid][0]["name"]) == judge_key(n) and (x["jd"] is None or x["jd"] == jd):
                    if x["court"] != court:
                        report.add(f"sample ballot {ln['label']}: {n} is a {court} court retention on the ballot and {x['court']} on the list")
                    x.setdefault("years", set()).add(years)
                    x.setdefault("printed", set()).add(n)
    if hd_seen != set(range(1, HOUSE_SEATS + 1)):
        report.add(f"house districts with no sample ballot: {sorted(set(range(1, HOUSE_SEATS + 1)) - hd_seen)}")
    for d in SENATE_LETTERS:
        if (d in sen26) != bool(senate_hds.get(d)):
            report.add(f"Senate District {d}: {'on the list but on no sample ballot' if d in sen26 else 'on a sample ballot but not on the list'}")
        elif d in sen26 and len(senate_hds[d]) != 2:
            report.add(f"Senate District {d}: on the ballots of {len(senate_hds[d])} house districts")

    # ---- who holds each seat today
    def holder_of(x):
        if x["office_kind"] == "governor":
            return offs.get("governor")
        if x["chamber"]:
            hs = [p for p in legs if p["chamber"] == x["chamber"] and p["district"] == x["district"]]
            if len(hs) != 1:
                report.add(f"{x['race_id']}: {len(hs)} sitting members in the roster for this seat")
            return hs[0] if len(hs) == 1 else None
        return None

    def where(p):
        return f"Alaska {'Senate' if p['chamber'] == 'Senate' else 'House of Representatives'}, District {p['district']}"

    def identify(x, name):
        """(incumbent, state_member_id, note) for a partisan race: the seat's sitting member when the name fits; else one
        sitting legislator anywhere whose name fits (named in the note, not an incumbent here)."""
        if x["level"] == "court" or not name:
            return 0, None, None
        who = turned_ticket(name)[0] if x["office_kind"] == "governor" else name
        who_listed = split_ticket(name)[0] if x["office_kind"] == "governor" else name
        h = x.get("_holder")
        if h is not None and person_fits(who_listed, h):
            return 1, h["id"], None
        pool = [p for p in legs if person_fits(who_listed, p)]
        if len(pool) == 1 and not (h is not None and pool[0]["id"] == h["id"]):
            return 0, pool[0]["id"], f"Serves today in the {where(pool[0])} (Open States roster)."
        if len(pool) > 1:
            report.add(f"{x['race_id']}: {who} fits {len(pool)} sitting legislators; none is named")
        return 0, None, None

    for rid, x in races.items():
        notes = []
        h = holder_of(x)
        x["_holder"] = h
        if h is not None:
            x.update(holder_id=h["id"], holder_name=h["full"], holder_party=h["party"])
        if x["office_kind"] == "governor":
            notes.append(GOV_NOTE)
            lt = offs.get("lt_governor")
            if lt:
                notes.append(f"Lieutenant Governor today: {lt['full']} ({lt['party']}, Open States roster).")
            notes += [TOP_FOUR, ORDER_NONE.format(why=WHY_OTHER)]
        elif x["office_kind"] == "state_senate":
            hds = sorted(senate_hds.get(x["district"], ()))
            notes.append(SENATE_NOTE)
            if hds:
                notes.append(f"On the ballots of House Districts {' and '.join(map(str, hds))} (the Division's sample ballots).")
            notes += [TOP_FOUR, ORDER_NONE.format(why=WHY_SENATE)]
        elif x["office_kind"] == "state_house":
            notes += [HOUSE_NOTE, TOP_FOUR]
            notes.append(ORDER_HOUSE.format(d=x["district"]) if rid in order else "No sample ballot was read for this district, so no ballot order is stored.")
        else:
            judge = turn(listed[rid][0]["name"])
            years = sorted(x.get("years", ()))
            court = {"supreme": "justice of the supreme court", "superior": "judge of the superior court",
                     "district": "judge of the district court"}[x["court"]]
            notes.append(RETENTION_NOTE)
            shown = sorted(x.get("printed", ()))
            if len(years) == 1 and len(shown) == 1:
                notes.append(f"The ballot asks: Shall {shown[0]} be retained as {court} for {years[0]} years?")
            if x["jd"]:
                hds = sorted(jd_hds.get(x["jd"], ()))
                notes.append(f"Voted on in the {ORDINAL_JD[x['jd']]} Judicial District: on the Division's sample ballots for House Districts "
                             f"{', '.join(map(str, hds))} (a house district split between judicial districts has one ballot for each part).")
            else:
                notes.append("Voted on statewide.")
            notes.append("The Division's list marks the judge as the incumbent; the Open States roster does not carry judges.")
            x.update(holder_name=judge)
        x["note"] = " ".join(notes)

    # ---- the rows
    cands, fields, swaps, upsets, singles = [], 0, [], [], 0
    for rid in sorted(races):
        x = races[rid]
        rows = listed[rid]
        if x["level"] == "court":
            if len(rows) != 1:
                report.add(f"{rid}: a retention vote with {len(rows)} names")
            r = rows[0]
            if not r["incumbent"]:
                report.add(f"{rid}: the list does not mark {r['name']} as the incumbent")
            cands.append([rid, "general", GENERAL, turn(r["name"]), NONPARTISAN, "N", None, 1, 0, None, None, None, None, SRC_GEN,
                          "Standing for retention as the sitting judge."])
            continue
        field = votes.get(rid, {})
        is_gov = x["office_kind"] == "governor"
        printed = {person_key(rid, r["name"]) for r in rows if not r["write_in"]}
        # the field against the primary list
        if set(field) != set(filed[rid]):
            report.add(f"{rid}: the results' candidates are not the primary list's Certified candidates "
                       f"(results only {sorted(set(field) - set(filed[rid]))}; list only {sorted(set(filed[rid]) - set(field))})")
        for key, (name, code, _v) in field.items():
            lr = filed[rid].get(key)
            if lr and code and "/".join(A.CODE_LABEL.get(c, "?") for c in code.split("/")) != reg_norm(lr["party"]):
                report.add(f"{rid}: {name}'s party code in the results ({code}) does not fit the list's registration ({lr['party']})")
        ranked = sorted(field.values(), key=lambda c: (-c[2], c[0]))
        place = {person_key(rid, c[0]): i for i, c in enumerate(ranked, 1)}
        tie = len(ranked) > 4 and ranked[3][2] == ranked[4][2]
        if tie:
            report.add(f"{rid}: a tie for fourth place in the primary; the record read does not say who advanced")
        top = {person_key(rid, c[0]) for c in ranked[:4]}
        missing = sorted(top - printed, key=lambda k: place.get(k, 99))
        extra = sorted(printed - top, key=lambda k: place.get(k, 99))
        for k in extra:
            if k not in field:
                report.add(f"{rid}: the November list names a candidate who was not on the primary ballot ({k})")
        if len(extra) > len(missing):
            report.add(f"{rid}: the November list prints a later finisher with no top-four place to fill")
        def name_of(k):
            if k in filed[rid]:
                return turned_ticket(filed[rid][k]["name"])[0] if is_gov else turn(filed[rid][k]["name"])
            return field[k][0].split("/")[0] if is_gov else turn(field[k][0])
        gone = " and ".join(name_of(k) for k in missing)
        last_extra = max((place[e] for e in extra if e in place), default=0)
        passed = [c for c in ranked[4:] if person_key(rid, c[0]) not in printed and place[person_key(rid, c[0])] < last_extra]
        for k in extra:
            if k in place:
                swaps.append(f"{rid}: {name_of(k)} ({A.ORDINAL.get(place[k], place[k])}) in place of {gone or 'nobody'}")
        for k in missing:
            upsets.append(f"{rid}: {name_of(k)} ({A.ORDINAL.get(place[k], place[k])}) advanced and is not on the November list")
        total = sum(c[2] for c in ranked)
        if len(ranked) >= 2:
            fields += 1
            for name, code, v in ranked:
                k = person_key(rid, name)
                lr = filed[rid].get(k)
                notes = []
                if lr is None:
                    notes.append("Not on the Division's primary candidate list; the name as the official results print it.")
                    shown, label, mate = turn(name), "", None
                elif is_gov:
                    shown, mate = turned_ticket(lr["name"])
                    label = lr["party"]
                else:
                    shown, label, mate = turn(lr["name"]), lr["party"], None
                if lr is not None and lr.get("from_ballot"):
                    notes.append("The Division's primary candidate list no longer carries this ticket; the names and registration are as "
                                 "the primary sample ballot printed them, and the votes are the official results'.")
                if mate:
                    notes.append(f"Running mate for Lieutenant Governor: {mate}." + (
                        f" The ticket's registrations are printed \"{label}\"." if "/" in label else ""))
                if k in missing:
                    notes.append(f"Finished {A.ORDINAL[place[k]]} in the top-four primary and advanced; not on the Division's list of "
                                 "candidates for the November ballot, nor on its sample ballots.")
                if k in extra:
                    note = (f"Finished {A.ORDINAL.get(place[k], place[k])} in the top-four primary. On the November ballot in the place of "
                            f"{gone}, who finished in the top four and {'is' if len(missing) == 1 else 'are'} not on the Division's November list")
                    if passed and place[k] == max(place[e] for e in extra if e in place):
                        lo, hi = place[person_key(rid, passed[0][0])], place[person_key(rid, passed[-1][0])]
                        note += (f"; the candidate who finished {A.ORDINAL[lo]} is not on it either" if lo == hi else
                                 f"; the candidates who finished {A.ORDINAL[lo]} to {A.ORDINAL[hi]} are not on it either")
                    notes.append(note + ".")
                party = split_regs(label)[0] if is_gov else label
                if not party and code:
                    party = A.CODE_LABEL.get(code.split("/")[0], "")
                inc, mid, n2 = identify(x, lr["name"] if lr else (None if is_gov else name))
                if n2:
                    notes.append(n2)
                outcome = None if (tie and ranked[3][2] == v) else "advanced" if (k in top or k in extra) else "lost"
                cands.append([rid, "primary", PRIMARY, shown, party, code_of(party), None, inc, 0, v,
                              round(100 * v / total, 1) if total else None, outcome, mid, SRC_CSV, " ".join(notes) or None])
        else:
            singles += 1
        seq = order.get(rid)
        for r in rows:
            k = person_key(rid, r["name"])
            notes = []
            if is_gov:
                shown, mate = turned_ticket(r["name"])
                regs = split_regs(r["party"])
                party = regs[0]
                notes.append(f"Running mate for Lieutenant Governor: {mate}." + (
                    f" The ticket's registrations are printed \"{r['party']}\"." if "/" in r["party"] else ""))
            else:
                shown, party = turn(r["name"]), r["party"]
            if r["write_in"]:
                notes.append(WRITE_IN)
                if k in place:
                    notes.append(f"Was on the August primary ballot and finished {A.ORDINAL.get(place[k], place[k])}.")
            elif k in extra:
                notes.append(f"On the November ballot in the place of {gone}, who finished in the top four of the August 18 primary and "
                             f"{'is' if len(missing) == 1 else 'are'} not on the Division's November list; this candidate finished "
                             f"{A.ORDINAL.get(place[k], place[k])}.")
            elif field:
                notes.append("Advanced from the August 18 top-four primary.")
            inc, mid, n2 = identify(x, r["name"])
            if n2:
                notes.append(n2)
            if r["incumbent"] and not inc:
                report.add(f"{rid}: the list marks {r['name']} as the incumbent, and the roster's holder of the seat does not fit")
            if inc and not r["incumbent"] and not is_gov:
                report.add(f"{rid}: {r['name']} fits the roster's holder of the seat, and the list does not mark an incumbent")
            bo = seq.index(k) + 1 if (seq and not r["write_in"] and k in seq) else None
            cands.append([rid, "general", GENERAL, shown, party, code_of(party), bo, inc, int(r["write_in"]), None, None, None, mid, SRC_GEN,
                          " ".join(notes) or None])

    seen = set()
    for c in cands:
        k = (c[0], c[1], c[3])
        if k in seen:
            raise SystemExit(f"Alaska (state races): {c[3]} is listed twice in {c[0]} {c[1]}")
        seen.add(k)

    # ---- write: Alaska's rows only, in one transaction
    cols = ["race_id", "state", "level", "office_kind", "office", "jurisdiction", "jurisdiction_id", "county_ids", "district", "seat",
            "special", "partisan", "holder_id", "holder_name", "holder_party", "election_date", "note"]
    for x in races.values():
        x.update(state=STATE, county_ids=None, seat=None, special=0, election_date=GENERAL)
        x.setdefault("holder_id", None), x.setdefault("holder_name", None), x.setdefault("holder_party", None)
    race_rows = [tuple(races[r][c] for c in cols) for r in sorted(races)]
    places = {}
    for x in races.values():
        if x.get("place"):
            places[x["place"][:2]] = x["place"]
    place_rows = [(k, pid, name, None, SRC_BALLOTS if k == "judicial_district" else SRC_GEN) for (k, pid), (_k, _i, name) in sorted(places.items())]
    list_sha = hashlib.sha256("".join(gen["page_sha256"]).encode()).hexdigest()
    n_gen = sum(1 for c in cands if c[1] == "general")
    n_pri = len(cands) - n_gen
    if n_gen != len(gen["rows"]) - len(off_list):
        report.add(f"the general list's {len(gen['rows'])} state rows ({len(off_list)} withdrawn) are not the {n_gen} stored")
    for rid, cs in votes.items():
        if len(cs) >= 2 and sum(1 for c in cands if c[0] == rid and c[1] == "primary") != len(cs):
            report.add(f"{rid}: {len(cs)} candidates in the results, a different number stored")
    src = [
        (SRC_GEN, STATE, "official candidate list", AGENCY,
         "2026 General Election candidates (November 3, 2026): Governor / Lieutenant Governor, State Senate, State House and judicial retention",
         A.GENERAL_URL, "", gen["read"], list_sha, len(gen["rows"]),
         f"Every page read through the list's own pager ({gen['pages']} pages; the judicial sections, repeated on each page, agreed). Only the "
         "Candidate Name on Ballot cell was read (name, registration, status, write-in and incumbent marks); addresses, contact details and "
         f"pamphlet links were never read and the pages were not kept. {gen['federal_rows']} federal rows counted only (left to the federal "
         f"pages). Withdrawn or removed, left off: {'; '.join(off_list) or 'none'}. The sha256 here is of the pages' own hashes joined."),
        (SRC_PRI, STATE, "official candidate list", AGENCY,
         "2026 Primary Election candidates (August 18, 2026): Governor / Lieutenant Governor, State Senator and State Representative",
         A.PRIMARY_URL, pri.get("updated", ""), pri["read"], pri["page_sha256"], len(pri["rows"]),
         f"A flat table of {pri['items']} rows, five cells each; only the office and the name, registration, status and incumbent cells "
         f"were read, each checked for its shape. Rows repeated word for word, counted once: {dupes}. Used to check the primary results and "
         f"for each candidate's registration. Withdrawn or denied before the primary, not on its ballot: {'; '.join(withdrew) or 'none'}."
         + (f" Not on this list but on the primary ballot and in the official results: {', '.join(ballot_only)} (Governor)." if ballot_only else "")),
        (SRC_CSV, STATE, "official results", AGENCY, "2026 Primary Election (August 18, 2026): Results Per Precinct, state contests",
         rec["csv"], rec.get("updated", ""), mtime(csv_path), sha(csv_path), n_pri,
         f"Found on {A.RESULTS_PAGE}, which gives the results status as Official. Votes summed over {precincts} reporting units. Top-four "
         f"primary with no write-in votes: each field's total is its candidates' votes. Fields shown where two or more candidates were on "
         f"the ballot: {fields}; races with one candidate: {singles}."),
        (SRC_SUM, STATE, "official results", AGENCY, "2026 Primary Election, August 18, 2026: Election Summary Report, Official Results",
         rec["pdf"], published, mtime(pdf_path), sha(pdf_path), sum(1 for r in summary),
         "Control: every candidate's summed votes, the percentages and each state contest's Total Votes match this report exactly"
         + ("." if not unreconciled else "; did not match: " + "; ".join(unreconciled) + ".")),
        (SRC_BALLOTS, STATE, "official sample ballots", AGENCY, "2026 General Election ranked-choice sample ballots, every house district",
         A.SAMPLE_PAGE, "", mtime(ballots[0][1]) if ballots else "", hashlib.sha256("".join(ballot_sha).encode()).hexdigest(), len(ballots),
         f"{len(ballots)} ballots (a house district split between judicial districts has one for each part). Read for the names and "
         f"registrations printed ({ballot_rows} candidate lines), the retention questions, each ballot's house and judicial district, and the "
         "House ballot order. The sha256 here is of the ballots' own hashes joined."),
        (SRC_PBALLOT, STATE, "official sample ballot", AGENCY, "2026 Primary Election sample ballot, House District 1",
         PRIMARY_BALLOT, "", mtime(pb_path), sha(pb_path), len(ptickets),
         "The Division's own address for the file (the primary's sample ballot page is no longer listed). Read for the statewide Governor / "
         "Lieutenant Governor contest only: its tickets checked against the official results'."),
        (SRC_2024, STATE, "official candidate list", AGENCY, "2024 General Election candidates: section headings only", LIST_2024, "",
         y24["read"], hashlib.sha256("".join(y24["page_sha256"]).encode()).hexdigest(), len(sen24),
         f"Only the section headings were read ({y24['sections']} over {y24['pages']} pages): Senate seats elected in 2024, "
         f"{', '.join(sen24)}. No name, address or contact cell was read."),
        (SRC_ROSTER, STATE, "roster", "Open States people project (CC0), as loaded into state_ak.sqlite",
         "Sitting Alaska legislators, Governor and Lieutenant Governor", "https://github.com/openstates/people", "", mtime(roster_db),
         sha(roster_db), len(legs) + len(offs),
         "Who holds each seat today (chamber and district) and incumbent matches; ids, names, party, chamber and district only. Not an official record."),
    ]

    con = sqlite3.connect(db_path)
    try:
        con.executescript(SCHEMA)
        with con:
            con.execute("DELETE FROM sl_candidates WHERE race_id IN (SELECT race_id FROM sl_races WHERE state = ?) OR race_id LIKE ?",
                        (STATE, f"2026-{STATE}-%"))
            con.execute("DELETE FROM sl_races WHERE state = ?", (STATE,))
            con.execute("DELETE FROM sl_sources WHERE state = ?", (STATE,))
            con.execute("DELETE FROM sl_places WHERE id LIKE ? AND source_id LIKE 'ak-%'", (f"{STATE}-%",))
            con.executemany(f"INSERT INTO sl_races VALUES ({','.join('?' * len(cols))})", race_rows)
            con.executemany("INSERT INTO sl_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", cands)
            con.executemany("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", src)
            con.executemany("INSERT INTO sl_places VALUES (?,?,?,?,?)", place_rows)
    finally:
        con.close()

    kinds = collections.Counter(x["office_kind"] for x in races.values())
    gk = collections.Counter(races[c[0]]["office_kind"] for c in cands if c[1] == "general")
    pk = collections.Counter(races[c[0]]["office_kind"] for c in cands if c[1] == "primary")
    wi = sum(1 for c in cands if c[1] == "general" and c[8])
    inc = sum(1 for c in cands if c[1] == "general" and c[7] and races[c[0]]["partisan"])
    say(f"    Alaska (state races): {len(races)} races ({', '.join(f'{k} {v}' for k, v in sorted(kinds.items()))}); {n_gen} on the November "
        f"list ({', '.join(f'{k} {v}' for k, v in sorted(gk.items()))}; {wi} certified write-ins, {len(off_list)} withdrawn left off, "
        f"{inc} incumbents matched); {fields} top-four primary fields, {n_pri} primary rows ({', '.join(f'{k} {v}' for k, v in sorted(pk.items()))}), "
        f"official votes, precinct sums checked against the Summary; {len(ballots)} sample ballots checked")
    for s in swaps:
        say(f"      later finisher on the ballot: {s}")
    for u in upsets:
        say(f"      note: {u}")
    for c in cands:
        if c[12] and not c[7]:
            say(f"      matched elsewhere: {c[0]} {c[1]}: {c[3]} -> {c[12]}")
    for line in unreconciled:
        say(f"      CHECK primary results: {line}")
    for line in report:
        say(f"      CHECK {line}")
    return {"races": len(races), "general": n_gen, "primary": n_pri, "fields": fields, "kinds": dict(kinds), "report": list(report),
            "unreconciled": unreconciled}


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m ballot.state_local_ak <database>")
    load(sys.argv[1])
