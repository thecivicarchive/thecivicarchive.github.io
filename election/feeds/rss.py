"""election/feeds/rss.py - headlines from the 145 news feeds the scouts found answering (ARCHITECTURE.md 3.3, 4.5).

    python -m election.feeds.rss poll [--db FILE] [--limit N] [--state MN]   one round of the feeds

Every 10 minutes on election night (30 in the day before), each active feed in the outlets table is asked once,
conditionally (ETag and Last-Modified, remembered across restarts in feed_state), through election/source.py: the kit's
honest User-Agent, one request at a time to a host, at least a second apart, four hosts at once at most. A 403, a 429 or
a challenge stops that host for the night and is never worked around.

Fields read (an allowlist): an item's title, its link (or a guid that is a permalink) and its time (pubDate, published,
updated, dc:date). Never the description, the summary or the article, even where a feed carries the whole text
(`full_text` in the outlets table); they are not parsed at all.

Kept: a headline about an election (its words) or one that names a candidate on a race's list, published in the last
three days. Placed by geotag.py's rules, the outlet's home state being the state context. An aggregator's item counts
as the outlet it links to (outlet_key is the link's registered domain) and carries the aggregator's name in `via`.
"""

import argparse
import datetime as dt
import html
import json
import os
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from election.feeds import geotag as G  # noqa: E402
from election.feeds.outlets import registered_domain  # noqa: E402

MAX_AGE = dt.timedelta(days=3)
WORKERS = 4
ITEM = re.compile(r"<(item|entry)\b[^>]*>(.*?)</\1\s*>", re.S | re.I)
TITLE = re.compile(r"<title\b[^>]*>(.*?)</title\s*>", re.S | re.I)
LINK_TEXT = re.compile(r"<link\b[^>]*>(.*?)</link\s*>", re.S | re.I)
LINK_HREF = re.compile(r"<link\b([^>]*?)/?>", re.S | re.I)
GUID = re.compile(r"<guid\b([^>]*)>(.*?)</guid\s*>", re.S | re.I)
TIMES = re.compile(r"<(pubDate|published|updated|dc:date|a10:updated)\b[^>]*>(.*?)</\1\s*>", re.S | re.I)
CDATA = re.compile(r"<!\[CDATA\[(.*?)\]\]>", re.S)
ATTR = re.compile(r"""(\w[\w:-]*)\s*=\s*(?:"([^"]*)"|'([^']*)')""")
TAGS = re.compile(r"<[^>]+>")


def _text(s):
    s = CDATA.sub(lambda m: m.group(1), s or "")
    s = TAGS.sub(" ", s)
    return " ".join(html.unescape(html.unescape(s)).split())


def _attrs(s):
    return {m.group(1).lower(): (m.group(2) if m.group(2) is not None else m.group(3)) for m in ATTR.finditer(s or "")}


def decode(body, charset=None):
    """The feed's text in the encoding it declares (its XML declaration, else the server's charset), else UTF-8, else
    Windows-1252, the usual fallback of feeds that say nothing."""
    m = re.match(rb"\s*<\?xml[^>]*encoding=[\"']([\w.:-]+)[\"']", body[:200])
    for enc in ([m.group(1).decode("ascii")] if m else []) + ([charset] if charset else []) + ["utf-8"]:
        try:
            return body.decode(enc)
        except (LookupError, UnicodeDecodeError):
            continue
    return body.decode("cp1252", "replace")


def items_of(body):
    """[(title, link, time string)] from an RSS or Atom document: only those three fields are read. Descriptions,
    summaries and content are cut out before anything else is looked at."""
    text = decode(body) if isinstance(body, bytes) else body
    out = []
    for _tag, inner in ITEM.findall(text):
        inner = re.sub(r"<(description|summary|content|content:encoded|media:[\w]+)\b.*?</\1\s*>|"
                       r"<(media:[\w]+)\b[^>]*/>", " ", inner, flags=re.S | re.I)
        t = TITLE.search(inner)
        title = _text(t.group(1)) if t else ""
        link = ""
        for m in LINK_HREF.finditer(inner):
            a = _attrs(m.group(1))
            if a.get("href") and a.get("rel", "alternate") == "alternate":
                link = a["href"]
                break
        if not link:
            m = LINK_TEXT.search(inner)
            if m and _text(m.group(1)).lower().startswith("http"):
                link = _text(m.group(1))
        if not link:
            g = GUID.search(inner)
            if g and _attrs(g.group(1)).get("ispermalink", "true").lower() != "false" and \
                    _text(g.group(2)).lower().startswith("http"):
                link = _text(g.group(2))
        tm = TIMES.search(inner)
        out.append((title, html.unescape(link.strip()), _text(tm.group(2)) if tm else ""))
    return out


def _validators(con, feed):
    v = G.state_get(con, "rss:" + feed)
    try:
        d = json.loads(v) if v else {}
    except ValueError:
        d = {}
    return d.get("etag"), d.get("lm")


def poll(src=None, now=None, rehearsal=False, say=print, db=None, limit=None, state=None):
    """One round of the news feeds. Returns counts for the log."""
    from election.source import Refused, SourceError
    if src is None:
        from election.feeds import accounts
        from election.source import Source
        src = Source(stopped_file=os.path.join(G.CACHE, "stopped_hosts.json"), log=accounts._log)
    now = now or G.utcnow()
    con = G.open_db(db)
    feeds = [dict(zip(("outlet_id", "name", "key", "state", "feed", "aggregator"), r)) for r in con.execute(
        "SELECT outlet_id, name, outlet_key, home_state, feed, aggregator FROM outlets WHERE active=1 "
        + ("AND home_state=? " if state else "") + "ORDER BY home_state, outlet_id", ((state,) if state else ()))]
    if limit:
        feeds = feeds[:limit]
    # Validators remembered across restarts: handed to the gate so its conditional requests carry them.
    vals = getattr(src, "_validators", None)
    if isinstance(vals, dict):
        for f in feeds:
            if f["feed"] not in vals:
                etag, lm = _validators(con, f["feed"])
                if etag or lm:
                    vals[f["feed"]] = (etag, lm)
    con.close()
    P = G.placer()
    tally = {"feeds": len(feeds), "answered": 0, "unchanged": 0, "failed": 0, "refused": 0, "items": 0, "kept": 0,
             "on_races": 0}
    lock = threading.Lock()

    def one(f):
        try:
            r = src.get(f["feed"], accept="application/rss+xml, application/atom+xml, application/xml;q=0.9, */*;q=0.5",
                        conditional=True, timeout=40)
        except Refused:
            return "refused", None, f
        except SourceError:
            return "failed", None, f
        if r.not_modified:
            return "unchanged", None, f
        if r.refused:
            return "refused", None, f
        if not r.ok:
            return "failed", None, f
        return "answered", r, f

    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        results = list(ex.map(one, feeds))
    con = G.open_db(db)
    try:
        for what, r, f in results:
            tally[what] += 1
            if r is None:
                continue
            etag, lm = r.headers.get("etag"), r.headers.get("last-modified")
            if etag or lm:
                G.state_set(con, "rss:" + f["feed"], json.dumps({"etag": etag, "lm": lm}))
            for title, link, when in items_of(r.body):
                tally["items"] += 1
                if not title or not link.lower().startswith(("http://", "https://")):
                    continue
                pub = G.parse_time(when)
                if pub and now - pub > MAX_AGE:
                    continue
                places = P.place(title, f["state"])
                election = G.is_election(title)
                if not (election or any(p["rule"] in (G.R1, G.R1B) for p in places)):
                    continue
                address = G.canonical(link)
                if not address:
                    continue
                if f["aggregator"]:
                    host = (urlsplit(link).hostname or "").lower()
                    key, name, via = registered_domain(host), registered_domain(host), f["name"]
                else:
                    key, name, via = f["key"], f["name"], None
                with lock:
                    new = G.store_item(con, source="rss", kind="news", address=address, link=link, headline=title,
                                       published=pub, fetched=now, outlet_id=None if via else f["outlet_id"],
                                       outlet_key=key, outlet_name=name, via=via, home_state=f["state"],
                                       election=election, places=places)
                if new:
                    tally["kept"] += 1
                    tally["on_races"] += 1 if any(p["place_kind"] == "race" for p in places) else 0
        G.refresh_shown(con)
    finally:
        con.close()
    return tally


def main(argv):
    ap = argparse.ArgumentParser(prog="rss")
    ap.add_argument("cmd", choices=["poll"])
    ap.add_argument("--db")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--state")
    a = ap.parse_args(argv)
    print(json.dumps(poll(db=a.db, limit=a.limit, state=(a.state or "").upper() or None)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
