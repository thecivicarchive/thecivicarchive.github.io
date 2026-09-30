"""
ballot/state_local_mo.py - Missouri's state races on the November 3, 2026 ballot: the Missouri Senate seats up this year
(the 17 even-numbered districts; Missouri elects half its Senate every two years), all 163 Missouri House seats, the
State Auditor (the only statewide office on this year's ballot), and the retention votes for the Supreme Court and the
Court of Appeals, with the August 4 party primaries that chose the nominees. Written into ballot_local_2026.sqlite
(never ballot_2026.sqlite).

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
  - Circuit and associate circuit judges (partisan races in some circuits, retention in others) are local courts and are
    left for the county pages; the loader counts them and stores nothing about them. U.S. Representative lines are the
    federal loader's.
"""

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
from ballot.lists import mo as fed                                          # noqa: E402
from ballot.match import fits                                               # noqa: E402
from ballot.pdftext import PDF, join, rows as pdf_rows                     # noqa: E402
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


def get_general(extract_dir, say, max_age_days=7):
    """The certification: the federal loader's cached copy when fresh, else fetched into memory (never saved)."""
    extract = os.path.join(extract_dir, "sl_mo_general_certification.json")
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
        return ex["published"], [tuple(r) for r in ex["rows"]], Counter(ex["others"]), ex["sha256"], ex["fetched"], "the saved extract"
    if not data.startswith(b"%PDF"):
        raise SystemExit("Missouri (state races): the certification address did not return a PDF")
    published, rows, others = read_general(data)
    sha = hashlib.sha256(data).hexdigest()
    del data
    os.makedirs(extract_dir, exist_ok=True)
    with open(extract, "w", encoding="utf-8") as fh:         # section, office, district and name only
        json.dump({"url": fed.GENERAL_URL, "sha256": sha, "fetched": fetched, "published": published,
                   "others": dict(others), "rows": rows}, fh, ensure_ascii=False, indent=0)
    return published, rows, others, sha, fetched, how


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


# ---------- the load ----------

def load(db_path, say=print, extract_dir=os.path.join(CACHE, "mo")):
    net.patient_lookups()
    published, g_rows, others, g_sha, g_fetched, g_how = get_general(extract_dir, say)
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
    place_rows = [("county", geoid, full, None, SRC_COUNTIES) for geoid, full in cmap]

    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA)
    with con:
        con.execute("DELETE FROM sl_candidates WHERE race_id LIKE '2026-MO-%'")
        con.execute("DELETE FROM sl_races WHERE state = 'MO'")
        con.execute("DELETE FROM sl_sources WHERE state = 'MO'")
        con.execute("DELETE FROM sl_places WHERE kind = 'county' AND id GLOB '29[0-9][0-9][0-9]'")
        con.executemany("INSERT INTO sl_races VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", race_rows)
        con.executemany("INSERT INTO sl_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", cand)
        con.executemany("INSERT INTO sl_places VALUES (?,?,?,?,?)", place_rows)
        src = [
            (SRC_GENERAL, STATE, "official candidate list", "Missouri Secretary of State",
             "Certification of Candidates and Party Emblems, General Election, Tuesday, November 3, 2026", fed.GENERAL_URL,
             published, g_fetched, g_sha, n_listed,
             f"Read from {g_how}: the State Auditor, State Senator and State Representative lines of each party section and the "
             "Supreme Court and Court of Appeals retention lines of the judicial section. Ballot order is the certification's own "
             "order (no ballot numbers are printed; parties in the order it lists them). It lists no write-in candidates. Senate "
             f"seats on it: the {len(sen)} even-numbered districts. Left to others: {others.get('federal', 0)} U.S. Representative "
             f"lines (the federal pages) and {others.get('local court', 0)} circuit and associate circuit judge lines (local courts, "
             "for the county pages)."),
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
             sha_of(COUNTY_ZIP), len(place_rows), "Missouri's 114 counties and the City of St. Louis: names and GEOIDs only."),
        ]
        con.executemany("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", src)
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
    say(f"    Missouri (state races): left to others: {others.get('federal', 0)} U.S. Representative and "
        f"{others.get('local court', 0)} local judge lines on the certification; {prim_other.get('federal', 0)} federal and "
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
    return len(cand)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: python ballot/state_local_mo.py <database file>")
    load(sys.argv[1])
