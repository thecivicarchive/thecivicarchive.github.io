"""election/readers/dc_boe.py - the District of Columbia Board of Elections' results site (electionresults.dcboe.org;
ARCHITECTURE.md 7). Checked 2026-10-10 with the kit's own User-Agent: every address answered a script with JSON.

  electionResults/getElectionResultsId               the list of elections (UrlText such as "2024-General-Election")
  electionResults/getElectionInfo/<UrlText>          LastUpdated, PrecinctsCounted, TotalPrecincts, the kind of results
                                                     ("Certified Results"), IsRCV: the cheap "what's new" address
  cityWide/getCityWide/<UrlText>                     every contest's totals: each line's name, party code and votes,
                                                     and the contest's total
Read from them, and only these fields: the election's date, LastUpdated, PrecinctsCounted, TotalPrecincts,
ElectionResultsTypeName and IsRCV; each contest's number, name and IsRCV; each line's Contestant, PartyCode, Votes and
TotalVotes. Over and under votes are lines in the file and are not candidates: they are left out.

The District has no race on the ballot lists yet (the Congress and the state and local ballot databases hold none).
Its crosswalk names two races by hand under "night_only" (the Delegate to the House and the Mayor, each with the
pattern of its title in the Board's file), and those contests are tied to them; every other contest is listed, not
shown, until the lists carry the District. The reader reads and checks everything regardless.
"""

import json
import re
import sys

from election.readers import _n10_common as C
from election.source import Refused, SourceError

FEED = None
SITE = "https://electionresults.dcboe.org/"
ACCEPT = "application/json, text/plain, */*"
NOT_CANDIDATES = re.compile(r"^(over ?votes|under ?votes|blank|blanks)$", re.I)
_last = {}


def _code(entry):
    return (entry.get("code") or "DC").upper()


def election_id(entry):
    raw = str(((entry.get("election") or {}).get("nov3_id")) or "").strip()
    m = re.match(r"[A-Za-z0-9_-]+", raw)
    return m.group(0) if m else None


def _get(src, url):
    r = src.get(url, state="DC", accept=ACCEPT)
    if r.refused:
        raise Refused(url, r.why or "refused")
    return r


def _json(body):
    return json.loads(body.decode("utf-8-sig"))


def utc(s):
    m = re.match(r"(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)", str(s or ""))
    return m.group(1) + "Z" if m else None


def check(src, entry):
    eid = election_id(entry)
    if not eid:
        return None
    url = f"{SITE}electionResults/getElectionInfo/{eid}"
    r = _get(src, url)
    if r.status == 404 or not r.body.strip() or r.body.strip() in (b"null", b"{}"):
        return None
    if not r.ok:
        raise SourceError(f"answered {r.status}")
    info = _json(r.body)
    if not isinstance(info, dict) or "LastUpdated" not in info:
        raise SourceError("the election's information did not read")
    version = f"{info.get('LastUpdated')}|{info.get('PrecinctsCounted')}|{info.get('ElectionResultsTypeName')}"
    _last[url] = (version, r.body)
    return {"version": version, "time": utc(info.get("LastUpdated"))}


def fetch(src, entry, version):
    eid = election_id(entry)
    iurl = f"{SITE}electionResults/getElectionInfo/{eid}"
    got = _last.get(iurl)
    if got and got[0] == version:
        info = got[1]
    else:
        r = _get(src, iurl)
        if not r.ok:
            raise SourceError(f"answered {r.status}")
        info = r.body
    curl = f"{SITE}cityWide/getCityWide/{eid}"
    r = _get(src, curl)
    if not r.ok:
        raise SourceError(f"the contests answered {r.status}")
    return [(iurl, info), (curl, r.body)]


def discover(src, entry):
    r = _get(src, SITE + "electionResults/getElectionResultsId")
    els = _json(r.body) if r.ok else []
    hits = [e for e in els if str(e.get("ElectionDate", ""))[:10] == C.ELECTION_DATE]
    if len(hits) == 1:
        return {"nov3_id": hits[0].get("UrlText"), "note": hits[0].get("ElectionName")}
    return {"nov3_id": None, "note": f"{len(hits)} elections dated Nov 3; newest listed: " + (els[0].get("UrlText") if els else "none")}


def contests_of(citywide):
    """[(number, name, rcv, [(printed name, party code, write-in, votes)], stated total, over/under left out)]"""
    out = []
    for c in citywide or []:
        lines, left = [], 0
        stated = None
        for x in c.get("ElectionData") or []:
            name = C.squash(x.get("Contestant"))
            votes = int(x.get("Votes") or 0)
            stated = x.get("TotalVotes", stated)
            if NOT_CANDIDATES.match(name):
                left += votes
                continue
            party = C.squash(x.get("PartyCode")) or None
            if party and name.startswith(party + " "):
                name = name[len(party) + 1:]
            wi = bool(re.fullmatch(r"(?i)write[- ]?ins?", name))
            lines.append((name, None if party in (None, "NPN") else party, wi, votes))
        out.append((str(c.get("ContestNumber")), C.squash(c.get("OfficeName")), bool(c.get("IsRCV")), lines,
                    int(stated) if stated is not None else None, left))
    return out


def read(files, entry):
    info, city = {}, []
    for name, body in files:
        d = _json(body)
        if "getElectionInfo" in str(name):
            info = d
        elif "getCityWide" in str(name):
            city = d
    return read_docs(info, city, entry)


def read_docs(info, city, entry, cw=None):
    R = C.Reading("DC", FEED or "dc-dc_boe", entry, primary=None, cw=cw)
    R.source_time = utc((info or {}).get("LastUpdated"))
    R.source_version = f"{(info or {}).get('LastUpdated')}|{(info or {}).get('PrecinctsCounted')}|{(info or {}).get('ElectionResultsTypeName')}"
    if not isinstance(city, list):
        R.problems.append("the contests file did not read")
        return R.done()
    pin, pall = (info or {}).get("PrecinctsCounted"), (info or {}).get("TotalPrecincts")
    night = (R.cw or {}).get("night_only") or {}
    for num, title, rcv, lines, stated, _left in contests_of(city):
        s = sum(v for _n, _p, _w, v in lines)
        if stated is not None and s != stated:
            R.problems.append(f"{title}: the lines add to {s:,}, the file's total is {stated:,}")
        fit = [rid for rid, e in sorted(night.items()) if e.get("titles") and re.search(e["titles"], C.squash(title), re.I)]
        if fit:
            if len(fit) > 1 or fit[0] in R.seen:
                R.skip(num, title, "more than one contest or race fits; none is guessed")
                continue
            e = night[fit[0]]
            R.seen[fit[0]] = title
            race = {"level": e.get("level") or "statewide", "kind": e.get("kind") or "other", "district": None, "cands": {}}
            R.add(fit[0], race, num, title, lines, "precinct", pin, pall, seats=int(e.get("seats") or 1), stated_total=stated, rcv=rcv)
            continue
        if not R.cw.get("races"):
            R.skip(num, title, "the District of Columbia has no races on the ballot lists yet")
            continue
        rid, race = R.tie(num, title)
        if rid is None:
            R.skip(num, title, race)
            continue
        R.add(rid, race, num, title, lines, "precinct", pin, pall, stated_total=stated, rcv=rcv)
    return R.done()


def selftest(say=print):
    import os
    here = os.path.join(C.HERE, "election", "fixtures", "dc_boe")
    ok = True

    def expect(cond, what):
        nonlocal ok
        say(f"      {'ok  ' if cond else 'FAIL'} {what}")
        ok = ok and bool(cond)

    info = C.read_json(os.path.join(here, "info_2024_general.json"))
    city = C.read_json(os.path.join(here, "citywide_2024_general.json"))
    rd = read_docs(info, city, {"code": "DC"})
    got = {t: ln for _n, t, _r, ln, _s, _l in contests_of(city)}
    dl = got.get("DELEGATE TO THE HOUSE OF REPRESENTATIVES FROM THE DISTRICT OF COLUMBIA") or []
    expect(("Eleanor Holmes Norton", "DEM", False, 251540) in dl, "the Delegate's lines read, the party code taken off the name")
    expect(not rd["problems"] and all(u["why"] for u in rd["unmatched"]), f"every contest adds up and is listed with a reason ({len(rd['unmatched'])})")
    night = C.load_crosswalk("DC").get("night_only") or {}
    tied = {c["race_id"]: c["office"] for c in rd["contests"]}
    if night.get("2026-DC-DELEGATE"):
        expect(tied.get("2026-DC-DELEGATE", "").startswith("DELEGATE TO THE HOUSE") and len(tied) == 1,
               f"the Delegate's contest tied to its night-only race, and nothing else (the shadow seats stay listed): {sorted(tied)}")
    if night.get("2026-DC-MAYOR"):
        mayor = [{"ContestNumber": 2, "OfficeName": "MAYOR OF THE DISTRICT OF COLUMBIA",
                  "ElectionData": [{"Contestant": "DEM A Person", "PartyCode": "DEM", "Votes": 3, "TotalVotes": 4},
                                   {"Contestant": "Write-in", "PartyCode": "", "Votes": 1, "TotalVotes": 4}]}]
        rm = read_docs(info, mayor, {"code": "DC"})
        expect([c["race_id"] for c in rm["contests"]] == ["2026-DC-MAYOR"], "a Mayor's contest tied to its night-only race")
    st, _c, _p = C.store_roundtrip(rd)
    expect(st == "ok", f"the store takes the reading ({st})")
    return ok


if __name__ == "__main__":
    sys.exit(0 if selftest() else 1)
