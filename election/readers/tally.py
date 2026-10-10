"""election/readers/tally.py - results from the Tally / TotalResults election-night service: North Dakota
(api.resultsnd.sos.nd.gov, client north-dakota) and Arkansas (enr-results-api.totalresults.com, client arkansas).

What is asked, through election/source.py (the kit's honest User-Agent, one request at a time, a second apart):
  Election/GetElectionInfo?cId=<client>&electionID=<id>          the cheap "what's new" (versionID, lastUpdated,
                                                                  isOfficial), every 2 minutes; also parties, counties
  Contest/GetContestSearchList?cid=<client>&electionID=<id>      when the version changed: every contest's name, vote
                                                                  for, and its choices' names and parties
  Contest/GetContestResults?cId=<client>&electionID=<id>&contestType=<type>
                                                                  the counts, by contest and county, for each contest
                                                                  type this site reads (statewide, Congress, Legislature)
  Election/GetElectionList?cid=<client>                          for `run_night.py discover`
The service address and client come from the registry's signal address.

What is kept (an allowlist; the service carries no contact detail, and picture file names are never read): the
version, time and official flag; each contest's id, name, vote for, precincts reporting and in all, total votes; each
choice's id, name, party, write-in flag and votes, statewide and by county. The service's own winner marks are never
read ("isWinner" is left unset even when official, and a page never calls a race).

    python -m election.readers.tally --selftest
    python -m election.readers.tally --replay nd 346
"""

import argparse
import json
import os
import re
import sys
import urllib.parse

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from election.readers import _n9_match as X  # noqa: E402
from election.source import Refused, SourceError  # noqa: E402

FAMILY = "tally"
FIXTURE_DIR = os.path.join(X.FIXTURES, "tally")
LOCAL_TYPES = re.compile(r"county|city|munic|school|town|judic|judge|^other\b|\bother$|court|district attorney|special|park|precinct|ward|justice|"
                         r"question|measure|issue|proposal", re.I)
PARTY_PREFIX = re.compile(r"^(REP|DEM|LIB|GRN|CON|NP|NON)\s+(.+)$")


# ============================================================================================== addresses

def service(entry):
    """(service root ending in '/', client id) from the registry's signal address."""
    sig = (entry.get("cadence") or {}).get("signal") or ""
    u = urllib.parse.urlsplit(sig.split(" ")[0])
    q = {k.lower(): v for k, v in urllib.parse.parse_qsl(u.query)}
    if not u.scheme or "cid" not in q:
        raise ValueError(f"the registry's signal address is not a Tally address: {sig!r}")
    return f"{u.scheme}://{u.netloc}/", q["cid"]


def election_id(entry):
    v = str((entry.get("election") or {}).get("nov3_id") or "").strip()
    return v if re.fullmatch(r"\d{2,6}|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", v) else None


def _addr(root, what, **params):
    return root + what + "?" + urllib.parse.urlencode(params)


def _json(resp):
    if resp.refused:
        raise Refused(resp.url, resp.why)
    if not resp.ok:
        raise SourceError(f"{resp.status} from {resp.url}")
    try:
        return json.loads(resp.body.decode("utf-8-sig"))
    except ValueError as e:
        raise SourceError(f"the answer from {resp.url} was not JSON ({e})") from e


# ============================================================================================== the reader's three steps

def check(src, entry):
    eid = election_id(entry)
    if not eid:
        return None
    root, client = service(entry)
    r = src.get(_addr(root, "Election/GetElectionInfo", cId=client, electionID=eid), state=entry.get("code"), accept="application/json")
    if r.status == 404:
        return None
    d = _json(r)
    if not d.get("response") or d.get("errorMessage"):
        return None
    return {"version": str(d.get("versionID")), "time": d.get("lastUpdated"), "official": bool(d.get("isOfficial"))}


def wanted_types(info, entry):
    """The contest types to read: those whose description is not a local, judicial or question kind (or the crosswalk's
    hand-kept "tally_types")."""
    try:
        own = X.load(entry.get("code")).get("tally_types")
    except (OSError, ValueError):
        own = None
    if own:
        return list(own)
    types = (info.get("response") or {}).get("contestTypes") or {}
    return [code for code, t in types.items() if not LOCAL_TYPES.search(f"{t.get('description', '')} {code}")]


def fetch(src, entry, version):
    eid = election_id(entry)
    root, client = service(entry)
    st = entry.get("code")
    out = []

    def ask(a):
        r = src.get(a, state=st, accept="application/json")
        d = _json(r)                        # raises on a refusal, an error or an answer that is not JSON
        out.append((a, r.body))             # kept as the service sent it
        return d

    info = ask(_addr(root, "Election/GetElectionInfo", cId=client, electionID=eid))
    ask(_addr(root, "Contest/GetContestSearchList", cid=client, electionID=eid))
    for t in wanted_types(info, entry):
        ask(_addr(root, "Contest/GetContestResults", cId=client, electionID=eid, contestType=t))
    return out


def discover(src, entry):
    root, client = service(entry)
    d = _json(src.get(_addr(root, "Election/GetElectionList", cid=client), state=entry.get("code"), accept="application/json"))
    rows = d if isinstance(d, list) else (d.get("response") or [])
    for e in rows:
        if str(e.get("electionDate", "")).startswith("2026-11-03"):
            return {"nov3_id": str(e.get("electionID")), "note": e.get("electionName")}
    return {"note": "not listed yet; newest: " + ", ".join(f"{e.get('electionName')} ({e.get('electionDate', '')[:10]})" for e in rows[:2])}


# ============================================================================================== reading

def _sort(files):
    """{'info': doc, 'search': doc, 'results': [doc, ...]} by each file's own shape (names may be addresses or paths)."""
    out = {"info": None, "search": None, "results": []}
    for _name, body in files:
        try:
            d = json.loads((body if isinstance(body, (bytes, bytearray)) else str(body).encode()).decode("utf-8-sig"))
        except ValueError:
            continue
        r = d.get("response") if isinstance(d, dict) else None
        if not isinstance(r, dict):
            continue
        if "contestType" in r and "contests" in r:
            out["results"].append(d)
        elif "contests" in r:
            out["search"] = d
        elif "parties" in r or "contestTypes" in r:
            out["info"] = d
    return out


def _title(name):
    """(title, party) from 'Representative in Congress Republican' or 'REP U.S. Congress District 02'."""
    name = X.tidy(name)
    m = PARTY_PREFIX.match(name)
    if m:
        return m.group(2), X.party_code(m.group(1))
    t, p = X.split_party(name)
    return t, p


def read(files, entry, matcher=None):
    code = (entry.get("code") or "").upper()
    m = matcher or X.Matcher(code)
    got = _sort(files)
    reading = {"state": code, "feed": f"{code.lower()}-{FAMILY}", "contests": [], "unmatched": [], "problems": []}
    if not got["search"] or not got["results"]:
        reading["problems"].append("the contest list or the results are missing from the files")
        return reading
    info = got["info"] or {}
    head = got["results"][0]
    reading["source_time"] = head.get("lastUpdated") or info.get("lastUpdated")
    reading["source_version"] = head.get("versionID") or info.get("versionID")
    reading["official"] = bool(head.get("isOfficial"))
    parties = {k: (v.get("partyName") or k) for k, v in (((info.get("response") or {}).get("parties")) or {}).items()}
    versions = {d.get("versionID") for d in got["results"] if d.get("versionID")}
    if len(versions) > 1:
        reading["problems"].append(f"the results files carry different versions ({', '.join(sorted(versions))}): read again")
    primary = "primary" in str(((info.get("response") or {}).get("name")) or "").lower()
    listed = (got["search"].get("response") or {}).get("contests") or {}
    seen = {}
    read_ids = set()
    for doc in got["results"]:
        for cid, res in ((doc.get("response") or {}).get("contests") or {}).items():
            read_ids.add(cid)
            c = listed.get(cid)
            if not c:
                reading["problems"].append(f"contest {cid} has results but is not in the contest list")
                continue
            title, party = _title(c.get("contestName"))
            party = party or ("NP" if primary else None)       # a nonpartisan contest on a primary ballot
            names = {k: X.tidy(ch.get("name")) for k, ch in (c.get("choices") or {}).items()}
            rid, why = m.resolve(title, names=list(names.values()), party=party)
            if rid is None:
                reading["unmatched"].append({"key": cid, "office": c.get("contestName"), "why": why})
                continue
            if rid in seen:
                reading["unmatched"].append({"key": cid, "office": c.get("contestName"), "why": f"a second contest for {rid} (the first: {seen[rid]})"})
                continue
            seen[rid] = c.get("contestName")
            reading["contests"].append(_contest(m, code, rid, cid, c, res, names, parties, reading["problems"]))
    for cid, c in listed.items():
        if cid in read_ids:
            continue
        t, p = _title(c.get("contestName"))
        rid, _why = m.resolve(t, party=p)
        if rid:
            reading["unmatched"].append({"key": cid, "office": c.get("contestName"),
                                         "why": f"its contest type ({c.get('contestTypeCode')}) was not read; add it to the crosswalk's tally_types"})
    return reading


def _contest(m, code, rid, cid, c, res, names, parties, problems):
    title = c.get("contestName")
    ct = X.contest_base(m, rid, cid, X.tidy(title))
    ct["seats"] = int(c.get("voteFor") or 1)
    # A write-in line named in writeInChoices with no choice id of its own is a breakdown of the contest's write-in line
    # (North Dakota names the write-in candidates who passed a threshold): its votes are already in that line.
    have = {str(x.get("choiceID")) for x in res.get("choices") or []}
    lines = (res.get("choices") or []) + [w for w in (res.get("writeInChoices") or res.get("writeinChoices") or [])
                                          if w.get("choiceID") is not None and str(w.get("choiceID")) not in have]
    order = {k: ch.get("order") for k, ch in (c.get("choices") or {}).items()}
    choices, keys = [], {}
    for ln in lines:
        chid = str(ln.get("choiceID"))
        listed = (c.get("choices") or {}).get(chid) or {}
        nm = names.get(chid) or ("Write-in" if listed.get("isWriteIn") else f"choice {chid}")
        pid = (ln.get("partyID") or listed.get("partyID") or "").strip()
        line = m.choice(rid, nm, parties.get(pid, pid) or None, order=order.get(chid))
        if listed.get("isWriteIn"):
            line["write_in"] = True
        if line["key"] in {x["key"] for x in choices}:
            line["key"] = f"{line['key']}-{chid}"
        choices.append(line)
        keys[chid] = line["key"]
    units = {"all": dict(X.UNIT_ALL)}
    rows, rep = [], [{"unit": "all", "in": res.get("precinctsReporting"), "all": res.get("totalPrecincts"), "ballots": None, "registered": None}]
    tot = 0
    for ln in lines:
        v = int(ln.get("totalVotes") or 0)
        tot += v
        rows.append({"unit": "all", "choice": keys[str(ln.get("choiceID"))], "type": "total", "votes": v})
    if res.get("totalVotes") is not None and tot != int(res["totalVotes"]):
        problems.append(f"{title}: its choices add to {tot:,}, the service says {int(res['totalVotes']):,}")
    by_choice = {}
    counties = 0
    for lid, loc in (res.get("locations") or {}).items():
        f = m.county(lid)
        if not f:
            continue
        counties += 1
        units[f] = X.unit_county(code, f)
        rep.append({"unit": f, "in": loc.get("precinctsReporting"), "all": loc.get("totalPrecincts"), "ballots": None, "registered": None})
        for ln in (loc.get("choices") or []) + [w for w in (loc.get("writeinChoices") or loc.get("writeInChoices") or [])
                                                if w.get("choiceID") is not None and str(w.get("choiceID")) not in have]:
            k = keys.get(str(ln.get("choiceID")))
            if k is None:
                problems.append(f"{title}: county {lid} has a choice the contest does not list")
                continue
            v = int(ln.get("totalVotes") or 0)
            by_choice[k] = by_choice.get(k, 0) + v
            rows.append({"unit": f, "choice": k, "type": "total", "votes": v})
    if counties and counties == len(res.get("locations") or {}):
        for r in rows:
            if r["unit"] == "all" and by_choice.get(r["choice"], 0) != r["votes"]:
                problems.append(f"{title}: the counties add to {by_choice.get(r['choice'], 0):,} for {r['choice']}, the service says {r['votes']:,}")
    ct.update({"unit_kind": "county" if counties else "race", "units_all": counties or None, "choices": choices, "units": list(units.values()),
               "rows": rows, "reporting": rep, "stated": [], "controls": []})
    return ct


# ============================================================================================== rehearsals

def _results_files(files):
    for path, body in files.items():
        try:
            d = json.loads(body.decode("utf-8-sig"))
        except ValueError:
            continue
        r = d.get("response") if isinstance(d, dict) else None
        if isinstance(r, dict) and "contestType" in r:
            yield path, d


def units(files):
    """[(county id, county id, votes cast in its biggest statewide contest)] for the rehearsal's reveal order."""
    best = {}
    for _p, d in _results_files(files):
        for res in (d["response"].get("contests") or {}).values():
            for lid, loc in (res.get("locations") or {}).items():
                best[lid] = max(best.get(lid, 0), int(loc.get("totalVotes") or 0))
    return [(k, k, v) for k, v in sorted(best.items())]


def reveal(files, keep, step):
    """The final files with only the counties in `keep` counted, under a new version id."""
    out = {}
    for path, body in files.items():
        try:
            d = json.loads(body.decode("utf-8-sig"))
        except ValueError:
            out[path] = body
            continue
        if isinstance(d, dict) and "versionID" in d:
            d["versionID"] = f"{d['versionID']}-r{step:03d}"
            d["lastUpdated"] = None                 # a rehearsal's figures carry the time they are read, not the past file's
        r = d.get("response") if isinstance(d, dict) else None
        if isinstance(r, dict) and "contestType" in r:
            for res in (r.get("contests") or {}).values():
                locs = res.get("locations") or {}
                if not locs:
                    continue
                sums, prec, tv = {}, 0, 0
                for lid, loc in locs.items():
                    if lid not in keep:
                        loc["precinctsReporting"] = 0
                        loc["totalVotes"] = 0
                        for ln in (loc.get("choices") or []) + (loc.get("writeinChoices") or []):
                            ln["totalVotes"] = 0
                    prec += int(loc.get("precinctsReporting") or 0)
                    tv += int(loc.get("totalVotes") or 0)
                    for ln in (loc.get("choices") or []) + (loc.get("writeinChoices") or []):
                        if ln.get("choiceID") is not None:
                            sums[str(ln["choiceID"])] = sums.get(str(ln["choiceID"]), 0) + int(ln.get("totalVotes") or 0)
                for ln in (res.get("choices") or []) + (res.get("writeInChoices") or []):
                    if ln.get("choiceID") is not None:
                        ln["totalVotes"] = sums.get(str(ln["choiceID"]), 0)
                    elif not keep.issuperset(locs):
                        ln["totalVotes"] = 0                # a breakdown of the write-in line: not kept part-way
                res["precinctsReporting"], res["totalVotes"] = prec, tv
        out[path] = json.dumps(d).encode()
    return out


# ============================================================================================== checks

def selftest(say=print):
    """No network: North Dakota's June 9, 2026 primary (the Representative in Congress and Secretary of State
    contests, cut from the service's own answers) reads, ties to the 2026 races, adds up by county, and a rehearsal
    step reads too."""
    ok = True

    def expect(cond, what):
        nonlocal ok
        ok = ok and bool(cond)
        say(f"  {'ok  ' if cond else 'FAIL'} {what}")

    names = ("info.json", "search.json", "results_sw.json")
    if not all(os.path.exists(os.path.join(FIXTURE_DIR, n)) for n in names):
        say("  FAIL the fixture files are missing (election/fixtures/tally/)")
        return False
    files = {n: open(os.path.join(FIXTURE_DIR, n), "rb").read() for n in names}
    entry = {"code": "ND"}
    r = read(list(files.items()), entry)
    ids = sorted(c["race_id"] for c in r["contests"])
    expect(not r["problems"], f"the fixture reads with no problem ({'; '.join(r['problems'][:3])})")
    expect(ids == ["2026-ND-H00~DEM", "2026-ND-H00~REP", "2026-ND-SOS~DEM", "2026-ND-SOS~REP"], f"four primary contests tied ({', '.join(ids)})")
    h = next(c for c in r["contests"] if c["race_id"] == "2026-ND-H00~REP")
    fed = next(ch for ch in h["choices"] if "Fedorchak" in ch["name"])
    tot = next(x["votes"] for x in h["rows"] if x["unit"] == "all" and x["choice"] == fed["key"])
    cty = sum(x["votes"] for x in h["rows"] if x["unit"] != "all" and x["choice"] == fed["key"])
    expect(tot == cty and len([u for u in h["units"] if u["kind"] == "county"]) == 53, f"Fedorchak's {tot:,} equal the 53 counties' sum")
    expect(fed["ballot_name"] == "Julie Fedorchak", f"tied to the name as filed ({fed['ballot_name']})")
    from election import store
    checks = store.run_checks(store.connect(":memory:"), dict(r, state="ND", feed="nd-tally"))
    expect(all(p for n, p, _d in checks if n in store.HARD), "the store's checks pass")
    us = units(files)
    keep = {u[0] for u in us[::2]}
    r2 = read(list(reveal(files, keep, 1).items()), entry)
    h2 = next(c for c in r2["contests"] if c["race_id"] == "2026-ND-H00~REP")
    tot2 = next(x["votes"] for x in h2["rows"] if x["unit"] == "all" and x["choice"] == fed["key"])
    expect(not r2["problems"] and 0 < tot2 < tot, f"a rehearsal step with {len(keep)} of {len(us)} counties adds up ({tot2:,})")
    say(f"  {'ok' if ok else 'FAIL'}: tally reader self-test")
    return ok


def make_fixture(say=print):
    """Cuts the fixture from a kept copy of North Dakota's 2026 primary (election_cache/replay/sources/nd-346/)."""
    from election import replay as R
    f = R.load_final(os.path.join(R.REPLAY_SOURCES, "nd-346"))
    want = {"20042REP", "20042DEM", "20283REP", "20283DEM"}
    os.makedirs(FIXTURE_DIR, exist_ok=True)
    for path, body in f.items():
        d = json.loads(body.decode("utf-8-sig"))
        r = d.get("response") or {}
        if "contestType" in r:
            if r["contestType"] != "SW":
                continue
            r["contests"] = {k: v for k, v in r["contests"].items() if k in want}
            name = "results_sw.json"
        elif "contests" in r:
            r["contests"] = {k: v for k, v in r["contests"].items() if k in want}
            r.pop("searchList", None)
            for c in r["contests"].values():
                for ch in c.get("choices", {}).values():
                    ch.pop("pictureFilename", None)
            name = "search.json"
        else:
            r = {k: r[k] for k in ("id", "name", "date", "parties", "contestTypes", "voteTypes") if k in r}
            d["response"] = r
            d["turnout"] = None
            name = "info.json"
        with open(os.path.join(FIXTURE_DIR, name), "w", encoding="utf-8") as fh:
            json.dump(d, fh, indent=0)
    say(f"fixture written to {os.path.relpath(FIXTURE_DIR, HERE)}")


def replay_check(code, eid, say=print, fetch_now=True):
    from election import registry
    from election import replay as R
    from election.source import Source
    code = code.upper()
    entry = dict(registry.load(code), code=code)
    entry["election"] = dict(entry.get("election") or {}, nov3_id=str(eid))
    final = os.path.join(R.REPLAY_SOURCES, f"{code.lower()}-{eid}")
    if not os.path.isdir(final):
        if not fetch_now:
            return None
        src = Source()
        sig = check(src, entry)
        if not sig:
            say(f"{code}: election {eid} is not posted")
            return None
        R.save_final(fetch(src, entry, sig["version"]), final)
    reading = read(list(R.load_final(final).items()), entry)
    return reading, *X.compare_primary(code, reading, say=say)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--make-fixture", action="store_true")
    ap.add_argument("--replay", nargs=2, metavar=("CODE", "ID"))
    a = ap.parse_args(argv)
    if a.make_fixture:
        make_fixture()
    if a.selftest:
        return 0 if selftest() else 1
    if a.replay:
        got = replay_check(*a.replay)
        if not got:
            return 1
        reading, equal, differ, missing = got
        print(f"{a.replay[0].upper()} {a.replay[1]}: {len(reading['contests'])} contests tied to races, {len(reading['unmatched'])} listed; "
              f"official: {reading.get('official')}; problems: {'; '.join(reading['problems'][:5]) or 'none'}")
        print(f"  certified primary totals: {len(equal)} races equal, {len(differ)} differ, {len(missing)} not in the feed")
        for k, sid, bad in differ:
            print(f"  DIFFER {k} ({sid}): " + "; ".join(bad[:4]))
        for k in missing:
            print(f"  MISSING {k}")
        return 0 if not differ else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
