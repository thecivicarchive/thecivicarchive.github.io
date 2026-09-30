"""
Alaska: the Division of Elections' candidate lists and its official results of the August 18, 2026 primary, all from
elections.alaska.gov (the Division is part of the Office of the Lieutenant Governor), which answers scripts.

  General list   "2026 General Election" candidates, www.elections.alaska.gov/candidates/?election=26genr (linked from
                 the Election Information page as "Candidates"): one section per office, headed UNITED STATES SENATOR,
                 UNITED STATES REPRESENTATIVE and so on, each a table with the columns Candidate Name on Ballot, Campaign
                 Address (or Address), Contact and Election Pamphlet Information. Only the Candidate Name on Ballot column
                 is read, found by its heading: the name as printed ("Last, First"), the registration in brackets
                 (Registered Republican, Nonpartisan, Undeclared ...), the status (Certified), the red "Certified
                 Write-In" mark and the "Incumbent" mark. Addresses, phones, e-mail, websites and pamphlet links are
                 never read, and the cached copy keeps only the fields read, for the two federal races.
  Primary list   "2026 Primary Election" candidates, ...?election=26prim ("last updated at: September 1, 2026"). Since the
                 primary it is one flat table with no headings, five cells a row. Only the first two cells are read, and
                 each must have the shape expected (office|district; name|registration|status|incumbent Yes or No), or
                 the loader stops; the other three (address, contact, pamphlet links) are never turned into text. Status
                 is Certified or Withdrawn: a candidate withdrawn before the primary was not on its ballot and is named
                 in the source note.
  Results        the 2026 Primary Election page of the results site, www.elections.alaska.gov/election-results/e/?id=26prim,
                 which must say "Results Status: Official": its "Results Per Precinct" file (GA_ENR_Precinct_State_of_
                 Alaska.csv, one row per precinct, contest and candidate; columns taken by name: Precinct_name,
                 Contest_title, candidate_name, Candidate_Type, Party_Code, total_votes) and its "Summary"
                 (ElectionSummaryReportRPT.pdf, headed "OFFICIAL RESULTS", read with ballot/pdftext.py).
  Sample ballot  the Division's 2026 General Election ranked-choice sample ballot for House District 1 (a PDF linked from
                 www.elections.alaska.gov/sample-ballots/ as "House District 1"). Its text sits inside form objects,
                 which pdftext's lines() does not open, so they are opened here with pdftext's own parts.

Alaska's primary is top-four (since 2022): every candidate, of every registration, is on one primary ballot, and the
four who receive the most votes advance to the November general election, which is ranked-choice. The primary takes no
write-in votes, so a field's total is its candidates' votes, which is the Summary's "Total Votes". So the primary field
is every candidate with their votes, summed over every precinct, with controls: each candidate's sum and the field's
total match the Summary exactly (and its percentages), and the field's candidates are exactly the primary list's
Certified candidates for that office.

The top four are marked "advanced". A top-four finisher can withdraw before the Division's deadline (August 31, the 64th
day before the election) and another primary candidate is then put on the ballot in that place: when the November list
names someone who finished below fourth, that candidate is also marked "advanced", and the notes on both say who
took whose place. The Division's pages do not say why a candidate withdrew or why others were passed over, and the
notes say only what the lists show.

The November ballot is the general list's Certified candidates for the two federal races, plus the certified write-in
candidates it names (write_in 1; their names are not printed on the ballot). A candidate the list marks withdrawn or
removed is left off and counted. Control: the names printed on the House District 1 sample ballot are exactly the
list's candidates who are not write-ins, with the same registration (the ballot may leave off an incumbent mark the
list has, and does for Begich, but never adds one). Where the ballot prints no registration after a name (the
Division's results print none either), the list's registration is kept and the row says so. No ballot order is stored: Alaska starts the federal candidates in alphabetical order in House District 1 and
rotates them from district to district (the sample ballot page says so), so the page shows them by surname.

Names are turned round from "Last, First" (a Jr., Sr., II or III goes to the end); curly quotation marks around a
nickname are written as the ballot prints them, straight. Registrations are shown as the list prints them.
"""

import collections
import csv
import html as H
import json
import os
import re
import time
from urllib.parse import urljoin

from ballot.common import fold, house_id, name_parts, party_code, record_source, senate_id
from ballot.pdftext import PDF, join, lines, page_runs
from states import net

SITE = "https://www.elections.alaska.gov"
GENERAL_URL = SITE + "/candidates/?election=26genr"
PRIMARY_URL = SITE + "/candidates/?election=26prim"
RESULTS_PAGE = SITE + "/election-results/e/?id=26prim"
SAMPLE_PAGE = SITE + "/sample-ballots/ballot/zk4o0"
AGENCY = "Alaska Division of Elections"
PRIMARY = "2026-08-18"
HOUSE, SENATE = house_id("AK", 0), senate_id("AK", 2)
OFFICES = {"UNITED STATES SENATOR": SENATE, "UNITED STATES REPRESENTATIVE": HOUSE}
CONTESTS = {"U.S. Senator": SENATE, "U.S. Representative": HOUSE}
BALLOT_HEADS = {"United States Senator": SENATE, "United States Representative": HOUSE}
NAME_COL = "Candidate Name on Ballot"
CSV_KEEP = ("Precinct_name", "Contest_title", "candidate_name", "Candidate_Type", "Party_Code", "total_votes")
STATUSES = ("Certified", "Withdrawn")
OFF = re.compile(r"WITHDR|REMOV|DISQUAL|DECEAS|REJECT|DENIED", re.I)
CODE_LABEL = {"REP": "Registered Republican", "DEM": "Registered Democrat", "LIB": "Registered Libertarian",
              "GRN": "Registered Green", "NON": "Nonpartisan", "UND": "Undeclared"}
ORDINAL = {1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth", 6: "sixth", 7: "seventh", 8: "eighth", 9: "ninth",
           10: "tenth", 11: "eleventh", 12: "twelfth", 13: "thirteenth", 14: "fourteenth", 15: "fifteenth", 16: "sixteenth"}
TOP_FOUR = ("Advanced from the August 18 top-four primary. Alaska prints each candidate's party registration, or Nonpartisan "
            "or Undeclared; the general election is ranked-choice.")
WRITE_IN = "Write-in candidate: the name is not printed on the ballot."
BARE_GENERAL = ("The ballot prints no party registration after this name (the Division's sample ballot shows none); the "
                "registration shown is the one the Division's candidate list gives.")
BARE_PRIMARY = ("The Division's results print no party registration for this candidate; the registration shown is the one "
                "its candidate list gives.")


def text(fragment):
    return re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", fragment)).replace("\xa0", " ")).strip()


def straight(s):
    return s.replace("“", '"').replace("”", '"').replace("’", "'")


def turn(name):
    """"Sullivan, Daniel J. Jr." -> "Daniel J. Sullivan Jr."; "McDermott, James C. "Jim"" -> "James C. "Jim" McDermott"."""
    name = re.sub(r"\s+", " ", straight(name)).strip()
    last, comma, first = name.partition(",")
    if not comma:
        return name
    words, suffix = first.split(), []
    while words and re.fullmatch(r"(?:Jr|Sr)\.?|II|III|IV|V", words[-1]):
        suffix.insert(0, words.pop())
    return " ".join(words + [last.strip()] + suffix)


def code_of(label):
    return "I" if (label or "").strip().lower() == "undeclared" else party_code(label)


def family(name):
    return name_parts(straight(name))[1]


def general_list(path, say):
    """The two federal races' rows of the general list, the name column only; kept on disk for two days."""
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < 2 * 86400:
        return json.load(open(path, encoding="utf-8"))
    page = net.get(GENERAL_URL, accept="text/html").decode("utf-8", "replace")
    if "<h2>2026 General Election</h2>" not in page:
        raise SystemExit(f"Alaska: {GENERAL_URL} is no longer the 2026 General Election candidate list")
    rows, seen, sections = [], set(), 0
    for sec in re.findall(r'<section class="candidates-table">(.*?)</section>', page, re.S):
        sections += 1
        head = re.search(r"<h4[^>]*>(.*?)</h4>", sec, re.S)
        office = text(head.group(1)) if head else ""
        if office not in OFFICES:
            continue
        if office in seen:
            raise SystemExit(f"Alaska: the general list has two sections headed {office}")
        seen.add(office)
        table = re.search(r"<table[^>]*>(.*?)</table>", sec, re.S)
        heads = [text(h) for h in re.findall(r"<th[^>]*>(.*?)</th>", table.group(1), re.S)] if table else []
        if heads.count(NAME_COL) != 1:
            raise SystemExit(f"Alaska: the {office} table no longer has one '{NAME_COL}' column ({[h for h in heads if h == NAME_COL]})")
        k = heads.index(NAME_COL)
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", table.group(1), re.S):
            if "<th" in tr:
                continue
            cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
            if len(cells) != len(heads):
                raise SystemExit(f"Alaska: a row of the {office} table does not line up with its headings")
            cell = cells[k]                                          # the name column only; the others are never read
            name = re.search(r"<strong>(.*?)</strong>", cell, re.S)
            small = re.search(r"<small>(.*?)</small>", cell, re.S)
            marks = [text(m) for m in re.findall(r'<span style="color: #e50000; font-weight: bold;">(.*?)</span>', cell, re.S)]
            marks = [m for m in marks if m]
            if not name or not small:
                raise SystemExit(f"Alaska: a name in the {office} table could not be read")
            groups = [g.strip() for g in re.findall(r"\(([^()]*)\)", text(small.group(1)))]
            if len(groups) != 2 or not groups[0]:
                raise SystemExit(f"Alaska: a registration and status for {office} could not be read ({len(groups)} bracketed parts)")
            if any(m != "Certified Write-In" for m in marks):
                raise SystemExit(f"Alaska: a mark on the {office} list that is not read ({marks})")
            rows.append({"race": OFFICES[office], "office": office, "name": straight(text(name.group(1))), "party": groups[0],
                         "status": groups[1], "write_in": bool(marks), "incumbent": bool(re.search(r"<em>\s*Incumbent\s*</em>", cell))})
    if seen != set(OFFICES):
        raise SystemExit(f"Alaska: the general list has no section for {sorted(set(OFFICES) - seen)}")
    kept = {"title": "2026 General Election", "url": GENERAL_URL, "sections": sections, "rows": rows}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(kept, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    say(f"      2026 General Election candidate list: {sections} offices, {len(rows)} rows for Congress")
    return kept


def primary_list(path, say):
    """The two federal races' rows of the primary list, the first two cells only; kept on disk for thirty days."""
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < 30 * 86400:
        return json.load(open(path, encoding="utf-8"))
    page = net.get(PRIMARY_URL, accept="text/html").decode("utf-8", "replace")
    if "<h2>2026 Primary Election</h2>" not in page:
        raise SystemExit(f"Alaska: {PRIMARY_URL} is no longer the 2026 Primary Election candidate list")
    m = re.search(r"last updated at:\s*(?:<[^>]+>\s*)*([A-Z][a-z]+ \d{1,2}, 20\d\d)", page)
    updated = time.strftime("%Y-%m-%d", time.strptime(m.group(1), "%B %d, %Y")) if m else ""
    table = re.search(r'<table id="cand"[^>]*>(.*?)</table>', page, re.S)
    if not table:
        raise SystemExit("Alaska: the primary list's table is gone")
    rows, total = [], 0
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", table.group(1), re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        if len(cells) != 5:
            raise SystemExit(f"Alaska: a row of the primary list has {len(cells)} cells, not five")
        total += 1
        where = [text(x) for x in cells[0].split("|")]               # office | district
        who = [text(x) for x in cells[1].split("|")]                 # name | registration | status | incumbent
        if len(where) != 2 or len(who) != 4 or who[3] not in ("Yes", "No") or not (who[2] in STATUSES or OFF.search(who[2])):
            raise SystemExit("Alaska: a row of the primary list no longer has the shape read (office|district; name|registration|status|Yes or No)")
        if where[0] not in OFFICES:
            continue
        if where[1] != "All":
            raise SystemExit(f"Alaska: a federal row of the primary list names a district ({where[1]!r})")
        rows.append({"race": OFFICES[where[0]], "office": where[0], "name": straight(who[0]), "party": who[1], "status": who[2],
                     "incumbent": who[3] == "Yes"})
    kept = {"title": "2026 Primary Election", "url": PRIMARY_URL, "updated": updated, "items": total, "rows": rows}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(kept, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    say(f"      2026 Primary Election candidate list: {total} rows, {len(rows)} for Congress")
    return kept


def results_files(folder, say):
    """The precinct file and the Summary of the primary, found on the results page, which must call them official."""
    rec_path = os.path.join(folder, "ak_2026_primary_results_record.json")
    csv_path = os.path.join(folder, "ak_2026_primary_precinct.csv")
    pdf_path = os.path.join(folder, "ak_2026_primary_summary.pdf")
    if not all(os.path.exists(p) for p in (rec_path, csv_path, pdf_path)):
        page = net.get(RESULTS_PAGE, accept="text/html").decode("utf-8", "replace")
        plain = text(re.sub(r"<script.*?</script>|<style.*?</style>", " ", page, flags=re.S))
        m = re.search(r"2026 Primary Election\s*\W\s*August 18, 2026\s*Results Status:\s*(\w+)", plain)
        if not m or m.group(1) != "Official":
            raise SystemExit(f"Alaska: the results page {RESULTS_PAGE} does not call the August 18 primary's results official; nothing is loaded")
        links = {text(lab): urljoin(RESULTS_PAGE, H.unescape(href))
                 for href, lab in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', page, re.S)}
        if "Results Per Precinct" not in links or "Summary" not in links:
            raise SystemExit("Alaska: the results page no longer links its Results Per Precinct file and its Summary")
        upd = re.search(r"Page last updated ([A-Z][a-z]+ \d{1,2}, 20\d\d)", plain)
        rec = {"status": m.group(1), "csv": links["Results Per Precinct"], "pdf": links["Summary"],
               "updated": time.strftime("%Y-%m-%d", time.strptime(upd.group(1), "%B %d, %Y")) if upd else ""}
        for key, path in (("csv", csv_path), ("pdf", pdf_path)):
            if os.path.exists(path):
                os.remove(path)
            net.download(rec[key], path, max_age_days=365, say=say)
        json.dump(rec, open(rec_path, "w", encoding="utf-8"), indent=1)
    rec = json.load(open(rec_path, encoding="utf-8"))
    if open(pdf_path, "rb").read(4) != b"%PDF":
        raise SystemExit(f"Alaska: {os.path.basename(pdf_path)} is not a PDF; delete it and run again")
    if not open(csv_path, "rb").read(20).lstrip(b"\xef\xbb\xbf").startswith(b"Precinct_name,"):
        raise SystemExit(f"Alaska: {os.path.basename(csv_path)} is not the precinct results file; delete it and run again")
    return rec, csv_path, pdf_path


def precinct_votes(path):
    """{race: {folded name: [name, party code, votes]}} for the two federal contests, summed over every precinct."""
    out, precincts = {}, set()
    with open(path, encoding="utf-8-sig", newline="") as fh:
        rd = csv.reader(fh)
        heads = [h.strip() for h in next(rd)]
        if not all(heads.count(k) == 1 for k in CSV_KEEP):
            raise SystemExit(f"Alaska: the precinct file's columns changed ({[k for k in CSV_KEEP if heads.count(k) != 1]})")
        idx = {k: heads.index(k) for k in CSV_KEEP}
        for r in rd:
            race = CONTESTS.get(r[idx["Contest_title"]].strip())
            if not race:
                continue
            if r[idx["Candidate_Type"]].strip() != "C":
                raise SystemExit(f"Alaska: a {race} row of the precinct file with a candidate type not read ({r[idx['Candidate_Type']]!r})")
            name = re.sub(r"\s+", " ", straight(r[idx["candidate_name"]])).strip()
            cell = out.setdefault(race, {}).setdefault(fold(name), [name, r[idx["Party_Code"]].strip(), 0])
            if cell[1] != r[idx["Party_Code"]].strip():
                raise SystemExit(f"Alaska: {name} has two party codes in the precinct file")
            cell[2] += int(r[idx["total_votes"]] or 0)
            precincts.add(r[idx["Precinct_name"]].strip())
    return out, len(precincts)


def summary_check(path, votes):
    """Each federal contest of the Summary: its candidates' figures and percentages and its Total Votes must be exactly
    the precinct file's. Returns the report's printed date."""
    got = lines(path)
    head = [t for p, _y, t in got if p == 1]
    for need in ("2026 PRIMARY ELECTION", "August 18, 2026", "OFFICIAL RESULTS"):
        if need not in head:
            raise SystemExit(f"Alaska: the Summary is no longer the official report of the 2026 primary (no '{need}')")
    printed = next((re.search(r"(\d{1,2})/(\d{1,2})/(20\d\d)", t) for t in head if t.startswith("Page: 1 of")), None)
    heads = {"U.S. Senator (Vote for 1)": SENATE, "U.S. Representative (Vote for 1)": HOUSE}
    found, race = {}, None
    for _p, _y, t in got:
        if t in heads:
            race = heads[t]
            found[race] = {"figures": [], "total": None}
            continue
        if race is None:
            continue
        m = re.fullmatch(r"Total Votes (\d{1,3}(?:,\d{3})*)", t)
        if m:
            found[race]["total"] = int(m.group(1).replace(",", ""))
            race = None
            continue
        if t.startswith(("Times Cast", "Precincts Reported")):
            continue
        m = re.search(r"(?:^| )(\d{1,3}(?:,\d{3})*) (\d{1,3}\.\d\d)%$", t)
        if m:
            found[race]["figures"].append((int(m.group(1).replace(",", "")), float(m.group(2))))
    for race, cands in votes.items():
        f = found.get(race)
        mine = sorted(v for _n, _c, v in cands.values())
        if not f or f["total"] is None:
            raise SystemExit(f"Alaska: the Summary has no whole table for {race}")
        if sorted(v for v, _pct in f["figures"]) != mine or f["total"] != sum(mine):
            raise SystemExit(f"Alaska: the precinct file's figures for {race} do not match the Summary's")
        for v, pct in f["figures"]:
            if abs(round(100 * v / f["total"], 2) - pct) > 0.006:
                raise SystemExit(f"Alaska: a percentage in the Summary for {race} does not follow from its figures ({v}, {pct}%)")
    return f"{printed.group(3)}-{int(printed.group(1)):02d}-{int(printed.group(2)):02d}" if printed else ""


def sample_ballot(folder, say):
    """{race: [(name, registration printed or "", incumbent)]} from the House District 1 sample ballot."""
    path = os.path.join(folder, "ak_2026_general_sample_ballot_hd1.pdf")
    rec_path = os.path.join(folder, "ak_2026_general_sample_ballot_hd1.json")
    if not (os.path.exists(path) and os.path.exists(rec_path)):
        page = net.get(SAMPLE_PAGE, accept="text/html").decode("utf-8", "replace")
        if "2026 General Election" not in page:
            raise SystemExit(f"Alaska: {SAMPLE_PAGE} is no longer the 2026 General Election sample ballots page")
        hd1 = next((urljoin(SAMPLE_PAGE, H.unescape(href)) for href, lab in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', page, re.S)
                    if text(lab) == "House District 1"), None)
        if not hd1:
            raise SystemExit("Alaska: the sample ballots page no longer links House District 1")
        if os.path.exists(path):
            os.remove(path)
        net.download(hd1, path, max_age_days=30, say=say)
        json.dump({"url": hd1}, open(rec_path, "w", encoding="utf-8"))
    url = json.load(open(rec_path, encoding="utf-8"))["url"]
    if open(path, "rb").read(4) != b"%PDF":
        raise SystemExit("Alaska: the House District 1 sample ballot is not a PDF; delete it and run again")
    pdf = PDF(open(path, "rb").read())

    def forms(res):
        for _name, ref in (pdf.get((pdf.get(res) or {}).get("XObject")) or {}).items():
            d = pdf.get(ref)
            if isinstance(d, dict) and d.get("Subtype") == "Form":
                yield ref, d
                yield from forms(d.get("Resources"))

    out, race = {}, None
    for page, res in pdf.pages():
        for ref, d in forms(res):
            grouped = []
            for r in sorted(page_runs(pdf, {"Contents": ref}, d.get("Resources")), key=lambda r: (-round(r[1], 1), r[0])):
                if grouped and abs(grouped[-1][0] - r[1]) <= max(1.5, 0.35 * r[2]):
                    grouped[-1][1].append(r)
                else:
                    grouped.append([r[1], [r]])
            for _y, runs in grouped:
                t = join(runs)
                if t in BALLOT_HEADS:
                    race = BALLOT_HEADS[t]
                    if race in out:
                        raise SystemExit(f"Alaska: the sample ballot prints {t} twice")
                    out[race] = []
                    continue
                if race is None:
                    continue
                if "Write-in:" in t:
                    race = None
                    continue
                t = re.sub(r"(?: \d)+$", "", t).strip()
                if not t or re.fullmatch(r"[\d ]+|(?:\d+(?:st|nd|rd|th) ?)+|(?:Choice ?)+", t):
                    continue
                m = re.fullmatch(r"(.+?)(?: \(([^()]*)\))?( Incumbent)?", t)
                out[race].append((straight(m.group(1)), re.sub(r"\s*/\s*", "/", m.group(2) or ""), bool(m.group(3))))
    if set(out) != {SENATE, HOUSE}:
        raise SystemExit("Alaska: the sample ballot's federal contests could not be read")
    return out, path, url


def load(con, cache, say=print):
    net.patient_lookups()
    folder = os.path.join(cache, "ak")
    os.makedirs(folder, exist_ok=True)
    gen_path, pri_path = os.path.join(folder, "ak_2026_general_federal.json"), os.path.join(folder, "ak_2026_primary_federal.json")
    gen = general_list(gen_path, say)
    pri = primary_list(pri_path, say)
    rec, csv_path, pdf_path = results_files(folder, say)
    votes, precincts = precinct_votes(csv_path)
    published = summary_check(pdf_path, votes)
    ballot, ballot_path, ballot_url = sample_ballot(folder, say)

    races = {r: holder for r, holder in con.execute("SELECT race_id, holder_name FROM races WHERE state = 'AK'")}
    if set(races) != {SENATE, HOUSE} or set(votes) != set(races):
        raise SystemExit(f"Alaska: the races ({sorted(races)}) are not the Senate race and the at-large House seat, or not the results' ({sorted(votes)})")

    # the general list: the November ballot
    listed, off = collections.defaultdict(list), []
    for r in gen["rows"]:
        if OFF.search(r["status"]):
            off.append(r)
        elif r["status"] == "Certified":
            listed[r["race"]].append(r)
        else:
            raise SystemExit(f"Alaska: a status on the general list that is not read ({r['status']!r}, {r['office']})")
    bare, unmarked = set(), []
    for race in races:
        printed = [r for r in listed[race] if not r["write_in"]]
        on_ballot = {fold(n): (p, inc) for n, p, inc in ballot[race]}
        if set(on_ballot) != {fold(r["name"]) for r in printed} or len(on_ballot) != len(ballot[race]):
            raise SystemExit(f"Alaska: the names printed on the sample ballot for {race} are not the general list's")
        for r in printed:
            p, inc = on_ballot[fold(r["name"])]
            if inc and not r["incumbent"]:
                raise SystemExit(f"Alaska: the sample ballot marks {r['name']} as the incumbent and the list does not")
            if r["incumbent"] and not inc:                           # the ballot may leave the mark off (Begich, 2026)
                unmarked.append(turn(r["name"]))
            if not p:
                bare.add((race, fold(r["name"])))
            elif p != re.sub(r"\s*/\s*", "/", r["party"]):
                raise SystemExit(f"Alaska: {r['name']}'s registration differs between the sample ballot ({p}) and the list ({r['party']})")
        marked = [r for r in listed[race] if r["incumbent"]]
        if len(marked) > 1 or (marked and family(marked[0]["name"]) != family(races[race] or "")):
            raise SystemExit(f"Alaska: the list's incumbent mark for {race} does not agree with who holds the seat ({races[race]})")

    # the primary list: who was on the August ballot, with each one's registration, and who withdrew before it
    filed, withdrew = collections.defaultdict(dict), []
    for r in pri["rows"]:
        if r["status"] == "Certified":
            filed[r["race"]][fold(r["name"])] = r
        elif OFF.search(r["status"]):
            withdrew.append(f"{turn(r['name'])} ({r['office'].title().replace('United States', 'U.S.')})")
        else:
            raise SystemExit(f"Alaska: a status on the primary list that is not read ({r['status']!r})")

    rows, swaps, label_of = [], [], {}
    for race in sorted(races):
        field = votes[race]
        if set(field) != set(filed[race]):
            raise SystemExit(f"Alaska: the results' candidates for {race} are not the primary list's Certified candidates")
        for key, (name, code, _v) in field.items():
            label = filed[race][key]["party"]
            if code and label_of.setdefault(code, label) != label or (code in CODE_LABEL and CODE_LABEL[code] != label):
                raise SystemExit(f"Alaska: {name}'s party code in the results ({code}) does not fit the list's registration ({label})")
        ranked = sorted(field.values(), key=lambda c: (-c[2], c[0]))
        if len(ranked) > 4 and ranked[3][2] == ranked[4][2]:
            raise SystemExit(f"Alaska: a tie for fourth place in the {race} primary; the record read does not say who advanced")
        place = {fold(c[0]): i for i, c in enumerate(ranked, 1)}
        top = {fold(c[0]) for c in ranked[:4]}
        printed = {fold(r["name"]) for r in listed[race] if not r["write_in"]}
        missing = sorted(top - printed, key=place.get)                   # top-four finishers not on the November list
        extra = sorted(printed - top, key=place.get)                     # later finishers on it in their places
        if any(k not in field for k in extra):
            raise SystemExit(f"Alaska: the November list for {race} names a candidate who was not on the primary ballot")
        if len(extra) > len(missing):
            raise SystemExit(f"Alaska: the November list for {race} prints more than four candidates, or a later finisher with no place to fill")
        gone = " and ".join(turn(field[k][0]) for k in missing)
        passed = [c for c in ranked[4:] if fold(c[0]) not in printed and place[fold(c[0])] < max((place[k] for k in extra), default=0)]
        for k in extra:
            swaps.append(f"{turn(field[k][0])} ({ORDINAL.get(place[k], place[k])}) in place of {gone} ({race})")
        total = sum(c[2] for c in ranked)
        for name, code, v in ranked:
            k = fold(name)
            notes = []
            if k in missing:
                notes.append(f"Finished {ORDINAL[place[k]]} in the top-four primary and advanced; not on the Division's list of "
                             "candidates for the November ballot, nor on its sample ballot.")
            if k in extra:
                note = (f"Finished {ORDINAL.get(place[k], place[k])} in the top-four primary. On the November ballot in the place of "
                        f"{gone}, who finished in the top four and {'is' if len(missing) == 1 else 'are'} not on the Division's November list")
                if passed and place[k] == max(place[x] for x in extra):
                    lo, hi = place[fold(passed[0][0])], place[fold(passed[-1][0])]
                    note += (f"; the candidate who finished {ORDINAL[lo]} is not on it either" if lo == hi else
                             f"; the candidates who finished {ORDINAL[lo]} to {ORDINAL[hi]} are not on it either")
                notes.append(note + ".")
            if not code:
                notes.append(BARE_PRIMARY)
            label = filed[race][k]["party"]
            rows.append((race, "primary", PRIMARY, turn(filed[race][k]["name"]), label, code_of(label), None, 0, 0, v,
                         round(100 * v / total, 1) if total else None, "advanced" if (k in top or k in extra) else "lost",
                         None, None, "ak-doe-2026-primary-precinct", " ".join(notes) or None))
        for r in listed[race]:
            k = fold(r["name"])
            if r["write_in"]:
                note = WRITE_IN
            elif k in extra:
                note = (f"On the November ballot in the place of {gone}, who finished in the top four of the August 18 primary and "
                        f"{'is' if len(missing) == 1 else 'are'} not on the Division's November list; this candidate finished "
                        f"{ORDINAL.get(place[k], place[k])}. Alaska prints each candidate's party registration, or Nonpartisan or "
                        "Undeclared; the general election is ranked-choice.")
            else:
                note = TOP_FOUR
            if (race, k) in bare:
                note += " " + BARE_GENERAL
            rows.append((race, "general", "2026-11-03", turn(r["name"]), r["party"], code_of(r["party"]), None, 0, int(r["write_in"]),
                         None, None, None, None, None, "ak-doe-2026-general-list", note))

    general = [r for r in rows if r[1] == "general"]
    write_ins = sum(1 for r in general if r[8])
    primary_rows = len(rows) - len(general)
    with con:
        con.execute("DELETE FROM list_gaps WHERE state = 'AK'")
        con.execute("DELETE FROM candidates WHERE race_id LIKE '2026-AK-%'")
        con.executemany("INSERT OR REPLACE INTO candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        record_source(con, "ak-doe-2026-general-list", path=gen_path, level="federal", state="AK", kind="official candidate list",
                      agency=AGENCY, title="2026 General Election candidates (November 3, 2026): United States Senator and United States Representative",
                      url=GENERAL_URL, rows=len(gen["rows"]),
                      note=f"Every office's section read ({gen['sections']}); for the two federal races only the Candidate Name on Ballot column "
                           "(name, registration, status, write-in and incumbent marks). Addresses, phones, e-mail, websites and pamphlet links "
                           f"never read. Certified write-ins kept as write-ins: {write_ins}. Withdrawn or removed, left off: {len(off)}. No ballot "
                           "order stored: the federal candidates rotate from house district to house district.")
        record_source(con, "ak-doe-2026-primary-list", path=pri_path, level="federal", state="AK", kind="official candidate list",
                      agency=AGENCY, title="2026 Primary Election candidates (August 18, 2026): United States Senator and United States Representative",
                      url=PRIMARY_URL, published=pri.get("updated", ""), rows=len(pri["rows"]),
                      note=f"A flat table of {pri['items']} rows, five cells each; only the office and the name, registration, status and "
                           "incumbent cells read, each checked for its shape. Used to check the primary results and for each candidate's "
                           f"registration. Withdrawn before the primary, not on its ballot: {'; '.join(withdrew) or 'none'}.")
        record_source(con, "ak-doe-2026-primary-precinct", path=csv_path, level="federal", state="AK", kind="official results",
                      agency=AGENCY, title="2026 Primary Election (August 18, 2026): Results Per Precinct",
                      url=rec["csv"], published=rec.get("updated", ""), rows=primary_rows,
                      note=f"Found on {RESULTS_PAGE}, which gives the results status as Official. Votes summed over {precincts} reporting units (precincts, and each house "
                           "district's absentee, early-voting and questioned ballots). Top-four primary with no write-in votes: each field's total is its "
                           "candidates' votes.")
        record_source(con, "ak-doe-2026-primary-summary", path=pdf_path, level="federal", state="AK", kind="official results",
                      agency=AGENCY, title="2026 Primary Election, August 18, 2026: Election Summary Report, Official Results",
                      url=rec["pdf"], published=published, rows=len(votes),
                      note="Control: every candidate's summed votes, the percentages and each contest's Total Votes match this report exactly.")
        record_source(con, "ak-doe-2026-sample-ballot-hd1", path=ballot_path, level="federal", state="AK", kind="official sample ballot",
                      agency=AGENCY, title="2026 General Election ranked-choice sample ballot, House District 1",
                      url=ballot_url, rows=sum(len(v) for v in ballot.values()),
                      note=f"Linked from {SAMPLE_PAGE}. Control: the names printed for both federal races are exactly the general list's "
                           "candidates who are not write-ins, with the same registrations"
                           + (f" (the list marks {' and '.join(unmarked)} as the incumbent; the ballot prints no such mark)" if unmarked else "")
                           + ". The order on this ballot is alphabetical and rotates in the other house districts.")
    say(f"    Alaska: the at-large House seat and the Senate race, {len(general)} candidates on the November ballot ({write_ins} certified "
        f"write-ins, {len(off)} withdrawn left off); 2 top-four primary fields ({primary_rows} candidates), votes from the official "
        "results, precinct sums checked against the Summary, printed names against the sample ballot"
        + (f"; later finishers on the ballot: {'; '.join(swaps)}" if swaps else ""))
    return len(general)
