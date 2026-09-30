"""
ballot/state_local_nh.py - New Hampshire's state races on the November 3, 2026 ballot, into ballot_local_2026.sqlite (the
federal ballot_2026.sqlite is never opened here, and the U.S. Senate and House races are left to the Congress pages).

Which races are on the ballot, from the law itself (the General Court's copy of the Revised Statutes, gc.nh.gov, which
answers scripts):
  - RSA 653:1: at every state general election, for two-year terms, the governor by the voters of the state, one executive
    councilor in each councilor district, one state senator in each senatorial district, and the number of state
    representatives each representative district is entitled to (county officers are elected too; they are left for the
    county pages). No other office is elected by the voters of the whole state, so the Governor is the one statewide race.
  - RSA 662:2, the five councilor districts; RSA 662:3, the 24 senatorial districts; RSA 662:5, the 203 state representative
    districts, county by county, with the towns and wards of each and the number of representatives it elects (400 in all).
    RSA 662:5 is printed as a table, and three of its rows put the count in the town's cell ("Ossipee 1") and eight put a
    ward's number in the count's cell ("Laconia Ward | 1"); both are read as the printed district shows they must be, and
    every town, ward and unincorporated place is then checked against the Census Bureau's list of New Hampshire's county
    subdivisions (st33_nh_cousub2020.txt), which also gives each district its counties. A district whose towns are exactly
    those of two or more other districts of the county is a floterial district, and its note says which.
  Only what is named here is kept, as <cache>/nh/sl_nh_law.json with each page's SHA-256; the pages are asked again after
  30 days.

Who is running, from the Secretary of State's own files. www.sos.nh.gov answers scripts with an Akamai "Access Denied"
page (checked again 2026-09-30, one request), which is never worked around, so nothing is requested from it: this loader
reads what John saves from a browser into <cache>/nh/, the folder the federal loader (ballot/lists/nh.py) reads.
  - November: the "2026 General Election Candidates" PDF on sos.nh.gov/2026-election-details, headed "General Election
    Candidates List with Write-ins" (saved as general-election-candidates-list-<date>.pdf; the latest printed copy wins).
    It has two columns only, Candidate Name and Party, under a heading per office, "District No: n" and "Vote for not more
    than n". Read here: Governor, Executive Councilor, State Senator and State Representative (under its county). A row in
    those sections with text anywhere but the name and party columns stops the loader, so a new column (an address, a
    telephone) is never read by accident; other offices' rows are passed over. The list gives no ballot positions (New
    Hampshire prints a column per party and rotates the columns), so ballot_order is left empty. It has no status column:
    a candidate who withdrew is simply not on it. "Vote for not more than" must equal the seats RSA 662:5 gives.
  - Primary: the Democratic and Republican State Primary pages (sos.nh.gov/2026-democratic-state-primary and
    .../2026-republican-state-primary), one Excel workbook per office and party, named 2026-sp-<office>-<party>.xlsx as the
    site names them: governor-summary (by county) and the ten governor-<county> files, executive council and state senate
    by district, state representatives by county (or by district). The workbooks carry votes only. Every column must add up
    to its Totals row; the ten county files, when all are saved, must agree with the Summary. A file whose name is not
    recognised is named in the report and not read. Only 2026-sp-*.xlsx files and the general-election-candidates PDF are
    ever opened: the Secretary's filing lists and winners lists print mailing addresses and are never read.
  The layouts expected are those ballot/lists/nh.py describes from the Secretary's 2024 files; the 2026 files have not been
  seen (none is saved yet), so anything laid out otherwise stops the loader and names the file and the check, never a row.

Privacy. From the list only the office heading, district, name and party are turned into text; from the results only the
heading cells (names and party letters), place names and figures. Nothing else is read, printed, logged, cached or stored.
Before anything is written every stored text is checked for anything that looks like a contact detail, and the load stops
(without showing it) if one does.

Today's holders from the Open States roster in state_nh.sqlite: legislators with is_current = 1 by chamber and district
("Belknap 1" as the roster writes a House district), and the officials table for the Governor. It does not carry the
Executive Council, so no holder is shown there. Only ids, names, parties, chambers and districts are selected; its e-mail,
phone and address columns never are. A candidate is marked incumbent (with state_member_id) only when the name fits a
sitting member of that seat and fits no other member of it, and that member fits no other candidate.

Primaries: a party's field is its candidates named in the results (two or more); another party's name in the file received
write-in votes and counts toward the total, with the Write-Ins column. Percent is of all votes for candidates, write-ins
included (in a district electing several, of all votes cast, each voter having up to that many). Who advanced is the
party's candidate on the November list; until it is saved, the most votes (the number of seats), said so in a note.

    python -m ballot.state_local_nh <database> [--cache <folder holding nh/>] [--no-fetch]
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
from collections import Counter, defaultdict
from urllib.error import HTTPError, URLError

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import openpyxl  # noqa: E402

from ballot.common import CACHE, fold, name_parts, party_code  # noqa: E402
from ballot.lists import nh as NHL  # noqa: E402  the Secretary's file conventions: read_book, check_heading, head_cell, num, place_key, shown, bands
from ballot.match import fits  # noqa: E402
from ballot.pdftext import PDF, join, rows as pdf_rows  # noqa: E402
from states import net  # noqa: E402

STATE, FIPS, NAME = "NH", "33", "New Hampshire"
GENERAL, PRIMARY = "2026-11-03", "2026-09-08"
ROSTER = os.path.join(HERE, "state_nh.sqlite")
RSA = "https://gc.nh.gov/rsa/html/LXIII/"
LAW_PAGES = {"653-1": RSA + "653/653-1.htm", "662-2": RSA + "662/662-2.htm", "662-3": RSA + "662/662-3.htm", "662-5": RSA + "662/662-5.htm"}
COUSUB_URL = "https://www2.census.gov/geo/docs/reference/codes2020/cousub/st33_nh_cousub2020.txt"
KEPT = "sl_nh_law.json"
KEEP_DAYS = 30
COUNTIES = ("Belknap", "Carroll", "Cheshire", "Coos", "Grafton", "Hillsborough", "Merrimack", "Rockingham", "Strafford", "Sullivan")

SRC_GENERAL, SRC_ROSTER, SRC_COUSUB = "nh-sos-2026-sl-general-list", "nh-openstates-roster", "nh-census-2020-cousub"
SRC_LAW = {k: f"nh-rsa-{k}" for k in LAW_PAGES}
PARTIES = {"DEM": ("democratic", "Democratic", "d"), "REP": ("republican", "Republican", "r")}
NONE_HELD_EC = "The Open States roster does not carry the Executive Council, so no holder is shown."
WAITING_NOTE = ("The November candidates are not loaded yet: the Secretary of State's website turns away automated requests, so its "
                "General Election Candidates List waits to be saved from a browser.")
PRIMARY_WAIT = "The September 8, 2026 primary results for this office are not loaded yet."
MOST_VOTES = ("Advanced by the most votes in the results; the November list, which names the nominees, is not saved yet.")
WORDS = "no one two three four five six seven eight nine ten eleven twelve".split()

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

# the last check on every stored text
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[A-Za-z]{2,}")
PHONE = re.compile(r"\(?\b\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}\b")
WEB = re.compile(r"https?://|\bwww\.|\b[\w-]+\.(?:com|org|net|us|gov|edu|info|biz)\b", re.I)
STREET = re.compile(r"\b\d{1,6}\s+(?:[NSEW]\.?\s+)?[A-Za-z0-9.' -]{1,40}?\s(?:St|Street|Ave|Avenue|Rd|Road|Blvd|Boulevard|Dr|Drive|Ln|Lane|"
                    r"Way|Ct|Court|Cir|Circle|Pkwy|Parkway|Hwy|Highway|Trl|Trail|Pl|Place|Ter|Terrace)\b\.?", re.I)
ZIP = re.compile(r"\b[A-Z]{2}\s+\d{5}\b|\b\d{5}-\d{4}\b")


def fail(msg):
    raise SystemExit(f"New Hampshire (state races): {msg}")


def sha_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha_file(path):
    return sha_bytes(open(path, "rb").read()) if path and os.path.exists(path) else ""


def mdate(path):
    return dt.date.fromtimestamp(os.path.getmtime(path)).isoformat() if path and os.path.exists(path) else ""


def number_word(n):
    return WORDS[n] if 0 <= n < len(WORDS) else str(n)


def and_list(items):
    items = list(items)
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1] if items else ""


# ------------------------------------------------------------------------------------------ the law, and the Census's town list

class Blocked(Exception):
    pass


def fetch(url, say=print):
    """One page, asked at most twice more on a refusal or a server error; a bot check is never answered."""
    for attempt in range(3):
        try:
            raw = net.get(url, timeout=90)
        except HTTPError as e:
            if e.code not in (403, 429, 500, 502, 503, 504) or attempt == 2:
                raise
            say(f"      {url}: HTTP {e.code}; asking again in {10 * (attempt + 1)} s")
            time.sleep(10 * (attempt + 1))
            continue
        if re.search(rb"Access Denied|_Incapsula_Resource|cf-chl|challenge-platform|Just a moment", raw[:4000]):
            raise Blocked(f"{url} answered with a bot check")
        time.sleep(0.5)
        return raw
    raise Blocked(url)


TYPE_WORDS = {"town", "city", "township"}      # "location", "grant" and "purchase" stay: Wentworth (a town) and Wentworth's Location differ
ABBR = {"e": "east", "n": "north", "s": "south", "w": "west"}


def town_key(name):
    """A town, ward's city or unincorporated place, spelled the statute's way or the Census's, as one key: "Hale's
    Location" and "Hale's location", "Bean's Grant" and "Beans grant", "E. Kingston" and "East Kingston town"."""
    t = (name or "").lower().replace("&", " and ").replace("’", "'")
    t = re.sub(r"\s+wards?\s+\d+.*$", "", t)
    t = re.sub(r"'s\b", "", t).replace("'", "")
    t = re.sub(r"\b([ensw])\.\s*", lambda m: ABBR[m.group(1)] + " ", t)
    words = re.findall(r"[a-z]+", t)
    while len(words) > 1 and words[-1] in TYPE_WORDS:
        words.pop()
    return " ".join(w[:-1] if w.endswith("s") and len(w) > 3 else w for w in words)


def parse_cousub(raw):
    """{town key: county FIPS (5 digits)} and {county FIPS: county name} from the Census's county subdivision codes."""
    lines = raw.decode("utf-8-sig").splitlines()
    head = lines[0].split("|")
    need = ("STATEFP", "COUNTYFP", "COUNTYNAME", "COUSUBNAME")
    if any(h not in head for h in need):
        fail("the Census county subdivision file's columns have changed")
    ix = {h: head.index(h) for h in need}
    towns, counties = {}, {}
    for line in lines[1:]:
        c = line.split("|")
        if len(c) != len(head) or c[ix["STATEFP"]] != FIPS:
            continue
        name = c[ix["COUSUBNAME"]]
        if re.search(r"not defined", name, re.I):
            continue
        g = FIPS + c[ix["COUNTYFP"]]
        counties[g] = c[ix["COUNTYNAME"]]
        k = town_key(name)
        if k in towns and towns[k] != g:
            fail(f"two county subdivisions share the key {k!r}")
        towns[k] = g
    if len(counties) != 10:
        fail(f"the Census county subdivision file names {len(counties)} counties, not 10")
    return towns, counties


def codesect(raw):
    t = raw.decode("windows-1252", errors="replace")
    a, b = t.find("<codesect>"), t.find("</codesect>")
    if a == -1 or b == -1:
        fail("a statute page no longer has its <codesect> block")
    return t[a:b]


def plain(t):
    return re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", t))).strip()


def parse_653_1(raw):
    """The offices elected at every state general election: the four clauses this loader relies on must be there."""
    t = plain(codesect(raw))
    need = {"I": r"I\. The governor by the voters of the state;",
            "II": r"II\. One executive councilor by the voters in each executive councilor district;",
            "III": r"III\. One state senator by the voters in each senatorial district;",
            "IV": r"IV\. The number of state representatives to which a district is entitled by the voters in such state representative district;"}
    if not re.search(r"At every state general election, the following officers shall be elected for 2-year terms", t):
        fail("RSA 653:1 no longer opens as expected; read it again")
    missing = [k for k, p in need.items() if not re.search(p, t)]
    if missing:
        fail(f"RSA 653:1 no longer has clause(s) {', '.join(missing)} as expected; read it again")
    return {"clauses": list(need)}


def town_list(text):
    """"Albany, Alexandria, ... and Wolfeboro" -> the places; "wards 1, 2, and 5 in Nashua" -> Nashua (for its county)."""
    t = re.sub(r"^the\s+.*?\bof\s+", "", text.strip())
    t = re.sub(r"\bwards?\s+[\d,\s]+(?:and\s+\d+\s*)?in\s+", "", t)
    t = t.rstrip(". ")
    return [re.sub(r"^and\s+", "", x.strip()) for x in t.split(",") if re.sub(r"^and\s+", "", x.strip())]


def parse_districts(raw, word, expect, towns):
    """RSA 662:2 (councilor) or 662:3 (senatorial): {district: sorted county FIPS}."""
    body = plain(codesect(raw))
    if not re.search(rf"divided into {expect} districts", body):
        fail(f"the statute no longer divides the state into {expect} {word.lower()} districts")
    out = {}
    for m in re.finditer(rf"[IVXL]+\.\s*{word} district number (\d+) is constituted of (.*?)(?=\s[IVXL]+\.\s*{word} district number|$)", body):
        d = int(m.group(1))
        places = town_list(m.group(2))
        bad = [p for p in places if town_key(p) not in towns]
        if bad:
            fail(f"{word} district {d} names a place the Census list does not have: {bad}")
        out[str(d)] = sorted({towns[town_key(p)] for p in places})
    if sorted(map(int, out)) != list(range(1, expect + 1)):
        fail(f"{len(out)} {word.lower()} districts read, not {expect}")
    return out


def parse_662_5(raw, towns, counties):
    """[{county, n, seats, towns, fips}] from RSA 662:5, with the table's slips read as the printed districts show."""
    body = codesect(raw)
    names = {v: k for k, v in counties.items()}
    out, county, slips = [], None, []
    for roman, cname, table in re.findall(r"([IVXL]+)\.\s*([A-Za-z]+) County|<table>(.*?)</table>", body, re.S):
        if cname:
            if cname not in COUNTIES:
                fail(f"RSA 662:5 names a county this loader does not know ({cname})")
            county = cname
            continue
        if county is None:
            fail("RSA 662:5 has a table before its first county")
        cur = None
        for tr in re.findall(r"<tr>(.*?)</tr>", table, re.S):
            cells = [plain(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
            if not 2 <= len(cells) <= 3:
                fail(f"RSA 662:5, {county} County: a table row with {len(cells)} cells")
            d, town, n = (cells + [""])[:3]
            if d:
                m = re.fullmatch(r"District No\. (\d+)", d)
                if not m:
                    fail(f"RSA 662:5, {county} County: a district cell that is not read ({d!r})")
                cur = {"county": county, "n": int(m.group(1)), "rows": []}
                out.append(cur)
            if cur is None:
                fail(f"RSA 662:5, {county} County: a row before the first district")
            cur["rows"].append([town, n])
    for c in out:
        rows = c["rows"]
        if not rows[-1][1]:                                      # "Ossipee 1": the count printed in the town's cell
            m = re.fullmatch(r"(.*\D)\s+(\d+)", rows[-1][0])
            if not m or re.search(r"Ward$", m.group(1)):
                fail(f"RSA 662:5, {c['county']} District {c['n']}: no number of representatives")
            rows[-1] = [m.group(1), m.group(2)]
            slips.append(f"{c['county']} {c['n']}: count in the town cell")
        places, i = [], 0
        while i < len(rows):
            town, n = rows[i]
            if i < len(rows) - 1 and n:                          # "Laconia Ward | 1": a ward's number in the count's cell
                if not (town.endswith("Ward") and n.isdigit()):
                    fail(f"RSA 662:5, {c['county']} District {c['n']}: a count before the district's last row")
                town = f"{town} {n}"
                slips.append(f"{c['county']} {c['n']}: ward number in the count cell")
            if town.endswith(" and") and i < len(rows) - 1:      # "Thompson and" / "Meserve's Purchase": one place on two rows
                town = f"{town} {rows[i + 1][0]}"
                if i + 1 == len(rows) - 1:
                    n = rows[i + 1][1]
                i += 1
            if re.search(r"Ward$", town):
                fail(f"RSA 662:5, {c['county']} District {c['n']}: a ward with no number")
            places.append(town)
            i += 1
        seats = rows[-1][1]
        if not seats.isdigit() or not 1 <= int(seats) <= 12:
            fail(f"RSA 662:5, {c['county']} District {c['n']}: a number of representatives that is not read ({seats!r})")
        g = names.get(f"{c['county']} County")
        for p in places:
            k = town_key(p)
            if k not in towns:
                fail(f"RSA 662:5, {c['county']} District {c['n']}: a place the Census list does not have ({p})")
            if towns[k] != g:
                fail(f"RSA 662:5 files {p} under {c['county']} County; the Census list does not")
        c.update(seats=int(seats), towns=places, fips=g)
        del c["rows"]
    keys = [(c["county"], c["n"]) for c in out]
    if len(keys) != len(set(keys)):
        fail("RSA 662:5 lists a district twice")
    for cty in COUNTIES:
        ns = sorted(n for k, n in keys if k == cty)
        if ns != list(range(1, len(ns) + 1)):
            fail(f"RSA 662:5, {cty} County: districts not numbered 1 to {len(ns)}")
    # floterial districts: their towns are exactly those of two or more other districts of the county
    for c in out:
        mine = set(c["towns"])
        subs = [o["n"] for o in out if o["county"] == c["county"] and o is not c and set(o["towns"]) < mine]
        if len(subs) >= 2 and set().union(*[set(o["towns"]) for o in out if o["county"] == c["county"] and o["n"] in subs]) == mine:
            c["floterial"] = sorted(subs)
    return out, slips


def law(folder, say=print, fetch_ok=True):
    """The statutes and the town list, read afresh every 30 days (or kept when the sites cannot be reached)."""
    path = os.path.join(folder, KEPT)
    kept = None
    if os.path.exists(path):
        try:
            kept = json.load(open(path, encoding="utf-8"))
        except ValueError:
            kept = None
    fresh = kept and (dt.date.today() - dt.date.fromisoformat(kept["fetched"])).days < KEEP_DAYS
    if kept and (fresh or not fetch_ok):
        return kept, "kept from " + kept["fetched"]
    if not fetch_ok:
        fail(f"no kept copy of the statutes ({path}); run without --no-fetch once")
    try:
        net.patient_lookups()
        raw = {k: fetch(u, say) for k, u in LAW_PAGES.items()}
        cousub = fetch(COUSUB_URL, say)
    except (Blocked, HTTPError, URLError, OSError) as e:
        if kept:
            say(f"      the statutes could not be read afresh ({e}); using the copy kept on {kept['fetched']}")
            return kept, "kept from " + kept["fetched"] + " (refresh failed)"
        raise
    towns, counties = parse_cousub(cousub)
    parse_653_1(raw["653-1"])
    council = parse_districts(raw["662-2"], "Councilor", 5, towns)
    senate = parse_districts(raw["662-3"], "Senatorial", 24, towns)
    house, slips = parse_662_5(raw["662-5"], towns, counties)
    out = {"fetched": dt.date.today().isoformat(),
           "pages": {k: {"url": u, "sha256": sha_bytes(raw[k])} for k, u in LAW_PAGES.items()},
           "cousub": {"url": COUSUB_URL, "sha256": sha_bytes(cousub), "places": len(towns)},
           "counties": counties, "council": council, "senate": senate, "house": house, "slips": slips}
    os.makedirs(folder, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    return out, "read afresh"


# ------------------------------------------------------------------------------------------ the roster

def roster(path=ROSTER):
    """Sitting legislators by (chamber, district) and the Governor. Ids, names, parties, chambers and districts only."""
    if not os.path.exists(path):
        fail(f"{os.path.basename(path)} is missing; run python run_states.py nh people")
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    members = defaultdict(list)
    for mid, full, first, last, party, district, chamber in con.execute(
            "SELECT bioguide_id, official_full, first_name, last_name, party_name, district, chamber FROM legislators WHERE is_current = 1"):
        members[(chamber, str(district).strip())].append(dict(id=mid, name=full or f"{first} {last}", first=first, last=last, party=party or ""))
    officials = {}
    for oid, full, office, party in con.execute("SELECT bioguide_id, official_full, office, party_name FROM officials"):
        officials[office] = dict(id=oid, name=full, party=party or "")
    con.close()
    return members, officials


def member_parts(m):
    g, f = name_parts(m["name"])
    if m.get("last"):
        f = fold(m["last"])
        g = fold(m.get("first") or "").split() or g
    return g, f


def incumbents(names, members):
    """{candidate name: member}: a member whose name fits exactly one candidate, that candidate fitting no other member."""
    hits = defaultdict(list)
    for m in members:
        mp = member_parts(m)
        fit = [n for n in names if fits(name_parts(n), mp)]
        if len(fit) == 1:
            hits[fit[0]].append(m)
    return {n: ms[0] for n, ms in hits.items() if len(ms) == 1}


# ------------------------------------------------------------------------------------------ the November list

SECTION = [(re.compile(r"Governor", re.I), "GOV"), (re.compile(r"Executive Council(?:or|lor)?s?", re.I), "EC"),
           (re.compile(r"State Senators?", re.I), "SS"), (re.compile(r"State Representatives?(?:\s*[-–]?\s*Floterial)?", re.I), "SH")]
REP_WITH_COUNTY = re.compile(r"State Representatives?\s*(?:[-–:,]\s*|\s)(" + "|".join(COUNTIES) + r")(?:\s+County)?(?:\s*[-–]?\s*Floterial)?", re.I)
COUNTY_LINE = re.compile(r"(" + "|".join(COUNTIES) + r")(?:\s+County)?", re.I)
DISTRICT_LINE = re.compile(r"(?:(" + "|".join(COUNTIES) + r")(?:\s+County)?\s*[-,]?\s*)?District\s+No\.?\s*:?\s*(\d{1,2})\s*(?:\(F\)|F|Floterial)?", re.I)
VOTE_FOR = re.compile(r"Vote for not more than\s*(\d{1,2})", re.I)
OTHER_OFFICE = re.compile(r"(President\b.*|United States Senator|U\.?\s?S\.? Senator|Representative in Congress|Sheriff|County Attorney|"
                          r"County Treasurer|Register of Deeds|Register of Probate|County Commissioner.*|Delegate\b.*|Question\b.*|"
                          r"Constitutional Amendment.*)", re.I)
WI_MARK = re.compile(r"\s*\((?:w|w/i|write[- ]?in)\)\s*$|\s+[-–]\s*write[- ]?in\s*$", re.I)


def read_general(path):
    """{race key: [(name as printed, party, write-in mark)]}, the vote-for figures read, the date printed, other rows passed over."""
    data = open(path, "rb").read()
    if data[:4] != b"%PDF":
        fail(f"{os.path.basename(path)} is not a PDF")
    pdf = PDF(re.sub(rb"stream[ \t]+\r\n", b"stream\r\n", data))      # the report writer puts a space after "stream"
    out, vote_for_read, other = defaultdict(list), {}, 0
    seen_title = seen_election = False
    printed = ""
    section = county = district = vote_for = None
    for n, (page, res) in enumerate(pdf.pages(), 1):
        for _y, runs in pdf_rows(pdf, page, res):
            left = join([r for r in runs if r[0] < NHL.NAME_BAND])
            right = join([r for r in runs if NHL.NAME_BAND <= r[0] < NHL.PARTY_BAND])
            beyond = [r for r in runs if r[0] >= NHL.PARTY_BAND]
            whole = join(runs) if not left or NHL.FURNITURE.search(left) else left
            if NHL.FURNITURE.search(whole):
                seen_title |= "General Election Candidates List" in whole
                if re.search(r"Election\s*:", whole):
                    if not NHL.ELECTION_LINE.search(whole):
                        fail(f"{os.path.basename(path)} is not the November 3, 2026 list")
                    seen_election = True
                m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4}) \d{1,2}:\d\d", whole)
                if m and not printed:
                    printed = f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
                continue
            if left == "Candidate Name" and right == "Party" and not beyond:
                continue
            state = section in ("GOV", "EC", "SS", "SH")
            if beyond:
                if state:
                    fail(f"{os.path.basename(path)}: a row of the {section} section on page {n} has text beyond the name and party columns")
                other += 1
                continue
            if not left:
                continue
            if not right:                                        # a heading line
                if any(p.fullmatch(left) for p, _k in SECTION):
                    section = next(k for p, k in SECTION if p.fullmatch(left))
                    county = district = vote_for = None
                elif REP_WITH_COUNTY.fullmatch(left):
                    section, county = "SH", REP_WITH_COUNTY.fullmatch(left).group(1).title()
                    district = vote_for = None
                elif OTHER_OFFICE.fullmatch(left):
                    section, county, district, vote_for = "other", None, None, None
                elif COUNTY_LINE.fullmatch(left):
                    county, district, vote_for = COUNTY_LINE.fullmatch(left).group(1).title(), None, None
                elif DISTRICT_LINE.fullmatch(left):
                    m = DISTRICT_LINE.fullmatch(left)
                    if m.group(1):
                        county = m.group(1).title()
                    district, vote_for = int(m.group(2)), None
                elif VOTE_FOR.fullmatch(left):
                    vote_for = int(VOTE_FOR.fullmatch(left).group(1))
                elif state:
                    fail(f"{os.path.basename(path)}: a line in the {section} section on page {n} that is not read (length {len(left)})")
                continue
            if not state:
                other += 1
                continue
            if section == "GOV":
                key = "GOV"
            elif section == "EC":
                key = f"EC{district}" if district and 1 <= district <= 5 else None
            elif section == "SS":
                key = f"SS{district}" if district and 1 <= district <= 24 else None
            else:
                key = ("SH", county, district) if county and district else None
            if key is None:
                fail(f"{os.path.basename(path)}: a {section} candidate on page {n} before the district is named")
            if vote_for is None:
                fail(f"{os.path.basename(path)}: a {section} candidate on page {n} before \"Vote for not more than\"")
            vote_for_read[key] = vote_for
            name, party = left, right
            mark = bool(WI_MARK.search(name) or WI_MARK.search(party))
            name, party = WI_MARK.sub("", name).strip(), WI_MARK.sub("", party).strip()
            if re.search(r"write", name + " " + party, re.I):
                fail(f"{os.path.basename(path)}: a {section} row on page {n} mentions a write-in in a way this loader does not read")
            if any(fold(name) == fold(x) for x, _p, _w in out[key]):
                fail(f"{os.path.basename(path)}: a candidate is listed twice in one {section} race (page {n})")
            out[key].append((name, party, mark))
    if not seen_title or not seen_election:
        fail(f"{os.path.basename(path)} is not headed as the General Election Candidates List for November 3, 2026")
    return dict(out), vote_for_read, printed, other


# ------------------------------------------------------------------------------------------ the primary results

PRI_FILE = re.compile(r"^2026-sp-(?P<stem>.+?)-(?P<party>democratic|republican)(?P<copy>_\d+)?(?: ?\(\d+\))?\.xlsx$", re.I)
FEDERAL_STEM = re.compile(r"^(us-senator|congressional-district)", re.I)
COUNTY_OFFICE_STEM = re.compile(r"sheriff|county-attorney|county-treasurer|register|commissioner|delegate", re.I)
CTY = "|".join(c.lower() for c in COUNTIES)


def classify_stem(stem):
    s = stem.lower()
    if re.fullmatch(r"governor-summary", s):
        return ("GOV", "summary")
    m = re.fullmatch(rf"governor-({CTY})", s)
    if m:
        return ("GOV", m.group(1).title())
    m = re.fullmatch(r"(?:executive-)?council(?:or|lor)?s?(?:-district)?-(?:no-?)?(\d)", s)
    if m and 1 <= int(m.group(1)) <= 5:
        return ("EC", int(m.group(1)))
    m = re.fullmatch(r"(?:state-)?senat(?:e|or)s?(?:-district)?-(?:no-?)?(\d{1,2})", s)
    if m and 1 <= int(m.group(1)) <= 24:
        return ("SS", int(m.group(1)))
    m = re.fullmatch(rf"(?:state-)?rep(?:resentatives?|s)?-({CTY})(?:-(?:district-)?(?:no-?)?(\d{{1,2}}))?", s)
    if m:
        return ("SH", m.group(1).title(), int(m.group(2)) if m.group(2) else None)
    return None


def primary_files(folder):
    """{(stem, party): path} for the saved 2026-sp-*.xlsx files this loader reads, and the names of those it does not."""
    groups, skipped = defaultdict(list), []
    for f in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
        m = PRI_FILE.match(f)
        if not m:
            if re.match(r"^2026-sp-", f, re.I) and not f.lower().endswith(".xlsx"):
                skipped.append(f"{f} (only the Excel version is read)")
            continue
        if FEDERAL_STEM.match(m.group("stem")):
            continue
        groups[(m.group("stem").lower(), m.group("party").lower())].append(f)
    out = {}
    for (stem, party), fs in groups.items():
        if len(fs) > 1:
            fail(f"{len(fs)} saved copies of 2026-sp-{stem}-{party} in {folder} ({', '.join(fs)}); keep the newest only")
        kind = classify_stem(stem)
        if kind is None:
            skipped.append(f"{fs[0]} ({'a county office, for the county pages' if COUNTY_OFFICE_STEM.search(stem) else 'name not recognised'})")
            continue
        out[(kind, party)] = os.path.join(folder, fs[0])
    return out, skipped


def read_contests(path, what):
    """A results sheet with a block per district (the state representative files by county): [(title, tally)], the file's title.
    Each block: title rows, a heading row of candidates, place rows, a Totals row; a block with no title of its own that lists
    the same places continues the one before (columns wrapped). Every column must add up to its Totals row."""
    with open(path, "rb") as fh:
        if fh.read(2) != b"PK":
            fail(f"{os.path.basename(path)} is not an Excel workbook (.xlsx)")
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        if len(wb.worksheets) != 1:
            fail(f"{what} has {len(wb.worksheets)} sheets; one was expected")
        sheet = [list(r) for r in wb.worksheets[0].iter_rows(values_only=True)]
    finally:
        wb.close()
    head_rows, pending, contests, dates, cur = [], [], [], [], None
    for r in sheet:
        while r and (r[-1] is None or (isinstance(r[-1], str) and not r[-1].strip())):
            r.pop()
        if not r:
            continue
        for c in r:
            if isinstance(c, (dt.datetime, dt.date)):
                dates.append(c.date() if isinstance(c, dt.datetime) else c)
        label, vals = r[0], r[1:]
        text = str(label).strip() if label is not None and not isinstance(label, (dt.datetime, dt.date)) else ""
        heads = [NHL.head_cell(c) for c in vals]
        if any(h and h[0] == "cand" for h in heads):
            bad = [h[1] for h in heads if h and h[0] == "?"]
            if bad:
                fail(f"{what}: {len(bad)} heading cell(s) that are not read")
            if cur and cur["total"] is None:
                fail(f"{what}: a block with no Totals row")
            title = " ".join(pending + ([text] if text else []))
            if not contests:
                head_rows = list(pending)
            pending = []
            cur = {"heads": heads, "rows": [], "since": [], "total": None}
            if contests and (not title or title == contests[-1]["title"]):
                contests[-1]["blocks"].append(cur)
            else:
                contests.append({"title": title, "blocks": [cur], "notes": []})
            continue
        figures = [v for v in vals if v is not None and not (isinstance(v, str) and not v.strip())]
        if cur is None or cur["total"] is not None:
            if figures:
                fail(f"{what}: figures outside a block")
            if text:
                if contests and re.match(r"^\*|correction", text, re.I):
                    contests[-1]["notes"].append(text)
                else:
                    pending.append(text)
            continue
        if re.fullmatch(r"(grand |state |district )?totals?", text, re.I):
            cur["total"] = vals
            continue
        if not text:
            if figures:
                fail(f"{what}: a row of figures with no place")
            continue
        if re.search(r"\btotals?$", text, re.I):
            width = max([len(vals)] + [len(v) for _p, v in cur["since"]])
            for i in range(width):
                got = sum(NHL.num(v[i] if i < len(v) else None, what) for _p, v in cur["since"])
                if got != NHL.num(vals[i] if i < len(vals) else None, what):
                    fail(f"{what}: a subtotal does not add up")
            cur["since"] = []
            continue
        cur["rows"].append((text, vals))
        cur["since"].append((text, vals))
    if not contests or contests[-1]["blocks"][-1]["total"] is None:
        fail(f"{what}: no candidates' heading row and Totals row were found")
    return [(c["title"], tally(c["blocks"], what), c["notes"]) for c in contests], " ".join(head_rows), sorted(set(dates))


def tally(blocks, what):
    """Candidates' totals, write-ins, over- and undervotes of one contest's blocks, every column checked."""
    cands, write_ins, over, under, places = {}, 0, 0, 0, None
    for b in blocks:
        width = max([len(b["heads"]), len(b["total"])] + [len(v) for _p, v in b["rows"]])
        heads = b["heads"] + [None] * (width - len(b["heads"]))
        for i, h in enumerate(heads):
            col = [NHL.num(v[i] if i < len(v) else None, what) for _p, v in b["rows"]]
            tot = NHL.num(b["total"][i] if i < len(b["total"]) else None, what)
            if h is None:
                if any(col) or tot:
                    fail(f"{what}: figures under a blank heading")
                continue
            if sum(col) != tot:
                fail(f"{what}: a column does not add up to its Totals row ({sum(col)} against {tot})")
            if h[0] == "cand":
                key = (h[1], h[2])
                if key in cands:
                    fail(f"{what}: one candidate has two columns")
                cands[key] = tot
            elif h[0] == "wi":
                write_ins += tot
            elif h[0] == "over":
                over += tot
            else:
                under += tot
        ps = sorted(NHL.place_key(p) for p, _v in b["rows"])
        if places is None:
            places = ps
        elif ps != places:
            fail(f"{what}: the blocks of one contest list different places")
    return {"cands": cands, "write_ins": write_ins, "over": over, "under": under, "places": places or []}


def check_title(title, dates, what, party_word, office, county=None):
    NHL.check_heading({"title": title, "dates": dates}, what, party_word, office)
    if county and county.lower() not in title.lower():
        fail(f"{what} does not name {county} County in its heading")


def district_in(title):
    m = re.search(r"District\s*(?:No\.?)?\s*(\d{1,2})\b", title, re.I)
    return int(m.group(1)) if m else None


def read_primaries(folder, house, say):
    """{(race key, party code): {"cands", "write_ins", "file", "files", "what"}}, files read, files skipped."""
    files, skipped = primary_files(folder)
    out, used = {}, []
    code_of = {v[0]: k for k, v in PARTIES.items()}
    seats_of = {(h["county"], h["n"]) for h in house}
    # the Governor: the Summary (by county), and the ten county files when all are saved
    for word in ("democratic", "republican"):
        code = code_of[word]
        summ = files.get((("GOV", "summary"), word))
        ctys = {c: files[(("GOV", c), word)] for c in COUNTIES if (("GOV", c), word) in files}
        if ctys and len(ctys) != 10:
            fail(f"{len(ctys)} of the ten Governor county files for the {word.title()} primary are saved; save all ten, or none")
        books = {}
        for c, p in ctys.items():
            b = NHL.read_book(p, os.path.basename(p))
            check_title(b["title"], b["dates"], os.path.basename(p), word, r"governor", c)
            books[c] = b
        if summ:
            s = NHL.read_book(summ, os.path.basename(summ))
            check_title(s["title"], s["dates"], os.path.basename(summ), word, r"governor")
            if sorted(s["places"]) != sorted(fold(c) for c in COUNTIES):
                fail(f"{os.path.basename(summ)} does not list the ten counties")
            for c, b in books.items():
                for k, v in b["cands"].items():
                    if k not in s["cands"] or s["cands"][k]["by_place"].get(fold(c)) != v["votes"]:
                        fail(f"the {word.title()} Governor Summary and the {c} County file disagree")
                if s["has_wi"] and s["wi_by_place"].get(fold(c), 0) != b["write_ins"]:
                    fail(f"{c} County's Governor write-ins differ between the county file and the Summary")
            cands = {k: v["votes"] for k, v in s["cands"].items()}
            wi = s["write_ins"] if s["has_wi"] or not books else sum(b["write_ins"] for b in books.values())
            out[("GOV", code)] = {"cands": cands, "write_ins": wi, "files": [summ] + [ctys[c] for c in COUNTIES if c in ctys],
                                  "what": "Governor, Summary (by county)" + (", with the ten county files (by town)" if books else "")}
        elif books:
            names = {k for b in books.values() for k in b["cands"]}
            out[("GOV", code)] = {"cands": {k: sum(b["cands"].get(k, {"votes": 0})["votes"] for b in books.values()) for k in names},
                                  "write_ins": sum(b["write_ins"] for b in books.values()), "files": [ctys[c] for c in COUNTIES],
                                  "what": "Governor, the ten county files (by town), summed"}
    for (kind, word), path in sorted(files.items(), key=lambda kv: str(kv[0])):
        code, what = code_of[word], os.path.basename(path)
        if kind[0] == "GOV":
            continue
        if kind[0] in ("EC", "SS"):
            d = kind[1]
            b = NHL.read_book(path, what)
            office = (r"council\w*\W+(?:district\W+)?(?:no\.?\s*)?" if kind[0] == "EC" else r"senat\w*\W+(?:district\W+)?(?:no\.?\s*)?") + rf"{d}\b"
            check_title(b["title"], b["dates"], what, word, office)
            key = f"{kind[0]}{d}"
            if (key, code) in out:
                fail(f"two saved files give the {word.title()} primary for {key}")
            out[(key, code)] = {"cands": {k: v["votes"] for k, v in b["cands"].items()}, "write_ins": b["write_ins"], "files": [path],
                                "what": ("Executive Councilor" if kind[0] == "EC" else "State Senator") + f", District No. {d}"}
            continue
        _k, county, d = kind
        if d is not None:
            b = NHL.read_book(path, what)
            check_title(b["title"], b["dates"], what, word, rf"district\W+(?:no\.?\s*)?{d}\b", county)
            got = [(d, {"cands": {k: v["votes"] for k, v in b["cands"].items()}, "write_ins": b["write_ins"]})]
        else:
            contests, head, dates = read_contests(path, what)
            check_title(head + " " + " ".join(t for t, _b, _n in contests), dates, what, word, r"representative", county)
            got = []
            for title, t, _notes in contests:
                dn = district_in(title)
                if dn is None:
                    fail(f"{what}: a block whose heading names no district")
                got.append((dn, t))
        for dn, t in got:
            if (county, dn) not in seats_of:
                fail(f"{what}: {county} District {dn} is not a district of RSA 662:5")
            key = ("SH", county, dn)
            if (key, code) in out:
                fail(f"{what}: {county} District {dn} is given twice for the {word.title()} primary")
            out[(key, code)] = {"cands": t["cands"], "write_ins": t["write_ins"], "files": [path],
                                "what": f"State Representative, {county} County" + (f", District No. {d}" if d else " (every district)")}
        used.append(path)
    used = sorted({p for v in out.values() for p in v["files"]})
    return out, used, skipped


# ------------------------------------------------------------------------------------------ the loader

def guard(races, cands, places):
    """Stops (without showing the text) if anything about to be stored looks like a contact detail."""
    texts = [(r["race_id"], v) for r in races.values() for v in (r["office"], r["jurisdiction"], r["holder_name"], r["note"])]
    texts += [(c[0], v) for c in cands for v in (c[3], c[4], c[14])]
    texts += [(p[1], p[2]) for p in places]
    for rid, v in texts:
        if v and (EMAIL.search(v) or PHONE.search(v) or WEB.search(v) or STREET.search(v) or ZIP.search(v)):
            fail(f"a stored text for {rid} looks like a contact detail; nothing was written")


def load(db_path, say=print, cache=CACHE, fetch_ok=True, roster_path=ROSTER):
    folder = os.path.join(cache, "nh")
    os.makedirs(folder, exist_ok=True)
    L, law_how = law(folder, say, fetch_ok)
    counties = L["counties"]
    fips_of = {v.replace(" County", ""): k for k, v in counties.items()}
    members, officials = roster(roster_path)
    report = []

    # ---- the races the law puts on the 2026 ballot
    races = {}

    def race(key, **kw):
        rid = f"2026-{STATE}-{key}"
        races[rid] = dict(race_id=rid, state=STATE, special=0, partisan=1, holder_id=None, holder_name=None, holder_party=None,
                          election_date=GENERAL, seat=None, _note=[], _members=[], _seats=1, **kw)
        return races[rid]

    gov = officials.get("governor")
    r = race("GOV", level="statewide", office_kind="governor", office="Governor", jurisdiction=NAME, jurisdiction_id=FIPS, county_ids=None,
             district=None)
    r["_note"].append("New Hampshire elects its governor every two years (RSA 653:1, I); the law names no other office elected by the voters "
                      "of the whole state.")
    if gov:
        r.update(holder_id=gov["id"], holder_name=gov["name"], holder_party=gov["party"])
        r["_members"] = [gov]
    for d in range(1, 6):
        r = race(f"EC{d}", level="statewide", office_kind="executive_council", office="Executive Councilor",
                 jurisdiction=f"Executive Council District {d}", jurisdiction_id=f"{STATE}-{d}", county_ids=json.dumps(L["council"][str(d)]),
                 district=str(d))
        r["_note"] += ["One of the five executive councilors, each elected by the voters of a councilor district for a two-year term "
                       "(RSA 653:1, II; the districts are set out in RSA 662:2).", NONE_HELD_EC]
    for d in range(1, 25):
        r = race(f"SS{d}", level="legislature", office_kind="state_senate", office="State Senator", jurisdiction=f"Senate District {d}",
                 jurisdiction_id=f"{STATE}-{d}", county_ids=json.dumps(L["senate"][str(d)]), district=str(d))
        r["_note"].append("All 24 senators are elected every two years, one in each senatorial district (RSA 653:1, III; RSA 662:3).")
        sitting = members.get(("Senate", str(d)), [])
        if len(sitting) > 1:
            report.append(f"{r['race_id']}: {len(sitting)} sitting senators on the roster")
        if sitting:
            r.update(holder_id=sitting[0]["id"], holder_name=sitting[0]["name"], holder_party=sitting[0]["party"])
        else:
            r["_note"].append("The roster used here lists nobody in this seat today.")
        r["_members"] = sitting
    house_key = {}
    for h in L["house"]:
        dname = f"{h['county']} {h['n']}"
        r = race(f"SH{h['county']}{h['n']}", level="legislature", office_kind="state_house", office="State Representative",
                 jurisdiction=f"{h['county']} County, District {h['n']}", jurisdiction_id=f"{STATE}-{dname}", county_ids=json.dumps([h["fips"]]),
                 district=dname)
        house_key[(h["county"], h["n"])] = r["race_id"]
        n = h["seats"]
        r["_seats"] = n
        r["_note"].append(f"Elect {n}. The district elects {number_word(n)} representative{'s' if n > 1 else ''} (RSA 662:5)"
                          + (f", the {number_word(n)} candidates with the most votes" if n > 1 else "") + f"; it is made up of "
                          f"{and_list(h['towns'])}.")
        if h.get("floterial"):
            r["_note"].append(f"A floterial district: its towns and wards are those of Districts {and_list([str(x) for x in h['floterial']])} of "
                              f"{h['county']} County, so their voters elect representatives in both.")
        sitting = members.get(("House", dname), [])
        if sitting:
            r.update(holder_id="; ".join(m["id"] for m in sitting), holder_name="; ".join(m["name"] for m in sitting),
                     holder_party="; ".join(m["party"] for m in sitting))
        if len(sitting) != n:
            r["_note"].append(f"The roster used here lists {number_word(len(sitting))} member{'s' if len(sitting) != 1 else ''} for the "
                              f"district's {number_word(n)} seat{'s' if n != 1 else ''}.")
        if len(sitting) > n:
            report.append(f"{r['race_id']}: {len(sitting)} sitting members on the roster for {n} seats")
        r["_members"] = sitting
    known = {(ch, d) for ch, d in members}
    stray = sorted(d for ch, d in known if ch == "House" and not any(r["district"] == d for r in races.values() if r["office_kind"] == "state_house"))
    stray += sorted(d for ch, d in known if ch == "Senate" and not (d.isdigit() and 1 <= int(d) <= 24))
    if stray:
        report.append(f"roster districts that are not districts of the law: {stray}")

    # ---- the November list
    lists = sorted(f for f in os.listdir(folder) if NHL.GENERAL_FILE.search(f))
    general, printed, gpath, vote_for, passed = None, "", None, {}, 0
    for f in lists:
        got, vf, when, other = read_general(os.path.join(folder, f))
        if general is None or when > printed:
            general, vote_for, printed, gpath, passed = got, vf, when, os.path.join(folder, f), other
    cands = []                 # [race, election, date, name, party, code, order, incumbent, write_in, votes, pct, outcome, member, source, note]
    nominees = defaultdict(list)
    if general is not None:
        for key, rows in general.items():
            if isinstance(key, tuple):
                rid = house_key.get((key[1], key[2]))
                if rid is None:
                    report.append(f"the November list has State Representative {key[1]} District {key[2]}, which RSA 662:5 does not")
                    continue
            else:
                rid = f"2026-{STATE}-{key}"
            r = races[rid]
            if vote_for.get(key) != r["_seats"]:
                report.append(f"{rid}: the list says vote for {vote_for.get(key)}, RSA 662:5 gives {r['_seats']} seat(s)")
            inc = incumbents([NHL.shown(n, None)[0] for n, _p, _w in rows], r["_members"])
            for name_printed, party, mark in rows:
                name, caps = NHL.shown(name_printed, "The Secretary of State's list prints this name in capitals; it is shown in ordinary capitals.")
                m = inc.get(name)
                note = " ".join(x for x in (caps, "Marked as a write-in on the Secretary of State's list." if mark else None) if x) or None
                cands.append([rid, "general", GENERAL, name, party, party_code(party), None, 1 if m else 0, 1 if mark else 0, None, None, None,
                              m["id"] if m else None, SRC_GENERAL, note])
                for code, (_w, label, _l) in PARTIES.items():
                    if party.lower() == label.lower():
                        nominees[(rid, code)].append(name)
    else:
        for r in races.values():
            r["_note"].append(WAITING_NOTE)

    # ---- the primaries
    prim, used, skipped = read_primaries(folder, L["house"], say)
    fields, single = 0, []
    have_office = defaultdict(set)
    for (key, code), p in prim.items():
        rid = house_key[(key[1], key[2])] if isinstance(key, tuple) else f"2026-{STATE}-{key}"
        have_office[rid].add(code)
        r = races[rid]
        word, label, letter = PARTIES[code]
        field = [(n, v) for (n, l), v in p["cands"].items() if l == letter]
        others = sum(v for (_n, l), v in p["cands"].items() if l != letter)
        total = sum(v for _n, v in field) + others + p["write_ins"]
        if len(field) < 2:
            single.append(f"{rid} {label}")
            continue
        fields += 1
        seats = r["_seats"]
        order = sorted(field, key=lambda nv: -nv[1])
        won, note_all = set(), None
        if general is not None:
            listed = nominees.get((rid, code), [])
            for n, _v in field:
                if any(fold(NHL.shown(n, None)[0]) == fold(x) or fits(name_parts(NHL.shown(n, None)[0]), name_parts(x)) for x in listed):
                    won.add(n)
            missing = [x for x in listed if not any(fits(name_parts(NHL.shown(n, None)[0]), name_parts(x)) for n, _v in field)]
            if missing:
                report.append(f"{rid} {label} primary: {len(missing)} {label} candidate(s) on the November list not among the named "
                              "candidates in the results (nominated by write-ins not named, or another way)")
        else:
            if len(order) > seats and order[seats - 1][1] == order[seats][1]:
                report.append(f"{rid} {label} primary: a tie at the last place that advances; read how it was settled")
            else:
                won = {n for n, _v in order[:seats]}
                note_all = MOST_VOTES
        inc = incumbents([NHL.shown(n, None)[0] for n, _v in field], r["_members"])
        src = "nh-sos-2026-sl-primary-" + re.sub(r"[^a-z0-9]+", "-", os.path.basename(p["files"][0]).lower()[8:-5]).strip("-")
        for n, v in order:
            name, caps = NHL.shown(n, "The Secretary of State's results print this name in capitals; it is shown in ordinary capitals.")
            m = inc.get(name)
            outcome = ("advanced" if n in won else "lost") if (won or general is not None) else None
            cands.append([rid, f"primary-{code}", PRIMARY, name, label, party_code(label), None, 1 if m else 0, 0, v,
                          round(100 * v / total, 1) if total else None, outcome, m["id"] if m else None, src,
                          " ".join(x for x in (caps, note_all if n in won else None) if x) or None])
    for rid, r in races.items():
        if len(have_office.get(rid, ())) < 2:
            r["_note"].append(PRIMARY_WAIT if not have_office.get(rid) else
                              f"The {PARTIES[[c for c in PARTIES if c not in have_office[rid]][0]][1]} primary results for this office are not loaded yet.")

    # ---- checks
    keyset = set()
    for c in cands:
        k = (c[0], c[1], c[3])
        if k in keyset:
            fail(f"a name is listed twice in {c[0]} {c[1]}")
        keyset.add(k)
    short, empty = [], []
    if general is not None:
        for rid, r in races.items():
            got = sum(1 for c in cands if c[0] == rid and c[1] == "general")
            if not got:
                empty.append(rid)
            elif got < r["_seats"]:
                short.append(rid)
        read_rows = sum(len(v) for v in general.values())
        stored = sum(1 for c in cands if c[1] == "general")
        if read_rows != stored:
            report.append(f"{read_rows} state rows read from the November list, {stored} stored")
        if empty:
            report.append(f"{len(empty)} race(s) with no candidate on the November list: {', '.join(empty[:20])}{' ...' if len(empty) > 20 else ''}")
    for r in races.values():
        r["note"] = " ".join(x for x in r["_note"] if x) or None

    places = [("county", g, n, json.dumps([g]), SRC_COUSUB) for g, n in sorted(counties.items())]
    places += [("executive_council", f"{STATE}-{d}", f"Executive Council District {d}", json.dumps(L["council"][str(d)]), SRC_LAW["662-2"])
               for d in range(1, 6)]
    places += [("senate", f"{STATE}-{d}", f"Senate District {d}", json.dumps(L["senate"][str(d)]), SRC_LAW["662-3"]) for d in range(1, 25)]
    places += [("house", f"{STATE}-{h['county']} {h['n']}", f"{h['county']} County, District {h['n']}", json.dumps([h["fips"]]), SRC_LAW["662-5"])
               for h in L["house"]]
    guard(races, cands, places)

    pages = L["pages"]
    house_seats = sum(h["seats"] for h in L["house"])
    src = [
        (SRC_LAW["653-1"], STATE, "law", "New Hampshire General Court", "RSA 653:1, Officers Elected at State General Elections",
         pages["653-1"]["url"], "", L["fetched"], pages["653-1"]["sha256"], 4,
         "Which offices are on the ballot: at every state general election, for two-year terms, the governor by the voters of the state, one "
         "executive councilor in each councilor district, one state senator in each senatorial district and the number of state representatives "
         "each district is entitled to (clauses I to IV, each checked on the page). County officers (clause V and after) are for the county pages."),
        (SRC_LAW["662-2"], STATE, "law", "New Hampshire General Court", "RSA 662:2, Councilor Districts", pages["662-2"]["url"], "",
         L["fetched"], pages["662-2"]["sha256"], 5, "The five councilor districts, town by town; each district's counties from the Census list."),
        (SRC_LAW["662-3"], STATE, "law", "New Hampshire General Court", "RSA 662:3, State Senate Districts", pages["662-3"]["url"], "",
         L["fetched"], pages["662-3"]["sha256"], 24, "The 24 senatorial districts, town by town (wards of Manchester and Nashua); each district's "
                                                    "counties from the Census list."),
        (SRC_LAW["662-5"], STATE, "law", "New Hampshire General Court", "RSA 662:5, State Representative Districts", pages["662-5"]["url"], "",
         L["fetched"], pages["662-5"]["sha256"], len(L["house"]),
         f"{len(L['house'])} districts in ten counties electing {house_seats} representatives, with the towns and wards of each. The page is a "
         f"table, and {len(L['slips'])} of its rows print a figure in the neighbouring cell (a count in the town's cell, a ward's number in the "
         f"count's cell); each is read as the district shows it must be. {sum(1 for h in L['house'] if h.get('floterial'))} floterial districts "
         "(towns exactly those of two or more other districts of the county) are named in their notes."),
        (SRC_COUSUB, STATE, "place codes", "U.S. Census Bureau", "2020 county subdivision codes, New Hampshire (st33_nh_cousub2020.txt)",
         COUSUB_URL, "2020", L["fetched"], L["cousub"]["sha256"], L["cousub"]["places"],
         "Every town, city and unincorporated place the statutes name is checked against this list, which gives its county's five-digit code."),
        (SRC_ROSTER, STATE, "roster", "Open States people project (CC0), as loaded into state_nh.sqlite", "Sitting legislators and the Governor",
         "https://github.com/openstates/people", "", mdate(roster_path), sha_file(roster_path),
         sum(len(v) for v in members.values()) + len(officials),
         "Who holds each seat today (ids, names, parties, chambers and districts only); it does not carry the Executive Council. Not an "
         "official record."),
    ]
    if general is not None:
        src.append((SRC_GENERAL, STATE, "official candidate list", "New Hampshire Secretary of State",
                    "General Election Candidates List with Write-ins, 11/03/2026 State General Election: Governor, Executive Councilor, State "
                    "Senator, State Representative", NHL.DETAILS, printed, mdate(gpath), sha_file(gpath),
                    sum(1 for c in cands if c[1] == "general"),
                    f"Saved from a browser ({os.path.basename(gpath)}; the Secretary's site turns away automated downloads). Two columns, Candidate "
                    "Name and Party; only the four state sections read, other offices' rows passed over. The list gives no ballot positions (a "
                    "column per party, rotated), so no ballot order is stored; it has no status column, so a candidate who withdrew is not on it."))
    for path in used:
        base = os.path.basename(path)
        word = "Democratic" if "democratic" in base.lower() else "Republican"
        sid = "nh-sos-2026-sl-primary-" + re.sub(r"[^a-z0-9]+", "-", base.lower()[8:-5]).strip("-")
        what = next((p["what"] for p in prim.values() if path in p["files"]), base)
        src.append((sid, STATE, "official results", "New Hampshire Secretary of State", f"2026 {word} State Primary (September 8, 2026): {what}",
                    NHL.FILES + re.sub(r" \(\d+\)", "", base), "", mdate(path), sha_file(path),
                    sum(1 for c in cands if c[13] == sid),
                    f"Saved from a browser from {NHL.PAGES['DEM' if word == 'Democratic' else 'REP']}. The page says tallies reflect the clerks' "
                    "returns and may change if clerks submit amendments. Every column adds up to its Totals row. Percent is of all votes for "
                    "candidates, write-ins included; overvotes and undervotes left out."))

    cols = ("race_id", "state", "level", "office_kind", "office", "jurisdiction", "jurisdiction_id", "county_ids", "district", "seat", "special",
            "partisan", "holder_id", "holder_name", "holder_party", "election_date", "note")
    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA)
    with con:
        con.execute("DELETE FROM sl_candidates WHERE race_id IN (SELECT race_id FROM sl_races WHERE state = ?)", (STATE,))
        con.execute("DELETE FROM sl_candidates WHERE race_id LIKE ?", (f"2026-{STATE}-%",))
        con.execute("DELETE FROM sl_races WHERE state = ?", (STATE,))
        con.execute("DELETE FROM sl_places WHERE source_id LIKE ?", (STATE.lower() + "-%",))
        con.execute("DELETE FROM sl_sources WHERE state = ?", (STATE,))
        con.executemany(f"INSERT INTO sl_races VALUES ({','.join('?' * len(cols))})", [tuple(r[k] for k in cols) for r in races.values()])
        con.executemany("INSERT INTO sl_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [tuple(c) for c in cands])
        con.executemany("INSERT INTO sl_places VALUES (?,?,?,?,?)", places)
        con.executemany("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", src)
    con.close()

    kinds = Counter(r["office_kind"] for r in races.values())
    gen = [c for c in cands if c[1] == "general"]
    g = Counter(races[c[0]]["office_kind"] for c in gen)
    head = (f"    New Hampshire (state races): {len(races)} races (Governor 1, Executive Council {kinds['executive_council']}, Senate "
            f"{kinds['state_senate']}, House {kinds['state_house']} districts electing {house_seats}); statutes {law_how}")
    if general is not None:
        head += (f"; {len(gen)} candidates on the November list (Governor {g['governor']}, Council {g['executive_council']}, Senate "
                 f"{g['state_senate']}, House {g['state_house']}; {len(short)} House districts with fewer candidates than seats)")
    else:
        head += "; no November candidates stored"
    head += f"; {fields} primary fields, {sum(1 for c in cands if c[1] != 'general')} primary rows from {len(used)} result files"
    say(head)
    if general is None:
        say(f"      waiting: the Secretary of State's \"2026 General Election Candidates\" PDF ({NHL.DETAILS}), saved from a browser into {folder} "
            "as general-election-candidates-list-<date>.pdf; www.sos.nh.gov answers scripts with Akamai's Access Denied page")
    if not used:
        say(f"      waiting: the September 8 State Primary results, the Excel files for Governor (Summary and the ten counties), Executive "
            f"Council and State Senate by district and State Representatives by county, from {NHL.PAGES['DEM']} and {NHL.PAGES['REP']}, "
            f"saved into {folder} under the names the site gives them")
    for f in skipped:
        say(f"      not read: {f}")
    if single:
        say(f"      one candidate only, not a field: {len(single)} party primaries")
    for c in cands:
        if c[12]:
            say(f"      matched: {c[0]} {c[1]}: {c[3]} -> {c[12]}{' (holds this seat)' if c[7] else ''}")
    for line in report:
        say(f"      check: {line}")
    return dict(races=len(races), general=len(gen), fields=fields, primary=sum(1 for c in cands if c[1] != "general"), report=report,
                waiting_general=general is None, waiting_primary=not used, skipped=skipped, short=short, empty=empty)


if __name__ == "__main__":
    args = sys.argv[1:]
    cache, fetch_flag = CACHE, True
    if "--cache" in args:
        i = args.index("--cache")
        cache = args[i + 1]
        del args[i:i + 2]
    if "--no-fetch" in args:
        args.remove("--no-fetch")
        fetch_flag = False
    if len(args) != 1:
        raise SystemExit("usage: python -m ballot.state_local_nh <database> [--cache <folder holding nh/>] [--no-fetch]")
    load(args[0], cache=cache, fetch_ok=fetch_flag)
