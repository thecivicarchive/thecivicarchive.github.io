"""
Oklahoma: the State Election Board's own lists, read in four pieces.

  The November ballot: the Board's "NOVEMBER / 2026 List of Elections" (hosting.okelections.us/electionlist.html, the
  page oklahoma.gov/elections/elections-results/next-election.html links as "November 3 General Election"), an HTML
  page that lists, county by county for all 77 counties, every office on that county's November 3 ballot and under
  it each candidate as "NAME, PARTY". The U.S. Senator and U.S. Representative races are taken from it. A district
  that spans several counties is listed once per county, and every county's list must agree; a race whose counties
  disagree is left out and named. The list's order is kept as the ballot order: it follows the Board's public drawing
  of July 8, 2026 (Republican, Democratic, Libertarian, then independent candidates in lot order). The page carries
  names, parties and offices only; it is cached whole. The same address is reused for each election, so a copy whose
  title is not the November 2026 list is refused and the cached copy kept.

  The primaries: the Board's "Candidates for Office 2026" (the 2026 Candidate List Book, a PDF linked from
  oklahoma.gov/elections/candidates/2026-candidate-filing-information.html), every candidate who filed April 1-3,
  2026, as compiled at 5 p.m. on April 3, grouped by office, district and party, read with ballot/pdftext.py. Each
  entry is one line of fixed-width type: the filing number, the name, and the candidate's city. Only the filing
  number and the name columns are ever read (by character position, the type being 6 points to a character); the
  city is never read or kept. A long name wraps onto a second line in the name column, which is joined.

  Withdrawals: the Board's "2026 Candidate Withdrawals" page (columns Number, Name, Office, Date), matched to the book
  by filing number. A candidate who withdrew before the June 16 primary was not on its ballot and is left out; one
  who withdrew after it is kept in the primary field, with a note. Contests of candidacy: the Board's "2026 Contests
  of Candidacy" page is read only to make sure none concerns a federal office (a contest for one stops the loader).

A party primary is a field when two or more of the party's candidates were on its June 16 ballot. The nominee is the
party's candidate on the November list, and every November candidate of a party must be one of that party's filers.

  The votes: the official results of the June 16 primary and the August 25 runoff are published only on the Board's
  results site, which answers scripts with 403 Forbidden. Both elections were marked "Official Results" there when
  their two export files (the site's own Export menu: <date>_StateResults.csv, one row per candidate per contest, and
  <date>_CountyResults_csv.zip, the same county by county) were saved through a browser on 2026-10-03 into
  ballot_cache/ok/results/<yyyymmdd>/; the loader reads them from there and downloads nothing. Columns are read by
  heading: the office, party, county owner, precincts, the candidate's number, name and party, and the votes. Each
  contest is checked before its votes are stored: every precinct reporting, each candidate's absentee, early and
  election-day votes adding up to the total, and the contest's total (and each candidate's) equal to the sum of its
  county rows. A contest that fails is stored without votes, as before, and named. The results print names in
  capitals; they are paired with the names already loaded (the same letters, else the same family name and a given
  name that fits, one to one) and the loaded spelling is kept. A majority nominates; without one the top two went to
  the August 25 runoff (26 O.S. 1-103), stored as its own election (runoff-REP, runoff-DEM, 2026-08-25), and its
  winner is the nominee; where one of the top two is on the Board's list of withdrawals after June 16 and the runoff
  results hold no contest, no runoff was held and the other is the nominee (Congressional District 1's Republicans).
  The winner the votes show must be the party's candidate on the November list. pct is the
  share of the contest's votes (the results carry no write-in line). When the files are not there, the fields carry no
  votes and who advanced comes from the November list.

Names are printed in capitals in both lists; the page shows them in ordinary capitals (a sitting member with the
roster's own capitals where the list's words are the roster's) and says so. Parties are printed in full and shown
in ordinary capitals: REPUBLICAN Republican, DEMOCRAT Democrat, LIBERTARIAN Libertarian, INDEPENDENT Independent.
"""

import csv
import hashlib
import html as H
import io
import json
import os
import re
import sqlite3
import time
import zipfile
from collections import Counter
from datetime import datetime

from ballot.common import HERE, fold, house_id, name_parts, party_code, record_source, senate_id
from ballot.lists.tx import proper
from ballot.match import fits
from ballot.pdftext import PDF, join, rows as pdf_rows
from states import net

LIST_URL = "https://hosting.okelections.us/electionlist.html"
BOOK_URL = ("https://oklahoma.gov/content/dam/ok/en/elections/candidate-filing-archives/2026-candidate-filing-archives/"
            "2026-candidate-list-book.pdf")
WITHDRAWALS_URL = "https://oklahoma.gov/elections/candidates/2026-candidate-filing-information/2026-candidate-withdrawals.html"
CONTESTS_URL = "https://oklahoma.gov/elections/candidates/2026-candidate-filing-information/2026-contests-of-candidacy.html"
RESULTS_URL = "https://results.okelections.us/OKER/?elecDate=20260616"
PRIMARY, RUNOFF = "2026-06-16", "2026-08-25"
PARTIES = {"REPUBLICAN": "Republican", "DEMOCRAT": "Democrat", "LIBERTARIAN": "Libertarian", "INDEPENDENT": "Independent"}
CODES = {"Republican": "REP", "Democrat": "DEM", "Libertarian": "LIB"}          # independents are not in a primary
FEDERAL_OFFICE = re.compile(r"\b(UNITED STATES|U\.\s?S\.)\s+(SENATOR|REPRESENTATIVE)\b", re.I)
LEFT, CW = 72.0, 6.0                          # the book's left margin and its fixed-width type, points per character
NAME_COLS = (7, 30)                           # filing number in columns 0-4, the name in 7-29; the city after is never read
CAPS = "Oklahoma's list prints names in capitals; they are shown here in ordinary capitals."
CAPS_BOOK = "Oklahoma's candidate list prints names in capitals; they are shown here in ordinary capitals."

# the official results, as the Board's results site exports them (saved through a browser; the site refuses scripts)
RESULTS_SAVED = "2026-10-03"
ELECTION_RESULTS = {"primary": ("20260616", PRIMARY, "Primary Election, June 16, 2026"),
                    "runoff": ("20260825", RUNOFF, "Runoff Primary Election, August 25, 2026")}
RESULT_COLUMNS = ("elec_date", "entity_description", "race_number", "race_description", "race_party", "tot_race_prec", "race_prec_reporting",
                  "cand_number", "cand_name", "cand_party", "cand_absmail_votes", "cand_early_votes", "cand_elecday_votes",
                  "cand_tot_votes", "race_county_owner")       # read by heading; nothing else in the files is read
VOTE_PARTS = ("cand_absmail_votes", "cand_early_votes", "cand_elecday_votes")
RUNOFF_NOTE = "No candidate had a majority on June 16; the top two went to the August 25 runoff."
WALKOVER_NOTE = ("No candidate had a majority on June 16, and the other of the top two withdrew afterwards (the State Election "
                 "Board's list of withdrawals), so no runoff was held.")
SRC_PRIMARY_RESULTS, SRC_RUNOFF_RESULTS = "ok-seb-2026-primary-results", "ok-seb-2026-runoff-results"


def results_url(ymd):
    return f"https://results.okelections.us/OKER/?elecDate={ymd}"


def read_export(data, need, label):
    """The rows of one of the Board's export files as {heading: cell} for the headings in `need`, read by heading. The
    export writes a comma after a blank last cell, so a row may carry one extra, empty cell; any other count stops."""
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise SystemExit(f"Oklahoma: {label} is not UTF-8 text; it is not the Board's export this loader was checked against") from None
    rows = list(csv.reader(io.StringIO(text)))
    head = [h.strip() for h in rows[0]] if rows else []
    missing = [h for h in need if h not in head]
    if missing:
        raise SystemExit(f"Oklahoma: {label} has no column {', '.join(missing)}; it is not the Board's export this loader was checked against")
    at = {h: head.index(h) for h in need}
    out = []
    for n, r in enumerate(rows[1:], start=2):
        if not r:
            continue
        if len(r) == len(head) + 1 and not r[-1].strip():
            r = r[:-1]
        if len(r) != len(head):
            raise SystemExit(f"Oklahoma: line {n} of {label} has {len(r)} cells for {len(head)} headings")
        out.append({h: r[i].strip() for h, i in at.items()})
    return out


def official_results(cache, kind):
    """One election's official results from the Board's two export files in ballot_cache/ok/results/<yyyymmdd>/, or
    None when they are not saved: {"contests": {race number: contest}, ...}. Each contest is checked: every precinct
    reporting, each candidate's absentee, early and election-day votes adding up to the total, its rows agreeing on the
    office, party, county and precincts, and the contest's total (and each candidate's) equal to the sum of its county
    rows. A contest that fails carries its problems and "ok" False, and its votes are not to be stored."""
    ymd, date, title = ELECTION_RESULTS[kind]
    folder = os.path.join(cache, "ok", "results", ymd)
    paths = (os.path.join(folder, f"{ymd}_StateResults.csv"), os.path.join(folder, f"{ymd}_CountyResults_csv.zip"))
    if not all(os.path.exists(p) for p in paths):
        return None
    day = f"{int(ymd[4:6])}/{int(ymd[6:])}/{ymd[:4]}"
    label = os.path.basename(paths[0])

    def count(cell, where):
        if not re.fullmatch(r"\d+", cell):
            raise SystemExit(f"Oklahoma: {where} holds a vote count that is not a whole number")
        return int(cell)

    contests = {}
    for r in read_export(open(paths[0], "rb").read(), RESULT_COLUMNS, label):
        if r["elec_date"] != day:
            raise SystemExit(f"Oklahoma: {label} holds a row dated {r['elec_date']}, not {day}")
        head = (re.sub(r"\s+", " ", r["race_description"]).upper(), r["race_party"].upper(), r["race_county_owner"].upper(),
                (r["tot_race_prec"], r["race_prec_reporting"]), re.sub(r"\s+", " ", r["entity_description"]).upper())
        c = contests.setdefault(r["race_number"], {"number": r["race_number"], "desc": head[0], "party": head[1], "owner": head[2],
                                                   "precincts": head[3], "entity": head[4], "cands": [], "problems": [],
                                                   "date": date, "kind": kind})
        if (c["desc"], c["party"], c["owner"], c["precincts"], c["entity"]) != head:
            c["problems"].append("its rows do not agree on the office, party, county, precincts or the body holding it")
        votes = count(r["cand_tot_votes"], label)
        if sum(count(r[p], label) for p in VOTE_PARTS) != votes:
            c["problems"].append("a candidate's absentee, early and election-day votes do not add up to the candidate's total")
        if any(x["number"] == r["cand_number"] for x in c["cands"]):
            c["problems"].append("a candidate is listed twice")
        c["cands"].append({"number": r["cand_number"], "name": re.sub(r"\s+", " ", r["cand_name"]), "party": r["cand_party"].upper(),
                           "votes": votes})
    zf = zipfile.ZipFile(paths[1])
    inner = [n for n in zf.namelist() if n.lower().endswith(".csv")]
    if len(inner) != 1:
        raise SystemExit(f"Oklahoma: {os.path.basename(paths[1])} does not hold exactly one CSV file")
    by_cand, by_race, counties, orphans = Counter(), Counter(), {}, 0
    for r in read_export(zf.read(inner[0]), RESULT_COLUMNS + ("county",), inner[0]):
        if r["elec_date"] != day:
            raise SystemExit(f"Oklahoma: {inner[0]} holds a row dated {r['elec_date']}, not {day}")
        if r["race_number"] not in contests:
            orphans += 1
            continue
        v = count(r["cand_tot_votes"], inner[0])
        by_cand[(r["race_number"], r["cand_number"])] += v
        by_race[r["race_number"]] += v
        counties.setdefault(r["race_number"], set()).add(r["county"].upper())
    for num, c in contests.items():
        c["total"], c["county_total"], c["counties"] = sum(x["votes"] for x in c["cands"]), by_race[num], len(counties.get(num, ()))
        if not c["counties"]:
            c["problems"].append("it has no county rows")
        elif c["county_total"] != c["total"]:
            c["problems"].append(f"its total ({c['total']:,}) is not the sum of its county rows ({c['county_total']:,})")
        elif any(by_cand[(num, x["number"])] != x["votes"] for x in c["cands"]):
            c["problems"].append("a candidate's total is not the sum of that candidate's county rows")
        if c["precincts"][0] != c["precincts"][1]:
            c["problems"].append(f"{c['precincts'][1]} of {c['precincts'][0]} precincts reporting")
        c["ok"] = not c["problems"]
    sha = [hashlib.sha256(open(p, "rb").read()).hexdigest() for p in paths]
    return {"kind": kind, "ymd": ymd, "date": date, "title": title, "contests": contests, "paths": paths, "sha": sha,
            "orphans": orphans, "url": results_url(ymd), "rows": sum(len(c["cands"]) for c in contests.values())}


def index_contests(results, race_fn):
    """{(race id, party code as printed: REP, DEM, LIB, or "" for a nonpartisan contest): contest} for the contests
    race_fn names; race_fn takes the office as printed, without its leading "FOR", and returns a race id or None."""
    out = {}
    for c in (results or {}).get("contests", {}).values():
        rid = race_fn(re.sub(r"^FOR\s+", "", c["desc"]))
        if rid is None:
            continue
        if (rid, c["party"]) in out:
            raise SystemExit(f"Oklahoma: the {results['title']} results hold two contests for {rid} ({c['party'] or 'nonpartisan'})")
        out[(rid, c["party"])] = c
    return out


def pair(loaded, printed):
    """{name as loaded: row of the results}, one to one both ways, or None: the same letters, else the same family name
    and a given name that fits (ballot.match.fits). The results print names in capitals; the loaded spelling is kept."""
    out, rest, left = {}, list(printed), []
    for name in loaded:
        hit = [p for p in rest if fold(p["name"]) == fold(name)]
        if len(hit) == 1:
            out[name] = hit[0]
            rest.remove(hit[0])
        else:
            left.append(name)
    for name in left:
        hit = [p for p in rest if fits(name_parts(name), name_parts(p["name"]))]
        if len(hit) != 1 or sum(1 for n in left if fits(name_parts(n), name_parts(hit[0]["name"]))) != 1:
            return None
        out[name] = hit[0]
        rest.remove(hit[0])
    return out if not rest and len(out) == len(loaded) else None


def settle(names, primary, runoff, two_go_on=False, withdrew=()):
    """What the official results say about one primary field: (result, problems). names: {key: name as loaded}.
    result is None when the primary's votes cannot be stored (the problems say why); else {"primary": {key: (votes, pct,
    outcome)}, "runoff": {key: (votes, pct, outcome)}, "to_runoff", "winner": key or None, "on": [keys that went on],
    "majority", "walkover": key or None}. A party primary (26 O.S. 1-103): a majority nominates; without one the top two
    go to the runoff, whose winner is the nominee; when one of the two withdrew after the primary (withdrew: the keys of
    those on the Board's list of withdrawals with a date after June 16) and the runoff results hold no contest, the other
    is the nominee and "walkover" names the one who withdrew. A nonpartisan judicial primary (two_go_on): a majority
    elects; without one the top two go on to November."""
    if primary is None:
        return None, ["no contest in the official results"]
    if not primary["ok"]:
        return None, list(primary["problems"])
    p = pair(list(names.values()), primary["cands"])
    if p is None:
        return None, ["the names in the official results do not match the filings one for one"]
    key_of = {n: k for k, n in names.items()}
    votes = {key_of[n]: row["votes"] for n, row in p.items()}
    total = primary["total"]
    ranked = sorted(votes, key=lambda k: -votes[k])
    out = {"runoff": {}, "to_runoff": False, "winner": None, "on": [], "majority": 2 * votes[ranked[0]] > total, "walkover": None}
    problems = []
    if out["majority"]:
        out["winner"], out["on"] = ranked[0], ranked[:1]
        if runoff is not None:
            problems.append("the August 25 results hold a runoff for it, though the primary had a majority")
    else:
        if len(ranked) > 2 and votes[ranked[1]] == votes[ranked[2]]:
            problems.append("a tie for second place")
        out["on"], out["to_runoff"] = ranked[:2], not two_go_on
        if not two_go_on:
            gone = [k for k in ranked[:2] if k in withdrew]
            if runoff is None and len(gone) == 1:
                stays = next(k for k in ranked[:2] if k not in gone)
                out.update(winner=stays, on=[stays], to_runoff=False, walkover=gone[0])
            elif runoff is None:
                problems.append("no majority, but no runoff for it in the August 25 results")
            elif not runoff["ok"]:
                problems.append("the runoff: " + "; ".join(runoff["problems"]))
            else:
                rp = pair([names[k] for k in out["on"]], runoff["cands"])
                if rp is None:
                    problems.append("the runoff's names are not the primary's top two")
                else:
                    rv = {key_of[n]: row["votes"] for n, row in rp.items()}
                    a, b = sorted(rv, key=lambda k: -rv[k])
                    if rv[a] == rv[b]:
                        problems.append("a tie in the runoff")
                    else:
                        out["winner"] = a
                        rt = runoff["total"]
                        out["runoff"] = {k: (rv[k], round(100 * rv[k] / rt, 1) if rt else None, "advanced" if k == a else "lost") for k in rv}
    out["primary"] = {k: (v, round(100 * v / total, 1) if total else None, "advanced" if k in out["on"] else "lost") for k, v in votes.items()}
    return out, problems


def federal_race(office):
    o = re.sub(r"\s+", " ", office).strip().upper()
    if o == "UNITED STATES SENATOR":
        return senate_id("OK", 2)
    m = re.fullmatch(r"UNITED STATES REPRESENTATIVE DISTRICT (\d+)", o)
    if m:
        return house_id("OK", int(m.group(1)))
    if FEDERAL_OFFICE.search(o):
        raise SystemExit(f"Oklahoma: a federal contest in the official results is not read ({office!r})")
    return None


def text(cell):
    return re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", cell)).replace("\xa0", " ")).strip()


def fetch_page(url, path, max_age_days, must=None, say=print):
    """A page kept on disk; refreshed when older than max_age_days, and never replaced by a copy lacking `must`."""
    fresh = os.path.exists(path) and time.time() - os.path.getmtime(path) < max_age_days * 86400
    if not fresh:
        try:
            page = net.get(url, accept="text/html").decode("utf-8", "replace")
        except Exception as e:  # noqa: BLE001
            if not os.path.exists(path):
                raise
            say(f"      could not refresh {os.path.basename(path)} ({e}); using the copy on disk")
            page = None
        if page is not None and must and must not in page:
            if not os.path.exists(path):
                raise SystemExit(f"Oklahoma: {url} is no longer the page this loader reads (no {must!r})")
            say(f"      {url} no longer shows {must!r}; using the copy on disk")
            page = None
        if page is not None:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8", newline="") as fh:
                fh.write(page)
            time.sleep(1.0)
    return open(path, encoding="utf-8").read()


def modified(page):
    m = re.search(r"Last Modified on\s*<span>([A-Z][a-z]{2} \d{1,2}, \d{4})</span>", page)
    return datetime.strptime(m.group(1), "%b %d, %Y").strftime("%Y-%m-%d") if m else ""


def race_of(heading):
    h = re.sub(r"\s+", " ", heading).strip().upper()
    if h == "UNITED STATES SENATOR":
        return senate_id("OK", 2)
    m = re.fullmatch(r"UNITED STATES REPRESENTATIVE - DISTRICT (\d+)", h)
    if m:
        return house_id("OK", int(m.group(1)))
    if FEDERAL_OFFICE.search(h):
        raise SystemExit(f"Oklahoma: a federal office on the List of Elections that is not read ({heading!r})")
    return None


def november(page):
    """{race: [(name, party)]} from every county's list, and the races whose counties disagree."""
    counties = re.findall(r"<option value=\"#(\d+)\">", page)
    parts = re.split(r"<A NAME=(\d+)>([^<]*)</A>", page)
    listed, seen = {}, 0
    for k in range(1, len(parts), 3):
        num, county, body = parts[k], parts[k + 1].strip(), parts[k + 2]
        if num == "00":
            continue
        seen += 1
        race = None
        for m in re.finditer(r"<TD WIDTH=(\d+)>(.*?)</TD>", body, re.S):
            width, t = m.group(1), text(m.group(2))
            if width == "990":                                   # a section: state, congressional, legislative officers
                race = None
            elif width == "980":                                 # an office
                race = race_of(t)
            elif width == "970" and race:
                name, _, label = t.rpartition(",")
                label = label.strip().upper()
                if not name or label not in PARTIES:
                    raise SystemExit(f"Oklahoma: a candidate line for {race} in {county} County is not read ({t!r})")
                listed.setdefault(race, {}).setdefault(county, []).append((re.sub(r"\s+", " ", name).strip(), PARTIES[label]))
    if seen != len(counties) or seen != 77:
        raise SystemExit(f"Oklahoma: the List of Elections has {seen} county sections for {len(counties)} counties in its menu (77 expected)")
    races, disagree = {}, []
    for race, by_county in listed.items():
        versions = {tuple(v) for v in by_county.values()}
        if len(versions) == 1:
            races[race] = (list(versions.pop()), len(by_county))
        else:
            disagree.append(race)
    return races, disagree


def grid(runs):
    """One printed line of the book as fixed-width characters, placed by where each run starts."""
    g = [" "] * 160
    for x0, _y, _size, t, _x1 in runs:
        c = round((x0 - LEFT) / CW)
        for i, ch in enumerate(t):
            if 0 <= c + i < len(g):
                g[c + i] = ch
    return "".join(g)


def book(path):
    """[{race, party, number, name}] for the federal offices, in the book's order, and whether it is the April 3 list."""
    pdf = PDF(open(path, "rb").read())
    pages = pdf.pages()
    cover = " ".join(join(rs) for _y, rs in pdf_rows(pdf, *pages[0]))
    if "Board April 1-3, 2026" not in cover or "April 3, 2026" not in cover:
        raise SystemExit("Oklahoma: the 2026 Candidate List Book's cover no longer reads as the April 1-3, 2026 filings")
    out, office, district, party, last, started = [], None, None, None, None, False
    for n, (page, res) in enumerate(pages, start=1):
        for y, runs in pdf_rows(pdf, page, res):
            heading = join(runs)                                  # compared against headings only; never printed
            if max(r[2] for r in runs) >= 11.5:                  # an office heading, 12-point
                if heading == "UNITED STATES SENATOR":
                    office, district, party, started = "S", None, None, True
                elif heading == "UNITED STATES REPRESENTATIVE":
                    office, district, party, started = "H", None, None, True
                elif started:
                    return out                                    # the federal offices come first; the next office ends them
                last = None
                continue
            if office is None:
                continue
            m = re.fullmatch(r"DISTRICT (\d+)", heading)
            if m and office == "H":
                district, party, last = int(m.group(1)), None, None
                continue
            if heading.upper() in PARTIES and len(heading) < 20:
                party, last = PARTIES[heading.upper()], None
                continue
            g = grid(runs)
            name = g[NAME_COLS[0]:NAME_COLS[1]].strip()
            if re.fullmatch(r"\d{5}", g[:5]) and not g[5:7].strip():
                if abs(min(r[0] for r in runs) - LEFT) > 1 or any(len(r[3]) >= 5 and abs((r[4] - r[0]) / len(r[3]) - CW) > 0.05 for r in runs):
                    raise SystemExit(f"Oklahoma: the book's type or margin changed on page {n}; its columns cannot be read by position")
                if not party or (office == "H" and not district):
                    raise SystemExit(f"Oklahoma: a candidate on page {n} of the book comes before its party or district heading")
                race = senate_id("OK", 2) if office == "S" else house_id("OK", district)
                last = [{"race": race, "party": party, "number": int(g[:5]), "name": name}, y]
                out.append(last[0])
            elif last and not g[:NAME_COLS[0]].strip() and name and 0 < last[1] - y < 15:
                last[0]["name"] += " " + name                     # a long name, wrapped in its own column
                last[1] = y
            else:
                raise SystemExit(f"Oklahoma: a line on page {n} of the candidate list book is not read (at {y:.0f} points)")
            if not re.fullmatch(r"[A-Z][A-Z0-9 .,'\"()-]*", last[0]["name"]):
                raise SystemExit(f"Oklahoma: filing number {last[0]['number']} on page {n} does not read as a name in capitals; "
                                 "the columns may have moved")
    raise SystemExit("Oklahoma: the candidate list book has no office after the federal ones")


def table(page, heads):
    """The rows of the page's table whose heading row is exactly `heads`, as lists of cell text."""
    for tb in re.findall(r"<table[^>]*>(.*?)</table>", page, re.S):
        trs = [[text(c) for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)] for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", tb, re.S)]
        if trs and trs[0] == list(heads):
            return trs[1:]
    raise SystemExit(f"Oklahoma: no table headed {heads} on the Board's page")


def load(con, cache, say=print):
    net.patient_lookups()
    folder = os.path.join(cache, "ok")
    list_path = os.path.join(folder, "ok_2026_general_list.html")
    book_path = os.path.join(folder, "ok_2026_candidate_list_book.pdf")
    wd_path, ct_path = os.path.join(folder, "ok_2026_withdrawals.json"), os.path.join(folder, "ok_2026_contests.json")

    page = fetch_page(LIST_URL, list_path, 2, must="NOVEMBER / 2026", say=say)
    if not re.search(r"<TITLE>\s*NOVEMBER / 2026\s+List of Elections\s*</TITLE>", page, re.I):
        raise SystemExit("Oklahoma: the cached List of Elections is not the November 2026 list")
    general, disagree = november(page)

    net.download(BOOK_URL, book_path, max_age_days=365)
    if open(book_path, "rb").read(5) != b"%PDF-":
        raise SystemExit(f"Oklahoma: {BOOK_URL} did not return a PDF")
    filers = book(book_path)

    # withdrawals (Number, Name, Office, Date) and contests of candidacy, kept on disk as those columns only
    if not os.path.exists(wd_path) or time.time() - os.path.getmtime(wd_path) > 2 * 86400:
        wp = net.get(WITHDRAWALS_URL, accept="text/html").decode("utf-8", "replace")
        wd = {"url": WITHDRAWALS_URL, "modified": modified(wp),
              "rows": [dict(zip(("number", "name", "office", "date"), r)) for r in table(wp, ("Number", "Name", "Office", "Date"))]}
        json.dump(wd, open(wd_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        time.sleep(1.0)
    wd = json.load(open(wd_path, encoding="utf-8"))
    if not os.path.exists(ct_path) or time.time() - os.path.getmtime(ct_path) > 7 * 86400:
        cp = net.get(CONTESTS_URL, accept="text/html").decode("utf-8", "replace")
        ct = {"url": CONTESTS_URL, "modified": modified(cp),
              "offices": [r[2] for r in table(cp, ("Cause", "Name", "Office", "Hearing")) if len(r) > 2 and r[2]]}
        json.dump(ct, open(ct_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    ct = json.load(open(ct_path, encoding="utf-8"))
    federal_contests = [o for o in ct["offices"] if FEDERAL_OFFICE.search(o)]
    if federal_contests:
        raise SystemExit(f"Oklahoma: a contest of candidacy concerns a federal office ({federal_contests}); read its outcome before loading")

    by_number = {f["number"]: f for f in filers}
    before, after = [], []
    for w in wd["rows"]:
        if not FEDERAL_OFFICE.search(w["office"]):
            continue
        f = by_number.get(int(w["number"]))
        if not f or name_parts(w["name"])[1] not in fold(f["name"]).split():
            raise SystemExit(f"Oklahoma: the withdrawal of {w['name']} (number {w['number']}) matches no federal filer in the book")
        when = datetime.strptime(w["date"], "%m/%d/%Y").strftime("%Y-%m-%d")
        f["withdrew"] = when
        (before if when < PRIMARY else after).append(f)

    rec = sqlite3.connect(f"file:{os.path.join(HERE, 'congress_119.sqlite')}?mode=ro", uri=True)
    fixed = {}
    for full, first, last in rec.execute("SELECT official_full, first_name, last_name FROM legislators WHERE is_current = 1 AND state = 'OK'"):
        for form in (full, f"{first} {last}"):
            if form:
                fixed[fold(form)] = form
    rec.close()

    def shown(caps):
        caps = re.sub(r"\s+", " ", caps).strip()
        if fold(caps) in fixed:
            return fixed[fold(caps)]
        t = re.sub(r"(['\"(])([a-z])", lambda m: m.group(1) + m.group(2).upper(), proper(caps))
        return re.sub(r"\b([A-Z])\.([a-z])\b", lambda m: m.group(1) + "." + m.group(2).upper(), t)      # R.o. -> R.O.

    def same(a, b):
        return fold(a) == fold(b)

    rows, nominee = [], {}
    for race, (cands, _n) in sorted(general.items()):
        for order, (name, party) in enumerate(cands, start=1):
            rows.append((race, "general", "2026-11-03", shown(name), party, party_code(party), order, 0, 0, None, None, None, None, None,
                         "ok-seb-2026-general-list", CAPS))
            filed = [f for f in filers if f["race"] == race and f["party"] == party]
            match = [f for f in filed if same(f["name"], name)] or \
                    [f for f in filed if name_parts(f["name"])[1] == name_parts(name)[1]]
            if len(match) != 1:
                raise SystemExit(f"Oklahoma: {name} ({party}, {race}) on the November list is not one {party} filer in the book")
            if match[0].get("withdrew"):
                raise SystemExit(f"Oklahoma: {name} ({race}) is on the November list but on the Board's list of withdrawals")
            if party in CODES:
                if (race, party) in nominee:
                    raise SystemExit(f"Oklahoma: two {party} candidates for {race} on the November list")
                nominee[(race, party)] = match[0]["number"]

    fields = {}
    for f in filers:
        if f["party"] in CODES and not (f.get("withdrew") and f["withdrew"] < PRIMARY):
            fields.setdefault((f["race"], f["party"]), []).append(f)
    # the official results of the June 16 primary and the August 25 runoff, when their export files are saved
    res = {k: official_results(cache, k) for k in ELECTION_RESULTS}
    found = {k: index_contests(res[k], federal_race) for k in res}
    with_field = {(race, CODES[party]) for (race, party), field in fields.items() if len(field) >= 2}
    problems, voted, nrunoffs = [], 0, 0
    for k in res:
        for key in sorted(set(found[k]) - with_field):
            problems.append(f"{key[0]} {key[1] or 'nonpartisan'}: a contest in the {ELECTION_RESULTS[k][2]} results for which the filings show no field")

    nfields = 0
    for (race, party), field in sorted(fields.items()):
        if (race, party) not in nominee:
            raise SystemExit(f"Oklahoma: the {party} primary for {race} has no candidate on the November list; read the results before loading")
        if len(field) < 2:
            continue
        nfields += 1
        code = CODES[party]
        got = None
        if res["primary"]:
            got, probs = settle({f["number"]: f["name"] for f in field}, found["primary"].get((race, code)),
                                found["runoff"].get((race, code)) if res["runoff"] else None,
                                withdrew={f["number"] for f in field if f.get("withdrew") and PRIMARY <= f["withdrew"] < RUNOFF})
            if got and not res["runoff"] and got["to_runoff"]:
                probs.append("no majority, and the August 25 results are not saved")
            if got and got["winner"] is not None and got["winner"] != nominee[(race, party)]:
                probs.append("the winner the official votes show is not the party's candidate on the November list; votes not stored")
                got = None
            if probs:
                problems.append(f"{race} {party}: " + "; ".join(probs))
            voted += bool(got)
        for f in field:
            note = CAPS_BOOK
            if f.get("withdrew"):
                day = datetime.strptime(f["withdrew"], "%Y-%m-%d")
                note = (f"Withdrew on {day:%B} {day.day}, {day.year}, after the June 16 primary (the State Election Board's list of "
                        f"withdrawals); not on the November list. {CAPS_BOOK}")
            if got:
                votes, pct, out = got["primary"][f["number"]]
                if out == "advanced" and got["to_runoff"]:
                    note = f"{RUNOFF_NOTE} {note}"
                elif out == "advanced" and got["walkover"]:
                    note = f"{WALKOVER_NOTE} {note}"
                src = SRC_PRIMARY_RESULTS
            else:
                votes = pct = None
                out, src = "advanced" if nominee[(race, party)] == f["number"] else "lost", "ok-seb-2026-candidate-list-book"
            rows.append((race, f"primary-{code}", PRIMARY, shown(f["name"]), party, party_code(party), None, 0, 0, votes, pct,
                         out, None, None, src, note))
        if got and got["runoff"]:
            nrunoffs += 1
            for f in field:
                if f["number"] in got["runoff"]:
                    votes, pct, out = got["runoff"][f["number"]]
                    rows.append((race, f"runoff-{code}", RUNOFF, shown(f["name"]), party, party_code(party), None, 0, 0, votes, pct,
                                 out, None, None, SRC_RUNOFF_RESULTS, CAPS_BOOK))

    gen_rows = [r for r in rows if r[1] == "general"]
    where = [f"{race.split('-')[-1]} in {n}" for race, (_c, n) in sorted(general.items())]
    wd_words = "; ".join(f"{shown(f['name'])} ({f['race']}, withdrew {f['withdrew']})" for f in before + after) or "none"
    with con:
        con.execute("DELETE FROM candidates WHERE race_id LIKE '2026-OK-%'")
        con.execute("DELETE FROM ballot_sources WHERE source_id IN (?, ?)", (SRC_PRIMARY_RESULTS, SRC_RUNOFF_RESULTS))
        con.executemany("INSERT OR REPLACE INTO candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        record_source(con, "ok-seb-2026-general-list", path=list_path, level="federal", state="OK", kind="official candidate list",
                      agency="Oklahoma State Election Board",
                      title="NOVEMBER / 2026 List of Elections (November 3, 2026 General Election), county by county: "
                            "United States Senator and United States Representative",
                      url=LIST_URL, rows=len(gen_rows),
                      note=f"Read for all 77 counties; every county's list of each federal race agreed "
                           f"({', '.join(where)} counties)"
                           + (f"; left out where counties disagreed: {', '.join(disagree)}" if disagree else "")
                           + ". The list's order is the ballot order of the Board's July 8, 2026 drawing (Republican, Democratic, "
                             "Libertarian, then independents in lot order). The list names no write-in candidates. Federal candidates "
                             f"on the Board's list of withdrawals, none of them on this list: {len(before) + len(after)} ({wd_words}).")
        record_source(con, "ok-seb-2026-candidate-list-book", path=book_path, level="federal", state="OK", kind="official candidate list",
                      agency="Oklahoma State Election Board",
                      title="Candidates for Office 2026, filed in the office of the State Election Board April 1-3, 2026 "
                            "(2026 Candidate List Book, compiled as of 5:00 p.m. April 3, 2026): United States Senator and "
                            "United States Representative",
                      url=BOOK_URL, published="2026-04-03", rows=len(filers),
                      note=f"Read for who was on each party's June 16, 2026 primary ballot: the filing number and name columns only, "
                           f"the city beside each name never read. Withdrawn before the primary, not on its ballot: "
                           f"{'; '.join(shown(f['name']) + ' (' + f['race'] + ')' for f in before) or 'none'}. The nominee is the party's "
                           f"candidate on the November list. "
                           + ("The votes and who went to the runoff come from the Board's official results (their own sources)."
                              if res["primary"] else
                              "Votes not loaded: the June 16 primary and August 25 runoff results are published only on the "
                              "Board's results site, which refuses scripts (403 Forbidden), and their export files are not saved; "
                              "which fields went to the runoff is not read."))
        for k, r in res.items():
            if not r:
                continue
            mine = {key: c for key, c in found[k].items() if key in with_field}
            bad = sorted(f"{key[0]} {key[1]}" for key, c in mine.items() if not c["ok"])
            record_source(con, SRC_PRIMARY_RESULTS if k == "primary" else SRC_RUNOFF_RESULTS, path=r["paths"][0], level="federal",
                          state="OK", kind="official results", agency="Oklahoma State Election Board",
                          title=f"Official results, {r['title']}: United States Senator and United States Representative",
                          url=r["url"], published="", rows=sum(len(c["cands"]) for c in mine.values()),
                          note=f"The Board's results site marked these results Official when its two export files were saved through a "
                               f"browser on {RESULTS_SAVED} (the site refuses scripts): {os.path.basename(r['paths'][0])}, one row per "
                               f"candidate per contest, and {os.path.basename(r['paths'][1])}, the same county by county (SHA-256 "
                               f"{r['sha'][1]}). Read by heading: the office, party, precincts, each candidate's name and votes. "
                               f"{len(mine)} federal contests; checked: every precinct reporting, each candidate's absentee, early and "
                               f"election-day votes adding up to the total, and each contest's total and each candidate's equal to the "
                               f"sum of the county rows"
                               + (f"; failed, so stored without votes: {', '.join(bad)}." if bad else
                                  " (all agree).")
                               + " Names are printed in capitals and paired with the names already loaded, whose spelling is kept.")
        record_source(con, "ok-seb-2026-withdrawals", path=wd_path, level="federal", state="OK", kind="official candidate list",
                      agency="Oklahoma State Election Board", title="2026 Candidate Withdrawals", url=WITHDRAWALS_URL,
                      published=wd.get("modified", ""), rows=len(before) + len(after),
                      note=f"Federal withdrawals, matched to the book by filing number: {wd_words}. Columns kept: Number, Name, Office, Date.")
        record_source(con, "ok-seb-2026-contests", path=ct_path, level="federal", state="OK", kind="official candidate list",
                      agency="Oklahoma State Election Board", title="2026 Contests of Candidacy", url=CONTESTS_URL,
                      published=ct.get("modified", ""), rows=0,
                      note=f"Checked: none of the {len(ct['offices'])} contests of candidacy concerns a federal office.")
    house = len({r[0] for r in gen_rows if "-H" in r[0]})
    say(f"    Oklahoma: {house} House districts and {'the' if any('-S' in r[0] for r in gen_rows) else 'no'} Senate race, "
        f"{len(gen_rows)} candidates on the November ballot (every county's list agrees"
        + (f"; left out where counties disagreed: {', '.join(disagree)}" if disagree else "")
        + f"); {nfields} party primaries with a field, from the April filings less {len(before)} withdrawn; "
        + (f"official votes stored for {voted} of them and {nrunoffs} August 25 runoffs, from the Board's saved results exports"
           if res["primary"] else "votes not loaded (the Board's results site refuses scripts and its exports are not saved), "
           "so who advanced comes from the November list"))
    for p in problems:
        say(f"      CHECK Oklahoma: {p}")
    return len(gen_rows)
