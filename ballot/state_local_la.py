"""
ballot/state_local_la.py - Louisiana's state races on the November 3, 2026 ballot, from the Secretary of State's own
Candidate Inquiry and official results, into ballot_local_2026.sqlite (Louisiana's rows only).

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
counted and reported, not loaded. District judges, district attorneys and city offices on the November 3 list are local
and are counted only.

Every judicial candidate's party is printed on the list and on the ballot, so the court races are partisan here.

Sources, all the state's own, read with the federal loader's parts (ballot/lists/la.py):
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
from urllib.error import HTTPError, URLError

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

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
           f"offices: {len(nov['offices'])} ({n_list[NOV]} candidates); also on its office list and not loaded here: "
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
    con.executescript(SCHEMA)
    with con:
        con.execute("DELETE FROM sl_candidates WHERE race_id IN (SELECT race_id FROM sl_races WHERE state = ?)", (STATE,))
        con.execute("DELETE FROM sl_candidates WHERE race_id LIKE ?", (f"2026-{STATE}-%",))
        con.execute("DELETE FROM sl_races WHERE state = ?", (STATE,))
        con.execute("DELETE FROM sl_sources WHERE state = ?", (STATE,))
        con.execute("DELETE FROM sl_places WHERE source_id LIKE ?", (f"{STATE.lower()}-%",))
        con.executemany(f"INSERT INTO sl_races VALUES ({','.join('?' * len(cols))})", race_rows)
        con.executemany("INSERT INTO sl_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [tuple(c) for c in cands])
        con.executemany("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", src)
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
    return len(gen)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m ballot.state_local_la <database>")
    load(sys.argv[1])
