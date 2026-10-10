"""election/feeds/outlets.py - the news outlets whose headlines the feed shows, from the feeds scout's tested list.

    python -m election.feeds.outlets load     write the outlets (and the feeds that refused) into night_feed_2026.sqlite
    python -m election.feeds.outlets check    the checks: 145 feeds loaded, every state and DC covered, no duplicate
                                              address, every row with a credit line; exit 1 on failure
    python -m election.feeds.outlets list     one line a feed

The source is election/scout/feeds.json (every feed tested 2026-10-09 with the kit's honest User-Agent: 145 answered).
This module makes no request of any kind: the collectors (phase 4) ask the feeds, conditionally, on their own clocks.

What the feed may show of an outlet's item (ARCHITECTURE.md 4.5): its headline, the outlet's name, the time and a link.
Never the summary or the article, even where a feed carries the whole text (`full_text` marks those, so the collector
knows to drop it on reading).

One row per feed. Two feeds of the same outlet (Maryland Matters' news and politics feeds, NPR's two) share an
`outlet_key`, the outlet's registered domain, which is what "distinct outlets" and "at most 3 items per outlet" count.
"""

import datetime as dt
import json
import os
import re
import sys
from urllib.parse import urlsplit

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from election.feeds import connect  # noqa: E402

SCOUT = os.path.join(HERE, "election", "scout", "feeds.json")
EXPECTED = 145

STATES = ("AK AL AR AZ CA CO CT DC DE FL GA HI IA ID IL IN KS KY LA MA MD ME MI MN MO MS MT NC ND NE NH NJ NM NV NY OH "
          "OK OR PA RI SC SD TN TX UT VA VT WA WI WV WY").split()

# Second-level suffixes, so that feeds.bbci.co.uk is "bbci.co.uk", not "co.uk".
SECOND_LEVEL = {"co.uk", "org.uk", "ac.uk", "gov.uk", "com.au", "co.nz"}

# Where one domain carries several outlets: the outlet is the domain and the path that names it.
OUTLET_KEY = {
    "WCCO (CBS Minnesota)": "cbsnews.com/minnesota",
}

# The outlet's own home page, where the feed's host is not it (a feeds. or rss. host, or a section). Used only by
# accounts.py, to read which social accounts the outlet itself links. None: not asked (the scouts found the site
# refusing scripts), with the reason.
HOME = {
    "NPR Politics": "https://www.npr.org/", "NPR News": "https://www.npr.org/",
    "PBS News Hour Politics": "https://www.pbs.org/newshour/",
    "CBS News Politics": "https://www.cbsnews.com/",
    "WCCO (CBS Minnesota)": "https://www.cbsnews.com/minnesota/",
    "ABC News Politics": "https://abcnews.go.com/", "NBC News Politics": "https://www.nbcnews.com/",
    "CNN Politics": "https://www.cnn.com/", "Fox News Politics": "https://www.foxnews.com/",
    "New York Times Politics": "https://www.nytimes.com/", "Washington Post Politics": "https://www.washingtonpost.com/",
    "Politico": "https://www.politico.com/", "Axios": "https://www.axios.com/",
    "Bloomberg Politics": "https://www.bloomberg.com/", "UPI Top News": "https://www.upi.com/",
    "BBC US and Canada": "https://www.bbc.com/news", "WBUR": "https://www.wbur.org/", "KQED": "https://www.kqed.org/",
    "Texas Tribune": None,
}
HOME_WHY = {"Texas Tribune": "the scouts found www.texastribune.org refusing scripts (only its feeds host answers)"}

# The scouts' file calls four commercial stations "public media". Corrected here, from the stations' own sites.
KIND_FIX = {
    "KSTP": "local TV or radio (commercial)",
    "KTTC": "local TV or radio (commercial)",
    "WCAX": "local TV or radio (commercial)",
    "WDEL": "local TV or radio (commercial)",
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS outlets (
  outlet_id TEXT PRIMARY KEY,      -- one per feed: <state>-<slug>, -2 for an outlet's second feed
  name TEXT NOT NULL,              -- the outlet's name, shown on its own headlines
  outlet_key TEXT NOT NULL,        -- registered domain (or domain/path): what counts as one outlet
  domain TEXT NOT NULL,            -- the feed's host
  kind TEXT,                       -- public media, newspaper, network, state capitol newsroom ...
  aggregator INTEGER NOT NULL DEFAULT 0,   -- links to others' stories: an item counts as the outlet it links to
  home_state TEXT NOT NULL,        -- two letters, or US for a national outlet
  market TEXT,                     -- statewide, national, or the city or region it serves
  feed TEXT NOT NULL UNIQUE,       -- the feed's address
  scope TEXT,                      -- all news, politics section, news section
  full_text INTEGER NOT NULL DEFAULT 0,    -- the feed carries the whole article (never shown, never kept)
  credit TEXT NOT NULL,            -- the credit line on its headlines
  home TEXT,                       -- the outlet's own home page (for accounts.py); null when not asked
  home_note TEXT,
  use TEXT,                        -- what may be shown
  checked TEXT,                    -- when the scouts tested the feed
  tested_status INTEGER,
  tested_items INTEGER,
  active INTEGER NOT NULL DEFAULT 1,
  loaded TEXT
);
CREATE TABLE IF NOT EXISTS outlets_refused (
  state TEXT, outlet TEXT, address TEXT PRIMARY KEY, why TEXT, checked TEXT
);
"""


def registered_domain(host):
    host = (host or "").lower().rstrip(".")
    parts = host.split(".")
    if len(parts) >= 3 and ".".join(parts[-2:]) in SECOND_LEVEL:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")


def rows_from_scout(path=SCOUT):
    with open(path, encoding="utf-8") as fh:
        doc = json.load(fh)
    out, seen = [], {}
    for f in doc["feeds"]:
        host = (urlsplit(f["feed"]).hostname or "").lower()
        base = f"{f['state'].lower()}-{slug(f['outlet'])}"
        seen[base] = seen.get(base, 0) + 1
        oid = base if seen[base] == 1 else f"{base}-{seen[base]}"
        name = f["outlet"]
        kind = KIND_FIX.get(name, f.get("kind"))
        if name in HOME:
            home = HOME[name]
        else:
            home = f"https://{host}/"
        out.append({
            "outlet_id": oid, "name": name,
            "outlet_key": OUTLET_KEY.get(name, registered_domain(host)),
            "domain": host, "kind": kind,
            "aggregator": 1 if (kind or "").startswith("aggregator") else 0,
            "home_state": f["state"], "market": f.get("market"), "feed": f["feed"], "scope": f.get("scope"),
            "full_text": 1 if f.get("feed_carries_full_text") else 0,
            "credit": name, "home": home, "home_note": HOME_WHY.get(name),
            "use": f.get("use"), "checked": f.get("checked"), "tested_status": f.get("status"),
            "tested_items": f.get("items_when_tested"),
        })
    refused = [{k: r.get(k) for k in ("state", "outlet", "address", "why", "checked")} for r in doc.get("not_working", [])]
    return out, refused


def load(con=None, say=print):
    own = con is None
    con = con or connect()
    con.executescript(SCHEMA)
    rows, refused = rows_from_scout()
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    cols = list(rows[0].keys()) + ["loaded"]
    with con:
        con.execute("DELETE FROM outlets")
        con.execute("DELETE FROM outlets_refused")
        con.executemany(f"INSERT INTO outlets ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                        [[r[c] for c in cols[:-1]] + [now] for r in rows])
        con.executemany("INSERT OR REPLACE INTO outlets_refused VALUES (?,?,?,?,?)",
                        [[r["state"], r["outlet"], r["address"], r["why"], r["checked"]] for r in refused])
    say(f"outlets: {len(rows)} feeds from {len({r['outlet_key'] for r in rows})} outlets loaded; "
        f"{len(refused)} refused feeds listed")
    if own:
        con.close()
    return len(rows)


def all_outlets(con=None):
    own = con is None
    con = con or connect()
    con.row_factory = None
    cur = con.execute("SELECT * FROM outlets WHERE active=1 ORDER BY home_state, name, outlet_id")
    names = [d[0] for d in cur.description]
    out = [dict(zip(names, r)) for r in cur.fetchall()]
    if own:
        con.close()
    return out


def run_checks(con=None, say=print):
    """True when every check passes."""
    own = con is None
    con = con or connect()
    ok = True

    def check(cond, line):
        nonlocal ok
        say(("PASS " if cond else "FAIL ") + line)
        ok = ok and bool(cond)

    n = con.execute("SELECT COUNT(*) FROM outlets WHERE active=1").fetchone()[0]
    check(n == EXPECTED, f"{n} feeds loaded (expected {EXPECTED})")
    states = {r[0] for r in con.execute("SELECT DISTINCT home_state FROM outlets")}
    missing = [s for s in STATES if s not in states]
    check(not missing, f"every state and DC has a feed{': missing ' + ', '.join(missing) if missing else ''}")
    check("US" in states, "national feeds present ({} of them)".format(
        con.execute("SELECT COUNT(*) FROM outlets WHERE home_state='US'").fetchone()[0]))
    dup = con.execute("SELECT feed, COUNT(*) FROM outlets GROUP BY feed HAVING COUNT(*)>1").fetchall()
    check(not dup, "no feed address loaded twice")
    bad = con.execute("SELECT COUNT(*) FROM outlets WHERE credit IS NULL OR credit='' OR outlet_key=''").fetchone()[0]
    check(bad == 0, "every feed has a credit line and an outlet key")
    nonhttps = con.execute("SELECT COUNT(*) FROM outlets WHERE feed NOT LIKE 'http%'").fetchone()[0]
    check(nonhttps == 0, "every feed is a web address")
    keys = con.execute("SELECT COUNT(DISTINCT outlet_key) FROM outlets").fetchone()[0]
    say(f"     {keys} distinct outlets; {con.execute('SELECT COUNT(*) FROM outlets WHERE full_text=1').fetchone()[0]} "
        f"feeds carry the whole article (headline, outlet, time and link only are kept)")
    if own:
        con.close()
    return ok


def main(argv):
    cmd = argv[0] if argv else "check"
    if cmd == "load":
        load()
        return 0
    if cmd == "check":
        return 0 if run_checks() else 1
    if cmd == "list":
        for r in all_outlets():
            print(f"{r['home_state']}  {r['outlet_id']:<40} {r['outlet_key']:<28} {r['market']}")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
