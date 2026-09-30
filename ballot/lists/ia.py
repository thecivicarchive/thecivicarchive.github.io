"""
Iowa: the Secretary of State's Candidate List for the November 3, 2026 General Election (a PDF of every office, linked
as "candidate list" from sos.iowa.gov/general-election; the address changes when the list is reissued, so the page is
read first). Its columns are For the Office Of, Party, Ballot Name(s), Address, Phone, Email and Filing Date; each
entry is its own text block at its column's left edge. Only the first three columns are turned into text; addresses,
phones and e-mail stay in the file. An office is named on its first row only.

The June 2, 2026 primaries come from two more of the Secretary's files. The Candidate List for the June 2, 2026 Primary
Election (the same layout, linked as "candidate list" from sos.iowa.gov/primary-election, read the same way, first three
columns only) says who was on each party's primary ballot and how the list prints their names. The Election Canvass
Summary (linked as "Official Canvass by County" in the Primary row of "2026 Election Results" on
sos.iowa.gov/iowans/election-results-statistics; canvass date printed on its first page) gives the votes: one section
per office and party ("United States Representative District 2 - Dem."), the candidates across the top, then county by
county Election Day, Absentee and Total rows, and a statewide TOTAL. Only the statewide rows are stored; the county rows
are added up and must come to the statewide Total, Election Day plus Absentee must equal it, and the candidates, write-ins,
under votes and over votes must add up to its Total column. Every name in the canvass must match the primary list.

A party primary becomes a field when two or more candidates were on that party's ballot. A candidate's share is of the
votes cast for the office in that party's primary: the candidates' votes and the write-ins. Write-ins are not listed;
under votes and over votes are left out of the total. Iowa nominates the leader only with at least 35 percent of those
votes; otherwise the party's convention chooses the nominee. Then the candidate on the November list for that party is
the one who advanced, and every row of that field says so. In 2026 every congressional primary was won outright.

Parties: the lists print Republican, Democratic, Libertarian and No Party in full; the canvass writes REP and DEM under
its names and "- Rep." and "- Dem." in its headings, which are read as Republican and Democratic. Libertarians and the
candidates of no party are nominated by convention or petition and have no primary.
"""

import os
import re
import html as H
from collections import Counter
from urllib.parse import urljoin

from ballot.common import fold, house_id, party_code, record_source, senate_id
from ballot.pdftext import PDF, join, lines, rows as pdf_rows
from states import net

PAGE = "https://sos.iowa.gov/general-election"
PRIMARY_PAGE = "https://sos.iowa.gov/primary-election"
RESULTS = "https://sos.iowa.gov/iowans/election-results-statistics"
PRIMARY = "2026-06-02"
THRESHOLD = 35.0
HEADING = re.compile(r"^(?P<office>[A-Z][^,]*?) - (?P<party>[A-Z][a-z]+)\.$")
ROW = re.compile(r"^(?:(?P<place>[A-Za-z][A-Za-z' .]*?) ?)?(?P<kind>Election Day|Absentee|Total) (?P<nums>\d[\d,]*(?: \d[\d,]*)*)$")
COLUMNS = "Write-in Under Votes Over Votes Total"
FURNITURE = re.compile(r"^(IOWA SECRETARY OF STATE|2026 Primary Election CANVASS SUMMARY|Page \d+ of \d+)$")
CANVASS_PARTY = {"Rep": ("Republican", "REP"), "Dem": ("Democratic", "DEM")}
SUFFIX = re.compile(r"^(Jr|Sr|II|III|IV|V)\.?$")


def clean(fragment):
    return re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


def list_url(page_url=PAGE, what="General Election"):
    page = net.get(page_url).decode("utf-8", "replace")
    for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', page, re.S | re.I):
        href, label = H.unescape(m.group(1)), re.sub(r"<[^>]+>|\s+", " ", m.group(2)).strip().lower()
        if label == "candidate list" and href.lower().endswith(".pdf"):
            return urljoin(page_url, href)
    raise SystemExit(f"Iowa: the {what} page no longer links a \"candidate list\" PDF")


def canvass_url():
    """The Primary row's "Official Canvass by County" under "2026 Election Results"."""
    page = net.get(RESULTS).decode("utf-8", "replace")
    sec = re.search(r">\s*2026 Election Results\s*</h2>(.*?)(?:<h2|$)", page, re.S)
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", sec.group(1) if sec else "", re.S):
        tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        if len(tds) >= 2 and clean(tds[0]) == "Primary":
            for href, label in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', tds[1], re.S):
                if clean(label) == "Official Canvass by County" and href.lower().endswith(".pdf"):
                    return urljoin(RESULTS, H.unescape(href))
    raise SystemExit("Iowa: the Election Results & Statistics page no longer links the 2026 primary's \"Official Canvass by County\"")


def cells(runs):
    """A printed row's pieces grouped into table cells: [(x, pieces)]. Every cell is its own text block starting at its
    column's left edge; a gap wider than six points between pieces starts the next cell."""
    out = []
    for r in sorted(runs, key=lambda r: r[0]):
        if out and r[0] - out[-1][2] <= 6:
            out[-1][1].append(r)
            out[-1][2] = max(out[-1][2], r[4])
        else:
            out.append([r[0], [r], r[4]])
    return [(x, rs) for x, rs, _end in out]


def federal_rows(path):
    """(race, party, name) for the candidates for Congress. The headings are centred over their columns and the entries
    are not, so the columns' left edges are found from the entries: the places where cells start again and again.
    The first three are the office, the party and the ballot name; cells from the fourth on (address, phone, e-mail,
    date) are never turned into text."""
    pdf = PDF(open(path, "rb").read())
    body = []
    for page, res in pdf.pages():
        head = False
        for _y, runs in pdf_rows(pdf, page, res):
            if not head:      # each page opens with a note, the title and the headings; the table starts after them
                head = "Ballot Name(s)" in join([r for r in runs if r[0] < 300])
                continue
            body.append(cells(runs))
    if not body:
        raise SystemExit("Iowa: the candidate list's column headings were not found")
    full = Counter(tuple(round(x) for x, _rs in row[:4]) for row in body if len(row) >= 4 and row[0][0] < 50)      # rows that name an office
    if not full:
        raise SystemExit("Iowa: no row of the candidate list names an office")
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
        if not (party and name):      # a footer, or a line that wrapped: it neither names an office nor a candidate
            continue
        if got.get(0):
            office = got[0]
        race = race_of(office or "")
        if race:
            out.append((race, party, name))
    return out


def race_of(office):
    m = re.fullmatch(r"United States Representative District (\d+)", office)
    return house_id("IA", int(m.group(1))) if m else (senate_id("IA", 2) if office == "United States Senator" else None)


def list_title(path):
    """The title lines above the headings on the list's first page (the office's own note on change requests is skipped)."""
    out = []
    for _p, _y, text in lines(path, first=1, last=1):
        if "Ballot Name" in text:
            break
        out.append(text)
    return out


def names_of(text):
    """'Dave Dawson, Stephanie Steiner,Ashley WolfTornabane,' -> three names; a Jr. or III after a comma stays with its name."""
    out = []
    for piece in (s.strip() for s in text.split(",")):
        if not piece:
            continue
        if out and SUFFIX.match(piece):
            out[-1] += ", " + piece
        else:
            out.append(piece)
    return out


def canvass(path):
    """(published, {(race, party): {"names", "votes", "write_in", "under", "over", "total"}}) for every congressional party
    primary in the canvass summary, from its statewide rows, each checked against the county rows."""
    L = lines(path)
    first = " ".join(t for p, _y, t in L if p == 1)
    when = re.search(r"Canvass date: (\d\d)/(\d\d)/(\d{4})", first)
    if "2026 Primary Election held on Tuesday, June 02, 2026" not in first or not when:
        raise SystemExit("Iowa: the canvass summary is not the June 2, 2026 primary's (or its first page changed)")
    published = f"{when.group(3)}-{when.group(1)}-{when.group(2)}"
    out, sec = {}, None

    def close(s):
        if s is None:
            return
        where = f"the canvass section {s['title']!r}"
        state = s["state"]
        if set(state) != {"Election Day", "Absentee", "Total"}:
            raise SystemExit(f"Iowa: {where} has no statewide TOTAL rows")
        if [a + b for a, b in zip(state["Election Day"], state["Absentee"])] != state["Total"]:
            raise SystemExit(f"Iowa: in {where}, Election Day plus Absentee is not the statewide Total")
        if s["counties"] != state["Total"]:
            raise SystemExit(f"Iowa: in {where}, the county Total rows add up to {s['counties']}, not the statewide {state['Total']}")
        t = state["Total"]
        if sum(t[:-1]) != t[-1]:
            raise SystemExit(f"Iowa: in {where}, the candidates, write-ins, under and over votes do not add up to the Total column")
        n = len(s["names"])
        out[(s["race"], s["party"])] = {"names": s["names"], "votes": t[:n], "write_in": t[n], "under": t[n + 1],
                                        "over": t[n + 2], "total": t[n + 3], "code": s["code"]}

    for page, _y, text in L:
        h = HEADING.match(text)
        if h:
            close(sec)
            race = race_of(h.group("office"))
            sec = None
            if race:
                if h.group("party") not in CANVASS_PARTY:
                    raise SystemExit(f"Iowa: a congressional primary for a party the loader does not know: {text!r}")
                party, code = CANVASS_PARTY[h.group("party")]
                sec = {"title": text, "race": race, "party": party, "code": code, "names": None, "buf": [], "want": "names",
                       "page": page, "state": {}, "statewide": False, "counties": None}
            continue
        if sec is None or FURNITURE.match(text):
            continue
        if page != sec["page"]:      # every page of a section repeats the candidates' names, the column headings and the parties
            sec["page"], sec["buf"], sec["want"] = page, [], "names"
        if sec["want"] == "names":
            if text == COLUMNS:
                names = names_of(" ".join(sec["buf"]))
                if sec["names"] is None:
                    sec["names"] = names
                elif names != sec["names"]:
                    raise SystemExit(f"Iowa: {sec['title']!r} names different candidates on page {page}: {names}")
                sec["want"] = "parties"
            else:
                sec["buf"].append(text)
            continue
        if sec["want"] == "parties":
            codes = text.split()
            if len(codes) != len(sec["names"]) or set(codes) != {sec["code"]}:
                raise SystemExit(f"Iowa: under {sec['title']!r} the party line reads {text!r}")
            sec["want"] = "rows"
            continue
        m = ROW.match(text)
        if not m:
            raise SystemExit(f"Iowa: a line in {sec['title']!r} the loader does not recognise: {text!r}")
        nums = [int(v.replace(",", "")) for v in m.group("nums").split()]
        if len(nums) != len(sec["names"]) + 4:
            raise SystemExit(f"Iowa: a row of {sec['title']!r} has {len(nums)} numbers for {len(sec['names'])} candidates: {text!r}")
        if m.group("place") == "TOTAL":
            sec["statewide"] = True
        if sec["statewide"]:
            sec["state"][m.group("kind")] = nums
        elif m.group("kind") == "Total":
            sec["counties"] = nums if sec["counties"] is None else [a + b for a, b in zip(sec["counties"], nums)]
    close(sec)
    return published, out


def load(con, cache, say=print):
    net.patient_lookups()
    folder = os.path.join(cache, "ia")
    os.makedirs(folder, exist_ok=True)
    url = list_url()
    path = os.path.join(folder, "ia_candidate_list_2026_general.pdf")
    net.download(url, path, max_age_days=2)
    listed = federal_rows(path)
    order = {}
    rows = []
    for race, party, name in listed:
        order[race] = order.get(race, 0) + 1
        rows.append((race, "general", "2026-11-03", name, party, party_code(party), order[race], 0, 0, None, None, None, None, None, "ia-sos-2026-candidate-list", None))

    # the June 2 primary: who was on each party's ballot, and the canvassed votes
    p_url = list_url(PRIMARY_PAGE, "Primary Election")
    p_path = os.path.join(folder, "ia_candidate_list_2026_primary.pdf")
    net.download(p_url, p_path, max_age_days=30)
    if "June 2, 2026 Primary Election" not in list_title(p_path):
        raise SystemExit("Iowa: the Primary Election page's candidate list is not the June 2, 2026 primary's")
    c_url = canvass_url()
    c_path = os.path.join(folder, "ia_canvass_summary_2026_primary.pdf")
    net.download(c_url, c_path, max_age_days=30)
    published, counted = canvass(c_path)
    ballots = {}
    for race, party, name in federal_rows(p_path):
        ballots.setdefault((race, party), []).append(name)
    if set(ballots) != set(counted):
        raise SystemExit(f"Iowa: the primary list and the canvass cover different party primaries: "
                         f"{sorted(set(ballots) ^ set(counted))}")
    nominee = {(race, party): fold(name) for race, party, name in listed}
    fields, convention, odd = 0, [], []
    for (race, party), names in sorted(ballots.items()):
        c = counted[(race, party)]
        if sorted(fold(n) for n in names) != sorted(fold(n) for n in c["names"]):
            raise SystemExit(f"Iowa: {race} {party}: the primary list names {names}, the canvass {c['names']}")
        if len(names) < 2:
            continue
        fields += 1
        votes = {fold(n): v for n, v in zip(c["names"], c["votes"])}
        total = sum(c["votes"]) + c["write_in"]
        top = max(votes, key=votes.get)
        outright = bool(total) and 100 * votes[top] / total >= THRESHOLD
        chosen = top if outright else nominee.get((race, party))
        note = None
        if not outright:
            convention.append(f"{race} {party}")
            note = "No candidate won the 35 percent of the vote Iowa law requires, so the party's convention chose the nominee."
        elif nominee.get((race, party)) != top:
            odd.append(f"{race} {party}")
            note = "Won the primary, but is not on the November list for this party."
        for name in names:
            v = votes[fold(name)]
            rows.append((race, f"primary-{c['code']}", PRIMARY, name, party, party_code(party), None, 0, 0, v,
                         round(100 * v / total, 1) if total else None, "advanced" if fold(name) == chosen else "lost",
                         None, None, "ia-sos-2026-primary-canvass", note))
    with con:
        con.execute("DELETE FROM candidates WHERE race_id LIKE '2026-IA-%'")
        con.executemany("INSERT OR REPLACE INTO candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        record_source(con, "ia-sos-2026-candidate-list", path=path, level="federal", state="IA", kind="official candidate list",
                      agency="Iowa Secretary of State", title="Candidate List, November 3, 2026 General Election",
                      url=url, rows=len(listed), note="Office, party and ballot name read; the address, phone and e-mail columns are never read.")
        record_source(con, "ia-sos-2026-primary-candidate-list", path=p_path, level="federal", state="IA", kind="official candidate list",
                      agency="Iowa Secretary of State", title="Candidate List, June 2, 2026 Primary Election",
                      url=p_url, rows=sum(len(v) for v in ballots.values()),
                      note="Who was on each party's primary ballot for Congress, and the names as printed; office, party and ballot name read, "
                           "the address, phone and e-mail columns never read.")
        record_source(con, "ia-sos-2026-primary-canvass", path=c_path, level="federal", state="IA", kind="official results",
                      agency="Iowa Secretary of State", title=f"Election Canvass Summary, 2026 Primary Election held on Tuesday, June 02, 2026 "
                                                              f"(canvass date {published[5:7]}/{published[8:]}/{published[:4]})",
                      url=c_url, published=published, rows=sum(len(v["names"]) for v in counted.values()),
                      note="Statewide totals for each congressional party primary, checked against the county rows. Shares are of the "
                           "candidates' votes plus write-ins; write-ins are not listed, under and over votes are left out. "
                           + (f"Went to a party convention (no one reached 35 percent): {', '.join(convention)}." if convention
                              else "Every congressional primary was won outright (35 percent or more); none went to a convention.")
                           + (f" Primary winner not on the November list: {', '.join(odd)}." if odd else ""))
    n = len(listed)
    say(f"    Iowa: {len({r[0] for r in listed if '-H' in r[0]})} House districts and {'the' if any('-S' in r[0] for r in listed) else 'no'} Senate race, "
        f"{n} candidates on the November ballot; {fields} party primaries with a field, votes from the official canvass"
        + (f"; to a convention: {', '.join(convention)}" if convention else "")
        + (f"; primary winner not on the November list: {', '.join(odd)}" if odd else ""))
    return n
