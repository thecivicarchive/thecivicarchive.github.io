"""election/readers/pa_returns.py - Pennsylvania's results, from the Department of State's election returns site
(www.electionreturns.pa.gov), whose pages read a JSON service.

Calls made (every one through election/source.py; fields allowlisted):
  api/ElectionReturn/GetUpdatedTimeStamp?methodName=LastUpdatedTimeStamp
        the site's own "last updated" time (a few bytes): the cheap "what's new" look
  api/Reports/GetElectionList
        every election with its id, type (G, P, S), date and status (O = official); read to find the night's election
        when the registry does not name it yet, and to say whether its returns are official
  api/ElectionReturn/GetOfficeNames?countyName=ALL&...       the offices the election carries (id, code, name)
  api/ElectionReturn/GetOfficeData?officeId=<o>&...          one office's districts, each candidate's party, ballot name,
        running mate, votes, and the votes cast on Election Day, by mail and on provisional ballots
  api/ElectionReturn/GetCountyBreak?officeId=<o>&districtId=<d>&...   the same, county by county, for one district:
        asked for every statewide office whenever the figures change, and for each congressional district at most every
        CONGRESS_COUNTY_EVERY minutes (the site sits behind a bot-defence service: requests stay few and spaced)
The answers are JSON text inside a JSON string. Precincts reporting are not in these answers.

Pennsylvania may not start processing mail ballots before 7 a.m. on Election Day, so mail counts arrive county by county
through the night; the Election Day, mail and provisional votes are kept apart. Governor and Lieutenant Governor are
elected together on one ticket in November: the ticket's votes are the Governor's race.

    python -m election.readers.pa_returns --crosswalk     rebuild election/crosswalk/pa.json (no request)
    python -m election.readers.pa_returns --replay        fetch the 2024 general (election 105) once, read it and check it
                                                          against the Department's own official figures
    python -m election.readers.pa_returns --selftest      the reader's test on its fixture (no network)
"""

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from election.readers import _common_n11 as K  # noqa: E402

STATE = "PA"
FAMILY = "pa_returns"
FEED = "pa-pa_returns"
ROOT = "https://www.electionreturns.pa.gov/"
API = ROOT + "api/"
ACCEPT = "application/json, text/plain, */*"
NOV3_DATE = "11/03/2026"
REPLAY = "105G"
STATEWIDE = {"USS": "us_senate", "GOV": "governor", "LTG": "lieutenant_governor", "ATT": "attorney_general", "AUD": "state_auditor",
             "TRE": "state_treasurer"}
OFFICE_KEYS = {"USC": "us_house", "STS": "state_senate", "STH": "state_house"}
NAMES = {"united states senator": "USS", "governor": "GOV", "lieutenant governor": "LTG", "attorney general": "ATT",
         "auditor general": "AUD", "state treasurer": "TRE", "representative in congress": "USC",
         "senator in the general assembly": "STS", "representative in the general assembly": "STH"}
KEEP = ("CandidateName", "PartyName", "Votes", "ElectionDayVotes", "MailInVotes", "ProvisionalVotes", "RunningMateName", "RankOrder",
        "CountyName", "OfficeName", "YesVotes", "NoVotes", "IsRetention")
VOTE_TYPES = (("ElectionDayVotes", "election_day"), ("MailInVotes", "mail"), ("ProvisionalVotes", "provisional"))
CONGRESS_COUNTY_EVERY = 10 * 60
_LIST = {"at": 0, "rows": None, "raw": None}
_LAST_CONGRESS = {}


def unjson(raw):
    t = json.loads(raw.decode("utf-8-sig") if isinstance(raw, (bytes, bytearray)) else raw)
    while isinstance(t, str):
        t = json.loads(t)
    return t


def q(eid, etype, active):
    return f"&electionid={eid}&electiontype={etype}&isactive={active}"


def election_list(src):
    if _LIST["rows"] is None or time.time() - _LIST["at"] > 1800:
        raw = K.body_ok(src.get(API + "Reports/GetElectionList", state=STATE, accept=ACCEPT), "the election list")
        _LIST["rows"], _LIST["raw"] = unjson(raw).get("Table", []), raw
        _LIST["at"] = time.time()
    return _LIST["rows"]


def which(src, entry):
    """(election id, type, active flag, row of the list) for the night (or a rehearsal's past election), or None."""
    named = str(((entry or {}).get("election") or {}).get("nov3_id") or "")
    m = re.search(r"(\d+)\s*-?\s*([GPS])?\b", named)
    rows = election_list(src)
    if m:
        eid, etype = int(m.group(1)), m.group(2) or "G"
        row = next((r for r in rows if r.get("Electionid") == eid and r.get("ElectionType") == etype), None)
    else:
        row = next((r for r in rows if r.get("ElectionDate") == NOV3_DATE and r.get("ElectionType") == "G"), None)
    if not row:
        return None
    return row["Electionid"], row["ElectionType"], row.get("ISActive") or 0, row


def discover(src, entry):
    row = next((r for r in election_list(src) if r.get("ElectionDate") == NOV3_DATE and r.get("ElectionType") == "G"), None)
    if row:
        return {"nov3_id": f"{row['Electionid']}{row['ElectionType']}", "note": f"{row.get('ElectionName')} (status {row.get('ElectionStatus')})"}
    return {"note": "the Department's election list has no November 3, 2026 general yet"}


# ---------------------------------------------------------------------------------------------- requests


def check(src, entry):
    w = which(src, entry)
    if not w:
        return None
    eid, etype, _a, row = w
    stamp = K.body_ok(src.get(API + "ElectionReturn/GetUpdatedTimeStamp?methodName=LastUpdatedTimeStamp", state=STATE, accept=ACCEPT),
                      "the update time").decode("utf-8-sig").strip().strip('"')
    return {"version": f"{eid}{etype}:{row.get('ElectionStatus')}:{stamp}", "time": K.iso(parse_stamp(stamp))}


def parse_stamp(s):
    try:
        t = dt.datetime.strptime(s[:19], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None
    return K.local_to_utc(t, "America/New_York")


def fetch(src, entry, version):
    w = which(src, entry)
    if not w:
        return []
    eid, etype, active, row = w
    out = [(API + "Reports/GetElectionList", _LIST["raw"])]
    stamp = version.split(":", 2)[2] if version.count(":") >= 2 else ""
    out.append((API + "ElectionReturn/GetUpdatedTimeStamp?methodName=LastUpdatedTimeStamp", json.dumps(stamp).encode("utf-8")))
    qs = q(eid, etype, active)
    off = K.body_ok(src.get(API + f"ElectionReturn/GetOfficeNames?countyName=ALL&methodName=GetOfficeNames{qs}", state=STATE, accept=ACCEPT),
                    "the office list")
    out.append((API + f"ElectionReturn/GetOfficeNames?countyName=ALL&methodName=GetOfficeNames{qs}", off))
    offices = [(int(o["OfficeID"]), o.get("OfficeCode"), o.get("OfficeName")) for o in unjson(off).get("Table", [])]
    nov3 = row.get("ElectionDate") == NOV3_DATE
    cw = K.load_crosswalk(STATE).get("keys", {})
    now = time.time()
    congress_due = (not nov3) or now - _LAST_CONGRESS.get(eid, 0) >= CONGRESS_COUNTY_EVERY
    for oid, code, name in offices:
        code = code if code in STATEWIDE or code in OFFICE_KEYS else NAMES.get((name or "").lower())
        if code not in STATEWIDE and code not in OFFICE_KEYS:
            continue
        url = API + f"ElectionReturn/GetOfficeData?officeId={oid}&methodName=GetOfficeDetails{qs}"
        body = K.body_ok(src.get(url, state=STATE, accept=ACCEPT), "an office's returns")
        out.append((url, body))
        if code in ("STS", "STH"):
            continue                                            # the Legislature: statewide district figures only
        if code == "USC" and not congress_due:
            continue
        for d in districts(unjson(body)):
            key = STATEWIDE.get(code) if code in STATEWIDE else f"us_house:{K.num(d['name'])}"
            if key == "us_senate" and not any(k.startswith("us_senate") for k in cw):
                continue
            if nov3 and key not in cw and not (key == "us_senate" and any(k.startswith("us_senate") for k in cw)):
                continue
            cu = API + f"ElectionReturn/GetCountyBreak?officeId={oid}&districtId={d['id']}&methodName=GetCountyBreak{qs}"
            r = src.get(cu, state=STATE, accept=ACCEPT)
            if r.ok:
                out.append((cu, r.body))
            elif r.refused:
                K.body_ok(r, "a county breakdown")
        if code == "USC":
            _LAST_CONGRESS[eid] = now
    return out


def districts(doc):
    """[{id, name, candidates}] of one office's answer."""
    out = []
    for _office, blocks in (doc.get("Election") or {}).items():
        for block in blocks:
            for label, ds in block.items():
                for d in ds:
                    out.append({"id": str(d.get("DistrictId")), "name": d.get("District") or label.split("$$")[0], "cands": cands(d.get("Candidates"))})
    return out


def cands(items):
    """Candidate rows, flat (a general) or filed under each party (a primary)."""
    out = []
    for it in items or []:
        if "CandidateName" in it:
            out.append({k: it.get(k) for k in KEEP})
        else:
            for _party, lst in it.items():
                out.extend({k: c.get(k) for k in KEEP} for c in lst)
    return out


# ---------------------------------------------------------------------------------------------- reading


def key_for(code, district_name):
    if code in STATEWIDE:
        return STATEWIDE[code]
    if code in OFFICE_KEYS:
        return f"{OFFICE_KEYS[code]}:{K.num(district_name)}"
    return None


def printed(c):
    name = re.sub(r"\s+", " ", c.get("CandidateName") or "").strip()
    mate = re.sub(r"\s+", " ", c.get("RunningMateName") or "").strip()
    return f"{name} / {mate}" if mate else name


def read(files, entry):
    _n, lb = K.file_named(files, "GetElectionList")
    on, _ob = K.file_named(files, "GetOfficeNames")
    m = re.search(r"electionid=(\d+)[&_]electiontype=([GPS])", str(on or ""))
    rows = unjson(lb).get("Table", []) if lb else []
    row = next((r for r in rows if m and str(r.get("Electionid")) == m.group(1) and r.get("ElectionType") == m.group(2)), {})
    nov3 = row.get("ElectionDate") == NOV3_DATE
    C = K.Contests(STATE, nov3=nov3)
    _n, ob = K.file_named(files, "GetOfficeNames")
    if ob is None:
        C.problems.append("the office list is missing")
        return C.reading(FEED)
    codes = {}
    for o in unjson(ob).get("Table", []):
        codes[str(o["OfficeID"])] = o.get("OfficeCode") if (o.get("OfficeCode") in STATEWIDE or o.get("OfficeCode") in OFFICE_KEYS) \
            else NAMES.get((o.get("OfficeName") or "").lower(), o.get("OfficeCode"))
    by_district = {}
    for n, b in files:
        m = re.search(r"GetOfficeData[?_]+officeId=(\d+)", str(n))
        if not m:
            continue
        code = codes.get(m.group(1))
        try:
            doc = unjson(b)
        except ValueError:
            C.problems.append(f"office {m.group(1)}'s returns did not read as JSON")
            continue
        for d in districts(doc):
            title = f"{(d['cands'][0].get('OfficeName') if d['cands'] else code) or code}, {d['name']}"
            rid = C.race_for(key_for(code, d["name"]), title, f"{m.group(1)}|{d['id']}")
            if not rid:
                continue
            c = C.contest(rid, f"{m.group(1)}|{d['id']}", title)
            C.unit(c, "all", "race", "the whole contest")
            by_district[(m.group(1), d["id"])] = rid
            for i, cd in enumerate(sorted(d["cands"], key=lambda x: int(x.get("RankOrder") or 0))):
                ck = C.choice(c, printed(cd), cd.get("PartyName"), order=i + 1)
                total = int(cd.get("Votes") or 0)
                C.row(c, "all", ck, total)
                parts = 0
                for f, vt in VOTE_TYPES:
                    if cd.get(f) not in (None, ""):
                        C.row(c, "all", ck, int(cd[f]), vt)
                        parts += int(cd[f])
                if parts and parts != total:
                    C.problems.append(f"{rid} {cd.get('CandidateName')}: Election Day, mail and provisional votes add to {parts:,}, the total says {total:,}")
    for n, b in files:
        m = re.search(r"GetCountyBreak[?_]+officeId=(\d+)[&_]districtId=(\d+)", str(n))
        if not m:
            continue
        rid = by_district.get((m.group(1), m.group(2)))
        if not rid:
            continue
        c = C.c[rid]
        try:
            doc = unjson(b)
        except ValueError:
            C.problems.append(f"a county breakdown of {rid} did not read as JSON")
            continue
        n_c = 0
        for _dname, blocks in (doc.get("Election") or {}).items():
            for block in blocks:
                for county, plist in block.items():
                    fips = K.county_unit(STATE, county)
                    if not fips:
                        C.problems.append(f"{rid}: the county {county!r} is not one of Pennsylvania's 67")
                        continue
                    n_c += 1
                    C.unit(c, fips, "county", county.title(), parent=STATE, map_id=fips)
                    for cd in cands(plist):
                        ck = C.choice(c, printed(cd), cd.get("PartyName"))
                        C.row(c, fips, ck, int(cd.get("Votes") or 0))
                        for f, vt in VOTE_TYPES:
                            if cd.get(f) not in (None, ""):
                                C.row(c, fips, ck, int(cd[f]), vt)
        c["units_all"] = n_c or None
    if row.get("ElectionStatus") == "O":
        C.notes.append("the Department's election list marks these returns Official")
    ver = hashlib.sha256(b"".join(b for _n, b in files)).hexdigest()[:16]
    rd = C.reading(FEED, source_version=ver)
    rd["official"] = row.get("ElectionStatus") == "O"
    return rd


# ---------------------------------------------------------------------------------------------- rehearsals


def units(files):
    size = {}
    for n, b in dict(files).items():
        if "GetCountyBreak" in n:
            for _d, blocks in (unjson(b).get("Election") or {}).items():
                for block in blocks:
                    for county, plist in block.items():
                        size[county] = size.get(county, 0) + sum(int(c.get("Votes") or 0) for c in cands(plist))
    return [(c, K.county_unit(STATE, c) or "", n) for c, n in sorted(size.items())]


def reveal(files, keep, step):
    """Each county breakdown with only the kept counties, and each district's lines the sums of its kept counties (a district
    without a breakdown keeps its share of votes in proportion to the counties in)."""
    files = dict(files)
    out, sums, share = {}, {}, {}
    for n in files:
        if "GetUpdatedTimeStamp" in n:                  # the site's update time moves on with each step
            t = dt.datetime(2024, 11, 5, 20, 0) + dt.timedelta(minutes=10 * step)
            out[n] = json.dumps(t.strftime("%Y-%m-%d %H:%M:%S.000")).encode("utf-8")
    for n, b in files.items():
        m = re.search(r"GetCountyBreak[?_]+officeId=(\d+)[&_]districtId=(\d+)", n)
        if not m:
            continue
        doc = unjson(b)
        s = {}
        for dname, blocks in (doc.get("Election") or {}).items():
            nb = []
            for block in blocks:
                kept = {cty: pl for cty, pl in block.items() if cty in keep}
                for cty, pl in kept.items():
                    for cd in cands(pl):
                        t = s.setdefault(cd["CandidateName"], {f: 0 for f in ("Votes",) + tuple(x for x, _v in VOTE_TYPES)})
                        for f in t:
                            t[f] += int(cd.get(f) or 0)
                if kept:
                    nb.append(kept)
            doc["Election"][dname] = nb
        sums[(m.group(1), m.group(2))] = s
        out[n] = json.dumps(json.dumps(doc)).encode("utf-8")
    all_counties = {u[0] for u in units(files)}
    frac = len(keep & all_counties) / len(all_counties) if all_counties else 0
    for n, b in files.items():
        m = re.search(r"GetOfficeData[?_]+officeId=(\d+)", n)
        if not m:
            out.setdefault(n, b)
            continue
        doc = unjson(b)
        for _o, blocks in (doc.get("Election") or {}).items():
            for block in blocks:
                for _label, ds in block.items():
                    for d in ds:
                        s = sums.get((m.group(1), str(d.get("DistrictId"))))
                        for cd in d.get("Candidates") or []:
                            if "CandidateName" not in cd:
                                continue
                            for f in ("Votes",) + tuple(x for x, _v in VOTE_TYPES):
                                cd[f] = str(s.get(cd["CandidateName"], {}).get(f, 0)) if s is not None else str(round(int(cd.get(f) or 0) * frac))
                            if s is None:
                                cd["Votes"] = str(sum(int(cd[x]) for x, _v in VOTE_TYPES))
        out[n] = json.dumps(json.dumps(doc)).encode("utf-8")
    return out


# ---------------------------------------------------------------------------------------------- crosswalk, replay, self-test


def build_crosswalk(say=print):
    return K.build_crosswalk(STATE, "electionreturns.pa.gov GetOfficeData (offices 3 Governor, 11 Congress, 12 and 13 the Legislature)", (
        "Pennsylvania's races on the November 3, 2026 ballot that the Election Night pages read (Congress from ballot_2026.sqlite; the "
        "Governor's ticket and the Legislature from ballot_local_2026.sqlite), each with the key a district of the Department's returns "
        "is tied by (its office and district number) and the candidates as filed. The Department posts the night's election only "
        "shortly before it, so no posted contest list is tied here yet. The Lieutenant Governor is elected on the Governor's ticket: "
        "its race holds the May primary only."), feed_contests=None, say=say,
        feed_note="Ballot names are printed in capitals (JOSH SHAPIRO); a ticket's printed name is the Governor's and the running mate's.")


def fixture_dir():
    return os.path.join(K.FIXTURE_DIR, "pa")


def replay(say=print, refetch=False):
    from election import replay as R
    from election.source import Source
    final = os.path.join(K.REPLAY_SOURCES, f"pa-{REPLAY}")
    entry = {"election": {"nov3_id": REPLAY}}
    if refetch or not os.path.isdir(final):
        src = Source()
        sig = check(src, entry)
        R.save_final(fetch(src, entry, sig["version"]), final)
    files = list(R.load_final(final).items())
    return check_reading(read(files, entry), say)


def check_reading(rd, say, need=17):
    ok = not rd["problems"]
    if rd["problems"]:
        say("  FAIL problems: " + "; ".join(rd["problems"][:5]))
    if not rd.get("official"):
        say("  FAIL the Department does not mark this election Official")
        ok = False
    compared = bad = 0
    for c in rd["contests"]:
        kinds = {u["id"]: u["kind"] for u in c["units"]}
        if not any(k == "county" for k in kinds.values()):
            continue
        for vt in ("total", "election_day", "mail", "provisional"):
            whole, parts = {}, {}
            for r in c["rows"]:
                if r["type"] != vt:
                    continue
                d = whole if r["unit"] == "all" else parts
                d[r["choice"]] = d.get(r["choice"], 0) + r["votes"]
            if whole != parts:
                bad += 1
                say(f"  FAIL {c['race_id']} {vt}: statewide {sum(whole.values()):,}, counties {sum(parts.values()):,}")
        compared += 1
    ok = ok and compared >= need and not bad
    votes = sum(r["votes"] for c in rd["contests"] for r in c["rows"] if r["unit"] == "all" and r["type"] == "total")
    say(f"  {'ok  ' if ok else 'FAIL'} Pennsylvania: {len(rd['contests'])} contests read ({votes:,} votes); {compared} with county breakdowns, "
        f"each statewide line equal to its counties' sum in all four counts (total, Election Day, mail, provisional): {bad} differ; "
        f"the Department marks the election Official: {rd.get('official')}; {len(rd['unmatched'])} contests listed, not read")
    return ok


def make_fixture(say=print):
    """The 2024 general's U.S. Senate and congressional districts 1 and 15 (offices 2 and 11), with their county breakdowns."""
    from election import replay as R
    files = R.load_final(os.path.join(K.REPLAY_SOURCES, f"pa-{REPLAY}"))
    keep = {}
    for n, b in files.items():
        if "GetElectionList" in n or "GetOfficeNames" in n:
            keep[n] = b
        elif re.search(r"GetOfficeData_+officeId=2_", n):
            keep[n] = b
        elif re.search(r"GetOfficeData_+officeId=11_", n):
            doc = unjson(b)
            for o, blocks in doc["Election"].items():
                doc["Election"][o] = [{k: v for k, v in blk.items() if k.split("$$")[0] in ("1st Congressional District", "15th Congressional District")}
                                      for blk in blocks]
            keep[n] = json.dumps(json.dumps(doc)).encode("utf-8")
        elif re.search(r"GetCountyBreak_+officeId=(2_districtId=1|11_districtId=(2|16))_", n):
            keep[n] = b
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
    rd = read(list(files.items()), {"election": {"nov3_id": REPLAY}})
    ok = check_reading(rd, say, need=2)
    us = units(files)
    half = {u[0] for u in us[: len(us) // 2]}
    rd2 = read(list(reveal(files, half, 1).items()), {"election": {"nov3_id": REPLAY}})
    ok2 = not rd2["problems"] and all(
        sum(r["votes"] for r in c["rows"] if r["unit"] == "all" and r["type"] == "total") ==
        sum(r["votes"] for r in c["rows"] if r["unit"] != "all" and r["type"] == "total") for c in rd2["contests"]
        if any(u["kind"] == "county" for u in c["units"]))
    say(f"  {'ok  ' if ok2 else 'FAIL'} a rehearsal step with {len(half)} of {len(us)} counties in reads and adds up")
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
