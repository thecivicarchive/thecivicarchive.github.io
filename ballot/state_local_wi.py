"""
ballot/state_local_wi.py - Wisconsin's state races on the November 3, 2026 ballot: Governor and Lieutenant Governor
(one ticket in November, nominated in separate party primaries in August), Attorney General, Secretary of State, State
Treasurer, the seventeen odd-numbered State Senate seats (four-year terms, the odd half up in 2026) and all 99 seats of
the Assembly, with each party's August 11 primary field and its official votes.

Sources, both the Wisconsin Elections Commission's own, both already cached for the federal loader (ballot/lists/wi.py)
because elections.wi.gov refuses scripts and serves browsers; this loader downloads nothing:
  - "Candidates on Ballot by Election", 2026 General Election (PDF). Four columns: ballot order, committee ID, candidate,
    party. Under each "Office : ... Incumbent: ..." heading one line per candidate, a long party name wrapping onto the
    next line ("Wisconsin" / "Green"), then "Total Number of ... Candidates :N", which is checked. Columns are found by
    where the page's own column headings start. The committee ID is never kept.
  - The County by County Report of the 2026 Partisan Primary (xlsx), one sheet per office and party, named in its
    Document map. Each sheet's county rows must add up to its "Office Totals:" row, and the candidates plus SCATTERING
    (write-ins nobody registered) to its Total Votes Cast. Registered write-ins are listed as "Name (write-in)".
    The county rows also say which counties each district reaches (their Census codes from the Bureau's county file).
Holders of each seat come from the Open States roster in state_wi.sqlite (legislators, is_current = 1; the officials
table for Governor, Lieutenant Governor and Attorney General). The roster does not carry the Secretary of State or the
Treasurer, so for those two the holder is the incumbent the Commission's list names.

Privacy: these two files carry no addresses, phones, e-mail or websites. Only office, district, name, party, ballot
order and votes are read and stored; nothing else from either file is kept, printed or logged.

    python -m ballot.state_local_wi <path to a test database>
"""

import datetime as dt
import hashlib
import io
import os
import re
import sqlite3
import sys
import zipfile

import openpyxl

from ballot.common import CACHE, HERE, fold, name_parts, party_code
from ballot.match import fits
from ballot.pdftext import PDF, join, rows

STATE, FIPS = "WI", "55"
GENERAL, PRIMARY = "2026-11-03", "2026-08-11"
LIST = "wi_candidates_on_ballot_2026_general.pdf"
BOOK = "wi_county_by_county_2026_partisan_primary.xlsx"
LIST_URL = "https://elections.wi.gov/media/40951/download"
BOOK_URL = ("https://elections.wi.gov/sites/default/files/documents/"
            "County%20by%20County%20Report_Partisan%20Primary%202026_All%20State%20Contests.xlsx")
COUNTY_ZIP = os.path.join(HERE, "states_cache", "census", "cb_2024_us_county_500k.zip")
ROSTER = os.path.join(HERE, "state_wi.sqlite")
SRC_LIST, SRC_BOOK = "wi-wec-2026-state-candidates-on-ballot", "wi-wec-2026-state-primary-county"
SRC_COUNTY, SRC_ROSTER = "wi-census-2024-county-codes", "wi-openstates-roster"

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

# The Commission's office headings, and what each is here: (race suffix, level, office_kind, office as shown).
STATEWIDE = {
    "GOVERNOR": ("GOV", "governor", "Governor and Lieutenant Governor"),
    "LIEUTENANT GOVERNOR": ("LTG", "lieutenant_governor", "Lieutenant Governor"),
    "ATTORNEY GENERAL": ("AG", "attorney_general", "Attorney General"),
    "SECRETARY OF STATE": ("SOS", "secretary_of_state", "Secretary of State"),
    "STATE TREASURER": ("TREAS", "state_treasurer", "State Treasurer"),
}
ROSTER_OFFICE = {"GOV": "governor", "LTG": "lt_governor", "AG": "attorney general"}     # officials.office in state_wi.sqlite
ON_LIST = ("GOVERNOR", "ATTORNEY GENERAL", "SECRETARY OF STATE", "STATE TREASURER")    # November; LTG rides on the GOV ticket
SENATE = re.compile(r"STATE SENATOR DISTRICT (\d+)")
ASSEMBLY = re.compile(r"REPRESENTATIVE TO THE ASSEMBLY DISTRICT (\d+)")
FEDERAL = re.compile(r"REPRESENTATIVE IN CONGRESS|UNITED STATES SENATOR")
PARTIES = {"Republican", "Democratic", "Libertarian", "Constitution", "Independent", "Wisconsin Green",
           "Serving People Not Parties", "American Solidarity Party"}
PRIMARY_CODE = {"Republican": "REP", "Democratic": "DEM", "Libertarian": "LIB", "Constitution": "CON", "Wisconsin Green": "WGR"}
OFFICE = re.compile(r"^Office : (?P<office>.+?)(?: Incumbent: (?P<inc>.*))?$")
TOTAL = re.compile(r"^Total Number of (?P<office>.+) Candidates :(?P<n>\d+)$")
FURNITURE = {"Candidates on Ballot by Election", "Wisconsin Elections Commission", "Ballot Committee Candidate Party", "Order# ID"}
STAMP = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4}) \d{1,2}:\d{2}:\d{2}")
NONCAND = "(Filed Notification of Noncandidacy)"
WRITE_IN = re.compile(r"\s*\((?:write-in)\)\s*$", re.I)


def race_of(office):
    """(race_id, level, office_kind, office, district) for a Commission office heading; None for a federal office."""
    o = office.strip()
    if FEDERAL.match(o):
        return None
    if o in STATEWIDE:
        kind, okind, shown = STATEWIDE[o]
        return f"2026-{STATE}-{kind}", "statewide", okind, shown, None
    m = SENATE.fullmatch(o)
    if m:
        return f"2026-{STATE}-SS{int(m.group(1))}", "legislature", "state_senate", "State Senator", str(int(m.group(1)))
    m = ASSEMBLY.fullmatch(o)
    if m:
        return f"2026-{STATE}-SH{int(m.group(1))}", "legislature", "state_house", "Representative to the Assembly", str(int(m.group(1)))
    raise SystemExit(f"Wisconsin: an office this loader does not know is on the list: {o!r}")


def key(text):
    return " ".join(fold(text).split())


# ---------------------------------------------------------------------------------------------------- the November list

def general_list(path):
    """[(office heading, incumbent named or '', filed noncandidacy, [(order, name, party)])] in the list's order, and the
    date the list was printed. Each office's candidates are counted against the list's own total."""
    pdf = PDF(open(path, "rb").read())
    offices, printed, cur, cols = [], "", None, None
    for page, res in pdf.pages():
        for _y, rs in rows(pdf, page, res):
            text = join(rs)
            if text.startswith("Ballot Committee"):                      # the column headings give the column edges
                at = {r[3].strip(): r[0] for r in rs}
                cols = (at["Committee"], at["Candidate"], at["Party"])
                continue
            m = STAMP.search(text)
            if m and not text[:1].isdigit() or text in FURNITURE or text.startswith("2026 General Election"):
                if m and not printed:
                    printed = f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
                continue
            m = OFFICE.match(text)
            if m:
                inc = (m.group("inc") or "").strip()
                cur = [m.group("office").strip(), inc.replace(NONCAND, "").strip(), NONCAND in inc, []]
                offices.append(cur)
                continue
            m = TOTAL.match(text)
            if m:
                if not cur or m.group("office").strip() != cur[0]:
                    raise SystemExit(f"Wisconsin: a total for {m.group('office')!r} came outside its office")
                if len(cur[3]) != int(m.group("n")):
                    raise SystemExit(f"Wisconsin: the list counts {m.group('n')} candidates for {cur[0]}; {len(cur[3])} were read")
                cur = None
                continue
            if cur is None or cols is None:
                continue
            order = join([r for r in rs if r[0] < cols[0] - 5])
            name = join([r for r in rs if cols[1] - 5 <= r[0] < cols[2] - 5])
            party = join([r for r in rs if r[0] >= cols[2] - 5])
            if order:
                if not order.isdigit() or not name:
                    raise SystemExit(f"Wisconsin: a candidate line under {cur[0]} has no ballot order or no name")
                cur[3].append([int(order), name, party])
            elif cur[3]:                                                    # a name or party wrapped onto the next line
                last = cur[3][-1]
                last[1] = f"{last[1]} {name}".strip()
                last[2] = f"{last[2]} {party}".strip()
    for office, _inc, _nc, cands in offices:
        for _o, name, party in cands:
            if party not in PARTIES:
                raise SystemExit(f"Wisconsin: {office} lists a party this loader does not know: {party!r} (add it to PARTIES)")
    return offices, printed


# ----------------------------------------------------------------------------------------------- the August primary

def primary_book(path):
    """{office heading: {"counties": set, "fields": {party: (code, total, [(name, write_in, votes)])}}}, every sheet's
    county rows added to its Office Totals and its candidates to its Total Votes Cast."""
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    titles = [r[1] for r in wb["Document map"].iter_rows(values_only=True) if len(r) > 1 and r[1]]
    out, problems = {}, []
    for k, title in enumerate(titles):
        title = str(title).strip()
        office, _, party = title.rpartition(" - ")
        if FEDERAL.match(office):
            continue
        race_of(office)                                                     # stops on an office not known here
        ws = wb.worksheets[k + 1]
        sheet = [tuple(r) for r in ws.iter_rows(values_only=True)]
        if not any(str(c or "").strip() == title for r in sheet[:5] for c in r):
            raise SystemExit(f"Wisconsin: sheet {ws.title} does not carry the office its Document map names ({title})")
        head = next(j for j, r in enumerate(sheet) if r and str(r[0] or "").strip() == "County")
        hdr, cands = sheet[head], sheet[head + 1]
        cast = next(j for j, c in enumerate(hdr) if str(c or "").strip() == "Total Votes Cast")
        totals = [r for r in sheet if r and str(r[0] or "").strip().startswith("Office Totals")]
        if len(totals) != 1:
            raise SystemExit(f"Wisconsin: {title} has {len(totals)} Office Totals rows")
        tot = totals[0]
        counties = [r for r in sheet[head + 2:] if r and r[0] and str(r[0]).strip() and not str(r[0]).strip().startswith("Office Totals")]
        cols = [j for j, c in enumerate(cands) if c and str(c).strip()]
        if sum(int(tot[j] or 0) for j in cols) != int(tot[cast] or 0):
            problems.append(f"{title}: candidates and write-ins do not add up to Total Votes Cast")
        for j in cols + [cast]:
            if sum(int(r[j] or 0) for r in counties) != int(tot[j] or 0):
                problems.append(f"{title}: county rows do not add up to Office Totals in column {j + 1}")
        entry = out.setdefault(office, {"counties": set(), "fields": {}})
        entry["counties"] |= {key(str(r[0])) for r in counties}
        abbr = next((str(c).strip() for c in hdr[cast + 1:] if c and str(c).strip()), "") or PRIMARY_CODE.get(party, party[:3].upper())
        field = []
        for j in cols:
            raw = str(cands[j]).strip()
            if raw == "SCATTERING":
                continue
            field.append((WRITE_IN.sub("", raw).strip(), bool(WRITE_IN.search(raw)), int(tot[j] or 0)))
        entry["fields"][party] = (abbr, int(tot[cast] or 0), field)
    if problems:
        raise SystemExit("Wisconsin: the primary report does not reconcile:\n  " + "\n  ".join(problems))
    return out


# -------------------------------------------------------------------------------------------------- the roster

def roster(path):
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    legs = [dict(zip(("id", "first", "last", "full", "other", "party", "chamber", "district"), r)) for r in con.execute(
        "SELECT bioguide_id, first_name, last_name, official_full, other_names, party_name, chamber, district FROM legislators WHERE is_current = 1")]
    offs = {r[1]: dict(zip(("id", "office", "full", "first", "last", "party"), r)) for r in con.execute(
        "SELECT bioguide_id, office, official_full, first_name, last_name, party_name FROM officials")}
    con.close()
    return legs, offs


def person_fits(name, p):
    """A listed name fits a roster person: same family name and a given name that fits (their roster name or any
    full form of it the roster keeps)."""
    cand = name_parts(name)
    forms = [(fold(p["first"] or "").split(), key(p["last"] or ""))]
    forms += [name_parts(o.strip()) for o in (p.get("other") or "").split(";") if o.strip() and "," not in o and "." not in o]
    return any(f[1] and fits(cand, f) for f in forms)


def chamber_words(p):
    return f"{'State Senate' if p['chamber'] == 'Senate' else 'Assembly'}, District {p['district']}"


# ---------------------------------------------------------------------------------------------------- loading

def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def mtime(path):
    return dt.datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d")


def census_counties(path):
    import shapefile                                                        # pyshp, in the kit's environment
    z = zipfile.ZipFile(path)
    base = next(n for n in z.namelist() if n.endswith(".dbf"))
    rdr = shapefile.Reader(dbf=io.BytesIO(z.read(base)))
    return {key(r["NAME"]): (r["GEOID"], r["NAME"]) for r in (x.as_dict() for x in rdr.iterRecords()) if r["STATEFP"] == FIPS}


def load(db_path, say=print, cache=CACHE, roster_db=ROSTER, county_zip=COUNTY_ZIP):
    folder = os.path.join(cache, "wi")
    lpath, bpath = os.path.join(folder, LIST), os.path.join(folder, BOOK)
    if not os.path.exists(lpath):
        say(f"    Wisconsin: {LIST} is not in {folder}. elections.wi.gov refuses scripts; the file is carried out of a browser "
            "(\"Candidates on Ballot By Election_November 3 2026 General Election.pdf\" on elections.wi.gov/elections).")
        return 0
    offices, printed = general_list(lpath)
    book = primary_book(bpath) if os.path.exists(bpath) else {}
    legs, offs = roster(roster_db)
    counties = census_counties(county_zip)
    report = []

    state = [o for o in offices if race_of(o[0])]
    heads = {o[0] for o in state}
    senate = sorted(int(SENATE.fullmatch(h).group(1)) for h in heads if SENATE.fullmatch(h))
    assembly = sorted(int(ASSEMBLY.fullmatch(h).group(1)) for h in heads if ASSEMBLY.fullmatch(h))
    if senate != list(range(1, 34, 2)):
        raise SystemExit(f"Wisconsin: the list's Senate seats are not the seventeen odd-numbered ones: {senate}")
    if assembly != list(range(1, 100)):
        raise SystemExit(f"Wisconsin: the list's Assembly seats are not all 99: {len(assembly)} listed")
    missing = [o for o in ON_LIST if o not in heads]
    if missing:
        raise SystemExit(f"Wisconsin: statewide offices missing from the list: {missing}")
    if len(state) != len(heads):
        raise SystemExit("Wisconsin: an office is listed twice")

    races, cands = {}, []
    ticket = {}                                                             # party -> (governor, lieutenant governor)

    def county_ids(office):
        names = book.get(office, {}).get("counties", set())
        bad = sorted(n for n in names if n not in counties)
        if bad:
            raise SystemExit(f"Wisconsin: county names in the primary report not in the Census file: {bad}")
        return ",".join(sorted(counties[n][0] for n in names)) or None

    def holder_of(rid, level, district, okind):
        if level == "legislature":
            chamber = "Senate" if okind == "state_senate" else "House"
            hs = [p for p in legs if p["chamber"] == chamber and str(p["district"]) == district]
            return hs[0] if len(hs) == 1 else None
        rk = ROSTER_OFFICE.get(rid.rsplit("-", 1)[1])
        return offs.get(rk) if rk else None

    def new_race(office, inc, noncand):
        rid, level, okind, shown, district = race_of(office)
        h = holder_of(rid, level, district, okind)
        note = []
        if h is None and level == "legislature":
            report.append(f"{rid}: no sitting member in the roster for this seat")
            note.append("The roster shows no sitting member for this seat.")
        hname, hparty, hid = (h["full"], h["party"], h["id"]) if h else (inc or None, None, None)
        if h is None and inc and level == "statewide":
            note.append("Holder as named on the Elections Commission's list; the Open States roster does not carry this office.")
        if h and inc and not person_fits(inc, h):
            report.append(f"{rid}: the Commission names {inc} as incumbent; the roster's holder is {h['full']}")
        if noncand and inc:
            note.append(f"{inc}, who holds the seat, filed a notification of noncandidacy.")
        if rid.endswith("-GOV"):
            note.append("Wisconsin elects the governor and lieutenant governor together in November, one vote for the pair; "
                        "each party nominates them in separate primaries (the lieutenant governor's under 2026-WI-LTG).")
        jur = "Wisconsin" if level == "statewide" else (f"Senate District {district}" if okind == "state_senate" else f"Assembly District {district}")
        races[rid] = [rid, STATE, level, okind, shown, jur, FIPS if level == "statewide" else district,
                      None if level == "statewide" else county_ids(office), district, None, 0, 1, hid, hname, hparty, GENERAL,
                      " ".join(note) or None]
        return rid, level, okind, h, inc

    def identify(rid, level, okind, h, inc, name, party):
        """(incumbent, state_member_id, note) for one listed name."""
        if h is not None and person_fits(name, h):
            return 1, h["id"], None
        if level == "statewide" and h is None and inc and person_fits(name, {"first": " ".join(name_parts(inc)[0]), "last": name_parts(inc)[1]}):
            return 1, None, "Named as the incumbent on the Elections Commission's list."
        pool = [p for p in legs if person_fits(name, p) and (p["party"] or "") == (party or "")]
        if len(pool) == 1 and not (h is not None and pool[0]["id"] == h["id"]):
            return 0, pool[0]["id"], f"Serves today in the {chamber_words(pool[0])}."
        return 0, None, None

    for office, inc, noncand, listed in state:
        rid, level, okind, h, inc = new_race(office, inc, noncand)
        for order, name, party in listed:
            note, mine = None, name
            if rid.endswith("-GOV"):
                gov, _, ltg = name.partition(" / ")
                if not ltg:
                    raise SystemExit(f"Wisconsin: a governor's line without a running mate: {name!r}")
                ticket[party] = (gov.strip(), ltg.strip())
                mine, note = gov.strip(), "Governor and lieutenant governor on one ticket, as the list prints them."
            incb, mid, n2 = identify(rid, level, okind, h, inc, mine, party)
            cands.append([rid, "general", GENERAL, name, party, party_code(party), order, incb, 0, None, None, None, mid, SRC_LIST,
                          " ".join(x for x in (note, n2) if x) or None])

    # The lieutenant governor: nominated in its own primary, elected on the governor's ticket in November.
    if "LIEUTENANT GOVERNOR" in book:
        new_race("LIEUTENANT GOVERNOR", "", False)
        races["2026-WI-LTG"][16] = ("Nominated in each party's own primary on August 11; in November the lieutenant governor is elected "
                                   "jointly with the governor, on the tickets listed under 2026-WI-GOV.")

    # Primary fields: two or more names on a party's sheet (registered write-ins count), official votes only.
    nominees = {}
    for rid in races:
        for c in cands:
            if c[0] == rid:
                nominees[(rid, c[4])] = c[3]
    for p, (gov, ltg) in ticket.items():
        nominees[("2026-WI-GOV", p)], nominees[("2026-WI-LTG", p)] = gov, ltg
    fields = 0
    for office, entry in book.items():
        rid = race_of(office)[0]
        if rid not in races:
            report.append(f"{rid}: in the primary report but not on the November list")
            continue
        _r, level, okind, _s, district = race_of(office)
        h = holder_of(rid, level, district, okind)
        for party, (code, total, field) in entry["fields"].items():
            if len(field) < 2:
                continue
            fields += 1
            nominee = nominees.get((rid, party))
            won = [n for n, _w, _v in field if nominee and person_fits(n, {"first": " ".join(name_parts(nominee)[0]), "last": name_parts(nominee)[1]})]
            top = max(field, key=lambda f: f[2])[0]
            if len(won) != 1:
                report.append(f"{rid} {party} primary: the November candidate ({nominee or 'none'}) is not one name in the field; outcome left blank")
            elif won[0] != top:
                report.append(f"{rid} {party} primary: {won[0]} is on the November list but {top} had the most votes")
            for name, wi, votes in field:
                incb, mid, n2 = identify(rid, level, okind, h, "", name, party)
                outcome = None if len(won) != 1 else ("advanced" if name == won[0] else "lost")
                cands.append([rid, f"primary-{code}", PRIMARY, name, party, party_code(party), None, incb, int(wi), votes,
                              round(100 * votes / total, 1) if total else None, outcome, mid, SRC_BOOK,
                              " ".join(x for x in ("Registered write-in candidate." if wi else None, n2) if x) or None])

    # Every November candidate of a party that held a primary should be among that party's primary names.
    for c in cands:
        if c[1] != "general" or c[4] not in PRIMARY_CODE:
            continue
        office = next((o for o in book if race_of(o)[0] == c[0]), None)
        name = ticket.get(c[4], (c[3],))[0] if c[0].endswith("-GOV") else c[3]
        names = [n for n, _w, _v in book.get(office, {}).get("fields", {}).get(c[4], ("", 0, []))[2]] if office else []
        if not any(person_fits(n, {"first": " ".join(name_parts(name)[0]), "last": name_parts(name)[1]}) for n in names):
            report.append(f"{c[0]}: {name} ({c[4]}) is on the November list but not among that party's primary names")

    seen = set()
    for c in cands:
        k = (c[0], c[1], c[3])
        if k in seen:
            raise SystemExit(f"Wisconsin: {c[3]} is listed twice in {c[0]} {c[1]}")
        seen.add(k)
    for rid in races:
        if rid != "2026-WI-LTG" and not any(c[0] == rid and c[1] == "general" for c in cands):
            report.append(f"{rid}: no candidates on the November list")

    general = [c for c in cands if c[1] == "general"]
    primary_rows = [c for c in cands if c[1] != "general"]
    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA)
    with con:
        con.execute("DELETE FROM sl_candidates WHERE race_id IN (SELECT race_id FROM sl_races WHERE state = ?)", (STATE,))
        con.execute("DELETE FROM sl_candidates WHERE race_id LIKE ?", (f"2026-{STATE}-%",))
        con.execute("DELETE FROM sl_races WHERE state = ?", (STATE,))
        con.execute("DELETE FROM sl_places WHERE source_id = ?", (SRC_COUNTY,))
        con.execute("DELETE FROM sl_sources WHERE state = ?", (STATE,))
        con.executemany("INSERT INTO sl_races VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", list(races.values()))
        con.executemany("INSERT INTO sl_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", cands)
        con.executemany("INSERT INTO sl_places VALUES (?,?,?,?,?)",
                        [("county", g, n, g, SRC_COUNTY) for g, n in sorted(counties.values())])
        src = [
            (SRC_LIST, STATE, "official candidate list", "Wisconsin Elections Commission",
             "Candidates on Ballot by Election: 2026 General Election, 11/3/2026", LIST_URL, printed, mtime(lpath), sha(lpath), len(general),
             "State offices only (the congressional lines are the federal loader's). Ballot order as printed; each office's count "
             "checked against the list's total. elections.wi.gov refuses scripts; the file was carried out of a browser."),
            (SRC_ROSTER, STATE, "roster", "Open States people project (CC0), as loaded into state_wi.sqlite",
             "Sitting legislators and statewide officials", "https://github.com/openstates/people", "", mtime(roster_db), sha(roster_db),
             len(legs) + len(offs), "Who holds each seat today; the roster does not carry the Secretary of State or the State Treasurer."),
            (SRC_COUNTY, STATE, "county codes", "U.S. Census Bureau", "Cartographic boundary file, counties, 2024 (1:500,000)",
             "https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_county_500k.zip", "2024", mtime(county_zip), sha(county_zip),
             len(counties), "Five-digit county codes (GEOID) for the counties the primary report lists under each district."),
        ]
        if book:
            src.append((SRC_BOOK, STATE, "official results", "Wisconsin Elections Commission",
                        "County by County Report: 2026 Partisan Primary, all state contests (August 11, 2026)", BOOK_URL, "", mtime(bpath),
                        sha(bpath), len(primary_rows),
                        "Votes from each office's Office Totals row; every sheet's county rows and candidates reconciled to its totals. "
                        "Write-ins nobody registered (SCATTERING) count in the total but are not listed; registered write-ins are."))
        con.executemany("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", src)
    con.close()

    by = lambda kind: sum(1 for c in general if races[c[0]][3] == kind)
    say(f"    Wisconsin: {len(races)} races ({len(senate)} Senate, {len(assembly)} Assembly, {len(races) - len(senate) - len(assembly)} statewide); "
        f"{len(general)} candidates on the November list (Senate {by('state_senate')}, Assembly {by('state_house')}, statewide "
        f"{len(general) - by('state_senate') - by('state_house')}); {fields} primary fields, {len(primary_rows)} primary rows")
    for c in cands:
        if c[12]:
            say(f"      matched: {c[0]} {c[1]}: {c[3]} -> {c[12]}{' (holds this seat)' if c[7] else ''}")
    for line in report:
        say(f"      check: {line}")
    return len(general)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m ballot.state_local_wi <database>")
    load(sys.argv[1])
