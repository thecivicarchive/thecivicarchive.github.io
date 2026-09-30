"""
Arkansas: the Secretary of State's own candidate list and official results. Arkansas has four House seats and the
Senate seat of class 2 (Tom Cotton) on the ballot in 2026; the districts are the 2022 lines.

  November ballot   the Secretary of State's "2026 Candidate Search" (candidates.arkansas.gov, linked as "2026
                    Candidate Search" from the Elections Division's For Candidates page). The page is a table filled
                    from its own data address (/wp-json/metl/v1/all, the DataTables request the page itself sends,
                    postID 2941), which gives five columns: a filer number, CanBallotName (the name as filed for the
                    ballot), Descript (the office: "U.S. Senate", "U.S. Congress District 03"), PartyAffiliation and
                    FilingDate. The whole list (every state and federal office, about two hundred rows) is read in
                    pages of 100, and only the U.S. Senate and U.S. Congress rows are kept: office, ballot name,
                    party and filing date, as JSON in ballot_cache/ar/. The filer number, which opens each candidate's
                    detail card on the page, is not kept, and the detail cards (addresses, telephones) are never
                    fetched. As read in September 2026 the list holds only candidates still in the running: the
                    primary's losers are gone (the loader checks this), and it lists no withdrawn, write-in or
                    independent candidates for Congress. It prints no ballot order, so the order here is the list's
                    own (by ballot name, as the page sorts it). Parties are printed in full (Republican, Democratic,
                    Libertarian) and kept as printed. Names are kept exactly as filed for the ballot, which in
                    Arkansas may begin with a title ("Congressman French Hill", "Senator Tom Cotton"; the official
                    results of 2022 and 2024 print the same titles); such rows carry a note.
  primary fields    the Secretary of State's official results of the March 3, 2026 preferential primary, from its
                    election night reporting site (arkansas.tally-enr.com, linked as "2026 Preferential Primary
                    Election" from the Election Results page; the page is read and the link followed). The site's own
                    data service (enr-results-api.totalresults.com, client "arkansas") gives the election list (name
                    and date), GetElectionInfo (the party table, and isOfficial), GetContestSearchList (each contest's
                    name and candidates) and GetContestResults for the Federal contests (each candidate's votes,
                    statewide and county by county). Contests are named "REP U.S. Senate", "DEM U.S. Congress District
                    04". Arkansas prints only contested primaries, so every contest is a field. Votes are stored only
                    when the site marks the election official (it does: version v3318 of July 2, 2026); pct is the
                    share of the party's primary vote in the race (the results carry no write-in line). A nominee needs
                    a majority; the one with a majority advanced, and must be the party's candidate on the November
                    list. Each field is checked: every precinct reporting, candidates adding up to the contest total,
                    and the county figures adding up to the statewide ones.
  runoff            the official results of the March 31, 2026 primary runoff ("2026 Primary Runoff Election"), read
                    the same way. It held no contest for Congress (its only statewide race was the Republican runoff
                    for Secretary of State); a federal runoff would be stored as its own election ("runoff-REP").

Both hosts answer scripts. The results site's data carries names, parties and votes only; the candidate list carries
no contact columns in the data the page loads, and only the kept columns are ever read from it.
"""

import datetime as dt
import hashlib
import html as H
import json
import os
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode

from ballot.common import fold, house_id, name_parts, party_code, record_source, senate_id
from states import net

SEARCH_PAGE = "https://candidates.arkansas.gov/"
SEARCH_API = "https://candidates.arkansas.gov/wp-json/metl/v1/all"
POST_ID = "2941"
COLUMNS = ("FilerID", "CanBallotName", "Descript", "PartyAffiliation", "FilingDate")      # the page's own columns, asked for as the page asks
KEEP = ("CanBallotName", "Descript", "PartyAffiliation", "FilingDate")
RESULTS_PAGE = "https://www.sos.arkansas.gov/elections/research/election-results"
ENR_SITE = "https://arkansas.tally-enr.com/"
ENR_API = "https://enr-results-api.totalresults.com/"
CLIENT = "arkansas"
# kind -> (the Election Results page's label, the election's id as last seen there, its name on the results site, date)
ELECTIONS = {"primary": ("2026 Preferential Primary Election", "7f77a178-af02-40ec-92db-c5cc50882c68", "2026 Preferential Primary", "2026-03-03"),
             "runoff": ("2026 Primary Runoff Election", "b412bdef-f97a-45bc-b3ec-6761d28caf9e", "2026 Primary Runoff", "2026-03-31")}
CODE = {"Republican": "REP", "Democratic": "DEM", "Libertarian": "LIB", "Green": "GRE", "Constitution": "CON"}
PREFIX = {"REP": "Republican", "DEM": "Democratic", "LIB": "Libertarian", "GRN": "Green", "GRE": "Green"}
TITLE = re.compile(r"^(?:U\.S\. Representative|U\.S\. Senator|State Representative|State Senator|Congressman|Congresswoman|"
                   r"Senator|Representative|Attorney General|Lieutenant Governor|Governor|Secretary of State|Mayor|Sheriff|"
                   r"Judge|Prosecuting Attorney|Dr\.)\s+(?=\S+\s+\S)")
TITLE_NOTE = ("Arkansas lets a candidate file a title as part of the name printed on the ballot; the name is shown as the "
              "Secretary of State's list gives it.")
RUNOFF_NOTE = "No candidate had a majority; the top two went to the March 31 runoff."


def untitled(name):
    """The name without a title filed before it, for matching only: 'Congressman French Hill' -> 'French Hill'."""
    return TITLE.sub("", name.strip())


def race_of(office):
    """'U.S. Senate' -> 2026-AR-S2; 'U.S. Congress District 03' -> 2026-AR-H03; any other office -> None. An office that
    looks federal but is not one of these stops the loader."""
    t = re.sub(r"\s+", " ", office or "").strip()
    if re.fullmatch(r"U\.\s?S\. Senate|United States Senat(?:e|or)", t, re.I):
        return senate_id("AR", 2)
    m = re.fullmatch(r"(?:U\.\s?S\.|United States) (?:Congress|Representative)(?:ional)?,? (?:District|Dist\.?|Dst) ?(\d+)", t, re.I)
    if m:
        return house_id("AR", int(m.group(1)))
    if re.search(r"\bU\.\s?S\.|United States|Congress", t, re.I):
        raise SystemExit(f"Arkansas: an office that looks federal could not be read: {t!r}")
    return None


def fresh(path, days):
    return os.path.exists(path) and time.time() - os.path.getmtime(path) < days * 86400


def search_page(start):
    q = {"draw": 1, "start": start, "length": 100, "search[value]": "", "search[regex]": "false",
         "order[0][column]": 1, "order[0][dir]": "asc", "postID": POST_ID}
    for i, c in enumerate(COLUMNS):
        q.update({f"columns[{i}][data]": c, f"columns[{i}][name]": "", f"columns[{i}][searchable]": "true",
                  f"columns[{i}][orderable]": "true", f"columns[{i}][search][value]": "", f"columns[{i}][search][regex]": "false"})
    return json.loads(net.get(SEARCH_API + "?" + urlencode(q), accept="application/json").decode("utf-8-sig"))


def candidate_list(folder, say):
    """The federal rows of the Candidate Search (kept columns only), as JSON in the cache, read afresh after two days."""
    path = os.path.join(folder, "ar_2026_candidate_search_federal.json")
    if fresh(path, 2):
        return path
    try:
        rows, start, total = [], 0, None
        while total is None or start < total:
            page = search_page(start)
            total = int(page["recordsFiltered"])
            data = page.get("data") or []
            if not data:
                break
            for r in data:
                if race_of(r.get("Descript")):
                    rows.append({k: re.sub(r"\s+", " ", str(r.get(k) or "")).strip() for k in KEEP})
            start += len(data)
            time.sleep(1.5)
    except (HTTPError, URLError, OSError, ValueError) as e:
        if os.path.exists(path):
            say(f"      could not read the Candidate Search afresh ({e}); using the copy read earlier")
            return path
        raise SystemExit(f"Arkansas: the Candidate Search could not be read ({e})")
    if start < (total or 0):
        raise SystemExit(f"Arkansas: the Candidate Search gave {start} of {total} rows")
    raw = json.dumps(rows, ensure_ascii=False, sort_keys=True).encode("utf-8")
    meta = {"url": SEARCH_PAGE, "data": SEARCH_API, "post_id": POST_ID, "records": total, "read": dt.date.today().isoformat(),
            "sha256_rows": hashlib.sha256(raw).hexdigest(), "rows": rows}
    json.dump(meta, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return path


def election_ids(say):
    """{kind: id}, from the links on the Secretary of State's Election Results page (the ids last seen there if the page
    cannot be read or no longer links a label)."""
    ids = {k: v[1] for k, v in ELECTIONS.items()}
    try:
        page = net.get(RESULTS_PAGE, accept="text/html").decode("utf-8", "replace")
    except (HTTPError, URLError, OSError) as e:
        say(f"      the Election Results page could not be read ({e}); using the election ids last seen there")
        return ids
    for m in re.finditer(r'<a[^>]+href="([^"]*tally-enr\.com/#election=([0-9a-f-]+))"[^>]*>(.*?)</a>', page, re.S | re.I):
        label = re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", "", m.group(3)))).strip()
        for kind, (want, *_rest) in ELECTIONS.items():
            if label == want:
                ids[kind] = m.group(2)
    return ids


def enr(path):
    return json.loads(net.get(ENR_API + path, accept="application/json").decode("utf-8-sig"))


def contest_parts(name):
    """'REP U.S. Congress District 02' or 'U.S. Congress District 02 - REP' -> (party prefix, race id); else (None, None)."""
    t = re.sub(r"\s+", " ", name).strip()
    m = re.fullmatch(r"([A-Z]{3}) (.+)", t)
    if m:
        prefix, office = m.group(1), m.group(2)
    else:
        m = re.fullmatch(r"(.+?) - ([A-Z]{3})", t)
        if not m:
            return None, None
        office, prefix = m.group(1), m.group(2)
    try:
        race = race_of(office)
    except SystemExit:
        race = None
    return prefix, race


def results(folder, kind, eid, say):
    """One election's federal contests (kept fields only) as JSON in the cache, read afresh after 30 days. The results
    site keeps every election, but if it cannot be reached the copy on disk is used."""
    label, _eid, name, date = ELECTIONS[kind]
    path = os.path.join(folder, f"ar_2026_{kind}_results_federal.json")
    if fresh(path, 30):
        return path
    try:
        listed = [e for e in enr(f"Election/GetElectionList?cid={CLIENT}") if e.get("electionID") == eid]
        if len(listed) != 1 or listed[0].get("electionName") != name or not str(listed[0].get("electionDate", "")).startswith(date):
            raise SystemExit(f"Arkansas: the results site does not list {eid} as the {name} of {date} ({listed})")
        time.sleep(1.0)
        search = enr(f"Contest/GetContestSearchList?cid={CLIENT}&electionID={eid}")
        federal = {cid: c for cid, c in search["response"]["contests"].items()
                   if c.get("contestTypeCode") == "Federal" or contest_parts(c.get("contestName", ""))[1]}
        contests, official, updated, version = [], bool(search.get("isOfficial")), search.get("lastUpdated"), search.get("versionID")
        if federal:
            time.sleep(1.0)
            info = enr(f"Election/GetElectionInfo?cId={CLIENT}&electionID={eid}")
            parties = {k: v["partyName"] for k, v in info["response"]["parties"].items()}
            official = official and bool(info.get("isOfficial"))
            time.sleep(1.0)
            res = enr(f"Contest/GetContestResults?cId={CLIENT}&electionID={eid}&contestType=Federal")
            got = res["response"]["contests"]
            if set(got) != set(federal):
                raise SystemExit(f"Arkansas: the {name} results and contest list name different federal contests")
            official = official and bool(res.get("isOfficial"))
            updated, version = res.get("lastUpdated"), res.get("versionID")
            for cid, c in sorted(federal.items(), key=lambda kv: kv[1].get("contestOrder", 0)):
                r = got[cid]
                choices = []
                for ch in (r.get("choices") or []) + (r.get("writeInChoices") or []):
                    who = c["choices"][ch["choiceID"]]
                    county = sum(next((x["totalVotes"] for x in loc.get("choices") or [] if x["choiceID"] == ch["choiceID"]), 0)
                                 for loc in (r.get("locations") or {}).values())
                    choices.append({"name": who["name"], "party": parties.get(ch.get("partyID") or who.get("partyID"), ""),
                                    "write_in": bool(who.get("isWriteIn")), "votes": int(ch["totalVotes"]), "county_sum": county})
                contests.append({"name": c["contestName"], "vote_for": c.get("voteFor"), "total": int(r["totalVotes"]),
                                 "precincts": [r.get("precinctsReporting"), r.get("totalPrecincts")],
                                 "counties": len(r.get("locations") or {}), "choices": choices})
    except (HTTPError, URLError, OSError, ValueError, KeyError) as e:
        if os.path.exists(path):
            say(f"      could not read the {name} results afresh ({e}); using the copy read earlier")
            return path
        raise SystemExit(f"Arkansas: the {name} results could not be read ({e})")
    keep = {"election": name, "date": date, "election_id": eid, "link": f"{ENR_SITE}#election={eid}", "official": official,
            "last_updated": updated, "version": version, "read": dt.date.today().isoformat(), "contests": contests}
    json.dump(keep, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return path


def same_person(a, b):
    """Two printings of one name: the same once any filed title is set aside, or the same family name and first name."""
    a, b = untitled(a), untitled(b)
    if fold(a) == fold(b):
        return True
    (ga, fa), (gb, fb) = name_parts(a), name_parts(b)
    return bool(fa and fa == fb and ga and gb and ga[0] == gb[0])


def fields_from(data, kind, nominees, problems):
    """Rows for one election's federal fields, and how many fields there were."""
    rows, n = [], 0
    election_date = ELECTIONS[kind][3]
    for c in data["contests"]:
        prefix, race = contest_parts(c["name"])
        if not race:
            raise SystemExit(f"Arkansas: the federal contest {c['name']!r} could not be read")
        parties = {ch["party"] for ch in c["choices"] if not ch["write_in"]}
        if len(parties) != 1 or PREFIX.get(prefix) not in parties:
            raise SystemExit(f"Arkansas: {c['name']} lists candidates of {sorted(parties)}")
        party = parties.pop()
        named = [ch for ch in c["choices"] if not ch["write_in"]]
        total = sum(ch["votes"] for ch in c["choices"])
        if total != c["total"]:
            problems.append(f"{c['name']}: candidates add up to {total:,}, the contest total is {c['total']:,}")
        if c["precincts"][0] != c["precincts"][1]:
            problems.append(f"{c['name']}: {c['precincts'][0]} of {c['precincts'][1]} precincts reporting")
        for ch in c["choices"]:
            if ch["county_sum"] != ch["votes"]:
                problems.append(f"{c['name']}: {ch['name']}'s counties add up to {ch['county_sum']:,}, the statewide figure is {ch['votes']:,}")
        if len(named) < 2:
            continue
        n += 1
        code = CODE.get(party, party[:3].upper())
        stage = "primary" if kind == "primary" else "runoff"
        nominee = nominees.get((race, party))
        ranked = sorted(named, key=lambda ch: -ch["votes"])
        if not data["official"]:
            won = [ch for ch in named if nominee and same_person(ch["name"], nominee)]
            runoff = False
        elif kind == "primary" and 2 * ranked[0]["votes"] <= total:
            won, runoff = ranked[:2], True
        else:
            won, runoff = ranked[:1], False
        if not runoff and nominee and not any(same_person(w["name"], nominee) for w in won):
            problems.append(f"{c['name']}: the results' winner ({', '.join(w['name'] for w in won) or 'none'}) is not the party's "
                            f"candidate on the November list ({nominee})")
        for ch in named:
            if nominee and ch not in won and same_person(ch["name"], nominee) and not runoff:
                problems.append(f"{c['name']}: {ch['name']} lost the primary but is on the November list")
            advanced = ch in won
            note = None
            if advanced and runoff:
                note = RUNOFF_NOTE
            elif advanced and not nominee:
                note = f"Won the {party} nomination but is not on the Secretary of State's November list."
            rows.append((race, f"{stage}-{code}", election_date, ch["name"], party, party_code(party), None, 0, 0,
                         ch["votes"] if data["official"] else None,
                         round(100 * ch["votes"] / total, 1) if data["official"] and total else None,
                         "advanced" if advanced else "lost", None, None, f"ar-sos-2026-{kind}-results", note))
    return rows, n


def load(con, cache, say=print):
    net.patient_lookups()
    folder = os.path.join(cache, "ar")
    os.makedirs(folder, exist_ok=True)
    gpath = candidate_list(folder, say)
    glist = json.load(open(gpath, encoding="utf-8"))

    rows, order, nominees, twice = [], {}, {}, []
    for r in glist["rows"]:
        race = race_of(r["Descript"])
        party, name = r["PartyAffiliation"], r["CanBallotName"]
        if not name or not party:
            raise SystemExit(f"Arkansas: a candidate for {race} with no name or no party on the Candidate Search")
        if (race, party) in nominees and party != "Independent":
            twice.append(f"{race} {party}")
        nominees[(race, party)] = name
        order[race] = order.get(race, 0) + 1
        rows.append((race, "general", "2026-11-03", name, party, party_code(party), order[race], 0, 0, None, None, None, None, None,
                     "ar-sos-2026-candidate-search", TITLE_NOTE if TITLE.match(name) else None))
    if twice:
        raise SystemExit(f"Arkansas: more than one candidate of one party for one seat: {', '.join(twice)}")
    races = {r[0] for r in rows}
    want = {senate_id("AR", 2)} | {house_id("AR", d) for d in range(1, 5)}
    if races != want:
        raise SystemExit(f"Arkansas: the Candidate Search names candidates for {sorted(races)}; {sorted(want)} were expected")

    ids = election_ids(say)
    problems, nfields, data = [], {}, {}
    for kind in ("primary", "runoff"):
        data[kind] = json.load(open(results(folder, kind, ids[kind], say), encoding="utf-8"))
        got, nfields[kind] = fields_from(data[kind], kind, nominees, problems)
        rows += got
    pdata, rdata = data["primary"], data["runoff"]

    with con:
        con.execute("DELETE FROM candidates WHERE race_id LIKE '2026-AR-%'")
        con.executemany("INSERT OR REPLACE INTO candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        record_source(con, "ar-sos-2026-candidate-search", path=gpath, level="federal", state="AR", kind="official candidate list",
                      agency="Arkansas Secretary of State, Elections Division",
                      title="2026 Candidate Search: U.S. Senate and U.S. Congress", url=SEARCH_PAGE, rows=len(glist["rows"]),
                      note=f"Read {glist['read']} from the page's own data address ({SEARCH_API}, postID {POST_ID}): {glist['records']} rows "
                           "for every state and federal office; the U.S. Senate and U.S. Congress rows kept (office, ballot name, party, filing "
                           "date). The list holds only candidates still in the running and prints no ballot order, so the order is the list's "
                           "own (by ballot name). It lists no withdrawn, write-in or independent candidates for Congress, so none were left off. "
                           "Names as filed for the ballot, titles included.")
        record_source(con, "ar-sos-2026-primary-results", path=os.path.join(folder, "ar_2026_primary_results_federal.json"), level="federal",
                      state="AR", kind="official results", agency="Arkansas Secretary of State, Elections Division",
                      title="Election Results: 2026 Preferential Primary, March 3, 2026 (federal contests"
                            + (", official)" if pdata["official"] else ", not yet official)"),
                      url=pdata["link"], published=(pdata["last_updated"] or "")[:10],
                      rows=sum(len(c["choices"]) for c in pdata["contests"]),
                      note=f"From the results site's data service ({ENR_API}, client {CLIENT}, election {pdata['election_id']}), "
                           f"version {pdata['version']}, marked {'official' if pdata['official'] else 'NOT official: votes not stored'}. "
                           "Every contested party primary for Congress; the results carry no write-in line, so each field's total is its "
                           "candidates' votes. Checked: all precincts reporting, candidates adding up to each contest's total, county "
                           "figures adding up to the statewide ones" + ("." if not problems else "; differences: " + "; ".join(problems)))
        record_source(con, "ar-sos-2026-runoff-results", path=os.path.join(folder, "ar_2026_runoff_results_federal.json"), level="federal",
                      state="AR", kind="official results", agency="Arkansas Secretary of State, Elections Division",
                      title="Election Results: 2026 Primary Runoff, March 31, 2026 (federal contests)", url=rdata["link"],
                      published=(rdata["last_updated"] or "")[:10], rows=sum(len(c["choices"]) for c in rdata["contests"]),
                      note=("No contest for Congress was on the runoff ballot." if not rdata["contests"] else
                            f"{nfields['runoff']} runoff fields for Congress, marked {'official' if rdata['official'] else 'not official'}."))
    n = sum(1 for r in rows if r[1] == "general")
    say(f"    Arkansas: 4 House districts and the Senate race, {n} candidates on the November ballot (none withdrawn listed); "
        f"{nfields['primary']} party primaries with a field, votes from the {'official' if pdata['official'] else 'UNOFFICIAL (not stored)'} "
        f"March 3 results; {'no federal runoff on March 31' if not rdata['contests'] else str(nfields['runoff']) + ' federal runoffs on March 31'}")
    if problems:
        say("      the results did not all reconcile: " + "; ".join(problems))
    return n
