"""election/readers/nc_sbe.py - North Carolina's results, from the State Board of Elections' results site (er.ncsbe.gov),
whose data are plain JSON text files.

Files read (every one through election/source.py; fields allowlisted):
  enr/<yyyymmdd>/data/county.txt      each county's title ("11/05/2024 OFFICIAL GENERAL ELECTION RESULTS - ALAMANCE"),
                                      precincts reporting and in all, and the time its last upload was taken in (imp);
                                      the row with cid 0 is the state. The cheap "what's new" look asks for it.
  enr/<yyyymmdd>/data/results_0.txt   every contest's statewide lines: contest name, ballot name, party, votes, precincts
                                      reporting and in all, and the votes by how they were cast: evc (Election Day),
                                      ovc (one-stop, North Carolina's early voting in person), avc (absentee by mail),
                                      pvc (provisional)
  enr/<yyyymmdd>/data/results_<cid>.txt   the same for one county (cid 1 to 100, alphabetical)
A county's file is asked for only when its row in county.txt changed (at most COUNTY_BATCH a cycle on the night, the
rest on the next cycles), so a quiet county costs nothing.

The Board's titles say UNOFFICIAL on the night and OFFICIAL once the county canvasses are done; the figures are "as
reported" until the State Board certifies.

    python -m election.readers.nc_sbe --crosswalk     rebuild election/crosswalk/nc.json (one request: the Nov 3 statewide file)
    python -m election.readers.nc_sbe --replay        fetch the 2024 general once (101 files, politely), read it and check
                                                      it against the Board's own official figures
    python -m election.readers.nc_sbe --selftest      the reader's test on its fixture (no network)
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

STATE = "NC"
FAMILY = "nc_sbe"
FEED = "nc-nc_sbe"
BASE = "https://er.ncsbe.gov/enr/"
NOV3_FOLDER = "20261103"
REPLAY_FOLDER = "20241105"
ACCEPT = "application/json, text/plain, */*"
COUNTY_BATCH = 40
VOTE_TYPES = (("evc", "election_day"), ("ovc", "early"), ("avc", "mail"), ("pvc", "provisional"))
KEEP = ("cid", "cnm", "bnm", "pty", "vct", "prt", "ptl", "evc", "ovc", "avc", "pvc", "dtx", "vfr", "gid")
_LAST = {}          # folder -> county.txt body from the last look
_SEEN = {}          # folder -> {cid: (prt, imp)} of the county files already fetched


def folder_of(entry):
    ids = K.election_ids(entry, r"\d{8}")
    return ids[0] if ids else NOV3_FOLDER


def key_of(title):
    t = re.sub(r"\s*\(VOTE FOR \d+\)\s*$", "", re.sub(r"\s+", " ", title or "").strip().upper())
    unexp = "(UNEXPIRED)" in t
    t = t.replace("(UNEXPIRED)", "").strip()
    if t == "US SENATE":
        return "us_senate:special" if unexp else "us_senate"
    m = re.fullmatch(r"US HOUSE OF REPRESENTATIVES DISTRICT (\d+)", t)
    if m:
        return f"us_house:{int(m.group(1))}"
    m = re.fullmatch(r"NC STATE SENATE DISTRICT (\d+)", t)
    if m:
        return f"state_senate:{int(m.group(1))}"
    m = re.fullmatch(r"NC HOUSE OF REPRESENTATIVES DISTRICT (\d+)", t)
    if m:
        return f"state_house:{int(m.group(1))}"
    m = re.fullmatch(r"NC SUPREME COURT (?:CHIEF JUSTICE|ASSOCIATE JUSTICE) SEAT (\d+)", t)
    if m:
        return f"supreme_court:{int(m.group(1))}" + (":unexpired" if unexp else "")
    m = re.fullmatch(r"NC COURT OF APPEALS JUDGE SEAT (\d+)", t)
    if m:
        return f"court_of_appeals::seat {int(m.group(1))}" + (":unexpired" if unexp else "")
    words = {"NC GOVERNOR": "governor", "NC LIEUTENANT GOVERNOR": "lieutenant_governor", "NC ATTORNEY GENERAL": "attorney_general",
             "NC SECRETARY OF STATE": "secretary_of_state", "NC TREASURER": "state_treasurer", "NC AUDITOR": "state_auditor",
             "NC COMMISSIONER OF AGRICULTURE": "agriculture_commissioner", "NC COMMISSIONER OF INSURANCE": "insurance_commissioner",
             "NC COMMISSIONER OF LABOR": "labor_commissioner", "NC SUPERINTENDENT OF PUBLIC INSTRUCTION": "superintendent_of_public_instruction"}
    return words.get(t)


def _rows(body):
    return [{k: r.get(k) for k in KEEP} for r in json.loads(body.decode("utf-8-sig"))]


def _counties(body):
    return [{k: c.get(k) for k in ("cid", "cnm", "tle", "prt", "ptl", "imp")} for c in json.loads(body.decode("utf-8-sig"))]


# ---------------------------------------------------------------------------------------------- requests


def _pending(folder, rows):
    seen = _SEEN.get(folder, {})
    return [c for c in rows if c["cid"] != "0" and seen.get(c["cid"]) != (c["prt"], c["imp"])]


def check(src, entry):
    folder = folder_of(entry)
    r = src.get(BASE + f"{folder}/data/county.txt", state=STATE, accept=ACCEPT)
    if r.status in (403, 404) and not r.refused:
        return None
    body = K.body_ok(r, "the county file")
    _LAST[folder] = body
    rows = _counties(body)
    state = next((c for c in rows if c["cid"] == "0"), {})
    when = parse_imp(state.get("imp"))
    left = len(_pending(folder, rows))
    return {"version": hashlib.sha256(body).hexdigest()[:16] + f":{left}", "time": K.iso(when)}


def discover(src, entry):
    """The Board's list of elections (elections.txt): whether November 3 is there."""
    rows = json.loads(K.body_ok(src.get(BASE + "elections.txt", state=STATE, accept=ACCEPT), "the list of elections").decode("utf-8-sig"))
    if any(r.get("edt") == "11/03/2026" for r in rows):
        return {"nov3_id": "20261103 (listed in elections.txt)", "note": "listed"}
    return {"note": "elections.txt does not list 11/03/2026"}


def fetch(src, entry, version):
    folder = folder_of(entry)
    body = _LAST.pop(folder, None)
    if body is None:
        body = K.body_ok(src.get(BASE + f"{folder}/data/county.txt", state=STATE, accept=ACCEPT), "the county file")
    out = [(BASE + f"{folder}/data/county.txt", body)]
    out.append((BASE + f"{folder}/data/results_0.txt",
                K.body_ok(src.get(BASE + f"{folder}/data/results_0.txt", state=STATE, accept=ACCEPT), "the statewide file")))
    rows = _counties(body)
    todo = _pending(folder, rows)
    if folder == NOV3_FOLDER:
        todo = sorted(todo, key=lambda c: -int(c.get("prt") or 0))[:COUNTY_BATCH]
    seen = _SEEN.setdefault(folder, {})
    for c in todo:
        r = src.get(BASE + f"{folder}/data/results_{c['cid']}.txt", state=STATE, accept=ACCEPT)
        if r.ok:
            out.append((BASE + f"{folder}/data/results_{c['cid']}.txt", r.body))
            seen[c["cid"]] = (c["prt"], c["imp"])
        elif r.refused:
            K.body_ok(r, "a county file")
    return out


def parse_imp(s):
    """'December 4, 2024 8:59 pm' (Eastern) as UTC."""
    try:
        t = dt.datetime.strptime(re.sub(r"\s+", " ", s or "").strip(), "%B %d, %Y %I:%M %p")
    except ValueError:
        return None
    return K.local_to_utc(t, "America/New_York")


# ---------------------------------------------------------------------------------------------- reading


def folder_in(files):
    for n, _b in files:
        m = re.search(r"(\d{8})/data/county\.txt|(\d{8})_data_county\.txt|enr/(\d{8})/", str(n).replace("\\", "/"))
        if m:
            return next(g for g in m.groups() if g)
    return None


def read(files, entry):
    folder = folder_in(files) or folder_of(entry)
    C = K.Contests(STATE, nov3=(folder == NOV3_FOLDER))
    _n, cb = K.file_named(files, "county.txt")
    _n, sb = K.file_named(files, "results_0.txt")
    if cb is None or sb is None:
        C.problems.append("the county file or the statewide file is missing")
        return C.reading(FEED)
    try:
        crow = _counties(cb)
        state_rows = _rows(sb)
    except (ValueError, AttributeError) as e:
        C.problems.append(f"a file did not read as the Board's JSON ({e.__class__.__name__})")
        return C.reading(FEED)
    cname = {c["cid"]: c["cnm"] for c in crow}
    st = next((c for c in crow if c["cid"] == "0"), {})
    official = "OFFICIAL" in (st.get("tle") or "").upper() and "UNOFFICIAL" not in (st.get("tle") or "").upper()

    def take(rows, unit):
        for r in rows:
            title = re.sub(r"\s+", " ", r.get("cnm") or "").strip()
            key = key_of(title)
            rid = C.race_for(key, title, r.get("gid") or title) if unit == "all" else (C.keys.get(key) if key else None)
            if not rid:
                continue
            if unit != "all" and rid not in C.c:
                continue                                    # a contest the statewide file did not carry this time
            c = C.contest(rid, r.get("gid") or title, title.title(), seats=int(r.get("vfr") or 1))
            if unit == "all":
                C.unit(c, "all", "race", "the whole contest")
            ck = C.choice(c, r.get("bnm"), r.get("pty") or None, write_in=bool(re.search(r"write[- ]?in", (r.get("bnm") or "") + (r.get("dtx") or ""), re.I)))
            C.row(c, unit, ck, int(r.get("vct") or 0))
            parts = 0
            for f, vt in VOTE_TYPES:
                if r.get(f) not in (None, ""):
                    C.row(c, unit, ck, int(r[f]), vt)
                    parts += int(r[f])
            if parts and parts != int(r.get("vct") or 0):
                C.problems.append(f"{rid} {unit} {r.get('bnm')}: its votes by how they were cast add to {parts:,}, the total says {r.get('vct')}")
            c.setdefault("_rep", {})[unit] = (r.get("prt"), r.get("ptl"))

    take(state_rows, "all")
    seen_counties = 0
    for n, b in files:
        m = re.search(r"results_(\d+)\.txt$", str(n))
        if not m or m.group(1) == "0":
            continue
        cid = m.group(1)
        fips = K.county_unit(STATE, cname.get(cid))
        if not fips:
            C.problems.append(f"county {cid} ({cname.get(cid)}) is not one of North Carolina's 100")
            continue
        try:
            rows = _rows(b)
        except ValueError:
            C.problems.append(f"county {cid}'s file did not read")
            continue
        seen_counties += 1
        before = {rid: len(c["rows"]) for rid, c in C.c.items()}
        take(rows, fips)
        for rid, c in C.c.items():
            if len(c["rows"]) > before.get(rid, 0):
                C.unit(c, fips, "county", (cname.get(cid) or "").title(), parent=STATE, map_id=fips)
    for c in C.c.values():
        for unit, (i, a) in c.pop("_rep", {}).items():
            C.report(c, unit, i, a)
        c["units_all"] = sum(1 for u in c["_units"].values() if u["kind"] == "county") or None
    if official:
        C.notes.append("the Board's titles say OFFICIAL")
    rd = C.reading(FEED, source_time=K.iso(parse_imp(st.get("imp"))), source_version=hashlib.sha256(cb).hexdigest()[:16])
    rd["official_title"] = st.get("tle")
    return rd


# ---------------------------------------------------------------------------------------------- rehearsals


def units(files):
    """[(county id, county code, size)]: every county with a file, sized by its ballots."""
    _n, cb = K.file_named(files.items() if isinstance(files, dict) else files, "county.txt")
    out = []
    for c in json.loads(cb.decode("utf-8-sig")):
        if c.get("cid") != "0":
            out.append((c["cid"], K.county_unit(STATE, c.get("cnm")) or "", int(c.get("bct") or 0)))
    return out


def reveal(files, keep, step):
    """The files as they would have stood with only the kept counties in: a county not yet in reports nothing (its
    lines at 0, its precincts at 0), and the statewide lines are the sums of the counties' (precincts too)."""
    files = dict(files)
    out = {}
    cfile = next(n for n in files if n.endswith("county.txt"))
    crows = json.loads(files[cfile].decode("utf-8-sig"))
    sums, prt = {}, {}
    for n, b in files.items():
        m = re.search(r"results_(\d+)\.txt$", n)
        if not m or m.group(1) == "0":
            continue
        rows = json.loads(b.decode("utf-8-sig"))
        on = m.group(1) in keep
        for r in rows:
            if not on:
                for f in ("vct", "evc", "ovc", "avc", "pvc", "prt"):
                    if f in r:
                        r[f] = "0"
            k = (r.get("cnm"), r.get("bnm"))
            s = sums.setdefault(k, {f: 0 for f in ("vct", "evc", "ovc", "avc", "pvc")})
            for f in s:
                s[f] += int(r.get(f) or 0)
            prt.setdefault(r.get("cnm"), {})[m.group(1)] = int(r.get("prt") or 0)
        out[n] = json.dumps(rows).encode("utf-8")
    sfile = next(n for n in files if n.endswith("results_0.txt"))
    srows = json.loads(files[sfile].decode("utf-8-sig"))
    for r in srows:
        s = sums.get((r.get("cnm"), r.get("bnm")))
        if s:
            for f, v in s.items():
                r[f] = str(v)
            r["prt"] = str(sum(prt.get(r.get("cnm"), {}).values()))
    out[sfile] = json.dumps(srows).encode("utf-8")
    for c in crows:
        if c.get("cid") != "0" and c["cid"] not in keep:
            c["prt"] = "0"
            c["tle"] = (c.get("tle") or "").replace("OFFICIAL", "UNOFFICIAL").replace("UNUNOFFICIAL", "UNOFFICIAL")
    st = next(c for c in crows if c.get("cid") == "0")
    st["prt"] = str(sum(int(c.get("prt") or 0) for c in crows if c.get("cid") != "0"))
    st["imp"] = f"step {step}"
    out[cfile] = json.dumps(crows).encode("utf-8")
    for n, b in files.items():
        out.setdefault(n, b)
    return out


# ---------------------------------------------------------------------------------------------- crosswalk, replay, self-test


def build_crosswalk(src=None, say=print):
    from election.source import Source
    src = src or Source()
    body = K.body_ok(src.get(BASE + f"{NOV3_FOLDER}/data/results_0.txt", state=STATE, accept=ACCEPT), "the statewide file")
    by = {}
    for r in _rows(body):
        t = re.sub(r"\s+", " ", r.get("cnm") or "").strip()
        by.setdefault((r.get("gid"), t), []).append(r.get("bnm"))
    posted = [{"id": g or t, "title": t, "key": key_of(t), "names": [n for n in names if n]} for (g, t), names in by.items()]
    return K.build_crosswalk(STATE, "er.ncsbe.gov enr/20261103/data/results_0.txt", (
        "North Carolina's races on the November 3, 2026 ballot that the Election Night pages read (Congress from ballot_2026.sqlite; "
        "the Legislature, the Supreme Court and the Court of Appeals from ballot_local_2026.sqlite; no statewide executive office "
        "is elected in 2026), each with the key a contest of the State Board's results files is tied by (read from its name) and the "
        "candidates as filed; and the Board's posted Nov 3 statewide file, already carrying every contest at zero, tied to them."),
        feed_contests=posted, say=say,
        feed_note="The Board posts the November 3 contests with zero votes weeks ahead; a race with one candidate is still printed.")


def fixture_dir():
    return os.path.join(K.FIXTURE_DIR, "nc")


def replay(say=print, refetch=False):
    from election import replay as R
    from election.source import Source
    final = os.path.join(K.REPLAY_SOURCES, f"nc-{REPLAY_FOLDER}")
    entry = {"election": {"nov3_id": REPLAY_FOLDER}}
    if refetch or not os.path.isdir(final):
        src = Source()
        sig = check(src, entry)
        R.save_final(fetch(src, entry, sig["version"]), final)
    files = list(R.load_final(final).items())
    return check_reading(read(files, entry), say, REPLAY_FOLDER)


def check_reading(rd, say, folder, need=100):
    ok = not rd["problems"]
    if rd["problems"]:
        say("  FAIL problems: " + "; ".join(rd["problems"][:5]))
    if "OFFICIAL" not in (rd.get("official_title") or "") or "UNOFFICIAL" in (rd.get("official_title") or ""):
        say(f"  FAIL the Board does not title {folder} OFFICIAL ({rd.get('official_title')})")
        ok = False
    bad = 0
    for c in rd["contests"]:
        whole, parts = {}, {}
        for r in c["rows"]:
            if r["type"] != "total":
                continue
            d = whole if r["unit"] == "all" else parts
            d[r["choice"]] = d.get(r["choice"], 0) + r["votes"]
        rep = next((x for x in c["reporting"] if x["unit"] == "all"), {})
        if whole != parts or rep.get("in") != rep.get("all"):
            bad += 1
            if bad <= 5:
                say(f"  FAIL {c['race_id']}: statewide {sum(whole.values()):,} against counties {sum(parts.values()):,}; "
                    f"{rep.get('in')} of {rep.get('all')} precincts")
    n_c = len({u["id"] for c in rd["contests"] for u in c["units"] if u["kind"] == "county"})
    ok = ok and not bad and bool(rd["contests"]) and n_c >= need
    votes = sum(r["votes"] for c in rd["contests"] for r in c["rows"] if r["unit"] == "all" and r["type"] == "total")
    say(f"  {'ok  ' if ok else 'FAIL'} North Carolina {folder}: {len(rd['contests'])} contests read ({votes:,} votes) from {n_c} counties; "
        f"each statewide total equal to its county rows and its votes by how they were cast, every precinct in; "
        f"the Board's title: {rd.get('official_title')}; {len(rd['unmatched'])} contests listed, not read")
    return ok


def make_fixture(say=print):
    """Three counties (Alamance, Alexander, Ashe) of the 2024 general and their contests for Congress and the State Senate,
    with statewide lines made the sums of the three (so that the fixture adds up on its own: a test file, not the result)."""
    from election import replay as R
    files = R.load_final(os.path.join(K.REPLAY_SOURCES, f"nc-{REPLAY_FOLDER}"))
    keep = {"1", "2", "5"}
    sub = {n: b for n, b in files.items() if n.endswith(("county.txt", "results_0.txt")) or re.search(r"results_(1|2|5)\.txt$", n)}
    wanted = lambda t: (key_of(t) or "").startswith(("us_house:", "state_senate:"))     # noqa: E731
    names = set()
    for n in list(sub):
        if re.search(r"results_[125]\.txt$", n):
            rows = [r for r in json.loads(sub[n].decode("utf-8-sig")) if wanted(r.get("cnm", ""))]
            names |= {r["cnm"] for r in rows}
            sub[n] = json.dumps(rows).encode("utf-8")
    for n in list(sub):
        if n.endswith("results_0.txt"):
            sub[n] = json.dumps([r for r in json.loads(sub[n].decode("utf-8-sig")) if r.get("cnm") in names]).encode("utf-8")
        elif n.endswith("county.txt"):
            sub[n] = json.dumps([c for c in json.loads(sub[n].decode("utf-8-sig")) if c.get("cid") in keep | {"0"}]).encode("utf-8")
    sub = reveal(sub, keep, 0)
    cf = next(n for n in sub if n.endswith("county.txt"))
    rows = json.loads(sub[cf])
    for c in rows:
        if c["cid"] == "0":
            c["imp"] = "December 4, 2024 8:59 pm"
            c["ptl"] = c["prt"]
            c["tle"] = "11/05/2024 OFFICIAL GENERAL ELECTION RESULTS - STATEWIDE"
    sub[cf] = json.dumps(rows).encode("utf-8")
    sf = next(n for n in sub if n.endswith("results_0.txt"))
    srows = json.loads(sub[sf])
    for r in srows:
        r["ptl"] = r["prt"]
    sub[sf] = json.dumps(srows).encode("utf-8")
    fd = fixture_dir()
    for n, b in sub.items():
        p = os.path.join(fd, *n.split("/"))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "wb").write(b)
    say(f"  fixture written: {len(sub)} files, {len(names)} contests, in {fd}")


def selftest(say=print):
    from election import replay as R
    fd = fixture_dir()
    if not os.path.isdir(fd):
        say("  FAIL no fixture")
        return False
    files = R.load_final(fd)
    ok = check_reading(read(list(files.items()), {"election": {"nov3_id": REPLAY_FOLDER}}), say, REPLAY_FOLDER, need=3)
    part = reveal(files, {"1"}, 1)
    rd = read(list(part.items()), {"election": {"nov3_id": REPLAY_FOLDER}})
    adds = all(sum(r["votes"] for r in c["rows"] if r["unit"] == "all" and r["type"] == "total") ==
               sum(r["votes"] for r in c["rows"] if r["unit"] != "all" and r["type"] == "total") for c in rd["contests"])
    ok2 = adds and not rd["problems"] and bool(rd["contests"])
    say(f"  {'ok  ' if ok2 else 'FAIL'} a rehearsal step with one county of three in reads and adds up")
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
