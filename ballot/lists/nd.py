"""
North Dakota: the Secretary of State's 2026 General Election Contest/Candidate List (vip.sos.nd.gov, election 348), a
search page: the loader asks it, as the page's own Search button does, for the contest "Representative in Congress"
(North Dakota has no Senate race in 2026) and reads the table it returns. Columns are taken by name, only Contest, Name
and Party; the table also carries mailing addresses, phones, e-mail and websites, which are never read. Parties are
printed as the list prints them ("Republican", "Democratic-NPL", "independent nomination"); none is abbreviated.

The June 9 primary comes from two more of the Secretary's pages. Who was on each party's primary ballot: the 2026 Primary
Election Contest/Candidate List (the same search page, election 346), read the same way and with the same three columns.
The votes: the Secretary's Election Night Reporting site, resultsnd.sos.nd.gov, which the Election Results page links as
"Primary Election Results - June 9, 2026 | Official results" (the older results.sos.nd.gov still shows the 2024 general
election). It is a script-drawn page; the loader asks the service behind it (api.resultsnd.sos.nd.gov) for the same
answers the page asks for: the election's details (name, date, and whether the results are official), the contest list
(each party's primary is a contest, "Representative in Congress Republican", whose choices are the candidates and a
"write-in" line) and each contest's statewide totals. Only those totals are kept; the county and precinct figures are not
stored. Write-in votes count toward a primary's total but are not a candidate. A party primary becomes a field only with
two candidates or more on its ballot (in 2026 the Republican one; Trygve Hammer was alone on the Democratic-NPL ballot).
The results service leaves every choice's "winner" mark unset, so the candidate on the November list for that party is
the one who advanced, and the loader checks that that candidate also had the most votes. Primary names are the
candidate list's; the results service's spelling of each name must match it.
"""

import html as H
import json
import os
import re
import time
import urllib.parse
from urllib.request import Request, urlopen

from ballot.common import fold, house_id, party_code, record_source
from states import net

URL = "https://vip.sos.nd.gov/candidatelist.aspx?eid=348"
PRIMARY_URL = "https://vip.sos.nd.gov/candidatelist.aspx?eid=346"
PRIMARY = "2026-06-09"
RESULTS_PAGE = "https://resultsnd.sos.nd.gov/#bucket=results&filter=SW&contest=20042REP"
API = "https://api.resultsnd.sos.nd.gov"
CLIENT, ELECTION = "north-dakota", "346"
FORM = "ctl00$ContentPlaceHolder1$"
KEEP = ("Contest", "Name", "Party")
OFFICE = "Representative in Congress"
CODES = {"Republican": "REP", "Democratic-NPL": "DEM", "Libertarian": "LIB"}      # primary-REP, primary-DEM, ...


def search(contest_label, url=URL, election="2026 General Election"):
    page = net.get(url).decode("utf-8", "replace")
    if election not in page:
        raise SystemExit(f"North Dakota: the candidate list page is no longer the {election}")
    fields = {m.group(1): H.unescape(m.group(2)) for m in re.finditer(r'<input type="hidden" name="([^"]+)" id="[^"]*" value="([^"]*)"', page)}
    contest = re.search(r'<option[^>]*value="(\d+)"[^>]*>\s*%s\s*</option>' % re.escape(contest_label), page)
    if not contest:
        raise SystemExit(f"North Dakota: the contest \"{contest_label}\" is not offered on the page")
    fields.update({FORM + "ddlJursdiction": "AL", FORM + "ddlDistrict": "0", FORM + "ddlContest": contest.group(1),
                   FORM + "ddlCandidate": "0", FORM + "btnSearch": "Search"})
    req = Request(url, data=urllib.parse.urlencode(fields).encode(), method="POST",
                  headers={"User-Agent": net.UA, "Content-Type": "application/x-www-form-urlencoded", "Referer": url})
    with urlopen(req, timeout=120) as r:
        return r.read().decode("utf-8", "replace")


def table_rows(page):
    for tab in re.findall(r"<table[^>]*>(.*?)</table>", page, re.S):
        heads = [H.unescape(re.sub(r"<[^>]+>", "", h)).strip() for h in re.findall(r"<th[^>]*>(.*?)</th>", tab, re.S)]
        if not all(k in heads for k in KEEP):
            continue
        idx = {k: max(i for i, h in enumerate(heads) if h == k) for k in KEEP}      # "Contest" is printed twice; the second is the office
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", tab, re.S):
            cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
            if len(cells) == len(heads):
                yield {k: re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", "", cells[i]))).strip() for k, i in idx.items()}


def primary_list(cache):
    """Every candidate on a party's June 9 primary ballot for the House seat (Contest, Name, Party), kept on disk: the
    primary is over, so the list is asked for once."""
    path = os.path.join(cache, "nd", "nd_2026_primary_congress.json")      # only the three columns kept
    if not os.path.exists(path):
        listed = [r for r in table_rows(search(OFFICE, PRIMARY_URL, "2026 Primary Election")) if r["Contest"] == OFFICE and r["Name"]]
        if not listed:
            raise SystemExit("North Dakota: the primary search returned no candidates for Representative in Congress")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        json.dump(listed, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return path, json.load(open(path, encoding="utf-8"))


def ask(what, **params):
    time.sleep(1.0)
    return json.loads(net.get(f"{API}/{what}?" + urllib.parse.urlencode(params), accept="application/json"))


def primary_results(cache, say=print):
    """The official statewide totals of each party's congressional primary, from the Election Night Reporting service.
    Kept on disk once the service calls them official; asked again while they are not. Returns (path, results) or
    (None, None) when the service cannot be reached and nothing is on disk."""
    path = os.path.join(cache, "nd", "nd_2026_primary_results_congress.json")      # statewide totals only
    if os.path.exists(path):
        kept = json.load(open(path, encoding="utf-8"))
        if kept.get("official"):
            return path, kept
    try:
        info = ask("Election/GetElectionInfo", cId=CLIENT, electionID=ELECTION)
        e = info["response"]
        if e["name"] != "2026 Primary Election" or not str(e["date"]).startswith(PRIMARY):
            raise SystemExit(f"North Dakota: results election {ELECTION} is {e['name']} of {e['date']}, not the June 9, 2026 primary")
        contests = ask("Contest/GetContestSearchList", cid=CLIENT, electionID=ELECTION)["response"]["contests"]
        kept = {"election": e["name"], "date": e["date"][:10], "official": bool(info.get("isOfficial")),
                "last_updated": info.get("lastUpdated"), "contests": {}}
        for cid, c in contests.items():
            if not c["contestName"].startswith(OFFICE + " "):
                continue
            res = ask("Contest/GetSingleContestResults", cId=CLIENT, electionID=ELECTION, contestType=c["contestTypeCode"], contestID=cid)["response"]
            names = {k: re.sub(r"\s+", " ", ch["name"]).strip() for k, ch in c["choices"].items()}
            choices = [{"id": ch["choiceID"], "name": names[ch["choiceID"]], "party": ch.get("partyID"), "votes": int(ch["totalVotes"]),
                        "write_in": bool(c["choices"][ch["choiceID"]].get("isWriteIn")) or fold(names[ch["choiceID"]]) == "write in"}
                       for ch in res["choices"]]
            extra = sum(int(w.get("totalVotes") or 0) for w in (res.get("writeinChoices") or []))
            if sum(ch["votes"] for ch in choices) + extra != int(res["totalVotes"]):
                raise SystemExit(f"North Dakota: the choices of {c['contestName']} do not add up to its total ({res['totalVotes']})")
            kept["contests"][cid] = {"contest": c["contestName"], "party": c["contestName"][len(OFFICE) + 1:], "total": int(res["totalVotes"]),
                                     "write_in_listed": extra, "precincts": f"{res['precinctsReporting']} of {res['totalPrecincts']}",
                                     "choices": choices}
    except SystemExit:
        raise
    except Exception as err:  # noqa: BLE001  the service unreachable or changed: say so and fall back to what is on disk
        if os.path.exists(path):
            say(f"      North Dakota: the results service did not answer ({err}); using the copy on disk")
            return path, json.load(open(path, encoding="utf-8"))
        say(f"      North Dakota: the results service did not answer ({err}); the primary field is stored without votes")
        return None, None
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(kept, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return path, kept


def load(con, cache, say=print):
    net.patient_lookups()
    listed = [r for r in table_rows(search(OFFICE)) if r["Contest"] == OFFICE and r["Name"]]
    if not listed:
        raise SystemExit("North Dakota: the search returned no candidates for Representative in Congress")
    path = os.path.join(cache, "nd", "nd_2026_general_congress.json")      # only the three columns kept
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(listed, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    race = house_id("ND", 0)
    rows = [(race, "general", "2026-11-03", r["Name"], r["Party"], party_code(r["Party"]), i, 0, 0, None, None, None, None, None, "nd-sos-2026-candidate-list", None)
            for i, r in enumerate(listed, start=1)]

    ppath, plist = primary_list(cache)
    nominee = {r["Party"]: fold(r["Name"]) for r in listed}
    ballots = {}
    for r in plist:
        ballots.setdefault(r["Party"], []).append(r["Name"])
    fields = {party: names for party, names in ballots.items() if len(names) >= 2}
    rpath, results = primary_results(cache, say) if fields else (None, None)
    official = bool(results and results.get("official"))
    for party, names in fields.items():
        code = CODES.get(party, party[:3].upper())
        contest = next((c for c in (results or {}).get("contests", {}).values() if c["party"] == party), None) if official else None
        votes = {}
        if official and not contest:
            raise SystemExit(f"North Dakota: the official results carry no contest \"{OFFICE} {party}\"")
        if contest:
            people = [ch for ch in contest["choices"] if not ch["write_in"]]
            if sorted(fold(ch["name"]) for ch in people) != sorted(fold(n) for n in names):
                raise SystemExit(f"North Dakota: the {party} primary's results name {[ch['name'] for ch in people]}, the candidate list {names}")
            votes = {fold(ch["name"]): ch["votes"] for ch in people}
            top = max(votes, key=votes.get)
            if nominee.get(party) and nominee[party] != top:
                raise SystemExit(f"North Dakota: the {party} candidate on the November list did not have the most votes in the primary")
        for name in names:
            v = votes.get(fold(name)) if contest else None
            rows.append((race, f"primary-{code}", PRIMARY, name, party, party_code(party), None, 0, 0, v,
                         round(100 * v / contest["total"], 1) if contest and contest["total"] else None,
                         "advanced" if nominee.get(party) == fold(name) else "lost", None, None,
                         "nd-sos-2026-primary-list", None))

    with con:
        con.execute("DELETE FROM candidates WHERE race_id LIKE '2026-ND-%'")
        con.executemany("INSERT OR REPLACE INTO candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        record_source(con, "nd-sos-2026-candidate-list", path=path, level="federal", state="ND", kind="official candidate list",
                      agency="North Dakota Secretary of State", title="2026 General Election Contest/Candidate List: Representative in Congress",
                      url=URL, rows=len(listed), note="Read through the page's own search; Contest, Name and Party only, contact columns never read.")
        record_source(con, "nd-sos-2026-primary-list", path=ppath, level="federal", state="ND", kind="official candidate list",
                      agency="North Dakota Secretary of State", title="2026 Primary Election Contest/Candidate List: Representative in Congress (June 9, 2026)",
                      url=PRIMARY_URL, rows=len(plist),
                      note="Read through the page's own search; Contest, Name and Party only, contact columns never read. "
                           f"Party primaries with two candidates or more: {len(fields)} ({', '.join(fields) or 'none'}); "
                           "who advanced is read from the November list"
                           + ("." if official else "; official vote counts could not be read, so the fields carry no votes."))
        if official:
            record_source(con, "nd-sos-2026-primary-results", path=rpath, level="federal", state="ND", kind="official results",
                          agency="North Dakota Secretary of State", title="2026 Primary Election (June 9, 2026), official results: Representative in Congress",
                          url=RESULTS_PAGE, published=(results.get("last_updated") or "")[:10],
                          rows=sum(len(c["choices"]) for c in results["contests"].values()),
                          note="Election Night Reporting, marked official by the Secretary; statewide totals read from the service behind the page "
                               f"({API}: Election/GetElectionInfo, Contest/GetContestSearchList, Contest/GetSingleContestResults, election {ELECTION}). "
                               "Write-in votes count in each primary's total but are not listed. The date given is the results' last update.")
        else:
            con.execute("DELETE FROM ballot_sources WHERE source_id = 'nd-sos-2026-primary-results'")
    n = len(listed)
    say(f"    North Dakota: the at-large House seat, {n} candidates on the November ballot (no Senate race in 2026); "
        f"{len(fields)} party primary with a field" + (", votes from the official results" if official else ", no votes read"))
    return n
