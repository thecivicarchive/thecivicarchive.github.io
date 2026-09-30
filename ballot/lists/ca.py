"""
California: the Secretary of State's Statement of Vote for the June 2, 2026 primary, in its machine-readable form
("CSV Files - Voter Nominated", an .xlsx with one row per county, contest and candidate: name, party preference,
incumbent and write-in flags, votes). The county rows are added up to district totals here.

California's primary is top-two: every candidate, of every party preference, is on one primary ballot, and the two
who receive the most votes advance to the November general election, whatever their parties (a tie for second
advances everyone tied). So the primary field is every candidate with their votes, and the November ballot is the
top two. The Secretary's Certified List of Candidates for November 3 (a PDF, fingerprinted in ballot_sources) is
the list printed on the ballot; checking the two against each other is on the list of next steps.
"""

import collections
import os

import openpyxl

from ballot.common import house_id, party_code, record_source
from states import net

URL = "https://elections.cdn.sos.ca.gov/sov/2026-primary/sov/csv-voter-nominated.xlsx"
PAGE = "https://www.sos.ca.gov/elections/prior-elections/statewide-election-results/primary-election-june-2-2026/statement-vote"
CERT = "https://elections.cdn.sos.ca.gov/statewide-elections/2026-general/cert-list-candidates.pdf"
PRIMARY = "2026-06-02"


def load(con, cache, say=print):
    path = os.path.join(cache, "ca_sov_2026_primary_voter_nominated.xlsx")
    net.download(URL, path, max_age_days=60)
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    it = wb.worksheets[0].iter_rows(values_only=True)
    head = next(it)
    field = collections.defaultdict(dict)      # district -> candidate id -> [name, party, incumbent, write-in, votes]
    for r in it:
        rec = dict(zip(head, r))
        contest = str(rec.get("Contest Name") or "")
        if not contest.startswith("United States Representative District "):
            continue
        d = int(contest.rsplit(" ", 1)[1])
        c = field[d].setdefault(rec["Candidate ID"], [str(rec["Candidate Name"]).strip(), (rec["Party Name"] or "").strip(),
                                                      rec["Incumbent Flag"] == "Y", rec["Write-in Flag"] == "Y", 0])
        c[4] += int(rec["Vote Total"] or 0)
    rows = []
    for d, cands in sorted(field.items()):
        ranked = sorted(cands.values(), key=lambda c: (-c[4], c[0]))
        total = sum(c[4] for c in ranked) or 1
        second = ranked[1][4] if len(ranked) > 1 else ranked[0][4]
        for c in ranked:
            went = c[4] >= second
            rows.append((house_id("CA", d), "primary", PRIMARY, c[0], c[1], party_code(c[1]), None, int(c[2]), int(c[3]),
                         c[4], round(100 * c[4] / total, 2), "advanced" if went else "lost", None, None, "ca-sov-2026-primary", None))
            if went:
                rows.append((house_id("CA", d), "general", "2026-11-03", c[0], c[1], party_code(c[1]), None, int(c[2]), int(c[3]),
                             None, None, None, None, None, "ca-sov-2026-primary",
                             "Advanced from the June 2 top-two primary. California prints each candidate's party preference."))
    with con:
        con.execute("DELETE FROM candidates WHERE race_id LIKE '2026-CA-%'")
        con.executemany("INSERT OR REPLACE INTO candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        record_source(con, "ca-sov-2026-primary", path=path, level="federal", state="CA", kind="official results",
                      agency="California Secretary of State", title="Statement of Vote, June 2, 2026 Primary Election: CSV Files - Voter Nominated",
                      url=URL, rows=sum(1 for r in rows if r[1] == "primary"),
                      note=f"Found on {PAGE}. County rows added up to district totals.")
    general = sum(1 for r in rows if r[1] == "general")
    say(f"    California: {len(field)} House districts, {len(rows) - general} primary candidates, {general} on the November ballot")
    return len(field)
