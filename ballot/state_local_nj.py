"""
ballot/state_local_nj.py - New Jersey's state races on the November 3, 2026 ballot, from the New Jersey Division of
Elections' own pages and files, into ballot_local_2026.sqlite (never ballot_2026.sqlite). New Jersey's rows only:
everything this loader writes is deleted and written again on each run.

What is on the ballot this year
-------------------------------
New Jersey elects its Legislature and its Governor in odd years: the General Assembly every two years (2025, next
2027), the Senate in 2023 and next in 2027, the Governor and Lieutenant Governor (one ticket) in 2025 and next in 2029.
No other statewide officer is elected (the Attorney General and the Secretary of State are appointed by the Governor,
and so are the judges). So no regular state race is on the November 3, 2026 ballot. What could be on it is a special
election for the rest of a legislative term, after a seat fell vacant; the Division lists such a contest with its own
label (in 2025, "State Senate - 35th Legislative District").

The loader does not assume there is none. It reads the Division's 2026 page and every certification and November list
it links, and stops (naming the file) if any of them carries a state office for the November 3 general election or the
June 2 primary, so a later filing cannot be missed quietly. Read on 2026-09-30, they carry none: every list and
certification is for the U.S. Senate or the U.S. House, the two 2026 special elections (February 5 and April 16) were
for the U.S. House in the 11th District, and the two state-office links in the page's source (General Assembly primary
results dated 2023, an amended certification for the 35th District) are commented out and answer 404. So this loader
stores no race and no candidate for New Jersey, and records every file it read, with the reason, in sl_sources.

Sources (all the Division's own, on the same site the federal loader, ballot/lists/nj.py, reads)
  * the "2026 Election Year Information" page (nj.gov/state/elections/election-information-2026.shtml): the labels of
    the files it shows are read and sorted into federal, state and other. The parts of the page's source that are
    commented out are set aside first; their links that name a state office are asked for only to confirm they are not
    live (a 404, or a file for another election), and are kept by address and office words only (one such label goes on
    to name a withdrawn candidate of an earlier year; that part is cut off).
  * every "Official General Election Candidates" list and every certification of nominees the page shows (the general
    election's of July 27 and its amendments, the primary's, the two special elections'): only the title lines of each
    page are read, the office ("Candidates for US Senate") and the election ("For GENERAL ELECTION 11/03/2026"), and the
    reading of a page stops at its table's headings. No candidate row is read by this loader (the federal loader reads
    the federal ones). The PDFs are read in memory and never written to disk.
  * the "2025 Election Year Information" page, labels only: which Senate seats went to the voters in 2025 for the rest
    of the term (a check on the roster below).
  * state_nj.sqlite (the Open States roster the state pages use): chamber, district and the date each sitting member
    took the seat, nothing else (not even names). Not an official record. It is a cross-check: a member seated after
    the last general election (November 4, 2025), or a senator seated mid-term whose seat was not on the 2025 ballot,
    would hold a seat that a special election could fill in November; the run lists any as a CHECK.

The privacy rule: from any list only office, district, name, party, ballot order, status and votes may be read, and
this loader reads less: office titles and election dates. The Division's "Candidates Email" lists are never fetched.
Nothing from a table row is turned into text, printed, logged, cached or stored; the cache (ballot_cache/nj/
nj_2026_sl_offices.json) holds link labels, addresses, the offices and elections each file's pages are for, page
counts and SHA-256 fingerprints.

sl_places: nothing, since there is no race to place.

Usage: python -m ballot.state_local_nj <database file> [cache folder]
"""

import collections
import datetime as dt
import hashlib
import html as H
import json
import os
import re
import sqlite3
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin

if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ballot.common import CACHE, HERE
from ballot.lists.nj import AGENCY, PAGE, PAGE_LINE, squash
from ballot.pdftext import PDF, join, rows as pdf_rows
from states import net

STATE, NAME = "NJ", "New Jersey"
GENERAL, PRIMARY = "2026-11-03", "2026-06-02"
PAGE_2025 = "https://www.nj.gov/state/elections/election-information-2025.shtml"
ROSTER = os.path.join(HERE, "state_nj.sqlite")
MAX_AGE_DAYS = 2                      # the 2026 page and its files are asked for afresh after this
SENATE_TERM, ASSEMBLY_TERM = "2024-01-09", "2026-01-13"      # the days the current terms began
LAST_GENERAL = "2025-11-04"

FILE = re.compile(r"\.(?:pdf|xlsx?|csv)$", re.I)
EMAIL = re.compile(r"\bE-?mails?\b", re.I)
STATE_OFFICE = re.compile(r"General Assembly|State Senate|Legislative District|\bGovernor\b|Lieutenant Governor", re.I)
FEDERAL_LABEL = re.compile(r"U\.S\. (?:Senate|House|President)|Congressional District|House of Representatives", re.I)
SCAN = re.compile(r"^Official General Election Candidates: |Certification of (?:\w+ )*Nominees|Certification of Nominees", re.I)
FEDERAL_OFFICE = re.compile(r"^(?:U\.?S\.? Senate|(?:U\.?S\.? )?House of Representatives|(?:U\.?S\.? )?President\b.*)$", re.I)
TITLE_START = re.compile(r"^(?:Candidates for |For\b|\d\d/\d\d/\d{4}\b|Official List|Page \d)")
FOR = re.compile(r"^For (?P<kind>(?:SPECIAL )?(?:GENERAL|PRIMARY)) ELECTION (?P<date>\d\d/\d\d/\d{4})\b")
SENATE_2025 = re.compile(r"State Senate\s*[-:]\s*(\d+)(?:st|nd|rd|th) Legislative District", re.I)
UPDATED = re.compile(r"Page Last Updated:\s*(\d\d)/(\d\d)/(\d\d)")

ODD_YEARS = ("New Jersey elects its Legislature and its Governor in odd years (the General Assembly in 2025 and next in "
             "2027, the Senate in 2023 and next in 2027, the Governor and Lieutenant Governor in 2025 and next in 2029); "
             "no other statewide officer is elected (the Attorney General and the Secretary of State are appointed, and so "
             "are the judges). So no regular state race is on the November 3, 2026 ballot; only a special election for the "
             "rest of a legislative term could be.")
TITLES_ONLY = ("Only each page's title lines were read (the office and the election the page is for); reading stopped at the "
               "table's headings, so no candidate row was read by this loader, and the PDF was not kept.")


def iso(mdy):
    m, d, y = mdy.split("/")
    return f"{y}-{m}-{d}"


def get(url, accept="*/*"):
    """One file, politely; asked at most three times in all (a 404 at once is final)."""
    for attempt in range(3):
        time.sleep(1.5)
        try:
            return net.get(url, accept=accept)
        except HTTPError as e:
            if e.code == 404 or attempt == 2:
                raise
        except (URLError, OSError):
            if attempt == 2:
                raise
        time.sleep(10 * (attempt + 1))


# ---------------------------------------------------------------- the Division's pages: labels only

def page_links(url):
    """(visible links, commented-out links, the page's own "last updated" date, SHA-256): each link (label, address) for
    a file (PDF, workbook, CSV). Commented-out parts of the source are set aside before the visible links are read."""
    raw = get(url, accept="text/html")
    page = raw.decode("utf-8", "replace")
    hidden_parts = re.findall(r"<!--.*?-->", page, re.S)
    visible = re.sub(r"<!--.*?-->", " ", page, flags=re.S)

    def links(html):
        out = []
        for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html, re.S | re.I):
            href = urljoin(url, H.unescape(m.group(1)))
            if FILE.search(href):
                label = squash(H.unescape(re.sub(r"<[^>]+>", " ", m.group(2))))
                if (label, href) not in out:
                    out.append((label, href))
        return out
    shown = links(visible)
    hidden = [x for x in links(" ".join(hidden_parts)) if x not in shown]
    u = UPDATED.search(re.sub(r"<[^>]+>", " ", visible))
    updated = f"20{u.group(3)}-{u.group(1)}-{u.group(2)}" if u else ""
    return shown, hidden, updated, hashlib.sha256(raw).hexdigest()


def kind_of(label):
    if EMAIL.search(label):
        return "email"                    # a list of candidates' e-mail addresses: never fetched
    if STATE_OFFICE.search(label):
        return "state"
    if FEDERAL_LABEL.search(label):
        return "federal"
    return "other"


# ---------------------------------------------------------------- a list or certification: title lines only

def titles(data, label):
    """For each page of one of the Division's candidate reports: the office and the election its title names, and the
    report's printed date. A row is joined into text only when its first piece begins a title line; the reading of a
    page stops at the table's headings ("Name ... Address ...") or its count of candidates per party."""
    if not data.startswith(b"%PDF"):
        raise SystemExit(f"New Jersey: {label} is not a PDF (it begins {data[:8]!r})")
    pdf = PDF(data)
    pages = []
    for n, (page, res) in enumerate(pdf.pages(), start=1):
        info = {"page": n, "office": None, "kind": None, "date": None, "printed": None}
        head = []
        for _y, rs in pdf_rows(pdf, page, res):
            rs = sorted(rs, key=lambda r: r[0])
            first = squash(rs[0][3])
            if first == "Name" or first.startswith("Candidate Totals"):
                break                                   # the table begins: nothing below its headings is read
            if not TITLE_START.match(first):
                continue                                # not a title line: never joined into text
            line = join(rs)
            if line.startswith("Candidates for "):
                info["office"] = line[len("Candidates for "):].strip()
                p = PAGE_LINE.match(" ".join(head))
                if p:
                    info["printed"] = iso(p.group("date") or p.group("date2"))
                continue
            f = FOR.match(line)
            if f:
                info["kind"], info["date"] = f.group("kind"), iso(f.group("date"))
                continue
            if info["office"] is None:
                head.append(line)
        if info["office"] and not (info["kind"] and info["date"]):
            raise SystemExit(f"New Jersey: {label}, page {n}: the title names an office but no election; the title lines changed")
        pages.append(info)
    offices = collections.Counter(p["office"] for p in pages if p["office"])
    elections = sorted({f"{p['kind']} {p['date']}" for p in pages if p["office"]})
    return {"pages": len(pages), "titled": sum(1 for p in pages if p["office"]), "offices": dict(offices),
            "elections": elections, "printed": sorted({p["printed"] for p in pages if p["printed"]}),
            "by_page": [[p["office"], p["kind"], p["date"]] for p in pages if p["office"]]}


def state_pages(scan):
    """The pages of a scanned report that name an office other than a federal one, for the November 3 general election
    or the June 2 primary (a special election on another day is not on the November ballot)."""
    return [(o, k, d) for o, k, d in scan["by_page"]
            if not FEDERAL_OFFICE.match(o or "") and d in (GENERAL, PRIMARY)]


# ---------------------------------------------------------------- read everything (or the copy kept)

def read_all(folder, say):
    """What the Division's pages and files say, kept as JSON (labels, addresses, offices, elections, counts and
    fingerprints only). Asked afresh when MAX_AGE_DAYS old; if the site cannot be reached, the copy kept is used."""
    path = os.path.join(folder, "nj_2026_sl_offices.json")
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < MAX_AGE_DAYS * 86400:
        return path, json.load(open(path, encoding="utf-8"))
    try:
        shown, hidden, updated, sha = page_links(PAGE)
        page = {"url": PAGE, "sha256": sha, "updated": updated,
                "links": [{"label": l, "url": u, "kind": kind_of(l)} for l, u in shown]}
        scans = []
        for label, url in shown:
            if kind_of(label) == "email" or not SCAN.search(label):
                continue
            data = get(url, accept="application/pdf")
            scans.append({"label": label, "url": url, "sha256": hashlib.sha256(data).hexdigest(), **titles(data, label)})
        checked_hidden = []
        for label, url in hidden:
            if kind_of(label) != "state":
                continue
            label = re.split(r"\s+-\s+", label)[0]      # the office only: a label can go on to name a candidate
            try:
                data = get(url, accept="application/pdf")
            except HTTPError as e:
                checked_hidden.append({"label": label, "url": url, "status": e.code})
                continue
            scan = titles(data, label) if data.startswith(b"%PDF") else {"by_page": [], "elections": []}
            checked_hidden.append({"label": label, "url": url, "status": 200, "elections": scan["elections"],
                                   "state_pages": len(state_pages(scan)) if scan["by_page"] else 0,
                                   "sha256": hashlib.sha256(data).hexdigest()})
        shown25, _h25, updated25, sha25 = page_links(PAGE_2025)
        page25 = {"url": PAGE_2025, "sha256": sha25, "updated": updated25,
                  "state_labels": [l for l, _u in shown25 if kind_of(l) == "state"],
                  "senate_specials": sorted({int(m.group(1)) for l, _u in shown25 for m in [SENATE_2025.search(l)] if m})}
    except (HTTPError, URLError, OSError) as e:
        if os.path.exists(path):
            say(f"      could not refresh the Division's pages ({e}); using the copy read earlier")
            return path, json.load(open(path, encoding="utf-8"))
        raise SystemExit(f"New Jersey: the Division's pages could not be read ({e})")
    keep = {"read": dt.date.today().isoformat(), "page": page, "scans": scans, "hidden": checked_hidden, "page_2025": page25}
    os.makedirs(folder, exist_ok=True)
    json.dump(keep, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return path, keep


# ---------------------------------------------------------------- the roster: chamber, district, date seated

def roster(path=ROSTER):
    """Sitting legislators as (id, chamber, district, date seated); names are not read."""
    if not os.path.exists(path):
        return []
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    out = con.execute("SELECT bioguide_id, chamber, district, term_start FROM legislators WHERE is_current = 1 AND state = ?",
                      (STATE,)).fetchall()
    con.close()
    return out


def roster_check(members, senate_2025):
    """(what the roster says, CHECK lines): seats a special election could fill in November, as far as the roster shows."""
    problems = []
    seats = collections.Counter(c for _i, c, _d, _s in members)
    if members and (seats.get("Senate", 0) != 40 or seats.get("House", 0) != 80):
        problems.append(f"the roster lists {seats.get('Senate', 0)} senators and {seats.get('House', 0)} members of the "
                        "General Assembly, not 40 and 80: a seat may be vacant; the Division's 2026 lists carry no contest for one")
    starts = collections.Counter((c, s) for _i, c, _d, s in members if s)
    for chamber, begun in (("Senate", SENATE_TERM), ("House", ASSEMBLY_TERM)):
        if members and starts.get((chamber, begun), 0) == 0:
            problems.append(f"no {chamber} member in the roster took a seat on {begun}, the day the term began; the dates "
                            "this check uses may be wrong")
    mid, undated = [], 0
    for _i, chamber, district, start in members:
        if not start:
            undated += 1
            continue
        if chamber == "Senate" and start > SENATE_TERM:
            if start <= LAST_GENERAL and str(district).isdigit() and int(district) in senate_2025:
                mid.append(f"Senate District {district} (seated {start}; the seat went to the voters in 2025 for the rest of the term)")
            else:
                problems.append(f"Senate District {district}: the roster's member took the seat on {start}, mid-term, and the "
                                "Division's 2025 page shows no special election for it; the 2026 lists carry no contest for it")
        if chamber == "House" and start > ASSEMBLY_TERM:
            problems.append(f"General Assembly District {district}: the roster's member took the seat on {start}, after the "
                            "term began; the Division's 2026 lists carry no contest for it")
    said = (f"{seats.get('Senate', 0)} senators and {seats.get('House', 0)} members of the General Assembly sitting; "
            + (f"seated mid-term: {'; '.join(mid)}; " if mid else "no senator seated mid-term; ")
            + ("no one seated after the Assembly's term began on January 13, 2026"
               if not any(c == "House" and s and s > ASSEMBLY_TERM for _i, c, _d, s in members) else "see the CHECK lines")
            + (f"; {undated} member(s) with no start date in the roster" if undated else ""))
    return said, problems


# ---------------------------------------------------------------- load

def load(db_path, say=print, cache=CACHE, roster_path=ROSTER):
    net.patient_lookups()
    folder = os.path.join(cache, "nj")
    path, got = read_all(folder, say)
    page, scans, hidden, page25 = got["page"], got["scans"], got["hidden"], got["page_2025"]
    problems = []

    # 1. the page: a visible file naming a state office would be a list this loader has not been taught to read
    by_kind = collections.Counter(l["kind"] for l in page["links"])
    state_links = [l["label"] for l in page["links"] if l["kind"] == "state"]
    if state_links:
        raise SystemExit(f"New Jersey: the Division's 2026 page now links {len(state_links)} file(s) for a state office "
                         f"({'; '.join(state_links)}); this loader does not read them yet: teach it the list")
    nov_lists = [s for s in scans if s["label"].lower().startswith("official general election candidates")]
    if not nov_lists:
        raise SystemExit("New Jersey: the Division's 2026 page shows no Official General Election Candidates list")

    # 2. the lists and certifications: every page for November 3 or June 2 must be a federal office
    for s in scans:
        if s["titled"] == 0:
            raise SystemExit(f"New Jersey: {s['label']}: no page with a title was read; the report's layout changed")
        found = state_pages(s)
        if found:
            raise SystemExit(f"New Jersey: {s['label']} carries a state office for {found[0][2]} ({found[0][0]}); "
                             "this loader does not read it yet: teach it the list")
    live = [h for h in hidden if h["status"] == 200 and h.get("state_pages")]
    if live:
        raise SystemExit(f"New Jersey: a link in the commented-out part of the 2026 page answers with a state office's list "
                         f"for 2026 ({live[0]['label']}); read it")
    for h in hidden:
        if h["status"] == 200:
            problems.append(f"a commented-out link answers ({h['label']}): {', '.join(h['elections']) or 'no titled page'}; "
                            "not a state office on the 2026 ballot")
    offices_nov = sorted({o for s in scans for o, _k, d in s["by_page"] if d == GENERAL})
    offices_pri = sorted({o for s in scans for o, _k, d in s["by_page"] if d == PRIMARY})
    specials = sorted({f"{o}, {k.title()} Election {d}" for s in scans for o, k, d in s["by_page"] if k.startswith("SPECIAL")})

    # 3. the roster: any seat a special election could be expected to fill
    members = roster(roster_path)
    said, roster_problems = roster_check(members, set(page25["senate_specials"]))
    problems += roster_problems

    # 4. the rows: sources only (no race, no candidate, no place)
    read_day = got["read"]
    sources = [
        ("nj-dos-2026-sl-page", STATE, "official election page", AGENCY, "2026 Election Year Information", page["url"],
         page["updated"], read_day, page["sha256"], len(page["links"]),
         f"The labels of the {len(page['links'])} files the page shows were read ({by_kind.get('federal', 0)} for a federal "
         f"office, {by_kind.get('state', 0)} for a state office, {by_kind.get('email', 0)} candidates' e-mail lists, never "
         f"fetched, {by_kind.get('other', 0)} other: turnout, results by county, audits, public questions, writs). The "
         "Official General Election Candidates it shows are for the U.S. Senate and the U.S. House only. Links in the "
         f"commented-out part of the page's source that name a state office: {len(hidden)}"
         + (" (" + "; ".join(f"{h['label']}: HTTP {h['status']}" for h in hidden) + ")" if hidden else "")
         + ", left over from earlier years' pages. " + ODD_YEARS + " No state race is stored for New Jersey."),
    ]
    for s in scans:
        slug = re.sub(r"[^a-z0-9]+", "-", os.path.basename(s["url"]).lower().rsplit(".", 1)[0]).strip("-")
        slug = re.sub(r"^2026-", "", slug)
        kind = "official candidate list" if s["label"].lower().startswith("official") else "official certification"
        offices = ", ".join(f"{o} ({n} pages)" for o, n in sorted(s["offices"].items()))
        sources.append((f"nj-dos-2026-sl-{slug}", STATE, kind, AGENCY, s["label"] + (f" (Official List, {s['printed'][-1]})" if s["printed"] else ""),
                        s["url"], s["printed"][-1] if s["printed"] else "", read_day, s["sha256"], 0,
                        f"{TITLES_ONLY} Pages: {s['pages']}, {s['titled']} with a title; offices: {offices}; election: "
                        f"{', '.join(s['elections'])}. No page is for a state office, so no row is stored from it."))
    sources.append(("nj-dos-2025-sl-page", STATE, "official election page", AGENCY, "2025 Election Year Information", page25["url"],
                    page25["updated"], read_day, page25["sha256"], len(page25["state_labels"]),
                    "Labels only, as a check on the roster: the 2025 files for a state office (Governor, the General Assembly "
                    "district by district, and the Senate for the rest of the term in "
                    + (", ".join(f"District {d}" for d in page25["senate_specials"]) or "no district")
                    + ") show which seats went to the voters in 2025."))
    if members:
        sources.append(("nj-openstates-roster", STATE, "roster", "Open States (people project, CC0)",
                        "New Jersey legislators serving now (state_nj.sqlite, from the Open States people project)",
                        "https://github.com/openstates/people", "", read_day, "", len(members),
                        "Chamber, district and the date each member took the seat only (names not read), to see whether any "
                        f"seat is held by someone a special election could replace in November: {said}. Not an official record."))

    con = sqlite3.connect(db_path)
    try:
        con.executescript(SCHEMA)
        with con:
            con.execute("DELETE FROM sl_candidates WHERE race_id IN (SELECT race_id FROM sl_races WHERE state = ?) OR race_id LIKE ?",
                        (STATE, f"2026-{STATE}-%"))
            con.execute("DELETE FROM sl_races WHERE state = ?", (STATE,))
            con.execute("DELETE FROM sl_sources WHERE state = ?", (STATE,))
            con.execute("DELETE FROM sl_places WHERE source_id LIKE 'nj-%'")
            con.executemany("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", sources)
    finally:
        con.close()

    say(f"    New Jersey: no state race on the November 3, 2026 ballot (0 races, 0 candidates). {len(scans)} lists and "
        f"certifications read by their page titles: November 3 offices {', '.join(offices_nov)}; June 2 primary offices "
        f"{', '.join(offices_pri) or 'none read'}; special elections {'; '.join(specials) or 'none'}. Roster: {said}. "
        "The Legislature and the Governor are elected in odd years (next 2027 and 2029).")
    for p in problems:
        say(f"      CHECK {p}")
    return {"races": 0, "candidates": 0, "scans": len(scans), "offices_nov": offices_nov, "offices_pri": offices_pri,
            "specials": specials, "problems": problems, "links": dict(by_kind), "hidden": len(hidden)}


SCHEMA = """
CREATE TABLE IF NOT EXISTS sl_races (race_id TEXT PRIMARY KEY, state TEXT NOT NULL, level TEXT NOT NULL, office_kind TEXT NOT NULL, office TEXT NOT NULL, jurisdiction TEXT, jurisdiction_id TEXT, county_ids TEXT, district TEXT, seat TEXT, special INTEGER NOT NULL DEFAULT 0, partisan INTEGER NOT NULL, holder_id TEXT, holder_name TEXT, holder_party TEXT, election_date TEXT NOT NULL, note TEXT);
CREATE TABLE IF NOT EXISTS sl_candidates (race_id TEXT NOT NULL, election TEXT NOT NULL, election_date TEXT, name TEXT NOT NULL, party TEXT, party_code TEXT, ballot_order INTEGER, incumbent INTEGER NOT NULL DEFAULT 0, write_in INTEGER NOT NULL DEFAULT 0, votes INTEGER, pct REAL, outcome TEXT, state_member_id TEXT, source_id TEXT, note TEXT, PRIMARY KEY (race_id, election, name));
CREATE TABLE IF NOT EXISTS sl_sources (source_id TEXT PRIMARY KEY, state TEXT, kind TEXT, agency TEXT, title TEXT, url TEXT, published TEXT, fetched TEXT, sha256 TEXT, rows INTEGER, note TEXT);
CREATE TABLE IF NOT EXISTS sl_places (kind TEXT NOT NULL, id TEXT NOT NULL, name TEXT NOT NULL, county_ids TEXT, source_id TEXT, PRIMARY KEY (kind, id));
"""


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("usage: python -m ballot.state_local_nj <database> [cache folder]")
    load(sys.argv[1], cache=sys.argv[2] if len(sys.argv) > 2 else CACHE)
