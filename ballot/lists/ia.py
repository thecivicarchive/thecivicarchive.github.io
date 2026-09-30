"""
Iowa: the Secretary of State's Candidate List for the November 3, 2026 General Election (a PDF of every office, linked
as "candidate list" from sos.iowa.gov/general-election; the address changes when the list is reissued, so the page is
read first). Its columns are For the Office Of, Party, Ballot Name(s), Address, Phone, Email and Filing Date; each
entry is its own text block at its column's left edge. Only the first three columns are turned into text; addresses,
phones and e-mail stay in the file. An office is named on its first row only. Iowa's June 2 primaries are not loaded yet.
"""

import os
import re
import html as H
from collections import Counter
from urllib.parse import urljoin

from ballot.common import house_id, party_code, record_source, senate_id
from ballot.pdftext import PDF, join, rows as pdf_rows
from states import net

PAGE = "https://sos.iowa.gov/general-election"


def list_url():
    page = net.get(PAGE).decode("utf-8", "replace")
    for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', page, re.S | re.I):
        href, label = H.unescape(m.group(1)), re.sub(r"<[^>]+>|\s+", " ", m.group(2)).strip().lower()
        if label == "candidate list" and href.lower().endswith(".pdf"):
            return urljoin(PAGE, href)
    raise SystemExit("Iowa: the General Election page no longer links a \"candidate list\" PDF")


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
        m = re.fullmatch(r"United States Representative District (\d+)", office or "")
        race = house_id("IA", int(m.group(1))) if m else (senate_id("IA", 2) if office == "United States Senator" else None)
        if race:
            out.append((race, party, name))
    return out


def load(con, cache, say=print):
    net.patient_lookups()
    url = list_url()
    path = os.path.join(cache, "ia", "ia_candidate_list_2026_general.pdf")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    net.download(url, path, max_age_days=2)
    listed = federal_rows(path)
    order = {}
    rows = []
    for race, party, name in listed:
        order[race] = order.get(race, 0) + 1
        rows.append((race, "general", "2026-11-03", name, party, party_code(party), order[race], 0, 0, None, None, None, None, None, "ia-sos-2026-candidate-list", None))
    with con:
        con.execute("DELETE FROM candidates WHERE race_id LIKE '2026-IA-%'")
        con.executemany("INSERT OR REPLACE INTO candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        record_source(con, "ia-sos-2026-candidate-list", path=path, level="federal", state="IA", kind="official candidate list",
                      agency="Iowa Secretary of State", title="Candidate List, November 3, 2026 General Election",
                      url=url, rows=len(rows), note="Office, party and ballot name read; the address, phone and e-mail columns are never read.")
    say(f"    Iowa: {len({r[0] for r in rows if '-H' in r[0]})} House districts and {'the' if any('-S' in r[0] for r in rows) else 'no'} Senate race, "
        f"{len(rows)} candidates on the November ballot")
    return len(rows)
