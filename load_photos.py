#!/usr/bin/env python3
"""
load_photos.py - official portraits for the members who appear on the site.

    python load_photos.py --db congress_119.sqlite            # every sponsor, cosponsor, voter and current member
    python load_photos.py --db congress_119.sqlite --force    # re-download and re-thumbnail everything

Source: the unitedstates/images project (public-domain official portraits, keyed by Bioguide ID).
Each portrait is reduced to a 120x146 WebP of about 2 KB and stored in the photos table, so the one-file
site can embed several hundred of them and stay small. Originals are cached in ./photo_cache; members with
no portrait are remembered so they are not requested again (use --force to retry them).
"""

import argparse
import datetime as dt
import io
import os
import sqlite3
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    sys.exit("Pillow is required: python -m pip install pillow")

SRC = "https://raw.githubusercontent.com/unitedstates/images/gh-pages/congress/225x275/{id}.jpg"
UA = "Mozilla/5.0 (compatible; congress-catalog/1.0; personal legislative research)"
SIZE = (120, 146)
SCHEMA = """
CREATE TABLE IF NOT EXISTS photos (
  bioguide_id TEXT PRIMARY KEY, webp BLOB, width INTEGER, height INTEGER, status TEXT, source_url TEXT, fetched_at TEXT
);
"""


def log(*a):
    print(*a, flush=True)


def wanted_ids(con):
    has = lambda t: con.execute("SELECT 1 FROM sqlite_master WHERE name = ?", (t,)).fetchone() is not None
    ids = set()
    if has("members"):
        ids |= {r[0] for r in con.execute("SELECT DISTINCT bioguide_id FROM sponsorships")} if has("sponsorships") else set()
        ids |= {r[0] for r in con.execute("SELECT bioguide_id FROM members")}
    if has("member_votes"):
        ids |= {r[0] for r in con.execute("SELECT DISTINCT member_key FROM member_votes")}
    if has("legislators"):
        ids |= {r[0] for r in con.execute("SELECT bioguide_id FROM legislators WHERE is_current = 1")}
        ids = {i for i in ids if i}
        known = {r[0] for r in con.execute("SELECT bioguide_id FROM legislators")}
        ids = {i for i in ids if i in known or i[0].isalpha()}
    return sorted(i for i in ids if i and i[0].isalpha())


def fetch(bid, cache_dir, force):
    path = os.path.join(cache_dir, f"{bid}.jpg")
    url = SRC.format(id=bid)
    if not force and os.path.exists(path) and os.path.getsize(path) > 0:
        return bid, open(path, "rb").read(), url, None
    try:
        raw = urlopen(Request(url, headers={"User-Agent": UA}), timeout=30).read()
    except HTTPError as e:
        return bid, None, url, ("missing" if e.code == 404 else f"http {e.code}")
    except (URLError, TimeoutError, OSError) as e:
        return bid, None, url, f"error {e}"
    with open(path, "wb") as fh:
        fh.write(raw)
    return bid, raw, url, None


def thumbnail(raw):
    im = Image.open(io.BytesIO(raw)).convert("RGB")
    im.thumbnail(SIZE, Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "WEBP", quality=70, method=6)
    return buf.getvalue(), im.size


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", required=True)
    ap.add_argument("--cache-dir", default="photo_cache")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--force", action="store_true", help="re-download every portrait, including ones recorded as missing")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    con = sqlite3.connect(args.db)
    con.executescript(SCHEMA)
    os.makedirs(args.cache_dir, exist_ok=True)
    ids = wanted_ids(con)
    done = {r[0]: r[1] for r in con.execute("SELECT bioguide_id, status FROM photos")}
    todo = [i for i in ids if args.force or i not in done]
    if args.limit:
        todo = todo[:args.limit]
    log(f"{len(ids):,} members appear on the site; {len(ids) - len(todo):,} already handled; {len(todo):,} to fetch")
    now = dt.datetime.now().isoformat(timespec="seconds")
    ok = missing = failed = 0
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        for i, (bid, raw, url, err) in enumerate(pool.map(lambda b: fetch(b, args.cache_dir, args.force), todo), 1):
            if raw:
                try:
                    webp, (w, h) = thumbnail(raw)
                    con.execute("INSERT OR REPLACE INTO photos VALUES (?,?,?,?,?,?,?)", (bid, webp, w, h, "ok", url, now))
                    ok += 1
                except Exception as e:  # noqa: BLE001 - a corrupt file
                    con.execute("INSERT OR REPLACE INTO photos VALUES (?,?,?,?,?,?,?)", (bid, None, None, None, f"bad image {e}", url, now))
                    failed += 1
            elif err == "missing":
                con.execute("INSERT OR REPLACE INTO photos VALUES (?,?,?,?,?,?,?)", (bid, None, None, None, "missing", url, now))
                missing += 1
            else:
                failed += 1
                if failed <= 5:
                    log(f"  {bid}: {err}")
            if i % 100 == 0:
                con.commit()
                log(f"  {i:,}/{len(todo):,} ({ok:,} portraits, {missing:,} none on file)")
    con.commit()
    total = con.execute("SELECT COUNT(*) FROM photos WHERE webp IS NOT NULL").fetchone()[0]
    size = con.execute("SELECT COALESCE(SUM(LENGTH(webp)), 0) FROM photos").fetchone()[0]
    log(f"Portraits: {ok:,} added, {missing:,} not on file, {failed:,} failed, in {time.time() - t0:.0f}s. "
        f"{total:,} stored ({size / 1e6:.1f} MB of WebP). Re-run to retry failures.")


if __name__ == "__main__":
    main()
