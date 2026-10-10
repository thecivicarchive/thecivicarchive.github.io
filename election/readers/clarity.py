"""election/readers/clarity.py - results from Clarity Elections sites (Scytl/Civica "ENR"): Iowa, Colorado, South
Carolina and West Virginia (ARCHITECTURE.md 7), each on the state's own Clarity address.

What is asked, through election/source.py (the kit's honest User-Agent, one request at a time, a second apart):
  <base>/<EID>/current_ver.txt                       the cheap "what's new": a version number, every 2 minutes
  <base>/<EID>/<version>/reports/detailxml.zip       only when the version changed: detail.xml, every contest, choice
                                                     and county, with each vote type (Election Day, absentee, early...)
  <base>/elections.json                              for `run_night.py discover` (the list of elections)
<base> is the registry's signal address up to <EID> (https://electionresults.iowa.gov/IA/ and so on).

A county's own Clarity page (Oakland County, Michigan: results.enr.clarityelections.com/MI/Oakland/<EID>/) is read the
same way when the entry carries "partial": {"county": "26125", "name": "Oakland County"}: only federal and statewide
contests, each as "<race id>@<county>" at level "partial" and titled "(Oakland County only)", so that no page takes
one county's count for the state's. Michigan publishes no statewide count on the night; the county is a labelled part.

What is kept (an allowlist; detail.xml holds nothing else, no contact detail of any kind): the file's own timestamp;
each contest's key, title, "vote for", precincts reported and participating, by county; each choice's name, party and
votes, by vote type and county. Ballot questions and local contests are listed, never shown.

Units: each county (its five-digit FIPS code, from the county names through the state's crosswalk) and "all" (the
whole contest, the file's own totals). Rows: every county and choice as a total and by vote type; the counties must
add up to the file's own contest totals, or the snapshot is held.

    python -m election.readers.clarity --selftest
    python -m election.readers.clarity --replay ia 126082     a past election, fetched once (politely) and kept in
                                                              election_cache/replay/sources/, read, and compared
                                                              with the certified figures in the ballot databases
"""

import argparse
import datetime as dt
import gzip
import io
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
import zipfile

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from election.readers import _n9_match as X  # noqa: E402
from election.source import Refused, SourceError  # noqa: E402

FAMILY = "clarity"
FIXTURE = os.path.join(X.FIXTURES, "clarity", "wv_2026_primary_federal_detail.xml")
ZONES = {"EST": -5, "EDT": -4, "CST": -6, "CDT": -5, "MST": -7, "MDT": -6, "PST": -8, "PDT": -7, "AKST": -9, "AKDT": -8, "HST": -10}
VOTE_TYPES = [(r"election\s*day|polls|in[- ]person on election", "election_day"), (r"early", "early"),
              (r"absentee by mail|mail", "mail"), (r"absentee", "absentee"), (r"provi|failsafe", "provisional")]


# ============================================================================================== addresses

def base_of(entry):
    """The Clarity base address of the state (or of a county, for a partial source), ending in '/'."""
    sig = (entry.get("cadence") or {}).get("signal") or ""
    m = re.match(r"(https://[^<]+?/)<[^>]+>/current_ver\.txt$", sig)
    if not m:
        raise ValueError(f"the registry's signal address is not a Clarity address: {sig!r}")
    return m.group(1)


def election_id(entry):
    v = str((entry.get("election") or {}).get("nov3_id") or "").strip()
    return v if re.fullmatch(r"\d{5,7}", v) else None


def _body(resp):
    """A response's bytes; Clarity sends some files gzipped whatever was asked."""
    b = resp.body or b""
    return gzip.decompress(b) if b[:2] == b"\x1f\x8b" else b


def _need(resp):
    if resp.refused:
        raise Refused(resp.url, resp.why)
    if not resp.ok:
        raise SourceError(f"{resp.status} from {resp.url}")
    return _body(resp)


# ============================================================================================== the reader's three steps

def check(src, entry):
    eid = election_id(entry)
    if not eid:
        return None
    r = src.get(base_of(entry) + f"{eid}/current_ver.txt", state=entry.get("code"), accept="text/plain")
    if r.refused:
        raise Refused(r.url, r.why)
    if r.status == 404:
        return None
    if not r.ok:
        raise SourceError(f"{r.status} from {r.url}")
    ver = _body(r).decode("utf-8", "replace").strip()
    if not re.fullmatch(r"\d{1,9}", ver):
        raise SourceError(f"current_ver.txt did not hold a version number ({ver[:40]!r})")
    return {"version": ver, "time": None}


def fetch(src, entry, version):
    eid = election_id(entry)
    base = base_of(entry)
    url = base + f"{eid}/{version}/reports/detailxml.zip"
    body = _need(src.get(url, state=entry.get("code"), accept="application/zip"))
    if body[:2] != b"PK":
        raise SourceError(f"detailxml.zip was not a zip file ({len(body)} bytes)")
    return [(base + f"{eid}/current_ver.txt", str(version).encode()), (url, body)]


def discover(src, entry):
    """{"nov3_id", "note"} from the state's list of elections; one request."""
    r = src.get(base_of(entry) + "elections.json", state=entry.get("code"), accept="application/json")
    if r.refused:
        raise Refused(r.url, r.why)
    if not r.ok:
        return {"note": f"its list of elections answered {r.status}; the id is found on the state's results page"}
    try:
        rows = json.loads(_body(r).decode("utf-8-sig"))
    except ValueError:
        return {"note": "its list of elections did not read"}
    for e in rows if isinstance(rows, list) else []:
        if str(e.get("Date", "")).startswith("11/3/2026") and not e.get("County"):
            return {"nov3_id": str(e.get("EID")), "note": e.get("ElectionName")}
    if not (isinstance(rows, list) and rows):
        return {"note": "its list of elections is empty; the Nov 3 id is linked from the state's results page in late October"}
    return {"note": f"not listed yet; newest: {rows[0].get('ElectionName')} ({rows[0].get('EID')})"}


# ============================================================================================== reading detail.xml

def detail_xml(files):
    """The detail.xml text from the fetched files (a zip, or the XML itself when a test passes it bare)."""
    for name, body in files:
        b = body if isinstance(body, (bytes, bytearray)) else str(body).encode()
        if b[:2] == b"\x1f\x8b":
            b = gzip.decompress(b)
        if b[:2] == b"PK":
            z = zipfile.ZipFile(io.BytesIO(b))
            names = [n for n in z.namelist() if n.lower().endswith(".xml")]
            if names:
                return z.read(names[0]).decode("utf-8-sig")
        if b.lstrip()[:5] in (b"<?xml", b"<Elec") or b.lstrip()[:20].startswith(b"<?xml"):
            return b.decode("utf-8-sig")
    return None


def source_time(text):
    """'6/15/2026 10:42:37 AM EDT' -> '2026-06-15T14:42:37Z'."""
    m = re.match(r"\s*(\d{1,2})/(\d{1,2})/(\d{4}) (\d{1,2}):(\d{2}):(\d{2}) ([AP]M)(?: ([A-Z]{2,4}))?", text or "")
    if not m:
        return None
    mo, d, y, h, mi, s, ap, z = m.groups()
    h = int(h) % 12 + (12 if ap == "PM" else 0)
    off = ZONES.get(z or "", None)
    if off is None:
        return None
    t = dt.datetime(int(y), int(mo), int(d), h, int(mi), int(s)) - dt.timedelta(hours=off)
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def vote_type(name):
    w = (name or "").lower()
    for pat, vt in VOTE_TYPES:
        if re.search(pat, w):
            return vt
    return "other"


def read(files, entry, matcher=None):
    code = (entry.get("code") or "").upper()
    m = matcher or X.Matcher(code)
    text = detail_xml(files)
    reading = {"state": code, "feed": f"{code.lower()}-{FAMILY}", "contests": [], "unmatched": [], "problems": []}
    if text is None:
        reading["problems"].append("no detail.xml among the files")
        return reading
    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        reading["problems"].append(f"detail.xml did not parse ({e})")
        return reading
    if root.tag != "ElectionResult":
        reading["problems"].append(f"detail.xml begins with <{root.tag}>, not <ElectionResult>")
        return reading
    reading["source_time"] = source_time(root.findtext("Timestamp"))
    reading["election_name"] = (root.findtext("ElectionName") or "").strip()
    primary = "primar" in reading["election_name"].lower()
    region = (root.findtext("Region") or "").strip()
    partial = entry.get("partial") or None          # a county's own Clarity page, read as a labelled partial source
    if partial and region and X.county_word(region) != X.county_word(partial.get("name")):
        reading["problems"].append(f"the file is for {region}, not {partial.get('name')}")
    elif not partial and region and code and region.upper() != code and "/" not in region:
        reading["problems"].append(f"the file is for {region}, not {code}")
    unknown_counties = set()
    seen = {}
    for c in root.iter("Contest"):
        title = (c.get("text") or "").strip()
        key = c.get("key") or title
        if c.get("isQuestion") == "true":
            reading["unmatched"].append({"key": key, "office": title, "why": "a ballot question, not a race"})
            continue
        choices_el = c.findall("Choice")
        _t, party = X.split_party(title)
        rid, why = m.resolve(title, names=[ch.get("text") for ch in choices_el],
                             party=None if party or not primary else "NP")      # a nonpartisan contest on a primary ballot
        if rid is None:
            reading["unmatched"].append({"key": key, "office": title, "why": why})
            continue
        if rid in seen:
            reading["unmatched"].append({"key": key, "office": title, "why": f"a second contest for {rid} (the first: {seen[rid]})"})
            continue
        seen[rid] = title
        ct = X.contest_base(m, rid, key, title)
        if partial:
            if ct["level"] not in ("federal", "statewide"):
                del seen[rid]
                reading["unmatched"].append({"key": key, "office": title, "why": "a county's partial count is read for federal and statewide races only"})
                continue
            # one county's share of a statewide count: its own race id and level, so that no page takes it for the state's
            ct.update(race_id=f"{rid}@{partial['county']}", level="partial", office=f"{title} ({partial['name']} only)")
            rid = ct["race_id"]
        ct["seats"] = int(c.get("voteFor") or 1)
        units = {"all": dict(X.UNIT_ALL)}
        rep = [{"unit": "all", "in": int(c.get("precinctsReported") or 0),
                "all": int(c.get("precinctsParticipating") or c.get("precinctsReporting") or 0), "ballots": None, "registered": None}]
        for pc in c.findall("ParticipatingCounties/County"):
            f = m.county(pc.get("name"))
            if not f:
                unknown_counties.add(pc.get("name"))
                continue
            units[f] = X.unit_county(code, f, pc.get("name"))
            rep.append({"unit": f, "in": int(pc.get("precinctsReported") or 0), "all": int(pc.get("precinctsParticipating") or 0),
                        "ballots": None, "registered": None})
        rows, choices = [], []
        for i, ch in enumerate(choices_el, 1):
            line = m.choice(rid, ch.get("text"), ch.get("party") or party, order=i)
            choices.append(line)
            k = line["key"]
            total = int(ch.get("totalVotes") or 0)
            by_county, typed = {}, []
            vt_sum = 0
            for vt in ch.findall("VoteType"):
                kind = vote_type(vt.get("name"))
                vt_votes = int(vt.get("votes") or 0)
                vt_sum += vt_votes
                csum = 0
                for cc in vt.findall("County"):
                    f = m.county(cc.get("name"))
                    v = int(cc.get("votes") or 0)
                    csum += v
                    if not f:
                        unknown_counties.add(cc.get("name"))
                        continue
                    by_county.setdefault(f, {}).setdefault(kind, 0)
                    by_county[f][kind] += v
                if vt.findall("County") and csum != vt_votes:
                    reading["problems"].append(f"{title}, {line['name']}, {vt.get('name')}: counties add to {csum:,}, the file says {vt_votes:,}")
                typed.append((kind, vt_votes))
            if typed and vt_sum != total:
                reading["problems"].append(f"{title}, {line['name']}: vote types add to {vt_sum:,}, the file says {total:,}")
            rows.append({"unit": "all", "choice": k, "type": "total", "votes": total})
            agg = {}
            for kind, v in typed:
                agg[kind] = agg.get(kind, 0) + v
            if len(agg) > 1:
                rows.extend({"unit": "all", "choice": k, "type": kind, "votes": v} for kind, v in sorted(agg.items()))
            for f, kinds in sorted(by_county.items()):
                rows.append({"unit": f, "choice": k, "type": "total", "votes": sum(kinds.values())})
                if len(agg) > 1:
                    rows.extend({"unit": f, "choice": k, "type": kind, "votes": v} for kind, v in sorted(kinds.items()))
        if len({ch["key"] for ch in choices}) != len(choices):
            reading["problems"].append(f"{title}: two lines share one name")
        ct.update({"unit_kind": "county", "units_all": len(units) - 1 or None, "choices": choices, "units": list(units.values()),
                   "rows": rows, "reporting": rep, "stated": [], "controls": []})
        reading["contests"].append(ct)
    if unknown_counties:
        reading["problems"].append("county names not in the crosswalk: " + ", ".join(sorted(n for n in unknown_counties if n)[:10]))
    return reading


# ============================================================================================== rehearsals

def units(files):
    """[(county name, county name, ballots cast)] from a final detail.xml, for the rehearsal's reveal order."""
    text = detail_xml(list(files.items()))
    root = ET.fromstring(text)
    return [(c.get("name"), c.get("name"), int(c.get("ballotsCast") or 0)) for c in root.findall("ElectionVoterTurnout/Counties/County")]


def reveal(files, keep, step):
    """The final files with only the counties in `keep` counted (the rest at zero, their precincts not in), under a new
    version number, so the reader's own check sees a change at every step."""
    ver_path = next(p for p in files if p.endswith("/current_ver.txt"))
    zip_path = next(p for p in files if p.endswith("/reports/detailxml.zip"))
    ver = files[ver_path].decode().strip()
    new_ver = f"{ver}{step:03d}"
    root = ET.fromstring(detail_xml([(zip_path, files[zip_path])]))
    ts = root.find("Timestamp")
    if ts is not None:
        ts.text = ""                                # a rehearsal's figures carry the time they are read, not the past file's
    for c in root.findall("ElectionVoterTurnout/Counties/County"):
        if c.get("name") not in keep:
            c.set("ballotsCast", "0")
            c.set("precinctsReported", "0")
    for c in root.iter("Contest"):
        rep = 0
        for pc in c.findall("ParticipatingCounties/County"):
            if pc.get("name") not in keep:
                pc.set("precinctsReported", "0")
            rep += int(pc.get("precinctsReported") or 0)
        c.set("precinctsReported", str(rep))
        for ch in c.findall("Choice"):
            tot = 0
            for vt in ch.findall("VoteType"):
                s = 0
                for cc in vt.findall("County"):
                    if cc.get("name") not in keep:
                        cc.set("votes", "0")
                    s += int(cc.get("votes") or 0)
                vt.set("votes", str(s))
                tot += s
            ch.set("totalVotes", str(tot))
    xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("detail.xml", xml)
    new_zip = zip_path.replace(f"/{ver}/reports/", f"/{new_ver}/reports/")
    return {ver_path: new_ver.encode(), new_zip: buf.getvalue()}


# ============================================================================================== checks

def selftest(say=print):
    """No network: the fixture (West Virginia's May 12, 2026 primary, U.S. Senate and House contests, cut from the
    state's own detail.xml) reads, ties to the 2026 races, adds up, and a reveal of half the counties reads too."""
    ok = True

    def expect(cond, what):
        nonlocal ok
        ok = ok and bool(cond)
        say(f"  {'ok  ' if cond else 'FAIL'} {what}")

    if not os.path.exists(FIXTURE):
        say(f"  FAIL the fixture is missing: {os.path.relpath(FIXTURE, HERE)}")
        return False
    xml = open(FIXTURE, "rb").read()
    entry = {"code": "WV"}
    r = read([("detail.xml", xml)], entry)
    ids = sorted(c["race_id"] for c in r["contests"])
    expect(not r["problems"], f"the fixture reads with no problem ({'; '.join(r['problems'][:3])})")
    expect(ids == ["2026-WV-H01~DEM", "2026-WV-H01~REP", "2026-WV-H02~DEM", "2026-WV-H02~REP", "2026-WV-S2~DEM", "2026-WV-S2~REP"],
           f"six primary contests tied to the 2026 races ({', '.join(ids)})")
    sen = next(c for c in r["contests"] if c["race_id"] == "2026-WV-S2~REP")
    cap = next(ch for ch in sen["choices"] if ch["name"] == "SHELLEY MOORE CAPITO")
    tot = next(x["votes"] for x in sen["rows"] if x["unit"] == "all" and x["choice"] == cap["key"])
    cty = sum(x["votes"] for x in sen["rows"] if x["unit"] != "all" and x["choice"] == cap["key"] and x["type"] == "total")
    expect(tot == 80376 and cty == tot, f"Capito's 80,376 votes equal the 55 counties' sum ({cty:,})")
    expect(cap["ballot_name"] == "Shelley Moore Capito", f"the printed name is tied to the name as filed ({cap['ballot_name']})")
    expect(r.get("source_time") == "2026-06-15T14:42:37Z", f"the file's own time is read ({r.get('source_time')})")
    from election import store
    con = store.connect(":memory:")
    checks = store.run_checks(con, dict(r, state="WV", feed="wv-clarity"))
    expect(all(p for n, p, _d in checks if n in store.HARD), "the store's checks pass: " + "; ".join(f"{n} {'ok' if p else 'FAIL'}" for n, p, _d in checks))
    base = "results.enr.clarityelections.com/WV/126209/"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("detail.xml", xml)
    files = {base + "current_ver.txt": b"375698", base + "375698/reports/detailxml.zip": buf.getvalue()}
    us = units(files)
    keep = {u[0] for u in us[: len(us) // 2]}
    step = reveal(files, keep, 3)
    r2 = read([(k, v) for k, v in step.items()], entry)
    sen2 = next(c for c in r2["contests"] if c["race_id"] == "2026-WV-S2~REP")
    tot2 = next(x["votes"] for x in sen2["rows"] if x["unit"] == "all" and x["choice"] == cap["key"])
    expect(not r2["problems"] and 0 < tot2 < tot and any(k.endswith("375698003/reports/detailxml.zip") for k in step),
           f"a rehearsal step with {len(keep)} of {len(us)} counties reads and adds up ({tot2:,} of {tot:,})")
    say(f"  {'ok' if ok else 'FAIL'}: clarity reader self-test")
    return ok


def replay_check(code, eid, say=print, fetch_now=True):
    """A past election through the reader, kept in election_cache/replay/sources/<code>-<eid>/ (fetched once, politely,
    through election/source.py), read, and compared with the certified primary figures in the ballot databases."""
    from election import registry
    from election import replay as R
    from election.source import Source
    code = code.upper()
    entry = dict(registry.load(code), code=code)
    entry["election"] = dict(entry.get("election") or {}, nov3_id=str(eid))
    final = os.path.join(R.REPLAY_SOURCES, f"{code.lower()}-{eid}")
    if not os.path.isdir(final):
        if not fetch_now:
            say(f"{code}: no copy of election {eid} on disk")
            return None
        src = Source()
        sig = check(src, entry)
        if not sig:
            say(f"{code}: election {eid} is not posted")
            return None
        R.save_final(fetch(src, entry, sig["version"]), final)
    files = [(p, b) for p, b in R.load_final(final).items()]
    reading = read(files, entry)
    return reading, *X.compare_primary(code, reading, say=say)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--replay", nargs=2, metavar=("CODE", "EID"))
    a = ap.parse_args(argv)
    if a.selftest:
        return 0 if selftest() else 1
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
