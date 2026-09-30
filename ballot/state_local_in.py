"""
ballot/state_local_in.py - Indiana's state races on the November 3, 2026 ballot: the 25 State Senate seats up this year
(four-year terms, half the chamber every two years), all 100 seats of the House of Representatives, and the three
statewide offices elected in 2026 (Secretary of State, Auditor of State, Treasurer of State), with each party's May 5
primary field and its certified votes.

Sources, all the Indiana Election Division's own (the same ones the federal loader, ballot/lists/in.py, reads):
  - The certified results of the May 5, 2026 primary, from its election results site (enr.indianavoters.in.gov).
    settings.json says which election the site holds and whether it is certified, and gives the party table;
    statewideElectionsC names the office categories; each category's OffCatC file gives, per district, every
    candidate's name as on the ballot, party, votes and whether they won, and the same per county. Every candidate's
    county votes must add up to the district total, and each party's field must have exactly one winner. The race list
    in the results is also how the 25 Senate districts on the 2026 ballot are known. Only the State Senator and State
    Representative categories are read; the site's candidate contact pages are never requested.
  - The "2026 Primary Candidate List" workbook (dated 3.25.26), linked from the Candidate Information page: every
    State Senator and State Representative candidate on the results must be on the list for the same district and
    party, and the other way round (differences are reported, not fatal: a withdrawal after March shows up here).
  - The "2026 General Election Candidate List" workbook, linked from the same page. As of 2026-09-30 the link
    (.../files/Candidate_List_Abbreviated_2026..9.11.xlsx) is answered with in.gov's "Page Not Found" page; a copy
    saved by hand as ballot_cache/in/in_candidate_list_2026_general.xlsx (the file the federal loader also looks for)
    is read instead when one is there. Until then no November candidates are stored and every race says so: the
    primary winners alone would leave off Libertarian and independent candidates, ballot vacancies filled by the
    parties since May, and the convention nominees for the three statewide offices.
The Secretary of State, Auditor of State and Treasurer of State are not on the primary ballot: the major parties'
state convention delegates choose those nominees (the results site's own description of the Convention Delegate
office says so, and the loader checks that it still does).

Holders of each seat come from the Open States roster in state_in.sqlite (legislators, is_current = 1; the officials
table for the Secretary of State). The roster does not carry the Auditor or the Treasurer, so no holder is shown for
those two. A candidate is marked as holding the seat when the name fits the sitting member for that chamber and
district, and tied to a sitting member of another seat only when the name fits exactly one sitting legislator of the
same party; every such match is printed for reading.

Privacy: only office, district, candidate name, party, ballot order, status and votes are read. The workbooks'
columns are taken by name (OFFICE, CANDIDATE NAME, POLITICAL PARTY, DISTRICT, and STATUS or BALLOT ORDER where the
general list carries one); DATE FILED and anything else is never read. The workbooks are not kept: only the state
office rows' allowed cells go to JSON in ballot_cache/in/ (sl_in_*.json), with the SHA-256 of the file they came
from. From the results, only names as on the ballot, party, votes, winner marks and county codes are kept.

    python -m ballot.state_local_in <path to a test database>
"""

import datetime as dt
import hashlib
import importlib
import io
import json
import os
import re
import sqlite3
import sys
import time
from urllib.error import HTTPError, URLError

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import openpyxl  # noqa: E402

from ballot.common import CACHE, fold, name_parts, party_code  # noqa: E402
from ballot.match import fits  # noqa: E402
from states import net  # noqa: E402

INL = importlib.import_module("ballot.lists.in")        # the federal loader: links(), fetch_workbook(), shown(), dated()

STATE, FIPS = "IN", "18"
GENERAL, PRIMARY = "2026-11-03", "2026-05-05"
ENR = "https://enr.indianavoters.in.gov/site/data/"
ENR_SITE = "https://enr.indianavoters.in.gov/site/index.html"
ROSTER = os.path.join(HERE, "state_in.sqlite")
HAND = "in_candidate_list_2026_general.xlsx"
SRC_SENATE, SRC_HOUSE = "in-ied-2026-state-primary-senate", "in-ied-2026-state-primary-house"
SRC_PLIST, SRC_GLIST, SRC_ROSTER = "in-ied-2026-state-primary-list", "in-ied-2026-state-general-list", "in-openstates-roster"

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

# The results site's office categories read here, and what each is: (race prefix, office_kind, office as Indiana writes it).
CATEGORIES = {"State Senator": ("SS", "state_senate", "State Senator"),
              "State Representative": ("SH", "state_house", "State Representative")}
SOURCE_OF = {"state_senate": SRC_SENATE, "state_house": SRC_HOUSE}
# The statewide offices on the 2026 ballot: (race suffix, office_kind, office, roster officials.office or None).
STATEWIDE = {"SECRETARY OF STATE": ("SOS", "secretary_of_state", "Secretary of State", "secretary of state"),
             "AUDITOR OF STATE": ("AUD", "state_auditor", "Auditor of State", None),
             "TREASURER OF STATE": ("TREAS", "state_treasurer", "Treasurer of State", None)}
LIST_OFFICE = {"STATE SENATOR": "state_senate", "STATE REPRESENTATIVE": "state_house"}
CONVENTION = ("Secretary of State", "Treasurer of State", "Auditor of State")
PRIMARY_CODE = {"Democratic": "DEM", "Republican": "REP"}
KEEP = ("OFFICE", "CANDIDATE NAME", "POLITICAL PARTY", "DISTRICT")
OPTIONAL = ("STATUS", "CANDIDATE STATUS", "BALLOT ORDER")
DISTRICT = re.compile(r"District (\d+)$")
COURT = re.compile(r"SUPREME COURT|COURT OF APPEALS|TAX COURT", re.I)

SENATE_NOTE = ("Indiana senators serve four-year terms; half the Senate's 50 seats are on the ballot every two years. "
               "This is one of the 25 on the 2026 ballot (the districts on the Election Division's May 5 primary ballot).")
CONVENTION_NOTE = ("Not on the May primary ballot: Indiana's major parties choose their nominees for this office at their state "
                   "conventions (the Election Division's results site, under Convention Delegate).")
WAITING_NOTE = ("The November candidates are not loaded yet: the Election Division's 2026 General Election Candidate List "
                "cannot be read (its link on the Candidate Information page answers Page Not Found).")
CAPS_NOTE = INL.CAPS_NOTE
WRITE_IN_NOTE = INL.WRITE_IN_NOTE


def as_list(x):
    return x if isinstance(x, list) else ([] if x is None else [x])


def fetch(url, accept="*/*", say=print):
    """One request, asked at most twice more on a refusal or a server error (never past a challenge page)."""
    for attempt in range(3):
        try:
            return net.get(url, accept=accept)
        except HTTPError as e:
            if e.code not in (403, 429, 500, 502, 503, 504) or attempt == 2:
                raise
            say(f"      {url}: HTTP {e.code}; asking again in {10 * (attempt + 1)} s")
            time.sleep(10 * (attempt + 1))


def enr(name, say=print):
    raw = fetch(ENR + name + ".json", accept="application/json", say=say)
    data = json.loads(raw.decode("utf-8-sig"))
    return data.get("Root", data), hashlib.sha256(raw).hexdigest()


def fresh(path, days):
    return os.path.exists(path) and time.time() - os.path.getmtime(path) < days * 86400


# ------------------------------------------------------------------------------------------ the certified primary results

def primary_results(folder, say):
    """The certified May 5 results for State Senator and State Representative, kept fields only, as JSON in the cache.
    The results site will turn to the November election; the copy on disk is used once it no longer holds the primary."""
    path = os.path.join(folder, "sl_in_primary_results.json")
    if fresh(path, 30):
        return path
    settings, _ = enr("settings", say)
    if settings.get("CurrentElection") != "05/05/2026" or settings.get("ElectionType") != "P":
        if os.path.exists(path):
            say("      the results site no longer holds the May 5 primary; using the copy read earlier")
            return path
        raise SystemExit(f"Indiana: the results site holds the election of {settings.get('CurrentElection')}, not the May 5, 2026 primary")
    if settings.get("Certified") != "T":
        raise SystemExit("Indiana: the May 5 primary results are not marked certified on the results site")
    parties = {p["POLITICALPARTYID"]: p["PARTY_NAME"] for p in as_list(settings["PolParties"]["PolParty"])}
    version = settings["VersionType"]
    offices, _ = enr(f"statewideElectionsC_{version}", say)
    items = [it for grp in offices["List"] for it in as_list((grp.get("Items") or {}).get("Item"))]
    names = {it.get("OFFICE_CATEGORY_NAME"): it for it in items}
    for statewide in CONVENTION:
        if statewide in names:
            raise SystemExit(f"Indiana: the primary results now carry {statewide}; this loader treats it as a convention nomination")
    delegate = (names.get("Convention Delegate") or {}).get("OFFICE_CATEGORY_DESCRIPTION", "")
    convention = all(o in delegate for o in CONVENTION)
    keep = {"election": settings["CurrentElection"], "certified": settings["Certified"], "version": settings["VersionCode"],
            "version_type": version, "read": dt.date.today().isoformat(), "convention_described": convention, "categories": {}}
    for cname in CATEGORIES:
        if cname not in names:
            raise SystemExit(f"Indiana: the results site has no office category named {cname!r}")
        cat = names[cname]["OFFICECATEGORYID"]
        data, digest = enr(f"OffCatC_{cat}_{version}", say)
        counties = {}                                       # office title -> [[fips, county, [[name, party, votes]...]]]
        for region in as_list(data["OfficeCategory"]["Regions"]["Region"]):
            for race in as_list((region.get("Races") or {}).get("Race")):
                j = race["Jurisdiction"]
                counties.setdefault(race["OFFICE_TITLE"], []).append(
                    [j["FIPS"], j["JURISDICTION_NAME"],
                     [[c["NAME_ON_BALLOT"], parties.get(c["POLITICALPARTYID"], c["POLITICALPARTYID"]), int(c["TOTAL_VOTES"])]
                      for c in as_list(race["Candidates"]["Candidate"])]])
        races = []
        for race in as_list(data["StatewideSummary"]["Race"]):
            races.append({"office": race["OFFICE_TITLE"], "sort": race["SubSortOrder"], "seats": race["NumofSeats"],
                          "candidates": [{"name": c["NAME_ON_BALLOT"], "party": parties.get(c["POLITICALPARTYID"], c["PARTY"]),
                                          "votes": int(c["TOTAL"]), "winner": c["isWinner"] == "T"}
                                         for c in as_list(race["Candidates"]["Candidate"])],
                          "counties": counties.get(race["OFFICE_TITLE"], [])})
        keep["categories"][cname] = {"id": cat, "file": f"OffCatC_{cat}_{version}.json", "sha256": digest,
                                     "written": data.get("WriteTime"), "races": races}
    json.dump(keep, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return path


# ------------------------------------------------------------------------------------------------ the candidate lists

def workbook_rows(data, election, wanted):
    """(heading, [rows]) from one of the Division's candidate list workbooks: the heading row must name the election;
    columns are taken by name (KEEP, and OPTIONAL where present); only rows whose OFFICE wanted() accepts are kept,
    and of those only the named cells. Court offices on the list are counted, not read."""
    wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    rows = wb.worksheets[0].iter_rows(values_only=True)
    heading, heads = None, None
    for i, r in enumerate(rows):
        cells = [str(c).strip() if c is not None else "" for c in r]
        if heading is None and any(cells):
            heading = " ".join(c for c in cells if c)
        if all(k in cells for k in KEEP):
            heads = cells
            break
        if i > 20:
            break
    if not heads:
        raise SystemExit(f"Indiana: the candidate list's columns changed (no row with {', '.join(KEEP)})")
    if election not in (heading or "").upper():
        raise SystemExit(f"Indiana: the candidate list is not the {election} (its heading reads {heading!r})")
    idx = {k: heads.index(k) for k in KEEP + OPTIONAL if k in heads}
    out, courts = [], 0
    for r in rows:
        office = str(r[idx["OFFICE"]]).strip() if idx["OFFICE"] < len(r) and r[idx["OFFICE"]] is not None else ""
        if COURT.search(office):
            courts += 1
        if not wanted(office):
            continue
        out.append({k: (str(r[i]).strip() if i < len(r) and r[i] is not None else "") for k, i in idx.items()})
    return heading, out, courts


def is_state_office(office):
    o = re.sub(r"\s+", " ", office.upper()).strip()
    return o in LIST_OFFICE or o in STATEWIDE


def candidate_list(folder, kind, url, say, max_age_days, election, hand=None):
    """A candidate list's state office rows, as JSON in the cache (sl_in_<kind>_list.json): fetched afresh when older
    than max_age_days, else read back. A workbook saved by hand is read when the address gives none. Returns the path,
    or None when there is no list to read."""
    path = os.path.join(folder, f"sl_in_{kind}_list.json")
    if fresh(path, max_age_days):
        return path
    data = INL.fetch_workbook(url, say) if url else None
    origin = url
    if data is None and hand and os.path.exists(hand):
        data, origin = open(hand, "rb").read(), "saved by hand: " + os.path.basename(hand)
        if data[:2] != b"PK":
            raise SystemExit(f"Indiana: {hand} is not a workbook")
    if data is None:
        if os.path.exists(path):
            say(f"      using the copy of the {kind} list read earlier")
            return path
        return None
    heading, rows, courts = workbook_rows(data, election, is_state_office)
    meta = {"url": url, "origin": origin, "sha256": hashlib.sha256(data).hexdigest(), "heading": heading,
            "published": INL.dated(url) if origin == url else "", "read": dt.date.today().isoformat(),
            "court_rows": courts, "columns": sorted({k for r in rows for k in r}), "rows": rows}
    json.dump(meta, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return path


# ---------------------------------------------------------------------------------------------------------- the roster

def roster(path):
    """Sitting legislators and statewide officials: ids, names, party, chamber and district only (the roster's
    contact columns are never selected)."""
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    legs = [dict(zip(("id", "first", "last", "full", "other", "party", "chamber", "district"), r)) for r in con.execute(
        "SELECT bioguide_id, first_name, last_name, official_full, other_names, party_name, chamber, district "
        "FROM legislators WHERE is_current = 1")]
    offs = {r[1]: dict(zip(("id", "office", "full", "first", "last", "party"), r)) for r in con.execute(
        "SELECT bioguide_id, office, official_full, first_name, last_name, party_name FROM officials")}
    con.close()
    return legs, offs


def person_fits(name, p):
    """A listed name fits a roster person: same family name and a given name that fits (the roster's own first name
    or any other form of the name it keeps)."""
    cand = name_parts(name)
    forms = [(fold(p["first"] or "").split(), " ".join(fold(p["last"] or "").split()))]
    forms += [name_parts(o.strip()) for o in (p.get("other") or "").split(";") if o.strip() and "," not in o and "." not in o]
    return any(f[1] and fits(cand, f) for f in forms)


def names_fit(a, b):
    pa, pb = name_parts(a), name_parts(b)
    return fits(pa, pb) or fits(pb, pa)


def chamber_words(p):
    return f"Indiana {'Senate' if p['chamber'] == 'Senate' else 'House'}, District {int(p['district'])}"


# ------------------------------------------------------------------------------------------------------------ loading

def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def mtime(path):
    return dt.datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d")


def load(db_path, say=print, cache=CACHE, roster_db=ROSTER):
    net.patient_lookups()
    folder = os.path.join(cache, "in")
    os.makedirs(folder, exist_ok=True)
    report = []

    page = fetch(INL.PAGE, say=say).decode("utf-8", "replace")
    found = INL.links(page)
    general_url, primary_url = found.get(INL.GENERAL_LABEL), found.get(INL.PRIMARY_LABEL)
    if not primary_url and not os.path.exists(os.path.join(folder, "sl_in_primary_list.json")):
        raise SystemExit(f"Indiana: the Candidate Information page no longer links \"{INL.PRIMARY_LABEL}\"")
    if not general_url:
        report.append(f"the Candidate Information page no longer links \"{INL.GENERAL_LABEL}\"")
    rpath = primary_results(folder, say)
    ppath = candidate_list(folder, "primary", primary_url, say, 30, "2026 PRIMARY ELECTION")
    gpath = candidate_list(folder, "general", general_url, say, 2, "2026 GENERAL ELECTION", hand=os.path.join(folder, HAND))
    results = json.load(open(rpath, encoding="utf-8"))
    plist = json.load(open(ppath, encoding="utf-8"))
    glist = json.load(open(gpath, encoding="utf-8")) if gpath else None
    legs, offs = roster(roster_db)
    if not results.get("convention_described"):
        report.append("the results site's Convention Delegate description no longer names the three statewide offices")

    # ---- races: the legislative seats on the primary ballot, and the three statewide offices
    races, cands, counties_seen, fields = {}, [], {}, {}
    for cname, (prefix, okind, office) in CATEGORIES.items():
        for race in results["categories"][cname]["races"]:
            m, m2 = DISTRICT.search(race["office"]), DISTRICT.search(race["sort"])
            if not m or not m2 or int(m.group(1)) != int(m2.group(1)) or race["seats"] != "1":
                raise SystemExit(f"Indiana: could not read one seat and its district from {race['office']!r}")
            d = str(int(m.group(1)))
            rid = f"2026-{STATE}-{prefix}{d}"
            if rid in races:
                raise SystemExit(f"Indiana: {race['office']} is listed twice in the results")
            chamber = "Senate" if okind == "state_senate" else "House"
            hs = [p for p in legs if p["chamber"] == chamber and str(p["district"]).lstrip("0") == d]
            h = hs[0] if len(hs) == 1 else None
            if h is None:
                report.append(f"{rid}: {len(hs)} sitting members in the roster for this seat")
            cids = sorted({c[0] for c in race["counties"]})
            for fips, cname2, _ in race["counties"]:
                if not re.fullmatch(r"18\d{3}", fips):
                    raise SystemExit(f"Indiana: county code {fips!r} under {race['office']} is not an Indiana county")
                counties_seen[fips] = cname2
            note = [SENATE_NOTE] if okind == "state_senate" else []
            if h is None:
                note.append("The roster shows no sitting member for this seat.")
            if glist is None:
                note.append(WAITING_NOTE)
            races[rid] = dict(race_id=rid, state=STATE, level="legislature", office_kind=okind, office=office,
                              jurisdiction=f"{'Senate' if chamber == 'Senate' else 'House'} District {d}", jurisdiction_id=d,
                              county_ids=json.dumps(cids) if cids else None, district=d, seat=None, special=0, partisan=1,
                              holder_id=h["id"] if h else None, holder_name=h["full"] if h else None,
                              holder_party=h["party"] if h else None, election_date=GENERAL, note=" ".join(note) or None,
                              _holder=h, _src=SOURCE_OF[okind], _race=race)
    for heading, (suffix, okind, office, rkey) in STATEWIDE.items():
        rid = f"2026-{STATE}-{suffix}"
        h = offs.get(rkey) if rkey else None
        note = [CONVENTION_NOTE]
        if rkey is None:
            note.append("The Open States roster does not carry this office, so no holder is shown.")
        if glist is None:
            note.append(WAITING_NOTE)
        races[rid] = dict(race_id=rid, state=STATE, level="statewide", office_kind=okind, office=office, jurisdiction="Indiana",
                          jurisdiction_id=FIPS, county_ids=None, district=None, seat=None, special=0, partisan=1,
                          holder_id=h["id"] if h else None, holder_name=h["full"] if h else None,
                          holder_party=h["party"] if h else None, election_date=GENERAL, note=" ".join(note),
                          _holder=h, _src=None, _race=None)

    nsen = sum(1 for r in races.values() if r["office_kind"] == "state_senate")
    nhouse = sum(1 for r in races.values() if r["office_kind"] == "state_house")
    if nsen != 25:
        report.append(f"the primary results list {nsen} Senate districts; half the Senate is 25 (a seat nobody filed for in May would be missing)")
    if nhouse != 100:
        report.append(f"the primary results list {nhouse} House districts, not all 100")

    def identify(race, name, party):
        """(incumbent, state_member_id, note) for one listed name."""
        h = race["_holder"]
        if h is not None and person_fits(name, h):
            return 1, h["id"], None
        pool = [p for p in legs if (p["party"] or "") == (party or "") and person_fits(name, p)]
        if len(pool) == 1 and not (h is not None and pool[0]["id"] == h["id"]):
            return 0, pool[0]["id"], f"Serves today in the {chamber_words(pool[0])}."
        return 0, None, None

    # ---- primary fields: official votes; county rows reconciled to the district totals
    nfields = 0
    for rid, race in races.items():
        r = race["_race"]
        if r is None:
            continue
        by_party = {}
        for c in r["candidates"]:
            by_party.setdefault(c["party"], []).append(c)
        county_sum = {}
        for _fips, _cn, cs in r["counties"]:
            for name, party, votes in cs:
                county_sum[(name, party)] = county_sum.get((name, party), 0) + votes
        for c in r["candidates"]:
            if county_sum.get((c["name"], c["party"])) != c["votes"]:
                report.append(f"{rid}: {c['name']} ({c['party']}) has {c['votes']} votes in the district total but "
                              f"{county_sum.get((c['name'], c['party']))} across its counties")
        extra = set(county_sum) - {(c["name"], c["party"]) for c in r["candidates"]}
        if extra:
            report.append(f"{rid}: county rows name candidates the district total does not: {sorted(extra)}")
        for party, cs in sorted(by_party.items()):
            if party not in PRIMARY_CODE:
                raise SystemExit(f"Indiana: {rid} has a {party!r} primary; this loader knows only {sorted(PRIMARY_CODE)}")
            winners = [c for c in cs if c["winner"]]
            if len(winners) != 1:
                raise SystemExit(f"Indiana: {rid} {party} primary has {len(winners)} winners marked")
            if max(c["votes"] for c in cs) != winners[0]["votes"]:
                report.append(f"{rid} {party} primary: the winner marked did not have the most votes")
            fields[(rid, party)] = winners[0]["name"]
            if len(cs) < 2:
                continue
            nfields += 1
            total = sum(c["votes"] for c in cs)
            for c in cs:
                name, caps = INL.shown(c["name"])
                inc, mid, n2 = identify(race, name, party)
                cands.append([rid, f"primary-{PRIMARY_CODE[party]}", PRIMARY, name, party, party_code(party), None, inc, 0,
                              c["votes"], round(100 * c["votes"] / total, 1) if total else None,
                              "advanced" if c["winner"] else "lost", mid, race["_src"],
                              " ".join(x for x in (CAPS_NOTE if caps else None, n2) if x) or None])

    # ---- the primary candidate list against the results (names by fit, same district and party)
    listed = {}
    for row in plist["rows"]:
        okind = LIST_OFFICE.get(re.sub(r"\s+", " ", row["OFFICE"].upper()).strip())
        m = DISTRICT.search(row["DISTRICT"])
        if not okind or not m:
            raise SystemExit(f"Indiana: could not read the office and district of a primary list row ({row['OFFICE']}, {row['DISTRICT']})")
        rid = f"2026-{STATE}-{'SS' if okind == 'state_senate' else 'SH'}{int(m.group(1))}"
        listed.setdefault((rid, row["POLITICAL PARTY"]), []).append(INL.shown(row["CANDIDATE NAME"])[0])
    on_results = {}
    for rid, race in races.items():
        for c in (race["_race"] or {}).get("candidates", []):
            on_results.setdefault((rid, c["party"]), []).append(INL.shown(c["name"])[0])
    differ = []
    for k in sorted(set(listed) | set(on_results)):
        a, b = listed.get(k, []), on_results.get(k, [])
        only_list = [n for n in a if not any(names_fit(n, x) for x in b)]
        only_res = [n for n in b if not any(names_fit(n, x) for x in a)]
        if only_list or only_res:
            differ.append(f"{k[0]} {k[1]}: on the March list only {only_list}, on the results only {only_res}")
    report += [f"primary list and results differ: {d}" for d in differ]

    # ---- the November list, when it can be read
    general, gone, unknown = [], [], set()
    if glist:
        order_given = any("BALLOT ORDER" in r for r in glist["rows"])
        for row in glist["rows"]:
            office = re.sub(r"\s+", " ", row["OFFICE"].upper()).strip()
            status = (row.get("STATUS") or row.get("CANDIDATE STATUS") or "").lower()
            if any(g in status for g in INL.GONE):
                gone.append(row)
                continue
            if office in STATEWIDE:
                rid = f"2026-{STATE}-{STATEWIDE[office][0]}"
            else:
                okind = LIST_OFFICE[office]
                m = DISTRICT.search(row["DISTRICT"])
                if not m:
                    raise SystemExit(f"Indiana: could not read the district of {row['DISTRICT']!r} on the general list")
                rid = f"2026-{STATE}-{'SS' if okind == 'state_senate' else 'SH'}{int(m.group(1))}"
                if rid not in races:
                    unknown.add(rid)
                    continue
            race = races[rid]
            name, caps = INL.shown(row["CANDIDATE NAME"])
            party = row["POLITICAL PARTY"]
            write_in = int("write" in (party + " " + row["OFFICE"]).lower())
            given = row.get("BALLOT ORDER", "")
            inc, mid, n2 = identify(race, name, party)
            note = " ".join(x for x in (CAPS_NOTE if caps else None, WRITE_IN_NOTE if write_in else None, n2) if x) or None
            general.append([rid, "general", GENERAL, name, party, party_code(party), int(given) if str(given).isdigit() else None,
                            inc, write_in, None, None, None, mid, SRC_GLIST, note])
        if unknown:
            report.append(f"the general list names legislative seats not on the primary ballot (not loaded): {sorted(unknown)}")
        if not order_given:
            report.append("the general list carries no ballot order; ballot_order left empty")
        if glist.get("court_rows"):
            report.append(f"the general list carries {glist['court_rows']} court rows (retention questions); not loaded by this loader")
        for (rid, party), winner in fields.items():
            mine = [g for g in general if g[0] == rid and g[4] == party]
            if not any(names_fit(g[3], INL.shown(winner)[0]) for g in mine):
                report.append(f"{rid}: the {party} primary winner ({INL.shown(winner)[0]}) is not the {party} candidate on the November list "
                              f"({', '.join(g[3] for g in mine) or 'none'})")
        for rid in races:
            if not any(g[0] == rid for g in general):
                report.append(f"{rid}: no candidates on the November list")
        cands = general + cands

    seen = set()
    for c in cands:
        k = (c[0], c[1], c[3])
        if k in seen:
            raise SystemExit(f"Indiana: {c[3]} is listed twice in {c[0]} {c[1]}")
        seen.add(k)

    # ---- write: Indiana's rows only, in one transaction
    cols = ["race_id", "state", "level", "office_kind", "office", "jurisdiction", "jurisdiction_id", "county_ids", "district", "seat",
            "special", "partisan", "holder_id", "holder_name", "holder_party", "election_date", "note"]
    race_rows = [tuple(r[c] for c in cols) for r in races.values()]
    place_rows = [("county", f, f"{n} County", json.dumps([f]), SRC_HOUSE) for f, n in sorted(counties_seen.items())]
    if len(place_rows) != 92:
        report.append(f"the results name {len(place_rows)} counties; Indiana has 92")
    primary_rows = [c for c in cands if c[1] != "general"]
    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA)
    with con:
        con.execute("DELETE FROM sl_candidates WHERE race_id IN (SELECT race_id FROM sl_races WHERE state = ?)", (STATE,))
        con.execute("DELETE FROM sl_candidates WHERE race_id LIKE ?", (f"2026-{STATE}-%",))
        con.execute("DELETE FROM sl_races WHERE state = ?", (STATE,))
        con.execute("DELETE FROM sl_places WHERE kind = 'county' AND id GLOB '18[0-9][0-9][0-9]'")
        con.execute("DELETE FROM sl_sources WHERE state = ?", (STATE,))
        con.executemany(f"INSERT INTO sl_races VALUES ({','.join('?' * len(cols))})", race_rows)
        con.executemany("INSERT INTO sl_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", cands)
        con.executemany("INSERT INTO sl_places VALUES (?,?,?,?,?)", place_rows)
        src = []
        for cname, sid in (("State Senator", SRC_SENATE), ("State Representative", SRC_HOUSE)):
            cat = results["categories"][cname]
            n = sum(len(r["candidates"]) for r in cat["races"])
            src.append((sid, STATE, "official results", "Indiana Election Division",
                        f"Indiana Election Results: May 5, 2026 Primary Election, {cname} (certified)", ENR + cat["file"],
                        (cat.get("written") or "")[:10], results["read"], cat["sha256"], n,
                        f"From the Division's election results site ({ENR_SITE}), marked certified; version {results['version']}. "
                        f"{len(cat['races'])} districts, {n} candidates. Names as on the ballot, party, votes and winner marks; every "
                        "candidate's county votes reconciled to the district total. The results carry no write-in line, so a field's "
                        "total is the sum of its candidates' votes. A field is a party primary with two candidates or more."
                        + (" The county codes (Census FIPS) listed under each district are the race's county_ids." if sid == SRC_HOUSE else "")))
        src.append((SRC_PLIST, STATE, "official candidate list", "Indiana Election Division",
                    f"2026 Primary Candidate List ({plist['heading']})", plist["url"], plist["published"], plist["read"], plist["sha256"],
                    len(plist["rows"]),
                    "State Senator and State Representative rows kept (office, name, party, district); nothing else read. Used to check "
                    "the primary results: " + ("every candidate agrees." if not differ else "differences: " + "; ".join(differ))))
        if glist:
            src.append((SRC_GLIST, STATE, "official candidate list", "Indiana Election Division",
                        f"2026 General Election Candidate List ({glist['heading']})", glist["url"] or INL.PAGE, glist["published"],
                        glist["read"], glist["sha256"], len(general),
                        f"{'Saved by hand' if glist['origin'] != glist['url'] else 'Fetched from the link on the Candidate Information page'}. "
                        f"State Senator, State Representative and statewide office rows kept ({', '.join(glist['columns'])}). "
                        f"Withdrawn or removed, left off: {len(gone)}."))
        src.append((SRC_ROSTER, STATE, "roster", "Open States people project (CC0), as loaded into state_in.sqlite",
                    "Sitting legislators and statewide officials", "https://github.com/openstates/people", "", mtime(roster_db), sha(roster_db),
                    len(legs) + len(offs), "Who holds each seat today; the roster does not carry the Auditor of State or the Treasurer of State."))
        con.executemany("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", src)
    con.close()

    by = lambda kind, rows: sum(1 for c in rows if races[c[0]]["office_kind"] == kind)
    head = (f"    Indiana: {len(races)} races ({nsen} Senate, {nhouse} House, {len(races) - nsen - nhouse} statewide); "
            f"{nfields} primary fields, {len(primary_rows)} primary rows (Senate {by('state_senate', primary_rows)}, "
            f"House {by('state_house', primary_rows)}), certified votes")
    if glist:
        say(head + f"; {len(general)} candidates on the November list (Senate {by('state_senate', general)}, House "
                   f"{by('state_house', general)}, statewide {len(general) - by('state_senate', general) - by('state_house', general)}; "
                   f"{len(gone)} withdrawn left off)")
    else:
        say(head + f"; the November list is waiting: the Election Division's page links \"{INL.GENERAL_LABEL}\" to {general_url}, "
                   f"which in.gov answers with its Page Not Found page. Save the workbook as {os.path.join(folder, HAND)} if a copy "
                   "can be had.")
    for c in cands:
        if c[12]:
            say(f"      matched: {c[0]} {c[1]}: {c[3]} -> {c[12]}{' (holds this seat)' if c[7] else ''}")
    for line in report:
        say(f"      check: {line}")
    return len(general)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m ballot.state_local_in <database>")
    load(sys.argv[1])
