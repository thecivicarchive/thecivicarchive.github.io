"""election/feeds/mastodon.py - Mastodon's public hashtag timelines, counted; official accounts' posts kept.

    python -m election.feeds.mastodon sample --db SCRATCH [--requests 4]   a few requests, counted into a scratch copy

Seven large servers answer their public tag timelines without a login (GET /api/v1/timelines/tag/<tag>, 40 posts a page;
each allows 300 requests in 5 minutes): mastodon.social, mastodon.online, mastodon.world, mas.to, universeodon.com,
journa.host and newsie.social. Each is asked about six tags (four national ones, and two states' "<xx>pol" tags in
turn), so 42 requests every 3 minutes, paced at no more than 14 a minute in all by a background worker that runs only
while the night's cycle keeps calling poll() (it stops itself 10 minutes after the last call). Every request goes
through election/source.py; a 403, a 429 or a challenge stops that server for the night.

Counted, never kept (ARCHITECTURE.md 4.5): a post counts only when its author's account is indexable or discoverable,
is not a bot and has no #nobot in its profile; one post is counted once across servers (by its address, held as a keyed
hash in memory for two hours); a post that names a race (geotag.py's rules on its text, never anyone's location) adds to
that race's counter, and its author, as a keyed hash never written, to the race's people for the hour. Nothing about
the post or its author is written: no id, address, handle, name or text. The place in each timeline is kept in memory
as the newest post's id, and on disk only as a time (feed_state); a restart starts from that time (a post id at Mastodon
is its time in milliseconds, shifted 16 bits).

Kept: posts of the official Mastodon accounts in the accounts table (two anchors each: the site links the account and
Mastodon's own two-way link check marks the site verified), read from each account's public RSS once a cycle. A reply is
not kept, and an @mention of an account not on the official list becomes "(an account)". A post that disappears from
the account's feed while it is still inside the feed's window is removed (deletions honoured). No post is marked for
showing until the site has a public contact address (decision D8).
"""

import argparse
import datetime as dt
import html
import json
import os
import re
import sys
import threading
import time
from urllib.parse import quote

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from election.feeds import geotag as G  # noqa: E402
from election.feeds import keywords as K  # noqa: E402

SERVERS = ("mastodon.social", "mastodon.online", "mastodon.world", "mas.to", "universeodon.com", "journa.host",
           "newsie.social")
NATIONAL = ("election", "uspol", "vote", "midterms")
STATE_TAGS = tuple(f"{c.lower()}pol" for c in sorted(K.STATE_NAMES))
PER_MINUTE = 14
IDLE_STOP = 10 * 60
START_BACK = dt.timedelta(minutes=60)        # a timeline never read before starts an hour back
TAGS_HTML = re.compile(r"<[^>]+>")
AT = re.compile(r"(?<![\w/])@([A-Za-z0-9_]{1,30})(@[A-Za-z0-9.-]+\.[a-z]{2,})?")


def snowflake(t):
    """Mastodon's id for a moment: milliseconds since 1970, shifted 16 bits."""
    return str(int(t.timestamp() * 1000) << 16)


def time_of(sid):
    try:
        return dt.datetime.fromtimestamp((int(sid) >> 16) / 1000, G.UTC)
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def strip_html(s):
    s = re.sub(r"<br\s*/?>|</p>\s*<p>", " ", s or "", flags=re.I)
    return " ".join(html.unescape(TAGS_HTML.sub(" ", s)).split())


def scrub(text, allowed):
    def rep(m):
        acct = (m.group(1) + (m.group(2) or "")).lower()
        return m.group(0) if acct in allowed or any(a.startswith(acct + "@") for a in allowed) else "(an account)"
    return AT.sub(rep, text)


def official_accounts(con):
    """{"user@server": (account_id, account, owner_kind, owner, owner_ref, state, site, proof, feed)}."""
    out = {}
    try:
        for row in con.execute("SELECT account, account_id, account, owner_kind, owner, owner_ref, state, site, proof, "
                               "feed FROM accounts WHERE platform='mastodon' AND active=1"):
            out[row[0].lower().lstrip("@")] = row[1:]
    except Exception:  # noqa: BLE001
        pass
    return out


class Timelines:
    """The counting side: one request at a time, a post counted once, nothing kept but numbers."""

    def __init__(self, src, db=None, say=print, witness=None):
        self.src, self.db, self.say, self.witness = src, db, say, witness
        self.counter = G.SocialCounter("mastodon")
        self.cursor = {}                # (server, tag) -> newest id read (memory only)
        self.jobs, self.turn = [], 0
        self.stats = {"requests": 0, "posts": 0, "counted_accounts_skipped": 0, "matched": 0, "official_seen": 0,
                      "refused": 0, "failed": 0}
        con = G.open_db(db)
        self.official = official_accounts(con)
        con.close()

    def plan(self):
        """This cycle's 42 requests: every server, the four national tags and two states' tags in turn."""
        jobs = []
        for i, server in enumerate(SERVERS):
            for tag in NATIONAL:
                jobs.append((server, tag))
            for k in range(2):
                jobs.append((server, STATE_TAGS[(self.turn * len(SERVERS) * 2 + i * 2 + k) % len(STATE_TAGS)]))
        self.turn += 1
        return jobs

    def one(self, con, server, tag):
        from election.source import Refused, SourceError
        key = (server, tag)
        since = self.cursor.get(key)
        if since is None:
            stored = G.state_get(con, f"mastodon:{server}:{tag}")
            t = G.parse_time(stored) if stored else None
            since = snowflake(max(t, G.utcnow() - dt.timedelta(hours=6)) if t else G.utcnow() - START_BACK)
        url = f"https://{server}/api/v1/timelines/tag/{quote(tag)}?limit=40&min_id={since}"
        try:
            r = self.src.get(url, accept="application/json", timeout=30)
        except Refused:
            self.stats["refused"] += 1
            return
        except SourceError:
            self.stats["failed"] += 1
            return
        self.stats["requests"] += 1
        if r.refused:
            self.stats["refused"] += 1
            return
        if not r.ok:
            self.stats["failed"] += 1
            return
        try:
            posts = json.loads(r.body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            self.stats["failed"] += 1
            return
        if not isinstance(posts, list):
            return
        newest = since
        for p in posts:
            if not isinstance(p, dict):
                continue
            pid = str(p.get("id") or "")
            if pid.isdigit() and int(pid) > int(newest):
                newest = pid
            self._post(con, server, p)
        self.cursor[key] = newest
        t = time_of(newest)
        if t:
            G.state_set(con, f"mastodon:{server}:{tag}", G.iso(t))

    def _post(self, con, server, p):
        acc = p.get("account") or {}
        acct = (acc.get("acct") or "").lower()
        full = acct if "@" in acct else f"{acct}@{server}"
        w = self.witness
        if w is not None and full not in self.official:
            ids = w.setdefault("ids", set())
            ids.update(x for x in (full, acct, str(acc.get("id") or ""), str(p.get("id") or ""), p.get("uri") or "",
                                   p.get("url") or "", acc.get("url") or "") if x)
            if acc.get("display_name"):
                w.setdefault("names", set()).add(acc["display_name"])
        self.stats["posts"] += 1
        if full in self.official:
            self.stats["official_seen"] += 1             # kept from the account's own feed, not from here
            return
        if acc.get("bot") or "#nobot" in (acc.get("note") or "").lower():
            self.stats["counted_accounts_skipped"] += 1
            return
        if not (acc.get("indexable") or acc.get("discoverable")):
            self.stats["counted_accounts_skipped"] += 1
            return
        if p.get("reblog"):
            return
        when = G.parse_time(p.get("created_at")) or G.utcnow()
        when = min(when, G.utcnow())
        if self.counter.seen_post(p.get("uri") or p.get("url") or "", when):
            return
        text = strip_html(p.get("content"))
        races = G.races_in(G.placer().place(text, None, post=True))
        if races:
            self.stats["matched"] += 1
            self.counter.add(acc.get("url") or full, races, when)


# ==================================================================================================== official posts

ITEM = re.compile(r"<item\b[^>]*>(.*?)</item\s*>", re.S | re.I)


def _field(inner, tag):
    m = re.search(rf"<{tag}\b[^>]*>(.*?)</{tag}\s*>", inner, re.S | re.I)
    if not m:
        return ""
    v = m.group(1)
    c = re.match(r"\s*<!\[CDATA\[(.*?)\]\]>\s*$", v, re.S)
    return c.group(1) if c else html.unescape(v)


def official_round(src, con, accounts, allowed, stats):
    """Each official account's public RSS: new posts kept, vanished ones removed."""
    from election.feeds.bluesky import keep_post
    from election.source import Refused, SourceError
    for key, acc in accounts.items():
        account_id, _a, owner_kind, owner, owner_ref, state, site, proof, feed = acc
        if not feed:
            continue
        try:
            r = src.get(feed, accept="application/rss+xml, application/xml", conditional=True, timeout=30)
        except (Refused, SourceError):
            continue
        if r.not_modified or not r.ok:
            continue
        body = r.body.decode("utf-8", "replace")
        present, oldest = set(), None
        for inner in ITEM.findall(body):
            link = _field(inner, "link").strip()
            if not link.startswith("https://"):
                continue
            address = G.canonical(link) or link
            present.add(address)
            when = G.parse_time(_field(inner, "pubDate"))
            if when and (oldest is None or when < oldest):
                oldest = when
            if re.search(r"<thr:in-reply-to|in_reply_to", inner):
                continue
            text = scrub(strip_html(_field(inner, "description")), allowed)
            if text:
                keep_post(con, "mastodon", (account_id, key, owner_kind, owner, owner_ref, state, site, proof),
                          address, text, when, stats)
        if oldest:
            for (address, pub) in con.execute("SELECT address, published_at FROM items WHERE account_id=? AND "
                                              "source='mastodon'", (account_id,)).fetchall():
                t = G.parse_time(pub)
                if t and t >= oldest and address not in present:
                    stats["deleted"] = stats.get("deleted", 0) + G.remove_post(con, "mastodon", address)


# ==================================================================================================== the worker and poll()

_WORKER = {"thread": None, "last_poll": 0.0, "tl": None, "lock": threading.Lock(), "stop": threading.Event()}


def _work(tl):
    con = G.open_db(tl.db)
    gap = 60.0 / PER_MINUTE
    try:
        while not _WORKER["stop"].is_set():
            if time.monotonic() - _WORKER["last_poll"] > IDLE_STOP:
                break
            for server, tag in tl.plan():
                if _WORKER["stop"].is_set() or time.monotonic() - _WORKER["last_poll"] > IDLE_STOP:
                    break
                t0 = time.monotonic()
                tl.one(con, server, tag)
                left = gap - (time.monotonic() - t0)
                if left > 0 and _WORKER["stop"].wait(left):
                    break
    finally:
        try:
            tl.counter.flush(con)
        except Exception:  # noqa: BLE001
            pass
        con.close()


def poll(src=None, now=None, rehearsal=False, say=print, db=None):
    """Keeps the paced worker going, writes the counts gathered since the last call, and reads the official accounts'
    feeds. Returns counts for the log."""
    if src is None:
        from election.feeds import accounts
        from election.source import Source
        src = Source(stopped_file=os.path.join(G.CACHE, "stopped_hosts.json"), log=accounts._log)
    with _WORKER["lock"]:
        _WORKER["last_poll"] = time.monotonic()
        if _WORKER["thread"] is None or not _WORKER["thread"].is_alive():
            _WORKER["stop"].clear()
            _WORKER["tl"] = Timelines(src, db=db, say=say)
            _WORKER["thread"] = threading.Thread(target=_work, args=(_WORKER["tl"],), name="mastodon", daemon=True)
            _WORKER["thread"].start()
        tl = _WORKER["tl"]
    con = G.open_db(db)
    try:
        tl.counter.flush(con)
        stats = {}
        allowed = set(tl.official)
        official_round(src, con, tl.official, allowed, stats)
        G.refresh_shown(con)
    finally:
        con.close()
    return dict(tl.stats, **stats)


def stop():
    _WORKER["stop"].set()
    t = _WORKER["thread"]
    if t is not None:
        t.join(30)


def sample(src=None, say=print, db=None, requests=4, witness=None):
    """A few requests (two servers, two national tags each), at the worker's pace, then the official feeds."""
    if src is None:
        from election.feeds import accounts
        from election.source import Source
        src = Source(stopped_file=os.path.join(G.CACHE, "stopped_hosts.json"), log=accounts._log)
    tl = Timelines(src, db=db, say=say, witness=witness)
    con = G.open_db(db)
    try:
        jobs = [(s, t) for s in SERVERS[:2] for t in NATIONAL[:2]][:requests]
        for i, (server, tag) in enumerate(jobs):
            if i:
                time.sleep(60.0 / PER_MINUTE)
            tl.one(con, server, tag)
        tl.counter.flush(con)
        stats = {}
        official_round(src, con, tl.official, set(tl.official), stats)
    finally:
        con.close()
    return dict(tl.stats, **stats, official_accounts=len(tl.official))


def selftest(say=print):
    """Made-up posts (no network): bots, #nobot and accounts that are neither indexable nor discoverable are not
    counted; one post seen on two servers counts once; a counted post leaves only numbers; @mentions scrubbed."""
    import sqlite3
    ok = True

    def check(cond, line):
        nonlocal ok
        say(("PASS " if cond else "FAIL ") + line)
        ok = ok and bool(cond)

    tl = Timelines.__new__(Timelines)
    tl.counter, tl.official, tl.witness = G.SocialCounter("mastodon"), {}, None
    tl.stats = {"posts": 0, "counted_accounts_skipped": 0, "matched": 0, "official_seen": 0}
    con = sqlite3.connect(":memory:")
    con.executescript(G.SCHEMA)
    text = "<p>Minnesota governor race: polls close at 8</p>"

    def post(acct, uri, **acc):
        a = {"acct": acct, "id": "99", "url": f"https://x.example/@{acct}", "discoverable": True, "indexable": True}
        a.update(acc)
        return {"id": "1", "uri": uri, "content": text, "created_at": "2026-11-04T02:00:00Z", "account": a}

    tl._post(con, "mastodon.social", post("botty", "u1", bot=True))
    tl._post(con, "mastodon.social", post("quiet", "u2", note="<p>#NoBot please</p>"))
    tl._post(con, "mastodon.social", post("hidden", "u3", discoverable=False, indexable=False))
    check(tl.stats["counted_accounts_skipped"] == 3 and tl.stats["matched"] == 0,
          "bots, #nobot and accounts neither indexable nor discoverable are not counted")
    tl._post(con, "mastodon.social", post("alice", "https://a.example/1"))
    tl._post(con, "mastodon.online", post("alice@mastodon.social", "https://a.example/1"))
    tl.counter.flush(con)
    n = con.execute("SELECT SUM(items), SUM(people) FROM counts").fetchone()
    check(tuple(n) == (1, 1), f"one post seen on two servers is counted once ({tuple(n)})")
    dump = "\n".join(con.iterdump())
    check("alice" not in dump and "a.example" not in dump, "nothing about the counted post or its author is written")
    s = scrub("Thanks @someone and @news@mas.to", {"news@mas.to"})
    check(s == "Thanks (an account) and @news@mas.to", "an ordinary account's @mention is replaced")
    t = dt.datetime(2026, 11, 4, 2, 0, tzinfo=G.UTC)
    check(time_of(snowflake(t)) == t, "a timeline's place is kept as a time, never a post id")
    return ok


def main(argv):
    ap = argparse.ArgumentParser(prog="mastodon")
    ap.add_argument("cmd", choices=["sample"])
    ap.add_argument("--db")
    ap.add_argument("--requests", type=int, default=4)
    a = ap.parse_args(argv)
    if not a.db:
        print("give --db: a scratch copy of the feed database")
        return 2
    print(json.dumps(sample(db=a.db, requests=a.requests)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
