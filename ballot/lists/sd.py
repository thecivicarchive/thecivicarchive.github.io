"""
South Dakota: the Secretary of State's 2026 General Election Candidate List (vip.sdsos.gov, election 774), a grid of
every contest sorted by office, the Senate and the House first. Its first page is read and every row of the two federal
contests taken, and the loader checks that a state office follows them there, so the federal block is whole. Columns
are taken by name, only Contest, Name, Party, Ballot Order, Status and the date of any withdrawal; the grid also carries
mailing addresses, which are never read. A withdrawn candidate is left off the November ballot. The list writes parties
as REP, DEM, IND and LIB; they are written out here. The June 2 primary is not loaded yet.
"""

import html as H
import json
import os
import re

from ballot.common import house_id, party_code, record_source, senate_id
from states import net

URL = "https://vip.sdsos.gov/candidatelist.aspx?eid=774"
KEEP = ("Contest", "Name", "Party", "Ballot Order", "Status", "WithdrawnDate")
PARTY = {"REP": "Republican", "DEM": "Democratic", "IND": "Independent", "LIB": "Libertarian"}
FEDERAL = {"United States Senator": lambda: senate_id("SD", 2), "United States Representative": lambda: house_id("SD", 0)}


def grid(page):
    heads = [re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", "", h))).strip()
             for h in re.findall(r'<th scope="col" class="rgHeader[^"]*"[^>]*>(.*?)</th>', page, re.S)]
    if not all(k in heads for k in KEEP):
        raise SystemExit(f"South Dakota: the candidate grid's columns changed ({heads})")
    idx = {k: heads.index(k) for k in KEEP}
    for tr in re.findall(r'<tr class="(?:rgRow|rgAltRow)"[^>]*>(.*?)</tr>', page, re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        if len(cells) != len(heads):
            raise SystemExit("South Dakota: a grid row does not line up with the grid's headings")
        yield {k: re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", "", cells[i]))).strip() for k, i in idx.items()}


def load(con, cache, say=print):
    net.patient_lookups()
    page = net.get(URL).decode("utf-8", "replace")
    if "2026 General Election" not in page:
        raise SystemExit("South Dakota: the candidate list page is no longer the 2026 General Election")
    all_rows = list(grid(page))
    fed = [r for r in all_rows if r["Contest"] in FEDERAL]
    last = max((i for i, r in enumerate(all_rows) if r["Contest"] in FEDERAL), default=-1)
    if not fed or last >= len(all_rows) - 1:
        raise SystemExit("South Dakota: the federal contests are not followed by a state office on the first page; the list may run on")
    path = os.path.join(cache, "sd", "sd_2026_general_federal.json")      # only the columns kept
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(fed, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    on = [r for r in fed if r["Status"] != "Withdrawn" and not r["WithdrawnDate"]]
    gone = [r for r in fed if r not in on]
    rows = []
    for r in on:
        party = PARTY.get(r["Party"], r["Party"])
        order = int(r["Ballot Order"]) if r["Ballot Order"].isdigit() else None
        rows.append((FEDERAL[r["Contest"]](), "general", "2026-11-03", r["Name"], party, party_code(party), order, 0, 0, None, None, None, None, None,
                     "sd-sos-2026-candidate-list", None))
    with con:
        con.execute("DELETE FROM candidates WHERE race_id LIKE '2026-SD-%'")
        con.executemany("INSERT OR REPLACE INTO candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        record_source(con, "sd-sos-2026-candidate-list", path=path, level="federal", state="SD", kind="official candidate list",
                      agency="South Dakota Secretary of State", title="2026 General Election Candidate List (U.S. Senate and U.S. House)",
                      url=URL, rows=len(fed),
                      note=f"Withdrawn, left off: {len(gone)}. Parties written out from the list's REP, DEM, IND, LIB; addresses never read.")
    say(f"    South Dakota: the Senate race and the at-large House seat, {len(rows)} candidates on the November ballot ({len(gone)} withdrawn left off)")
    return len(rows)
