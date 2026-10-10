"""election/feeds/measures.py - the feed's leaderboard: four measures for every race, each with its arithmetic.

    python -m election.feeds.measures selftest            the measures against worked examples (no database needed)
    python -m election.feeds.measures residents [--rebuild] every race's residents (ACS 2020-2024 table B01003), cached
    python -m election.feeds.measures update [--db F] [--now UTC] [--rehearsal]   one computation, rows written
    python -m election.feeds.measures page [--code MN] [--db F] [--now UTC]       print a feed file's size and counts

The plan is election/ARCHITECTURE.md 4.3 (John's measures) and election/scout/feeds.md. All four are Analysis:
"Counted from public headlines and posts. Not a measure of importance or of support."

THE COUNTING RULES (against one viral item or one big outlet)
  - A news item counts for a race only when it was placed on that race with high or medium confidence (election/feeds/
    geotag.py). Items placed only by where the outlet is (low) never count for a race.
  - One story is one canonical address (no query string, no fragment, no AMP form): the same story from GDELT and from
    the outlet's own feed counts once.
  - The same wire story counts once per outlet: one outlet's items with the same headline are one.
  - At most 3 items per outlet per race per window.
  - An aggregator counts as the outlet it links to (the registered domain of the story's own address).
  - Social mentions are distinct people, once per race per hour (the collectors' counts table); reposts are not read.
  - The window: a rolling 60 minutes on election night, a rolling 24 hours before it (NIGHT_FROM).

THE MEASURES (each race against the races of its own board, never all races together)
  1. Coverage per 100,000 residents (John's leveller).
       raw   = 100,000 x N / residents
       shown = 100,000 x (N + R) / (residents + 100,000)
     N: the race's news items in the window, counted by the rules above. R: the board's own rate, all its items per
     100,000 of all its residents. The extra 100,000 residents carrying the board's own rate keep a small school board
     with two stories from topping the board; the raw figure is printed beside it. Ranked only with 3 or more items from
     2 or more outlets.
  2. Attention gap (coverage against closeness).
       gap = percentile of closeness - percentile of coverage shown, within the board, from -100 to +100
       closeness = 1 - |margin|, margin = (first - second) / (first + second)
     The margin is the count's once 20 percent of the expected vote is in (the forecast's expected total, else the
     share of units reported), before that the forecast's median margin (none when the two medians at the line are the
     same); with neither, not ranked. Where several seats
     are filled, the margin is between the last seat and the first name below it. Retention votes, races with one name a
     seat, and races where the forecast says the record favours nobody are left out. Close races with no coverage are
     included: that is the point. Positive: closer than its coverage suggests.
  3. Momentum (the last hour against the hour before).
       momentum = (c_last + 1) / (c_prev + 1), c = news items (by the rules) + distinct people posting
     Ranked only with 10 or more in the two hours. "Rising" only when c_last is above the 95 percent Poisson upper bound
     of c_prev: the rate u for which a count of c_prev or fewer has only a 5 percent chance (Garwood's bound).
  4. Source breadth (distinct outlets, 24 hours).
       outlets = distinct registered domains; effective = exp(-sum p ln p), p each outlet's share of the race's items
     (one story one address, wire stories once per outlet; not capped, since the cap would hide how lopsided it is).
     Ranked with 3 or more items. 10 stories with 8 from one paper: 3 outlets, about 1.9 effective.

RESIDENTS: ACS 2020-2024 five-year table B01003 (states_cache/acs2024/, already on disk), at the race's own level: the
state; the congressional district (119th Congress; a state with new 2026 lines takes its residents divided by its seats,
since districts are drawn equal and the new lines have no Census figures yet); the legislative district; the county or
counties; the county subdivision (Minnesota's cities and townships); the school district (block groups carried to the
district through 2020 blocks, from the forecast model's features). A district with no figure of its own (a county
commissioner's district, a hospital district) takes the counties it lies in, marked "approx", which makes its rate read
low; the page says so.

WHAT THIS MODULE READS AND WRITES
  Reads: night_feed_2026.sqlite's race_keywords (the races), outlets, accounts, and the collectors' tables items,
  item_places, counts and deletions (column names read by alias, since they are written by another module: COLUMNS);
  ballot_2026.sqlite and ballot_local_2026.sqlite (read only); election_2026.sqlite through election.store (the count);
  election_model_2026.sqlite through election.model.runs (the forecast) and its features (school districts).
  Writes: the measures table (a row for a race only when its figures changed) and the residents cache,
  election_cache/feeds/residents.json. Nothing about an ordinary account is ever read here: the collectors keep only
  counts of them.

For the updater (election/live.py): update(src=, now=, rehearsal=, say=) every 5 minutes; page_json(code or "US") for
feed/<code>.json in each snapshot (budget 200 KB); newest() for now.json's "fd".
"""

import argparse
import datetime as dt
import gzip
import hashlib
import json
import math
import os
import re
import sqlite3
import sys
import threading
from urllib.parse import urlsplit, urlunsplit

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from election.feeds import CACHE, DB  # noqa: E402

UTC = dt.timezone.utc
METHOD = "1.0"                  # bump whenever a formula below changes
BALLOT = os.path.join(HERE, "ballot_2026.sqlite")
LOCAL = os.path.join(HERE, "ballot_local_2026.sqlite")
MODEL = os.path.join(HERE, "election_model_2026.sqlite")
ACS_DIR = os.path.join(HERE, "states_cache", "acs2024")
RESIDENTS_CACHE = os.path.join(CACHE, "residents.json")
ACS_CACHE = os.path.join(CACHE, "acs_b01003.json.gz")

# Election night starts with the first poll closings (6 p.m. Eastern, eastern Indiana and Kentucky) and the window is a
# rolling hour from then on; before it, a rolling day.
NIGHT_FROM = dt.datetime(2026, 11, 3, 23, 0, tzinfo=UTC)
WINDOW_NIGHT = 60               # minutes
WINDOW_BEFORE = 24 * 60
BREADTH_WINDOW = 24 * 60
PER_100K = 100_000
SHRINK = 100_000                # residents' worth of the board's own rate added to every race
CAP = 3                         # items per outlet per race per window
COVER_MIN_ITEMS, COVER_MIN_OUTLETS = 3, 2
MOMENTUM_MIN = 10
BREADTH_MIN = 3
LIVE_MARGIN_FROM = 0.20         # share of the expected vote counted before the count's margin replaces the forecast's
RISING_P = 0.05
COUNTED_CONF = ("high", "medium")
NEWS_SOURCES = ("gdelt", "rss")
SOCIAL_SOURCES = ("bluesky", "mastodon", "youtube")

# The boards: one per level, never one for all.
BOARDS = (("statewide", "Statewide offices and the U.S. Senate"), ("house", "U.S. House"), ("legislature", "Legislature"),
          ("county", "County offices and district courts"), ("local", "Cities, towns and schools"))
BOARD_NAMES = dict(BOARDS)
TOP_US, TOP_STATE = 25, 40       # rows per board and measure in the country's file and a state's
ITEMS_US, ITEMS_STATE = 60, 100
POSTS_MAX = 40

# The collectors' tables are another module's (election/feeds/gdelt.py, rss.py, bluesky.py ...). Their columns are read
# by these names, the first one present winning, so that a small difference in naming does not stop the board.
COLUMNS = {
    "items": {"id": ("item_id", "id"), "source": ("source",), "outlet": ("outlet_id", "outlet"),
              "account": ("account_id", "account"), "url": ("url", "canonical", "address", "link", "canonical_url"),
              "headline": ("headline", "title", "text"), "published": ("published_at", "published", "pub_at", "published_utc"),
              "fetched": ("fetched_at", "fetched", "fetched_utc", "seen_at")},
    "item_places": {"id": ("item_id",), "race": ("race_id", "race"), "place": ("place_id", "place"), "state": ("state",),
                    "conf": ("confidence", "conf"), "rule": ("rule", "placed_by", "how")},
    "counts": {"minute": ("minute", "t", "at"), "race": ("race_id", "race"), "kind": ("kind",), "items": ("items", "n"),
               "people": ("people", "distinct_people", "distinct", "persons")},
    "deletions": {"url": ("post_url", "url", "address")},
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS measures (
  t TEXT NOT NULL,                -- when the measures were worked out (UTC)
  rehearsal INTEGER NOT NULL DEFAULT 0,
  board TEXT NOT NULL,            -- statewide, house, legislature, county, local
  race_id TEXT NOT NULL,
  state TEXT NOT NULL,
  window_min INTEGER NOT NULL,    -- 60 on election night, 1440 before
  items INTEGER NOT NULL,         -- news items in the window, by the counting rules
  outlets INTEGER NOT NULL,       -- distinct outlets among them
  social INTEGER NOT NULL,        -- distinct people posting, once per race per hour, summed over the window
  residents INTEGER,
  residents_how TEXT,             -- which Census geography; "approx" when the counties stand in for the district
  coverage_raw REAL, coverage_shown REAL, board_rate REAL,
  margin REAL, margin_source TEXT,                 -- count or forecast
  closeness_pct REAL, coverage_pct REAL, gap REAL,
  last_hour INTEGER, hour_before INTEGER, momentum REAL, bound95 REAL, rising INTEGER,
  items_24h INTEGER, outlets_24h INTEGER, effective_outlets REAL,
  ranked TEXT,                    -- which boards ranked it: c coverage, g gap, m momentum, b breadth
  method TEXT NOT NULL,
  PRIMARY KEY (t, rehearsal, race_id)
);
CREATE INDEX IF NOT EXISTS measures_race ON measures (race_id, rehearsal, t);
"""


# ============================================================================================ small helpers

def utcnow():
    return dt.datetime.now(UTC).replace(microsecond=0)


def iso(t):
    return t.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_time(s):
    """A stored time (ISO 8601, with Z or an offset, or a bare UTC time; or epoch seconds) as an aware UTC datetime."""
    if s is None or s == "":
        return None
    if isinstance(s, (int, float)):
        v = float(s)
        if v > 1e12:            # milliseconds
            v /= 1000.0
        return dt.datetime.fromtimestamp(v, UTC)
    s = str(s).strip()
    if re.fullmatch(r"\d{9,13}(\.\d+)?", s):
        return parse_time(float(s))
    s = s.replace(" ", "T", 1) if re.match(r"\d{4}-\d\d-\d\d \d", s) else s
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    if re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d", s):
        s += ":00"
    try:
        t = dt.datetime.fromisoformat(s)
    except ValueError:
        return None
    return t.replace(tzinfo=UTC) if t.tzinfo is None else t.astimezone(UTC)


def ro(path):
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def tables(con):
    return {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type IN ('table', 'view')")}


def columns_of(con, table):
    """{logical name: the column that holds it} for one of the collectors' tables (COLUMNS), or None if it is absent."""
    if table not in tables(con):
        return None
    have = [r[1] for r in con.execute(f"PRAGMA table_info({table})")]
    low = {c.lower(): c for c in have}
    out = {}
    for name, aliases in COLUMNS[table].items():
        for a in aliases:
            if a in low:
                out[name] = low[a]
                break
    return out


# ---------------------------------------------------------------------------------------- addresses and outlets

SECOND_LEVEL = {"co.uk", "org.uk", "ac.uk", "gov.uk", "com.au", "co.nz"}
AMP_QUERY = re.compile(r"(^|&)(outputType=amp|amp=1|amp)(&|$)", re.I)


def canonical(url):
    """One story, one address: scheme and host in small letters, no www., no query string, no fragment, no AMP form
    (an amp. host, an /amp/ path segment, a trailing /amp or .amp), no trailing slash."""
    if not url:
        return ""
    try:
        p = urlsplit(str(url).strip())
    except ValueError:
        return str(url).strip()
    host = (p.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if host.startswith("amp."):
        host = host[4:]
    path = re.sub(r"/amp(?=/|$)", "", p.path or "")
    path = re.sub(r"\.amp(?:\.html)?$", "", path)
    path = re.sub(r"/+$", "", path) or "/"
    return urlunsplit(("https" if p.scheme in ("http", "https", "") else p.scheme, host, path, "", ""))


def registered_domain(url_or_host):
    """The registered domain of an address or a host: mprnews.org for www.mprnews.org, bbci.co.uk for feeds.bbci.co.uk."""
    s = str(url_or_host or "")
    host = (urlsplit(s).hostname if "//" in s else s.split("/")[0]) or ""
    host = host.lower().strip(".")
    parts = host.split(".")
    if len(parts) >= 3 and ".".join(parts[-2:]) in SECOND_LEVEL:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def headline_key(h):
    return " ".join(re.sub(r"[^a-z0-9]+", " ", str(h or "").lower()).split())


# ---------------------------------------------------------------------------------------- the arithmetic

def coverage(n, residents, rate):
    """(raw, shown) per 100,000 residents. rate: the board's own items per 100,000 of all its residents."""
    if not residents:
        return None, None
    raw = PER_100K * n / residents
    shown = PER_100K * (n + rate) / (residents + SHRINK)
    return raw, shown


def effective_number(counts):
    """exp(-sum p ln p) over each outlet's share of the items; 0 with no items."""
    total = sum(counts)
    if not total:
        return 0.0
    h = -sum((c / total) * math.log(c / total) for c in counts if c)
    return math.exp(h)


def poisson_cdf(k, mu):
    """P(X <= k) for X ~ Poisson(mu), summed in log space."""
    if mu <= 0:
        return 1.0
    term = math.exp(-mu)
    total = term
    for i in range(1, k + 1):
        term *= mu / i
        total += term
    return min(1.0, total)


def upper95(k, p=RISING_P):
    """Garwood's one-sided upper bound: the rate u at which a count of k or fewer has only a 5 percent chance."""
    lo, hi = float(k), float(k) + 10.0 * math.sqrt(k + 1) + 10.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if poisson_cdf(k, mid) > p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def momentum(last, prev):
    """(ratio, bound, rising)."""
    ratio = (last + 1) / (prev + 1)
    bound = upper95(prev)
    return ratio, bound, last > bound


def percentiles(values):
    """Percentile ranks (0 to 100) of each value among them, ties sharing the average place; 50 when there is one."""
    n = len(values)
    if n == 0:
        return []
    if n == 1:
        return [50.0]
    order = sorted(range(n), key=lambda i: values[i])
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg = (i + j) / 2
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return [100.0 * r / (n - 1) for r in ranks]


def margin_of(shares, seats=1):
    """(first - second) / (first + second), the seat line for several seats: shares sorted high to low, the last seat
    against the first name below it. None without two names beyond the seats."""
    s = sorted((x for x in shares if x is not None), reverse=True)
    seats = max(1, int(seats or 1))
    if len(s) <= seats:
        return None
    a, b = s[seats - 1], s[seats]
    if a + b <= 0:
        return None
    return (a - b) / (a + b)


def count_items(rows, cap=CAP):
    """The counting rules over one race's rows [(canonical address, outlet key, headline key, time)], oldest first:
    (counted, by outlet {outlet: counted}). One address once; one outlet's same headline once; at most cap an outlet."""
    seen_url, seen_head, by = set(), set(), {}
    for url, outlet, head, _t in rows:
        if url in seen_url or (head and (outlet, head) in seen_head):
            continue
        seen_url.add(url)
        if head:
            seen_head.add((outlet, head))
        if cap is not None and by.get(outlet, 0) >= cap:
            continue
        by[outlet] = by.get(outlet, 0) + 1
    return sum(by.values()), by


# ============================================================================================ the races and their residents

def _file_stamp(*paths):
    out = []
    for p in paths:
        try:
            st = os.stat(p)
            out.append([os.path.basename(p), st.st_size, int(st.st_mtime)])
        except OSError:
            out.append([os.path.basename(p), None, None])
    return out


def acs_index(say=print):
    """B01003 by geography, from the ACS summary file's geography list and table file (90 MB and 18 MB, read once and
    cached): states, counties, county subdivisions, congressional districts (119th) and both legislative chambers.
    {"fips": {abbr: state fips}, "state": {fips: pop}, "county": {5-digit: pop}, "cousub": {"27|00172": pop},
     "cd": {"27|05": pop}, "sldu": {"27|1": pop}, "sldl": {"27|1A": pop}, "stamp": [...]}"""
    geos = os.path.join(ACS_DIR, "Geos20245YR.txt")
    table = os.path.join(ACS_DIR, "acsdt5y2024-b01003.dat")
    stamp = _file_stamp(geos, table)
    if os.path.exists(ACS_CACHE):
        try:
            with gzip.open(ACS_CACHE, "rt", encoding="utf-8") as fh:
                doc = json.load(fh)
            if doc.get("stamp") == stamp:
                return doc
        except (OSError, ValueError):
            pass
    if not (os.path.exists(geos) and os.path.exists(table)):
        say("  measures: the ACS files are not on disk (states_cache/acs2024/); residents are unknown")
        return {"fips": {}, "state": {}, "county": {}, "cousub": {}, "cd": {}, "sldu": {}, "sldl": {}, "stamp": stamp}
    say("  measures: reading the ACS geography list and table B01003 once (cached afterwards)")
    want = {"040": "state", "050": "county", "060": "cousub", "500": "cd", "610": "sldu", "620": "sldl"}
    geo = {}
    fips = {}
    with open(geos, encoding="utf-8", errors="replace") as fh:
        head = fh.readline().rstrip("\n").split("|")
        ix = {name: i for i, name in enumerate(head)}
        for line in fh:
            f = line.rstrip("\n").split("|")
            if len(f) < len(head) - 3:
                continue
            sl = f[ix["SUMLEVEL"]]
            if sl not in want or f[ix["COMPONENT"]] != "00":
                continue
            st = f[ix["STATE"]]
            kind = want[sl]
            if kind == "state":
                fips[f[ix["STUSAB"]]] = st
                key = st
            elif kind == "county":
                key = st + f[ix["COUNTY"]]
            elif kind == "cousub":
                key = f"{st}|{f[ix['COUSUB']]}"
            elif kind == "cd":
                key = f"{st}|{f[ix['CDCURR']]}"
            else:
                code = f[ix["SLDU" if kind == "sldu" else "SLDL"]]
                if not code or code.upper().startswith("ZZZ"):
                    continue
                key = f"{st}|{district_key(code)}"
            geo[f[ix["GEO_ID"]]] = (kind, key)
    out = {"fips": fips, "state": {}, "county": {}, "cousub": {}, "cd": {}, "sldu": {}, "sldl": {}, "stamp": stamp}
    with open(table, encoding="utf-8", errors="replace") as fh:
        head = fh.readline().rstrip("\n").split("|")
        gi, ei = head.index("GEO_ID"), head.index("B01003_E001")
        for line in fh:
            f = line.rstrip("\n").split("|")
            g = geo.get(f[gi])
            if not g:
                continue
            try:
                v = int(f[ei])
            except ValueError:
                continue
            kind, key = g
            # a county subdivision that crosses counties is one place: its parts are added up
            out[kind][key] = out[kind].get(key, 0) + v if kind == "cousub" else v
    os.makedirs(os.path.dirname(ACS_CACHE), exist_ok=True)
    with gzip.open(ACS_CACHE, "wt", encoding="utf-8") as fh:
        json.dump(out, fh, separators=(",", ":"))
    return out


def district_key(code):
    """A district's code compared by its letters and digits, leading zeros off: '001' -> '1', '01A' -> '1A'."""
    s = re.sub(r"[^0-9A-Za-z]", "", str(code or "")).upper()
    s = re.sub(r"^0+(?=[0-9])", "", s)
    return s


def board_of(level, kind, jurisdiction_id, state):
    if level == "federal":
        return "statewide" if str(kind).endswith("Senate") else "house"
    if level == "statewide":
        return "statewide"
    if level == "court":
        return "statewide" if str(jurisdiction_id or "") == state else "county"
    if level == "legislature":
        return "legislature"
    if level in ("county", "soil_water"):
        return "county"
    return "local"


RETENTION = re.compile(r"\bretention\b|\bretain\b|\bretained\b", re.I)


def ordinal(n):
    n = int(n)
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def race_label(r):
    """A short name for a race as the boards print it: the office, then where."""
    st = r["state"]
    if r["level"] == "federal":
        if r["kind"].endswith("Senate"):
            return "U.S. Senate" + (" (special)" if r.get("special") else "")
        d = str(r.get("district") or "")
        return "U.S. House, at large" if d in ("", "0", "00", "AL") else f"U.S. House, {ordinal(int(d))} District" if d.isdigit() else f"U.S. House, District {d}"
    office = r.get("office") or r["kind"].replace("_", " ").capitalize()
    where = r.get("jurisdiction") or ""
    bits = [office]
    if where and where not in (st, r.get("state_name")) and r["level"] not in ("statewide",) and not (r["level"] == "legislature"):
        bits.append(where)
    if r["level"] == "legislature" and where:
        bits = [where]
    if r.get("district") and r["level"] not in ("legislature",) and not re.search(r"\bdistrict\b", where, re.I):
        bits.append(f"District {r['district']}")
    seat = r.get("seat")
    if seat and not re.fullmatch(r"(?i)at large", str(seat)):
        bits.append(f"seat {seat}")
    if r.get("special"):
        bits.append("special")
    return ", ".join(bits)


def load_races(feed_con, say=print):
    """{race id: race} for every race the feed knows (race_keywords), with its board, label, seats and kind."""
    if "race_keywords" not in tables(feed_con):
        return {}
    races = {}
    for rid, state, level, office, cands, kw in feed_con.execute("SELECT race_id, state, level, office, candidates, keywords FROM race_keywords"):
        try:
            k = json.loads(kw)
        except ValueError:
            k = {}
        named = [c for c in (k.get("candidates") or []) if not c.get("write_in")]
        races[rid] = {"id": rid, "state": state, "level": level, "kind": k.get("kind") or office or "", "office": office or "",
                      "names": len(named) if k.get("candidates") is not None else int(cands or 0)}
    fed_ids = [rid for rid, r in races.items() if r["level"] == "federal"]
    if fed_ids and os.path.exists(BALLOT):
        con = ro(BALLOT)
        try:
            for rid, district, special in con.execute("SELECT race_id, district, special FROM races"):
                if rid in races:
                    races[rid].update(district=district, special=bool(special))
        finally:
            con.close()
    if os.path.exists(LOCAL):
        con = ro(LOCAL)
        try:
            for rid, kind, office, jur, jid, cids, district, seat, special, note in con.execute(
                    "SELECT race_id, office_kind, office, jurisdiction, jurisdiction_id, county_ids, district, seat, special, note FROM sl_races"):
                r = races.get(rid)
                if not r:
                    continue
                try:
                    counties = json.loads(cids) if cids else []
                except ValueError:
                    counties = [cids]
                if not isinstance(counties, list):
                    counties = [counties]
                r.update(kind=kind or r["kind"], office=office or r["office"], jurisdiction=jur or "", jid=jid or "", counties=counties,
                         district=district, seat=seat, special=bool(special),
                         retention=bool(RETENTION.search(f"{office or ''} {kind or ''} {note or ''}")))
        finally:
            con.close()
    for r in races.values():
        r["board"] = board_of(r["level"], r["kind"], r.get("jid"), r["state"])
        r["label"] = race_label(r)
        r.setdefault("retention", False)
    return races


def residents(races=None, rebuild=False, say=print):
    """{race id: [residents, how, approx 0/1]} for every race, cached in election_cache/feeds/residents.json against the
    ACS files' and the databases' stamps."""
    con = ro(DB) if races is None else None
    try:
        if races is None:
            races = load_races(con, say)
    finally:
        if con is not None:
            con.close()
    stamp = _file_stamp(os.path.join(ACS_DIR, "acsdt5y2024-b01003.dat"), BALLOT, LOCAL, MODEL) + [METHOD, len(races)]
    if not rebuild and os.path.exists(RESIDENTS_CACHE):
        try:
            with open(RESIDENTS_CACHE, encoding="utf-8") as fh:
                doc = json.load(fh)
            if doc.get("stamp") == json.loads(json.dumps(stamp)) and all(rid in doc["r"] for rid in races):
                return doc["r"]
        except (OSError, ValueError, KeyError):
            pass
    acs = acs_index(say)
    fips = acs["fips"]
    changed = set()
    if os.path.exists(BALLOT):
        con = ro(BALLOT)
        try:
            changed = {s for (s,) in con.execute("SELECT state FROM state_notes WHERE lines_changed = 1")}
            seats = dict(con.execute("SELECT state, COUNT(*) FROM races WHERE office = 'U.S. House' GROUP BY state").fetchall())
        finally:
            con.close()
    else:
        seats = {}
    schools = {}
    if os.path.exists(MODEL):
        con = ro(MODEL)
        try:
            if "features" in tables(con):
                schools = {(s.upper(), u): int(round(v)) for s, u, v in con.execute(
                    "SELECT state, unit_id, value FROM features WHERE unit_kind = 'school' AND name = 'acs_pop'")}
        finally:
            con.close()
    out = {}

    def counties_sum(r, sf):
        tot, ok = 0, False
        for c in r.get("counties") or []:
            c = str(c)
            key = c if len(c) == 5 else sf + c.zfill(3)
            if key in acs["county"]:
                tot += acs["county"][key]
                ok = True
        return tot if ok else None

    for rid, r in races.items():
        st = r["state"]
        sf = fips.get(st, "")
        whole = acs["state"].get(sf)
        val, how, approx = None, "", 0
        lv, kind = r["level"], r["kind"]
        if lv == "federal" and kind.endswith("Senate"):
            val, how = whole, "the state"
        elif lv == "federal":
            d = str(r.get("district") or "")
            n = seats.get(st) or 1
            if n == 1 or d in ("", "0", "00"):
                val, how = whole, "the state (one seat)"
            elif st in changed:
                val, how, approx = (int(round(whole / n)) if whole else None), f"the state's residents divided by its {n} seats (new 2026 lines; districts are drawn equal)", 1
            else:
                val, how = acs["cd"].get(f"{sf}|{d.zfill(2)}"), "the congressional district (119th Congress)"
        elif lv == "statewide" or (lv == "court" and str(r.get("jid") or "") == st):
            if r.get("district"):
                cs = counties_sum(r, sf)
                cdm = re.search(r"-CD(\d+)$", rid)
                if cdm and st not in changed and acs["cd"].get(f"{sf}|{cdm.group(1).zfill(2)}"):
                    # a board elected by congressional district (Colorado's regents and state board)
                    val, how = acs["cd"][f"{sf}|{cdm.group(1).zfill(2)}"], "the congressional district it is elected by"
                elif cs:
                    val, how, approx = cs, "the counties the district reaches", 1
                else:
                    # how many districts the office has is not on file (not all are on this year's ballot): no figure
                    val, how = None, "no Census figure for this district"
            else:
                val, how = whole, "the state"
        elif lv == "legislature":
            chamber = "sldu" if "senate" in kind else "sldl"
            val = acs[chamber].get(f"{sf}|{district_key(r.get('district'))}")
            how = "the State Senate district" if chamber == "sldu" else "the State House district"
            if val is None:
                val, how, approx = counties_sum(r, sf), "the counties the district reaches", 1
        elif lv in ("city", "township"):
            jid = str(r.get("jid") or "")
            if re.fullmatch(r"\d{5}", jid):
                val, how = acs["cousub"].get(f"{sf}|{jid}"), "the city or township (county subdivision)"
            if val is None:
                val, how, approx = counties_sum(r, sf), "the county or counties it lies in", 1
        elif lv == "school":
            val = schools.get((st, str(r.get("jid") or "")))
            how = "the school district (block groups carried through 2020 blocks)"
            if val is None:
                val, how, approx = counties_sum(r, sf), "the county or counties it lies in", 1
        elif lv == "court":
            val, how = counties_sum(r, sf), "the counties of the judicial district"
        elif lv in ("county", "soil_water"):
            val, how = counties_sum(r, sf), "the county"
            if r.get("district"):
                how, approx = "the whole county (the district's own count is not on file)", 1
        else:
            val, how, approx = counties_sum(r, sf), "the county or counties it lies in", 1
        out[rid] = [int(val) if val else None, how, approx]
    try:
        os.makedirs(os.path.dirname(RESIDENTS_CACHE), exist_ok=True)
        with open(RESIDENTS_CACHE, "w", encoding="utf-8") as fh:
            json.dump({"stamp": stamp, "built": iso(utcnow()), "r": out}, fh, separators=(",", ":"))
    except OSError:
        pass
    return out


# ============================================================================================ reading the collectors' tables

def read_items(con, since, until):
    """The news items placed on a race (high or medium) or in a state, between since and until (UTC), each
    {url, outlet, head, t, race, state, conf, rule, headline, name, source}. The time is the story's own (published)
    when it is no later than when it was fetched, else when it was fetched."""
    ci, cp = columns_of(con, "items"), columns_of(con, "item_places")
    if not ci or not cp or "id" not in ci or "id" not in cp:
        return []
    outlets = {}
    if "outlets" in tables(con):
        for oid, name, key, agg, home in con.execute("SELECT outlet_id, name, outlet_key, aggregator, home_state FROM outlets"):
            outlets[oid] = (name, key, agg, home)
    sel = [f"i.{ci['id']}"] + [f"i.{ci[k]}" if k in ci else "NULL" for k in ("source", "outlet", "url", "headline", "published", "fetched")]
    sel += [f"p.{cp[k]}" if k in cp else "NULL" for k in ("race", "state", "conf", "rule", "place")]
    tcol = ci.get("fetched") or ci.get("published")
    where = ""
    args = []
    kind = con.execute(f"SELECT typeof({tcol}) FROM items WHERE {tcol} IS NOT NULL LIMIT 1").fetchone() if tcol else None
    if kind and kind[0] == "text":
        # a generous cut on the stored text (ISO times sort as text); the exact cut is made below on the parsed time
        where = f"WHERE i.{tcol} >= ?"
        args.append(iso(since - dt.timedelta(days=2))[:10])
    elif kind and kind[0] in ("integer", "real"):
        where = f"WHERE i.{tcol} >= ?"      # seconds (or milliseconds) since 1970
        cut = (since - dt.timedelta(days=2)).timestamp()
        big = con.execute(f"SELECT MAX({tcol}) FROM items").fetchone()[0] or 0
        args.append(cut * 1000 if big > 1e12 else cut)
    q = f"SELECT {', '.join(sel)} FROM items i JOIN item_places p ON p.{cp['id']} = i.{ci['id']} {where}"
    out = []
    for iid, source, outlet, url, head, pub, fetched, race, state, conf, rule, place in con.execute(q, args):
        src = str(source or "").lower()
        if src and src not in NEWS_SOURCES:
            continue
        tf, tp = parse_time(fetched), parse_time(pub)
        t = tp if (tp and (not tf or tp <= tf + dt.timedelta(minutes=5))) else tf
        if not t or t < since or t > until:
            continue
        o = outlets.get(outlet)
        curl = canonical(url)
        if o and not o[2]:
            key, name = o[1], o[0]
        else:
            key = registered_domain(curl)
            name = o[0] if (o and registered_domain(o[1]) == key) else None
        out.append({"id": iid, "url": curl, "link": str(url or ""), "outlet": key, "name": name, "head": headline_key(head),
                    "headline": str(head or "").strip(), "t": t, "race": race or None, "state": (state or "").upper() or None,
                    "conf": str(conf or "").lower(), "rule": str(rule or ""), "place": place, "source": src})
    out.sort(key=lambda x: x["t"])
    return out


def read_social(con, since, until):
    """{race id: [(minute, people)]} from the collectors' counts table (kind social): distinct people, once per race per
    hour, summed over the minutes they were first counted in."""
    cc = columns_of(con, "counts")
    if not cc or "minute" not in cc or "race" not in cc:
        return {}
    people = cc.get("people") or cc.get("items")
    kind = f"AND {cc['kind']} = 'social'" if "kind" in cc else ""
    out = {}
    for minute, race, n in con.execute(f"SELECT {cc['minute']}, {cc['race']}, {people} FROM counts WHERE 1 = 1 {kind}"):
        t = parse_time(minute)
        if not t or t < since or t > until or not race:
            continue
        out.setdefault(race, []).append((t, int(n or 0)))
    return out


def read_posts(con, until):
    """Official accounts' posts the feed may show: only once the site has its public contact address (accounts.
    posts_may_be_shown), only from accounts marked shown and active, never a deleted one. [[time, owner, platform, text,
    address, race]]"""
    try:
        from election.feeds import accounts
        if not accounts.posts_may_be_shown():
            return None
    except Exception:  # noqa: BLE001 - without the gate, nothing is shown
        return None
    ci, cp = columns_of(con, "items"), columns_of(con, "item_places")
    if not ci or "account" not in ci or "accounts" not in tables(con):
        return []
    acc = {a: (owner, plat) for a, owner, plat in con.execute("SELECT account_id, owner, platform FROM accounts WHERE shown = 1 AND active = 1")}
    gone = set()
    cd = columns_of(con, "deletions")
    if cd and "url" in cd:
        gone = {canonical(u) for (u,) in con.execute(f"SELECT {cd['url']} FROM deletions")}
    race_of = {}
    if cp and "race" in cp:
        for iid, race in con.execute(f"SELECT {cp['id']}, {cp['race']} FROM item_places WHERE {cp['race']} IS NOT NULL"):
            race_of.setdefault(iid, race)
    rows = []
    tcol = ci.get("published") or ci.get("fetched")
    for iid, src, account, url, text, t in con.execute(
            f"SELECT {ci['id']}, {ci.get('source', 'NULL')}, {ci['account']}, {ci.get('url', 'NULL')}, {ci.get('headline', 'NULL')}, {tcol} "
            f"FROM items WHERE {ci['account']} IS NOT NULL"):
        if account not in acc or canonical(url) in gone:
            continue
        tt = parse_time(t)
        if not tt or tt > until:
            continue
        rows.append([iso(tt), acc[account][0], acc[account][1], str(text or "")[:500], str(url or ""), race_of.get(iid) or ""])
    rows.sort(key=lambda x: x[0], reverse=True)
    return rows[:POSTS_MAX]


# ============================================================================================ margins: the count, else the forecast

def margins(codes, rehearsal=False, results_db=None, model_db=None, say=print):
    """{race id: (margin, source, share counted)} for the races of these states: the count's once 20 percent of the
    expected vote is in, else the forecast's median; equal-chance races (the record favours nobody) left out."""
    out = {}
    fc = {}
    try:
        from election.model import runs
        for code in codes:
            doc = runs.page_json(code, db=model_db or runs.DB, rehearsal=rehearsal) if hasattr(runs, "page_json") else None
            if not doc:
                continue
            pre = doc.get("pre") or ""
            for key, r in (doc.get("r") or {}).items():
                fc[pre + key] = r
    except Exception as e:  # noqa: BLE001 - no forecast: margins from the count alone
        say(f"  measures: the forecasts could not be read ({e.__class__.__name__}); margins from the count alone")
    counts = {}
    try:
        from election import store
        path = results_db or store.DB
        if os.path.exists(path):
            con = ro(path)
            try:
                if "contests" in tables(con):
                    for code in codes:
                        doc = store.page_json(con, code, compact=False)
                        for rid, e in (doc.get("r") or {}).items():
                            counts[rid] = e
            finally:
                con.close()
    except Exception as e:  # noqa: BLE001
        say(f"  measures: the count could not be read ({e.__class__.__name__}); margins from the forecasts alone")
    for rid in set(fc) | set(counts):
        f, e = fc.get(rid), counts.get(rid)
        seats = (f or {}).get("s") or 1
        if e and e.get("v"):
            votes = [v for v, ch in zip(e["v"], e.get("ch") or []) if not (len(ch) > 3 and ch[3])]
            total = sum(e["v"])
            share = None
            if f and f.get("v") and f["v"][1]:
                share = total / f["v"][1]
            elif f and f.get("sc") is not None:
                share = f["sc"]
            elif e.get("p") and e["p"][1]:
                share = e["p"][0] / e["p"][1]
            if share is not None and share >= LIVE_MARGIN_FROM:
                m = margin_of(votes, seats)
                if m is not None:
                    out[rid] = (m, "count", round(min(share, 1.0), 3))
                    continue
        if f and f.get("c") and not f.get("eq") and f.get("st") not in ("unopposed",):
            meds = [c[2] for c in f["c"] if len(c) > 2 and isinstance(c[2], (int, float))]
            m = margin_of(meds, seats)
            # the same median for the two at the line: the forecast tells them apart no better than the record, so no margin
            if m is not None and m != 0:
                out[rid] = (m, "forecast", f.get("sc"))
    return out


# ============================================================================================ the computation

_LOCK = threading.Lock()
_LAST = {}          # rehearsal flag -> the newest computation


def window_minutes(now, rehearsal=False):
    return WINDOW_NIGHT if (rehearsal or now >= NIGHT_FROM) else WINDOW_BEFORE


def compute(now=None, db=None, rehearsal=False, results_db=None, model_db=None, say=print):
    """Every race's measures at this moment, and the boards. Reads only; writes nothing."""
    now = (now or utcnow()).astimezone(UTC)
    wmin = window_minutes(now, rehearsal)
    con = ro(db or DB)
    try:
        races = load_races(con, say)
        res = residents(races, say=say)
        since = now - dt.timedelta(minutes=max(wmin, BREADTH_WINDOW, 120))
        items = read_items(con, since, now)
        social = read_social(con, now - dt.timedelta(minutes=max(wmin, 120)), now)
        posts = read_posts(con, now)
    finally:
        con.close()
    w_from = now - dt.timedelta(minutes=wmin)
    h1, h0 = now - dt.timedelta(minutes=60), now - dt.timedelta(minutes=120)
    b_from = now - dt.timedelta(minutes=BREADTH_WINDOW)
    by_race = {}
    for it in items:
        if it["race"] and it["conf"] in COUNTED_CONF and it["race"] in races:
            by_race.setdefault(it["race"], []).append(it)
    codes = sorted({r["state"] for r in races.values()})
    marg = margins(codes, rehearsal, results_db, model_db, say)
    M = {}
    for rid, r in races.items():
        rows = by_race.get(rid, [])
        win = [(x["url"], x["outlet"], x["head"], x["t"]) for x in rows if x["t"] >= w_from]
        n, by = count_items(win)
        last, _ = count_items([(x["url"], x["outlet"], x["head"], x["t"]) for x in rows if x["t"] >= h1])
        prev, _ = count_items([(x["url"], x["outlet"], x["head"], x["t"]) for x in rows if h0 <= x["t"] < h1])
        b24, by24 = count_items([(x["url"], x["outlet"], x["head"], x["t"]) for x in rows if x["t"] >= b_from], cap=None)
        soc = social.get(rid, [])
        sp = sum(p for t, p in soc if t >= w_from)
        sp1 = sum(p for t, p in soc if t >= h1)
        sp0 = sum(p for t, p in soc if h0 <= t < h1)
        pop, how, approx = (res.get(rid) or [None, "", 0])
        m = {"board": r["board"], "state": r["state"], "n": n, "o": len(by), "sp": sp, "pop": pop, "how": how, "ax": approx,
             "c1": last + sp1, "c0": prev + sp0, "i24": b24, "o24": len(by24), "eff": effective_number(list(by24.values())),
             "os": sorted(by24.values(), reverse=True)}
        mg = marg.get(rid)
        excluded = r.get("retention") or (r.get("names", 0) <= 1)
        if mg and not excluded:
            m["mg"], m["ms"], m["sc"] = mg
        M[rid] = m
    # each board's own rate, then the measures that compare races within a board
    rates = {}
    for b, _name in BOARDS:
        n = sum(m["n"] for m in M.values() if m["board"] == b and m["pop"])
        p = sum(m["pop"] for m in M.values() if m["board"] == b and m["pop"])
        rates[b] = PER_100K * n / p if p else 0.0
    for m in M.values():
        m["cr"], m["cs"] = coverage(m["n"], m["pop"], rates[m["board"]])
        m["mo"], m["ub"], m["ri"] = momentum(m["c1"], m["c0"])
        rk = ""
        if m["cs"] is not None and m["n"] >= COVER_MIN_ITEMS and m["o"] >= COVER_MIN_OUTLETS:
            rk += "c"
        if m["c1"] + m["c0"] >= MOMENTUM_MIN:
            rk += "m"
        if m["i24"] >= BREADTH_MIN:
            rk += "b"
        m["rk"] = rk
    for b, _name in BOARDS:
        el = [rid for rid, m in M.items() if m["board"] == b and "mg" in m and m["cs"] is not None]
        pc = percentiles([1 - abs(M[rid]["mg"]) for rid in el])
        pv = percentiles([M[rid]["cs"] for rid in el])
        for rid, a, c in zip(el, pc, pv):
            M[rid]["pc"], M[rid]["pv"], M[rid]["gap"] = a, c, a - c
            M[rid]["rk"] += "g"
    # the states, for the map: items placed in each state (high or medium), per 100,000 of its residents
    acs = acs_index(say)
    S = {}
    for it in items:
        if it["t"] < w_from or it["conf"] not in COUNTED_CONF:
            continue
        st = it["state"] or (races[it["race"]]["state"] if it["race"] in races else None)
        if not st:
            continue
        S.setdefault(st, []).append((it["url"], it["outlet"], it["head"], it["t"]))
    states = {}
    for st in set(S) | set(codes):
        n, by = count_items(sorted(S.get(st, []), key=lambda x: x[3]), cap=None)
        pop = acs["state"].get(acs["fips"].get(st, ""), None)
        states[st] = {"n": n, "o": len(by), "pop": pop, "cr": (PER_100K * n / pop) if pop else None}
    doc = {"t": now, "w": wmin, "rehearsal": bool(rehearsal), "races": races, "M": M, "rates": rates, "items": items,
           "posts": posts, "states": states, "w_from": w_from}
    with _LOCK:
        _LAST[bool(rehearsal)] = doc
    return doc


def board_lists(M, rids, top):
    """For each board, the races each measure ranks, best first: c coverage shown, g attention gap, m momentum (rising
    first), b source breadth (effective number, then distinct outlets)."""
    out = {}
    for b, _name in BOARDS:
        ids = [rid for rid in rids if M[rid]["board"] == b]
        c = sorted((r for r in ids if "c" in M[r]["rk"]), key=lambda r: (-M[r]["cs"], -M[r]["n"], r))[:top]
        g = sorted((r for r in ids if "g" in M[r]["rk"]), key=lambda r: (-M[r]["gap"], r))[:top]
        m = sorted((r for r in ids if "m" in M[r]["rk"]), key=lambda r: (not M[r]["ri"], -M[r]["mo"], -M[r]["c1"], r))[:top]
        bb = sorted((r for r in ids if "b" in M[r]["rk"]), key=lambda r: (-M[r]["eff"], -M[r]["o24"], r))[:top]
        out[b] = {"c": c, "g": g, "m": m, "b": bb, "n": len(ids)}
    return out


def _r(x, d=2):
    return None if x is None else round(x, d)


def _sig(x, n=4):
    """A figure kept to n significant digits (a statewide race's coverage can be 0.00002 per 100,000)."""
    return None if x is None else float(f"{x:.{n}g}")


def race_entry(m):
    """A race's measures as the feed file carries them (every figure the page needs to show its arithmetic)."""
    e = {"n": m["n"], "o": m["o"], "sp": m["sp"], "pop": m["pop"], "c1": m["c1"], "c0": m["c0"], "i24": m["i24"], "o24": m["o24"],
         "eff": _r(m["eff"]), "cr": _sig(m["cr"]), "cs": _sig(m["cs"]), "mo": _r(m["mo"]), "ub": _r(m["ub"]), "rk": m["rk"]}
    if m["ri"]:
        e["ri"] = 1
    if m["ax"]:
        e["ax"] = 1
    if "mg" in m:
        e["mg"] = round(m["mg"], 4)
        e["ms"] = m["ms"][0]          # c count, f forecast
        if m.get("sc") is not None:
            e["sc"] = m["sc"]
    if "gap" in m:
        e["pc"], e["pv"], e["gap"] = round(m["pc"], 1), round(m["pv"], 1), round(m["gap"], 1)
    if m.get("os") and len(m["os"]) > 1:
        e["os"] = m["os"][:12]          # each outlet's items in 24 hours, most first: the shares behind the effective number
    counts = ("o", "sp", "c1", "c0", "i24", "o24", "eff")      # left off when 0; every other figure kept whatever its value
    return {k: v for k, v in e.items() if v is not None and v != "" and not (k in counts and v == 0)}


def page_json(code="US", db=None, now=None, rehearsal=None, fresh=False):
    """feed/us.json or feed/<code>.json (ARCHITECTURE.md 2.6; budget 200 KB): the newest headlines with their outlet,
    time, link, race and how they were placed; official posts once they may be shown; the boards; every race with a
    figure, with what its arithmetic needs; the boards' own rates; for the country, each state's figures for the map.
    None when the feed has nothing yet (no collectors' tables)."""
    code = (code or "US").upper()
    with _LOCK:
        if rehearsal is None:
            cands = sorted(_LAST.values(), key=lambda d: d["t"])
            doc = cands[-1] if cands else None
        else:
            doc = _LAST.get(bool(rehearsal))
    if fresh or doc is None or (now and doc["t"] != now) or (utcnow() - doc["t"] > dt.timedelta(minutes=6) and now is None):
        con = ro(db or DB)
        try:
            ready = columns_of(con, "items") is not None
        finally:
            con.close()
        if not ready:
            return None
        doc = compute(now=now, db=db, rehearsal=bool(rehearsal))
    races, M = doc["races"], doc["M"]
    us = code == "US"
    rids = [rid for rid in M if us or M[rid]["state"] == code]
    if not us and not rids:
        return None
    boards = board_lists(M, rids, TOP_US if us else TOP_STATE)
    listed = set()
    for b in boards.values():
        for k in ("c", "g", "m", "b"):
            listed.update(b[k])
    # the headlines: newest first, those placed on a race or in the state (a state's file also carries those placed only by
    # where the outlet is, which the page shows at state zoom alone)
    seen, heads = set(), []
    for it in reversed(doc["items"]):
        if us and it["conf"] not in COUNTED_CONF:
            continue
        st = it["state"] or (races[it["race"]]["state"] if it["race"] in races else None)
        if not us and st != code:
            continue
        key = (it["url"], it["race"] or "")
        if key in seen or it["url"] in {h[3] for h in heads[-40:]} and not it["race"]:
            continue
        seen.add(key)
        name = it["name"] or it["outlet"]
        heads.append([iso(it["t"]), name, it["headline"][:300], it["link"] or it["url"], it["race"] or "", st or "",
                      it["conf"][:1], it["rule"][:40]])
        if it["race"]:
            listed.add(it["race"])
        if len(heads) >= (ITEMS_US if us else ITEMS_STATE):
            break
    ng = {}
    for m_ in M.values():
        if "g" in m_["rk"]:
            ng[m_["board"]] = ng.get(m_["board"], 0) + 1      # the races each board's percentiles are taken among (the whole country)
    pre = "2026-" + ("" if us else code + "-")
    keep = [rid for rid in rids if rid in listed or M[rid]["n"] or M[rid]["sp"] or M[rid]["i24"] or (not us and "g" in M[rid]["rk"])]
    short = (lambda rid: rid[len(pre):] if rid.startswith(pre) else rid)
    out = {"v": 1, "code": code, "t": iso(doc["t"]), "w": doc["w"], "m": METHOD, "pre": pre,
           "rates": {b: _sig(v) for b, v in doc["rates"].items()},
           "boards": {b: {k: [short(r) for r in v[k]] for k in ("c", "g", "m", "b")} | {"n": v["n"], "ng": ng.get(b, 0)} for b, v in boards.items()},
           "r": {short(rid): race_entry(M[rid]) for rid in keep},
           "rl": {short(rid): [races[rid]["label"], races[rid]["state"], races[rid]["board"]] for rid in keep},
           "h": [[h[0], h[1], h[2], h[3], short(h[4]) if h[4] else "", h[5], h[6], h[7]] for h in heads]}
    if doc["rehearsal"]:
        out["rehearsal"] = True
    posts = doc["posts"]
    if posts is None:
        out["posts"] = "off"          # posts are not shown yet (the site has no public contact address)
    else:
        out["posts"] = [p for p in posts if us or (p[5] and races.get(p[5], {}).get("state") == code)]
    if us:
        out["st"] = {st: [s["n"], s["o"], s["pop"], _sig(s["cr"])] for st, s in sorted(doc["states"].items()) if s["pop"]}
    else:
        s = doc["states"].get(code)
        if s:
            out["st"] = {code: [s["n"], s["o"], s["pop"], _sig(s["cr"])]}
    return out


def newest():
    """{"t": UTC} of the newest computation, for now.json's "fd"; None before the first."""
    with _LOCK:
        if not _LAST:
            return None
        t = max(d["t"] for d in _LAST.values())
    return {"t": iso(t), "m": METHOD}


# ============================================================================================ the updater's call

ROW_FIELDS = ("board", "state", "window_min", "items", "outlets", "social", "residents", "residents_how", "coverage_raw", "coverage_shown",
              "board_rate", "margin", "margin_source", "closeness_pct", "coverage_pct", "gap", "last_hour", "hour_before", "momentum",
              "bound95", "rising", "items_24h", "outlets_24h", "effective_outlets", "ranked")


def _row(m, wmin, rate):
    return (m["board"], m["state"], wmin, m["n"], m["o"], m["sp"], m["pop"], (m["how"] + (" (approx)" if m["ax"] else "")) if m["how"] else None,
            _r(m["cr"], 4), _r(m["cs"], 4), round(rate, 4), _r(m.get("mg"), 4), m.get("ms"), _r(m.get("pc"), 1), _r(m.get("pv"), 1),
            _r(m.get("gap"), 1), m["c1"], m["c0"], _r(m["mo"], 3), _r(m["ub"], 3), int(bool(m["ri"])), m["i24"], m["o24"], _r(m["eff"], 3), m["rk"])


def update(src=None, now=None, rehearsal=False, say=print, db=None, results_db=None, model_db=None):
    """Every 5 minutes (election/live.py): work the measures out and write a row for each race whose own figures changed
    (and for a race with a figure the first time). src is not used: this section makes no request. Returns a short
    dict for the log."""
    now = (now or utcnow()).astimezone(UTC)
    con = sqlite3.connect(db or DB, timeout=30)
    try:
        con.execute("PRAGMA busy_timeout=30000")
        if columns_of(con, "items") is None:
            return {"skipped": "no items table yet"}
        con.executescript(SCHEMA)
    finally:
        con.close()
    doc = compute(now=now, db=db, rehearsal=rehearsal, results_db=results_db, model_db=model_db, say=say)
    M, wmin = doc["M"], doc["w"]
    con = sqlite3.connect(db or DB, timeout=30)
    try:
        con.execute("PRAGMA busy_timeout=30000")
        last = {}
        q = (f"SELECT m.race_id, {', '.join('m.' + f for f in ROW_FIELDS)} FROM measures m JOIN (SELECT race_id, MAX(t) t FROM measures "
             "WHERE rehearsal = ? GROUP BY race_id) x ON x.race_id = m.race_id AND x.t = m.t WHERE m.rehearsal = ?")
        for row in con.execute(q, (int(rehearsal), int(rehearsal))):
            last[row[0]] = tuple(row[1:])
        t = iso(now)
        rows = []
        for rid, m in M.items():
            has = m["n"] or m["sp"] or m["i24"] or m["c1"] or m["c0"] or "mg" in m
            row = _row(m, wmin, doc["rates"][m["board"]])
            if rid in last:
                # the board's rate and the percentiles move with other races: a row is written when the race's own
                # figures change, and those come along with it
                own = lambda r: r[2:6] + r[11:13] + r[16:18] + r[21:24]     # noqa: E731
                if own(last[rid]) == own(row):
                    continue
            elif not has:
                continue
            rows.append((t, int(rehearsal), rid) + row + (METHOD,))
        if rows:
            con.executemany(f"INSERT OR REPLACE INTO measures (t, rehearsal, race_id, {', '.join(ROW_FIELDS)}, method) VALUES "
                            f"({', '.join('?' * (len(ROW_FIELDS) + 4))})", rows)
            con.commit()
    finally:
        con.close()
    ranked = {k: sum(1 for m in M.values() if k in m["rk"]) for k in "cgmb"}
    return {"t": iso(now), "window": wmin, "items": sum(1 for it in doc["items"] if it["t"] >= doc["w_from"]),
            "races_with_items": sum(1 for m in M.values() if m["n"]), "rows": len(rows), "ranked": ranked}


# ============================================================================================ the self-test

def selftest(say=print):
    ok = True

    def check(what, got, want, tol=1e-6):
        nonlocal ok
        good = (abs(got - want) <= tol) if isinstance(want, (int, float)) and isinstance(got, (int, float)) else got == want
        say(f"  {'ok ' if good else 'BAD'} {what}: {got!r}" + ("" if good else f" (expected {want!r})"))
        ok = ok and good

    # coverage: a 5,000-person school board with two stories against a board rate of 1.0 per 100,000
    raw, shown = coverage(2, 5000, 1.0)
    check("coverage raw, 2 items, 5,000 residents", round(raw, 3), 40.0)
    check("coverage shown, same, board rate 1.0", round(shown, 4), round(100000 * 3 / 105000, 4))
    raw, shown = coverage(30, 5_700_000, 1.0)
    check("coverage shown, a big state stays near its raw rate", round(shown, 3), round(100000 * 31 / 5_800_000, 3))
    # breadth: 10 stories, 8 from one paper
    check("effective outlets, 8 1 1", round(effective_number([8, 1, 1]), 2), 1.89)
    check("effective outlets, 5 even", round(effective_number([2, 2, 2, 2, 2]), 6), 5.0)
    # momentum: Garwood's bound
    check("upper 95% bound of 0", round(upper95(0), 3), 2.996)
    check("upper 95% bound of 3", round(upper95(3), 2), 7.75)
    check("3 to 6 is noise", momentum(6, 3)[2], False)
    check("30 to 60 is not", momentum(60, 30)[2], True)
    check("momentum ratio (5+1)/(2+1)", momentum(5, 2)[0], 2.0)
    # attention gap: percentiles with ties
    check("percentiles", percentiles([0.1, 0.5, 0.5, 0.9]), [0.0, 50.0, 50.0, 100.0])
    check("one race: 50", percentiles([3]), [50.0])
    check("margin, 52 to 48", round(margin_of([48, 52]), 4), 0.04)
    check("margin, two seats of four", round(margin_of([30, 28, 22, 20], 2), 4), round(6 / 50, 4))
    check("margin, one name", margin_of([60]), None)
    # the counting rules
    t = dt.datetime(2026, 11, 4, 3, 0, tzinfo=UTC)
    rows = [("https://a.com/1", "a.com", "x one", t), ("https://a.com/1", "a.com", "x one", t),       # the same address
            ("https://a.com/2", "a.com", "x one", t),                                                  # wire: same headline
            ("https://a.com/3", "a.com", "x three", t), ("https://a.com/4", "a.com", "x four", t),
            ("https://a.com/5", "a.com", "x five", t),                                                 # the fourth of one outlet
            ("https://b.org/1", "b.org", "x one", t)]                                                  # wire, another outlet
    n, by = count_items(rows)
    check("counted under the rules", (n, by), (4, {"a.com": 3, "b.org": 1}))
    n, by = count_items(rows, cap=None)
    check("uncounted cap (breadth)", (n, by), (5, {"a.com": 4, "b.org": 1}))
    check("canonical: query, AMP, www, slash", canonical("http://www.Example.com/news/amp/story/?utm=1#x"), "https://example.com/news/story")
    check("canonical: amp host", canonical("https://amp.example.com/a.amp.html"), "https://example.com/a")
    check("registered domain", (registered_domain("https://feeds.bbci.co.uk/news/rss"), registered_domain("www.mprnews.org")), ("bbci.co.uk", "mprnews.org"))
    check("district key", (district_key("001"), district_key("01A"), district_key("10")), ("1", "1A", "10"))
    check("times", iso(parse_time("2026-11-04 03:05:00")), "2026-11-04T03:05:00Z")
    say("measures self-test: " + ("passed" if ok else "FAILED"))
    return ok


# ============================================================================================ command line

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("what", choices=("selftest", "residents", "update", "page"))
    ap.add_argument("--db", default=None, help="the feed database (default night_feed_2026.sqlite)")
    ap.add_argument("--now", default=None, help="the moment to work the measures out for (UTC), for tests and replays")
    ap.add_argument("--rehearsal", action="store_true")
    ap.add_argument("--rebuild", action="store_true")
    ap.add_argument("--code", default="US")
    a = ap.parse_args(argv)
    now = parse_time(a.now) if a.now else None
    if a.what == "selftest":
        return 0 if selftest() else 1
    if a.what == "residents":
        con = ro(a.db or DB)
        try:
            races = load_races(con)
        finally:
            con.close()
        r = residents(races, rebuild=a.rebuild)
        known = sum(1 for v in r.values() if v[0])
        approx = sum(1 for v in r.values() if v[0] and v[2])
        print(f"residents: {known:,} of {len(r):,} races have a figure ({approx:,} of them approximate: the counties stand in)")
        missing = sorted(rid for rid, v in r.items() if not v[0])
        if missing:
            print(f"  no figure: {len(missing)}: " + ", ".join(missing[:20]) + (" ..." if len(missing) > 20 else ""))
        return 0
    if a.what == "update":
        print(json.dumps(update(now=now, rehearsal=a.rehearsal, db=a.db)))
        return 0
    doc = page_json(a.code, db=a.db, now=now, rehearsal=a.rehearsal, fresh=True)
    if doc is None:
        print("no feed file: the collectors' tables are not there yet")
        return 0
    text = json.dumps(doc, ensure_ascii=False, separators=(",", ":"))
    print(f"feed/{a.code.lower()}.json: {len(text.encode('utf-8')) / 1e3:,.1f} KB, {len(doc['h'])} headlines, {len(doc['r'])} races, "
          f"boards {', '.join(f'{b} c{len(v['c'])} g{len(v['g'])} m{len(v['m'])} b{len(v['b'])}' for b, v in doc['boards'].items())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
