"""
North Carolina: the State Board of Elections' own files. North Carolina has fourteen House seats on the lines enacted
on October 22, 2025, and the class 2 Senate seat (Thom Tillis, not running). The primary was on March 3, 2026; no
second primary followed it (the Board's results site lists no election between March 3 and November 3, and each
field's leader passed the thirty percent that G.S. 163-111 asks for).

  November ballot   the Board's "Candidate Listing 2026" (dl.ncsbe.gov/Elections/2026/Candidate Filing/
                    Candidate_Listing_2026.csv, refreshed weekly): every candidate for every office in the March 3
                    primary and the November 3 general election, one row per county the contest reaches. The rows
                    dated 11/03/2026 for US SENATE and US HOUSE OF REPRESENTATIVES DISTRICT nn are the November ballot.
                    Every county's list of a contest must agree, name for name, party for party and in the same order;
                    that order (the same in the Board's printed "Candidate List Grouped by Contest") is kept as the
                    list order. The list gives no ballot order and no status column: a candidate who withdraws is
                    taken out of the file, so none can be counted as left off.
  primary fields    the Board's precinct results of the March 3 primary (dl.ncsbe.gov/ENRS/2026_03_03/
                    results_pct_20260303.zip, tab-separated: County, Election Date, Precinct, Contest Group ID,
                    Contest Type, Contest Name, Choice, Choice Party, Vote For, Election Day, Early Voting, Absentee
                    by Mail, Provisional, Total Votes, Real Precinct), summed by county and then statewide over every
                    precinct, administrative ones included. Each row's four voting methods must add to its total.
  control           the Board's election results site (er.ncsbe.gov): enr/elections.txt lists the elections it holds;
                    enr/20260303/data/county.txt must title every county and the state "03/03/2026 OFFICIAL PRIMARY
                    ELECTION RESULTS", with every precinct reporting; enr/20260303/data/results_0.txt gives each
                    candidate's statewide total, which must equal the precinct file's sum exactly.
  party names       the Board's own party key, in its voter statistics layout (dl.ncsbe.gov/ENRS/
                    layout_voter_stats.txt): CST Constitution, DEM Democratic, GRE Green, LIB Libertarian, NLB No
                    Labels, REP Republican, UNA Unaffiliated. A code not in the key stops the loader.

The candidate listing also carries each candidate's street address, city, state, ZIP code, three telephone numbers and
e-mail; those columns are never read. Columns are taken by name from the header: election_dt, county_name,
contest_name, name_on_ballot, party_contest, party_candidate, has_primary, is_unexpired and vote_for; the cached copy
(ballot_cache/nc/nc_candidate_listing_2026_federal.json, with the SHA-256 of the whole file) keeps only those, for
the federal rows. The results zip carries no personal details and is kept whole.

A primary field is a party's primary for a race with two candidates or more on its ballot (North Carolina prints a
party primary only when it is contested; the results carry no write-in line for these contests, so a field's total is
the sum of its candidates' votes, and a write-in line, should one appear, would count in the total only). The leader advanced. Where the leader is not the party's candidate on the November list, the row
says so. Names are printed as the list prints them (first name first, ordinary capitals); the primary rows use the
name as the results print it, which can differ from the November list (Alma Shealey Adams, Alma S. Adams).
"""

import collections
import csv
import datetime as dt
import hashlib
import io
import json
import os
import re
import time
import zipfile
from urllib.parse import quote

from ballot.common import house_id, name_parts, party_code, record_source, senate_id
from ballot.lists.tx import proper
from states import net

DL = "https://dl.ncsbe.gov/"
BUCKET = "https://s3.amazonaws.com/dl.ncsbe.gov"
LISTING = "Elections/2026/Candidate Filing/Candidate_Listing_2026.csv"
RESULTS = "ENRS/2026_03_03/results_pct_20260303.zip"
PARTY_KEY = "ENRS/layout_voter_stats.txt"
ENR = "https://er.ncsbe.gov/enr/"
ENR_SITE = "https://er.ncsbe.gov/?election_dt=03/03/2026"
PRIMARY = "2026-03-03"
PRIMARY_DT, GENERAL_DT = "03/03/2026", "11/03/2026"
KEEP = ("election_dt", "county_name", "contest_name", "name_on_ballot", "party_contest", "party_candidate",
        "has_primary", "is_unexpired", "vote_for")
RESULT_KEEP = ("County", "Election Date", "Precinct", "Contest Name", "Choice", "Choice Party", "Election Day",
               "Early Voting", "Absentee by Mail", "Provisional", "Total Votes")
METHODS = ("Election Day", "Early Voting", "Absentee by Mail", "Provisional")
CAPS = "North Carolina's list prints names in capitals; they are shown here in ordinary capitals."
RUNOFF_SHARE = 30.0


def url(key):
    return DL + quote(key)


def race_of(contest):
    """'US SENATE' -> 2026-NC-S2; 'US HOUSE OF REPRESENTATIVES DISTRICT 07' -> 2026-NC-H07; anything else None.
    A results contest carries its party after the name ('... DISTRICT 07 (REP)', '... DISTRICT 07 - REP (VOTE FOR 1)')."""
    c = re.sub(r"\s*(\((?:[A-Z]{3})\)|- [A-Z]{3} \(VOTE FOR \d+\))\s*$", "", (contest or "").strip().upper())
    if c == "US SENATE":
        return senate_id("NC", 2)
    m = re.fullmatch(r"US HOUSE OF REPRESENTATIVES DISTRICT (\d{1,2})", c)
    if m:
        return house_id("NC", int(m.group(1)))
    if c.startswith("US "):
        raise SystemExit(f"North Carolina: a federal contest the loader does not read ({contest!r})")
    return None


def shown(raw):
    """(name as shown, whether it was printed in capitals)."""
    name = re.sub(r"\s+", " ", str(raw or "")).strip()
    caps = any(c.isalpha() for c in name) and name == name.upper()
    return (proper(name) if caps else name), caps


def published(key):
    """The date the Board put a file up, from its bucket's own listing (the listing dl.ncsbe.gov/list.html reads)."""
    try:
        d = net.get(f"{BUCKET}?prefix={quote(key)}", accept="application/xml").decode("utf-8", "replace")
    except OSError:
        return ""
    for k, when in re.findall(r"<Key>(.*?)</Key><LastModified>(\d{4}-\d\d-\d\d)", d):
        if k.replace("&amp;", "&") == key:
            return when
    return ""


def fresh(path, days):
    return os.path.exists(path) and time.time() - os.path.getmtime(path) < days * 86400


def party_names(folder):
    """{code: name} from the Board's party key in its voter statistics layout."""
    path = os.path.join(folder, "nc_party_key.json")
    if not fresh(path, 30):
        text = net.get(url(PARTY_KEY), accept="text/plain").decode("utf-8", "replace")
        block = re.search(r"\nParty\s*\n-+\s*\ncode\s+description\s*\n-+[^\n]*\n(.*?)\n-{4}", text, re.S)
        if not block:
            raise SystemExit("North Carolina: the party key in layout_voter_stats.txt could not be found")
        key = {m.group(1): m.group(2).strip().title() for m in re.finditer(r"^([A-Z]{3})\s+(\S.*?)\s*$", block.group(1), re.M)}
        if not {"DEM", "REP"} <= set(key):
            raise SystemExit("North Carolina: the Board's party key does not name DEM and REP")
        json.dump({"url": url(PARTY_KEY), "read": dt.date.today().isoformat(), "key": key},
                  open(path, "w", encoding="utf-8"), indent=1)
    return json.load(open(path, encoding="utf-8"))["key"]


def listing(folder, say):
    """The candidate listing's federal rows, the kept columns only, as JSON; fetched afresh after two days."""
    path = os.path.join(folder, "nc_candidate_listing_2026_federal.json")
    if fresh(path, 2):
        return path
    try:
        data = net.get(url(LISTING), accept="text/csv,*/*")
    except OSError as e:
        if os.path.exists(path):
            say(f"      could not refresh the candidate listing ({e}); using the copy read earlier")
            return path
        raise
    text = data.decode("utf-8-sig")
    if not text.startswith('"election_dt"') and not text.startswith("election_dt"):
        raise SystemExit("North Carolina: the candidate listing did not come back as the Board's CSV")
    reader = csv.reader(io.StringIO(text))
    head = [h.strip() for h in next(reader)]
    missing = [k for k in KEEP if k not in head]
    if missing:
        raise SystemExit(f"North Carolina: the candidate listing's columns changed (no {', '.join(missing)})")
    idx = {k: head.index(k) for k in KEEP}
    total, rows = 0, []
    for r in reader:
        total += 1
        contest = r[idx["contest_name"]].strip()
        if contest.upper().startswith("US "):
            rows.append({k: r[i].strip() for k, i in idx.items()})
    meta = {"url": url(LISTING), "sha256": hashlib.sha256(data).hexdigest(), "published": published(LISTING),
            "read": dt.date.today().isoformat(), "rows_in_file": total, "columns_kept": list(KEEP), "rows": rows}
    json.dump(meta, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    return path


def precinct_totals(path):
    """{(race, party): {choice: votes}} and {(race, party): {county: votes}} from the precinct results, federal
    contests only; every row's voting methods must add to its total."""
    z = zipfile.ZipFile(path)
    names = [n for n in z.namelist() if n.lower().endswith(".txt")]
    if len(names) != 1:
        raise SystemExit(f"North Carolina: the results zip holds {len(names)} text files, not one")
    reader = csv.reader(io.StringIO(z.read(names[0]).decode("utf-8-sig")), delimiter="\t")
    head = [h.strip() for h in next(reader)]
    missing = [k for k in RESULT_KEEP if k not in head]
    if missing:
        raise SystemExit(f"North Carolina: the precinct results' columns changed (no {', '.join(missing)})")
    idx = {k: head.index(k) for k in RESULT_KEEP}
    votes = collections.defaultdict(lambda: collections.defaultdict(int))
    by_county = collections.defaultdict(lambda: collections.defaultdict(int))
    parties, bad, dates = {}, [], set()
    for r in reader:
        if not r or len(r) <= max(idx.values()):
            continue
        contest = r[idx["Contest Name"]]
        rid = race_of(contest)
        if not rid:
            continue
        m = re.search(r"\(([A-Z]{3})\)\s*$", contest)
        if not m:
            raise SystemExit(f"North Carolina: a federal primary contest names no party ({contest!r})")
        key = (rid, m.group(1))
        dates.add(r[idx["Election Date"]])
        n = int(r[idx["Total Votes"]])
        if sum(int(r[idx[k]] or 0) for k in METHODS) != n:
            bad.append((r[idx["County"]], r[idx["Precinct"]], contest, r[idx["Choice"]]))
        choice = r[idx["Choice"]].strip()
        votes[key][choice] += n
        by_county[key][r[idx["County"]]] += n
        parties[(key, choice)] = r[idx["Choice Party"]].strip()
    if dates != {PRIMARY_DT}:
        raise SystemExit(f"North Carolina: the precinct results are for {sorted(dates)}, not {PRIMARY_DT}")
    if bad:
        raise SystemExit(f"North Carolina: {len(bad)} precinct rows whose voting methods do not add to their total, e.g. {bad[0]}")
    return votes, by_county, parties


def enr_control(folder, say):
    """The results site's own word on the primary (county titles and reporting) and its statewide totals for the
    federal contests, as JSON (kept fields only); fetched afresh after thirty days."""
    path = os.path.join(folder, "nc_2026_primary_enr.json")
    if fresh(path, 30):
        return json.load(open(path, encoding="utf-8"))
    get = lambda name: json.loads(net.get(ENR + name, accept="application/json").decode("utf-8-sig"))
    elections = [e["edt"] for e in get("elections.txt")]
    counties = [{k: c.get(k) for k in ("cid", "cnm", "tle", "prt", "ptl", "imp")} for c in get("20260303/data/county.txt")]
    results = [{k: r.get(k) for k in ("cnm", "gid", "bnm", "pty", "vct", "prt", "ptl")}
               for r in get("20260303/data/results_0.txt") if str(r.get("cnm", "")).upper().startswith("US ")]
    keep = {"read": dt.date.today().isoformat(), "elections": elections, "counties": counties, "results": results}
    json.dump(keep, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return keep


def load(con, cache, say=print):
    net.patient_lookups()
    folder = os.path.join(cache, "nc")
    os.makedirs(folder, exist_ok=True)
    key = party_names(folder)

    def party_name(code):
        if code not in key:
            raise SystemExit(f"North Carolina: party code {code!r} is not in the Board's party key ({url(PARTY_KEY)})")
        return key[code]

    lpath = listing(folder, say)
    lst = json.load(open(lpath, encoding="utf-8"))
    zpath = os.path.join(folder, "results_pct_20260303.zip")
    net.download(url(RESULTS), zpath, max_age_days=30, say=say)
    if open(zpath, "rb").read(2) != b"PK":
        os.remove(zpath)
        raise SystemExit("North Carolina: the precinct results address did not give a zip file")
    enr = enr_control(folder, say)

    # control: the results site calls the primary official, everywhere, with every precinct in; no second primary
    unofficial = [c["cnm"] for c in enr["counties"] if "OFFICIAL PRIMARY" not in (c["tle"] or "").upper() or "UNOFFICIAL" in (c["tle"] or "").upper()]
    short = [c["cnm"] for c in enr["counties"] if c["prt"] != c["ptl"]]
    if unofficial or short:
        raise SystemExit(f"North Carolina: the March 3 results are not official everywhere (not official: {unofficial}; precincts missing: {short})")
    state_row = next(c for c in enr["counties"] if c["cid"] == "0")
    later = [e for e in enr["elections"] if e.endswith("/2026") and e not in (PRIMARY_DT, GENERAL_DT)
             and (e[:2], e[3:5]) > ("03", "03") and (e[:2], e[3:5]) < ("11", "03")]
    if later:
        raise SystemExit(f"North Carolina: the results site holds a later 2026 election ({later}); a second primary is not read yet")
    when = re.match(r"([A-Z][a-z]+ \d{1,2}, \d{4})", state_row.get("imp") or "")
    certified_on = dt.datetime.strptime(when.group(1), "%B %d, %Y").date().isoformat() if when else ""

    # the November ballot: every county's list of a contest must agree
    by_contest = collections.defaultdict(lambda: collections.defaultdict(list))
    primary_listed = collections.defaultdict(set)
    for r in lst["rows"]:
        rid = race_of(r["contest_name"])
        if r["election_dt"] == GENERAL_DT:
            by_contest[rid][r["county_name"]].append((r["name_on_ballot"], r["party_candidate"]))
        elif r["election_dt"] == PRIMARY_DT:
            primary_listed[(rid, r["party_contest"])].add(r["name_on_ballot"])
        else:
            raise SystemExit(f"North Carolina: a federal row for an election the loader does not read ({r['election_dt']})")
    general, november = [], {}
    for rid in sorted(by_contest):
        lists = {tuple(v) for v in by_contest[rid].values()}
        if len(lists) != 1:
            raise SystemExit(f"North Carolina: the counties' lists of {rid} differ")
        entries = next(iter(lists))
        if len(set(entries)) != len(entries):
            raise SystemExit(f"North Carolina: {rid} lists a candidate twice")
        november[rid] = entries
        for order, (raw, code) in enumerate(entries, start=1):
            name, caps = shown(raw)
            party = party_name(code)
            general.append((rid, "general", "2026-11-03", name, party, party_code(party), order, 0, 0, None, None, None,
                            None, None, "nc-sbe-2026-candidate-listing", CAPS if caps else None))

    # the primary fields, from the precinct results, checked against the listing and the results site
    votes, by_county, parties = precinct_totals(zpath)
    site = collections.defaultdict(dict)
    for r in enr["results"]:
        m = re.search(r"- ([A-Z]{3}) \(VOTE FOR", r["cnm"])
        site[(race_of(r["cnm"]), m.group(1) if m else "")][r["bnm"]] = int(r["vct"])
        if r["prt"] != r["ptl"]:
            raise SystemExit(f"North Carolina: {r['cnm']} is not fully reported on the results site")
    differ, mismatch = [], []
    for k in sorted(set(votes) | set(site) | set(primary_listed)):
        if dict(votes.get(k, {})) != site.get(k, {}):
            mismatch.append(f"{k[0]} {k[1]}")
        listed, counted = primary_listed.get(k, set()), set(votes.get(k, {}))
        if listed != counted:
            differ.append(f"{k[0]} {k[1]}: list only {sorted(listed - counted)}, results only {sorted(counted - listed)}")
    if mismatch:
        raise SystemExit("North Carolina: the precinct sums differ from the results site's official statewide totals for " + "; ".join(mismatch))
    for k, counties in by_county.items():
        if sum(counties.values()) != sum(votes[k].values()):
            raise SystemExit(f"North Carolina: county sums of {k} do not add to the statewide total")

    rows, nfields, gone = [], 0, []
    for (rid, code), cands in sorted(votes.items()):
        party = party_name(code)
        wins = [c for c in cands if not re.match(r"(?i)write", c)]
        if len(wins) < 2:
            continue
        nfields += 1
        total = sum(cands.values())
        ranked = sorted(wins, key=lambda c: -cands[c])
        if cands[ranked[0]] == cands[ranked[1]]:
            raise SystemExit(f"North Carolina: {rid} {party} primary is tied at the top")
        leader = ranked[0]
        share = 100 * cands[leader] / total
        on_list = [n for n, c in november.get(rid, ()) if c == code]
        for c in ranked:
            name, caps = shown(c)
            notes = [CAPS if caps else ""]
            if c == leader:
                if share <= RUNOFF_SHARE:
                    notes.append("Led with 30 percent or less; no second primary was held, so the leader is the nominee.")
                if not any(name_parts(n)[1] == name_parts(c)[1] for n in on_list):
                    instead = (" The Board's November list names " + " and ".join(on_list) + f" as the {party} candidate.") if on_list else ""
                    notes.append(f"Won the primary but is not on the Board's November list.{instead}")
                    gone.append(f"{name} ({rid} {party})")
            rows.append((rid, f"primary-{code}", PRIMARY, name, party, party_code(party), None, 0, 0, cands[c],
                         round(100 * cands[c] / total, 1) if total else None, "advanced" if c == leader else "lost",
                         None, None, "nc-sbe-2026-primary-results", " ".join(n for n in notes if n) or None))

    races = [r for (r,) in con.execute("SELECT race_id FROM races WHERE state='NC'")]
    empty = [r for r in races if r not in november]
    stray = [r for r in november if races and r not in races]
    if stray:
        raise SystemExit(f"North Carolina: the list names races not in the races table: {stray}")

    with con:
        con.execute("DELETE FROM candidates WHERE race_id LIKE '2026-NC-%'")
        con.executemany("INSERT OR REPLACE INTO candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", general + rows)
        record_source(con, "nc-sbe-2026-candidate-listing", path=lpath, level="federal", state="NC", kind="official candidate list",
                      agency="North Carolina State Board of Elections",
                      title="Candidate Listing 2026 (Candidate_Listing_2026.csv): the March 3 primary and the November 3 general election, county by county",
                      url=lst["url"], published=lst["published"], rows=len(lst["rows"]),
                      note=f"CSV SHA-256 {lst['sha256'][:16]}... ({lst['rows_in_file']} rows, every office). Columns taken by name: "
                           f"{', '.join(KEEP)}; addresses, telephones and e-mail are never read. The federal rows dated {GENERAL_DT} are the "
                           "November ballot; every county's list of a contest agrees, and that list order is kept (the list gives no ballot "
                           "order). The list has no status column: a candidate who withdraws is taken out of the file, so none are counted "
                           "as left off. Parties written out with the Board's own key (layout_voter_stats.txt). The rows dated "
                           f"{PRIMARY_DT} were used to check the primary results: "
                           + ("every candidate agrees." if not differ else "differences: " + "; ".join(differ))
                           + (" Primary winners not on the November list: " + "; ".join(gone) + "." if gone else ""))
        record_source(con, "nc-sbe-2026-primary-results", path=zpath, level="federal", state="NC", kind="official results",
                      agency="North Carolina State Board of Elections",
                      title="Precinct results, March 3, 2026 primary election (results_pct_20260303.zip)",
                      url=url(RESULTS), published=published(RESULTS), rows=sum(len(v) for v in votes.values()),
                      note="Federal contests summed over every precinct (administrative precincts included) by county, then statewide; "
                           "each row's four voting methods add to its total. The results carry no write-in line for these contests, so a "
                           "field's total is the sum of its candidates' votes. Every candidate's statewide sum equals the results site's official total.")
        record_source(con, "nc-sbe-2026-primary-enr", path=os.path.join(folder, "nc_2026_primary_enr.json"), level="federal", state="NC",
                      kind="official results", agency="North Carolina State Board of Elections",
                      title=f"Election results site: {state_row['tle']}", url=ENR + "20260303/data/results_0.txt", published=certified_on,
                      rows=len(enr["results"]),
                      note=f"Control only (from {ENR_SITE}): every county and the state are titled OFFICIAL, with {state_row['prt']} of "
                           f"{state_row['ptl']} precincts reporting; the statewide totals match the precinct file exactly. The site lists "
                           "no election between March 3 and November 3, 2026, so no second primary was held.")
    n = len(general)
    say(f"    North Carolina: {sum(1 for r in november if '-H' in r)} House districts and the Senate race, {n} candidates on the November "
        f"ballot (the list has no status column, so none withdrawn can be counted); {nfields} party primaries with a field, votes from "
        f"the official results, no second primary" + (f"; primary winners not on the November list: {', '.join(gone)}" if gone else ""))
    if empty:
        say(f"      races with no November candidates on the list: {', '.join(empty)}")
    if differ:
        say("      the candidate listing and the primary results differ: " + "; ".join(differ))
    return n
