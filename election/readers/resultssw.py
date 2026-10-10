"""election/readers/resultssw.py - results from the "ResultsSW" election-night sites several Secretaries of State run
on one system: Nebraska and New Mexico (read through the sites' own CSV export, resultsCSV.aspx), and Montana, South
Dakota and Oregon (read from the results pages, resultsSW.aspx, which those sites do not offer as CSV).

What is asked, through election/source.py (the kit's honest User-Agent, one request at a time, at least two seconds
apart on these small state sites):
  CSV states    resultsCSV.aspx?text=All&type=<type>&map=<map>[&eid=<id>]      one file per contest type this site
                reads (Nebraska: CG Congress, SW statewide, PS Public Service Commission, SE State Board of Education, RG Regents, LD
                Legislature; New Mexico: FED, SW, ECX Public Education Commission, LGX Legislature). The cheap
                "what's new" is the Congress file itself (2 KB); its contents, less the column that only gives the
                server's clock, are the version.
  Page states   resultsSW.aspx?type=<type>&map=<map>&eid=<id>                     one page per contest type (Montana:
                FED, STATE, PSC, SENATE, HOUSE). The "what's new" is the federal page, and its figures are the version.
  Nothing else: never the export postbacks, the county pages' scripts or the map services.

What is kept (an allowlist): CSV: RaceID, RaceName, PartyCode, AreaNum, CandidateName, VoteFor, CandidateVotes,
PrecinctsReporting, and New Mexico's absentee, early and election-day columns. Pages: each contest's title, race id,
party, precincts fully reported and in all, each candidate's name, party and votes, and the contest's total votes. The
pages' other text (the office's own contact links among it) is never read.

Units: "all" (the whole contest); these exports give no county rows.
Nebraska posts its November contests early with zero votes: a zero report is a test until the polls close (the
updater never publishes anything read before a state's first poll closing).

    python -m election.readers.resultssw --selftest
    python -m election.readers.resultssw --replay nm 2911       a past election, fetched once and kept, compared with
                                                                the certified figures in the ballot databases
    python -m election.readers.resultssw --posted ne            the posted Nov 3 contest list against the crosswalk
"""

import argparse
import csv
import hashlib
import html
import io
import os
import re
import sys
import urllib.parse

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from election.readers import _n9_match as X  # noqa: E402
from election.source import Refused, SourceError  # noqa: E402

FAMILY = "resultssw"
FIXTURE_DIR = os.path.join(X.FIXTURES, "resultssw")
# (type, map) of each state's contest types, read in this order; the first is the "what's new" file
TYPES = {"NE": [("CG", "DIST"), ("SW", "CTY"), ("PS", "DIST"), ("SE", "DIST"), ("RG", "DIST"), ("LD", "DIST")],
         "NM": [("FED", "CTY"), ("SW", "CTY"), ("ECX", "DIST"), ("LGX", "DIST")],
         "MT": [("FED", "CTY"), ("STATE", "CTY"), ("PSC", "CTY"), ("SENATE", "DIST"), ("HOUSE", "DIST")],
         "SD": [("SWR", "CTY"), ("LEG", "DIST")],
         "OR": [("FED", "CTY"), ("SW", "CTY"), ("LEG", "DIST")]}
CSV_KEEP = ("RaceID", "RaceName", "PartyCode", "AreaNum", "CandidateName", "VoteFor", "CandidateVotes", "PrecinctsReporting",
            "CandidateAbsenteeVotes", "CandidateElectionDayVotes", "CandidateEarlyVotes")
CSV_TYPES = {"CandidateAbsenteeVotes": "absentee", "CandidateElectionDayVotes": "election_day", "CandidateEarlyVotes": "early"}
ERROR_PAGE = re.compile(rb"An error has occur+ed", re.I)


# ============================================================================================== addresses

def signal(entry):
    return ((entry.get("cadence") or {}).get("signal") or "").split(" ")[0]


def mode(entry):
    return "csv" if "resultscsv.aspx" in signal(entry).lower() else "page"


def address(entry, typ, mp):
    """The address of one contest type's file or page, from the registry's signal address: its host and path, the type
    and map asked for, and the election id where the state uses one (a rehearsal's past id in its place)."""
    u = urllib.parse.urlsplit(signal(entry))
    q = dict(urllib.parse.parse_qsl(u.query))
    eid = str((entry.get("election") or {}).get("nov3_id") or "")
    m = re.match(r"\s*(\d{3,12})\b", eid)
    if "eid" in q or m:
        if not m:
            raise ValueError("this site needs an election id and the registry has none")
        q["eid"] = m.group(1)
    if mode(entry) == "csv":
        q = {"text": "All", "type": typ, "map": mp, **({"eid": q["eid"]} if "eid" in q else {})}
    else:
        q = {"type": typ, "map": mp, **({"eid": q["eid"]} if "eid" in q else {})}
    return f"{u.scheme}://{u.netloc}{u.path}?" + urllib.parse.urlencode(q)


def types(entry):
    code = (entry.get("code") or "").upper()
    try:
        own = X.load(code).get("csv_types") or X.load(code).get("pages")
    except (OSError, ValueError):
        own = None
    return [tuple(t) for t in own] if own else TYPES.get(code, [])


def _get(src, url, entry, html_page):
    r = src.get(url, state=entry.get("code"), accept="text/html" if html_page else "text/csv,text/plain,*/*", small=True,
                expect_html=html_page)
    if r.refused:
        raise Refused(r.url, r.why)
    if not r.ok:
        raise SourceError(f"{r.status} from {r.url}")
    return r.body


# ============================================================================================== the reader's three steps

def check(src, entry):
    ts = types(entry)
    if not ts:
        return None
    try:
        url = address(entry, *ts[0])
    except ValueError:
        return None
    body = _get(src, url, entry, mode(entry) == "page")
    if mode(entry) == "csv":
        rows = csv_rows(body)
        if not rows:
            return None
        return {"version": fingerprint_csv(rows), "time": None}
    if ERROR_PAGE.search(body[:20000]) and b"display-results-box-a" not in body:
        return None                                      # nothing posted for this election yet (the site's error page)
    blocks = page_contests(body)
    if not blocks:
        return None
    return {"version": hashlib.sha256(repr(blocks).encode()).hexdigest()[:16], "time": None}


def fetch(src, entry, version):
    out = []
    for typ, mp in types(entry):
        url = address(entry, typ, mp)
        out.append((url, _get(src, url, entry, mode(entry) == "page")))
    return out


def discover(src, entry):
    """New Mexico's November id is expected to be 2917: is it open? Montana's is posted. Nebraska has no id."""
    code = (entry.get("code") or "").upper()
    eid = str((entry.get("election") or {}).get("nov3_id") or "")
    m = re.match(r"\s*(\d{3,12})", eid)
    if not m:
        return {"note": "this site holds one election at a time; no id to find"}
    try:
        got = check(src, entry)
    except SourceError as e:
        return {"note": f"the results site did not answer ({e})"}
    if got:
        return {"nov3_id": m.group(1), "note": "its contests are posted"}
    return {"note": f"election {m.group(1)} does not answer with contests yet ({code})"}


# ============================================================================================== CSV

def csv_rows(body):
    """The allowlisted columns of a resultsCSV export, one dict a line."""
    text = body.decode("utf-8-sig", "replace") if isinstance(body, (bytes, bytearray)) else str(body)
    rd = csv.reader(io.StringIO(text))
    head = next(rd, None)
    if not head or "RaceID" not in head:
        return []
    idx = {h: i for i, h in enumerate(head) if h in CSV_KEEP}
    return [{h: (row[i] if i < len(row) else "") for h, i in idx.items()} for row in rd if row and any(row)]


def fingerprint_csv(rows):
    return hashlib.sha256(repr([sorted(r.items()) for r in rows]).encode()).hexdigest()[:16]


def _num(s):
    s = str(s or "").strip().strip('="').replace(",", "")
    return int(s) if re.fullmatch(r"-?\d+", s) else 0


def _reporting(s):
    m = re.search(r"(\d+)\s*/\s*(\d+)", str(s or ""))
    return (int(m.group(1)), int(m.group(2))) if m else (None, None)


# ============================================================================================== pages

def _text(fragment):
    return X.tidy(html.unescape(re.sub(r"<[^>]+>", " ", fragment or "")))


def page_contests(body):
    """[{title, raceid, party, in, all, total, cands: [(name, party, votes)]}] from a results page, by its markup."""
    t = body.decode("utf-8", "replace") if isinstance(body, (bytes, bytearray)) else str(body)
    t = re.sub(r"<script\b.*?</script>", "", t, flags=re.S | re.I)
    parts = re.split(r'<div class="display-results-box-a">', t)[1:]
    out = []
    for p in parts:
        title = _text((re.search(r"<h1>(.*?)</h1>", p, re.S) or [None, ""])[1])
        rid = re.search(r'raceid="(\d+)"\s+party="([^"]*)"', p)
        rep = re.search(r"Precincts Fully:\s*([\d,]+)\s*/\s*([\d,]+)", p)
        cands = []
        for m in re.finditer(r'display-results-box-d">\s*<h1>(.*?)</h1>\s*<h2[^>]*>(.*?)</h2>.*?display-results-box-f">\s*<h1>([\d,]+)</h1>', p, re.S):
            cands.append((_text(m.group(1)), _text(m.group(2)), _num(m.group(3))))
        tot = re.search(r'display-results-box-total">\s*<h2>([\d,]+)</h2>', p)
        out.append({"title": title, "raceid": rid.group(1) if rid else None, "party": (rid.group(2) if rid else "").strip(),
                    "in": _num(rep.group(1)) if rep else None, "all": _num(rep.group(2)) if rep else None,
                    "total": _num(tot.group(1)) if tot else None, "cands": cands})
    return out


# ============================================================================================== reading

def read(files, entry, matcher=None):
    code = (entry.get("code") or "").upper()
    m = matcher or X.Matcher(code)
    reading = {"state": code, "feed": f"{code.lower()}-{FAMILY}", "contests": [], "unmatched": [], "problems": []}
    eid = re.match(r"\s*(\d+)", str((entry.get("election") or {}).get("nov3_id") or ""))
    known = (m.cw.get("elections") or {}).get(eid.group(1) if eid else "", {})
    primary = known.get("kind") == "primary"
    groups, seen = {}, {}
    any_file = False
    for name, body in files:
        b = body if isinstance(body, (bytes, bytearray)) else str(body).encode()
        rows = csv_rows(b) if b.lstrip()[:6] in (b"RaceID", b"\xef\xbb\xbfRac") else []
        if rows:
            any_file = True
            for r in rows:
                party = X.party_code(r.get("PartyCode")) if primary else None
                groups.setdefault((r["RaceID"], r.get("AreaNum", ""), party), []).append(r)
            continue
        if b"display-results-box" in b:
            any_file = True
            for c in page_contests(b):
                party = X.party_code(c["party"]) if c["party"] else None
                groups.setdefault((c["raceid"] or c["title"], "", party), []).append(c)
        elif ERROR_PAGE.search(b[:20000]):
            any_file = True                               # a type with nothing posted
    if not any_file:
        reading["problems"].append("none of the files is a results export or a results page")
        return reading
    for (race_key, area, party), items in sorted(groups.items(), key=lambda kv: str(kv[0])):
        is_csv = "RaceName" in items[0]
        title = X.tidy(items[0]["RaceName"] if is_csv else items[0]["title"])
        names = [X.tidy(i["CandidateName"]) for i in items] if is_csv else [c[0] for c in items[0]["cands"]]
        rid, why = m.resolve(title, district=area or None, names=names, party=party)
        key = f"{race_key}{'|' + area if area else ''}{'|' + party if party else ''}"
        if rid is None:
            reading["unmatched"].append({"key": key, "office": f"{title}{' ' + area if area else ''}", "why": why})
            continue
        if rid in seen:
            reading["unmatched"].append({"key": key, "office": title, "why": f"a second contest for {rid} (the first: {seen[rid]})"})
            continue
        seen[rid] = f"{title} {area}".strip()
        reading["contests"].append((_from_csv if is_csv else _from_page)(m, rid, key, title, items, reading["problems"]))
    return reading


def _from_csv(m, rid, key, title, rows, problems):
    ct = X.contest_base(m, rid, key, title)
    ct["seats"] = max(_num(r.get("VoteFor")) for r in rows) or 1
    choices, out = [], []
    for i, r in enumerate(rows, 1):
        line = m.choice(rid, r["CandidateName"], r.get("PartyCode") or None, order=i)
        if line["key"] in {c["key"] for c in choices}:
            line["key"] = f"{line['key']}-{i}"
        choices.append(line)
        v = _num(r.get("CandidateVotes"))
        out.append({"unit": "all", "choice": line["key"], "type": "total", "votes": v})
        typed = {vt: _num(r.get(col)) for col, vt in CSV_TYPES.items() if r.get(col, "") != ""}
        if typed:
            if sum(typed.values()) != v:
                problems.append(f"{title}, {line['name']}: absentee, early and election-day votes add to {sum(typed.values()):,}, the total is {v:,}")
            out.extend({"unit": "all", "choice": line["key"], "type": vt, "votes": n} for vt, n in typed.items())
    i_, a_ = _reporting(rows[0].get("PrecinctsReporting"))
    ct.update({"unit_kind": "race", "units_all": None, "choices": choices, "units": [dict(X.UNIT_ALL)], "rows": out,
               "reporting": [{"unit": "all", "in": i_, "all": a_, "ballots": None, "registered": None}], "stated": [], "controls": []})
    return ct


def _from_page(m, rid, key, title, items, problems):
    c = items[0]
    ct = X.contest_base(m, rid, key, title)
    choices, out = [], []
    for i, (name, party, votes) in enumerate(c["cands"], 1):
        line = m.choice(rid, name, party or None, order=i)
        if line["key"] in {x["key"] for x in choices}:
            line["key"] = f"{line['key']}-{i}"
        choices.append(line)
        out.append({"unit": "all", "choice": line["key"], "type": "total", "votes": votes})
    stated = [{"unit": "all", "total": c["total"]}] if c["total"] is not None else []
    ct.update({"unit_kind": "race", "units_all": None, "choices": choices, "units": [dict(X.UNIT_ALL)], "rows": out,
               "reporting": [{"unit": "all", "in": c["in"], "all": c["all"], "ballots": None, "registered": None}],
               "stated": stated, "controls": []})
    return ct


# ============================================================================================== checks

def selftest(say=print):
    """No network: New Mexico's June 2, 2026 primary export for federal contests (the file the ballot pages kept) and a
    Montana results page cut to its three U.S. Senate primaries read, tie to the 2026 races and add up."""
    ok = True

    def expect(cond, what):
        nonlocal ok
        ok = ok and bool(cond)
        say(f"  {'ok  ' if cond else 'FAIL'} {what}")

    nm = os.path.join(FIXTURE_DIR, "nm_2911_fed.csv")
    mt = os.path.join(FIXTURE_DIR, "mt_450002928_fed_senate.html")
    if not (os.path.exists(nm) and os.path.exists(mt)):
        say("  FAIL the fixture files are missing (election/fixtures/resultssw/)")
        return False
    from election import store
    cw = X.load("NM")
    cw = dict(cw, elections=dict(cw.get("elections") or {}, **{"2911": {"kind": "primary", "date": "2026-06-02"}}))
    r = read([("nm.csv", open(nm, "rb").read())], {"code": "NM", "election": {"nov3_id": "2911"}}, matcher=X.Matcher("NM", cw))
    ids = sorted(c["race_id"] for c in r["contests"])
    expect(not r["problems"], f"New Mexico's export reads ({'; '.join(r['problems'][:3])})")
    expect(ids == ["2026-NM-H01~DEM", "2026-NM-H01~REP", "2026-NM-H02~DEM", "2026-NM-H02~REP", "2026-NM-H03~DEM", "2026-NM-H03~REP",
                   "2026-NM-S2~DEM", "2026-NM-S2~REP"], f"eight party primaries tied ({', '.join(ids)})")
    s = next(c for c in r["contests"] if c["race_id"] == "2026-NM-S2~DEM")
    lu = next(ch for ch in s["choices"] if "LUJAN" in ch["name"])
    by = {x["type"]: x["votes"] for x in s["rows"] if x["choice"] == lu["key"]}
    expect(by.get("total") == 182360 and by.get("absentee", 0) + by.get("early", 0) + by.get("election_day", 0) == 182360,
           f"Lujan's 182,360 and his absentee, early and election-day votes ({by})")
    expect(all(p for n, p, _d in store.run_checks(store.connect(":memory:"), dict(r, state="NM", feed="nm-resultssw")) if n in store.HARD),
           "the store's checks pass (New Mexico)")
    r2 = read([("mt.html", open(mt, "rb").read())], {"code": "MT", "election": {"nov3_id": "450002928"}})
    ids2 = sorted(c["race_id"] for c in r2["contests"])
    expect(not r2["problems"] and ids2 == ["2026-MT-S2~DEM", "2026-MT-S2~LIB", "2026-MT-S2~REP"], f"Montana's page reads ({', '.join(ids2)})")
    rep = next(c for c in r2["contests"] if c["race_id"] == "2026-MT-S2~REP")
    expect(sum(x["votes"] for x in rep["rows"]) == rep["stated"][0]["total"] == 169062 and rep["reporting"][0]["all"] == 728,
           "Montana's Republican Senate primary adds to the page's own 169,062, with 728 of 728 precincts")
    expect(all(p for n, p, _d in store.run_checks(store.connect(":memory:"), dict(r2, state="MT", feed="mt-resultssw")) if n in store.HARD),
           "the store's checks pass (Montana)")
    say(f"  {'ok' if ok else 'FAIL'}: resultssw reader self-test")
    return ok


def make_fixture(say=print):
    import shutil
    from election import replay as R
    os.makedirs(FIXTURE_DIR, exist_ok=True)
    shutil.copyfile(os.path.join(HERE, "ballot_cache", "nm", "nm_2026_primary_results_federal.csv"), os.path.join(FIXTURE_DIR, "nm_2911_fed.csv"))
    page = None
    for p, b in R.load_final(os.path.join(R.REPLAY_SOURCES, "mt-450002928")).items():
        if "type=FED" in p:
            page = b.decode("utf-8", "replace")
    parts = re.split(r'(<div class="display-results-box-a">)', re.sub(r"<script\b.*?</script>", "", page, flags=re.S | re.I))
    keep = "".join(parts[i] + parts[i + 1] for i in range(1, len(parts), 2) if "UNITED STATES SENATOR" in parts[i + 1][:200])
    keep = re.sub(r"<a [^>]*>|</a>", "", keep)                       # links (share buttons) are not results
    with open(os.path.join(FIXTURE_DIR, "mt_450002928_fed_senate.html"), "w", encoding="utf-8") as fh:
        fh.write("<!-- Montana Secretary of State, June 2, 2026 primary, federal results page cut to the two U.S. Senate contests -->\n" + keep)
    say(f"fixture written to {os.path.relpath(FIXTURE_DIR, HERE)}")


def replay_check(code, eid, kind="primary", say=print, fetch_now=True):
    from election import registry
    from election import replay as R
    from election.source import Source
    code = code.upper()
    entry = dict(registry.load(code), code=code)
    entry["election"] = dict(entry.get("election") or {}, nov3_id=str(eid))
    cw = X.load(code)
    if str(eid) not in (cw.get("elections") or {}):
        say(f"{code}: election {eid} is not in the crosswalk's list of past elections")
        return None
    final = os.path.join(R.REPLAY_SOURCES, f"{code.lower()}-{eid}")
    if not os.path.isdir(final):
        if not fetch_now:
            return None
        src = Source()
        if not check(src, entry):
            say(f"{code}: election {eid} is not posted")
            return None
        R.save_final(fetch(src, entry, None), final)
    reading = read(list(R.load_final(final).items()), entry)
    return reading, *X.compare_primary(code, reading, say=say)


def posted(code, say=print):
    """The state's posted Nov 3 contests (zero counts) read and checked against the crosswalk."""
    from election import registry
    from election.source import Source
    code = code.upper()
    entry = dict(registry.load(code), code=code)
    src = Source()
    if not check(src, entry):
        say(f"{code}: nothing posted for Nov 3 yet")
        return None
    reading = read(fetch(src, entry, None), entry)
    if reading["problems"]:
        say(f"{code}: problems: {'; '.join(reading['problems'][:5])}")
    return X.check_posted(code, reading, (entry.get("election") or {}).get("nov3_id"), say=say)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--make-fixture", action="store_true")
    ap.add_argument("--replay", nargs=2, metavar=("CODE", "EID"))
    ap.add_argument("--posted", metavar="CODE")
    a = ap.parse_args(argv)
    if a.make_fixture:
        make_fixture()
    if a.selftest:
        return 0 if selftest() else 1
    if a.posted:
        return 0 if posted(a.posted) == [] else 1
    if a.replay:
        got = replay_check(*a.replay)
        if not got:
            return 1
        reading, equal, differ, missing = got
        print(f"{a.replay[0].upper()} {a.replay[1]}: {len(reading['contests'])} contests tied to races, {len(reading['unmatched'])} listed; "
              f"problems: {'; '.join(reading['problems'][:5]) or 'none'}")
        print(f"  certified primary totals: {len(equal)} races equal, {len(differ)} differ, {len(missing)} not in the feed")
        for k, sid, bad in differ:
            print(f"  DIFFER {k} ({sid}): " + "; ".join(bad[:4]))
        for k in missing:
            print(f"  MISSING {k}")
        return 0 if not differ else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
