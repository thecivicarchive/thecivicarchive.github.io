"""election/readers/fl_watch.py - Florida's results, from the Division of Elections' election-night file (Florida Election
Watch's flat file, flelectionfiles.floridados.gov/enightfilespublic/<yyyymmdd>_ElecResultsFL.txt).

One tab-separated file, one row per candidate per county. Columns kept (an allowlist; the file has no others today):
ElectionDate, PartyCode, RaceCode, RaceName, CountyCode, CountyName, Juris1num (the district), Juris2num, Precincts,
PrecinctsReporting, CanNameLast, CanNameFirst, CanNameMiddle, CanVotes. The file gives no statewide line: a contest's
whole figure is the sum of its counties. The address is asked with a conditional request (the file's ETag), so an
unchanged file costs a few bytes; it answers 404 until the Division posts the night's file.

Florida counts mail and early ballots before the polls close and releases them first, from 8 p.m. Eastern; the file
has county totals only (no split by how ballots were cast). The figures are "as reported" until the Elections Canvassing
Commission certifies them; certified() reads the Division's own Summary Report pages once they say "Official Results".

    python -m election.readers.fl_watch --crosswalk     rebuild election/crosswalk/fl.json (no request: the Nov 3 file is
                                                        not posted until the night, so races are keyed from the lists)
    python -m election.readers.fl_watch --replay        fetch the 2024 general's file once, read it, and check its county
                                                        sums against the Division's official Summary Report (federal races)
    python -m election.readers.fl_watch --selftest      the reader's test on its fixture (no network)
"""

import argparse
import csv
import hashlib
import html as H
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from election.readers import _common_n11 as K  # noqa: E402

STATE = "FL"
FAMILY = "fl_watch"
FEED = "fl-fl_watch"
BASE = "https://flelectionfiles.floridados.gov/enightfilespublic/"
RESULTS = "https://results.elections.myflorida.com"
NOV3 = "20261103"
REPLAY = "20241105"
ACCEPT = "text/plain, application/octet-stream, */*"
COLS = ("ElectionDate", "PartyCode", "RaceCode", "RaceName", "CountyCode", "CountyName", "Juris1num", "Juris2num", "Precincts",
        "PrecinctsReporting", "CanNameLast", "CanNameFirst", "CanNameMiddle", "CanVotes")
STATEWIDE = {"GOV": "governor", "ATG": "attorney_general", "CFO": "chief_financial_officer", "AGR": "agriculture_commissioner"}
_LAST = {}


def day_of(entry):
    ids = K.election_ids(entry, r"\d{8}")
    return ids[0] if ids else NOV3


def url_of(day):
    return BASE + f"{day}_ElecResultsFL.txt"


def key_of(code, title):
    code, t = (code or "").strip().upper(), re.sub(r"\s+", " ", title or "").strip()
    if code == "USS" or t.lower().startswith("united states senator"):
        return "us_senate"
    m = re.match(r"Representative in Congress, District (\d+)", t)
    if code == "USR" and m:
        return f"us_house:{int(m.group(1))}"
    if code in STATEWIDE:
        return STATEWIDE[code]
    low = t.lower()
    for words, k in (("governor", "governor"), ("attorney general", "attorney_general"), ("chief financial officer", "chief_financial_officer"),
                     ("commissioner of agriculture", "agriculture_commissioner")):
        if low.startswith(words):
            return k
    m = re.match(r"State Senator, District (\d+)", t)
    if m:
        return f"state_senate:{int(m.group(1))}"
    m = re.match(r"State Representative, District (\d+)", t)
    if m:
        return f"state_house:{int(m.group(1))}"
    m = re.match(r"Shall Justice (.+) be retained in Office\?", t)
    if m:
        return f"supreme_court_retention:{K.name_words(m.group(1))[1]}"
    m = re.match(r"Shall Judge (.+) be retained in Office\?", t)
    if m:
        return f"court_of_appeals_retention:{K.name_words(m.group(1))[1]}"
    return None


def rows_of(body):
    """The file's rows as dicts of the kept columns; a header that lacks one of them is a changed layout."""
    text = body.decode("cp1252", "replace")
    rdr = csv.reader(io.StringIO(text), delimiter="\t")
    head = next(rdr, [])
    idx = {h.strip(): i for i, h in enumerate(head)}
    missing = [c for c in COLS if c not in idx]
    if missing:
        raise ValueError(f"the file's heading lacks {', '.join(missing)}")
    out = []
    for r in rdr:
        if len(r) < len(head):
            continue
        out.append({c: r[idx[c]].strip() for c in COLS})
    return out


# ---------------------------------------------------------------------------------------------- requests


def check(src, entry):
    day = day_of(entry)
    r = src.get(url_of(day), state=STATE, accept=ACCEPT, conditional=True)
    if r.not_modified and day in _LAST:
        return {"version": _LAST[day][0], "time": None}
    if r.status in (403, 404) and not r.refused:            # S3 answers 403 or 404 for a file not posted yet
        return None
    body = K.body_ok(r, "the results file")
    ver = hashlib.sha256(body).hexdigest()[:16]
    _LAST[day] = (ver, body)
    return {"version": ver, "time": None}


def discover(src, entry):
    """Whether the night's file is posted yet (its name follows the date; it appears on the night)."""
    r = src.get(url_of(NOV3), state=STATE, accept=ACCEPT)
    if r.ok:
        return {"nov3_id": "20261103 (by the file pattern)", "note": "the file is posted"}
    if r.refused:
        K.body_ok(r, "the results file")
    return {"nov3_id": "20261103 (by the file pattern)", "note": f"the file is not posted yet (answered {r.status}); it appears on the night"}


def fetch(src, entry, version):
    day = day_of(entry)
    got = _LAST.get(day)
    if got and got[0] == version:
        return [(url_of(day), got[1])]
    return [(url_of(day), K.body_ok(src.get(url_of(day), state=STATE, accept=ACCEPT), "the results file"))]


# ---------------------------------------------------------------------------------------------- reading


def day_in(files):
    for n, _b in files:
        m = re.search(r"(\d{8})_ElecResultsFL", str(n))
        if m:
            return m.group(1)
    return None


def person(r):
    last, first, mid = r["CanNameLast"], r["CanNameFirst"], r["CanNameMiddle"]
    if r["RaceCode"] == "PRE":
        return f"{first} / {last}".strip(" /")
    if last in ("Yes", "No") and not first:
        return last
    return " ".join(x for x in (first, mid if mid not in ("/",) else "", last) if x and x.strip()).strip()


def read(files, entry):
    day = day_in(files) or day_of(entry)
    C = K.Contests(STATE, nov3=(day == NOV3))
    _n, body = K.file_named(files, "ElecResultsFL")
    if body is None:
        body = files[0][1] if files else None
    if not body:
        C.problems.append("no results file")
        return C.reading(FEED)
    try:
        rows = rows_of(body)
    except ValueError as e:
        C.problems.append(str(e))
        return C.reading(FEED)
    sums, rep = {}, {}
    for r in rows:
        title = r["RaceName"]
        key = key_of(r["RaceCode"], title)
        rid = C.race_for(key, title, f"{r['RaceCode']}|{r['Juris1num']}|{r['Juris2num']}")
        if not rid:
            continue
        c = C.contest(rid, f"{r['RaceCode']}|{r['Juris1num'].strip()}", title)
        C.unit(c, "all", "race", "the whole contest")
        fips = K.county_unit(STATE, r["CountyName"])
        if not fips:
            C.problems.append(f"{title}: the county {r['CountyName']!r} is not one of Florida's 67")
            continue
        C.unit(c, fips, "county", r["CountyName"], parent=STATE, map_id=fips)
        party = r["PartyCode"] if r["PartyCode"] not in ("NOP",) else None
        ck = C.choice(c, person(r), party, write_in=(r["PartyCode"] == "WRI"))
        v = int(r["CanVotes"] or 0)
        C.row(c, fips, ck, v)
        s = sums.setdefault(rid, {})
        s[ck] = s.get(ck, 0) + v
        rp = rep.setdefault(rid, {})
        rp[fips] = (int(r["PrecinctsReporting"] or 0), int(r["Precincts"] or 0))
    for rid, s in sums.items():
        c = C.c[rid]
        for ck, v in s.items():
            C.row(c, "all", ck, v)
        for fips, (i, a) in sorted(rep[rid].items()):
            C.report(c, fips, i, a)
        C.report(c, "all", sum(i for i, _a in rep[rid].values()), sum(a for _i, a in rep[rid].values()))
        c["units_all"] = len(rep[rid])
    return C.reading(FEED, source_version=hashlib.sha256(body).hexdigest()[:16])


# ---------------------------------------------------------------------------------------------- certified figures


def summary(body, date_words):
    """(official?, {race key: {printed name: votes}}) from one of the Division's Summary Report pages."""
    t = body.decode("cp1252", "replace")
    if date_words and date_words not in t:
        raise ValueError("the Summary Report is of another election")
    head = re.search(r'(?is)CLASS="OfficialHeading">\s*(.*?)\s*<', t)
    official = bool(head) and head.group(1).strip() == "Official Results"
    out = {}
    for tab in re.findall(r"(?is)<TABLE[^>]*>(.*?)</TABLE>", t):
        m = re.search(r"(?i)DetailRpt\.Asp\?ELECTIONDATE=([\d/]+)&RACE=(\w+)&PARTY=(\w*)&DIST=(\d*)", tab)
        if not m:
            continue
        cells = lambda pat, s: [re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", x))).strip() for x in re.findall(pat, s)]  # noqa: E731
        names = cells(r'(?is)CLASS="tableheaderright"[^>]*>(.*?)</TD>', tab)
        tot = re.search(r'(?is)CLASS="ColumnHeaders">\s*Total\s*</TD>(.*?)</TR>', tab)
        totals = [int(x.replace(",", "")) for x in cells(r'(?is)CLASS="tablecellright"[^>]*>(.*?)</TD>', tot.group(1))] if tot else []
        if names and len(totals) == len(names):
            out[(m.group(2).upper(), int(m.group(4) or 0))] = dict(zip(names, totals))
    return official, out


def certified(src, entry):
    """The Division's official figures for the federal races, by its Summary Report (only when it says Official Results):
    ({race id: {choice key: votes}}, source, date)."""
    day = day_of(entry)
    d = f"{int(day[4:6])}/{int(day[6:])}/{day[:4]}"
    url = f"{RESULTS}/SummaryRpt.asp?ElectionDate={d}&Race=FED&DATAMODE="
    off, got = summary(K.body_ok(src.get(url, state=STATE, accept="text/html, */*", expect_html=True), "the Summary Report"), "")
    if not off:
        return {}, None, None
    cw = K.load_crosswalk(STATE)
    out = {}
    for (race, dist), figs in got.items():
        key = "us_senate" if race == "USS" else f"us_house:{dist}" if race == "USR" else None
        rid = cw.get("keys", {}).get(key) if key else None
        if not rid and key == "us_senate":
            rid = next((v for k, v in cw.get("keys", {}).items() if k.startswith("us_senate")), None)
        if rid:
            out[rid] = {K.choice_key(n): v for n, v in figs.items()}
    return out, "the Florida Division of Elections' Summary Report (Official Results)", None


# ---------------------------------------------------------------------------------------------- rehearsals


def units(files):
    _n, body = K.file_named(files.items() if isinstance(files, dict) else files, "ElecResultsFL")
    size = {}
    for r in rows_of(body):
        size[r["CountyName"]] = size.get(r["CountyName"], 0) + int(r["CanVotes"] or 0)
    return [(c, K.county_unit(STATE, c) or "", n) for c, n in sorted(size.items())]


def reveal(files, keep, step):
    """The file with every county not yet in at zero votes and zero precincts reporting."""
    out = {}
    for n, b in dict(files).items():
        if "ElecResultsFL" not in n:
            out[n] = b
            continue
        text = b.decode("cp1252", "replace")
        rdr = list(csv.reader(io.StringIO(text), delimiter="\t"))
        head = rdr[0]
        ci, vi, pi = head.index("CountyName"), head.index("CanVotes"), head.index("PrecinctsReporting")
        for r in rdr[1:]:
            if len(r) > vi and r[ci] not in keep:
                r[vi], r[pi] = "0", "0"
        buf = io.StringIO()
        csv.writer(buf, delimiter="\t", lineterminator="\r\n").writerows(rdr)
        out[n] = buf.getvalue().encode("cp1252", "replace")
    return out


# ---------------------------------------------------------------------------------------------- crosswalk, replay, self-test


def build_crosswalk(say=print):
    return K.build_crosswalk(STATE, "flelectionfiles.floridados.gov enightfilespublic/20261103_ElecResultsFL.txt (posted on the night)", (
        "Florida's races on the November 3, 2026 ballot that the Election Night pages read (Congress from ballot_2026.sqlite; the four "
        "Cabinet offices, the Legislature and the Supreme Court and District Court of Appeal retention votes from "
        "ballot_local_2026.sqlite), each with the key a row of the Division's election-night file is tied by (its race code and "
        "district, or the judge's family name on a retention vote) and the candidates as filed. The Division posts the night's "
        "file only on the night, so no posted contest list is tied here yet; a race whose key no row carries is shown as not "
        "reported."), feed_contests=None, say=say,
        feed_note="A candidate with no opponent is not printed on Florida's ballot (section 101.151), so such races never appear in the file.")


def fixture_dir():
    return os.path.join(K.FIXTURE_DIR, "fl")


def replay(say=print, refetch=False):
    from election import replay as R
    from election.source import Source
    final = os.path.join(K.REPLAY_SOURCES, f"fl-{REPLAY}")
    entry = {"election": {"nov3_id": REPLAY}}
    src = Source()
    if refetch or not os.path.isdir(final):
        sig = check(src, entry)
        R.save_final(fetch(src, entry, sig["version"]), final)
    files = list(R.load_final(final).items())
    rd = read(files, entry)
    cert_path = os.path.join(K.REPLAY_SOURCES, f"fl-{REPLAY}-certified", "summary_FED.html")
    if not os.path.exists(cert_path):
        os.makedirs(os.path.dirname(cert_path), exist_ok=True)
        r = src.get(f"{RESULTS}/SummaryRpt.asp?ElectionDate=11/5/2024&Race=FED&DATAMODE=", state=STATE, accept="text/html, */*", expect_html=True)
        open(cert_path, "wb").write(K.body_ok(r, "the Summary Report"))
    off, figs = summary(open(cert_path, "rb").read(), "November 5, 2024 General Election")
    return check_reading(rd, off, figs, say)


def check_reading(rd, off, figs, say):
    ok = not rd["problems"]
    if rd["problems"]:
        say("  FAIL problems: " + "; ".join(rd["problems"][:5]))
    compared = bad = 0
    for c in rd["contests"]:
        m = re.match(r"(USS|USR)\|(\d*)", c["key"])
        if not m:
            continue
        want = figs.get((m.group(1), int(m.group(2) or 0)))
        if want is None:
            continue
        got = {}
        for r in c["rows"]:
            if r["unit"] == "all":
                got[r["choice"]] = got.get(r["choice"], 0) + r["votes"]
        names = {ch["key"]: ch["name"] for ch in c["choices"]}
        mine = {}
        for k, v in got.items():
            fam = K.name_words(names[k])[1] if names[k] not in ("Yes", "No") else names[k]
            mine[fam] = mine.get(fam, 0) + v
        theirs = {}
        for n, v in want.items():
            fam = "writein" if re.search(r"write", n, re.I) else K.name_words(n)[1]
            theirs[fam] = theirs.get(fam, 0) + v
        wi = sum(v for k, v in got.items() if re.search(r"write", names[k], re.I) or k.startswith("write"))
        compared += 1
        mine_n = {k: v for k, v in mine.items() if v}
        theirs_n = {k: v for k, v in theirs.items() if v and k != "writein"}
        if {k: v for k, v in mine_n.items() if k in theirs_n} != theirs_n:
            bad += 1
            say(f"  FAIL {c['race_id']}: counties add to {mine_n}, the official report says {theirs_n} (write-ins {wi:,})")
    ok = ok and off and compared > 0 and not bad
    votes = sum(r["votes"] for c in rd["contests"] for r in c["rows"] if r["unit"] == "all")
    say(f"  {'ok  ' if ok else 'FAIL'} Florida: {len(rd['contests'])} contests read ({votes:,} votes); {compared} federal races' county sums "
        f"compared with the Division's Summary Report ({'Official Results' if off else 'not marked official'}): {bad} differ; "
        f"{len(rd['unmatched'])} contests listed, not read")
    return ok


def make_fixture(say=print):
    """Four small counties of the 2024 general (Lafayette, Liberty, Glades, Union) and their congressional and legislative
    rows, with a Summary Report made of their own sums (a test file, not the result)."""
    from election import replay as R
    files = R.load_final(os.path.join(K.REPLAY_SOURCES, f"fl-{REPLAY}"))
    n, b = next((n, b) for n, b in files.items() if "ElecResultsFL" in n)
    rdr = list(csv.reader(io.StringIO(b.decode("cp1252")), delimiter="\t"))
    keep = {"Lafayette", "Liberty", "Glades", "Union"}
    rows = [rdr[0]] + [r for r in rdr[1:] if r[6] in keep and r[3] in ("USS", "USR", "STS", "STR", "SCJ")]
    buf = io.StringIO()
    csv.writer(buf, delimiter="\t", lineterminator="\r\n").writerows(rows)
    fd = fixture_dir()
    p = os.path.join(fd, *n.split("/"))
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "wb").write(buf.getvalue().encode("cp1252"))
    say(f"  fixture written: {len(rows) - 1} rows in {p}")


def selftest(say=print):
    from election import replay as R
    fd = fixture_dir()
    if not os.path.isdir(fd):
        say("  FAIL no fixture")
        return False
    files = R.load_final(fd)
    rd = read(list(files.items()), {"election": {"nov3_id": REPLAY}})
    figs = {}
    for c in rd["contests"]:
        m = re.match(r"(USS|USR)\|(\d*)", c["key"])
        if m:
            names = {ch["key"]: ch["name"] for ch in c["choices"]}
            figs[(m.group(1), int(m.group(2) or 0))] = {names[r["choice"]]: r["votes"] for r in c["rows"] if r["unit"] == "all"}
    ok = check_reading(rd, True, figs, say)
    us = units(files)
    part = reveal(files, {us[0][0]}, 1)
    rd2 = read(list(part.items()), {"election": {"nov3_id": REPLAY}})
    left = sum(r["votes"] for c in rd2["contests"] for r in c["rows"] if r["unit"] not in ("all", us[0][1]))
    ok2 = left == 0 and not rd2["problems"] and bool(rd2["contests"])
    say(f"  {'ok  ' if ok2 else 'FAIL'} a rehearsal step with one county of {len(us)} in shows only that county's votes")
    return ok and ok2


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    for f in ("crosswalk", "replay", "refetch", "fixture", "selftest"):
        ap.add_argument("--" + f, action="store_true")
    a = ap.parse_args(argv)
    ok = True
    if a.crosswalk:
        build_crosswalk()
    if a.replay:
        ok = replay(refetch=a.refetch) and ok
    if a.fixture:
        make_fixture()
    if a.selftest:
        ok = selftest() and ok
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
