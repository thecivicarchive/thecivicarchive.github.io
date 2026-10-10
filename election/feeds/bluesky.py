"""election/feeds/bluesky.py - Bluesky's open stream: everyone counted, official accounts' posts kept, deletions honoured.

    python -m election.feeds.bluesky sample [--seconds 60] --db SCRATCH   both streams for a while, into a scratch copy
    python -m election.feeds.bluesky sweep [--db FILE]                     ask Bluesky which kept posts still exist

Two connections to Jetstream (Bluesky's free, keyless live stream of public events; jetstream1 and jetstream2, east
and west, the same JSON), through Python's own library (a small WebSocket client below), with the kit's honest
User-Agent, after election/source.py's gate has said the host may be asked:

  THE COUNTING STREAM (wantedCollections=app.bsky.feed.post, about 30 posts a second). Each new post's text is matched
  in memory against the races' words (geotag.py, rules 1, 1b and 2 on the text alone: never anyone's location); a post
  that names a race adds one to that race's counter for the minute, and its author, as a keyed hash that is never
  written, to the race's set of people for the clock hour (geotag.SocialCounter). Reposts are a different collection
  and are not read. Nothing about the post or its author is written anywhere: no id, handle, text or record key. Each
  minute only the numbers go to the counts table. This stream does not resume after a drop (counts missed while the
  computer was off are simply missing).

  THE OFFICIAL STREAM (wantedDids = the official Bluesky accounts in the accounts table, two anchors each). A new post
  is kept in items (kind "post": its text, time, account and a link; never images), placed by its text with the
  account's state as context; a newsroom's post is kept only when it is about an election or names a candidate. A
  post that is a reply is not kept (its context is someone else's), and an @mention of an account not on the official
  list is replaced by "(an account)" before the text is kept. Bluesky's developer guidelines ask that deletions be
  honoured: a delete event removes the post at once (the deletions table notes the address); an account that goes
  inactive (an account event) is marked inactive and its posts are no longer marked for showing; a handle that leaves
  the site's domain breaks that account's second anchor and marks it inactive too. This stream resumes from its cursor
  (a time, kept in feed_state) after a drop, and every 30 minutes the kept posts of the last week are checked against
  Bluesky's public read host (app.bsky.feed.getPosts, 25 at a time) and any that are gone are removed.

No post is marked for showing until the site has a public contact address (decision D8; accounts.CONTACT_ADDRESS).
"""

import argparse
import base64
import datetime as dt
import json
import os
import re
import socket
import ssl
import struct
import sys
import threading
import time
from urllib.parse import quote, urlsplit

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from election.feeds import geotag as G  # noqa: E402
from states import net  # noqa: E402

HOSTS = ("jetstream2.us-east.bsky.network", "jetstream1.us-east.bsky.network",
         "jetstream1.us-west.bsky.network", "jetstream2.us-west.bsky.network")
POST = "app.bsky.feed.post"
PUBLIC = "https://public.api.bsky.app/xrpc/"
FLUSH_EVERY = 60
SWEEP_EVERY = 30 * 60
SWEEP_DAYS = 7
MENTION = re.compile(r"(?<![\w@])@([a-z0-9][a-z0-9.-]*\.[a-z]{2,})", re.I)


# ==================================================================================================== a WebSocket

class Refusal(Exception):
    def __init__(self, status):
        super().__init__(f"answered {status}")
        self.status = status


class WebSocket:
    """A small client for one text stream (RFC 6455): the upgrade, frames in, pings answered, frames out masked."""

    def __init__(self, url, stop, timeout=30):
        s = urlsplit(url)
        self.host, self.stop = s.hostname, stop
        path = s.path + ("?" + s.query if s.query else "")
        net.patient_lookups()
        raw = socket.create_connection((self.host, s.port or 443), timeout=timeout)
        try:
            import certifi
            ctx = ssl.create_default_context(cafile=certifi.where())
        except ImportError:
            ctx = ssl.create_default_context()
        self.sock = ctx.wrap_socket(raw, server_hostname=self.host)       # certificate checking stays on
        key = base64.b64encode(os.urandom(16)).decode()
        req = (f"GET {path} HTTP/1.1\r\nHost: {self.host}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
               f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\nUser-Agent: {net.UA}\r\n\r\n")
        self.sock.sendall(req.encode("ascii"))
        self.buf = b""
        head = self._until(b"\r\n\r\n")
        status = int(head.split(b" ", 2)[1]) if head.startswith(b"HTTP/") else 0
        if status != 101:
            self.close()
            raise Refusal(status)
        self.sock.settimeout(5)

    def _fill(self):
        while True:
            if self.stop.is_set():
                raise EOFError("stopped")
            try:
                chunk = self.sock.recv(65536)
            except socket.timeout:
                continue
            if not chunk:
                raise EOFError("closed")
            self.buf += chunk
            return

    def _until(self, mark):
        while mark not in self.buf:
            self._fill()
        head, _, self.buf = self.buf.partition(mark)
        return head

    def _exact(self, n):
        while len(self.buf) < n:
            self._fill()
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def send(self, opcode, payload=b""):
        mask = os.urandom(4)
        n = len(payload)
        head = bytes([0x80 | opcode])
        if n < 126:
            head += bytes([0x80 | n])
        elif n < 65536:
            head += bytes([0x80 | 126]) + struct.pack(">H", n)
        else:
            head += bytes([0x80 | 127]) + struct.pack(">Q", n)
        body = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        self.sock.sendall(head + mask + body)

    def recv(self):
        """The next whole message (bytes), or None when the server closed the stream."""
        parts = []
        while True:
            b1, b2 = self._exact(2)
            fin, op = b1 & 0x80, b1 & 0x0F
            n = b2 & 0x7F
            if n == 126:
                n = struct.unpack(">H", self._exact(2))[0]
            elif n == 127:
                n = struct.unpack(">Q", self._exact(8))[0]
            mask = self._exact(4) if b2 & 0x80 else None
            data = self._exact(n)
            if mask:
                data = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
            if op == 0x8:
                try:
                    self.send(0x8)
                except OSError:
                    pass
                return None
            if op == 0x9:
                self.send(0xA, data)
                continue
            if op == 0xA:
                continue
            parts.append(data)
            if fin:
                return b"".join(parts)

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


# ==================================================================================================== the collector

def official_accounts(con):
    """{did: (account_id, handle, owner_kind, owner, owner_ref, state, site, proof)} for active official accounts."""
    out = {}
    try:
        for row in con.execute("SELECT platform_id, account_id, account, owner_kind, owner, owner_ref, state, site, proof "
                               "FROM accounts WHERE platform='bluesky' AND active=1"):
            out[row[0]] = row[1:]
    except Exception:  # noqa: BLE001
        pass
    return out


def official_handles(con):
    try:
        return {r[0].lower() for r in con.execute("SELECT account FROM accounts WHERE platform='bluesky'")}
    except Exception:  # noqa: BLE001
        return set()


def scrub_mentions(text, allowed):
    return MENTION.sub(lambda m: m.group(0) if m.group(1).lower() in allowed else "(an account)", text or "")


def post_address(did, rkey):
    return f"https://bsky.app/profile/{did}/post/{rkey}"


class Collector:
    def __init__(self, src, say=print, db=None, witness=None, counting=True, official=True):
        self.src, self.say, self.db = src, say, db
        self.stop_ev = threading.Event()
        self.counter = G.SocialCounter("bluesky")
        self.witness = witness              # a test's dict: ordinary accounts seen, kept in memory for the scan
        self.threads = []
        self.counting, self.official = counting, official
        self.stats = {"events": 0, "posts": 0, "matched": 0, "official_kept": 0, "deleted": 0, "inactive": 0,
                      "connects": 0, "drops": 0}
        self._sockets = []
        self._lock = threading.Lock()
        con = G.open_db(db)
        self.accounts = official_accounts(con)
        self.allowed = official_handles(con)
        con.close()

    # ------------------------------------------------------------------ lifecycle
    def start(self):
        if self.counting:
            self.threads.append(threading.Thread(target=self._run, args=("counting",), name="bsky-count", daemon=True))
        if self.official and self.accounts:
            self.threads.append(threading.Thread(target=self._run, args=("official",), name="bsky-official",
                                                 daemon=True))
        for t in self.threads:
            t.start()
        return self

    def stop(self):
        self.stop_ev.set()
        with self._lock:
            for ws in self._sockets:
                ws.close()
        for t in self.threads:
            t.join(20)
        con = G.open_db(self.db)
        try:
            self.counter.flush(con)
        finally:
            con.close()

    # ------------------------------------------------------------------ one stream
    def _url(self, host, which, cursor=None):
        url = f"wss://{host}/subscribe?wantedCollections={POST}"
        if which == "official":
            url += "".join(f"&wantedDids={quote(d, safe=':')}" for d in sorted(self.accounts))
            if cursor:
                url += f"&cursor={int(cursor)}"
        return url

    def _run(self, which):
        from election.source import Refused
        con = G.open_db(self.db)
        backoff, i = 5, 0
        last_flush = last_sweep = time.monotonic()
        try:
            while not self.stop_ev.is_set():
                host = HOSTS[i % len(HOSTS)]
                i += 1
                try:
                    self.src.check(f"https://{host}/subscribe")
                except Refused:
                    if all(self.src.stopped(h) for h in HOSTS):
                        self.say(f"Bluesky's {which} stream: every Jetstream host is stopped for the night")
                        return
                    continue
                cursor = None
                if which == "official":
                    c = G.state_get(con, "bluesky:official:cursor")
                    if c:
                        cursor = max(int(c) - 5_000_000, int((time.time() - 2 * 86400) * 1e6))
                t0 = time.monotonic()
                try:
                    ws = WebSocket(self._url(host, which, cursor), self.stop_ev)
                except Refusal as e:
                    self.src.log(f"-- WS {host}/subscribe {e.status} 0B {time.monotonic() - t0:.2f}s")
                    if e.status in (403, 429):
                        self.src.stop_host(host, f"answered {e.status}")
                    time.sleep(min(backoff, 300))
                    backoff = min(backoff * 2, 300)
                    continue
                except (OSError, EOFError, ValueError):
                    self.src.log(f"-- WS {host}/subscribe no answer")
                    if self.stop_ev.wait(min(backoff, 300)):
                        break
                    backoff = min(backoff * 2, 300)
                    continue
                self.src.log(f"-- WS {host}/subscribe 101 {which} stream {time.monotonic() - t0:.2f}s")
                with self._lock:
                    self._sockets.append(ws)
                    self.stats["connects"] += 1
                backoff = 5
                try:
                    while not self.stop_ev.is_set():
                        msg = ws.recv()
                        if msg is None:
                            break
                        self.stats["events"] += 1
                        try:
                            ev = json.loads(msg)
                        except ValueError:
                            continue
                        try:
                            if which == "counting":
                                self._count(ev)
                            else:
                                self._official(con, ev)
                        except Exception:  # noqa: BLE001 - one bad event never stops a stream; nothing of it is logged
                            self.stats["errors"] = self.stats.get("errors", 0) + 1
                        now = time.monotonic()
                        if now - last_flush >= FLUSH_EVERY:
                            last_flush = now
                            if which == "counting":
                                self.counter.flush(con)
                            elif ev.get("time_us"):
                                G.state_set(con, "bluesky:official:cursor", str(int(ev["time_us"])))
                        if which == "official" and now - last_sweep >= SWEEP_EVERY:
                            last_sweep = now
                            self.stats["deleted"] += sweep(self.src, con, say=self.say)
                except (OSError, EOFError, ValueError, struct.error):
                    pass
                finally:
                    ws.close()
                    with self._lock:
                        if ws in self._sockets:
                            self._sockets.remove(ws)
                if not self.stop_ev.is_set():
                    self.stats["drops"] += 1
                    self.stop_ev.wait(3)
        finally:
            if which == "counting":
                try:
                    self.counter.flush(con)
                except Exception:  # noqa: BLE001
                    pass
            con.close()

    # ------------------------------------------------------------------ the counting stream (memory only)
    def _count(self, ev):
        w = self.witness
        if w is not None:                                   # a test: what to look for on disk afterwards
            ids = w.setdefault("ids", set())
            if ev.get("did") and ev["did"] not in self.accounts:
                ids.add(ev["did"])
                if ev.get("kind") == "commit" and (ev.get("commit") or {}).get("rkey"):
                    ids.add(ev["commit"]["rkey"])
                if ev.get("kind") == "identity" and (ev.get("identity") or {}).get("handle"):
                    ids.add(ev["identity"]["handle"])
        if ev.get("kind") != "commit":
            return
        c = ev.get("commit") or {}
        if c.get("operation") != "create" or c.get("collection") != POST:
            return
        did = ev.get("did") or ""
        if did in self.accounts:
            return                                          # official posts are the other stream's
        self.stats["posts"] += 1
        text = (c.get("record") or {}).get("text") or ""
        if not text:
            return
        races = G.races_in(G.placer().place(text, None, post=True))
        if races:
            self.stats["matched"] += 1
            when = dt.datetime.fromtimestamp(ev.get("time_us", time.time() * 1e6) / 1e6, G.UTC)
            self.counter.add(did, races, when)

    # ------------------------------------------------------------------ the official stream
    def _official(self, con, ev):
        did = ev.get("did")
        acc = self.accounts.get(did)
        kind = ev.get("kind")
        if kind == "account":
            a = ev.get("account") or {}
            active = 1 if a.get("active") else 0
            with con:
                con.execute("UPDATE accounts SET active=? WHERE platform='bluesky' AND platform_id=?", (active, did))
            if not active:
                self.stats["inactive"] += 1
            G.refresh_shown(con)
            return
        if kind == "identity" and acc:
            handle = ((ev.get("identity") or {}).get("handle") or "").lower()
            domain = _owner_domain(acc[6])
            if handle and acc[7].startswith("the account's handle is") and not (handle == domain or
                                                                                 handle.endswith("." + domain)):
                with con:
                    con.execute("UPDATE accounts SET active=0 WHERE platform='bluesky' AND platform_id=?", (did,))
                self.stats["inactive"] += 1
                G.refresh_shown(con)
            return
        if kind != "commit" or not acc:
            return
        c = ev.get("commit") or {}
        if c.get("collection") != POST or not c.get("rkey"):
            return
        address = post_address(did, c["rkey"])
        if c.get("operation") == "delete":
            if G.remove_post(con, "bluesky", address):
                self.stats["deleted"] += 1
            return
        if c.get("operation") != "create":
            return
        rec = c.get("record") or {}
        if rec.get("reply"):
            return                                          # a reply's context is someone else's post
        text = scrub_mentions(" ".join((rec.get("text") or "").split()), self.allowed)
        if not text:
            return
        keep_post(con, "bluesky", acc, address, text, rec.get("createdAt"), self.stats)


def _owner_domain(site):
    from election.feeds.accounts import owner_domain
    return owner_domain(site)


def keep_post(con, platform, acc, address, text, created, stats=None):
    """An official account's post into items (kind post), placed by its text with the account's state as context.
    acc: (account_id, handle, owner_kind, owner, owner_ref, state, site, proof)."""
    account_id, _handle, owner_kind, owner, owner_ref, state, _site, _proof = acc
    places = G.placer().place(text, state, post=True)
    election = G.is_election(text)
    if owner_kind == "newsroom" and not (election or any(p["place_kind"] == "race" for p in places)):
        return False
    new = G.store_item(con, source=platform, kind="post", address=address, link=address, headline=text,
                       published=created, fetched=G.utcnow(), outlet_key=owner_ref or owner, outlet_name=owner,
                       account_id=account_id, home_state=state, election=election, places=places)
    if new and stats is not None:
        stats["official_kept"] = stats.get("official_kept", 0) + 1
    return new


# ==================================================================================================== the sweep

def sweep(src, con, say=print, days=SWEEP_DAYS):
    """Kept Bluesky posts of the last `days` that Bluesky no longer serves are removed (deleted, or the account gone)."""
    from election.source import Refused, SourceError
    cut = G.iso(G.utcnow() - dt.timedelta(days=days))
    rows = [r[0] for r in con.execute("SELECT address FROM items WHERE source='bluesky' AND kind='post' AND "
                                      "fetched_at >= ?", (cut,))]
    gone = 0
    for i in range(0, len(rows), 25):
        chunk = rows[i:i + 25]
        uris = []
        for a in chunk:
            m = re.match(r"https://bsky\.app/profile/([^/]+)/post/([^/?#]+)$", a)
            if m:
                uris.append((a, f"at://{m.group(1)}/{POST}/{m.group(2)}"))
        if not uris:
            continue
        url = PUBLIC + "app.bsky.feed.getPosts?" + "&".join("uris=" + quote(u, safe="") for _a, u in uris)
        try:
            r = src.get(url, accept="application/json", timeout=30)
        except (Refused, SourceError):
            return gone
        if not r.ok:
            return gone
        try:
            have = {p.get("uri") for p in json.loads(r.body.decode("utf-8")).get("posts", [])}
        except (ValueError, AttributeError):
            return gone
        for a, u in uris:
            if u not in have:
                gone += G.remove_post(con, "bluesky", a)
    return gone


# ==================================================================================================== the self-test

def selftest(say=print):
    """Made-up events (no network, a database in memory): an official post kept and not shown (D8 off), a reply not
    kept, an ordinary account's @mention scrubbed, a deletion honoured, an inactive account and a handle that left its
    domain marked inactive, an ordinary post counted with nothing about it written, a WebSocket frame read back."""
    import sqlite3
    from election.feeds import accounts as A
    ok = True

    def check(cond, line):
        nonlocal ok
        say(("PASS " if cond else "FAIL ") + line)
        ok = ok and bool(cond)

    con = sqlite3.connect(":memory:")
    con.executescript(A.SCHEMA)
    con.executescript(G.SCHEMA)
    did, ordinary = "did:plc:aaaaaaaaaaaaaaaaaaaaaaaa", "did:plc:bbbbbbbbbbbbbbbbbbbbbbbb"
    con.execute("INSERT INTO accounts (account_id, platform, account, platform_id, owner_kind, owner, owner_ref, state, "
                "race_id, site, linked_from, link_kind, proof, feed, checked_on, active, shown) VALUES "
                "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,0)",
                ("bluesky:" + did, "bluesky", "news.example.org", did, "newsroom", "Example News", "example.org", "MN",
                 None, "https://example.org/", "https://example.org/", "a link on the page",
                 "the account's handle is the site's own domain (news.example.org)", did, "2026-10-10"))
    col = Collector.__new__(Collector)
    col.accounts = official_accounts(con)
    col.allowed = official_handles(con)
    col.stats = {"official_kept": 0, "deleted": 0, "inactive": 0, "posts": 0, "matched": 0}
    col.witness = None
    col.counter = G.SocialCounter("bluesky")

    def ev(op, rkey, text=None, reply=False, who=did):
        rec = {"text": text, "createdAt": "2026-11-04T02:00:00Z"}
        if reply:
            rec["reply"] = {"parent": {"uri": "at://x"}}
        return {"did": who, "time_us": 1, "kind": "commit",
                "commit": {"operation": op, "collection": POST, "rkey": rkey, "record": rec if op == "create" else None}}

    col._official(con, ev("create", "3kaaaaaaaaaa2", "Election night in Minnesota: polls close at 8. Thanks "
                                                   "@someone.bsky.social and @news.example.org"))
    col._official(con, ev("create", "3kaaaaaaaaaa3", "Replying about the election", reply=True))
    rows = con.execute("SELECT headline, shown, kind FROM items").fetchall()
    check(len(rows) == 1 and rows[0][1] == 0 and rows[0][2] == "post",
          "an official post is kept as a post and not marked for showing (no contact address, D8); a reply is not kept")
    check(rows and "(an account)" in rows[0][0] and "someone" not in rows[0][0] and "@news.example.org" in rows[0][0],
          "an ordinary account's @mention is replaced; an official one stays")
    col._official(con, ev("delete", "3kaaaaaaaaaa2"))
    check(con.execute("SELECT COUNT(*) FROM items").fetchone()[0] == 0 and
          con.execute("SELECT COUNT(*) FROM deletions").fetchone()[0] == 1, "a deleted post is removed at once and noted")
    col._official(con, {"did": did, "kind": "account", "account": {"active": False, "did": did}})
    check(con.execute("SELECT active FROM accounts").fetchone()[0] == 0, "an account that goes inactive is marked so")
    con.execute("UPDATE accounts SET active=1")
    col._official(con, {"did": did, "kind": "identity", "identity": {"did": did, "handle": "someone-else.bsky.social"}})
    check(con.execute("SELECT active FROM accounts").fetchone()[0] == 0,
          "a handle that leaves the site's domain breaks the second anchor: marked inactive")
    before = con.execute("SELECT COUNT(*) FROM items").fetchone()[0]
    col._count(ev("create", "3kbbbbbbbbbb2", "Minnesota governor race: who wins?", who=ordinary))
    col.counter.flush(con)
    dump = "\n".join(con.iterdump())
    check(ordinary not in dump and "3kbbbbbbbbbb2" not in dump and before == con.execute(
        "SELECT COUNT(*) FROM items").fetchone()[0], "an ordinary post is counted in memory; nothing about it is written")
    # a WebSocket frame, as a server sends it, read back
    ws = WebSocket.__new__(WebSocket)
    ws.stop = threading.Event()
    msg = b'{"kind":"commit"}'
    ws.buf = bytes([0x81, len(msg)]) + msg
    ws.sock = None
    check(ws.recv() == msg, "a WebSocket text frame is read whole")
    return ok


# ==================================================================================================== the night's entry points

def start(src=None, say=print, db=None):
    """Both streams in the background (election/live.py calls this once); returns the collector, which has stop()."""
    if src is None:
        from election.feeds import accounts
        from election.source import Source
        src = Source(stopped_file=os.path.join(G.CACHE, "stopped_hosts.json"), log=accounts._log)
    return Collector(src, say=say, db=db).start()


def sample(seconds=60, src=None, say=print, db=None, witness=None):
    """Both streams for `seconds`, then stopped; returns the counts (never what was counted)."""
    if src is None:
        from election.feeds import accounts
        from election.source import Source
        src = Source(stopped_file=os.path.join(G.CACHE, "stopped_hosts.json"), log=accounts._log)
    col = Collector(src, say=say, db=db, witness=witness).start()
    t_end = time.monotonic() + seconds
    while time.monotonic() < t_end:
        time.sleep(1)
    col.stop()
    out = dict(col.stats)
    out["official_accounts"] = len(col.accounts)
    out["counted_people_hours_kept_in_memory"] = sum(len(s) for s in col.counter._sets.values())
    con = G.open_db(db)
    out["count_rows"] = con.execute("SELECT COUNT(*) FROM counts WHERE source='bluesky'").fetchone()[0]
    con.close()
    return out


def main(argv):
    ap = argparse.ArgumentParser(prog="bluesky")
    ap.add_argument("cmd", choices=["sample", "sweep", "selftest"])
    ap.add_argument("--seconds", type=int, default=60)
    ap.add_argument("--db")
    a = ap.parse_args(argv)
    if a.cmd == "selftest":
        return 0 if selftest() else 1
    if a.cmd == "sample":
        if not a.db:
            print("give --db: a scratch copy of the feed database")
            return 2
        print(json.dumps(sample(a.seconds, db=a.db, say=lambda s: print(s, flush=True))))
        return 0
    from election.feeds import accounts
    from election.source import Source
    src = Source(stopped_file=os.path.join(G.CACHE, "stopped_hosts.json"), log=accounts._log)
    con = G.open_db(a.db)
    print(json.dumps({"removed": sweep(src, con)}))
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
