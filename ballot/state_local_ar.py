"""
ballot/state_local_ar.py - Arkansas's state races on the November 3, 2026 ballot: the Arkansas Senate seats up this year
(17 regular seats, plus a special election for District 1), all 100 Arkansas House seats, and the seven statewide
offices (Governor, Lieutenant Governor, Attorney General, Secretary of State, State Treasurer, Auditor of State and
Commissioner of State Lands), with the party primaries and runoffs that chose the nominees; and, as far as official
lists have been read, its county and local races (see "The local part" below: the courts' November runoffs statewide,
and the county, city and district contests of Pulaski and Washington counties). Written into ballot_local_2026.sqlite
(never ballot_2026.sqlite); only Arkansas's own rows are deleted and written again.

    python ballot/state_local_ar.py <database file>

Sources, all official, most of them the ones the federal loader (ballot/lists/ar.py) already reads:

  - The Secretary of State's "2026 Candidate Search" (candidates.arkansas.gov), read from the page's own data address
    in pages of 100, as the federal loader reads it. Each row has five cells: a filer number, the name as filed for the
    ballot, the office, the party and the filing date. Only the name, office and party are kept; the filer number and
    the filing date are dropped on the spot, and the detail cards the filer number opens (addresses, telephones) are
    never fetched. What was read is kept as a small JSON extract of the state offices' rows (office, name, party) with
    counts of the federal and local rows left to others.
  - The Secretary of State's official results (arkansas.tally-enr.com, whose data service is
    enr-results-api.totalresults.com, client "arkansas"): the March 3 preferential primary, the March 31 primary
    runoff, the June 2 special primary for House District 44 (and its June 30 runoff) and the August 18 special primary
    for Senate District 1. Each election's link is read from the Secretary's Election Results page. Only contest names,
    candidate names, parties, votes and the winner flags are read; each is kept as a JSON extract.
  - The Governor's proclamations calling special elections (governor.arkansas.gov): Senate District 1 (July 2, 2026:
    the special election on November 3, its primary on August 18) and Senate District 18 (September 18, 2026: the
    special primary on November 3, the special election on January 5, 2027). Only the facts named below are checked
    in them; the page is not kept.
  - Today's holders from the Open States roster in state_ar.sqlite (legislators by chamber and district; the officials
    table for six of the seven statewide offices). Contact columns are never selected.
  - County names from the Census Bureau's 2024 county file, as the other state loaders add them.

What the record does not say, the loader does not say:
  - The Candidate Search prints no ballot order (county boards print the ballots), so no ballot order is stored. The
    results site's own order is not a ballot order either, so primary rows have none.
  - The list names no write-in candidates for state offices, so none are stored. It holds only candidates still in
    the running: the primary's losers are not on it (checked against the results).
  - Arkansas lets a candidate file a title as part of the ballot name ("State Representative ...", "Justice ..."); the
    name is stored exactly as filed and such rows carry a note. Titles are set aside only for matching.
  - Arkansas prints only contested primaries, so every primary contest is a field. Votes are stored only when the
    results site marks the election official. A nominee needs a majority; without one the top two go to the runoff.
  - A candidate is marked as the sitting member only when the name fits the roster's holder of that same seat (or
    office) and no other name in the race fits. The roster does not carry the Commissioner of State Lands.
  - House District 8: the list names two Republicans and a Democrat, and says nothing more; all three are stored as
    listed, with a note, and the loader says CHECK.
  - Senate District 18's special primary is on the November 3 ballot, but its candidates are not on the list yet; the
    loader stores nothing for it and says so, and stops short of storing any District 18 rows that appear later (they
    would be primary candidates, not November ones).
  - U.S. Senate and U.S. Congress rows are the federal loader's.

The local part (county, city and township offices, school and district boards, and the courts' November runoffs)
--------------------------------------------------------------------------------------------------------------------
Arkansas has no statewide list of candidates for county, city and township offices: they file with the county clerk
(city candidates by petition), and each county's board of election commissioners publishes its own list. So the local
rows are read source by source, and every county not read yet gets a row in sl_gaps saying so.

  - The Candidate Search's rows for circuit judge and prosecuting attorney. These are nonpartisan offices elected on
    March 3; the rows left on the list are the November 3 runoffs. They are stored as level "court" (circuit_court,
    prosecuting_attorney), nonpartisan. The list does not say which counties a judicial district covers, so the
    counties are those that returned votes for the same contest in the Secretary's official March 3 results, which
    are also used to check that each contest had no majority and that the two names on the list are its top two.
    The list prints no ballot order (each county draws its own), so none is stored.
  - Pulaski County: the election commission's "Ballot Position Draw" for the November 3 general election (a text PDF
    of five columns: Name of Office, Ballot Name, Party, # Drawn, Ballot Position; no contact columns, so the file is
    kept whole in ballot_cache/ar/local/). It lists only contests with two or more candidates. The county, constable
    and city contests are stored with the ballot position the draw gave; its federal and state rows are counted and
    left to the other loaders. The draw lists every city candidate as "Independent". A city with no party's nominee
    in any contest has a nonpartisan city election, where no party is printed beside a name (see the manual below),
    so those contests are stored as nonpartisan, each with a note of what the draw says; a city with a party's
    nominee in any contest would be stored on party lines, Independent included.
  - Washington County: the election commission's "November 3, 2026 Election Information" page. Its candidate tables
    carry e-mail, address, city of residence and ZIP columns. The page is read in memory, table by table: a table's
    heading row must be exactly one of the layouts in WASH_LAYOUTS, and then only the cells of the allowed columns
    (office, district, the municipality or school district, candidate name, party, ballot order) are ever collected;
    every other cell's text is skipped as the page is parsed, and only that cut-down copy is kept, as JSON. The ballot
    order column holds a number, or a mark that the candidate is unopposed ("Unopposed", "Sheriff-Elect"). Its city
    table has no party column, so those contests are stored as the list gives them, without parties.
  - City names and codes from the Census Bureau's 2020 place codes file (kept whole: names and codes only).
  - The Secretary of State's 2026 election calendar, read once to confirm what is voted on which day (the dates and
    statutes quoted in the notes), and the State Board of Election Commissioners' 2026 procedures manual for county
    election commissioners, read once for what the ballot prints: an unopposed candidate's name is left off the
    general election ballot except for mayor, governor, circuit clerk and state offices, and beside each name stands
    the party or "INDEPENDENT" except in a nonpartisan election or a nonpartisan municipal election. Of each file
    only whether its sentences were found, and its SHA-256, are kept.

  What is never read: e-mail, addresses, cities of residence, ZIP codes, telephones, websites, filing dates and
  numbers. A kept cell that looks like contact details typed into the wrong column is blanked and counted. When a
  layout no longer fits, the loader names the file, the place in it and the check, never the text; that county is
  then left out with a gap, and everything else is still loaded.
  Not loaded: ballot questions and measures, and anything about a candidate beyond name, office, place, party and
  ballot order. (Arkansas ballots have had no write-in line since 2024, the manual says.)
"""

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
import unicodedata
import zipfile
from collections import Counter, defaultdict
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ballot import pdftext                                                  # noqa: E402
from ballot.check_local import EXTRA_SCHEMA, contact_like                   # noqa: E402
from ballot.common import CACHE, HERE, fold, name_parts, party_code          # noqa: E402
from ballot.lists import ar as fed                                          # noqa: E402
from ballot.match import fits                                               # noqa: E402
from states import net                                                     # noqa: E402

STATE, FIPS, NAME = "AR", "05", "Arkansas"
GENERAL = "2026-11-03"
ROSTER_DB = os.path.join(HERE, "state_ar.sqlite")
COUNTY_ZIP = os.path.join(HERE, "states_cache", "census", "cb_2024_us_county_500k.zip")

SCHEMA = """
CREATE TABLE IF NOT EXISTS sl_races (race_id TEXT PRIMARY KEY, state TEXT NOT NULL, level TEXT NOT NULL, office_kind TEXT NOT NULL, office TEXT NOT NULL, jurisdiction TEXT, jurisdiction_id TEXT, county_ids TEXT, district TEXT, seat TEXT, special INTEGER NOT NULL DEFAULT 0, partisan INTEGER NOT NULL, holder_id TEXT, holder_name TEXT, holder_party TEXT, election_date TEXT NOT NULL, note TEXT);
CREATE TABLE IF NOT EXISTS sl_candidates (race_id TEXT NOT NULL, election TEXT NOT NULL, election_date TEXT, name TEXT NOT NULL, party TEXT, party_code TEXT, ballot_order INTEGER, incumbent INTEGER NOT NULL DEFAULT 0, write_in INTEGER NOT NULL DEFAULT 0, votes INTEGER, pct REAL, outcome TEXT, state_member_id TEXT, source_id TEXT, note TEXT, PRIMARY KEY (race_id, election, name));
CREATE TABLE IF NOT EXISTS sl_sources (source_id TEXT PRIMARY KEY, state TEXT, kind TEXT, agency TEXT, title TEXT, url TEXT, published TEXT, fetched TEXT, sha256 TEXT, rows INTEGER, note TEXT);
CREATE TABLE IF NOT EXISTS sl_places (kind TEXT NOT NULL, id TEXT NOT NULL, name TEXT NOT NULL, county_ids TEXT, source_id TEXT, PRIMARY KEY (kind, id));
"""

SRC_LIST = "ar-sos-2026-sl-candidate-search"
SRC_ROSTER = "ar-openstates-roster"
SRC_COUNTIES = "ar-census-cb-2024-county"
SRC_PROC_SD1 = "ar-gov-2026-sd1-special-proclamation"
SRC_PROC_SD18 = "ar-gov-2026-sd18-special-proclamation"
AGENCY = "Arkansas Secretary of State, Elections Division"

# the statewide offices as the Candidate Search names them: (key, office_kind, office, officials.office in state_ar.sqlite)
STATEWIDE = {
    "Governor": ("GOV", "governor", "Governor", "governor"),
    "Lieutenant Governor": ("LTG", "lieutenant_governor", "Lieutenant Governor", "lt_governor"),
    "Attorney General": ("AG", "attorney_general", "Attorney General", "attorney general"),
    "Secretary of State": ("SOS", "secretary_of_state", "Secretary of State", "secretary of state"),
    "State Treasurer": ("TREAS", "state_treasurer", "State Treasurer", "treasurer"),
    "Auditor of State": ("AUD", "state_auditor", "Auditor of State", "auditor"),
    "Commissioner of State Lands": ("LAND", "land_commissioner", "Commissioner of State Lands", None),
}
# the same offices as the results site abbreviates them
RESULT_OFFICE = [
    (re.compile(r"Governor", re.I), "Governor"),
    (re.compile(r"Lieutenant Governor|Lt\.? Governor", re.I), "Lieutenant Governor"),
    (re.compile(r"Attorney General", re.I), "Attorney General"),
    (re.compile(r"Secretary of State", re.I), "Secretary of State"),
    (re.compile(r"(?:State )?Treasurer(?: of State)?", re.I), "State Treasurer"),
    (re.compile(r"Auditor(?: of State)?|State Auditor", re.I), "Auditor of State"),
    (re.compile(r"Comm(?:issioner|\.) of State Lands|Land Commissioner", re.I), "Commissioner of State Lands"),
]
COURT = re.compile(r"Sup\.? Ct\.|Supreme Court|Ct\.? of Appeals|Court of Appeals", re.I)
LOCAL = re.compile(r"^(?:Circuit Judge|Prosecuting Attorney|District Judge|County |Justice of the Peace|Municipal|City |Mayor)", re.I)

# the Secretary's results elections this loader reads: kind -> the Election Results page's label, the id last seen there,
# the name and date on the results site, and what it is
ELECTIONS = {
    "primary": dict(label="2026 Preferential Primary Election", eid="7f77a178-af02-40ec-92db-c5cc50882c68",
                    name="2026 Preferential Primary", date="2026-03-03", stage="primary", src="ar-sos-2026-sl-primary-results",
                    title="Election Results: 2026 Preferential Primary, March 3, 2026 (state offices)"),
    "runoff": dict(label="2026 Primary Runoff Election", eid="b412bdef-f97a-45bc-b3ec-6761d28caf9e",
                   name="2026 Primary Runoff", date="2026-03-31", stage="runoff", src="ar-sos-2026-sl-runoff-results",
                   title="Election Results: 2026 Primary Runoff, March 31, 2026 (state offices)"),
    "hd44": dict(label="2026 Special Primary Election for House District 44", eid="4dfe2063-3126-4eb4-ae59-1468c9d6c9cd",
                 name="Special Primary House 44", date="2026-06-02", stage="primary", src="ar-sos-2026-sl-hd44-special-primary",
                 title="Election Results: Special Primary, State Representative District 44, June 2, 2026", plurality_vin="HD44VIN"),
    "hd44r": dict(label="2026 Special Primary Runoff Election for House District 44", eid="fefa84d5-388a-4de9-9ade-acd50e0a8b1d",
                  name="Special Primary Runoff House 44", date="2026-06-30", stage="runoff", src="ar-sos-2026-sl-hd44-special-runoff",
                  title="Election Results: Special Primary Runoff, State Representative District 44, June 30, 2026"),
    "sd1": dict(label="2026 Primary Special Election Senate District 1", eid="4b025e66-db9f-4e01-a7b8-3d06d87bccda",
                name="2026 Primary Special Election", date="2026-08-18", stage="primary", src="ar-sos-2026-sl-sd1-special-primary",
                title="Election Results: Special Primary, State Senate District 1, August 18, 2026"),
}
# which races each special election's party contests may name (anything else there stops the loader)
SPECIAL_SCOPE = {"hd44": {"2026-AR-SH44"}, "hd44r": {"2026-AR-SH44"}, "sd1": {"2026-AR-SS1"}}
PREFIX = {"REP": "Republican", "DEM": "Democratic", "LIB": "Libertarian", "GRN": "Green", "GRE": "Green", "CON": "Constitution"}
CODE = {v: k for k, v in PREFIX.items() if k != "GRE"}

# the Governor's proclamations: the facts checked in each, and what the loader does with them
PROCLAMATIONS = {
    "SD1": dict(src=SRC_PROC_SD1, date="2026-07-02",
                url="https://governor.arkansas.gov/news_post/sanders-calls-for-special-election-to-fill-vacancy-in-office-for-state-senator-for-district-1/",
                title="Proclamation calling a special election to fill a vacancy in office for State Senator for District 1",
                facts=("VACANCY IN OFFICE FOR STATE SENATOR FOR DISTRICT 1", "November 3, 2026", "August 18, 2026")),
    "SD18": dict(src=SRC_PROC_SD18, date="2026-09-18",
                 url="https://governor.arkansas.gov/news_post/sanders-calls-for-special-election-to-fill-vacancy-in-office-for-state-senator-for-district-18/",
                 title="Proclamation calling a special election to fill a vacancy in office for State Senator for District 18",
                 facts=("vacancy in office for State Senator for District 18", "January 5, 2027", "November 3, 2026")),
    "HD44VIN": dict(src="ar-gov-2026-hd44-vin-proclamation", date="2026-04-07",
                    url="https://governor.arkansas.gov/news_post/sanders-announces-vacancy-in-nomination-for-state-representative-for-district-44/",
                    title="Proclamation calling a special primary election to fill a vacancy in nomination for State Representative for District 44",
                    facts=("VACANCY IN NOMINATION FOR STATE REPRESENTATIVE FOR DISTRICT 44", "June 2, 2026"), absent=("runoff",)),
}
SPECIAL_RACES = {"2026-AR-SS1"}                   # special elections on the November 3 ballot (for the rest of a term)
SPECIAL_PRIMARY_ONLY = {("Senate", "18")}         # a special primary on November 3 whose election is later: no November race

TITLE = re.compile(r"^(?:U\.S\. Representative|U\.S\. Senator|State Representative|State Senator|Rep\.|Sen\.|Representative|Senator|"
                   r"Congressman|Congresswoman|Lieutenant Governor|Governor|Attorney General|Secretary of State|Auditor of State|"
                   r"State Treasurer|Treasurer|Commissioner of State Lands|Land Commissioner|Mayor|Sheriff|County Judge|Judge|"
                   r"Justice of the Peace|Justice|Council Member|Councilman|Councilwoman|Alderman|Alderwoman|School Board Director|"
                   r"School Board Member|Prosecuting Attorney|Dr\.)\s+(?=\S+\s+\S)")
TITLE_NOTE = ("Arkansas lets a candidate file a title as part of the name printed on the ballot; the name is shown as the "
              "Secretary of State's list gives it.")
RUNOFF_NOTE = "No candidate had a majority; the top two went to the runoff."
VIN_NOTE = "A special primary to fill a vacancy in the party's nomination for this seat."
PLURALITY_NOTE = ("No candidate had a majority; the Governor's proclamation called this special primary with no runoff, and "
                  "the most votes won.")
SD1_PRIMARY_NOTE = "The special primary for the special election, called by the Governor's proclamation of July 2, 2026."


# ---------- names ----------

def untitled(name):
    """The name without a title filed before it, for matching only: 'State Representative Jane Doe' -> 'Jane Doe'."""
    return TITLE.sub("", (name or "").strip())


def same_person(a, b):
    """Two printings of one candidate's name (the list's and the results site's)."""
    ua, ub = untitled(a), untitled(b)
    if fold(ua) == fold(ub) or fold(ua).replace(" ", "") == fold(ub).replace(" ", ""):
        return True
    return fits(name_parts(ua), name_parts(ub))


def holder_fits(name, h):
    """The name fits the roster's holder: the same letters once spaces and stops are set aside ("RJ Hawk", "R.J. Hawk"),
    or the same family name with a given name that fits."""
    bare = fold(untitled(name)).replace(" ", "")
    if bare and bare in {fold(h["full"] or "").replace(" ", ""), fold(f"{h['first']} {h['last']}").replace(" ", "")}:
        return True
    cand = name_parts(untitled(name))
    regs = ((fold(h["first"]).split(), fold(h["last"])), name_parts(h["full"] or ""))
    return any(fits(cand, reg) for reg in regs if reg[1])


# ---------- offices ----------

def statewide_race(label):
    key, kind, office, _roster = STATEWIDE[label]
    return dict(race_id=f"2026-{STATE}-{key}", level="statewide", office_kind=kind, office=office, district=None, chamber=None,
                label=label)


def leg_race(chamber, district):
    d = str(int(district))
    if chamber == "Senate":
        return dict(race_id=f"2026-{STATE}-SS{d}", level="legislature", office_kind="state_senate", office="State Senator",
                    district=d, chamber="Senate", label=None)
    return dict(race_id=f"2026-{STATE}-SH{d}", level="legislature", office_kind="state_house", office="State Representative",
                district=d, chamber="House", label=None)


def list_office(descript):
    """What a Candidate Search office is: ("state", race) | ("federal", None) | ("local", what). Anything the loader does
    not know stops it, naming the office (never a person)."""
    t = re.sub(r"\s+", " ", descript or "").strip()
    if t in STATEWIDE:
        return "state", statewide_race(t)
    m = re.fullmatch(r"State (Senate|Representative) District (\d{1,3})", t)
    if m:
        return "state", leg_race("Senate" if m.group(1) == "Senate" else "House", m.group(2))
    if fed.race_of(t):
        return "federal", None
    if LOCAL.match(t):
        return "local", re.sub(r"[,\s]+(?:District|Division|Dist\.).*$", "", t)
    if COURT.search(t):
        raise SystemExit(f"Arkansas (state races): an appellate court race is on the November list ({t!r}); the loader does not store courts yet")
    raise SystemExit(f"Arkansas (state races): an office on the Candidate Search the loader does not know: {t!r}")


def result_office(text):
    """A results contest's office (party prefix and VIN/VIO already removed) -> race dict, "court", or None (local)."""
    t = re.sub(r"\s+", " ", text).strip()
    m = re.fullmatch(r"State Senat(?:e|or),? (?:District|Dist\.?) ?(\d{1,3})", t, re.I)
    if m:
        return leg_race("Senate", m.group(1))
    m = re.fullmatch(r"State Representative,? (?:District|Dist\.?) ?(\d{1,3})", t, re.I)
    if m:
        return leg_race("House", m.group(1))
    if COURT.search(t):
        return "court"
    for rx, label in RESULT_OFFICE:
        if rx.fullmatch(t):
            return statewide_race(label)
    return None


def parse_contest(name):
    """'REP State Representative Dist. 44 VIN' -> ("REP", "VIN", race); a contest that is not a state office -> None."""
    t = re.sub(r"\s+", " ", name or "").strip()
    prefix = None
    m = re.match(r"(REP|DEM|LIB|GRN|GRE|CON) (.+)$", t)
    if m:
        prefix, t = m.group(1), m.group(2)
    else:
        m = re.fullmatch(r"(.+?) - (REP|DEM|LIB|GRN|GRE|CON)", t)
        if m:
            t, prefix = m.group(1), m.group(2)
    vac = None
    m = re.search(r"\b(VIN|VIO)\b", t)
    if m:
        vac = m.group(1)
        t = re.sub(r"\s*\b(?:VIN|VIO)\b\s*", " ", t).strip()
    office = result_office(t)
    return None if office is None else (prefix, vac, office)


# ---------- fetching (retries at most twice more, then stops) ----------

def patient(fn, what, tries=3, wait=6.0):
    last = None
    for i in range(tries):
        try:
            return fn()
        except HTTPError as e:
            last = e
            if e.code not in (403, 408, 429, 500, 502, 503, 504):
                raise
        except (URLError, OSError) as e:
            last = e
        if i + 1 < tries:
            time.sleep(wait)
    raise RuntimeError(f"{what}: {type(last).__name__} {getattr(last, 'code', '') or ''}".strip())


def enr(path):
    return patient(lambda: json.loads(net.get(fed.ENR_API + path, accept="application/json").decode("utf-8-sig")), "the results site")


def fresh(path, days):
    return os.path.exists(path) and time.time() - os.path.getmtime(path) < days * 86400


# ---------- the Candidate Search ----------

_SEARCH = {}


def search_bytes(start):
    """One page of the Candidate Search exactly as fetched: the request the page itself sends, as
    ballot/lists/ar.py's search_page sends it."""
    q = {"draw": 1, "start": start, "length": 100, "search[value]": "", "search[regex]": "false",
         "order[0][column]": 1, "order[0][dir]": "asc", "postID": fed.POST_ID}
    for i, c in enumerate(fed.COLUMNS):
        q.update({f"columns[{i}][data]": c, f"columns[{i}][name]": "", f"columns[{i}][searchable]": "true",
                  f"columns[{i}][orderable]": "true", f"columns[{i}][search][value]": "", f"columns[{i}][search][regex]": "false"})
    return net.get(fed.SEARCH_API + "?" + urlencode(q), accept="application/json")


def search_pages():
    """The whole Candidate Search, asked for once in a run, in pages of 100: ([each page's rows], the list's own
    count, how many rows came, the SHA-256 of the pages as fetched). A row is cut down to the office, the ballot name
    and the party as it arrives; the filer number and the filing date are dropped on the spot."""
    if "pages" not in _SEARCH:
        pages, start, total, sha = [], 0, None, hashlib.sha256()
        while total is None or start < total:
            raw = patient(lambda: search_bytes(start), "the Candidate Search")
            page = json.loads(raw.decode("utf-8-sig"))
            total = int(page["recordsFiltered"])
            data = page.get("data") or []
            if not data:
                break
            sha.update(raw)
            pages.append([{"office": re.sub(r"\s+", " ", str(r.get("Descript") or "")).strip(),
                           "name": re.sub(r"\s+", " ", str(r.get("CanBallotName") or "")).strip(),
                           "party": re.sub(r"\s+", " ", str(r.get("PartyAffiliation") or "")).strip()} for r in data])
            start += len(data)
            time.sleep(1.5)
        _SEARCH.update(pages=pages, total=total, got=start, sha=sha.hexdigest())
    return _SEARCH["pages"], _SEARCH["total"], _SEARCH["got"], _SEARCH["sha"]


def candidate_list(folder, say, max_age_days=2):
    """{rows: [{office, name, party}] for state offices, others: {kind: count}, records, read, sha256_rows}: from the saved
    extract when fresh, else read afresh (only the name, office and party cells are ever kept)."""
    path = os.path.join(folder, "sl_ar_2026_candidate_search_state.json")
    if fresh(path, max_age_days):
        return json.load(open(path, encoding="utf-8")), path
    try:
        rows, others = [], Counter()
        pages, total, start, _sha = search_pages()
        for data in pages:
            for r in data:
                what, _race = list_office(r["office"])
                if what != "state":
                    others[what] += 1
                    continue
                rows.append({"office": r["office"], "name": r["name"], "party": r["party"]})
    except RuntimeError as e:
        if os.path.exists(path):
            say(f"    Arkansas (state races): could not read the Candidate Search afresh ({e}); using the extract read earlier")
            return json.load(open(path, encoding="utf-8")), path
        raise SystemExit(f"Arkansas (state races): the Candidate Search could not be read ({e}); a browser would show it at {fed.SEARCH_PAGE}")
    if start < (total or 0):
        raise SystemExit(f"Arkansas (state races): the Candidate Search gave {start} of {total} rows")
    raw = json.dumps(rows, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ex = {"url": fed.SEARCH_PAGE, "data": fed.SEARCH_API, "post_id": fed.POST_ID, "records": total, "read": dt.date.today().isoformat(),
          "sha256_rows": hashlib.sha256(raw).hexdigest(), "others": dict(others), "rows": rows}
    os.makedirs(folder, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(ex, fh, ensure_ascii=False, indent=0)
    return ex, path


# ---------- the results ----------

def election_ids(say):
    """{kind: id} from the links on the Secretary's Election Results page (the ids last seen there otherwise)."""
    ids = {k: v["eid"] for k, v in ELECTIONS.items()}
    try:
        page = patient(lambda: net.get(fed.RESULTS_PAGE, accept="text/html"), "the Election Results page").decode("utf-8", "replace")
    except RuntimeError as e:
        say(f"    Arkansas (state races): the Election Results page could not be read ({e}); using the election ids last seen there")
        return ids
    for m in re.finditer(r'<a[^>]+href="([^"]*tally-enr\.com/#election=([0-9a-f-]+))"[^>]*>(.*?)</a>', page, re.S | re.I):
        label = re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", "", m.group(3)))).strip()
        for kind, spec in ELECTIONS.items():
            if label == spec["label"]:
                ids[kind] = m.group(2)
    return ids


def results(folder, kind, eid, say, max_age_days=30):
    """One election's state-office contests (names, parties, votes, winner flags) as a JSON extract, read afresh after
    max_age_days; the extract on disk is used if the site cannot be reached."""
    spec = ELECTIONS[kind]
    path = os.path.join(folder, f"sl_ar_2026_{kind}_results_state.json")
    if fresh(path, max_age_days):
        return json.load(open(path, encoding="utf-8")), path
    try:
        listed = [e for e in enr(f"Election/GetElectionList?cid={fed.CLIENT}") if e.get("electionID") == eid]
        if len(listed) != 1 or listed[0].get("electionName") != spec["name"] or not str(listed[0].get("electionDate", "")).startswith(spec["date"]):
            raise SystemExit(f"Arkansas (state races): the results site does not list {eid} as the {spec['name']} of {spec['date']}")
        time.sleep(1.0)
        search = enr(f"Contest/GetContestSearchList?cid={fed.CLIENT}&electionID={eid}")
        official, updated, version = bool(search.get("isOfficial")), search.get("lastUpdated"), search.get("versionID")
        keep, types, skipped = {}, set(), Counter()
        for cid, c in search["response"]["contests"].items():
            parsed = parse_contest(c.get("contestName", ""))
            ctype = c.get("contestTypeCode")
            if parsed is None:
                if ctype in ("Statewide", "State Senate", "State Representative"):
                    raise SystemExit(f"Arkansas (state races): a {ctype} contest in the {spec['name']} the loader cannot read: {c.get('contestName')!r}")
                continue
            if parsed[2] == "court":
                skipped["appellate court"] += 1
                continue
            keep[cid] = c
            types.add(ctype)
        contests = []
        if keep:
            time.sleep(1.0)
            info = enr(f"Election/GetElectionInfo?cId={fed.CLIENT}&electionID={eid}")
            parties = {k: v["partyName"] for k, v in info["response"]["parties"].items()}
            official = official and bool(info.get("isOfficial"))
            got = {}
            for ctype in sorted(types):
                time.sleep(1.0)
                res = enr(f"Contest/GetContestResults?cId={fed.CLIENT}&electionID={eid}&contestType={quote(ctype)}")
                official = official and bool(res.get("isOfficial"))
                updated, version = res.get("lastUpdated") or updated, res.get("versionID") or version
                got.update({k: v for k, v in res["response"]["contests"].items() if k in keep})
            if set(got) != set(keep):
                raise SystemExit(f"Arkansas (state races): the {spec['name']} results and contest list name different state contests")
            for cid, c in sorted(keep.items(), key=lambda kv: kv[1].get("contestOrder", 0)):
                r = got[cid]
                choices = []
                for ch in (r.get("choices") or []) + (r.get("writeInChoices") or []):
                    who = c["choices"][ch["choiceID"]]
                    county = sum(next((x["totalVotes"] for x in loc.get("choices") or [] if x["choiceID"] == ch["choiceID"]), 0)
                                 for loc in (r.get("locations") or {}).values())
                    choices.append({"name": who["name"], "party": parties.get(ch.get("partyID") or who.get("partyID"), ""),
                                    "write_in": bool(who.get("isWriteIn")), "votes": int(ch["totalVotes"]), "county_sum": county,
                                    "winner": bool(ch.get("isWinner"))})
                contests.append({"name": c["contestName"], "type": c.get("contestTypeCode"), "vote_for": c.get("voteFor"),
                                 "total": int(r["totalVotes"]), "precincts": [r.get("precinctsReporting"), r.get("totalPrecincts")],
                                 "counties": len(r.get("locations") or {}), "choices": choices})
    except RuntimeError as e:
        if os.path.exists(path):
            say(f"    Arkansas (state races): could not read the {spec['name']} results afresh ({e}); using the extract read earlier")
            return json.load(open(path, encoding="utf-8")), path
        raise SystemExit(f"Arkansas (state races): the {spec['name']} results could not be read ({e}); a browser would show them at "
                         f"{fed.ENR_SITE}#election={eid}")
    ex = {"election": spec["name"], "date": spec["date"], "election_id": eid, "link": f"{fed.ENR_SITE}#election={eid}",
          "official": official, "last_updated": updated, "version": version, "read": dt.date.today().isoformat(),
          "skipped": dict(skipped), "contests": contests}
    os.makedirs(folder, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(ex, fh, ensure_ascii=False, indent=0)
    return ex, path


# ---------- the Governor's proclamations ----------

def proclamations(folder, say, max_age_days=30):
    """{key: {checked, sha256, fetched}}: each proclamation fetched and the facts the loader relies on looked for in its
    text (nothing from it is kept but whether they were found, and the page's SHA-256)."""
    path = os.path.join(folder, "sl_ar_2026_proclamations.json")
    if fresh(path, max_age_days):
        return json.load(open(path, encoding="utf-8"))
    out = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}
    for key, p in PROCLAMATIONS.items():
        try:
            raw = patient(lambda: net.get(p["url"], accept="text/html"), "the Governor's site")
        except RuntimeError as e:
            say(f"    Arkansas (state races): the {key} proclamation could not be read ({e}); "
                + ("using the check made earlier" if key in out else "its facts are not checked"))
            out.setdefault(key, {"checked": False, "sha256": "", "fetched": ""})
            continue
        text = re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"<script.*?</script>|<style.*?</style>", "", raw.decode("utf-8", "replace"), flags=re.S))))
        found = [f for f in p["facts"] if f.lower() in text.lower()]
        present = [f for f in p.get("absent", ()) if f.lower() in text.lower()]
        out[key] = {"checked": len(found) == len(p["facts"]) and not present,
                    "missing": [f for f in p["facts"] if f not in found] + [f"'{f}' is in the text" for f in present],
                    "sha256": hashlib.sha256(raw).hexdigest(), "fetched": dt.date.today().isoformat()}
        del raw, text
        time.sleep(1.5)
    os.makedirs(folder, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=0)
    return out


# ---------- the roster and the counties ----------

def roster(path=ROSTER_DB):
    """Today's holders: {("Senate"|"House", district): row}, {officials.office: row}, and the roster's date. Contact
    columns are never selected."""
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    seats = {}
    for r in con.execute("SELECT bioguide_id, first_name, last_name, official_full, party_name, chamber, district "
                         "FROM legislators WHERE is_current = 1"):
        key = (r[5], str(r[6]))
        if key in seats:
            raise SystemExit(f"Arkansas (state races): the roster lists two sitting members for {key}")
        seats[key] = {"id": r[0], "first": r[1], "last": r[2], "full": r[3], "party": r[4]}
    offs = {}
    for r in con.execute("SELECT bioguide_id, first_name, last_name, official_full, party_name, office FROM officials"):
        offs[r[5]] = {"id": r[0], "first": r[1], "last": r[2], "full": r[3], "party": r[4]}
    as_of = (con.execute("SELECT max(updated_at) FROM legislators").fetchone()[0] or "")[:10]
    con.close()
    return seats, offs, as_of


def counties(path=COUNTY_ZIP):
    """[(GEOID, "Arkansas County")] for Arkansas's 75 counties, from the Census Bureau's file."""
    import shapefile                                   # pyshp
    z = zipfile.ZipFile(path)
    base = next(n[:-4] for n in z.namelist() if n.endswith(".dbf"))
    rdr = shapefile.Reader(dbf=io.BytesIO(z.read(base + ".dbf")))
    fields = [f[0] for f in rdr.fields[1:]]
    out = []
    for rec in rdr.iterRecords():
        rec = dict(zip(fields, rec))
        if str(rec.get("STATEFP")) == FIPS:
            out.append((str(rec["GEOID"]), str(rec["NAMELSAD"])))
    if len(out) != 75:
        raise SystemExit(f"Arkansas (state races): the county file gives {len(out)} Arkansas counties, not 75")
    return sorted(out)


def sha_of(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest() if os.path.exists(path) else ""


def mdate(path):
    return dt.date.fromtimestamp(os.path.getmtime(path)).isoformat() if os.path.exists(path) else ""


# ---------- the fields ----------

def fields_from(data, kind, races, nominees, problems, skipped):
    """[(race, election, date, name, party, votes, pct, outcome, write_in, note)] for one election's party contests with a
    field, plus {race_id: [the runoff pairs this primary sent on]} for the runoff check."""
    spec = ELECTIONS[kind]
    out, sent = [], defaultdict(list)
    for c in data["contests"]:
        parsed = parse_contest(c["name"])
        if parsed is None or parsed[2] == "court":
            raise SystemExit(f"Arkansas (state races): a saved contest can no longer be read: {c['name']!r}")
        prefix, vac, race = parsed
        rid = race["race_id"]
        if vac == "VIO":                               # a special election for the rest of a term, decided before November
            skipped["special election for a vacancy in office (decided before November)"] += 1
            continue
        if prefix is None:                             # a nonpartisan special general held on the same day
            if rid in races:
                raise SystemExit(f"Arkansas (state races): {c['name']!r} in the {spec['name']} has no party but names a November race")
            skipped["special general election decided before November"] += 1
            continue
        if kind in SPECIAL_SCOPE and rid not in SPECIAL_SCOPE[kind]:
            raise SystemExit(f"Arkansas (state races): the {spec['name']} holds a contest the loader does not expect: {c['name']!r}")
        if kind not in SPECIAL_SCOPE and rid in SPECIAL_RACES:
            raise SystemExit(f"Arkansas (state races): the regular {spec['name']} holds a contest for the special race {rid}")
        if vac == "VIN" and kind not in SPECIAL_SCOPE:
            raise SystemExit(f"Arkansas (state races): a vacancy-in-nomination contest in the regular {spec['name']}: {c['name']!r}")
        if rid not in races:
            problems.append(f"{c['name']} ({spec['name']}): not a race on the November list")
            continue
        named = [ch for ch in c["choices"] if not ch["write_in"]]
        parties = {ch["party"] for ch in named}
        party = PREFIX.get(prefix)
        if parties != {party}:
            raise SystemExit(f"Arkansas (state races): {c['name']} ({spec['name']}) lists candidates of {sorted(parties)}")
        total = sum(ch["votes"] for ch in c["choices"])
        if total != c["total"]:
            problems.append(f"{c['name']} ({spec['name']}): candidates add up to {total:,}, the contest total is {c['total']:,}")
        if c["precincts"][0] != c["precincts"][1]:
            problems.append(f"{c['name']} ({spec['name']}): {c['precincts'][0]} of {c['precincts'][1]} precincts reporting")
        for ch in c["choices"]:
            if ch["county_sum"] != ch["votes"]:
                problems.append(f"{c['name']} ({spec['name']}): a candidate's counties add up to {ch['county_sum']:,}, the total is {ch['votes']:,}")
        if len(named) < 2:
            continue
        stage = spec["stage"]
        noms = nominees.get((rid, party), [])
        ranked = sorted(named, key=lambda ch: -ch["votes"])
        runoff = plurality = False
        if not data["official"]:
            won = [ch for ch in named if any(same_person(ch["name"], n) for n in noms)]
        elif vac == "VIN" and spec.get("plurality_vin"):     # the proclamation called a special primary only, no runoff
            won, plurality = ranked[:1], 2 * ranked[0]["votes"] <= total
        elif stage == "primary" and 2 * ranked[0]["votes"] <= total:
            won, runoff = ranked[:2], True
            sent[(rid, party)].append([ch["name"] for ch in won])
        else:
            if len(ranked) > 1 and ranked[0]["votes"] == ranked[1]["votes"]:
                problems.append(f"{c['name']} ({spec['name']}): a tie for first place")
            won = ranked[:1]
        flagged = [ch for ch in named if ch.get("winner")]
        if flagged and data["official"] and {id(x) for x in flagged} != {id(x) for x in won}:
            problems.append(f"{c['name']} ({spec['name']}): the site's winner flags differ from the vote count")
        if not runoff and noms and not any(same_person(w["name"], n) for w in won for n in noms):
            problems.append(f"{c['name']} ({spec['name']}): the winner is not the party's candidate on the November list")
        if not runoff and not noms:
            problems.append(f"{c['name']} ({spec['name']}): the party has no candidate for this seat on the November list")
        code = CODE.get(party, prefix)
        for ch in named:
            advanced = any(ch is w for w in won)
            note = RUNOFF_NOTE if (advanced and runoff) else None
            if vac == "VIN":
                note = VIN_NOTE + (" " + PLURALITY_NOTE if plurality else "")
            elif kind == "sd1":
                note = SD1_PRIMARY_NOTE if not note else note + " " + SD1_PRIMARY_NOTE
            out.append((rid, f"{stage}-{code}", spec["date"], ch["name"], party,
                        ch["votes"] if data["official"] else None,
                        round(100 * ch["votes"] / total, 1) if data["official"] and total else None,
                        ("advanced" if advanced else "lost") if (data["official"] or won) else None, 0, note))
        for ch in [x for x in c["choices"] if x["write_in"] and fold(x["name"]) not in ("", "write in", "write ins")]:
            out.append((rid, f"{stage}-{code}", spec["date"], ch["name"], party, ch["votes"] if data["official"] else None,
                        round(100 * ch["votes"] / total, 1) if data["official"] and total else None, "lost", 1, None))
    return out, sent


# ---------- the local part: the courts' November runoffs, and the counties whose own lists are read ----------

LOCAL_DIR = os.path.join(CACHE, "ar", "local")
NONPARTISAN, NP_CODE = "Nonpartisan office", "N"
PULASKI, WASHINGTON, BENTON = "05119", "05143", "05007"
SRC_COURT = "ar-sos-2026-sl-candidate-search-runoffs"
SRC_MARCH = "ar-sos-2026-sl-nonpartisan-general-results"
SRC_PULASKI = "ar-pulaski-2026-ballot-draw"
SRC_WASH = "ar-washington-2026-candidate-list"
SRC_PLACES = "ar-census-2020-place"
SRC_CALENDAR = "ar-sos-2026-election-calendar"
SRC_MANUAL = "ar-sbec-2026-cbec-manual"
PULASKI_URL = "https://votepulaskiar.gov/wp-content/uploads/11032026_Ballot-Draw-Results.pdf"
WASH_URL = ("https://www.washingtoncountyar.gov/government/departments-a-e/election-commission/"
            "november-3-2026-general-election-information")
BENTON_URL = "https://bentoncountyar.gov/election-commission/"
BENTON_SAVED = ("benton_2026_general_candidates.pdf", "benton_2026_general_candidates.html")
PLACE_URL = "https://www2.census.gov/geo/docs/reference/codes2020/place/st05_ar_place2020.txt"
PLACE_HEAD = ["STATE", "STATEFP", "PLACEFP", "PLACENS", "PLACENAME", "TYPE", "CLASSFP", "FUNCSTAT", "COUNTIES"]
CALENDAR_URL = "https://www.sos.arkansas.gov/uploads/elections/2026_Election_Calendar_Rev._6-2025_.pdf"
# the calendar's summary of dates, in the order it prints them (only letters and digits are compared)
CALENDAR_ORDER = ("MARCH 3, 2026", "Preferential Primary Election", "Nonpartisan General Election", "Annual School Election",
                  "NOVEMBER 3, 2026", "General Election", "Nonpartisan Runoff Election", "Annual School Runoff Election",
                  "DECEMBER 1, 2026", "General Runoff Election (County and Municipal)")
# The State Board of Election Commissioners' manual for county election commissioners: what the ballot prints. These
# sentences are what the notes on unopposed candidates and on city offices rest on.
MANUAL_URL = "https://sbec.arkansas.gov/wp-content/uploads/2026-CBEC-Manual.pdf"
MANUAL_FACTS = (
    "Filing - Mayor Council Form Nonpartisan Municipal Offices",
    "the names of unopposed candidates for the office of mayor, governor, circuit clerk and non-judicial state elected officials "
    "are placed on the general election ballot separately",
    "All unopposed candidates other than for the offices of mayor, governor, circuit clerk and non-judicial state elected officials "
    "can be declared and certified elected without being placed on the general election ballot",
    "the phrase unopposed candidates shall appear on the ballot in a place where a voter may cast a vote for all unopposed candidates",
    "Except for a nonpartisan election or nonpartisan municipal election, beside each candidate's name shall be his or her party "
    "designation or the term INDEPENDENT")

DRAW_HEAD = ("Name of Office", "Ballot Name", "Party", "# Drawn", "Ballot Position")
DRAW_PARTIES = {"Democratic", "Republican", "Libertarian", "Independent", "Green", "Constitution"}
# Washington County's tables, each known by its whole heading row; only the columns named here are ever read. In the
# city table the heading "City" comes twice: the first is the municipality, the second the candidate's city of
# residence, which is never read.
WASH_LAYOUTS = {
    "county": (["offices up for election", "district", "candidate name", "party", "filing date", "filing number", "ballot order",
                "email", "address", "city", "zip"], {0: "office", 1: "district", 2: "name", 3: "party", 6: "order"}),
    "municipal": (["city", "office", "candidate name", "filing date", "time", "ballot order", "email", "address", "city", "zip"],
                  {0: "place", 1: "office", 2: "name", 5: "order"}),
    "judicial": (["offices up for election", "candidate name", "filing date", "filing order", "ballot order", "email", "address",
                  "city", "zip"], {0: "office", 1: "name", 4: "order"}),
    "school": (["school district", "school board office", "candidate name", "filing date", "ballot order", "email", "address",
                "city", "zip"], {0: "place", 1: "office", 2: "name", 4: "order"}),
    "contents": (["type of election", "content"], {0: "kind", 1: "content"}),
}
COUNTY_OFFICES = {"county judge": ("county_judge", "County Judge"), "county sheriff": ("sheriff", "Sheriff"), "sheriff": ("sheriff", "Sheriff"),
                  "county assessor": ("county_assessor", "County Assessor"), "assessor": ("county_assessor", "County Assessor"),
                  "circuit clerk": ("clerk_of_court", "Circuit Clerk"), "county clerk": ("county_clerk", "County Clerk"),
                  "county collector": ("tax_collector", "County Collector"), "collector": ("tax_collector", "County Collector"),
                  "county treasurer": ("county_treasurer", "County Treasurer"), "treasurer": ("county_treasurer", "County Treasurer"),
                  "county coroner": ("coroner", "Coroner"), "coroner": ("coroner", "Coroner"),
                  "county surveyor": ("county_surveyor", "County Surveyor"), "surveyor": ("county_surveyor", "County Surveyor")}
CITY_OFFICES = {"mayor": ("mayor", "Mayor"), "city mayor": ("mayor", "Mayor"), "city clerk": ("city_clerk", "City Clerk"),
                "city treasurer": ("city_treasurer", "City Treasurer"), "city clerk/treasurer": ("city_clerk_treasurer", "City Clerk/Treasurer"),
                "city attorney": ("city_attorney", "City Attorney")}
COUNCIL_RX = re.compile(r"(?:City )?Council{1,2} ?Member,? Ward 0*(\d{1,2}),? Pos(?:ition|\.)? ?0*(\d{1,2})", re.I)
DIRECTOR_RX = re.compile(r"City Director,? Ward 0*(\d{1,2})", re.I)
SPECIAL_RX = re.compile(r"^Special Election Vacancy: ", re.I)
VOTED_ANYWAY = {"mayor", "clerk_of_court"}        # an unopposed candidate for mayor or circuit clerk is still voted on
COURT_RX = re.compile(r"^(Circuit Judge|Prosecuting Attorney),? (?:District|Dist\.?) ?0*(\d{1,2})(?:\s?-\s?(North|South|East|West|N|S|E|W)\b)?(.*)$", re.I)
DIVISION_RX = re.compile(r"^,? ?(?:Division|Div\.?) ?0*(\d{1,2})\b(.*)$", re.I)
ELECT = re.compile(r"^Unopposed$|-Elect$", re.I)
LOCAL_TITLE = re.compile(r"^(?:State Representative|State Senator|Representative|Senator|Rep\.|Sen\.|Mayor|Vice Mayor|Sheriff|County Judge|Judge|"
                         r"Justice of the Peace|Council Member|Councilmember|Councilman|Councilwoman|Alderman|Alderwoman|City Director|Director|"
                         r"City Attorney|City Clerk|County Clerk|Circuit Clerk|Assessor|Collector|Treasurer|Coroner|Constable|"
                         r"School Board Director|School Board Member|Prosecuting Attorney|Dr\.)\s+(?=\S+\s+\S)")
LOCAL_TITLE_NOTE = ("Arkansas lets a candidate file a title as part of the name printed on the ballot; the name is shown as the "
                    "official list gives it.")
COURT_RUNOFF = ("A runoff. No candidate had a majority at the nonpartisan general election on March 3, 2026, so the two with the "
                "most votes are on the November 3 ballot (A.C.A. 7-10-102).")
COURT_RUNOFF_PLAIN = "A runoff from the nonpartisan general election of March 3, 2026 (A.C.A. 7-10-102)."
SCHOOL_RUNOFF = "A runoff from the annual school election of March 3, 2026, held with the November 3 general election (A.C.A. 6-14-121)."
UNOPPOSED_NOTE = ("One candidate, marked unopposed on the county's list. Arkansas certifies an unopposed candidate for a local "
                  "office as elected without printing the name on the general election ballot, which has one line for all "
                  "unopposed candidates; mayor and circuit clerk are the exceptions (A.C.A. 7-5-207).")
UNOPPOSED_VOTED = ("One candidate, marked unopposed on the county's list. An unopposed candidate for mayor or circuit clerk is "
                   "still printed on the general election ballot in Arkansas, and the votes are counted (A.C.A. 7-5-207).")
SPECIAL_NOTE = "A special election to fill a vacancy, as the county's list titles it."
NO_PARTY_NOTE = "Washington County's list gives no party for this office."
ALL_INDEPENDENT_NOTE = "Pulaski County's draw lists every candidate for this office as Independent."
NOT_READ = ("The county's list carries this contest, but in a form this loader has not been checked against, so it is not "
            "shown yet.")
COUNTY_NOT_LOADED = ("Arkansas keeps no statewide list of candidates for county, city and township offices or for school board "
                     "runoffs: each county's clerk and election commission publish their own, and this county's list has not been "
                     "read yet.")


class Layout(Exception):
    """A file or page that no longer fits the layout this loader was checked against. The words name the file, the
    place in it and the check, never the text found there."""


def slug(text):
    """Lower-case letters and digits with hyphens between, accents folded: for ids only."""
    t = "".join(c for c in unicodedata.normalize("NFKD", text or "") if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")


def kept(text, tally):
    """A cell that is kept, white space tidied, after the contact check: a cell that looks like contact details typed
    into the wrong column is blanked and counted, and never shown."""
    t = re.sub(r"\s+", " ", text or "").strip()
    if t and contact_like(t, True):
        tally["blanked"] += 1
        return ""
    return t


def and_list(items):
    items = list(items)
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


# ----- the courts' runoffs: the Candidate Search's rows, and the official March 3 results for their counties -----

def court_list(local_dir, say, max_age_days=2):
    """The Candidate Search's rows for circuit judge and prosecuting attorney: {rows: [{office, name, party}], counts,
    records, read, sha256, blanked}, from the saved extract when fresh, else read afresh. None if it cannot be read and
    there is no extract."""
    path = os.path.join(local_dir, "ar_2026_candidate_search_local.json")
    if fresh(path, max_age_days):
        return json.load(open(path, encoding="utf-8")), path
    try:
        pages, total, got, sha = search_pages()
        if got < (total or 0):
            raise RuntimeError(f"{got} of {total} rows came")
    except RuntimeError as e:
        if os.path.exists(path):
            say(f"    Arkansas (local races): could not read the Candidate Search afresh ({e}); using the extract read earlier")
            return json.load(open(path, encoding="utf-8")), path
        say(f"    CHECK Arkansas (local races): the Candidate Search could not be read ({e}); the courts' runoffs are not loaded")
        return None, path
    rows, counts, tally = [], Counter(), Counter()
    for data in pages:
        for r in data:
            what, _race = list_office(r["office"])
            counts[what] += 1
            if what == "local":
                rows.append({"office": r["office"], "name": kept(r["name"], tally), "party": kept(r["party"], tally)})
    ex = {"url": fed.SEARCH_PAGE, "records": total, "read": dt.date.today().isoformat(), "sha256": sha, "counts": dict(counts),
          "blanked": tally["blanked"], "rows": rows}
    os.makedirs(local_dir, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(ex, fh, ensure_ascii=False, indent=0)
    return ex, path


def court_office(text):
    """A circuit judge's or prosecuting attorney's office, as the Candidate Search, a county's list or the results
    site words it -> {what, district ("2", "11-West"), division ("4") or None, extra ("At Large", "Subdistrict 6.2")
    or None}; None when it cannot be read."""
    m = COURT_RX.match(re.sub(r"\s+", " ", text or "").strip())
    if not m:
        return None
    what = "circuit" if m.group(1).lower().startswith("circuit") else "prosecutor"
    side = {"n": "North", "s": "South", "e": "East", "w": "West"}.get((m.group(3) or "")[:1].lower())
    district = str(int(m.group(2))) + (f"-{side}" if side else "")
    division, rest = None, m.group(4)
    d = DIVISION_RX.match(rest)
    if d:
        division, rest = str(int(d.group(1))), d.group(2)
    rest, extra = rest.strip(" ,"), None
    if rest:
        s = re.fullmatch(r"Sub-?district (\d{1,2}\.\d)", rest, re.I)
        if re.fullmatch(r"At[ -]?Large", rest, re.I):
            extra = "At Large"
        elif s:
            extra = f"Subdistrict {s.group(1)}"
        else:
            return None
    if (what == "circuit") != (division is not None) or (what == "prosecutor" and extra):
        return None
    return {"what": what, "district": district, "division": division, "extra": extra}


def court_key(o):
    return (o["what"], o["district"].lower(), o["division"])


def court_race(o):
    """The race a court office is: its id, kind, title, district and seat as the list words them."""
    label = o["district"]
    if o["what"] == "circuit":
        rid, kind, office = f"2026-{STATE}-CC{label}-D{o['division']}", "circuit_court", "Circuit Judge"
        seat = f"Division {o['division']}" + (f", {o['extra']}" if o["extra"] else "")
    else:
        rid, kind, office, seat = f"2026-{STATE}-PA{label}", "prosecuting_attorney", "Prosecuting Attorney", None
    return {"race_id": rid, "office_kind": kind, "office": office, "jurisdiction": f"Judicial District {label}",
            "jurisdiction_id": f"{STATE}-JD{label}", "district": label if label.isdigit() else f"District {label}", "seat": seat}


def march_contests(local_dir, eid, say, max_age_days=30):
    """The March 3 contests for circuit judge and prosecuting attorney from the Secretary's results service: each
    contest's name, the counties that returned votes for it, the precincts and each candidate's votes, as a JSON
    extract (names and numbers only). None if it cannot be read and there is no extract."""
    spec = ELECTIONS["primary"]
    path = os.path.join(local_dir, "ar_2026_march3_nonpartisan_results.json")
    if fresh(path, max_age_days):
        return json.load(open(path, encoding="utf-8")), path
    try:
        listed = [e for e in enr(f"Election/GetElectionList?cid={fed.CLIENT}") if e.get("electionID") == eid]
        if len(listed) != 1 or listed[0].get("electionName") != spec["name"] or not str(listed[0].get("electionDate", "")).startswith(spec["date"]):
            raise RuntimeError(f"the results site does not list {eid} as the {spec['name']} of {spec['date']}")
        time.sleep(1.0)
        search = enr(f"Contest/GetContestSearchList?cid={fed.CLIENT}&electionID={eid}")
        official, updated, version = bool(search.get("isOfficial")), search.get("lastUpdated"), search.get("versionID")
        keep = {cid: c for cid, c in search["response"]["contests"].items() if court_office(c.get("contestName") or "")}
        got = {}
        for ctype in sorted({str(c.get("contestTypeCode")) for c in keep.values()}):
            time.sleep(1.0)
            res = enr(f"Contest/GetContestResults?cId={fed.CLIENT}&electionID={eid}&contestType={quote(ctype)}")
            official = official and bool(res.get("isOfficial"))
            updated, version = res.get("lastUpdated") or updated, res.get("versionID") or version
            got.update({k: v for k, v in res["response"]["contests"].items() if k in keep})
        contests = []
        for cid, c in sorted(keep.items(), key=lambda kv: kv[1].get("contestOrder", 0)):
            r = got.get(cid)
            if r is None:
                continue
            choices = [{"name": re.sub(r"\s+", " ", c["choices"][ch["choiceID"]]["name"] or "").strip(),
                        "write_in": bool(c["choices"][ch["choiceID"]].get("isWriteIn")), "votes": int(ch["totalVotes"])}
                       for ch in (r.get("choices") or []) + (r.get("writeInChoices") or [])]
            contests.append({"name": re.sub(r"\s+", " ", c["contestName"]).strip(), "type": c.get("contestTypeCode"),
                             "total": int(r["totalVotes"]), "precincts": [r.get("precinctsReporting"), r.get("totalPrecincts")],
                             "counties": sorted(str(k) for k in (r.get("locations") or {})), "choices": choices})
    except (RuntimeError, HTTPError, URLError, OSError, KeyError, ValueError, TypeError) as e:
        if os.path.exists(path):
            say(f"    Arkansas (local races): could not read the March 3 results afresh ({type(e).__name__}); using the extract read earlier")
            return json.load(open(path, encoding="utf-8")), path
        say(f"    CHECK Arkansas (local races): the March 3 results could not be read ({type(e).__name__}: {e}); the runoffs' counties are not known")
        return None, path
    ex = {"election": spec["name"], "date": spec["date"], "election_id": eid, "link": f"{fed.ENR_SITE}#election={eid}", "official": official,
          "last_updated": updated, "version": version, "read": dt.date.today().isoformat(), "listed": len(keep), "contests": contests}
    os.makedirs(local_dir, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(ex, fh, ensure_ascii=False, indent=0)
    return ex, path


class _Rows:
    """The local rows as they are gathered: races, candidates, places, gaps, and counts and words for the report."""

    def __init__(self, cmap):
        self.name_of = dict(cmap)
        self.races, self.cands, self.places, self.gaps, self.checks = [], [], {}, [], []
        self.ids, self.stats = set(), Counter()

    def check(self, words):
        if words not in self.checks:
            self.checks.append(words)

    def gap(self, scope, place_id, place, what, reason, url=None):
        self.gaps.append((STATE, scope, place_id, place, what, reason, url))

    def contest(self, county, rid, level, kind, office, jname, jid, district, seat, special, partisan, entries, src, notes, label, url):
        """One contest filed under a county, and its candidates: entries are (name, party words or None, ballot order
        or None). A contest that cannot be stored whole is left out, with a gap saying why. True when stored."""
        def leave_out(reason):
            self.gap("county", county, self.name_of[county], label, reason, url)
            self.check(f"{label} ({self.name_of[county]}): {reason}")
            self.stats["contests left out"] += 1
            self.stats["rows left out"] += len(entries)
            return False
        if rid in self.ids:
            return leave_out("The county's list carries this contest twice in a form that cannot be told apart, so it is not shown.")
        names = [e[0] for e in entries]
        if any(not n for n in names):
            return leave_out("A candidate line of this contest on the county's list does not read as a name, so the contest is not shown.")
        if len({n.lower() for n in names}) != len(names):
            return leave_out("The county's list prints the same name twice in this contest, so it is not shown.")
        self.ids.add(rid)
        self.races.append((rid, STATE, level, kind, office, jname, jid, json.dumps([county]), district, seat, 1 if special else 0,
                           1 if partisan else 0, None, None, None, GENERAL, " ".join(n for n in notes if n) or None))
        for name, party, order in entries:
            self.cands.append((rid, "general", GENERAL, name, party if partisan else NONPARTISAN, party_code(party) if partisan else NP_CODE,
                               order, 0, 0, None, None, None, None, src, LOCAL_TITLE_NOTE if LOCAL_TITLE.match(name) else None))
        self.stats["contests"] += 1
        self.stats["candidates"] += len(entries)
        self.stats[f"level {level}"] += 1
        self.stats[f"kind {kind}"] += 1
        self.stats[f"county {county} contests"] += 1
        self.stats[f"county {county} candidates"] += len(entries)
        self.stats["special"] += 1 if special else 0
        self.stats["partisan"] += 1 if partisan else 0
        self.stats["with ballot order"] += 1 if entries and all(e[2] is not None for e in entries) else 0
        return True


def court_rows(L, clist, march, cmap):
    """The November runoffs for circuit judge and prosecuting attorney: races (level court) with the counties of the
    March 3 results, and their candidates. Returns what the report and the source rows say about them."""
    info = {"races": 0, "candidates": 0, "verified": 0, "no_majority": None, "names": {}}
    if clist is None:
        L.gap("state", STATE, NAME, "the November runoffs for circuit judge and prosecuting attorney",
              "The Secretary of State's candidate list could not be read when this was built, so these runoffs are not shown yet.", fed.SEARCH_PAGE)
        return info
    by_key = {}
    for c in (march or {}).get("contests", []):
        o = court_office(c["name"])
        if o:
            by_key.setdefault(court_key(o), []).append(c)
    groups = {}
    for r in clist["rows"]:
        groups.setdefault(r["office"], []).append(r)
    listed = set()
    for office_text, rows in groups.items():
        o = court_office(office_text)
        if o is None:                                          # a district judge, or wording this loader does not know
            L.gap("state", STATE, NAME, office_text, "The Secretary of State's candidate list carries this office, but in a form this "
                  "loader has not been checked against, so it is not shown yet.", fed.SEARCH_PAGE)
            L.check(f"an office on the Candidate Search the local part does not read: {office_text} ({len(rows)} rows)")
            L.stats["court rows left out"] += len(rows)
            continue
        race = court_race(o)
        rid = race["race_id"]
        names = [r["name"] for r in rows]
        if rid in L.ids or any(not n for n in names) or len({n.lower() for n in names}) != len(names):
            L.gap("state", STATE, NAME, office_text, "The Secretary of State's candidate list could not be read cleanly for this "
                  "office, so it is not shown yet.", fed.SEARCH_PAGE)
            L.check(f"{rid}: the Candidate Search's rows could not be stored (a repeated contest or name, or a name that did not read)")
            L.stats["court rows left out"] += len(rows)
            continue
        listed.add(court_key(o))
        hit = by_key.get(court_key(o), [])
        cids, verified = None, False
        if len(hit) == 1:
            c = hit[0]
            cids = [g for g in c["counties"] if g in L.name_of]
            if len(cids) != len(c["counties"]):
                L.check(f"{rid}: the March 3 results name a county code the county file does not have")
            named = sorted((x for x in c["choices"] if not x["write_in"]), key=lambda x: -x["votes"])
            no_majority = bool(named) and 2 * named[0]["votes"] <= c["total"]
            top_two = len(names) == 2 and len(named) >= 2 and all(any(same_person(n, x["name"]) for x in named[:2]) for n in names)
            verified = bool(march.get("official")) and no_majority and top_two and c["precincts"][0] == c["precincts"][1]
            if not verified:
                L.check(f"{rid}: the official March 3 results do not show this contest as one with no majority whose top two are the "
                        f"two names on the November list (official: {bool(march.get('official'))}, no majority: {no_majority}, "
                        f"top two: {top_two})")
        else:
            L.check(f"{rid}: {len(hit)} contests of the March 3 results fit this office, so its counties are not known")
        where = ""
        if cids:
            short = [re.sub(r" County$", "", L.name_of[g]) for g in cids]
            where = f" Voted on in {and_list(short)} {'County' if len(short) == 1 else 'counties'}, the counties of the official March 3 results."
        note = (COURT_RUNOFF if verified else COURT_RUNOFF_PLAIN) + where + (
            " The Secretary of State's list prints no ballot order; each county draws its own.")
        L.ids.add(rid)
        L.races.append((rid, STATE, "court", race["office_kind"], race["office"], race["jurisdiction"], race["jurisdiction_id"],
                        json.dumps(cids) if cids else None, race["district"], race["seat"], 0, 0, None, None, None, GENERAL, note))
        for n in names:
            L.cands.append((rid, "general", GENERAL, n, NONPARTISAN, NP_CODE, None, 0, 0, None, None, None, None, SRC_COURT,
                            LOCAL_TITLE_NOTE if (TITLE.match(n) or LOCAL_TITLE.match(n)) else None))
        info["races"] += 1
        info["candidates"] += len(names)
        info["verified"] += 1 if verified else 0
        info["names"][court_key(o)] = (rid, names)
    if march:
        # every March 3 contest for these offices that ended without a majority should be a runoff on the list, and no other
        open_ = set()
        for key, cs in by_key.items():
            for c in cs:
                named = sorted((x["votes"] for x in c["choices"] if not x["write_in"]), reverse=True)
                if named and 2 * named[0] <= c["total"]:
                    open_.add(key)
        info["no_majority"] = len(open_)
        if open_ != listed:
            L.check(f"the March 3 results show {len(open_)} circuit judge and prosecuting attorney contests without a majority; the "
                    f"November list carries {len(listed)} ({len(open_ - listed)} not on the list, {len(listed - open_)} on the list only)")
    return info


# ----- places: the Census Bureau's 2020 place codes -----

def read_places(local_dir, cmap, say):
    """({county GEOID: {bare name in lower case: [(place code, name with its kind word, [county GEOIDs])]}}, SHA-256,
    day fetched, rows) for Arkansas's incorporated cities and towns, from the Census Bureau's 2020 place codes file.
    The file has names, codes and counties only; it is kept whole and asked for once."""
    path = os.path.join(local_dir, "st05_ar_place2020.txt")
    try:
        net.download(PLACE_URL, path, 3650, tries=3, say=say)
    except (HTTPError, URLError, OSError) as e:
        say(f"    CHECK Arkansas (local races): the Census Bureau's place codes file could not be fetched ({type(e).__name__}); "
            "cities are filed under their county's code and their name")
        return {}, "", "", 0
    by_full = {full.lower(): geoid for geoid, full in cmap}
    out, n = {}, 0
    with open(path, encoding="utf-8", errors="replace") as fh:
        if fh.readline().rstrip("\r\n").split("|") != PLACE_HEAD:
            raise SystemExit("Arkansas (local races): st05_ar_place2020.txt: the header is not the one this loader was checked against")
        for ln, line in enumerate(fh, start=2):
            if not line.strip():
                continue
            f = line.rstrip("\r\n").split("|")
            if len(f) != len(PLACE_HEAD) or f[1] != FIPS or not re.fullmatch(r"\d{5}", f[2]):
                raise SystemExit(f"Arkansas (local races): st05_ar_place2020.txt: line {ln} does not fit the header")
            n += 1
            if f[5] != "INCORPORATED PLACE":
                continue
            cids = [by_full.get(c.strip().lower()) for c in f[8].split("~~~")]
            if not all(cids):
                raise SystemExit(f"Arkansas (local races): st05_ar_place2020.txt: line {ln} names a county the county file does not have")
            bare = re.sub(r"\s+(city|town)$", "", f[4]).lower()
            for g in cids:
                out.setdefault(g, {}).setdefault(bare, []).append((f[2], f[4], sorted(cids)))
    return out, sha_of(path), mdate(path), n


def city_place(L, places, county, name, src):
    """(jurisdiction id, name, key) for a city or town a county's list names: the Census place code when the name fits
    exactly one incorporated place reaching that county, else the county's three-digit code and the name."""
    hit = places.get(county, {}).get(name.lower(), [])
    if len(hit) == 1:
        code, full, cids = hit[0]
        jid = f"{STATE}-M-{code}"
        old = L.places.get(jid)
        L.places[jid] = ("mcd", jid, full, json.dumps(sorted(set(cids) | {county} | set(json.loads(old[3]) if old else []))), SRC_PLACES)
        return jid, full, f"M-{code}"
    key = f"{county[2:]}-{slug(name)}"
    jid = f"{STATE}-M-{key}"
    L.places[jid] = ("mcd", jid, name, json.dumps([county]), src)
    L.check(f"{name} ({L.name_of[county]}): not exactly one incorporated place of that name in the Census place file; filed under "
            "the county's code and its name")
    return jid, name, f"M-{key}"


# ----- the offices of a county's list -----

def county_office(text, district, county_full):
    """A county or township office as a county's list words it -> (kind, title, district or None); None if not known.
    "Pulaski County Judge" and "County Judge" are the same office; a justice of the peace and a constable carry their
    district (a number, or a township's name) in the title or in the list's district column."""
    t = re.sub(r"\s+", " ", text or "").strip()
    d = re.sub(r"\s+", " ", district or "").strip()
    bare = re.sub(r" County$", "", county_full)
    for form in (t, t[len(bare) + 1:] if t.lower().startswith(bare.lower() + " ") else None,
                 t[len(county_full) + 1:] if t.lower().startswith(county_full.lower() + " ") else None):
        if form and form.lower() in COUNTY_OFFICES and not d:
            return COUNTY_OFFICES[form.lower()] + (None,)
    m = re.fullmatch(r"Justice of the Peace(?:,? District 0*(\d{1,2}))?", t, re.I)
    if m and (m.group(1) or d.isdigit()) and not (m.group(1) and d):
        return "justice_of_the_peace", "Justice of the Peace", str(int(m.group(1) or d))
    m = re.fullmatch(r"Constable(?:,? (?:District 0*(\d{1,2})|(.+ Township)))?", t, re.I)
    if m and not ((m.group(1) or m.group(2)) and d):
        if m.group(1) or d.isdigit():
            return "constable", "Constable", str(int(m.group(1) or d))
        if m.group(2) or re.fullmatch(r".+ Township", d, re.I):
            return "constable", "Constable", m.group(2) or d
    return None


def city_office(text):
    """A city office as a county's list words it -> (kind, title, district, seat, special); None if not known."""
    t = re.sub(r"\s+", " ", text or "").strip()
    special = bool(SPECIAL_RX.match(t))
    t = SPECIAL_RX.sub("", t)
    if t.lower() in CITY_OFFICES:
        return CITY_OFFICES[t.lower()] + (None, None, special)
    m = COUNCIL_RX.fullmatch(t)
    if m:
        return "council", "Council Member", f"Ward {int(m.group(1))}", f"Position {int(m.group(2))}", special
    m = DIRECTOR_RX.fullmatch(t)
    if m:
        return "council", "City Director", f"Ward {int(m.group(1))}", None, special
    return None


def read_orders(orders):
    """What a contest's ballot order cells say: ([a ballot order or None for each], unopposed, what is wrong or None).
    A cell is a number, or a mark that the candidate is unopposed ("Unopposed", "Sheriff-Elect")."""
    if any(ELECT.search(o) for o in orders):
        if len(orders) == 1:
            return [None], True, None
        return [None] * len(orders), False, "an unopposed mark on a contest with more than one candidate"
    nums = [int(o) if o.isdigit() else None for o in orders]
    if None in nums or sorted(nums) != list(range(1, len(nums) + 1)):
        return [None] * len(orders), False, "the ballot orders are not the numbers 1 to the number of candidates"
    return nums, False, None


def unopposed_note(kind):
    return UNOPPOSED_VOTED if kind in VOTED_ANYWAY else UNOPPOSED_NOTE


def race_label(title, district, seat):
    return ", ".join(x for x in (title, (f"District {district}" if district and district.isdigit() else district), seat) if x)


# ----- Pulaski County: the election commission's ballot position draw -----

def _columns(runs):
    """Where each of the five headings starts on a heading row: five x positions, or None if the row is not the
    heading row. Pieces of text are matched with white space set aside (the file sets its type letter by letter)."""
    chars = []
    for x0, _y, _size, text, _x1 in sorted(runs, key=lambda r: r[0]):
        chars += [(c, x0) for c in text if not c.isspace()]
    line, xs, at = "".join(c for c, _x in chars), [], 0
    for head in DRAW_HEAD:
        want = re.sub(r"\s+", "", head)
        if not line.startswith(want, at):
            return None
        xs.append(chars[at][1])
        at += len(want)
    return xs if at == len(line) else None


def read_draw(data):
    """([{office, name, party, drawn, position, page, row}], the day the draw was conducted, pages) from the PDF's
    bytes. Raises Layout when a page does not fit."""
    if data[:5] != b"%PDF-":
        raise Layout("the file is not a PDF")
    pdf = pdftext.PDF(data)
    pages = pdf.pages()
    if not pages:
        raise Layout("the PDF has no pages")
    out, conducted, of = [], None, None
    for n, (page, res) in enumerate(pages, start=1):
        xs, top = None, ""
        for k, (_y, runs) in enumerate(pdftext.rows(pdf, page, res), start=1):
            if xs is None:
                xs = _columns(runs)
                if xs is None:
                    top += re.sub(r"\s+", "", pdftext.join(runs))
                continue
            foot = re.fullmatch(r"Conductedon(\d{1,2})/(\d{1,2})/(\d{4})(?:11/3/2026BallotPositionDraw)?Page(\d+)of(\d+)",
                                re.sub(r"\s+", "", pdftext.join(runs)))
            if foot:
                conducted = f"{foot.group(3)}-{int(foot.group(1)):02d}-{int(foot.group(2)):02d}"
                if int(foot.group(4)) != n:
                    raise Layout(f"page {n}: its own page number is {foot.group(4)}")
                of = int(foot.group(5))
                continue
            cols = [[] for _ in xs]
            for r in runs:
                cols[max((i for i, x in enumerate(xs) if r[0] >= x - 6), default=0)].append(r)
            cells = [pdftext.join(c) if c else "" for c in cols]
            if not all(cells) or not cells[3].isdigit() or not cells[4].isdigit():
                raise Layout(f"page {n}, row {k}: not five cells ending in two numbers")
            out.append({"office": cells[0], "name": cells[1], "party": cells[2], "drawn": int(cells[3]), "position": int(cells[4]),
                        "page": n, "row": k})
        if xs is None:
            raise Layout(f"page {n}: the heading row ({', '.join(DRAW_HEAD)}) was not found")
        if "11/3/2026GeneralElection" not in top or "BallotPositionDraw" not in top:
            raise Layout(f"page {n}: the title is not the 11/3/2026 General Election ballot position draw")
    if of != len(pages):
        raise Layout(f"the last page says there are {of} pages; the file has {len(pages)}")
    return out, conducted, len(pages)


def draw_office(text, county, county_full, places):
    """What an office of the draw is: ("federal",), ("state",), ("county", kind, title, district),
    ("city", place name, kind, title, district, seat, special) or ("unknown",)."""
    t = re.sub(r"\s+", " ", text or "").strip()
    try:
        if fed.race_of(t):
            return ("federal",)
    except SystemExit:
        return ("unknown",)
    if t in STATEWIDE or re.fullmatch(r"State (Senate|Representative) District \d{1,3}", t):
        return ("state",)
    c = county_office(t, None, county_full)
    if c:
        return ("county",) + c
    words = t.split(" ")
    known = places.get(county, {})
    for i in range(len(words) - 1, 0, -1):                     # the longest place name first: North Little Rock before Little Rock
        city, rest = " ".join(words[:i]), " ".join(words[i:])
        o = city_office(rest)
        if o and len(known.get(city.lower(), [])) == 1:
            return ("city", city) + o
    return ("unknown",)


def pulaski_rows(L, places, local_dir, say, max_age_days=2):
    """Pulaski County's contested county, constable and city contests, from the ballot position draw."""
    county, full = PULASKI, L.name_of[PULASKI]
    path = os.path.join(local_dir, "pulaski_11032026_ballot_draw_results.pdf")
    info = {"path": path, "rows": 0, "conducted": "", "pages": 0, "ok": False, "federal": 0, "state": 0, "local": 0, "contests": 0}

    def failed(words, reason):
        say(f"    CHECK Arkansas (local races): Pulaski County's ballot position draw: {words}; the county is left out")
        L.check(f"Pulaski County's ballot position draw: {words}")
        L.gap("county", county, full, "county, city and township contests", reason, PULASKI_URL)
        return info
    try:
        net.download(PULASKI_URL, path, max_age_days, tries=3, say=say)
    except (HTTPError, URLError, OSError) as e:
        return failed(f"could not be fetched ({type(e).__name__} {getattr(e, 'code', '') or ''})".replace(" )", ")"),
                      "The county election commission's ballot position draw could not be fetched when this was built, so the "
                      "county's contests are not shown yet.")
    try:
        rows, conducted, pages = read_draw(open(path, "rb").read())
    except Layout as e:
        return failed(f"pulaski_11032026_ballot_draw_results.pdf: {e}",
                      "The county election commission's ballot position draw no longer has the layout this loader reads, so the "
                      "county's contests are not shown yet.")
    info.update(rows=len(rows), conducted=conducted or "", pages=pages)
    tally, groups, order = Counter(), {}, []
    for r in rows:
        what = draw_office(r["office"], county, full, places)
        if what[0] in ("federal", "state"):
            info[what[0]] += 1
            continue
        info["local"] += 1
        r["name"] = kept(r["name"], tally)
        if r["office"] not in groups:
            groups[r["office"]] = (what, [])
            order.append(r["office"])
        groups[r["office"]][1].append(r)
    # A city whose candidates are all listed as Independent has a nonpartisan city election: no party's nominee is in
    # any of its contests, and no party is printed beside a name there (A.C.A. 7-5-207(d), as the State Board's manual
    # states it). A city with a party's nominee in any contest is on party lines, and Independent is then a label too.
    on_lines = {}
    for what, rs in groups.values():
        if what[0] == "city":
            on_lines[what[1]] = on_lines.get(what[1], False) or any(r["party"] != "Independent" for r in rs)
    info["cities"], info["cities on party lines"] = len(on_lines), sum(1 for v in on_lines.values() if v)
    for office_text in order:
        what, rs = groups[office_text]
        if what[0] == "unknown":
            L.gap("county", county, full, office_text, NOT_READ, PULASKI_URL)
            L.check(f"Pulaski County's draw: an office this loader does not know is not loaded: {office_text} ({len(rs)} rows)")
            L.stats["contests left out"] += 1
            L.stats["rows left out"] += len(rs)
            continue
        bad = [r for r in rs if r["party"] not in DRAW_PARTIES]
        positions = sorted(r["position"] for r in rs)
        if what[0] == "county":
            _, kind, title, district = what
            level, jid, jname, seat, special, pk, partisan = "county", county, full, None, False, county, True
        else:
            _, city, kind, title, district, seat, special = what
            jid, jname, pk = city_place(L, places, county, city, SRC_PULASKI)
            level, partisan = "city", on_lines[city]
        rid = f"2026-{STATE}-{pk}-{slug(kind)}" + "".join(f"-{slug(x)}" for x in (district, seat) if x) + ("-S" if special else "")
        label = race_label(title, district, seat) + ("" if level == "county" else f", {jname}")
        if bad or positions != list(range(1, len(rs) + 1)):
            L.gap("county", county, full, label, "A line of this contest on the county's ballot position draw does not read as a "
                  "party and a ballot position, so the contest is not shown.", PULASKI_URL)
            L.check(f"Pulaski County's draw: {label}: a party or ballot position did not read ({len(rs)} rows)")
            L.stats["contests left out"] += 1
            L.stats["rows left out"] += len(rs)
            continue
        entries = [(r["name"], r["party"], r["position"]) for r in sorted(rs, key=lambda r: r["position"])]
        if L.contest(county, rid, level, kind, title, jname, jid, district, seat, special, partisan, entries, SRC_PULASKI,
                     [SPECIAL_NOTE if special else None, None if partisan else ALL_INDEPENDENT_NOTE], label, PULASKI_URL):
            info["contests"] += 1
    info["ok"] = True
    info["blanked"] = tally["blanked"]
    L.gap("county", county, full, "county, city and township offices with one candidate",
          "The county election commission's ballot position draw lists only contests with two or more candidates. Offices with one "
          "candidate are on the county's own candidate list, which is not loaded yet.", PULASKI_URL)
    return info


# ----- Washington County: the election commission's candidate tables -----

class _CutTables(HTMLParser):
    """The tables of the county's page, cut down as they are read. A table's first row names its columns; only when
    that row is exactly one of WASH_LAYOUTS are the cells of the allowed columns collected. The text of every other
    cell (e-mail, address, city of residence, ZIP, filing date, time and number) is never collected at all."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.problems, self.tally = [], [], Counter()
        self.depth, self.t, self.row, self.col, self.buf, self.open = 0, None, None, -1, None, False

    def _end_cell(self):
        if self.open and self.buf is not None:
            if self.t["n"] == 0:
                self.t["head"].append(re.sub(r"\s+", " ", self.buf).strip().lower())
            else:
                self.row[self.t["keep"][self.col]] = kept(self.buf, self.tally)
        self.buf, self.open = None, False

    def _end_row(self):
        self._end_cell()
        if self.row is None:
            return
        t = self.t
        if t["n"] == 0:
            if t["th_only"] and self.col >= 0 and len(t["head"]) == self.col + 1:
                for name, (want, cols) in WASH_LAYOUTS.items():
                    if t["head"] == want:
                        t["layout"], t["keep"] = name, cols
        elif t["layout"]:
            if self.col + 1 != len(WASH_LAYOUTS[t["layout"]][0]):
                self.problems.append(f"the {t['layout']} table, data row {t['n']}: {self.col + 1} cells where the heading row has "
                                     f"{len(WASH_LAYOUTS[t['layout']][0])}")
            t["rows"].append(self.row)
        t["n"] += 1
        self.row = None

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.depth += 1
            if self.depth == 1:
                self.t = {"layout": None, "head": [], "keep": {}, "n": 0, "rows": [], "th_only": True, "spans": False}
                self.row, self.col, self.buf, self.open = None, -1, None, False
        elif self.depth != 1 or self.t is None:
            return
        elif tag == "tr":
            self._end_row()                                        # a row whose end tag was left out
            self.row, self.col = {}, -1
        elif tag in ("td", "th") and self.row is not None:
            self._end_cell()
            self.col += 1
            a = dict(attrs)
            if (a.get("colspan") or "1") != "1" or (a.get("rowspan") or "1") != "1":
                self.t["spans"] = True
            self.open = True
            if self.t["n"] == 0:
                if tag != "th":
                    self.t["th_only"] = False
                self.buf = "" if tag == "th" else None             # headings only: a first row of plain cells is never read
            else:
                self.buf = "" if self.col in self.t["keep"] else None      # every other column's text is never collected
        elif tag in ("br", "p", "div", "li") and self.buf is not None:
            self.buf += " "

    def handle_data(self, data):
        if self.buf is not None and self.depth == 1:
            self.buf += data

    def handle_endtag(self, tag):
        if tag == "table":
            if self.depth == 1 and self.t is not None:
                self._end_row()
                if self.t["layout"]:
                    if self.t["spans"]:
                        self.problems.append(f"the {self.t['layout']} table has cells that span rows or columns")
                    self.out.append({"layout": self.t["layout"], "rows": self.t["rows"], "data_rows": self.t["n"] - 1})
                self.t = None
            self.depth = max(0, self.depth - 1)
        elif self.depth != 1 or self.t is None:
            return
        elif tag in ("td", "th"):
            self._end_cell()
        elif tag == "tr":
            self._end_row()


def washington_list(local_dir, say, max_age_days=2):
    """Washington County's candidate tables, cut down to the allowed columns: {tables: [{layout, rows, data_rows}],
    sha256 and size of the page as fetched, read, title, blanked}, from the saved extract when fresh, else read afresh.
    The page itself is never kept. (None, why) if it cannot be read and there is no extract."""
    path = os.path.join(local_dir, "washington_2026_general_candidates.json")
    if fresh(path, max_age_days):
        return json.load(open(path, encoding="utf-8")), None
    why = None
    try:
        raw = patient(lambda: net.get(WASH_URL, accept="text/html"), "Washington County's page")
        page = raw.decode("utf-8", "replace")
        title = re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", "", (re.search(r"<title[^>]*>(.*?)</title>", page, re.S | re.I) or [None, ""])[1]))).strip()
        p = _CutTables()
        p.feed(page)
        p.close()
        del page
        layouts = [t["layout"] for t in p.out]
        if "November 3, 2026" not in title:
            why = "the page's title is no longer the November 3, 2026 election's"
        elif p.problems:
            why = p.problems[0]
        elif "county" not in layouts or "municipal" not in layouts:
            why = "the county table or the city table was not found under the headings this loader knows"
    except (RuntimeError, HTTPError, URLError, OSError) as e:
        why = f"could not be fetched ({type(e).__name__} {getattr(e, 'code', '') or ''})".replace(" )", ")")
    if why:
        if os.path.exists(path):
            say(f"    Arkansas (local races): Washington County's page {why}; using the extract read earlier")
            return json.load(open(path, encoding="utf-8")), None
        return None, why
    ex = {"url": WASH_URL, "read": dt.date.today().isoformat(), "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw),
          "rows_sha256": hashlib.sha256(json.dumps(p.out, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest(),
          "title": "" if contact_like(title, False) else title, "blanked": p.tally["blanked"], "tables": p.out}
    os.makedirs(local_dir, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(ex, fh, ensure_ascii=False, indent=0)
    return ex, None


def washington_rows(L, places, court, local_dir, say):
    """Washington County's county, city, district and school runoff contests, from the election commission's page."""
    county, full = WASHINGTON, L.name_of[WASHINGTON]
    info = {"ok": False, "rows": 0, "federal": 0, "state": 0, "county": 0, "municipal": 0, "judicial": 0, "school": 0, "blank": 0,
            "sections": 0, "unopposed": 0, "questions": 0, "contests": 0, "sha256": "", "read": "", "blanked": 0, "court_match": None}
    ex, why = washington_list(local_dir, say)
    if ex is None:
        say(f"    CHECK Arkansas (local races): Washington County's page: {why}; the county is left out")
        L.check(f"Washington County's page: {why}")
        L.gap("county", county, full, "county, city and township contests",
              "The county election commission's candidate page could not be read in the layout this loader knows when this was "
              "built, so the county's contests are not shown yet.", WASH_URL)
        return info
    info.update(sha256=ex["sha256"], read=ex["read"], blanked=ex.get("blanked", 0), bytes=ex.get("bytes", 0),
                rows_sha256=ex.get("rows_sha256") or hashlib.sha256(json.dumps(ex["tables"], ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest())

    def left_out(label, n, words, reason=NOT_READ):
        L.gap("county", county, full, label, reason, WASH_URL)
        L.check(f"Washington County's list: {label}: {words} ({n} rows)")
        L.stats["contests left out"] += 1
        L.stats["rows left out"] += n

    def store(rid, level, kind, title, jname, jid, district, seat, special, partisan, rs, notes, label):
        orders, unopposed, wrong = read_orders([r["order"] for r in rs])
        if wrong:
            L.check(f"Washington County's list: {label}: {wrong}; no ballot order stored")
        if partisan and any(r["party"] not in DRAW_PARTIES for r in rs):
            return left_out(label, len(rs), "a party did not read", "A line of this contest on the county's list does not read as a "
                            "party, so the contest is not shown.")
        entries = sorted(((r["name"], r.get("party"), o) for r, o in zip(rs, orders)), key=lambda e: (e[2] is None, e[2] or 0))
        if L.contest(county, rid, level, kind, title, jname, jid, district, seat, special, partisan, entries, SRC_WASH,
                     [SPECIAL_NOTE if special else None] + notes + [unopposed_note(kind) if unopposed else None], label, WASH_URL):
            info["contests"] += 1
            info["unopposed"] += 1 if unopposed else 0

    for t in ex["tables"]:
        rows, layout = t["rows"], t["layout"]
        if layout == "contents":
            # the page's own table of what is on the ballot: its rows for questions are counted, never loaded
            info["questions"] += sum(1 for r in rows if re.search(r"annexation|local option|issue|question|measure|millage|tax", r.get("content", ""), re.I)
                                     and not re.search(r"elections", r.get("content", ""), re.I))
            continue
        if layout == "county":
            section = office = district = None
            groups, order = {}, []
            for n, r in enumerate(rows, start=1):
                if not any(r.get(k) for k in ("office", "district", "name", "party", "order")):
                    info["blank"] += 1
                    continue
                if r.get("office") and not r.get("name"):
                    if r["office"].lower() not in ("federal", "state", "county") or r.get("district") or r.get("party") or r.get("order"):
                        left_out(f"row {n} of the county table", 1, "a row with an office and no name that is not a section heading")
                        continue
                    section, office, district = r["office"].lower(), None, None
                    info["sections"] += 1
                    continue
                if r.get("office"):
                    office, district = r["office"], None
                if r.get("district"):
                    district = r["district"]
                if not r.get("name") or office is None or section is None:
                    left_out(f"row {n} of the county table", 1, "a candidate row with no name, or with no office or section above it")
                    continue
                info["rows"] += 1
                info[section] += 1
                if section != "county":
                    continue                                    # the federal and state loaders' offices
                key = (office, district)
                if key not in groups:
                    groups[key] = []
                    order.append(key)
                groups[key].append(r)
            for office, district in order:
                rs = groups[(office, district)]
                o = county_office(office, district, full)
                if o is None:
                    left_out(office + (f", District {district}" if district else ""), len(rs), "an office this loader does not know")
                    continue
                kind, title, d = o
                rid = f"2026-{STATE}-{county}-{slug(kind)}" + (f"-{slug(d)}" if d else "")
                store(rid, "county", kind, title, full, county, d, None, False, True, rs, [], race_label(title, d, None))
        elif layout == "municipal":
            groups, order = {}, []
            for n, r in enumerate(rows, start=1):
                if not any(r.get(k) for k in ("place", "office", "name", "order")):
                    info["blank"] += 1
                    continue
                if not (r.get("place") and r.get("office") and r.get("name")):
                    left_out(f"row {n} of the city table", 1, "a row with no city, office or name")
                    continue
                info["rows"] += 1
                info["municipal"] += 1
                o = city_office(r["office"])
                board = re.fullmatch(r"Director (.+) Board", r["office"], re.I)
                if o:
                    key = (r["place"], "city") + o
                elif board and board.group(1).lower() == r["place"].lower() and re.search(r"\bWater District$", r["place"], re.I):
                    key = (r["place"], "water", "water_board", "Board Director", None, None, False)
                else:
                    key = (r["place"], "unknown", r["office"], None, None, None, False)
                if key not in groups:
                    groups[key] = []
                    order.append(key)
                groups[key].append(r)
            for key in order:
                place, what, kind, title, district, seat, special = key
                rs = groups[key]
                if what == "unknown":
                    left_out(f"{place}: {kind}", len(rs), "an office this loader does not know")
                    continue
                if what == "water":
                    jid, jname, pk, level = f"{STATE}-X-{slug(place)}", place, f"X-{slug(place)}", "other"
                    L.places[jid] = ("special", jid, place, json.dumps([county]), SRC_WASH)
                else:
                    jid, jname, pk = city_place(L, places, county, place, SRC_WASH)
                    level = "city"
                rid = f"2026-{STATE}-{pk}-{slug(kind)}" + "".join(f"-{slug(x)}" for x in (district, seat) if x) + ("-S" if special else "")
                store(rid, level, kind, title, jname, jid, district, seat, special, False, rs, [NO_PARTY_NOTE],
                      f"{race_label(title, district, seat)}, {jname}")
        elif layout == "school":
            place = office = None
            groups, order = {}, []
            for n, r in enumerate(rows, start=1):
                if not any(r.get(k) for k in ("place", "office", "name", "order")):
                    info["blank"] += 1
                    continue
                if r.get("place"):
                    place, office = r["place"], None
                if r.get("office"):
                    office = r["office"]
                if not r.get("name") or not place or not office:
                    left_out(f"row {n} of the school table", 1, "a row with no name, or with no district or office above it")
                    continue
                info["rows"] += 1
                info["school"] += 1
                if (place, office) not in groups:
                    groups[(place, office)] = []
                    order.append((place, office))
                groups[(place, office)].append(r)
            for place, office in order:
                rs = groups[(place, office)]
                if not re.fullmatch(r"(Zone|Position|Pos\.?) ?\d{1,2}|At[ -]Large(?: Position ?\d{1,2})?", office, re.I) \
                        or not re.search(r"\bSchool District\b", place, re.I):
                    left_out(f"{place}: {office}", len(rs), "a school district or seat this loader does not know")
                    continue
                key = f"{county[2:]}-{slug(place)}"             # the list carries no state district number: the county's code and the name
                jid = f"{STATE}-S-{key}"
                L.places[jid] = ("school", jid, place, json.dumps([county]), SRC_WASH)
                store(f"2026-{STATE}-S-{key}-school-board-{slug(office)}", "school", "school_board", "School Board Member", place, jid,
                      office, None, False, False, rs, [SCHOOL_RUNOFF], f"School Board Member, {office}, {place}")
        elif layout == "judicial":
            office, groups = None, {}
            for n, r in enumerate(rows, start=1):
                if not any(r.get(k) for k in ("office", "name", "order")):
                    info["blank"] += 1
                    continue
                if r.get("office"):
                    office = r["office"]
                if not r.get("name") or not office:
                    left_out(f"row {n} of the judicial runoff table", 1, "a row with no name, or with no office above it")
                    continue
                info["rows"] += 1
                info["judicial"] += 1
                groups.setdefault(office, []).append(r)
            # these runoffs are stored from the Secretary of State's list; the county's table is only read against it
            for office, rs in groups.items():
                o = court_office(office)
                mine = court["names"].get(court_key(o)) if o else None
                same = bool(mine) and len(mine[1]) == len(rs) and all(any(same_person(r["name"], n) for n in mine[1]) for r in rs)
                info["court_match"] = same if info["court_match"] in (None, True) else False
                if not same:
                    L.check(f"Washington County's list: {office}: its names are not the names on the Secretary of State's list for "
                            "that runoff" if mine else f"Washington County's list: {office}: no such runoff on the Secretary of State's list")
                    if not mine:
                        L.gap("county", county, full, office, NOT_READ, WASH_URL)
    info["ok"] = True
    return info


# ----- the agencies' publications the notes rest on: the election calendar and the commissioners' manual -----

def checked_pdf(local_dir, name, what, url, facts, in_order, say, max_age_days=90):
    """{checked, missing, sha256, fetched}: an agency's publication (a text PDF), fetched and the sentences the notes
    rely on looked for in its text. Only letters and digits are compared, so line breaks, spacing and the kind of
    quotation mark do not matter; with in_order the facts must come in the order given (a summary of dates). Nothing
    of the file is kept but whether they were found and its SHA-256."""
    path = os.path.join(local_dir, name)
    if fresh(path, max_age_days):
        return json.load(open(path, encoding="utf-8"))
    bare = lambda s: re.sub(r"[^a-z0-9]+", "", s.lower())
    try:
        raw = patient(lambda: net.get(url, accept="application/pdf"), what)
        pdf = pdftext.PDF(raw)
        text = ""
        for page, res in pdf.pages():
            for _y, runs in pdftext.rows(pdf, page, res):
                text += bare(pdftext.join(runs))
        at, missing = 0, []
        for fact in facts:
            i = text.find(bare(fact), at)
            if i < 0:
                missing.append(fact)
            elif in_order:
                at = i + 1
        out = {"checked": not missing, "missing": missing, "sha256": hashlib.sha256(raw).hexdigest(), "fetched": dt.date.today().isoformat()}
        del raw, text
    except (RuntimeError, HTTPError, URLError, OSError, ValueError, KeyError, TypeError, IndexError) as e:
        if os.path.exists(path):
            say(f"    Arkansas (local races): {what} could not be read afresh ({type(e).__name__}); using the check made earlier")
            return json.load(open(path, encoding="utf-8"))
        return {"checked": False, "missing": ["not read"], "sha256": "", "fetched": ""}
    os.makedirs(local_dir, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=0)
    return out


# ----- all of it -----

def local_part(local_dir, cmap, eid, glist, say):
    """Everything the local part writes: {races, cands, places, gaps, notes, sources, and the report's lines}."""
    os.makedirs(local_dir, exist_ok=True)
    L = _Rows(cmap)
    clist, _cpath = court_list(local_dir, say)
    march, mpath = march_contests(local_dir, eid, say) if clist and clist["rows"] else (None, None)
    court = court_rows(L, clist, march, cmap)
    if clist and (clist["counts"].get("state", 0) != len(glist["rows"]) or clist["counts"].get("local", 0) != glist["others"].get("local", 0)
                  or clist["counts"].get("federal", 0) != glist["others"].get("federal", 0)):
        L.check("the Candidate Search read for the local rows does not have the counts of the one read for the state rows (the "
                f"state rows were read on {glist['read']}, the local rows on {clist['read']}); the older one is read again within two days")
    places, p_sha, p_fetched, p_rows = read_places(local_dir, cmap, say)
    pul = pulaski_rows(L, places, local_dir, say)
    wash = washington_rows(L, places, court, local_dir, say)
    cal = checked_pdf(local_dir, "ar_2026_election_calendar_check.json", "the election calendar", CALENDAR_URL, CALENDAR_ORDER, True, say)
    if not cal.get("checked"):
        L.check("the election calendar's facts could not be confirmed (" + "; ".join(cal.get("missing") or ["not read"]) + ")")
    manual = checked_pdf(local_dir, "ar_2026_cbec_manual_check.json", "the election commissioners' manual", MANUAL_URL, MANUAL_FACTS, False, say)
    if not manual.get("checked"):
        L.check("the election commissioners' manual: these sentences could not be confirmed (" + "; ".join(manual.get("missing") or ["not read"]) + ")")

    # every county whose own list is not read
    saved = [f for f in BENTON_SAVED if os.path.exists(os.path.join(local_dir, f))]
    for geoid, full in cmap:
        if geoid in (PULASKI, WASHINGTON):
            continue
        if geoid == BENTON:
            L.gap("county", geoid, full, "county, city and township contests",
                  ("A copy of this county's list saved from a browser is in the kit, but the reader for it is not written yet, so "
                   "its contests are not shown." if saved else
                   "The county election commission's site turns away the program that reads these lists, so its list has to be "
                   "saved from a browser first; its contests are not loaded yet."), BENTON_URL)
        else:
            L.gap("county", geoid, full, "county, city and township contests", COUNTY_NOT_LOADED, None)
    n_gap_counties = len({g[2] for g in L.gaps if g[1] == "county" and g[4] == "county, city and township contests"})

    # the notes
    st = L.stats
    def county_words(geoid, what):
        return f"{st[f'county {geoid} contests']} contests, {st[f'county {geoid} candidates']} candidates{what}"
    parts = []
    if court["races"]:
        parts.append(f"the {court['races']} November runoffs for circuit judge and prosecuting attorney on the Secretary of State's "
                     f"candidate list ({court['candidates']} candidates; the counties of each judicial district are those of the "
                     "official March 3 results)")
    if pul["ok"]:
        parts.append("Pulaski County's contested county, constable and city contests from its election commission's ballot position "
                     f"draw ({county_words(PULASKI, ', in the order drawn')})")
    if wash["ok"]:
        parts.append("Washington County's county, city, water district and school runoff contests from its election commission's "
                     f"candidate list ({county_words(WASHINGTON, '')}; the {wash['unopposed']} unopposed candidates are shown and marked)")
    coverage = ("Read so far: " + "; ".join(parts) + ". " if parts else "Nothing could be read when this was built. ") + (
        f"Not here yet: the other {n_gap_counties} of the 75 counties, each named among the gaps"
        + (", and Pulaski County's offices with one candidate, which the draw leaves out" if pul["ok"] else "") + ". "
        + ("City offices are shown as nonpartisan: Pulaski County's draw lists every city candidate as Independent, Washington "
           "County's list gives no party for city offices, and no party is printed beside a name in a nonpartisan city election "
           "(A.C.A. 7-5-207). " if pul["ok"] and wash["ok"] and not pul.get("cities on party lines") else "")
        + "Ballot questions (constitutional issues, annexations, local option votes) are not loaded.")
    cal_text = ("On November 3, 2026 Arkansas counties elect their county officers by party (county judge, sheriff, county and "
                "circuit clerks, assessor, collector, treasurer, coroner, justices of the peace and constables), and cities and "
                "towns elect the mayors, council members and other city officers whose terms are up. School boards were elected at "
                "the annual school election on March 3, 2026, and circuit judges and prosecuting attorneys at the nonpartisan "
                "general election the same day, so only their runoffs are on the November ballot. A runoff for a county or city "
                "office, where one is needed, is on December 1, 2026.")
    notes = [(STATE, "local_calendar", cal_text,
              "Arkansas Secretary of State, 2026 Election Dates (rev. June 2025), which cites A.C.A. 7-5-102, 7-10-102, 6-14-102, "
              "6-14-121 and 7-5-106; the offices named are those on the county lists read here", CALENDAR_URL),
             (STATE, "local_coverage", coverage,
              "Arkansas Secretary of State, 2026 Candidate Search and official results of March 3, 2026; Pulaski County Election "
              "Commission, ballot position draw; Washington County Election Commission, candidate list; Arkansas State Board of "
              "Election Commissioners, 2026 procedures manual for county election commissioners (what the ballot prints)",
              fed.SEARCH_PAGE)]

    # nothing written here may look like contact details (addresses of sources live only in url columns)
    for what, texts in (("a race note", [r[16] for r in L.races]), ("a candidate note", [c[14] for c in L.cands]),
                        ("a gap", [g[5] for g in L.gaps] + [g[4] for g in L.gaps]), ("a note", [n[2] for n in notes] + [n[3] for n in notes])):
        if any(t and contact_like(t, True) for t in texts):
            raise SystemExit(f"Arkansas (local races): {what} written by this loader reads like contact details to the check; nothing was changed")

    # the sources
    src = []
    if clist:
        src.append((SRC_COURT, STATE, "official candidate list", AGENCY, "2026 Candidate Search: the November runoffs for circuit judge "
                    "and prosecuting attorney", fed.SEARCH_PAGE, "", clist["read"], clist["sha256"], len(clist["rows"]),
                    f"The same list the state rows come from, read in pages of 100: {clist['records']} rows, of which "
                    f"{clist['counts'].get('local', 0)} are for circuit judge and prosecuting attorney (the runoffs of the nonpartisan "
                    "general election of March 3, held on November 3). Office, ballot name and party read; the filer number and "
                    "filing date are dropped as each row arrives and the detail cards are never fetched. The list has no contact "
                    "columns. The SHA-256 is of the pages as fetched. The list prints no ballot order."))
    if march:
        src.append((SRC_MARCH, STATE, "official results", AGENCY, "Election Results: Nonpartisan General Election, March 3, 2026 (circuit "
                    "judge and prosecuting attorney contests)" + ("" if march.get("official") else " (not yet official)"), march["link"],
                    (march.get("last_updated") or "")[:10], march["read"], sha_of(mpath), sum(len(c["choices"]) for c in march["contests"]),
                    f"From the results site's data service, version {march.get('version')}, marked "
                    f"{'official' if march.get('official') else 'not official'}: {len(march['contests'])} contests. Contest names, "
                    "candidate names, votes, precincts and the counties that returned votes only (the service carries no contact "
                    "details). Used for the counties each judicial district covers and to check each November runoff: no majority on "
                    f"March 3, and the list's two names its top two ({court['verified']} of {court['races']} checked so). No March 3 "
                    "votes are stored for local offices. The SHA-256 is of the extract kept."))
    if pul["rows"]:
        src.append((SRC_PULASKI, STATE, "official ballot draw", "Pulaski County Election Commission", "11/3/2026 General Election: "
                    "Ballot Position Draw", PULASKI_URL, pul["conducted"], mdate(pul["path"]), sha_of(pul["path"]), pul["rows"],
                    f"A text PDF of {pul['pages']} pages and five columns (Name of Office, Ballot Name, Party, # Drawn, Ballot "
                    f"Position), all read; it has no contact columns. {pul['rows']} candidate lines: {pul['federal']} for federal "
                    f"and {pul['state']} for state offices (left to those pages) and {pul['local']} "
                    f"for county, constable and city offices, in {pul['contests']} contests. Only contests with two or more candidates "
                    "are drawn. The ballot order stored is the Ballot Position column."))
    if wash["ok"]:
        src.append((SRC_WASH, STATE, "official candidate list", "Washington County Election Commission", "November 3, 2026 Election "
                    "Information: candidates for the general election, the municipal general election, the nonpartisan judicial "
                    "runoff and the annual school runoff", WASH_URL, "", wash["read"], wash["sha256"], wash["rows"],
                    f"A web page of tables. {wash['rows']} candidate rows: {wash['federal']} federal and {wash['state']} state (left to "
                    f"those pages), {wash['county']} county, {wash['municipal']} city and district, {wash['judicial']} judicial runoff "
                    f"(stored from the Secretary of State's list; read here only to compare) and {wash['school']} school runoff. "
                    "Columns read: the office, the district, the municipality or school district, the candidate's name, the party "
                    "and the ballot order (a number, or a mark that the candidate is unopposed). The tables also carry e-mail, "
                    "address, city of residence and ZIP columns, which are never read: their cells are skipped as the page is parsed, "
                    "and only the cut-down rows are kept. The SHA-256 is of the page as fetched; the page changes a little with every "
                    f"request, so the SHA-256 of the rows kept is given too: {wash.get('rows_sha256', '')}. The page also names "
                    f"{wash['questions']} local ballot questions, which are not loaded."))
    if p_rows:
        src.append((SRC_PLACES, STATE, "place codes", "U.S. Census Bureau", "2020 Census place codes for Arkansas (st05_ar_place2020.txt)",
                    PLACE_URL, "", p_fetched, p_sha, p_rows, "Names, codes and counties of incorporated cities and towns only; the "
                    "file has no contact data and is kept whole. A city on a county's list takes the Bureau's code and name when "
                    "exactly one incorporated place of that name reaches the county."))
    src.append((SRC_CALENDAR, STATE, "official calendar", "Arkansas Secretary of State", "2026 Election Dates (rev. June 2025)", CALENDAR_URL,
                "2025-06", cal.get("fetched", ""), cal.get("sha256", ""), 0,
                ("Checked in its text, in the order it prints them: " + "; ".join(CALENDAR_ORDER) + "." if cal.get("checked") else
                 "Its facts could not be confirmed on the last read.") + " The file is not kept."))
    src.append((SRC_MANUAL, STATE, "official manual", "Arkansas State Board of Election Commissioners",
                "2026 County Board of Election Commissioners Procedures Manual", MANUAL_URL, "", manual.get("fetched", ""),
                manual.get("sha256", ""), 0,
                ("Checked in its text: " + "; ".join(MANUAL_FACTS) + "." if manual.get("checked") else
                 "Its sentences could not be confirmed on the last read.")
                + " These are what the notes on unopposed candidates and on city offices rest on (the manual cites A.C.A. 7-5-207 "
                  "and 14-42-206). The file is not kept."))

    by_level = ", ".join(f"{k[6:]} {v}" for k, v in sorted(st.items()) if k.startswith("level "))
    kinds = ", ".join(f"{k[5:].replace('_', ' ')} {v}" for k, v in sorted(st.items()) if k.startswith("kind "))
    lines = [f"    Arkansas (local races): {court['races']} runoffs for circuit judge and prosecuting attorney ({court['candidates']} "
             f"candidates, {court['verified']} checked against the official March 3 results"
             + (f"; {court['no_majority']} contests there ended without a majority" if court["no_majority"] is not None else "") + ")",
             f"    Arkansas (local races): {st['contests']} county and local contests, {st['candidates']} candidates ({by_level}); "
             f"partisan {st['partisan']}, nonpartisan {st['contests'] - st['partisan']}; special {st['special']}; with ballot order "
             f"{st['with ballot order']}; kinds: {kinds}",
             f"    Arkansas (local races): Pulaski County's draw: {pul['rows']} lines ({pul['federal']} federal, {pul['state']} state, "
             f"{pul['local']} local) -> {st[f'county {PULASKI} contests']} contests, "
             f"{st[f'county {PULASKI} candidates']} candidates",
             f"    Arkansas (local races): Washington County's list: {wash['rows']} candidate rows ({wash['federal']} federal, "
             f"{wash['state']} state, {wash['county']} county, {wash['municipal']} city and district, {wash['judicial']} judicial runoff, "
             f"{wash['school']} school runoff; {wash['sections']} section rows and {wash['blank']} blank rows skipped) -> "
             f"{st[f'county {WASHINGTON} contests']} contests, {st[f'county {WASHINGTON} candidates']} candidates, "
             f"{wash['unopposed']} unopposed; judicial runoff names " + {True: "agree with", False: "DIFFER from", None: "not compared with"}[wash["court_match"]]
             + " the Secretary of State's list",
             f"    Arkansas (local races): left out: {st['contests left out']} contests ({st['rows left out']} rows); cells blanked by the "
             f"contact check: {(clist or {}).get('blanked', 0) + pul.get('blanked', 0) + wash.get('blanked', 0)}; gaps: "
             f"{len(L.gaps)} ({n_gap_counties} counties not read); places: {len(L.places)}"]
    return {"races": L.races, "cands": L.cands, "places": sorted(L.places.values()), "gaps": L.gaps, "notes": notes, "sources": src,
            "lines": lines, "checks": L.checks, "court": court}


# ---------- the load ----------

def load(db_path, say=print, extract_dir=os.path.join(CACHE, "ar"), local_dir=LOCAL_DIR):
    net.patient_lookups()
    glist, gpath = candidate_list(extract_dir, say)
    ids = election_ids(say)
    rdata, rpath = {}, {}
    for kind in ELECTIONS:
        rdata[kind], rpath[kind] = results(extract_dir, kind, ids[kind], say)
    procs = proclamations(extract_dir, say)
    seats, offs, as_of = roster()
    cmap = counties()

    # the November list: races and candidates
    races, general, held_back = {}, [], []
    for r in glist["rows"]:
        what, race = list_office(r["office"])
        if not r["name"] or not r["party"]:
            raise SystemExit(f"Arkansas (state races): a candidate for {race['race_id']} with no name or no party on the Candidate Search")
        if race["chamber"] and (race["chamber"], race["district"]) in SPECIAL_PRIMARY_ONLY:
            held_back.append(race["race_id"])
            continue
        races.setdefault(race["race_id"], race)
        general.append((race["race_id"], r["party"], r["name"]))
    dup = [k for k, v in Counter((rid, fold(n)) for rid, _p, n in general).items() if v > 1]
    if dup:
        raise SystemExit(f"Arkansas (state races): one name twice in one race: {sorted(r for r, _ in dup)}")
    nominees = defaultdict(list)
    for rid, party, name in general:
        nominees[(rid, party)].append(name)
    two_of_a_party = sorted({rid for (rid, party), names in nominees.items() if len(names) > 1 and party != "Independent"})

    # which seats are on the ballot
    sen = sorted(int(r["district"]) for r in races.values() if r["office_kind"] == "state_senate")
    hou = sorted(int(r["district"]) for r in races.values() if r["office_kind"] == "state_house")
    if hou != list(range(1, 101)):
        raise SystemExit(f"Arkansas (state races): the Candidate Search has House districts {hou}, not all 100")
    regular_sen = [d for d in sen if f"2026-{STATE}-SS{d}" not in SPECIAL_RACES]
    checks = []
    if len(regular_sen) != 17:
        checks.append(f"{len(regular_sen)} regular Senate seats on the list ({regular_sen}); 17 were expected (35 seats, four-year terms, "
                      "the other 18 up in 2024 and 2028)")
    for rid in SPECIAL_RACES:
        if rid not in races:
            checks.append(f"the special election {rid} has no candidates on the list")
    missing = sorted(k for k, *_ in STATEWIDE.values() if f"2026-{STATE}-{k}" not in races)
    if missing:
        checks.append(f"statewide offices with no candidate on the list: {missing}")
    for key, p in PROCLAMATIONS.items():
        if not procs.get(key, {}).get("checked"):
            checks.append(f"the {key} proclamation's facts could not be confirmed ({', '.join(procs.get(key, {}).get('missing') or ['not read'])})")
    if held_back:
        checks.append(f"the Candidate Search now lists {len(held_back)} candidate(s) for State Senate District 18, whose special primary is on "
                      "the November 3 ballot; they are not stored (they are primary candidates, not November ones)")
    for rid in two_of_a_party:
        checks.append(f"{rid}: the list names more than one candidate of one party; all are stored as listed, with a note")

    # the fields: the March 3 primary, the March 31 runoff and the special primaries
    problems, skipped, prim, sent = [], Counter(), [], {}
    for kind in ELECTIONS:
        rows, s = fields_from(rdata[kind], kind, races, nominees, problems, skipped)
        prim += [(kind,) + r for r in rows]
        sent[kind] = s
    for kind in rdata:
        skipped["appellate court"] += rdata[kind].get("skipped", {}).get("appellate court", 0)
    # every primary that sent two on has its runoff, with those two, and the runoff's winner is the November candidate
    for pk, rk in (("primary", "runoff"), ("hd44", "hd44r")):
        for (rid, party), pairs in sent[pk].items():
            ran = [r[4] for r in prim if r[0] == rk and r[1] == rid and r[5] == party]
            if not any(len(ran) == len(pair) and all(any(same_person(a, b) for b in pair) for a in ran) for pair in pairs):
                problems.append(f"{rid} {party}: the primary sent two on to a runoff, but the runoff results do not show those two")
    for kind in rdata:
        if not rdata[kind]["official"]:
            problems.append(f"the {ELECTIONS[kind]['name']} results are not marked official: votes not stored")

    # today's holders, and the sitting member on the ballot
    holders, notes = {}, {}
    for rid, r in races.items():
        h = None
        if r["chamber"]:
            h = seats.get((r["chamber"], r["district"]))
            if h is None:
                notes[rid] = f"The Open States roster ({as_of}) lists no sitting member for this seat."
        else:
            roster_office = STATEWIDE[r["label"]][3]
            h = offs.get(roster_office) if roster_office else None
            if h is None:
                notes[rid] = f"The Open States roster this site uses does not carry the {r['office']}, so today's holder is not shown."
        holders[rid] = h
    if "2026-AR-SS1" in races:
        notes["2026-AR-SS1"] = ("A special election for the rest of the term: the senator resigned effective June 30, 2026, and the "
                                "Governor's proclamation of July 2, 2026 set this election for November 3, with a special primary on "
                                "August 18. The seat is vacant until then.")
    if "2026-AR-SH8" in two_of_a_party:
        notes["2026-AR-SH8"] = (("The Open States roster (" + as_of + ") lists no sitting member for this seat. ") if holders.get("2026-AR-SH8") is None else "") + (
            "The Secretary of State's list names two Republican candidates for this seat as well as a Democrat, and does not say "
            "whether one Republican replaced the other or whether a special election is also on the ballot; all three are "
            "shown as the list gives them.")
    elif two_of_a_party:
        for rid in two_of_a_party:
            notes[rid] = ((notes.get(rid) + " ") if notes.get(rid) else "") + (
                "The Secretary of State's list names more than one candidate of one party for this seat and does not say why; "
                "all are shown as the list gives them.")

    names_in = defaultdict(set)
    for rid, _party, name in general:
        names_in[rid].add(name)
    for r in prim:
        names_in[r[1]].add(r[4])
    sitting, party_differs = {}, []
    for rid, h in holders.items():
        if not h:
            continue
        fit = {fold(untitled(n)) for n in names_in.get(rid, ()) if holder_fits(n, h)}
        if len(fit) == 1:
            sitting[rid] = (fit.pop(), h["id"])
    is_sitting = lambda rid, name: rid in sitting and fold(untitled(name)) == sitting[rid][0]
    for rid, party, name in general:
        if is_sitting(rid, name) and holders[rid]["party"] and holders[rid]["party"] != party:
            party_differs.append(rid)

    # rows: November
    cand = []
    not_in_primary = []
    for rid, party, name in general:
        inc = is_sitting(rid, name)
        note = TITLE_NOTE if TITLE.match(name) else None
        cand.append((rid, "general", GENERAL, name, party, party_code(party), None, 1 if inc else 0, 0, None, None, None,
                     sitting[rid][1] if inc else None, SRC_LIST, note))
    n_general_rows = len(cand)
    # rows: the primaries, runoffs and special primaries
    for kind, rid, election, date, name, party, votes, pct, outcome, wi, note in prim:
        inc = is_sitting(rid, name)
        cand.append((rid, election, date, name, party, party_code(party), None, 1 if inc else 0, wi, votes, pct, outcome,
                     sitting[rid][1] if inc else None, ELECTIONS[kind]["src"], note))
    keys = Counter((c[0], c[1], c[3]) for c in cand)
    if any(v > 1 for v in keys.values()):
        raise SystemExit(f"Arkansas (state races): one name twice in one race and election: {[k for k, v in keys.items() if v > 1]}")
    if n_general_rows != len(glist["rows"]) - len(held_back):
        raise SystemExit("Arkansas (state races): November rows stored do not match the Candidate Search's state rows")

    race_rows = []
    for rid, r in sorted(races.items()):
        h = holders[rid]
        race_rows.append((rid, STATE, r["level"], r["office_kind"], r["office"], NAME, FIPS, None, r["district"], None,
                          1 if rid in SPECIAL_RACES else 0, 1, h["id"] if h else None, h["full"] if h else None,
                          h["party"] if h else None, GENERAL, notes.get(rid)))
    place_rows = [("county", geoid, full, json.dumps([geoid]), SRC_COUNTIES) for geoid, full in cmap]

    # the local part: the courts' November runoffs, and the counties whose own lists are read
    loc = local_part(local_dir, cmap, ids["primary"], glist, say)
    clash = {r[0] for r in race_rows} & {r[0] for r in loc["races"]}
    if clash:
        raise SystemExit(f"Arkansas (local races): a local race id is also a state race's ({sorted(clash)[0]}); nothing was changed")
    lkeys = Counter((c[0], c[1], c[3]) for c in loc["cands"])
    if any(v > 1 for v in lkeys.values()) or len({r[0] for r in loc["races"]}) != len(loc["races"]):
        raise SystemExit("Arkansas (local races): one race or one name twice among the local rows; nothing was changed")

    # the sources
    n_rows = lambda kind: sum(len(c["choices"]) for c in rdata[kind]["contests"])
    n_fields = Counter((r[0], r[1], r[2]) for r in prim)
    fields_by_kind = Counter(k for k, _rid, _e in n_fields)
    src = [
        (SRC_LIST, STATE, "official candidate list", AGENCY, "2026 Candidate Search: state offices", fed.SEARCH_PAGE,
         "", glist["read"], glist["sha256_rows"], len(glist["rows"]),
         f"Read from the page's own data address ({fed.SEARCH_API}, postID {fed.POST_ID}): {glist['records']} rows for every "
         "state and federal office on the November 3, 2026 ballot; the rows for the seven statewide offices, the Arkansas Senate "
         "and the Arkansas House kept (office, ballot name, party; the filer number and filing date are dropped and the detail "
         "cards are never fetched). The list prints no ballot order, so none is stored; it names no write-in candidates, and "
         "only candidates still in the running. Names as filed for the ballot, titles included. Senate seats on it: "
         f"{len(regular_sen)} regular seats and a special election for District 1. Left to others: "
         f"{glist['others'].get('federal', 0)} U.S. Senate and U.S. Congress rows (the federal pages) and "
         f"{glist['others'].get('local', 0)} circuit judge and prosecuting attorney rows (the November runoffs of nonpartisan "
         "offices, stored from the same list as court races)."),
        (SRC_ROSTER, STATE, "roster", "Open States people project (CC0)", "Arkansas legislators and statewide officials, as loaded into state_ar.sqlite",
         "https://github.com/openstates/people", as_of, as_of, "", len(seats) + len(offs),
         "Today's holder of each seat and office. The roster does not carry the Commissioner of State Lands. A candidate is "
         "marked as the sitting member only when the name fits the holder of that seat or office and no other name in the race fits."),
        (SRC_COUNTIES, STATE, "boundaries", "U.S. Census Bureau", "Cartographic boundary file, counties, 2024, 1:500,000 (cb_2024_us_county_500k)",
         "https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_county_500k.zip", "", mdate(COUNTY_ZIP), sha_of(COUNTY_ZIP),
         len(place_rows), "Arkansas's 75 counties: names and GEOIDs only."),
    ]
    for key, p in PROCLAMATIONS.items():
        got = procs.get(key, {})
        src.append((p["src"], STATE, "official notice", "Office of the Governor of Arkansas", p["title"], p["url"], p["date"],
                    got.get("fetched", ""), got.get("sha256", ""), 0,
                    ("Checked in its text: " + "; ".join(p["facts"]) + "." if got.get("checked") else "Its facts could not be confirmed on the last read.")
                    + {"SD1": " The special election is on November 3, 2026; its candidates are on the Candidate Search.",
                       "SD18": " Its special primary is on the November 3, 2026 ballot and the special election on January 5, 2027; its "
                               "candidates were not on the Candidate Search when read, so nothing is stored for it yet.",
                       "HD44VIN": " It called a special primary on June 2, 2026 to fill a vacancy in the nomination, with no runoff, so "
                                  "that contest was won by the most votes."}[key]))
    for kind, spec in ELECTIONS.items():
        d = rdata[kind]
        src.append((spec["src"], STATE, "official results", AGENCY, spec["title"] + ("" if d["official"] else " (not yet official)"),
                    d["link"], (d.get("last_updated") or "")[:10], d["read"], sha_of(rpath[kind]), n_rows(kind),
                    f"From the results site's data service ({fed.ENR_API}, client {fed.CLIENT}, election {d['election_id']}), version "
                    f"{d['version']}, marked {'official' if d['official'] else 'NOT official: votes not stored'}. Contest names, candidate "
                    f"names, parties, votes and winner flags only. {fields_by_kind.get(kind, 0)} party contests with a field for the "
                    "races on these pages. Checked: all precincts reporting, candidates adding up to each contest's total, county figures "
                    "adding up to the totals, the winner being the party's candidate on the November list."))

    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA + EXTRA_SCHEMA)
    with con:
        con.execute("DELETE FROM sl_candidates WHERE race_id LIKE '2026-AR-%'")
        con.execute("DELETE FROM sl_races WHERE state = 'AR'")
        con.execute("DELETE FROM sl_sources WHERE state = 'AR'")
        con.execute("DELETE FROM sl_places WHERE source_id LIKE 'ar-%'")
        con.execute("DELETE FROM sl_gaps WHERE state = 'AR'")
        con.execute("DELETE FROM sl_notes WHERE state = 'AR'")
        con.executemany("INSERT INTO sl_races VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", race_rows + loc["races"])
        con.executemany("INSERT INTO sl_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", cand + loc["cands"])
        con.executemany("INSERT INTO sl_places VALUES (?,?,?,?,?)", place_rows + loc["places"])
        con.executemany("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", src + loc["sources"])
        con.executemany("INSERT OR REPLACE INTO sl_gaps VALUES (?,?,?,?,?,?,?)", loc["gaps"])
        con.executemany("INSERT INTO sl_notes VALUES (?,?,?,?,?)", loc["notes"])
    con.close()

    # the report: counts only
    kind_of = lambda rid: races[rid]["office_kind"] if races[rid]["level"] == "legislature" else "statewide"
    by = Counter(kind_of(rid) for rid in races)
    gen_by = Counter(kind_of(rid) for rid, _p, _n in general)
    one = Counter(kind_of(rid) for rid, k in Counter(rid for rid, _p, _n in general).items() if k == 1)
    inc_by = Counter(kind_of(rid) for rid in sitting)
    fld_by = Counter(kind_of(rid) for (_k, rid, _e) in n_fields)
    say(f"    Arkansas (state races): {by['state_senate']} Senate seats ({len(regular_sen)} regular and a special for District 1), "
        f"{by['state_house']} House seats, {by['statewide']} statewide offices; {len(general)} names on the November ballot "
        f"(Senate {gen_by['state_senate']}, House {gen_by['state_house']}, statewide {gen_by['statewide']}; one candidate only: "
        f"Senate {one['state_senate']}, House {one['state_house']}, statewide {one['statewide']}); sitting member on the ballot: "
        f"Senate {inc_by['state_senate']}, House {inc_by['state_house']}, statewide {inc_by['statewide']}")
    say(f"    Arkansas (state races): party contests with a field: Senate {fld_by['state_senate']}, House {fld_by['state_house']}, "
        f"statewide {fld_by['statewide']} ({len(prim)} candidate rows: " + ", ".join(f"{ELECTIONS[k]['date']} {fields_by_kind[k]}" for k in ELECTIONS)
        + f"); left out: {sum(skipped.values())} contests ({', '.join(f'{v} {k}' for k, v in sorted(skipped.items()))})")
    say(f"    Arkansas (state races): left to others on the list: {glist['others'].get('federal', 0)} federal rows; its "
        f"{glist['others'].get('local', 0)} circuit judge and prosecuting attorney rows are the local part's. Senate District 18: "
        "special primary on November 3 (Governor's proclamation of September 18, 2026), no candidates on the list yet, nothing stored")
    for line in loc["lines"]:
        say(line)
    for c in loc["checks"]:
        say(f"    CHECK Arkansas (local races): {c}")
    if party_differs:
        say(f"    CHECK Arkansas (state races): sitting member listed under another party: {party_differs}")
    for c in checks:
        say(f"    CHECK Arkansas (state races): {c}")
    if problems:
        say("    CHECK Arkansas (state races): the results did not all reconcile: " + "; ".join(problems))
    vac = sorted((rid for rid, h in holders.items() if h is None and races[rid]["level"] == "legislature"),
                 key=lambda x: (x[8:10], int(re.sub(r"\D", "", x[10:]))))
    if vac:
        say(f"    Arkansas (state races): no sitting member in the roster for {', '.join(vac)}")
    return len(cand) + len(loc["cands"])


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: python ballot/state_local_ar.py <database file>")
    load(sys.argv[1])
