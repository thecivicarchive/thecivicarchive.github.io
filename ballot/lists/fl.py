"""
Florida: the Division of Elections' candidate list for the 2026 election cycle, federal offices, downloaded from its
Candidate Tracking System (downloadcanlist.asp posts to extractCanList.asp and answers with a tab-separated file).
Each row is one candidate with a status: Qualified (on the November ballot), Unopposed (elected without appearing
on the ballot, section 101.151, Florida Statutes), Defeated (lost a primary), Withdrew, or Did Not Qualify.

Florida's primaries are closed, one per party, on August 18, 2026; a party with a single qualified candidate holds
none. So a party's primary field is its candidates who were Qualified, Unopposed or Defeated, with the winner
marked. The file also carries addresses, telephone numbers, e-mail and treasurers' names; none of it is read.

The primary's votes are the Division's official results, from its Election Results Reporting System
(results.elections.myflorida.com, "August 18, 2026 Primary Election"):

  results extract   the site's Data Download Utility (downloadresults.asp posts its own form to ResultsExtract.Asp and
                    answers with a tab-separated file, 08182026Election.txt). The form's hidden field OfficialResults
                    must be Y, or no votes are stored. One row per county, party, contest and candidate: ElectionDate,
                    PartyCode, PartyName, RaceCode (USS United States Senator, USR United States Representative),
                    OfficeDesc, CountyCode, CountyName, Juris1num (the district), Juris2num, Precincts,
                    PrecinctsReporting, CanNameLast, CanNameFirst, CanNameMiddle, CanVotes. It holds results only; the
                    federal rows are read and the rest of the file is kept as published. A candidate's votes are the
                    sum of the county rows; every precinct must have reported, and the Senate contests must list all
                    67 counties.
  summary reports   the site's Summary Report for Federal Offices, one page per party (SummaryRpt.asp, Race=FED,
                    Party=REP or DEM). Each page must be headed "Official Results"; its statewide Total for each
                    candidate must equal the county sums, and its "% Votes" must equal the share computed here. The
                    line under a contest (the page's RunoffIndicator cell: "Machine Recount Completed") is kept as a
                    note on that field.

Florida has had no primary runoffs since 2002: the most votes wins. The results carry no write-in line (write-in
candidates are not on a Florida primary ballot), so a field's shares are of its candidates' votes. Candidates are
matched to the candidate list within their race and party by family name (suffixes set aside) and first given name,
or by the family name alone when it is the only one in the field; the names stored are the candidate list's, as for
November. The top vote-getter advanced; the candidate list's statuses (Qualified or Unopposed for the nominee,
Defeated for the rest) must agree, and any difference is printed. The 2026 Senate race is a special election for the
rest of the term (2026-FL-S3); its primaries are stored as primary-REP and primary-DEM like the House's.
"""

import csv
import html as H
import io
import os
import re
import time
import urllib.parse
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ballot.common import SUFFIXES, fold, house_id, party_code, record_source, senate_id
from states import net

PAGE = "https://dos.elections.myflorida.com/candidates/downloadcanlist.asp"
POST = "https://dos.elections.myflorida.com/candidates/extractCanList.asp"
FORM = {"elecID": "20261103-GEN", "office": "FED", "status": "All", "cantype": "STA"}
PRIMARY = "2026-08-18"
ON_BALLOT = ("Qualified", "Unopposed")

RESULTS = "https://results.elections.myflorida.com"
RES_DATE = "8/18/2026"
RES_TITLE = "August 18, 2026 Primary Election"
RES_PAGE = f"{RESULTS}/Index.asp?ElectionDate={RES_DATE}&DATAMODE="
RES_DOWNLOAD = f"{RESULTS}/downloadresults.asp?ElectionDate={RES_DATE}&DATAMODE="
RES_EXTRACT = f"{RESULTS}/ResultsExtract.Asp"
RES_SUMMARY = RESULTS + "/SummaryRpt.asp?ElectionDate=" + RES_DATE + "&Race=FED&Party={party}&DATAMODE="
RES_HEAD = b"ElectionDate\tPartyCode\tPartyName\tRaceCode\tOfficeDesc\tCountyCode\t"
RES_COLS = ("ElectionDate", "PartyCode", "RaceCode", "CountyCode", "Juris1num", "Juris2num", "Precincts", "PrecinctsReporting",
            "CanNameLast", "CanNameFirst", "CanNameMiddle", "CanVotes")
RES_FILE = "fl_2026_primary_official_results_extract.txt"
SUM_FILE = "fl_2026_primary_official_summary_federal_{party}.html"
RES_PARTIES = ("REP", "DEM")
COUNTIES = 67
CHALLENGE = re.compile(rb"(?i)just a moment|cf-chl|challenge-platform|captcha|access denied")


def fetch(path, max_age_days=2):
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < max_age_days * 86400:
        return
    net.patient_lookups()
    req = Request(POST, data=urllib.parse.urlencode(FORM).encode(), method="POST",
                  headers={"User-Agent": net.UA, "Referer": PAGE, "Content-Type": "application/x-www-form-urlencoded"})
    with urlopen(req, timeout=180) as r:
        data = r.read()
    if b"NameLast" not in data[:400]:
        raise SystemExit("Florida's candidate download did not answer with the candidate file; try again later")
    open(path, "wb").write(data)


# ---------- the official results of the August 18 primary ----------

class Blocked(Exception):
    pass


def ask(what, go, valid):
    """One request; asked at most twice more when the server refuses (403, 429, 503) or answers with a challenge page."""
    last = ""
    for attempt in range(3):
        try:
            data = go()
        except HTTPError as e:
            if e.code not in (403, 429, 503):
                raise Blocked(f"{what} answered HTTP {e.code}")
            last = f"HTTP {e.code}"
        except (URLError, OSError) as e:
            raise Blocked(f"{what} could not be reached ({e})")
        else:
            if valid(data):
                return data
            if not CHALLENGE.search(data[:20000]):
                raise Blocked(f"{what} did not answer with the expected file (it begins {data[:40]!r})")
            last = "a challenge page"
        if attempt < 2:
            time.sleep(15 * (attempt + 1))
    raise Blocked(f"{what} answered with {last} three times")


def results_files(folder, say, max_age_days=30):
    """{"extract": path, "REP": path, "DEM": path} for the official results, fetched when the cached set is older than
    max_age_days (the results are certified); (None, reason) when they cannot be had. A set saved by hand is used."""
    paths = {"extract": os.path.join(folder, RES_FILE)} | {p: os.path.join(folder, SUM_FILE.format(party=p.lower())) for p in RES_PARTIES}
    have = all(os.path.exists(p) and os.path.getsize(p) > 0 for p in paths.values())
    if have and all(time.time() - os.path.getmtime(p) < max_age_days * 86400 for p in paths.values()):
        return paths, None
    try:
        page = ask("the results site's Data Download Utility", lambda: net.get(RES_DOWNLOAD, accept="text/html"),
                   lambda d: b"ResultsExtract.Asp" in d)
        form = dict(re.findall(r'(?i)<INPUT\s+TYPE="hidden"\s+NAME="(\w+)"\s+VALUE="([^"]*)"', page.decode("cp1252", "replace")))
        if form.get("ElectionDate") != RES_DATE or RES_TITLE not in page.decode("cp1252", "replace"):
            raise Blocked("the Data Download Utility no longer offers the August 18, 2026 primary")
        if form.get("OfficialResults") != "Y":
            raise Blocked("the Data Download Utility does not offer official results (OfficialResults is not Y); unofficial figures are never stored")
        form["FormsButton2"] = "Download"

        def post():
            req = Request(RES_EXTRACT, data=urllib.parse.urlencode(form).encode(), method="POST",
                          headers={"User-Agent": net.UA, "Referer": RES_DOWNLOAD, "Content-Type": "application/x-www-form-urlencoded"})
            with urlopen(req, timeout=300) as r:
                return r.read()
        time.sleep(1.0)
        got = {"extract": ask("the results extract", post, lambda d: d.startswith(RES_HEAD))}
        for p in RES_PARTIES:
            time.sleep(1.0)
            got[p] = ask(f"the {p} Summary Report for Federal Offices", lambda p=p: net.get(RES_SUMMARY.format(party=p), accept="text/html"),
                         lambda d: f"<TITLE>{RES_TITLE}</TITLE>".encode() in d)
    except Blocked as e:
        if have:
            say(f"    Florida: could not refresh the official results ({e}); using the copies in {folder}")
            return paths, None
        return None, str(e)
    for k, data in got.items():
        open(paths[k], "wb").write(data)
    return paths, None


def ballot_name(first, middle, last):
    return " ".join(fold(" ".join((first, middle, last))).split())


def extract(path, senate_race):
    """{(race, party code): {(last, first, middle): {"votes": n, "counties": set()}}} for the congressional contests in
    the results extract, and a list of the checks that failed."""
    raw = open(path, "rb").read()
    if not raw.startswith(RES_HEAD):
        raise SystemExit(f"Florida: {os.path.basename(path)} is not the results extract")
    rows = csv.DictReader(io.StringIO(raw.decode("cp1252", "replace")), delimiter="\t")
    missing = [c for c in RES_COLS if c not in (rows.fieldnames or [])]
    if missing:
        raise SystemExit(f"Florida: the results extract no longer has the columns {', '.join(missing)}")
    out, differ, partial = {}, [], set()
    for r in rows:
        r = {k: (r.get(k) or "").strip() for k in RES_COLS}
        if r["RaceCode"] == "USS":
            if not senate_race:
                raise SystemExit("Florida: the results carry a Senate primary but the races table has no single Florida Senate race")
            race = senate_race
        elif r["RaceCode"] == "USR":
            race = house_id("FL", int(r["Juris1num"]))
        else:
            continue
        if r["ElectionDate"] != RES_DATE:
            raise SystemExit(f"Florida: a row of the results extract is dated {r['ElectionDate']!r}, not {RES_DATE}")
        if r["Precincts"] != r["PrecinctsReporting"]:
            partial.add((race, r["PartyCode"], r["CountyCode"]))
        c = out.setdefault((race, r["PartyCode"]), {}).setdefault((r["CanNameLast"], r["CanNameFirst"], r["CanNameMiddle"]),
                                                                 {"votes": 0, "counties": set()})
        if r["CountyCode"] in c["counties"]:
            differ.append(f"{race} {r['PartyCode']}: {r['CanNameFirst']} {r['CanNameLast']} has two rows for county {r['CountyCode']}")
        c["votes"] += int(r["CanVotes"] or 0)
        c["counties"].add(r["CountyCode"])
    for race, pc, county in sorted(partial):
        differ.append(f"{race} {pc}: not every precinct reported in county {county}")
    for (race, pc), cands in out.items():
        counties = {frozenset(c["counties"]) for c in cands.values()}
        if len(counties) != 1:
            differ.append(f"{race} {pc}: the candidates are not listed for the same counties")
        if race == senate_race and any(len(c["counties"]) != COUNTIES for c in cands.values()):
            differ.append(f"{race} {pc}: a candidate is not listed for all {COUNTIES} counties")
    return out, differ


def summary(path, party):
    """(official?, {(race code, district): {"names", "totals", "pcts", "note"}}) from one Summary Report page."""
    t = open(path, "rb").read().decode("cp1252", "replace")
    if f"<TITLE>{RES_TITLE}</TITLE>" not in t:
        raise SystemExit(f"Florida: {os.path.basename(path)} is not a Summary Report of the {RES_TITLE}")
    head = re.search(r'(?is)CLASS="OfficialHeading">\s*(.*?)\s*<', t)
    official = bool(head) and head.group(1).strip() == "Official Results"
    out = {}
    for tab in re.findall(r"(?is)<TABLE[^>]*>(.*?)</TABLE>", t):
        m = re.search(r"(?i)DetailRpt\.Asp\?ELECTIONDATE=([\d/]+)&RACE=(\w+)&PARTY=(\w+)&DIST=(\d*)", tab)
        if not m:
            continue
        if m.group(1) != RES_DATE or m.group(3).upper() != party:
            raise SystemExit(f"Florida: the {party} Summary Report lists a contest of another election or party")
        cells = lambda pat, s: [re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", x))).strip() for x in re.findall(pat, s)]
        names = cells(r'(?is)CLASS="tableheaderright"[^>]*>(.*?)</TD>', tab)
        tot = re.search(r'(?is)CLASS="ColumnHeaders">\s*Total\s*</TD>(.*?)</TR>', tab)
        pct = re.search(r'(?is)CLASS="ColumnHeaders">\s*% Votes\s*</TD>(.*?)</TR>', tab)
        note = cells(r'(?is)CLASS="RunoffIndicator"[^>]*>(.*?)</td>', tab)
        totals = [int(x.replace(",", "")) for x in cells(r'(?is)CLASS="tablecellright"[^>]*>(.*?)</TD>', tot.group(1))] if tot else []
        pcts = [float(x.rstrip("%")) for x in cells(r'(?is)CLASS="tablecellright"[^>]*>(.*?)</TD>', pct.group(1))] if pct else []
        if not names or len(totals) != len(names) or len(pcts) != len(names):
            raise SystemExit(f"Florida: a contest on the {party} Summary Report ({m.group(2)} {m.group(4)}) could not be read")
        out[(m.group(2).upper(), int(m.group(4) or 0))] = {"names": names, "totals": totals, "pcts": pcts, "note": " ".join(n for n in note if n)}
    return official, out


def person_key(first, last):
    family = [w for w in fold(last).split() if w not in SUFFIXES]
    given = fold(first).split()
    return " ".join(family), (given[0] if given else "")


def pick(cands, first, last):
    """The one candidate-list entry that fits a name in the results, or None."""
    fam, giv = person_key(first, last)
    exact = [c for c in cands if person_key(c["first"], c["last"]) == (fam, giv)]
    if len(exact) == 1:
        return exact[0]
    same = [c for c in cands if person_key(c["first"], c["last"])[0] == fam]
    return same[0] if len(same) == 1 and not exact else None


def load(con, cache, say=print):
    path = os.path.join(cache, "fl_candidates_20261103_federal.txt")
    fetch(path)
    keep = ("OfficeDesc", "Juris1num", "StatusDesc", "PartyCode", "PartyDesc", "NameFirst", "NameMiddle", "NameLast")
    rows = [{k: (r.get(k) or "").strip() for k in keep}
            for r in csv.DictReader(io.StringIO(open(path, encoding="utf-8", errors="replace").read()), delimiter="\t")]
    senate = con.execute("SELECT race_id FROM races WHERE state = 'FL' AND office = 'U.S. Senate'").fetchall()
    out, fields, listed = [], {}, {}
    for r in rows:
        if r["OfficeDesc"] == "United States Representative":
            race = house_id("FL", int(r["Juris1num"] or 0))
        elif r["OfficeDesc"] == "United States Senator" and len(senate) == 1:
            race = senate[0][0]
        else:
            continue
        name = " ".join(x for x in (r["NameFirst"], r["NameMiddle"], r["NameLast"]) if x)
        code, status = party_code(r["PartyDesc"]), r["StatusDesc"]
        write_in = int(r["PartyCode"] == "WRI")
        if status in ON_BALLOT:
            note = ("Unopposed. Florida law (section 101.151) leaves an unopposed candidate off the general election ballot."
                    if status == "Unopposed" else ("Write-in candidate: the name is not printed on the ballot." if write_in else None))
            out.append((race, "general", "2026-11-03", name, r["PartyDesc"], code, None, 0, write_in, None, None,
                        "unopposed" if status == "Unopposed" else None, None, None, "fl-dos-2026-candidates", note))
        listed.setdefault((race, r["PartyCode"]), []).append({"name": name, "party": r["PartyDesc"], "code": code, "status": status,
                                                             "first": r["NameFirst"], "last": r["NameLast"]})
        if status in ON_BALLOT + ("Defeated",) and r["PartyCode"] in ("REP", "DEM", "LPF", "GRE"):
            fields.setdefault((race, r["PartyCode"]), []).append((name, r["PartyDesc"], code, status))

    # the primary fields, with the official votes
    folder = os.path.join(cache, "fl")
    os.makedirs(folder, exist_ok=True)
    files, blocked = results_files(folder, say)
    contests, differ, official, sums = {}, [], False, {}
    if files:
        contests, differ = extract(files["extract"], senate[0][0] if len(senate) == 1 else None)
        official = True
        for p in RES_PARTIES:
            ok, sums[p] = summary(files[p], p)
            official = official and ok
        if not official:
            blocked = "the results site's Summary Reports are not headed \"Official Results\"; unofficial figures are never stored"
            contests = {}
    notes = {}
    for (race, pc), cands in contests.items():          # the county sums against the Division's own statewide totals
        rc, dist = ("USS", 0) if "-S" in race else ("USR", int(race[-2:]))
        s = sums.get(pc, {}).get((rc, dist))
        if s is None:
            differ.append(f"{race} {pc}: in the results extract but not on the {pc} Summary Report")
            continue
        notes[(race, pc)] = s["note"]
        mine = {ballot_name(first, middle, last): v["votes"] for (last, first, middle), v in cands.items()}
        total = sum(mine.values())
        theirs = {" ".join(fold(n).split()): (t, p) for n, t, p in zip(s["names"], s["totals"], s["pcts"])}
        if set(mine) != set(theirs):
            differ.append(f"{race} {pc}: the Summary Report names {sorted(set(theirs) - set(mine))}, the extract {sorted(set(mine) - set(theirs))}")
            continue
        for n, v in mine.items():
            if theirs[n][0] != v:
                differ.append(f"{race} {pc}: {n}'s counties add to {v}, the Summary Report's Total is {theirs[n][0]}")
            if total and abs(theirs[n][1] - 100 * v / total) > 0.051:
                differ.append(f"{race} {pc}: {n}'s share on the Summary Report is {theirs[n][1]}%, computed {100 * v / total:.2f}%")
    for p in sums:
        for (rc, dist), s in sums[p].items():
            race = (senate[0][0] if rc == "USS" and len(senate) == 1 else house_id("FL", dist))
            if (race, p) not in contests and official:
                differ.append(f"{race} {p}: on the Summary Report but not in the results extract")

    nfields, unmatched, disagree, recounts = 0, [], [], []
    for key in sorted(set(k for k, v in fields.items() if len(v) > 1) | set(k for k, v in contests.items() if len(v) > 1)):
        race, pc = key
        field = [c for c in listed.get(key, []) if c["status"] in ON_BALLOT + ("Defeated",)]
        res = contests.get(key)
        nfields += 1
        if not res:            # no official votes: kept as the candidate list gives it
            if files and official:
                differ.append(f"{race} {pc}: a field on the candidate list with no contest in the official results")
            for c in field:
                out.append((race, f"primary-{pc}", PRIMARY, c["name"], c["party"], c["code"], None, 0, 0, None, None,
                            "lost" if c["status"] == "Defeated" else "advanced", None, None, "fl-dos-2026-candidates", None))
            continue
        total = sum(v["votes"] for v in res.values())
        ranked = sorted(res.items(), key=lambda kv: -kv[1]["votes"])
        tie = len(ranked) > 1 and ranked[0][1]["votes"] == ranked[1][1]["votes"]
        if tie:
            differ.append(f"{race} {pc}: the top two have the same number of votes; no one is marked as advanced")
        party = (field or listed.get(key) or [{"party": {"REP": "Republican Party of Florida", "DEM": "Florida Democratic Party"}.get(pc, pc)}])[0]["party"]
        used = set()
        recount = notes.get(key, "")
        if recount:
            recounts.append(f"{race} {pc}: {recount}")
        for rank, ((last, first, middle), v) in enumerate(ranked):
            c = pick(field, first, last) or pick(listed.get(key, []), first, last)
            if c is None:
                unmatched.append(f"{race} {pc}: {first} {last}")
                name, status = " ".join(x for x in (first, middle.strip("'\""), last) if x), None
            else:
                if id(c) in used:
                    raise SystemExit(f"Florida: two names in the {race} {pc} results fit {c['name']} on the candidate list")
                used.add(id(c))
                name, status = c["name"], c["status"]
            won = rank == 0 and not tie
            note = []
            if won and status not in ON_BALLOT:
                note.append("Won the primary, but is not on the November list" + (f" (the Division's candidate list gives the status \"{status}\")." if status else "."))
            if status is None:
                note.append("Named as in the official results: not found on the Division's candidate list.")
            if recount:
                note.append(f"The Division's official results note: {recount[0].upper() + recount[1:].lower()}.")
            if status is not None and (won != (status in ON_BALLOT)) and status in ON_BALLOT + ("Defeated",):
                disagree.append(f"{race} {pc}: {name} has {v['votes']:,} votes ({'the most' if rank == 0 else 'not the most'}) but is \"{status}\" on the candidate list")
            out.append((race, f"primary-{pc}", PRIMARY, name, party, party_code(party), None, 0, 0, v["votes"],
                        round(100 * v["votes"] / total, 1) if total else None, "advanced" if won else "lost",
                        None, None, "fl-dos-2026-primary-results", " ".join(note) or None))
        for c in field:
            if id(c) not in used:
                differ.append(f"{race} {pc}: {c['name']} (\"{c['status']}\") is on the candidate list but not in the official results")

    with con:
        con.execute("DELETE FROM candidates WHERE race_id LIKE '2026-FL-%'")
        con.executemany("INSERT OR REPLACE INTO candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", out)
        record_source(con, "fl-dos-2026-candidates", path=path, level="federal", state="FL", kind="official candidate list",
                      agency="Florida Department of State, Division of Elections", title="Candidate Tracking System: candidate list, 2026 election, federal offices",
                      url=PAGE, rows=len(rows), note="Downloaded as a tab-separated file (all statuses)."
                      + (" Primary votes are from the Division's official results (fl-dos-2026-primary-results)." if contests else " Primary votes not yet loaded."))
        if contests:
            nres = sum(len(v) for v in contests.values())
            record_source(con, "fl-dos-2026-primary-results", path=files["extract"], level="federal", state="FL", kind="official results",
                          agency="Florida Department of State, Division of Elections",
                          title=f"Election Results Reporting System: {RES_TITLE}, Data Download Utility (official results extract)",
                          url=RES_DOWNLOAD, rows=nres,
                          note=f"The site's download form (posted to {RES_EXTRACT}, OfficialResults=Y) answers with a tab-separated file, one row "
                               f"per county, party, contest and candidate; the file is kept as published, and only the congressional contests are "
                               f"read. Votes are the county rows summed, checked against the Division's Summary Reports for Federal Offices "
                               f"(fl-dos-2026-primary-summary-rep, -dem)"
                               + ("; every candidate's county sum equals the statewide Total there." if not differ else "; differences: " + "; ".join(differ) + ".")
                               + " The results carry no write-in line, so shares are of the candidates' votes. The names stored are the candidate list's."
                               + (" Contest notes: " + "; ".join(recounts) + "." if recounts else ""))
            for p in RES_PARTIES:
                record_source(con, f"fl-dos-2026-primary-summary-{p.lower()}", path=files[p], level="federal", state="FL", kind="official results",
                              agency="Florida Department of State, Division of Elections",
                              title=f"Election Results Reporting System: {RES_TITLE}, "
                                    f"{'Republican' if p == 'REP' else 'Democratic'} Primary, Summary Report, Federal Offices (Official Results)",
                              url=RES_SUMMARY.format(party=p), rows=sum(len(s["names"]) for s in sums[p].values()),
                              note=f"Headed \"Official Results\". Statewide totals per candidate, used to check the county sums of the results extract "
                                   f"(fl-dos-2026-primary-results). Site: {RES_PAGE}")
    general = sum(1 for r in out if r[1] == "general")
    tail = (", votes from the Division's official results" if contests else
            f"; no votes: the official results could not be read ({blocked})")
    say(f"    Florida: {general} candidates on or qualified for the November ballot; {len(out) - general} in "
        f"{nfields} party primaries{tail}")
    if blocked and not files:
        say(f"      A person can open {RES_DOWNLOAD}, press Download and save the file as {os.path.join(folder, RES_FILE)}, and save the "
            f"pages {RES_SUMMARY.format(party='REP')} and {RES_SUMMARY.format(party='DEM')} as "
            f"{os.path.join(folder, SUM_FILE.format(party='rep'))} and {os.path.join(folder, SUM_FILE.format(party='dem'))}.")
    for d in differ + [f"not matched to the candidate list: {u}" for u in unmatched] + disagree:
        say("      " + d)
    for r in recounts:
        say("      note: " + r)
    return general
