"""election/readers/civix.py - Texas's results, from the Secretary of State's election-night system built by Civix
(goelect.txelections.civixapps.com: "Civix Election Night Results"), whose answers are JSON wrapped as base64 in JSON.

Calls made (every one through election/source.py, with the file's ETag; fields allowlisted):
  api-ivis-system/api/s3/enr/election/<ID>            one election's record: Home (when it was last updated, counties
        and precincts reporting), Federal, StateWide and Districted (each race: id, name, and each candidate's id, ballot
        name, party, votes V and early votes EV), plus sections never read (propositions, lookups of names, reports).
        Before the night it holds only {"Version": ""}. It is the cheap "what's new" look: an unchanged record answers
        304 to the ETag.
  api-ivis-system/api/s3/enr/election/countyInfo/<ID>  every race county by county (the same fields, with each county's
        precincts reporting and in all); asked only when the record changed
  api-ivis-system/api/s3/enr/electionConstants        the list of elections (read by discover only)
The registry names November 3's elections: the general (53815) and two special elections the same day (House District
93, 66734; Senate District 22, 66618). The specials are not in the ballot lists yet, so their contests are listed, not
shown.

Texas reports early votes (EV) beside each candidate's total (V); Election Day votes are the difference. Mail is not
split from early voting in person. The figures are "as reported" until the state canvass.

    python -m election.readers.civix --crosswalk     rebuild election/crosswalk/tx.json (no request: the Nov 3 record is
                                                     empty until the night)
    python -m election.readers.civix --replay        fetch the March 3, 2026 Republican primary (53813) once, read it,
                                                     and check it against the Secretary's Official Canvass Report and its
                                                     own county figures
    python -m election.readers.civix --selftest      the reader's test on its fixture (no network)
"""

import argparse
import base64
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

STATE = "TX"
FAMILY = "civix"
FEED = "tx-civix"
API = "https://goelect.txelections.civixapps.com/api-ivis-system/api/s3/enr/"
NOV3_IDS = ("53815", "66734", "66618")
REPLAY = "53813"
ACCEPT = "application/json, text/plain, */*"
SECTIONS = ("Federal", "StateWide", "Districted")
CAND = ("ID", "N", "P", "V", "EV", "O")
_LAST = {}

STATEWIDE = {"GOVERNOR": "governor", "LIEUTENANT GOVERNOR": "lieutenant_governor", "ATTORNEY GENERAL": "attorney_general",
             "COMPTROLLER OF PUBLIC ACCOUNTS": "comptroller", "COMMISSIONER OF THE GENERAL LAND OFFICE": "land_commissioner",
             "COMMISSIONER OF AGRICULTURE": "agriculture_commissioner", "RAILROAD COMMISSIONER": "railroad_commissioner"}


def ids_of(entry):
    ids = K.election_ids(entry, r"\b\d{5}\b")
    return ids or list(NOV3_IDS)


def key_of(title):
    t = re.sub(r"\s+", " ", title or "").strip().upper()
    unexp = bool(re.search(r"UNEXPIRED", t))
    t = re.sub(r",?\s*UNEXPIRED TERM", "", t).strip(" ,")
    tail = ":unexpired" if unexp else ""
    if re.fullmatch(r"U\. ?S\. SENATOR", t):
        return "us_senate" + (":special" if unexp else "")
    m = re.fullmatch(r"U\. ?S\. REPRESENTATIVE,? DISTRICT (\d+)", t)
    if m:
        return f"us_house:{int(m.group(1))}"
    if t in STATEWIDE:
        return STATEWIDE[t]
    m = re.fullmatch(r"STATE SENATOR,? DISTRICT (\d+)", t)
    if m:
        return f"state_senate:{int(m.group(1))}"
    m = re.fullmatch(r"STATE REPRESENTATIVE,? DISTRICT (\d+)", t)
    if m:
        return f"state_house:{int(m.group(1))}"
    m = re.fullmatch(r"MEMBER,? STATE BOARD OF EDUCATION,? DISTRICT (\d+)", t)
    if m:
        return f"state_board_of_education:{int(m.group(1))}"
    if t == "CHIEF JUSTICE, SUPREME COURT":
        return "supreme_court:chief" + tail
    m = re.fullmatch(r"JUSTICE, SUPREME COURT,? PLACE (\d+)", t)
    if m:
        return f"supreme_court:{int(m.group(1))}{tail}"
    m = re.fullmatch(r"JUDGE, COURT OF CRIMINAL APPEALS,? PLACE (\d+)", t)
    if m:
        return f"court_of_criminal_appeals:{int(m.group(1))}{tail}"
    m = re.fullmatch(r"CHIEF JUSTICE, (\d+)\w* COURT OF APPEALS DISTRICT", t)
    if m:
        return f"court_of_appeals:{int(m.group(1))}:chief justice{tail}"
    m = re.fullmatch(r"JUSTICE, (\d+)\w* COURT OF APPEALS DISTRICT,? PLACE (\d+)", t)
    if m:
        return f"court_of_appeals:{int(m.group(1))}:place {int(m.group(2))}{tail}"
    return None


def unpack(body):
    d = json.loads(body.decode("utf-8-sig"))
    return json.loads(base64.b64decode(d["upload"])) if isinstance(d, dict) and "upload" in d else d


def section(rec, name):
    v = rec.get(name)
    return json.loads(base64.b64decode(v)) if isinstance(v, str) and v else (v or {})


# ---------------------------------------------------------------------------------------------- requests


def _record(src, eid):
    r = src.get(API + f"election/{eid}", state=STATE, accept=ACCEPT, conditional=True)
    if r.not_modified and eid in _LAST:
        return _LAST[eid]
    body = K.body_ok(r, f"election {eid}'s record")
    rec = json.loads(body.decode("utf-8-sig"))
    home = section(rec, "Home") if len(rec) > 1 else {}
    ver = f"{rec.get('Version') or ''}|{home.get('LastUpdatedTime') or ''}"
    _LAST[eid] = (ver, body, home)
    return _LAST[eid]


def check(src, entry):
    vers, when = [], None
    for eid in ids_of(entry):
        ver, body, home = _record(src, eid)
        if ver.strip("|"):
            vers.append(f"{eid}:{hashlib.sha256(body).hexdigest()[:10]}")
            t = parse_time(home.get("LastUpdatedTime"))
            when = max(when, t) if when and t else (t or when)
    if not vers:
        return None                                        # nothing loaded for the night yet
    return {"version": ",".join(vers), "time": K.iso(when)}


def fetch(src, entry, version):
    out = []
    for eid in ids_of(entry):
        got = _LAST.get(eid) or _record(src, eid)
        if not got[0].strip("|"):
            continue
        out.append((API + f"election/{eid}", got[1]))
        out.append((API + f"election/countyInfo/{eid}",
                    K.body_ok(src.get(API + f"election/countyInfo/{eid}", state=STATE, accept=ACCEPT), f"election {eid}'s county figures")))
    return out


def discover(src, entry):
    d = unpack(K.body_ok(src.get(API + "electionConstants", state=STATE, accept=ACCEPT), "the list of elections"))
    found = []
    for _y, kinds in (d.get("electionInfo") or {}).items():
        for _k, els in kinds.items():
            for eid, e in els.items():
                if str(eid) in NOV3_IDS:
                    found.append(f"{eid} {e.get('N')}")
    return {"nov3_id": "53815; specials 66734 (House District 93) and 66618 (Senate District 22)" if found else None,
            "note": "; ".join(found) or "not listed"}


def parse_time(s):
    try:
        t = dt.datetime.strptime(re.sub(r"\s+", " ", s or "").strip(), "%b %d, %Y %H:%M:%S")
    except ValueError:
        return None
    return K.local_to_utc(t, "America/Chicago")


# ---------------------------------------------------------------------------------------------- reading


def eid_of(name):
    m = re.search(r"election(?:/|_)(?:countyInfo(?:/|_))?(\d{5})", str(name).replace("\\", "/"))
    return m.group(1) if m else None


def read(files, entry):
    ids = ids_of(entry)
    nov3 = ids[0] == NOV3_IDS[0]
    C = K.Contests(STATE, nov3=nov3)
    recs, cinfo = {}, {}
    for n, b in files:
        eid = eid_of(n)
        if not eid:
            continue
        try:
            if "countyInfo" in str(n):
                cinfo[eid] = unpack(b)
            else:
                recs[eid] = json.loads(b.decode("utf-8-sig"))
        except (ValueError, KeyError) as e:
            C.problems.append(f"election {eid}: a file did not read ({e.__class__.__name__})")
    if not recs:
        C.problems.append("no election record")
        return C.reading(FEED)
    newest, version = None, []
    for eid, rec in recs.items():
        main = eid == ids[0]
        home = section(rec, "Home")
        t = parse_time(home.get("LastUpdatedTime"))
        newest = max(newest, t) if newest and t else (t or newest)
        version.append(f"{eid}:{rec.get('Version')}")
        race_of = {}
        for sec in SECTIONS:
            for r in (section(rec, sec).get("Races") or []):
                title = re.sub(r"\s+", " ", r.get("N") or "").strip()
                key = key_of(title)
                if key and not main:
                    key += ":special-election"              # a special election held the same day: its own contest
                rid = C.race_for(key, title, f"{eid}|{r.get('id')}")
                if not rid:
                    continue
                if rid in C.c:
                    C.problems.append(f"{rid}: two contests of the file tie to it ({title})")
                    continue
                c = C.contest(rid, f"{eid}|{r.get('id')}", title.title())
                C.unit(c, "all", "race", "the whole contest")
                race_of[str(r.get("id"))] = rid
                cks = {}
                for i, cd in enumerate(r.get("Candidates") or []):
                    cd = {k: cd.get(k) for k in CAND}
                    ck = C.choice(c, cd["N"], cd.get("P"), order=i + 1, write_in=bool(re.search(r"write[- ]?in", cd["N"] or "", re.I)))
                    cks[str(cd["ID"])] = ck
                    C.row(c, "all", ck, int(cd.get("V") or 0))
                    if cd.get("EV") is not None:
                        C.row(c, "all", ck, int(cd["EV"]), "early")
                if r.get("T") is not None:
                    c.setdefault("stated", []).append({"unit": "all", "total": int(r["T"])})
                c["_cks"] = cks
        # county by county
        ci = cinfo.get(eid) or {}
        sums = {}
        for _cid, cty in ci.items():
            fips = K.county_unit(STATE, cty.get("N"))
            if not fips:
                C.problems.append(f"the county {cty.get('N')!r} is not one of Texas's 254")
                continue
            for oid, rr in (cty.get("Races") or {}).items():
                rid = race_of.get(str(oid))
                if not rid:
                    continue
                c = C.c[rid]
                C.unit(c, fips, "county", (cty.get("N") or "").title(), parent=STATE, map_id=fips)
                for cand_id, cd in (rr.get("C") or {}).items():
                    ck = c["_cks"].get(str(cand_id)) or C.choice(c, cd.get("N"), cd.get("P"))
                    C.row(c, fips, ck, int(cd.get("V") or 0))
                    if cd.get("EV") is not None:
                        C.row(c, fips, ck, int(cd["EV"]), "early")
                C.report(c, fips, rr.get("PR"), rr.get("TP"))
                s = sums.setdefault(rid, [0, 0, 0])
                s[0] += int(rr.get("PR") or 0)
                s[1] += int(rr.get("TP") or 0)
                s[2] += 1
        for rid, (i, a, n) in sums.items():
            C.report(C.c[rid], "all", i, a)
            C.c[rid]["units_all"] = n
    for c in C.c.values():
        c.pop("_cks", None)
    return C.reading(FEED, source_time=K.iso(newest), source_version=hashlib.sha256(",".join(version).encode()).hexdigest()[:16])


# ---------------------------------------------------------------------------------------------- rehearsals


def units(files):
    out = {}
    for n, b in dict(files).items():
        if "countyInfo" in n:
            for cid, cty in unpack(b).items():
                out[cid] = (cid, K.county_unit(STATE, cty.get("N")) or "", int(cty.get("TV") or 0) or
                            sum(int(cd.get("V") or 0) for rr in (cty.get("Races") or {}).values() for cd in (rr.get("C") or {}).values()))
    return sorted(out.values())


def reveal(files, keep, step):
    """The record and the county figures as they would have stood with only the kept counties in: a county not yet in
    has its votes and precincts reporting at 0, and each race's lines in the record are the sums of the counties'."""
    files = dict(files)
    out, sums = {}, {}
    for n, b in files.items():
        if "countyInfo" not in n:
            continue
        ci = unpack(b)
        for cid, cty in ci.items():
            on = cid in keep
            for oid, rr in (cty.get("Races") or {}).items():
                if not on:
                    rr["PR"] = 0
                    for cd in (rr.get("C") or {}).values():
                        cd["V"], cd["EV"] = 0, 0
                    rr["T"] = 0
                for cand_id, cd in (rr.get("C") or {}).items():
                    s = sums.setdefault((eid_of(n), str(oid)), {}).setdefault(str(cand_id), [0, 0])
                    s[0] += int(cd.get("V") or 0)
                    s[1] += int(cd.get("EV") or 0)
        out[n] = json.dumps({"upload": base64.b64encode(json.dumps(ci).encode()).decode()}).encode("utf-8")
    for n, b in files.items():
        if "countyInfo" in n:
            continue
        eid = eid_of(n)
        if not eid:
            out[n] = b
            continue
        rec = json.loads(b.decode("utf-8-sig"))
        for sec in SECTIONS:
            d = section(rec, sec)
            for r in d.get("Races") or []:
                s = sums.get((eid, str(r.get("id"))))
                if s is None:
                    continue
                for cd in r.get("Candidates") or []:
                    v, ev = s.get(str(cd.get("ID")), [0, 0])
                    cd["V"], cd["EV"] = v, ev
                r["T"] = sum(int(cd.get("V") or 0) for cd in r.get("Candidates") or [])
            if d:
                rec[sec] = base64.b64encode(json.dumps(d).encode()).decode()
        home = section(rec, "Home")
        if home:
            home["LastUpdatedTime"] = (dt.datetime(2026, 3, 3, 19, 0) + dt.timedelta(minutes=10 * step)).strftime("%b %d, %Y %H:%M:%S")
            rec["Home"] = base64.b64encode(json.dumps(home).encode()).decode()
        rec["Version"] = f"{rec.get('Version')}step{step}"
        out[n] = json.dumps(rec).encode("utf-8")
    return out


# ---------------------------------------------------------------------------------------------- crosswalk, replay, self-test


def build_crosswalk(say=print):
    return K.build_crosswalk(STATE, "goelect.txelections.civixapps.com election/53815 (empty until the night)", (
        "Texas's races on the November 3, 2026 ballot that the Election Night pages read (Congress from ballot_2026.sqlite; the "
        "statewide offices, the State Board of Education, the Legislature, the Supreme Court, the Court of Criminal Appeals and "
        "the courts of appeals from ballot_local_2026.sqlite), each with the key a race of the Secretary's election record is tied "
        "by (read from its name) and the candidates as filed. The record for November 3 holds nothing until the night, so no "
        "posted contest list is tied here yet. The two special elections the same day (House District 93, Senate District 22) "
        "are not in the ballot lists: their contests are listed, never tied to the regular races."), feed_contests=None, say=say,
        feed_note="Ballot names are printed in capitals, with (I) after an incumbent; that mark is set aside.")


def fixture_dir():
    return os.path.join(K.FIXTURE_DIR, "tx")


def canvass_figures():
    """{race id: {family name: votes}} for the federal races of the March 3, 2026 Republican primary, from the Secretary's
    Official Canvass Report as the kit already reads it (ballot/lists/tx.py)."""
    from ballot.lists import tx as T
    folder = os.path.join(HERE, "ballot_cache", "tx")
    races, _stamp, differ = T.canvass(os.path.join(folder, "tx_2026_primary_rep_official_canvass.pdf"), "2026 REPUBLICAN PRIMARY ELECTION",
                                      "REP", os.path.join(folder, "tx_2026_primary_rep_federal_results.json"))
    out = {}
    for rid, c in races.items():
        d = {}
        for n, v in c["cands"]:
            fam = K.name_words(n)[1]
            d[fam] = d.get(fam, 0) + v
        out[rid] = d
    return out, differ


def replay(say=print, refetch=False):
    from election import replay as R
    from election.source import Source
    final = os.path.join(K.REPLAY_SOURCES, f"tx-{REPLAY}")
    entry = {"election": {"nov3_id": REPLAY}}
    if refetch or not os.path.isdir(final):
        src = Source()
        sig = check(src, entry)
        R.save_final(fetch(src, entry, sig["version"]), final)
    files = list(R.load_final(final).items())
    rd = read(files, entry)
    figs, differ = canvass_figures()
    return check_reading(rd, figs, differ, say)


def check_reading(rd, figs, differ, say, need=30):
    ok = not rd["problems"]
    if rd["problems"]:
        say("  FAIL problems: " + "; ".join(rd["problems"][:5]))
    bad_c = 0
    for c in rd["contests"]:
        for vt in ("total", "early"):
            whole, parts = {}, {}
            for r in c["rows"]:
                if r["type"] == vt:
                    d = whole if r["unit"] == "all" else parts
                    d[r["choice"]] = d.get(r["choice"], 0) + r["votes"]
            if parts and whole != parts:
                bad_c += 1
                if bad_c <= 4:
                    say(f"  FAIL {c['race_id']} {vt}: the record says {sum(whole.values()):,}, its counties {sum(parts.values()):,}")
    compared = bad = 0
    for c in rd["contests"]:
        want = figs.get(c["race_id"])
        if not want:
            continue
        names = {ch["key"]: ch["name"] for ch in c["choices"]}
        got = {}
        for r in c["rows"]:
            if r["unit"] == "all" and r["type"] == "total":
                fam = K.name_words(names[r["choice"]])[1]
                got[fam] = got.get(fam, 0) + r["votes"]
        compared += 1
        if got != want:
            bad += 1
            say(f"  FAIL {c['race_id']}: read {got}, the canvass report says {want}")
    ok = ok and not bad and not bad_c and compared >= need
    votes = sum(r["votes"] for c in rd["contests"] for r in c["rows"] if r["unit"] == "all" and r["type"] == "total")
    say(f"  {'ok  ' if ok else 'FAIL'} Texas: {len(rd['contests'])} contests read ({votes:,} votes); every race's record lines equal to its "
        f"county sums (total and early): {bad_c} differ; {compared} federal races compared with the Official Canvass Report: {bad} differ"
        f"{' (the report itself: ' + '; '.join(differ[:2]) + ')' if differ else ''}; {len(rd['unmatched'])} contests listed, not read")
    return ok


def make_fixture(say=print):
    """Two congressional districts (1 and 31), the Governor and one State Senate seat of the March primary, in six counties,
    with the record's lines the sums of those counties (a test file, not the result)."""
    from election import replay as R
    files = R.load_final(os.path.join(K.REPLAY_SOURCES, f"tx-{REPLAY}"))
    keep_titles = {"U. S. REPRESENTATIVE DISTRICT 1", "U. S. REPRESENTATIVE DISTRICT 31", "GOVERNOR", "STATE SENATOR, DISTRICT 1"}
    out = {}
    rec_name = next(n for n in files if "countyInfo" not in n and eid_of(n))
    rec = json.loads(files[rec_name].decode("utf-8-sig"))
    ids = set()
    small = {"rec": {"Version": rec.get("Version"), "Home": rec.get("Home")}}
    for sec in SECTIONS:
        d = section(rec, sec)
        d["Races"] = [r for r in d.get("Races") or [] if re.sub(r"\s+", " ", r.get("N") or "").strip() in keep_titles]
        ids |= {str(r["id"]) for r in d["Races"]}
        small["rec"][sec] = base64.b64encode(json.dumps(d).encode()).decode()
    ci_name = next(n for n in files if "countyInfo" in n)
    ci = unpack(files[ci_name])
    want = {"BELL", "WILLIAMSON", "BOWIE", "CASS", "HARRISON", "GREGG"}
    ci = {cid: dict(c, Races={o: r for o, r in (c.get("Races") or {}).items() if o in ids}) for cid, c in ci.items() if c.get("N") in want}
    out[ci_name] = json.dumps({"upload": base64.b64encode(json.dumps(ci).encode()).decode()}).encode("utf-8")
    out[rec_name] = json.dumps(small["rec"]).encode("utf-8")
    out = reveal(out, set(ci), 0)
    fd = fixture_dir()
    for n, b in out.items():
        p = os.path.join(fd, *n.split("/"))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "wb").write(b)
    say(f"  fixture written: {len(out)} files, {len(ids)} races, {len(ci)} counties, in {fd}")


def selftest(say=print):
    from election import replay as R
    fd = fixture_dir()
    if not os.path.isdir(fd):
        say("  FAIL no fixture")
        return False
    files = R.load_final(fd)
    rd = read(list(files.items()), {"election": {"nov3_id": REPLAY}})
    ok = check_reading(rd, {}, [], say, need=0) and len(rd["contests"]) == 4
    us = units(files)
    part = reveal(files, {us[0][0]}, 1)
    rd2 = read(list(part.items()), {"election": {"nov3_id": REPLAY}})
    ok2 = check_reading(rd2, {}, [], lambda *_: None, need=0)
    say(f"  {'ok  ' if ok2 else 'FAIL'} a rehearsal step with one county of {len(us)} in reads and adds up")
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
