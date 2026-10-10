"""election/readers/wy_pdf.py - Wyoming, from the Secretary of State's summary PDFs (ARCHITECTURE.md 5.3, section 7: care).

Where the figures are
  The Secretary's results page for an election (sos.wyo.gov/Elections/Docs/<year>/<year>GeneralResults.aspx; the 2026
  page is not linked yet) links summary PDFs that are "updated through election night as a county reports 100 percent
  and the Secretary verifies it" (the 2024 page's words): counties arrive whole, never precinct by precinct.
    <year>_General_Statewide_Candidates_Summary.pdf          Congress and the statewide offices
    <year>_General_Statewide_Senate_Candidates_Summary.pdf   State Senate districts
    <year>_General_Statewide_House_Candidates_Summary.pdf    State House districts
    <year>_General_Statewide_Judicial_Summary.pdf            judges' retention votes
  (the primary's are <year>_Statewide_..._Summary.pdf). Each table: the office, for a primary a band of party names,
  the candidates' names over their columns (a general's carry "(R)", "(D)" ...), then Write-Ins, Overvotes and
  Undervotes, a row per county ("-" where the county is outside the district) and a Total row. A table too wide for one
  page goes on over the next ("<office>, Continued").

How it is read: with the kit's PDF reader (ballot/pdftext.py), keeping each piece of text's position. Columns are found
from the right edges of the county rows' figures, and each heading word is put over the column whose right edge is the
first one past the word's middle. Only the office, party, candidate headings, county names and figures are read.

Checks made here: each column's county figures add up to its Total row (a problem holds the snapshot); every heading
fits a column; the counties are Wyoming's 23. A county with no figures in a table has not reported.

The night's requests: the results page once a cycle (is the election posted?), then each summary it links, asked with
If-Modified-Since so an unchanged file is not sent again. check() keeps what it fetched for fetch(), so nothing is
asked twice.

    python -m election.readers.wy_pdf --crosswalk     (re)build election/crosswalk/wy.json from the ballot databases
    python -m election.readers.wy_pdf --selftest      no network: the fixture (two pages of the 2026 primary)
    python -m election.readers.wy_pdf --replay        the 2026 primary and 2024 general summaries
"""

import collections
import datetime as dt
import hashlib
import json
import os
import re
import sqlite3
import sys
import unicodedata

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

STATE = "WY"
FIPS = "56"
FEED = "wy-pdf"
FAMILY = "wy_pdf"
SITE = "https://sos.wyo.gov"
PAGE = SITE + "/Elections/Docs/{year}/{id}.aspx"
CROSSWALK = os.path.join(HERE, "election", "crosswalk", "wy.json")
FIXTURE = os.path.join(HERE, "election", "fixtures", "wy")
REPLAY = os.path.join(HERE, "election_cache", "wy", "replay")
BALLOT_US = os.path.join(HERE, "ballot_2026.sqlite")
BALLOT_LOCAL = os.path.join(HERE, "ballot_local_2026.sqlite")
SUMMARIES = ("Statewide_Candidates_Summary", "Statewide_Senate_Candidates_Summary", "Statewide_House_Candidates_Summary",
             "Statewide_Judicial_Summary")
COUNTIES = ("Albany", "Big Horn", "Campbell", "Carbon", "Converse", "Crook", "Fremont", "Goshen", "Hot Springs", "Johnson",
            "Laramie", "Lincoln", "Natrona", "Niobrara", "Park", "Platte", "Sheridan", "Sublette", "Sweetwater", "Teton",
            "Uinta", "Washakie", "Weston")
PARTIES = {"Republican": "REP", "Democratic": "DEM", "Libertarian": "LIB", "Constitution": "CON", "Independent": "IND"}
NOT_CHOICES = ("Overvotes", "Undervotes")
MARGIN = 80                     # points from the page's left edge: county names start at about 20
NUMBER = re.compile(r"^(?:\d{1,3}(?:,\d{3})*|\d+|-)$")
SUFFIX = {"JR", "SR", "II", "III", "IV", "V"}
COURT = (("supreme", "supreme_court_retention"), ("chancery", "chancery_court_retention"),
         ("circuit", "circuit_court_retention"), ("district court", "district_court_retention"))
STATEWIDE = {"governor": "governor", "secretary of state": "secretary_of_state", "state auditor": "state_auditor",
             "state treasurer": "state_treasurer", "superintendent of public instruction": "superintendent_of_public_instruction"}


# ============================================================================================== small helpers

def fold(s):
    return "".join(ch for ch in unicodedata.normalize("NFKD", str(s or "")) if not unicodedata.combining(ch))


def family(name):
    n = re.sub(r"\s+and\s+.*$", "", fold(name))                  # a ticket, 'Donald J. Trump and JD Vance'
    n = re.sub(r'"[^"]*"|\([^)]*\)', " ", n)
    toks = [re.sub(r"[^A-Za-z]", "", t).upper() for t in n.split()]
    toks = [t for t in toks if t and t not in SUFFIX]
    return toks[-1] if toks else ""


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", fold(name).lower()).strip("-")[:48] or "unnamed"


# ============================================================================================== the crosswalk (offline)

def build_crosswalk(path=CROSSWALK, say=print):
    races = {}
    us = sqlite3.connect(f"file:{BALLOT_US}?mode=ro", uri=True)
    for rid, office in us.execute("SELECT race_id, office FROM races WHERE state=?", (STATE,)):
        races[rid] = {"cls": "us_senate" if office == "U.S. Senate" else "us_house", "district": None, "level": "congress",
                      "office": office, "judge": None, "names": {}}
    for rid, el, name, party, wi in us.execute("SELECT race_id, election, name, party, write_in FROM candidates WHERE race_id LIKE ?",
                                               (f"2026-{STATE}-%",)):
        if rid in races:
            races[rid]["names"].setdefault(el, []).append([name, party, int(wi or 0)])
    loc = sqlite3.connect(f"file:{BALLOT_LOCAL}?mode=ro", uri=True)
    for rid, level, kind, office, district in loc.execute(
            "SELECT race_id, level, office_kind, office, district FROM sl_races WHERE state=? AND level IN ('statewide','legislature','court')",
            (STATE,)):
        races[rid] = {"cls": kind, "district": str(district) if district else None, "level": level, "office": office,
                      "judge": rid.rsplit("-", 1)[1] if kind.endswith("_retention") else None, "names": {}}
    for rid, el, name, party, wi in loc.execute("SELECT race_id, election, name, party, write_in FROM sl_candidates WHERE race_id LIKE ?",
                                                (f"2026-{STATE}-%",)):
        if rid in races:
            races[rid]["names"].setdefault(el, []).append([name, party, int(wi or 0)])
    counties = {}
    for cid, name in loc.execute("SELECT id, name FROM sl_places WHERE kind='county' AND id LIKE ?", (FIPS + "___",)):
        counties[re.sub(r"\s+County$", "", name)] = cid
    doc = {"_about": "Wyoming's 2026 races for Congress, statewide offices, the Legislature and judges' retention (read only from the "
                     "ballot databases) and what ties a table of the Secretary of State's summaries to each: the office class, the "
                     "district, a retention's judge, the candidates' names as filed for each 2026 election; and the counties' FIPS "
                     "codes by name.",
           "state": STATE, "built": dt.date.today().isoformat(), "races": races, "counties": counties}
    with open(path + ".part", "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=0, sort_keys=True)
    os.replace(path + ".part", path)
    say(f"    crosswalk: {len(races)} races, {len(counties)} counties -> {os.path.relpath(path, HERE)}")
    return doc


_CW = {"mtime": None, "doc": None}


def crosswalk(path=CROSSWALK):
    m = os.path.getmtime(path)
    if _CW["mtime"] != m:
        _CW["doc"], _CW["mtime"] = json.load(open(path, encoding="utf-8")), m
    return _CW["doc"]


def resolve(cw, title, judge):
    """(race id or None, why)."""
    low = " ".join(fold(title).lower().split())
    if "amendment" in low or "proposition" in low:
        return None, "a ballot question, not a contest between people"
    if low.startswith("united states president"):
        return None, "not on the 2026 ballot"
    want = None
    if low == "united states senator":
        want = ("us_senate", None)
    elif low == "united states representative":
        want = ("us_house", None)
    elif low in STATEWIDE:
        want = (STATEWIDE[low], None)
    else:
        m = re.fullmatch(r"(senate|house) district (\d+)", low)
        if m:
            want = ("state_senate" if m.group(1) == "senate" else "state_house", m.group(2))
    if want:
        got = [r for r, e in cw["races"].items() if e["cls"] == want[0] and (want[1] is None or e["district"] == want[1])]
        return (got[0], "") if len(got) == 1 else (None, f"{len(got)} 2026 races fit this title")
    if judge:
        kind = next((k for w, k in COURT if w in low), None)
        fam = family(judge)
        got = [r for r, e in cw["races"].items() if kind and e["cls"] == kind and e["judge"] == fam]
        return (got[0], "") if len(got) == 1 else (None, f"a retention vote; {len(got)} judges on the 2026 list fit it")
    return None, "no 2026 race on the lists has this title"


# ============================================================================================== reading one PDF

def page_rows(raw):
    """[(page, [(y, [(x0, x1, text)])])] with the kit's reader."""
    from ballot.pdftext import PDF, rows
    pdf = PDF(raw)
    out = []
    for n, (page, res) in enumerate(pdf.pages(), start=1):
        got = []
        for y, rs in rows(pdf, page, res):
            merged = []                       # pieces that touch are one piece ("1,1" + "17", "W" + "rite-Ins"), as pdftext joins them
            for x0, _y, size, t, x1 in sorted(rs, key=lambda r: r[0]):
                gap = x0 - merged[-1][1] if merged else None
                words = merged and re.search(r"[A-Za-z(]", t) and re.search(r"[A-Za-z)]", merged[-1][2])
                if merged and t.strip() and merged[-1][2] and (gap <= 0.18 * size or (words and gap <= 1.2 * size)):
                    a, _b, s = merged[-1]               # a word space (some files set every word apart) joins with a space
                    merged[-1] = (a, max(x1, merged[-1][1]), s + ("" if gap <= 0.18 * size else " ") + t)
                else:
                    merged.append((x0, x1, t))
            got.append((y, [(a, b, t.strip()) for a, b, t in merged if t.strip()]))
        out.append((n, got))
    return out


def tables(raw, label, problems):
    """Every table of one summary PDF: [{"title", "judge", "columns": [{"head", "party"}], "rows": {county: [figure or
    None]}, "total": [figure]}], continued tables joined."""
    out = collections.OrderedDict()
    for pno, rows in page_rows(raw):
        texts = [" ".join(t for _a, _b, t in rs) for _y, rs in rows]
        # a county row starts at the left margin (a candidate named Johnson heads a column further right)
        first = next((i for i, (_y, rs) in enumerate(rows) if rs and rs[0][2] in COUNTIES and rs[0][0] < MARGIN), None)
        if first is None:
            continue
        # the heading rows: after the summary's own two lines, before the first county row
        head = [i for i in range(first) if not re.search(r"Official Summary|Unofficial Summary|Summary$|Election - ", texts[i])]
        if not head:
            problems.append(f"{label} page {pno}: no office heading")
            continue
        title = re.sub(r",\s*Continued$", "", texts[head[0]]).strip()
        judge, party_runs, name_rows = None, [], []
        for i in head[1:]:
            rs = rows[i][1]
            if rs and all(t in PARTIES for _a, _b, t in rs for t in t.split()):
                party_runs = [(a, b, p) for a, b, t in rs for p in [t]]
            else:
                name_rows.append(rs)
        if name_rows and any("Yes" == t for _a, _b, t in name_rows[-1]) and len(name_rows) >= 2:
            judge = " ".join(t for _a, _b, t in name_rows[0])
            name_rows = name_rows[1:]
        # columns: right edges of the county rows' figures
        edges = []
        body = []
        total = None
        for y, rs in rows[first:]:
            if not rs:
                continue
            name = rs[0][2]
            if (name not in COUNTIES and name != "Total") or rs[0][0] >= MARGIN:
                if re.match(r"Page \d+ of \d+", name) or name.startswith("*"):
                    continue
                break
            figs = [(a, b, t) for a, b, t in rs[1:] if t != "*"]       # "*" marks the gap between two parties' columns
            if any(not NUMBER.match(t) for _a, _b, t in figs):
                problems.append(f"{label} page {pno}: the {name} row holds something that is not a figure")
            for _a, b, _t in figs:
                if not any(abs(b - e) < 4 for e in edges):
                    edges.append(b)
            (body.append((name, figs)) if name != "Total" else None)
            if name == "Total":
                total = figs
        edges.sort()
        cols = [{"head": [], "party": None, "x": e} for e in edges]
        for rs in name_rows:
            for a, b, t in rs:
                mid = (a + b) / 2
                k = next((i for i, e in enumerate(edges) if e >= mid - 1), None)
                if k is None:
                    problems.append(f"{label} page {pno}: the heading {t!r} sits over no column")
                    continue
                cols[k]["head"].append(t)
        for c in cols:
            c["head"] = " ".join(c["head"]).strip()
        if party_runs:
            groups, g = [], []
            for c in cols:
                g.append(c)
                if c["head"] == "Undervotes":
                    groups.append(g)
                    g = []
            if g:
                groups.append(g)
            if len(groups) != len(party_runs):
                problems.append(f"{label} page {pno}: {len(party_runs)} parties over {len(groups)} groups of columns")
            for (_a, _b, p), g in zip(party_runs, groups):
                for c in g:
                    c["party"] = PARTIES.get(p, p)

        def fig(figs, e):
            for a, b, t in figs:
                if abs(b - e) < 4 and NUMBER.match(t):
                    return None if t == "-" else int(t.replace(",", ""))
            return None

        key_base = (title, judge)
        groups = collections.OrderedDict()
        for c in cols:
            groups.setdefault(c["party"], []).append(c)
        for party, cs in groups.items():
            t = out.setdefault(key_base + (party,), {"title": title, "judge": judge, "party": party, "columns": [], "rows": {},
                                                     "outside": set(), "total": []})
            base = len(t["columns"])
            t["columns"].extend({"head": c["head"]} for c in cs)
            for name, figs in body:
                vals = [fig(figs, c["x"]) for c in cs]
                dashes = [t_ for a_, b_, t_ in figs if any(abs(b_ - c["x"]) < 4 for c in cs)]
                if dashes and all(t_ == "-" for t_ in dashes):
                    t["outside"].add(name)                    # the county is outside this district
                row = t["rows"].setdefault(name, [None] * base)
                row.extend(vals)
            for name in t["rows"]:
                if len(t["rows"][name]) < len(t["columns"]):
                    t["rows"][name].extend([None] * (len(t["columns"]) - len(t["rows"][name])))
            t["total"].extend(fig(total or [], c["x"]) for c in cs)
    return list(out.values())


def contests_of(tbls, cw, election, problems, notes):
    out, unmatched, seen = [], [], set()
    for t in tbls:
        office = t["title"] + (f" ({t['judge']})" if t["judge"] else "") + (f", {t['party']}" if t["party"] else "")
        rid, why = resolve(cw, t["title"], t["judge"])
        if not rid:
            unmatched.append({"key": office, "office": office, "why": why})
            continue
        race = cw["races"][rid]
        if election == "primary":
            el = f"primary-{t['party'] or 'NP'}"
            rid = f"{rid}-{(t['party'] or 'np').lower()}-primary"
        else:
            el = "general"
        if rid in seen:
            unmatched.append({"key": office, "office": office, "why": "a second table tied to the same race"})
            continue
        seen.add(rid)
        filed = collections.defaultdict(list)
        for n, _p, wi in race["names"].get(el, []) if election != "past" else []:
            filed[family(n)].append(n)
        choices, idx = [], []
        for i, c in enumerate(t["columns"]):
            h = c["head"]
            if h in NOT_CHOICES:
                continue
            m = re.search(r"\((\w{1,4})\)\s*$", h)
            party = m.group(1) if m else t["party"]
            name = re.sub(r"\s*\(\w{1,4}\)\s*$", "", h).strip()
            wi = name == "Write-Ins"
            if name.startswith("*"):
                name = name.lstrip("* ").strip()
            key = "write-in" if wi else slug(name)
            f = filed.get(family(name)) or []
            choices.append({"key": key, "name": name, "party": None if wi or race["level"] == "court" else party,
                            "ballot_name": f[0] if len(f) == 1 and not wi else None, "write_in": wi, "order": None})
            idx.append(i)
        if len({c["key"] for c in choices}) != len(choices):
            problems.append(f"{office}: two columns make the same key")
        units = [{"id": "all", "kind": "race", "name": "the whole contest", "parent": None, "map_id": None}]
        rows, reporting = [], []
        in_n, all_n = 0, 0
        sums = [0] * len(t["columns"])
        for county, vals in t["rows"].items():
            if county in t["outside"]:
                continue
            fips = cw["counties"].get(county)
            if not fips:
                problems.append(f"{office}: a county the crosswalk does not know: {county}")
                continue
            all_n += 1
            got = any(v for v in vals if v)
            for k, v in enumerate(vals):
                sums[k] += v or 0
            if not got:
                reporting.append({"unit": fips, "in": 0, "all": 1})
                continue
            in_n += 1
            units.append({"id": fips, "kind": "county", "name": county, "parent": STATE, "map_id": fips})
            reporting.append({"unit": fips, "in": 1, "all": 1})
            for ch, i in zip(choices, idx):
                rows.append({"unit": fips, "choice": ch["key"], "type": "total", "votes": vals[i] or 0})
        if t["total"] and any(v is not None for v in t["total"]):
            bad = [t["columns"][k]["head"] for k, v in enumerate(t["total"]) if (v or 0) != sums[k]]
            if bad:
                problems.append(f"{office}: the county rows do not add up to the Total row ({', '.join(bad[:4])})")
        for ch, i in zip(choices, idx):
            rows.append({"unit": "all", "choice": ch["key"], "type": "total", "votes": sums[i]})
        reporting.insert(0, {"unit": "all", "in": in_n, "all": all_n})
        out.append({"race_id": rid, "key": office, "office": t["title"], "level": race["level"], "district": race["district"], "seats": 1,
                    "rule": "plurality", "rcv": False, "unit_kind": "county", "units_all": all_n, "choices": choices,
                    "units": units, "rows": rows, "reporting": reporting, "stated": [], "controls": []})
    return out, unmatched


# ============================================================================================== the night's requests

_KEPT = {}                       # address -> (version, bytes): what check() fetched, for fetch()


def page_url(entry):
    nid = (entry.get("election") or {}).get("nov3_id") or "2026GeneralResults"
    if not re.fullmatch(r"\d{4}\w+Results", nid):
        nid = "2026GeneralResults"
    return PAGE.format(year=nid[:4], id=nid)


def _get(src, url, accept, conditional=False, expect_html=False):
    from election.source import Refused, SourceError
    r = src.get(url, state=STATE, accept=accept, conditional=conditional, small=True, expect_html=expect_html)
    if r.refused:
        raise Refused(url, r.why)
    if r.not_modified:
        return r
    if r.status != 200:
        raise SourceError(f"{url} answered {r.status}")
    return r


def summary_links(page, url):
    out = []
    for m in re.finditer(r"(?i)href\s*=\s*['\"]?([^'\" >]+\.pdf)", page.decode("utf-8", "replace")):
        h = m.group(1)
        if any(h.endswith(s + ".pdf") for s in SUMMARIES):
            full = SITE + h if h.startswith("/") else h
            if full not in out:
                out.append(full)
    return out


def check(src, entry):
    """The results page (None while it is not posted or links no summary), then each summary with If-Modified-Since;
    the version is the summaries' own validators."""
    from election.source import SourceError
    url = page_url(entry)
    try:
        r = _get(src, url, "text/html", expect_html=True)
    except SourceError:
        return None
    links = summary_links(r.body, url)
    if not links:
        return None
    parts = []
    for u in links:
        x = _get(src, u, "application/pdf", conditional=True)
        if x.not_modified and u in _KEPT:
            parts.append(_KEPT[u][0])
            continue
        if x.body[:4] != b"%PDF":
            raise SourceError(f"{u} is not a PDF")
        v = x.headers.get("last-modified") or x.headers.get("etag") or hashlib.sha256(x.body).hexdigest()[:16]
        _KEPT[u] = (v, x.body)
        parts.append(v)
    return {"version": "|".join(parts), "time": None}


def fetch(src, entry, version):
    url = page_url(entry)
    links = summary_links(_get(src, url, "text/html", expect_html=True).body, url)
    out = []
    for u in links:
        if u in _KEPT:
            out.append((u, _KEPT[u][1]))
        else:
            out.append((u, _get(src, u, "application/pdf").body))
    return out


def read(files, entry):
    cw = crosswalk()
    problems, notes = [], []
    tbls = []
    election = "general"
    for name, raw in files:
        if raw[:4] != b"%PDF":
            continue
        head = " ".join(t for _p, rows in page_rows(raw)[:1] for _y, rs in rows[:3] for _a, _b, t in rs)
        if "Primary Election" in head:
            election = "primary"
        m = re.search(r"Election - [A-Z][a-z]+ \d{1,2}, (\d{4})", head)
        if m and m.group(1) != "2026":
            election = "past"
        tbls += tables(raw, os.path.basename(name), problems)
    contests, unmatched = contests_of(tbls, cw, election, problems, notes)
    return {"state": STATE, "feed": FEED, "source_time": None, "source_version": None, "contests": contests,
            "unmatched": unmatched, "problems": problems, "notes": notes}


# ============================================================================================== tests

def _official(rid, el):
    out = []
    for db, table in ((BALLOT_US, "candidates"), (BALLOT_LOCAL, "sl_candidates")):
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        out += [v for (v,) in con.execute(f"SELECT votes FROM {table} WHERE race_id=? AND election=? AND votes IS NOT NULL", (rid, el))]
    return sorted(out)


def _store_checks(reading, say):
    from election import store
    con = store.connect(":memory:")
    checks = store.run_checks(con, reading)
    for n, p, d in checks:
        say(f"      {'ok  ' if p else 'FAIL'} {n}: {d[:150]}")
    return all(p for n, p, _d in checks if n in store.HARD)


def _files(folder):
    return [(n, open(os.path.join(folder, n), "rb").read()) for n in sorted(os.listdir(folder)) if n.lower().endswith(".pdf")]


def selftest(say=print):
    ok = True

    def expect(c, what):
        nonlocal ok
        say(f"      {'ok  ' if c else 'FAIL'} {what}")
        ok = ok and bool(c)

    rd = read(_files(FIXTURE), {})
    ids = sorted(c["race_id"] for c in rd["contests"])
    expect("2026-WY-S2-rep-primary" in ids and "2026-WY-S2-dem-primary" in ids, f"the Senate primaries are tied ({ids})")
    expect(not rd["problems"], f"no problems ({rd['problems'][:2]})")
    expect(_store_checks(rd, say), "the store's hard checks pass")
    for c in rd["contests"]:
        base, party = re.match(r"(.+)-([a-z]+)-primary$", c["race_id"]).groups()
        named = sorted(r["votes"] for r in c["rows"] if r["unit"] == "all" and r["choice"] != "write-in")
        off = _official(base, f"primary-{party.upper()}")
        if off:                                    # an unopposed primary has no figures stored in the ballot databases
            expect(named == off, f"{c['race_id']}: totals equal the official figures")
    expect(family("Donald J. Trump and JD Vance") == "TRUMP", "a ticket is known by its first name")
    return ok


def make_fixture(say=print):
    """The 2026 primary's Statewide Candidates Summary, kept whole as the fixture (public results, 111 KB)."""
    os.makedirs(FIXTURE, exist_ok=True)
    src = os.path.join(REPLAY, "2026_primary", "2026_Statewide_Candidates_Summary.pdf")
    open(os.path.join(FIXTURE, os.path.basename(src)), "wb").write(open(src, "rb").read())
    say(f"    fixture written: {os.path.relpath(FIXTURE, HERE)}")


def replay_test(say=print):
    """The 2026 primary summaries (fetched once, 2026-10-10): every table tied to a race equals the official totals the
    ballot databases hold (from the Secretary's official results workbook), and every table's counties add up to its
    Total row. The 2024 general summaries: every table's counties add up to its Total row."""
    ok = True
    folder = os.path.join(REPLAY, "2026_primary")
    rd = read(_files(folder), {})
    good = _store_checks(rd, lambda s: None)
    compared, same, diffs = 0, 0, []
    for c in rd["contests"]:
        base, party = re.match(r"(.+)-([a-z]+)-primary$", c["race_id"]).groups()
        off = _official(base, f"primary-{party.upper()}")
        if not off:
            continue
        compared += 1
        named = sorted(r["votes"] for r in c["rows"] if r["unit"] == "all" and r["choice"] != "write-in")
        if named == off:
            same += 1
        else:
            diffs.append(c["race_id"])
    say(f"    2026 primary: {len(rd['contests'])} tables tied, {len(rd['unmatched'])} listed; store checks {'pass' if good else 'FAIL'}; "
        f"{same} of {compared} equal the official totals" + (f"; differ: {diffs[:6]}" if diffs else "")
        + (f"; problems: {rd['problems'][:3]}" if rd["problems"] else ""))
    for w, n in collections.Counter(u["why"] for u in rd["unmatched"]).most_common():
        say(f"        listed, not shown: {n} x {w}")
    ok = ok and good and not diffs and not rd["problems"] and compared > 0
    folder = os.path.join(REPLAY, "2024_general")
    if os.path.isdir(folder):
        rd = read(_files(folder), {})
        good = _store_checks(rd, lambda s: None)
        say(f"    2024 general: {len(rd['contests'])} tables tied to a 2026 race of the same office, {len(rd['unmatched'])} listed; "
            f"store checks {'pass' if good else 'FAIL'}" + (f"; problems: {rd['problems'][:3]}" if rd["problems"] else ""))
        for w, n in collections.Counter(u["why"] for u in rd["unmatched"]).most_common():
            say(f"        listed, not shown: {n} x {w}")
        ok = ok and good and not rd["problems"]
    return ok


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for f in ("crosswalk", "fixture", "selftest", "replay"):
        ap.add_argument("--" + f, action="store_true")
    a = ap.parse_args(argv)
    good = True
    if a.crosswalk:
        build_crosswalk()
    if a.fixture:
        make_fixture()
    if a.selftest:
        print("    Wyoming reader self-test")
        good = selftest() and good
    if a.replay:
        print("    Wyoming replay test")
        good = replay_test() and good
    print("    PASS" if good else "    FAIL")
    return 0 if good else 1


if __name__ == "__main__":
    sys.exit(main())
