"""
ballot/ar_place_votes.py - how each Arkansas place voted in past partisan general elections, so a page can show the
record of a county or a district without anyone labelling a candidate. The Arkansas twin of ballot/mn_place_votes.py;
the output has the same shape (the Democratic count is "dem" here, as in the other states' files, where Minnesota's is
"dfl").

    python ballot/ar_place_votes.py               reads (or downloads) the results, writes ballot/lean/ar_place_votes.json
    python ballot/ar_place_votes.py --refresh     asks for everything again even when the cached copies are there
    python ballot/ar_place_votes.py --out x.json  writes somewhere else; --cache DIR keeps the downloads somewhere else
    python ballot/ar_place_votes.py --selftest    the arithmetic and the district rules on made-up precincts; downloads nothing

What it is, and is not
----------------------
For President in 2024, Governor and U.S. Senator in 2022, and President and U.S. Senator in 2020: the votes for the
Democratic ticket, the Republican ticket, every other candidate and all write-ins together, and the total, for every one
of the 75 counties and for each judicial district whose own contest on the March 3, 2026 ballot reached whole counties;
for 2022 and 2024 also for every state House and Senate district whose precincts voted in that district alone (see
below). No Democrat was on Arkansas's 2020 ballot for U.S. Senator: Ricky Dale Harrington Jr. was the Libertarian
nominee, and his votes are a count of their own ("lib") rather than being folded into "other". It is how the people of
a place voted then, on the lines in force at that election. It is not a prediction, it says nothing about any candidate
on a later ballot or about any voter, and it turns no nonpartisan office into a partisan one. No database is opened for
writing; ballot_local_2026.sqlite is opened read-only at the end, only to count how many of our places are covered.

Where the numbers come from
---------------------------
The Arkansas Secretary of State's official results, from its results site (arkansas.tally-enr.com) and the site's own
data service (enr-results-api.totalresults.com, client "arkansas"), which answers a plain script with JSON and holds the
2020, 2022 and 2024 general elections, each marked official:
  - Election/GetElectionInfo: the parties, and every county's precincts (an id and a name);
  - Contest/GetContestSearchList: each contest's name and its candidates as the ballot printed them (only the federal,
    statewide, state Senate and state House contests are kept);
  - Contest/GetSingleContestResults (one statewide contest): the statewide figures and each county's row;
  - Contest/GetContestResults with a county's locationId: every contest of the county with its precinct rows.
Of a precinct row only the precinct's id, each candidate's id and count and the row's total are read. A county's
figures are its row in the statewide contest; they must equal the county's own figures and its precinct rows added up.
The 2026 Preferential Primary (March 3, 2026) is read the same way for the circuit judge and prosecuting attorney
contests only, to find which counties each judicial district is.

Which district a precinct is in
-------------------------------
Arkansas's House and Senate districts were drawn in 2021 and used from 2022, so the 2022 and 2024 elections were held on
today's lines; 2020's results are on the old lines and are given for counties and judicial districts only. Which
districts reach each county is read from the Census Bureau's 2024 State Legislative Block Equivalency Files (the plans
the state reported, block by block; the 2022 and 2024 elections were held on them). A precinct lies (at least partly) in
every district whose contest it voted in. It may also lie in a district that reaches its county but has no results
there that year: a Senate seat not on the 2024 ballot (18 of 35 were), or a contest with one candidate that the county
did not print (in 2022 several counties printed no unopposed legislative contest; in 2024 a few). A contest a county
printed is taken to count every precinct of the county that lies in the district, except that a precinct which voted in
no contest of the kind although every district reaching its county has results there is a gap in the precinct lists (a
few 2022 precincts) and could lie in any of them. The same precinct (county, id and name) in the other election narrows
the choice, since the lines did not change, unless the two years contradict each other. A precinct is placed only where
one district is left; a precinct listed in two districts' contests lies in both (Arkansas precincts are often split
between House districts) and its votes are given whole, so they cannot be divided without an estimate. A district is
given for a year only where no unplaced precinct may lie in it; most are therefore not given.

A judicial district is whole counties: the counties whose every precinct voted in a contest for the whole district (a
circuit judge's division with no subdistrict, or the prosecuting attorney) on the March 3, 2026 ballot. A district with
no such contest that day is not given. The district ids follow our pages (AR-JD2, AR-JD11-West, AR-JD8-North).

Not given: cities and towns and their wards (a precinct may reach beyond a city's line: the results give each precinct
whole and do not say how many of its voters live in the city; in 2024 one Pulaski County precinct even voted in two
congressional districts), justice of the peace districts and townships, school, fire and other districts.

The control
-----------
Nothing is written unless all of this holds: each election is marked official and is the general election of its date;
every precinct row's candidates add up to the row's total; each county's precinct rows add up, candidate by candidate,
to the county's own figures, which equal the county's row in the statewide contest; every precinct reported; the
counties add up to the statewide figures, which equal the Clerk of the U.S. House of Representatives' "Statistics of the
Presidential and Congressional Election" for President and U.S. Senator; every precinct in a legislative contest is in
the statewide contests, and every district it voted in reaches its county in the Census file; the House and Senate
districts given and the precincts of those left out add up to the statewide figures. The Governor's figures have no
second official compilation that a script reads; the file says so.
"""
import argparse
import collections
import datetime as dt
import hashlib
import json
import os
import pathlib
import re
import sqlite3
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

METHOD = "1.0"                  # change how anything is added up or matched, and this goes up
CACHE = os.path.join(HERE, "ballot_cache", "ar", "votes")
OUT = os.path.join(HERE, "ballot", "lean", "ar_place_votes.json")
DB = os.path.join(HERE, "ballot_local_2026.sqlite")
STATE_FIPS = "05"
FEW = 20
KEEP_DAYS = 3650                # certified results of past elections do not change; --refresh asks again
PAUSE = 0.6                     # seconds between requests to the results service

API = "https://enr-results-api.totalresults.com/"
SITE = "https://arkansas.tally-enr.com/"
CLIENT = "arkansas"
AGENCY = "Arkansas Secretary of State, Elections Division"
RESULTS_PAGE = "https://www.sos.arkansas.gov/elections/research/election-results"
ELECTIONS = {2024: ("1846", "2024 General", "2024-11-05"), 2022: ("1844", "2022 General", "2022-11-08"),
             2020: ("1841", "2020 General", "2020-11-03")}
PRIMARY_2026 = ("7f77a178-af02-40ec-92db-c5cc50882c68", "2026 Preferential Primary", "2026-03-03")
DISTRICT_YEARS = (2024, 2022)
KEEP_TYPES = ("FED", "STW", "SEN", "REP")
CLERK = {2024: ("November 5, 2024", "Presidential and Congressional"), 2022: ("November 8, 2022", "Congressional"),
         2020: ("November 3, 2020", "Presidential and Congressional")}

# The contests: id, year, office, the results' contest name and the nominees as the ballot printed them (with any title
# the filer gave, as Arkansas prints them).
CONTESTS = [
    {"id": "2024-president", "year": 2024, "date": "2024-11-05", "office": "President and Vice President of the United States", "name": "U.S. President",
     "dem": ("Democratic", "Harris and Walz", "Kamala D. Harris/Tim Walz"), "rep": ("Republican", "Trump and Vance", "Donald J. Trump/JD Vance"),
     "clerk": "FOR PRESIDENTIAL ELECTORS"},
    {"id": "2022-governor", "year": 2022, "date": "2022-11-08", "office": "Governor", "name": "Governor",
     "dem": ("Democratic", "Jones", "Chris Jones"), "rep": ("Republican", "Sanders", "Sarah Huckabee Sanders")},
    {"id": "2022-us-senate", "year": 2022, "date": "2022-11-08", "office": "United States Senator", "name": "U.S. Senate",
     "dem": ("Democratic", "James", "Natalie James"), "rep": ("Republican", "Boozman", "Senator John Boozman"), "clerk": "FOR UNITED STATES SENATOR"},
    {"id": "2020-president", "year": 2020, "date": "2020-11-03", "office": "President and Vice President of the United States", "name": "U.S. President, Vice President",
     "dem": ("Democratic", "Biden and Harris", "Joseph R. Biden/Kamala Harris"), "rep": ("Republican", "Trump and Pence", "Donald J. Trump/Michael R. Pence"),
     "clerk": "FOR PRESIDENTIAL ELECTORS"},
    {"id": "2020-us-senate", "year": 2020, "date": "2020-11-03", "office": "United States Senator", "name": "U.S. Senate",
     "rep": ("Republican", "Cotton", "Senator Tom Cotton"), "lib": ("Libertarian", "Harrington", "Ricky Dale Harrington Jr."), "clerk": "FOR UNITED STATES SENATOR"},
]
SIDE_KEYS = ("dem", "rep", "lib")
PARTY_WORD = {"dem": "Democratic", "rep": "Republican", "lib": "Libertarian"}

KINDS = [
    ("county", "Counties", "five-digit county FIPS code, as sl_places kind county and the jurisdiction_id of our county races"),
    ("judicial", "Judicial districts (circuits), as whole counties",
     "AR-JD and the district as our pages write it (AR-JD2, AR-JD11-West, AR-JD8-North), as the jurisdiction_id of our circuit judge and prosecuting attorney races"),
    ("house", "State House districts of the plan first used in 2022", "district number, as the district of our House races"),
    ("senate", "State Senate districts of the plan first used in 2022", "district number, as the district of our Senate races"),
]
WHAT = ("How each Arkansas place voted in five contests of the 2020, 2022 and 2024 general elections: the votes for the Democratic ticket, "
        "the Republican ticket (and in 2020, when no Democrat was on the ballot for U.S. Senator, the Libertarian candidate), every other "
        "candidate and all write-ins together and the total, from the Secretary of State's official results, county by county and, added up "
        "here, precinct by precinct for each state House and Senate district.")
NOTE = ("What this is: how the people of a place voted in that election, in the Arkansas Secretary of State's official results: each county's "
        "own figures, with the official precinct results added up here by state House and Senate district for 2022 and 2024 (the elections "
        "held on today's districts); 2020 is given for counties and judicial districts only, because the districts were drawn again in 2021. "
        "A judicial district is its counties added up. A district is given only where every precinct of it voted in that district alone: "
        "where a precinct lies in two districts the results give its votes whole, and they are never divided by estimate. What this is not: "
        "it is not a prediction of any election; it says nothing about any candidate on a later ballot or about any voter; a nonpartisan "
        "office stays nonpartisan; and a place is not its lines for ever: the figures are for the lines of that year. Arkansas elected its "
        "Governor in 2022, and in 2020 no Democrat was on its ballot for U.S. Senator. The tickets are named, as the results name them, only "
        "to say which election this was. In a place with very few voters the split would come close to saying how particular people voted; "
        "those contests are listed in the place's too_few, and a page should leave the split out.")
HOW_TO_READ = ("Each place's votes are four counts for each contest: dem (the Democratic ticket), rep (the Republican ticket), other (every "
               "other candidate and all write-ins, together) and total (the votes for candidates and write-ins). For U.S. Senator in 2020, when "
               "no Democrat was on the ballot, the counts are rep, lib (Ricky Dale Harrington Jr., the Libertarian nominee), other and total. "
               "Minnesota's file calls the first count dfl. A contest a place does not have was not counted on its lines: House and Senate "
               "districts are given for 2022 and 2024 only, and only where no precinct of the district lies in another district too.")
TOO_FEW = (f"A place's too_few lists the contests in which it had fewer than {FEW} votes, or in which every vote went the same way. There the "
           "split comes close to saying how particular people voted, so a page should leave it out. The counts are the official record all "
           "the same, and are kept here so that the sums can be checked.")
NOT_GIVEN = ("Cities and towns, and their wards: a precinct may reach beyond a city's line, the results give each precinct whole and do not "
             "say how many of its voters live in the city, so a city's votes cannot be added up without an estimate (in 2024 one Pulaski "
             "County precinct even voted in two congressional districts). Justice of the peace districts, townships, school, fire and other "
             "districts are not added up here. House and Senate districts for 2020: that election was held on the lines drawn in 2011.")
WHY_NOT = ("House and Senate districts are given for 2022 and 2024 only: the 2020 election was held on the districts drawn in 2011. A "
           "district missing from a year has a precinct that lies in it and in another district too (Arkansas precincts are often split "
           "between districts, and the results give a precinct's votes whole), or one the record does not place in a single district: "
           "in 2024 only 18 of the 35 Senate seats were on the ballot, and in 2022 several counties printed no unopposed legislative contest.")


def say_default(msg):
    print(msg, flush=True)


def _now():
    return dt.date.today().isoformat()


def _day(path):
    return dt.datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d")


def _sha_file(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def fresh(path, refresh, days=KEEP_DAYS):
    return (not refresh) and os.path.exists(path) and os.path.getsize(path) > 0 and (time.time() - os.path.getmtime(path)) < days * 86400


def write_whole(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".part", "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False)
    os.replace(path + ".part", path)


def ask(path_query, waits=(5, 20, 60)):
    from states import net
    for wait in tuple(waits) + (None,):
        try:
            raw = net.get(API + path_query, accept="application/json")
            time.sleep(PAUSE)
            return json.loads(raw.decode("utf-8-sig"))
        except (OSError, ValueError):
            if wait is None:
                raise
            time.sleep(wait)


def cached(path, refresh, make):
    """A trimmed extract, cached whole (written under another name and renamed, so a half-written copy is never read)."""
    if fresh(path, refresh):
        return json.load(open(path, encoding="utf-8"))
    data = make()
    write_whole(path, data)
    return data


def letters(s):
    return re.sub(r"[^A-Z]", "", str(s).upper())


def county_name(raw):
    return " ".join(w.capitalize() for w in raw.strip().split()) + " County"


# ---------- reading the results service (only the kept fields are cached) ----------

def election_meta(eid, name, date, cache, refresh):
    """The election as the service lists it, its parties and every county's precincts."""
    def make():
        listed = [e for e in ask(f"Election/GetElectionList?cid={CLIENT}") if str(e.get("electionID")) == eid]
        if len(listed) != 1 or listed[0].get("electionName") != name or not str(listed[0].get("electionDate", "")).startswith(date):
            raise SystemExit(f"Arkansas: the results service does not list election {eid} as the {name} of {date}")
        info = ask(f"Election/GetElectionInfo?cId={CLIENT}&electionID={eid}")
        resp = info["response"]
        return {"election_id": eid, "name": resp["name"], "date": str(resp["date"])[:10], "official": bool(info.get("isOfficial")),
                "version": info.get("versionID"), "last_updated": info.get("lastUpdated"),
                "parties": {k: v["partyName"] for k, v in (resp.get("parties") or {}).items()},
                "counties": {c: {"name": cl["locationName"], "precincts": {p: pl["locationName"] for p, pl in (cl.get("locations") or {}).items()}}
                             for c, cl in resp["locations"].items()}}
    meta = cached(os.path.join(cache, eid, "election.json"), refresh, make)
    if not meta["official"] or meta["name"] != name or meta["date"] != date:
        raise SystemExit(f"Arkansas: the {name} is not marked official, or is not of {date}")
    return meta


def contest_list(eid, cache, refresh, keep=lambda c: c.get("contestTypeCode") in KEEP_TYPES):
    def make():
        s = ask(f"Contest/GetContestSearchList?cid={CLIENT}&electionID={eid}")
        if not s.get("isOfficial"):
            raise SystemExit(f"Arkansas: the contest list of election {eid} is not marked official")
        return {cid: {"name": re.sub(r"\s+", " ", c["contestName"]).strip(), "type": c.get("contestTypeCode"), "vote_for": c.get("voteFor"),
                      "choices": {ch: {"name": x["name"], "party": x.get("partyID"), "write_in": bool(x.get("isWriteIn"))} for ch, x in c["choices"].items()}}
                for cid, c in s["response"]["contests"].items() if keep(c)}
    return cached(os.path.join(cache, eid, "contests.json"), refresh, make)


def row(r):
    """One row of results (a contest's statewide figures, a county's or a precinct's): {choice id: votes}, total, reporting."""
    ch = {}
    for x in (r.get("choices") or []) + (r.get("writeinChoices") or []) + (r.get("writeInChoices") or []):
        cid = str(x["choiceID"])
        ch[cid] = ch.get(cid, 0) + int(x.get("totalVotes") or 0)
    return {"choices": ch, "total": int(r.get("totalVotes") or 0),
            "reporting": [r.get("precinctsReporting"), r.get("totalPrecincts")]}


def statewide_contest(eid, cid, ctype, cache, refresh):
    def make():
        r = ask(f"Contest/GetSingleContestResults?cId={CLIENT}&electionID={eid}&contestType={ctype}&contestID={cid}")
        if not r.get("isOfficial"):
            raise SystemExit(f"Arkansas: contest {cid} of election {eid} is not marked official")
        resp = r["response"]
        return {"state": row(resp), "counties": {c: row(x) for c, x in (resp.get("locations") or {}).items()}}
    return cached(os.path.join(cache, eid, f"statewide_{cid}.json"), refresh, make)


def county_contests(eid, fips, wanted, cache, refresh):
    """Every kept contest of one county: {contest id: {county row, precincts: {precinct id: row}}}."""
    def make():
        r = ask(f"Contest/GetContestResults?cId={CLIENT}&electionID={eid}&contestType=FED&locationId={fips}")
        if not r.get("isOfficial"):
            raise SystemExit(f"Arkansas: the results of county {fips} in election {eid} are not marked official")
        out = {}
        for cid, c in (r["response"].get("contests") or {}).items():
            if cid in wanted:
                out[cid] = {"county": row(c), "precincts": {p: row(x) for p, x in (c.get("locations") or {}).items()}}
        return out
    return cached(os.path.join(cache, eid, "county", f"{fips}.json"), refresh, make)


# ---------- the sides of a contest ----------

def sides(contest, clist, parties):
    """{choice id: key} for a statewide contest: the nominees by the name the ballot printed and their party, else other."""
    hit = [cid for cid, c in clist.items() if c["name"] == contest["name"] and c["type"] in ("FED", "STW")]
    if len(hit) != 1:
        raise SystemExit(f"Arkansas: the contest {contest['name']!r} ({contest['id']}) is not listed once")
    cid = hit[0]
    keys = {}
    for ch, c in clist[cid]["choices"].items():
        keys[ch] = "other"
        for k in SIDE_KEYS:
            if contest.get(k) and letters(c["name"]) == letters(contest[k][2]):
                party = parties.get(str(c["party"]), "")
                # the service's party table names the Democratic and Republican parties only (its other entries are a
                # vendor's list from another state); a Libertarian's label is checked on the Clerk's statistics instead
                if c["write_in"] or (k != "lib" and not party.startswith(PARTY_WORD[k])):
                    raise SystemExit(f"Arkansas: {contest['id']}: {c['name']!r} is not printed as {PARTY_WORD[k]} ({party!r})")
                keys[ch] = k
        if keys[ch] == "other" and not c["write_in"]:
            party = parties.get(str(c["party"]), "")
            for k in ("dem", "rep"):
                if contest.get(k) and party.startswith(PARTY_WORD[k]):
                    raise SystemExit(f"Arkansas: {contest['id']}: a {PARTY_WORD[k]} candidate is {c['name']!r}, not {contest[k][2]!r}")
    for k in SIDE_KEYS:
        if contest.get(k) and list(keys.values()).count(k) != 1:
            raise SystemExit(f"Arkansas: {contest['id']}: the {k} nominee is not listed once")
    return cid, clist[cid]["type"], keys


def four(r, keys, contest):
    out = {k: 0 for k in SIDE_KEYS if contest.get(k)}
    out.update(other=0, total=0)
    for ch, v in r["choices"].items():
        if ch not in keys:
            raise SystemExit(f"Arkansas: {contest['id']}: a row counts votes for a candidate ({ch}) the contest does not list")
        out[keys[ch]] += v
        out["total"] += v
    return out


# ---------- districts ----------

DIST_RX = re.compile(r"^State (Representative|Senate) District 0*(\d+)$")


def district_contests(clist):
    """{contest id: ("house" or "senate", number)} for every state House and Senate contest."""
    out = {}
    for cid, c in clist.items():
        m = DIST_RX.match(c["name"])
        if c["type"] in ("REP", "SEN"):
            if not m or (m.group(1) == "Representative") != (c["type"] == "REP"):
                raise SystemExit(f"Arkansas: a legislative contest is named {c['name']!r}")
            out[cid] = ("house" if c["type"] == "REP" else "senate", int(m.group(2)))
    return out


def could_be(listed, reach, present):
    """The districts a precinct can lie in: those whose contest it voted in, and those that reach its county (by the
    Census Bureau's block equivalency file) but have no results in the county that year (not on the ballot, or a
    contest with one candidate that the county did not print). A contest a county printed counts every precinct of the
    county that lies in the district, so a district with results in the county that the precinct did not vote in is
    not one it lies in. A precinct that voted in no contest of the kind although every district reaching its county has
    results there is a gap in the precinct lists (the 2022 lists miss a few precincts), and it could be in any of them."""
    off = set(reach) - set(present)
    if not listed and not off:
        return set(reach)
    return set(listed) | off


def settle(ps, other_ps=None, listed=(), other_listed=()):
    """(district, None) when the precinct lies in one district alone, else (None, the districts it could be in). The same
    precinct (county, id and name) in the other election on the same lines narrows the choice, unless the two years
    contradict each other (a district one year's ballot puts it in that the other year's rules out), when it is not used."""
    final = set(ps)
    if other_ps is not None and set(listed) <= set(other_ps) and set(other_listed) <= set(ps):
        final &= set(other_ps)
    if len(final) == 1:
        return next(iter(final)), None
    return None, final


# ---------- adding up ----------

def add(into, v):
    for k, n in v.items():
        into[k] = into.get(k, 0) + n


def few(votes):
    out = []
    for cid, v in votes.items():
        parts = [n for k, n in v.items() if k != "total"]
        if v["total"] < FEW or (v["total"] and max(parts) == v["total"]):
            out.append(cid)
    return out


def jd_label(raw):
    """'District 08-N', 'Dist. 11-West', 'DISTRICT 04' -> '8-North', '11-West', '4' (as state_local_ar writes them)."""
    m = re.search(r"\bDist(?:rict|\.)?\s*0*(\d+)(?:\s*-\s*(North|South|East|West|N|S|E|W)\b)?", raw, re.I)
    if not m:
        return None
    side = {"n": "North", "s": "South", "e": "East", "w": "West"}.get((m.group(2) or "")[:1].lower())
    return m.group(1) + (f"-{side}" if side else "")


def district_wide(name):
    """A March 3, 2026 contest for a whole judicial district: a circuit judge's division with no subdistrict, or the
    prosecuting attorney. Party contests (circuit clerks) are not."""
    if re.match(r"^(REP|DEM|LIB)\b", name) or re.search(r"\bclerk\b", name, re.I) or re.search(r"subdist", name, re.I):
        return False
    return bool(re.search(r"^(Circuit (Court )?Judge|Prosecuting Attorney)\b", name, re.I))


def selftest():
    # county reached by districts 7, 8 and 9; 8 and 9 had results in the county, 7 did not
    assert could_be([8], {7, 8, 9}, {8, 9}) == {7, 8}
    assert could_be([8], {8, 9}, {8, 9}) == {8}
    assert could_be([], {7, 8, 9}, {8, 9}) == {7}
    assert could_be([], {8, 9}, {8, 9}) == {8, 9}
    assert settle({8}) == (8, None)
    assert settle({7, 8}) == (None, {7, 8})
    assert settle({7, 8}, {8}, [8], [8]) == (8, None)
    assert settle({7, 8}, {7, 9}, [8], [9]) == (None, {7, 8})          # the years contradict each other: not used
    assert settle({7, 8}, {7, 8}, [8], [8]) == (None, {7, 8})
    assert settle({8, 9}, {8, 9}, [8, 9], [8, 9]) == (None, {8, 9})
    assert jd_label("Circuit Judge, District 08-N, Division 02") == "8-North"
    assert jd_label("Prosecuting Attorney, Dist. 11-West") == "11-West"
    assert jd_label("CIRCUIT JUDGE DISTRICT 04 DIVISION 02") == "4"
    assert district_wide("Circuit Judge, District 02, Division 4 AT-LARGE") and not district_wide("Circuit Judge, District 06, Division 03, Subdistrict 6.2")
    assert not district_wide("REP Circuit Clerk") and district_wide("Prosecuting Attorney, District 21")
    c = {"id": "t", "dem": 1, "rep": 1}
    assert four({"choices": {"a": 5, "b": 7, "c": 1}}, {"a": "dem", "b": "rep", "c": "other"}, c) == {"dem": 5, "rep": 7, "other": 1, "total": 13}
    assert few({"x": {"dem": 0, "rep": 19, "other": 0, "total": 19}, "y": {"dem": 1, "rep": 30, "other": 0, "total": 31}}) == ["x"]
    assert county_name("ST. FRANCIS") == "St. Francis County" and county_name("HOT SPRING") == "Hot Spring County"
    print("selftest: ok")


# ---------- the Clerk of the House ----------

def clerk_check(doc, section, contest):
    lines = [(lab, v) for lab, v in doc["sections"].get(section) or [] if lab not in ("Under Votes", "Over Votes")]
    party = (lambda s: s) if section == "FOR PRESIDENTIAL ELECTORS" else (lambda s: s.rsplit(",", 1)[-1].strip())
    out = {}
    for k in SIDE_KEYS:
        if contest.get(k):
            hit = [v for lab, v in lines if party(lab).startswith(PARTY_WORD[k] if k != "dem" else "Democrat")]
            if len(hit) != 1:
                raise SystemExit(f"Arkansas: the Clerk's {section} has not one {PARTY_WORD[k]} line")
            out[k] = hit[0]
    total = sum(v for _l, v in lines)
    out["other"] = total - sum(out.values())
    out["total"] = total
    return out


# ---------- our places ----------

def our_places(db):
    if not db or not os.path.exists(db):
        return None
    con = sqlite3.connect(pathlib.Path(os.path.abspath(db)).as_uri() + "?mode=ro", uri=True)
    try:
        out = collections.defaultdict(set)
        for kind, pid in con.execute("SELECT kind, id FROM sl_places WHERE source_id LIKE 'ar-%'"):
            out[kind].add(pid)
        for office, level, jid, district in con.execute("SELECT office_kind, level, jurisdiction_id, district FROM sl_races WHERE state = 'AR'"):
            if office == "state_senate":
                out["senate"].add(str(district))
            elif office == "state_house":
                out["house"].add(str(district))
            elif level == "court" and re.fullmatch(r"AR-JD[\w-]+", str(jid or "")):
                out["judicial"].add(str(jid))
            elif level == "county" and re.fullmatch(r"05\d{3}", str(jid or "")):
                out["county"].add(str(jid))
        return dict(out)
    finally:
        con.close()


# ---------- the run ----------

def read_year(year, cache, refresh, say):
    """One general election: {meta, contests (statewide, with keys), precincts {(fips, pid): {...}}, county, statewide, districts}."""
    eid, name, date = ELECTIONS[year]
    meta = election_meta(eid, name, date, cache, refresh)
    clist = contest_list(eid, cache, refresh)
    if len(meta["counties"]) != 75:
        raise SystemExit(f"Arkansas {year}: the results service lists {len(meta['counties'])} counties, not 75")
    mine = [c for c in CONTESTS if c["year"] == year]
    keyed = {}
    for c in mine:
        cid, ctype, keys = sides(c, clist, meta["parties"])
        keyed[c["id"]] = (cid, ctype, keys)
    dists = district_contests(clist) if year in DISTRICT_YEARS else {}
    wanted = {cid for cid, _t, _k in keyed.values()} | set(dists)
    statewide, state_rows = {}, {}
    for c in mine:
        cid, ctype, keys = keyed[c["id"]]
        sw = statewide_contest(eid, cid, ctype, cache, refresh)
        if sw["state"]["reporting"][0] != sw["state"]["reporting"][1]:
            raise SystemExit(f"Arkansas {year}: {c['id']}: not every precinct reported")
        statewide[c["id"]] = four(sw["state"], keys, c)
        if statewide[c["id"]]["total"] != sw["state"]["total"]:
            raise SystemExit(f"Arkansas {year}: {c['id']}: the candidates do not add up to the statewide total")
        if set(sw["counties"]) != set(meta["counties"]):
            raise SystemExit(f"Arkansas {year}: {c['id']}: the county rows are not the 75 counties")
        for fips, r in sw["counties"].items():
            state_rows[(fips, c["id"])] = four(r, keys, c)
    precincts = {}
    county = {}
    present = {}
    for fips in sorted(meta["counties"]):
        got = county_contests(eid, fips, wanted, cache, refresh)
        listed = meta["counties"][fips]["precincts"]
        for c in mine:
            cid, _t, keys = keyed[c["id"]]
            if cid not in got:
                raise SystemExit(f"Arkansas {year}: {c['id']}: no results for county {fips}")
            g = got[cid]
            own = four(g["county"], keys, c)
            if own != state_rows[(fips, c["id"])]:
                raise SystemExit(f"Arkansas {year}: {c['id']} {fips}: the county's figures differ from its row in the statewide contest")
            if g["county"]["reporting"][0] != g["county"]["reporting"][1]:
                raise SystemExit(f"Arkansas {year}: {c['id']} {fips}: not every precinct reported")
            s = {}
            for pid, r in g["precincts"].items():
                if pid not in listed:
                    raise SystemExit(f"Arkansas {year}: {c['id']} {fips}: a precinct row ({pid}) names no precinct of the county")
                if sum(r["choices"].values()) != r["total"]:
                    raise SystemExit(f"Arkansas {year}: {c['id']} {fips} {listed[pid]}: the candidates do not add up to the row's total")
                v = four(r, keys, c)
                add(s, v)
                p = precincts.setdefault((fips, pid), {"county": fips, "id": pid, "name": listed[pid], "votes": {}, "house": set(), "senate": set()})
                p["votes"][c["id"]] = v
            if s != own:
                raise SystemExit(f"Arkansas {year}: {c['id']} {fips}: the precinct rows do not add up to the county's figures")
            county.setdefault(fips, {})[c["id"]] = own
        for cid, (kind, n) in dists.items():
            if cid in got:
                present.setdefault(fips, {"house": set(), "senate": set()})[kind].add(n)
            for pid in (got.get(cid) or {}).get("precincts", {}):
                if (fips, pid) not in precincts:
                    # a precinct that voted in a legislative contest but in no statewide contest
                    raise SystemExit(f"Arkansas {year}: {fips} {listed.get(pid, pid)}: in a {kind} contest but in no statewide contest")
                precincts[(fips, pid)][kind].add(n)
        say(f"      {year} {county_name(meta['counties'][fips]['name'])}: {sum(1 for k in precincts if k[0] == fips)} precincts")
    for key, p in precincts.items():
        if sorted(p["votes"]) != sorted(c["id"] for c in mine):
            raise SystemExit(f"Arkansas {year}: precinct {key} does not vote in every statewide contest of the year")
    return {"meta": meta, "statewide": statewide, "county": county, "precincts": precincts, "dists": dists,
            "keyed": keyed, "contests": clist, "present": present}


# ---------- which districts reach each county (the Census Bureau's block equivalency files) ----------

BEF = {"house": ("https://www2.census.gov/programs-surveys/decennial/rdo/mapping-files/2025/2024-state-legislative-bef/sldl24.zip", "NationalSLDL24.txt"),
       "senate": ("https://www2.census.gov/programs-surveys/decennial/rdo/mapping-files/2025/2024-state-legislative-bef/sldu24.zip", "NationalSLDU24.txt")}
BEF_PAGE = "https://www.census.gov/geographies/mapping-files/2025/dec/rdo/2024-state-legislative-bef.html"


def reach(cache, refresh, say):
    """{kind: {county fips: set of districts}} from every Arkansas block of the 2024 plans (the plan of 2022 and 2024),
    with each file's SHA-256. Only the block ids' county part and the district are read."""
    import zipfile
    from states import net
    out, recs = {}, []
    for kind, (url, member) in BEF.items():
        path = os.path.join(cache, "census", os.path.basename(url))
        net.download(url, path, 0 if refresh else KEEP_DAYS, tries=4, say=say)
        rel = collections.defaultdict(set)
        blocks = 0
        with zipfile.ZipFile(path) as z, z.open(member) as fh:
            head = fh.readline().decode("ascii").strip().split(",")
            if head[0] != "GEOID" or len(head) != 2:
                raise SystemExit(f"Arkansas: the Census file {member} does not begin GEOID,<district>")
            for line in fh:
                if not line.startswith(b"05"):
                    continue
                geoid, dist = line.decode("ascii").strip().split(",")
                blocks += 1
                if dist.strip().upper() in ("", "ZZZ"):
                    continue
                rel[geoid[:5]].add(int(dist))
        want = 100 if kind == "house" else 35
        if len(rel) != 75 or set().union(*rel.values()) != set(range(1, want + 1)):
            raise SystemExit(f"Arkansas: the Census file {member} does not hold 75 counties and {want} districts")
        out[kind] = {f: sorted(v) for f, v in rel.items()}
        recs.append({"file": os.path.basename(url), "member": member, "blocks": blocks, "sha256": _sha_file(path), "fetched": _day(path)})
    return out, recs


def judicial(cache, refresh, say):
    """{label: [county fips]} from the March 3, 2026 contests for whole judicial districts, each county reached whole."""
    eid, name, date = PRIMARY_2026
    meta = election_meta(eid, name, date, cache, refresh)
    clist = contest_list(eid, cache, refresh, keep=lambda c: district_wide(re.sub(r"\s+", " ", c["contestName"]).strip()))
    found, used = {}, []
    for cid, c in sorted(clist.items(), key=lambda kv: kv[1]["name"]):
        label = jd_label(c["name"])
        if not label:
            raise SystemExit(f"Arkansas 2026: the district of {c['name']!r} could not be read")
        sw = statewide_contest(eid, cid, c["type"], cache, refresh)
        counties = sorted(sw["counties"])
        for fips in counties:
            rep = sw["counties"][fips]["reporting"]
            if rep[1] != len(meta["counties"][fips]["precincts"]) or rep[0] != rep[1]:
                raise SystemExit(f"Arkansas 2026: {c['name']}: county {fips} is not reached whole ({rep} of {len(meta['counties'][fips]['precincts'])} precincts)")
        if label in found and found[label] != counties:
            raise SystemExit(f"Arkansas 2026: two contests of judicial district {label} reach different counties")
        found[label] = counties
        used.append({"contest": c["name"], "district": label, "counties": counties})
    say(f"   2026: {len(found)} judicial districts from the March 3 contests")
    return found, used, meta


def run(out_path, cache, refresh, say=say_default):
    from states import net
    from ballot.wy_place_votes import read_clerk
    net.patient_lookups()
    os.makedirs(cache, exist_ok=True)
    say("Arkansas: past votes by place")
    sources, control = [], {"result": "equal", "contests": {}, "precincts": {}}
    years = {}
    for year in (2024, 2022, 2020):
        say(f"   {year}: the official results, county by county and precinct by precinct")
        years[year] = read_year(year, cache, refresh, say)
        control["precincts"][str(year)] = len(years[year]["precincts"])
    names = {f: county_name(c["name"]) for f, c in years[2024]["meta"]["counties"].items()}
    for year in (2022, 2020):
        if set(years[year]["meta"]["counties"]) != set(names):
            raise SystemExit(f"Arkansas {year}: the counties are not those of 2024")

    # counties add up to the statewide figures
    for c in CONTESTS:
        y = years[c["year"]]
        s = {}
        for fips in names:
            add(s, y["county"][fips][c["id"]])
        if s != y["statewide"][c["id"]]:
            raise SystemExit(f"Arkansas: {c['id']}: the counties do not add up to the statewide figures")
        control["contests"][c["id"]] = {"sum_of_counties": s, "official": y["statewide"][c["id"]], "counties": {"compared": 75, "equal": 75},
                                        "equal": True, "source": f"ar-results-{c['year']}",
                                        "where": "the results service's statewide figures for the contest, its row for each county, each county's own figures and its precinct rows",
                                        "precinct_rows": {"precincts": sum(1 for p in y["precincts"].values() if c["id"] in p["votes"]), "sum": s}}

    # the Clerk of the House, a second statewide control for President and U.S. Senator
    for year, (day, kind) in CLERK.items():
        path = os.path.join(cache, f"clerk_statistics{year}.pdf")
        url = f"https://clerk.house.gov/member_info/electionInfo/{year}/statistics{year}.pdf"
        net.download(url, path, 0 if refresh else KEEP_DAYS, tries=4, say=say)
        doc = read_clerk(path, "ARKANSAS")
        top = re.search(r"page (\d+)", doc["where"])
        where = f"Arkansas, page {top.group(1)}" if top else "the Arkansas page"
        for c in CONTESTS:
            if c["year"] != year or not c.get("clerk"):
                continue
            figs = clerk_check(doc, c["clerk"], c)
            mine = control["contests"][c["id"]]["sum_of_counties"]
            if figs != mine:
                raise SystemExit(f"Arkansas {year}: {c['id']}: the Clerk of the House's statistics {figs} differ from {mine}")
            control["contests"][c["id"]]["clerk"] = {"official": figs, "equal": True, "where": where}
        sources.append({"id": f"clerk-statistics-{year}", "kind": "official federal compilation", "agency": "Office of the Clerk, U.S. House of Representatives",
                        "title": f"Statistics of the {kind} Election from Official Sources for the Election of {day}", "url": url,
                        "fetched": _day(path), "sha256": _sha_file(path), "where": where,
                        "read": "The Arkansas lines for presidential electors and United States Senator; its under and over votes are left out."})
    control["contests"]["2022-governor"]["clerk"] = ("The Clerk's statistics carry federal offices only; the Governor's figures are checked "
                                                     "within the Secretary's results (precincts, counties and the statewide figures).")

    for year in (2024, 2022, 2020):
        y = years[year]
        m = y["meta"]
        sources.insert(len([s for s in sources if s["id"].startswith("ar-results")]),
                       {"id": f"ar-results-{year}", "kind": "official results by precinct, with the county and statewide figures", "agency": AGENCY,
                        "title": f"{m['name']} Election, official results (the Secretary of State's results site and its data service, election {m['election_id']})",
                        "url": f"{SITE}#election={m['election_id']}", "data_service": API, "listed_on": RESULTS_PAGE,
                        "fetched": _day(os.path.join(cache, m["election_id"], "election.json")), "results_last_updated": str(m.get("last_updated") or "")[:10],
                        "version": m.get("version"), "precincts": len(y["precincts"]),
                        "read": "Of each precinct row: the precinct's id and each candidate's id and count, for "
                                + ", ".join(c["office"] for c in CONTESTS if c["year"] == year)
                                + (" and every state House and Senate contest" if year in DISTRICT_YEARS else "") + "; nothing else."})

    # districts
    places = {"county": {}, "judicial": {}, "house": {}, "senate": {}}
    dctl = {}
    house_by_year, senate_by_year = {}, {}
    rch, bef_recs = reach(cache, refresh, say)
    sources.append({"id": "census-bef-2024", "kind": "the state's House and Senate plans as the Census Bureau holds them, block by block (used only to say which districts reach each county)",
                    "agency": "U.S. Census Bureau", "title": "2024 State Legislative Block Equivalency Files (the plans in force for the 2022 and 2024 elections)",
                    "url": BEF_PAGE, "files": bef_recs,
                    "read": "Of each Arkansas block: the county part of its id and its district; nothing else."})
    # possible districts of every precinct, each year; then the same precinct in the other year narrows them
    poss = {}
    for year in DISTRICT_YEARS:
        y = years[year]
        if sorted({n for k, n in y["dists"].values() if k == "house"}) != list(range(1, 101)):
            raise SystemExit(f"Arkansas {year}: the ballot did not carry all 100 House contests")
        if year == 2022 and sorted({n for k, n in y["dists"].values() if k == "senate"}) != list(range(1, 36)):
            raise SystemExit("Arkansas 2022: the ballot did not carry all 35 Senate contests")
        for key, p in y["precincts"].items():
            if not any(v["total"] for v in p["votes"].values()):
                continue                       # a precinct with no votes at all (it changes no sum; counted below)
            pres = y["present"].get(p["county"], {"house": set(), "senate": set()})
            for kind in ("house", "senate"):
                ps = could_be(p[kind], rch[kind][p["county"]], pres[kind])
                if not ps:
                    raise SystemExit(f"Arkansas {year}: {names[p['county']]} {p['name']}: no {kind} district can hold it")
                if not set(p[kind]) <= set(rch[kind][p["county"]]):
                    raise SystemExit(f"Arkansas {year}: {names[p['county']]} {p['name']}: voted in a {kind} district the Census file does not put in its county")
                poss[(year, kind, p["county"], p["id"], p["name"])] = (ps, set(p[kind]))
    for year in DISTRICT_YEARS:
        y = years[year]
        P = y["precincts"]
        other = 2022 if year == 2024 else 2024
        ids = [c["id"] for c in CONTESTS if c["year"] == year]
        on_ballot = sorted({n for k, n in y["dists"].values() if k == "senate"})
        notes = collections.defaultdict(list)
        assign = {"house": {}, "senate": {}}
        bad = {"house": set(), "senate": set()}
        empty = 0
        for key, p in P.items():
            if not any(v["total"] for v in p["votes"].values()):
                empty += 1                     # a precinct with no votes at all changes no sum
                continue
            where = {"county": names[p["county"]], "precinct": p["name"]}
            for kind in ("house", "senate"):
                ps, listed = poss[(year, kind, p["county"], p["id"], p["name"])]
                o = poss.get((other, kind, p["county"], p["id"], p["name"]))
                d, could = settle(ps, o[0] if o else None, listed, o[1] if o else ())
                if d is not None:
                    assign[kind][key] = d
                else:
                    bad[kind] |= could
                    notes[f"{kind}_unplaced"].append(dict(where, voted_in=sorted(listed), could_be=sorted(could)))
        house, senate = {}, {}
        for kind, into in (("house", house), ("senate", senate)):
            for key, d in assign[kind].items():
                if d in bad[kind]:
                    continue
                for cid in ids:
                    into.setdefault(d, {}).setdefault(cid, {})
                    add(into[d][cid], P[key]["votes"][cid])
        # a contest on the ballot that a county reached by the district did not print (one candidate, as a rule)
        not_printed = []
        for kind in ("house", "senate"):
            on = {n for k, n in y["dists"].values() if k == kind}
            for fips in sorted(names):
                miss = sorted(set(rch[kind][fips]) & (on - y["present"].get(fips, {}).get(kind, set())))
                if miss:
                    not_printed.append({"county": names[fips], "kind": kind, "districts": miss})
        house_of, senate_of, bad_h, bad_s = assign["house"], assign["senate"], bad["house"], bad["senate"]
        # the districts given and the precincts of those left out add up to the statewide figures
        for kind, sums, assign, bad in (("house", house, house_of, bad_h), ("senate", senate, senate_of, bad_s)):
            tot = {cid: {} for cid in ids}
            for vv in sums.values():
                for cid, v in vv.items():
                    add(tot[cid], v)
            for key, p in P.items():
                d = assign.get(key)
                if d is None or d in bad:
                    for cid in ids:
                        add(tot[cid], p["votes"][cid])
            if any(tot[cid] != y["statewide"][cid] for cid in ids):
                raise SystemExit(f"Arkansas {year}: the {kind} districts given and the precincts left out do not add up to the statewide figures")
        house_by_year[year], senate_by_year[year] = house, senate
        dctl[str(year)] = {"house_contests": 100, "senate_contests": len(on_ballot),
                           "senate_districts_on_the_ballot": on_ballot if year == 2024 else "all 35",
                           "house_districts_given": len(house), "house_districts_left_out": sorted(set(range(1, 101)) - set(house)),
                           "senate_districts_given": len(senate), "senate_districts_left_out": sorted(set(range(1, 36)) - set(senate)),
                           "precincts_with_no_votes": empty,
                           "contests_a_county_did_not_print": not_printed,
                           "precincts_not_placed_in_one_house_district": notes["house_unplaced"],
                           "precincts_not_placed_in_one_senate_district": notes["senate_unplaced"]}

    # judicial districts
    jd, jd_used, jmeta = judicial(cache, refresh, say)
    sources.append({"id": "ar-results-2026-primary", "kind": "official results of the March 3, 2026 preferential primary and nonpartisan election (used only to find each judicial district's counties)",
                    "agency": AGENCY, "title": f"{jmeta['name']}, official results (election {jmeta['election_id']})",
                    "url": f"{SITE}#election={jmeta['election_id']}", "data_service": API, "listed_on": RESULTS_PAGE,
                    "fetched": _day(os.path.join(cache, jmeta["election_id"], "election.json")), "version": jmeta.get("version"),
                    "read": "Of each circuit judge contest with no subdistrict and each prosecuting attorney contest: its name, the counties that "
                            "returned votes and how many of their precincts; nothing else."})

    # places
    for fips in sorted(names):
        votes = {}
        for c in CONTESTS:
            votes[c["id"]] = years[c["year"]]["county"][fips][c["id"]]
        places["county"][fips] = {"name": names[fips], "votes": votes}
    for label in sorted(jd, key=lambda s: (int(re.match(r"\d+", s).group()), s)):
        votes = {}
        for fips in jd[label]:
            for cid, v in places["county"][fips]["votes"].items():
                votes.setdefault(cid, {})
                add(votes[cid], v)
        places["judicial"][f"AR-JD{label}"] = {"name": f"Judicial District {label}", "counties": jd[label], "votes": {c["id"]: votes[c["id"]] for c in CONTESTS}}
    for kind, by_year, word in (("house", house_by_year, "House District"), ("senate", senate_by_year, "Senate District")):
        nums = sorted(set().union(*[set(v) for v in by_year.values()]))
        for n in nums:
            votes = {}
            for year in DISTRICT_YEARS:
                if n in by_year[year]:
                    votes.update(by_year[year][n])
            places[kind][str(n)] = {"name": f"{word} {n}", "votes": {c["id"]: votes[c["id"]] for c in CONTESTS if c["id"] in votes}}
    for kind in places:
        for pl in places[kind].values():
            f = few(pl["votes"])
            if f:
                pl["too_few"] = [c["id"] for c in CONTESTS if c["id"] in f]

    contest_out = []
    for c in CONTESTS:
        y = years[c["year"]]
        rec = {"id": c["id"], "date": c["date"], "office": c["office"], "table": f"ar-results-{c['year']}",
               "kinds": ["county", "judicial", "house", "senate"] if c["year"] in DISTRICT_YEARS else ["county", "judicial"]}
        for k in SIDE_KEYS:
            if c.get(k):
                rec[k] = {"party": c[k][0], "ticket": c[k][1], "column": f"the candidate printed as {c[k][2]}"}
        rec["other"] = {"what": "every other candidate and all write-ins, together"}
        rec["total"] = {"what": "the votes cast for candidates and write-ins"}
        rec["statewide"] = control["contests"][c["id"]]["sum_of_counties"]
        rec["official_source"] = rec["table"]
        contest_out.append(rec)

    ours = our_places(DB)
    kinds = {}
    for kind, what, key in KINDS:
        k = {"what": what, "key": key, "places": len(places[kind]),
             "contests": [c["id"] for c in CONTESTS if kind in ("county", "judicial") or c["year"] in DISTRICT_YEARS],
             "places_with_a_contest_too_few": sum(1 for p in places[kind].values() if p.get("too_few"))}
        if kind == "county":
            k["covers_the_state"] = True
        elif kind == "judicial":
            k["covers_the_state"] = False
            k["how"] = ("A judicial district is the counties whose every precinct voted in a contest for the whole district (a circuit judge's "
                        "division with no subdistrict, or the prosecuting attorney) on the March 3, 2026 ballot; a district with no such contest "
                        "that day is not given. Each year's figures are those counties' votes.")
            k["contests_read"] = jd_used
        else:
            total = 100 if kind == "house" else 35
            left = {y: dctl[str(y)][f"{kind}_districts_left_out"] for y in DISTRICT_YEARS}
            k["covers_the_state"] = {str(y): not left[y] for y in DISTRICT_YEARS}
            k["why_not_2020"] = WHY_NOT
            if any(left.values()):
                k["left_out"] = {str(y): left[y] for y in DISTRICT_YEARS if left[y]}
                k["note"] = (f"A {'House' if kind == 'house' else 'Senate'} district is given for a year only where every precinct of it voted in "
                             f"that district alone. Left out: " + "; ".join(f"{y}: {len(left[y])} of {total} ({', '.join(map(str, left[y]))})"
                                                                            for y in DISTRICT_YEARS if left[y]) + ".")
            k["rows"] = "A district's figures are its precincts' rows added up."
            k["how"] = ("A precinct is placed in a district where it voted in that district's contest and in no other, and no other district "
                        "that reaches its county (by the Census Bureau's block equivalency file) went without results there that year; the "
                        "same precinct in the other election on the same lines can narrow the choice. "
                        + ("Every Senate seat was on the 2022 ballot; 18 of the 35 were on the 2024 ballot." if kind == "senate" else
                           "All 100 seats are on the ballot every two years."))
        kinds[kind] = k
    coverage = {"not_given": NOT_GIVEN, "no_2024_senate": "Arkansas elected no United States senator in 2024.",
                "no_2020_2024_governor": "Arkansas elected its Governor in 2022, not in 2020 or 2024.",
                "no_democrat_2020_senate": "No Democrat was on Arkansas's 2020 ballot for U.S. Senator; Ricky Dale Harrington Jr. was the Libertarian nominee."}
    if ours is not None:
        cov = {}
        for kind in ("county", "judicial", "house", "senate"):
            want = sorted(ours.get(kind, set()), key=lambda x: (len(x), x))
            have = set(places[kind])
            cov[kind] = {"places": len(want), "with_votes": sum(1 for x in want if x in have), "without": [x for x in want if x not in have]}
        cities = sorted(ours.get("mcd", set()))
        cov["mcd"] = {"places": len(cities), "with_votes": 0, "without": cities, "why": "Cities are not given (see not_given)."}
        cov["not_given_kinds"] = {k: len(v) for k, v in ours.items() if k not in ("county", "judicial", "house", "senate", "mcd")}
        cov["read"] = f"sl_places and sl_races in ballot_local_2026.sqlite, opened read-only on {_now()}"
        coverage["our_places"] = cov

    control["kinds"] = {"county": "equal", "judicial": "each district's counties reached whole by its own March 3, 2026 contest",
                        "house": "for 2022 and 2024, the House districts given and the precincts of those left out add up to the statewide figures",
                        "senate": "for 2022 and 2024, the Senate districts given and the precincts of those left out add up to the statewide figures"}
    control["districts"] = dctl
    control["notes"] = [
        "Arkansas prints a title some candidates filed with their name (\"Senator John Boozman\", \"Senator Tom Cotton\"); the nominees are matched as printed.",
        "The results count write-in candidates with the others; they are in other and total.",
        "The results service's party table names the Democratic and Republican parties and otherwise carries a vendor's list from another "
        "state; only those two labels are read from it. Harrington's Libertarian label in 2020 is the Clerk of the House's.",
    ]
    out = {"what": WHAT, "note": NOTE, "state": "AR", "generated": _now(), "method_version": METHOD, "how_to_read": HOW_TO_READ,
           "vote_keys": ["dem", "rep", "lib", "other", "total"], "too_few": {"fewer_than": FEW, "why": TOO_FEW},
           "contests": contest_out, "kinds": kinds, "control": control, "coverage": coverage, "sources": sources,
           "places": places}
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path + ".part", "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    os.replace(out_path + ".part", out_path)
    say(f"   wrote {out_path}: {len(places['county'])} counties, {len(places['judicial'])} judicial districts, "
        + ", ".join(f"{y}: {dctl[str(y)]['house_districts_given']} of 100 House and {dctl[str(y)]['senate_districts_given']} of 35 Senate districts" for y in DISTRICT_YEARS)
        + "; control equal")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--cache", default=CACHE)
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        selftest()
        return
    run(a.out, a.cache, a.refresh)


if __name__ == "__main__":
    main()
