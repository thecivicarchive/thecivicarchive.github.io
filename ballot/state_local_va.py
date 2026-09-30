"""
ballot/state_local_va.py - Virginia's state races on the November 3, 2026 ballot, from the Virginia Department of
Elections' own candidate lists and results, into ballot_local_2026.sqlite (never ballot_2026.sqlite). Virginia's rows
only: everything this loader writes is deleted and written again on each run.

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
import zipfile
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urljoin

if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import openpyxl

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


def page_links(url, heading):
    """A page's links as (absolute address, link text), after checking its heading."""
    page = get(url).decode("utf-8", "replace")
    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", page, re.S | re.I)
    said = re.sub(r"\s+", " ", H.unescape(H.unescape(re.sub(r"<[^>]+>", " ", h1.group(1))))).strip() if h1 else ""
    if said != heading:
        raise SystemExit(f"Virginia: the page {url} is headed {said!r}, not {heading!r}")
    out = []
    for href, text in re.findall(r"<a[^>]+href=\"([^\"]+)\"[^>]*>(.*?)</a>", page, re.S | re.I):
        out.append((urljoin(url, H.unescape(href)), re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", text))).strip()))
    return out


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
            links = [u for u, _t in page_links(ALL_PAGE, ALL_HEADING) if ALL_LINK.search(u)]
            if not links:
                raise SystemExit("Virginia: the All Offices page no longer links the 2026 November All Offices Candidate List workbook")
            main = read_list(links[0], ALL_PAGE, ALL_HEADING, all_path, 0, say)
        else:
            main = json.load(open(all_path, encoding="utf-8"))
        index = page_links(INDEX, INDEX_HEADING)
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

    for folded, (geoid, label) in sorted(geo.items(), key=lambda kv: kv[1][0]):
        place_rows.append(("county", geoid, label, json.dumps([geoid]), SRC_COUNTY))
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
         f"{counts.get('local', 0)} local offices, not stored in this phase; {len(main['rows'])} of a state office, one per "
         f"candidate per locality). Withdrawn or removed, left off: {len(gone)}. " + ODD_YEARS
         + (" State races on this list: " + ", ".join(sorted(races)) + "." if races else " This list carries no state race."))]
    sources += special_sources + pri_sources
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

    con = sqlite3.connect(db_path)
    try:
        con.executescript(SCHEMA)
        with con:
            con.execute("DELETE FROM sl_candidates WHERE race_id IN (SELECT race_id FROM sl_races WHERE state = ?) OR race_id LIKE ?",
                        (STATE, f"2026-{STATE}-%"))
            con.execute("DELETE FROM sl_races WHERE state = ?", (STATE,))
            con.execute("DELETE FROM sl_sources WHERE state = ?", (STATE,))
            con.execute("DELETE FROM sl_places WHERE source_id LIKE 'va-%'")
            con.executemany("INSERT INTO sl_races VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", race_rows)
            con.executemany("INSERT INTO sl_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", cands)
            con.executemany("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", sources)
            con.executemany("INSERT OR REPLACE INTO sl_places VALUES (?,?,?,?,?)", place_rows)
    finally:
        con.close()

    kinds = ", ".join(f"{k} {v}" for k, v in sorted(by_kind.items())) or "none"
    if races:
        say(f"    Virginia: {len(races)} state race(s) on the November ballot ({kinds}), {gen_rows} candidates; "
            f"{fields} state primary fields (the August 4 primaries carried {'no' if not fields else 'some'} state contest); "
            f"{sum(1 for c in cands if c[1] == 'general' and c[7])} incumbents matched; no regular state race (odd-year elections)")
    else:
        say("    Virginia: no state race on the November 3, 2026 ballot. " + ODD_YEARS)
    for p in problems:
        say(f"      CHECK {p}")
    return {"races": len(races), "candidates": gen_rows, "by_kind": dict(by_kind), "fields": fields, "problems": problems,
            "specials": [t for t, _m in specials], "counts": counts, "gone": len(gone)}


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
