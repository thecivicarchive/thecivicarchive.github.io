"""
ballot/state_local_pa.py - Pennsylvania's state races on the November 3, 2026 ballot, into the state-and-local ballot
database (ballot_local_2026.sqlite, or a test copy). The federal ballot database (ballot_2026.sqlite) is never opened.

What is on the ballot. Governor and Lieutenant Governor (one vote for the pair in November; each party nominates them in
separate May 19 primaries), the 25 even-numbered State Senate seats (four-year terms: the even-numbered districts are
elected in the governor's year, the odd-numbered in 2028; the Department's list for November carries only the even ones,
and the loader stops to say so if that changes) and all 203 seats of the House of Representatives. The Department's list
carries no other state office this year (the row offices were last elected in 2024; judges are elected in odd-numbered
years); an office it does not know is reported, never guessed at. Party state committee members, on the same list, are
party offices chosen in the primary and are not read.

Sources (the candidates and votes are all the Department of State's own):
  - PA Voter Services, Election Information for the 2026 General Election (the page ballot/lists/pa.py reads): every
    candidate is data in one hidden field (dataJson). Kept, as the federal loader keeps them: candidate id, name, party,
    status (Approved, Withdrawn, Terminated, Inactive-CrossFiled), how the candidate got there (Petition, a party primary;
    Write-in, a party primary won with write-in votes; Substitute, named by the party to replace a nominee; Paper,
    nomination papers for minor parties and independents), office, district, election, primary result, general result.
    The rows also carry each candidate's municipality and county of residence; those are dropped as the page is read,
    before anything is kept, and never printed or stored. The November ballot is every Approved candidate who came by
    Paper, or who won the primary (Petition, Write-in or Substitute). A cross-filed candidate (one who won two parties'
    primaries) is one row with the list's own joint label, "Democratic / Republican"; the second party's row, marked
    Inactive-CrossFiled, is read only to say which nomination came by write-in.
  - Pennsylvania Election Returns (electionreturns.pa.gov), the 2026 General Primary (election 117), used only because
    the site's own election list marks its returns Official: the statewide total of every printed candidate in each
    party's primary for Governor (office 3), Lieutenant Governor (4), Senator in the General Assembly (12) and
    Representative in the General Assembly (13), from the data call its Office Results page makes, and every district's
    county breakdown from the call its county view makes (GetCountyBreak, one request a district, a pause between each,
    kept in ballot_cache/pa/ so none is asked twice). Checks: election-day, mail and provisional votes add up to every
    total, and every candidate's counties add up to the statewide total. The counties a district reaches are the counties
    its breakdown lists. The Reporting Center's exports sit behind a reCAPTCHA and are never asked for.
  - Who holds each seat today: the Open States roster in state_pa.sqlite (legislators, is_current = 1; the officials
    table for Governor and Lieutenant Governor). Only ids, names and party are read.
  - County codes: the Census Bureau's 2024 county file (states_cache/census/cb_2024_us_county_500k.zip).

Fields. A party's primary is a field when its primary ballot printed two names or more (the federal rule). The returns
carry no write-in votes, so percentages are of the printed candidates' votes; who advanced is the list's PrimaryResult,
checked against the top vote-getter. Names are shown as the Department's list files them, turned first name first and
into ordinary capitals (a sitting member's family name in the roster's capitals); a returns name not on the list is
shown in ordinary capitals with a note. No ballot order is stored: the list gives no ballot positions.

Matching. The returns print ballot names (MARTY FLYNN for FLYNN, MARTIN B); each is tied to the list's row for the same
district and party by family name, then by the list's family name among the ballot name's words (SHARON SOLTIS SPARANO),
then by the names fitting, and last by elimination: the one row left in the party's primary whose given name fits
(NATALIE MIHALEK for STUCK, NATALIE NICOLE), which is printed for reading and noted on the row. A sitting member is the
candidate whose name fits the roster's (same chamber and district, one fit only); where none does, the candidate whose
own primary ballot name fits the member (Mindy Fee for Melinda S Fee; an apostrophe may be dropped, ONEAL for O'Neal), printed for
reading and noted with the ballot name.

Privacy. Nothing but office, district, name, party, status, primary result and votes is read into anything kept; the
last step checks every stored name and note for anything that looks like a contact detail and stops, naming the race
only, if one does.

    python -m ballot.state_local_pa --db <path to a test database> [--no-fetch]
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
from urllib.error import HTTPError, URLError

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from ballot.common import fold, name_parts, party_code  # noqa: E402
from ballot.lists import pa as fed  # noqa: E402
from ballot.lists.tx import proper  # noqa: E402
from ballot.match import fits  # noqa: E402
from states import net  # noqa: E402
from states.money_mn import given_fits  # noqa: E402

STATE, FIPS, NAME = "PA", "42", "Pennsylvania"
GENERAL, PRIMARY = "2026-11-03", fed.PRIMARY
CACHE = os.path.join(HERE, "ballot_cache")
FOLDER = os.path.join(CACHE, "pa")
LIST_PATH = os.path.join(CACHE, "pa_electioninfo_2026_general.json")     # the same kept columns the federal loader writes
ROSTER = os.path.join(HERE, "state_pa.sqlite")
COUNTY_ZIP = os.path.join(HERE, "states_cache", "census", "cb_2024_us_county_500k.zip")
COUNTY_URL = "https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_county_500k.zip"
KEEP = ("CandidateIDNum", "CandidateName", "PartyName", "CandidateStatusValue", "CandidateTypeValue", "OfficeName", "DistrictName",
        "ElectionName", "PrimaryResult", "GeneralResult")

RETURNS = fed.RETURNS
ELECTION = fed.PRIMARY_ID
OFFICE_URL = (RETURNS + "api/ElectionReturn/GetOfficeData?officeId={o}&methodName=GetOfficeDetails&electionid=" + str(ELECTION)
              + "&electiontype=P&isactive=0")
COUNTY_BREAK_URL = (RETURNS + "api/ElectionReturn/GetCountyBreak?officeId={o}&districtId={d}&methodName=GetCountyBreak&electionid="
                    + str(ELECTION) + "&electiontype=P&isactive=0")
OFFICE_PAGE = RETURNS + "General/OfficeResults?OfficeID={o}&ElectionID=" + str(ELECTION) + "&ElectionType=P&IsActive=0"
COUNTY_FILE = os.path.join(FOLDER, "pa_primary_2026_state_offices_by_county.json")

# the list's office -> (race key, returns office id, the returns' office name, office_kind, office shown)
OFFICES = {
    "GOVERNOR": ("GOV", 3, "Governor", "governor", "Governor and Lieutenant Governor"),
    "LIEUTENANT GOVERNOR": ("LTG", 4, "Lieutenant Governor", "lieutenant_governor", "Lieutenant Governor"),
    "SENATOR IN THE GENERAL ASSEMBLY": ("SS", 12, "Senator in the General Assembly", "state_senate", "State Senator"),
    "REPRESENTATIVE IN THE GENERAL ASSEMBLY": ("SH", 13, "Representative in the General Assembly", "state_house", "State Representative"),
}
NOT_READ = {"REPRESENTATIVE IN CONGRESS": "federal (the federal pages)", "MEMBER OF REPUBLICAN STATE COMMITTEE": "party office",
            "MEMBER OF DEMOCRATIC STATE COMMITTEE": "party office"}
SENATE_UP = list(range(2, 51, 2))
HOUSE_SEATS = 203
CODE = {"Democratic": "DEM", "Republican": "REP"}
SRC_LIST = "pa-dos-2026-electioninfo"
SRC_ELECTIONS = "pa-dos-returns-election-list"
SRC_RET = {3: "pa-dos-2026-primary-governor", 4: "pa-dos-2026-primary-lt-governor", 12: "pa-dos-2026-primary-state-senate",
           13: "pa-dos-2026-primary-state-house"}
SRC_BY_COUNTY = "pa-dos-2026-primary-state-by-county"
SRC_COUNTY = "pa-census-2024-county-codes"
SRC_ROSTER = "pa-openstates-roster"
NOT_A_NAME = re.compile(r"\d|@|www\.|https?:|\.com\b|\bBox\b", re.I)

SCHEMA = """
CREATE TABLE IF NOT EXISTS sl_races (race_id TEXT PRIMARY KEY, state TEXT NOT NULL, level TEXT NOT NULL, office_kind TEXT NOT NULL,
  office TEXT NOT NULL, jurisdiction TEXT, jurisdiction_id TEXT, county_ids TEXT, district TEXT, seat TEXT,
  special INTEGER NOT NULL DEFAULT 0, partisan INTEGER NOT NULL, holder_id TEXT, holder_name TEXT, holder_party TEXT,
  election_date TEXT NOT NULL, note TEXT);
CREATE TABLE IF NOT EXISTS sl_candidates (race_id TEXT NOT NULL, election TEXT NOT NULL, election_date TEXT, name TEXT NOT NULL,
  party TEXT, party_code TEXT, ballot_order INTEGER, incumbent INTEGER NOT NULL DEFAULT 0, write_in INTEGER NOT NULL DEFAULT 0,
  votes INTEGER, pct REAL, outcome TEXT, state_member_id TEXT, source_id TEXT, note TEXT, PRIMARY KEY (race_id, election, name));
CREATE TABLE IF NOT EXISTS sl_sources (source_id TEXT PRIMARY KEY, state TEXT, kind TEXT, agency TEXT, title TEXT, url TEXT,
  published TEXT, fetched TEXT, sha256 TEXT, rows INTEGER, note TEXT);
CREATE TABLE IF NOT EXISTS sl_places (kind TEXT NOT NULL, id TEXT NOT NULL, name TEXT NOT NULL, county_ids TEXT, source_id TEXT,
  PRIMARY KEY (kind, id));
"""


class Blocked(Exception):
    """A data call that would not answer with data (an error page, a challenge, nothing)."""


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def fetched(path):
    return dt.datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d")


def fresh(path, days):
    return os.path.exists(path) and os.path.getsize(path) > 0 and time.time() - os.path.getmtime(path) < days * 86400


# ---------------------------------------------------------------- the candidate list

def read_list(fetch, say):
    """The Election Information rows, cut to KEEP. With fetch, the page is asked again when the kept copy is a day old;
    the residence columns are dropped from every row before anything is written."""
    if fetch and not fresh(LIST_PATH, 1):
        net.patient_lookups()
        page = net.get(fed.URL).decode("utf-8", "replace")
        m = re.search(r"id='dataJson'[^>]*value='(.*?)'\s*/?>", page, re.S) or re.search(r'id="dataJson"[^>]*value="(.*?)"\s*/?>', page, re.S)
        if not m:
            raise SystemExit("Pennsylvania (state races): the Election Information page no longer carries its dataJson field")
        kept = [{k: r.get(k) for k in KEEP} for r in json.loads(H.unescape(m.group(1)))]
        del page, m
        with open(LIST_PATH + ".part", "w", encoding="utf-8") as fh:
            json.dump(kept, fh, ensure_ascii=False)
        os.replace(LIST_PATH + ".part", LIST_PATH)
        say(f"    Pennsylvania: Election Information page read afresh ({len(kept)} rows, residence columns dropped)")
    rows = [{k: r.get(k) for k in KEEP} for r in json.load(open(LIST_PATH, encoding="utf-8"))]
    elections = {r["ElectionName"] for r in rows}
    if elections != {"2026 General Election"}:
        raise SystemExit(f"Pennsylvania (state races): expected the 2026 General Election on the list, it gives {sorted(elections)}")
    return rows


def display(raw):
    """SHAPIRO, JOSHUA D -> Joshua D Shapiro; MOYER JR, WAYNE R -> Wayne R Moyer Jr."""
    return proper(re.sub(r"\s+", " ", fed.first_last(re.sub(r"\s+", " ", raw or "").strip())).strip())


def race_of(office, district):
    """The list's (or the returns') office and district -> race id; None for offices not read here."""
    key = OFFICES[office][0]
    d = (district or "").strip()
    if key in ("GOV", "LTG"):
        if d != "Statewide":
            raise SystemExit(f"Pennsylvania (state races): {office} filed under {d!r}, not Statewide")
        return f"2026-{STATE}-{key}"
    word = "Senatorial" if key == "SS" else "Legislative"
    m = re.fullmatch(r"(\d{1,3})(?:st|nd|rd|th) " + word + r" District", d)
    if not m:
        raise SystemExit(f"Pennsylvania (state races): a {office.title()} district this loader does not know: {d!r}")
    return f"2026-{STATE}-{key}{int(m.group(1))}"


def parties(label):
    return [p.strip() for p in (label or "").split(" / ") if p.strip()]


def is_true(v):
    return str(v).lower() == "true"


# ---------------------------------------------------------------- the official primary returns

def data_call(url, path, days, say):
    """One of the returns site's data calls, parsed; kept on disk (the raw answer holds only offices, districts, parties,
    ballot names and votes). Three tries at most, then Blocked."""
    if fresh(path, days):
        return fed.unjson(open(path, "rb").read())
    net.patient_lookups()
    last = ""
    for attempt in range(3):
        if attempt:
            time.sleep(5 * attempt)
        try:
            raw = net.get(url, timeout=90, accept="application/json, text/plain, */*")
        except HTTPError as e:
            last = f"HTTP {e.code}"
            continue
        except (URLError, OSError) as e:
            last = str(e)
            continue
        head = raw[:64].lstrip(b"\xef\xbb\xbf \r\n\t")
        if raw.strip() in (b'""', b"", b"null"):
            last = "an empty answer"
            continue
        if not head.startswith((b'"', b"{", b"[")):
            last = f"not JSON (it began {head[:12]!r})"
            continue
        try:
            parsed = fed.unjson(raw)
        except ValueError:
            last = "not JSON"
            continue
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path + ".part", "wb") as fh:
            fh.write(raw)
        os.replace(path + ".part", path)
        return parsed
    raise Blocked(f"{url} gave {last} three times")


def official_status(say):
    """(path, why not): the site's election list must mark the 2026 General Primary Official."""
    path = os.path.join(FOLDER, fed.LIST_FILE)
    t = data_call(fed.ELECTIONS_URL, path, 7, say)
    status = [r for r in t.get("Table", []) if r.get("Electionid") == ELECTION and r.get("ElectionType") == "P"]
    if len(status) != 1 or status[0].get("ElectionName") != "2026 General Primary" or status[0].get("ElectionDate") != "05/19/2026":
        return path, f"the returns site's election list no longer shows the 2026 General Primary as election {ELECTION}"
    if status[0].get("ElectionStatus") != "O":
        return path, f"the returns site still marks the 2026 General Primary unofficial (status {status[0].get('ElectionStatus')})"
    return path, ""


def office_returns(office, say, problems):
    """{race: {party: [(ballot name, votes)]}}, {race: district id on the site}, path, rows."""
    key, oid, oname, _k, _o = OFFICES[office]
    path = os.path.join(FOLDER, f"pa_primary_2026_office{oid}_returns.json")
    t = data_call(OFFICE_URL.format(o=oid), path, 30, say)
    blocks = (t.get("Election") or {}).get(oname)
    if not blocks:
        raise Blocked(f"the returns for {oname} carry no results")
    got, ids, n = {}, {}, 0
    for block in blocks:
        for _label, districts in block.items():
            for d in districts:
                rid = race_of(office, d.get("District"))
                ids[rid] = str(d.get("DistrictId"))
                for pdict in d.get("Candidates") or []:
                    for party, cands in pdict.items():
                        for c in cands:
                            if c.get("PartyName") != party or c.get("OfficeName") != oname:
                                raise SystemExit(f"Pennsylvania (state races): a row of the {oname} returns for {rid} is filed under "
                                                 "the wrong party or office")
                            name, votes = re.sub(r"\s+", " ", c["CandidateName"]).strip(), int(c["Votes"])
                            parts = sum(int(c.get(k) or 0) for k in ("ElectionDayVotes", "MailInVotes", "ProvisionalVotes"))
                            if parts != votes:
                                problems.append(f"{rid} {party} {name}: election-day, mail and provisional votes add up to {parts:,}, "
                                                f"the total says {votes:,}")
                            got.setdefault(rid, {}).setdefault(party, []).append((name, votes))
                            n += 1
    return got, ids, path, n


def county_breaks(wanted, say):
    """{(office id, district id): {"district": name, "rows": [[county, party, ballot name, votes]]}} from the site's county
    view, one request a district, kept in COUNTY_FILE as it goes (only these four cells of each row are kept)."""
    have = json.load(open(COUNTY_FILE, encoding="utf-8")) if os.path.exists(COUNTY_FILE) else {}
    todo = [(o, d) for o, d in wanted if f"{o}|{d}" not in have]
    if todo:
        say(f"    Pennsylvania: asking the returns site for {len(todo)} county breakdowns, one at a time")
        net.patient_lookups()
    blocked = ""
    for i, (o, d) in enumerate(todo):
        url = COUNTY_BREAK_URL.format(o=o, d=d)
        last = ""
        for attempt in range(3):
            if attempt:
                time.sleep(5 * attempt)
            try:
                raw = net.get(url, timeout=90, accept="application/json, text/plain, */*")
                t = fed.unjson(raw) if raw[:64].lstrip(b"\xef\xbb\xbf \r\n\t").startswith((b'"', b"{", b"[")) and raw.strip() != b'""' else None
            except HTTPError as e:
                last, t = f"HTTP {e.code}", None
            except (URLError, OSError, ValueError) as e:
                last, t = str(e)[:80], None
            if isinstance(t, dict) and t.get("Election"):
                break
            last = last or "no data"
        else:
            blocked = f"the county view for office {o}, district {d} gave {last} three times"
            break
        rows, names = [], set()
        for dname, blocks in t["Election"].items():
            names.add(dname)
            for block in blocks:
                for county, plist in block.items():
                    for pdict in plist:
                        for party, cands in pdict.items():
                            for c in cands:
                                rows.append([c["CountyName"], c["PartyName"], re.sub(r"\s*\([A-Z]{2,4}\)\s*$", "",
                                             re.sub(r"\s+", " ", c["CandidateName"]).strip()), int(c["Votes"])])
        have[f"{o}|{d}"] = {"district": sorted(names)[0] if len(names) == 1 else " | ".join(sorted(names)), "rows": rows}
        if (i + 1) % 25 == 0 or i == len(todo) - 1:
            with open(COUNTY_FILE + ".part", "w", encoding="utf-8") as fh:
                json.dump(have, fh, ensure_ascii=False)
            os.replace(COUNTY_FILE + ".part", COUNTY_FILE)
            say(f"      {i + 1} of {len(todo)} county breakdowns")
        time.sleep(0.6)
    if todo and have:
        with open(COUNTY_FILE + ".part", "w", encoding="utf-8") as fh:
            json.dump(have, fh, ensure_ascii=False)
        os.replace(COUNTY_FILE + ".part", COUNTY_FILE)
    return have, blocked


# ---------------------------------------------------------------- roster, counties, names

def roster(path=ROSTER):
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    members = {}
    for mid, full, first, last, other, party, district, chamber in con.execute(
            "SELECT bioguide_id, official_full, first_name, last_name, other_names, party_name, district, chamber "
            "FROM legislators WHERE is_current = 1"):
        members.setdefault((chamber, str(int(district))), []).append(
            dict(id=mid, name=full or f"{first} {last}", first=first or "", last=last or "", other=other or "", party=party))
    officials = {o: dict(id=i, name=n, first=f or "", last=l or "", other="", party=p) for i, n, f, l, o, p in con.execute(
        "SELECT bioguide_id, official_full, first_name, last_name, office, party_name FROM officials")}
    con.close()
    return members, officials


def census_counties(path=COUNTY_ZIP):
    """{COUNTY NAME IN CAPITALS: five-digit code} for Pennsylvania's 67 counties."""
    import shapefile
    z = zipfile.ZipFile(path)
    base = next(n for n in z.namelist() if n.endswith(".dbf"))
    rdr = shapefile.Reader(dbf=io.BytesIO(z.read(base)))
    return {r["NAME"].upper(): (r["GEOID"], r["NAME"]) for r in (x.as_dict() for x in rdr.iterRecords()) if r["STATEFP"] == FIPS}


def person(name):
    """The first person of a ticket, as (given names, family name)."""
    return name_parts(name.split(" / ")[0])


def member_forms(m):
    """The ways a member's name may be written; an apostrophe may be dropped (O'Neal is ONEAL on the returns and the list)."""
    forms = [(fold(m["first"]).split(), fold(m["last"]))] if m.get("last") else []
    if "'" in (m.get("last") or "") or "’" in (m.get("last") or ""):
        forms.append((fold(m["first"]).split(), fold(re.sub("['’]", "", m["last"]))))
    forms.append(name_parts(m["name"]))
    for o in (m.get("other") or "").split(";"):
        o = o.strip()
        if o and not re.search(r"\b[A-Z]\.$|^[A-Z]\.", o):
            forms.append(name_parts(o))
    return forms


def find_incumbent(names, member):
    """The one name that fits the sitting member, or None (none fit, or more than one)."""
    if not member:
        return None
    forms = member_forms(member)
    hits = [n for n in names if any(fits(person(n), f) for f in forms)]
    return hits[0] if len(set(hits)) == 1 else None


def roster_caps(name, member):
    """A sitting member's family name in the roster's capitals (Digirolamo -> DiGirolamo); only the case changes."""
    last = (member or {}).get("last") or ""
    if not last:
        return name
    words = name.split(" ")
    lw = last.split(" ")
    for i in range(len(words) - len(lw) + 1):
        if [w.lower() for w in words[i:i + len(lw)]] == [w.lower() for w in lw]:
            return " ".join(words[:i] + lw + words[i + len(lw):])
    return name


def family(name):
    return fed.family(name)


def match_printed(printed, listed):
    """Each printed name on the returns -> (ballot name, votes, the list row or None, how). The returns print the ballot name
    (MARTY FLYNN for FLYNN, MARTIN B; SHARON SOLTIS SPARANO for SOLTIS, SHARON; NATALIE MIHALEK for STUCK, NATALIE NICOLE).
    In order: the same family name, unique in the party's primary; the list's family name among the ballot name's words and
    a given name that fits; the names fit; and last, the one list row left in the party's primary whose first given name
    fits (printed for reading)."""
    out, used = [], set()
    for ballot, votes in printed:
        words = set(re.sub(r"[^A-Z -]", "", ballot.upper()).split())
        how = "family name"
        hit = [c for c in listed if family(c["name"]) == family(ballot)]
        if len(hit) > 1:
            hit = [c for c in hit if fits(name_parts(ballot), name_parts(c["name"]))]
        if len(hit) != 1:
            how = "family name among the ballot name's words"
            hit = [c for c in listed if family(c["name"]) in words and given_ok(ballot, c["name"])]
        if len(hit) != 1:
            how = "names fit"
            hit = [c for c in listed if fits(name_parts(ballot), name_parts(c["name"]))]
        c = hit[0] if len(hit) == 1 and id(hit[0]) not in used else None
        if c:
            used.add(id(c))
        out.append([ballot, votes, c, how if c else ""])
    for m in out:
        if m[2]:
            continue
        left = [c for c in listed if id(c) not in used and given_ok(m[0], c["name"])]
        if len(left) == 1:
            m[2], m[3] = left[0], "given name only, the one list row left in the party's primary"
            used.add(id(left[0]))
    return [tuple(m) for m in out]


def given_ok(ballot, listed_name):
    g1, g2 = name_parts(ballot)[0], name_parts(listed_name)[0]
    return bool(g1 and g2) and given_fits(g1[0], g2[0])


def ballot_fits(ballot, member):
    return bool(member) and any(fits(name_parts(ballot), f) for f in member_forms(member))


def printed_for(c, party, race_rows):
    """Was this list row a printed name in the party's primary? A petition candidate, except for the party whose nomination a
    cross-filed candidate won with write-in votes (the list then carries an Inactive-CrossFiled Write-in row for it)."""
    if c["type"] != "Petition":
        return False
    return not (len(parties(c["party"])) > 1 and any(
        x["status"] == "Inactive-CrossFiled" and x["type"] == "Write-in" and parties(x["party"]) == [party] and fold(x["name"]) == fold(c["name"])
        for x in race_rows))


# ---------------------------------------------------------------- the load

def load(db_path, say=print, fetch=True, roster_db=ROSTER, county_zip=COUNTY_ZIP):
    problems, checks = [], []

    # 1. the candidate list, state offices only
    rows = read_list(fetch, say)
    left_out = {}
    mine, seen_ids = [], set()
    for r in rows:
        office = (r["OfficeName"] or "").strip()
        if office not in OFFICES:
            why = NOT_READ.get(office)
            if not why:
                problems.append(f"an office on the list this loader does not know: {office!r} (not read)")
                why = "unknown office"
            left_out[why] = left_out.get(why, 0) + 1
            continue
        ident = (r["CandidateIDNum"], office, (r["DistrictName"] or "").strip(), r["PartyName"])
        if ident in seen_ids:           # the page repeats a row now and then (the same candidate id twice)
            continue
        seen_ids.add(ident)
        rid = race_of(office, r["DistrictName"])
        mine.append(dict(race=rid, office=office, id=r["CandidateIDNum"], name=display(r["CandidateName"]), party=(r["PartyName"] or "").strip(),
                         status=r["CandidateStatusValue"], type=r["CandidateTypeValue"], won=is_true(r["PrimaryResult"])))
    statuses = {c["status"] for c in mine} - {"Approved", "Withdrawn", "Terminated", "Inactive-CrossFiled"}
    types = {c["type"] for c in mine} - {"Petition", "Paper", "Write-in", "Substitute"}
    if statuses or types:
        raise SystemExit(f"Pennsylvania (state races): the list has statuses {sorted(statuses)} or types {sorted(types)} this loader "
                         "does not know; read them before going on")

    def on_november(c):
        return c["status"] == "Approved" and (c["type"] == "Paper" or (c["won"] and c["type"] in ("Petition", "Write-in", "Substitute")))

    senate_listed = sorted({int(c["race"].split("SS")[1]) for c in mine if "-SS" in c["race"]})
    if senate_listed != SENATE_UP:
        raise SystemExit(f"Pennsylvania (state races): the list's Senate districts are {senate_listed}, not the even-numbered 25; "
                         "check which half of the Senate is elected this year")
    house_listed = sorted({int(c["race"].split("SH")[1]) for c in mine if "-SH" in c["race"]})
    if house_listed != list(range(1, HOUSE_SEATS + 1)):
        problems.append(f"House districts on the list: {len(house_listed)} of {HOUSE_SEATS} "
                        f"(missing {sorted(set(range(1, HOUSE_SEATS + 1)) - set(house_listed))})")

    # 2. the official primary returns and their county breakdowns
    members, officials = roster(roster_db)
    counties = census_counties(county_zip)
    if len(counties) != 67:
        raise SystemExit(f"Pennsylvania (state races): the Census file gives {len(counties)} counties, not 67")
    returns, ret_ids, ret_files, blocked = {}, {}, {}, []
    try:
        elist, why = official_status(say)
    except Blocked as e:
        elist, why = None, str(e)
        blocked.append(f"election list: {e}")
    if not why:
        for office in OFFICES:
            try:
                got, ids, path, n = office_returns(office, say, problems)
            except Blocked as e:
                blocked.append(f"{OFFICES[office][2]} returns: {e}")
                continue
            returns.update(got)
            ret_ids.update({rid: (OFFICES[office][1], d) for rid, d in ids.items()})
            ret_files[OFFICES[office][1]] = (path, n)
    else:
        checks.append(f"primary votes not stored: {why}")
    breaks, cblocked = ({}, "")
    if ret_ids:
        breaks, cblocked = county_breaks(sorted(set(ret_ids.values())), say)
        if cblocked:
            blocked.append(f"county breakdowns: {cblocked}")
    reach, sums, bad_county = {}, {}, set()
    for rid, (o, d) in ret_ids.items():
        b = breaks.get(f"{o}|{d}")
        if not b:
            continue
        for county, party, name, votes in b["rows"]:
            if county.upper() not in counties:
                bad_county.add(county)
                continue
            reach.setdefault(rid, set()).add(counties[county.upper()][0])
            k = (rid, party, name)
            sums[k] = sums.get(k, 0) + votes
    if bad_county:
        problems.append(f"county names in the breakdowns that are not in the Census file: {sorted(bad_county)}")
    n_checked = 0
    for rid, byp in returns.items():
        if f"{ret_ids[rid][0]}|{ret_ids[rid][1]}" not in breaks:
            continue
        for party, cands in byp.items():
            for name, votes in cands:
                n_checked += 1
                if sums.get((rid, party, name)) != votes:
                    problems.append(f"{rid} {party} {name}: counties add up to {sums.get((rid, party, name), 0):,}, the statewide total is {votes:,}")
    extra = {k for k in sums if k[2] not in [n for n, _v in returns.get(k[0], {}).get(k[1], [])]}
    if extra:
        problems.append(f"{len(extra)} county-breakdown candidates not on the statewide returns: {sorted(extra)[:5]}")

    # 3. the races
    race_ids = [f"2026-{STATE}-GOV", f"2026-{STATE}-LTG"] + [f"2026-{STATE}-SS{d}" for d in SENATE_UP] + \
               [f"2026-{STATE}-SH{d}" for d in range(1, HOUSE_SEATS + 1)]
    by_race = {}
    for c in mine:
        by_race.setdefault(c["race"], []).append(c)
    races, holders, notes = {}, {}, {}
    for rid in race_ids:
        key = rid.split(f"-{STATE}-", 1)[1]
        note, holder, district, jur, jur_id, cids = [], None, None, NAME, FIPS, None
        if key == "GOV":
            kind, office, level = "governor", "Governor and Lieutenant Governor", "statewide"
            holder = officials.get("governor")
            note.append("Pennsylvania elects the Governor and Lieutenant Governor together in November, one vote for the pair; each party "
                        f"nominates them in separate primaries (the Lieutenant Governor's fields are under 2026-{STATE}-LTG). Each ticket is "
                        "written governor first.")
            if officials.get("lt_governor"):
                note.append(f"Lieutenant Governor today: {officials['lt_governor']['name']}.")
        elif key == "LTG":
            kind, office, level = "lieutenant_governor", "Lieutenant Governor", "statewide"
            holder = officials.get("lt_governor")
            note.append("Nominated in each party's own primary on May 19; in November the Lieutenant Governor is elected jointly with the "
                        f"Governor, on the tickets listed under 2026-{STATE}-GOV. This race holds the primary fields only.")
        else:
            senate = key.startswith("SS")
            chamber = "Senate" if senate else "House"
            district = key[2:]
            kind = "state_senate" if senate else "state_house"
            office = "State Senator" if senate else "State Representative"
            level = "legislature"
            jur, jur_id = f"{chamber} District {district}", f"{STATE}-{district}"
            sitting = members.get((chamber, district), [])
            holder = sitting[0] if len(sitting) == 1 else None
            if not sitting:
                note.append("The roster shows no one holding this seat today.")
                checks.append(f"{rid}: no sitting member on the roster")
            elif len(sitting) > 1:
                problems.append(f"{rid}: {len(sitting)} sitting members on the roster; none is taken as the holder")
            if senate:
                note.append("Pennsylvania's senators serve four-year terms; the even-numbered districts are elected in 2026, the odd-numbered "
                            "in 2028.")
            if rid in reach:
                cids = json.dumps(sorted(reach[rid]))
            else:
                checks.append(f"{rid}: no county breakdown on the returns, so the counties the district reaches are not stored")
        holders[rid] = holder
        notes[rid] = note
        races[rid] = [rid, STATE, level, kind, office, jur, jur_id, cids, district, None, 0, 1,
                      holder["id"] if holder else None, holder["name"] if holder else None, holder["party"] if holder else None,
                      GENERAL, None]

    # 4. the returns' printed names matched to the list, and the sitting member's own ballot name
    pool = {}
    for c in mine:
        for p in parties(c["party"]):
            pool.setdefault((c["race"], p), []).append(c)
    ret_match, loose = {}, []
    for rid in race_ids:
        for party, printed in returns.get(rid, {}).items():
            listed = [c for c in pool.get((rid, party), []) if printed_for(c, party, by_race.get(rid, []))]
            ret_match[(rid, party)] = match_printed(printed, listed)
            for ballot, _v, c, how in ret_match[(rid, party)]:
                if c and how.startswith("given name only"):
                    loose.append(f"{rid} {party}: the returns' {ballot} taken as the list's {c['name']} ({how})")

    def bridge(rid, holder):
        """(party, ballot name, list row) when exactly one printed name in the race's primaries fits the sitting member."""
        hits = [(p, b, c) for (r, p), ms in ret_match.items() if r == rid for b, _v, c, _h in ms if c and ballot_fits(b, holder)]
        return hits[0] if len(hits) == 1 else None

    # 5. November candidates
    cands, general_expected = [], 0
    nov = {rid: [c for c in by_race.get(rid, []) if on_november(c)] for rid in race_ids}
    for rid in race_ids:
        general_expected += len(nov[rid]) if not rid.endswith("-LTG") else 0
    tickets = []
    mates = {c["party"]: c for c in nov[f"2026-{STATE}-LTG"]}
    for g in nov[f"2026-{STATE}-GOV"]:
        mate = mates.pop(g["party"], None)
        if not mate:
            problems.append(f"2026-{STATE}-GOV: no {g['party']} candidate for Lieutenant Governor on the list to pair with {g['name']}")
        tickets.append(dict(g, name=f"{g['name']} / {mate['name']}" if mate else g["name"], mate=mate))
    for p, mate in mates.items():
        problems.append(f"2026-{STATE}-LTG: {mate['name']} ({p}) has no candidate for Governor of the same party on the list")
    nov[f"2026-{STATE}-GOV"] = tickets

    cross = {}
    for c in mine:
        if c["status"] == "Inactive-CrossFiled":
            cross.setdefault((c["race"], fold(c["name"])), []).append(c)
    for rid in race_ids:
        if rid.endswith("-LTG"):
            continue
        here = nov[rid]
        holder = holders[rid]
        if not here:
            problems.append(f"{rid}: no candidate on the Department's list for the November ballot")
            notes[rid].append("No candidate is on the Department of State's list for this seat.")
        inc = find_incumbent([c["name"] for c in here], holder)
        via = None
        if holder and not inc and not rid.endswith("-GOV"):
            b = bridge(rid, holder)
            if b and any(c["id"] == b[2]["id"] for c in here):
                inc, via = b[2]["name"], proper(b[1])
                loose.append(f"{rid}: sitting member {holder['name']} taken as the list's {inc}, through the {b[0]} primary ballot name {b[1]}")
        seen = set()
        for c in here:
            name = c["name"]
            is_inc = int(name == inc)
            if is_inc and not rid.endswith("-GOV"):
                name = roster_caps(name, holder)
            if name in seen:
                problems.append(f"{rid}: {name} twice on the November list")
                continue
            seen.add(name)
            note = []
            ps = parties(c["party"])
            if is_inc and via:
                note.append(f"The May 19 primary ballot printed the name as {via}.")
            if c["type"] == "Write-in":
                note.append(f"Won the {ps[0]} nomination with write-in votes in the May 19 primary.")
            if c["type"] == "Substitute":
                note.append(f"Named by the {ps[0]} Party as a substitute nominee after the May 19 primary (the Department's list marks the "
                            "candidate Substitute).")
            if c["type"] == "Paper":
                note.append("On the ballot by nomination papers.")
            if len(ps) > 1:
                wi = [x["party"] for x in cross.get((rid, fold(c["name"])), []) if x["type"] == "Write-in"]
                note.append(f"Won the {' and '.join(ps)} nominations" + (f" (the {' and '.join(wi)} one with write-in votes)" if wi else "")
                            + f"; the Department's list writes the party as \"{c['party']}\".")
            if rid.endswith("-GOV") and c.get("mate") and officials.get("lt_governor") and \
                    find_incumbent([c["mate"]["name"]], officials["lt_governor"]):
                note.append(f"{c['mate']['name']} serves today as Lieutenant Governor.")
            cands.append([rid, "general", GENERAL, name, c["party"], party_code(c["party"]), None, is_inc, 0, None, None, None,
                          holder["id"] if is_inc else None, SRC_LIST, " ".join(note) or None])
        # nominees who are no longer on the list, and others marked off it
        gone = [c for c in by_race.get(rid, []) + (by_race.get(f"2026-{STATE}-LTG", []) if rid.endswith("-GOV") else [])
                if c["status"] in ("Withdrawn", "Terminated") and (c["won"] or c["type"] == "Paper")]
        for c in gone:
            role = " for Lieutenant Governor" if c["race"].endswith("-LTG") else ""
            ps = parties(c["party"])
            if c["won"]:
                sub = [x for x in by_race.get(c["race"], []) if x["type"] == "Substitute" and x["status"] == "Approved" and ps[0] in parties(x["party"])]
                notes[rid].append(f"{c['name']} won the {ps[0]} primary{role} on May 19 and is marked {c['status']} on the Department's list"
                                  + (f"; the party's substitute nominee is {sub[0]['name']}." if sub else "; the list names no substitute."))
                if not sub:
                    checks.append(f"{rid}: the {ps[0]} primary winner is marked {c['status']} and the list names no substitute")
            else:
                notes[rid].append(f"{c['name']} ({c['party']}){role} is marked {c['status']} on the Department's list and is not on the "
                                  "November ballot.")
    for c in mine:
        if c["type"] == "Substitute" and c["status"] == "Approved":
            ps = parties(c["party"])
            if not any(x["won"] and x["status"] in ("Withdrawn", "Terminated") and ps[0] in parties(x["party"]) for x in by_race.get(c["race"], [])):
                checks.append(f"{c['race']}: {c['name']} is a substitute nominee, but no {ps[0]} primary winner is marked withdrawn")

    # 6. primary fields from the official returns
    nfields, field_rows = 0, 0
    for rid in race_ids:
        byp = returns.get(rid, {})
        for party, printed in sorted(byp.items()):
            listed = [c for c in pool.get((rid, party), []) if printed_for(c, party, by_race.get(rid, []))]
            wi_winners = [c for c in pool.get((rid, party), []) if c["type"] == "Write-in" and c["won"]]
            top = max(v for _n, v in printed)
            leaders = [n for n, v in printed if v == top]
            matched = ret_match[(rid, party)]
            used = {id(m[2]) for m in matched if m[2]}
            for c in listed:
                if id(c) not in used and c["status"] != "Withdrawn":
                    checks.append(f"{rid} {party}: {c['name']} is a primary candidate on the list but not on the returns")
            winners = [m for m in matched if m[2] and m[2]["won"] and m[2]["type"] == "Petition"]
            if wi_winners and printed:
                checks.append(f"{rid} {party}: won with write-in votes by {wi_winners[0]['name']} over {len(printed)} printed name(s); "
                              "the returns carry no write-in votes")
            elif len(winners) != 1:
                checks.append(f"{rid} {party}: {len(winners)} printed candidates marked as the winner on the list")
            elif winners[0][0] not in leaders:
                checks.append(f"{rid} {party}: the list marks {winners[0][2]['name']} as the winner; the returns' top vote-getter is "
                              f"{' and '.join(leaders)}")
            if len(printed) < 2:
                continue
            nfields += 1
            code = CODE.get(party)
            if not code:
                problems.append(f"{rid}: a primary for {party!r}, which has no code here")
                continue
            total = sum(v for _n, v in printed)
            holder = holders[rid]
            names = [c["name"] if c else proper(ballot) for ballot, _v, c, _h in matched]
            inc = find_incumbent(names, holder)
            if holder and not inc:
                b = bridge(rid, holder)
                if b and b[0] == party:
                    inc = b[2]["name"]
            for (ballot, votes, c, how), name in zip(matched, names):
                note = []
                if c:
                    won = c["won"]
                    if how != "family name" and how != "names fit":
                        note.append(f"The primary ballot printed the name as {proper(ballot)}.")
                    if won and c["status"] in ("Withdrawn", "Terminated"):
                        note.append(f"Won the primary; marked {c['status']} on the Department's list since, and not on the November ballot.")
                    elif c["status"] in ("Withdrawn", "Terminated"):
                        note.append(f"Marked {c['status']} on the Department's list.")
                else:
                    won = leaders == [ballot] and not wi_winners
                    note.append("Not on the Department's candidate list; the returns print the name in capitals, shown here in ordinary capitals.")
                    checks.append(f"{rid} {party}: {ballot} is on the returns but not matched on the list")
                is_inc = int(name == inc)
                shown = roster_caps(name, holder) if is_inc else name
                cands.append([rid, f"primary-{code}", PRIMARY, shown, party, party_code(party), None, is_inc, 0, votes,
                              round(100 * votes / total, 1) if total else None, "advanced" if won else "lost",
                              holder["id"] if is_inc else None, SRC_RET[OFFICES_BY_KEY[rid_key(rid)][1]], " ".join(note) or None])
                field_rows += 1
            for c in wi_winners:
                cands.append([rid, f"primary-{code}", PRIMARY, c["name"], party, party_code(party), None, 0, 1, None, None, "advanced",
                              None, SRC_LIST, "Won with write-in votes; the official returns carry no write-in votes, so no count is shown."])
                field_rows += 1
    # every primary winner who came by petition is on the returns as the top of the party's primary
    for c in mine:
        if c["type"] == "Petition" and c["won"] and returns:
            for p in parties(c["party"]):
                if c["status"] == "Approved" and p not in returns.get(c["race"], {}) and not any(
                        x["status"] == "Inactive-CrossFiled" and x["type"] == "Write-in" and p in parties(x["party"])
                        for x in by_race.get(c["race"], [])):
                    checks.append(f"{c['race']}: {c['name']} won the {p} primary by the list, but the returns have no {p} primary for the race")

    # 7. race notes, and the last look at every stored text
    for rid in race_ids:
        races[rid][16] = " ".join(notes[rid]) or None
    keys = [(c[0], c[1], c[3]) for c in cands]
    if len(keys) != len(set(keys)):
        dup = sorted({k for k in keys if keys.count(k) > 1})
        problems.append(f"two candidate rows share race, election and name: {dup[:5]}")
    for c in cands:
        if NOT_A_NAME.search(re.sub(r"\b(Jr|Sr|II|III|IV)\.?$", "", c[3])) or (c[14] and re.search(r"@|www\.|https?:|\d{3}", c[14])):
            raise SystemExit(f"Pennsylvania (state races): a stored cell for {c[0]} failed the contact-detail check (not shown)")
    general = [c for c in cands if c[1] == "general"]
    if len(general) != general_expected:
        problems.append(f"{len(general)} November rows stored, the list gives {general_expected}")

    # 8. places
    place_rows = [("county", g, f"{n} County", json.dumps([g]), SRC_COUNTY) for g, n in sorted(counties.values())]
    for rid in race_ids:
        r = races[rid]
        if r[2] == "legislature":
            place_rows.append(("senate" if r[3] == "state_senate" else "house", r[6], r[5], r[7], SRC_BY_COUNTY if r[7] else SRC_ROSTER))

    # 9. write
    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA)
    with con:
        con.execute("DELETE FROM sl_candidates WHERE race_id IN (SELECT race_id FROM sl_races WHERE state = ?) OR race_id LIKE ?",
                    (STATE, f"2026-{STATE}-%"))
        con.execute("DELETE FROM sl_races WHERE state = ?", (STATE,))
        con.execute("DELETE FROM sl_sources WHERE state = ?", (STATE,))
        con.execute("DELETE FROM sl_places WHERE source_id LIKE ?", (f"{STATE.lower()}-%",))
        con.executemany("INSERT INTO sl_races VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [races[r] for r in race_ids])
        con.executemany("INSERT INTO sl_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", cands)
        con.executemany("INSERT INTO sl_places VALUES (?,?,?,?,?)", place_rows)
        n_state = len(mine)
        con.execute("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", (
            SRC_LIST, STATE, "official candidate list", "Pennsylvania Department of State",
            "PA Voter Services, Election Information: 2026 General Election", fed.URL, "", fetched(LIST_PATH), sha(LIST_PATH), n_state,
            f"Read from the page's own candidate data: {n_state} rows for Governor, Lieutenant Governor and both chambers of the General "
            f"Assembly ({', '.join(f'{v} {k}' for k, v in sorted(left_out.items()))} rows not read). The November ballot is every Approved "
            "candidate who came by nomination papers or won the May 19 primary (by petition, by write-in votes, or as the party's "
            "substitute). Only candidate id, name, party, status, how the candidate got there, office, district and primary result are "
            "kept; the residence columns are dropped as the page is read. Names are turned first name first and into ordinary "
            "capitals. The list gives no ballot positions."))
        if elist:
            con.execute("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", (
                SRC_ELECTIONS, STATE, "official results", "Pennsylvania Department of State", "Pennsylvania Election Returns: election list",
                fed.ELECTIONS_URL, "", fetched(elist), sha(elist), None,
                f"Read only for the status of the 2026 General Primary (election {ELECTION}): "
                + ("Official (ElectionStatus O), so its returns are stored." if not why else why)))
        for office, (key, oid, oname, _k, _o) in OFFICES.items():
            if oid not in ret_files:
                continue
            path, n = ret_files[oid]
            con.execute("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", (
                SRC_RET[oid], STATE, "official results", "Pennsylvania Department of State",
                f"Pennsylvania Election Returns: 2026 General Primary (May 19, 2026), {oname}, Official Returns", OFFICE_PAGE.format(o=oid),
                PRIMARY, fetched(path), sha(path), n,
                f"Statewide total of every printed candidate in each party's primary, read from the data call the Office Results page makes "
                f"({OFFICE_URL.format(o=oid)}). Election-day, mail and provisional votes add up to each total. The returns carry no "
                "write-in votes, so percentages are of the printed candidates' votes; who advanced is the candidate list's primary result, "
                "checked against the top vote-getter."))
        if breaks:
            con.execute("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", (
                SRC_BY_COUNTY, STATE, "official results", "Pennsylvania Department of State",
                "Pennsylvania Election Returns: 2026 General Primary, county breakdown of each state office's districts, Official Returns",
                RETURNS + "api/ElectionReturn/GetCountyBreak", PRIMARY, fetched(COUNTY_FILE), sha(COUNTY_FILE),
                sum(len(b["rows"]) for b in breaks.values()),
                f"One request a district to the data call the site's county view makes ({len(breaks)} districts); only county, party, "
                f"ballot name and votes are kept. Every candidate's counties add up to the statewide total ({n_checked} checked). The "
                "counties a district reaches are the counties its breakdown lists."))
        con.execute("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", (
            SRC_COUNTY, STATE, "county codes", "U.S. Census Bureau", "Cartographic boundary file, counties, 2024 (1:500,000)", COUNTY_URL,
            "2024", fetched(county_zip), sha(county_zip), len(counties),
            "Five-digit county codes (GEOID) for Pennsylvania's 67 counties, matched by name to the returns' county rows."))
        con.execute("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", (
            SRC_ROSTER, STATE, "member roster", "Open States people project (CC0), via state_pa.sqlite",
            "Sitting Pennsylvania legislators and statewide officials", "https://github.com/openstates/people", "", fetched(roster_db), "",
            sum(len(v) for v in members.values()) + len(officials),
            "Who holds each seat today and which candidate is the sitting member (same chamber and district, the name fits, one fit "
            "only); ids, names and party only."))
    con.close()

    # 10. say what happened
    ss = [c for c in general if "-SS" in c[0]]
    sh = [c for c in general if "-SH" in c[0]]
    gov = [c for c in general if c[0].endswith("-GOV")]
    empty = [r for r in race_ids if not r.endswith("-LTG") and not nov[r]]
    say(f"    Pennsylvania state offices: {len(races)} races; {len(general)} candidates on the November ballot (Governor tickets {len(gov)}, "
        f"Senate {len(ss)} in {len(SENATE_UP)} seats, House {len(sh)} in {HOUSE_SEATS} seats; {sum(c[7] for c in general)} sitting members, "
        f"{sum(1 for c in general if c[14] and 'write-in votes' in c[14])} nominated by write-in); {nfields} party primaries with a field "
        f"({field_rows} rows), " + ("official votes" if returns else "no votes") + f"; {n_checked} candidates' county sums checked")
    if empty:
        say(f"      no November candidate: {', '.join(empty)}")
    for b in blocked:
        say(f"      blocked: {b}")
    for x in loose:
        say(f"      matched by the looser rule (read it): {x}")
    for c in checks:
        say(f"      check: {c}")
    for p in problems:
        say(f"      CHECK {p}")
    return dict(races=len(races), general=len(general), senate=len(ss), house=len(sh), governor=len(gov), fields=nfields,
                field_rows=field_rows, empty=empty, blocked=blocked, checks=checks, problems=problems, county_checked=n_checked, loose=loose)


OFFICES_BY_KEY = {v[0]: v for v in OFFICES.values()}


def rid_key(rid):
    key = rid.split(f"-{STATE}-", 1)[1]
    return key if key in ("GOV", "LTG") else key[:2]


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", required=True, help="the state-and-local ballot database to write Pennsylvania's rows into")
    ap.add_argument("--no-fetch", action="store_true", help="use the kept candidate list as it is")
    a = ap.parse_args()
    load(a.db, fetch=not a.no_fetch)
