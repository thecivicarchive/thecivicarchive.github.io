"""
Oklahoma: the State Election Board's own lists, read in four pieces.

  The November ballot: the Board's "NOVEMBER / 2026 List of Elections" (hosting.okelections.us/electionlist.html, the
  page oklahoma.gov/elections/elections-results/next-election.html links as "November 3 General Election"), an HTML
  page that lists, county by county for all 77 counties, every office on that county's November 3 ballot and under
  it each candidate as "NAME, PARTY". The U.S. Senator and U.S. Representative races are taken from it. A district
  that spans several counties is listed once per county, and every county's list must agree; a race whose counties
  disagree is left out and named. The list's order is kept as the ballot order: it follows the Board's public drawing
  of July 8, 2026 (Republican, Democratic, Libertarian, then independent candidates in lot order). The page carries
  names, parties and offices only; it is cached whole. The same address is reused for each election, so a copy whose
  title is not the November 2026 list is refused and the cached copy kept.

  The primaries: the Board's "Candidates for Office 2026" (the 2026 Candidate List Book, a PDF linked from
  oklahoma.gov/elections/candidates/2026-candidate-filing-information.html), every candidate who filed April 1-3,
  2026, as compiled at 5 p.m. on April 3, grouped by office, district and party, read with ballot/pdftext.py. Each
  entry is one line of fixed-width type: the filing number, the name, and the candidate's city. Only the filing
  number and the name columns are ever read (by character position, the type being 6 points to a character); the
  city is never read or kept. A long name wraps onto a second line in the name column, which is joined.

  Withdrawals: the Board's "2026 Candidate Withdrawals" page (columns Number, Name, Office, Date), matched to the book
  by filing number. A candidate who withdrew before the June 16 primary was not on its ballot and is left out; one
  who withdrew after it is kept in the primary field, with a note. Contests of candidacy: the Board's "2026 Contests
  of Candidacy" page is read only to make sure none concerns a federal office (a contest for one stops the loader).

A party primary is a field when two or more of the party's candidates were on its June 16 ballot. The nominee is the
party's candidate on the November list, and every November candidate of a party must be one of that party's filers.
The official results of the June 16 primary and the August 25 runoff are published only on the Board's results site,
results.okelections.us, which answers scripts with 403 Forbidden; so the fields carry no votes (the page says who won
comes from the candidate list), and which fields went to the August 25 runoff is not read. The runoff is its own
election (runoff-REP, runoff-DEM, 2026-08-25) once the results files are here.

Names are printed in capitals in both lists; the page shows them in ordinary capitals (a sitting member with the
roster's own capitals where the list's words are the roster's) and says so. Parties are printed in full and shown
in ordinary capitals: REPUBLICAN Republican, DEMOCRAT Democrat, LIBERTARIAN Libertarian, INDEPENDENT Independent.
"""

import html as H
import json
import os
import re
import sqlite3
import time
from datetime import datetime

from ballot.common import HERE, fold, house_id, name_parts, party_code, record_source, senate_id
from ballot.lists.tx import proper
from ballot.pdftext import PDF, join, rows as pdf_rows
from states import net

LIST_URL = "https://hosting.okelections.us/electionlist.html"
BOOK_URL = ("https://oklahoma.gov/content/dam/ok/en/elections/candidate-filing-archives/2026-candidate-filing-archives/"
            "2026-candidate-list-book.pdf")
WITHDRAWALS_URL = "https://oklahoma.gov/elections/candidates/2026-candidate-filing-information/2026-candidate-withdrawals.html"
CONTESTS_URL = "https://oklahoma.gov/elections/candidates/2026-candidate-filing-information/2026-contests-of-candidacy.html"
RESULTS_URL = "https://results.okelections.us/OKER/?elecDate=20260616"
PRIMARY, RUNOFF = "2026-06-16", "2026-08-25"
PARTIES = {"REPUBLICAN": "Republican", "DEMOCRAT": "Democrat", "LIBERTARIAN": "Libertarian", "INDEPENDENT": "Independent"}
CODES = {"Republican": "REP", "Democrat": "DEM", "Libertarian": "LIB"}          # independents are not in a primary
FEDERAL_OFFICE = re.compile(r"\b(UNITED STATES|U\.\s?S\.)\s+(SENATOR|REPRESENTATIVE)\b", re.I)
LEFT, CW = 72.0, 6.0                          # the book's left margin and its fixed-width type, points per character
NAME_COLS = (7, 30)                           # filing number in columns 0-4, the name in 7-29; the city after is never read
CAPS = "Oklahoma's list prints names in capitals; they are shown here in ordinary capitals."
CAPS_BOOK = "Oklahoma's candidate list prints names in capitals; they are shown here in ordinary capitals."


def text(cell):
    return re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", cell)).replace("\xa0", " ")).strip()


def fetch_page(url, path, max_age_days, must=None, say=print):
    """A page kept on disk; refreshed when older than max_age_days, and never replaced by a copy lacking `must`."""
    fresh = os.path.exists(path) and time.time() - os.path.getmtime(path) < max_age_days * 86400
    if not fresh:
        try:
            page = net.get(url, accept="text/html").decode("utf-8", "replace")
        except Exception as e:  # noqa: BLE001
            if not os.path.exists(path):
                raise
            say(f"      could not refresh {os.path.basename(path)} ({e}); using the copy on disk")
            page = None
        if page is not None and must and must not in page:
            if not os.path.exists(path):
                raise SystemExit(f"Oklahoma: {url} is no longer the page this loader reads (no {must!r})")
            say(f"      {url} no longer shows {must!r}; using the copy on disk")
            page = None
        if page is not None:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8", newline="") as fh:
                fh.write(page)
            time.sleep(1.0)
    return open(path, encoding="utf-8").read()


def modified(page):
    m = re.search(r"Last Modified on\s*<span>([A-Z][a-z]{2} \d{1,2}, \d{4})</span>", page)
    return datetime.strptime(m.group(1), "%b %d, %Y").strftime("%Y-%m-%d") if m else ""


def race_of(heading):
    h = re.sub(r"\s+", " ", heading).strip().upper()
    if h == "UNITED STATES SENATOR":
        return senate_id("OK", 2)
    m = re.fullmatch(r"UNITED STATES REPRESENTATIVE - DISTRICT (\d+)", h)
    if m:
        return house_id("OK", int(m.group(1)))
    if FEDERAL_OFFICE.search(h):
        raise SystemExit(f"Oklahoma: a federal office on the List of Elections that is not read ({heading!r})")
    return None


def november(page):
    """{race: [(name, party)]} from every county's list, and the races whose counties disagree."""
    counties = re.findall(r"<option value=\"#(\d+)\">", page)
    parts = re.split(r"<A NAME=(\d+)>([^<]*)</A>", page)
    listed, seen = {}, 0
    for k in range(1, len(parts), 3):
        num, county, body = parts[k], parts[k + 1].strip(), parts[k + 2]
        if num == "00":
            continue
        seen += 1
        race = None
        for m in re.finditer(r"<TD WIDTH=(\d+)>(.*?)</TD>", body, re.S):
            width, t = m.group(1), text(m.group(2))
            if width == "990":                                   # a section: state, congressional, legislative officers
                race = None
            elif width == "980":                                 # an office
                race = race_of(t)
            elif width == "970" and race:
                name, _, label = t.rpartition(",")
                label = label.strip().upper()
                if not name or label not in PARTIES:
                    raise SystemExit(f"Oklahoma: a candidate line for {race} in {county} County is not read ({t!r})")
                listed.setdefault(race, {}).setdefault(county, []).append((re.sub(r"\s+", " ", name).strip(), PARTIES[label]))
    if seen != len(counties) or seen != 77:
        raise SystemExit(f"Oklahoma: the List of Elections has {seen} county sections for {len(counties)} counties in its menu (77 expected)")
    races, disagree = {}, []
    for race, by_county in listed.items():
        versions = {tuple(v) for v in by_county.values()}
        if len(versions) == 1:
            races[race] = (list(versions.pop()), len(by_county))
        else:
            disagree.append(race)
    return races, disagree


def grid(runs):
    """One printed line of the book as fixed-width characters, placed by where each run starts."""
    g = [" "] * 160
    for x0, _y, _size, t, _x1 in runs:
        c = round((x0 - LEFT) / CW)
        for i, ch in enumerate(t):
            if 0 <= c + i < len(g):
                g[c + i] = ch
    return "".join(g)


def book(path):
    """[{race, party, number, name}] for the federal offices, in the book's order, and whether it is the April 3 list."""
    pdf = PDF(open(path, "rb").read())
    pages = pdf.pages()
    cover = " ".join(join(rs) for _y, rs in pdf_rows(pdf, *pages[0]))
    if "Board April 1-3, 2026" not in cover or "April 3, 2026" not in cover:
        raise SystemExit("Oklahoma: the 2026 Candidate List Book's cover no longer reads as the April 1-3, 2026 filings")
    out, office, district, party, last, started = [], None, None, None, None, False
    for n, (page, res) in enumerate(pages, start=1):
        for y, runs in pdf_rows(pdf, page, res):
            heading = join(runs)                                  # compared against headings only; never printed
            if max(r[2] for r in runs) >= 11.5:                  # an office heading, 12-point
                if heading == "UNITED STATES SENATOR":
                    office, district, party, started = "S", None, None, True
                elif heading == "UNITED STATES REPRESENTATIVE":
                    office, district, party, started = "H", None, None, True
                elif started:
                    return out                                    # the federal offices come first; the next office ends them
                last = None
                continue
            if office is None:
                continue
            m = re.fullmatch(r"DISTRICT (\d+)", heading)
            if m and office == "H":
                district, party, last = int(m.group(1)), None, None
                continue
            if heading.upper() in PARTIES and len(heading) < 20:
                party, last = PARTIES[heading.upper()], None
                continue
            g = grid(runs)
            name = g[NAME_COLS[0]:NAME_COLS[1]].strip()
            if re.fullmatch(r"\d{5}", g[:5]) and not g[5:7].strip():
                if abs(min(r[0] for r in runs) - LEFT) > 1 or any(len(r[3]) >= 5 and abs((r[4] - r[0]) / len(r[3]) - CW) > 0.05 for r in runs):
                    raise SystemExit(f"Oklahoma: the book's type or margin changed on page {n}; its columns cannot be read by position")
                if not party or (office == "H" and not district):
                    raise SystemExit(f"Oklahoma: a candidate on page {n} of the book comes before its party or district heading")
                race = senate_id("OK", 2) if office == "S" else house_id("OK", district)
                last = [{"race": race, "party": party, "number": int(g[:5]), "name": name}, y]
                out.append(last[0])
            elif last and not g[:NAME_COLS[0]].strip() and name and 0 < last[1] - y < 15:
                last[0]["name"] += " " + name                     # a long name, wrapped in its own column
                last[1] = y
            else:
                raise SystemExit(f"Oklahoma: a line on page {n} of the candidate list book is not read (at {y:.0f} points)")
            if not re.fullmatch(r"[A-Z][A-Z0-9 .,'\"()-]*", last[0]["name"]):
                raise SystemExit(f"Oklahoma: filing number {last[0]['number']} on page {n} does not read as a name in capitals; "
                                 "the columns may have moved")
    raise SystemExit("Oklahoma: the candidate list book has no office after the federal ones")


def table(page, heads):
    """The rows of the page's table whose heading row is exactly `heads`, as lists of cell text."""
    for tb in re.findall(r"<table[^>]*>(.*?)</table>", page, re.S):
        trs = [[text(c) for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)] for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", tb, re.S)]
        if trs and trs[0] == list(heads):
            return trs[1:]
    raise SystemExit(f"Oklahoma: no table headed {heads} on the Board's page")


def load(con, cache, say=print):
    net.patient_lookups()
    folder = os.path.join(cache, "ok")
    list_path = os.path.join(folder, "ok_2026_general_list.html")
    book_path = os.path.join(folder, "ok_2026_candidate_list_book.pdf")
    wd_path, ct_path = os.path.join(folder, "ok_2026_withdrawals.json"), os.path.join(folder, "ok_2026_contests.json")

    page = fetch_page(LIST_URL, list_path, 2, must="NOVEMBER / 2026", say=say)
    if not re.search(r"<TITLE>\s*NOVEMBER / 2026\s+List of Elections\s*</TITLE>", page, re.I):
        raise SystemExit("Oklahoma: the cached List of Elections is not the November 2026 list")
    general, disagree = november(page)

    net.download(BOOK_URL, book_path, max_age_days=365)
    if open(book_path, "rb").read(5) != b"%PDF-":
        raise SystemExit(f"Oklahoma: {BOOK_URL} did not return a PDF")
    filers = book(book_path)

    # withdrawals (Number, Name, Office, Date) and contests of candidacy, kept on disk as those columns only
    if not os.path.exists(wd_path) or time.time() - os.path.getmtime(wd_path) > 2 * 86400:
        wp = net.get(WITHDRAWALS_URL, accept="text/html").decode("utf-8", "replace")
        wd = {"url": WITHDRAWALS_URL, "modified": modified(wp),
              "rows": [dict(zip(("number", "name", "office", "date"), r)) for r in table(wp, ("Number", "Name", "Office", "Date"))]}
        json.dump(wd, open(wd_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        time.sleep(1.0)
    wd = json.load(open(wd_path, encoding="utf-8"))
    if not os.path.exists(ct_path) or time.time() - os.path.getmtime(ct_path) > 7 * 86400:
        cp = net.get(CONTESTS_URL, accept="text/html").decode("utf-8", "replace")
        ct = {"url": CONTESTS_URL, "modified": modified(cp),
              "offices": [r[2] for r in table(cp, ("Cause", "Name", "Office", "Hearing")) if len(r) > 2 and r[2]]}
        json.dump(ct, open(ct_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    ct = json.load(open(ct_path, encoding="utf-8"))
    federal_contests = [o for o in ct["offices"] if FEDERAL_OFFICE.search(o)]
    if federal_contests:
        raise SystemExit(f"Oklahoma: a contest of candidacy concerns a federal office ({federal_contests}); read its outcome before loading")

    by_number = {f["number"]: f for f in filers}
    before, after = [], []
    for w in wd["rows"]:
        if not FEDERAL_OFFICE.search(w["office"]):
            continue
        f = by_number.get(int(w["number"]))
        if not f or name_parts(w["name"])[1] not in fold(f["name"]).split():
            raise SystemExit(f"Oklahoma: the withdrawal of {w['name']} (number {w['number']}) matches no federal filer in the book")
        when = datetime.strptime(w["date"], "%m/%d/%Y").strftime("%Y-%m-%d")
        f["withdrew"] = when
        (before if when < PRIMARY else after).append(f)

    rec = sqlite3.connect(f"file:{os.path.join(HERE, 'congress_119.sqlite')}?mode=ro", uri=True)
    fixed = {}
    for full, first, last in rec.execute("SELECT official_full, first_name, last_name FROM legislators WHERE is_current = 1 AND state = 'OK'"):
        for form in (full, f"{first} {last}"):
            if form:
                fixed[fold(form)] = form
    rec.close()

    def shown(caps):
        caps = re.sub(r"\s+", " ", caps).strip()
        if fold(caps) in fixed:
            return fixed[fold(caps)]
        t = re.sub(r"(['\"(])([a-z])", lambda m: m.group(1) + m.group(2).upper(), proper(caps))
        return re.sub(r"\b([A-Z])\.([a-z])\b", lambda m: m.group(1) + "." + m.group(2).upper(), t)      # R.o. -> R.O.

    def same(a, b):
        return fold(a) == fold(b)

    rows, nominee = [], {}
    for race, (cands, _n) in sorted(general.items()):
        for order, (name, party) in enumerate(cands, start=1):
            rows.append((race, "general", "2026-11-03", shown(name), party, party_code(party), order, 0, 0, None, None, None, None, None,
                         "ok-seb-2026-general-list", CAPS))
            filed = [f for f in filers if f["race"] == race and f["party"] == party]
            match = [f for f in filed if same(f["name"], name)] or \
                    [f for f in filed if name_parts(f["name"])[1] == name_parts(name)[1]]
            if len(match) != 1:
                raise SystemExit(f"Oklahoma: {name} ({party}, {race}) on the November list is not one {party} filer in the book")
            if match[0].get("withdrew"):
                raise SystemExit(f"Oklahoma: {name} ({race}) is on the November list but on the Board's list of withdrawals")
            if party in CODES:
                if (race, party) in nominee:
                    raise SystemExit(f"Oklahoma: two {party} candidates for {race} on the November list")
                nominee[(race, party)] = match[0]["number"]

    fields = {}
    for f in filers:
        if f["party"] in CODES and not (f.get("withdrew") and f["withdrew"] < PRIMARY):
            fields.setdefault((f["race"], f["party"]), []).append(f)
    nfields = 0
    for (race, party), field in sorted(fields.items()):
        if (race, party) not in nominee:
            raise SystemExit(f"Oklahoma: the {party} primary for {race} has no candidate on the November list; read the results before loading")
        if len(field) < 2:
            continue
        nfields += 1
        code = CODES[party]
        for f in field:
            note = CAPS_BOOK
            if f.get("withdrew"):
                day = datetime.strptime(f["withdrew"], "%Y-%m-%d")
                note = (f"Withdrew on {day:%B} {day.day}, {day.year}, after the June 16 primary (the State Election Board's list of "
                        f"withdrawals); not on the November list. {CAPS_BOOK}")
            rows.append((race, f"primary-{code}", PRIMARY, shown(f["name"]), party, party_code(party), None, 0, 0, None, None,
                         "advanced" if nominee[(race, party)] == f["number"] else "lost", None, None, "ok-seb-2026-candidate-list-book", note))

    gen_rows = [r for r in rows if r[1] == "general"]
    where = [f"{race.split('-')[-1]} in {n}" for race, (_c, n) in sorted(general.items())]
    wd_words = "; ".join(f"{shown(f['name'])} ({f['race']}, withdrew {f['withdrew']})" for f in before + after) or "none"
    with con:
        con.execute("DELETE FROM candidates WHERE race_id LIKE '2026-OK-%'")
        con.executemany("INSERT OR REPLACE INTO candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        record_source(con, "ok-seb-2026-general-list", path=list_path, level="federal", state="OK", kind="official candidate list",
                      agency="Oklahoma State Election Board",
                      title="NOVEMBER / 2026 List of Elections (November 3, 2026 General Election), county by county: "
                            "United States Senator and United States Representative",
                      url=LIST_URL, rows=len(gen_rows),
                      note=f"Read for all 77 counties; every county's list of each federal race agreed "
                           f"({', '.join(where)} counties)"
                           + (f"; left out where counties disagreed: {', '.join(disagree)}" if disagree else "")
                           + ". The list's order is the ballot order of the Board's July 8, 2026 drawing (Republican, Democratic, "
                             "Libertarian, then independents in lot order). The list names no write-in candidates. Federal candidates "
                             f"on the Board's list of withdrawals, none of them on this list: {len(before) + len(after)} ({wd_words}).")
        record_source(con, "ok-seb-2026-candidate-list-book", path=book_path, level="federal", state="OK", kind="official candidate list",
                      agency="Oklahoma State Election Board",
                      title="Candidates for Office 2026, filed in the office of the State Election Board April 1-3, 2026 "
                            "(2026 Candidate List Book, compiled as of 5:00 p.m. April 3, 2026): United States Senator and "
                            "United States Representative",
                      url=BOOK_URL, published="2026-04-03", rows=len(filers),
                      note=f"Read for who was on each party's June 16, 2026 primary ballot: the filing number and name columns only, "
                           f"the city beside each name never read. Withdrawn before the primary, not on its ballot: "
                           f"{'; '.join(shown(f['name']) + ' (' + f['race'] + ')' for f in before) or 'none'}. The nominee is the party's "
                           f"candidate on the November list. Votes not loaded: the June 16 primary and August 25 runoff results are "
                           f"published only on the Board's results site ({RESULTS_URL}), which refuses scripts (403 Forbidden); which "
                           f"fields went to the runoff is not read.")
        record_source(con, "ok-seb-2026-withdrawals", path=wd_path, level="federal", state="OK", kind="official candidate list",
                      agency="Oklahoma State Election Board", title="2026 Candidate Withdrawals", url=WITHDRAWALS_URL,
                      published=wd.get("modified", ""), rows=len(before) + len(after),
                      note=f"Federal withdrawals, matched to the book by filing number: {wd_words}. Columns kept: Number, Name, Office, Date.")
        record_source(con, "ok-seb-2026-contests", path=ct_path, level="federal", state="OK", kind="official candidate list",
                      agency="Oklahoma State Election Board", title="2026 Contests of Candidacy", url=CONTESTS_URL,
                      published=ct.get("modified", ""), rows=0,
                      note=f"Checked: none of the {len(ct['offices'])} contests of candidacy concerns a federal office.")
    house = len({r[0] for r in gen_rows if "-H" in r[0]})
    say(f"    Oklahoma: {house} House districts and {'the' if any('-S' in r[0] for r in gen_rows) else 'no'} Senate race, "
        f"{len(gen_rows)} candidates on the November ballot (every county's list agrees"
        + (f"; left out where counties disagreed: {', '.join(disagree)}" if disagree else "")
        + f"); {nfields} party primaries with a field, from the April filings less {len(before)} withdrawn; votes not loaded "
          "(the Board's results site refuses scripts), so who advanced comes from the November list")
    return len(gen_rows)
