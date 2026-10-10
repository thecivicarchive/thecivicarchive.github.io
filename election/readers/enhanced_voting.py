"""election/readers/enhanced_voting.py - Enhanced Voting results sites: Georgia, Virginia, Washington, Utah, Idaho and
Rhode Island (ARCHITECTURE.md 7). One platform, one reader.

Addresses (each state's site, checked 2026-10-09 and 2026-10-10 with the kit's own User-Agent; every one answered a
script with JSON and no challenge):
  <site>/results/public/api/jurisdictions/<J>                the state's list of elections (publicElectionId, date)
  <site>/results/public/api/elections/<j>/<id>               the election's record: lastUpdated, isOfficialResults,
                                                             isProduction (about 8 KB): the cheap "what's new" address
  <site>/results/public/api/elections/<j>/<id>/data          every contest: each candidate's votes, the same by count
                                                             group (Election Day, early, mail, provisional) where the
                                                             state reports them, each contest's reporting units
Read from it, and only these fields (an allowlist): the election's name, date, lastUpdated, isOfficialResults,
isProduction, isPrimary and parties; each contest's id, name, voteFor, voteTotal, reportingStatus (units in and in
all), partyName; each line's name, party, voteCount, isWriteIn and its count groups' names and votes.

Left out on purpose: the per-contest county breakdown (<data>/ballot-item/<id>) is the whole data file again plus the
breakdown, about 2.5 MB a contest in Virginia, too heavy to ask for every few minutes. The statewide figures, the
reporting units and the count groups are what the night needs from these six states.

In a rehearsal (Source with a replay) the record is not kept apart, so `check` reads the data file's own copy of it.
"""

import datetime as dt
import json
import re
import sys

from election.readers import _n10_common as C
from election.source import Refused, SourceError

FEED = None             # the updater's default: "<code>-enhanced_voting"
SITES = {               # state: (site, the jurisdiction's name in the elections address, in the jurisdictions address, unit kind)
    "GA": ("https://results.sos.ga.gov", "Georgia", "Georgia", "county"),
    "VA": ("https://enr.elections.virginia.gov", "virginia", "Virginia", "locality"),
    "WA": ("https://results.votewa.gov", "washington", "washington", "county"),
    "UT": ("https://electionresults.utah.gov", "Utah", "Utah", "county"),
    "ID": ("https://results.voteidaho.gov", "id", "id", "county"),
    "RI": ("https://electionresults.ri.gov", "RhodeIsland", "RhodeIsland", "town"),
}
ACCEPT = "application/json, text/plain, */*"


def _code(entry):
    return (entry.get("code") or "").upper()


def election_id(entry):
    """The election to read: the registry's Nov 3 id (or a rehearsal's past id), the first word of it only."""
    raw = str(((entry.get("election") or {}).get("nov3_id")) or "").strip()
    m = re.match(r"[A-Za-z0-9_-]+", raw)
    return m.group(0) if m else None


def addresses(entry):
    code = _code(entry)
    site, j, _jj, _u = SITES[code]
    eid = election_id(entry)
    base = f"{site}/results/public/api/elections/{j}/{eid}"
    return base, base + "/data"


def _get(src, url, code):
    r = src.get(url, state=code, accept=ACCEPT)
    if r.refused:
        raise Refused(url, r.why or "refused")
    return r


def _json(body):
    return json.loads(body.decode("utf-8-sig"))


def utc(s):
    """The site's time ("2026-10-07T17:54:22.8002483Z") as the store writes times ("2026-10-07T17:54:22Z")."""
    if not s:
        return None
    m = re.match(r"(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)(?:\.\d+)?(Z|[+-]\d\d:\d\d)?$", str(s))
    if not m:
        return None
    t = dt.datetime.fromisoformat(m.group(1) + (m.group(2) or "Z").replace("Z", "+00:00"))
    return t.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------------------------- the updater's calls

def check(src, entry):
    """The election's lastUpdated (and whether it is marked official): None when the election is not posted."""
    code = _code(entry)
    if not election_id(entry):
        return None
    record, data = addresses(entry)
    url = data if getattr(src, "replay", None) is not None else record
    r = _get(src, url, code)
    if r.status == 404:
        return None
    if not r.ok:
        raise SourceError(f"answered {r.status}")
    doc = _json(r.body)
    el = doc.get("election") if isinstance(doc.get("election"), dict) else doc
    if not el.get("lastUpdated") and not el.get("id"):
        raise SourceError("the election record did not read")
    return {"version": f"{el.get('lastUpdated')}|{'official' if el.get('isOfficialResults') else 'count'}", "time": utc(el.get("lastUpdated"))}


def fetch(src, entry, version):
    code = _code(entry)
    _record, data = addresses(entry)
    r = _get(src, data, code)
    if not r.ok:
        raise SourceError(f"answered {r.status}")
    return [(data, r.body)]


def discover(src, entry):
    """The Nov 3 election's publicElectionId from the state's list of elections (one request)."""
    code = _code(entry)
    site, _j, jj, _u = SITES[code]
    url = f"{site}/results/public/api/jurisdictions/{jj}"
    r = _get(src, url, code)
    if not r.ok:
        raise SourceError(f"answered {r.status}")
    els = _json(r.body).get("elections") or []
    hits = [e for e in els if str(e.get("electionDate", ""))[:10] == C.ELECTION_DATE]
    if len(hits) == 1:
        return {"nov3_id": hits[0]["publicElectionId"], "note": C.text_of(hits[0].get("name"))}
    if hits:
        gen = [e for e in hits if re.search(r"general", C.text_of(e.get("name")), re.I)]
        if len(gen) == 1:
            return {"nov3_id": gen[0]["publicElectionId"], "note": f"{C.text_of(gen[0].get('name'))}; {len(hits)} elections that day"}
        return {"nov3_id": None, "note": f"{len(hits)} elections dated Nov 3; none chosen: " + "; ".join(e["publicElectionId"] for e in hits)}
    return {"nov3_id": None, "note": f"{len(els)} elections listed, none dated Nov 3 yet"}


def read(files, entry):
    code = _code(entry)
    body = None
    for name, b in files:
        if str(name).rstrip("/").endswith("/data") or body is None:
            body = b
    doc = _json(body)
    return read_doc(doc, entry)


def read_doc(doc, entry, cw=None):
    code = _code(entry)
    el = doc.get("election") or {}
    name = C.text_of(el.get("name"))
    primary = None
    eparty = None
    if el.get("isPrimary") or re.search(r"\bprimary\b", name, re.I):
        m = re.search(r"\b(Democratic|Republican|Libertarian|Green)\b", name)
        eparty = m.group(1) if m else None
        primary = C.party_code(eparty) if eparty else ""
    R = C.Reading(code, FEED or f"{code.lower()}-enhanced_voting", entry, primary=primary, cw=cw)
    R.source_time = utc(el.get("lastUpdated"))
    R.source_version = f"{el.get('lastUpdated')}|{'official' if el.get('isOfficialResults') else 'count'}"
    if el.get("isProduction") is False:
        R.test = True
    if not R.cw.get("races") and code != "DC":
        R.problems.append("the crosswalk for this state is not built")
    unit_kind = SITES.get(code, (None, None, None, "county"))[3]
    items = doc.get("ballotItems")
    if not isinstance(items, list):
        R.problems.append("the data file has no list of contests")
        return R.done()
    for it in items:
        key = str(it.get("id"))
        title = C.text_of(it.get("name"))
        if it.get("parentId"):
            R.skip(key, title, "a locality's own copy of a contest")
            continue
        bare, party = C.party_of_title(title, it.get("partyName"), eparty)
        if primary is None:
            party = None
        rid, race = R.tie(key, bare, party)
        if rid is None:
            R.skip(key, title, race)
            continue
        opts = ((it.get("summaryResults") or {}).get("ballotOptions")) or []
        lines, groups = [], {}
        for i, o in enumerate(opts):
            p = o.get("party") or {}
            plabel = C.text_of(p.get("name")) or p.get("standardName") or p.get("abbreviation") or None
            try:
                v = int(o.get("voteCount") or 0)
            except (TypeError, ValueError):
                R.problems.append(f"{title}: a vote count that is not a number")
                v = 0
            lines.append((C.text_of(o.get("name")), plabel, bool(o.get("isWriteIn")), v))
            gsum = 0
            for g in o.get("groupResults") or []:
                vt = C.vote_type(C.text_of(g.get("groupName")))
                groups.setdefault(vt, [0] * len(opts))[i] += int(g.get("voteCount") or 0)
                gsum += int(g.get("voteCount") or 0)
            if o.get("groupResults") and gsum != v:
                R.problems.append(f"{title}: {C.text_of(o.get('name'))}'s count groups add to {gsum:,}, not {v:,}")
        rs = it.get("reportingStatus") or {}
        vf = re.search(r"\d+", C.text_of(it.get("voteFor")) or "")
        seats = int(vf.group(0)) if vf else 1
        R.add(rid, race, key, title, lines, unit_kind, rs.get("reportingUnits"), rs.get("totalUnits"), seats=seats,
              stated_total=it.get("voteTotal"), groups=groups, party=party)
    return R.done()


# ---------------------------------------------------------------------------------------------- self-test on the fixture

def selftest(say=print):
    """Reads the fixture (election/fixtures/enhanced_voting/: a trimmed copy of Virginia's 2026 November General data,
    every figure zero, and of Georgia's official 2024 general data) and checks what it reads."""
    import os
    here = os.path.join(C.HERE, "election", "fixtures", "enhanced_voting")
    ok = True

    def expect(cond, what):
        nonlocal ok
        say(f"      {'ok  ' if cond else 'FAIL'} {what}")
        ok = ok and bool(cond)

    va = C.read_json(os.path.join(here, "va_2026_general_data.json"))
    rd = read_doc(va, {"code": "VA", "decision": {"default": "plurality", "rules": []}})
    ids = sorted(c["race_id"] for c in rd["contests"])
    expect("2026-VA-S2" in ids and "2026-VA-H07" in ids, f"Virginia's Senate and House contests tied to their races ({len(ids)})")
    s2 = next(c for c in rd["contests"] if c["race_id"] == "2026-VA-S2")
    expect([ch["ballot_name"] for ch in s2["choices"]][:2] == ["Mark R. Warner", "Bert Mizusawa"] and s2["choices"][-1]["write_in"],
           "each line tied to the name as filed; the write-in line kept apart")
    expect(all(u.get("why") for u in rd["unmatched"]), f"every other contest listed with a reason ({len(rd['unmatched'])})")
    st, checks, _page = C.store_roundtrip(rd)
    expect(st == "ok", f"the store takes the reading ({st})")
    ga = C.read_json(os.path.join(here, "ga_2024_general_data.json"))
    rd = read_doc(ga, {"code": "GA", "decision": {"default": "majority_runoff", "rules": []}})
    h = next((c for c in rd["contests"] if c["race_id"] == "2026-GA-H01"), None)
    expect(h is not None and h["rule"] == "majority_runoff" and h["reporting"][0] == {"unit": "all", "in": 15, "all": 15},
           "Georgia 2024's District 1 read, with its reporting counties and the runoff rule")
    tot = {r["choice"]: r["votes"] for r in h["rows"] if r["type"] == "total"} if h else {}
    ed = {r["choice"]: r["votes"] for r in h["rows"] if r["type"] == "election_day"} if h else {}
    expect(sum(tot.values()) == h["stated"][0]["total"] and sum(ed.values()) > 0, "the lines add to the contest's own total; Election Day kept apart")
    st, checks, _ = C.store_roundtrip(rd)
    expect(st == "ok", f"the store takes Georgia 2024 ({st})")
    return ok


if __name__ == "__main__":
    sys.exit(0 if selftest() else 1)
