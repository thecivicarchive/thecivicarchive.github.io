#!/usr/bin/env python3
"""
load_roll_calls.py
==================
Fills `member_votes` (one row per member per recorded vote) and `floor_votes.party_split` from
the House Clerk (EVS) and Senate (LIS) roll-call XML linked in the catalog, resolving Senate
members to their bioguide IDs through the legislators table (run load_legislators.py first).

    python load_roll_calls.py --db congress_119.sqlite               # every linked roll call (cached in ./rollcall_cache)
    python load_roll_calls.py --db congress_119.sqlite --bill hr22-119
    python load_roll_calls.py --db congress_119.sqlite --from-dir ./rollcalls   # pre-downloaded XML
    python load_roll_calls.py --db congress_119.sqlite --import-compact votes.json

--import-compact reads a JSON list of {"roll_call_xml": <url>, "votes": "A000370:Y B001302:N ..."}
where each token is a bioguide (House) or LIS id (Senate) followed by Y, N, P (present) or X
(not voting), optionally followed by the member's party at the time of the vote (e.g. K000401:Y:R). It exists so votes transcribed by hand can be loaded and later replaced.
"""

import argparse
import datetime as dt
import json
import os
import re
import sqlite3
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from urllib.request import Request, urlopen

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import congress_catalog as cc  # noqa: E402  (parsers shared with the pipeline)

POS = {"Y": "Yea", "N": "Nay", "P": "Present", "X": "Not Voting"}


def party_split_text(rows):
    """[(party, position)] -> 'D 46-156, R 217-0' (independents fold into D, as the rubric does)."""
    tally = Counter()
    for p, pos in rows:
        p = "D" if p in ("D", "I", "ID") else ("R" if p == "R" else None)
        if p and pos in ("Yea", "Nay", "Aye", "No"):
            tally[(p, "Y" if pos in ("Yea", "Aye") else "N")] += 1
    return ", ".join(f"{p} {tally[(p, 'Y')]}-{tally[(p, 'N')]}" for p in ("D", "R") if tally[(p, "Y")] + tally[(p, "N")])


def resolve(con, member_key):
    """Senate LIS id -> bioguide; House name-id is already a bioguide."""
    if len(member_key) == 4 and member_key.startswith("S") and member_key[1:].isdigit():   # LIS ids are S### ; bioguides are S000000
        row = con.execute("SELECT bioguide_id FROM legislators WHERE lis_id = ?", (member_key,)).fetchone()
        return row[0] if row else member_key
    return member_key


def party_of(con, bioguide, fallback=""):
    row = con.execute("SELECT party, state FROM legislators WHERE bioguide_id = ?", (bioguide,)).fetchone()
    return (row[0], row[1]) if row else (fallback, "")


def store(con, vote_ids, members, source):
    rows = []
    for m in members:
        bio = resolve(con, m["member_key"])
        rparty, rstate = party_of(con, bio, "")
        # party and state as recorded on the roll call itself (party at the time of the vote) win;
        # the roster fills in for hand-transcribed votes, which carry no party
        rows.append((bio, m.get("name", ""), m.get("party") or rparty, m.get("state") or rstate, m["position"]))
    split = party_split_text([(r[2], r[4]) for r in rows])
    for vid in vote_ids:
        con.execute("DELETE FROM member_votes WHERE vote_id = ?", (vid,))
        con.executemany("INSERT OR REPLACE INTO member_votes VALUES (?,?,?,?,?,?)", [(vid, *r) for r in rows])
        con.execute("UPDATE floor_votes SET party_split = ? WHERE vote_id = ?", (split, vid))
    con.commit()
    return len(rows), split


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", required=True)
    ap.add_argument("--bill", nargs="*", help="limit to these bill keys")
    ap.add_argument("--from-dir", help="folder of already-downloaded roll-call XML files (named by URL basename)")
    ap.add_argument("--import-compact", help="JSON file of hand-transcribed votes (see docstring)")
    ap.add_argument("--force", action="store_true", help="reload votes that already have member rows")
    ap.add_argument("--cache-dir", default="rollcall_cache", help="keep each roll-call XML here so re-runs never re-download ('' to disable)")
    ap.add_argument("--workers", type=int, default=4, help="parallel downloads (be polite: 4 is plenty)")
    args = ap.parse_args()
    con = sqlite3.connect(args.db)
    con.executescript("CREATE TABLE IF NOT EXISTS member_votes (vote_id TEXT, member_key TEXT, member_name TEXT, party TEXT, "
                      "state TEXT, position TEXT, PRIMARY KEY (vote_id, member_key));")
    if not con.execute("SELECT 1 FROM sqlite_master WHERE name = 'legislators'").fetchone():
        sys.exit("Run load_legislators.py first (Senate roll calls need the LIS-to-bioguide crosswalk).")

    if args.import_compact:
        n = 0
        for item in json.load(open(args.import_compact, encoding="utf-8")):
            url = item["roll_call_xml"]
            vids = [r[0] for r in con.execute("SELECT vote_id FROM floor_votes WHERE roll_call_xml = ?", (url,))]
            if not vids:
                print(f"  no floor vote links to {url}; skipped")
                continue
            members = []
            for tok in item["votes"].split():
                parts = tok.split(":")                    # bioguide:CODE[:PARTY-AT-VOTE-TIME]
                key, code = parts[0], parts[1] if len(parts) > 1 else ""
                members.append({"member_key": key, "position": POS.get(code.upper(), code),
                                "party": parts[2] if len(parts) > 2 else ""})
            count, split = store(con, vids, members, "compact")
            print(f"  {url.rsplit('/', 1)[-1]}: {count} members -> {split}")
            n += 1
        print(f"Imported {n} roll call(s) from {args.import_compact}")
        return

    q = "SELECT DISTINCT roll_call_xml FROM floor_votes WHERE roll_call_xml <> ''"
    params = ()
    if args.bill:
        q += f" AND bill_key IN ({','.join('?' * len(args.bill))})"
        params = tuple(args.bill)
    urls = [r[0] for r in con.execute(q, params)]
    todo = []
    for url in urls:
        vids = [r[0] for r in con.execute("SELECT vote_id FROM floor_votes WHERE roll_call_xml = ?", (url,))]
        if args.force or not con.execute("SELECT 1 FROM member_votes WHERE vote_id = ? LIMIT 1", (vids[0],)).fetchone():
            todo.append((url, vids))
    print(f"{len(urls):,} roll calls linked; {len(urls) - len(todo):,} already loaded; {len(todo):,} to load"
          + (f" (cache: {args.cache_dir})" if args.cache_dir else ""))
    os.makedirs(args.cache_dir, exist_ok=True) if args.cache_dir else None

    def fetch(item):
        url, vids = item
        try:
            if args.from_dir:
                raw = open(os.path.join(args.from_dir, url.rsplit("/", 1)[-1]), "rb").read()
            else:
                path = os.path.join(args.cache_dir, cache_name(url)) if args.cache_dir else ""
                if path and os.path.exists(path) and os.path.getsize(path) > 0:
                    raw = open(path, "rb").read()
                else:
                    raw = cc.http_get(url, retries=3, timeout=60)
                    if path:
                        with open(path, "wb") as fh:
                            fh.write(raw)
            members = parse_members(cc.ET.fromstring(raw))
            if not members:
                raise ValueError("no members parsed")
            return url, vids, members, None
        except Exception as e:  # noqa: BLE001
            return url, vids, None, str(e)

    done = fails = 0
    failed = []
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        for url, vids, members, err in pool.map(fetch, todo):
            if err:
                fails += 1
                failed.append(f"{url}: {err}")
                continue
            count, split = store(con, vids, members, url)
            done += 1
            if done % 50 == 0 or done == len(todo) - fails:
                print(f"  {done:,}/{len(todo):,} loaded (latest {url.rsplit('/', 1)[-1]}: {count} members, {split})")
    print(f"Loaded {done:,} roll call(s), {fails:,} failed, {len(urls) - len(todo):,} already present")
    for f in failed[:10]:
        print(f"  FAILED {f}")
    if fails:
        print("  Re-run the same command to retry failures; cached files are reused.")
    report_unresolved(con)


def cache_name(url):
    """clerk.house.gov/evs/2025/roll102.xml -> clerk.house.gov_evs_2025_roll102.xml (House roll numbers restart each year)."""
    return re.sub(r"[^A-Za-z0-9._-]+", "_", url.split("://", 1)[-1])[:180]


def report_unresolved(con):
    """Members on a roll call who are not in the roster can't be placed on the map; list them."""
    if not con.execute("SELECT 1 FROM sqlite_master WHERE name = 'legislators'").fetchone():
        return
    rows = con.execute("SELECT mv.member_key, MAX(mv.member_name), COUNT(*) FROM member_votes mv LEFT JOIN legislators l "
                       "ON l.bioguide_id = mv.member_key WHERE l.bioguide_id IS NULL GROUP BY mv.member_key").fetchall()
    if rows:
        print(f"  {len(rows)} member id(s) on roll calls are missing from the roster (run load_legislators.py again): "
              + ", ".join(f"{k} {n or ''} ({c} votes)" for k, n, c in rows[:8]))
    else:
        print("  Every member on the loaded roll calls matches the roster.")

def parse_members(root):
    """Same layouts as congress_catalog.roll_call_members, for a pre-parsed XML root."""
    out = []
    for rv in root.iter("recorded-vote"):
        leg = rv.find("legislator")
        if leg is not None:
            out.append({"member_key": leg.get("name-id", ""), "name": (leg.text or "").strip(), "party": leg.get("party", ""),
                        "state": leg.get("state", ""), "position": (rv.findtext("vote") or "").strip()})
    if out:
        return out
    for m in root.iter("member"):
        out.append({"member_key": (m.findtext("lis_member_id") or "").strip(), "name": (m.findtext("member_full") or "").strip(),
                    "party": (m.findtext("party") or "").strip(), "state": (m.findtext("state") or "").strip(),
                    "position": (m.findtext("vote_cast") or "").strip()})
    return out


if __name__ == "__main__":
    main()
