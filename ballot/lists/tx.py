"""
Texas: the Secretary of State's Ballot Certification Report for the November 3, 2026 general election, a PDF of
1,395 pages dated August 28, 2026, read with ballot/pdftext.py. It goes county by county; under each county, every
office on that county's ballot and, under each office, its candidates in ballot order with their party (REP, DEM,
LIB, GRE, IND). The congressional races are taken from it. A district that spans several counties is listed once
per county, and every county's list must agree; any that does not is reported and the race is left out.

The certification prints names in capitals; the page shows them in ordinary capitals (a member of Congress with the
spelling the congress-legislators roster gives), and says so. Texas's March 3 primaries and May 26 runoffs are not
loaded yet.
"""

import os
import re

from ballot.common import house_id, party_code, record_source, senate_id
from ballot.pdftext import lines
from states import net

URL = "https://www.sos.texas.gov/elections/forms/2026-ballot-cert.pdf"
PARTIES = {"REP": "Republican", "DEM": "Democratic", "LIB": "Libertarian", "GRE": "Green", "IND": "Independent", "W-I": "Write-in"}
HEADER = re.compile(r"^(Texas Secretary of State|Ballot Certification Report|2026 NOVEMBER GENERAL ELECTION|November 03, 2026)$|"
                    r"^\d\d/\d\d/\d{4} \d\d:\d\d [AP]M Page \d+ of \d+$")
SMALL = {"DE", "LA", "DEL", "VAN", "VON", "DER"}


def proper(name):
    """KEVIN MCCORMICK -> Kevin McCormick; V. ALONZO ECHAVARRIA-GARZA -> V. Alonzo Echavarria-Garza; JR. and III kept."""
    out = []
    for i, w in enumerate(name.split()):
        if re.fullmatch(r"(JR|SR)\.?", w):
            out.append(w.title())
        elif re.fullmatch(r"[IVX]+", w) and i:
            out.append(w)
        elif i and w in SMALL and i < len(name.split()) - 1:
            out.append(w.lower() if w != "LA" else "La")
        else:
            parts = []
            for p in w.split("-"):
                p2 = p.capitalize()
                p2 = re.sub(r"^Mc([a-z])", lambda m: "Mc" + m.group(1).upper(), p2)
                p2 = re.sub(r"^O'([a-z])", lambda m: "O'" + m.group(1).upper(), p2)
                parts.append(p2)
            out.append("-".join(parts))
    return " ".join(out)


def load(con, cache, say=print):
    path = os.path.join(cache, "tx_ballot_cert_2026.pdf")
    net.download(URL, path, max_age_days=30)
    races, county, office, listed = {}, None, None, {}
    for page, y, text in lines(path):
        if HEADER.match(text):
            continue
        m = re.match(r"^County (.+)$", text)
        if m:
            county, office = m.group(1).strip(), None
            continue
        m = re.match(r"^(.+?) (REP|DEM|LIB|GRE|IND|W-I)$", text)
        if m and office:
            listed.setdefault((office, county), []).append((m.group(1).strip(), m.group(2)))
            continue
        if m:
            continue
        # anything else is the next office's heading
        if re.fullmatch(r"U\. ?S\. SENATOR", text):
            office = ("S", 2)
        else:
            h = re.fullmatch(r"U\. ?S\. REPRESENTATIVE,? DISTRICT (\d+)( \(UNEXPIRED TERM\))?", text)
            office = ("H", int(h.group(1))) if h and not h.group(2) else None
    disagree = []
    for (off, cty), cands in listed.items():
        first = races.setdefault(off, (cty, cands))
        if first[1] != cands:
            disagree.append(f"{off} {first[0]} / {cty}")
    rows = []
    import sqlite3      # a sitting member's name as the congress-legislators roster spells it
    from ballot.common import HERE
    rec = sqlite3.connect(f"file:{os.path.join(HERE, 'congress_119.sqlite')}?mode=ro", uri=True)
    fixed = {}
    for full, first, last in rec.execute("SELECT official_full, first_name, last_name FROM legislators WHERE is_current = 1 AND state = 'TX'"):
        for form in (full, f"{first} {last}"):
            if form:
                fixed[form.upper()] = full or form
    for (kind, n), (_cty, cands) in sorted(races.items()):
        if any(d.startswith(f"{(kind, n)} ") for d in disagree):
            continue
        race = senate_id("TX", 2) if kind == "S" else house_id("TX", n)
        for order, (name, code) in enumerate(cands, start=1):
            party = PARTIES[code]
            rows.append((race, "general", "2026-11-03", fixed.get(name, proper(name)), party, party_code(party), order, 0, int(code == "W-I"),
                         None, None, None, None, None, "tx-sos-2026-ballot-cert",
                         "Texas's certification prints names in capitals; they are shown here in ordinary capitals."))
    with con:
        con.execute("DELETE FROM candidates WHERE race_id LIKE '2026-TX-%'")
        con.executemany("INSERT OR REPLACE INTO candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        record_source(con, "tx-sos-2026-ballot-cert", path=path, level="federal", state="TX", kind="official candidate list",
                      agency="Texas Secretary of State", title="Ballot Certification Report, 2026 November General Election (certified August 28, 2026)",
                      url=URL, published="2026-08-28", rows=len(rows),
                      note=f"Read county by county from the PDF; {len(listed):,} county lists of federal races agreed" + (f"; {len(disagree)} disagreed" if disagree else ""))
    house = len({r[0] for r in rows if "-H" in r[0]})
    say(f"    Texas: {house} House districts and {'the' if any('-S' in r[0] for r in rows) else 'no'} Senate race, {len(rows)} candidates on the November ballot"
        + (f"; left out where counties disagreed: {'; '.join(disagree[:6])}" if disagree else ""))
    return len(rows)
