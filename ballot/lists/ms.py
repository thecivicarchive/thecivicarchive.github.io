"""
Mississippi: the Secretary of State's own candidate list, sample ballot and official primary results. Mississippi has
four House seats and the Senate seat of class 2 (Cindy Hyde-Smith) on the ballot in 2026; the districts are the 2022
lines, used again in 2024.

  November list     the Secretary of State's Candidate Qualifying List (sos.ms.gov/content/CandidateQualifying/
                    default.aspx, shown inside the Elections Division's "Candidate Qualifying List" page), headed "All
                    offices and candidates currently on file". Its "Download CSV" button (the page's own postback, sent
                    with the page's own form fields) gives CandidateQualifying.csv, whose columns are Office, Candidate
                    Name, Party, District, Place, Qualifying Period, Primary Election, General Election and Election; the
                    list carries no addresses, telephones or e-mail at all. Only the rows of "Candidates for United
                    States Senate" and "Candidates for United States House of Representatives" are kept (office, name,
                    party, district, and the primary and general election dates the list prints), as JSON in
                    ballot_cache/ms/, and checked name for name against the tables on the page itself. As read in
                    September 2026 the list holds only candidates still in the running: the March primary's losers are
                    gone, and it lists no write-in candidates. It has no status column, so a candidate who withdrew or
                    was removed is simply no longer listed and cannot be counted.
  ballot order      the Secretary of State's "SAMPLE Official Election Ballot, State of Mississippi, Federal and Judicial
                    Election, Tuesday, November 3, 2026" (a PDF linked as "Sample Ballot" from the Elections & Voting
                    page; the file read was dated 9-9-26 in its name). The ballot is printed in two columns; each column
                    is read top to bottom, a contest being its heading ("For United States Senate", "For US House of
                    Representatives, 4th Congressional District", "Vote for ONE"), its candidates (name, then party at
                    the right of the column) and a closing "Write-in" line. Only the federal contests are kept. The
                    order is the ballot's own: party nominees in alphabetical order, then independent candidates. The
                    names and parties on the November rows are the ballot's, exactly as printed ("Democrat", where the
                    qualifying list writes "Democratic"); the ballot's candidates must be exactly the qualifying list's,
                    race by race, name for name, party for party.
  primary fields    the Secretary of State's Official Recapitulation of the March 10, 2026 party primaries, one PDF per
                    party ("2026 Republican Primary Election Results", "2026 Democratic Primary Election Results"),
                    linked from the results page the Election Results pages show for the March primary. Each is headed
                    "Official Results ... FEDERAL PRIMARY ELECTION, Date of Election: 3/10/2026" and prints every
                    candidate's votes county by county for all 82 counties, eleven counties to a page, with a TOTAL
                    column on the last; an "X" marks a county outside the district. Columns are read from the county
                    names printed across the top of each page; a page that repeats a set of counties with no contest
                    heading continues the last contest of that set (a party's list too long for one page). Checks:
                    every candidate has one cell for each of the 82 counties, the county figures add up to the TOTAL,
                    the Senate has figures in every county, and every candidate in a House contest has figures in the
                    same counties. Mississippi prints no write-in line in a primary, so a field's total is the sum of
                    its candidates' votes. A nominee needs a majority; every 2026 federal primary was won outright
                    (the loader checks this and stops if a runoff would have been needed), so there was no federal
                    runoff on April 7 and none is stored. A field is a party primary with two candidates or more; its
                    winner must be the party's candidate on the November list. Unopposed primaries (the recapitulation
                    prints them with votes) are not fields.

Names are printed in ordinary capitals everywhere and are shown as printed. Every host here answers scripts.
"""

import csv
import html as H
import io
import json
import os
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen

from ballot import pdftext
from ballot.common import fold, house_id, party_code, record_source, senate_id
from states import net

ELECTIONS_PAGE = "https://www.sos.ms.gov/elections-voting"
LIST_PAGE = "https://www.sos.ms.gov/elections-voting/candidate-qualifying-list"
QUALIFYING = "https://sos.ms.gov/content/CandidateQualifying/default.aspx"
RESULTS_PAGE = "https://www.sos.ms.gov/elections-voting/election-results"
RESULTS_FRAME = "https://sos.ms.gov/elections/electionresults_aspx/elections_results_2026_march_primary.aspx?party=republican"
# last seen at these addresses; the loader looks for the links again and falls back to these
SAMPLE_SEEN = "https://www.sos.ms.gov/content/documents/Elections/2026/Sample%20Ballot%209-9-26.pdf"
RECAP_SEEN = {"DEM": "https://www.sos.ms.gov/content/documents/elections/2026/Recap%20report%20Democratic%20Primary%202026.pdf",
              "REP": "https://www.sos.ms.gov/content/documents/elections/2026/republican%20primary%202026.pdf"}
RECAP_LABEL = {"DEM": "2026 Democratic Primary Election Results", "REP": "2026 Republican Primary Election Results"}
RECAP_PARTY = {"DEM": "Democrat", "REP": "Republican"}                 # the party as each recapitulation prints it
PRIMARY = "2026-03-10"
COUNTIES = 82
CSV_COLUMNS = ("Office", "Candidate Name", "Party", "District")        # the only columns ever read
KEEP = ("Office", "Candidate Name", "Party", "District", "Primary Election", "General Election")
OFFICES = {"Candidates for United States Senate": "S", "Candidates for United States House of Representatives": "H"}
SAME_PARTY = {"democratic": "democrat"}                                # the list's word -> the ballot's word, for the check only


def fresh(path, days):
    return os.path.exists(path) and time.time() - os.path.getmtime(path) < days * 86400


def fetch(url, data=None, accept="*/*"):
    """One GET (or form POST), with the honest User-Agent; repairs a missing issuer certificate as states/net.get does."""
    req = Request(url, data=urlencode(data).encode() if data else None,
                  headers={"User-Agent": net.UA, "Accept": accept,
                           **({"Content-Type": "application/x-www-form-urlencoded"} if data else {})})
    try:
        with urlopen(req, timeout=120) as r:
            return r.read()
    except URLError as e:
        if getattr(getattr(e, "reason", None), "verify_code", None) != 20:
            raise
        ctx = net._context_with_issuer(req.host)
        if ctx is None:
            raise
        with urlopen(req, timeout=120, context=ctx) as r:
            return r.read()


def clean(text):
    return re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", text or "")).replace("​", "")).strip()


def race_of(office, district):
    kind = OFFICES.get(clean(office))
    if kind == "S":
        if district:
            raise SystemExit(f"Mississippi: a Senate row of the qualifying list names a district ({district!r})")
        return senate_id("MS", 2)
    if kind == "H":
        if not re.fullmatch(r"[1-4]", district or ""):
            raise SystemExit(f"Mississippi: a House row of the qualifying list names district {district!r}")
        return house_id("MS", int(district))
    if re.search(r"United States|Congress|\bU\.?S\.? ", office or "", re.I):
        raise SystemExit(f"Mississippi: an office on the qualifying list that looks federal could not be read: {office!r}")
    return None


def page_tables(page):
    """{office heading: [(name, party, district)]} from the qualifying page's own tables, for the check."""
    out = {}
    for heading in OFFICES:
        at = page.find(heading)
        if at < 0:
            raise SystemExit(f"Mississippi: the qualifying page no longer has a section headed {heading!r}")
        m = re.search(r"<table\b.*?</table>", page[at:], re.S | re.I)
        heads = [clean(x) for x in re.findall(r"<th[^>]*>(.*?)</th>", m.group(0), re.S | re.I)]
        if heads[:2] != ["Name", "Party"]:
            raise SystemExit(f"Mississippi: the qualifying page's table for {heading} has columns {heads}")
        rows = []
        for tr in re.findall(r"<tr.*?</tr>", m.group(0), re.S | re.I):
            cells = dict(zip(heads, [clean(x) for x in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S | re.I)]))
            if cells.get("Name"):
                rows.append((cells["Name"], cells["Party"], cells.get("District", "")))
        out[heading] = rows
    return out


def read_list(path, say):
    """The federal rows of the qualifying list's CSV (kept columns only), checked against the page; read afresh after two days."""
    if fresh(path, 2):
        return json.load(open(path, encoding="utf-8"))
    try:
        page = fetch(QUALIFYING, accept="text/html").decode("utf-8", "replace")
        form = {n: H.unescape(v) for n, v in re.findall(r'<input type="hidden" name="([^"]+)" id="[^"]+" value="([^"]*)"', page)}
        button = re.search(r'<input type="submit" name="([^"]+)" value="(Download CSV)"', page)
        if not form.get("__VIEWSTATE") or not button:
            raise SystemExit("Mississippi: the qualifying page no longer has its Download CSV button")
        form[button.group(1)] = button.group(2)
        time.sleep(1.5)
        raw = fetch(QUALIFYING, data=form, accept="text/csv")
    except (HTTPError, URLError, OSError) as e:
        if os.path.exists(path):
            say(f"      could not read the qualifying list afresh ({e}); using the copy read earlier")
            return json.load(open(path, encoding="utf-8"))
        raise SystemExit(f"Mississippi: the qualifying list could not be read ({e})")
    text = raw.decode("utf-8-sig", "replace")
    if not text.startswith("Office,"):
        raise SystemExit("Mississippi: the qualifying list's Download CSV did not give a CSV file")
    reader = csv.DictReader(io.StringIO(text))
    missing = [c for c in CSV_COLUMNS if c not in (reader.fieldnames or [])]
    if missing:
        raise SystemExit(f"Mississippi: the qualifying list's CSV has no {missing} column")
    rows, total = [], 0
    for r in reader:
        total += 1
        if race_of(r["Office"], (r["District"] or "").strip()):
            rows.append({k: clean(r.get(k)) for k in KEEP})
    # control: the page's own tables list the same federal candidates
    tables = page_tables(page)
    shown = sorted((o, n, p, d) for o, rs in tables.items() for n, p, d in rs)
    read = sorted((r["Office"], r["Candidate Name"], r["Party"], r["District"]) for r in rows)
    if shown != read:
        raise SystemExit("Mississippi: the qualifying list's CSV and the tables on its page list different federal candidates")
    for r in rows:
        if r["Primary Election"] != "March 10, 2026" or r["General Election"] != "November 3, 2026":
            raise SystemExit(f"Mississippi: a federal row of the qualifying list is for {r['Primary Election']} / {r['General Election']}")
    kept = {"url": QUALIFYING, "page": LIST_PAGE, "csv": "CandidateQualifying.csv (the page's Download CSV button)",
            "rows_in_file": total, "read": time.strftime("%Y-%m-%d"), "federal": rows}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(kept, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    say(f"      qualifying list: {len(rows)} federal candidates of {total} rows")
    return kept


def find_links(say):
    """{'sample': url, 'DEM': url, 'REP': url} from the Secretary's own pages; the addresses last seen where a page
    cannot be read or no longer links a label."""
    links = {"sample": SAMPLE_SEEN, **RECAP_SEEN}
    try:
        page = fetch(ELECTIONS_PAGE, accept="text/html").decode("utf-8", "replace")
        for href, label in re.findall(r'<a[^>]+href="([^"]+\.pdf)"[^>]*>(.*?)</a>', page, re.S | re.I):
            if clean(label).startswith("Sample Ballot") and "2026" in href:
                links["sample"] = urljoin(ELECTIONS_PAGE, H.unescape(href).replace(" ", "%20"))
                break
        time.sleep(1.5)
        frame = fetch(RESULTS_FRAME, accept="text/html").decode("utf-8", "replace")
        for href, label in re.findall(r'<a[^>]+href="([^"]+\.pdf)"[^>]*>(.*?)</a>', frame, re.S | re.I):
            for code, want in RECAP_LABEL.items():
                if clean(label) == want:
                    links[code] = urljoin(RESULTS_FRAME, H.unescape(href).replace(" ", "%20"))
    except (HTTPError, URLError, OSError) as e:
        say(f"      the Secretary's pages could not be read ({e}); using the addresses last seen there")
    return links


def get_pdf(url, path, days, what):
    net.download(url, path, max_age_days=days)
    if open(path, "rb").read(5) != b"%PDF-":
        os.remove(path)
        raise SystemExit(f"Mississippi: the {what} downloaded from {url} is not a PDF")
    return path


def created(path):
    """The PDF's own creation date, as YYYY-MM-DD, or ''."""
    m = re.search(rb"/CreationDate\s*\(D:(\d{4})(\d{2})(\d{2})", open(path, "rb").read())
    return f"{m.group(1).decode()}-{m.group(2).decode()}-{m.group(3).decode()}" if m else ""


def lines_of(runs):
    """Runs grouped into printed lines, top to bottom: [(y, [runs left to right])]."""
    out = []
    for r in sorted(runs, key=lambda r: (-round(r[1], 1), r[0])):
        if out and abs(out[-1][0] - r[1]) <= max(1.5, 0.35 * r[2]):
            out[-1][1].append(r)
        else:
            out.append([r[1], [r]])
    return [(y, sorted(rs)) for y, rs in out]


def ballot_contest(heading):
    """The race of a heading on the sample ballot; None for a contest that is not federal."""
    t = re.sub(r"\s*Vote for ONE\s*$", "", heading).strip()
    if re.fullmatch(r"For United States Senate", t):
        return senate_id("MS", 2)
    m = re.fullmatch(r"For US House of Representatives ([1-4])(?:st|nd|rd|th) Congressional District", t)
    if m:
        return house_id("MS", int(m.group(1)))
    if re.search(r"United States|US House|Congress", t, re.I):
        raise SystemExit(f"Mississippi: a federal contest on the sample ballot could not be read: {heading!r}")
    return None


def ballot_order(path):
    """{race: [(name, party)]} in ballot order, from the sample ballot's two columns."""
    pdf = pdftext.PDF(open(path, "rb").read())
    out, first = {}, ""
    for n, (page, res) in enumerate(pdf.pages(), start=1):
        box = [pdf.get(v) for v in (pdf.get(page.get("MediaBox")) or [0, 0, 612, 792])]
        mid = (float(box[0]) + float(box[2])) / 2
        runs = pdftext.page_runs(pdf, page, res)
        if n == 1:
            first = " ".join(pdftext.join(rs) for _y, rs in lines_of(runs))
        for side in (False, True):
            col = [r for r in runs if (r[0] >= mid) == side and r[3].strip()]
            heading, in_contest, race = [], False, None
            for _y, rs in lines_of(col):
                text, size = pdftext.join(rs), max(r[2] for r in rs)
                if text == "Write-in":
                    heading, in_contest, race = [], False, None
                elif size >= 10.5:
                    if in_contest:
                        heading, in_contest, race = [], False, None
                    heading.append(text)
                elif 8.5 <= size < 10.5:
                    if not in_contest:
                        race, in_contest = ballot_contest(" ".join(heading)), True
                        if race and not " ".join(heading).endswith("Vote for ONE"):
                            raise SystemExit(f"Mississippi: the sample ballot's {race} contest is not 'Vote for ONE'")
                        if race in out:
                            raise SystemExit(f"Mississippi: the sample ballot prints {race} twice")
                        if race:
                            out[race] = []
                    if race:
                        left = min(r[0] for r in rs)
                        name = pdftext.join([r for r in rs if r[0] < left + 150])
                        party = pdftext.join([r for r in rs if r[0] >= left + 150])
                        if not name or not party:
                            raise SystemExit(f"Mississippi: a line of the sample ballot's {race} contest has no name or no party")
                        out[race].append((name, party))
    if "Federal and Judicial Election" not in first or "November 3, 2026" not in first:
        raise SystemExit("Mississippi: the sample ballot read is not the November 3, 2026 Federal and Judicial Election's")
    return out


def recap_race(heading):
    t = re.sub(r"\s+", " ", heading).strip()
    if t == "United States-Senate":
        return senate_id("MS", 2)
    m = re.fullmatch(r"US House Of Rep 0?([1-4])-\d(?:st|nd|rd|th) Congressional District", t)
    if m:
        return house_id("MS", int(m.group(1)))
    raise SystemExit(f"Mississippi: a contest in the primary recapitulation that is not read ({t!r})")


def recapitulation(path, party):
    """{race: [(name, votes)]} from one party's Official Recapitulation, in the order printed; every check made."""
    pdf = pdftext.PDF(open(path, "rb").read())
    fields, cells, counties, last_of_set = {}, {}, set(), {}
    for n, (page, res) in enumerate(pdf.pages(), start=1):
        rows = lines_of(pdftext.page_runs(pdf, page, res))
        texts = [pdftext.join(rs) for _y, rs in rows]
        if n == 1:
            if texts[:1] != ["Official Results"] or "Total Votes Reported by Counties for FEDERAL PRIMARY ELECTION" not in texts \
                    or "Date of Election: 3/10/2026" not in texts:
                raise SystemExit(f"Mississippi: {os.path.basename(path)} is not headed as the official results of the 3/10/2026 federal primary")
            continue
        if "Official Recapitulation" not in texts or "FEDERAL PRIMARY ELECTION" not in texts or "day of March 2026" not in texts:
            raise SystemExit(f"Mississippi: page {n} of {os.path.basename(path)} is not a page of the federal primary's recapitulation")
        head = [(y, rs) for y, rs in rows if all(r[2] < 2 for r in rs)]            # the county names, printed turned
        if len(head) != 1:
            raise SystemExit(f"Mississippi: page {n} of {os.path.basename(path)} has no single row of county names")
        head_y, head_runs = head[0]
        cols = [r[3].strip() for r in head_runs]
        edge = min(r[0] for r in head_runs) - 15                                   # the cells start right of this
        key = tuple(cols)
        counties.update(c for c in cols if c != "TOTAL")
        race, pending = None, []
        for (y, rs), text in zip(rows, texts):
            if y >= head_y or text.startswith("Statewide Election Management System"):
                continue
            left = [r for r in rs if r[4] <= edge]
            right = [r for r in rs if r[4] > edge]
            if not right:                                                           # a contest heading, perhaps on two lines
                pending.append(pdftext.join(left))
                continue
            if pending:
                race, pending = recap_race(" ".join(pending)), []
                fields.setdefault(race, [])
                last_of_set[key] = race
            elif race is None:
                race = last_of_set.get(key)                                         # a page continuing the last contest of these counties
                if race is None:
                    raise SystemExit(f"Mississippi: page {n} of {os.path.basename(path)} begins with a candidate and no contest")
            printed_party = max(left, key=lambda r: r[0])
            name = pdftext.join([r for r in left if r is not printed_party])
            if printed_party[3].strip() != party:
                raise SystemExit(f"Mississippi: {name} is printed as {printed_party[3]!r} in the {party} recapitulation")
            values = [r[3].strip() for r in right]
            if len(values) != len(cols) or any(not re.fullmatch(r"X|\d+", v) for v in values):
                raise SystemExit(f"Mississippi: {name}'s row on page {n} does not have one figure or X for each county")
            if name not in cells.setdefault(race, {}):
                fields[race].append(name)
            got = cells[race].setdefault(name, {})
            for c, v in zip(cols, values):
                if c in got:
                    raise SystemExit(f"Mississippi: {name} has two figures for {c}")
                got[c] = None if v == "X" else int(v)
    if len(counties) != COUNTIES:
        raise SystemExit(f"Mississippi: {os.path.basename(path)} has columns for {len(counties)} counties, not {COUNTIES}")
    out = {}
    for race, names in fields.items():
        pattern = None
        for name in names:
            got = cells[race][name]
            if set(got) != counties | {"TOTAL"} or got["TOTAL"] is None:
                raise SystemExit(f"Mississippi: {name} ({race}) is not given a figure or X for every county and a TOTAL")
            summed = sum(v for c, v in got.items() if c != "TOTAL" and v is not None)
            if summed != got["TOTAL"]:
                raise SystemExit(f"Mississippi: {name}'s county figures in {race} add to {summed}, the TOTAL says {got['TOTAL']}")
            mine = frozenset(c for c, v in got.items() if v is not None)
            if race.endswith("-S2") and len(mine) != COUNTIES + 1:
                raise SystemExit(f"Mississippi: {name} has an X in a county for the Senate")
            if pattern is not None and mine != pattern:
                raise SystemExit(f"Mississippi: the candidates for {race} are counted in different counties")
            pattern = mine
        out[race] = [(name, cells[race][name]["TOTAL"]) for name in names]
    return out


def load(con, cache, say=print):
    net.patient_lookups()
    folder = os.path.join(cache, "ms")
    os.makedirs(folder, exist_ok=True)
    lpath = os.path.join(folder, "ms_2026_qualifying_list_federal.json")
    listed = read_list(lpath, say)
    links_path = os.path.join(folder, "ms_2026_links.json")
    if fresh(links_path, 7):
        links = json.load(open(links_path, encoding="utf-8"))
    else:
        links = find_links(say)
        json.dump(links, open(links_path, "w", encoding="utf-8"), indent=1)
    spath = get_pdf(links["sample"], os.path.join(folder, "ms_2026_general_sample_ballot.pdf"), 7, "sample ballot")
    rpaths = {code: get_pdf(links[code], os.path.join(folder, f"ms_2026_primary_{code.lower()}_recapitulation.pdf"), 90,
                            f"{code} primary recapitulation") for code in RECAP_LABEL}

    # the November list, and the ballot's order, names and parties; the two must agree name for name
    on_list = {}
    for r in listed["federal"]:
        on_list.setdefault(race_of(r["Office"], r["District"]), []).append((r["Candidate Name"], r["Party"]))
    expected = {senate_id("MS", 2)} | {house_id("MS", d) for d in range(1, 5)}
    order = ballot_order(spath)
    if set(on_list) != expected or set(order) != expected:
        raise SystemExit(f"Mississippi: the list covers {sorted(on_list)} and the sample ballot {sorted(order)}; {sorted(expected)} were expected")
    rows, nominee = [], {}
    for race in sorted(expected):
        want = sorted((fold(n), SAME_PARTY.get(p.lower(), p.lower())) for n, p in on_list[race])
        have = sorted((fold(n), p.lower()) for n, p in order[race])
        if want != have:
            raise SystemExit(f"Mississippi: the sample ballot's candidates for {race} are not the qualifying list's")
        for pos, (name, party) in enumerate(order[race], start=1):
            code = {"R": "REP", "D": "DEM"}.get(party_code(party))
            if code:
                if (race, code) in nominee:
                    raise SystemExit(f"Mississippi: two {party} candidates for {race} on the November ballot")
                nominee[(race, code)] = name
            rows.append((race, "general", "2026-11-03", name, party, party_code(party), pos, 0, 0, None, None, None, None, None,
                         "ms-sos-2026-sample-ballot", None))
    general = len(rows)

    # the March 10 primaries
    fields, checked = 0, 0
    for code, path in rpaths.items():
        contests = recapitulation(path, RECAP_PARTY[code])
        for race, field in contests.items():
            total = sum(v for _n, v in field)
            top = max(field, key=lambda nv: nv[1])
            if sum(1 for _n, v in field if v == top[1]) > 1 or 2 * top[1] <= total:
                raise SystemExit(f"Mississippi: no one won a majority in the {race} {code} primary; read the April runoff's results")
            won = nominee.get((race, code))
            if won and fold(won) != fold(top[0]):
                raise SystemExit(f"Mississippi: the {race} {code} primary's winner ({top[0]}) is not the party's candidate on the November ballot ({won})")
            checked += 1
            if len(field) < 2:
                continue
            fields += 1
            for name, votes in field:
                advanced = name == top[0]
                rows.append((race, f"primary-{code}", PRIMARY, name, RECAP_PARTY[code], party_code(RECAP_PARTY[code]), None, 0, 0, votes,
                             round(100 * votes / total, 1) if total else None, "advanced" if advanced else "lost", None, None,
                             f"ms-sos-2026-primary-{code.lower()}",
                             "Won the nomination; not on the November ballot." if advanced and not won else None))
        missing = [r for (r, c) in nominee if c == code and r not in contests]
        if missing:
            raise SystemExit(f"Mississippi: the {code} nominee for {missing} on the November ballot is not in the {code} recapitulation")

    with con:
        con.execute("DELETE FROM list_gaps WHERE state = 'MS'")
        con.execute("DELETE FROM candidates WHERE race_id LIKE '2026-MS-%'")
        con.executemany("INSERT OR REPLACE INTO candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        record_source(con, "ms-sos-2026-sample-ballot", path=spath, level="federal", state="MS", kind="official sample ballot",
                      agency="Mississippi Secretary of State",
                      title="SAMPLE Official Election Ballot, State of Mississippi: Federal and Judicial Election, Tuesday, November 3, 2026",
                      url=links["sample"], published=created(spath), rows=general,
                      note=f"Linked as \"Sample Ballot\" from {ELECTIONS_PAGE}. The federal contests only, read column by column; the "
                           "order, names and parties are the ballot's own (party nominees in alphabetical order, then independent "
                           "candidates). Every contest's candidates are exactly the Candidate Qualifying List's. The ballot leaves a "
                           "Write-in line in each contest; no declared write-in candidates are listed.")
        record_source(con, "ms-sos-2026-qualifying-list", path=lpath, level="federal", state="MS", kind="official candidate list",
                      agency="Mississippi Secretary of State",
                      title="Candidate Qualifying List: Candidates for United States Senate and United States House of Representatives "
                            "(CandidateQualifying.csv)",
                      url=QUALIFYING, rows=len(listed["federal"]),
                      note=f"Shown on {LIST_PAGE}, \"All offices and candidates currently on file\"; read through the page's own Download "
                           "CSV button (columns Office, Candidate Name, Party, District, Place, Qualifying Period, Primary Election, "
                           "General Election, Election; no contact columns) and checked against the tables on the page. Used as the "
                           "control for the sample ballot: the same candidates, race by race (the list writes \"Democratic\" where the "
                           "ballot prints \"Democrat\"). The list has no status column: a candidate who withdrew or was removed is no "
                           "longer listed, so none can be counted; it lists no write-in candidates.")
        for code, path in rpaths.items():
            n = sum(1 for r in rows if r[1] == f"primary-{code}")
            record_source(con, f"ms-sos-2026-primary-{code.lower()}", path=path, level="federal", state="MS", kind="official results",
                          agency="Mississippi Secretary of State",
                          title=f"{RECAP_LABEL[code]}: Official Recapitulation, Federal Primary Election, March 10, 2026",
                          url=links[code], published=created(path), rows=n,
                          note=f"Linked from the March 10, 2026 primary results on {RESULTS_PAGE}. Headed \"Official Results\"; every "
                               f"candidate's figures for all {COUNTIES} counties add up to the TOTAL column. No write-in line is printed, so "
                               "a field's total is its candidates' votes. Every federal nominee won a majority, so no federal runoff "
                               "was held on April 7.")
    say(f"    Mississippi: 4 House districts and the Senate race, {general} candidates on the November ballot in the sample "
        f"ballot's order (0 declared write-ins); {fields} party primaries with a field ({checked - fields} unopposed), votes from the "
        f"Secretary of State's official recapitulations, county sums checked, every nominee by majority (no runoff)")
    return general
