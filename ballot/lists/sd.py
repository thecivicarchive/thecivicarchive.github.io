"""
South Dakota: the Secretary of State's 2026 General Election Candidate List (vip.sdsos.gov, election 774), a grid of
every contest sorted by office, the Senate and the House first. Its first page is read and every row of the two federal
contests taken, and the loader checks that a state office follows them there, so the federal block is whole. Columns
are taken by name, only Contest, Name, Party, Ballot Order, Status and the date of any withdrawal; the grid also carries
mailing addresses, which are never read. A withdrawn candidate is left off the November ballot. The list writes parties
as REP, DEM, IND and LIB; they are written out here (Republican, Democratic, Independent, Libertarian).

The June 2 primary comes from the same site's 2026 Primary Election Candidate List (election 773), read the same way
(its grid adds the election date, which is checked, and more address columns, never read). South Dakota prints a party
primary on the ballot only when it is contested, and only party primaries with two or more candidates on the list become
fields: in 2026 the Republican primaries for the Senate (Justin McNeal, Mike Rounds) and the House (Marty Jackley, James
Bialota). The Democrats each had one candidate (Julian Beaudion for the Senate, who withdrew on August 4, after the
primary; Nicole Gronli for the House), so they have no field. The one on the November list for that party, withdrawn or
not, is the one who advanced. A primary winner below 35 percent in a race for Congress would go to a runoff; the July 28
runoff was for Governor only.

The primary's vote counts are not loaded. The Secretary of State's results site (electionresults.sd.gov, the same
election number 773) labels its figures "Unofficial Results" and keeps them after the canvass: for the 2024 primary the
site still shows Biden 13,418 where the State Canvassing Board certified 13,372. The Board's certified canvass is
published as a scanned PDF on sdsos.gov's election history page (2024: "2024 Primary Election State Canvass and
Certificate"); the 2026 primary's canvass was not linked there, or anywhere on sdsos.gov, on 2026-09-30. Once it is,
its totals can be read here.
"""

import html as H
import json
import os
import re

from ballot.common import fold, house_id, party_code, record_source, senate_id
from states import net

URL = "https://vip.sdsos.gov/candidatelist.aspx?eid=774"
PRIMARY_URL = "https://vip.sdsos.gov/candidatelist.aspx?eid=773"
PRIMARY = "2026-06-02"
KEEP = ("Contest", "Name", "Party", "Ballot Order", "Status", "WithdrawnDate")
PARTY = {"REP": "Republican", "DEM": "Democratic", "IND": "Independent", "LIB": "Libertarian"}
FEDERAL = {"United States Senator": lambda: senate_id("SD", 2), "United States Representative": lambda: house_id("SD", 0)}
STATUS_MARK = re.compile(r"\s*\((?:Withdrawn|Successful Challenge)[^)]*\)\s*$")      # "Julian Beaudion (Withdrawn 08/04/2026)"


def grid(page, keep=KEEP):
    heads = [re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", "", h))).strip()
             for h in re.findall(r'<th scope="col" class="rgHeader[^"]*"[^>]*>(.*?)</th>', page, re.S)]
    if not all(k in heads for k in keep):
        raise SystemExit(f"South Dakota: the candidate grid's columns changed ({heads})")
    idx = {k: heads.index(k) for k in keep}
    for tr in re.findall(r'<tr class="(?:rgRow|rgAltRow)"[^>]*>(.*?)</tr>', page, re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        if len(cells) != len(heads):
            raise SystemExit("South Dakota: a grid row does not line up with the grid's headings")
        yield {k: re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", "", cells[i]))).strip() for k, i in idx.items()}


def federal_block(url, election, keep=KEEP):
    """Every row of the two federal contests on the list's first page, checked to be followed by a state office."""
    page = net.get(url).decode("utf-8", "replace")
    if f"2026 {election} Election" not in page:
        raise SystemExit(f"South Dakota: the candidate list page is no longer the 2026 {election} Election")
    all_rows = list(grid(page, keep))
    fed = [r for r in all_rows if r["Contest"] in FEDERAL]
    last = max((i for i, r in enumerate(all_rows) if r["Contest"] in FEDERAL), default=-1)
    if not fed or last >= len(all_rows) - 1:
        raise SystemExit("South Dakota: the federal contests are not followed by a state office on the first page; the list may run on")
    return fed


def active(r):
    return r["Status"] == "Active" and not r["WithdrawnDate"]


def save(fed, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump([{k: r[k] for k in KEEP} for r in fed], open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def load(con, cache, say=print):
    net.patient_lookups()
    fed = federal_block(URL, "General")
    path = os.path.join(cache, "sd", "sd_2026_general_federal.json")      # only the columns kept
    save(fed, path)
    on = [r for r in fed if r["Status"] != "Withdrawn" and not r["WithdrawnDate"]]
    gone = [r for r in fed if r not in on]
    rows = []
    for r in on:
        party = PARTY.get(r["Party"], r["Party"])
        order = int(r["Ballot Order"]) if r["Ballot Order"].isdigit() else None
        rows.append((FEDERAL[r["Contest"]](), "general", "2026-11-03", r["Name"], party, party_code(party), order, 0, 0, None, None, None, None, None,
                     "sd-sos-2026-candidate-list", None))

    primary = federal_block(PRIMARY_URL, "Primary", KEEP + ("eldate",))
    if any(not r["eldate"].startswith("6/2/2026") for r in primary):
        raise SystemExit("South Dakota: a row of the primary list is not dated June 2, 2026")
    ppath = os.path.join(cache, "sd", "sd_2026_primary_federal.json")      # only the columns kept
    save(primary, ppath)
    # the nominee of each party: the November list's candidate for it, a withdrawn one included (Beaudion withdrew after winning)
    nominee = {(FEDERAL[r["Contest"]](), r["Party"]): fold(STATUS_MARK.sub("", r["Name"])) for r in fed}
    fields = {}
    for r in primary:
        if active(r):
            fields.setdefault((FEDERAL[r["Contest"]](), r["Party"]), []).append(r["Name"])
    off_primary = sum(1 for r in primary if not active(r))
    unsettled = []
    for (race, code), names in sorted(fields.items()):
        if len(names) < 2:
            continue
        party = PARTY.get(code, code)
        won = nominee.get((race, code))
        if won not in {fold(n) for n in names}:
            unsettled.append(f"{race} {party}")
        for name in names:
            outcome = None if won not in {fold(n) for n in names} else ("advanced" if fold(name) == won else "lost")
            rows.append((race, f"primary-{code}", PRIMARY, name, party, party_code(party), None, 0, 0, None, None, outcome, None, None,
                         "sd-sos-2026-primary-candidate-list", None))
    contested = sum(1 for v in fields.values() if len(v) > 1)

    with con:
        con.execute("DELETE FROM candidates WHERE race_id LIKE '2026-SD-%'")
        con.executemany("INSERT OR REPLACE INTO candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        record_source(con, "sd-sos-2026-candidate-list", path=path, level="federal", state="SD", kind="official candidate list",
                      agency="South Dakota Secretary of State", title="2026 General Election Candidate List (U.S. Senate and U.S. House)",
                      url=URL, rows=len(fed),
                      note=f"Withdrawn, left off: {len(gone)}. Parties written out from the list's REP, DEM, IND, LIB; addresses never read.")
        record_source(con, "sd-sos-2026-primary-candidate-list", path=ppath, level="federal", state="SD", kind="official candidate list",
                      agency="South Dakota Secretary of State",
                      title="2026 Primary Election Candidate List, June 2, 2026 (U.S. Senate and U.S. House)",
                      url=PRIMARY_URL, rows=len(primary),
                      note=(f"Party primaries with two or more candidates are fields ({contested}); withdrawn or decertified, left off: {off_primary}. "
                            "Who advanced is read from the November list. Vote counts not loaded: the results site (electionresults.sd.gov) "
                            "labels its figures unofficial, and the State Canvassing Board's certified canvass of the 2026 primary was not "
                            "published on sdsos.gov as of 2026-09-30. Addresses never read."))
    say(f"    South Dakota: the Senate race and the at-large House seat, {len(rows) - sum(1 for r in rows if r[1] != 'general')} candidates on the "
        f"November ballot ({len(gone)} withdrawn left off); {contested} party primaries with a field (who advanced, no vote counts: the "
        f"certified canvass is not published yet)" + (f"; no nominee found on the November list for {', '.join(unsettled)}" if unsettled else ""))
    return sum(1 for r in rows if r[1] == "general")
