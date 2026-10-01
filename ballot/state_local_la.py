"""
ballot/state_local_la.py - Louisiana's state, parish and local races on the November 3, 2026 ballot, from the Secretary
of State's own Candidate Inquiry and official results, into ballot_local_2026.sqlite (Louisiana's rows only).

What is on the ballot. Louisiana elects its Legislature and its Governor and the other statewide executive officers in
odd years (2023, next 2027; the roster's Governor, Lieutenant Governor and Attorney General all serve to January 2028),
so no regular legislative or statewide executive race is on the 2026 ballot. The Candidate Inquiry's office list for the
November 3, 2026 election holds, at the state level:
  - a special election for State Representative, 92nd District (Jefferson Parish), the seat left vacant when
    Representative Joseph A. Stagni resigned effective June 30, 2026: the Speaker of the House's proclamation of June 30,
    2026 (house.louisiana.gov/H_Misc/proclamations/District%2092%20-%20Proclamation.pdf, a scanned page, read by eye;
    its fingerprint is checked on every run) fixes the special primary for November 3 and the special general for
    December 12. The Legislature runs in the open primary system: every candidate on one ballot, more than half the
    votes wins, otherwise the top two meet in the general.
  - the offices that held closed party primaries this spring (the Secretary's "Types of Elections" page: "closed party
    primaries will be held in the Spring for U.S. Senator, La. Supreme Court Justice, Public Service Commissioner
    (PSC), and Board of Elementary and Secondary Education Member (BESE)"; the "Election Dates" page: "The November 3,
    2026 election is the open general election date for party primary offices"): Associate Justice of the Supreme
    Court, Districts 1, 3 and 4; Public Service Commission, Districts 1 and 5; BESE, District 1. Party primaries were
    on May 16, runoffs on June 27.
  - four seats on the Courts of Appeal, which are not party primary offices (open primary on November 3).
The only other state-level race on the Secretary's 2026 lists after today is a special primary for State Senator, 14th
District (East Baton Rouge), on December 12 (qualifying October 14 to 16): not on the November 3 ballot, so it is
counted and reported, not loaded. District judges, district attorneys and the parish, school board, municipal and
special district offices on the November 3 list are read by the parish and local part, below.

Every judicial candidate's party is printed on the list and on the ballot, so the court races are partisan here.

The parish and local part (John, 2026-09-30)
--------------------------------------------
Louisiana's parishes are its counties. November 3, 2026 is the open primary (R.S. 18:402(C)(2)) for the local offices
filled in congressional election years, with the general election on December 12 for any seat nobody wins by a majority
(R.S. 18:511(A)). As the state part does for the Court of Appeal, the November 3 candidates are stored as election
"general", dated 2026-11-03, and each race's note says it is the open primary; the federal loader's "open-primary" name is
not used here, because the state and local pages read "general" as the November list. A candidate nobody opposes is
declared elected and left off the ballot (R.S. 18:511(B)): the list marks them Unopposed, and they are kept, as the state
part keeps them, with outcome "unopposed", no ballot order and a note; an office nobody qualified for is kept with a
note. Candidates marked Withdrew, Other/Disq or Deceased are left off and counted.

Three readings of the Secretary of State's own list, reconciled with each other (ballot_cache/la/local/ holds only the
cut-down copies: office, number to be elected, name, party, status; never an answer as it arrived):
  1. Candidate Inquiry, "Races in a Parish", for each of the 64 parishes, read twice: the CSV export (columns found by
     their headings: Election, Parish, OfficeTitle, OfficeTitleDescription, NumberToBeElected, BallotFirstName,
     BallotLastName, BallotSuffix, Party, Outcome; the Address, City, State, Zip, Address Mismatch, Phone, Email Address,
     Race, Gender and Filed Date columns are never read) and the page itself (the federal loader's reader: office title,
     number to be elected, first line of the name and party columns, the status cell; the page also shows the offices
     nobody qualified for, which the export leaves out). The two must agree office by office and name by name. The name
     stored is the page's (the name as the ballot prints it, nicknames in quotation marks).
  2. Candidate Inquiry, statewide tab: its office list says which offices are one contest across parishes (district
     judges, district attorneys, city courts and the offices of municipalities that lie in two parishes); an office of
     one municipality (the only place of its name in the Census Bureau's list) is likewise one contest wherever it is
     listed; every other office (a school board district, a justice of the peace ward) is its own parish's. The tab's
     own candidate list of those offices must equal every parish's list of them. The parishes a contest reaches are the
     parishes whose lists carry it.
  3. The results site's race files for November 3 (ElectionRaces.htm, RacesCandidates_Multiparish.htm and
     RacesCandidates/ByParish_01..64.htm; no contact fields; no votes yet): the contests that will be voted on. They must
     be exactly the list's contested offices, with the same candidates, parties and number to be elected, in the same
     order. The list gives no ballot position; the law lists each office's candidates alphabetically by surname (R.S.
     18:551(C)) and both readings are in that order, so it is kept as the ballot order for contested offices.
Where each office goes: justices of the peace, constables, a sheriff, police jurors, a parish president and parish
council members under level county (the parish's five-digit code); mayors, police chiefs, aldermen and council members
and a city prosecutor under level city (the Census Bureau's 2020 place code, by name, one match only); school board
members under level school (the Census Bureau's school district code: the parish's district, or the city or community
system the list names); a community development district under level other; district, parish, family, juvenile and city
court judges, district attorneys, city marshals and the constable of a city court under level court, with the parishes
they reach in county_ids. A title no rule here fits is left out and listed in sl_gaps; nothing is guessed. A sheriff's,
police juror's or parish council seat (outside Plaquemines) and a Lafayette school board seat are marked special, with a
note, because the Secretary's schedule of regular elections (a sideways PDF page, read by eye, fingerprint checked) fills
those offices in other years; "(Unexpired Term)" in a title marks the rest. No candidate's name is used to look anything
up, no local candidate is matched to the legislative roster, and holders are left empty.

The state part's sources, all the state's own, read with the federal loader's parts (ballot/lists/la.py):
  - The Candidate Inquiry (voterportal.sos.la.gov/candidateinquiry): the office list of the November 3, May 16, June 27
    and December 12 elections (office titles only) and the candidate list of the state offices, of which only the office
    title, the first line of the name column (the name as printed on the ballot), the first line of the party column
    and the status cell are read (LA.candidate_list). Addresses, telephones, e-mail, race, gender and filing dates are
    never read; the answers themselves are never written anywhere, only the kept cells, with each answer's SHA-256, in
    ballot_cache/la/sl_la_2026_candidate_inquiry_state.json. Withdrawn, disqualified or deceased candidates are left off
    and counted. "Unopposed" marks the only candidate who qualified: Louisiana declares that candidate elected, so the
    office is not voted on November 3; the row is kept with outcome "unopposed" and a note (as other states' loaders
    do). The list gives no ballot position; Louisiana's ballot lists candidates alphabetically by surname, and so does
    the list, so its order is kept as the ballot order (checked, and any break reported). Louisiana has no write-ins.
  - The official results (voterportal.sos.la.gov/graphical data: RacesCandidates_Multiparish.htm, Votes_Multiparish.htm
    and csv/ByParish_<race>.csv) of May 16 and June 27, read only when ElectionDates.htm marks them official, for the
    closed party primaries of the offices above. Names and vote counts only. Each race's statewide votes must equal its
    parish rows, every precinct and absentee count must have reported, each race's id must be the Candidate Inquiry's
    office id and its candidates the Inquiry's. A primary needs more than half the vote; the two sent to a runoff are
    stored "advanced" with a note; the party's nominee on the November list must be the primary's or runoff's winner
    (or the party's only candidate). Once the November 3 results are official, their votes and outcomes are read the
    same way.
  - The Secretary's "Election Dates" and "Types of Elections" pages: only the sentences quoted above are kept (the pages
    carry a hotline number, which is never kept), with each page's SHA-256.
  - Holders from the Open States roster in state_la.sqlite (legislators, is_current = 1). The roster carries no judges,
    Public Service Commissioners or BESE members, so those races show no holder. A candidate whose name fits exactly one
    sitting legislator of the same party gets that member's id (and incumbent 1 only for the seat's own holder).

    python -m ballot.state_local_la <path to a test database>
"""

import collections
import csv
import datetime as dt
import hashlib
import html as H
import io
import json
import os
import re
import sqlite3
import sys
import time
import zipfile
from urllib.error import HTTPError, URLError
from urllib.parse import quote

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from ballot.check_local import EXTRA_SCHEMA, contact_like  # noqa: E402
from ballot.common import CACHE, fold, name_parts, party_code  # noqa: E402
from ballot.lists import la as LA  # noqa: E402
from ballot.match import fits  # noqa: E402
from states import net  # noqa: E402

STATE = "LA"
NOV, DEC, PRI, RUN = LA.NOV, LA.DEC, LA.PRIMARY, LA.RUNOFF                  # "11/03/2026" ...
ISO = LA.ISO
GENERAL = ISO[NOV]
ROSTER = os.path.join(HERE, "state_la.sqlite")
LIST_FILE = "sl_la_2026_candidate_inquiry_state.json"
PAGES_FILE = "sl_la_2026_election_pages.json"
STATUS_FILE = "sl_la_2026_results_status.json"
PROC_FILE = "la_2026_hd92_proclamation.pdf"
SRC_LIST = "la-sos-2026-state-candidate-inquiry"
SRC_PAGES = "la-sos-2026-election-pages"
SRC_PROC = "la-house-2026-hd92-proclamation"
SRC_ROSTER = "la-openstates-roster"
SRC_RES = lambda date: f"la-sos-2026-state-results-{ISO[date].replace('-', '')}"      # noqa: E731

DATES_URL = "https://www.sos.la.gov/elections-voting/election-dates"
TYPES_URL = "https://www.sos.la.gov/elections-voting/types-of-elections"
PROC_URL = "https://house.louisiana.gov/H_Misc/proclamations/District%2092%20-%20Proclamation.pdf"
PROC_SHA = "17b2062dcb01ae6cd51b4459ceb30234eeb071cffa3cd224c8bd08668a1ca904"    # the copy whose dates were read (2026-09-30)
# what the proclamation says, read from its scanned page
HD92 = {"district": "92", "parish": "Jefferson", "resigned": "Joseph A. Stagni", "effective": "2026-06-30",
        "primary": GENERAL, "general": ISO[DEC], "qualifying": "August 5 to 7, 2026", "dated": "2026-06-30"}

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

PARTY_OF = {"Democratic Party": ("DEM", "Democrat"), "Republican Party": ("REP", "Republican")}   # a closed primary's party, as the list prints its candidates
GONE = LA.GONE
ON_LIST = {"", "Advances", "Runoff", "Elected", "Defeated", "Unopposed"}
ORD = r"(\d+)(?:st|nd|rd|th)"
PARTY_SUFFIX = r"(?: - (Democratic Party|Republican Party))?"
# a title that names a state office this loader does not read stops it, so a new kind of race is never passed over
STATE_WORDS = re.compile(r"^(Governor|Lieutenant Governor|Attorney General|Secretary of State|State Treasurer|"
                         r"Commissioner of (Agriculture|Insurance)|Associate Justice|Chief Justice|Judge, Court of Appeal|PSC|BESE|"
                         r"State Senator|State Representative)\b")

SPECIAL_NOTE = (f"A special election for the rest of the term: Representative {HD92['resigned']} resigned effective June 30, 2026, and "
                "the Speaker of the House's proclamation of June 30 set the special primary for November 3 and the special general "
                "election for December 12. It is an open primary: every candidate of every party is on one ballot; more than half "
                "the votes wins the seat, otherwise the top two meet on December 12. Louisiana elects its whole Legislature in odd "
                "years (next in 2027), so no other legislative seat is on the 2026 ballot.")
CLOSED_NOTE = ("A party primary office: Louisiana held its Democratic and Republican primaries on May 16 (runoffs, where needed, on "
               "June 27), and November 3 is the general election between the parties' nominees and anyone who qualified by "
               "nominating petition.")
OPEN_COURT_NOTE = ("Not a party primary office: it runs in Louisiana's open primary on November 3, every candidate on one ballot, "
                   "with the top two meeting on December 12 if nobody wins more than half the votes. The party is printed on the ballot.")
NO_HOLDER = "The Open States roster this site uses does not carry this office, so today's holder is not shown."
NOT_VOTED = ("Not voted on November 3: only one candidate qualified, and the Secretary of State's list marks that candidate "
             "Unopposed. Louisiana declares an unopposed candidate elected.")
UNOPPOSED = ("Unopposed: the only candidate who qualified, as the Secretary of State's list marks it. Louisiana declares an unopposed "
             "candidate elected, so this name is not printed on the November 3 ballot.")
TO_RUNOFF = LA.TO_RUNOFF
TO_DECEMBER = "Goes on to the special general election on December 12: no candidate won more than half the votes."
NOT_ON_LIST = "Won, but is not on the November list for this party."

# the page's last check on notes (build_ballot_state_dev.py Guard, strict): a note that trips it would be dropped, so none may
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[A-Za-z]{2,}")
PHONE = re.compile(r"\(?\b\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}\b")
WEB = re.compile(r"https?://|\bwww\.|\b[\w-]+\.(?:com|org|net|us|gov|edu|info|biz)\b", re.I)
STREET = re.compile(r"\b\d{1,6}\s+(?:[NSEW]\.?\s+)?[A-Za-z0-9.' -]{1,40}?\s(?:St|Street|Ave|Avenue|Rd|Road|Blvd|Boulevard|Dr|Drive|Ln|Lane|Way|Ct|Court|"
                    r"Cir|Circle|Pkwy|Parkway|Hwy|Highway|Trl|Trail|Pl|Place|Ter|Terrace)\b\.?", re.I)
ZIP = re.compile(r"\b[A-Z]{2}\s+\d{5}\b|\b\d{5}-\d{4}\b")


def page_would_drop(text):
    return bool(text) and any(p.search(text) for p in (EMAIL, PHONE, WEB, STREET, ZIP))


# ------------------------------------------------------------------------------------------------------------- offices

def norm(title):
    """One spelling for the three ways the portal writes an office: the office list ("PSC, District 1"), the candidate list
    ("PSC District 1") and the results ("PSC -- District 5 - Democratic Party")."""
    return re.sub(r"\s+", " ", title.replace(" -- ", " ").replace(",", " ")).strip()


def office_of(title):
    """The race a state office title names, with the party of a closed primary, or None for a federal or local office."""
    t = norm(title)
    m = re.fullmatch(rf"State Representative {ORD} Representative District", t)
    if m:
        d = str(int(m.group(1)))
        return dict(race_id=f"2026-{STATE}-SH{d}", level="legislature", office_kind="state_house", office="State Representative",
                    jurisdiction=f"House District {d}", jurisdiction_id=d, district=d, seat=None, partisan=1, chamber="House"), None
    m = re.fullmatch(rf"State Senator {ORD} Senatorial District", t)
    if m:
        d = str(int(m.group(1)))
        return dict(race_id=f"2026-{STATE}-SS{d}", level="legislature", office_kind="state_senate", office="State Senator",
                    jurisdiction=f"Senate District {d}", jurisdiction_id=d, district=d, seat=None, partisan=1, chamber="Senate"), None
    m = re.fullmatch(rf"Associate Justice Supreme Court {ORD}(?: Supreme Court)? District{PARTY_SUFFIX}", t)
    if m:
        d = str(int(m.group(1)))
        return dict(race_id=f"2026-{STATE}-SC{d}", level="court", office_kind="supreme_court", office="Associate Justice, Supreme Court",
                    jurisdiction=f"Supreme Court District {d}", jurisdiction_id=f"SC{d}", district=d, seat=None, partisan=1,
                    chamber=None), m.group(2)
    m = re.fullmatch(rf"Judge Court of Appeal {ORD} Circuit {ORD} Dist(?:\.|rict) (At Large|Division ([A-Z]))", t)
    if m:
        c, d = str(int(m.group(1))), str(int(m.group(2)))
        seat = m.group(3)
        code = "AL" if seat == "At Large" else m.group(4)
        return dict(race_id=f"2026-{STATE}-COA{c}-{d}-{code}", level="court", office_kind="court_of_appeals", office="Judge, Court of Appeal",
                    jurisdiction=f"Court of Appeal, {ordinal(c)} Circuit, {ordinal(d)} District, {seat}", jurisdiction_id=f"COA{c}-{d}",
                    district=f"{c}-{d}", seat=seat, partisan=1, chamber=None), None
    m = re.fullmatch(rf"PSC District (\d+){PARTY_SUFFIX}", t)
    if m:
        d = str(int(m.group(1)))
        return dict(race_id=f"2026-{STATE}-PSC{d}", level="statewide", office_kind="public_service_commissioner",
                    office="Public Service Commissioner", jurisdiction=f"Public Service Commission District {d}", jurisdiction_id=f"PSC{d}",
                    district=d, seat=None, partisan=1, chamber=None), m.group(2)
    m = re.fullmatch(rf"BESE District (\d+){PARTY_SUFFIX}", t)
    if m:
        d = str(int(m.group(1)))
        return dict(race_id=f"2026-{STATE}-SBOE{d}", level="statewide", office_kind="state_board_of_education",
                    office="Member, Board of Elementary and Secondary Education", jurisdiction=f"BESE District {d}",
                    jurisdiction_id=f"BESE{d}", district=d, seat=None, partisan=1, chamber=None), m.group(2)
    if STATE_WORDS.match(title.strip()):
        raise SystemExit(f"Louisiana: a state office on the Candidate Inquiry that this loader does not read ({title!r})")
    return None


def ordinal(n):
    n = int(n)
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def other_kind(title):
    return "federal" if re.match(r"U\. ?S\. ", title) else "local offices and district courts"


# ------------------------------------------------------------------------------------------------ fetching and caching

def fresh(path, days):
    return os.path.exists(path) and time.time() - os.path.getmtime(path) < days * 86400


def ask(fn, what, say):
    """One request, asked at most twice more on a refusal or a server error (never past a challenge page)."""
    for attempt in range(3):
        try:
            return fn()
        except HTTPError as e:
            if e.code not in (403, 429, 500, 502, 503, 504) or attempt == 2:
                raise
            say(f"      {what}: HTTP {e.code}; asking again in {10 * (attempt + 1)} s")
            time.sleep(10 * (attempt + 1))


def read_inquiry(folder, say, max_age_days=2):
    """The state offices' kept cells for the four elections, as JSON in the cache; the answers are never written."""
    path = os.path.join(folder, LIST_FILE)
    if fresh(path, max_age_days):
        return path
    get = lambda url: ask(lambda: net.get(url, accept="text/html"), url, say)                  # noqa: E731
    try:
        page = get(LA.INQUIRY)
        ids = LA.election_ids(page.decode("utf-8", "replace"))
        keep = {"read": dt.date.today().isoformat(), "url": LA.INQUIRY, "page_sha256": hashlib.sha256(page).hexdigest(), "elections": {}}
        for date in (NOV, PRI, RUN, DEC):
            if date not in ids:
                raise SystemExit(f"Louisiana: the Candidate Inquiry no longer lists the {date} election")
            time.sleep(1.5)
            raw = get(LA.OFFICE_LIST + ids[date])
            offs = LA.offices(raw.decode("utf-8", "replace"))
            if not offs:
                raise SystemExit(f"Louisiana: the Candidate Inquiry's office list for {date} is empty")
            want, others = [], {}
            for i, t in offs:
                if office_of(t) is None:
                    others[other_kind(t)] = others.get(other_kind(t), 0) + 1
                else:
                    want.append((i, t))
            e = {"id": ids[date], "office_list_sha256": hashlib.sha256(raw).hexdigest(), "offices": dict(want), "others": others, "lists": []}
            if want:
                time.sleep(1.5)
                ans = ask(lambda: LA.post(LA.CANDIDATE_LIST, [("electionId", ids[date])] + [("officeIds", i) for i, _t in want]),
                          LA.CANDIDATE_LIST, say)
                lists = LA.candidate_list(ans, date)
                e["list_sha256"] = hashlib.sha256(ans.encode("utf-8")).hexdigest()
                del ans
                if sorted(norm(o["office"]) for o in lists) != sorted(norm(t) for _i, t in want):
                    raise SystemExit(f"Louisiana: the {date} candidate list does not answer for the offices asked "
                                     f"({len(want)} asked, {len(lists)} answered)")
                by_title = {norm(t): i for i, t in want}
                for o in lists:
                    o["office_id"] = by_title[norm(o["office"])]
                e["lists"] = lists
            keep["elections"][date] = e
            say(f"      Candidate Inquiry {date}: {len(want)} state offices, {sum(len(o['candidates']) for o in e['lists'])} candidates; "
                + (", ".join(f"{n} {k}" for k, n in sorted(others.items())) + " counted only" if others else "nothing else on its list"))
    except (HTTPError, URLError, OSError) as e:
        if os.path.exists(path):
            say(f"      the Candidate Inquiry could not be read ({e}); using the copy read earlier")
            return path
        raise
    json.dump(keep, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return path


def page_text(raw):
    raw = re.sub(r"<script.*?</script>|<style.*?</style>", "", raw.decode("utf-8", "replace"), flags=re.S)
    return re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", raw))).strip()


# the sentences kept from the Secretary's two pages (the pages themselves are never saved: they carry a hotline number)
PHRASES = {
    DATES_URL: {"november": r"November 3, 2026 - [A-Za-z./ ]+? Election(?= The following)",
                "party_general": r"The November 3, 2026 election is the open general election date for party primary offices\.",
                "december": r"December 12, 2026 - [A-Za-z./ ]+?\([^)]*State Senator, 14th Senatorial District[^)]*\) Election",
                "sd14_qualifying": r"Special Primary Election \(State Senator, 14th Senatorial District, Parish of East Baton Rouge\): "
                                   r"The qualifying period for candidates is [A-Za-z0-9, -]+?2026\."},
    TYPES_URL: {"closed": r"Beginning in 2026, closed party primaries will be held in the Spring for .{10,200}?\(BESE\)\.",
                "open": r"If there is no majority vote winner in the primary election then the top two candidates go to a run-off election "
                        r"called a general election\."},
}


def read_pages(folder, say, max_age_days=7):
    path = os.path.join(folder, PAGES_FILE)
    if fresh(path, max_age_days):
        return json.load(open(path, encoding="utf-8"))
    keep = {"read": dt.date.today().isoformat(), "pages": {}}
    try:
        for url, pats in PHRASES.items():
            raw = ask(lambda: net.get(url, accept="text/html"), url, say)
            text = page_text(raw)
            got = {}
            for k, p in pats.items():
                m = re.search(p, text)
                got[k] = m.group(0) if m else None
            keep["pages"][url] = {"sha256": hashlib.sha256(raw).hexdigest(), "phrases": got}
            time.sleep(1.5)
    except (HTTPError, URLError, OSError) as e:
        if os.path.exists(path):
            say(f"      the Secretary's election pages could not be read ({e}); using the copy read earlier")
            return json.load(open(path, encoding="utf-8"))
        raise
    json.dump(keep, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return keep


def official_dates(folder, max_age_days=2):
    path = os.path.join(folder, STATUS_FILE)
    if fresh(path, max_age_days):
        return json.load(open(path, encoding="utf-8"))
    got = json.loads(LA.data("ElectionDates.htm"))["Dates"]["Date"]
    kept = {d["ElectionDate"]: d.get("ResultsOfficial") == "1" for d in got if d.get("ElectionDate", "").endswith("/2026")}
    json.dump(kept, open(path, "w", encoding="utf-8"), indent=1)
    return kept


def as_list(x):
    return x if isinstance(x, list) else [x] if x else []


def read_results(date, folder, race_ids, max_age_days=30):
    """The official results of the races whose ids are given (the Candidate Inquiry's office ids), with each race's parish
    rows: names and numbers only. Kept for 30 days (a day for an election whose results are still being certified)."""
    path = os.path.join(folder, f"sl_la_2026_results_{ISO[date].replace('-', '')}_state.json")
    if fresh(path, max_age_days):
        kept = json.load(open(path, encoding="utf-8"))
        if set(kept.get("asked", [])) == set(race_ids):
            return path, kept
    folder_name = ISO[date].replace("-", "")
    races = json.loads(LA.data(f"{folder_name}/RacesCandidates_Multiparish.htm"))["Races"]
    time.sleep(1.5)
    votes = {r["ID"]: r for r in as_list(json.loads(LA.data(f"{folder_name}/Votes_Multiparish.htm"))["Races"]["Race"])}
    out = {"date": date, "written": races.get("WriteTime"), "asked": sorted(race_ids), "races": []}
    for r in as_list(races["Race"]):
        if r["ID"] not in race_ids:
            continue
        title = re.sub(r"\s+", " ", r["SpecificTitle"]).strip()
        v = votes.get(r["ID"])
        if v is None:
            raise SystemExit(f"Louisiana: the {date} results have no votes for {title}")
        vc = {c["ID"]: c for c in as_list(v["Choice"])}
        choices = [{"name": re.sub(rf"\s*\({LA.RESULT_PARTY}\)$", "", c["Desc"]).strip(), "desc": c["Desc"],
                    "votes": int(vc[c["ID"]]["VoteTotal"]), "outcome": vc[c["ID"]].get("Outcome")} for c in as_list(r["Choice"])]
        time.sleep(1.5)
        rows = list(csv.reader(io.StringIO(LA.data(f"{folder_name}/csv/ByParish_{r['ID']}.csv"))))
        head, parishes = rows[0], {}
        if head[:2] != ["Office", "Parish"] or sorted(head[2:]) != sorted(c["desc"] for c in choices):
            raise SystemExit(f"Louisiana: the parish file for {title} on {date} does not name the same candidates")
        for row in rows[1:]:
            if row:
                parishes[row[1]] = {h: int(x.replace(",", "") or 0) for h, x in zip(head[2:], row[2:])}
        out["races"].append({"id": r["ID"], "title": title, "closed": r.get("IsClosedParty") == "1", "choices": choices,
                             "precincts": [v["PrecinctsReporting"], v["PrecinctsExpected"]],
                             "absentee": [v["NumAbsenteeReporting"], v["NumAbsenteeExpected"]], "parishes": parishes})
    json.dump(out, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return path, out


def checked(res, problems):
    """Each race's statewide votes against its parish rows, and every precinct and absentee count reported."""
    for r in res["races"]:
        where = f"{r['title']} ({res['date']})"
        if not r["parishes"]:
            problems.append(f"{where}: no parish rows")
        for c in r["choices"]:
            summed = sum(p.get(c["desc"], 0) for p in r["parishes"].values())
            if summed != c["votes"]:
                problems.append(f"{where}: {c['name']}'s parish rows add to {summed:,}, the total is {c['votes']:,}")
        if r["precincts"][0] != r["precincts"][1] or r["absentee"][0] != r["absentee"][1]:
            problems.append(f"{where}: {r['precincts'][0]} of {r['precincts'][1]} precincts reported")


# ================================================================================= the parish and local part: reading
#
# Three readings of the Secretary of State's November 3 list, each cut down in memory to the cells named here before
# anything else touches it; only the cut-down copies are kept (ballot_cache/la/local/), never an answer as it arrived.
#   1. Candidate Inquiry, "Races in a Parish", parish by parish, twice: the CSV export (columns by name) and the page
#      itself (the federal loader's reader: office title, first line of the name and party columns, the status cell).
#   2. Candidate Inquiry, the statewide tab: the district and multi-parish offices' own list.
#   3. The results site's race files for November 3 (no contact fields at all): the contests that will be voted on.

LOCAL_FOLDER = "local"
PARISH_FILE = "sl_la_2026_local_parish_lists.json"
WIDE_FILE = "sl_la_2026_local_statewide_tab.json"
FEED_FILE = "sl_la_2026_local_results_feed.json"
PARISH_INDEX = LA.PORTAL + "/CandidateInquiry/ParishCandidate/Index?electionId="
PARISH_RACES = LA.PORTAL + "/CandidateInquiry/ParishCandidate/RacesInParish?electionId={e}&parishId={p}"
PARISH_EXPORT = LA.PORTAL + "/CandidateInquiry/ParishCandidate/Export?electionId={e}&electionDate={d}&parishId={p}&parishName={n}"
CSV_KEEP = {"election": "Election", "parish": "Parish", "title": "OfficeTitle", "desc": "OfficeTitleDescription",
            "n": "NumberToBeElected", "first": "BallotFirstName", "last": "BallotLastName", "suffix": "BallotSuffix",
            "party": "Party", "status": "Outcome"}
CSV_NEVER = ("Address", "City", "State", "Zip", "Address Mismatch", "Phone", "Email Address", "Race", "Gender", "Filed Date")
NOT_A_NAME = re.compile(r"@|\d{3}|\bwww\.|\.(?:com|org|net|gov)\b", re.I)
LOCAL_MAX_AGE = 2                # days a cut-down copy is used before the lists are read again
PAUSE = 1.2                      # seconds between requests
PROPOSITION_LEVELS = ("998", "999")      # the results site's level codes for constitutional amendments and local propositions


def spaces(text):
    return re.sub(r"\s+", " ", str(text or "").replace("\xa0", " ")).strip()


def name_cell(text, counter):
    """A name cell as filed, or "" when it holds something that is not a name (contact details typed into the wrong
    column): blanked here, counted, never printed."""
    t = spaces(text)
    if t and (NOT_A_NAME.search(t) or contact_like(t, True)):
        counter["cells that did not hold a name"] += 1
        return ""
    return t


def letters(text):
    return re.sub(r"[^a-z0-9]+", "", (text or "").lower())


def cut_csv(raw, label, counter):
    """One parish's CSV export cut down, as it is parsed, to the columns in CSV_KEEP, found by their headings. The rest
    of each row (address, city, ZIP code, phone, e-mail, race, gender, filing date) is dropped here and goes nowhere.
    A row that does not fit stops the loader, which names the parish, the row number and the check, never the row."""
    table = list(csv.reader(io.StringIO(raw.decode("utf-8-sig", "replace"))))
    head = [h.strip() for h in table[0]] if table else []
    if any(head.count(c) != 1 for c in CSV_KEEP.values()):
        raise SystemExit(f"Louisiana: the Candidate Inquiry's export for {label} does not have the columns this loader reads by name")
    counter["export columns this loader does not know (they are not read)"] += sum(
        1 for h in head if h not in CSV_KEEP.values() and h not in CSV_NEVER)
    idx = {k: head.index(c) for k, c in CSV_KEEP.items()}
    rows = []
    for n, cells in enumerate(table[1:], 2):
        if not any(c.strip() for c in cells):
            continue
        if len(cells) != len(head):
            raise SystemExit(f"Louisiana: row {n} of the export for {label} has {len(cells)} cells, not the heading's {len(head)} "
                             "(the row is not printed)")
        row = {k: spaces(cells[i]) for k, i in idx.items()}
        if row.pop("election") != NOV or row.pop("parish") != label:
            raise SystemExit(f"Louisiana: row {n} of the export for {label} is for another election or parish (the row is not printed)")
        if not row["title"] or not row["n"].isdigit():
            raise SystemExit(f"Louisiana: row {n} of the export for {label} lacks an office or the number to be elected (the row is not printed)")
        for k in ("first", "last", "suffix"):
            row[k] = name_cell(row[k], counter)
        if (contact_like(row["title"], False) or contact_like(row["desc"], False) or not re.fullmatch(r"[A-Za-z ]{0,30}", row["party"])
                or not re.fullmatch(r"[A-Za-z/ ]{0,20}", row["status"])):      # the Secretary's own words: checked, not guessed at
            raise SystemExit(f"Louisiana: row {n} of the export for {label} has an office, party or status cell that is not one "
                             "(the row is not printed)")
        row["n"] = int(row["n"])
        rows.append(row)
    del table
    return rows


def parish_offices(rows, listed, label, counter, problems):
    """One parish's offices from its two readings, which must agree: the export gives the office and its description
    apart and the names in parts; the page gives each name as the ballot prints it and the offices nobody qualified for."""
    by, order = {}, []
    for r in rows:
        key = spaces(f"{r['title']} {r['desc']}")
        if key not in by:
            by[key] = {"title": r["title"], "desc": r["desc"], "n": r["n"], "rows": []}
            order.append(key)
        o = by[key]
        if (o["title"], o["desc"], o["n"]) != (r["title"], r["desc"], r["n"]):
            raise SystemExit(f"Louisiana: two offices of {label}'s export read the same once joined, or disagree on the number to be elected")
        o["rows"].append(r)
    out, seen = [], set()
    for o in listed:
        key = spaces(o["office"])
        if key in seen:
            raise SystemExit(f"Louisiana: {label}'s page lists the office {key!r} twice")
        seen.add(key)
        names = [name_cell(c["name"], counter) for c in o["candidates"]]
        e = by.get(key)
        if e is None:
            if o["candidates"]:
                raise SystemExit(f"Louisiana: {label}'s page has candidates for {key!r} and its export has none")
            out.append({"joined": key, "title": None, "desc": None, "n": o["to_elect"], "cands": []})
            continue
        if o["to_elect"] != e["n"]:
            raise SystemExit(f"Louisiana: {label}'s page and export disagree on the number to be elected for {key!r}")
        both = [(letters(" ".join(x for x in (r["first"], r["last"], r["suffix"]) if x)), r["party"], r["status"]) for r in e["rows"]]
        page = [(letters(n), c["party"], c["status"]) for n, c in zip(names, o["candidates"])]
        if sorted(both) != sorted(page):
            raise SystemExit(f"Louisiana: {label}'s page and export do not list the same candidates for {key!r} (names are not printed)")
        if both != page:
            problems.append(f"{label}: the page and the export list {key}'s candidates in a different order; the page's order is kept")
        last = {k: r["last"] for (k, _p, _s), r in zip(both, e["rows"])}
        out.append({"joined": key, "title": e["title"], "desc": e["desc"], "n": e["n"],
                    "cands": [{"name": n, "last": last[letters(n)], "party": c["party"], "status": c["status"]}
                              for n, c in zip(names, o["candidates"])]})
    missing = [k for k in order if k not in seen]
    if missing:
        raise SystemExit(f"Louisiana: {label}'s export has {len(missing)} office(s) its page does not list ({missing[0]!r} ...)")
    return out


def read_parish_lists(folder, election_id, say, max_age_days=LOCAL_MAX_AGE):
    """Every parish's November 3 list, both readings reconciled, as ballot_cache/la/local/<PARISH_FILE>: allowed cells
    only, with each answer's SHA-256 and row count. A run that stops partway keeps what it has for the same day."""
    path = os.path.join(folder, PARISH_FILE)
    if fresh(path, max_age_days):
        return json.load(open(path, encoding="utf-8"))
    part = path + ".part.json"
    today = dt.date.today().isoformat()
    keep = {"read": today, "election": NOV, "election_id": election_id, "parishes": {}, "dropped": {}, "order_notes": []}
    if os.path.exists(part):
        old = json.load(open(part, encoding="utf-8"))
        if old.get("read") == today and old.get("election_id") == election_id:
            keep = old
    get = lambda url, accept: ask(lambda: net.get(url, accept=accept), url.split("?")[0], say)      # noqa: E731
    try:
        raw = get(PARISH_INDEX + election_id, "text/html")
        keep["index_sha256"] = hashlib.sha256(raw).hexdigest()
        sel = re.search(r'<select[^>]*id="parish"[^>]*>(.*?)</select>', raw.decode("utf-8", "replace"), re.S)
        opts = [(v, LA.text_of(t)) for v, t in re.findall(r'<option[^>]*value="(\d+)"[^>]*>(.*?)</option>', sel.group(1), re.S)] if sel else []
        if len(opts) != LA.PARISHES or any(not re.fullmatch(r"[A-Z. ]+ - \d\d", t) for _v, t in opts):
            raise SystemExit(f"Louisiana: the Candidate Inquiry's parish list has {len(opts)} parishes written in a way this loader does not read")
        counter = collections.Counter(keep["dropped"])
        for k, (pid, label) in enumerate(opts, 1):
            num = label[-2:]
            if num in keep["parishes"]:
                continue
            time.sleep(PAUSE)
            raw = get(PARISH_EXPORT.format(e=election_id, d=quote(NOV), p=pid, n=quote(label)), "text/csv, */*")      # as the page's own script asks
            if not raw.lstrip(b"\xef\xbb\xbf").startswith(b'"Election"'):
                raise SystemExit(f"Louisiana: the Candidate Inquiry's export for {label} did not come back as its CSV")
            rows = cut_csv(raw, label, counter)
            csv_sha, csv_bytes = hashlib.sha256(raw).hexdigest(), len(raw)
            time.sleep(PAUSE)
            raw = get(PARISH_RACES.format(e=election_id, p=pid), "text/html")
            if b"candidate-title-row" not in raw:
                raise SystemExit(f"Louisiana: the Candidate Inquiry's page for {label} did not come back as its list of races")
            listed = LA.candidate_list(raw.decode("utf-8", "replace"), label)
            offices = parish_offices(rows, listed, label, counter, keep["order_notes"])
            keep["parishes"][num] = {"pid": pid, "label": label, "csv_sha256": csv_sha, "csv_bytes": csv_bytes, "csv_rows": len(rows),
                                     "page_sha256": hashlib.sha256(raw).hexdigest(), "page_bytes": len(raw), "offices": offices}
            del raw, rows, listed
            keep["dropped"] = dict(counter)
            if k % 8 == 0 or k == len(opts):
                say(f"      Candidate Inquiry, races in a parish: {k} of {len(opts)} parishes read")
                with open(part, "w", encoding="utf-8") as fh:
                    json.dump(keep, fh, ensure_ascii=False)
    except (HTTPError, URLError, OSError) as e:
        if keep["parishes"]:
            with open(part, "w", encoding="utf-8") as fh:
                json.dump(keep, fh, ensure_ascii=False)
        if os.path.exists(path):
            say(f"      the parish lists could not be read again ({type(e).__name__}); using the copy read earlier")
            return json.load(open(path, encoding="utf-8"))
        raise SystemExit(f"Louisiana: the Candidate Inquiry stopped answering ({type(e).__name__} {getattr(e, 'code', '')}) after "
                         f"{len(keep['parishes'])} of {LA.PARISHES} parishes; run again later (what was read is kept)")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(keep, fh, ensure_ascii=False, indent=0)
    if os.path.exists(part):
        os.remove(part)
    return keep


def read_wide(folder, election_id, say, max_age_days=LOCAL_MAX_AGE):
    """The statewide tab's office list (ids and titles) and, for its district and multi-parish offices, its own candidate
    list: kept cells only, with each answer's SHA-256."""
    path = os.path.join(folder, WIDE_FILE)
    if fresh(path, max_age_days):
        return json.load(open(path, encoding="utf-8"))
    counter = collections.Counter()
    try:
        raw = ask(lambda: net.get(LA.OFFICE_LIST + election_id, accept="text/html"), LA.OFFICE_LIST, say)
        offs = LA.offices(raw.decode("utf-8", "replace"))
        if not offs:
            raise SystemExit("Louisiana: the Candidate Inquiry's office list for November 3 is empty")
        want = [(i, t) for i, t in offs if office_of(t) is None and not re.match(r"U\. ?S\. ", t)]
        keep = {"read": dt.date.today().isoformat(), "election_id": election_id, "office_list_sha256": hashlib.sha256(raw).hexdigest(),
                "all": len(offs), "offices": dict(want), "lists": []}
        time.sleep(PAUSE)
        ans = ask(lambda: LA.post(LA.CANDIDATE_LIST, [("electionId", election_id)] + [("officeIds", i) for i, _t in want]),
                  LA.CANDIDATE_LIST, say)
        keep["list_sha256"], keep["list_bytes"] = hashlib.sha256(ans.encode("utf-8")).hexdigest(), len(ans.encode("utf-8"))
        lists = LA.candidate_list(ans, "the statewide tab")
        del ans
        if sorted(norm(o["office"]) for o in lists) != sorted(norm(t) for _i, t in want):
            raise SystemExit(f"Louisiana: the statewide tab's candidate list does not answer for the offices asked ({len(want)} asked, "
                             f"{len(lists)} answered)")
        by_title = {norm(t): i for i, t in want}
        if len(by_title) != len(want):
            raise SystemExit("Louisiana: two offices on the statewide tab read the same")
        for o in lists:
            o["office_id"] = by_title[norm(o["office"])]
            for c in o["candidates"]:
                c["name"] = name_cell(c["name"], counter)
        keep["lists"], keep["dropped"] = lists, dict(counter)
    except (HTTPError, URLError, OSError) as e:
        if os.path.exists(path):
            say(f"      the statewide tab could not be read again ({type(e).__name__}); using the copy read earlier")
            return json.load(open(path, encoding="utf-8"))
        raise SystemExit(f"Louisiana: the Candidate Inquiry's statewide tab did not answer ({type(e).__name__} {getattr(e, 'code', '')})")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(keep, fh, ensure_ascii=False, indent=0)
    return keep


def read_feed(folder, say, max_age_days=LOCAL_MAX_AGE):
    """The results site's race files for November 3 (the contests that will be voted on, and their choices as the site
    will report them): ids, titles, level codes, the number to be elected and each choice's printed name with its party
    tag. The files carry no contact fields; the text of ballot propositions is not kept."""
    path = os.path.join(folder, FEED_FILE)
    if fresh(path, max_age_days):
        return json.load(open(path, encoding="utf-8"))
    day = GENERAL.replace("-", "")
    blob = lambda name: ask(lambda: net.get(LA.DATA + f"{day}/{name}", accept="application/json, */*"), name, say)      # noqa: E731
    counter = collections.Counter()
    keep = {"read": dt.date.today().isoformat(), "files": {}, "races": [], "choices": {}}
    try:
        raw = blob("ElectionRaces.htm")
        keep["files"]["ElectionRaces.htm"] = hashlib.sha256(raw).hexdigest()
        for r in as_list(json.loads(raw.decode("utf-8-sig"))["Races"]["Race"]):
            keep["races"].append({"id": r["RaceID"], "level": r["Level"], "title": spaces(r["OfficeTitleAndDesc"])})
        level_of = {r["id"]: r["level"] for r in keep["races"]}
        if len(level_of) != len(keep["races"]):
            raise SystemExit("Louisiana: the results site's race list gives one id twice")
        names = ["RacesCandidates_Multiparish.htm"] + [f"RacesCandidates/ByParish_{n:02d}.htm" for n in range(1, LA.PARISHES + 1)]
        for k, name in enumerate(names):
            time.sleep(PAUSE)
            raw = blob(name)
            keep["files"][name] = hashlib.sha256(raw).hexdigest()
            got = json.loads(raw.decode("utf-8-sig"))["Races"]
            keep["written"] = max(keep.get("written", ""), got.get("WriteTime") or "")
            for r in as_list(got.get("Race")):
                if level_of.get(r["ID"]) in PROPOSITION_LEVELS:     # a proposition: counted from the race list, its text never kept
                    continue
                if r["ID"] not in level_of or "Choice" not in r:
                    raise SystemExit(f"Louisiana: race {r['ID']} of the results site's {name} is not in its race list, or has no choices")
                if r["ID"] in keep["choices"]:
                    raise SystemExit(f"Louisiana: race {r['ID']} is in two of the results site's race files")
                keep["choices"][r["ID"]] = {
                    "file": name[-6:-4] if k else "multi", "general": spaces(r.get("GeneralTitle")), "specific": spaces(r.get("SpecificTitle")),
                    "level": r.get("OfficeLevel"), "n": int(r.get("NumberToBeElected") or 0), "multi": r.get("IsMultiParish") == "1",
                    "runoff": r.get("CanHaveRunoff") == "1", "closed": r.get("IsClosedParty") == "1",
                    "choices": [name_cell(c.get("Desc"), counter) for c in as_list(r.get("Choice"))]}
            if k and (k % 16 == 0 or k == LA.PARISHES):
                say(f"      results site, November 3 race files: {k} of {LA.PARISHES} parishes read")
        keep["dropped"] = dict(counter)
    except (HTTPError, URLError, OSError) as e:
        if os.path.exists(path):
            say(f"      the results site's race files could not be read again ({type(e).__name__}); using the copy read earlier")
            return json.load(open(path, encoding="utf-8"))
        raise SystemExit(f"Louisiana: the results site did not answer ({type(e).__name__} {getattr(e, 'code', '')})")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(keep, fh, ensure_ascii=False, indent=0)
    return keep


# ============================================================================ the parish and local part: what each office is

FIPS = "22"
COUNTY_ZIP = os.path.join(HERE, "states_cache", "census", "cb_2024_us_county_500k.zip")
COUNTY_URL = "https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_county_500k.zip"
PLACE_FILE = "st22_la_place2020.txt"
PLACE_URL = "https://www2.census.gov/geo/docs/reference/codes2020/place/st22_la_place2020.txt"
PLACE_HEAD = ["STATE", "STATEFP", "PLACEFP", "PLACENS", "PLACENAME", "TYPE", "CLASSFP", "FUNCSTAT", "COUNTIES"]
UNSD_FILE = "cb_2024_22_unsd_500k.zip"
UNSD_URL = "https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_22_unsd_500k.zip"
LAW_FILE = "sl_la_2026_local_law_pages.json"
LAW_402 = "https://legis.la.gov/Legis/Law.aspx?d=81545"
LAW_511 = "https://legis.la.gov/Legis/Law.aspx?d=81616"
LAW_551 = "https://legis.la.gov/Legis/Law.aspx?d=81637"
# the sentences kept from the Legislature's pages of the Election Code (the pages carry the Capitol's mailing address in
# their footer, so only these sentences are kept, with each page's SHA-256)
LAW = {
    LAW_402: {"fall_primary": r"There shall be a fall primary election held on the first Tuesday after the first Monday in November for officers "
                              r"elected at the same time as members of congress in that year\.",
              "fall_general": r"There shall be a fall general election held on the sixth Saturday after the first Tuesday after the first Monday "
                              r"in November of a congressional election year\.",
              "governor": r"There shall be a fall primary election held on the third to last Saturday in October of a gubernatorial election "
                          r"year for governor and officers elected at the same time as the governor\.",
              "special": r"Special elections to fill newly created offices or vacancies in office shall be held on dates fixed by the "
                         r"appropriate authority in the proclamation issued in accordance with law\."},
    LAW_511: {"majority": r"A candidate who receives a majority of the votes cast for an office in a primary election is elected\.",
              "unopposed": r"the candidates for that office, or those remaining after the withdrawal of one or more candidates, are declared "
                           r"elected by the people, and their names shall not appear on the ballot in either the primary or the general election\."},
    LAW_551: {"order": r"The names of the candidates for each office shall be arranged alphabetically by surname and shall be listed below the "
                       r"title of the office\."},
}
SCHEDULE_FILE = "la_sos_offices_regularly_scheduled_congressional.pdf"
SCHEDULE_URL = "https://www.sos.la.gov/media/4uhlwtng/congressional-regular-schedule-offices.pdf"
SCHEDULE_SHA = "7e029074fae1c735e5432c744af561e2eb023d527dfe075043a5cfc153d310a9"       # the copy read (2026-09-30)
CALENDAR_FILE = "la_sos_elections_calendar_2026.pdf"
CALENDAR_URL = "https://www.sos.la.gov/media/p31j4zkc/elections-calendar-2026.pdf"
CALENDAR_SHA = "67ceeafd50946e114d39941423f2d6bbf616de080031873b7400bf0ce158f6dd"       # the copy read (2026-09-30)
# What the Secretary of State's table "Congressional / Presidential Elections: Offices Regularly Scheduled to be Filled"
# (revised 08/2024; one sideways page, read by eye, its fingerprint checked on every run) says is filled in 2026: district
# judges, district attorneys, justices of the peace and constables (six-year terms), school board members in every parish
# but Orleans (2028) and Lafayette (with the Governor), the Plaquemines Parish president and council, and the municipal
# offices on the fall cycle (others vote in 2028). It lists no sheriff, clerk of court, assessor, coroner or police juror,
# and no parish president or council but East Baton Rouge's (2028) and Plaquemines'.
SCHEDULE = {"revised": "2024-08", "parish_government_2026": ("22075",), "school_board_other_year": ("22055", "22071")}

SRC_PARISH = "la-sos-2026-local-races-in-a-parish"
SRC_TAB = "la-sos-2026-local-statewide-tab"
SRC_FEED = "la-sos-2026-local-results-race-files"
SRC_COUNTY = "la-census-2024-counties"
SRC_PLACE = "la-census-2020-places"
SRC_SCHOOL = "la-census-2024-school-districts"
SRC_LAW = "la-legislature-election-code"
SRC_SCHEDULE = "la-sos-offices-regularly-scheduled"
SRC_CALENDAR = "la-sos-2026-elections-calendar"

LOCAL_LEVELS = ("county", "soil_water", "city", "township", "school", "hospital", "other")
# The November 3 list is stored as election "general", as this loader's state part stores the Court of Appeal and House
# District 92 (both open primaries too) and as the state and local pages expect: they read "general" as the November
# list. Each race's note says it is the open primary, with the general election on December 12.
LOCAL_ELECTION = "general"
KNOWN_KINDS = {"sheriff", "county_commissioner", "mayor", "council", "school_board", "district_court"}      # kinds the pages already know
LOCAL_GONE = re.compile(r"withdr|disq|deceas|remov|died", re.I)
LOCAL_ON = {"", "Advances", "Runoff", "Elected", "Defeated"}
PARTY_TAG = {"REP": "Republican", "DEM": "Democrat", "NOPTY": "No Party", "LBT": "Libertarian", "OTHER": "Other", "GRN": "Green",
             "IND": "Independent"}                                    # the results site's tag after a name -> the list's word
ABBREV = ((r"\bDiv\.", "Division"), (r"\bElec\. Sect\.", "Election Section"), (r"\bES (?=\d)", "Election Section "),
          (r"\bJust\. Court\b", "Justice Court"), (r"\bDist\.", "District"), (r"\bJDC\b", "Judicial District Court"))
SEAT = re.compile(r"(?:(?:Division|Seat|Place|Section|Domestic Section) \w+|Magistrate Section|At Large)")
COUNCIL_TITLES = re.compile(r"(Alderm[ae]n|Councilm[ae]n|Council Members?|Council Member\(s\)|Selectm[ae]n|Mem\(s\)\., Bd\. of Trustees)( at Large)?")

OPEN_ONE = ("Open primary: every candidate, of any party or none, is on one ballot on November 3. More than half the votes wins; "
            "otherwise the top two meet in the general election on December 12.")
OPEN_MANY = ("Voters choose {n}. Open primary: every candidate, of any party or none, is on one ballot on November 3; any seat not won "
             "by a majority then is decided in the general election on December 12.")
NOT_VOTED_MANY = ("Not voted on November 3: {k} qualified for {n} seats, and the Secretary of State's list marks them Unopposed. "
                  "Louisiana declares unopposed candidates elected.")
NOBODY = "Not on the November 3 ballot: the Secretary of State's list shows no candidate for this office."
NOBODY_LEFT = ("Not on the November 3 ballot: everyone who qualified for this office has withdrawn, been disqualified or died, as the "
               "Secretary of State's list marks them.")
UNEXPIRED = "An election for the rest of an unexpired term, as the Secretary of State's list titles it."
BY_SCHEDULE = ("A special election: the Secretary of State's schedule of regular elections does not fill this office in 2026, and special "
               "elections are held on the regular election dates. The list itself does not mark it.")
UNOPPOSED_LOCAL = "Unopposed: declared elected without a vote, so this name is not printed on the November 3 ballot."
NO_MUNICIPALITY = "The Secretary of State's list titles this office Council Member and names no municipality, so it is filed under the parish."
NO_ORDER = "The Candidate Inquiry and the results site do not list this office's candidates alike, so no ballot order is shown."


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")


def plain_words(text):
    """The list's abbreviations written out (Div. -> Division, ES 1 -> Election Section 1); nothing else is changed."""
    t = spaces(text)
    for a, b in ABBREV:
        t = re.sub(a, b, t)
    return spaces(t)


def where_parts(text):
    """(district, seat) from the words that tell one seat of an office from the next, in the list's own words: 'District 1'
    is district 1 (the page writes District 1); a division, seat, place or section is the seat; the rest is kept as written."""
    dist, seat = [], []
    for p in (x.strip() for x in plain_words(text).split(",")):
        if not p:
            continue
        if re.fullmatch(r"at large", p, re.I):
            p = "At Large"
        (seat if SEAT.fullmatch(p) else dist).append(p)
    d = ", ".join(dist)
    m = re.fullmatch(r"District (\d+)", d)
    return (m.group(1) if m else d) or None, ", ".join(seat) or None


def jp_where(desc):
    """A justice of the peace court's ward or district as the list words it, without the words that repeat the office."""
    d = plain_words(desc)
    m = re.fullmatch(r"Justice of the Peace(?: & Constable)?,? ((?:Wards?|Districts?) .+|Parishwide)", d)
    tail = m.group(1) if m else d
    m = re.fullmatch(r"District (\d+)", tail)
    return m.group(1) if m else tail


def office_words(title, n):
    """The office as the list titles it, with its plural marker settled by the number to be elected."""
    return title.replace("Mem(s)., Bd. of Trustees", "Member(s), Board of Trustees").replace("(s)", "s" if n > 1 else "")


def classify_local(title, desc, n):
    """What one office of the list is, from its title and description: level, office kind, the office in plain words, the
    kind of jurisdiction and the district and seat, or None when no rule here fits (the contest is then left out and listed
    as a gap; nothing is guessed). `schedule` says which line of the Secretary's schedule of regular elections decides
    whether the contest is a special election."""
    d, special = desc or "", 0
    m = re.search(r"\s*\(Unexpired Term\)$", d, re.I)
    if m:
        d, special = d[:m.start()].strip(), 1

    def out(**kw):
        return dict(dict(district=None, seat=None, special=special, schedule=None, said=[]), **kw)

    # ---- courts and their officers
    if title in ("District Judge", "Magistrate Judge"):
        m = re.fullmatch(rf"{ORD} (?:Judicial District Court|JDC)(?:, (.+))?", d)
        if m and (title == "District Judge" or not m.group(2)):
            return out(level="court", kind="district_court", office=title, jt="jdc", jnum=int(m.group(1)), district=str(int(m.group(1))),
                       seat=plain_words(m.group(2)) if m.group(2) else None, idword="magistrate-judge" if title == "Magistrate Judge" else None)
        return None
    if title == "District Attorney":
        m = re.fullmatch(rf"{ORD} Judicial District Court", d)
        if m:
            return out(level="court", kind="district_attorney", office=title, jt="jdc", jnum=int(m.group(1)), district=str(int(m.group(1))))
        return out(level="court", kind="district_attorney", office=title, jt="crdc") if d == "Criminal District Court" else None
    if title == "Judge":
        m = re.fullmatch(r"(Civil|Criminal) District Court, (.+)", d)
        if m:
            return out(level="court", kind="district_court", office=f"Judge, {m.group(1)} District Court",
                       jt="cdc" if m.group(1) == "Civil" else "crdc", seat=plain_words(m.group(2)))
        m = re.fullmatch(r"Juvenile Court, (.+)", d)
        if m:
            dist, seat = where_parts(m.group(1))
            return out(level="court", kind="juvenile_court", office="Judge, Juvenile Court", jt="juvenile", district=dist, seat=seat)
        m = re.fullmatch(rf"{ORD} Parish Court, (.+)", d)
        if m:
            dist, seat = where_parts(m.group(2))
            return out(level="court", kind="parish_court", office="Judge, Parish Court", jt="parish_court", jnum=int(m.group(1)),
                       district=dist, seat=seat)
        return None
    if title == "Magistrate":
        if d == "Magistrate Section, Criminal District Court":
            return out(level="court", kind="district_court", office="Magistrate, Criminal District Court", jt="crdc", seat="Magistrate Section")
        return None
    if title == "Judge, Family Court":
        dist, seat = where_parts(d)
        return out(level="court", kind="family_court", office=title, jt="family", district=dist, seat=seat)
    if title in ("City Judge", "City Judge, City Court", "City Marshal"):
        rest = d if title == "City Judge, City Court" else d[len("City Court, "):] if d.startswith("City Court, ") else None
        if not rest:
            return None
        parts = [p.strip() for p in rest.split(",")]
        if any(not re.match(r"(Division|Div\.|Election Dist\.|Election District|Election Section|Section|Seat|Ward|District) ", p) for p in parts[:-1]):
            return None
        dist, seat = where_parts(", ".join(parts[:-1]))
        marshal = title == "City Marshal"
        return out(level="court", kind="city_marshal" if marshal else "city_court", office="City Marshal" if marshal else "City Judge",
                   jt="city_court", court=parts[-1], district=dist, seat=seat)
    if title == "Constable" and re.fullmatch(rf"{ORD} City Court", d):
        return out(level="court", kind="constable", office="Constable", jt="city_court_parish", court=d)

    # ---- parish offices
    if title in ("Justice of the Peace", "Justice(s) of the Peace", "Constable", "Constable(s)"):
        jp = title.startswith("Justice")
        return out(level="county", kind="justice_of_the_peace" if jp else "constable", office=office_words(title, n), jt="parish",
                   district=jp_where(d))
    if title in ("Sheriff", "Parish President") and not d:
        return out(level="county", kind="sheriff" if title == "Sheriff" else "county_executive", office=title, jt="parish",
                   schedule="never" if title == "Sheriff" else "parish_government")
    if title in ("Member of Parish Council", "Police Juror"):
        dist, seat = where_parts(d)
        juror = title == "Police Juror"
        return out(level="county", kind="county_commissioner" if juror else "county_council", office=title, jt="parish", district=dist,
                   seat=seat, schedule="never" if juror else "parish_government")

    # ---- school boards
    if title in ("Member of School Board", "Member(s) of School Board"):
        parts = [p.strip() for p in d.split(",")]
        system = parts.pop() if len(parts) > 1 and re.fullmatch(r"City of .+|.+ Community", parts[-1]) else None
        dist, seat = where_parts(", ".join(parts))
        return out(level="school", kind="school_board", office=office_words(title, n), jt="school", system=system, district=dist, seat=seat,
                   schedule=None if system else "school")

    # ---- municipal offices: the description ends with the municipality
    m = re.fullmatch(r"(?:(.+), )?(City|Town|Village) of (.+)", d)
    if m:
        where, mkind, mname = m.groups()
        dist, seat = where_parts(where or "")
        base = dict(level="city", jt="muni", mkind=mkind, mname=mname, district=dist, seat=seat)
        if title in ("Mayor", "Chief of Police", "Marshal", "City Prosecutor"):
            if where:
                return None
            kind = {"Mayor": "mayor", "City Prosecutor": "city_prosecutor"}.get(title, "police_chief")
            return out(kind=kind, office=title, **base)
        cm = COUNCIL_TITLES.fullmatch(title)
        if cm:
            if cm.group(2):
                base["seat"] = "At Large" + (", " + seat if seat else "")
            return out(kind="council", office=office_words(cm.group(1), n), **base)
        return None
    if title == "Council Member" and re.fullmatch(r"District \w+", d):       # no municipality named: the parish's own council
        dist, seat = where_parts(d)
        return out(level="county", kind="county_council", office=title, jt="parish", district=dist, seat=seat,
                   schedule="parish_government", said=[NO_MUNICIPALITY])

    # ---- special districts
    if title.endswith(" Community Development District"):
        m = re.fullmatch(r"District Supervisor(?:, (.+))?", d)
        if m:
            dist, seat = where_parts(m.group(1) or "")
            return out(level="other", kind="development_district_board", office="District Supervisor", jt="special", sname=title,
                       district=dist, seat=seat)
    return None


# ============================================================================ the parish and local part: official place lists

def census_parishes(path=COUNTY_ZIP):
    """{the parish's name, letters only: (five-digit code, name with 'Parish')} from the Census Bureau's county file."""
    import shapefile
    z = zipfile.ZipFile(path)
    rdr = shapefile.Reader(dbf=io.BytesIO(z.read(next(n for n in z.namelist() if n.endswith(".dbf")))))
    out = {letters(r["NAME"]): (r["GEOID"], r["NAMELSAD"]) for r in (x.as_dict() for x in rdr.iterRecords()) if r["STATEFP"] == FIPS}
    if len(out) != LA.PARISHES or any(not n.endswith(" Parish") for _g, n in out.values()):
        raise SystemExit(f"Louisiana: the Census county file gives {len(out)} parishes, not {LA.PARISHES}")
    return out


def census_places(path):
    """({name, letters only: [(place code, name with its kind word, kind word)]}, how many) for Louisiana's incorporated
    cities, towns and villages, from the Census Bureau's 2020 place codes."""
    with open(path, encoding="utf-8-sig", errors="replace") as fh:
        lines = fh.read().splitlines()
    if not lines or lines[0].split("|") != PLACE_HEAD:
        raise SystemExit(f"Louisiana: {os.path.basename(path)} does not begin with the header this loader was checked against")
    out, n = collections.defaultdict(list), 0
    for ln in lines[1:]:
        f = ln.split("|")
        if len(f) < 9 or f[1] != FIPS or not f[5].upper().startswith("INCORPORATED"):
            continue
        base, _, kind = f[4].rpartition(" ")
        if kind in ("city", "town", "village") and re.fullmatch(r"\d{5}", f[2]):
            out[letters(base)].append((f[2], f[4], kind))
            n += 1
    return out, n


def census_schools(path):
    """{name, letters only: (seven-digit code, name)} for Louisiana's school districts, from the Census Bureau's file."""
    import shapefile
    z = zipfile.ZipFile(path)
    rdr = shapefile.Reader(dbf=io.BytesIO(z.read(next(n for n in z.namelist() if n.endswith(".dbf")))))
    out = {}
    for r in (x.as_dict() for x in rdr.iterRecords()):
        if r["STATEFP"] == FIPS and re.fullmatch(r"\d{7}", r["GEOID"] or ""):
            out.setdefault(letters(r["NAME"]), []).append((r["GEOID"], r["NAME"]))
    return out


def read_law(folder, say, max_age_days=30):
    """The sentences of the Election Code this part leans on, each found again on the Legislature's page; the pages
    themselves are not saved."""
    path = os.path.join(folder, LAW_FILE)
    if fresh(path, max_age_days):
        return json.load(open(path, encoding="utf-8"))
    keep = {"read": dt.date.today().isoformat(), "pages": {}}
    try:
        for url, pats in LAW.items():
            raw = ask(lambda: net.get(url, accept="text/html"), url, say)
            text = page_text(raw)
            keep["pages"][url] = {"sha256": hashlib.sha256(raw).hexdigest(),
                                  "phrases": {k: (m.group(0) if m else None) for k, m in ((k, re.search(p, text)) for k, p in pats.items())}}
            del raw, text
            time.sleep(PAUSE)
    except (HTTPError, URLError, OSError) as e:
        if os.path.exists(path):
            say(f"      the Legislature's pages could not be read again ({type(e).__name__}); using the sentences read earlier")
            return json.load(open(path, encoding="utf-8"))
        say(f"      the Legislature's pages could not be read ({type(e).__name__}); the sentences of the Election Code are not confirmed this run")
        return keep
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(keep, fh, ensure_ascii=False, indent=1)
    return keep


# ============================================================================ the parish and local part: the rows to write

def joined_sha(hashes):
    return hashlib.sha256("".join(hashes).encode()).hexdigest()


def day_words(iso):
    d = dt.date.fromisoformat(iso)
    return f"{d:%B} {d.day}, {d.year}"


def and_list(items):
    items = [i for i in items if i]
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1] if items else ""


def local_part(folder, election_id, say):
    """The parish and local contests of the November 3 lists -> the rows to write (races, candidates, places, gaps, notes,
    sources) and the counts that reconcile the three readings. Nothing is written here."""
    lists = read_parish_lists(folder, election_id, say)
    tab = read_wide(folder, election_id, say)
    feed = read_feed(folder, say)
    law = read_law(folder, say)
    checks, problems, gaps = list(lists.get("order_notes") or []), [], []
    for source in (lists, tab, feed):
        checks += [f"{what}: {n}" for what, n in (source.get("dropped") or {}).items() if n]
    for url, pg in law["pages"].items():
        for k, v in pg["phrases"].items():
            if not v:
                checks.append(f"the sentence '{k}' is no longer on the Legislature's page of the Election Code ({url.rsplit('=', 1)[-1]}); read it again")
    if set(law["pages"]) != set(LAW):
        checks.append("the Legislature's pages of the Election Code could not all be read this run")

    # ---- official place lists and the Secretary's two schedules
    geo = census_parishes()
    ppath, upath = os.path.join(folder, PLACE_FILE), os.path.join(folder, UNSD_FILE)
    spath, cpath = os.path.join(folder, SCHEDULE_FILE), os.path.join(folder, CALENDAR_FILE)
    net.download(PLACE_URL, ppath, max_age_days=3650, say=say)
    net.download(UNSD_URL, upath, max_age_days=3650, say=say)
    net.download(SCHEDULE_URL, spath, max_age_days=30, say=say)
    net.download(CALENDAR_URL, cpath, max_age_days=30, say=say)
    if open(upath, "rb").read(2) != b"PK" or any(not open(p, "rb").read(5).startswith(b"%PDF") for p in (spath, cpath)):
        raise SystemExit("Louisiana: a reference file for the local part did not come back as the file it should be")
    places, n_places = census_places(ppath)
    schools = census_schools(upath)
    if sha(spath) != SCHEDULE_SHA:
        checks.append("the Secretary of State's table of offices regularly scheduled has changed since it was read (a sideways page, read by "
                      "eye); read it again and update SCHEDULE in this loader")
    if sha(cpath) != CALENDAR_SHA:
        checks.append("the Secretary of State's Schedule of 2026 Elections has changed since it was read; read it again")

    # ---- the parishes, by name, in the Census Bureau's county file
    parish = {}
    for num, v in lists["parishes"].items():
        hit = geo.get(letters(v["label"][:-5]))
        if not hit:
            raise SystemExit(f"Louisiana: the Candidate Inquiry's parish {v['label']} is not in the Census county file by that name")
        parish[num] = {"fips": hit[0], "name": hit[1]}
        if hit[0] != f"{FIPS}{2 * int(num) - 1:03d}":
            checks.append(f"{hit[1]}: the Secretary's parish number {num} is not the usual one for its Census code {hit[0]}")
    if len(parish) != LA.PARISHES or len({p["fips"] for p in parish.values()}) != LA.PARISHES:
        raise SystemExit(f"Louisiana: {len(parish)} parishes read, not {LA.PARISHES} different ones")

    # ---- contests: an office on the statewide tab, or of one municipality, is one contest wherever it is listed; any other
    # office (a school board district, a justice of the peace ward) is its parish's own
    wide_norm = {norm(t): i for i, t in tab["offices"].items()}
    if len(wide_norm) != len(tab["offices"]):
        raise SystemExit("Louisiana: two offices on the statewide tab read the same")
    known_titles = sorted({o["title"] for v in lists["parishes"].values() for o in v["offices"] if o["title"]}, key=len, reverse=True)
    trio = lambda cands: [(x["name"], x["party"], x["status"]) for x in cands]      # noqa: E731
    contests, count = {}, collections.Counter()
    for num in sorted(lists["parishes"]):
        for o in lists["parishes"][num]["offices"]:
            joined, rows = o["joined"], len(o["cands"])
            count["rows"] += rows
            if re.match(r"U\. ?S\. ", joined):
                count["federal_rows"] += rows
                continue
            if office_of(joined) is not None:
                count["state_rows"] += rows
                continue
            count["local_rows"] += rows
            title, desc = o["title"], o["desc"]
            if title is None:                      # an office nobody qualified for is only on the page: its title and description are split here
                title = next((t for t in known_titles if joined == t or joined.startswith(t + " ")), None)
                desc = joined[len(title):].strip() if title else None
            wid = wide_norm.get(norm(joined))
            town = re.search(r"\b(?:City|Town|Village) of (.+)$", desc or "")
            if wid:
                key = ("W", wid)
            elif town and len(places.get(letters(town.group(1)), [])) == 1:
                key = ("M", joined)                # an office of one municipality, the only one of its name, wherever it is listed
            else:
                key = ("P", num, joined)
            c = contests.get(key)
            if c is None:
                contests[key] = c = {"title": title, "desc": desc, "joined": joined, "n": o["n"], "nums": [], "cands": o["cands"]}
            elif key[0] == "P" or num in c["nums"]:
                raise SystemExit(f"Louisiana: {parish[num]['name']}'s list has the office {joined!r} twice")
            elif (c["n"], trio(c["cands"])) != (o["n"], trio(o["cands"])):
                problems.append(f"{joined}: the parishes that list this contest do not list the same candidates; the first parish's list is kept")
            c["nums"].append(num)
    off_tab = sorted(c["joined"] for k, c in contests.items() if k[0] == "M" and len(c["nums"]) > 1)
    if off_tab:
        checks.append("municipal offices on more than one parish's list that the statewide tab does not carry (read as one contest each): "
                      + "; ".join(off_tab))
    tab_list = {o["office_id"]: o for o in tab["lists"]}
    tab_same = 0
    for wid, title in tab["offices"].items():
        c, t = contests.get(("W", wid)), tab_list[wid]
        if c is None:
            problems.append(f"{title}: on the statewide tab, on no parish's list; not loaded")
            gaps.append((STATE, "race", f"{STATE}-{slug(title)}", title, "an office on no parish's list",
                         "The Secretary of State's Candidate Inquiry lists this office on its statewide tab but on no parish's own list, so the "
                         "parishes it reaches are not known and it is not loaded.", LA.INQUIRY))
        elif (t["to_elect"], trio(t["candidates"])) != (c["n"], trio(c["cands"])):
            problems.append(f"{title}: the statewide tab and the parish lists do not list the same candidates; the parish lists are kept")
        else:
            tab_same += 1

    # ---- who is on the ballot: the list's own status words
    for key, c in contests.items():
        for x in c["cands"]:
            if not LOCAL_GONE.search(x["status"]) and x["status"] not in LOCAL_ON and x["status"] != "Unopposed":
                raise SystemExit(f"Louisiana: a status on the parish lists that is not read ({x['status']!r})")
        c["live"] = [x for x in c["cands"] if not LOCAL_GONE.search(x["status"])]
        un = sum(1 for x in c["live"] if x["status"] == "Unopposed")
        if un and un != len(c["live"]):
            raise SystemExit(f"Louisiana: {c['joined']!r} has a candidate marked Unopposed beside others who are not")
        c["state"] = "none" if not c["live"] else "unopposed" if un else "ballot"
        if (c["state"] == "ballot") != (len(c["live"]) > c["n"]):
            checks.append(f"{c['joined']}: {len(c['live'])} candidates for {c['n']} to be elected, marked "
                          + ("Unopposed" if c["state"] == "unopposed" else "as contested"))

    # ---- the results site's race files: the contests that will be voted on, and their choices, must be the list's
    level = {r["id"]: r for r in feed["races"]}
    by_parish = {(num, norm(c["joined"])): k for k, c in contests.items() if k[0] != "W" for num in c["nums"]}
    fcount, seen = collections.Counter(), set()
    for r in feed["races"]:
        fcount["propositions" if r["level"] in PROPOSITION_LEVELS else "candidate_races"] += 1
    for rid, fc in feed["choices"].items():
        title = level[rid]["title"]
        if re.match(r"U\. ?S\. ", title):
            fcount["federal"] += 1
            continue
        if office_of(title) is not None:
            fcount["state"] += 1
            continue
        fcount["local"] += 1
        fcount["local_choices"] += len(fc["choices"])
        key = ("W", rid) if rid in tab["offices"] else by_parish.get((fc["file"], norm(fc["specific"])))
        c = contests.get(key) if key else None
        if c is None:
            problems.append(f"the results site has a contest the Candidate Inquiry's lists do not ({title})")
            continue
        seen.add(key)
        tags = [re.fullmatch(r"(.*?)\s*\(([A-Z]+)\)", d) for d in fc["choices"]]
        fnames = [letters(m.group(1) if m else d) for m, d in zip(tags, fc["choices"])]
        fparty = [PARTY_TAG.get(m.group(2)) if m else None for m in tags]
        names = [letters(x["name"]) for x in c["live"]]
        if c["state"] != "ballot":
            problems.append(f"{c['joined']}: in the results site's race files, though the list does not show it as contested")
        elif sorted(names) != sorted(fnames) or fc["n"] != c["n"]:
            problems.append(f"{c['joined']}: the results site's race file does not name the list's candidates or number to be elected")
        else:
            c["order"] = names == fnames
            fcount["same"] += 1
            fcount["same_choices"] += len(names)
            if c["order"] and [x["party"] for x in c["live"]] != fparty:
                problems.append(f"{c['joined']}: the results site's party tags are not the list's parties")
    for key, c in contests.items():
        if c["state"] == "ballot" and key not in seen:
            problems.append(f"{c['joined']}: contested on the list, not in the results site's race files")

    # ---- races, candidates and places
    races, cands, ids = [], [], {}
    jur, reach = {}, collections.defaultdict(set)       # jurisdiction id -> (place kind, name, source); -> parishes
    stats = collections.Counter()
    kind_differs, uncoded, not_alpha, no_order = [], [], [], []
    for key in sorted(contests, key=lambda k: (k[0], k[1], k[2] if len(k) > 2 else "")):
        c = contests[key]
        nums = sorted(c["nums"])
        cids = sorted(parish[n]["fips"] for n in nums)
        info = classify_local(c["title"], c["desc"], c["n"]) if c["title"] else None
        one = parish[nums[0]] if len(nums) == 1 else None
        jt = info["jt"] if info else None
        if info and jt in ("parish", "school", "cdc", "crdc", "family", "juvenile", "parish_court", "city_court_parish") and not one:
            info = None                                 # a court or board of one parish, listed by several: not placed by guess
        if info is None:
            stats["left_contests"] += 1
            stats["left_rows"] += len(c["cands"]) * len(nums)
            gaps.append((STATE, "race", f"{cids[0]}-{slug(c['joined'])}", f"{c['joined']} ({and_list([parish[n]['name'] for n in nums])})",
                         "an office this loader has no rule for",
                         "The Secretary of State's list titles this office in a way this loader has no rule for yet, so it is left out rather "
                         "than guessed at.", LA.INQUIRY))
            continue
        notes = list(info["said"])
        f3 = one["fips"][2:] if one else None
        if jt == "parish":
            jid, jname, pkind, psrc = one["fips"], one["name"], None, None
        elif jt == "muni":
            hits = places.get(letters(info["mname"]), [])
            if len(hits) == 1:
                code, jname, ckind = hits[0]
                jid, pkind, psrc = f"{STATE}-M-{code}", "mcd", SRC_PLACE
                if ckind != info["mkind"].lower():
                    notes.append(f"The Secretary of State's list calls this municipality the {info['mkind']} of {info['mname']}; the Census "
                                 f"Bureau's 2020 list, whose code is used here, has it as a {ckind}.")
                    kind_differs.append(jname)
            else:
                jname = f"{info['mname']} {info['mkind'].lower()}"
                jid, pkind, psrc = f"{STATE}-M-{cids[0][2:]}-{slug(jname)}", "mcd", SRC_PARISH
                uncoded.append(jname)
        elif jt == "school":
            base = one["name"][:-len(" Parish")]
            sysname = info["system"]
            m = re.fullmatch(r"City of (.+)", sysname or "")
            want = f"{m.group(1)} City School District" if m else f"{sysname} School District" if sysname else f"{base} Parish School District"
            hits = schools.get(letters(want), [])
            if len(hits) == 1:
                jid, jname, pkind, psrc = f"{STATE}-S-{hits[0][0]}", hits[0][1], "school", SRC_SCHOOL
            else:
                jname = f"{sysname} School Board" if sysname else f"{one['name']} School Board"
                jid, pkind, psrc = f"{STATE}-S-{f3}-{slug(jname)}", "school", SRC_PARISH
                uncoded.append(jname)
        elif jt == "special":
            jname = info["sname"]
            jid, pkind, psrc = (f"{STATE}-X-{f3}-{slug(jname)}" if one else f"{STATE}-X-{slug(jname)}"), "special", SRC_PARISH
        elif jt == "jdc":
            jid, jname, pkind, psrc = f"{STATE}-JDC-{info['jnum']}", f"{ordinal(info['jnum'])} Judicial District Court", "judicial", SRC_TAB
        elif jt == "city_court":
            jname = f"City Court, {info['court']}"
            jid, pkind, psrc = f"{STATE}-CC-{slug(info['court'])}", "judicial", SRC_PARISH
        else:                                           # a court of one parish, named with its parish
            head, words = {"cdc": ("CDC", "Civil District Court"), "crdc": ("CRDC", "Criminal District Court"), "family": ("FC", "Family Court"),
                           "juvenile": ("JC", "Juvenile Court"), "parish_court": ("PC", f"{ordinal(info.get('jnum') or 0)} Parish Court"),
                           "city_court_parish": ("CC", info.get("court"))}[jt]
            jname = f"{words}, {one['name']}"
            tail = f"-{info['jnum']}" if jt == "parish_court" else f"-{slug(info['court'])}" if jt == "city_court_parish" else ""
            jid, pkind, psrc = f"{STATE}-{head}-{f3}{tail}", "judicial", SRC_PARISH
        special = info["special"]
        if special:
            notes.append(UNEXPIRED)
        sched = info["schedule"]
        if not special and ((sched == "never") or (sched == "parish_government" and one["fips"] not in SCHEDULE["parish_government_2026"])
                            or (sched == "school" and one["fips"] in SCHEDULE["school_board_other_year"])):
            special = 1
            notes.append(BY_SCHEDULE)
            stats["special_by_schedule"] += 1
        district, seat, n = info["district"], info["seat"], c["n"]
        where = [] if jt == "jdc" else [("d" + district) if district.isdigit() else slug(district)] if district else []
        where += [slug(seat)] if seat else []
        where += [info["idword"]] if info.get("idword") else []
        jkey = jid[len(STATE) + 1:] if jid.startswith(STATE + "-") else jid
        rid = "-".join([f"2026-{STATE}", jkey, info["kind"].replace("_", "-")] + where) + ("-S" if special else "")
        if not re.fullmatch(rf"2026-{STATE}-[A-Za-z0-9-]+", rid):
            raise SystemExit(f"Louisiana: a race id that is not letters, digits and hyphens ({rid!r})")
        if rid in ids:
            raise SystemExit(f"Louisiana: two offices of the list share the race id {rid}: {ids[rid]!r} and {c['joined']!r}")
        ids[rid] = c["joined"]

        live, order = c["live"], None
        named = [x for x in live if x["name"]]
        if c["state"] == "ballot":
            notes.insert(0, OPEN_ONE if n == 1 else OPEN_MANY.format(n=n))
            order = bool(c.get("order")) and len(named) == len(live)
            if not order:
                notes.append(NO_ORDER)
                no_order.append(rid)
            ranks = [(letters(x["last"]), letters(x["name"])) for x in live]
            if ranks != sorted(ranks):
                not_alpha.append(rid)
        elif c["state"] == "unopposed":
            if n == 1 and len(live) == 1:
                notes.insert(0, NOT_VOTED)
            else:
                left = n - len(live)
                notes.insert(0, NOT_VOTED_MANY.format(k=len(live), n=n)
                             + (f" The list shows no candidate for the other {'seat' if left == 1 else f'{left} seats'}." if left > 0 else ""))
        else:
            notes.insert(0, (NOBODY_LEFT if c["cands"] else NOBODY) + (f" The list gives {n} to be elected." if n > 1 else ""))
        if len(named) != len(live):
            lost = len(live) - len(named)
            notes.append(("One name" if lost == 1 else f"{lost} names") + " on the list for this office could not be read as a name and "
                         + ("is" if lost == 1 else "are") + " left out.")
            gaps.append((STATE, "race", rid, f"{info['office']}, {jname}", "a candidate whose name could not be read",
                         "A name cell for this office on the Secretary of State's list held something other than a name, so that candidate is "
                         "left out until the list is corrected.", LA.INQUIRY))
            stats["names_unread"] += lost
        races.append([rid, STATE, info["level"], info["kind"], info["office"], jname, jid, json.dumps(cids), district, seat, special, 1,
                      None, None, None, GENERAL, " ".join(notes) or None])
        for k, x in enumerate(live, start=1):
            if not x["name"]:
                continue
            if not x["party"]:
                raise SystemExit(f"Louisiana: a candidate for {rid} has no party word on the list")
            un = c["state"] == "unopposed"
            cands.append([rid, LOCAL_ELECTION, GENERAL, x["name"], x["party"], party_code(x["party"]), k if order else None, 0, 0, None, None,
                          "unopposed" if un else None, None, SRC_PARISH, UNOPPOSED_LOCAL if un else None])
        stats[c["state"]] += 1
        stats[c["state"] + "_candidates"] += len(named)
        stats["gone"] += len(c["cands"]) - len(live)
        stats["placed_rows"] += len(c["cands"]) * len(nums)
        stats["unique_candidacies"] += len(c["cands"])
        stats["none_left"] += int(c["state"] == "none" and bool(c["cands"]))
        stats["short"] += int(c["state"] == "unopposed" and len(live) < n)
        stats["several_parishes"] += int(len(nums) > 1)
        if pkind:
            jur[jid] = (pkind, jname, psrc)
            reach[jid].update(cids)
    keys = [(x[0], x[3]) for x in cands]
    if len(keys) != len(set(keys)):
        raise SystemExit("Louisiana: two local candidate rows share a race and a name")
    if count["local_rows"] != stats["placed_rows"] + stats["left_rows"]:
        raise SystemExit(f"Louisiana: {count['local_rows']} local rows read but {stats['placed_rows']} placed and {stats['left_rows']} left out")

    # ---- the last look: nothing that reads like contact details is stored
    for r in races:
        if any(v and (contact_like(v, True) or page_would_drop(v)) for v in (r[4], r[5], r[8], r[9], r[16])):
            raise SystemExit(f"Louisiana: a stored cell of {r[0]} failed the contact-detail check (not shown)")
    for x in cands:
        if NOT_A_NAME.search(x[3]) or contact_like(x[3], True) or contact_like(x[4], True) or (x[14] and page_would_drop(x[14])):
            raise SystemExit(f"Louisiana: a stored name, party or note in {x[0]} failed the contact-detail check (not shown)")

    place_rows = [("county", p["fips"], p["name"], json.dumps([p["fips"]]), SRC_COUNTY) for p in sorted(parish.values(), key=lambda p: p["fips"])]
    place_rows += [(kind, jid, name, json.dumps(sorted(reach[jid])), src) for jid, (kind, name, src) in sorted(jur.items())]
    for _k, pid, name, _c, _s in place_rows:
        if contact_like(name, True):
            raise SystemExit(f"Louisiana: the name of place {pid} failed the contact-detail check (not shown)")

    # ---- counts, notes and sources
    local = [r for r in races if r[2] in LOCAL_LEVELS]
    court = [r for r in races if r[2] == "court"]
    lids = {r[0] for r in local}
    by_level = collections.Counter(r[2] for r in races)
    by_kind = collections.Counter(r[3] for r in races)
    reached = {g for r in local for g in json.loads(r[7])}
    n_cands, n_lcands = len(cands), sum(1 for x in cands if x[0] in lids)
    read = lists["read"]
    calendar = (
        "November 3, 2026 is Louisiana's open primary for the local offices filled in congressional election years: district judges and "
        "district attorneys, parish, family, juvenile and city court judges and city marshals, school boards in every parish but Orleans and "
        "Lafayette, justices of the peace and constables, the Plaquemines Parish president and council, and the mayors, police chiefs and "
        "councils of the municipalities on the fall cycle. Every candidate is on one ballot with the party printed; a majority elects, any "
        "seat left goes to the general election on December 12, and a candidate nobody opposed is declared elected and left off the ballot. "
        "Sheriffs, police juries and the other parish offices elected with the Governor (next in 2027), the Orleans and Lafayette school "
        "boards, and the municipalities that vote in the spring or in 2028 are not regularly on this ballot, so a seat of theirs here is a "
        "special election.")
    coverage = (
        f"Loaded from the Secretary of State's Candidate Inquiry as read on {day_words(read)}: every parish, court, school board, municipal "
        f"and special district office on the November 3 lists of all {LA.PARISHES} parishes, {len(races):,} contests. {stats['ballot']:,} will be "
        f"voted on, with {stats['ballot_candidates']:,} candidates; {stats['unopposed']:,} were filled when qualifying closed, their "
        f"{stats['unopposed_candidates']:,} candidates shown as unopposed and not on the ballot; {stats['none']:,} have no candidate left on the "
        f"list. Left off: {stats['gone']:,} candidates marked withdrawn, disqualified or deceased. Not loaded: the "
        f"{fcount['propositions']:,} constitutional amendments and local propositions, the December 12 general election, and who holds each "
        "office today."
        + (f" {stats['left_contests']} offices the loader has no rule for are listed as gaps." if stats["left_contests"] else ""))
    notes = [(STATE, "local_calendar", calendar,
              "La. R.S. 18:402 and 18:511 (Louisiana State Legislature); Louisiana Secretary of State, Schedule of 2026 Elections and Offices "
              "Regularly Scheduled for Congressional and/or Presidential Elections", LAW_402),
             (STATE, "local_coverage", coverage, "Louisiana Secretary of State, Candidate Inquiry (Races in a Parish), November 3, 2026",
              LA.INQUIRY)]
    for _s, k, text, source, _u in notes:
        if contact_like(text, False) or contact_like(source, False):
            raise SystemExit(f"Louisiana: the {k} note reads like contact details")
    for g in gaps:
        if any(contact_like(v, False) for v in g[3:6]):
            raise SystemExit("Louisiana: a gap's words read like contact details")

    pl = lists["parishes"]
    sources = [
        (SRC_PARISH, STATE, "official candidate list", "Louisiana Secretary of State",
         f"Candidate Inquiry, Races in a Parish: the November 3, 2026 lists of all {LA.PARISHES} parishes", LA.INQUIRY, "", read,
         joined_sha([pl[n]["csv_sha256"] + pl[n]["page_sha256"] for n in sorted(pl)]), count["rows"],
         f"Each parish's list was read twice, as the portal's CSV export and as its page (election id {election_id}), and the two had to "
         "agree office by office and name by name. From the export, by column name: " + ", ".join(v for k, v in CSV_KEEP.items())
         + "; from the page: the office title, the number to be elected, the first line of the name and party columns and the status cell. "
         f"The export's other columns ({', '.join(CSV_NEVER)}) are never read, nor is the rest of each candidate's block on the page, and only "
         f"the kept cells are saved. {count['rows']:,} candidate rows: {count['federal_rows']:,} federal (left to the federal pages), "
         f"{count['state_rows']:,} for the state offices this loader's state part reads, and {count['local_rows']:,} local, of which "
         f"{stats['placed_rows']:,} are placed: {stats['unique_candidacies']:,} candidacies in {len(races):,} contests, each in exactly one "
         f"(a contest on several parishes' lists has a row in each: {stats['several_parishes']:,} contests)"
         + (f"; {stats['left_rows']:,} rows of {stats['left_contests']} offices are left out and listed as gaps" if stats["left_contests"] else "")
         + f". Status words: Unopposed ({stats['unopposed_candidates']:,} candidates in {stats['unopposed']:,} contests, declared elected and not "
         f"on the ballot); Withdrew, Other/Disq and Deceased ({stats['gone']:,}, left off). {stats['none']:,} offices have no candidate left "
         "on the list (the page shows them; the export has no row for them). The list gives no ballot position: the law arranges each "
         "office's candidates alphabetically by surname (R.S. 18:551(C)), the list and the results site's race files are in the same order, "
         "and that order is kept as the ballot order of the contested offices"
         + (f" ({len(not_alpha)} contests are not in plain alphabetical order as this loader sorts surnames; their official order is kept)"
            if not_alpha else "")
         + ". Louisiana has no write-ins. The sha256 here is of the answers' own hashes joined."
         + (f" Cells that did not hold a name, blanked: {(lists.get('dropped') or {}).get('cells that did not hold a name')}."
            if (lists.get("dropped") or {}).get("cells that did not hold a name") else "")),
        (SRC_TAB, STATE, "official candidate list", "Louisiana Secretary of State",
         "Candidate Inquiry, statewide tab: the district and multi-parish offices of November 3, 2026", LA.INQUIRY, "", tab["read"],
         joined_sha([tab["office_list_sha256"], tab["list_sha256"]]), sum(len(o["candidates"]) for o in tab["lists"]),
         f"The tab's office list ({tab['all']} offices) says which offices are one contest across parishes: its {len(tab['offices'])} district "
         "judge, district attorney, city court and multi-parish municipal offices. Their candidates on the tab's own list (office title, "
         "first line of the name and party columns, status cell; contact columns never read) were compared with every parish's list of the "
         f"same office: {tab_same} of {len(tab['offices'])} agree, name for name. The parishes a contest reaches are those whose lists "
         "carry it."),
        (SRC_FEED, STATE, "official election setup", "Louisiana Secretary of State",
         "Election results site: the race files for November 3, 2026 (races and choices, before any votes)", LA.RESULTS,
         (feed.get("written") or "")[:10], feed["read"], joined_sha([feed["files"][k] for k in sorted(feed["files"])]),
         sum(len(v["choices"]) for v in feed["choices"].values()),
         f"A check only: the site's race list and its {len(feed['files']) - 1} race files (one for multi-parish contests, one a parish), "
         "which carry no contact fields; the text of propositions is not kept. Its "
         f"{fcount['candidate_races']:,} contests between people are {fcount['federal']} federal, {fcount['state']} state and {fcount['local']:,} "
         f"local; the list's {stats['ballot']:,} contested local offices are those {fcount['local']:,}, and {fcount['same']:,} name the same "
         f"candidates ({fcount['same_choices']:,}) for the same number of seats. {fcount['propositions']} constitutional amendments and local "
         "propositions are counted, not loaded. No votes are read."),
        (SRC_COUNTY, STATE, "county codes", "U.S. Census Bureau", "Cartographic boundary file, counties, 2024 (1:500,000)", COUNTY_URL, "2024",
         mtime(COUNTY_ZIP), sha(COUNTY_ZIP), len(parish),
         "Five-digit codes and names of Louisiana's 64 parishes, matched by name to the Secretary of State's parish list."),
        (SRC_PLACE, STATE, "official place codes", "U.S. Census Bureau", "2020 place codes, Louisiana (st22_la_place2020.txt)", PLACE_URL,
         "2020", mtime(ppath), sha(ppath), n_places,
         f"Names and five-digit place codes of Louisiana's {n_places} incorporated cities, towns and villages. Each municipality on the "
         f"list is the one place of the same name ({sum(1 for v in jur.values() if v[0] == 'mcd' and v[2] == SRC_PLACE)} of "
         f"{sum(1 for v in jur.values() if v[0] == 'mcd')} matched)"
         + (f"; {len(set(kind_differs))} are a town on one list and a village on the other, said on their races" if kind_differs else "")
         + ". The file holds no personal details."),
        (SRC_SCHOOL, STATE, "official district codes", "U.S. Census Bureau",
         "Cartographic boundary file, unified school districts, Louisiana, 2024 (attributes only)", UNSD_URL, "2024", mtime(upath), sha(upath),
         sum(len(v) for v in schools.values()),
         "Names and seven-digit codes of Louisiana's school districts: each parish school board is the district named for its parish, and "
         "the city and community systems the list names (Baker, Bogalusa, Monroe, Central, Zachary) the district of that name."),
        (SRC_LAW, STATE, "statute", "Louisiana State Legislature", "Louisiana Election Code: R.S. 18:402, 18:511 and 18:551", LAW_402, "",
         law["read"], joined_sha([law["pages"][u]["sha256"] for u in sorted(law["pages"])]), sum(len(p["phrases"]) for p in law["pages"].values()),
         "Sentences found on the Legislature's pages, each page's SHA-256 joined (the pages are not kept): the fall primary for officers "
         "elected with Congress and the general election on the sixth Saturday after it (18:402); a majority elects, and candidates nobody "
         "opposes are declared elected and left off the ballot (18:511); candidates are listed alphabetically by surname (18:551). "
         + ("All found." if all(v for p in law["pages"].values() for v in p["phrases"].values()) and set(law["pages"]) == set(LAW)
            else "Not all found this run.")),
        (SRC_SCHEDULE, STATE, "official notice", "Louisiana Secretary of State",
         "Congressional / Presidential Elections: Offices Regularly Scheduled to be Filled", SCHEDULE_URL, SCHEDULE["revised"], mtime(spath),
         sha(spath), 1,
         "One sideways page, read by eye: the offices regularly filled in 2026 and those filled in other years, used for the calendar note "
         "and to mark as special a sheriff's, police juror's, parish council's or Lafayette school board seat on this ballot. "
         + ("The file is the one read." if sha(spath) == SCHEDULE_SHA else "The file has changed since it was read.")),
        (SRC_CALENDAR, STATE, "official notice", "Louisiana Secretary of State", "Schedule of 2026 Elections", CALENDAR_URL, "2026-07",
         mtime(cpath), sha(cpath), 1,
         "Read by eye: November 3 is the open primary and December 12 the open general election; qualifying was August 5 to 7. "
         + ("The file is the one read." if sha(cpath) == CALENDAR_SHA else "The file has changed since it was read.")),
    ]
    if not_alpha:
        checks.append(f"{len(not_alpha)} contests are not in plain alphabetical order by surname as this loader sorts them; the official order is kept")
    if kind_differs:
        checks.append("a town on one list and a village on the other (the Census code is used, and the race says so): " + ", ".join(sorted(set(kind_differs))))
    if uncoded:
        checks.append("no single official entry of the same name, so filed by parish and name: " + ", ".join(sorted(set(uncoded))))
    return dict(races=races, cands=cands, places=place_rows, gaps=gaps, notes=notes, sources=sources, checks=checks, problems=problems,
                stats=dict(stats), count=dict(count), fcount=dict(fcount), by_level=dict(by_level), by_kind=dict(by_kind),
                local=len(local), court=len(court), local_cands=n_lcands, court_cands=n_cands - n_lcands, reached=len(reached),
                tab_same=tab_same, tab_all=len(tab["offices"]), no_order=no_order, new_kinds=sorted(set(by_kind) - KNOWN_KINDS),
                partisan=sum(1 for r in local if r[11]), places_by_kind=dict(collections.Counter(p[0] for p in place_rows)))


# ---------------------------------------------------------------------------------------------------------- the roster

def roster(path):
    """Sitting legislators: ids, names, party, chamber and district only (the roster's contact columns are never selected)."""
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    legs = [dict(zip(("id", "first", "last", "full", "other", "party", "chamber", "district"), r)) for r in con.execute(
        "SELECT bioguide_id, first_name, last_name, official_full, other_names, party_name, chamber, district "
        "FROM legislators WHERE is_current = 1")]
    con.close()
    return legs


def person_fits(name, p):
    """A listed name fits a roster person: same family name and a given name that fits (the roster's first name or any other
    form of the name it keeps). The list prints nicknames in quotation marks, sometimes in place of the given name."""
    readings = [name_parts(name), name_parts(re.sub(r'"[^"]*"', " ", name)), name_parts(name.replace('"', " "))]
    forms = [(fold(p["first"] or "").split(), " ".join(fold(p["last"] or "").split()))]
    forms += [name_parts(o.strip()) for o in (p.get("other") or "").split(";") if o.strip() and "," not in o and "." not in o]
    return any(f[1] and r[1] and r[0] and fits(r, f) for r in readings for f in forms)


def chamber_words(p):
    return f"Louisiana {'Senate' if p['chamber'] == 'Senate' else 'House of Representatives'}, District {int(p['district'])}"


# ------------------------------------------------------------------------------------------------------------ loading

def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def mtime(path):
    return dt.datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d")


def load(db_path, say=print, cache=CACHE, roster_db=ROSTER):
    net.patient_lookups()
    folder = os.path.join(cache, "la")
    os.makedirs(folder, exist_ok=True)
    report = []

    lpath = read_inquiry(folder, say)
    inquiry = json.load(open(lpath, encoding="utf-8"))
    pages = read_pages(folder, say)
    for url, pg in pages["pages"].items():
        for k, v in pg["phrases"].items():
            if not v:
                report.append(f"the sentence '{k}' is no longer on {url}; read the page again")
    ppath = os.path.join(folder, PROC_FILE)
    net.download(PROC_URL, ppath, max_age_days=30, say=say)
    if not open(ppath, "rb").read(5).startswith(b"%PDF"):
        raise SystemExit("Louisiana: the House District 92 proclamation downloaded is not a PDF")
    if sha(ppath) != PROC_SHA:
        report.append("the House District 92 proclamation's file has changed since its dates were read (a scanned page, read by "
                      "eye); read it again and update HD92 in this loader")
    legs = roster(roster_db)
    official = official_dates(folder)

    def identify(race, name, party):
        """(incumbent, state_member_id, note): the seat's own holder when the name fits, else a sitting legislator of the same
        party whose name fits, when exactly one does."""
        h = race.get("_holder")
        if h is not None and person_fits(name, h):
            return 1, h["id"], None
        pool = [p for p in legs if party_code(p["party"]) == party_code(party) and person_fits(name, p)]
        if len(pool) == 1 and not (h is not None and pool[0]["id"] == h["id"]):
            return 0, pool[0]["id"], f"Serves today in the {chamber_words(pool[0])}."
        if len(pool) > 1:
            report.append(f"{race['race_id']}: {name} fits {len(pool)} sitting legislators; none is linked")
        return 0, None, None

    # ---- races and November 3 candidates
    nov = inquiry["elections"][NOV]
    races, cands, gone, order_breaks, nominee, counted = {}, [], [], [], {}, {}
    for o in nov["lists"]:
        info, party = office_of(o["office"])
        if party:
            raise SystemExit(f"Louisiana: a party primary office ({o['office']}) on the November 3 list")
        if o["to_elect"] != 1:
            raise SystemExit(f"Louisiana: {o['office']} on the November 3 list elects {o['to_elect']}, not 1")
        rid = info["race_id"]
        if rid in races:
            raise SystemExit(f"Louisiana: {rid} is on the November 3 list twice")
        live = []
        for c in o["candidates"]:
            if GONE.search(c["status"]):
                gone.append((rid, c["name"]))
                continue
            if c["status"] not in ON_LIST:
                raise SystemExit(f"Louisiana: a status on the November 3 list that is not read ({c['status']!r})")
            live.append(c)
        counted[rid] = (len(o["candidates"]), len(live))
        chamber = info["chamber"]
        hs = [p for p in legs if chamber and p["chamber"] == chamber and str(p["district"]).lstrip("0") == info["district"]]
        h = hs[0] if len(hs) == 1 else None
        special = int(rid == f"2026-{STATE}-SH{HD92['district']}")
        if chamber and not special:
            raise SystemExit(f"Louisiana: a legislative race on the November 3 list that is not the House District 92 special ({o['office']})")
        if special and hs:
            report.append(f"{rid}: the roster still shows {len(hs)} sitting member(s) for this seat, which the proclamation says is vacant; "
                          "no holder is shown")
            h = None
        alone = len(live) == 1 and live[0]["status"] == "Unopposed"
        if any(c["status"] == "Unopposed" for c in live) and not alone:
            raise SystemExit(f"Louisiana: {rid} has a candidate marked Unopposed beside others on the November 3 list")
        closed = info["office_kind"] in ("supreme_court", "public_service_commissioner", "state_board_of_education")
        note = [SPECIAL_NOTE if special else CLOSED_NOTE if closed else OPEN_COURT_NOTE]
        if alone:
            note.append(NOT_VOTED)
        if not chamber:
            note.append(NO_HOLDER)
        races[rid] = dict(race_id=rid, state=STATE, level=info["level"], office_kind=info["office_kind"], office=info["office"],
                          jurisdiction=info["jurisdiction"], jurisdiction_id=info["jurisdiction_id"], county_ids=None,
                          district=info["district"], seat=info["seat"], special=special, partisan=info["partisan"], holder_id=None,
                          holder_name=None, holder_party=None, election_date=GENERAL, note=" ".join(note), _holder=h,
                          _office_id=o["office_id"], _closed=closed, _alone=alone)
        fams = [name_parts(re.sub(r'"', " ", c["name"]))[1] for c in live]
        if fams != sorted(fams):
            order_breaks.append(rid)
        for k, c in enumerate(live, start=1):
            if closed and c["party"] in ("Democrat", "Republican"):
                if (rid, c["party"]) in nominee:
                    raise SystemExit(f"Louisiana: two {c['party']} candidates for {rid} on the November 3 list")
                nominee[(rid, c["party"])] = c["name"]
            inc, mid, n2 = identify(races[rid], c["name"], c["party"])
            notes = [UNOPPOSED] if alone else []
            if n2:
                notes.append(n2)
            cands.append([rid, "general", GENERAL, c["name"], c["party"], party_code(c["party"]), None if alone else k, inc, 0,
                          None, None, "unopposed" if alone else None, mid, SRC_LIST, " ".join(notes) or None])
    if f"2026-{STATE}-SH{HD92['district']}" not in races:
        report.append(f"the House District {HD92['district']} special election is not on the Candidate Inquiry's November 3 list")
    for rid, race in races.items():
        if not any(c[0] == rid for c in cands):
            report.append(f"{rid}: no candidate left on the November 3 list")

    # ---- the spring's closed party primaries and runoffs for the November 3 party primary offices
    problems, upset, used, fields, primary = [], [], {}, 0, []
    party_lists = {}                    # (race, party) -> {date: [candidates]}
    for date in (PRI, RUN):
        for o in inquiry["elections"][date]["lists"]:
            info, party = office_of(o["office"])
            if info["race_id"] not in races:
                continue                # a special election decided in the spring (House District 39), not on November 3
            if not party:
                raise SystemExit(f"Louisiana: {o['office']} on the {date} list is not a party primary")
            live = []
            for c in o["candidates"]:
                if GONE.search(c["status"]):
                    gone.append((info["race_id"], c["name"]))
                    continue
                if c["status"] not in ON_LIST:
                    raise SystemExit(f"Louisiana: a status on the {date} list that is not read ({c['status']!r})")
                if c["party"] != PARTY_OF[party][1]:
                    raise SystemExit(f"Louisiana: a {c['party']} candidate in the {party} primary for {info['race_id']}")
                live.append(c)
            party_lists.setdefault((info["race_id"], party), {})[date] = (o["office_id"], live)

    for date, code_of in ((PRI, "primary"), (RUN, "runoff")):
        want = {oid: key for key, by in party_lists.items() for d, (oid, live) in by.items() if d == date and len(live) >= 2}
        if not want:
            continue
        if not official.get(date):
            problems.append(f"the {date} results are not marked official; its primary votes are not loaded")
            continue
        rpath, res = read_results(date, folder, set(want))
        used[date] = (rpath, res)
        checked(res, problems)
        if sorted(r["id"] for r in res["races"]) != sorted(want):
            problems.append(f"the {date} results do not have every contested primary on the {date} list")
        for r in res["races"]:
            rid, party = want[r["id"]]
            info, p2 = office_of(r["title"])
            if info["race_id"] != rid or p2 != party or not r["closed"]:
                raise SystemExit(f"Louisiana: result race {r['id']} ({r['title']}) is not the {date} list's {rid} {party} primary")
            _oid, live = party_lists[(rid, party)][date]
            if sorted(fold(c["name"]) for c in live) != sorted(fold(c["name"]) for c in r["choices"]):
                raise SystemExit(f"Louisiana: the {date} results for {r['title']} do not name the Candidate Inquiry's candidates")
            by_name = {fold(c["name"]): c for c in live}
            fields += 1
            total = sum(c["votes"] for c in r["choices"])
            code = PARTY_OF[party][0]
            won = nominee.get((rid, PARTY_OF[party][1]))
            for c in r["choices"]:
                listed = by_name[fold(c["name"])]
                out, note = c["outcome"], None
                if code_of == "primary" and out == "Runoff":
                    outcome, note = "advanced", TO_RUNOFF
                elif out in ("Advances", "Elected"):
                    outcome = "advanced"
                    if won and fold(won) != fold(c["name"]):
                        upset.append(f"{rid} {party} {date}: {c['name']} won; the November list names {won}")
                        note = f"Won; the November list names {won} as the party's candidate instead."
                    elif not won:
                        note = NOT_ON_LIST
                        upset.append(f"{rid} {party} {date}: {c['name']} won, and the November list has no {PARTY_OF[party][1]}")
                    if listed["status"] not in ("", out):
                        problems.append(f"{rid} {party} {date}: the Candidate Inquiry says {listed['status']!r} for {c['name']}")
                elif out == "Defeated":
                    outcome = "lost"
                else:
                    raise SystemExit(f"Louisiana: an outcome in the {date} results that is not read ({out!r})")
                inc, mid, n2 = identify(races[rid], listed["name"], listed["party"])
                primary.append([rid, f"{code_of}-{code}", ISO[date], listed["name"], listed["party"], party_code(listed["party"]), None, inc, 0,
                                c["votes"], round(100 * c["votes"] / total, 1) if total else None, outcome, mid, SRC_RES(date),
                                " ".join(x for x in (note, n2) if x) or None])
    # each party's path to November: its only candidate, or its primary's (and runoff's) winner, must be its nominee
    for (rid, party), by in sorted(party_lists.items()):
        pname = PARTY_OF[party][1]
        _oid, first = by.get(PRI, (None, []))
        won = nominee.get((rid, pname))
        if len(first) == 1 and (not won or fold(won) != fold(first[0]["name"])):
            upset.append(f"{rid} {party}: its only candidate on May 16 was {first[0]['name']}; the November list names {won or 'nobody'}")
        if not first and won:
            upset.append(f"{rid} {party}: nobody in the May 16 primary, yet the November list names {won}")
        code = PARTY_OF[party][0]
        sent = [x for x in primary if x[0] == rid and x[1] == f"primary-{code}" and x[14] and TO_RUNOFF in x[14]]
        rwon = [x for x in primary if x[0] == rid and x[1] == f"runoff-{code}" and x[11] == "advanced"]
        if sent and RUN in used and (len(sent) != 2 or len(rwon) != 1 or rwon[0][3] not in {x[3] for x in sent}):
            problems.append(f"{rid} {party}: the primary sent {len(sent)} to a runoff, and the runoff has {len(rwon)} winner(s)")
        _oid, second = by.get(RUN, (None, []))
        if sent and sorted(fold(x[3]) for x in sent) != sorted(fold(c["name"]) for c in second):
            problems.append(f"{rid} {party}: the two sent to the runoff are not the June 27 list's candidates")
    for rid, party in [(k[0], k[1]) for k in nominee]:
        if races[rid]["_closed"] and not any(k == (rid, "Democratic Party" if party == "Democrat" else "Republican Party") for k in party_lists):
            upset.append(f"{rid}: the November list names a {party} nominee, and the spring lists have no {party} primary for it")
    cands += primary

    # ---- the November 3 results, once they are official
    if official.get(NOV):
        want = {r["_office_id"]: rid for rid, r in races.items() if not r["_alone"]}
        rpath, res = read_results(NOV, folder, set(want))
        used[NOV] = (rpath, res)
        checked(res, problems)
        for rid in sorted(set(want.values()) - {want[r["id"]] for r in res["races"]}):
            problems.append(f"{rid}: not in the November 3 results")
        for r in res["races"]:
            rid = want[r["id"]]
            mine = [x for x in cands if x[0] == rid and x[1] == "general"]
            if sorted(fold(x[3]) for x in mine) != sorted(fold(c["name"]) for c in r["choices"]):
                raise SystemExit(f"Louisiana: the November 3 results for {r['title']} do not name the Candidate Inquiry's candidates")
            total = sum(c["votes"] for c in r["choices"])
            for c in r["choices"]:
                x = [x for x in mine if fold(x[3]) == fold(c["name"])][0]
                outcome = {"Elected": "elected", "Runoff": "advanced", "Defeated": "lost"}.get(c["outcome"])
                if outcome is None:
                    raise SystemExit(f"Louisiana: an outcome in the November 3 results that is not read ({c['outcome']!r})")
                x[9], x[10], x[11], x[13] = c["votes"], round(100 * c["votes"] / total, 1) if total else None, outcome, SRC_RES(NOV)
                if outcome == "advanced":
                    x[14] = " ".join(y for y in (TO_DECEMBER, x[14]) if y)
                    report.append(f"{rid}: goes on to December 12; that election is not stored yet")

    # ---- checks: counts, names twice, notes the page would drop
    for rid, (listed, live) in counted.items():
        stored = sum(1 for c in cands if c[0] == rid and c[1] == "general")
        if stored != live:
            report.append(f"{rid}: {live} candidates on the November 3 list, {stored} stored")
    seen = set()
    for c in cands:
        k = (c[0], c[1], c[3])
        if k in seen:
            raise SystemExit(f"Louisiana: {c[3]} is listed twice in {c[0]} {c[1]}")
        seen.add(k)
    for r in races.values():
        if page_would_drop(r["note"]):
            report.append(f"{r['race_id']}: its note would be dropped by the page's contact-detail check")
    for c in cands:
        if page_would_drop(c[14]) or page_would_drop(c[3]):
            report.append(f"{c[0]} {c[1]}: a candidate's name or note would be dropped by the page's contact-detail check")

    # ---- what else is on the lists, counted only
    dec = inquiry["elections"][DEC]
    later = [(o["office"], len(o["candidates"])) for o in dec["lists"]]

    # ---- the parish and local part: every other office on the November 3 lists of the 64 parishes
    local_folder = os.path.join(folder, LOCAL_FOLDER)
    os.makedirs(local_folder, exist_ok=True)
    loc = local_part(local_folder, nov["id"], say)
    clash = sorted(set(races) & {r[0] for r in loc["races"]})
    if clash:
        raise SystemExit(f"Louisiana: a local race id is also a state race id ({clash[:3]})")

    # ---- write: Louisiana's rows only, in one transaction
    cols = ["race_id", "state", "level", "office_kind", "office", "jurisdiction", "jurisdiction_id", "county_ids", "district", "seat",
            "special", "partisan", "holder_id", "holder_name", "holder_party", "election_date", "note"]
    race_rows = [tuple(r[c] for c in cols) for r in races.values()]
    n_list = {d: sum(len(o["candidates"]) for o in e["lists"]) for d, e in inquiry["elections"].items()}
    others = nov["others"]
    src = [
        (SRC_LIST, STATE, "official candidate list", "Louisiana Secretary of State",
         "Candidate Inquiry: the state offices of the November 3, 2026 election, their May 16 and June 27 party primaries, and the "
         "December 12 special primary", LA.INQUIRY, "", inquiry["read"],
         hashlib.sha256("".join(e.get("list_sha256", "") + e["office_list_sha256"] for e in inquiry["elections"].values()).encode()).hexdigest(),
         sum(n_list.values()),
         "Read from the portal's own office and candidate lists (CandidateInquiry/StatewideCandidate), election ids "
         + ", ".join(f"{d} = {e['id']}" for d, e in inquiry["elections"].items())
         + ": the office title, the first line of the name and party columns, and the status cell only; addresses, telephones, "
           "e-mail, race and gender are never read, filing dates are not kept, and the answers are not saved. November 3 state "
           f"offices: {len(nov['offices'])} ({n_list[NOV]} candidates); also on its office list, and read elsewhere (the federal offices by the federal loader, the local offices and "
           "district courts by this loader's parish and local part): "
         + ", ".join(f"{n} {k}" for k, n in sorted(others.items()))
         + f". May 16 state party primaries read: {sum(1 for k, b in party_lists.items() if PRI in b)}; June 27 runoffs: "
           f"{sum(1 for k, b in party_lists.items() if RUN in b)}. Withdrawn, disqualified or deceased, left off: {len(gone)}. The list "
           "gives no ballot position; its order, alphabetical by surname as Louisiana's ballot is, is kept for November 3. A candidate "
           "marked Unopposed is declared elected and is not on the ballot. Louisiana has no write-ins. The sha256 here is of the "
           "answers' own hashes joined."
         + (" December 12, not loaded (not on the November 3 ballot): " + "; ".join(f"{t} ({n} candidates listed so far)" for t, n in later)
            + "." if later else "")),
        (SRC_PAGES, STATE, "official notice", "Louisiana Secretary of State",
         "Election Dates and Types of Elections pages", DATES_URL, "", pages["read"],
         hashlib.sha256("".join(p["sha256"] for p in pages["pages"].values()).encode()).hexdigest(), len(PHRASES),
         "Kept only these sentences, each page's SHA-256 recorded (the pages carry a hotline number, which is never kept): "
         + " | ".join(f"{url}: " + " / ".join(v for v in p["phrases"].values() if v) for url, p in pages["pages"].items())),
        (SRC_PROC, STATE, "official notice", "Louisiana House of Representatives",
         "Proclamation of the Speaker of the House: special primary and special general election, State Representative, District 92",
         PROC_URL, HD92["dated"], mtime(ppath), sha(ppath), 1,
         f"A scanned page, read by eye: Representative {HD92['resigned']} resigned effective June 30, 2026; the special primary is on "
         "Tuesday, November 3, 2026 and the special general on Saturday, December 12, 2026; qualifying August 5 to 7, 2026. "
         + ("The file is the one read." if sha(ppath) == PROC_SHA else "The file has changed since it was read.")),
        (SRC_ROSTER, STATE, "roster", "Open States people project (CC0), as loaded into state_la.sqlite",
         "Sitting Louisiana legislators", "https://github.com/openstates/people", "", mtime(roster_db), sha(roster_db), len(legs),
         "Who holds each legislative seat today (chamber and district), and which candidates serve in the Legislature now; the roster "
         "carries no judges, Public Service Commissioners or BESE members."),
    ]
    for date, (rpath, res) in used.items():
        src.append((SRC_RES(date), STATE, "official results", "Louisiana Secretary of State",
                    f"Official election results, {date}: " + ("state closed party primaries" if date == PRI else
                                                              "state closed party primary runoffs" if date == RUN else "state races"),
                    LA.RESULTS, (res.get("written") or "")[:10], mtime(rpath), sha(rpath), sum(len(r["choices"]) for r in res["races"]),
                    f"From the results site's data ({LA.DATA}{ISO[date].replace('-', '')}/RacesCandidates_Multiparish.htm and "
                    "Votes_Multiparish.htm), marked official in its ElectionDates.htm; races "
                    + ", ".join(f"{r['title']} ({len(r['parishes'])} parishes)" for r in res["races"])
                    + ". Totals stored, checked against each race's parish file (csv/ByParish_<race>.csv) and every precinct reported. "
                      "No write-ins in Louisiana, so shares are of the candidates' votes. The date given is when the site wrote the races "
                      "file. " + ("Every race's parish rows add up to its totals." if not [p for p in problems if date in p]
                                  else "Did not add up: " + "; ".join(p for p in problems if date in p) + ".")))
    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA + EXTRA_SCHEMA)
    with con:
        con.execute("DELETE FROM sl_candidates WHERE race_id IN (SELECT race_id FROM sl_races WHERE state = ?)", (STATE,))
        con.execute("DELETE FROM sl_candidates WHERE race_id LIKE ?", (f"2026-{STATE}-%",))
        con.execute("DELETE FROM sl_races WHERE state = ?", (STATE,))
        con.execute("DELETE FROM sl_sources WHERE state = ?", (STATE,))
        con.execute("DELETE FROM sl_places WHERE source_id LIKE ?", (f"{STATE.lower()}-%",))
        con.execute("DELETE FROM sl_gaps WHERE state = ?", (STATE,))
        con.execute("DELETE FROM sl_notes WHERE state = ?", (STATE,))
        con.executemany(f"INSERT INTO sl_races VALUES ({','.join('?' * len(cols))})", race_rows + [tuple(r) for r in loc["races"]])
        con.executemany("INSERT INTO sl_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [tuple(c) for c in cands + loc["cands"]])
        con.executemany("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", src + loc["sources"])
        con.executemany("INSERT INTO sl_places VALUES (?,?,?,?,?)", loc["places"])
        con.executemany("INSERT INTO sl_gaps VALUES (?,?,?,?,?,?,?)", loc["gaps"])
        con.executemany("INSERT INTO sl_notes VALUES (?,?,?,?,?)", loc["notes"])
    con.close()

    gen = [c for c in cands if c[1] == "general"]
    kinds = {}
    for r in races.values():
        kinds[r["office_kind"]] = kinds.get(r["office_kind"], 0) + 1
    say(f"    Louisiana: {len(races)} state races on the November 3 list ("
        + ", ".join(f"{n} {k}" for k, n in sorted(kinds.items())) + f"); {len(gen)} candidates "
        f"({sum(1 for c in gen if c[11] == 'unopposed')} unopposed, not voted; {len(gone)} withdrawn left off); "
        f"{fields} party primaries and runoffs with a field, {len(primary)} primary rows, votes from the official results")
    for c in cands:
        if c[12]:
            say(f"      matched: {c[0]} {c[1]}: {c[3]} -> {c[12]}{' (holds this seat)' if c[7] else ''}")
    for t, n in later:
        say(f"      not loaded: {t} on December 12 ({n} candidates listed so far); not on the November 3 ballot")
    if order_breaks:
        report.append("the November 3 list is not alphabetical by surname in " + ", ".join(order_breaks) + "; its order is kept")
    for line in problems + upset + report:
        say(f"      check: {line}")

    st, lv, fc, ct = loc["stats"], loc["by_level"], loc["fcount"], loc["count"]
    say(f"    Louisiana parish and local offices: {loc['local']:,} races ("
        + ", ".join(f"{k.replace('_', ' ')} {lv[k]:,}" for k in LOCAL_LEVELS if lv.get(k)) + f"), {loc['local_cands']:,} candidates, in "
        f"{loc['reached']} of {LA.PARISHES} parishes; under courts, {loc['court']:,} district, parish, family, juvenile and city court, "
        f"district attorney and city marshal contests with {loc['court_cands']:,} candidates")
    say(f"      on the November 3 ballot: {st.get('ballot', 0):,} contests, {st.get('ballot_candidates', 0):,} candidates; filled without a "
        f"vote: {st.get('unopposed', 0):,} contests, {st.get('unopposed_candidates', 0):,} unopposed candidates ({st.get('short', 0)} with "
        f"fewer candidates than seats); no candidate left: {st.get('none', 0)} ({st.get('none_left', 0)} after everyone withdrew or was "
        f"removed); left off as withdrawn, disqualified or deceased: {st.get('gone', 0)}; marked special from the Secretary's schedule: "
        f"{st.get('special_by_schedule', 0)}")
    say(f"      the parish lists' {ct['rows']:,} rows: {ct.get('federal_rows', 0):,} federal, {ct.get('state_rows', 0):,} state, "
        f"{ct.get('local_rows', 0):,} local; {st.get('placed_rows', 0):,} placed ({st.get('unique_candidacies', 0):,} candidacies, each in "
        f"exactly one race; {st.get('several_parishes', 0)} contests are on more than one parish's list), {st.get('left_rows', 0)} left out")
    say(f"      statewide tab: {loc['tab_same']} of {loc['tab_all']} district and multi-parish offices agree with the parish lists; results "
        f"site: {fc.get('local', 0):,} local contests set up for November 3, {fc.get('same', 0):,} with the list's candidates "
        f"({fc.get('same_choices', 0):,}); {fc.get('propositions', 0)} amendments and propositions not loaded")
    say("      office kinds: " + ", ".join(f"{k} {v:,}" for k, v in sorted(loc["by_kind"].items())))
    say("      places: " + ", ".join(f"{k} {v:,}" for k, v in sorted(loc["places_by_kind"].items()))
        + (f"; office kinds the pages do not know yet: {', '.join(loc['new_kinds'])}" if loc["new_kinds"] else ""))
    for g in loc["gaps"]:
        say(f"      gap ({g[1]}): {g[3]}: {g[4]}")
    for line in loc["checks"]:
        say(f"      check: {line}")
    for line in loc["problems"]:
        say(f"      CHECK {line}")
    return len(gen) + len(loc["cands"])


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m ballot.state_local_la <database>")
    load(sys.argv[1])
