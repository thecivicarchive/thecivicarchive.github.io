"""
ballot/fec26.py - the 2026 cycle from the Federal Election Commission's bulk files, for every House and Senate
candidate, not only sitting members: who registered, what each campaign reported (money from people as a total,
from committees, from the party, from the candidate), and every itemized payment by a committee to, for or against
a candidate.

It reads the same four cached files as load_donors.py (cn26, cm26, weball26, pas226 in fec_cache/, fetched again
when a week old) with the same rules, imported from it: memo lines are left out, as the FEC's own totals leave them
out; a passed-along earmark keeps only a yes/no flag, never the memo text; the kinds of payment are the same. Only
organizations are ever named; the treasurer and address columns of the committee file are not read.
"""

import os

from ballot.common import HERE
from load_donors import FEC, KIND, download, iso, money, patient_lookups, rows

CACHE = os.path.join(HERE, "fec_cache")


def load(con, say=print):
    patient_lookups()
    os.makedirs(CACHE, exist_ok=True)
    paths = {}
    for stem in ("cn", "cm", "weball", "pas2"):
        paths[stem] = os.path.join(CACHE, f"{stem}26.zip")
        if download(f"{FEC}2026/{stem}26.zip", paths[stem], 7):
            say(f"    fetched {stem}26.zip ({os.path.getsize(paths[stem]) / 1e6:,.1f} MB)")
    cands = {}
    for f in rows(paths["cn"]):                                  # candidates registered for the 2026 cycle
        if len(f) >= 10 and f[5] in ("H", "S") and f[3] == "2026":
            dist = f[6].strip() if f[5] == "H" else ""
            cands[f[0]] = (f[0], f[1].strip(), f[2].strip(), f[5], f[4].strip(), dist, f[7].strip(), f[8].strip(), f[9].strip())
    totals = []
    for f in rows(paths["weball"]):
        if len(f) >= 28 and f[0] in cands:
            totals.append((f[0], money(f[5]), money(f[17]), money(f[25]), money(f[26]), money(f[11]), money(f[12]),
                           money(f[13]), money(f[6]), money(f[7]), money(f[10]), iso(f[27])))
    gifts, memo = [], 0
    for f in rows(paths["pas2"]):
        if len(f) < 22 or f[16] not in cands:
            continue
        kind = KIND.get(f[5])
        if not kind:
            continue
        if (f[19] or "").strip().upper() == "X":
            memo += 1
            continue
        if not f[21].isdigit():
            continue
        gifts.append((int(f[21]), f[0], f[16], kind, f[5], (f[3] or "").strip(), iso(f[13]), money(f[14]),
                      1 if "EARMARK" in (f[20] or "").upper() else 0))
    used = {g[1] for g in gifts} | {c[8] for c in cands.values() if c[8]}
    committees = []
    for f in rows(paths["cm"]):
        if len(f) >= 15 and f[0] in used:
            committees.append((f[0], f[1], f[8], f[9], f[10], f[12], f[13], f[14]))
    with con:
        for t in ("fec26_candidates", "fec26_totals", "fec26_gifts", "fec26_committees"):
            con.execute(f"DELETE FROM {t}")
        con.executemany("INSERT OR REPLACE INTO fec26_candidates VALUES (?,?,?,?,?,?,?,?,?)", cands.values())
        con.executemany("INSERT OR REPLACE INTO fec26_totals VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", totals)
        con.executemany("INSERT OR REPLACE INTO fec26_gifts VALUES (?,?,?,?,?,?,?,?,?)", gifts)
        con.executemany("INSERT OR REPLACE INTO fec26_committees VALUES (?,?,?,?,?,?,?,?)", committees)
    say(f"    FEC 2026: {len(cands):,} House and Senate candidates, {len(totals):,} campaign totals, "
        f"{len(gifts):,} committee payments from {len({g[1] for g in gifts}):,} committees ({memo:,} memo lines left out)")
    return len(cands)
