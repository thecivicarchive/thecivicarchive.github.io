"""
ballot/state_local_ma.py - Massachusetts's state races on the November 3, 2026 ballot: all 40 seats of the State Senate
and all 160 seats of the House of Representatives (the General Court; both chambers serve two-year terms, so every seat
is elected this year), the eight seats of the Governor's Council (two-year terms, every seat this year), and the six
constitutional officers elected together every four years in the Governor's year: Governor and Lieutenant Governor (one
ticket in November, nominated in separate primaries), Attorney General, Secretary of the Commonwealth, Treasurer and
Auditor. The September 1 Democratic and Republican primaries are stored with the Secretary's certified votes. Written
into ballot_local_2026.sqlite (never ballot_2026.sqlite), Massachusetts's rows only.

Sources, all the Secretary of the Commonwealth's Elections Division's own, the same two the federal loader
(ballot/lists/ma.py) reads for Congress:

  - PD43+ Certified Election Results (electionstats.state.ma.us, "all from Public Document 43", the Secretary's official
    returns). Its search for 2026 and each office (Governor 3, Lieutenant Governor 4, Attorney General 12, Secretary of
    the Commonwealth 45, Treasurer 53, Auditor 90, Governor's Council 529, State Senate 9, State Representative 8) lists
    every primary with each candidate's votes, the winner's mark, a "(Write-In)" label for a named write-in, All Others
    (write-in votes for names not listed), Blanks and Total Votes Cast. The page carries names, votes and the office
    only. Each primary's CSV download (city and town totals and a TOTALS row) is the control: the towns must add up to
    the TOTALS row, and the TOTALS row must equal the search page, for every candidate and line; it also says which
    cities and towns each district reaches. Every district of each chamber, and every Council district, has a Democratic
    and a Republican primary listed, so PD43+ is also the list of seats: it must name exactly the 40 Senate and 160
    House districts the roster and states/places.py know, and the 8 Council districts. The special elections PD43+ lists
    for 2026 (held earlier in the year to fill vacancies) are left out unless one is dated November 3; their dates come
    from the election's own page. What is kept goes to ballot_cache/ma/sl_ma_2026_primary_results.json (names, votes,
    town names), refreshed after 30 days; a run that stops partway keeps the CSV figures read so far and picks up there.
    Learned from the 2026 files: the search page leaves out an All Others or Blanks line that is zero; a primary no one
    ran in has a CSV column "No Nomination" with a dash in every town; the CSV writes names in title case (Mcgonagle for
    McGonagle) and now and then differently from the search page (Tara Thorn Hong for Tara Hong, Macgregor for
    MaGgregor), so the control pairs the same given name and family name, or one letter apart, with the same votes, and
    the loader lists the pairs that differ by more than case (the search page's spelling is shown, with a note).
  - The November list: the Division's "2026 State Election Candidates" page, one heading per office, one per district,
    one paragraph per candidate: name, street address, city or town, party or designation. www.sec.state.ma.us sits
    behind an Incapsula bot wall, which is never worked around, so the page is read only as a browser saves it into
    ballot_cache/ma/ (any name containing "2026 State Election Candidates"; the federal loader reads the same file).
    Only the name (with a following Jr., Sr., II ...) and the party (the last field) are taken from a line; the street
    and the town between them are dropped on the spot and never printed, logged, cached or stored, and an error names
    the section, never the line. A last field that is neither a designation in ballot/lists/ma.py's PARTIES nor one of
    the 351 cities and towns stops the loader (so an address can never be taken for a party). Until the page is saved,
    no November candidates are stored and every race says why.
  - Who holds each seat today, from state_ma.sqlite (the Open States roster the state pages use): sitting legislators by
    chamber and district, and the statewide officers it carries (Governor, Lieutenant Governor, Attorney General,
    Treasurer, Auditor, and the Secretary as "chief election officer"). Only ids, names, parties, chambers, districts and
    offices are selected. The roster carries no Governor's Councillors.
  - The Census Bureau's 2020 county subdivision codes for Massachusetts (st25_ma_cousub2020.txt), for the county of each
    city and town (every one lies in a single county), so each district carries the counties it reaches.

Race ids: 2026-MA-SS<district>, 2026-MA-SH<district> (the district as PD43+ writes it, made into one word: ordinals as
numbers, "and", "&" and commas set aside, the rest joined by hyphens: 2026-MA-SH7-Hampden, 2026-MA-SS1-Essex-Middlesex,
2026-MA-SSBerkshire-Hampden-Franklin-Hampshire; the district column keeps the Secretary's own words), 2026-MA-GC<n>
(Governor's Council, office_kind governors_council, level statewide like other states' district-elected boards),
2026-MA-GOV (Governor and Lieutenant Governor, the November ticket), 2026-MA-LTG (the Lieutenant Governor's primaries
only), 2026-MA-AG, 2026-MA-SOS, 2026-MA-TREAS, 2026-MA-AUD.

A party's primary is stored as a field when two or more candidates were printed on its ballot for the seat (a named
write-in is shown as one, write_in 1). pct is a candidate's share of the votes for candidates and write-ins (All Others),
blanks left out, as PD43+ computes it (checked to 0.1). The winner's mark says who advanced; it must be the top
vote-getter. A candidate is the incumbent (incumbent 1, state_member_id) only when the name fits exactly one sitting
member of the same chamber and district (or the statewide officer), and that member fits only that candidate; a sitting
legislator or officer running for another office is given their roster id (not incumbent) when the name fits exactly
one of them of the same party.

    python -m ballot.state_local_ma <path to a test database> [--list-dir <folder holding a saved November page>]
"""

import collections
import csv
import datetime as dt
import hashlib
import io
import json
import os
import re
import sqlite3
import sys
import time
from urllib.error import HTTPError

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from ballot.common import CACHE, fold, name_parts  # noqa: E402
from ballot.lists import ma as MA  # noqa: E402
from ballot.lists.tx import proper  # noqa: E402
from ballot.match import fits  # noqa: E402
from states import net  # noqa: E402

STATE, FIPS = "MA", "25"
GENERAL, PRIMARY = "2026-11-03", MA.PRIMARY
ROSTER = os.path.join(HERE, "state_ma.sqlite")
ES = MA.ES
SEARCH = MA.SEARCH                     # .../elections/search/year_from:2026/year_to:2026/office_id:{office}
CSV_URL = MA.CSV_URL                   # .../elections/download/{eid}/precincts_include:0/
VIEW = ES + "/elections/view/{eid}/"
LIST_PAGE = MA.LIST_PAGE
COUSUB_URL = "https://www2.census.gov/geo/docs/reference/codes2020/cousub/st25_ma_cousub2020.txt"
COUSUB_FILE = "census_st25_ma_cousub2020.txt"
RESULTS_FILE = "sl_ma_2026_primary_results.json"
PARTIAL_FILE = "sl_ma_2026_primary_towns_partial.json"
SRC_PRI, SRC_CSV, SRC_GEN = "ma-sec-2026-sl-primary-results", "ma-sec-2026-sl-primary-towns", "ma-sec-2026-sl-general-list"
SRC_ROSTER, SRC_CENSUS = "ma-openstates-roster", "ma-census-cousub-2020"

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

# PD43+ office id -> (race key, level, office_kind, office as shown, PD43+'s own office name)
OFFICES = {
    3: ("GOV", "statewide", "governor", "Governor and Lieutenant Governor", "Governor"),
    4: ("LTG", "statewide", "lieutenant_governor", "Lieutenant Governor", "Lieutenant Governor"),
    12: ("AG", "statewide", "attorney_general", "Attorney General", "Attorney General"),
    45: ("SOS", "statewide", "secretary_of_state", "Secretary of the Commonwealth", "Secretary of the Commonwealth"),
    53: ("TREAS", "statewide", "state_treasurer", "Treasurer and Receiver General", "Treasurer"),
    90: ("AUD", "statewide", "state_auditor", "Auditor of the Commonwealth", "Auditor"),
    529: ("GC", "statewide", "governors_council", "Governor's Councillor", "Governor's Council"),
    9: ("SS", "legislature", "state_senate", "State Senator", "State Senate"),
    8: ("SH", "legislature", "state_house", "State Representative", "State Representative"),
}
SEATS = {"SS": 40, "SH": 160, "GC": 8}
ROSTER_OFFICE = {"GOV": "governor", "LTG": "lt_governor", "AG": "attorney general", "SOS": "chief election officer",
                 "TREAS": "treasurer", "AUD": "auditor"}
CHAMBER = {"SS": "Senate", "SH": "House"}
OFFICE_WORDS = {"governor": "Governor", "lt_governor": "Lieutenant Governor", "attorney general": "Attorney General",
                "chief election officer": "Secretary of the Commonwealth", "treasurer": "Treasurer", "auditor": "Auditor"}
ORDINAL_WORDS = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9,
                 "tenth": 10, "eleventh": 11, "twelfth": 12, "thirteenth": 13, "fourteenth": 14, "fifteenth": 15, "sixteenth": 16,
                 "seventeenth": 17, "eighteenth": 18, "nineteenth": 19, "twentieth": 20}
TENS = {"twenty": 20, "thirty": 30, "forty": 40}
UNITS = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9}
ABBREV = {"e": "east", "n": "north", "s": "south", "w": "west"}       # PD43+ writes E. Bridgewater, N. Adams, W. Tisbury

# the November page's section headings, folded, and what each is (None: not a state office read here)
SECTION = {
    "governor": "GOV", "lieutenant governor": "LTG", "governor and lieutenant governor": "TICKET",
    "attorney general": "AG", "secretary of state": "SOS", "secretary of the commonwealth": "SOS",
    "treasurer": "TREAS", "treasurer and receiver general": "TREAS", "state treasurer": "TREAS",
    "auditor": "AUD", "state auditor": "AUD", "auditor of the commonwealth": "AUD",
    "councillor": "GC", "governor s councillor": "GC", "governor s council": "GC", "executive councillor": "GC",
    "senator in general court": "SS", "state senator": "SS", "state senate": "SS",
    "representative in general court": "SH", "state representative": "SH",
    "senator in congress": None, "representative in congress": None,
}

WRITE_IN = MA.WRITE_IN
WAIT = ("The Secretary of the Commonwealth's November candidate list is not loaded yet: www.sec.state.ma.us turns away "
        "automated requests, so the list waits to be saved from a browser. Until then only the certified September 1 "
        "primary results are shown; the November ballot can also carry unenrolled and other candidates who ran in no primary.")
NOTES = {
    "SS": "Massachusetts elects all 40 state senators every two years; every Senate district is on the 2026 ballot.",
    "SH": "Massachusetts elects all 160 state representatives every two years; every House district is on the 2026 ballot.",
    "GC": ("The Governor's Council (eight councillors, two-year terms) confirms judges and other appointments; every Council "
           "district is on the 2026 ballot. The Open States roster this site uses does not carry councillors, so today's "
           "holder is not shown."),
    "GOV": ("Massachusetts elects the Governor and Lieutenant Governor together in November, one vote for the pair; each party "
            "nominates them in separate primaries (the Lieutenant Governor's under 2026-MA-LTG)."),
    "LTG": ("Nominated in each party's own September 1 primary; in November the Lieutenant Governor is elected jointly with the "
            "Governor, one vote for the pair (see 2026-MA-GOV)."),
}


# ------------------------------------------------------------------------------------------------ fetching and caching

def fetch(url, accept="*/*", say=print):
    """One request, asked at most twice more on a refusal or a server error, never past a challenge page."""
    for attempt in range(3):
        try:
            raw = net.get(url, accept=accept)
        except HTTPError as e:
            if e.code not in (403, 429, 500, 502, 503, 504) or attempt == 2:
                raise
            say(f"      {url}: HTTP {e.code}; asking again in {10 * (attempt + 1)} s")
            time.sleep(10 * (attempt + 1))
            continue
        head = raw[:4000].lower()
        if b"captcha" in head or b"challenge-platform" in head or b"incapsula" in head or b"_incapsula_resource" in head:
            raise SystemExit(f"Massachusetts (state races): {url} answered with a bot check; it was not worked around. A person in "
                             "a browser would have to fetch it.")
        return raw
    raise SystemExit(f"Massachusetts (state races): {url} could not be read")


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def mtime(path):
    return dt.datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d")


# ------------------------------------------------------------------------------------------- the certified primary results

def search(office, say):
    """Every 2026 election PD43+ lists for one office: id, where (Statewide, a district), stage, party, special, candidates
    and the All Others, Blanks and Total lines."""
    key, _, _, _, pd_name = OFFICES[office]
    url = SEARCH.format(office=office)
    page = fetch(url, accept="text/html", say=say).decode("utf-8", "replace")
    time.sleep(1.5)
    if "election-id-" not in page:
        raise SystemExit(f"Massachusetts (state races): the PD43+ search for {pd_name} lists no elections ({url})")
    out = []
    for part in re.split(r'(?=<tr\s+id="election-id-)', page)[1:]:
        eid = re.match(r'<tr\s+id="election-id-(\d+)"', part).group(1)
        part = part.split('<tr class="more_info"')[0]
        cells = [MA.text(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", part[:part.find("candidates_container_cell")] + "</td>", re.S)][:4]
        if len(cells) < 4 or cells[0] != "2026" or cells[1] != pd_name:
            raise SystemExit(f"Massachusetts (state races): PD43+ election {eid} does not read as a 2026 {pd_name} election ({cells[:2]})")
        stage = cells[3]
        m = re.fullmatch(r"(Special )?(?:(.+?) Primary|General Election|General)", stage)
        if not m:
            raise SystemExit(f"Massachusetts (state races): PD43+ election {eid} is a stage that is not read ({stage!r})")
        special, party = bool(m.group(1)), m.group(2)
        where = cells[2]
        if key in ("SS", "SH", "GC"):
            if where in ("", "Statewide"):
                raise SystemExit(f"Massachusetts (state races): PD43+ {pd_name} election {eid} names no district")
            if key == "GC" and not re.fullmatch(r"[1-8](?:st|nd|rd|th)", where):
                raise SystemExit(f"Massachusetts (state races): PD43+ Council election {eid} names a district that is not read ({where!r})")
        elif where != "Statewide":
            raise SystemExit(f"Massachusetts (state races): PD43+ {pd_name} election {eid} is not statewide ({where!r})")
        cands, lines = [], {}
        for cls, body in re.findall(r'<tr class="([^"]*)">(.*?)</tr>', part, re.S):
            nums = [MA.text(n) for n in re.findall(r'<td class="number">(.*?)</td>', body, re.S)]
            if "non_candidate" in cls:
                kind = re.search(r"n_(all_other|blank|total)_votes", cls)
                if not kind or not nums:
                    raise SystemExit(f"Massachusetts (state races): a line in PD43+ election {eid} that is not read ({cls.strip()!r})")
                lines[kind.group(1)] = MA.ints(nums[0])
                continue
            name = re.search(r'<div class="name">(.*?)</div>', body, re.S)
            if not name or len(nums) < 2:
                continue
            label = re.search(r'<div class="party">(.*?)</div>', body, re.S)
            label = MA.text(label.group(1)) if label else ""
            if label not in ("", "(Write-In)") and party:          # a general election prints each candidate's party here
                raise SystemExit(f"Massachusetts (state races): a label beside a name in PD43+ election {eid} that is not read ({label!r})")
            cands.append({"name": MA.text(name.group(1)), "write_in": label == "(Write-In)", "votes": MA.ints(nums[0]),
                          "pct": float(nums[1].rstrip("%")) if nums[1] else None, "winner": "is_winner" in cls,
                          **({"label": label} if label and not party else {})})
        if cands:
            if "total" not in lines:
                raise SystemExit(f"Massachusetts (state races): PD43+ election {eid} is missing its Total Votes Cast line")
            lines.setdefault("all_other", 0)                      # PD43+ leaves out an All Others or Blanks line that is zero;
            lines.setdefault("blank", 0)                          # the lines must still add up, and the CSV must agree
        out.append({"id": eid, "office": office, "key": key, "where": where, "stage": stage, "party": party, "special": special,
                    "candidates": cands, **lines})
    return out


def election_date(eid, say):
    """The date PD43+'s own page for one election gives (its data block's "date")."""
    page = fetch(VIEW.format(eid=eid), accept="text/html", say=say).decode("utf-8", "replace")
    time.sleep(1.0)
    m = re.search(r'"date":"(\d{4}-\d\d-\d\d)","year":"(\d{4})"', page)
    if not m:
        raise SystemExit(f"Massachusetts (state races): PD43+'s page for election {eid} gives no date")
    return m.group(1)


def town_totals(eid, say):
    """The CSV download of one election: the cities and towns, each column summed over them, and the TOTALS row."""
    raw = fetch(CSV_URL.format(eid=eid), say=say)
    time.sleep(1.0)
    if raw[:8].lstrip(b"\xef\xbb\xbf")[:4] != b"City":
        raise SystemExit(f"Massachusetts (state races): PD43+'s download for election {eid} is not its CSV file")
    rows = list(csv.reader(io.StringIO(raw.decode("utf-8-sig", "replace"))))
    heads = [MA.squash(h) for h in rows[0]]
    for need in ("City/Town", "All Others", "Blanks", "Total Votes Cast"):
        if need not in heads:
            raise SystemExit(f"Massachusetts (state races): PD43+'s CSV for election {eid} has no {need!r} column")
    # "No Nomination" is the column of a primary no one ran in: a dash in every town, no votes
    cols = [i for i, h in enumerate(heads) if h and h not in ("City/Town", "Ward", "Pct", "No Nomination")]
    sums, totals, towns = {heads[i]: 0 for i in cols}, None, []
    for r in rows[1:]:
        first = MA.squash(r[0]) if r else ""
        if not first:
            continue
        if first == "TOTALS":
            totals = {heads[i]: MA.ints(r[i]) for i in cols}
            continue
        towns.append(first)
        for i in cols:
            sums[heads[i]] += MA.ints(r[i]) if MA.squash(r[i]) else 0
    if totals is None:
        raise SystemExit(f"Massachusetts (state races): PD43+'s CSV for election {eid} has no TOTALS row")
    return {"towns": towns, "sums": sums, "totals": totals}


def one_slip(a, b):
    """True when two words differ by at most one letter added, dropped or changed."""
    if a == b:
        return True
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) > len(b):
        a, b = b, a
    i = 0
    while i < len(a) and a[i] == b[i]:
        i += 1
    return a[i + (len(a) == len(b)):] == b[i + 1:]


def same_but_spelling(a, b):
    """The same person written two ways by PD43+: a given name that fits and the family name the same, or one of the two
    names' family name found in the other (Tara Hong, Tara Thorn Hong), or one letter apart (MaGgregor, Macgregor)."""
    (ga, fa), (gb, fb) = name_parts(a), name_parts(b)
    if not fits((ga, fa), (gb, fb)) and not (ga and gb and ga[0] == gb[0] and one_slip(fa, fb)):
        return False
    return True


def printed(e):
    return [x for x in e["candidates"] if not x["write_in"]]


def primary_results(say, folder):
    """Every office's 2026 elections; each field's CSV (the control) and one CSV per district (its cities and towns);
    the date of every special election and of one regular primary (to confirm September 1). The CSV figures read so far
    are kept in a partial file, so a run that stops partway picks up where it left off."""
    ppath = os.path.join(folder, PARTIAL_FILE)
    partial = json.load(open(ppath, encoding="utf-8")) if os.path.exists(ppath) else {}
    elections = []
    for office in OFFICES:
        got = search(office, say)
        say(f"      PD43+: {OFFICES[office][4]}, {len(got)} elections listed")
        elections += got
    regular = [e for e in elections if not e["special"] and e["party"]]
    if not regular:
        raise SystemExit("Massachusetts (state races): PD43+ lists no regular 2026 primary")
    dates = {"regular": election_date(regular[0]["id"], say)}
    for e in elections:
        if e["special"]:
            e["date"] = election_date(e["id"], say)
    wanted = {e["id"] for e in regular if len(printed(e)) >= 2}
    by_district = collections.defaultdict(list)
    for e in regular:
        if e["key"] in SEATS:
            by_district[(e["key"], e["where"])].append(e)
    for es in by_district.values():
        if not any(e["id"] in wanted for e in es):
            pick = next((e for e in es if e["candidates"]), es[0])
            wanted.add(pick["id"])
    n = 0
    for e in elections:
        if e["id"] in wanted:
            if e["id"] not in partial:
                partial[e["id"]] = town_totals(e["id"], say)
                if len(partial) % 25 == 0:
                    with open(ppath, "w", encoding="utf-8") as fh:
                        json.dump(partial, fh, ensure_ascii=False)
            e["csv"] = partial[e["id"]]
            n += 1
            if n % 50 == 0:
                say(f"      PD43+: {n} of {len(wanted)} city and town files read")
    say(f"      PD43+: {n} city and town files read")
    if os.path.exists(ppath):
        os.remove(ppath)
    return {"elections": elections, "dates": dates}


def check_results(results):
    """Controls: the towns add up to TOTALS, TOTALS equal the search page, the lines add up, pct agrees, one winner and
    the top one."""
    checked, spelled = 0, []
    for e in results["elections"]:
        if "csv" not in e:
            continue
        c = e["csv"]
        where = f"PD43+ election {e['id']} ({OFFICES[e['office']][4]}, {e['where']}, {e['stage']})"
        if c["sums"] != c["totals"]:
            raise SystemExit(f"Massachusetts (state races): {where}: the cities and towns do not add up to the TOTALS row")
        page = {x["name"]: x["votes"] for x in e["candidates"]}
        page.update({"All Others": e.get("all_other", 0), "Blanks": e.get("blank", 0), "Total Votes Cast": e.get("total", 0)})
        totals = dict(c["totals"])
        if e["candidates"] and page != totals:
            # the CSV's heading can spell a name more fully than the search page (Tara Thorn Hong, Tara Hong): the same
            # person (family name and first given name) with the same votes, one to one, is the same line
            for a in [n for n in page if n not in totals]:
                b = [n for n in totals if n not in page and totals[n] == page[a] and same_but_spelling(a, n)]
                if len(b) == 1:
                    if a.lower() != b[0].lower():                   # the CSV writes Mcgonagle for McGonagle: case alone is not listed
                        spelled.append(f"{a} / {b[0]} ({e['where']}, {e['stage']})")
                        e.setdefault("csv_spelling", {})[a] = b[0]
                    totals[a] = totals.pop(b[0])
            if page != totals:
                raise SystemExit(f"Massachusetts (state races): {where}: the CSV's TOTALS row does not equal the search page "
                                 f"({sorted(set(page.items()) ^ set(totals.items()))[:4]})")
        checked += 1
    for e in results["elections"]:
        if not e["candidates"]:
            continue
        where = f"PD43+ election {e['id']} ({OFFICES[e['office']][4]}, {e['where']}, {e['stage']})"
        if sum(x["votes"] for x in e["candidates"]) + e["all_other"] + e["blank"] != e["total"]:
            raise SystemExit(f"Massachusetts (state races): {where}: the candidates, All Others and Blanks do not add up to Total Votes Cast")
        cast = sum(x["votes"] for x in e["candidates"]) + e["all_other"]
        for x in e["candidates"]:
            if x["pct"] is not None and cast and abs(round(100 * x["votes"] / cast, 1) - x["pct"]) > 0.11:
                raise SystemExit(f"Massachusetts (state races): {where}: {x['name']}'s share does not agree with PD43+'s ({x['pct']}%)")
        won = [x for x in e["candidates"] if x["winner"]]
        top = max(x["votes"] for x in e["candidates"])
        if len(won) > 1 or (won and won[0]["votes"] != top):
            raise SystemExit(f"Massachusetts (state races): {where}: the winner's mark is not on the one top vote-getter")
    return checked, spelled


# --------------------------------------------------------------------------------------------------------- places

def town_key(name):
    words = fold(name).split()
    if len(words) > 1 and words[0] in ABBREV:
        words[0] = ABBREV[words[0]]
    return " ".join(words)


def counties_of_towns(path):
    """{town key: county GEOID} and {county GEOID: county name} from the Census codes file (names and codes only)."""
    town, names = {}, {}
    lines = open(path, encoding="utf-8-sig").read().splitlines()
    head = lines[0].split("|")
    need = ("STATEFP", "COUNTYFP", "COUNTYNAME", "COUSUBFP", "COUSUBNAME")
    if any(h not in head for h in need):
        raise SystemExit(f"Massachusetts (state races): {os.path.basename(path)} does not have the columns {need}")
    ix = {h: head.index(h) for h in need}
    for line in lines[1:]:
        f = line.split("|")
        if f[ix["STATEFP"]] != FIPS:
            continue
        geoid = FIPS + f[ix["COUNTYFP"]]
        names[geoid] = f[ix["COUNTYNAME"]]
        if f[ix["COUSUBFP"]] == "00000":
            continue                                              # "County subdivisions not defined" (water areas)
        n = re.sub(r" Town$", "", re.sub(r" (city|town)$", "", f[ix["COUSUBNAME"]]))
        k = town_key(n)
        if k in town and town[k] != geoid:
            raise SystemExit(f"Massachusetts (state races): two counties hold a city or town named {n}")
        town[k] = geoid
    if len(town) != 351 or len(names) != 14:
        raise SystemExit(f"Massachusetts (state races): the Census codes file gives {len(town)} cities and towns in {len(names)} counties, "
                         "not 351 in 14")
    return town, names


# ------------------------------------------------------------------------------------------------ districts and names

def number(word):
    w = word.lower()
    m = re.fullmatch(r"(\d+)(?:st|nd|rd|th)?", w)
    if m:
        return str(int(m.group(1)))
    if w in ORDINAL_WORDS:
        return str(ORDINAL_WORDS[w])
    return None


def dkey(text):
    """A district name as both the Secretary and the roster would write it: ordinals as numbers, "and", "&", commas and
    the word District set aside, no case (1st Essex & Middlesex = First Essex and Middlesex District)."""
    s = (text or "").lower().replace("&", " ").replace(",", " ").replace("-", " ")
    s = re.sub(r"\b(twenty|thirty|forty)\s+(" + "|".join(UNITS) + r")\b", lambda m: str(TENS[m.group(1)] + UNITS[m.group(2)]), s)
    words = [number(w) or w for w in s.split() if w not in ("and", "district", "councillor")]
    return " ".join(words)


def slug(district):
    """The district made into one word for the race id: 7th Hampden -> 7-Hampden; Berkshire, Hampden, Franklin & Hampshire ->
    Berkshire-Hampden-Franklin-Hampshire."""
    parts = []
    for w in dkey(district).split():
        parts.append(w if w.isdigit() else w.capitalize())
    return "-".join(parts)


def roster(path):
    """Sitting legislators and the statewide officers the roster carries: ids, names, parties, chambers, districts and
    offices only (its contact columns are never selected)."""
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    legs = [dict(zip(("id", "first", "last", "full", "other", "party", "chamber", "district"), r)) for r in con.execute(
        "SELECT bioguide_id, first_name, last_name, official_full, other_names, party_name, chamber, district "
        "FROM legislators WHERE is_current = 1")]
    offs = [dict(zip(("id", "first", "last", "full", "office", "party", "term_end"), r)) for r in con.execute(
        "SELECT bioguide_id, first_name, last_name, official_full, office, party_name, term_end FROM officials")]
    con.close()
    for p in offs:
        p["other"] = ""
    return legs, offs


def readings(name):
    """(given names, family name) readings of a name as printed: with and without a quoted nickname, and the nickname
    alone as a given name."""
    plain = re.sub(r"[\"“”][^\"“”]*[\"“”]|\([^)]*\)", " ", name)
    out = [name_parts(name), name_parts(plain)]
    fam = name_parts(plain)[1]
    for nick in re.findall(r"[\"“”(]([^\"“”()]+)[\"“”)]", name):
        if fold(nick):
            out.append((fold(nick).split(), fam))
    return out


def person_fits(reads, p):
    forms = [(fold(p["first"] or "").split(), " ".join(fold(p["last"] or "").split()))]
    if p.get("full"):
        forms.append(name_parts(p["full"]))
    for o in (p.get("other") or "").split(";"):                  # William F. MacGregor for Billy; never an initial alone (B. MacGregor)
        g, f = name_parts(o.strip())
        if f and g and len(g[0]) > 1:
            forms.append((g, f))
    return any(f[1] and r[1] and fits(r, f) for r in reads for f in forms)


def same_person(a, b):
    """The same candidate written twice (the November list and PD43+): the federal loader's test, or the first given name
    the same and the family name one letter apart (MacGregor, MaGgregor)."""
    if MA.same_person(a, b):
        return True
    (ga, fa), (gb, fb) = name_parts(a), name_parts(b)
    return bool(ga and gb and ga[0] == gb[0] and len(fa) > 3 and one_slip(fa, fb))


def display(name):
    return MA.squash(name)


# ------------------------------------------------------------------------------------------ the November list, as saved

def general_list(path, towns, districts):
    """[(race, name, party or None, order, caps)], the running mates [(party, name)], the lines left off, and the other
    sections' headings, from the saved page. districts: {(key, dkey): race_id} for SS, SH and GC."""
    page = MA.page_html(path)
    if not re.search(r"<h1[^>]*>\s*2026 State Election Candidates\s*</h1>", page):
        raise SystemExit(f"Massachusetts (state races): {os.path.basename(path)} is not the Secretary's \"2026 State Election Candidates\" page")
    main = re.search(r"<main\b.*?</main>", page, re.S)
    main = main.group(0) if main else page
    on, mates, off, other, order, seen = [], [], [], [], collections.Counter(), set()
    section, race = None, None
    for tag, attrs, inner in re.findall(r"<(h2|h3|p)\b([^>]*)>(.*?)</\1>", main, re.S):
        t = MA.text(inner)
        if tag == "h2":
            head = fold(t)
            section = SECTION.get(head, "OTHER")
            race = None
            if section == "OTHER":
                other.append(t)
            elif section in ("GOV", "LTG", "TICKET", "AG", "SOS", "TREAS", "AUD"):
                race = f"2026-{STATE}-{'GOV' if section == 'TICKET' else section}"
            continue
        if section in (None, "OTHER"):
            continue
        if tag == "h3":
            if section not in ("SS", "SH", "GC"):
                raise SystemExit(f"Massachusetts (state races): a district heading under a statewide office on the saved list ({t!r})")
            race = districts.get((section, dkey(t)))
            if not race:
                raise SystemExit(f"Massachusetts (state races): a district heading on the saved list that names no 2026 seat ({t!r})")
            continue
        label = race or f"the {section} section"
        if not t or "top-of-page" in attrs or re.search(r"top of page", t, re.I):
            continue
        if not race:
            raise SystemExit(f"Massachusetts (state races): a candidate line in {label} before any district heading")
        if "," not in t:
            raise SystemExit(f"Massachusetts (state races): a line in {label} that does not read as name, street, town and party")
        fields = [MA.squash(f) for f in t.split(",")]
        name, i = fields[0], 1
        while i < len(fields) and MA.SUFFIX.match(fields[i]):
            name += ", " + fields[i]
            i += 1
        rest = fields[i:]
        struck = bool(re.search(r"<(s|del|strike)\b", inner, re.I)) or bool(MA.OFF.search(name))
        name = MA.squash(MA.OFF.sub("", name))
        if re.search(r"\d", name) or not re.fullmatch(r"[A-Za-z .,'\"()\-À-ſ‘-”]+", name) or len(name.split()) > 12:
            raise SystemExit(f"Massachusetts (state races): a candidate line in {label} does not begin with a name")
        if len(rest) < 2:
            raise SystemExit(f"Massachusetts (state races): a candidate line in {label} has fewer fields than a name, street, town and party")
        last = rest[-1]
        if last in MA.PARTIES:
            party = last
        elif town_key(last) in towns:
            party = None                                          # the line ends with the town: no party printed
        else:
            raise SystemExit(f"Massachusetts (state races): a candidate line in {label} ends in a field that is neither a designation in "
                             "ballot/lists/ma.py's PARTIES nor a Massachusetts city or town; look at the page and add the designation")
        rest = None                                               # the street and town are dropped here
        where = f"2026-{STATE}-LTG" if section == "LTG" else label
        if struck:
            off.append(f"{name} ({where})")
            continue
        caps = name == name.upper() and any(c.isalpha() for c in name)
        shown = proper(name) if caps else name
        if section == "TICKET":
            pair = re.split(r"\s+(?:and|&)\s+", shown)
            if len(pair) != 2:
                raise SystemExit("Massachusetts (state races): a Governor and Lieutenant Governor line that does not name two people")
            shown, mate = pair
            mates.append((party, mate, shown))
        elif section == "LTG":
            mates.append((party, shown, None))
            continue
        if (race, fold(shown)) in seen:
            raise SystemExit(f"Massachusetts (state races): {shown} is listed twice in {label}")
        seen.add((race, fold(shown)))
        order[race] += 1
        on.append((race, shown, party, order[race], caps))
    return on, mates, off, other


# ------------------------------------------------------------------------------------------------------------ loading

def load(db_path, say=print, cache=CACHE, roster_db=ROSTER, list_dir=None):
    net.patient_lookups()
    folder = os.path.join(cache, "ma")
    os.makedirs(folder, exist_ok=True)
    report = []

    # 1. the certified primary results, kept as the figures read
    rpath = os.path.join(folder, RESULTS_FILE)
    if os.path.exists(rpath) and time.time() - os.path.getmtime(rpath) < 30 * 86400:
        results = json.load(open(rpath, encoding="utf-8"))
    else:
        results = primary_results(say, folder)
        with open(rpath, "w", encoding="utf-8") as fh:
            json.dump(results, fh, ensure_ascii=False, indent=1)
    checked, spelled = check_results(results)
    if spelled:
        report.append(f"names PD43+'s search page and CSV spell differently (the search page's is shown): {spelled}")
    if results["dates"]["regular"] != PRIMARY:
        raise SystemExit(f"Massachusetts (state races): PD43+ dates the 2026 state primary {results['dates']['regular']}, not {PRIMARY}")

    # 2. towns and counties
    cpath = os.path.join(folder, COUSUB_FILE)
    net.download(COUSUB_URL, cpath, 365, say=say)
    town_county, county_names = counties_of_towns(cpath)

    # 3. the seats: every regular primary's office and district
    elections = results["elections"]
    specials = [e for e in elections if e["special"]]
    on_ballot_specials = [e for e in specials if e.get("date") == GENERAL]
    if on_ballot_specials:
        raise SystemExit("Massachusetts (state races): PD43+ lists a special election dated November 3; add it to the loader "
                         f"({[(e['id'], e['where']) for e in on_ballot_specials]})")
    regular = [e for e in elections if not e["special"]]
    stray = [e for e in regular if not e["party"]]
    if stray:
        raise SystemExit(f"Massachusetts (state races): PD43+ already lists a 2026 general election ({stray[0]['id']}); the loader "
                         "reads primaries only")
    legs, offs = roster(roster_db)
    races = {}
    for e in regular:
        key, level, kind, office, _ = OFFICES[e["office"]]
        if key in SEATS:
            if key == "GC":
                district = str(int(re.match(r"\d+", e["where"]).group(0)))
                rid = f"2026-{STATE}-GC{district}"
            else:
                district = e["where"]
                rid = f"2026-{STATE}-{key}{slug(district)}"
        else:
            district, rid = None, f"2026-{STATE}-{key}"
        r = races.setdefault(rid, {"key": key, "level": level, "kind": kind, "office": office, "district": district,
                                   "dk": dkey(district) if district else None, "primaries": [], "towns": set()})
        if r["district"] != district:
            raise SystemExit(f"Massachusetts (state races): two districts share the race id {rid} ({r['district']!r}, {district!r})")
        r["primaries"].append(e)
        if "csv" in e:
            r["towns"] |= set(e["csv"]["towns"])
    for key in ("GOV", "LTG", "AG", "SOS", "TREAS", "AUD"):
        if f"2026-{STATE}-{key}" not in races:
            raise SystemExit(f"Massachusetts (state races): PD43+ lists no 2026 primary for {key}")
    for key, n in SEATS.items():
        got = sorted(r["district"] for r in races.values() if r["key"] == key)
        if len(got) != n:
            raise SystemExit(f"Massachusetts (state races): PD43+ lists {len(got)} {key} districts for 2026, not {n}")
    for key, ch in CHAMBER.items():
        mine = {r["dk"] for r in races.values() if r["key"] == key}
        held = {dkey(p["district"]) for p in legs if p["chamber"] == ch}
        if held - mine:
            raise SystemExit(f"Massachusetts (state races): roster {ch} districts PD43+ does not list: {sorted(held - mine)[:5]}")
    for rid, r in races.items():
        parties = sorted(e["party"] for e in r["primaries"])
        if parties != ["Democratic", "Republican"]:
            report.append(f"{rid}: PD43+ lists these primaries: {parties}")
    for key in SEATS:
        towns = set().union(*(r["towns"] for r in races.values() if r["key"] == key))
        if {town_key(t) for t in towns} != set(town_county):
            raise SystemExit(f"Massachusetts (state races): the {key} districts' city and town files reach {len(towns)} cities and towns, not 351")
    towns_all = set(town_county)

    # 4. holders
    def legs_of(key, dk):
        return [p for p in legs if p["chamber"] == CHAMBER.get(key) and dkey(p["district"]) == dk]

    # one person listed twice for one office (Kim and Kimberly Driscoll): the record with the later term end is kept
    grouped = collections.defaultdict(list)
    for p in offs:
        grouped[(p["office"], fold(p["last"]))].append(p)
    twice = [f"{g[0]['office']}: {', '.join(p['id'] for p in g)}" for g in grouped.values() if len(g) > 1]
    offs = [max(g, key=lambda p: (p["term_end"] or "", p["id"])) for g in grouped.values()]
    if twice:
        report.append(f"roster officials listed twice, the later term end kept: {twice}")

    for rid, r in races.items():
        want = ROSTER_OFFICE.get(r["key"])
        r["holders"] = legs_of(r["key"], r["dk"]) if r["key"] in CHAMBER else [p for p in offs if p["office"] == want] if want else []
        if len(r["holders"]) > 1:
            raise SystemExit(f"Massachusetts (state races): the roster lists {len(r['holders'])} sitting members for {rid}")

    def identify(rid, name, party, also=None):
        """(incumbent, member id, note) for one candidate: the seat's holder first, then any sitting legislator or officer of
        the same party whose name fits only this one. also: the same name as PD43+'s city and town file spells it."""
        reads = readings(name) + (readings(also) if also else [])
        h = races[rid]["holders"]
        if h and person_fits(reads, h[0]):
            return 1, h[0]["id"], None
        pool = [p for p in legs + offs if person_fits(reads, p) and (not party or (p["party"] or "") == party)]
        if len(pool) == 1:
            p = pool[0]
            if p in legs:
                where = f"Serves today in the Massachusetts {'Senate' if p['chamber'] == 'Senate' else 'House'} ({p['district']} District)."
            else:
                where = f"Serves today as {OFFICE_WORDS.get(p['office'], p['office'])}."
            return 0, p["id"], where
        return 0, None, None

    # 5. the primary fields
    cands, nfields, winners = [], collections.Counter(), collections.defaultdict(list)
    for rid, r in sorted(races.items()):
        for e in r["primaries"]:
            for x in e["candidates"]:
                if x["winner"]:
                    winners[rid].append((e["party"], x["name"], x["write_in"]))
            if len(printed(e)) < 2:
                continue
            nfields[r["kind"]] += 1
            cast = sum(x["votes"] for x in e["candidates"]) + e["all_other"]
            rows = []
            for x in sorted(e["candidates"], key=lambda x: (-x["votes"], x["name"])):
                inc, mid, note = identify(rid, x["name"], e["party"], e.get("csv_spelling", {}).get(x["name"]))
                notes = [WRITE_IN] if x["write_in"] else []
                if x["name"] in e.get("csv_spelling", {}):
                    notes.append(f"PD43+'s city and town file spells this name {e['csv_spelling'][x['name']]}.")
                if note:
                    notes.append(note)
                rows.append([rid, f"primary-{MA.code(e['party'])}", PRIMARY, display(x["name"]), e["party"], MA.colour(e["party"]), None,
                             inc, int(x["write_in"]), x["votes"], round(100 * x["votes"] / cast, 1) if cast else None,
                             "advanced" if x["winner"] else "lost", mid, SRC_PRI, " ".join(notes) or None])
            one_each(rows)
            cands += rows

    # 6. the November list, if a browser has saved it
    gpath = MA.saved_list(list_dir or folder)
    gen_rows, off, other, not_on, later, mates_used = [], [], [], [], [], 0
    if gpath:
        districts = {(r["key"], r["dk"] if r["key"] != "GC" else r["district"]): rid for rid, r in races.items() if r["key"] in SEATS}
        on, mates, off, other = general_list(gpath, towns_all, districts)
        for race, name, party, order, caps in on:
            notes = ["Massachusetts's list prints names in capitals; they are shown here in ordinary capitals."] if caps else []
            if party is None:
                won = [p for p, n, _ in winners.get(race, []) if same_person(n, name)]
                if len(won) == 1:
                    party = won[0]
                    notes.append(MA.NO_PARTY_NOMINEE)
                else:
                    notes.append(MA.NO_PARTY)
            if race == f"2026-{STATE}-GOV":
                mate = [m for p, m, g in mates if (g and g == name) or (g is None and p and p == party)]
                if len(mate) == 1:
                    mates_used += 1
                    notes.insert(0, f"On one ticket with {mate[0]} for Lieutenant Governor, as the list names them.")
                else:
                    notes.insert(0, "The list names no single running mate of the same party for this candidate.")
            inc, mid, note = identify(race, name, party)
            if note:
                notes.append(note)
            gen_rows.append([race, "general", GENERAL, name, party, MA.colour(party) if party else "O", order, inc, 0, None, None, None,
                             mid, SRC_GEN, " ".join(notes) or None])
        by_race = collections.defaultdict(list)
        for g in gen_rows:
            by_race[g[0]].append(g)
        for g in by_race.values():
            one_each(g)
        for rid, won in winners.items():
            if rid == f"2026-{STATE}-LTG":
                continue
            for party, name, _ in won:
                if not any(g[4] == party and same_person(g[3], name) for g in by_race.get(rid, [])):
                    not_on.append(f"{name} ({rid}, {party})")
                    for c in cands:
                        if c[0] == rid and c[3] == display(name) and c[1] == f"primary-{MA.code(party)}":
                            c[14] = ((c[14] + " ") if c[14] else "") + "Won the primary but is not on the November list."
        for g in gen_rows:
            if g[4] in ("Democratic", "Republican") and not any(p == g[4] and same_person(n, g[3]) for p, n, _ in winners.get(g[0], [])):
                later.append(f"{g[3]} ({g[0]}, {g[4]})")
        empty = sorted(rid for rid in races if rid != f"2026-{STATE}-LTG" and rid not in by_race)
        if empty:
            report.append(f"seats with no candidate on the November list: {empty}")
        gen_count = collections.Counter(races[g[0]]["key"] for g in gen_rows)
    else:
        gen_count = collections.Counter()

    # 7. the race rows
    race_rows, place_rows = [], []
    for geoid, cname in sorted(county_names.items()):
        place_rows.append(("county", geoid, cname, json.dumps([geoid]), SRC_CENSUS))
    for rid, r in sorted(races.items()):
        notes = [NOTES[r["key"]]] if r["key"] in NOTES else []
        if r["key"] in CHAMBER and not r["holders"]:
            notes.append("The Open States roster this site uses lists no sitting member for this district today.")
        if not gpath and rid != f"2026-{STATE}-LTG":
            notes.append(WAIT)
            won = winners.get(rid, [])
            if won:
                notes.append("The Secretary's certified September 1 primary results mark as winners: " +
                             "; ".join(f"{display(n)} ({p}{', a write-in' if w else ''})" for p, n, w in sorted(won)) + ".")
            elif not any(e["candidates"] for e in r["primaries"]):
                notes.append("No one's name was on either party's September 1 primary ballot for this seat.")
        cids = sorted({town_county[town_key(t)] for t in r["towns"]}) if r["key"] in SEATS else []
        h = r["holders"][0] if r["holders"] else None
        jur = {"SS": "Massachusetts Senate", "SH": "Massachusetts House of Representatives", "GC": "Governor's Council"}.get(r["key"], "Massachusetts")
        race_rows.append((rid, STATE, r["level"], r["kind"], r["office"], jur, FIPS, json.dumps(cids) if cids else None, r["district"], None,
                          0, 1, h["id"] if h else None, display(h["full"] or f"{h['first']} {h['last']}") if h else None,
                          h["party"] if h else None, GENERAL, " ".join(notes) or None))
        if r["key"] in SEATS:
            pkind = {"SS": "senate", "SH": "house", "GC": "governors_council"}[r["key"]]
            pname = f"{r['district']} District" if r["key"] != "GC" else f"Governor's Council District {r['district']}"
            place_rows.append((pkind, f"{STATE}-{r['district']}", pname, json.dumps(cids), SRC_CSV))
    cands = gen_rows + cands
    keys = collections.Counter((c[0], c[1], c[3]) for c in cands)
    dup = [k for k, n in keys.items() if n > 1]
    if dup:
        raise SystemExit(f"Massachusetts (state races): two candidate rows share race, election and name: {dup[:3]}")
    if len({p[:2] for p in place_rows}) != len(place_rows):
        raise SystemExit("Massachusetts (state races): two places share a kind and id")

    # 8. sources
    n_pri = sum(len(e["candidates"]) for e in regular)
    left_specials = "; ".join(f"{OFFICES[e['office']][4]} {e['where']} {e['stage']} ({e.get('date')})" for e in specials) or "none"
    src = [
        (SRC_PRI, STATE, "official results", "Massachusetts Secretary of the Commonwealth, Elections Division",
         "PD43+ Certified Election Results: 2026 State Primary (September 1, 2026), Governor, Lieutenant Governor, Attorney General, "
         "Secretary of the Commonwealth, Treasurer, Auditor, Governor's Council, State Senate and State Representative",
         SEARCH.format(office=9), "", mtime(rpath), sha(rpath), n_pri,
         f"The PD43+ searches for 2026 and office_id 3, 4, 12, 45, 53, 90, 529, 9 and 8: {len(regular)} party primaries "
         f"({sum(1 for e in regular if e['candidates'])} with candidates), names, votes, winner marks and write-in labels only. "
         f"A field is a party primary with two or more printed candidates. The special elections listed for 2026 are not on the "
         f"November ballot and are left out: {left_specials}. The primary's date is read from PD43+'s own election page. Kept as "
         "the figures read (the SHA-256 is of that JSON)."),
        (SRC_CSV, STATE, "official results", "Massachusetts Secretary of the Commonwealth, Elections Division",
         "PD43+ city and town results (CSV downloads) of the 2026 State Primary", CSV_URL.format(eid="<election id>"), "", mtime(rpath),
         sha(rpath), checked,
         f"Control: for {checked} primaries (every field, and one primary for each Senate, House and Council district) the cities and "
         "towns add up to the TOTALS row, and the TOTALS row equals the search page for every candidate, All Others, Blanks and Total "
         "Votes Cast. The same files give the cities and towns each district reaches; every chamber's districts reach all 351."),
        (SRC_ROSTER, STATE, "roster", "Open States people project (CC0), as loaded into state_ma.sqlite",
         "Sitting Massachusetts legislators and statewide officers", "https://github.com/openstates/people", "", mtime(roster_db),
         sha(roster_db), len(legs) + len(offs),
         "Who holds each legislative seat today (chamber and district), and the Governor, Lieutenant Governor, Attorney General, "
         "Treasurer, Auditor and Secretary of the Commonwealth (the roster's \"chief election officer\"); the roster lists the Lieutenant "
         "Governor twice (Kim and Kimberly Driscoll) and the record with the later term end is used; it carries no Governor's "
         "Councillors. Only ids, names, parties, chambers, districts and offices are read."),
        (SRC_CENSUS, STATE, "geography", "U.S. Census Bureau", "2020 county subdivision codes, Massachusetts (st25_ma_cousub2020.txt)",
         COUSUB_URL, "", mtime(cpath), sha(cpath), len(town_county),
         "The county of each of the 351 cities and towns (names and codes only), for the counties each district reaches. PD43+'s "
         "abbreviations (E., N., S., W.) are read as East, North, South, West."),
    ]
    if gpath:
        src.append((SRC_GEN, STATE, "official candidate list", "Massachusetts Secretary of the Commonwealth, Elections Division",
                    "2026 State Election Candidates (November 3, 2026): state offices", LIST_PAGE, "", mtime(gpath), sha(gpath),
                    len(gen_rows) + len(off),
                    f"Saved from a browser ({os.path.basename(gpath)}): www.sec.state.ma.us answers scripts with an Incapsula challenge. "
                    "Only the name and the party or designation are read from each candidate's line; the street address and town "
                    "printed between them are never kept. Ballot order is the list's own order. Withdrawn or struck through, left off: "
                    f"{len(off)} ({'; '.join(off) or 'none'}). Other sections on the page, not read here: {', '.join(other) or 'none'}."))

    # 9. write Massachusetts's rows only, in one transaction
    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA)
    with con:
        con.execute("DELETE FROM sl_candidates WHERE race_id IN (SELECT race_id FROM sl_races WHERE state = ?)", (STATE,))
        con.execute("DELETE FROM sl_candidates WHERE race_id LIKE ?", (f"2026-{STATE}-%",))
        con.execute("DELETE FROM sl_races WHERE state = ?", (STATE,))
        con.execute("DELETE FROM sl_sources WHERE state = ?", (STATE,))
        con.execute("DELETE FROM sl_places WHERE source_id LIKE ?", (f"{STATE.lower()}-%",))
        con.executemany("INSERT INTO sl_races VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", race_rows)
        con.executemany("INSERT INTO sl_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [tuple(c) for c in cands])
        con.executemany("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", src)
        con.executemany("INSERT INTO sl_places VALUES (?,?,?,?,?)", place_rows)
    con.close()

    # 10. what was done
    kinds = collections.Counter(r["key"] for r in races.values())
    prim = [c for c in cands if c[1] != "general"]
    say(f"    Massachusetts: {len(races)} races (Senate {kinds['SS']}, House {kinds['SH']}, Governor's Council {kinds['GC']}, statewide "
        f"{sum(kinds[k] for k in ('GOV', 'LTG', 'AG', 'SOS', 'TREAS', 'AUD'))} incl. the Lieutenant Governor's primaries); "
        + (f"{len(gen_rows)} candidates on the November list (Senate {gen_count['SS']}, House {gen_count['SH']}, Council {gen_count['GC']}, "
           f"statewide {sum(gen_count[k] for k in ('GOV', 'AG', 'SOS', 'TREAS', 'AUD'))}; {len(off)} left off, {mates_used} running mates)"
           if gpath else "the November list waits for a browser (www.sec.state.ma.us answers scripts with an Incapsula challenge; save "
           f"{LIST_PAGE} into {list_dir or folder}); no November candidates stored")
        + f"; primary fields: Senate {nfields['state_senate']}, House {nfields['state_house']}, Council {nfields['governors_council']}, "
          f"statewide {sum(v for k, v in nfields.items() if k not in ('state_senate', 'state_house', 'governors_council'))} "
          f"({len(prim)} rows), votes from the certified PD43+ results, {checked} city and town files reconciled")
    for c in cands:
        if c[12]:
            say(f"      matched: {c[0]} {c[1]}: {c[3]} -> {c[12]}{' (holds this seat)' if c[7] else ''}")
    if not_on:
        report.append(f"primary winners not on the November list: {not_on}")
    if later:
        report.append(f"party candidates on the November list who did not win its primary: {later}")
    vacant = sorted(rid for rid, r in races.items() if r["key"] in CHAMBER and not r["holders"])
    if vacant:
        report.append(f"districts with no sitting member in the roster: {vacant}")
    for line in report:
        say(f"      check: {line}")
    return len(gen_rows)


def one_each(rows):
    """Never give one member's record to two candidates of the same election in a race: if two rows carry the same id,
    neither keeps it."""
    seen = collections.Counter(r[12] for r in rows if r[12])
    for r in rows:
        if r[12] and seen[r[12]] > 1:
            r[7], r[12] = 0, None
            r[14] = re.sub(r"\s*Serves today [^.]*\.", "", r[14] or "").strip() or None


if __name__ == "__main__":
    args = sys.argv[1:]
    list_dir = None
    if "--list-dir" in args:
        i = args.index("--list-dir")
        list_dir = args[i + 1]
        del args[i:i + 2]
    if len(args) != 1:
        raise SystemExit("usage: python -m ballot.state_local_ma <database> [--list-dir <folder>]")
    load(args[0], list_dir=list_dir)
