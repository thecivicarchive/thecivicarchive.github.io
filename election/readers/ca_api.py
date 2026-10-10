"""election/readers/ca_api.py - California's results, from the Secretary of State's public returns service
(api.sos.ca.gov/returns/), which the Secretary's election-night pages read.

Calls made (every one through election/source.py; fields allowlisted):
  returns/governor                           the Governor's statewide figures: the cheap "what's new" look (its
                                             ReportingTime changes whenever a county reports)
  returns/<office>/county/all                each statewide office, statewide and then county by county: raceTitle,
        Reporting ("20.2% (4,817 of 23,860) precincts reporting"), ReportingTime, and each candidate's Name, Party, Votes
        (governor, lieutenant-governor, secretary-of-state, controller, treasurer, attorney-general, insurance-commissioner,
        superintendent-of-public-instruction)
  returns/us-rep/district/all, returns/state-senate/district/all, returns/state-assembly/district/all,
  returns/board-of-equalization/district/all  each district's figures, districtwide only
The service serves the current election only: it carries the November 3 contests now, with TEST numbers. A figure whose
ReportingTime is before 8 p.m. Pacific on November 3 is a test figure and the reading says so (the updater never
publishes one). The service has no split by how ballots were cast. California counts for weeks; the Secretary
certifies on the 38th day.

    python -m election.readers.ca_api --crosswalk     rebuild election/crosswalk/ca.json (asks the service for the district
                                                      lists it carries today: four requests)
    python -m election.readers.ca_api --replay        fetch the service's current figures once (today's test numbers),
                                                      read them, and check every statewide office's county rows against its
                                                      statewide line (the source's own totals; no past election is served)
    python -m election.readers.ca_api --selftest      the reader's test on its fixture (no network)
"""

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from election.readers import _common_n11 as K  # noqa: E402

STATE = "CA"
FAMILY = "ca_api"
FEED = "ca-ca_api"
API = "https://api.sos.ca.gov/returns/"
ACCEPT = "application/json, */*"
STATEWIDE = {"governor": "governor", "lieutenant-governor": "lieutenant_governor", "secretary-of-state": "secretary_of_state",
             "controller": "state_controller", "treasurer": "state_treasurer", "attorney-general": "attorney_general",
             "insurance-commissioner": "insurance_commissioner",
             "superintendent-of-public-instruction": "superintendent_of_public_instruction"}
DISTRICTS = {"us-rep": "us_house", "state-senate": "state_senate", "state-assembly": "state_house",
             "board-of-equalization": "board_of_equalization"}
FIRST_CLOSE = dt.datetime(2026, 11, 4, 4, 0, tzinfo=K.UTC)          # 8 p.m. Pacific Standard Time on November 3
REPLAY = "testfeed"
_LAST = {}


def paths():
    return [f"{o}/county/all" for o in STATEWIDE] + [f"{d}/district/all" for d in DISTRICTS]


def to_int(s):
    return int(re.sub(r"[^\d]", "", str(s or "")) or 0)


def reporting(s):
    m = re.search(r"\(([\d,]+) of ([\d,]+)\)", s or "")
    return (to_int(m.group(1)), to_int(m.group(2))) if m else (None, None)


def parse_time(s):
    """'October 9, 2026, 2:53 p.m.' (Pacific) as UTC."""
    t = re.sub(r"\s+", " ", (s or "").replace("a.m.", "AM").replace("p.m.", "PM").replace(".", "")).strip()
    for fmt in ("%B %d, %Y, %I:%M %p", "%B %d, %Y, %I %p"):
        try:
            return K.local_to_utc(dt.datetime.strptime(t, fmt), "America/Los_Angeles")
        except ValueError:
            continue
    return None


# ---------------------------------------------------------------------------------------------- requests


def check(src, entry):
    r = src.get(API + "governor", state=STATE, accept=ACCEPT)
    if r.status == 404 and not r.refused:
        return None
    body = K.body_ok(r, "the Governor's figures")
    d = json.loads(body.decode("utf-8-sig"))
    when = parse_time(d.get("ReportingTime"))
    return {"version": f"{d.get('ReportingTime')}|{hashlib.sha256(body).hexdigest()[:10]}", "time": K.iso(when)}


def discover(src, entry):
    """The service serves the current election: say what it carries now."""
    sig = check(src, entry)
    if not sig:
        return {"note": "the service did not answer for the Governor"}
    test = (K.parse_iso(sig.get("time")) or FIRST_CLOSE) < FIRST_CLOSE
    return {"nov3_id": "the current election (no id)", "note": f"the service carries the November 3 contests ({'test numbers' if test else 'figures'} as of {sig.get('time')})"}


def fetch(src, entry, version):
    out = []
    for p in paths():
        r = src.get(API + p, state=STATE, accept=ACCEPT)
        if r.ok:
            out.append((API + p, r.body))
        elif r.refused:
            K.body_ok(r, p)
    return out


# ---------------------------------------------------------------------------------------------- reading


def path_of(name):
    m = re.search(r"returns[/_]([a-z-]+)[/_](county|district)[/_]all", str(name).replace("\\", "/"))
    return (m.group(1), m.group(2)) if m else (None, None)


def read(files, entry):
    C = K.Contests(STATE, nov3=True)
    newest = None
    test = False
    for n, b in files:
        office, kind = path_of(n)
        if not office:
            continue
        try:
            items = json.loads(b.decode("utf-8-sig"))
        except ValueError:
            C.problems.append(f"{office}: the answer did not read as JSON")
            continue
        if isinstance(items, dict):
            items = [items]
        for it in items:
            title = re.sub(r"\s+", " ", it.get("raceTitle") or "").strip()
            when = parse_time(it.get("ReportingTime"))
            if when:
                newest = max(newest, when) if newest else when
                if when < FIRST_CLOSE:
                    test = True
            head, _, where = title.partition(" - ")
            if kind == "county":
                key = STATEWIDE.get(office)
                unit = "all" if where.startswith("Statewide") else None
                cname = re.sub(r"\s+County Results$", "", where).strip() if unit is None else None
            else:
                m = re.search(r"District (\d+)", head)
                key = f"{DISTRICTS[office]}:{int(m.group(1))}" if office in DISTRICTS and m else None
                unit, cname = "all", None
            rid = C.race_for(key, head, f"{office}|{head}")
            if not rid:
                continue
            c = C.contest(rid, f"{office}|{head}", head, rule="top_two")
            C.unit(c, "all", "race", "the whole contest")
            if unit is None:
                fips = K.county_unit(STATE, cname)
                if not fips:
                    C.problems.append(f"{head}: the county {cname!r} is not one of California's 58")
                    continue
                C.unit(c, fips, "county", cname, parent=STATE, map_id=fips)
                unit = fips
            for i, cd in enumerate(it.get("candidates") or []):
                party = cd.get("Party")
                ck = C.choice(c, cd.get("Name"), None if party in (None, "", "Non") else party, order=i + 1)
                C.row(c, unit, ck, to_int(cd.get("Votes")))
            i_, a_ = reporting(it.get("Reporting"))
            C.report(c, unit, i_, a_)
    for c in C.c.values():
        c["units_all"] = sum(1 for u in c["_units"].values() if u["kind"] == "county") or None
    sha = hashlib.sha256(b"".join(b for _n, b in files)).hexdigest()[:16]
    return C.reading(FEED, source_time=K.iso(newest), source_version=sha, test=test)


# ---------------------------------------------------------------------------------------------- rehearsals


def units(files):
    out = {}
    for n, b in dict(files).items():
        office, kind = path_of(n)
        if kind != "county":
            continue
        for it in json.loads(b.decode("utf-8-sig")):
            where = (it.get("raceTitle") or "").partition(" - ")[2]
            if where.endswith("County Results"):
                cn = re.sub(r"\s+County Results$", "", where).strip()
                out[cn] = out.get(cn, 0) + sum(to_int(cd.get("Votes")) for cd in it.get("candidates") or [])
    return [(c, K.county_unit(STATE, c) or "", v) for c, v in sorted(out.items())]


def reveal(files, keep, step):
    """County rows of counties not yet in at zero; each statewide line the sum of the counties in; each district's lines
    scaled by the share of counties in (the service gives districts no county rows, so a rehearsal can only scale them)."""
    files = dict(files)
    allc = {u[0] for u in units(files)}
    frac = len(keep & allc) / len(allc) if allc else 0
    out = {}
    for n, b in files.items():
        office, kind = path_of(n)
        if not office:
            out[n] = b
            continue
        items = json.loads(b.decode("utf-8-sig"))
        if kind == "county":
            tot, pin, pall = {}, 0, 0
            for it in items[1:]:
                cn = re.sub(r"\s+County Results$", "", (it.get("raceTitle") or "").partition(" - ")[2]).strip()
                i_, a_ = reporting(it.get("Reporting"))
                if cn not in keep:
                    for cd in it.get("candidates") or []:
                        cd["Votes"] = "0"
                    it["Reporting"] = f"0.0% (0 of {a_:,}) precincts reporting"
                    i_ = 0
                pin, pall = pin + (i_ or 0), pall + (a_ or 0)
                for cd in it.get("candidates") or []:
                    tot[cd["Name"]] = tot.get(cd["Name"], 0) + to_int(cd["Votes"])
            for cd in items[0].get("candidates") or []:
                cd["Votes"] = f"{tot.get(cd['Name'], 0):,}"
            items[0]["Reporting"] = f"{100 * pin / pall if pall else 0:.1f}% ({pin:,} of {pall:,}) precincts reporting"
        else:
            for it in items:
                for cd in it.get("candidates") or []:
                    cd["Votes"] = f"{round(to_int(cd['Votes']) * frac):,}"
                i_, a_ = reporting(it.get("Reporting"))
                if a_:
                    it["Reporting"] = f"{100 * frac:.1f}% ({round(a_ * frac):,} of {a_:,}) precincts reporting"
        out[n] = json.dumps(items).encode("utf-8")
    return out


# ---------------------------------------------------------------------------------------------- crosswalk, replay, self-test


def build_crosswalk(src=None, say=print):
    """The races in scope, and the district races the service carries today (its Nov 3 contests, with test numbers)."""
    from election.source import Source
    src = src or Source()
    posted = []
    for p in [f"{d}/district/all" for d in DISTRICTS] + list(STATEWIDE):
        items = json.loads(K.body_ok(src.get(API + p, state=STATE, accept=ACCEPT), p).decode("utf-8-sig"))
        for it in items if isinstance(items, list) else [items]:
            head = (it.get("raceTitle") or "").partition(" - ")[0].strip()
            office = p.split("/")[0]
            m = re.search(r"District (\d+)", head)
            key = STATEWIDE.get(office) or (f"{DISTRICTS[office]}:{int(m.group(1))}" if office in DISTRICTS and m else None)
            posted.append({"id": f"{office}|{head}", "title": head, "key": key, "names": [cd.get("Name") for cd in it.get("candidates") or []]})
    return K.build_crosswalk(STATE, "api.sos.ca.gov/returns (district/all and the statewide offices, as served on " + dt.date.today().isoformat() + ")", (
        "California's races on the November 3, 2026 ballot that the Election Night pages read (Congress from ballot_2026.sqlite; the "
        "statewide offices, the Board of Equalization and the Legislature from ballot_local_2026.sqlite), each with the key a contest "
        "of the Secretary's returns service is tied by (its office and district) and the candidates as filed; and the contests the "
        "service already carries for November 3 (with test numbers) tied to them. The Supreme Court and Court of Appeal retention "
        "votes are left out: the service's address for them was not found, so the pages link to the Secretary's own results."), feed_contests=posted, say=say,
        feed_note="The service serves the current election only; before 8 p.m. Pacific on November 3 its numbers are test numbers.",
        levels=("congress", "statewide", "legislature"))


def fixture_dir():
    return os.path.join(K.FIXTURE_DIR, "ca")


def replay(say=print, refetch=False):
    from election import replay as R
    from election.source import Source
    final = os.path.join(K.REPLAY_SOURCES, f"ca-{REPLAY}")
    if refetch or not os.path.isdir(final):
        src = Source()
        sig = check(src, {})
        R.save_final(fetch(src, {}, sig["version"]), final)
    files = list(R.load_final(final).items())
    return check_reading(read(files, {}), say)


def check_reading(rd, say, need_statewide=8, need_districts=150):
    ok = not rd["problems"]
    if rd["problems"]:
        say("  FAIL problems: " + "; ".join(rd["problems"][:5]))
    bad = sw = 0
    for c in rd["contests"]:
        if not any(u["kind"] == "county" for u in c["units"]):
            continue
        sw += 1
        whole, parts = {}, {}
        for r in c["rows"]:
            d = whole if r["unit"] == "all" else parts
            d[r["choice"]] = d.get(r["choice"], 0) + r["votes"]
        rep = {x["unit"]: x for x in c["reporting"]}
        p_in = sum(x["in"] or 0 for u, x in rep.items() if u != "all")
        if whole != parts or (rep.get("all") or {}).get("in") != p_in:
            bad += 1
            say(f"  FAIL {c['race_id']}: statewide {sum(whole.values()):,} against counties {sum(parts.values()):,}")
    dist = len(rd["contests"]) - sw
    ok = ok and not bad and sw >= need_statewide and dist >= need_districts
    say(f"  {'ok  ' if ok else 'FAIL'} California (the service's {'test' if rd.get('test') else 'live'} figures): {len(rd['contests'])} contests read "
        f"({sw} statewide with county rows, {dist} districts); each statewide line equal to its counties' sum, precincts too: {bad} differ; "
        f"{len(rd['unmatched'])} listed, not read; {len(rd['notes'])} notes")
    return ok


def make_fixture(say=print):
    """The service's test figures for the Governor (statewide and every county) and the 52 House districts."""
    from election import replay as R
    files = R.load_final(os.path.join(K.REPLAY_SOURCES, f"ca-{REPLAY}"))
    keep = {n: b for n, b in files.items() if path_of(n)[0] in ("governor", "us-rep")}
    fd = fixture_dir()
    for n, b in keep.items():
        p = os.path.join(fd, *n.split("/"))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "wb").write(b)
    say(f"  fixture written: {len(keep)} files in {fd}")


def selftest(say=print):
    from election import replay as R
    fd = fixture_dir()
    if not os.path.isdir(fd):
        say("  FAIL no fixture")
        return False
    files = R.load_final(fd)
    rd = read(list(files.items()), {})
    ok = check_reading(rd, say, need_statewide=1, need_districts=52) and rd.get("test") is True and not rd["notes"]
    us = units(files)
    rd2 = read(list(reveal(files, {us[0][0]}, 1).items()), {})
    ok2 = check_reading(rd2, lambda *_: None, need_statewide=1, need_districts=52)
    say(f"  {'ok  ' if ok2 else 'FAIL'} a rehearsal step with one county of {len(us)} in reads and adds up; test figures marked as test: {rd.get('test')}")
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
