"""
New Mexico: the Secretary of State's own candidate lists and its official, certified results of the June 2, 2026
primary. New Mexico has three House seats (the 2024 lines) and the class 2 Senate seat.

  November ballot   the "2026 General Election Contest/Candidate List" of the Secretary's candidate portal
                    (candidateportal.servis.sos.state.nm.us/CandidateList.aspx, election 2917; the portal's page with
                    no election number shows the same list). It is a Telerik grid of every office in the state, all on
                    one page (the loader stops if a pager ever appears). Columns are taken by name, only Contest,
                    District, Name, Party, Ballot Order and Status; the grid also carries physical and mailing
                    addresses, phones, e-mail and websites, which are never read, and the cached copy
                    (ballot_cache/nm/) keeps only the columns taken, for the federal rows. "Contest" is printed twice:
                    the second (hidden) one is the office alone, and that is the one read. A row with the status
                    Qualified is on the ballot; Disqualified and Withdrawn are left off and counted; any other status
                    stops the loader. The list's own Ballot Order is kept. A name ending "(write-in)" is a declared
                    write-in (write_in 1, no ballot position, the mark dropped); there is none for Congress in 2026.
                    Parties are written out from the list's own key, read from the page's party menu (DEM DEMOCRATIC,
                    REP REPUBLICAN, LIB LIBERTARIAN, FWD FORWARD, DTS NO PARTY/DECLINED TO SELECT), in ordinary
                    capitals. Names are printed first name first, in capitals; the page shows them in ordinary
                    capitals (a sitting member as the congress-legislators roster spells them where the letters are
                    the same) and says so.
  primary list      the portal's "2026 Primary Election Contest/Candidate List" (election 2911), read the same way:
                    who was on each party's June ballot. Disqualified and Withdrawn rows were not on it and are
                    counted in the source note (in 2026 the Senate's Christopher J Vanden Heuvel, Republican; District
                    1's Carlton R Pennington and Steve Jones, Republicans; District 2's Thomas John Wakely, Democrat).
  primary votes     the Secretary's results site, electionresults.sos.nm.gov, election 2911, headed "Official Results
                    2026 Primary June 2, 2026" and last updated 6/23/2026, the day the State Canvass Board certified the
                    primary (the Secretary's release of June 23, 2026 says "the official, certified results ... are
                    available to be viewed on the Secretary of State's website" and links this site; the Secretary's
                    2026 Election Results page lists it as "2026 Primary Election Official Results"). The loader
                    checks the page still says Official Results and never Unofficial, then reads the site's own export
                    for Federal contests (resultsCSV.aspx, type FED: RaceID, RaceName, PartyCode, AreaNum, CandidateName,
                    CandidateVotes, CandidatePercentage, PrecinctsReporting, and the absentee, election day and early
                    votes). Checks: every precinct reported; each candidate's absentee, election day and early votes
                    add up to the total; the site's percentages are the votes' shares of the candidates' total; the
                    names under each party's contest are exactly that party's Qualified rows on the primary list; and,
                    for every field, the county-by-county figures the results page itself draws on (its own service,
                    nmresultswebservice.azurewebsites.us, GetMapDataArchive) add up to each candidate's statewide total.
                    New Mexico counts write-in votes only for declared write-in candidates, and the export lists them
                    among the candidates (their names marked "(write in)"), so a field's total is its candidates'
                    votes, write-ins included. None of the State Canvass Board's recounts ordered on June 23 was for
                    Congress.

A field is a party primary with two or more names printed on that party's ballot (a declared write-in alone beside one
printed name would not make one). The candidate of that party on the November list advanced, and must be the field's
top vote-getter. In 2026 the fields are the Democratic primary for the Senate (Ben R Lujan, Matt Dodson) and the
Republican primary in District 2 (Gregory G Cunningham, Jose Orozco). No Republican name was printed for the Senate:
Larry E Marker, a declared write-in, was nominated with 31,220 votes, and his November row says so. The only
Libertarian primary was for a state office. Both hosts answer scripts.
"""

import csv
import html as H
import io
import json
import os
import re
import sqlite3
import time

from ballot.common import HERE, fold, house_id, party_code, record_source, senate_id
from ballot.lists.tx import proper
from states import net

PORTAL = "https://candidateportal.servis.sos.state.nm.us/CandidateList.aspx?eid={eid}&cty=99"
LISTS = {"general": ("2917", "2026 General Election Contest/Candidate List"),
         "primary": ("2911", "2026 Primary Election Contest/Candidate List")}
RESULTS = "https://electionresults.sos.nm.gov/"
RESULTS_PAGE = RESULTS + "resultsSW.aspx?type=FED&map=CTY&eid=2911"
RESULTS_CSV = RESULTS + "resultsCSV.aspx?text=All&type=FED&map=CTY&eid=2911"
COUNTY_SERVICE = ("https://nmresultswebservice.azurewebsites.us/NMResultsAjax.svc/GetMapDataArchive?type=FED&category=CTY"
                  "&raceID={race}&osn={osn}&county=0&party={party}&electionID=2911")
CERTIFIED_NEWS = "https://www.sos.nm.gov/2026/06/23/state-canvass-board-certifies-2026-primary-election-results-orders-automatic-recounts/"
PRIMARY = "2026-06-02"
KEEP = ("Contest", "District", "Name", "Party", "Ballot Order", "Status")
ON, OFF = ("Qualified",), ("Disqualified", "Withdrawn")
SEATS = 3
WRITE_MARK = re.compile(r"\s*\(write[- ]in\)\s*$", re.I)
CAPS = "New Mexico's list prints names in capitals; they are shown here in ordinary capitals."
CAPS_RESULTS = "New Mexico's results print names in capitals; they are shown here in ordinary capitals."
WRITE_IN = "Write-in candidate: the name is not printed on the ballot."


def text(cell):
    cell = re.sub(r"<br\s*/?>", " ", cell)
    return re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", "", cell)).replace("\xa0", " ")).strip()


def race_of(office, district):
    office, district = (office or "").strip(), (district or "").strip().upper()
    if office == "United States Senator":
        if district:
            raise SystemExit(f"New Mexico: a U.S. Senator row names a district ({district!r})")
        return senate_id("NM", 2)
    if office == "United States Representative":
        m = re.fullmatch(r"DISTRICT (\d+)", district)
        if not m or not 1 <= int(m.group(1)) <= SEATS:
            raise SystemExit(f"New Mexico: a U.S. Representative row names a district that is not read ({district!r})")
        return house_id("NM", int(m.group(1)))
    if office.upper().startswith("UNITED STATES"):
        raise SystemExit(f"New Mexico: a federal office that is not read ({office!r})")
    return None


def ordinary(label):
    """DEMOCRATIC -> Democratic; NO PARTY/DECLINED TO SELECT -> No Party/Declined to Select."""
    words = re.split(r"(\s+|/)", label.strip())
    return "".join(w.lower() if i and w.upper() in ("TO", "OF", "THE", "AND") else w.capitalize() for i, w in enumerate(words))


def read_list(kind, path, say):
    """The federal rows of one list (the kept columns only), with the list's key of parties; kept on disk for two days."""
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < 2 * 86400:
        return json.load(open(path, encoding="utf-8"))
    eid, title = LISTS[kind]
    url = PORTAL.format(eid=eid)
    page = net.get(url, accept="text/html").decode("utf-8", "replace")
    if not re.search(r"<title>\s*" + re.escape(title) + r"\s*</title>", page):
        raise SystemExit(f"New Mexico: {url} is no longer the {title}")
    if re.search(r'class="rgPager|class="rgNumPart', page):
        raise SystemExit(f"New Mexico: the {title} now runs over several pages; read them through its pager")
    menu = re.search(r'id="MainContent_ddlParty"[^>]*>(.*?)</select>', page, re.S)
    legend = {c: ordinary(H.unescape(t)) for c, t in re.findall(r'<option[^>]*value="([A-Z]+)"[^>]*>([^<]+)</option>', menu.group(1) if menu else "")}
    if not legend:
        raise SystemExit(f"New Mexico: the {title} no longer shows its party menu")
    heads = [text(h) for h in re.findall(r'<th scope="col" class="rgHeader[^"]*"[^>]*>(.*?)</th>', page, re.S)]
    if not all(k in heads for k in KEEP):
        raise SystemExit(f"New Mexico: the candidate grid's columns changed ({[h for h in heads if h in KEEP]})")
    idx = {k: heads.index(k) for k in KEEP}
    idx["Contest"] = len(heads) - 1 - heads[::-1].index("Contest")      # printed twice; the second is the office alone
    rows = []
    for tr in re.findall(r'<tr class="(?:rgRow|rgAltRow)"[^>]*>(.*?)</tr>', page, re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        if len(cells) != len(heads):
            raise SystemExit(f"New Mexico: a row of the {title} does not line up with the grid's headings")
        rows.append({k: text(cells[i]) for k, i in idx.items()})
    fed = [r for r in rows if race_of(r["Contest"], r["District"])]
    if not fed:
        raise SystemExit(f"New Mexico: no federal rows read from the {title}")
    kept = {"title": title, "url": url, "items": len(rows), "legend": legend, "rows": fed}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(kept, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    say(f"      {title}: {len(rows)} rows, {len(fed)} for Congress")
    time.sleep(1.0)
    return kept


def county_check(race, code, cands, rows):
    """The county rows must add up to each candidate's statewide total. A count the site protects is printed "*" (in 2026
    one small county figure); it is not added, the rest must not exceed the total, and where it is its candidate's only
    protected figure the remainder it implies must give the county share the service itself prints beside it.
    Returns [(where, candidate, implied votes, whether the share was checked)]."""
    statewide = {c["name"]: c["votes"] for c in cands}
    if {r["name"] for r in rows} != set(statewide):
        raise SystemExit(f"New Mexico: the county figures for {race} {code} name other candidates than the statewide results")
    shown, hidden = {}, {}
    for r in rows:
        if r["votes"].isdigit():
            shown[r["name"]] = shown.get(r["name"], 0) + int(r["votes"])
        elif r["votes"] == "*":
            hidden.setdefault(r["name"], []).append(r)
        else:
            raise SystemExit(f"New Mexico: a county figure for {race} {code} that is not read ({r['votes']!r})")
    protected = []
    for name, total in statewide.items():
        rest = total - shown.get(name, 0)
        if name not in hidden:
            if rest:
                raise SystemExit(f"New Mexico: {name}'s county figures in {race} {code} add up to {shown.get(name, 0):,}, not {total:,}")
            continue
        if rest < 0:
            raise SystemExit(f"New Mexico: {name}'s shown county figures in {race} {code} exceed the statewide total")
        county = hidden[name][0]["county"]
        others = [r for r in rows if r["county"] == county and r["name"] != name]
        if len(hidden[name]) == 1 and all(r["votes"].isdigit() for r in others):
            whole = rest + sum(int(r["votes"]) for r in others)
            if not whole or abs(rest / whole - float(hidden[name][0]["share"] or 0)) > 1e-9:
                raise SystemExit(f"New Mexico: the protected figure for {name} in {county} County ({race} {code}) does not give the share "
                                 "the results service prints")
            protected.append((f"{county} County", name, rest, True))
        else:
            where = f"{county} County" if len(hidden[name]) == 1 else f"{len(hidden[name])} counties"
            protected.append((where, name, rest, False))
    return protected


def read_results(folder, say):
    """{(race, party code): [{"name", "write_in", "votes"}]} from the official results export, with the checks above."""
    cpath = os.path.join(folder, "nm_2026_primary_results_federal.csv")
    jpath = os.path.join(folder, "nm_2026_primary_results_checks.json")
    fresh = all(os.path.exists(p) and time.time() - os.path.getmtime(p) < 30 * 86400 for p in (cpath, jpath))
    if not fresh:
        page = net.get(RESULTS_PAGE, accept="text/html").decode("utf-8", "replace")
        plain = H.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", re.sub(r"(?s)<script.*?</script>|<style.*?</style>", "", page))))
        if "Official Results 2026 Primary June 2, 2026" not in plain or re.search(r"unofficial", plain, re.I):
            raise SystemExit("New Mexico: the results site no longer heads the 2026 primary \"Official Results\"; read it again")
        updated = re.search(r"Results last updated: ([0-9/]+ [0-9:]+ [AP]M(?: MT)?)", plain)
        osn = {f"{r}|{p}": o for r, o, p in re.findall(r"BuildCounty\('FED', '(\d+)', '(\d+)', '([A-Z]+)'\)", page)}
        time.sleep(1.0)
        raw = net.get(RESULTS_CSV, accept="text/csv,*/*")
        if not raw.lstrip(b"\xef\xbb\xbf").startswith(b"RaceID,RaceName,"):
            raise SystemExit("New Mexico: the results export is not the CSV of federal contests; read the Media/Results Exports page again")
        with open(cpath, "wb") as fh:
            fh.write(raw)
        json.dump({"heading": "Official Results 2026 Primary June 2, 2026", "updated": updated.group(1) if updated else "",
                   "osn": osn, "counties": {}}, open(jpath, "w", encoding="utf-8"), indent=1)
    checks = json.load(open(jpath, encoding="utf-8"))
    out, meta = {}, {}
    for r in csv.DictReader(io.StringIO(open(cpath, encoding="utf-8-sig").read())):
        race = race_of(r["RaceName"], r["AreaNum"])
        if not race:
            continue
        done, total = (r["PrecinctsReporting"] or "").split("/") if "/" in (r["PrecinctsReporting"] or "") else ("", "x")
        if done != total:
            raise SystemExit(f"New Mexico: the {race} {r['PartyCode']} primary is not fully reported ({r['PrecinctsReporting']})")
        votes = int(r["CandidateVotes"])
        parts = [int(r[k] or 0) for k in ("CandidateAbsenteeVotes", "CandidateElectionDayVotes", "CandidateEarlyVotes")]
        if sum(parts) != votes:
            raise SystemExit(f"New Mexico: {r['CandidateName']}'s absentee, election day and early votes do not add up to {votes}")
        key = (race, r["PartyCode"].strip())
        meta[key] = r["RaceID"]
        out.setdefault(key, []).append({"name": WRITE_MARK.sub("", r["CandidateName"]).strip(), "write_in": bool(WRITE_MARK.search(r["CandidateName"])),
                                        "votes": votes, "site_pct": float(r["CandidatePercentage"] or 0)})
    for key, cands in out.items():
        total = sum(c["votes"] for c in cands)
        if any(abs(c["site_pct"] - (c["votes"] / total if total else 0)) > 1e-9 for c in cands):
            raise SystemExit(f"New Mexico: the site's percentages for {key} are not shares of the candidates' votes; a total is missing")
    # the county-by-county figures behind every field, from the results page's own service
    fetched = False
    for (race, code), cands in sorted(out.items()):
        if sum(1 for c in cands if not c["write_in"]) < 2:
            continue
        ck = f"{meta[(race, code)]}|{code}"
        if ck not in checks["counties"]:
            if ck not in checks["osn"]:
                raise SystemExit(f"New Mexico: the results page does not draw the county map for {race} {code}")
            data = json.loads(net.get(COUNTY_SERVICE.format(race=meta[(race, code)], osn=checks["osn"][ck], party=code), accept="application/json"))
            kept = []
            for row in data:
                if str(row.get("RaceID")) != meta[(race, code)] or (row.get("PartyCode") or "").strip() != code:
                    raise SystemExit(f"New Mexico: the county service answered for another contest than {race} {code}")
                kept.append({"county": (row.get("CountyName") or row.get("CountyID") or "").strip(),
                             "name": WRITE_MARK.sub("", row.get("calcCandidate") or "").strip(),
                             "votes": str(row.get("calcCandidateVotes") or "0").strip(), "share": row.get("calcCandidatePercentage")})
            checks["counties"][ck] = {"race": race, "party": code, "rows": kept}
            fetched = True
            time.sleep(1.0)
        checks["counties"][ck]["protected"] = county_check(race, code, cands, checks["counties"][ck]["rows"])
    if fetched:
        json.dump(checks, open(jpath, "w", encoding="utf-8"), indent=1)
    if not fresh:
        say(f"      2026 Primary Official Results (updated {checks['updated']}): {sum(len(v) for v in out.values())} federal candidate lines")
    return out, checks, cpath


def roster_spellings():
    """Upper-case forms of the sitting New Mexico members' names, with the capitals the congress-legislators roster gives them."""
    path = os.path.join(HERE, "congress_119.sqlite")
    if not os.path.exists(path):
        return {}
    rec = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    out = {}
    try:
        for full, first, last in rec.execute("SELECT official_full, first_name, last_name FROM legislators WHERE is_current = 1 AND state = 'NM'"):
            for form in (full, f"{first} {last}"):
                if form:                                   # the letters as printed, with the roster's capitals: never another name
                    out[re.sub(r"\s+", " ", form.upper())] = form
    finally:
        rec.close()
    return out


def load(con, cache, say=print):
    net.patient_lookups()
    folder = os.path.join(cache, "nm")
    gen = read_list("general", os.path.join(folder, "nm_2026_general_federal.json"), say)
    pri = read_list("primary", os.path.join(folder, "nm_2026_primary_federal.json"), say)
    results, checks, cpath = read_results(folder, say)
    legend = {**pri["legend"], **gen["legend"]}

    def party_of(code):
        if code not in legend:
            raise SystemExit(f"New Mexico: the party code {code!r} is not in the list's key ({legend})")
        return legend[code]

    roster = roster_spellings()

    def shown(caps):
        caps = re.sub(r"\s+", " ", WRITE_MARK.sub("", caps)).strip()
        if caps in roster:
            return roster[caps]
        return re.sub(r"(['\"(])([a-z])", lambda m: m.group(1) + m.group(2).upper(), proper(caps))

    # who won each party primary, and how: the Senate's Republican nominee was a declared write-in
    primary_note = {}
    for (race, code), cands in results.items():
        if len(cands) == 1 and cands[0]["write_in"]:
            primary_note[(race, fold(cands[0]["name"]))] = (
                f"Nominated in the June 2 {party_of(code)} primary as a declared write-in candidate, the only candidate in that primary "
                f"({cands[0]['votes']:,} votes); no {party_of(code)} name was printed on that ballot.")

    rows, off, write_ins, nominee = [], [], [], {}
    for r in gen["rows"]:
        race = race_of(r["Contest"], r["District"])
        if r["Status"] in OFF:
            off.append(f"{shown(r['Name'])} ({party_of(r['Party']) if r['Party'] else 'no party'}, {r['Status'].lower()})")
            continue
        if r["Status"] not in ON:
            raise SystemExit(f"New Mexico: a status on the general list that is not read ({r['Status']!r}, {r['Contest']})")
        name, wi = shown(r["Name"]), bool(WRITE_MARK.search(r["Name"]))
        party = party_of(r["Party"]) if r["Party"] else "No party"
        notes = [WRITE_IN] if wi else []
        notes += [CAPS]
        if (race, fold(name)) in primary_note:
            notes.append(primary_note[(race, fold(name))])
        if wi:
            write_ins.append(name)
        else:
            if (race, r["Party"]) in nominee:
                raise SystemExit(f"New Mexico: two {party} candidates printed for {race} on the general list")
            nominee[(race, r["Party"])] = fold(name)
        order = int(r["Ballot Order"]) if r["Ballot Order"].isdigit() and not wi else None
        rows.append((race, "general", "2026-11-03", name, party, party_code(party), order, 0, int(wi), None, None, None, None, None,
                     "nm-sos-2026-general-list", " ".join(notes)))

    # the primary list: who was on each party's June ballot; the results must name exactly them
    filed, withdrew = {}, []
    for r in pri["rows"]:
        race = race_of(r["Contest"], r["District"])
        if r["Status"] in OFF:
            withdrew.append(f"{shown(r['Name'])}, {party_of(r['Party'])}, {race} ({r['Status'].lower()})")
        elif r["Status"] in ON:
            filed.setdefault((race, r["Party"]), set()).add(fold(WRITE_MARK.sub("", r["Name"])))
        else:
            raise SystemExit(f"New Mexico: a status on the primary list that is not read ({r['Status']!r}, {r['Contest']})")
    if set(filed) != set(results):
        raise SystemExit(f"New Mexico: the primary list's party contests and the results' differ ({sorted(set(filed) ^ set(results))})")
    for key, cands in results.items():
        if {fold(c["name"]) for c in cands} != filed[key]:
            raise SystemExit(f"New Mexico: the results' candidates for {key} are not the primary list's Qualified rows")

    fields, upset, counted = 0, [], 0
    for (race, code), cands in sorted(results.items()):
        if sum(1 for c in cands if not c["write_in"]) < 2:
            continue
        fields += 1
        counted += len(cands)
        party, total = party_of(code), sum(c["votes"] for c in cands)
        top = max(cands, key=lambda c: c["votes"])
        won = nominee.get((race, code))
        winner = next((c for c in cands if fold(c["name"]) == won), None) or top
        if winner is not top:
            upset.append(f"{race} {party}")
        for c in sorted(cands, key=lambda c: -c["votes"]):
            notes = [WRITE_IN] if c["write_in"] else []
            notes.append(CAPS_RESULTS)
            if c is winner and won is None:
                notes.append("Won the primary; not on the November list.")
            rows.append((race, f"primary-{code}", PRIMARY, shown(c["name"]), party, party_code(party), None, 0, int(c["write_in"]), c["votes"],
                         round(100 * c["votes"] / total, 1) if total else None, "advanced" if c is winner else "lost", None, None,
                         "nm-sos-2026-primary-results", " ".join(notes)))

    protected = [p for v in checks["counties"].values() for p in v.get("protected", [])]
    races = {r[0] for r in con.execute("SELECT race_id FROM races WHERE state = 'NM'")}
    listed = {r[0] for r in rows if r[1] == "general"}
    gaps = sorted(races - listed)
    general = [r for r in rows if r[1] == "general"]
    with con:
        con.execute("DELETE FROM candidates WHERE race_id LIKE '2026-NM-%'")
        con.execute("DELETE FROM list_gaps WHERE state = 'NM'")
        con.executemany("INSERT OR REPLACE INTO candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        con.executemany("INSERT INTO list_gaps VALUES (?, 'NM', ?)",
                        [(race, "the Secretary of State's candidate list names no one for this seat yet") for race in gaps])
        record_source(con, "nm-sos-2026-general-list", path=os.path.join(folder, "nm_2026_general_federal.json"), level="federal", state="NM",
                      kind="official candidate list", agency="New Mexico Secretary of State",
                      title="2026 General Election Contest/Candidate List (November 3, 2026): United States Senator and United States Representative",
                      url=gen["url"], rows=len(gen["rows"]),
                      note=f"The candidate portal's grid of every office ({gen['items']} rows, one page); the kept columns only (contest, district, "
                           f"name, party, ballot order, status), addresses, phones, e-mail and websites never read. The list's own ballot order is "
                           f"kept. Disqualified or withdrawn, left off: {len(off)}" + (f" ({'; '.join(off)})" if off else "")
                           + f". Declared write-ins: {len(write_ins)}. Parties written out from the list's own key.")
        record_source(con, "nm-sos-2026-primary-list", path=os.path.join(folder, "nm_2026_primary_federal.json"), level="federal", state="NM",
                      kind="official candidate list", agency="New Mexico Secretary of State",
                      title="2026 Primary Election Contest/Candidate List (June 2, 2026): United States Senator and United States Representative",
                      url=pri["url"], rows=len(pri["rows"]),
                      note="Used to check the primary results: every party contest's names are exactly that party's Qualified rows. "
                           f"Disqualified or withdrawn before the primary, not on its ballot: {'; '.join(withdrew) or 'none'}.")
        record_source(con, "nm-sos-2026-primary-results", path=cpath, level="federal", state="NM", kind="official results",
                      agency="New Mexico Secretary of State",
                      title="2026 Primary Election Official Results (June 2, 2026), certified by the State Canvass Board on June 23, 2026: "
                            "Federal contests, the results site's CSV export",
                      url=RESULTS_CSV, published="2026-06-23", rows=counted,
                      note=f"The results page ({RESULTS_PAGE}) is headed \"Official Results\", last updated {checks['updated']}; the Secretary's "
                           f"release of June 23, 2026 ({CERTIFIED_NEWS}) says the certified results are the ones on this site. Every precinct "
                           "reported; absentee, election day and early votes add up; each field's county-by-county figures (the page's own "
                           "service) add up to its statewide totals"
                           + (" (protected, printed \"*\": " + "; ".join(
                               f"{proper(n)} in {where}, {v:,} by the remainder" + (", which gives the share the service prints" if ok else "")
                               for where, n, v, ok in protected) + ")" if protected else "")
                           + ". Write-in votes are counted only for declared write-in candidates, who are listed among the candidates, so a "
                           "field's total is its candidates' votes."
                           + (f" November nominee not the primary's top vote-getter: {', '.join(upset)}." if upset else ""))
    if upset:
        say("    New Mexico: the November nominee is not the primary's top vote-getter in " + ", ".join(upset) + "; read the files again")
    say(f"    New Mexico: {len({r[0] for r in general if '-H' in r[0]})} House districts and {'the' if senate_id('NM', 2) in listed else 'no'} "
        f"Senate race, {len(general)} candidates on the November ballot ({len(off)} disqualified or withdrawn left off"
        + (f", {len(write_ins)} declared write-ins" if write_ins else "") + f"); {fields} party primaries with a field, votes from the "
        "official certified results" + (f"; not loaded: {', '.join(gaps)}" if gaps else ""))
    return len(general)
