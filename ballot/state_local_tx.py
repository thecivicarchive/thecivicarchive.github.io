"""
ballot/state_local_tx.py - Texas's state races on the November 3, 2026 ballot, with the March 3 party primaries and the
May 26 primary runoffs that chose the nominees, into ballot_local_2026.sqlite. The federal ballot database
(ballot_2026.sqlite) is never opened here, and U.S. Senator and U.S. Representative rows are left to the federal pages.

What is on the ballot, read from the certification itself, never assumed:
  - the Texas Senate: 16 of its 31 seats (four-year terms, staggered; in 2026 districts 1, 2, 3, 4, 5, 9, 11, 13, 18, 19,
    21, 22, 24, 26, 28 and 31);
  - the Texas House: all 150 seats (two-year terms);
  - the statewide executive offices up this year: Governor, Lieutenant Governor (elected separately), Attorney General,
    Comptroller of Public Accounts, Commissioner of the General Land Office, Commissioner of Agriculture and one
    Railroad Commissioner (the Secretary of State is appointed and is never on the ballot);
  - the State Board of Education districts up this year;
  - the courts the certification lists as state and district offices: the Supreme Court (Chief Justice and places),
    the Court of Criminal Appeals, the courts of appeals (chief justices and places), the district courts and the
    criminal district courts. Every one of these offices is partisan in Texas.
County offices, county courts, justices of the peace, district and criminal district attorneys and district clerks are
left to a later local phase; they are counted in the report.

Sources, all the Texas Secretary of State's own, the same files the federal loader (ballot/lists/tx.py) reads:

  Ballot Certification Report, 2026 November General Election (certified August 28, 2026; a PDF of 1,396 pages read
  with ballot/pdftext.py, from the federal loader's cached copy ballot_cache/tx_ballot_cert_2026.pdf). County by county,
  every office on that county's ballot and under it each candidate in ballot order with the party (REP, DEM, LIB, GRE,
  IND). It prints offices, names and parties only. An office heading this loader does not know stops it (the heading,
  an office title, is named). A race that spans several counties is listed once per county, and every county's list
  must agree, or the race's November candidates are left out and named. The counties that list a race are its
  county_ids (derived, and said so).

  Official Canvass Reports of the March 3, 2026 Republican and Democratic primaries and the May 26, 2026 runoffs, from
  the Secretary of State's election results system (goelect.txelections.civixapps.com), each marked official there;
  the four PDFs are the federal loader's cached copies in ballot_cache/tx/. Per office: each candidate's name as on the
  ballot (with "(I)", the report's incumbent mark), party, canvass votes and percent, then a Total line. Every Total
  line must equal its candidates' sum and every printed percent must match. An office heading may run onto a second
  line (PLACE 3, DISTRICT 2, - UNEXPIRED TERM) and a long name onto a second line; both are joined.
  The same system's election records (/api-ivis-system/api/s3/enr/election/<id>) carry each election's StateWide and
  Districted races; only race name, total, and each candidate's name, party and votes are kept (as JSON, in
  tx_2026_state_results_records.json), and their figures must equal the canvass report's, race by race.

  A field is a party primary with two candidates or more. A nominee needs a majority; a candidate with one advanced.
  Otherwise the two with the most votes met in the May 26 runoff: both advanced (noted), and the runoff, stored as its
  own election (runoff-REP, runoff-DEM), was won by the one with more votes. The runoff's pair must be the primary's top
  two. Where no one had a majority and the runoff canvass has no contest for the nomination, the leader advanced only
  if the November certification names the leader and not the runner-up, and both rows say so. Each nominee must be the
  party's candidate on the November certification; where not, the row says so plainly.

  Who holds each seat: the Open States roster in state_tx.sqlite (legislators with is_current = 1 by chamber and
  district; the officials table for Governor, Lieutenant Governor and Attorney General). Only id, name, party, chamber,
  district and office are selected. A candidate is the sitting member only when the name fits the roster's holder of
  that same seat and every fitting name in the race is the same person. For the offices the roster does not carry
  (the other statewide offices, the State Board of Education and the courts) the canvass's own incumbent mark "(I)" is
  used for the incumbent flag, with no member id, and the race says so. For seats the roster does carry, the canvass
  marks are compared with the roster and every difference is printed.

  County codes: the Census Bureau's 2024 county file (states_cache/census/cb_2024_us_county_500k.zip), names and GEOIDs.

Privacy. None of these files carries an address, telephone, e-mail, website or treasurer (checked: every line of the
certification is a header, a county, an office or "NAME PARTY"). Only office, district, name, party, ballot order,
votes and the incumbent mark are read; nothing is printed but counts, race keys and office titles; and before anything
is written every stored name and note is checked for anything that looks like a contact detail.

Names are printed in capitals and shown in ordinary capitals (a sitting member as the roster spells the name).

    python -m ballot.state_local_tx <path to a test database> [--keep <folder for the kept-cells JSON>]
"""

import base64
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
from ballot.lists import tx as fed                                          # noqa: E402
from ballot.lists.tx import proper, same_person                             # noqa: E402
from ballot.match import fits                                               # noqa: E402
from ballot.pdftext import lines                                            # noqa: E402
from states import net                                                     # noqa: E402

STATE, FIPS, NAME = "TX", "48", "Texas"
GENERAL = "2026-11-03"
PRIMARY, RUNOFF = fed.PRIMARY, fed.RUNOFF
ROSTER_DB = os.path.join(HERE, "state_tx.sqlite")
COUNTY_ZIP = os.path.join(HERE, "states_cache", "census", "cb_2024_us_county_500k.zip")
CERT_PATH = os.path.join(CACHE, "tx_ballot_cert_2026.pdf")
FED_FOLDER = os.path.join(CACHE, "tx")
RECORDS_FILE = "tx_2026_state_results_records.json"
N_COUNTIES = 254

SCHEMA = """
CREATE TABLE IF NOT EXISTS sl_races (race_id TEXT PRIMARY KEY, state TEXT NOT NULL, level TEXT NOT NULL, office_kind TEXT NOT NULL, office TEXT NOT NULL, jurisdiction TEXT, jurisdiction_id TEXT, county_ids TEXT, district TEXT, seat TEXT, special INTEGER NOT NULL DEFAULT 0, partisan INTEGER NOT NULL, holder_id TEXT, holder_name TEXT, holder_party TEXT, election_date TEXT NOT NULL, note TEXT);
CREATE TABLE IF NOT EXISTS sl_candidates (race_id TEXT NOT NULL, election TEXT NOT NULL, election_date TEXT, name TEXT NOT NULL, party TEXT, party_code TEXT, ballot_order INTEGER, incumbent INTEGER NOT NULL DEFAULT 0, write_in INTEGER NOT NULL DEFAULT 0, votes INTEGER, pct REAL, outcome TEXT, state_member_id TEXT, source_id TEXT, note TEXT, PRIMARY KEY (race_id, election, name));
CREATE TABLE IF NOT EXISTS sl_sources (source_id TEXT PRIMARY KEY, state TEXT, kind TEXT, agency TEXT, title TEXT, url TEXT, published TEXT, fetched TEXT, sha256 TEXT, rows INTEGER, note TEXT);
CREATE TABLE IF NOT EXISTS sl_places (kind TEXT NOT NULL, id TEXT NOT NULL, name TEXT NOT NULL, county_ids TEXT, source_id TEXT, PRIMARY KEY (kind, id));
"""

PARTIES = fed.PARTIES                  # REP Republican, DEM Democratic, LIB Libertarian, GRE Green, IND Independent, W-I Write-in
PRIMARY_PARTIES = ("REP", "DEM")
CAND_LINE = re.compile(r"^(.+?) (REP|DEM|LIB|GRE|IND|W-I)$")
CERT_STAMP = re.compile(r"^\d\d/\d\d/\d{4} \d\d:\d\d [AP]M Page (\d+) of (\d+)$")

# statewide executive offices as the certification and the canvass print them: (key, office_kind, office, roster office)
EXEC = {
    "GOVERNOR": ("GOV", "governor", "Governor", "governor"),
    "LIEUTENANT GOVERNOR": ("LTG", "lieutenant_governor", "Lieutenant Governor", "lt_governor"),
    "ATTORNEY GENERAL": ("AG", "attorney_general", "Attorney General", "attorney general"),
    "COMPTROLLER OF PUBLIC ACCOUNTS": ("COMP", "comptroller", "Comptroller of Public Accounts", None),
    "COMMISSIONER OF THE GENERAL LAND OFFICE": ("GLO", "land_commissioner", "Commissioner of the General Land Office", None),
    "COMMISSIONER OF AGRICULTURE": ("AGR", "agriculture_commissioner", "Commissioner of Agriculture", None),
    "RAILROAD COMMISSIONER": ("RRC", "railroad_commissioner", "Railroad Commissioner", None),
}
ORD = r"(\d+)(?:ST|ND|RD|TH)"
# offices left to the federal pages or a later local phase: (pattern, the report's word for it)
SKIP = [
    (r"U\. ?S\. (SENATOR|REPRESENTATIVE)\b.*", "federal"),
    (r"(CRIMINAL )?DISTRICT ATTORNEY\b.*", "district attorney"),
    (r"JUSTICE OF THE PEACE\b.*", "justice of the peace"),
    (r"JUDGE, (COUNTY|PROBATE)\b.*|(JUDGE, )?PROBATE COURT\b.*|\d+(ST|ND|RD|TH) MULTICOUNTY COURT AT LAW\b.*", "county court"),
    (r"COUNTY\b.*|DISTRICT (AND COUNTY )?CLERK\b.*|SHERIFF\b.*|HARRIS COUNTY DEPARTMENT OF EDUCATION\b.*", "county office"),
    (r"PROPOSITION \d+|YES|NO", "party proposition"),
]

SRC_CERT = "tx-sos-2026-ballot-cert"
SRC_CANVASS = {("primary", "REP"): "tx-sos-2026-primary-rep-canvass", ("primary", "DEM"): "tx-sos-2026-primary-dem-canvass",
               ("runoff", "REP"): "tx-sos-2026-runoff-rep-canvass", ("runoff", "DEM"): "tx-sos-2026-runoff-dem-canvass"}
SRC_RECORDS = "tx-sos-2026-results-records"
SRC_ROSTER = "tx-openstates-roster"
SRC_COUNTIES = "tx-census-cb-2024-county"

NO_ROSTER = "The Open States roster this site uses does not carry this office, so today's holder is not shown."
MARK_NOTE = "The incumbent mark on a candidate here is the Secretary of State's primary canvass's own \"(I)\"."
SPECIAL_NOTE = "An election for the rest of the term (the certification: unexpired term)."
CONTACT = re.compile(r"@|https?://|www\.|\.(com|org|net|gov|us)\b|\(\d{3}\)|\b\d{3}[-.]\d{3}[-.]\d{4}\b|\b\d{5}(-\d{4})?\b|\bP\.? ?O\.? BOX\b", re.I)


def ordinal(n):
    n = int(n)
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def squash(name):
    return fold(name).replace(" ", "")


def strip_mark(raw):
    return re.sub(r"\s*\(I\)\s*$", "", re.sub(r"\s+", " ", raw)).strip()


def is_marked(raw):
    """The canvass's incumbent mark, "(I)" after the name."""
    return bool(re.search(r"\(I\)\s*$", raw))


# ---------- one key for every list: the certification, the canvass and the election records ----------

def classify(heading, cmap):
    """A race dict for a state office this loader keeps, ("skip", word) for one it leaves, or None if unknown. The
    heading is normalised first: spaces, and the canvass's ' - UNEXPIRED TERM' written as the certification's
    ' (UNEXPIRED TERM)'."""
    t = re.sub(r"\s+", " ", heading).strip().upper()
    t = re.sub(r"\s*-\s*\(?UNEXPIRED TERM\)?$", " (UNEXPIRED TERM)", t)
    special = t.endswith(" (UNEXPIRED TERM)")
    base = t[: -len(" (UNEXPIRED TERM)")].strip() if special else t
    suffix = "-UNEXP" if special else ""
    common = {"special": int(special), "partisan": 1, "chamber": None, "roster": None, "district": None, "seat": None,
              "place": None, "statewide": False}

    def race(key, level, kind, office, jur, jur_id, **kw):
        d = dict(common, race_id=f"2026-{STATE}-{key}{suffix}", level=level, office_kind=kind, office=office, jurisdiction=jur,
                 jurisdiction_id=jur_id)
        d.update(kw)
        return d

    if base in EXEC:
        key, kind, office, roster = EXEC[base]
        return race(key, "statewide", kind, office, NAME, STATE, roster=roster, statewide=True)
    if base == "CHIEF JUSTICE, SUPREME COURT":
        return race("SCCJ", "court", "supreme_court", "Chief Justice, Supreme Court", NAME, STATE, seat="Chief Justice", statewide=True)
    m = re.fullmatch(r"JUSTICE, SUPREME COURT, PLACE (\d+)", base)
    if m:
        p = str(int(m.group(1)))
        return race(f"SC{p}", "court", "supreme_court", "Justice, Supreme Court", NAME, STATE, seat=f"Place {p}", statewide=True)
    if base == "PRESIDING JUDGE, COURT OF CRIMINAL APPEALS":
        return race("CCAPJ", "court", "court_of_criminal_appeals", "Presiding Judge, Court of Criminal Appeals", NAME, STATE,
                    seat="Presiding Judge", statewide=True)
    m = re.fullmatch(r"JUDGE, COURT OF CRIMINAL APPEALS, PLACE (\d+)", base)
    if m:
        p = str(int(m.group(1)))
        return race(f"CCA{p}", "court", "court_of_criminal_appeals", "Judge, Court of Criminal Appeals", NAME, STATE, seat=f"Place {p}",
                    statewide=True)
    m = re.fullmatch(rf"CHIEF JUSTICE, {ORD} COURT OF APPEALS DISTRICT", base)
    if m:
        n = str(int(m.group(1)))
        return race(f"COA{n}-CJ", "court", "court_of_appeals", "Chief Justice, Court of Appeals", f"{ordinal(n)} Court of Appeals District",
                    f"{STATE}-COA{n}", district=n, seat="Chief Justice", place=("appeals", f"{STATE}-COA{n}", f"{ordinal(n)} Court of Appeals District"))
    m = re.fullmatch(rf"JUSTICE, {ORD} COURT OF APPEALS DISTRICT, PLACE (\d+)", base)
    if m:
        n, p = str(int(m.group(1))), str(int(m.group(2)))
        return race(f"COA{n}-{p}", "court", "court_of_appeals", "Justice, Court of Appeals", f"{ordinal(n)} Court of Appeals District",
                    f"{STATE}-COA{n}", district=n, seat=f"Place {p}", place=("appeals", f"{STATE}-COA{n}", f"{ordinal(n)} Court of Appeals District"))
    m = re.fullmatch(rf"DISTRICT JUDGE, {ORD} JUDICIAL DISTRICT", base) or re.fullmatch(r"DISTRICT JUDGE, JUDICIAL DISTRICT (\d+[A-Z]?)", base)
    if m:
        n = m.group(1) if not m.group(1).isdigit() else str(int(m.group(1)))
        jur = f"{ordinal(n)} Judicial District" if n.isdigit() else f"Judicial District {n}"
        return race(f"DC{n}", "court", "district_court", "District Judge", jur, f"{STATE}-JD{n}", district=n,
                    place=("judicial", f"{STATE}-JD{n}", jur))
    m = (re.fullmatch(r"CRIMINAL DISTRICT JUDGE,? ([A-Z .']+?) COUNTY(?: NUMBER| NO\.?) ?#?(\d+)", base)
         or re.fullmatch(r"CRIMINAL DISTRICT JUDGE,? #?(\d+),? ([A-Z .']+?) COUNTY", base)
         or re.fullmatch(r"CRIMINAL DISTRICT JUDGE,? ([A-Z .']+?) COUNTY", base))
    if m:
        g = m.groups()
        county, n = (g[1], g[0]) if g[0].isdigit() else (g[0], g[1] if len(g) > 1 else None)
        hit = cmap.get(squash(county))
        if not hit:
            return None
        geoid, full = hit
        n = str(int(n)) if n else None
        return race(f"CDC{geoid[2:]}" + (f"-{n}" if n else ""), "court", "district_court", "Criminal District Judge", full, geoid,
                    seat=f"Number {n}" if n else None, fixed_counties=[geoid])
    m = re.fullmatch(r"MEMBER, STATE BOARD OF EDUCATION, DISTRICT (\d+)", base)
    if m:
        d = str(int(m.group(1)))
        return race(f"SBOE{d}", "statewide", "state_board_of_education", "Member, State Board of Education",
                    f"State Board of Education District {d}", f"{STATE}-SBOE{d}", district=d,
                    place=("sboe", f"{STATE}-SBOE{d}", f"State Board of Education District {d}"))
    m = re.fullmatch(r"STATE SENATOR,? DISTRICT (\d+)", base)
    if m:
        d = str(int(m.group(1)))
        return race(f"SS{d}", "legislature", "state_senate", "State Senator", f"Senate District {d}", f"{STATE}-{d}", district=d,
                    chamber="Senate", place=("senate", f"{STATE}-{d}", f"Senate District {d}"))
    m = re.fullmatch(r"STATE REPRESENTATIVE,? DISTRICT (\d+)", base)
    if m:
        d = str(int(m.group(1)))
        return race(f"SH{d}", "legislature", "state_house", "State Representative", f"House District {d}", f"{STATE}-{d}", district=d,
                    chamber="House", place=("house", f"{STATE}-{d}", f"House District {d}"))
    for pat, word in SKIP:
        if re.fullmatch(pat, base):
            return ("skip", word)
    return None


# ---------- the certification ----------

def read_cert(path, cmap):
    """({race_id: race}, {(race_id, county GEOID): [(name, party code)]}, {kind of office left out: [county lists,
    candidate lines]}, facts)."""
    races, listed, left, left_heads = {}, {}, {}, set()
    county = office = None
    stamps, pages, cover = set(), 0, []
    for page, _y, text in lines(path):
        if page == 1:
            cover.append(text)
            continue
        m = CERT_STAMP.match(text)
        if m:
            stamps.add(int(m.group(1)))
            pages = int(m.group(2))
            continue
        if fed.HEADER.match(text):
            continue
        m = re.match(r"^County (.+)$", text)
        if m:
            hit = cmap.get(squash(m.group(1)))
            if not hit:
                raise SystemExit(f"Texas (state races): the certification names a county the Census file does not have (page {page})")
            county, office = hit[0], None
            continue
        m = CAND_LINE.match(text)
        if m:
            if office is None:
                raise SystemExit(f"Texas (state races): a candidate on page {page} of the certification comes before any office heading")
            if isinstance(office, tuple):
                left.setdefault(office[1], [0, 0])[1] += 1
                continue
            listed.setdefault((office["race_id"], county), []).append((m.group(1).strip(), m.group(2)))
            continue
        if county is None:
            raise SystemExit(f"Texas (state races): page {page} of the certification has text before its county line")
        office = classify(text, cmap)
        if office is None:
            raise SystemExit(f"Texas (state races): an office heading in the certification this loader does not know: {text!r} (page {page})")
        if isinstance(office, tuple):
            left_heads.add((office[1], text, county))
            continue
        races.setdefault(office["race_id"], office)
    joined = " ".join(cover)
    if "DO HEREBY" not in joined or "day of August, 2026" not in joined:
        raise SystemExit("Texas (state races): the certification's cover no longer reads as the August 2026 certification")
    signed = re.search(r"this (\d+)(?:st|nd|rd|th) day of August, 2026", joined)
    if pages != len(stamps) or stamps != set(range(1, pages + 1)):
        raise SystemExit(f"Texas (state races): the certification says {pages} report pages and {len(stamps)} were read")
    for word, _t, _c in left_heads:
        left.setdefault(word, [0, 0])[0] += 1
    return races, listed, left, {"pages": pages + 1, "signed": f"2026-08-{int(signed.group(1)):02d}" if signed else ""}


# ---------- the canvass ----------

def read_canvass(path, name, code, cmap):
    """({race_id: {"office", "cands": [[name as printed, votes]], "total"}} for the state offices this loader keeps,
    printed date, [differences], Counter of offices left out). Checked against its Total lines, its percents and its
    page count."""
    out, differ, left = {}, [], Counter()
    office = head = last = None
    printed, pages, seen = "", 0, set()
    got_title = got_name = False
    said_races, n_totals = None, 0

    def settle():
        nonlocal office
        if head is None:
            return
        c = classify(head["text"], cmap)
        if c is None:
            raise SystemExit(f"Texas (state races): an office in {os.path.basename(path)} this loader does not know: {head['text']!r}")
        if isinstance(c, tuple):
            left[c[1]] += 1
            office = "skip"
            return
        rid = c["race_id"]
        if rid in out:
            raise SystemExit(f"Texas (state races): {os.path.basename(path)} lists {rid} twice")
        out[rid] = {"office": head["text"], "cands": [], "total": None, "race": c}
        office = rid

    for page, y, text in lines(path):
        seen.add(page)
        m = fed.STAMP.match(text)
        if m:
            printed, pages = m.group(1), int(m.group(3))
            continue
        if fed.CANVASS_HEAD.match(text):
            got_title |= text == "Official Canvass Report"
            got_name |= text == name
            continue
        m = re.match(rf"^(.+?) ({code}) ([\d,]+) (\d+\.\d\d) %$", text)
        if m:
            if head is not None and office is None:
                settle()
            head = None
            if office is None:
                raise SystemExit(f"Texas (state races): a candidate in {os.path.basename(path)} (page {page}) comes before any office")
            last = [m.group(1).strip(), int(m.group(3).replace(",", "")), float(m.group(4)), page, y]
            if office != "skip":
                out[office]["cands"].append(last)
            continue
        m = re.match(r"^Total Races ([\d,]+)$", text)
        if m:
            said_races = int(m.group(1).replace(",", ""))
            office, head, last = None, None, None
            continue
        m = re.match(r"^Total ([\d,]+)$", text)
        if m:
            if head is not None and office is None:
                settle()
            head, last = None, None
            n_totals += 1
            if office is None:
                raise SystemExit(f"Texas (state races): a Total line in {os.path.basename(path)} (page {page}) comes before any office")
            if office != "skip":
                out[office]["total"] = int(m.group(1).replace(",", ""))
            continue
        m = re.match(r"^(.+?) ([\d,]+) (\d+\.\d\d) %$", text)
        if m:
            if head is not None and office is None:
                settle()
            office, last = None, None
            head = {"text": m.group(1).strip(), "page": page, "y": y}
            continue
        if head is not None and office is None and head["page"] == page and 0 < head["y"] - y < 16:
            head["text"] = f"{head['text']} {text.strip()}"          # an office heading's second line
            head["y"] = y
            continue
        if last and last[3] == page and 0 < last[4] - y < 16:      # the rest of a long name, on the line just below
            last[0] = last[0] + text.strip() if last[0].endswith("-") else f"{last[0]} {text.strip()}"     # CANTU- / CASTLE
            last[4] = y
            continue
        raise SystemExit(f"Texas (state races): a line in {os.path.basename(path)} (page {page}) the loader cannot place"
                         + (f" under {office}" if office and office != "skip" else ""))
    if head is not None and office is None:
        settle()
    if not (got_title and got_name):
        raise SystemExit(f"Texas (state races): {os.path.basename(path)} is not the Official Canvass Report of the {name}")
    if pages != len(seen):
        differ.append(f"{name}: the report says {pages} pages and {len(seen)} were read")
    if said_races != n_totals:
        differ.append(f"{name}: the report's closing line counts {said_races} races and {n_totals} Total lines were read")
    for rid, c in out.items():
        total = sum(v for _n, v, *_ in c["cands"])
        if c["total"] != total:
            differ.append(f"{name}, {rid}: Total {c['total']} is not the sum of its candidates ({total})")
        for n, v, pct, *_ in c["cands"]:
            if total and abs(100 * v / total - pct) > 0.006:
                differ.append(f"{name}, {rid}: a printed percent ({pct}) is not {100 * v / total:.2f}")
        c["cands"] = [(n, v) for n, v, *_ in c["cands"]]
    stamp = dt.datetime.strptime(printed, "%m/%d/%Y").strftime("%Y-%m-%d") if printed else ""
    return out, stamp, differ, left


def records(meta, keep_dir, say):
    """{"<kind>-<party>": {"id", "races": [{"N", "T", "C": [[name, party, votes]]}]}} from each election's record: the
    StateWide and Districted sections only, and of them only race name, total, candidate name, party and votes. Kept
    30 days in keep_dir (the results are canvassed)."""
    path = os.path.join(keep_dir, RECORDS_FILE)
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < 30 * 86400:
        got = json.load(open(path, encoding="utf-8"))
        if all(k in got and got[k].get("id") == meta[k]["id"] for k in meta):
            return got, path
    got = {}
    for key, m in meta.items():
        time.sleep(1.0)
        rec = json.loads(net.get(f"{fed.API}/election/{m['id']}", accept="application/json"))
        home = json.loads(base64.b64decode(rec["Home"]))
        if home.get("ElecDate") != dt.date.fromisoformat(m["date"]).strftime("%m%d%Y"):
            raise SystemExit(f"Texas (state races): the results system dates election {m['id']} {home.get('ElecDate')}, not {m['date']}")
        races = []
        for sec in ("StateWide", "Districted"):
            for r in json.loads(base64.b64decode(rec[sec])).get("Races") or []:
                races.append({"N": re.sub(r"\s+", " ", r["N"]).strip(), "T": int(r["T"]),
                              "C": [[re.sub(r"\s+", " ", c["N"]).strip(), c["P"], int(c["V"])] for c in r.get("Candidates") or []]})
        got[key] = {"id": m["id"], "name": m["name"], "races": races}
    os.makedirs(keep_dir, exist_ok=True)
    json.dump(got, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    say(f"    Texas (state races): kept the four election records' state races ({sum(len(v['races']) for v in got.values())} races; "
        "names, parties and votes only)")
    return got, path


# ---------- the roster and the counties ----------

def roster(path=ROSTER_DB):
    """Today's holders: {("Senate"|"House", district): row}, {roster office: row}, the roster's date, and the roster's own
    spelling of each sitting member's name. Only id, name, party, chamber, district and office are selected."""
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    seats, offices, forms = {}, {}, {}
    for r in con.execute("SELECT bioguide_id, first_name, last_name, official_full, party_name, chamber, district "
                         "FROM legislators WHERE is_current = 1"):
        key = (r[5], str(r[6]).strip())
        if key in seats:
            raise SystemExit(f"Texas (state races): the roster lists two sitting members for {key}")
        seats[key] = {"id": r[0], "first": r[1], "last": r[2], "full": r[3] or f"{r[1]} {r[2]}", "party": r[4]}
    for r in con.execute("SELECT bioguide_id, first_name, last_name, official_full, party_name, office FROM officials"):
        offices[r[5]] = {"id": r[0], "first": r[1], "last": r[2], "full": r[3] or f"{r[1]} {r[2]}", "party": r[4]}
    as_of = (con.execute("SELECT max(updated_at) FROM legislators").fetchone()[0] or "")[:10]
    con.close()
    for h in list(seats.values()) + list(offices.values()):
        for form in (h["full"], f"{h['first']} {h['last']}"):
            if form:
                forms[squash(form)] = h["full"]
    return seats, offices, as_of, forms


def counties(path=COUNTY_ZIP):
    """{squashed county name: (GEOID, "Anderson County")} for Texas from the Census Bureau's cartographic county file."""
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
    if len(out) != N_COUNTIES:
        raise SystemExit(f"Texas (state races): the county file gives {len(out)} Texas counties, not {N_COUNTIES}")
    return out


def holder_fits(name, h):
    """The name fits the roster's holder: as written without its nickname, or with the nickname in quotes or brackets
    as the given name (MARIA LUISA "LULU" FLORES for Lulu Flores)."""
    plain = re.sub(r'"[^"]*"|\([^)]*\)', " ", name)
    forms = [name_parts(plain)]
    family = forms[0][1]
    for nick in re.findall(r'"([^"]+)"|\(([^)]+)\)', name):
        nick = "".join(nick).strip()
        if nick and family:
            forms.append((fold(nick).split(), family))
    regs = [reg for reg in ((fold(h["first"]).split(), fold(h["last"])), name_parts(h["full"] or "")) if reg[1]]
    return any(fits(cand, reg) for cand in forms for reg in regs)


def family_of(name):
    return name_parts(re.sub(r'"[^"]*"|\([^)]*\)', " ", name))[1]


def sha_of(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest() if os.path.exists(path) else ""


def mdate(path):
    return dt.date.fromtimestamp(os.path.getmtime(path)).isoformat() if os.path.exists(path) else ""


def shown_with(forms):
    def shown(caps):
        """'JAMES "JIM" SMITH (I)' -> 'James "Jim" Smith'; initials written together stay capitals (TJ); a sitting
        member as the roster spells the name."""
        name = strip_mark(caps)
        if squash(name) in forms:
            return forms[squash(name)]
        words = proper(name).split()
        for i, w in enumerate(name.split()):
            if i < len(words) and re.fullmatch(r"[B-DF-HJ-NP-TV-XZ]{2,3}", w) and w not in ("JR", "SR"):
                words[i] = w
        t = re.sub(r"(^|\s)([\"\u201c(])([a-z])", lambda m: m.group(1) + m.group(2) + m.group(3).upper(), " ".join(words))
        return re.sub(r"\b([A-Z])\.([a-z])\b", lambda m: m.group(1) + "." + m.group(2).upper(), t)
    return shown


# ---------- the load ----------

def load(db_path, say=print, keep_dir=FED_FOLDER):
    net.patient_lookups()
    cmap = counties()
    by_geoid = {g: full for g, full in cmap.values()}
    seats, offices, as_of, forms = roster()
    shown = shown_with(forms)
    checks, info = [], []

    # 1. the November certification
    net.download(fed.URL, CERT_PATH, max_age_days=30, say=say)
    c_races, listed, c_left, c_facts = read_cert(CERT_PATH, cmap)
    where, lists, disagree = {}, {}, []
    for (rid, geoid), cands in sorted(listed.items()):
        where.setdefault(rid, set()).add(geoid)
        first = lists.setdefault(rid, (geoid, cands))
        if first[1] != cands and rid not in disagree:
            disagree.append(rid)
    for rid in disagree:
        checks.append(f"{rid}: the counties' certification lists disagree; its November candidates are left out")
    for rid, r in c_races.items():
        if r.get("fixed_counties") and where.get(rid, set()) - set(r["fixed_counties"]):
            checks.append(f"{rid}: a county court race listed in {len(where[rid])} counties")
        if r["statewide"] and len(where.get(rid, ())) != N_COUNTIES:
            checks.append(f"{rid}: a statewide contest listed in {len(where.get(rid, ()))} of {N_COUNTIES} counties")

    # which seats: every Senate and House seat the certification lists; statewide offices checked against the list above
    sen = sorted(int(r["district"]) for r in c_races.values() if r["office_kind"] == "state_senate" and not r["special"])
    hou = sorted(int(r["district"]) for r in c_races.values() if r["office_kind"] == "state_house" and not r["special"])
    if hou != list(range(1, 151)):
        checks.append(f"House districts on the certification are not all 150 (missing {sorted(set(range(1, 151)) - set(hou))})")
    if len(sen) != len(set(sen)) or not sen or any(not 1 <= d <= 31 for d in sen):
        checks.append(f"Senate districts on the certification: {sen}")
    missing_exec = sorted(k for k, (key, *_r) in EXEC.items() if f"2026-{STATE}-{key}" not in c_races)
    if missing_exec:
        info.append("statewide offices not on the certification this year: " + ", ".join(missing_exec))

    general = {}
    for rid in c_races:
        if rid in disagree or rid not in lists:
            continue
        general[rid] = [(shown(n), code, order) for order, (n, code) in enumerate(lists[rid][1], start=1)]
        seen_codes = Counter(code for _n, code, _o in general[rid] if code in PARTIES and code not in ("IND", "W-I"))
        if any(v > 1 for v in seen_codes.values()):
            checks.append(f"{rid}: two candidates of one party on the certification")

    # 2. the primaries and runoffs, from the official canvass, checked against the election records
    meta = fed.election_records(FED_FOLDER, say)
    books, printed = {}, {}
    for (kind, code), (_date, ename, _t) in fed.ELECTIONS.items():
        m = meta[f"{kind}-{code}"]
        book, stamp, d, _left = read_canvass(os.path.join(FED_FOLDER, m["file"]), ename, code, cmap)
        books[(kind, code)] = book
        printed[(kind, code)] = stamp
        checks += d
    # the election records against the canvass. The records' race names leave out "UNEXPIRED TERM", so races are
    # compared by seat (the key without -UNEXP), every race of a seat together; votes and totals must be equal, and
    # names the same person (the two sometimes print a name differently: JAMES FRANKLIN ALVARADO, JAMES ALVARADO)
    recs, rec_path = records(meta, keep_dir, say)
    rec_checked, rec_names = 0, []
    seat = lambda rid: rid[:-len("-UNEXP")] if rid.endswith("-UNEXP") else rid
    for (kind, code), book in books.items():
        rec, mine = {}, {}
        for r in recs[f"{kind}-{code}"]["races"]:
            c = classify(r["N"], cmap)
            if isinstance(c, dict):
                rec.setdefault(seat(c["race_id"]), []).append((r["T"], sorted(((v, strip_mark(n)) for n, _p, v in r["C"]), reverse=True)))
            elif c is None:
                checks.append(f"{kind}-{code}: the election record has an office this loader does not know: {r['N']!r}")
        for rid, c in book.items():
            mine.setdefault(seat(rid), []).append((c["total"], sorted(((v, strip_mark(n)) for n, v in c["cands"]), reverse=True)))
        for key in sorted(set(rec) | set(mine)):
            a, b = sorted(rec.get(key, [])), sorted(mine.get(key, []))
            rec_checked += 1
            same_votes = [(t, [v for v, _n in cs]) for t, cs in a] == [(t, [v for v, _n in cs]) for t, cs in b]
            if not same_votes:
                checks.append(f"{kind}-{code}, {key}: the election record's votes differ from the canvass report's"
                              + (" (a one-candidate primary; no votes are stored for it)" if all(len(cs) == 1 for _t, cs in a + b) else ""))
            elif any(not same_person(x, y) for (_t, ca), (_u, cb) in zip(a, b) for (_v, x), (_w, y) in zip(ca, cb)):
                rec_names.append(f"{kind}-{code} {key}")

    # a canvass race is filed under the certification's race for the same seat when the two disagree only on whether
    # it is for the rest of a term, and there is just one such race on the certification
    relabeled = []
    for (kind, code), book in books.items():
        for rid in list(book):
            if rid in c_races:
                continue
            fit = [x for x in (seat(rid), seat(rid) + "-UNEXP") if x in c_races]
            if len(fit) == 1 and fit[0] not in book:
                book[fit[0]] = book.pop(rid)
                relabeled.append(f"{kind}-{code} {rid} -> {fit[0]}")
            else:
                checks.append(f"{rid}: in the {kind} {code} canvass but not on the November certification; its primary is not stored")

    prim, nominee, fields = [], {}, Counter()
    for code in PRIMARY_PARTIES:
        party = PARTIES[code]
        primary, runoff = books[("primary", code)], books[("runoff", code)]
        for rid, c in sorted(primary.items()):
            if rid not in c_races:
                continue
            cands, total = c["cands"], c["total"]
            ranked = sorted(cands, key=lambda x: -x[1])
            if len(cands) == 1:
                nominee[(rid, code)] = ("primary", cands[0][0])
                continue
            fields[c_races[rid]["office_kind"]] += 1
            went, notes = set(), {}
            if ranked[0][1] * 2 > total:
                winners = {ranked[0][0]}
                nominee[(rid, code)] = ("primary", ranked[0][0])
            else:
                r = runoff.get(rid)
                on = [n for n, pc, _o in general.get(rid, []) if pc == code]
                lead, second = shown(ranked[0][0]), shown(ranked[1][0])
                if not r and any(same_person(x, lead) for x in on) and not any(same_person(x, second) for x in on):
                    winners = {ranked[0][0]}
                    nominee[(rid, code)] = ("primary", ranked[0][0])
                    notes = {ranked[0][0]: fed.NO_RUNOFF_LEAD, ranked[1][0]: fed.NO_RUNOFF_SECOND}
                    info.append(f"{rid} {party}: no majority on March 3 and no runoff on May 26; the November certification names the leader")
                elif not r:
                    checks.append(f"{rid} {party}: no majority on March 3 and no runoff in the May 26 canvass")
                    winners = set()
                else:
                    pair = {n for n, _v in r["cands"]}
                    if len(ranked) > 2 and ranked[1][1] == ranked[2][1]:
                        checks.append(f"{rid} {party}: a tie for second place on March 3")
                    if pair != {ranked[0][0], ranked[1][0]}:
                        checks.append(f"{rid} {party}: the runoff's pair is not the primary's top two")
                    winners = went = pair
            for n, votes in cands:
                prim.append({"rid": rid, "election": f"primary-{code}", "date": PRIMARY, "raw": n, "name": shown(n), "code": code,
                             "votes": votes, "pct": round(100 * votes / total, 1) if total else None,
                             "outcome": ("advanced" if n in winners else "lost") if winners else None,
                             "src": SRC_CANVASS[("primary", code)], "note": fed.RUNOFF_NOTE if n in went else notes.get(n)})
        for rid, c in sorted(runoff.items()):
            if rid not in c_races:
                continue
            cands, total = c["cands"], c["total"]
            if rid not in primary:
                checks.append(f"{rid} {party}: a runoff with no March 3 contest")
            ranked = sorted(cands, key=lambda x: -x[1])
            if len(cands) != 2 or ranked[0][1] == ranked[1][1]:
                checks.append(f"{rid} {party}: the runoff has {len(cands)} candidates or a tie")
                continue
            nominee[(rid, code)] = ("runoff", ranked[0][0])
            for n, votes in cands:
                prim.append({"rid": rid, "election": f"runoff-{code}", "date": RUNOFF, "raw": n, "name": shown(n), "code": code,
                             "votes": votes, "pct": round(100 * votes / total, 1) if total else None,
                             "outcome": "advanced" if n == ranked[0][0] else "lost", "src": SRC_CANVASS[("runoff", code)], "note": None})

    # each nominee must be the party's candidate on the November certification
    not_on = []
    for (rid, code), (stage, raw) in sorted(nominee.items()):
        noted = False
        who = shown(raw)
        on = [n for n, pc, _o in general.get(rid, []) if pc == code]
        if any(same_person(x, who) for x in on):
            continue
        not_on.append(rid)
        note = (f"Won the nomination; the Secretary of State's November certification names {on[0]} as the party's candidate instead."
                if on else "Won the nomination; not on the Secretary of State's November certification.")
        for p in prim:
            if p["rid"] == rid and p["election"] == f"{stage}-{code}" and p["raw"] == raw:
                p["note"] = " ".join(x for x in (p["note"], note) if x)
                noted = True
        if rid not in disagree:
            info.append(f"{rid}: the {PARTIES[code]} nominee in the canvass is not the party's candidate on the November certification"
                        + (" (another candidate is listed" if on else " (none is listed")
                        + ("; the stored primary row says so)" if noted else "; a one-candidate primary, not stored)"))
    # a party's November candidate with no March 3 contest for that party (a nominee named by the party after filing)
    no_primary = sorted({rid for rid, cs in general.items() for _n, code, _o in cs
                         if code in PRIMARY_PARTIES and rid not in books[("primary", code)]})

    # 3. holders, the sitting member and the canvass's incumbent marks
    holders, n_holder = {}, {}
    for rid, r in c_races.items():
        h = None
        if r["chamber"]:
            h = seats.get((r["chamber"], r["district"]))
            if h is None:
                n_holder[rid] = f"The Open States roster ({as_of}) lists no sitting member for this seat."
        elif r["roster"]:
            h = offices.get(r["roster"])
            if h is None:
                n_holder[rid] = f"The Open States roster ({as_of}) lists no one in this office."
        else:
            n_holder[rid] = NO_ROSTER
        holders[rid] = h
    sitting, marked_used, mark_diff, mark_agree, mark_matched = {}, [], [], 0, []
    for rid, r in c_races.items():
        # every name in the race (November, the fields, the runoffs), and every canvass name with its "(I)" mark,
        # one-candidate primaries included
        canv = [(shown(n), is_marked(n)) for book in books.values() if rid in book for n, _v in book[rid]["cands"]]
        names = [n for n, _c, _o in general.get(rid, [])] + [n for n, _m in canv]
        marked = [n for n, m in canv if m]
        h = holders[rid]
        if h:
            fit = [n for n in names if holder_fits(n, h)]
            fam = {family_of(h["full"]), fold(h["last"])} - {""}
            by_mark = [x for x in marked if family_of(x) in fam]
            if fit and all(same_person(fit[0], x) for x in fit):
                sitting[rid] = ({squash(x) for x in fit}, h["id"])
            elif fit:
                checks.append(f"{rid}: more than one candidate's name fits the roster's holder; none is marked as the sitting member")
            elif by_mark and all(same_person(by_mark[0], x) for x in by_mark):
                # the given names do not fit (Jolanda for Jo), but the canvass marks a candidate of the holder's family
                # name as the incumbent: that candidate is taken, and listed
                sitting[rid] = ({squash(x) for x in names if any(same_person(x, y) for y in by_mark)}, h["id"])
                mark_matched.append(rid)
                fit = by_mark
            in_canvass = [n for n, _m in canv if holder_fits(n, h) or n in fit]
            if marked and not any(holder_fits(x, h) or x in fit for x in marked):
                mark_diff.append(f"{rid}: the canvass marks a candidate as the incumbent whose name does not fit the roster's holder")
            elif in_canvass and not marked:
                mark_diff.append(f"{rid}: the roster's holder is in the primary canvass without its incumbent mark")
            elif marked:
                mark_agree += 1
        elif r["chamber"] or r["roster"]:
            if marked:
                mark_diff.append(f"{rid}: the roster lists no holder, and the canvass marks a candidate as the incumbent")
        elif marked:
            if all(same_person(marked[0], x) for x in marked):
                sitting[rid] = ({squash(x) for x in names if any(same_person(x, y) for y in marked)}, None)
                marked_used.append(rid)
            else:
                checks.append(f"{rid}: the canvass marks more than one person as the incumbent")

    def inc_of(rid, name):
        return rid in sitting and squash(name) in sitting[rid][0]

    # 4. rows
    cand = []
    for rid, cs in sorted(general.items()):
        for name, code, order in cs:
            party = PARTIES[code]
            inc = inc_of(rid, name)
            cand.append((rid, "general", GENERAL, name, party, party_code(party), order, 1 if inc else 0, int(code == "W-I"),
                         None, None, None, sitting[rid][1] if inc else None, SRC_CERT, None))
    for p in prim:
        party = PARTIES[p["code"]]
        inc = inc_of(p["rid"], p["name"])
        cand.append((p["rid"], p["election"], p["date"], p["name"], party, party_code(party), None, 1 if inc else 0, 0, p["votes"],
                     p["pct"], p["outcome"], sitting[p["rid"]][1] if inc else None, p["src"], p["note"]))
    keys = Counter((c[0], c[1], c[3]) for c in cand)
    dup = [k for k, v in keys.items() if v > 1]
    if dup:
        raise SystemExit(f"Texas (state races): two candidates shown under one name in one election ({len(dup)} cases, e.g. {dup[0][0]})")

    race_rows, place_rows = [], []
    senate_up = ", ".join(str(d) for d in sen)
    for rid, r in sorted(c_races.items()):
        h = holders[rid]
        note = []
        if r["special"]:
            note.append(SPECIAL_NOTE)
        if rid in disagree:
            note.append("The counties' copies of the certification list this race differently, so its November candidates are not shown.")
        if r["office_kind"] == "state_senate" and not r["special"]:
            note.append(f"Senate terms are staggered: the certification lists {len(sen)} of the Texas Senate's 31 seats this year "
                        f"(districts {senate_up}).")
        if r["office_kind"] == "governor" or r["office_kind"] == "lieutenant_governor":
            note.append("The Governor and Lieutenant Governor are elected separately in Texas.")
        if n_holder.get(rid):
            note.append(n_holder[rid])
        if rid in marked_used:
            note.append(MARK_NOTE)
        cids = None if r["statewide"] else json.dumps(sorted(r.get("fixed_counties") or where.get(rid, ())))
        race_rows.append((rid, STATE, r["level"], r["office_kind"], r["office"], r["jurisdiction"], r["jurisdiction_id"], cids,
                          r["district"], r["seat"], r["special"], r["partisan"], h["id"] if h else None, h["full"] if h else None,
                          h["party"] if h else None, GENERAL, " ".join(note) or None))
    places = {}
    for rid, r in c_races.items():
        if r["place"]:
            kind, pid, pname = r["place"]
            cs = places.setdefault((kind, pid), [pname, set()])[1]
            cs.update(where.get(rid, ()))
    place_rows = [("county", g, full, json.dumps([g]), SRC_COUNTIES) for g, full in sorted(by_geoid.items())]
    place_rows += [(k, pid, pname, json.dumps(sorted(cs)) if cs else None, SRC_CERT) for (k, pid), (pname, cs) in sorted(places.items())]

    # privacy: nothing that looks like a contact detail in any stored name or note
    for row in cand:
        for v in (row[3], row[14]):
            if v and CONTACT.search(v):
                raise SystemExit(f"Texas (state races): a stored name or note for {row[0]} looks like a contact detail; nothing written")
    for row in race_rows:
        if row[16] and CONTACT.search(row[16]):
            raise SystemExit(f"Texas (state races): the note for {row[0]} looks like a contact detail; nothing written")

    # 5. sources and the write
    n_gen = sum(1 for c in cand if c[1] == "general")
    left_words = "; ".join(f"{k} ({a:,} county lists, {b:,} candidate lines)" for k, (a, b) in sorted(c_left.items()))
    cert_lines = sum(len(v) for (rid, _g), v in listed.items() if rid in general)
    cert_note = (f"Read county by county, all {N_COUNTIES} counties, {c_facts['pages']:,} pages (the cover and "
                 f"{c_facts['pages'] - 1:,} report pages, every page stamp accounted for): offices, names and parties only. "
                 f"{len(c_races)} state races kept ({cert_lines:,} county lines of their candidates; every county's list of each race "
                 "agreed" + (f" except {', '.join(disagree)}, left out" if disagree else "") + "). The list's order is kept as the ballot "
                 "order. Left for the federal pages or a later local phase: " + left_words
                 + ". A race's county_ids are the counties whose lists carry it. Names are printed in capitals and shown in ordinary "
                 "capitals (a sitting member as the roster spells the name).")
    src = [(SRC_CERT, STATE, "official candidate list", "Texas Secretary of State",
            "Ballot Certification Report, 2026 November General Election (state and district offices)", fed.URL, c_facts["signed"] or "2026-08-28",
            mdate(CERT_PATH), sha_of(CERT_PATH), n_gen, cert_note)]
    for (kind, code), (date, ename, _t) in fed.ELECTIONS.items():
        m = meta[f"{kind}-{code}"]
        book = {rid: c for rid, c in books[(kind, code)].items() if rid in c_races}
        title = ename.title().replace("2026 ", "")
        src.append((SRC_CANVASS[(kind, code)], STATE, "official results", "Texas Secretary of State, Elections Division",
                    f"Official Canvass Report: 2026 {title}, {dt.date.fromisoformat(date).strftime('%B %d, %Y').replace(' 0', ' ')}",
                    m["url"], printed[(kind, code)], m.get("read", ""), m.get("sha256") or sha_of(os.path.join(FED_FOLDER, m["file"])),
                    sum(1 for p in prim if p["src"] == SRC_CANVASS[(kind, code)]),
                    f"The Official Canvass Report the Secretary of State's election results system offers for this election ({fed.REPORTS_PAGE}, "
                    f"election {m['id']}, marked official), printed {printed[(kind, code)]}. The state offices read ({len(book)}, "
                    f"{sum(len(c['cands']) for c in book.values())} candidates; stored: the fields of two or more): each candidate's canvass votes; every office's Total line equals the sum of its candidates and every printed percent "
                    "matches; the election record's own figures equal the report's, race by race. The report carries no write-in "
                    "line. Names are shown in ordinary capitals; the report's incumbent mark \"(I)\" is taken off the name."))
    src.append((SRC_RECORDS, STATE, "official results", "Texas Secretary of State, Elections Division",
                "Election results system records (StateWide and Districted races) for the 2026 primaries and runoffs",
                f"{fed.API}/election/<id>", "", mdate(rec_path), sha_of(rec_path), sum(len(v["races"]) for v in recs.values()),
                "Elections " + ", ".join(str(v["id"]) for v in recs.values()) + ": only race name, total and each candidate's name, "
                f"party and votes are kept. {rec_checked} state races compared with the canvass reports."))
    src.append((SRC_ROSTER, STATE, "roster", "Open States people project (CC0)",
                "Texas legislators and statewide officials, as loaded into state_tx.sqlite", "https://github.com/openstates/people",
                as_of, as_of, "", len(seats) + len(offices),
                "Today's holder of each seat and office. The roster carries the Governor, Lieutenant Governor, Attorney General and "
                "Secretary of State only among statewide offices. A candidate is marked as the sitting member only when the name fits "
                "the holder of that seat and every fitting name in the race is the same person. For offices the roster does not "
                "carry, the incumbent flag is the primary canvass's own \"(I)\" mark, with no member id."))
    src.append((SRC_COUNTIES, STATE, "boundaries", "U.S. Census Bureau",
                "Cartographic boundary file, counties, 2024, 1:500,000 (cb_2024_us_county_500k)",
                "https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_county_500k.zip", "", mdate(COUNTY_ZIP), sha_of(COUNTY_ZIP),
                N_COUNTIES, "Texas's 254 counties: names and GEOIDs only."))

    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA)
    with con:
        con.execute("DELETE FROM sl_candidates WHERE race_id LIKE '2026-TX-%'")
        con.execute("DELETE FROM sl_races WHERE state = 'TX'")
        con.execute("DELETE FROM sl_sources WHERE state = 'TX'")
        con.execute("DELETE FROM sl_places WHERE (kind = 'county' AND id GLOB '48[0-9][0-9][0-9]') OR id LIKE 'TX-%'")
        con.executemany("INSERT INTO sl_races VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", race_rows)
        con.executemany("INSERT INTO sl_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", cand)
        con.executemany("INSERT INTO sl_places VALUES (?,?,?,?,?)", place_rows)
        con.executemany("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", src)
    con.close()

    # 6. the report: counts, race keys and office titles only
    def grp(rid):
        r = c_races[rid]
        return r["office_kind"] if r["level"] in ("legislature", "court") else ("sboe" if r["office_kind"] == "state_board_of_education" else "statewide")
    order = ["state_senate", "state_house", "statewide", "sboe", "supreme_court", "court_of_criminal_appeals", "court_of_appeals", "district_court"]
    by = Counter(grp(rid) for rid in c_races)
    gen_by = Counter(grp(c[0]) for c in cand if c[1] == "general")
    inc_by = Counter(grp(c[0]) for c in cand if c[1] == "general" and c[7])
    pf = Counter(grp(p["rid"]) for p in prim if p["election"].startswith("primary"))
    fld = Counter()
    for (rid, e) in {(p["rid"], p["election"]) for p in prim}:
        fld[(grp(rid), e.split("-")[0])] += 1
    sp = Counter(grp(rid) for rid, r in c_races.items() if r["special"])
    say(f"    Texas (state races): {len(c_races)} races, {n_gen} candidates on the November ballot; "
        + "; ".join(f"{k}: {by[k]} races" + (f" ({sp[k]} for the rest of a term)" if sp[k] else "") + f", {gen_by[k]} candidates, "
                    f"{fld[(k, 'primary')]} primary fields ({pf[k]} candidates), {fld[(k, 'runoff')]} runoffs, sitting member on the November ballot in {inc_by[k]}"
                    for k in order if by[k]))
    say(f"    Texas (state races): Senate seats up: {senate_up}. Counts: {cert_lines:,} certification lines for these races across "
        f"{len({g for (rid, g) in listed if rid in general})} counties = {n_gen} candidates, one per race; "
        f"{sum(len(c['cands']) for (k, cd), b in books.items() for rid, c in b.items() if rid in c_races)} canvass candidate lines "
        f"for these races, {len(prim)} stored (fields only), every Total line equal to its candidates' sum"
        + ("" if not any("Total" in c or "percent" in c for c in checks) else " EXCEPT as listed below"))
    say(f"    Texas (state races): primaries reconciled with the election records: {rec_checked} race comparisons; "
        f"{len(nominee)} nominations checked against the certification ({len(not_on)} differ); "
        f"{len(no_primary)} party candidates on the certification with no March 3 contest for their party"
        + (f" ({', '.join(no_primary[:8])}{' ...' if len(no_primary) > 8 else ''})" if no_primary else "")
        + f"; the canvass's incumbent marks agree with the roster in {mark_agree} races and differ in {len(mark_diff)}; "
        f"incumbent flag from the canvass mark (offices the roster lacks) in {len(marked_used)} races")
    say(f"    Texas (state races): left for the federal pages or a local phase: {left_words}")
    for line in info:
        say(f"    Texas (state races): {line}")
    if mark_matched:
        say(f"    NOTE Texas (state races): sitting member taken from the canvass's incumbent mark and the roster's family name "
            f"(the given names do not fit): {', '.join(sorted(mark_matched))}")
    if relabeled:
        say(f"    NOTE Texas (state races): the canvass and the certification disagree on whether these are for the rest of a term; "
            f"filed under the certification's race: {'; '.join(relabeled)}")
    if rec_names:
        say(f"    NOTE Texas (state races): the election record prints a name differently from the canvass (votes equal): {'; '.join(rec_names)}")
    no_mark = sorted(d.split(":")[0] for d in mark_diff if "without its incumbent mark" in d)
    if no_mark:
        say(f"    NOTE Texas (state races): the roster's holder is in the primary canvass without the canvass's incumbent mark (seated "
            f"since filing, or unmarked): {', '.join(no_mark)}")
    for d in mark_diff:
        if "without its incumbent mark" not in d:
            say(f"    NOTE Texas (state races): {d}")
    for c in checks:
        say(f"    CHECK Texas (state races): {c}")
    return len(cand)


if __name__ == "__main__":
    args = sys.argv[1:]
    keep = FED_FOLDER
    if "--keep" in args:
        i = args.index("--keep")
        keep = args[i + 1]
        del args[i:i + 2]
    if len(args) != 1:
        raise SystemExit("usage: python -m ballot.state_local_tx <database file> [--keep <folder>]")
    load(args[0], keep_dir=keep)
