"""
ballot/state_local_nd.py - North Dakota's state races on the November 3, 2026 ballot: the Legislative Assembly seats up
this year, the statewide offices, and the Supreme Court and district court seats, with the June 9 primaries that chose
the nominees. Written into ballot_local_2026.sqlite (never ballot_2026.sqlite), North Dakota's rows only.

Sources, all the Secretary of State's own:
  * the 2026 General Election Contest/Candidate List (vip.sos.nd.gov/candidatelist.aspx?eid=348) and the 2026 Primary
    Election Contest/Candidate List (eid=346): search pages, asked as the page's own Search button asks, once per
    jurisdiction (Statewide, Legislative, Judicial) with no contest chosen. The table carries mailing addresses, e-mail,
    phones and websites; only five cells of each row are ever read (the contest title, the office, the district, the
    candidate's name and the party), found by their headings, and only those five are kept on disk. The County and Term
    Length columns are not read either. The list is printed alphabetically by family name and gives no ballot order, so
    ballot_order is left empty.
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

The privacy rule: only office, district, name, party, ballot order, status and votes are read from any file. Nothing
else is printed, logged, cached or stored.
"""

import hashlib
import html as H
import json
import os
import re
import sqlite3
import sys
import time
import urllib.parse
import datetime as dt
from urllib.error import HTTPError
from urllib.request import Request, urlopen

if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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


def search(eid, jurisdiction, election):
    """Every candidate in one jurisdiction (SW, LEG, JUD) of one election, through the page's own Search."""
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
        answer = r.read().decode("utf-8", "replace")
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


# ---------------------------------------------------------------- load

def source_row(source_id, path, kind, title, url, rows, note, published=""):
    digest = hashlib.sha256(open(path, "rb").read()).hexdigest() if path and os.path.exists(path) else ""
    fetched = dt.datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d") if path and os.path.exists(path) else ""
    agency = "Open States (people project, CC0)" if source_id == SRC_ROSTER else "North Dakota Secretary of State"
    return (source_id, STATE, kind, agency, title, url, published, fetched, digest, rows, note)


def load(db_path, say=print, cache=CACHE, roster_path=ROSTER):
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
                                  f"Election Night Reporting, marked official by the Secretary; statewide totals read from the service behind the page ({API}: "
                                  f"Election/GetElectionInfo, Contest/GetContestSearchList, Contest/GetContestResults, election {PRI_EID}). Write-in votes count in "
                                  "each primary's total but are not listed; in a two-seat primary a percentage is the share of all votes cast. The date given is the results' last update.",
                                  published=(results.get("last_updated") or "")[:10]))
    if members or officials:
        sources.append(source_row(SRC_ROSTER, roster_path, "roster", "Legislators serving now and statewide officials (state_nd.sqlite, from the Open States people project)",
                                  "https://github.com/openstates/people", len(members) + len(officials),
                                  "Used only to say who holds each seat today and to mark incumbents: names, parties, districts and start dates. Not an official record."))

    con = sqlite3.connect(db_path)
    try:
        con.executescript(SCHEMA)
        with con:
            con.execute("DELETE FROM sl_candidates WHERE race_id IN (SELECT race_id FROM sl_races WHERE state = ?) OR race_id LIKE ?", (STATE, f"2026-{STATE}-%"))
            con.execute("DELETE FROM sl_races WHERE state = ?", (STATE,))
            con.execute("DELETE FROM sl_sources WHERE state = ?", (STATE,))
            con.execute("DELETE FROM sl_places WHERE id LIKE ? AND source_id LIKE 'nd-%'", (f"{STATE}-%",))
            con.executemany("INSERT INTO sl_races VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", race_rows)
            con.executemany("INSERT INTO sl_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", cands)
            con.executemany("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", sources)
            con.executemany("INSERT INTO sl_places VALUES (?,?,?,?,?)", place_rows)
    finally:
        con.close()

    counts = ", ".join(f"{k} {v}" for k, v in sorted(by_kind.items()))
    say(f"    North Dakota: {len(races)} state races on the November ballot ({counts}), {gen_rows} candidates; "
        f"{len(fields)} primary fields" + (", votes from the official results" if official else ", no votes read")
        + f"; {sum(1 for c in cands if c[1] == 'general' and c[7])} incumbents matched")
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
            "checked_primaries": len(group_votes), "read": read, "federal": federal}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("usage: python -m ballot.state_local_nd <database> [cache folder]")
    load(sys.argv[1], cache=sys.argv[2] if len(sys.argv) > 2 else CACHE)
