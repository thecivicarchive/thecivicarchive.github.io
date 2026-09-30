"""
ballot/state_local_ky.py - Kentucky's state races on the November 3, 2026 ballot: the nineteen even-numbered State Senate
seats (four-year terms, half the Senate every two years; the Secretary of State's list names exactly these), all 100 seats
of the House of Representatives, and the appellate court seats on the list (one Justice of the Supreme Court and three
Judges of the Court of Appeals, all nonpartisan), with each party's contested May 19 primary and its certified votes.
Kentucky elects its Governor and the other statewide officers in odd years (2027 next), so no statewide office is on the
2026 ballot.

Sources, both the state's own and both the ones the federal loader (ballot/lists/ky.py) already reads:
  - The Secretary of State's "Candidate Filings with the Office of the Secretary of State" for the 2026 General Election
    (web.sos.ky.gov/CandidateFilings/): the pages for State Senator (Default.aspx?id=11), State Representative (id=12),
    Justice of the Supreme Court (id=14) and Judge of the Court of Appeals (id=15), read with the federal loader's
    filings(): the page must be the 2026 General Election's, columns are taken by their headings, and only Name (the
    first line of the cell), Office, District/Division and Party are turned into text; the address and e-mail column is
    never read. Every group's count in its heading must match its rows. A candidate in the "Withdrawn / Deceased /
    Disqualified" group is left off and counted. Party printed "Write-In" is a declared write-in (not printed on the
    ballot). The list gives no ballot order (it goes by district, then filing); its own order within a race is kept, as
    on the federal side, write-ins left out of it. The other offices on the list (Commonwealth's Attorney, Circuit and
    District Judges, Family Court, the constitutional amendment) are local or not a candidate race and are counted only.
  - The State Board of Elections' "Official 2026 Primary Election Results" certification (the PDF the federal loader
    caches as ballot_cache/ky/ky_2026_primary_certification_of_vote_totals.pdf), its State Senator and State
    Representative sections, read with the federal loader's text-position parts. Kentucky prints a primary only when it
    is contested; each section's county rows must add up to its Total Votes row. The certification prints no write-in
    line, so a field's total is the sum of its candidates' votes. The most votes wins (no runoffs); the one on the
    November list for that party must be the field's top vote-getter.
  - Holders of each legislative seat from the Open States roster in state_ky.sqlite (legislators, is_current = 1, by
    chamber and district). The roster carries no judges, so the court seats show no holder.

Privacy: only office, district, candidate name, party, ballot order (the list's own), status and votes are read. The
filings pages are never saved: only the kept cells of each row go to ballot_cache/ky/sl_ky_2026_general_filings_state.json,
with each page's SHA-256. The certification holds names and vote counts only.

    python -m ballot.state_local_ky <path to a test database>
"""

import datetime as dt
import hashlib
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

from ballot import pdftext as P  # noqa: E402
from ballot.common import CACHE, fold, name_parts, party_code  # noqa: E402
from ballot.lists import ky as KY  # noqa: E402
from ballot.match import fits  # noqa: E402
from states import net  # noqa: E402

STATE = "KY"
GENERAL, PRIMARY = "2026-11-03", KY.PRIMARY
ROSTER = os.path.join(HERE, "state_ky.sqlite")
SRC_LIST, SRC_CERT, SRC_ROSTER = "ky-sos-2026-state-general-filings", "ky-sbe-2026-state-primary-certification", "ky-openstates-roster"
LIST_FILE = "sl_ky_2026_general_filings_state.json"
CERT_FILE = "ky_2026_primary_certification_of_vote_totals.pdf"          # the federal loader's copy

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

# The Candidate Filings pages read here: page id -> (office as the page prints it, race prefix, level, office_kind, partisan).
PAGES = {"11": ("State Senator", "SS", "legislature", "state_senate", 1),
         "12": ("State Representative", "SH", "legislature", "state_house", 1),
         "14": ("Justice of the Supreme Court", "SC", "court", "supreme_court", 0),
         "15": ("Judge of the Court of Appeals", "COA", "court", "court_of_appeals", 0)}
KIND = {v[0]: (k,) + v[1:] for k, v in PAGES.items()}
# The certification's sections read here, and the district line each carries.
CERT_OFFICES = {"State Senator": "state_senate", "State Representative": "state_house"}
CERT_DISTRICT = re.compile(r"^(\d+)(?:st|nd|rd|th) (Senatorial|Representative) District$")
ORDINAL = re.compile(r"^(\d+)(?:st|nd|rd|th)$")
COA_DISTRICT = re.compile(r"^(\d+)(?:st|nd|rd|th) / (\d+)(?:st|nd|rd|th)$")
PRIMARY_CODE = {"Republican Party": "REP", "Democratic Party": "DEM"}
NONPARTISAN = "Nonpartisan office"
SENATE_SEATS, HOUSE_SEATS = 38, 100

SENATE_NOTE = ("Kentucky senators serve four-year terms, and half the Senate is elected every two years (Kentucky Constitution, "
               "Section 31). This is one of the 19 districts, the even-numbered ones, on the Secretary of State's 2026 list.")
COURT_NOTE = ("A nonpartisan office: no party is printed on the ballot. The Open States roster does not carry judges, so no holder "
              "is shown. The Secretary of State's list names only the court seats someone filed for.")
ORDER_NOTE = ("Kentucky's candidate list gives no ballot order; candidates are kept in the list's own order (by district, then "
              "filing), declared write-ins left out of it.")
WRITE_IN = KY.WRITE_IN
CAPS = KY.CAPS
NOT_ON_LIST = KY.NOT_ON_LIST


# ------------------------------------------------------------------------------------------------ fetching and caching

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


def fresh(path, days):
    return os.path.exists(path) and time.time() - os.path.getmtime(path) < days * 86400


def filings(folder, say, max_age_days=2):
    """The kept cells of the four state office pages, as JSON in the cache: {read, pages: {office: {url, sha256, groups, rows}}}.
    The pages themselves are never written anywhere."""
    path = os.path.join(folder, LIST_FILE)
    if fresh(path, max_age_days):
        return path
    keep = {"read": dt.date.today().isoformat(), "pages": {}}
    try:
        for pid, (office, *_rest) in PAGES.items():
            raw = fetch(KY.FILINGS + pid, accept="text/html", say=say)
            got = KY.filings(raw.decode("utf-8", "replace"), office)
            keep["pages"][office] = {"url": KY.FILINGS + pid, "sha256": hashlib.sha256(raw).hexdigest(),
                                     "groups": got["groups"], "rows": got["rows"]}
            time.sleep(1.5)
    except (HTTPError, OSError) as e:
        if os.path.exists(path):
            say(f"      the Candidate Filings pages could not be read ({e}); using the copy read earlier")
            return path
        raise
    json.dump(keep, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return path


def other_offices(say):
    """The office links on the Candidate Filings home page with their counts: [(office, count)] (headings only)."""
    try:
        raw = fetch("https://web.sos.ky.gov/CandidateFilings/", accept="text/html", say=say).decode("utf-8", "replace")
    except (HTTPError, OSError):
        return None
    out = []
    for m in re.finditer(r'<a[^>]+href="[^"]*[Dd]efault\.aspx\?id=(\d+)[^"]*"[^>]*>(.*?)</a>', raw, re.S):
        text = KY.text_of(m.group(2))
        c = re.fullmatch(r"(.+?) \((\d+)\)", text)
        if c:
            out.append((m.group(1), c.group(1), int(c.group(2))))
    return out


# ---------------------------------------------------------------------------------------------- the primary certification

def certification(path):
    """[{office, district, party, names, total, counties, page}] for every State Senator and State Representative section
    of the certification: the federal loader's reader (ballot/lists/ky.py certification()), with the state offices'
    sections and their district lines in place of the federal ones."""
    pdf = P.PDF(open(path, "rb").read())
    out, cur, section, covers = [], None, None, []
    for n, (page, res) in enumerate(pdf.pages(), start=1):
        runs = KY.page_runs(pdf, page, res)
        flat = [r for r in runs if abs(r[3] - r[1]) < 0.01]
        up = [r for r in runs if abs(r[3] - r[1]) >= 0.01]
        rows = KY.flat_rows(flat)
        texts = [P.join(rs) for _y, rs in rows]
        if "For the office of" in texts:
            if cur is not None:
                raise SystemExit(f"Kentucky: a certification section ends at page {n} without its Total Votes row")
            section = texts[texts.index("For the office of") + 1]
            covers.append(section)
            if not any("Official 2026 Primary Election Results" == t for t in texts):
                raise SystemExit("Kentucky: the certification's cover page is not the Official 2026 Primary Election Results'")
            continue
        if section not in CERT_OFFICES:
            continue
        pending, head = [], None
        for (y, rs), text in zip(rows, texts):
            if KY.PAGE_HEAD.match(text):
                continue
            toks = KY.tokens(rs)
            nums = [t for t in toks if KY.NUMBER.match(t[2])]
            if text.startswith("Total Votes"):
                if cur is None or len(nums) != len(cur["edges"]):
                    raise SystemExit(f"Kentucky: a Total Votes row on page {n} of the certification does not fit its section")
                cur["total"] = [int(t[2].replace(",", "")) for t in nums]
                out.append(cur)
                cur, pending = None, []
                continue
            if nums and not KY.NUMBER.match(toks[0][2]) and all(KY.NUMBER.match(t[2]) for t in toks[1:]):     # a county row
                if head is not None:
                    edges = [t[1] for t in nums]
                    where = f"{head['office']} {head['district']} {head['party']}"
                    cols = {}
                    for rs2 in head["names"]:
                        for k, t in KY.by_edge(rs2, edges, where).items():
                            cols.setdefault(k, []).append(t)
                    for x, top, bottom, t in KY.upward_lines(up):
                        if bottom > y and top < head["y"]:
                            k = [k for k, e in enumerate(edges) if 0 < e - x < 50]
                            if len(k) != 1:
                                raise SystemExit(f"Kentucky: a name printed upward in {where} is under no column")
                            cols.setdefault(k[0], []).append((x, t))
                    names = []
                    for k in range(len(edges)):
                        got = cols.get(k, [])
                        if got and isinstance(got[0], tuple):
                            got = [t for _x, t in sorted(got, reverse=True)]
                        if not got:
                            raise SystemExit(f"Kentucky: column {k + 1} of {where} has no name")
                        names.append(" ".join(got))
                    cur = {"office": head["office"], "district": head["district"], "party": head["party"], "names": names,
                           "edges": edges, "counties": {}, "page": n}
                    head = None
                if cur is None:
                    raise SystemExit(f"Kentucky: a county row on page {n} of the certification comes before any section heading")
                county = toks[0][2]
                vals = {}
                for t in nums:
                    k = [k for k, e in enumerate(cur["edges"]) if abs(t[1] - e) <= 1.5]
                    if len(k) != 1:
                        raise SystemExit(f"Kentucky: a number in {county}'s row on page {n} is under no column")
                    vals[k[0]] = int(t[2].replace(",", ""))
                if len(vals) != len(cur["edges"]) or county in cur["counties"]:
                    raise SystemExit(f"Kentucky: {county}'s row on page {n} of the certification does not fit its section")
                cur["counties"][county] = [vals[k] for k in range(len(cur["edges"]))]
                continue
            if KY.PARTY_ROW.match(text):
                if cur is not None:
                    raise SystemExit(f"Kentucky: a new section starts on page {n} of the certification before the last one's Total Votes row")
                if not pending or pending[0] != section:
                    raise SystemExit(f"Kentucky: a party heading on page {n} of the certification has no {section} heading above it")
                ds = [CERT_DISTRICT.match(t) for t in pending[1:]]
                ds = [m for m in ds if m]
                if len(ds) != 1 or (ds[0].group(2) == "Senatorial") != (section == "State Senator"):
                    raise SystemExit(f"Kentucky: a {section} section on page {n} of the certification names no district of its chamber")
                head = {"office": section, "district": str(int(ds[0].group(1))), "party": text, "y": y, "names": []}
                pending = []
                continue
            if head is not None:
                head["names"].append(rs)
            elif cur is None:
                pending.append(text)
            # else: the names printed again at the top of a section's next page
    if cur is not None or head is not None:
        raise SystemExit("Kentucky: the certification's last state section has no Total Votes row")
    for office in CERT_OFFICES:
        if office not in covers:
            raise SystemExit(f"Kentucky: the certification has no {office} part")
    return out, covers


# ---------------------------------------------------------------------------------------------------------- the roster

def roster(path):
    """Sitting legislators: ids, names, party, chamber and district only (the roster's contact columns are never selected)."""
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    legs = [dict(zip(("id", "first", "last", "full", "other", "party", "chamber", "district"), r)) for r in con.execute(
        "SELECT bioguide_id, first_name, last_name, official_full, other_names, party_name, chamber, district "
        "FROM legislators WHERE is_current = 1")]
    con.close()
    return legs


def person_fits(name, p):
    """A listed name fits a roster person: same family name and a given name that fits (the roster's first name or any
    other form of the name it keeps)."""
    readings = [name_parts(name), name_parts(re.sub(r'"[^"]*"', " ", name))]        # with and without a quoted nickname
    forms = [(fold(p["first"] or "").split(), " ".join(fold(p["last"] or "").split()))]
    forms += [name_parts(o.strip()) for o in (p.get("other") or "").split(";") if o.strip() and "," not in o and "." not in o]
    return any(f[1] and fits(r, f) for r in readings for f in forms)


def bare(party):
    return re.sub(r"\s+Party$", "", (party or "").strip())


def chamber_words(p):
    return f"Kentucky {'Senate' if p['chamber'] == 'Senate' else 'House'}, District {int(p['district'])}"


# ------------------------------------------------------------------------------------------------------------ loading

def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def mtime(path):
    return dt.datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d")


def race_for(row):
    """(race_id, level, office_kind, office, jurisdiction, district, seat, partisan) for one list row."""
    office, dd = row["Office"], row["District/Division"]
    pid, prefix, level, okind, partisan = KIND[office]
    if okind == "court_of_appeals":
        m = COA_DISTRICT.match(dd)
        if not m:
            raise SystemExit(f"Kentucky: could not read the district and division of a Court of Appeals filing ({dd!r})")
        d, div = str(int(m.group(1))), str(int(m.group(2)))
        return (f"2026-{STATE}-{prefix}{d}-{div}", level, okind, office, f"Court of Appeals District {d}, Division {div}", d, div, partisan)
    m = ORDINAL.match(dd)
    if not m:
        raise SystemExit(f"Kentucky: could not read the district of a {office} filing ({dd!r})")
    d = str(int(m.group(1)))
    where = {"state_senate": "Senate District", "state_house": "House District", "supreme_court": "Supreme Court District"}[okind]
    return (f"2026-{STATE}-{prefix}{d}", level, okind, office, f"{where} {d}", d, None, partisan)


def load(db_path, say=print, cache=CACHE, roster_db=ROSTER):
    net.patient_lookups()
    folder = os.path.join(cache, "ky")
    os.makedirs(folder, exist_ok=True)
    report = []

    lpath = filings(folder, say)
    listed = json.load(open(lpath, encoding="utf-8"))
    cpath = os.path.join(folder, CERT_FILE)
    net.download(KY.CERT_URL, cpath, max_age_days=30, say=say)
    if not open(cpath, "rb").read(5).startswith(b"%PDF"):
        raise SystemExit("Kentucky: the primary certification downloaded is not a PDF; read the results page again")
    sections, covers = certification(cpath)
    legs = roster(roster_db)
    home = other_offices(say)

    # ---- races and November candidates, from the list
    races, general, gone, write_ins, order, nominee, counted = {}, [], [], [], {}, {}, {}
    for office, page in listed["pages"].items():
        live = sum(c for _g, c, w in page["groups"] if not w)
        counted[office] = (live, sum(1 for r in page["rows"] if not r["withdrawn"]))
        if counted[office][0] != counted[office][1]:
            report.append(f"the {office} page's headings count {live} candidates but {counted[office][1]} rows were read")
        for r in page["rows"]:
            rid, level, okind, office_, juris, d, seat, partisan = race_for(r)
            if r["withdrawn"]:
                gone.append((rid, r["Name"]))
                continue
            if rid not in races:
                chamber = {"state_senate": "Senate", "state_house": "House"}.get(okind)
                hs = [p for p in legs if chamber and p["chamber"] == chamber and str(p["district"]).lstrip("0") == d]
                h = hs[0] if len(hs) == 1 else None
                note = []
                if okind == "state_senate":
                    note.append(SENATE_NOTE)
                if chamber and h is None:
                    note.append("The roster shows no sitting member for this seat.")
                    report.append(f"{rid}: {len(hs)} sitting members in the roster for this seat")
                if not partisan:
                    note.append(COURT_NOTE)
                note.append(ORDER_NOTE)
                races[rid] = dict(race_id=rid, state=STATE, level=level, office_kind=okind, office=office_, jurisdiction=juris,
                                  jurisdiction_id=d, county_ids=None, district=d, seat=seat, special=0, partisan=partisan,
                                  holder_id=h["id"] if h else None, holder_name=h["full"] if h else None,
                                  holder_party=h["party"] if h else None, election_date=GENERAL, note=" ".join(note), _holder=h,
                                  _chamber=chamber)
            party = r["Party"]
            write_in = int(party == "Write-In")
            if not partisan:
                if party not in ("Nonpartisan", "Write-In"):
                    report.append(f"{rid}: a nonpartisan seat's candidate is listed with the party {party!r}")
                shown_party, code = NONPARTISAN, "N"
            else:
                shown_party, code = party, party_code(party)
            if write_in:
                write_ins.append((rid, r["Name"]))
                pos = None
            else:
                order[rid] = order.get(rid, 0) + 1
                pos = order[rid]
                if party in PRIMARY_CODE:
                    if (rid, party) in nominee:
                        raise SystemExit(f"Kentucky: two {party} candidates for {rid} on the November list")
                    nominee[(rid, party)] = r["Name"]
            general.append(dict(rid=rid, name=r["Name"], party=shown_party, code=code, pos=pos, write_in=write_in))

    def identify(race, name, party):
        """(incumbent, state_member_id, note) for one name: the seat's sitting member when the name fits, else a sitting
        legislator of the same party elsewhere when the name fits exactly one."""
        h = race["_holder"]
        if h is not None and person_fits(name, h):
            return 1, h["id"], None
        if not race["_chamber"]:
            return 0, None, None
        pool = [p for p in legs if bare(p["party"]) == bare(party) and person_fits(name, p)]
        if len(pool) == 1 and not (h is not None and pool[0]["id"] == h["id"]):
            return 0, pool[0]["id"], f"Serves today in the {chamber_words(pool[0])}."
        return 0, None, None

    cands = []
    for g in general:
        race = races[g["rid"]]
        inc, mid, n2 = identify(race, g["name"], g["party"])
        note = " ".join(x for x in (WRITE_IN if g["write_in"] else None, n2) if x) or None
        cands.append([g["rid"], "general", GENERAL, g["name"], g["party"], g["code"], g["pos"], inc, g["write_in"], None, None, None,
                      mid, SRC_LIST, note])

    # ---- which seats: the Senate's even half, the whole House
    sen = sorted(int(r["district"]) for r in races.values() if r["office_kind"] == "state_senate")
    house = sorted(int(r["district"]) for r in races.values() if r["office_kind"] == "state_house")
    if sen != list(range(2, SENATE_SEATS + 1, 2)):
        report.append(f"the Senate seats on the list are not the 19 even-numbered districts: {sen}")
    if house != list(range(1, HOUSE_SEATS + 1)):
        missing = sorted(set(range(1, HOUSE_SEATS + 1)) - set(house))
        report.append(f"House districts with no candidate on the list: {missing}")
    for rid, race in races.items():
        if not any(c[0] == rid and not c[8] for c in cands):
            report.append(f"{rid}: only declared write-ins on the list; nobody's name will be printed")

    # ---- primary fields: certified votes, county rows reconciled to Total Votes
    unreconciled, upset, stray, nfields, primary = [], [], [], 0, []
    for s in sections:
        okind = CERT_OFFICES[s["office"]]
        rid = f"2026-{STATE}-{'SS' if okind == 'state_senate' else 'SH'}{s['district']}"
        if s["party"] not in PRIMARY_CODE:
            raise SystemExit(f"Kentucky: a {s['party']} primary for {rid} in the certification; its election code is not set")
        summed = [sum(c[k] for c in s["counties"].values()) for k in range(len(s["names"]))]
        if summed != s["total"]:
            unreconciled.append(f"{rid} {s['party']}: county rows add to {summed}, Total Votes row says {s['total']}")
        if rid not in races:
            stray.append(f"{rid} {s['party']}")
            continue
        if len(s["names"]) < 2:
            continue
        nfields += 1
        race = races[rid]
        total = sum(s["total"])
        won = nominee.get((rid, s["party"]))
        top = max(range(len(s["names"])), key=lambda k: s["total"][k])
        if sorted(s["total"], reverse=True)[:2].count(s["total"][top]) > 1:
            report.append(f"{rid} {s['party']} primary: the top two are tied")
        picked = [k for k, nm in enumerate(s["names"]) if won and KY.same_person(nm, won)]
        if len(picked) > 1:
            raise SystemExit(f"Kentucky: {won} on the November list fits more than one name in the {rid} {s['party']} primary")
        winner = picked[0] if picked else top
        if winner != top:
            upset.append(f"{rid} {s['party']}")
        if not picked:
            report.append(f"{rid} {s['party']} primary: its top vote-getter is not the {s['party']} candidate on the November list "
                          f"({won or 'none'})")
        for k, printed in enumerate(s["names"]):
            name, caps = KY.shown(printed)
            inc, mid, n2 = identify(race, name, s["party"])
            notes = [CAPS] if caps else []
            if k == winner and not picked:
                notes.append(NOT_ON_LIST)
            if n2:
                notes.append(n2)
            primary.append([rid, f"primary-{PRIMARY_CODE[s['party']]}", PRIMARY, name, s["party"], party_code(s["party"]), None, inc, 0,
                            s["total"][k], round(100 * s["total"][k] / total, 1) if total else None,
                            "advanced" if k == winner else "lost", mid, SRC_CERT, " ".join(notes) or None])
    if stray:
        report.append(f"primary sections for seats not on the November list (not loaded): {stray}")
    report += [f"primary section does not add up: {u}" for u in unreconciled]
    if upset:
        report.append("the November nominee is not the primary's top vote-getter in " + ", ".join(upset))
    cands += primary

    seen = set()
    for c in cands:
        k = (c[0], c[1], c[3])
        if k in seen:
            raise SystemExit(f"Kentucky: {c[3]} is listed twice in {c[0]} {c[1]}")
        seen.add(k)

    # ---- the rest of the list, counted only
    skipped = []
    if home is None:
        report.append("the Candidate Filings home page could not be read, so the other offices on it were not counted")
    else:
        for pid, office, n in home:
            if pid in PAGES:
                live = counted.get(PAGES[pid][0], (None,))[0]
                if live is not None and live != n:
                    report.append(f"the home page counts {n} candidates for {office}; its page counts {live}")
            elif pid not in KY.OFFICE_PAGES:
                skipped.append(f"{office} ({n})")

    # ---- write: Kentucky's rows only, in one transaction
    cols = ["race_id", "state", "level", "office_kind", "office", "jurisdiction", "jurisdiction_id", "county_ids", "district", "seat",
            "special", "partisan", "holder_id", "holder_name", "holder_party", "election_date", "note"]
    race_rows = [tuple(r[c] for c in cols) for r in races.values()]
    nlist = sum(len(p["rows"]) for p in listed["pages"].values())
    src = [
        (SRC_LIST, STATE, "official candidate list", "Kentucky Secretary of State",
         "Candidate Filings with the Office of the Secretary of State, 2026 General Election: State Senator, State Representative, "
         "Justice of the Supreme Court and Judge of the Court of Appeals", KY.FILINGS + "12", "", listed["read"],
         hashlib.sha256("".join(p["sha256"] for p in listed["pages"].values()).encode()).hexdigest(), nlist,
         "Read from the pages " + ", ".join(f"{o} ({p['url']}, SHA-256 {p['sha256'][:16]}...)" for o, p in listed["pages"].items())
         + ". Name (first line), office, district/division and party only; the address and e-mail column is never read and the "
           "pages are not kept. Every group's count in its heading matched its rows. The list gives no ballot order (it goes by "
           f"district, then filing); its own order is kept. Withdrawn, deceased or disqualified, left off: {len(gone)}. Declared "
           f"write-in candidates (party printed \"Write-In\"): {len(write_ins)}. The sha256 here is of the pages' own hashes joined."
         + (f" Also on the list and not loaded here (local offices or a ballot question): {', '.join(skipped)}." if skipped else "")),
        (SRC_CERT, STATE, "official results", "Kentucky State Board of Elections",
         "Official 2026 Primary Election Results, May 19, 2026 (\"2026 Primary Results - Official Certification\"): State Senator "
         "and State Representative", KY.CERT_URL, KY.created(cpath), mtime(cpath), sha(cpath), sum(len(s["names"]) for s in sections),
         f"Linked from {KY.RESULTS_PAGE}. One section per contested party primary (an uncontested primary is not on the ballot): "
         f"{sum(1 for s in sections if s['office'] == 'State Senator')} State Senator and "
         f"{sum(1 for s in sections if s['office'] == 'State Representative')} State Representative sections. Statewide Total Votes "
         "stored, checked against the county rows. The certification has no write-in line, so shares are of the candidates' votes. "
         "The date given as published is the file's own creation date. "
         + ("Every section's county rows add up to its Total Votes row." if not unreconciled else "Did not add up: " + "; ".join(unreconciled) + ".")),
        (SRC_ROSTER, STATE, "roster", "Open States people project (CC0), as loaded into state_ky.sqlite",
         "Sitting Kentucky legislators", "https://github.com/openstates/people", "", mtime(roster_db), sha(roster_db), len(legs),
         "Who holds each legislative seat today (chamber and district); the roster carries no judges."),
    ]
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

    gen = [c for c in cands if c[1] == "general"]
    by = lambda kind, rows: sum(1 for c in rows if races[c[0]]["office_kind"] == kind)
    say(f"    Kentucky: {len(races)} races ({len(sen)} Senate, {len(house)} House, "
        f"{sum(1 for r in races.values() if r['level'] == 'court')} appellate court); {len(gen)} candidates on the November list "
        f"(Senate {by('state_senate', gen)}, House {by('state_house', gen)}, courts "
        f"{by('supreme_court', gen) + by('court_of_appeals', gen)}; {len(write_ins)} declared write-ins, {len(gone)} withdrawn left off); "
        f"{nfields} primary fields, {len(primary)} primary rows (Senate {by('state_senate', primary)}, House {by('state_house', primary)}), "
        "certified votes")
    for c in cands:
        if c[12]:
            say(f"      matched: {c[0]} {c[1]}: {c[3]} -> {c[12]}{' (holds this seat)' if c[7] else ''}")
    for line in report:
        say(f"      check: {line}")
    return len(gen)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m ballot.state_local_ky <database>")
    load(sys.argv[1])
