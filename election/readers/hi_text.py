"""election/readers/hi_text.py - the Hawaii Office of Elections' results text file, summary.txt (ARCHITECTURE.md 7).
Checked 2026-10-10 with the kit's own User-Agent: the 2026 primary's file answered a script; the general election's
folder is expected as "2026 General" beside it.

  elections.hawaii.gov/wp-content/results/<YYYY> <Primary|General>/summary.txt
      one row per candidate line: the contest's id, title and party section, the precincts in all and counted, the
      line's name, and its mail, in-person and total votes. 2026's file is tab-separated text headed "#FormatVersion 1";
      older years (files.hawaii.gov, 2022) are comma-separated UTF-16 headed "Format#1". Columns are taken by name.
Read, and only these columns: Contest ID, Contest Title, Contest Party, Total Precincts, Counted Precincts, Candidate
Name, Candidate Party, Mail Votes, In-Person Votes, Total Votes. The blank, over and invalid votes are not candidates.

There is no separate "what's new" address: `check` asks for the file itself with the conditions the server allows,
and keeps it for `fetch`. Polls close at 7 p.m. Hawaii time (midnight Central); the first readout follows.
"""

import csv
import datetime as dt
import email.utils
import hashlib
import io
import re
import sys

from election.readers import _n10_common as C
from election.source import Refused, SourceError

FEED = None
BASE = "https://elections.hawaii.gov/wp-content/results/"
PAST = {                                     # rehearsal ids for past elections whose files sit elsewhere
    "2022-general": "https://files.hawaii.gov/elections/files/results/2022/general/summary.txt",
}
KEEP = ("Contest ID", "Contest Title", "Contest Party", "Total Precincts", "Counted Precincts", "Candidate Name", "Candidate Party",
        "Mail Votes", "In-Person Votes", "Total Votes")
SECTION = {"D": "DEM", "R": "REP", "G": "GRE", "L": "LIB", "N": "NP", "A": "ALO", "C": "CON"}
_last = {}


def election_id(entry):
    raw = str(((entry.get("election") or {}).get("nov3_id")) or "").strip()
    m = re.match(r"(?:folder\s+)?['\"]?(\d{4} (?:General|Primary)|[\w-]+)['\"]?", raw)
    return m.group(1) if m else None


def address(entry):
    eid = election_id(entry)
    if eid in PAST:
        return PAST[eid]
    return BASE + eid.replace(" ", "%20") + "/summary.txt"


def _get(src, url, conditional=False):
    r = src.get(url, state="HI", accept="text/plain, */*", conditional=conditional)
    if r.refused:
        raise Refused(url, r.why or "refused")
    return r


def text_of(body):
    if body[:2] in (b"\xff\xfe", b"\xfe\xff") or (len(body) > 3 and body[1:2] == b"\x00"):
        return body.decode("utf-16")
    try:
        return body.decode("utf-8-sig")
    except UnicodeDecodeError:
        return body.decode("cp1252")


def rows_of(body):
    """(rows as dicts of the kept columns only, problems)."""
    t = text_of(body)
    lines = t.splitlines()
    if not lines or not re.match(r"#?Format(Version |#)1", lines[0].strip()):
        return [], ["the file does not open with its format line"]
    head_i = next((i for i, ln in enumerate(lines[:5]) if ln.startswith("#Contest ID")), None)
    if head_i is None:
        return [], ["no heading line"]
    delim = "\t" if "\t" in lines[head_i] else ","
    rd = csv.reader(io.StringIO("\n".join(lines[head_i:])), delimiter=delim)
    head = [h.lstrip("#").strip() for h in next(rd)]
    missing = [k for k in KEEP if k not in head]
    if missing:
        return [], [f"columns missing: {', '.join(missing)}"]
    pos = {k: head.index(k) for k in KEEP}
    out = []
    for row in rd:
        if not row or not any(x.strip() for x in row):
            continue
        if len(row) < len(head) - 1:
            return out, ["a row shorter than the heading"]
        out.append({k: (row[i].strip() if i < len(row) else "") for k, i in pos.items()})
    return out, []


def last_modified(headers):
    v = (headers or {}).get("last-modified")
    try:
        return email.utils.parsedate_to_datetime(v).astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if v else None
    except (TypeError, ValueError):
        return None


def check(src, entry):
    if not election_id(entry):
        return None
    url = address(entry)
    r = _get(src, url, conditional=True)
    if r.not_modified and url in _last:
        return {"version": _last[url][0], "time": _last[url][2]}
    if r.status == 404:
        return None
    if not r.ok:
        raise SourceError(f"answered {r.status}")
    if not re.match(r"﻿?#?Format", text_of(r.body[:200])):
        raise SourceError("the file does not open with its format line")
    version = hashlib.sha256(r.body).hexdigest()[:16]
    t = last_modified(r.headers)
    _last[url] = (version, r.body, t)
    return {"version": version, "time": t}


def fetch(src, entry, version):
    url = address(entry)
    got = _last.get(url)
    if got and got[0] == version:
        return [(url, got[1])]
    r = _get(src, url)
    if not r.ok:
        raise SourceError(f"answered {r.status}")
    return [(url, r.body)]


def discover(src, entry):
    url = BASE + "2026%20General/summary.txt"
    r = _get(src, url)
    return {"nov3_id": "2026 General" if r.ok else None, "note": "summary.txt answers" if r.ok else f"answered {r.status}"}


def num(s):
    t = str(s or "").replace(",", "").strip()
    return int(t) if re.fullmatch(r"\d+", t) else 0


def read(files, entry):
    body = files[0][1] if files else b""
    return read_body(body, entry)


def read_body(body, entry, cw=None):
    rows, probs = rows_of(body)
    sections = {r["Contest Party"] for r in rows}
    primary = "" if sections - {""} else None
    R = C.Reading("HI", FEED or "hi-hi_text", entry, primary=primary, cw=cw)
    R.source_version = hashlib.sha256(body).hexdigest()[:16]
    R.problems += probs
    contests = {}
    for r in rows:
        contests.setdefault(r["Contest ID"] or r["Contest Title"], []).append(r)
    for cid, rs in contests.items():
        title = C.squash(rs[0]["Contest Title"])
        sec = rs[0]["Contest Party"]
        pcode = SECTION.get(sec, sec or None) if primary is not None else None
        rid, race = R.tie(cid, title, pcode)
        if rid is None:
            R.skip(cid, title + (f" ({sec})" if sec else ""), race)
            continue
        lines, groups = [], {"mail": [], "election_day": []}
        for r in rs:
            name = C.squash(r["Candidate Name"])
            party = C.squash(r["Candidate Party"]) or None
            m = re.match(r"^\(([A-Z]{1,3})\)\s+(.*)$", name)
            if m:
                party = party or m.group(1)
                name = m.group(2)
            mail, inp, tot = num(r["Mail Votes"]), num(r["In-Person Votes"]), num(r["Total Votes"])
            if mail + inp != tot:
                R.problems.append(f"{title}: {name}'s mail and in-person votes add to {mail + inp:,}, not {tot:,}")
            lines.append((name, party, bool(re.search(r"write[- ]?in", name, re.I)), tot))
            groups["mail"].append(mail)
            groups["election_day"].append(inp)
        pin, pall = num(rs[0]["Counted Precincts"]), num(rs[0]["Total Precincts"])
        R.add(rid, race, cid, title, lines, "precinct", pin, pall, groups=groups, party=pcode)
    return R.done()


def selftest(say=print):
    import os
    here = os.path.join(C.HERE, "election", "fixtures", "hi_text")
    ok = True

    def expect(cond, what):
        nonlocal ok
        say(f"      {'ok  ' if cond else 'FAIL'} {what}")
        ok = ok and bool(cond)

    rd = read_body(C.read_bytes(os.path.join(here, "summary_2026_primary.txt")), {"code": "HI"})
    h1 = [c for c in rd["contests"] if c["race_id"].startswith("2026-HI-H01/")]
    expect(len(h1) >= 3 and not rd["problems"], f"the House district I sections read, one for each party ({len(h1)})")
    rd2 = read_body(C.read_bytes(os.path.join(here, "summary_2022_general.txt")), {"code": "HI"})
    h = next((c for c in rd2["contests"] if c["race_id"] == "2026-HI-H01"), None)
    tot = {r["choice"]: r["votes"] for r in h["rows"] if r["type"] == "total"} if h else {}
    expect(tot.get("case-ed") == 143546, "the 2022 file (UTF-16, comma-separated) read: Ed Case's 143,546 in district I")
    st, _c, _p = C.store_roundtrip(rd)
    expect(st == "ok", f"the store takes the reading ({st})")
    return ok


if __name__ == "__main__":
    sys.exit(0 if selftest() else 1)
