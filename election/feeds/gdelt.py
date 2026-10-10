"""election/feeds/gdelt.py - news headlines from GDELT's raw 15-minute files (ARCHITECTURE.md 2.3, 3.3, 4.4).

    python -m election.feeds.gdelt poll [--db FILE] [--backfill N]    one look: the newest file, and up to N missed ones

GDELT's search API answers this machine 429 and is on source.py's never list. Its raw files are read instead:
http://data.gdeltproject.org/gdeltv2/lastupdate.txt names the newest three zips every 15 minutes; the Global Knowledge
Graph zip (".gkg.csv.zip", about 2.6 MB) holds every article GDELT saw in those minutes, with its headline, outlet,
themes and places. A zip is read in memory and never written to disk (parsed, then dropped).

Fields read (an allowlist, by position in GKG 2.1): V2.1DATE (1), V2SOURCECOMMONNAME (3, the outlet's domain),
V2DOCUMENTIDENTIFIER (4, the address), V1THEMES and V2ENHANCEDTHEMES (7, 8), V1LOCATIONS and V2ENHANCEDLOCATIONS
(9, 10) and the page title inside V2EXTRASXML (26). Never the persons, organizations, quotations, image or social
media embeds (the last name ordinary people's posts), tone or counts.

Kept: a US story (an outlet on the feed list, or a place in the United States) that is about an election (GDELT's
ELECTION theme, or the headline's words) or that names a candidate on a race's list. Placed by geotag.py's rules,
GDELT's own places being rule 3. Credit: the GDELT Project (https://www.gdeltproject.org/), wherever its items appear.

Missed files (the computer was off): the files are named by their 15-minute mark, so up to `backfill` missed marks
(newest first, at most a day back) are read on each look, one request at a time.
"""

import argparse
import datetime as dt
import hashlib
import io
import json
import os
import re
import sys
import zipfile

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from election.feeds import geotag as G  # noqa: E402
from election.feeds.outlets import registered_domain  # noqa: E402

LAST = "http://data.gdeltproject.org/gdeltv2/lastupdate.txt"
BASE = "http://data.gdeltproject.org/gdeltv2/"
CREDIT = "GDELT Project"
CREDIT_URL = "https://www.gdeltproject.org/"
BACKFILL = 4                     # missed files read on one look (each about 2.6 MB)
MAX_BACK = dt.timedelta(hours=24)
TITLE = re.compile(r"<PAGE_TITLE>(.*?)</PAGE_TITLE>", re.S)
STAMP = re.compile(r"/(\d{14})\.gkg\.csv\.zip$")


def _outlets(con):
    by_key = {}
    try:
        for oid, name, key, domain, state in con.execute(
                "SELECT outlet_id, name, outlet_key, domain, home_state FROM outlets WHERE active=1"):
            by_key.setdefault(key, (oid, name, state))
            by_key.setdefault(registered_domain(domain), (oid, name, state))
    except Exception:  # noqa: BLE001
        pass
    return by_key


def parse_lastupdate(body):
    """[(size, md5, url)] for the GKG file named in lastupdate.txt."""
    out = []
    for line in body.decode("ascii", "replace").splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[2].endswith(".gkg.csv.zip"):
            out.append((int(parts[0]), parts[1], parts[2]))
    return out


def rows(zbytes):
    """The allowlisted fields of every row of a GKG zip (in memory)."""
    with zipfile.ZipFile(io.BytesIO(zbytes)) as z:
        for name in z.namelist():
            with z.open(name) as fh:
                for raw in fh:
                    f = raw.decode("utf-8", "replace").rstrip("\r\n").split("\t")
                    if len(f) < 27:
                        continue
                    title = TITLE.search(f[26])
                    yield {"date": f[1], "domain": f[3].strip().lower(), "url": f[4].strip(),
                           "themes": set(t.split(",")[0] for t in (f[7] + ";" + f[8]).split(";") if t),
                           "locs": f[10] or f[9], "title": title.group(1).strip() if title else ""}


def locations(field):
    """[(type, adm1, adm2, feature id)] from V2ENHANCEDLOCATIONS (or V1LOCATIONS): only the place codes."""
    out = []
    for block in (field or "").split(";"):
        p = block.split("#")
        if len(p) >= 7:
            out.append((p[0], p[3], p[4] if len(p) >= 9 else "", p[-2] if len(p) >= 9 else p[-1]))
    return out


def _html_unescape(s):
    import html
    return " ".join(html.unescape(s).split())


def read_zip(con, zbytes, now, P=None, say=print):
    P = P or G.placer()
    outlets = _outlets(con)
    seen = kept = placed = 0
    for r in rows(zbytes):
        seen += 1
        if not r["url"].lower().startswith(("http://", "https://")) or not r["title"]:
            continue
        title = _html_unescape(r["title"])
        locs = locations(r["locs"])
        us = any(l[1].startswith("US") for l in locs)
        key = registered_domain(r["domain"])
        known = outlets.get(key)
        if not (us or known):
            continue
        home = known[2] if known else None
        places = P.place(title, home, gdelt=locs)
        election = G.gdelt_election(r["themes"]) or G.is_election(title)
        if not (election or any(p["rule"] in (G.R1, G.R1B) for p in places)):
            continue
        address = G.canonical(r["url"])
        if not address:
            continue
        try:
            pub = dt.datetime.strptime(r["date"], "%Y%m%d%H%M%S").replace(tzinfo=G.UTC)
        except ValueError:
            pub = None
        new = G.store_item(con, source="gdelt", kind="news", address=address, link=r["url"], headline=title,
                           published=pub, fetched=now, outlet_id=known[0] if known else None, outlet_key=key,
                           outlet_name=known[1] if known else r["domain"], home_state=home, election=election,
                           places=places)
        kept += 1 if new else 0
        placed += 1 if new and any(p["place_kind"] == "race" for p in places) else 0
    return {"rows": seen, "kept": kept, "on_races": placed}


def _stamp_of(url):
    m = STAMP.search(url)
    return dt.datetime.strptime(m.group(1), "%Y%m%d%H%M%S").replace(tzinfo=G.UTC) if m else None


def poll(src=None, now=None, rehearsal=False, say=print, db=None, backfill=BACKFILL):
    """One look at GDELT: the newest GKG file if it is new, and up to `backfill` missed ones."""
    from election.source import Refused, SourceError
    if src is None:
        from election.feeds import accounts
        from election.source import Source
        src = Source(stopped_file=os.path.join(G.CACHE, "stopped_hosts.json"), log=accounts._log)
    now = now or G.utcnow()
    con = G.open_db(db)
    try:
        r = src.get(LAST, accept="text/plain", timeout=30)
        if not r.ok:
            return {"gdelt": f"lastupdate answered {r.status}" + (" (refused)" if r.refused else "")}
        latest = parse_lastupdate(r.body)
        if not latest:
            return {"gdelt": "lastupdate named no knowledge-graph file"}
        size, md5, url = latest[0]
        newest = _stamp_of(url)
        done = G.state_get(con, "gdelt:last")
        last = G.parse_time(done) if done else None
        todo = []
        if newest and (last is None or newest > last):
            todo.append((url, md5, size))
            mark = newest - dt.timedelta(minutes=15)
            floor = max(last or (newest - dt.timedelta(minutes=15 * backfill)), newest - MAX_BACK)
            while backfill and len(todo) <= backfill and mark > floor:
                todo.append((f"{BASE}{mark.strftime('%Y%m%d%H%M%S')}.gkg.csv.zip", None, None))
                mark -= dt.timedelta(minutes=15)
        out = {"files": 0, "rows": 0, "kept": 0, "on_races": 0}
        for u, digest, sz in todo:
            try:
                z = src.get(u, accept="application/zip", timeout=120)
            except (Refused, SourceError) as e:
                out["error"] = e.__class__.__name__
                break
            if z.status == 404:
                continue                                   # GDELT skips a mark now and then
            if not z.ok:
                out["error"] = f"answered {z.status}"
                break
            if digest and hashlib.md5(z.body).hexdigest() != digest:  # noqa: S324 (GDELT publishes MD5 sums)
                out["error"] = "a file's MD5 sum did not match; not read"
                continue
            try:
                res = read_zip(con, z.body, now, say=say)
            except zipfile.BadZipFile:
                out["error"] = "a file was not a zip; not read"
                continue
            out["files"] += 1
            for k in ("rows", "kept", "on_races"):
                out[k] += res[k]
            del z
        if newest and out["files"]:
            G.state_set(con, "gdelt:last", G.iso(newest))
        G.refresh_shown(con)
        return out
    finally:
        con.close()


def main(argv):
    ap = argparse.ArgumentParser(prog="gdelt")
    ap.add_argument("cmd", choices=["poll"])
    ap.add_argument("--db")
    ap.add_argument("--backfill", type=int, default=0)
    a = ap.parse_args(argv)
    print(json.dumps(poll(db=a.db, backfill=a.backfill)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
