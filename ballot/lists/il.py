"""
Illinois: the State Board of Elections' Website Candidate List for the General Election of November 3, 2026 (the
"Print This List" PDF of the election's Candidate List page, every office, "All Candidates as of" the moment it is
printed), read with ballot/pdftext.py. Under each office, one line per candidate: party, name, filing date and time.
Candidates who filed by petition as independents or new parties have their address on the next lines; a candidate
the Board removed or who withdrew is marked there ("REMOVED 7/21/2026"). Addresses are never kept; removed and
withdrawn candidates are left off the November ballot. Illinois's March 17 primaries are not loaded yet.
"""

import os
import re

from ballot.common import house_id, party_code, record_source, senate_id
from ballot.pdftext import lines
from states import net

PAGE = "https://elections.il.gov/ElectionOperations/CandidateList.aspx?ElectionID=sejIrI%2bQmww%3d"
URL = ("https://elections.il.gov/ElectionOperations/EOPDFViewer.aspx?ElectionID=sejIrI%2bQmww%3d"
       "&QueryType=xF443FTCAJbIL3atac%2fUjEg7Y4yklgT1&Status=P2wRQXkiFoo%3d")
CAND = re.compile(r"^(?P<rest>.+?) (?P<date>\d{1,2}/\d{1,2}/\d{4}) \d{1,2}:\d\d ?[AP]M$")


def split_party(rest):
    """DEMOCRATIC La Shawn K. Ford -> (DEMOCRATIC, La Shawn K. Ford): the party is the words before the first word
    with a small letter in it."""
    words = rest.split()
    k = next((i for i, w in enumerate(words) if re.search(r"[a-z]", w)), None)
    if not k:
        return None, None
    return " ".join(words[:k]), " ".join(words[k:])


def load(con, cache, say=print):
    path = os.path.join(cache, "il_2026_general_candidate_list.pdf")
    net.patient_lookups()
    net.download(URL, path, max_age_days=2)
    office, out, removed = None, [], []
    for page, y, text in lines(path):
        if re.fullmatch(r"UNITED STATES SENATOR", text):
            office = ("S", 2)
            continue
        m = re.fullmatch(r"(\d+)(ST|ND|RD|TH) CONGRESS", text)
        if m:
            office = ("H", int(m.group(1)))
            continue
        if re.fullmatch(r"[0-9A-Z ,.&'()-]+", text) and not CAND.match(text) and not re.search(r"\d{1,2}/\d{1,2}/\d{4}", text):
            if re.search(r"SENATE|REPRESENTATIVE|GOVERNOR|ATTORNEY|SECRETARY|COMPTROLLER|TREASURER|CIRCUIT|SUPREME|APPELLATE|JUDGE|DISTRICT", text):
                office = None      # the next office's heading
            continue
        if office is None:
            continue
        if re.search(r"\b(REMOVED|WITHDRAWN|DISQUALIFIED)\b", text):      # on the address line under a candidate
            if out:
                removed.append(out.pop())
            continue
        if re.match(r"^\d", text):      # an address line
            continue
        m = CAND.match(text)
        if m:
            party, name = split_party(m.group("rest"))
            if party and name:
                race = senate_id("IL", 2) if office[0] == "S" else house_id("IL", office[1])
                out.append([race, party.title(), name])
            continue
    rows = [(race, "general", "2026-11-03", name, party, party_code(party), None, 0, 0, None, None, None, None, None, "il-sbe-2026-candidate-list", None)
            for race, party, name in out]
    with con:
        con.execute("DELETE FROM candidates WHERE race_id LIKE '2026-IL-%'")
        con.executemany("INSERT OR REPLACE INTO candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        record_source(con, "il-sbe-2026-candidate-list", path=path, level="federal", state="IL", kind="official candidate list",
                      agency="Illinois State Board of Elections", title="Website Candidate List, General Election November 3, 2026 (all candidates as printed)",
                      url=URL, rows=len(rows), note=f"The Candidate List page's Print This List. Removed or withdrawn, left off: {len(removed)}. Addresses not kept.")
    say(f"    Illinois: {len({r[0] for r in rows if '-H' in r[0]})} House districts and {'the' if any('-S' in r[0] for r in rows) else 'no'} Senate race, "
        f"{len(rows)} candidates on the November ballot ({len(removed)} removed or withdrawn left off)")
    return len(rows)
