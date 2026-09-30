"""
Pennsylvania: the Department of State's Election Information page for the 2026 General Election on PA Voter Services
(pavoterservices.pa.gov/ElectionInfo/ElectionInfo.aspx). The page carries every candidate for the election as data in
one hidden field (dataJson): name, party, office, district, status (Approved), how the candidate got there (Petition,
a party primary; Paper, nomination papers for minor parties and independents), and whether they won the May 19
primary. The November ballot is every approved Paper candidate and every Petition candidate who won the primary; a
party's primary field is its Petition candidates for the district, winners marked.

The rows also give each candidate's municipality and county of residence; those are never read. Names are written
"LAST, FIRST M" in capitals; the page shows them first name first in ordinary capitals (a sitting member as the
congress-legislators roster spells them) and says so.

The May 19, 2026 primary's votes come from the Department's own election returns site, electionreturns.pa.gov:
the statewide total of every candidate in each district's Democratic and Republican primaries for Representative in
Congress, read from the data call its Office Results page makes (GetOfficeData, the 2026 General Primary is election
117, the office is 11). They are stored only when the Department's election list marks that election's returns
Official (ElectionStatus "O"); otherwise the fields are kept without votes, as before. On that site a party primary is
a field when the party's primary ballot printed two names or more. Each candidate on the returns is matched to the
Election Information list by family name within the district and party (the returns print the ballot name, BOB HARVIE
for HARVIE JR, ROBERT J); the stored name stays the list's, and who advanced is still the list's PrimaryResult, checked
against the top vote-getter. The returns carry no write-in votes, so percentages are of the printed candidates' votes.

A second copy of the same official returns, county by county (the Reporting Center's CSV export, requested once and
kept in ballot_cache/pa/), is used only as a check: its county rows must add up to every statewide total.
"""

import csv
import hashlib
import html as H
import json
import os
import re
import sqlite3

from ballot.common import HERE, house_id, party_code, record_source
from ballot.lists.tx import proper
from states import net

URL = "https://www.pavoterservices.pa.gov/ElectionInfo/ElectionInfo.aspx"
PRIMARY = "2026-05-19"
SUFFIX = re.compile(r"^(JR|SR|II|III|IV)\.?$")

RETURNS = "https://www.electionreturns.pa.gov/"
PRIMARY_ID, CONGRESS = 117, 11      # the Department's numbers for the 2026 General Primary and for Representative in Congress
ELECTIONS_URL = RETURNS + "api/Reports/GetElectionList"
RESULTS_URL = (RETURNS + f"api/ElectionReturn/GetOfficeData?officeId={CONGRESS}&methodName=GetOfficeDetails"
               f"&electionid={PRIMARY_ID}&electiontype=P&isactive=0")
RESULTS_PAGE = RETURNS + f"General/OfficeResults?OfficeID={CONGRESS}&ElectionID={PRIMARY_ID}&ElectionType=P&IsActive=0"
REPORTS_PAGE = RETURNS + "ReportCenter/Reports"
LIST_FILE = "pa_election_list.json"
RETURNS_FILE = "pa_primary_2026_congress_returns.json"
COUNTY_FILE = "pa_primary_2026_congress_by_county.csv"      # the Reporting Center's export, requested once (a POST) and kept
COUNTY_COLUMNS = ("Election Name", "County Name", "Office Name", "District Name", "Party Name", "Candidate Name", "Votes")
CODE = {"Democratic": "DEM", "Republican": "REP"}


def first_last(raw):
    """ARRIAGA, JESSICA -> JESSICA ARRIAGA; ALLEN JR , BRYAN F -> BRYAN F ALLEN JR"""
    last, _, first = raw.partition(",")
    words = last.split()
    suffix = [w for w in words if SUFFIX.match(w)]
    family = [w for w in words if not SUFFIX.match(w)]
    return " ".join(first.split() + family + suffix)


def family(name):
    """The family name, for matching the returns' ballot name to the list's: BOB HARVIE and Robert J Harvie Jr -> HARVIE."""
    w = [x for x in re.sub(r"[^A-Z -]", "", name.upper()).split() if not SUFFIX.match(x)]
    return w[-1] if w else ""


def unjson(raw):
    """The site answers with JSON written inside a JSON string (sometimes twice)."""
    t = json.loads(raw.decode("utf-8-sig"))
    while isinstance(t, str):
        t = json.loads(t)
    return t


def fetch(url, path, days, say):
    """One of the Department's data calls, kept on disk; None when it cannot be had or is not JSON (a bot page)."""
    try:
        net.download(url, path, max_age_days=days, tries=3, say=say)
    except Exception as e:  # noqa: BLE001  the site can be down; the fields are then kept without votes
        return None, f"not fetched ({e})"
    head = open(path, "rb").read(64).lstrip(b"\xef\xbb\xbf \r\n\t")
    if not head.startswith((b'"', b"{", b"[")):
        os.remove(path)
        return None, f"not JSON (it began {head[:20]!r}); a browser would need to save {url} as {os.path.basename(path)}"
    return path, ""


def official(cache, say):
    """({(race, party): [(ballot name, votes)]}, why not, files) from the Department's official primary returns."""
    folder = os.path.join(cache, "pa")
    os.makedirs(folder, exist_ok=True)
    lpath, why = fetch(ELECTIONS_URL, os.path.join(folder, LIST_FILE), 7, say)
    if not lpath:
        return {}, f"the Department's election list was {why}", {}
    status = [r for r in unjson(open(lpath, "rb").read()).get("Table", [])
              if r.get("Electionid") == PRIMARY_ID and r.get("ElectionType") == "P"]
    if len(status) != 1 or status[0].get("ElectionName") != "2026 General Primary" or status[0].get("ElectionDate") != "05/19/2026":
        return {}, f"the Department's election list no longer shows the 2026 General Primary as election {PRIMARY_ID}", {}
    if status[0].get("ElectionStatus") != "O":
        return {}, f"the Department still marks the 2026 General Primary's returns unofficial (status {status[0].get('ElectionStatus')})", {}
    rpath, why = fetch(RESULTS_URL, os.path.join(folder, RETURNS_FILE), 30, say)
    if not rpath:
        return {}, f"the Department's primary returns were {why}", {}
    offices = unjson(open(rpath, "rb").read()).get("Election", {}).get("Representative in Congress")
    if not offices:
        return {}, "the Department's primary returns carry no Representative in Congress results", {}
    got, bad = {}, []
    for block in offices:
        for key, districts in block.items():
            for d in districts:
                m = re.fullmatch(r"(\d{1,2})(?:st|nd|rd|th) Congressional District", (d.get("District") or "").strip())
                if not m or not 1 <= int(m.group(1)) <= 17:
                    raise SystemExit(f"Pennsylvania: the primary returns name a district this loader does not know: {key}")
                race = house_id("PA", int(m.group(1)))
                for parties in d.get("Candidates") or []:
                    for party, cands in parties.items():
                        for c in cands:
                            if c.get("PartyName") != party or c.get("OfficeName") != "Representative in Congress":
                                raise SystemExit(f"Pennsylvania: a row of the primary returns for {race} is filed under the wrong party or office")
                            name, votes = re.sub(r"\s+", " ", c["CandidateName"]).strip(), int(c["Votes"])
                            parts = sum(int(c.get(k) or 0) for k in ("ElectionDayVotes", "MailInVotes", "ProvisionalVotes"))
                            if parts != votes:
                                bad.append(f"{race} {name}: election-day, mail and provisional votes add up to {parts:,}, the total says {votes:,}")
                            got.setdefault((race, party), []).append((name, votes))
    if len({r for r, _p in got}) != 17:
        return {}, f"the Department's primary returns cover {len({r for r, _p in got})} districts, not 17", {}
    return got, "; ".join(bad), {"list": lpath, "returns": rpath}


def county_check(cache, got):
    """The Reporting Center's county rows added up and compared with every statewide total: (path or None, disagreements)."""
    path = os.path.join(cache, "pa", COUNTY_FILE)
    if not os.path.exists(path):
        return None, []
    if not open(path, "rb").read(20).lstrip(b"\xef\xbb\xbf").startswith(b'"Election Name"'):
        return None, [f"{COUNTY_FILE} is not the Reporting Center's CSV"]
    sums = {}
    with open(path, encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        if not set(COUNTY_COLUMNS) <= set(reader.fieldnames or []):
            return None, [f"{COUNTY_FILE}'s columns changed"]
        for r in reader:      # only the allowlisted columns are read
            if r["Election Name"] != "2026 General Primary" or r["Office Name"] != "Representative in Congress":
                continue
            m = re.match(r"(\d{1,2})", r["District Name"])
            key = (house_id("PA", int(m.group(1))), r["Party Name"], re.sub(r"\s+", " ", r["Candidate Name"]).strip())
            sums[key] = sums.get(key, 0) + int(r["Votes"].replace(",", ""))
    state = {(race, party, name): v for (race, party), cands in got.items() for name, v in cands}
    off = [f"{k[0]} {k[2]}: counties add up to {sums.get(k, 0):,}, the statewide total is {state.get(k, 0):,}"
           for k in sorted(set(sums) | set(state)) if sums.get(k) != state.get(k)]
    return path, off


def load(con, cache, say=print):
    net.patient_lookups()
    page = net.get(URL).decode("utf-8", "replace")
    m = re.search(r"id='dataJson'[^>]*value='(.*?)'\s*/?>", page, re.S) or re.search(r'id="dataJson"[^>]*value="(.*?)"\s*/?>', page, re.S)
    if not m:
        raise SystemExit("Pennsylvania: the Election Information page no longer carries its dataJson field")
    raw = H.unescape(m.group(1))
    rows = json.loads(raw)
    path = os.path.join(cache, "pa_electioninfo_2026_general.json")
    kept = [{k: r.get(k) for k in ("CandidateIDNum", "CandidateName", "PartyName", "CandidateStatusValue", "CandidateTypeValue",
                                   "OfficeName", "DistrictName", "ElectionName", "PrimaryResult", "GeneralResult")} for r in rows]
    json.dump(kept, open(path, "w", encoding="utf-8"), ensure_ascii=False)      # the residence columns are not kept
    elections = {r["ElectionName"] for r in kept}
    if elections != {"2026 General Election"}:
        raise SystemExit(f"Pennsylvania: expected the 2026 General Election, the page gave {sorted(elections)}")
    rec = sqlite3.connect(f"file:{os.path.join(HERE, 'congress_119.sqlite')}?mode=ro", uri=True)
    def key_of(name):      # first name and family name, suffixes and initials set aside
        w = [x for x in re.sub(r"[^A-Z ]", "", name.upper()).split() if not SUFFIX.match(x)]
        return (w[0], w[-1]) if len(w) >= 2 else tuple(w)
    fixed, clash = {}, set()
    for full, first, last in rec.execute("SELECT official_full, first_name, last_name FROM legislators WHERE is_current = 1 AND state = 'PA'"):
        k = key_of(f"{first} {last}")
        if k in fixed and fixed[k] != full:
            clash.add(k)
        fixed[k] = full
    for k in clash:
        fixed.pop(k, None)
    out, fields = [], {}
    for r in kept:
        if (r["OfficeName"] or "").strip() != "REPRESENTATIVE IN CONGRESS" or r["CandidateStatusValue"] != "Approved":
            continue
        d = re.match(r"(\d+)", r["DistrictName"] or "")
        if not d:
            continue
        race = house_id("PA", int(d.group(1)))
        caps = first_last(r["CandidateName"])
        name = fixed.get(key_of(caps)) or proper(caps)
        party = r["PartyName"] or ""
        won = str(r["PrimaryResult"]).lower() == "true"
        paper = r["CandidateTypeValue"] == "Paper"
        if paper or won:
            out.append((race, "general", "2026-11-03", name, party, party_code(party), None, 0, 0, None, None, None, None, None, "pa-dos-2026-electioninfo",
                        "Pennsylvania's list writes names in capitals, family name first; they are shown here first name first."))
        if not paper:
            fields.setdefault((race, party), []).append((name, party, won))
    general = [r for r in out if r[1] == "general"]
    on_ballot = {(r[0], r[3]) for r in general}
    returns, trouble, files = official(cache, say)
    checks = [trouble] if trouble and returns else []
    nfields = 0
    if not returns:      # no official votes: the fields as the Election Information list gives them
        for (race, party), cands in fields.items():
            if len(cands) < 2:
                continue
            nfields += 1
            code = CODE.get(party, party[:3].upper())
            for name, p, won in cands:
                out.append((race, f"primary-{code}", PRIMARY, name, p, party_code(p), None, 0, 0, None, None, "advanced" if won else "lost",
                            None, None, "pa-dos-2026-electioninfo", None))
    else:
        for (race, party) in sorted(set(fields) - set(returns)):
            if len(fields[(race, party)]) > 1:
                checks.append(f"{race} {party}: {len(fields[(race, party)])} primary candidates on the list, none on the returns; not shown as a field")
        for (race, party), counted in sorted(returns.items()):
            if len(counted) < 2:      # one name on the party's primary ballot: no field
                continue
            nfields += 1
            code = CODE.get(party, party[:3].upper())
            listed = fields.get((race, party), [])
            by_family = {}
            for c in listed:
                by_family.setdefault(family(c[0]), []).append(c)
            total = sum(v for _n, v in counted)
            top = max(v for _n, v in counted)
            leaders = [n for n, v in counted if v == top]
            used = set()
            for ballot, votes in counted:
                match = by_family.get(family(ballot), [])
                note = None
                if len(match) == 1:
                    name, p, won = match[0]
                    used.add(name)
                    if won and ballot not in leaders:
                        checks.append(f"{race} {code}: the list marks {name} as the winner; the returns' top vote-getter is {' and '.join(leaders)}")
                else:
                    name, p = proper(ballot), party
                    won = leaders == [ballot]
                    checks.append(f"{race} {code}: {ballot} is on the returns but not matched on the Election Information list")
                    note = "The Department's returns print this name in capitals; it is shown here in ordinary capitals."
                if won and (race, name) not in on_ballot:
                    note = "; ".join(x for x in (note, "Won the primary; not on the Department's list for the November ballot.") if x)
                out.append((race, f"primary-{code}", PRIMARY, name, p, party_code(p), None, 0, 0, votes, round(100 * votes / total, 1) if total else None,
                            "advanced" if won else "lost", None, None, "pa-dos-2026-primary-returns", note))
            for name, p, won in listed:
                if name not in used:
                    checks.append(f"{race} {code}: {name} is a primary candidate on the list but not on the returns; not shown")
            if sum(1 for r in out if r[0] == race and r[1] == f"primary-{code}" and r[11] == "advanced") != 1:
                checks.append(f"{race} {code}: the field does not have exactly one candidate who advanced")
    cpath, off = county_check(cache, returns) if returns else (None, [])
    checks += off
    with con:
        con.execute("DELETE FROM candidates WHERE race_id LIKE '2026-PA-%'")
        con.executemany("INSERT OR REPLACE INTO candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", out)
        record_source(con, "pa-dos-2026-electioninfo", path=path, level="federal", state="PA", kind="official candidate list",
                      agency="Pennsylvania Department of State", title="PA Voter Services, Election Information: 2026 General Election",
                      url=URL, rows=len(kept), note=f"Read from the page's own candidate data (SHA-256 of the data {hashlib.sha256(raw.encode()).hexdigest()[:16]}...); "
                                                    "residence columns not kept. " + ("Primary vote counts from the Department's official returns (see its "
                                                    "Election Returns source); who advanced is this list's PrimaryResult." if returns else
                                                    "Primary vote counts not loaded yet."))
        if returns:
            record_source(con, "pa-dos-2026-primary-returns", path=files["returns"], level="federal", state="PA", kind="official results",
                          agency="Pennsylvania Department of State", title="Pennsylvania Election Returns: 2026 General Primary (May 19, 2026), "
                          "Representative in Congress, Official Returns", url=RESULTS_PAGE, published=PRIMARY,
                          rows=sum(len(v) for v in returns.values()),
                          note=f"Statewide total of every candidate in each district's Democratic and Republican primaries, read from the data call "
                               f"the Office Results page makes ({RESULTS_URL}); stored because the Department's election list ({ELECTIONS_URL}) marks "
                               "the 2026 General Primary Official (ElectionStatus O). The returns carry no write-in votes, so percentages are of the "
                               "printed candidates' votes. Election-day, mail and provisional votes add up to each total."
                               + (" Checked against the Reporting Center's county-by-county export: every candidate's counties add up to the statewide total."
                                  if cpath and not off else ""))
        if cpath:
            record_source(con, "pa-dos-2026-primary-counties", path=cpath, level="federal", state="PA", kind="official results",
                          agency="Pennsylvania Department of State", title="Pennsylvania Election Returns, Reporting Center: 2026 General Primary, "
                          "Representative in Congress, county by county (CSV export, Official)", url=REPORTS_PAGE, published=PRIMARY,
                          rows=sum(1 for _ in open(cpath, encoding="utf-8-sig")) - 1,
                          note="Used only as a check on the statewide totals. The Reporting Center builds this file on request; it was requested "
                               "once (2026-09-30) and is kept. Columns read: election, county, office, district, party, candidate and votes.")
    say(f"    Pennsylvania: {len({r[0] for r in general})} House districts, {len(general)} candidates on the November ballot, "
        f"{len(out) - len(general)} in {nfields} party primaries"
        + (", votes from the Department's official returns" if returns else f" (no votes: {trouble or 'official returns not read'})"))
    for c in checks:
        say(f"      check: {c}")
    return len(general)
