"""election/readers/pcc_ems.py - the PCC Technology Group's election management systems: Connecticut's CTEMS and
Vermont's Election Management System (ARCHITECTURE.md 7). Two layouts, one family; the state decides which is read.

Connecticut (ctemspublic.pcctg.net, checked 2026-10-10: every address answered a script, no challenge):
  ng-app/data/Elections.json                         the list of elections (ID, Name)
  ng-app/data/election/<id>/Version.json             {"Version": n}: the cheap "what's new" address
  ng-app/data/election/<id>/<n>/Lookupdata.json      offices (name, district), candidate lines (printed name and party
                                                     only: the file also carries an address field that is never read),
                                                     parties, towns
  .../stateVotes_Electiondata.json                   each line's statewide votes
  .../townVotes_Electiondata.json                    each line's votes town by town
  .../townStatus_Electiondata.json                   each town's status ("( Official Results )") and precincts in
  .../officePrecincts_Electiondata.json              each office's precincts in ("760 of 770 (98.7%)")
  A candidate nominated by several parties has a line for each; the lines are added together under the person, with
  every party named, as the ballot lists file them.

Vermont (static.electionresults.vermont.gov, checked 2026-10-10):
  elections/elections.json                           the list (electionGuid, date)
  elections/<guid>.json                              the index: lastUpdatedDate, townsReporting, and the address of
                                                     each part (federal, statewide, Senate, House), renamed at every
                                                     publish: the cheap "what's new" address
  elections/<guid>-<part>-<stamp>.json               each office: a STATE WIDE row with every line's total, and a row
                                                     for each town (a town split between House districts has a row
                                                     for each), each with its write-ins and districts reported ("1/1")
  Only these fields are read: office name and vote-for; each row's town id and name, districts reported; each line's
  name, party, votes and write-in mark.
"""

import hashlib
import json
import re
import sys

from election.readers import _n10_common as C
from election.source import Refused, SourceError

FEED = None
CT_DATA = "https://ctemspublic.pcctg.net/ng-app/data/"
VT_DATA = "https://static.electionresults.vermont.gov/"
CT_FILES = ("Lookupdata", "stateVotes_Electiondata", "townVotes_Electiondata", "townStatus_Electiondata", "officePrecincts_Electiondata")
VT_PARTS = ("federal", "stateWide", "senate", "house")
ACCEPT = "application/json, text/plain, */*"
_last = {}                  # the index read by check(), kept for fetch() so it is not asked twice


def _code(entry):
    return (entry.get("code") or "").upper()


def election_id(entry):
    raw = str(((entry.get("election") or {}).get("nov3_id")) or "").strip()
    m = re.match(r"[A-Za-z0-9-]+", raw)
    return m.group(0) if m else None


def _get(src, url, code):
    r = src.get(url, state=code, accept=ACCEPT)
    if r.refused:
        raise Refused(url, r.why or "refused")
    return r


def _json(body):
    return json.loads(body.decode("utf-8-sig"))


def ints(text):
    t = str(text if text is not None else "").replace(",", "").strip()
    return int(t) if re.fullmatch(r"-?\d+", t) else 0


# ---------------------------------------------------------------------------------------------- the updater's calls

def check(src, entry):
    code, eid = _code(entry), election_id(entry)
    if not eid:
        return None
    if code == "CT":
        url = f"{CT_DATA}election/{eid}/Version.json"
        r = _get(src, url, code)
        if r.status == 404:
            return None
        if not r.ok:
            raise SourceError(f"answered {r.status}")
        v = _json(r.body).get("Version")
        if v is None:
            raise SourceError("Version.json did not read")
        return {"version": str(v), "time": None}
    url = f"{VT_DATA}elections/{eid}.json"
    r = _get(src, url, code)
    if r.status == 404:
        return None
    if not r.ok:
        raise SourceError(f"answered {r.status}")
    idx = _json(r.body)
    paths = "|".join(str((idx.get(p) or {}).get("path") or "") for p in VT_PARTS)
    version = f"{idx.get('lastUpdatedDate')}|{hashlib.sha256(paths.encode()).hexdigest()[:12]}"
    _last[url] = (version, r.body)
    return {"version": version, "time": vt_time(idx.get("lastUpdatedDate"))}


def fetch(src, entry, version):
    code, eid = _code(entry), election_id(entry)
    out = []
    if code == "CT":
        out.append((f"{CT_DATA}election/{eid}/Version.json", json.dumps({"Version": int(version)}).encode()))
        for f in CT_FILES:
            url = f"{CT_DATA}election/{eid}/{version}/{f}.json"
            r = _get(src, url, code)
            if not r.ok:
                raise SourceError(f"{f} answered {r.status}")
            out.append((url, r.body))
        return out
    url = f"{VT_DATA}elections/{eid}.json"
    got = _last.get(url)
    if got and got[0] == version:
        body = got[1]
    else:
        r = _get(src, url, code)
        if not r.ok:
            raise SourceError(f"the index answered {r.status}")
        body = r.body
    out.append((url, body))
    idx = _json(body)
    for p in VT_PARTS:
        part = idx.get(p) or {}
        if not part.get("isEnable") or not part.get("path"):
            continue
        purl = VT_DATA + str(part["path"]).replace("\\", "/").lstrip("/")
        r = _get(src, purl, code)
        if not r.ok:
            raise SourceError(f"the {p} part answered {r.status}")
        out.append((purl, r.body))
    return out


def discover(src, entry):
    code = _code(entry)
    if code == "CT":
        r = _get(src, CT_DATA + "Elections.json", code)
        els = _json(r.body) if r.ok else []
        hits = [e for e in els if str(e.get("Name", "")).startswith("11/03/2026")]
        if len(hits) == 1:
            return {"nov3_id": hits[0]["ID"], "note": hits[0].get("Name")}
        return {"nov3_id": None, "note": f"{len(hits)} elections dated 11/03/2026"}
    r = _get(src, VT_DATA + "elections/elections.json", code)
    els = _json(r.body) if r.ok else []
    hits = [e for e in els if str(e.get("electionDate", ""))[:10] == C.ELECTION_DATE and e.get("isStateWideElection")]
    if len(hits) == 1:
        return {"nov3_id": hits[0]["electionGuid"], "note": hits[0].get("electionName")}
    return {"nov3_id": None, "note": f"{len(hits)} statewide elections dated Nov 3"}


def vt_time(s):
    """Vermont's "10/10/2026 06:06 AM" (Eastern time) in UTC."""
    import datetime as dt
    m = re.match(r"(\d\d)/(\d\d)/(\d{4}) (\d\d):(\d\d) (AM|PM)", str(s or ""))
    if not m:
        return None
    mo, d, y, h, mi, ap = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4)) % 12, int(m.group(5)), m.group(6)
    h += 12 if ap == "PM" else 0
    local = dt.datetime(y, mo, d, h, mi)
    # Eastern daylight time to the first Sunday of November at 2 a.m., standard time after
    first = dt.date(y, 11, 1)
    end = first + dt.timedelta(days=(6 - first.weekday()) % 7)
    mar = dt.date(y, 3, 1)
    start = mar + dt.timedelta(days=(6 - mar.weekday()) % 7 + 7)
    dst = dt.datetime(start.year, start.month, start.day, 2) <= local < dt.datetime(end.year, end.month, end.day, 2)
    t = local + dt.timedelta(hours=4 if dst else 5)
    return t.strftime("%Y-%m-%dT%H:%M:00Z")


def read(files, entry):
    code = _code(entry)
    docs = {}
    for name, body in files:
        docs[str(name)] = _json(body)
    return read_ct(docs, entry) if code == "CT" else read_vt(docs, entry)


# ---------------------------------------------------------------------------------------------- Connecticut

def _ct_doc(docs, stem):
    for k, v in docs.items():
        if k.rsplit("/", 1)[-1].startswith(stem):
            return v
    return None


def read_ct(docs, entry, cw=None):
    code = "CT"
    look = _ct_doc(docs, "Lookupdata") or {}
    state = _ct_doc(docs, "stateVotes") or {}
    towns = _ct_doc(docs, "townVotes") or {}
    status = _ct_doc(docs, "townStatus") or {}
    precincts = _ct_doc(docs, "officePrecincts") or {}
    ver = _ct_doc(docs, "Version.json") or {}
    el = look.get("election") or {}
    party_el = (el.get("P") or "").strip()
    primary = None if el.get("ET") == "G" or not party_el else C.party_code({"D": "DEM", "R": "REP"}.get(party_el, party_el)) or ""
    R = C.Reading(code, FEED or "ct-pcc_ems", entry, primary=primary, cw=cw)
    R.source_version = str(ver.get("Version")) if ver else None
    if not look or not isinstance(look.get("officeList"), list):
        R.problems.append("Lookupdata did not read")
        return R.done()
    parties = {pid: C.squash(p.get("NM")) for pid, p in (look.get("partyIds") or {}).items()}
    lines_of = {}                                            # candidate line id -> (printed name, party): nothing else is read
    for cid, rec in (look.get("candidateIds") or {}).items():
        lines_of[cid] = (C.squash(rec.get("NM")), parties.get(rec.get("P"), rec.get("P")))
    town_names = {str(t): C.squash(n) for t, n in (look.get("townIds") or {}).items()}
    for group in look["officeList"]:
        for oid, o in group.items():
            title = C.squash(o.get("NM"))
            pcode = primary if primary else None
            rid, race = R.tie(oid, title, pcode)
            if rid is None:
                R.skip(oid, title, race)
                continue
            order, people = [], {}
            for cell in state.get(oid) or []:
                for cid, v in cell.items():
                    name, party = lines_of.get(cid, (None, None))
                    if not name:
                        R.problems.append(f"{title}: a line with no name in Lookupdata ({cid})")
                        continue
                    k = C.fold(name)
                    if k not in people:
                        order.append(k)
                        people[k] = {"name": name, "parties": [], "votes": 0, "cids": [], "wi": bool(re.search(r"write[- ]?in", name, re.I))}
                    if party and party not in people[k]["parties"]:
                        people[k]["parties"].append(party)
                    people[k]["votes"] += ints(v.get("V"))
                    people[k]["cids"].append(cid)
            pos = {cid: i for i, k in enumerate(order) for cid in people[k]["cids"]}
            by_town, meta = {}, {}
            for tid, offs in towns.items():
                if oid not in offs:
                    continue
                vals = [0] * len(order)
                for cell in offs[oid]:
                    for cid, v in cell.items():
                        if cid in pos:
                            vals[pos[cid]] += ints(v.get("V"))
                        else:
                            R.problems.append(f"{title}: town {tid} has a line the state total lacks")
                uid = f"CT-T{int(tid):03d}" if str(tid).isdigit() else f"CT-T{tid}"
                by_town[uid] = vals
                pr = re.match(r"\s*(\d+) of (\d+)", str((status.get(tid) or {}).get("PR") or ""))
                meta[uid] = {"kind": "town", "name": town_names.get(str(tid)), "in": int(pr.group(1)) if pr else None,
                             "all": int(pr.group(2)) if pr else None}
            for i, k in enumerate(order):
                summed = sum(v[i] for v in by_town.values())
                if by_town and summed != people[k]["votes"]:
                    R.problems.append(f"{title}: {people[k]['name']}'s towns add to {summed:,}, the state total is {people[k]['votes']:,}")
            m = re.match(r"\s*(\d+) of (\d+)", str(precincts.get(oid) or ""))
            lines = [(people[k]["name"], ", ".join(people[k]["parties"]) or None, people[k]["wi"], people[k]["votes"]) for k in order]
            R.add(rid, race, oid, title, lines, "precinct", int(m.group(1)) if m else None, int(m.group(2)) if m else None,
                  by_unit=by_town, unit_meta=meta, party=pcode)
    # the newest official mark: a town's status is the only time-free mark the files carry
    return R.done()


# ---------------------------------------------------------------------------------------------- Vermont

def read_vt(docs, entry, cw=None):
    code = "VT"
    idx = next((v for k, v in docs.items() if isinstance(v, dict) and "electionDetails" in v), {})
    det = idx.get("electionDetails") or {}
    name = C.squash(det.get("electionName"))
    primary = "" if re.search(r"primary", name, re.I) else None
    R = C.Reading(code, FEED or "vt-pcc_ems", entry, primary=primary, cw=cw)
    R.source_time = vt_time(idx.get("lastUpdatedDate"))
    R.source_version = idx.get("lastUpdatedDate")
    for k, d in docs.items():
        if not (isinstance(d, dict) and isinstance(d.get("d"), list)):
            continue
        for grp in d["d"]:
            gparty = C.squash(grp.get("pn")) or None
            for o in grp.get("o") or []:
                title = C.squash(o.get("on"))
                oid = str(o.get("oid"))
                pcode = C.party_code(gparty) if primary is not None and gparty else (None if primary is None else "")
                if o.get("dn") and o.get("isrep") is not None:          # the Legislature: the district is named, not numbered
                    dn = C.squash(str(o["dn"]).rstrip("_ "))
                    kind = "state_house" if o.get("isrep") else "state_senate"
                    fit = [k for k, r in (R.cw.get("races") or {}).items() if r["kind"] == kind and C.fold(r.get("district")) == C.fold(dn)]
                    title = f"{title} {dn}"
                    oid = f"{oid}-{o.get('dc') or dn}"
                    rid, race = R.tie_rid(fit[0], title, pcode) if len(fit) == 1 else (None, "no 2026 race on the ballot lists for this district"
                                                                                      if not fit else "more than one race fits; none is guessed")
                else:
                    rid, race = R.tie(oid, title, pcode)
                if rid is None:
                    R.skip(oid, title, race)
                    continue
                rows = o.get("cs") or []
                sw = [c for c in rows if not c.get("tid")]
                towns = [c for c in rows if c.get("tid")]
                if len(sw) != 1:
                    R.problems.append(f"{title}: {len(sw)} STATE WIDE rows")
                    continue
                order, names, parties, wis = [], {}, {}, {}
                for r in sw[0].get("rc") or []:
                    cid = str(r.get("cid"))
                    order.append(cid)
                    names[cid] = C.squash(r.get("cn"))
                    parties[cid] = C.squash(r.get("pn")) or None
                    wis[cid] = bool(r.get("isWriteIn"))
                tot = {cid: 0 for cid in order}
                for r in sw[0].get("rc") or []:
                    tot[str(r.get("cid"))] += ints(r.get("vc"))
                wi_total = sum(ints(r.get("vc")) for r in sw[0].get("wc") or [])
                lines = [(names[c], parties[c], wis[c], tot[c]) for c in order] + [("Write-in", None, True, wi_total)]
                by_town, meta, done = {}, {}, {}
                for c in towns:
                    uid = f"VT-T{int(c['tid']):03d}"
                    vals = by_town.setdefault(uid, [0] * (len(order) + 1))
                    for r in c.get("rc") or []:
                        cid = str(r.get("cid"))
                        if cid in tot:
                            vals[order.index(cid)] += ints(r.get("vc"))
                        else:
                            R.problems.append(f"{title}: a town line the STATE WIDE row lacks ({cid})")
                    for r in c.get("wc") or []:              # a write-in a town counted by name may be a line of its own statewide
                        cid = str(r.get("cid"))
                        vals[order.index(cid) if cid in tot else -1] += ints(r.get("vc"))
                    m = re.match(r"(\d+)/(\d+)", str(c.get("distReported") or ""))
                    a, b = (int(m.group(1)), int(m.group(2))) if m else (0, 0)
                    x = done.setdefault(uid, [0, 0])
                    x[0] += a
                    x[1] += b
                    meta[uid] = {"kind": "town", "name": C.squash(c.get("tn"))}
                towns_in = sum(1 for x in done.values() if x[1] and x[0] >= x[1])
                for uid, x in done.items():
                    meta[uid]["in"], meta[uid]["all"] = (1 if x[1] and x[0] >= x[1] else 0), 1
                for i in range(len(lines)):
                    s = sum(v[i] for v in by_town.values())
                    if by_town and s != lines[i][3]:
                        R.problems.append(f"{title}: {lines[i][0]}'s towns add to {s:,}, the STATE WIDE row says {lines[i][3]:,}")
                R.add(rid, race, oid, title, lines, "town", towns_in, len(done), seats=int(o.get("vf") or 1),
                      by_unit=by_town, unit_meta=meta, party=pcode)
    if not idx:
        R.problems.append("the election's index was not among the files")
    return R.done()


# ---------------------------------------------------------------------------------------------- rehearsals

def _items(files):
    return list(files.items()) if isinstance(files, dict) else list(files)


def units(files):
    """[(town, "", size)] for a rehearsal: every town in the files, sized by the votes it cast in its first office."""
    size = {}
    for name, body in _items(files):
        n = str(name)
        if n.endswith("townVotes_Electiondata.json"):                  # Connecticut
            for tid, offs in _json(body).items():
                size[f"CT-{tid}"] = sum(ints(v.get("V")) for cells in list(offs.values())[:1] for cell in cells for v in cell.values())
        elif re.search(r"-f-\d+\.json$", n):                            # Vermont's federal part
            d = _json(body)
            for grp in d.get("d") or []:
                for o in (grp.get("o") or [])[:1]:
                    for c in o.get("cs") or []:
                        if c.get("tid"):
                            k = f"VT-{c['tid']}"
                            size[k] = size.get(k, 0) + sum(ints(r.get("vc")) for r in (c.get("rc") or []) + (c.get("wc") or []))
    return [(u, "", n) for u, n in sorted(size.items())]


def reveal(files, keep, step):
    """The files as they would have stood with only the kept towns in: the other towns' votes left out (Connecticut) or
    zero with no district reported (Vermont), every total the sum of the kept towns, and a new version number or update
    time for each step so the reader asks again."""
    out = {}
    items = _items(files)
    ct = any(str(n).endswith("townVotes_Electiondata.json") for n, _b in items)
    if ct:
        towns = next(_json(b) for n, b in items if str(n).endswith("townVotes_Electiondata.json"))
        status = next((_json(b) for n, b in items if str(n).endswith("townStatus_Electiondata.json")), {})
        old_v = next((str(_json(b).get("Version")) for n, b in items if str(n).endswith("Version.json")), "0")
        new_v = str(int(old_v) * 1000 + step + 1)
        kept = {tid: offs for tid, offs in towns.items() if f"CT-{tid}" in keep}
        state = {}
        for offs in kept.values():
            for oid, cells in offs.items():
                acc = state.setdefault(oid, {})
                for cell in cells:
                    for cid, v in cell.items():
                        acc[cid] = acc.get(cid, 0) + ints(v.get("V"))
        stv = {oid: [{cid: {"V": str(n)}} for cid, n in acc.items()] for oid, acc in state.items()}
        st2 = {tid: (s if tid in kept else {"TS": "", "PR": re.sub(r"^\s*\d+", "0", str(s.get("PR") or "0 of 0"))}) for tid, s in status.items()}
        pr = {}
        for tid, offs in towns.items():
            m = re.match(r"\s*(\d+) of (\d+)", str((status.get(tid) or {}).get("PR") or ""))
            for oid in offs:
                a = pr.setdefault(oid, [0, 0])
                if m:
                    a[0] += int(m.group(1)) if tid in kept else 0
                    a[1] += int(m.group(2))
        for n, b in items:
            n2 = re.sub(r"(election/\d+/)\d+/", lambda m: m.group(1) + new_v + "/", str(n))
            stem = n2.rsplit("/", 1)[-1]
            if stem == "Version.json":
                out[n2] = json.dumps({"Version": int(new_v)}).encode()
            elif stem.startswith("townVotes"):
                out[n2] = json.dumps(kept).encode()
            elif stem.startswith("stateVotes"):
                out[n2] = json.dumps(stv).encode()
            elif stem.startswith("townStatus"):
                out[n2] = json.dumps(st2).encode()
            elif stem.startswith("officePrecincts"):
                out[n2] = json.dumps({oid: f"{a} of {b}" for oid, (a, b) in pr.items()}).encode()
            else:
                out[n2] = b
        return out
    for n, b in items:
        d = _json(b)
        if "electionDetails" in d:
            import datetime as dt
            t = dt.datetime(2026, 11, 3, 20, 0) + dt.timedelta(minutes=10 * step)      # a rehearsal's own clock, Eastern time
            d["lastUpdatedDate"] = t.strftime("%m/%d/%Y %I:%M %p")
            d["townsReporting"] = f"{len({u for u in keep if u.startswith('VT-')})}/{d.get('townsReporting', '0/0').split('/')[-1]}"
        elif isinstance(d.get("d"), list):
            for grp in d["d"]:
                for o in grp.get("o") or []:
                    rows = o.get("cs") or []
                    tot, wtot = {}, {}
                    for c in rows:
                        if not c.get("tid"):
                            continue
                        if f"VT-{c['tid']}" not in keep:
                            for r in (c.get("rc") or []) + (c.get("wc") or []):
                                r["vc"] = 0
                            m = re.match(r"\d+/(\d+)", str(c.get("distReported") or ""))
                            c["distReported"] = f"0/{m.group(1) if m else 1}"
                        for r in c.get("rc") or []:
                            tot[str(r.get("cid"))] = tot.get(str(r.get("cid")), 0) + ints(r.get("vc"))
                        for r in c.get("wc") or []:
                            wtot[str(r.get("cid"))] = wtot.get(str(r.get("cid")), 0) + ints(r.get("vc"))
                    for c in rows:
                        if c.get("tid"):
                            continue
                        for r in c.get("rc") or []:
                            cid = str(r.get("cid"))
                            r["vc"] = tot.get(cid, 0) + wtot.get(cid, 0)
                        for r in c.get("wc") or []:
                            r["vc"] = wtot.get(str(r.get("cid")), 0) if str(r.get("cid")) not in tot else 0
        out[str(n)] = json.dumps(d).encode()
    return out


# ---------------------------------------------------------------------------------------------- self-test

def selftest(say=print):
    import os
    here = os.path.join(C.HERE, "election", "fixtures", "pcc_ems")
    ok = True

    def expect(cond, what):
        nonlocal ok
        say(f"      {'ok  ' if cond else 'FAIL'} {what}")
        ok = ok and bool(cond)

    ct = {n: C.read_json(os.path.join(here, "ct_2026", n)) for n in os.listdir(os.path.join(here, "ct_2026"))}
    rd = read_ct({f"election/108/1/{n}": d for n, d in ct.items()}, {"code": "CT"})
    ids = {c["race_id"] for c in rd["contests"]}
    expect({"2026-CT-H01", "2026-CT-GOV", "2026-CT-AG"} <= ids and not rd["problems"], f"Connecticut's Nov 3 contests tied ({len(ids)})")
    gov = next(c for c in rd["contests"] if c["race_id"] == "2026-CT-GOV")
    expect(any(ch["ballot_name"] == "Ned Lamont" and "Working Families" in (ch["party"] or "") for ch in gov["choices"]),
           "a candidate on two party lines is one person, both parties named")
    st, _c, _p = C.store_roundtrip(rd)
    expect(st == "ok", f"the store takes Connecticut's reading ({st})")
    vt = {n: C.read_json(os.path.join(here, "vt_2024", n)) for n in os.listdir(os.path.join(here, "vt_2024"))}
    rd = read_vt(vt, {"code": "VT"})
    h = next((c for c in rd["contests"] if c["race_id"] == "2026-VT-H00"), None)
    tot = {r["choice"]: r["votes"] for r in h["rows"] if r["unit"] == "all"} if h else {}
    expect(h is not None and tot.get("becca-balint") == 218398 and not rd["problems"], "Vermont 2024's House count read, towns adding to the state total")
    st, _c, _p = C.store_roundtrip(rd)
    expect(st == "ok", f"the store takes Vermont's reading ({st})")
    return ok


if __name__ == "__main__":
    sys.exit(0 if selftest() else 1)
