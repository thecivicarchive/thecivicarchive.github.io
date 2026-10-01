"""
ballot/state_local_nd.py - North Dakota's state and local races on the November 3, 2026 ballot: the Legislative
Assembly seats up this year, the statewide offices, and the Supreme Court and district court seats, with the June 9
primaries that chose the nominees; and, from the same official list, every county office, soil conservation district
supervisor and Garrison Diversion Conservancy District director on the ballot in the 53 counties. Written into
ballot_local_2026.sqlite (never ballot_2026.sqlite), North Dakota's rows only.

    python -m ballot.state_local_nd <database> [cache folder] [--refresh]

Sources, all the Secretary of State's own:
  * the 2026 General Election Contest/Candidate List (vip.sos.nd.gov/candidatelist.aspx?eid=348) and the 2026 Primary
    Election Contest/Candidate List (eid=346): search pages, asked as the page's own Search button asks, once per
    jurisdiction (Statewide, Legislative, Judicial) with no contest chosen. The table carries mailing addresses, e-mail,
    phones and websites; only five cells of each row are ever read (the contest title, the office, the district, the
    candidate's name and the party), found by their headings, and only those five are kept on disk. The County and Term
    Length columns are not read by these searches (the county-level search below reads the County column too). The
    list is printed alphabetically by family name and gives no ballot order, so ballot_order is left empty.
  * the official June 9 primary results, from the Election Night Reporting site resultsnd.sos.nd.gov, read through the
    service behind it (api.resultsnd.sos.nd.gov): the election's details, the contest list (names, how many to vote for,
    the choices) and each contest type's results (statewide totals only; county and precinct figures are not kept).

Who holds each seat today comes from state_nd.sqlite (the Open States roster the state pages use): legislators serving
now, by chamber and district, and the officials table for the statewide offices it carries (Attorney General,
Secretary of State). Only names, parties, districts and start dates are read from it. A candidate is marked as the
incumbent only when the name fits exactly one sitting member of the same chamber and district (or the holder of the
same statewide office). Offices the roster does not carry (the commissioners, the Superintendent, the courts) have no
holder, and the race says so; nobody is filled in from memory.

What the lists show about 2026: every North Dakota district elects its senator and both representatives in the same
year for four years, and the odd-numbered districts are up now; districts 20, 26 and 42 also elect one representative
for an unexpired 2-year term. A House race elects two members; a special one elects one. Party primaries nominate as
many as there are seats; the nonpartisan offices (the Superintendent and the courts) send twice as many on to
November. A primary is stored as a field only when its ballot named more candidates than it could send on; who
advanced is read from the November list and checked against the vote counts. Write-in votes count toward a primary's
total but are not candidates. For a two-seat primary a candidate's percentage is their share of all votes cast.

The local level (county offices and district boards), from the same November list
---------------------------------------------------------------------------------
One more search of the same page, Jurisdiction "All", returns every contest in one table (729 rows on 2026-09-30).
Its rows are cut down in memory to six cells, found by their headings: the contest title, the office, the district,
the county, the candidate's name and the party. Only that cut-down copy is kept, as JSON, in ballot_cache/nd/local/
(with the day it was fetched and the SHA-256 of the answer as it came); it is used again for a week, so a re-run
downloads nothing. The statewide, legislative and judicial rows in it are counted against the three searches above
and otherwise left alone. What is loaded from it:
  * county offices, all on the no-party ballot (N.D.C.C. 16.1-11-08): auditor, treasurer, recorder, clerk of district
    court (several counties combine them), sheriff, state's attorney, and county commissioners. The list files a
    commissioner's seat three ways: "County Commissioner" (at large), "At Large By District" (the whole county votes,
    the commissioner must live in the district, N.D.C.C. 11-07-03) and "By District" (the district's own voters
    choose, N.D.C.C. 11-11-02);
  * one supervisor of each soil conservation district (N.D.C.C. 4.1-20-18), filed under level soil_water. A district
    is a place of its own (ND-X-<county code>-<name>). The list files a contest under one county (a district lying
    in more than one takes petitions in the county where the candidate lives, N.D.C.C. 4.1-20-16); where the
    district's own name names a second county (Bowman/Slope) or the 2024 list filed the district under another
    (Stark Billings), the contest is shown for both and the race's note says why. The 2024 General Election
    Contest/Candidate List (election 333) is read once for that, the district and county cells of its soil
    conservation rows only; a district on it with no row this year (Mouse River, on 2026-09-30) goes to sl_gaps,
    since every district elects a supervisor at each general election;
  * a director of the Garrison Diversion Conservancy District in each county that elects one this year (N.D.C.C.
    61-24-03), under level other.
A row with no name is a contest the list shows with no candidate; it is kept, with a note. Each county's "County
Official Newspaper" contest is a choice between newspapers, not people, and is left out and counted. The list has no
status column (a candidate who withdrew is simply absent), no declared write-ins and no ballot order: it is
alphabetical, and the law rotates names from precinct to precinct (N.D.C.C. 16.1-06-08, 16.1-11-27).

How many an at-large commissioner contest elects is not in the list. It is read from the Secretary's results service
for the June 9 primary: the no-party ballot's "vote for no more than" number is by law the number to be elected in
November (N.D.C.C. 16.1-11-24). Two answers are read once (the contest list, and the county contests' results for the
county each was held in) and only each county contest's name, vote-for number and county are kept; no name or vote.

County names and codes come from the Census Bureau's county file the kit keeps (states_cache/census/). Cities, park
districts, school boards and townships elect at other times of the year and have nothing on this ballot; sl_notes says
so with the statutes, and sl_gaps names what is not here.

The privacy rule: only office, district, county, name, party, ballot order, status and votes are read from any file.
Nothing else is printed, logged, cached or stored; a stop names a row's number and the check it failed, never the row.
"""

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
import urllib.parse
import zipfile
import datetime as dt
from urllib.error import HTTPError
from urllib.request import Request, urlopen

if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ballot.check_local import EXTRA_SCHEMA, contact_like
from ballot.common import CACHE, HERE, fold, name_parts, party_code
from ballot.match import fits
from states import net

STATE, NAME, FIPS = "ND", "North Dakota", "38"
GENERAL, PRIMARY = "2026-11-03", "2026-06-09"
LIST_URL = "https://vip.sos.nd.gov/candidatelist.aspx?eid={}"
GEN_EID, PRI_EID = "348", "346"
API = "https://api.resultsnd.sos.nd.gov"
RESULTS_PAGE = "https://resultsnd.sos.nd.gov/"
CLIENT = "north-dakota"
FORM = "ctl00$ContentPlaceHolder1$"
JURISDICTIONS = ("SW", "LEG", "JUD")                     # the page's Statewide, Legislative and Judicial searches
ROSTER = os.path.join(HERE, "state_nd.sqlite")
CODES = {"Republican": "REP", "Democratic-NPL": "DEM", "Libertarian": "LIB", "Nonpartisan": "NP"}
NONPARTISAN = "Nonpartisan office"
SRC_GEN, SRC_PRI, SRC_RES, SRC_ROSTER = "nd-sos-2026-sl-general-list", "nd-sos-2026-sl-primary-list", "nd-sos-2026-sl-primary-results", "nd-openstates-roster-2026"

SCHEMA = """
CREATE TABLE IF NOT EXISTS sl_races (race_id TEXT PRIMARY KEY, state TEXT NOT NULL, level TEXT NOT NULL, office_kind TEXT NOT NULL, office TEXT NOT NULL, jurisdiction TEXT, jurisdiction_id TEXT, county_ids TEXT, district TEXT, seat TEXT, special INTEGER NOT NULL DEFAULT 0, partisan INTEGER NOT NULL, holder_id TEXT, holder_name TEXT, holder_party TEXT, election_date TEXT NOT NULL, note TEXT);
CREATE TABLE IF NOT EXISTS sl_candidates (race_id TEXT NOT NULL, election TEXT NOT NULL, election_date TEXT, name TEXT NOT NULL, party TEXT, party_code TEXT, ballot_order INTEGER, incumbent INTEGER NOT NULL DEFAULT 0, write_in INTEGER NOT NULL DEFAULT 0, votes INTEGER, pct REAL, outcome TEXT, state_member_id TEXT, source_id TEXT, note TEXT, PRIMARY KEY (race_id, election, name));
CREATE TABLE IF NOT EXISTS sl_sources (source_id TEXT PRIMARY KEY, state TEXT, kind TEXT, agency TEXT, title TEXT, url TEXT, published TEXT, fetched TEXT, sha256 TEXT, rows INTEGER, note TEXT);
CREATE TABLE IF NOT EXISTS sl_places (kind TEXT NOT NULL, id TEXT NOT NULL, name TEXT NOT NULL, county_ids TEXT, source_id TEXT, PRIMARY KEY (kind, id));
"""

# office as the list prints it -> (race key, office_kind, partisan); only offices North Dakota elects statewide
STATEWIDE = {
    "Governor": ("GOV", "governor", 1), "Attorney General": ("AG", "attorney_general", 1),
    "Secretary of State": ("SOS", "secretary_of_state", 1), "State Auditor": ("AUD", "state_auditor", 1),
    "State Treasurer": ("TREAS", "state_treasurer", 1), "Insurance Commissioner": ("INS", "insurance_commissioner", 1),
    "Agriculture Commissioner": ("AGR", "agriculture_commissioner", 1), "Tax Commissioner": ("TAX", "tax_commissioner", 1),
    "Public Service Commissioner": ("PSC", "public_service_commissioner", 1),
    "Superintendent of Public Instruction": ("SPI", "superintendent_of_public_instruction", 0),
}
OFFICIALS = {"attorney_general": "attorney general", "secretary_of_state": "secretary of state", "governor": "governor"}  # officials.office
JUDICIAL = {"East Central": "EC", "Northeast": "NE", "Northeast Central": "NEC", "Northwest": "NW", "South Central": "SC",
            "Southeast": "SE", "Southwest": "SW"}
FEDERAL = {"Representative in Congress", "United States Senator"}


def clean(cell):
    return re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", "", cell))).strip()


def key(name):
    """For matching one spelling of a candidate's name to another: a nickname in brackets set aside, letters only."""
    return " ".join(fold(re.sub(r"\([^)]*\)", " ", name or "")).split())


# ---------------------------------------------------------------- the candidate lists

def allowed_rows(page):
    """(title, office, district, name, party) from the search's table, cells chosen by heading; nothing else is read."""
    found = False
    for tab in re.findall(r"<table[^>]*>(.*?)</table>", page, re.S):
        heads = [clean(h) for h in re.findall(r"<th[^>]*>(.*?)</th>", tab, re.S)]
        if "Name" not in heads:
            continue
        contest = [i for i, h in enumerate(heads) if h == "Contest"]
        if len(contest) != 2 or not all(h in heads for h in ("District", "Party")):
            raise SystemExit(f"North Dakota: the candidate list's columns have changed ({heads})")
        found = True
        idx = {"title": contest[0], "office": contest[1], "district": heads.index("District"), "name": heads.index("Name"),
               "party": heads.index("Party")}
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", tab, re.S):
            cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
            if len(cells) == len(heads):
                row = {k: clean(cells[i]) for k, i in idx.items()}
                if row["name"]:
                    yield row
    if not found and "No records" not in page and "no records" not in page:
        raise SystemExit("North Dakota: the candidate list search returned no table")


def search_answer(eid, jurisdiction, election):
    """What the page's own Search returns for one jurisdiction (SW, LEG, JUD, or AL for all) of one election, as it
    comes. The answer carries contact columns, so it is never written anywhere: callers cut it down first."""
    url = LIST_URL.format(eid)
    for attempt in range(3):
        try:
            page = net.get(url).decode("utf-8", "replace")
            break
        except HTTPError as e:
            if e.code in (403, 429) and attempt < 2:
                time.sleep(20)
                continue
            raise
    if election not in page:
        raise SystemExit(f"North Dakota: the candidate list page (election {eid}) is no longer the {election}")
    if f'value="{jurisdiction}"' not in page:
        raise SystemExit(f"North Dakota: the candidate list no longer offers the jurisdiction {jurisdiction}")
    fields = {m.group(1): H.unescape(m.group(2)) for m in re.finditer(r'<input type="hidden" name="([^"]+)" id="[^"]*" value="([^"]*)"', page)}
    fields.update({FORM + "ddlJursdiction": jurisdiction, FORM + "ddlDistrict": "0", FORM + "ddlContest": "0",
                   FORM + "ddlCandidate": "0", FORM + "btnSearch": "Search"})
    time.sleep(1.0)
    req = Request(url, data=urllib.parse.urlencode(fields).encode(), method="POST",
                  headers={"User-Agent": net.UA, "Content-Type": "application/x-www-form-urlencoded", "Referer": url})
    with urlopen(req, timeout=120) as r:
        return r.read()


def search(eid, jurisdiction, election):
    """Every candidate in one jurisdiction (SW, LEG, JUD) of one election, through the page's own Search."""
    answer = search_answer(eid, jurisdiction, election).decode("utf-8", "replace")
    if "Page$" in answer:
        raise SystemExit("North Dakota: the candidate list now comes in pages; the loader reads only one")
    return [dict(r, jurisdiction=jurisdiction) for r in allowed_rows(answer)]


def candidate_list(cache, eid, election, keep, say=print):
    """The five allowed columns of every Statewide, Legislative and Judicial candidate, as JSON on disk. keep=True: the
    copy on disk is used as it is (the primary is over); otherwise the list is asked for afresh, and the copy on disk is
    used only when the site cannot be reached."""
    path = os.path.join(cache, "nd", f"nd_2026_sl_{'primary' if eid == PRI_EID else 'general'}_list.json")
    if keep and os.path.exists(path):
        return path, json.load(open(path, encoding="utf-8"))
    try:
        rows = []
        for j in JURISDICTIONS:
            rows += search(eid, j, election)
            time.sleep(1.0)
    except SystemExit:
        raise
    except Exception as err:  # noqa: BLE001  unreachable: fall back to the copy on disk, and say so
        if os.path.exists(path):
            say(f"      North Dakota: the candidate list (election {eid}) did not answer ({err}); using the copy on disk")
            return path, json.load(open(path, encoding="utf-8"))
        raise
    if not rows:
        raise SystemExit(f"North Dakota: the candidate list (election {eid}) returned no candidates")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(rows, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return path, rows


# ---------------------------------------------------------------- races

def race_for(row):
    """The race a list row belongs to, or None for a federal office. Raises for an office this loader does not know."""
    office, title, district = row["office"], row["title"], row["district"]
    if office in FEDERAL:
        return None
    term = re.search(r"Unexpired (\d+)-Year Term", title)
    special = 1 if term else 0
    unexpired = f"Unexpired {term.group(1)}-year term" if term else ""
    if office in ("State Senator", "State Representative"):
        m = re.fullmatch(r"District 0*(\d+)([A-Z]?)", district)
        if not m:
            raise SystemExit(f"North Dakota: a legislative district written \"{district}\" is not understood")
        d = m.group(1) + m.group(2)
        senate = office == "State Senator"
        seats = 1 if (senate or special or m.group(2)) else 2
        note = ("One seat." if seats == 1 else "Two seats: the district elects two representatives, and the two candidates "
                "with the most votes win.")
        if special:
            note = f"{unexpired}, as the Secretary of State's list titles it: one of the district's two House seats."
        return {"race_id": f"2026-{STATE}-{'SS' if senate else 'SH'}{d}", "level": "legislature",
                "office_kind": "state_senate" if senate else "state_house", "office": office,
                "jurisdiction": f"Legislative District {d}", "jurisdiction_id": d, "district": d, "seat": None,
                "special": special, "partisan": 1, "seats": seats, "chamber": "Senate" if senate else "House", "note": note}
    if office in STATEWIDE:
        k, kind, partisan = STATEWIDE[office]
        return {"race_id": f"2026-{STATE}-{k}" + ("-UNEXP" if special else ""), "level": "statewide", "office_kind": kind,
                "office": office, "jurisdiction": NAME, "jurisdiction_id": FIPS, "district": None, "seat": None,
                "special": special, "partisan": partisan, "seats": 1, "chamber": None,
                "note": (unexpired + ", as the Secretary of State's list titles it." if special else None)}
    if office == "Justice of the Supreme Court":
        return {"race_id": f"2026-{STATE}-SUPREME" + ("-UNEXP" if special else ""), "level": "court", "office_kind": "supreme_court",
                "office": office, "jurisdiction": NAME, "jurisdiction_id": FIPS, "district": None, "seat": None,
                "special": special, "partisan": 0, "seats": 1, "chamber": None,
                "note": (unexpired + ", as the Secretary of State's list titles it." if special else None)}
    m = re.fullmatch(r"Judge of the District Court No\. (\d+)", office)
    if m:
        jd = JUDICIAL.get(district) or re.sub(r"[^A-Z]", "", district.title())
        if not district:
            raise SystemExit(f"North Dakota: {office} is listed without its judicial district")
        return {"race_id": f"2026-{STATE}-DC-{jd}-{m.group(1)}" + ("-UNEXP" if special else ""), "level": "court",
                "office_kind": "district_court", "office": "Judge of the District Court", "jurisdiction": f"{district} Judicial District",
                "jurisdiction_id": f"{STATE}-{jd}", "district": district, "seat": f"No. {m.group(1)}", "special": special,
                "partisan": 0, "seats": 1, "chamber": None, "place": ("judicial_district", f"{STATE}-{jd}", f"{district} Judicial District"),
                "note": (unexpired + ", as the Secretary of State's list titles it." if special else None)}
    raise SystemExit(f"North Dakota: the list names an office this loader does not know: \"{office}\" ({title})")


def results_name(row):
    """The results service's name for a primary contest: the list's title with a space before the district, then the
    party for a party primary ("State Representative District 01 Republican")."""
    title, district = row["title"], row["district"]
    if district and title.endswith(district):
        title = title[: -len(district)].strip() + " " + district
    party = row["party"]
    return " ".join((title + ("" if party == "Nonpartisan" else " " + party)).split())


# ---------------------------------------------------------------- who holds each seat

def roster(path=ROSTER):
    """Sitting legislators and statewide officials: id, name, party and start date only."""
    if not os.path.exists(path):
        return [], []
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    members = [dict(zip(("id", "chamber", "district", "first", "last", "full", "party", "start"), r)) for r in con.execute(
        "SELECT bioguide_id, chamber, district, first_name, last_name, official_full, party_name, term_start "
        "FROM legislators WHERE is_current = 1")]
    officials = [dict(zip(("id", "office", "first", "last", "full", "party"), r)) for r in con.execute(
        "SELECT bioguide_id, office, first_name, last_name, official_full, party_name FROM officials")]
    con.close()
    return members, officials


def member_parts(m):
    return [w for w in fold(m["first"]).split()], " ".join(fold(m["last"]).split())


def one_fit(name, people):
    """The one person the name fits, else None."""
    parts = name_parts(name)
    hits = [p for p in people if fits(parts, member_parts(p)) or fits(parts, name_parts(p["full"]))]
    return hits[0] if len(hits) == 1 else None


def holders(race, members, officials):
    """The sitting member(s) of the seat. A special election's seat is the one whose member joined mid-term (a start
    other than the 1 December after an election); when that cannot be told, both of the district's members are given."""
    if race["chamber"]:
        people = [m for m in members if m["chamber"] == race["chamber"] and m["district"] == race["district"]]
        if race["special"]:
            mid = [m for m in people if not (m["start"] or "").endswith("-12-01")]
            if len(mid) == 1:
                people = mid
        return sorted(people, key=lambda m: m["last"]), people
    office = OFFICIALS.get(race["office_kind"])
    held = [o for o in officials if office and o["office"] == office]
    return held, held


# ---------------------------------------------------------------- the primary results

def ask(what, **params):
    time.sleep(1.0)
    return json.loads(net.get(f"{API}/{what}?" + urllib.parse.urlencode(params), accept="application/json"))


def primary_results(cache, wanted, say=print):
    """Official statewide totals of the primary contests named in `wanted`, kept on disk once the service calls them
    official. Returns (path, results) or (None, None) when the service cannot be reached and nothing is on disk."""
    path = os.path.join(cache, "nd", "nd_2026_sl_primary_results.json")      # statewide totals only
    if os.path.exists(path):
        kept = json.load(open(path, encoding="utf-8"))
        if kept.get("official") and set(wanted) <= set(kept["contests"]):
            return path, kept
    try:
        info = ask("Election/GetElectionInfo", cId=CLIENT, electionID=PRI_EID)
        e = info["response"]
        if e["name"] != "2026 Primary Election" or not str(e["date"]).startswith(PRIMARY):
            raise SystemExit(f"North Dakota: results election {PRI_EID} is {e['name']} of {e['date']}, not the June 9, 2026 primary")
        listing = ask("Contest/GetContestSearchList", cid=CLIENT, electionID=PRI_EID)["response"]["contests"]
        kept = {"election": e["name"], "date": str(e["date"])[:10], "official": bool(info.get("isOfficial")),
                "last_updated": info.get("lastUpdated"), "contests": {}}
        by_id = {cid: c for cid, c in listing.items() if " ".join(c["contestName"].split()) in wanted}
        for ctype in sorted({c["contestTypeCode"] for c in by_id.values()}):
            res = ask("Contest/GetContestResults", cId=CLIENT, electionID=PRI_EID, contestType=ctype)
            kept["official"] = kept["official"] and bool(res.get("isOfficial"))
            answered = res["response"]["contests"]
            for r in (answered.values() if isinstance(answered, dict) else answered):
                c = by_id.get(r["contestID"])
                if not c:
                    continue
                names = {str(k): " ".join(ch["name"].split()) for k, ch in c["choices"].items()}
                choices = [{"name": names[str(ch["choiceID"])], "votes": int(ch["totalVotes"]),
                            "write_in": bool(c["choices"][str(ch["choiceID"])].get("isWriteIn")) or key(names[str(ch["choiceID"])]) == "write in"}
                           for ch in r["choices"]]
                extra = sum(int(w.get("totalVotes") or 0) for w in (r.get("writeInChoices") or r.get("writeinChoices") or []))
                if sum(ch["votes"] for ch in choices) + extra != int(r["totalVotes"]):
                    raise SystemExit(f"North Dakota: the choices of {c['contestName']} do not add up to its total ({r['totalVotes']})")
                kept["contests"][" ".join(c["contestName"].split())] = {
                    "id": r["contestID"], "vote_for": int(c.get("voteFor") or 1), "total": int(r["totalVotes"]),
                    "write_in_listed": extra, "precincts": f"{r['precinctsReporting']} of {r['totalPrecincts']}", "choices": choices}
    except SystemExit:
        raise
    except Exception as err:  # noqa: BLE001  the service unreachable or changed: say so and fall back to what is on disk
        if os.path.exists(path):
            say(f"      North Dakota: the results service did not answer ({err}); using the copy on disk")
            return path, json.load(open(path, encoding="utf-8"))
        say(f"      North Dakota: the results service did not answer ({err}); primary fields are stored without votes")
        return None, None
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(kept, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return path, kept


# ---------------------------------------------------------------- the local level: county offices and district boards

LOCAL_LIST_SRC, COUNTY_SRC = "nd-sos-2026-local-general-list", "nd-census-2024-counties"
JUNE_LIST_SRC, JUNE_RES_SRC = "nd-sos-2026-primary-contest-list", "nd-sos-2026-primary-county-results"
PRIOR_EID, PRIOR_ELECTION, PRIOR_SRC = "333", "2024 General Election", "nd-sos-2024-general-list-soil"      # the last general election's list
COUNTY_ZIP = os.path.join(HERE, "states_cache", "census", "cb_2024_us_county_500k.zip")
COUNTY_URL = "https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_county_500k.zip"
CODE_URL = "https://ndlegis.gov/general-information/north-dakota-century-code"
LOCAL_MAX_AGE_DAYS = 7                                                        # the cut-down list is used again for a week
LOCAL_KEEP = ("title", "office", "district", "county", "name", "party")      # the only cells of a row ever taken

# office as the list prints it -> office_kind (the office keeps the list's own words)
COUNTY_OFFICES = {
    "County Auditor": "county_auditor", "County Auditor/Treasurer": "county_auditor_treasurer", "County Treasurer": "county_treasurer",
    "County Recorder": "county_recorder", "County Clerk of District Court": "clerk_of_court",
    "County Recorder/Clerk of District Court": "county_recorder_clerk_of_court", "County Treasurer/Recorder": "county_treasurer_recorder",
    "County Treasurer/Recorder/Clerk of District Court": "county_treasurer_recorder_clerk_of_court",
    "County Sheriff": "sheriff", "County State's Attorney": "county_attorney",
}
# the three ways the list files a commissioner's seat (N.D.C.C. 11-07-03, 11-07-06, 11-11-02)
COMMISSIONER = {"County Commissioner": "at large", "County Commissioner At Large By District": "at large by district",
                "County Commissioner By District": "by district"}
SOIL, GARRISON, NEWSPAPER = "Supervisor, Soil Conservation District", "Director, Garrison Diversion Conservancy", "County Official Newspaper"
SOIL_KIND, AT_LARGE = "Soil Conservation District", "Districts At-Large"
GARRISON_NAME, GARRISON_ID = "Garrison Diversion Conservancy District", f"{STATE}-X-garrison-diversion-conservancy-district"      # N.D.C.C. 61-24-02
NUMBER = "no one two three four five six seven eight nine ten".split()
# the page builder's own last check is a little wider than the trial check's (it also stops at Court and Place)
BUILDER_STREET = re.compile(r"\b\d{1,6}\s+(?:[NSEW]\.?\s+)?[A-Za-z0-9.' -]{1,40}?\s(?:St|Street|Ave|Avenue|Rd|Road|Blvd|Boulevard|Dr|Drive|Ln|Lane|Way|Ct|Court|"
                            r"Cir|Circle|Pkwy|Parkway|Hwy|Highway|Trl|Trail|Pl|Place|Ter|Terrace)\b\.?", re.I)


def state_office(office):
    """An office the state-level part of this loader (or the federal loader) handles."""
    return (office in STATEWIDE or office in FEDERAL or office in ("State Senator", "State Representative", "Justice of the Supreme Court")
            or bool(re.fullmatch(r"Judge of the District Court No\. \d+", office)))


def slug(text):
    """Letters, digits and hyphens, for ids: "Bowman/Slope Soil Conservation District" -> bowman-slope-soil-conservation-district."""
    t = unicodedata.normalize("NFKD", text or "")
    return re.sub(r"[^a-z0-9]+", "-", "".join(ch for ch in t if not unicodedata.combining(ch)).lower()).strip("-")


def contest_words(text):
    """Contest words for a stop message, and only when they are plainly contest words (letters, spaces, a few marks)."""
    return f"\"{text}\"" if re.fullmatch(r"[A-Za-z ,/'.-]{1,80}", text or "") else "its words are not shown"


def and_names(items):
    items = list(items)
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def local_allowed_rows(page, keep=LOCAL_KEEP):
    """Six cells of every row of the search's table (contest title, office, district, county, name, party), or the ones
    of them named in `keep`, chosen by their headings; no other cell is read. A row with no name is a contest the list
    shows with no candidate."""
    out = []
    for tab in re.findall(r"<table[^>]*>(.*?)</table>", page, re.S):
        heads = [clean(h) for h in re.findall(r"<th[^>]*>(.*?)</th>", tab, re.S)]
        if "Name" not in heads:
            continue
        contest = [i for i, h in enumerate(heads) if h == "Contest"]
        if len(contest) != 2 or any(heads.count(h) != 1 for h in ("District", "County", "Name", "Party")):
            raise SystemExit("North Dakota: the candidate list's columns have changed (Contest twice, and District, County, Name and Party once each, are not all there)")
        idx = {"title": contest[0], "office": contest[1], "district": heads.index("District"), "county": heads.index("County"),
               "name": heads.index("Name"), "party": heads.index("Party")}
        for n, tr in enumerate(re.findall(r"<tr[^>]*>(.*?)</tr>", tab, re.S)):
            cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
            if not cells:
                continue                                    # the row of headings
            if len(cells) != len(heads):
                raise SystemExit(f"North Dakota: row {n} of the candidate list has {len(cells)} cells, not the {len(heads)} its headings name; stopping (the row is not printed)")
            out.append({k: clean(cells[idx[k]]) for k in keep})
    if not out:
        raise SystemExit("North Dakota: the candidate list search (all contests) returned no table")
    return out


def local_list(folder, say=print, refresh=False):
    """Every row of the November list's "All" search, cut down in memory to the six allowed cells and kept as JSON with
    the day it was fetched and the fingerprint of the answer as it came. The copy on disk is used again for a week (and
    whenever the site cannot be reached); refresh=True asks afresh. Returns (path, kept)."""
    path = os.path.join(folder, "nd_2026_local_general_list.json")
    old = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else None
    if old and not refresh and (dt.date.today() - dt.date.fromisoformat(old["fetched"])).days < LOCAL_MAX_AGE_DAYS:
        return path, old
    try:
        time.sleep(1.0)                                     # one request at a time, a second apart
        raw = search_answer(GEN_EID, "AL", "2026 General Election")
        answer = raw.decode("utf-8", "replace")
        if "Page$" in answer:
            raise SystemExit("North Dakota: the candidate list now comes in pages; the loader reads only one")
        kept = {"title": "2026 General Election Contest/Candidate List", "url": LIST_URL.format(GEN_EID), "asked": "the page's own Search, Jurisdiction: All",
                "fetched": dt.date.today().isoformat(), "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw), "columns": list(LOCAL_KEEP),
                "rows": local_allowed_rows(answer)}
        del raw, answer
    except SystemExit:
        raise
    except Exception as err:  # noqa: BLE001  unreachable: fall back to the copy on disk, and say so
        if old:
            say(f"      North Dakota: the candidate list (all contests) did not answer ({err}); using the copy of {old['fetched']} on disk")
            return path, old
        raise
    os.makedirs(folder, exist_ok=True)
    with open(path + ".part", "w", encoding="utf-8") as fh:
        json.dump(kept, fh, ensure_ascii=False, indent=1)
    os.replace(path + ".part", path)
    return path, kept


def prior_soil(folder, say=print):
    """The soil conservation districts on the 2024 General Election Contest/Candidate List and the county each was
    filed under: three cells of each row are read (office, district, county) and only the district and county of the
    soil conservation rows are kept; no name is read. Two uses. A district lies where its candidates live (a petition
    is filed "with the county auditor of the county where the candidate resides", N.D.C.C. 4.1-20-16), so a district
    filed under another county in 2024 reaches that county too. And every district elects a supervisor at each general
    election (N.D.C.C. 4.1-20-18), so a district on the 2024 list with no row this year is named in sl_gaps. Asked once:
    2024 is over. Returns (path, kept), or (None, None) when that list cannot be read."""
    path = os.path.join(folder, "nd_2024_general_soil_districts.json")
    if os.path.exists(path):
        return path, json.load(open(path, encoding="utf-8"))
    try:
        time.sleep(1.0)
        raw = search_answer(PRIOR_EID, "AL", PRIOR_ELECTION)
        answer = raw.decode("utf-8", "replace")
        if "Page$" in answer:
            raise ValueError("it now comes in pages")
        pairs = sorted({(r["district"], r["county"]) for r in local_allowed_rows(answer, keep=("office", "district", "county")) if r["office"] == SOIL})
        if not pairs:
            raise ValueError("it names no soil conservation district")
        kept = {"title": "2024 General Election Contest/Candidate List", "url": LIST_URL.format(PRIOR_EID), "asked": "the page's own Search, Jurisdiction: All",
                "fetched": dt.date.today().isoformat(), "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw),
                "kept": "the district and county cells of the soil conservation rows; no name", "districts": [{"district": d, "county": c} for d, c in pairs]}
        del raw, answer
    except (SystemExit, Exception) as err:  # noqa: BLE001  a check only: without it the loader goes on, and says so
        say(f"      North Dakota: the 2024 list could not be read ({err}); this year's soil conservation districts are not checked against it")
        return None, None
    os.makedirs(folder, exist_ok=True)
    with open(path + ".part", "w", encoding="utf-8") as fh:
        json.dump(kept, fh, ensure_ascii=False, indent=1)
    os.replace(path + ".part", path)
    return path, kept


def ask_bytes(what, **params):
    """One answer of the results service as it came (for its fingerprint), with its address."""
    url = f"{API}/{what}?" + urllib.parse.urlencode(params)
    time.sleep(1.0)
    return url, net.get(url, accept="application/json")


def june_contests(folder, say=print):
    """The county contests of the June 9 primary, from the Secretary's results service: each contest's name, the number
    its ballot said to vote for, and the county it was held in. On the no-party ballot that number "must be the number
    to be elected to the office at the next succeeding general election" (N.D.C.C. 16.1-11-24), which is how the seats
    of an at-large commissioner contest are known. No candidate's name and no vote is kept. Asked once: the primary is
    over and its results are official. Returns (path, kept), or (None, None) when the service cannot be read."""
    path = os.path.join(folder, "nd_2026_primary_county_contests.json")
    old = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else None
    if old and old.get("official"):
        return path, old
    try:
        info = ask("Election/GetElectionInfo", cId=CLIENT, electionID=PRI_EID)
        e = info["response"]
        if e["name"] != "2026 Primary Election" or not str(e["date"]).startswith(PRIMARY):
            raise ValueError(f"results election {PRI_EID} is not the June 9, 2026 primary")
        list_url, raw_list = ask_bytes("Contest/GetContestSearchList", cid=CLIENT, electionID=PRI_EID)
        res_url, raw_res = ask_bytes("Contest/GetContestResults", cId=CLIENT, electionID=PRI_EID, contestType="CW")
        listing, res = json.loads(raw_list), json.loads(raw_res)
        named = {str(cid): (" ".join(c["contestName"].split()), int(c.get("voteFor") or 0))
                 for cid, c in listing["response"]["contests"].items() if c.get("contestTypeCode") == "CW"}
        answered = res["response"]["contests"]
        contests = []
        for r in (answered.values() if isinstance(answered, dict) else answered):
            hit, where = named.get(str(r["contestID"])), [str(k) for k in (r.get("locations") or {})]
            if not hit or hit[1] < 1 or len(where) != 1 or not re.fullmatch(FIPS + r"\d{3}", where[0]):
                raise ValueError("a June county contest without a name, a vote-for number or exactly one county")
            contests.append({"name": hit[0], "vote_for": hit[1], "county": where[0]})
        if len(contests) != len(named) or len({(c["county"], c["name"]) for c in contests}) != len(contests):
            raise ValueError("the June county contests do not pair off one to one between the contest list and the results")
        kept = {"election": e["name"], "date": str(e["date"])[:10],
                "official": bool(info.get("isOfficial")) and bool(listing.get("isOfficial")) and bool(res.get("isOfficial")),
                "last_updated": info.get("lastUpdated"), "fetched": dt.date.today().isoformat(),
                "list": {"url": list_url, "sha256": hashlib.sha256(raw_list).hexdigest(), "bytes": len(raw_list)},
                "results": {"url": res_url, "sha256": hashlib.sha256(raw_res).hexdigest(), "bytes": len(raw_res)},
                "kept": "each county contest's name, vote-for number and county; no candidate's name, no vote",
                "contests": sorted(contests, key=lambda c: (c["county"], c["name"]))}
        del raw_list, raw_res, listing, res, answered
    except Exception as err:  # noqa: BLE001  the service unreachable or changed: say so and go on without the seat counts
        if old:
            say(f"      North Dakota: the results service did not answer ({err}); using the copy on disk for the June vote-for numbers")
            return path, old
        say(f"      North Dakota: the results service could not be read ({err}); at-large contests are stored without the number of seats")
        return None, None
    os.makedirs(folder, exist_ok=True)
    with open(path + ".part", "w", encoding="utf-8") as fh:
        json.dump(kept, fh, ensure_ascii=False, indent=1)
    os.replace(path + ".part", path)
    return path, kept


def census_counties(say=print):
    """{county name: (five-digit code, name with its kind word)} for North Dakota, from the attribute table of the
    Census Bureau's county file the kit keeps (no shapes are read)."""
    if not os.path.exists(COUNTY_ZIP):
        net.download(COUNTY_URL, COUNTY_ZIP, 3650, say=say)
    import shapefile                                        # pyshp
    z = zipfile.ZipFile(COUNTY_ZIP)
    dbf = [n for n in z.namelist() if n.lower().endswith(".dbf")]
    if len(dbf) != 1:
        raise SystemExit("North Dakota: the Census county file does not hold exactly one attribute table")
    out = {}
    for rec in shapefile.Reader(dbf=io.BytesIO(z.read(dbf[0]))).iterRecords():
        d = rec.as_dict()
        if str(d.get("STATEFP")) == FIPS:
            out[str(d["NAME"])] = (str(d["GEOID"]), str(d["NAMELSAD"]))
    if len(out) != 53 or any(not re.fullmatch(FIPS + r"\d{3}", f) for f, _full in out.values()):
        raise SystemExit(f"North Dakota: the Census county file gives {len(out)} counties for the state, not 53")
    return out


def soil_name(district):
    """A soil conservation district's name with its kind word. The list writes all but two as "... Soil Conservation
    District"; the two it writes another way ("... Soil Conservation County", "... District") are given the kind word
    the list's own office column uses, and the race's note quotes the list. Returns (name, the list's wording where it
    differs), or (None, ...) for a wording this loader does not know."""
    d = " ".join((district or "").split())
    if d.endswith(" " + SOIL_KIND):
        return d, None
    if d.endswith(" Soil Conservation County"):
        return d[: -len("County")] + "District", d
    if d.endswith(" District"):
        return d[: -len("District")].rstrip() + " " + SOIL_KIND, d
    return None, d


def counties_named(stem, counties):
    """The counties a district's own name names (Bowman/Slope, Stark Billings, Adams County), longest names first so
    that a two-word county (Grand Forks, Golden Valley) is read whole."""
    found, rest = set(), stem
    for cname in sorted(counties, key=len, reverse=True):
        pat = r"(?<![A-Za-z])" + re.escape(cname) + r"(?![A-Za-z])"
        if re.search(pat, rest):
            found.add(counties[cname][0])
            rest = re.sub(pat, " ", rest)
    return found


def local_level(folder, say=print, refresh=False):
    """North Dakota's county and district contests on the November list, as rows ready to write (races, candidates,
    places, sources, gaps, notes) with the counts behind them. Nothing here touches the database."""
    _lpath, kept = local_list(folder, say, refresh)
    rows = kept["rows"]
    counties = census_counties(say)
    by_fold = {fold(n).replace(" ", ""): (f, n, full) for n, (f, full) in counties.items()}
    full_name = {f: full for f, full in counties.values()}
    _jpath, june = june_contests(folder, say)
    vote_for = {(c["county"], c["name"]): c["vote_for"] for c in june["contests"]} if june else {}

    def place_of(row, n):
        hit = by_fold.get(fold(row["county"]).replace(" ", ""))
        if not hit:
            raise SystemExit(f"North Dakota: row {n} of the candidate list names a county the Census Bureau's county file does not have; stopping (the row is not printed)")
        return hit

    soil_filed = {}                                        # a soil district's name -> the counties the list files it under
    for n, row in enumerate(rows, 1):
        if row["office"] == SOIL:
            name, _said = soil_name(row["district"])
            if not name:
                raise SystemExit(f"North Dakota: row {n} of the candidate list writes a soil conservation district in a way this loader does not know; stopping")
            soil_filed.setdefault(name, set()).add(place_of(row, n)[0])
    problems = []
    _ppath, prior = prior_soil(folder, say)
    prior_filed = {}                                       # the same for the 2024 list
    for d in (prior or {}).get("districts", []):
        name, hit = soil_name(d["district"])[0], by_fold.get(fold(d["county"]).replace(" ", ""))
        if name and hit:
            prior_filed.setdefault(name, set()).add(hit[0])
        else:
            problems.append("the 2024 list names a soil conservation district or a county this loader cannot read; that row is not used")

    contests, counts, newspapers = {}, {"state": 0, "newspaper": 0, "people": 0, "empty": 0}, set()
    for n, row in enumerate(rows, 1):
        office, title, district = row["office"], row["title"], row["district"]
        if row["county"] == "STATE" or state_office(office):
            if not (row["county"] == "STATE" and state_office(office)):
                raise SystemExit(f"North Dakota: row {n} of the candidate list pairs a statewide office with a county, or a county office with none; stopping")
            counts["state"] += 1
            continue
        fips, _cname, cfull = place_of(row, n)
        if office == NEWSPAPER:                             # a choice between newspapers, not people: counted and left out
            counts["newspaper"] += 1
            newspapers.add(fips)
            continue
        if district and not title.endswith(district):
            raise SystemExit(f"North Dakota: row {n} of the candidate list: the contest title does not end with its district; stopping")
        term = re.search(r"Unexpired (\d+)-Year Term", title)
        c = {"special": 1 if term else 0, "county": fips, "county_name": cfull, "names": [], "empty": 0, "notes": [], "june": None, "at_large": False,
             "said": None, "filed": {fips}, "named": set(), "prior": set(),
             "unexpired": f"Unexpired {term.group(1)}-year term, as the Secretary of State's list titles it." if term else None}
        if office in COUNTY_OFFICES:
            if district:
                raise SystemExit(f"North Dakota: row {n} of the candidate list gives a district to a countywide office ({contest_words(office)}); stopping")
            kind = COUNTY_OFFICES[office]
            c.update(level="county", office_kind=kind, office=office, jurisdiction=cfull, jurisdiction_id=fips, counties={fips}, district=None, seat=None,
                     race_id=f"2026-{STATE}-{fips}-{kind.replace('_', '-')}", june=f"{title} {row['county']}")
        elif office in COMMISSIONER:
            how, m = COMMISSIONER[office], re.fullmatch(r"District (\d+)", district)
            if m and how == "at large by district":
                c["notes"].append("Filed as \"At Large By District\" in the Secretary of State's list: every voter in the county votes on this seat, "
                                  "and the commissioner must live in the district.")
            elif m and how == "by district":
                c["notes"].append("Filed as \"By District\" in the Secretary of State's list: the voters of this commissioner district choose the commissioner.")
            elif district == AT_LARGE:
                c["notes"].append(f"The Secretary of State's list files this contest as \"{office}\", district \"{AT_LARGE}\".")
            elif district or how != "at large":
                raise SystemExit(f"North Dakota: row {n} of the candidate list: a county commissioner's district this loader does not know; stopping")
            suffix = f"-D{int(m.group(1))}" if m else "-AL" if district == AT_LARGE else ""
            c.update(level="county", office_kind="county_commissioner", office="County Commissioner", jurisdiction=cfull, jurisdiction_id=fips, counties={fips},
                     district=district if m else None, seat="At Large" if district == AT_LARGE else None, at_large=not m,
                     race_id=f"2026-{STATE}-{fips}-county-commissioner{suffix}",
                     june=(title[: -len(district)].strip() + " " + district) if district else f"{title} {row['county']}")
        elif office == SOIL:
            name, said = soil_name(district)
            filed, named, before = soil_filed[name], counties_named(name[: -len(SOIL_KIND)].strip(), counties), prior_filed.get(name, set())
            key = f"{min(filed)[2:]}-{slug(name)}"
            c.update(level="soil_water", office_kind="soil_water", office=office, jurisdiction=name, jurisdiction_id=f"{STATE}-X-{key}",
                     counties=set(filed) | named | before, district=None, seat=None,
                     race_id=f"2026-{STATE}-X-{key}-soil-water", said=said, filed=set(filed), named=named, prior=set(before))
        elif office == GARRISON:
            if district:
                raise SystemExit(f"North Dakota: row {n} of the candidate list gives a district to a Garrison Diversion director; stopping")
            c.update(level="other", office_kind="water_board", office=office, jurisdiction=GARRISON_NAME, jurisdiction_id=GARRISON_ID, counties={fips},
                     district=cfull, seat=None, race_id=f"2026-{GARRISON_ID}-water-board-{fips[2:]}", june=f"{title} {row['county']}")
            c["notes"].append(f"Each county in the district elects its own director; this seat is chosen by the voters of {cfull}.")
        else:
            raise SystemExit(f"North Dakota: row {n} of the candidate list names a county-level office this loader does not know ({contest_words(office)}); stopping")
        if c["special"]:
            c["race_id"] += "-S"
        rid = c["race_id"]
        have = contests.setdefault(rid, c)
        same = ("office", "jurisdiction", "jurisdiction_id", "district", "seat", "unexpired")
        if have is not c and any(have[k] != c[k] for k in same):
            raise SystemExit(f"North Dakota: two different contests share the race id {rid}; stopping")
        if row["name"]:
            if row["party"] != "Nonpartisan":
                raise SystemExit(f"North Dakota: row {n} of the candidate list: a county-level candidate whose party cell is not \"Nonpartisan\"; stopping")
            if row["name"] in have["names"]:
                raise SystemExit(f"North Dakota: row {n} of the candidate list repeats a name already in {rid}; stopping")
            have["names"].append(row["name"])
            counts["people"] += 1
        else:
            if row["party"]:
                raise SystemExit(f"North Dakota: row {n} of the candidate list has a party but no name; stopping")
            have["empty"] += 1
            counts["empty"] += 1

    races, cands, gaps, seats_known = [], [], [], 0
    for rid, c in sorted(contests.items()):
        n, notes = len(c["names"]), ([c["unexpired"]] if c["unexpired"] else []) + c["notes"]
        seats = vote_for.get((c["county"], " ".join(c["june"].split()))) if c["june"] else None
        if seats:
            seats_known += 1
            if seats > 1:
                notes.append(f"Voters choose {NUMBER[seats] if seats < len(NUMBER) else seats}.")
            if n > 2 * seats:
                problems.append(f"{rid}: {n} candidates on the November list for {seats} to elect, more than twice as many")
        elif c["at_large"] and june:
            gaps.append((STATE, "race", rid, c["county_name"], "how many commissioners this contest elects",
                         "The Secretary of State's list does not say how many are elected, and this contest was not on the June 9 no-party ballot, "
                         "whose vote-for number tells it for the other at-large contests.", LIST_URL.format(GEN_EID)))
        if c["empty"] and n:
            problems.append(f"{rid}: listed both with a candidate and with an empty row")
        if c["empty"] > 1:
            problems.append(f"{rid}: {c['empty']} rows with no name")
        if not n:
            notes.append("The Secretary of State's list shows this contest with no candidate named.")
        if c["said"]:
            notes.append(f"The Secretary of State's list prints this district's name as \"{c['said']}\".")
        for f in sorted(c["counties"] - c["filed"]):        # a second county, and how it is known
            why = and_names((["which the district's name names"] if f in c["named"] else [])
                            + (["under which the 2024 list filed the district"] if f in c["prior"] else []))
            notes.append(f"The Secretary of State's list files this contest under {and_names(full_name[x] for x in sorted(c['filed']))}; it is shown for "
                         f"{full_name[f]} too, {why}.")
        races.append((rid, STATE, c["level"], c["office_kind"], c["office"], c["jurisdiction"], c["jurisdiction_id"], json.dumps(sorted(c["counties"])),
                      c["district"], c["seat"], c["special"], 0, None, None, None, GENERAL, " ".join(notes) or None))
        cands += [(rid, "general", GENERAL, name, NONPARTISAN, "N", None, 0, 0, None, None, None, None, LOCAL_LIST_SRC, None) for name in sorted(c["names"])]

    # counts: every row of the table is a statewide row, a newspaper, a candidate or an empty contest, and every candidate is in one race
    n_local = len(rows) - counts["state"]
    if n_local != counts["newspaper"] + counts["people"] + counts["empty"] or len(cands) != counts["people"]:
        raise SystemExit(f"North Dakota: {n_local} county-level rows read, {counts['newspaper'] + counts['people'] + counts['empty']} accounted for and "
                         f"{len(cands)} candidates stored for {counts['people']} named rows; stopping")
    if len({(c[0], c[3]) for c in cands}) != len(cands):
        raise SystemExit("North Dakota: a candidate is stored twice in one county-level race; stopping")

    by_level, by_kind = {}, {}
    for r in races:
        by_level[r[2]] = by_level.get(r[2], 0) + 1
        by_kind[r[3]] = by_kind.get(r[3], 0) + 1
    reached = {f for r in races for f in json.loads(r[7])}
    garrison = sorted({c["county"] for c in contests.values() if c["level"] == "other"})
    soil = {}
    for c in contests.values():
        if c["level"] == "soil_water":
            soil.setdefault(c["jurisdiction_id"], [c["jurisdiction"], set()])[1].update(c["counties"])
    by_name = [f"{name} ({and_names(full_name[f] for f in sorted(cs - soil_filed[name]))})" for _pid, (name, cs) in sorted(soil.items()) if cs - soil_filed[name]]
    # a district on the 2024 list with no row this year: every district elects a supervisor at each general election, so it is named as a gap
    missing = sorted((name, f) for name, fs in prior_filed.items() if name not in soil_filed for f in fs)

    places = [("county", f, full, json.dumps([f]), COUNTY_SRC) for f, full in sorted(full_name.items())]
    places += [("special", pid, name, json.dumps(sorted(cs)), LOCAL_LIST_SRC) for pid, (name, cs) in sorted(soil.items())]
    if garrison:
        places.append(("special", GARRISON_ID, GARRISON_NAME, json.dumps(garrison), LOCAL_LIST_SRC))

    url = LIST_URL.format(GEN_EID)
    gaps.append((STATE, "state", STATE, NAME, "special city, school or park district elections",
                 "Cities, park districts and school boards hold their regular elections in spring and June, and the Secretary of State's November list names no "
                 "contest for any of them; a special election one of them calls for November 3 is not on that list and would have to be read from the notice of "
                 "the county auditor or of the city or district itself.", url))
    if not june:
        gaps.append((STATE, "state", STATE, NAME, "how many commissioners an at-large contest elects",
                     "The Secretary of State's list does not say how many are elected; the number comes from the June 9 no-party ballot in the Secretary's results "
                     "service, which could not be read on this run.", RESULTS_PAGE))
    for name, f in missing:
        gaps.append((STATE, "county", f, full_name[f], f"supervisor of the {name}",
                     f"The Secretary of State's 2024 general election list had a contest for this district, filed under {full_name[f]}, and state law has every "
                     "soil conservation district elect a supervisor at each general election; this year's list has no row for the district, with or without a "
                     "candidate, so it is not shown here.", url))
    if not prior:
        gaps.append((STATE, "state", STATE, NAME, "soil conservation districts missing from the list",
                     "This year's soil conservation districts are checked against the Secretary of State's 2024 general election list, which could not be read on "
                     "this run; a district with no row on this year's list would not be noticed.", LIST_URL.format(PRIOR_EID)))

    n_empty = sum(1 for c in contests.values() if not c["names"])
    where = "all 53" if len(reached) == len(counties) else f"{len(reached)} of the {len(counties)}"
    per_county = {}
    for name, filed in soil_filed.items():
        for f in filed:
            per_county[f] = per_county.get(f, 0) + 1
    several = [full_name[f] for f in sorted(per_county) if per_county[f] > 1]
    lines_words = [f"{and_names(several)} {'each have' if len(several) > 1 else 'has'} more than one"] if several else []
    if by_name:
        lines_words.append(f"{NUMBER[len(by_name)] if len(by_name) < len(NUMBER) else len(by_name)} {'are' if len(by_name) > 1 else 'is'} shown for a second county "
                           "that the district's own name names or the 2024 list filed it under")
    soil_words = (f" Soil conservation districts do not all follow county lines ({'; '.join(lines_words)}), and a voter's ballot carries only the district the "
                  "voter lives in.") if lines_words else ""
    if missing:
        gone = sorted({name for name, _f in missing})
        soil_words += (f" The {and_names(gone)} had a contest on the 2024 list and {'has' if len(gone) == 1 else 'have'} no row on this year's; "
                       f"{'it is' if len(gone) == 1 else 'they are'} named among the gaps.")
    seat_words = ("how many commissioners an at-large contest elects is taken from the June 9 no-party ballot, which by law states the number to be elected in November"
                  if june else "how many commissioners an at-large contest elects could not be read on this run")
    notes = [
        (STATE, "local_calendar",
         "On November 3, 2026 North Dakota's counties elect their auditor, treasurer, recorder, sheriff and state's attorney (some of these offices are combined, "
         "a few counties also elect a clerk of district court, and a county may make an office appointed), the county commissioners whose terms are up, and one "
         "supervisor of each soil conservation district; counties in the Garrison Diversion Conservancy District whose director's term is up elect a director, and "
         "each county's voters choose its official newspaper. All are no-party offices. Cities and park districts held their regular elections on June 9, 2026, "
         "school boards hold theirs each year between April and June, townships elect officers at their annual meetings in March, and Southwest Water Authority "
         "directors were on the June ballot, so none of those offices is on the November ballot.",
         "N.D.C.C. 11-10-02, 11-11-03, 4.1-20-17, 4.1-20-18, 61-24-03, 46-06-01 and 16.1-11-08 (offices on the November ballot); 40-21-02, 40-49-07, 15.1-09-22, "
         "58-04-01, 58-05-02 and 61-24.5-06 (offices elected at other times)", CODE_URL),
        (STATE, "local_coverage",
         f"Loaded from the Secretary of State's 2026 General Election Contest/Candidate List: {len(races)} county and district contests in {where} counties "
         f"({by_level.get('county', 0)} for county offices, {by_level.get('soil_water', 0)} for soil conservation district supervisors, "
         f"{by_level.get('other', 0)} for directors of the Garrison Diversion Conservancy District in the counties electing one this year) with {len(cands)} "
         f"candidates; {n_empty} of the contests are listed with no candidate. Left out: the {len(newspapers)} contests for a county's official newspaper "
         f"({counts['newspaper']} newspapers, not people) and ballot measures, which a candidate list does not carry; the list has no status column, so a candidate "
         f"who withdrew is simply absent and cannot be counted.{soil_words} "
         f"The list is alphabetical and state law rotates names from precinct to precinct, so no ballot order is given; {seat_words}.",
         "North Dakota Secretary of State, 2026 General Election Contest/Candidate List; N.D.C.C. 16.1-06-08 and 16.1-11-27 (names rotated), 16.1-11-24 "
         "(the June ballot's vote-for number)", url),
    ]

    sources = [
        (LOCAL_LIST_SRC, STATE, "official candidate list", "North Dakota Secretary of State",
         "2026 General Election Contest/Candidate List (county offices, soil conservation districts and the Garrison Diversion Conservancy District)",
         kept["url"], "", kept["fetched"], kept["sha256"], n_local,
         f"Read through the page's own search with the jurisdiction All, which returns every contest in one table ({len(rows)} rows). Six cells of each row are read, "
         "by their headings: the contest title, the office, the district, the county, the name and the party. The address, e-mail, phone and website columns are "
         "never read, and only those six cells are kept on disk; the fingerprint is of the answer as it came. "
         f"Of the {n_local} county-level rows, {counts['people']} name a candidate for an office, {counts['newspaper']} name a newspaper (left out) and "
         f"{counts['empty']} are contests shown with no candidate; the other {counts['state']} rows are statewide, legislative, judicial and federal. "
         "The list is alphabetical and gives no ballot order."),
        (COUNTY_SRC, STATE, "official boundaries (attributes)", "U.S. Census Bureau", "Cartographic boundary file, counties, 1:500,000 (2024)", COUNTY_URL, "",
         dt.datetime.fromtimestamp(os.path.getmtime(COUNTY_ZIP)).strftime("%Y-%m-%d"), hashlib.sha256(open(COUNTY_ZIP, "rb").read()).hexdigest(), len(counties),
         "County names and five-digit codes for North Dakota, read from the file's attribute table (the kit's copy; no shapes are read here)."),
    ]
    if prior:
        sources.append(
            (PRIOR_SRC, STATE, "official candidate list", "North Dakota Secretary of State", "2024 General Election Contest/Candidate List (soil conservation districts only)",
             prior["url"], "", prior["fetched"], prior["sha256"], len(prior["districts"]),
             "The last general election's list, read once through the page's own search with the jurisdiction All. Three cells of each row are read, by their headings "
             "(office, district, county), and only the district and county of the soil conservation rows are kept; no name is read, and the contact columns never are. "
             "Used to see which county each district was filed under then (a district lies where its candidates live) and whether a district on that list is "
             "missing from this year's. The fingerprint is of the answer as it came."))
    if june:
        sources += [
            (JUNE_LIST_SRC, STATE, "official results", "North Dakota Secretary of State", "2026 Primary Election (June 9, 2026), official results: the contest list",
             june["list"]["url"], (june.get("last_updated") or "")[:10], june["fetched"], june["list"]["sha256"], len(june["contests"]),
             "The contest list of the service behind the Election Night Reporting page, marked official. Only each county contest's name and vote-for number are "
             "kept: on the no-party ballot that number is the number to be elected in November (N.D.C.C. 16.1-11-24), which is how the seats of an at-large "
             f"commissioner contest are known ({seats_known} November contests found their June contest). No candidate's name and no vote is kept; the fingerprint is "
             "of the answer as it came."),
            (JUNE_RES_SRC, STATE, "official results", "North Dakota Secretary of State", "2026 Primary Election (June 9, 2026), official results: county contests",
             june["results"]["url"], (june.get("last_updated") or "")[:10], june["fetched"], june["results"]["sha256"], len(june["contests"]),
             "Read only for the county each June county contest was held in (the county code its results are filed under), so that a contest named for a "
             "district alone is matched in the right county. No candidate's name and no vote is kept; the fingerprint is of the answer as it came."),
        ]

    # the last look before anything is written: nothing that reads like contact details, by the trial check's own test and the page builder's
    for table, strict, items in (("sl_races", True, [(r[0], (r[4], r[5], r[8], r[9], r[16])) for r in races]),
                                 ("sl_candidates", True, [(c[0], (c[3], c[4], c[14])) for c in cands]),
                                 ("sl_places", True, [(p[1], (p[2],)) for p in places]),
                                 ("sl_gaps", False, [(g[2], (g[3], g[4], g[5])) for g in gaps]),
                                 ("sl_notes", False, [(x[1], (x[2], x[3])) for x in notes]),
                                 ("sl_sources", False, [(s[0], (s[3], s[4], s[10])) for s in sources])):
        for ident, texts in items:
            if any(t and (contact_like(t, strict) or (strict and BUILDER_STREET.search(str(t)))) for t in texts):
                raise SystemExit(f"North Dakota: a text for {table} ({ident}) reads like contact details; stopping (the text is not printed)")

    return {"races": races, "cands": cands, "places": places, "sources": sources, "gaps": gaps, "notes": notes, "problems": problems, "counts": counts,
            "rows": len(rows), "local_rows": n_local, "by_level": by_level, "by_kind": by_kind, "counties": len(reached), "empty": n_empty,
            "newspapers": len(newspapers), "seats_known": seats_known, "seats_read": bool(june), "by_name": by_name, "fetched": kept["fetched"],
            "missing": [f"{name} ({full_name[f]})" for name, f in missing], "prior_read": bool(prior)}


# ---------------------------------------------------------------- load

def source_row(source_id, path, kind, title, url, rows, note, published=""):
    digest = hashlib.sha256(open(path, "rb").read()).hexdigest() if path and os.path.exists(path) else ""
    fetched = dt.datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d") if path and os.path.exists(path) else ""
    agency = "Open States (people project, CC0)" if source_id == SRC_ROSTER else "North Dakota Secretary of State"
    return (source_id, STATE, kind, agency, title, url, published, fetched, digest, rows, note)


def load(db_path, say=print, cache=CACHE, roster_path=ROSTER, local_cache=None, refresh=False):
    """North Dakota's rows into the database at db_path: the state races, then the county and district ones. local_cache
    is the folder for the cut-down county-level list (ballot_cache/nd/local/ unless told otherwise); refresh=True asks
    for that list again even when the copy on disk is less than a week old."""
    net.patient_lookups()
    gpath, general = candidate_list(cache, GEN_EID, "2026 General Election", keep=False, say=say)
    ppath, primary = candidate_list(cache, PRI_EID, "2026 Primary Election", keep=True, say=say)
    members, officials = roster(roster_path)

    races, cands, places, problems = {}, [], {}, []
    federal = {"general": 0, "primary": 0}
    read = {"general": {}, "primary": {}}                  # office -> rows read, for the count check

    # November: every candidate on the list, one race per contest
    listed = {}                                            # race_id -> [row]
    for row in general:
        race = race_for(row)
        if race is None:
            federal["general"] += 1
            continue
        read["general"][row["office"]] = read["general"].get(row["office"], 0) + 1
        rid = race["race_id"]
        if rid in races and races[rid]["office"] != race["office"]:
            raise SystemExit(f"North Dakota: two offices share the race key {rid}")
        races.setdefault(rid, race)
        listed.setdefault(rid, []).append(row)
        if race.get("place"):
            places[race["place"][:2]] = race["place"]

    # primary ballots, by race and party
    ballots = {}                                           # (race_id, party) -> [row]
    for row in primary:
        race = race_for(row)
        if race is None:
            federal["primary"] += 1
            continue
        read["primary"][row["office"]] = read["primary"].get(row["office"], 0) + 1
        if race["race_id"] not in races:
            problems.append(f"{race['race_id']} had a June primary but is not on the November list")
            continue
        ballots.setdefault((race["race_id"], row["party"]), []).append(row)

    # a field: more names on a party's (or the nonpartisan) ballot than it can send on
    def places_for(rid, party, contest):
        n = contest["vote_for"] if contest else races[rid]["seats"]
        return 2 * n if party == "Nonpartisan" else n

    wanted = {results_name(rows[0]) for (rid, party), rows in ballots.items()}
    rpath, results = primary_results(cache, wanted, say)
    official = bool(results and results.get("official"))
    def contest_votes(rid, party, rows, contest):
        """Each listed candidate's official votes; the results must name the same candidates as the list, once each."""
        people_choices = [ch for ch in contest["choices"] if not ch["write_in"]]
        if len(people_choices) != len(rows):
            raise SystemExit(f"North Dakota: the results of {rid} ({party}) name {len(people_choices)} candidates, the list {len(rows)}")
        votes = {}
        for row in rows:
            hit = [ch for ch in people_choices if key(ch["name"]) == key(row["name"])] or \
                  [ch for ch in people_choices if fits(name_parts(row["name"]), name_parts(ch["name"]))]
            if len(hit) != 1:
                raise SystemExit(f"North Dakota: {row['name']} ({rid}, {party}) is not found once in the official results")
            votes[row["name"]] = hit[0]["votes"]
        return votes

    fields, uncontested, group_votes = {}, 0, {}
    for (rid, party), rows in sorted(ballots.items()):
        contest = (results or {}).get("contests", {}).get(results_name(rows[0])) if official else None
        if official and not contest:
            problems.append(f"{rid}: the official results carry no contest \"{results_name(rows[0])}\"")
        if contest:
            group_votes[(rid, party)] = contest_votes(rid, party, rows, contest)      # checked for every primary, field or not
        if len(rows) > places_for(rid, party, contest):
            fields[(rid, party)] = (rows, contest)
        else:
            uncontested += 1
    if sum(len(rows) for rows in ballots.values()) + sum(1 for p in problems if "not on the November list" in p) < sum(read["primary"].values()):
        problems.append(f"primary: {sum(read['primary'].values())} rows read, {sum(len(r) for r in ballots.values())} placed in a race")

    # the November rows
    general_keys = {}                                      # race_id -> {(key, party)}
    for rid, rows in sorted(listed.items()):
        race = races[rid]
        shown, people = holders(race, members, officials)
        race["holder_id"] = "; ".join(p["id"] for p in shown) or None
        race["holder_name"] = "; ".join(p["full"] for p in shown) or None
        race["holder_party"] = "; ".join(p["party"] or "" for p in shown) or None
        if not shown:
            extra = ("The roster used here does not list who holds this office today." if race["level"] != "legislature"
                     else "The roster used here lists nobody in this seat today.")
            race["note"] = " ".join(x for x in (race["note"], extra) if x)
        elif race["special"] and len(shown) > 1:
            race["note"] = " ".join(x for x in (race["note"], "Which of the district's two members holds the seat being filled could not be told from the roster, so both are given.") if x)
        if race["special"] and not any(k[0] == rid for k in ballots):
            race["note"] = " ".join(x for x in (race["note"], "No primary contest for this seat was on the June 9 ballot.") if x)
        general_keys[rid] = set()
        for row in sorted(rows, key=lambda r: r["name"]):
            party = NONPARTISAN if row["party"] == "Nonpartisan" else row["party"]
            code = "N" if row["party"] == "Nonpartisan" else party_code(row["party"])
            who = one_fit(row["name"], people) if people else None
            general_keys[rid].add((key(row["name"]), row["party"]))
            note = None
            if race["partisan"] and (rid, row["party"]) in ballots and not any(key(r["name"]) == key(row["name"]) for r in ballots[(rid, row["party"])]):
                note = "Not on the party's June 9 primary ballot."
            elif race["partisan"] and (rid, row["party"]) not in ballots and row["party"] in CODES and any(k[0] == rid for k in ballots):
                note = "Not on the party's June 9 primary ballot."
            cands.append((rid, "general", GENERAL, row["name"], party, code, None, 1 if who else 0, 0, None, None, None,
                          who["id"] if who else None, SRC_GEN, note))

    def went_on(rid, rows):
        """Names on a primary ballot that are on the November list for the same race (and party, for a party primary)."""
        return {row["name"] for row in rows
                if (key(row["name"]), row["party"]) in general_keys[rid]
                or (row["party"] == "Nonpartisan" and any(k[0] == key(row["name"]) for k in general_keys[rid]))}

    # an uncontested primary's candidate missing in November (withdrew, or otherwise off the list): reported, not stored
    gone = [f"{row['name']} ({rid}, {party})" for (rid, party), rows in sorted(ballots.items()) if (rid, party) not in fields
            for row in rows if row["name"] not in went_on(rid, rows)]

    # the primary fields
    mismatched = []
    for (rid, party), (rows, contest) in sorted(fields.items()):
        race = races[rid]
        _shown, people = holders(race, members, officials)
        np_ = party == "Nonpartisan"
        election = f"primary-{CODES.get(party, party[:3].upper())}"
        votes = group_votes.get((rid, party), {})
        advanced = went_on(rid, rows)
        if votes:
            ranked = sorted(votes, key=votes.get, reverse=True)
            top = set(ranked[:len(advanced)])
            if advanced != top or len(advanced) > places_for(rid, party, contest):
                mismatched.append(f"{rid} {party}: advanced {sorted(advanced)}, most votes {sorted(top)}")
        for row in sorted(rows, key=lambda r: r["name"]):
            v = votes.get(row["name"]) if contest else None
            who = one_fit(row["name"], people) if people else None
            cands.append((rid, election, PRIMARY, row["name"], NONPARTISAN if np_ else party, "N" if np_ else party_code(party),
                          None, 1 if who else 0, 0, v,
                          round(100 * v / contest["total"], 1) if contest and contest["total"] and v is not None else None,
                          "advanced" if row["name"] in advanced else "lost", who["id"] if who else None,
                          SRC_PRI, None))

    # CHECKS: odd-numbered districts all on the ballot; counts read = counts stored
    senate = sorted(int(r["district"]) for r in races.values() if r["office_kind"] == "state_senate")
    house = sorted(int(re.match(r"\d+", r["district"]).group()) for r in races.values() if r["office_kind"] == "state_house" and not r["special"])
    odd = list(range(1, 48, 2))
    for label, got in (("Senate", senate), ("House", house)):
        missing = [d for d in odd if d not in got]
        extra = [d for d in got if d not in odd]
        if missing:
            problems.append(f"{label}: odd-numbered districts with no race on the November list: {missing}")
        if extra:
            problems.append(f"{label}: regular races in even-numbered districts: {extra}")
    gen_rows = sum(1 for c in cands if c[1] == "general")
    if gen_rows != sum(read["general"].values()):
        problems.append(f"November: {sum(read['general'].values())} rows read, {gen_rows} stored")
    short = [rid for rid, rows in listed.items() if len(rows) < races[rid]["seats"]]

    race_rows = [(r["race_id"], STATE, r["level"], r["office_kind"], r["office"], r["jurisdiction"], r["jurisdiction_id"], None,
                  r["district"], r["seat"], r["special"], r["partisan"], r.get("holder_id"), r.get("holder_name"), r.get("holder_party"),
                  GENERAL, r["note"]) for r in races.values()]
    place_rows = [(kind, pid, name, None, SRC_GEN) for (kind, pid), (_k, _i, name) in sorted(places.items())]
    by_kind = {}
    for r in races.values():
        by_kind[r["office_kind"]] = by_kind.get(r["office_kind"], 0) + 1

    # the local level: county offices, soil conservation districts and the Garrison Diversion Conservancy District
    local = local_level(local_cache or os.path.join(cache, "nd", "local"), say, refresh)
    if local["counts"]["state"] != len(general):
        problems.append(f"the search of all contests (fetched {local['fetched']}) has {local['counts']['state']} statewide, legislative, judicial and federal rows; "
                        f"the three searches give {len(general)}")
    problems += local["problems"]

    sources = [
        source_row(SRC_GEN, gpath, "official candidate list", "2026 General Election Contest/Candidate List (statewide, legislative and judicial contests)",
                   LIST_URL.format(GEN_EID), len(general),
                   "Read through the page's own search, once each for the Statewide, Legislative and Judicial jurisdictions. Only the contest title, "
                   "office, district, name and party are read, by their headings; the address, e-mail, phone and website columns are never read. "
                   f"The list is alphabetical by family name and gives no ballot order. {federal['general']} federal rows (Representative in Congress) left to the federal loader."),
        source_row(SRC_PRI, ppath, "official candidate list", "2026 Primary Election Contest/Candidate List (statewide, legislative and judicial contests), June 9, 2026",
                   LIST_URL.format(PRI_EID), len(primary),
                   "Read the same way as the November list, with the same five columns. "
                   f"Primaries with a field (more names than places): {len(fields)}; without: {uncontested}. Who advanced is read from the November list"
                   + (" and checked against the official vote counts." if official else "; official vote counts could not be read, so the fields carry no votes.")),
    ]
    if official:
        sources.append(source_row(SRC_RES, rpath, "official results", "2026 Primary Election (June 9, 2026), official results: state contests",
                                  RESULTS_PAGE, sum(len(c["choices"]) for c in results["contests"].values()),
                                  "Election Night Reporting, marked official by the Secretary; statewide totals read from the service behind the page (its "
                                  f"Election/GetElectionInfo, Contest/GetContestSearchList and Contest/GetContestResults answers, election {PRI_EID}). Write-in votes count in "
                                  "each primary's total but are not listed; in a two-seat primary a percentage is the share of all votes cast. The date given is the results' last update.",
                                  published=(results.get("last_updated") or "")[:10]))
    if members or officials:
        sources.append(source_row(SRC_ROSTER, roster_path, "roster", "Legislators serving now and statewide officials (state_nd.sqlite, from the Open States people project)",
                                  "https://github.com/openstates/people", len(members) + len(officials),
                                  "Used only to say who holds each seat today and to mark incumbents: names, parties, districts and start dates. Not an official record."))

    # North Dakota's rows only, in one transaction: its races and candidates by state and race id, its sources, gaps and
    # notes by state, its places by their nd- source ids (the counties' codes begin 38, so the id cannot pick them out)
    con = sqlite3.connect(db_path)
    try:
        con.executescript(SCHEMA)
        con.executescript(EXTRA_SCHEMA)
        with con:
            con.execute("DELETE FROM sl_candidates WHERE race_id IN (SELECT race_id FROM sl_races WHERE state = ?) OR race_id LIKE ?", (STATE, f"2026-{STATE}-%"))
            con.execute("DELETE FROM sl_races WHERE state = ?", (STATE,))
            con.execute("DELETE FROM sl_sources WHERE state = ?", (STATE,))
            con.execute("DELETE FROM sl_places WHERE source_id LIKE 'nd-%'")
            con.execute("DELETE FROM sl_gaps WHERE state = ?", (STATE,))
            con.execute("DELETE FROM sl_notes WHERE state = ?", (STATE,))
            con.executemany("INSERT INTO sl_races VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", race_rows + local["races"])
            con.executemany("INSERT INTO sl_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", cands + local["cands"])
            con.executemany("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", sources + local["sources"])
            con.executemany("INSERT INTO sl_places VALUES (?,?,?,?,?)", place_rows + local["places"])
            con.executemany("INSERT INTO sl_gaps VALUES (?,?,?,?,?,?,?)", local["gaps"])
            con.executemany("INSERT INTO sl_notes VALUES (?,?,?,?,?)", local["notes"])
    finally:
        con.close()

    counts = ", ".join(f"{k} {v}" for k, v in sorted(by_kind.items()))
    say(f"    North Dakota: {len(races)} state races on the November ballot ({counts}), {gen_rows} candidates; "
        f"{len(fields)} primary fields" + (", votes from the official results" if official else ", no votes read")
        + f"; {sum(1 for c in cands if c[1] == 'general' and c[7])} incumbents matched")
    lv = local["by_level"]
    say(f"    North Dakota: {len(local['races'])} county and district races in {local['counties']} of 53 counties (county offices {lv.get('county', 0)}, soil "
        f"conservation districts {lv.get('soil_water', 0)}, Garrison Diversion {lv.get('other', 0)}), {len(local['cands'])} candidates, {local['empty']} contests with "
        f"no candidate; {local['newspapers']} official-newspaper contests ({local['counts']['newspaper']} newspapers) left out; list of {local['fetched']}")
    say(f"      check: {local['rows']} rows in the list = {local['counts']['state']} statewide, legislative, judicial and federal + {local['local_rows']} county-level "
        f"({local['counts']['people']} candidates, each in one race, + {local['counts']['newspaper']} newspapers + {local['counts']['empty']} empty contests)"
        + (f"; seats read from the June ballot for {local['seats_known']} contests" if local["seats_read"] else "; the June vote-for numbers could not be read"))
    if local["by_name"]:
        say("      note: soil conservation districts shown for a second county, which their own names name or the 2024 list filed them under: "
            + "; ".join(local["by_name"]))
    if local["missing"]:
        say(f"      note: on the 2024 list but with no row on this year's (named in sl_gaps): {'; '.join(local['missing'])}")
    for p in problems:
        say(f"      CHECK {p}")
    for m in mismatched:
        say(f"      CHECK primary advancers differ from the vote order: {m}")
    for rid in sorted(short):
        say(f"      note: {rid} has fewer candidates than seats ({len(listed[rid])} for {races[rid]['seats']})")
    if gone:
        say(f"      note: on an uncontested June primary ballot but not on the November list: {'; '.join(gone)}")
    return {"races": len(races), "candidates": gen_rows, "by_kind": by_kind, "fields": len(fields), "uncontested": uncontested,
            "official": official, "problems": problems, "mismatched": mismatched, "short": sorted(short), "gone": gone,
            "checked_primaries": len(group_votes), "read": read, "federal": federal,
            "local": {k: local[k] for k in ("counts", "rows", "local_rows", "by_level", "by_kind", "counties", "empty", "newspapers", "seats_known", "seats_read",
                                            "by_name", "missing", "prior_read", "fetched")}
                     | {"races": len(local["races"]), "candidates": len(local["cands"]), "gaps": len(local["gaps"])}}


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--refresh"]
    if not args:
        raise SystemExit("usage: python -m ballot.state_local_nd <database> [cache folder] [--refresh]")
    load(args[0], cache=args[1] if len(args) > 1 else CACHE, refresh="--refresh" in sys.argv[1:])
