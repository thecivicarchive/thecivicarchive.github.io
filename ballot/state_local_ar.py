"""
ballot/state_local_ar.py - Arkansas's state races on the November 3, 2026 ballot: the Arkansas Senate seats up this year
(17 regular seats, plus a special election for District 1), all 100 Arkansas House seats, and the seven statewide
offices (Governor, Lieutenant Governor, Attorney General, Secretary of State, State Treasurer, Auditor of State and
Commissioner of State Lands), with the party primaries and runoffs that chose the nominees. Written into
ballot_local_2026.sqlite (never ballot_2026.sqlite).

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
  - Circuit judges and prosecuting attorneys on the list are local offices, left for the county pages (counted,
    nothing stored). U.S. Senate and U.S. Congress rows are the federal loader's.
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
import zipfile
from collections import Counter, defaultdict
from urllib.error import HTTPError, URLError
from urllib.parse import quote

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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

def candidate_list(folder, say, max_age_days=2):
    """{rows: [{office, name, party}] for state offices, others: {kind: count}, records, read, sha256_rows}: from the saved
    extract when fresh, else read afresh (only the name, office and party cells are ever kept)."""
    path = os.path.join(folder, "sl_ar_2026_candidate_search_state.json")
    if fresh(path, max_age_days):
        return json.load(open(path, encoding="utf-8")), path
    try:
        rows, others, start, total = [], Counter(), 0, None
        while total is None or start < total:
            page = patient(lambda: fed.search_page(start), "the Candidate Search")
            total = int(page["recordsFiltered"])
            data = page.get("data") or []
            if not data:
                break
            for r in data:
                office = re.sub(r"\s+", " ", str(r.get("Descript") or "")).strip()
                what, _race = list_office(office)
                if what != "state":
                    others[what] += 1
                    continue
                rows.append({"office": office, "name": re.sub(r"\s+", " ", str(r.get("CanBallotName") or "")).strip(),
                             "party": re.sub(r"\s+", " ", str(r.get("PartyAffiliation") or "")).strip()})
            start += len(data)
            time.sleep(1.5)
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


# ---------- the load ----------

def load(db_path, say=print, extract_dir=os.path.join(CACHE, "ar")):
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
         f"{glist['others'].get('local', 0)} circuit judge and prosecuting attorney rows (local offices, for the county pages)."),
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
    con.executescript(SCHEMA)
    with con:
        con.execute("DELETE FROM sl_candidates WHERE race_id LIKE '2026-AR-%'")
        con.execute("DELETE FROM sl_races WHERE state = 'AR'")
        con.execute("DELETE FROM sl_sources WHERE state = 'AR'")
        con.execute("DELETE FROM sl_places WHERE source_id LIKE 'ar-%'")
        con.executemany("INSERT INTO sl_races VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", race_rows)
        con.executemany("INSERT INTO sl_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", cand)
        con.executemany("INSERT INTO sl_places VALUES (?,?,?,?,?)", place_rows)
        con.executemany("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", src)
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
    say(f"    Arkansas (state races): left to others on the list: {glist['others'].get('federal', 0)} federal and "
        f"{glist['others'].get('local', 0)} local rows. Senate District 18: special primary on November 3 (Governor's proclamation "
        "of September 18, 2026), no candidates on the list yet, nothing stored")
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
    return len(cand)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: python ballot/state_local_ar.py <database file>")
    load(sys.argv[1])
