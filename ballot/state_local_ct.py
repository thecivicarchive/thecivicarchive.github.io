"""
ballot/state_local_ct.py - Connecticut's state races on the November 3, 2026 ballot: all 36 seats of the State Senate
and all 151 of the House of Representatives (Connecticut elects its whole General Assembly every two years, so no seat
is skipped), and the five statewide offices elected every four years in the Governor's year: Governor and Lieutenant
Governor (one vote for the pair in November), Secretary of the State, Treasurer, Comptroller and Attorney General; with
the party primaries that had a field and their official votes. Written into ballot_local_2026.sqlite (never
ballot_2026.sqlite), Connecticut's rows only. Congress is left to the federal loader (ballot/lists/ct.py). The two local
offices that share the ballot, Judge of Probate and Registrar of Voters, are read from the same sample ballots: see
"The local level" below.

Sources: the Secretary of the State's own, the same two the federal loader reads for Congress.

  November ballot   "November 3, 2026, State Election, Sample Town Ballots" (portal.ct.gov/sots, town-ballots/
                    2026-november-town-election-ballots): one PDF per town, posted town by town as each town's ballot is
                    approved (19 of 169 towns on 2026-09-30). Every ballot face is one voting district's ballot, headed
                    with its Congressional, Senatorial and Assembly District, and laid out as Connecticut's party-row grid
                    (a numbered column per office, a lettered row per party, each filled cell marked "2A", the party's
                    name at the left of its row). The loader finds the columns headed Governor and Lieutenant Governor,
                    Secretary of the State, Treasurer, Comptroller, Attorney General, State Senator and State
                    Representative, and for every row above "Write-in Votes" reads the party's name and the name printed
                    in each of those cells, using ballot/lists/ct.py's own word and line reading. Controls: every face
                    of every posted town must print the same statewide lines; every face carrying a Senatorial or
                    Assembly District must print the same lines for it; a town's ballot laid out in a way this reading
                    does not follow is set aside and named, never guessed at. A district none of whose towns has a
                    ballot posted yet gets its race row with a note saying so, and no November candidates.
                    The PDFs are kept in ballot_cache/ct/sl_ballots/ (a sample ballot prints names, parties and offices
                    and nothing else; a file the federal loader already holds at the same revision is copied, not
                    downloaded again), with what was read from them in sl_ct_2026_ballots_read.json.
  primaries         the Election Management System's public reporting (ctemspublic.pcctg.net, linked from the Secretary's
                    Election Results page): every 2026 party primary (08/11/2026 Democratic and Republican, and the
                    09/01/2026 Democratic primary for the 58th Assembly District), read from the JSON files its own page
                    loads (Elections.json; election/<id>/Version.json; that version's Lookupdata, stateVotes, townVotes,
                    townStatus and officePrecincts). The candidate records also carry an address field ("AD") and
                    another ("CO"): only the printed name ("NM") and party ("P") are ever read, and the cache
                    (sl_ct_2026_primaries_state.json) keeps only the state contests' names, parties, votes, town figures
                    and statuses. Controls: the towns' figures add up to each candidate's total, no town reports a
                    candidate without a total, and each share the file prints ("TO") matches the one worked out here.
                    A total is stored only when every town that voted in the contest is marked "( Official Results )"
                    and all its precincts are in. Connecticut primary ballots have no write-in line, so a field's total
                    is its candidates' votes. The top vote-getter advanced; where the district's November ballot is
                    posted, the winner must be on that party's line, or the row says so.
  holders           state_ct.sqlite (the Open States roster the state pages use): sitting legislators by chamber and
                    district, and the statewide officials it carries (Governor, Lieutenant Governor, Secretary of the
                    State, Attorney General; not the Treasurer or the Comptroller). Only ids, names, parties, chambers,
                    districts and offices are selected; the roster's contact columns are never read.

What is stored. 2026-CT-GOV, -SOS, -TREAS, -COMP, -AG; 2026-CT-SS<n> (State Senator, Senatorial District n) and
2026-CT-SH<n> (State Representative, Assembly District n). Names are as printed, first name first, the given names and
the family name on two lines of the cell joined. The Governor's cell prints the ticket, "Ned Lamont and Susan
Bysiewicz": the Governor is the candidate's name and the running mate is named in the row's note (as for Maryland).
Parties are as printed ("Democratic Party", "Working Families Party", "Independent Party", "Petitioning Candidate"). A
candidate nominated by several parties (cross-endorsement) is listed once with every line held, in row order, coloured by
the first major party among them, as the federal loader does; ballot order is the order of the candidates' first rows.
Registered write-in candidates are not printed on the ballot and are not stored. A candidate is the incumbent
(incumbent 1, state_member_id) only when the name fits the one sitting member of that chamber and district (or the
statewide officer) and that member fits no other candidate in the race; a sitting legislator running for another office
is given their roster id (not incumbent) when the name fits exactly one legislator of the same party.

The local level. Connecticut has no county government, so no county office is elected, and its towns hold their
regular municipal elections in odd-numbered years (C.G.S. 9-164). Two local offices are on the state election ballot:

  Judge of Probate      one in each of the 54 probate districts, every four years at the state election (C.G.S.
                        45a-18). The districts and the towns of each are section 45a-2 of the General Statutes, read
                        from the General Assembly's page of chapter 801 (a numbered list, "(28) The towns of Chaplin,
                        Colchester, ..."; the statute numbers the districts and gives them no names). One race per
                        district, level court (2026-CT-PD<n>), filed under every county its towns lie in. Its
                        candidates are the Judge of Probate column ("Probate Judge" on a bilingual ballot) of the first
                        posted town of the district, checked against every other posted town of it; ballots that
                        disagree leave the race without candidates and say so in sl_gaps. A district none of whose
                        towns is posted has its race and a note. Where a ballot is headed "Probate District N" the
                        number must be the statute's.
  Registrar of Voters   the towns that elect registrars this year (two-year terms from each state election, C.G.S.
                        9-190a, unless a town chose four-year terms, 9-189a): one race per town whose ballot prints the
                        column (2026-CT-M-<code>-registrar-of-voters, level township), the town named and keyed as the
                        Census Bureau's 2020 county subdivision codes file writes it ("Canaan town", CT-M-<code>). A
                        column printed with no name (only the write-in line) is kept as a contest with no candidate.

A ballot belongs to the town the Secretary's page links it under (or, where the link carries a note, the one town its
file is named for); every page of it must be headed with that town's name and print these two columns alike, or the
town is set aside and named in sl_gaps. Any other column a ballot prints (a town office its charter puts on this day, a
vacancy), and a grid that goes on to a second sheet, are not read yet: they are counted and named in sl_gaps, never
dropped. Ballot questions, printed below the grid, are not loaded. Local candidates carry a name, the party lines held
and the ballot order, and nothing else: no incumbent mark and no link to any other record.
Places: the eight counties (09001 to 09015) and the towns come from the 2020 codes file, because the Bureau's current
county file (cb_2024_us_county_500k) lists nine planning regions for Connecticut instead. The towns not posted yet are
covered by one sl_gaps row (registrars file every sample ballot ten days before early voting begins, C.G.S. 9-256 and
9-163aa: by October 9), and sl_notes says which local offices are on this ballot and what was read. Kept in
ballot_cache/ct/local/: the Census codes file (no personal data in it), the statute's districts and towns as JSON, the
fingerprint and town links of the Sample Town Ballots page, and what was read from each ballot's local columns
(headings, parties and names only).

Privacy: from every source only office, district, candidate name, party, ballot order and votes are read; nothing else
from any file is printed, logged, cached or stored.

    python -m ballot.state_local_ct <path to a test database> [--refresh]
"""

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

from ballot.check_local import EXTRA_SCHEMA, contact_like  # noqa: E402
from ballot.common import CACHE, fold, name_parts  # noqa: E402
from ballot.lists import ct as CT  # noqa: E402
from ballot.match import fits  # noqa: E402
from ballot.pdftext import PDF, page_runs  # noqa: E402
from states import net  # noqa: E402

STATE, FIPS = "CT", "09"
GENERAL = "2026-11-03"
ROSTER = os.path.join(HERE, "state_ct.sqlite")
TOWNS = 169
SENATE_SEATS, HOUSE_SEATS, CONGRESS_SEATS = 36, 151, 5
READER = 1                                            # bump when state_columns reads a page differently
INDEX, PRIMS = "sl_ct_2026_ballots_read.json", "sl_ct_2026_primaries_state.json"
FED_INDEX = "ct_2026_ballots_read.json"
SRC_ROSTER = "ct-openstates-roster"
AGENCY = "Connecticut Secretary of the State"

# (key, the column heading as printed, office, office_kind)
OFFICES = (
    ("GOV", re.compile(r"\bGovernor and Lieutenant Governor\b"), "Governor and Lieutenant Governor", "governor"),
    ("SOS", re.compile(r"\bSecretary of the State\b"), "Secretary of the State", "secretary_of_state"),
    ("TREAS", re.compile(r"(?<!Town )\bTreasurer\b"), "Treasurer", "state_treasurer"),
    ("COMP", re.compile(r"\bComptroller\b"), "Comptroller", "comptroller"),
    ("AG", re.compile(r"\bAttorney General\b"), "Attorney General", "attorney_general"),
    ("SS", re.compile(r"\bState Senat(?:or|e)\b"), "State Senator", "state_senate"),      # Canterbury prints "State Senate"
    ("SH", re.compile(r"\bState Representative\b"), "State Representative", "state_house"),
)
OFFICE = {k: (title, kind) for k, _rx, title, kind in OFFICES}
OFFICE["LTG"] = ("Lieutenant Governor", "lieutenant_governor")                 # only if a party primary is held for it
STATEWIDE = ("GOV", "SOS", "TREAS", "COMP", "AG")
ROSTER_OFFICE = {"GOV": "governor", "SOS": "secretary of state", "AG": "attorney general", "LTG": "lt_governor"}
SENATE_HEAD = re.compile(r"\bSenatorial District(?:/[^\d]*?)?\s(\d{1,2})\b")
ASSEMBLY_HEAD = re.compile(r"\bAssembly District(?:/[^\d]*?)?\s(\d{1,3})\b")
HEADS = (("cd", CT.HEADING, "congressional", CONGRESS_SEATS), ("sd", SENATE_HEAD, "senatorial", SENATE_SEATS),
         ("ad", ASSEMBLY_HEAD, "assembly", HOUSE_SEATS))
# the state offices as the Management System names them
PRIMARY_OFFICE = ((re.compile(r"Governor"), "GOV"), (re.compile(r"Lieutenant Governor"), "LTG"),
                  (re.compile(r"Secretary of the State"), "SOS"), (re.compile(r"Treasurer"), "TREAS"),
                  (re.compile(r"Comptroller"), "COMP"), (re.compile(r"Attorney General"), "AG"),
                  (re.compile(r"State Senator (\d{1,2})"), "SS"), (re.compile(r"State Representative (\d{1,3})"), "SH"))
PRIMARY_NAME = re.compile(r"(\d\d)/(\d\d)/2026 -- (.*\bPrimary\b.*)")
CODES = {"Democratic Party": "DEM", "Republican Party": "REP", "Libertarian Party": "LIB", "Green Party": "GRE",
         "Working Families Party": "WFP", "Independent Party": "IND"}
MAJOR = {"Democratic Party": "D", "Republican Party": "R"}

# ---- the local level: judges of probate and registrars of voters, from the same sample ballots
LOCAL_READER = 1                                      # bump when local_columns reads a page differently
LOCAL_READ, LISTING, PROBATE_KEPT, COUSUB_FILE = ("ct_2026_local_ballots_read.json", "ct_2026_ballot_listing.json",
                                                  "ct_cgs_45a-2_probate_districts.json", "st09_ct_cousub2020.txt")
COUSUB_URL = "https://www2.census.gov/geo/docs/reference/codes2020/cousub/st09_ct_cousub2020.txt"
COUSUB_HEAD = "STATE|STATEFP|COUNTYFP|COUNTYNAME|COUSUBFP|COUSUBNS|COUSUBNAME|CLASSFP|FUNCSTAT"
STATUTES = "https://www.cga.ct.gov/current/pub/"                    # the General Assembly's own text of the General Statutes
PROBATE_URL, ELECTIONS_URL = STATUTES + "chap_801.htm", STATUTES + "chap_146.htm"
SRC_LISTING, SRC_PROBATE, SRC_CENSUS = "ct-sots-2026-ballot-listing", "ct-cga-cgs-45a-2", "ct-census-2020-cousub"
PROBATE_DISTRICTS, COUNTIES = 54, 8
STATUTE_MAX_AGE_DAYS = 30
EARLY_VOTING = dt.date.fromisoformat(GENERAL) - dt.timedelta(days=15)      # C.G.S. 9-163aa: it begins on the fifteenth day before the election
BALLOTS_DUE = EARLY_VOTING - dt.timedelta(days=10)                        # C.G.S. 9-256: sample ballots are filed at least ten days before that
ELSEWHERE = re.compile(r"\bRepresentative in Congress\b|\bUnited States Senator\b|\bPresidential Electors\b")      # the federal loader's columns
PROBATE_HEAD = re.compile(r"\bProbate District(?:/[^\d]*?)?\s(\d{1,2})\b")
# kind -> (the heading as printed, the office's title here); Greenwich's bilingual ballot prints "Probate Judge"
LOCAL_HEADS = (("probate", re.compile(r"\bJudge of Probate\b|\bProbate Judge\b")), ("registrar", re.compile(r"\bRegistrars? of Voters\b")))
LOCAL_TITLE = {"probate": "Judge of Probate", "registrar": "Registrar of Voters"}
NOT_A_FULL_TERM = re.compile(r"(?i)\bvacanc|\bunexpired\b|\bto fill\b")      # a column so headed is another contest, not read yet
A_TOWNS_OWN = re.compile(r"(?i)\b(?:town|city|borough|municipal|board|constable|selectm[ae]n|council|clerk)\b")      # "City Treasurer" is not the State's
SHEETS = re.compile(r"\bSheet \d+ of (\d+)\b")
VOTE_FOR = re.compile(r"\bVote [Ff]or\s+(?:Any\s+|Up [Tt]o\s+)?([A-Za-z]+|\d+)\b")
NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
PLAIN_WORDS = re.compile(r"[A-Za-z][A-Za-z ,/'&().-]{1,79}")               # a heading that is plainly office words may be named in a gap
# the page builder's own last check is a little wider than the trial check's (it also stops at Court and Place)
BUILDER_STREET = re.compile(r"\b\d{1,6}\s+(?:[NSEW]\.?\s+)?[A-Za-z0-9.' -]{1,40}?\s(?:St|Street|Ave|Avenue|Rd|Road|Blvd|Boulevard|Dr|Drive|Ln|Lane|Way|Ct|Court|"
                            r"Cir|Circle|Pkwy|Parkway|Hwy|Highway|Trl|Trail|Pl|Place|Ter|Terrace)\b\.?", re.I)
REGISTRAR_NOTE = ("Voters choose 1. The candidate with the most votes and the candidate with the next most who is of another party become the "
                  "town's registrars, and a major party's candidate who is not one of those two is elected as well (C.G.S. 9-190).")
CALENDAR = ("On November 3, 2026 each of Connecticut's 54 probate districts elects its judge of probate for four years, and the towns whose "
            "registrars of voters are up elect them (registrars serve two years from each state election unless a town has chosen four-year "
            "terms); both offices are on the state election ballot with party lines. Connecticut has no county government, so no county office "
            "is elected. Selectmen, mayors, councils, town clerks, boards of education and other town officers are chosen at municipal elections "
            "in odd-numbered years, in November or in May, so they are not on this ballot unless a town's own charter or a vacancy puts one there.")
CALENDAR_SOURCE = ("Connecticut General Statutes sections 45a-18 (judges of probate), 9-190, 9-190a and 9-189a (registrars of voters), and 9-164 "
                   "and 9-185 (municipal elections and town officers)")

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

GOV_NOTE = ("Connecticut elects the Governor and Lieutenant Governor together in November: one vote for the pair, both names "
            "printed in one box on each party's line. Each party nominates the two separately, by convention or primary.")
NO_ROSTER = "The Open States roster this site uses does not carry the {office}, so today's holder is not shown."


class Unreadable(Exception):
    """A town's ballot laid out in a way this loader does not read: that town is set aside and named, never guessed at."""


# ------------------------------------------------------------------------------------------------ fetching

def fetch(url, accept="*/*", say=print):
    """One request, asked at most twice more on a refusal or a server error; a bot check stops the loader."""
    for attempt in range(3):
        try:
            raw = net.get(url, accept=accept)
        except HTTPError as e:
            if e.code not in (403, 429, 500, 502, 503, 504) or attempt == 2:
                raise
            say(f"      {url.rsplit('/', 1)[-1][:60]}: HTTP {e.code}; asking again in {10 * (attempt + 1)} s")
            time.sleep(10 * (attempt + 1))
            continue
        head = raw[:4000].lower()
        if b"captcha" in head or b"challenge-platform" in head or b"incapsula" in head or b"cf-chl" in head:
            raise SystemExit(f"Connecticut (state races): {url} answered with a bot check; it was not worked around. A person in a "
                             "browser would have to fetch it.")
        return raw


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest() if path and os.path.exists(path) else ""


def mtime(path):
    return dt.datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d") if path and os.path.exists(path) else ""


# ------------------------------------------------------------------------------------------------ the sample ballots

def state_columns(path, town):
    """[{"pages": [n], "cd": d, "sd": d, "ad": d, "cols": {key: [[row, party, name]]}}] for a town's ballot, identical
    faces merged. Only the seven state offices' cells and the party names are read."""
    pdf = PDF(open(path, "rb").read())
    found = []
    for n, (page, res) in enumerate(pdf.pages(), start=1):
        ws = CT.words(page_runs(pdf, page, res))
        lines = CT.text_lines(ws)
        top_row = next((y for y, t in lines if len(t.split()) >= 2 and t.split() == [str(k) for k in range(1, len(t.split()) + 1)]), None)
        if top_row is None:
            continue                                  # not a ballot face (instructions, a blank back)
        where = f"{town}'s ballot, page {n}"
        face = {"pages": [n]}
        for key, rx, words_, top in HEADS:
            got = {int(m.group(1)) for _y, t in lines for m in [rx.search(t)] if m}
            if len(got) != 1 or not 1 <= min(got) <= top:
                raise Unreadable(f"{where} does not name one {words_} district ({sorted(got)})")
            face[key] = min(got)
        labels = [(int(m.group(1)), m.group(2), w) for w in ws for m in [CT.LABEL.match(w["t"])] if m and w["y"] < top_row - 10]
        cols, rows = {}, {}
        for c, r, w in labels:
            cols.setdefault(c, []).append(w["x0"])
            rows.setdefault(r, []).append(w["y"])
        if sorted(cols) != list(range(1, len(cols) + 1)) or len(cols) < 2:
            raise Unreadable(f"{where}: the office columns are not numbered 1 to N ({sorted(cols)})")
        if any(max(v) - min(v) > 4 for v in cols.values()) or any(max(v) - min(v) > 2 for v in rows.values()):
            raise Unreadable(f"{where}: the cell marks do not line up in columns and rows")
        centre = {c: sum(xs) / len(xs) + 5 for c, xs in cols.items()}
        order = sorted(rows, key=lambda r: -sum(rows[r]) / len(rows[r]))
        if order != sorted(order):
            raise Unreadable(f"{where}: the party rows are not lettered from the top ({order})")
        rowy = {r: sum(v) / len(v) for r, v in rows.items()}
        cs = sorted(centre)
        band = {}
        for i, c in enumerate(cs):
            lo = (centre[cs[i - 1]] + centre[c]) / 2 if i else centre[c] - (centre[cs[1]] - centre[c]) / 2
            hi = (centre[cs[i + 1]] + centre[c]) / 2 if i + 1 < len(cs) else centre[c] + (centre[c] - centre[cs[i - 1]]) / 2
            band[c] = (lo, hi)
        first = rowy[order[0]]
        heads = {c: " ".join(t for _y, t in CT.text_lines([w for w in ws if lo <= w["xc"] < hi and first + 4 < w["y"] < top_row + 4]))
                 for c, (lo, hi) in band.items()}
        mine = {}
        for key, rx, title, _kind in OFFICES:
            hit = [c for c, h in heads.items() if rx.search(h)]
            if len(hit) != 1:
                raise Unreadable(f"{where}: {len(hit)} columns headed {title}")
            mine[key] = hit[0]
        if len(set(mine.values())) != len(mine):
            raise Unreadable(f"{where}: two offices read from one column")
        party_edge = band[1][0] + 1
        filled = {(cc, r) for cc, r, _w in labels}
        got, write_in_row = {key: [] for key in mine}, False
        for k, r in enumerate(order):
            below = rowy[order[k + 1]] + 3 if k + 1 < len(order) else rowy[r] - 60
            party = CT.english(" ".join(t for _y, t in CT.text_lines([w for w in ws if w["x1"] <= party_edge and below < w["y"] <= rowy[r] + 3])))
            if party.startswith("Write-in"):
                write_in_row = True
                break
            for key, c in mine.items():
                lo, hi = band[c]
                cell = [t for _y, t in CT.text_lines([w for w in ws if lo <= w["xc"] < hi and below < w["y"] < rowy[r] - 2])]
                if (c, r) not in filled:
                    if cell:
                        raise Unreadable(f"{where}: words in the {OFFICE[key][0]} column of row {r} with no cell mark")
                    continue
                if not party or not cell:
                    raise Unreadable(f"{where}: cell {c}{r} has no {'party' if not party else 'name'}")
                name = re.sub(r"\s+", " ", " ".join(cell)).strip()
                if name == name.upper():
                    raise Unreadable(f"{where} prints a name in capitals, which this loader does not yet show")
                if re.match(r"(?i)and\b", name) or re.search(r"(?i)\band$", name):
                    raise Unreadable(f"{where}: cell {c}{r} begins or ends with 'and' (a ticket split across columns)")
                if key == "GOV" and not re.search(r"\sand\s", name):
                    raise Unreadable(f"{where}: cell {c}{r} does not print a Governor and a Lieutenant Governor")
                got[key].append([r, party, name])
        if not write_in_row:
            raise Unreadable(f"{where}: no Write-in Votes row found")
        face["cols"] = got
        for f in found:
            if all(f[x] == face[x] for x in ("cd", "sd", "ad", "cols")):
                f["pages"].append(n)
                break
        else:
            found.append(face)
    if not found:
        raise Unreadable(f"no ballot faces read in {town}'s sample ballot")
    return found


def town_links(page):
    """{file name: (town, address, revision)} for every town ballot the Sample Town Ballots page links."""
    links = {}
    for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', page, re.S | re.I):
        href = H.unescape(m.group(1))
        hit = CT.BALLOT_LINK.search(href)
        if hit:
            town = re.sub(r"<[^>]+>|\s+", " ", H.unescape(m.group(2))).strip()
            rev = re.search(r"[?&]rev=([0-9A-Fa-f]+)", href)
            links[hit.group(1).lower()] = (town, urljoin(CT.BALLOT_PAGE, href), rev.group(1) if rev else "")
    return links


def keep_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".part", "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
    os.replace(path + ".part", path)


def keep_listing(local_dir, raw, links):
    """The Sample Town Ballots page as it came: the day, its fingerprint and the towns it links (a page of town names
    and ballot addresses; nothing else is kept from it)."""
    rec = {"url": CT.BALLOT_PAGE, "fetched": dt.date.today().isoformat(), "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw),
           "towns": {f: [town, rev] for f, (town, _url, rev) in sorted(links.items())}}
    keep_json(os.path.join(local_dir, LISTING), rec)
    return rec


def ballots(folder, say, refresh=False, local_dir=None):
    """Every posted town's sample ballot, kept once per revision and read once: ({file: {...}}, index path, listing date)."""
    index_path = os.path.join(folder, INDEX)
    old = json.load(open(index_path, encoding="utf-8")) if os.path.exists(index_path) else {}
    if old and not refresh and time.time() - os.path.getmtime(index_path) < 86400 and all(v.get("reader") == READER for v in old.values()):
        return old, index_path
    raw_page = fetch(CT.BALLOT_PAGE, "text/html", say)
    links = town_links(raw_page.decode("utf-8", "replace"))
    if not links:
        raise SystemExit("Connecticut (state races): the Sample Town Ballots page links no town ballots")
    keep_listing(local_dir or os.path.join(folder, "local"), raw_page, links)
    mine_dir, fed_dir = os.path.join(folder, "sl_ballots"), os.path.join(folder, "ballots")
    os.makedirs(mine_dir, exist_ok=True)
    fed_path = os.path.join(folder, FED_INDEX)
    fed = json.load(open(fed_path, encoding="utf-8")) if os.path.exists(fed_path) else {}

    def read(path, town):
        try:
            return {"faces": state_columns(path, town), "unreadable": None}
        except Unreadable as e:
            return {"faces": [], "unreadable": str(e)}

    index, fetched, copied = {}, 0, 0
    for fname, (town, url, rev) in sorted(links.items()):
        path = os.path.join(mine_dir, fname)
        prev = old.get(fname)
        if prev and prev.get("rev") == rev and os.path.exists(path) and sha(path) == prev.get("sha256"):
            if prev.get("reader") != READER:                  # the reading changed: read the kept file again, nothing downloaded
                prev = dict(prev, reader=READER, **read(path, town))
            index[fname] = prev
            continue
        theirs, their_path = fed.get(fname), os.path.join(fed_dir, fname)
        if theirs and theirs.get("rev") == rev and os.path.exists(their_path) and sha(their_path) == theirs.get("sha256"):
            raw, when = open(their_path, "rb").read(), theirs.get("fetched") or mtime(their_path)
            copied += 1
        else:
            raw, when = fetch(url, "application/pdf", say), dt.date.today().isoformat()
            fetched += 1
            time.sleep(1.0)
        entry = {"town": town, "url": url.split("?")[0], "rev": rev, "sha256": hashlib.sha256(raw).hexdigest(), "fetched": when, "reader": READER}
        if not raw.startswith(b"%PDF"):
            index[fname] = dict(entry, faces=[], unreadable=f"{town}'s sample ballot did not come back as a PDF")
            continue
        with open(path, "wb") as fh:
            fh.write(raw)
        index[fname] = dict(entry, **read(path, town))
    for gone in sorted(set(os.listdir(mine_dir)) - set(links)):
        if gone.lower().endswith(".pdf"):
            os.remove(os.path.join(mine_dir, gone))          # a ballot the Secretary took down: never read again
    json.dump(index, open(index_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    say(f"      sample ballots: {len(index)} of {TOWNS} towns posted; {fetched} downloaded, {copied} copied from the federal loader's cache")
    return index, index_path


# ------------------------------------------------------------------------------------------------ the primaries

def ints(text):
    t = str(text or "").replace(",", "").strip()
    return int(t) if t else 0


def official_contest(c):
    """Every town that voted in the contest has its return marked official, and every precinct is in."""
    m = re.fullmatch(r"(\d+) of (\d+) \(100%\)", c["precincts"])
    return bool(m) and m.group(1) == m.group(2) and bool(c["status"]) and all(s == CT.OFFICIAL for s in c["status"].values())


def office_key(title):
    """('SS', '13') for 'State Senator 13', ('GOV', '') for 'Governor'; (None, None) for an office not read here."""
    t = re.sub(r"\s+", " ", title).strip()
    for rx, key in PRIMARY_OFFICE:
        m = rx.fullmatch(t)
        if m:
            return key, (str(int(m.group(1))) if m.groups() else "")
    return None, None


def primaries(say):
    """The state contests of every 2026 party primary: names, parties, votes, town figures and statuses only."""
    def get(path):
        return json.loads(fetch(CT.CTEMS_DATA + path, "application/json", say).decode("utf-8-sig"))

    out = []
    for e in get("Elections.json"):
        m = PRIMARY_NAME.fullmatch(e.get("Name", "").strip())
        if not m or re.search(r"Presidential|Municipal|Town Committee", m.group(3), re.I):
            continue
        eid = e["ID"]
        version = int(get(f"election/{eid}/Version.json")["Version"])
        base = f"election/{eid}/{version}/"
        look = get(base + "Lookupdata.json")
        el = look["election"]
        if el.get("ET") != "P":
            continue
        party = el["P"]
        offices, skipped = {}, []
        for group in look["officeList"]:
            for oid, o in group.items():
                key, district = office_key(o["NM"])
                if key is None:
                    skipped.append(re.sub(r"\s+", " ", o["NM"]).strip())
                    continue
                if district and str(o.get("D", "")).strip() != district:
                    raise SystemExit(f"Connecticut: the Management System files {o['NM']!r} under district {o.get('D')!r}")
                offices[oid] = (key, district, re.sub(r"\s+", " ", o["NM"]).strip())
        contests = {}
        if offices:
            state = get(base + "stateVotes_Electiondata.json")
            towns = get(base + "townVotes_Electiondata.json")
            status = get(base + "townStatus_Electiondata.json")
            precincts = get(base + "officePrecincts_Electiondata.json")
            parties = {pid: p["NM"] for pid, p in look["partyIds"].items()}
            for oid, (key, district, title) in offices.items():
                cands = {}
                for cell in state.get(oid, []):
                    for cid, v in cell.items():
                        rec = look["candidateIds"][cid]                   # only the printed name and the party are read
                        cands[cid] = {"name": re.sub(r"\s+", " ", rec["NM"]).strip(), "party": parties.get(rec["P"], rec["P"]),
                                      "votes": ints(v["V"]), "share": str(v.get("TO", "")).strip()}
                by_town = {tid: {cid: ints(v["V"]) for cell in offs[oid] for cid, v in cell.items()} for tid, offs in towns.items() if oid in offs}
                contests[oid] = {"key": key, "district": district, "office": title, "candidates": cands, "towns": by_town,
                                 "precincts": precincts.get(oid, ""), "status": {tid: status.get(tid, {}).get("TS", "") for tid in by_town},
                                 "town_names": {tid: look["townIds"].get(tid, tid) for tid in by_town}}
        out.append({"id": eid, "name": e["Name"].strip(), "date": f"2026-{m.group(1)}-{m.group(2)}", "party": party, "version": version,
                    "contests": contests, "skipped": sorted(skipped)})
        time.sleep(1.0)
    if not out:
        raise SystemExit("Connecticut: the Election Management System lists no 2026 party primary")
    say(f"      Election Management System: {len(out)} 2026 primaries read ({sum(len(e['contests']) for e in out)} state contests)")
    return {"fetched": dt.date.today().isoformat(), "elections": out}


def kept_primaries(folder, say, refresh=False):
    path = os.path.join(folder, PRIMS)
    prim = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else None
    age = time.time() - os.path.getmtime(path) if prim else None
    settled = prim and all(official_contest(c) for e in prim["elections"] for c in e["contests"].values())
    if refresh or not prim or age > 30 * 86400 or (not settled and age > 86400):     # returns not yet official are asked for daily
        try:
            prim = primaries(say)
        except (HTTPError, OSError) as e:
            if not prim:
                raise
            say(f"      could not refresh the primaries ({e}); using the copy read earlier")
            return prim, path
        json.dump(prim, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return prim, path


# ------------------------------------------------------------------------------------------------ who holds each seat

def roster(path):
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    legs = [dict(zip(("id", "first", "last", "full", "other", "code", "party", "chamber", "district"), r)) for r in con.execute(
        "SELECT bioguide_id, first_name, last_name, official_full, other_names, party, party_name, chamber, district FROM legislators "
        "WHERE is_current = 1")]
    offs = {r[1]: dict(zip(("id", "office", "full", "first", "last", "code", "party"), r)) for r in con.execute(
        "SELECT bioguide_id, office, official_full, first_name, last_name, party, party_name FROM officials")}
    con.close()
    return legs, offs


def person_fits(name, p):
    """A printed name fits a roster person: same family name and a given name that fits (their roster name or a full
    form the roster keeps)."""
    cand = name_parts(name)
    forms = [(fold(p["first"] or "").split(), " ".join(fold(p["last"] or "").split()))]
    forms += [name_parts(o.strip()) for o in (p.get("other") or "").split(";") if o.strip() and "," not in o and "." not in o]
    return any(f[1] and fits(cand, f) for f in forms)


def names_fit(a, b):
    return person_fits(a, {"first": " ".join(name_parts(b)[0]), "last": name_parts(b)[1]})


def chamber_words(p):
    return f"{'State Senate, Senatorial' if p['chamber'] == 'Senate' else 'House of Representatives, Assembly'} District {p['district']}"


def line_code(lines):
    """The colour of a candidate on several lines: the first major party among them, else the first line's."""
    first = next((p for p in lines if p in MAJOR), lines[0])
    return CT.code(first)


# ------------------------------------------------------------------------------------------------ the local level

def src_ballot(fname):
    return f"ct-sots-2026-sl-ballot-{CT.slug(fname)}"


def and_names(items):
    items = list(items)
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def plural(n, word):
    return f"{n} {word}{'' if n == 1 else 's'}"


def long_date(day):
    d = dt.date.fromisoformat(day) if isinstance(day, str) else day
    return f"{d.strftime('%B')} {d.day}, {d.year}"


def polite(url, accept, say):
    """fetch() for the local level's own sources: None, with the reason said, when the address cannot be had. A refusal
    is asked about at most twice more and a bot check is never worked around; the caller records a gap instead."""
    try:
        raw = fetch(url, accept, say)
    except SystemExit as e:
        say(f"      {e}")
        return None
    except (HTTPError, OSError) as e:
        say(f"      {url}: {e}")
        return None
    time.sleep(1.0)
    return raw


def census_towns(local_dir, say):
    """({county code: name}, {town: {"code", "county", "name"}}, the file's record) from the Census Bureau's 2020 county
    subdivision codes for Connecticut: its 169 towns, each with a code of its own, in the eight counties. The file is
    fetched once and kept whole (it holds codes and place names, no personal data). None when it cannot be fetched."""
    path = os.path.join(local_dir, COUSUB_FILE)
    if not os.path.exists(path) or not os.path.getsize(path):
        try:
            net.download(COUSUB_URL, path, 36500, tries=3, say=say)
        except (HTTPError, OSError) as e:
            say(f"      the Census Bureau's county subdivision codes could not be fetched ({e})")
            return None
    lines = open(path, encoding="utf-8").read().splitlines()
    if not lines or lines[0].strip() != COUSUB_HEAD:
        raise SystemExit(f"Connecticut (local): {COUSUB_FILE}, line 1: the columns are not the ones this loader reads")
    counties, towns = {}, {}
    for n, line in enumerate(lines[1:], start=2):
        if not line.strip():
            continue
        cells = line.split("|")
        if len(cells) != 9 or cells[1] != FIPS or not re.fullmatch(r"\d{3}", cells[2]) or not re.fullmatch(r"\d{5}", cells[4]):
            raise SystemExit(f"Connecticut (local): {COUSUB_FILE}, line {n}: not a Connecticut county subdivision row")
        _st, _fp, county, cname, code_, _ns, name, _cls, func = cells
        if not re.fullmatch(r".+ County", cname) or counties.setdefault(county, cname) != cname:
            raise SystemExit(f"Connecticut (local): {COUSUB_FILE}, line {n}: the county is not named as a county, or is named two ways")
        if code_ == "00000" or func == "F":
            continue                                  # "County subdivisions not defined": water, not a town
        m = re.fullmatch(r"(.+) town", name)
        if not m or m.group(1) in towns:
            raise SystemExit(f"Connecticut (local): {COUSUB_FILE}, line {n}: not a town named once")
        towns[m.group(1)] = {"code": code_, "county": county, "name": name}
    if len(towns) != TOWNS or len(counties) != COUNTIES or len({t["code"] for t in towns.values()}) != TOWNS:
        raise SystemExit(f"Connecticut (local): {COUSUB_FILE} does not list {TOWNS} towns, each with a code of its own, in {COUNTIES} counties")
    return counties, towns, {"sha256": sha(path), "fetched": mtime(path)}


def read_45a2(page):
    """{"1": ["Hartford"], ... "54": ["Greenwich"]} from the General Assembly's page of chapter 801: the numbered list
    of section 45a-2, "(28) The towns of Chaplin, Colchester, Hampton, Lebanon, Scotland and Windham." The history
    notes under the list are not read."""
    m = re.search(r'<span class="catchln" id="sec_45a-2">(.*?)<span class="catchln" id="sec_', page, re.S)
    if not m:
        raise ValueError("section 45a-2 is not on the chapter's page")
    text = H.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", m.group(1))))
    if "fifty-four probate districts" not in text:
        raise ValueError("section 45a-2 no longer says there are fifty-four probate districts")
    out = {}
    for n, names in re.findall(r"\((\d{1,2})\) The towns? of ([A-Za-z ,]+?)\.", text):
        if int(n) != len(out) + 1:
            break                                     # the list is over
        out[n] = [t.strip() for t in re.split(r",\s*|\s+and\s+", names) if t.strip()]
    return out


def districts_fit(districts, towns):
    """Why a reading of section 45a-2 cannot be used, or None: 54 districts numbered in order, whose towns are the
    Census Bureau's 169, each named once."""
    if list(districts) != [str(n) for n in range(1, PROBATE_DISTRICTS + 1)]:
        return f"it lists {len(districts)} districts, not {PROBATE_DISTRICTS} numbered in order"
    listed = [t for ts in districts.values() for t in ts]
    if len(listed) != len(set(listed)) or set(listed) != set(towns):
        return f"its towns are not the Census Bureau's {TOWNS}, each named once"
    return None


def probate_districts(local_dir, towns, say, problems, refresh=False):
    """The towns of each probate district (C.G.S. 45a-2), kept as JSON with the day and the fingerprint of the page as it
    came, and asked for again after a month. A page that no longer reads as 54 districts of the 169 towns is not used:
    the copy on disk stands, or with none the answer is None and no judge of probate contest is filed."""
    path = os.path.join(local_dir, PROBATE_KEPT)
    kept = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else None
    if kept and districts_fit(kept.get("districts") or {}, towns):
        kept = None
    if refresh or not kept or (dt.date.today() - dt.date.fromisoformat(kept["fetched"])).days >= STATUTE_MAX_AGE_DAYS:
        raw = polite(PROBATE_URL, "text/html", say)
        if raw is not None:
            try:
                districts = read_45a2(raw.decode("utf-8", "replace"))
                why = districts_fit(districts, towns)
                if why:
                    raise ValueError(f"section 45a-2 as read today: {why}")
            except ValueError as e:
                problems.append(f"{e}; " + (f"the copy read on {kept['fetched']} is used" if kept else "no judge of probate contest is filed"))
            else:
                kept = {"url": PROBATE_URL + "#sec_45a-2", "fetched": dt.date.today().isoformat(), "sha256": hashlib.sha256(raw).hexdigest(),
                        "bytes": len(raw), "districts": districts}
                keep_json(path, kept)
        elif kept:
            say(f"      the General Statutes' page could not be fetched; using the probate districts read on {kept['fetched']}")
    return kept


def grid(ws, lines, where):
    """The party-row grid of one ballot face, found the way state_columns finds it: the row of column numbers, the cell
    marks ("9A"), a band across the page for each column, the party rows from the top, and each column's heading. None
    when the page is not a ballot face."""
    top = next(((y, t.split()) for y, t in lines if len(t.split()) >= 2 and t.split() == [str(k) for k in range(1, len(t.split()) + 1)]), None)
    if top is None:
        return None
    top_row = top[0]
    labels = [(int(m.group(1)), m.group(2), w) for w in ws for m in [CT.LABEL.match(w["t"])] if m and w["y"] < top_row - 10]
    cols, rows = {}, {}
    for c, r, w in labels:
        cols.setdefault(c, []).append(w["x0"])
        rows.setdefault(r, []).append(w["y"])
    if sorted(cols) != list(range(1, len(cols) + 1)) or len(cols) < 2:
        raise Unreadable(f"{where}: the office columns are not numbered 1 to N ({sorted(cols)})")
    if len(top[1]) > len(cols):                       # a numbered column with no cell mark in it would be passed over unseen
        raise Unreadable(f"{where}: the columns are numbered to {len(top[1])} along the top and the cell marks run to {len(cols)}")
    if any(max(v) - min(v) > 4 for v in cols.values()) or any(max(v) - min(v) > 2 for v in rows.values()):
        raise Unreadable(f"{where}: the cell marks do not line up in columns and rows")
    centre = {c: sum(xs) / len(xs) + 5 for c, xs in cols.items()}
    order = sorted(rows, key=lambda r: -sum(rows[r]) / len(rows[r]))
    if order != sorted(order):
        raise Unreadable(f"{where}: the party rows are not lettered from the top ({order})")
    rowy = {r: sum(v) / len(v) for r, v in rows.items()}
    cs = sorted(centre)
    band = {}
    for i, c in enumerate(cs):
        lo = (centre[cs[i - 1]] + centre[c]) / 2 if i else centre[c] - (centre[cs[1]] - centre[c]) / 2
        hi = (centre[cs[i + 1]] + centre[c]) / 2 if i + 1 < len(cs) else centre[c] + (centre[c] - centre[cs[i - 1]]) / 2
        band[c] = (lo, hi)
    first = rowy[order[0]]
    heads = {c: " ".join(t for _y, t in CT.text_lines([w for w in ws if lo <= w["xc"] < hi and first + 4 < w["y"] < top_row + 4]))
             for c, (lo, hi) in band.items()}
    return {"top": top_row, "band": band, "order": order, "rowy": rowy, "heads": heads, "edge": band[1][0] + 1,
            "filled": {(c, r) for c, r, _w in labels}}


def local_columns(path, town, town_names):
    """[{"pages": [n], "probate": the district the page is headed with or None, "cols": [...]}] for a town's ballot,
    identical faces merged. A column is one the state and federal loaders do not read: {"col", "kind": "probate" or
    "registrar", "cells": [[row, party, name]], "write_in": whether the write-in row has a mark in it}, or, for any other
    heading, {"col", "kind": "other", "head": its words when they are plainly an office's, "cells": how many are
    filled}. Only headings, party names and the names printed in those cells are read; every face must be headed with
    the town's own name. A face that says the ballot has more than one sheet carries "sheets"; a page with cell marks
    and no row of column numbers from 1 (the grid going on, on a back or a second sheet) is not read: its columns are
    counted as "other" on a face of their own, marked "more"."""
    pdf = PDF(open(path, "rb").read())
    found, more = [], {}
    for n, (page, res) in enumerate(pdf.pages(), start=1):
        ws = CT.words(page_runs(pdf, page, res))
        lines = CT.text_lines(ws)
        where = f"{town}'s ballot, page {n}"
        g = grid(ws, lines, where)
        if g is None:                                 # not a ballot face (instructions, a blank back), unless the grid goes on here
            marks = [m for w in ws for m in [CT.LABEL.match(w["t"])] if m]
            if len(marks) >= 4 and len({m.group(2) for m in marks}) >= 2:
                for m in marks:
                    more.setdefault(int(m.group(1)), set()).add(m.group(2))
            continue
        above = " ".join(t for y, t in lines if y > g["top"] + 2)
        for pattern in (r"(?<![A-Za-z]){}, Connecticut\b", r"(?i:\b(?:Town|City) of ){}\b"):
            named = [t for t in town_names if re.search(pattern.format(re.escape(t)), above)]
            named = [t for t in named if not any(t != u and t in u for u in named)]      # "Canaan" inside "North Canaan"
            if named:
                break
        if named != [town]:
            raise Unreadable(f"{where} is not headed with the town's name and no other town's")
        got = {int(x) for x in PROBATE_HEAD.findall(above)}
        if len(got) > 1 or any(not 1 <= d <= PROBATE_DISTRICTS for d in got):
            raise Unreadable(f"{where} is not headed with one probate district ({sorted(got)})")
        order, rowy, filled = g["order"], g["rowy"], g["filled"]
        parties, write_in = [], None
        for k, r in enumerate(order):
            below = rowy[order[k + 1]] + 3 if k + 1 < len(order) else rowy[r] - 60
            party = CT.english(" ".join(t for _y, t in CT.text_lines([w for w in ws if w["x1"] <= g["edge"] and below < w["y"] <= rowy[r] + 3])))
            if party.startswith("Write-in"):
                write_in = r
                break
            parties.append((r, party, below))
        if write_in is None:
            raise Unreadable(f"{where}: no Write-in Votes row found")
        face = {"pages": [n], "probate": min(got) if got else None, "cols": []}
        sheets = max((int(x) for _y, t in lines for x in SHEETS.findall(t)), default=1)
        if sheets > 1:
            face["sheets"] = sheets
        for c in sorted(g["band"]):
            head = re.sub(r"\s+", " ", g["heads"][c]).strip()
            words_ = re.sub(rf"^{c}\b\s*", "", head)
            m = VOTE_FOR.search(words_)
            title = (words_[:m.start()] if m else words_).strip()
            if (ELSEWHERE.search(title) or any(rx.search(title) for _key, rx, _title, _kind in OFFICES)) and not A_TOWNS_OWN.search(title):
                continue                              # a federal or a state office: the loaders for those read it
            kind = "other" if NOT_A_FULL_TERM.search(words_) else next((k for k, rx in LOCAL_HEADS if rx.search(title)), "other")
            if kind == "other":
                face["cols"].append({"col": c, "kind": kind, "head": title if PLAIN_WORDS.fullmatch(title) and not contact_like(title, True) else "",
                                     "cells": sum(1 for r, _p, _b in parties if (c, r) in filled)})
                continue
            seats = m.group(1) if m else "one"           # by law one judge to a district, and one vote for registrar (C.G.S. 45a-18, 9-190)
            if (int(seats) if seats.isdigit() else NUMBER_WORDS.get(seats.lower())) != 1:
                raise Unreadable(f"{where}: the {LOCAL_TITLE[kind]} column is not headed Vote for One")
            lo, hi = g["band"][c]
            cells = []
            for r, party, below in parties:
                cell = [t for _y, t in CT.text_lines([w for w in ws if lo <= w["xc"] < hi and below < w["y"] < rowy[r] - 2])]
                if (c, r) not in filled:
                    if cell:
                        raise Unreadable(f"{where}: words in the {LOCAL_TITLE[kind]} column of row {r} with no cell mark")
                    continue
                if not party or not cell:
                    raise Unreadable(f"{where}: cell {c}{r} has no {'party' if not party else 'name'}")
                name = re.sub(r"\s+", " ", " ".join(cell)).strip()
                if name == name.upper():
                    raise Unreadable(f"{where} prints a name in capitals, which this loader does not yet show")
                if not fold(name) or contact_like(name, True) or BUILDER_STREET.search(name) or contact_like(party, True):
                    raise Unreadable(f"{where}: cell {c}{r} does not read as a name on a party's line (it is not kept)")
                cells.append([r, party, name])
            face["cols"].append({"col": c, "kind": kind, "cells": cells, "write_in": (c, write_in) in filled})
        for f in found:
            if (f["probate"], f["cols"], f.get("sheets")) == (face["probate"], face["cols"], face.get("sheets")):
                f["pages"].append(n)
                break
        else:
            found.append(face)
    if not found:
        raise Unreadable(f"no ballot faces read in {town}'s sample ballot")
    if more:                                          # every row but the last (the write-in row) of each column that goes on
        last = max(r for rows in more.values() for r in rows)
        found.append({"pages": [], "probate": None, "more": True,
                      "cols": [{"col": c, "kind": "other", "head": "", "cells": len(rows - {last})} for c, rows in sorted(more.items())]})
    return found


def town_of(link_text, fname, town_names):
    """The town a posted ballot belongs to: the name the page links it under, or, when that is not one of the towns'
    names (a note added to the link), the one town the file is named for ("deep-river_sample.pdf"). The ballot's own
    heading must still name that town on every face."""
    town = " ".join(link_text.split())
    if town in town_names:
        return town
    named = [t for t in town_names if re.sub(r"[^a-z]+", "-", t.lower()).strip("-") == CT.slug(fname)]
    return named[0] if len(named) == 1 else town


def local_read(folder, index, local_dir, town_names, say):
    """What every posted ballot prints in its local columns, read once per file: a ballot is read again only when its
    fingerprint or the reader changes (or it could not be read before). Kept as JSON: headings, parties and names."""
    path = os.path.join(local_dir, LOCAL_READ)
    old = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}
    out, fresh = {}, 0
    for fname, rec in sorted(index.items()):
        town = town_of(rec["town"], fname, town_names)
        prev = old.get(fname)
        if prev and not prev.get("unreadable") and (prev.get("sha256"), prev.get("reader"), prev.get("town")) == (rec["sha256"], LOCAL_READER, town):
            out[fname] = prev
            continue
        entry = {"town": town, "sha256": rec["sha256"], "reader": LOCAL_READER, "faces": [], "unreadable": None}
        pdf_path = os.path.join(folder, "sl_ballots", fname)
        if town not in town_names:
            entry["unreadable"] = f"the ballot posted as {CT.slug(fname)} is not under one of the {TOWNS} towns' names"
        elif not os.path.exists(pdf_path) or sha(pdf_path) != rec["sha256"]:
            entry["unreadable"] = f"{town}'s sample ballot is not on disk as it was fetched"
        else:
            fresh += 1
            try:
                entry["faces"] = local_columns(pdf_path, town, town_names)
            except Unreadable as e:
                entry["unreadable"] = str(e)
            except Exception as e:  # noqa: BLE001  a file the kit's reader cannot take apart: set aside and named, like any other
                entry["unreadable"] = f"{town}'s sample ballot could not be read as text ({type(e).__name__})"
        out[fname] = entry
    if out != old:
        keep_json(path, out)
    if fresh:
        say(f"      local columns: {plural(fresh, 'town ballot')} read, {len(out) - fresh} kept from an earlier run")
    return out


def listing_record(local_dir, say):
    """The Sample Town Ballots page's own record: ballots() keeps it whenever it fetches the page. When the ballots on
    disk were read before that record was kept, the page is asked for once, for its fingerprint and its links."""
    path = os.path.join(local_dir, LISTING)
    if os.path.exists(path):
        return json.load(open(path, encoding="utf-8"))
    raw = polite(CT.BALLOT_PAGE, "text/html", say)
    links = town_links(raw.decode("utf-8", "replace")) if raw is not None else {}
    return keep_listing(local_dir, raw, links) if links else None


def folded(lines):
    return [(p, " ".join(fold(n).split())) for p, n in lines]


def people_of(lines, where, report=None):
    """A column's party lines as candidates, in the order of their first rows: [{"name", "lines": [party, ...]}]. A
    candidate nominated by several parties is one person on several lines, as for the state offices. Two lines with
    the same letters and other punctuation ("Fred DeCaro III", "Fred DeCaro, III") are one person, kept as the first
    line prints the name; the run's output says so."""
    people, order, on_line = {}, [], set()
    for p, n in lines:
        k = " ".join(fold(n).split())
        if k not in people:
            people[k] = {"name": n, "lines": []}
            order.append(k)
        elif people[k]["name"] != n and report is not None:
            report.append(f"{where}: the {p} line prints {n!r} where the {people[k]['lines'][0]} line prints {people[k]['name']!r} (one candidate, kept as "
                          "the first line prints it)")
        if p in on_line:
            raise Unreadable(f"{where}: the {p} line is printed twice")
        on_line.add(p)
        people[k]["lines"].append(p)
    return [people[k] for k in order]


def town_reading(faces, town):
    """A town's local columns, which every face of its ballot must print alike: {"probate_no": the district it is
    headed with or None, "probate" and "registrar": [[party, name]] or None when the column is not printed, "write_in":
    {kind: whether the write-in row is marked}, "other": [(heading words, columns)], "sheets": how many sheets the
    ballot says it has}."""
    nos = {f["probate"] for f in faces if f["probate"] is not None}
    if len(nos) > 1:
        raise Unreadable(f"{town}'s ballot is headed with more than one probate district ({sorted(nos)})")
    out = {"probate_no": min(nos) if nos else None, "write_in": {}, "sheets": max((f.get("sheets", 1) for f in faces), default=1)}
    for kind, title in LOCAL_TITLE.items():
        seen, marks = [], []
        for f in faces:
            if f.get("more"):
                continue                              # a page where the grid goes on: counted below, not read
            cols = [c for c in f["cols"] if c["kind"] == kind]
            if len(cols) > 1:
                raise Unreadable(f"{town}'s ballot, pages {f['pages']}: {len(cols)} columns headed {title}")
            got = [[p, n] for _r, p, n in cols[0]["cells"]] if cols else None
            if got not in seen:
                seen.append(got)
            marks.append(bool(cols and cols[0]["write_in"]))
        if len(seen) != 1:
            raise Unreadable(f"{town}'s ballot does not print the same {title} column on every page")
        out[kind], out["write_in"][kind] = seen[0], all(marks)
        if seen[0]:
            people_of(seen[0], f"{town}'s ballot, {title}")
    other = {}
    for f in faces:
        for c in f["cols"]:
            if c["kind"] == "other":
                other.setdefault(c["head"], set()).add(c["col"])
    out["other"] = sorted((h, len(cs)) for h, cs in other.items())
    return out


def cand_rows(rid, people, source_id):
    """sl_candidates rows for a local contest: the name as printed, every party line held, the ballot's own order, and
    nothing else (no incumbent mark, no link to any other record)."""
    out = []
    for k, x in enumerate(people, start=1):
        held = x["lines"]
        note = f"On the ballot on {len(held)} party lines: {', '.join(held)}." if len(held) > 1 else None
        out.append([rid, "general", GENERAL, x["name"], ", ".join(held), line_code(held), k, 0, 0, None, None, None, None, source_id, note])
    return out


def no_name(write_in):
    return "The ballot prints no candidate's name for this office" + (", only the write-in line." if write_in else ".")


def local_level(folder, index, listed_on, local_dir, say, refresh=False):
    """Connecticut's local contests on the state election ballot, from the sample ballots the state races are read from:
    a Judge of Probate race for each of the 54 probate districts and a Registrar of Voters race for each posted town
    that prints one. Returns the rows for sl_races, sl_candidates, sl_places, sl_gaps and sl_notes, the sources of its
    own, what each ballot's source row should say of its local columns, and the lines for the run's output."""
    os.makedirs(local_dir, exist_ok=True)
    races, cands, places, gaps, sources, problems, report = [], [], {}, [], [], [], []
    out = {"races": races, "cands": cands, "places": places, "gaps": gaps, "notes": [], "sources": sources, "ballots": {}, "problems": problems,
           "report": report, "counts": {}}
    n_posted = len(index)
    posted_words = (f"all {TOWNS} towns' ballots were posted" if n_posted >= TOWNS else f"{n_posted} of the {TOWNS} towns' ballots were posted") \
        + f" when the list was read on {long_date(listed_on)}"
    census = census_towns(local_dir, say)
    if census is None:
        gaps.append((STATE, "state", STATE, "Connecticut", "judge of probate and registrar of voters contests",
                     "These contests are filed under towns and counties as the Census Bureau lists them, and that list could not be fetched on this "
                     "run, so no local contest was loaded.", COUSUB_URL))
        out["notes"] = [(STATE, "local_calendar", CALENDAR, CALENDAR_SOURCE, ELECTIONS_URL),
                        (STATE, "local_coverage", "No judge of probate or registrar of voters contest is loaded for Connecticut yet: the list of towns "
                         "they are filed under could not be read on this run.", "U.S. Census Bureau, 2020 county subdivision codes", COUSUB_URL)]
        return out
    counties, towns, census_rec = census
    for code_, cname in sorted(counties.items()):
        places[("county", FIPS + code_)] = ("county", FIPS + code_, cname, json.dumps([FIPS + code_]), SRC_CENSUS)

    def town_place(town):
        t = towns[town]
        pid = f"{STATE}-M-{t['code']}"
        places[("mcd", pid)] = ("mcd", pid, t["name"], json.dumps([FIPS + t["county"]]), SRC_CENSUS)
        return pid, t

    def town_gap(town, what, reason, url):
        pid, t = town_place(town)
        gaps.append((STATE, "place", pid, t["name"], what, reason, url))

    probate = probate_districts(local_dir, towns, say, problems, refresh)
    district_of = {t: int(n) for n, ts in probate["districts"].items() for t in ts} if probate else {}
    reading = local_read(folder, index, local_dir, sorted(towns), say)
    listing = listing_record(local_dir, say)

    # ---- each posted town's local columns, or why its ballot is set aside
    read, aside, twice = {}, [], set()
    for fname, rec in sorted(reading.items()):
        town, url = rec["town"], index[fname]["url"]
        if town not in towns:
            aside.append(f"the ballot posted as {CT.slug(fname)} is not under one of the {TOWNS} towns' names")
            gaps.append((STATE, "state", STATE, "Connecticut", f"local contests on the ballot posted as {CT.slug(fname)}",
                         "The Secretary of the State's page links this ballot under a name that is not one of the 169 towns as the Census Bureau "
                         "writes them, so its contests could not be filed under a town.", url))
            out["ballots"][fname] = {"read_for": [], "words": ["Not read for the local offices: the page links it under a name that is not a town's."]}
            continue
        try:
            if rec["unreadable"]:
                raise Unreadable(rec["unreadable"])
            cols = town_reading(rec["faces"], town)
            if probate and cols["probate_no"] not in (None, district_of[town]):
                raise Unreadable(f"{town}'s ballot is headed Probate District {cols['probate_no']}; section 45a-2 puts the town in district {district_of[town]}")
        except Unreadable as e:
            aside.append(str(e))
            town_gap(town, "judge of probate and registrar of voters candidates",
                     "The Secretary of the State has posted this town's sample ballot, but it is laid out in a way this loader does not read yet, so "
                     "nothing was taken from it rather than guess.", url)
            out["ballots"][fname] = {"read_for": [], "words": ["Set aside for the local offices: it is laid out in a way the loader does not read."]}
            continue
        out["ballots"][fname] = {"read_for": [], "words": []}
        if town in twice:
            out["ballots"][fname]["words"].append("Not read for the local offices: two files are posted for the town and they differ.")
        elif town not in read:
            read[town] = (fname, cols)
        elif read[town][1] == cols:                   # a second file for the town that prints the same local columns
            out["ballots"][fname]["words"].append("Its local columns are the same as on the town's other posted file, which is the one read.")
        else:
            first = read.pop(town)[0]
            twice.add(town)
            aside.append(f"two files are posted for {town} and their local columns differ")
            town_gap(town, "judge of probate and registrar of voters candidates",
                     "The Secretary of the State's page links two sample ballot files for this town, and they do not print the same local columns, so "
                     "nothing was taken from either rather than guess.", url)
            for f2 in (first, fname):
                out["ballots"][f2] = {"read_for": [], "words": ["Not read for the local offices: two files are posted for the town and they differ."]}

    # ---- Judge of Probate: one race per district, the first posted town's column checked against the others'
    by_district = {}
    for town, (fname, cols) in sorted(read.items(), key=lambda kv: kv[1][0]):
        if cols["probate"] is None:
            problems.append(f"{town}'s ballot prints no Judge of Probate column")
            town_gap(town, "judge of probate candidates",
                     "Every probate district elects its judge this year, but this town's sample ballot prints no column for the office, so the "
                     "office could not be read there or checked against the district's other towns.", index[fname]["url"])
        elif probate:
            by_district.setdefault(district_of[town], []).append((fname, town, cols["probate"], cols["write_in"]["probate"]))
    with_names, cells = 0, {"source": 0, "check": 0, "unused": 0}      # the filled cells read, by what became of them
    posted_towns = {rec["town"] for rec in reading.values()}
    stuck = 0                                         # districts with a posted ballot and still no names
    for n in range(1, PROBATE_DISTRICTS + 1) if probate else ():
        members = probate["districts"][str(n)]
        cids = sorted({FIPS + towns[t]["county"] for t in members})
        rid, jid, jur = f"2026-{STATE}-PD{n}", f"{STATE}-PD{n}", f"Probate District {n}"
        places[("judicial", jid)] = ("judicial", jid, jur, json.dumps(cids), SRC_PROBATE)
        note = [f"{jur} covers the town{'s' if len(members) > 1 else ''} of {and_names(members)} (C.G.S. 45a-2)."]
        got = by_district.get(n, [])
        unused = [t for t in members if t in posted_towns]
        if not got and unused:
            stuck += 1
            note.append(f"The sample ballot{'s' if len(unused) > 1 else ''} of {and_names(unused)} {'have' if len(unused) > 1 else 'has'} been posted but "
                        "could not be read for this office, so no candidate is shown yet.")
        elif not got:
            note.append(f"No town in this district has had its November ballot posted by the Secretary of the State yet ({n_posted} of {TOWNS} "
                        f"towns posted when the list was read, {listed_on}); the candidates appear once one is.")
        else:
            (fname, town, lines, marked), others = got[0], got[1:]
            differ = [t2 for _f2, t2, l2, _m2 in others if folded(l2) != folded(lines)]
            if differ:
                names = and_names([town] + differ)
                note.append(f"The sample ballots of {names} do not print the same names for this office, so no candidate is shown until they agree.")
                gaps.append((STATE, "race", rid, jur, "judge of probate candidates",
                             f"Every town of a probate district votes on the same candidates for its judge, but the posted sample ballots of {names} "
                             "do not print the same names, so none is shown rather than guess which is right.", index[fname]["url"]))
                problems.append(f"{rid}: the ballots of {names} do not print the same Judge of Probate lines")
                stuck += 1
                cells["unused"] += sum(len(l2) for _f2, _t2, l2, _m2 in got)
                for f2, _t2, _l2, _m2 in got:
                    out["ballots"][f2]["words"].append(f"Its Judge of Probate column does not agree with the other posted ballots of {jur}, so no "
                                                       "candidate is taken from it.")
            else:
                people = people_of(lines, rid, report)
                with_names += 1
                cells["source"] += len(lines)
                cells["check"] += sum(len(l2) for _f2, _t2, l2, _m2 in others)
                cands.extend(cand_rows(rid, people, src_ballot(fname)))
                if not people:
                    note.append(no_name(marked))
                spell = {}
                for _f2, t2, l2, _m2 in others:
                    for (_p1, n1), (_p2, n2) in zip(lines, l2):
                        if n1 != n2:                      # the same letters, other punctuation
                            spell.setdefault((n1, n2), []).append(t2)
                for (n1, n2), ts in sorted(spell.items()):
                    report.append(f"{rid}: {and_names(ts)} print{'s' if len(ts) == 1 else ''} {n2!r} where {town} prints {n1!r} (kept as {town} prints it)")
                mine = out["ballots"][fname]
                mine["read_for"].append(f"Judge of Probate ({jur})")
                mine["words"].append(f"Its Judge of Probate column agrees with the ballot{'s' if len(others) > 1 else ''} of "
                                     f"{and_names([t2 for _f2, t2, _l2, _m2 in others])}." if others else
                                     f"No other town of {jur} has a ballot posted yet to check its Judge of Probate column against.")
                if spell:
                    mine["words"].append("Only the punctuation differs ("
                                         + "; ".join(f"{and_names(ts)} print{'s' if len(ts) == 1 else ''} {n2}" for (_n1, n2), ts in sorted(spell.items()))
                                         + "); names are kept as this town prints them.")
                for f2, _t2, _l2, _m2 in others:
                    out["ballots"][f2]["words"].append(f"Its Judge of Probate column was read as a check on {jur}, whose candidates are taken from "
                                                       f"{town}'s ballot.")
        races.append([rid, STATE, "court", "judge_of_probate", "Judge of Probate", jur, jid, json.dumps(cids), str(n), None, 0, 1, None, None, None,
                      GENERAL, " ".join(note)])

    # ---- Registrar of Voters: one race per posted town that prints the column; any other column is named, not read
    no_registrar, empty, other_columns, more_sheets = [], [], 0, []
    for town, (fname, cols) in sorted(read.items()):
        if cols["registrar"] is None:
            no_registrar.append(town)
        else:
            pid, t = town_place(town)
            rid = f"2026-{STATE}-M-{t['code']}-registrar-of-voters"
            people = people_of(cols["registrar"], rid, report)
            cells["source"] += len(cols["registrar"])
            note = [REGISTRAR_NOTE]
            if not people:
                note.append(no_name(cols["write_in"]["registrar"]))
                empty.append(town)
            races.append([rid, STATE, "township", "registrar_of_voters", "Registrar of Voters", t["name"], pid, json.dumps([FIPS + t["county"]]),
                          None, None, 0, 1, None, None, None, GENERAL, " ".join(note)])
            cands.extend(cand_rows(rid, people, src_ballot(fname)))
            out["ballots"][fname]["read_for"].append("Registrar of Voters")
        if cols["other"]:
            k = sum(c for _h, c in cols["other"])
            heads = [h for h, _c in cols["other"] if h]
            other_columns += k
            town_gap(town, "other offices on the town's ballot",
                     f"The town's sample ballot also prints {plural(k, 'more column')}" + (f" (headed {and_names(heads)})" if heads else "")
                     + " besides the state offices, Judge of Probate and Registrar of Voters; this loader does not read "
                     + ("it yet, so that contest is not shown." if k == 1 else "them yet, so those contests are not shown."), index[fname]["url"])
            out["ballots"][fname]["words"].append(f"{plural(k, 'more column')} for other offices {'is' if k == 1 else 'are'} printed and not read.")
        elif cols["sheets"] > 1:
            more_sheets.append(town)
            town_gap(town, "anything on the other sheets of the town's ballot",
                     f"The town's sample ballot says it has {cols['sheets']} sheets, and this loader reads the grid of offices on the first; "
                     "an office printed on another sheet, if there is one, is not shown.", index[fname]["url"])
            out["ballots"][fname]["words"].append(f"The ballot says it has {cols['sheets']} sheets; only the first sheet's grid is read.")

    # ---- what is not here, in the reader's words
    if n_posted < TOWNS:
        gaps.append((STATE, "state", STATE, "Connecticut", "judge of probate and registrar of voters candidates in towns whose ballot is not posted yet",
                     f"The Secretary of the State posts each town's sample ballot as it is approved: {posted_words}. State law has every town's "
                     f"registrars of voters file the sample ballot at least ten days before early voting begins on {EARLY_VOTING.strftime('%B')} "
                     f"{EARLY_VOTING.day}, so the rest are due by {BALLOTS_DUE.strftime('%B')} {BALLOTS_DUE.day} (C.G.S. 9-256 and 9-163aa); a town's "
                     "candidates are loaded once its ballot is posted.", CT.BALLOT_PAGE))
    if not probate:
        gaps.append((STATE, "state", STATE, "Connecticut", "judge of probate contests",
                     "The towns of each probate district are set out in section 45a-2 of the General Statutes, and the General Assembly's page of it "
                     "could not be read on this run, so the contests could not be filed under their districts.", PROBATE_URL))

    prob = [r for r in races if r[3] == "judge_of_probate"]
    reg = [r for r in races if r[3] == "registrar_of_voters"]
    prob_ids, reg_ids = {r[0] for r in prob}, {r[0] for r in reg}
    prob_cands, reg_cands = sum(1 for c in cands if c[0] in prob_ids), sum(1 for c in cands if c[0] in reg_ids)
    cover = [f"Loaded from the Secretary of the State's sample ballots, one per town: {posted_words}."]
    if probate:
        cover.append(f"They give the judge of probate contest of {with_names} of the {PROBATE_DISTRICTS} probate districts ({plural(prob_cands, 'candidate')}; "
                     f"every posted town of a district must print the same names) and the registrar of voters contest of {plural(len(reg), 'town')} "
                     f"({plural(reg_cands, 'candidate')}).")
        waiting = PROBATE_DISTRICTS - with_names - stuck
        if waiting:
            cover.append(f"{'The other ' if not stuck else ''}{plural(waiting, 'probate district')} {'have' if waiting > 1 else 'has'} no town posted yet and "
                         f"{'are' if waiting > 1 else 'is'} listed without candidates until one is.")
        if stuck:
            cover.append(f"{plural(stuck, 'probate district')} {'have' if stuck > 1 else 'has'} a posted ballot that could not be used, and "
                         f"{'are' if stuck > 1 else 'is'} listed without candidates (see the gaps).")
    else:
        cover.append(f"They give the registrar of voters contest of {plural(len(reg), 'town')} ({plural(reg_cands, 'candidate')}); the judge of probate "
                     "contests could not be filed under their districts on this run.")
    if empty:
        cover.append(f"The ballot{'s' if len(empty) > 1 else ''} of {and_names(empty)} print{'' if len(empty) > 1 else 's'} the registrar's office with no "
                     "candidate's name, and the contest is shown with none.")
    if no_registrar:
        cover.append(f"The ballot{'s' if len(no_registrar) > 1 else ''} of {and_names(no_registrar)} print{'' if len(no_registrar) > 1 else 's'} no "
                     "registrar of voters column.")
    if aside:
        cover.append(f"{plural(len(aside), 'posted ballot')} could not be read and {'is' if len(aside) == 1 else 'are'} named among the gaps.")
    cover.append("Not loaded: registered write-in candidates, who are not printed on a ballot; ballot questions; and any other town office a ballot "
                 "prints (" + ("none of the posted ballots prints one" if not other_columns else "named among the gaps") + "). A ballot prints no "
                 "withdrawn candidate, so none can be counted. Towns are filed under Connecticut's eight counties, which have no government but "
                 "still say where a town lies; the Census Bureau's newer planning regions are not used.")
    out["notes"] = [(STATE, "local_calendar", CALENDAR, CALENDAR_SOURCE, ELECTIONS_URL),
                    (STATE, "local_coverage", " ".join(cover),
                     "Connecticut Secretary of the State, November 3, 2026, State Election, Sample Town Ballots; Connecticut General Statutes section "
                     "45a-2 (the towns of each probate district); U.S. Census Bureau, 2020 county subdivision codes (towns and counties)",
                     CT.BALLOT_PAGE)]

    # ---- the local level's own sources (the ballots' rows are written with the state races')
    sources.append((SRC_CENSUS, STATE, "official codes", "U.S. Census Bureau", f"2020 Census county subdivision codes for Connecticut ({COUSUB_FILE})",
                    COUSUB_URL, "", census_rec["fetched"], census_rec["sha256"], TOWNS,
                    "Each town's name, its county subdivision code (the key of the town's place id) and the county it lies in, and the eight "
                    "counties' names and codes: the state, county, code and name columns are read, and the file holds no personal data. "
                    "Connecticut's counties have no government, and the Bureau's current county file (2024) lists nine planning regions in "
                    "their place; the eight counties are kept here to say where a town lies."))
    if probate:
        sources.append((SRC_PROBATE, STATE, "statute", "Connecticut General Assembly",
                        "General Statutes of Connecticut, section 45a-2: Probate districts (chapter 801)", probate["url"], "", probate["fetched"],
                        probate["sha256"], PROBATE_DISTRICTS,
                        f"The {PROBATE_DISTRICTS} probate districts and the towns of each, read from the section's numbered list; the {TOWNS} towns "
                        "it names are the Census Bureau's, each in one district. The fingerprint is of the chapter's page as it came; only the "
                        "district numbers and town names are kept on disk. The statute numbers the districts and gives them no names, so they "
                        "are shown by number."))
    if listing:
        same = {f: v[1] for f, v in listing["towns"].items()} == {f: r["rev"] for f, r in index.items()}
        sources.append((SRC_LISTING, STATE, "official list of sample ballots", AGENCY,
                        "November 3, 2026, State Election, Sample Town Ballots: the towns posted", listing["url"], "", listing["fetched"],
                        listing["sha256"], len(listing["towns"]),
                        f"The page that links each town's sample ballot as it is posted: {len(listing['towns'])} of {TOWNS} towns linked on the day "
                        "of this fingerprint. Only the towns' names and the ballots' addresses are read from it. "
                        + ("They are the ballots read here, at the same revisions." if same else
                           f"The ballots read here are the {n_posted} linked on {long_date(listed_on)}; the page has changed since, and the newly "
                           "posted ballots are read when the list is next refreshed (once a day).")))
        if not same:
            report.append(f"the Sample Town Ballots page links {len(listing['towns'])} towns as of {listing['fetched']}, not the {n_posted} ballots "
                          f"read on {listed_on}; they are read at the next refresh")

    said = set()
    gaps[:] = [g for g in gaps if (g[1], g[2], g[4]) not in said and not said.add((g[1], g[2], g[4]))]      # one row to a (scope, place, matter)

    # ---- the last look before anything is written: nothing that reads like contact details, by the trial check's own
    # test and the page builder's (a text that fails is not printed)
    for table, strict, items in (("sl_races", True, [(r[0], (r[4], r[5], r[8], r[9], r[16])) for r in races]),
                                 ("sl_candidates", True, [(c[0], (c[3], c[4], c[14])) for c in cands]),
                                 ("sl_places", True, [(p[1], (p[2],)) for p in places.values()]),
                                 ("sl_gaps", False, [(g[2], (g[3], g[4], g[5])) for g in gaps]),
                                 ("sl_notes", False, [(x[1], (x[2], x[3])) for x in out["notes"]]),
                                 ("sl_sources", False, [(s[0], (s[3], s[4], s[10])) for s in sources])):
        for ident, texts in items:
            if any(t and (contact_like(t, strict) or (strict and BUILDER_STREET.search(str(t)))) for t in texts):
                raise SystemExit(f"Connecticut (local): a text for {table} ({ident}) reads like contact details; stopping (the text is not printed)")

    # the count check: every filled cell read is on a source ballot (and stored as one party line of one candidate), on a
    # ballot read as a check, or in a district whose ballots disagree; nothing else
    cells["all"] = sum(len(cols[k] or []) for _f, cols in read.values() for k in LOCAL_TITLE)
    cells["stored"] = sum(len(c[4].split(", ")) for c in cands)
    if not probate:
        cells["unused"] += sum(len(cols["probate"] or []) for _f, cols in read.values())
    if cells["all"] != cells["source"] + cells["check"] + cells["unused"] or cells["source"] != cells["stored"]:
        problems.append(f"the cells do not add up: {cells['all']} read, {cells['source']} on source ballots, {cells['check']} on ballots read as checks, "
                        f"{cells['unused']} not used, {cells['stored']} party lines stored")
    out["counts"] = {"posted": n_posted, "read": len(read), "aside": aside, "probate_races": len(prob), "probate_with": with_names,
                     "probate_candidates": prob_cands, "registrar_races": len(reg), "registrar_candidates": reg_cands, "empty": empty,
                     "no_registrar": no_registrar, "other_columns": other_columns, "more_sheets": more_sheets, "cells": cells,
                     "counties": len({c for r in races for c in json.loads(r[7])})}
    return out


# ------------------------------------------------------------------------------------------------ the loader

def load(db_path, say=print, cache=CACHE, roster_db=ROSTER, refresh=False, local_cache=None):
    net.patient_lookups()
    folder = os.path.join(cache, "ct")
    os.makedirs(folder, exist_ok=True)
    local_dir = local_cache or os.path.join(folder, "local")
    index, index_path = ballots(folder, say, refresh, local_dir)
    prim, ppath = kept_primaries(folder, say, refresh)
    legs, offs = roster(roster_db)
    listed_on = mtime(index_path)
    report = []

    # the seats: every one on the ballot, by law and by the roster
    senate = sorted({int(p["district"]) for p in legs if p["chamber"] == "Senate"})
    house = sorted({int(p["district"]) for p in legs if p["chamber"] == "House"})
    if senate != list(range(1, SENATE_SEATS + 1)) or house != list(range(1, HOUSE_SEATS + 1)):
        report.append(f"the roster's seats are not Senate 1-{SENATE_SEATS} and House 1-{HOUSE_SEATS} "
                      f"({len(senate)} Senate, {len(house)} House districts with a sitting member)")

    # ---- the November ballot: each office's party lines, which every face carrying it must print alike
    unreadable = sorted((rec["town"], rec["unreadable"]) for rec in index.values() if rec.get("unreadable"))
    seen = {}
    for fname, rec in sorted(index.items()):
        for face in rec["faces"]:
            for key, lines in face["cols"].items():
                d = "" if key in STATEWIDE else str(face["sd"] if key == "SS" else face["ad"])
                seen.setdefault((key, d), []).append((fname, face["pages"], [(p, n) for _r, p, n in lines]))
    ballot = {}                                                   # (key, district) -> {"src": fname, "pages", "checked", "people"}
    spellings = {}                                                # (key, district) -> ["Coventry, Harwinton print Jennifer S Tooker"]
    for (key, d), got in sorted(seen.items()):
        (fname, pages, lines), others = got[0], got[1:]
        variants = {}
        for f2, p2, l2 in others:
            if [(p, " ".join(fold(n).split())) for p, n in l2] != [(p, " ".join(fold(n).split())) for p, n in lines]:
                raise SystemExit(f"Connecticut: {OFFICE[key][0]}{' ' + d if d else ''}: {index[f2]['town']}'s ballot (pages {p2}) does not "
                                 f"print the same lines as {index[fname]['town']}'s (pages {pages})")
            for (_p, n1), (_p2, n2) in zip(lines, l2):
                if n1 != n2:                              # the same letters, other punctuation ("Jennifer S Tooker")
                    variants.setdefault((n1, n2), set()).add(index[f2]["town"])
        for (n1, n2), towns in sorted(variants.items()):
            report.append(f"{OFFICE[key][0]}{' ' + d if d else ''}: {', '.join(sorted(towns))} print{'s' if len(towns) == 1 else ''} "
                          f"{n2!r} where {index[fname]['town']} prints {n1!r} (kept as {index[fname]['town']} prints it)")
            spellings.setdefault((key, d), []).append(f"{', '.join(sorted(towns))} print{'s' if len(towns) == 1 else ''} {n2}")
        people, order, on_line = {}, [], {}
        for p, n in lines:
            if key == "GOV":
                parts = re.split(r"\s+and\s+", n)
                if len(parts) != 2:
                    raise SystemExit(f"Connecticut: a Governor's box that is not one Governor and one Lieutenant Governor ({n!r})")
                gov, mate = parts[0].strip(), parts[1].strip()
            else:
                gov, mate = n, None
            k = fold(gov)
            if k not in people:
                people[k] = {"name": gov, "mate": mate, "lines": []}
                order.append(k)
            elif people[k]["name"] != gov or people[k]["mate"] != mate:
                raise SystemExit(f"Connecticut: {OFFICE[key][0]}{' ' + d if d else ''}: one candidate printed two ways ({people[k]['name']!r} "
                                 f"with {people[k]['mate']!r}, {gov!r} with {mate!r})")
            if p in people[k]["lines"] or p in on_line:
                raise SystemExit(f"Connecticut: {OFFICE[key][0]}{' ' + d if d else ''}: the {p} line is printed twice")
            people[k]["lines"].append(p)
            on_line[p] = gov
        towns_checked = sorted({index[f2]["town"] for f2, _p, _l in others} - {index[fname]["town"]})
        ballot[(key, d)] = {"src": fname, "pages": pages, "checked": towns_checked, "people": [people[k] for k in order], "on_line": on_line}

    # ---- the races
    races, cands = {}, []

    def race_id(key, d):
        return f"2026-{STATE}-{key}{d}" if key in ("SS", "SH") else f"2026-{STATE}-{key}"

    def holder_of(key, d):
        if key in ("SS", "SH"):
            hs = [p for p in legs if p["chamber"] == ("Senate" if key == "SS" else "House") and str(p["district"]) == d]
            return hs[0] if len(hs) == 1 else None
        return offs.get(ROSTER_OFFICE.get(key, ""))

    def add_race(key, d):
        rid = race_id(key, d)
        if rid in races:
            return rid
        title, kind = OFFICE[key]
        h = holder_of(key, d)
        note = []
        if key in ("SS", "SH"):
            jur, jid, level = (f"Senatorial District {d}" if key == "SS" else f"Assembly District {d}"), f"{STATE}-{d}", "legislature"
            if h is None:
                note.append("The roster shows no sitting member for this seat.")
                report.append(f"{rid}: no single sitting member in the roster")
        else:
            jur, jid, level = "Connecticut", FIPS, "statewide"
            if key == "GOV":
                note.append(GOV_NOTE)
            if key == "LTG":
                note.append("Nominated in a party primary of its own; in November the Lieutenant Governor is elected jointly with the "
                            "Governor, on the tickets listed under 2026-CT-GOV.")
            if h is None and key not in ROSTER_OFFICE:
                note.append(NO_ROSTER.format(office=title))
        if (key, d) not in ballot and key != "LTG":
            note.append(f"No town in this district has had its November ballot posted by the Secretary of the State yet "
                        f"({len(index)} of {TOWNS} towns posted when the list was read, {listed_on}); the candidates appear once one is.")
        races[rid] = [rid, STATE, level, kind, title, jur, jid, None, d or None, None, 0, 1, h["id"] if h else None,
                      h["full"] if h else None, h["party"] if h else None, GENERAL, " ".join(note) or None]
        return rid

    for key in STATEWIDE:
        add_race(key, "")
    for d in range(1, SENATE_SEATS + 1):
        add_race("SS", str(d))
    for d in range(1, HOUSE_SEATS + 1):
        add_race("SH", str(d))
    for (key, d) in ballot:
        if race_id(key, d) not in races:
            raise SystemExit(f"Connecticut: a ballot names {OFFICE[key][0]} {d}, which is not a seat")

    def identify(key, d, name, pcode, pool_names):
        """(incumbent, state_member_id, note) for one printed name; pool_names are the other names in the same election."""
        h = holder_of(key, d)
        if h is not None and person_fits(name, h):
            if sum(1 for n in pool_names if person_fits(n, h)) == 1:
                return 1, h["id"], None
            report.append(f"{race_id(key, d)}: the holder {h['full']} fits more than one name; no incumbent marked")
            return 0, None, None
        pool = [p for p in legs if person_fits(name, p) and p["code"] == pcode]
        if len(pool) == 1 and not (h is not None and pool[0]["id"] == h["id"]):
            return 0, pool[0]["id"], f"Serves today in the {chamber_words(pool[0])}."
        return 0, None, None

    for (key, d), b in sorted(ballot.items(), key=lambda kv: (["GOV", "SOS", "TREAS", "COMP", "AG", "SS", "SH"].index(kv[0][0]), int(kv[0][1] or 0))):
        rid = race_id(key, d)
        names = [x["name"] for x in b["people"]]
        for k, x in enumerate(b["people"], start=1):
            held = x["lines"]
            code = line_code(held)
            major = next((MAJOR[p] for p in held if p in MAJOR), CT.code(held[0]))
            inc, mid, n2 = identify(key, d, x["name"], major, names)
            note = []
            if x["mate"]:
                note.append(f"On one ticket with {x['mate']} for Lieutenant Governor, as the ballot prints it.")
            if len(held) > 1:
                note.append(f"On the ballot on {len(held)} party lines: {', '.join(held)}.")
            if n2:
                note.append(n2)
            cands.append([rid, "general", GENERAL, x["name"], ", ".join(held), code, k, inc, 0, None, None, None, mid, src_ballot(b["src"]),
                          " ".join(note) or None])

    # ---- the primaries: fields of two or more, official votes only
    fields, unofficial, not_on, unopposed, skipped = 0, [], [], 0, set()
    for e in prim["elections"]:
        skipped |= set(e.get("skipped", []))
        party = e["party"]
        pcode = CODES.get(party)
        if not pcode:
            raise SystemExit(f"Connecticut: a primary of a party that is not read ({party!r})")
        mmdd = e["date"][5:].replace("-", "")
        src = f"ct-sots-2026-sl-primary-{pcode.lower()}-{mmdd}"
        e["_src"] = src
        for oid, c in e["contests"].items():
            key, d, cs = c["key"], c["district"], c["candidates"]
            where = f"{c['office']} ({e['name']})"
            for cid, v in cs.items():
                if v["party"] != party:
                    raise SystemExit(f"Connecticut: {v['name']} is filed under {v['party']} in the {party} primary")
                summed = sum(t.get(cid, 0) for t in c["towns"].values())
                if summed != v["votes"]:
                    raise SystemExit(f"Connecticut: {v['name']}, {where}: the towns add up to {summed}, the total is {v['votes']}")
            if {cid for t in c["towns"].values() for cid in t} - set(cs):
                raise SystemExit(f"Connecticut: {where} has town figures for candidates with no total")
            total = sum(v["votes"] for v in cs.values())
            for v in cs.values():
                m = re.fullmatch(r"([\d.]+)%", v.get("share", ""))
                if total and m and abs(float(m.group(1)) - 100 * v["votes"] / total) > 0.01:
                    raise SystemExit(f"Connecticut: {v['name']}, {where}: the file prints {v['share']}, the votes give "
                                     f"{100 * v['votes'] / total:.2f}%")
            if len(cs) < 2:
                unopposed += 1
                continue
            if key in ("SS", "SH") and not 1 <= int(d) <= (SENATE_SEATS if key == "SS" else HOUSE_SEATS):
                raise SystemExit(f"Connecticut: {where} names a district that is not a seat")
            rid = add_race(key, d)
            fields += 1
            if e["date"] != CT.PRIMARY:                    # the 58th Assembly District's Democrats: a special primary on September 1
                day = dt.date.fromisoformat(e["date"])
                extra = f"The {party}'s nomination was decided in a separate primary on {day.strftime('%B')} {day.day}, {day.year}."
                races[rid][16] = " ".join(x for x in (races[rid][16], extra) if x)
            official = official_contest(c)
            if not official:
                unofficial.append(where)
            ranked = sorted(cs.values(), key=lambda v: (-v["votes"], v["name"]))
            if official and ranked[0]["votes"] == ranked[1]["votes"]:
                raise SystemExit(f"Connecticut: {where} is tied at the top")
            b = ballot.get((key, d)) if key != "LTG" else None
            listed = b["on_line"].get(party) if b else None
            names = [v["name"] for v in ranked]
            for v in ranked:
                if official:
                    won = v is ranked[0]
                else:
                    won = None if listed is None else names_fit(v["name"], listed)
                note = []
                if won and b and (listed is None or not names_fit(v["name"], listed)):
                    note.append("Won the primary but is not on the November ballot." if listed is None else
                                f"Won the primary; the November ballot prints {listed} on the {party} line instead.")
                    not_on.append(f"{v['name']} ({rid}, {party})")
                elif won and key != "LTG" and not b:
                    note.append("Won the primary; no November ballot for this district has been posted yet to show the party's line.")
                if not official:
                    note.append("The primary's official returns are not all in, so no votes are shown.")
                major = MAJOR.get(party, CT.code(party))
                inc, mid, n2 = identify(key, d, v["name"], major, names)
                if n2:
                    note.append(n2)
                cands.append([rid, f"primary-{pcode}", e["date"], v["name"], party, CT.code(party), None, inc, 0,
                              v["votes"] if official else None, round(100 * v["votes"] / total, 1) if official and total else None,
                              None if won is None else ("advanced" if won else "lost"), mid, src, " ".join(note) or None])

    seen_keys = set()
    for c in cands:
        k = (c[0], c[1], c[3])
        if k in seen_keys:
            raise SystemExit(f"Connecticut: {c[3]} is listed twice in {c[0]} {c[1]}")
        seen_keys.add(k)

    # ---- the local level: judges of probate and registrars of voters, from the same ballots
    local = local_level(folder, index, listed_on, local_dir, say, refresh)

    # ---- write
    general = [c for c in cands if c[1] == "general"]
    primary_rows = [c for c in cands if c[1] != "general"]
    used = {}
    for (key, d), b in ballot.items():
        used.setdefault(b["src"], []).append((key, d))
    sources = []
    for fname, rec in sorted(index.items()):          # one row per ballot file, whatever was read from it
        keys, loc = used.get(fname, []), local["ballots"].get(fname) or {"read_for": [], "words": []}
        path = os.path.join(folder, "sl_ballots", fname)
        rows_n = sum(1 for c in general + local["cands"] if c[13] == src_ballot(fname))
        words_ = ["Listed on the Secretary of the State's Sample Town Ballots page."]
        if keys:
            state_part = [OFFICE[k][0] for k, _d in keys if k in STATEWIDE]
            seats = [f"{'Senatorial' if k == 'SS' else 'Assembly'} District {d}" for k, d in sorted(keys, key=lambda x: (x[0], int(x[1] or 0))) if d]
            checked = sorted({t for kd in keys for t in ballot[kd]["checked"]})
            variants = [s for kd in keys for s in spellings.get(kd, [])]
            words_.append(f"Read here for: {', '.join(state_part + seats)}.")
            words_.append(f"Checked against the same columns on the ballots of {', '.join(checked)}, which agree." if checked else
                          "No other posted town's ballot carries these districts yet.")
            if variants:
                words_.append(f"Only the punctuation differs on some ({'; '.join(variants)}); names are kept as this town prints them.")
        elif rec["faces"]:
            words_.append("Its columns for the state offices were read as a check on the ballots those races are taken from.")
        else:
            words_.append("Set aside for the state offices: it is laid out in a way the loader does not read.")
        if loc["read_for"]:
            words_.append(f"Read for the local offices: {and_names(loc['read_for'])}.")
        words_ += loc["words"]
        words_.append("The party-row ballot is read by its cell marks, column by office heading; a sample ballot prints names, parties and "
                      "offices only, so it has no contact details to leave out. Registered write-in candidates are not printed on the ballot "
                      "and are not stored.")
        sources.append((src_ballot(fname), STATE, "official sample ballot", AGENCY,
                        f"November 3, 2026, State Election, Sample Town Ballots: {rec['town']}", rec["url"], "", rec.get("fetched") or mtime(path),
                        rec["sha256"], rows_n, " ".join(words_)))
    for e in prim["elections"]:
        if not e["contests"]:
            continue
        n = sum(1 for c in primary_rows if c[13] == e["_src"])
        towns = len({t for c in e["contests"].values() for t in c["towns"]})
        sources.append((e["_src"], STATE, "official results", AGENCY,
                        f"Election Management System public reporting: {e['name']}, state offices", f"{CT.CTEMS}#/home",
                        e["date"], prim["fetched"], sha(ppath), n,
                        f"Data: {CT.CTEMS_DATA}election/{e['id']}/{e['version']}/ (data version {e['version']}). Contests read: "
                        f"{', '.join(sorted(c['office'] for c in e['contests'].values()))}. Each candidate's total (stateVotes) is checked "
                        f"against the sum of the town returns (townVotes, {towns} towns) and against the share the file prints; a total is "
                        f"stored only when every town is marked \"( Official Results )\" and all precincts are in. Only the printed name and "
                        f"party of each candidate record are read (it also carries an address field, never read). Connecticut primary "
                        f"ballots have no write-in line; a contest with one candidate is not stored as a field. The SHA-256 is of the "
                        f"loader's own JSON of the figures read."))
    sources.append((SRC_ROSTER, STATE, "roster", "Open States people project (CC0), as loaded into state_ct.sqlite",
                    "Sitting legislators and statewide officials", "https://github.com/openstates/people", "", mtime(roster_db), sha(roster_db),
                    len(legs) + len(offs),
                    "Who holds each seat today, by chamber and district; the roster carries the Governor, Lieutenant Governor, Secretary of "
                    "the State and Attorney General, not the Treasurer or the Comptroller. Only ids, names, parties, chambers, districts "
                    "and offices are read. Also the source of the district places (36 Senatorial, 151 Assembly)."))
    sources += local["sources"]
    places = [("senate", f"{STATE}-{d}", f"Senatorial District {d}", None, SRC_ROSTER) for d in range(1, SENATE_SEATS + 1)] + \
             [("house", f"{STATE}-{d}", f"Assembly District {d}", None, SRC_ROSTER) for d in range(1, HOUSE_SEATS + 1)] + \
             list(local["places"].values())
    clash = sorted({r[0] for r in local["races"]} & set(races))
    if clash:
        raise SystemExit(f"Connecticut: a local race has a state race's id ({', '.join(clash)})")

    # Connecticut's rows only, in one transaction: its races and candidates by state and race id, its sources, gaps and
    # notes by state, its places by their ct- source ids
    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA + EXTRA_SCHEMA)
    with con:
        con.execute("DELETE FROM sl_candidates WHERE race_id IN (SELECT race_id FROM sl_races WHERE state = ?)", (STATE,))
        con.execute("DELETE FROM sl_candidates WHERE race_id LIKE ?", (f"2026-{STATE}-%",))
        con.execute("DELETE FROM sl_races WHERE state = ?", (STATE,))
        con.execute("DELETE FROM sl_sources WHERE state = ?", (STATE,))
        con.execute("DELETE FROM sl_places WHERE source_id LIKE ?", (STATE.lower() + "-%",))
        con.execute("DELETE FROM sl_gaps WHERE state = ?", (STATE,))
        con.execute("DELETE FROM sl_notes WHERE state = ?", (STATE,))
        con.executemany("INSERT INTO sl_races VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", list(races.values()) + local["races"])
        con.executemany("INSERT INTO sl_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", cands + local["cands"])
        con.executemany("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", sources)
        con.executemany("INSERT INTO sl_places VALUES (?,?,?,?,?)", places)
        con.executemany("INSERT INTO sl_gaps VALUES (?,?,?,?,?,?,?)", local["gaps"])
        con.executemany("INSERT INTO sl_notes VALUES (?,?,?,?,?)", local["notes"])
    con.close()

    # ---- say what was done, and what is still missing
    def count(kind, rows):
        return sum(1 for c in rows if races[c[0]][3] == kind)
    have = {k: sum(1 for (kk, _d) in ballot if kk == k) for k in ("SS", "SH")}
    missing_sw = [OFFICE[k][0] for k in STATEWIDE if (k, "") not in ballot]
    say(f"    Connecticut: {len(races)} races ({SENATE_SEATS} Senate, {HOUSE_SEATS} House, {len(races) - SENATE_SEATS - HOUSE_SEATS} statewide); "
        f"November candidates from the sample ballots of {len(index) - len(unreadable)} of {TOWNS} towns: statewide "
        f"{sum(1 for c in general if races[c[0]][2] == 'statewide')} ({5 - len(missing_sw)} of 5 offices), Senate {count('state_senate', general)} "
        f"({have['SS']} of {SENATE_SEATS} districts), House {count('state_house', general)} ({have['SH']} of {HOUSE_SEATS} districts); "
        f"{sum(1 for c in general if c[14] and 'party lines' in c[14])} on more than one party line; {fields} primary fields "
        f"({len(primary_rows)} rows, {unopposed} one-candidate contests not stored), votes from the official returns"
        + (f"; not yet official: {', '.join(unofficial)}" if unofficial else "")
        + (f"; primary winners not on the November ballot: {', '.join(not_on)}" if not_on else ""))
    if skipped:
        say(f"      primary contests not read here (other loaders or not loaded): {', '.join(sorted(skipped))}")
    for c in cands:
        if c[12]:
            say(f"      matched: {c[0]} {c[1]}: {c[3]} -> {c[12]}{' (holds this seat)' if c[7] else ''}")
    for town, why in unreadable:
        say(f"      check: set aside, {why}")
    if missing_sw:
        say(f"      check: no posted ballot read for {', '.join(missing_sw)}")
    for k, n in (("SS", SENATE_SEATS), ("SH", HOUSE_SEATS)):
        gap = [str(d) for d in range(1, n + 1) if (k, str(d)) not in ballot]
        if gap:
            say(f"      check: {len(gap)} {'Senatorial' if k == 'SS' else 'Assembly'} districts have no posted town ballot yet: {', '.join(gap)}")
    for line in report:
        say(f"      check: {line}")
    lc = local["counts"]
    if lc:
        say(f"    Connecticut (local): {lc['probate_races']} judge of probate races, one per probate district ({lc['probate_with']} with the names "
            f"from a posted town, {lc['probate_candidates']} candidates), and {lc['registrar_races']} registrar of voters races "
            f"({lc['registrar_candidates']} candidates), from the local columns of {lc['read']} of the {lc['posted']} posted towns' ballots; "
            f"{lc['counties']} of {COUNTIES} counties reached; {len(local['gaps'])} gap{'s' if len(local['gaps']) != 1 else ''} recorded")
        cl = lc["cells"]
        say(f"      check: {cl['all']} filled cells in the local columns of {lc['read']} ballots = {cl['source']} on the ballots the races are taken "
            f"from ({cl['stored']} party lines stored, held by {lc['probate_candidates'] + lc['registrar_candidates']} candidates, each in one race) "
            f"+ {cl['check']} on ballots read as checks" + (f" + {cl['unused']} not used" if cl["unused"] else ""))
        if lc["empty"]:
            say(f"      note: the office is printed with no candidate's name on the ballot of {', '.join(lc['empty'])} (registrar of voters)")
        if lc["no_registrar"]:
            say(f"      note: no registrar of voters column on the ballot of {', '.join(lc['no_registrar'])}")
        if lc["other_columns"]:
            say(f"      note: {lc['other_columns']} columns for other offices are printed and not read (named in sl_gaps)")
        if lc["more_sheets"]:
            say(f"      note: a ballot of more than one sheet, of which the first is read (named in sl_gaps): {', '.join(lc['more_sheets'])}")
        for why in lc["aside"]:
            say(f"      check: set aside for the local offices, {why}")
    else:
        say("    Connecticut (local): nothing loaded on this run (see sl_gaps)")
    for line in local["report"]:
        say(f"      note: {line}")
    for line in local["problems"]:
        say(f"      CHECK {line}")
    return len(general) + len(local["cands"])


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 1:
        raise SystemExit("usage: python -m ballot.state_local_ct <database> [--refresh]")
    load(args[0], refresh="--refresh" in sys.argv)
