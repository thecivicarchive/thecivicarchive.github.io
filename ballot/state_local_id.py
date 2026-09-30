"""
ballot/state_local_id.py - Idaho's state races on the November 3, 2026 ballot: all 35 State Senate seats and all 70
State House seats (Idaho elects both chambers every two years; each legislative district elects one senator and two
representatives, in Seat A and Seat B, each seat its own contest), the seven statewide offices on this year's ballot
(Governor, Lieutenant Governor, Secretary of State, State Controller, State Treasurer, Attorney General and
Superintendent of Public Instruction, each elected on its own), and any judge's seat the list carries for November (a
district judge's seat that no one won outright in May). The statewide and legislative offices are partisan; judges
are elected without party labels.

Sources, the Idaho Secretary of State's own (Elections Division, voteidaho.gov) and nothing else:

  - The Idaho Candidate Filing Portal's "Search Filed Candidates List" (run.voteidaho.gov/search), asked the same
    questions its page asks of the portal's public service (api-run.voteidaho.gov/api), as ballot/lists/id.py does for
    Congress: the elections "2026 GENERAL" and "2026 PRIMARY", and the district types Statewide (SWD), State Legislature
    (LEG) and Judicial (JUD), 100 rows a page, the count checked against the service's "candidatesFound". Each row the
    service sends also carries a mailing address, a county and a voter number; the row is cut down to the allowed keys
    (ballot/lists/id.py's KEEP: ballot name, office, district type, district, seat, party, write-in mark, filing status
    and a withdrawal date) the moment it arrives, before anything else sees it, and nothing else is printed, logged or
    kept. The kept rows, those keys only, are ballot_cache/id/id_2026_sl_filed_candidates.json (refreshed after two
    days; the kept copy is used if the portal cannot be reached). A row marked Approved is on the ballot; Withdrawn is
    left off and counted; any other status stops the loader. The list gives no ballot order (Idaho's county clerks
    print the ballots), so none is stored; a declared write-in has write_in 1.
  - The May 19 primary: the Division's "Canvass Report" (the PDF ballot/lists/id.py reads; results only, no contact
    details in it), read with ballot/pdftext.py. One contest a page run: the heading ("State Representative District 1
    Seat A - Democratic", "4th Judicial District Judge - Seat Ada A"), the candidates across the top with the party's
    code under each, then Over Votes, Under Votes, Total Registered Voters and Total Votes Cast, county by county, and a
    Contest Total row. Checks: every county row's candidates, over votes and under votes add up to its votes cast; the
    county rows add up to the Contest Total, column by column (a count printed "**", "Protected", is left out of its
    row's sum, and its column's county sum need only not exceed the Contest Total); every name under a contest is on the
    primary list for that office, district, seat and party (Approved, or Withdrawn after the ballots were printed, which
    is noted), and every Approved name on the primary list is under its contest. Only the Contest Total is stored. The
    counties listed under a district's contests are its county_ids.

A party primary becomes a field when two or more names were on its ballot; write-ins would count in the share but the
canvass prints no write-in column for these contests, so a field's total is its candidates' votes. Who advanced is the
party's candidate on the November list (in any status: a nominee who withdrew later stays on the list as Withdrawn),
checked against the most votes. Independents file in the primary period but are not on a primary ballot; the
Constitution Party's candidates are on the primary list but have no contest in the canvass (each was alone). A judge's
seat on the November list is the May contest's runoff: the May field is kept as election "primary-NP", and the two on
the November list must be the two with the most votes, with no one past half.

Today's holders come from state_id.sqlite (the Open States roster): current legislators by chamber and district (the
roster writes House seats as 1A, 1B), and the officials table for the Governor, Lieutenant Governor, Secretary of State
and Attorney General (it does not carry the Controller, the Treasurer or the Superintendent). Only ids, names, parties
and districts are read from it; its e-mail, phone and address columns are never selected. A candidate is marked as the
sitting member (incumbent 1, state_member_id) only when the name fits that seat's holder, one to one. A candidate who
holds another seat in the same legislative district today, or (for a statewide race) any seat or office in the roster,
gets state_member_id with incumbent 0 and a note, again only when exactly one roster person fits.

Usage: python ballot/state_local_id.py <database file> [--cache <folder>]
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
from collections import Counter, OrderedDict, defaultdict
from urllib.error import HTTPError, URLError

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from ballot.common import fold, name_parts, party_code                          # noqa: E402
from ballot.lists.id import API, CANVASS_URL, KEEP, PAGE, iso, post, spoken     # noqa: E402
from ballot.match import fits, initials_clash                                    # noqa: E402
from ballot.pdftext import PDF, join, rows as pdf_rows                           # noqa: E402
from states import net                                                           # noqa: E402

STATE, FIPS, NAME = "ID", "16", "Idaho"
GENERAL, PRIMARY = "2026-11-03", "2026-05-19"
ROSTER_DB = os.path.join(HERE, "state_id.sqlite")
CACHE = os.path.join(HERE, "ballot_cache", "id")
FEDERAL_CACHE = os.path.join(HERE, "ballot_cache", "id")          # where ballot/lists/id.py keeps the canvass
COUNTY_ZIP = os.path.join(HERE, "states_cache", "census", "cb_2024_us_county_500k.zip")
COUNTY_URL = "https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_county_500k.zip"
LIST_FILE = "id_2026_sl_filed_candidates.json"
CANVASS_FILE = "id_2026_primary_canvass.pdf"
ELECTIONS = {"general": "2026 GENERAL", "primary": "2026 PRIMARY"}
TYPES = {"SWD": "Statewide", "LEG": "State Legislature", "JUD": "Judicial"}

# the office as the portal and the canvass write it -> (race key, office_kind, office shown, roster office)
STATEWIDE = OrderedDict([
    ("Governor", ("GOV", "governor", "Governor", "governor")),
    ("Lieutenant Governor", ("LTG", "lieutenant_governor", "Lieutenant Governor", "lt_governor")),
    ("Secretary of State", ("SOS", "secretary_of_state", "Secretary of State", "secretary of state")),
    ("State Controller", ("CTRL", "state_controller", "State Controller", None)),
    ("State Treasurer", ("TREAS", "state_treasurer", "State Treasurer", None)),
    ("Attorney General", ("AG", "attorney_general", "Attorney General", "attorney general")),
    ("Superintendent of Public Instruction", ("SPI", "superintendent_of_public_instruction", "Superintendent of Public Instruction", None)),
])
CHAMBER_WORDS = {"Senate": "the Idaho Senate", "House": "the Idaho House of Representatives"}
ORDINAL = {1: "First", 2: "Second", 3: "Third", 4: "Fourth", 5: "Fifth", 6: "Sixth", 7: "Seventh"}
WRITE_IN = "Write-in candidate: the name is not printed on the ballot."
PROTECTED = object()          # "**" in the canvass: a count it protects; its footnote says only "Protected"

HEAD_PARTY = re.compile(r"^(?P<office>.+?) - (?P<party>[A-Z][a-z]+(?:[- ][A-Z][a-z]+)*)$")
HEAD_SENATE = re.compile(r"^State Senator District (\d+)$")
HEAD_HOUSE = re.compile(r"^State Representative District (\d+) Seat ([AB])$")
HEAD_DJ = re.compile(r"^(\d)(?:st|nd|rd|th) Judicial District Judge - Seat (.+)$")
HEAD_SC = re.compile(r"^Justice of the Supreme Court - Seat ([A-Z])$")
HEAD_COA = re.compile(r"^Judge of the Court of Appeals - Seat ([A-Z])$")

SRC_GENERAL = "id-sos-2026-sl-general-list"
SRC_PRIMARY_LIST = "id-sos-2026-sl-primary-list"
SRC_CANVASS = "id-sos-2026-sl-primary-canvass"
SRC_ROSTER = "id-openstates-roster"
SRC_COUNTIES = "id-census-cb-2024-county"

SCHEMA = """
CREATE TABLE IF NOT EXISTS sl_races (race_id TEXT PRIMARY KEY, state TEXT NOT NULL, level TEXT NOT NULL, office_kind TEXT NOT NULL, office TEXT NOT NULL, jurisdiction TEXT, jurisdiction_id TEXT, county_ids TEXT, district TEXT, seat TEXT, special INTEGER NOT NULL DEFAULT 0, partisan INTEGER NOT NULL, holder_id TEXT, holder_name TEXT, holder_party TEXT, election_date TEXT NOT NULL, note TEXT);
CREATE TABLE IF NOT EXISTS sl_candidates (race_id TEXT NOT NULL, election TEXT NOT NULL, election_date TEXT, name TEXT NOT NULL, party TEXT, party_code TEXT, ballot_order INTEGER, incumbent INTEGER NOT NULL DEFAULT 0, write_in INTEGER NOT NULL DEFAULT 0, votes INTEGER, pct REAL, outcome TEXT, state_member_id TEXT, source_id TEXT, note TEXT, PRIMARY KEY (race_id, election, name));
CREATE TABLE IF NOT EXISTS sl_sources (source_id TEXT PRIMARY KEY, state TEXT, kind TEXT, agency TEXT, title TEXT, url TEXT, published TEXT, fetched TEXT, sha256 TEXT, rows INTEGER, note TEXT);
CREATE TABLE IF NOT EXISTS sl_places (kind TEXT NOT NULL, id TEXT NOT NULL, name TEXT NOT NULL, county_ids TEXT, source_id TEXT, PRIMARY KEY (kind, id));
"""


def fail(msg):
    raise SystemExit(f"Idaho (state races): {msg}")


def sha_of(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest() if path and os.path.exists(path) else ""


def mdate(path):
    return dt.date.fromtimestamp(os.path.getmtime(path)).isoformat() if path and os.path.exists(path) else ""


def clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


# ---------- races: one key for the portal's rows and the canvass's headings ----------

def seat_key(seat):
    return re.sub(r"[^A-Z0-9]+", "-", seat.upper()).strip("-")


def race_info(kind, district=None, seat=None, office=None):
    """(race_id, info) for a statewide office, a legislative seat or a judge's seat."""
    if kind == "statewide":
        key, okind, shown, roster_office = STATEWIDE[office]
        return f"2026-{STATE}-{key}", dict(level="statewide", office_kind=okind, office=shown, district=None, seat=None, chamber=None,
                                           roster=roster_office, partisan=1, jurisdiction=NAME, jurisdiction_id=FIPS)
    if kind == "senate":
        d = str(int(district))
        return f"2026-{STATE}-SS{d}", dict(level="legislature", office_kind="state_senate", office="State Senator", district=d, seat=None,
                                           chamber="Senate", roster=d, partisan=1, jurisdiction=f"Legislative District {d}", jurisdiction_id=FIPS)
    if kind == "house":
        d, s = str(int(district)), seat.upper()
        return f"2026-{STATE}-SH{d}{s}", dict(level="legislature", office_kind="state_house", office="State Representative", district=d, seat=s,
                                              chamber="House", roster=f"{d}{s}", partisan=1, jurisdiction=f"Legislative District {d}",
                                              jurisdiction_id=FIPS)
    if kind == "supreme_court":
        return f"2026-{STATE}-SC-{seat}", dict(level="court", office_kind="supreme_court", office="Justice of the Supreme Court", district=None,
                                               seat=seat, chamber=None, roster=None, partisan=0, jurisdiction=NAME, jurisdiction_id=FIPS)
    if kind == "court_of_appeals":
        return f"2026-{STATE}-COA-{seat}", dict(level="court", office_kind="court_of_appeals", office="Judge of the Court of Appeals",
                                                district=None, seat=seat, chamber=None, roster=None, partisan=0, jurisdiction=NAME,
                                                jurisdiction_id=FIPS)
    if kind == "district_court":
        d = str(int(district))
        return f"2026-{STATE}-DJ{d}-{seat_key(seat)}", dict(level="court", office_kind="district_court", office="District Judge", district=d,
                                                            seat=seat, chamber=None, roster=None, partisan=0,
                                                            jurisdiction=f"{ORDINAL.get(int(d), d)} Judicial District", jurisdiction_id=None)
    fail(f"a kind of race the loader does not know: {kind}")


def race_of_row(r):
    """(race_id, info) for a row of the portal's list."""
    office, d, s = r["officeName"], (r["district"] or "").strip(), (r["seat"] or "").strip()
    if r["districtType"] == "Statewide" and office in STATEWIDE and not d and not s:
        return race_info("statewide", office=office)
    if r["districtType"] == "State Legislature" and d.isdigit():
        if office == "State Senator" and not s:
            return race_info("senate", d)
        if office == "State Representative" and s in ("A", "B"):
            return race_info("house", d, s)
    if r["districtType"] == "Judicial":
        if office == "Supreme Court Justice" and re.fullmatch(r"[A-Z]", d) and not s:
            return race_info("supreme_court", seat=d)
        if office == "Appellate Court Justice" and re.fullmatch(r"[A-Z]", d) and not s:
            return race_info("court_of_appeals", seat=d)
        if office == "District Judge" and d.isdigit() and s:
            return race_info("district_court", d, s)
    fail(f"a row of the filing list names an office, district or seat the loader does not know ({r['districtType']!r}, {office!r}, "
         f"{d!r}, {s!r})")


def race_of_heading(title):
    """(race_id, info, party as printed or None) for a canvass heading; 'federal' for Congress (the federal loader's); None when
    the heading is not one the loader knows."""
    if title.startswith("United States "):
        return "federal"
    for pat, kind in ((HEAD_DJ, "district_court"), (HEAD_SC, "supreme_court"), (HEAD_COA, "court_of_appeals")):
        m = pat.match(title)
        if m:
            if kind == "district_court":
                return (*race_info(kind, m.group(1), clean(m.group(2))), None)
            return (*race_info(kind, seat=m.group(1)), None)
    m = HEAD_PARTY.match(title)
    if not m:
        return None
    office, party = m.group("office"), m.group("party")
    if office in STATEWIDE:
        return (*race_info("statewide", office=office), party)
    ms, mh = HEAD_SENATE.match(office), HEAD_HOUSE.match(office)
    if ms:
        return (*race_info("senate", ms.group(1)), party)
    if mh:
        return (*race_info("house", mh.group(1), mh.group(2)), party)
    return None


# ---------- the filing portal: allowed keys only ----------

def ask(path, body):
    """One question to the portal's service, asked again at most twice after a refusal or a page that is not its JSON."""
    last = None
    for attempt in range(3):
        try:
            return post(path, body)
        except (HTTPError, URLError, OSError, ValueError, SystemExit) as e:      # ValueError: an answer that is not JSON (a bot check)
            last = e
            if attempt < 2:
                time.sleep(5 * (attempt + 1))
    raise ConnectionError(f"{path}: {last}")


def fetch_lists(say):
    elections = ask("PublicLookup/GetAllElections", {"isFutureElections": False})
    kinds = {k.get("code"): (k["value"], k.get("name")) for k in ask("Filing/GetAllDistrictTypes", {"isSearch": True})}
    parties = {p["name"]: p["code"] for p in ask("Filing/GetLookupValues", {"tableName": "Party"})}
    for code, name in TYPES.items():
        if code not in kinds or kinds[code][1] != name:
            fail(f"the filing portal no longer lists the district type {code} ({name})")
    out = {"page": PAGE, "service": API + "FiledCandidates/SearchCandidates", "parties": parties,
           "fetched": dt.date.today().isoformat(), "keys": list(KEEP)}
    for which, label in ELECTIONS.items():
        e = [x for x in elections if clean(x["name"]).endswith(label)]
        if len(e) != 1:
            fail(f"the filing portal lists {len(e)} elections named {label!r}")
        block = {"election": clean(e[0]["name"]), "date": iso(e[0].get("attribute1")), "final": {}, "counts": {}, "rows": []}
        for code in TYPES:
            rows, n, found = [], 1, None
            while found is None or len(rows) < found:
                data = ask("FiledCandidates/SearchCandidates", {
                    "candidateName": None, "electionGuid": e[0]["value"], "districtTypeGuid": kinds[code][0], "districtNumber": None,
                    "countyGuid": None, "officeGuid": None, "district": None, "seat": None, "partyGuid": None,
                    "filingStatusGuids": None, "pageNumber": n, "pageSize": 100, "sortBy": None, "sortType": "asc"})
                found = data["candidatesFound"]
                block["final"][code] = data["isFinalList"]
                got = data.get("candidates") or []
                if not got:
                    break
                rows += [{k: c.get(k) for k in KEEP} for c in got]      # the allowed keys only; address, county and voter number dropped here
                del got, data
                n += 1
            if len(rows) != found:
                fail(f"the filing portal counts {found} {TYPES[code]} candidates for {label}; {len(rows)} were read")
            for r in rows:
                r["candidateName"] = clean(r["candidateName"])
                if r["districtType"] != TYPES[code]:
                    fail(f"a {TYPES[code]} row of the {label} list names another district type")
            block["counts"][code] = found
            block["rows"] += rows
        say(f"      Filed Candidates List, {label}: " + ", ".join(f"{TYPES[c]} {block['counts'][c]}" for c in TYPES)
            + (" (marked final)" if all(block["final"].values()) else ""))
        out[which] = block
    return out


def read_lists(cache, say):
    """The kept rows (allowed keys only) for the general and primary lists: fresh from the portal every two days, else the kept
    copy. Returns (lists, path, how)."""
    path = os.path.join(cache, LIST_FILE)
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < 2 * 86400:
        return json.load(open(path, encoding="utf-8")), path, "the rows kept from the portal within the last two days"
    try:
        net.patient_lookups()
        lists = fetch_lists(say)
    except ConnectionError as e:
        if not os.path.exists(path):
            fail(f"the filing portal could not be read ({e}) and there is no kept copy; a browser would show the same "
                 f"list at {PAGE}")
        say(f"    Idaho (state races): the filing portal could not be read ({e}); using the rows kept on {mdate(path)}")
        return json.load(open(path, encoding="utf-8")), path, f"the rows kept on {mdate(path)} (the portal could not be reached)"
    os.makedirs(cache, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(lists, fh, ensure_ascii=False, indent=0)
    return lists, path, "read afresh from the portal's service"


# ---------- the canvass (results only) ----------

def canvass(path, codes):
    """{(race_id, party code): contest} for every state and judicial contest, from the Contest Total rows, after the checks in
    the note at the top. A contest: names, votes, over, under, cast, counties (names as printed), party, hidden, pages."""
    pdf = PDF(open(path, "rb").read())
    num = lambda s: int(s.replace(",", "")) if re.fullmatch(r"\d{1,3}(?:,\d{3})*", s) else None
    contests, info, titled, federal = {}, {}, False, 0
    for n, (page, res) in enumerate(pdf.pages(), start=1):
        prow = pdf_rows(pdf, page, res)
        texts = [(y, join(rs), rs) for y, rs in prow]
        titled = titled or any(t == "Primary Election - May 19, 2026" for _y, t, _rs in texts)
        votefor = [y for y, t, _rs in texts if t.startswith("Vote For")]
        if not votefor:
            continue
        heads = [(y, t, race_of_heading(t)) for y, t, _rs in texts if y > votefor[0] and race_of_heading(t) is not None]
        if len(votefor) != 1 or len(heads) != 1:
            fail(f"page {n} of the canvass has {len(votefor)} 'Vote For' lines and {len(heads)} headings the loader knows; "
                 "it expects one contest a page")
        _hy, title, got = heads[0]
        if got == "federal":
            federal += 1
            continue
        rid, rinfo, party = got
        if party is None:
            pcode, printed = "NP", "NON"
        else:
            if party not in codes:
                fail(f"the canvass names a party not in the filing portal's key ({party!r}, page {n})")
            pcode = printed = codes[party]
        over = next(((y, rs) for y, t, rs in texts if t.startswith("Over Votes Under Votes")), None)
        if not over:
            fail(f"page {n} of the canvass has no Over Votes heading")
        oy, ors = over
        right = {join([r]): r[0] for r in ors}
        if not {"Over Votes", "Under Votes", "Voters", "Total Votes Cast"} <= set(right):
            fail(f"page {n} of the canvass has column headings the loader does not read")
        below = [(y, rs) for y, rs in prow if y < oy - 1]
        pcodes = sorted(next((rs for y, rs in below if all(join([r]).isupper() and len(join([r])) <= 4 for r in rs)), []))
        if not pcodes or [join([r]) for r in pcodes] != [printed] * len(pcodes):
            fail(f"the party codes under the names on page {n} of the canvass are not all {printed}")
        # candidate columns: one under each party code; a name's pieces (a name that wraps sits a little to the right) between
        # "Vote For" and the Over Votes line go to the code at or just left of them
        anchors = [r[0] for r in pcodes]
        cols = [[] for _ in anchors]
        for y, rs in prow:
            if oy < y < votefor[0]:
                for r in rs:
                    if r[0] < right["Over Votes"] - 5:
                        k = max((i for i, a in enumerate(anchors) if a <= r[0] + 5), default=None)
                        if k is None:
                            fail(f"a name on page {n} of the canvass sits left of every party code")
                        cols[k].append(r)
        if not all(cols):
            fail(f"a party code on page {n} of the canvass has no name above it")
        names = []
        for rs in cols:      # read line by line, top to bottom; a line that ends in a hyphen runs straight on (Carter- / Goodheart)
            parts = [join([r for r in rs if round(r[1]) == y]) for y in sorted({round(r[1]) for r in rs}, reverse=True)]
            text = parts[0]
            for p in parts[1:]:
                text += p if text.endswith("-") else " " + p
            names.append(clean(text))
        edges = [min(r[0] for r in rs) for rs in cols] + [right["Over Votes"], right["Under Votes"], right["Voters"] - 11,
                                                        right["Total Votes Cast"]]
        labels = names + ["over", "under", "registered", "cast"]
        key = (rid, pcode)
        f = contests.setdefault(key, {"title": title, "party": party, "names": names, "sum": [0] * len(labels), "total": None,
                                      "counties": [], "pages": [], "hidden": set(), "labels": labels})
        info[rid] = rinfo
        if f["names"] != names:
            fail(f"the candidates under {title} differ from one page of the canvass to the next (page {n})")
        f["pages"].append(n)
        for y, rs in below:
            first = join([r for r in rs if r[0] < edges[0] - 20])
            if not (first.endswith(" County") or first == "Contest Total"):
                continue
            vals = [None] * len(labels)
            for r in rs:
                if r[0] < edges[0] - 20:
                    continue
                k = min(range(len(edges)), key=lambda i: abs(edges[i] - r[0]))
                cell = r[3].strip()
                if abs(edges[k] - r[0]) > 20 or vals[k] is not None or (num(cell) is None and cell != "**"):
                    fail(f"a cell on page {n} of the canvass under {title} is not read ({first})")
                vals[k] = num(cell) if cell != "**" else PROTECTED
            if None in vals:
                fail(f"a row on page {n} of the canvass under {title} is missing a cell ({first})")
            hidden = {i for i, v in enumerate(vals) if v is PROTECTED}
            if hidden and first == "Contest Total":
                fail(f"the canvass protects (**) a Contest Total figure under {title}")
            if not hidden and sum(vals[:len(names)]) + vals[-4] + vals[-3] != vals[-1]:
                fail(f"{first} under {title}: candidates, over and under votes do not add up to votes cast (page {n})")
            if first == "Contest Total":
                if f["total"] is not None:
                    fail(f"two Contest Total rows under {title}")
                f["total"] = vals
            else:
                f["counties"].append(first)
                f["hidden"] |= hidden
                f["sum"] = [a + (0 if b is PROTECTED else b) for a, b in zip(f["sum"], vals)]
    if not titled:
        fail("the file is not the canvass of the May 19, 2026 primary")
    out = {}
    for key, f in contests.items():
        if not f["total"]:
            fail(f"no Contest Total for {f['title']} in the canvass")
        for i, label in enumerate(f["labels"]):
            if label == "registered":      # a county split between districts counts all its voters under each
                continue
            if f["sum"][i] != f["total"][i] and not (i in f["hidden"] and f["sum"][i] <= f["total"][i]):
                fail(f"the county rows under {f['title']} do not add up to the canvass's Contest Total ({label})")
        k = len(f["names"])
        writes = [i for i, nm in enumerate(f["names"]) if re.search(r"write", nm, re.I)]
        out[key] = {"title": f["title"], "party": f["party"], "names": [nm for i, nm in enumerate(f["names"]) if i not in writes],
                    "votes": [v for i, v in enumerate(f["total"][:k]) if i not in writes],
                    "write_ins": sum(f["total"][i] for i in writes), "over": f["total"][k], "under": f["total"][k + 1],
                    "cast": f["total"][-1], "counties": f["counties"], "hidden": sorted(f["labels"][i] if i >= k else "a candidate"
                                                                                       for i in f["hidden"]), "pages": f["pages"]}
    return out, info, federal


# ---------- the roster (ids, names, parties and districts only) and the counties ----------

def roster():
    con = sqlite3.connect(ROSTER_DB)
    seats = defaultdict(list)
    for bid, first, last, full, party, district, chamber in con.execute(
            "SELECT bioguide_id, first_name, last_name, official_full, party_name, district, chamber FROM legislators WHERE is_current = 1"):
        seats[(chamber, str(district))].append({"id": bid, "first": first or "", "last": last or "", "full": full or f"{first} {last}",
                                                "party": party, "chamber": chamber, "district": str(district)})
    offices = {}
    for bid, first, last, full, office, label, party in con.execute(
            "SELECT bioguide_id, first_name, last_name, official_full, office, office_label, party_name FROM officials"):
        offices[office] = {"id": bid, "first": first or "", "last": last or "", "full": full or f"{first} {last}", "party": party,
                           "label": label, "chamber": None, "district": None}
    as_of = (con.execute("SELECT MAX(updated_at) FROM legislators").fetchone()[0] or "")[:10]
    con.close()
    return seats, offices, as_of


def counties():
    """{folded 'Ada County': (GEOID, 'Ada County')} for Idaho from the Census Bureau's cartographic county file."""
    import shapefile                                   # pyshp
    if not os.path.exists(COUNTY_ZIP):
        net.download(COUNTY_URL, COUNTY_ZIP, max_age_days=3650)
    z = zipfile.ZipFile(COUNTY_ZIP)
    base = next(n[:-4] for n in z.namelist() if n.endswith(".dbf"))
    rdr = shapefile.Reader(dbf=io.BytesIO(z.read(base + ".dbf")))
    fields = [f[0] for f in rdr.fields[1:]]
    out = {}
    for rec in rdr.iterRecords():
        rec = dict(zip(fields, rec))
        if str(rec.get("STATEFP")) == FIPS:
            out[fold(str(rec["NAMELSAD"]))] = (str(rec["GEOID"]), str(rec["NAMELSAD"]))
    if len(out) != 44:
        fail(f"the county file gives {len(out)} Idaho counties, not 44")
    return out


def forms(parts):
    g, f = parts
    out = [(g, f)]
    if len(g) > 1 and all(len(w) == 1 for w in g):
        out.append((["".join(g)], f))
    return out


def person_fits(name, p):
    for cand in forms(name_parts(name)):
        for reg0 in ((fold(p["first"]).split(), fold(p["last"])), name_parts(p["full"])):
            for reg in forms(reg0):
                if reg[1] and fits(cand, reg) and not initials_clash(name, reg):
                    return True
    return False


def same_person(a, b):
    return fold(a) == fold(b) or fits(name_parts(a), name_parts(b))


# ---------- the load ----------

def load(db_path, say=print, cache=CACHE):
    seats, offices, as_of = roster()
    cmap = counties()
    checks = []

    lists, lpath, how = read_lists(cache, say)
    codes = lists["parties"]
    gen, pri = lists["general"], lists["primary"]
    if gen["date"] != GENERAL or pri["date"] != PRIMARY:
        fail(f"the portal's election dates are {gen['date']} and {pri['date']}, not {GENERAL} and {PRIMARY}")

    cpath = next((p for p in (os.path.join(cache, CANVASS_FILE), os.path.join(FEDERAL_CACHE, CANVASS_FILE)) if os.path.exists(p)), None)
    if not cpath:
        cpath = os.path.join(cache, CANVASS_FILE)
        net.download(CANVASS_URL, cpath, max_age_days=30, say=say)
    if open(cpath, "rb").read(5) != b"%PDF-":
        fail(f"{CANVASS_URL} did not give a PDF (a bot check or a moved file); a browser would need to save it as {cpath}")
    contests, cinfo, n_federal = canvass(cpath, codes)

    # ---- the November list: races and candidates
    races, on_ballot, gone, write_ins, nominees = OrderedDict(), defaultdict(list), [], [], defaultdict(list)
    for r in gen["rows"]:
        rid, info = race_of_row(r)
        races.setdefault(rid, info)
        party, name, status = r["partyName"], r["candidateName"], r["filingStatusCode"]
        if party not in codes:
            fail(f"the general list names a party not in the portal's key ({party!r}, {rid})")
        if info["partisan"] == (codes[party] == "NOP"):
            fail(f"{rid}: a {'partisan' if info['partisan'] else 'nonpartisan'} office with the party {party!r} on the general list")
        nominees[(rid, codes[party] if info["partisan"] else "NP")].append((name, status, iso(r["withdrawalDate"])))
        if status == "W":
            gone.append((rid, name, party, iso(r["withdrawalDate"])))
            continue
        if status != "A":
            fail(f"a filing status on the general list the loader does not read ({r['filingStatus']!r}, {rid})")
        on_ballot[rid].append((name, party, bool(r["isWriteIn"])))
    senate = sorted(int(i["district"]) for i in races.values() if i["office_kind"] == "state_senate")
    house = sorted((int(i["district"]), i["seat"]) for i in races.values() if i["office_kind"] == "state_house")
    if senate != list(range(1, 36)):
        checks.append(f"State Senate districts on the general list are not 1 to 35: missing {sorted(set(range(1, 36)) - set(senate))}")
    want_house = [(d, s) for d in range(1, 36) for s in "AB"]
    if house != want_house:
        checks.append(f"State House seats on the general list are not 1A to 35B: missing {sorted(set(want_house) - set(house))}")
    sw_missing = [o for o, v in STATEWIDE.items() if f"2026-{STATE}-{v[0]}" not in races]
    if sw_missing:
        checks.append(f"statewide offices with no row on the general list: {', '.join(sw_missing)}")
    empty = sorted(rid for rid in races if not on_ballot.get(rid))
    if empty:
        checks.append(f"races on the general list with every candidate withdrawn: {', '.join(empty)}")

    # ---- the primary list: who was on each primary ballot (for the canvass check)
    ballot, withdrawn_pri = defaultdict(set), defaultdict(dict)      # withdrawn: {folded name: withdrawal date}
    for r in pri["rows"]:
        rid, _info = race_of_row(r)
        code = codes.get(r["partyName"])
        if code is None:
            fail(f"the primary list names a party not in the portal's key ({r['partyName']!r})")
        judicial = r["districtType"] == "Judicial"
        if judicial != (code == "NOP"):
            fail(f"{rid}: the primary list gives the party {r['partyName']!r} to a {'judicial' if judicial else 'partisan'} office")
        if code == "IND":
            continue
        pc = "NP" if judicial else code
        if r["filingStatusCode"] == "W":
            withdrawn_pri[(rid, pc)][fold(r["candidateName"])] = iso(r["withdrawalDate"])
            continue
        if r["filingStatusCode"] != "A":
            fail(f"a filing status on the primary list the loader does not read ({r['filingStatus']!r}, {rid})")
        ballot[(rid, pc)].add(fold(r["candidateName"]))

    unmatched, late_withdrawn = [], []
    for key, f in sorted(contests.items()):
        got = {fold(n) for n in f["names"]}
        extra = got - ballot.get(key, set())
        late = extra & set(withdrawn_pri.get(key, {}))
        for nm in sorted(late):
            d = withdrawn_pri[key][nm]
            late_withdrawn.append(f"{key[0]} {key[1]} (withdrew {spoken(d) if d else 'on a date the list does not give'}"
                                  f"{', after the primary' if d and d > PRIMARY else ''})")
        if extra - late or ballot.get(key, set()) - got:
            unmatched.append(f"{f['title']} ({len(extra - late)} under the contest not on the list, {len(ballot.get(key, set()) - got)} "
                             "on the list not under the contest)")
    no_contest = sorted(k for k in ballot if k not in contests)
    contested_missing = [f"{r} {c}" for r, c in no_contest if len(ballot[(r, c)]) > 1]
    if unmatched:
        checks.append("canvass contests whose names are not the primary list's: " + "; ".join(unmatched))
    if contested_missing:
        checks.append("two or more on a primary list with no contest in the canvass: " + ", ".join(contested_missing))

    # ---- holders and the people who might be them
    holders, notes = {}, {}
    for rid, i in races.items():
        if i["level"] == "legislature":
            hs = seats.get((i["chamber"], i["roster"]), [])
            if len(hs) > 1:
                checks.append(f"the roster lists {len(hs)} sitting members for {rid}")
            holders[rid] = hs
            if not hs:
                notes[rid] = f"The Open States roster ({as_of}) lists no sitting member for this seat."
        elif i["level"] == "statewide":
            h = offices.get(i["roster"]) if i["roster"] else None
            holders[rid] = [h] if h else []
            if not h:
                notes[rid] = "The Open States roster this site uses does not carry this office, so today's holder is not shown."
        else:
            holders[rid] = []
    everyone = [p for ps in seats.values() for p in ps] + list(offices.values())
    own_race = {h["id"]: rid for rid, hs in holders.items() for h in hs}
    names_in = defaultdict(set)
    for rid, rows in on_ballot.items():
        names_in[rid] |= {n for n, _p, _w in rows}
    for (rid, _pc), f in contests.items():
        names_in[rid] |= set(f["names"])

    def running_at_home(p, rid):
        home = own_race.get(p["id"])
        return bool(home and home != rid and any(person_fits(n, p) for n in names_in[home]))

    def sitting(rid, names):
        i, out = races[rid], {}
        hs = holders[rid]
        pairs = [(n, h) for n in names for h in hs if person_fits(n, h)]
        for n, h in pairs:
            if sum(1 for a, _ in pairs if a == n) == 1 and sum(1 for _, b in pairs if b["id"] == h["id"]) == 1:
                out[n] = (h["id"], 1, None)
        if i["level"] == "court":
            return out
        for n in names:
            if n in out:
                continue
            if i["level"] == "legislature":      # the district's other seats: the Senate seat and House Seats A and B
                pool = [p for (ch, d), ps in seats.items() for p in ps
                        if re.sub(r"[AB]$", "", d) == i["district"] and not any(p["id"] == h["id"] for h in hs)]
            else:
                pool = [p for p in everyone if not any(p["id"] == h["id"] for h in hs)]
            got = [p for p in pool if person_fits(n, p)]
            if len(got) == 1 and not running_at_home(got[0], rid):
                p = got[0]
                where = (f"Serves today in {CHAMBER_WORDS[p['chamber']]}, District {re.sub(r'[AB]$', '', p['district'])}"
                         + (f", Seat {p['district'][-1]}" if p["chamber"] == "House" and p["district"][-1:] in "AB" else "") + "."
                         if p["chamber"] else f"Serves today as {p['label']}.")
                out[n] = (p["id"], 0, where)
        return out

    cand = []

    # ---- the November ballot
    for rid, rows in on_ballot.items():
        i = races[rid]
        fit = sitting(rid, [n for n, _p, _w in rows])
        for name, party, wi in rows:
            mid, inc, note = fit.get(name, (None, 0, None))
            n = [note] if note else []
            if wi:
                write_ins.append(rid)
                n.append(WRITE_IN)
            if i["partisan"]:
                pc = codes[party]
                was = set(contests.get((rid, pc), {}).get("names", [])) | ballot.get((rid, pc), set())
                if pc != "IND" and not wi and not any(same_person(name, x) for x in was):
                    n.append(f"Not on the May 19 {party} primary ballot for this seat; the list does not say how the nomination was made.")
                shown_party, shown_code = party, party_code(party)
            else:
                shown_party, shown_code = "Nonpartisan office", "N"
            if inc and holders[rid]:
                h = next(h for h in holders[rid] if h["id"] == mid)
                if i["partisan"] and h["party"] and h["party"] != party:
                    checks.append(f"{rid}: the sitting member is {h['party']} in the roster, {party} on the list")
            cand.append((rid, "general", GENERAL, name, shown_party, shown_code, None, inc, 1 if wi else 0, None, None, None, mid,
                         SRC_GENERAL, " ".join(n) or None))

    # ---- the May 19 fields (the primary, and the first round of a judge's seat in a runoff)
    fields, upset, open_, runoffs = Counter(), [], [], []
    for (rid, pc), f in sorted(contests.items()):
        if rid not in races or len(f["names"]) < 2:
            continue
        i = races[rid]
        entries = list(zip(f["names"], f["votes"]))
        counted = sum(v for _n, v in entries) + f["write_ins"]
        top = sorted(entries, key=lambda e: -e[1])
        noms = nominees.get((rid, pc), [])
        won = [e for e in entries if any(same_person(e[0], x[0]) for x in noms)]
        if pc == "NP":      # a judge's seat: the November list names the two who go on
            winners = {e[0] for e in won}
            if len(won) != 2 or winners != {e[0] for e in top[:2]} or (len(top) > 2 and top[1][1] == top[2][1]):
                upset.append(f"{rid} (the November list's names are not the May contest's top two)")
            if top[0][1] * 2 > counted:
                upset.append(f"{rid} (a candidate won more than half the votes in May, yet the seat is on the November list)")
            runoffs.append(rid)
            spoken_top = ", ".join(f"{n} {v:,}" for n, v in top)
            notes[rid] = ((notes[rid] + " ") if rid in notes else "") + (
                f"On May 19 no candidate won more than half the votes for this seat ({spoken_top}, in the canvass); the two with the most "
                "votes are on the November list.")
        elif len(won) == 1:
            winners = {won[0][0]}
            if top[0][0] != won[0][0] or top[0][1] == top[1][1]:
                upset.append(f"{rid} {f['party']}")
        elif not won and top[0][1] != top[1][1]:
            winners = {top[0][0]}
            open_.append(f"{rid} {f['party']} (the most votes: {top[0][0]}; not on the November list)")
        else:
            winners = set()
            open_.append(f"{rid} {f['party']} ({len(won)} names fit the November list)")
        fields["court" if pc == "NP" else i["office_kind"] if i["level"] == "legislature" else "statewide"] += 1
        fit = sitting(rid, [n for n, _v in entries])
        election = "primary-NP" if pc == "NP" else f"primary-{pc}"
        for name, votes in entries:
            mid, inc, snote = fit.get(name, (None, 0, None))
            extra = [snote] if snote else []
            nom = next((x for x in noms if same_person(name, x[0])), None)
            if name in winners and nom and nom[1] == "W":
                extra.append(f"Won the primary, then withdrew{' on ' + spoken(nom[2]) if nom[2] else ''}; not on the November ballot.")
            elif name in winners and not nom:
                extra.append("Won the most votes in the primary; not on the November list (the list does not say why).")
            wd = withdrawn_pri.get((rid, pc), {})
            if fold(name) in wd:
                d = wd[fold(name)]
                extra.append(f"Withdrew on {spoken(d)}, after the primary." if d and d > PRIMARY else
                             f"Withdrew{' on ' + spoken(d) if d else ''} after the primary ballots were printed; the canvass still counts the "
                             "votes cast for this candidate.")
            cand.append((rid, election, PRIMARY, name, f["party"] if pc != "NP" else "Nonpartisan office",
                         party_code(f["party"]) if pc != "NP" else "N", None, inc, 0, votes,
                         round(100 * votes / counted, 1) if counted else None,
                         None if not winners else ("advanced" if name in winners else "lost"), mid, SRC_CANVASS, " ".join(extra) or None))

    # ---- county ids: the counties listed under the district's contests in the canvass
    by_district = defaultdict(set)
    for (rid, _pc), f in contests.items():
        info = cinfo[rid]
        if info["level"] == "legislature":
            by_district[info["district"]] |= set(f["counties"])
    county_ids, unknown_c = {}, set()
    for rid, i in races.items():
        if i["level"] == "legislature":
            names = by_district.get(i["district"], set())
        elif i["office_kind"] == "district_court":
            names = set().union(*(set(f["counties"]) for (r2, _pc), f in contests.items() if r2 == rid))
        else:
            names = set()
        unknown_c |= {c for c in names if fold(c) not in cmap}
        ids = sorted(cmap[fold(c)][0][2:] for c in names if fold(c) in cmap)
        county_ids[rid] = json.dumps(ids) if ids else None
        if i["level"] == "legislature" and not ids:
            checks.append(f"{rid}: no contest for this district in the canvass, so no counties")
    if unknown_c:
        checks.append(f"county names in the canvass not in the Census file: {', '.join(sorted(unknown_c))}")

    # ---- checks on the whole
    keys = Counter((c[0], c[1], c[3]) for c in cand)
    dup = [k for k, v in keys.items() if v > 1]
    if dup:
        fail(f"the same name twice in one election: {dup}")
    gen_n = Counter(c[0] for c in cand if c[1] == "general")
    if gen_n.total() + len(gone) != len(gen["rows"]):
        fail("November rows written plus withdrawn do not equal the general list's rows")
    for key, f in contests.items():      # the stored primary votes are the canvass's Contest Total, candidate by candidate
        if key[0] in races and len(f["names"]) > 1:
            stored = {c[3]: c[9] for c in cand if c[0] == key[0] and c[1] == ("primary-NP" if key[1] == "NP" else f"primary-{key[1]}")}
            if stored != dict(zip(f["names"], f["votes"])):
                fail(f"the stored votes for {f['title']} are not the canvass's")

    race_rows = []
    for rid, i in races.items():
        hs = holders[rid]
        race_rows.append((rid, STATE, i["level"], i["office_kind"], i["office"], i["jurisdiction"], i["jurisdiction_id"], county_ids.get(rid),
                          i["district"], i["seat"], 0, i["partisan"], ",".join(h["id"] for h in hs) or None,
                          " and ".join(h["full"] for h in hs) or None, ", ".join(dict.fromkeys(h["party"] for h in hs if h["party"])) or None,
                          GENERAL, notes.get(rid)))
    place_rows = [("county", geoid, full, None, SRC_COUNTIES) for geoid, full in sorted(cmap.values())]

    n_field_rows = sum(1 for c in cand if c[1] != "general")
    gone_words = "; ".join(f"{name} ({party}, {rid}{', withdrew ' + spoken(d) if d else ''})" for rid, name, party, d in gone) or "none"
    protected = [f"{f['title']} ({', '.join(f['hidden'])})" for f in contests.values() if f["hidden"]]
    final_g = all(gen["final"].values())
    src = [
        (SRC_GENERAL, STATE, "official candidate list", "Idaho Secretary of State, Elections Division",
         f"Filed Candidates List, Idaho Candidate Filing Portal: {gen['election']}, Statewide, State Legislature and Judicial offices",
         PAGE, "", lists.get("fetched") or mdate(lpath), sha_of(lpath), len(gen["rows"]),
         f"Read from the portal's public service ({lists['service']}), the questions the search page asks ({how}); "
         f"{'the Division marks the list final' if final_g else 'the Division has not marked every part of the list final'}. "
         "Ballot name, office, district, seat, party, write-in mark, filing status and withdrawal date only; the mailing address, county "
         "and voter number the service also sends are dropped as each row arrives and never read, printed or stored. The fingerprint is "
         f"of the kept rows (ballot_cache/id/{LIST_FILE}), not of the service's answer. The list gives no ballot order (county clerks print "
         f"the ballots), so none is stored. Withdrawn, left off the November ballot: {gone_words}. Declared write-ins: {len(write_ins)}."),
        (SRC_PRIMARY_LIST, STATE, "official candidate list (used as a check)", "Idaho Secretary of State, Elections Division",
         f"Filed Candidates List, Idaho Candidate Filing Portal: {pri['election']}, Statewide, State Legislature and Judicial offices",
         PAGE, "", lists.get("fetched") or mdate(lpath), sha_of(lpath), len(pri["rows"]),
         "Used to check the canvass: every name under a contest is on the primary list for that office, district, seat and party, and "
         "every Approved name is under its contest. Independents file in the primary period but are not on a primary ballot. Alone on a "
         "party's primary list with no contest in the canvass: " + (", ".join(f"{r} {c}" for r, c in no_contest) or "none") + "."
         + (f" Marked Withdrawn on the primary list but under a contest in the canvass: {'; '.join(late_withdrawn)}." if late_withdrawn else "")
         + (" Did not reconcile: " + "; ".join(unmatched) + "." if unmatched else "")),
        (SRC_CANVASS, STATE, "official results", "Idaho Secretary of State, Elections Division",
         "Canvass Report, Primary Election - May 19, 2026 (Idaho Detailed Results by Contest)", CANVASS_URL, "", mdate(cpath), sha_of(cpath),
         n_field_rows,
         f"{len(contests)} state and judicial contests read ({n_federal} pages of federal contests left to the federal loader). Votes from each "
         "contest's Contest Total row; the county rows add up to it, and each county row's candidates, over votes and under votes add up to "
         "its votes cast. No write-in column is printed for these contests, so a field's total is its candidates' votes; over and under votes "
         "are left out. Kept for races on the November ballot where two or more were on a primary ballot."
         + (" Counts printed ** (\"Protected\"), left out of their rows' sums and checked only to be no more than the Contest Total: "
            + "; ".join(protected) + "." if protected else "")),
        (SRC_ROSTER, STATE, "roster", "Open States people project (CC0)",
         "Idaho legislators and statewide officials, as loaded into state_id.sqlite", "https://github.com/openstates/people",
         as_of, as_of, "", sum(len(v) for v in seats.values()) + len(offices),
         "Today's holder of each seat and office (ids, names, parties and districts only). The roster does not carry the State Controller, "
         "the State Treasurer or the Superintendent of Public Instruction."),
        (SRC_COUNTIES, STATE, "official boundaries", "U.S. Census Bureau",
         "Cartographic boundary file, counties, 2024, 1:500,000 (cb_2024_us_county_500k)", COUNTY_URL, "", mdate(COUNTY_ZIP),
         sha_of(COUNTY_ZIP), len(place_rows), "Idaho's 44 counties: names and GEOIDs only."),
    ]

    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA)
    with con:
        con.execute("DELETE FROM sl_candidates WHERE race_id IN (SELECT race_id FROM sl_races WHERE state = ?) OR race_id LIKE ?",
                    (STATE, f"2026-{STATE}-%"))
        con.execute("DELETE FROM sl_races WHERE state = ?", (STATE,))
        con.execute("DELETE FROM sl_places WHERE source_id LIKE 'id-%' OR (kind = 'county' AND id GLOB '16[0-9][0-9][0-9]')")
        con.execute("DELETE FROM sl_sources WHERE state = ?", (STATE,))
        con.executemany("INSERT INTO sl_races VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", race_rows)
        con.executemany("INSERT INTO sl_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", cand)
        con.executemany("INSERT INTO sl_places VALUES (?,?,?,?,?)", place_rows)
        con.executemany("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", src)
    con.close()

    # ---- the report: counts only
    kind_of = lambda rid: races[rid]["office_kind"] if races[rid]["level"] == "legislature" else races[rid]["level"]
    by = Counter(kind_of(rid) for rid in races)
    g = Counter(kind_of(c[0]) for c in cand if c[1] == "general")
    alone = Counter(kind_of(rid) for rid, v in gen_n.items() if v == 1)
    inc = Counter(kind_of(c[0]) for c in cand if c[1] == "general" and c[7])
    judges = f", {by['court']} judge's seat{'s' if by['court'] != 1 else ''}" if by["court"] else ""
    say(f"    Idaho (state races): {by['state_senate']} Senate seats, {by['state_house']} House seats, {by['statewide']} statewide offices"
        f"{judges}; "
        f"{g.total()} candidates on the November ballot (Senate {g['state_senate']}, House {g['state_house']}, statewide {g['statewide']}"
        f"{', court ' + str(g['court']) if g['court'] else ''}; {len(gone)} withdrawn left off; {len(write_ins)} declared write-in; unopposed: "
        f"Senate {alone['state_senate']}, House {alone['state_house']}, statewide {alone['statewide']}); sitting member on the ballot: "
        f"Senate {inc['state_senate']}, House {inc['state_house']}, statewide {inc['statewide']}; May 19 fields: Senate "
        f"{fields['state_senate']}, House {fields['state_house']}, statewide {fields['statewide']}, court {fields['court']} "
        f"({n_field_rows} rows, official votes from the canvass)")
    for label, items in (("the November nominee is not the primary's top vote-getter", upset), ("primary fields left open", open_)):
        if items:
            say(f"    CHECK Idaho (state races): {label}: {', '.join(items)}")
    for c in checks:
        say(f"    CHECK Idaho (state races): {c}")
    return len(cand)


if __name__ == "__main__":
    args = sys.argv[1:]
    cache = CACHE
    if "--cache" in args:
        i = args.index("--cache")
        cache = args[i + 1]
        del args[i:i + 2]
    if len(args) != 1:
        raise SystemExit("usage: python ballot/state_local_id.py <database file> [--cache <folder>]")
    load(args[0], cache=cache)
