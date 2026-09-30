"""
Rhode Island: the Department of State's candidate list for the November 3, 2026 general election, and the Board of
Elections' official results of the September 9, 2026 party primaries. Rhode Island has two House seats (the 2024 lines)
and the Senate seat of class 2. The primary was held on Wednesday, September 9 (the Department of State's 2026 "Run for
Office" guide and the Board's results both give that date).

  November ballot   the Department of State Elections Division's "Candidates in Upcoming Elections"
                    (vote.sos.ri.gov/Candidates/CandidateSearch, one summary page per office:
                    Candidates/CandidateSearchSummary?OfficeType=...&Election=...). vote.sos.ri.gov, and the Elections
                    pages of www.sos.ri.gov, answer scripts with a Cloudflare challenge; they are never worked around and
                    not asked again. The page for SENATOR IN CONGRESS and the page for REPRESENTATIVE IN CONGRESS, for the
                    November 3, 2026 General Election, saved in a browser (as a web page, or as the spreadsheet or CSV
                    export if the page offers one) into ballot_cache/ri/general/, are read from there. Until they are,
                    no November candidate is stored: the primary winners alone would leave off every independent
                    candidate, and Rhode Island lets a party replace a nominee who withdraws by September 11. The three
                    races then go in list_gaps.
  primary results   the Board of Elections' election results site (electionresults.ri.gov, linked as "September 9, 2026
                    Statewide Primary Results" from elections.ri.gov's Previous Election Results page), which fetches its
                    figures from the site's own data service (results/public/api/elections/RhodeIsland/
                    RI2026StatewidePrimary: the election, marked isOfficialResults; .../data: every contest, every
                    candidate's statewide votes and the same by count group, Election Day, Early Voting and Mail Ballots;
                    .../data/ballot-item/<id>: the same contest town by town). Checked against the Board's "Summary
                    Results Report, OFFICIAL RESULTS, Primary Election 2026" (Prim26_Summary.pdf, from the same page):
                    each candidate's TOTAL and each count group must equal the data service's figures, each contest's
                    Total Votes Cast must equal the sum of its candidates, and the towns must add up to the statewide
                    figures. The Senate contests' Contest Totals must equal the report's "Ballots Cast" for the party.
                    No write-in votes are reported for these contests, so a field's total is the sum of its candidates'
                    votes. The loader stops if the service ever says the results are not official.

The saved candidate list has not yet been seen (2026-09-30), so its reader takes columns only by these headings, and
reads nothing else in a row: the candidate's name, the party (or "political principle", Rhode Island's word for what an
independent candidate may print beneath the name), the office, the district, the status and a ballot order. Any other
column (addresses, telephones, e-mail, websites, committees) is dropped as each row is read and never kept or printed.
When a page gives the office or the district only in its heading ("Candidates for REPRESENTATIVE IN CONGRESS", a
"District 1" line above its rows), the heading is read. A status the reader does not know stops the loader and names
it; a candidate marked withdrawn, not qualified, disqualified or defeated in the primary is left off and counted. A list
with no status column is read only when its heading says it is the general election list. Ballot order is the list's
own order unless the list gives a position (Rhode Island draws the order of the parties, and of the independents
beneath them, by lottery on July 17). The Board registers voters as Democrat, Republican or nonpartisan only (the
primary report's own rows), so only those two parties' nominees stand as party candidates; anyone else is an
independent candidate whose "political principle" (or the word Independent) is printed beneath the name, and is shown
with that label and the independent colour. Names are shown as printed; a name in capitals is shown in ordinary
capitals and a name written "Last, First" turned round, and the row says so.

Primary ballots mark the candidate the party endorsed with an asterisk (*) and print that candidate first (the guide,
page 16); the results carry the asterisk too ("John F. Reed*"). It is taken off the name and said in the row's note.
Parties are shown as the Board prints them, in ordinary capitals: DEMOCRAT and REPUBLICAN as Democrat and Republican.
An unopposed party candidate for federal office is printed on the primary ballot and is the nominee without a contest;
a field is a party primary with two candidates or more (in 2026 the Democratic Senate primary and the Republican
primary in District 2). The nominee is the leader, who must be the party's candidate on the November list.
"""

import csv
import html as H
import io
import json
import os
import re
import time

from ballot.common import fold, house_id, party_code, record_source, senate_id
from ballot.lists.tx import proper
from ballot.pdftext import lines as pdf_lines
from states import net

PRIMARY = "2026-09-09"
BOARD_PAGE = "https://elections.ri.gov/elections/previous-election-results"
SITE = "https://electionresults.ri.gov/results/public/RhodeIsland/elections/RI2026StatewidePrimary"
API = "https://electionresults.ri.gov/results/public/api/elections/RhodeIsland/RI2026StatewidePrimary"
SUMMARY_PDF = "https://elections.ri.gov/sites/g/files/xkgbur756/files/2026-09/Prim26_Summary.pdf"
SOS_PAGE = "https://vote.sos.ri.gov/Candidates/CandidateSearch"
SENATE = senate_id("RI", 2)
RACES = (house_id("RI", 1), house_id("RI", 2), SENATE)
CODE = {"DEM": "DEM", "REP": "REP"}
CONTEST = re.compile(r"^(DEM|REP) (Senator in Congress|Representative in Congress District ([12]))$")
ENDORSED = "Endorsed by the party: the primary ballot and the results mark the endorsed candidate with an asterisk (*)."
CAPS_NOTE = "Rhode Island's list prints names in capitals; they are shown here in ordinary capitals."
TURNED = "The list writes the name last name first; it is shown here first name first."
WRITE_IN = "Write-in candidate: the name is not printed on the ballot."
GAP = ("Rhode Island's Department of State publishes its candidate list on a site that turns away scripts, "
       "so the list waits for a copy saved by hand")

# the saved list's columns: taken by heading, and nothing else in a row is read
HEADS = {
    "name": ("candidate", "candidate name", "candidates", "name", "name on ballot", "ballot name", "candidate ballot name"),
    "party": ("party", "political party", "party affiliation", "affiliation", "party or political principle",
              "party political principle", "political principle", "party principle"),
    "office": ("office", "office name", "office sought", "office title", "title of office", "contest"),
    "district": ("district", "district name", "congressional district", "dist"),
    "status": ("status", "candidate status", "certification status", "ballot status", "qualification status"),
    "order": ("ballot order", "ballot position", "position on ballot", "order"),
}
GONE = re.compile(r"withdr|not qualif|did not|disqual|insufficient|failed|lost|defeat|removed|deceased|declin|ineligible|rejected", re.I)
ON = re.compile(r"qualif|certif|nominee|nominated|on ballot|ballot placement|active|endorsed", re.I)
PARTY_WORDS = {"DEM": "Democrat", "D": "Democrat", "REP": "Republican", "R": "Republican", "IND": "Independent",
               "I": "Independent", "LIB": "Libertarian", "GRN": "Green", "MOD": "Moderate"}


def squash(text):
    return re.sub(r"\s+", " ", (text or "").replace("\xa0", " ")).strip()


def ordinary(text):
    """DEMOCRAT -> Democrat; a party word written in capitals shown in ordinary capitals."""
    t = squash(text)
    return t.title() if t.isupper() else t


def get_json(url):
    raw = net.get(url, timeout=120, accept="application/json")
    if raw.lstrip()[:1] != b"{":
        raise SystemExit(f"Rhode Island: {url} did not answer with the results service's data")
    time.sleep(1.0)
    return json.loads(raw)


def text_of(field):
    if isinstance(field, list):
        for t in field:
            if t.get("languageId") in ("en", None):
                return squash(t.get("text"))
        return squash(field[0].get("text")) if field else ""
    return squash(field)


# ---------------------------------------------------------------- the primary: the Board's official results

def fetch_results(say):
    """The Congress contests of the September 9 primary, from the Board's results service: kept as JSON (figures only)."""
    election = get_json(API)
    if not election.get("isOfficialResults"):
        raise SystemExit("Rhode Island: the Board's results service does not mark the 2026 primary's results official")
    if election.get("electionDate") != PRIMARY:
        raise SystemExit(f"Rhode Island: the results service dates the primary {election.get('electionDate')}, not {PRIMARY}")
    data = get_json(API + "/data")
    contests = []
    for item in data["ballotItems"]:
        title = text_of(item["name"])
        m = CONTEST.match(title)
        if not m:
            if re.search(r"in Congress", title, re.I):
                raise SystemExit(f"Rhode Island: a Congress contest in the results that is not read ({title!r})")
            continue
        code = m.group(1)
        race = SENATE if m.group(3) is None else house_id("RI", int(m.group(3)))
        cands = []
        for o in item["summaryResults"]["ballotOptions"]:
            party = o.get("party") or {}
            if (party.get("abbreviation") or code) != code:
                raise SystemExit(f"Rhode Island: {text_of(o['name'])} in {title} carries the party {party.get('abbreviation')!r}")
            cands.append({"name": text_of(o["name"]), "votes": int(o["voteCount"]), "write_in": bool(o.get("isWriteIn")),
                          "party": text_of(party.get("name")) or code,
                          "groups": {text_of(g["groupName"]): int(g["voteCount"]) for g in (o.get("groupResults") or [])}})
        status = item.get("reportingStatus") or {}
        detail = get_json(f"{API}/data/ballot-item/{item['id']}")["ballotItemWithBreakdown"]
        towns = {}
        for b in detail["breakdownResults"]:
            town = text_of(b["locality"]["name"])
            towns[town] = {text_of(o["name"]): int(o["voteCount"]) for o in b["ballotOptions"]}
        contests.append({"title": title, "code": code, "race": race, "vote_total": item.get("voteTotal"),
                         "units": [status.get("reportingUnits"), status.get("totalUnits")], "candidates": cands, "towns": towns})
    if len(contests) != 6:
        raise SystemExit(f"Rhode Island: {len(contests)} Congress contests in the primary results, not six (two parties, three races)")
    say(f"      results service: {len(contests)} Congress contests, town by town")
    return {"name": text_of(election.get("name")), "date": election.get("electionDate"), "official": election.get("isOfficialResults"),
            "as_of": election.get("asOf"), "last_updated": election.get("lastUpdated"), "contests": contests}


def summary_report(path):
    """{title: {"cands": [(name, total, [groups])], "cast": n, "contest": n}} and the report's Ballots Cast by party."""
    out, cast, head, cur, date = {}, {}, [], None, ""
    for page, _y, text in pdf_lines(path):
        t = squash(text)
        if page == 1 and len(head) < 3:
            head.append(t)
        m = re.match(r"^Election Summary - (\d\d)/(\d\d)/(\d{4})", t)
        if m and not date:
            date = f"{m.group(3)}-{m.group(1)}-{m.group(2)}"
        m = re.match(r"^Ballots Cast - (DEMOCRAT|REPUBLICAN) ([\d,]+)", t)
        if m:
            cast[m.group(1)] = int(m.group(2).replace(",", ""))
        if CONTEST.match(t):
            cur = out.setdefault(t, {"cands": [], "cast": None, "contest": None})
            continue
        if cur is None:
            continue
        m = re.match(r"^(Total Votes Cast|Contest Totals) ([\d,]+) [\d.]+%", t)
        if m:
            cur["cast" if m.group(1) == "Total Votes Cast" else "contest"] = int(m.group(2).replace(",", ""))
            if m.group(1) == "Contest Totals":
                cur = None
            continue
        m = re.match(r"^(.+?) ([\d,]+) [\d.]+% ([\d,]+) ([\d,]+) ([\d,]+)$", t)
        if m and not re.match(r"^(Overvotes|Undervotes|Precincts)", t):
            cur["cands"].append((m.group(1), int(m.group(2).replace(",", "")), [int(m.group(k).replace(",", "")) for k in (3, 4, 5)]))
    if not any("OFFICIAL RESULTS" in h for h in head):
        raise SystemExit(f"Rhode Island: {os.path.basename(path)} is not headed OFFICIAL RESULTS")
    return out, cast, date


def same_name(pdf_name, name):
    """The report's font turns a letter such as the n with a tilde into a replacement mark; match it as any letter."""
    pattern = "".join("." if c == "�" else re.escape(c) for c in pdf_name)
    return re.fullmatch(pattern, name) is not None


def check_results(results, report, cast):
    checked = 0
    for c in results["contests"]:
        rep = report.get(c["title"])
        if rep is None:
            raise SystemExit(f"Rhode Island: the summary report has no {c['title']} contest")
        if len(rep["cands"]) != len(c["candidates"]):
            raise SystemExit(f"Rhode Island: {c['title']}: the report lists {len(rep['cands'])} candidates, the results service {len(c['candidates'])}")
        total = sum(x["votes"] for x in c["candidates"])
        if rep["cast"] != total or c["vote_total"] != total:
            raise SystemExit(f"Rhode Island: {c['title']}: Total Votes Cast {rep['cast']}, service total {c['vote_total']}, candidates sum to {total}")
        for x in c["candidates"]:
            hit = [r for r in rep["cands"] if same_name(r[0], x["name"])]
            if len(hit) != 1 or hit[0][1] != x["votes"]:
                raise SystemExit(f"Rhode Island: {c['title']}: {x['name']} has {x['votes']} votes in the results service and "
                                 f"{hit[0][1] if hit else 'no line'} in the summary report")
            groups = [x["groups"].get(g) for g in ("Election Day", "Early Voting", "Mail Ballots")]
            if groups != hit[0][2] or sum(groups) != x["votes"]:
                raise SystemExit(f"Rhode Island: {c['title']}: {x['name']}'s Election Day, Early Voting and Mail Ballots votes do not agree")
            towns = sum(t.get(x["name"], 0) for t in c["towns"].values())
            if towns != x["votes"]:
                raise SystemExit(f"Rhode Island: {c['title']}: {x['name']}'s towns add up to {towns}, not {x['votes']}")
            checked += 1
        if c["units"][0] != c["units"][1]:
            raise SystemExit(f"Rhode Island: {c['title']}: {c['units'][0]} of {c['units'][1]} towns reported")
        if c["race"] == SENATE:
            word = {"DEM": "DEMOCRAT", "REP": "REPUBLICAN"}[c["code"]]
            if rep["contest"] != cast.get(word):
                raise SystemExit(f"Rhode Island: {c['title']}: Contest Totals {rep['contest']} is not the report's Ballots Cast - {word} {cast.get(word)}")
    return checked


# ---------------------------------------------------------------- the November list: pages saved from vote.sos.ri.gov

def column_map(cells):
    """{field: index} for a heading row, or None when it names no candidate column."""
    idx = {}
    for i, c in enumerate(cells):
        h = " ".join(fold(c).split())                                  # "Party/Political Principle" -> "party political principle"
        for field, names in HEADS.items():
            if h in names and field not in idx:
                idx[field] = i
    return idx if "name" in idx else None


SENATE_WORDS = re.compile(r"senat\w* in congress|united states senat|u\.?\s?s\.? senat", re.I)
HOUSE_WORDS = re.compile(r"representative in congress|u\.?\s?s\.? (house|representative)|house of representatives", re.I)


def office_race(office, district):
    """The race a saved row is for, from its office (and district) words; None for any other office."""
    o = squash(f"{office} {district}")
    if SENATE_WORDS.search(o):
        return SENATE
    if HOUSE_WORDS.search(o):
        m = re.search(r"(?:district|dist\.?)\s*(?:no\.?\s*)?0?([12])\b|\b0?([12])(?:st|nd)\b", o, re.I)
        if not m:
            raise SystemExit(f"Rhode Island: a saved Representative in Congress row gives no district ({squash(office)!r}, {squash(district)!r})")
        return house_id("RI", int(m.group(1) or m.group(2)))
    return None


def html_rows(raw):
    """(context, cells) for every table row of a saved page, the context being the page title and the headings above it;
    and every heading on the page."""
    text = raw.decode("utf-8", "replace")
    title = re.search(r"<title[^>]*>(.*?)</title>", text, re.S | re.I)
    context = [squash(H.unescape(re.sub(r"<[^>]+>", " ", title.group(1))))] if title else []
    out = []
    for m in re.finditer(r"<(h[1-4]|caption)[^>]*>(.*?)</(?:h[1-4]|caption)>|<tr[^>]*>(.*?)</tr>", text, re.S | re.I):
        if m.group(1):
            context.append(squash(H.unescape(re.sub(r"<[^>]+>", " ", m.group(2)))))
            continue
        cells = [squash(H.unescape(re.sub(r"<[^>]+>", " ", c)))
                 for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", m.group(3), re.S | re.I)]
        out.append((context[:1] + context[1:][-3:], cells))
    return context, out


def sheet_rows(path):
    raw = open(path, "rb").read()
    if raw[:2] == b"PK":
        import openpyxl
        book = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
        for ws in book.worksheets:
            for r in ws.iter_rows(values_only=True):
                yield [squash("" if v is None else str(v)) for v in r]
        return
    for enc in ("utf-8-sig", "cp1252"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    for r in csv.reader(io.StringIO(text)):
        yield [squash(c) for c in r]


def saved_list(folder):
    """Every candidate for Congress on the pages saved from vote.sos.ri.gov: only the allowlisted columns are kept."""
    files = sorted(os.path.join(folder, f) for f in os.listdir(folder)
                   if f.lower().endswith((".html", ".htm", ".csv", ".xlsx"))) if os.path.isdir(folder) else []
    rows, headings = [], []
    for path in files:
        if path.lower().endswith((".html", ".htm")):
            title, table = html_rows(open(path, "rb").read())
            headings += title
        else:
            table = [([os.path.basename(path)], cells) for cells in sheet_rows(path)]
        idx, band = None, ""
        for context, cells in table:
            found = column_map(cells)
            if found:
                idx, band = found, ""
                continue
            if idx is None or not any(cells):
                continue
            filled = [c for c in cells if c]
            if len(filled) == 1 and re.search(r"\bdistrict\b|in congress|senat", filled[0], re.I):
                band = filled[0]                                        # a heading row across the table: "Congressional District 1"
                continue
            if len(cells) <= max(idx.values()):
                continue
            row = {f: cells[i] for f, i in idx.items()}                 # the allowlisted cells only; the rest of the row is dropped here
            office = row.get("office") or next((t for t in [band] + context[::-1] if SENATE_WORDS.search(t) or HOUSE_WORDS.search(t)), "")
            district = row.get("district") or (band if re.search(r"district", band, re.I) else "")
            if district.isdigit():
                district = f"District {district}"
            race = office_race(office, district)
            if race is None or not row["name"]:
                continue
            rows.append({"race": race, "name": row["name"], "party": row.get("party", ""), "status": row.get("status"),
                         "order": row.get("order", ""), "file": os.path.basename(path)})
    return files, rows, headings


def shown(name):
    """The name as printed, first name first, in ordinary capitals; and the notes that say what was changed."""
    notes, n = [], squash(name)
    head, comma, tail = n.partition(",")
    if comma and tail.strip() and not re.fullmatch(r"\s*(jr|sr|ii|iii|iv)\.?\s*", tail, re.I):
        n = squash(f"{tail} {head}")
        notes.append(TURNED)
    if re.search(r"[A-Z]{2}", n) and n == n.upper():
        n = proper(n)
        notes.append(CAPS_NOTE)
    return n, notes


# ---------------------------------------------------------------- load

def load(con, cache, say=print):
    net.patient_lookups()
    folder = os.path.join(cache, "ri")
    os.makedirs(folder, exist_ok=True)

    # the primary
    rpath = os.path.join(folder, "ri_2026_primary_congress.json")
    if os.path.exists(rpath) and time.time() - os.path.getmtime(rpath) < 30 * 86400:
        results = json.load(open(rpath, encoding="utf-8"))
    else:
        results = fetch_results(say)
        json.dump(results, open(rpath, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    ppath = os.path.join(folder, "Prim26_Summary.pdf")
    net.download(SUMMARY_PDF, ppath, max_age_days=30, say=say)
    if open(ppath, "rb").read(5) != b"%PDF-":
        raise SystemExit("Rhode Island: Prim26_Summary.pdf is not a PDF")
    report, cast, printed = summary_report(ppath)
    checked = check_results(results, report, cast)

    # the November list, if a copy has been saved
    gfolder = os.path.join(folder, "general")
    gfiles, glist, headings = saved_list(gfolder)
    rows, off, unknown, write_ins, order, nominee = [], [], set(), [], {}, {}
    has_status = any(r["status"] is not None for r in glist)
    if glist and not has_status and not any(re.search(r"general", h, re.I) for h in headings):
        raise SystemExit("Rhode Island: the saved candidate list has no status column and its heading does not say it is the "
                         "general election list; save the page that shows each candidate's status")
    seen = set()
    for r in glist:
        status = squash(r["status"] or "")
        if status and GONE.search(status):
            off.append(f"{r['name']} ({r['race']}, {status})")
            continue
        if status and not ON.search(status):
            unknown.add(status)
            continue
        name, notes = shown(r["name"])
        party = PARTY_WORDS.get(squash(r["party"]).upper(), ordinary(r["party"])) or "Independent"
        write_in = int(bool(re.search(r"write", f"{r['party']} {status}", re.I)))
        if (r["race"], fold(name)) in seen:
            continue                                  # the same candidate on two saved pages
        seen.add((r["race"], fold(name)))
        if write_in:
            write_ins.append(name)
            notes.append(WRITE_IN)
            place = None
        else:
            order[r["race"]] = order.get(r["race"], 0) + 1
            place = int(r["order"]) if str(r["order"]).isdigit() else order[r["race"]]
        if party_code(party) in "DR" and not write_in:
            if (r["race"], party_code(party)) in nominee:
                raise SystemExit(f"Rhode Island: the saved list prints two {party} candidates for {r['race']}; save the general election list")
            nominee[(r["race"], party_code(party))] = fold(name)
        code = "W" if write_in else party_code(party)
        if code == "O":
            code = "I"                                # not a recognised party's nominee: an independent candidate's "political principle"
        rows.append((r["race"], "general", "2026-11-03", name, party, code, place, 0, write_in,
                     None, None, None, None, None, "ri-sos-2026-general-list", " ".join(notes) or None))
    if unknown:
        raise SystemExit(f"Rhode Island: statuses on the saved candidate list that are not read: {sorted(unknown)}")

    # the primary fields
    fields, not_on = 0, []
    for c in results["contests"]:
        cands = [x for x in c["candidates"] if not x["write_in"]]
        if len(cands) < 2:
            continue
        fields += 1
        total = sum(x["votes"] for x in c["candidates"])
        top = sorted(c["candidates"], key=lambda x: -x["votes"])
        if top[0]["votes"] == top[1]["votes"]:
            raise SystemExit(f"Rhode Island: {c['title']} is tied at the top; the loader does not decide a tie")
        for x in c["candidates"]:
            won = x is top[0]
            name = x["name"].rstrip("*").strip()
            party = ordinary(x["party"])
            notes = [ENDORSED] if x["name"].endswith("*") else []
            if x["write_in"]:
                notes.append(WRITE_IN)
            if won and glist:
                listed = nominee.get((c["race"], party_code(party)))
                if listed is None:
                    notes.append("Won the primary but is not on the November list.")
                    not_on.append(f"{name} ({c['race']})")
                elif fold(name).split()[-1] != listed.split()[-1]:
                    notes.append("Won the primary; the November list names another candidate for the party.")
                    not_on.append(f"{name} ({c['race']})")
            rows.append((c["race"], f"primary-{CODE[c['code']]}", PRIMARY, name, "Write-in" if x["write_in"] else party,
                         "W" if x["write_in"] else party_code(party), None, 0, int(x["write_in"]), x["votes"],
                         round(100 * x["votes"] / total, 1) if total else None, "advanced" if won else "lost", None, None,
                         "ri-boe-2026-primary-results", " ".join(notes) or None))

    listed_races = {r[0] for r in rows if r[1] == "general"}
    gaps = [(race, GAP if not glist else "the saved candidate list does not carry this race") for race in RACES if race not in listed_races]
    general_rows = [r for r in rows if r[1] == "general"]
    with con:
        con.execute("DELETE FROM candidates WHERE race_id LIKE '2026-RI-%'")
        con.execute("DELETE FROM list_gaps WHERE state = 'RI'")
        con.executemany("INSERT OR REPLACE INTO candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        con.executemany("INSERT OR REPLACE INTO list_gaps VALUES (?, 'RI', ?)", gaps)
        if glist:
            record_source(con, "ri-sos-2026-general-list", path=gfiles[0], level="federal", state="RI", kind="official candidate list",
                          agency="Rhode Island Department of State, Elections Division",
                          title="Candidates in Upcoming Elections: Senator in Congress and Representative in Congress, November 3, 2026 General Election",
                          url=SOS_PAGE, rows=len(glist),
                          note=f"Saved in a browser (vote.sos.ri.gov answers scripts with a Cloudflare challenge): "
                               f"{', '.join(os.path.basename(f) for f in gfiles)}. Only the name, party, office, district, status and ballot "
                               f"order columns read; addresses, telephones, e-mail and websites never read. Ballot order is the list's own "
                               f"unless it gives one. Withdrawn, not qualified or defeated, left off: {len(off)} ({'; '.join(off) or 'none'}). "
                               f"Write-in candidates listed: {len(write_ins)}.")
        record_source(con, "ri-boe-2026-primary-results", path=rpath, level="federal", state="RI", kind="official results",
                      agency="Rhode Island Board of Elections",
                      title=f"{results['name']} (September 9, 2026): official results, Senator in Congress and Representative in Congress",
                      url=SITE, published=(results.get("last_updated") or "")[:10], rows=sum(len(c["candidates"]) for c in results["contests"]),
                      note="From the Board's election results site's data service (marked isOfficialResults), statewide and town by town; "
                           f"every town sum and count group checked ({checked} candidates). No write-in votes are reported for these "
                           "contests, so a field's total is the sum of its candidates' votes. The asterisk the results print after the "
                           "party-endorsed candidate's name is taken off and said in the note.")
        record_source(con, "ri-boe-2026-primary-summary", path=ppath, level="federal", state="RI", kind="official results",
                      agency="Rhode Island Board of Elections",
                      title="Summary Results Report, OFFICIAL RESULTS, Primary Election 2026, September 9, 2026 (Prim26_Summary.pdf)",
                      url=SUMMARY_PDF, published=printed, rows=sum(len(v["cands"]) for v in report.values()),
                      note="Control: each Congress candidate's TOTAL, Election Day, Early Voting and Mail Ballots votes equal the results "
                           "service's; Total Votes Cast equals the sum of the candidates; the Senate contests' Contest Totals equal the "
                           "report's Ballots Cast for the party.")
    if glist:
        houses = sum(1 for race in listed_races if "-H" in race)
        say(f"    Rhode Island: {houses} House {'district' if houses == 1 else 'districts'} and {'the' if SENATE in listed_races else 'no'} "
            f"Senate race, {len(general_rows)} candidates on the November ballot "
            f"({len(off)} withdrawn, not qualified or defeated left off); {fields} party primaries with a field, votes from the "
            f"official results, towns and summary report checked"
            + (f"; primary winners not on the November list: {', '.join(not_on)}" if not_on else ""))
    else:
        say(f"    Rhode Island: the November list is not loaded: the Department of State's candidate pages (vote.sos.ri.gov) answer "
            f"scripts with a Cloudflare challenge; save its Senator in Congress and Representative in Congress pages into {gfolder}. "
            f"{fields} party primaries with a field stored, votes from the official results, towns and summary report checked; "
            f"{len(gaps)} races in list_gaps")
    return len(general_rows)
