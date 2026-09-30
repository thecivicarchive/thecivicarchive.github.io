"""
Washington: the Secretary of State's candidate lists on voter.votewa.gov ("GENERAL 2026 Candidate List", election 899,
and "PRIMARY 2026 Candidate List", election 898; sos.wa.gov/elections links the first as "Candidates Who Have Filed"),
and the certified results of the August 4, 2026 primary from the Secretary's results site (results.vote.wa.gov, which
now sends readers to results.votewa.gov/results/public/washington): its "All Results Excel" workbook, one sheet of
statewide totals per contest and candidate ("Summary Results") and one of the same by county ("Precinct Results",
whose first column names the county).

Washington's primary is top-two: every candidate, of every party preference, is on one primary ballot, and the two who
receive the most votes advance to the November general election, whatever their parties (a tie for second advances
everyone tied). So the primary field is every candidate with their votes, and the November ballot is the top two.
There is no U.S. Senate race in Washington in 2026.

Each list is a Telerik grid of every office, 100 rows a page. Every page is read through the grid's own pager (the
form posted with its Next Page button, as a browser posts it) and the count of rows is checked against the grid's own "items" figure.
Columns are taken by name, only District Type, District, Race, Term Type, Name, Party Preference, Status, Election
Status and Ballot Order; the grid also carries mailing addresses, e-mail and phones, which are never read, and the
cached copy keeps only the columns taken, for the federal rows. Status is Active or Withdrawn: a withdrawn candidate
is left off and counted, and any other status stops the loader. The general list gives the November ballot order (the
primary's leader first).

The results site's own election record (its public API, /results/public/api/elections/washington/20260804) names the
current workbook and says whether the results are official; the loader stops unless they are. A field's total is its
candidates' votes plus the write-in line ("Write-In", votes for names not printed on the ballot, not a candidate);
over- and under-votes are left out. Controls: every candidate's county rows add up to the statewide total; the
primary field is exactly the primary list's Active candidates for that district; the two who advanced are exactly the
general list's two; and each candidate's party preference agrees between the results and the lists.

Party preferences are shown as the ballot and the results print them, without the parentheses ("(Prefers Democratic
Party)" is stored as "Prefers Democratic Party", "(States No Party Preference)" as "States No Party Preference"); the
lists write the same preference short and in capitals (DEMOCRATIC, STATES NO PARTY PREFERENCE), and only serve as the
check. Names are printed in ordinary capitals and are kept as printed.

The Secretary also posts the signed "2026 Certification of Candidates to General Election" and the "Official Canvass
of the Returns" of the primary, both on the 2026 Primary Election page. Both are scanned images with no text layer, so
they are fingerprinted in ballot_sources and not read.
"""

import collections
import html as H
import json
import os
import re
import time
import urllib.parse
from urllib.request import Request, urlopen

import openpyxl

from ballot.common import fold, house_id, party_code, record_source
from states import net

LIST_URL = "https://voter.votewa.gov/CandidateList.aspx?e="
LISTS = {"general": ("899", "GENERAL 2026"), "primary": ("898", "PRIMARY 2026")}
API = "https://results.votewa.gov/results/public/api/elections/washington/20260804"
CDN = "https://results.votewa.gov/cdn/results/"
RESULTS_PAGE = "https://results.vote.wa.gov/"
SOS_PAGE = ("https://www.sos.wa.gov/elections/data-research/election-data-and-maps/election-results-and-voters-pamphlets/"
            "2026-primary-election")
SCANS = {
    "wa-sos-2026-certification": ("wa_2026_certification_of_candidates_general.pdf",
                                  "https://www.sos.wa.gov/sites/default/files/2026-08/2026%20Certification%20of%20Candidates%20to%20General%20Election.pdf",
                                  "2026 Certification of Candidates to General Election"),
    "wa-sos-2026-primary-canvass": ("wa_2026_primary_official_canvass.pdf",
                                    "https://www.sos.wa.gov/sites/default/files/2026-08/Official%20Canvass%20of%20Returns%20of%20the%20Primary%202026.pdf",
                                    "Official Canvass of the Returns of the Primary, August 4, 2026 (certification)")}
PRIMARY = "2026-08-04"
KEEP = ("District Type", "District", "Race", "Term Type", "Name", "Party Preference", "Status", "Election Status", "Ballot Order")
BOOK_KEEP = ("Office Name", "Ballot Name", "Choice ID", "Party", "Total")
COUNTY_KEEP = ("Precinct",) + BOOK_KEEP
OFFICE = re.compile(r"U\.S\. Representative - Congressional District (\d+)")
NOT_CANDIDATES = ("ballots cast", "over votes", "under votes")
TOP_TWO = "Advanced from the August 4 top-two primary. Washington prints each candidate's party preference."


def race_of(race, district):
    """The race key for a federal row of a list, or None for any other office."""
    race = (race or "").strip()
    if race.upper().startswith("U.S. SENAT"):
        raise SystemExit("Washington: a U.S. Senate row is on the list; Washington has no Senate race in 2026. Read the list again.")
    if race != "U.S. Representative":
        return None
    m = re.fullmatch(r"congressional district (\d+)", (district or "").strip().lower())
    if not m:
        raise SystemExit(f"Washington: a U.S. Representative row names a district that is not read ({district!r})")
    return house_id("WA", int(m.group(1)))


def grid_rows(page):
    """Every row of one page of the grid, the kept columns only."""
    heads = [text(h) for h in re.findall(r'<th[^>]*class="rgHeader[^"]*"[^>]*>(.*?)</th>', page, re.S)]
    if not all(k in heads for k in KEEP) or len(set(heads)) != len(heads):
        raise SystemExit(f"Washington: the candidate grid's columns changed ({[h for h in heads if h in KEEP]})")
    idx = {k: heads.index(k) for k in KEEP}
    for tr in re.findall(r'<tr class="(?:rgRow|rgAltRow)"[^>]*>(.*?)</tr>', page, re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        if len(cells) != len(heads):
            raise SystemExit("Washington: a grid row does not line up with the grid's headings")
        yield {k: text(cells[i]) for k, i in idx.items()}


def text(cell):
    return re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", "", cell)).replace("\xa0", " ")).strip()


def form(page):
    """The form's hidden fields and lists as a browser posts them: a list with no option marked selected sends its
    first option (the language list here; the server answers an empty one with its error page)."""
    fields = {}
    for tag in re.findall(r'<input[^>]*type="hidden"[^>]*>', page):
        name, value = re.search(r'name="([^"]+)"', tag), re.search(r'value="([^"]*)"', tag)
        if name:
            fields[name.group(1)] = H.unescape(value.group(1)) if value else ""
    for name, body in re.findall(r'<select[^>]*name="([^"]+)"[^>]*>(.*?)</select>', page, re.S):
        chosen = re.search(r'<option selected="selected" value="([^"]*)"', body) or re.search(r'<option[^>]*value="([^"]*)"', body)
        fields[name] = chosen.group(1) if chosen else ""
    return fields


def read_list(kind, path, say):
    """The federal rows of one list, every page read; kept on disk (kept columns only) for two days."""
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < 2 * 86400:
        return json.load(open(path, encoding="utf-8"))
    eid, title = LISTS[kind]
    url = LIST_URL + eid
    page = net.get(url, accept="text/html").decode("utf-8", "replace")
    if not re.search(rf"<title>\s*{title} Candidate List\s*</title>", page):
        raise SystemExit(f"Washington: {url} is no longer the {title} Candidate List")
    m = re.search(r"<strong>(\d+)</strong>\s*items in\s*<strong>(\d+)</strong>", page)
    if not m:
        raise SystemExit(f"Washington: the {title} list no longer shows its row count")
    items, pages = int(m.group(1)), int(m.group(2))
    rows = list(grid_rows(page))
    for n in range(2, pages + 1):
        # the Next button is a plain submit button on the first page (it posts its own name) and a script button after
        # that (it names itself as the event target), as a browser would send either
        nxt = re.search(r'<input type="(submit|button)" name="([^"]+)" value=" " (?:onclick="javascript:__doPostBack\(&#39;([^&]+)&#39;,'
                        r'&#39;&#39;\)" )?title="Next Page" class="rgPageNext" />', page)
        if not nxt:
            raise SystemExit(f"Washington: page {n - 1} of the {title} list has no Next Page button")
        fields = form(page)
        if nxt.group(1) == "submit":
            fields.update({"__EVENTTARGET": "", "__EVENTARGUMENT": "", nxt.group(2): " "})
        elif nxt.group(3):
            fields.update({"__EVENTTARGET": nxt.group(3), "__EVENTARGUMENT": ""})
        else:
            raise SystemExit(f"Washington: page {n - 1} of the {title} list has a Next Page button that is not read")
        time.sleep(2)
        req = Request(url, data=urllib.parse.urlencode(fields).encode(), method="POST",
                      headers={"User-Agent": net.UA, "Content-Type": "application/x-www-form-urlencoded", "Referer": url})
        with urlopen(req, timeout=120) as r:
            page = r.read().decode("utf-8", "replace")
        cur = re.search(r'class="rgCurrentPage"[^>]*><span>(\d+)</span>', page)
        if not cur or int(cur.group(1)) != n:
            raise SystemExit(f"Washington: asked for page {n} of the {title} list and got {cur.group(1) if cur else 'no page'}")
        rows += list(grid_rows(page))
    if len(rows) != items:
        raise SystemExit(f"Washington: the {title} list counts {items} rows; {len(rows)} were read")
    fed = [r for r in rows if race_of(r["Race"], r["District"])]
    for r in fed:
        if r["Term Type"] != "Regular":
            raise SystemExit(f"Washington: a federal race on the {title} list is not a regular term ({r['District']}, {r['Term Type']})")
    kept = {"title": title, "url": url, "items": items, "rows": fed}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(kept, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    say(f"      {title} Candidate List: {items} rows on {pages} pages, {len(fed)} for Congress")
    return kept


def results_book(folder):
    """The certified primary workbook, found through the results site's own record of the election."""
    info_path = os.path.join(folder, "wa_2026_primary_results_record.json")
    book = os.path.join(folder, "wa_2026_primary_all_results.xlsx")
    if not (os.path.exists(info_path) and os.path.exists(book) and time.time() - os.path.getmtime(info_path) < 30 * 86400):
        rec = json.loads(net.get(API, accept="application/json"))
        if rec.get("electionDate") != PRIMARY:
            raise SystemExit(f"Washington: the results site's election {API} is not the {PRIMARY} primary")
        if rec.get("isOfficialResults") is not True:
            raise SystemExit("Washington: the results site does not mark the August 4 primary's results as official; nothing is loaded")
        blob = next((r["blobName"] for c in rec.get("publicReportCategories") or [] for r in c.get("reports") or []
                     if r.get("reportName") == "All Results Excel"), None)
        if not blob:
            raise SystemExit("Washington: the results site no longer offers its All Results Excel report")
        url = CDN + rec["jurisdictionId"] + "/" + urllib.parse.quote(blob)
        info = {"url": url, "asOf": rec.get("asOf"), "isOfficialResults": rec.get("isOfficialResults"), "name": rec["name"][0]["text"]}
        if os.path.exists(book):
            os.remove(book)
        net.download(url, book, max_age_days=30)
        json.dump(info, open(info_path, "w", encoding="utf-8"), indent=1)
    info = json.load(open(info_path, encoding="utf-8"))
    if open(book, "rb").read(2) != b"PK":
        raise SystemExit(f"Washington: {os.path.basename(book)} is not a workbook; delete it and run again")
    return book, info


def sheet(wb, name, keep):
    it = wb[name].iter_rows(values_only=True)
    heads = [str(c or "").strip() for c in next(it)]
    if not all(k in heads for k in keep):
        raise SystemExit(f"Washington: the {name} sheet's columns changed ({[h for h in heads if h]})")
    idx = {k: heads.index(k) for k in keep}
    for r in it:
        m = OFFICE.fullmatch(str(r[idx["Office Name"]] or "").strip())
        if m:
            yield house_id("WA", int(m.group(1))), {k: r[i] for k, i in idx.items()}


def primary_results(book):
    """{race: {"cands": [(name, party, votes)], "write_in": votes}} from the statewide sheet, with every figure checked
    against the sum of its county rows."""
    wb = openpyxl.load_workbook(book, read_only=True, data_only=True)
    out, state = {}, collections.Counter()
    for race, r in sheet(wb, "Summary Results", BOOK_KEEP):
        name = re.sub(r"\s+", " ", str(r["Ballot Name"] or "")).strip()
        f = out.setdefault(race, {"cands": [], "write_in": 0})
        v = int(r["Total"] or 0)
        if name.lower() in NOT_CANDIDATES:
            continue
        if name.lower().startswith("write-in") or name.lower().startswith("write in"):
            f["write_in"] += v
            state[(race, "write-in")] += v
            continue
        party = str(r["Party"] or "").strip()
        if not party:
            raise SystemExit(f"Washington: a candidate for {race} with no party preference in the results ({name})")
        f["cands"].append((name, party, v))
        state[(race, fold(name))] += v
    counties, byc = set(), collections.Counter()
    for race, r in sheet(wb, "Precinct Results", COUNTY_KEEP):
        name = re.sub(r"\s+", " ", str(r["Ballot Name"] or "")).strip()
        if name.lower() in NOT_CANDIDATES:
            continue
        key = "write-in" if re.match(r"write[- ]in", name, re.I) else fold(name)
        byc[(race, key)] += int(r["Total"] or 0)
        counties.add(str(r["Precinct"]).strip())
    wb.close()
    if byc != state:
        bad = sorted(k for k in set(byc) | set(state) if byc[k] != state[k])
        raise SystemExit(f"Washington: county rows do not add up to the statewide totals for {bad}")
    return out, len(counties)


def short(party):
    """(Prefers Democratic Party) -> DEMOCRATIC; (States No Party Preference) -> STATES NO PARTY PREFERENCE: the lists' form."""
    p = re.sub(r"\s+", " ", party.strip().strip("()")).strip()
    m = re.fullmatch(r"Prefers (.+?) Party", p, re.I)
    return (m.group(1) if m else p).upper()


def load(con, cache, say=print):
    net.patient_lookups()
    folder = os.path.join(cache, "wa")
    gen_path, pri_path = os.path.join(folder, "wa_2026_general_federal.json"), os.path.join(folder, "wa_2026_primary_federal.json")
    gen = read_list("general", gen_path, say)
    pri = read_list("primary", pri_path, say)
    book, info = results_book(folder)
    for _sid, (fname, url, _title) in SCANS.items():
        net.download(url, os.path.join(folder, fname), max_age_days=60)
        if open(os.path.join(folder, fname), "rb").read(4) != b"%PDF":
            raise SystemExit(f"Washington: {fname} is not a PDF; delete it and run again")
    results, counties = primary_results(book)

    # the general list: the November ballot
    listed, off = collections.defaultdict(list), []
    for r in gen["rows"]:
        race = race_of(r["Race"], r["District"])
        if r["Status"] == "Withdrawn":
            off.append(r)
            continue
        if r["Status"] != "Active":
            raise SystemExit(f"Washington: a status on the general list that is not read ({r['Status']!r}, {r['District']})")
        if not r["Ballot Order"].isdigit():
            raise SystemExit(f"Washington: no ballot order on the general list for {r['Name']} ({r['District']})")
        listed[race].append(r)

    # the primary list: who was on the August ballot, and who withdrew before it
    filed, withdrew = collections.defaultdict(dict), []
    for r in pri["rows"]:
        race = race_of(r["Race"], r["District"])
        if r["Status"] == "Withdrawn":
            withdrew.append(f"{r['Name']}, {r['District'].title()}")
        elif r["Status"] == "Active":
            filed[race][fold(r["Name"])] = r
        else:
            raise SystemExit(f"Washington: a status on the primary list that is not read ({r['Status']!r}, {r['District']})")

    races = [x for (x,) in con.execute("SELECT race_id FROM races WHERE state = 'WA' ORDER BY race_id")]
    if set(races) != set(results) or set(races) != set(listed):
        raise SystemExit(f"Washington: the races ({races}) are not the results' ({sorted(results)}) and the general list's ({sorted(listed)})")

    rows, not_listed = [], []
    for race in races:
        field, write_in = results[race]["cands"], results[race]["write_in"]
        if {fold(n) for n, _p, _v in field} != set(filed[race]):
            raise SystemExit(f"Washington: the results' candidates for {race} are not the primary list's Active candidates")
        for name, party, _v in field:
            if short(party) != filed[race][fold(name)]["Party Preference"].upper():
                raise SystemExit(f"Washington: {name}'s party preference differs between the results ({party}) and the primary list")
        ranked = sorted(field, key=lambda c: (-c[2], c[0]))
        second = ranked[1][2] if len(ranked) > 1 else ranked[0][2]
        went = {fold(n) for n, _p, v in ranked if v >= second}
        on_list = {fold(r["Name"]): r for r in listed[race]}
        if set(on_list) - went:
            raise SystemExit(f"Washington: the general list for {race} names someone who did not advance from the primary ({sorted(set(on_list) - went)})")
        total = sum(v for _n, _p, v in field) + write_in
        printed = {fold(n): p.strip().strip("()").strip() for n, p, _v in field}
        for name, party, v in ranked:
            note = None
            if fold(name) in went and fold(name) not in on_list:
                note = "Advanced from the top-two primary, but is not on the Secretary of State's list for the November ballot."
                not_listed.append(f"{name} ({race})")
            shown = party.strip().strip("()").strip()
            rows.append((race, "primary", PRIMARY, name, shown, party_code(shown), None, 0, 0, v,
                         round(100 * v / total, 1) if total else None, "advanced" if fold(name) in went else "lost",
                         None, None, "wa-sos-2026-primary-results", note))
        for r in sorted(listed[race], key=lambda r: int(r["Ballot Order"])):
            shown = printed[fold(r["Name"])]
            if short(shown) != r["Party Preference"].upper():
                raise SystemExit(f"Washington: {r['Name']}'s party preference differs between the general list and the results")
            rows.append((race, "general", "2026-11-03", r["Name"], shown, party_code(shown), int(r["Ballot Order"]), 0, 0,
                         None, None, None, None, None, "wa-sos-2026-general-list", TOP_TWO))

    general = [r for r in rows if r[1] == "general"]
    primary_rows = len(rows) - len(general)
    with con:
        con.execute("DELETE FROM candidates WHERE race_id LIKE '2026-WA-%'")
        con.executemany("INSERT OR REPLACE INTO candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        record_source(con, "wa-sos-2026-general-list", path=gen_path, level="federal", state="WA", kind="official candidate list",
                      agency="Washington Secretary of State", title="GENERAL 2026 Candidate List (November 3, 2026): U.S. Representative",
                      url=gen["url"], rows=len(gen["rows"]),
                      note=f"Every page of the grid read through its own pager ({gen['items']} rows, every office); the kept columns only, "
                           f"mailing addresses, e-mail and phones never read. Ballot order as the list gives it. Withdrawn, left off: {len(off)}. "
                           "Party preferences shown as the ballot prints them, from the primary results; the list's short form checked against them.")
        record_source(con, "wa-sos-2026-primary-list", path=pri_path, level="federal", state="WA", kind="official candidate list",
                      agency="Washington Secretary of State", title="PRIMARY 2026 Candidate List (August 4, 2026): U.S. Representative",
                      url=pri["url"], rows=len(pri["rows"]),
                      note="Used to check the primary results (every Active candidate, and each one's party preference). Withdrawn before "
                           f"the primary, not on its ballot: {'; '.join(withdrew) or 'none'}.")
        record_source(con, "wa-sos-2026-primary-results", path=book, level="federal", state="WA", kind="official results",
                      agency="Washington Secretary of State", title="2026 Primary (August 4, 2026): All Results Excel, certified results",
                      url=info["url"], published=(info.get("asOf") or "")[:10], rows=primary_rows,
                      note=f"Found on the Secretary's results site ({RESULTS_PAGE}), which marks these results official. Top-two primary: "
                           f"each field's total is its candidates' votes plus write-ins (over- and under-votes left out). Every figure checked "
                           f"against the sum of its rows for {counties} counties.")
        for sid, (fname, url, title) in SCANS.items():
            record_source(con, sid, path=os.path.join(folder, fname), level="federal", state="WA", kind="official certification",
                          agency="Washington Secretary of State", title=title, url=url, rows=0,
                          note=f"Posted on {SOS_PAGE}. A scanned image with no text layer: fingerprinted here, not read.")
    fields = len({r[0] for r in rows if r[1] == "primary"})
    say(f"    Washington: {len(races)} House districts, {len(general)} candidates on the November ballot ({len(off)} withdrawn left off); "
        f"{fields} top-two primary fields ({primary_rows} candidates), votes from the certified results, county sums checked"
        + (f"; advanced but not on the November list: {', '.join(not_listed)}" if not_listed else ""))
    return len(general)
