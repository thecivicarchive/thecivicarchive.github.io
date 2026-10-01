"""
ballot/state_local_va.py - Virginia's state races, and its county, city, town and school board races, on the November
3, 2026 ballot, from the Virginia Department of Elections' own candidate lists and results, into
ballot_local_2026.sqlite (never ballot_2026.sqlite). Virginia's rows only: everything this loader writes is deleted and
written again on each run.

What is on the ballot this year
-------------------------------
Virginia elects its General Assembly and its three statewide officers in odd years: the House of Delegates in 2025
and next in 2027, the Senate of Virginia in 2023 and next in 2027, the Governor, Lieutenant Governor and Attorney
General in 2025 and next in 2029. So no regular state race is on the November 3, 2026 ballot. What can be on it is a
special election to fill a vacancy for the rest of a term. The Department's lists for November 3 carry one: the House
of Delegates, 20th District, for the term ending January 11, 2028 (read 2026-09-30). The loader does not assume this:
it reads every office on the lists and stores whatever state office they carry, and if a later revision carries none,
it stores no race and says why.

Sources (all the Department's own; the same site the federal loader, ballot/lists/va.py, reads)
  * "2026 November All Offices Candidate List", the workbook linked as "Download this file" from the page "November 3,
    2026 - All Offices" (elections.virginia.gov, Candidates & Referendums). The page is read first and its link
    followed, so a revision (the file's name carries its date: rev-9-29-2026 on the copy read first) is picked up by
    itself. One sheet, one row per candidate per locality where the office is on the ballot. Columns are taken by name,
    and only these: Locality, Office Ballot Order, Party Ballot Order, Office Title, District, Number of Seats, Office
    Term, Special Office Unexpired Term End Date, Status, Candidate Party, Candidate Name, Incumbent. The campaign
    e-mail, website, phone and address columns that follow are never read: the sheet is read only up to the last
    allowed column, and nothing else of a row is kept. For a row that is not a state office (a federal or local
    office) only the Office Title cell is looked at, to count it; no name of a local candidate is kept.
  * each special-election list the Candidates & Referendums page links for November 3 ("2026 November Virginia House
    of Delegates, District 20 Special Election"), read the same way, as a control: its candidates, parties and ballot
    order must be the All Offices list's for that race, locality by locality.
  * the official results of the August 4, 2026 Democratic and Republican primaries (enr.elections.virginia.gov, the
    same records ballot/lists/va.py reads, required to be marked official): the loader looks for any state office among
    their contests. They carry none (only U.S. Senate and House contests), so no state primary field is stored: the
    District 20 nominees were not chosen in a primary the Department ran, and there is no official vote count for how
    they were chosen. Were a state contest ever there, its votes would come from the statewide summary, checked
    candidate by candidate against the precinct-by-precinct Election Results report.
  * who holds each seat today: state_va.sqlite (the Open States roster the state pages use), names, parties and
    districts only; statewide officers from its officials table. Not an official record. A candidate is marked the
    incumbent only when the name fits exactly one sitting member of the same chamber and district.
  * county_ids: the list's localities (Virginia's 95 counties and 38 independent cities) turned into Census GEOIDs by
    the Census Bureau's 2024 cartographic county file.

Ballot order: the Party Ballot Order column, the candidate's place within the office on the ballot (it must be the
same in every locality). Names are kept as printed (a name printed in capitals would be shown in ordinary capitals and
the race note would say so). Parties are written out as printed.

The privacy rule: from any list only office, district, locality, name, party, ballot order, status, the incumbent mark
and votes are read. Nothing else is read, printed, logged, cached or stored; the cache keeps only those columns, as
JSON, with the workbook's SHA-256. No photos, ages, websites, biographies or money in this phase.

County, city, town and school board offices (the local part)
------------------------------------------------------------
Source: the Department's "2026 November Local Offices Candidate List", the workbook linked as "Download this file" from
its page "November 3, 2026 - Local Offices" (the page is read for that one link and nothing else of it is kept). One
sheet, one row per candidate per locality (county or independent city) whose ballot carries the contest. Columns are
taken by name, and only these: Locality, Office Ballot Order, Party Ballot Order, Office Title, District, Number of
Seats, Office Term, Special Office Unexpired Term End Date, Status, Candidate Party, Candidate Name. The sheet is read
no further than the Candidate Name column, so the Incumbent column and the campaign e-mail, website, phone and
address columns to its right are never read; the kept columns must be the leftmost ones, with no other heading among
them, or the loader stops. The cut-down copy (JSON) is the only thing cached, in ballot_cache/va/local/. A layout that
no longer fits stops the loader, which names the file, the sheet row and the check, never the row.

What a row says, and where a contest is filed:
  * the office is the opening words of the title, which the list spells several ways ("Member Town Council - Hurt",
    "Member, Town Council - Hurt", "Member Town Council, Fincastle"); what follows names a town, "At Large", a seat
    or "Special". The District cell holds a ward or district, or the locality itself, or a town ("Town of Herndon",
    "Blackstone Ward A", or a bare "Farmville"). A town is taken only when it is one town of that county in the
    Census Bureau's 2020 place list (st51_va_place2020.txt), compared by spelling (Mt for Mount, spaces set aside).
  * Virginia's towns are municipalities inside counties and its 38 cities are independent of any county: both are
    filed under level "city" (Virginia has no townships), each with its Census place code (VA-M-36648). A town in two
    counties has a row per county; they are one contest, with both counties in county_ids.
  * an elected school board belongs to a county, a city or a town (Colonial Beach, West Point): level "school", named
    after that place ("Arlington County school board"), keyed by the county's three digits and the place's name.
  * county offices (supervisors, Arlington's County Board, and special elections for sheriff, Commonwealth's attorney,
    treasurer, commissioner of the revenue and clerk of court) are level "county"; an office a city shares with a
    county (the list's District names both) is filed under the county, with both in county_ids.
  * a filled Special Office Unexpired Term End Date, or "Special" in the title, makes a special election (-S).
Party: the list has a Candidate Party column (who nominated; nearly all Independent), but Virginia prints a party
beside a name only for federal, statewide and General Assembly offices (Code of Virginia 24.2-613 B), so every local
contest is stored partisan 0 with "Nonpartisan office"; the column is not shown. Ballot order: for local offices the
Party Ballot Order column is one number to a party (1 Democratic, 2 Republican, 5 Independent): the place of a
candidate's party group, not the candidate's own. Party nominees are printed first and then the independents, who
are nearly all the candidates, in the order they filed (24.2-613 C), which the list does not give; so no ballot order
is stored for local contests (of 310 with two or more candidates on the copy first read, nine could have been
ranked). The loader says so if the column ever stops being one number to a party. The Incumbent column is never read
for local offices. A town office whose row names no town is that town's only where the county has exactly one town on
the Census list (Hillsville in Carroll County), and the contest's note says so. A row that cannot be placed (a town
office with no town named in a county with several towns) is not guessed: it goes to sl_gaps with the reason, and the
loader's check line counts it. The list names only
candidates who qualified, so a contest nobody qualified for (write-in only) is not on it; sl_gaps says so. sl_notes
carries the local calendar (which offices are elected now and which another year, with the Code sections) and what
is covered.

Fetching: one request at a time through states/net.py with its honest User-Agent, a second apart: the Local Offices
page, the workbook, and once the Census place list; a second run within two days asks for nothing (the index page's
links, the cut-down list and the place list are in ballot_cache/va/local/). If the Department's site ever refuses the request
(a 403, a challenge page, anything but the workbook) and the cache holds no copy, nothing is tried again and nothing
is worked around: the state rows are still written and sl_gaps says the local list is missing. An ordinary network
failure with no copy in the cache stops the loader, and the rows loaded before stay as they were.

Usage: python -m ballot.state_local_va <database file> [cache folder]
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
import unicodedata
import zipfile
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urljoin

if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import openpyxl

from ballot.check_local import EXTRA_SCHEMA, contact_like
from ballot.common import CACHE, HERE, fold, name_parts, party_code
from ballot.lists.va import ENR_API, ENR_CDN, ENR_SITE, PRIMARIES, CODE, race_of as federal_race, shown
from ballot.match import fits
from states import net

STATE, NAME, FIPS = "VA", "Virginia", "51"
GENERAL, PRIMARY = "2026-11-03", "2026-08-04"
BASE = "https://www.elections.virginia.gov"
INDEX = BASE + "/casting-a-ballot/candidate-list/"
INDEX_HEADING = "Candidates & Referendums"
ALL_PAGE = INDEX + "november-3-2026-gen-elect-all-offices/"
ALL_HEADING = "November 3, 2026 - All Offices"
ALL_LINK = re.compile(r"/candidatelist/2026/2026-November-All-Offices-Candidate-List[^\"'<>]*\.xlsx$", re.I)
NOV_LINK = re.compile(r"/candidatelist/2026/2026-November-[^\"'<>]*\.xlsx$", re.I)
SPECIAL_TEXT = re.compile(r"House of Delegates|Senate of Virginia|Governor|Attorney General", re.I)
ROSTER = os.path.join(HERE, "state_va.sqlite")
COUNTY_ZIP = os.path.join(HERE, "states_cache", "census", "cb_2024_us_county_500k.zip")
COUNTY_URL = "https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_county_500k.zip"

# the only columns ever taken from a candidate list (by heading); the contact columns are never read
REQUIRED = ("Office Title", "District", "Candidate Party", "Candidate Name")
ALLOWED = ("Locality", "Office Ballot Order", "Party Ballot Order", "Office Title", "District", "Number of Seats",
           "Office Term", "Special Office Unexpired Term End Date", "Status", "Candidate Status", "Candidate Party",
           "Candidate Name", "Incumbent")
GONE = ("withdr", "disqual", "remov", "denied", "deceas", "inactive")
STATE_LIKE = re.compile(r"delegate|senate|senator|governor|attorney general|general assembly|supreme court|court of appeals"
                        r"|state corporation", re.I)
STATEWIDE = {"Governor": ("GOV", "governor", "Governor", "governor"),
             "Lieutenant Governor": ("LTG", "lieutenant_governor", "Lieutenant Governor", "lt_governor"),
             "Attorney General": ("AG", "attorney_general", "Attorney General", "attorney general")}
CAPS = "Virginia's list prints this name in capitals; it is shown here in ordinary capitals."
WRITE_IN = "Write-in candidate: the name is not printed on the ballot."
NO_PRIMARY = ("No primary field: the Department's official results of the August 4, 2026 primaries carry no contest for "
              "this office, so the nominees were not chosen in a primary the Department ran and there is no official "
              "vote count for how they were chosen.")
ODD_YEARS = ("Virginia elects its General Assembly and its Governor, Lieutenant Governor and Attorney General in odd years "
             "(the House of Delegates next in 2027, the Senate of Virginia in 2027, the three statewide offices in 2029), "
             "so no regular state race is on the November 3, 2026 ballot; only a special election to fill a vacancy can be.")
SRC_ALL, SRC_COUNTY, SRC_ROSTER = "va-elections-2026-sl-all-offices-list", "va-census-2024-counties", "va-openstates-roster"
SRC_PRI = {"Democratic": "va-elections-2026-sl-primary-dem", "Republican": "va-elections-2026-sl-primary-rep"}


def ordinal(n):
    n = int(n)
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def day_of(path):
    return dt.datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d") if path and os.path.exists(path) else ""


def sha_of(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest() if path and os.path.exists(path) else ""


def join(*parts):
    return " ".join(p for p in parts if p) or None


def clean(v):
    """A cell as text: dates as YYYY-MM-DD, whole numbers without .0, spaces collapsed."""
    if v is None:
        return ""
    if isinstance(v, dt.datetime):
        return v.date().isoformat()
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    t = re.sub(r"\s+", " ", str(v)).strip()
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", t)
    return f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}" if m else t


def special_sid(url):
    """va-elections-2026-sl-special-hd20 for .../2026-November-HD20-Candidate-List.xlsx."""
    slug = re.sub(r"[^a-z0-9]+", "-", os.path.basename(url).lower().rsplit(".", 1)[0]).strip("-")
    slug = re.sub(r"^2026-november-|-candidate-list$", "", slug)
    return "va-elections-2026-sl-special-" + slug


def get(url, accept="*/*"):
    time.sleep(1.0)
    return net.get(url, accept=accept)


def page_links(url, heading, only=None, seen=None):
    """A page's links as (absolute address, link text), after checking its heading. With `only` (a pattern for the
    Department's own files), no other link of the page is collected at all: a list page may carry candidates'
    campaign websites, and those addresses are never taken, kept or shown. `seen`, a dict, is given the SHA-256 and
    the size of the page as fetched."""
    raw = get(url)
    if seen is not None:
        seen.update(sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))
    page = raw.decode("utf-8", "replace")
    del raw
    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", page, re.S | re.I)
    said = re.sub(r"\s+", " ", H.unescape(H.unescape(re.sub(r"<[^>]+>", " ", h1.group(1))))).strip() if h1 else ""
    if said != heading:
        raise SystemExit(f"Virginia: the page {url} is headed {said!r}, not {heading!r}")
    out = []
    for href, text in re.findall(r"<a[^>]+href=\"([^\"]+)\"[^>]*>(.*?)</a>", page, re.S | re.I):
        address = urljoin(url, H.unescape(href))
        if only is not None and not only.search(address):
            continue
        out.append((address, re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", text))).strip()))
    return out


def index_links(folder):
    """The Candidates & Referendums page's links to the Department's own November 2026 workbooks, as (address, link
    text), kept two days in the cache so that a second run asks for nothing."""
    path = os.path.join(folder, "local", "va_candidate_list_index.json")
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < 2 * 86400:
        return [tuple(x) for x in json.load(open(path, encoding="utf-8"))["links"]]
    links = page_links(INDEX, INDEX_HEADING, only=NOV_LINK)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump({"page": INDEX, "heading": INDEX_HEADING, "read": dt.date.today().isoformat(), "links": links},
              open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return links


# ---------------------------------------------------------------- offices

def classify(office, district):
    """The state race an office belongs to, as a dict; "federal" for the U.S. Senate and House (left to the federal
    pages); None for a local office. Raises for a state-sounding office this loader does not know."""
    office = re.sub(r"\s+", " ", office or "").strip()
    district = re.sub(r"\s+", " ", district or "").strip()
    try:
        if federal_race(office, district):
            return "federal"
    except SystemExit:
        return "federal-unread"
    m = re.fullmatch(r"Member,? (House of Delegates|Senate of Virginia)(?: \((\d+)(?:st|nd|rd|th) District\))?", office, re.I)
    if m:
        d = m.group(2) or (re.fullmatch(r"(\d+)(?:st|nd|rd|th) District", district) or [None, None])[1]
        house = m.group(1).lower().startswith("house")
        top = 100 if house else 40
        if not d or not 1 <= int(d) <= top:
            raise SystemExit(f"Virginia: could not read the district of {office!r} ({district!r})")
        d = str(int(d))
        if house:
            return {"race_id": f"2026-{STATE}-SH{d}", "level": "legislature", "office_kind": "state_house",
                    "office": "Member, House of Delegates", "jurisdiction": f"House of Delegates District {d}",
                    "jurisdiction_id": f"{STATE}-{d}", "district": d, "chamber": "House",
                    "place": ("house", f"{STATE}-{d}", f"House of Delegates District {d}")}
        return {"race_id": f"2026-{STATE}-SS{d}", "level": "legislature", "office_kind": "state_senate",
                "office": "Member, Senate of Virginia", "jurisdiction": f"Senate District {d}",
                "jurisdiction_id": f"{STATE}-{d}", "district": d, "chamber": "Senate",
                "place": ("senate", f"{STATE}-{d}", f"Senate District {d}")}
    if office in STATEWIDE:
        key, kind, label, _ = STATEWIDE[office]
        return {"race_id": f"2026-{STATE}-{key}", "level": "statewide", "office_kind": kind, "office": label,
                "jurisdiction": NAME, "jurisdiction_id": STATE, "district": None, "chamber": None, "place": None}
    if STATE_LIKE.search(office) and not re.search(r"commonwealth'?s attorney", office, re.I):
        raise SystemExit(f"Virginia: the list names an office this loader does not know: {office!r}")
    return None


# ---------------------------------------------------------------- the candidate lists: allowed columns only

def read_workbook(data, label):
    """The rows of a state office on the list (allowed columns only), and counts of the other rows by kind."""
    if data[:2] != b"PK":
        raise SystemExit(f"Virginia: {label} is not a workbook")
    wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    if len(wb.worksheets) != 1:
        raise SystemExit(f"Virginia: {label} has {len(wb.worksheets)} sheets; read it again")
    ws = wb.worksheets[0]
    heads, start = None, 0
    for i, r in enumerate(ws.iter_rows(values_only=True, max_row=12)):           # headings only, to find the columns
        cells = [str(c).strip() if c is not None else "" for c in r]
        if all(k in cells for k in REQUIRED):
            heads, start = cells, i + 2
            break
    if not heads:
        raise SystemExit(f"Virginia: {label}'s columns changed (no row with {', '.join(REQUIRED)})")
    idx = {k: heads.index(k) for k in ALLOWED if k in heads}
    last = max(idx.values()) + 1                                                 # the sheet is read no further than this column
    kept, counts, n = [], collections.Counter(), 0
    for r in ws.iter_rows(min_row=start, max_col=last, values_only=True):
        cell = lambda k: clean(r[idx[k]]) if k in idx and idx[k] < len(r) else ""
        office = cell("Office Title")
        if not office and not cell("Candidate Name"):
            continue
        n += 1
        what = classify(office, cell("District"))
        if what is None:
            counts["local"] += 1                                                 # only the office cell was looked at
            continue
        if isinstance(what, str):
            counts[what] += 1
            continue
        kept.append({k: cell(k) for k in idx})
    wb.close()
    return {"columns": list(idx), "rows": kept, "counts": dict(counts), "all_rows": n}


def read_list(url, page, heading, path, max_age_days, say):
    """One list, kept on disk as JSON (the allowed columns of its state-office rows, counts of the rest, the workbook's
    SHA-256). Asked afresh when older than max_age_days."""
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < max_age_days * 86400:
        return json.load(open(path, encoding="utf-8"))
    data = get(url, accept="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,*/*")
    got = read_workbook(data, os.path.basename(url))
    m = re.search(r"rev-(\d{1,2})-(\d{1,2})-(\d{4})", url)
    meta = {"url": url, "page": page, "heading": heading, "sha256": hashlib.sha256(data).hexdigest(),
            "published": f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}" if m else "",
            "revision": f"rev. {m.group(1)}-{m.group(2)}-{m.group(3)}" if m else "", "read": dt.date.today().isoformat(), **got}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(meta, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    say(f"      {os.path.basename(url)}: {got['all_rows']} rows, {len(got['rows'])} of a state office "
        f"({', '.join(f'{k} {v}' for k, v in sorted(got['counts'].items())) or 'no others'})")
    return meta


def lists(folder, say):
    """The All Offices list and every special-election list linked for November 3 that names a state office."""
    all_path = os.path.join(folder, "va_2026_sl_all_offices_list.json")
    fresh = os.path.exists(all_path) and time.time() - os.path.getmtime(all_path) < 2 * 86400
    specials = []
    try:
        if not fresh:
            links = [u for u, _t in page_links(ALL_PAGE, ALL_HEADING, only=ALL_LINK)]
            if not links:
                raise SystemExit("Virginia: the All Offices page no longer links the 2026 November All Offices Candidate List workbook")
            main = read_list(links[0], ALL_PAGE, ALL_HEADING, all_path, 0, say)
        else:
            main = json.load(open(all_path, encoding="utf-8"))
        index = index_links(folder)
        for u, text in index:
            if NOV_LINK.search(u) and not ALL_LINK.search(u) and SPECIAL_TEXT.search(text) and "Special" in text:
                slug = re.sub(r"[^a-z0-9]+", "-", os.path.basename(u).lower().replace(".xlsx", "")).strip("-")
                specials.append((text, read_list(u, INDEX, text, os.path.join(folder, f"va_2026_sl_special_{slug}.json"), 2, say)))
    except (HTTPError, URLError, OSError) as e:
        if not os.path.exists(all_path):
            raise
        say(f"      could not refresh the Department's lists ({e}); using the copies read earlier")
        main, specials = json.load(open(all_path, encoding="utf-8")), []
        for name in sorted(os.listdir(folder)):
            if name.startswith("va_2026_sl_special_") and name.endswith(".json"):
                meta = json.load(open(os.path.join(folder, name), encoding="utf-8"))
                specials.append((meta["heading"], meta))
    return all_path, main, specials


# ---------------------------------------------------------------- the August 4 primaries: any state contest?

def primary_state_contests(folder, party, say):
    """The state contests (if any) on one party's official August 4 primary results, as JSON in the cache, with the
    precinct report's sums for them. Read afresh when thirty days old."""
    slug = PRIMARIES[party]
    path = os.path.join(folder, f"va_2026_sl_primary_{CODE[party].lower()}.json")
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < 30 * 86400:
        return path, json.load(open(path, encoding="utf-8"))
    try:
        raw = get(ENR_API + slug + "/data", accept="application/json")
    except (HTTPError, URLError, OSError) as e:
        if os.path.exists(path):
            say(f"      could not refresh the {party} primary results ({e}); using the copy read earlier")
            return path, json.load(open(path, encoding="utf-8"))
        raise
    data = json.loads(raw.decode("utf-8-sig"))
    el = data["election"]
    name = el["name"][0]["text"]
    if el.get("electionDate") != PRIMARY or party not in name or "Primary" not in name:
        raise SystemExit(f"Virginia: the results site's {slug} is {name!r} of {el.get('electionDate')}, not the {party} primary of {PRIMARY}")
    if el.get("isOfficialResults") is not True:
        raise SystemExit(f"Virginia: the results site does not mark the {party} primary's results official")
    contests, federal, other = [], 0, 0
    for item in data["ballotItems"]:
        if item.get("parentId"):
            continue
        office = item["name"][0]["text"]
        what = classify(office, "")
        if isinstance(what, str):
            federal += 1
            continue
        if what is None:
            other += 1
            continue
        options = []
        for o in item["summaryResults"]["ballotOptions"]:
            p = o.get("party") or {}
            label = next((t["text"] for t in p.get("name") or [] if t.get("languageId") == "en"), p.get("standardName") or "")
            options.append({"name": o["name"][0]["text"], "party": label, "votes": int(o["voteCount"] or 0),
                            "winner": bool(o.get("isWinner")), "write_in": bool(o.get("isWriteIn"))})
        contests.append({"office": office, "race": what["race_id"], "vote_total": int(item.get("voteTotal") or 0), "options": options})
    report_url, report_sha = "", ""
    if contests:                                                    # only then is the precinct report needed
        reports = [r for c in el.get("publicReportCategories") or [] for r in c.get("reports") or [] if r.get("reportName") == "Election Results"]
        if len(reports) != 1:
            raise SystemExit(f"Virginia: the results site lists {len(reports)} Election Results reports for the {party} primary")
        report_url = ENR_CDN + el["jurisdictionId"] + "/" + quote(reports[0]["blobName"])
        report = get(report_url, accept="text/csv,*/*")
        if report[:1] == b"<" or b"CandidateName" not in report[:400]:
            raise SystemExit(f"Virginia: the {party} primary's Election Results report is not the CSV it was")
        report_sha = hashlib.sha256(report).hexdigest()
        wanted = {c["office"] for c in contests}
        sums = collections.defaultdict(collections.Counter)
        for r in csv.DictReader(io.StringIO(report.decode("utf-8-sig"))):   # only these columns are read
            if r["OfficeTitle"] in wanted:
                sums[r["OfficeTitle"]][r["CandidateName"]] += int(float(r["TOTAL_VOTES"] or 0))
        for c in contests:
            c["precinct_sums"] = dict(sums.get(c["office"], {}))
    keep = {"slug": slug, "name": name, "date": el["electionDate"], "official": el["isOfficialResults"], "as_of": el.get("asOf"),
            "site": ENR_SITE + slug, "data_url": ENR_API + slug + "/data", "data_sha256": hashlib.sha256(raw).hexdigest(),
            "report_url": report_url, "report_sha256": report_sha, "federal_contests": federal, "other_contests": other,
            "read": dt.date.today().isoformat(), "contests": contests}
    os.makedirs(folder, exist_ok=True)
    json.dump(keep, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return path, keep


# ---------------------------------------------------------------- the roster and the counties

def roster(path=ROSTER):
    """Sitting legislators and statewide officers: id, chamber or office, district, names and party only."""
    if not os.path.exists(path):
        return [], {}
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    members = [dict(zip(("id", "chamber", "district", "first", "last", "full", "party"), r)) for r in con.execute(
        "SELECT bioguide_id, chamber, district, first_name, last_name, official_full, party_name "
        "FROM legislators WHERE is_current = 1 AND state = 'VA'")]
    officers = {}
    for r in con.execute("SELECT office, bioguide_id, first_name, last_name, official_full, party_name, term_end FROM officials "
                         "WHERE state = 'VA'"):
        if not r[6] or r[6] >= dt.date.today().isoformat():
            officers.setdefault(r[0], []).append(dict(zip(("office", "id", "first", "last", "full", "party"), r[:6])))
    con.close()
    return members, officers


def name_fits(name, person):
    given, family = name_parts(name)
    for reg in (([w for w in fold(person["first"]).split()], " ".join(fold(person["last"]).split())), name_parts(person["full"])):
        if fits((given, family), reg):
            return True
    return False


def one_fit(name, people):
    hits = [p for p in people if name_fits(name, p)]
    return hits[0] if len(hits) == 1 else None


def county_codes(path=COUNTY_ZIP):
    """{folded name as Virginia writes a locality ("prince william county", "manassas city"): (GEOID, name)}."""
    import shapefile                                   # pyshp
    z = zipfile.ZipFile(path)
    base = next(n[:-4] for n in z.namelist() if n.endswith(".dbf"))
    rdr = shapefile.Reader(dbf=io.BytesIO(z.read(base + ".dbf")))
    fields = [f[0] for f in rdr.fields[1:]]
    out = {}
    for rec in rdr.iterRecords():
        rec = dict(zip(fields, rec))
        if str(rec.get("STATEFP")) == FIPS:
            out[fold(str(rec["NAMELSAD"]))] = (str(rec["GEOID"]), str(rec["NAMELSAD"]))
    if len(out) != 133:
        raise SystemExit(f"Virginia: the county file gives {len(out)} counties and independent cities, not 133")
    return out


# ---------------------------------------------------------------- county, city, town and school board offices

LOCAL_PAGE = INDEX + "november-3-2026-gen-elect-local-offices/"
LOCAL_HEADING = "November 3, 2026 - Local Offices"
LOCAL_LINK = re.compile(r"/candidatelist/2026/2026-November-Local-Offices-Candidate-List[^\"'<>]*\.xlsx$", re.I)
PLACE_URL = "https://www2.census.gov/geo/docs/reference/codes2020/place/st51_va_place2020.txt"
PLACE_HEAD = ["STATE", "STATEFP", "PLACEFP", "PLACENS", "PLACENAME", "TYPE", "CLASSFP", "FUNCSTAT", "COUNTIES"]
CODE_URL = "https://law.lis.virginia.gov/vacode/title24.2/chapter2/"
END = "Special Office Unexpired Term End Date"
# the only columns taken from the Local Offices list: its leftmost columns. Nothing to their right is read.
LOCAL_KEEP = ("Locality", "Office Ballot Order", "Party Ballot Order", "Office Title", "District", "Number of Seats", "Office Term",
              END, "Status", "Candidate Status", "Candidate Party", "Candidate Name")
LOCAL_REQUIRED = ("Locality", "Party Ballot Order", "Office Title", "District", "Number of Seats", END, "Candidate Party", "Candidate Name")
SRC_LOCAL, SRC_LOCAL_PAGE, SRC_PLACE = "va-elections-2026-local-offices-list", "va-elections-2026-local-offices-page", "va-census-2020-places"
NONPARTISAN = "Nonpartisan office"
# the office a title opens with: the words the list most often uses, a pattern, the office kind, and whose office it is
LOCAL_OFFICES = (
    ("Member Town Council", r"member town council", "council", "town"),
    ("Member City Council", r"member city council", "council", "city"),
    ("Member School Board", r"member school board", "school_board", "school"),
    ("Member Board of Supervisors", r"member board of supervisors", "county_commissioner", "county"),
    ("Chairman Board of Supervisors", r"chairman board of supervisors", "county_board_chair", "county"),
    ("Member County Board", r"member county board", "county_commissioner", "county"),
    ("Vice Mayor", r"vice mayor", "vice_mayor", "municipal"),
    ("Mayor", r"mayor", "mayor", "municipal"),
    ("Recorder", r"recorder", "city_recorder", "municipal"),
    ("Sheriff", r"sheriff", "sheriff", "constitutional"),
    ("Treasurer", r"treasurer", "treasurer", "constitutional"),
    ("Commonwealth's Attorney", r"commonwealth.?s attorney", "commonwealths_attorney", "constitutional"),
    ("Commissioner of Revenue", r"commissioner of (?:the )?revenue", "commissioner_of_revenue", "constitutional"),
    ("Clerk of Court", r"clerk of (?:the )?(?:circuit )?court", "clerk_of_court", "constitutional"),
)
CALENDAR = ("On November 3, 2026 the Virginia cities and towns that vote in November of even years elect mayors and councils, and "
            "where the school board is elected it is chosen at the same election; Arlington County elects a member of its County "
            "Board and of its School Board; and special elections fill vacancies in county, city and town offices for the rest of "
            "a term. Most counties elect their supervisors, sheriffs, Commonwealth's attorneys, treasurers, commissioners of the "
            "revenue and school boards in November 2027, when soil and water conservation district directors are elected too; "
            "cities elect those constitutional officers in 2029 unless a charter says otherwise; clerks of circuit court serve "
            "eight years (counties next in 2031, cities in 2027); and cities and towns whose charters set odd years, or a May "
            "election, vote then. Virginia's local governments are counties, cities and towns (it has no townships), and its judges "
            "are chosen by the General Assembly, not elected.")
CALENDAR_SOURCE = ("Code of Virginia 24.2-217, 24.2-218, 24.2-222, 24.2-222.1, 24.2-223, 24.2-226, 15.2-102, 15.2-705 and 10.1-530; "
                   "Constitution of Virginia, Article VI, Section 7; Virginia Department of Elections, 2026 November Local Offices "
                   "Candidate List")


class LayoutError(SystemExit):
    """The list no longer has the layout this loader was checked against. The message names the file, the sheet row and
    the check that failed; never what the row says."""


class Unavailable(Exception):
    """The Local Offices list or the place list was refused (a 403, a challenge page, anything but the file) and the
    cache holds no earlier copy: the local part is left out, with a gap that says so. Nothing is tried again, and no
    wall is worked around. An ordinary network failure is not this: it stops the loader, and the rows loaded before
    stay as they were."""

    def __init__(self, detail, reason):
        super().__init__(detail)
        self.reason = reason


REFUSED = (401, 403, 406, 429, 451, 503)         # the answers of a site that does not want a script
# The page builder's last check drops any note in which a number is followed by a street word ("3 towns on the place
# list" reads to it like an address). The sentences written here are tried against the same pattern, so that none of
# them is silently left off a page.
STREET_LIKE = re.compile(r"\b\d{1,6}\s+(?:[NSEW]\.?\s+)?[A-Za-z0-9.' -]{1,40}?\s(?:St|Street|Ave|Avenue|Rd|Road|Blvd|Boulevard|Dr|Drive|Ln|"
                         r"Lane|Way|Ct|Court|Cir|Circle|Pkwy|Parkway|Hwy|Highway|Trl|Trail|Pl|Place|Ter|Terrace)\b\.?", re.I)


def reads_like_contact(text):
    return bool(text) and (contact_like(text, True) or bool(STREET_LIKE.search(str(text))))


class Unplaced(Exception):
    """A row that names no place this loader can be sure of: what the contest is, and why it is not shown."""

    def __init__(self, what, reason):
        super().__init__(what)
        self.what, self.reason = what, reason


def _check(ok, label, line, what):
    if not ok:
        raise LayoutError(f"Virginia: {label}: sheet row {line} fails the layout check '{what}'; stopping (the row is not printed)")


def slug(text):
    """'Valley Springs District' -> 'valley-springs-district': letters, digits and hyphens, for ids only."""
    t = unicodedata.normalize("NFKD", text or "")
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")


def town_key(text):
    """'Mt Crawford', 'Mount Crawford', 'Lacrosse', 'La Crosse' -> one spelling, for comparing names only."""
    return "".join("mt" if w == "mount" else "st" if w == "saint" else w for w in fold(text).split())


def words_list(items):
    items = list(items)
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def plural(n, word):
    return f"{n:,} {word}{'' if n == 1 else 's'}"


def read_local_workbook(data, label):
    """The Local Offices workbook cut down, in memory, to the LOCAL_KEEP columns of its local-office rows (and, for a
    state office on it, the cells the control against the All Offices list needs). The sheet is read no further than
    the last of those columns."""
    if data[:2] != b"PK":
        raise Unavailable(f"{label} is not a workbook", "The Department of Elections' site sent something other than its Local Offices "
                          "candidate list when this was loaded, so no local race is shown; loading again asks for it once more.")
    wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    try:
        if len(wb.worksheets) != 1:
            raise LayoutError(f"Virginia: {label} has {len(wb.worksheets)} sheets, not the one this loader was checked against; stopping")
        ws = wb.worksheets[0]
        heads, start = None, 0
        for i, r in enumerate(ws.iter_rows(values_only=True, max_row=12)):       # headings only, to find the columns
            cells = [str(c).strip() if c is not None else "" for c in r]
            del r
            if all(k in cells for k in LOCAL_REQUIRED):
                heads, start = cells, i + 2
                break
            del cells
        if not heads:
            raise LayoutError(f"Virginia: {label}'s columns changed (no heading row with {', '.join(LOCAL_REQUIRED)}); stopping")
        idx = {k: heads.index(k) for k in LOCAL_KEEP if k in heads}
        last = max(idx.values()) + 1                                             # the sheet is read no further than this column
        if any(h not in LOCAL_KEEP for h in heads[:last]) or len(set(heads[:last])) != last:
            raise LayoutError(f"Virginia: {label}: a heading this loader does not take sits among the columns it reads; stopping")
        kept, state_rows, counts, n = [], [], collections.Counter(), 0
        for line, r in enumerate(ws.iter_rows(min_row=start, max_col=last, values_only=True), start):
            rec = {k: (clean(r[i]) if i < len(r) else "") for k, i in idx.items()}
            del r
            if not rec["Office Title"] and not rec["Candidate Name"]:
                continue
            n += 1
            _check(rec["Locality"] and rec["Office Title"] and rec["Candidate Name"], label, line, "locality, office title and name present")
            _check(rec["Number of Seats"].isdigit() and int(rec["Number of Seats"]) >= 1, label, line, "number of seats is a whole number")
            _check(not rec[END] or re.fullmatch(r"\d{4}-\d{2}-\d{2}", rec[END]), label, line, "unexpired-term end date is empty or a date")
            _check(not rec["Party Ballot Order"] or rec["Party Ballot Order"].isdigit(), label, line, "party ballot order is empty or a number")
            _check(not any(contact_like(v, True) for v in rec.values()), label, line, "no kept cell looks like contact details")
            what = classify(rec["Office Title"], rec["District"])
            if what is None:
                rec["_row"] = line
                kept.append(rec)
            elif isinstance(what, str):
                counts[what] += 1
            else:
                counts["state"] += 1
                state_rows.append([rec["Locality"], rec["Office Title"], rec["District"], rec["Candidate Name"], rec["Candidate Party"],
                                   rec["Party Ballot Order"]])
    finally:
        wb.close()
    return {"columns": list(idx), "rows": kept, "state_rows": state_rows, "counts": dict(counts), "all_rows": n}


def local_list(folder, say):
    """The Local Offices list, kept on disk only as its cut-down copy (JSON: the LOCAL_KEEP columns, the workbook's
    SHA-256). Asked afresh when two days old; if that fails, the copy read earlier is used."""
    path = os.path.join(folder, "va_2026_local_offices_list.json")
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < 2 * 86400:
        return path, json.load(open(path, encoding="utf-8"))
    seen = {}
    try:
        links = page_links(LOCAL_PAGE, LOCAL_HEADING, only=LOCAL_LINK, seen=seen)
        if not links:
            raise SystemExit("Virginia: the Local Offices page no longer links the 2026 November Local Offices Candidate List workbook")
        url = links[0][0]
        data = get(url, accept="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,*/*")
        got = read_local_workbook(data, os.path.basename(url))
    except (HTTPError, URLError, OSError, Unavailable) as e:
        if os.path.exists(path):
            say(f"      could not refresh the Local Offices list ({type(e).__name__}); using the copy read earlier")
            return path, json.load(open(path, encoding="utf-8"))
        if isinstance(e, HTTPError) and e.code in REFUSED:
            raise Unavailable(f"HTTP {e.code}", f"The Department of Elections' site refused this site's request for its Local Offices "
                              f"candidate list when this was loaded (it answered {e.code}), so no local race is shown; the list can "
                              "be read in a browser at the address given here.") from None
        raise
    m = re.search(r"rev-(\d{1,2})-(\d{1,2})-(\d{4})", url)
    meta = {"url": url, "page": LOCAL_PAGE, "heading": LOCAL_HEADING, "page_sha256": seen.get("sha256", ""), "page_bytes": seen.get("bytes", 0),
            "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data),
            "published": f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}" if m else "",
            "revision": f"rev. {m.group(1)}-{m.group(2)}-{m.group(3)}" if m else "", "read": dt.date.today().isoformat(), **got}
    del data
    os.makedirs(folder, exist_ok=True)
    with open(path + ".part", "w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=1)
    os.replace(path + ".part", path)
    say(f"      {os.path.basename(url)}: {got['all_rows']:,} rows, {len(got['rows']):,} of a local office "
        f"({', '.join(f'{k} {v}' for k, v in sorted(got['counts'].items())) or 'no others'})")
    return path, meta


def census_places(folder, say):
    """Virginia's incorporated places from the Census Bureau's 2020 place codes: towns by county and by name, and the
    independent cities, each with its place code. A public reference file with no personal data, cached whole."""
    path = os.path.join(folder, "st51_va_place2020.txt")
    try:
        net.download(PLACE_URL, path, 3650, tries=3, say=say)
    except HTTPError as e:
        if e.code not in REFUSED:
            raise
        raise Unavailable(f"HTTP {e.code}", "The Census Bureau's place list, which names Virginia's cities and towns, was refused to "
                          f"this site when this was loaded (it answered {e.code}), so no local race is shown yet.") from None
    towns, cities, n = collections.defaultdict(dict), {}, 0
    with open(path, encoding="utf-8", errors="replace") as fh:
        if fh.readline().rstrip("\r\n").split("|") != PLACE_HEAD:
            raise LayoutError("Virginia: st51_va_place2020.txt: the header is not the one this loader was checked against; stopping")
        for line in fh:
            f = line.rstrip("\r\n").split("|")
            if len(f) != len(PLACE_HEAD) or f[1] != FIPS or f[5] != "INCORPORATED PLACE":
                continue
            n += 1
            if f[4].endswith(" town"):
                place = {"code": f[2], "name": f[4], "counties": [c for c in f[8].split("~~~") if c]}
                for county in place["counties"]:
                    towns[fold(county)].setdefault(town_key(f[4][:-5]), []).append(place)
            elif f[4].endswith(" city"):
                cities[fold(f[4])] = {"code": f[2], "name": f[4]}
    return {"path": path, "towns": towns, "cities": cities, "n": n,
            "n_towns": len({p["code"] for by in towns.values() for hits in by.values() for p in hits})}


def one_town(towns_here, text):
    hits = towns_here.get(town_key(text), [])
    return hits[0] if len(hits) == 1 else None


def read_title(title):
    """An office title as the list writes it -> the office, and what the rest of the title says (a town, At Large, a
    seat, Special). None when it opens with no office this loader knows."""
    t = re.sub(r"\s+", " ", (title or "").replace(",", " ")).strip()
    for words, pattern, kind, scope in LOCAL_OFFICES:
        m = re.match(pattern + r"\b", t, re.I)
        if m:
            break
    else:
        return None
    out = {"office": words, "kind": kind, "scope": scope, "special": False, "at_large": False, "seat": None, "places": []}
    for piece in re.split(r"\s+-\s*|\s*-\s+", t[m.end():]):
        piece = piece.strip()
        if not piece:
            continue
        if re.fullmatch(r"special", piece, re.I):
            out["special"] = True
        elif re.fullmatch(r"at[- ]?large", piece, re.I):
            out["at_large"] = True
        elif re.fullmatch(r"seat \w+", piece, re.I):
            out["seat"] = piece
        else:
            out["places"].append(re.sub(r"^town of\s+", "", piece, flags=re.I))
    return out


def read_district(cell, own, towns_here, geo):
    """What the District cell holds: nothing, the locality itself, At Large, a town ("Town of X", "X Ward 2", a bare
    "X" that is one town of this county), two localities that share an office, or a district in the list's own words."""
    d = re.sub(r"\s+", " ", cell or "").strip()
    if not d:
        return {"kind": "none", "town": None}
    if fold(d) == fold(own):
        return {"kind": "self", "town": None}
    if re.fullmatch(r"at[- ]?large", d, re.I):
        return {"kind": "at_large", "town": None}
    m = re.fullmatch(r"town of (.+)", d, re.I)
    if m:
        return {"kind": "town_of", "town": one_town(towns_here, m.group(1)), "text": d}
    m = re.fullmatch(r"(.+?) (ward \w+)", d, re.I)
    if m and one_town(towns_here, m.group(1)):
        return {"kind": "town_ward", "town": one_town(towns_here, m.group(1)), "ward": m.group(2), "text": d}
    if one_town(towns_here, d):
        return {"kind": "bare_town", "town": one_town(towns_here, d), "text": d}
    if "," in d:
        named = [geo.get(fold(p)) for p in d.split(",")]
        if all(named) and len({g for g, _n in named}) == len(named) > 1:
            return {"kind": "localities", "town": None, "localities": named, "text": d}
    return {"kind": "text", "town": None, "text": d}


def contest_of(r, geo, places, backed):
    """One row of the Local Offices list -> the contest it belongs to: level, office, jurisdiction, district, seat.
    Raises Unplaced for a row whose place cannot be read with certainty; nothing is guessed."""
    geoid, own = geo[fold(r["Locality"])]
    is_city = own.endswith(" city")
    t = read_title(r["Office Title"])
    if t is None:
        raise Unplaced(re.sub(r"\s+", " ", r["Office Title"]).strip()[:80],
                       "The Department of Elections' list gives this contest an office title this site does not know yet, so it is "
                       "not shown.")
    special = 1 if (t["special"] or r[END]) else 0
    what = t["office"] + (" (special election)" if special else "") + (f", {r['District']}" if r["District"] else "")
    towns_here = {} if is_city else places["towns"].get(fold(own), {})
    d = read_district(r["District"], own, towns_here, geo)
    named = {}
    for p in t["places"]:
        hit = one_town(towns_here, p)
        if not hit:
            raise Unplaced(what, f"The Department of Elections' list files this contest under {own} with a title that names a place "
                                 f"which is not one town of {own} on the Census Bureau's place list, so it is not shown.")
        named[hit["code"]] = hit
    if d["kind"] == "town_of" and not d["town"]:
        raise Unplaced(what, f"The Department of Elections' list files this contest under {own} for a town that is not one town of "
                             f"{own} on the Census Bureau's place list, so it is not shown.")
    unclear = Unplaced(what, f"The Department of Elections' list files this contest under {own} in a way this site cannot read with "
                             "certainty (the office and the District cell do not fit together), so it is not shown.")
    seat = t["seat"] or ("At Large" if t["at_large"] or d["kind"] == "at_large" else None)
    kind, scope, district, how, shared, place = t["kind"], t["scope"], None, None, None, None

    def town_office(town):
        return "city", town["name"], f"{STATE}-M-{town['code']}", "M" + town["code"], ("mcd", f"{STATE}-M-{town['code']}", town["name"], SRC_PLACE)

    def city_office():
        city = places["cities"].get(fold(own))
        if not city:
            raise unclear
        return "city", city["name"], f"{STATE}-M-{city['code']}", "M" + city["code"], ("mcd", f"{STATE}-M-{city['code']}", city["name"], SRC_PLACE)

    if scope == "town" or (scope == "municipal" and not is_city):            # a town's council, mayor, vice mayor or recorder
        if is_city or d["kind"] == "localities":
            raise unclear
        if d["town"]:
            named[d["town"]["code"]] = d["town"]
        if len(named) > 1:
            raise unclear
        if named:
            town = next(iter(named.values()))
        else:
            every = {p["code"]: p for hits in towns_here.values() for p in hits}
            if len(every) != 1:
                raise Unplaced(what, f"The Department of Elections' list files this contest under {own} without naming the town, and "
                                     f"the Census Bureau lists {len(every) or 'no'} towns in {own}, so it is not shown here; the "
                                     "county registrar's sample ballot names the town.")
            town = next(iter(every.values()))
            how = (f"The Department's list does not name the town for this contest; {town['name'][:-5]} is the only town in "
                   f"{own} on the Census Bureau's place list.")
        district = d["ward"] if d["kind"] == "town_ward" else d["text"] if d["kind"] == "text" else None
        level, jurisdiction, jid, jpart, place = town_office(town)
    elif scope in ("city", "municipal"):                                       # an independent city's council or mayor
        if not is_city or named or d["kind"] not in ("none", "self", "at_large", "text"):
            raise unclear
        district = d["text"] if d["kind"] == "text" else None
        level, jurisdiction, jid, jpart, place = city_office()
    elif scope == "county":                                                    # supervisors, Arlington's County Board
        if is_city or named or d["kind"] in ("town_of", "localities"):
            raise unclear
        district = d.get("text") if d["kind"] in ("text", "town_ward", "bare_town") else None
        level, jurisdiction, jid, jpart = "county", own, geoid, geoid
    elif scope == "constitutional":                                            # sheriff, treasurer, prosecutor, revenue, clerk
        if d["kind"] == "town_of":
            named[d["town"]["code"]] = d["town"]
        if len(named) > 1 or d["kind"] in ("town_ward", "bare_town", "text", "at_large"):
            raise unclear
        if named:                                                              # a town's own officer (a town treasurer)
            if is_city:
                raise unclear
            level, jurisdiction, jid, jpart, place = town_office(next(iter(named.values())))
        elif d["kind"] == "localities":                                        # an office a city shares with a county
            counties = [(g, n) for g, n in d["localities"] if not n.endswith(" city")]
            if len(counties) != 1 or geoid not in {g for g, _n in d["localities"]}:
                raise unclear
            shared = sorted(g for g, _n in d["localities"])
            level, jid, jpart = "county", counties[0][0], counties[0][0]
            jurisdiction = words_list([counties[0][1]] + sorted(n for g, n in d["localities"] if g != counties[0][0]))
        elif is_city:
            level, jurisdiction, jid, jpart, place = city_office()
        else:
            level, jurisdiction, jid, jpart = "county", own, geoid, geoid
        if kind == "treasurer":
            kind = "county_treasurer" if level == "county" else "city_treasurer"
    else:                                                                      # an elected school board
        if d["kind"] == "localities":
            raise unclear
        if d["town"] and (d["kind"] == "town_of" or named or (geoid, d["town"]["code"]) in backed):
            named[d["town"]["code"]] = d["town"]
        elif d["town"]:
            raise Unplaced(what, f"The Department of Elections' list files this school board contest under {own} with a District that "
                                 "is also a town's name, and nothing on the list says whether it is that town's own school board, so "
                                 "it is not shown.")
        if len(named) > 1 or (named and is_city):
            raise unclear
        if named:                                                              # a town's own school board
            town = next(iter(named.values()))
            first = min(geo[fold(c)][0] for c in town["counties"] if fold(c) in geo)
            base, key = town["name"], f"{first[2:]}-{slug(town['name'])}"
            district = d["ward"] if d["kind"] == "town_ward" else None
        else:
            base, key = own, f"{geoid[2:]}-{slug(own)}"
            district = d["text"] if d["kind"] == "text" else None
        level, jurisdiction, jid, jpart = "school", f"{base} school board", f"{STATE}-S-{key}", "S" + key
        place = ("school", jid, jurisdiction, SRC_LOCAL)
    race_id = f"2026-{STATE}-" + "-".join([jpart, kind.replace("_", "-")] + [slug(x) for x in (district, seat) if x]) + ("-S" if special else "")
    return {"race_id": race_id, "level": level, "office_kind": kind, "office": t["office"], "jurisdiction": jurisdiction,
            "jurisdiction_id": jid, "district": district, "seat": seat, "special": special, "how": how, "shared": shared, "place": place,
            "said_special": t["special"]}


def build_local(meta, geo, places):
    """The Local Offices list's rows as contests and candidates: every row in exactly one contest, or in sl_gaps with
    the reason. Returns the rows for sl_races, sl_candidates, sl_places and sl_gaps, the CHECK lines and the counts."""
    rows, problems = meta["rows"], []
    # The Party Ballot Order is one number to a party (the party group's place on the ballot), not a candidate's own
    # place, so no ballot order is stored for local offices. If that ever changes, say so.
    order_of = collections.defaultdict(set)
    for r in rows:
        order_of[r["Candidate Party"]].add(r["Party Ballot Order"])
    if any(len(v) != 1 for v in order_of.values()) or len({next(iter(v)) for v in order_of.values()}) != len(order_of):
        problems.append("local: the Party Ballot Order column is no longer one number to a party; read the list again (it may now "
                        "give each candidate's own place)")
    # towns the list itself shows to have a school board of their own (so a bare town name in a later row can be trusted)
    backed = set()
    for r in rows:
        loc, t = geo.get(fold(r["Locality"])), read_title(r["Office Title"])
        if not loc or not t or t["scope"] != "school" or loc[1].endswith(" city"):
            continue
        towns_here = places["towns"].get(fold(loc[1]), {})
        d = read_district(r["District"], loc[1], towns_here, geo)
        for p in [one_town(towns_here, x) for x in t["places"]] + ([d["town"]] if d["kind"] == "town_of" else []):
            if p:
                backed.add((loc[0], p["code"]))

    races, gaps, gone, placed = {}, {}, 0, 0
    for r in rows:
        status = (r.get("Status") or r.get("Candidate Status") or "").lower()
        if any(g in status for g in GONE):
            gone += 1
            continue
        loc = geo.get(fold(r["Locality"]))
        try:
            if not loc:
                raise Unplaced(re.sub(r"\s+", " ", r["Office Title"]).strip()[:80],
                               "The Department of Elections' list files this contest under a locality the Census Bureau's county "
                               "file does not name, so it is not shown.")
            c = contest_of(r, geo, places, backed)
        except Unplaced as u:
            key = ("county", loc[0], loc[1], u.what) if loc else ("state", STATE, NAME, u.what)
            g = gaps.setdefault(key, {"reason": u.reason, "names": set(), "rows": 0})
            g["names"].add(r["Candidate Name"])
            g["rows"] += 1
            continue
        race = races.get(c["race_id"])
        if race is None:
            race = races[c["race_id"]] = dict(c, localities={}, ends=set(), seats=set(), people={}, hows=set(), rows=0)
        elif any(race[k] != c[k] for k in ("level", "office_kind", "office", "jurisdiction", "jurisdiction_id", "district", "seat", "special")):
            raise SystemExit(f"Virginia: two different contests of the Local Offices list share the race id {c['race_id']}; stopping")
        race["localities"][loc[0]] = loc[1]
        race["ends"].add(r[END])
        race["seats"].add(r["Number of Seats"])
        race["rows"] += 1
        if c["how"]:
            race["hows"].add(c["how"])
        if c["said_special"] and not r[END]:
            problems.append(f"{c['race_id']}: the title says Special but the list gives no unexpired-term end date")
        p = race["people"].setdefault(r["Candidate Name"], {"orders": set(), "places": collections.Counter(), "party": set()})
        p["orders"].add(r["Party Ballot Order"])
        p["places"][loc[0]] += 1
        p["party"].add(r["Candidate Party"])
        placed += 1

    race_rows, cand_rows, place_of = [], [], {}
    for rid in sorted(races):
        race = races[rid]
        cids = sorted(set(race["localities"]) | set(race["shared"] or ()))
        if race["shared"] and set(race["shared"]) != set(race["localities"]):
            problems.append(f"{rid}: the District cell names {len(race['shared'])} localities but its rows are filed under {len(race['localities'])}")
        if race["place"] and race["place"][0] == "mcd" and race["jurisdiction"].endswith(" town"):
            census = {geo[fold(c)][0] for hits in places["towns"].values() for ps in hits.values() for p in ps
                      if p["code"] == race["place"][1].rsplit("-", 1)[-1] for c in p["counties"] if fold(c) in geo}
            if not set(race["localities"]) <= census:
                problems.append(f"{rid}: filed under a county the Census Bureau's place list does not give for {race['jurisdiction']}")
        notes = []
        seats = sorted(race["seats"])
        if len(seats) != 1:
            problems.append(f"{rid}: the list gives {seats} seats")
        elif int(seats[0]) > 1:
            notes.append(f"Voters choose up to {int(seats[0])}.")
        if race["special"]:
            ends = sorted(race["ends"] - {""})
            if len(ends) == 1:
                day = dt.date.fromisoformat(ends[0])
                notes.append(f"A special election for the rest of a term that ends {day:%B} {day.day}, {day.year}.")
            else:
                notes.append("A special election for the rest of a term.")
                if len(ends) > 1:
                    problems.append(f"{rid}: the list gives more than one unexpired-term end date ({ends})")
        elif race["ends"] - {""}:
            problems.append(f"{rid}: an unexpired-term end date on some rows only")
        if len(cids) > 1:
            notes.append("On the ballot in " + words_list(sorted(geo_name(geo, c) for c in cids))
                         + " (the localities the Department's list gives for this office).")
        notes += sorted(race["hows"])
        people = race["people"]
        for p in people.values():
            if set(p["places"]) != set(race["localities"]):
                problems.append(f"{rid}: a candidate is listed in {len(p['places'])} of the contest's {len(race['localities'])} localities")
            if max(p["places"].values()) > 1:
                problems.append(f"{rid}: a candidate is listed twice in one locality")
            if len(p["orders"]) > 1 or len(p["party"]) > 1:
                problems.append(f"{rid}: a candidate's party or party ballot order differs between localities")
        seen, caps_any = set(), False
        for raw, p in people.items():
            name, caps = shown(raw)
            if name in seen:
                raise SystemExit(f"Virginia: the same name twice in the contest {rid}; stopping (the name is not printed)")
            seen.add(name)
            caps_any |= caps
            write_in = int(any("write" in x.lower() for x in p["party"]))
            cand_rows.append((rid, "general", GENERAL, name, NONPARTISAN, "N", None, 0, write_in, None, None, None, None,
                              SRC_LOCAL, join(CAPS if caps else "", WRITE_IN if write_in else "")))
        if caps_any:
            notes.append(CAPS)
        race_rows.append((rid, STATE, race["level"], race["office_kind"], race["office"], race["jurisdiction"], race["jurisdiction_id"],
                          json.dumps(cids), race["district"], race["seat"], race["special"], 0, None, None, None, GENERAL,
                          " ".join(notes) or None))
        if race["place"]:
            kind, pid, pname, src = race["place"]
            place_of.setdefault((kind, pid), {"name": pname, "src": src, "counties": set()})["counties"] |= set(cids)
    place_rows = [(kind, pid, e["name"], json.dumps(sorted(e["counties"])), e["src"]) for (kind, pid), e in sorted(place_of.items())]
    gap_rows, unplaced = [], 0
    for (scope, pid, pname, what), g in sorted(gaps.items()):
        unplaced += g["rows"]
        n = len(g["names"])
        gap_rows.append((STATE, scope, pid, pname, what, g["reason"] + f" The list names {n} candidate{'s' if n != 1 else ''} for it.", LOCAL_PAGE))
    levels = collections.Counter(r[2] for r in race_rows)
    kinds = collections.Counter(r[3] for r in race_rows)
    reached = {c for r in race_rows for c in json.loads(r[7])}
    return {"races": race_rows, "cands": cand_rows, "places": place_rows, "gaps": gap_rows, "problems": problems,
            "rows": len(rows), "placed": placed, "unplaced": unplaced, "unplaced_contests": len(gaps), "gone": gone,
            "levels": dict(levels), "kinds": dict(kinds), "reached": len(reached),
            "specials": sum(1 for r in race_rows if r[10]), "parties": {k: len([1 for r in rows if r["Candidate Party"] == k]) for k in order_of},
            "party_orders": {k: sorted(v) for k, v in order_of.items()},
            "two_county": sum(1 for r in race_rows if len(json.loads(r[7])) > 1), "copies": placed - len(cand_rows),
            "statuses": dict(collections.Counter((r.get("Status") or r.get("Candidate Status") or "") for r in rows))}


def geo_name(geo, geoid):
    return next(name for g, name in geo.values() if g == geoid)


# ---------------------------------------------------------------- load

def load(db_path, say=print, cache=CACHE, roster_path=ROSTER):
    net.patient_lookups()
    folder = os.path.join(cache, "va")
    os.makedirs(folder, exist_ok=True)
    all_path, main, specials = lists(folder, say)
    members, officers = roster(roster_path)
    geo = county_codes() if os.path.exists(COUNTY_ZIP) else {}
    problems = []

    # the races and their candidates, from the All Offices list (the special lists are the control)
    races, by_race, gone = {}, collections.defaultdict(list), []
    for r in main["rows"]:
        status = (r.get("Status") or r.get("Candidate Status") or "").lower()
        if any(g in status for g in GONE):
            gone.append(r)
            continue
        race = classify(r["Office Title"], r["District"])
        races.setdefault(race["race_id"], race)
        by_race[race["race_id"]].append(r)
    for text, meta in specials:
        for r in meta["rows"]:
            race = classify(r["Office Title"], r["District"])
            if race["race_id"] not in races:
                problems.append(f"{race['race_id']}: on the special-election list ({text}) but not on the All Offices list; "
                                "stored from the special-election list")
                races[race["race_id"]] = race
                by_race[race["race_id"]] += [dict(x, _from=special_sid(meta["url"])) for x in meta["rows"]
                                             if classify(x["Office Title"], x["District"])["race_id"] == race["race_id"]]

    cands, place_rows, unknown_localities = [], [], set()
    ends = {}
    for rid, race in races.items():
        rows = by_race[rid]
        localities = sorted({r.get("Locality", "") for r in rows if r.get("Locality")})
        cids = sorted({geo[fold(l)][0] for l in localities if fold(l) in geo})
        unknown_localities |= {l for l in localities if geo and fold(l) not in geo}
        race["county_ids"] = json.dumps(cids) if cids else None
        seats = {r.get("Number of Seats") for r in rows} - {""}
        end = {r.get("Special Office Unexpired Term End Date") for r in rows} - {""}
        ends[rid] = sorted(end)
        race["special"] = 1 if end else 0
        race["seat"] = None
        race["partisan"] = 1
        if seats - {"1"}:
            problems.append(f"{rid}: the list gives {sorted(seats)} seats")
        if not end:
            problems.append(f"{rid}: a state office with no unexpired-term end date on a {GENERAL[:4]} list (a regular race "
                            "in an even year is not expected); read the list again")
        if len(end) > 1:
            problems.append(f"{rid}: the list gives more than one term end date ({sorted(end)})")
        # each candidate once, the same in every locality
        people = {}
        for r in rows:
            key = r["Candidate Name"]
            people.setdefault(key, {"row": r, "orders": set(), "places": set(), "parties": set(), "marks": set()})
            people[key]["orders"].add(r.get("Party Ballot Order", ""))
            people[key]["places"].add(r.get("Locality", ""))
            people[key]["parties"].add(r["Candidate Party"])
            people[key]["marks"].add((r.get("Incumbent") or "").strip().lower())
        for key, p in people.items():
            if p["places"] != set(localities or [""]):
                problems.append(f"{rid}: a candidate is listed in {len(p['places'])} of the race's {len(localities)} localities")
            if len(p["orders"]) > 1 or len(p["parties"]) > 1:
                problems.append(f"{rid}: a candidate's ballot order or party differs between localities")
        orders = [next(iter(p["orders"])) for p in people.values()]
        if len(set(orders)) != len(orders):
            problems.append(f"{rid}: two candidates share a ballot order")
        # who holds the seat today
        if race["chamber"]:
            sitting = [m for m in members if m["chamber"] == race["chamber"] and str(m["district"]) == race["district"]]
        else:
            sitting = officers.get(STATEWIDE[race["office"]][3], [])
        race["holder_id"] = "; ".join(m["id"] for m in sitting) or None
        race["holder_name"] = "; ".join(m["full"] for m in sitting) or None
        race["holder_party"] = "; ".join(m["party"] or "" for m in sitting) or None
        caps_any = False
        marked = []
        for key, p in sorted(people.items(), key=lambda kv: int(next(iter(kv[1]["orders"])) or 99)):
            r = p["row"]
            name, caps = shown(key)
            caps_any |= caps
            party = r["Candidate Party"]
            write_in = int("write" in party.lower())
            order = next(iter(p["orders"]))
            who = one_fit(key, sitting) if race["chamber"] else None
            if "yes" in p["marks"]:
                marked.append(name)
            src = r.get("_from") or SRC_ALL
            cands.append((rid, "general", GENERAL, name, party, party_code(party), int(order) if order.isdigit() else None,
                          1 if who else 0, write_in, None, None, None, who["id"] if who else None, src,
                          join(CAPS if caps else "", WRITE_IN if write_in else "")))
        if sitting and not any(name_fits(n, m) for n in marked for m in sitting):
            problems.append(f"{rid}: the list marks {marked or 'no one'} as the incumbent; the roster's holder is {race['holder_name']}")
        if marked and not sitting:
            problems.append(f"{rid}: the list marks {marked} as the incumbent, but the roster lists nobody in the seat")
        term = ""
        if len(end) == 1:
            ends_on = dt.date.fromisoformat(next(iter(end)))
            term = f" The term ends {ends_on:%B} {ends_on.day}, {ends_on.year} (the list's Special Office Unexpired Term End Date)."
        race["note"] = join("A special election to fill the seat for the rest of the term." + term if race["special"] else "",
                            "The roster used here lists nobody in this seat today." if not sitting else "",
                            "On the ballot in " + ", ".join(geo[fold(l)][1] if fold(l) in geo else l.title() for l in localities)
                            + " (the localities the Department's list gives for this office)." if localities else "",
                            CAPS if caps_any else "")
        if race["place"]:
            kind, pid, pname = race["place"]
            place_rows.append((kind, pid, pname, race["county_ids"], SRC_ALL))
    if unknown_localities:
        problems.append(f"localities the Census file does not name: {sorted(unknown_localities)}")

    # the control: every special-election list agrees with the All Offices list, locality by locality
    special_sources = []
    for text, meta in specials:
        mine = {(classify(r["Office Title"], r["District"])["race_id"], r.get("Locality", ""), r["Candidate Name"],
                 r["Candidate Party"], r.get("Party Ballot Order", "")) for r in meta["rows"]}
        theirs = {(classify(r["Office Title"], r["District"])["race_id"], r.get("Locality", ""), r["Candidate Name"],
                   r["Candidate Party"], r.get("Party Ballot Order", "")) for r in main["rows"]
                  if classify(r["Office Title"], r["District"])["race_id"] in {m[0] for m in mine}}
        agree = mine == theirs
        if not agree:
            problems.append(f"{text}: {len(mine - theirs)} rows not on the All Offices list, {len(theirs - mine)} All Offices rows "
                            "not on it")
        sid = special_sid(meta["url"])
        special_sources.append((sid, STATE, "official candidate list", "Virginia Department of Elections", text,
                                meta["url"], meta["published"], meta["read"], meta["sha256"], len(meta["rows"]),
                                f"Linked from the Candidates & Referendums page ({INDEX}). Read as a control, the same allowed "
                                f"columns only ({', '.join(meta['columns'])}); the campaign e-mail, website, phone and address "
                                "columns are never read. "
                                + ("Every row (candidate, party, ballot order, locality) is the All Offices list's for this race."
                                   if agree else "It differs from the All Offices list; see the loader's CHECK lines.")
                                + " SHA-256 is the workbook's."))

    # the primaries: any state contest?
    pri_sources, fields, unreconciled = [], 0, []
    for party in PRIMARIES:
        ppath, res = primary_state_contests(folder, party, say)
        n_rows = 0
        for c in res["contests"]:
            rid = c["race"]
            names = [o for o in c["options"] if not o["write_in"]]
            total = sum(o["votes"] for o in c["options"])
            if total != c["vote_total"]:
                unreconciled.append(f"{rid} {party}: candidates {total:,} against the summary's total {c['vote_total']:,}")
            for o in c["options"]:
                if c.get("precinct_sums", {}).get(o["name"], 0) != o["votes"]:
                    unreconciled.append(f"{rid} {party} {o['name']}: precincts {c.get('precinct_sums', {}).get(o['name'], 0):,}, summary {o['votes']:,}")
            if rid not in races:
                problems.append(f"{rid}: a {party} primary contest on August 4 but no November race")
                continue
            if len(names) < 2:
                continue
            winners = [o for o in names if o["winner"]]
            top = max(names, key=lambda o: o["votes"])
            if len(winners) != 1 or winners[0] is not top:
                problems.append(f"{rid} {party}: the winner marked is not the one top vote-getter; no outcome stored")
                winners = []
            fields += 1
            sitting = [m for m in members if races[rid]["chamber"] and m["chamber"] == races[rid]["chamber"]
                       and str(m["district"]) == races[rid]["district"]]
            for o in names:
                name, caps = shown(o["name"])
                who = one_fit(o["name"], sitting) if sitting else None
                cands.append((rid, f"primary-{CODE[party]}", PRIMARY, name, party, party_code(party), None, 1 if who else 0, 0,
                              o["votes"], round(100 * o["votes"] / total, 1) if total else None,
                              ("advanced" if o is winners[0] else "lost") if winners else None, who["id"] if who else None,
                              SRC_PRI[party], CAPS if caps else None))
                n_rows += 1
        pri_sources.append((SRC_PRI[party], STATE, "official results", "Virginia Department of Elections",
                            f"Election results: {res['name']} (August 4, 2026), official results",
                            res["site"], (res.get("as_of") or "")[:10], day_of(ppath), res["data_sha256"], n_rows,
                            f"The results site marks these results official (as of {(res.get('as_of') or '')[:10]}); statewide summary "
                            f"{res['data_url']}, SHA-256 {res['data_sha256'][:16]}... (the SHA-256 column). Contests: "
                            f"{res['federal_contests']} federal, {len(res['contests'])} for a state office, {res['other_contests']} other. "
                            + ("No state office was on this primary: no state primary field is stored." if not res["contests"] else
                               f"State primary rows stored: {n_rows}; precinct report {res['report_url']} (SHA-256 "
                               f"{res['report_sha256'][:16]}...) " + ("adds up to the summary." if not [u for u in unreconciled if f' {party}' in u]
                                                                        else "differs: " + "; ".join(u for u in unreconciled if f' {party}' in u)))))
    for rid, race in races.items():
        if not any(c[0] == rid and c[1].startswith("primary-") for c in cands):
            race["note"] = join(race["note"], NO_PRIMARY)

    # CHECKS: every race has its candidates; every state row read is stored
    gen_rows = sum(1 for c in cands if c[1] == "general")
    distinct = len({(classify(r["Office Title"], r["District"])["race_id"], r["Candidate Name"]) for r in main["rows"]
                    if not any(g in (r.get("Status") or r.get("Candidate Status") or "").lower() for g in GONE)})
    distinct += sum(1 for c in cands if c[1] == "general" and c[13] != SRC_ALL)
    if gen_rows != distinct:
        problems.append(f"November: {distinct} candidates on the lists, {gen_rows} stored")
    empty = [rid for rid in races if not any(c[0] == rid and c[1] == "general" for c in cands)]
    if empty:
        problems.append(f"races with no November candidate: {empty}")
    problems += unreconciled

    # ---- county, city, town and school board offices, from the Local Offices list (see the docstring)
    local, lmeta, lplaces, local_gaps, control = None, None, None, [], ""
    try:
        if not geo:
            raise Unavailable("the county file is not in states_cache/census", "The Census Bureau's county file, which turns the list's "
                              "localities into county codes, was not in this site's cache when this was loaded, so no local race is "
                              "shown yet.")
        _lpath, lmeta = local_list(os.path.join(folder, "local"), say)
        lplaces = census_places(os.path.join(folder, "local"), say)
        local = build_local(lmeta, geo, lplaces)
    except Unavailable as e:
        say(f"      Virginia local: not loaded ({e})")
        local_gaps.append((STATE, "state", STATE, NAME, "county, city, town and school board races", e.reason, LOCAL_PAGE))
    local_races, local_cands = (local["races"], local["cands"]) if local else ([], [])
    if local:
        clash = sorted({r[0] for r in local_races} & set(races))
        if clash:
            raise SystemExit(f"Virginia: a local contest and a state race share a race id ({clash[:3]}); stopping")
        problems += local["problems"]
        local_gaps += local["gaps"]
        local_gaps.append((STATE, "state", STATE, NAME, "contests nobody qualified for",
                           "The Department of Elections' list names only candidates who qualified for the ballot, so a contest that "
                           "no one qualified for, which voters decide by writing a name in, is not on the list and is not shown here; "
                           "the general registrar's sample ballot for each locality lists every contest.", LOCAL_PAGE))
        # the control: the All Offices list of the same revision counts the same local rows and carries the same state rows
        if main.get("published") and main.get("published") == lmeta.get("published"):
            all_local = main.get("counts", {}).get("local", 0)
            mine = sorted(tuple(x) for x in lmeta.get("state_rows", []))
            theirs = sorted((r.get("Locality", ""), r["Office Title"], r["District"], r["Candidate Name"], r["Candidate Party"],
                             r.get("Party Ballot Order", "")) for r in main["rows"])
            if all_local != local["rows"]:
                problems.append(f"local: the Local Offices list has {local['rows']} local rows, the All Offices list of the same revision {all_local}")
            if mine != theirs:
                problems.append("local: the Local Offices list's rows of a state office are not the All Offices list's")
            control = (f"The All Offices list of the same revision counts {all_local:,} rows of a local office ("
                       + ("the same" if all_local == local["rows"] else "not the same") + "), and its rows of a state office "
                       + ("are" if mine == theirs else "are not") + " this list's.")
        else:
            control = "The All Offices list in the cache is another revision, so the two lists were not compared."

    for folded, (geoid, label) in sorted(geo.items(), key=lambda kv: kv[1][0]):
        place_rows.append(("county", geoid, label, json.dumps([geoid]), SRC_COUNTY))
    if local:
        place_rows += local["places"]
    race_rows = [(r["race_id"], STATE, r["level"], r["office_kind"], r["office"], r["jurisdiction"], r["jurisdiction_id"],
                  r["county_ids"], r["district"], r["seat"], r["special"], r["partisan"], r["holder_id"], r["holder_name"],
                  r["holder_party"], GENERAL, r["note"]) for r in races.values()]
    by_kind = collections.Counter(r["office_kind"] + ("_special" if r["special"] else "") for r in races.values())
    counts = main.get("counts", {})
    sources = [
        (SRC_ALL, STATE, "official candidate list", "Virginia Department of Elections",
         f"2026 November All Offices Candidate List ({main['heading']}" + (f", {main['revision']})" if main["revision"] else ")"),
         main["url"], main["published"], main["read"], main["sha256"], len(main["rows"]),
         f"Linked from {main['page']}. Only these columns are read: {', '.join(main['columns'])}; the campaign e-mail, website, "
         "phone and address columns are never read (the sheet is read no further than the last of these), and for a row "
         "that is not a state office only the Office Title is looked at. SHA-256 is the workbook's. "
         f"Rows on the list: {main['all_rows']} ({counts.get('federal', 0)} federal, left to the federal pages; "
         f"{counts.get('local', 0)} local offices, read from the Department's Local Offices list instead; {len(main['rows'])} of a "
         f"state office, one per candidate per locality). Withdrawn or removed, left off: {len(gone)}. " + ODD_YEARS
         + (" State races on this list: " + ", ".join(sorted(races)) + "." if races else " This list carries no state race."))]
    sources += special_sources + pri_sources
    notes = [(STATE, "local_calendar", CALENDAR, CALENDAR_SOURCE, CODE_URL)]
    if local:
        statuses = ", ".join(f"{k} {v:,}" for k, v in sorted(local["statuses"].items())) or "none given"
        sources.append((SRC_LOCAL, STATE, "official candidate list", "Virginia Department of Elections",
                        f"2026 November Local Offices Candidate List ({lmeta['heading']}" + (f", {lmeta['revision']})" if lmeta["revision"] else ")"),
                        lmeta["url"], lmeta["published"], lmeta["read"], lmeta["sha256"], local["rows"],
                        "Linked as \"Download this file\" from the Department's page \"November 3, 2026 - Local Offices\" (Candidates & "
                        f"Referendums). Only these columns are read: {', '.join(lmeta['columns'])}. The sheet is read no further than the "
                        "Candidate Name column: the Incumbent column and the campaign e-mail, website, phone and address columns to its "
                        "right are never read, and only the cut-down copy is cached. SHA-256 is the workbook's. "
                        f"Rows on the list: {lmeta['all_rows']:,}, one per candidate per locality: {lmeta['counts'].get('state', 0)} of a state "
                        f"office (stored from the All Offices list), {local['rows']:,} of a local office"
                        + (f", {lmeta['counts']['federal']} federal" if lmeta["counts"].get("federal") else "")
                        + f". Of the local rows {local['placed']:,} are placed, each in exactly one contest, giving {len(local_cands):,} "
                        f"candidates in {len(local_races):,} contests ({local['copies']} rows are a second locality's copy of a candidate, "
                        f"for a town in two counties or an office two localities share); {local['unplaced']} rows of "
                        f"{plural(local['unplaced_contests'], 'contest')} could not be placed and are listed as gaps; withdrawn or removed, "
                        f"left off: {local['gone']}. Status values on the list: {statuses}. Party is not shown (the ballot prints none for local "
                        "offices). No ballot order is stored: the Party Ballot Order column is the place of a candidate's party group ("
                        + ", ".join(f"{k} {'/'.join(v)}" for k, v in sorted(local["party_orders"].items(), key=lambda kv: kv[1]))
                        + "), and independents are printed in the order they filed, which the list does not give. " + control))
        if lmeta.get("page_sha256"):
            sources.append((SRC_LOCAL_PAGE, STATE, "official page", "Virginia Department of Elections",
                            f"{lmeta['heading']} (the page that links the Local Offices list)", lmeta["page"], "",
                            lmeta["read"], lmeta["page_sha256"], 1,
                            "Read for one thing only, the address of the workbook it offers as \"Download this file\". Nothing else on "
                            "the page is taken, kept or shown, and no other link of the page is collected. SHA-256 is the page's as "
                            "fetched; rows is the one link taken."))
        sources.append((SRC_PLACE, STATE, "official place codes", "U.S. Census Bureau", "2020 place codes, Virginia (st51_va_place2020.txt)",
                        PLACE_URL, "", day_of(lplaces["path"]), sha_of(lplaces["path"]), lplaces["n"],
                        f"Virginia's incorporated places: {len(lplaces['cities'])} independent cities and {lplaces['n_towns']} towns, with "
                        "the counties each town lies in. Used to name each contest's city or town as the Bureau writes it and to give it "
                        "its place code; a town is taken only when the list's words fit exactly one town of the county. A public "
                        "reference file with no personal data."))
        notes.append((STATE, "local_coverage",
                      "Loaded from the Virginia Department of Elections' 2026 November Local Offices Candidate List"
                      + (f" ({lmeta['revision']})" if lmeta["revision"] else "") + f": {len(local_races):,} contests and {len(local_cands):,} "
                      f"candidates for county, city, town and school board offices, reaching {local['reached']} of Virginia's 133 counties and "
                      f"independent cities; {local['specials']} of the contests are special elections for the rest of a term. Names are as "
                      "the list prints them, and a school board contest is filed under the county, city or town whose ballot carries it "
                      "(the list does not name the school division). Not shown: the list's party column, because Virginia prints no "
                      "party beside a name for local offices; the ballot order, because the list gives only the place of each candidate's "
                      "party group, and independents, who are nearly all the candidates, are printed in the order they filed; contests "
                      "nobody qualified for, which are decided by write-in and are not on the list"
                      + (f"; {plural(local['unplaced_contests'], 'contest')} that could not be filed with certainty (listed among the gaps)"
                         if local["unplaced_contests"] else "")
                      + "; and the proposed constitutional amendments and local referendums, which the Department lists on a page of "
                      "their own.",
                      "Virginia Department of Elections, 2026 November Local Offices Candidate List; Code of Virginia 24.2-613 (what a "
                      "ballot prints beside a name, and the order of names)", LOCAL_PAGE))
    else:
        notes.append((STATE, "local_coverage", "No county, city, town or school board race is loaded for Virginia yet: the Department of "
                      "Elections' Local Offices candidate list could not be read when this was loaded.",
                      "Virginia Department of Elections, 2026 November Local Offices Candidate List", LOCAL_PAGE))
    if geo:
        sources.append((SRC_COUNTY, STATE, "boundaries", "U.S. Census Bureau",
                        "Cartographic boundary file, counties, 2024, 1:500,000 (cb_2024_us_county_500k)", COUNTY_URL, "",
                        day_of(COUNTY_ZIP), sha_of(COUNTY_ZIP), len(geo),
                        "Virginia's 95 counties and 38 independent cities: names and GEOIDs only, to turn the list's localities into codes."))
    if members or officers:
        sources.append((SRC_ROSTER, STATE, "roster", "Open States (people project, CC0)",
                        "Virginia legislators and statewide officers serving now (state_va.sqlite, from the Open States people project)",
                        "https://github.com/openstates/people", "", day_of(roster_path), "", len(members) + sum(map(len, officers.values())),
                        "Used only to say who holds each seat today and to mark incumbents: names, parties and districts. Not an official record."))

    # the sentences written here, tried against the page's last check (see STREET_LIKE)
    for table, key, text in ([("sl_races.note", r[0], r[16]) for r in local_races]
                             + [("sl_gaps", f"{g[1]} {g[2]}", " ".join(x for x in g[3:6] if x)) for g in local_gaps]
                             + [("sl_notes", n[1], n[2]) for n in notes]):
        if reads_like_contact(text):
            problems.append(f"{table} {key}: this sentence would read as contact details to the page's last check and be left out; reword it")

    # Virginia's rows only, in one transaction: races and candidates by state and race id, sources, gaps and notes by
    # state, places by their va- source ids. Other states' loaders share this database; nothing of theirs is touched.
    con = sqlite3.connect(db_path)
    try:
        con.executescript(SCHEMA + EXTRA_SCHEMA)
        with con:
            con.execute("DELETE FROM sl_candidates WHERE race_id IN (SELECT race_id FROM sl_races WHERE state = ?) OR race_id LIKE ?",
                        (STATE, f"2026-{STATE}-%"))
            con.execute("DELETE FROM sl_races WHERE state = ?", (STATE,))
            con.execute("DELETE FROM sl_sources WHERE state = ?", (STATE,))
            con.execute("DELETE FROM sl_places WHERE source_id LIKE 'va-%'")
            con.execute("DELETE FROM sl_gaps WHERE state = ?", (STATE,))
            con.execute("DELETE FROM sl_notes WHERE state = ?", (STATE,))
            con.executemany("INSERT INTO sl_races VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", race_rows + local_races)
            con.executemany("INSERT INTO sl_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", cands + local_cands)
            con.executemany("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", sources)
            con.executemany("INSERT OR REPLACE INTO sl_places VALUES (?,?,?,?,?)", place_rows)
            con.executemany("INSERT INTO sl_gaps VALUES (?,?,?,?,?,?,?)", local_gaps)
            con.executemany("INSERT INTO sl_notes VALUES (?,?,?,?,?)", notes)
    finally:
        con.close()

    kinds = ", ".join(f"{k} {v}" for k, v in sorted(by_kind.items())) or "none"
    if races:
        say(f"    Virginia: {len(races)} state race(s) on the November ballot ({kinds}), {gen_rows} candidates; "
            f"{fields} state primary fields (the August 4 primaries carried {'no' if not fields else 'some'} state contest); "
            f"{sum(1 for c in cands if c[1] == 'general' and c[7])} incumbents matched; no regular state race (odd-year elections)")
    else:
        say("    Virginia: no state race on the November 3, 2026 ballot. " + ODD_YEARS)
    if local:
        say(f"    Virginia local: {len(local_races):,} contests ({', '.join(f'{k} {v:,}' for k, v in sorted(local['levels'].items()))}), "
            f"{len(local_cands):,} candidates, reaching {local['reached']} of 133 counties and independent cities; {local['specials']} "
            f"special elections; {local['two_county']} contests on the ballot in more than one locality; no ballot order (the list "
            "gives only each party group's place)")
        say(f"      check: {local['rows']:,} local rows on the list = {local['placed']:,} placed, each in exactly one contest "
            f"({local['copies']} of them a second locality's copy of a candidate) + {local['unplaced']} not placed "
            f"({plural(local['unplaced_contests'], 'contest')}, in sl_gaps) + {local['gone']} withdrawn or removed. {control}")
        say("      office kinds: " + ", ".join(f"{k} {v:,}" for k, v in sorted(local["kinds"].items(), key=lambda kv: (-kv[1], kv[0]))))
        for g in local["gaps"]:
            say(f"      not placed (in sl_gaps): {g[3]}: {g[4]}")
    for p in problems:
        say(f"      CHECK {p}")
    return {"races": len(races), "candidates": gen_rows, "by_kind": dict(by_kind), "fields": fields, "problems": problems,
            "specials": [t for t, _m in specials], "counts": counts, "gone": len(gone),
            "local": dict({k: local[k] for k in ("rows", "placed", "unplaced", "unplaced_contests", "gone", "levels", "kinds", "reached",
                                                 "specials", "two_county", "copies")},
                          races=len(local_races), candidates=len(local_cands)) if local else None}


SCHEMA = """
CREATE TABLE IF NOT EXISTS sl_races (race_id TEXT PRIMARY KEY, state TEXT NOT NULL, level TEXT NOT NULL, office_kind TEXT NOT NULL, office TEXT NOT NULL, jurisdiction TEXT, jurisdiction_id TEXT, county_ids TEXT, district TEXT, seat TEXT, special INTEGER NOT NULL DEFAULT 0, partisan INTEGER NOT NULL, holder_id TEXT, holder_name TEXT, holder_party TEXT, election_date TEXT NOT NULL, note TEXT);
CREATE TABLE IF NOT EXISTS sl_candidates (race_id TEXT NOT NULL, election TEXT NOT NULL, election_date TEXT, name TEXT NOT NULL, party TEXT, party_code TEXT, ballot_order INTEGER, incumbent INTEGER NOT NULL DEFAULT 0, write_in INTEGER NOT NULL DEFAULT 0, votes INTEGER, pct REAL, outcome TEXT, state_member_id TEXT, source_id TEXT, note TEXT, PRIMARY KEY (race_id, election, name));
CREATE TABLE IF NOT EXISTS sl_sources (source_id TEXT PRIMARY KEY, state TEXT, kind TEXT, agency TEXT, title TEXT, url TEXT, published TEXT, fetched TEXT, sha256 TEXT, rows INTEGER, note TEXT);
CREATE TABLE IF NOT EXISTS sl_places (kind TEXT NOT NULL, id TEXT NOT NULL, name TEXT NOT NULL, county_ids TEXT, source_id TEXT, PRIMARY KEY (kind, id));
"""


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("usage: python -m ballot.state_local_va <database> [cache folder]")
    load(sys.argv[1], cache=sys.argv[2] if len(sys.argv) > 2 else CACHE)
