"""
New York: the State Board of Elections' Certification for the November 3, 2026 General Election (the accessible PDF
of September 17, 2026, 136 pages), read with ballot/pdftext.py. Each office is a table: "Office", "District",
"Counties", then one row per party line with the party on the left and the candidate on the right, the candidate's
given names printed above the party's row and the family name below it. A line with no candidate is left blank.

New York lets several parties nominate the same person (fusion): a candidate is listed once, with every line they
hold, in the order the lines appear on the ballot, and ordered by their first line. The file sits behind a Cloudflare
check that sometimes refuses a plain request and then lets it through; the kit's patient download is all that is
used.

The June 23, 2026 primaries are the Board's workbook of the primary's results, "2026-june-primary-vote-results-08312026
.xlsx" (on its file host under /system/files/documents/2026/08/, for the 2026 Election Results page; the Board's
workbooks of this kind are its certified results: 2024's was "2024-june-primary-results-for-certification.xlsx"). One
sheet per contest the primary held (New York prints a party primary only when it is contested). Cell A1 is the title,
"Representative in Congress 1st Congressional District - Democratic - Primary Election 6/25/2024" (2024's words), then
a heading row "Candidate Name (Party)", one column per county or part of a county ("Part of Suffolk County Vote
Results"), "Total Votes by Party" and "Total Votes by Candidate"; then one row per candidate, "Nancy S. Goroff (DEM)",
and the rows Blank, Void, Scattering (write-ins) and "Total Votes by County". Only sheets whose title names
Representative in Congress are read; the title must carry the date 6/23/2026. Every row's county cells must add up to
its Total Votes by Party (an empty cell is none), every county column's rows must add up to its Total Votes by County,
and a candidate's two totals must agree; anything that does not add up is reported and named in the source's note.
A field is a party primary with two candidates or more on its ballot; shares are of the candidates' votes plus the
write-ins (Scattering), blank and void ballots left out. The one with the most votes advanced (New York nominates by
plurality; there are no runoffs), and is looked for on the November list on the party's own line: a winner who is not
there (a nominee who declined, and whose party filled the vacancy) keeps "advanced", with a note. The parties with
primaries are Democratic (DEM), Republican (REP), Conservative (CON) and Working Families (WOR), stored as
primary-DEM, primary-REP, primary-CON and primary-WOR; any other party in a title stops the loader. The workbook
carries names and votes only.

The layout read is that of the Board's 2024 workbook of the same kind (2024-june-primary-results-for-certification_0
.xlsx, the June 25, 2024 primary: seven congressional sheets), looked at in a copy kept by the Internet Archive because
the Board's own site answered this kit with a Cloudflare challenge (HTTP 403) on September 30, 2026; the 2026 workbook
itself was not seen before this loader was written, so a sheet laid out otherwise stops the loader and names the sheet.
The workbook is read from ballot_cache/ny/ when a copy is there (saved by the patient download, or by John in his own
browser under the Board's own file name). When none is there it is asked for once, and twice more, through the kit's
patient download; if the host refuses, the refusal is written to ballot_cache/ny/refused.json and the host is not asked
again for a day (delete that file to ask sooner). Until the workbook is there the November ballot is loaded alone.
"""

import datetime as dt
import json
import os
import re
from urllib.error import HTTPError

import openpyxl

from ballot.common import house_id, name_parts, party_code, record_source
from ballot.pdftext import PDF, join, rows
from states import net

URL = "https://elections.ny.gov/system/files/documents/2026/09/accessible-2026-general-ballot-certification-9.17.2026.pdf"
PAGE = "https://elections.ny.gov/ballot-certifications-elections"

PRIMARY_URL = "https://elections.ny.gov/system/files/documents/2026/08/2026-june-primary-vote-results-08312026.xlsx"
RESULTS_PAGE = "https://elections.ny.gov/certified-june-23-2026-primary-election-results"      # the Board's "Certified June 23rd Primary" page
PRIMARY = "2026-06-23"
PRINTED_DATE = "6/23/2026"
PARTIES = {"Democratic": "DEM", "Republican": "REP", "Conservative": "CON", "Working Families": "WOR"}
SAVED = re.compile(r"^2026-june-primary.*results.*\.xlsx$", re.I)        # the Board's own name, or a later copy of it
TITLE = re.compile(r"^Representative in Congress (?P<district>\d+)(?:st|nd|rd|th) Congressional District - "
                   r"(?P<party>[A-Za-z][A-Za-z .'-]*?) - Primary Election (?:- )?(?P<date>\d{1,2}/\d{1,2}/\d{4}|[A-Z][a-z]+ \d{1,2}, \d{4})$")
                   # 2024 and 2025 print "Primary Election 6/25/2024"; 2026 prints "Primary Election - June 23, 2026"
CANDIDATE = re.compile(r"^(?P<name>.+?)\s*\(?\s*(?P<code>[A-Z]{3})\s*\)$")        # "(DEM)"; 2025's workbook once printed "REP)"
COUNTY_HEAD = re.compile(r"^(?:Part of )?[A-Z][A-Za-z. ]* County ?Vote Results$")
OTHER_ROWS = ("Blank", "Void", "Scattering")
TOTAL_ROW = "Total Votes by County"
REFUSED = "refused.json"
ASK_AGAIN_DAYS = 1
NOT_ON_LIST = "Won the primary, but is not on the November ballot on this party's line."
NO_VOTES = "The Board's results workbook shows no votes in this primary; who advanced is taken from the November ballot."


# ---------- the June 23 primaries ----------

def _clean(cell):
    return re.sub(r"\s+", " ", str(cell)).strip() if cell is not None else ""


def _num(cell, where):
    """A vote count: an empty cell is none."""
    if cell is None or (isinstance(cell, str) and not cell.strip()):
        return 0
    if isinstance(cell, bool):
        raise SystemExit(f"New York: a vote cell in {where} is not a number ({cell!r})")
    if isinstance(cell, (int, float)) and float(cell).is_integer() and cell >= 0:
        return int(cell)
    if isinstance(cell, str) and re.fullmatch(r"\d{1,3}(?:,\d{3})*|\d+", cell.strip()):
        return int(cell.strip().replace(",", ""))
    raise SystemExit(f"New York: a vote cell in {where} is not a count ({cell!r})")


def results(path, printed=PRINTED_DATE):
    """Every congressional sheet of the Board's primary results workbook, checked:
    ({(district, party code): {"party", "sheet", "cands": [(name, code, votes)], "scattering", "blank", "void", "total",
    "counties"}}, [what does not add up], number of other sheets)."""
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    out, wrong, other = {}, [], 0
    for ws in wb.worksheets:
        grid = [list(r) for r in ws.iter_rows(values_only=True)]
        title = next((str(c) for r in grid[:3] for c in r if isinstance(c, str) and c.strip()), "")
        first = _clean(title.strip().split("\n")[0])
        if "Congress" not in first:
            other += 1
            continue
        where = f"the sheet {ws.title!r}"
        m = TITLE.match(first)
        if not m:
            raise SystemExit(f"New York: {where} of the primary results is titled {first!r}, which the loader cannot read")
        when = m.group("date")
        if "/" not in when:
            import datetime as _dt
            d = _dt.datetime.strptime(when, "%B %d, %Y")
            when = f"{d.month}/{d.day}/{d.year}"
        if when != printed:
            raise SystemExit(f"New York: {where} of the primary results is for the primary of {when}, not {printed}")
        party = m.group("party")
        if party not in PARTIES:
            raise SystemExit(f"New York: a {party} primary in {where}; its election code is not set (PARTIES)")
        key = (int(m.group("district")), PARTIES[party])
        if key in out:
            raise SystemExit(f"New York: two sheets of the primary results for district {key[0]}'s {party} primary")
        hi = next((i for i, r in enumerate(grid) if r and _clean(r[0]) == "Candidate Name (Party)"), None)
        if hi is None:
            raise SystemExit(f"New York: {where} of the primary results has no \"Candidate Name (Party)\" heading row")
        head = [_clean(c) for c in grid[hi]]
        counties = [k for k, h in enumerate(head) if COUNTY_HEAD.match(h)]
        if "Total Votes by Party" not in head or not counties:
            raise SystemExit(f"New York: the heading row of {where} is not laid out as the loader expects ({head})")
        by_party = head.index("Total Votes by Party")
        by_cand = head.index("Total Votes by Candidate") if "Total Votes by Candidate" in head else None
        unread = [h for k, h in enumerate(head) if k and h and k not in counties and k not in (by_party, by_cand)]
        if unread:
            raise SystemExit(f"New York: {where} of the primary results has columns the loader does not read: {unread}")
        cands, others, total = [], {}, None
        for r in grid[hi + 1:]:
            label = _clean(r[0]) if r else ""
            if not label:
                if any(_clean(c) for c in r):
                    raise SystemExit(f"New York: a row of {where} has figures but no label")
                continue
            if total is not None:
                raise SystemExit(f"New York: {where} has rows after its {TOTAL_ROW} row ({label!r})")
            vals = [_num(r[k] if k < len(r) else None, where) for k in counties]
            tot = _num(r[by_party] if by_party < len(r) else None, where)
            if sum(vals) != tot:
                wrong.append(f"district {key[0]} {party}, {label}: the counties add up to {sum(vals):,}, the total says {tot:,}")
            if label == TOTAL_ROW:
                total = (vals, tot)
            elif label in OTHER_ROWS:
                if label in others:
                    raise SystemExit(f"New York: {where} has two {label} rows")
                others[label] = (vals, tot)
            else:
                cm = CANDIDATE.match(label)
                if not cm:
                    raise SystemExit(f"New York: a row of {where} is neither a candidate \"Name (PTY)\" nor Blank, Void, Scattering: {label!r}")
                if by_cand is not None and by_cand < len(r) and r[by_cand] is not None and _num(r[by_cand], where) != tot:
                    wrong.append(f"district {key[0]} {party}, {label}: Total Votes by Candidate differs from Total Votes by Party")
                name = cm.group("name").strip()
                if any(c[0] == name for c in cands):
                    raise SystemExit(f"New York: {name} is listed twice in {where}")
                cands.append((name, cm.group("code"), tot, vals))
        if total is None or "Scattering" not in others:
            raise SystemExit(f"New York: {where} of the primary results has no Scattering row or no {TOTAL_ROW} row")
        every = [c[3] for c in cands] + [v for v, _t in others.values()]
        for j, k in enumerate(counties):
            s = sum(v[j] for v in every)
            if s != total[0][j]:
                wrong.append(f"district {key[0]} {party}, {head[k]}: the rows add up to {s:,}, {TOTAL_ROW} says {total[0][j]:,}")
        s = sum(c[2] for c in cands) + sum(t for _v, t in others.values())
        if s != total[1]:
            wrong.append(f"district {key[0]} {party}: the rows add up to {s:,}, {TOTAL_ROW} says {total[1]:,}")
        out[key] = {"party": party, "sheet": ws.title, "cands": [(n, c, t) for n, c, t, _v in cands],
                    "scattering": others["Scattering"][1], "blank": others.get("Blank", (0, 0))[1], "void": others.get("Void", (0, 0))[1],
                    "total": total[1], "counties": len(counties)}
    wb.close()
    return out, wrong, other


def same_person(a, b):
    """The same family name, and given names that fit (Nick, Nicholas J.)."""
    ga, fa = name_parts(re.sub(r'"[^"]*"', " ", a))
    gb, fb = name_parts(re.sub(r'"[^"]*"', " ", b))
    return bool(fa and fa.replace(" ", "") == fb.replace(" ", "") and ga and gb
                and (ga[0] == gb[0] or set(ga) & set(gb) or ga[0][0] == gb[0][0]))


def _stamp(name):
    """The date in a workbook's name, 08312026 -> 20260831, for choosing the latest copy."""
    m = re.search(r"(\d\d)(\d\d)(20\d\d)", name)
    return m.group(3) + m.group(1) + m.group(2) if m else ""


def _answer(e):
    if isinstance(e, HTTPError):
        return f"HTTP {e.code}" + (" (Cloudflare challenge)" if (e.headers or {}).get("cf-mitigated") == "challenge" else "")
    return f"{type(e).__name__}: {e}"


def primary_workbook(folder, say):
    """(path, "") for the Board's primary results workbook, or ("", why not)."""
    os.makedirs(folder, exist_ok=True)
    saved = [f for f in os.listdir(folder) if SAVED.match(f)]
    if saved:
        path = os.path.join(folder, max(saved, key=lambda f: (_stamp(f), os.path.getmtime(os.path.join(folder, f)))))
        if open(path, "rb").read(4) != b"PK\x03\x04":
            raise SystemExit(f"New York: {os.path.basename(path)} in {folder} is not an Excel workbook (save the file itself, not the page)")
        return path, ""
    marker = os.path.join(folder, REFUSED)
    if os.path.exists(marker):
        info = json.load(open(marker, encoding="utf-8"))
        asked = dt.datetime.fromisoformat(info["asked"])
        if dt.datetime.now() - asked < dt.timedelta(days=ASK_AGAIN_DAYS):
            return "", f"elections.ny.gov refused on {asked:%Y-%m-%d %H:%M} ({info['answer']}) and is not asked again for a day"
    path = os.path.join(folder, os.path.basename(PRIMARY_URL))
    answer = ""
    try:
        net.download(PRIMARY_URL, path, max_age_days=30, tries=3, say=say)
        if open(path, "rb").read(4) != b"PK\x03\x04":
            answer = "a page, not the workbook, came back"
            os.remove(path)
    except Exception as e:  # noqa: BLE001  any refusal: the November ballot is loaded alone
        answer = _answer(e)
    if os.path.exists(path + ".part"):
        os.remove(path + ".part")
    if answer:
        json.dump({"host": "elections.ny.gov", "asked": dt.datetime.now().isoformat(timespec="seconds"), "url": PRIMARY_URL,
                   "answer": answer}, open(marker, "w", encoding="utf-8"), indent=1)
        return "", f"elections.ny.gov answered {answer}"
    if os.path.exists(marker):
        os.remove(marker)
    return path, ""


def load(con, cache, say=print):
    path = os.path.join(cache, "ny_2026_general_ballot_certification.pdf")
    net.patient_lookups()
    net.download(URL, path, max_age_days=30)
    pdf = PDF(open(path, "rb").read())
    races, office, district, split = {}, None, None, None
    counties = False      # a long "Counties:" list wraps onto lines of its own, until "Vote For:"
    for page, res in pdf.pages():
        parties, names = [], []
        for y, rs in rows(pdf, page, res):      # the page's printed rows, top to bottom
            text = join(rs)
            if text.startswith("Counties:"):
                counties = True
            if text.startswith("Vote For:"):
                counties = False
                continue
            if counties:
                continue
            m = re.match(r"^Office:\s*(.+)$", text)
            if m:
                office, district = m.group(1).strip(), None
                continue
            m = re.match(r"^District:\s*(\d+)", text)
            if m:
                district = int(m.group(1))
                continue
            if "Candidate Name" in text:      # the name column starts at the first piece after the word "Party"
                ordered = sorted(rs, key=lambda r: r[0])
                split = next((ordered[k][0] - 4 for k in range(1, len(ordered)) if join(ordered[:k]).endswith("Party")), split)
                continue
            if re.match(r"^(Counties:|Vote For:|Certification for the)", text) or split is None:
                continue
            left, right = join([r for r in rs if r[0] < split]), join([r for r in rs if r[0] >= split])
            if left:
                parties.append((y, left, office, district))
            if right:
                names.append((y, right, office, district))
        for y, party, off, dist in parties:      # a party's row, and the name printed just above and just below it
            if off != "Representative in Congress" or not dist:
                continue
            mine = sorted((n for n in names if abs(n[0] - y) <= 10 and n[2] == off and n[3] == dist), key=lambda n: -n[0])
            races.setdefault(dist, []).append((party, re.sub(r"\s+", " ", " ".join(n[1] for n in mine)).strip()))
    out = []
    for dist, lines_ in sorted(races.items()):
        people, order = {}, []
        for party, name in lines_:
            if not name:
                continue
            if name not in people:
                people[name] = []
                order.append(name)
            people[name].append(party)
        for k, name in enumerate(order, start=1):
            lines_held = people[name]
            first_major = next((p for p in lines_held if party_code(p) in ("D", "R")), lines_held[0])
            out.append((house_id("NY", dist), "general", "2026-11-03", name, ", ".join(lines_held), party_code(first_major), k, 0, 0,
                         None, None, None, None, None, "ny-sboe-2026-general-cert",
                         ("On the ballot on " + str(len(lines_held)) + " party lines: " + ", ".join(lines_held) + ".") if len(lines_held) > 1 else None))

    # the June 23 primaries, from the Board's results workbook
    wpath, why = primary_workbook(os.path.join(cache, "ny"), say)
    prim, fields, single, upset, wrong, silent, other_sheets = [], {}, [], [], [], [], 0
    if wpath:
        contests, wrong, other_sheets = results(wpath)
        holder = {(house_id("NY", d), party): name for d, lines_ in races.items() for party, name in lines_ if name}
        for (dist, code), c in sorted(contests.items()):
            race, party = house_id("NY", dist), c["party"]
            if dist not in races:
                raise SystemExit(f"New York: the primary results have a {party} primary for district {dist}, which is not on the November list")
            if len(c["cands"]) < 2:
                single.append(f"{race} {code}")
                continue
            fields[code] = fields.get(code, 0) + 1
            base = sum(v for _n, _c, v in c["cands"]) + c["scattering"]
            nov = holder.get((race, party))
            picked = [k for k, (n, _c, _v) in enumerate(c["cands"]) if nov and same_person(n, nov)]
            if len(picked) > 1:
                raise SystemExit(f"New York: {nov}, on the November list, fits more than one name in the {race} {party} primary")
            if base:
                ranked = sorted(range(len(c["cands"])), key=lambda k: -c["cands"][k][2])
                if c["cands"][ranked[0]][2] == c["cands"][ranked[1]][2]:
                    raise SystemExit(f"New York: the {race} {party} primary is a tie in the results workbook; read who the Board certified")
                winner = ranked[0]
                if winner not in picked:
                    upset.append(f"{race} {code}")
            else:
                winner = picked[0] if picked else None
                silent.append(f"{race} {code}")
            for k, (name, _pc, votes) in enumerate(c["cands"]):
                notes = []
                if not base:
                    notes.append(NO_VOTES)
                elif k == winner and winner not in picked:
                    notes.append(NOT_ON_LIST)
                prim.append((race, f"primary-{code}", PRIMARY, name, party, party_code(party), None, 0, 0,
                             votes if base else None, round(100 * votes / base, 1) if base else None,
                             None if winner is None else "advanced" if k == winner else "lost",
                             None, None, "ny-sboe-2026-primary-results", " ".join(notes) or None))
    with con:
        con.execute("DELETE FROM candidates WHERE race_id LIKE '2026-NY-%'")
        con.executemany("INSERT OR REPLACE INTO candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", out)
        record_source(con, "ny-sboe-2026-general-cert", path=path, level="federal", state="NY", kind="official candidate list",
                      agency="New York State Board of Elections", title="Certification for the November 3, 2026 General Election (September 17, 2026)",
                      url=URL, published="2026-09-17", rows=len(out), note=f"Listed on {PAGE}. Several parties may nominate one candidate (fusion).")
        if wpath:
            con.executemany("INSERT OR REPLACE INTO candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", prim)
            record_source(con, "ny-sboe-2026-primary-results", path=wpath, level="federal", state="NY", kind="official results",
                          agency="New York State Board of Elections",
                          title="June 23, 2026 Primary Election: vote results (" + os.path.basename(wpath) + ")",
                          url=PRIMARY_URL, published="2026-08-31", rows=len(prim),
                          note=f"Linked from {RESULTS_PAGE}; carried out of the Browser pane, since elections.ny.gov answers scripts with a Cloudflare challenge. One sheet per contested primary; the {sum(fields.values()) + len(single)} congressional sheets "
                               f"are read ({other_sheets} other sheets left alone). Shares are of the candidates' votes plus write-ins (Scattering); "
                               f"blank and void ballots are left out. The most votes wins a New York primary (no runoffs). "
                               + ("Every sheet's counties and rows add up to its totals." if not wrong else "Did not add up: " + "; ".join(wrong) + ".")
                               + (f" Winner not on the November ballot on the party's line: {', '.join(upset)}." if upset else "")
                               + (f" Sheets with one candidate (no field): {', '.join(single)}." if single else "")
                               + (f" Sheets with no votes: {', '.join(silent)}." if silent else ""))
    if wrong:
        say("    New York: primary figures that do not add up: " + "; ".join(wrong))
    if wpath:
        told = (f"; June 23 primaries: {sum(fields.values())} party primaries with a field ("
                + ", ".join(f"{n} {code}" for code, n in sorted(fields.items())) + "), votes from the Board's results workbook"
                + (f"; winner not on the November ballot on the party's line in {', '.join(upset)}" if upset else "")
                + (f"; no votes shown in {', '.join(silent)}" if silent else ""))
    else:
        told = (f"; the June 23 primaries wait for the Board's results workbook ({why}): save {os.path.basename(PRIMARY_URL)} "
                f"from {RESULTS_PAGE} into {os.path.join(cache, 'ny')}")
    say(f"    New York: {len(races)} House districts, {len(out)} candidates on the November ballot "
        f"({sum(1 for r in out if r[15])} on more than one party line)" + told)
    return len(out)
