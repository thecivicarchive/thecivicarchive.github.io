"""
ballot/state_local_mo.py - Missouri's state races on the November 3, 2026 ballot: the Missouri Senate seats up this year
(the 17 even-numbered districts; Missouri elects half its Senate every two years), all 163 Missouri House seats, the
State Auditor (the only statewide office on this year's ballot), and the retention votes for the Supreme Court and the
Court of Appeals, with the August 4 party primaries that chose the nominees; and its local races as far as official
lists reach them: the circuit and associate circuit judges, and the county (and a few city and school) contests on the
notices and sample ballots of the election authorities read so far (see "The local part" below). Written into
ballot_local_2026.sqlite (never ballot_2026.sqlite).

    python ballot/state_local_mo.py <database file>

Sources, all the Missouri Secretary of State's own, the same three the federal loader (ballot/lists/mo.py) reads:

  - Certification of Candidates and Party Emblems, General Election, Tuesday, November 3, 2026 (PDF, "Certified
    Candidates - November 2026" on sos.mo.gov/elections). It goes party by party ("REPUBLICAN CANDIDATES" ...),
    office by office ("For State Senator"), one line a candidate ("District 2, Name"; the State Auditor and the Supreme
    Court by name alone; the Court of Appeals as "Eastern District, Name"), then a "JUDICIAL CANDIDATES" section for the
    judges standing for retention under Article V, Section 25(c) of the Missouri Constitution. It carries no candidate
    addresses; the Secretary's own office address on its cover and notice pages is never read (only lines inside a
    party or judicial section are). The federal loader's cached copy is read when it is fresh; otherwise the PDF is
    fetched into memory and never written to disk. What was read is kept as a small JSON extract with the file's SHA-256.
  - Certified Candidate List, 2026 Primary Election (s1.sos.mo.gov/CandidatesOnWeb, election 750006905): under each
    office, one table per party with Name, Mailing Address, Random Number and Date Filed. Only the Name column is ever
    read; the page is parsed in memory and never saved; office, party, place in the table and name are kept as JSON.
  - Withdrawn/Removed Candidates for the same primary: its Candidate cell runs the name, the party in brackets and the
    mailing address together; only the name and the party before the bracket are kept, with the office, the reason and
    the date. Removed candidates were not on the primary ballot and are left off.

What the record does not say, the loader does not say:
  - The certification prints no ballot numbers. A race's ballot order is the certification's own order: the parties in
    the order it lists them (Republican, Democratic, Libertarian, Independent), as the federal loader does. It lists no
    write-in candidates.
  - The primary list is the Secretary's candidate placement list, one table per party in ballot order; a primary
    candidate's ballot_order is the place in that table.
  - No primary vote counts: the Secretary's results page offers only the unofficial election-night site
    (enr.sos.mo.gov, which answers scripts with a Cloudflare challenge), and no official results file for August 4,
    2026 was posted as of 2026-09-30. Every primary row has votes None. Who advanced is read from the November
    certification: the party's nominee for that seat, when exactly one name on the party's primary ballot fits it.
  - Today's holders come from the Open States roster in state_mo.sqlite (legislators by chamber and district). The
    roster does not carry the State Auditor or any judge, so the Auditor's race shows no holder. A judge standing for
    retention is by law the sitting judge (Article V, Section 25(c)), so that one name is the holder and is marked as
    the sitting judge.
  - A candidate is marked as the sitting member only when the name fits the roster's holder of that same seat and no
    other candidate in the race fits.
  - U.S. Representative lines are the federal loader's.

The local part (county and city offices, local judges)
------------------------------------------------------
Missouri has no statewide list of county candidates: they file with each county's election authority (the county
clerk in most counties; a board of elections in St. Louis County, the City of St. Louis, Kansas City, and Jackson, Clay
and Platte counties; an elected director of elections in St. Charles County), and each authority publishes its own
notice of election or sample ballot. So the local rows come from two places:

  - The Secretary of State's certification (the same PDF as above) also lists the circuit judges elected by party and,
    in its judicial section, the circuit and associate circuit judges on whom voters decide Yes or No (Article V,
    Section 25(c)). They are stored under level "court": circuit_court for a contest between candidates,
    circuit_court_retention for a retention vote. Which counties a circuit covers comes from the Secretary of State's
    Official Manual 2025-2026, chapter 5 ("Counties: ..." under each circuit); the chapter is read in memory and only
    the circuit numbers and county names are kept. Circuit 22 has no county line there: it is the City of St. Louis,
    the one county-equivalent the other 45 circuits leave out (the loader checks that they cover the 114 counties).
  - AUTHORITIES, below: one entry an election authority, largest county first, with the address of its November 3
    notice of election, sample ballot or ballot proof, each found by hand on the authority's own site on 2026-10-01 and
    never guessed. These are ballots: an office heading, "Vote for one", names and parties, and, apart, questions and
    retention votes. None has a contact column. A document is fetched into memory with states/net.py, read, and kept
    only as a JSON extract in ballot_cache/mo/local/ (the headings of contests between people, the vote-for number,
    names and parties, with the file's SHA-256), so a re-run within a week downloads nothing. State and federal
    contests on a county's list are counted and left to the certification; questions, amendments and propositions
    are not loaded; a party's "no candidate filed" line is not a candidate.

Reading a ballot. Each document is cut into its columns (the edges are in its entry), its lines are read top to bottom,
and a contest is the heading above a "Vote for" line with the names under it. Three checks keep the reading honest: a
name with a party that falls outside every contest stops the reading; the party labels printed in the whole document
are counted a second way (without columns or contests) and must equal the names with a party read into contests; and
a heading the loader does not know is never filed under a guess: the contest goes into sl_gaps. When a document cannot
be read, the loader names the document, the page and the check, never the line, and the county gets a gap.

What the record does not say, the loader does not say (local):
  - Names printed in capitals are shown in ordinary capitals, and the candidate's note says so; a name printed in
    ordinary capitals on another authority's list for the same contest is used as printed.
  - ballot_order is the place on the sample ballot or notice. A contest printed by two authorities (Jackson County's
    executive and at-large legislators, on the county board's and the Kansas City board's lists) is one race; the two
    lists must agree, and if their orders differ no order is given.
  - A circuit judge contest is also printed on the county's ballot. When that ballot and the certification name
    different candidates, no name is shown: the race is kept with the reason, and a race-level gap says what each list
    prints.
  - Cities, school boards and special districts elect in April (RSMo 115.121.3), so they appear here only where a seat
    is on a November list (a St. Charles council seat for the rest of a term; the St. Louis Board of Education).
  - A site that turns scripts away (St. Louis County: a Cloudflare check) is never worked around. A notice or sample
    ballot saved by hand as a PDF into ballot_cache/mo/local/<authority key>/ (st_louis_county, clay, ...) is read
    when it is there, with the same checks, only if its own text names the county and one of the known layouts fits
    it; a saved web page (.html) is read line by line for headings and names that carry a party. Both readers were
    tried on stand-ins only (another county's ballot, which was refused, and a made-up page): they must be checked
    against the real file when John saves one.
  - sl_gaps holds every county whose list is not loaded, with the reason; sl_notes holds the calendar and coverage.
"""

import collections
import datetime as dt
import glob
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

from ballot.check_local import EXTRA_SCHEMA, contact_like                   # noqa: E402
from ballot.common import CACHE, HERE, fold, name_parts, party_code          # noqa: E402
from ballot.lists import mo as fed                                          # noqa: E402
from ballot.match import fits                                               # noqa: E402
from ballot.pdftext import PDF, Font, Ref, _mul, _ops, join, rows as pdf_rows      # noqa: E402
from states import net                                                     # noqa: E402

STATE, FIPS, NAME = "MO", "29", "Missouri"
GENERAL = "2026-11-03"
PRIMARY = fed.PRIMARY
ROSTER_DB = os.path.join(HERE, "state_mo.sqlite")
COUNTY_ZIP = os.path.join(HERE, "states_cache", "census", "cb_2024_us_county_500k.zip")
FED_PDF = os.path.join(CACHE, "mo", "mo_2026_general_certified_candidates.pdf")

SCHEMA = """
CREATE TABLE IF NOT EXISTS sl_races (race_id TEXT PRIMARY KEY, state TEXT NOT NULL, level TEXT NOT NULL, office_kind TEXT NOT NULL, office TEXT NOT NULL, jurisdiction TEXT, jurisdiction_id TEXT, county_ids TEXT, district TEXT, seat TEXT, special INTEGER NOT NULL DEFAULT 0, partisan INTEGER NOT NULL, holder_id TEXT, holder_name TEXT, holder_party TEXT, election_date TEXT NOT NULL, note TEXT);
CREATE TABLE IF NOT EXISTS sl_candidates (race_id TEXT NOT NULL, election TEXT NOT NULL, election_date TEXT, name TEXT NOT NULL, party TEXT, party_code TEXT, ballot_order INTEGER, incumbent INTEGER NOT NULL DEFAULT 0, write_in INTEGER NOT NULL DEFAULT 0, votes INTEGER, pct REAL, outcome TEXT, state_member_id TEXT, source_id TEXT, note TEXT, PRIMARY KEY (race_id, election, name));
CREATE TABLE IF NOT EXISTS sl_sources (source_id TEXT PRIMARY KEY, state TEXT, kind TEXT, agency TEXT, title TEXT, url TEXT, published TEXT, fetched TEXT, sha256 TEXT, rows INTEGER, note TEXT);
CREATE TABLE IF NOT EXISTS sl_places (kind TEXT NOT NULL, id TEXT NOT NULL, name TEXT NOT NULL, county_ids TEXT, source_id TEXT, PRIMARY KEY (kind, id));
"""

SRC_GENERAL = "mo-sos-2026-sl-general-certification"
SRC_PRIMARY = "mo-sos-2026-sl-primary-list"
SRC_REMOVED = "mo-sos-2026-sl-primary-removed"
SRC_ROSTER = "mo-openstates-roster"
SRC_COUNTIES = "mo-census-cb-2024-county"

NONPARTISAN, NONPARTISAN_CODE = "Nonpartisan office", "N"
RETENTION_NOTE = ("A retention vote under Article V, Section 25(c) of the Missouri Constitution: voters answer Yes or No on "
                  "whether this judge stays in office. There is no opponent and no party label.")

# the certification's office headings: what each line under it is
HEADINGS = {
    "For State Auditor": "AUD",
    "For State Senator": "SS",
    "For State Representative": "SH",
    "For the Missouri Supreme Court": "SC",
    "For the Missouri Court of Appeals": "COA",
    "For U.S. Representative": "federal",
    "For Circuit Judge": "local court",
    "For Associate Circuit Judge": "local court",
}
END = ("CERTIFICATION", "COUNTY CLERK/ELECTION AUTHORITY CERTIFICATION", "NOTICE OF ELECTION")
COA = {"Eastern": "E", "Western": "W", "Southern": "S"}


def race_of(key, district=None, seat=None):
    """{race_id, level, office_kind, office, district, seat, chamber, partisan} for a state race."""
    if key == "AUD":
        return dict(race_id=f"2026-{STATE}-AUD", level="statewide", office_kind="state_auditor", office="State Auditor",
                    district=None, seat=None, chamber=None, partisan=1)
    if key == "SS":
        return dict(race_id=f"2026-{STATE}-SS{district}", level="legislature", office_kind="state_senate",
                    office="State Senator", district=district, seat=None, chamber="Senate", partisan=1)
    if key == "SH":
        return dict(race_id=f"2026-{STATE}-SH{district}", level="legislature", office_kind="state_house",
                    office="State Representative", district=district, seat=None, chamber="House", partisan=1)
    if key == "SC":
        return dict(race_id=f"2026-{STATE}-SCRET-{seat}", level="court", office_kind="supreme_court_retention",
                    office="Judge of the Supreme Court (retention vote)", district=None, seat=None, chamber=None, partisan=0)
    if key == "COA":
        return dict(race_id=f"2026-{STATE}-COARET-{COA[district]}{seat}", level="court", office_kind="court_of_appeals_retention",
                    office="Judge of the Court of Appeals (retention vote)", district=f"{district} District", seat=None,
                    chamber=None, partisan=0)
    raise SystemExit(f"Missouri (state races): no race for {key!r}")


def primary_office(head):
    """(key, district) for a primary-list heading, ("federal"|"local court", None) for offices read elsewhere, and a
    SystemExit for anything new, so an office added to the list is noticed rather than dropped."""
    if head == "State Auditor":
        return "AUD", None
    m = re.fullmatch(r"State (Senator|Representative) - District (\d+)", head)
    if m:
        return ("SS" if m.group(1) == "Senator" else "SH"), str(int(m.group(2)))
    if fed.OFFICE.fullmatch(head.upper()) or head.upper().startswith("U.S. SENATOR"):
        return "federal", None
    if head.startswith("Circuit Judge - ") or head.startswith("Associate Circuit Judge - "):
        return "local court", None
    raise SystemExit(f"Missouri (state races): an office on the primary list the loader does not know: {head!r}")


# ---------- the November certification ----------

def read_general(data):
    """(published, [(section, key, district, name)], Counter of lines left to others). Only lines inside a party or
    judicial section are looked at; nothing is ever printed from the file."""
    pdf = PDF(data)
    months = fed.MONTHS.split("|")
    published, out, others = "", [], Counter()
    section = key = None
    for n, (page, res) in enumerate(pdf.pages(), start=1):
        for _y, runs in pdf_rows(pdf, page, res):
            text = join(runs)
            if not text:
                continue
            m = re.fullmatch(rf"({fed.MONTHS}) (\d{{1,2}}), (2026)", text)
            if m and not published and n < 6:
                published = f"{m.group(3)}-{months.index(m.group(1)) + 1:02d}-{int(m.group(2)):02d}"
                continue
            m = re.fullmatch(r"([A-Z ]+) CANDIDATES", text)
            if m:
                section, key = m.group(1).strip(), None
                continue
            if text in END:
                section = key = None
                continue
            if section is None:
                continue
            if re.fullmatch(r"[A-Z ]+ PARTY EMBLEM", text) or re.fullmatch(r"\d{1,3}", text) or text.startswith("Article V, Section 25"):
                continue
            if text.startswith("For "):
                if text not in HEADINGS:
                    raise SystemExit(f"Missouri (state races): an office heading the loader does not know, on page {n}: {text!r}")
                key = HEADINGS[text]
                continue
            if key is None:
                raise SystemExit(f"Missouri (state races): a line under {section} CANDIDATES before any office, on page {n}")
            if key in ("federal", "local court"):
                others[key] += 1
                continue
            judicial = section == "JUDICIAL"
            if judicial != (key in ("SC", "COA")):
                raise SystemExit(f"Missouri (state races): {key} lines under {section} CANDIDATES, on page {n}")
            if key in ("SS", "SH"):
                m = re.fullmatch(r"District (\d+), (.+)", text)
                if not m:
                    raise SystemExit(f"Missouri (state races): a {key} line on page {n} is not \"District N, Name\"")
                out.append((section, key, str(int(m.group(1))), m.group(2).strip()))
            elif key == "COA":
                m = re.fullmatch(r"(Eastern|Western|Southern) District, (.+)", text)
                if not m:
                    raise SystemExit(f"Missouri (state races): a Court of Appeals line on page {n} is not \"<Name> District, Name\"")
                out.append((section, key, m.group(1), m.group(2).strip()))
            else:                                  # the State Auditor and the Supreme Court: the name alone
                if re.match(r"(District|Circuit) \d", text):
                    raise SystemExit(f"Missouri (state races): a {key} line on page {n} names a district")
                out.append((section, key, None, text.strip()))
    if not published:
        raise SystemExit("Missouri (state races): the certification's date was not found")
    if not out:
        raise SystemExit("Missouri (state races): no state candidates found in the certification")
    return published, out, others


def get_general(extract_dir, say, max_age_days=7, local_dir=None):
    """The certification: the federal loader's cached copy when fresh, else fetched into memory (never saved). The last
    value returned is its circuit and associate circuit judge lines (the local part), or None when they could not be
    read; they are kept as an extract of their own in local_dir."""
    extract = os.path.join(extract_dir, "sl_mo_general_certification.json")
    courts_extract = os.path.join(local_dir or os.path.join(extract_dir, "local"), "sos_certification_local_courts.json")
    data, fetched, how = None, None, None
    if os.path.exists(FED_PDF) and time.time() - os.path.getmtime(FED_PDF) < max_age_days * 86400:
        data = open(FED_PDF, "rb").read()
        fetched, how = dt.date.fromtimestamp(os.path.getmtime(FED_PDF)).isoformat(), "the federal loader's cached copy"
    else:
        try:
            data = net.get(fed.GENERAL_URL)
            fetched, how = dt.date.today().isoformat(), "fetched into memory"
        except Exception as e:
            say(f"    Missouri (state races): could not fetch the certification ({type(e).__name__})")
    if data is None:
        if not os.path.exists(extract):
            raise SystemExit("Missouri (state races): the certification could not be read")
        ex = json.load(open(extract, encoding="utf-8"))
        say(f"    Missouri (state races): using the saved extract of the certification ({ex['fetched']})")
        courts = None
        if os.path.exists(courts_extract):                  # the same file's local judges, if they were read from this very copy
            cx = json.load(open(courts_extract, encoding="utf-8"))
            courts = [tuple(r) for r in cx["rows"]] if cx.get("sha256") == ex["sha256"] else None
        return ex["published"], [tuple(r) for r in ex["rows"]], Counter(ex["others"]), ex["sha256"], ex["fetched"], "the saved extract", courts
    if not data.startswith(b"%PDF"):
        raise SystemExit("Missouri (state races): the certification address did not return a PDF")
    published, rows, others = read_general(data)
    try:
        courts = read_local_courts(data)
    except LayoutError as e:
        courts = None
        say(f"    Missouri (local courts): the certification's circuit judge lines could not be read ({e}); none loaded")
    sha = hashlib.sha256(data).hexdigest()
    del data
    os.makedirs(extract_dir, exist_ok=True)
    with open(extract, "w", encoding="utf-8") as fh:         # section, office, district and name only
        json.dump({"url": fed.GENERAL_URL, "sha256": sha, "fetched": fetched, "published": published,
                   "others": dict(others), "rows": rows}, fh, ensure_ascii=False, indent=0)
    if courts is not None:
        os.makedirs(os.path.dirname(courts_extract), exist_ok=True)
        with open(courts_extract, "w", encoding="utf-8") as fh:      # section, office, circuit, division and name only
            json.dump({"url": fed.GENERAL_URL, "sha256": sha, "fetched": fetched, "published": published, "rows": courts},
                      fh, ensure_ascii=False, indent=0)
    return published, rows, others, sha, fetched, how, courts


# ---------- the primary list and the removed list ----------

def read_primary(raw):
    """[{office, party, order, name}] for every candidate on the certified primary list; only the Name column is read."""
    page = fed.decode(raw)
    if "2026 Primary Election" not in page or "Certified Candidate List" not in page:
        raise SystemExit("Missouri (state races): the CandidatesOnWeb page is no longer the Certified Candidate List for the 2026 Primary Election")
    page = re.sub(r"<script.*?</script>|<style.*?</style>", "", page, flags=re.S)
    parts = re.split(r"<h3[^>]*>(.*?)</h3>", page, flags=re.S)
    out = []
    for k in range(1, len(parts), 2):
        head = fed.text_of(parts[k])
        for tab in re.findall(r"<table[^>]*>(.*?)</table>", parts[k + 1], re.S):
            cap = re.search(r"<caption[^>]*>(.*?)</caption>", tab, re.S)
            heads = [fed.text_of(h) for h in re.findall(r"<th[^>]*>(.*?)</th>", tab, re.S)]
            if not cap or "Name" not in heads:
                raise SystemExit(f"Missouri (state races): a table under {head!r} has no party caption or no Name column")
            col, order = heads.index("Name"), 0
            for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", tab, re.S):
                cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
                if not cells:
                    continue
                if len(cells) != len(heads):
                    raise SystemExit(f"Missouri (state races): a row under {head!r} does not line up with its headings")
                name = fed.text_of(cells[col])
                if name:
                    order += 1
                    out.append({"office": head, "party": fed.text_of(cap.group(1)), "order": order, "name": name})
    return out


def read_removed(raw):
    """[{office, name, party, reason, date}] for every candidate taken off the primary ballot. The Candidate cell also
    holds the mailing address; only the name and the party before the bracket are kept."""
    page = re.sub(r"<script.*?</script>|<style.*?</style>", "", fed.decode(raw), flags=re.S)
    out, found = [], False
    for tab in re.findall(r"<table[^>]*>(.*?)</table>", page, re.S):
        heads = [fed.text_of(h) for h in re.findall(r"<th[^>]*>(.*?)</th>", tab, re.S)]
        if not all(k in heads for k in ("Office", "Candidate", "Reason", "Removal Date")):
            continue
        found = True
        idx = {k: heads.index(k) for k in ("Office", "Candidate", "Reason", "Removal Date")}
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", tab, re.S):
            cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
            if len(cells) != len(heads):
                continue
            who = re.match(r"(.+?) \(([A-Za-z ]+)\)", fed.text_of(cells[idx["Candidate"]]))
            out.append({"office": fed.text_of(cells[idx["Office"]]), "name": who.group(1).strip() if who else None,
                        "party": who.group(2).strip() if who else None, "reason": fed.text_of(cells[idx["Reason"]])[:40],
                        "date": fed.text_of(cells[idx["Removal Date"]]).split(" ")[0]})
    if not found:
        raise SystemExit("Missouri (state races): the removed-candidates page has no Office/Candidate/Reason table")
    return out


def kept(path, url, reader, what, say, max_age_days=7):
    """A page read in memory and kept only as the JSON of its allowed columns, refreshed when older than max_age_days;
    if the page cannot be read, the saved extract is used."""
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < max_age_days * 86400:
        return json.load(open(path, encoding="utf-8"))
    try:
        raw = net.get(url, accept="text/html")
    except Exception as e:
        if os.path.exists(path):
            ex = json.load(open(path, encoding="utf-8"))
            say(f"    Missouri (state races): could not read the {what} ({type(e).__name__}); using the saved extract ({ex['fetched']})")
            return ex
        raise SystemExit(f"Missouri (state races): could not read the {what} ({type(e).__name__}) and no extract is saved")
    ex = {"url": url, "sha256": hashlib.sha256(raw).hexdigest(), "fetched": dt.date.today().isoformat(), "rows": reader(raw)}
    del raw
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(ex, fh, ensure_ascii=False, indent=0)
    time.sleep(1.0)
    return ex


# ---------- the roster and the counties ----------

def roster(path=ROSTER_DB):
    """Today's holders: {("Senate"|"House", district): row}, plus the roster's date. Contact columns are never selected."""
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    seats = {}
    for r in con.execute("SELECT bioguide_id, first_name, last_name, official_full, party_name, chamber, district "
                         "FROM legislators WHERE is_current = 1"):
        key = (r[5], str(r[6]))
        if key in seats:
            raise SystemExit(f"Missouri (state races): the roster lists two sitting members for {key}")
        seats[key] = {"id": r[0], "first": r[1], "last": r[2], "full": r[3], "party": r[4]}
    as_of = (con.execute("SELECT max(updated_at) FROM legislators").fetchone()[0] or "")[:10]
    con.close()
    return seats, as_of


def counties(path=COUNTY_ZIP):
    """[(GEOID, "Adair County")] for Missouri's 114 counties and the City of St. Louis, from the Census Bureau's file."""
    import shapefile                                   # pyshp
    z = zipfile.ZipFile(path)
    base = next(n[:-4] for n in z.namelist() if n.endswith(".dbf"))
    rdr = shapefile.Reader(dbf=io.BytesIO(z.read(base + ".dbf")))
    fields = [f[0] for f in rdr.fields[1:]]
    out = []
    for rec in rdr.iterRecords():
        rec = dict(zip(fields, rec))
        if str(rec.get("STATEFP")) == FIPS:
            out.append((str(rec["GEOID"]), str(rec["NAMELSAD"])))
    if len(out) != 115:
        raise SystemExit(f"Missouri (state races): the county file gives {len(out)} Missouri counties, not 115")
    return sorted(out)


def holder_fits(name, h):
    cand = name_parts(name)
    return any(fits(cand, reg) for reg in ((fold(h["first"]).split(), fold(h["last"])), name_parts(h["full"] or "")) if reg[1])


def same_person(a, b):
    """Two spellings of one candidate's name on two of the Secretary's lists."""
    fa, fb = fold(a), fold(b)
    return fa == fb or fa.replace(" ", "") == fb.replace(" ", "") or fits(name_parts(a), name_parts(b))


def sha_of(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest() if os.path.exists(path) else ""


def mdate(path):
    return dt.date.fromtimestamp(os.path.getmtime(path)).isoformat() if os.path.exists(path) else ""


# ======================================================================================================================
# The local part: local judges from the certification, and each election authority's own notice or sample ballot
# ======================================================================================================================

LOCAL_DIR = os.path.join(CACHE, "mo", "local")
SRC_MANUAL = "mo-sos-official-manual-2025-2026-judicial"
SRC_PLACES = "mo-census-2020-place"
MANUAL_URL = "https://www.sos.mo.gov/cmsimages/bluebook/2025-2026/5_Judicial.pdf"
PLACE_URL = "https://www2.census.gov/geo/docs/reference/codes2020/place/st29_mo_place2020.txt"
PLACE_HEAD = ["STATE", "STATEFP", "PLACEFP", "PLACENS", "PLACENAME", "TYPE", "CLASSFP", "FUNCSTAT", "COUNTIES"]
LEA_URL = "https://www.sos.mo.gov/elections/goVoteMissouri/localelectionauthority"
CALENDAR_URL = "https://revisor.mo.gov/main/OneSection.aspx?section=115.121"
CAPS_NOTE = "The list prints names in capitals; they are shown here in ordinary capitals."
SITTING_NOTE = "Standing for retention as the sitting judge."
GAP_WHAT = "county offices and associate circuit judges"


class LayoutError(Exception):
    """A document that does not read the way it was checked to read. The message names the page and the check,
    never the line."""


class Unread(Exception):
    """A document that did not answer and has no extract to fall back on."""


# How each layout is read (contests_of, below): cols are the left and right edges of the ballot's columns in points;
# tol is how far apart two pieces of type may sit and still be one printed line; block_dy how far apart two lines may
# sit and still be one candidate (a long name runs on under its first line); party says how the party is printed
# ("codes" REP after the name, "Codes" Rep, "words" Republican, "lead" REP before the name, "none" on a line of its
# own); title says how a heading is found ("for": the lines from the one beginning "For" down to "Vote for"; "caps":
# the lines in capitals above "Vote for"; "forline": a line beginning "For", in a list with no "Vote for" lines;
# "headline": the line above the first name).
BALLOT3 = dict(cols=[(0, 208), (208, 400), (400, 612)], tol=5.0, party="codes", block_dy=16.6)
BALLOT4 = dict(cols=[(0, 180), (180, 310), (310, 438), (438, 612)], tol=3.0, party="codes", title="caps", block_dy=14.0,
               noise=r"^(Vote Both Sides o|f this Ballot|Sample Ballot|All Precincts|PROPOSITION|AMENDMENT)$")
TYPED = dict(tol=3.0, party="codes")

# One entry an election authority, the largest county first (2020 census). Every address was found by hand on
# 2026-10-01 on the authority's own site ("page" is the page that links it) and then opened and read: each is the
# November 3, 2026 document its title says. None is guessed. Two are not plain links: Kansas City's page links the
# file on Google Drive and the address here is Drive's download address for that same file, and Boone County's notice
# is not linked from the clerk's election page (which links the polling-place notice kept in the same folder); it was
# found by a search of the clerk's own site. "docs" is empty where no list could be read, and "why" says so in plain
# words. A county not named here has not been looked at yet.
AUTHORITIES = [
    dict(key="st_louis_county", county="St. Louis County", agency="St. Louis County Board of Elections",
         page="https://stlouiscountymo.gov/st-louis-county-government/board-of-elections/", docs=[],
         why="The St. Louis County Board of Elections' site turns scripts away with a check for human visitors, so its November 3 "
             "ballot content could not be read here. A copy saved by hand is read when it is in place."),
    dict(key="jackson", county="Jackson County", agency="Jackson County Election Board", area="Jackson County outside Kansas City",
         page="https://jcebmo.org/election-information/on-the-ballot/",
         docs=[dict(id="mo-jackson-2026-general-notice", kind="notice of election",
                    title="Notice of General Election: Sample Ballot, November 3, 2026",
                    url="https://jcebmo.org/wp-content/uploads/11.03.26-Notice-of-Election-Sample-Ballot-Poster.pdf",
                    spec=dict(cols=[(0, 266), (266, 525), (525, 792)], tol=5.0, party="codes", title="caps",
                              labels=r"^(JACKSON COUNTY, MISSOURI|STATE OF MISSOURI|GENERAL ELECTION|SPECIAL ELECTION|NOVEMBER 3, 2026)$",
                              noise=r"^(NOTICE OF G|ENERAL ELECTION . SAMPL|E BALLOT|Page \d+)$"))]),
    dict(key="kansas_city", county="Jackson County", agency="Kansas City Election Board", area="Kansas City within Jackson County",
         page="https://kceb.org/sample-ballot-for-november-3-2026-election/",
         docs=[dict(id="mo-kansas-city-2026-general-sample-ballot", kind="official sample ballot",
                    title="Sample Ballot, General Election, November 3, 2026, Kansas City, Missouri",
                    url="https://drive.google.com/uc?export=download&id=1K9yPQmPpIB1g9qoErahvNjTGhrBRi9A2",
                    spec=dict(tol=3.0, party="Codes", title="forline", xtol=8, noise=r"^\d+(?:st|nd|rd|th) District:$"))]),
    dict(key="st_charles", county="St. Charles County", agency="St. Charles County Election Authority",
         page="https://www.sccmo.org/410/Election-Authority",
         docs=[dict(id="mo-st-charles-2026-general-sample-ballot", kind="official sample ballot",
                    title="Sample Ballot and Notice of Election, General Election, Tuesday, November 3, 2026",
                    url="https://www.sccmo.org/DocumentCenter/View/29008", spec=BALLOT3)]),
    dict(key="st_louis_city", county="St. Louis city", agency="City of St. Louis Board of Election Commissioners",
         page="https://www.stlouis-mo.gov/government/departments/board-election-commissioners/elections/index.cfm",
         school="City of St. Louis Board of Education",
         docs=[dict(id="mo-st-louis-city-2026-general-sample-ballot", kind="official sample ballot",
                    title="Sample Ballot, General Election, City of St. Louis, November 3, 2026, All Precincts",
                    url="https://www.stlouis-mo.gov/government/departments/board-election-commissioners/documents/upload/Nov26-All-Races-Sample-Ballot.pdf",
                    spec=BALLOT4)]),
    dict(key="greene", county="Greene County", agency="Greene County Clerk", page="https://vote.greenecountymo.gov/voting-information/",
         docs=[dict(id="mo-greene-2026-general-composite-ballot", kind="official sample ballot",
                    title="November 3, 2026 General Election: Candidates and Ballot Issues (composite sample ballot)",
                    url="https://vote.greenecountymo.gov/wp-content/uploads/2026/09/Candidates_and_Ballot_Issues_Composite_November_2026.pdf",
                    spec=dict(tol=3.0, party="codes",
                              noise=r"^(OFFICE OF THE GREENE COUNTY CLERK|November 3, 2026 General Election|Candidates and Ballot Issues|"
                                    r"General Election Candidates)$"))]),
    dict(key="clay", county="Clay County", agency="Clay County Board of Election Commissioners", page="https://www.voteclaycountymo.gov/elections",
         docs=[],
         why="The Clay County Board of Election Commissioners' site linked no notice of election or countywide sample ballot for "
             "November 3 when it was read on October 1, 2026; it shows each voter a ballot by address. Not loaded yet."),
    dict(key="jefferson", county="Jefferson County", agency="Jefferson County Clerk", page="https://www.jeffcomo.org/SampleBallot.aspx?nodeID=VoterInformation",
         docs=[dict(id="mo-jefferson-2026-general-sample-ballot", kind="official sample ballot",
                    title="November 3, 2026 General Election County-Wide Sample Ballot",
                    url="https://www.jeffcomo.org/DocumentCenter/View/22933/November-3-2026-General-Election-County-Wide-Sample-Ballot-PDF",
                    spec=BALLOT3)]),
    dict(key="boone", county="Boone County", agency="Boone County Clerk", page="https://www.boonemo.gov/clerk/elections/",
         docs=[dict(id="mo-boone-2026-general-notice", kind="notice of election", title="Notice of General Election (November 3, 2026)",
                    url="https://www.boonemo.gov/clerk/webpublish/elections/notices/election-notice.pdf",
                    spec=dict(tol=3.0, party="none", party_line=True))]),
    dict(key="jasper", county="Jasper County", agency="Jasper County Clerk", page="https://www.jaspercountymo.gov/county-clerk",
         docs=[dict(id="mo-jasper-2026-general-sample-ballots", kind="official sample ballot",
                    title="Sample Ballots for the November 3rd, 2026 General Election (every ballot type)",
                    url="https://www.jaspercountymo.gov/_files/ugd/d9f579_55f86f639dc64d3c87994d6d910ebe21.pdf",
                    spec=dict(cols=[(0, 232), (232, 402), (402, 612)], tol=3.0, party="codes"))]),
    dict(key="cass", county="Cass County", agency="Cass County Clerk", page="https://www.casscounty.com/2352/Sample-Ballots",
         docs=[dict(id="mo-cass-2026-general-sample-ballot", kind="official sample ballot", title="November 2026 Sample Ballot",
                    url="https://www.casscounty.com/DocumentCenter/View/4496/November-2026-Sample-Ballotpdf", spec=BALLOT3)]),
    dict(key="platte", county="Platte County", agency="Platte County Board of Elections", page="https://www.plattecountymovotes.gov/",
         docs=[dict(id="mo-platte-2026-general-ballot-proof", kind="official sample ballot",
                    title="Election Proof: General Election, Platte County, Missouri, November 3, 2026",
                    url="https://www.plattecountymovotes.gov/s/Election_Proof_Report_136.pdf",
                    spec=dict(cols=[(0, 208), (208, 400), (400, 612)], tol=5.0, party="words"))]),
    dict(key="franklin", county="Franklin County", agency="Franklin County Clerk", page="https://www.franklinmo.gov/176/Election-Information",
         docs=[dict(id="mo-franklin-2026-general-list", kind="official candidate list", title="Franklin County General Election, November 3, 2026",
                    url="https://www.franklinmo.gov/DocumentCenter/View/484", spec=dict(tol=3.0, party="lead", title="headline"))]),
    dict(key="christian", county="Christian County", agency="Christian County Clerk",
         page="https://www.christiancountymo.gov/offices/county-clerk/sample-ballots/",
         docs=[dict(id=f"mo-christian-2026-general-sample-ballot-{n}", kind="official sample ballot",
                    title=f"Sample Ballot, General Election, Tuesday, November 3, 2026 (ballot type {n})",
                    url=f"https://www.christiancountymo.gov/wp-content/uploads/SAMPLE-BT-{n}-{v}.pdf", spec=BALLOT3)
               for n, v in ((1, 5), (2, 4), (3, 3))]),
    dict(key="cole", county="Cole County", agency="Cole County Clerk", page="https://colecounty.org/441/Sample-Ballots",
         docs=[dict(id="mo-cole-2026-general-sample-ballot", kind="official sample ballot", title="November 3, 2026 Cole County Combined Sample Ballot",
                    url="https://colecounty.org/DocumentCenter/View/14428/November-3-2026-Cole-County-Combined-Sample-Ballot", spec=BALLOT3)]),
]
# the layouts tried, in turn, on a notice or sample ballot saved by hand (a reading counts only if every check passes)
SAVED_PDF_SPECS = [BALLOT3, BALLOT4, TYPED, dict(tol=3.0, party="codes", title="caps"), dict(tol=3.0, party="none", party_line=True),
                   dict(tol=3.0, party="lead", title="headline")]
SAVED_PAGE_SPECS = [dict(flat=True, party="any"), dict(flat=True, party="any", title="caps"), dict(flat=True, party="lead", title="headline")]


# ---------- a PDF's text, drawn pages included ----------

def page_runs_all(pdf, page, res):
    """(x, y, size, text, x_end) for every piece of text on a page, in page coordinates: ballot.pdftext's page_runs,
    with two things a ballot needs. Text drawn inside a form (a ballot drawn once and placed on the page) is read too,
    and the type settings are put back when a saved state is restored, as the format says they are."""
    out = []
    contents = pdf.get(page.get("Contents"))
    parts = contents if isinstance(contents, list) else [page.get("Contents")]
    data = b"\n".join(pdf.stream(p) or b"" for p in parts if isinstance(p, Ref))
    _draw_text(pdf, data, pdf.get(res) or {}, [1, 0, 0, 1, 0, 0], out, 0)
    return out


def _draw_text(pdf, data, res, ctm, out, depth):
    fonts = {}
    fres = pdf.get(res.get("Font")) or {}
    xres = pdf.get(res.get("XObject")) or {}
    saved = []
    tm = tlm = [1, 0, 0, 1, 0, 0]
    font, size, tc, tw, th, tl, rise = None, 1.0, 0.0, 0.0, 1.0, 0.0, 0.0

    def show(s):
        nonlocal tm
        if font is None:
            return
        text, codes = font.decode(s if isinstance(s, (bytes, bytearray)) else b"")
        trm = _mul([size * th, 0, 0, size, 0, rise], _mul(tm, ctm))
        adv = 0.0
        for code in codes:
            adv += (font.width(code) * size + tc + (tw if (not font.two and code == 32) else 0)) * th
        x0, y0 = trm[4], trm[5]
        tm = _mul([1, 0, 0, 1, adv, 0], tm)
        x1 = _mul([size * th, 0, 0, size, 0, rise], _mul(tm, ctm))[4]
        if text.strip():
            out.append((x0, y0, abs(trm[3]) or size, text, x1))

    for op, a in _ops(data):
        if op == "q":
            saved.append((ctm[:], font, size, tc, tw, th, tl, rise))
        elif op == "Q":
            if saved:
                ctm, font, size, tc, tw, th, tl, rise = saved.pop()
        elif op == "cm" and len(a) == 6:
            ctm = _mul([float(x) for x in a], ctm)
        elif op == "BT":
            tm = tlm = [1, 0, 0, 1, 0, 0]
        elif op == "Tf" and len(a) == 2:
            name = str(a[0])
            if name not in fonts:
                fonts[name] = Font(pdf, fres.get(name))
            font, size = fonts[name], float(a[1])
        elif op == "Tc" and a:
            tc = float(a[0])
        elif op == "Tw" and a:
            tw = float(a[0])
        elif op == "Tz" and a:
            th = float(a[0]) / 100
        elif op == "TL" and a:
            tl = float(a[0])
        elif op == "Ts" and a:
            rise = float(a[0])
        elif op in ("Td", "TD") and len(a) == 2:
            tx, ty = float(a[0]), float(a[1])
            if op == "TD":
                tl = -ty
            tlm = _mul([1, 0, 0, 1, tx, ty], tlm)
            tm = tlm
        elif op == "Tm" and len(a) == 6:
            tm = tlm = [float(x) for x in a]
        elif op == "T*":
            tlm = _mul([1, 0, 0, 1, 0, -tl], tlm)
            tm = tlm
        elif op == "Tj" and a:
            show(a[-1])
        elif op in ("'", '"') and a:
            tlm = _mul([1, 0, 0, 1, 0, -tl], tlm)
            tm = tlm
            if op == '"' and len(a) == 3:
                tw, tc = float(a[0]), float(a[1])
            show(a[-1])
        elif op == "TJ" and a and isinstance(a[-1], list):
            for item in a[-1]:
                if isinstance(item, (bytes, bytearray)):
                    show(item)
                elif isinstance(item, (int, float)):
                    tm = _mul([1, 0, 0, 1, -float(item) / 1000.0 * size * th, 0], tm)
        elif op == "Do" and a and depth < 6:
            ref = xres.get(str(a[-1]))
            form = pdf.get(ref)
            if isinstance(form, dict) and form.get("Subtype") == "Form" and isinstance(ref, Ref):
                m = [float(pdf.get(x)) for x in (pdf.get(form.get("Matrix")) or [1, 0, 0, 1, 0, 0])]
                _draw_text(pdf, pdf.stream(ref) or b"", pdf.get(form.get("Resources")) or res, _mul(m, ctm), out, depth + 1)


def rows_of(runs, tol=None):
    """Pieces of text grouped into printed rows, top to bottom: [(y, [runs])]."""
    out = []
    for r in sorted(runs, key=lambda r: (-round(r[1], 1), r[0])):
        if out and abs(out[-1][0] - r[1]) <= (tol if tol is not None else max(1.5, 0.35 * r[2])):
            out[-1][1].append(r)
        else:
            out.append([r[1], [r]])
    return out


# ---------- a ballot's lines and contests ----------

Line = collections.namedtuple("Line", "page col y x size text")
VOTE = re.compile(r"^\(?\s*vote for (?:not more than |up to )?(one|two|three|four|five|six|\d+)\s*\)?$", re.I)
WRITEIN = re.compile(r"^(?:\(?write[- ]?in\)?|[_ ]{4,})$", re.I)
YESNO = re.compile(r"^(?:YES|NO|YES NO)$|^(?:YES|NO) - (?:FOR|AGAINST) THE\b")
NUMBER = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6}
PARTY_CODE = {"REP": "Republican", "DEM": "Democratic", "LIB": "Libertarian", "GRN": "Green", "CST": "Constitution", "IND": "Independent"}
PARTY_WORD = {"republican": "Republican", "democratic": "Democratic", "democrat": "Democratic", "libertarian": "Libertarian",
              "constitution": "Constitution", "independent": "Independent", "green": "Green"}
_C, _W = "REP|DEM|LIB|GRN|CST|IND", "Republican|Democratic|Libertarian|Independent"
# a name with its party on one line, by the way the document prints parties. Where parties are printed as words, Green
# and Constitution are left out of the words looked for: one is a family name and the other is in every amendment's
# text, and a line the rules cannot place stops the reading rather than being misread.
PARTY_TAIL = {
    "codes": re.compile(rf"^(?P<name>.+?)\s+\(?(?P<p>{_C})\)?$"),
    "Codes": re.compile(r"^(?P<name>.+?)\s+(?P<p>Rep|Dem|Lib|Grn|Cst|Ind)\.?$"),
    "words": re.compile(rf"^(?P<name>.+?)\s+(?P<p>{_W})$"),
    "lead": re.compile(rf"^(?P<p>{_C})\s+(?P<name>.+)$"),
    "any": re.compile(rf"^(?P<name>.+?)(?:\s*[-–,]\s*|\s+)\(?(?P<p>{_C}|{_W}|Democrat)\)?(?: Party)?$"),
    "none": re.compile(r"(?!)"),
}
PARTY_LINE = re.compile(rf"^\(?(?:(?P<c>{_C})|(?P<w>{_W}|Democrat)(?: Party)?|(?P<v>Green|Constitution) Party)\)?$")
# the same labels counted in a whole row of the page, columns and contests set aside (the second reading)
PARTY_COUNT = {
    "codes": re.compile(rf"(?<![A-Za-z])(?:{_C})(?![A-Za-z.])"),
    "Codes": re.compile(r"(?<![A-Za-z])(?:Rep|Dem|Lib|Grn|Cst|Ind)(?![A-Za-z])"),
    "words": re.compile(rf"(?<![A-Za-z])(?:{_W})(?![A-Za-z])"),
    "lead": re.compile(rf"(?<![A-Za-z])(?:{_C})(?![A-Za-z.])"),
    "any": re.compile(rf"(?<![A-Za-z])(?:{_C}|{_W}|Democrat)(?![A-Za-z.])"),
    "none": re.compile(rf"(?<![A-Za-z])(?:{_W}|Green|Constitution) Party(?![A-Za-z])"),
}
# the key to the party letters printed on a ballot ("REPUBLICAN (REP)", "Republican - REP", "REP = Republican Party")
LEGEND = re.compile(rf"(?i)^,?\s*(?:(?:REPUBLICAN|DEMOCRATIC|LIBERTARIAN|GREEN|CONSTITUTION|INDEPENDENT) (?:\((?:{_C})\)|- (?:{_C})),?\s*)+$"
                    rf"|^(?:{_C}) = [A-Za-z ]+$")
PARTY_KEY = re.compile(r"(?i)(?<![A-Za-z])(?:REPUBLICAN,?\s*(?:\(REP\)|- REP)|DEMOCRATIC,?\s*(?:\(DEM\)|- DEM)|LIBERTARIAN,?\s*(?:\(LIB\)|- LIB)"
                       r"|GREEN,?\s*(?:\(GRN\)|- GRN)|CONSTITUTION,?\s*(?:\(CST\)|- CST)|INDEPENDENT,?\s*(?:\(IND\)|- IND)"
                       r"|(?:REP|DEM|LIB|GRN|CST|IND) = [A-Za-z]+ Party)")
NOBODY = re.compile(r"(?i)NO CANDIDATE(?: FILED)?")
RETENTION_Q = re.compile(r"Shall Judge (?P<name>[A-Za-z][A-Za-z .,'\"()-]*?),? (?P<a>Associate )?Circuit Judge of (?:the )?Judicial Circuit "
                         r"No\. ?(?P<c>\d+)")


def party_words(token):
    return PARTY_CODE.get(token.upper()) or PARTY_WORD.get(token.lower())


def lines_of(data, spec):
    """(every printed line, column by column and top to bottom; the text of every printed row across the whole
    page) of a PDF. The second is for the second reading: it knows nothing of columns."""
    pdf = PDF(data)
    out, across = [], []
    for n, (page, res) in enumerate(pdf.pages(), 1):
        runs = [r for r in page_runs_all(pdf, page, res) if r[2] <= 30]       # a SAMPLE watermark is drawn very large
        across += [join(rs) for _y, rs in rows_of(runs, spec.get("tol"))]
        for c, (lo, hi) in enumerate(spec.get("cols") or [(0, 10 ** 6)]):
            for y, rs in rows_of([r for r in runs if lo <= r[0] < hi], spec.get("tol")):
                text = join(rs)
                if text:
                    out.append(Line(n, c, y, min(r[0] for r in rs), max(r[2] for r in rs), text))
    return out, across


def page_lines(raw):
    """A saved web page as its lines of text, in the page's own order: no columns and no positions."""
    page = re.sub(r"(?is)<(script|style|head)\b.*?</\1>", " ", fed.decode(raw))
    page = re.sub(r"(?i)</?(?:p|div|br|li|tr|h[1-6]|table|ul|ol|section|article|dt|dd|caption|thead|tbody)\b[^>]*>", "\n", page)
    out = []
    for k, piece in enumerate(page.split("\n")):
        text = fed.text_of(piece)
        if text:
            out.append(Line(1, 0, -float(k), 0.0, 10.0, text))
    return out, [ln.text for ln in out]


def party_labels(across, spec):
    count = PARTY_COUNT[spec.get("party", "codes")]
    return sum(len(count.findall(PARTY_KEY.sub(" ", text))) for text in across)


def retention_questions(lines):
    """[[circuit, 1 for an associate circuit judge, the judge's name]] for the retention questions a ballot prints."""
    text = collections.defaultdict(list)
    for ln in lines:
        text[(ln.page, ln.col)].append(ln.text)
    out = []
    for key in sorted(text):
        t = re.sub(r"\s+", " ", re.sub(r"-\s+(?=[A-Z])", "-", " ".join(text[key])))      # a hyphened name broken at a line's end
        for m in RETENTION_Q.finditer(t):
            row = [int(m.group("c")), 1 if m.group("a") else 0, m.group("name").strip()]
            if row not in out:
                out.append(row)
    return out


def contests_of(lines, spec):
    """[{title: [its lines], context: [the lines just above], n: how many to vote for, cands: [[name, party or None]],
    page}] in the document's order. A line the rules cannot place stops the reading."""
    tail = PARTY_TAIL[spec.get("party", "codes")]
    party_line = spec.get("party_line", False)       # the party is printed on a line of its own under the name
    block_dy = spec.get("block_dy")
    mode = spec.get("title", "for")
    caps, forline, headline = mode == "caps", mode == "forline", mode == "headline"
    flat = spec.get("flat", False) or headline       # no positions to go by: a name is a line that carries a party
    start = re.compile(spec.get("title_start", r"^for\s?[A-Z(]"), re.I)
    labels = re.compile(spec["labels"]) if spec.get("labels") else None
    noise = re.compile(spec["noise"]) if spec.get("noise") else None
    xtol = spec.get("xtol", 3)

    toks = []
    for ln in lines:
        t = ln.text
        if (noise and noise.search(t)) or LEGEND.match(t):
            continue
        m = VOTE.match(t)
        if m:
            toks.append(("VOTE", ln, int(NUMBER.get(m.group(1).lower(), m.group(1)))))
        elif WRITEIN.match(t):
            toks.append(("WRITEIN", ln, None))
        elif YESNO.match(t):
            toks.append(("YESNO", ln, None))
        elif PARTY_LINE.match(t):
            m = PARTY_LINE.match(t)
            toks.append(("PARTY", ln, party_words(m.group("c") or m.group("w") or m.group("v"))))
        elif tail.match(t):
            m = tail.match(t)
            toks.append(("CAND", ln, (m.group("name").strip(), party_words(m.group("p")))))
        else:
            toks.append(("TEXT", ln, None))

    # where names are printed, by page and column (a ballot's two sides are set a little apart): the commonest left
    # edge of the lines that carry a party
    edges = collections.defaultdict(Counter)
    for kind, ln, _v in toks:
        if kind == "CAND":
            edges[(ln.page, ln.col)][round(ln.x)] += 1
    name_x = {k: cnt.most_common(1)[0][0] for k, cnt in edges.items()}

    out, block, cur = [], [], None
    pending = []                                     # a name waiting for the party printed under it
    group = []                                       # the lines of one candidate (block_dy)

    def title_of(block):
        if caps:
            k = len(block)
            while k and re.fullmatch(r"[A-Z0-9 .,'&#()/–-]+", block[k - 1].text) and re.search(r"[A-Z]{2}", block[k - 1].text):
                k -= 1
            run = block[k:]
            return [b for b in run if not (labels and labels.search(b.text))], [b for b in run if labels and labels.search(b.text)]
        for k in range(len(block) - 1, -1, -1):
            if start.match(block[k].text):
                above = [b for b in block[max(0, k - 2):k] if b.page == block[k].page and b.col == block[k].col and b.y - block[k].y < 45]
                return block[k:], above
        return [], []

    def flush():
        """The lines gathered for one candidate become a name and a party (or none)."""
        nonlocal group
        if not group:
            return
        parts, party = [], None
        for g in group:
            m = PARTY_LINE.match(g.text)
            if m:
                found, text = party_words(m.group("c") or m.group("w") or m.group("v")), None
            else:
                m = tail.match(g.text)
                found, text = (party_words(m.group("p")), m.group("name").strip()) if m else (None, g.text)
            if found:
                if party:
                    raise LayoutError(f"page {g.page}: two parties beside one name")
                party = found
            if text:
                parts.append(text)
        if not parts:
            raise LayoutError(f"page {group[0].page}: a party with no name")
        cur["cands"].append([" ".join(parts), party])
        group = []

    def close():
        nonlocal cur
        if cur is not None:
            flush()
            if pending:
                raise LayoutError(f"page {pending[0].page}: a name with no party under it")
            out.append(cur)
        cur = None

    def opened(title, above, n, ln):
        return {"title": [b.text for b in title], "context": [b.text for b in above], "n": n, "cands": [], "page": ln.page, "col": ln.col,
                "vote_x": ln.x, "nx": name_x.get((ln.page, ln.col))}

    for i, (kind, ln, v) in enumerate(toks):
        nxt = toks[i + 1][0] if i + 1 < len(toks) else "END"
        if kind == "VOTE":
            if forline or headline:
                continue
            close()
            title, above = title_of(block)
            cur, block = opened(title, above, v, ln), []
            continue
        if (forline and kind == "TEXT" and start.match(ln.text)) or (headline and kind == "TEXT" and nxt == "CAND"):
            close()
            cur, block = opened([ln], [], 1 if forline else None, ln), []
            continue
        if cur is None:
            if kind in ("CAND", "PARTY") and abs(ln.x - name_x.get((ln.page, ln.col), -99)) <= xtol:
                raise LayoutError(f"page {ln.page}: a name with a party outside any contest")
            block = block + [ln] if kind == "TEXT" else []
            continue
        # a contest is open
        if kind in ("WRITEIN", "YESNO"):
            if forline and kind == "WRITEIN":
                continue                               # a typed list: the next "For" line closes the contest
            close()
            block = []
            continue
        if cur["nx"] is None and not party_line and not flat and kind == "TEXT" and not cur["cands"] and not group \
                and ln.col == cur["col"] and ln.x >= cur["vote_x"] + 8:
            cur["nx"] = round(ln.x)                    # a column with no party anywhere: names are the lines set in from the heading
        at_name = cur["nx"] is not None and ln.col == cur["col"] and ln.page == cur["page"] and abs(ln.x - cur["nx"]) <= xtol
        if party_line or flat:                         # a typed list: a name with its party, or the party on the line under the name
            if kind == "PARTY":
                if not pending:
                    raise LayoutError(f"page {ln.page}: a party with no name above it")
                cur["cands"].append([" ".join(p.text for p in pending), v])
                del pending[:]
            elif kind == "CAND":
                cur["cands"].append([v[0], v[1]])
            elif nxt == "PARTY":
                pending.append(ln)
            else:
                close()
                block = [ln]
        elif block_dy:                                 # a ballot: a candidate is one line, or two set close together
            if at_name:
                if group and group[-1].page == ln.page and group[-1].col == ln.col and 0 < group[-1].y - ln.y <= block_dy:
                    group.append(ln)
                else:
                    flush()
                    group = [ln]
            elif kind == "TEXT":
                close()
                block = [ln]
            else:
                raise LayoutError(f"page {ln.page}: a party printed away from the names")
        else:                                          # one line a candidate
            if kind == "CAND" and (at_name or forline or cur["nx"] is None):
                cur["cands"].append([v[0], v[1]])
            elif kind == "TEXT" and at_name and all(c[1] is None for c in cur["cands"]):
                cur["cands"].append([ln.text, None])    # a contest without parties
            elif kind == "TEXT" and not at_name:
                close()
                block = [ln]
            else:
                raise LayoutError(f"page {ln.page}: a line among the names that the rules cannot place")
    close()
    for c in out:
        c["cands"] = [[re.sub(r"\s+", " ", n).strip(), p] for n, p in c["cands"]]
    return out


# ---------- what a heading is ----------

STATE_LEVEL = re.compile(r"^(?:STATE AUDITOR|STATE SEN\w*|STATE REP\w*\.?|U\.? ?S\.? REP\w*\.?|UNITED STATES REP\w*)(?![A-Za-z])")
DISTRICT_ONLY = r"(?:DISTRICT \d+|\d+(?:ST|ND|RD|TH) DISTRICT(?: AT-LARGE)?)"
PLACE_LINE = re.compile(r"(?i)^(?:(?:CITY|TOWN|VILLAGE) OF .+|.+\b(?:SCHOOL|FIRE|AMBULANCE|EMERGENCY|WATER|SEWER|LIBRARY|HOSPITAL|HEALTH|ROAD|"
                        r"LEVEE|DRAINAGE)\b.*\bDISTRICT\b.*)$")
COUNTY_OFFICES = [      # (the heading once "For", terms and stray spaces are off, the office kind, its part of the race id)
    (r"PRES+IDING COMMISSIONER(?: OF THE COUNTY COMMISSION)?", "county_commissioner", "presiding-commissioner"),
    (r"(?:ASSOCIATE )?COMMISSIONER(?: OF THE COUNTY COMMISSION)?(?: -)? (?P<d>.+ DISTRICT|DISTRICT .+)", "county_commissioner", "county-commissioner"),
    (r"COUNTY CLERK|CLERK OF THE COUNTY COMMISSION", "county_clerk", "county-clerk"),
    (r"CIRCUIT CLERK|CLERK OF THE CIRCUIT COURT", "clerk_of_court", "circuit-clerk"),
    (r"RECORDER OF DEEDS", "county_recorder", "recorder-of-deeds"),
    (r"PROSECUTING ATTORNEY", "county_attorney", "prosecuting-attorney"),
    (r"(?:COUNTY )?COLLECTOR(?: OF REVENUE)?", "tax_collector", "collector"),
    (r"LICENSE COLLECTOR", "license_collector", "license-collector"),
    (r"(?:COUNTY )?AUDITOR", "county_auditor", "auditor"),
    (r"(?:COUNTY )?TREASURER", "county_treasurer", "treasurer"),
    (r"(?:COUNTY )?SHERIFF", "sheriff", "sheriff"),
    (r"(?:COUNTY )?ASSESSOR", "county_assessor", "assessor"),
    (r"(?:COUNTY )?CORONER", "coroner", "coroner"),
    (r"(?:COUNTY )?SURVEYOR", "county_surveyor", "surveyor"),
    (r"DIRECTOR OF ELECTIONS", "county_elections_director", "director-of-elections"),
    (r"COUNTY EXECUTIVE(?P<x> - [A-Z. ]+ COUNTY)?", "county_executive", "county-executive"),
    (r"COUNTY (?:COUNCIL(?: MEMBER)?|LEGISLATOR)(?: -)? (?P<d>.+)", "county_council", "county-council"),
]
SMALL_WORDS = {"of", "the", "and", "for", "in", "at", "to"}


def ordinal(n):
    n = int(n)
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", fold_digits(text)).strip("-")


def fold_digits(text):
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower().replace("&", " and ")).strip()


def squash(text):
    """A place's name for comparing only: Saint and St. the same, the kind word and the spaces off."""
    t = re.sub(r"\b(?:saint|st)\b\.?", "st", (text or "").lower())
    return re.sub(r"[^a-z0-9]", "", t)


def office_words(text):
    """A heading printed in capitals, in ordinary words: CLERK OF THE CIRCUIT COURT -> Clerk of the Circuit Court."""
    out = []
    for i, w in enumerate((text or "").split()):
        low = w.lower()
        if i and low in SMALL_WORDS:
            out.append(low)
        elif re.fullmatch(r"[IVX]+", w) or not re.search(r"[A-Za-z]", w):
            out.append(w)
        elif re.fullmatch(r"\d+(?:st|nd|rd|th)", low):
            out.append(low)
        else:
            out.append("-".join(p[:1].upper() + p[1:].lower() for p in w.split("-")))
    return " ".join(out)


def ordinary(name):
    """A name printed in capitals, in ordinary capitals: BARNETT-STILLINGS -> Barnett-Stillings, MCCULLOCH -> McCulloch,
    D'SOUZA -> D'Souza. Initials (F.X.), numerals (III) and a word already in ordinary capitals are kept as printed."""
    def word(w):
        if not re.search(r"[A-Z]{2}", w) or re.search(r"[a-z]", w) or re.fullmatch(r"I{2,3}|IV|VI{0,3}", w):
            return w
        w = w.capitalize()
        w = re.sub(r"^Mc([a-z])", lambda m: "Mc" + m.group(1).upper(), w)
        return re.sub(r"^([DO])'([a-z])", lambda m: m.group(1) + "'" + m.group(2).upper(), w)
    out = []
    for token in (name or "").split():
        lead, core, end = re.fullmatch(r"([^A-Za-z0-9]*)(.*?)([^A-Za-z0-9]*)", token).groups()
        out.append(lead + "-".join(word(p) for p in core.split("-")) + end)
    return " ".join(out)


def heading_of(title, strip_for, prev):
    """A contest's heading in capitals, "For" and stray spacing off. A heading that is a district alone ("DISTRICT 20"
    under the heading before it) takes that heading's office (prev)."""
    t = re.sub(r"\s+", " ", " ".join(title).replace("–", " - ").replace("—", " - ")).strip()
    if strip_for:
        t = re.sub(r"^(?i:for)(?:\s+|(?=[A-Z][a-z]))", "", t)
    t = re.sub(r"\b(\d+) (ST|ND|RD|TH)\b", r"\1\2", t.upper())          # an ordinal whose letters are printed small and raised
    t = re.sub(r"\s*-\s*(?=DIVISION\b|DISTRICT\b|\d)|(?<=\s)-\s*|\s*-(?=\s)", " - ", t)
    t = re.sub(r"\s+", " ", t).strip()
    if prev and re.fullmatch(DISTRICT_ONLY, t):
        t = f"{prev} {t}"
    return t


def base_of(heading):
    return re.sub(rf"(?: -)? {DISTRICT_ONLY}$", "", heading)


def district_words(d):
    m = re.fullmatch(r"DISTRICT (\d+)", d) or re.fullmatch(r"(\d+)(?:ST|ND|RD|TH) DISTRICT", d)
    if m:
        return str(int(m.group(1)))
    m = re.fullmatch(r"(\d+)(?:ST|ND|RD|TH) DISTRICT AT-LARGE", d)
    return f"{ordinal(m.group(1))} District At-Large" if m else office_words(d)


def classify(heading):
    """What a heading is: {"what": "state" | "cj" | "acj" | "county" | "city" | "school" | "unknown", ...}."""
    h, out = heading, dict(special=0, ends=None, term=None)
    m = re.search(r"\s*\bUNEXPIRED TERM(?: ENDING ([A-Z]+ \d{4}))?", h)
    if m:
        out.update(special=1, ends=m.group(1))
        h = h[:m.start()] + h[m.end():]
    m = re.search(r"\s*\b(TWO|FOUR|SIX|\d+)[- ]YEAR TERM\b", h)
    if m:
        out["term"] = m.group(1).lower()
        h = h[:m.start()] + h[m.end():]
    h = re.sub(r"\s+", " ", h).strip()
    if STATE_LEVEL.match(h):
        return dict(out, what="state")
    m = re.fullmatch(r"(ASSOCIATE )?CIRCUIT JUDGE(?: -)?(?: CIRCUIT (\d+))?(?: -)?(?: DIVISION ([0-9IVX]+))?", h)
    if m:
        return dict(out, what="acj" if m.group(1) else "cj", circuit=int(m.group(2)) if m.group(2) else None, division=m.group(3))
    for pattern, kind, part in COUNTY_OFFICES:
        m = re.fullmatch(pattern, h)
        if m:
            g = m.groupdict()
            base = h[:m.start("d")].rstrip(" -") if g.get("d") else (h[:m.start("x")] if g.get("x") else h)
            return dict(out, what="county", kind=kind, part=part, office=re.sub(r"Pres+iding", "Presiding", office_words(base)),
                        district=district_words(g["d"]) if g.get("d") else None)
    m = re.fullmatch(r"(MAYOR|COUNCIL ?MEMBER|COUNCILMAN|COUNCILWOMAN|COUNCILPERSON|ALDERMAN|ALDERWOMAN|ALDERPERSON)(?: -)?(?: (?P<d>.+))?", h)
    if m:
        return dict(out, what="city", kind="mayor" if m.group(1) == "MAYOR" else "council", part="mayor" if m.group(1) == "MAYOR" else "council",
                    office=office_words(m.group(1)), district=office_words(m.group("d")) if m.group("d") else None)
    if re.fullmatch(r"MEMBER OF THE BOARD OF EDUCATION|BOARD OF EDUCATION MEMBER|SCHOOL BOARD (?:MEMBER|DIRECTOR)", h):
        return dict(out, what="school", kind="school_board", part="school-board", office=office_words(h), district=None)
    return dict(out, what="unknown")


# ---------- one document ----------

def extract_of(data, doc, page=False):
    """What is kept of a document: the contests between people that are not state or federal ones (heading, the
    place line above it if any, the vote-for number, names and parties), the retention questions it prints, and
    counts of the rest. Raises LayoutError when a check fails."""
    spec = doc["spec"]
    if page:
        lines, across = page_lines(data)
    else:
        if not data.startswith(b"%PDF"):
            raise LayoutError("the address did not return a PDF")
        lines, across = lines_of(data, spec)
    contests = contests_of(lines, spec)
    read, printed = sum(1 for c in contests for _n, p in c["cands"] if p), party_labels(across, spec)
    if read != printed:
        raise LayoutError(f"{printed} party labels are printed and {read} names with a party were read into contests")
    strip_for = spec.get("title", "for") in ("for", "forline")
    kept, counts, prev = {}, Counter(), None
    for c in contests:
        heading = heading_of(c["title"], strip_for, prev)
        prev = base_of(heading) or prev
        what = classify(heading)["what"]
        cands = []
        for name, party in c["cands"]:
            if NOBODY.fullmatch(name):
                counts["no candidate filed"] += 1
            elif contact_like(name, True):
                counts["cells set aside"] += 1          # something that is not a name sat where a name belongs: never kept
            else:
                cands.append([name, party])
        if what == "state":
            counts["state and federal contests"] += 1
            counts["state and federal names"] += len(cands)
            continue
        if cands and not heading:
            raise LayoutError(f"page {c['page']}: names under a \"Vote for\" line with no heading above it")
        if {bool(p) for _n, p in cands} == {True, False}:
            raise LayoutError(f"page {c['page']}: names with and without a party in one contest")
        if len({fold(n) for n, _p in cands}) != len(cands):
            raise LayoutError(f"page {c['page']}: one name twice in one contest")
        place = next((t for t in reversed(c["context"]) if PLACE_LINE.match(t) and not contact_like(t, True)), "")
        if contact_like(heading, True):
            counts["cells set aside"] += 1
            continue
        key = f"{heading}|{place}"
        row = {"heading": heading, "place": place, "n": c["n"], "cands": cands, "page": c["page"]}
        if key in kept:                                 # one contest printed on several ballot types is one contest
            if kept[key]["cands"] != cands or kept[key]["n"] != c["n"]:
                raise LayoutError(f"page {c['page']}: one contest printed two ways in one document")
            counts["repeats on other ballot types"] += 1
        else:
            kept[key] = row
    return {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data), "contests": list(kept.values()), "counts": dict(counts),
            "retention": retention_questions(lines), "party_labels": printed}


def read_document(doc, local_dir, say, max_age_days=7):
    """A document's extract: the one kept in local_dir when it is fresh, else read again from its address (in memory;
    only the extract is written). If the address does not answer and an extract is kept, the extract is used."""
    path = os.path.join(local_dir, doc["id"] + ".json")
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < max_age_days * 86400:
        ex = json.load(open(path, encoding="utf-8"))
        if ex.get("url") == doc["url"]:
            return ex
    try:
        data = net.get(doc["url"])
        time.sleep(1.0)
        if not data.startswith(b"%PDF"):               # an error page served in the document's place
            raise ValueError("not a PDF")
    except Exception as e:  # noqa: BLE001
        how = "did not return a PDF" if isinstance(e, ValueError) else f"did not answer ({type(e).__name__})"
        if os.path.exists(path):
            ex = json.load(open(path, encoding="utf-8"))
            if ex.get("url") == doc["url"]:
                say(f"    Missouri (local): {doc['id']}: its address {how}; using the extract of {ex['fetched']}")
                return ex
        raise Unread(f"its address {how}")
    ex = extract_of(data, doc)
    del data
    ex.update(url=doc["url"], fetched=dt.date.today().isoformat())
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(ex, fh, ensure_ascii=False, indent=0)
    return ex


def saved_documents(a, local_dir, say):
    """[(doc, extract)] for the notices or sample ballots saved by hand into local_dir/<authority key>/ (a site that
    turns scripts away), and [reason] for the ones no known layout reads. A reading counts only if every check passes
    and it holds a county office this loader knows."""
    out, bad = [], []
    for path in sorted(glob.glob(os.path.join(local_dir, a["key"], "*"))):
        ext = os.path.splitext(path)[1].lower()
        if ext not in (".pdf", ".html", ".htm"):
            continue
        base = os.path.basename(path)
        data = open(path, "rb").read()
        got = None
        # the file must be this county's: its own text has to name the county ("City of St. Louis" for the city)
        words = (["City", "of"] + a["county"][:-5].split()) if a["county"].endswith(" city") else a["county"].split()
        named = re.compile(r"\s+".join(re.escape(w).replace(r"St\.", r"S(?:ain)?t\.?") for w in words), re.I)
        try:
            across = page_lines(data)[1] if ext != ".pdf" else lines_of(data, TYPED)[1]
        except Exception:  # noqa: BLE001
            across = []
        if not named.search(" ".join(across)):
            bad.append(f"A copy saved by hand is in place ({base}), but its text does not name {a['county']}, so nothing was taken from it.")
            say(f"    Missouri (local): the saved file {base} for {a['agency']} was not read (it does not name {a['county']})")
            continue
        for spec in (SAVED_PDF_SPECS if ext == ".pdf" else SAVED_PAGE_SPECS):
            doc = dict(id=f"mo-{a['key'].replace('_', '-')}-saved-{slug(os.path.splitext(base)[0])}",
                       kind="official sample ballot" if ext == ".pdf" else "official candidate list",
                       title=f"{a['agency']}: {base} (saved by hand)", url=a["page"], spec=spec, saved=base)
            try:
                ex = extract_of(data, doc, page=ext != ".pdf")
            except Exception:  # noqa: BLE001  a layout that does not fit: try the next
                continue
            known = [c for c in ex["contests"] if classify(c["heading"])["what"] in ("county", "acj") and c["cands"]]
            names = sum(len(c["cands"]) for c in ex["contests"]) + ex["counts"].get("state and federal names", 0)
            if known and names >= 6:
                ex.update(url=a["page"], fetched=mdate(path))
                got = (doc, ex)
                break
        del data
        if got:
            out.append(got)
        else:
            bad.append(f"A copy saved by hand is in place ({base}), but none of the layouts this loader has been checked against "
                       "reads it with every check passing, so nothing was taken from it.")
            say(f"    Missouri (local): the saved file {base} for {a['agency']} was not read (no known layout passes the checks)")
    return out, bad


# ---------- official lists of places ----------

def read_circuits(local_dir, cmap, say, max_age_days=30):
    """({circuit number: [county GEOIDs]}, {sha256, fetched, bytes}) from the Secretary of State's Official Manual
    2025-2026, chapter 5: under each "Circuit N" heading a line "Counties: A, B and C." (and "County: A." under each
    associate circuit judge). The chapter also holds the courts' office addresses and judges' biographies, so it is read
    in memory and only circuit numbers and county names are kept. Returns (None, reason) if it cannot be read."""
    path = os.path.join(local_dir, "sos_official_manual_judicial_circuits.json")
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < max_age_days * 86400:
        ex = json.load(open(path, encoding="utf-8"))
    else:
        try:
            data = net.get(MANUAL_URL)
            time.sleep(1.0)
            if not data.startswith(b"%PDF"):
                raise LayoutError("the address did not return a PDF")
            pdf = PDF(data)
            found, cur = collections.defaultdict(set), None
            for page, res in pdf.pages():
                for _y, rs in rows_of(page_runs_all(pdf, page, res)):
                    text = join(rs)
                    m = re.fullmatch(r"Circuit (\d{1,2})(?:\s*[—–-]\s*Divisions? .*)?", text)
                    if m:
                        cur = int(m.group(1))
                        continue
                    m = re.fullmatch(r"Count(?:y|ies): ([A-Za-z .,']+?)\.?", text)
                    if m and cur is not None:
                        found[cur].update(n.strip() for n in re.split(r",\s*|\s+and\s+", m.group(1)) if n.strip())
            ex = {"url": MANUAL_URL, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data), "fetched": dt.date.today().isoformat(),
                  "circuits": {str(c): sorted(v) for c, v in sorted(found.items())}}
            del data
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(ex, fh, ensure_ascii=False, indent=0)
        except Exception as e:  # noqa: BLE001
            if not os.path.exists(path):
                say(f"    Missouri (local courts): the Official Manual's list of circuits could not be read ({type(e).__name__}); "
                    "circuit judges are loaded without their counties")
                return None, f"it could not be read ({type(e).__name__})"
            ex = json.load(open(path, encoding="utf-8"))
    geoid_of = {full: g for g, full in cmap}
    out, used = {}, Counter()
    for c, names in ex["circuits"].items():
        ids = [geoid_of.get(f"{n} County") for n in names]
        if not all(ids):
            return None, "it names a county the Census Bureau's county file does not have"
        out[int(c)] = sorted(ids)
        used.update(ids)
    left = sorted(set(geoid_of.values()) - set(used))
    if any(v > 1 for v in used.values()) or len(used) != 114 or set(out) != set(range(1, 47)) - {22} or left != ["29510"]:
        return None, "its circuits do not add up to Missouri's 114 counties, each in one circuit, with the City of St. Louis left for Circuit 22"
    out[22] = ["29510"]            # the City of St. Louis: the one county-equivalent the other 45 circuits leave out
    return out, ex


def read_places(local_dir, cmap, say):
    """({squashed bare name: [(place code, name, [county GEOIDs])]}, sha256, day fetched, rows) for Missouri's
    incorporated cities, towns and villages, from the Census Bureau's 2020 place codes file (names, codes and counties
    only; kept whole in local_dir and asked for once)."""
    path = os.path.join(local_dir, "st29_mo_place2020.txt")
    net.download(PLACE_URL, path, 3650, say=say)
    geoid_of = {full: g for g, full in cmap}
    out, n = collections.defaultdict(list), 0
    with open(path, encoding="utf-8", errors="replace") as fh:
        if fh.readline().rstrip("\r\n").split("|") != PLACE_HEAD:
            raise LayoutError("st29_mo_place2020.txt: the header is not the one this loader was checked against")
        for k, line in enumerate(fh, start=2):
            f = line.rstrip("\r\n").split("|")
            if not line.strip():
                continue
            if len(f) != len(PLACE_HEAD) or f[1] != FIPS or not re.fullmatch(r"\d{5}", f[2]):
                raise LayoutError(f"st29_mo_place2020.txt: line {k} does not fit the header")
            n += 1
            if f[5] != "INCORPORATED PLACE":
                continue
            cids = [geoid_of.get(c) for c in f[8].split("~~~")]
            if not all(cids):
                raise LayoutError(f"st29_mo_place2020.txt: line {k} names a county the county file does not have")
            out[squash(re.sub(r"\s+(?:city|town|village)$", "", f[4]))].append((f[2], f[4], sorted(cids)))
    return out, sha_of(path), mdate(path), n


# ---------- the certification's local judges ----------

def read_local_courts(data):
    """[(section, "CJ" | "ACJ", circuit, division or None, name)] for the circuit and associate circuit judge lines of the
    certification: under a party's heading the candidates in a contested circuit, under JUDICIAL the judges standing
    for retention. Only lines inside a section and under one of those two headings are looked at."""
    pdf = PDF(data)
    out, section, key = [], None, None
    for n, (page, res) in enumerate(pdf.pages(), start=1):
        for _y, runs in pdf_rows(pdf, page, res):
            text = join(runs)
            if not text:
                continue
            m = re.fullmatch(r"([A-Z ]+) CANDIDATES", text)
            if m:
                section, key = m.group(1).strip(), None
                continue
            if text in END or text == "Certificate of Judicial Candidates":
                section = key = None
                continue
            if section is None:
                continue
            if text.startswith("For "):
                key = {"For Circuit Judge": "CJ", "For Associate Circuit Judge": "ACJ"}.get(text)
                continue
            if key is None or re.fullmatch(r"[A-Z ]+ PARTY EMBLEM", text) or re.fullmatch(r"\d{1,3}", text) or text.startswith("Article V, Section 25"):
                continue
            m = re.fullmatch(r"Circuit (\d+)(?:,? Division (\d+))?, (.+)", text)
            if not m:
                raise LayoutError(f"a line under \"{'For Circuit Judge' if key == 'CJ' else 'For Associate Circuit Judge'}\" on page {n} "
                                  "is not \"Circuit N, Division M, Name\"")
            out.append((section, key, int(m.group(1)), int(m.group(2)) if m.group(2) else None, m.group(3).strip()))
    return out


# ---------- the local rows ----------

def month_day(iso):
    y, m, d = (int(x) for x in iso.split("-"))
    return f"{fed.MONTHS.split('|')[m - 1]} {d}, {y}"


def build_local(local_dir, cmap, courts, published, say, max_age_days=7):
    """The local part's rows: {"races", "cands", "places", "sources", "gaps", "notes"} ready for the database, and
    "court_lines" (the certification's local judge lines placed) for the certification's own source row."""
    os.makedirs(local_dir, exist_ok=True)
    name_of = dict(cmap)                                   # GEOID -> "Adair County"
    geoid_of = {full: g for g, full in cmap}
    races, gaps, sources, places = {}, [], [], {}
    report = Counter()

    def race(rid, level, kind, office, jur, jid, cids, district, seat, special, partisan, holder=None, notes=()):
        return dict(race_id=rid, level=level, office_kind=kind, office=office, jurisdiction=jur, jurisdiction_id=jid, county_ids=cids,
                    district=district, seat=seat, special=special, partisan=partisan, holder=holder, notes=list(notes), cands=[], docs=[])

    def gap(scope, pid, place, what, reason, url):
        for text in (place, what, reason):
            if contact_like(text or "", False):
                raise SystemExit("Missouri (local): a gap's own words look like contact details; nothing was changed")
        if not any(g[1] == scope and g[2] == pid and g[4] == what for g in gaps):
            gaps.append((STATE, scope, pid, place, what, reason, url))

    # ---- which counties each circuit covers
    circuits, manual = read_circuits(local_dir, cmap, say)
    circuit_of = {g: c for c, ids in (circuits or {}).items() for g in ids}
    if circuits:
        sources.append((SRC_MANUAL, STATE, "official directory", "Missouri Secretary of State",
                        "Official Manual, State of Missouri, 2025-2026, chapter 5: Judicial Branch", MANUAL_URL, "", manual["fetched"],
                        manual["sha256"], 46,
                        "Read in memory for one thing: which counties each of the 46 judicial circuits covers (the line of counties under "
                        "each circuit). Circuit 22 has no such line; it is the City of St. Louis, the one county-equivalent the other 45 "
                        "circuits leave out. The chapter's office addresses, telephone numbers and biographies are never read into "
                        "anything kept."))
    else:
        gap("state", STATE, NAME, "which counties each judicial circuit covers",
            "The Secretary of State's Official Manual lists the counties of each judicial circuit, and " + manual +
            ", so circuit judges are shown without their counties and do not appear on the county pages.", MANUAL_URL)

    # ---- the certification's circuit and associate circuit judges
    cert_cj, cert_ret, court_lines = {}, [], 0
    if courts is None:
        gap("state", STATE, NAME, "circuit and associate circuit judges",
            "The Secretary of State's certification lists the circuit judges elected by party and the judges standing for retention; "
            "its lines for them could not be read this time, so none is loaded.", fed.GENERAL_URL)
    else:
        order = Counter()
        for section, key, c, d, name in courts:
            title = "Associate Circuit Judge" if key == "ACJ" else "Circuit Judge"
            jur, jid, cids = f"{ordinal(c)} Judicial Circuit", f"MO-JC{c}", (circuits or {}).get(c)
            seat = f"Division {d}" if d else None
            tail = f"-{c}" + (f"-{d}" if d else "")
            if section == "JUDICIAL":
                rid = f"2026-{STATE}-{key}RET{tail}"
                if rid in races:
                    raise SystemExit(f"Missouri (local courts): two judges for one retention question {rid}")
                races[rid] = race(rid, "court", "circuit_court_retention", f"{title} (retention vote)", jur, jid, cids, f"Circuit {c}", seat,
                                  0, 0, holder=name, notes=[RETENTION_NOTE])
                races[rid]["cands"].append(dict(name=name, party=NONPARTISAN, order=1, inc=1, caps=False, src=SRC_GENERAL, note=SITTING_NOTE))
                cert_ret.append((c, 1 if key == "ACJ" else 0, name, rid))
            else:
                rid = f"2026-{STATE}-{key}{tail}"
                if rid not in races:
                    races[rid] = race(rid, "court", "circuit_court", title, jur, jid, cids, f"Circuit {c}", seat, 0, 1)
                    cert_cj[(c, str(d) if d else None)] = rid
                order[rid] += 1
                races[rid]["cands"].append(dict(name=name, party=fed.PARTY.get(section, section.title()), order=order[rid], inc=0, caps=False,
                                                src=SRC_GENERAL, note=None))
            court_lines += 1
        twice = [rid for rid, r in races.items()
                 if any(k > 1 for p, k in Counter(x["party"] for x in r["cands"]).items() if p != "Independent")]
        if twice:
            raise SystemExit(f"Missouri (local courts): more than one candidate of one party for one seat: {sorted(twice)}")
    report["court races"], report["court names"] = len(races), sum(len(r["cands"]) for r in races.values())

    # ---- each election authority's own list
    place_index = None
    loaded, on_lists = collections.defaultdict(list), []
    cj_seen, ret_seen, doc_rows = [], [], Counter()

    def put(rid, fields, shown, caps, doc_id):
        """A contest from one list. The same contest on a second list is the same race: the lists must agree."""
        r = races.get(rid)
        doc_rows[doc_id] += len(shown)
        if r is None:
            r = races[rid] = fields
            r["cands"] = [dict(name=n, party=p, order=i, inc=0, caps=caps, src=doc_id, note=None) for i, (n, p) in enumerate(shown, 1)]
            r["docs"] = [doc_id]
            return
        old, new = [(fold(x["name"]), x["party"]) for x in r["cands"]], [(fold(n), p) for n, p in shown]
        r["docs"].append(doc_id)
        if r.get("conflict") or sorted(old, key=str) != sorted(new, key=str):
            r["conflict"] = True
            return
        report["contests on two lists"] += 1
        if old != new:
            for x in r["cands"]:
                x["order"] = None
        if not caps:                                   # the other list prints the same names in ordinary capitals: use them
            by = {fold(n): n for n, _p in shown}
            for x in r["cands"]:
                if x["caps"]:
                    x["name"], x["caps"] = by[fold(x["name"])], False

    for a in AUTHORITIES:
        geoid = geoid_of.get(a["county"])
        if not geoid:
            raise SystemExit(f"Missouri (local): the county file has no {a['county']}")
        county = name_of[geoid]
        got, why = [], []
        for doc in a["docs"]:
            try:
                got.append((doc, read_document(doc, local_dir, say, max_age_days)))
            except (LayoutError, Unread) as e:      # the log names the check; the reader is told only that it could not be read
                why.append("its address did not answer" if isinstance(e, Unread) else "its layout did not pass this site's reading checks")
                say(f"    CHECK Missouri (local): {a['agency']}: \"{doc['title']}\" was not read: {e}")
        more, bad = saved_documents(a, local_dir, say)
        got += more
        if not got:
            reason = a.get("why") or (f"The list the {a['agency']} publishes for November 3 could not be read this time (" +
                                      "; ".join(sorted(set(why))) + "), so nothing from it is loaded.")
            gap("county", geoid, county, GAP_WHAT if not a.get("area") else f"contests on the list for {a['area']}",
                " ".join([reason] + bad), a["page"])
            continue
        for doc, ex in got:
            unread, kept_here = 0, 0
            for c in ex["contests"]:
                info = classify(c["heading"])
                what, names = info["what"], c["cands"]
                caps = bool(names) and all(n == n.upper() for n, _p in names)
                shown = [(ordinary(n) if caps else n, p) for n, p in names]
                if what == "unknown":
                    if names:
                        gap("county", geoid, county, f"the contest headed \"{office_words(c['heading'])}\"",
                            f"The {a['agency']}'s list prints a contest headed \"{office_words(c['heading'])}\" with {len(names)} "
                            f"{'name' if len(names) == 1 else 'names'}; this site does not know that office yet, so it is not loaded.", doc["url"])
                        report["contests not known"] += 1
                    else:
                        unread += 1
                    continue
                if what == "cj":
                    cj_seen.append((info["circuit"] or circuit_of.get(geoid), info["division"], shown, a, doc))
                    continue
                notes = []
                if info["special"]:
                    notes.append("An election for the rest of an unexpired term" + (f", ending {info['ends'].title()}" if info["ends"] else "") + ".")
                if c["n"] and c["n"] > 1:
                    notes.append(f"Voters choose {c['n']}.")
                if info["term"] and info["term"] not in ("four", "4"):
                    notes.append(f"The list prints this contest as a {info['term']}-year term.")
                if not names:
                    notes.append("No candidate is on the list for this office.")
                partisan = 1 if any(p for _n, p in names) or (not names and what in ("county", "acj")) else 0
                sfx = "-S" if info["special"] else ""
                if what == "acj":
                    circuit = info["circuit"] or circuit_of.get(geoid)
                    if info["circuit"] and circuit_of.get(geoid) and info["circuit"] != circuit_of[geoid]:
                        gap("county", geoid, county, f"the associate circuit judge contest for Division {info['division'] or '(none given)'}",
                            f"The list prints an associate circuit judge contest for Circuit {info['circuit']}, and the Official Manual puts "
                            f"{county} in Circuit {circuit_of[geoid]}; it is not loaded.", doc["url"])
                        continue
                    seat = f"Division {info['division']}" if info["division"] else None
                    rid = f"2026-{STATE}-{geoid}-associate-circuit-judge" + (f"-division-{slug(info['division'])}" if info["division"] else "") + sfx
                    fields = race(rid, "court", "circuit_court", "Associate Circuit Judge", county, geoid, [geoid],
                                  f"Circuit {circuit}" if circuit else None, seat, info["special"], partisan, notes=notes)
                elif what == "county":
                    rid = f"2026-{STATE}-{geoid}-{info['part']}" + (f"-{slug(info['district'])}" if info["district"] else "") + sfx
                    fields = race(rid, "county", info["kind"], info["office"], county, geoid, [geoid], info["district"], None, info["special"],
                                  partisan, notes=notes)
                elif what == "city":
                    m = re.fullmatch(r"(?i)(CITY|TOWN|VILLAGE) OF (.+)", c["place"])
                    if not m:
                        gap("county", geoid, county, f"a city contest ({info['office']}{', ' + info['district'] if info['district'] else ''})",
                            f"The {a['agency']}'s list prints a contest for {info['office']} without naming the city above it, so it is "
                            "not loaded.", doc["url"])
                        continue
                    if place_index is None:
                        try:
                            place_index = read_places(local_dir, cmap, say)
                        except Exception as e:  # noqa: BLE001  without the list a city is named as the county's list names it
                            place_index = ({}, "", "", 0)
                            say(f"    Missouri (local): the Census Bureau's place codes could not be read ({type(e).__name__}); "
                                "cities are filed under the names the lists give")
                    fit = [p for p in place_index[0].get(squash(m.group(2)), []) if geoid in p[2]]
                    kind_fit = [p for p in fit if p[1].lower().endswith(" " + m.group(1).lower())]
                    fit = kind_fit if len(kind_fit) == 1 else fit
                    if len(fit) == 1:
                        key, jur, cids, psrc = fit[0][0], fit[0][1], fit[0][2], SRC_PLACES
                    else:                              # no single entry on the Census Bureau's list: named as the list names it
                        jur = f"{office_words(m.group(2))} {m.group(1).lower()}"
                        key, cids, psrc = f"{geoid[2:]}-{slug(jur)}", [geoid], doc["id"]
                    jid = f"{STATE}-M-{key}"
                    places[jid] = ("mcd", jid, jur, json.dumps(cids), psrc)
                    rid = f"2026-{STATE}-M-{key}-{info['part']}" + (f"-{slug(info['district'])}" if info["district"] else "") + sfx
                    fields = race(rid, "city", info["kind"], info["office"], jur, jid, cids, info["district"], None, info["special"], partisan,
                                  notes=notes)
                else:                                  # a school board
                    jur = a.get("school") or (office_words(c["place"]) if c["place"] else None)
                    if not jur:
                        gap("county", geoid, county, "a school board contest",
                            f"The {a['agency']}'s list prints a school board contest without naming the district above it, so it is "
                            "not loaded.", doc["url"])
                        continue
                    key = f"{geoid[2:]}-{slug(jur)}"
                    jid = f"{STATE}-S-{key}"
                    places[jid] = ("school", jid, jur, json.dumps([geoid]), doc["id"])
                    rid = f"2026-{STATE}-S-{key}-{info['part']}" + sfx
                    fields = race(rid, "school", info["kind"], info["office"], jur, jid, [geoid], info["district"], None, info["special"],
                                  partisan, notes=notes)
                put(rid, fields, shown, caps, doc["id"])
                kept_here += 1
            cc = ex.get("counts", {})
            for c_, d_, name_ in ex.get("retention", []):
                ret_seen.append((c_, d_, name_, a, doc))
            loaded[geoid].append(a)
            on_lists.append((a, doc, ex, kept_here, unread))
            report["documents read"] += 1
            report["state and federal contests left to the certification"] += cc.get("state and federal contests", 0)
            report["no candidate filed lines"] += cc.get("no candidate filed", 0)
            report["cells set aside"] += cc.get("cells set aside", 0)
        if why:                                         # some of this authority's documents were read, some were not
            gap("county", geoid, county, "contests printed only on a ballot type that could not be read",
                f"The {a['agency']} publishes its November 3 list in {len(a['docs'])} documents and {len(why)} could not be read this time, "
                "so a contest printed only there is missing.", a["page"])
        if bad:
            say(f"    Missouri (local): {a['agency']}: " + " ".join(bad))

    # ---- two lists that disagree about one contest: no name is shown
    agency_of = {doc["id"]: a["agency"] for a, doc, _ex, _k, _u in on_lists}
    for rid, r in races.items():
        if r.get("conflict"):
            who = sorted({agency_of.get(d, d) for d in r["docs"]})
            reason = (f"The lists of {' and '.join(who)} both print this contest and do not name the same candidates, so no name is "
                      "shown here.")
            r["cands"], r["notes"] = [], [reason]
            gap("race", rid, f"{r['office']}, {r['jurisdiction']}", "the candidates' names", reason, None)
            report["contests two lists disagree on"] += 1

    # ---- the circuit judge contests the counties print, against the certification
    confirmed = 0
    for circuit, division, shown, a, doc in cj_seen:
        geoid = geoid_of[a["county"]]
        rid = cert_cj.get((circuit, division))
        words = "Circuit Judge" + (f", Circuit {circuit}" if circuit else "") + (f", Division {division}" if division else "")
        if rid is None:
            gap("county", geoid, name_of[geoid], f"the contest for {words}",
                f"The {a['agency']}'s list prints a contest for {words}, which the Secretary of State's certification does not carry; "
                "circuit judges are loaded from the certification, so it is not shown.", doc["url"])
            report["circuit contests only on a county list"] += 1
            continue
        r = races[rid]
        cert = r.get("certified") or [(x["name"], x["party"]) for x in r["cands"]]
        r["certified"] = cert
        same = len(cert) == len(shown) and all(any(p == p2 and same_person(n, n2) for n2, p2 in shown) for n, p in cert)
        if same:
            confirmed += 1
            continue
        say_names = lambda rows: " and ".join(f"{n} ({p})" for n, p in rows) or "no one"      # noqa: E731
        reason = (f"The Secretary of State's certification of {month_day(published)} names {say_names(cert)} for this seat; "
                  f"{name_of[geoid]}'s list for November 3 prints {say_names(shown)}. The two official lists disagree and neither says why, "
                  "so no name is shown here.")
        r["cands"], r["notes"] = [], [reason]
        gap("race", rid, f"{words} ({r['jurisdiction']})", "which candidate is on the ballot", reason, doc["url"])
        report["circuit contests the lists disagree on"] += 1
    report["circuit contests a county list confirms"] = confirmed

    # ---- the retention questions the counties print, against the certification (a second reading; nothing is stored from it)
    found_ret, extra_ret = set(), []
    for c_, assoc, name_, a, doc in ret_seen:
        hit = [rid for cc_, aa, nn, rid in cert_ret if cc_ == c_ and aa == assoc and same_person(nn, name_)]
        if hit:
            found_ret.add(hit[0])
        else:
            extra_ret.append(f"{a['agency']}: Circuit {c_}")
    read_circuits_ = {c_ for c_, _a, _n, _x, _d in ret_seen}
    missing_ret = [rid for c_, _a, _n, rid in cert_ret if c_ in read_circuits_ and rid not in found_ret]
    report["retention judges also on a county list"] = len(found_ret)
    if extra_ret or missing_ret:
        say(f"    CHECK Missouri (local courts): retention questions do not match the certification: on a county list only: "
            f"{sorted(set(extra_ret)) or 'none'}; on the certification but not on the list of a county read: {missing_ret or 'none'}")

    # ---- counties: every one, and a gap for each whose list is not loaded
    for geoid, full in cmap:
        places[geoid] = ("county", geoid, full, json.dumps([geoid]), SRC_COUNTIES)
        if geoid not in loaded and not any(g[1] == "county" and g[2] == geoid for g in gaps):
            gap("county", geoid, full, GAP_WHAT,
                "Not loaded yet. Missouri has no statewide list of county candidates: each county's election authority (the county "
                "clerk in most counties, a board of election commissioners in a few) publishes its own notice of election and sample "
                "ballot for November 3, and this county's has not been read into this site.", LEA_URL)

    # ---- sources: one row a document
    for a, doc, ex, kept_here, unread in on_lists:
        cc = ex.get("counts", {})
        bits = [f"Read: the headings of contests between people, the vote-for number, and names and parties in the order printed; "
                f"{kept_here} local {'contest' if kept_here == 1 else 'contests'} kept. The document is a ballot and has no contact columns."]
        if a.get("area"):
            bits.append(f"It covers {a['area']}.")
        if doc.get("saved"):
            bits.append(f"Saved by hand from the authority's site, which turns scripts away ({doc['saved']}).")
        if cc.get("state and federal contests"):
            bits.append(f"Its {cc['state and federal contests']} state and federal contests ({cc.get('state and federal names', 0)} names) are "
                        "left to the Secretary of State's certification, and its ballot questions are not loaded.")
        n_cj = sum(1 for c in ex["contests"] if classify(c["heading"])["what"] == "cj")
        if n_cj or ex.get("retention"):
            bits.append(f"Its {n_cj} circuit judge {'contest' if n_cj == 1 else 'contests'} and {len(ex.get('retention', []))} retention "
                        "questions on circuit and associate circuit judges are only compared with the certification, which is where those "
                        "rows come from.")
        if cc.get("repeats on other ballot types"):
            bits.append(f"{cc['repeats on other ballot types']} contests printed again on other ballot types were counted once.")
        if cc.get("no candidate filed"):
            bits.append(f"{cc['no candidate filed']} lines saying no candidate filed for a party are not candidates.")
        if unread:
            bits.append(f"{unread} {'heading' if unread == 1 else 'headings'} with no name under it could not be read (two lines of type "
                        "printed over each other).")
        if cc.get("cells set aside"):
            bits.append(f"{cc['cells set aside']} cells that did not hold a name were set aside.")
        bits.append(f"Checked by a second count: the {ex.get('party_labels', 0)} party labels printed in the document equal the names with a "
                    "party read into contests. Ballot order is the order printed.")
        sources.append((doc["id"], STATE, doc["kind"], a["agency"], doc["title"], doc["url"], "", ex["fetched"], ex["sha256"],
                        doc_rows.get(doc["id"], 0), " ".join(bits)))
    if place_index is not None and place_index[3]:
        sources.append((SRC_PLACES, STATE, "official place codes", "U.S. Census Bureau", "2020 place codes, Missouri (st29_mo_place2020.txt)",
                        PLACE_URL, "2020", place_index[2], place_index[1], place_index[3],
                        "Names and codes of incorporated cities, towns and villages and the counties each lies in; a city on a county's "
                        "list is filed under its code when exactly one place of that name lies in that county."))

    # ---- rows
    race_rows, cand_rows = [], []
    for rid, r in sorted(races.items()):
        if not re.fullmatch(rf"2026-{STATE}-[A-Za-z0-9-]+", rid):
            raise SystemExit(f"Missouri (local): a race id that is not letters, digits and hyphens: {rid}")
        for cell in (r["office"], r["jurisdiction"], r["district"], r["seat"]):
            if cell and contact_like(cell, True):
                raise SystemExit(f"Missouri (local): {rid}: a cell that looks like contact details; nothing was changed")
        note = " ".join(r["notes"]) or None
        race_rows.append((rid, STATE, r["level"], r["office_kind"], r["office"], r["jurisdiction"], r["jurisdiction_id"],
                          json.dumps(r["county_ids"]) if r["county_ids"] else None, r["district"], r["seat"], r["special"], r["partisan"],
                          None, r["holder"], None, GENERAL, note))
        if len({fold(x["name"]) for x in r["cands"]}) != len(r["cands"]):
            raise SystemExit(f"Missouri (local): one name twice in {rid}")
        for x in r["cands"]:
            party = x["party"] or NONPARTISAN
            if r["partisan"] and party == NONPARTISAN:
                raise SystemExit(f"Missouri (local): a name without a party in a contest with parties: {rid}")
            if not r["partisan"]:
                party = NONPARTISAN
            cand_rows.append((rid, "general", GENERAL, x["name"], party, NONPARTISAN_CODE if party == NONPARTISAN else party_code(party),
                              x["order"], x["inc"], 0, None, None, None, None, x["src"], CAPS_NOTE if x["caps"] else x["note"]))

    # ---- the two notes
    by_level = Counter(r["level"] for r in races.values())
    n_ret = sum(1 for r in races.values() if r["office_kind"] == "circuit_court_retention")
    n_assoc = sum(1 for r in races.values() if r["level"] == "court" and r["jurisdiction_id"] in name_of)      # from the counties' lists
    n_circuit = by_level["court"] - n_ret - n_assoc
    county_names = sum(len(r["cands"]) for r in races.values() if r["level"] != "court" or r["jurisdiction_id"] in name_of)
    read_names = sorted({a["agency"] for a, _d, _e, _k, _u in on_lists})
    ret_circuits = sorted({c for c, _a, _n, _r in cert_ret})
    plural = lambda n, word: f"{n} {word}" + ("" if n == 1 else "s")      # noqa: E731
    few = sorted({f"{r['jurisdiction']} ({r['office'].lower()}{', for the rest of a term' if r['special'] else ''})"
                  for r in races.values() if r["level"] in ("city", "school")})
    calendar = (
        "On November 3, 2026 Missouri's counties elect county officers by party: on the lists read so far, the presiding commissioner, "
        "county clerk, circuit clerk, recorder of deeds, prosecuting attorney, collector and auditor, in charter counties the county "
        "executive and the council or legislature, and in a few counties a sheriff, assessor, treasurer or district commissioner. "
        "Associate circuit judges, and the circuit judges whose terms end, are elected by party too, except in the "
        f"{len(ret_circuits)} circuits where voters instead answer Yes or No on keeping each judge. "
        "Cities, school districts and special districts elect their officers on the general municipal election day in April (April 7 "
        "this year), so few of their offices are on this ballot" + (": on the lists read so far, " + " and ".join(few) if few else "") + ".")
    coverage = (
        f"Loaded: the circuit and associate circuit judges on the Secretary of State's certification ({plural(n_circuit, 'contest')} "
        f"between candidates and {plural(n_ret, 'retention vote')}), and every contest between people on the November 3 notice, sample "
        f"ballot or ballot proof of {len(read_names)} election authorities ({', '.join(read_names)}): {plural(by_level['county'], 'county contest')}, "
        f"{plural(n_assoc, 'associate circuit judge contest')} elected by party, {plural(by_level['city'], 'city contest')} and "
        f"{plural(by_level['school'], 'school board contest')}, with {county_names} names. "
        f"Left out: the {sum(1 for g in gaps if g[1] == 'county' and g[4] == GAP_WHAT)} counties whose lists are not loaded yet (each is "
        "listed with the reason); ballot questions, constitutional amendments and propositions; a party's line saying no candidate "
        "filed; the state and federal contests on the county lists, which come from the certification; and local primaries. The lists "
        "carry no write-in candidates and do not say who withdrew.")
    notes = [(STATE, "local_calendar", calendar,
              "RSMo 115.121 (the general election day and the April election day for political subdivisions and special districts); the "
              "election authorities' notices and sample ballots for November 3, 2026; the Secretary of State's certification of candidates",
              CALENDAR_URL),
             (STATE, "local_coverage", coverage,
              "The Secretary of State's Certification of Candidates for November 3, 2026, and the election authorities' own notices of "
              "election and sample ballots", LEA_URL)]
    for _s, _k, text, source, _u in notes:
        if contact_like(text, False) or contact_like(source, False):
            raise SystemExit("Missouri (local): a note's own words look like contact details; nothing was changed")

    # ---- the report: counts only
    kinds = Counter(r["office_kind"] for r in races.values() if r["level"] != "court")
    say(f"    Missouri (local): {len(race_rows)} local races and {len(cand_rows)} candidates: court {by_level['court']} ({n_ret} retention votes, "
        f"{n_circuit} circuit judge and {n_assoc} associate circuit judge contests), county {by_level['county']}, city {by_level['city']}, "
        f"school {by_level['school']}; "
        f"{len(loaded)} of {len(cmap)} counties have their own list loaded ({report['documents read']} documents of {len(read_names)} "
        f"election authorities); {sum(1 for g in gaps if g[1] == 'county')} county gaps, {sum(1 for g in gaps if g[1] == 'race')} race gaps, "
        f"{sum(1 for g in gaps if g[1] == 'state')} state gaps")
    say("    Missouri (local): county office kinds: " + ", ".join(f"{k} {v}" for k, v in kinds.most_common()))
    say(f"    Missouri (local): checks: {report['contests on two lists']} contests printed on two lists and agreeing; "
        f"{report['circuit contests a county list confirms']} of {len(cert_cj)} circuit judge contests confirmed by a county's list, "
        f"{report['circuit contests the lists disagree on']} disagreeing; {report['retention judges also on a county list']} of "
        f"{len(cert_ret)} retention judges also printed on a county list read; {report['no candidate filed lines']} \"no candidate filed\" "
        f"lines and {report['state and federal contests left to the certification']} state and federal contests left out; "
        f"{report['contests not known']} contests with an office not known; {report['cells set aside']} cells set aside")
    return {"races": race_rows, "cands": cand_rows, "places": list(places.values()), "sources": sources, "gaps": gaps, "notes": notes,
            "court_lines": court_lines}


# ---------- the load ----------

def load(db_path, say=print, extract_dir=os.path.join(CACHE, "mo"), local_dir=None):
    net.patient_lookups()
    local_dir = local_dir or LOCAL_DIR
    published, g_rows, others, g_sha, g_fetched, g_how, court_lines = get_general(extract_dir, say, local_dir=local_dir)
    prim = kept(os.path.join(extract_dir, "sl_mo_primary_list.json"), fed.PRIMARY_URL, read_primary, "primary list", say)
    remv = kept(os.path.join(extract_dir, "sl_mo_primary_removed.json"), fed.REMOVED_URL, read_removed, "removed-candidates page", say)
    seats, as_of = roster()
    cmap = counties()

    # the November certification: races and candidates, in the certification's order
    races, general, count = {}, [], Counter()
    for section, key, district, name in g_rows:
        if key in ("SC", "COA"):
            count[(key, district)] += 1
            r = race_of(key, district, count[(key, district)])
            party = NONPARTISAN
        else:
            r = race_of(key, district)
            party = fed.PARTY.get(section, section.title())
        if r["race_id"] in races and key in ("SC", "COA"):
            raise SystemExit(f"Missouri (state races): two judges for one retention question {r['race_id']}")
        races.setdefault(r["race_id"], r)
        general.append((r["race_id"], party, name))
    n_listed = len(g_rows)
    twice = [k for k, v in Counter((rid, p) for rid, p, _n in general if p not in ("Independent", NONPARTISAN)).items() if v > 1]
    if twice:
        raise SystemExit(f"Missouri (state races): more than one nominee of one party for one seat: {sorted(twice)}")
    dup = [k for k, v in Counter((rid, fold(n)) for rid, _p, n in general).items() if v > 1]
    if dup:
        raise SystemExit(f"Missouri (state races): one name twice in one race: {sorted(r for r, _ in dup)}")

    # which seats are on the ballot
    sen = sorted(int(r["district"]) for r in races.values() if r["office_kind"] == "state_senate")
    hou = sorted(int(r["district"]) for r in races.values() if r["office_kind"] == "state_house")
    if hou != list(range(1, 164)):
        raise SystemExit(f"Missouri (state races): the certification has House districts {hou}, not all 163")
    checks = []
    if sen != list(range(2, 35, 2)):
        checks.append(f"Senate districts on the certification are {sen}, not the 17 even-numbered ones")
    if f"2026-{STATE}-AUD" not in races:
        checks.append("no State Auditor on the certification")

    # the August 4 primary list, by race and party
    ballots, prim_other, n_prim_state = {}, Counter(), 0
    for r in prim["rows"]:
        key, district = primary_office(r["office"])
        if key in ("federal", "local court"):
            prim_other[key] += 1
            continue
        rid = race_of(key, district)["race_id"]
        if rid not in races:
            raise SystemExit(f"Missouri (state races): {r['office']!r} was on the primary ballot but is not on the November certification")
        if r["party"] not in fed.CODE:
            raise SystemExit(f"Missouri (state races): a primary for a party the loader does not know under {r['office']!r}")
        ballots.setdefault((rid, r["party"]), []).append((r["order"], r["name"]))
        n_prim_state += 1
    for key, names in ballots.items():
        orders = [o for o, _n in names]
        if orders != list(range(1, len(orders) + 1)):
            raise SystemExit(f"Missouri (state races): the primary table for {key} is not numbered 1..{len(orders)}")
        if len({fold(n) for _o, n in names}) != len(names):
            raise SystemExit(f"Missouri (state races): one name twice on the {key} primary ballot")

    # removed before the primary: left off, and never also on the certified list
    removed_state, removed_on_list = [], []
    for r in remv["rows"]:
        try:
            key, district = primary_office(r["office"])
        except SystemExit:
            continue
        if key in ("federal", "local court"):
            continue
        removed_state.append(r)
        rid = race_of(key, district)["race_id"]
        if r["name"] and any(fold(n) == fold(r["name"]) for _o, n in ballots.get((rid, r["party"]), [])):
            removed_on_list.append(rid)
    if removed_on_list:
        checks.append(f"removed candidates still on the certified primary list: {sorted(set(removed_on_list))}")

    # today's holders and the sitting member on the ballot
    holders, notes = {}, {}
    for rid, r in races.items():
        h = None
        if r["chamber"]:
            h = seats.get((r["chamber"], r["district"]))
            if h is None:
                notes[rid] = f"The Open States roster ({as_of}) lists no sitting member for this seat."
        elif r["office_kind"] == "state_auditor":
            notes[rid] = "The Open States roster this site uses does not carry the State Auditor, so today's holder is not shown."
        else:
            notes[rid] = RETENTION_NOTE
        holders[rid] = h

    names_in = {}
    for rid, _party, name in general:
        names_in.setdefault(rid, set()).add(name)
    for (rid, _party), names in ballots.items():
        names_in[rid].update(n for _o, n in names)
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

    # rows: November
    cand, order = [], Counter()
    nominee = {(rid, party): name for rid, party, name in general}
    not_in_primary = []
    for rid, party, name in general:
        order[rid] += 1
        retention = races[rid]["level"] == "court"
        inc = retention or (rid in sitting and fold(name) == sitting[rid][0])
        note = None
        if party in fed.CODE and not any(same_person(name, n) for _o, n in ballots.get((rid, party), [])):
            note = f"Not on the August 4 {party} primary ballot; nominated afterwards (the certification does not say how)."
            not_in_primary.append(f"{rid} {party}")
        elif retention:
            note = "Standing for retention as the sitting judge."
        cand.append((rid, "general", GENERAL, name, party, NONPARTISAN_CODE if retention else party_code(party), order[rid],
                     1 if inc else 0, 0, None, None, None, sitting[rid][1] if (inc and not retention and rid in sitting) else None,
                     SRC_GENERAL, note))
    n_general_rows = len(cand)

    # rows: the August 4 party primaries with a field
    fields, unsettled = Counter(), []
    for (rid, party), names in sorted(ballots.items()):
        if len(names) < 2:
            continue
        fields[races[rid]["office_kind"] if races[rid]["level"] == "legislature" else "statewide"] += 1
        pick = nominee.get((rid, party))
        won = [n for _o, n in names if pick and same_person(pick, n)]
        settled = len(won) == 1
        note = None
        if not settled:
            unsettled.append(f"{rid} {party}")
            note = ("No candidate of this party for this seat is on the November certification; the official primary "
                    "results are not posted yet, so who won is not shown.") if not pick else (
                    "This party's November candidate was not on its primary ballot; the official primary results are not "
                    "posted yet, so who won the primary is not shown.") if not won else (
                    "More than one name on the primary ballot fits this party's November candidate; who advanced is not shown.")
        for o, name in names:
            inc = rid in sitting and fold(name) == sitting[rid][0]
            outcome = ("advanced" if name == won[0] else "lost") if settled else None
            cand.append((rid, f"primary-{fed.CODE[party]}", PRIMARY, name, party, party_code(party), o, 1 if inc else 0, 0,
                         None, None, outcome, sitting[rid][1] if inc else None, SRC_PRIMARY, note))
    n_primary_rows = len(cand) - n_general_rows
    n_primary_single = sum(1 for v in ballots.values() if len(v) == 1)
    if n_primary_rows + n_primary_single != n_prim_state:
        raise SystemExit("Missouri (state races): primary rows stored plus one-candidate primaries do not add up to the list")
    if n_general_rows != n_listed:
        raise SystemExit("Missouri (state races): November rows stored do not match the certification's state lines")
    keys = Counter((c[0], c[1], c[3]) for c in cand)
    if any(v > 1 for v in keys.values()):
        raise SystemExit("Missouri (state races): one name twice in one race and election")

    race_rows = []
    for rid, r in sorted(races.items()):
        h = holders[rid]
        hname = next((n for x, _p, n in general if x == rid), None) if r["level"] == "court" else (h["full"] if h else None)
        race_rows.append((rid, STATE, r["level"], r["office_kind"], r["office"], NAME, FIPS, None, r["district"], r["seat"], 0,
                          r["partisan"], h["id"] if h else None, hname, h["party"] if h else None, GENERAL, notes.get(rid)))
    # the local part: local judges from the same certification, and the election authorities' own lists (the rows above
    # are not touched by it; it adds its own races, candidates, places, sources, gaps and notes)
    local = build_local(local_dir, cmap, court_lines, published, say)
    if {r[0] for r in local["races"]} & set(races):
        raise SystemExit("Missouri (local): a local race id is also a state race id; nothing was changed")
    place_rows = local["places"]

    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA)
    con.executescript(EXTRA_SCHEMA)
    with con:
        con.execute("DELETE FROM sl_candidates WHERE race_id LIKE '2026-MO-%'")
        con.execute("DELETE FROM sl_races WHERE state = 'MO'")
        con.execute("DELETE FROM sl_sources WHERE state = 'MO'")
        con.execute("DELETE FROM sl_places WHERE kind = 'county' AND id GLOB '29[0-9][0-9][0-9]'")
        con.execute("DELETE FROM sl_places WHERE source_id LIKE 'mo-%'")
        con.execute("DELETE FROM sl_gaps WHERE state = 'MO'")
        con.execute("DELETE FROM sl_notes WHERE state = 'MO'")
        con.executemany("INSERT INTO sl_races VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", race_rows + local["races"])
        con.executemany("INSERT INTO sl_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", cand + local["cands"])
        con.executemany("INSERT INTO sl_places VALUES (?,?,?,?,?)", place_rows)
        con.executemany("INSERT INTO sl_gaps VALUES (?,?,?,?,?,?,?)", local["gaps"])
        con.executemany("INSERT INTO sl_notes VALUES (?,?,?,?,?)", local["notes"])
        src = [
            (SRC_GENERAL, STATE, "official candidate list", "Missouri Secretary of State",
             "Certification of Candidates and Party Emblems, General Election, Tuesday, November 3, 2026", fed.GENERAL_URL,
             published, g_fetched, g_sha, n_listed + local["court_lines"],
             f"Read from {g_how}: the State Auditor, State Senator and State Representative lines of each party section, the "
             "Supreme Court and Court of Appeals retention lines of the judicial section, and the circuit and associate circuit "
             f"judge lines ({local['court_lines']}: candidates under a party's heading, judges standing for retention under the "
             "judicial heading). Ballot order is the certification's own "
             "order (no ballot numbers are printed; parties in the order it lists them). It lists no write-in candidates. Senate "
             f"seats on it: the {len(sen)} even-numbered districts. Left to others: {others.get('federal', 0)} U.S. Representative "
             "lines (the federal pages). It carries no candidate addresses; only lines inside a party or judicial section are read."),
            (SRC_PRIMARY, STATE, "official candidate list", "Missouri Secretary of State",
             "Certified Candidate List, 2026 Primary Election (August 4, 2026)", prim["url"], "", prim["fetched"], prim["sha256"],
             n_prim_state,
             "Office, party, place in the party's table (the ballot order) and name only; the Mailing Address, Random Number and "
             "Date Filed columns are never read. A party primary is shown as a field when two or more were on its ballot. No vote "
             "counts: the Secretary's results page offers only unofficial election-night results on a host that refuses scripts, "
             "and no official results file for August 4, 2026 was posted as of 2026-09-30. Who advanced is read from the November "
             "certification." + (f" Not settled: {', '.join(unsettled)}." if unsettled else "")),
            (SRC_REMOVED, STATE, "official candidate list", "Missouri Secretary of State",
             "Withdrawn/Removed Candidates, 2026 Primary Election", remv["url"], "", remv["fetched"], remv["sha256"],
             len(removed_state),
             "Candidates for state offices taken off the primary ballot before August 4, left off these pages. Only the name and "
             "party before the bracket are kept; the mailing address in the same cell is never kept."),
            (SRC_ROSTER, STATE, "roster", "Open States people project (CC0)",
             "Missouri legislators, as loaded into state_mo.sqlite", "https://github.com/openstates/people", as_of, as_of, "",
             len(seats),
             "Today's holder of each seat. The roster does not carry the State Auditor or judges. A candidate is marked as the "
             "sitting member only when the name fits the holder of that seat and no other candidate in the race fits."),
            (SRC_COUNTIES, STATE, "boundaries", "U.S. Census Bureau",
             "Cartographic boundary file, counties, 2024, 1:500,000 (cb_2024_us_county_500k)",
             "https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_county_500k.zip", "", mdate(COUNTY_ZIP),
             sha_of(COUNTY_ZIP), len(cmap), "Missouri's 114 counties and the City of St. Louis: names and GEOIDs only."),
        ]
        con.executemany("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", src + local["sources"])
    con.close()

    # the report: counts only
    kind = lambda rid: races[rid]["office_kind"] if races[rid]["level"] == "legislature" else races[rid]["level"]
    by = Counter(kind(rid) for rid in races)
    gen_by = Counter(kind(rid) for rid, _p, _n in general)
    one = Counter(kind(rid) for rid, k in Counter(rid for rid, _p, _n in general).items() if k == 1 and races[rid]["level"] != "court")
    inc_by = Counter(kind(rid) for rid in sitting)
    say(f"    Missouri (state races): {by['state_senate']} Senate seats (even districts), {by['state_house']} House seats, "
        f"{by['statewide']} statewide office, {by['court']} judicial retention votes; {len(general)} names on the November ballot "
        f"(Senate {gen_by['state_senate']}, House {gen_by['state_house']}, statewide {gen_by['statewide']}, retention {gen_by['court']}; "
        f"one candidate only: Senate {one['state_senate']}, House {one['state_house']}); sitting member on the ballot: "
        f"Senate {inc_by['state_senate']}, House {inc_by['state_house']}; primary fields: Senate {fields['state_senate']}, "
        f"House {fields['state_house']}, statewide {fields['statewide']} ({n_primary_rows} candidates, no vote counts yet); "
        f"{n_prim_state} state candidates on the primary list, {len(removed_state)} removed before the primary left off")
    say(f"    Missouri (state races): left to others: {others.get('federal', 0)} U.S. Representative lines on the certification "
        f"(its {local['court_lines']} local judge lines are read by the local part); {prim_other.get('federal', 0)} federal and "
        f"{prim_other.get('local court', 0)} local judge rows on the primary list")
    if not_in_primary:
        say(f"    Missouri (state races): November candidates not on their party's primary ballot: {', '.join(not_in_primary)}")
    if unsettled:
        say(f"    Missouri (state races): primaries with no advancer shown: {', '.join(unsettled)}")
    if party_differs:
        say(f"    CHECK Missouri (state races): sitting member listed under another party: {party_differs}")
    for c in checks:
        say(f"    CHECK Missouri (state races): {c}")
    vac = sorted((rid for rid, h in holders.items() if h is None and races[rid]["level"] == "legislature"),
                 key=lambda x: (x[8:10], int(re.sub(r"\D", "", x[10:]))))
    if vac:
        say(f"    Missouri (state races): no sitting member in the roster for {', '.join(vac)}")
    return len(cand) + len(local["cands"])


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: python ballot/state_local_mo.py <database file>")
    load(sys.argv[1])
