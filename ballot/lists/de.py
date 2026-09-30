"""
Delaware: the Department of Elections' own candidate lists and official results (elections.delaware.gov). Delaware has
one House seat, elected at large, and a Senate race in 2026 (class 2, held by Christopher A. Coons). The state primary
was held on September 15, 2026 (the primary list's heading "Primary Election 9/15/2026" and the results' election date).

  November ballot   "Filed Candidates by Office, General Election 11/3/2026" (candidates/candidatelist/genl_fcddt_2026.html,
                    linked as "11/03/2026 Statewide General" from the Ballot Qualified Candidates page), read from the
                    page's own "Download the candidate list Excel file" (genl_fcddt_2026.xlsx): one row per filing, every
                    office on Delaware's ballot. The page's "Last Updated" line is read for the date and nothing else.
  write-in list     "Write-In Candidates by Office, General Election 11/3/2026" (genl_wcddt_2026.html, linked there as
                    "Declared Write-In Candidates"), read from its Excel file (genl_wcddt_2026.xlsx). Delaware counts
                    write-in votes only for a person who has declared a write-in candidacy, and these are they.
  primary list      "Filed Candidates by Office, Primary Election 9/15/2026" (prim_fcddt_2026.html and .xlsx): who was on
                    each party's primary ballot and how their names are printed. It lists contested primaries only (a
                    party with one candidate holds no primary), so it names no Democrat for the House.
  primary results   the Department's results site for the 2026 Primary Election (results/enr/PR2026.html, linked from
                    results/index.html as "Primary Election Official Results"), which draws its tables from files beside
                    it: Election_StatewideResults_ID_PR2026.json (every candidate's machine, absentee, early-voting and
                    total votes, the election districts reported and the "Results Type") and, as a control,
                    Election_ByCountyWithWilmington_ID_PR2026.json (the same votes for New Castle, Kent and Sussex, and for
                    Wilmington and the rest of New Castle). Every row must say OFFICIAL RESULTS and every election district
                    must have reported; unofficial figures are never stored.

The Excel lists also carry residential and mailing addresses, the website, two e-mail addresses and two telephone
numbers. Columns are taken by name, only County, Office, Withdrawal Date, BallotName, Party (the write-in list has none)
and DisplayedStatus; nothing else is read, the downloaded workbooks are never written to disk, and the cache
(ballot_cache/de/) keeps only those columns for the U.S. Senator and Representative in Congress rows, as JSON. The results
files carry votes only and are cached as the Department publishes them.

Names are shown as the lists print them on the ballot (BallotName: "Michael "Dr. Mike" Katz"), in ordinary capitals; the
results write them in capitals and are matched to the primary list letters only. Parties are printed in full on the lists
(Democratic, Republican) and kept as printed; the results write "Democratic Party" and "Republican Party". The only
abbreviation on the lists, "Ind Pty of DE" (no federal candidate this year), would be written out.

The November ballot is every federal row of the general list whose status is Qualified (or Provisional: the State
Election Commissioner is still reviewing the candidate's filing, and the row says so). A row with the status Withdrawn,
or with a withdrawal date, is left off and counted; any other status stops the loader. The list gives no ballot
positions and no general-election sample ballots are posted yet, so its own order is kept (Democratic, then Republican).
The write-in list's federal rows are stored with write_in 1, no ballot position and the party "Write-in" (the list gives
none). A party primary is a field when two or more of its candidates were on the ballot; the results' candidates must be
exactly the primary list's, each candidate's county figures must add up to the statewide total, and the leader, who is
the nominee, must be the party's candidate on the November list, or the row says plainly that the nominee is not on it.
The results report no write-in votes for these contests, so a field's total is the sum of its candidates' votes.
"""

import datetime as dt
import io
import json
import os
import re
import time

from ballot.common import fold, house_id, party_code, record_source, senate_id
from states import net

BASE = "https://elections.delaware.gov/"
LISTS_PAGE = BASE + "candidates/candidatelist/"
LISTS = {      # key: (page, Excel file, the page's heading)
    "general": ("genl_fcddt_2026.html", "genl_fcddt_2026.xlsx", "General Election 11/3/2026"),
    "write_in": ("genl_wcddt_2026.html", "genl_wcddt_2026.xlsx", "General Election 11/3/2026"),
    "primary": ("prim_fcddt_2026.html", "prim_fcddt_2026.xlsx", "Primary Election 9/15/2026"),
}
KEEP = ("County", "Office", "Withdrawal Date", "BallotName", "Party", "DisplayedStatus")
RESULTS_PAGE = BASE + "results/enr/PR2026.html"
STATEWIDE = BASE + "results/enr/Election_StatewideResults_ID_PR2026.json"
COUNTIES = BASE + "results/enr/Election_ByCountyWithWilmington_ID_PR2026.json"
ELECTION_ID, PRIMARY = "PR2026", "2026-09-15"
FEDERAL = {"U.S. Senator": senate_id("DE", 2), "Representative in Congress": house_id("DE", 0)}
LOOKS_FEDERAL = re.compile(r"\bU\.?\s?S\.?\b|United States|Congress", re.I)
WRITTEN_OUT = {"Ind Pty of DE": "Independent Party of Delaware"}
CODES = {"Democratic": "DEM", "Republican": "REP", "Libertarian": "LIB", "Green": "GRN"}
ON = {"Qualified", "Provisional"}
PROVISIONAL = ("The Department lists this candidate as Provisional: the State Election Commissioner is still reviewing "
               "the candidate's filing.")
WRITE_IN = "Write-in candidate: the name is not printed on the ballot."


def squash(text):
    return re.sub(r"\s+", " ", str(text if text is not None else "").replace("\xa0", " ")).strip()


def cell(value):
    if isinstance(value, (dt.datetime, dt.date)):
        return f"{value.month}/{value.day}/{value.year}"
    return squash(value)


def last_updated(page_url, heading):
    """The "Last Updated" date printed on a candidate list page (YYYY-MM-DD); the heading is checked and nothing else
    from the page is kept."""
    page = net.get(page_url, accept="text/html").decode("utf-8-sig", "replace")
    if heading not in page:
        raise SystemExit(f"Delaware: {page_url} is no longer headed {heading!r}")
    m = re.search(r"Last Updated:\s*(\d{4}-\d\d-\d\d)", page)
    return m.group(1) if m else ""


def candidate_list(key):
    """The federal rows of one candidate list's Excel file, the kept columns only (the workbook is read in memory)."""
    import openpyxl
    page, book, heading = LISTS[key]
    url = LISTS_PAGE + book
    raw = net.get(url)
    if raw[:2] != b"PK":
        raise SystemExit(f"Delaware: {url} is not an Excel workbook")
    wb = openpyxl.load_workbook(io.BytesIO(raw), read_only=True)
    if len(wb.worksheets) != 1:
        raise SystemExit(f"Delaware: {book} has {len(wb.worksheets)} sheets; one was expected")
    rows = wb.worksheets[0].iter_rows(values_only=True)
    heads = [squash(h) for h in next(rows)]
    need = [k for k in KEEP if not (k == "Party" and key == "write_in")]
    if any(k not in heads for k in need):
        raise SystemExit(f"Delaware: {book}'s columns changed ({[k for k in need if k not in heads]} missing)")
    idx = {k: heads.index(k) for k in need}
    out, total = [], 0
    for r in rows:
        if not r or not any(v not in (None, "") for v in r):
            continue
        total += 1
        row = {k: cell(r[i]) if i < len(r) else "" for k, i in idx.items()}
        if row["Office"] in FEDERAL:
            out.append(row)
        elif LOOKS_FEDERAL.search(row["Office"]):
            raise SystemExit(f"Delaware: a federal office on {book} that is not read ({row['Office']!r})")
    wb.close()
    time.sleep(1.5)
    published = last_updated(LISTS_PAGE + page, heading)
    time.sleep(1.5)
    return {"url": url, "page": LISTS_PAGE + page, "published": published, "rows_in_file": total, "rows": out}


def kept(path, max_age_days, fetch):
    """A small JSON of what is read from a source, refreshed when older than max_age_days."""
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < max_age_days * 86400:
        return json.load(open(path, encoding="utf-8"))
    data = fetch()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(data, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return data


def results_file(url, path, say):
    """One of the results site's JSON files, cached as published for 30 days; must be a JSON list."""
    net.download(url, path, max_age_days=30, say=say)
    raw = open(path, "rb").read()
    if raw.lstrip(b"\xef\xbb\xbf").lstrip()[:1] != b"[":
        raise SystemExit(f"Delaware: {url} is not the results site's JSON list")
    return json.loads(raw.decode("utf-8-sig"))


def votes_of(text):
    t = squash(text).replace(",", "")
    if not re.fullmatch(r"\d+", t):
        raise SystemExit(f"Delaware: a vote count in the results that is not a number ({text!r})")
    return int(t)


def code_of(party_name):
    """'Democratic Party' -> DEM."""
    word = re.sub(r"\s+Party$", "", squash(party_name))
    if word not in CODES:
        raise SystemExit(f"Delaware: a party in the primary results that is not read ({party_name!r})")
    return CODES[word]


def primary_votes(statewide, counties):
    """{(race, code): ([(name as reported, votes, percentage)], write-in votes)} for every federal party primary, with
    the report time; every check made."""
    out, times = {}, set()
    for r in statewide:
        if r.get("Election Id") != ELECTION_ID or r.get("Election Date") != PRIMARY:
            raise SystemExit(f"Delaware: the results file is for {r.get('Election Name')} {r.get('Election Date')}, not the 2026 primary")
        if r.get("Results Type") != "OFFICIAL RESULTS":
            raise SystemExit(f"Delaware: the primary results say {r.get('Results Type')!r}; unofficial figures are never stored")
        if r.get("Precincts Reported") != r.get("Total Precincts"):
            raise SystemExit(f"Delaware: {r.get('Contest Title')} has {r.get('Precincts Reported')} of {r.get('Total Precincts')} election districts reported")
        times.add(r.get("ReportTime"))
        race = FEDERAL.get(squash(r.get("Contest Title")))
        if race is None:
            if LOOKS_FEDERAL.search(r.get("Contest Title") or ""):
                raise SystemExit(f"Delaware: a federal contest in the results that is not read ({r.get('Contest Title')!r})")
            continue
        code, name = code_of(r.get("Party Name")), squash(r.get("Candidate Name"))
        total = votes_of(r["Total Votes"])
        parts = sum(votes_of(r[k]) for k in ("Machine Votes", "Absentee Votes", "Early Voting Votes"))
        if parts != total:
            raise SystemExit(f"Delaware: {name}'s machine, absentee and early votes ({parts}) do not add up to the total ({total})")
        field, write_ins = out.setdefault((race, code), ([], 0))
        if re.search(r"write[- ]?in", name, re.I):
            out[(race, code)] = (field, write_ins + total)
            continue
        if any(fold(n) == fold(name) for n, _v, _p in field):
            raise SystemExit(f"Delaware: {name} appears twice in the {race} {code} results")
        field.append((name, total, r.get("Percentage")))
    if len(times) != 1:
        raise SystemExit(f"Delaware: the statewide results carry more than one report time ({sorted(map(str, times))})")
    # control: the county file adds up to the same statewide totals
    seen = {}
    for r in counties:
        if r.get("Election Id") != ELECTION_ID or r.get("Results Type") != "OFFICIAL RESULTS":
            raise SystemExit("Delaware: the county results file is not the official 2026 primary results")
        race = FEDERAL.get(squash(r.get("Contest Title")))
        if race is None:
            continue
        name = squash(r.get("Candidate Name"))
        nc, kent, sussex, state = (votes_of(r[k]) for k in ("New Castle", "Kent", "Sussex", "State"))
        if nc + kent + sussex != state or votes_of(r["Wilmington"]) + votes_of(r["Rest of New Castle"]) != nc:
            raise SystemExit(f"Delaware: {name}'s county votes in {race} do not add up to the state figure")
        seen[(race, code_of(r.get("Party Name")), fold(name))] = state
    mine = {(race, code, fold(n)): v for (race, code), (field, _w) in out.items() for n, v, _p in field}
    mine.update({(race, code, "write in"): w for (race, code), (_f, w) in out.items() if w})
    if seen != mine:
        raise SystemExit(f"Delaware: the county results differ from the statewide results ({sorted(set(seen.items()) ^ set(mine.items()))[:4]})")
    return out, times.pop()


def load(con, cache, say=print):
    net.patient_lookups()
    folder = os.path.join(cache, "de")
    paths = {k: os.path.join(folder, f"de_2026_{k}_federal.json") for k in LISTS}
    lists = {k: kept(paths[k], 30 if k == "primary" else 2, lambda k=k: candidate_list(k)) for k in LISTS}

    def status_of(r, where):
        status = r["DisplayedStatus"]
        if status == "Withdrawn" or r["Withdrawal Date"]:
            return "off"
        if status not in ON:
            raise SystemExit(f"Delaware: a status on the {where} list that is not read ({status!r}, {r['Office']})")
        return status

    def federal(r, where):
        if r["County"] != "Statewide":
            raise SystemExit(f"Delaware: a {r['Office']} row on the {where} list is filed under {r['County']!r}, not Statewide")
        if not r["BallotName"]:
            raise SystemExit(f"Delaware: a {r['Office']} row on the {where} list has no ballot name")
        return FEDERAL[r["Office"]]

    def party_of(r, where):
        if not r["Party"]:
            raise SystemExit(f"Delaware: a candidate for {r['Office']} with no party on the {where} list")
        return WRITTEN_OUT.get(r["Party"], r["Party"])

    rows, off, order, nominee, seen, provisional = [], [], {}, {}, set(), []
    for r in lists["general"]["rows"]:
        race, name = federal(r, "general"), r["BallotName"]
        status = status_of(r, "general")
        if status == "off":
            off.append(f"{name} ({r['Office']}, {r['Party'] or 'no party'}, withdrew {r['Withdrawal Date'] or 'on a date not given'})")
            continue
        party = party_of(r, "general")
        if (race, fold(name)) in seen:
            raise SystemExit(f"Delaware: {name} is on the {r['Office']} list twice")
        seen.add((race, fold(name)))
        if party in CODES:
            if (race, CODES[party]) in nominee:
                raise SystemExit(f"Delaware: two {party} candidates printed for {r['Office']}")
            nominee[(race, CODES[party])] = fold(name)
        order[race] = order.get(race, 0) + 1
        note = PROVISIONAL if status == "Provisional" else None
        if note:
            provisional.append(name)
        rows.append((race, "general", "2026-11-03", name, party, party_code(party), order[race], 0, 0, None, None, None, None, None,
                     "de-doe-2026-general-list", note))

    write_ins, write_off = [], []
    for r in lists["write_in"]["rows"]:
        race, name = federal(r, "write-in"), r["BallotName"]
        status = status_of(r, "write-in")
        if status == "off":
            write_off.append(f"{name} ({r['Office']})")
            continue
        if (race, fold(name)) in seen:
            raise SystemExit(f"Delaware: {name} is both printed and a declared write-in for {r['Office']}")
        seen.add((race, fold(name)))
        write_ins.append(f"{name} ({r['Office']}{', Provisional' if status == 'Provisional' else ''})")
        rows.append((race, "general", "2026-11-03", name, "Write-in", "W", None, 0, 1, None, None, None, None, None,
                     "de-doe-2026-general-write-ins", WRITE_IN + (" " + PROVISIONAL if status == "Provisional" else "")))

    # who was on each party's September ballot, as the primary list prints them
    filed, withdrew = {}, []
    for r in lists["primary"]["rows"]:
        race, name = federal(r, "primary"), r["BallotName"]
        if status_of(r, "primary") == "off":
            withdrew.append(f"{name} ({r['Office']}, {r['Party']})")
            continue
        party = party_of(r, "primary")
        if party not in CODES:
            raise SystemExit(f"Delaware: a primary candidate for {r['Office']} of a party that is not read ({party!r})")
        filed.setdefault((race, CODES[party]), {})[fold(name)] = (name, party)

    stpath = os.path.join(folder, "Election_StatewideResults_ID_PR2026.json")
    copath = os.path.join(folder, "Election_ByCountyWithWilmington_ID_PR2026.json")
    statewide = results_file(STATEWIDE, stpath, say)
    time.sleep(1.5)
    counties = results_file(COUNTIES, copath, say)
    votes, report_time = primary_votes(statewide, counties)
    if set(votes) != set(filed):
        raise SystemExit(f"Delaware: the party primaries in the results and on the primary list differ ({sorted(set(votes) ^ set(filed))})")

    fields, not_on = 0, []
    for (race, code), (field, write_in_votes) in sorted(votes.items()):
        listed = filed[(race, code)]
        if {fold(n) for n, _v, _p in field} != set(listed):
            raise SystemExit(f"Delaware: the results' candidates for {race} {code} are not the primary list's "
                             f"({sorted({fold(n) for n, _v, _p in field} ^ set(listed))})")
        if len(field) < 2:
            continue
        fields += 1
        total = sum(v for _n, v, _p in field) + write_in_votes
        top = max(v for _n, v, _p in field)
        if sum(1 for _n, v, _p in field if v == top) > 1:
            raise SystemExit(f"Delaware: the {race} {code} primary is tied at the top; read how it was settled")
        for name, v, pct in sorted(field, key=lambda t: (-t[1], fold(t[0]))):
            printed, party = listed[fold(name)]
            mine = round(100 * v / total, 1) if total else None
            if isinstance(pct, (int, float)) and total and abs(100 * v / total - pct) > 0.011:
                raise SystemExit(f"Delaware: {name}'s share in the {race} {code} results ({pct}) is not the votes' share ({100 * v / total:.2f})")
            won, note = v == top, None
            if won and nominee.get((race, code)) != fold(printed):
                note = "Won the primary but is not on the November list."
                not_on.append(f"{printed} ({race}, {code})")
            rows.append((race, f"primary-{code}", PRIMARY, printed, party, party_code(party), None, 0, 0, v, mine,
                         "advanced" if won else "lost", None, None, "de-doe-2026-primary-results", note))

    general = [r for r in rows if r[1] == "general"]
    races = [r[0] for r in con.execute("SELECT race_id FROM races WHERE state = 'DE' ORDER BY race_id")]
    gaps = [(race, "the Department of Elections' candidate list names no one for this race yet")
            for race in races if not any(g[0] == race for g in general)]
    unknown = sorted({g[0] for g in general} - set(races))
    if unknown:
        raise SystemExit(f"Delaware: candidates read for races not in the races table ({unknown})")
    published = report_time[:10] if report_time else ""
    parties_in_order = list(dict.fromkeys(r[4] for r in general if not r[8]))
    with con:
        con.execute("DELETE FROM candidates WHERE race_id LIKE '2026-DE-%'")
        con.execute("DELETE FROM list_gaps WHERE state = 'DE'")
        con.executemany("INSERT OR REPLACE INTO candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        con.executemany("INSERT INTO list_gaps VALUES (?, 'DE', ?)", gaps)
        g, w, p = lists["general"], lists["write_in"], lists["primary"]
        record_source(con, "de-doe-2026-general-list", path=paths["general"], level="federal", state="DE", kind="official candidate list",
                      agency="Delaware Department of Elections",
                      title="Filed Candidates by Office, General Election 11/3/2026: U.S. Senator and Representative in Congress (Excel)",
                      url=g["url"], published=g["published"], rows=len(g["rows"]),
                      note=f"From the list's own Excel file ({g['rows_in_file']} filings for every office; page {g['page']}). Six columns "
                           "read by name (county, office, withdrawal date, ballot name, party, status); addresses, website, e-mail and "
                           "telephones never read. The list gives no ballot positions and no general-election sample ballots are posted "
                           f"yet; its order is kept ({', then '.join(parties_in_order)}). Withdrawn, left off: {len(off)} ({'; '.join(off) or 'none'}). Provisional: {', '.join(provisional) or 'none'}.")
        record_source(con, "de-doe-2026-general-write-ins", path=paths["write_in"], level="federal", state="DE", kind="official candidate list",
                      agency="Delaware Department of Elections",
                      title="Write-In Candidates by Office, General Election 11/3/2026: U.S. Senator and Representative in Congress (Excel)",
                      url=w["url"], published=w["published"], rows=len(w["rows"]),
                      note=f"Declared write-in candidates, whose write-in votes alone Delaware counts ({w['rows_in_file']} for every office; "
                           f"page {w['page']}). The same columns read, less party (the list gives none). Federal: "
                           f"{'; '.join(write_ins) or 'none'}. Withdrawn, left off: {', '.join(write_off) or 'none'}. Provisional means the "
                           "State Election Commissioner is still reviewing the filing.")
        record_source(con, "de-doe-2026-primary-list", path=paths["primary"], level="federal", state="DE", kind="official candidate list",
                      agency="Delaware Department of Elections",
                      title="Filed Candidates by Office, Primary Election 9/15/2026: U.S. Senator and Representative in Congress (Excel)",
                      url=p["url"], published=p["published"], rows=len(p["rows"]),
                      note="Used for who was on each party's primary ballot and how the names are printed; the results' candidates must be "
                           "exactly these. The list names contested primaries only. The same kept columns only. Withdrawn before the "
                           f"primary: {'; '.join(withdrew) or 'none'}.")
        record_source(con, "de-doe-2026-primary-results", path=stpath, level="federal", state="DE", kind="official results",
                      agency="Delaware Department of Elections",
                      title="2026 Primary Election (September 15, 2026), Official Results: statewide results (JSON)",
                      url=STATEWIDE, published=published, rows=sum(len(f) for f, _w in votes.values()),
                      note=f"The file behind the Department's results page ({RESULTS_PAGE}); every row says OFFICIAL RESULTS, report time "
                           f"{report_time}, all election districts reported. Each candidate's machine, absentee and early-voting votes add up "
                           "to the total. No write-in votes are reported for these contests, so a field's total is its candidates' votes.")
        record_source(con, "de-doe-2026-primary-results-county", path=copath, level="federal", state="DE", kind="official results",
                      agency="Delaware Department of Elections",
                      title="2026 Primary Election (September 15, 2026), Official Results: by county, with Wilmington (JSON)",
                      url=COUNTIES, published=published, rows=sum(len(f) for f, _w in votes.values()),
                      note="Control: for every federal candidate, New Castle, Kent and Sussex add up to the state figure, Wilmington and the "
                           "rest of New Castle add up to New Castle, and the state figure equals the statewide file's.")
    say(f"    Delaware: the at-large House seat and the Senate race, {len(general)} candidates on the November ballot "
        f"({len(write_ins)} declared write-in, {len(off)} withdrawn left off); {fields} party primaries with a field, votes from the "
        f"Department of Elections' official results, county sums checked"
        + (f"; primary winners not on the November list: {', '.join(not_on)}" if not_on else "")
        + (f"; no list for {', '.join(r for r, _ in gaps)}" if gaps else ""))
    return len(general)
