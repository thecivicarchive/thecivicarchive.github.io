#!/usr/bin/env python3
"""
states/load_people.py
=====================
Who sits in a state's legislature, from the Open States "people" project: hand-checked files on every state
legislator, in the public domain (CC0), the state-level twin of the `congress-legislators` roster the federal
side uses. One download (the whole project, about 30 MB) serves every state, and it is kept for a week.

  legislators        one row per sitting member: name, party as the state writes it, chamber, district, when
                     they took this seat and their first seat on record, office, phone, email, official page
  member_terms       every seat the files record for them, in order (chamber, district, from, to)
  member_committees  committee seats and titles
  member_wikipedia   the opening paragraph of their Wikipedia article, when the files link to one. As on the
                     federal side it is fenced off on the page as not an official record
  photos             official portraits from the legislature's own site, as 2 KB thumbnails

The member id is the first eight characters of the Open States person id. The column is named bioguide_id only so
that this database has the same layout as congress_119.sqlite and the same code can read both.

    python -m states.load_people --place mn --db state_mn.sqlite
"""

import argparse
import datetime as dt
import io
import os
import re
import sqlite3
import sys
import tarfile
import time
from concurrent.futures import ThreadPoolExecutor
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urlsplit, urlunsplit

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("pip install pyyaml")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from states import net                     # noqa: E402
from states.places import place, party_code  # noqa: E402

TARBALL = "https://codeload.github.com/openstates/people/tar.gz/refs/heads/main"

SCHEMA = """
CREATE TABLE IF NOT EXISTS legislators (
  bioguide_id TEXT PRIMARY KEY, openstates_id TEXT, legiscan_id INTEGER, first_name TEXT, last_name TEXT, official_full TEXT,
  other_names TEXT, birthday TEXT, gender TEXT, party TEXT, party_name TEXT, state TEXT, district TEXT, chamber TEXT,
  is_current INTEGER, term_start TEXT, first_term_start TEXT, terms_count INTEGER, url TEXT, email TEXT, phone TEXT,
  office TEXT, wikipedia TEXT, image_url TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS member_terms (
  bioguide_id TEXT NOT NULL, seq INTEGER NOT NULL, type TEXT, start TEXT, end TEXT, state TEXT, district TEXT,
  party TEXT, how TEXT, PRIMARY KEY (bioguide_id, seq));
CREATE TABLE IF NOT EXISTS member_committees (
  bioguide_id TEXT NOT NULL, committee_id TEXT NOT NULL, name TEXT, chamber TEXT, parent TEXT, title TEXT, rank INTEGER,
  PRIMARY KEY (bioguide_id, committee_id));
CREATE TABLE IF NOT EXISTS member_wikipedia (
  bioguide_id TEXT PRIMARY KEY, title TEXT, extract TEXT, url TEXT, revision TEXT, fetched_at TEXT);
CREATE TABLE IF NOT EXISTS photos (
  bioguide_id TEXT PRIMARY KEY, webp BLOB, width INTEGER, height INTEGER, status TEXT, source_url TEXT, fetched_at TEXT);
"""
CHAMBER = {"lower": "House", "upper": "Senate", "legislature": "Legislature"}
# Statewide offices the roster carries, as it names them: the label to show, and the order to show them in.
OFFICES = {"governor": ("Governor", 0), "lt_governor": ("Lieutenant Governor", 1), "attorney general": ("Attorney General", 2),
           "secretary of state": ("Secretary of State", 3), "chief election officer": ("Chief election officer", 4)}
OFFICIALS_SCHEMA = """
CREATE TABLE IF NOT EXISTS officials (
  bioguide_id TEXT PRIMARY KEY, openstates_id TEXT, first_name TEXT, last_name TEXT, official_full TEXT, office TEXT, office_label TEXT, rank INTEGER,
  party TEXT, party_name TEXT, state TEXT, term_start TEXT, term_end TEXT, earlier TEXT, url TEXT, email TEXT, phone TEXT, address TEXT,
  wikipedia TEXT, image_url TEXT, updated_at TEXT);
"""


def short_id(ocd):
    return (ocd or "").rsplit("/", 1)[-1].replace("-", "")[:8]


def read_project(path, code):
    """(people, committees, executives) for one state out of the downloaded project."""
    people, committees, executives = [], [], []
    want = {f"/data/{code}/legislature/": people, f"/data/{code}/committees/": committees, f"/data/{code}/executive/": executives}
    with tarfile.open(path, "r:gz") as tar:
        for member in tar:
            if not member.isfile() or not member.name.endswith(".yml"):
                continue
            for folder, bucket in want.items():
                if folder in member.name:
                    bucket.append(yaml.load(tar.extractfile(member).read(), Loader=getattr(yaml, "CSafeLoader", yaml.SafeLoader)))
    return people, committees, executives


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--place", required=True)
    ap.add_argument("--db", required=True)
    ap.add_argument("--cache-dir", default="states_cache")
    ap.add_argument("--skip-wikipedia", action="store_true")
    ap.add_argument("--skip-photos", action="store_true")
    args = ap.parse_args()
    P = place(args.place)
    code = args.place.lower()
    today = dt.date.today().isoformat()

    tar_path = os.path.join(args.cache_dir, "openstates-people.tar.gz")
    if net.download(TARBALL, tar_path, 7):
        print(f"    fetched the Open States people project ({os.path.getsize(tar_path) / 1e6:,.1f} MB)")
    people, committees, executives = read_project(tar_path, code)
    print(f"    {P['name']}: {len(people):,} sitting members on file, {len(committees):,} committees, {len(executives):,} statewide officials")

    rows, terms, wiki_jobs, photo_jobs, by_ocd = [], [], [], [], {}
    for d in people:
        pid = short_id(d.get("id"))
        roles = sorted((r for r in d.get("roles") or [] if r.get("type") in CHAMBER), key=lambda r: str(r.get("start_date") or ""))
        now = [r for r in roles if not r.get("end_date") or str(r["end_date"]) >= today]
        cur = now[-1] if now else (roles[-1] if roles else {})
        pname = ((d.get("party") or [{}])[-1] or {}).get("name", "")
        pcode, plabel = party_code(P, pname)
        office = next((o for o in d.get("offices") or [] if o.get("classification") == "capitol"), (d.get("offices") or [{}])[0] if d.get("offices") else {})
        links = [x.get("url", "") for x in (d.get("links") or [])]
        sources = [x.get("url", "") for x in (d.get("sources") or [])]
        wiki = next((unquote(u.rsplit("/wiki/", 1)[1]).replace("_", " ") for u in links + sources if "en.wikipedia.org/wiki/" in u), "")
        others = "; ".join(o.get("name", "") for o in d.get("other_names") or [] if o.get("name"))
        starts = [str(r.get("start_date")) for r in roles if r.get("start_date")]
        rows.append((pid, d.get("id"), None, d.get("given_name") or "", d.get("family_name") or "", d.get("name") or "", others,
                     str(d.get("birth_date") or ""), d.get("gender") or "", pcode, plabel, P["code"], str(cur.get("district") or ""),
                     CHAMBER.get(cur.get("type"), ""), 1 if now else 0, str(cur.get("start_date") or ""), min(starts) if starts else "",
                     len(roles), links[0] if links else "", d.get("email") or "", office.get("voice") or "", office.get("address") or "",
                     wiki, d.get("image") or "", dt.datetime.now().isoformat(timespec="seconds")))
        for i, r in enumerate(roles):
            terms.append((pid, i, {"lower": "rep", "upper": "sen"}.get(r.get("type"), r.get("type")), str(r.get("start_date") or ""),
                          str(r.get("end_date") or ""), P["code"], str(r.get("district") or ""), "", ""))
        by_ocd[d.get("id")] = pid
        if wiki:
            wiki_jobs.append((pid, wiki))
        if d.get("image"):
            photo_jobs.append((pid, d["image"]))

    # -- statewide officials: only an office held today counts; seats they held in the legislature before are kept as history
    import json as _json
    officials = []
    for d in executives:
        pid = short_id(d.get("id"))
        held = [r for r in d.get("roles") or [] if r.get("type") not in CHAMBER and (not r.get("end_date") or str(r["end_date"]) >= today)]
        if not held:
            continue
        role = sorted(held, key=lambda r: str(r.get("start_date") or ""))[-1]
        label, rank = OFFICES.get(role.get("type"), (str(role.get("type") or "").title(), 9))
        pname = ((d.get("party") or [{}])[-1] or {}).get("name", "")
        pcode, plabel = party_code(P, pname)
        office = next((o for o in d.get("offices") or [] if o.get("classification") == "capitol"), (d.get("offices") or [{}])[0] if d.get("offices") else {})
        links = [x.get("url", "") for x in (d.get("links") or [])]
        sources = [x.get("url", "") for x in (d.get("sources") or [])]
        wiki = next((unquote(u.rsplit("/wiki/", 1)[1]).replace("_", " ") for u in links + sources if "en.wikipedia.org/wiki/" in u), "")
        earlier = [{"ch": CHAMBER[r["type"]], "d": str(r.get("district") or ""), "from": str(r.get("start_date") or "")[:4], "to": str(r.get("end_date") or "")[:4]}
                   for r in sorted((r for r in d.get("roles") or [] if r.get("type") in CHAMBER), key=lambda r: str(r.get("end_date") or ""))]
        own = next((u for u in links if "legis" not in u.lower() and "house" not in u.lower() and "senate" not in u.lower()), links[0] if links else "")
        officials.append((pid, d.get("id"), d.get("given_name") or "", d.get("family_name") or "", d.get("name") or "", role.get("type") or "", label, rank,
                          pcode, plabel, P["code"], str(role.get("start_date") or ""), str(role.get("end_date") or ""), _json.dumps(earlier), own,
                          d.get("email") or "", office.get("voice") or "", office.get("address") or "", wiki, d.get("image") or "",
                          dt.datetime.now().isoformat(timespec="seconds")))
        if wiki:
            wiki_jobs.append((pid, wiki))
        if d.get("image"):
            photo_jobs.append((pid, d["image"]))

    seats = []
    for c in committees:
        cid = short_id(c.get("id")) or re.sub(r"\W+", "-", c.get("name", "").lower())[:40]
        parent = ""
        if c.get("parent"):
            parent = next((x.get("name", "") for x in committees if x.get("id") == c["parent"]), "")
        for rank, m in enumerate(c.get("members") or []):
            pid = by_ocd.get(m.get("person_id"))
            if pid:
                role = (m.get("role") or "").strip()
                seats.append((pid, cid, c.get("name", ""), CHAMBER.get(c.get("chamber"), ""), parent,
                              "" if role.lower() == "member" else role.title(), rank))

    con = sqlite3.connect(args.db)
    con.executescript(SCHEMA)
    con.executescript(OFFICIALS_SCHEMA)
    with con:
        con.execute("DELETE FROM officials")
        con.executemany("INSERT OR REPLACE INTO officials VALUES (" + ",".join("?" * 21) + ")", officials)
        con.execute("DELETE FROM legislators")
        con.executemany("INSERT OR REPLACE INTO legislators VALUES (" + ",".join("?" * 25) + ")", rows)
        con.execute("DELETE FROM member_terms")
        con.executemany("INSERT OR REPLACE INTO member_terms VALUES (?,?,?,?,?,?,?,?,?)", terms)
        con.execute("DELETE FROM member_committees")
        con.executemany("INSERT OR REPLACE INTO member_committees VALUES (?,?,?,?,?,?,?)", seats)
    by_ch = dict(con.execute("SELECT chamber, COUNT(*) FROM legislators WHERE is_current = 1 GROUP BY 1"))
    by_pt = dict(con.execute("SELECT party_name, COUNT(*) FROM legislators WHERE is_current = 1 GROUP BY 1"))
    print(f"    Stored: {sum(by_ch.values()):,} members ({', '.join(f'{k} {v}' for k, v in sorted(by_ch.items()))}; "
          f"{', '.join(f'{k} {v}' for k, v in sorted(by_pt.items()))}); {len(terms):,} seats held over time; {len(seats):,} committee seats")
    print(f"    Statewide officials: {', '.join(f'{o[6]} {o[4]}' for o in sorted(officials, key=lambda o: o[7])) or 'none on file'}")
    for ch, key in (("House", "lower"), ("Senate", "upper")):
        if P.get(key) and by_ch.get(ch, 0) != P[key]["seats"]:
            print(f"    note: the {ch} has {P[key]['seats']} seats and {by_ch.get(ch, 0)} members on file (vacancies are usual)")

    # -- Wikipedia's opening paragraph, the same polite batches the federal profiles stage uses
    if not args.skip_wikipedia and wiki_jobs:
        from load_profiles import wikipedia_batch
        folder = os.path.join(args.cache_dir, "wikipedia", code)
        os.makedirs(folder, exist_ok=True)
        import json
        stale = [(pid, t) for pid, t in wiki_jobs if not (os.path.exists(os.path.join(folder, pid + ".json"))
                 and time.time() - os.path.getmtime(os.path.join(folder, pid + ".json")) < 30 * 86400)]
        net.patient_lookups()
        for i in range(0, len(stale), 20):
            chunk = stale[i:i + 20]
            try:
                got = wikipedia_batch([t for _p, t in chunk])
            except (HTTPError, URLError, OSError, ValueError) as e:
                print(f"    Wikipedia request {i // 20 + 1}: {e}")
                continue
            for pid, title in chunk:
                if title in got:
                    json.dump(got[title], open(os.path.join(folder, pid + ".json"), "w", encoding="utf-8"), ensure_ascii=False)
            time.sleep(1.0)
        wiki_rows = []
        for pid, title in wiki_jobs:
            try:
                j = json.load(open(os.path.join(folder, pid + ".json"), encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if (j.get("extract") or "").strip():
                page = ((j.get("content_urls") or {}).get("desktop") or {}).get("page") or ""
                wiki_rows.append((pid, j.get("title") or title, " ".join(j["extract"].split()), page, j.get("timestamp") or "",
                                  dt.datetime.now().isoformat(timespec="seconds")))
        with con:
            con.execute("DELETE FROM member_wikipedia")
            con.executemany("INSERT OR REPLACE INTO member_wikipedia VALUES (?,?,?,?,?,?)", wiki_rows)
        print(f"    Wikipedia: {len(wiki_rows):,} opening paragraphs of {len(wiki_jobs):,} members with an article on file")

    # -- portraits from the legislature's own site, four at a time, cached
    if not args.skip_photos and photo_jobs:
        try:
            from PIL import Image
        except ImportError:
            print("    Pillow is not installed; skipping portraits")
            return
        folder = os.path.join(args.cache_dir, "photos", code)
        os.makedirs(folder, exist_ok=True)

        def fetch(job):
            pid, url = job
            path = os.path.join(folder, pid)
            if os.path.exists(path) and os.path.getsize(path) > 0:
                return pid, url, open(path, "rb").read(), None
            try:
                # some rosters carry addresses with spaces and commas in them ("reisch, tim rep.jpg"); write those the
                # way a web address must be written, leaving anything already written that way alone
                inner = re.search(r"^https?://.+?(https?://.+)$", url)       # one whole address pasted inside another: the inner one is the picture
                parts = urlsplit(inner.group(1) if inner else url)
                safe = urlunsplit((parts.scheme, parts.netloc, quote(parts.path, safe="/%:@!$&'()*+,;=~-._"), parts.query, ""))
                raw = net.get(safe, timeout=60)
                open(path, "wb").write(raw)
                return pid, url, raw, None
            except (HTTPError, URLError, OSError, ValueError, HTTPException) as e:
                return pid, url, None, str(e)

        ok = bad = 0
        now = dt.datetime.now().isoformat(timespec="seconds")
        with ThreadPoolExecutor(max_workers=4) as pool:
            for pid, url, raw, err in pool.map(fetch, photo_jobs):
                if not raw:
                    bad += 1
                    con.execute("INSERT OR REPLACE INTO photos VALUES (?,?,?,?,?,?,?)", (pid, None, None, None, err or "missing", url, now))
                    continue
                try:
                    im = Image.open(io.BytesIO(raw))
                    if im.mode in ("P", "LA", "RGBA"):               # a cut-out portrait: stand it on white rather than on whatever lies under the transparency
                        im = im.convert("RGBA")
                        ground = Image.new("RGB", im.size, (255, 255, 255))
                        ground.paste(im, mask=im.split()[-1])
                        im = ground
                    else:
                        im = im.convert("RGB")
                    w, h = im.size                                   # crop to the federal portraits' shape, from the top
                    target = 120 / 146
                    if w / h > target:
                        nw = int(h * target); im = im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
                    else:
                        nh = int(w / target); im = im.crop((0, 0, w, min(h, nh)))
                    im.thumbnail((120, 146), Image.LANCZOS)
                    buf = io.BytesIO(); im.save(buf, "WEBP", quality=60, method=6)
                    con.execute("INSERT OR REPLACE INTO photos VALUES (?,?,?,?,?,?,?)", (pid, buf.getvalue(), im.size[0], im.size[1], "ok", url, now))
                    ok += 1
                except Exception as e:  # noqa: BLE001
                    bad += 1
                    con.execute("INSERT OR REPLACE INTO photos VALUES (?,?,?,?,?,?,?)", (pid, None, None, None, f"unreadable: {e}", url, now))
        con.commit()
        size = con.execute("SELECT COALESCE(SUM(LENGTH(webp)), 0) FROM photos").fetchone()[0]
        print(f"    Portraits: {ok:,} stored ({size / 1e3:,.0f} KB){f', {bad} not available' if bad else ''}")


if __name__ == "__main__":
    main()
