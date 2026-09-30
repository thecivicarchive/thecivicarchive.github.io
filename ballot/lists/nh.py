"""
New Hampshire: the Secretary of State's own list of November candidates and its results of the September 8, 2026 State
Primary. New Hampshire has two House seats (District 1 open: Chris Pappas runs for the Senate) and the class 2 Senate
seat (Jeanne Shaheen is not running).

The Secretary's site (www.sos.nh.gov, and app.sos.nh.gov) answers scripts with an Akamai "Access Denied" page (tried
2026-09-30 with the kit's honest User-Agent, three times, then left alone), so nothing here is downloaded. John saves the
files in his own browser into ballot_cache/nh/, under the names the site gives them, and this loader reads whatever is
there. Until the November list is there, the three races say their list is coming (list_gaps).

  November ballot   "2026 General Election Candidates" on the 2026 Election Details page (sos.nh.gov/2026-election-details):
                    a PDF the Secretary prints from its election system, headed "General Election Candidates List with
                    Write-ins" and "Election : 11/03/2026 -- STATE GENERAL ELECTION" (2024's, general-election-candidates-
                    list-10.8.24.pdf, was posted on October 8). Saved as general-election-candidates-list-<date>.pdf. It has
                    two columns only, Candidate Name and Party, under a heading per office ("United States Senator",
                    "Representative in Congress" with "District No: 1" and "Vote for not more than 1"). The list
                    names each party's nominee (a write-in winner of a primary is printed on the November ballot like any
                    nominee, hence "with Write-ins") and each candidate nominated by nomination papers, with the party
                    or the word Independent. Only rows in the two federal sections are used. A candidate row with text
                    anywhere but the name and party columns stops the loader, so a new column is never read by accident.
                    The list gives no ballot positions (New Hampshire prints one column per party and rotates the
                    columns between districts), so the list's own order is kept. The list has no status column:
                    a candidate who withdrew is no longer on it and cannot be counted.
  primary results   the 2026 Democratic and Republican State Primary pages (sos.nh.gov/2026-democratic-state-primary,
                    .../2026-republican-state-primary, both linked from .../2026-state-primary-election-results), one Excel
                    workbook per office and party: "US Senator Summary" (2026-sp-us-senator-summary-<party>.xlsx, one row
                    per county), the ten "US Senator <County>" files (2026-sp-us-senator-<county>-<party>.xlsx, one row per
                    town and ward) and "Representative in Congress District No. 1" and "No. 2"
                    (2026-sp-congressional-district-<n>-<party>.xlsx, one row per town and ward). The pages say: "Tallies
                    accurately reflect the returns of votes reported by clerk but are subject to change if clerks submit
                    amendments"; they are the town and city clerks' official returns as the Secretary tallies them, and a
                    recount's result replaces a file (the site then adds _1, _2 to its name). Read: the heading rows
                    (title, date and one column per candidate, "Name, r" or "Last, First (r)", then Write-Ins,
                    Overvotes and Undervotes), every place row and the Totals row; every column must add up to its
                    Totals row, and a sheet whose columns wrap onto a second block must list the same places in each.
                    Where the ten county files are saved, each county's totals must equal its row of the Summary. The
                    files carry votes only, no addresses of any kind.

A primary's field is the candidates of the primary's own party (the party letter after each name); a candidate of
another party named in the file received write-in votes, and those votes count toward the total with the Write-Ins
column, as do any named write-ins of the same party (none can be told apart from printed names in these files, so a
file whose leader is not a printed candidate would show as one: checked against the November list). Overvotes and
undervotes are not votes for anyone. A field is a party primary with two candidates or more; New Hampshire nominates
the one with the most votes, who must be the party's candidate on the November list, or the row says plainly that the
nominee is not on it. Libertarian and other parties have no state primary in 2026 (only the two primary pages exist).

Names are printed first name first in ordinary capitals ("Last, First" in the county files is turned round); a name in
capitals would be shown in ordinary capitals and the row would say so. Parties are printed in full on the list and kept
as printed.

The layouts read are those of the Secretary's 2024 files (the 2024 State Primary's congressional district workbooks, the
2024 Presidential Primary's summary and county workbooks, whose columns wrap onto a second block, and the 2024 General
Election Candidates List), looked at in copies kept by the Internet Archive because the Secretary's own site could not be
reached; the 2026 files themselves were not seen before this loader was written. Anything laid out otherwise stops the
loader and names the file. The Secretary's other lists are never opened: the primary winners lists and the filing lists
print mailing addresses, and only a PDF named general-election-candidates... is read. The list's PDF writer puts a space
between "stream" and its line end, which ballot/pdftext.py does not expect, so that one space is taken out before reading.
"""

import datetime as dt
import hashlib
import json
import os
import re

import openpyxl

from ballot.common import fold, house_id, name_parts, party_code, record_source, senate_id
from ballot.lists.tx import proper
from ballot.pdftext import PDF, join, rows as pdf_rows

SITE = "https://www.sos.nh.gov"
DETAILS = SITE + "/2026-election-details"
RESULTS_PAGE = SITE + "/2026-state-primary-election-results"
FILES = SITE + "/sites/g/files/ehbemt561/files/inline-documents/sonh/"
PRIMARY = "2026-09-08"
PRIMARY_DATE = dt.date(2026, 9, 8)
PARTIES = {"DEM": ("democratic", "Democratic", "d"), "REP": ("republican", "Republican", "r")}
PAGES = {"DEM": SITE + "/2026-democratic-state-primary", "REP": SITE + "/2026-republican-state-primary"}
COUNTIES = ("belknap", "carroll", "cheshire", "coos", "grafton", "hillsborough", "merrimack", "rockingham", "strafford", "sullivan")
SENATE, HOUSE = senate_id("NH", 2), {1: house_id("NH", 1), 2: house_id("NH", 2)}
ELECTION_LINE = re.compile(r"11/03/2026\s*--\s*STATE GENERAL ELECTION")
GENERAL_FILE = re.compile(r"general[-_ ]election[-_ ]candidates?.*\.pdf$", re.I)       # only this PDF is ever opened
SENATE_HEAD = re.compile(r"(United States|U\.\s?S\.|US) Senator", re.I)
HOUSE_HEAD = re.compile(r"Representative in Congress", re.I)
OTHER_HEADS = re.compile(r"^(President\b.*|Governor|Executive Councilor|State Senator|State Representative|Sheriff|County\b.*|"
                         r"Register of\b.*|Delegate\b.*|" + "|".join(COUNTIES) + r")$", re.I)
FURNITURE = re.compile(r"Secretary of State|Candidates List|^Election\s*:|Printed on|Page \d+ of \d+", re.I)
NAME_BAND, PARTY_BAND = 230, 330          # x: names left of 230, parties from 230 to 330 (2024: names at 38, parties at 236)
CAPS = "New Hampshire's list prints names in capitals; they are shown here in ordinary capitals."
CAPS_RESULTS = "New Hampshire's results print names in capitals; they are shown here in ordinary capitals."
GAP = "the Secretary of State's site turns away automated downloads, so its list is saved by hand, and that has not been done yet"


def say_files(folder):
    return ("the Excel files \"US Senator Summary\" (and the ten county files), \"Representative in Congress District No. 1\" "
            f"and \"No. 2\" from {PAGES['DEM']} and {PAGES['REP']} (both linked from {RESULTS_PAGE}), and \"2026 General Election "
            f"Candidates\" (PDF) from {DETAILS}, saved into {folder}")


# ---------- the results workbooks ----------

def turned(s):
    """"Carney, Robert S. Jr" -> "Robert S. Carney Jr"."""
    last, _, first = s.partition(",")
    if not first.strip():
        return s.strip()
    words = first.split()
    suffix = [w for w in words if w.rstrip(".").lower() in ("jr", "sr", "ii", "iii", "iv")]
    return " ".join([w for w in words if w not in suffix] + [last.strip()] + suffix)


def head_cell(c):
    """What one heading cell names: ("cand", name, party letter), ("wi",), ("over",), ("under",), None if blank, ("?", text)."""
    if c is None:
        return None
    t = re.sub(r"\s+", " ", str(c)).strip()
    if not t:
        return None
    if re.fullmatch(r"write[- ]?ins?|scatter(ing)?", t, re.I):
        return ("wi",)
    if re.fullmatch(r"over ?votes?", t, re.I):
        return ("over",)
    if re.fullmatch(r"under ?votes?|blanks?", t, re.I):
        return ("under",)
    m = re.fullmatch(r"(.+?)\s*\(([a-z]{1,3})\)", t, re.I)                    # "Ayers, Scott A. (r)": family name first
    if m:
        return ("cand", turned(m.group(1)), m.group(2).lower())
    m = re.fullmatch(r"(.+?),\s*([a-z]{1,3})", t, re.I)                       # "Walter J. McFarlane III, r": as printed
    if m and ("," not in m.group(1) or re.fullmatch(r"[^,]+, (Jr|Sr|II|III|IV)\.?", m.group(1))):
        return ("cand", m.group(1).strip(), m.group(2).lower())
    return ("?", t)


def num(v, what):
    if v is None or (isinstance(v, str) and not v.strip()):
        return 0
    if isinstance(v, (int, float)) and float(v).is_integer() and v >= 0:
        return int(v)
    raise SystemExit(f"New Hampshire: {what}: a figure that is not a count ({v!r})")


def place_key(p):
    return re.sub(r"\s*county$", "", fold(p.replace("*", "")))


def read_book(path, what):
    """Every block of one results sheet: its candidates' totals, the write-ins, the places, every column checked."""
    with open(path, "rb") as fh:
        if fh.read(2) != b"PK":
            raise SystemExit(f"New Hampshire: {os.path.basename(path)} is not an Excel workbook (.xlsx)")
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        sheets = len(wb.worksheets)
        sheet = [list(r) for r in wb.worksheets[0].iter_rows(values_only=True)]
    finally:
        wb.close()                               # a read-only workbook holds its file open until closed
    if sheets != 1:
        raise SystemExit(f"New Hampshire: {what} has {sheets} sheets; one was expected")
    title, dates, blocks, notes, cur = [], [], [], [], None
    for r in sheet:
        while r and (r[-1] is None or (isinstance(r[-1], str) and not r[-1].strip())):
            r.pop()
        if not r:
            continue
        for c in r:
            if isinstance(c, (dt.datetime, dt.date)):
                dates.append(c.date() if isinstance(c, dt.datetime) else c)
        label, vals = r[0], r[1:]
        heads = [head_cell(c) for c in vals]
        if any(h and h[0] == "cand" for h in heads):
            bad = [h[1] for h in heads if h and h[0] == "?"]
            if bad:
                raise SystemExit(f"New Hampshire: {what}: headings that are not read ({bad})")
            if cur and cur["total"] is None:
                raise SystemExit(f"New Hampshire: {what}: a block with no Totals row")
            if isinstance(label, str) and label.strip():
                title.append(label.strip())
            cur = {"heads": heads, "rows": [], "since": [], "total": None}
            blocks.append(cur)
            continue
        if cur is None:                          # the title rows above the first heading
            title += [str(c).strip() for c in r if isinstance(c, str) and c.strip()]
            continue
        text = str(label).strip() if label is not None and not isinstance(label, (dt.datetime, dt.date)) else ""
        figures = [v for v in vals if v is not None and not (isinstance(v, str) and not v.strip())]
        if cur["total"] is not None:             # below the Totals row: notes such as "*Correction issued by Town Clerk"
            if figures:
                raise SystemExit(f"New Hampshire: {what}: figures below the Totals row")
            if text:
                notes.append(text)
            continue
        if re.fullmatch(r"(grand |state )?totals?", text, re.I):
            cur["total"] = vals
            continue
        if not text:
            if figures:
                raise SystemExit(f"New Hampshire: {what}: a row of figures with no place")
            continue
        if re.search(r"\btotals?$", text, re.I):   # a county's subtotal: it must equal the rows above it, and is not added again
            width = max([len(vals)] + [len(v) for _p, v in cur["since"]])
            for i in range(width):
                got = sum(num(v[i] if i < len(v) else None, what) for _p, v in cur["since"])
                if got != num(vals[i] if i < len(vals) else None, what):
                    raise SystemExit(f"New Hampshire: {what}: the subtotal {text!r} does not add up")
            cur["since"] = []
            continue
        cur["rows"].append((text, vals))
        cur["since"].append((text, vals))
    if not blocks or blocks[-1]["total"] is None:
        raise SystemExit(f"New Hampshire: {what}: no candidates' heading row and Totals row were found")

    cands, write_ins, over, under, places = {}, 0, 0, 0, None
    wi_by_place, has_wi = {}, False
    for b in blocks:
        width = max([len(b["heads"]), len(b["total"])] + [len(v) for _p, v in b["rows"]])
        heads = b["heads"] + [None] * (width - len(b["heads"]))
        for i, h in enumerate(heads):
            col = [num(v[i] if i < len(v) else None, what) for _p, v in b["rows"]]
            tot = num(b["total"][i] if i < len(b["total"]) else None, what)
            if h is None:
                if any(col) or tot:
                    raise SystemExit(f"New Hampshire: {what}: figures under a blank heading")
                continue
            if sum(col) != tot:
                raise SystemExit(f"New Hampshire: {what}: a column does not add up to its Totals row ({sum(col)} against {tot})")
            by_place = {place_key(p): n for (p, _v), n in zip(b["rows"], col)}
            if h[0] == "cand":
                key = (h[1], h[2])
                if key in cands:
                    raise SystemExit(f"New Hampshire: {what}: {h[1]} has two columns")
                cands[key] = {"votes": tot, "by_place": by_place}
            elif h[0] == "wi":
                has_wi = True
                write_ins += tot
                for p, n in by_place.items():
                    wi_by_place[p] = wi_by_place.get(p, 0) + n
            elif h[0] == "over":
                over += tot
            else:
                under += tot
        ps = sorted(place_key(p) for p, _v in b["rows"])
        if places is None:
            places = ps
        elif ps != places:
            raise SystemExit(f"New Hampshire: {what}: the blocks of the sheet list different places")
    return {"title": " ".join(title), "dates": sorted(set(dates)), "cands": cands, "write_ins": write_ins, "has_wi": has_wi,
            "wi_by_place": wi_by_place, "over": over, "under": under, "places": places or [], "notes": notes, "blocks": len(blocks)}


def check_heading(book, what, party_word, office):
    """The file must say it is the 2026 State Primary, for this office and this party."""
    t = book["title"]
    if book["dates"] and book["dates"] != [PRIMARY_DATE]:
        raise SystemExit(f"New Hampshire: {what} is dated {', '.join(str(d) for d in book['dates'])}, not September 8, 2026")
    written = re.findall(r"(January|February|March|April|May|June|July|August|September|October|November|December) (\d{1,2}), (\d{4})", t)
    if any((m, int(d), int(y)) != ("September", 8, 2026) for m, d, y in written):
        raise SystemExit(f"New Hampshire: {what} names another date ({t!r})")
    if not book["dates"] and not written and "2026" not in t:
        raise SystemExit(f"New Hampshire: {what} does not say it is the 2026 primary ({t!r})")
    if party_word not in t.lower():
        raise SystemExit(f"New Hampshire: {what} does not say it is the {party_word.title()} primary ({t!r})")
    if not re.search(office, t, re.I):
        raise SystemExit(f"New Hampshire: {what} does not name its office as expected ({t!r})")


def saved(folder, stem, say):
    """The one saved copy of a Secretary of State file: named as the site names it, with the _1 the site may add after a
    correction or the (1) a browser may add. Several copies stop the loader; a PDF alone is named and not read."""
    if not os.path.isdir(folder):
        return None
    pat = re.compile(rf"^{re.escape(stem)}(?:_\d+)?(?: ?\(\d+\))?\.(xlsx|pdf)$", re.I)
    hits = sorted(f for f in os.listdir(folder) if pat.match(f))
    books = [f for f in hits if f.lower().endswith(".xlsx")]
    if len(books) > 1:
        raise SystemExit(f"New Hampshire: {len(books)} saved copies of {stem} in {folder} ({', '.join(books)}); keep the newest only")
    if not books and hits:
        say(f"      {hits[0]} is a PDF; the loader reads the Excel version of the same file")
    return os.path.join(folder, books[0]) if books else None


def sha(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def senate_primary(folder, code, say):
    """(candidates, write-ins, the file behind them, the county files, the figures read) for one party's Senate primary."""
    word, _label, _letter = PARTIES[code]
    summary_path = saved(folder, f"2026-sp-us-senator-summary-{word}", say)
    county_paths = {c: saved(folder, f"2026-sp-us-senator-{c}-{word}", say) for c in COUNTIES}
    have = {c: p for c, p in county_paths.items() if p}
    if have and len(have) != len(COUNTIES):
        raise SystemExit(f"New Hampshire: {len(have)} of the ten US Senator county files for the {word.title()} primary are saved; "
                         f"save all ten, or none (missing: {', '.join(c for c in COUNTIES if c not in have)})")
    summary = None
    if summary_path:
        summary = read_book(summary_path, os.path.basename(summary_path))
        check_heading(summary, os.path.basename(summary_path), word, r"senat")
        if sorted(summary["places"]) != sorted(COUNTIES):
            raise SystemExit(f"New Hampshire: {os.path.basename(summary_path)} does not list the ten counties ({summary['places']})")
    counties = {}
    for c, p in have.items():
        book = read_book(p, os.path.basename(p))
        check_heading(book, os.path.basename(p), word, r"senat")
        if c not in fold(book["title"]):
            raise SystemExit(f"New Hampshire: {os.path.basename(p)} does not name {c.title()} County in its heading ({book['title']!r})")
        counties[c] = book
    if not summary and not counties:
        return None
    if counties:
        names = {k for b in counties.values() for k in b["cands"]}
        summed = {k: sum(b["cands"].get(k, {"votes": 0})["votes"] for b in counties.values()) for k in names}
        summed_wi = sum(b["write_ins"] for b in counties.values())
        if summary:                                              # control: every county's totals are its row of the Summary
            if set(summary["cands"]) != names:
                raise SystemExit(f"New Hampshire: the {word.title()} Senate Summary and county files name different candidates")
            for c, b in counties.items():
                for k, v in b["cands"].items():
                    if summary["cands"][k]["by_place"].get(c) != v["votes"]:
                        raise SystemExit(f"New Hampshire: {k[0]}'s {c.title()} County total differs between the county file and the Summary")
                if summary["has_wi"] and summary["wi_by_place"].get(c, 0) != b["write_ins"]:
                    raise SystemExit(f"New Hampshire: {c.title()} County's write-ins differ between the county file and the Summary")
    if summary:
        cands = {k: v["votes"] for k, v in summary["cands"].items()}
        write_ins, path = summary["write_ins"], summary_path
        if not summary["has_wi"] and counties:                 # a Summary without a Write-Ins column: the county files' own
            write_ins = summed_wi
    else:
        cands, write_ins, path = summed, summed_wi, None
    read = {"summary": {"file": os.path.basename(summary_path), "sha256": sha(summary_path), "totals": {k[0]: v for k, v in cands.items()},
                        "write_ins": write_ins} if summary_path else None,
            "counties": {c: {"file": os.path.basename(have[c]), "sha256": sha(have[c]),
                             "totals": {k[0]: v["votes"] for k, v in b["cands"].items()}, "write_ins": b["write_ins"]}
                         for c, b in counties.items()}}
    return cands, write_ins, path, [have[c] for c in COUNTIES if c in have], read


def house_primary(folder, code, d, say):
    word = PARTIES[code][0]
    path = saved(folder, f"2026-sp-congressional-district-{d}-{word}", say)
    if not path:
        return None
    book = read_book(path, os.path.basename(path))
    check_heading(book, os.path.basename(path), word, rf"congress\w*\s+district\s*(no\.?\s*)?{d}\b")
    cands = {k: v["votes"] for k, v in book["cands"].items()}
    read = {"file": os.path.basename(path), "sha256": sha(path), "places": len(book["places"]),
            "totals": {k[0]: v for k, v in cands.items()}, "write_ins": book["write_ins"], "notes": book["notes"]}
    return cands, book["write_ins"], path, read


# ---------- the November list ----------

def read_general(path):
    """{race: [(name, party)]} from the General Election Candidates List, with the date it was printed."""
    with open(path, "rb") as fh:
        data = fh.read()
    if data[:4] != b"%PDF":
        raise SystemExit(f"New Hampshire: {os.path.basename(path)} is not a PDF")
    pdf = PDF(re.sub(rb"stream[ \t]+\r\n", b"stream\r\n", data))     # the report writer puts a space after "stream"
    out, seen_title, seen_election, printed = {}, False, False, ""
    office = district = vote_for = None
    for n, (page, res) in enumerate(pdf.pages(), 1):
        for _y, runs in pdf_rows(pdf, page, res):
            text = join(runs)
            if not text:
                continue
            if FURNITURE.search(text):
                seen_title |= "General Election Candidates List" in text
                if re.search(r"^Election\s*:", text) or "Election :" in text:
                    if not ELECTION_LINE.search(text):
                        raise SystemExit(f"New Hampshire: {os.path.basename(path)} is not the November 3, 2026 list ({text!r})")
                    seen_election = True
                m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4}) \d{1,2}:\d\d", text)
                if m and not printed:
                    printed = f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
                continue
            left = join([r for r in runs if r[0] < NAME_BAND])
            right = join([r for r in runs if NAME_BAND <= r[0] < PARTY_BAND])
            beyond = [r for r in runs if r[0] >= PARTY_BAND]
            if left == "Candidate Name" and right == "Party" and not beyond:
                continue
            federal = office in ("senate", "house")
            if beyond:
                if federal:
                    raise SystemExit(f"New Hampshire: a row of the federal sections on page {n} has text beyond the name and party columns")
                continue
            if not right:
                m = re.fullmatch(r"District No:?\s*(\d+)", left)
                if m:
                    district = int(m.group(1))
                    continue
                m = re.fullmatch(r"Vote for not more than\s*(\d+)", left)
                if m:
                    vote_for = int(m.group(1))
                    if federal and vote_for != 1:
                        raise SystemExit(f"New Hampshire: a federal race on the list elects {vote_for}")
                    continue
                if SENATE_HEAD.fullmatch(left):
                    office, district, vote_for = "senate", None, None
                elif HOUSE_HEAD.fullmatch(left):
                    office, district, vote_for = "house", None, None
                elif OTHER_HEADS.match(left):
                    office, district, vote_for = "other", None, None
                elif federal:
                    raise SystemExit(f"New Hampshire: a line in the {office} section on page {n} that is not read (length {len(left)})")
                else:
                    office = "other"
                continue
            if not federal:
                continue
            if office == "senate":
                race = SENATE
            elif district in HOUSE:
                race = HOUSE[district]
            else:
                raise SystemExit(f"New Hampshire: a Representative in Congress candidate on page {n} with no district ({district})")
            if vote_for != 1:
                raise SystemExit(f"New Hampshire: a federal candidate on page {n} before the race's \"Vote for not more than 1\"")
            if re.search(r"write", left + " " + right, re.I):
                raise SystemExit("New Hampshire: a federal row of the list mentions a write-in; read how it is printed")
            name = re.sub(r"\s+", " ", left).strip()
            if any(fold(name) == fold(x) for x, _p in out.get(race, [])):
                raise SystemExit(f"New Hampshire: a candidate is listed twice for {race}")
            out.setdefault(race, []).append((name, right.strip()))
    if not seen_title or not seen_election:
        raise SystemExit(f"New Hampshire: {os.path.basename(path)} is not headed as the General Election Candidates List for November 3, 2026")
    return out, printed


def same_person(a, b):
    ga, fa = name_parts(a)
    gb, fb = name_parts(b)
    return fa == fb and bool(ga) and bool(gb) and ga[0][0] == gb[0][0]


def shown(name, caps_note):
    name = re.sub(r"\s+", " ", name).strip()
    if name.isupper():
        return re.sub(r"(['\"(])([a-z])", lambda m: m.group(1) + m.group(2).upper(), proper(name)), caps_note
    return name, None


# ---------- the loader ----------

def load(con, cache, say=print):
    folder = os.path.join(cache, "nh")
    os.makedirs(folder, exist_ok=True)
    rows, gaps = [], []

    # the November list
    lists = sorted(f for f in os.listdir(folder) if GENERAL_FILE.search(f))
    general, printed, gpath = None, "", None
    for f in lists:                               # the latest printed copy wins
        got, when = read_general(os.path.join(folder, f))
        if general is None or when > printed:
            general, printed, gpath = got, when, os.path.join(folder, f)
    if lists and not general:
        raise SystemExit(f"New Hampshire: {', '.join(lists)} has no federal candidates; read how the list is laid out")
    nominee = {}
    if general:
        missing = [r for r in (SENATE, HOUSE[1], HOUSE[2]) if not general.get(r)]
        if missing:
            raise SystemExit(f"New Hampshire: the November list has no candidates for {', '.join(missing)}")
        for race, cands in general.items():
            for order, (printed_name, party) in enumerate(cands, 1):
                name, note = shown(printed_name, CAPS)
                rows.append((race, "general", "2026-11-03", name, party, party_code(party), order, 0, 0, None, None, None, None, None,
                             "nh-sos-2026-general-list", note))
                for code, (_w, label, _l) in PARTIES.items():
                    if party.lower() == label.lower():
                        nominee[(race, code)] = name
    else:
        gaps = [(r, GAP) for r in (SENATE, HOUSE[1], HOUSE[2])]

    # the primaries
    fields, single, read, missing, used = 0, [], {}, [], []
    for code, (word, label, letter) in PARTIES.items():
        got = {}
        s = senate_primary(folder, code, say)
        cfiles = []
        if s:
            cands, wi, path, cfiles, figures = s
            got[SENATE] = (cands, wi, path, figures)
            read[f"senate-{code}"] = figures
        else:
            missing.append(f"US Senator Summary ({label})")
        for d in (1, 2):
            h = house_primary(folder, code, d, say)
            if h:
                got[HOUSE[d]] = h
                read[f"house-{d}-{code}"] = h[3]
            else:
                missing.append(f"Representative in Congress District No. {d} ({label})")
        for race, (cands, wi, path, _figures) in got.items():
            field = [(name, v) for (name, l), v in cands.items() if l == letter]
            others = sum(v for (_name, l), v in cands.items() if l != letter)
            total = sum(v for _n, v in field) + others + wi
            if len(field) < 2:
                single.append(f"{race} {label}")
                continue
            fields += 1
            if path:
                used.append(("file", code, race, path, len(field)))
            if race == SENATE and cfiles:
                used.append(("counties", code, cfiles, bool(path)))
            top = max(v for _n, v in field)
            if sum(1 for _n, v in field if v == top) > 1:
                raise SystemExit(f"New Hampshire: the {race} {label} primary is tied at the top; read how it was settled")
            leader = next(n for n, v in field if v == top)
            won = nominee.get((race, code))
            source = f"nh-sos-2026-primary-{'senate' if race == SENATE else 'house-' + race[-1]}-{code.lower()}"
            if not path:
                source = f"nh-sos-2026-primary-senate-counties-{code.lower()}"
            for name, v in sorted(field, key=lambda nv: -nv[1]):
                shown_name, note = shown(name, CAPS_RESULTS)
                if name == leader and general and not (won and same_person(won, name)):
                    note = " ".join(x for x in ("Not on the November list.", note) if x)
                rows.append((race, f"primary-{code}", PRIMARY, shown_name, label, party_code(label), None, 0, 0, v,
                             round(100 * v / total, 1) if total else None, "advanced" if name == leader else "lost",
                             None, None, source, note))
    if read:
        with open(os.path.join(folder, "nh_2026_primary_read.json"), "w", encoding="utf-8") as fh:
            json.dump(read, fh, ensure_ascii=False, indent=1)

    general_rows = [r for r in rows if r[1] == "general"]
    with con:
        con.execute("DELETE FROM candidates WHERE race_id LIKE '2026-NH-%'")
        con.execute("DELETE FROM list_gaps WHERE state = 'NH'")
        con.executemany("INSERT OR REPLACE INTO candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        con.executemany("INSERT INTO list_gaps VALUES (?, 'NH', ?)", gaps)
        if general:
            record_source(con, "nh-sos-2026-general-list", path=gpath, level="federal", state="NH", kind="official candidate list",
                          agency="New Hampshire Secretary of State",
                          title="General Election Candidates List with Write-ins, 11/03/2026 State General Election: United States Senator "
                                "and Representative in Congress",
                          url=DETAILS, published=printed, rows=len(general_rows),
                          note=f"Saved by John from the 2026 Election Details page ({os.path.basename(gpath)}; the Secretary's site turns away "
                               "automated downloads). Two columns, Candidate Name and Party; only the federal sections read. The list gives no "
                               "ballot positions (one column per party, rotated between districts), so its own order is kept; it has no status "
                               "column, so a candidate who withdrew is simply not on it.")
        for kind, code, *rest in used:
            label = PARTIES[code][1]
            if kind == "file":
                race, path, n = rest
                office = "United States Senator, Summary (by county)" if race == SENATE else f"Representative in Congress District No. {race[-1]}"
                record_source(con, f"nh-sos-2026-primary-{'senate' if race == SENATE else 'house-' + race[-1]}-{code.lower()}", path=path,
                              level="federal", state="NH", kind="official results", agency="New Hampshire Secretary of State",
                              title=f"2026 {label} State Primary (September 8, 2026): {office}", url=FILES + os.path.basename(path).split(" (")[0],
                              rows=n,
                              note=f"Saved by John from {PAGES[code]} (the Secretary's site turns away automated downloads). The page says: "
                                   "\"Tallies accurately reflect the returns of votes reported by clerk but are subject to change if clerks "
                                   "submit amendments.\" Every column adds up to the Totals row. Percent is of the votes for candidates, "
                                   "write-ins included (named candidates of another party and the Write-Ins column); overvotes and undervotes "
                                   "are left out.")
            else:
                cfiles, with_summary = rest
                record_source(con, f"nh-sos-2026-primary-senate-counties-{code.lower()}",
                              path=os.path.join(folder, "nh_2026_primary_read.json"), level="federal", state="NH", kind="official results",
                              agency="New Hampshire Secretary of State",
                              title=f"2026 {label} State Primary (September 8, 2026): United States Senator, the ten county files (by town)",
                              url=PAGES[code], rows=len(cfiles),
                              note=("Control: every county's totals equal its row of the Summary. " if with_summary else
                                    "No Summary saved: the candidates' totals are the sums of the ten county files, each checked town by town. ")
                                   + "The figures read and each file's SHA-256 are kept in nh_2026_primary_read.json: "
                                   + f"{', '.join(os.path.basename(p) for p in cfiles)}.")
    if not general and not read:
        say(f"    New Hampshire: waiting for the Secretary of State's files ({say_files(folder)}); the Secretary's site turns "
            "away automated downloads, so they are saved by hand. The three races say their list is coming.")
        return 0
    say(f"    New Hampshire: 2 House districts and the Senate race, "
        + (f"{len(general_rows)} candidates on the November ballot (list printed {printed})" if general
           else "the November list not saved yet (3 races wait)")
        + f"; {fields} party primaries with a field, votes from the Secretary of State's primary results"
        + (f" ({len(missing)} of 6 result files not saved: {'; '.join(missing)})" if missing else ", every file saved")
        + (f"; one candidate only, not a field: {', '.join(single)}" if single else ""))
    return len(general_rows)
