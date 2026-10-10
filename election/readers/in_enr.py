"""election/readers/in_enr.py - Indiana's results, from the Election Division's election-night site
(enr.indianavoters.in.gov), which holds one election at a time and switches to the next in place.

What is asked, through election/source.py (the kit's honest User-Agent, one request at a time, a second apart):
  site/data/settings.json                         the cheap "what's new": the election the site holds
                                                  (CurrentElection, ElectionType), VersionCode, WriteTime, Certified
  site/data/statewideElectionsC_<type>.json       when the version changed: the office categories
  site/data/OffCatC_<category>_<type>.json        each category this site reads (U.S. Senator and Representative, the
                                                  statewide offices, State Senator and Representative): the statewide
                                                  totals of each race and its counties' totals
The files start with a byte-order mark. <type> is settings.json's VersionType.

What is kept (an allowlist; the files hold no contact detail): the election's date and kind, the version and its time,
the certified flag; each race's office id, title and number of seats; each candidate's name on the ballot, party and
votes, statewide and by county (FIPS). The site's own winner marks are never read. The site gives no count of precincts
reporting, so a race's reporting is left blank.

The site held the May 5, 2026 primary on 2026-10-10; its files were copied then into
election_cache/replay/sources/in-2026-05-05/ for rehearsals (the site will switch to November in place).

    python -m election.readers.in_enr --selftest
    python -m election.readers.in_enr --replay 2026-05-05      (reads the copy on disk; asks nothing)
"""

import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from election.readers import _n9_match as X  # noqa: E402
from election.source import Refused, SourceError  # noqa: E402

FAMILY = "in_enr"
FIXTURE_DIR = os.path.join(X.FIXTURES, "in_enr")
CATEGORIES = re.compile(r"^(US |U\.S\. |United States )|^Governor|^Lieutenant Governor|^Attorney General|^Secretary of State|"
                        r"^Auditor of State|^Treasurer of State|^Superintendent|^State Senator|^State Representative", re.I)


def data_root(entry):
    sig = (entry.get("cadence") or {}).get("signal") or ""
    m = re.match(r"(https://[^ ]+/)settings\.json$", sig)
    if not m:
        raise ValueError(f"the registry's signal address is not the Indiana settings file: {sig!r}")
    return m.group(1)


def wanted_date(entry):
    """The election to read, as the site writes it ('11/03/2026'), from the registry's nov3_id or a rehearsal's date."""
    v = str((entry.get("election") or {}).get("nov3_id") or "")
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", v) or re.search(r"(\d{4})-(\d{2})-(\d{2})", str((entry.get("election") or {}).get("date") or ""))
    return f"{m.group(2)}/{m.group(3)}/{m.group(1)}" if m else "11/03/2026"


def _doc(body):
    d = json.loads((body if isinstance(body, (bytes, bytearray)) else str(body).encode()).decode("utf-8-sig"))
    return d.get("Root", d) if isinstance(d, dict) else d


def _get(src, url, st):
    r = src.get(url, state=st, accept="application/json")
    if r.refused:
        raise Refused(r.url, r.why)
    if not r.ok:
        raise SourceError(f"{r.status} from {r.url}")
    try:
        return r.body, _doc(r.body)
    except ValueError as e:
        raise SourceError(f"{url} was not JSON ({e})") from e


def _list(x):
    return x if isinstance(x, list) else [x] if x else []


# ============================================================================================== the reader's three steps

def check(src, entry):
    _b, s = _get(src, data_root(entry) + "settings.json", entry.get("code"))
    if s.get("CurrentElection") != wanted_date(entry):
        return None                                    # the site still holds another election
    return {"version": f"{s.get('VersionCode')}-{s.get('VersionType')}", "time": s.get("WriteTime")}


def fetch(src, entry, version):
    root, st = data_root(entry), entry.get("code")
    out = []
    b, s = _get(src, root + "settings.json", st)
    out.append((root + "settings.json", b))
    vt = s.get("VersionType") or "A"
    b, cats = _get(src, root + f"statewideElectionsC_{vt}.json", st)
    out.append((root + f"statewideElectionsC_{vt}.json", b))
    for cid, _name in categories(cats, entry):
        url = root + f"OffCatC_{cid}_{vt}.json"
        b, _d = _get(src, url, st)
        out.append((url, b))
    return out


def categories(cats, entry=None):
    """[(category id, name)] of the office categories this site reads."""
    own = None
    try:
        own = X.load((entry or {}).get("code") or "IN").get("categories")
    except (OSError, ValueError):
        pass
    out = []
    for grp in _list(cats.get("List")):
        for it in _list((grp.get("Items") or {}).get("Item")):
            name = it.get("OFFICE_CATEGORY_NAME") or ""
            if (own and name in own) or (not own and CATEGORIES.search(name)):
                out.append((str(it.get("OFFICECATEGORYID")), name))
    return out


def discover(src, entry):
    _b, s = _get(src, data_root(entry) + "settings.json", entry.get("code"))
    if s.get("CurrentElection") == "11/03/2026":
        return {"nov3_id": "2026-11-03", "note": "the site holds the November 3 election"}
    return {"note": f"the site still holds the election of {s.get('CurrentElection')} (type {s.get('ElectionType')})"}


# ============================================================================================== reading

def read(files, entry, matcher=None):
    code = (entry.get("code") or "IN").upper()
    m = matcher or X.Matcher(code)
    reading = {"state": code, "feed": f"{code.lower()}-{FAMILY}", "contests": [], "unmatched": [], "problems": []}
    settings, offices = None, []
    for _n, body in files:
        try:
            d = _doc(body)
        except ValueError:
            continue
        if isinstance(d, dict) and "CurrentElection" in d:
            settings = d
        elif isinstance(d, dict) and "StatewideSummary" in d:
            offices.append(d)
    if not settings or not offices:
        reading["problems"].append("settings.json or the office files are missing")
        return reading
    reading["source_time"] = _utc(settings.get("WriteTime"))
    reading["source_version"] = settings.get("VersionCode")
    reading["official"] = settings.get("Certified") == "T"
    if settings.get("CurrentElection") != wanted_date(entry):
        reading["problems"].append(f"the site holds the election of {settings.get('CurrentElection')}, not {wanted_date(entry)}")
    primary = settings.get("ElectionType") == "P"
    parties = {p.get("POLITICALPARTYID"): p for p in _list((settings.get("PolParties") or {}).get("PolParty"))}
    seen = {}
    for d in offices:
        cat = (d.get("OfficeCategory") or {}).get("OFFICE_CATEGORY_NAME")
        counties = {}                                       # office id -> {fips: [candidate rows]}
        for reg in _list(((d.get("OfficeCategory") or {}).get("Regions") or {}).get("Region")):
            for race in _list((reg.get("Races") or {}).get("Race")):
                fips = str(((race.get("Jurisdiction") or {}).get("FIPS")) or "")
                if re.fullmatch(r"18\d{3}", fips):
                    counties.setdefault(str(race.get("OFFICEID")), {}).setdefault(fips, []).extend(_list((race.get("Candidates") or {}).get("Candidate")))
        for race in _list((d.get("StatewideSummary") or {}).get("Race")):
            oid, title = str(race.get("OFFICEID")), X.tidy(race.get("OFFICE_TITLE"))
            cands = _list((race.get("Candidates") or {}).get("Candidate"))
            groups = {}
            for c in cands:
                p = parties.get(c.get("POLITICALPARTYID"), {})
                code_p = X.party_code(p.get("PARTY_NAME") or c.get("PARTY")) if primary else None
                groups.setdefault(code_p, []).append(c)
            for party, cs in sorted(groups.items(), key=lambda kv: str(kv[0])):
                rid, why = m.resolve(title, names=[c.get("NAME_ON_BALLOT") for c in cs], party=party)
                key = f"{oid}{'|' + party if party else ''}"
                if rid is None:
                    reading["unmatched"].append({"key": key, "office": f"{title}{' (' + party + ')' if party else ''}", "why": why})
                    continue
                if rid in seen:
                    reading["unmatched"].append({"key": key, "office": title, "why": f"a second contest for {rid} (the first: {seen[rid]})"})
                    continue
                seen[rid] = title
                reading["contests"].append(_contest(m, code, rid, key, title, race, cs, parties, counties.get(oid, {}), reading["problems"], cat))
    return reading


def _utc(t):
    """'2026-09-27T15:49:51.483' (Indianapolis time) -> UTC."""
    import datetime as dt
    mt = re.match(r"(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})", t or "")
    if not mt:
        return None
    local = dt.datetime(*map(int, mt.groups()))

    def sunday(y, mo, nth):
        d = dt.date(y, mo, 1)
        return d + dt.timedelta(days=(6 - d.weekday()) % 7 + 7 * (nth - 1))

    y = local.year
    summer = dt.datetime.combine(sunday(y, 3, 2), dt.time(2)) <= local < dt.datetime.combine(sunday(y, 11, 1), dt.time(2))
    return (local + dt.timedelta(hours=4 if summer else 5)).strftime("%Y-%m-%dT%H:%M:%SZ")     # Indiana's Eastern time


def _ckey(c):
    return (X.tidy(c.get("NAME_ON_BALLOT")).lower(), c.get("POLITICALPARTYID"))


def _contest(m, code, rid, key, title, race, cs, parties, by_county, problems, cat):
    ct = X.contest_base(m, rid, key, title)
    ct["seats"] = int(race.get("NumofSeats") or 1)
    choices, keys = [], {}
    for i, c in enumerate(sorted(cs, key=lambda c: int(c.get("SORT_ORDER") or 99)), 1):
        p = parties.get(c.get("POLITICALPARTYID"), {})
        line = m.choice(rid, c.get("NAME_ON_BALLOT"), p.get("PARTY_NAME") or c.get("PARTY"), order=i)
        if line["key"] in keys.values():
            line["key"] = f"{line['key']}-{c.get('POLITICALPARTYID')}"
        keys[_ckey(c)] = line["key"]
        choices.append(line)
    units = {"all": dict(X.UNIT_ALL)}
    rows = [{"unit": "all", "choice": keys[_ckey(c)], "type": "total", "votes": int(c.get("TOTAL") or 0)} for c in cs]
    sums = {}
    for fips, lines in sorted(by_county.items()):
        got = False
        for c in lines:
            k = keys.get(_ckey(c))
            if k is None:
                continue                                  # another party's line in a primary, or another race's
            got = True
            v = int(c.get("TOTAL_VOTES") or 0)
            sums[k] = sums.get(k, 0) + v
            rows.append({"unit": fips, "choice": k, "type": "total", "votes": v})
        if got:
            units[fips] = X.unit_county(code, fips)
    if by_county:
        for r in rows:
            if r["unit"] == "all" and sums.get(r["choice"], 0) != r["votes"]:
                problems.append(f"{title}: the counties add to {sums.get(r['choice'], 0):,} for {r['choice']}, the statewide total is {r['votes']:,}")
    ct.update({"unit_kind": "county" if len(units) > 1 else "race", "units_all": (len(units) - 1) or None, "choices": choices,
               "units": list(units.values()), "rows": rows,
               "reporting": [{"unit": "all", "in": None, "all": None, "ballots": None, "registered": None}], "stated": [], "controls": []})
    return ct


# ============================================================================================== rehearsals

def units(files):
    """[(county FIPS, county FIPS, votes cast in its races)]."""
    size = {}
    for _p, body in files.items():
        try:
            d = _doc(body)
        except ValueError:
            continue
        if not isinstance(d, dict) or "OfficeCategory" not in d:
            continue
        for reg in _list((d["OfficeCategory"].get("Regions") or {}).get("Region")):
            for race in _list((reg.get("Races") or {}).get("Race")):
                f = str(((race.get("Jurisdiction") or {}).get("FIPS")) or "")
                size[f] = size.get(f, 0) + sum(int(c.get("TOTAL_VOTES") or 0) for c in _list((race.get("Candidates") or {}).get("Candidate")))
    return [(f, f, v) for f, v in sorted(size.items()) if f]


def reveal(files, keep, step):
    """The final files with only the counties in `keep` counted (statewide totals made from them), a new version."""
    out = {}
    for path, body in files.items():
        try:
            d = _doc(body)
        except ValueError:
            out[path] = body
            continue
        if isinstance(d, dict) and "CurrentElection" in d:
            d["VersionCode"] = f"{d.get('VersionCode')}-r{step:03d}"
            d["WriteTime"] = ""                     # a rehearsal's figures carry the time they are read
        if isinstance(d, dict) and "OfficeCategory" in d:
            tot = {}
            for reg in _list((d["OfficeCategory"].get("Regions") or {}).get("Region")):
                for race in _list((reg.get("Races") or {}).get("Race")):
                    f = str(((race.get("Jurisdiction") or {}).get("FIPS")) or "")
                    for c in _list((race.get("Candidates") or {}).get("Candidate")):
                        if f not in keep:
                            c["TOTAL_VOTES"] = 0
                        k = (str(race.get("OFFICEID")), X.tidy(c.get("NAME_ON_BALLOT")).lower(), c.get("POLITICALPARTYID"))
                        tot[k] = tot.get(k, 0) + int(c.get("TOTAL_VOTES") or 0)
            for race in _list((d.get("StatewideSummary") or {}).get("Race")):
                for c in _list((race.get("Candidates") or {}).get("Candidate")):
                    c["TOTAL"] = tot.get((str(race.get("OFFICEID")), X.tidy(c.get("NAME_ON_BALLOT")).lower(), c.get("POLITICALPARTYID")), 0)
        out[path] = json.dumps({"Root": d}).encode()
    return out


# ============================================================================================== checks

def selftest(say=print):
    """No network: the May 5, 2026 primary's U.S. Representative file (districts 1 to 3, cut from the copy kept on
    2026-10-10) reads, splits each race by party, adds up by county, and a rehearsal step reads too."""
    ok = True

    def expect(cond, what):
        nonlocal ok
        ok = ok and bool(cond)
        say(f"  {'ok  ' if cond else 'FAIL'} {what}")

    names = ("settings.json", "OffCatC_1005_A.json")
    if not all(os.path.exists(os.path.join(FIXTURE_DIR, n)) for n in names):
        say("  FAIL the fixture files are missing (election/fixtures/in_enr/)")
        return False
    files = {n: open(os.path.join(FIXTURE_DIR, n), "rb").read() for n in names}
    entry = {"code": "IN", "election": {"nov3_id": "2026-05-05"}}
    r = read(list(files.items()), entry)
    ids = sorted(c["race_id"] for c in r["contests"])
    expect(not r["problems"], f"the fixture reads with no problem ({'; '.join(r['problems'][:3])})")
    expect(ids == ["2026-IN-H01~DEM", "2026-IN-H01~REP", "2026-IN-H02~DEM", "2026-IN-H02~REP", "2026-IN-H03~DEM", "2026-IN-H03~REP"],
           f"six party primaries tied ({', '.join(ids)})")
    h = next(c for c in r["contests"] if c["race_id"] == "2026-IN-H01~DEM")
    mv = next(ch for ch in h["choices"] if "Mrvan" in ch["name"])
    tot = next(x["votes"] for x in h["rows"] if x["unit"] == "all" and x["choice"] == mv["key"])
    cty = sum(x["votes"] for x in h["rows"] if x["unit"] != "all" and x["choice"] == mv["key"])
    expect(tot == 42519 and cty == tot, f"Mrvan's 42,519 equal his counties' sum ({cty:,})")
    from election import store
    checks = store.run_checks(store.connect(":memory:"), dict(r, state="IN", feed="in-in_enr"))
    expect(all(p for n, p, _d in checks if n in store.HARD), "the store's checks pass")
    us = units(files)
    keep = {u[0] for u in us[::2]}
    r2 = read(list(reveal(files, keep, 2).items()), entry)
    h2 = next(c for c in r2["contests"] if c["race_id"] == "2026-IN-H01~DEM")
    tot2 = next(x["votes"] for x in h2["rows"] if x["unit"] == "all" and x["choice"] == mv["key"])
    expect(not r2["problems"] and tot2 < tot, f"a rehearsal step with {len(keep)} of {len(us)} counties adds up ({tot2:,})")
    say(f"  {'ok' if ok else 'FAIL'}: in_enr reader self-test")
    return ok


def make_fixture(say=print):
    from election import replay as R
    base = os.path.join(R.REPLAY_SOURCES, "in-2026-05-05", "enr.indianavoters.in.gov", "site", "data")
    os.makedirs(FIXTURE_DIR, exist_ok=True)
    s = _doc(open(os.path.join(base, "settings.json"), "rb").read())
    with open(os.path.join(FIXTURE_DIR, "settings.json"), "w", encoding="utf-8") as fh:
        json.dump({"Root": s}, fh, indent=0)
    d = _doc(open(os.path.join(base, "OffCatC_1005_A.json"), "rb").read())
    keep = {"United States Representative, First District", "United States Representative, Second District",
            "United States Representative, Third District"}
    d["StatewideSummary"]["Race"] = [r for r in _list(d["StatewideSummary"]["Race"]) if r.get("OFFICE_TITLE") in keep]
    oc = d["OfficeCategory"]
    oc.pop("OFFICE_CATEGORY_DESCRIPTION", None)
    oc["Regions"]["Region"] = [g for g in _list(oc["Regions"]["Region"]) if (g.get("RegionSummary") or {}).get("Race", {}).get("OFFICE_TITLE") in keep]
    with open(os.path.join(FIXTURE_DIR, "OffCatC_1005_A.json"), "w", encoding="utf-8") as fh:
        json.dump({"Root": d}, fh, indent=0)
    say(f"fixture written to {os.path.relpath(FIXTURE_DIR, HERE)}")


def replay_check(day="2026-05-05", say=print):
    from election import registry
    from election import replay as R
    entry = dict(registry.load("IN"), code="IN")
    entry["election"] = dict(entry.get("election") or {}, nov3_id=day)
    final = os.path.join(R.REPLAY_SOURCES, f"in-{day}")
    if not os.path.isdir(final):
        say(f"IN: no copy of {day} on disk")
        return None
    reading = read(list(R.load_final(final).items()), entry)
    return reading, *X.compare_primary("IN", reading, say=say)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--make-fixture", action="store_true")
    ap.add_argument("--replay", metavar="DATE")
    a = ap.parse_args(argv)
    if a.make_fixture:
        make_fixture()
    if a.selftest:
        return 0 if selftest() else 1
    if a.replay:
        got = replay_check(a.replay)
        if not got:
            return 1
        reading, equal, differ, missing = got
        print(f"IN {a.replay}: {len(reading['contests'])} contests tied to races, {len(reading['unmatched'])} listed; certified flag: "
              f"{reading.get('official')}; problems: {'; '.join(reading['problems'][:5]) or 'none'}")
        print(f"  certified primary totals: {len(equal)} races equal, {len(differ)} differ, {len(missing)} not in the feed")
        for k, sid, bad in differ:
            print(f"  DIFFER {k} ({sid}): " + "; ".join(bad[:4]))
        for k in missing:
            print(f"  MISSING {k}")
        return 0 if not differ else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
