"""
ballot/state_local_ia.py - Iowa's state races on the November 3, 2026 ballot: the Iowa Senate seats up this year (the
25 odd-numbered districts), all 100 Iowa House seats, and the statewide offices (Governor with Lieutenant Governor,
Secretary of State, Auditor of State, Treasurer of State, Secretary of Agriculture, Attorney General), with the June 2
party primaries that chose the nominees; and, county by county from the county auditors' own files, the county,
township and district offices on the same ballot (see "The county and township pass" below). Written into
ballot_local_2026.sqlite (never ballot_2026.sqlite), Iowa's rows only.

Sources, all the Iowa Secretary of State's own, the same three files the federal loader (ballot/lists/ia.py) reads:

  Candidate List, November 3, 2026 General Election (PDF, linked as "candidate list" from sos.iowa.gov/general-election)
  Candidate List, June 2, 2026 Primary Election (PDF, the same layout, linked from sos.iowa.gov/primary-election)
  Election Canvass Summary, 2026 Primary Election (PDF, "Official Canvass by County" on the Election Results page)

The two candidate lists carry each candidate's address, phone, e-mail and filing date beside the office, party and
ballot name. Only the first three columns are ever turned into text; the others stay inside the file and are never
read, printed, logged or stored. When the federal loader's cached copy of a list is fresh it is read from there;
otherwise the list is fetched into memory and never written to disk whole. What was read (office, party, name) is kept
as a small JSON extract with the file's SHA-256. The canvass holds only names and vote counts, so it is cached whole.

What the record does not say, the loader does not say:
  - The lists do not state a ballot order, and their order is not strictly by party (State Senator District 9 and 23
    print the Democrat first), so no ballot order is stored. County auditors print the ballots.
  - Iowa elects the Governor and Lieutenant Governor together on one vote; the list names each party's candidate for
    Lieutenant Governor on a row of its own. There is one race, 2026-IA-GOV, and each governor candidate's running
    mate (same party, the only one listed) is named in the candidate's note.
  - Today's holder comes from the Open States roster in state_ia.sqlite (legislators by chamber and district; the
    officials table for Governor, Attorney General and Secretary of State). The roster does not carry the Auditor, the
    Treasurer or the Secretary of Agriculture, so those races show no holder.
  - A candidate is marked as the sitting member only when the name fits the roster's holder of that same seat and no
    other candidate in the race fits.

Primaries: a party primary becomes a field when two or more candidates were on that party's ballot. Shares are of the
candidates' votes plus write-ins (write-ins are not listed; under and over votes are left out). Iowa nominates the
leader only with at least 35 percent; otherwise a party convention chooses, and the candidate on the November list for
that party is the one who advanced. Every canvass section is checked: county rows add up to the statewide Total,
Election Day plus Absentee equals it, and candidates, write-ins, under and over votes add up to its Total column.

The county and township pass (from the second half of this file on)
--------------------------------------------------------------------
Iowa has no statewide list of county and township candidates: they file with each of the 99 county auditors, and the
Secretary of State's list stops at the Legislature. So this pass goes county by county, largest first, and loads a
county only from its auditor's own files for November 3, 2026. Every county it does not load is named in sl_gaps.

On this ballot (sl_notes "local_calendar", from Iowa Code 39.17, 39.18, 39.21, 39.22): county supervisors, treasurer,
recorder and county attorney, with parties; and on the nonpartisan part, county public hospital trustees, soil and
water conservation district commissioners, county agricultural extension council members, and township trustees and
clerks where a township elects them. Cities and school boards elected in November 2025.

How a county is read (COUNTIES says which way):
  * sample ballots (Polk, Scott, Black Hawk, Woodbury, Story, Dallas, Warren, Marshall, Des Moines): every sample
    ballot the auditor posts, one file per precinct or one file of every ballot style. ballot_contests() finds the
    ballot's columns from its own "Vote for no more than N" lines and reads each contest under one: its title, the
    number to vote for, the names and the party beside each. A contest is kept once; every ballot that carries it must
    name the same candidates, or the county is not loaded. The federal and state contests, the judges standing for
    retention and the public measures on a ballot are not read here. A sample ballot holds offices, names and parties
    only. It is fetched into memory, read and dropped; what is kept is what was read (ballots_extract.json in the
    county's folder) with the file's SHA-256.
  * Linn: the auditor's Candidate Listing (PDF). Its columns to the right of the first hold each candidate's
    residential and mailing address, telephone, e-mail and filing date; only the first column (office, vote-for line,
    name, party) is ever turned into rows, and the file is never written to disk.
  * Johnson: the auditor's page of offices and candidates. A candidate's name is followed there by lines of address,
    telephone and e-mail; every line with a digit, an at-sign or a link is dropped before anything else reads the
    page, each such block must sit right under one name already read, and the page is never written to disk.
  * a county whose site will not serve a script (SAVED: Dubuque, Clinton): its sample ballots are read from PDF files
    John saves from his own browser into ballot_cache/ia/local/<folder>/, when they are there.
A file that does not fit its reader stops that county, which then goes to sl_gaps with the reason; a stop names the
file, the page and the row, never the words. Nothing is filed by guess: a contest title the reader does not know stops
the county; a township is filed under a Census code only when its name fits exactly one township of the county in the
Bureau's 2020 list; where a ballot says only "Township Trustee", the township is the one its precinct heading names,
and if the heading names none or two the contest goes to sl_gaps.

Parties: a party is what the November file prints beside the name. As a second route, each county's June 2 primary is
read from the Secretary of State's results system (contest titles, names and parties only; no votes are kept): a party
read from a ballot must be the party whose primary ballot carried the same name for the same office, or the county is
not loaded. Where a sample ballot prints no party beside a name for a partisan office, the party is taken from that
primary ballot and the candidate's note says so; with no primary ballot either, the row says "No party printed".

Ballot order: given where every ballot carrying a contest prints the names in the same order (the nonpartisan offices
are placed by lot and the parties' order is one for the whole county, Iowa Code 49.31); a contest whose names rotate
from precinct to precinct, and anything read from a candidate list, has none.

Caches, all under ballot_cache/ia/local/: each county's index.json (the links on its page), ballots_extract.json or
the cut-down list, and primary_county_offices.json; the Census Bureau's list of county subdivisions (names and codes);
the addresses of the county auditors' own sites from the Secretary of State's list (its telephone numbers and e-mail
are not read). No address, telephone number, e-mail or website of any candidate is read, printed, logged, cached or
stored. A second run downloads nothing but each county's page, and that only every INDEX_DAYS days.
"""

import datetime as dt
import gzip
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
from collections import Counter
from urllib.error import HTTPError, URLError

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ballot.check_local import EXTRA_SCHEMA, contact_like                   # noqa: E402
from ballot.common import CACHE, HERE, fold, name_parts, party_code          # noqa: E402
from ballot.lists import ia as fed                                          # noqa: E402
from ballot.match import fits                                               # noqa: E402
from ballot.pdftext import PDF, join, lines, page_runs, rows as pdf_rows   # noqa: E402
from states import net                                                     # noqa: E402

STATE, FIPS, NAME = "IA", "19", "Iowa"
GENERAL = "2026-11-03"
PRIMARY = fed.PRIMARY
ROSTER_DB = os.path.join(HERE, "state_ia.sqlite")
COUNTY_ZIP = os.path.join(HERE, "states_cache", "census", "cb_2024_us_county_500k.zip")

SCHEMA = """
CREATE TABLE IF NOT EXISTS sl_races (race_id TEXT PRIMARY KEY, state TEXT NOT NULL, level TEXT NOT NULL, office_kind TEXT NOT NULL, office TEXT NOT NULL, jurisdiction TEXT, jurisdiction_id TEXT, county_ids TEXT, district TEXT, seat TEXT, special INTEGER NOT NULL DEFAULT 0, partisan INTEGER NOT NULL, holder_id TEXT, holder_name TEXT, holder_party TEXT, election_date TEXT NOT NULL, note TEXT);
CREATE TABLE IF NOT EXISTS sl_candidates (race_id TEXT NOT NULL, election TEXT NOT NULL, election_date TEXT, name TEXT NOT NULL, party TEXT, party_code TEXT, ballot_order INTEGER, incumbent INTEGER NOT NULL DEFAULT 0, write_in INTEGER NOT NULL DEFAULT 0, votes INTEGER, pct REAL, outcome TEXT, state_member_id TEXT, source_id TEXT, note TEXT, PRIMARY KEY (race_id, election, name));
CREATE TABLE IF NOT EXISTS sl_sources (source_id TEXT PRIMARY KEY, state TEXT, kind TEXT, agency TEXT, title TEXT, url TEXT, published TEXT, fetched TEXT, sha256 TEXT, rows INTEGER, note TEXT);
CREATE TABLE IF NOT EXISTS sl_places (kind TEXT NOT NULL, id TEXT NOT NULL, name TEXT NOT NULL, county_ids TEXT, source_id TEXT, PRIMARY KEY (kind, id));
"""

# statewide offices as the lists print them: (race key, office_kind, office shown, roster office)
STATEWIDE = {
    "Governor": ("GOV", "governor", "Governor and Lieutenant Governor", "governor"),
    "Secretary of State": ("SOS", "secretary_of_state", "Secretary of State", "secretary of state"),
    "Auditor of State": ("AUD", "state_auditor", "Auditor of State", None),
    "Treasurer of State": ("TREAS", "state_treasurer", "Treasurer of State", None),
    "Secretary of Agriculture": ("AGR", "secretary_of_agriculture", "Secretary of Agriculture", None),
    "Attorney General": ("AG", "attorney_general", "Attorney General", "attorney general"),
}
RUNNING_MATE = "Lieutenant Governor"
LEGISLATURE = [(re.compile(r"State Senator District (\d+)"), "SS", "state_senate", "State Senator", "Senate"),
               (re.compile(r"State Representative District (\d+)"), "SH", "state_house", "State Representative", "House")]

# A few counties tallied a write-in line by name ("Tommy Hexter") or as "Blank"; the canvass then prints an extra column
# between Write-in and Under Votes. Those columns are write-ins and are added to the write-in total.
COLUMNS_EXTRA = re.compile(r"^Write-in (?P<extra>.+) Under Votes Over Votes Total$")

NOBODY = re.compile(r"^[-–—]+$")      # the lists print "--" where a party has no candidate

SRC_GENERAL = "ia-sos-2026-candidate-list"
SRC_PRIMARY_LIST = "ia-sos-2026-primary-candidate-list"
SRC_CANVASS = "ia-sos-2026-primary-canvass"
SRC_ROSTER = "ia-openstates-roster"
SRC_COUNTIES = "ia-census-cb-2024-county"


def office_of(text):
    """{race_id, level, office_kind, office, district, chamber, roster} for an office the list or canvass names; None for
    Congress; a SystemExit for anything else, so a new office on the list is noticed rather than dropped."""
    if text.startswith("United States "):
        return None
    if text in STATEWIDE:
        key, kind, office, roster = STATEWIDE[text]
        return {"race_id": f"2026-{STATE}-{key}", "level": "statewide", "office_kind": kind, "office": office,
                "district": None, "chamber": None, "roster": roster}
    for pat, key, kind, office, chamber in LEGISLATURE:
        m = pat.fullmatch(text)
        if m:
            d = str(int(m.group(1)))
            return {"race_id": f"2026-{STATE}-{key}{d}", "level": "legislature", "office_kind": kind, "office": office,
                    "district": d, "chamber": chamber, "roster": None}
    raise SystemExit(f"Iowa (state races): an office the loader does not know: {text!r}")


# ---------- the candidate lists: office, party and ballot name only ----------

def read_list(data):
    """(title lines, [(office, party, name)]) from a candidate list's bytes. Cells from the fourth column on (address,
    phone, e-mail, filing date) are never joined into text. The title lines are only tested, never stored or printed."""
    pdf = PDF(data)
    title, body = [], []
    for n, (page, res) in enumerate(pdf.pages(), start=1):
        head = False
        for _y, runs in pdf_rows(pdf, page, res):
            if not head:
                head = "Ballot Name(s)" in join([r for r in runs if r[0] < 300])
                if n == 1 and not head:
                    title.append(join(runs))
                continue
            body.append(fed.cells(runs))
    if not body:
        raise SystemExit("Iowa (state races): the candidate list's column headings were not found")
    full = Counter(tuple(round(x) for x, _rs in row[:4]) for row in body if len(row) >= 4 and row[0][0] < 50)
    if not full:
        raise SystemExit("Iowa (state races): no row of the candidate list names an office")
    edges = list(full.most_common(1)[0][0])
    col = lambda x: next((i for i in range(len(edges) - 1, -1, -1) if x >= edges[i] - 1.5), 0)
    office, out = None, []
    for row in body:
        got = {}
        for x, rs in row:
            k = col(x)
            if k < 3:
                got[k] = join(rs)
        party, name = got.get(1, ""), got.get(2, "")
        if not (party and name):      # a footnote or a wrapped line: neither an office nor a candidate
            continue
        if got.get(0):
            office = got[0]
        if office is None:
            raise SystemExit("Iowa (state races): a candidate row before any office")
        out.append((office, party, name))
    return title, out


def get_list(which, page_url, title_words, max_age_days, extract_dir, say):
    """Read one candidate list: the federal loader's cached copy when fresh, else fetched into memory (never saved
    whole). Returns (rows, url, sha256, fetched date, how)."""
    url = None
    for attempt in range(3):
        try:
            url = fed.list_url(page_url, which.title() + " Election")
            break
        except (Exception, SystemExit) as e:          # list_url raises SystemExit when the page stops linking a list
            if attempt == 2:
                say(f"    Iowa (state races): could not read {page_url} ({e}); using the linking page as the address")
            else:
                time.sleep(2)
    cached = os.path.join(CACHE, "ia", f"ia_candidate_list_2026_{which}.pdf")
    extract = os.path.join(extract_dir, f"sl_ia_{which}_list.json")
    data, fetched, how = None, None, None
    if os.path.exists(cached) and time.time() - os.path.getmtime(cached) < max_age_days * 86400:
        data = open(cached, "rb").read()
        fetched, how = dt.date.fromtimestamp(os.path.getmtime(cached)).isoformat(), "the federal loader's cached copy"
    elif url:
        data = net.get(url)
        fetched, how = dt.date.today().isoformat(), "fetched into memory"
    if data is None:
        if not os.path.exists(extract):
            raise SystemExit(f"Iowa (state races): the {which} candidate list could not be read")
        ex = json.load(open(extract, encoding="utf-8"))
        say(f"    Iowa (state races): using the saved extract of the {which} list ({ex['fetched']})")
        return [tuple(r) for r in ex["rows"]], ex["url"], ex["sha256"], ex["fetched"], "the saved extract"
    title, rows = read_list(data)
    if title_words not in title:
        raise SystemExit(f"Iowa (state races): the {which} candidate list is not the one for the {title_words}")
    sha = hashlib.sha256(data).hexdigest()
    del data
    url = url or page_url
    os.makedirs(extract_dir, exist_ok=True)
    with open(extract, "w", encoding="utf-8") as fh:        # office, party and ballot name only
        json.dump({"url": url, "sha256": sha, "fetched": fetched, "title": title_words, "rows": rows}, fh, indent=0)
    return rows, url, sha, fetched, how


# ---------- the primary canvass ----------

def canvass(path):
    """(published, {(office, party): {names, votes, write_in, under, over, total, code, places}}) for every section of
    the canvass summary, from its statewide rows, each checked against the county rows. A section with nobody on the
    ballot (write-ins only) has no names and no party line."""
    L = lines(path)
    first = " ".join(t for p, _y, t in L if p == 1)
    when = re.search(r"Canvass date: (\d\d)/(\d\d)/(\d{4})", first)
    if "2026 Primary Election held on Tuesday, June 02, 2026" not in first or not when:
        raise SystemExit("Iowa (state races): the canvass summary is not the June 2, 2026 primary's")
    published = f"{when.group(3)}-{when.group(1)}-{when.group(2)}"
    out, sec = {}, None

    def close(s):
        if s is None:
            return
        where = f"the canvass section {s['title']!r}"
        st = s["state"]
        if set(st) != {"Election Day", "Absentee", "Total"}:
            raise SystemExit(f"Iowa (state races): {where} has no statewide TOTAL rows")
        if [a + b for a, b in zip(st["Election Day"], st["Absentee"])] != st["Total"]:
            raise SystemExit(f"Iowa (state races): in {where}, Election Day plus Absentee is not the statewide Total")
        if s["counties"] != st["Total"]:
            raise SystemExit(f"Iowa (state races): in {where}, the county Total rows add up to {s['counties']}, not {st['Total']}")
        t = st["Total"]
        if sum(t[:-1]) != t[-1]:
            raise SystemExit(f"Iowa (state races): in {where}, the columns do not add up to the Total column")
        n, e = len(s["names"]), s["n_extra"] or 0
        key = (s["office"], s["party"])
        if key in out:
            raise SystemExit(f"Iowa (state races): {where} appears twice")
        out[key] = {"names": s["names"], "votes": t[:n], "write_in": sum(t[n:n + 1 + e]), "under": t[n + 1 + e],
                    "over": t[n + 2 + e], "total": t[n + 3 + e], "code": s["code"], "places": s["places"],
                    "extra": s["extra"]}

    for page, _y, text in L:
        h = fed.HEADING.match(text)
        if h:
            close(sec)
            if h.group("party") not in fed.CANVASS_PARTY:
                raise SystemExit(f"Iowa (state races): a primary for a party the loader does not know: {text!r}")
            party, code = fed.CANVASS_PARTY[h.group("party")]
            sec = {"title": text, "office": h.group("office"), "party": party, "code": code, "names": None, "buf": [],
                   "want": "names", "page": page, "state": {}, "statewide": False, "counties": None, "places": [],
                   "extra": None, "n_extra": None}
            continue
        if sec is None or fed.FURNITURE.match(text):
            continue
        if page != sec["page"]:      # every page of a section repeats the names, the column headings and the parties
            sec["page"], sec["buf"], sec["want"] = page, [], "names"
        if sec["want"] == "names":
            x = COLUMNS_EXTRA.match(text)
            if text == fed.COLUMNS or x:
                label = x.group("extra") if x else None
                if sec["names"] is not None and label != sec["extra"]:
                    raise SystemExit(f"Iowa (state races): {sec['title']!r} has different columns on page {page}")
                sec["extra"] = label
                names = fed.names_of(" ".join(sec["buf"]))
                if sec["names"] is None:
                    sec["names"] = names
                elif names != sec["names"]:
                    raise SystemExit(f"Iowa (state races): {sec['title']!r} names different candidates on page {page}")
                sec["want"] = "parties" if names else "rows"
            else:
                sec["buf"].append(text)
            continue
        if sec["want"] == "parties":
            codes = text.split()
            if len(codes) != len(sec["names"]) or set(codes) != {sec["code"]}:
                raise SystemExit(f"Iowa (state races): under {sec['title']!r} the party line reads {text!r}")
            sec["want"] = "rows"
            continue
        m = fed.ROW.match(text)
        if not m:
            raise SystemExit(f"Iowa (state races): a line in {sec['title']!r} the loader does not recognise: {text!r}")
        nums = [int(v.replace(",", "")) for v in m.group("nums").split()]
        e = len(nums) - len(sec["names"]) - 4
        if (e != 0 if sec["extra"] is None else e < 1) or (sec["n_extra"] is not None and e != sec["n_extra"]):
            raise SystemExit(f"Iowa (state races): a row of {sec['title']!r} has {len(nums)} numbers for {len(sec['names'])} candidates")
        sec["n_extra"] = e
        place = m.group("place")
        if place == "TOTAL":
            sec["statewide"] = True
        if sec["statewide"]:
            sec["state"][m.group("kind")] = nums
        else:
            if place and m.group("kind") == "Election Day":
                sec["places"].append(place)
            if m.group("kind") == "Total":
                sec["counties"] = nums if sec["counties"] is None else [a + b for a, b in zip(sec["counties"], nums)]
    close(sec)
    return published, out


def get_canvass(say):
    path = os.path.join(CACHE, "ia", "ia_canvass_summary_2026_primary.pdf")
    url = None
    try:
        url = fed.canvass_url()
    except (Exception, SystemExit) as e:
        say(f"    Iowa (state races): could not read the results page ({e}); using it as the address")
    if url:
        net.download(url, path, max_age_days=30, say=say)       # names and votes only: safe to keep whole
    if not os.path.exists(path):
        raise SystemExit("Iowa (state races): the primary canvass could not be read")
    return path, url or fed.RESULTS


# ---------- the roster and the counties ----------

def roster(path=ROSTER_DB):
    """Today's holders: {("Senate"|"House", district): row} and {roster office: row}, plus the roster's date."""
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    seats, offices = {}, {}
    for r in con.execute("SELECT bioguide_id, first_name, last_name, official_full, party_name, chamber, district "
                         "FROM legislators WHERE is_current = 1"):
        key = (r[5], str(r[6]))
        if key in seats:
            raise SystemExit(f"Iowa (state races): the roster lists two sitting members for {key}")
        seats[key] = {"id": r[0], "first": r[1], "last": r[2], "full": r[3], "party": r[4]}
    for r in con.execute("SELECT bioguide_id, first_name, last_name, official_full, party_name, office FROM officials"):
        offices[r[5]] = {"id": r[0], "first": r[1], "last": r[2], "full": r[3], "party": r[4]}
    as_of = (con.execute("SELECT max(updated_at) FROM legislators").fetchone()[0] or "")[:10]
    con.close()
    return seats, offices, as_of


def counties(path=COUNTY_ZIP):
    """{folded county name: (GEOID, "Adair County")} for Iowa from the Census Bureau's cartographic county file."""
    import shapefile                                   # pyshp
    z = zipfile.ZipFile(path)
    base = next(n[:-4] for n in z.namelist() if n.endswith(".dbf"))
    rdr = shapefile.Reader(dbf=io.BytesIO(z.read(base + ".dbf")))
    fields = [f[0] for f in rdr.fields[1:]]
    out = {}
    for rec in rdr.iterRecords():
        rec = dict(zip(fields, rec))
        if str(rec.get("STATEFP")) == FIPS:
            out[fold(str(rec["NAME"]))] = (str(rec["GEOID"]), str(rec["NAMELSAD"]))
    if len(out) != 99:
        raise SystemExit(f"Iowa (state races): the county file gives {len(out)} Iowa counties, not 99")
    return out


def holder_fits(name, h):
    cand = name_parts(name)
    return any(fits(cand, reg) for reg in ((fold(h["first"]).split(), fold(h["last"])), name_parts(h["full"] or "")) if reg[1])


def same_name(a, b):
    return fold(a) == fold(b) or fold(a).replace(" ", "") == fold(b).replace(" ", "")


def sha_of(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest() if os.path.exists(path) else ""


def mdate(path):
    return dt.date.fromtimestamp(os.path.getmtime(path)).isoformat() if os.path.exists(path) else ""


# ====================================================================================================================
# The county and township pass: what each county auditor publishes for November 3, 2026
# ====================================================================================================================

LOCAL = os.path.join(CACHE, "ia", "local")
COUSUB_URL = "https://www2.census.gov/geo/docs/reference/codes2020/cousub/st19_ia_cousub2020.txt"
COUSUB_HEAD = "STATE|STATEFP|COUNTYFP|COUNTYNAME|COUSUBFP|COUSUBNS|COUSUBNAME|CLASSFP|FUNCSTAT"
AUDITORS_URL = "https://sos.iowa.gov/auditors"
CODE_URL = "https://www.legis.iowa.gov/law/iowaCode"
PAUSE = 1.2             # seconds between two requests
INDEX_DAYS = 3          # a county's page is read again after this many days; the ballots it links are kept
NONPARTISAN = "Nonpartisan office"
SRC_COUSUB = "ia-census-2020-cousub"
SRC_AUDITORS = "ia-sos-county-auditors"
BALLOT_DATE = re.compile(r"november\s+3,\s+2026", re.I)


class LayoutError(Exception):
    """A file that does not fit its reader. The county is left out and named among the gaps; nothing is filed by guess."""


class Blocked(Exception):
    """A host that refuses a script (403, a challenge page). It is asked three times at most, then left alone."""


_last_request = [0.0]
_refused = {}
CHALLENGE = re.compile(rb"captcha|verify (?:that )?you are (?:a )?human|just a moment\.\.\.|incapsula|radware|cf-chl", re.I)


def polite(url):
    """One request at a time, PAUSE seconds apart, with the kit's honest User-Agent. A refusal (401, 403, 429) is tried
    twice more; after that the host is not asked again in this run. A short page that asks the reader to prove they
    are human is a refusal too, and is never answered."""
    host = urllib.parse.urlsplit(url).netloc.lower()
    if host in _refused:
        raise Blocked(_refused[host])
    for attempt in range(3):
        wait = PAUSE - (time.time() - _last_request[0])
        if wait > 0:
            time.sleep(wait)
        try:
            data = net.get(url, timeout=180)
            if len(data) < 30000 and not data.startswith(b"%PDF") and CHALLENGE.search(data[:8000]):
                _refused[host] = f"{host} answers a script with a page that asks whether the reader is human"
                raise Blocked(_refused[host])
            return data
        except HTTPError as e:
            if e.code in (401, 403, 429):
                if attempt == 2:
                    _refused[host] = f"{host} answers a script with HTTP {e.code}"
                    raise Blocked(_refused[host])
            elif e.code in (404, 410) or attempt == 2:
                raise
        except (URLError, OSError):
            if attempt == 2:
                raise
        finally:
            _last_request[0] = time.time()
        time.sleep(5 * (attempt + 1))
    raise Blocked(f"{host} did not answer")


def squeeze(text):
    return re.sub(r"\s+", " ", text or "").strip()


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", fold_keep_digits(text)).strip("-")


def fold_keep_digits(text):
    return re.sub(r"[^a-z0-9]+", " ", (text or "").replace("&", " and ").lower()).strip()


def page_text(fragment):
    return squeeze(H.unescape(re.sub(r"<[^>]+>", " ", fragment)))


def page_links(page, base):
    """(address, label) of a page's links to other pages and files; mail, telephone and script links are never read."""
    out = []
    for m in re.finditer(r'<a\b[^>]*?href\s*=\s*["\']([^"\']+)["\'][^>]*>(.*?)</a>', page, re.S | re.I):
        href = H.unescape(m.group(1)).strip()
        if href.lower().startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        out.append((urllib.parse.urljoin(base, href), page_text(m.group(2))))
    return out


# ---------- a sample ballot: the contests under each "Vote for no more than N" line ----------

NUMBER = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
VOTE_FOR = re.compile(r"^\(?\s*vote for no more than (\w+)( team)?\s*\)?\.?$", re.I)
PARTY_LABEL = re.compile(r"^(DEM|REP|LIB|NP|NBP|IND|Democratic|Republican|Libertarian|No Party|Nominated by Petition|Independent|.+ Party)$")
WRITE_IN = re.compile(r"write-?in", re.I)
SECTION = re.compile(r"^(non[- ]?partisan|partisan|federal|state|county|township|judicial|city|school|local|other)"
                     r"( (and )?(township|county|city|school|federal|state|local))? (offices?|ballot)$|^public measures?$", re.I)
YES_NO = re.compile(r"^(yes|no)$", re.I)
TURN = re.compile(r"^(turn (the )?ballot over|vote both sides|continue voting|sample)\b", re.I)
WORD_GAP = 4.5          # points: the pieces of one line of type sit closer than this; a column's gutter is wider
CELL_GAP = 12.0         # a candidate's name and a party printed at the right of the same row are further apart than this


def rows_of(runs):
    """Runs grouped into printed rows, top to bottom: [(y, [runs])]."""
    out = []
    for r in sorted(runs, key=lambda r: (-r[1], r[0])):
        if out and abs(out[-1][0] - r[1]) <= 3.0:
            out[-1][1].append(r)
        else:
            out.append([r[1], [r]])
    return out


def pieces_of(rs, gap):
    """One row's runs as pieces of type: runs closer together than `gap` belong to one piece."""
    out = []
    for r in sorted(rs, key=lambda r: r[0]):
        if out and r[0] - max(x[4] for x in out[-1]) <= gap:
            out[-1].append(r)
        else:
            out.append([r])
    return out


def ballot_contests(data):
    """({"contests": [{title, vote_for, candidates: [(name, party)], write_ins, page}], "tops": {page: [piece]}, "dated"})
    for a sample ballot (or a file of many). A ballot is set in columns of one width. The width is the distance between
    the vote-for lines of neighbouring columns; the columns begin where no line of type crosses from one to the next.
    Type that is not under a vote-for line (the judges, the public measures, the instructions) makes no contest. `tops`
    holds the pieces printed in the top band of each page, where a ballot names its precinct."""
    pdf = PDF(data)
    pages, tops, dated = [], {}, False
    for pn, (page, res) in enumerate(pdf.pages(), start=1):
        runs = page_runs(pdf, page, res)
        box = pdf.get(page.get("MediaBox")) or [0, 0, 612, 792]
        height = float(box[3]) - float(box[1])
        band = [r for r in runs if r[1] > float(box[1]) + height - 150]
        tops[pn] = [join(p) for _y, rs in rows_of(band) for p in pieces_of(rs, WORD_GAP)]
        dated = dated or any(BALLOT_DATE.search(t) for t in tops[pn])
        pages.append([r for r in runs if r[2] <= 16])            # watermarks and banners set aside
    if not any(pages):
        raise LayoutError("the file has no text (a picture of a ballot)")
    lines_of, starts = [], Counter()            # per page: [(y, [pieces])]; where the commonest vote-for wording starts
    for runs in pages:
        page_lines = [(y, pieces_of(rs, WORD_GAP)) for y, rs in rows_of(runs)]
        lines_of.append(page_lines)
        for _y, ps in page_lines:
            for p in ps:
                m = VOTE_FOR.match(join(p))
                if m and not m.group(2):
                    starts[(m.group(1).lower(), round(p[0][0]))] += 1
    if not starts:
        raise LayoutError("no vote-for line in the file")
    words = Counter()
    for (w, _x), n in starts.items():
        words[w] += n
    word = words.most_common(1)[0][0]
    cols = []
    for x in sorted(x for (w, x) in starts if w == word):
        if cols and x - cols[-1][-1] <= 4:
            cols[-1].append(x)
        else:
            cols.append([x])
    anchors = [sum(c) / len(c) for c in cols]
    gaps = [b - a for a, b in zip(anchors, anchors[1:])]
    if not gaps:
        raise LayoutError("only one column of contests, so the column width cannot be told")
    pitch = min(gaps)
    if pitch < 100 or any(abs(g / pitch - round(g / pitch)) * pitch > 6 for g in gaps):
        raise LayoutError("the columns of contests are not evenly spaced")
    pitch = sum(gaps) / sum(round(g / pitch) for g in gaps)

    # where the columns begin: the offset at which the fewest pieces of type cross a column's edge
    spans = []
    for page_lines in lines_of:
        heads = [y for y, ps in page_lines for p in ps if VOTE_FOR.match(join(p))]
        if not heads:
            continue
        for y, ps in page_lines:
            if y <= max(heads) + 45:
                spans.extend((p[0][0], max(r[4] for r in p)) for p in ps)
    steps = [k * 0.5 for k in range(int(pitch * 2))]
    cost = []
    for o in steps:
        n = 0
        for a, b in spans:
            k = int((b - 0.75 - o) // pitch)             # the last edge left of the piece's end
            if o + k * pitch > a + 0.75:
                n += 1
        cost.append(n)
    low = min(cost)
    if low > max(2, len(spans) // 200):
        raise LayoutError("no clear gutter between the columns")
    best, run = None, []
    for i in range(2 * len(steps)):                      # the widest stretch of offsets at the lowest cost (it may wrap around)
        o, c = steps[i % len(steps)] + (pitch if i >= len(steps) else 0), cost[i % len(steps)]
        if c == low:
            run.append(o)
            continue
        if best is None or len(run) > len(best):
            best = run
        run = []
    if best is None or len(run) > len(best):
        best = run
    offset = (best[0] + best[-1]) / 2 % pitch

    out = []
    for pn, runs in enumerate(pages, start=1):
        by_col = {}
        for r in runs:
            by_col.setdefault(int((r[0] - offset) // pitch), []).append(r)
        for k in sorted(by_col):
            contest, pending, state = None, [], "title"
            for y, rs in rows_of(by_col[k]):
                text = join(rs)
                if not text:
                    continue
                m = VOTE_FOR.match(text)
                if m:
                    w = m.group(1).lower()
                    n = int(w) if w.isdigit() else NUMBER.get(w)
                    if n is None:
                        raise LayoutError(f"a vote-for number the reader does not know on page {pn}")
                    title, last_y, size = [], y, None
                    for py, ptext, psize in reversed(pending):               # the block of lines right above, in one size of type
                        if py - last_y > (42 if size is None else 20) or (size is not None and abs(psize - size) > 0.6):
                            break
                        if SECTION.match(ptext) or YES_NO.match(ptext) or WRITE_IN.search(ptext) or TURN.match(ptext):
                            break
                        title.append(ptext)
                        last_y, size = py, psize
                    contest = {"title": " ".join(reversed(title)), "vote_for": n, "team": bool(m.group(2)), "write_ins": 0, "page": pn, "_rows": []}
                    out.append(contest)
                    pending, state = [], "cands"
                    continue
                if state == "cands":
                    if WRITE_IN.search(text):
                        contest["write_ins"] += 1
                        state = "after"
                        continue
                    big = max(r[2] for r in rs)
                    small = [r for r in rs if r[2] < big - 0.6]
                    if small:                                # the party in smaller type beside the name
                        name, party = join([r for r in rs if r[2] >= big - 0.6]), join(small)
                    else:                                    # or in the same type at the right of the row
                        ps = pieces_of(rs, CELL_GAP)
                        name, party = join(ps[0]), " ".join(join(p) for p in ps[1:])
                    contest["_rows"].append({"y": y, "name": name, "party": party, "label": not party and bool(PARTY_LABEL.match(name))})
                    continue
                if state == "after" and WRITE_IN.search(text):
                    contest["write_ins"] += 1
                    continue
                state = "title"
                pending.append((y, text, max(r[2] for r in rs)))

    # The usual distance between two candidates on this ballot: a name that runs on to a second line sits closer than
    # that, and closer than the widest step between the names of its own contest (a contest set tight keeps its names apart).
    drops = sorted(a["y"] - b["y"] for c in out for a, b in zip(c["_rows"], c["_rows"][1:]) if not a["label"] and not b["label"] and a["y"] - b["y"] > 6)
    usual = drops[len(drops) // 2] if drops else None
    for c in out:
        raw = c.pop("_rows")
        ys = [e["y"] for e in raw if not e["label"]]
        steps = [a - b for a, b in zip(ys, ys[1:])]
        widest = max(steps) if len(steps) >= 2 else None
        rows = []
        for e in raw:
            last = rows[-1] if rows else None
            near = last["foot"] - e["y"] if last else None
            if (usual and last and not e["label"] and not last["label"] and not e["party"] and near < 0.8 * usual
                    and (widest is None or near < 0.8 * widest)):
                last["name"] += " " + e["name"]                # the second line of a long name
                last["foot"] = e["y"]
            else:
                rows.append(dict(e, foot=e["y"]))
        for i, e in enumerate(rows):                          # a party printed on a row of its own goes to the name it sits by
            if not e["label"]:
                continue
            prev = next((n for n in reversed(rows[:i]) if not n["label"]), None)
            nxt = next((n for n in rows[i + 1:] if not n["label"]), None)
            d_prev = prev["foot"] - e["y"] if prev and not prev["party"] else None
            d_next = e["y"] - nxt["y"] if nxt and not nxt["party"] else None
            if d_prev is not None and (d_next is None or d_prev <= d_next + 1.0) and d_prev <= 16:
                prev["party"] = e["name"]
            elif d_next is not None and d_next <= 16:
                nxt["party"] = e["name"]
            else:
                raise LayoutError(f"a party label with no name beside it on page {c['page']}")
        c["candidates"] = [(squeeze(n["name"]), squeeze(n["party"])) for n in rows if not n["label"]]
    return {"contests": out, "tops": tops, "dated": dated}


# ---------- a contest's title into an office ----------

STATE_OFFICE = re.compile(r"^(united states|u\.?\s?s\.?) (senator|representative)\b|^(governor|secretary of state|auditor of state|treasurer of state|"
                          r"secretary of agriculture|attorney general|state senat(e|or)|state representative)\b", re.I)
VACANCY = re.compile(r"\s*[-,(]?\s*\bto fill (?:a |the )?vacanc(?:y|ies)\b\s*\)?", re.I)
TERM_DATES = re.compile(r"\s*(\d{1,2})-(\d{1,2})-(\d{4}) thru (\d{1,2})-(\d{1,2})-(\d{4})\s*$", re.I)
TERM_YEARS = re.compile(r"\s*[-,(]\s*(\d+) year term\)?\s*$", re.I)
COUNTY_OFFICE = {"county treasurer": ("county_treasurer", "County Treasurer"), "county recorder": ("county_recorder", "County Recorder"),
                 "county attorney": ("county_attorney", "County Attorney"), "county auditor": ("county_auditor", "County Auditor"),
                 "county sheriff": ("sheriff", "County Sheriff")}
DISTRICT_BOARD = (("sanitary", "sanitary_board", "Sanitary District Trustee"), ("water", "water_board", "Water District Trustee"),
                  ("light", "lighting_board", "Street Lighting District Trustee"), ("lake", "lake_board", "Recreational Lake District Trustee"),
                  ("fire", "fire_board", "Fire District Trustee"))
PARTY_WORDS = {"dem": "Democratic", "democratic": "Democratic", "democratic party": "Democratic", "rep": "Republican",
               "republican": "Republican", "republican party": "Republican", "lib": "Libertarian", "libertarian": "Libertarian",
               "libertarian party": "Libertarian", "no party": "No Party", "np": "No Party", "nominated by petition": "No Party"}
MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")


def proper(text):
    """DES MOINES -> Des Moines; a name already in ordinary capitals is left as printed."""
    return " ".join(w.capitalize() if w.isupper() and len(w) > 1 else w for w in squeeze(text).split())


def classify(title, county):
    """A contest title as a ballot or a county's list prints it -> {level, kind, office, partisan, township, body,
    district, special, term, years}; None for a federal or state office (those come from the Secretary of State's
    list); LayoutError for a title this reader does not know, so that nothing is filed by guess. `township` is the
    township's name as printed, or "" when the title says only "Township Trustee"."""
    t = re.sub(r"^for\s+", "", squeeze(title), flags=re.I)
    if STATE_OFFICE.match(t):
        return None
    o = {"special": 0, "township": None, "body": None, "district": None, "term": None, "years": None}
    m = TERM_DATES.search(t)
    if m:
        a, b = [int(v) for v in m.groups()[:3]], [int(v) for v in m.groups()[3:]]
        if not (1 <= a[0] <= 12 and 1 <= b[0] <= 12):
            raise LayoutError(f"a term the reader cannot read in a contest title: {t!r}")
        o["term"] = f"{MONTHS[a[0] - 1]} {a[1]}, {a[2]} to {MONTHS[b[0] - 1]} {b[1]}, {b[2]}"
        o["years"] = f"{a[2]}-{b[2]}"
        t = t[:m.start()]
    m = TERM_YEARS.search(t)
    if m:
        o["term"], t = f"{int(m.group(1))} years", t[:m.start()]
    m = VACANCY.search(t)
    if m:
        o["special"], t = 1, squeeze(t[:m.start()] + " " + t[m.end():])
    t = squeeze(t)
    low = re.sub(rf"^{re.escape(county.lower())} county (?=treasurer|recorder|attorney|auditor|sheriff)", "county ", t.lower())

    def out(level, kind, office, partisan, **kw):
        o.update(level=level, kind=kind, office=office, partisan=partisan, **kw)
        return o

    m = re.fullmatch(r"(?:county )?(?:board of )?supervisors?(?: district (\d+))?", low)
    if m:
        return out("county", "county_commissioner", "County Supervisor", 1, district=m.group(1))
    if low in COUNTY_OFFICE:
        return out("county", COUNTY_OFFICE[low][0], COUNTY_OFFICE[low][1], 1)
    if re.fullmatch(r"soil (?:and|&) water(?: conservation)?(?: district)?(?: commissioners?| members?)?", low):
        return out("soil_water", "soil_water", "Soil and Water Conservation District Commissioner", 0)
    if re.fullmatch(r"(?:county )?agricultural extension(?: council)?(?: members?)?", low):
        return out("other", "extension_council", "County Agricultural Extension Council Member", 0)
    if re.fullmatch(r"(?:county )?(?:public )?hospital trustees?", low):
        return out("hospital", "hospital_board", "County Public Hospital Trustee", 0)
    m = re.fullmatch(r"(?:(.+?) )?(?:township|twp\.?) (trustees?|clerk)(?: (.+))?", t, re.I)
    if m and not (m.group(1) and m.group(3)):
        trustee = m.group(2).lower().startswith("trustee")
        return out("township", "town_supervisor" if trustee else "town_clerk", "Township Trustee" if trustee else "Township Clerk", 0,
                   township=proper(m.group(1) or m.group(3) or ""))
    m = re.fullmatch(r"(.+?) trustees?", t, re.I)
    if m:
        for word, kind, office in DISTRICT_BOARD:
            if re.search(rf"\b{word}", m.group(1), re.I):
                return out("other", kind, office, 0, body=proper(m.group(1)))
    raise LayoutError(f"a contest title the reader does not know: {t!r}")


def party_word(label, office, title):
    """The party as Iowa's other rows word it. A nonpartisan office has none. On a partisan one, a name with no party
    printed beside it comes back with None: confirm_parties settles it from the June primary, never by guess."""
    if not office["partisan"]:
        if label:
            raise LayoutError(f"a party beside a candidate for a nonpartisan office ({title!r})")
        return NONPARTISAN
    if not label:
        return None
    p = PARTY_WORDS.get(squeeze(label).lower().rstrip("."))
    if p is None:
        raise LayoutError(f"a party label the reader does not know in {title!r}: {label!r}")
    return p


# ---------- the places: counties, townships ----------

def letters(text):
    """Allen's Grove, Allens Grove; LeClaire, Le Claire; Mt. Vernon, Mount Vernon: the same letters."""
    t = re.sub(r"\bmt\b\.?", "mount", (text or "").lower())
    t = re.sub(r"\bst\b\.?", "saint", t)
    return re.sub(r"[^a-z0-9]", "", t)


def townships(say):
    """{county code: {letters of the name: (code, "Delaware township")}} from the Census Bureau's 2020 list of Iowa's
    county subdivisions (kept whole: it holds names and codes only), and the file's path."""
    path = os.path.join(LOCAL, "st19_ia_cousub2020.txt")
    if not os.path.exists(path):
        data = polite(COUSUB_URL)
        os.makedirs(LOCAL, exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(data)
    rows = open(path, encoding="utf-8").read().splitlines()
    if not rows or rows[0].strip() != COUSUB_HEAD:
        raise LayoutError("the Census Bureau's list of county subdivisions has other headings than expected")
    out = {}
    for n, line in enumerate(rows[1:], start=2):
        cells = line.split("|")
        if len(cells) != 9:
            raise LayoutError(f"line {n} of the Census Bureau's list of county subdivisions does not have nine cells")
        if cells[1] != FIPS or not cells[6].endswith(" township"):
            continue
        by = out.setdefault(cells[1] + cells[2], {})
        key = letters(cells[6][:-len(" township")])
        by[key] = None if key in by else (cells[4], cells[6])          # two of one name in a county: neither is matched
    return out, path


# ---------- where each county posts its ballots ----------

def find_rows(page, base):
    """The county-elections site several auditors share: one "ballotRow" for each sample ballot."""
    out = []
    for row in re.findall(r'<div class="ballotRow"[^>]*>(.*?)</div>', page, re.S):
        out += [(label, url) for url, label in page_links(row, base) if url.lower().split("?")[0].endswith(".pdf")]
    return out


def find_polk(page, base):
    """Polk County's voter information page: each precinct's polling-place file, then its sample ballot or ballots."""
    out, precinct = [], ""
    for url, label in page_links(page, base):
        if url.lower().endswith("-sample.pdf"):
            out.append((precinct if label == "Sample Ballot" else squeeze(precinct + " " + label), url))
        elif re.search(r"/media/[^/]+/[^/]+\.pdf$", url):
            precinct = label
    return out


def find_story(page, base):
    """Story County's election page: the front of each precinct's ballot, and one back that every ballot shares."""
    found = page_links(page, base)
    fronts = [(label, url) for url, label in found if re.search(r"/DocumentCenter/View/\d+/\d+-Sample-FRONT$", url)]
    backs = [("Back of every sample ballot", url) for url, _label in found if re.search(r"/DocumentCenter/View/\d+/A_Back-of-Sample-Ballots$", url)]
    return fronts + backs[:1]


def find_dallas(page, base):
    """Dallas County's Sample Ballots page links one file that holds every ballot style."""
    seen = []
    for url, _label in page_links(page, base):
        if re.search(r"/DocumentCenter/View/\d+$", url) and url not in seen:
            seen.append(url)
    return [("Every ballot style", url) for url in seen]


def find_warren(page, base):
    return [(label, url) for url, label in page_links(page, base) if label == "General Election Sample Ballots" and url.lower().endswith(".pdf")]


# Counties whose November 3, 2026 list a script can read, largest first. `page` is the auditor's page that links the
# files; `find` picks the links. A county that is not here is named in sl_gaps.
COUNTIES = [
    {"name": "Polk", "slug": "polk", "how": "ballots", "find": find_polk,
     "page": "https://www.polkcountyiowa.gov/county-auditor/election/news-and-press-releases/general-election-november-3-2026-voter-information/"},
    {"name": "Linn", "slug": "linn", "how": "linn",
     "page": "https://www.linncountyiowa.gov/1794/November-3-2026-General-Election",
     "file": "https://gis.linncountyiowa.gov/web-data/elections/year/2026/20261103GE/candidates.pdf"},
    {"name": "Scott", "slug": "scott", "how": "ballots", "find": find_rows,
     "page": "https://elections.scottcountyiowa.gov/elections/info/2026_gubernatorial_general_election_2026_11_03/"},
    {"name": "Johnson", "slug": "johnson", "how": "johnson",
     "page": "https://johnsoncountyiowa.gov/november-3-2026-general-election"},
    {"name": "Black Hawk", "slug": "black-hawk", "how": "ballots", "find": find_rows,
     "page": "https://blackhawkcountyelections.iowa.gov/elections/info/2026_general_election_2026_11_03/"},
    {"name": "Woodbury", "slug": "woodbury", "how": "ballots", "find": find_rows,
     "page": "https://elections.woodburycountyiowa.gov/elections/info/2026_general_election_2026_11_03/"},
    {"name": "Story", "slug": "story", "how": "ballots", "find": find_story,
     "page": "https://www.storycountyiowa.gov/1754/General-Election-11032026"},
    {"name": "Dallas", "slug": "dallas", "how": "ballots", "find": find_dallas,
     "page": "https://www.dallascountyiowa.gov/524/Sample-Ballots-None-Active"},
    {"name": "Warren", "slug": "warren", "how": "ballots", "find": find_warren,
     "page": "https://www.warrencountyia.gov/services/resident-services/election-information/"},
    {"name": "Marshall", "slug": "marshall", "how": "ballots", "find": find_rows,
     "page": "https://elections.marshallcountyia.gov/elections/info/2026_general_election_2026_11_03/"},
    {"name": "Des Moines", "slug": "des-moines", "how": "ballots", "find": find_rows,
     "page": "https://dmcountyelections.iowa.gov/elections/info/2026_general_election_2026_11_03/"},
]

# Counties that were tried and could not be read by a script on 2026-10-01, with the reason a reader is given.
TRIED = {
    "Pottawattamie": ("https://www.pottcounty-ia.gov/elections/2026_general_election_2026_11_03/",
                      "The county auditor posts 66 sample ballots for November 3, 2026, and each is a picture of the printed page with no "
                      "text a script can read, so the county's list is not loaded here yet."),
    "Jasper": ("https://jaspercountyelections.iowa.gov/elections/info/november_3rd_general_election_2026_11_03/",
               "The county auditor posts 38 sample ballots for November 3, 2026, and each is a picture of the printed page with no text a "
               "script can read, so the county's list is not loaded here yet."),
}
# A county whose site will not serve a script: its sample ballots are read from the PDF files John saves himself, from his
# own browser, into ballot_cache/ia/local/<folder>/ (under the names the site gives them). Until then the county is a gap.
SAVED = {
    "Dubuque": ("dubuque", "https://elections.dubuquecountyiowa.gov/pages/sample-ballots",
                "The county auditor's election pages are drawn by a program in the reader's browser, and a script receives an empty page. "
                "The county's sample ballots are read here once they have been saved by hand from a browser; until then its list is not "
                "loaded."),
    "Clinton": ("clinton", "https://elections.clintoncounty-ia.gov",
                "The county auditor's election site refuses a script's requests. The county's sample ballots are read here once they have "
                "been saved by hand from a browser; until then its list is not loaded."),
}


# ---------- reading one county ----------

def file_name(url):
    """The name a ballot is kept under: the address's last part (with the document number, on a document-centre site)."""
    parts = url.rstrip("/").split("/")
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", urllib.parse.unquote(parts[-1]))
    if "DocumentCenter" in parts and parts[-2].isdigit():
        name = parts[-2] + "_" + name
    return name if name.lower().endswith(".pdf") else name + ".pdf"


def day_of(path):
    return dt.date.fromtimestamp(os.path.getmtime(path)).isoformat()


READER = 1               # raised when ballot_contests changes what it reads, so that the saved extracts are rebuilt


def link_index(c, say):
    """{"page", "read", "sha256", "ballots": [{label, url, file}], "names", "withdrawn"}: the sample ballots a county's
    page links. The page is read again when the saved list is older than INDEX_DAYS. Where the page also lists the
    county's candidates, how many names it lists and how many of them it marks withdrawn are counted (the names
    themselves come from the ballots)."""
    folder = os.path.join(LOCAL, c["slug"])
    path = os.path.join(folder, "index.json")
    index = None
    if os.path.exists(path):
        try:
            index = json.load(open(path, encoding="utf-8"))
        except ValueError:
            index = None
        if not isinstance(index, dict) or index.get("page") != c["page"]:
            index = None
    if index is None or (dt.date.today() - dt.date.fromisoformat(index["read"])).days >= INDEX_DAYS:
        try:
            raw = polite(c["page"])
            page = raw.decode("utf-8", "replace")
            pairs, seen = [], set()
            for label, url in c["find"](page, c["page"]):
                if url not in seen:
                    seen.add(url)
                    pairs.append((squeeze(label), url))
            if not pairs:
                raise LayoutError("the county's page links no sample ballot")
            listed = re.findall(r'<div class="officeCandidate"[^>]*>(.*?)</div>', page, re.S)
            index = {"page": c["page"], "read": dt.date.today().isoformat(), "sha256": hashlib.sha256(raw).hexdigest(),
                     "ballots": [{"label": label, "url": url, "file": file_name(url)} for label, url in pairs],
                     "names": len(listed), "withdrawn": sum(1 for x in listed if re.search(r"withdrawn", x, re.I))}
            os.makedirs(folder, exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(index, fh, indent=0)
        except (Blocked, LayoutError, HTTPError, URLError, OSError) as e:
            if index is None:
                raise
            say(f"    Iowa local: {c['name']} County's page could not be read again ({e}); using the links saved on {index['read']}")
    return index


def saved_ballots(folder_name):
    """Sample ballots saved by hand (a site that will not serve a script): every PDF in the county's folder."""
    folder = os.path.join(LOCAL, folder_name)
    if not os.path.isdir(folder):
        return []
    return [{"label": os.path.splitext(f)[0], "url": None, "file": f} for f in sorted(os.listdir(folder)) if f.lower().endswith(".pdf")]


def ballot_extracts(c, wanted, say):
    """What ballot_contests reads from each of a county's sample ballots, in the order given: [{label, url, file,
    sha256, bytes, fetched, dated, tops, contests}]. A ballot is fetched into memory, read and dropped; what is kept
    (ballots_extract.json in the county's folder) is the contests' titles, vote-for numbers, names and party labels and
    the words at the head of each page, with the file's SHA-256. A copy of a ballot found in the folder (saved by hand)
    is read from there instead of being fetched. A ballot already in the extract is not fetched again."""
    folder = os.path.join(LOCAL, c["slug"])
    path = os.path.join(folder, "ballots_extract.json")
    kept = {"reader": READER, "files": {}}
    if os.path.exists(path):
        try:
            old = json.load(open(path, encoding="utf-8"))
            if old.get("reader") == READER:
                kept = old
        except ValueError:
            pass
    out, new = [], 0

    def save():
        os.makedirs(folder, exist_ok=True)
        with open(path + ".part", "w", encoding="utf-8") as fh:
            json.dump(kept, fh)
        os.replace(path + ".part", path)

    try:
        for b in wanted:
            e = kept["files"].get(b["file"])
            on_disk = os.path.join(folder, b["file"])
            by_hand = os.path.exists(on_disk) and os.path.getsize(on_disk) > 0
            if e is None or e.get("url") != b["url"] or (by_hand and e.get("bytes") != os.path.getsize(on_disk)):
                if by_hand:
                    data, fetched = open(on_disk, "rb").read(), day_of(on_disk)
                elif b["url"]:
                    data, fetched = polite(b["url"]), dt.date.today().isoformat()
                else:
                    raise LayoutError(f"{b['file']} is not in the county's folder")
                if not data.startswith(b"%PDF"):
                    raise LayoutError(f"{b['file']} is not a PDF file")
                try:
                    read = ballot_contests(data)
                except LayoutError as err:
                    raise LayoutError(f"{b['file']}: {err}")
                e = {"url": b["url"], "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data), "fetched": fetched, "dated": read["dated"],
                     "tops": {str(k): v for k, v in read["tops"].items()},
                     "contests": [{"title": x["title"], "vote_for": x["vote_for"], "write_ins": x["write_ins"], "page": x["page"],
                                   "candidates": [list(p) for p in x["candidates"]]} for x in read["contests"]]}
                del data
                kept["files"][b["file"]] = e
                new += 1
                if new % 25 == 0:
                    save()
            out.append(dict(e, label=b["label"], file=b["file"]))
    finally:
        if new:
            save()                                                 # what was read is kept even when a later file stops the county
    gone = [f for f in kept["files"] if f not in {b["file"] for b in wanted}]
    for name in gone:
        del kept["files"][name]                                    # a ballot the county no longer posts
    if gone:
        save()
    return out


def precinct_township(tops, known):
    """The one township a ballot's own heading names (its precinct is called after it: "Barclay", "Linn Township",
    "Poyner 2", "Big Creek/Kirkwood"), or None when the heading names none or more than one."""
    found = {}
    for piece in tops:
        for part in piece.split("/"):
            part = re.sub(r"\s+\d+$", "", re.sub(r"\s+(township|twp\.?)$", "", squeeze(part), flags=re.I))
            hit = known.get(letters(part)) if part else None
            if hit:
                found[hit[0]] = hit
    return next(iter(found.values())) if len(found) == 1 else None


def race_key(o, place):
    return (o["level"], o["kind"], (place[0] + "|" + place[1]) if place else (o["body"] or ""), o["district"] or "", o["special"],
            o["years"] or o["term"] or "")


def county_from_ballots(c, entries, known):
    """Every local contest on a county's sample ballots, merged across the ballots that carry it.
    -> ({key: race}, [facts about each file], counts, [(ballot, title, names) for contests that could not be placed])"""
    races, per_file, stats, unplaced = {}, [], Counter(), []
    for b in entries:
        label = b["label"]
        if not b["dated"] and not label.startswith("Back of"):
            raise LayoutError(f"{b['file']} does not say November 3, 2026 at its head")
        fact = {"label": label, "url": b["url"], "sha": b["sha256"], "fetched": b["fetched"], "lines": 0, "contests": 0}
        per_file.append(fact)
        stats["files"] += 1
        on_sheet = {}
        for con in b["contests"]:
            o = classify(con["title"], c["name"])
            if o is None:
                stats["federal and state contests on the ballots (not read here)"] += 1
                continue
            if con.get("write_ins", con["vote_for"]) != con["vote_for"]:      # a ballot prints one write-in line for each one to be chosen
                raise LayoutError(f"{b['file']}: {con['title']!r} has {con['write_ins']} write-in lines for {con['vote_for']} to be chosen, "
                                  "so the contest may not have been read whole")
            notes, place = [], None
            if o["level"] == "township":
                if o["township"]:
                    hit = known.get(letters(o["township"]))
                    place = hit or ("", f"{o['township']} township")
                else:                                         # "Township Trustee": the ballot's heading names the precinct
                    front = con["page"] if con["page"] % 2 else con["page"] - 1
                    hit = precinct_township(b["tops"].get(str(front), []) + b["tops"].get(str(con["page"]), []), known)
                    if hit is None:
                        unplaced.append((label, con["title"], len(con["candidates"])))
                        stats["township contests the ballot does not place"] += 1
                        continue
                    place = hit
                    notes.append("The ballot titles this contest without naming the township; it is filed under the township the "
                                 "ballot's precinct is named for.")
            cands = []
            for name, plabel in con["candidates"]:
                party = party_word(plabel, o, con["title"])
                if contact_like(name, True) or "@" in name or re.search(r"\d{3,}", name):
                    stats["names set aside because they look like contact details"] += 1
                    continue
                cands.append((name, party, None))
            if len({n for n, _p, _c in cands}) != len(cands):
                raise LayoutError(f"{b['file']}: a name twice in {con['title']!r}")
            key = race_key(o, place)
            sheet = (con["page"] + 1) // 2
            if key in on_sheet.setdefault(sheet, set()):
                raise LayoutError(f"{b['file']}: {con['title']!r} twice on one ballot")
            on_sheet[sheet].add(key)
            fact["lines"] += len(cands)
            fact["contests"] += 1
            stats["candidate lines read"] += len(cands)
            stats["contests read"] += 1
            r = races.get(key)
            if r is None:
                races[key] = {"o": o, "place": place, "vote_for": con["vote_for"], "cands": cands, "first": fact, "seen": 1, "notes": notes,
                              "title": con["title"], "same_order": True}
            else:
                if {(n, p) for n, p, _c in r["cands"]} != {(n, p) for n, p, _c in cands} or r["vote_for"] != con["vote_for"]:
                    raise LayoutError(f"{b['file']}: {con['title']!r} differs from the same contest on {r['first']['label']}")
                r["seen"] += 1
                r["same_order"] = r["same_order"] and [n for n, _p, _c in r["cands"]] == [n for n, _p, _c in cands]
    if not races:
        raise LayoutError("no county or township contest was found on the ballots")
    return races, per_file, stats, unplaced


# ---------- Linn County: the auditor's candidate listing ----------

LINN_EDGE = 195.0        # the listing's first column ends here; the addresses, telephone numbers and e-mail lie to the right
LINN_SKIP = re.compile(r"^(Linn County Election Services|Candidate's Name|Party|The filing deadline\b.*)$")
LINN_PARTY = {"Republican Party": "Republican", "Democratic Party": "Democratic", "Libertarian Party": "Libertarian", "No Party": "No Party",
              "Nonpartisan Office": NONPARTISAN}


def linn_rows(data):
    """(title ok, [[office, vote for, name or None, party or None]], offices counted by the listing's own column
    headings) from Linn County's candidate listing. Only the first column is ever turned into rows: every piece that
    starts right of LINN_EDGE (the residential and mailing addresses, telephone numbers, e-mail addresses and filing
    dates) is dropped before anything else looks at the page. A line that fits nothing stops the reader, which names
    the page and the row, never the words."""
    pdf = PDF(data)
    titled, out, heads, office, vote = False, [], 0, None, None
    for pn, (page, res) in enumerate(pdf.pages(), start=1):
        for rn, (_y, rs) in enumerate(rows_of(page_runs(pdf, page, res)), start=1):
            where = f"Linn County's listing, page {pn}, row {rn}"
            pieces = pieces_of(rs, 6.0)                                 # by position only: nothing has been read yet
            first = pieces[0]
            if first[0][0] >= 60:
                continue                                                # nothing in the first column on this row
            size = max(r[2] for r in first if r[0] < LINN_EDGE)
            if size < 9.5:                                              # the disclaimer in small type
                continue
            if size >= 13.5:                                            # a title or an office's heading stands alone on its row
                if size < 15 and len(pieces) > 1:
                    raise LayoutError(f"{where}: an office's heading with something beside it")
                text = join(first)
            else:                                                       # everything right of the first column is dropped here
                kept = [r for r in first if r[0] < LINN_EDGE]
                if size >= 11.5 and max(r[4] for r in kept) > LINN_EDGE - 4:
                    raise LayoutError(f"{where}: a name that runs into the next column")
                text = join(kept)
            if not text:
                continue
            if size >= 15:
                titled = titled or "November 3, 2026 General Election" in text
                continue
            if text == "Candidate's Name":
                heads += 1
            if LINN_SKIP.match(text):
                continue
            m = re.match(r"^vote for no more than (\w+)", text, re.I)
            if m and size < 11:
                vote = NUMBER.get(m.group(1).lower())
                if vote is None or office is None or out[-1][1] is not None:
                    raise LayoutError(f"{where}: a vote-for line the reader cannot place")
                out[-1][1] = vote
                continue
            if size >= 13.5:
                if out and (out[-1][3] is None):
                    raise LayoutError(f"{where}: the office before this one has no candidate line, or a name with no party line")
                office, vote = text, None
                out.append([office, None, None, None])
                continue
            if office is None or vote is None:
                raise LayoutError(f"{where}: a line before any office")
            if size >= 11.5:                                            # a candidate's name; an asterisk marks an incumbent
                if out[-1][2] is not None and out[-1][3] is None:
                    raise LayoutError(f"{where}: a name with no party line")
                name = squeeze(text.lstrip("*")) or None
                if name is None:
                    raise LayoutError(f"{where}: an empty name")
                if name == "No Candidate":
                    name = None
                if out[-1][2] is None and out[-1][3] is None:           # the office's first line
                    out[-1][2], out[-1][3] = name, ("" if name is None else None)
                else:
                    out.append([office, vote, name, "" if name is None else None])
                continue
            if text in LINN_PARTY and out[-1][3] in (None, "") and not (out[-1][2] is None and out[-1][3] is None):
                if out[-1][2] is not None:
                    out[-1][3] = LINN_PARTY[text]
                continue
            raise LayoutError(f"{where}: a line the reader does not know")
    if out and out[-1][3] is None:
        raise LayoutError("Linn County's listing ends with an office or a name that is not finished")
    if any(row[1] is None for row in out):
        raise LayoutError("Linn County's listing names an office with no vote-for line")
    return titled, out, heads


def county_from_linn(c, known, say):
    """Linn County's contests from the auditor's candidate listing. The file is fetched into memory and never written
    to disk; what is kept is its first column cut down to office, vote-for number, name and party, as JSON."""
    folder = os.path.join(LOCAL, c["slug"])
    extract = os.path.join(folder, "candidate_listing_extract.json")
    ex = None
    if os.path.exists(extract):
        ex = json.load(open(extract, encoding="utf-8"))
        if ex.get("url") != c["file"]:
            ex = None
    if ex is None or (dt.date.today() - dt.date.fromisoformat(ex["fetched"])).days >= INDEX_DAYS:
        try:
            data = polite(c["file"])
            if not data.startswith(b"%PDF"):
                raise LayoutError("Linn County's candidate listing is not a PDF file")
            titled, rows, heads = linn_rows(data)
            sha, size = hashlib.sha256(data).hexdigest(), len(data)
            del data
            if not titled:
                raise LayoutError("Linn County's candidate listing is not the November 3, 2026 General Election's")
            blanked = 0
            for row in rows:                                            # a cell that looks like contact details is never kept
                if contact_like(row[0], True) or "@" in row[0]:
                    raise LayoutError("Linn County's listing has contact details where an office's title should be")
                if row[2] and (contact_like(row[2], True) or "@" in row[2] or re.search(r"\d{3,}", row[2])):
                    row[2], blanked = "[set aside]", blanked + 1
            ex = {"url": c["file"], "sha256": sha, "bytes": size, "fetched": dt.date.today().isoformat(), "offices_by_heading": heads,
                  "set_aside": blanked, "rows": rows}
            os.makedirs(folder, exist_ok=True)
            with open(extract, "w", encoding="utf-8") as fh:            # office, vote-for number, name and party only
                json.dump(ex, fh, indent=0)
        except (Blocked, HTTPError, URLError, OSError) as e:
            if ex is None:
                raise
            say(f"    Iowa local: Linn County's listing could not be read again ({e}); using the extract saved on {ex['fetched']}")
    rows = ex["rows"]
    offices = []
    for row in rows:
        if not offices or offices[-1] != row[0]:
            offices.append(row[0])
    if len(set(offices)) != len(offices):
        raise LayoutError("Linn County's listing names an office twice")
    if len(offices) != ex["offices_by_heading"]:
        raise LayoutError(f"Linn County's listing has {ex['offices_by_heading']} sets of column headings for {len(offices)} offices")
    fact = {"label": "Candidate Listing", "url": c["file"], "path": None, "sha": ex["sha256"], "fetched": ex["fetched"], "lines": 0, "contests": 0}
    races, stats = {}, Counter()
    stats["offices on the listing"] = len(offices)
    if ex.get("set_aside"):
        stats["names set aside because they look like contact details"] = ex["set_aside"]
    for office, vote, name, party in rows:
        o = classify(office, c["name"])
        if o is None:
            stats["federal and state lines on the listing (not read here)"] += 1
            continue
        place = None
        if o["level"] == "township":
            if not o["township"]:
                raise LayoutError("Linn County's listing has a township office with no township's name")
            place = known.get(letters(o["township"])) or ("", f"{o['township']} township")
        key = race_key(o, place)
        r = races.setdefault(key, {"o": o, "place": place, "vote_for": vote, "cands": [], "first": fact, "seen": 1, "notes": [], "title": office})
        if r["vote_for"] != vote:
            raise LayoutError("Linn County's listing gives one office two vote-for numbers")
        if name is None:
            r["empty"] = True
            continue
        if name == "[set aside]":
            continue
        if party is None or (party == NONPARTISAN) != (not o["partisan"]):
            raise LayoutError(f"Linn County's listing gives a party that does not fit {office!r}")
        r["cands"].append((name, party, None))
        fact["lines"] += 1
        stats["candidate lines read"] += 1
    for r in races.values():
        if r.get("empty") and r["cands"]:
            raise LayoutError("Linn County's listing shows an office both with and without a candidate")
        if len({n for n, _p, _c in r["cands"]}) != len(r["cands"]):
            raise LayoutError("Linn County's listing has a name twice under one office")
    fact["contests"] = stats["contests read"] = len(races)
    stats["files"] = 1
    if not races:
        raise LayoutError("Linn County's listing has no county or township office")
    return races, [fact], stats, []


# ---------- Johnson County: the auditor's page of offices and candidates ----------

JOHNSON_PARTS = ("County Partisan Offices", "Township offices", "Countywide Nonpartisan Offices")
JOHNSON_END = "Judicial Retention"
JOHNSON_NAME = re.compile(r"^[A-Za-z][A-Za-z.'\-]*(?: [A-Za-z][A-Za-z.'\-]*){1,5}(?:, (?:Jr|Sr|II|III|IV)\.?)?$")
JOHNSON_PARTISAN = re.compile(r"^(?P<name>[A-Za-z][A-Za-z .'\-]{2,60}), (?P<party>Democratic Party|Republican Party|Libertarian Party|No Party)$")
JOHNSON_DISTRICT = re.compile(r"^District (\d+) \((\w+) year term\)$")
JOHNSON_OFFICE = re.compile(r"^(County (?:Treasurer|Recorder|Attorney|Auditor|Sheriff)) \((\w+) year term\)$")
JOHNSON_BOARD = re.compile(r"^(Agricultural Extension Council|Soil and Water Commission|County Hospital Trustees?) \((\w+) to be elected\)$")
JOHNSON_TOWN = re.compile(r"^(?P<town>[A-Za-z][A-Za-z .'\-]*?) (?P<what>Trustee|Clerk)(?P<more>(?: to fill vacancy| \(\w+ seats?\))*):\s*(?P<names>[A-Za-z .,'\-]*)$")
JOHNSON_INTRO = re.compile(r"^(?:[A-Z][A-Za-z ]* townships (?:will|may) elect\b|Candidates for the Agricultural Extension Council\b)")
SUFFIX_WORD = re.compile(r"^(Jr|Sr|II|III|IV)\.?$")


def johnson_lines(page):
    """The page's candidate part as [(part, kind, text)]: kind is "words" for a line of letters only (an office, a
    name, a township line), "title" for a line that fits an office's pattern although it holds a number, "contact"
    for any other line with a digit, an e-mail link or an at-sign, and "gap" for an empty line or a paragraph's end. A
    contact line's text is never kept: it is replaced by nothing here, before anything else sees the page."""
    start = page.find(">" + JOHNSON_PARTS[0] + "<")
    end = page.find(JOHNSON_END, start)
    if start == -1 or end == -1:
        raise LayoutError("Johnson County's page has no list of county offices and candidates in the place it had")
    out, part = [], None
    for m in re.finditer(r"<(dt|p|li)\b[^>]*>(.*?)</\1>", page[page.rfind("<dt", 0, start):page.rfind("<dt", 0, end)], re.S | re.I):
        tag, body = m.group(1).lower(), m.group(2)
        if tag == "li":
            continue                                               # links to maps and notices
        if tag == "dt":
            part = page_text(body)
            if part not in JOHNSON_PARTS:
                raise LayoutError("Johnson County's page has a section the reader does not know among its lists of candidates")
            continue
        for piece in re.split(r"<br\s*/?>", body, flags=re.I):
            if re.search(r"<a\b|__cf_email__|email-protection|@", piece, re.I):
                out.append((part, "contact", ""))
                continue
            text = page_text(piece)
            if not text:
                out.append((part, "gap", ""))
            elif JOHNSON_DISTRICT.match(text) or JOHNSON_OFFICE.match(text) or JOHNSON_BOARD.match(text) or JOHNSON_INTRO.match(text):
                out.append((part, "title", text))
            elif re.search(r"\d", text):
                out.append((part, "contact", ""))
            else:
                out.append((part, "words", text))
        out.append((part, "gap", ""))
    return out


def johnson_rows(page):
    """[[office title, vote for, name or None, party or None]] from Johnson County's page, and the number of contact
    blocks counted (each must follow one name read, so that no candidate is missed and no stray line is taken for a name)."""
    lines_ = johnson_lines(page)
    rows, office, vote, board, blocks, named, waiting, started = [], None, None, False, 0, 0, None, set()

    def start(title, n):
        nonlocal office, vote
        if title in started:
            raise LayoutError("Johnson County's page names an office twice")
        started.add(title)
        office, vote = title, n
        rows.append([title, n, None, ""])

    def add(name, party):
        if rows[-1][2] is None:
            rows[-1][2], rows[-1][3] = name, party
        else:
            rows.append([office, vote, name, party])

    for i, (part, kind, text) in enumerate(lines_):
        where = f"Johnson County's page, line {i + 1} of its candidate lists"
        prev_kind = lines_[i - 1][1] if i else "gap"
        next_kind = lines_[i + 1][1] if i + 1 < len(lines_) else "gap"
        if kind == "contact":
            if prev_kind != "contact":                          # a contact block opens: it must sit right under a name just read
                blocks += 1
                if waiting != i - 1:
                    raise LayoutError(f"{where}: contact details that follow no candidate's name")
                waiting = None
            continue
        if waiting is not None:
            raise LayoutError(f"{where}: a name with no contact block under it, which is not this page's layout")
        if kind == "gap":
            continue
        if kind == "title":
            if JOHNSON_INTRO.match(text):
                continue
            m = JOHNSON_DISTRICT.match(text)
            if m:
                if not board:
                    raise LayoutError(f"{where}: a supervisor district before the Board of Supervisors heading")
                years = NUMBER.get(m.group(2).lower())
                if years is None:
                    raise LayoutError(f"{where}: a term the reader cannot read")
                start(f"Board of Supervisors District {int(m.group(1))}" + ("" if years == 4 else f" - {years} Year Term"), 1)
                continue
            m = JOHNSON_OFFICE.match(text)
            if m:
                board = False
                start(m.group(1), 1)
                continue
            m = JOHNSON_BOARD.match(text)
            n = NUMBER.get(m.group(2).lower())
            if n is None:
                raise LayoutError(f"{where}: a number to be elected the reader cannot read")
            start({"Agricultural Extension Council": "County Agricultural Extension Council", "Soil and Water Commission":
                   "Soil and Water Conservation District Commissioner"}.get(m.group(1), "County Public Hospital Trustee"), n)
            continue
        # a line of words
        if part == JOHNSON_PARTS[0]:
            if text == "Board of Supervisors":
                board = True
                continue
            m = JOHNSON_PARTISAN.match(text)
            if not m or office is None or next_kind != "contact":
                raise LayoutError(f"{where}: a line the reader does not know among the partisan offices")
            add(squeeze(m.group("name")), LINN_PARTY[m.group("party")])
            waiting, named = i, named + 1
        elif part == JOHNSON_PARTS[1]:
            m = JOHNSON_TOWN.match(text)
            if not m:
                raise LayoutError(f"{where}: a line the reader does not know among the township offices")
            seats = re.search(r"\((\w+) seats?\)", m.group("more"))
            n = NUMBER.get(seats.group(1).lower()) if seats else 1
            if n is None:
                raise LayoutError(f"{where}: a number of seats the reader cannot read")
            start(f"{squeeze(m.group('town'))} Township {m.group('what')}" + (" To Fill Vacancy" if "to fill vacancy" in m.group("more") else ""), n)
            names = []
            for piece in (squeeze(p) for p in m.group("names").split(",")):
                if piece and names and SUFFIX_WORD.match(piece):
                    names[-1] += ", " + piece
                elif piece:
                    names.append(piece)
            for name in names:
                if not JOHNSON_NAME.match(name):
                    raise LayoutError(f"{where}: a township candidate's name the reader cannot read")
                add(name, NONPARTISAN)
        else:
            if not JOHNSON_NAME.match(text) or office is None or prev_kind == "words" or next_kind != "contact":
                raise LayoutError(f"{where}: a line the reader does not know among the nonpartisan offices")
            add(text, NONPARTISAN)
            waiting, named = i, named + 1
    if waiting is not None:
        raise LayoutError("Johnson County's page ends with a name that has no contact block under it, which is not its layout")
    if blocks != named:
        raise LayoutError(f"Johnson County's page has {blocks} contact blocks for {named} names read")
    return rows, blocks


def county_from_johnson(c, known, say):
    """Johnson County's contests from the auditor's page. The page is fetched into memory and never written to disk;
    what is kept is the office titles, vote-for numbers, names and parties, as JSON."""
    folder = os.path.join(LOCAL, c["slug"])
    extract = os.path.join(folder, "candidate_page_extract.json")
    ex = None
    if os.path.exists(extract):
        ex = json.load(open(extract, encoding="utf-8"))
        if ex.get("url") != c["page"]:
            ex = None
    if ex is None or (dt.date.today() - dt.date.fromisoformat(ex["fetched"])).days >= INDEX_DAYS:
        try:
            raw = polite(c["page"])
            page = raw.decode("utf-8", "replace")
            if "November 3, 2026 General Election" not in page_text(" ".join(re.findall(r"<h1\b[^>]*>(.*?)</h1>", page, re.S | re.I))):
                raise LayoutError("Johnson County's page is not headed November 3, 2026 General Election")
            rows, blocks = johnson_rows(page)
            sha, size = hashlib.sha256(raw).hexdigest(), len(raw)
            del raw, page
            blanked = 0
            for row in rows:
                if contact_like(row[0], True):
                    raise LayoutError("Johnson County's page has contact details where an office's title should be")
                if row[2] and (contact_like(row[2], True) or "@" in row[2] or re.search(r"\d", row[2])):
                    row[2], blanked = "[set aside]", blanked + 1
            ex = {"url": c["page"], "sha256": sha, "bytes": size, "fetched": dt.date.today().isoformat(), "contact_blocks": blocks,
                  "set_aside": blanked, "rows": rows}
            os.makedirs(folder, exist_ok=True)
            with open(extract, "w", encoding="utf-8") as fh:            # office, vote-for number, name and party only
                json.dump(ex, fh, indent=0)
        except (Blocked, HTTPError, URLError, OSError) as e:
            if ex is None:
                raise
            say(f"    Iowa local: Johnson County's page could not be read again ({e}); using the extract saved on {ex['fetched']}")
    fact = {"label": "Offices and candidates", "url": c["page"], "path": None, "sha": ex["sha256"], "fetched": ex["fetched"], "lines": 0, "contests": 0}
    races, stats = {}, Counter()
    if ex.get("set_aside"):
        stats["names set aside because they look like contact details"] = ex["set_aside"]
    for office, vote, name, party in ex["rows"]:
        o = classify(office, c["name"])
        if o is None:
            raise LayoutError("Johnson County's page lists a state office among its county offices")
        place = None
        if o["level"] == "township":
            place = known.get(letters(o["township"])) or ("", f"{o['township']} township")
        key = race_key(o, place)
        if key in races and name is None:
            raise LayoutError("Johnson County's page names an office twice")
        r = races.setdefault(key, {"o": o, "place": place, "vote_for": vote, "cands": [], "first": fact, "seen": 1, "notes": [], "title": office})
        if name is None or name == "[set aside]":
            continue
        if (party == NONPARTISAN) != (not o["partisan"]):
            raise LayoutError(f"Johnson County's page gives a party that does not fit {office!r}")
        r["cands"].append((name, party, None))
        fact["lines"] += 1
        stats["candidate lines read"] += 1
    for r in races.values():
        if len({n for n, _p, _c in r["cands"]}) != len(r["cands"]):
            raise LayoutError("Johnson County's page has a name twice under one office")
    fact["contests"] = stats["contests read"] = len(races)
    stats["files"] = 1
    stats["contact blocks on the page, each after one name read"] = ex["contact_blocks"]
    return races, [fact], stats, []


# ---------- the June 2 primary, as a second route to a candidate's party ----------

RESULTS_SITE = "https://electionresults.iowa.gov/IA/"
PRIMARY_NAME = "2026 Primary Election"
PRIMARY_DAYS = 30
NOT_PRINTED = "No party printed"
PARTY_FROM_PRIMARY = ("The sample ballot prints no party beside this name; the party is the one on whose June 2 primary ballot the name "
                      "stood for this office (the Secretary of State's primary results).")
NO_PARTY_ANYWHERE = ("The sample ballot prints no party beside this name, and the name was not on a party's June 2 primary ballot for this "
                     "office.")


def results_json(url):
    """(bytes as fetched, the JSON they hold): the results system sends its files compressed."""
    raw = polite(url)
    body = gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw
    return raw, json.loads(body.decode("utf-8", "replace"))


def primary_index(say):
    """Where each county's June 2, 2026 primary results sit on the Secretary of State's results system:
    {"counties": {county name folded: [folder, election number, version]}, ...}. Kept for PRIMARY_DAYS."""
    path = os.path.join(LOCAL, "primary_results_index.json")
    if os.path.exists(path):
        kept = json.load(open(path, encoding="utf-8"))
        if (dt.date.today() - dt.date.fromisoformat(kept["fetched"])).days < PRIMARY_DAYS:
            return kept
    raw_list, elections = results_json(RESULTS_SITE + "elections.json")
    eids = [e.get("EID") for e in elections if e.get("ElectionName") == PRIMARY_NAME and str(e.get("Date", "")).startswith("6/2/2026")]
    if len(eids) != 1:
        raise LayoutError("the results system does not list one 2026 Primary Election of June 2, 2026")
    version = polite(f"{RESULTS_SITE}{eids[0]}/current_ver.txt").decode("ascii", "replace").strip()
    if not version.isdigit():
        raise LayoutError("the results system's version file is not a number")
    url = f"{RESULTS_SITE}{eids[0]}/{version}/json/en/electionsettings.json"
    raw, settings = results_json(url)
    counties = {}
    for item in settings.get("settings", {}).get("electiondetails", {}).get("participatingcounties", []):
        cells = item.split("|")
        if len(cells) >= 3 and cells[1].isdigit() and cells[2].isdigit():
            counties[fold(cells[0].replace("_", " "))] = cells[:3]
    if len(counties) != 99:
        raise LayoutError(f"the results system names {len(counties)} counties for the primary, not 99")
    kept = {"fetched": dt.date.today().isoformat(), "election": eids[0], "version": version, "url": url, "sha256": hashlib.sha256(raw).hexdigest(),
            "list_url": RESULTS_SITE + "elections.json", "list_sha256": hashlib.sha256(raw_list).hexdigest(), "list_rows": len(elections),
            "counties": counties}
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(kept, fh, indent=0)
    return kept


def primary_parties(c, index, say):
    """({(office kind, district, special): {letters of a name: party}}, facts for sl_sources) for the county offices on
    one county's June 2 primary ballots. From the county's summary file only the contest titles, the candidates' names
    and their party are kept; the votes are not."""
    folder = os.path.join(LOCAL, c["slug"])
    path = os.path.join(folder, "primary_county_offices.json")
    kept = None
    if os.path.exists(path):
        kept = json.load(open(path, encoding="utf-8"))
        if (dt.date.today() - dt.date.fromisoformat(kept["fetched"])).days >= PRIMARY_DAYS:
            kept = None
    if kept is None:
        where = index["counties"].get(fold(c["name"]))
        if not where:
            raise LayoutError(f"the results system has no {c['name']} County page for the primary")
        url = f"{RESULTS_SITE}{where[0]}/{where[1]}/{where[2]}/json/en/summary.json"
        raw, contests = results_json(url)
        offices = {}
        for con in contests if isinstance(contests, list) else []:
            title = squeeze(str(con.get("C", "")))
            if not re.match(r"^(County|Board of Supervisors)\b", title, re.I):
                continue
            names, parties = con.get("CH") or [], con.get("P") or []
            offices[title] = [[squeeze(str(n)), squeeze(str(p))] for n, p in zip(names, parties) if squeeze(str(p))]
        kept = {"url": url, "sha256": hashlib.sha256(raw).hexdigest(), "fetched": dt.date.today().isoformat(), "offices": offices}
        os.makedirs(folder, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:                  # contest titles, names and parties only
            json.dump(kept, fh, indent=0)
    out, n = {}, 0
    for title, people in kept["offices"].items():
        try:
            o = classify(re.sub(r"\s*-\s*(Rep|Dem|Lib)\.?\s*$", "", title, flags=re.I), c["name"])
        except LayoutError:
            continue
        if not o or not o["partisan"]:
            continue
        by = out.setdefault((o["kind"], o["district"] or "", o["special"]), [])
        for name, party in people:
            word = PARTY_WORDS.get(party.lower())
            if word:
                by.append((name, word))
                n += 1
    fact = (f"ia-{c['slug']}-2026-primary-results", STATE, "official results", "Iowa Secretary of State",
            f"2026 Primary Election (June 2, 2026), {c['name']} County results summary", kept["url"], "", kept["fetched"], kept["sha256"], n,
            "Read only to see which party's primary ballot carried each candidate for a county office: contest titles, candidates' names and "
            "parties are kept, votes are not. A party read from a November sample ballot is checked against it.")
    return out, fact


def same_person(a, b):
    """Jordyn M. Hill and Jordyn Hill: the same family name and first name, and no middle initial that contradicts."""
    (ga, fa), (gb, fb) = name_parts(a), name_parts(b)
    if not fa or fa != fb or not ga or not gb or ga[0] != gb[0]:
        return False
    ma, mb = [g[:1] for g in ga[1:]], [g[:1] for g in gb[1:]]
    return not (ma and mb and ma[0] != mb[0])


def confirm_parties(races, primary):
    """Settle each partisan candidate's party. The party printed on the November ballot stands, and must agree with the
    June primary ballot that carried the same name for the same office. A name with no party printed takes the party
    of that primary ballot; with none there either, the row says that no party is printed."""
    n = Counter()
    for r in races.values():
        o = r["o"]
        if not o["partisan"]:
            continue
        before = (primary or {}).get((o["kind"], o["district"] or "", o["special"]), [])
        settled = []
        for name, party, note in r["cands"]:
            fits_ = {p for other, p in before if same_person(name, other)}
            was = fits_.pop() if len(fits_) == 1 else None
            if party is None:
                if was:
                    party, note = was, PARTY_FROM_PRIMARY
                    n["names with no party printed, settled by the June primary"] += 1
                else:
                    party, note = NOT_PRINTED, (NO_PARTY_ANYWHERE if primary is not None else "The sample ballot prints no party beside this name.")
                    n["names with no party printed"] += 1
            elif was and was != party:
                raise LayoutError(f"the party read beside a name in {r['title']!r} is not the party of the June 2 primary ballot that carried it")
            elif was:
                n["parties the June primary confirms"] += 1
            else:
                n["partisan candidates who were not on a June primary ballot"] += 1
            settled.append((name, party, note))
        r["cands"] = settled
        if len(settled) > 1 and all(p == NOT_PRINTED for _n, p, _c in settled):
            raise LayoutError(f"no party is printed beside any name in {r['title']!r}")
    return n


# ---------- the counties' own sites, for the counties not read ----------

def auditor_sites(say):
    """{"sites": {county name folded: address of the county auditor's own site}, ...} from the Secretary of State's
    list of county auditors. Under each county's heading only the first link to a site outside the Secretary's own is
    taken; the list's telephone numbers and e-mail addresses are offices' and are not read. What is kept on disk is the
    county names and those addresses."""
    path = os.path.join(LOCAL, "county_auditor_sites.json")
    kept = None
    if os.path.exists(path):
        kept = json.load(open(path, encoding="utf-8"))
        if (dt.date.today() - dt.date.fromisoformat(kept["fetched"])).days < 30:
            return kept
    try:
        raw = polite(AUDITORS_URL)
    except (Blocked, HTTPError, URLError, OSError) as e:
        if kept:
            return kept
        say(f"    Iowa local: the Secretary of State's list of county auditors could not be read ({e})")
        return {"sites": {}, "sha256": "", "fetched": "", "url": AUDITORS_URL}
    page = raw.decode("utf-8", "replace")
    parts = re.split(r"<h2\b[^>]*>(.*?)</h2>", page, flags=re.S | re.I)
    sites = {}
    for i in range(1, len(parts) - 1, 2):
        name = page_text(parts[i])
        for url, _label in page_links(parts[i + 1], AUDITORS_URL):
            host = urllib.parse.urlsplit(url).netloc.lower()
            if url.startswith("https://") and host and "sos.iowa.gov" not in host and "safelinks" not in host:
                sites[fold(name)] = url
                break
    kept = {"url": AUDITORS_URL, "sha256": hashlib.sha256(raw).hexdigest(), "fetched": dt.date.today().isoformat(), "sites": sites}
    os.makedirs(LOCAL, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(kept, fh, indent=0)
    return kept


# ---------- rows ----------

CALENDAR = ("On November 3, 2026 each Iowa county elects its treasurer, recorder and county attorney and the county supervisors whose terms "
            "are up, all with parties on the ballot; on the nonpartisan part of the same ballot voters choose county public hospital "
            "trustees, soil and water conservation district commissioners, county agricultural extension council members and, in townships "
            "that elect rather than appoint them, township trustees and a township clerk (voted on only outside city limits where a "
            "township includes a city). The county auditor and the sheriff are elected in presidential years, next in 2028. Mayors, city "
            "councils, school boards and community college boards are elected in November of odd-numbered years; they were last on the "
            "ballot on November 4, 2025.")
CALENDAR_SOURCE = ("Iowa Code sections 39.17 (county officers), 39.18 (supervisors), 39.21 (nonpartisan offices at the general election), "
                   "39.22 (township officers), 376.1 (city elections) and 277.1 (school and merged-area elections)")
NO_NAME_BALLOT = "No candidate's name is printed on the ballot for this office; the ballot has a write-in line."
NO_NAME_LIST = "The county auditor's list shows no candidate for this office."
VACANCY_NOTE = "To fill a vacancy: this election is for the rest of a term."
NOT_READ = ("{county}'s candidates for county, township and district offices file with the county auditor, who publishes the county's list "
            "and sample ballots; that list is not loaded here yet.")
WHAT = "county, township and district offices"


def checked(text, what):
    if text and contact_like(text, True):
        raise LayoutError(f"{what} would carry text that looks like contact details")
    return text


def plain(text, what):
    if contact_like(text, False):
        raise LayoutError(f"{what} would carry text that looks like contact details")
    return text


def count_word(n):
    return {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten"}.get(n, str(n))


def county_rows(c, fips, full, races, per_file, how):
    """One county's merged contests as rows: (sl_races, sl_candidates, {place rows}, sl_sources, counts)."""
    code3 = fips[2:]
    agency = f"{c['name']} County Auditor"
    used, src_of = set(), {}
    for fact in per_file:                                   # a source id for every file read, by its label
        base = f"ia-{c['slug']}-2026-" + ("list" if how == "list" else "ballot-" + (slug(fact["label"]) or "x"))
        sid, k = base, 2
        while sid in used:
            sid, k = f"{base}-{k}", k + 1
        used.add(sid)
        src_of[id(fact)] = sid
    rows, ids = [], Counter()
    for r in races.values():
        o = r["o"]
        place_row = None
        if o["level"] == "county":
            jur, jid = full, fips
            rid = f"2026-IA-{fips}-{o['kind'].replace('_', '-')}" + (f"-d{o['district']}" if o["district"] else "")
        elif o["level"] == "soil_water":
            jur, jid, rid = full, fips, f"2026-IA-{fips}-soil-water"
        elif o["kind"] == "extension_council":
            jur, jid, rid = f"{full} Agricultural Extension District", fips, f"2026-IA-{fips}-extension-council"
        elif o["level"] == "hospital":
            jur, jid = f"{full} public hospital", f"IA-H-{code3}-county-public-hospital"
            rid, place_row = f"2026-{jid}-trustee", ("hospital", jid, jur, json.dumps([fips]), None)
        elif o["level"] == "township":
            code, name = r["place"]
            jur, jid = name, (f"IA-M-{code}" if code else f"IA-M-{code3}-{slug(name)}")
            rid = f"2026-{jid}-" + ("trustee" if o["kind"] == "town_supervisor" else "clerk")
            place_row = ("mcd", jid, name, json.dumps([fips]), SRC_COUSUB if code else None)
        else:
            jur, jid = o["body"], f"IA-X-{code3}-{slug(o['body'])}"
            rid, place_row = f"2026-{jid}-trustee", ("special", jid, jur, json.dumps([fips]), None)
        if o["special"]:
            rid += "-S"
        ids[rid] += 1
        rows.append([rid, r, jur, jid, place_row])
    race_rows, cand_rows, places, counts = [], [], {}, Counter()
    for rid, r, jur, jid, place_row in rows:
        o = r["o"]
        seat = None
        if ids[rid] > 1:                                    # two seats of one board, told apart by their terms
            if not o["years"]:
                raise LayoutError(f"two contests for one office in one place, with nothing to tell them apart ({r['title']!r})")
            rid, seat = f"{rid}-t{o['years']}", f"{o['years']} term"
        notes = []
        if r["vote_for"] > 1:
            notes.append(f"Voters choose {r['vote_for']}.")
        if o["special"]:
            notes.append(VACANCY_NOTE)
        if o["years"] and (seat or o["special"]):
            notes.append(f"The ballot gives the term as {o['term']}.")
        elif o["term"] and not o["years"]:
            notes.append(("The county auditor's list" if how == "list" else "The ballot") + f" marks this as a term of {o['term']}.")
        notes.extend(r["notes"])
        if o["level"] == "township" and not r["place"][0]:
            counts["township names not in the Census Bureau's list"] += 1
            notes.append("The township's name is as the ballot prints it; it is not in the Census Bureau's 2020 list for this county under that spelling.")
        if not r["cands"]:
            notes.append(NO_NAME_LIST if how == "list" else NO_NAME_BALLOT)
        src = src_of[id(r["first"])]
        race_rows.append((rid, STATE, o["level"], o["kind"], checked(o["office"], rid), checked(jur, rid), jid, json.dumps([fips]), o["district"], seat,
                          o["special"], o["partisan"], None, None, None, GENERAL, checked(" ".join(notes), rid) or None))
        if place_row:
            places[(place_row[0], place_row[1])] = place_row[:4] + (place_row[4] or src,)
        for n, (name, party, cnote) in enumerate(r["cands"], start=1):
            order = n if how == "ballots" and r.get("same_order", True) else None
            code = "N" if party == NONPARTISAN else ("O" if party == NOT_PRINTED else party_code(party))
            cand_rows.append((rid, "general", GENERAL, checked(name, rid), party, code, order, 0, 0, None, None, None, None, src, checked(cnote, rid)))
            counts["candidates"] += 1
        counts[o["level"]] += 1
        counts["contests with no candidate"] += 0 if r["cands"] else 1
    if len({r[0] for r in race_rows}) != len(race_rows):
        raise LayoutError("two contests came out with one race id")
    sources = []
    for n, fact in enumerate(per_file):
        if how == "list" and c["how"] == "linn":
            title = f"Candidate Listing, November 3, 2026 General Election: {full}"
            kind = "official candidate list"
            note = ("Read from the listing's first column only: the office's title, the vote-for line, each candidate's name and the party line "
                    "under it. The listing also prints each candidate's residential and mailing address, telephone number, e-mail address "
                    "and filing date; those columns are never read, and the file is not kept: what is kept is the office, vote-for number, "
                    "name and party as JSON. An asterisk marking an incumbent is dropped. The listing states no ballot order.")
        elif how == "list":
            title = f"November 3, 2026 General Election: offices to appear on the ballot and lists of candidates, {full}"
            kind = "official candidate list"
            note = ("Read line by line: an office's title, a candidate's name with the party after it, and each township's line (township, "
                    "office, names). The page also prints candidates' addresses, telephone numbers and e-mail addresses: a line with a "
                    "digit, an at-sign or a link is dropped before anything else reads it, each such block must sit under one name already "
                    "read, and the page is not kept: what is kept is the office, vote-for number, name and party as JSON. The page states no "
                    "ballot order.")
        else:
            title = f"Sample ballot, General Election, November 3, 2026: {full}, {fact['label']}"
            kind = "official sample ballot"
            note = f"County, township and district contests read: {fact['contests']}."
            if n == 0:
                note += (" The federal and state contests, the judges and the public measures on a ballot are not read here. A sample "
                         f"ballot carries offices, names and parties only, with no contact details. {full}'s contests are read from every "
                         f"sample ballot the auditor posts ({len(per_file)} {'file' if len(per_file) == 1 else 'files'}, each with a row "
                         "here); a contest is kept once, and every ballot that carries it must name the same candidates. A candidate's "
                         "place on the ballot is given where every ballot carrying the contest prints the same order. The file is read and "
                         "not kept; what was read from it is kept with its SHA-256.")
        sources.append((src_of[id(fact)], STATE, kind, agency, title, fact["url"] or c.get("page") or "", "", fact["fetched"], fact["sha"], fact["lines"],
                        plain(note, title)))
    return race_rows, cand_rows, places, sources, counts


def local_rows(cmap, say):
    """The county and township pass. -> {races, cands, places, sources, gaps, notes, report: [lines], checks: [lines], ...}"""
    os.makedirs(LOCAL, exist_ok=True)
    out = {"races": [], "cands": [], "places": {}, "sources": [], "gaps": [], "notes": [], "report": [], "checks": []}
    known_all, cousub_path = townships(say)
    sites = auditor_sites(say)
    done, totals, by_county = [], Counter(), {}
    try:
        pindex = primary_index(say)
    except (LayoutError, Blocked, HTTPError, URLError, OSError, ValueError) as e:
        pindex = None
        out["checks"].append(f"the June 2 primary results could not be read ({e}); parties are as the November files print them, unconfirmed")

    def gap(name, reason, url, what=WHAT):
        geoid, full = cmap[fold(name)]
        out["gaps"].append((STATE, "county", geoid, full, what, plain(reason, "a gap's reason"), url or sites["sites"].get(fold(name)) or AUDITORS_URL))

    def take(c, how, got, page_fact=None, index=None):
        races, per_file, stats, unplaced = got
        geoid, full = cmap[fold(c["name"])]
        primary, pfact = None, None
        if pindex is not None and any(r["o"]["partisan"] for r in races.values()):
            try:
                primary, pfact = primary_parties(c, pindex, say)
            except (LayoutError, Blocked, HTTPError, URLError, OSError, ValueError) as e:
                out["checks"].append(f"{c['name']} County's June 2 primary results could not be read ({e}); its parties are unconfirmed")
        settled = confirm_parties(races, primary)
        race_rows, cand_rows, places, sources, counts = county_rows(c, geoid, full, races, per_file, how)
        if index and index.get("names"):
            stats["names on the county's own candidates page"] = index["names"]
            stats["of them marked withdrawn"] = index["withdrawn"]
            totals["marked withdrawn on a county's page"] += index["withdrawn"]
        out["races"] += race_rows
        out["cands"] += cand_rows
        out["places"].update(places)
        out["sources"] += ([page_fact] if page_fact else []) + sources + ([pfact] if pfact else [])
        done.append(c["name"])
        by_county[c["name"]] = {"races": len(race_rows), "candidates": counts["candidates"], "files": stats["files"]}
        for k in ("county", "soil_water", "township", "hospital", "other", "candidates", "contests with no candidate"):
            totals[k] += counts[k]
        totals["files"] += stats["files"]
        totals.update(settled)
        said = dict(stats)
        said.update(settled)
        said.update({k: v for k, v in counts.items() if k.startswith("township names")})
        extra = "; ".join(f"{v} {k}" for k, v in sorted(said.items()) if k not in ("files", "candidate lines read", "contests read") and v)
        out["report"].append(
            f"{c['name']}: {len(race_rows)} contests, {counts['candidates']} candidates, from {stats['files']} {'file' if stats['files'] == 1 else 'files'} "
            f"({stats['contests read']} contest headings and {stats['candidate lines read']} candidate lines read; each candidate is in one "
            f"contest, and every file carrying a contest names the same candidates)" + (f"; {extra}" if extra else ""))
        if unplaced:
            n = len(unplaced)
            gap(c["name"], f"{count_word(n).capitalize()} township {'contest' if n == 1 else 'contests'} on {full}'s sample ballots "
                f"{'is' if n == 1 else 'are'} titled only Township Trustee or Township Clerk on a ballot whose heading does not name one "
                "township, so the ballot does not say which township's office it is and it is not filed here.", c.get("page"),
                what="township contests the ballot does not place")
            totals["township contests not placed"] += n

    for c in COUNTIES:
        geoid, full = cmap[fold(c["name"])]
        known = {k: v for k, v in known_all.get(geoid, {}).items() if v}
        try:
            if c["how"] == "ballots":
                index = link_index(c, say)
                entries = ballot_extracts(c, index["ballots"], say)
                page_fact = (f"ia-{c['slug']}-2026-ballot-page", STATE, "official page", f"{c['name']} County Auditor",
                             f"The page that links {full}'s sample ballots for the November 3, 2026 General Election", c["page"], "",
                             index["read"], index.get("sha256", ""), len(entries),
                             "Only the links to the sample ballots are read from this page, and only they are kept"
                             + (f"; the page also lists {index['names']} candidates' names, {index['withdrawn']} of them marked withdrawn, "
                                "which are counted and not read." if index.get("names") else "."))
                take(c, "ballots", county_from_ballots(c, entries, known), page_fact, index)
            elif c["how"] == "linn":
                take(c, "list", county_from_linn(c, known, say))
            else:
                take(c, "list", county_from_johnson(c, known, say))
        except (LayoutError, Blocked, HTTPError, URLError, OSError) as e:
            out["checks"].append(f"{c['name']} County was not loaded: {e}")
            gap(c["name"], f"{full}'s list for November 3, 2026 could not be read when this page was built; the county auditor publishes it.", c.get("page"))
    for name, (folder_name, url, reason) in SAVED.items():
        geoid, full = cmap[fold(name)]
        wanted = saved_ballots(folder_name)
        if not wanted:
            gap(name, reason, url)
            continue
        c = {"name": name, "slug": folder_name, "page": url}
        try:
            entries = ballot_extracts(c, wanted, say)
            take(c, "ballots", county_from_ballots(c, entries, {k: v for k, v in known_all.get(geoid, {}).items() if v}))
        except LayoutError as e:
            out["checks"].append(f"{name} County's saved ballots were not loaded: {e}")
            gap(name, reason, url)
    for name, (url, reason) in TRIED.items():
        if name not in done:
            gap(name, reason, url)
    reached = {g[2] for g in out["gaps"] if g[4] == WHAT} | {cmap[fold(n)][0] for n in done}
    for geoid, full in sorted(cmap.values()):
        if geoid not in reached:
            gap(full[:-len(" County")], NOT_READ.format(county=full), None)
    out["gaps"].append((STATE, "state", STATE, NAME, "special city and school elections", plain(
        "Cities and school districts hold their regular elections in November of odd-numbered years. A city or school vacancy filled by "
        "special election on November 3, 2026 would be on the county auditor's ballot for that place; none is on the ballots read here, and "
        "the counties not read yet may have one.", "a gap's reason"), AUDITORS_URL))

    n_loaded = len(done)
    settled_n, bare_n = totals["names with no party printed, settled by the June primary"], totals["names with no party printed"]
    gone = totals["marked withdrawn on a county's page"]
    coverage = (
        f"Loaded for {n_loaded} of Iowa's 99 counties ({', '.join(done)}), each from the county auditor's own files: {len(out['races'])} contests "
        f"and {len(out['cands'])} candidates for county supervisor, treasurer, recorder and county attorney, township trustee and clerk, "
        f"county public hospital trustee, soil and water conservation district commissioner, county agricultural extension council member "
        f"and the trustees of a few sanitary, water, street lighting and lake districts. {totals['contests with no candidate']} of the "
        f"contests have no candidate's name printed. Iowa has no statewide list of county and township candidates: they file with each county "
        f"auditor, and the other {99 - n_loaded} counties are named among the gaps. Left out everywhere: the judges standing for retention "
        f"(a yes-or-no vote on each judge, not a contest between candidates), the constitutional amendment and local public measures, and "
        f"the federal and state offices, which come from the Secretary of State's list. A sample ballot shows who is on the ballot, not who "
        f"withdrew, so withdrawals cannot be counted in full"
        + (f"; the county pages read here mark {count_word(gone)} {'name' if gone == 1 else 'names'} as withdrawn, and "
           f"{'it is' if gone == 1 else 'they are'} left off" if gone else "")
        + "."
        + (f" Each party read from a November file is checked against the party whose June 2 primary ballot carried the same name for the "
           f"same office: {totals['parties the June primary confirms']} agree, and a county in which one disagreed would not be loaded."
           if pindex is not None else " The June 2 primary results could not be read this time, so the parties are as the November files "
           "print them, unchecked.")
        + (f" {count_word(settled_n).capitalize()} {'name' if settled_n == 1 else 'names'} printed with no party on a sample ballot "
           f"{'takes' if settled_n == 1 else 'take'} the party of that primary ballot." if settled_n else "")
        + (f" {count_word(bare_n).capitalize()} {'name' if bare_n == 1 else 'names'} printed with no party and found on no primary ballot "
           f"{'is' if bare_n == 1 else 'are'} shown with no party printed." if bare_n else ""))
    out["notes"] = [(STATE, "local_calendar", plain(CALENDAR, "the calendar note"), plain(CALENDAR_SOURCE, "the calendar note"), CODE_URL),
                    (STATE, "local_coverage", plain(coverage, "the coverage note"),
                     "County auditors' sample ballots and candidate listings for the November 3, 2026 General Election; the Secretary of "
                     "State's results of the June 2, 2026 primary; Iowa Code section 49.31 (order of names on the ballot)", AUDITORS_URL)]
    out["sources"].append((SRC_COUSUB, STATE, "place codes", "U.S. Census Bureau", "2020 Census county subdivision codes, Iowa (st19_ia_cousub2020.txt)",
                           COUSUB_URL, "", day_of(cousub_path), sha_of(cousub_path), sum(len(v) for v in known_all.values()),
                           "Township names and codes only: a township named on a ballot is filed under the one township of that name in its county."))
    if sites.get("sha256"):
        out["sources"].append((SRC_AUDITORS, STATE, "official page", "Iowa Secretary of State", "County Auditor List", AUDITORS_URL, "", sites["fetched"],
                               sites["sha256"], len(sites["sites"]),
                               "Read only for the address of each county auditor's own site, given beside the counties whose lists are not loaded "
                               "yet. The page's telephone numbers and e-mail addresses are not read or kept."))
    if pindex is not None:
        out["sources"].append(("ia-sos-2026-primary-results-list", STATE, "official results", "Iowa Secretary of State",
                               "Election results system: the list of elections", pindex["list_url"], "", pindex["fetched"], pindex["list_sha256"],
                               pindex["list_rows"], "Read only to find the 2026 Primary Election of June 2, 2026."))
        out["sources"].append(("ia-sos-2026-primary-results-counties", STATE, "official results", "Iowa Secretary of State",
                               "2026 Primary Election (June 2, 2026): election settings, with each county's results page", pindex["url"], "",
                               pindex["fetched"], pindex["sha256"], len(pindex["counties"]),
                               "Read only for where each county's results summary sits; the version number in its address comes from the "
                               "system's current-version file."))
    out["totals"], out["by_county"], out["loaded"] = totals, by_county, n_loaded
    return out


# ---------- the load ----------

def load(db_path, say=print, extract_dir=os.path.join(CACHE, "ia")):
    net.patient_lookups()
    g_rows, g_url, g_sha, g_fetched, g_how = get_list("general", fed.PAGE, "November 3, 2026 General Election", 2, extract_dir, say)
    p_rows, p_url, p_sha, p_fetched, p_how = get_list("primary", fed.PRIMARY_PAGE, "June 2, 2026 Primary Election", 30, extract_dir, say)
    c_path, c_url = get_canvass(say)
    published, counted = canvass(c_path)
    seats, offices, as_of = roster()
    cmap = counties()

    # the November list: the state races, and each party's running mate for Lieutenant Governor
    races, general, mates = {}, [], {}
    empty = Counter()
    for office, party, name in g_rows:
        if NOBODY.match(name):
            empty["general"] += 1
            continue
        if office == RUNNING_MATE:
            mates.setdefault(party, []).append(name)
            continue
        o = office_of(office)
        if o is None:
            continue
        races.setdefault(o["race_id"], o)
        general.append((o["race_id"], party, name))
    n_state_listed = len(general)

    # the June 2 primary list, by race and party
    ballots = {}
    for office, party, name in p_rows:
        o = office_of(office)
        if o is None:
            continue
        if NOBODY.match(name):
            empty["primary"] += 1
            continue
        if o["race_id"] not in races:
            raise SystemExit(f"Iowa (state races): {office} was on the primary ballot but is not on the November list")
        ballots.setdefault((o["race_id"], party), []).append(name)

    # canvass sections for state offices, by race and party
    sections, places = {}, {}
    for (office, party), c in counted.items():
        o = office_of(office)
        if o is None:
            continue
        if o["race_id"] not in races:
            raise SystemExit(f"Iowa (state races): the canvass has {office}, which is not on the November list")
        sections[(o["race_id"], party)] = c
        places.setdefault(o["race_id"], set()).update(c["places"])
    for key, names in ballots.items():
        c = sections.get(key)
        if c is None:
            raise SystemExit(f"Iowa (state races): {key} was on the primary list but has no canvass section")
        if sorted(fold(n).replace(" ", "") for n in names) != sorted(fold(n).replace(" ", "") for n in c["names"]):
            raise SystemExit(f"Iowa (state races): {key}: the primary list and the canvass name different candidates")
    for key, c in sections.items():
        if c["names"] and key not in ballots:
            raise SystemExit(f"Iowa (state races): the canvass names candidates for {key}, the primary list nobody")

    # checks on which seats are on the ballot
    sen = sorted(int(r["district"]) for r in races.values() if r["office_kind"] == "state_senate")
    hou = sorted(int(r["district"]) for r in races.values() if r["office_kind"] == "state_house")
    if hou != list(range(1, 101)):
        raise SystemExit(f"Iowa (state races): the November list has House districts {hou}, not all 100")
    if sen != list(range(1, 50, 2)):
        say(f"    CHECK Iowa (state races): Senate districts on the list are {sen}, not the 25 odd-numbered ones")
    missing_statewide = sorted(set(v[0] for v in STATEWIDE.values()) - {r["race_id"].split("-")[-1] for r in races.values()})
    if missing_statewide:
        say(f"    CHECK Iowa (state races): statewide offices not on the November list: {missing_statewide}")

    # today's holders and the sitting member on the ballot
    holders, notes = {}, {}
    for rid, r in races.items():
        h = None
        if r["chamber"]:
            h = seats.get((r["chamber"], r["district"]))
            if h is None:
                notes[rid] = f"The Open States roster ({as_of}) lists no sitting member for this seat."
        elif r["roster"]:
            h = offices.get(r["roster"])
        else:
            notes[rid] = "The Open States roster this site uses does not carry this office, so today's holder is not shown."
        holders[rid] = h
    if "2026-IA-GOV" in races:
        notes["2026-IA-GOV"] = ("Iowa elects the Governor and Lieutenant Governor together, on one vote. The Secretary of "
                                "State's list names each party's candidate for Lieutenant Governor on a row of its own; "
                                "each is named here in the note of the same party's candidate for Governor.")

    names_in = {}
    for rid, party, name in general:
        names_in.setdefault(rid, set()).add(name)
    for (rid, party), names in ballots.items():
        names_in[rid].update(names)
    sitting, party_differs = {}, []
    for rid, h in holders.items():
        if not h:
            continue
        fit = {fold(n) for n in names_in.get(rid, ()) if holder_fits(n, h)}
        if len(fit) == 1:
            sitting[rid] = (fit.pop(), h["id"])
    for rid, party, name in general:
        if rid in sitting and fold(name) == sitting[rid][0] and holders[rid]["party"] and holders[rid]["party"] != party:
            party_differs.append(rid)

    # rows
    cand = []
    mate_note, unpaired = {}, []
    gov_parties = [p for rid, p, _n in general if rid == "2026-IA-GOV"]
    for party, ms in mates.items():
        if len(ms) == 1 and gov_parties.count(party) == 1:
            mate_note[party] = f"Running mate for Lieutenant Governor: {ms[0]}."
        else:
            unpaired.extend(f"{party}: {m}" for m in ms)
    for p in gov_parties:
        if p not in mates:
            unpaired.append(f"{p}: no running mate on the list")
    nominee = {(rid, party): fold(name) for rid, party, name in general}
    for rid, party, name in general:
        inc = rid in sitting and fold(name) == sitting[rid][0]
        note = []
        if rid == "2026-IA-GOV" and party in mate_note:
            note.append(mate_note[party])
        if party in ("Republican", "Democratic") and not any(same_name(name, n) for n in ballots.get((rid, party), [])):
            note.append(f"Not on the June 2 {party} primary ballot; nominated afterwards (the list does not say how).")
        cand.append((rid, "general", GENERAL, name, party, party_code(party), None, 1 if inc else 0, 0, None, None, None,
                     sitting[rid][1] if inc else None, SRC_GENERAL, " ".join(note) or None))

    fields, convention, odd = Counter(), [], []
    for (rid, party), names in sorted(ballots.items()):
        if len(names) < 2:
            continue
        c = sections[(rid, party)]
        fields[races[rid]["office_kind"] if races[rid]["level"] == "legislature" else "statewide"] += 1
        votes = {fold(n).replace(" ", ""): v for n, v in zip(c["names"], c["votes"])}
        total = sum(c["votes"]) + c["write_in"]
        top = max(votes, key=votes.get)
        if list(votes.values()).count(votes[top]) > 1:
            raise SystemExit(f"Iowa (state races): {rid} {party}: a tie at the top of the primary")
        outright = bool(total) and 100 * votes[top] / total >= fed.THRESHOLD
        pick = nominee.get((rid, party))
        chosen = top if outright else (pick.replace(" ", "") if pick else None)
        swapped = outright and (pick is None or pick.replace(" ", "") != top)
        if not outright:
            convention.append(f"{rid} {party}")
        elif swapped:
            odd.append(f"{rid} {party}")
        for name in names:
            k = fold(name).replace(" ", "")
            v = votes[k]
            inc = rid in sitting and fold(name) == sitting[rid][0]
            note = None
            if not outright:
                note = "No candidate won the 35 percent of the vote Iowa law requires, so a party convention chose the nominee."
            elif swapped and k == top:
                note = "Won the primary, but is not on the November list for this party."
            elif swapped and pick and k == pick.replace(" ", ""):
                note = ("Lost the primary, but is this party's candidate on the November list "
                        "(the list does not say how the nomination was made).")
            cand.append((rid, f"primary-{c['code']}", PRIMARY, name, party, party_code(party), None, 1 if inc else 0, 0, v,
                         round(100 * v / total, 1) if total else None, "advanced" if k == chosen else "lost",
                         sitting[rid][1] if inc else None, SRC_CANVASS, note))

    race_rows = []
    for rid, r in sorted(races.items()):
        h = holders[rid]
        cids = None
        if r["level"] == "legislature":
            got = places.get(rid, set())
            unknown = sorted(p for p in got if fold(p) not in cmap)
            if unknown:
                raise SystemExit(f"Iowa (state races): county names in the canvass not in the Census file: {unknown}")
            if not got:
                raise SystemExit(f"Iowa (state races): no county rows in the canvass for {rid}")
            cids = ",".join(sorted(cmap[fold(p)][0] for p in got))
        race_rows.append((rid, STATE, r["level"], r["office_kind"], r["office"], NAME, FIPS, cids, r["district"], None, 0, 1,
                          h["id"] if h else None, h["full"] if h else None, h["party"] if h else None, GENERAL, notes.get(rid)))

    place_rows = [("county", geoid, full, json.dumps([geoid]), SRC_COUNTIES) for geoid, full in sorted(cmap.values())]
    n_primary_listed = sum(len(v) for v in ballots.values())
    n_sections = len(sections)

    # the county and township pass: nothing above is changed by it
    L = local_rows(cmap, say)
    clash = {r[0] for r in L["races"]} & {r[0] for r in race_rows}
    if clash:
        raise SystemExit(f"Iowa: a local race shares its id with a state race ({sorted(clash)[:3]})")

    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA + EXTRA_SCHEMA)
    with con:
        con.execute("DELETE FROM sl_candidates WHERE race_id LIKE '2026-IA-%'")
        con.execute("DELETE FROM sl_races WHERE state = 'IA'")
        con.execute("DELETE FROM sl_sources WHERE state = 'IA'")
        con.execute("DELETE FROM sl_places WHERE (kind = 'county' AND id GLOB '19[0-9][0-9][0-9]') OR source_id LIKE 'ia-%'")
        con.execute("DELETE FROM sl_gaps WHERE state = 'IA'")
        con.execute("DELETE FROM sl_notes WHERE state = 'IA'")
        con.executemany("INSERT INTO sl_races VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", race_rows + L["races"])
        con.executemany("INSERT INTO sl_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", cand + L["cands"])
        con.executemany("INSERT INTO sl_places VALUES (?,?,?,?,?)", place_rows + sorted(L["places"].values()))
        con.executemany("INSERT INTO sl_gaps VALUES (?,?,?,?,?,?,?)", L["gaps"])
        con.executemany("INSERT INTO sl_notes VALUES (?,?,?,?,?)", L["notes"])
        con.executemany("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", L["sources"])
        src = [
            (SRC_GENERAL, STATE, "official candidate list", "Iowa Secretary of State",
             "Candidate List, November 3, 2026 General Election", g_url, "", g_fetched, g_sha, n_state_listed + sum(len(v) for v in mates.values()),
             "Office, party and ballot name read (from " + g_how + "); the address, phone, e-mail and filing-date columns are never "
             "read. The list does not state a ballot order and its order is not strictly by party, so no ballot order is stored. "
             "Rows for Lieutenant Governor are named in the notes of the same party's candidate for Governor."),
            (SRC_PRIMARY_LIST, STATE, "official candidate list", "Iowa Secretary of State",
             "Candidate List, June 2, 2026 Primary Election", p_url, "", p_fetched, p_sha, n_primary_listed,
             "Who was on each party's primary ballot for the state offices, and the names as printed; office, party and ballot "
             "name read (from " + p_how + "), the address, phone, e-mail and filing-date columns never read."),
            (SRC_CANVASS, STATE, "official results", "Iowa Secretary of State",
             f"Election Canvass Summary, 2026 Primary Election held on Tuesday, June 02, 2026 (canvass date "
             f"{published[5:7]}/{published[8:]}/{published[:4]})", c_url, published, mdate(c_path), sha_of(c_path),
             sum(len(c["names"]) for c in sections.values()),
             f"Statewide totals of {n_sections} state-office party primaries, each checked against its county rows. Shares are of "
             "the candidates' votes plus write-ins; write-ins are not listed, under and over votes are left out. The counties "
             "listed under each legislative district are the race's county_ids. "
             + (f"Went to a party convention (no one reached 35 percent): {', '.join(convention)}." if convention
                else "Every state-office primary with a field was won outright (35 percent or more).")
             + (f" Primary winner not on the November list: {', '.join(odd)}." if odd else "")),
            (SRC_ROSTER, STATE, "roster", "Open States people project (CC0)",
             "Iowa legislators and statewide officials, as loaded into state_ia.sqlite", "https://github.com/openstates/people",
             as_of, as_of, "", len(seats) + len(offices),
             "Today's holder of each seat and office. The roster does not carry the Auditor, the Treasurer or the Secretary of "
             "Agriculture. A candidate is marked as the sitting member only when the name fits the holder of that seat and no "
             "other candidate in the race fits."),
            (SRC_COUNTIES, STATE, "boundaries", "U.S. Census Bureau",
             "Cartographic boundary file, counties, 2024, 1:500,000 (cb_2024_us_county_500k)",
             "https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_county_500k.zip", "", mdate(COUNTY_ZIP),
             sha_of(COUNTY_ZIP), len(place_rows), "Iowa's 99 counties: names and GEOIDs only."),
        ]
        con.executemany("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", src)
    con.close()

    # the report: counts only
    by = Counter(r["office_kind"] if r["level"] == "legislature" else "statewide" for r in races.values())
    gen_by = Counter(races[rid]["office_kind"] if races[rid]["level"] == "legislature" else "statewide" for rid, _p, _n in general)
    one = Counter(races[rid]["office_kind"] if races[rid]["level"] == "legislature" else "statewide"
                  for rid, k in Counter(rid for rid, _p, _n in general).items() if k == 1)
    inc_by = Counter(races[rid]["office_kind"] if races[rid]["level"] == "legislature" else "statewide" for rid in sitting)
    say(f"    Iowa (state races): {by['state_senate']} Senate seats (odd districts), {by['state_house']} House seats, "
        f"{by['statewide']} statewide offices; {len(general)} candidates on the November ballot "
        f"(Senate {gen_by['state_senate']}, House {gen_by['state_house']}, statewide {gen_by['statewide']}; "
        f"one candidate only: Senate {one['state_senate']}, House {one['state_house']}, statewide {one['statewide']}); "
        f"sitting member on the ballot: Senate {inc_by['state_senate']}, House {inc_by['state_house']}, statewide {inc_by['statewide']}; "
        f"primary fields: Senate {fields['state_senate']}, House {fields['state_house']}, statewide {fields['statewide']}; "
        f"{n_sections} canvass sections reconciled")
    say(f"    Iowa (state races): \"--\" (no candidate) on the November list {empty['general']} times, on the primary list "
        f"{empty['primary']} times (state offices); {n_primary_listed} state candidates on the primary list")
    if convention:
        say(f"    Iowa (state races): to a convention: {', '.join(convention)}")
    if odd:
        say(f"    CHECK Iowa (state races): primary winner not on the November list: {', '.join(odd)}")
    if unpaired:
        say(f"    CHECK Iowa (state races): running mates not paired: {unpaired}")
    if party_differs:
        say(f"    CHECK Iowa (state races): sitting member listed under another party: {party_differs}")
    vac = [rid for rid, h in holders.items() if h is None and races[rid]["level"] == "legislature"]
    if vac:
        say(f"    Iowa (state races): no sitting member in the roster for {', '.join(vac)}")

    T = L["totals"]
    say(f"    Iowa local: {len(L['races'])} contests and {len(L['cands'])} candidates in {L['loaded']} of 99 counties "
        f"(county offices {T['county']}, townships {T['township']}, soil and water {T['soil_water']}, hospital trustees {T['hospital']}, "
        f"extension councils and other districts {T['other']}); {T['contests with no candidate']} contests with no name printed; "
        f"parties: {T['parties the June primary confirms']} confirmed by the June primary, "
        f"{T['partisan candidates who were not on a June primary ballot']} not on a primary ballot, "
        f"{T['names with no party printed, settled by the June primary']} printed with no party and settled by the primary, "
        f"{T['names with no party printed']} with no party printed; {T['files']} files read; "
        f"{sum(1 for g in L['gaps'] if g[1] == 'county')} county gaps recorded")
    for line in L["report"]:
        say(f"      {line}")
    for line in L["checks"]:
        say(f"      CHECK {line}")
    return len(cand) + len(L["cands"])


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: python ballot/state_local_ia.py <database file>")
    load(sys.argv[1])
