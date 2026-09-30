"""
Nevada: the Secretary of State's Elections Division. Nevada elects its four House members this year (2024 lines) and
no U.S. Senator (its seats are next up in 2028 and 2030). The closed party primaries were on June 9, 2026. Nevada
allows no write-in votes, so nobody is listed as a write-in.

The Secretary of State's hosts, www.nvsos.gov and silverstateelection.nv.gov, sit behind an Incapsula bot wall: a
plain request gets the wall's 212-byte or one-kilobyte page ("Request unsuccessful. Incapsula incident ID ...") in
place of the page asked for (2026-09-30: four requests to www.nvsos.gov, one answered; two to silverstateelection,
none). The wall is never worked around, so this loader downloads nothing. It reads what a browser saves into
ballot_cache/nv/ (the New York and Wisconsin method in CLAUDE.md), each file under one of these names, with the
extension .html, .htm, .md, .csv or .xlsx:

  nv_2026_general_candidates   the certified list of candidates for the November 3, 2026 general election: Aurora's
                               "Candidate Filing List" (LIST_PAGE) with the 2026 General Election chosen, saved as the
                               page's HTML or as its own export, or the certified list the 2026 Election Information
                               page (INFO_PAGE) links, if it is a table rather than a PDF
  nv_2026_primary_results      the official (canvassed) results of the June 9, 2026 primary, the U.S. Congress contests
                               of "2026 Official Statewide Primary Election Results" (RESULTS_PAGE); election-night
                               figures are never read, so a file that does not call itself official, or calls itself
                               unofficial, stops the loader
  nv_2026_candidate_filings    optional: Aurora's list of everyone who filed in the 2026 cycle; when the results file is
                               missing it gives each party primary's field, stored without votes, the winner read from
                               the November list

None of these layouts had been seen when this loader was written (every request met the wall), so it reads them by
what they say, not by position, and stops, naming the file and the headings it found, when a file does not read as
expected. A table's columns are found by their headings, and only these are read: the candidate's name, the office
(or contest) and district, the party, the status and the ballot order, and in a results table the votes. Addresses,
telephones, e-mail, websites and anything else a list carries are never read or kept. A results page is read in
document order: a heading naming "Representative in Congress" and a district starts a contest (its party from the
heading, a Party column, or a "(DEM)" after the name), a row headed Votes finds the columns, and each row below with a
whole number of votes is a candidate; a "Total" row, where there is one, must equal the candidates' votes added up.

Statuses: a candidate marked withdrawn, removed, disqualified or deceased is left off and counted; any other status
that is not plainly on the ballot stops the loader. The ballot order is the list's own where it gives one, else the
list's order. Parties printed as codes are written out (DEM Democratic, REP Republican, LPN Libertarian, IAP
Independent American, NP No Political Party, the label Nevada uses for a candidate registered with no party); a party
printed in full is kept as printed. Names printed "Last, First" are turned round; names in capitals are shown in
ordinary capitals (a sitting member as the congress-legislators roster spells them), with a note saying so.

Until the November list is saved, each of the four races is recorded in list_gaps with the reason, and the pages say the
list is not loaded yet.
"""

import csv
import glob
import html as H
import io
import os
import re
import sqlite3

from ballot.common import HERE, SUFFIXES, fold, house_id, party_code, record_source
from ballot.lists.tx import proper

LIST_PAGE = "https://www.nvsos.gov/SOSCandidateServices/AnonymousAccess/CEFDSearchUU/CertCandList.aspx"
INFO_PAGE = "https://www.nvsos.gov/elections/election-information/2026-election-information"
RESULTS_PAGE = "https://www.nvsos.gov/SOSelectionPages/results/2026StateWidePrimary/ElectionSummary.aspx"
PRIMARY = "2026-06-09"
STEMS = {"general": "nv_2026_general_candidates", "primary": "nv_2026_primary_results", "filings": "nv_2026_candidate_filings"}
KINDS = (".html", ".htm", ".md", ".csv", ".xlsx")
RACES = [house_id("NV", d) for d in range(1, 5)]
GAP = "the Secretary of State's website turns away automated requests, so its list waits to be saved from a browser"

# the only columns ever read, found by their headings
HEADS = {"name": r"(candidate(?:'s)?|ballot|choice)?\s*name(?: on ballot| as it appears on ballot)?|candidate|choice",
         "office": r"(office|contest|race)(?: name| title| sought)?", "district": r"district(?: name| no\.?| number)?",
         "party": r"party(?: affiliation| preference)?", "status": r"(filing |candidate )?status", "order": r"ballot order|order|position",
         "votes": r"(total )?votes(?: cast)?|vote count"}
PARTIES = {"DEM": "Democratic", "REP": "Republican", "LPN": "Libertarian", "LIB": "Libertarian", "IAP": "Independent American",
           "NP": "No Political Party", "NPP": "No Political Party", "NON": "No Political Party", "GRN": "Green"}
FULL = {"democratic party": "Democratic", "democrat": "Democratic", "republican party": "Republican", "libertarian party": "Libertarian",
        "libertarian party of nevada": "Libertarian", "independent american party": "Independent American",
        "nonpartisan": "No Political Party", "non-partisan": "No Political Party", "no party": "No Political Party"}
COLOUR = {"Independent American": "O", "No Political Party": "I"}      # party_code would colour the Independent American Party as an independent
PRIMARY_CODE = {"Democratic": "DEM", "Republican": "REP", "Libertarian": "LIB", "Independent American": "IAP"}
OFF = re.compile(r"withdr|remov|disqual|deceas|reject|denied|not certified|inactive", re.I)
ON = re.compile(r"^(certified|qualified|filed|active|nominated|on ballot|accepted|approved)$", re.I)
CONGRESS = re.compile(r"(?:representative in congress|u\.?\s?s\.?\s+representative|united states representative|congressional)", re.I)
DISTRICT = re.compile(r"(?:district|dist\.?)\s*(?:no\.?\s*)?(\d{1,2})\b|\b(\d)(?:st|nd|rd|th)\s+(?:congressional\s+)?district", re.I)
SENATE = re.compile(r"(?:u\.?\s?s\.?|united states)\s+senat", re.I)
NUMBER = re.compile(r"^\d{1,3}(?:,\d{3})*$|^\d+$")
CAPS = "Nevada's list prints names in capitals; they are shown here in ordinary capitals."
CAPS_RESULTS = "Nevada's results print names in capitals; they are shown here in ordinary capitals."


def saved(folder, kind):
    """The file a browser saved for one kind, or None; a copy of the bot wall's own page is refused."""
    found = sorted(p for p in glob.glob(os.path.join(folder, STEMS[kind] + ".*")) if p.lower().endswith(KINDS))
    if not found:
        pdfs = glob.glob(os.path.join(folder, STEMS[kind] + ".pdf"))
        if pdfs:
            raise SystemExit(f"Nevada: {os.path.basename(pdfs[0])} is a PDF; this loader reads the list as a table (HTML, CSV or a workbook). "
                             "Save the page itself, or teach ballot/lists/nv.py the PDF's columns")
        return None
    path = found[0]
    head = open(path, "rb").read(4096)
    if path.lower().endswith(".xlsx") and not head.startswith(b"PK"):
        raise SystemExit(f"Nevada: {os.path.basename(path)} is not a workbook (first bytes {head[:8]!r})")
    if b"_Incapsula_Resource" in head or b"Request unsuccessful" in head:
        raise SystemExit(f"Nevada: {os.path.basename(path)} is the bot wall's page, not the file; save it again from a browser that shows the page")
    return path


def clean(text):
    return re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", text or "")).replace("\xa0", " ")).strip()


def head_key(text):
    t = re.sub(r"[:*]+$", "", clean(str(text or ""))).strip().lower()
    return next((k for k, pat in HEADS.items() if re.fullmatch(pat, t)), None)


def html_rows(page):
    """Every row of every innermost table, as lists of cell texts, in the page's order."""
    for table in re.findall(r"<table\b(?:(?!<table\b).)*?</table>", page, re.S | re.I):
        yield None                                                           # a new table: its headings are found afresh
        for tr in re.findall(r"<tr\b[^>]*>(.*?)</tr>", table, re.S | re.I):
            yield [clean(c) for c in re.findall(r"<t[hd]\b[^>]*>(.*?)</t[hd]>", tr, re.S | re.I)]


def raw_rows(path):
    """Rows of cell texts from a saved page, a CSV or a workbook (every sheet), with None where a new table begins."""
    low = path.lower()
    if low.endswith(".xlsx"):
        import openpyxl
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        for ws in wb.worksheets:
            yield None
            for r in ws.iter_rows(values_only=True):
                yield ["" if c is None else re.sub(r"\s+", " ", str(c)).strip() for c in r]
        wb.close()
        return
    text = open(path, encoding="utf-8-sig", errors="replace").read()
    if low.endswith(".csv") or not text.lstrip().startswith("<"):
        yield None
        for r in csv.reader(io.StringIO(text)):
            yield [re.sub(r"\s+", " ", c).strip() for c in r]
        return
    yield from html_rows(text)


def table(path):
    """([row dicts of the allowlisted columns, with the group heading above each row], headings found) from the
    tables in a file. A table's heading row is its first row naming a candidate column and at least one other."""
    out, seen, cols, group = [], [], None, ""
    for row in raw_rows(path):
        if row is None:
            cols, group = None, ""
            continue
        if cols is None:
            keys = [head_key(c) for c in row]
            if "name" in keys and sum(1 for k in keys if k) >= 2:
                cols = {k: i for i, k in reversed(list(enumerate(keys))) if k}
                seen.append([c for c, k in zip(row, keys) if k])          # the allowlisted headings only
            continue
        filled = [c for c in row if c]
        if not filled:
            continue
        if len(filled) == 1 and sum(1 for i in cols.values() if i < len(row) and row[i]) < 2:
            group = filled[0]                                              # a heading row across the table (an office, a party)
            continue
        if len(row) < max(cols.values()) + 1:
            if any(CONGRESS.search(c) for c in row):
                raise SystemExit(f"Nevada: a row naming a congressional office in {os.path.basename(path)} does not line up with its headings")
            continue
        out.append({**{k: row[i] for k, i in cols.items()}, "_group": group})
    return out, seen


def race_of(office, district="", group=""):
    """The race a row belongs to, from its office, its district and the heading above it; None for any other office."""
    t = " ".join(x for x in (office, group) if x)
    if SENATE.search(t):
        raise SystemExit(f"Nevada: a U.S. Senate row ({t!r}), but Nevada elects no senator in 2026; read the file again")
    if not CONGRESS.search(t):
        return None
    m = DISTRICT.search(f"{t} {district}")
    bare = re.fullmatch(r"(?:no\.?\s*)?0?(\d)", (district or "").strip(), re.I)
    if not m and not bare:
        raise SystemExit(f"Nevada: a congressional row names no district that is read ({t!r}, {district!r})")
    d = int(m.group(1) or m.group(2)) if m else int(bare.group(1))
    if not 1 <= d <= 4:
        raise SystemExit(f"Nevada: a congressional district {d}; Nevada has four")
    return house_id("NV", d)


def party_of(label):
    t = re.sub(r"\s+", " ", (label or "").strip().strip("()"))
    if not t:
        return ""
    if t.upper() in PARTIES:
        return PARTIES[t.upper()]
    if t.lower() in FULL:
        return FULL[t.lower()]
    return proper(t.upper()) if t.isupper() else t


def colour(party):
    return COLOUR.get(party) or party_code(party)


def turned(raw):
    """'TITUS, DINA' -> 'DINA TITUS'; 'THOMAS, JR., ANTHONY' -> 'ANTHONY THOMAS JR.'; an incumbent's asterisk dropped."""
    raw = re.sub(r"\s+", " ", (raw or "").replace("*", " ")).strip()
    if "," not in raw:
        return raw
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    family, rest = parts[0], parts[1:]
    suffix = [p for p in rest if fold(p) in SUFFIXES]
    given = [p for p in rest if fold(p) not in SUFFIXES]
    if len(given) != 1:
        return raw if not given else " ".join(given + [family] + suffix)
    return " ".join([given[0], family] + suffix)


def words(name):
    w = [x for x in fold(re.sub(r"\"[^\"]*\"|\([^)]*\)|“[^”]*”", " ", turned(name))).split() if x not in SUFFIXES]
    return w or [""]


def same(a, b):
    """The same person in two files: the family name and the first initial, or one name's words inside the other's."""
    A, B = words(a), words(b)
    return (A[-1] == B[-1] and A[0][:1] == B[0][:1]) or set(A) <= set(B) or set(B) <= set(A)


def roster():
    """Sitting members' names as the congress-legislators roster spells them, keyed by their capitals."""
    fixed = {}
    path = os.path.join(HERE, "congress_119.sqlite")
    if os.path.exists(path):
        rec = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        for full, first, last in rec.execute("SELECT official_full, first_name, last_name FROM legislators WHERE is_current = 1 AND state = 'NV'"):
            for form in (full, f"{first} {last}"):
                if form:
                    fixed[fold(form)] = full or form
        rec.close()
    return fixed


def shown(raw, fixed):
    """(name to show, whether it was printed in capitals)."""
    name = turned(raw)
    if not (re.search(r"[A-Z]", name) and name == name.upper()):
        return name, False
    if fold(name) in fixed:
        return fixed[fold(name)], True
    return re.sub(r"(['\"(“])([a-z])", lambda m: m.group(1) + m.group(2).upper(), proper(name)), True


def general_list(path, fixed):
    """([(race, name, party, order, caps)], [left off], headings) from the November list."""
    rows, seen = table(path)
    on, off, order = [], [], {}
    for r in rows:
        race = race_of(r.get("office", ""), r.get("district", ""), "" if r.get("office") else r["_group"])
        if not race or not r.get("name"):
            continue
        status = r.get("status", "")
        if status and OFF.search(status):
            off.append((race, r["name"]))
            continue
        if status and not ON.match(status):
            raise SystemExit(f"Nevada: a status on the November list that is not read ({status!r}, {race})")
        party = party_of(r.get("party") or "")
        if not party:
            m = re.search(r"\(([A-Z]{2,3})\)\s*$", r["name"])
            party = party_of(m.group(1)) if m else ""
        if not party:
            raise SystemExit(f"Nevada: a candidate for {race} with no party on the November list")
        name, caps = shown(re.sub(r"\s*\([A-Z]{2,3}\)\s*$", "", r["name"]), fixed)
        order[race] = order.get(race, 0) + 1
        given = r.get("order", "")
        on.append((race, name, party, int(given) if given.isdigit() else order[race], caps))
    if not on:
        raise SystemExit(f"Nevada: no candidate for Congress read from {os.path.basename(path)} (headings read: {seen})")
    return on, off, seen


def official(path):
    """Whether a results file calls itself official and not unofficial."""
    if path.lower().endswith((".xlsx", ".csv")):
        first = []
        for r in raw_rows(path):
            if r:
                first.append(" ".join(r))
            if len(first) >= 12:
                break
        text = " ".join(first)
    else:
        page = open(path, encoding="utf-8-sig", errors="replace").read()
        title = re.search(r"<title[^>]*>(.*?)</title>", page, re.S | re.I)
        text = clean(title.group(1)) + " " + clean(page[:60000]) if title else clean(page[:60000])
    return bool(re.search(r"\bofficial\b", text, re.I)) and not re.search(r"\bunofficial\b", text, re.I)


def primary_results(path, fixed):
    """{(race, party): {"names": [(name, votes, caps)], "total": printed total or None}} from the official results."""
    if not official(path):
        raise SystemExit(f"Nevada: {os.path.basename(path)} does not call itself the official results (or calls itself unofficial); "
                         "only the canvassed figures are stored")
    out, race, party, cols = {}, None, "", None
    party_text = lambda t: next((PARTIES[c] for c in re.findall(r"\b(DEM|REP|LPN|IAP)\b", t)), "") or next(
        (p for w, p in (("democratic", "Democratic"), ("republican", "Republican")) if re.search(rf"\b{w}\b", t, re.I)), "")
    if path.lower().endswith((".csv", ".xlsx")):
        rows, seen = table(path)
        for r in rows:
            rc = race_of(r.get("office", ""), r.get("district", ""), r["_group"])
            if not rc or not r.get("name") or not NUMBER.match(r.get("votes", "")):
                continue
            p = party_of(r.get("party", "")) or party_text(r.get("office", "") + " " + r["_group"])
            name, caps = shown(r["name"], fixed)
            f = out.setdefault((rc, p), {"names": {}, "total": None})
            f["names"][name] = (f["names"].get(name, (0,))[0] + int(r["votes"].replace(",", "")), caps)
        return {k: {"names": [(n, v, c) for n, (v, c) in f["names"].items()], "total": None} for k, f in out.items()}
    page = open(path, encoding="utf-8-sig", errors="replace").read()
    token = re.compile(r"<tr\b[^>]*>(.*?)</tr>|>([^<>]*\S[^<>]*)<", re.S | re.I)
    for m in token.finditer(page):
        if m.group(2) is not None:                                          # a heading outside a table
            t = clean(m.group(2))
            if CONGRESS.search(t) and DISTRICT.search(t) and len(t) < 160:
                race, party, cols = race_of(t), party_text(t), None
            elif race and re.fullmatch(r"(?:democratic|republican)(?: party)?|dem|rep", t, re.I):
                party = party_text(t)
            continue
        cells = [clean(c) for c in re.findall(r"<t[hd]\b[^>]*>(.*?)</t[hd]>", m.group(1), re.S | re.I)]
        filled = [c for c in cells if c]
        joined = " ".join(filled)
        if len(filled) <= 2 and CONGRESS.search(joined) and DISTRICT.search(joined):
            race, party, cols = race_of(joined), party_text(joined), None
            continue
        if not race:
            continue
        if len(filled) == 1 and re.fullmatch(r"(?:democratic|republican)(?: party)?|dem|rep", filled[0], re.I):
            party = party_text(filled[0])                                   # a party's heading row inside the contest's table
            continue
        keys = [head_key(c) for c in cells]
        if "votes" in keys:
            cols = {k: i for i, k in reversed(list(enumerate(keys))) if k}
            cols.setdefault("name", 0)
            continue
        if not cols or len(cells) <= max(cols.values()):
            continue
        votes = cells[cols["votes"]]
        if not NUMBER.match(votes):
            continue
        label = cells[cols["name"]]
        p = party_of(cells[cols["party"]]) if "party" in cols else ""
        suffix = re.search(r"\(([A-Z]{2,3})\)\s*$", label)
        p = p or (party_of(suffix.group(1)) if suffix else "") or party
        if not p:
            raise SystemExit(f"Nevada: no party read for a candidate under {race} in {os.path.basename(path)}")
        f = out.setdefault((race, p), {"names": [], "total": None})
        if re.match(r"total", label, re.I):
            f["total"] = int(votes.replace(",", ""))
            continue
        name, caps = shown(re.sub(r"\s*\([A-Z]{2,3}\)\s*$", "", label), fixed)
        f["names"].append((name, int(votes.replace(",", "")), caps))
    if not out:
        raise SystemExit(f"Nevada: no congressional contest read from {os.path.basename(path)}; read the saved page again")
    return out


def filings(path, fixed):
    """{(race, party): [names]} of the candidates who filed and did not withdraw, from Aurora's list for the cycle."""
    rows, seen = table(path)
    out = {}
    for r in rows:
        race = race_of(r.get("office", ""), r.get("district", ""), "" if r.get("office") else r["_group"])
        if not race or not r.get("name") or OFF.search(r.get("status", "")):
            continue
        party = party_of(r.get("party", ""))
        if party in PRIMARY_CODE:
            out.setdefault((race, party), []).append(shown(r["name"], fixed))
    if not out:
        raise SystemExit(f"Nevada: no candidate for Congress read from {os.path.basename(path)} (headings read: {seen})")
    return out


def load(con, cache, say=print):
    folder = os.path.join(cache, "nv")
    os.makedirs(folder, exist_ok=True)
    gpath = saved(folder, "general")
    if not gpath:
        with con:
            con.execute("DELETE FROM candidates WHERE race_id LIKE '2026-NV-%'")
            con.execute("DELETE FROM list_gaps WHERE state = 'NV'")
            con.execute("DELETE FROM ballot_sources WHERE source_id LIKE 'nv-sos-2026-%'")      # none of this loader's files is in use
            con.executemany("INSERT INTO list_gaps VALUES (?, 'NV', ?)", [(race, GAP) for race in RACES])
        say(f"    Nevada: waiting for the Secretary of State's certified November list in {folder} (its sites answer scripts with an "
            f"Incapsula challenge, so a browser saves it as {STEMS['general']}.html); the 4 House races are marked not loaded")
        return 0
    fixed = roster()
    on, off, _seen = general_list(gpath, fixed)
    rows = [(race, "general", "2026-11-03", name, party, colour(party), order, 0, 0, None, None, None, None, None,
             "nv-sos-2026-general-list", CAPS if caps else None) for race, name, party, order, caps in on]
    nominee = {}
    for race, name, party, _o, _c in on:
        nominee.setdefault((race, party), name)
    missing = [race for race in RACES if not any(r[0] == race for r in on)]
    if missing:
        raise SystemExit(f"Nevada: the November list names no candidate for {', '.join(missing)}; read the file again")

    ppath, fpath = saved(folder, "primary"), saved(folder, "filings")
    nfields, checks, used = 0, [], {}
    if ppath:
        results = primary_results(ppath, fixed)
        used["primary"] = ppath
        for (race, party), f in sorted(results.items()):
            total = sum(v for _n, v, _c in f["names"])
            if f["total"] is not None and f["total"] != total:
                raise SystemExit(f"Nevada: the {race} {party} primary's candidates add up to {total:,}; the results print a total of {f['total']:,}")
            if len(f["names"]) < 2:
                continue
            nfields += 1
            listed = nominee.get((race, party))
            top = max(f["names"], key=lambda n: n[1])[0]
            if listed and not same(top, listed):
                checks.append(f"{race} {party}: the top vote-getter is {top}; the November list names {listed}")
            for name, votes, caps in sorted(f["names"], key=lambda n: -n[1]):
                won = same(name, listed) if listed else name == top
                note = " ".join(x for x in (
                    CAPS_RESULTS if caps else None,
                    "Won the nomination; not on the November list read." if won and not listed else None) if x) or None
                rows.append((race, f"primary-{PRIMARY_CODE.get(party, party[:3].upper())}", PRIMARY, name, party, colour(party), None, 0, 0,
                             votes, round(100 * votes / total, 1) if total else None, "advanced" if won else "lost", None, None,
                             "nv-sos-2026-primary-results", note))
    elif fpath:
        used["filings"] = fpath
        for (race, party), names in sorted(filings(fpath, fixed).items()):
            if len(names) < 2:
                continue
            nfields += 1
            listed = nominee.get((race, party))
            for name, caps in names:
                note = " ".join(x for x in (CAPS if caps else None, "The primary's official vote counts are not loaded yet.") if x)
                rows.append((race, f"primary-{PRIMARY_CODE[party]}", PRIMARY, name, party, colour(party), None, 0, 0, None, None,
                             "advanced" if listed and same(name, listed) else "lost", None, None, "nv-sos-2026-filings", note))

    general = [r for r in rows if r[1] == "general"]
    with con:
        con.execute("DELETE FROM candidates WHERE race_id LIKE '2026-NV-%'")
        con.execute("DELETE FROM list_gaps WHERE state = 'NV'")
        con.execute("DELETE FROM ballot_sources WHERE source_id LIKE 'nv-sos-2026-%'")      # a file no longer used is not kept on record
        con.executemany("INSERT OR REPLACE INTO candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        record_source(con, "nv-sos-2026-general-list", path=gpath, level="federal", state="NV", kind="official candidate list",
                      agency="Nevada Secretary of State, Elections Division",
                      title="Candidate Filing List, 2026 General Election (November 3, 2026): Representative in Congress", url=LIST_PAGE,
                      rows=len(on) + len(off),
                      note=f"Saved from a browser ({os.path.basename(gpath)}): the Secretary of State's site answers scripts with an Incapsula "
                           "challenge. Name, office, district, party, status and ballot order read by their headings; addresses, telephones, "
                           f"e-mail and websites never read. Withdrawn or removed, left off: {len(off)}. Nevada allows no write-in votes.")
        if "primary" in used:
            record_source(con, "nv-sos-2026-primary-results", path=ppath, level="federal", state="NV", kind="official results",
                          agency="Nevada Secretary of State, Elections Division",
                          title="2026 Official Statewide Primary Election Results (June 9, 2026): Representative in Congress", url=RESULTS_PAGE,
                          rows=sum(1 for r in rows if r[1].startswith("primary")),
                          note=f"Saved from a browser ({os.path.basename(ppath)}). Nevada allows no write-in votes, so a field's total is its "
                               "candidates' votes; each printed Total row matches them.")
        if "filings" in used:
            record_source(con, "nv-sos-2026-filings", path=fpath, level="federal", state="NV", kind="official candidate list",
                          agency="Nevada Secretary of State, Elections Division", title="Candidate Filing List, 2026 election cycle",
                          url=LIST_PAGE, rows=sum(1 for r in rows if r[1].startswith("primary")),
                          note=f"Saved from a browser ({os.path.basename(fpath)}). Each party primary's field; who advanced is read from the "
                               "November list, and the vote counts are not loaded. Addresses, telephones and e-mail never read.")
    for c in checks:
        say(f"      check: {c}")
    how = ("votes from the official results" if "primary" in used else "fields from the filing list, votes not loaded" if "filings" in used
           else "the primary results are not saved yet")
    say(f"    Nevada: 4 House districts, {len(general)} candidates on the November ballot ({len(off)} withdrawn or removed left off); "
        f"{nfields} party primaries with a field, {how}")
    return len(general)
