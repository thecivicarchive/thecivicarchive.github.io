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

The county offices and the local judges (John, 2026-09-30)
----------------------------------------------------------
The same November list carries every county office on this ballot and the judges elected by county or judicial
district, and from it the loader also writes: county commissioners (Los Alamos County's councilors), sheriffs,
assessors, the county clerks and the treasurer up this year and probate judges (level county, as the list's own
DistrictType files them), and, under level court with their counties, magistrate judges, Los Alamos County's
municipal judge, district court judges, judges of the Bernalillo County Metropolitan Court and the yes-or-no retention
votes for sitting district and metropolitan court judges. Every one of these offices but the retention votes is on the
partisan ballot. New Mexico's cities, school boards and other districts elect at the Regular Local Election in
November of odd-numbered years (or, a municipality that kept it, at the Municipal Officer Election in March of
even-numbered years), so the November 2026 list has no contest of theirs; sl_notes says so.

  - The whole list (the same page the state rows come from, asked once a run), cut down in memory to the county and
    judge rows and to these cells, by their headings: Contest (both), District, DistrictType, Name, Party, Ballot
    Order, Status, and Filing County only on a row for an office filed in its own county (a county office, a probate
    judge, a magistrate, the municipal judge). On a district or metropolitan court row that cell is the county where
    the candidate lives, so it is never turned into text; those courts' counties come from the courts' own page and
    the proclamation. The addresses, city, ZIP, phones, e-mail, website, filing time and "Confidential Public
    Official" cells are never read. A kept cell that reads like contact details is blanked and counted, never printed.
    Only the cut-down rows are kept (ballot_cache/nm/local/nm_2026_general_local.json).
  - The same list county by county (CandidateList.aspx?...&cty=<code>, the 33 codes of the page's own county menu), the
    second route the first is checked against, because the list prints no totals: every row for an office filed in its
    own county must be on exactly the view of the county the whole list names, with the same cells, and every other
    office must be either wholly on the county views or wholly off them (filed with the Secretary of State). The other
    rows of a view are only counted, all views together, by office; their cells are never read.
  - The Secretary's General Election Proclamation (January 26, 2026), the checklist of offices. It is a scan, so its
    list of county offices and of the district and metropolitan court seats "to fill unexpired term" was typed from it
    once (PROCLAIMED and the two SEATS tables below) and the loader checks, by SHA-256, that the file on the
    Secretary's site is still the one it was typed from. It tells what the candidate list cannot: a contest nobody is
    listed for (kept, with a note), how many councilors Los Alamos County elects, and which judgeships are for an
    unexpired term (special 1).
  - The New Mexico Courts' own page "Courts by District": which counties each of the thirteen judicial districts
    covers. It must name every county exactly once.
  - The results site's export of county contests in the June 2 primary, read only for each contest's vote-for number
    (the number each party nominates is the number elected in November). No name and no vote is kept from it.

Withdrawn and disqualified names are left off and counted in the contest's note, without the name. Local primaries are
not loaded. Ballot questions are not on a candidate list and are not loaded. If the two readings of the list cannot be
made to agree the loader stops before writing anything, naming the counties and the counts, never a row.

What is kept on disk for this part, all of it in <cache>/local/ (ballot_cache/nm/local/) and none of it a page as it
came: nm_2026_general_local.json (the county and judge rows, allowed cells), nm_2026_general_local_views.json (the same
rows as each county's view gives them, and one count by office of the other rows on all views together),
nm_judicial_districts.json (each judicial district's counties), nm_2026_general_proclamation.json (the proclamation's
fingerprint) and nm_2026_primary_county_contests.json (each county contest's vote-for number). The list is asked again
after two days; the county views only when the list's county and judge rows have changed; the courts' page and the
proclamation after a month; the June primary's export once.

Race ids for these rows: 2026-NM-<county code>-<office>[-<district or division>] for an office of one county (so
2026-NM-35001-county-commissioner-5, 2026-NM-35045-magistrate-division-2), 2026-NM-JD<n>-district-court... for a
judicial district, and -S at the end for a seat filled for an unexpired term.
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

from ballot.check_local import EXTRA_SCHEMA, contact_like        # noqa: E402
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

_PAGES = {}


def list_page(kind):
    """One list as the portal serves it, asked once a run: the state rows and the county rows are cut from the same
    answer, and a refusal is remembered too, so the portal is not asked for the same page again. Held in memory only,
    and let go when the load ends."""
    if kind not in _PAGES:
        eid, title = LISTS[kind]
        try:
            _PAGES[kind] = ask(PORTAL.format(eid=eid), "text/html", title, expect=b'class="rgHeader')
        except SystemExit as e:
            _PAGES[kind] = e
    if isinstance(_PAGES[kind], SystemExit):
        raise _PAGES[kind]
    return _PAGES[kind]


def read_grid(kind):
    eid, title = LISTS[kind]
    url = PORTAL.format(eid=eid)
    page = list_page(kind).decode("utf-8", "replace")
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


# ======================================================================================================================
# The county offices and the local judges: the rows of the November list the state part above only counts
# ======================================================================================================================

LOCAL = "New Mexico (county offices and local judges)"
GEN_EID = LISTS["general"][0]
VIEW = "https://candidateportal.servis.sos.state.nm.us/CandidateList.aspx?eid={eid}&cty={cty}"
PROCLAMATION_URL = "https://www.sos.nm.gov/wp-content/uploads/2026/04/2026-General-Election-Proclamation-English.pdf"
PROCLAMATION_SHA = "a0efc2d279ebb3414ab92afee77e8e583c2cc3302026fbfc8ed5ea65ae492cc4"      # the scan the tables below were typed from
PROCLAMATION_DAY = "2026-01-26"
COURTS_URL = "https://nmcourts.gov/courts-by-district/"
LOCAL_ELECTIONS_URL = "https://www.sos.nm.gov/voting-and-elections/local-election-act-information/"
VOTE_FOR_CSV = RESULTS + "resultsCSV.aspx?text=All&type=CTY&map=CTY&eid=" + EID

LOCAL_SRC = "nm-sos-2026-local-general-list"
VIEW_SRC = "nm-sos-2026-local-general-list-c{code}"
PROC_SRC = "nm-sos-2026-general-proclamation"
COURTS_SRC = "nm-courts-judicial-districts"
VOTE_FOR_SRC = "nm-sos-2026-primary-county-contests"

# The proclamation's county offices, typed from the scan (its text layer is the scanner's own reading: "PRO BA TE",
# "SHERJFF", "District I"), one county a line as the proclamation lists them:
#   magistrate judges: () none, (0,) one judge with no division named, else the divisions (for Sandoval and Santa Fe
#   counties the proclamation writes "District 1" and so on where the candidate list writes "Division");
#   the countywide offices; and the commissioners: by District or Position, or the number of councilors.
PROCLAIMED = {
    "Bernalillo": ((), "sheriff assessor probate", ("District", (1, 5))),
    "Catron": ((0,), "sheriff assessor probate", ("District", (1, 2))),
    "Chaves": ((1, 2), "sheriff assessor probate", ("District", (1, 5))),
    "Cibola": ((1, 2), "sheriff assessor probate", ("District", (1, 3))),
    "Colfax": ((1, 2), "sheriff assessor probate", ("District", (1, 2))),
    "Curry": ((1, 2), "sheriff assessor probate", ("District", (1, 2, 3))),
    "De Baca": ((0,), "sheriff assessor probate", ("District", (1, 2))),
    "Dona Ana": ((1, 2, 3, 4, 5, 6, 7), "sheriff assessor probate", ("District", (1, 3))),
    "Eddy": ((1, 2, 3), "assessor clerk probate", ("District", (1, 4))),
    "Grant": ((2,), "sheriff assessor probate", ("District", (1, 2))),
    "Guadalupe": ((0,), "sheriff assessor probate", ("District", (1, 2))),
    "Harding": ((0,), "sheriff assessor probate", ("District", (1, 2))),
    "Hidalgo": ((0,), "sheriff assessor probate", ("District", (1, 2))),
    "Lea": ((1, 2, 3, 4), "sheriff assessor probate", ("District", (2, 3))),
    "Lincoln": ((1, 2), "clerk treasurer probate", ("District", (2, 4, 5))),
    "Los Alamos": ((0,), "municipal sheriff assessor probate", ("Councilors", (4,))),
    "Luna": ((0,), "sheriff assessor probate", ("District", (1, 2))),
    "McKinley": ((1, 2, 3), "sheriff assessor probate", ("District", (1, 2))),
    "Mora": ((0,), "sheriff assessor probate", ("District", (1, 2))),
    "Otero": ((1, 2), "sheriff assessor probate", ("District", (1, 2))),
    "Quay": ((0,), "sheriff assessor probate", ("District", (3,))),
    "Rio Arriba": ((1, 2), "sheriff assessor probate", ("District", (1, 2))),
    "Roosevelt": ((0,), "sheriff assessor probate", ("District", (3, 4, 5))),
    "San Juan": ((1, 2, 3, 4, 5, 6), "sheriff assessor probate", ("District", (1, 2))),
    "San Miguel": ((1, 2), "sheriff assessor probate", ("District", (1, 3))),
    "Sandoval": ((1, 2, 3), "sheriff assessor probate", ("District", (1, 3))),
    "Santa Fe": ((1, 2, 3, 4), "sheriff assessor probate", ("District", (1, 3))),
    "Sierra": ((0,), "sheriff assessor probate", ("District", (1, 2))),
    "Socorro": ((0,), "sheriff assessor probate", ("District", (1, 3))),
    "Taos": ((1, 2), "sheriff assessor probate", ("District", (1, 2, 5))),
    "Torrance": ((0,), "sheriff assessor probate", ("District", (1, 2))),
    "Union": ((0,), "sheriff assessor probate", ("Position", (1, 2))),
    "Valencia": ((1, 2, 3), "sheriff assessor probate", ("District", (1, 3))),
}
# "Judicial District Judges ... to fill unexpired term" and "Two judges of the Bernalillo County Metropolitan Court ...
# to fill unexpired term", as the proclamation lists them: judicial district -> divisions, and the court's divisions
PROCLAIMED_DISTRICT_SEATS = {1: (4, 8), 2: (2, 11, 19, 24), 3: (4,), 5: (5,), 10: (1,), 11: (2, 6, 8), 12: (2,)}
PROCLAIMED_METRO_SEATS = (5, 19)
METRO_COUNTY = "Bernalillo"                                 # the proclamation's own words: "the Bernalillo County Metropolitan Court"
PROCLAIMED_WORD = {"sheriff": "County Sheriff", "assessor": "County Assessor", "clerk": "County Clerk", "treasurer": "County Treasurer",
                   "probate": "Probate Judge"}

COUNTYWIDE = {"County Assessor": ("county_assessor", "County Assessor"), "County Clerk": ("county_clerk", "County Clerk"),
              "County Sheriff": ("sheriff", "County Sheriff"), "County Treasurer": ("county_treasurer", "County Treasurer"),
              "Probate Judge": ("probate_judge", "Probate Judge")}
COUNTY_FILED = ("countywide", "commissioner", "at_large", "magistrate", "municipal")      # offices filed in the office's own county
DISTRICT_TYPE = {"countywide": "CTY", "commissioner": "CCX", "at_large": "CTY", "magistrate": "MGX", "municipal": "MUX", "district": "JDX",
                 "metro": "JMC"}
LOCAL_HEADS = ("District", "Filing County", "Name", "Party", "Ballot Order", "Status", "DistrictType")
KEY = ("Office", "Contest", "District", "DistrictType", "Name", "Party", "Ballot Order", "Status")
ORD_WORDS = ("First", "Second", "Third", "Fourth", "Fifth", "Sixth", "Seventh", "Eighth", "Ninth", "Tenth", "Eleventh", "Twelfth", "Thirteenth")
NUMBER = ("no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve", "thirteen", "fourteen",
          "fifteen", "sixteen", "seventeen", "eighteen", "nineteen", "twenty")
UNEXPIRED = "An election to fill an unexpired term, as the Secretary of State's proclamation of January 26, 2026 words it."
RETENTION_VOTE = "A retention vote: voters answer Yes or No on keeping this judge in office."
NO_ONE = "The Secretary of State's proclamation of January 26, 2026 lists this office for election; the candidate list names no candidate for it."
# the page builder's own test for a number followed soon after by a street word (it knows more such words than the trial
# check does: Court, Place); every text written here is tried against both before it is stored
BUILDER_STREET = re.compile(r"\b\d{1,6}\s+(?:[NSEW]\.?\s+)?[A-Za-z0-9.' -]{1,40}?\s(?:St|Street|Ave|Avenue|Rd|Road|Blvd|Boulevard|Dr|Drive|Ln|Lane|Way|Ct|Court|"
                            r"Cir|Circle|Pkwy|Parkway|Hwy|Highway|Trl|Trail|Pl|Place|Ter|Terrace)\b\.?", re.I)


class LocalStop(SystemExit):
    """The county and judge rows cannot be loaded as they should be; the loader stops before it writes anything."""


def stop(what):
    raise LocalStop(f"{LOCAL}: {what}; stopped (no row is printed)")


def number(n):
    return NUMBER[n] if 0 <= n < len(NUMBER) else f"{n:,}"


def and_names(items):
    items = list(items)
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1] if items else ""


def reads_like_contact(value):
    return bool(value) and (contact_like(value, True) or bool(BUILDER_STREET.search(str(value))))


def fetch(url, accept, what, expect=None):
    """One address, asked at most three times and then left alone (a refusal, or an answer without what it should
    hold, is never worked around). Returns the bytes as they came, after a pause."""
    last = None
    for attempt in range(3):
        try:
            body = net.get(url, accept=accept)
            if expect is not None and expect not in body:
                last = "the answer came back without its expected content (a bot check or a changed page)"
            else:
                time.sleep(1.2)
                return body
        except (HTTPError, URLError, OSError) as e:
            last = e
        if attempt < 2:
            time.sleep(5 * (attempt + 1))
    raise LocalStop(f"{LOCAL}: {what} ({url}) could not be read in three tries ({last}); stopped. This loader does not work around a refusal.")


def keep_json(path, kept):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".part", "w", encoding="utf-8") as fh:
        json.dump(kept, fh, ensure_ascii=False, indent=0)
    os.replace(path + ".part", path)


def fresh(path, days):
    return os.path.exists(path) and time.time() - os.path.getmtime(path) < days * 86400


def local_kind(office):
    """Which kind of county or judge row an office of the list is; None for the state and federal rows."""
    if office in COUNTYWIDE:
        return "countywide"
    if office == "County Commissioner by Commissioner District":
        return "commissioner"
    if office == "County Commissioner At Large":
        return "at_large"
    if office == "Magistrate Judge":
        return "magistrate"
    if office == "Municipal Judge":
        return "municipal"
    if office == "District Court Judge":
        return "district"
    if office == "Judge of the Metropolitan Court":
        return "metro"
    if office.startswith("Judicial Retention District Court Judge "):
        return "district_retention"
    if office.startswith("Judicial Retention Judge of the Metropolitan Court "):
        return "metro_retention"
    if office.startswith("County "):
        return "unknown"                                    # a county office this loader has not met: it stops, naming the office
    return None


def judicial(words):
    """'FIRST JUDICIAL DISTRICT, DIVISION 04' or '10TH JUDICIAL DISTRICT' -> (1, 4) or (10, None); None when not read."""
    m = re.fullmatch(r"([A-Z]+|\d+(?:ST|ND|RD|TH)) JUDICIAL DISTRICT(?:\s*,\s*DIVISION 0*(\d+))?", (words or "").strip().upper())
    if not m:
        return None
    w = m.group(1)
    n = int(re.match(r"\d+", w).group(0)) if w[0].isdigit() else ORD_WORDS.index(w.title()) + 1 if w.title() in ORD_WORDS else 0
    return (n, int(m.group(2)) if m.group(2) else None) if 1 <= n <= len(ORD_WORDS) else None


# ---------- reading the list: the whole of it, and county by county ----------

def open_grid(raw, title, what):
    """The grid of one answer: (page, where each needed column is, rows as lists of raw cells). Only the headings are
    turned into text here; a caller reads the cells it is allowed to and no others."""
    page = raw.decode("utf-8", "replace")
    if not re.search(r"<title>\s*" + re.escape(title) + r"\s*</title>", page):
        stop(f"{what} is no longer the {title}")
    if re.search(r'class="rgPager|class="rgNumPart', page):
        stop(f"{what} now runs over several pages; read them through its pager")
    heads = [text(h) for h in re.findall(r'<th scope="col" class="rgHeader[^"]*"[^>]*>(.*?)</th>', page, re.S)]
    if heads.count("Contest") != 2 or any(heads.count(k) != 1 for k in LOCAL_HEADS):
        stop(f"{what}: the grid's columns changed")
    rows = []
    for n, tr in enumerate(re.findall(r'<tr class="(?:rgRow|rgAltRow)"[^>]*>(.*?)</tr>', page, re.S), 1):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        if len(cells) != len(heads):
            stop(f"row {n} of {what} does not line up with the grid's headings")
        rows.append(cells)
    col = {k: heads.index(k) for k in LOCAL_HEADS}
    col["first"], col["office"] = heads.index("Contest"), len(heads) - 1 - heads[::-1].index("Contest")
    return page, col, rows


def kept_row(cells, col, office, with_county, blanked):
    """The allowed cells of one county or judge row. A kept cell that reads like contact details (typed into the
    wrong column) is blanked and counted; it is never printed."""
    r = {"Office": office, "Contest": text(cells[col["first"]])}
    r.update({k: text(cells[col[k]]) for k in ("District", "DistrictType", "Name", "Party", "Ballot Order", "Status")})
    if with_county:
        r["County"] = text(cells[col["Filing County"]])
    for k in ("Contest", "District", "Name"):
        if reads_like_contact(r[k]):
            r[k] = ""
            blanked[0] += 1
    return r


def county_menu(page):
    menu = re.search(r'id="MainContent_ddlCounty"[^>]*>(.*?)</select>', page, re.S)
    return menu.group(1) if menu else ""


def read_whole(folder, say, force=False):
    """The county and judge rows of the whole November list (the allowed cells only), kept two days. When the state
    part has just asked for the page, the rows are cut from that same answer, so the two parts never drift apart."""
    path = os.path.join(folder, "nm_2026_general_local.json")
    if not force and fresh(path, 2) and "general" not in _PAGES:
        return json.load(open(path, encoding="utf-8"))
    eid, title = LISTS["general"]
    try:
        if force:
            _PAGES.pop("general", None)
        raw = list_page("general")
    except SystemExit as e:
        if not os.path.exists(path):
            raise LocalStop(str(e))
        kept = json.load(open(path, encoding="utf-8"))
        say(f"    {LOCAL}: the candidate list could not be read; using the copy kept on {kept['fetched']}")
        return kept
    page, col, grid = open_grid(raw, title, "the candidate list")
    counties = {c: H.unescape(t).strip() for c, t in re.findall(r'<option[^>]*value="(\d+)"[^>]*>([^<]+)</option>', county_menu(page))
                if c not in ("0", "99")}
    menu = re.search(r'id="MainContent_ddlParty"[^>]*>(.*?)</select>', page, re.S)
    legend = {c: ordinary(H.unescape(t)) for c, t in re.findall(r'<option[^>]*value="([A-Z]+)"[^>]*>([^<]+)</option>', menu.group(1) if menu else "")}
    if len(counties) != 33 or not legend:
        stop("the candidate list no longer shows its menus of 33 counties and of parties")
    rows, by_office, blanked = [], Counter(), [0]
    for n, cells in enumerate(grid, 1):
        office = text(cells[col["office"]])
        by_office[office_label(office)] += 1
        kind = local_kind(office)
        if kind is None:
            continue                                        # a state or federal row: nothing else of it is read here
        if kind == "unknown":
            stop(f"row {n} of the candidate list names a county office this loader does not know ({office_label(office)})")
        rows.append(kept_row(cells, col, office, kind in COUNTY_FILED, blanked))
    kept = {"title": title, "url": PORTAL.format(eid=eid), "fetched": dt.date.today().isoformat(), "sha256": hashlib.sha256(raw).hexdigest(),
            "bytes": len(raw), "items": len(grid), "legend": legend, "counties": counties,
            "columns": ["Office", "Contest", "District", "DistrictType", "Name", "Party", "Ballot Order", "Status",
                        "County (only on a row for an office filed in its own county)"],
            "by_office": dict(sorted(by_office.items())), "blanked": blanked[0], "rows": rows}
    del raw, page, grid
    keep_json(path, kept)
    return kept


def rows_digest(rows):
    return hashlib.sha256(json.dumps(rows, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def read_views(folder, whole, say, force=False):
    """The same list asked county by county, the 33 codes of its own county menu: the rows for offices filed in their
    own county (allowed cells), and one count by office of every other row on all the views together. Kept for as long
    as the whole list's county and judge rows are the ones these views were read against."""
    path = os.path.join(folder, "nm_2026_general_local_views.json")
    want = rows_digest(whole["rows"])
    if not force and os.path.exists(path):
        kept = json.load(open(path, encoding="utf-8"))
        if kept.get("of") == want:
            return kept
    title = LISTS["general"][1]
    views, other, items, blanked = {}, Counter(), 0, [0]
    say(f"      {LOCAL}: reading the candidate list county by county (33 views, one at a time)")
    for code, name in sorted(whole["counties"].items()):
        what = f"the candidate list's view for {name} County"
        url = VIEW.format(eid=GEN_EID, cty=code)
        raw = fetch(url, "text/html", what, expect=b'class="rgHeader')
        page, col, grid = open_grid(raw, title, what)
        if re.findall(r'<option[^>]*selected="selected"[^>]*value="(\d+)"', county_menu(page)) != [code]:
            stop(f"{what} is not that county's: its county menu shows another choice")
        rows = []
        for cells in grid:
            office = text(cells[col["office"]])
            if local_kind(office) in COUNTY_FILED:
                rows.append(kept_row(cells, col, office, False, blanked))
            else:
                other[office_label(office)] += 1            # counted with every other view's; nothing else of the row is read
        items += len(grid)
        views[code] = {"county": name, "url": url, "fetched": dt.date.today().isoformat(), "sha256": hashlib.sha256(raw).hexdigest(),
                       "bytes": len(raw), "rows": rows}
        del raw, page, grid
    kept = {"of": want, "fetched": dt.date.today().isoformat(), "items": items, "other": dict(sorted(other.items())), "blanked": blanked[0],
            "views": views}
    keep_json(path, kept)
    return kept


def reconcile(whole, views):
    """The whole list against its county views. Every row for an office filed in its own county must be on exactly the
    view of the county the whole list names, cell for cell; every other office must be wholly on the views or wholly
    off them (filed with the Secretary of State); and the rows must add up."""
    a = Counter((r["County"],) + tuple(r[k] for k in KEY) for r in whole["rows"] if local_kind(r["Office"]) in COUNTY_FILED)
    b = Counter((v["county"],) + tuple(r[k] for k in KEY) for v in views["views"].values() for r in v["rows"])
    if a != b:
        only_a, only_b = a - b, b - a
        where = sorted({k[0] or "no county" for k in only_a} | {k[0] for k in only_b})
        stop(f"the whole list and its county views differ: {sum(only_a.values())} rows only on the whole list, {sum(only_b.values())} only on "
             f"a county view (counties: {', '.join(where)})")
    filed_here = {office_label(r["Office"]) for r in whole["rows"] if local_kind(r["Office"]) in COUNTY_FILED}
    on_views, with_state, split = {}, {}, []
    for label, n in whole["by_office"].items():
        if label in filed_here:
            continue
        m = views["other"].get(label, 0)
        if m == n:
            on_views[label] = n
        elif m == 0:
            with_state[label] = n
        else:
            split.append(f"{label} ({n} on the whole list, {m} on the county views)")
    stray = sorted(set(views["other"]) - set(whole["by_office"]))
    if split or stray:
        stop("the whole list and its county views count other offices differently: " + "; ".join(split + [f"{s} (on a view only)" for s in stray]))
    matched = sum(b.values())
    if views["items"] != matched + sum(on_views.values()) or whole["items"] != views["items"] + sum(with_state.values()):
        stop(f"the rows do not add up: {whole['items']} on the whole list, {views['items']} on the county views, "
             f"{sum(with_state.values())} for offices on no view")
    return {"matched": matched, "on_views": on_views, "with_state": with_state}


# ---------- the three smaller sources ----------

def judicial_districts(folder, by_key, say):
    """({judicial district number: [county codes]}, what was kept) from the New Mexico Courts' own page, kept a month.
    The page must name thirteen districts and every county exactly once."""
    path = os.path.join(folder, "nm_judicial_districts.json")
    kept = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else None

    def codes_of(found):
        out, seen = {}, Counter()
        for n, names in found["districts"].items():
            codes = []
            for name in names:
                hit = by_key.get(fold(name).replace(" ", ""))
                if not hit:
                    stop(f"the courts' page names a county the Census Bureau's county file does not have, under the {ORD_WORDS[int(n) - 1]} Judicial District")
                codes.append(hit[0])
                seen[hit[0]] += 1
            out[int(n)] = sorted(codes)
        if sorted(out) != list(range(1, 14)) or len(seen) != len(by_key) or any(v != 1 for v in seen.values()):
            stop(f"the courts' page does not give thirteen judicial districts that hold every county once ({len(out)} districts, {len(seen)} counties)")
        return out

    if not kept or not fresh(path, 30):
        try:
            raw = fetch(COURTS_URL, "text/html", "the New Mexico Courts' page of courts by district", expect=b"Judicial District")
            plain = H.unescape(re.sub(r"<[^>]+>", "\n", re.sub(r"(?s)<script.*?</script>|<style.*?</style>", "", raw.decode("utf-8", "replace"))))
            lines = [" ".join(s.split()) for s in plain.split("\n") if s.strip()]
            found = {}
            for i, line in enumerate(lines[:-1]):
                m = re.fullmatch("(" + "|".join(ORD_WORDS) + ") Judicial District", line)
                w = re.fullmatch(r"(?:For|Serving) (.+)", lines[i + 1]) if m else None
                if w:
                    names = [re.sub(r"\s+Count(?:y|ies)$", "", x).strip() for x in re.split(r"\s*,\s*(?:and\s+)?|\s+and\s+", w.group(1)) if x.strip()]
                    if found.setdefault(ORD_WORDS.index(m.group(1)) + 1, names) != names:
                        stop("the courts' page names two different sets of counties for one judicial district")
            got = {"title": "Courts by District", "url": COURTS_URL, "fetched": dt.date.today().isoformat(), "sha256": hashlib.sha256(raw).hexdigest(),
                   "bytes": len(raw), "kept": "each judicial district's counties, as the page words them; nothing else",
                   "districts": {str(n): v for n, v in sorted(found.items())}}
            del raw, plain, lines
            out = codes_of(got)                             # a page that no longer reads right is never kept over a copy that did
            keep_json(path, got)
            return out, got
        except LocalStop as e:
            if not kept:
                raise
            say(f"    {e} Using the copy of the courts' page kept on {kept['fetched']}.")
    return codes_of(kept), kept


def proclamation(folder, say):
    """Is the proclamation on the Secretary's site still the scan PROCLAIMED was typed from? The file is fetched once a
    month for its fingerprint and is not kept (it is a list of offices; the receipt is)."""
    path = os.path.join(folder, "nm_2026_general_proclamation.json")
    kept = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else None
    if kept and fresh(path, 30):
        return kept
    try:
        raw = fetch(PROCLAMATION_URL, "application/pdf,*/*", "the General Election Proclamation", expect=b"%PDF")
    except LocalStop:
        if not kept:
            raise
        say(f"    {LOCAL}: the proclamation could not be read again; its fingerprint of {kept['fetched']} stands")
        return kept
    digest = hashlib.sha256(raw).hexdigest()
    kept = {"title": "2026 General Election Proclamation", "url": PROCLAMATION_URL, "fetched": dt.date.today().isoformat(), "sha256": digest,
            "bytes": len(raw), "typed_from": PROCLAMATION_SHA, "same": digest == PROCLAMATION_SHA}
    del raw
    keep_json(path, kept)
    return kept


def vote_for(folder, say):
    """Each county contest of the June 2 primary with the number its ballot said to vote for, from the results site's
    own export. Four columns are read (contest number, contest name, district, vote-for); no name and no vote is.
    Asked once: the primary is over and certified. None when it cannot be read (the loader then says less)."""
    path = os.path.join(folder, "nm_2026_primary_county_contests.json")
    if os.path.exists(path):
        return json.load(open(path, encoding="utf-8"))
    try:
        raw = fetch(VOTE_FOR_CSV, "text/csv,*/*", "the results site's export of county contests", expect=b"RaceID,RaceName,")
        rd = csv.reader(io.StringIO(raw.decode("utf-8-sig", "replace")))
        head = [h.strip() for h in next(rd)]
        at = {k: head.index(k) for k in ("RaceID", "RaceName", "AreaNum", "VoteFor")}
        contests = {}
        for n, row in enumerate(rd, 2):
            if not row:
                continue
            if len(row) <= max(at.values()):
                raise ValueError(f"line {n} is short")
            parts = [p.strip() for p in row[at["RaceName"]].split(" - ")]
            if len(parts) != 3 or parts[1] != parts[2] or not row[at["VoteFor"]].strip().isdigit():
                raise ValueError(f"line {n}: a contest name or a vote-for number that is not read")
            item = {"office": parts[0], "county": parts[1], "area": row[at["AreaNum"]].strip(), "vote_for": int(row[at["VoteFor"]])}
            if contests.setdefault(row[at["RaceID"]].strip(), item) != item:
                raise ValueError(f"line {n}: one contest number, two descriptions")
    except (LocalStop, ValueError, StopIteration) as e:
        say(f"    {LOCAL}: the June primary's county contests could not be read ({str(e).replace(LOCAL + ': ', '')}); the number of seats of an "
            "at-large contest is then taken from the proclamation alone")
        return None
    kept = {"title": "2026 Primary Election results: county contests", "url": VOTE_FOR_CSV, "fetched": dt.date.today().isoformat(),
            "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw), "kept": "each contest's office, county, district and vote-for number; no name, no vote",
            "contests": sorted(contests.values(), key=lambda c: (c["county"], c["office"], c["area"]))}
    del raw
    keep_json(path, kept)
    return kept


# ---------- one contest ----------

def _race(rid, level, kind, office, jurisdiction, jid, counties, district=None, seat=None, special=0, partisan=1, notes=()):
    return {"race_id": rid + ("-S" if special else ""), "level": level, "office_kind": kind, "office": office, "jurisdiction": jurisdiction,
            "jurisdiction_id": jid, "counties": sorted(counties), "district": district, "seat": seat, "special": int(special), "partisan": partisan,
            "notes": list(notes)}


def countywide_race(fips, cfull, list_office):
    kind, office = COUNTYWIDE[list_office]
    return _race(f"2026-{STATE}-{fips}-{kind.replace('_', '-')}", "county", kind, office, cfull, fips, [fips])


def commissioner_race(fips, cfull, d):
    return _race(f"2026-{STATE}-{fips}-county-commissioner-{d}", "county", "county_commissioner", "County Commissioner", cfull, fips, [fips],
                 district=str(d))


def at_large_race(fips, cfull, name):
    """The list's "County Commissioner At Large" contests, told apart by the name the first Contest column gives them."""
    if name == "County Councilor":
        return _race(f"2026-{STATE}-{fips}-county-council-at-large", "county", "county_council", "County Councilor", cfull, fips, [fips], seat="At Large")
    if name == "County Commissioner":
        return _race(f"2026-{STATE}-{fips}-county-commissioner-at-large", "county", "county_commissioner", "County Commissioner", cfull, fips, [fips],
                     seat="At Large")
    m = re.fullmatch(r"County Commissioner District 0*(\d+)", name, re.I)
    if m:
        d = m.group(1)
        return _race(f"2026-{STATE}-{fips}-county-commissioner-at-large-district-{d}", "county", "county_commissioner", "County Commissioner", cfull, fips,
                     [fips], seat=f"District {d}",
                     notes=[f"The Secretary of State's list files this contest among the at-large commissioner contests, under the name \"County Commissioner District {d}\"."])
    return None


def magistrate_race(fips, cfull, div, said=None):
    return _race(f"2026-{STATE}-{fips}-magistrate" + (f"-division-{div}" if div else ""), "court", "magistrate", "Magistrate Judge", cfull, fips, [fips],
                 seat=f"Division {div}" if div else None, notes=[f"The Secretary of State's list words this contest \"{said}\"."] if said else [])


def municipal_race(fips, cfull, said=None):
    return _race(f"2026-{STATE}-{fips}-municipal-court", "court", "municipal_court", "Municipal Judge", cfull, fips, [fips],
                 notes=[f"The Secretary of State's list words this contest \"{said}\"."] if said else [])


def district_race(n, div, counties, special=False, retention=False):
    name, jid = f"{ORD_WORDS[n - 1]} Judicial District", f"{STATE}-JD{n}"
    if retention:
        return _race(f"2026-{STATE}-JD{n}-district-court-retention-division-{div}", "court", "district_court_retention",
                     "District Court Judge (retention vote)", name, jid, counties, district=str(n), seat=f"Division {div}", partisan=0)
    return _race(f"2026-{STATE}-JD{n}-district-court" + (f"-division-{div}" if div else ""), "court", "district_court", "District Court Judge", name, jid,
                 counties, district=str(n), seat=f"Division {div}" if div else None, special=special)


def metro_race(fips, cfull, div, special=False, retention=False):
    if retention:
        return _race(f"2026-{STATE}-{fips}-metropolitan-court-retention-division-{div}", "court", "metropolitan_court_retention",
                     "Judge of the Metropolitan Court (retention vote)", cfull, fips, [fips], seat=f"Division {div}", partisan=0)
    return _race(f"2026-{STATE}-{fips}-metropolitan-court-division-{div}", "court", "metropolitan_court", "Judge of the Metropolitan Court", cfull, fips,
                 [fips], seat=f"Division {div}", special=special)


# ---------- the county and judge rows, ready to write ----------

def local_level(cache, cmap, say=print):
    """New Mexico's county offices and local judges on the November list, as rows ready to write (races, candidates,
    places, sources, gaps, notes) with the counts behind them. Nothing here touches the database."""
    folder = os.path.join(cache, "local")
    whole = read_whole(folder, say)
    views = read_views(folder, whole, say)
    try:
        facts = reconcile(whole, views)
    except LocalStop as first:                              # the list may have changed between the two readings: read both again, once
        say("    " + str(first).replace("; stopped (no row is printed)", "") + ". Reading the list and its county views again, once.")
        time.sleep(5)
        whole = read_whole(folder, say, force=True)
        views = read_views(folder, whole, say, force=True)
        facts = reconcile(whole, views)
    by_key = {k.replace(" ", ""): v for k, v in cmap.items()}      # 'donaana' -> ('35013', 'Doña Ana County')

    def county(name, what):
        hit = by_key.get(fold(name).replace(" ", "")) if name else None
        if not hit:
            stop(f"{what} names a county the Census Bureau's county file does not have, or none")
        return hit

    if sorted(fold(n) for n in whole["counties"].values()) != sorted(fold(n) for n in PROCLAIMED):
        stop("the candidate list's county menu and the proclamation's counties are not the same 33")
    districts, courts = judicial_districts(folder, by_key, say)
    proc = proclamation(folder, say)
    primary = vote_for(folder, say)
    legend = whole["legend"]
    problems, contests = [], {}
    if not proc["same"]:
        problems.append("the proclamation on the Secretary of State's site is no longer the scan its office list was typed from; read it again "
                        "(PROCLAIMED, PROCLAIMED_DISTRICT_SEATS, PROCLAIMED_METRO_SEATS and PROCLAMATION_SHA)")
    metro_fips, metro_full = county(METRO_COUNTY, "the proclamation's metropolitan court")

    def contest(info, n=None):
        have = contests.get(info["race_id"])
        if have is None:
            have = contests[info["race_id"]] = dict(info, on=[], off=Counter(), nameless=0, listed=False, key=None)
        elif any(have[k] != info[k] for k in ("level", "office_kind", "office", "jurisdiction_id", "counties", "district", "seat", "special", "partisan")):
            stop(f"row {n} of the candidate list: two different contests share the race id {info['race_id']}")
        else:
            have["notes"] += [x for x in info["notes"] if x not in have["notes"]]
        return have

    def proclaimed_district(n, div):
        seats = PROCLAIMED_DISTRICT_SEATS.get(n, ())
        return div in seats or (div is None and len(seats) == 1)

    counts = Counter()
    for n, r in enumerate(whole["rows"], 1):
        kind, tail, where = local_kind(r["Office"]), r["District"], f"row {n} of the candidate list"
        if not r["Contest"] or not r["Contest"].endswith(tail):
            stop(f"{where}: the contest's title is blank or does not end with its district")
        if kind in DISTRICT_TYPE and r["DistrictType"] != DISTRICT_TYPE[kind]:
            problems.append(f"{where}: the list's district type for {office_label(r['Office'])} is {r['DistrictType']!r}, not {DISTRICT_TYPE[kind]!r}")
        if kind in COUNTY_FILED:
            fips, cfull = county(r["County"], where)
        info, key = None, None
        if kind == "countywide":
            if tail or r["Contest"] != r["Office"]:
                stop(f"{where}: a countywide office ({r['Office']}) with a district")
            info, key = countywide_race(fips, cfull, r["Office"]), (r["Office"], fips, "")
        elif kind == "commissioner":
            m = re.fullmatch(r"(?:COUNTY COMMISSION )?DIST(?:RICT)? 0*(\d+)", tail, re.I)
            if not m:
                stop(f"{where}: a county commissioner's district that is not read")
            info, key = commissioner_race(fips, cfull, m.group(1)), (r["Office"], fips, m.group(1))
        elif kind == "at_large":
            info = None if tail else at_large_race(fips, cfull, r["Contest"])
            if not info:
                stop(f"{where}: an at-large commissioner contest whose name is not read")
            key = (r["Office"], fips, "")
        elif kind == "magistrate":
            m = re.fullmatch(r"(?:MAGISTRATE(?: COURT)? )?DIVISION 0*(\d+)", tail, re.I)
            alone = re.fullmatch(r"MAGISTRATE(?:\s*-\s*(.+))?", tail, re.I)
            if m:
                info = magistrate_race(fips, cfull, m.group(1))
            elif alone and (not alone.group(1) or fold(alone.group(1)) == fold(r["County"])):
                info = magistrate_race(fips, cfull, None)
            elif re.fullmatch(r"MAGISTRATE DISTRICT \d+", tail, re.I):
                info = magistrate_race(fips, cfull, None, said=r["Contest"])      # a district number of the list's own, not a division
            else:
                stop(f"{where}: a magistrate judge's division that is not read")
        elif kind == "municipal":
            if not re.fullmatch(r"MUNICIPAL DISTRICT \d+", tail, re.I):
                stop(f"{where}: a municipal judge's district that is not read")
            info = municipal_race(fips, cfull, said=r["Contest"])
        elif kind in ("district", "district_retention"):
            got = judicial(tail)
            if not got or (kind == "district_retention" and (got[1] is None or r["Office"] != "Judicial Retention District Court Judge " + tail)):
                stop(f"{where}: a judicial district or division that is not read")
            dn, div = got
            if kind == "district":
                special = proclaimed_district(dn, div)
                info = district_race(dn, div, districts[dn], special=special)
                if div is None and special:
                    info["notes"].append(f"The Secretary of State's proclamation calls this seat Division {PROCLAIMED_DISTRICT_SEATS[dn][0]}.")
                if not special:
                    problems.append(f"{info['race_id']}: a district court seat on the candidate list that the proclamation does not list")
            else:
                info = district_race(dn, div, districts[dn], retention=True)
                if not (r["DistrictType"] or "").upper().startswith(ORD_WORDS[dn - 1].upper()):
                    problems.append(f"{where}: the list's district type does not name the {ORD_WORDS[dn - 1]} Judicial District")
        elif kind in ("metro", "metro_retention"):
            m = re.fullmatch(r"DIVISION 0*(\d+)", tail, re.I)
            if not m or (kind == "metro_retention" and r["Office"] != "Judicial Retention Judge of the Metropolitan Court " + tail):
                stop(f"{where}: a metropolitan court division that is not read")
            div = int(m.group(1))
            if kind == "metro":
                info = metro_race(metro_fips, metro_full, div, special=div in PROCLAIMED_METRO_SEATS)
                if div not in PROCLAIMED_METRO_SEATS:
                    problems.append(f"{info['race_id']}: a metropolitan court seat on the candidate list that the proclamation does not list")
            else:
                info = metro_race(metro_fips, metro_full, div, retention=True)
        else:
            stop(f"{where}: an office this loader does not know")
        c = contest(info, n)
        c["listed"], c["key"] = True, key or c["key"]
        counts["rows"] += 1
        if r["Status"] in OFF:
            c["off"][r["Status"]] += 1
            counts["off"] += 1
        elif r["Status"] not in ON:
            stop(f"{where}: a status that is not read ({r['Status']!r})")
        elif not r["Name"]:
            c["nameless"] += 1
            counts["nameless"] += 1
        else:
            c["on"].append(r)

    # ---- the proclamation as the checklist: an office it lists that the candidate list has no row for is kept, empty
    proclaimed, empty = set(), []

    def expect(options, any_of=None):
        ids = [o["race_id"] for o in options]
        proclaimed.update(ids)
        if any_of:
            proclaimed.update(any_of)
        if not any(i in contests for i in ids) and not any_of:
            c = contest(options[0])
            c["notes"].append(NO_ONE)
            empty.append(c["race_id"])

    seats, positions = {}, {}                               # race id -> the number the proclamation says are elected, and its positions
    for cname, (mag, wide, (how, which)) in PROCLAIMED.items():
        fips, cfull = county(cname, "the proclamation's office list")
        for w in wide.split():
            expect([municipal_race(fips, cfull)] if w == "municipal" else [countywide_race(fips, cfull, PROCLAIMED_WORD[w])])
        for d in mag:
            mine = [i for i in contests if i.startswith(f"2026-{STATE}-{fips}-magistrate")]
            expect([magistrate_race(fips, cfull, d or None)], any_of=mine if d == 0 else None)
        if how == "District":
            for d in which:
                expect([commissioner_race(fips, cfull, d), at_large_race(fips, cfull, f"County Commissioner District {d}")])
        elif how == "Position":
            info = at_large_race(fips, cfull, "County Commissioner")
            expect([info])
            seats[info["race_id"]], positions[info["race_id"]] = len(which), and_names(f"Position {p}" for p in which)
        else:
            info = at_large_race(fips, cfull, "County Councilor")
            expect([info])
            seats[info["race_id"]] = which[0]
    for dn, divs in PROCLAIMED_DISTRICT_SEATS.items():
        for div in divs:
            expect([district_race(dn, div, districts[dn], special=True)] + ([district_race(dn, None, districts[dn], special=True)] if len(divs) == 1 else []))
    for div in PROCLAIMED_METRO_SEATS:
        expect([metro_race(metro_fips, metro_full, div, special=True)])
    for rid, c in contests.items():
        if c["partisan"] and c["listed"] and rid not in proclaimed:
            problems.append(f"{rid}: on the candidate list but not among the offices the proclamation lists")

    # ---- how many each county contest elects: the June primary's vote-for number, and the proclamation's count
    voted = defaultdict(set)
    for item in (primary or {}).get("contests", []):
        hit = by_key.get(fold(item["county"]).replace(" ", ""))
        m = re.search(r"(\d+)\s*$", item["area"])
        if hit:
            voted[(item["office"], hit[0], m.group(1) if m else "")].add(item["vote_for"])
    for rid, c in contests.items():
        got = voted.get(c["key"]) if c["key"] else None
        want = seats.get(rid, 1)
        if got and got != {want}:
            problems.append(f"{rid}: the June primary ballot said vote for {sorted(got)}, the proclamation gives {want}")
            seats.pop(rid, None)
        c["voted"] = bool(got)

    # ---- races and candidates
    def party_of(code, rid):
        if code not in legend:
            stop(f"{rid}: a party code that is not in the list's key")
        return legend[code]

    races, cands, gaps = [], [], []
    for rid, c in sorted(contests.items()):
        notes = ([UNEXPIRED] if c["special"] else []) + list(c["notes"])
        if not c["partisan"]:
            notes.append(RETENTION_VOTE)
            if len(c["on"]) != 1:
                problems.append(f"{rid}: a retention vote with {len(c['on'])} names")
        if rid in seats and seats[rid] > 1:
            notes.append(f"Voters choose {seats[rid]}.")
            if rid in positions:                            # the proclamation lists positions, the candidate list one contest
                if c["voted"]:
                    notes.append(f"The Secretary of State's proclamation calls the {number(seats[rid])} seats {positions[rid]}; the candidate list and "
                                 "the June primary's results carry them as one contest.")
                else:
                    notes[-1] = (f"The Secretary of State's proclamation calls for {number(seats[rid])} commissioners here, {positions[rid]}; the "
                                 "candidate list files the candidates under one contest and does not say which position each seeks.")
                    gaps.append((STATE, "race", rid, c["jurisdiction"], "which position each candidate seeks",
                                 f"The Secretary of State's proclamation lists {number(seats[rid])} commissioner positions for this county and the "
                                 "candidate list files every candidate under one contest; the June primary's results, which would say whether "
                                 "voters choose them in one contest, could not be read on this run.", whole["url"]))
        for status, v in sorted(c["off"].items()):
            notes.append(f"The Secretary of State's list also carries {number(v)} name{'s' if v > 1 else ''} marked {status}, left off here.")
        if c["nameless"]:
            notes.append(f"{number(c['nameless']).capitalize()} row{'s' if c['nameless'] > 1 else ''} of the Secretary of State's list for this contest "
                         f"{'are' if c['nameless'] > 1 else 'is'} left out: the name cell did not hold a name.")
        if c["listed"] and not c["on"]:
            notes.append("No name on the Secretary of State's list for this contest is still on the ballot.")
        orders, names = [], set()
        for r in c["on"]:
            wi = bool(WRITE_MARK.search(r["Name"]))
            name = shown(r["Name"])
            if not name or name in names:
                stop(f"{rid}: a name that is blank once its write-in mark is taken off, or the same name twice")
            names.add(name)
            if c["partisan"]:
                party = party_of(r["Party"], rid) if r["Party"] else "No party"
                code, inc, note = party_code(party), 0, ([WRITE_IN] if wi else []) + [CAPS]
            else:
                if r["Party"]:
                    problems.append(f"{rid}: a retention row with a party code")
                party, code, inc, note = NONPARTISAN, "N", 1, ["Standing for retention as the sitting judge.", CAPS]
            order = int(r["Ballot Order"]) if c["partisan"] and not wi and r["Ballot Order"].isdigit() and r["Ballot Order"] != NO_PLACE else None
            orders.append(order)
            counts["write_in"] += int(wi)
            counts["no_order"] += int(order is None and not wi and bool(c["partisan"]))
            cands.append((rid, "general", GENERAL, name, party, code, order, inc, int(wi), None, None, None, None, LOCAL_SRC, " ".join(note)))
        given = [o for o in orders if o is not None]
        if len(given) != len(set(given)):
            problems.append(f"{rid}: two names with the same ballot order on the list")
        races.append((rid, STATE, c["level"], c["office_kind"], c["office"], c["jurisdiction"], c["jurisdiction_id"], json.dumps(c["counties"]),
                      c["district"], c["seat"], c["special"], c["partisan"], None, None, None, GENERAL, " ".join(notes) or None))

    # ---- the counts: every county and judge row is a candidate, a name left off, or a row without a name
    if counts["rows"] != len(whole["rows"]) or len(cands) + counts["off"] + counts["nameless"] != len(whole["rows"]):
        stop(f"{len(whole['rows'])} county and judge rows read, {len(cands)} candidates stored, {counts['off']} left off, {counts['nameless']} without a name")
    if len({(c[0], c[3]) for c in cands}) != len(cands):
        stop("a candidate is stored twice in one contest")
    local_rows = sum(n for label, n in whole["by_office"].items() if local_kind(label) or label.startswith("Judicial Retention "))
    if sum(whole["by_office"].values()) != whole["items"] or local_rows != len(whole["rows"]):
        stop("the whole list's rows by office do not add up")

    by_level, by_kind = Counter(r[2] for r in races), Counter(r[3] for r in races)
    county_races = [r for r in races if r[2] == "county"]
    court_races = [r for r in races if r[2] == "court"]
    reached = {f for r in races for f in json.loads(r[7])}
    used = sorted({int(r[8]) for r in races if r[3].startswith("district_court")})
    places = [("judicial", f"{STATE}-JD{n}", f"{ORD_WORDS[n - 1]} Judicial District", json.dumps(districts[n]), COURTS_SRC) for n in used]

    # ---- what the list cannot show
    gaps.append((STATE, "state", STATE, NAME, "offices added after the proclamation that nobody filed for",
                 "The Secretary of State's candidate list shows a contest only when someone is listed for it, so the checklist of offices is the "
                 "proclamation of January 26, 2026; an office put on the ballot after that date for which no candidate is listed would not be "
                 "seen here.", whole["url"]))
    gaps.append((STATE, "state", STATE, NAME, "elections that conservancy districts and other bodies run themselves",
                 "The Secretary of State's November list carries no contest for any city, school district or special district, and the Local Election "
                 "Act leaves conservancy districts out of the Regular Local Election; an election such a body holds on its own is not on the list and "
                 "would have to be read from that body's own notice.", LOCAL_ELECTIONS_URL))

    # ---- the two notes
    has = lambda w: [c for c, (_m, wide, _c) in PROCLAIMED.items() if w in wide.split()]
    mag_counties = [c for c, (mag, _w, _c) in PROCLAIMED.items() if mag]
    special_dc = sum(1 for r in races if r[3] == "district_court" and r[10])
    special_metro = sum(1 for r in races if r[3] == "metropolitan_court" and r[10])
    retention = sum(1 for r in races if r[3].endswith("_retention"))
    counties_words = lambda names: and_names(names) + (" counties" if len(names) > 1 else " County")
    calendar = (
        f"On November 3, 2026 New Mexico's counties elect, on the partisan ballot, a probate judge in each of the {len(PROCLAIMED)} counties, the county "
        f"commissioners whose terms are up (county councilors in Los Alamos County), a sheriff in {len(has('sheriff'))} counties, an assessor in "
        f"{len(has('assessor'))}, a county clerk in {counties_words(has('clerk'))} and a treasurer in {counties_words(has('treasurer'))}; magistrate "
        f"judges are elected in {len(mag_counties)} counties and a municipal judge in {counties_words(has('municipal'))}, {number(special_dc)} district "
        f"judgeships and {number(special_metro)} judgeships of the Bernalillo County Metropolitan Court are filled for unexpired terms, and sitting "
        f"district and metropolitan court judges face yes-or-no retention votes ({retention} of them). Cities, towns and villages, school boards and "
        "other local districts elect at the Regular Local Election in November of odd-numbered years, and a municipality that has not joined it at "
        "the Municipal Officer Election in March of even-numbered years, so none of their offices is on this ballot.")
    empties = [f"{r[4]}{', District ' + r[8] if r[8] and r[2] == 'county' else ''}{', ' + r[9] if r[9] else ''}, {r[5]}" for r in races if r[0] in empty]
    coverage = (
        f"Loaded from the Secretary of State's 2026 General Election Contest/Candidate List: {len(county_races)} contests for county offices in all "
        f"{len({r[6] for r in county_races})} counties (commissioners and councilors, sheriffs, assessors, clerks, a treasurer and probate judges) and "
        f"{len(court_races)} for local judges, shown with the judges (magistrate judges: {by_kind['magistrate']}; district court judges: "
        f"{by_kind['district_court']}; metropolitan court judges: {by_kind['metropolitan_court']}; a municipal judge: {by_kind['municipal_court']}; "
        f"retention votes: {retention}), {len(cands)} names in all, {counts['write_in']} of them declared write-in candidates. The list was read whole "
        f"and again county by county and the two readings agree; {counts['off']} names it marks Withdrawn or Disqualified are left off. "
        + (f"The proclamation lists {number(len(empties))} office{'s' if len(empties) > 1 else ''} nobody is on the list for ({'; '.join(empties)}), kept "
           "here with no candidate. " if empties else "")
        + "Not loaded: ballot questions (constitutional amendments, bond questions and any county question), which a candidate list does not carry; "
        "the June 2 primaries for these offices; and any office put on the ballot after the proclamation for which nobody is listed.")
    notes = [
        (STATE, "local_calendar", calendar,
         "New Mexico Secretary of State: General Election Proclamation of January 26, 2026 (the offices on this ballot) and Local Election Act "
         "Information (the Regular Local Election and the Municipal Officer Election, under the Local Election Act of 2018 as amended in 2019, "
         "NMSA 1978, Chapter 1, Article 22)", LOCAL_ELECTIONS_URL),
        (STATE, "local_coverage", coverage, "New Mexico Secretary of State: 2026 General Election Contest/Candidate List, and the General Election "
         "Proclamation of January 26, 2026", whole["url"]),
    ]

    # ---- sources: one row per page or file read
    with_state = sum(facts["with_state"].values())
    sources = [
        (LOCAL_SRC, STATE, "official candidate list", "New Mexico Secretary of State",
         "2026 General Election Contest/Candidate List (November 3, 2026): county offices and local judges",
         whole["url"], "", whole["fetched"], whole["sha256"], len(whole["rows"]),
         f"The candidate portal's grid of every office ({whole['items']} rows on one page), cut down in memory to its {len(whole['rows'])} rows for "
         "county offices and for magistrate, municipal, district and metropolitan court judges. Cells read, by their headings: both Contest columns, "
         "District, DistrictType, Name, Party, Ballot Order, Status, and Filing County only on a row for an office filed in its own county; on a "
         "district or metropolitan court row that cell is where the candidate lives and is never read. The addresses, city, ZIP, phones, e-mail, "
         "website and filing time are never read, and only the cut-down rows are kept; the fingerprint is of the page as it came. "
         f"{len(cands)} names stored, {counts['off']} marked Withdrawn or Disqualified left off, {counts['write_in']} declared write-ins; ballot order "
         f"as the list gives it (99 means none: {counts['no_order']} printed names have none). Checked against the same list read county by county: "
         f"{facts['matched']} rows for offices filed in their own county match cell for cell, {sum(facts['on_views'].values())} rows for other offices "
         f"are on the county views and {with_state} are for offices filed with the Secretary of State, which makes {whole['items']}."
         + (f" Kept cells blanked because they read like contact details: {whole['blanked']}." if whole["blanked"] else "")),
    ]
    for code, v in sorted(views["views"].items()):
        sources.append((VIEW_SRC.format(code=code), STATE, "official candidate list", "New Mexico Secretary of State",
                        f"2026 General Election Contest/Candidate List (November 3, 2026), {v['county']} County's view: county offices, magistrate and "
                        "municipal judges", v["url"], "", v["fetched"], v["sha256"], len(v["rows"]),
                        f"{v['county']} County's own view of the list (the county menu's choice {code}): {len(v['rows'])} rows for offices filed in the "
                        "county, matched against the whole list cell for cell. Cells read, by their headings: both Contest columns, District, "
                        "DistrictType, Name, Party, Ballot Order and Status; the addresses, city, ZIP, phones, e-mail, website, filing county and "
                        "filing time are never read. The view's other rows (legislative, education commission, district court and metropolitan "
                        "court candidates who filed in the county) are only counted, with every other view's, by office; nothing else of them "
                        "is read, and the page was not kept."))
    n_proclaimed = (sum(len(wide.split()) + len(mag) + (len(which) if how != "Councilors" else which[0]) for mag, wide, (how, which) in PROCLAIMED.values())
                    + sum(len(v) for v in PROCLAIMED_DISTRICT_SEATS.values()) + len(PROCLAIMED_METRO_SEATS))
    sources += [
        (PROC_SRC, STATE, "official proclamation", "New Mexico Secretary of State", "2026 General Election Proclamation (English), filed January 26, 2026",
         PROCLAMATION_URL, PROCLAMATION_DAY, proc["fetched"], proc["sha256"], n_proclaimed,
         "The checklist of offices. The file is a scan, so its list of county offices, county by county, and of the district and metropolitan court "
         f"judgeships to fill an unexpired term was typed from it once ({n_proclaimed} seats) and is kept in the loader; the fingerprint is of the "
         "file as fetched, and " + ("it is the scan the list was typed from. " if proc["same"] else "IT IS NO LONGER THE SCAN THE LIST WAS TYPED FROM: read it again. ")
         + "It gives what the candidate list cannot: an office nobody is listed for, how many councilors Los Alamos County elects, the two "
         "commissioner positions of Union County, and which judgeships are for an unexpired term. The file names no candidate and has no contact "
         "columns; it is not kept, only its fingerprint."),
        (COURTS_SRC, STATE, "official court directory", "New Mexico Courts (the state's Judicial Branch)", courts["title"] + ": the counties of each judicial district",
         courts["url"], "", courts["fetched"], courts["sha256"], len(courts["districts"]),
         "Only each judicial district's counties are read and kept, nothing else of the page; it must name thirteen districts and every county "
         "exactly once. A district court contest is shown for the counties of its judicial district, never for the county a candidate filed in."),
    ]
    if primary:
        sources.append(
            (VOTE_FOR_SRC, STATE, "official results", "New Mexico Secretary of State",
             "2026 Primary Election results (June 2, 2026): county contests, the results site's CSV export", primary["url"], "2026-06-23", primary["fetched"],
             primary["sha256"], len(primary["contests"]),
             "Read only for the number each county contest's ballot said to vote for, which is the number elected in November: four columns (contest "
             "number, contest name, district and vote-for). No candidate's name and no vote is read or kept, and the export has no contact columns; "
             "the fingerprint is of the export as it came."))

    # ---- the last look before anything is written: nothing that reads like contact details, by the trial check's test and the page builder's
    for table, items in (("sl_races", [(r[0], (r[4], r[5], r[8], r[9], r[16])) for r in races]),
                         ("sl_candidates", [(c[0], (c[3], c[4], c[14])) for c in cands]),
                         ("sl_places", [(p[1], (p[2],)) for p in places]),
                         ("sl_gaps", [(g[2], (g[3], g[4], g[5])) for g in gaps]),
                         ("sl_notes", [(x[1], (x[2], x[3])) for x in notes]),
                         ("sl_sources", [(s[0], (s[3], s[4], s[10])) for s in sources])):
        for ident, texts in items:
            if any(reads_like_contact(t) for t in texts):
                stop(f"a text for {table} ({ident}) reads like contact details")

    return {"races": races, "cands": cands, "places": places, "sources": sources, "gaps": gaps, "notes": notes, "problems": problems, "empty": empty,
            "by_level": dict(by_level), "by_kind": dict(by_kind), "counties": len(reached), "counts": dict(counts), "rows": len(whole["rows"]),
            "items": whole["items"], "facts": facts, "fetched": whole["fetched"], "retention": retention, "voted": bool(primary)}


# ---------- the load ----------

def load(db_path, say=print, cache=CACHE):
    """New Mexico's rows into the database at db_path: the state races, then the county offices and the local judges
    (their cut-down copies are kept in <cache>/local/). Everything is read and checked before anything is written."""
    if os.path.abspath(db_path) == os.path.abspath(os.path.join(HERE, "ballot_2026.sqlite")):
        raise SystemExit("New Mexico (state races): this loader never writes ballot_2026.sqlite")
    net.patient_lookups()
    try:
        return _load(db_path, say, cache)
    finally:
        _PAGES.clear()                                     # the pages held for this run are let go, whatever happened


def _load(db_path, say, cache):
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

    # ---- the county offices and the local judges: read and checked whole before anything is written
    local = local_level(cache, cmap, say)
    clash = {r[0] for r in race_rows} & {r[0] for r in local["races"]}
    if clash:
        raise SystemExit(f"{LOCAL}: a county or judge contest shares its race id with a state race ({sorted(clash)[:3]}); stopped")

    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA + EXTRA_SCHEMA)
    with con:
        con.execute("DELETE FROM sl_candidates WHERE race_id IN (SELECT race_id FROM sl_races WHERE state = ?) OR race_id LIKE ?",
                    (STATE, f"2026-{STATE}-%"))
        con.execute("DELETE FROM sl_races WHERE state = ?", (STATE,))
        con.execute("DELETE FROM sl_places WHERE source_id IN (SELECT source_id FROM sl_sources WHERE state = ?) OR source_id LIKE ?",
                    (STATE, "nm-%"))
        con.execute("DELETE FROM sl_sources WHERE state = ?", (STATE,))
        con.execute("DELETE FROM sl_gaps WHERE state = ?", (STATE,))
        con.execute("DELETE FROM sl_notes WHERE state = ?", (STATE,))
        con.executemany("INSERT INTO sl_races VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", race_rows + local["races"])
        con.executemany("INSERT INTO sl_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", cands + local["cands"])
        con.executemany("INSERT INTO sl_places VALUES (?,?,?,?,?)", place_rows + local["places"])
        con.executemany("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", src + local["sources"])
        con.executemany("INSERT INTO sl_gaps VALUES (?,?,?,?,?,?,?)", local["gaps"])
        con.executemany("INSERT INTO sl_notes VALUES (?,?,?,?,?)", local["notes"])
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

    # ---- the county and judge rows: counts only
    lk, lc, lf = local["by_kind"], local["counts"], local["facts"]
    county_ids = {r[0] for r in local["races"] if r[2] == "county"}
    county_kinds = Counter(r[3] for r in local["races"] if r[2] == "county")
    county_n, county_c = len(county_ids), sum(1 for c in local["cands"] if c[0] in county_ids)
    say(f"    {LOCAL}: {county_n} county contests ({', '.join(f'{k} {v}' for k, v in sorted(county_kinds.items()))}) "
        f"with {county_c} candidates, and {len(local['races']) - county_n} contests for local judges (magistrate {lk.get('magistrate', 0)}, municipal "
        f"court {lk.get('municipal_court', 0)}, district court {lk.get('district_court', 0)}, metropolitan court {lk.get('metropolitan_court', 0)}, "
        f"retention votes {local['retention']}) with {len(local['cands']) - county_c}; {local['counties']} of 33 counties reached; "
        f"{lc.get('off', 0)} withdrawn or disqualified left off, {lc.get('write_in', 0)} declared write-ins, {lc.get('no_order', 0)} printed names "
        "with no ballot order on the list")
    say(f"    {LOCAL}: the list read whole ({local['items']} rows, {local['rows']} of them county and judge rows) and again county by county: "
        f"{lf['matched']} rows for offices filed in their own county match cell for cell, {sum(lf['on_views'].values())} rows for other offices are on "
        f"the county views, {sum(lf['with_state'].values())} are for offices filed with the Secretary of State"
        + ("" if local["voted"] else "; the June primary's vote-for numbers were not read"))
    for rid in local["empty"]:
        say(f"    {LOCAL}: on the proclamation with no candidate on the list (kept, empty): {rid}")
    for p in local["problems"]:
        say(f"    CHECK {LOCAL}: {p}")
    return len(cands) + len(local["cands"])


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
