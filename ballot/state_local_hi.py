"""
ballot/state_local_hi.py - Hawaii's state races on the November 3, 2026 ballot: Governor and Lieutenant Governor (one
pair per party in November, nominated in separate August 8 primaries), the fifteen State Senate seats elected this year
(thirteen regular seats and two vacancies, Districts 18 and 19, for the rest of terms that end in 2028), all 51 House
seats, and the five Office of Hawaiian Affairs trustees (three at-large, the Maui and Oahu resident seats), with the
August 8 primaries that chose the nominees. Written into ballot_local_2026.sqlite (never ballot_2026.sqlite), Hawaii's
rows only.

    python ballot/state_local_hi.py <database file> [--cache <folder>] [--refresh]

Sources, all the State of Hawaii Office of Elections' own:

  * The "2026 Candidate Report" (olvr.hawaii.gov/Controls/CandidateFiling.aspx?elid=94, linked as "Candidate Report"
    from elections.hawaii.gov/candidates/candidate-reports/), the list the federal loader (ballot/lists/hi.py) reads for
    Congress. A Telerik grid of every candidate for every office in 2026, fifteen rows a page, read through the grid's own
    pager and counted against its "items" figure. Only four columns are taken, by their headings: Contests, Party, Ballot
    Name and Status. The grid also carries each candidate's legal name, mailing address, phone, e-mail, website and filing
    dates; those cells are never turned into text, printed or kept, and no page of the grid is written to disk. The kept
    columns of the state rows go to <cache>/hi_2026_candidate_report_state.json; the county and federal rows are only
    counted by contest and status. Status: "In General" is on the November ballot; "Elected After Primary" is declared
    elected after the primary, the only candidate left for the seat, and not on the November ballot (stored with outcome
    "unopposed" and a note, as other states' loaders store a seat settled early); "In Primary" was on the primary ballot
    and not nominated; "Issued" took out nomination papers and never filed them (never a candidate); "Withdrawn" and
    "Void" are left off; "Filed" is accepted only where there was no primary (the Senate District 18 vacancy, whose
    nonpartisan nominee the proclamation says is decided by lot), and is left off. Any other status stops the loader.
  * The certified results of the August 8, 2026 primary: the "Certified Text Files" Statewide Summary (summary.txt) and,
    as a control, the "Certified Reports" Statewide Summary (histatewide.pdf, "SUMMARY REPORT FINAL"), the files the federal
    loader keeps in ballot_cache/hi/ (fed.fetch_results checks that the results page still heads them Certified). Only the
    contest title, section (Contest Party), precinct counts, candidate name and mail, in-person and total votes are read.
    Checks: every state contest counted all its precincts; mail plus in-person make each total; each section's
    candidates are exactly the Candidate Report's candidates of that party for the office marked In General, Elected
    After Primary or In Primary; each party's leader is the party's nominee and everyone else is In Primary; the leading
    nonpartisan candidate is on the November ballot exactly when the Office's rule says so (at least 10 percent of every
    vote cast for the office, or as many votes as the party nominee with the fewest: the Office's page "Nonpartisan
    Candidates in Partisan Contests"); the six leading at-large OHA candidates are the six the report marks In General;
    every candidate's name and total appear together in the Final Summary Report. Hawaii's ballots have no write-in line.
  * The drawing results linked under "Drawings" on the results page (State Senate District 20 and State Representative
    District 43): both Republican primaries ended in ties in the certified count, and the Office decided each by lot on
    August 15 (Hawaii Revised Statutes section 11-157). Each file names the contest, the two tied candidates and the name
    drawn. The loader reads them whole (short statements, no contact details) and applies the drawing; where the
    Candidate Report has not caught up (it still marks both District 43 Republicans In General, though the drawing
    "selected" one "as the State Representative for District 43" and no one else was nominated), the drawing is followed
    and the difference is reported as a CHECK line.
  * The Contest Schedule (elections.hawaii.gov/voting/contest-schedule/): its 2026 table names every office up this year,
    with the State Senate seats (18* and 19*: two-year terms, the original terms expiring November 7, 2028), the House
    (1 - 51) and the OHA trustee seats. The races read from the Candidate Report must be exactly these. Only the table's
    cells are kept (<cache>/hi_2026_contest_schedule.json); the county rows are counted, not loaded.
  * The proclamations for the two Senate vacancies (elections.hawaii.gov/proclamations/: State Senate District 18 and
    State Senate District 19), read for how each seat is filled and when its term ends.
  * The Office's certified 2022 General Election Statewide Summary (files.hawaii.gov, summary.txt): only its Governor
    contest's title and candidate lines are read, to show that the November ballot carries one contest, "Governor and
    Lieutenant Governor", with each party's pair. The 2026 November rows follow that form: one row per pair, the
    candidate for Governor named first, under 2026-HI-GOV; 2026-HI-LTG carries the Lieutenant Governor primaries.
  * The Census Bureau's 2024 cartographic files (states_cache/census/): Hawaii's five counties (names and GEOIDs) and the
    State Senate and House district lines, to say which counties each district reaches. A district reaches a county when
    a point inside one of its pieces lies in the county, or a point inside one of the county's pieces lies in the district
    (so Kalawao, which sits inside a Molokai district, is counted).

Who holds each seat today comes from state_hi.sqlite (the Open States roster the state pages use): legislators serving
now, by chamber and district, and the officials table for the Governor and Lieutenant Governor. Only ids, names,
parties and districts are selected; its contact columns never are. It does not carry the OHA trustees. A candidate is
the incumbent only when the name fits exactly one sitting member of the same seat and that member fits only that
candidate.

Names are printed "FAMILY, Given" with the family name in capitals; they are turned round and the family name shown in
ordinary capitals (a sitting member or official with the capitals the roster gives the same words), and every row says
so. A suffix printed after the given name (", Jr.", ", III") follows the family name. The report gives no ballot
positions (its order within a contest is not alphabetical throughout), so ballot_order is left empty.

A field is a primary section with two candidates or more: primary-DEM, primary-REP, primary-GRE, primary-LIB, and
primary-NP (the nonpartisan section of a partisan contest, and the OHA at-large primary). pct is of the section's
candidates' votes (the Office's own percentages include blank and over votes).

The privacy rule: from every list only office, district, name, party, status and votes are read. Nothing else reaches
the cache, the database, a log or the screen.
"""

import collections
import csv
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
import urllib.parse
import zipfile
from http.cookiejar import CookieJar
from urllib.request import HTTPCookieProcessor, Request, build_opener

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ballot.common import CACHE, HERE, fold, name_parts, party_code          # noqa: E402
from ballot.lists import hi as fed                                          # noqa: E402
from ballot.lists.tx import proper                                          # noqa: E402
from ballot.match import fits                                               # noqa: E402
from ballot.pdftext import lines as pdf_lines                               # noqa: E402
from states import net                                                     # noqa: E402

STATE, NAME, FIPS = "HI", "Hawaii", "15"
GENERAL, PRIMARY = "2026-11-03", "2026-08-08"
DEFAULT_CACHE = os.path.join(CACHE, "hi")
ROSTER = os.path.join(HERE, "state_hi.sqlite")
CENSUS = os.path.join(HERE, "states_cache", "census")
COUNTY_ZIP = os.path.join(CENSUS, "cb_2024_us_county_500k.zip")
DISTRICT_ZIP = {"SS": os.path.join(CENSUS, "cb_2024_15_sldu_500k.zip"), "SH": os.path.join(CENSUS, "cb_2024_15_sldl_500k.zip")}
CENSUS_URL = "https://www2.census.gov/geo/tiger/GENZ2024/shp/"
REPORT, REPORT_LINK = fed.REPORT, fed.REPORT_LINK
RESULTS_PAGE = fed.RESULTS_PAGE
SCHEDULE = "https://elections.hawaii.gov/voting/contest-schedule/"
PROCLAMATIONS = {"18": "https://elections.hawaii.gov/state-senate-district-18-proclamation/",
                 "19": "https://elections.hawaii.gov/state-senate-19-proclamation-2/"}
PROCLAMATION_LIST = "https://elections.hawaii.gov/proclamations/"
RULE_PAGE = "https://elections.hawaii.gov/candidates/nonpartisan-candidates-in-partisan-contests/"
GOV_2022 = "https://files.hawaii.gov/elections/files/results/2022/general/summary.txt"
KEEP = ("Contests", "Party", "Ballot Name", "Status")
SUMMARY_KEEP = ("Contest ID", "Contest Title", "Contest Party", "Total Precincts", "Counted Precincts", "Candidate Name",
                "Mail Votes", "In-Person Votes", "Total Votes")
ON, EAP, LOST, NEVER, FILED, OFF = "In General", "Elected After Primary", "In Primary", "Issued", "Filed", ("Withdrawn", "Void")
NOMINATED = (ON, EAP)
SECTION = {"D": "DEM", "R": "REP", "G": "GRE", "L": "LIB", "N": "NP", "NON": "NP"}
REPORT_PARTY = {"DEMOCRATIC": "DEM", "REPUBLICAN": "REP", "GREEN": "GRE", "LIBERTARIAN": "LIB", "NONPARTISAN": "NP",
                "NONPARTISAN SPECIAL": "NP"}
LETTER = {"DEM": "D", "REP": "R", "GRE": "G", "LIB": "L", "NP": "N"}
ISLANDS = {"HAWAII": "Hawaii Island", "KAUAI": "Kauai", "MAUI": "Maui", "OAHU": "Oahu", "MOLOKAI": "Molokai", "LANAI": "Lanai"}
NONPARTISAN_OFFICE = "Nonpartisan office"
CAPS = "Hawaii's list prints family names in capitals; they are shown here in ordinary capitals."
NO_ORDER = "The Office of Elections' Candidate Report gives no ballot positions."
AGENCY = "State of Hawaii Office of Elections"
SRC = {"report": "hi-oe-2026-sl-candidate-report", "results": "hi-oe-2026-sl-primary-results", "pdf": "hi-oe-2026-sl-primary-summary-pdf",
       "schedule": "hi-oe-2026-contest-schedule", "gov2022": "hi-oe-2022-general-governor", "county": "hi-census-2024-counties",
       "SS": "hi-census-2024-sldu", "SH": "hi-census-2024-sldl", "roster": "hi-openstates-roster-2026"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS sl_races (race_id TEXT PRIMARY KEY, state TEXT NOT NULL, level TEXT NOT NULL, office_kind TEXT NOT NULL, office TEXT NOT NULL, jurisdiction TEXT, jurisdiction_id TEXT, county_ids TEXT, district TEXT, seat TEXT, special INTEGER NOT NULL DEFAULT 0, partisan INTEGER NOT NULL, holder_id TEXT, holder_name TEXT, holder_party TEXT, election_date TEXT NOT NULL, note TEXT);
CREATE TABLE IF NOT EXISTS sl_candidates (race_id TEXT NOT NULL, election TEXT NOT NULL, election_date TEXT, name TEXT NOT NULL, party TEXT, party_code TEXT, ballot_order INTEGER, incumbent INTEGER NOT NULL DEFAULT 0, write_in INTEGER NOT NULL DEFAULT 0, votes INTEGER, pct REAL, outcome TEXT, state_member_id TEXT, source_id TEXT, note TEXT, PRIMARY KEY (race_id, election, name));
CREATE TABLE IF NOT EXISTS sl_sources (source_id TEXT PRIMARY KEY, state TEXT, kind TEXT, agency TEXT, title TEXT, url TEXT, published TEXT, fetched TEXT, sha256 TEXT, rows INTEGER, note TEXT);
CREATE TABLE IF NOT EXISTS sl_places (kind TEXT NOT NULL, id TEXT NOT NULL, name TEXT NOT NULL, county_ids TEXT, source_id TEXT, PRIMARY KEY (kind, id));
"""

# the page's last check on every note (build_ballot_state_dev.py Guard, strict): a note that trips it would be dropped, so none may
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[A-Za-z]{2,}")
PHONE = re.compile(r"\(?\b\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}\b")
WEB = re.compile(r"https?://|\bwww\.|\b[\w-]+\.(?:com|org|net|us|gov|edu|info|biz)\b", re.I)
STREET = re.compile(r"\b\d{1,6}\s+(?:[NSEW]\.?\s+)?[A-Za-z0-9.' -]{1,40}?\s(?:St|Street|Ave|Avenue|Rd|Road|Blvd|Boulevard|Dr|Drive|Ln|Lane|Way|Ct|Court|"
                    r"Cir|Circle|Pkwy|Parkway|Hwy|Highway|Trl|Trail|Pl|Place|Ter|Terrace)\b\.?", re.I)
ZIP = re.compile(r"\b[A-Z]{2}\s+\d{5}\b|\b\d{5}-\d{4}\b")


def page_would_drop(text):
    return bool(text) and any(p.search(text) for p in (EMAIL, PHONE, WEB, STREET, ZIP))


def fresh(path, days):
    return os.path.exists(path) and os.path.getsize(path) > 0 and time.time() - os.path.getmtime(path) < days * 86400


def sha_file(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest() if path and os.path.exists(path) else ""


def day_of(path):
    return dt.datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d") if path and os.path.exists(path) else ""


def words_of(markup):
    return re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", markup, flags=re.S)))).strip()


# ---------------------------------------------------------------- offices

def office_of(title):
    """(kind, district or seat, vacancy) for a contest title of the Candidate Report or the results; 'federal' or 'county'
    for an office this loader only counts. Any other title stops the loader."""
    t = re.sub(r"\s+", " ", title or "").strip().upper()
    if t == "GOVERNOR":
        return ("GOV", None, False)
    if t == "LIEUTENANT GOVERNOR":
        return ("LTG", None, False)
    m = re.fullmatch(r"STATE (SENATOR|REPRESENTATIVE), DIST (\d+)( VACANCY)?", t)
    if m:
        return ("SS" if m.group(1) == "SENATOR" else "SH", str(int(m.group(2))), bool(m.group(3)))
    if t in ("OHA AT-LARGE TRUSTEE", "AT-LARGE TRUSTEE"):
        return ("OHA", "AL", False)
    m = re.fullmatch(r"(?:OHA )?(HAWAII|KAUAI|MAUI|OAHU|MOLOKAI|LANAI) RESIDENT TRUSTEE", t)
    if m:
        return ("OHA", m.group(1), False)
    if t.startswith("U.S."):
        return "federal"
    if re.match(r"(HAWAII|HONOLULU|KAUAI|MAUI|KALAWAO) (COUNCILMEMBER|MAYOR|PROSECUTING ATTORNEY)\b", t) or \
            re.fullmatch(r"(COUNCILMEMBER|MAYOR|PROSECUTING ATTORNEY)\b.*", t):
        return "county"
    raise SystemExit(f"Hawaii (state races): a contest title that is not read ({title!r}); look at the list again")


def race_id(key):
    kind, d, _v = key
    if kind in ("GOV", "LTG"):
        return f"2026-{STATE}-{kind}"
    if kind == "OHA":
        return f"2026-{STATE}-OHA-{d}"
    return f"2026-{STATE}-{kind}{d}"


def race_info(key):
    kind, d, vacancy = key
    base = {"race_id": race_id(key), "district": None, "seat": None, "special": int(vacancy), "partisan": 1, "chamber": None,
            "jurisdiction": NAME, "jurisdiction_id": FIPS, "level": "statewide", "county_ids": None, "notes": []}
    if kind == "GOV":
        base.update(office_kind="governor", office="Governor and Lieutenant Governor")
    elif kind == "LTG":
        base.update(office_kind="lieutenant_governor", office="Lieutenant Governor")
    elif kind == "OHA":
        base.update(office_kind="oha_trustee", partisan=0,
                    office="Office of Hawaiian Affairs Trustee, At-Large" if d == "AL" else f"Office of Hawaiian Affairs Trustee, {ISLANDS[d]} Resident",
                    seat="At-Large" if d == "AL" else f"Resident of {ISLANDS[d]}")
    else:
        senate = kind == "SS"
        base.update(level="legislature", office_kind="state_senate" if senate else "state_house",
                    office="State Senator" if senate else "State Representative", district=d,
                    jurisdiction=f"{'Senate' if senate else 'House'} District {d}", jurisdiction_id=f"{STATE}-{d}",
                    chamber="Senate" if senate else "House")
    return base


# ---------------------------------------------------------------- the Candidate Report (four columns only)

def grid_rows(page):
    """Every row of one page of the report's grid: the four kept cells only. The other cells are never turned into text."""
    heads = [fed.text(h) for h in re.findall(r'<th[^>]*class="rgHeader[^"]*"[^>]*>(.*?)</th>', page, re.S)]
    if not all(k in heads for k in KEEP) or len(set(heads)) != len(heads):
        raise SystemExit(f"Hawaii (state races): the Candidate Report's columns changed ({[h for h in heads if h in KEEP]})")
    idx = {k: heads.index(k) for k in KEEP}
    for tr in re.findall(r'<tr class="(?:rgRow|rgAltRow)"[^>]*>(.*?)</tr>', page, re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        if len(cells) != len(heads):
            raise SystemExit("Hawaii (state races): a Candidate Report row does not line up with the grid's headings")
        yield {k: fed.text(cells[i]) for k, i in idx.items()}


def read_report(path, say, refresh=False):
    """The state rows of the 2026 Candidate Report (four columns), every page read; kept on disk for two days."""
    if not refresh and fresh(path, 2):
        return json.load(open(path, encoding="utf-8"))
    opener = build_opener(HTTPCookieProcessor(CookieJar()))

    def fetch(fields=None):
        data = urllib.parse.urlencode(fields).encode() if fields is not None else None
        headers = {"User-Agent": net.UA, "Accept": "text/html"}
        if data:
            headers.update({"Content-Type": "application/x-www-form-urlencoded", "Referer": REPORT})
        with opener.open(Request(REPORT, data=data, headers=headers), timeout=120) as r:
            return r.read().decode("utf-8", "replace")

    page = fetch()
    chosen = re.search(r'<select[^>]*ddlElection[^>]*>.*?<option selected="selected" value="94">([^<]*)</option>', page, re.S)
    if not chosen or chosen.group(1).strip() != "2026 Candidate Report":
        raise SystemExit(f"Hawaii (state races): {REPORT} is no longer the 2026 Candidate Report")
    m = re.search(r"<strong>(\d+)</strong>\s*items in\s*<strong>(\d+)</strong>", page)
    if not m:
        raise SystemExit("Hawaii (state races): the Candidate Report no longer shows its row count")
    items, pages = int(m.group(1)), int(m.group(2))
    rows = list(grid_rows(page))
    for n in range(2, pages + 1):
        nxt = re.search(r'<input type="submit" name="([^"]+)"[^>]*?title="Next Page"[^>]*>', page)
        if not nxt or "return false" in nxt.group(0):
            raise SystemExit(f"Hawaii (state races): page {n - 1} of the Candidate Report has no Next Page button")
        fields = fed.form(page)
        fields.update({"__EVENTTARGET": "", "__EVENTARGUMENT": "", nxt.group(1): " "})
        time.sleep(1.5)
        page = fetch(fields)
        cur = re.search(r'class="rgCurrentPage"[^>]*>\s*<span>(\d+)</span>', page)
        if not cur or int(cur.group(1)) != n:
            raise SystemExit(f"Hawaii (state races): asked for page {n} of the Candidate Report and got {cur.group(1) if cur else 'no page'}")
        rows += list(grid_rows(page))
    del page
    if len(rows) != items:
        raise SystemExit(f"Hawaii (state races): the Candidate Report counts {items} rows; {len(rows)} were read")
    if len({tuple(r.values()) for r in rows}) != len(rows):
        raise SystemExit("Hawaii (state races): the Candidate Report gave the same row twice; its pager may have changed")
    state, others = [], collections.defaultdict(collections.Counter)
    for r in rows:
        o = office_of(r["Contests"])
        if isinstance(o, tuple):
            state.append(r)
        else:
            others[f"{o}: {r['Contests']}"][r["Status"]] += 1
    kept = {"title": "2026 Candidate Report", "url": REPORT, "items": items, "pages": pages, "fetched": dt.date.today().isoformat(),
            "columns": list(KEEP), "rows": state, "others": {k: dict(v) for k, v in sorted(others.items())}}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(kept, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    say(f"      2026 Candidate Report: {items} rows on {pages} pages, {len(state)} for state offices")
    return kept


# ---------------------------------------------------------------- the results page, drawings, schedule, proclamations

def results_block(say):
    """The 2026 block of the results page, after checking it still heads the primary's files Certified."""
    page = net.get(RESULTS_PAGE, accept="text/html").decode("utf-8", "replace")
    start = page.find('id="tab-2026"')
    block = page[start:page.find("To Top", start)] if start >= 0 else ""
    words = words_of(block)
    if "Primary Election August 8, 2026" not in words or "Certified Text Files" not in words or "Certified Reports" not in words:
        raise SystemExit("Hawaii (state races): the results page no longer heads the August 8, 2026 primary's files Certified")
    return block


def drawings(cache, say, refresh=False):
    """Each drawing result linked under 'Drawings' on the results page: contest, the tied names, the name drawn."""
    meta_path = os.path.join(cache, "hi_2026_drawings.json")
    if not refresh and fresh(meta_path, 30):
        links = json.load(open(meta_path, encoding="utf-8"))["links"]
    else:
        block = results_block(say)
        links = []
        for href, txt in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', block, re.S):
            label = words_of(txt)
            if "Drawing" in label:
                links.append({"label": label, "url": H.unescape(href)})
        json.dump({"page": RESULTS_PAGE, "links": links, "read": dt.date.today().isoformat()}, open(meta_path, "w", encoding="utf-8"), indent=1)
    out = []
    for ln in links:
        path = os.path.join(cache, "hi_2026_" + re.sub(r"[^a-z0-9]+", "_", os.path.basename(ln["url"]).lower()).strip("_").replace("_pdf", ".pdf"))
        net.download(ln["url"].replace(" ", "%20"), path, max_age_days=30, say=say)
        if open(path, "rb").read(5) != b"%PDF-":
            raise SystemExit(f"Hawaii (state races): {ln['url']} is not a PDF")
        text = " ".join(re.sub(r"\s+", " ", t) for _p, _y, t in pdf_lines(path))
        m = re.search(r"results for (State Senate|State Representative) District (\d+) (\w+)\s+contest resulted in a tie between (.+?) and (.+?)\.", text)
        w = re.search(r"The result of the drawing is: ([A-Z' .-]+, [^.]+?)(?: The drawing|$)", text)
        how = re.search(r"to determine which candidate will be selected as the (.+?)\. The result", text)
        if not (m and w and how):
            raise SystemExit(f"Hawaii (state races): the drawing result {os.path.basename(path)} is not in the form read")
        kind = "SS" if m.group(1) == "State Senate" else "SH"
        party = {"Republican": "REP", "Democratic": "DEM", "Green": "GRE", "Libertarian": "LIB", "Nonpartisan": "NP"}.get(m.group(3))
        if not party:
            raise SystemExit(f"Hawaii (state races): the drawing result {os.path.basename(path)} names a section that is not read ({m.group(3)})")
        out.append({"race": race_id((kind, str(int(m.group(2))), False)), "party": party, "tied": [m.group(4).strip(), m.group(5).strip()],
                    "winner": w.group(1).strip(), "selected_as": how.group(1).strip(), "label": ln["label"], "url": ln["url"], "path": path,
                    "date": (re.search(r"on \w+day, (\w+ \d+, \d{4})", text) or [None, ""])[1]})
    return out


def contest_schedule(cache, say, refresh=False):
    """The 2026 table of the Contest Schedule page, its cells only."""
    path = os.path.join(cache, "hi_2026_contest_schedule.json")
    if not refresh and fresh(path, 30):
        return json.load(open(path, encoding="utf-8")), path
    page = net.get(SCHEDULE, accept="text/html").decode("utf-8", "replace")
    page = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", page, flags=re.S)
    start = page.find("The following provides a schedule")
    table = re.search(r"<table.*?</table>", page[start:], re.S) if start >= 0 else None
    if not table or "2026" not in words_of(page[start:start + table.start()]):
        raise SystemExit(f"Hawaii (state races): {SCHEDULE} no longer opens with the 2026 table")
    rows = []
    for tr in re.findall(r"<tr.*?</tr>", table.group(0), re.S):
        rows.append([words_of(c) for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)])
    kept = {"url": SCHEDULE, "year": "2026", "fetched": dt.date.today().isoformat(), "rows": rows}
    json.dump(kept, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return kept, path


def schedule_expect(sched):
    """What the schedule's 2026 table says is up: senate seats (and which are starred), house seats, OHA seats, the rest."""
    exp = {"senate": set(), "senate_star": set(), "house": set(), "oha_at_large": 0, "oha_resident": set(), "gov": False,
           "county": [], "federal": [], "term_note": ""}
    group = None
    for cells in sched["rows"]:
        if not cells or cells[0] == "OFFICE":
            continue
        if len(cells) >= 2 and not any(cells[1:]):
            group = cells[0]
            continue
        office, seats, where = cells[0], cells[1], cells[2] if len(cells) > 2 else ""
        if group == "State":
            if office == "Governor and Lieutenant Governor":
                exp["gov"] = True
            elif office == "State Senate":
                for tok in re.findall(r"\d+\*?", where):
                    exp["senate"].add(tok.rstrip("*"))
                    if tok.endswith("*"):
                        exp["senate_star"].add(tok.rstrip("*"))
                if int(seats) != len(exp["senate"]):
                    raise SystemExit(f"Hawaii (state races): the Contest Schedule counts {seats} Senate seats and lists {len(exp['senate'])}")
                star = re.search(r"\*\s*(.+)$", cells[3] if len(cells) > 3 else "")
                exp["term_note"] = star.group(1).strip() if star else ""
            elif office == "State House of Representatives":
                m = re.fullmatch(r"(\d+)\s*-\s*(\d+)", where)
                if not m:
                    raise SystemExit(f"Hawaii (state races): the Contest Schedule's House row is not read ({where!r})")
                exp["house"] = {str(i) for i in range(int(m.group(1)), int(m.group(2)) + 1)}
                if int(seats) != len(exp["house"]):
                    raise SystemExit("Hawaii (state races): the Contest Schedule's House count and range differ")
            elif office == "Office of Hawaiian Affairs Trustee":
                m = re.search(r"At-Large \((\d+) seats?\)", where)
                exp["oha_at_large"] = int(m.group(1)) if m else 0
                exp["oha_resident"] = {x.upper() for x in re.findall(r"Resident of (\w+)", where)}
                if int(seats) != exp["oha_at_large"] + len(exp["oha_resident"]):
                    raise SystemExit("Hawaii (state races): the Contest Schedule's OHA seat count does not add up")
            else:
                raise SystemExit(f"Hawaii (state races): the Contest Schedule names a state office that is not read ({office!r})")
        elif group == "Federal":
            exp["federal"].append(f"{office} ({where})")
        else:
            exp["county"].append(f"{group}: {office}, {seats} ({where})")
    return exp


def proclamation(district, cache, say, refresh=False):
    """The vacancy proclamation for a Senate district: kept whole (a signed notice, no contact details), read for its facts."""
    meta = os.path.join(cache, f"hi_2026_sd{district}_proclamation.json")
    if not refresh and fresh(meta, 30):
        info = json.load(open(meta, encoding="utf-8"))
    else:
        page = net.get(PROCLAMATIONS[district], accept="text/html").decode("utf-8", "replace")
        pdfs = sorted({H.unescape(h) for h in re.findall(r'href="([^"]+\.pdf)"', page) if re.search(rf"Senate-{district}-Proclamation", h)})
        if len(pdfs) != 1:
            raise SystemExit(f"Hawaii (state races): the State Senate District {district} proclamation page no longer links one proclamation")
        info = {"page": PROCLAMATIONS[district], "url": pdfs[0], "read": dt.date.today().isoformat()}
        json.dump(info, open(meta, "w", encoding="utf-8"), indent=1)
    path = os.path.join(cache, f"hi_2026_sd{district}_proclamation.pdf")
    net.download(info["url"], path, max_age_days=30, say=say)
    text = re.sub(r"\s+", " ", " ".join(t for _p, _y, t in pdf_lines(path))).replace(" .", ".")
    ords = {"18": "Eighteenth", "19": "Nineteenth"}
    if "PROCLAMATION" not in text or f"State Senate, {ords[district]} District" not in text:
        raise SystemExit(f"Hawaii (state races): the District {district} proclamation is not in the form read")
    who = re.search(r"resignation of the Honorable (.+?), from the", text)
    end = re.search(r"unexpired term which ends on (\w+ \d+, \d{4})", text)
    signed = re.search(r"this (\d+)(?:st|nd|rd|th) day of (\w+) (\d{4})", text)
    info.update({"path": path, "resigned": who.group(1) if who else "", "term_end": end.group(1) if end else "",
                 "signed": f"{signed.group(2)} {signed.group(1)}, {signed.group(3)}" if signed else "",
                 "primary": "Primary Election will be held on Saturday, August 8, 2026" in text,
                 "committees": "nominated by the county committees of the parties" in text, "lot": "decided by lot" in text})
    return info


def governor_2022(cache, say, refresh=False):
    """The Governor contest of the certified 2022 general summary: its title and the candidates' lines only."""
    path = os.path.join(cache, "hi_2022_general_governor.json")
    if not refresh and fresh(path, 365):
        return json.load(open(path, encoding="utf-8")), path
    raw = net.get(GOV_2022)
    text = raw.decode("utf-16-le" if raw[1:2] == b"\x00" else "utf-8-sig").lstrip("﻿")
    table = list(csv.reader(io.StringIO(text.replace("\r\n", "\n")), delimiter="\t" if "\t" in text.splitlines()[1] else ","))
    heads = [h.lstrip("#").strip() for h in table[1]]
    if "Contest Title" not in heads or "Candidate Name" not in heads:
        raise SystemExit("Hawaii (state races): the 2022 general summary's columns are not the ones read")
    ti, ci = heads.index("Contest Title"), heads.index("Candidate Name")
    rows = [{"contest": r[ti], "candidate": re.sub(r"\s+", " ", r[ci]).strip()} for r in table[2:] if len(r) > ci and "Governor" in r[ti]]
    kept = {"url": GOV_2022, "fetched": dt.date.today().isoformat(), "sha256": hashlib.sha256(raw).hexdigest(), "rows": rows}
    json.dump(kept, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return kept, path


# ---------------------------------------------------------------- the certified primary

def read_summary(path):
    """{(race, code): [(name as printed, total)]} for every state contest of the certified summary, plus counts of the rest."""
    with open(path, encoding="utf-8-sig", newline="") as fh:
        table = list(csv.reader(fh, delimiter="\t"))
    heads = [h.lstrip("#").strip() for h in table[1]]
    if not all(k in heads for k in SUMMARY_KEEP):
        raise SystemExit(f"Hawaii (state races): summary.txt's columns changed ({[h for h in heads if h in SUMMARY_KEEP]})")
    idx = {k: heads.index(k) for k in SUMMARY_KEEP}
    votes, titles, seen, other = collections.OrderedDict(), {}, {}, collections.Counter()
    for r in table[2:]:
        if not any(c.strip() for c in r):
            continue
        if len(r) < len(heads):
            raise SystemExit("Hawaii (state races): a line of summary.txt is shorter than its heading")
        c = {k: r[i].strip() for k, i in idx.items()}
        o = office_of(c["Contest Title"])
        if not isinstance(o, tuple):
            other[o] += 1
            continue
        if c["Contest Party"] not in SECTION:
            raise SystemExit(f"Hawaii (state races): a section that is not read ({c['Contest Title']} - {c['Contest Party']})")
        if (o[0] == "OHA") != (c["Contest Party"] == "NON"):
            raise SystemExit(f"Hawaii (state races): {c['Contest Title']} is in section {c['Contest Party']}, not the one expected")
        key = (race_id(o), SECTION[c["Contest Party"]])
        if seen.setdefault(c["Contest ID"], key) != key:
            raise SystemExit(f"Hawaii (state races): summary.txt contest {c['Contest ID']} names two offices")
        if c["Counted Precincts"] != c["Total Precincts"]:
            raise SystemExit(f"Hawaii (state races): {c['Contest Title']} ({c['Contest Party']}) counted {c['Counted Precincts']} of {c['Total Precincts']} precincts")
        mail, person, total = int(c["Mail Votes"]), int(c["In-Person Votes"]), int(c["Total Votes"])
        if mail + person != total:
            raise SystemExit(f"Hawaii (state races): a candidate's mail and in-person votes do not make the total in {c['Contest Title']}")
        if re.search(r"write[- ]?in", c["Candidate Name"], re.I):
            raise SystemExit(f"Hawaii (state races): summary.txt reports a write-in line for {c['Contest Title']}")
        votes.setdefault(key, []).append((re.sub(r"\s+", " ", c["Candidate Name"]), total))
        titles[key] = (c["Contest Title"], c["Contest Party"], o)
    return votes, titles, other


def pdf_control(path, votes, titles):
    """Every state candidate's name beside the same total in the Final Summary Report; returns its print date and the
    at-large trustee count to vote for."""
    text_lines = [re.sub(r"\s+", " ", t) for _p, _y, t in pdf_lines(path)]
    head = "\n".join(text_lines[:8])
    for words in ("PRIMARY ELECTION 2026 - State of Hawaii - Statewide", "August 8, 2026", "SUMMARY REPORT", "FINAL"):
        if words not in head:
            raise SystemExit(f"Hawaii (state races): histatewide.pdf's heading no longer says {words!r}")
    whole = "\n".join(text_lines)
    for key, field in votes.items():
        title, section, o = titles[key]
        heading = title if o[0] == "OHA" else f"{title} - {section}"
        if heading not in whole:
            raise SystemExit(f"Hawaii (state races): histatewide.pdf has no heading {heading!r}")
        for name, v in field:
            if f"{name} {v:,}" not in whole:
                raise SystemExit(f"Hawaii (state races): histatewide.pdf does not print a {title} ({section}) candidate beside {v:,} votes")
    seats = None                     # the report is laid out in columns: the count follows its heading within a few lines
    for i, t in enumerate(text_lines):
        if t == "At-Large Trustee":
            near = [re.fullmatch(r"Number To Vote For: (\d+)", x) for x in text_lines[i + 1:i + 6]]
            near = [m for m in near if m]
            seats = int(near[0].group(1)) if near else None
    m = re.search(r"Printed on: (\d\d)/(\d\d)/(\d{4})", head)
    return (f"{m.group(3)}-{m.group(1)}-{m.group(2)}" if m else ""), seats


# ---------------------------------------------------------------- counties and district lines

def _shapes(zpath, keep):
    import shapefile                                   # pyshp
    z = zipfile.ZipFile(zpath)
    base = next(n[:-4] for n in z.namelist() if n.endswith(".shp"))
    rdr = shapefile.Reader(shp=io.BytesIO(z.read(base + ".shp")), dbf=io.BytesIO(z.read(base + ".dbf")),
                           shx=io.BytesIO(z.read(base + ".shx")))
    fields = [f[0] for f in rdr.fields[1:]]
    for sr in rdr.iterShapeRecords():
        rec = dict(zip(fields, sr.record))
        if keep(rec):
            pts, parts = sr.shape.points, list(sr.shape.parts) + [len(sr.shape.points)]
            yield rec, [pts[parts[i]:parts[i + 1]] for i in range(len(parts) - 1)]


def _area(ring):
    return sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1])) / 2


def _crossings(y, rings):
    xs = []
    for ring in rings:
        for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
            if (y1 > y) != (y2 > y):
                xs.append(x1 + (y - y1) * (x2 - x1) / (y2 - y1))
    return sorted(xs)


def _inside(pt, rings):
    x, y = pt
    return sum(1 for cx in _crossings(y, rings) if cx > x) % 2 == 1


def _interior_points(rings):
    """One point well inside each outer ring (clockwise in a shapefile), holes respected."""
    out = []
    for ring in rings:
        if _area(ring) >= 0:
            continue
        ys = [p[1] for p in ring]
        best = None
        for f in (0.5, 0.35, 0.65, 0.2, 0.8):
            y = min(ys) + (max(ys) - min(ys)) * f
            xs = _crossings(y, rings)
            for a, b in zip(xs[0::2], xs[1::2]):
                mid = ((a + b) / 2, y)
                if _inside(mid, [ring]) and (best is None or b - a > best[0]):
                    best = (b - a, mid)
            if best:
                break
        if best:
            out.append(best[1])
    return out


def geography():
    """Hawaii's counties {GEOID: name} and, for each chamber, {district: [county GEOIDs it reaches]}."""
    counties = {str(r["GEOID"]): (str(r.get("NAMELSAD") or r["NAME"]), rings)
                for r, rings in _shapes(COUNTY_ZIP, lambda rec: str(rec.get("STATEFP")) == FIPS)}
    if len(counties) != 5:
        raise SystemExit(f"Hawaii (state races): the Census county file lists {len(counties)} Hawaii counties, not 5")
    cpts = {g: _interior_points(rings) for g, (_n, rings) in counties.items()}
    reach = {}
    for kind, zpath in DISTRICT_ZIP.items():
        col = "SLDUST" if kind == "SS" else "SLDLST"
        out = {}
        for rec, rings in _shapes(zpath, lambda rec: str(rec.get("STATEFP")) == FIPS):
            d = str(int(rec[col]))
            dpts = _interior_points(rings)
            hit = {g for g, (_n, crings) in counties.items() if any(_inside(p, crings) for p in dpts)}
            hit |= {g for g in counties if any(_inside(p, rings) for p in cpts[g])}
            out[d] = sorted(hit)
        reach[kind] = out
    return {g: n for g, (n, _r) in counties.items()}, reach


# ---------------------------------------------------------------- the roster

def roster(path=ROSTER):
    """Sitting legislators and statewide officials: id, names, party and district only."""
    if not os.path.exists(path):
        return [], [], ""
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    members = [dict(zip(("id", "chamber", "district", "first", "last", "full", "party", "other"), r)) for r in con.execute(
        "SELECT bioguide_id, chamber, district, first_name, last_name, official_full, party_name, other_names FROM legislators "
        "WHERE is_current = 1")]
    officials = [dict(zip(("id", "office", "first", "last", "full", "party"), r)) for r in con.execute(
        "SELECT bioguide_id, office, first_name, last_name, official_full, party_name FROM officials")]
    as_of = (con.execute("SELECT MAX(updated_at) FROM legislators").fetchone()[0] or "")[:10]
    con.close()
    for m in members:
        m["district"] = str(int(m["district"])) if str(m["district"] or "").isdigit() else str(m["district"] or "")
    return members, officials, as_of


def person_fits(printed, p):
    parts = name_parts(printed)
    forms = [p.get("full") or ""] + [f.strip() for f in (p.get("other") or "").split(";") if f.strip()]
    return (fits(parts, (fold(p["first"] or "").split(), " ".join(fold(p["last"] or "").split())))
            or any(fits(parts, name_parts(f)) for f in forms if f))


def split_printed(printed):
    """'IHARA, Les, Jr.' -> ('IHARA', 'Les', ['Jr.'])."""
    family, _, rest = re.sub(r"\s+", " ", printed).partition(",")
    parts = [p.strip() for p in rest.split(",") if p.strip()]
    if not family.strip() or not parts:
        raise SystemExit("Hawaii (state races): a name not printed 'FAMILY, Given' (the name is not shown)")
    return family.strip(), parts[0], parts[1:]


# ---------------------------------------------------------------- load

def source_row(source_id, kind, agency, title, url, published, fetched, sha256, rows, note):
    return (source_id, STATE, kind, agency, title, url, published or "", fetched or "", sha256 or "", rows, note)


def load(db_path, say=print, cache=DEFAULT_CACHE, fed_cache=None, roster_path=ROSTER, refresh=False):
    if os.path.abspath(db_path) == os.path.abspath(os.path.join(HERE, "ballot_2026.sqlite")):
        raise SystemExit("Hawaii (state races): this loader never writes ballot_2026.sqlite")
    net.patient_lookups()
    os.makedirs(cache, exist_ok=True)
    fed_folder = fed_cache or os.path.join(CACHE, "hi")
    report_path = os.path.join(cache, "hi_2026_candidate_report_state.json")
    report = read_report(report_path, say, refresh)
    res_paths, res_meta = fed.fetch_results(fed_folder, say)            # the files (and check) the federal loader keeps
    votes, titles, other_contests = read_summary(res_paths["summary"])
    printed_on, at_large_seats = pdf_control(res_paths["pdf"], votes, titles)
    draws = drawings(cache, say, refresh)
    sched, sched_path = contest_schedule(cache, say, refresh)
    exp = schedule_expect(sched)
    procs = {d: proclamation(d, cache, say, refresh) for d in PROCLAMATIONS}
    gov22, gov22_path = governor_2022(cache, say, refresh)
    counties, reach = geography()
    members, officials, roster_as_of = roster(roster_path)
    problems, notes_out = [], []

    everyone = members + officials
    fixed = {}
    for p in everyone:
        for form in (p["full"], f"{p['first']} {p['last']}"):
            if form:
                fixed.setdefault(fold(form), p["full"] or form)

    def shown(printed):
        family, given, tail = split_printed(printed)
        name = " ".join([given, proper(family)] + tail)
        return fixed.get(fold(name), name)

    # ---- races, from the report's state rows, checked against the Contest Schedule
    races = collections.OrderedDict()
    rows_by_race = collections.defaultdict(list)
    statuses = collections.Counter()
    for r in report["rows"]:
        key = office_of(r["Contests"])
        rid = race_id(key)
        if rid not in races:
            races[rid] = race_info(key)
        elif races[rid]["special"] != int(key[2]):
            raise SystemExit(f"Hawaii (state races): {rid} is listed both as a regular seat and as a vacancy; the two need their own ids")
        if r["Party"] not in REPORT_PARTY:
            raise SystemExit(f"Hawaii (state races): a party that is not read ({r['Party']!r}, {r['Contests']})")
        if (r["Party"] == "NONPARTISAN SPECIAL") != (key[0] == "OHA"):
            raise SystemExit(f"Hawaii (state races): {r['Contests']} has a {r['Party']} row")
        if r["Status"] not in (ON, EAP, LOST, NEVER, FILED, *OFF):
            raise SystemExit(f"Hawaii (state races): a status that is not read ({r['Status']!r}, {r['Contests']})")
        statuses[r["Status"]] += 1
        rows_by_race[rid].append(dict(r, code=REPORT_PARTY[r["Party"]]))
    senate = {r["district"] for r in races.values() if r["office_kind"] == "state_senate"}
    house = {r["district"] for r in races.values() if r["office_kind"] == "state_house"}
    if senate != exp["senate"]:
        problems.append(f"the Candidate Report's Senate seats ({sorted(senate, key=int)}) are not the Contest Schedule's ({sorted(exp['senate'], key=int)})")
    if {r["district"] for r in races.values() if r["office_kind"] == "state_senate" and r["special"]} != exp["senate_star"]:
        problems.append("the Candidate Report's Senate vacancies are not the Contest Schedule's starred seats")
    if house != exp["house"]:
        problems.append(f"the Candidate Report's House seats are not the Contest Schedule's 1 - 51 ({len(house)} read)")
    oha = {r["race_id"].rsplit("-", 1)[1] for r in races.values() if r["office_kind"] == "oha_trustee"}
    if oha != {"AL"} | exp["oha_resident"] or exp["oha_at_large"] != at_large_seats:
        problems.append(f"the OHA seats read ({sorted(oha)}, {at_large_seats} at large) are not the Contest Schedule's")
    if not exp["gov"] or f"2026-{STATE}-GOV" not in races or f"2026-{STATE}-LTG" not in races:
        problems.append("Governor and Lieutenant Governor are not both on the Candidate Report and the Contest Schedule")
    for rid, rr in rows_by_race.items():
        if any(x["Status"] == FILED for x in rr) and (races[rid]["special"] == 0 or any(k[0] == rid for k in votes)):
            raise SystemExit(f"Hawaii (state races): {rid} has a row still marked Filed after its primary")

    # ---- the primary: each section's candidates are the report's, and who won
    by_name = {rid: {(x["code"], fold(x["Ballot Name"])): x for x in rr if x["Status"] in (ON, EAP, LOST)} for rid, rr in rows_by_race.items()}
    winners, fields, drawn = {}, [], {}
    office_total = collections.Counter()
    for (rid, code), field in votes.items():
        office_total[rid] += sum(v for _n, v in field)
    for (rid, code), field in votes.items():
        listed = {f for (c, f) in by_name.get(rid, {}) if c == code}
        if {fold(n) for n, _v in field} != listed:
            raise SystemExit(f"Hawaii (state races): the results' {rid} {code} candidates are not the Candidate Report's")
    for rid in {k[0] for k in votes}:
        listed_sections = {c for (c, _f) in by_name.get(rid, {})}
        if listed_sections - {k[1] for k in votes if k[0] == rid}:
            raise SystemExit(f"Hawaii (state races): {rid} has candidates on the report in a section the results do not have")
    for (rid, code), field in votes.items():
        if code == "NP" and races[rid]["partisan"]:
            continue                                       # worked out below, after the party nominees
        if races[rid]["office_kind"] == "oha_trustee":
            n_on = sum(1 for x in rows_by_race[rid] if x["Status"] in NOMINATED)
            ranked = sorted(field, key=lambda nv: -nv[1])
            if n_on < len(ranked) and ranked[n_on - 1][1] == ranked[n_on][1]:
                raise SystemExit(f"Hawaii (state races): {rid} is tied at the last place to November")
            winners[(rid, code)] = [n for n, _v in ranked[:n_on]]
            continue
        top = max(v for _n, v in field)
        leaders = [n for n, v in field if v == top]
        if len(leaders) > 1:
            d = [x for x in draws if x["race"] == rid and x["party"] == code]
            if len(d) != 1:
                raise SystemExit(f"Hawaii (state races): the {rid} {code} section is tied at the top and no drawing result settles it")
            d = d[0]
            fit = {t: [n for n in leaders if fits(name_parts(n), name_parts(t))] for t in d["tied"]}
            if any(len(v) != 1 for v in fit.values()) or {v[0] for v in fit.values()} != set(leaders):
                raise SystemExit(f"Hawaii (state races): the {rid} drawing names other tied candidates than the certified count")
            win = [n for n in leaders if fold(n) == fold(d["winner"])]
            if len(win) != 1:
                raise SystemExit(f"Hawaii (state races): the {rid} drawing's result is not one of the tied candidates")
            winners[(rid, code)] = win
            drawn[(rid, code)] = d
        else:
            winners[(rid, code)] = leaders
    np_notes = {}
    for (rid, code), field in votes.items():
        if not (code == "NP" and races[rid]["partisan"]):
            continue
        top = max(v for _n, v in field)
        leaders = [n for n, v in field if v == top]
        if len(leaders) > 1:
            raise SystemExit(f"Hawaii (state races): the {rid} nonpartisan section is tied at the top")
        partisan = sorted((v, n) for k, w in winners.items() if k[0] == rid and k[1] != "NP"
                          for n, v in votes[k] if n in w)
        lowest = partisan[0] if partisan else None
        qualifies = top >= 0.10 * office_total[rid] or (lowest is not None and top >= lowest[0])
        marked = by_name[rid][("NP", fold(leaders[0]))]["Status"]
        if qualifies != (marked in NOMINATED):
            raise SystemExit(f"Hawaii (state races): the {rid} nonpartisan leader's qualifying and the report's mark ({marked}) disagree")
        winners[(rid, code)] = leaders if qualifies else []
        if not qualifies:
            np_notes[(rid, leaders[0])] = (f"Led the nonpartisan section but did not qualify for November: a nonpartisan candidate needs at least 10 "
                                           f"percent of the votes cast for the office ({office_total[rid]:,} in all) or as many votes as the party "
                                           f"nominee with the fewest ({shown(lowest[1])}, {lowest[0]:,})." if lowest else
                                           "Led the nonpartisan section but did not qualify for November (10 percent of the votes cast for the office).")

    # ---- the November list: the report's nominees, drawings applied, checked against the results
    general = collections.defaultdict(list)          # race -> report rows on the November list (or declared elected)
    losers_marked_on = []
    for rid, rr in rows_by_race.items():
        for x in rr:
            if x["Status"] not in NOMINATED:
                continue
            d = drawn.get((rid, x["code"]))
            if d and fold(x["Ballot Name"]) not in {fold(n) for n in winners[(rid, x["code"])]}:
                losers_marked_on.append((rid, x))
                continue
            general[rid].append(x)
    for rid, x in losers_marked_on:
        d = drawn[(rid, x["code"])]
        problems.append(f"{rid}: the Candidate Report still marks {shown(x['Ballot Name'])} {x['Status']}, though the Office's drawing of "
                        f"{d['date'] or 'August 15'} chose {shown(d['winner'])}; loaded as the drawing decided")
    for (rid, code), w in winners.items():
        got = sorted(fold(x["Ballot Name"]) for x in general[rid] if x["code"] == code)
        if got != sorted(fold(n) for n in w):
            problems.append(f"{rid} {code}: the primary's winners and the Candidate Report's nominees differ")
    for rid, rr in rows_by_race.items():
        for x in rr:
            if x["Status"] == LOST and not any(k[0] == rid and k[1] == x["code"] for k in votes):
                problems.append(f"{rid}: a candidate marked In Primary has no section in the results")

    # ---- holders and incumbents
    def holders(rid):
        r = races[rid]
        if r["chamber"]:
            return [m for m in members if m["chamber"] == r["chamber"] and m["district"] == r["district"]]
        want = {"governor": "governor", "lieutenant_governor": "lt_governor"}.get(r["office_kind"])
        return [o for o in officials if o["office"] == want] if want else []

    def identify(rid, names):
        """{printed name: holder} for the names that fit exactly one holder, where that holder fits only that name."""
        out = {}
        for h in holders(rid):
            hits = [n for n in names if person_fits(n, h)]
            if len(hits) == 1 and sum(1 for hh in holders(rid) if person_fits(hits[0], hh)) == 1:
                out[hits[0]] = h
        return out

    cands, incumbents, settled = [], 0, []
    party_word = {"DEM": "Democratic", "REP": "Republican", "GRE": "Green", "LIB": "Libertarian", "NP": "Nonpartisan"}

    def party_of(rid, code):
        return NONPARTISAN_OFFICE if not races[rid]["partisan"] else party_word[code]

    def pcode(rid, code):
        return "N" if not races[rid]["partisan"] else party_code(party_word[code])

    # Governor and Lieutenant Governor: one pair per party in November
    gov, ltg = f"2026-{STATE}-GOV", f"2026-{STATE}-LTG"
    pairs = collections.defaultdict(dict)
    for rid, role in ((gov, "gov"), (ltg, "ltg")):
        for x in general.get(rid, []):
            if role in pairs[x["code"]]:
                raise SystemExit(f"Hawaii (state races): two {x['code']} candidates for {rid} on the November list")
            pairs[x["code"]][role] = x
    g_inc = identify(gov, [p["gov"]["Ballot Name"] for p in pairs.values() if "gov" in p])
    l_inc = identify(ltg, [p["ltg"]["Ballot Name"] for p in pairs.values() if "ltg" in p])
    for code, p in sorted(pairs.items()):
        if set(p) != {"gov", "ltg"}:
            problems.append(f"{gov}: the {party_word[code]} nominees for Governor and Lieutenant Governor are not both on the November list")
            continue
        g, l = p["gov"]["Ballot Name"], p["ltg"]["Ballot Name"]
        notes = ["Governor and Lieutenant Governor on one ticket, the candidate for Governor named first."]
        hid = None
        if g in g_inc:
            hid = g_inc[g]["id"]
            incumbents += 1
        if l in l_inc:
            notes.append(f"{shown(l)} serves today as Lieutenant Governor.")
        notes.append(CAPS)
        cands.append((gov, "general", GENERAL, f"{shown(g)} and {shown(l)}", party_word[code], party_code(party_word[code]), None,
                      1 if hid else 0, 0, None, None, None, hid, SRC["report"], " ".join(notes)))
    general.pop(gov, None)
    general.pop(ltg, None)

    for rid, rr in general.items():
        r = races[rid]
        inc = identify(rid, [x["Ballot Name"] for x in rr])
        alone = r["level"] == "legislature" and len(rr) == 1
        marks = {x["Status"] for x in rr}
        if alone:
            settled.append(rid)
            if marks != {EAP}:
                problems.append(f"{rid}: one candidate left after the primary, and the Candidate Report marks {sorted(marks)}, not Elected After Primary")
        elif EAP in marks:
            problems.append(f"{rid}: the Candidate Report marks Elected After Primary beside other nominees")
        for x in rr:
            h = inc.get(x["Ballot Name"])
            if h:
                incumbents += 1
            notes = []
            if alone:
                d = drawn.get((rid, x["code"]))
                notes.append("Declared elected after the August 8 primary: the only candidate nominated for this seat, so the name is not on "
                             "the November 3 ballot" + (f" (chosen by lot on {d['date']}, the primary having ended in a tie)." if d else "."))
            notes.append(CAPS)
            cands.append((rid, "general", GENERAL, shown(x["Ballot Name"]), party_of(rid, x["code"]), pcode(rid, x["code"]), None,
                          1 if h else 0, 0, None, None, "unopposed" if alone else None, h["id"] if h else None, SRC["report"],
                          " ".join(n for n in notes if n)))

    # primary fields
    field_rows = 0
    alone_lost = collections.defaultdict(list)
    for (rid, code), field in votes.items():
        w = {fold(n) for n in winners.get((rid, code), [])}
        if len(field) < 2:
            n, v = field[0]
            if fold(n) not in w:
                alone_lost[rid].append(f"{shown(n)} ({party_of(rid, code)}, {v:,} votes)")
            continue
        fields.append((rid, code))
        total = sum(v for _n, v in field)
        inc = identify(rid, [n for n, _v in field])
        d = drawn.get((rid, code))
        tied = {fold(x) for x, vv in field if vv == max(v for _n, v in field)}
        for n, v in sorted(field, key=lambda nv: (-nv[1], fold(nv[0]))):
            h = inc.get(n)
            notes = []
            if d and fold(n) in tied:
                notes.append(f"Tied for first in the certified count; the Office of Elections drew lots on {d['date']}, and the name drawn was "
                             f"{shown(d['winner'])}.")
            if (rid, n) in np_notes:
                notes.append(np_notes[(rid, n)])
            notes.append(CAPS)
            cands.append((rid, f"primary-{code}", PRIMARY, shown(n), party_of(rid, code), pcode(rid, code), None, 1 if h else 0, 0, v,
                          round(100 * v / total, 1) if total else None, "advanced" if fold(n) in w else "lost", h["id"] if h else None,
                          SRC["results"], " ".join(notes)))
            field_rows += 1

    # ---- race notes, holders, counties
    left = collections.defaultdict(collections.Counter)
    for rid, rr in rows_by_race.items():
        for x in rr:
            if x["Status"] in OFF or x["Status"] == FILED:
                left[rid][x["Status"]] += 1
    race_rows, place_rows = [], []
    for rid, r in races.items():
        notes = []
        hs = holders(rid)
        if r["office_kind"] == "governor":
            notes.append("Hawaii elects the Governor and Lieutenant Governor together in November, one vote for the pair (the November contest "
                         "is Governor and Lieutenant Governor, as the Office's certified 2022 general results show it); each party nominates "
                         f"them in separate primaries, the Lieutenant Governor's under 2026-{STATE}-LTG.")
        if r["office_kind"] == "lieutenant_governor":
            notes.append(f"Nominated in each party's own primary on August 8; in November the Lieutenant Governor is elected jointly with the "
                         f"Governor, on the pairs listed under 2026-{STATE}-GOV.")
        if r["office_kind"] == "oha_trustee":
            if r["seat"] == "At-Large":
                sent = sum(1 for c in cands if c[0] == rid and c[1] == "general")
                notes.append(f"{exp['oha_at_large']} at-large seats: every voter may vote for up to {at_large_seats}, and the {at_large_seats} "
                             f"with the most votes are elected. The August 8 primary sent {sent} on to November.")
            else:
                notes.append(f"Every voter in the state votes for this seat; the trustee must live on {ISLANDS[rid.rsplit('-', 1)[1]]}. "
                             "No primary: the Candidate Report marks both candidates In General, and the certified primary has no contest for it.")
            notes.append("A nonpartisan office: no party is printed on the ballot.")
            notes.append("The roster this site uses does not carry the Office of Hawaiian Affairs trustees, so today's holders are not shown.")
        if r["special"]:
            p = procs.get(r["district"])
            if p:
                notes.append(f"A special election for the rest of the term, which ends on {p['term_end'] or 'November 7, 2028'}: the seat fell "
                             f"vacant when {p['resigned'] or 'the senator'} resigned (the Chief Election Officer's proclamation of {p['signed']}).")
                if p["committees"]:
                    notes.append("No primary: the parties' county committees nominated their candidates, and the proclamation says the "
                                 "nonpartisan nominee is decided by lot.")
                    if left[rid].get(FILED):
                        notes.append(f"The Candidate Report marks {left[rid][FILED]} more nonpartisan filing Filed rather than In General; "
                                     "it is not on the November list.")
                elif p["primary"]:
                    notes.append("Its nominees were chosen in the August 8 primary, with the regular seats.")
            else:
                problems.append(f"{rid}: a vacancy with no proclamation read")
        elif r["office_kind"] == "state_senate":
            notes.append("Hawaii's senators serve four years; this is one of the seats the Contest Schedule lists for 2026.")
        dd = [d for (dr, _c), d in drawn.items() if dr == rid]
        if rid in settled:
            x = next(c for c in cands if c[0] == rid and c[1] == "general")
            marked = {g["Status"] for g in general.get(rid, [])}
            if marked == {EAP}:
                notes.append(f"Not on the November 3 ballot: {x[3]} ({x[4]}) was the only candidate left for this seat after the August 8 "
                             "primary and is declared elected, as the Office of Elections' Candidate Report marks it (Elected After Primary).")
            else:
                notes.append(f"Not on the November 3 ballot: {x[3]} ({x[4]}) is the only candidate left for this seat after the August 8 primary "
                             "and its drawing, and so is declared elected.")
            if dd:
                notes.append(f"The {party_word[dd[0]['party']]} primary was a tie in the certified count; the Office drew lots on {dd[0]['date']} "
                             f"and its drawing result says the name drawn was selected as the {dd[0]['selected_as']}.")
                if marked != {EAP}:
                    notes.append(f"The Candidate Report, read {report.get('fetched') or day_of(report_path)}, still marks both "
                                 f"{party_word[dd[0]['party']]} candidates In General; this page follows the drawing result.")
        elif dd:
            notes.append(f"The {party_word[dd[0]['party']]} primary was a tie in the certified count; the Office drew lots on {dd[0]['date']}, "
                         f"and {shown(dd[0]['winner'])} was selected as the {dd[0]['selected_as']}.")
        if alone_lost.get(rid):
            notes.append("Also on the August 8 primary ballot, alone in a section, and not nominated: " + "; ".join(alone_lost[rid]) + ".")
        gone = left[rid]
        if gone.get("Withdrawn") or gone.get("Void"):
            notes.append("Left off the lists: " + ", ".join(f"{n} {s.lower()}" for s, n in sorted(gone.items()) if s in OFF) + ".")
        if r["level"] == "legislature" and not hs:
            notes.append(f"The Open States roster ({roster_as_of}) lists no one holding this seat today.")
            problems.append(f"{rid}: no sitting member in the roster")
        notes.append(NO_ORDER)
        cids = None
        if r["chamber"]:
            kind = "SS" if r["chamber"] == "Senate" else "SH"
            got = reach[kind].get(r["district"])
            if got is None:
                problems.append(f"{rid}: no {r['chamber']} district {r['district']} in the Census file")
            else:
                cids = got
                place_rows.append(("senate" if kind == "SS" else "house", f"{STATE}-{r['district']}", r["jurisdiction"], json.dumps(got), SRC[kind]))
        race_rows.append((rid, STATE, r["level"], r["office_kind"], r["office"], r["jurisdiction"], r["jurisdiction_id"],
                          json.dumps(cids) if cids else None, r["district"], r["seat"], r["special"], r["partisan"],
                          "; ".join(h["id"] for h in hs) or None, "; ".join(h["full"] or f"{h['first']} {h['last']}" for h in hs) or None,
                          "; ".join(h["party"] or "" for h in hs) or None, GENERAL, " ".join(notes) or None))
    place_rows = [("county", g, n, json.dumps([g]), SRC["county"]) for g, n in sorted(counties.items())] + place_rows

    # ---- checks on the whole
    keys = collections.Counter((c[0], c[1], c[3]) for c in cands)
    dup = [k for k, v in keys.items() if v > 1]
    if dup:
        raise SystemExit(f"Hawaii (state races): the same name twice in one election ({len(dup)} cases)")
    gen_by_race = collections.Counter(c[0] for c in cands if c[1] == "general")
    for rid in races:
        if rid != ltg and not gen_by_race[rid]:
            problems.append(f"{rid}: no candidate on the November list")
    n_nominated = sum(1 for rr in rows_by_race.values() for x in rr if x["Status"] in NOMINATED)
    n_general = sum(1 for c in cands if c[1] == "general") + len(pairs)           # a pair row counts its two names
    if n_general + len(losers_marked_on) != n_nominated:
        problems.append(f"{n_nominated} rows marked In General or Elected After Primary; {n_general} names stored and "
                        f"{len(losers_marked_on)} set aside by a drawing")
    for c in cands:
        if page_would_drop(c[14]) or page_would_drop(c[3]):
            problems.append(f"{c[0]} {c[1]}: a candidate's name or note would be dropped by the page's contact-detail check")
    for r in race_rows:
        if page_would_drop(r[16]):
            problems.append(f"{r[0]}: its note would be dropped by the page's contact-detail check")
    uncovered = sorted(set(counties) - {g for kind in reach for v in reach[kind].values() for g in v})
    if uncovered:
        notes_out.append(f"no district of either chamber reaches {', '.join(counties[g] for g in uncovered)} in the Census lines")

    # ---- sources
    others = report.get("others", {})
    county_rows = sum(sum(v.values()) for k, v in others.items() if k.startswith("county"))
    federal_rows = sum(sum(v.values()) for k, v in others.items() if k.startswith("federal"))
    rep_note = (f"Linked as \"Candidate Report\" from {REPORT_LINK}. All {report['items']} rows on {report['pages']} pages read through the "
                f"grid's own pager on {report.get('fetched') or day_of(report_path)} and counted against its total; only Contests, Party, Ballot "
                "Name and Status taken, by their headings (legal name, mailing address, phone, e-mail, website and filing dates are never read "
                f"or kept). State rows: {len(report['rows'])} ({', '.join(f'{s} {n}' for s, n in sorted(statuses.items()))}). The November list is "
                "the rows marked In General; Elected After Primary is declared elected and not on the November ballot (stored as unopposed); "
                "In Primary lost at the primary; Issued never filed (not candidates); Withdrawn, Void and Filed are left off. "
                f"Counted, not loaded: county offices ({county_rows} rows) and Congress ({federal_rows} rows, the federal loader's). "
                "The report gives no ballot positions. Hawaii's ballots have no write-in line.")
    draw_ids = {}
    sources = [
        source_row(SRC["report"], "official candidate list", AGENCY, "2026 Candidate Report: Governor, Lieutenant Governor, State Senate, "
                   "State House and Office of Hawaiian Affairs trustees", REPORT, "", report.get("fetched") or day_of(report_path),
                   sha_file(report_path), len(report["rows"]), rep_note + " sha256 is of the kept extract."),
        source_row(SRC["results"], "official results", AGENCY,
                   "Primary Election August 8, 2026, Certified Text Files: Statewide Summary (summary.txt), state contests",
                   res_meta["urls"]["summary"], printed_on, day_of(res_paths["summary"]), sha_file(res_paths["summary"]), field_rows,
                   f"Listed under \"{res_meta['heading']}\" on {RESULTS_PAGE}, headed Certified; the federal loader's copy. {len(votes)} state "
                   "sections read (Governor, Lieutenant Governor, State Senate, State House, OHA at-large); every one counted all its "
                   "precincts; mail and in-person votes make each total; each section's candidates are the Candidate Report's; each "
                   "party's leader is its nominee (two ties settled by lot, below); the nonpartisan rule checked for every partisan contest "
                   f"(the Office's page {RULE_PAGE}). Fields stored: {len(fields)}. pct is of the section's candidates' votes. Counted, not "
                   f"loaded: {sum(other_contests.values())} county and federal lines."),
        source_row(SRC["pdf"], "official results", AGENCY,
                   "Primary Election August 8, 2026, Certified Reports: Statewide Summary (Summary Report, Final)", res_meta["urls"]["pdf"],
                   printed_on, day_of(res_paths["pdf"]), sha_file(res_paths["pdf"]), sum(len(f) for f in votes.values()),
                   f"Control: every state candidate's name is printed beside the same total as in summary.txt; the at-large trustee contest "
                   f"says Number To Vote For: {at_large_seats}."),
        source_row(SRC["schedule"], "official notice", AGENCY, "Contest Schedule: 2026", SCHEDULE, "", sched.get("fetched") or day_of(sched_path),
                   sha_file(sched_path), len(sched["rows"]),
                   f"The 2026 table's cells only (sha256 of the kept extract). State: Governor and Lieutenant Governor; State Senate "
                   f"{len(exp['senate'])} seats ({', '.join(sorted(exp['senate'], key=int))}; {', '.join(sorted(exp['senate_star'], key=int))} "
                   f"starred: {exp['term_note']}); State House 1 - 51; OHA trustees {exp['oha_at_large']} at large and resident of "
                   f"{', '.join(sorted(x.title() for x in exp['oha_resident']))}. Also listed, not loaded: {'; '.join(exp['county'])}."),
        source_row(SRC["gov2022"], "official results", AGENCY, "2022 General Election Statewide Summary (summary.txt): Governor contest only",
                   GOV_2022, "", gov22.get("fetched") or day_of(gov22_path), gov22.get("sha256", ""), len(gov22["rows"]),
                   f"Only the contest title and candidate lines of the Governor contest are kept: \"{gov22['rows'][0]['contest'] if gov22['rows'] else ''}\", "
                   "each line a party's candidate for Governor with the party's candidate for Lieutenant Governor. Used to show the November "
                   "contest is one pair per party."),
    ]
    for d in draws:
        sid = f"hi-oe-2026-drawing-{d['race'].rsplit('-', 1)[1].lower()}"
        draw_ids[d["race"]] = sid
        sources.append(source_row(sid, "official notice", AGENCY, d["label"], d["url"], "", day_of(d["path"]), sha_file(d["path"]), 1,
                                  f"Linked under Drawings on {RESULTS_PAGE}. The {party_word[d['party']]} primary for {d['race']} was a tie in the certified "
                                  f"count; the drawing by lot ({d['date']}, Hawaii Revised Statutes section 11-157) chose the candidate "
                                  f"\"selected as the {d['selected_as']}\"."))
    for dist, p in procs.items():
        sources.append(source_row(f"hi-oe-2026-sd{dist}-proclamation", "official notice", AGENCY,
                                  f"Proclamation: State Senate District {dist} vacancy ({p['signed']})", p["url"], "", day_of(p["path"]),
                                  sha_file(p["path"]), 1, f"Linked from {p['page']} (listed on {PROCLAMATION_LIST}). Read for the term's end "
                                  f"({p['term_end']}) and how the seat is filled"
                                  + (": party nominees by the parties' county committees, the nonpartisan nominee by lot, no primary."
                                     if p["committees"] else ": a primary on August 8 and the general election on November 3.")))
    sources.append(source_row(SRC["county"], "official place names", "U.S. Census Bureau", "Cartographic boundary file, counties, 1:500,000 (2024)",
                              CENSUS_URL + "cb_2024_us_county_500k.zip", "", day_of(COUNTY_ZIP), sha_file(COUNTY_ZIP), len(counties),
                              "Hawaii's five counties: names, GEOIDs and lines, to say which counties each district reaches."))
    for kind, label in (("SS", "State legislative districts, upper chamber"), ("SH", "State legislative districts, lower chamber")):
        sources.append(source_row(SRC[kind], "official district lines", "U.S. Census Bureau", f"Cartographic boundary file, {label}, Hawaii (2024)",
                                  CENSUS_URL + os.path.basename(DISTRICT_ZIP[kind]), "", day_of(DISTRICT_ZIP[kind]), sha_file(DISTRICT_ZIP[kind]),
                                  len(reach[kind]), "District numbers and lines only. A district reaches a county when a point inside one of its "
                                  "pieces lies in the county, or a point inside one of the county's pieces lies in the district."))
    if members or officials:
        sources.append(source_row(SRC["roster"], "roster", "Open States (people project, CC0)",
                                  "Legislators serving now and statewide officials (state_hi.sqlite, from the Open States people project)",
                                  "https://github.com/openstates/people", roster_as_of, day_of(roster_path), sha_file(roster_path),
                                  len(members) + len(officials),
                                  "Used only to say who holds each seat today, to mark incumbents and for the capitals of a sitting member's "
                                  "name: ids, names, parties and districts. Not an official record."))
    # the drawings' own source ids on the rows they decided
    cands = [c if not (c[0] in draw_ids and c[11] == "unopposed") else c[:13] + (draw_ids[c[0]],) + c[14:] for c in cands]

    con = sqlite3.connect(db_path)
    try:
        con.executescript(SCHEMA)
        with con:
            con.execute("DELETE FROM sl_candidates WHERE race_id IN (SELECT race_id FROM sl_races WHERE state = ?) OR race_id LIKE ?",
                        (STATE, f"2026-{STATE}-%"))
            con.execute("DELETE FROM sl_races WHERE state = ?", (STATE,))
            con.execute("DELETE FROM sl_sources WHERE state = ?", (STATE,))
            con.execute("DELETE FROM sl_places WHERE source_id LIKE 'hi-%'")
            con.executemany("INSERT INTO sl_races VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", race_rows)
            con.executemany("INSERT INTO sl_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", cands)
            con.executemany("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", sources)
            con.executemany("INSERT INTO sl_places VALUES (?,?,?,?,?)", place_rows)
    finally:
        con.close()

    by_kind = collections.Counter(r["office_kind"] for r in races.values())
    gen_rows = [c for c in cands if c[1] == "general"]
    say(f"    Hawaii: {len(races)} state races (Governor and Lieutenant Governor, Senate {by_kind['state_senate']}, House "
        f"{by_kind['state_house']}, OHA trustees {by_kind['oha_trustee']}); {len(gen_rows) - len(settled)} candidate rows on the November "
        f"ballot ({len(pairs)} Governor pairs), {len(settled)} seats declared elected after the primary; {len(fields)} primary fields "
        f"({field_rows} rows, certified votes); {incumbents} incumbents marked")
    for p in problems:
        say(f"      CHECK {p}")
    for n in notes_out:
        say(f"      note: {n}")
    return {"races": len(races), "by_kind": dict(by_kind), "general_rows": len(gen_rows), "settled": settled, "fields": len(fields),
            "field_rows": field_rows, "incumbents": incumbents, "problems": problems, "notes": notes_out,
            "statuses": dict(statuses), "drawings": [(d["race"], d["party"]) for d in draws]}


if __name__ == "__main__":
    args = sys.argv[1:]
    cache, refresh = DEFAULT_CACHE, "--refresh" in args
    args = [a for a in args if a != "--refresh"]
    if "--cache" in args:
        i = args.index("--cache")
        cache = args[i + 1]
        del args[i:i + 2]
    if len(args) != 1:
        raise SystemExit("usage: python ballot/state_local_hi.py <database file> [--cache <folder>] [--refresh]")
    load(args[0], cache=cache, refresh=refresh)
