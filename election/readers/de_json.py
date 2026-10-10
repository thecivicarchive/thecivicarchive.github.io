"""election/readers/de_json.py - the Delaware Department of Elections' results files (elections.delaware.gov/results/
enr/; ARCHITECTURE.md 7). Checked 2026-10-10: the 2026 primary's files answered a script; the Nov 3 code is expected to
be GE2026 (the primary's is PR2026) and is confirmed from the results index on the day.

  results/enr/Election_StatewideResults_ID_<code>.json           one row per line: the contest, party, candidate, and
                                                                 machine, absentee, early-voting and total votes, the
                                                                 election districts reported, the results type and the
                                                                 report time (Eastern time)
  results/enr/Election_ByCountyWithWilmington_ID_<code>.json     the same lines by county (New Castle, Kent, Sussex)
Read from them, and only these fields: Election Id, Election Name, Results Type, Total Precincts, Precincts Reported,
Party Name, Contest Title, Candidate Name, Pos, Machine Votes, Absentee Votes, Early Voting Votes, Total Votes,
ReportTime; and from the county file New Castle, Kent, Sussex and State.

There is no separate "what's new" address: `check` asks for the statewide file itself (about 30 KB) with the
conditions the server allows, and keeps it for `fetch`.
"""

import datetime as dt
import hashlib
import json
import re
import sys

from election.readers import _n10_common as C
from election.source import Refused, SourceError

FEED = None
BASE = "https://elections.delaware.gov/results/enr/"
COUNTIES = {"New Castle": "10003", "Kent": "10001", "Sussex": "10005"}
ACCEPT = "application/json, text/plain, */*"
_last = {}


def election_id(entry):
    raw = str(((entry.get("election") or {}).get("nov3_id")) or "").strip()
    m = re.match(r"[A-Za-z0-9]+", raw)
    return m.group(0) if m else None


def addresses(entry):
    eid = election_id(entry)
    return f"{BASE}Election_StatewideResults_ID_{eid}.json", f"{BASE}Election_ByCountyWithWilmington_ID_{eid}.json"


def _get(src, url, conditional=False):
    r = src.get(url, state="DE", accept=ACCEPT, conditional=conditional)
    if r.refused:
        raise Refused(url, r.why or "refused")
    return r


def _rows(body):
    d = json.loads(body.decode("utf-8-sig"))
    if not isinstance(d, list):
        raise ValueError("not a list of rows")
    return d


def votes(text):
    t = str(text if text is not None else "").replace(",", "").strip()
    if not re.fullmatch(r"\d+", t):
        raise ValueError(f"a vote count that is not a number ({text!r})")
    return int(t)


def report_time(rows):
    times = sorted({str(r.get("ReportTime")) for r in rows if r.get("ReportTime")})
    if not times:
        return None
    m = re.match(r"(\d{4}-\d\d-\d\dT\d\d:\d\d(?::\d\d)?)", times[-1])
    return C.local_to_utc(dt.datetime.fromisoformat(m.group(1)), -5) if m else None


def check(src, entry):
    if not election_id(entry):
        return None
    url, _c = addresses(entry)
    r = _get(src, url, conditional=True)
    if r.not_modified and url in _last:
        return {"version": _last[url][0], "time": _last[url][2]}
    if r.status == 404:
        return None
    if not r.ok:
        raise SourceError(f"answered {r.status}")
    try:
        rows = _rows(r.body)
    except ValueError as e:
        raise SourceError(f"the statewide file did not read ({e})")
    version = hashlib.sha256(r.body).hexdigest()[:16]
    t = report_time(rows)
    _last[url] = (version, r.body, t)
    return {"version": version, "time": t}


def fetch(src, entry, version):
    surl, curl = addresses(entry)
    got = _last.get(surl)
    if got and got[0] == version:
        body = got[1]
    else:
        r = _get(src, surl)
        if not r.ok:
            raise SourceError(f"answered {r.status}")
        body = r.body
    r = _get(src, curl)
    if not r.ok:
        raise SourceError(f"the county file answered {r.status}")
    return [(surl, body), (curl, r.body)]


def discover(src, entry):
    """Whether the Nov 3 files are posted under the expected code (one request)."""
    url, _c = addresses(dict(entry, election=dict(entry.get("election") or {}, nov3_id="GE2026")))
    r = _get(src, url)
    return {"nov3_id": "GE2026" if r.ok else None, "note": "the statewide file answers" if r.ok else f"GE2026 answered {r.status}"}


def read(files, entry):
    state, county = None, None
    for name, body in files:
        if "StatewideResults" in str(name):
            state = _rows(body)
        elif "ByCounty" in str(name):
            county = _rows(body)
    return read_rows(state or [], county, entry)


def read_rows(state, county, entry, cw=None):
    name = C.squash((state[0] if state else {}).get("Election Name"))
    primary = "" if re.search(r"primary", name, re.I) else None
    R = C.Reading("DE", FEED or "de-de_json", entry, primary=primary, cw=cw)
    R.source_time = report_time(state)
    R.source_version = hashlib.sha256(json.dumps(state, sort_keys=True).encode()).hexdigest()[:16]
    if not state:
        R.problems.append("the statewide file has no rows")
        return R.done()
    if any("test" in C.fold(r.get("Results Type")) for r in state):
        R.test = True
    contests = {}
    for r in state:
        party = C.squash(r.get("Party Name")) if primary is not None else ""
        key = (C.squash(r.get("Contest Title")), party)
        contests.setdefault(key, []).append(r)
    by_county = {}
    for r in county or []:
        party = C.squash(r.get("Party Name")) if primary is not None else ""
        by_county[(C.squash(r.get("Contest Title")), party, C.fold(r.get("Candidate Name")))] = r
    for (title, party), rows in contests.items():
        pcode = C.party_code(re.sub(r"\s+Party$", "", party)) if party else None
        rid, race = R.tie(title + (f" ({party})" if party else ""), title, pcode)
        if rid is None:
            R.skip(title + (f" ({party})" if party else ""), title, race)
            continue
        rows = sorted(rows, key=lambda r: (int(r.get("Pos") or 999), C.squash(r.get("Candidate Name"))))
        lines, groups, kv = [], {"election_day": [], "absentee": [], "early": []}, {}
        try:
            for r in rows:
                cname = C.squash(r.get("Candidate Name"))
                total = votes(r.get("Total Votes"))
                parts = [votes(r.get("Machine Votes")), votes(r.get("Absentee Votes")), votes(r.get("Early Voting Votes"))]
                if sum(parts) != total:
                    R.problems.append(f"{title}: {cname}'s machine, absentee and early votes add to {sum(parts):,}, not {total:,}")
                wi = bool(re.search(r"write[- ]?in", cname, re.I))
                lines.append((cname, C.squash(r.get("Party Name")) or None, wi, total))
                for vt, v in zip(("election_day", "absentee", "early"), parts):
                    groups[vt].append(v)
                c = by_county.get((title, party, C.fold(cname)))
                if county is not None:
                    if c is None:
                        R.problems.append(f"{title}: {cname} is missing from the county file")
                        kv = None
                    elif kv is not None:
                        cv = {u: votes(c.get(k)) for k, u in COUNTIES.items()}
                        if sum(cv.values()) != votes(c.get("State")) or votes(c.get("State")) != total:
                            R.problems.append(f"{title}: {cname}'s counties add to {sum(cv.values()):,}; the state figure is {total:,}")
                        for u, v in cv.items():
                            kv.setdefault(u, []).append(v)
        except ValueError as e:
            R.problems.append(f"{title}: {e}")
            continue
        pin, pall = rows[0].get("Precincts Reported"), rows[0].get("Total Precincts")
        meta = {u: {"kind": "county", "name": k, "map_id": u} for k, u in COUNTIES.items()}
        R.add(rid, race, title, title, lines, "precinct", int(pin) if pin is not None else None, int(pall) if pall is not None else None,
              by_unit=kv or None, unit_meta=meta, groups=groups, party=pcode)
    return R.done()


def selftest(say=print):
    import os
    here = os.path.join(C.HERE, "election", "fixtures", "de_json")
    ok = True

    def expect(cond, what):
        nonlocal ok
        say(f"      {'ok  ' if cond else 'FAIL'} {what}")
        ok = ok and bool(cond)

    s = C.read_json(os.path.join(here, "Election_StatewideResults_ID_PR2026.json"))
    c = C.read_json(os.path.join(here, "Election_ByCountyWithWilmington_ID_PR2026.json"))
    rd = read_rows(s, c, {"code": "DE"})
    sen = [x for x in rd["contests"] if x["race_id"].startswith("2026-DE-S2/")]
    expect(len(sen) >= 1 and not rd["problems"], f"the Senate primaries read, counties adding to the state ({len(sen)})")
    expect(any(r["type"] == "absentee" for r in sen[0]["rows"]) and any(r["unit"] == "10003" for r in sen[0]["rows"]),
           "absentee votes kept apart; New Castle County's figures kept")
    expect(rd["source_time"] == "2026-09-16T18:35:00Z", f"the report time in UTC ({rd['source_time']})")
    st, _c, _p = C.store_roundtrip(rd)
    expect(st == "ok", f"the store takes the reading ({st})")
    return ok


if __name__ == "__main__":
    sys.exit(0 if selftest() else 1)
