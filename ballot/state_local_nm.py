"""
ballot/state_local_nm.py - New Mexico's state races on the November 3, 2026 ballot: all 70 seats of the House of
Representatives, the one State Senate seat on this year's list (District 33), Governor and Lieutenant Governor (one
ticket in November, nominated in separate June primaries), Secretary of State, Attorney General, State Auditor, State
Treasurer, Commissioner of Public Lands, the Public Education Commission seats up this year, the Court of Appeals seat
elected this year and the retention votes for the Supreme Court and the Court of Appeals, with the June 2 party
primaries that chose the nominees. Written into ballot_local_2026.sqlite (never ballot_2026.sqlite), New Mexico's rows
only.

    python ballot/state_local_nm.py <database file> [--cache <folder>]

New Mexico elects its House every two years and its Senate for four years in presidential years (the last regular
Senate election was in 2024), so the whole House is up and the Senate only where the Secretary's list names a seat.

Sources, the New Mexico Secretary of State's own (the lists and results site the federal loader, ballot/lists/nm.py,
reads for Congress; this loader keeps the state rows):

  - The "2026 General Election Contest/Candidate List" of the candidate portal (candidateportal.servis.sos.state.nm.us,
    election 2917): a Telerik grid of every office in the state on one page. Columns are taken by their headings, and
    only these: Contest (printed twice: the first names the office with its district, the second the office alone),
    District, Name, Party, Ballot Order and Status. The grid also carries physical and mailing addresses, city, ZIP,
    phones, e-mail, websites, the filing county and the filing time; those cells are never turned into text, printed or
    kept. A row's office is read first, and a row outside the state races (Congress, county offices, district,
    magistrate, metropolitan, probate and municipal courts and their retention votes) is only counted by office; its
    other cells are never read. The kept columns of the state rows are cached as JSON in ballot_cache/nm/. Qualified is
    on the ballot; Disqualified and Withdrawn are left off, named in the race's note; any other status stops the loader.
    The list's own Ballot Order is kept (99 means no place: write-ins, retention votes, rows off the ballot). Parties
    are written out from the list's own key (the page's party menu). A name ending "(write-in)" is a declared write-in.
  - The portal's "2026 Primary Election Contest/Candidate List" (election 2911), read the same way: who was on each
    party's June 2 ballot, and in what order.
  - The results site (electionresults.sos.nm.gov, election 2911), headed "Official Results 2026 Primary June 2, 2026"
    and last updated 6/23/2026, the day the State Canvass Board certified the primary. Its own CSV exports for
    Statewide Offices (SW), Legislative (LGX) and Public Education Commission (ECX) are read; they hold contest, party,
    district, candidate and votes only. Checks: the page still says Official Results and never Unofficial; every
    precinct reported; each candidate's absentee, election day and early votes add up to the total; the site's
    percentages are shares of the candidates' votes; the names under each party contest are exactly that party's
    Qualified rows on the primary list; and every contest's county-by-county figures (the results page's own service,
    nmresultswebservice.azurewebsites.us, GetMapDataArchive) add up to its statewide totals. Those county rows also give
    the counties each House, Senate and Public Education Commission district reaches (county_ids). New Mexico counts
    write-in votes only for declared write-in candidates, listed among the candidates, so a field's total is its
    candidates' votes.
  - The Secretary's release of June 23, 2026 (the State Canvass Board certifies the primary and orders automatic
    recounts): only the list of recounted contests is read. State Representative District 66 (Republican) was one; its
    figures are the certified canvass, and the loader says so.
  - Today's holders from state_nm.sqlite (the Open States roster the state pages use): legislators serving now, by
    chamber and district, and the officials table (Governor, Lieutenant Governor, Attorney General). Only ids, names,
    parties, districts and start dates are read; the roster's contact columns are never selected. It does not carry the
    Secretary of State, Auditor, Treasurer, Commissioner of Public Lands, the Public Education Commission or judges.
  - County names and GEOIDs from the Census Bureau's 2024 county file (states_cache/census/), attribute table only.

A candidate is the sitting member (incumbent 1, state_member_id) only when the name fits the holder of that seat or
office and the fit is one to one. A candidate who holds another seat or office in the roster gets state_member_id with
incumbent 0 and a note, only when exactly one roster person of the same party fits. A judge standing for retention is
by definition the sitting judge, so that name is the holder and the incumbent.

A field is a party primary with two or more names printed on that party's ballot (a declared write-in beside one printed
name does not make one). The top vote-getter won the nomination (outcome "advanced"), and the November list must agree:
the party's row there, withdrawn or not, is that name; where the nominee withdrew and another name stands, both notes
say so. pct is the share of that party primary's votes.

The privacy rule: from any list only office, district, name, party, ballot order, status and votes are read. No
address, city, ZIP code, phone, website, e-mail or treasurer is read, printed, logged, cached or stored, and the page
gets names as filed (in ordinary capitals), office, district, party, ballot order and write-in marks only.
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
import zipfile
from collections import Counter, defaultdict
from urllib.error import HTTPError, URLError

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from ballot.common import fold, name_parts, party_code          # noqa: E402
from ballot.lists.nm import CERTIFIED_NEWS, LISTS, PORTAL, RESULTS, WRITE_MARK, county_check, ordinary, text   # noqa: E402
from ballot.lists.tx import proper                              # noqa: E402
from ballot.match import fits                                   # noqa: E402
from states import net                                          # noqa: E402

STATE, FIPS, NAME = "NM", "35", "New Mexico"
GENERAL, PRIMARY = "2026-11-03", "2026-06-02"
EID = "2911"
RESULT_TYPES = {"SW": "Statewide Offices", "LGX": "Legislative", "ECX": "Public Education Commission"}
RESULTS_PAGE = RESULTS + "resultsSW.aspx?type={t}&map=CTY&eid=" + EID
RESULTS_CSV = RESULTS + "resultsCSV.aspx?text=All&type={t}&map=CTY&eid=" + EID
COUNTY_SERVICE = ("https://nmresultswebservice.azurewebsites.us/NMResultsAjax.svc/GetMapDataArchive?type={t}&category=CTY"
                  "&raceID={race}&osn={osn}&county=0&party={party}&electionID=" + EID)
HEADING = "Official Results 2026 Primary June 2, 2026"
ROSTER_DB = os.path.join(HERE, "state_nm.sqlite")
COUNTY_ZIP = os.path.join(HERE, "states_cache", "census", "cb_2024_us_county_500k.zip")
COUNTY_URL = "https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_county_500k.zip"
CACHE = os.path.join(HERE, "ballot_cache", "nm")

# the only grid columns ever read; every other cell (addresses, city, ZIP, phones, e-mail, websites) is never unescaped
KEEP = ("Contest", "District", "Name", "Party", "Ballot Order", "Status")
ON, OFF = ("Qualified",), ("Disqualified", "Withdrawn")
NO_PLACE = "99"
RESULT_COLUMNS = ("RaceID", "RaceName", "PartyCode", "AreaNum", "CandidateID", "CandidateName", "VoteFor", "CandidateVotes",
                  "CandidatePercentage", "PrecinctsReporting", "CandidateAbsenteeVotes", "CandidateElectionDayVotes",
                  "CandidateEarlyVotes")

STATEWIDE = {
    "Governor and Lieutenant Governor": ("GOV", "governor", "Governor and Lieutenant Governor"),
    "Governor": ("GOV", "governor", "Governor and Lieutenant Governor"),
    "Lieutenant Governor": ("LTG", "lieutenant_governor", "Lieutenant Governor"),
    "Secretary of State": ("SOS", "secretary_of_state", "Secretary of State"),
    "Attorney General": ("AG", "attorney_general", "Attorney General"),
    "State Auditor": ("AUD", "state_auditor", "State Auditor"),
    "State Treasurer": ("TREAS", "state_treasurer", "State Treasurer"),
    "Commissioner of Public Lands": ("LAND", "land_commissioner", "Commissioner of Public Lands"),
}
ROSTER_OFFICE = {"GOV": "governor", "LTG": "lt_governor", "AG": "attorney general", "SOS": "secretary of state"}
LEGISLATURE = {"State Senator": ("SS", "state_senate", "State Senator", "Senate", 42),
               "State Representative": ("SH", "state_house", "State Representative", "House", 70)}
RETENTION = {"Judicial Retention Justice of the Supreme Court": ("SCRET", "supreme_court_retention",
                                                                 "Justice of the Supreme Court (retention vote)"),
             "Judicial Retention Judge of the Court of Appeals": ("COARET", "court_of_appeals_retention",
                                                                  "Judge of the Court of Appeals (retention vote)")}
# offices on the lists that are not state races here: counted by office, their other cells never read
OUT_OF_SCOPE = re.compile(r"^(?:United States |County |District Court Judge|Magistrate Judge|Judge of the Metropolitan Court|"
                          r"Probate Judge|Municipal Judge|Judicial Retention (?:District Court Judge|Judge of the Metropolitan Court))")
CHAMBER_WORDS = {"Senate": "the New Mexico Senate", "House": "the New Mexico House of Representatives"}
NONPARTISAN = "Nonpartisan office"
CAPS = "New Mexico's list prints names in capitals; they are shown here in ordinary capitals."
WRITE_IN = "Write-in candidate: the name is not printed on the ballot."

SRC_GENERAL = "nm-sos-2026-sl-general-list"
SRC_PRIMARY = "nm-sos-2026-sl-primary-list"
SRC_RESULTS = {t: f"nm-sos-2026-sl-primary-results-{t.lower()}" for t in RESULT_TYPES}
SRC_RELEASE = "nm-sos-2026-primary-certification"
SRC_ROSTER = "nm-openstates-roster"
SRC_COUNTY = "nm-census-2024-counties"

SCHEMA = """
CREATE TABLE IF NOT EXISTS sl_races (race_id TEXT PRIMARY KEY, state TEXT NOT NULL, level TEXT NOT NULL, office_kind TEXT NOT NULL, office TEXT NOT NULL, jurisdiction TEXT, jurisdiction_id TEXT, county_ids TEXT, district TEXT, seat TEXT, special INTEGER NOT NULL DEFAULT 0, partisan INTEGER NOT NULL, holder_id TEXT, holder_name TEXT, holder_party TEXT, election_date TEXT NOT NULL, note TEXT);
CREATE TABLE IF NOT EXISTS sl_candidates (race_id TEXT NOT NULL, election TEXT NOT NULL, election_date TEXT, name TEXT NOT NULL, party TEXT, party_code TEXT, ballot_order INTEGER, incumbent INTEGER NOT NULL DEFAULT 0, write_in INTEGER NOT NULL DEFAULT 0, votes INTEGER, pct REAL, outcome TEXT, state_member_id TEXT, source_id TEXT, note TEXT, PRIMARY KEY (race_id, election, name));
CREATE TABLE IF NOT EXISTS sl_sources (source_id TEXT PRIMARY KEY, state TEXT, kind TEXT, agency TEXT, title TEXT, url TEXT, published TEXT, fetched TEXT, sha256 TEXT, rows INTEGER, note TEXT);
CREATE TABLE IF NOT EXISTS sl_places (kind TEXT NOT NULL, id TEXT NOT NULL, name TEXT NOT NULL, county_ids TEXT, source_id TEXT, PRIMARY KEY (kind, id));
"""


def nkey(name):
    """A name for matching only: write-in mark off, letters folded, spaces squeezed ('POPE, JR' = 'POPE JR')."""
    return " ".join(fold(WRITE_MARK.sub("", name or "")).split())


def sha_of(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest() if path and os.path.exists(path) else ""


def day_of(path):
    return dt.date.fromtimestamp(os.path.getmtime(path)).isoformat() if path and os.path.exists(path) else ""


def ask(url, accept, what, expect=None):
    """One address, asked at most three times (a refusal, or a page without what it should hold, such as a bot check,
    is not asked a fourth time). The candidate portal's pages load Google's reCAPTCHA script for a form of their own
    while serving the list to anyone, so a page is judged by the content it must hold, never by that word."""
    last = None
    for attempt in range(3):
        try:
            body = net.get(url, accept=accept)
            if expect is not None and expect not in body:
                last = "the page came back without its expected content (a bot check or a changed page)"
            else:
                return body
        except (HTTPError, URLError, OSError) as e:
            last = e
        if attempt < 2:
            time.sleep(5 * (attempt + 1))
    raise SystemExit(f"New Mexico (state races): {what} ({url}) was refused three times ({last}); stopped. It would have to be "
                     "read in an ordinary browser; this loader does not work around a refusal.")


# ---------- which race a row belongs to ----------

def district_of(text_, what):
    m = re.fullmatch(r"DISTRICT 0*(\d+)", (text_ or "").strip().upper())
    if not m:
        raise SystemExit(f"New Mexico (state races): a {what} row names a district that is not read ({text_!r})")
    return m.group(1)


def race_of(office, contest="", district="", name=""):
    """(race_id, info) for a state race; None for an office this loader leaves to others; SystemExit for an office it
    does not know (so a new state office is never dropped silently)."""
    office, contest = (office or "").strip(), (contest or "").strip()
    base = {"level": "statewide", "jurisdiction": NAME, "jurisdiction_id": FIPS, "district": None, "seat": None, "special": 0,
            "partisan": 1, "chamber": None}
    if office in STATEWIDE:
        key, kind, shown_office = STATEWIDE[office]
        return f"2026-{STATE}-{key}", dict(base, office_kind=kind, office=shown_office, key=key)
    if office in LEGISLATURE:
        key, kind, shown_office, chamber, seats = LEGISLATURE[office]
        d = district_of(district, office)
        if not 1 <= int(d) <= seats:
            raise SystemExit(f"New Mexico (state races): {office} District {d} does not exist")
        words = "Senate" if chamber == "Senate" else "House"
        return f"2026-{STATE}-{key}{d}", dict(base, level="legislature", office_kind=kind, office=shown_office,
                                               jurisdiction=f"{words} District {d}", jurisdiction_id=d, district=d,
                                               special=int(chamber == "Senate"), chamber=chamber, key=key)
    if office == "Public Education Commissioner":
        d = district_of(district, office)
        return f"2026-{STATE}-PEC{d}", dict(base, office_kind="public_education_commission", office="Public Education Commissioner",
                                             jurisdiction=f"Public Education Commission District {d}", jurisdiction_id=f"{STATE}-PEC{d}",
                                             district=d, key="PEC")
    m = re.fullmatch(r"(Judge of the Court of Appeals|Justice of the Supreme Court) Position (\d+)", office)
    if m:
        coa = m.group(1).startswith("Judge")
        return (f"2026-{STATE}-{'COA' if coa else 'SC'}-P{m.group(2)}",
                dict(base, level="court", office_kind="court_of_appeals" if coa else "supreme_court", office=m.group(1),
                     seat=f"Position {m.group(2)}", key="COA" if coa else "SC"))
    if office == "Judicial Retention" and contest in RETENTION:
        key, kind, shown_office = RETENTION[contest]
        fam = re.sub(r"[^A-Z]", "", name_parts(WRITE_MARK.sub("", name))[1].upper())
        if not fam:
            raise SystemExit(f"New Mexico (state races): a retention row without a readable name ({contest})")
        return f"2026-{STATE}-{key}-{fam}", dict(base, level="court", office_kind=kind, office=shown_office, partisan=0, key=key)
    if OUT_OF_SCOPE.match(office) or (office == "Judicial Retention" and OUT_OF_SCOPE.match(contest)):
        return None
    raise SystemExit(f"New Mexico (state races): an office this loader does not know: {office!r} ({contest!r})")


def office_label(office):
    """For counting the rows left out: the office without its judicial district or division."""
    return re.sub(r"\s+(?:[A-Z0-9]+ JUDICIAL DISTRICT\b.*|DIVISION\b.*)$", "", office).strip()


# ---------- the candidate lists: the kept columns only ----------

def read_grid(kind):
    eid, title = LISTS[kind]
    url = PORTAL.format(eid=eid)
    page = ask(url, "text/html", title, expect=b'class="rgHeader').decode("utf-8", "replace")
    if not re.search(r"<title>\s*" + re.escape(title) + r"\s*</title>", page):
        raise SystemExit(f"New Mexico (state races): {url} is no longer the {title}")
    if re.search(r'class="rgPager|class="rgNumPart', page):
        raise SystemExit(f"New Mexico (state races): the {title} now runs over several pages; read them through its pager")
    menu = re.search(r'id="MainContent_ddlParty"[^>]*>(.*?)</select>', page, re.S)
    legend = {c: ordinary(H.unescape(t)) for c, t in re.findall(r'<option[^>]*value="([A-Z]+)"[^>]*>([^<]+)</option>',
                                                                menu.group(1) if menu else "")}
    if not legend:
        raise SystemExit(f"New Mexico (state races): the {title} no longer shows its party menu")
    heads = [text(h) for h in re.findall(r'<th scope="col" class="rgHeader[^"]*"[^>]*>(.*?)</th>', page, re.S)]
    if not all(k in heads for k in KEEP) or heads.count("Contest") != 2:
        raise SystemExit(f"New Mexico (state races): the candidate grid's columns changed ({[h for h in heads if h in KEEP]})")
    idx = {k: heads.index(k) for k in KEEP if k != "Contest"}
    first_contest, office_col = heads.index("Contest"), len(heads) - 1 - heads[::-1].index("Contest")
    rows, left_out, items = [], Counter(), 0
    for tr in re.findall(r'<tr class="(?:rgRow|rgAltRow)"[^>]*>(.*?)</tr>', page, re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        if len(cells) != len(heads):
            raise SystemExit(f"New Mexico (state races): a row of the {title} does not line up with the grid's headings")
        items += 1
        office, contest = text(cells[office_col]), text(cells[first_contest])
        if office.startswith("United States ") or (OUT_OF_SCOPE.match(office) and office != "Judicial Retention"):
            left_out[office_label(office)] += 1            # nothing else of this row is read
            continue
        if office == "Judicial Retention" and contest not in RETENTION:
            if not OUT_OF_SCOPE.match(contest):
                raise SystemExit(f"New Mexico (state races): a retention vote this loader does not know: {contest!r}")
            left_out[office_label(contest)] += 1
            continue
        r = {"Office": office, "Contest": contest}
        r.update({k: text(cells[i]) for k, i in idx.items()})
        race_of(r["Office"], r["Contest"], r["District"], r["Name"])      # stops on an office it does not know
        rows.append(r)
    if not rows:
        raise SystemExit(f"New Mexico (state races): no state rows read from the {title}")
    return {"title": title, "url": url, "items": items, "legend": legend, "columns": ["Office", "Contest"] + [k for k in KEEP if k != "Contest"],
            "rows": rows, "left_out": dict(sorted(left_out.items()))}


def cached_grid(kind, path, say):
    """The state rows of one list, read afresh when the kept copy is over two days old; the kept copy if the portal
    cannot be read. Returns (list, fetched, how)."""
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < 2 * 86400:
        got = json.load(open(path, encoding="utf-8"))
        return got, got["fetched"], "kept copy, under two days old"
    try:
        got = read_grid(kind)
    except SystemExit as e:
        if not os.path.exists(path):
            raise
        got = json.load(open(path, encoding="utf-8"))
        say(f"    New Mexico (state races): {e}; using the copy kept on {got['fetched']}")
        return got, got["fetched"], "kept copy"
    got["fetched"] = dt.date.today().isoformat()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(got, fh, ensure_ascii=False, indent=0)
    time.sleep(1.0)
    return got, got["fetched"], "read afresh"


# ---------- the certified primary results ----------

def read_results(cache, say):
    """{type: csv path}, the page facts (heading, updated, county-map numbers) and the recount list, fetched once a month."""
    jpath = os.path.join(cache, "nm_2026_primary_results_state_checks.json")
    paths = {t: os.path.join(cache, f"nm_2026_primary_results_state_{t.lower()}.csv") for t in RESULT_TYPES}
    fresh = all(os.path.exists(p) and time.time() - os.path.getmtime(p) < 30 * 86400 for p in list(paths.values()) + [jpath])
    if fresh:
        return paths, json.load(open(jpath, encoding="utf-8"))
    net.patient_lookups()
    checks = {"heading": HEADING, "updated": {}, "osn": {}, "recounts": [], "release_sha256": "", "counties": {}}
    if os.path.exists(jpath):                                   # county rows already fetched are kept
        checks["counties"] = json.load(open(jpath, encoding="utf-8")).get("counties", {})
    for t in RESULT_TYPES:
        page = ask(RESULTS_PAGE.format(t=t), "text/html", f"the results page for {RESULT_TYPES[t]}", expect=b"Results last updated").decode(
            "utf-8", "replace")
        plain = H.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", re.sub(r"(?s)<script.*?</script>|<style.*?</style>", "", page))))
        if HEADING not in plain or re.search(r"unofficial", plain, re.I):
            raise SystemExit(f"New Mexico (state races): the {RESULT_TYPES[t]} results page is no longer headed \"Official Results\"")
        updated = re.search(r"Results last updated: ([0-9/]+ [0-9:]+ [AP]M(?: MT)?)", plain)
        checks["updated"][t] = updated.group(1) if updated else ""
        for typ, race, osn, party in re.findall(r"BuildCounty\('(\w+)', '(\d+)', '(\d+)', '([A-Z]+)'\)", page):
            checks["osn"][f"{t}|{race}|{party}"] = osn
        time.sleep(1.0)
        raw = ask(RESULTS_CSV.format(t=t), "text/csv,*/*", f"the {RESULT_TYPES[t]} results export", expect=b"RaceID,RaceName,")
        head = raw.lstrip(b"\xef\xbb\xbf").split(b"\n", 1)[0].decode("utf-8", "replace").strip().split(",")
        if tuple(head[:len(RESULT_COLUMNS)]) != RESULT_COLUMNS or len(head) > len(RESULT_COLUMNS) + 1:
            raise SystemExit(f"New Mexico (state races): the {RESULT_TYPES[t]} results export's columns changed ({head})")
        with open(paths[t], "wb") as fh:                         # contest, party, district, candidate and votes only
            fh.write(raw)
        time.sleep(1.0)
    # the State Canvass Board's recounts: the list of contests only, from the Secretary's release
    page = ask(CERTIFIED_NEWS, "text/html", "the Secretary's release of June 23, 2026", expect=b"automatic recounts")
    checks["release_sha256"] = hashlib.sha256(page).hexdigest()
    body = H.unescape(re.sub(r"<[^>]+>", "\n", re.sub(r"(?s)<script.*?</script>|<style.*?</style>", "", page.decode("utf-8", "replace"))))
    part = re.search(r"(?s)ordered automatic recounts\s*in these contests:(.*?)The official, certified results", re.sub(r"[\xa0\s]+", " ", body))
    if not part:
        raise SystemExit("New Mexico (state races): the June 23 release no longer lists the recounted contests")
    checks["recounts"] = re.findall(r"((?:State Representative|State Senator|Public Education Commissioner), District \d+ \((?:Republican|Democrat)\))"
                                    r"|((?:Governor|Lieutenant Governor|Secretary of State|Attorney General|State Auditor|State Treasurer|"
                                    r"Commissioner of Public Lands) \((?:Republican|Democrat)\))", part.group(1))
    checks["recounts"] = [a or b for a, b in checks["recounts"]]
    os.makedirs(cache, exist_ok=True)
    json.dump(checks, open(jpath, "w", encoding="utf-8"), indent=1)
    say("      New Mexico (state races): the 2026 primary's official results read (statewide, legislative, Public Education Commission)")
    return paths, checks


def parse_results(paths, problems):
    """{(race, party code): contest} from the exports, with the export's own checks. A contest the export lists twice
    (the top two again, without the absentee, election day and early split: District 66's recounted primary) must
    carry the same figures both times; the full listing is kept."""
    grouped = defaultdict(list)
    for t, path in paths.items():
        for r in csv.DictReader(io.StringIO(open(path, encoding="utf-8-sig").read())):
            got = race_of(r["RaceName"], "", r["AreaNum"])
            if not got:
                raise SystemExit(f"New Mexico (state races): the {t} export names a contest outside the state races ({r['RaceName']})")
            grouped[(got[0], r["PartyCode"].strip(), r["RaceID"], t)].append(r)
    out = {}
    for (race, code, race_num, t), rows in grouped.items():
        split = lambda r: any((r[k] or "").strip() for k in ("CandidateAbsenteeVotes", "CandidateElectionDayVotes", "CandidateEarlyVotes"))
        full = [r for r in rows if split(r)]
        again = [r for r in rows if not split(r)]
        ids = Counter(r["CandidateID"] for r in rows)
        repeated = bool(again) and any(v > 1 for v in ids.values())
        if again and not repeated:
            full = rows                                        # a contest whose every figure is zero has no split at all
            again = []
        if repeated:
            byid = {r["CandidateID"]: int(r["CandidateVotes"]) for r in full}
            if len(byid) != len(full) or any(byid.get(r["CandidateID"]) != int(r["CandidateVotes"]) for r in again):
                raise SystemExit(f"New Mexico (state races): {race} {code} is listed twice in the export with different figures")
        if (race, code) in out:
            raise SystemExit(f"New Mexico (state races): {race} {code} is two contests in the export")
        cands = []
        for r in full:
            done, _, total = (r["PrecinctsReporting"] or "").partition("/")
            if not done or done != total:
                raise SystemExit(f"New Mexico (state races): the {race} {code} primary is not fully reported ({r['PrecinctsReporting']})")
            votes = int(r["CandidateVotes"])
            parts = [int(r[k] or 0) for k in ("CandidateAbsenteeVotes", "CandidateElectionDayVotes", "CandidateEarlyVotes")]
            if votes and sum(parts) != votes:
                raise SystemExit(f"New Mexico (state races): a candidate's absentee, election day and early votes in {race} {code} "
                                 f"do not add up to {votes}")
            cands.append({"name": WRITE_MARK.sub("", r["CandidateName"]).strip(), "write_in": bool(WRITE_MARK.search(r["CandidateName"])),
                          "votes": votes, "site_pct": float(r["CandidatePercentage"] or 0), "cid": r["CandidateID"]})
        total = sum(c["votes"] for c in cands)
        if any(abs(c["site_pct"] - (c["votes"] / total if total else 0)) > 1e-9 for c in cands):
            problems.append(f"{race} {code}: the site's percentages are not shares of the candidates' votes")
        out[(race, code)] = {"type": t, "race_num": race_num, "cands": cands, "repeated": repeated}
    return out


def county_rows(t, contest, race, code, checks, office_osn):
    """The county figures of one contest from the results page's own service (kept in the checks file)."""
    ck = f"{t}|{contest['race_num']}|{code}"
    if ck in checks["counties"]:
        return checks["counties"][ck]["rows"], False
    osn = checks["osn"].get(ck) or office_osn.get((t, race.rsplit("-", 1)[-1].rstrip("0123456789"))) or "0"
    data = json.loads(ask(COUNTY_SERVICE.format(t=t, race=contest["race_num"], osn=osn, party=code), "application/json",
                          f"the county figures of {race} {code}"))
    kept = []
    for row in data:
        if str(row.get("RaceID")) != contest["race_num"] or (row.get("PartyCode") or "").strip() != code:
            raise SystemExit(f"New Mexico (state races): the county service answered for another contest than {race} {code}")
        kept.append({"county": (row.get("CountyName") or "").strip(), "name": WRITE_MARK.sub("", row.get("calcCandidate") or "").strip(),
                     "votes": str(row.get("calcCandidateVotes") or "0").strip(), "share": row.get("calcCandidatePercentage"),
                     "osn": str(row.get("OfficeSeqNo") or "").strip()})
    checks["counties"][ck] = {"race": race, "party": code, "osn_asked": osn, "rows": kept}
    time.sleep(1.0)
    return kept, True


# ---------- places and the roster ----------

def county_names(path=COUNTY_ZIP):
    """{folded county name: (GEOID, 'Name County')} for New Mexico, from the Census file's attribute table only."""
    import shapefile                                   # pyshp
    z = zipfile.ZipFile(path)
    base = next(n[:-4] for n in z.namelist() if n.endswith(".dbf"))
    rdr = shapefile.Reader(dbf=io.BytesIO(z.read(base + ".dbf")))
    fields = [f[0] for f in rdr.fields[1:]]
    out = {}
    for rec in rdr.iterRecords():
        rec = dict(zip(fields, rec))
        if str(rec.get("STATEFP")) == FIPS:
            out[fold(str(rec["NAME"]))] = (str(rec["GEOID"]), str(rec.get("NAMELSAD") or f"{rec['NAME']} County"))
    return out


def roster():
    con = sqlite3.connect(f"file:{ROSTER_DB}?mode=ro", uri=True)
    seats = defaultdict(list)
    for bid, first, last, full, party, district, chamber, start in con.execute(
            "SELECT bioguide_id, first_name, last_name, official_full, party_name, district, chamber, term_start FROM legislators "
            "WHERE is_current = 1"):
        seats[(chamber, str(district))].append({"id": bid, "first": first or "", "last": last or "", "full": full or f"{first} {last}",
                                                "party": party, "chamber": chamber, "district": str(district), "start": start or ""})
    offices = {}
    for bid, first, last, full, office, label, party in con.execute(
            "SELECT bioguide_id, first_name, last_name, official_full, office, office_label, party_name FROM officials"):
        offices[office] = {"id": bid, "first": first or "", "last": last or "", "full": full or f"{first} {last}", "party": party,
                           "label": label, "chamber": None, "district": None}
    as_of = (con.execute("SELECT MAX(updated_at) FROM legislators").fetchone()[0] or "")[:10]
    con.close()
    return seats, offices, as_of


def person_fits(name, p):
    cand = name_parts(WRITE_MARK.sub("", name))
    return fits(cand, (fold(p["first"]).split(), fold(p["last"]))) or fits(cand, name_parts(p["full"]))


def shown(caps, member=None):
    """The filed name in ordinary capitals; a matched member as the roster spells the same letters."""
    caps = re.sub(r"\s+", " ", WRITE_MARK.sub("", caps)).strip()
    if member and fold(member["full"]).replace(" ", "") == fold(caps).replace(" ", ""):
        return member["full"]
    out = re.sub(r"(['\"(])([a-z])", lambda m: m.group(1) + m.group(2).upper(), proper(caps)).split(" ")
    # initials written together without vowels stay in capitals (JOSE JC LOPEZ -> Jose JC Lopez); Jr and Sr are words
    return " ".join(c if re.fullmatch(r"[B-DF-HJ-NP-TV-XZ]{2,3}", c) and c not in ("JR", "SR") else o
                    for c, o in zip(caps.split(" "), out))


def ticket(name):
    """'DEB HAALAND AND STEPHANIE GARCIA RICHARD' -> ('DEB HAALAND', 'STEPHANIE GARCIA RICHARD')."""
    parts = re.split(r"\s+AND\s+", name.strip(), maxsplit=1)
    if len(parts) != 2:
        raise SystemExit(f"New Mexico (state races): a Governor and Lieutenant Governor row without two names ({name!r})")
    return parts[0], parts[1]


# ---------- the load ----------

def load(db_path, say=print, cache=CACHE):
    if os.path.abspath(db_path) == os.path.abspath(os.path.join(HERE, "ballot_2026.sqlite")):
        raise SystemExit("New Mexico (state races): this loader never writes ballot_2026.sqlite")
    net.patient_lookups()
    seats, offices, as_of = roster()
    cmap = county_names()
    problems, notes_out = [], []
    gen, g_fetched, g_how = cached_grid("general", os.path.join(cache, "nm_2026_general_state.json"), say)
    pri, p_fetched, p_how = cached_grid("primary", os.path.join(cache, "nm_2026_primary_state.json"), say)
    paths, checks = read_results(cache, say)
    legend = {**pri["legend"], **gen["legend"]}

    def party_of(code):
        if not code:
            return None
        if code not in legend:
            raise SystemExit(f"New Mexico (state races): the party code {code!r} is not in the list's key ({legend})")
        return legend[code]

    # ---- races: every state contest on the November list, and the Lieutenant Governor's primary
    races, notes = {}, defaultdict(list)
    for r in gen["rows"]:
        rid, info = race_of(r["Office"], r["Contest"], r["District"], r["Name"])
        races.setdefault(rid, info)
    for r in pri["rows"]:
        rid, info = race_of(r["Office"], r["Contest"], r["District"], r["Name"])
        if rid == f"2026-{STATE}-LTG":
            races.setdefault(rid, info)
        elif rid not in races:
            problems.append(f"{rid}: on the primary list but not on the November list")
            races[rid] = info
    house = sorted(int(i["district"]) for i in races.values() if i["office_kind"] == "state_house")
    if house != list(range(1, 71)):
        problems.append(f"House districts on the November list are not 1 to 70 ({len(house)} read)")
    for key in ("GOV", "SOS", "AG", "AUD", "TREAS", "LAND"):
        if f"2026-{STATE}-{key}" not in races:
            problems.append(f"2026-{STATE}-{key}: not on the November list")

    def holders_of(rid):
        i = races[rid]
        if i["level"] == "legislature":
            return seats.get((i["chamber"], i["district"]), [])
        if i["level"] == "statewide" and i["key"] in ROSTER_OFFICE and ROSTER_OFFICE[i["key"]] in offices:
            return [offices[ROSTER_OFFICE[i["key"]]]]
        return []

    everyone = [p for ps in seats.values() for p in ps] + list(offices.values())

    def identify(rid, name, party, holders):
        """(incumbent, state_member_id, note, roster person) for one name."""
        fit = [h for h in holders if person_fits(name, h)]
        if len(fit) == 1 and sum(1 for h in holders if person_fits(name, h)) == 1:
            return 1, fit[0]["id"], None, fit[0]
        pool = [p for p in everyone if person_fits(name, p) and (p["party"] or "") == (party or "") and p not in holders]
        if len(pool) == 1:
            p = pool[0]
            where = f"in {CHAMBER_WORDS[p['chamber']]}, District {p['district']}" if p["chamber"] else f"as {p['label']}"
            return 0, p["id"], f"Serves today {where}.", p
        return 0, None, None, None

    # ---- the November ballot
    cands = []
    on_list, off_list = defaultdict(list), defaultdict(list)
    for r in gen["rows"]:
        rid, _ = race_of(r["Office"], r["Contest"], r["District"], r["Name"])
        if r["Status"] in OFF:
            off_list[rid].append(r)
        elif r["Status"] in ON:
            on_list[rid].append(r)
        else:
            raise SystemExit(f"New Mexico (state races): a status on the general list that is not read ({r['Status']!r}, {rid})")

    # ---- the primary ballots and their certified results
    ballots = defaultdict(list)                                   # (race, party code) -> Qualified rows on the primary list
    pri_off = []
    for r in pri["rows"]:
        rid, _ = race_of(r["Office"], r["Contest"], r["District"], r["Name"])
        if r["Status"] in OFF:
            pri_off.append(f"{shown(r['Name'])} ({party_of(r['Party'])}, {rid}, {r['Status'].lower()})")
        elif r["Status"] in ON:
            ballots[(rid, r["Party"])].append(r)
        else:
            raise SystemExit(f"New Mexico (state races): a status on the primary list that is not read ({r['Status']!r}, {rid})")
    results = parse_results(paths, problems)
    if set(results) != set(ballots):
        problems.append(f"the primary list's party contests and the results' differ: {sorted(set(results) ^ set(ballots))}")
    for key, contest in results.items():
        if key in ballots and sorted(nkey(c["name"]) for c in contest["cands"]) != sorted(nkey(r["Name"]) for r in ballots[key]):
            problems.append(f"{key[0]} {key[1]}: the results' candidates are not the primary list's Qualified rows")

    # county figures for every contest: they must add up, and they say which counties each district reaches
    office_osn = {}
    for k, v in checks["osn"].items():
        t, race_num, code = k.split("|")
        rid = next((r for (r, c), ct in results.items() if ct["race_num"] == race_num and c == code), None)
        if rid:
            office_osn.setdefault((t, rid.rsplit("-", 1)[-1].rstrip("0123456789")), set()).add(v)
    office_osn = {k: next(iter(v)) for k, v in office_osn.items() if len(v) == 1}
    race_counties, reconciled, fetched_any, protected = defaultdict(set), {}, False, []
    for (rid, code), contest in sorted(results.items()):
        rows, fetched = county_rows(contest["type"], contest, rid, code, checks, office_osn)
        fetched_any |= fetched
        if not rows:
            problems.append(f"{rid} {code}: the results service gives no county figures")
            reconciled[(rid, code)] = False
            continue
        spelled = {nkey(c["name"]): c["name"] for c in contest["cands"]}      # the service writes "DAY" where the export writes 'DAY'
        try:
            protected += [(contest["type"], rid) + tuple(x) for x in county_check(
                rid, code, contest["cands"], [dict(row, name=spelled.get(nkey(row["name"]), row["name"])) for row in rows])]
            reconciled[(rid, code)] = True
        except SystemExit as e:
            problems.append(str(e).replace("New Mexico: ", ""))
            reconciled[(rid, code)] = False
        for row in rows:
            c = cmap.get(fold(row["county"]))
            if not c:
                problems.append(f"{rid}: a county the Census file does not name ({row['county']!r})")
            else:
                race_counties[rid].add(c[0])
    if fetched_any:
        json.dump(checks, open(os.path.join(cache, "nm_2026_primary_results_state_checks.json"), "w", encoding="utf-8"), indent=1)

    recounted = set()
    for item in checks.get("recounts", []):
        m = re.fullmatch(r"(.+?), District (\d+) \((Republican|Democrat)\)", item) or re.fullmatch(r"(.+?)() \((Republican|Democrat)\)", item)
        got = race_of(m.group(1), "", f"DISTRICT {m.group(2)}" if m.group(2) else "")
        if got:
            recounted.add((got[0], "REP" if m.group(3) == "Republican" else "DEM"))

    # who won each party primary, from the certified votes
    winners, fields, write_in_noms = {}, [], {}
    for (rid, code), contest in results.items():
        cs = contest["cands"]
        if len(cs) == 1 and cs[0]["write_in"]:
            write_in_noms[(rid, code)] = cs[0]
        if sum(1 for c in cs if not c["write_in"]) < 2:
            if len(cs) == 1:
                winners[(rid, code)] = cs[0]
            continue
        top = sorted(cs, key=lambda c: -c["votes"])
        if top[0]["votes"] == top[1]["votes"]:
            problems.append(f"{rid} {code}: a tie at the top of the primary; outcome left open")
            continue
        winners[(rid, code)] = top[0]
        fields.append((rid, code))

    # November rows
    listed_names = defaultdict(list)                  # (race, party code) -> [(name as filed, status)] on the November list
    for rid in set(on_list) | set(off_list):
        for r in on_list[rid] + off_list[rid]:
            names = ticket(r["Name"]) if r["Office"] == "Governor and Lieutenant Governor" else (r["Name"],)
            listed_names[(rid, r["Party"])].append((names[0], r["Status"]))
            if len(names) == 2:
                listed_names[(f"2026-{STATE}-LTG", r["Party"])].append((names[1], r["Status"]))
    orders_none, write_ins = 0, []
    for rid in sorted(races):
        i = races[rid]
        holders = holders_of(rid)
        if i["level"] == "court" and i["partisan"] == 0:
            judge = [r for r in on_list[rid]]
            if len(judge) != 1:
                problems.append(f"{rid}: a retention vote with {len(judge)} names")
            for r in judge:
                cands.append((rid, "general", GENERAL, shown(r["Name"]), NONPARTISAN, "N", None, 1, 0, None, None, None, None, SRC_GENERAL,
                              f"Standing for retention as the sitting judge. {CAPS}"))
            continue
        for r in on_list[rid]:
            party = party_of(r["Party"]) or "No party"
            wi = bool(WRITE_MARK.search(r["Name"]))
            n = [WRITE_IN] if wi else []
            if r["Office"] == "Governor and Lieutenant Governor":
                head, mate = ticket(r["Name"])
                inc, mid, note, who = identify(rid, head, party, holders)
                m_inc, m_mid, m_note, m_who = identify(f"2026-{STATE}-LTG", mate, party, holders_of(f"2026-{STATE}-LTG"))
                name = f"{shown(head, who)} and {shown(mate, m_who)}"
                n.append("Governor and Lieutenant Governor on one ticket, the candidate for Governor named first.")
                if note:
                    n.append(f"{shown(head, who)}: {note}")
                if m_note or m_inc:
                    n.append(f"{shown(mate, m_who)}: " + (m_note or "Serves today as Lieutenant Governor."))
                for part, prace in ((head, rid), (mate, f"2026-{STATE}-LTG")):
                    b = ballots.get((prace, r["Party"]))
                    if r["Party"] in ("DEM", "REP") and not (b and any(nkey(x["Name"]) == nkey(part) for x in b)):
                        role = "Governor" if prace == rid else "Lieutenant Governor"
                        w = winners.get((prace, r["Party"]))
                        gone = w and any(nkey(nm) == nkey(w["name"]) and st in OFF for nm, st in listed_names[(prace, r["Party"])])
                        n.append(f"{shown(part)} was not on the June 2 {party} primary ballot for {role}; named afterwards"
                                 + (f", after {shown(w['name'])}, who won that primary, withdrew" if gone else "") + " (the list does not say how).")
            else:
                inc, mid, note, who = identify(rid, r["Name"], party, holders)
                name = shown(r["Name"], who)
                if note:
                    n.append(note)
                b = ballots.get((rid, r["Party"]))
                if r["Party"] in ("DEM", "REP") and not wi and not (b and any(nkey(x["Name"]) == nkey(r["Name"]) for x in b)):
                    w = winners.get((rid, r["Party"]))
                    gone = w and any(nkey(nm) == nkey(w["name"]) and st in OFF for nm, st in listed_names[(rid, r["Party"])])
                    n.append(f"Not on the June 2 {party} primary ballot for this seat; named afterwards"
                             + (f", after {shown(w['name'])}, who won that primary, withdrew" if gone else "") + " (the list does not say how).")
                wn = write_in_noms.get((rid, r["Party"]))
                if wn and nkey(wn["name"]) == nkey(r["Name"]):
                    n.append(f"Nominated in the June 2 {party} primary as a declared write-in candidate, the only candidate in that primary "
                             f"({wn['votes']:,} votes); no {party} name was printed on that ballot.")
            if inc and holders:
                h = next(h for h in holders if h["id"] == mid)
                if h["party"] and h["party"] != party:
                    problems.append(f"{rid}: sitting member listed as {h['party']}, on the ballot as {party}")
            n.append(CAPS)
            order = int(r["Ballot Order"]) if r["Ballot Order"].isdigit() and r["Ballot Order"] != NO_PLACE and not wi else None
            if order is None and not wi:
                orders_none += 1
            if wi:
                write_ins.append(f"{name} ({rid})")
            cands.append((rid, "general", GENERAL, name, party, party_code(party), order, inc, int(wi), None, None, None, mid,
                          SRC_GENERAL, " ".join(n)))

    # primary rows: the fields
    for rid, code in sorted(fields):
        contest, party = results[(rid, code)], party_of(code)
        holders = holders_of(rid)
        filed = {nkey(r["Name"]): r for r in ballots.get((rid, code), [])}
        total = sum(c["votes"] for c in contest["cands"])
        winner = winners[(rid, code)]
        nov = listed_names.get((rid, code), [])
        nov_qual = [nm for nm, st in nov if st in ON]
        won_gone = any(nkey(nm) == nkey(winner["name"]) and st in OFF for nm, st in nov)
        if nov and not any(nkey(nm) == nkey(winner["name"]) for nm, _ in nov):
            problems.append(f"{rid} {party}: the November list's {party} candidate is not the primary's top vote-getter")
        ok = reconciled.get((rid, code), False)
        if not ok:
            notes_out.append(f"{rid} {party}: county figures do not reconcile; votes left out")
        for c in sorted(contest["cands"], key=lambda c: -c["votes"]):
            row = filed.get(nkey(c["name"]))
            name_caps = row["Name"] if row else c["name"]
            inc, mid, note, who = identify(rid, name_caps, party, holders)
            n = [WRITE_IN] if c["write_in"] else []
            if note:
                n.append(note)
            if c is winner and won_gone:
                n.append("Won the primary; withdrew afterwards (the November list marks the name Withdrawn)"
                         + (f"; {', '.join(shown(x) for x in nov_qual)} stands for the party in November." if nov_qual
                            else f"; no {party} candidate is on the November ballot."))
            elif c is winner and not nov:
                n.append(f"Won the primary; the November list names no {party} candidate for this race.")
            if (rid, code) in recounted:
                n.append("The State Canvass Board ordered an automatic recount of this primary on June 23, 2026. The figures are the "
                         "certified canvass" + ("; the results export lists the top two a second time with the same figures, without "
                                                "the absentee, election day and early split" if contest["repeated"] else "") + ".")
            n.append(CAPS)
            order = int(row["Ballot Order"]) if row and row["Ballot Order"].isdigit() and row["Ballot Order"] != NO_PLACE and not c["write_in"] else None
            cands.append((rid, f"primary-{code}", PRIMARY, shown(name_caps, who), party, party_code(party), order, inc, int(c["write_in"]),
                          c["votes"] if ok else None, round(100 * c["votes"] / total, 1) if ok and total else None,
                          "advanced" if c is winner else "lost", mid, SRC_RESULTS[contest["type"]], " ".join(n)))

    # ---- race notes and holders
    for rid, i in races.items():
        hs = holders_of(rid)
        if i["level"] == "legislature" and not hs:
            notes[rid].append(f"The Open States roster ({as_of}) lists no sitting member for this seat.")
            problems.append(f"{rid}: no sitting member in the roster")
        elif i["level"] == "statewide" and not hs:
            notes[rid].append("The Open States roster this site uses does not carry this office, so today's holder is not shown.")
        elif i["level"] == "court" and i["partisan"]:
            notes[rid].append("The roster this site uses does not carry judges, so today's holder is not shown.")
        if i["office_kind"] == "state_senate":
            start = hs[0]["start"] if len(hs) == 1 else ""
            notes[rid].append("New Mexico elects its Senate for four years in presidential years (the last regular election was in 2024); "
                              "this is the only Senate seat on the Secretary's 2026 list"
                              + (f", and the roster shows its holder serving since {start}." if start else "."))
        if i["key"] == "GOV":
            notes[rid].append("New Mexico elects the Governor and Lieutenant Governor together in November, one vote for the pair; each "
                              f"party nominates them in separate primaries (the Lieutenant Governor's under 2026-{STATE}-LTG).")
        if i["key"] == "LTG":
            notes[rid].append("Nominated in each party's own primary on June 2; in November the Lieutenant Governor is elected jointly "
                              f"with the Governor, on the tickets listed under 2026-{STATE}-GOV.")
        if i["office_kind"] == "public_education_commission":
            notes[rid].append(f"Only the voters of Public Education Commission District {i['district']} elect this seat.")
        if i["level"] == "court" and not i["partisan"]:
            notes[rid].append("A retention vote: voters answer Yes or No on keeping this judge in office.")
        gone = off_list.get(rid, [])
        if gone:
            notes[rid].append("Withdrawn or disqualified, not on the November ballot: " + "; ".join(
                f"{shown(r['Name'])} ({party_of(r['Party']) or 'no party'}, {r['Status'].lower()})" for r in gone) + ".")
        if i["level"] != "court" and rid != f"2026-{STATE}-LTG" and not any(k[0] == rid for k in ballots):
            notes[rid].append("No party held a primary for this seat on June 2.")

    race_rows = []
    for rid, i in sorted(races.items()):
        hs = holders_of(rid)
        if i["level"] == "court" and not i["partisan"]:
            judge = next((c[3] for c in cands if c[0] == rid and c[1] == "general"), None)
            hid, hname, hparty = None, judge, None
        else:
            hid = ",".join(h["id"] for h in hs) or None
            hname = " and ".join(h["full"] for h in hs) or None
            hparty = ", ".join(dict.fromkeys(h["party"] for h in hs if h["party"])) or None
        cids = sorted(race_counties.get(rid, set())) if i["district"] else []      # statewide offices and courts: none
        race_rows.append((rid, STATE, i["level"], i["office_kind"], i["office"], i["jurisdiction"], i["jurisdiction_id"],
                          json.dumps(cids) if cids else None, i["district"], i["seat"], i["special"], i["partisan"],
                          hid, hname, hparty, GENERAL, " ".join(notes[rid]) or None))

    place_rows = [("county", geoid, full, json.dumps([geoid]), SRC_COUNTY) for geoid, full in sorted(cmap.values())]
    for rid, i in sorted(races.items()):
        kind = {"state_senate": "senate", "state_house": "house", "public_education_commission": "pec"}.get(i["office_kind"])
        if kind:
            pid = f"{STATE}-PEC{i['district']}" if kind == "pec" else f"{STATE}-{i['district']}"
            cids = sorted(race_counties.get(rid, set()))
            place_rows.append((kind, pid, i["jurisdiction"], json.dumps(cids) if cids else None, SRC_RESULTS["ECX" if kind == "pec" else "LGX"]))

    # ---- checks on the whole
    keys = Counter((c[0], c[1], c[3]) for c in cands)
    dup = [k for k, v in keys.items() if v > 1]
    if dup:
        raise SystemExit(f"New Mexico (state races): the same name twice in one election: {dup}")
    gen_by_race = Counter(c[0] for c in cands if c[1] == "general")
    empty = sorted(rid for rid in races if gen_by_race[rid] == 0 and rid != f"2026-{STATE}-LTG")
    n_off = sum(len(v) for v in off_list.values())
    if gen_by_race.total() + n_off != len(gen["rows"]):
        raise SystemExit("New Mexico (state races): November rows written plus those left off do not equal the list's state rows")
    for rid in races:
        if races[rid]["level"] != "statewide" and not race_counties.get(rid) and races[rid]["level"] != "court":
            problems.append(f"{rid}: no county figures, so no county_ids")

    counted = {t: sum(len(results[k]["cands"]) for k in fields if results[k]["type"] == t) for t in RESULT_TYPES}
    rows_in = {t: sum(len(ct["cands"]) for ct in results.values() if ct["type"] == t) for t in RESULT_TYPES}
    reconciled_n = sum(1 for v in reconciled.values() if v)
    left_gen = "; ".join(f"{k} {v}" for k, v in gen["left_out"].items())
    src = [
        (SRC_GENERAL, STATE, "official candidate list", "New Mexico Secretary of State",
         "2026 General Election Contest/Candidate List (November 3, 2026): state offices, the Legislature and the statewide courts",
         gen["url"], "", g_fetched, sha_of(os.path.join(cache, "nm_2026_general_state.json")), len(gen["rows"]),
         f"The candidate portal's grid of every office ({gen['items']} rows, one page, {g_how}); the {len(gen['rows'])} rows for state "
         "races kept, and only the office, contest, district, name, party, ballot order and status; the grid's addresses, city, ZIP, "
         "phones, e-mail, websites and filing county are never read. Withdrawn or disqualified, left off: "
         f"{n_off}. Declared write-ins: {len(write_ins)}. Parties written out from the list's own key. Not loaded here, counted by "
         f"office: {left_gen}. The fingerprint is of the kept columns (nm_2026_general_state.json)."),
        (SRC_PRIMARY, STATE, "official candidate list", "New Mexico Secretary of State",
         "2026 Primary Election Contest/Candidate List (June 2, 2026): state offices, the Legislature and the statewide courts",
         pri["url"], "", p_fetched, sha_of(os.path.join(cache, "nm_2026_primary_state.json")), len(pri["rows"]),
         f"Read the same way ({pri['items']} rows, {p_how}); the {len(pri['rows'])} state rows kept, allowed columns only. Who was on "
         "each party's June 2 ballot and in what order; every party contest in the results names exactly its Qualified rows. "
         f"Withdrawn or disqualified before the primary, not on its ballot: {'; '.join(pri_off) or 'none'}."),
    ]
    for t, label in RESULT_TYPES.items():
        src.append((SRC_RESULTS[t], STATE, "official results", "New Mexico Secretary of State",
                    f"2026 Primary Election Official Results (June 2, 2026), certified by the State Canvass Board on June 23, 2026: "
                    f"{label}, the results site's CSV export", RESULTS_CSV.format(t=t), "2026-06-23", day_of(paths[t]), sha_of(paths[t]),
                    counted[t],
                    f"{rows_in[t]} candidate lines in {sum(1 for ct in results.values() if ct['type'] == t)} party contests; "
                    f"{sum(1 for k in fields if results[k]['type'] == t)} of them fields (two or more printed names), {counted[t]} lines "
                    f"loaded. The results page ({RESULTS_PAGE.format(t=t)}) is headed \"Official Results\", last updated "
                    f"{checks['updated'].get(t, '')}. Every precinct reported; absentee, election day and early votes add up; each "
                    "contest's county figures (the page's own service) add up to its statewide totals"
                    + (" (protected, printed \"*\": " + "; ".join(f"{shown(n)} in {w} ({r}), {v:,} by the remainder"
                                                                  + (", which gives the share the service prints" if ok else "")
                                                                  for tt, r, w, n, v, ok in protected if tt == t) + ")"
                       if any(x[0] == t for x in protected) else "") + ". Write-in votes are counted only for declared write-in candidates, listed among the "
                    "candidates, so a field's total is its candidates' votes."))
    src += [
        (SRC_RELEASE, STATE, "official release", "New Mexico Secretary of State",
         "State Canvass Board Certifies 2026 Primary Election Results, Orders Automatic Recounts (June 23, 2026)", CERTIFIED_NEWS,
         "2026-06-23", day_of(os.path.join(cache, "nm_2026_primary_results_state_checks.json")), checks.get("release_sha256", ""),
         len(checks.get("recounts", [])),
         "Only the list of recounted contests is read: " + "; ".join(checks.get("recounts", [])) + ". State races among them: "
         + (", ".join(f"{r} {c}" for r, c in sorted(recounted)) or "none") + "; their figures are the certified canvass."),
        (SRC_ROSTER, STATE, "roster", "Open States people project (CC0)",
         "New Mexico legislators and statewide officials, as loaded into state_nm.sqlite", "https://github.com/openstates/people",
         as_of, as_of, "", sum(len(v) for v in seats.values()) + len(offices),
         "Today's holder of each seat and office (ids, names, parties, districts and start dates only). The roster does not carry "
         "the Secretary of State, the Auditor, the Treasurer, the Commissioner of Public Lands, the Public Education Commission or judges."),
        (SRC_COUNTY, STATE, "official place names", "U.S. Census Bureau", "Cartographic boundary file, counties, 1:500,000 (2024)",
         COUNTY_URL, "", day_of(COUNTY_ZIP), sha_of(COUNTY_ZIP), len(cmap),
         "New Mexico's 33 counties: names and GEOIDs only. A district's county_ids are the counties the results service reports "
         "votes from in that district's June 2 primary contests."),
    ]

    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA)
    with con:
        con.execute("DELETE FROM sl_candidates WHERE race_id IN (SELECT race_id FROM sl_races WHERE state = ?) OR race_id LIKE ?",
                    (STATE, f"2026-{STATE}-%"))
        con.execute("DELETE FROM sl_races WHERE state = ?", (STATE,))
        con.execute("DELETE FROM sl_places WHERE source_id IN (SELECT source_id FROM sl_sources WHERE state = ?) OR source_id LIKE ?",
                    (STATE, "nm-%"))
        con.execute("DELETE FROM sl_sources WHERE state = ?", (STATE,))
        con.executemany("INSERT INTO sl_races VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", race_rows)
        con.executemany("INSERT INTO sl_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", cands)
        con.executemany("INSERT INTO sl_places VALUES (?,?,?,?,?)", place_rows)
        con.executemany("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", src)
    con.close()

    # ---- the report: counts only
    kind_of = lambda rid: {"state_senate": "Senate", "state_house": "House", "public_education_commission": "PEC"}.get(
        races[rid]["office_kind"], races[rid]["level"])
    by = Counter(kind_of(rid) for rid in races if rid != f"2026-{STATE}-LTG")
    gen_n = Counter(kind_of(c[0]) for c in cands if c[1] == "general")
    alone = Counter(kind_of(rid) for rid, v in gen_by_race.items() if v == 1)
    inc = Counter(kind_of(c[0]) for c in cands if c[1] == "general" and c[7])
    fld = Counter(kind_of(r) for r, _ in fields)
    say(f"    New Mexico (state races): House {by['House']} seats, Senate {by['Senate']} (special), statewide {by['statewide']} offices, "
        f"Public Education Commission {by['PEC']}, court {by['court']}; {gen_n.total()} candidates on the November ballot (House "
        f"{gen_n['House']}, Senate {gen_n['Senate']}, statewide {gen_n['statewide']}, PEC {gen_n['PEC']}, court {gen_n['court']}; "
        f"{n_off} withdrawn or disqualified left off; {len(write_ins)} declared write-ins); one name only: House {alone['House']}, "
        f"Senate {alone['Senate']}, statewide {alone['statewide']}, PEC {alone['PEC']}, court {alone['court']}; sitting member on "
        f"the ballot: House {inc['House']}, Senate {inc['Senate']}, statewide {inc['statewide']}; primary fields: House "
        f"{fld['House']}, Senate {fld['Senate']}, statewide {fld['statewide']}, PEC {fld['PEC']} (official certified votes; "
        f"{reconciled_n} of {len(results)} party contests reconciled county by county)")
    for label, items in (("no candidate on the November list", empty),):
        if items:
            say(f"    CHECK New Mexico (state races): {label}: {', '.join(items)}")
    for p in problems + notes_out:
        say(f"    CHECK New Mexico (state races): {p}")
    for rid, code in sorted(recounted):
        say(f"    New Mexico (state races): {rid} {party_of(code)} primary was recounted (ordered June 23); the certified canvass figures are loaded")
    return len(cands)


if __name__ == "__main__":
    args = sys.argv[1:]
    cache = CACHE
    if "--cache" in args:
        i = args.index("--cache")
        cache = args[i + 1]
        del args[i:i + 2]
    if len(args) != 1:
        raise SystemExit("usage: python ballot/state_local_nm.py <database file> [--cache <folder>]")
    load(args[0], cache=cache)
