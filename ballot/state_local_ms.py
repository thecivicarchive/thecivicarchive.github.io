"""
ballot/state_local_ms.py - Mississippi's state races on the November 3, 2026 ballot, into ballot_local_2026.sqlite
(never ballot_2026.sqlite), Mississippi's rows only.

What is on the ballot. Mississippi elects its Governor, the other statewide officers and the whole Legislature in odd
years, so no statewide office and no regular legislative seat is on the 2026 ballot (the roster the state pages use,
state_ms.sqlite, carries the Governor's, Lieutenant Governor's and Attorney General's terms to January 2028). The
Secretary of State calls November 3, 2026 the "Federal and Judicial Election". Beside Congress (left to the federal
pages) it carries, as the Secretary's own list and sample ballot give them:
  * special elections: two House seats (Districts 70 and 77) and District Attorney, District 7;
  * the nonpartisan judicial elections: seats on the Court of Appeals (by district and position), and the chancery
    and circuit court seats (by district, place or subdistrict, as the ballot writes each).
The list names no Supreme Court seat and no State Senate seat for November, and it carries a heading "Candidates for
Mississippi Circuit Court Judge Special Election" with no candidate under it; the loader reports any such empty heading.

Sources, all the Secretary of State's own; the first two are the ones the federal loader (ballot/lists/ms.py) reads:
  * the Candidate Qualifying List ("All offices and candidates currently on file"), through its page's own Download
    CSV button (CandidateQualifying.csv). Its columns are Office, Candidate Name, Party, District, Place, Qualifying
    Period, Primary Election, General Election and Election; it has no contact columns at all, and only these are ever
    read, by heading: Office, Candidate Name, Party, District, Place, Election, Primary Election, General Election. The
    state rows are checked, heading by heading, against the tables on the page itself (only the Name, Party, District
    and Place columns of those tables are read). Only the kept columns of the state rows are cached, as JSON, with the
    CSV's SHA-256; the CSV itself is never saved. The list has no status column, so a candidate who withdrew or was
    removed may simply stop being listed; it lists no write-in candidates.
  * the SAMPLE Official Election Ballot for the November 3, 2026 Federal and Judicial Election (the PDF linked as
    "Sample Ballot" from the Elections & Voting page), read column by column as the federal loader reads it: a contest
    is its heading ("SPECIAL ELECTION" or "NONPARTISAN JUDICIAL ELECTION", the office, the district, "Vote for ONE"),
    its candidates (name, then the party word at the right of the column) and a closing "Write-in" line. Its names,
    party words and order are the ones stored; ballot_order is the position on this statewide sample. Every contest
    must be "Vote for ONE".
  * the Official Recapitulations of the March 10, 2026 party primaries (one PDF per party). They are read only to show
    that no state contest was on a party primary ballot: every contest in them must be federal (the federal loader's
    own reader stops on anything else), so no primary fields are stored for Mississippi's state races.

How the two lists are tied together. Each list row is placed in the one ballot contest of the same court or office
whose seat it names: the list writes some seats as district and place (7, 2) and some as a subdistrict (7-2), and the
ballot writes them either way too ("Chancery District 7-2", "Chancery District 7-1 Place 1"), so a seat is compared in
both readings and must fit exactly one contest. Candidates are then paired by name within the contest (the same family
name and a given name that fits, ballot.match.fits; the list sometimes writes the full given names where the ballot
prints a short form, Gwendolyn for Gwen). Every ballot candidate must be on the list. A list candidate who is not on
the sample ballot is not stored as a November candidate: the race note names them and the run reports them. A list
contest with no ballot contest would be stored from the list alone, without ballot positions, and reported.

Parties. The judicial contests are headed "NONPARTISAN JUDICIAL ELECTION" and print Nonpartisan beside every name: they
are stored as nonpartisan offices ("Nonpartisan office", party code N). The special elections are stored with the party
word the ballot prints (every candidate is printed "Independent"; for the district attorney the list gives no party),
and the race note says so.

Who holds each seat. The House seats come from state_ms.sqlite (the Open States roster the state pages use): the member
serving now for the district, if any; Districts 70 and 77 have none, and the race note says so. The roster carries no
judges and no district attorneys, so those holders are not shown. A candidate is marked as the incumbent only when the
name fits exactly one sitting member of the same chamber and district.

Places. county_ids are not stored: neither the list nor the ballot says which counties make up a judicial district,
and the state page does not use them for a state with no local races. sl_places carries each House district and each
judicial district by name.

The privacy rule: from the list, only office, district, place, name, party and election dates are read; from the
ballot, only contest headings, names and party words. Nothing else is printed, logged, cached or stored, and no photos,
ages, websites, biographies or money are stored in this phase.

Usage: python -m ballot.state_local_ms <database file> [cache folder]
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

if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ballot import pdftext
from ballot.common import CACHE, HERE, fold, name_parts, party_code
from ballot.lists import ms as fed
from ballot.match import fits
from states import net

STATE, NAME = "MS", "Mississippi"
GENERAL = "2026-11-03"
FED_FOLDER = os.path.join(CACHE, "ms")
ROSTER = os.path.join(HERE, "state_ms.sqlite")
LIST_FILE = "ms_2026_qualifying_list_state.json"
LIST_READ = ("Office", "Candidate Name", "Party", "District", "Place", "Election", "Primary Election", "General Election")
PAGE_READ = ("Name", "Party", "District", "Place")
NONPARTISAN = "Nonpartisan office"
SRC_LIST, SRC_BALLOT, SRC_ROSTER = "ms-sos-2026-sl-qualifying-list", "ms-sos-2026-sl-sample-ballot", "ms-openstates-roster"
SRC_RECAP = {"DEM": "ms-sos-2026-sl-primary-dem", "REP": "ms-sos-2026-sl-primary-rep"}

# the list's section headings: (pattern, kind); "Special Election" in a heading marks a special election
LIST_OFFICES = [
    (r"Candidates for United States (?:Senate|House of Representatives)", "federal"),
    (r"Candidates for Mississippi Supreme Court\b.*", "SC"),
    (r"Candidates for Mississippi Court of Appeals\b.*", "COA"),
    (r"Candidates for Mississippi Chancery Court Judge\b.*", "CH"),
    (r"Candidates for Mississippi Circuit Court Judge\b.*", "CC"),
    (r"Candidates for State Senate\b.*", "SS"),
    (r"Candidates for State House of Representatives\b.*", "SH"),
    (r"Candidates for District Attorney\b.*", "DA"),
]
KINDS = {  # kind -> (level, office_kind, office, partisan)
    "SC": ("court", "supreme_court", "Justice of the Supreme Court", 0),
    "COA": ("court", "court_of_appeals", "Judge of the Court of Appeals", 0),
    "CH": ("court", "chancery_court", "Chancery Court Judge", 0),
    "CC": ("court", "circuit_court", "Circuit Court Judge", 0),
    "SS": ("legislature", "state_senate", "State Senator", 1),
    "SH": ("legislature", "state_house", "State Representative", 1),
    "DA": ("court", "district_attorney", "District Attorney", 1),
}
JUDICIAL = {"SC", "COA", "CH", "CC"}
CHAMBER = {"SS": "Senate", "SH": "House"}
SEAT = r"(\d+(?:-\d+)?)"
BALLOT_CONTESTS = [  # (pattern on the heading without its first and last lines, kind); groups: district, place
    (r"For United States Senate", "federal"),
    (r"For US House of Representatives [1-4](?:st|nd|rd|th) Congressional District", "federal"),
    (r"For State House Of Rep (\d+) District (\d+)", "SH"),
    (r"For State Senate\D*?(\d+) District (\d+)", "SS"),
    (r"For District Attorney (\d+) District (\d+)", "DA"),
    (r"For Court of Appeals Judge District (\d+) Position (\d+)", "COA"),
    (r"For Supreme Court(?: Justice)? District (\d+) (?:Place|Position) (\d+)", "SC"),
    (rf"For Chancery Court (?:Judge|{SEAT}) (?:Chancery District|Chancery Court, District) {SEAT}(?: Place (\d+))?", "CH"),
    (rf"For Circuit Court (?:Judge|{SEAT}) (?:Circuit District|Circuit Court) {SEAT}(?: Place (\d+))?", "CC"),
]
PARTY_WORDS = {"Nonpartisan", "Independent", "Democrat", "Republican", "Libertarian", "Constitution", "Green", "Reform"}
SAME_PARTY = {"democratic": "democrat"}


def sha_of(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest() if path and os.path.exists(path) else ""


def day_of(path):
    return dt.datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d") if path and os.path.exists(path) else ""


def dnorm(text):
    """A district as a number or number-number, leading zeros dropped: '04' -> '4', '17-1' -> '17-1'."""
    t = (text or "").strip()
    if not t:
        return ""
    if not re.fullmatch(r"\d+(?:-\d+)?", t):
        raise SystemExit(f"{NAME}: a district written {t!r} could not be read")
    return "-".join(str(int(p)) for p in t.split("-"))


def ordinal(n):
    n = int(n)
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def readings(d, p):
    """Every way a seat can be written: (7, 2) is also 7-2; 7-1 place 1 is also district 7, place 1."""
    out = {(d, p)}
    if "-" in d:
        main, sub = d.split("-", 1)
        out.add((main, p or sub))
    elif p:
        out.add((f"{d}-{p}", ""))
    return out


def seat_words(d, p):
    return f"district {d}, place {p}" if p else f"district {d}"


def letters(name):
    """A name's letters and the spaces between its words, for telling whether two lists spell it alike (quotes, commas
    and full stops set aside)."""
    return " ".join(fold(name).split())


def join(*parts):
    return " ".join(p for p in parts if p) or None


def list_kind(office):
    for pattern, kind in LIST_OFFICES:
        if re.fullmatch(pattern, office):
            return kind
    raise SystemExit(f"{NAME}: the Candidate Qualifying List has a section this loader does not read: {office!r}")


# ---------------------------------------------------------------- the Candidate Qualifying List: allowed columns only

def page_sections(page):
    """{heading: [row dicts]} from the qualifying page's own tables, each table searched for only up to the next heading;
    only the Name, Party, District and Place columns are read."""
    marks = [(m.start(), fed.clean(m.group(0))) for m in re.finditer(r"Candidates for [^<]{3,160}", page)]
    out = {}
    for i, (at, heading) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(page)
        m = re.search(r"<table\b.*?</table>", page[at:end], re.S | re.I)
        rows = []
        if m:
            heads = [fed.clean(x) for x in re.findall(r"<th[^>]*>(.*?)</th>", m.group(0), re.S | re.I)]
            use = {i: h for i, h in enumerate(heads) if h in PAGE_READ}
            if "Name" not in use.values():
                raise SystemExit(f"{NAME}: the qualifying page's table under {heading!r} has no Name column")
            for tr in re.findall(r"<tr.*?</tr>", m.group(0), re.S | re.I):
                cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S | re.I)
                got = {h: fed.clean(cells[i]) for i, h in use.items() if i < len(cells)}
                if got.get("Name"):
                    rows.append(got)
        out[heading] = rows
    return out


def read_list(path, refresh, say):
    """The state rows of the qualifying list's CSV (kept columns only), checked against the page; read afresh after two
    days. The federal rows are counted and left to ballot/lists/ms.py."""
    if not refresh and fed.fresh(path, 2):
        return json.load(open(path, encoding="utf-8"))
    net.patient_lookups()
    try:
        page = fed.fetch(fed.QUALIFYING, accept="text/html").decode("utf-8", "replace")
        form = {n: H.unescape(v) for n, v in re.findall(r'<input type="hidden" name="([^"]+)" id="[^"]+" value="([^"]*)"', page)}
        button = re.search(r'<input type="submit" name="([^"]+)" value="(Download CSV)"', page)
        if not form.get("__VIEWSTATE") or not button:
            raise SystemExit(f"{NAME}: the qualifying page no longer has its Download CSV button")
        form[button.group(1)] = button.group(2)
        time.sleep(1.5)
        raw = fed.fetch(fed.QUALIFYING, data=form, accept="text/csv")
    except OSError as e:                                   # URLError and HTTPError are OSErrors
        if os.path.exists(path):
            say(f"      could not read the qualifying list afresh ({type(e).__name__}); using the copy read earlier")
            return json.load(open(path, encoding="utf-8"))
        raise SystemExit(f"{NAME}: the qualifying list could not be read ({type(e).__name__})")
    text = raw.decode("utf-8-sig", "replace")
    if not text.startswith("Office,"):
        raise SystemExit(f"{NAME}: the qualifying list's Download CSV did not give a CSV file")
    reader = csv.reader(io.StringIO(text))
    header = [h.strip() for h in next(reader)]
    idx = {h: i for i, h in enumerate(header) if h in LIST_READ}          # every other column is never read
    missing = [c for c in LIST_READ if c not in idx]
    if missing:
        raise SystemExit(f"{NAME}: the qualifying list's CSV has no {missing} column")
    state, empty, total, federal = [], [], 0, 0
    for n, cells in enumerate(reader, start=2):
        if not any(c.strip() for c in cells):
            continue
        total += 1
        r = {k: fed.clean(cells[i]) if i < len(cells) else "" for k, i in idx.items()}
        kind = list_kind(r["Office"])
        if kind == "federal":
            federal += 1
            continue
        if not r["Candidate Name"]:
            empty.append(r["Office"])
            continue
        state.append(r)
    # control: the tables on the page list the same state candidates, heading by heading
    tables = page_sections(page)
    for heading in sorted({r["Office"] for r in state}):
        rows = tables.get(heading)
        if rows is None:
            raise SystemExit(f"{NAME}: the qualifying page has no section headed {heading!r}")
        cols = [c for c in PAGE_READ if rows and c in rows[0]]
        shown = sorted(tuple(x.get(c, "") for c in cols) for x in rows)
        read = sorted(tuple(r[{"Name": "Candidate Name"}.get(c, c)] for c in cols) for r in state if r["Office"] == heading)
        if shown != read:
            raise SystemExit(f"{NAME}: the qualifying list's CSV and the table on its page list different candidates under {heading!r}")
    for heading in empty:
        if tables.get(heading):
            raise SystemExit(f"{NAME}: the CSV has no candidate under {heading!r}, the page lists some")
    kept = {"url": fed.QUALIFYING, "page": fed.LIST_PAGE, "csv": "CandidateQualifying.csv (the page's Download CSV button)",
            "columns_read": list(LIST_READ), "sha256": hashlib.sha256(raw).hexdigest(), "rows_in_file": total,
            "federal_rows": federal, "empty_headings": empty, "read": time.strftime("%Y-%m-%d"), "state": state}
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    json.dump(kept, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    say(f"      qualifying list: {len(state)} state candidates, {federal} federal rows, {total} rows in all")
    return kept


# ---------------------------------------------------------------- the sample ballot

def contest_of(lines):
    """A contest heading on the sample ballot -> {kind, district, place, special, judicial, heading}; None for the
    ballot's title block."""
    t = " ".join(lines)
    if t.startswith("SAMPLE Official Election Ballot"):
        return None
    special = judicial = False
    if t.startswith("SPECIAL ELECTION "):
        special, t = True, t[len("SPECIAL ELECTION "):]
    elif t.startswith("NONPARTISAN JUDICIAL ELECTION "):
        judicial, t = True, t[len("NONPARTISAN JUDICIAL ELECTION "):]
    if not t.endswith(" Vote for ONE"):
        raise SystemExit(f"{NAME}: a contest on the sample ballot is not 'Vote for ONE': {' '.join(lines)!r}")
    t = t[:-len(" Vote for ONE")]
    for pattern, kind in BALLOT_CONTESTS:
        m = re.fullmatch(pattern, t, re.I)
        if not m:
            continue
        if kind == "federal":
            return {"kind": "federal", "heading": t}
        g = [x for x in m.groups()]
        if kind in ("CH", "CC"):
            first, d, p = (dnorm(g[0]) if g[0] else ""), dnorm(g[1]), (str(int(g[2])) if g[2] else "")
            if first and first not in (d, d.split("-")[0]):
                raise SystemExit(f"{NAME}: the sample ballot's contest {t!r} names two different districts")
        elif kind in ("SH", "SS", "DA"):
            d, p = dnorm(g[0]), ""
            if dnorm(g[1]) != d:
                raise SystemExit(f"{NAME}: the sample ballot's contest {t!r} names two different districts")
        else:
            d, p = dnorm(g[0]), str(int(g[1]))
        if (kind in JUDICIAL) != judicial:
            raise SystemExit(f"{NAME}: the sample ballot's contest {t!r} is {'' if judicial else 'not '}headed as a nonpartisan judicial election")
        if kind in ("SH", "SS", "DA") and not special:
            raise SystemExit(f"{NAME}: the sample ballot's contest {t!r} is not headed as a special election; a regular election "
                             "for this office is not expected in 2026")
        return {"kind": kind, "district": d, "place": p, "special": 1 if special else 0, "heading": t}
    raise SystemExit(f"{NAME}: a contest heading on the sample ballot that this loader does not read: {t!r}")


def ballot_contests(path):
    """Every contest on the sample ballot, in ballot order (page by page, left column then right): [contest dict with
    'candidates': [(name, party word)]]."""
    pdf = pdftext.PDF(open(path, "rb").read())
    out, first = [], ""
    for n, (page, res) in enumerate(pdf.pages(), start=1):
        box = [pdf.get(v) for v in (pdf.get(page.get("MediaBox")) or [0, 0, 612, 792])]
        mid = (float(box[0]) + float(box[2])) / 2
        runs = pdftext.page_runs(pdf, page, res)
        if n == 1:
            first = " ".join(pdftext.join(rs) for _y, rs in fed.lines_of(runs))
        for side in (False, True):
            col = [r for r in runs if (r[0] >= mid) == side and r[3].strip()]
            heading, contest, preamble = [], None, False
            for _y, rs in fed.lines_of(col):
                text, size = pdftext.join(rs), max(r[2] for r in rs)
                if text == "Write-in":
                    if contest is None:
                        raise SystemExit(f"{NAME}: page {n} of the sample ballot has a Write-in line outside a contest")
                    contest["write_in_line"] = True
                    heading, contest, preamble = [], None, False
                elif size >= 10.5:
                    if contest is not None:
                        raise SystemExit(f"{NAME}: the contest {contest['heading']!r} on the sample ballot has no Write-in line")
                    if preamble:
                        heading, preamble = [], False
                    heading.append(text)
                elif 8.5 <= size < 10.5:
                    if preamble:
                        continue                                          # the voting instructions under the title
                    if contest is None:
                        c = contest_of(heading)
                        heading = []
                        if c is None:
                            preamble = True
                            continue
                        contest = dict(c, candidates=[], page=n)
                        out.append(contest)
                    left = min(r[0] for r in rs)
                    name = pdftext.join([r for r in rs if r[0] < left + 150])
                    party = pdftext.join([r for r in rs if r[0] >= left + 150])
                    if not name or not party:
                        raise SystemExit(f"{NAME}: a line of the sample ballot's contest {contest['heading']!r} has no name or no party")
                    contest["candidates"].append((name, party))
            left_over = " ".join(heading)
            if contest is not None:
                raise SystemExit(f"{NAME}: the contest {contest['heading']!r} on page {n} of the sample ballot has no Write-in line")
            if left_over and left_over not in ("TURN BALLOT OVER TO CONTINUE VOTING", "END OF BALLOT"):
                raise SystemExit(f"{NAME}: page {n} of the sample ballot ends a column with a heading and no candidates: {left_over!r}")
    if "Federal and Judicial Election" not in first or "November 3, 2026" not in first:
        raise SystemExit(f"{NAME}: the sample ballot read is not the November 3, 2026 Federal and Judicial Election's")
    return out


# ---------------------------------------------------------------- files

def fresh_in(folders, name, days):
    for folder in folders:
        p = os.path.join(folder, name)
        if fed.fresh(p, days):
            return p
    return None


def links_of(cache, say):
    """The sample ballot's and the recapitulations' addresses: the federal loader's record of them when fresh, else
    looked for again on the Secretary's pages."""
    p = fresh_in((cache, FED_FOLDER), "ms_2026_links.json", 7)
    if p:
        return json.load(open(p, encoding="utf-8"))
    links = fed.find_links(say)
    json.dump(links, open(os.path.join(cache, "ms_2026_links.json"), "w", encoding="utf-8"), indent=1)
    return links


def pdf_file(cache, name, url, days, what):
    """A PDF the federal loader keeps in ballot_cache/ms (used as it is when fresh), else fetched into the cache folder."""
    return fresh_in((cache, FED_FOLDER), name, days) or fed.get_pdf(url, os.path.join(cache, name), days, what)


# ---------------------------------------------------------------- the roster

def roster():
    """{(chamber, district): [{id, name, party, given, family}]} for the members serving now; names, parties and
    districts only."""
    out = collections.defaultdict(list)
    if not os.path.exists(ROSTER):
        return out, 0
    con = sqlite3.connect(f"file:{ROSTER}?mode=ro", uri=True)
    n = 0
    for bid, full, first, last, party, chamber, district in con.execute(
            "SELECT bioguide_id, official_full, first_name, last_name, party, chamber, district FROM legislators WHERE is_current = 1"):
        n += 1
        out[(chamber, dnorm(str(district)))].append({"id": bid, "name": full or f"{first} {last}", "party": party,
                                                    "parts": ([w for w in fold(first).split()], fold(last))})
    con.close()
    return out, n


PARTY_WORD = {"R": "Republican", "D": "Democratic", "I": "Independent"}


def one_fit(name, people):
    parts = name_parts(name)
    hits = [p for p in people if fits(parts, p["parts"])]
    return hits[0] if len(hits) == 1 else None


# ---------------------------------------------------------------- load

def race_for(kind, d, p, special):
    level, office_kind, office, partisan = KINDS[kind]
    main = d.split("-")[0]
    if kind in ("SH", "SS"):
        rid = f"2026-{STATE}-{kind}{d}"
        jur, jid = f"{'House' if kind == 'SH' else 'Senate'} District {d}", d
        place = ("house" if kind == "SH" else "senate", f"{STATE}-{d}", jur)
        seat = None
    elif kind == "DA":
        rid, jur, jid, seat = f"2026-{STATE}-DA{d}", f"District Attorney District {d}", f"{STATE}-DA{d}", None
        place = ("judicial", jid, jur)
    elif kind in ("COA", "SC"):
        court = "Court of Appeals" if kind == "COA" else "Supreme Court"
        rid, jur, jid, seat = f"2026-{STATE}-{kind}{d}-P{p}", f"{court} District {d}", f"{STATE}-{kind}{d}", f"Position {p}"
        place = ("judicial", jid, jur)
    else:
        court = "Chancery" if kind == "CH" else "Circuit"
        rid = f"2026-{STATE}-{kind}{d}" + (f"-P{p}" if p else "")
        jur, jid, seat = f"{court} Court District {main}", f"{STATE}-{kind}{main}", (f"Place {p}" if p else None)
        place = ("judicial", jid, jur)
    return {"race_id": rid, "level": level, "office_kind": office_kind, "office": office, "jurisdiction": jur,
            "jurisdiction_id": jid, "county_ids": None, "district": d, "seat": seat, "special": special,
            "partisan": partisan, "holder_id": None, "holder_name": None, "holder_party": None, "note": None,
            "kind": kind, "place": place}


def load(db_path, say=print, cache=None, refresh=False):
    cache = cache or FED_FOLDER
    os.makedirs(cache, exist_ok=True)
    net.patient_lookups()
    problems = []

    lpath = os.path.join(cache, LIST_FILE)
    listed = read_list(lpath, refresh, say)
    links = links_of(cache, say)
    spath = pdf_file(cache, "ms_2026_general_sample_ballot.pdf", links["sample"], 7, "sample ballot")
    rpaths = {code: pdf_file(cache, f"ms_2026_primary_{code.lower()}_recapitulation.pdf", links[code], 90, f"{code} primary recapitulation")
              for code in fed.RECAP_LABEL}

    # the ballot's contests; the federal ones are the federal loader's
    contests = ballot_contests(spath)
    fed_contests = [c for c in contests if c["kind"] == "federal"]
    contests = [c for c in contests if c["kind"] != "federal"]
    if len(fed_contests) != 5:
        problems.append(f"the sample ballot has {len(fed_contests)} federal contests, not 5 (the Senate and four House seats)")
    seen = collections.Counter((c["kind"], c["district"], c["place"]) for c in contests)
    twice = [k for k, v in seen.items() if v > 1]
    if twice:
        raise SystemExit(f"{NAME}: the sample ballot prints these seats twice: {twice}")

    # every list row placed in the one ballot contest whose seat it names
    for r in listed["state"]:
        if r["Election"] != "November 3, 2026" or r["Primary Election"] or r["General Election"]:
            raise SystemExit(f"{NAME}: a state row of the qualifying list is dated {r['Election']!r} / {r['Primary Election']!r} / "
                             f"{r['General Election']!r}; November 3, 2026 was expected")
    assigned = collections.defaultdict(list)          # contest index -> list rows
    list_only = collections.defaultdict(list)         # (kind, district, place) -> list rows with no ballot contest
    for r in listed["state"]:
        kind, special = list_kind(r["Office"]), 1 if "Special Election" in r["Office"] else 0
        d, p = dnorm(r["District"]), (str(int(r["Place"])) if r["Place"] else "")
        if not d:
            raise SystemExit(f"{NAME}: a row under {r['Office']!r} names no district")
        hits = [i for i, c in enumerate(contests) if c["kind"] == kind and readings(c["district"], c["place"]) & readings(d, p)]
        if len(hits) > 1:
            raise SystemExit(f"{NAME}: the list's {kind} seat {seat_words(d, p)} fits {len(hits)} contests on the sample ballot")
        if hits:
            c = contests[hits[0]]
            if c.get("special", 0) != special and kind not in JUDICIAL:
                problems.append(f"{kind} {seat_words(d, p)}: the list and the ballot disagree about whether it is a special election")
            assigned[hits[0]].append(dict(r, d=d, p=p))
        else:
            list_only[(kind, d, p, special)].append(dict(r, d=d, p=p))

    members, n_members = roster()
    races, cands, places = {}, [], {}
    left_off, respelled, stored_ballot = [], 0, 0
    for i, c in enumerate(contests):
        race = race_for(c["kind"], c["district"], c["place"], c.get("special", 0))
        rid = race["race_id"]
        rows = assigned.get(i, [])
        if not c["candidates"]:
            problems.append(f"{rid}: a contest on the sample ballot with no candidate")
        # pair ballot names with list rows
        free = list(range(len(rows)))
        pairs = {}
        for strict in (True, False):
            for j, (name, _party) in enumerate(c["candidates"]):
                if j in pairs:
                    continue
                parts = name_parts(name)
                hits = [k for k in free if fits(parts, name_parts(rows[k]["Candidate Name"]))]
                if not strict and not hits:
                    fam = [k for k in free if name_parts(rows[k]["Candidate Name"])[1] == parts[1]]
                    same = [k for k in range(len(rows)) if name_parts(rows[k]["Candidate Name"])[1] == parts[1]]
                    hits = fam if len(same) == 1 else []
                if len(hits) == 1:
                    pairs[j] = hits[0]
                    free.remove(hits[0])
        note_race = []
        if c["kind"] in JUDICIAL:
            note_race.append("The ballot heads this contest \"Nonpartisan Judicial Election\" and prints Nonpartisan beside every "
                             "name. The roster used here carries no judges, so today's judge is not named.")
        forms = sorted({(r["d"], r["p"]) for r in rows} - {(c["district"], c["place"])})
        if forms:
            note_race.append("The ballot writes this seat as " + seat_words(c["district"], c["place"]) + "; the Secretary of State's "
                             "Candidate Qualifying List writes it as " + " and as ".join(seat_words(d, p) for d, p in
                             sorted({(r["d"], r["p"]) for r in rows})) + ".")
        list_parties = {r["Party"] for r in rows}
        for pos, (name, word) in enumerate(c["candidates"], start=1):
            k = pairs.get(pos - 1)
            note = None
            if k is None:
                problems.append(f"{rid}: {name} is on the sample ballot but not on the Candidate Qualifying List")
                note = "Not found on the Secretary of State's Candidate Qualifying List."
            else:
                lr = rows[k]
                if letters(lr["Candidate Name"]) != letters(name):
                    note = f"The Candidate Qualifying List writes the name as {lr['Candidate Name'].rstrip('.')}."
                    respelled += 1
                lp = lr["Party"]
                if c["kind"] in JUDICIAL and lp:
                    problems.append(f"{rid}: the list gives {name} the party {lp!r} in a nonpartisan contest")
                if c["kind"] not in JUDICIAL and lp and SAME_PARTY.get(lp.lower(), lp.lower()) != word.lower():
                    problems.append(f"{rid}: the list gives {name} the party {lp!r}, the ballot prints {word!r}")
            if word not in PARTY_WORDS:
                problems.append(f"{rid}: the ballot prints the party word {word!r}, which this loader has not seen before")
            if c["kind"] in JUDICIAL:
                if word != "Nonpartisan":
                    problems.append(f"{rid}: {name} is printed as {word!r} in a nonpartisan judicial contest")
                party, pc = NONPARTISAN, "N"
            else:
                party, pc = word, party_code(word)
            who = None
            if c["kind"] in CHAMBER:
                who = one_fit(name, members.get((CHAMBER[c["kind"]], c["district"]), []))
            cands.append((rid, "general", GENERAL, name, party, pc, pos, 1 if who else 0, 0, None, None, None,
                          who["id"] if who else None, SRC_BALLOT, note))
            stored_ballot += 1
        gone = [rows[k]["Candidate Name"] for k in free]
        for g in gone:
            left_off.append(f"{rid}: {g}")
        if gone:
            note_race.append("The Candidate Qualifying List also names " + " and ".join(gone) + " for this seat; "
                             + ("that name is" if len(gone) == 1 else "those names are") + " not on the Secretary of State's "
                             "sample ballot, so " + ("it is" if len(gone) == 1 else "they are") + " not listed here.")
        if c["kind"] in CHAMBER:
            sitting = members.get((CHAMBER[c["kind"]], c["district"]), [])
            if len(sitting) == 1:
                race.update(holder_id=sitting[0]["id"], holder_name=sitting[0]["name"],
                            holder_party=PARTY_WORD.get(sitting[0]["party"], sitting[0]["party"]))
            note_race.insert(0, "A special election, as the ballot and the list head it. "
                                + ("Every candidate is printed as Independent on the Secretary of State's sample ballot and on "
                                   "the Candidate Qualifying List. " if {w for _n, w in c["candidates"]} == {"Independent"}
                                   and list_parties == {"Independent"} else "")
                                + ("The Open States roster used by the state pages lists no member serving for this district now. "
                                   if not sitting else "")
                                + "The March 10 party primaries' official results carry no contest for this seat.")
        elif c["kind"] == "DA":
            note_race.insert(0, "A special election, as the ballot and the list head it. "
                                + ("Every candidate is printed as Independent on the Secretary of State's sample ballot; the "
                                   "Candidate Qualifying List gives no party. " if {w for _n, w in c["candidates"]} == {"Independent"}
                                   and list_parties == {""} else "")
                                + "The roster used here carries no district attorneys, so today's holder is not named.")
        race["note"] = " ".join(note_race) or None
        races[rid] = race
        places[race["place"][:2]] = race["place"]

    # a list contest with no ballot contest: stored from the list alone, and reported
    for (kind, d, p, special), rows in sorted(list_only.items()):
        race = race_for(kind, d, p, special)
        rid = race["race_id"]
        if rid in races:
            raise SystemExit(f"{NAME}: {rid} is both on the ballot and a list-only seat")
        problems.append(f"{rid}: on the Candidate Qualifying List ({len(rows)} candidates) but not on the sample ballot; stored from the list")
        race["note"] = ("On the Secretary of State's Candidate Qualifying List but not on its sample ballot, so there are no ballot "
                        "positions. Names as the list writes them.")
        for r in rows:
            if kind in JUDICIAL:
                party, pc = NONPARTISAN, "N"
            else:
                party, pc = r["Party"] or None, party_code(r["Party"])
            cands.append((rid, "general", GENERAL, r["Candidate Name"], party, pc, None, 0, 0, None, None, None, None, SRC_LIST, None))
        races[rid] = race
        places[race["place"][:2]] = race["place"]

    # the March 10 primaries: federal contests only
    recap_contests = {}
    for code, path in rpaths.items():
        try:
            recap_contests[code] = len(fed.recapitulation(path, fed.RECAP_PARTY[code]))
        except SystemExit as e:
            problems.append(f"the {code} primary recapitulation could not be confirmed as federal only: {e}")
            recap_contests[code] = None

    # CHECKS
    list_rows = len(listed["state"])
    placed = sum(len(v) for v in assigned.values()) + sum(len(v) for v in list_only.values())
    if placed != list_rows:
        problems.append(f"{list_rows} state rows on the list, {placed} placed in a contest")
    paired = sum(1 for c in cands if c[1] == "general" and c[13] == SRC_BALLOT and not (c[14] or "").startswith("Not found"))
    if paired + len(left_off) + sum(len(v) for v in list_only.values()) != list_rows:
        problems.append(f"list rows: {list_rows}; paired with the ballot {paired}, not on the ballot {len(left_off)}, "
                        f"list-only contests {sum(len(v) for v in list_only.values())}")
    for heading in listed.get("empty_headings", []):
        problems.append(f"the list has a section headed {heading!r} with no candidate under it")
    for rid in left_off:
        problems.append(f"on the Candidate Qualifying List, not on the sample ballot (not stored): {rid}")

    by_kind = collections.Counter(r["office_kind"] + ("_special" if r["special"] else "") for r in races.values())
    general = sum(1 for c in cands if c[1] == "general")
    race_rows = [(r["race_id"], STATE, r["level"], r["office_kind"], r["office"], r["jurisdiction"], r["jurisdiction_id"],
                  r["county_ids"], r["district"], r["seat"], r["special"], r["partisan"], r["holder_id"], r["holder_name"],
                  r["holder_party"], GENERAL, r["note"]) for r in races.values()]
    place_rows = [(kind, pid, pname, None, SRC_BALLOT) for (kind, pid), (_k, _i, pname) in sorted(places.items())]
    recap_note = ", ".join(f"{code} {n}" for code, n in recap_contests.items() if n is not None)
    sources = [
        (SRC_LIST, STATE, "official candidate list", "Mississippi Secretary of State",
         "Candidate Qualifying List: state offices (CandidateQualifying.csv)", fed.QUALIFYING, "", listed["read"],
         listed["sha256"], list_rows,
         f"Shown on {fed.LIST_PAGE}, \"All offices and candidates currently on file\"; read through the page's own Download CSV "
         "button and checked, heading by heading, against the tables on the page. Only Office, Candidate Name, Party, District, "
         "Place and the election dates are read (the file has no contact columns). The SHA-256 is the CSV's as downloaded; only "
         "the kept columns are cached. Used to confirm the sample ballot's candidates seat by seat. The list has no status "
         "column (a candidate who withdrew may simply stop being listed) and lists no write-in candidates"
         + (f"; candidates it names who are not on the sample ballot are not stored: {'; '.join(left_off)}" if left_off else "")
         + (f"; it has a heading with no candidate under it: {'; '.join(listed['empty_headings'])}" if listed.get("empty_headings") else "")
         + "."),
        (SRC_BALLOT, STATE, "official sample ballot", "Mississippi Secretary of State",
         "SAMPLE Official Election Ballot, State of Mississippi: Federal and Judicial Election, Tuesday, November 3, 2026",
         links["sample"], fed.created(spath), day_of(spath), sha_of(spath), stored_ballot,
         f"Linked as \"Sample Ballot\" from {fed.ELECTIONS_PAGE}. The state contests only (the federal ones are the federal "
         "pages'), read column by column: the names, party words and order are the ballot's own, and ballot_order is the "
         "position on this statewide sample. Every contest leaves a Write-in line; no declared write-in candidates are listed. "
         f"{len(contests)} state contests: special elections for two House seats and a district attorney, and the nonpartisan "
         "judicial elections (Court of Appeals, chancery and circuit courts)."),
    ]
    for code, path in rpaths.items():
        sources.append((SRC_RECAP[code], STATE, "official results", "Mississippi Secretary of State",
                        f"{fed.RECAP_LABEL[code]}: Official Recapitulation, Federal Primary Election, March 10, 2026", links[code],
                        fed.created(path), day_of(path), sha_of(path), 0,
                        "Read only to confirm that no state contest was on the March 10 party primary ballot: every contest in it is "
                        f"federal ({recap_contests[code]} contests). No primary fields are stored for Mississippi's state races."
                        if recap_contests[code] is not None else "Could not be confirmed as federal only; see the run's CHECK lines."))
    sources.append((SRC_ROSTER, STATE, "roster", "Open States (people project, CC0)",
                    "Mississippi legislators serving now (state_ms.sqlite, from the Open States people project)",
                    "https://github.com/openstates/people", "", day_of(ROSTER), "", n_members,
                    "Used only to say who holds each House seat on the ballot today and to mark incumbents: names, parties and "
                    "districts. Not an official record. It lists no member serving now for House Districts 70 and 77."
                    if not any(r["holder_name"] for r in races.values() if r["kind"] in CHAMBER) else
                    "Used only to say who holds each legislative seat on the ballot today and to mark incumbents: names, parties "
                    "and districts. Not an official record."))

    con = sqlite3.connect(db_path)
    try:
        con.executescript(SCHEMA)
        with con:
            con.execute("DELETE FROM sl_candidates WHERE race_id IN (SELECT race_id FROM sl_races WHERE state = ?) OR race_id LIKE ?",
                        (STATE, f"2026-{STATE}-%"))
            con.execute("DELETE FROM sl_races WHERE state = ?", (STATE,))
            con.execute("DELETE FROM sl_sources WHERE state = ?", (STATE,))
            con.execute("DELETE FROM sl_places WHERE source_id LIKE 'ms-%'")
            con.executemany("INSERT INTO sl_races VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", race_rows)
            con.executemany("INSERT INTO sl_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", cands)
            con.executemany("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", sources)
            con.executemany("INSERT INTO sl_places VALUES (?,?,?,?,?)", place_rows)
    finally:
        con.close()

    counts = ", ".join(f"{k} {v}" for k, v in sorted(by_kind.items()))
    say(f"    {NAME}: {len(races)} state races on the November ballot ({counts}), {general} candidates in the sample ballot's "
        f"order (0 declared write-ins, {respelled} names the list writes differently); no statewide office and no regular "
        f"legislative seat (elected in odd years); no state primary (the March 10 recapitulations hold federal contests only: "
        f"{recap_note}); {sum(1 for c in cands if c[7])} incumbents matched")
    for p in problems:
        say(f"      CHECK {p}")
    return {"races": len(races), "candidates": general, "by_kind": dict(by_kind), "problems": problems, "left_off": left_off,
            "list_rows": list_rows, "respelled": respelled, "recap_contests": recap_contests}


SCHEMA = """
CREATE TABLE IF NOT EXISTS sl_races (race_id TEXT PRIMARY KEY, state TEXT NOT NULL, level TEXT NOT NULL, office_kind TEXT NOT NULL, office TEXT NOT NULL, jurisdiction TEXT, jurisdiction_id TEXT, county_ids TEXT, district TEXT, seat TEXT, special INTEGER NOT NULL DEFAULT 0, partisan INTEGER NOT NULL, holder_id TEXT, holder_name TEXT, holder_party TEXT, election_date TEXT NOT NULL, note TEXT);
CREATE TABLE IF NOT EXISTS sl_candidates (race_id TEXT NOT NULL, election TEXT NOT NULL, election_date TEXT, name TEXT NOT NULL, party TEXT, party_code TEXT, ballot_order INTEGER, incumbent INTEGER NOT NULL DEFAULT 0, write_in INTEGER NOT NULL DEFAULT 0, votes INTEGER, pct REAL, outcome TEXT, state_member_id TEXT, source_id TEXT, note TEXT, PRIMARY KEY (race_id, election, name));
CREATE TABLE IF NOT EXISTS sl_sources (source_id TEXT PRIMARY KEY, state TEXT, kind TEXT, agency TEXT, title TEXT, url TEXT, published TEXT, fetched TEXT, sha256 TEXT, rows INTEGER, note TEXT);
CREATE TABLE IF NOT EXISTS sl_places (kind TEXT NOT NULL, id TEXT NOT NULL, name TEXT NOT NULL, county_ids TEXT, source_id TEXT, PRIMARY KEY (kind, id));
"""


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("usage: python -m ballot.state_local_ms <database> [cache folder]")
    load(sys.argv[1], cache=sys.argv[2] if len(sys.argv) > 2 else None)
