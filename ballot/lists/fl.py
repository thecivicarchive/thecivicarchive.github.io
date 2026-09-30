"""
Florida: the Division of Elections' candidate list for the 2026 election cycle, federal offices, downloaded from its
Candidate Tracking System (downloadcanlist.asp posts to extractCanList.asp and answers with a tab-separated file).
Each row is one candidate with a status: Qualified (on the November ballot), Unopposed (elected without appearing
on the ballot, section 101.151, Florida Statutes), Defeated (lost a primary), Withdrew, or Did Not Qualify.

Florida's primaries are closed, one per party, on August 18, 2026; a party with a single qualified candidate holds
none. So a party's primary field is its candidates who were Qualified, Unopposed or Defeated, with the winner
marked; the votes come from the official results, not yet loaded here. The file also carries addresses, telephone
numbers, e-mail and treasurers' names; none of it is read.
"""

import csv
import io
import os
import time
import urllib.parse
from urllib.request import Request, urlopen

from ballot.common import house_id, party_code, record_source, senate_id
from states import net

PAGE = "https://dos.elections.myflorida.com/candidates/downloadcanlist.asp"
POST = "https://dos.elections.myflorida.com/candidates/extractCanList.asp"
FORM = {"elecID": "20261103-GEN", "office": "FED", "status": "All", "cantype": "STA"}
PRIMARY = "2026-08-18"
ON_BALLOT = ("Qualified", "Unopposed")


def fetch(path, max_age_days=2):
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < max_age_days * 86400:
        return
    net.patient_lookups()
    req = Request(POST, data=urllib.parse.urlencode(FORM).encode(), method="POST",
                  headers={"User-Agent": net.UA, "Referer": PAGE, "Content-Type": "application/x-www-form-urlencoded"})
    with urlopen(req, timeout=180) as r:
        data = r.read()
    if b"NameLast" not in data[:400]:
        raise SystemExit("Florida's candidate download did not answer with the candidate file; try again later")
    open(path, "wb").write(data)


def load(con, cache, say=print):
    path = os.path.join(cache, "fl_candidates_20261103_federal.txt")
    fetch(path)
    keep = ("OfficeDesc", "Juris1num", "StatusDesc", "PartyCode", "PartyDesc", "NameFirst", "NameMiddle", "NameLast")
    rows = [{k: (r.get(k) or "").strip() for k in keep}
            for r in csv.DictReader(io.StringIO(open(path, encoding="utf-8", errors="replace").read()), delimiter="\t")]
    senate = con.execute("SELECT race_id FROM races WHERE state = 'FL' AND office = 'U.S. Senate'").fetchall()
    out, fields = [], {}
    for r in rows:
        if r["OfficeDesc"] == "United States Representative":
            race = house_id("FL", int(r["Juris1num"] or 0))
        elif r["OfficeDesc"] == "United States Senator" and len(senate) == 1:
            race = senate[0][0]
        else:
            continue
        name = " ".join(x for x in (r["NameFirst"], r["NameMiddle"], r["NameLast"]) if x)
        code, status = party_code(r["PartyDesc"]), r["StatusDesc"]
        write_in = int(r["PartyCode"] == "WRI")
        if status in ON_BALLOT:
            note = ("Unopposed. Florida law (section 101.151) leaves an unopposed candidate off the general election ballot."
                    if status == "Unopposed" else ("Write-in candidate: the name is not printed on the ballot." if write_in else None))
            out.append((race, "general", "2026-11-03", name, r["PartyDesc"], code, None, 0, write_in, None, None,
                        "unopposed" if status == "Unopposed" else None, None, None, "fl-dos-2026-candidates", note))
        if status in ON_BALLOT + ("Defeated",) and r["PartyCode"] in ("REP", "DEM", "LPF", "GRE"):
            fields.setdefault((race, r["PartyCode"]), []).append((name, r["PartyDesc"], code, status))
    for (race, pc), cands in fields.items():
        if len(cands) < 2:      # one candidate: that party held no primary for this race
            continue
        for name, party, code, status in cands:
            out.append((race, f"primary-{pc}", PRIMARY, name, party, code, None, 0, 0, None, None,
                        "lost" if status == "Defeated" else "advanced", None, None, "fl-dos-2026-candidates", None))
    with con:
        con.execute("DELETE FROM candidates WHERE race_id LIKE '2026-FL-%'")
        con.executemany("INSERT OR REPLACE INTO candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", out)
        record_source(con, "fl-dos-2026-candidates", path=path, level="federal", state="FL", kind="official candidate list",
                      agency="Florida Department of State, Division of Elections", title="Candidate Tracking System: candidate list, 2026 election, federal offices",
                      url=PAGE, rows=len(rows), note="Downloaded as a tab-separated file (all statuses). Primary votes not yet loaded.")
    general = sum(1 for r in out if r[1] == "general")
    say(f"    Florida: {general} candidates on or qualified for the November ballot; {len(out) - general} in "
        f"{sum(1 for v in fields.values() if len(v) > 1)} party primaries")
    return general
