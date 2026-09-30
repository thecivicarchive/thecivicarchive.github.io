"""
New York: the State Board of Elections' Certification for the November 3, 2026 General Election (the accessible PDF
of September 17, 2026, 136 pages), read with ballot/pdftext.py. Each office is a table: "Office", "District",
"Counties", then one row per party line with the party on the left and the candidate on the right, the candidate's
given names printed above the party's row and the family name below it. A line with no candidate is left blank.

New York lets several parties nominate the same person (fusion): a candidate is listed once, with every line they
hold, in the order the lines appear on the ballot, and ordered by their first line. The file sits behind a Cloudflare
check that sometimes refuses a plain request and then lets it through; the kit's patient download is all that is
used. New York's June 23 primaries are not loaded yet.
"""

import os
import re

from ballot.common import house_id, party_code, record_source
from ballot.pdftext import PDF, join, rows
from states import net

URL = "https://elections.ny.gov/system/files/documents/2026/09/accessible-2026-general-ballot-certification-9.17.2026.pdf"
PAGE = "https://elections.ny.gov/ballot-certifications-elections"


def load(con, cache, say=print):
    path = os.path.join(cache, "ny_2026_general_ballot_certification.pdf")
    net.patient_lookups()
    net.download(URL, path, max_age_days=30)
    pdf = PDF(open(path, "rb").read())
    races, office, district, split = {}, None, None, None
    counties = False      # a long "Counties:" list wraps onto lines of its own, until "Vote For:"
    for page, res in pdf.pages():
        parties, names = [], []
        for y, rs in rows(pdf, page, res):      # the page's printed rows, top to bottom
            text = join(rs)
            if text.startswith("Counties:"):
                counties = True
            if text.startswith("Vote For:"):
                counties = False
                continue
            if counties:
                continue
            m = re.match(r"^Office:\s*(.+)$", text)
            if m:
                office, district = m.group(1).strip(), None
                continue
            m = re.match(r"^District:\s*(\d+)", text)
            if m:
                district = int(m.group(1))
                continue
            if "Candidate Name" in text:      # the name column starts at the first piece after the word "Party"
                ordered = sorted(rs, key=lambda r: r[0])
                split = next((ordered[k][0] - 4 for k in range(1, len(ordered)) if join(ordered[:k]).endswith("Party")), split)
                continue
            if re.match(r"^(Counties:|Vote For:|Certification for the)", text) or split is None:
                continue
            left, right = join([r for r in rs if r[0] < split]), join([r for r in rs if r[0] >= split])
            if left:
                parties.append((y, left, office, district))
            if right:
                names.append((y, right, office, district))
        for y, party, off, dist in parties:      # a party's row, and the name printed just above and just below it
            if off != "Representative in Congress" or not dist:
                continue
            mine = sorted((n for n in names if abs(n[0] - y) <= 10 and n[2] == off and n[3] == dist), key=lambda n: -n[0])
            races.setdefault(dist, []).append((party, re.sub(r"\s+", " ", " ".join(n[1] for n in mine)).strip()))
    out = []
    for dist, lines_ in sorted(races.items()):
        people, order = {}, []
        for party, name in lines_:
            if not name:
                continue
            if name not in people:
                people[name] = []
                order.append(name)
            people[name].append(party)
        for k, name in enumerate(order, start=1):
            lines_held = people[name]
            first_major = next((p for p in lines_held if party_code(p) in ("D", "R")), lines_held[0])
            out.append((house_id("NY", dist), "general", "2026-11-03", name, ", ".join(lines_held), party_code(first_major), k, 0, 0,
                         None, None, None, None, None, "ny-sboe-2026-general-cert",
                         ("On the ballot on " + str(len(lines_held)) + " party lines: " + ", ".join(lines_held) + ".") if len(lines_held) > 1 else None))
    with con:
        con.execute("DELETE FROM candidates WHERE race_id LIKE '2026-NY-%'")
        con.executemany("INSERT OR REPLACE INTO candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", out)
        record_source(con, "ny-sboe-2026-general-cert", path=path, level="federal", state="NY", kind="official candidate list",
                      agency="New York State Board of Elections", title="Certification for the November 3, 2026 General Election (September 17, 2026)",
                      url=URL, published="2026-09-17", rows=len(out), note=f"Listed on {PAGE}. Several parties may nominate one candidate (fusion).")
    say(f"    New York: {len(races)} House districts, {len(out)} candidates on the November ballot "
        f"({sum(1 for r in out if r[15])} on more than one party line)")
    return len(out)
