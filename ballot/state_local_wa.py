"""
ballot/state_local_wa.py - Washington's state races on the November 3, 2026 ballot: the 24 State Senate seats whose
four-year terms end this year, all 98 seats of the House of Representatives (two in each of the 49 legislative
districts, Position 1 and Position 2), and the appellate court seats on the list (five Justice of the Supreme Court
positions and eight Court of Appeals positions, all nonpartisan), with the August 4 top-two primary and its certified
votes. Washington elects its Governor and the other statewide executive officers in presidential years (2028 next),
so no statewide executive office is on the 2026 ballot; the federal rows (U.S. Representative) are left to
ballot/lists/wa.py and the federal database, which is never opened here.

Sources, all the Secretary of State's own:
  - The candidate lists on voter.votewa.gov: "GENERAL 2026 Candidate List" (election 899) and "PRIMARY 2026 Candidate
    List" (election 898), the same Telerik grids the federal loader reads, every page read through the grid's own pager
    and the rows counted against the grid's own "items" figure. Columns are found by their headings and only these
    cells are ever turned into text: District Type, District, Race, Term Type, Term Length, Name, Party Preference,
    Status, Election Status and Ballot Order. The grid also carries Mailing Address, Email, Phone and Filing Date; those
    cells are never read, printed or kept, and the pages themselves are never saved: only the kept cells of the state
    rows go to ballot_cache/wa/sl_wa_2026_<general|primary>_state.json, with each page's SHA-256 and a count (no
    names) of the other offices' rows. A Withdrawn candidate is left off and counted; any other status stops the loader.
  - The certified results of the August 4, 2026 primary: the "All Results Excel" workbook the federal loader finds
    through the results site's own election record (results.votewa.gov) and caches as
    ballot_cache/wa/wa_2026_primary_all_results.xlsx; only its State Senator, State Representative, Supreme Court and
    Court of Appeals contests are read (office, candidate, party preference, votes). Every candidate's county rows
    ("Precinct Results") must add up to the statewide total ("Summary Results").
  - The Secretary of State's results exports of the November 5, 2024 and November 8, 2022 general elections
    (results.vote.wa.gov/results/<date>/export/<date>_AllState.csv: race, candidate, party, votes, percentage and
    jurisdiction only). 2022 and 2024 together show which Senate seats were elected when (a 2022 seat's four-year term
    ends in January 2027); 2024 shows who won each House position, which the Open States roster does not record.
  - Who holds each seat today: the Open States roster in state_wa.sqlite (legislators, is_current = 1, by chamber and
    district; only ids, names, party, chamber and district are selected). The roster carries no House position and no
    judges. A House position's holder is the 2024 winner of that position when that winner still sits for the
    district; otherwise the district's one other sitting representative, when the other position's holder is known
    (Zach Hall, appointed in 2025 to the Position 1 seat Victoria Hunt won in 2024). Courts show no holder.

Washington's primary is top-two: every candidate, of every party preference, is on one primary ballot, and the two with
the most votes advance whatever their parties (a tie for second advances everyone tied); Supreme Court and Court of
Appeals races work the same way, and an office with no more than two candidates skips the primary (the primary list
marks them "Advanced to General"). So the one primary field is election "primary" (as on the federal side), shown only
where two or more candidates were on the August ballot. The party shown is the candidate's own stated preference as
the ballot and results print it, without parentheses ("Prefers Democratic Party", "States No Party Preference"); it is
not a party's nomination. party_code is D or R only for "Prefers Democratic/Democrat Party" and "Prefers Republican/GOP
Party", L and G for Libertarian and Green, I for Independent and no party preference, O for anything else (Labor
Democrat, Cascade Democrat and the like are O, not D). Nonpartisan courts are "Nonpartisan office", code N.

Controls: each list's rows = its own count; the primary field is exactly the primary list's Active candidates for the
race; everyone on the general list advanced from the primary (top two with ties); each candidate's party preference
agrees between the results and both lists; county rows add up; the Senate seats on the list are exactly the 2022 seats
and none of the 2024 ones, 49 in all; the House list has all 98 positions. Every mismatch is reported, never patched.

Privacy: only office, district, candidate name, party preference, ballot order, status and votes are read. No address,
city, ZIP code, phone, website, e-mail, filing date or treasurer is read, printed, logged, cached or stored; no photos,
ages, websites, biographies or money reach the database.

    python -m ballot.state_local_wa <path to a test database>
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
import urllib.parse
from urllib.error import HTTPError
from urllib.request import Request, urlopen

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import openpyxl  # noqa: E402

from ballot.common import CACHE, fold, name_parts  # noqa: E402
from ballot.lists import wa as W  # noqa: E402
from ballot.match import fits  # noqa: E402
from states import net  # noqa: E402

STATE = "WA"
GENERAL, PRIMARY = "2026-11-03", W.PRIMARY
ROSTER = os.path.join(HERE, "state_wa.sqlite")
LISTS = {"general": ("899", "GENERAL 2026"), "primary": ("898", "PRIMARY 2026")}
LIST_FILE = "sl_wa_2026_{}_state.json"
PAST = {"2024": ("20241105", "November 5, 2024"), "2022": ("20221108", "November 8, 2022")}
PAST_URL = "https://results.vote.wa.gov/results/{0}/export/{0}_AllState.csv"
PAST_FILE = "wa_{}_general_results_allstate.csv"
SRC_GEN, SRC_PRI, SRC_RES = "wa-sos-2026-state-general-list", "wa-sos-2026-state-primary-list", "wa-sos-2026-state-primary-results"
SRC_PAST = {"2024": "wa-sos-2024-general-results", "2022": "wa-sos-2022-general-results"}
SRC_ROSTER = "wa-openstates-roster"
SCAN_SRC = {"wa-sos-2026-certification": "wa-sos-2026-state-certification", "wa-sos-2026-primary-canvass": "wa-sos-2026-state-primary-canvass"}

# Only these cells of a grid row are ever turned into text.
KEEP = ("District Type", "District", "Race", "Term Type", "Term Length", "Name", "Party Preference", "Status", "Election Status",
        "Ballot Order")
SENATE_SEATS, DISTRICTS = 49, 49
NONPARTISAN = "Nonpartisan office"

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

TOP_TWO = ("Washington's primary is top-two: every candidate was on one August 4 ballot and the two with the most votes advanced, "
           "whatever their parties. The party shown is the candidate's own stated preference as the ballot prints it, not a party's "
           "nomination.")
SENATE_NOTE = ("Washington senators serve four-year terms, and about half the Senate is elected every two years. This district's "
               "seat was elected for a four-year term in November 2022 (the Secretary of State's results), a term that ends in January 2027.")
HOUSE_NOTE = ("Each legislative district elects two representatives, Position 1 and Position 2, both for two-year terms, so every "
              "House seat is on the ballot every even year.")
SHORT_FULL = ("The Secretary of State's list gives this race as \"Short & Full\": the winner also serves the rest of the present "
              "term, not only the full two-year term that begins in January 2027.")
COURT_NOTE = ("A nonpartisan office: no party is printed on the ballot. The Open States roster does not carry judges, so no holder "
              "is shown.")
SKIPPED_PRIMARY = ("With no more than two candidates filed, this office was not on the August primary ballot; the primary list marks "
                   "its candidates \"Advanced to General\".")
COURT_TOP_TWO = "The two with the most votes in the August 4 primary advanced."
ORDER_NOTE = "Ballot order as the Secretary of State's general election list gives it."


# ------------------------------------------------------------------------------------------------ fetching and caching

def fresh(path, days):
    return os.path.exists(path) and time.time() - os.path.getmtime(path) < days * 86400


def ask(req, say):
    """One request, asked at most twice more on a refusal or a server error (never past a challenge page)."""
    for attempt in range(3):
        try:
            if isinstance(req, str):
                return net.get(req, accept="text/html")
            with urlopen(req, timeout=120) as r:
                return r.read()
        except HTTPError as e:
            if e.code not in (403, 429, 500, 502, 503, 504) or attempt == 2:
                raise
            say(f"      voter.votewa.gov: HTTP {e.code}; asking again in {10 * (attempt + 1)} s")
            time.sleep(10 * (attempt + 1))


def text(cell):
    return W.text(cell)


def grid_rows(page):
    """The kept cells of every row of one page of the grid, found by the headings; no other cell is turned into text."""
    heads = [text(h) for h in re.findall(r'<th[^>]*class="rgHeader[^"]*"[^>]*>(.*?)</th>', page, re.S)]
    if not all(k in heads for k in KEEP) or len(set(heads)) != len(heads):
        raise SystemExit(f"Washington: the candidate grid's columns changed ({[h for h in heads if h in KEEP]})")
    idx = {heads.index(k): k for k in KEEP}
    for tr in re.findall(r'<tr class="(?:rgRow|rgAltRow)"[^>]*>(.*?)</tr>', page, re.S):
        row, n = {}, 0
        for n, m in enumerate(re.finditer(r"<td[^>]*>(.*?)</td>", tr, re.S), start=1):
            if n - 1 in idx:
                row[idx[n - 1]] = text(m.group(1))
        if n != len(heads):
            raise SystemExit("Washington: a grid row does not line up with the grid's headings")
        yield row


def state_row(r):
    """True for a row this loader keeps: the Legislature, the Supreme Court and the Court of Appeals."""
    t = r["District Type"].strip().upper()
    if t == "LEGISLATIVE":
        return True
    if t == "JUDICIAL":
        d = r["District"].strip().lower()
        return d == "supreme court" or d.startswith("court of appeals")
    return False


def read_list(kind, folder, say, max_age_days=2):
    """The kept cells of the state rows of one list, every page read; cached (kept cells only) for two days."""
    path = os.path.join(folder, LIST_FILE.format(kind))
    if fresh(path, max_age_days):
        return path, json.load(open(path, encoding="utf-8"))
    eid, title = LISTS[kind]
    url = W.LIST_URL + eid
    try:
        raw = ask(url, say)
    except (HTTPError, OSError) as e:
        if os.path.exists(path):
            say(f"      the {title} list could not be read ({e}); using the copy read earlier")
            return path, json.load(open(path, encoding="utf-8"))
        raise
    page = raw.decode("utf-8", "replace")
    hashes = [hashlib.sha256(raw).hexdigest()]
    if not re.search(rf"<title>\s*{title} Candidate List\s*</title>", page):
        raise SystemExit(f"Washington: {url} is no longer the {title} Candidate List (a challenge page? nothing is read)")
    m = re.search(r"<strong>(\d+)</strong>\s*items in\s*<strong>(\d+)</strong>", page)
    if not m:
        raise SystemExit(f"Washington: the {title} list no longer shows its row count")
    items, pages = int(m.group(1)), int(m.group(2))
    rows = list(grid_rows(page))
    for n in range(2, pages + 1):
        nxt = re.search(r'<input type="(submit|button)" name="([^"]+)" value=" " (?:onclick="javascript:__doPostBack\(&#39;([^&]+)&#39;,'
                        r'&#39;&#39;\)" )?title="Next Page" class="rgPageNext" />', page)
        if not nxt:
            raise SystemExit(f"Washington: page {n - 1} of the {title} list has no Next Page button")
        fields = W.form(page)
        if nxt.group(1) == "submit":
            fields.update({"__EVENTTARGET": "", "__EVENTARGUMENT": "", nxt.group(2): " "})
        elif nxt.group(3):
            fields.update({"__EVENTTARGET": nxt.group(3), "__EVENTARGUMENT": ""})
        else:
            raise SystemExit(f"Washington: page {n - 1} of the {title} list has a Next Page button that is not read")
        time.sleep(2)
        req = Request(url, data=urllib.parse.urlencode(fields).encode(), method="POST",
                      headers={"User-Agent": net.UA, "Content-Type": "application/x-www-form-urlencoded", "Referer": url})
        raw = ask(req, say)
        page = raw.decode("utf-8", "replace")
        hashes.append(hashlib.sha256(raw).hexdigest())
        cur = re.search(r'class="rgCurrentPage"[^>]*><span>(\d+)</span>', page)
        if not cur or int(cur.group(1)) != n:
            raise SystemExit(f"Washington: asked for page {n} of the {title} list and got {cur.group(1) if cur else 'no page'}")
        rows += list(grid_rows(page))
    if len(rows) != items:
        raise SystemExit(f"Washington: the {title} list counts {items} rows; {len(rows)} were read")
    kept = [r for r in rows if state_row(r)]
    other = collections.Counter(r["District Type"].strip().upper() for r in rows if not state_row(r))
    keep = {"title": title, "url": url, "read": dt.date.today().isoformat(), "items": items, "pages": pages, "page_sha256": hashes,
            "rows": kept, "other": dict(sorted(other.items()))}
    os.makedirs(folder, exist_ok=True)
    json.dump(keep, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    say(f"      {title} Candidate List: {items} rows on {pages} pages, {len(kept)} for the Legislature and the appellate courts")
    return path, keep


def past_results(year, folder, say):
    """[(race, candidate, votes)] for the Legislature from one past general election's statewide export (race, candidate,
    party, votes, percentage and jurisdiction are all the file has)."""
    date, _words = PAST[year]
    path = os.path.join(folder, PAST_FILE.format(year))
    net.download(PAST_URL.format(date), path, max_age_days=365, say=say)
    raw = open(path, "rb").read()
    if raw.lstrip()[:1] == b"<":
        raise SystemExit(f"Washington: {os.path.basename(path)} is a web page, not the results export; delete it and run again")
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    if not {"Race", "Candidate", "Votes"} <= set(reader.fieldnames or []):
        raise SystemExit(f"Washington: the {year} results export's columns changed ({reader.fieldnames})")
    out = []
    for r in reader:
        race = r["Race"].strip()
        if re.search(r"legislative district", race, re.I):
            out.append((race, r["Candidate"].strip(), int(r["Votes"] or 0)))
    return path, out


# ---------------------------------------------------------------------------------------------------------- the races

def race_of(r):
    """(race_id, level, office_kind, office, jurisdiction, jurisdiction_id, district, seat, partisan) for a kept list row."""
    d, race = r["District"].strip(), r["Race"].strip()
    if r["District Type"].strip().upper() == "LEGISLATIVE":
        m = re.fullmatch(r"legislative district (\d+)", d, re.I)
        if not m or not 1 <= int(m.group(1)) <= DISTRICTS:
            raise SystemExit(f"Washington: a legislative row names a district that is not read ({d!r})")
        n = str(int(m.group(1)))
        if race == "State Senator":
            return (f"2026-{STATE}-SS{n}", "legislature", "state_senate", "State Senator", f"Legislative District {n}", n, n, None, 1)
        p = re.fullmatch(r"State Representative Pos\. ([12])", race)
        if not p:
            raise SystemExit(f"Washington: a legislative race that is not read ({race!r}, {d})")
        return (f"2026-{STATE}-SH{n}-{p.group(1)}", "legislature", "state_house", "State Representative", f"Legislative District {n}", n, n,
                f"Position {p.group(1)}", 1)
    if d.lower() == "supreme court":
        p = re.fullmatch(r"Justice Position #?0*(\d+)", race)
        if not p:
            raise SystemExit(f"Washington: a Supreme Court race that is not read ({race!r})")
        return (f"2026-{STATE}-SC{p.group(1)}", "court", "supreme_court", "Justice of the Supreme Court", "Washington", STATE, None,
                f"Position {p.group(1)}", 0)
    m = re.fullmatch(r"court of appeals, division (\d), district (\d)", d, re.I)
    p = re.fullmatch(r"Judge Position (\d+)", race)
    if not m or not p:
        raise SystemExit(f"Washington: a Court of Appeals race that is not read ({d!r}, {race!r})")
    div, dist, pos = m.group(1), m.group(2), p.group(1)
    return (f"2026-{STATE}-COA{div}-{dist}-{pos}", "court", "court_of_appeals", "Judge of the Court of Appeals",
            f"Court of Appeals, Division {div}, District {dist}", f"COA{div}-{dist}", f"Division {div}, District {dist}", f"Position {pos}", 0)


OFFICE_RE = [
    (re.compile(r"State Senator - Legislative District (\d+)"), lambda m: f"2026-{STATE}-SS{int(m.group(1))}"),
    (re.compile(r"State Representative Pos\. ([12]) - Legislative District (\d+)"), lambda m: f"2026-{STATE}-SH{int(m.group(2))}-{m.group(1)}"),
    (re.compile(r"Justice Position #?0*(\d+) - Supreme Court"), lambda m: f"2026-{STATE}-SC{m.group(1)}"),
    (re.compile(r"Judge Position (\d+) - Court of Appeals,? Division (\d),? District (\d)", re.I),
     lambda m: f"2026-{STATE}-COA{m.group(2)}-{m.group(3)}-{m.group(1)}"),
]
BOOK_KEEP = ("Office Name", "Ballot Name", "Party", "Total")
NOT_CANDIDATES = ("ballots cast", "over votes", "under votes")


def book_race(office):
    office = re.sub(r"\s+", " ", str(office or "")).strip()
    for rx, rid in OFFICE_RE:
        m = rx.fullmatch(office)
        if m:
            return rid(m)
    if re.search(r"state senator|state representative|supreme court|court of appeals", office, re.I):
        raise SystemExit(f"Washington: a state office in the primary results that is not read ({office!r})")
    return None


def book_rows(wb, name, keep):
    it = wb[name].iter_rows(values_only=True)
    heads = [str(c or "").strip() for c in next(it)]
    if not all(k in heads for k in keep):
        raise SystemExit(f"Washington: the {name} sheet's columns changed ({[h for h in heads if h]})")
    idx = {k: heads.index(k) for k in keep}
    for r in it:
        rid = book_race(r[idx["Office Name"]])
        if rid:
            yield rid, {k: r[i] for k, i in idx.items()}


def primary_results(book):
    """{race: {"cands": [(name, party, votes)], "write_in": votes}} for the state offices, every figure checked against the
    sum of its county rows. Returns (results, counties, problems)."""
    wb = openpyxl.load_workbook(book, read_only=True, data_only=True)
    out, state = {}, collections.Counter()
    for rid, r in book_rows(wb, "Summary Results", BOOK_KEEP):
        name = re.sub(r"\s+", " ", str(r["Ballot Name"] or "")).strip()
        f = out.setdefault(rid, {"cands": [], "write_in": 0})
        v = int(r["Total"] or 0)
        if name.lower() in NOT_CANDIDATES:
            continue
        if re.match(r"write[- ]in", name, re.I):
            f["write_in"] += v
            state[(rid, "write-in")] += v
            continue
        party = re.sub(r"\s+", " ", str(r["Party"] or "")).strip()
        f["cands"].append((name, party, v))
        state[(rid, fold(name))] += v
    counties, byc = set(), collections.Counter()
    for rid, r in book_rows(wb, "Precinct Results", ("Precinct",) + BOOK_KEEP):
        name = re.sub(r"\s+", " ", str(r["Ballot Name"] or "")).strip()
        if name.lower() in NOT_CANDIDATES:
            continue
        key = "write-in" if re.match(r"write[- ]in", name, re.I) else fold(name)
        byc[(rid, key)] += int(r["Total"] or 0)
        counties.add(str(r["Precinct"]).strip())
    wb.close()
    problems = [f"{k[0]} {k[1]}: county rows add to {byc[k]:,}, the statewide sheet says {state[k]:,}"
                for k in sorted(set(byc) | set(state)) if byc[k] != state[k]]
    return out, len(counties), problems


# ---------------------------------------------------------------------------------------------------------- parties

def shown(party):
    """'(Prefers Democratic Party)' -> 'Prefers Democratic Party', as the ballot prints it without the parentheses."""
    return re.sub(r"\s+", " ", (party or "").strip().strip("()")).strip()


def code(party):
    p = shown(party).lower()
    m = re.fullmatch(r"prefers (.+?) party", p)
    word = m.group(1) if m else p
    if word in ("democratic", "democrat"):
        return "D"
    if word in ("republican", "gop"):
        return "R"
    if word == "libertarian":
        return "L"
    if word == "green":
        return "G"
    if word in ("independent", "states no party preference", "no party preference"):
        return "I"
    return "O"


def same_pref(party, listed):
    """The results' preference and a list's short form agree: (Prefers StandUp America Party) and STANDUP-AMERICA, letters
    only."""
    return re.sub(r"[^A-Z]", "", W.short(party)) == re.sub(r"[^A-Z]", "", (listed or "").upper())


# ---------------------------------------------------------------------------------------------------------- the roster

def roster(path):
    """Sitting legislators: ids, names, party, chamber and district only (the roster's contact columns are never selected)."""
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    legs = [dict(zip(("id", "first", "last", "full", "other", "party", "chamber", "district"), r)) for r in con.execute(
        "SELECT bioguide_id, first_name, last_name, official_full, other_names, party_name, chamber, district "
        "FROM legislators WHERE is_current = 1")]
    con.close()
    for p in legs:
        p["district"] = str(int(p["district"])) if str(p["district"] or "").isdigit() else str(p["district"] or "")
    return legs


def person_fits(name, p):
    """A listed name fits a roster person: same family name and a given name that fits (the roster's first name or any
    other form of the name it keeps)."""
    readings = [name_parts(name), name_parts(re.sub(r'"[^"]*"|\([^)]*\)', " ", name))]
    forms = [(fold(p["first"] or "").split(), " ".join(fold(p["last"] or "").split()))]
    forms += [name_parts(o.strip()) for o in (p.get("other") or "").split(";") if o.strip() and "," not in o and "." not in o]
    return any(f[1] and r[1] and fits(r, f) for r in readings for f in forms)


def party_letter(roster_party):
    t = (roster_party or "").lower()
    return "D" if t.startswith("democrat") else "R" if t.startswith("republican") else "O"


# ------------------------------------------------------------------------------------------------------------ loading

def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def mtime(path):
    return dt.datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d")


def load(db_path, say=print, cache=CACHE, roster_db=ROSTER):
    net.patient_lookups()
    folder = os.path.join(cache, "wa")
    os.makedirs(folder, exist_ok=True)
    report = []

    gpath, gen = read_list("general", folder, say)
    ppath, pri = read_list("primary", folder, say)
    book, info = W.results_book(folder)
    results, counties, unreconciled = primary_results(book)
    past = {y: past_results(y, folder, say) for y in PAST}
    legs = roster(roster_db)

    # ---- the races and the November ballot, from the general list
    races, listed, gone = {}, collections.defaultdict(list), []
    for r in gen["rows"]:
        rid, level, okind, office, juris, jid, district, seat, partisan = race_of(r)
        if r["Status"] == "Withdrawn":
            gone.append((rid, r["Name"]))
            continue
        if r["Status"] != "Active":
            raise SystemExit(f"Washington: a status on the general list that is not read ({r['Status']!r}, {rid})")
        if not r["Ballot Order"].isdigit():
            raise SystemExit(f"Washington: no ballot order on the general list for {r['Name']} ({rid})")
        term = r["Term Type"].strip()
        if term not in ("Regular", "Short & Full", "Unexpired"):
            raise SystemExit(f"Washington: a term type on the general list that is not read ({term!r}, {rid})")
        if rid not in races:
            races[rid] = dict(race_id=rid, state=STATE, level=level, office_kind=okind, office=office, jurisdiction=juris,
                              jurisdiction_id=jid, county_ids=None, district=district, seat=seat, special=int(term == "Unexpired"),
                              partisan=partisan, holder_id=None, holder_name=None, holder_party=None, election_date=GENERAL, note=None,
                              _term=term, _length=r["Term Length"].strip())
        elif (races[rid]["_term"], races[rid]["_length"]) != (term, r["Term Length"].strip()):
            raise SystemExit(f"Washington: two term types for {rid} on the general list")
        listed[rid].append(r)

    # ---- the primary list: who was on the August ballot, and who withdrew before it
    filed, withdrew, skipped = collections.defaultdict(dict), [], collections.defaultdict(list)
    for r in pri["rows"]:
        rid = race_of(r)[0]
        if r["Status"] == "Withdrawn":
            withdrew.append(f"{r['Name']} ({rid})")
        elif r["Status"] == "Active":
            if fold(r["Name"]) in filed[rid]:
                raise SystemExit(f"Washington: {r['Name']} is on the primary list twice for {rid}")
            filed[rid][fold(r["Name"])] = r
            if r["Election Status"] == "Advanced to General":
                skipped[rid].append(r)
            elif r["Election Status"] != "In Primary":
                raise SystemExit(f"Washington: an election status on the primary list that is not read ({r['Election Status']!r}, {rid})")
        else:
            raise SystemExit(f"Washington: a status on the primary list that is not read ({r['Status']!r}, {rid})")

    # ---- which seats: the Senate seats elected in 2022, all 98 House positions
    senate_won = {y: {int(re.search(r"district (\d+)", race, re.I).group(1)) for race, _c, _v in rows_
                      if re.fullmatch(r"legislative district \d+ - state senator", race, re.I)} for y, (_p, rows_) in past.items()}
    sen = sorted(int(x["district"]) for x in races.values() if x["office_kind"] == "state_senate")
    if set(sen) != senate_won["2022"] - senate_won["2024"]:
        report.append(f"the Senate seats on the list {sen} are not the seats elected in 2022 and not again in 2024 "
                      f"{sorted(senate_won['2022'] - senate_won['2024'])}")
    if set(sen) & senate_won["2024"]:
        report.append(f"Senate seats on the list that were elected for four years in 2024: {sorted(set(sen) & senate_won['2024'])}")
    if len(senate_won["2024"] | set(sen)) != SENATE_SEATS:
        report.append(f"the 2024 Senate seats and the 2026 list's cover {len(senate_won['2024'] | set(sen))} of {SENATE_SEATS} districts")
    for x in races.values():
        if x["office_kind"] == "state_senate" and x["_term"] != "Regular":
            report.append(f"{x['race_id']}: the Senate race is a {x['_term']} term")
    house = {(int(x["district"]), x["seat"]) for x in races.values() if x["office_kind"] == "state_house"}
    want = {(d, f"Position {p}") for d in range(1, DISTRICTS + 1) for p in (1, 2)}
    if house != want:
        report.append(f"House positions with no candidate on the general list: {sorted(want - house)}")
    for rid in set(filed) - set(races):
        report.append(f"{rid}: on the primary list, but nobody for it on the general list")

    # ---- who holds each seat today
    past_won = {}
    for race, cand, votes in past["2024"][1]:
        m = re.fullmatch(r"legislative district (\d+) - state representative pos\. ([12])", race, re.I)
        if m:
            key = (m.group(1), f"Position {m.group(2)}")
            past_won.setdefault(key, []).append((votes, cand))
    holder, how = {}, {}
    for d in range(1, DISTRICTS + 1):
        d = str(d)
        sitting = [p for p in legs if p["chamber"] == "House" and p["district"] == d]
        if len(sitting) != 2:
            report.append(f"the roster shows {len(sitting)} sitting representatives for District {d}")
        for pos in ("Position 1", "Position 2"):
            ranked = sorted(past_won.get((d, pos), []), reverse=True)
            if not ranked:
                report.append(f"no 2024 result for District {d} {pos}")
                continue
            won = ranked[0][1]
            fit = [p for p in sitting if person_fits(won, p)]
            if len(fit) == 1:
                holder[(d, pos)], how[(d, pos)] = fit[0], ("won", won)
        for pos, other in (("Position 1", "Position 2"), ("Position 2", "Position 1")):
            if (d, pos) not in holder and (d, other) in holder:
                rest = [p for p in sitting if p["id"] != holder[(d, other)]["id"]]
                if len(rest) == 1:
                    won = sorted(past_won.get((d, pos), []), reverse=True)
                    holder[(d, pos)], how[(d, pos)] = rest[0], ("rest", won[0][1] if won else None, holder[(d, other)]["full"])
        for pos in ("Position 1", "Position 2"):
            if (d, pos) not in holder:
                report.append(f"District {d} {pos}: which sitting representative holds it could not be told from the record")

    for rid, x in races.items():
        notes = []
        h = None
        if x["office_kind"] == "state_senate":
            hs = [p for p in legs if p["chamber"] == "Senate" and p["district"] == x["district"]]
            h = hs[0] if len(hs) == 1 else None
            if h is None:
                report.append(f"{rid}: {len(hs)} sitting senators in the roster for this district")
            notes += [SENATE_NOTE]
        elif x["office_kind"] == "state_house":
            key = (x["district"], x["seat"])
            h = holder.get(key)
            notes.append(HOUSE_NOTE)
            if h is not None and how[key][0] == "won":
                notes.append(f"Who holds this position today: {h['full']}, who won it in November 2024 (the Secretary of State's "
                             "results) and still serves, by the Open States roster.")
            elif h is not None:
                _k, won, other = how[key]
                notes.append(f"Who holds this position today: {h['full']}. The roster does not say which position a representative "
                             f"holds; {other} won the district's other position in November 2024 and still serves, and "
                             f"{h['full']} is the district's other sitting representative"
                             + (f" ({won} won this position in 2024 and no longer sits for the district)." if won else "."))
            else:
                notes.append("Which of the district's sitting representatives holds this position could not be told from the record, "
                             "so no holder is shown.")
            if x["_term"] == "Short & Full":
                notes.append(SHORT_FULL)
        else:
            notes.append(COURT_NOTE)
            if x["office_kind"] == "supreme_court":
                notes.append("Justices of the Supreme Court serve six-year terms and are elected statewide.")
            else:
                notes.append("Judges of the Court of Appeals serve six-year terms and are elected by district within their division.")
            if x["_term"] == "Unexpired":
                notes.append(f"This election is for the rest of a term: the Secretary of State's list gives it as Unexpired, "
                             f"{x['_length']} years.")
            elif x["_term"] == "Short & Full":
                notes.append("The Secretary of State's list gives this race as \"Short & Full\": the winner also serves the rest of "
                             "the present term.")
        if x["partisan"]:
            notes.append(TOP_TWO)
        elif rid in results:
            notes.append(COURT_TOP_TWO)
        elif rid in skipped:
            notes.append(SKIPPED_PRIMARY)
        notes.append(ORDER_NOTE)
        if h is not None:
            x.update(holder_id=h["id"], holder_name=h["full"], holder_party=h["party"])
        x["note"] = " ".join(notes)
        x["_holder"] = h
        x["_chamber"] = {"state_senate": "Senate", "state_house": "House"}.get(x["office_kind"])

    def where(p):
        pos = next((k[1] for k, v in holder.items() if v["id"] == p["id"]), None)
        return f"Washington {'Senate' if p['chamber'] == 'Senate' else 'House'}, District {p['district']}" + (f", {pos}" if pos else "")

    def identify(race, name, pcode):
        """(incumbent, state_member_id, note): the seat's sitting member when the name fits; else a sitting legislator of a
        compatible party anywhere when the name fits exactly one."""
        h = race["_holder"]
        if h is not None and person_fits(name, h):
            return 1, h["id"], None
        if not race["_chamber"]:
            return 0, None, None
        pool = [p for p in legs if person_fits(name, p) and (pcode not in ("D", "R") or party_letter(p["party"]) in (pcode, "O"))]
        if len(pool) == 1 and not (h is not None and pool[0]["id"] == h["id"]):
            return 0, pool[0]["id"], f"Serves today in the {where(pool[0])}."
        return 0, None, None

    # ---- controls between the lists and the results, and the rows
    cands, fields, singles, upsets, off_list, wrote_in = [], 0, 0, [], [], []
    for rid in sorted(races):
        race = races[rid]
        on_list = {fold(r["Name"]): r for r in listed[rid]}
        printed = {}
        if rid in results:
            field, write_in = results[rid]["cands"], results[rid]["write_in"]
            names = {fold(n) for n, _p, _v in field}
            if names != set(filed[rid]):
                report.append(f"{rid}: the results' candidates are not the primary list's Active candidates "
                              f"(results only: {sorted(names - set(filed[rid]))}; list only: {sorted(set(filed[rid]) - names)})")
            for n, p, _v in field:
                if race["partisan"]:
                    if not p:
                        report.append(f"{rid}: {n} has no party preference in the results")
                    elif fold(n) in filed[rid] and not same_pref(p, filed[rid][fold(n)]["Party Preference"]):
                        report.append(f"{rid}: {n}'s party preference differs between the results ({p}) and the primary list "
                                      f"({filed[rid][fold(n)]['Party Preference']})")
                elif p:
                    report.append(f"{rid}: a nonpartisan candidate, {n}, has a party in the results ({p})")
                printed[fold(n)] = shown(p)
            ranked = sorted(field, key=lambda c: (-c[2], c[0]))
            second = ranked[1][2] if len(ranked) > 1 else ranked[0][2]
            went = {fold(n) for n, _p, v in ranked if v >= second}
            if set(on_list) - went - (set(on_list) - set(filed[rid])):
                upsets.append(f"{rid}: {sorted(set(on_list) - went - (set(on_list) - set(filed[rid])))}")
            for n in sorted(went - set(on_list)):
                off_list.append(f"{rid}: {n}")
            total = sum(v for _n, _p, v in field) + write_in
            if len(field) >= 2:
                fields += 1
                for name, party, v in ranked:
                    pcode = code(party) if race["partisan"] else "N"
                    inc, mid, n2 = identify(race, name, pcode)
                    note = [n2] if n2 else []
                    if fold(name) in went and fold(name) not in on_list:
                        note.append("Advanced from the top-two primary, but is not on the Secretary of State's list for the November ballot.")
                    lr = filed[rid].get(fold(name))
                    order = int(lr["Ballot Order"]) if lr and lr["Ballot Order"].isdigit() else None
                    cands.append([rid, "primary", PRIMARY, name, shown(party) if race["partisan"] else NONPARTISAN, pcode, order, inc, 0,
                                  v, round(100 * v / total, 1) if total else None, "advanced" if fold(name) in went else "lost", mid,
                                  SRC_RES, " ".join(note) or None])
            else:
                singles += 1
        else:
            if race["partisan"]:
                report.append(f"{rid}: a partisan race with no primary results")
            elif set(on_list) != {fold(r["Name"]) for r in skipped.get(rid, [])}:
                report.append(f"{rid}: not in the primary results, and the general list is not the primary list's 'Advanced to General' names")
        for r in sorted(listed[rid], key=lambda r: int(r["Ballot Order"])):
            extra = None
            if race["partisan"]:
                party = printed.get(fold(r["Name"]))
                if not party and rid in results and fold(r["Name"]) not in filed[rid]:
                    # not printed on the August ballot and named on the November list: a write-in who advanced; the results
                    # count write-ins together, so no votes of this candidate's own are stored
                    party = r["Party Preference"].strip().capitalize()
                    pcode = "I" if party.lower() in ("states no party preference", "no party preference") else "O"
                    extra = (f"Was not printed on the August primary ballot; the Secretary of State's general list names this candidate "
                             f"for the November ballot, with the party preference written \"{r['Party Preference'].strip()}\" (shown here "
                             f"in ordinary capitals). The certified primary results count write-in votes together, not by name "
                             f"({results[rid]['write_in']:,} in this race).")
                    wrote_in.append(f"{rid}: {r['Name']}")
                elif not party:
                    report.append(f"{rid}: {r['Name']} is on the general list but not in the primary results; the list's own words are shown")
                    party = r["Party Preference"].strip().capitalize()
                    pcode = "O"
                else:
                    if not same_pref(party, r["Party Preference"]):
                        report.append(f"{rid}: {r['Name']}'s party preference differs between the general list ({r['Party Preference']}) "
                                      f"and the results ({party})")
                    pcode = code(party)
            else:
                if r["Party Preference"]:
                    report.append(f"{rid}: a nonpartisan candidate, {r['Name']}, has a party on the general list")
                party, pcode = NONPARTISAN, "N"
            inc, mid, n2 = identify(race, r["Name"], pcode)
            cands.append([rid, "general", GENERAL, r["Name"], party, pcode, int(r["Ballot Order"]), inc, 0, None, None, None, mid, SRC_GEN,
                          " ".join(x for x in (extra, n2) if x) or None])
        orders = sorted(int(r["Ballot Order"]) for r in listed[rid])
        if orders != list(range(1, len(orders) + 1)):
            report.append(f"{rid}: the general list's ballot order is {orders}")

    for rid in sorted(set(results) - set(races)):
        report.append(f"{rid}: in the primary results, but nobody for it on the general list")
    report += [f"primary results do not add up: {u}" for u in unreconciled]
    report += [f"on the general list without being in the primary's top two: {u}" for u in upsets]
    report += [f"in the primary's top two but not on the general list: {u}" for u in off_list]
    report += [f"on the general list after a write-in run in the primary (not a printed candidate; no votes of their own stored): {u}"
               for u in wrote_in]

    # House incumbents who filed for the other position, or elsewhere
    for rid in sorted(races):
        race = races[rid]
        if race["office_kind"] != "state_house":
            continue
        for r in listed[rid]:
            for (d, pos), p in holder.items():
                if d == race["district"] and pos != race["seat"] and person_fits(r["Name"], p):
                    report.append(f"{rid}: {r['Name']} fits {p['full']}, who holds District {d} {pos} by the record read here")

    seen = set()
    for c in cands:
        k = (c[0], c[1], c[3])
        if k in seen:
            raise SystemExit(f"Washington: {c[3]} is listed twice in {c[0]} {c[1]}")
        seen.add(k)

    # ---- write: Washington's rows only, in one transaction
    cols = ["race_id", "state", "level", "office_kind", "office", "jurisdiction", "jurisdiction_id", "county_ids", "district", "seat",
            "special", "partisan", "holder_id", "holder_name", "holder_party", "election_date", "note"]
    race_rows = [tuple(races[r][c] for c in cols) for r in sorted(races)]
    other = lambda keep: ", ".join(f"{k.title()} {v}" for k, v in keep["other"].items())
    list_sha = lambda keep: hashlib.sha256("".join(keep["page_sha256"]).encode()).hexdigest()
    src = [
        (SRC_GEN, STATE, "official candidate list", "Washington Secretary of State",
         "GENERAL 2026 Candidate List (November 3, 2026): State Senator, State Representative, Supreme Court and Court of Appeals",
         gen["url"], "", gen["read"], list_sha(gen), len(gen["rows"]),
         f"Every page of the grid read through its own pager ({gen['items']} rows on {gen['pages']} pages, every office; the count "
         "matched). Only District Type, District, Race, Term Type, Term Length, Name, Party Preference, Status, Election Status and Ballot "
         "Order were read; mailing addresses, e-mail, phones and filing dates were never read and the pages were not kept. Ballot order "
         f"as the list gives it. Withdrawn, left off: {len(gone)}. The sha256 here is of the pages' own hashes joined. Other offices on "
         f"the list, counted only (local offices and the federal rows): {other(gen)}."),
        (SRC_PRI, STATE, "official candidate list", "Washington Secretary of State",
         "PRIMARY 2026 Candidate List (August 4, 2026): State Senator, State Representative, Supreme Court and Court of Appeals",
         pri["url"], "", pri["read"], list_sha(pri), len(pri["rows"]),
         f"Read the same way ({pri['items']} rows on {pri['pages']} pages). Used to check the primary results (every Active candidate, "
         "each one's party preference) and for the August ballot order. Withdrawn before the primary, not on its ballot: "
         f"{'; '.join(withdrew) or 'none'}. Other offices, counted only: {other(pri)}."),
        (SRC_RES, STATE, "official results", "Washington Secretary of State",
         "2026 Primary (August 4, 2026): All Results Excel, certified results: State Senator, State Representative and Supreme Court",
         info["url"], (info.get("asOf") or "")[:10], mtime(book), sha(book), sum(len(f["cands"]) for f in results.values()),
         f"Found through the results site's own record of the election ({W.API}), which marks these results official. Top-two primary: "
         "each field's total is its candidates' votes plus write-ins (over- and under-votes left out). A field is shown only where two "
         f"or more candidates were on the ballot ({fields} fields; {singles} races had one candidate). "
         + (f"Every figure checked against the sum of its rows for {counties} counties." if not unreconciled
            else "Did not add up: " + "; ".join(unreconciled) + ".")),
    ]
    for y, (path, rows_) in past.items():
        date, words = PAST[y]
        src.append((SRC_PAST[y], STATE, "official results", "Washington Secretary of State",
                    f"{words} General Election results, statewide export (AllState.csv)", PAST_URL.format(date), "", mtime(path), sha(path),
                    len(rows_),
                    "Legislative races only were read (race, candidate, votes). "
                    + ("Used for who won each House position, which the roster does not record, and for which Senate seats were elected "
                       "for four years in 2024." if y == "2024" else "Used for which Senate seats were elected in 2022, whose terms end in January 2027.")))
    src.append((SRC_ROSTER, STATE, "roster", "Open States people project (CC0), as loaded into state_wa.sqlite", "Sitting Washington legislators",
                "https://github.com/openstates/people", "", mtime(roster_db), sha(roster_db), len(legs),
                "Who holds each legislative seat today (chamber and district); the roster carries no House position and no judges."))
    for fsid, (fname, url, title) in W.SCANS.items():
        path = os.path.join(folder, fname)
        if os.path.exists(path):
            src.append((SCAN_SRC[fsid], STATE, "official certification", "Washington Secretary of State", title, url, "", mtime(path), sha(path), 0,
                        f"Posted on {W.SOS_PAGE}. A scanned image with no text layer (the federal loader's copy): fingerprinted here, not read."))

    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA)
    with con:
        con.execute("DELETE FROM sl_candidates WHERE race_id IN (SELECT race_id FROM sl_races WHERE state = ?)", (STATE,))
        con.execute("DELETE FROM sl_candidates WHERE race_id LIKE ?", (f"2026-{STATE}-%",))
        con.execute("DELETE FROM sl_races WHERE state = ?", (STATE,))
        con.execute("DELETE FROM sl_sources WHERE state = ?", (STATE,))
        con.executemany(f"INSERT INTO sl_races VALUES ({','.join('?' * len(cols))})", race_rows)
        con.executemany("INSERT INTO sl_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", cands)
        con.executemany("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", src)
    con.close()

    gen_rows = [c for c in cands if c[1] == "general"]
    pri_rows = [c for c in cands if c[1] == "primary"]
    by = lambda kind, rows_: sum(1 for c in rows_ if races[c[0]]["office_kind"] == kind)
    nk = lambda kind: sum(1 for r in races.values() if r["office_kind"] == kind)
    say(f"    Washington: {len(races)} races ({nk('state_senate')} Senate, {nk('state_house')} House, {nk('supreme_court')} Supreme Court, "
        f"{nk('court_of_appeals')} Court of Appeals); {len(gen_rows)} candidates on the November list (Senate {by('state_senate', gen_rows)}, "
        f"House {by('state_house', gen_rows)}, Supreme Court {by('supreme_court', gen_rows)}, Court of Appeals "
        f"{by('court_of_appeals', gen_rows)}; {len(gone)} withdrawn left off); {fields} top-two primary fields, {len(pri_rows)} primary rows "
        f"(Senate {by('state_senate', pri_rows)}, House {by('state_house', pri_rows)}, Supreme Court {by('supreme_court', pri_rows)}), "
        "certified votes, county sums checked")
    for c in cands:
        if c[12] and not c[7]:
            say(f"      matched elsewhere: {c[0]} {c[1]}: {c[3]} -> {c[12]}")
    for line in report:
        say(f"      check: {line}")
    return len(gen_rows)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m ballot.state_local_wa <database>")
    load(sys.argv[1])
