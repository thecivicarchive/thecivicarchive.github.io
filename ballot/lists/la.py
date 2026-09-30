"""
Louisiana: the Secretary of State's Candidate Inquiry and its official election results, both on voterportal.sos.la.gov.

How Louisiana votes for Congress in 2026 (the Secretary's notice "Details for U.S. House races in fall finalized", May
14, 2026, www.sos.la.gov/media/dcvl5ojl/051426-fall-house-races.pdf, and the qualifying page, which cites Act 7 of the
2026 Regular Session):
  - U.S. Senate: a closed party primary on May 16, a party primary runoff on June 27, and the general election on
    November 3 between the parties' nominees (and anyone nominated by petition; nobody was).
  - U.S. House: the May 16 and June 27 party primaries for the House were cancelled after the Supreme Court's ruling
    and the new map (votes cast in them are void and were never released). Under Act 7 the House is not a closed
    party office this year: every candidate, of every party or none, is on the November 3 open primary ballot. A
    candidate with more than half the votes is elected; otherwise the top two meet in the general election on
    December 12. Qualifying was August 5 to 7.
So the November 3 ballot holds the Senate's general election and the House's open primary. The House rows are stored
as election "open-primary", dated 2026-11-03, with no votes and no outcome until the official results are posted;
the Senate's as "general". A House general election on December 12 is stored as "general", dated 2026-12-12, once
the Candidate Inquiry lists its candidates (it lists none for Congress yet).

The lists: the Candidate Inquiry (voterportal.sos.la.gov/candidateinquiry, linked as "Candidate Inquiry page" and
"Search for candidates" from sos.la.gov) is a page that asks the portal for the offices of the chosen election
(CandidateInquiry/StatewideCandidate/OfficeList?electionId=) and then posts the chosen offices' ids to
CandidateInquiry/StatewideCandidate/CandidateList. Election ids are read from the page's own Election Date list. The
answer is HTML: under each office, its title and "1 to be elected", a heading row (Name/Address/Phone, Filed Date,
Party/Race/Gender), and one block per candidate. Only these are read: the office title, the first line of the
Name/Address/Phone column (the name as it is printed on the ballot, nicknames in quotation marks), the first line of
the Party/Race/Gender column (the party, checked against the block's own "Party" label), and the status cell (empty,
"Advances", or a word such as Withdrawn). The address, telephone, e-mail, race and gender are never read; the filing
date is neither kept nor used; the cached copy keeps only the office, name, party and status. A candidate whose status says withdrawn, disqualified, deceased or
removed is left off and counted. The list names no ballot position; Louisiana's ballot lists each office's candidates
alphabetically by surname (R.S. 18:551(C)), and so does the list, so its order is kept as the ballot order (checked,
and any break reported). Parties are printed in full ("Republican", "Democrat", "Libertarian", "No Party") and kept
as printed. Louisiana has no write-in candidates.

The Senate primaries: the portal's official results (the "Graphical election results" site, voterportal.sos.la.gov/
graphical, which reads ElectionResults/ElectionResults/Data?blob=<yyyymmdd>/RacesCandidates_Multiparish.htm for the
races and choices and .../Votes_Multiparish.htm for the votes; ElectionDates.htm says whether an election's results
are official). Only elections marked ResultsOfficial 1 are read: unofficial election-night figures are never stored.
Each federal race's statewide votes are checked against its parish file (csv/ByParish_<race>.csv, columns by the
candidates' names; all 64 parishes for the Senate) and every precinct and absentee count must have reported. The candidates of each
race must be the Candidate Inquiry's for that election and office. A Louisiana primary needs more than half the vote;
the portal marks each choice Runoff, Advances, Elected or Defeated. The two in a runoff are both stored "advanced",
with a note; the runoff's winner must be the party's nominee on the November list. No write-ins, so a field's total is
its candidates' votes. When the November 3 results are official, the House open primary's votes and outcomes are read
the same way ("elected" for a candidate with more than half the votes, "advanced" for the two going on to December 12).
Both hosts answer scripts.
"""

import csv
import html as H
import io
import json
import os
import re
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ballot.common import fold, house_id, name_parts, party_code, record_source, senate_id
from states import net

PORTAL = "https://voterportal.sos.la.gov"
INQUIRY = PORTAL + "/candidateinquiry"
OFFICE_LIST = PORTAL + "/CandidateInquiry/StatewideCandidate/OfficeList?electionId="
CANDIDATE_LIST = PORTAL + "/CandidateInquiry/StatewideCandidate/CandidateList"
RESULTS = PORTAL + "/graphical"
DATA = PORTAL + "/ElectionResults/ElectionResults/Data?blob="
NOTICE = "https://www.sos.la.gov/media/dcvl5ojl/051426-fall-house-races.pdf"
NOV, DEC, PRIMARY, RUNOFF = "11/03/2026", "12/12/2026", "05/16/2026", "06/27/2026"
ISO = {NOV: "2026-11-03", DEC: "2026-12-12", PRIMARY: "2026-05-16", RUNOFF: "2026-06-27"}
HEADINGS = ("Name/Address/Phone", "Filed Date", "Party/Race/Gender")
PARTY_CODE = {"Democratic Party": "DEM", "Republican Party": "REP"}            # a closed party primary's party
RESULT_PARTY = r"(?:DEM|REP|LBT|LIB|GRN|NOPTY|OTHER|IND|[A-Z]{2,6})"          # the portal's abbreviation after a name
GONE = re.compile(r"withdr|disqualif|deceas|remov|died", re.I)
ON_BALLOT = {"", "Advances", "Runoff", "Elected", "Defeated"}
PARISHES = 64
OPEN_PRIMARY = ("On the November 3 ballot: Louisiana's open primary for the U.S. House, every candidate of every party on one "
                "ballot. More than half the votes wins the seat; otherwise the top two meet in the general election on December 12.")
DECEMBER = "The general election for this seat is on December 12: no candidate won more than half the votes on November 3."
TO_RUNOFF = "Went on to the party's runoff on June 27: no candidate won more than half the votes."
TO_DECEMBER = "Goes on to the general election on December 12: no candidate won more than half the votes."
NOT_ON_LIST = "Won the runoff, but is not on the November list for this party."


# ---------- the Candidate Inquiry ----------

def text_of(cell):
    return re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", cell)).replace("\xa0", " ")).strip()


def post(url, fields):
    req = Request(url, data=urlencode(fields).encode(), method="POST",
                  headers={"User-Agent": net.UA, "Accept": "text/html, */*", "Content-Type": "application/x-www-form-urlencoded",
                           "X-Requested-With": "XMLHttpRequest"})
    with urlopen(req, timeout=120) as r:
        return r.read().decode("utf-8", "replace")


def election_ids(page):
    """{"11/03/2026": "344", ...} from the Candidate Inquiry's Election Date list."""
    sel = re.search(r'<select[^>]*id="ElectionId"[^>]*>(.*?)</select>', page, re.S)
    if not sel:
        raise SystemExit("Louisiana: the Candidate Inquiry page has no Election Date list")
    return {text_of(d): v for v, d in re.findall(r'<option[^>]*value="(\d+)"[^>]*>(.*?)</option>', sel.group(1), re.S)}


def offices(page):
    """[(office id, title)] from an election's office list."""
    return [(i, text_of(t)) for i, t in re.findall(r'<input type="checkbox" id="cb_(\d+)"\s*/>\s*([^<]+)</label>', page)]


def candidate_list(page, where):
    """[{"office", "to_elect", "candidates": [{"name", "party", "status"}]}] from a CandidateList answer: only the
    office title, the first line of the name and party columns, and the status cell are read."""
    page = re.sub(r"<script.*?</script>|<style.*?</style>", "", page, flags=re.S)
    marks = sorted([(m.start(), "office") for m in re.finditer(r'<span class="office-title">', page)]
                   + [(m.start(), "head") for m in re.finditer(r'class="row candidate-header-row', page)]
                   + [(m.start(), "cand") for m in re.finditer(r'class="row candidate-row candidate-top-row"', page)])
    out = []
    for k, (pos, kind) in enumerate(marks):
        seg = page[pos:marks[k + 1][0] if k + 1 < len(marks) else len(page)]
        if kind == "office":
            title = text_of(re.match(r'<span class="office-title">(.*?)</span>', seg, re.S).group(1))
            n = re.search(r"<strong>(\d+) to be elected</strong>", seg)
            out.append({"office": title, "to_elect": int(n.group(1)) if n else None, "candidates": []})
            continue
        if not out:
            raise SystemExit(f"Louisiana: the Candidate Inquiry list for {where} has rows before any office title")
        if kind == "head":
            heads = tuple(text_of(b) for b in re.findall(r"<b>(.*?)</b>", seg, re.S))
            if heads != HEADINGS:
                raise SystemExit(f"Louisiana: the Candidate Inquiry's columns for {out[-1]['office']} are {heads}, not {HEADINGS}")
            out[-1]["headed"] = True
            continue
        if not out[-1].get("headed"):
            raise SystemExit(f"Louisiana: a candidate under {out[-1]['office']} comes before the column headings")
        top = seg.split('<div class="row candidate-row">', 1)[0]            # the first line of each column
        cells = re.findall(r'<div class="col-[^"]*">(.*?)</div>', top, re.S)
        if len(cells) != len(HEADINGS):
            raise SystemExit(f"Louisiana: a candidate's first line under {out[-1]['office']} has {len(cells)} cells, not {len(HEADINGS)}")
        name = text_of(re.sub(r'<span class="visible-xs">.*?</span>', " ", cells[0], flags=re.S))
        party = text_of(cells[2])
        labelled = [text_of(v) for lab, v in re.findall(r"<strong[^>]*>(.*?)</strong>([^<]*)</span>", seg, re.S) if text_of(lab) == "Party"]
        if labelled != [party]:
            raise SystemExit(f"Louisiana: a candidate's party under {out[-1]['office']} is not the same in both places on the list")
        status = re.search(r'<div class="col-xs-3 text-danger">(.*?)</div>', seg, re.S)
        if not name:
            raise SystemExit(f"Louisiana: a candidate under {out[-1]['office']} has no name")
        out[-1]["candidates"].append({"name": name, "party": party, "status": text_of(status.group(1)) if status else ""})
    for o in out:
        o.pop("headed", None)
    return out


def read_inquiry(path, say, max_age_days=2):
    """The federal offices' candidates for the four elections of Congress's 2026 cycle; kept (read fields only) for two days."""
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < max_age_days * 86400:
        return json.load(open(path, encoding="utf-8"))
    net.patient_lookups()
    ids = election_ids(net.get(INQUIRY, accept="text/html").decode("utf-8", "replace"))
    kept = {"url": INQUIRY, "elections": {}}
    for date in (NOV, DEC, PRIMARY, RUNOFF):
        if date not in ids:
            raise SystemExit(f"Louisiana: the Candidate Inquiry no longer lists the {date} election")
        time.sleep(1.5)
        offs = offices(net.get(OFFICE_LIST + ids[date], accept="text/html").decode("utf-8", "replace"))
        # the House's May 16 and June 27 party primaries were cancelled (Act 7 of 2026); only the Senate's are read
        want = [(i, t) for i, t in offs if re.match(r"U\. ?S\. Senator\b", t) or (date in (NOV, DEC) and re.match(r"U\. ?S\. Representative\b", t))]
        lists = []
        if want:
            time.sleep(1.5)
            lists = candidate_list(post(CANDIDATE_LIST, [("electionId", ids[date])] + [("officeIds", i) for i, _t in want]), date)
            if len(lists) != len(want):
                raise SystemExit(f"Louisiana: {len(want)} federal offices asked for on {date}; the list has {len(lists)}")
        kept["elections"][date] = {"id": ids[date], "offices": dict(want), "lists": lists}
        say(f"      Candidate Inquiry {date}: {len(want)} federal offices, {sum(len(x['candidates']) for x in lists)} candidates")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(kept, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return kept


def race_of(title):
    """(race, party of a closed primary or None) for a federal office title, in either site's wording."""
    t = re.sub(r"\s+", " ", title.replace(" -- ", " ").replace(",", " ")).strip()
    m = re.fullmatch(r"U\. ?S\. Senator(?: -)?(?: (Democratic Party|Republican Party))?", t)
    if m:
        return senate_id("LA", 2), m.group(1)
    m = re.fullmatch(r"U\. ?S\. Representative (\d+)(?:st|nd|rd|th) Congressional District(?: - (Democratic Party|Republican Party))?", t)
    if m:
        return house_id("LA", int(m.group(1))), m.group(2)
    raise SystemExit(f"Louisiana: a federal office that is not read ({title!r})")


# ---------- the official results ----------

def data(blob):
    return net.get(DATA + blob, accept="application/json, text/csv, */*").decode("utf-8-sig")


def official_dates(path, max_age_days=2):
    """{"05/16/2026": True, ...}: whether the results site marks each 2026 election's results official."""
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < max_age_days * 86400:
        return json.load(open(path, encoding="utf-8"))
    got = json.loads(data("ElectionDates.htm"))["Dates"]["Date"]
    kept = {d["ElectionDate"]: d.get("ResultsOfficial") == "1" for d in got if d.get("ElectionDate", "").endswith("/2026")}
    json.dump(kept, open(path, "w", encoding="utf-8"), indent=1)
    return kept


def read_results(date, path, keep, max_age_days=30):
    """The official results of the federal races of one election (keep(race title) says which), with each race's
    parish rows; kept for 30 days."""
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < max_age_days * 86400:
        return json.load(open(path, encoding="utf-8"))
    folder = f"{date[6:]}{date[:2]}{date[3:5]}"
    races = json.loads(data(f"{folder}/RacesCandidates_Multiparish.htm"))["Races"]
    time.sleep(1.5)
    votes = {r["ID"]: r for r in json.loads(data(f"{folder}/Votes_Multiparish.htm"))["Races"]["Race"]}
    out = {"date": date, "written": races.get("WriteTime"), "races": []}
    for r in races["Race"]:
        title = re.sub(r"\s+", " ", r["SpecificTitle"]).strip()
        if not re.match(r"U\. ?S\. (Senator|Representative)\b", title) or not keep(title):
            continue
        v = votes.get(r["ID"])
        if v is None:
            raise SystemExit(f"Louisiana: the {date} results have no votes for {title}")
        vc = {c["ID"]: c for c in v["Choice"]}
        choices = [{"name": re.sub(rf"\s*\({RESULT_PARTY}\)$", "", c["Desc"]).strip(), "desc": c["Desc"],
                    "votes": int(vc[c["ID"]]["VoteTotal"]), "outcome": vc[c["ID"]].get("Outcome")} for c in r["Choice"]]
        time.sleep(1.5)
        rows = list(csv.reader(io.StringIO(data(f"{folder}/csv/ByParish_{r['ID']}.csv"))))
        head, parishes = rows[0], {}
        if head[:2] != ["Office", "Parish"] or sorted(head[2:]) != sorted(c["desc"] for c in choices):
            raise SystemExit(f"Louisiana: the parish file for {title} on {date} does not name the same candidates")
        for row in rows[1:]:
            if row:
                parishes[row[1]] = {h: int(x.replace(",", "") or 0) for h, x in zip(head[2:], row[2:])}
        out["races"].append({"id": r["ID"], "title": title, "closed": r.get("IsClosedParty") == "1", "choices": choices,
                             "precincts": [v["PrecinctsReporting"], v["PrecinctsExpected"]],
                             "absentee": [v["NumAbsenteeReporting"], v["NumAbsenteeExpected"]], "parishes": parishes})
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(out, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return out


def checked(res, problems):
    """Each race's statewide votes against its parish rows (all 64 parishes for the Senate), and every precinct reported."""
    for r in res["races"]:
        where = f"{r['title']} ({res['date']})"
        if not r["parishes"] or (r["title"].startswith("U. S. Senator") and len(r["parishes"]) != PARISHES):
            problems.append(f"{where}: {len(r['parishes'])} parishes in its parish file")
        for c in r["choices"]:
            summed = sum(p.get(c["desc"], 0) for p in r["parishes"].values())
            if summed != c["votes"]:
                problems.append(f"{where}: {c['name']}'s parish rows add to {summed:,}, the statewide total is {c['votes']:,}")
        if r["precincts"][0] != r["precincts"][1] or r["absentee"][0] != r["absentee"][1]:
            problems.append(f"{where}: {r['precincts'][0]} of {r['precincts'][1]} precincts reported")


def same(a, b):
    return fold(a) == fold(b)


def load(con, cache, say=print):
    net.patient_lookups()
    folder = os.path.join(cache, "la")
    os.makedirs(folder, exist_ok=True)
    ipath = os.path.join(folder, "la_2026_candidate_inquiry_federal.json")
    inquiry = read_inquiry(ipath, say)
    rows, gone, order_breaks, nominee = [], [], [], {}

    def on_list(date):
        """{(race, party of a closed primary): [candidate]} for one election, the ones left off counted."""
        got = {}
        for o in inquiry["elections"][date]["lists"]:
            race, party = race_of(o["office"])
            if o["to_elect"] != 1:
                raise SystemExit(f"Louisiana: {o['office']} on {date} elects {o['to_elect']}, not 1")
            for c in o["candidates"]:
                if GONE.search(c["status"]):
                    gone.append((race, date, c["name"]))
                    continue
                if c["status"] not in ON_BALLOT:
                    raise SystemExit(f"Louisiana: a status on the {date} list that is not read ({c['status']!r})")
                got.setdefault((race, party), []).append(c)
        return got

    for date in (NOV, DEC):
        for (race, party), cands in on_list(date).items():
            if party:
                raise SystemExit(f"Louisiana: a party office {race} {party} on the {date} list")
            fams = [name_parts(c["name"])[1] for c in cands]
            if fams != sorted(fams):
                order_breaks.append(f"{race} {date}")
            house = "-H" in race
            election = "open-primary" if house and date == NOV else "general"
            if not house and date == DEC:
                raise SystemExit(f"Louisiana: the Senate on the {date} list")
            for k, c in enumerate(cands, start=1):
                if not house:
                    if c["party"] in ("Democrat", "Republican"):
                        if (race, c["party"]) in nominee:
                            raise SystemExit(f"Louisiana: two {c['party']} candidates for {race} on the November list")
                        nominee[(race, c["party"])] = c["name"]
                rows.append([race, election, ISO[date], c["name"], c["party"], party_code(c["party"]), k, 0, 0, None, None, None, None, None,
                             "la-sos-2026-candidate-inquiry", OPEN_PRIMARY if election == "open-primary" else (DECEMBER if house else None)])
    expected = {senate_id("LA", 2)} | {house_id("LA", d) for d in range(1, 7)}
    got_races = {r[0] for r in rows if r[2] == ISO[NOV]}
    missing = sorted(expected - got_races)
    if got_races - expected:
        raise SystemExit(f"Louisiana: the November list has races that are not expected ({sorted(got_races - expected)})")

    # ---------- the Senate's party primaries and runoffs ----------
    spath = os.path.join(folder, "la_2026_results_status.json")
    official = official_dates(spath)
    problems, upset, fields, used = [], [], 0, {}
    senate = lambda t: t.startswith("U. S. Senator")
    for date, code_of in ((PRIMARY, "primary"), (RUNOFF, "runoff")):
        if not official.get(date):
            problems.append(f"the {date} results are not marked official; not loaded")
            continue
        rpath = os.path.join(folder, f"la_2026_results_{ISO[date].replace('-', '')}_federal.json")
        res = read_results(date, rpath, senate)
        used[date] = (rpath, res)
        checked(res, problems)
        on = on_list(date)
        for r in res["races"]:
            race, party = race_of(r["title"])
            if party not in PARTY_CODE or not r["closed"]:
                raise SystemExit(f"Louisiana: a Senate race in the {date} results that is not a closed party primary ({r['title']})")
            cands = on.get((race, party), [])
            if sorted(fold(c["name"]) for c in cands) != sorted(fold(c["name"]) for c in r["choices"]):
                raise SystemExit(f"Louisiana: the {date} results for {r['title']} do not name the Candidate Inquiry's candidates")
            by_name = {fold(c["name"]): c for c in cands}
            if len(r["choices"]) < 2:
                continue
            fields += 1
            total = sum(c["votes"] for c in r["choices"])
            printed = by_name[fold(r["choices"][0]["name"])]["party"]
            won = nominee.get((race, printed))
            for c in r["choices"]:
                listed_c = by_name[fold(c["name"])]
                out = c["outcome"]
                if code_of == "primary" and out == "Runoff":
                    outcome, note = "advanced", TO_RUNOFF
                elif out in ("Advances", "Elected"):
                    outcome, note = "advanced", None
                    if won and not same(won, c["name"]):
                        upset.append(f"{race} {party} {date}: {c['name']} won; the November list names {won}")
                        note = f"Won; the November list names {won} as the party's candidate instead."
                    if not won:
                        note = NOT_ON_LIST
                    if listed_c["status"] not in ("", out):
                        problems.append(f"{race} {party} {date}: the Candidate Inquiry says {listed_c['status']!r} for {c['name']}")
                elif out == "Defeated":
                    outcome, note = "lost", None
                else:
                    raise SystemExit(f"Louisiana: an outcome in the {date} results that is not read ({out!r})")
                rows.append([race, f"{code_of}-{PARTY_CODE[party]}", ISO[date], listed_c["name"], listed_c["party"], party_code(listed_c["party"]),
                             None, 0, 0, c["votes"], round(100 * c["votes"] / total, 1) if total else None, outcome, None, None,
                             f"la-sos-2026-results-{ISO[date].replace('-', '')}", note])
    for code in PARTY_CODE.values():                  # a primary that sent two to a runoff must have a runoff with one winner
        sent = [r for r in rows if r[1] == f"primary-{code}" and r[15] == TO_RUNOFF]
        won = [r for r in rows if r[1] == f"runoff-{code}" and r[11] == "advanced"]
        if sent and RUNOFF in used and (len(sent) != 2 or len(won) != 1 or won[0][3] not in {r[3] for r in sent}):
            problems.append(f"the {code} Senate primary sent {len(sent)} to a runoff, and the runoff has {len(won)} winner(s)")

    # ---------- the House open primary's official results, once there are any ----------
    if official.get(NOV):
        rpath = os.path.join(folder, "la_2026_results_20261103_federal.json")
        res = read_results(NOV, rpath, lambda t: t.startswith("U. S. Representative"))
        used[NOV] = (rpath, res)
        checked(res, problems)
        for r in res["races"]:
            race, _party = race_of(r["title"])
            mine = [x for x in rows if x[0] == race and x[1] == "open-primary"]
            if sorted(fold(x[3]) for x in mine) != sorted(fold(c["name"]) for c in r["choices"]):
                raise SystemExit(f"Louisiana: the November 3 results for {r['title']} do not name the Candidate Inquiry's candidates")
            total = sum(c["votes"] for c in r["choices"])
            for c in r["choices"]:
                x = [x for x in mine if same(x[3], c["name"])][0]
                outcome = {"Elected": "elected", "Runoff": "advanced", "Defeated": "lost"}.get(c["outcome"])
                if outcome is None:
                    raise SystemExit(f"Louisiana: an outcome in the November 3 results that is not read ({c['outcome']!r})")
                x[9], x[10], x[11] = c["votes"], round(100 * c["votes"] / total, 1) if total else None, outcome
                x[14] = "la-sos-2026-results-20261103"
                x[15] = OPEN_PRIMARY + (" " + TO_DECEMBER if outcome == "advanced" else "")

    with con:
        con.execute("DELETE FROM candidates WHERE race_id LIKE '2026-LA-%'")
        con.execute("DELETE FROM list_gaps WHERE state = 'LA'")
        con.executemany("INSERT OR REPLACE INTO candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [tuple(r) for r in rows])
        con.executemany("INSERT INTO list_gaps VALUES (?, 'LA', ?)",
                        [(race, "the Secretary of State's Candidate Inquiry lists no candidate for it yet") for race in missing])
        n_listed = sum(len(o["candidates"]) for e in inquiry["elections"].values() for o in e["lists"])
        record_source(con, "la-sos-2026-candidate-inquiry", path=ipath, level="federal", state="LA", kind="official candidate list",
                      agency="Louisiana Secretary of State",
                      title="Candidate Inquiry: U.S. Senator and U.S. Representative, elections of May 16, June 27, November 3 and "
                            "December 12, 2026",
                      url=INQUIRY, rows=n_listed,
                      note="Read from the portal's own office and candidate lists (CandidateInquiry/StatewideCandidate): the office title, the "
                           "first line of the name and party columns, and the status cell only; addresses, telephones, e-mail, race and "
                           "gender are never read, and filing dates are not kept. November 3: the Senate's general election and the House's open primary (Act 7 "
                           f"of 2026; the Secretary's notice of May 14, 2026, {NOTICE}). The list gives no ballot position; its order, "
                           "alphabetical by surname as R.S. 18:551(C) sets the ballot, is kept. Withdrawn, disqualified or removed, left off: "
                           f"{len(gone)} (November: {sum(1 for g in gone if g[1] == NOV)}). Louisiana has no write-in candidates."
                           + (f" December 12 candidates listed: {sum(1 for r in rows if r[2] == ISO[DEC])}." if any(r[2] == ISO[DEC] for r in rows) else
                              " No December 12 candidates for Congress are listed yet."))
        for date, (rpath, res) in used.items():
            record_source(con, f"la-sos-2026-results-{ISO[date].replace('-', '')}", path=rpath, level="federal", state="LA", kind="official results",
                          agency="Louisiana Secretary of State",
                          title=f"Official election results, {date}: " + ("U.S. Senator, closed party primaries" if date == PRIMARY else
                                                                         "U.S. Senator, closed party primary runoffs" if date == RUNOFF else
                                                                         "U.S. Representative, open primary"),
                          url=RESULTS, published=(res.get("written") or "")[:10],
                          rows=sum(len(r["choices"]) for r in res["races"]),
                          note=f"From the results site's data ({DATA}{ISO[date].replace('-', '')}/RacesCandidates_Multiparish.htm and "
                               "Votes_Multiparish.htm), marked official in its ElectionDates.htm. Statewide totals stored, checked against each race's "
                               "parish file (csv/ByParish_<race>.csv; all 64 parishes for the Senate) and every precinct reported. No write-ins in Louisiana, so shares are of the "
                               "candidates' votes. The date given is when the site wrote the races file. "
                               + ("Every race's parish rows add up to its statewide totals." if not [p for p in problems if date in p]
                                  else "Did not add up: " + "; ".join(p for p in problems if date in p) + "."))
    for p in problems:
        say(f"      check: {p}")
    for u in upset:
        say(f"      check: {u}")
    if order_breaks:
        say("      check: the list is not alphabetical by surname in " + ", ".join(order_breaks) + "; its order is kept")
    for race in missing:
        say(f"      {race} not loaded: no candidate on the Candidate Inquiry's November 3 list")
    nov = [r for r in rows if r[2] == ISO[NOV]]
    house = [r for r in nov if r[1] == "open-primary"]
    say(f"    Louisiana: {len({r[0] for r in house})} House districts and {'the' if any(r[1] == 'general' for r in nov) else 'no'} Senate race, "
        f"{len(nov)} candidates on the November 3 ballot ({len(house)} in the House's open primary, {len(nov) - len(house)} in the Senate's "
        f"general election; {sum(1 for g in gone if g[1] == NOV)} withdrawn left off); {fields} Senate party primaries and runoffs with a field, votes from the official results")
    return len(nov)
