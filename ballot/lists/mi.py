"""
Michigan: the Department of State's Official Candidate Listing, published from the Bureau of Elections' filing system
(mi-boe.entellitrak.com, "Candidate Listing Report"); the Secretary of State's Elections page links it as "2026 November
General Candidate Listing" and "2026 August Primary Candidate Listing". Each is one HTML report of every office: a
heading per office ("U.S. Senate 6 Year Term (1) Position", "1st District Representative in Congress 2 Year Term (1)
Position"), then a row per candidate: a status mark (DISQ disqualified, WITHD withdrawn, blank otherwise), the party,
the name written "Last, First", the filing date and how the candidate filed.

The November ballot is every candidate without a status mark, in the order the listing gives them (by party, as the
ballot is). A party's primary field is its unmarked candidates on the August list; the one on the November list for that
party is the one who advanced. The listing gives no vote counts (the Department's results site refuses scripts), so the
fields say who advanced and nothing more. The rest of michigan.gov answers scripts with 403; this host does not.
"""

import os
import re
import html as H

from ballot.common import fold, house_id, party_code, record_source, senate_id
from states import net

BASE = ("https://mi-boe.entellitrak.com/etk-mi-boe-prod/page.request.do?page=page.miboePublicReport"
        "&electionYear=2026&electionType=")
PRIMARY = "2026-08-04"
SUFFIX = re.compile(r"^(JR|SR|II|III|IV|V)\.?$", re.I)


def first_last(raw):
    """McDonald Rivet, Kristen -> Kristen McDonald Rivet; Gilchrist II, Garlin -> Garlin Gilchrist II"""
    last, _, first = raw.partition(",")
    words = last.split()
    return " ".join(first.split() + [w for w in words if not SUFFIX.match(w)] + [w for w in words if SUFFIX.match(w)])


def federal_rows(path):
    """(race, status, party, name) for every candidate for Congress on one report, in the report's order."""
    text = open(path, encoding="utf-8", errors="replace").read()
    if "Official Candidate Listing" not in text:
        raise SystemExit(f"Michigan: {os.path.basename(path)} is not the Official Candidate Listing report")
    race, out = None, []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", text, re.S):
        head = re.search(r'<a id="[^"]*"></a><span[^>]*>([^<]+)</span>', tr)
        if head:
            h = H.unescape(head.group(1)).strip()
            m = re.match(r"(\d+)(?:st|nd|rd|th) District Representative in Congress\b", h)
            race = house_id("MI", int(m.group(1))) if m else (senate_id("MI", 2) if h.startswith("U.S. Senate") else None)
            continue
        if not race:
            continue
        cells = [H.unescape(re.sub(r"<[^>]+>", "", c)).replace("\xa0", " ").strip() for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        if len(cells) >= 7 and re.fullmatch(r"\d\d/\d\d/\d{4}", cells[5]) and cells[4]:
            if cells[3] in ("", "INCUMBENT"):
                raise SystemExit(f"Michigan: a candidate for {race} with no party on the listing ({cells[3] or 'blank'}); read the report again")
            out.append((race, cells[1], cells[3], re.sub(r"\s+", " ", first_last(cells[4]))))
    return out


def load(con, cache, say=print):
    net.patient_lookups()
    paths = {}
    for kind in ("GEN", "PRI"):
        paths[kind] = os.path.join(cache, f"mi_candidate_listing_2026_{kind.lower()}.html")
        net.download(BASE + kind, paths[kind], max_age_days=2)
    general = federal_rows(paths["GEN"])
    on = [r for r in general if not r[1]]
    off = [r for r in general if r[1]]
    rows, order = [], {}
    for race, _status, party, name in on:
        order[race] = order.get(race, 0) + 1
        rows.append((race, "general", "2026-11-03", name, party, party_code(party), order[race], 0, 0, None, None, None, None, None,
                     "mi-sos-2026-general-listing", None))
    nominee = {(race, party): fold(name) for race, _s, party, name in on}
    fields = {}
    for race, status, party, name in federal_rows(paths["PRI"]):
        if not status:
            fields.setdefault((race, party), []).append(name)
    for (race, party), names in fields.items():
        if len(names) < 2:
            continue
        code = {"Democratic Party": "DEM", "Republican Party": "REP"}.get(party, party[:3].upper())
        for name in names:
            rows.append((race, f"primary-{code}", PRIMARY, name, party, party_code(party), None, 0, 0, None, None,
                         "advanced" if nominee.get((race, party)) == fold(name) else "lost", None, None, "mi-sos-2026-primary-listing", None))
    with con:
        con.execute("DELETE FROM candidates WHERE race_id LIKE '2026-MI-%'")
        con.executemany("INSERT OR REPLACE INTO candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        record_source(con, "mi-sos-2026-general-listing", path=paths["GEN"], level="federal", state="MI", kind="official candidate list",
                      agency="Michigan Department of State, Bureau of Elections", title="Official Candidate Listing, General Election, Tuesday, November 3, 2026",
                      url=BASE + "GEN", rows=len(general),
                      note=f"Every office; the candidates for Congress read. Marked disqualified or withdrawn, left off: {len(off)}.")
        record_source(con, "mi-sos-2026-primary-listing", path=paths["PRI"], level="federal", state="MI", kind="official candidate list",
                      agency="Michigan Department of State, Bureau of Elections", title="Official Candidate Listing, August Primary, August 4, 2026",
                      url=BASE + "PRI", rows=sum(len(v) for v in fields.values()),
                      note="Who advanced is read from the November listing; the primary's vote counts are not loaded.")
    n = sum(1 for r in rows if r[1] == "general")
    say(f"    Michigan: {len({r[0] for r in rows if r[1] == 'general' and '-H' in r[0]})} House districts and the Senate race, {n} candidates on the "
        f"November ballot ({len(off)} disqualified or withdrawn left off); {sum(1 for v in fields.values() if len(v) > 1)} party primaries with a field")
    return n
