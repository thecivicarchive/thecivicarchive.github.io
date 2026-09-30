"""
Hawaii: the State of Hawaii Office of Elections' "2026 Candidate Report" (olvr.hawaii.gov, linked as "Candidate Report"
from elections.hawaii.gov/candidates/candidate-reports/), and the certified results of the August 8, 2026 primary (the
Office's results page, elections.hawaii.gov/election-results/: "Primary Election August 8, 2026", its "Certified Text
Files" Statewide Summary, summary.txt, and its "Certified Reports" Statewide Summary, histatewide.pdf). Hawaii has two
House districts and no U.S. Senate race in 2026.

The Candidate Report is a Telerik grid of every candidate for every office in 2026, fifteen rows a page. Every page is
read through the grid's own pager (the form posted with its Next Page button, as a browser posts it), each page is
checked to be the one asked for, and the rows read are counted against the grid's own "items" figure. Columns are taken
by name, only Contests, Party, Ballot Name, Issued, Filed and Status; the grid also carries each candidate's legal name,
mailing address, phone, e-mail and website, which are never read, and the cached copy keeps only the columns taken, for
the U.S. Representative rows. The Status column says where each candidate stands now: "In General" (nominated at the
primary, on the November ballot), "In Primary" (was on the primary ballot and was not nominated), "Issued" (took out
nomination papers and never filed them: never a candidate), "Withdrawn" and "Void" (left off, and counted). Any other
status on a federal row ("Filed", "Elected After Primary") stops the loader, since the primary is over and certified.

The November ballot is every U.S. Representative row marked In General. The report gives no ballot positions; it lists a
contest's candidates alphabetically by the name printed on the ballot, and that order is kept. There are no write-in
candidates: Hawaii's ballots have no write-in line. Names are printed "FAMILY, Given" with the family name in capitals;
they are turned round and the family name shown in ordinary capitals (a sitting member with the capitals the
congress-legislators roster gives the same words), and the row says so. Parties are printed in capitals and shown in
ordinary capitals: DEMOCRATIC, REPUBLICAN, GREEN, LIBERTARIAN, NONPARTISAN.

The primary: Hawaii's primary ballot has a section for each party and one for nonpartisan candidates, and the voter
votes in one section. summary.txt (tab-separated, "#FormatVersion 1", columns taken by name) has one contest per office
and section: "U.S. Representative, Dist I" with Contest Party D, R, G, L or N (nonpartisan), each candidate's mail,
in-person and total votes, and the precincts counted. Checks: every federal contest has counted all its precincts;
mail plus in-person votes make each total; each contest's candidates are exactly the Candidate Report's candidates of
that party marked In General or In Primary for that district; the leader of each party's section is the one the report
marks In General and every other candidate is marked In Primary (a tie at the top stops the loader); and every
candidate's name and total appear together in the Office's Final Summary Report (histatewide.pdf, "SUMMARY REPORT
FINAL"), read with ballot/pdftext.py. The results page must still head the files "Certified".

A nonpartisan candidate reaches the November ballot only by leading the nonpartisan section with at least 10 percent of
the votes cast for the office, or with as many votes as the party nominee with the fewest (the Office's page
"Nonpartisan Candidates in Partisan Contests"; only one nonpartisan candidate can advance per seat). The loader works
the rule out (10 percent of every candidate's votes for the office, all sections) and stops if it disagrees with the
report's In General mark.

A field is a section with two candidates or more. Election codes: primary-DEM, primary-REP, primary-GRE (Green),
primary-LIB, and primary-NP for the nonpartisan section. Hawaii has no write-in votes, so a field's total is its
candidates' votes, and pct is of that total; the Office's own percentages divide by every ballot cast in the section,
blank, over and invalid votes included, so they are lower. Blank, over and invalid votes are not stored.
"""

import collections
import csv
import datetime as dt
import html as H
import json
import os
import re
import sqlite3
import time
import urllib.parse
from http.cookiejar import CookieJar
from urllib.request import HTTPCookieProcessor, Request, build_opener

from ballot.common import HERE, fold, house_id, party_code, record_source
from ballot.lists.tx import proper
from ballot.pdftext import lines
from states import net

REPORT = "https://olvr.hawaii.gov/Controls/CandidateFiling.aspx?elid=94"
REPORT_LINK = "https://elections.hawaii.gov/candidates/candidate-reports/"
RESULTS_PAGE = "https://elections.hawaii.gov/election-results/"
RESULTS = "https://elections.hawaii.gov/wp-content/results/2026%20Primary/"
FILES = {"summary": ("summary.txt", "hi_2026_primary_summary.txt"), "pdf": ("histatewide.pdf", "hi_2026_primary_histatewide.pdf")}
PRIMARY = "2026-08-08"
KEEP = ("Contests", "Party", "Ballot Name", "Issued", "Filed", "Status")
SUMMARY_KEEP = ("Contest ID", "Contest Title", "Contest Party", "Total Precincts", "Counted Precincts", "Candidate Name",
                "Candidate Seq Nbr", "Mail Votes", "In-Person Votes", "Total Votes")
SECTION = {"D": "DEM", "R": "REP", "G": "GRE", "L": "LIB", "N": "NP"}                   # summary.txt Contest Party -> election code
REPORT_PARTY = {"DEMOCRATIC": "DEM", "REPUBLICAN": "REP", "GREEN": "GRE", "LIBERTARIAN": "LIB", "NONPARTISAN": "NP"}
ON, LOST, NEVER, OFF = "In General", "In Primary", "Issued", ("Withdrawn", "Void")
ROMAN = {"I": 1, "II": 2}
CAPS = "Hawaii's list prints family names in capitals; they are shown here in ordinary capitals."


def race_of(office):
    """The race for a federal contest of the report or the results, or None for any other office."""
    t = re.sub(r"\s+", " ", office or "").strip().upper()
    if not t.startswith("U.S."):
        return None
    m = re.fullmatch(r"U\.S\. REPRESENTATIVE, DIST (I|II)", t)
    if m:
        return house_id("HI", ROMAN[m.group(1)])
    if "SENAT" in t:
        raise SystemExit(f"Hawaii: a U.S. Senate contest is listed ({office!r}); Hawaii has no Senate race in 2026. Read the list again.")
    raise SystemExit(f"Hawaii: a federal contest that is not read ({office!r})")


def text(cell):
    return re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", cell)).replace("\xa0", " ")).strip()


def grid_rows(page):
    """Every row of one page of the report's grid, the kept columns only."""
    heads = [text(h) for h in re.findall(r'<th[^>]*class="rgHeader[^"]*"[^>]*>(.*?)</th>', page, re.S)]
    if not all(k in heads for k in KEEP) or len(set(heads)) != len(heads):
        raise SystemExit(f"Hawaii: the Candidate Report's columns changed ({[h for h in heads if h in KEEP]})")
    idx = {k: heads.index(k) for k in KEEP}
    for tr in re.findall(r'<tr class="(?:rgRow|rgAltRow)"[^>]*>(.*?)</tr>', page, re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        if len(cells) != len(heads):
            raise SystemExit("Hawaii: a Candidate Report row does not line up with the grid's headings")
        yield {k: text(cells[i]) for k, i in idx.items()}


def form(page):
    """The form's hidden fields and lists as a browser posts them."""
    fields = {}
    for tag in re.findall(r'<input[^>]*type="hidden"[^>]*>', page):
        name, value = re.search(r'name="([^"]+)"', tag), re.search(r'value="([^"]*)"', tag)
        if name:
            fields[name.group(1)] = H.unescape(value.group(1)) if value else ""
    for name, body in re.findall(r'<select[^>]*name="([^"]+)"[^>]*>(.*?)</select>', page, re.S):
        chosen = re.search(r'<option selected="selected" value="([^"]*)"', body) or re.search(r'<option[^>]*value="([^"]*)"', body)
        fields[name] = chosen.group(1) if chosen else ""
    return fields


def read_report(path, say):
    """The U.S. Representative rows of the 2026 Candidate Report, every page read; kept on disk (kept columns only) for two days."""
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < 2 * 86400:
        return json.load(open(path, encoding="utf-8"))
    opener = build_opener(HTTPCookieProcessor(CookieJar()))

    def fetch(fields=None):
        data = urllib.parse.urlencode(fields).encode() if fields is not None else None
        headers = {"User-Agent": net.UA, "Accept": "text/html"}
        if data:
            headers.update({"Content-Type": "application/x-www-form-urlencoded", "Referer": REPORT})
        with opener.open(Request(REPORT, data=data, headers=headers), timeout=120) as r:
            return r.read().decode("utf-8", "replace")

    page = fetch()
    chosen = re.search(r'<select[^>]*ddlElection[^>]*>.*?<option selected="selected" value="94">([^<]*)</option>', page, re.S)
    if not chosen or chosen.group(1).strip() != "2026 Candidate Report":
        raise SystemExit(f"Hawaii: {REPORT} is no longer the 2026 Candidate Report")
    m = re.search(r"<strong>(\d+)</strong>\s*items in\s*<strong>(\d+)</strong>", page)
    if not m:
        raise SystemExit("Hawaii: the Candidate Report no longer shows its row count")
    items, pages = int(m.group(1)), int(m.group(2))
    rows = list(grid_rows(page))
    for n in range(2, pages + 1):
        # the Next Page button's name changes with the pager's numbers (ctl28, then ctl30 from page 11), so it is found by its title
        nxt = re.search(r'<input type="submit" name="([^"]+)"[^>]*?title="Next Page"[^>]*>', page)
        if not nxt or "return false" in nxt.group(0):
            raise SystemExit(f"Hawaii: page {n - 1} of the Candidate Report has no Next Page button")
        fields = form(page)
        fields.update({"__EVENTTARGET": "", "__EVENTARGUMENT": "", nxt.group(1): " "})
        time.sleep(1.5)
        page = fetch(fields)
        cur = re.search(r'class="rgCurrentPage"[^>]*>\s*<span>(\d+)</span>', page)
        if not cur or int(cur.group(1)) != n:
            raise SystemExit(f"Hawaii: asked for page {n} of the Candidate Report and got {cur.group(1) if cur else 'no page'}")
        rows += list(grid_rows(page))
    if len(rows) != items:
        raise SystemExit(f"Hawaii: the Candidate Report counts {items} rows; {len(rows)} were read")
    if len({tuple(r.values()) for r in rows}) != len(rows):
        raise SystemExit("Hawaii: the Candidate Report gave the same row twice; its pager may have changed")
    fed = [r for r in rows if race_of(r["Contests"])]
    kept = {"title": "2026 Candidate Report", "url": REPORT, "items": items, "pages": pages, "rows": fed}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(kept, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    say(f"      2026 Candidate Report: {items} rows on {pages} pages, {len(fed)} for Congress")
    return kept


def fetch_results(folder, say):
    """The certified primary summary (text and PDF), after checking the results page still heads them Certified; 30 days."""
    meta_path = os.path.join(folder, "hi_2026_primary_results_meta.json")
    paths = {k: os.path.join(folder, local) for k, (_name, local) in FILES.items()}
    if not (os.path.exists(meta_path) and all(os.path.exists(p) for p in paths.values())
            and time.time() - os.path.getmtime(meta_path) < 30 * 86400):
        page = net.get(RESULTS_PAGE, accept="text/html").decode("utf-8", "replace")
        start = page.find('id="tab-2026"')
        block = page[start:page.find("To Top", start)] if start >= 0 else ""
        words = re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", block)))
        if "Primary Election August 8, 2026" not in words or "Certified Reports" not in words or "Certified Text Files" not in words:
            raise SystemExit("Hawaii: the results page no longer heads the August 8, 2026 primary's files Certified; "
                             "uncertified figures are never stored")
        for name, _local in FILES.values():
            if f"2026 Primary/{name}" not in block:
                raise SystemExit(f"Hawaii: the results page no longer links the 2026 primary's {name}")
        for key, (name, _local) in FILES.items():
            if os.path.exists(paths[key]):
                os.remove(paths[key])
            net.download(RESULTS + name, paths[key], max_age_days=30, say=say)
        json.dump({"heading": "Primary Election August 8, 2026", "certified": True, "page": RESULTS_PAGE,
                   "urls": {k: RESULTS + name for k, (name, _l) in FILES.items()}}, open(meta_path, "w", encoding="utf-8"), indent=1)
        say("      results page: Primary Election August 8, 2026, Certified Reports and Certified Text Files")
    if open(paths["summary"], "rb").read(16) != b"#FormatVersion 1":
        raise SystemExit("Hawaii: summary.txt does not open with #FormatVersion 1; delete it and run again")
    if open(paths["pdf"], "rb").read(5) != b"%PDF-":
        raise SystemExit("Hawaii: histatewide.pdf is not a PDF; delete it and run again")
    return paths, json.load(open(meta_path, encoding="utf-8"))


def primary_votes(path):
    """{(race, code): [(name as printed, votes)]} for every federal contest of the certified summary, and the office totals."""
    with open(path, encoding="utf-8-sig", newline="") as fh:
        table = list(csv.reader(fh, delimiter="\t"))
    heads = [h.lstrip("#").strip() for h in table[1]]
    if not all(k in heads for k in SUMMARY_KEEP):
        raise SystemExit(f"Hawaii: summary.txt's columns changed ({[h for h in heads if h in SUMMARY_KEEP]})")
    idx = {k: heads.index(k) for k in SUMMARY_KEEP}
    out, seen_ids = collections.OrderedDict(), {}
    for r in table[2:]:
        if not any(c.strip() for c in r):
            continue
        if len(r) < len(heads):
            raise SystemExit("Hawaii: a line of summary.txt is shorter than its heading")
        c = {k: r[i].strip() for k, i in idx.items()}
        race = race_of(c["Contest Title"])
        if not race:
            continue
        if c["Contest Party"] not in SECTION:
            raise SystemExit(f"Hawaii: a federal contest of a section that is not read ({c['Contest Title']} - {c['Contest Party']})")
        code = SECTION[c["Contest Party"]]
        if seen_ids.setdefault(c["Contest ID"], (race, code)) != (race, code):
            raise SystemExit(f"Hawaii: summary.txt contest {c['Contest ID']} names two offices")
        if c["Counted Precincts"] != c["Total Precincts"]:
            raise SystemExit(f"Hawaii: {c['Contest Title']} ({c['Contest Party']}) has counted {c['Counted Precincts']} of "
                             f"{c['Total Precincts']} precincts")
        mail, person, total = int(c["Mail Votes"]), int(c["In-Person Votes"]), int(c["Total Votes"])
        if mail + person != total:
            raise SystemExit(f"Hawaii: {c['Candidate Name']}'s mail and in-person votes do not make the total ({mail} + {person} != {total})")
        if re.search(r"write[- ]?in", c["Candidate Name"], re.I):
            raise SystemExit(f"Hawaii: summary.txt reports a write-in line for {c['Contest Title']}; read how it is counted")
        out.setdefault((race, code), []).append((re.sub(r"\s+", " ", c["Candidate Name"]), total))
    return out


def pdf_check(path, votes):
    """Control: the Final Summary Report prints every federal candidate's name beside the same total. Returns its print date."""
    text_lines = [t for _p, _y, t in lines(path)]
    head = "\n".join(text_lines[:8])
    for words in ("PRIMARY ELECTION 2026 - State of Hawaii - Statewide", "August 8, 2026", "SUMMARY REPORT", "FINAL"):
        if words not in head:
            raise SystemExit(f"Hawaii: histatewide.pdf's heading no longer says {words!r}")
    whole = "\n".join(re.sub(r"\s+", " ", t) for t in text_lines)
    for (race, code), field in votes.items():
        n = int(race[-2:])
        section = {v: k for k, v in SECTION.items()}[code]
        if f"U.S. Representative, Dist {'I' * n} - {section}" not in whole:
            raise SystemExit(f"Hawaii: histatewide.pdf has no heading for {race} {code}")
        for name, v in field:
            if f"{name} {v:,}" not in whole:
                raise SystemExit(f"Hawaii: histatewide.pdf does not print {name} with {v:,} votes ({race} {code})")
    m = re.search(r"Printed on: (\d\d)/(\d\d)/(\d{4})", head)
    return f"{m.group(3)}-{m.group(1)}-{m.group(2)}" if m else ""


def load(con, cache, say=print):
    net.patient_lookups()
    folder = os.path.join(cache, "hi")
    report_path = os.path.join(folder, "hi_2026_candidate_report_federal.json")
    report = read_report(report_path, say)
    paths, meta = fetch_results(folder, say)

    rec = sqlite3.connect(f"file:{os.path.join(HERE, 'congress_119.sqlite')}?mode=ro", uri=True)
    fixed = {}
    for full, first, last in rec.execute("SELECT official_full, first_name, last_name FROM legislators WHERE is_current = 1 AND state = 'HI'"):
        for form_ in (full, f"{first} {last}"):
            if form_:
                fixed[fold(form_)] = form_
    rec.close()

    def shown(printed):
        """'KEOHOKALOLE, Jarrett K.' -> 'Jarrett K. Keohokalole'."""
        family, _, given = re.sub(r"\s+", " ", printed).partition(",")
        if not given.strip():
            raise SystemExit(f"Hawaii: a name not printed 'FAMILY, Given' ({printed!r})")
        name = f"{given.strip()} {proper(family.strip())}"
        return fixed.get(fold(name), name)

    counts = collections.Counter(r["Status"] for r in report["rows"])
    odd = set(counts) - {ON, LOST, NEVER, *OFF}
    if odd:
        raise SystemExit(f"Hawaii: a federal row of the Candidate Report has a status that is not read ({sorted(odd)})")
    by_status = collections.defaultdict(dict)       # (race, code) -> {folded name: (printed, party, status)}
    rows, order, nominee = [], collections.Counter(), {}
    for r in report["rows"]:
        race = race_of(r["Contests"])
        if r["Party"] not in REPORT_PARTY:
            raise SystemExit(f"Hawaii: a candidate for {r['Contests']} of a party that is not read ({r['Party']!r})")
        code, party = REPORT_PARTY[r["Party"]], proper(r["Party"])
        if r["Status"] in (ON, LOST, *OFF):
            by_status[(race, code)][fold(r["Ballot Name"])] = (r["Ballot Name"], party, r["Status"])
        if r["Status"] != ON:
            continue
        if (race, code) in nominee:
            raise SystemExit(f"Hawaii: two {party} candidates for {race} are marked In General")
        nominee[(race, code)] = fold(r["Ballot Name"])
        order[race] += 1
        rows.append((race, "general", "2026-11-03", shown(r["Ballot Name"]), party, party_code(party), order[race], 0, 0,
                     None, None, None, None, None, "hi-oe-2026-candidate-report", CAPS))
    races = {r[0] for r in con.execute("SELECT race_id FROM races WHERE state = 'HI'")}
    if set(order) != races:
        raise SystemExit(f"Hawaii: the Candidate Report's races marked In General are {sorted(order)}, not {sorted(races)}")

    votes = primary_votes(paths["summary"])
    printed_on = pdf_check(paths["pdf"], votes)
    on_primary = {key: {f for f, (_p, _pty, st) in names.items() if st in (ON, LOST)} for key, names in by_status.items()}
    on_primary = {k: v for k, v in on_primary.items() if v}
    if set(votes) != set(on_primary):
        raise SystemExit(f"Hawaii: the primary sections in the results and in the Candidate Report differ ({sorted(set(votes) ^ set(on_primary))})")
    office_total = collections.Counter()
    for (race, _code), field in votes.items():
        office_total[race] += sum(v for _n, v in field)
    fields = 0
    for (race, code), field in votes.items():
        names = by_status[(race, code)]
        if {fold(n) for n, _v in field} != on_primary[(race, code)]:
            raise SystemExit(f"Hawaii: the results' {race} {code} candidates are not the Candidate Report's")
        top = max(v for _n, v in field)
        leaders = [n for n, v in field if v == top]
        if len(leaders) > 1:
            raise SystemExit(f"Hawaii: the {race} {code} section is tied at the top ({leaders}); read how it was settled")
        leader = leaders[0]
        note_leader = None
        if code == "NP":
            partisan = sorted((v, n) for k in votes if k[0] == race and k[1] != "NP" and k in nominee
                              for n, v in votes[k] if fold(n) == nominee[k])       # each party nominee's primary votes
            lowest = partisan[0] if partisan else None
            qualifies = top >= 0.10 * office_total[race] or (lowest is not None and top >= lowest[0])
            if qualifies != (names[fold(leader)][2] == ON):
                raise SystemExit(f"Hawaii: {leader} led the {race} nonpartisan section with {top:,} votes; the rule says "
                                 f"{'qualified' if qualifies else 'not qualified'}, the Candidate Report marks {names[fold(leader)][2]}")
            if not qualifies and lowest:
                note_leader = (f"Led the nonpartisan section but did not qualify for November: Hawaii puts a nonpartisan candidate on "
                               f"the general ballot only with at least 10 percent of the votes cast for the office or as many votes as "
                               f"the party nominee with the fewest ({shown(lowest[1])}, {lowest[0]:,}). {CAPS}")
        elif names[fold(leader)][2] != ON:
            raise SystemExit(f"Hawaii: {leader} led the {race} {code} section; the Candidate Report marks {names[fold(leader)][2]}")
        for n, _v in field:
            if n != leader and names[fold(n)][2] != LOST:
                raise SystemExit(f"Hawaii: {n} lost the {race} {code} section; the Candidate Report marks {names[fold(n)][2]}")
        if len(field) < 2:
            continue
        fields += 1
        total = sum(v for _n, v in field)
        for n, v in sorted(field, key=lambda nv: -nv[1]):
            printed, party, status = names[fold(n)]
            won = status == ON
            rows.append((race, f"primary-{code}", PRIMARY, shown(printed), party, party_code(party), None, 0, 0, v,
                         round(100 * v / total, 1) if total else None, "advanced" if won else "lost", None, None,
                         "hi-oe-2026-primary-results", note_leader if n == leader and note_leader else CAPS))

    general = [r for r in rows if r[1] == "general"]
    left = {s: counts.get(s, 0) for s in OFF}
    fetched_report = dt.datetime.fromtimestamp(os.path.getmtime(report_path)).strftime("%Y-%m-%d")
    with con:
        con.execute("DELETE FROM list_gaps WHERE state = 'HI'")
        con.execute("DELETE FROM candidates WHERE race_id LIKE '2026-HI-%'")
        con.executemany("INSERT OR REPLACE INTO candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        record_source(con, "hi-oe-2026-candidate-report", path=report_path, level="federal", state="HI", kind="official candidate list",
                      agency="State of Hawaii Office of Elections",
                      title="2026 Candidate Report: U.S. Representative, Districts I and II", url=REPORT, rows=len(report["rows"]),
                      note=f"Linked as \"Candidate Report\" from {REPORT_LINK}. All {report['items']} rows on {report['pages']} pages read "
                           f"through the grid's own pager on {fetched_report} and counted against its total; only Contests, Party, Ballot "
                           "Name, Issued, Filed and Status read; legal name, mailing address, phone, e-mail and website never read or kept. "
                           f"November ballot: the rows marked In General ({len(general)}). Marked In Primary (on the primary ballot, not "
                           f"nominated): {counts.get(LOST, 0)}. Took out nomination papers and never filed them (Issued; not candidates): "
                           f"{counts.get(NEVER, 0)}. Withdrawn: {left['Withdrawn']}; void: {left['Void']}; left off. The report gives no "
                           "ballot positions; its alphabetical order is kept. Hawaii's ballots have no write-in line.")
        record_source(con, "hi-oe-2026-primary-results", path=paths["summary"], level="federal", state="HI", kind="official results",
                      agency="State of Hawaii Office of Elections",
                      title="Primary Election August 8, 2026, Certified Text Files: Statewide Summary (summary.txt)",
                      url=meta["urls"]["summary"], published=printed_on, rows=len(rows) - len(general),
                      note=f"Listed under \"{meta['heading']}\" on {RESULTS_PAGE}, headed Certified. Every federal contest counted all "
                           "its precincts; mail and in-person votes make each total; each section's candidates are the Candidate "
                           "Report's; each party's leader is the report's nominee. Hawaii has no write-in votes, so pct is of the "
                           "candidates' votes; the Office's own percentages include blank, over and invalid votes. Published date: the "
                           "print date of the matching Final Summary Report.")
        record_source(con, "hi-oe-2026-primary-summary-pdf", path=paths["pdf"], level="federal", state="HI", kind="official results",
                      agency="State of Hawaii Office of Elections",
                      title="Primary Election August 8, 2026, Certified Reports: Statewide Summary (Summary Report, Final)",
                      url=meta["urls"]["pdf"], published=printed_on, rows=sum(len(f) for f in votes.values()),
                      note="Control: every federal candidate's name is printed beside the same total as in summary.txt.")
    say(f"    Hawaii: 2 House districts (no Senate race this year), {len(general)} candidates on the November ballot from the Office "
        f"of Elections' 2026 Candidate Report; {fields} primary sections with a field, votes from the certified August 8 summary, "
        f"checked against the Final Summary Report")
    return len(general)
