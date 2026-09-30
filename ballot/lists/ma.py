"""
Massachusetts: the Secretary of the Commonwealth's Elections Division. Massachusetts elects its nine House members
(2022 lines) and the class 2 U.S. Senator (Edward J. Markey's seat) on November 3, 2026. The state primary was held on
September 1, 2026 (the last date in the Division's results database for 2026).

  November ballot   the Division's "2026 State Election Candidates" page (LIST_PAGE), one heading per office, one
                    heading per district beneath "Representative in Congress", and one paragraph per candidate:
                    the name, the street address, the city or town and the party or political designation, in that
                    order, separated by commas. www.sec.state.ma.us sits behind an Incapsula bot wall: every request
                    on 2026-09-30 (three pages, the list among them) got the wall's one-kilobyte page in place of the
                    page asked for. The wall is never worked around, so this loader does not download the list. It
                    reads the page as a browser saves it into ballot_cache/ma/ ("Save as", "Webpage, HTML only" or
                    "Single file"), under any name containing "2026 State Election Candidates" (spaces, hyphens or
                    underscores; .html, .htm or .mhtml), such as ma_2026_state_election_candidates.html. Until it is
                    there, the ten races are recorded in list_gaps and no November candidates are stored.
  primary fields    the Division's certified results of the September 1, 2026 state primary, from PD43+
                    (electionstats.state.ma.us, "Certified Election Results" in the Division's own menu; "all from
                    Public Document 43", the Secretary's official returns). Its search for 2026, U.S. House (office 5)
                    and U.S. Senate (office 6), lists each party primary with every candidate's votes, the winner's
                    mark, All Others (write-in votes for names not listed), Blanks and Total Votes Cast; each
                    primary's CSV download (city and town totals and a TOTALS row) is the control: the towns must add
                    up to the TOTALS row, and the TOTALS row must equal the search page, for every candidate and line.

Only the two federal sections of the list are read ("Senator in Congress" and "Representative in Congress"), and of
each candidate's paragraph only the name (the first field, with a following Jr., Sr., II, III or IV) and the party
(the last field). The street address and the town printed between them are never stored, printed or kept: the loader
keeps nothing from the saved page but the names, parties and districts it reads, and the saved page stays where the
browser put it. The party must be one of the designations in PARTIES; a line whose last field is instead a
Massachusetts city or town (the 351 in the Senate primary's results) prints no party, and any other last field stops
the loader without printing it, so that a new designation is added to PARTIES by hand after a look at the page (and
an address can never be taken for a party). The layout was learned from the Internet Archive's copy of the page
(2026-09-28), read in memory on 2026-09-30 only for that and to test this reader; nothing from it is stored. On that
copy every federal line read as name, street, town and party except Richard E. Neal's, which prints no party: a candidate with no party printed who won a party's
certified primary for the same seat is shown with that party and a note saying so; anyone else with no party printed
would be shown without one. A line marked withdrawn, removed or struck through is left off and counted. The list
names no write-in candidates, and none are stored. Ballot order is the list's own order.

Parties and designations are shown as printed (Democratic, Republican, Independent, Unenrolled,
Independent/Unenrolled, Socialism and Liberation). Names are printed first name first in ordinary capitals and are
kept as printed; a name in capitals would be shown in ordinary capitals with a note.

A party primary is a field when two or more candidates were printed on that party's ballot for the seat. In 2026
that is seven Democratic primaries (the Senate and districts 1, 4, 5, 6, 8 and 9); every Republican primary had one
printed candidate or none (District 5's Republican ballot had none, and its one named write-in was not nominated), and
PD43+ lists no other party's primary for these offices. A named
write-in candidate in a field's results is shown as one (write_in 1). pct is a candidate's share of the votes for
candidates and write-ins (All Others), blanks left out, as PD43+ computes it (checked to 0.1). The winner's mark says
who advanced; it must be the top vote-getter, and each winner must be that party's candidate on the November list,
or the row says plainly that the nominee is not on it.

The same blocked host also carries the Division's "2026 Candidates" and party primary candidate pages
(candidates2026.htm, dem-state-primary-candidates2026.htm); they are not read. The PD43+ search page carries names,
votes and the office only; its CSV's second line is empty on these files (it is
never read either way). The cache (ballot_cache/ma/) keeps the figures read, as JSON.
"""

import csv
import email
import glob
import html as H
import io
import json
import os
import re
import time

from ballot.common import fold, house_id, name_parts, party_code, record_source, senate_id
from ballot.lists.tx import proper
from states import net

ES = "https://electionstats.state.ma.us"
SEARCH = ES + "/elections/search/year_from:2026/year_to:2026/office_id:{office}"
CSV_URL = ES + "/elections/download/{eid}/precincts_include:0/"
LIST_PAGE = "https://www.sec.state.ma.us/divisions/elections/research-and-statistics/2026-state-election-candidates.htm"
PRIMARY = "2026-09-01"
OFFICES = {5: "U.S. House", 6: "U.S. Senate"}
SENATE = senate_id("MA", 2)
RACES = [house_id("MA", d) for d in range(1, 10)] + [SENATE]
SECTIONS = {"senator in congress": "S", "representative in congress": "H"}
ORDINALS = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9}
PARTIES = {      # designations as the Secretary prints them; a new one is added here after checking the page by eye
    "Democratic", "Republican", "Libertarian", "Green-Rainbow", "Unenrolled", "Independent", "Independent/Unenrolled",
    "Socialism and Liberation", "Workers Party", "Working Families"}
SUFFIX = re.compile(r"^(Jr|Sr|II|III|IV|V|2nd|3rd)\.?$", re.I)
OFF = re.compile(r"\(?\b(withdrawn|withdrew|removed|deceased|disqualified)\b\)?", re.I)
GAP = "the Secretary of the Commonwealth's website turns away automated requests, so its list waits to be saved from a browser"
WRITE_IN = "Write-in candidate: the name is not printed on the ballot."
CAPS = "Massachusetts's list prints names in capitals; they are shown here in ordinary capitals."
NO_PARTY_NOMINEE = ("The Secretary's list prints no party beside this name; the party shown is the one whose certified "
                    "September 1 primary for this seat the candidate won.")
NO_PARTY = "The Secretary's list prints no party or designation beside this name."


def squash(text):
    return re.sub(r"\s+", " ", (text or "").replace("\xa0", " ")).strip()


def text(fragment):
    return squash(H.unescape(re.sub(r"<[^>]+>", " ", fragment)))


def ints(cell):
    t = squash(cell).replace(",", "")
    if not re.fullmatch(r"\d+", t):
        raise SystemExit(f"Massachusetts: a vote count that is not a whole number in the PD43+ results ({cell!r})")
    return int(t)


def code(party):
    """The election key's party code: DEM, REP, LIB; any other party's first three letters."""
    return {"Democratic": "DEM", "Republican": "REP", "Libertarian": "LIB"}.get(party) or re.sub(r"[^A-Z]", "", party.upper())[:3]


def colour(party):
    return "I" if party and "unenrolled" in party.lower() else party_code(party)


# ---------- the certified primary results (PD43+) ----------

def search(office, say):
    """Every 2026 primary PD43+ lists for one office: id, district, party, candidates, All Others, Blanks, Total."""
    page = net.get(SEARCH.format(office=office), accept="text/html").decode("utf-8", "replace")
    time.sleep(1.5)
    if "election-id-" not in page:
        raise SystemExit(f"Massachusetts: the PD43+ search for {OFFICES[office]} lists no elections ({SEARCH.format(office=office)})")
    out = []
    for part in re.split(r'(?=<tr\s+id="election-id-)', page)[1:]:
        eid = re.match(r'<tr\s+id="election-id-(\d+)"', part).group(1)
        part = part.split('<tr class="more_info"')[0]
        cells = [text(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", part[:part.find("candidates_container_cell")] + "</td>", re.S)][:4]
        if len(cells) < 4 or cells[0] != "2026" or cells[1] != OFFICES[office]:
            raise SystemExit(f"Massachusetts: PD43+ election {eid} does not read as a 2026 {OFFICES[office]} election ({cells[:2]})")
        m = re.fullmatch(r"(.+?) Primary", cells[3])
        if not m:
            if cells[3] == "General" or cells[3].startswith("Special"):
                continue                                          # the general election, once its results are posted
            raise SystemExit(f"Massachusetts: PD43+ election {eid} is a stage that is not read ({cells[3]!r})")
        party = m.group(1)
        if office == 5:
            d = re.fullmatch(r"(\d+)(?:st|nd|rd|th) Congressional", cells[2])
            if not d or not 1 <= int(d.group(1)) <= 9:
                raise SystemExit(f"Massachusetts: PD43+ election {eid} names a district that is not read ({cells[2]!r})")
            race = house_id("MA", int(d.group(1)))
        else:
            if cells[2] != "Statewide":
                raise SystemExit(f"Massachusetts: PD43+ Senate election {eid} is not statewide ({cells[2]!r})")
            race = SENATE
        cands, lines = [], {}
        for cls, body in re.findall(r'<tr class="([^"]*)">(.*?)</tr>', part, re.S):
            nums = [text(n) for n in re.findall(r'<td class="number">(.*?)</td>', body, re.S)]
            if "non_candidate" in cls:
                kind = re.search(r"n_(all_other|blank|total)_votes", cls)
                if not kind or not nums:
                    raise SystemExit(f"Massachusetts: a line in PD43+ election {eid} that is not read ({cls.strip()!r})")
                lines[kind.group(1)] = ints(nums[0])
                continue
            name = re.search(r'<div class="name">(.*?)</div>', body, re.S)
            if not name or len(nums) < 2:
                continue
            label = re.search(r'<div class="party">(.*?)</div>', body, re.S)
            label = text(label.group(1)) if label else ""
            if label not in ("", "(Write-In)"):
                raise SystemExit(f"Massachusetts: a label beside a name in PD43+ election {eid} that is not read ({label!r})")
            cands.append({"name": text(name.group(1)), "write_in": label == "(Write-In)", "votes": ints(nums[0]),
                          "pct": float(nums[1].rstrip("%")) if nums[1] else None, "winner": "is_winner" in cls})
        if cands and set(lines) != {"all_other", "blank", "total"}:
            raise SystemExit(f"Massachusetts: PD43+ election {eid} is missing its All Others, Blanks or Total line")
        out.append({"id": eid, "race": race, "party": party, "candidates": cands, **lines})
    say(f"      PD43+: {OFFICES[office]}, {len(out)} primaries listed")
    return out


def town_totals(eid):
    """The CSV download of one primary: the cities and towns, and each column summed over them and in the TOTALS row."""
    raw = net.get(CSV_URL.format(eid=eid))
    time.sleep(1.0)
    if raw[:8].lstrip(b"\xef\xbb\xbf")[:4] != b"City":
        raise SystemExit(f"Massachusetts: PD43+'s download for election {eid} is not its CSV file")
    rows = list(csv.reader(io.StringIO(raw.decode("utf-8-sig", "replace"))))
    heads = [squash(h) for h in rows[0]]
    for need in ("City/Town", "All Others", "Blanks", "Total Votes Cast"):
        if need not in heads:
            raise SystemExit(f"Massachusetts: PD43+'s CSV for election {eid} has no {need!r} column")
    cols = [i for i, h in enumerate(heads) if h and h not in ("City/Town", "Ward", "Pct")]
    sums, totals, towns = {heads[i]: 0 for i in cols}, None, []
    for r in rows[1:]:
        first = squash(r[0]) if r else ""
        if not first:
            continue                                              # the empty line under the headings, never read
        if first == "TOTALS":
            totals = {heads[i]: ints(r[i]) for i in cols}
            continue
        towns.append(first)
        for i in cols:
            sums[heads[i]] += ints(r[i]) if squash(r[i]) else 0
    if totals is None:
        raise SystemExit(f"Massachusetts: PD43+'s CSV for election {eid} has no TOTALS row")
    return {"towns": towns, "sums": sums, "totals": totals}


def primary_results(say):
    elections = search(5, say) + search(6, say)
    for e in elections:
        if e["candidates"]:
            e["csv"] = town_totals(e["id"])
    say(f"      PD43+: {sum(1 for e in elections if e['candidates'])} primaries' city and town files read")
    return {"elections": elections}


def check_results(results):
    """Controls: towns add up to TOTALS, TOTALS equal the search page, lines add up, one winner and the top one."""
    towns = set()
    for e in results["elections"]:
        if not e["candidates"]:
            continue
        c = e["csv"]
        where = f"PD43+ election {e['id']} ({e['race']}, {e['party']})"
        if c["sums"] != c["totals"]:
            raise SystemExit(f"Massachusetts: {where}: the cities and towns do not add up to the TOTALS row")
        page = {x["name"]: x["votes"] for x in e["candidates"]}
        page.update({"All Others": e["all_other"], "Blanks": e["blank"], "Total Votes Cast": e["total"]})
        if page != c["totals"]:
            raise SystemExit(f"Massachusetts: {where}: the CSV's TOTALS row does not equal the search page "
                             f"({sorted(set(page.items()) ^ set(c['totals'].items()))[:4]})")
        if sum(x["votes"] for x in e["candidates"]) + e["all_other"] + e["blank"] != e["total"]:
            raise SystemExit(f"Massachusetts: {where}: the candidates, All Others and Blanks do not add up to Total Votes Cast")
        cast = sum(x["votes"] for x in e["candidates"]) + e["all_other"]
        for x in e["candidates"]:
            if x["pct"] is not None and cast and abs(round(100 * x["votes"] / cast, 1) - x["pct"]) > 0.11:
                raise SystemExit(f"Massachusetts: {where}: {x['name']}'s share does not agree with PD43+'s ({x['pct']}%)")
        won = [x for x in e["candidates"] if x["winner"]]
        top = max(x["votes"] for x in e["candidates"])
        if len(won) > 1 or (won and won[0]["votes"] != top):
            raise SystemExit(f"Massachusetts: {where}: the winner's mark is not on the one top vote-getter")
        if e["race"] == SENATE:
            towns |= set(c["towns"])
    if len(towns) != 351:
        raise SystemExit(f"Massachusetts: the Senate primary's results list {len(towns)} cities and towns, not 351")
    return {fold(t) for t in towns}


# ---------- the November list, as saved from a browser ----------

def saved_list(folder):
    found = [p for p in glob.glob(os.path.join(folder, "*"))
             if p.lower().endswith((".html", ".htm", ".mhtml", ".mht"))
             and "2026stateelectioncandidates" in re.sub(r"[^a-z0-9]", "", os.path.basename(p).lower())]
    if len(found) > 1:
        raise SystemExit(f"Massachusetts: more than one saved copy of the November list in {folder}; keep only the newest")
    return found[0] if found else None


def page_html(path):
    raw = open(path, "rb").read()
    if path.lower().endswith((".mhtml", ".mht")):
        for part in email.message_from_bytes(raw).walk():
            if part.get_content_type() == "text/html":
                body = part.get_payload(decode=True)
                return body.decode(part.get_content_charset() or "utf-8", "replace")
        raise SystemExit(f"Massachusetts: {os.path.basename(path)} holds no web page")
    return raw.decode("utf-8", "replace")


def general_list(path, towns):
    """[(race, name, party or None, order, caps)] and the lines left off, from the two federal sections only."""
    page = page_html(path)
    if not re.search(r"<h1[^>]*>\s*2026 State Election Candidates\s*</h1>", page):
        raise SystemExit(f"Massachusetts: {os.path.basename(path)} is not the Secretary's \"2026 State Election Candidates\" page")
    main = re.search(r"<main\b.*?</main>", page, re.S)
    main = main.group(0) if main else page
    on, off, order, where, seen = [], [], {}, None, set()
    for tag, attrs, inner in re.findall(r"<(h2|h3|p)\b([^>]*)>(.*?)</\1>", main, re.S):
        t = text(inner)
        if tag == "h2":
            where = [SECTIONS.get(t.lower()), None]
            continue
        if not where or not where[0]:
            continue
        if tag == "h3":
            d = re.fullmatch(r"(\w+) District", t)
            if where[0] != "H" or not d or d.group(1).lower() not in ORDINALS:
                raise SystemExit(f"Massachusetts: a heading in the list's {'Senate' if where[0] == 'S' else 'House'} section that is not read ({t!r})")
            where[1] = ORDINALS[d.group(1).lower()]
            continue
        label = "Senator in Congress" if where[0] == "S" else f"Representative in Congress, district {where[1]}"
        if not t or "top-of-page" in attrs or re.search(r"top of page", t, re.I):
            continue                                              # the "Top of page" link
        if "," not in t:
            raise SystemExit(f"Massachusetts: a line under {label} that does not read as name, street, town and party")
        race = SENATE if where[0] == "S" else (house_id("MA", where[1]) if where[1] else None)
        if not race:
            raise SystemExit("Massachusetts: a candidate line in the list's House section before any district heading")
        fields = [squash(f) for f in t.split(",")]
        name, i = fields[0], 1
        while i < len(fields) and SUFFIX.match(fields[i]):
            name += ", " + fields[i]
            i += 1
        rest = fields[i:]
        struck = bool(re.search(r"<(s|del|strike)\b", inner, re.I)) or bool(OFF.search(name))
        name = squash(OFF.sub("", name))
        if re.search(r"\d", name) or not re.fullmatch(r"[A-Za-z .,'\"()\-\u00c0-\u017f\u2018-\u201d]+", name) or len(name.split()) > 7:
            raise SystemExit(f"Massachusetts: a candidate line under {label} does not begin with a name (line {len(on) + len(off) + 1})")
        if len(rest) < 2:
            raise SystemExit(f"Massachusetts: a candidate line under {label} has fewer fields than a name, street, town and party")
        last = rest[-1]
        if last in PARTIES:
            party = last
            if fold(rest[-2]) not in towns and len(rest) < 3:
                raise SystemExit(f"Massachusetts: a candidate line under {label} does not read as name, street, town and party")
        elif fold(last) in towns:
            party = None                                          # the line ends with the town: no party printed
        else:
            raise SystemExit(f"Massachusetts: a candidate line under {label} ends in a field that is neither a designation in "
                             f"PARTIES nor a Massachusetts city or town; look at the page and add the designation to PARTIES")
        if struck:
            off.append(f"{name} ({label})")
            continue
        caps = name == name.upper() and any(c.isalpha() for c in name)
        shown = proper(name) if caps else name
        if (race, fold(shown)) in seen:
            raise SystemExit(f"Massachusetts: {shown} is listed twice under {label}")
        seen.add((race, fold(shown)))
        order[race] = order.get(race, 0) + 1
        on.append((race, shown, party, order[race], caps))
    missing = [r for r in RACES if r not in order]
    if missing:
        raise SystemExit(f"Massachusetts: no candidates read for {missing} in {os.path.basename(path)}")
    return on, off


def same_person(a, b):
    ga, fa = name_parts(a)
    gb, fb = name_parts(b)
    return fa == fb and bool(ga) and bool(gb) and (ga[0].startswith(gb[0]) or gb[0].startswith(ga[0]))


def load(con, cache, say=print):
    net.patient_lookups()
    folder = os.path.join(cache, "ma")
    os.makedirs(folder, exist_ok=True)
    rpath = os.path.join(folder, "ma_2026_primary_results.json")
    if os.path.exists(rpath) and time.time() - os.path.getmtime(rpath) < 30 * 86400:
        results = json.load(open(rpath, encoding="utf-8"))
    else:
        results = primary_results(say)
        json.dump(results, open(rpath, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    towns = check_results(results)

    # the party primaries with a field: two or more printed candidates on the party's ballot
    rows, fields, winners = [], 0, {}
    for e in results["elections"]:
        for x in e["candidates"]:
            if x["winner"]:
                winners.setdefault(e["race"], []).append((e["party"], x["name"]))
        printed = [x for x in e["candidates"] if not x["write_in"]]
        if len(printed) < 2:
            continue
        fields += 1
        cast = sum(x["votes"] for x in e["candidates"]) + e["all_other"]
        for x in sorted(e["candidates"], key=lambda x: (-x["votes"], x["name"])):
            rows.append([e["race"], f"primary-{code(e['party'])}", PRIMARY, x["name"], e["party"], colour(e["party"]), None, 0,
                         int(x["write_in"]), x["votes"], round(100 * x["votes"] / cast, 1) if cast else None,
                         "advanced" if x["winner"] else "lost", None, None, "ma-sec-2026-primary-results",
                         WRITE_IN if x["write_in"] else None])

    gpath = saved_list(folder)
    general, off, not_on, disagree = [], [], [], []
    if gpath:
        on, off = general_list(gpath, towns)
        for race, name, party, order, caps in on:
            notes = [CAPS] if caps else []
            if party is None:
                won = [p for p, n in winners.get(race, []) if same_person(n, name)]
                if len(won) == 1:
                    party = won[0]
                    notes.append(NO_PARTY_NOMINEE)
                else:
                    notes.append(NO_PARTY)
            general.append([race, "general", "2026-11-03", name, party, colour(party) if party else "O", order, 0, 0, None, None, None,
                            None, None, "ma-sec-2026-general-list", " ".join(notes) or None])
        # each primary winner should be that party's candidate on the November list, and each party candidate a winner
        for race, won in winners.items():
            for party, name in won:
                if not any(g[0] == race and g[4] == party and same_person(g[3], name) for g in general):
                    not_on.append(f"{name} ({race}, {party})")
                    for r in rows:
                        if r[0] == race and r[3] == name and r[1] == f"primary-{code(party)}":
                            r[15] = "Won the primary but is not on the November list."
        for g in general:
            if g[4] in ("Democratic", "Republican") and not any(p == g[4] and same_person(n, g[3]) for p, n in winners.get(g[0], [])):
                disagree.append(f"{g[3]} ({g[0]}, {g[4]})")

    with con:
        con.execute("DELETE FROM candidates WHERE race_id LIKE '2026-MA-%'")
        con.execute("DELETE FROM list_gaps WHERE state = 'MA'")
        con.execute("DELETE FROM ballot_sources WHERE source_id LIKE 'ma-sec-2026-%'")      # a file no longer used is not kept on record
        con.executemany("INSERT OR REPLACE INTO candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [tuple(r) for r in general + rows])
        if gpath:
            record_source(con, "ma-sec-2026-general-list", path=gpath, level="federal", state="MA", kind="official candidate list",
                          agency="Massachusetts Secretary of the Commonwealth, Elections Division",
                          title="2026 State Election Candidates (November 3, 2026): Senator in Congress and Representative in Congress",
                          url=LIST_PAGE, rows=len(general) + len(off),
                          note=f"Saved from a browser ({os.path.basename(gpath)}): www.sec.state.ma.us answers scripts with an Incapsula "
                               "challenge. Only the name and the party or designation are read from each candidate's line; the street "
                               "address and town printed between them are never kept. Ballot order is the list's own order. "
                               f"Withdrawn or struck through, left off: {len(off)} ({'; '.join(off) or 'none'}). No write-in candidates listed.")
        else:
            con.executemany("INSERT INTO list_gaps VALUES (?, 'MA', ?)", [(race, GAP) for race in RACES])
        record_source(con, "ma-sec-2026-primary-results", path=rpath, level="federal", state="MA", kind="official results",
                      agency="Massachusetts Secretary of the Commonwealth, Elections Division",
                      title="PD43+ Certified Election Results: 2026 State Primary (September 1, 2026), U.S. House and U.S. Senate",
                      url=SEARCH.format(office=5), rows=sum(len(e["candidates"]) for e in results["elections"]),
                      note=f"The PD43+ searches for 2026, U.S. House (office_id 5) and U.S. Senate (office_id 6): "
                           f"{len(results['elections'])} party primaries, {sum(1 for e in results['elections'] if e['candidates'])} with "
                           "candidates. Control: each primary's city and town CSV (" + CSV_URL.format(eid="<id>") + ") adds up to its TOTALS "
                           "row, and the TOTALS row equals the search page for every candidate, All Others, Blanks and Total Votes Cast. "
                           "All Others is write-in votes for names not listed; a field's total for pct is its candidates plus All Others.")
    if gpath:
        say(f"    Massachusetts: 9 House districts and the Senate, {len(general)} candidates on the November ballot "
            f"({len(off)} withdrawn left off); {fields} party primaries with a field, votes from the certified PD43+ results, "
            f"city and town files checked"
            + (f"; primary winners not on the November list: {', '.join(not_on)}" if not_on else "")
            + (f"; party candidates on the November list who did not win its primary: {', '.join(disagree)}" if disagree else ""))
    else:
        say(f"    Massachusetts: the November list waits for a browser: www.sec.state.ma.us answers scripts with an Incapsula challenge. "
            f"Save {LIST_PAGE} (\"Webpage, HTML only\") into {folder}; the 10 races are marked not loaded. "
            f"{fields} party primaries with a field stored, votes from the certified PD43+ results, city and town files checked")
    return len(general)
