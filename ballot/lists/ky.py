"""
Kentucky: two files from the state's own election offices.

The November ballot is the Secretary of State's "Candidate Filings with the Office of the Secretary of State" for the
2026 General Election (web.sos.ky.gov/CandidateFilings/, linked as "View Candidate Filings" from sos.ky.gov; the page
for each office is Default.aspx?id=3, US Senator, and id=4, US Representative). Each page is one table per group, headed
"US Representative (21)", and a last group headed "Withdrawn / Deceased / Disqualified (1)". The columns are Name /
Running Mate, POBox Address / Email, Office, District/Division, Party and Date Filed; columns are taken by their
headings, only Name (the first line of the cell: a running mate would be on the second), Office, District/Division and
Party. The address and e-mail column is never read, and the cached copy keeps only the columns taken. A group's count
in its heading must match its rows. A candidate in the withdrawn group is left off and counted. The list gives no
ballot order and lists candidates by the date they filed, so the order kept is the list's own, write-ins left out of
it. Names are printed in ordinary capitals and kept as printed; parties are printed in full ("Republican Party",
"Democratic Party", "Libertarian Party", "Kentucky Party", "Independent") and kept as printed. A candidate whose party
is printed "Write-In" is a declared write-in candidate: the name is not printed on the ballot (write_in 1, no position).

The May 19, 2026 primary is the State Board of Elections' "2026 Primary Results - Official Certification" (a PDF
headed "Official 2026 Primary Election Results", from elect.ky.gov/results/2020-2029/Pages/2026.aspx), read with
ballot/pdftext.py's parts. Kentucky prints a primary on the ballot only when it is contested, and the certification
has one section per contested office, district and party: the candidates across the top, each column's name and
numbers right-aligned to the same edge, then one row per county and a "Total Votes" row. Names are printed given names
first, family names in capitals on the line below; where a field is wide (the Republican Senate primary) the names are
turned a quarter turn and printed upward in narrow columns, so the reader here keeps each piece of text's direction
(pdftext.page_runs keeps only where it starts). The county rows must add up to the Total Votes row for every candidate,
and the Senate sections must list all 120 counties. The certification prints no write-in line, so a field's total is
the sum of its candidates' votes. The one on the November list for that party advanced (the most votes wins a Kentucky
primary; there are no runoffs), and must be the field's top vote-getter. Family names printed in capitals are shown in
ordinary capitals, and the rows say so. Both hosts answer scripts.
"""

import html as H
import json
import math
import os
import re
import time

from ballot import pdftext as P
from ballot.common import house_id, name_parts, party_code, record_source, senate_id
from ballot.lists.tx import proper
from states import net

FILINGS = "https://web.sos.ky.gov/CandidateFilings/Default.aspx?id="
OFFICE_PAGES = {"3": "US Senator", "4": "US Representative"}
RESULTS_PAGE = "https://elect.ky.gov/results/2020-2029/Pages/2026.aspx"
CERT_URL = "https://elect.ky.gov/Documents/2026%20Primary%20Certification%20of%20Vote%20Totals%20Final.pdf"
PRIMARY = "2026-05-19"
KEEP = ("Name", "Office", "District/Division", "Party")
CODE = {"Republican Party": "REP", "Democratic Party": "DEM"}
FEDERAL = {"United States Senator", "United States Representative in Congress", "US Representative"}
DISTRICT = re.compile(r"^(\d+)(?:st|nd|rd|th) Congressional District$")
PARTY_ROW = re.compile(r"^[A-Z][A-Za-z]*(?: [A-Z][A-Za-z]*)* Party$")
NUMBER = re.compile(r"^\d{1,3}(?:,\d{3})*$")
PAGE_HEAD = re.compile(r"^Commonwealth of Kentucky Michael G\. Adams, Secretary of State 2026 Primary Election Results$")
COUNTIES = 120
WRITE_IN = "Write-in candidate: the name is not printed on the ballot."
CAPS = "Kentucky's official results print family names in capitals; they are shown here in ordinary capitals."
NOT_ON_LIST = "Won the primary, but is not on the November list for this party."


# ---------- the November list ----------

def text_of(cell):
    return re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", cell)).replace("\xa0", " ")).strip()


def filings(page, office):
    """{"groups": [(heading, count, withdrawn)], "rows": [{Name, Office, District/Division, Party, withdrawn}]} for one office's page."""
    title = re.search(r"<title[^>]*>(.*?)</title>", page, re.S)
    if not title or text_of(title.group(1)) != "Election: 2026 General Election" or f"Candidates for {office}" not in page:
        raise SystemExit(f"Kentucky: the Candidate Filings page for {office} is no longer the 2026 General Election's")
    page = re.sub(r"<script.*?</script>|<style.*?</style>", "", page, flags=re.S)
    wdd = page.find('id="ctl00_MainContent_pnlOfficeWddResults"')      # the withdrawn, deceased and disqualified groups follow this
    summaries = list(re.finditer(r"<summary[^>]*>(.*?)</summary>", page, re.S))
    groups, out = [], []
    for i, g in enumerate(summaries):
        head = text_of(g.group(1))
        body = page[g.end():summaries[i + 1].start() if i + 1 < len(summaries) else len(page)]
        m = re.fullmatch(r"(.+?) \((\d+)\)", head)
        if not m:
            raise SystemExit(f"Kentucky: a group heading on the {office} page is not \"Name (count)\": {head!r}")
        withdrawn = wdd != -1 and g.start() > wdd
        if m.group(1).startswith("Withdrawn") and not withdrawn:
            raise SystemExit(f"Kentucky: the group {head!r} on the {office} page is not in the withdrawn part of the page")
        taken = 0
        for tab in re.findall(r"<table[^>]*>(.*?)</table>", body, re.S):
            trs = re.findall(r"<tr[^>]*>(.*?)</tr>", tab, re.S)
            heads = [text_of(re.split(r"<br\s*/?>", c)[0]).rstrip(" /") for c in re.findall(r"<td[^>]*>(.*?)</td>", trs[0], re.S)] if trs else []
            if not all(k in heads for k in KEEP):
                raise SystemExit(f"Kentucky: a table under {head!r} lacks one of the columns {KEEP} ({heads})")
            idx = {k: heads.index(k) for k in KEEP}
            for tr in trs[1:]:
                cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
                if len(cells) != len(heads):
                    raise SystemExit(f"Kentucky: a row under {head!r} does not line up with its headings")
                row = {k: text_of(cells[idx[k]]) for k in KEEP if k != "Name"}
                row["Name"] = text_of(re.split(r"<br\s*/?>", cells[idx["Name"]])[0])      # the first line; a running mate is on the second
                row["withdrawn"] = withdrawn
                taken += 1
                if row["Office"] == office:
                    out.append(row)
                elif not withdrawn:
                    raise SystemExit(f"Kentucky: a row for {row['Office']!r} on the {office} page")
        nested = taken == 0 and m.group(1).startswith("Withdrawn")       # its rows are in groups of their own below it
        if taken != int(m.group(2)) and not nested:
            raise SystemExit(f"Kentucky: the group {head!r} on the {office} page has {taken} rows")
        groups.append((m.group(1), int(m.group(2)), withdrawn))
    if not any(not w for _g, _c, w in groups):
        raise SystemExit(f"Kentucky: no candidates read on the {office} page")
    return {"groups": groups, "rows": out}


def race_of(row):
    office, district = row["Office"], row["District/Division"]
    if office == "US Senator":
        return senate_id("KY", 2)
    m = re.fullmatch(r"(\d+)(?:st|nd|rd|th)", district)
    if office == "US Representative" and m:
        return house_id("KY", int(m.group(1)))
    raise SystemExit(f"Kentucky: a filing for {office!r}, district {district!r}, is not read")


def kept(path, fetch, max_age_days=2):
    """A small JSON of the kept columns, refreshed from the pages when it is older than max_age_days."""
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < max_age_days * 86400:
        return json.load(open(path, encoding="utf-8"))
    data = fetch()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(data, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return data


def fetch_filings():
    out = {}
    for pid, office in OFFICE_PAGES.items():
        raw = net.get(FILINGS + pid, accept="text/html")
        out[office] = filings(raw.decode("utf-8", "replace"), office)
        time.sleep(1.5)
    return out


# ---------- the primary certification ----------

def page_runs(pdf, page, res):
    """Every text run on a page as (x, y, x_end, y_end, height, text): pdftext.page_runs, keeping the direction the
    text runs in, so that names printed upward can be read."""
    fonts, runs = {}, []
    fres = pdf.get((pdf.get(res) or {}).get("Font")) or {}
    contents = pdf.get(page.get("Contents"))
    parts = contents if isinstance(contents, list) else [page.get("Contents")]
    data = b"\n".join(pdf.stream(p) or b"" for p in parts if isinstance(p, P.Ref))
    ctm, saved = [1, 0, 0, 1, 0, 0], []
    st = {"tm": [1, 0, 0, 1, 0, 0], "tlm": [1, 0, 0, 1, 0, 0], "font": None, "size": 1.0, "tc": 0.0, "tw": 0.0, "th": 1.0,
          "tl": 0.0, "rise": 0.0}

    def show(s):
        font, size, th = st["font"], st["size"], st["th"]
        if font is None:
            return
        text, codes = font.decode(s if isinstance(s, (bytes, bytearray)) else b"")
        trm = P._mul([size * th, 0, 0, size, 0, st["rise"]], P._mul(st["tm"], ctm))
        adv = 0.0
        for code in codes:
            adv += (font.width(code) * size + st["tc"] + (st["tw"] if (not font.two and code == 32) else 0)) * th
        st["tm"] = P._mul([1, 0, 0, 1, adv, 0], st["tm"])
        end = P._mul([size * th, 0, 0, size, 0, st["rise"]], P._mul(st["tm"], ctm))
        if text.strip():
            runs.append((trm[4], trm[5], end[4], end[5], math.hypot(trm[2], trm[3]) or size, text))

    for op, a in P._ops(data):
        if op == "q":
            saved.append(ctm[:])
        elif op == "Q":
            ctm = saved.pop() if saved else [1, 0, 0, 1, 0, 0]
        elif op == "cm" and len(a) == 6:
            ctm = P._mul([float(x) for x in a], ctm)
        elif op == "BT":
            st["tm"] = st["tlm"] = [1, 0, 0, 1, 0, 0]
        elif op == "Tf" and len(a) == 2:
            name = str(a[0])
            if name not in fonts:
                fonts[name] = P.Font(pdf, fres.get(name))
            st["font"], st["size"] = fonts[name], float(a[1])
        elif op in ("Tc", "Tw", "TL", "Ts") and a:
            st[{"Tc": "tc", "Tw": "tw", "TL": "tl", "Ts": "rise"}[op]] = float(a[0])
        elif op == "Tz" and a:
            st["th"] = float(a[0]) / 100
        elif op in ("Td", "TD") and len(a) == 2:
            tx, ty = float(a[0]), float(a[1])
            if op == "TD":
                st["tl"] = -ty
            st["tm"] = st["tlm"] = P._mul([1, 0, 0, 1, tx, ty], st["tlm"])
        elif op == "Tm" and len(a) == 6:
            st["tm"] = st["tlm"] = [float(x) for x in a]
        elif op == "T*":
            st["tm"] = st["tlm"] = P._mul([1, 0, 0, 1, 0, -st["tl"]], st["tlm"])
        elif op == "Tj" and a:
            show(a[-1])
        elif op in ("'", '"') and a:
            st["tm"] = st["tlm"] = P._mul([1, 0, 0, 1, 0, -st["tl"]], st["tlm"])
            if op == '"' and len(a) == 3:
                st["tw"], st["tc"] = float(a[0]), float(a[1])
            show(a[-1])
        elif op == "TJ" and a and isinstance(a[-1], list):
            for item in a[-1]:
                if isinstance(item, (bytes, bytearray)):
                    show(item)
                elif isinstance(item, (int, float)):
                    st["tm"] = P._mul([1, 0, 0, 1, -float(item) / 1000.0 * st["size"] * st["th"], 0], st["tm"])
    return runs


def flat_rows(runs):
    """Runs printed left to right, grouped into rows top to bottom: [(y, [(x, y, height, text, x_end)])]."""
    out = []
    for x0, y0, x1, _y1, h, t in sorted(runs, key=lambda r: (-round(r[1], 1), r[0])):
        r = (x0, y0, h, t, x1)
        if out and abs(out[-1][0] - y0) <= max(1.5, 0.35 * h):
            out[-1][1].append(r)
        else:
            out.append([y0, [r]])
    return [(y, sorted(rs, key=lambda r: r[0])) for y, rs in out]


def tokens(rs):
    """A row's pieces joined where they touch: [(x, x_end, text)]."""
    out = []
    for x0, _y, _h, t, x1 in rs:
        if out and x0 - out[-1][1] <= 1.0:
            out[-1] = (out[-1][0], max(out[-1][1], x1), out[-1][2] + t)
        else:
            out.append((x0, x1, t))
    return [(a, b, re.sub(r"\s+", " ", t).strip()) for a, b, t in out]


def upward_lines(runs):
    """Text printed upward, one line per column position: [(x, top, bottom, text)]."""
    cols = {}
    for x0, y0, x1, y1, h, t in runs:
        cols.setdefault(round(x0 * 2) / 2, []).append((-y0, 0, h, t, -y1))
    return [(x, -min(r[0] for r in rs), -max(r[4] for r in rs), P.join(rs)) for x, rs in sorted(cols.items())]


def by_edge(rs, edges, where):
    """A row's pieces split into columns by the right edge each column's text is aligned to: {column: text}."""
    out, pending = {}, []
    for r in rs:
        pending.append(r)
        hit = [k for k, e in enumerate(edges) if abs(r[4] - e) <= 1.5]
        if hit:
            out[hit[0]] = P.join(pending)
            pending = []
    if pending:
        raise SystemExit(f"Kentucky: text in a name row of {where} does not end at a column's edge ({P.join(pending)!r})")
    return out


def shown(printed):
    """Andy BARR -> Andy Barr; Amy McGRATH -> Amy McGrath; Joshua BLANTON SR. -> Joshua Blanton Sr. (given names as printed)"""
    out, caps = [], False
    for w in printed.split():
        if re.search(r"[A-Z]{2}", w.replace('"', "")) and not re.fullmatch(r"[IVX]+", w):
            caps = True
            m = re.fullmatch(r"([A-Z][a-z]+)([A-Z]{2}.*)", w)
            w = m.group(1) + proper(m.group(2)) if m else proper(w)
        out.append(w)
    return " ".join(out), caps


def certification(path):
    """[{office, district, party, names, total, counties}] for every federal section of the certification, in its order."""
    pdf = P.PDF(open(path, "rb").read())
    out, cur, section = [], None, None
    for n, (page, res) in enumerate(pdf.pages(), start=1):
        runs = page_runs(pdf, page, res)
        flat = [r for r in runs if abs(r[3] - r[1]) < 0.01]
        up = [r for r in runs if abs(r[3] - r[1]) >= 0.01]
        rows = flat_rows(flat)
        texts = [P.join(rs) for _y, rs in rows]
        if "For the office of" in texts:                      # a section's cover page
            section = texts[texts.index("For the office of") + 1]
            if not any("Official 2026 Primary Election Results" == t for t in texts):
                raise SystemExit("Kentucky: the certification's cover page is not the Official 2026 Primary Election Results'")
            continue
        if section not in FEDERAL:
            continue
        pending, head = [], None
        for (y, rs), text in zip(rows, texts):
            if PAGE_HEAD.match(text):
                continue
            toks = tokens(rs)
            nums = [t for t in toks if NUMBER.match(t[2])]
            if text.startswith("Total Votes"):
                if cur is None or len(nums) != len(cur["edges"]):
                    raise SystemExit(f"Kentucky: a Total Votes row on page {n} of the certification does not fit its section")
                cur["total"] = [int(t[2].replace(",", "")) for t in nums]
                out.append(cur)
                cur, pending = None, []
                continue
            if nums and not NUMBER.match(toks[0][2]) and all(NUMBER.match(t[2]) for t in toks[1:]):     # a county row
                if head is not None:
                    edges = [t[1] for t in nums]
                    where = f"{head['office']} {head['district'] or ''} {head['party']}".replace("  ", " ")
                    cols = {}
                    for rs2 in head["names"]:
                        for k, t in by_edge(rs2, edges, where).items():
                            cols.setdefault(k, []).append(t)
                    for x, top, bottom, t in upward_lines(up):
                        if bottom > y and top < head["y"]:
                            k = [k for k, e in enumerate(edges) if 0 < e - x < 50]
                            if len(k) != 1:
                                raise SystemExit(f"Kentucky: a name printed upward in {where} is under no column")
                            cols.setdefault(k[0], []).append((x, t))
                    names = []
                    for k in range(len(edges)):
                        got = cols.get(k, [])
                        if got and isinstance(got[0], tuple):
                            got = [t for _x, t in sorted(got, reverse=True)]      # upward: the first line is the rightmost
                        if not got:
                            raise SystemExit(f"Kentucky: column {k + 1} of {where} has no name")
                        names.append(" ".join(got))
                    cur = {"office": head["office"], "district": head["district"], "party": head["party"], "names": names,
                           "edges": edges, "counties": {}, "page": n}
                    head = None
                if cur is None:
                    raise SystemExit(f"Kentucky: a county row on page {n} of the certification comes before any section heading")
                county = toks[0][2]
                vals = {}
                for t in nums:
                    k = [k for k, e in enumerate(cur["edges"]) if abs(t[1] - e) <= 1.5]
                    if len(k) != 1:
                        raise SystemExit(f"Kentucky: a number in {county}'s row on page {n} is under no column")
                    vals[k[0]] = int(t[2].replace(",", ""))
                if len(vals) != len(cur["edges"]) or county in cur["counties"]:
                    raise SystemExit(f"Kentucky: {county}'s row on page {n} of the certification does not fit its section")
                cur["counties"][county] = [vals[k] for k in range(len(cur["edges"]))]
                continue
            if PARTY_ROW.match(text):
                if cur is not None:
                    raise SystemExit(f"Kentucky: a new section starts on page {n} of the certification before the last one's Total Votes row")
                if not pending:
                    raise SystemExit(f"Kentucky: a party heading on page {n} of the certification has no office above it")
                district = [DISTRICT.match(t) for t in pending[1:]]
                district = [int(m.group(1)) for m in district if m]
                head = {"office": pending[0], "district": district[0] if district else None, "party": text, "y": y, "names": []}
                pending = []
                continue
            if head is not None:
                head["names"].append(rs)
            elif cur is None:
                pending.append(text)
            # else: the names printed again at the top of a section's next page
    if cur is not None or head is not None:
        raise SystemExit("Kentucky: the certification's last federal section has no Total Votes row")
    return out


def created(path):
    """The PDF's own creation date (D:20260601...) as 2026-06-01, or ''."""
    raw = open(path, "rb").read()
    m = re.search(rb"/CreationDate\s*(?:\(D:(\d{8})|<((?:[0-9A-Fa-f]{2}){10,}))", raw)
    if not m:
        return ""
    s = m.group(1).decode() if m.group(1) else bytes.fromhex(m.group(2).decode()).decode("latin-1")[2:10]
    return f"{s[:4]}-{s[4:6]}-{s[6:8]}" if re.fullmatch(r"\d{8}", s) else ""


def same_person(a, b):
    ga, fa = name_parts(re.sub(r'"[^"]*"', " ", a))
    gb, fb = name_parts(re.sub(r'"[^"]*"', " ", b))
    return bool(fa == fb and ga and gb and (ga[0] == gb[0] or set(ga) & set(gb) or ga[0][0] == gb[0][0]))


def load(con, cache, say=print):
    net.patient_lookups()
    folder = os.path.join(cache, "ky")
    os.makedirs(folder, exist_ok=True)
    lpath = os.path.join(folder, "ky_2026_general_candidate_filings_federal.json")
    listed = kept(lpath, fetch_filings)
    rows, order, gone, write_ins, nominee = [], {}, [], [], {}
    for office in OFFICE_PAGES.values():
        for r in listed[office]["rows"]:
            race = race_of(r)
            if r["withdrawn"]:
                gone.append((race, r["Name"]))
                continue
            party = r["Party"]
            if party == "Write-In":
                write_ins.append((race, r["Name"]))
                rows.append((race, "general", "2026-11-03", r["Name"], party, party_code(party), None, 0, 1, None, None, None, None, None,
                             "ky-sos-2026-general-filings", WRITE_IN))
                continue
            order[race] = order.get(race, 0) + 1
            if party in CODE:
                if (race, party) in nominee:
                    raise SystemExit(f"Kentucky: two {party} candidates for {race} on the November list")
                nominee[(race, party)] = r["Name"]
            rows.append((race, "general", "2026-11-03", r["Name"], party, party_code(party), order[race], 0, 0, None, None, None, None, None,
                         "ky-sos-2026-general-filings", None))
    expected = {senate_id("KY", 2)} | {house_id("KY", d) for d in range(1, 7)}
    if {r[0] for r in rows} != expected:
        raise SystemExit(f"Kentucky: the November list covers {sorted({r[0] for r in rows})}; {sorted(expected)} were expected")

    cpath = os.path.join(folder, "ky_2026_primary_certification_of_vote_totals.pdf")
    net.download(CERT_URL, cpath, max_age_days=30)
    if not open(cpath, "rb").read(5).startswith(b"%PDF"):
        raise SystemExit("Kentucky: the primary certification downloaded is not a PDF; read the results page again")
    sections, unreconciled, upset, fields = certification(cpath), [], [], 0
    for s in sections:
        if s["office"] == "United States Senator":
            race = senate_id("KY", 2)
            if len(s["counties"]) != COUNTIES:
                unreconciled.append(f"{race} {s['party']}: {len(s['counties'])} counties listed, not {COUNTIES}")
        elif s["district"]:
            race = house_id("KY", s["district"])
        else:
            raise SystemExit(f"Kentucky: a certification section for {s['office']} names no congressional district")
        if s["party"] not in CODE:
            raise SystemExit(f"Kentucky: a {s['party']} primary for {race} in the certification; its election code is not set")
        summed = [sum(c[k] for c in s["counties"].values()) for k in range(len(s["names"]))]
        if summed != s["total"]:
            unreconciled.append(f"{race} {s['party']}: county rows add to {summed}, Total Votes row says {s['total']}")
        if len(s["names"]) < 2:
            continue
        fields += 1
        total = sum(s["total"])
        won = nominee.get((race, s["party"]))
        top = max(range(len(s["names"])), key=lambda k: s["total"][k])
        picked = [k for k, nm in enumerate(s["names"]) if won and same_person(nm, won)]
        if len(picked) > 1:
            raise SystemExit(f"Kentucky: {won} on the November list fits more than one name in the {race} {s['party']} primary")
        winner = picked[0] if picked else top
        if winner != top:
            upset.append(f"{race} {s['party']}")
        for k, printed in enumerate(s["names"]):
            name, caps = shown(printed)
            notes = [CAPS] if caps else []
            if k == winner and not picked:
                notes.append(NOT_ON_LIST)
            rows.append((race, f"primary-{CODE[s['party']]}", PRIMARY, name, s["party"], party_code(s["party"]), None, 0, 0, s["total"][k],
                         round(100 * s["total"][k] / total, 1) if total else None, "advanced" if k == winner else "lost",
                         None, None, "ky-sbe-2026-primary-certification", " ".join(notes) or None))
    with con:
        con.execute("DELETE FROM candidates WHERE race_id LIKE '2026-KY-%'")
        con.executemany("INSERT OR REPLACE INTO candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        record_source(con, "ky-sos-2026-general-filings", path=lpath, level="federal", state="KY", kind="official candidate list",
                      agency="Kentucky Secretary of State",
                      title="Candidate Filings with the Office of the Secretary of State, 2026 General Election: US Senator and US Representative",
                      url=FILINGS + "4", rows=sum(len(v["rows"]) for v in listed.values()),
                      note=f"Read from the pages for US Senator ({FILINGS}3) and US Representative ({FILINGS}4): name, office, district and "
                           f"party only; the address and e-mail column is never read. The list gives no ballot order (it goes by date filed); "
                           f"its own order is kept. Withdrawn, deceased or disqualified, left off: {len(gone)}. "
                           f"Declared write-in candidates (party printed \"Write-In\"): {len(write_ins)}.")
        record_source(con, "ky-sbe-2026-primary-certification", path=cpath, level="federal", state="KY", kind="official results",
                      agency="Kentucky State Board of Elections",
                      title="Official 2026 Primary Election Results, May 19, 2026 (\"2026 Primary Results - Official Certification\", "
                            "Certification of Vote Totals)",
                      url=CERT_URL, published=created(cpath), rows=sum(len(s["names"]) for s in sections),
                      note=f"Linked from {RESULTS_PAGE}. One section per contested congressional party primary (an uncontested primary is not "
                           f"on the ballot); statewide Total Votes stored, checked against the county rows. The certification has no write-in "
                           f"line, so shares are of the candidates' votes. The date given is the file's own creation date. "
                           + ("Every section's county rows add up to its Total Votes row." if not unreconciled
                              else "Did not add up: " + "; ".join(unreconciled) + ".")
                           + (f" November nominee not the primary's top vote-getter: {', '.join(upset)}." if upset else ""))
    if unreconciled:
        say("    Kentucky: primary sections that do not add up: " + "; ".join(unreconciled))
    if upset:
        say("    Kentucky: the November nominee is not the primary's top vote-getter in " + ", ".join(upset) + "; read the files again")
    n = sum(1 for r in rows if r[1] == "general")
    say(f"    Kentucky: 6 House districts and the Senate race, {n} candidates on the November ballot ({len(write_ins)} declared write-ins, "
        f"{len(gone)} withdrawn left off); {fields} party primaries with a field, votes from the official certification")
    return n
