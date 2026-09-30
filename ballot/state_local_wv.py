"""
ballot/state_local_wv.py - West Virginia's state races on the November 3, 2026 ballot: the State Senate seats up this
year, all 100 seats of the House of Delegates, and the judicial vacancies the Secretary of State lists for November,
with the May 12 party primaries that chose the legislative nominees. Written into ballot_local_2026.sqlite (never
ballot_2026.sqlite), West Virginia's rows only.

Sources, all the Secretary of State's own (the same two the federal loader, ballot/lists/wv.py, reads):
  * the 2026 candidate listing (candidates.wvsos.gov), read through the listing's own data service
    (candidate-web-api/candidates, a JSON POST with the page's own filters): the election ("11/03/2026 - GENERAL 2026"
    and "05/12/2026 - PRIMARY 2026"), the office level STATE RACE, and the tab (R Regular Candidates, W Write-In
    Candidates). Every page is counted against the service's own total. Each row also carries the candidate's e-mail,
    telephones, residential and mailing addresses, town, website and committee; none of those is ever read into the
    loader's own structures, printed or kept. Only these fields are taken from each row as it arrives: the election and
    its date, the office, its level, the district name and division number, the party code and party, the name as
    printed on the ballot (candidateBallotName) and the tab. The cached copy on disk holds nothing else.
  * the official results of the May 12, 2026 primary, from the Secretary's results site (hosted by Clarity
    Elections): the detail report (one Contest per office and party, each candidate's total, and the same votes county
    by county) and the summary report as a control. ballot/lists/wv.py fetches and checks them (headed "Official
    Results", every county completely reported); this loader reads the state contests from the same files.

What is on the November ballot: the listing's STATE RACE offices for the general election are "STATE SENATE - DISTRICT
n" (one seat in each of the 17 senatorial districts), "STATE SENATE - UNEXPIRED - DISTRICT n" (a second seat in a
district, for the rest of a term), "HOUSE OF DELEGATES - DISTRICT n" (1 to 100, one delegate each) and two kinds of
judicial vacancy ("CIRCUIT COURT JUDGE - UNEXPIRED - DISTRICT n" and "FAMILY COURT JUDGE - UNEXPIRED - DISTRICT n", with
a division number), which are nonpartisan. West Virginia elects its Governor and the other executive offices in
presidential years, and the listing has none for 2026. The Supreme Court of Appeals and the Intermediate Court of
Appeals were elected on the May 12 ballot, in nonpartisan elections that decide the seat; they are not on November's
listing, so they are not stored here.

The listing gives no ballot positions, so ballot_order is left empty. Declared write-in candidates (the Write-In tab)
are stored with write_in 1, no ballot position and party_code W; the party is the one the tab gives, where it gives
one, else "Write-in". The listing has no status column: a candidate
who withdrew or was removed is no longer listed. Names are printed in capitals; they are shown in ordinary capitals (a
sitting member as the Open States roster spells the same letters), and the race note says so.

The primary: a party's primary is stored as a field only when two or more candidates were on its ballot. The listing's
May rows say who was on each party's ballot and how the names are printed; the votes come from the detail report,
whose candidates must be the listing's for that office and party (names matched on letters only). Every candidate's
county votes must add up to the total, and the summary report must give the same totals. The results site reports no
write-in votes for these contests, so a field's total is the sum of its candidates' votes. West Virginia nominates the
leader (outcome "advanced"); a leader who is not the party's candidate on the November listing is noted, and so is a
November candidate who was not on the party's May ballot. A candidate the results count who is no longer on the
listing (withdrawn since) is kept in a field with a note, and reported.

Who holds each seat today comes from state_wv.sqlite (the Open States roster the state pages use): names, parties,
districts and start dates only. A House of Delegates seat has one member. A senatorial district has two senators,
elected in alternate even years, and the roster does not say whose seat is on the ballot, so the holder is worked out
only where the record allows: an unexpired-term seat is the one held by the district's only senator who joined
mid-term (a roster start other than 1 December of an even year or the first two weeks of January after it), and the
district's other senator then holds the full-term seat; elsewhere, the district's one sitting senator who is a
candidate for this seat (on the May or November list) is taken as its holder. Otherwise both senators are given and the
race note says why. A candidate is marked as the incumbent only when the name fits exactly one sitting member of the
same chamber and district. The roster carries no judges.

County codes: the detail report lists the counties taking part in each contest; a district's county_ids are those
counties (Census GEOIDs, from the Bureau's cartographic county file), for the legislative districts and any judicial
circuit that also had a May contest.

The privacy rule: only office, district, name, party, ballot order, status and votes are read from any list. Nothing
else is printed, logged, cached or stored, and no photos, ages, websites, biographies or money are stored in this
phase.

Usage: python -m ballot.state_local_wv <database file> [cache folder]
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
import zipfile
import xml.etree.ElementTree as ET

if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ballot.common import CACHE, HERE, fold, name_parts, party_code
from ballot.lists.tx import proper
from ballot.lists.wv import API, DONE, RESULTS_PAGE, RESULT_CODES, SITE, fetch_results, post
from ballot.match import fits
from states import net

STATE, NAME, FIPS = "WV", "West Virginia", "54"
GENERAL, PRIMARY = "2026-11-03", "2026-05-12"
ELECTIONS = {"general": ("11/03/2026 - GENERAL 2026", "11/03/2026"), "primary": ("05/12/2026 - PRIMARY 2026", "05/12/2026")}
LEVEL = "STATE RACE"
KEEP = ("candidateType", "electionName", "electionDate", "officeName", "officeDescription", "candidateDistrictName",
        "divisionNumber", "partyCode", "partyDescription", "candidateBallotName")
PAGE_SIZE = 100
ROSTER = os.path.join(HERE, "state_wv.sqlite")
COUNTY_ZIP = os.path.join(HERE, "states_cache", "census", "cb_2024_us_county_500k.zip")
COUNTY_URL = "https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_county_500k.zip"
LIST_CODES = {"R": "REP", "D": "DEM", "L": "LIB", "M": "MTN", "C1": "CON"}   # listing party code -> primary election code
NONPARTISAN = "Nonpartisan office"
CAPS = "West Virginia's list prints names in capitals; they are shown here in ordinary capitals."
WRITE_IN = "Declared write-in candidate: the name is not printed on the ballot."
NO_ORDER = "The Secretary of State's listing gives no ballot positions."
OFF_LIST = "Not on the party's May 12 primary ballot."
SRC_GEN, SRC_PRI = "wv-sos-2026-sl-general-list", "wv-sos-2026-sl-primary-list"
SRC_RES, SRC_SUM = "wv-sos-2026-sl-primary-results", "wv-sos-2026-sl-primary-summary"
SRC_COUNTY, SRC_ROSTER = "wv-census-2024-counties", "wv-openstates-roster"

SCHEMA = """
CREATE TABLE IF NOT EXISTS sl_races (race_id TEXT PRIMARY KEY, state TEXT NOT NULL, level TEXT NOT NULL, office_kind TEXT NOT NULL, office TEXT NOT NULL, jurisdiction TEXT, jurisdiction_id TEXT, county_ids TEXT, district TEXT, seat TEXT, special INTEGER NOT NULL DEFAULT 0, partisan INTEGER NOT NULL, holder_id TEXT, holder_name TEXT, holder_party TEXT, election_date TEXT NOT NULL, note TEXT);
CREATE TABLE IF NOT EXISTS sl_candidates (race_id TEXT NOT NULL, election TEXT NOT NULL, election_date TEXT, name TEXT NOT NULL, party TEXT, party_code TEXT, ballot_order INTEGER, incumbent INTEGER NOT NULL DEFAULT 0, write_in INTEGER NOT NULL DEFAULT 0, votes INTEGER, pct REAL, outcome TEXT, state_member_id TEXT, source_id TEXT, note TEXT, PRIMARY KEY (race_id, election, name));
CREATE TABLE IF NOT EXISTS sl_sources (source_id TEXT PRIMARY KEY, state TEXT, kind TEXT, agency TEXT, title TEXT, url TEXT, published TEXT, fetched TEXT, sha256 TEXT, rows INTEGER, note TEXT);
CREATE TABLE IF NOT EXISTS sl_places (kind TEXT NOT NULL, id TEXT NOT NULL, name TEXT NOT NULL, county_ids TEXT, source_id TEXT, PRIMARY KEY (kind, id));
"""


def ordinal(n):
    n = int(n)
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def sha_of(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest() if path and os.path.exists(path) else ""


def day_of(path):
    return dt.datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d") if path and os.path.exists(path) else ""


def norm(text):
    """Letters and digits only, for comparing a district name with the office it belongs to."""
    return " ".join(re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).split())


def join(*parts):
    return " ".join(p for p in parts if p) or None


# ---------------------------------------------------------------- the candidate listing: allowed fields only

def read_tab(election, ctype):
    """Every STATE RACE row of one election on one tab (R regular, W write-in), the allowed fields only."""
    rows, page, meta = [], 0, {}
    while True:
        got = post({"page": page, "size": PAGE_SIZE, "candidateType": ctype, "electionName": election, "officeDescription": [LEVEL]})
        if got.get("error") or not isinstance(got.get("data"), dict):
            raise SystemExit(f"West Virginia: the candidate listing's service answered with an error ({got.get('message')!r})")
        meta = got.get("meta") or {}
        rows += [{k: c.get(k) for k in KEEP} for c in got["data"].get("candidates") or []]   # the other fields are never kept
        if meta.get("last", True):
            break
        page += 1
        time.sleep(1.5)
    if len(rows) != meta.get("totalElements", len(rows)):
        raise SystemExit(f"West Virginia: the listing counts {meta.get('totalElements')} rows for {election} ({ctype}); {len(rows)} were read")
    if any(r["officeDescription"] != LEVEL or r["electionName"] != election for r in rows):
        raise SystemExit(f"West Virginia: the listing's service did not apply its own filters ({election}, {ctype})")
    return rows


def read_list(kind, path, max_age_days, say):
    """The STATE RACE rows of one election, both tabs, kept on disk (allowed fields only)."""
    if os.path.exists(path) and (max_age_days is None or time.time() - os.path.getmtime(path) < max_age_days * 86400):
        return json.load(open(path, encoding="utf-8"))
    net.patient_lookups()
    election, date = ELECTIONS[kind]
    regular = read_tab(election, "R")
    time.sleep(1.5)
    write_in = read_tab(election, "W")
    for r in regular + write_in:
        if r["electionDate"] != date:
            raise SystemExit(f"West Virginia: a row of {election} is dated {r['electionDate']}")
    kept = {"election": election, "url": SITE, "service": API, "level": LEVEL, "fields": list(KEEP),
            "regular": regular, "write_in": write_in}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(kept, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    say(f"      {election}: {len(regular)} regular and {len(write_in)} write-in rows at the STATE RACE level")
    return kept


# ---------------------------------------------------------------- races

def race_for(row):
    """The race a listing row belongs to, or None for an office that is not stored (party committees, the Greater
    Huntington park board, the May judicial elections). Raises for an office this loader does not know."""
    office = re.sub(r"\s+", " ", row["officeName"] or "").strip().upper()
    dname = norm(row.get("candidateDistrictName"))
    m = re.fullmatch(r"STATE SENATE( - UNEXPIRED)? - DISTRICT (\d+)", office)
    if m:
        d, special = str(int(m.group(2))), 1 if m.group(1) else 0
        if norm(f"{ordinal(d)} senatorial district") != dname:
            raise SystemExit(f"West Virginia: {office} is listed under the district {row.get('candidateDistrictName')!r}")
        return {"race_id": f"2026-{STATE}-SS{d}" + ("-UNEXP" if special else ""), "level": "legislature",
                "office_kind": "state_senate", "office": "State Senator", "jurisdiction": f"{ordinal(d)} Senatorial District",
                "jurisdiction_id": d, "district": d, "seat": "Unexpired term" if special else None, "special": special,
                "partisan": 1, "chamber": "Senate", "place": ("senate", f"{STATE}-{d}", f"{ordinal(d)} Senatorial District"),
                "note": ("An election for the rest of a term, as the Secretary of State's list titles it (\"unexpired\"): the "
                         "district's second seat. The district's other seat is also on this ballot, for a full term."
                         if special else None)}
    m = re.fullmatch(r"HOUSE OF DELEGATES - DISTRICT (\d+)", office)
    if m:
        d = str(int(m.group(1)))
        if norm(f"{ordinal(d)} delegate district") != dname:
            raise SystemExit(f"West Virginia: {office} is listed under the district {row.get('candidateDistrictName')!r}")
        return {"race_id": f"2026-{STATE}-SH{d}", "level": "legislature", "office_kind": "state_house",
                "office": "Member of the House of Delegates", "jurisdiction": f"{ordinal(d)} Delegate District",
                "jurisdiction_id": d, "district": d, "seat": None, "special": 0, "partisan": 1, "chamber": "House",
                "place": ("house", f"{STATE}-{d}", f"{ordinal(d)} Delegate District"), "note": None}
    m = re.fullmatch(r"(CIRCUIT|FAMILY) COURT JUDGE - UNEXPIRED - DISTRICT (\d+)", office)
    if m:
        court, d, div = m.group(1).title(), str(int(m.group(2))), (row.get("divisionNumber") or "").strip()
        if not div.isdigit():
            raise SystemExit(f"West Virginia: {office} is listed without a division number")
        want = norm(f"{ordinal(d)} {court} court district {ordinal(div)} division")
        if want != dname:
            raise SystemExit(f"West Virginia: {office}, division {div}, is listed under {row.get('candidateDistrictName')!r}")
        key = "CC" if court == "Circuit" else "FC"
        return {"race_id": f"2026-{STATE}-{key}-{d}-{div}", "level": "court",
                "office_kind": "circuit_court" if court == "Circuit" else "family_court", "office": f"{court} Court Judge",
                "jurisdiction": f"{ordinal(d)} {court} Court District", "jurisdiction_id": f"{STATE}-{key}{d}", "district": d,
                "seat": f"Division {div}", "special": 1, "partisan": 0, "chamber": None,
                "place": ("judicial" if court == "Circuit" else "family_court", f"{STATE}-{key}{d}", f"{ordinal(d)} {court} Court District"),
                "note": ("An election for the rest of a term, as the Secretary of State's list titles it (\"unexpired\"). "
                         "Judges in West Virginia are elected on a nonpartisan ballot: no party is printed. The roster used "
                         "here carries no judges, so today's holder is not shown.")}
    if re.fullmatch(r"STATE EXECUTIVE COMMITTEE - (FE)?MALE - DISTRICT \d+", office) or office.startswith("GREATER HUNTINGTON PARK"):
        return None
    raise SystemExit(f"West Virginia: the listing names a state office this loader does not know: {office!r}")


def contest_of(text):
    """(race_id, election code) for a state legislative contest of the results report, or None for other contests."""
    t = re.sub(r"\s+", " ", text).strip()
    m = re.fullmatch(r"STATE SENATOR, (\d+)(?:st|nd|rd|th) Senatorial District - ([A-Z]+)( - UNEXPIRED TERM)?", t)
    if m:
        race, party = f"2026-{STATE}-SS{int(m.group(1))}" + ("-UNEXP" if m.group(3) else ""), m.group(2)
    else:
        m = re.fullmatch(r"HOUSE OF DELEGATES, (\d+)(?:st|nd|rd|th) District - ([A-Z]+)", t)
        if not m:
            if t.upper().startswith(("STATE SENATOR", "HOUSE OF DELEGATES")):
                raise SystemExit(f"West Virginia: a legislative contest in the results that is not read ({t!r})")
            return None
        race, party = f"2026-{STATE}-SH{int(m.group(1))}", m.group(2)
    if party not in RESULT_CODES:
        raise SystemExit(f"West Virginia: a party in the results that is not read ({party!r}, {t})")
    return race, RESULT_CODES[party]


def circuit_of(text):
    """The judicial place of a May judicial contest ("... CIRCUIT COURT JUDGE - UNEXPIRED TERM, 7th"), or None."""
    m = re.search(r"(CIRCUIT|FAMILY) COURT JUDGE - UNEXPIRED TERM, (\d+)(?:st|nd|rd|th)$", re.sub(r"\s+", " ", text).strip())
    return f"{STATE}-{'CC' if m.group(1) == 'CIRCUIT' else 'FC'}{int(m.group(2))}" if m else None


# ---------------------------------------------------------------- the primary results

PLACEHOLDER = "no candidate filed"
COURT = re.compile(r"COURT JUDGE", re.I)


def primary_votes(detail, summary, meta):
    """({(race, code): (field, placeholders)}, {race or judicial place: {county names}}) for every state legislative
    party primary: field is [(name as reported, votes)]. Every check is made; nothing but names and votes is read."""
    if meta["election"] != "2026 Primary" or meta["date"] != "5/12/2026":
        raise SystemExit(f"West Virginia: the results site is for {meta['election']} {meta['date']}, not the 2026 primary")
    behind = {c: s for c, s in meta["counties"].items() if s not in DONE.values()}
    if len(meta["counties"]) != 55 or behind:
        raise SystemExit(f"West Virginia: not every county has completely reported ({len(meta['counties'])} counties; {behind})")
    root = ET.fromstring(zipfile.ZipFile(detail).read("detail.xml"))
    if root.findtext("ElectionName") != "2026 Primary" or root.findtext("ElectionDate") != "5/12/2026":
        raise SystemExit("West Virginia: the detail report is not the 2026 primary's")
    out, counties = {}, {}
    for c in root.findall("Contest"):
        text = c.get("text", "")
        key = contest_of(text)
        place = circuit_of(text)
        if key is None and place is None:
            continue
        taking_part = {cc.get("name") for cc in c.findall("ParticipatingCounties/County") if int(cc.get("precinctsParticipating") or 0) > 0}
        counties.setdefault(key[0] if key else place, set()).update(taking_part)
        if key is None:
            continue
        if c.get("precinctsReported") != c.get("precinctsParticipating") or c.get("countiesReported") != c.get("countiesParticipating"):
            raise SystemExit(f"West Virginia: {text} is not completely reported in the detail report")
        if c.get("voteFor") != "1":
            raise SystemExit(f"West Virginia: {text} votes for {c.get('voteFor')}, not one")
        field, empty = [], 0
        for ch in c.findall("Choice"):
            total = int(ch.get("totalVotes"))
            by_type = sum(int(vt.get("votes")) for vt in ch.findall("VoteType"))
            by_county = sum(int(cc.get("votes")) for vt in ch.findall("VoteType") for cc in vt.findall("County"))
            if by_type != total or by_county != total:
                raise SystemExit(f"West Virginia: a choice's votes in {text} do not add up ({total}, by type {by_type}, by county {by_county})")
            name = re.sub(r"\s+", " ", ch.get("text", "")).strip()
            if fold(name) == PLACEHOLDER:
                if total:
                    raise SystemExit(f"West Virginia: {text}'s \"no candidate filed\" line carries {total} votes")
                empty += 1
                continue
            if re.search(r"write[- ]?in", name, re.I):
                raise SystemExit(f"West Virginia: {text} reports write-in votes; read how they are reported")
            if RESULT_CODES.get(ch.get("party")) != key[1]:
                raise SystemExit(f"West Virginia: a candidate of {text} is reported under the party {ch.get('party')}")
            field.append((name, total))
        if key in out:
            raise SystemExit(f"West Virginia: {text} appears twice in the detail report")
        out[key] = (field, empty)
    # control: the summary report gives the same totals
    rows = list(csv.reader(io.StringIO(zipfile.ZipFile(summary).read("summary.csv").decode("utf-8-sig", "replace"))))
    head = rows[0]
    ci, ni, vi = head.index("contest name"), head.index("choice name"), head.index("total votes")
    seen = {}
    for r in rows[1:]:
        if not r:
            continue
        key = contest_of(re.sub(r" \(Vote For \d+\)$", "", r[ci]))
        if key and fold(r[ni]) != PLACEHOLDER:
            seen.setdefault(key, {})[fold(r[ni])] = int(r[vi])
    for key, (field, _e) in out.items():
        if {fold(n): v for n, v in field} != seen.get(key, {}):
            raise SystemExit(f"West Virginia: the summary report's totals for {key} differ from the detail report's")
    if {k for k, (f, _e) in out.items() if f} != set(seen):
        raise SystemExit("West Virginia: the summary and detail reports list different state legislative contests")
    return out, counties


# ---------------------------------------------------------------- who holds each seat

def roster(path=ROSTER):
    """Sitting legislators: id, chamber, district, names, party and start date only."""
    if not os.path.exists(path):
        return []
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    members = [dict(zip(("id", "chamber", "district", "first", "last", "full", "party", "start"), r)) for r in con.execute(
        "SELECT bioguide_id, chamber, district, first_name, last_name, official_full, party_name, term_start "
        "FROM legislators WHERE is_current = 1 AND state = 'WV'")]
    con.close()
    return members


def letters(text):
    """Letters only, no spaces: J.B. Akers and JB AKERS are the same letters."""
    return fold(text).replace(" ", "")


def name_fits(name, person):
    """The family name the same and one given name that fits, any of the ballot's given names (FREDERICK "HAPPY" JOE
    PARSONS for Joe Parsons, D.R. BUCK JENNINGS for Buck Jennings) or its initials run together (JB for J.B.)."""
    given, family = name_parts(name)
    initials = "".join(w for w in given if len(w) == 1)
    tries = [given] + [[w] for w in given[2:]] + ([[initials]] if len(initials) > 1 else [])
    for reg in (([w for w in fold(person["first"]).split()], " ".join(fold(person["last"]).split())), name_parts(person["full"])):
        reg_given = reg[0] + ([reg[0][0] + reg[0][1]] if len(reg[0]) > 1 and all(len(w) == 1 for w in reg[0][:2]) else [])
        if any(fits((g, family), (reg_given, reg[1])) for g in tries):
            return True
    return False


def one_fit(name, people):
    """The one person the name fits, else None."""
    hits = [p for p in people if name_fits(name, p)]
    return hits[0] if len(hits) == 1 else None


def mid_term(member):
    """True when the roster's start date is not the beginning of a term (1 December of an even year, or the first two
    weeks of January after it, where the roster gives the session's opening instead)."""
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", member["start"] or "")
    if not m:
        return None
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    return not ((y % 2 == 0 and mo == 12 and d == 1) or (y % 2 == 1 and mo == 1 and d <= 14))


# ---------------------------------------------------------------- counties

def county_codes(path=COUNTY_ZIP):
    """{folded county name: (GEOID, "Barbour County")} for West Virginia from the Census Bureau's cartographic file."""
    import shapefile                                   # pyshp
    z = zipfile.ZipFile(path)
    base = next(n[:-4] for n in z.namelist() if n.endswith(".dbf"))
    rdr = shapefile.Reader(dbf=io.BytesIO(z.read(base + ".dbf")))
    fields = [f[0] for f in rdr.fields[1:]]
    out = {}
    for rec in rdr.iterRecords():
        rec = dict(zip(fields, rec))
        if str(rec.get("STATEFP")) == FIPS:
            out[fold(str(rec["NAME"]))] = (str(rec["GEOID"]), str(rec["NAMELSAD"]))
    if len(out) != 55:
        raise SystemExit(f"West Virginia: the county file gives {len(out)} counties, not 55")
    return out


# ---------------------------------------------------------------- load

def load(db_path, say=print, cache=CACHE, roster_path=ROSTER):
    net.patient_lookups()
    folder = os.path.join(cache, "wv")
    gpath, ppath = os.path.join(folder, "wv_2026_sl_general_list.json"), os.path.join(folder, "wv_2026_sl_primary_list.json")
    gen = read_list("general", gpath, 2, say)           # asked afresh after two days
    pri = read_list("primary", ppath, None, say)        # the primary is over: the copy on disk is kept
    detail, summary, meta = fetch_results(folder, say)
    votes, contest_counties = primary_votes(detail, summary, meta)
    members = roster(roster_path)
    geo = county_codes() if os.path.exists(COUNTY_ZIP) else {}

    spelled = {}                                        # the roster's capitals, where its words are the same letters
    for m in members:
        for form in (m["full"], f"{m['first']} {m['last']}"):
            if form:
                spelled.setdefault(letters(form), form)

    def shown(caps):
        caps = re.sub(r"\s+", " ", caps or "").strip()
        if letters(caps) in spelled:
            return spelled[letters(caps)]
        out = re.sub(r"(['\"(])([a-z])", lambda m: m.group(1) + m.group(2).upper(), proper(caps))
        return re.sub(r"\b([A-Z])\.([a-z])\.", lambda m: f"{m.group(1)}.{m.group(2).upper()}.", out)   # D.R., not D.r.

    def party_of(r):
        if r["partyCode"] == "NON":
            return NONPARTISAN, "N"
        if not r["partyDescription"]:
            raise SystemExit(f"West Virginia: a candidate for {r['officeName']} with no party on the listing")
        p = proper(r["partyDescription"])
        return p, party_code(p)

    races, listed, places, problems, skipped = {}, collections.defaultdict(list), {}, [], collections.Counter()
    read = {"general": 0, "general_write_in": 0, "primary": 0}
    for r in gen["regular"] + gen["write_in"]:
        race = race_for(r)
        if race is None:
            skipped[("general", re.sub(r"\d+", "n", r["officeName"]))] += 1
            continue
        read["general_write_in" if r["candidateType"] == "W" else "general"] += 1
        rid = race["race_id"]
        if rid in races and races[rid]["office"] != race["office"]:
            raise SystemExit(f"West Virginia: two offices share the race key {rid}")
        races.setdefault(rid, race)
        listed[rid].append(r)
        places[race["place"][:2]] = race["place"]
    if gen["write_in"] and any(r["candidateType"] != "W" for r in gen["write_in"]):
        raise SystemExit("West Virginia: the Write-In tab returned a row that is not a write-in")

    filed = collections.defaultdict(dict)               # (race, code) -> {folded name: printed name}
    for r in pri["regular"]:
        race = None if COURT.search(r["officeName"] or "") else race_for(r)   # May's judicial elections: not a primary
        if race is None:
            skipped[("primary", re.sub(r"\d+", "n", r["officeName"]))] += 1
            continue
        read["primary"] += 1
        if r["partyCode"] not in LIST_CODES:
            raise SystemExit(f"West Virginia: a primary candidate for {r['officeName']} of a party that is not read ({r['partyCode']})")
        key = (race["race_id"], LIST_CODES[r["partyCode"]])
        if fold(r["candidateBallotName"]) in filed[key]:
            raise SystemExit(f"West Virginia: a name is listed twice in the {key} primary")
        filed[key][fold(r["candidateBallotName"])] = (r["candidateBallotName"], party_of(r))
        if race["race_id"] not in races:
            problems.append(f"{race['race_id']} had a May primary but is not on the November listing")
    if any(not COURT.search(r["officeName"] or "") and race_for(r) for r in pri["write_in"]):
        raise SystemExit("West Virginia: the primary listing names write-in candidates for the Legislature; read how the results report them")

    # the listing's primaries and the results' contests must be the same, candidate for candidate
    with_names = {k for k, (f, _e) in votes.items() if f}
    if with_names != set(filed):
        problems.append(f"party primaries on the listing but not in the results, or the reverse: {sorted(with_names ^ set(filed))}")
    ballots = {}                                        # (race, code) -> [(name as the listing prints it, party, votes, note)]
    extra_in_results = []
    for key in sorted(set(filed) | with_names):
        field = votes.get(key, ([], 0))[0]
        entries, used = [], set()
        for folded, (printed, (party, _pc)) in filed.get(key, {}).items():
            hit = [i for i, (n, _v) in enumerate(field) if fold(n) == folded] or \
                  [i for i, (n, _v) in enumerate(field) if fits(name_parts(printed), name_parts(n))]
            if len(hit) != 1 or hit[0] in used:
                problems.append(f"{key}: {shown(printed)} is not found once in the official results")
                entries.append((printed, party, None, None))
                continue
            used.add(hit[0])
            entries.append((printed, party, field[hit[0]][1], None))
        for i, (n, v) in enumerate(field):
            if i not in used:                           # on the ballot and counted, but no longer on the listing
                extra_in_results.append((key, n, v))
                entries.append((n, "Republican" if key[1] == "REP" else "Democrat", v,
                                "In the official results, but no longer on the Secretary of State's candidate listing."))
        ballots[key] = entries

    # who holds each seat
    def people_of(race):
        return [m for m in members if m["chamber"] == race["chamber"] and m["district"] == race["district"]] if race["chamber"] else []

    def candidates_named(rid, people):
        out = set()
        names = [r["candidateBallotName"] for r in listed.get(rid, [])]
        names += [n for (race_id, _c), d in filed.items() if race_id == rid for n, _p in d.values()]
        for n in names:
            who = one_fit(n, people)
            if who:
                out.add(who["id"])
        return out

    held = {}
    for rid, race in races.items():
        people = people_of(race)
        if race["chamber"] == "House" or not race["chamber"]:
            held[rid] = (people, None)
            continue
        unexp = f"2026-{STATE}-SS{race['district']}-UNEXP"
        mid = [m for m in people if mid_term(m)]
        if unexp in races and len(people) == 2 and len(mid) == 1:
            held[rid] = (mid if race["special"] else [m for m in people if m is not mid[0]],
                         "The unexpired seat is taken to be the one held by the district's only senator who joined mid-term, "
                         "by the roster's dates; the other senator holds the full-term seat.")
            continue
        if not race["special"] and unexp not in races:
            running = candidates_named(rid, people)
            if len(people) == 2 and len(running) == 1:
                held[rid] = ([m for m in people if m["id"] in running],
                             "The district has two senators, elected in alternate even years; the one who is a candidate "
                             "for this seat is given as its holder.")
                continue
        held[rid] = (people, "The district has two senators, elected in alternate even years, and the roster used here "
                             "does not say which of them holds the seat on this ballot, so both are given." if len(people) > 1 else None)

    # November rows
    cands, nominee = [], {}
    for rid, rows in sorted(listed.items()):
        race = races[rid]
        people = people_of(race)
        holders, why = held[rid]
        holders = sorted(holders, key=lambda m: m["last"])
        race["holder_id"] = "; ".join(m["id"] for m in holders) or None
        race["holder_name"] = "; ".join(m["full"] for m in holders) or None
        race["holder_party"] = "; ".join(m["party"] or "" for m in holders) or None
        race["note"] = join(race["note"], why, CAPS, NO_ORDER)
        if race["chamber"] and not holders:
            race["note"] = join(race["note"], "The roster used here lists nobody in this seat today.")
        cids = sorted(geo[fold(c)][0] for c in contest_counties.get(rid if race["chamber"] else race["jurisdiction_id"], ()) if fold(c) in geo)
        race["county_ids"] = json.dumps(cids) if cids else None
        seen = set()
        for r in rows:
            name = shown(r["candidateBallotName"])
            if name in seen:
                raise SystemExit(f"West Virginia: {rid} lists the same name twice")
            seen.add(name)
            who = one_fit(r["candidateBallotName"], people) if people else None
            if r["candidateType"] == "W":
                party = proper(r["partyDescription"]) if r["partyDescription"] else "Write-in"
                cands.append((rid, "general", GENERAL, name, party, "W", None, 1 if who else 0, 1, None, None, None,
                              who["id"] if who else None, SRC_GEN, WRITE_IN))
                continue
            party, code = party_of(r)
            note = None
            if race["partisan"] and r["partyCode"] in ("R", "D"):
                key = (rid, LIST_CODES[r["partyCode"]])
                nominee[key] = fold(r["candidateBallotName"])
                if fold(r["candidateBallotName"]) not in {fold(e[0]) for e in ballots.get(key, [])}:
                    note = OFF_LIST
            cands.append((rid, "general", GENERAL, name, party, code, None, 1 if who else 0, 0, None, None, None,
                          who["id"] if who else None, SRC_GEN, note))

    # the primary fields
    fields, uncontested, leaders_off, ties = 0, 0, [], []
    for key, entries in sorted(ballots.items()):
        rid, code = key
        if len(entries) < 2:
            uncontested += 1
            continue
        if rid not in races:
            continue                                    # reported above: a May primary with no November race
        fields += 1
        people = people_of(races[rid])
        complete = all(v is not None for _n, _p, v, _x in entries)
        total = sum(v for _n, _p, v, _x in entries if v is not None)
        top = max((v for _n, _p, v, _x in entries if v is not None), default=None)
        leaders = [n for n, _p, v, _x in entries if v == top] if complete else []
        if len(leaders) > 1:
            ties.append(f"{rid} {code}")
        won = nominee.get(key)
        for printed, party, v, note in sorted(entries, key=lambda e: -(e[2] if e[2] is not None else -1)):
            who = one_fit(printed, people) if people else None
            outcome = None
            if complete and len(leaders) == 1:
                outcome = "advanced" if printed == leaders[0] else "lost"
                if printed == leaders[0] and won != fold(printed):
                    note = join(note, "Not on the November list.")
                    leaders_off.append(f"{rid} {code}: {shown(printed)}")
            cands.append((rid, f"primary-{code}", PRIMARY, shown(printed), party, party_code(party), None, 1 if who else 0, 0, v,
                          round(100 * v / total, 1) if v is not None and total else None, outcome,
                          who["id"] if who else None, SRC_RES if v is not None else SRC_PRI, note))

    # CHECKS: every seat that should be on the ballot is, and every row read is stored
    senate = sorted(int(r["district"]) for r in races.values() if r["office_kind"] == "state_senate" and not r["special"])
    house = sorted(int(r["district"]) for r in races.values() if r["office_kind"] == "state_house")
    for label, got, want in (("State Senate", senate, range(1, 18)), ("House of Delegates", house, range(1, 101))):
        missing = [d for d in want if d not in got]
        if missing:
            problems.append(f"{label}: districts with no candidate on the November listing: {missing}")
    gen_rows = sum(1 for c in cands if c[1] == "general")
    if gen_rows != read["general"] + read["general_write_in"]:
        problems.append(f"November: {read['general'] + read['general_write_in']} rows read, {gen_rows} stored")
    pri_rows = sum(len(d) for d in filed.values())
    if pri_rows != read["primary"]:
        problems.append(f"primary: {read['primary']} rows read, {pri_rows} placed in a party primary")
    for key, n, v in extra_in_results:
        problems.append(f"{key}: the results name {shown(n)} ({v} votes), who is no longer on the Secretary of State's listing "
                        + ("(stored in the field with a note)" if len(ballots[key]) > 1 else
                           "(the only candidate, so no field is stored; not on the November listing either)"
                           if key not in nominee or nominee[key] != fold(n) else "(the only candidate, so no field is stored)"))

    race_rows = [(r["race_id"], STATE, r["level"], r["office_kind"], r["office"], r["jurisdiction"], r["jurisdiction_id"],
                  r.get("county_ids"), r["district"], r["seat"], r["special"], r["partisan"], r.get("holder_id"),
                  r.get("holder_name"), r.get("holder_party"), GENERAL, r["note"]) for r in races.values()]
    place_rows = []
    for (kind, pid), (_k, _i, pname) in sorted(places.items()):
        here = [r for r in races.values() if r["place"][:2] == (kind, pid)]
        race = next((r for r in here if not (r["chamber"] and r["special"])), here[0])
        place_rows.append((kind, pid, pname, race.get("county_ids"), SRC_GEN))
    for folded, (geoid, label) in sorted(geo.items(), key=lambda kv: kv[1][0]):
        place_rows.append(("county", geoid, label, json.dumps([geoid]), SRC_COUNTY))
    unknown_counties = sorted({c for cs in contest_counties.values() for c in cs if fold(c) not in geo})
    if unknown_counties:
        problems.append(f"counties in the results that the Census file does not name: {unknown_counties}")

    by_kind = collections.Counter(r["office_kind"] + ("_unexpired" if r["special"] and r["chamber"] else "") for r in races.values())
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", meta["updated"] or "")
    updated = f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}" if m else ""
    write_ins = sum(1 for c in cands if c[1] == "general" and c[8])
    sources = [
        (SRC_GEN, STATE, "official candidate list", "West Virginia Secretary of State",
         "2026 General Candidate Listing: 11/03/2026 - GENERAL 2026, state races (Regular and Write-In Candidates)",
         SITE, "", day_of(gpath), sha_of(gpath), len(gen["regular"]) + len(gen["write_in"]),
         f"Read through the listing's own data service ({API}, office level {LEVEL}), every page counted against its total. "
         "Only the office, district name and division, party, name as printed on the ballot and tab are kept; e-mail, "
         "phones, addresses, town, website and committee are never read, printed or kept. The listing gives no ballot "
         "positions and no status column (a candidate who withdrew is no longer listed). It lists no statewide executive "
         "office for 2026 and no Supreme Court seat. "
         f"Declared write-ins (Write-In Candidates tab): {write_ins}."),
        (SRC_PRI, STATE, "official candidate list", "West Virginia Secretary of State",
         "2026 Candidate Listing: 05/12/2026 - PRIMARY 2026, State Senate and House of Delegates",
         SITE, "", day_of(ppath), sha_of(ppath), read["primary"],
         "Used for who was on each party's primary ballot and how the names are printed; the results' candidates must be "
         f"exactly these. The same kept fields only. Party primaries with a field (two or more candidates): {fields}; "
         f"with one candidate: {uncontested}. The May 12 ballot also carried the nonpartisan elections of the Supreme Court "
         "of Appeals, the Intermediate Court of Appeals and some circuit and family court seats, which decided those seats "
         "in May; they are not stored here. Party executive committee seats are not stored either."),
        (SRC_RES, STATE, "official results", "West Virginia Secretary of State",
         "2026 Primary Election (May 12, 2026), Official Results: detail report (XML), State Senate and House of Delegates",
         meta["detail_url"], updated, day_of(detail), sha_of(detail), sum(1 for e in ballots.values() for x in e if x[2] is not None),
         f"The Secretary's results site ({RESULTS_PAGE}, hosted by Clarity Elections), headed \"{meta['heading']}\", "
         f"version {meta['version']}, last updated {meta['updated']}. All 55 counties completely reported. Every "
         "candidate's county votes add up to the total. The report prints \"NO CANDIDATE FILED\" where a party had no "
         "candidate; those lines carry no votes and are not stored. No write-in votes are reported for these contests, "
         "so a field's total is its candidates' votes. The counties taking part in each contest give the district's "
         "county_ids."),
        (SRC_SUM, STATE, "official results", "West Virginia Secretary of State",
         "2026 Primary Election (May 12, 2026), Official Results: summary report (CSV)",
         meta["summary_url"], updated, day_of(summary), sha_of(summary), len(with_names),
         "Control: every state legislative party primary's totals here match the detail report's."),
    ]
    if geo:
        sources.append((SRC_COUNTY, STATE, "boundaries", "U.S. Census Bureau",
                        "Cartographic boundary file, counties, 2024, 1:500,000 (cb_2024_us_county_500k)", COUNTY_URL, "",
                        day_of(COUNTY_ZIP), sha_of(COUNTY_ZIP), len(geo),
                        "West Virginia's 55 counties: names and GEOIDs only, to turn the results' county names into codes."))
    if members:
        sources.append((SRC_ROSTER, STATE, "roster", "Open States (people project, CC0)",
                        "West Virginia legislators serving now (state_wv.sqlite, from the Open States people project)",
                        "https://github.com/openstates/people", "", day_of(roster_path), "", len(members),
                        "Used only to say who holds each seat today and to mark incumbents: names, parties, districts and start "
                        "dates. Not an official record."))

    con = sqlite3.connect(db_path)
    try:
        con.executescript(SCHEMA)
        with con:
            con.execute("DELETE FROM sl_candidates WHERE race_id IN (SELECT race_id FROM sl_races WHERE state = ?) OR race_id LIKE ?",
                        (STATE, f"2026-{STATE}-%"))
            con.execute("DELETE FROM sl_races WHERE state = ?", (STATE,))
            con.execute("DELETE FROM sl_sources WHERE state = ?", (STATE,))
            con.execute("DELETE FROM sl_places WHERE source_id LIKE 'wv-%'")
            con.executemany("INSERT INTO sl_races VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", race_rows)
            con.executemany("INSERT INTO sl_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", cands)
            con.executemany("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", sources)
            con.executemany("INSERT INTO sl_places VALUES (?,?,?,?,?)", place_rows)
    finally:
        con.close()

    counts = ", ".join(f"{k} {v}" for k, v in sorted(by_kind.items()))
    say(f"    West Virginia: {len(races)} state races on the November ballot ({counts}), {gen_rows} candidates "
        f"({write_ins} declared write-in); {fields} party primaries with a field, votes from the official results; "
        f"{sum(1 for c in cands if c[1] == 'general' and c[7])} incumbents matched")
    for p in problems:
        say(f"      CHECK {p}")
    for t in ties:
        say(f"      CHECK the {t} primary is tied at the top; no outcome stored")
    for x in leaders_off:
        say(f"      note: a primary leader not on the November listing: {x}")
    return {"races": len(races), "candidates": gen_rows, "by_kind": dict(by_kind), "fields": fields, "uncontested": uncontested,
            "problems": problems, "ties": ties, "leaders_off": leaders_off, "read": read, "skipped": dict(skipped)}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("usage: python -m ballot.state_local_wv <database> [cache folder]")
    load(sys.argv[1], cache=sys.argv[2] if len(sys.argv) > 2 else CACHE)
