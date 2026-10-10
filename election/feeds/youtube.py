"""election/feeds/youtube.py - new videos of official YouTube channels, from YouTube's keyless channel feeds.

    python -m election.feeds.youtube poll --db SCRATCH [--limit N]   one round (or the first N channels), waited for

Only channels in the accounts table (two anchors each: the official site links the channel, and the channel's own
links or description name the site). Each channel's feed (https://www.youtube.com/feeds/videos.xml?channel_id=UC...,
its 15 newest uploads) is asked once a round, conditionally, at most one a second, through election/source.py. A round
runs in the background (about three minutes for 190 channels) so the night's other sections are not held up; poll()
starts one when none is running and returns what the last finished round found. YouTube's search needs a key and
allows 100 searches a day, so it is not used.

Fields read (an allowlist): each upload's title, its watch address and its time. Never the description, the thumbnail
or anything under media:group (a reader's browser would contact YouTube to show a thumbnail; the page shows none).
Kept as posts of their account (kind "post"): a newsroom's video only when it is about an election or names a
candidate; a candidate's or an election office's videos of the last week. A video that leaves the channel's feed while
still inside the feed's window is removed (deletions honoured). No post is marked for showing until the site has a
public contact address (decision D8).
"""

import argparse
import datetime as dt
import json
import os
import re
import sys
import threading
import time

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from election.feeds import geotag as G  # noqa: E402
from election.feeds.rss import items_of  # noqa: E402

MAX_AGE = dt.timedelta(days=7)
WATCH = re.compile(r"^https://(?:www\.)?youtube\.com/watch\?v=[\w-]{6,20}$")


def channels(con):
    out = []
    try:
        for row in con.execute("SELECT account_id, account, owner_kind, owner, owner_ref, state, site, proof, feed FROM "
                               "accounts WHERE platform='youtube' AND active=1 ORDER BY state, owner"):
            if row[8] and row[8].startswith("https://www.youtube.com/feeds/videos.xml?channel_id="):
                out.append(row)
    except Exception:  # noqa: BLE001
        pass
    return out


def one_round(src, db=None, limit=None, stats=None):
    from election.feeds.bluesky import keep_post
    from election.source import Refused, SourceError
    stats = stats if stats is not None else {}
    stats.update({"channels": 0, "answered": 0, "unchanged": 0, "failed": 0, "refused": 0, "videos": 0, "kept": 0,
                  "removed": 0})
    con = G.open_db(db)
    try:
        chans = channels(con)[:limit] if limit else channels(con)
        stats["channels"] = len(chans)
        now = G.utcnow()
        for row in chans:
            account_id, account, owner_kind, owner, owner_ref, state, site, proof, feed = row
            t0 = time.monotonic()
            try:
                r = src.get(feed, accept="application/atom+xml, application/xml", conditional=True, timeout=30)
            except Refused:
                stats["refused"] += 1
                if src.stopped("www.youtube.com"):
                    break                                   # the host is stopped for the night
                continue
            except SourceError:
                stats["failed"] += 1
                continue
            finally:
                left = 1.0 - (time.monotonic() - t0)
                if left > 0:
                    time.sleep(left)
            if r.not_modified:
                stats["unchanged"] += 1
                continue
            if r.refused or not r.ok:
                stats["refused" if r.refused else "failed"] += 1
                if r.refused:
                    break
                continue
            stats["answered"] += 1
            present, oldest = set(), None
            for title, link, when in items_of(r.body):
                if not WATCH.match(link):
                    continue
                stats["videos"] += 1
                address = G.canonical(link)
                present.add(address)
                pub = G.parse_time(when)
                if pub and (oldest is None or pub < oldest):
                    oldest = pub
                if not title or (pub and now - pub > MAX_AGE):
                    continue
                acc = (account_id, account, owner_kind, owner, owner_ref, state, site, proof)
                if keep_post(con, "youtube", acc, address, title, pub, None):
                    stats["kept"] += 1
            if oldest:
                for address, pub in con.execute("SELECT address, published_at FROM items WHERE account_id=? AND "
                                                "source='youtube'", (account_id,)).fetchall():
                    t = G.parse_time(pub)
                    if t and t >= oldest and address not in present:
                        stats["removed"] += G.remove_post(con, "youtube", address)
        G.refresh_shown(con)
    finally:
        con.close()
    return stats


_ROUND = {"thread": None, "last": None, "lock": threading.Lock()}


def poll(src=None, now=None, rehearsal=False, say=print, db=None, limit=None, wait=False):
    """Starts a round in the background when none is running; returns the last finished round's counts."""
    if src is None:
        from election.feeds import accounts
        from election.source import Source
        src = Source(stopped_file=os.path.join(G.CACHE, "stopped_hosts.json"), log=accounts._log)
    if wait:
        return one_round(src, db, limit)
    with _ROUND["lock"]:
        t = _ROUND["thread"]
        if t is None or not t.is_alive():
            def run():
                s = {}
                try:
                    one_round(src, db, limit, s)
                finally:
                    _ROUND["last"] = dict(s, finished=G.iso(G.utcnow()))
            _ROUND["thread"] = threading.Thread(target=run, name="youtube", daemon=True)
            _ROUND["thread"].start()
            started = True
        else:
            started = False
    return {"round": "started" if started else "still running", "last": _ROUND["last"]}


def main(argv):
    ap = argparse.ArgumentParser(prog="youtube")
    ap.add_argument("cmd", choices=["poll"])
    ap.add_argument("--db")
    ap.add_argument("--limit", type=int)
    a = ap.parse_args(argv)
    if not a.db:
        print("give --db: a scratch copy of the feed database")
        return 2
    print(json.dumps(poll(db=a.db, limit=a.limit, wait=True)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
