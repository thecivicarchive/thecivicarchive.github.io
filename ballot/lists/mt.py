"""
Montana: the Secretary of State's candidate filing lists on candidatefiling.mt.gov ("FEDERAL GENERAL 2026 Candidate
List", election 450002987, and "FEDERAL PRIMARY 2026 Candidate List", election 450002928; sosmt.gov/elections/filing/
links them as "2026 Candidate Filings"), and its official results of the June 2, 2026 primary from
sosmt.gov/elections/results/: the "2026 Primary Election Precinct by Precinct Report" (a workbook) and the "2026
Statewide Primary Election Canvass" (a PDF, read with ballot/pdftext.py).

Each list is a Telerik grid of every office, 100 rows a page, the offices in ballot order (the U.S. Senate and House
first). Every page is read through the grid's own pager (a postback, as the page's Next button makes), and the count
of rows is checked against the grid's own "items" figure. Columns are taken by name, only Status, District Type,
District, Race, Term Type, Name, Party Preference and Ballot Order; the grid also carries mailing addresses, e-mail and
web addresses and phones, which are never read, and the cached copy keeps only the columns taken, for the federal rows.
An asterisk before a name marks an incumbent and is dropped. Parties are written out from the list's own key, read
from the page: DEM Democratic, REP Republican, LIB Libertarian, IND Independent, MP Minor Party, NON Non Partisan.

The November ballot is every federal row of the general list with the status FILED or NOMINATED; a row marked
withdrawn or removed is left off and counted, and any other status stops the loader. The general list gives no ballot
order, so its own order is kept (party nominees, then independents, then write-ins). The list notes a write-in
declaration only in its e-mail and web column, which is never read; a party nominee is DEM, REP, LIB or MP and an
independent who petitioned is IND, so a candidate for Congress filed as NON is shown as a declared write-in whose name
is not printed on the ballot (write_in 1, no ballot position).

The primary: each party's candidates for each federal race with their votes, summed from the precinct workbook
(columns County, Precinct, Race, District, Candidate Last Name, Party, Votes, Full Name On Ballot); each party
primary's totals must match a "Total" line of the State Canvass, and its candidates must be exactly the primary list's
FILED and NOMINATED rows for that party. Neither file carries write-in votes, so a field's total is the sum of its
candidates' votes. A field is a party primary with two candidates or more; the one on the November list for that party
advanced, and the primary list's own NOMINATED mark must agree.

Names are printed in capitals everywhere; the page shows them in ordinary capitals (a sitting member as the
congress-legislators roster spells them) and says so.
"""

import collections
import html as H
import json
import os
import re
import sqlite3
import time
import urllib.parse
from urllib.request import Request, urlopen

import openpyxl

from ballot.common import HERE, fold, house_id, party_code, record_source, senate_id
from ballot.lists.tx import proper
from ballot.pdftext import lines
from states import net

LIST_URL = "https://candidatefiling.mt.gov/candidatefiling/CandidateList.aspx?e="
LISTS = {"general": ("450002987", "FEDERAL GENERAL 2026"), "primary": ("450002928", "FEDERAL PRIMARY 2026")}
PRECINCT_URL = "https://sosmt.gov/docs/31/post-election/76697/2026-primary-election-precinct-by-precinct-report"
CANVASS_URL = "https://sosmt.gov/docs/31/post-election/76711/2026-primary-state-canvass"
PRIMARY = "2026-06-02"
KEEP = ("Status", "District Type", "District", "Race", "Term Type", "Name", "Party Preference", "Ballot Order")
BOOK_KEEP = ("County", "Race", "District", "Candidate Last Name", "Party", "Votes", "Full Name On Ballot")
FEDERAL = ("UNITED STATES SENATOR", "UNITED STATES REPRESENTATIVE")
ON = ("FILED", "NOMINATED")
OFF = re.compile(r"WITHDR|REMOV|DISQUAL|DECEAS|REJECT|DENIED", re.I)
NOMINEE_CODES = ("DEM", "REP", "LIB", "MP")
CAPS = "Montana's list prints names in capitals; they are shown here in ordinary capitals."
CAPS_RESULTS = "Montana's results print names in capitals; they are shown here in ordinary capitals."
WRITE_IN = "Write-in candidate: the name is not printed on the ballot."


def text(cell):
    return re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", "", cell)).replace("\xa0", " ")).strip()


def race_of(race, district):
    race = (race or "").strip().upper()
    if race == "UNITED STATES SENATOR":
        return senate_id("MT", 2)
    if race == "UNITED STATES REPRESENTATIVE":
        m = re.fullmatch(r"(\d+)(?:ST|ND|RD|TH) CONGRESSIONAL", (district or "").strip().upper())
        if not m:
            raise SystemExit(f"Montana: a U.S. Representative row names a district that is not read ({district!r})")
        return house_id("MT", int(m.group(1)))
    return None


def grid_rows(page):
    """Every row of one page of the grid, the kept columns only."""
    heads = [text(h) for h in re.findall(r'<th[^>]*class="rgHeader[^"]*"[^>]*>(.*?)</th>', page, re.S)]
    if not all(k in heads for k in KEEP):
        raise SystemExit(f"Montana: the candidate grid's columns changed ({[h for h in heads if h in KEEP]})")
    idx = {k: heads.index(k) for k in KEEP}      # "Status" is printed twice; the first is the one shown
    for tr in re.findall(r'<tr class="(?:rgRow|rgAltRow)"[^>]*>(.*?)</tr>', page, re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        if len(cells) != len(heads):
            raise SystemExit("Montana: a grid row does not line up with the grid's headings")
        yield {k: text(cells[i]) for k, i in idx.items()}


def form_fields(page):
    fields = {}
    for tag in re.findall(r'<input[^>]*type="hidden"[^>]*>', page):
        name, value = re.search(r'name="([^"]+)"', tag), re.search(r'value="([^"]*)"', tag)
        if name:
            fields[name.group(1)] = H.unescape(value.group(1)) if value else ""
    for name, body in re.findall(r'<select[^>]*name="([^"]+)"[^>]*>(.*?)</select>', page, re.S):
        chosen = re.search(r'<option selected="selected" value="([^"]*)"', body)
        fields[name] = chosen.group(1) if chosen else ""
    return fields


def read_list(kind, path, say):
    """The federal rows of one list, every page read; kept on disk (kept columns only) for two days."""
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < 2 * 86400:
        return json.load(open(path, encoding="utf-8"))
    eid, title = LISTS[kind]
    url = LIST_URL + eid
    page = net.get(url, accept="text/html").decode("utf-8", "replace")
    if f"{title} Candidate List" not in page:
        raise SystemExit(f"Montana: {url} is no longer the {title} Candidate List")
    m = re.search(r"<strong>(\d+)</strong>\s*items in\s*<strong>(\d+)</strong>", page)
    key = re.search(r"DEM = Democratic[^<]*", page)
    if not m or not key:
        raise SystemExit(f"Montana: the {title} list no longer shows its row count or its key of parties")
    items, pages = int(m.group(1)), int(m.group(2))
    legend = dict(re.findall(r"\b([A-Z]{2,3}) = ([A-Z][a-z]+(?: [A-Z][a-z]+)*)", key.group(0)))
    rows = list(grid_rows(page))
    for n in range(2, pages + 1):
        nxt = re.search(r'name="([^"]+)" value=" " onclick="javascript:__doPostBack\(&#39;[^&]+&#39;,&#39;&#39;\)" title="Next Page"', page)
        if not nxt:
            raise SystemExit(f"Montana: page {n - 1} of the {title} list has no Next Page button")
        fields = form_fields(page)
        fields.update({"__EVENTTARGET": nxt.group(1), "__EVENTARGUMENT": ""})
        time.sleep(2)
        req = Request(url, data=urllib.parse.urlencode(fields).encode(), method="POST",
                      headers={"User-Agent": net.UA, "Content-Type": "application/x-www-form-urlencoded", "Referer": url})
        with urlopen(req, timeout=120) as r:
            page = r.read().decode("utf-8", "replace")
        cur = re.search(r'class="rgCurrentPage"[^>]*><span>(\d+)</span>', page)
        if not cur or int(cur.group(1)) != n:
            raise SystemExit(f"Montana: asked for page {n} of the {title} list and got {cur.group(1) if cur else 'no page'}")
        rows += list(grid_rows(page))
    if len(rows) != items:
        raise SystemExit(f"Montana: the {title} list counts {items} rows; {len(rows)} were read")
    fed = [r for r in rows if r["Race"] in FEDERAL]
    for r in fed:
        if r["Term Type"] != "REGULAR":
            raise SystemExit(f"Montana: a federal race on the {title} list is not a regular term ({r['Race']}, {r['Term Type']})")
    kept = {"title": title, "url": url, "items": items, "legend": legend, "rows": fed}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(kept, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    say(f"      {title} Candidate List: {items} rows on {pages} pages, {len(fed)} for Congress")
    return kept


def primary_votes(path):
    """{(race, party code): {name on ballot: [last name, votes]}} for the federal races, summed over every precinct."""
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.worksheets[0]
    it = ws.iter_rows(values_only=True)
    heads = [str(c or "").strip() for c in next(it)]
    if not all(k in heads for k in BOOK_KEEP):
        raise SystemExit(f"Montana: the precinct workbook's columns changed ({heads})")
    idx = {k: heads.index(k) for k in BOOK_KEEP}
    out, counties = {}, set()
    for r in it:
        race = race_of(r[idx["Race"]], r[idx["District"]]) if str(r[idx["Race"]] or "").strip().upper() in FEDERAL else None
        if not race:
            continue
        name = re.sub(r"\s+", " ", str(r[idx["Full Name On Ballot"]] or "")).strip()
        cell = out.setdefault((race, str(r[idx["Party"]]).strip()), {}).setdefault(name, [str(r[idx["Candidate Last Name"]] or "").strip(), 0])
        cell[1] += int(r[idx["Votes"]] or 0)
        counties.add(r[idx["County"]])
    wb.close()
    return out, len(counties)


def canvass_totals(path):
    """Every "Total" line of the State Canvass, as the sorted tuple of its whole numbers."""
    out = set()
    for _page, _y, t in lines(path):
        m = re.fullmatch(r"Total((?: \d+)+)", t.strip())
        if m:
            out.add(tuple(sorted(int(x) for x in m.group(1).split())))
    return out


def load(con, cache, say=print):
    net.patient_lookups()
    folder = os.path.join(cache, "mt")
    gen = read_list("general", os.path.join(folder, "mt_2026_general_federal.json"), say)
    pri = read_list("primary", os.path.join(folder, "mt_2026_primary_federal.json"), say)
    book, canvass = os.path.join(folder, "mt_2026_primary_precinct.xlsx"), os.path.join(folder, "mt_2026_primary_state_canvass.pdf")
    net.download(PRECINCT_URL, book, max_age_days=30)
    net.download(CANVASS_URL, canvass, max_age_days=30)

    legend = {**pri["legend"], **gen["legend"]}
    def party_of(code):
        if code not in legend:
            raise SystemExit(f"Montana: the party code {code!r} is not in the list's key ({legend})")
        return legend[code]

    rec = sqlite3.connect(f"file:{os.path.join(HERE, 'congress_119.sqlite')}?mode=ro", uri=True)
    fixed = {}
    for full, first, last in rec.execute("SELECT official_full, first_name, last_name FROM legislators WHERE is_current = 1 AND state = 'MT'"):
        for form in (full, f"{first} {last}"):
            if form:
                fixed[form.upper()] = full or form
    def shown(caps):
        caps = re.sub(r"\s+", " ", caps.lstrip("*").strip())
        if caps in fixed:
            return fixed[caps]
        return re.sub(r"(['\"(])([a-z])", lambda m: m.group(1) + m.group(2).upper(), proper(caps))

    rows, off, write_ins, order = [], [], [], collections.Counter()
    nominee = {}
    for r in gen["rows"]:
        race = race_of(r["Race"], r["District"])
        if OFF.search(r["Status"]):
            off.append(r)
            continue
        if r["Status"] not in ON:
            raise SystemExit(f"Montana: a status on the general list that is not read ({r['Status']!r}, {r['Race']})")
        code, name = r["Party Preference"], shown(r["Name"])
        party = party_of(code)
        if code == "NON":                                        # a declared write-in (see the note above)
            write_ins.append(name)
            rows.append((race, "general", "2026-11-03", name, party, party_code("nonpartisan"), None, 0, 1, None, None, None, None, None,
                         "mt-sos-2026-general-list", f"{WRITE_IN} {CAPS}"))
            continue
        order[race] += 1
        given = int(r["Ballot Order"]) if r["Ballot Order"].isdigit() else order[race]
        rows.append((race, "general", "2026-11-03", name, party, party_code(party), given, 0, 0, None, None, None, None, None,
                     "mt-sos-2026-general-list", CAPS))
        if code in NOMINEE_CODES:
            nominee[(race, code)] = fold(r["Name"].lstrip("*"))

    # the primary list: who was on each party's June ballot, who it nominated, and who withdrew before it
    filed, nominated, withdrew = {}, {}, []
    for r in pri["rows"]:
        race, code = race_of(r["Race"], r["District"]), r["Party Preference"]
        if code not in NOMINEE_CODES:
            continue                                            # independents petition for November; they are not in a primary
        if OFF.search(r["Status"]):
            withdrew.append(f"{shown(r['Name'])}, {party_of(code)}, {r['Race'].title().replace('United States', 'U.S.')}")
        elif r["Status"] in ON:
            filed.setdefault((race, code), set()).add(fold(r["Name"].lstrip("*")))
            if r["Status"] == "NOMINATED":
                nominated[(race, code)] = fold(r["Name"].lstrip("*"))
        else:
            raise SystemExit(f"Montana: a status on the primary list that is not read ({r['Status']!r}, {r['Race']})")
    if nominated != nominee:
        raise SystemExit(f"Montana: the primary list's nominees and the November list's party candidates differ "
                         f"({sorted(set(nominated.items()) ^ set(nominee.items()))})")

    votes, counties = primary_votes(book)
    totals = canvass_totals(canvass)
    fields = 0
    for (race, code), cands in sorted(votes.items()):
        if {fold(n) for n in cands} != filed.get((race, code), set()):
            raise SystemExit(f"Montana: the precinct workbook's candidates for {race} {code} are not the primary list's")
        if tuple(sorted(v for _last, v in cands.values())) not in totals:
            raise SystemExit(f"Montana: the {race} {code} primary's totals match no Total line of the State Canvass")
        if len(cands) < 2:
            continue
        fields += 1
        party, total = party_of(code), sum(v for _last, v in cands.values())
        for name, (_last, v) in sorted(cands.items(), key=lambda kv: (-kv[1][1], kv[1][0])):
            rows.append((race, f"primary-{code}", PRIMARY, shown(name), party, party_code(party), None, 0, 0, v,
                         round(100 * v / total, 1) if total else None, "advanced" if nominee.get((race, code)) == fold(name) else "lost",
                         None, None, "mt-sos-2026-primary-precinct", CAPS_RESULTS))
    if set(filed) - set(votes):
        raise SystemExit(f"Montana: party primaries on the list with no votes in the workbook: {sorted(set(filed) - set(votes))}")

    general = [r for r in rows if r[1] == "general"]
    primary_rows = len(rows) - len(general)
    with con:
        con.execute("DELETE FROM candidates WHERE race_id LIKE '2026-MT-%'")
        con.executemany("INSERT OR REPLACE INTO candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        record_source(con, "mt-sos-2026-general-list", path=os.path.join(folder, "mt_2026_general_federal.json"), level="federal", state="MT",
                      kind="official candidate list", agency="Montana Secretary of State",
                      title="FEDERAL GENERAL 2026 Candidate List (November 3, 2026): United States Senator and United States Representative",
                      url=gen["url"], rows=len(gen["rows"]),
                      note=f"Every page of the grid read through its own pager ({gen['items']} rows, every office); the kept columns only, "
                           f"addresses, e-mail, web and phone never read. The list gives no ballot order; its order is kept. "
                           f"Withdrawn or removed, left off: {len(off)}. Declared write-ins (party NON, Non Partisan): {len(write_ins)}. "
                           f"Parties written out from the list's key.")
        record_source(con, "mt-sos-2026-primary-list", path=os.path.join(folder, "mt_2026_primary_federal.json"), level="federal", state="MT",
                      kind="official candidate list", agency="Montana Secretary of State",
                      title="FEDERAL PRIMARY 2026 Candidate List (June 2, 2026): United States Senator and United States Representative",
                      url=pri["url"], rows=len(pri["rows"]),
                      note="Used to check the primary results (who was on each party's ballot, whom it NOMINATED). Withdrawn or removed "
                           f"before the primary, not on its ballot: {'; '.join(withdrew) or 'none'}.")
        record_source(con, "mt-sos-2026-primary-precinct", path=book, level="federal", state="MT", kind="official results",
                      agency="Montana Secretary of State", title="2026 Primary Election Precinct by Precinct Report (June 2, 2026)",
                      url=PRECINCT_URL, rows=primary_rows,
                      note=f"Votes summed over every precinct of {counties} counties; the file carries no write-in votes, so a field's total "
                           "is the sum of its candidates' votes.")
        record_source(con, "mt-sos-2026-primary-canvass", path=canvass, level="federal", state="MT", kind="official results",
                      agency="Montana Secretary of State", title="2026 Statewide Primary Election Canvass",
                      url=CANVASS_URL, rows=len(votes),
                      note="Control: every federal party primary's totals in the precinct workbook match a Total line of the canvass.")
    say(f"    Montana: 2 House districts and the Senate race, {len(general)} candidates on the November ballot "
        f"({len(write_ins)} declared write-in, {len(off)} withdrawn or removed left off); {fields} party primaries with a field, "
        f"votes from the official precinct report, checked against the State Canvass")
    return len(general)
