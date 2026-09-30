"""
ballot/state_local_ri.py - Rhode Island's state races on the November 3, 2026 ballot, into ballot_local_2026.sqlite:

  - the five general officers, elected statewide for four years (all last elected in 2022): Governor, Lieutenant
    Governor (elected on its own, not as a ticket), Secretary of State, Attorney General and General Treasurer;
  - all 38 seats of the Senate and all 75 of the House of Representatives of the General Assembly (two-year terms: the
    whole legislature is elected every even year);
with each party's primary field (September 9, 2026) and its official votes. Which offices are up is taken from a fixed
list and checked against the official primary results: every statewide office above must have at least one party
contest there, every Senate and House district is looked for, and a state contest in the results that is not above
stops the loader. Rhode Island elects no judges; the state's courts are not on the ballot.

Not stored here: the party committee places on the September ballot (state committee members, senatorial,
representative district and ward committees: party offices, not on the November ballot), and the city and town
contests (mayors, councils, school committees), which are local. The federal ballot database is never opened here.

Sources, all Rhode Island's own:
  - the Board of Elections' official results of the September 9, 2026 Statewide Primary, from its election results site
    (electionresults.ri.gov, linked from elections.ri.gov's Previous Election Results page), which fetches its figures
    from the site's own data service (results/public/api/elections/RhodeIsland/RI2026StatewidePrimary: the election,
    marked isOfficialResults; .../data: every contest with every candidate's statewide votes and the same by count
    group, Election Day, Early Voting and Mail Ballots; .../data/ballot-item/<id>: one contest town by town). The same
    service the federal loader (ballot/lists/ri.py) reads. Only the state contests are kept, as figures (contest,
    candidate name as printed, party, votes), in ballot_cache/ri/ri_2026_primary_state.json. Checked against the Board's
    "Summary Results Report, OFFICIAL RESULTS, Primary Election 2026" (Prim26_Summary.pdf, from the same page, the copy
    the federal loader keeps): every candidate's TOTAL and count groups must equal the service's, each contest's Total
    Votes Cast must equal the sum of its candidates and the service's vote total, the towns must add up to the statewide
    figures, every town must have reported, and each statewide contest's Contest Totals must equal the report's Ballots
    Cast for the party. No write-in votes are reported for these contests, so a field's total is the sum of its
    candidates. The loader stops if the service ever says the results are not official. The primary ballot marks the
    candidate the party endorsed with an asterisk (*), and the results carry it ("Samuel W. Bell*"): it is taken off the
    name and said in the row's note (it is not an incumbency mark).
  - the November ballot: the Department of State Elections Division's "Candidates in Upcoming Elections"
    (vote.sos.ri.gov/Candidates/CandidateSearch, one summary page per office). The site answers scripts with a
    Cloudflare challenge, which is never worked around and not asked again. A page for a state office (Governor,
    Lieutenant Governor, Secretary of State, Attorney General, General Treasurer, Senator in General Assembly,
    Representative in General Assembly), for the November 3, 2026 General Election, saved in a browser (as a web page, or
    as the spreadsheet or CSV export if the page offers one) into ballot_cache/ri/general/ (the folder the federal loader
    reads for Congress) is read from there. Until one is, no November candidate is stored and every race says so; its
    note names the nominees the official primary results give (the list would add independent candidates and drop
    anyone who withdrew; Rhode Island lets a party replace a nominee who withdraws).
Who holds each seat comes from the Open States roster in state_ri.sqlite (legislators is_current = 1 by chamber and
district; the officials table for Governor, Lieutenant Governor, Secretary of State and Attorney General, the only
general officers it carries): ids, names and party only. A candidate is the seat's incumbent when the name fits the
sitting member of that seat (same family name, a given name that fits) and no other candidate in the same election
fits. County codes: the Census Bureau's 2024 county file and its 2024 county subdivision file for Rhode Island (the 39
cities and towns, each wholly inside one county); the counties a district reaches are those of the towns its primary
contests were counted in (derived, and said so).

Privacy. The results carry contest names, candidate names as printed, parties and votes only. From a saved November
page only these cells are ever read, by their headings (the allowlist in ballot/lists/ri.py, HEADS): the candidate's
name, the party or "political principle", the office, the district, the status and a ballot position. Any other column
(addresses, cities, telephones, e-mail, websites, committees) is dropped as each row is read and never kept, printed,
logged or cached; the file is never copied. An error names the file, the office or the check, never a row. The
roster's contact columns are never selected. Before anything is written every stored name, party and note is checked
for anything that looks like a contact detail (the page builder's own patterns), and the load stops (without showing
it) if one does.

Ballot order. The primary results do not say in what order the ballot printed the names, so no primary row carries
one. A November row carries one only when the saved list gives a position column.

    python -m ballot.state_local_ri <path to a test database>
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

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from ballot.common import CACHE, fold, name_parts, party_code  # noqa: E402
from ballot.lists.ri import (API, BOARD_PAGE, ENDORSED, GONE, ON, PARTY_WORDS, PRIMARY, SITE, SOS_PAGE, SUMMARY_PDF,  # noqa: E402
                             WRITE_IN, column_map, get_json, html_rows, ordinary, same_name, sheet_rows, shown, squash, text_of)
from ballot.match import fits  # noqa: E402
from ballot.pdftext import lines as pdf_lines  # noqa: E402

STATE, FIPS, NAME = "RI", "44", "Rhode Island"
GENERAL = "2026-11-03"
FOLDER = os.path.join(CACHE, "ri")
GFOLDER = os.path.join(FOLDER, "general")
RESULTS_JSON = "ri_2026_primary_state.json"
ROSTER = os.path.join(HERE, "state_ri.sqlite")
CENSUS = os.path.join(HERE, "states_cache", "census")
COUNTY_ZIP = os.path.join(CENSUS, "cb_2024_us_county_500k.zip")
COUNTY_URL = "https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_county_500k.zip"
COUSUB_ZIP = os.path.join(CENSUS, "cb_2024_44_cousub_500k.zip")
COUSUB_URL = "https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_44_cousub_500k.zip"
SENATE_SEATS, HOUSE_SEATS, TOWNS, COUNTIES = 38, 75, 39, 5
AGENCY_BOE = "Rhode Island Board of Elections"
AGENCY_SOS = "Rhode Island Department of State, Elections Division"
SRC_RESULTS, SRC_SUMMARY = "ri-sl-boe-2026-primary-results", "ri-sl-boe-2026-primary-summary"
SRC_LIST, SRC_ROSTER = "ri-sl-sos-2026-general-list", "ri-sl-openstates-roster"
SRC_COUNTY, SRC_COUSUB = "ri-sl-census-2024-counties", "ri-sl-census-2024-towns"
CODE = {"DEM": "DEM", "REP": "REP"}
PARTY = {"DEM": "Democrat", "REP": "Republican"}               # as the Board prints them (DEMOCRAT, REPUBLICAN), in ordinary capitals
BOARD_WORD = {"DEM": "DEMOCRAT", "REP": "REPUBLICAN"}

# the statewide offices: results office name -> (race key, office_kind, office shown, roster office in state_ri.sqlite)
STATEWIDE = {
    "Governor": ("GOV", "governor", "Governor", "governor"),
    "Lieutenant Governor": ("LTG", "lieutenant_governor", "Lieutenant Governor", "lt_governor"),
    "Secretary of State": ("SOS", "secretary_of_state", "Secretary of State", "secretary of state"),
    "Attorney General": ("AG", "attorney_general", "Attorney General", "attorney general"),
    "General Treasurer": ("TREAS", "state_treasurer", "General Treasurer", None),
}
OFFICIAL_WORDS = {"governor": "Governor", "lt_governor": "Lieutenant Governor", "secretary of state": "Secretary of State",
                  "attorney general": "Attorney General"}
S_OFFICE, H_OFFICE = "Senator in General Assembly", "Representative in General Assembly"

# the results' contest names: "DEM Senator in General Assembly District 5", "REP Governor"
R_STATE = re.compile(r"^(DEM|REP) (Governor|Lieutenant Governor|Secretary of State|Attorney General|General Treasurer|"
                     r"Senator in General Assembly District (\d{1,2})|Representative in General Assembly District (\d{1,2}))$")
R_FEDERAL = re.compile(r"\bin Congress\b")
R_PARTY_OFFICE = re.compile(r"^(DEM|REP) (State Committee(man|woman)|Senatorial District Committee|Representative District Committee|"
                            r"Ward Committee)\b")
R_STATE_LIKE = re.compile(r"Governor|Secretary of State|Attorney General|Treasurer|General Assembly", re.I)

# the page builder's privacy patterns (build_ballot_state_dev.py): nothing stored may trip them
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[A-Za-z]{2,}")
PHONE = re.compile(r"\(?\b\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}\b")
WEB = re.compile(r"https?://|\bwww\.|\b[\w-]+\.(?:com|org|net|us|gov|edu|info|biz)\b", re.I)
STREET = re.compile(r"\b\d{1,6}\s+(?:[NSEW]\.?\s+)?[A-Za-z0-9.' -]{1,40}?\s(?:St|Street|Ave|Avenue|Rd|Road|Blvd|Boulevard|Dr|Drive|Ln|Lane|Way|Ct|Court|"
                    r"Cir|Circle|Pkwy|Parkway|Hwy|Highway|Trl|Trail|Pl|Place|Ter|Terrace)\b\.?", re.I)
ZIP = re.compile(r"\b[A-Z]{2}\s+\d{5}\b|\b\d{5}-\d{4}\b")
NAME_BAD = re.compile(r"\d{3}")

SENATE_NOTE = (f"Rhode Island's senators serve two-year terms; all {SENATE_SEATS} seats are on the ballot in 2026 "
               "(the official primary results carry a party contest in every Senate district).")
HOUSE_NOTE = (f"Rhode Island's representatives serve two-year terms; all {HOUSE_SEATS} seats are on the ballot in 2026 "
              "(the official primary results carry a party contest in every House district).")
LTG_NOTE = "Rhode Island elects its lieutenant governor on his or her own, not on a ticket with the governor."
NO_LIST = ("The Department of State's list of candidates for the November 3 ballot is not loaded yet: its candidate pages turn "
           "away scripts, so the list waits for a copy saved by hand.")
NONE_ON_LIST = "No candidate for this seat is on the saved November list."
NO_HOLDER = "The roster used here does not list who holds this office, so no holder is shown."
NOT_ON_LIST = "Won the primary but is not on the November list."
OTHER_ON_LIST = "Won the primary; the November list names another candidate for the party."


# ------------------------------------------------------------------------------------------------ the primary results

def contest_key(title):
    """A results contest name -> (party code, race key, statewide name or None), or None when it is not a state office."""
    m = R_STATE.match(title)
    if not m:
        return None
    if m.group(3):
        return m.group(1), f"SS{int(m.group(3))}", None
    if m.group(4):
        return m.group(1), f"SH{int(m.group(4))}", None
    return m.group(1), STATEWIDE[m.group(2)][0], m.group(2)


def fetch_results(say):
    """The state contests of the September 9 primary from the Board's results service, town by town: figures only."""
    election = get_json(API)
    if not election.get("isOfficialResults"):
        raise SystemExit("Rhode Island (state races): the Board's results service does not mark the 2026 primary's results official")
    if election.get("electionDate") != PRIMARY:
        raise SystemExit(f"Rhode Island (state races): the results service dates the primary {election.get('electionDate')}, not {PRIMARY}")
    data = get_json(API + "/data")
    contests, skipped, unread = [], {"federal": 0, "party offices": 0, "local": 0}, []
    items = data["ballotItems"]
    for item in items:
        title = text_of(item["name"])
        key = contest_key(title)
        if key is None:
            if R_FEDERAL.search(title):
                skipped["federal"] += 1
            elif R_PARTY_OFFICE.match(title):
                skipped["party offices"] += 1
            elif R_STATE_LIKE.search(title):
                unread.append(title)
            else:
                skipped["local"] += 1
            continue
        code, race, _sw = key
        vote_for = text_of(item.get("voteFor")) if item.get("voteFor") is not None else "Vote for 1"   # [{"text": "Vote for 1"}]
        if not re.fullmatch(r"(?i)vote for 1", vote_for):
            raise SystemExit(f"Rhode Island (state races): {title} says {vote_for!r}, not one seat")
        cands = []
        for o in item["summaryResults"]["ballotOptions"]:
            party = o.get("party") or {}
            if (party.get("abbreviation") or code) != code:
                raise SystemExit(f"Rhode Island (state races): a candidate in {title} carries the party {party.get('abbreviation')!r}")
            cands.append({"name": text_of(o["name"]), "votes": int(o["voteCount"]), "write_in": bool(o.get("isWriteIn")),
                          "party": text_of(party.get("name")) or BOARD_WORD[code],
                          "groups": {text_of(g["groupName"]): int(g["voteCount"]) for g in (o.get("groupResults") or [])}})
        status = item.get("reportingStatus") or {}
        detail = get_json(f"{API}/data/ballot-item/{item['id']}")["ballotItemWithBreakdown"]
        towns = {}
        for b in detail["breakdownResults"]:
            towns[text_of(b["locality"]["name"])] = {text_of(o["name"]): int(o["voteCount"]) for o in b["ballotOptions"]}
        contests.append({"title": title, "code": code, "race": race, "vote_total": item.get("voteTotal"),
                         "units": [status.get("reportingUnits"), status.get("totalUnits")], "candidates": cands, "towns": towns})
    if unread:
        raise SystemExit(f"Rhode Island (state races): state contests in the primary results that are not read: {unread}")
    say(f"      results service: {len(contests)} state contests, town by town ({len(items)} contests in all)")
    return {"name": text_of(election.get("name")), "date": election.get("electionDate"), "official": election.get("isOfficialResults"),
            "as_of": election.get("asOf"), "last_updated": election.get("lastUpdated"), "contests": contests, "skipped": skipped,
            "all_contests": len(items)}


def federal_only(say):
    """{party: ballots} cast with only the federal contests on them: the "Federal" unit of each party's Senator in Congress
    contest in the same results service (these ballots carry no state contest, so the statewide contests' Contest Totals
    fall short of the party's Ballots Cast by exactly this many)."""
    data = get_json(API + "/data")
    out = {}
    for item in data["ballotItems"]:
        m = re.match(r"^(DEM|REP) Senator in Congress$", text_of(item["name"]))
        if not m:
            continue
        detail = get_json(f"{API}/data/ballot-item/{item['id']}")["ballotItemWithBreakdown"]
        fed = [b for b in detail["breakdownResults"] if text_of(b["locality"]["name"]) == "Federal"]
        out[m.group(1)] = sum(int(o["voteCount"]) for b in fed for o in b["ballotOptions"])
    if sorted(out) != ["DEM", "REP"]:
        raise SystemExit("Rhode Island (state races): the results service has no Senator in Congress contest for each party")
    say(f"      federal-only ballots (the results' Federal unit): {out}")
    return out


def summary_report(path):
    """{contest title: {"cands": [(name, total, [groups])], "cast": n, "contest": n}} for the state contests, the report's
    Ballots Cast by party, and the date it prints."""
    out, cast, head, cur, date, in_cands = {}, {}, [], None, "", False
    for page, _y, text in pdf_lines(path):
        t = squash(text)
        if page == 1 and len(head) < 3:
            head.append(t)
        m = re.match(r"^Election Summary - (\d\d)/(\d\d)/(\d{4})", t)
        if m and not date:
            date = f"{m.group(3)}-{m.group(1)}-{m.group(2)}"
        m = re.match(r"^Ballots Cast - (DEMOCRAT|REPUBLICAN) ([\d,]+) ([\d,]+) ([\d,]+) ([\d,]+)$", t)
        if m:
            cast[m.group(1)] = [int(m.group(k).replace(",", "")) for k in (2, 3, 4, 5)]      # total, Election Day, Early Voting, Mail
        if R_STATE.match(t):
            if t in out:
                raise SystemExit(f"Rhode Island (state races): the summary report prints {t} twice")
            cur, in_cands = out.setdefault(t, {"cands": [], "cast": None, "contest": None}), True
            continue
        if cur is None:
            continue
        m = re.match(r"^(Total Votes Cast|Contest Totals) ([\d,]+) [\d.]+% ([\d,]+) ([\d,]+) ([\d,]+)$", t)
        if m:
            figs = [int(m.group(k).replace(",", "")) for k in (2, 3, 4, 5)]
            if m.group(1) == "Total Votes Cast":
                cur["cast"] = figs[0]
            else:
                cur["contest"] = figs                                    # total, Election Day, Early Voting, Mail
            in_cands = False
            if m.group(1) == "Contest Totals":
                cur = None
            continue
        m = re.match(r"^(.+?) ([\d,]+) [\d.]+% ([\d,]+) ([\d,]+) ([\d,]+)$", t)
        if m and in_cands and not re.match(r"^(Overvotes|Undervotes|Precincts|Registered|Ballots)", t):
            cur["cands"].append((m.group(1), int(m.group(2).replace(",", "")), [int(m.group(k).replace(",", "")) for k in (3, 4, 5)]))
    if not any("OFFICIAL RESULTS" in h for h in head):
        raise SystemExit(f"Rhode Island (state races): {os.path.basename(path)} is not headed OFFICIAL RESULTS")
    return out, cast, date


def check_results(results, report, cast, town_county):
    """Every reconciliation the loader promises; returns (candidates checked, list of problems)."""
    checked, problems = 0, []
    for c in results["contests"]:
        rep = report.get(c["title"])
        if rep is None:
            problems.append(f"{c['title']}: not in the summary report")
            continue
        if len(rep["cands"]) != len(c["candidates"]):
            problems.append(f"{c['title']}: the report lists {len(rep['cands'])} candidates, the results service {len(c['candidates'])}")
        total = sum(x["votes"] for x in c["candidates"])
        if rep["cast"] != total or c["vote_total"] != total:
            problems.append(f"{c['title']}: Total Votes Cast {rep['cast']}, service total {c['vote_total']}, candidates sum to {total}")
        if c["units"][0] != c["units"][1]:
            problems.append(f"{c['title']}: {c['units'][0]} of {c['units'][1]} towns reported")
        for town in c["towns"]:
            if fold(town) not in town_county:
                problems.append(f"{c['title']}: the results name a town the Census file does not: {town}")
        for x in c["candidates"]:
            hit = [r for r in rep["cands"] if same_name(r[0], x["name"])]
            if len(hit) != 1 or hit[0][1] != x["votes"]:
                problems.append(f"{c['title']}: {x['name']} has {x['votes']} votes in the results service and "
                                f"{hit[0][1] if len(hit) == 1 else 'no single line'} in the summary report")
                continue
            groups = [x["groups"].get(g) for g in ("Election Day", "Early Voting", "Mail Ballots")]
            if groups != hit[0][2] or sum(g or 0 for g in groups) != x["votes"]:
                problems.append(f"{c['title']}: {x['name']}'s Election Day, Early Voting and Mail Ballots votes do not agree")
            towns = sum(t.get(x["name"], 0) for t in c["towns"].values())
            if towns != x["votes"]:
                problems.append(f"{c['title']}: {x['name']}'s towns add up to {towns}, not {x['votes']}")
            checked += 1
        if contest_key(c["title"])[2]:
            # a statewide contest was on every party ballot but the federal-only ones (mail ballots, the results' "Federal" unit,
            # which only the Congress contests carry): Contest Totals + those = Ballots Cast, the difference all in Mail Ballots
            word, fed = BOARD_WORD[c["code"]], (results.get("federal_only") or {}).get(c["code"])
            want = cast.get(word)
            got = rep["contest"]
            if not want or not got or fed is None or got[0] + fed != want[0] or got[1:3] != want[1:3] or got[3] + fed != want[3]:
                problems.append(f"{c['title']}: Contest Totals {got} and {fed} federal-only ballots do not make the report's "
                                f"Ballots Cast - {word} {want}")
    seen = {c["title"] for c in results["contests"]}
    for t in report:
        if t not in seen:
            problems.append(f"{t}: in the summary report but not in the results service")
    return checked, problems


# ------------------------------------------------------------------------------------------------ the November list

def list_office(text):
    """What office a saved cell or heading names: a race key stem (SS, SH, GOV ...), "federal", or None."""
    t = " ".join(fold(text).split())
    if re.search(r"\bin congress\b|\bunited states\b|\bu s (senat|house|represent)|\bpresident\b", t):
        return "federal"
    if re.search(r"\bsenat\w* in general assembly\b|\bstate senat", t):
        return "SS"
    if re.search(r"\brepresentative in general assembly\b|\bstate representative\b", t):
        return "SH"
    if re.search(r"\blieutenant governor\b|\blt governor\b", t):
        return "LTG"
    if re.search(r"\bgovernor\b", t):
        return "GOV"
    if re.search(r"\bsecretary of state\b", t):
        return "SOS"
    if re.search(r"\battorney general\b", t):
        return "AG"
    if re.search(r"\bgeneral treasurer\b", t):
        return "TREAS"
    return None


def district_of(*texts):
    for t in texts:
        m = re.search(r"(?:district|dist\.?)\s*(?:no\.?\s*)?0*(\d{1,2})\b", t or "", re.I) or re.fullmatch(r"\s*0*(\d{1,2})\s*", t or "")
        if m:
            return int(m.group(1))
    return None


def november_list(folder):
    """Every state-office row on the pages saved from vote.sos.ri.gov: only the allowlisted cells are kept."""
    files = sorted(os.path.join(folder, f) for f in os.listdir(folder)
                   if f.lower().endswith((".html", ".htm", ".csv", ".xlsx"))) if os.path.isdir(folder) else []
    rows, headings, other = [], [], {"federal": 0, "other offices": 0}
    for path in files:
        if path.lower().endswith((".html", ".htm")):
            title, table = html_rows(open(path, "rb").read())
            headings += title
        else:
            table = [([os.path.basename(path)], cells) for cells in sheet_rows(path)]
        idx, band = None, ""
        for context, cells in table:
            found = column_map(cells)
            if found:
                idx, band = found, ""
                continue
            if idx is None or not any(cells):
                continue
            filled = [c for c in cells if c]
            if len(filled) == 1 and (re.search(r"\bdistrict\b", filled[0], re.I) or list_office(filled[0])):
                band = filled[0]                                       # a heading row across the table: "Senate District 5"
                continue
            if len(cells) <= max(idx.values()):
                continue
            row = {f: cells[i] for f, i in idx.items()}                # the allowlisted cells only; the rest of the row is dropped here
            if not row["name"]:
                continue
            office_text = row.get("office") or next((t for t in [band] + context[::-1] if list_office(t)), "")
            stem = list_office(office_text)
            if stem is None:
                other["other offices"] += 1
                continue
            if stem == "federal":
                other["federal"] += 1
                continue
            if stem in ("SS", "SH"):
                d = district_of(row.get("office", ""), row.get("district", ""), band)
                top = SENATE_SEATS if stem == "SS" else HOUSE_SEATS
                if d is None or not 1 <= d <= top:
                    raise SystemExit(f"Rhode Island (state races): a saved {'Senate' if stem == 'SS' else 'House'} row in "
                                     f"{os.path.basename(path)} gives no district from 1 to {top}")
                key = f"{stem}{d}"
            else:
                key = stem
            rows.append({"key": key, "name": row["name"], "party": row.get("party", ""), "status": row.get("status"),
                         "order": row.get("order", ""), "file": os.path.basename(path)})
    return files, rows, headings, other


# ------------------------------------------------------------------------------------------------ the roster

def roster(path):
    """Sitting legislators and the statewide officials the roster carries: ids, names, party, chamber and district only
    (the roster's contact columns are never selected)."""
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
    """A name on the results or the list fits a roster person: the same family name and a given name that fits. Both
    sides must carry a given name (the roster's other names include the family name alone, which would fit anyone)."""
    cand = name_parts(name)
    return bool(cand[0]) and any(fits(cand, f) for f in forms(p) if f[0])


# ------------------------------------------------------------------------------------------------ helpers

def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def mtime(path):
    return dt.datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d")


def dbf_records(path):
    import shapefile                                                     # pyshp, in the kit's environment
    z = zipfile.ZipFile(path)
    dbf = next(n for n in z.namelist() if n.endswith(".dbf"))
    return [r.as_dict() for r in shapefile.Reader(dbf=io.BytesIO(z.read(dbf))).iterRecords()]


def looks_like_contact(text, strict=False):
    t = str(text or "")
    return bool(EMAIL.search(t) or PHONE.search(t) or WEB.search(t) or (strict and (STREET.search(t) or ZIP.search(t))))


# ------------------------------------------------------------------------------------------------ loading

def load(db_path, say=print, folder=FOLDER, gfolder=GFOLDER, roster_db=ROSTER, county_zip=COUNTY_ZIP, cousub_zip=COUSUB_ZIP):
    from states import net
    net.patient_lookups()
    os.makedirs(folder, exist_ok=True)
    checks = []

    # 1. the official primary results (state contests), the summary report, and the Census codes
    rpath = os.path.join(folder, RESULTS_JSON)
    if os.path.exists(rpath) and time.time() - os.path.getmtime(rpath) < 30 * 86400:
        results = json.load(open(rpath, encoding="utf-8"))
    else:
        results = fetch_results(say)
    if "federal_only" not in results:
        results["federal_only"] = federal_only(say)
        json.dump(results, open(rpath, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if not results.get("official") or results.get("date") != PRIMARY:
        raise SystemExit("Rhode Island (state races): the cached primary results are not the official September 9 results")
    ppath = os.path.join(folder, "Prim26_Summary.pdf")
    net.download(SUMMARY_PDF, ppath, 30, say=say)
    if open(ppath, "rb").read(5) != b"%PDF-":
        raise SystemExit("Rhode Island (state races): Prim26_Summary.pdf is not a PDF")
    report, cast, printed = summary_report(ppath)
    net.download(COUNTY_URL, county_zip, 365, say=say)
    net.download(COUSUB_URL, cousub_zip, 365, say=say)
    counties = {r["GEOID"]: r["NAME"] for r in dbf_records(county_zip) if r["STATEFP"] == FIPS}
    towns = [r for r in dbf_records(cousub_zip) if r["STATEFP"] == FIPS]
    town_county = {fold(r["NAME"]): FIPS + r["COUNTYFP"] for r in towns}
    if len(counties) != COUNTIES or len(town_county) != TOWNS or not set(town_county.values()) <= set(counties):
        raise SystemExit(f"Rhode Island (state races): the Census files give {len(counties)} counties and {len(town_county)} towns, "
                         f"not {COUNTIES} and {TOWNS}")
    checked, problems = check_results(results, report, cast, town_county)
    if problems:
        for p in problems:
            say(f"      CHECK: {p}")
        raise SystemExit(f"Rhode Island (state races): {len(problems)} primary figures do not reconcile (listed above); nothing written")

    # 2. the races: the five general officers and every seat of both chambers
    legs, offs = roster(roster_db)
    by_seat = {}
    for p in legs:
        k = ("SS" if p["chamber"] == "Senate" else "SH" if p["chamber"] == "House" else None, str(int(p["district"])))
        if k[0] is None:
            raise SystemExit(f"Rhode Island (state races): the roster has a sitting member in a chamber not read ({p['chamber']})")
        if k in by_seat:
            raise SystemExit(f"Rhode Island (state races): the roster has two sitting members for {k[0]}{k[1]}")
        by_seat[k] = p
    if sum(1 for k in by_seat if k[0] == "SS") != SENATE_SEATS or sum(1 for k in by_seat if k[0] == "SH") != HOUSE_SEATS:
        checks.append(f"the roster has {sum(1 for k in by_seat if k[0] == 'SS')} sitting senators and "
                      f"{sum(1 for k in by_seat if k[0] == 'SH')} representatives, not {SENATE_SEATS} and {HOUSE_SEATS} (vacancies?)")
    races = {}

    def add(key, level, kind, office, jur, jur_id, district, holder, notes):
        rid = f"2026-{STATE}-{key}"
        races[rid] = {"race_id": rid, "state": STATE, "level": level, "office_kind": kind, "office": office, "jurisdiction": jur,
                      "jurisdiction_id": jur_id, "county_ids": None, "district": district, "seat": None, "special": 0, "partisan": 1,
                      "holder_id": holder["id"] if holder else None, "holder_name": (holder.get("full") or
                      f"{holder.get('first') or ''} {holder.get('last') or ''}".strip()) if holder else None,
                      "holder_party": holder["party"] if holder else None, "election_date": GENERAL, "note": list(notes),
                      "_key": key, "_kind": kind, "_holder": holder}

    for rname, (key, kind, office, roster_office) in STATEWIDE.items():
        holder = offs.get(roster_office) if roster_office else None
        notes = [LTG_NOTE] if key == "LTG" else []
        if holder is None:
            notes.append(NO_HOLDER)
        add(key, "statewide", kind, office, NAME, FIPS, None, holder, notes)
    for d in range(1, SENATE_SEATS + 1):
        add(f"SS{d}", "legislature", "state_senate", S_OFFICE, f"Senate District {d}", f"{STATE}-{d}", str(d), by_seat.get(("SS", str(d))), [SENATE_NOTE])
    for d in range(1, HOUSE_SEATS + 1):
        add(f"SH{d}", "legislature", "state_house", H_OFFICE, f"House District {d}", f"{STATE}-{d}", str(d), by_seat.get(("SH", str(d))), [HOUSE_NOTE])
    for rid, r in races.items():
        if r["level"] == "legislature" and r["_holder"] is None:
            r["note"].append("The roster used here lists no sitting member for this seat.")

    # which races the primary results reach; every statewide office must have a party contest, every district is looked for
    contests_by_race = {}
    for c in results["contests"]:
        rid = f"2026-{STATE}-{c['race']}"
        if rid not in races:
            raise SystemExit(f"Rhode Island (state races): the primary results carry {c['title']}, which is not a seat read here")
        if (rid, c["code"]) in contests_by_race:
            raise SystemExit(f"Rhode Island (state races): the primary results carry {c['title']} twice")
        contests_by_race[(rid, c["code"])] = c
    reached = {rid for rid, _code in contests_by_race}
    for rid, r in races.items():
        if rid not in reached:
            if r["level"] == "statewide":
                raise SystemExit(f"Rhode Island (state races): no party contest for {r['office']} in the primary results; is it on the 2026 ballot?")
            checks.append(f"{rid}: no party contest in the primary results (the seat is still elected; any candidate would be independent)")

    # 3. the primary: fields (two candidates or more) with official votes; the nominee of every party contest for the notes
    cands, nominee, fields, matched = [], {}, 0, []

    def mark_incumbent(rows, race):
        holder = race["_holder"]
        if holder is None:
            return
        fit = [row for row in rows if person_fits(row[3], holder)]
        if len(fit) == 1:
            fit[0][7], fit[0][12] = 1, holder["id"]
            matched.append(f"{race['race_id']} {fit[0][1]}: {fit[0][3]} -> {holder['id']} (holds this seat)")
        elif len(fit) > 1:
            checks.append(f"{race['race_id']} {rows[0][1]}: more than one name fits the sitting member; none is marked")

    people = legs + list(offs.values())

    def mark_other_seat(rows, race):
        """A candidate who sits today in another seat (a representative running for attorney general): tied to the roster
        only when the name fits exactly one sitting legislator or general officer, of the same party, who is not this
        seat's own holder. Not marked incumbent."""
        for row in rows:
            if row[12] or row[8]:
                continue
            fit = [p for p in people if person_fits(row[3], p)]
            if len(fit) != 1 or fit[0] is race["_holder"] or party_code(fit[0]["party"]) != row[5]:
                continue
            p = fit[0]
            row[12] = p["id"]
            where = (f"as {OFFICIAL_WORDS.get(p['office'], p['office'])}" if p.get("office") else
                     f"in the Rhode Island {'Senate' if p['chamber'] == 'Senate' else 'House of Representatives'}, District {int(p['district'])}")
            row[14].append(f"Serves today {where} (the roster used here).")
            matched.append(f"{race['race_id']} {row[1]}: {row[3]} -> {p['id']} (serves today {where})")

    for (rid, code), c in sorted(contests_by_race.items()):
        race = races[rid]
        listed = [x for x in c["candidates"] if not x["write_in"]]
        top = sorted(c["candidates"], key=lambda x: -x["votes"])
        if len(top) > 1 and top[0]["votes"] == top[1]["votes"]:
            raise SystemExit(f"Rhode Island (state races): {c['title']} is tied at the top; the loader does not decide a tie")
        if top:
            nominee[(rid, code)] = top[0]["name"].rstrip("*").strip()
        if len(listed) < 2:
            continue
        fields += 1
        total = sum(x["votes"] for x in c["candidates"])
        rows = []
        for x in c["candidates"]:
            name = x["name"].rstrip("*").strip()
            notes = [ENDORSED] if x["name"].endswith("*") else []
            if x["write_in"]:
                notes.append(WRITE_IN)
            rows.append([rid, f"primary-{CODE[code]}", PRIMARY, name, "Write-in" if x["write_in"] else PARTY[code],
                         "W" if x["write_in"] else party_code(PARTY[code]), None, 0, int(x["write_in"]), x["votes"],
                         round(100 * x["votes"] / total, 1) if total else None, "advanced" if x is top[0] else "lost", None, SRC_RESULTS,
                         notes])
        mark_incumbent(rows, race)
        mark_other_seat(rows, race)
        cands += rows

    # 4. the November list, if a copy has been saved
    gfiles, glist, headings, other_rows = november_list(gfolder)
    general, gone, unknown, write_ins, nominee_on_list = [], [], set(), 0, {}
    if glist and not any(r["status"] is not None for r in glist) and not any(re.search(r"general", h, re.I) for h in headings):
        raise SystemExit("Rhode Island (state races): the saved candidate list has no status column and its heading does not say it is "
                         "the general election list; save the page that shows each candidate's status")
    has_order = any(str(r["order"]).strip() for r in glist)
    seen = set()
    for r in glist:
        rid = f"2026-{STATE}-{r['key']}"
        status = squash(r["status"] or "")
        if status and GONE.search(status):
            gone.append(rid)
            continue
        if status and not ON.search(status):
            unknown.add(status)
            continue
        name, notes = shown(r["name"])
        party = PARTY_WORDS.get(squash(r["party"]).upper(), ordinary(r["party"])) or "Independent"
        write_in = int(bool(re.search(r"write", f"{r['party']} {status}", re.I)))
        if (rid, fold(name)) in seen:
            continue                                   # the same candidate on two saved pages
        seen.add((rid, fold(name)))
        if write_in:
            write_ins += 1
            notes.append(WRITE_IN)
        place = int(r["order"]) if has_order and str(r["order"]).strip().isdigit() and not write_in else None
        code = "W" if write_in else party_code(party)
        if code == "O":
            code = "I"                                 # not a recognised party's nominee: an independent candidate's "political principle"
        if code in ("D", "R") and not write_in:
            if (rid, code) in nominee_on_list:
                raise SystemExit(f"Rhode Island (state races): the saved list prints two {party} candidates for {rid}; save the general "
                                 "election list, not a primary's")
            nominee_on_list[(rid, code)] = name
        general.append([rid, "general", GENERAL, name, party, code, place, 0, write_in, None, None, None, None, SRC_LIST, notes])
    if unknown:
        raise SystemExit(f"Rhode Island (state races): statuses on the saved candidate list that are not read: {sorted(unknown)}")
    listed_races = {g[0] for g in general} | set(gone)
    listed_kinds = {races[rid]["_kind"] for rid in listed_races}
    for rid in sorted({g[0] for g in general}):
        mark_incumbent([g for g in general if g[0] == rid], races[rid])
        mark_other_seat([g for g in general if g[0] == rid], races[rid])
    if general:
        for (rid, pcode), name in sorted(nominee.items()):
            if rid not in listed_races:
                continue
            code = pcode[0]
            on = nominee_on_list.get((rid, code))
            if on and fits(name_parts(on), name_parts(name)):
                continue
            checks.append(f"{rid}: the official results' {PARTY[pcode]} nominee, {name}, is not on the November list"
                          + (f" (the list's {PARTY[pcode]} candidate is {on})" if on else ""))
            final = f"primary-{pcode}"
            for c in cands:
                if c[0] == rid and c[1] == final and c[3] == name:
                    c[14].append(OTHER_ON_LIST if on else NOT_ON_LIST)
        cands = general + cands

    # 5. per race: its counties, and what its note says about the list
    all_geoids = sorted(counties)
    for rid, r in races.items():
        if r["level"] == "statewide":
            r["county_ids"] = json.dumps(all_geoids)
        else:
            geo = {town_county[fold(t)] for (rr, _code), c in contests_by_race.items() if rr == rid for t in c["towns"]}
            r["county_ids"] = json.dumps(sorted(geo)) if geo else None
        on_list = any(c[0] == rid and c[1] == "general" for c in cands)
        if r["_kind"] not in listed_kinds:
            r["note"].append(NO_LIST)
            noms = [(code, nominee[(rid, code)]) for code in ("DEM", "REP") if (rid, code) in nominee]
            if noms:
                r["note"].append("The official September 9 primary results give the parties' nominees: " + "; ".join(
                    f"{n} ({PARTY[code]})" for code, n in noms) + ". The list would add any independent candidates and drop anyone who withdrew.")
        elif not on_list:
            r["note"].append(NONE_ON_LIST)
            checks.append(f"{rid}: no candidates on the November list")

    # 6. the last look at every stored text: nothing that looks like a contact detail reaches the database
    for c in cands:
        c[14] = " ".join(c[14]) or None
        if NAME_BAD.search(c[3]) or looks_like_contact(c[3], strict=True) or looks_like_contact(c[4], strict=True) \
                or looks_like_contact(c[14], strict=True):
            raise SystemExit(f"Rhode Island (state races): a stored cell for {c[0]} failed the contact-detail check (not shown); read the file again")
    for r in races.values():
        if looks_like_contact(" ".join(r["note"]), strict=True) or looks_like_contact(r["holder_name"], strict=True):
            raise SystemExit(f"Rhode Island (state races): the note or holder for {r['race_id']} failed the contact-detail check (not shown)")
    keys = [(c[0], c[1], c[3]) for c in cands]
    if len(keys) != len(set(keys)):
        raise SystemExit("Rhode Island (state races): two candidate rows share race, election and name")
    on_ballot = len(glist) - len(gone) - len(unknown)
    dupes = on_ballot - len(general)
    if dupes < 0:
        raise SystemExit(f"Rhode Island (state races): {on_ballot} rows on the list, {len(general)} stored")

    # 7. write Rhode Island's rows only, in one transaction
    race_rows = [tuple(" ".join(r["note"]) or None if k == "note" else r[k] for k in (
        "race_id", "state", "level", "office_kind", "office", "jurisdiction", "jurisdiction_id", "county_ids", "district", "seat", "special",
        "partisan", "holder_id", "holder_name", "holder_party", "election_date", "note")) for r in races.values()]
    place_rows = [("county", g, f"{n} County", json.dumps([g]), SRC_COUNTY) for g, n in sorted(counties.items())]
    for rid, r in sorted(races.items()):
        if r["level"] == "legislature":
            place_rows.append(("senate" if r["_kind"] == "state_senate" else "house", f"{STATE}-{r['district']}", r["jurisdiction"],
                               r["county_ids"], SRC_RESULTS if r["county_ids"] else SRC_ROSTER))
    gen = [c for c in cands if c[1] == "general"]
    prim = [c for c in cands if c[1] != "general"]
    skipped = results.get("skipped") or {}
    sources = [
        (SRC_ROSTER, STATE, "member roster", "Open States people project (CC0), as loaded into state_ri.sqlite",
         "Sitting Rhode Island legislators and general officers", "https://github.com/openstates/people", "", mtime(roster_db), sha(roster_db),
         len(legs) + len(offs), "Who holds each seat today, and which candidate is the seat's sitting member (same chamber and district, or "
         "the same office; the name fits; one fit only). A candidate for another seat is tied to a sitting member (not marked incumbent) "
         "only when the name fits exactly one sitting legislator or general officer, of the same party. The roster's general officers are the Governor, Lieutenant Governor, Secretary "
         "of State and Attorney General only; for the General Treasurer the holder is left empty. Names, party and ids only; the roster's "
         "contact columns are never selected."),
        (SRC_COUNTY, STATE, "county codes", "U.S. Census Bureau", "Cartographic boundary file, counties, 2024 (1:500,000)", COUNTY_URL,
         "2024", mtime(county_zip), sha(county_zip), len(counties), "Five-digit county codes (GEOID) for Rhode Island's five counties."),
        (SRC_COUSUB, STATE, "town codes", "U.S. Census Bureau", "Cartographic boundary file, county subdivisions, Rhode Island, 2024 (1:500,000)",
         COUSUB_URL, "2024", mtime(cousub_zip), sha(cousub_zip), len(towns),
         "Rhode Island's 39 cities and towns and the county each lies in, matched by name to the results' town rows (every one matched). "
         "The counties a district reaches are those of the towns its September 9 primary contests were counted in (derived)."),
        (SRC_RESULTS, STATE, "official results", AGENCY_BOE,
         f"{results['name']} (September 9, 2026): official results, state offices", SITE, (results.get("last_updated") or "")[:10],
         mtime(rpath), sha(rpath), sum(len(c["candidates"]) for c in results["contests"]),
         f"From the Board's election results site's data service (marked isOfficialResults), statewide and town by town, the same service "
         f"the federal loader reads; linked from {BOARD_PAGE}. {len(results['contests'])} state contests read (general officers, Senate, "
         f"House), kept as figures only in {RESULTS_JSON}; every candidate checked ({checked}): the towns add up to the statewide figure, "
         "the count groups add up and equal the summary report's, and each contest's total equals the sum of its candidates. No write-in "
         "votes are reported for these contests. The asterisk the results print after the party-endorsed candidate's name is taken off "
         "and said in the note. A field is a party primary with two candidates or more; a party's only candidate is its nominee without a "
         f"contest and is named in the race's note. Not read here: {skipped.get('federal', 0)} Congress contests (the federal loader's), "
         f"{skipped.get('party offices', 0)} party committee contests (party offices, not on the November ballot) and "
         f"{skipped.get('local', 0)} city and town contests (local)."),
        (SRC_SUMMARY, STATE, "official results", AGENCY_BOE,
         "Summary Results Report, OFFICIAL RESULTS, Primary Election 2026, September 9, 2026 (Prim26_Summary.pdf)", SUMMARY_PDF, printed,
         mtime(ppath), sha(ppath), sum(len(v["cands"]) for v in report.values()),
         "Control: each state candidate's TOTAL, Election Day, Early Voting and Mail Ballots votes equal the results service's; Total Votes "
         "Cast equals the sum of the candidates; each statewide contest's Contest Totals, plus the party's federal-only mail ballots "
         "(the votes in the results' Federal unit of its Senator in Congress contest, a unit only the Congress contests carry: "
         f"DEMOCRAT {results['federal_only']['DEM']:,}, REPUBLICAN {results['federal_only']['REP']:,}), equals the report's Ballots Cast "
         f"for the party (DEMOCRAT {cast['DEMOCRAT'][0]:,}, REPUBLICAN {cast['REPUBLICAN'][0]:,}), the difference falling wholly in Mail "
         "Ballots."),
    ]
    if gfiles:
        sources.append((
            SRC_LIST, STATE, "official candidate list", AGENCY_SOS,
            "Candidates in Upcoming Elections: state offices, November 3, 2026 General Election", SOS_PAGE, "",
            max(mtime(f) for f in gfiles), hashlib.sha256(b"".join(open(f, "rb").read() for f in gfiles)).hexdigest(), len(glist),
            f"Saved in a browser (the site answers scripts with a Cloudflare challenge): {', '.join(os.path.basename(f) for f in gfiles)} "
            "(the fingerprint is of the files joined in name order). Only the name, party or political principle, office, district, "
            "status and ballot position columns read; addresses, telephones, e-mail and websites never read. Ballot order only where the "
            f"list gives a position. Withdrawn, not qualified or defeated, left off: {len(gone)}. Write-in candidates listed: {write_ins}. "
            f"Rows for Congress ({other_rows['federal']}) and other offices ({other_rows['other offices']}) not read here."))
    con = sqlite3.connect(db_path)
    con.executescript("""
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
""")
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

    # 8. say what happened, and what is still waiting
    kind_n = lambda rows, k: sum(1 for c in rows if races[c[0]]["_kind"] == k)
    n_state = sum(1 for r in races.values() if r["level"] == "statewide")
    n_fields = lambda k: sum(1 for (rid, _code), c in contests_by_race.items() if races[rid]["_kind"] == k
                             and sum(1 for x in c["candidates"] if not x["write_in"]) > 1)
    say(f"    Rhode Island state offices: {len(races)} races ({n_state} statewide; {sum(1 for r in races.values() if r['_kind'] == 'state_senate')} "
        f"Senate; {sum(1 for r in races.values() if r['_kind'] == 'state_house')} House); {len(gen)} candidates on the November list "
        f"(statewide {sum(1 for c in gen if races[c[0]]['level'] == 'statewide')}, Senate {kind_n(gen, 'state_senate')}, House "
        f"{kind_n(gen, 'state_house')}); {fields} primary fields (statewide {sum(n_fields(k) for k in ('governor', 'lieutenant_governor', 'secretary_of_state', 'attorney_general', 'state_treasurer'))}, "
        f"Senate {n_fields('state_senate')}, House {n_fields('state_house')}), {len(prim)} primary rows (statewide "
        f"{sum(1 for c in prim if races[c[0]]['level'] == 'statewide')}, Senate {kind_n(prim, 'state_senate')}, House {kind_n(prim, 'state_house')}); "
        f"{len(results['contests'])} party contests reconciled ({checked} candidates: towns, count groups, summary report)")
    if not gfiles:
        say(f"      waiting: the November 3, 2026 list. The Department of State's candidate pages ({SOS_PAGE}) answer scripts with a "
            f"Cloudflare challenge; save the pages for Governor, Lieutenant Governor, Secretary of State, Attorney General, General "
            f"Treasurer, Senator in General Assembly and Representative in General Assembly (November 3, 2026 General Election) into {gfolder}")
    else:
        missing = sorted(k for k in {r["_kind"] for r in races.values()} if k not in listed_kinds)
        say(f"      list read: {len(gfiles)} file(s), {len(glist)} state rows ({len(gone)} withdrawn or defeated left off, {max(dupes, 0)} repeated "
            f"on two pages), {other_rows['federal']} Congress rows and {other_rows['other offices']} other rows not read here"
            + (f"; offices with no saved page: {', '.join(missing)}" if missing else ""))
    for line in matched:
        say(f"      matched: {line}")
    for line in checks:
        say(f"      check: {line}")
    return dict(races=len(races), general=len(gen), primary=len(prim), fields=fields, checks=checks, files=gfiles)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Rhode Island's state races on the November 3, 2026 ballot")
    ap.add_argument("db", help="the state-and-local ballot database to write Rhode Island's rows into")
    ap.add_argument("--general", default=GFOLDER, help="the folder holding the saved November candidate pages")
    a = ap.parse_args()
    load(a.db, gfolder=a.general)
