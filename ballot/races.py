"""
ballot/races.py - every federal race on the November 3, 2026 ballot, and what a reader should know about each
state's ballot this year.

The House: all 435 seats, one race per district, from the district file the site already draws (44 states) plus
the six states with a single at-large seat. The Senate: the 33 class 2 seats, whose terms end in January 2027, plus
a special election in every state where a senator of another class serves by appointment today (Ohio and Florida
in 2026), for the rest of that term. Who holds each seat today comes from the roster in congress_119.sqlite.

Where a state's congressional lines changed for 2026, the note says so, citing the National Conference of State
Legislatures' tracker (a secondary source, named on the page), and the page does not place a reader in a district
from the 2024 lines there.
"""

import json
import os
import sqlite3

from ballot.common import GENERAL, HERE, house_id, senate_id

AT_LARGE = ("AK", "DE", "ND", "SD", "VT", "WY")
OWN_SOURCE = {      # a state's own notice, where it corrects or adds to NCSL's summary
    "LA": ("Louisiana Secretary of State, notice of May 14, 2026 on the fall U.S. House races, and NCSL's map tracker",
           "https://www.sos.la.gov/media/dcvl5ojl/051426-fall-house-races.pdf", "2026-05-14")}
NCSL = ("National Conference of State Legislatures, Changing the Maps: Tracking Mid-Decade Redistricting (updated September 11, 2026)",
        "https://www.ncsl.org/redistricting-and-census/changing-the-maps-tracking-mid-decade-redistricting")
MAPS_2026 = {      # (lines differ from 2024?, what to know), from the tracker above
    "AL": (1, "Alabama's 2023 congressional map is back in effect for 2026 after the U.S. Supreme Court's order of June 2, 2026, "
              "so some district lines differ from 2024. Districts affected by the change held special primaries on August 11."),
    "CA": (1, "California voters adopted a new congressional map on November 4, 2025 (Proposition 50). It is in effect for 2026."),
    "FL": (1, "Florida enacted a new congressional map on May 4, 2026. It is in effect for 2026; a challenge to it is pending in state court."),
    "LA": (1, "Louisiana enacted a new congressional map on May 29, 2026. Its spring party primaries for the U.S. House were cancelled "
              "(Act 7 of 2026): on November 3 every House candidate, of every party, is on one open primary ballot; a candidate with more "
              "than half the votes wins, and otherwise the top two meet on December 12. The Senate race held its party primaries in May "
              "and June, and its general election is on November 3."),
    "MO": (0, "Missouri's 2025 map is paused until voters decide a referendum on it this November, so the 2022 lines are in effect. "
              "The August primaries used the 2025 map; each nominee runs in the district with the same number under the 2022 lines."),
    "NC": (1, "North Carolina enacted a new congressional map on October 22, 2025. It is in effect for 2026."),
    "OH": (1, "Ohio adopted a new congressional map on October 31, 2025. It is in effect for 2026."),
    "TN": (1, "Tennessee adopted a new congressional map on May 7, 2026. It is in effect for 2026."),
    "TX": (1, "Texas enacted a new congressional map on August 29, 2025. It is in effect for 2026; the U.S. Supreme Court stayed a "
              "lower court's order against it on December 4, 2025."),
    "UT": (1, "Utah's new congressional map was adopted by court order on November 10, 2025. It is in effect for 2026."),
}


def build(con, record_db=os.path.join(HERE, "congress_119.sqlite")):
    """Write the races and state_notes tables. Returns (house, senate, special) counts."""
    rec = sqlite3.connect(f"file:{record_db}?mode=ro", uri=True)
    lines = json.load(open(os.path.join(HERE, "us_districts_albers.json"), encoding="utf-8"))["states"]
    seats = {st: sorted(int(d) for d in ds) for st, ds in lines.items()}
    for st in AT_LARGE:
        seats[st] = [0]
    if sum(len(v) for v in seats.values()) != 435:
        raise SystemExit(f"expected 435 House seats, found {sum(len(v) for v in seats.values())}")
    holders = {(r[0], int(r[1] or 0)): r[2:] for r in rec.execute(
        "SELECT state, district, bioguide_id, official_full, party_name FROM legislators WHERE is_current = 1 AND chamber = 'House'")}
    rows = []
    for st, ds in sorted(seats.items()):
        for d in ds:
            h = holders.get((st, d)) or (None, None, None)
            rows.append((house_id(st, d), "federal", "U.S. House", st, f"{d:02d}", None, 0, h[0], h[1], h[2], GENERAL, None))
    senators = rec.execute("SELECT state, senate_class, bioguide_id, official_full, party_name FROM legislators WHERE is_current = 1 AND chamber = 'Senate'").fetchall()
    appointed = {r[0] for r in rec.execute("""SELECT bioguide_id FROM member_terms WHERE type = 'sen' AND how = 'appointment' AND end >= date('now')""")}
    specials = 0
    for st, cls, bio, name, party in sorted(senators):
        if cls == 2:
            rows.append((senate_id(st, 2), "federal", "U.S. Senate", st, None, 2, 0, bio, name, party, GENERAL,
                         "Appointed to the seat; the regular election for it is this year." if bio in appointed else None))
        elif bio in appointed:      # a seat of another class filled by appointment: a special election for the rest of the term
            specials += 1
            rows.append((senate_id(st, cls), "federal", "U.S. Senate", st, None, cls, 1, bio, name, party, GENERAL,
                         "Special election for the rest of the term, which ends in January " + ("2029" if cls == 3 else "2031") + "."))
    with con:
        con.execute("DELETE FROM races WHERE level = 'federal'")
        con.executemany("INSERT INTO races VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        con.execute("DELETE FROM state_notes")
        con.executemany("INSERT INTO state_notes VALUES (?,?,?,?,?,?)",
                        [(st, changed, note, *OWN_SOURCE.get(st, (NCSL[0], NCSL[1], "2026-09-11"))) for st, (changed, note) in MAPS_2026.items()])
    house = sum(1 for r in rows if r[2] == "U.S. House")
    return house, len(rows) - house, specials
