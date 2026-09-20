#!/usr/bin/env python3
"""
load_profiles.py
================
What the member cards need to say who someone is, beyond their votes:

  member_terms        every term each member has served (chamber, dates, state, district, party), from the
                      `congress-legislators` roster: how long they have held this seat, earlier service in
                      the other chamber, any change of party
  member_committees   current committee and subcommittee seats, with titles such as Chair or Ranking Member
  member_social       official accounts on X, Facebook, YouTube and Instagram
  member_wikipedia    the opening paragraph of each member's Wikipedia article, for life before Congress

The first three are the same public-domain roster project the `roster` stage uses. The Wikipedia paragraph
is NOT a government record: the site fences it off and says so, credits it, and links to the article, as its
licence (CC BY-SA 4.0) requires. The official Biographical Directory of Congress would be the better source,
but it refuses automated requests.

Only members who matter to the site are loaded: everyone now serving, and anyone who cast a recorded vote in
this database. Wikipedia is asked for twenty articles at a time (about thirty requests in all, a second apart),
and each answer is cached under profile_cache/ and fetched again only after --refresh-days.

    python load_profiles.py --db congress_119.sqlite --cache-dir profile_cache
"""

import argparse
import datetime as dt
import json
import os
import sqlite3
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("pip install pyyaml")

BASE = "https://raw.githubusercontent.com/unitedstates/congress-legislators/main/"
WIKI_API = "https://en.wikipedia.org/w/api.php"
UA = "congress-catalog/1.0 (personal legislative research; thecivicarchive.github.io)"

SCHEMA = """
CREATE TABLE IF NOT EXISTS member_terms (
  bioguide_id TEXT NOT NULL, seq INTEGER NOT NULL, type TEXT, start TEXT, end TEXT, state TEXT, district INTEGER,
  party TEXT, how TEXT, PRIMARY KEY (bioguide_id, seq));
CREATE TABLE IF NOT EXISTS member_committees (
  bioguide_id TEXT NOT NULL, committee_id TEXT NOT NULL, name TEXT, chamber TEXT, parent TEXT, title TEXT, rank INTEGER,
  PRIMARY KEY (bioguide_id, committee_id));
CREATE TABLE IF NOT EXISTS member_social (
  bioguide_id TEXT PRIMARY KEY, twitter TEXT, facebook TEXT, youtube TEXT, instagram TEXT);
CREATE TABLE IF NOT EXISTS member_wikipedia (
  bioguide_id TEXT PRIMARY KEY, title TEXT, extract TEXT, url TEXT, revision TEXT, fetched_at TEXT);
"""


def get(url, timeout=60):
    with urlopen(Request(url, headers={"User-Agent": UA, "Accept": "application/json, text/plain, */*"}), timeout=timeout) as r:
        return r.read()


def roster(name, local_dir):
    if local_dir and os.path.exists(os.path.join(local_dir, name)):
        data = open(os.path.join(local_dir, name), "rb").read()
    else:
        data = get(BASE + name, timeout=180)
    return yaml.load(data, Loader=getattr(yaml, "CSafeLoader", yaml.SafeLoader))


def wikipedia_batch(titles):
    """Up to 20 article titles -> {title as asked: cache record}. One request; redirects are followed."""
    q = urlencode({"action": "query", "format": "json", "formatversion": "2", "redirects": "1", "prop": "extracts|info",
                   "exintro": "1", "explaintext": "1", "exlimit": "max", "inprop": "url", "titles": "|".join(titles)})
    for attempt in range(4):
        try:
            j = json.loads(get(WIKI_API + "?" + q, timeout=60))
            break
        except HTTPError as e:                     # when the server says wait, wait
            if e.code == 429 and attempt < 3:
                wait = e.headers.get("Retry-After") if e.headers else None
                time.sleep(min(120, int(wait) if wait and str(wait).isdigit() else 20 * (attempt + 1)))
                continue
            raise
    query = j.get("query") or {}
    hop = {n["from"]: n["to"] for n in (query.get("normalized") or [])}
    hop.update({r["from"]: r["to"] for r in (query.get("redirects") or [])})
    pages = {pg["title"]: pg for pg in (query.get("pages") or []) if not pg.get("missing")}
    out = {}
    for t in titles:
        final = t
        for _ in range(3):
            final = hop.get(final, final)
        pg = pages.get(final)
        first = ((pg or {}).get("extract") or "").strip().split("\n")[0].strip()
        if pg and first:
            out[t] = {"type": "standard", "title": pg["title"], "extract": first, "timestamp": pg.get("touched") or "",
                      "content_urls": {"desktop": {"page": pg.get("fullurl") or ""}}}
    return out


def wikipedia_row(job):
    """(bioguide, title, cache path) -> (row for member_wikipedia or None, problem or None), read from the cache."""
    bio, title, path = job
    try:
        j = json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError):
        return None, f"{title}: no answer"
    if j.get("type") != "standard" or not (j.get("extract") or "").strip():
        return None, f"{title}: not a plain article ({j.get('type')})"
    page = ((j.get("content_urls") or {}).get("desktop") or {}).get("page") or ("https://en.wikipedia.org/wiki/" + quote(title.replace(" ", "_")))
    return (bio, j.get("title") or title, " ".join(j["extract"].split()), page, j.get("timestamp") or "",
            dt.datetime.now().isoformat(timespec="seconds")), None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", required=True)
    ap.add_argument("--cache-dir", default="profile_cache")
    ap.add_argument("--dir", default="", help="folder with local copies of the roster files")
    ap.add_argument("--refresh-days", type=int, default=30, help="fetch a Wikipedia paragraph again once its copy is this old")
    ap.add_argument("--skip-wikipedia", action="store_true")
    args = ap.parse_args()
    con = sqlite3.connect(args.db)
    con.executescript(SCHEMA)
    if not con.execute("SELECT 1 FROM sqlite_master WHERE name = 'legislators'").fetchone():
        sys.exit("No roster yet. Run the roster stage first: python run_all.py roster")
    wanted = {r[0] for r in con.execute("SELECT bioguide_id FROM legislators WHERE is_current = 1")}
    if con.execute("SELECT 1 FROM sqlite_master WHERE name = 'member_votes'").fetchone():
        wanted |= {r[0] for r in con.execute("SELECT DISTINCT member_key FROM member_votes") if r[0]}
    print(f"    {len(wanted):,} members to describe (now serving, or on a recorded vote here)")

    # -- terms: the current file first, the historical one only if someone is missing from it
    terms, seen = [], set()
    for name in ("legislators-current.yaml", "legislators-historical.yaml"):
        if name.endswith("historical.yaml") and not (wanted - seen):
            break
        for m in roster(name, args.dir):
            bio = (m.get("id") or {}).get("bioguide")
            if bio in wanted and bio not in seen:
                seen.add(bio)
                for i, t in enumerate(m.get("terms") or []):
                    terms.append((bio, i, t.get("type"), str(t.get("start") or ""), str(t.get("end") or ""), t.get("state"),
                                  t.get("district") if t.get("type") == "rep" else None, t.get("party"), t.get("how")))
        print(f"    {name}: terms for {len(seen):,} members so far")

    # -- committees: names from one file, seats from the other
    names = {}
    for c in roster("committees-current.yaml", args.dir):
        chamber = {"house": "House", "senate": "Senate", "joint": "Joint"}.get(c.get("type"), "")
        names[c["thomas_id"]] = (c.get("name") or "", chamber, None)
        for s in c.get("subcommittees") or []:
            names[c["thomas_id"] + str(s.get("thomas_id"))] = (s.get("name") or "", chamber, c.get("name") or "")
    seats = []
    for cid, people in (roster("committee-membership-current.yaml", args.dir) or {}).items():
        nm, chamber, parent = names.get(cid, (cid, "", None))
        for p in people or []:
            if p.get("bioguide") in wanted:
                seats.append((p["bioguide"], cid, nm, chamber, parent, p.get("title"), p.get("rank")))
    print(f"    committees: {len(seats):,} seats on {len({s[1] for s in seats}):,} committees and subcommittees")

    # -- social accounts
    social = []
    for m in roster("legislators-social-media.yaml", args.dir):
        bio, s = (m.get("id") or {}).get("bioguide"), m.get("social") or {}
        if bio in wanted and any(s.get(k) for k in ("twitter", "facebook", "youtube", "youtube_id", "instagram")):
            tube = ("channel/" + s["youtube_id"]) if s.get("youtube_id") else (("user/" + s["youtube"]) if s.get("youtube") else None)
            social.append((bio, s.get("twitter"), s.get("facebook"), tube, s.get("instagram")))
    print(f"    social accounts: {len(social):,} members")

    # -- Wikipedia's opening paragraph, cached on disk
    wiki_rows, problems = [], []
    if not args.skip_wikipedia:
        folder = os.path.join(args.cache_dir, "wikipedia")
        os.makedirs(folder, exist_ok=True)
        jobs = [(bio, title, os.path.join(folder, bio + ".json"))
                for bio, title in con.execute("SELECT bioguide_id, wikipedia FROM legislators WHERE wikipedia IS NOT NULL AND wikipedia <> ''")
                if bio in wanted]
        stale = [j for j in jobs if not (os.path.exists(j[2]) and (time.time() - os.path.getmtime(j[2])) < args.refresh_days * 86400)]
        for i in range(0, len(stale), 20):                                    # twenty articles a request, a second apart
            chunk = stale[i:i + 20]
            try:
                got = wikipedia_batch([t for _b, t, _p in chunk])
            except (HTTPError, URLError, OSError, ValueError) as e:
                problems.append(f"request {i // 20 + 1}: {e}")
                continue
            for _bio, title, path in chunk:
                if title in got:
                    with open(path, "w", encoding="utf-8") as fh:
                        json.dump(got[title], fh, ensure_ascii=False)
            print(f"    Wikipedia: {min(i + 20, len(stale)):,} of {len(stale):,} fetched", flush=True)
            time.sleep(1.0)
        for job in jobs:
            row, problem = wikipedia_row(job)
            if row:
                wiki_rows.append(row)
            elif problem:
                problems.append(problem)
        print(f"    Wikipedia: {len(wiki_rows):,} opening paragraphs" + (f"; {len(problems)} not available" if problems else ""))
        for p in problems[:8]:
            print(f"      - {p}")

    with con:
        con.execute("DELETE FROM member_terms")
        con.executemany("INSERT INTO member_terms VALUES (?,?,?,?,?,?,?,?,?)", terms)
        con.execute("DELETE FROM member_committees")
        con.executemany("INSERT OR REPLACE INTO member_committees VALUES (?,?,?,?,?,?,?)", seats)
        con.execute("DELETE FROM member_social")
        con.executemany("INSERT OR REPLACE INTO member_social VALUES (?,?,?,?,?)", social)
        if not args.skip_wikipedia:
            con.execute("DELETE FROM member_wikipedia")
            con.executemany("INSERT OR REPLACE INTO member_wikipedia VALUES (?,?,?,?,?,?)", wiki_rows)
    print(f"    Stored: {len(terms):,} terms, {len(seats):,} committee seats, {len(social):,} social profiles, "
          f"{len(wiki_rows):,} Wikipedia paragraphs")


if __name__ == "__main__":
    main()
