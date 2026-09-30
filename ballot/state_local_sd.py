"""
ballot/state_local_sd.py - South Dakota's state races on the November 3, 2026 ballot: every State Senate seat (35, one
member a district), every State House seat (70: two members a district, except that Districts 26 and 28 are each split
into single-member A and B districts), Governor and Lieutenant Governor (one ticket, one vote), and the statewide offices
on this year's list: Secretary of State, Attorney General, State Auditor, State Treasurer, Commissioner of School and
Public Lands and Public Utilities Commissioner. South Dakota elects both chambers every two years, so every seat is up.

Sources, the Secretary of State's own and nothing else:

  - The 2026 General Election Candidate List (vip.sdsos.gov, election 774): a Telerik grid of every contest, 50 rows a
    page, paged here through the grid's own page links (one request a second). Columns are taken by name, and only
    Contest, Name, Party, District/County, Ballot Order, Status, WithdrawnDate, OfficeSeqNum, DistrictType, elType and
    eldate; the grid also carries mailing addresses (Mailing Address, elAddress1, elAddress2, elCity, elState, elZip),
    which are never read, printed or kept. Only the state offices' rows are kept, and only those columns, as JSON in
    ballot_cache/sd/. A withdrawn candidate is left off the November ballot.
  - The 2026 Primary Election Candidate List (election 773), read the same way. South Dakota prints a party primary
    only when it is contested; every candidate in a contested primary has a ballot order on the list, which is used as
    a check (uncontested Democrats have one too, so its absence proves nothing). A party primary is a field when it has
    more candidates on the ballot than seats (one, or two in a two-member House district). Who advanced is read from the November list: the party's candidates for that seat
    there, a withdrawn one included (he or she won the primary and withdrew later).
  - The July 28 Republican runoff for Governor: the Secretary of State's results site (electionresults.sd.gov) shows it
    as its current election. Only the names of the runoff's two candidates are read from it (they are the two who
    advanced from the June 2 field); the site labels its figures "Unofficial Results", so no figure is loaded. The
    names are kept in ballot_cache/sd/ so a later run still has them once the site moves on to November.
  - No vote counts: the State Canvassing Board's certified canvass of the 2026 primary and runoff was not published on
    sdsos.gov as of 2026-09-30 (see ballot/lists/sd.py). Every primary and runoff row has votes None.

Today's holders come from state_sd.sqlite (the Open States roster): current legislators by chamber and district, and
the officials table for Governor, Attorney General and Secretary of State (the roster does not carry the Auditor, the
Treasurer, the Commissioner of School and Public Lands or the Public Utilities Commissioners). A two-member House
district has two holders: holder_id holds both roster ids joined by a comma, holder_name both names joined by " and ",
holder_party both parties joined by ", " (one party when both are the same). Only names, parties, districts and ids are
read from the roster; its e-mail, phone and address columns never are.

A candidate is marked as the sitting member (incumbent 1, state_member_id) only when the name fits a holder of that same
seat (for Governor, the first name on the ticket against the Governor), and the fit is one to one. A candidate who sits
today in the other chamber for the same district, or who holds another seat or office in the roster (for a statewide
race), gets state_member_id with incumbent 0 and a note, again only when exactly one roster person fits.

Usage: python ballot/state_local_sd.py <database file> [--cache <folder>]
"""

import datetime as dt
import hashlib
import html as H
import http.cookiejar
import json
import os
import re
import sqlite3
import sys
import time
import urllib.parse
from collections import Counter, defaultdict
from urllib.error import HTTPError, URLError
from urllib.request import HTTPCookieProcessor, Request, build_opener

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from ballot.common import fold, name_parts, party_code      # noqa: E402
from ballot.match import fits                               # noqa: E402
from states import net                                      # noqa: E402

STATE, FIPS, NAME = "SD", "46", "South Dakota"
GENERAL, PRIMARY, RUNOFF = "2026-11-03", "2026-06-02", "2026-07-28"
GENERAL_URL = "https://vip.sdsos.gov/candidatelist.aspx?eid=774"
PRIMARY_URL = "https://vip.sdsos.gov/candidatelist.aspx?eid=773"
RUNOFF_URL = "https://electionresults.sd.gov/resultsSW.aspx?type=SWR&map=CTY"
ROSTER_DB = os.path.join(HERE, "state_sd.sqlite")
CACHE = os.path.join(HERE, "ballot_cache", "sd")

# the only grid columns ever read; every other column (the addresses among them) is never turned into text
KEEP = ("Contest", "Name", "Party", "District/County", "Ballot Order", "Status", "WithdrawnDate", "OfficeSeqNum",
        "DistrictType", "elType", "eldate")
STATE_TYPES = {"SW", "SEN", "HOU"}                          # statewide, State Senate, State House; county and local rows are skipped
PARTY = {"REP": "Republican", "DEM": "Democratic", "IND": "Independent", "LIB": "Libertarian"}
STATUS_MARK = re.compile(r"\s*\((?:Withdrawn|Successful Challenge)[^)]*\)\s*$")

# statewide contests as the lists print them: (race key, office_kind, office shown, roster office)
STATEWIDE = {
    "Governor and Lieutenant Governor": ("GOV", "governor", "Governor and Lieutenant Governor", "governor"),
    "Governor": ("GOV", "governor", "Governor and Lieutenant Governor", "governor"),        # the primary's name for the same race
    "Secretary of State": ("SOS", "secretary_of_state", "Secretary of State", "secretary of state"),
    "Attorney General": ("AG", "attorney_general", "Attorney General", "attorney general"),
    "State Auditor": ("AUD", "state_auditor", "State Auditor", None),
    "State Treasurer": ("TREAS", "state_treasurer", "State Treasurer", None),
    "Commissioner of School and Public Lands": ("SPL", "school_and_public_lands_commissioner", "Commissioner of School and Public Lands", None),
    "Public Utilities Commissioner": ("PUC", "public_utilities_commissioner", "Public Utilities Commissioner", None),
}
LEGISLATURE = {"State Senator": ("SS", "state_senate", "State Senator", "Senate"),
               "State Representative": ("SH", "state_house", "State Representative", "House")}
CHAMBER_WORDS = {"Senate": "the South Dakota Senate", "House": "the South Dakota House of Representatives"}

SRC_GENERAL = "sd-sos-2026-state-candidate-list"
SRC_PRIMARY = "sd-sos-2026-state-primary-candidate-list"
SRC_RUNOFF = "sd-sos-2026-governor-runoff-contest"
SRC_ROSTER = "sd-openstates-roster"

SCHEMA = """
CREATE TABLE IF NOT EXISTS sl_races (race_id TEXT PRIMARY KEY, state TEXT NOT NULL, level TEXT NOT NULL, office_kind TEXT NOT NULL, office TEXT NOT NULL, jurisdiction TEXT, jurisdiction_id TEXT, county_ids TEXT, district TEXT, seat TEXT, special INTEGER NOT NULL DEFAULT 0, partisan INTEGER NOT NULL, holder_id TEXT, holder_name TEXT, holder_party TEXT, election_date TEXT NOT NULL, note TEXT);
CREATE TABLE IF NOT EXISTS sl_candidates (race_id TEXT NOT NULL, election TEXT NOT NULL, election_date TEXT, name TEXT NOT NULL, party TEXT, party_code TEXT, ballot_order INTEGER, incumbent INTEGER NOT NULL DEFAULT 0, write_in INTEGER NOT NULL DEFAULT 0, votes INTEGER, pct REAL, outcome TEXT, state_member_id TEXT, source_id TEXT, note TEXT, PRIMARY KEY (race_id, election, name));
CREATE TABLE IF NOT EXISTS sl_sources (source_id TEXT PRIMARY KEY, state TEXT, kind TEXT, agency TEXT, title TEXT, url TEXT, published TEXT, fetched TEXT, sha256 TEXT, rows INTEGER, note TEXT);
CREATE TABLE IF NOT EXISTS sl_places (kind TEXT NOT NULL, id TEXT NOT NULL, name TEXT NOT NULL, county_ids TEXT, source_id TEXT, PRIMARY KEY (kind, id));
"""


def text(cell):
    return re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", "", cell))).strip()


# ---------- the candidate grids: allowed columns only ----------

def grid_rows(page):
    """The allowed columns of every row on one page of the grid, as dicts. Cells of other columns are never unescaped."""
    heads = [text(h) for h in re.findall(r'<th scope="col" class="rgHeader[^"]*"[^>]*>(.*?)</th>', page, re.S)]
    missing = [k for k in KEEP if k not in heads]
    if missing:
        raise SystemExit(f"South Dakota (state races): the candidate grid's columns changed; missing {missing}")
    idx = {k: heads.index(k) for k in KEEP}
    out = []
    for tr in re.findall(r'<tr class="(?:rgRow|rgAltRow)"[^>]*>(.*?)</tr>', page, re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        if len(cells) != len(heads):
            raise SystemExit("South Dakota (state races): a grid row does not line up with the grid's headings")
        out.append({k: text(cells[i]) for k, i in idx.items()})
    return out


def read_grid(url, election, say=print):
    """Every page of a candidate list; returns (items the grid reports, [state-office rows, allowed columns only]).
    Asks at most three times for any one page, then stops and says so."""
    opener = build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))
    net.patient_lookups()

    def ask(data=None):
        headers = {"User-Agent": net.UA, "Accept": "text/html"}
        if data:
            headers.update({"Content-Type": "application/x-www-form-urlencoded", "Referer": url})
        last = None
        for attempt in range(3):
            try:
                with opener.open(Request(url, data=data, headers=headers), timeout=120) as r:
                    page = r.read().decode("utf-8", "replace")
                if 'class="rgHeader' not in page:
                    raise SystemExit(f"South Dakota (state races): {url} answered without its candidate grid "
                                     "(a bot check or a changed page); stopped")
                return page
            except (HTTPError, URLError, OSError) as e:
                last = e
                if attempt < 2:
                    time.sleep(5 * (attempt + 1))
        raise SystemExit(f"South Dakota (state races): {url} refused three times ({last}); stopped")

    page = ask()
    if f"2026 {election} Election" not in page:
        raise SystemExit(f"South Dakota (state races): {url} is no longer the 2026 {election} Election list")
    info = re.search(r"(\d+)\s*(?:</strong>)?\s*items in\s*(?:<strong>)?\s*(\d+)", page)
    if not info:
        raise SystemExit("South Dakota (state races): the grid's item count was not found")
    items, pages = int(info.group(1)), int(info.group(2))
    seen, kept, n = 0, [], 1
    while True:
        rows = grid_rows(page)
        seen += len(rows)
        kept += [r for r in rows if r["DistrictType"] in STATE_TYPES and not r["Contest"].startswith("United States ")]
        if n >= pages:
            break
        pager = page[page.find('class="rgPager"'):][:20000]
        links = [(text(t), H.unescape(tg)) for tg, t in
                 re.findall(r'<a[^>]*href="javascript:__doPostBack\(&#39;([^&]+)&#39;[^"]*"[^>]*>(.*?)</a>', pager, re.S)]
        target = next((tg for t, tg in links if t == str(n + 1)), None)
        if target is None:                                   # past page 10: the last "..." opens the next block of pages
            target = next((tg for t, tg in reversed(links) if t == "..."), None)
        if target is None:
            raise SystemExit(f"South Dakota (state races): no link to page {n + 1} of {url}")
        form = {m.group(1): H.unescape(m.group(2))
                for m in re.finditer(r'<input type="hidden" name="([^"]+)" id="[^"]*" value="([^"]*)"', page)}
        form["__EVENTTARGET"], form["__EVENTARGUMENT"] = target, ""
        time.sleep(1.0)
        page = ask(urllib.parse.urlencode(form).encode())
        n += 1
        cur = re.search(r'class="rgCurrentPage"[^>]*>\s*<span>(\d+)</span>', page)
        if not cur or int(cur.group(1)) != n:
            raise SystemExit(f"South Dakota (state races): paging {url} went wrong at page {n}")
    if seen != items:
        raise SystemExit(f"South Dakota (state races): read {seen} rows of {url}, the grid reports {items}")
    return items, kept


def cached_grid(url, election, path, date_prefix, say=print):
    """Read a list afresh and keep its state rows (allowed columns only) as JSON; fall back to that JSON if the site
    cannot be read. Returns (items, rows, fetched, how)."""
    try:
        items, rows = read_grid(url, election, say)
    except SystemExit as e:
        if not os.path.exists(path):
            raise
        got = json.load(open(path, encoding="utf-8"))
        say(f"    South Dakota (state races): {e}; using the copy kept on {got['fetched']}")
        return got["items"], got["rows"], got["fetched"], "kept copy"
    odd = [r for r in rows if not r["eldate"].startswith(date_prefix) or r["elType"] != election]
    if odd:
        raise SystemExit(f"South Dakota (state races): {len(odd)} rows of the {election} list are not dated {date_prefix}")
    fetched = dt.date.today().isoformat()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"url": url, "fetched": fetched, "items": items, "columns": list(KEEP), "rows": [{k: r[k] for k in KEEP} for r in rows]},
                  fh, ensure_ascii=False, indent=0)
    return items, rows, fetched, "read afresh"


# ---------- the July 28 runoff: the two names only ----------

def runoff_names(path, say=print):
    """The candidates in the Republican runoff for Governor, from the results site while it still shows July 28; else
    from the names kept earlier. Returns (names, fetched) or (None, None)."""
    try:
        page = net.get(RUNOFF_URL).decode("utf-8", "replace")
        date = re.search(r'id="hidElectionDate[^"]*" value="([^"]*)"', page)
        if date and date.group(1) == "7/28/2026":
            page = re.sub(r"<(script|style).*?</\1>", "", page, flags=re.S)
            contests = {}
            for block in page.split('class="display-results-box-a"')[1:]:
                title = re.search(r"<h1>(.*?)</h1>", block, re.S)
                title = text(re.sub(r"<span.*?</span>", "", title.group(1), flags=re.S)) if title else ""
                contests[title] = [(text(n), text(p)) for n, p in re.findall(
                    r'class="col display-results-box-d">\s*<h1>(.*?)</h1>\s*<h2[^>]*>(.*?)</h2>', block, re.S)]
            names = [n for n, p in contests.get("Governor", []) if p == "Republican"]
            if len(names) == 2 and len(contests.get("Governor", [])) == 2:
                fetched = dt.date.today().isoformat()
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w", encoding="utf-8") as fh:
                    json.dump({"url": RUNOFF_URL, "fetched": fetched, "election": "2026-07-28 Republican primary runoff, Governor",
                               "names": names}, fh, ensure_ascii=False, indent=1)
                return names, fetched
            say("    South Dakota (state races): the results site's July 28 page does not show a two-candidate Republican runoff for Governor")
    except (HTTPError, URLError, OSError) as e:
        say(f"    South Dakota (state races): the results site could not be read ({e})")
    if os.path.exists(path):
        got = json.load(open(path, encoding="utf-8"))
        return got["names"], got["fetched"]
    return None, None


# ---------- the roster: names, parties, districts and ids only ----------

def roster():
    con = sqlite3.connect(ROSTER_DB)
    seats = defaultdict(list)                                # (chamber, district) -> [person]
    for bid, first, last, full, party, district, chamber in con.execute(
            "SELECT bioguide_id, first_name, last_name, official_full, party_name, district, chamber FROM legislators WHERE is_current = 1"):
        seats[(chamber, district)].append({"id": bid, "first": first or "", "last": last or "", "full": full or f"{first} {last}",
                                           "party": party, "chamber": chamber, "district": district})
    offices = {}
    for bid, first, last, full, office, label, party in con.execute(
            "SELECT bioguide_id, first_name, last_name, official_full, office, office_label, party_name FROM officials"):
        offices[office] = {"id": bid, "first": first or "", "last": last or "", "full": full or f"{first} {last}", "party": party, "label": label}
    as_of = con.execute("SELECT MAX(updated_at) FROM legislators").fetchone()[0] or ""
    con.close()
    return seats, offices, as_of[:10]


def person_fits(name, p):
    cand = name_parts(name)
    return fits(cand, ([w for w in fold(p["first"]).split()], fold(p["last"]))) or fits(cand, name_parts(p["full"]))


def same_person(a, b):
    """Two ways of writing one candidate's name ('Larry  Rhoden' on the results site, 'Larry Rhoden' on the list)."""
    return fold(a) == fold(b) or fits(name_parts(a), name_parts(b))


def ticket_head(name):
    """'Larry Rhoden & Tony Venhuizen' -> 'Larry Rhoden' (the candidate for Governor is named first)."""
    return re.split(r"\s+(?:&|and)\s+", name, maxsplit=1)[0]


# ---------- the load ----------

def race_of(contest, district_text):
    """(race_id, info) for a state contest on the lists; a SystemExit for a contest the loader does not know."""
    if contest in STATEWIDE:
        key, kind, office, roster_office = STATEWIDE[contest]
        return f"2026-{STATE}-{key}", {"level": "statewide", "office_kind": kind, "office": office, "district": None,
                                       "chamber": None, "roster": roster_office}
    if contest in LEGISLATURE:
        m = re.fullmatch(r"District 0*(\d+[AB]?)", district_text)
        if not m:
            raise SystemExit(f"South Dakota (state races): a district the loader cannot read: {district_text!r}")
        key, kind, office, chamber = LEGISLATURE[contest]
        d = m.group(1)
        return f"2026-{STATE}-{key}{d}", {"level": "legislature", "office_kind": kind, "office": office, "district": d,
                                          "chamber": chamber, "roster": None}
    raise SystemExit(f"South Dakota (state races): an office the loader does not know: {contest!r}")


def sha_of(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest() if path and os.path.exists(path) else ""


def after_primary(date_text):
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", date_text or "")
    return bool(m) and dt.date(int(m.group(3)), int(m.group(1)), int(m.group(2))) > dt.date(2026, 6, 2)


def load(db_path, say=print, cache=CACHE):
    seats, offices, as_of = roster()
    checks = []
    g_path = os.path.join(cache, "sd_2026_general_state.json")
    p_path = os.path.join(cache, "sd_2026_primary_state.json")
    r_path = os.path.join(cache, "sd_2026_governor_runoff_names.json")
    g_items, g_rows, g_fetched, g_how = cached_grid(GENERAL_URL, "General", g_path, "11/3/2026", say)
    p_items, p_rows, p_fetched, p_how = cached_grid(PRIMARY_URL, "Primary", p_path, "6/2/2026", say)
    ro_names, ro_fetched = runoff_names(r_path, say)

    # ---- races: every contest on the November list, and every seat the roster says exists
    races = {}
    for r in g_rows:
        rid, info = race_of(r["Contest"], r["District/County"])
        races.setdefault(rid, info)
    for r in p_rows:
        rid, info = race_of(r["Contest"], r["District/County"])
        if rid not in races:
            raise SystemExit(f"South Dakota (state races): {rid} is on the primary list but not on the November list")
    missing_seats = sorted({f"2026-{STATE}-{'SS' if ch == 'Senate' else 'SH'}{d}" for (ch, d) in seats} - set(races))
    # one senator a district; two representatives, except in the single-member A and B districts (26A, 26B, 28A, 28B)
    n_seats = {rid: 2 if i["chamber"] == "House" and not i["district"][-1:].isalpha() else 1 for rid, i in races.items()}
    for rid, i in races.items():
        held = len(seats.get((i["chamber"], i["district"]), [])) if i["level"] == "legislature" else None
        if held is not None and held != n_seats[rid]:
            checks.append(f"{rid}: the roster lists {held} sitting members for {n_seats[rid]} seats")

    holders, notes = {}, {}
    for rid, i in races.items():
        if i["level"] == "legislature":
            hs = seats.get((i["chamber"], i["district"]), [])
            holders[rid] = hs
            if not hs:
                notes[rid] = f"The Open States roster ({as_of}) lists no sitting member for this seat."
            if i["chamber"] == "House" and n_seats[rid] == 2:
                notes[rid] = ("Elect 2. Two members represent this district in the State House; the two candidates with the "
                              "most votes are elected." + (" " + notes[rid] if rid in notes else ""))
        else:
            h = offices.get(i["roster"]) if i["roster"] else None
            holders[rid] = [h] if h else []
            if not h:
                notes[rid] = "The Open States roster this site uses does not carry this office, so today's holder is not shown."
    notes[f"2026-{STATE}-GOV"] = ("South Dakota elects the Governor and Lieutenant Governor together, on one vote; the list "
                                  "names each ticket, the candidate for Governor first.")
    primary_offices = {race_of(r["Contest"], r["District/County"])[0] for r in p_rows}
    for rid, i in races.items():
        if i["level"] == "statewide" and rid not in primary_offices:
            notes[rid] = ((notes[rid] + " ") if rid in notes else "") + "This office was not on the June 2 primary ballot."

    # everyone in the roster, for a candidate who sits today in another seat or office
    everyone = [p for ps in seats.values() for p in ps] + [dict(p, chamber=None, district=None) for p in offices.values()]

    def sitting(rid, names):
        """{name: (member id, incumbent, note)}: a one-to-one fit with the seat's holders; else, for a legislative race,
        one sitting member of the other chamber for the same district; for a statewide race, one roster person."""
        i, out = races[rid], {}
        heads = {n: ticket_head(n) if rid.endswith("-GOV") else n for n in names}
        hs = holders[rid]
        pairs = [(n, h) for n in names for h in hs if person_fits(heads[n], h)]
        for n, h in pairs:
            if sum(1 for a, _ in pairs if a == n) == 1 and sum(1 for _, b in pairs if b["id"] == h["id"]) == 1:
                out[n] = (h["id"], 1, None)
        for n in names:
            if n in out:
                continue
            if i["level"] == "legislature":
                other = "House" if i["chamber"] == "Senate" else "Senate"
                pool = [p for (ch, d), ps in seats.items() if ch == other and
                        (d == i["district"] or (other == "House" and re.fullmatch(re.escape(i["district"]) + "[AB]", d or ""))
                         or (other == "Senate" and d == re.sub(r"[AB]$", "", i["district"]))) for p in ps]
            else:
                pool = [p for p in everyone if not any(p["id"] == h["id"] for h in hs)]
            got = [p for p in pool if person_fits(heads[n], p)]
            if len(got) == 1:
                p = got[0]
                where = (f"{CHAMBER_WORDS[p['chamber']]}, District {p['district']}" if p["chamber"] else p["label"])
                out[n] = (p["id"], 0, f"Serves today in {where}." if p["chamber"] else f"Serves today as {where}.")
        return out

    cand = []

    # ---- the November ballot
    on_ballot = defaultdict(list)
    noms_shown = defaultdict(list)                           # (race, party code) -> names on the list, withdrawn included
    withdrawn = []
    for r in g_rows:
        rid, _ = race_of(r["Contest"], r["District/County"])
        name = STATUS_MARK.sub("", r["Name"]).strip()
        noms_shown[(rid, r["Party"])].append(name)
        if r["Status"] != "Active" or r["WithdrawnDate"]:
            withdrawn.append(rid)
            continue
        on_ballot[rid].append(r | {"Name": name})
    primary_names = defaultdict(list)
    for r in p_rows:
        rid, _ = race_of(r["Contest"], r["District/County"])
        primary_names[(rid, r["Party"])].append(STATUS_MARK.sub("", r["Name"]).strip())
    for rid, rows in on_ballot.items():
        fit = sitting(rid, [r["Name"] for r in rows])
        for r in rows:
            party = PARTY.get(r["Party"], r["Party"])
            mid, inc, note = fit.get(r["Name"], (None, 0, None))
            n = [note] if note else []
            if races[rid]["level"] == "legislature" or rid.endswith("-GOV"):
                if r["Party"] in ("REP", "DEM") and not any(same_person(ticket_head(r["Name"]), x) for x in primary_names[(rid, r["Party"])]):
                    n.append(f"Not on the June 2 {party} primary list for this seat; named afterwards (the list does not say how).")
            if inc and holders[rid]:
                h = next(h for h in holders[rid] if h["id"] == mid)
                if h["party"] and h["party"] != party:
                    checks.append(f"{rid}: sitting member listed as {h['party']}, on the ballot as {party}")
            order = int(r["Ballot Order"]) if r["Ballot Order"].isdigit() else None
            cand.append((rid, "general", GENERAL, r["Name"], party, party_code(party), order, inc, 0, None, None, None,
                         mid, SRC_GENERAL, " ".join(n) or None))

    # ---- the June 2 primary fields, and the July 28 runoff
    ballot = defaultdict(list)                               # (race, party code) -> primary-ballot rows
    off_primary = 0
    for r in p_rows:
        rid, _ = race_of(r["Contest"], r["District/County"])
        on = r["Status"] == "Active" or (r["Status"] == "Withdrawn" and after_primary(r["WithdrawnDate"]))
        if not on:
            off_primary += 1
            continue
        ballot[(rid, r["Party"])].append(r | {"Name": STATUS_MARK.sub("", r["Name"]).strip()})
    fields = Counter()
    unsettled, order_odd = [], []
    runoff_used = False
    for (rid, code), rows in sorted(ballot.items()):
        k = n_seats[rid]
        printed = [r for r in rows if r["Ballot Order"].isdigit()]
        if len(rows) <= k:
            continue
        if len(printed) != len(rows):
            order_odd.append(f"{rid} {code} (a field of {len(rows)}, {len(printed)} with a ballot order)")
        party = PARTY.get(code, code)
        fields[races[rid]["office_kind"] if races[rid]["level"] == "legislature" else "statewide"] += 1
        fit = sitting(rid, [r["Name"] for r in rows])
        runoff = None
        if rid.endswith("-GOV") and code == "REP":
            if not ro_names:
                checks.append("the Republican runoff for Governor could not be read: June 2 outcomes left open")
            else:
                runoff = [n for n in ro_names if sum(1 for r in rows if same_person(n, r["Name"])) == 1]
                if len(runoff) != 2:
                    checks.append(f"the runoff's candidates ({ro_names}) are not both in the June 2 Republican field for Governor")
                    runoff = None
        if runoff:
            runoff_used = True
            # the November list names the ticket ("Larry Rhoden & Tony Venhuizen"): its first name is the nominee for Governor
            winner = [n for n in runoff if any(same_person(n, ticket_head(x)) for x in noms_shown[(rid, code)])]
            for r in rows:
                mid, inc, note = fit.get(r["Name"], (None, 0, None))
                a = any(same_person(n, r["Name"]) for n in runoff)
                cand.append((rid, f"primary-{code}", PRIMARY, r["Name"], party, party_code(party),
                             int(r["Ballot Order"]) if r["Ballot Order"].isdigit() else None, inc, 0, None, None,
                             "advanced" if a else "lost", mid, SRC_PRIMARY,
                             " ".join(x for x in [note, "Advanced to the July 28 runoff." if a else None] if x) or None))
            if len(winner) != 1:
                checks.append(f"the runoff's winner is not the one Republican on the November list for Governor ({runoff})")
            rfit = sitting(rid, runoff)
            for n in runoff:
                mid, inc, note = rfit.get(n, (None, 0, None))
                cand.append((rid, f"runoff-{code}", RUNOFF, n, party, party_code(party), None, inc, 0, None, None,
                             None if len(winner) != 1 else ("advanced" if n == winner[0] else "lost"), mid, SRC_RUNOFF, note))
            continue
        won = [r for r in rows if any(same_person(r["Name"], x) for x in noms_shown[(rid, code)])]
        settled = len(won) == k
        if not settled:
            unsettled.append(f"{rid} {party} ({len(won)} of {k} found on the November list)")
        for r in rows:
            mid, inc, note = fit.get(r["Name"], (None, 0, None))
            outcome = None if not settled else ("advanced" if r in won else "lost")
            cand.append((rid, f"primary-{code}", PRIMARY, r["Name"], party, party_code(party),
                         int(r["Ballot Order"]) if r["Ballot Order"].isdigit() else None, inc, 0, None, None, outcome, mid,
                         SRC_PRIMARY, note))

    # ---- checks on the whole
    keys = Counter((c[0], c[1], c[3]) for c in cand)
    dup = [k for k, v in keys.items() if v > 1]
    if dup:
        raise SystemExit(f"South Dakota (state races): the same name twice in one election: {dup}")
    gen_by_race = Counter(c[0] for c in cand if c[1] == "general")
    empty = sorted(rid for rid in races if gen_by_race[rid] == 0)
    short = sorted(f"{rid} ({gen_by_race[rid]} for {n_seats[rid]} seats)" for rid in races if 0 < gen_by_race[rid] < n_seats[rid])
    listed = len(g_rows)
    if gen_by_race.total() + len(withdrawn) != listed:
        raise SystemExit("South Dakota (state races): November rows written plus withdrawn do not equal the list's state rows")
    kind_of = lambda rid: races[rid]["office_kind"] if races[rid]["level"] == "legislature" else "statewide"
    sen = sorted(int(re.sub(r"\D", "", i["district"])) for i in races.values() if i["office_kind"] == "state_senate")
    if sen != list(range(1, 36)):
        checks.append(f"State Senate districts on the list are not 1 to 35: {sen}")
    house_seats = sum(n_seats[rid] for rid, i in races.items() if i["office_kind"] == "state_house")
    if house_seats != 70:
        checks.append(f"State House seats on the list add to {house_seats}, not 70")

    race_rows = []
    for rid, i in sorted(races.items()):
        hs = holders[rid]
        hid = ",".join(h["id"] for h in hs) or None
        hname = " and ".join(h["full"] for h in hs) or None
        hparty = ", ".join(dict.fromkeys(h["party"] for h in hs if h["party"])) or None
        race_rows.append((rid, STATE, i["level"], i["office_kind"], i["office"], NAME, FIPS, None, i["district"], None, 0, 1,
                          hid, hname, hparty, GENERAL, notes.get(rid)))

    n_primary_state = len(p_rows)
    src = [
        (SRC_GENERAL, STATE, "official candidate list", "South Dakota Secretary of State",
         "2026 General Election Candidate List (state offices and the Legislature)", GENERAL_URL, "", g_fetched, sha_of(g_path), listed,
         f"Every page of the grid read ({g_items} rows, {g_how}); the {listed} rows for state offices and the Legislature kept, and only "
         "Contest, Name, Party, District/County, Ballot Order, Status, WithdrawnDate, OfficeSeqNum, DistrictType, elType and eldate; "
         f"the grid's mailing-address columns are never read. Withdrawn, left off the November ballot: {len(withdrawn)}. Parties "
         "written out from REP, DEM, IND, LIB. The fingerprint is of the kept columns (ballot_cache/sd/sd_2026_general_state.json)."),
        (SRC_PRIMARY, STATE, "official candidate list", "South Dakota Secretary of State",
         "2026 Primary Election Candidate List, June 2, 2026 (Governor and the Legislature)", PRIMARY_URL, "", p_fetched, sha_of(p_path),
         n_primary_state,
         f"Every page of the grid read ({p_items} rows, {p_how}; most are county and party offices, not kept); {n_primary_state} rows "
         "for Governor and the Legislature kept, allowed columns only; mailing addresses never read. A party primary is a field when "
         "more candidates were on its ballot than seats; withdrawn before June 2 or decertified after a challenge, left off: "
         f"{off_primary}. Who advanced is read from the November list. No vote counts: the State Canvassing Board's certified "
         "canvass of the 2026 primary was not published on sdsos.gov as of 2026-09-30, and the results site labels its figures unofficial."),
        (SRC_ROSTER, STATE, "roster", "Open States people project (CC0)",
         "South Dakota legislators and statewide officials, as loaded into state_sd.sqlite", "https://github.com/openstates/people",
         as_of, as_of, "", sum(len(v) for v in seats.values()) + len(offices),
         "Today's holder of each seat and office (names, parties, districts and ids only). The roster does not carry the Auditor, "
         "the Treasurer, the Commissioner of School and Public Lands or the Public Utilities Commissioners."),
    ]
    if runoff_used:
        src.append((SRC_RUNOFF, STATE, "results site (candidate names only)", "South Dakota Secretary of State",
                    "Primary Election July 28, 2026: Governor (the Republican runoff's two candidates)", RUNOFF_URL, "", ro_fetched,
                    sha_of(r_path), len(ro_names),
                    "Only the names of the runoff's two candidates are read, as the two who advanced from the June 2 Republican field; "
                    "the winner is the Republican on the November list. The site labels its figures \"Unofficial Results\", so no "
                    "figure is loaded; votes wait for the State Canvassing Board's certified canvass."))

    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA)
    with con:
        con.execute("DELETE FROM sl_candidates WHERE race_id IN (SELECT race_id FROM sl_races WHERE state = ?) OR race_id LIKE ?",
                    (STATE, f"2026-{STATE}-%"))
        con.execute("DELETE FROM sl_races WHERE state = ?", (STATE,))
        con.execute("DELETE FROM sl_sources WHERE state = ?", (STATE,))
        con.executemany("INSERT INTO sl_races VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", race_rows)
        con.executemany("INSERT INTO sl_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", cand)
        con.executemany("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", src)
    con.close()

    # ---- the report: counts only
    by = Counter(kind_of(rid) for rid in races)
    gen = Counter(kind_of(c[0]) for c in cand if c[1] == "general")
    one = Counter(kind_of(rid) for rid, v in gen_by_race.items() if v <= n_seats[rid])
    inc = Counter(kind_of(c[0]) for c in cand if c[1] == "general" and c[7])
    say(f"    South Dakota (state races): {by['state_senate']} Senate seats, {by['state_house']} House races ({house_seats} seats), "
        f"{by['statewide']} statewide offices; {gen.total()} candidates on the November "
        f"ballot (Senate {gen['state_senate']}, House {gen['state_house']}, statewide {gen['statewide']}; {len(withdrawn)} withdrawn left "
        f"off; no more candidates than seats: Senate {one['state_senate']}, House {one['state_house']}, statewide {one['statewide']}); "
        f"sitting member on the ballot: Senate {inc['state_senate']}, House {inc['state_house']}, statewide {inc['statewide']}; "
        f"primary fields: Senate {fields['state_senate']}, House {fields['state_house']}, statewide {fields['statewide']}"
        + ("; the July 28 runoff for Governor" if runoff_used else "") + " (who advanced, no vote counts)")
    for label, items in (("no candidate on the November list", empty), ("fewer candidates than seats", short),
                         ("seats in the roster not on the November list", missing_seats), ("primary fields left open", unsettled),
                         ("ballot order does not match the field", order_odd)):
        if items:
            say(f"    CHECK South Dakota (state races): {label}: {', '.join(items)}")
    for c in checks:
        say(f"    CHECK South Dakota (state races): {c}")
    return len(cand)


if __name__ == "__main__":
    args = sys.argv[1:]
    cache = CACHE
    if "--cache" in args:
        i = args.index("--cache")
        cache = args[i + 1]
        del args[i:i + 2]
    if len(args) != 1:
        raise SystemExit("usage: python ballot/state_local_sd.py <database file> [--cache <folder>]")
    load(args[0], cache=cache)
