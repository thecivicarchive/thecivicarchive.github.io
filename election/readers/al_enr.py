"""election/readers/al_enr.py - Alabama, from the Secretary of State's own results (ARCHITECTURE.md 5.3, section 7: care).

Two sources, one reader:

  Election night   the Secretary's "Election Night Reporting" page, www2.alabamavotes.gov/electionNight/ (ASP.NET), fed by
                   the 67 probate judges. Between elections it is an empty form (checked 2026-10-09 and 2026-10-10: 468
                   bytes, no table), so its layout on the night is NOT KNOWN YET. check() says nothing is posted while
                   the page holds no table. read() takes every table whose heading row names a candidate column and a
                   votes column, under the nearest heading that names an office the crosswalk knows; a page that holds
                   no such table is a problem (the state's last figures stay and the page links out). The architect's
                   plan: load the page once in the last week of October, or on the afternoon of November 3, and mend
                   read_night() then (`run_night.py once --state al --from-file <raw>`). Only the page itself is asked
                   for: no form is posted, no ViewState replayed.

  Certified        the Secretary's precinct results files on the Elections Data Downloads page
                   (sos.alabama.gov/alabama-votes/voter/election-data), weeks after the election: a zip of one old-format
                   Excel file per county (Contest Title, Party, Candidate, a column per precinct, ABSENTEE, PROVISIONAL).
                   certified() reads the general's when it is posted; the reader reads the 2026 primary's for its replay
                   test. The workbook reader is the kit's own (ballot/lists/al.xls_sheets).

What is read (an allowlist): contest titles, parties, candidate names and vote figures; registered-voter and
ballots-cast lines are left out (they are not contests). The files carry no contact details.

    python -m election.readers.al_enr --crosswalk     (re)build election/crosswalk/al.json from the ballot databases
    python -m election.readers.al_enr --selftest      no network: the fixture (three counties of the 2026 primary)
    python -m election.readers.al_enr --replay        the whole 2026 primary file against the official totals stored
"""

import collections
import datetime as dt
import hashlib
import html as H
import io
import json
import os
import re
import sqlite3
import sys
import unicodedata
import zipfile

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

STATE = "AL"
FIPS = "01"
FEED = "al-enr"
FAMILY = "al_enr"
NIGHT = "https://www2.alabamavotes.gov/electionNight/"
DATA_PAGE = "https://www.sos.alabama.gov/alabama-votes/voter/election-data"
CROSSWALK = os.path.join(HERE, "election", "crosswalk", "al.json")
FIXTURE = os.path.join(HERE, "election", "fixtures", "al")
PRIMARY_ZIP = os.path.join(HERE, "ballot_cache", "al", "al_2026_primary_precinct_results.zip")
BALLOT_US = os.path.join(HERE, "ballot_2026.sqlite")
BALLOT_LOCAL = os.path.join(HERE, "ballot_local_2026.sqlite")
STATEWIDE = {"GOVERNOR": "governor", "LIEUTENANT GOVERNOR": "lieutenant_governor", "ATTORNEY GENERAL": "attorney_general",
             "SECRETARY OF STATE": "secretary_of_state", "STATE TREASURER": "state_treasurer", "STATE AUDITOR": "state_auditor",
             "COMMISSIONER OF AGRICULTURE AND INDUSTRIES": "agriculture_commissioner"}
NOT_CHOICES = ("Over Votes", "Under Votes")
SUFFIX = {"JR", "SR", "II", "III", "IV", "V"}


def fold(s):
    return "".join(ch for ch in unicodedata.normalize("NFKD", str(s or "")) if not unicodedata.combining(ch))


def family(name):
    n = re.sub(r'"[^"]*"|\([^)]*\)|“[^”]*”', " ", fold(name))
    if "," in n:
        head, tail = n.split(",", 1)
        n = head if re.sub(r"[^A-Za-z]", "", tail).upper() in SUFFIX else n
    toks = [re.sub(r"[^A-Za-z]", "", t).upper() for t in n.split()]
    toks = [t for t in toks if t and t not in SUFFIX]
    return toks[-1] if toks else ""


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", fold(name).lower()).strip("-")[:48] or "unnamed"


def county_slug(name):
    return re.sub(r"[^a-z]", "", fold(name.replace("_", " ")).lower())


# ============================================================================================== the crosswalk (offline)

def build_crosswalk(path=CROSSWALK, say=print):
    races = {}
    us = sqlite3.connect(f"file:{BALLOT_US}?mode=ro", uri=True)
    for rid, office, district in us.execute("SELECT race_id, office, district FROM races WHERE state=?", (STATE,)):
        races[rid] = {"cls": "us_senate" if office == "U.S. Senate" else "us_house", "district": str(int(district)) if district else None,
                      "seat": None, "level": "congress", "names": {}}
    for rid, el, name, party, wi in us.execute("SELECT race_id, election, name, party, write_in FROM candidates WHERE race_id LIKE ?",
                                               (f"2026-{STATE}-%",)):
        if rid in races:
            races[rid]["names"].setdefault(el, []).append([name, party, int(wi or 0)])
    loc = sqlite3.connect(f"file:{BALLOT_LOCAL}?mode=ro", uri=True)
    for rid, level, kind, district, seat in loc.execute(
            "SELECT race_id, level, office_kind, district, seat FROM sl_races WHERE state=? AND level IN ('statewide','legislature')", (STATE,)):
        races[rid] = {"cls": kind, "district": str(district) if district else None,
                      "seat": re.sub(r"\D", "", seat or "") or None, "level": level, "names": {}}
    for rid, el, name, party, wi in loc.execute("SELECT race_id, election, name, party, write_in FROM sl_candidates WHERE race_id LIKE ?",
                                                (f"2026-{STATE}-%",)):
        if rid in races:
            races[rid]["names"].setdefault(el, []).append([name, party, int(wi or 0)])
    counties = {}
    for cid, name in loc.execute("SELECT id, name FROM sl_places WHERE kind='county' AND id LIKE ?", (FIPS + "___",)):
        counties[county_slug(re.sub(r"\s+County$", "", name))] = cid
    doc = {"_about": "Alabama's 2026 races for Congress, the statewide offices and the Legislature (read only from the ballot "
                     "databases) and what ties a contest title of the Secretary's results to each: the office class, the "
                     "district or place, the candidates' names as filed for each 2026 election; and the counties' FIPS codes.",
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


def title_parts(title):
    """('UNITED STATES SENATOR', 'REP') from 'UNITED STATES SENATOR (REP)'."""
    t = " ".join(fold(title).upper().split())
    m = re.fullmatch(r"(.+?)\s*\((REP|DEM|LIB|IND|NP)\)", t)
    return (m.group(1), m.group(2)) if m else (t, None)


def resolve(cw, title):
    t, _party = title_parts(title)
    t = re.sub(r"^FOR\s+", "", t)
    want = None
    if t == "UNITED STATES SENATOR":
        want = ("us_senate", None, None)
    elif t in STATEWIDE:
        want = (STATEWIDE[t], None, None)
    else:
        m = re.fullmatch(r"UNITED STATES REPRESENTATIVE,? (\d+)(?:ST|ND|RD|TH) CONGRESSIONAL DISTRICT", t)
        if m:
            want = ("us_house", str(int(m.group(1))), None)
        m = m or re.fullmatch(r"STATE (REPRESENTATIVE|SENATOR),? DISTRICT (\d+)", t)
        if m and not want:
            want = ("state_house" if m.group(1) == "REPRESENTATIVE" else "state_senate", m.group(2), None)
        m2 = re.fullmatch(r"PUBLIC SERVICE COMMISSION,? PLACE (\d+)", t)
        if m2:
            want = ("public_service_commissioner", None, m2.group(1))
        m3 = re.fullmatch(r"(?:MEMBER,? )?STATE BOARD OF EDUCATION,? DISTRICT (\d+)", t)
        if m3:
            want = ("state_board_of_education", m3.group(1), None)
    if not want:
        if re.match(r"(PROPOSED|.*AMENDMENT)", t):
            return None, "a ballot question, not a contest between people"
        if re.match(r"(REGISTERED VOTERS|BALLOTS CAST)", t):
            return None, "a count of voters or ballots, not a contest"
        return None, "no 2026 race of this office is read here (county, judicial and party offices come later)"
    got = [r for r, e in cw["races"].items() if e["cls"] == want[0] and (want[1] is None or e["district"] == want[1])
           and (want[2] is None or e["seat"] == want[2])]
    return (got[0], "") if len(got) == 1 else (None, f"{len(got)} 2026 races fit this title")


# ============================================================================================== the certified precinct files

def _number(v):
    if isinstance(v, (int, float)):
        return int(v) if float(v) == int(v) else None
    t = str(v or "").strip().replace(",", "")
    return int(t) if t.isdigit() else (0 if not t else None)


def precinct_files(zip_bytes, problems):
    """{county name: rows} of a precinct results zip: each county's sheet, as the kit's workbook reader gives it."""
    from ballot.lists.al import xls_sheets
    out = {}
    z = zipfile.ZipFile(io.BytesIO(zip_bytes))
    for n in sorted(z.namelist()):
        m = re.fullmatch(r"\d{4}_[A-Z_]*ELECTION-(.+)\.xlsx?", os.path.basename(n), re.I)
        if not m:
            problems.append(f"a file in the zip that is not a county's results: {n}")
            continue
        for _sheet, rows in xls_sheets(z.read(n)).items():
            if not rows:
                continue
            if [str(c or "").strip() for c in rows[0][:3]] != ["Contest Title", "Party", "Candidate"]:
                problems.append(f"{n} does not begin Contest Title, Party, Candidate")
                continue
            out.setdefault(m.group(1).replace("_", " "), []).extend([rows[0]] + rows[1:])
    return out


def read_certified(zip_bytes, election="general", official=True):
    """A reading from one precinct results zip: every contest the crosswalk knows, by precinct, county and statewide,
    with absentee and provisional ballots apart."""
    cw = crosswalk()
    problems, notes = [], []
    files = precinct_files(zip_bytes, problems)
    contests = {}
    unmatched = {}
    for county, rows in files.items():
        fips = cw["counties"].get(county_slug(county))
        if not fips:
            problems.append(f"a county the crosswalk does not know: {county}")
            continue
        heads = [str(c or "").strip() for c in rows[0]]
        cols = list(range(3, len(heads)))
        for r in rows[1:]:
            if not r or not str(r[0] or "").strip():
                continue
            title = re.sub(r"\s+", " ", str(r[0])).strip()
            rid, why = resolve(cw, title)
            if not rid:
                unmatched.setdefault(title, {"key": title, "office": title, "why": why})
                continue
            _t, party = title_parts(title)
            if election == "primary":
                if not party:
                    unmatched.setdefault(title, {"key": title, "office": title, "why": "a primary contest without a party"})
                    continue
                rid = f"{rid}-{party.lower()}-primary"
            c = contests.setdefault(rid, {"title": title, "party": party, "base": rid.split("-" + (party or "").lower() + "-primary")[0]
                                          if election == "primary" else rid, "lines": collections.OrderedDict(), "prec": {}, "counties": set()})
            cand = re.sub(r"\s+", " ", str(r[2] or "")).strip().replace("`", "'").replace("’", "'")
            if cand in NOT_CHOICES:
                continue
            c["counties"].add(fips)
            # one candidate, however the counties spell the name ("O'Hara", "O`hara"): lines are kept by their key
            line = c["lines"].setdefault(slug(cand), {"name": cand, "party": str(r[1] or "").strip() or None, "by": collections.Counter()})
            for i in cols:
                v = _number(r[i]) if i < len(r) else 0
                if v is None:
                    problems.append(f"{county}: {title}, {cand}: a figure that is not a whole number")
                    continue
                h = heads[i]
                if h == "ABSENTEE":
                    line["by"][(fips, "absentee")] += v
                elif h == "PROVISIONAL":
                    line["by"][(fips, "provisional")] += v
                else:
                    pid = f"{fips}-{slug(h)}"
                    c["prec"][pid] = (h, fips)
                    line["by"][(pid, "election_day")] += v
    out = []
    for rid, c in sorted(contests.items()):
        race = cw["races"][c["base"]]
        el = f"primary-{c['party']}" if election == "primary" else "general"
        filed = collections.defaultdict(list)
        for n, _p, wi in race["names"].get(el) or race["names"].get("general", []):
            filed[family(n)].append(n)
        choices, rows = [], []
        units = {"all": {"id": "all", "kind": "race", "name": "the whole contest", "parent": None, "map_id": None}}
        for f in sorted(c["counties"]):
            units[f] = {"id": f, "kind": "county", "name": None, "parent": STATE, "map_id": f}
        for pid, (name, f) in c["prec"].items():
            units[pid] = {"id": pid, "kind": "precinct", "name": name, "parent": f, "map_id": None}
        for _k, line in c["lines"].items():
            cand = line["name"]
            wi = cand.lower().startswith("write-in")
            key = "write-in" if wi else slug(cand)
            fl = filed.get(family(cand)) or []
            choices.append({"key": key, "name": cand, "party": None if wi else line["party"], "ballot_name": fl[0] if len(fl) == 1 and not wi else None,
                            "write_in": wi, "order": None})
            by_unit = collections.Counter()
            by_county = collections.defaultdict(collections.Counter)
            for (u, vt), v in line["by"].items():
                by_unit[u] += v
                f = u if len(u) == 5 else u[:5]
                by_county[f][vt] += v
            for u, v in by_unit.items():
                if len(u) > 5:
                    rows.append({"unit": u, "choice": key, "type": "total", "votes": v})
            for f, types in by_county.items():
                rows.append({"unit": f, "choice": key, "type": "total", "votes": sum(types.values())})
            allt = collections.Counter()
            for types in by_county.values():
                allt.update(types)
            rows.append({"unit": "all", "choice": key, "type": "total", "votes": sum(allt.values())})
            rows += [{"unit": "all", "choice": key, "type": vt, "votes": v} for vt, v in sorted(allt.items())]
        reporting = [{"unit": "all", "in": len(c["prec"]), "all": len(c["prec"])}]
        reporting += [{"unit": pid, "in": 1, "all": 1} for pid in c["prec"]]
        out.append({"race_id": rid, "key": c["title"], "office": c["title"], "level": race["level"], "district": race["district"], "seats": 1,
                    "rule": "majority_runoff" if election == "primary" else "plurality", "rcv": False, "unit_kind": "precinct",
                    "units_all": len(c["prec"]), "choices": choices, "units": list(units.values()), "rows": rows,
                    "reporting": reporting, "stated": [], "controls": []})
    return {"state": STATE, "feed": FEED, "source_time": None, "source_version": None, "official": official, "contests": out,
            "unmatched": list(unmatched.values()), "problems": problems, "notes": notes}


# ============================================================================================== election night

def _text(fragment):
    return re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


def _visible(page):
    page = re.sub(r'(?is)<input[^>]+name="__(VIEWSTATE|VIEWSTATEGENERATOR|EVENTVALIDATION)"[^>]*>', " ", page)
    return _text(re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", page))


def read_night(files):
    """The election-night page(s): tables whose heading row has a candidate and a votes column, each under the nearest
    heading that names an office. Written before the page's layout could be seen; a page that holds no such table is a
    problem, so the state's last figures stay."""
    cw = crosswalk()
    problems, contests, unmatched, seen = [], [], [], set()
    for name, raw in files:
        page = raw.decode("utf-8", "replace")
        heading = None
        for m in re.finditer(r"(?is)<(h\d|caption|th|span|div|td)[^>]*>([^<]{4,140})</\1>|<table.*?</table>", page):
            if m.group(1):
                t = _text(m.group(2))
                if resolve(cw, t)[0] or re.search(r"(?i)senator|representative|governor|attorney|secretary|treasurer|auditor|commission|board of education", t):
                    heading = t
                continue
            trs = re.findall(r"(?is)<tr[^>]*>(.*?)</tr>", m.group(0))
            grid = [[_text(c) for c in re.findall(r"(?is)<t[hd][^>]*>(.*?)</t[hd]>", tr)] for tr in trs]
            head_i = next((i for i, row in enumerate(grid) if any(re.search(r"(?i)candidate", c) for c in row)
                           and any(re.search(r"(?i)^(votes|total votes|total)$", c) for c in row)), None)
            if head_i is None or not heading:
                continue
            head = grid[head_i]
            ci = next(i for i, c in enumerate(head) if re.search(r"(?i)candidate", c))
            vi = next(i for i, c in enumerate(head) if re.search(r"(?i)^(votes|total votes|total)$", c))
            pi = next((i for i, c in enumerate(head) if re.search(r"(?i)^party$", c)), None)
            rid, why = resolve(cw, heading)
            if not rid or rid in seen:
                unmatched.append({"key": heading, "office": heading, "why": why or "a second table for the same race"})
                continue
            seen.add(rid)
            race = cw["races"][rid]
            filed = collections.defaultdict(list)
            for n, _p, wi in race["names"].get("general", []):
                filed[family(n)].append(n)
            choices, rows = [], []
            for row in grid[head_i + 1:]:
                if len(row) <= max(ci, vi) or not row[ci] or row[ci].lower().startswith(("total", "over", "under")):
                    continue
                v = re.sub(r"[^\d]", "", row[vi])
                if not v:
                    continue
                cand = row[ci]
                wi = cand.lower().startswith("write-in")
                key = "write-in" if wi else slug(cand)
                fl = filed.get(family(cand)) or []
                choices.append({"key": key, "name": cand, "party": (row[pi] or None) if pi is not None and pi < len(row) else None,
                                "ballot_name": fl[0] if len(fl) == 1 and not wi else None, "write_in": wi, "order": None})
                rows.append({"unit": "all", "choice": key, "type": "total", "votes": int(v)})
            if choices:
                contests.append({"race_id": rid, "key": heading, "office": heading, "level": race["level"], "district": race["district"],
                                 "seats": 1, "rule": "plurality", "rcv": False, "unit_kind": "race", "units_all": None, "choices": choices,
                                 "units": [{"id": "all", "kind": "race", "name": "the whole contest", "parent": None, "map_id": None}],
                                 "rows": rows, "reporting": [], "stated": [], "controls": []})
    if not contests:
        problems.append("the election-night page holds no results table in a layout this reader knows yet; mend read_night() "
                        "with the page kept raw")
    return {"state": STATE, "feed": FEED, "source_time": None, "source_version": None, "contests": contests,
            "unmatched": unmatched, "problems": problems}


def _get(src, url, accept="text/html", expect_html=True):
    from election.source import Refused, SourceError
    r = src.get(url, state=STATE, accept=accept, small=True, expect_html=expect_html)
    if r.refused:
        raise Refused(url, r.why)
    if r.status != 200:
        raise SourceError(f"{url} answered {r.status}")
    return r


def check(src, entry):
    """The election-night page: None while it holds no table (no election loaded); else a hash of what it shows."""
    r = _get(src, NIGHT)
    if b"<table" not in r.body.lower():
        return None
    return {"version": hashlib.sha256(_visible(r.body.decode("utf-8", "replace")).encode()).hexdigest()[:20], "time": None}


def fetch(src, entry, version):
    return [(NIGHT, _get(src, NIGHT).body)]


def read(files, entry):
    zips = [b for _n, b in files if b[:2] == b"PK"]
    if zips:
        return read_certified(zips[0], election="general")
    return read_night(files)


def certified(src, entry):
    """The general's precinct results zip from the Elections Data Downloads page, once posted: ({race: {choice: votes}},
    source, date). None while it is not posted."""
    page = _get(src, DATA_PAGE).body.decode("utf-8", "replace")
    m = re.search(r"""href=["']([^"']*2026[-_ ]?General[^"']*Precinct[^"']*\.zip)["']""", page, re.I)
    if not m:
        return None
    url = m.group(1) if m.group(1).startswith("http") else "https://www.sos.alabama.gov" + m.group(1)
    rd = read_certified(_get(src, url, accept="application/zip", expect_html=False).body)
    if rd["problems"]:
        raise ValueError("; ".join(rd["problems"][:3]))
    out = {c["race_id"]: {r["choice"]: r["votes"] for r in c["rows"] if r["unit"] == "all" and r["type"] == "total"} for c in rd["contests"]}
    return out, "the Alabama Secretary of State's precinct results files", dt.date.today().isoformat()


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


def make_fixture(say=print):
    """Three counties of the 2026 primary's precinct zip (public results)."""
    os.makedirs(FIXTURE, exist_ok=True)
    src = zipfile.ZipFile(PRIMARY_ZIP)
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w", zipfile.ZIP_DEFLATED) as z:
        for n in ("2026_PRIMARY_ELECTION-Autauga.xls", "2026_PRIMARY_ELECTION-Coosa.xls", "2026_PRIMARY_ELECTION-Lowndes.xls"):
            z.writestr(n, src.read(n))
    open(os.path.join(FIXTURE, "primary_three_counties.zip"), "wb").write(bio.getvalue())
    open(os.path.join(FIXTURE, "night_empty.html"), "wb").write(
        b'<!DOCTYPE html><html><head><title></title></head><body><form name="form1" method="post" action="./" id="form1">'
        b'<input type="hidden" name="__VIEWSTATE" id="__VIEWSTATE" value="x" /><div></div></form></body></html>')
    say(f"    fixture written: {os.path.relpath(FIXTURE, HERE)}")


def selftest(say=print):
    ok = True

    def expect(c, what):
        nonlocal ok
        say(f"      {'ok  ' if c else 'FAIL'} {what}")
        ok = ok and bool(c)

    rd = read_certified(open(os.path.join(FIXTURE, "primary_three_counties.zip"), "rb").read(), election="primary")
    ids = sorted(c["race_id"] for c in rd["contests"])
    expect("2026-AL-S2-rep-primary" in ids and "2026-AL-GOV-dem-primary" in ids, f"contests tied to races ({len(ids)})")
    expect(not rd["problems"], f"no problems ({rd['problems'][:2]})")
    expect(_store_checks(rd, say), "the store's hard checks pass")
    sen = next(c for c in rd["contests"] if c["race_id"] == "2026-AL-S2-rep-primary")
    tot = {r["choice"]: r["votes"] for r in sen["rows"] if r["unit"] == "all" and r["type"] == "total"}
    parts = collections.Counter()
    for r in sen["rows"]:
        if r["unit"] == "all" and r["type"] != "total":
            parts[r["choice"]] += r["votes"]
    expect(tot == dict(parts), "Election Day, absentee and provisional add up to each total")
    empty = open(os.path.join(FIXTURE, "night_empty.html"), "rb").read()
    expect(b"<table" not in empty.lower(), "the empty election-night form holds no table (check() says nothing is posted)")
    rn = read_night([(NIGHT, empty)])
    expect(rn["problems"] and not rn["contests"], "a page with no results table is a problem, never an empty count")
    sample = (b"<h3>UNITED STATES SENATOR</h3><table><tr><th>Candidate</th><th>Party</th><th>Votes</th></tr>"
              b"<tr><td>Barry Moore</td><td>REP</td><td>1,234</td></tr><tr><td>Everett Wess</td><td>DEM</td><td>567</td></tr>"
              b"<tr><td>Write-In</td><td></td><td>8</td></tr></table>")
    rs = read_night([(NIGHT, sample)])
    expect([c["race_id"] for c in rs["contests"]] == ["2026-AL-S2"] and rs["contests"][0]["rows"][0]["votes"] == 1234,
           "a plain candidate-and-votes table under an office heading is read")
    return ok


def replay_test(say=print):
    """The 2026 primary's precinct zip (the Secretary's, July 31): every contest the crosswalk ties equals the official
    totals the ballot databases hold for it; the May contests of districts 1 and 6, replaced by the August special
    primaries, are compared with nothing (the databases hold the specials)."""
    rd = read_certified(open(PRIMARY_ZIP, "rb").read(), election="primary")
    good = _store_checks(rd, lambda s: None)
    compared, same, diffs, skipped = 0, 0, [], []
    for c in rd["contests"]:
        base, party = re.match(r"(.+)-([a-z]+)-primary$", c["race_id"]).groups()
        if base in ("2026-AL-H01", "2026-AL-H06") and party == "rep":
            skipped.append(c["race_id"])
            continue
        off = _official(base, f"primary-{party.upper()}")
        if not off:
            continue
        compared += 1
        mine = sorted(r["votes"] for r in c["rows"] if r["unit"] == "all" and r["type"] == "total" and r["choice"] != "write-in")
        (diffs.append(c["race_id"]) if mine != off else None)
        same += mine == off
    say(f"    2026 primary: {len(rd['contests'])} contests tied, {len(rd['unmatched'])} listed; store checks {'pass' if good else 'FAIL'}; "
        f"{same} of {compared} equal the official totals" + (f"; differ: {diffs[:6]}" if diffs else "")
        + (f"; set aside: {skipped}" if skipped else "") + (f"; problems: {rd['problems'][:3]}" if rd["problems"] else ""))
    for w, k in collections.Counter(u["why"] for u in rd["unmatched"]).most_common():
        say(f"        listed, not shown: {k} x {w}")
    return good and not diffs and not rd["problems"] and compared > 0


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
        print("    Alabama reader self-test")
        good = selftest() and good
    if a.replay:
        print("    Alabama replay test")
        good = replay_test() and good
    print("    PASS" if good else "    FAIL")
    return 0 if good else 1


if __name__ == "__main__":
    sys.exit(main())
