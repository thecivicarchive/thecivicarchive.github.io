"""
Tennessee: the Secretary of State's Division of Elections. Nine House seats, on the new map adopted May 7, 2026 (see
the state note), and the class 2 Senate seat.

The Secretary's sites (sos.tn.gov, its file host sos-prod.tnsosgovfiles.com and the election-night site
elections.tn.gov) answer this tool's honest User-Agent with "403 Request blocked" from CloudFront, so this loader
downloads nothing. The files are saved from a browser into ballot_cache/tn/, and the loader reads whatever is there.
It was written before the 2026 files could be read: the layouts are those of the Division's files of the same kind
from 2022 and 2024 and of its 2026 pre-primary lists, and the checks below stop the loader if the 2026 files differ.

The November ballot is the Division's candidate list for the November 3, 2026 General Election, one for the United
States Senate and one for the United States House of Representatives, linked from sos.tn.gov/elections/2026-candidate-
lists (the Governor's is Governor_Nov2026.pdf; the federal ones are expected alongside it). The loader finds them by
their own titles, whatever the files are called: a PDF titled "Candidates for United States Senate" or "Candidates
for United States House of Representatives" that says November 3, 2026 above its first table, or a workbook whose
heading row names Office, Name and Party (the Division's 2024 lists came as both; when both copies are there, the
workbook is used, since its cells hold the whole name and the 2024 PDF cut one short, and the PDF is checked against
it). In a PDF, each district's table is
headed by its district ("District 1"; the 2024 lists printed it over the word "Jurisdiction") and a row of column
headings (Candidate or Name, Party, then City, or Address, City and ZIP); the column edges come from those headings,
and only the name and the party are ever turned into text. Everything from the third column on (city, street address,
ZIP, filing dates) stays in the file and is never read; in a workbook only Office, Name and Party are read. The list
prints no order numbers, so a race's ballot order is the list's own order (party nominees, then independents). Parties
are printed in full (Republican, Democratic, Independent) and kept as printed; an abbreviation would be written out
(R or REP Republican, D or DEM Democratic, I or IND Independent, L or LIB Libertarian, G or GRN Green). Names are
printed in ordinary capitals, first name first; a list printed in capitals, or "Last, First", would be shown in
ordinary capitals, first name first, with a note saying so. The list leaves out anyone who withdrew or did not
qualify, so there is nothing to leave off; it lists no write-in candidates.

The August 6, 2026 primaries are the Division's official results by county, one PDF per party:
20260806RepublicanPrimarybyCounty.pdf and 20260806DemocraticPrimarybyCounty.pdf (linked from sos.tn.gov/elections/
results; the date printed at the foot of each page is when the file was issued). Each office is a section: its title
("United States Senate", "United States House of Representatives District 5"), the candidates numbered in ballot order
("1.Name"; a certified write-in candidate is printed "1.Write-In - Name"; a number can be skipped), a row of column
numbers, a row per county, and "STATE TOTALS" or "DISTRICT TOTALS". A section carried onto the next page repeats its title and candidates.
Every section of the file is read; each county column must add up to its TOTALS row, and the statewide Senate section
must have all 95 counties. A party primary becomes a field when two or more candidates were printed on that party's
ballot. A candidate's share is of all the votes the section counts: the printed candidates and the certified write-in
candidates (the results carry no other write-ins). Write-in candidates are counted in the total but not listed, unless
one won. The party's candidate on the November list is the one who advanced, and must be the section's top
vote-getter (Tennessee nominates by plurality); the loader says so plainly if not. Only the Republican and Democratic
parties hold primaries; independents qualify for November by petition.
"""

import glob
import os
import re

from ballot.common import fold, house_id, name_parts, party_code, record_source, senate_id
from ballot.lists.tx import proper
from ballot.pdftext import PDF, join, lines, rows as pdf_rows

LIST_PAGE = "https://sos.tn.gov/elections/2026-candidate-lists"
RESULTS_PAGE = "https://sos.tn.gov/elections/results"
FILES = "https://sos-prod.tnsosgovfiles.com/s3fs-public/document/"
GENERAL_TEXT = "November 3, 2026"
PRIMARY_TEXT = "August 6, 2026"
PRIMARY = "2026-08-06"
RESULTS = {"Republican": "20260806RepublicanPrimarybyCounty.pdf", "Democratic": "20260806DemocraticPrimarybyCounty.pdf"}
CODE = {"Republican": "REP", "Democratic": "DEM"}
ABBR = {"R": "Republican", "REP": "Republican", "D": "Democratic", "DEM": "Democratic", "I": "Independent", "IND": "Independent",
        "L": "Libertarian", "LIB": "Libertarian", "G": "Green", "GRN": "Green"}
MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")
DATE = r"(?:%s) \d{1,2}, \d{4}" % "|".join(MONTHS)
TITLE = re.compile(r"^Candidates for (United States Senate|United States House of Representatives)\b")
DISTRICT = re.compile(r"istrict\s*(\d{1,2})$")
PAGE_FURNITURE = re.compile(rf"{DATE}|General Election|^Page \d+(?: of \d+)?$")
CAPS = "Tennessee's list prints names in capitals; they are shown here in ordinary capitals."
CAPS_RESULTS = "Tennessee's results print names in capitals; they are shown here in ordinary capitals."
TURNED = "Tennessee's list prints the family name first; it is shown here first name first."
NOT_ON_LIST = "Won the primary but is not on the Secretary of State's November candidate list."
WRITE_IN_WON = "Write-in candidate: the name was not printed on the primary ballot."
SUFFIX = re.compile(r"^(JR|SR|II|III|IV|V)\.?$", re.I)
TOTAL_COUNTIES = 95

# the results by county
FURNITURE = re.compile(rf"^(State of Tennessee|{DATE}|(Republican|Democratic) Primary)$")
FOOTER = re.compile(rf"^({DATE}) Page \d+ of \d+$")
CANDIDATE = re.compile(r"^(\d{1,2})\.\s*(.+)$")
COLUMNS = re.compile(r"^\d{1,2}(?: \d{1,2})*$")
NUMBER = r"\d{1,3}(?:,\d{3})*"
COUNTY = re.compile(rf"^([A-Z][A-Za-z.' ]*[a-z]) ({NUMBER}(?: {NUMBER})*)$")
TOTALS = re.compile(rf"^(STATE|DISTRICT) TOTALS ({NUMBER}(?: {NUMBER})*)$")
WRITE_IN = re.compile(r"^Write-In\s*-\s*(.+)$", re.I)


def iso(text):
    m = re.fullmatch(r"([A-Z][a-z]+) (\d{1,2}), (\d{4})", text or "")
    return f"{m.group(3)}-{MONTHS.index(m.group(1)) + 1:02d}-{int(m.group(2)):02d}" if m and m.group(1) in MONTHS else ""


def race_of(office):
    """United States Senate -> 2026-TN-S2; United States House of Representatives District 5 -> 2026-TN-H05; else None."""
    office = re.sub(r"\s+", " ", office or "").strip()
    if office == "United States Senate":
        return senate_id("TN", 2)
    m = re.fullmatch(r"United States House of Representatives,? District (\d{1,2})", office)
    return house_id("TN", int(m.group(1))) if m else None


def shown(raw, caps_note):
    """The name as the Secretary prints it, first name first and in ordinary capitals, and the note that says what changed."""
    name, notes = re.sub(r"\s+", " ", raw).strip(), []
    if "," in name and not re.search(r",\s*(Jr|Sr|II|III|IV)\.?$", name, re.I):
        last, _, first = name.partition(",")
        words = last.split()
        name = " ".join(first.split() + [w for w in words if not SUFFIX.match(w)] + [w for w in words if SUFFIX.match(w)])
        notes.append(TURNED)
    if not re.search(r"[a-z]", name):
        name = re.sub(r"(['\"(])([a-z])", lambda m: m.group(1) + m.group(2).upper(), proper(name))
        notes.append(caps_note)
    return name, (" ".join(notes) or None)


def party_of(raw):
    p = re.sub(r"\s+", " ", raw or "").strip()
    return ABBR.get(p.upper().rstrip("."), p)


def cells(runs):
    """A printed row's pieces grouped into cells: [(x, pieces)]; a gap wider than six points starts the next cell."""
    out = []
    for r in sorted(runs, key=lambda r: r[0]):
        if out and r[0] - out[-1][2] <= 6:
            out[-1][1].append(r)
            out[-1][2] = max(out[-1][2], r[4])
        else:
            out.append([r[0], [r], r[4]])
    return [(x, rs) for x, rs, _end in out]


class NotTheList(Exception):
    pass


def pdf_list(path):
    """(title, date printed, [(race, name, party)]) from one of the Division's candidate-list PDFs. Only the name and the
    party columns are ever turned into text; a data row's third column on (city, address, ZIP, dates) is never read."""
    pdf = PDF(open(path, "rb").read())
    title, printed, office, district, edges, out, head = "", "", None, None, None, [], []
    for page, res in pdf.pages():
        for _y, runs in pdf_rows(pdf, page, res):
            cs = cells(runs)
            if edges is None:                                    # page 1 above the first table: the title, the date, a note
                heads = {join(rs): x for x, rs in cs}
                key = "Candidate" if "Candidate" in heads else "Name" if "Name" in heads else None
                if key and "Party" in heads:
                    if not office:
                        raise NotTheList("no \"Candidates for United States Senate/House of Representatives\" title")
                    if GENERAL_TEXT not in " ".join(head):
                        raise NotTheList(f"its title does not say {GENERAL_TEXT} (a list from before the primary?)")
                    later = [x for x in heads.values() if x > heads["Party"] + 1]
                    edges = (heads[key] - 8, heads["Party"] - 8, (min(later) if later else 10 ** 6) - 8)
                    continue
                if len(head) >= 15:                              # no table near the top: stop before any row of it is read
                    raise NotTheList("no table headed Name (or Candidate) and Party near the top of the first page")
                text = join(runs)
                head.append(text)
                m = TITLE.match(text)
                if m:
                    office = m.group(1)
                d = DISTRICT.search(text)
                if d and len(text) < 30:
                    district = int(d.group(1))
                continue
            name_cells = [rs for x, rs in cs if edges[0] <= x < edges[1]]
            party_cells = [rs for x, rs in cs if edges[1] <= x < edges[2]]
            name = join([r for rs in name_cells for r in rs])
            party = join([r for rs in party_cells for r in rs])
            if name in ("Candidate", "Name") and party == "Party":  # a table's heading row: the edges again
                heads = {join(rs): x for x, rs in cs}
                later = [x for x in heads.values() if x > heads["Party"] + 1]
                edges = (heads[name] - 8, heads["Party"] - 8, (min(later) if later else 10 ** 6) - 8)
                continue
            if len(cs) == 1 and cs[0][0] < edges[2]:                # a line of one piece: a district, a title, a note
                text = join(cs[0][1])
                d = DISTRICT.search(text)
                if d and len(text) < 30:
                    district = int(d.group(1))
                    continue
                if (cs[0][0] < edges[0] or TITLE.match(text) or PAGE_FURNITURE.search(text) or len(text) > 45 or text.endswith(".")
                        or (cs[0][0] >= edges[1] and re.match(r"^(Juri\w*|Statewide|None)\b", text))):
                    continue
                raise SystemExit(f"Tennessee: {os.path.basename(path)}: a line of one piece that is not a name with a party, a district or "
                                 "a heading; read the list again")
            if name and party:
                if office == "United States Senate":
                    race = senate_id("TN", 2)
                elif office and district:
                    race = house_id("TN", district)
                else:
                    raise SystemExit(f"Tennessee: {os.path.basename(path)}: a candidate row before any district heading")
                out.append((race, name, party))
            elif name or party:
                raise SystemExit(f"Tennessee: {os.path.basename(path)}: a row with a name or a party but not both; read the list again")
    if edges is None:
        raise NotTheList("no table headed Name (or Candidate) and Party")
    block = " ".join(head)
    m = re.search(rf"as of ({DATE})", block)
    printed = m.group(1) if m else ""
    title = next(t for t in head if TITLE.match(t))
    return title, printed, out


def xlsx_list(path):
    """[(race, name, party)] from a candidate-list workbook: the Office, Name and Party columns only."""
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    out, found = [], False
    for ws in wb.worksheets:
        it = ws.iter_rows(values_only=True)
        idx = None
        for k, r in enumerate(it):
            heads = [str(c).strip() if c is not None else "" for c in r]
            if all(h in heads for h in ("Office", "Name", "Party")):
                idx = {h: heads.index(h) for h in ("Office", "Name", "Party")}
                break
            if k > 10:
                break
        if not idx:
            continue
        found = True
        for r in it:
            office, name, party = (str(r[idx[h]]).strip() if len(r) > idx[h] and r[idx[h]] is not None else "" for h in ("Office", "Name", "Party"))
            if not (office or name):
                continue
            race = race_of(office)
            if race and name:
                if not party:
                    raise SystemExit(f"Tennessee: {os.path.basename(path)}: a candidate for {office} with no party")
                out.append((race, name, party))
    wb.close()
    if not found:
        raise NotTheList("no sheet with Office, Name and Party headings")
    return out


def find_lists(folder, say):
    """{path: (kind, title, printed, rows)} for every November list in the folder, found by what the file says it is."""
    found = {}
    for path in sorted(glob.glob(os.path.join(folder, "*"))):
        base = os.path.basename(path)
        if base in RESULTS.values() or not base.lower().endswith((".pdf", ".xlsx")):
            continue
        magic = open(path, "rb").read(5)
        try:
            if base.lower().endswith(".pdf"):
                if magic != b"%PDF-":
                    raise NotTheList("not a PDF (a saved error page?)")
                title, printed, got = pdf_list(path)
                found[path] = ("pdf", title, printed, got)
            else:
                if magic[:2] != b"PK":
                    raise NotTheList("not a workbook (a saved error page?)")
                got = xlsx_list(path)
                if got:
                    found[path] = ("xlsx", "", "", got)
        except NotTheList as e:
            if not re.match(r"20260806(Republican|Democratic)", base):
                say(f"      {base}: not read as a November candidate list ({e})")
    return found


def results(path, party):
    """(date issued, {race: {"names": [(name, votes, write_in)], "counties": n}}) for the federal sections of one party's
    results by county. Every section is read and checked: its county rows must add up to its TOTALS row."""
    L = lines(path)
    words = {t for _p, _y, t in L[:6]}
    if f"{party} Primary" not in words or PRIMARY_TEXT not in words or "State of Tennessee" not in words:
        raise SystemExit(f"Tennessee: {os.path.basename(path)} is not the {PRIMARY_TEXT} {party} Primary results by county")
    issued, state, cur, sections, page = "", "head", None, [], None
    for p, _y, t in L:
        if p != page:                                            # a new page opens with its furniture, then a title
            page, state = p, "head"
        m = FOOTER.match(t)
        if m:
            issued = issued or m.group(1)
            continue
        if FURNITURE.match(t):
            continue
        if state == "head":
            if cur and not cur.get("done") and t == cur["office"]:
                state, cur["again"] = "cands", []                # the section carried over: its candidates are printed again
            else:
                if cur and not cur.get("done"):
                    raise SystemExit(f"Tennessee: {os.path.basename(path)}: {cur['office']} has no TOTALS row")
                cur = {"office": t, "names": [], "counties": {}, "totals": None}
                sections.append(cur)
                state = "cands"
            continue
        if state == "cands":
            m = CANDIDATE.match(t)
            if not m and not cur["names"] and "again" not in cur and not (COLUMNS.match(t) or TOTALS.match(t) or COUNTY.match(t)):
                cur["office"] += " " + t                         # a title printed on two lines
                continue
            if m:                                                # numbered in ballot order; a number can be skipped (2022, 2024)
                target = cur["again"] if "again" in cur else cur["names"]
                num = int(m.group(1))
                if target and num <= target[-1][0]:
                    raise SystemExit(f"Tennessee: {os.path.basename(path)}: the candidates under {cur['office']} are not numbered in order")
                target.append((num, re.sub(r"\s+", " ", m.group(2)).strip()))
                continue
            if "again" in cur:
                if cur.pop("again") != cur["names"]:
                    raise SystemExit(f"Tennessee: {os.path.basename(path)}: {cur['office']} lists different candidates on a later page")
            state = "counties"
            if COLUMNS.match(t):                                 # the row of column numbers: each must be a candidate's number
                if not {int(x) for x in t.split()} <= {num for num, _n in cur["names"]}:
                    raise SystemExit(f"Tennessee: {os.path.basename(path)}: the column numbers under {cur['office']} do not match its candidates")
                continue
        m = TOTALS.match(t)
        if m and state == "counties":
            cur["totals"] = [int(x.replace(",", "")) for x in m.group(2).split()]
            cur["done"], state = True, "head"
            continue
        m = COUNTY.match(t)
        if m and state == "counties":
            nums = [int(x.replace(",", "")) for x in m.group(2).split()]
            if len(nums) != len(cur["names"]) or m.group(1) in cur["counties"]:
                raise SystemExit(f"Tennessee: {os.path.basename(path)}: a county row under {cur['office']} does not fit its candidates")
            cur["counties"][m.group(1)] = nums
            continue
        raise SystemExit(f"Tennessee: {os.path.basename(path)}: a line under {cur['office'] if cur else 'the first page'} was not understood; read the file again")
    if cur and not cur.get("done"):
        raise SystemExit(f"Tennessee: {os.path.basename(path)}: {cur['office']} has no TOTALS row")
    out = {}
    for s in sections:
        n = len(s["names"])
        if len(s["totals"]) != n:
            raise SystemExit(f"Tennessee: {os.path.basename(path)}: the TOTALS row of {s['office']} does not fit its candidates")
        summed = [sum(v[k] for v in s["counties"].values()) for k in range(n)]
        if summed != s["totals"]:
            raise SystemExit(f"Tennessee: {os.path.basename(path)}: the counties of {s['office']} add up to {summed}, its TOTALS row says {s['totals']}")
        race = race_of(s["office"])
        if not race:
            continue
        if race.endswith("-S2") and len(s["counties"]) != TOTAL_COUNTIES:
            raise SystemExit(f"Tennessee: {os.path.basename(path)}: the Senate section has {len(s['counties'])} counties, not {TOTAL_COUNTIES}")
        if race in out:
            raise SystemExit(f"Tennessee: {os.path.basename(path)}: {s['office']} appears twice")
        names = []
        for (_num, raw), votes in zip(s["names"], s["totals"]):
            if raw == "No Candidate Qualified":
                continue
            w = WRITE_IN.match(raw)
            names.append((w.group(1).strip() if w else raw, votes, bool(w)))
        out[race] = {"names": names, "counties": len(s["counties"]), "sections": len(sections)}
    return issued, out


def pick(nominee, names):
    """Which of a primary's candidates is the November list's nominee: the same letters; else the one candidate with the
    same family name whose given name begins with the same letter (Chuck and Charles J.); else the one candidate with that
    family name. None when no single candidate fits."""
    if not nominee:
        return None
    exact = [k for k, n in enumerate(names) if fold(n) == fold(nominee)]
    if len(exact) == 1:
        return exact[0]
    g0, f0 = name_parts(nominee)
    family = [k for k, n in enumerate(names) if name_parts(n)[1] == f0]
    initial = [k for k in family if g0 and name_parts(names[k])[0] and name_parts(names[k])[0][0][0] == g0[0][0]]
    if len(initial) == 1:
        return initial[0]
    return family[0] if len(family) == 1 else None


def load(con, cache, say=print):
    folder = os.path.join(cache, "tn")
    os.makedirs(folder, exist_ok=True)
    lists = find_lists(folder, say)
    listed = [(path, r) for path, (_k, _t, _p, got) in lists.items() for r in got]
    if not listed:
        say(f"    Tennessee: no November candidate list in {folder}. The Secretary of State's sites refuse scripts (403 from CloudFront); "
            f"save from a browser, keeping the Secretary's file names: the November 3, 2026 General Election candidate lists for "
            f"United States Senate and United States House of Representatives from {LIST_PAGE}, and {FILES}{RESULTS['Republican']} "
            f"and {FILES}{RESULTS['Democratic']} from {RESULTS_PAGE}. Nothing was changed.")
        return 0
    # a race named in two files (a PDF and a workbook of one list) must read the same in both
    by_race = {}
    for path, (race, name, party) in listed:
        by_race.setdefault(race, {}).setdefault(path, []).append((name, party))
    general, sources, differ = [], {}, []
    for race in sorted(by_race):
        # a workbook first: its cells hold the whole name, and a PDF's column can cut a long one short (the 2024 PDF did)
        copies = sorted(by_race[race].items(), key=lambda kv: (lists[kv[0]][0] != "xlsx", kv[0]))
        first = copies[0][1]
        for path, other in copies[1:]:
            if [(fold(n), p) for n, p in other] != [(fold(n), p) for n, p in first]:
                differ.append(f"{race} ({os.path.basename(copies[0][0])} used, {os.path.basename(path)} differs)")
        sources[race] = copies[0][0]
        for order, (raw, party) in enumerate(first, start=1):
            name, note = shown(raw, CAPS)
            general.append((race, name, party_of(party), order, note))
    expected = {r for (r,) in con.execute("SELECT race_id FROM races WHERE state = 'TN'")}
    missing = sorted(expected - {r[0] for r in general})
    strays = sorted({r[0] for r in general} - expected)
    if strays:
        raise SystemExit(f"Tennessee: the lists name races that are not on the ballot: {strays}")
    twice = sorted({(r[0], r[2]) for r in general if r[2] in CODE and sum(1 for g in general if (g[0], g[2]) == (r[0], r[2])) > 1})
    if twice:
        raise SystemExit(f"Tennessee: more than one nominee of one party for one seat: {twice}")

    rows = [(race, "general", "2026-11-03", name, party, party_code(party), order, 0, 0, None, None, None, None, None,
             source_id(sources[race]), note) for race, name, party, order, note in general]
    nominee = {(race, party): name for race, name, party, _o, _n in general}

    fields, problems, issued, read = 0, [], {}, {}
    for party, base in RESULTS.items():
        path = os.path.join(folder, base)
        if not os.path.exists(path):
            continue
        if open(path, "rb").read(5) != b"%PDF-":
            raise SystemExit(f"Tennessee: {base} is not a PDF (a saved error page?)")
        issued[party], sections = results(path, party)
        read[party] = sections
        code = CODE[party]
        for race, s in sorted(sections.items()):
            names = s["names"]
            printed = [c for c in names if not c[2]]
            total = sum(v for _n, v, _w in names)
            nom = nominee.get((race, party))
            k = pick(nom, [n for n, _v, _w in names])
            top = max(range(len(names)), key=lambda j: names[j][1]) if names else None
            if nom and k is None:
                problems.append((party, f"{race} {party}: the November nominee ({nom}) is not found in the primary results"))
            elif nom and names and names[k][1] != names[top][1]:
                problems.append((party, f"{race} {party}: the November nominee ({nom}) is not the primary's top vote-getter ({names[top][0]})"))
            if not nom and names:
                k = top
                if sum(1 for _n, v, _w in names if v == names[top][1]) > 1:
                    problems.append((party, f"{race} {party}: no November nominee on the list and a tie at the top of the primary"))
            if len(printed) < 2:
                continue
            fields += 1
            for j in sorted(range(len(names)), key=lambda j: -names[j][1]):
                name_raw, votes, write_in = names[j]
                won = j == k
                if write_in and not won:
                    continue                                   # counted in the total, not listed
                name, note = shown(name_raw, CAPS_RESULTS)
                if won and not nom:
                    note = " ".join(x for x in (note, NOT_ON_LIST) if x)
                if write_in:
                    note = " ".join(x for x in (note, WRITE_IN_WON) if x)
                rows.append((race, f"primary-{code}", PRIMARY, name, party, party_code(party), None, 0, int(write_in), votes,
                             round(100 * votes / total, 1) if total else None, "advanced" if won else "lost", None, None,
                             f"tn-sos-2026-primary-{code.lower()}-county", note))
    with con:
        con.execute("DELETE FROM candidates WHERE race_id LIKE '2026-TN-%'")
        con.execute("DELETE FROM ballot_sources WHERE source_id LIKE 'tn-sos-2026-list-%'")      # named after the files, which may be renamed
        con.executemany("INSERT OR REPLACE INTO candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        for path, (kind, title, printed, got) in lists.items():
            base = os.path.basename(path)
            used = sum(1 for r in general if sources[r[0]] == path)
            if not used:
                continue                                        # another copy of the same list (the workbook) was used
            others = sorted({os.path.basename(q) for q, (_race, _n, _p) in listed if q != path and any(sources[r] == path for r in {x[0] for x in lists[q][3]})})
            offices = sorted({"United States Senate" if r[0].endswith("-S2") else "United States House of Representatives" for r in got})
            record_source(con, source_id(path), path=path, level="federal", state="TN", kind="official candidate list",
                          agency="Tennessee Secretary of State, Division of Elections",
                          title=(title or f"Candidates for {' and '.join(offices)}, {GENERAL_TEXT} General Election (workbook)") + f" (file {base})",
                          url=LIST_PAGE, published=iso(printed), rows=len(got),
                          note=f"The Secretary's sites refuse scripts; the file ({base}) was saved from a browser. "
                               + ("Name and party columns only; city, address and ZIP are never read. " if kind == "pdf" else
                                  "Office, Name and Party columns only; address, city, state and ZIP are never read. ")
                               + "No order numbers are printed; the list's own order is kept. The list leaves out anyone who withdrew or "
                                 f"did not qualify, and lists no write-in candidates. Rows used: {used}."
                               + (f" The PDF copy of the same list ({', '.join(others)}) was checked against it"
                                  + (f" and differs for {'; '.join(differ)}." if differ else " and agrees.") if others else ""))
        for party, base in RESULTS.items():
            if party not in read:
                continue
            code = CODE[party]
            record_source(con, f"tn-sos-2026-primary-{code.lower()}-county", path=os.path.join(folder, base), level="federal", state="TN",
                          kind="official results", agency="Tennessee Secretary of State, Division of Elections",
                          title=f"August 6, 2026 {party} Primary, State of Tennessee: results by county"
                                + (f" (issued {issued[party]})" if issued[party] else ""),
                          url=FILES + base, published=iso(issued[party]),
                          rows=sum(len(s["names"]) for s in read[party].values()),
                          note=f"Linked from {RESULTS_PAGE}; saved from a browser. Every section's counties add up to its TOTALS row. "
                               "Votes from the STATE or DISTRICT TOTALS row; a share is of the printed and the certified write-in "
                               "candidates' votes (no other write-ins are counted); write-in candidates are not listed unless one won."
                               + (" Did not reconcile: " + "; ".join(t for p, t in problems if p == party) + "."
                                  if any(p == party for p, _t in problems) else ""))
    for _p, t in problems:
        say(f"    Tennessee: {t}; read the files again")
    if differ:
        say("    Tennessee: the PDF and the workbook of one list disagree for " + "; ".join(differ) + "; read both")
    if missing:
        say(f"    Tennessee: no November candidates read for {', '.join(missing)}")
    n = len(general)
    lacking = [p for p in RESULTS if p not in read]
    say(f"    Tennessee: {len({r[0] for r in general if '-H' in r[0]})} House districts"
        f"{' and the Senate race' if senate_id('TN', 2) in {r[0] for r in general} else ''}, {n} candidates on the November ballot; "
        f"{fields} party primaries with a field, votes from the official results by county"
        + (f" (no {' or '.join(lacking)} results file yet)" if lacking else ""))
    return n


def source_id(path):
    base = re.sub(r"[^a-z0-9]+", "-", os.path.basename(path).lower()).strip("-")
    return f"tn-sos-2026-list-{base}"
