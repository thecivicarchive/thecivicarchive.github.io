"""
ballot/state_local_ok.py - Oklahoma's state races in 2026: the Oklahoma Senate seats up this year (the 24 even-numbered
districts, plus any seat filled for the rest of a term), all 101 Oklahoma House seats, the statewide offices (Governor,
Lieutenant Governor, State Auditor and Inspector, Attorney General, State Treasurer, Superintendent of Public
Instruction, Commissioner of Labor, Insurance Commissioner, Corporation Commissioner), and the district court judges
on the November ballot, with the June 16 party primaries that chose the nominees. Written into
ballot_local_2026.sqlite (never ballot_2026.sqlite).

Sources, all the Oklahoma State Election Board's own, the same ones the federal loader (ballot/lists/ok.py) reads:

  NOVEMBER / 2026 List of Elections (hosting.okelections.us/electionlist.html): county by county, every office on each
  county's November 3 ballot and under it each candidate as "NAME, PARTY" (judges by name alone). It carries names,
  parties and offices only. A district that spans several counties is listed once per county, and every county's
  list of it must agree. The list's order is kept as the ballot order, as the federal loader keeps it.

  Candidates for Office 2026 (the Candidate List Book, a PDF): everyone who filed April 1-3, 2026, by office, district
  and party. Each entry is one line of fixed-width type: the filing number, the name and the candidate's city. Only
  the first thirty character columns (the filing number and the name) are ever placed into text; the city column is
  never read. The book is read from the federal loader's cached copy when there is one, otherwise fetched into
  memory; it is never written to disk by this loader. What was read (office, district, party, filing number, name)
  is kept as a small JSON extract with the file's SHA-256.

  2026 Candidate Withdrawals (Number, Name, Office, Date; the federal loader's extract) and 2026 Contests of Candidacy
  (cause, the case name, office and ruling; kept as a small extract). A candidate who withdrew or was stricken before
  the June 16 primary was not on its ballot.

Oklahoma leaves a seat off the November ballot when it was settled earlier, and the November list shows it: a seat
with one candidate left once filing closed (stored as that candidate with outcome "unopposed" and a note, as the
federal Florida loader does), and a seat for which only one party's candidates filed (settled in that party's June 16
primary or August 25 runoff: the field is stored, with no winner, because the Board publishes results only on
results.okelections.us, which refuses scripts with 403 Forbidden). No vote counts are loaded, and which primaries went
to the August 25 runoff is not read. A primary field is two or more of a party's candidates on its June 16 ballot; the
nominee is that party's candidate on the November list.

Judges: the November list names the district and associate district judge races still to be decided in November;
only those are loaded (a judicial seat with one candidate, or decided by a majority in June, is not on the list and is
counted in the report). The Supreme Court, Court of Criminal Appeals and Court of Civil Appeals retention questions are
on every ballot, but the list does not name the judges, so they are not loaded. District attorneys and county offices
are left for the local loaders.

Today's holders come from the Open States roster in state_ok.sqlite (legislators by chamber and district; the
officials table for Governor, Lieutenant Governor and Attorney General); only id, name, party, chamber and district
are selected. A candidate is marked as the sitting member only when the name fits the roster's holder of that same
seat and no other candidate in the race fits.

Nothing but office, district, name, party, ballot order and status is read from any list; nothing else is printed,
logged, cached or stored.
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
from collections import Counter

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ballot.common import CACHE, HERE, fold, name_parts, party_code          # noqa: E402
from ballot.lists import ok as fed                                          # noqa: E402
from ballot.lists.tx import proper                                          # noqa: E402
from ballot.match import fits                                               # noqa: E402
from ballot.pdftext import PDF, join, rows as pdf_rows                     # noqa: E402
from states import net                                                     # noqa: E402

STATE, FIPS, NAME = "OK", "40", "Oklahoma"
GENERAL = "2026-11-03"
PRIMARY, RUNOFF = fed.PRIMARY, fed.RUNOFF
ROSTER_DB = os.path.join(HERE, "state_ok.sqlite")
COUNTY_ZIP = os.path.join(HERE, "states_cache", "census", "cb_2024_us_county_500k.zip")

SCHEMA = """
CREATE TABLE IF NOT EXISTS sl_races (race_id TEXT PRIMARY KEY, state TEXT NOT NULL, level TEXT NOT NULL, office_kind TEXT NOT NULL, office TEXT NOT NULL, jurisdiction TEXT, jurisdiction_id TEXT, county_ids TEXT, district TEXT, seat TEXT, special INTEGER NOT NULL DEFAULT 0, partisan INTEGER NOT NULL, holder_id TEXT, holder_name TEXT, holder_party TEXT, election_date TEXT NOT NULL, note TEXT);
CREATE TABLE IF NOT EXISTS sl_candidates (race_id TEXT NOT NULL, election TEXT NOT NULL, election_date TEXT, name TEXT NOT NULL, party TEXT, party_code TEXT, ballot_order INTEGER, incumbent INTEGER NOT NULL DEFAULT 0, write_in INTEGER NOT NULL DEFAULT 0, votes INTEGER, pct REAL, outcome TEXT, state_member_id TEXT, source_id TEXT, note TEXT, PRIMARY KEY (race_id, election, name));
CREATE TABLE IF NOT EXISTS sl_sources (source_id TEXT PRIMARY KEY, state TEXT, kind TEXT, agency TEXT, title TEXT, url TEXT, published TEXT, fetched TEXT, sha256 TEXT, rows INTEGER, note TEXT);
CREATE TABLE IF NOT EXISTS sl_places (kind TEXT NOT NULL, id TEXT NOT NULL, name TEXT NOT NULL, county_ids TEXT, source_id TEXT, PRIMARY KEY (kind, id));
"""

# statewide offices as both lists print them: (race key, office_kind, office shown, roster office in state_ok.sqlite)
STATEWIDE = {
    "GOVERNOR": ("GOV", "governor", "Governor", "governor"),
    "LIEUTENANT GOVERNOR": ("LTG", "lieutenant_governor", "Lieutenant Governor", "lt_governor"),
    "STATE AUDITOR AND INSPECTOR": ("AUD", "state_auditor", "State Auditor and Inspector", None),
    "ATTORNEY GENERAL": ("AG", "attorney_general", "Attorney General", "attorney general"),
    "STATE TREASURER": ("TREAS", "state_treasurer", "State Treasurer", None),
    "SUPERINTENDENT OF PUBLIC INSTRUCTION": ("SPI", "superintendent_of_public_instruction", "Superintendent of Public Instruction", None),
    "COMMISSIONER OF LABOR": ("LAB", "labor_commissioner", "Commissioner of Labor", None),
    "INSURANCE COMMISSIONER": ("INS", "insurance_commissioner", "Insurance Commissioner", None),
    "CORPORATION COMMISSIONER": ("CC", "corporation_commissioner", "Corporation Commissioner", None),
}
# the book's office headings (12-point) and what this loader does with each
BOOK_OFFICES = {"UNITED STATES SENATOR": "skip", "UNITED STATES REPRESENTATIVE": "skip", "DISTRICT ATTORNEY": "skip",
                "DISTRICT JUDGE": "DJ", "ASSOCIATE DISTRICT JUDGE": "ADJ", "STATE SENATOR": "SS", "STATE REPRESENTATIVE": "SH",
                **{k: "SW" for k in STATEWIDE}}
PARTIES = fed.PARTIES                                    # REPUBLICAN Republican, DEMOCRAT Democrat, ...
CODES = fed.CODES                                        # Republican REP, Democrat DEM, Libertarian LIB
NONPARTISAN, NP_CODE = "Nonpartisan office", "N"
LEFT, CW = fed.LEFT, fed.CW
NUM_END, NAME_START, NAME_END = 5, 7, 30                 # filing number in columns 0-4, the name in 7-29; nothing after is read
COUNTY_LIST = re.compile(r"\*?[A-Za-z][A-Za-z .']*(?:, \*?[A-Za-z][A-Za-z .']*)*")
NAME_OK = re.compile(r"[^\W\d_][\w .,'\"()-]*")                  # letters of any alphabet (PEÑA, ASSÉO)

SRC_GENERAL = "ok-seb-2026-general-list"
SRC_BOOK = "ok-seb-2026-candidate-list-book"
SRC_WD = "ok-seb-2026-withdrawals"
SRC_CONTESTS = "ok-seb-2026-contests"
SRC_ROSTER = "ok-openstates-roster"
SRC_COUNTIES = "ok-census-cb-2024-county"

UNOPPOSED = ("Unopposed: the only candidate for this seat once withdrawals and contests of candidacy were settled, so the seat "
             "is not on the State Election Board's November 3 list and this name is not printed on the ballot.")
RESULTS_REFUSED = ("The Board publishes who won only on its results site (results.okelections.us), which refuses scripts, so "
                   "the winner is not shown here.")


def ordinal(n):
    n = int(n)
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def squash(name):
    return fold(name).replace(" ", "")


# ---------- races: one key for both lists ----------

def race_of(kind, district=None, office_no=None, county=None, special=False):
    """{race_id, level, office_kind, office, district, seat, special, partisan, chamber, roster, ...} for a race either
    list names."""
    if kind == "SW":
        key, okind, office, roster = STATEWIDE[district]
        return {"race_id": f"2026-{STATE}-{key}", "level": "statewide", "office_kind": okind, "office": office, "district": None,
                "seat": None, "special": 0, "partisan": 1, "chamber": None, "roster": roster, "jurisdiction": NAME,
                "jurisdiction_id": FIPS}
    if kind in ("SS", "SH"):
        d = str(int(district))
        return {"race_id": f"2026-{STATE}-{kind}{d}" + ("-UNEXP" if special else ""), "level": "legislature",
                "office_kind": "state_senate" if kind == "SS" else "state_house",
                "office": "State Senator" if kind == "SS" else "State Representative", "district": d, "seat": None,
                "special": 1 if special else 0, "partisan": 1, "chamber": "Senate" if kind == "SS" else "House", "roster": None,
                "jurisdiction": NAME, "jurisdiction_id": FIPS}
    if kind == "DJ":
        d, o = str(int(district)), str(int(office_no))
        return {"race_id": f"2026-{STATE}-DC-{d}-{o}", "level": "court", "office_kind": "district_court", "office": "District Judge",
                "district": d, "seat": f"Office {o}", "special": 0, "partisan": 0, "chamber": None, "roster": None,
                "jurisdiction": f"{ordinal(d)} Judicial District", "jurisdiction_id": f"{STATE}-JD{d}"}
    if kind == "ADJ":
        return {"race_id": f"2026-{STATE}-ADJ-{county[0]}" + (f"-{office_no}" if office_no else ""), "level": "court",
                "office_kind": "district_court", "office": "Associate District Judge", "district": None,
                "seat": f"Office {office_no}" if office_no else None, "special": 0, "partisan": 0, "chamber": None, "roster": None,
                "jurisdiction": county[1], "jurisdiction_id": county[0]}
    raise ValueError(kind)


# ---------- the Candidate List Book: filing number and name columns only ----------

def name_grid(runs):
    """The first thirty character columns of one printed line of the book (filing number and name), placed by where each
    run starts. Characters at column thirty and beyond (the candidate's city) are never placed."""
    g = [" "] * NAME_END
    for x0, _y, _size, t, _x1 in runs:
        c = round((x0 - LEFT) / CW)
        if c >= NAME_END:
            continue
        for i, ch in enumerate(t):
            if c + i >= NAME_END:
                break
            if c + i >= 0:
                g[c + i] = ch
    return "".join(g)


def read_book(data, cmap):
    """([{kind, race_id, party, number, name}] for the state offices in the book's order, {race_id: race with the counties
    its heading names}). Lines are
    either a candidate (read through name_grid only), a wrapped name (the same), or a heading compared against the
    heading patterns below; a heading's text is never printed or stored unless it is an office, district or party."""
    pdf = PDF(data)
    pages = pdf.pages()
    cover = " ".join(join(rs) for _y, rs in pdf_rows(pdf, *pages[0]))
    if "Board April 1-3, 2026" not in cover or "April 3, 2026" not in cover:
        raise SystemExit("Oklahoma (state races): the Candidate List Book's cover no longer reads as the April 1-3, 2026 filings")
    out, seen, races = [], [], {}
    kind = race = party = last = None
    for n, (page, res) in enumerate(pages, start=1):
        for y, runs in pdf_rows(pdf, page, res):
            g = name_grid(runs)
            cand = bool(re.fullmatch(r"\d{5}", g[:NUM_END])) and not g[NUM_END:NAME_START].strip()
            if not cand and max(r[2] for r in runs) >= 11.5:              # an office heading, 12-point
                heading = join(runs)
                if heading in BOOK_OFFICES:
                    kind, race, party, last = BOOK_OFFICES[heading], None, None, None
                    seen.append(heading)
                    if kind == "SW":
                        race = race_of("SW", heading)
                        races[race["race_id"]] = race
                elif kind is not None:
                    raise SystemExit(f"Oklahoma (state races): an office heading on page {n} of the book this loader does not know")
                continue
            if kind is None or kind == "skip":                            # the cover, federal offices, district attorneys
                continue
            if cand:
                near = [r for r in runs if round((r[0] - LEFT) / CW) < NAME_END]
                if abs(min(r[0] for r in runs) - LEFT) > 1 or any(len(r[3]) >= 5 and abs((r[4] - r[0]) / len(r[3]) - CW) > 0.05 for r in near):
                    raise SystemExit(f"Oklahoma (state races): the book's type or margin changed on page {n}; its columns cannot be read by position")
                if race is None or (kind in ("SW", "SS", "SH") and not party):
                    raise SystemExit(f"Oklahoma (state races): a candidate on page {n} of the book comes before its district or party heading")
                if g[NAME_END - 1] != " ":
                    raise SystemExit(f"Oklahoma (state races): a name on page {n} of the book reaches the edge of its column and may run on")
                rec = {"kind": kind, "race_id": race["race_id"], "party": party if kind in ("SW", "SS", "SH") else NONPARTISAN,
                       "number": int(g[:NUM_END]), "name": g[NAME_START:NAME_END].strip()}
                last = [rec, y]
                out.append(rec)
                continue
            x0 = min(r[0] for r in runs)
            if last and not g[:NAME_START].strip() and g[NAME_START:].strip() and abs(x0 - (LEFT + NAME_START * CW)) < 1.5 \
                    and 0 < last[1] - y < 15:
                if g[NAME_END - 1] != " ":
                    raise SystemExit(f"Oklahoma (state races): a name on page {n} of the book reaches the edge of its column and may run on")
                last[0]["name"] += " " + g[NAME_START:NAME_END].strip()   # a long name, wrapped in its own column
                last[1] = y
                continue
            heading = join(runs)                                          # compared only; never printed
            last = None
            if heading.upper() in PARTIES and len(heading) < 20:
                if kind not in ("SW", "SS", "SH"):
                    raise SystemExit(f"Oklahoma (state races): a party heading under a nonpartisan office on page {n} of the book")
                party = PARTIES[heading.upper()]
                continue
            m = re.fullmatch(r"DISTRICT (\d+)( \(unexpired\))? - (.+)", heading) if kind in ("SS", "SH") else None
            if m and COUNTY_LIST.fullmatch(m.group(3)):
                race, party = race_of(kind, m.group(1), special=bool(m.group(2))), None
                race["counties"] = counties_named(m.group(3), cmap, f"{kind} {m.group(1)}")
                if race["race_id"] in races:
                    raise SystemExit(f"Oklahoma (state races): {race['race_id']} has two headings in the book")
                races[race["race_id"]] = race
                continue
            m = re.fullmatch(r"DISTRICT (\d+), OFFICE (\d+) - (.+)", heading) if kind == "DJ" else None
            if m and COUNTY_LIST.fullmatch(m.group(3)):
                race = race_of("DJ", m.group(1), m.group(2))
                race["counties"] = counties_named(m.group(3), cmap, f"district judge {m.group(1)}-{m.group(2)}")
                if race["race_id"] in races:
                    raise SystemExit(f"Oklahoma (state races): {race['race_id']} has two headings in the book")
                races[race["race_id"]] = race
                continue
            m = re.fullmatch(r"([A-Z][A-Z .']*) COUNTY(?:,? (?:- )?OFFICE (?:NO\. )?(\d+))?", heading.upper()) if kind == "ADJ" else None
            if m:
                c = cmap.get(squash(m.group(1)))
                if not c:
                    raise SystemExit(f"Oklahoma (state races): a county in the book's associate district judge headings is not in the Census file ({m.group(1)})")
                race = race_of("ADJ", county=c, office_no=m.group(2))
                race["counties"] = [c[0]]
                if race["race_id"] in races:
                    raise SystemExit(f"Oklahoma (state races): {race['race_id']} has two headings in the book")
                races[race["race_id"]] = race
                continue
            raise SystemExit(f"Oklahoma (state races): a line on page {n} of the candidate list book is not read (at {y:.0f} points)")
    for rec in out:
        rec["name"] = re.sub(r"\s+", " ", rec["name"]).strip()
        if not NAME_OK.fullmatch(rec["name"]):
            raise SystemExit(f"Oklahoma (state races): filing number {rec['number']} does not read as a name; the columns may have moved")
    missing = [h for h in STATEWIDE if h not in seen] + [h for h in ("STATE SENATOR", "STATE REPRESENTATIVE") if h not in seen]
    if missing:
        raise SystemExit(f"Oklahoma (state races): the book has no section for {missing}")
    return out, races


def counties_named(text, cmap, where):
    out = []
    for w in text.split(","):
        c = cmap.get(squash(w.replace("*", "")))
        if not c:
            raise SystemExit(f"Oklahoma (state races): a county named in the book for {where} is not in the Census file ({w.strip()})")
        out.append(c[0])
    return sorted(set(out))


def get_book(extract_dir, cmap, say):
    """The book's state-office entries: from the federal loader's cached copy, else fetched into memory (never saved)."""
    cached = os.path.join(CACHE, "ok", "ok_2026_candidate_list_book.pdf")
    extract = os.path.join(extract_dir, "sl_ok_book.json")
    data, how, fetched = None, None, None
    if os.path.exists(cached):
        data, how = open(cached, "rb").read(), "the federal loader's cached copy"
        fetched = dt.date.fromtimestamp(os.path.getmtime(cached)).isoformat()
    else:
        try:
            data, how, fetched = net.get(fed.BOOK_URL), "fetched into memory", dt.date.today().isoformat()
        except Exception as e:  # noqa: BLE001
            say(f"    Oklahoma (state races): could not fetch the Candidate List Book ({type(e).__name__})")
    if data is None:
        if not os.path.exists(extract):
            raise SystemExit("Oklahoma (state races): the Candidate List Book could not be read")
        ex = json.load(open(extract, encoding="utf-8"))
        say(f"    Oklahoma (state races): using the saved extract of the Candidate List Book ({ex['fetched']})")
        return ex["rows"], ex["races"], ex["sha256"], ex["fetched"], "the saved extract"
    if data[:5] != b"%PDF-":
        raise SystemExit(f"Oklahoma (state races): {fed.BOOK_URL} did not return a PDF")
    rows, races = read_book(data, cmap)
    sha = hashlib.sha256(data).hexdigest()
    del data
    os.makedirs(extract_dir, exist_ok=True)
    keep = [{k: r[k] for k in ("kind", "race_id", "party", "number", "name")} for r in rows]
    with open(extract, "w", encoding="utf-8") as fh:              # office, party, filing number and name only
        json.dump({"url": fed.BOOK_URL, "sha256": sha, "fetched": fetched, "rows": keep, "races": races}, fh, indent=0)
    return rows, races, sha, fetched, how


# ---------- the November list ----------

def list_office(text, cmap):
    """(kind, race) for an office heading of the November list; None for an office another loader reads (Congress,
    county offices); a SystemExit for anything else."""
    h = re.sub(r"\s+", " ", text).strip().upper()
    if h in STATEWIDE:
        return race_of("SW", h)
    m = re.fullmatch(r"STATE (SENATOR|REPRESENTATIVE) - DISTRICT (\d+)( \(UNEXPIRED TERM\))?", h)
    if m:
        return race_of("SS" if m.group(1) == "SENATOR" else "SH", m.group(2), special=bool(m.group(3)))
    m = re.fullmatch(r"DISTRICT JUDGE - DISTRICT (\d+), OFFICE (\d+)", h)
    if m:
        return race_of("DJ", m.group(1), m.group(2))
    m = re.fullmatch(r"ASSOCIATE DISTRICT JUDGE - ([A-Z .']+) COUNTY(?:,? (?:- )?OFFICE (?:NO\. )?(\d+))?", h)
    if m:
        c = cmap.get(squash(m.group(1)))
        if not c:
            raise SystemExit(f"Oklahoma (state races): a county on the November list is not in the Census file ({m.group(1)})")
        return race_of("ADJ", county=c, office_no=m.group(2))
    if fed.FEDERAL_OFFICE.search(h) or h.startswith("COUNTY "):
        return None
    raise SystemExit(f"Oklahoma (state races): an office on the November list this loader does not know ({text!r})")


def november(page, cmap):
    """({race_id: race}, {race_id: [(name, party)]}, {race_id: [county GEOIDs]}, disagreeing races, retention headings)."""
    counties = re.findall(r"<option value=\"#(\d+)\">", page)
    parts = re.split(r"<A NAME=(\d+)>([^<]*)</A>", page)
    races, listed, retention, seen = {}, {}, set(), 0
    for k in range(1, len(parts), 3):
        num, county, body = parts[k], parts[k + 1].strip(), parts[k + 2]
        if num == "00":
            continue
        seen += 1
        c = cmap.get(squash(county))
        if not c:
            raise SystemExit(f"Oklahoma (state races): a county section of the November list is not in the Census file ({county})")
        sec = race = None
        for m in re.finditer(r"<TD WIDTH=(\d+)>(.*?)</TD>", body, re.S):
            width, t = m.group(1), fed.text(m.group(2))
            if width == "990":
                sec, race = t, None
            elif width == "980":
                race = None
                if sec in ("STATE OFFICERS", "LEGISLATIVE, DISTRICT AND COUNTY OFFICERS", "JUDICIAL OFFICERS"):
                    race = list_office(t, cmap)
                    if race:
                        races.setdefault(race["race_id"], race)
                        listed.setdefault(race["race_id"], {}).setdefault(c[0], [])
                elif sec == "JUDICIAL RETENTION":
                    retention.add(t.upper())
            elif width == "970" and race:
                if race["partisan"]:
                    name, _, label = t.rpartition(",")
                    label = label.strip().upper()
                    if not name or label not in PARTIES:
                        raise SystemExit(f"Oklahoma (state races): a candidate line for {race['race_id']} in {county} County is not read")
                    entry = (re.sub(r"\s+", " ", name).strip(), PARTIES[label])
                else:
                    entry = (re.sub(r"\s+", " ", t).strip(), NONPARTISAN)
                listed[race["race_id"]][c[0]].append(entry)
    if seen != len(counties) or seen != 77:
        raise SystemExit(f"Oklahoma (state races): the November list has {seen} county sections for {len(counties)} counties (77 expected)")
    cands, where, disagree = {}, {}, []
    for rid, by_county in listed.items():
        versions = {tuple(v) for v in by_county.values()}
        if len(versions) == 1:
            cands[rid] = list(versions.pop())
            where[rid] = sorted(by_county)
        else:
            disagree.append(rid)
    return races, cands, where, disagree, retention


def get_november(extract_dir, cmap, say):
    """The November list: the federal loader's cached copy when it is under a week old, else fetched into memory."""
    cached = os.path.join(CACHE, "ok", "ok_2026_general_list.html")
    page, how = None, None
    if os.path.exists(cached) and time.time() - os.path.getmtime(cached) < 7 * 86400:
        page, how = open(cached, encoding="utf-8").read(), "the federal loader's cached copy"
        fetched = dt.date.fromtimestamp(os.path.getmtime(cached)).isoformat()
    else:
        try:
            page = net.get(fed.LIST_URL, accept="text/html").decode("utf-8", "replace")
            how, fetched = "fetched into memory", dt.date.today().isoformat()
        except Exception as e:  # noqa: BLE001
            if not os.path.exists(cached):
                raise
            say(f"    Oklahoma (state races): could not refresh the November list ({type(e).__name__}); using the cached copy")
            page, how = open(cached, encoding="utf-8").read(), "the federal loader's cached copy (not refreshed)"
            fetched = dt.date.fromtimestamp(os.path.getmtime(cached)).isoformat()
    if not re.search(r"<TITLE>\s*NOVEMBER / 2026\s+List of Elections\s*</TITLE>", page, re.I):
        raise SystemExit("Oklahoma (state races): the List of Elections is not the November 2026 list")
    sha = hashlib.sha256(page.encode("utf-8")).hexdigest()
    return november(page, cmap) + (sha, fetched, how)


# ---------- withdrawals and contests of candidacy ----------

def get_withdrawals(say):
    path = os.path.join(CACHE, "ok", "ok_2026_withdrawals.json")
    if not os.path.exists(path) or time.time() - os.path.getmtime(path) > 7 * 86400:
        try:
            wp = net.get(fed.WITHDRAWALS_URL, accept="text/html").decode("utf-8", "replace")
            return {"url": fed.WITHDRAWALS_URL, "modified": fed.modified(wp), "fetched": dt.date.today().isoformat(),
                    "rows": [dict(zip(("number", "name", "office", "date"), r)) for r in fed.table(wp, ("Number", "Name", "Office", "Date"))]}
        except Exception as e:  # noqa: BLE001
            if not os.path.exists(path):
                raise
            say(f"    Oklahoma (state races): could not refresh the withdrawals page ({type(e).__name__}); using the federal loader's extract")
    wd = json.load(open(path, encoding="utf-8"))
    wd["fetched"] = dt.date.fromtimestamp(os.path.getmtime(path)).isoformat()
    return wd


def get_contests(extract_dir, say):
    """[{cause, case, office, hearing, ruling}] from the Board's contests page (names and rulings only)."""
    path = os.path.join(extract_dir, "sl_ok_contests.json")
    if not os.path.exists(path) or time.time() - os.path.getmtime(path) > 7 * 86400:
        try:
            cp = net.get(fed.CONTESTS_URL, accept="text/html").decode("utf-8", "replace")
            rows, cur = [], None
            for r in fed.table(cp, ("Cause", "Name", "Office", "Hearing")):
                r = (r + ["", "", "", ""])[:4]
                if r[0]:
                    cur = {"cause": r[0], "case": r[1], "office": r[2], "hearing": r[3], "ruling": ""}
                    rows.append(cur)
                elif cur and r[1]:
                    cur["ruling"] = (cur["ruling"] + " " + r[1]).strip()
            os.makedirs(extract_dir, exist_ok=True)
            json.dump({"url": fed.CONTESTS_URL, "modified": fed.modified(cp), "fetched": dt.date.today().isoformat(), "rows": rows},
                      open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            time.sleep(1.0)
        except Exception as e:  # noqa: BLE001
            if not os.path.exists(path):
                raise
            say(f"    Oklahoma (state races): could not refresh the contests page ({type(e).__name__}); using the saved extract")
    return json.load(open(path, encoding="utf-8"))


def office_race(text, cmap):
    """The race a withdrawal's or contest's office names ("State Representative, District 21"); None for other offices."""
    t = re.sub(r"\s+", " ", text).strip()
    if t.upper() in STATEWIDE:
        return race_of("SW", t.upper())["race_id"]
    m = re.fullmatch(r"State (Senator|Representative),? District (\d+)( \(Unexpired(?: Term)?\))?", t, re.I)
    if m:
        return race_of("SS" if m.group(1).lower() == "senator" else "SH", m.group(2), special=bool(m.group(3)))["race_id"]
    m = re.fullmatch(r"District Judge,? District (\d+),? Office (\d+)", t, re.I)
    if m:
        return race_of("DJ", m.group(1), m.group(2))["race_id"]
    return None


# ---------- the roster and the counties ----------

def roster(path=ROSTER_DB):
    """Today's holders: {("Senate"|"House", district): row} and {roster office: row}, the roster's date, and the roster's
    own spelling of each sitting member's name. Only id, name, party, chamber, district and office are selected."""
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    seats, offices, forms = {}, {}, {}
    for r in con.execute("SELECT bioguide_id, first_name, last_name, official_full, party_name, chamber, district "
                         "FROM legislators WHERE is_current = 1"):
        key = (r[5], str(r[6]))
        if key in seats:
            raise SystemExit(f"Oklahoma (state races): the roster lists two sitting members for {key}")
        seats[key] = {"id": r[0], "first": r[1], "last": r[2], "full": r[3] or f"{r[1]} {r[2]}", "party": r[4]}
    for r in con.execute("SELECT bioguide_id, first_name, last_name, official_full, party_name, office FROM officials"):
        offices[r[5]] = {"id": r[0], "first": r[1], "last": r[2], "full": r[3] or f"{r[1]} {r[2]}", "party": r[4]}
    as_of = (con.execute("SELECT max(updated_at) FROM legislators").fetchone()[0] or "")[:10]
    con.close()
    for h in list(seats.values()) + list(offices.values()):
        for form in (h["full"], f"{h['first']} {h['last']}"):
            if form:
                forms[squash(form)] = form
    return seats, offices, as_of, forms


def counties(path=COUNTY_ZIP):
    """{squashed county name: (GEOID, "Adair County")} for Oklahoma from the Census Bureau's cartographic county file."""
    import shapefile                                   # pyshp
    z = zipfile.ZipFile(path)
    base = next(n[:-4] for n in z.namelist() if n.endswith(".dbf"))
    rdr = shapefile.Reader(dbf=io.BytesIO(z.read(base + ".dbf")))
    fields = [f[0] for f in rdr.fields[1:]]
    out = {}
    for rec in rdr.iterRecords():
        rec = dict(zip(fields, rec))
        if str(rec.get("STATEFP")) == FIPS:
            out[squash(str(rec["NAME"]))] = (str(rec["GEOID"]), str(rec["NAMELSAD"]))
    if len(out) != 77:
        raise SystemExit(f"Oklahoma (state races): the county file gives {len(out)} Oklahoma counties, not 77")
    return out


def holder_fits(name, h):
    cand = name_parts(name)
    return any(fits(cand, reg) for reg in ((fold(h["first"]).split(), fold(h["last"])), name_parts(h["full"] or "")) if reg[1])


def sha_of(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest() if os.path.exists(path) else ""


def mdate(path):
    return dt.date.fromtimestamp(os.path.getmtime(path)).isoformat() if os.path.exists(path) else ""


# ---------- the load ----------

def load(db_path, say=print, extract_dir=os.path.join(CACHE, "ok")):
    net.patient_lookups()
    cmap = counties()
    seats, offices, as_of, forms = roster()
    filers, book_races, b_sha, b_fetched, b_how = get_book(extract_dir, cmap, say)
    l_races, l_cands, l_where, disagree, retention, l_sha, l_fetched, l_how = get_november(extract_dir, cmap, say)
    wd = get_withdrawals(say)
    ct = get_contests(extract_dir, say)
    checks = []

    # who filed for each race the book lists (every legislative and statewide seat up this year; judges too)
    by_race = {}
    for f in filers:
        by_race.setdefault(f["race_id"], []).append(f)

    # withdrawals and strikes
    by_number = {f["number"]: f for f in filers}
    wd_state = []
    for w in wd["rows"]:
        rid = office_race(w["office"], cmap)
        if rid is None:
            if not fed.FEDERAL_OFFICE.search(w["office"]):
                checks.append(f"a withdrawal for an office this loader does not read ({w['office']})")
            continue
        f = by_number.get(int(w["number"]))
        if not f or f["race_id"] != rid or name_parts(w["name"])[1] not in fold(f["name"]).split():
            raise SystemExit(f"Oklahoma (state races): the withdrawal numbered {w['number']} ({w['office']}) matches no filer of that office in the book")
        f["withdrew"] = dt.datetime.strptime(w["date"], "%m/%d/%Y").strftime("%Y-%m-%d")
        wd_state.append(f)
    struck, contest_words = [], []
    for c in ct["rows"]:
        rid = office_race(c["office"], cmap)
        ruling = c["ruling"]
        respondent = c["case"].split(" v. ", 1)[1].strip() if " v. " in c["case"] else ""
        if re.search(r"stricken from (the )?ballot", ruling, re.I):
            if rid is None:
                raise SystemExit(f"Oklahoma (state races): a candidate for an office this loader does not read was stricken ({c['office']})")
            hit = [f for f in by_race.get(rid, []) if name_parts(respondent)[1] and name_parts(respondent)[1] in fold(f["name"]).split()]
            if len(hit) != 1:
                raise SystemExit(f"Oklahoma (state races): contest {c['cause']} strikes a candidate who is not one filer for {rid}")
            hit[0]["struck"] = c["hearing"] and dt.datetime.strptime(c["hearing"], "%m/%d/%Y").strftime("%Y-%m-%d") or "before the primary"
            struck.append(hit[0])
            contest_words.append(f"{c['cause']} ({rid}): stricken")
        elif re.search(r"retained on (the )?ballot|contest withdrawn|has withdrawn", ruling, re.I):
            contest_words.append(f"{c['cause']} ({rid or c['office']}): {'retained' if 'retained' in ruling.lower() else 'withdrawn'}")
        else:
            raise SystemExit(f"Oklahoma (state races): contest {c['cause']} has a ruling this loader does not read")

    def on_primary_ballot(f):
        return not (f.get("withdrew") and f["withdrew"] < PRIMARY) and not f.get("struck")

    # the November list against the book
    for rid in disagree:
        checks.append(f"{rid}: the counties' November lists disagree; left out of the November candidates")
    for rid in l_races:
        if rid not in by_race:
            raise SystemExit(f"Oklahoma (state races): {rid} is on the November list but nobody filed for it in the book")
    general, nominee = {}, {}
    for rid, cands in l_cands.items():
        rows = []
        for order, (name, party) in enumerate(cands, start=1):
            filed = [f for f in by_race[rid] if f["party"] == party]
            match = [f for f in filed if squash(f["name"]) == squash(name)] or \
                    [f for f in filed if name_parts(f["name"])[1] == name_parts(name)[1]]
            if len(match) != 1:
                raise SystemExit(f"Oklahoma (state races): a November candidate for {rid} ({party}) is not one {party} filer in the book")
            f = match[0]
            if f.get("struck") or f.get("withdrew"):
                raise SystemExit(f"Oklahoma (state races): a November candidate for {rid} withdrew or was stricken")
            if party in CODES:
                if (rid, party) in nominee:
                    raise SystemExit(f"Oklahoma (state races): two {party} candidates for {rid} on the November list")
                nominee[(rid, party)] = f["number"]
            rows.append((name, party, order, f))
        general[rid] = rows
        where_book = set(book_races[rid].get("counties") or [])
        if where_book and set(l_where.get(rid, [])) != where_book and l_races[rid]["level"] == "legislature":
            checks.append(f"{rid}: the November list carries it in {len(l_where.get(rid, []))} counties, the book names {len(where_book)}")

    # which races: every legislative and statewide seat in the book; courts only where on the November list
    race_info, skipped_courts = {}, Counter()
    for rid, fs in by_race.items():
        info = dict(book_races[rid])
        if rid in l_races and l_races[rid]["special"] != info["special"]:
            checks.append(f"{rid}: the book and the November list disagree on whether it is for the rest of a term")
        if info["level"] == "court" and rid not in l_races:
            on = [f for f in fs if on_primary_ballot(f)]
            if len(on) == 1:
                skipped_courts["one candidate (unopposed)"] += 1
            elif len(on) >= 3:
                skipped_courts["three or more filed (settled by a majority in June)"] += 1
            else:
                skipped_courts[f"{len(on)} candidates on the filings, not on the November list ({rid})"] += 1
            continue
        race_info[rid] = info

    # seat checks
    sen = sorted(int(r["district"]) for r in race_info.values() if r["office_kind"] == "state_senate" and not r["special"])
    hou = sorted(int(r["district"]) for r in race_info.values() if r["office_kind"] == "state_house" and not r["special"])
    if hou != list(range(1, 102)):
        checks.append(f"House districts in the book are not all 101 (missing {sorted(set(range(1, 102)) - set(hou))})")
    if sen != list(range(2, 49, 2)):
        checks.append(f"Senate districts in the book are {sen}, not the 24 even-numbered ones")
    specials = sorted(rid for rid, r in race_info.items() if r["special"])

    # holders and the sitting member; a race's note is its special mark, then its status, then its holder, then the rest
    holders = {}
    n_special, n_status, n_holder, n_extra = {}, {}, {}, {}
    for rid, r in race_info.items():
        h = None
        if r["chamber"]:
            h = seats.get((r["chamber"], r["district"]))
            if h is None:
                n_holder[rid] = f"The Open States roster ({as_of}) lists no sitting member for this seat."
        elif r["roster"]:
            h = offices.get(r["roster"])
        elif r["level"] == "statewide":
            n_holder[rid] = "The Open States roster this site uses does not carry this office, so today's holder is not shown."
        holders[rid] = h
        if r["special"]:
            n_special[rid] = "An election for the rest of the term (the Board's lists: unexpired term)."
    sitting = {}
    for rid, h in holders.items():
        if not h:
            continue
        names = {f["name"] for f in by_race[rid] if on_primary_ballot(f) or f.get("withdrew")} | {n for n, _p, _o, _f in general.get(rid, [])}
        fit = {squash(n) for n in names if holder_fits(n, h)}
        if len(fit) == 1:
            sitting[rid] = (fit.pop(), h["id"])

    def shown(caps):
        caps = re.sub(r"\s+", " ", caps).strip()
        if squash(caps) in forms:
            return forms[squash(caps)]
        t = re.sub(r"(['\"(])([a-z])", lambda m: m.group(1) + m.group(2).upper(), proper(caps))
        return re.sub(r"\b([A-Z])\.([a-z])\b", lambda m: m.group(1) + "." + m.group(2).upper(), t)

    def inc_of(rid, name):
        return rid in sitting and squash(name) == sitting[rid][0]

    # rows
    cand, status = [], {}
    fields = Counter()
    for rid, r in sorted(race_info.items()):
        fs = by_race[rid]
        on = [f for f in fs if on_primary_ballot(f)]
        pt = bool(r["partisan"])
        slots = len({f["party"] for f in on if f["party"] in CODES}) + len([f for f in on if f["party"] not in CODES]) if pt else len(on)
        listed = rid in general
        if listed:
            status[rid] = "november"
            for name, party, order, f in general[rid]:
                inc = inc_of(rid, name)
                cand.append((rid, "general", GENERAL, shown(name), party if pt else NONPARTISAN, party_code(party) if pt else NP_CODE, order,
                             1 if inc else 0, 0, None, None, None, sitting[rid][1] if inc else None, SRC_GENERAL, None))
            if slots < 2:
                checks.append(f"{rid}: on the November list, though the filings leave only {slots} party or candidate")
        elif len(on) == 1:
            status[rid] = "unopposed"
            f = on[0]
            inc = inc_of(rid, f["name"])
            cand.append((rid, "general", GENERAL, shown(f["name"]), f["party"] if pt else NONPARTISAN,
                         party_code(f["party"]) if pt else NP_CODE, None, 1 if inc else 0, 0, None, None, "unopposed",
                         sitting[rid][1] if inc else None, SRC_BOOK, UNOPPOSED))
            n_status[rid] = ("Not on the November 3 ballot: only one candidate remained for this seat once withdrawals and "
                             "contests of candidacy were settled.")
        elif pt and slots == 1 and len(on) >= 2:
            status[rid] = "primary"
            party = on[0]["party"]
            n_status[rid] = (f"Not on the November 3 ballot: every candidate filed as a {party}, so the party's June 16 primary (and "
                             f"the August 25 runoff, where no one had a majority) settled the seat. " + RESULTS_REFUSED)
        else:
            status[rid] = "missing"
            checks.append(f"{rid}: not on the November list, though the filings leave {slots} parties or candidates")
            n_status[rid] = "Not on the State Election Board's November 3 list; the filings do not say why."

        # primaries: a field is two or more of a party's candidates on its June 16 ballot (judges: three or more filed)
        groups = {}
        for f in on:                                    # withdrawn after the primary: still on its ballot
            if pt and f["party"] not in CODES:
                continue
            groups.setdefault(f["party"] if pt else NONPARTISAN, []).append(f)
        for party, field in groups.items():
            if len(field) < (2 if pt else 3):
                continue
            fields[r["office_kind"] if r["level"] != "statewide" else "statewide"] += 1
            key = f"primary-{CODES[party]}" if pt else "primary-NP"
            if listed and pt:
                pick = {nominee.get((rid, party))}
            elif listed:
                pick = {f["number"] for _n, _p, _o, f in general[rid]}
            else:
                pick = None
            for f in field:
                inc = inc_of(rid, f["name"])
                note = []
                if f.get("withdrew"):
                    note.append(f"Withdrew on {f['withdrew']}, after the June 16 primary.")
                if pick is None:
                    out = None
                elif f["number"] in pick:
                    out = "advanced"
                else:
                    out = "lost"
                if pt and listed and (rid, party) not in nominee:
                    note.append(f"The November list has no {party} candidate for this seat.")
                    out = None
                cand.append((rid, key, PRIMARY, shown(f["name"]), party, party_code(party) if pt else NP_CODE, None, 1 if inc else 0, 0,
                             None, None, out, sitting[rid][1] if inc else None, SRC_BOOK, " ".join(note) or None))
            if not pt and listed:
                n_extra.setdefault(rid, []).append("Three or more filed, so the June 16 ballot carried a nonpartisan primary; the two "
                                                   "on the November list went on.")

    # every party with candidates on the primary ballot of a November race has its nominee there, unless one withdrew after it
    for (rid, party) in sorted({(f["race_id"], f["party"]) for f in filers if f["party"] in CODES and on_primary_ballot(f)}):
        if status.get(rid) == "november" and (rid, party) not in nominee:
            late = [f for f in by_race[rid] if f["party"] == party and f.get("withdrew") and f["withdrew"] >= PRIMARY]
            if late:
                n_extra.setdefault(rid, []).append(
                    f"The November list has no {party} candidate: "
                    + " and ".join(f"{shown(f['name'])} ({party}) withdrew on {f['withdrew']}" for f in late) + ", after the June 16 primary.")
            else:
                checks.append(f"{rid}: {party} candidates were on the June 16 ballot but the November list has no {party} candidate")

    race_rows = []
    for rid, r in sorted(race_info.items()):
        h = holders[rid]
        cids = ",".join(r["counties"]) if r.get("counties") and r["level"] != "statewide" else None
        race_rows.append((rid, STATE, r["level"], r["office_kind"], r["office"], r["jurisdiction"], r["jurisdiction_id"], cids,
                          r["district"], r["seat"], r["special"], r["partisan"], h["id"] if h else None, h["full"] if h else None,
                          h["party"] if h else None, GENERAL,
                          " ".join([x for x in (n_special.get(rid), n_status.get(rid), n_holder.get(rid)) if x] + n_extra.get(rid, [])) or None))

    place_rows = [("county", geoid, full, None, SRC_COUNTIES) for geoid, full in sorted(cmap.values())]
    wd_before = [f for f in wd_state if f["withdrew"] < PRIMARY]
    wd_after = [f for f in wd_state if f["withdrew"] >= PRIMARY]
    n_gen = sum(1 for c in cand if c[1] == "general" and c[11] != "unopposed")
    n_state_filers = sum(1 for f in filers if f["race_id"] in race_info)

    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA)
    with con:
        con.execute("DELETE FROM sl_candidates WHERE race_id LIKE '2026-OK-%'")
        con.execute("DELETE FROM sl_races WHERE state = 'OK'")
        con.execute("DELETE FROM sl_sources WHERE state = 'OK'")
        con.execute("DELETE FROM sl_places WHERE kind = 'county' AND id GLOB '40[0-9][0-9][0-9]'")
        con.executemany("INSERT INTO sl_races VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", race_rows)
        con.executemany("INSERT INTO sl_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", cand)
        con.executemany("INSERT INTO sl_places VALUES (?,?,?,?,?)", place_rows)
        src = [
            (SRC_GENERAL, STATE, "official candidate list", "Oklahoma State Election Board",
             "NOVEMBER / 2026 List of Elections (November 3, 2026 General Election), county by county: state officers, "
             "legislative officers and judicial officers", fed.LIST_URL, "", l_fetched, l_sha, n_gen,
             f"Read for all 77 counties (from {l_how}); every county's list of each race agreed"
             + (f", except {', '.join(disagree)} (left out)" if disagree else "") + ". Names, parties and offices only. The list's "
             "order is kept as the ballot order (for partisan offices the Board's drawing: Republican, Democrat, Libertarian, then independents; for judges the list's own order). Names "
             "are printed in capitals and shown in ordinary capitals (a sitting member as the roster spells the name). The "
             f"list carries {len(retention)} judicial retention questions without the judges' names; they are not loaded."),
            (SRC_BOOK, STATE, "official candidate list", "Oklahoma State Election Board",
             "Candidates for Office 2026, filed April 1-3, 2026 (2026 Candidate List Book, compiled as of 5:00 p.m. April 3, "
             "2026): state officers, State Senator, State Representative, District Judge and Associate District Judge",
             fed.BOOK_URL, "2026-04-03", b_fetched, b_sha, n_state_filers,
             f"Read from {b_how}: the filing number and name columns only, by character position; the city column beside each "
             "name is never read. Who filed for each seat and who was on each party's June 16 primary ballot (less withdrawals "
             "and strikes). A seat with one candidate left is stored with that candidate marked unopposed; a seat only one "
             "party filed for was settled in its primary. Votes not loaded: the June 16 primary and August 25 runoff results "
             f"are published only on the Board's results site ({fed.RESULTS_URL}), which refuses scripts (403 Forbidden)."),
            (SRC_WD, STATE, "official candidate list", "Oklahoma State Election Board", "2026 Candidate Withdrawals", fed.WITHDRAWALS_URL,
             wd.get("modified", ""), wd.get("fetched", ""), "", len(wd_state),
             f"State-office withdrawals matched to the book by filing number: {len(wd_before)} before the June 16 primary (left off "
             f"its ballot), {len(wd_after)} after it (kept in the primary field, with a note). Columns kept: Number, Name, Office, Date."),
            (SRC_CONTESTS, STATE, "official candidate list", "Oklahoma State Election Board", "2026 Contests of Candidacy", fed.CONTESTS_URL,
             ct.get("modified", ""), ct.get("fetched", ""), "", len(ct["rows"]),
             "Rulings read: " + ("; ".join(contest_words) or "none") + ". A candidate stricken from the ballot is left off the primary."),
            (SRC_ROSTER, STATE, "roster", "Open States people project (CC0)",
             "Oklahoma legislators and statewide officials, as loaded into state_ok.sqlite", "https://github.com/openstates/people",
             as_of, as_of, "", len(seats) + len(offices),
             "Today's holder of each seat and office. The roster carries the Governor, Lieutenant Governor and Attorney General "
             "only among statewide offices. A candidate is marked as the sitting member only when the name fits the holder of that "
             "seat and no other candidate in the race fits."),
            (SRC_COUNTIES, STATE, "boundaries", "U.S. Census Bureau",
             "Cartographic boundary file, counties, 2024, 1:500,000 (cb_2024_us_county_500k)",
             "https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_county_500k.zip", "", mdate(COUNTY_ZIP),
             sha_of(COUNTY_ZIP), len(place_rows), "Oklahoma's 77 counties: names and GEOIDs only; a race's county_ids are the "
             "counties the book names for its district."),
        ]
        con.executemany("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", src)
    con.close()

    # the report: counts only
    grp = lambda rid: race_info[rid]["office_kind"] if race_info[rid]["level"] == "legislature" else race_info[rid]["level"]
    by = Counter(grp(rid) for rid in race_info)
    st = {k: Counter(grp(rid) for rid, s in status.items() if s == k) for k in ("november", "unopposed", "primary", "missing")}
    gen_by = Counter(grp(c[0]) for c in cand if c[1] == "general" and c[11] != "unopposed")
    inc_by = Counter(grp(rid) for rid in sitting)
    sp = Counter(race_info[rid]["office_kind"] for rid in specials)
    say(f"    Oklahoma (state races): {by['state_senate']} Senate races ({sp['state_senate']} for the rest of a term), {by['state_house']} "
        f"House races ({sp['state_house']} for the rest of a term), {by['statewide']} statewide offices, {by['court']} judges' races on the November list; on the November ballot: "
        f"Senate {st['november']['state_senate']}, House {st['november']['state_house']}, statewide {st['november']['statewide']}, "
        f"judges {st['november']['court']} ({len([c for c in cand if c[1] == 'general' and c[11] != 'unopposed'])} candidates: Senate "
        f"{gen_by['state_senate']}, House {gen_by['state_house']}, statewide {gen_by['statewide']}, judges {gen_by['court']}); "
        f"unopposed at filing: Senate {st['unopposed']['state_senate']}, House {st['unopposed']['state_house']}, statewide "
        f"{st['unopposed']['statewide']}; settled in a one-party primary: Senate {st['primary']['state_senate']}, House "
        f"{st['primary']['state_house']}, statewide {st['primary']['statewide']}; sitting member in the race: Senate "
        f"{inc_by['state_senate']}, House {inc_by['state_house']}, statewide {inc_by['statewide']}; primary fields: Senate "
        f"{fields['state_senate']}, House {fields['state_house']}, statewide {fields['statewide']}, judges {fields['district_court']}; "
        f"withdrawals {len(wd_before)} before and {len(wd_after)} after the primary, {len(struck)} stricken")
    on_ballot = sum(1 for f in filers if f["race_id"] in race_info and on_primary_ballot(f))
    off = sum(1 for f in filers if f["race_id"] in race_info and not on_primary_ballot(f))
    say(f"    Oklahoma (state races): filings reconciled: {n_state_filers} filed for the races loaded = {on_ballot} on the June 16 "
        f"ballot + {off} withdrawn before it or stricken"
        + ("" if on_ballot + off == n_state_filers else "  (DOES NOT ADD UP)"))
    if skipped_courts:
        say(f"    Oklahoma (state races): judges' seats in the book not on the November list (not loaded): "
            + ", ".join(f"{v} {k}" for k, v in sorted(skipped_courts.items())))
    for c in checks:
        say(f"    CHECK Oklahoma (state races): {c}")
    return len(cand)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: python ballot/state_local_ok.py <database file>")
    load(sys.argv[1])
