"""election/feeds/geotag.py - where an item belongs (ARCHITECTURE.md 4.4), and the feed tables every collector writes.

    python -m election.feeds.geotag check              the placing rules' self-test on made-up headlines, the tables'
                                                       shape, and the D8 setting (no post marked for showing while
                                                       there is no contact address); exit 1 on failure
    python -m election.feeds.geotag place "HEADLINE" [--state MN]   where one made-up headline would be placed
    python -m election.feeds.geotag sample [--seconds 60] [--db scratch.sqlite]
                                                       every collector on a short, polite live sample into a scratch
                                                       copy of the feed database, then the privacy scan: no ordinary
                                                       account's handle, name, id or post id may be on disk anywhere
                                                       in the kit's folder (or the temporary folder) afterwards
    python -m election.feeds.geotag scan [--db FILE]   the at-rest scan alone: the feed tables hold only official
                                                       accounts' posts, every place has a confidence and a rule

THE TABLES (night_feed_2026.sqlite; ARCHITECTURE.md 2.3). Collectors write them through `store_item()` and
`SocialCounter`; election/feeds/measures.py reads them.

  items         one row per story or official post: item_id (the canonical address's SHA-256, 20 hex), source (gdelt,
                rss, bluesky, mastodon, youtube), kind ("news": a headline; "post": an official account's post), the
                outlet (outlet_id when it is on the list; outlet_key, the registered domain, which is what "distinct
                outlets" and "3 items per outlet" count; outlet_name, the credit line; via, an aggregator's name), the
                official account (account_id, for a post), home_state (the outlet's or account's), address (the
                canonical address: no query string, no AMP), link (as published), headline (or the post's text),
                published_at and fetched_at (UTC), election (1 when the words or GDELT's theme say it is about an
                election), shown (headlines 1; posts 0 until the site has a contact address, decision D8).
  item_places   item_id, race_id (the ballot databases' race id) or place_id (a state "MN", a county's five-digit
                FIPS "27053", a city "MN-P-43000" from the Census place code), place_kind (race, state, county, city),
                state, confidence (high, medium, low), rule (the rule that placed it, in words), how (which words).
  counts        minute (UTC, "2026-11-04T03:40Z"), race_id, kind (news, social), source, items, people. News: new
                stories placed on the race, by the minute they were published (only within the last day). Social:
                posts that name the race (rule 5: never by anyone's location), and the distinct people among them, each
                person counted once per race per clock hour through a keyed hash whose key is made at start and never
                written; the hour's set of hashes is dropped when the hour ends, leaving only its size here.
  deletions     platform, address, at: an official post deleted at its source and removed from items.
  feed_state    key, value, at: the collectors' places in their sources (GDELT's last file, a feed's ETag, a stream's
                cursor time). Times and file names only: never a post id or an account of anyone.

Nothing about an ordinary account is ever written to any table, file or log: no id, handle, name, text or post id.

THE PLACING RULES, in order (an item can be placed on several races and places):
  1. high: a candidate on a race's list is named (keywords.mentions(): a full name, or a family name with the race's
     words, and the outlet's home state or a state named in the headline is the race's state).
  1b. medium: the race itself is named: a statewide office's own words ("governor", "attorney general", "U.S. Senate")
     or a congressional district ("5th Congressional District", "MN-05") with its state named in the headline or the
     outlet in the state, and only when exactly one race of the state fits.
  2. high, or not placed: a county ("Hennepin County") or city named, within a state the outlet or the headline gives;
     a name that is also an ordinary word, a famous or a candidate's family name, or that two places of the state share,
     is not used.
  3. medium: GDELT's most-mentioned US state (and the county of its most-mentioned city) when it agrees with the
     outlet's home state; low when it does not or the outlet's home is not known. Only when rules 1 to 2 placed nothing.
  4. low: the outlet's home state, "placed by where the outlet is", shown only at state zoom. Only when nothing else did.
  5. Posts: rules 1, 1b and 2 on their text, the state context from the text alone (an official account's own state
     counts as an outlet's home state). Never by anyone's location.
"""

import argparse
import datetime as dt
import glob
import hashlib
import hmac
import json
import os
import re
import sqlite3
import sys
import tempfile
import threading
import time
from collections import Counter, defaultdict
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from election.feeds import CACHE, DB  # noqa: E402
from election.feeds import keywords as K  # noqa: E402
from election.feeds.outlets import registered_domain  # noqa: E402

UTC = dt.timezone.utc
GEOS = os.path.join(HERE, "states_cache", "acs2024", "Geos20245YR.txt")
PLACES_CACHE = os.path.join(CACHE, "census_places.json")
METHOD = "1.0"
COUNT_WINDOW = dt.timedelta(hours=24)        # a story published longer ago than this is kept but not counted

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
  item_id TEXT PRIMARY KEY, source TEXT NOT NULL, kind TEXT NOT NULL,
  outlet_id TEXT, outlet_key TEXT NOT NULL, outlet_name TEXT NOT NULL, via TEXT,
  account_id TEXT, home_state TEXT,
  address TEXT NOT NULL UNIQUE, link TEXT NOT NULL, headline TEXT NOT NULL,
  published_at TEXT, fetched_at TEXT NOT NULL,
  election INTEGER NOT NULL DEFAULT 0, shown INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS items_published ON items(published_at);
CREATE INDEX IF NOT EXISTS items_account ON items(account_id);
CREATE TABLE IF NOT EXISTS item_places (
  item_id TEXT NOT NULL, race_id TEXT, place_id TEXT, place_kind TEXT NOT NULL, state TEXT NOT NULL,
  confidence TEXT NOT NULL, rule TEXT NOT NULL, how TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS item_places_one ON item_places(item_id, COALESCE(race_id, ''), COALESCE(place_id, ''));
CREATE INDEX IF NOT EXISTS item_places_race ON item_places(race_id);
CREATE INDEX IF NOT EXISTS item_places_place ON item_places(place_id);
CREATE TABLE IF NOT EXISTS counts (
  minute TEXT NOT NULL, race_id TEXT NOT NULL, kind TEXT NOT NULL, source TEXT NOT NULL DEFAULT '',
  items INTEGER NOT NULL DEFAULT 0, people INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (minute, race_id, kind, source)
);
CREATE TABLE IF NOT EXISTS deletions (
  platform TEXT NOT NULL, address TEXT NOT NULL, at TEXT NOT NULL, PRIMARY KEY (platform, address)
);
CREATE TABLE IF NOT EXISTS feed_state (key TEXT PRIMARY KEY, value TEXT, at TEXT);
"""

R1 = "a candidate on the race's list is named"
R1B = "the race's office and its state are named"
R2 = "a place is named, in a state the outlet or the headline gives"
R3_AGREE = "GDELT's most-mentioned place, which agrees with the outlet's home state"
R3_OTHER = "GDELT's most-mentioned place (the outlet's home state differs or is not known)"
R4 = "placed by where the outlet is"


# ==================================================================================================== the database

def open_db(path=None):
    """The feed database with the collectors' tables (created on first use)."""
    con = sqlite3.connect(path or DB, timeout=60)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=60000")
    con.executescript(SCHEMA)
    return con


def utcnow():
    return dt.datetime.now(UTC)


def iso(t):
    return t.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z") if t else None


def minute_of(t):
    return t.astimezone(UTC).strftime("%Y-%m-%dT%H:%MZ")


def parse_time(s):
    if not s:
        return None
    if isinstance(s, dt.datetime):
        return s if s.tzinfo else s.replace(tzinfo=UTC)
    s = str(s).strip()
    try:
        t = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
        return t if t.tzinfo else t.replace(tzinfo=UTC)
    except ValueError:
        pass
    try:
        from email.utils import parsedate_to_datetime
        t = parsedate_to_datetime(s)
        return t if t.tzinfo else t.replace(tzinfo=UTC)
    except (TypeError, ValueError, IndexError):
        return None


def state_get(con, key, default=None):
    row = con.execute("SELECT value FROM feed_state WHERE key=?", (key,)).fetchone()
    return row[0] if row else default


def state_set(con, key, value):
    with con:
        con.execute("INSERT OR REPLACE INTO feed_state VALUES (?,?,?)", (key, value, iso(utcnow())))


def posts_shown_now():
    """The one setting (decision D8): accounts.CONTACT_ADDRESS. Off until John has created the site's contact address."""
    from election.feeds import accounts
    return bool(accounts.posts_may_be_shown())


def refresh_shown(con):
    """Posts follow the D8 setting and their account's standing; headlines are always shown. The accounts' own `shown`
    follows the same one setting (an active account is shown once the contact address exists, never before)."""
    on = posts_shown_now() and _has_accounts(con)
    with con:
        if _has_accounts(con):
            con.execute("UPDATE accounts SET shown = CASE WHEN ? = 1 THEN active ELSE 0 END WHERE shown != "
                        "CASE WHEN ? = 1 THEN active ELSE 0 END", (int(on), int(on)))
        if not on:
            con.execute("UPDATE items SET shown=0 WHERE kind='post' AND shown=1")
            return
        con.execute("UPDATE items SET shown=0 WHERE kind='post' AND shown=1 AND (account_id IS NULL OR account_id "
                    "NOT IN (SELECT account_id FROM accounts WHERE active=1))")
        con.execute("UPDATE items SET shown=1 WHERE kind='post' AND shown=0 AND account_id IN "
                    "(SELECT account_id FROM accounts WHERE active=1)")


def _has_accounts(con):
    return con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='accounts'").fetchone() is not None


# ==================================================================================================== addresses

AMP_PATH = re.compile(r"(/amp)+/?$|/amp/(?=[^/]*$)", re.I)
KEEP_QUERY = {"id", "p", "story_id", "storyid", "articleid", "article_id", "a", "sid", "newsid", "itemid", "v", "aid"}


def canonical(url):
    """One story, one address: scheme and host folded, "www." and "amp." taken off, the query string dropped (except a
    key that names the story on a page with no path of its own: ?p=123, watch?v=...), the fragment and any AMP tail."""
    try:
        s = urlsplit((url or "").strip())
    except ValueError:
        return ""
    if s.scheme.lower() not in ("http", "https") or not s.hostname:
        return ""
    host = s.hostname.lower().rstrip(".")
    for pre in ("www.", "amp.", "m."):
        if host.startswith(pre) and host.count(".") >= 2:
            host = host[len(pre):]
    path = re.sub(r"/{2,}", "/", s.path or "/")
    path = AMP_PATH.sub("/", path)
    path = re.sub(r"\.amp(\.html?)?$", r"\1", path, flags=re.I)
    if len(path) > 1:
        path = path.rstrip("/")
    q = ""
    keep = [(k, v) for k, v in parse_qsl(s.query, keep_blank_values=False) if k.lower() in KEEP_QUERY]
    generic = path in ("/", "") or re.search(r"\.(php|aspx?|cfm|jsp)$|/watch$|/index\.html?$", path, re.I)
    if keep and generic:
        q = urlencode(sorted(keep))
    return urlunsplit(("https", host, path or "/", q, ""))


def item_id(address):
    return hashlib.sha256(address.encode("utf-8")).hexdigest()[:20]


# ==================================================================================================== election words

ELECTION_WORDS = set("""
election elections electoral elect elected electing reelection reelect vote votes voted voting voter voters ballot
ballots poll polls polling pollster campaign campaigns campaigning candidate candidates candidacy primary primaries
midterm midterms runoff runoffs recount recounts canvass canvassing turnout absentee concede concedes conceded
concession debate debates endorse endorses endorsed endorsement endorsements gubernatorial caucus caucuses
referendum electorate precinct precincts incumbent incumbents challenger challengers nominee nominees
""".split())
RACE_WITH = re.compile(r"\b(race|races|seat|seats|contest|matchup|showdown|frontrunner)\b")
OFFICE_HINT = re.compile(r"\b(governor|senate|senator|house|congress|congressional|mayor|mayoral|council|sheriff|"
                         r"attorney general|secretary of state|legislature|legislative|school board|judge|justice|"
                         r"commissioner|auditor|treasurer|district)\b")


def is_election(text):
    t = K.norm(text)
    words = set(t.split())
    if words & ELECTION_WORDS:
        return True
    return bool(RACE_WITH.search(t) and OFFICE_HINT.search(t))


GDELT_THEMES = {"ELECTION", "TAX_FNCACT_CANDIDATE", "TAX_FNCACT_CANDIDATES", "TAX_FNCACT_VOTER", "TAX_FNCACT_VOTERS",
                "TAX_FNCACT_ELECTORAL_OFFICIAL"}


def gdelt_election(themes):
    return any(t in GDELT_THEMES or t.startswith("ELECTION") for t in themes)


# ==================================================================================================== Census places

PLACE_KIND = re.compile(r"\s+(city and borough|consolidated government|metropolitan government|unified government|"
                        r"urban county|city|town|village|borough|municipality|corporation)\s*$", re.I)
COUNTY_WORDS = ("county", "parish", "borough", "census area", "city and borough", "municipality", "municipio")
# Single words never used as a city's name alone: ordinary words a headline uses for other things.
PLACE_STOP = set("""
union liberty independence commerce mission victory republic freedom justice hope harmony opportunity industry
enterprise progress unity paradise friendship center central media normal marshall mayor democrat republican
congress senate capitol columbia lincoln franklin jackson washington jefferson madison monroe hamilton clinton
warren carson cleveland pierce taylor tyler grant hoover truman kennedy johnson nixon reagan carter bush obama
trump harris vance walz american america national federal state county city town village general early late
north south east west new old lake river spring springs valley hill hills park beach bay harbor port mount
fairview midway riverside oakland salem greenville bristol clayton chester dover georgetown kingston newport
oxford manchester troy auburn burlington ashland milton marion fremont lexington concord princeton plymouth
""".split())


def _census_places():
    """{state: {"county": {phrase: (fips, name)}, "city": {phrase: [(id, name)]}}} from the ACS geography file (on disk),
    cached in election_cache/feeds/census_places.json."""
    if os.path.exists(PLACES_CACHE) and os.path.exists(GEOS) and os.path.getmtime(PLACES_CACHE) >= os.path.getmtime(GEOS):
        try:
            with open(PLACES_CACHE, encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, ValueError):
            pass
    out = {}
    if not os.path.exists(GEOS):
        return out
    with open(GEOS, encoding="latin-1") as fh:
        head = fh.readline().rstrip("\n").split("|")
        ix = {k: i for i, k in enumerate(head)}
        for line in fh:
            f = line.rstrip("\n").split("|")
            if len(f) < len(head) or f[ix["COMPONENT"]] != "00" or f[ix["SUMLEVEL"]] not in ("050", "160"):
                continue
            st = f[ix["STUSAB"]]
            name = f[ix["NAME"]].rsplit(",", 1)[0].strip()
            d = out.setdefault(st, {"county": {}, "city": {}})
            if f[ix["SUMLEVEL"]] == "050":
                fips = f[ix["STATE"]] + f[ix["COUNTY"]]
                d["county"][K.norm(name)] = [fips, name]
                core = K.norm(re.sub(r"\s+(county|parish|borough|census area|city and borough|municipality|municipio)$",
                                     "", name, flags=re.I))
                for w in ("county", "parish", "borough"):
                    if name.lower().endswith(w) and core:
                        d["county"].setdefault(f"{core} {w}", [fips, name])
            else:
                if re.search(r"\bCDP$|\bcomunidad$|\bzona urbana$", name):
                    continue
                core = re.sub(r"\s*\([^)]*\)", "", name)
                core = re.sub(r"-.*\b(metropolitan government|urban county|unified government|consolidated government)"
                              r".*$", "", core, flags=re.I)
                core = PLACE_KIND.sub("", core)
                core = K.norm(core)
                if not core:
                    continue
                pid = f"{st}-P-{f[ix['PLACE']]}"
                d["city"].setdefault(core, []).append([pid, name])
                if core.startswith("st "):
                    d["city"].setdefault("saint " + core[3:], []).append([pid, name])
                if core.startswith("saint "):
                    d["city"].setdefault("st " + core[6:], []).append([pid, name])
    os.makedirs(CACHE, exist_ok=True)
    tmp = PLACES_CACHE + ".part"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(out, fh, separators=(",", ":"))
    os.replace(tmp, PLACES_CACHE)
    return out


# ==================================================================================================== the placer

STATE_NAME_TO_CODE = {K.norm(v): k for k, v in K.STATE_NAMES.items()}
FIPS_TO_STATE = {}


def _fips_states():
    if FIPS_TO_STATE:
        return FIPS_TO_STATE
    codes = ("AL 01 AK 02 AZ 04 AR 05 CA 06 CO 08 CT 09 DE 10 DC 11 FL 12 GA 13 HI 15 ID 16 IL 17 IN 18 IA 19 KS 20 "
             "KY 21 LA 22 ME 23 MD 24 MA 25 MI 26 MN 27 MS 28 MO 29 MT 30 NE 31 NV 32 NH 33 NJ 34 NM 35 NY 36 NC 37 "
             "ND 38 OH 39 OK 40 OR 41 PA 42 RI 44 SC 45 SD 46 TN 47 TX 48 UT 49 VT 50 VA 51 WA 53 WV 54 WI 55 "
             "WY 56").split()
    for i in range(0, len(codes), 2):
        FIPS_TO_STATE[codes[i + 1]] = codes[i]
    return FIPS_TO_STATE


def ngrams(t, n=6):
    w = t.split()
    out = set()
    for size in range(1, n + 1):
        for i in range(len(w) - size + 1):
            out.add(" ".join(w[i:i + size]))
    return out


# Office words that name one statewide race of a state on their own (with the state named). Longer phrases first.
RACE_OFFICE = (
    ("lieutenant_governor", ("lieutenant governor", "lt governor", "lt gov", "lieutenant gov")),
    ("governor", ("governor", "gubernatorial", "governors race", "governor race")),
    ("attorney_general", ("attorney general",)),
    ("secretary_of_state", ("secretary of state",)),
    ("state_auditor", ("state auditor",)),
    ("state_treasurer", ("state treasurer",)),
    ("U.S. Senate", ("u s senate", "us senate")),
)


OTHER_DISTRICT = re.compile(r" (senate|house|legislative|school|judicial|county|council|commission|commissioner|ward|"
                            r"park|soil|hospital|sanitary|fire|water|state) (district|districts) | (district) \d+[a-z] |"
                            r" (state senate|state house|legislature|city council|school board|county board) ")


class Placer:
    """Where a headline or a post belongs. Built once from the race keyword sets (keywords.py) and Census names."""

    def __init__(self, con=None, places=True):
        own = con is None
        con = con or sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        self.kw = {}
        for rid, js in con.execute("SELECT race_id, keywords FROM race_keywords"):
            self.kw[rid] = json.loads(js)
        if own:
            con.close()
        self.by_phrase = defaultdict(set)         # a candidate's full-name phrase or family name -> race ids
        self.office = defaultdict(lambda: defaultdict(list))   # state -> office kind -> race ids
        self.house = defaultdict(list)            # (state, phrase) -> race ids, for congressional districts
        self.house_ord = defaultdict(list)        # (state, "5th district") -> race ids: Congress unless told otherwise
        self.families = defaultdict(set)          # state -> family names of its candidates (not used as city names)
        for rid, kw in self.kw.items():
            for c in kw["candidates"]:
                for p in c["alone"]:
                    self.by_phrase[p].add(rid)
                if c["family_needs"] != "never":
                    for f in [c["family"]] + c.get("family_also", []):
                        if f:
                            self.by_phrase[f].add(rid)
                if c["family"]:
                    self.families[kw["state"]].add(c["family"])
            if kw["level"] in ("statewide", "federal") and kw["kind"] != "U.S. House":
                self.office[kw["state"]][kw["kind"]].append(rid)
            if kw["kind"] == "U.S. House":
                st = kw["state"].lower()
                dws = kw["district_words"]
                for w in dws:
                    if "congressional" in w or w.startswith(("cd", st)):
                        self.house[(kw["state"], w)].append(rid)
                    elif re.fullmatch(r"\d+(st|nd|rd|th) district", w):
                        self.house_ord[(kw["state"], w)].append(rid)
        self.state_words = {}
        for code in K.STATE_NAMES:
            for w in K.state_words(code):
                self.state_words.setdefault(w, set()).add(code)
        self.places = _census_places() if places else {}
        self.county_phrase = {}                   # phrase -> [(state, fips, name)]
        self.city_phrase = {}
        for st, d in self.places.items():
            for ph, (fips, name) in d["county"].items():
                self.county_phrase.setdefault(ph, []).append((st, fips, name))
            for ph, lst in d["city"].items():
                self.city_phrase.setdefault(ph, []).append((st, lst))

    # ------------------------------------------------------------------ helpers
    def states_named(self, t, grams):
        out = set()
        for g in grams:
            for code in self.state_words.get(g, ()):
                if code == "WA" and g == "washington" and " washington state " not in f" {t} ":
                    continue                       # "Washington" is the capital's shorthand far more often
                out.add(code)
        return out

    def place(self, text, outlet_state=None, gdelt=None, post=False):
        """[{place, place_kind, state, confidence, rule, how}] for one headline or post. outlet_state: the outlet's
        or official account's home state ("US" or None when national or not known). gdelt: GDELT's locations
        [(type, adm1, adm2, featureid)] for rule 3. post: an official post or a counted post (rules 1, 1b, 2 only)."""
        t = K.norm(text)
        if not t:
            return []
        padded = f" {t} "
        grams = ngrams(t)
        named = self.states_named(t, grams)
        home = outlet_state if outlet_state and outlet_state != "US" else None
        ctx = set(named) | ({home} if home else set())
        out, seen = [], set()

        def add(place, kind, state, conf, rule, how):
            if place in seen:
                return
            seen.add(place)
            out.append({"place": place, "place_kind": kind, "state": state, "confidence": conf, "rule": rule,
                        "how": how})

        # rule 1: a candidate named
        cand_races = set()
        for g in grams:
            cand_races |= self.by_phrase.get(g, set())
        for rid in sorted(cand_races):
            kw = self.kw[rid]
            if kw["state"] not in ctx:
                continue
            hits = K.mentions(text, kw, outlet_state=home)
            if hits:
                add(rid, "race", kw["state"], "high", R1, hits[0][1])
        # rule 1b: the race's office and its state
        for st in sorted(ctx):
            rest = padded
            for kind, phrases in RACE_OFFICE:
                hit = next((p for p in phrases if f" {p} " in rest), None)
                if not hit:
                    continue
                rest = rest.replace(f" {hit} ", " ")
                races = self.office.get(st, {}).get(kind, [])
                if len(races) == 1 and races[0] not in seen:
                    add(races[0], "race", st, "medium", R1B, hit)
            hrace = set()
            for (hst, w), rids in self.house.items():
                if hst == st and f" {w} " in padded:
                    hrace.update(rids)
            if not hrace and not OTHER_DISTRICT.search(padded):     # "1st District race": Congress, unless the
                for (hst, w), rids in self.house_ord.items():         # headline names another kind of district
                    if hst == st and f" {w} " in padded:
                        hrace.update(rids)
            if len(hrace) == 1:
                rid = next(iter(hrace))
                if rid not in seen:
                    add(rid, "race", st, "medium", R1B, "the congressional district")
        # rule 2: a county or a city in a state the outlet or the headline gives
        for g in grams:
            for st, fips, name in self.county_phrase.get(g, ()):
                if st in ctx and " " in g:
                    add(fips, "county", st, "high", R2, name)
        for g in grams:
            for st, lst in self.city_phrase.get(g, ()):
                if st not in ctx or len(lst) != 1:
                    continue
                if self._city_unsafe(g, st):
                    continue
                if any(g == ph.split(" county")[0] for ph in self.places.get(st, {}).get("county", {})):
                    continue                      # "Hennepin" alone: the county is named only with the word County
                add(lst[0][0], "city", st, "high", R2, lst[0][1])
        if out or post:
            return out
        # rule 3: GDELT's places
        if gdelt:
            by_state = Counter()
            city_county = defaultdict(Counter)
            for typ, adm1, adm2, _fid in gdelt:
                if not adm1.startswith("US") or len(adm1) != 4:
                    continue
                st = adm1[2:]
                if st not in K.STATE_NAMES:
                    continue
                by_state[st] += 1
                fips = self._adm2_fips(st, adm2)
                if typ in ("3", "4") and fips:
                    city_county[st][fips] += 1
            if by_state:
                top = by_state.most_common()
                best = [s for s, n in top if n == top[0][1]]
                st = home if home in best else (best[0] if len(best) == 1 else None)
                if st:
                    agree = home == st
                    conf, rule = ("medium", R3_AGREE) if agree else ("low", R3_OTHER)
                    add(st, "state", st, conf, rule, "GDELT")
                    if city_county[st]:
                        fips, _n = city_county[st].most_common(1)[0]
                        add(fips, "county", st, conf, rule, "GDELT")
                    return out
        # rule 4: where the outlet is
        if home:
            add(home, "state", home, "low", R4, "the outlet's home state")
        return out

    def _city_unsafe(self, g, st):
        words = g.split()
        if len(words) == 1:
            w = words[0]
            if len(w) < 5 or w in PLACE_STOP or w in K.ORDINARY or w in K.FAMOUS or w in STATE_NAME_TO_CODE:
                return True
        if g in self.families.get(st, ()) or g in STATE_NAME_TO_CODE or g in ELECTION_WORDS:
            return True
        return False

    @staticmethod
    def _adm2_fips(st, adm2):
        """GDELT writes a US county as the state's letters and the county's three digits ("MN053")."""
        m = re.fullmatch(r"([A-Z]{2})(\d{3})", adm2 or "")
        if not m or m.group(1) != st:
            return None
        sf = {v: k for k, v in _fips_states().items()}.get(st)
        return sf + m.group(2) if sf else None


_PLACER = None
_PLACER_LOCK = threading.Lock()


def placer(con=None):
    """One Placer for the process (built in about a second)."""
    global _PLACER
    with _PLACER_LOCK:
        if _PLACER is None:
            _PLACER = Placer(con)
        return _PLACER


# ==================================================================================================== writing items

def store_item(con, *, source, kind, address, link, headline, published=None, fetched=None, outlet_id=None,
               outlet_key="", outlet_name="", via=None, account_id=None, home_state=None, election=0, places=(),
               count_source=None):
    """Writes one story or official post with its places, once. Returns True when it was new. A news story placed on a
    race is also counted (counts, kind news) by the minute it was published, when that is within the last day."""
    if not address or not headline:
        return False
    iid = item_id(address)
    fetched = fetched or utcnow()
    pub = parse_time(published)
    if pub and pub > fetched + dt.timedelta(minutes=10):
        pub = None                                             # a time in the future is not believed
    shown = 1 if kind == "news" else (1 if posts_shown_now() else 0)
    with con:
        cur = con.execute(
            "INSERT OR IGNORE INTO items (item_id, source, kind, outlet_id, outlet_key, outlet_name, via, account_id, "
            "home_state, address, link, headline, published_at, fetched_at, election, shown) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (iid, source, kind, outlet_id, outlet_key or "", outlet_name or outlet_key or "", via, account_id,
             home_state, address, link or address, headline[:1000], iso(pub), iso(fetched), int(bool(election)), shown))
        if cur.rowcount == 0:
            return False
        for p in places:
            race = p["place_kind"] == "race"
            con.execute("INSERT OR IGNORE INTO item_places (item_id, race_id, place_id, place_kind, state, confidence, "
                        "rule, how) VALUES (?,?,?,?,?,?,?,?)",
                        (iid, p["place"] if race else None, None if race else p["place"], p["place_kind"], p["state"],
                         p["confidence"], p["rule"], p.get("how")))
        if kind == "news" and pub and fetched - pub <= COUNT_WINDOW:
            for p in places:
                if p["place_kind"] == "race":
                    con.execute("INSERT INTO counts (minute, race_id, kind, source, items, people) VALUES (?,?,?,?,1,0) "
                                "ON CONFLICT(minute, race_id, kind, source) DO UPDATE SET items = items + 1",
                                (minute_of(pub), p["place"], "news", count_source or source))
    return True


def remove_post(con, platform, address, at=None):
    """An official post deleted at its source: gone from items and its places, and the deletion noted."""
    iid = item_id(address)
    with con:
        n = con.execute("DELETE FROM items WHERE item_id=?", (iid,)).rowcount
        con.execute("DELETE FROM item_places WHERE item_id=?", (iid,))
        if n:
            con.execute("INSERT OR REPLACE INTO deletions VALUES (?,?,?)", (platform, address, iso(at or utcnow())))
    return n


class SocialCounter:
    """Counts posts that name a race, and the distinct people among them, without knowing who anyone is.

    A person is a keyed hash (HMAC-SHA256, a key made here from os.urandom and never written) of the platform's own
    account id, held in memory in a set per race and clock hour; the set is dropped when the hour ends. Only numbers
    reach the database: per minute, race and source, how many posts and how many people not seen before that hour."""

    def __init__(self, source):
        self.source = source
        self._key = os.urandom(32)
        self._sets = {}                  # (race, hour) -> set of 16-byte digests (memory only)
        self._pending = defaultdict(lambda: [0, 0])
        self._seen_posts = {}            # digest of a post's address -> hour (memory only), for posts seen twice
        self._lock = threading.Lock()
        self.total_posts = 0
        self.total_matched = 0

    def _h(self, token):
        return hmac.new(self._key, token.encode("utf-8"), hashlib.sha256).digest()[:16]

    def seen_post(self, address, when):
        """True when this post (by its address) was already counted this hour or the last (one post, once)."""
        d = self._h("post:" + address)
        hour = when.strftime("%Y%m%d%H")
        with self._lock:
            if d in self._seen_posts:
                return True
            self._seen_posts[d] = hour
        return False

    def add(self, person, races, when):
        if not races:
            return
        hour = when.strftime("%Y%m%d%H")
        d = self._h("person:" + person)
        with self._lock:
            self.total_matched += 1
            for rid in races:
                key = (rid, hour)
                s = self._sets.setdefault(key, set())
                cell = self._pending[(minute_of(when), rid)]
                cell[0] += 1
                if d not in s:
                    s.add(d)
                    cell[1] += 1

    def flush(self, con, now=None):
        now = now or utcnow()
        hour = now.strftime("%Y%m%d%H")
        with self._lock:
            pend, self._pending = self._pending, defaultdict(lambda: [0, 0])
            for key in [k for k in self._sets if k[1] < hour]:
                del self._sets[key]                       # the hour is over: only its size (already counted) stays
            prev = (now - dt.timedelta(hours=1)).strftime("%Y%m%d%H")
            for d in [d for d, h in self._seen_posts.items() if h < prev]:
                del self._seen_posts[d]
        if not pend:
            return 0
        with con:
            for (minute, rid), (n, p) in pend.items():
                con.execute("INSERT INTO counts (minute, race_id, kind, source, items, people) VALUES (?,?,?,?,?,?) "
                            "ON CONFLICT(minute, race_id, kind, source) DO UPDATE SET items = items + excluded.items, "
                            "people = people + excluded.people", (minute, rid, "social", self.source, n, p))
        return len(pend)


def races_in(placements):
    return sorted({p["place"] for p in placements if p["place_kind"] == "race"})


# ==================================================================================================== the self-test

def selftest(say=print):
    """The placing rules on made-up headlines, against a made-up keyword set (no feed text, no network)."""
    ok = True
    P = Placer.__new__(Placer)
    P.kw = {}
    P.by_phrase, P.office, P.house, P.families = defaultdict(set), defaultdict(lambda: defaultdict(list)), \
        defaultdict(list), defaultdict(set)
    P.house_ord = defaultdict(list)
    P.state_words = {}
    for code in K.STATE_NAMES:
        for w in K.state_words(code):
            P.state_words.setdefault(w, set()).add(code)
    gov = {"race_id": "T-GOV", "state": "MN", "level": "statewide", "kind": "governor",
           "office_words": K.office_words("governor", "Governor"), "district_words": [], "state_words": K.state_words("MN"),
           "specific_words": K.office_words("governor", "Governor"), "specific_also": [], "candidates": []}
    for nm, fn in (("Jane Q. Example", "office"), ("Mary Lake", "never")):
        ph, fam, ex = K.name_variants(nm)
        gov["candidates"].append({"name": nm, "alone": ph, "family": fam, "family_also": ex, "family_needs": fn,
                                  "full_needs": "state"})
    h5 = {"race_id": "T-H05", "state": "MN", "level": "federal", "kind": "U.S. House",
          "office_words": K.office_words("U.S. House", "U.S. House"),
          "district_words": K.district_words("federal", "U.S. House", "05", None, "MN", ""),
          "state_words": K.state_words("MN"), "candidates": [],
          "specific_words": K.district_words("federal", "U.S. House", "05", None, "MN", ""), "specific_also": []}
    for kw in (gov, h5):
        P.kw[kw["race_id"]] = kw
        for c in kw["candidates"]:
            for p in c["alone"]:
                P.by_phrase[p].add(kw["race_id"])
            if c["family_needs"] != "never":
                P.by_phrase[c["family"]].add(kw["race_id"])
            P.families["MN"].add(c["family"])
    P.office["MN"]["governor"].append("T-GOV")
    for w in h5["district_words"]:
        if "congressional" in w or w.startswith(("cd", "mn")):
            P.house[("MN", w)].append("T-H05")
        elif re.fullmatch(r"\d+(st|nd|rd|th) district", w):
            P.house_ord[("MN", w)].append("T-H05")
    P.places = {"MN": {"county": {"hennepin county": ["27053", "Hennepin County"]},
                       "city": {"richfield": [["MN-P-54214", "Richfield city"]], "lake": [["MN-P-0", "Lake city"]],
                                "rochester": [["MN-P-54880", "Rochester city"]]}},
                "NY": {"county": {}, "city": {"rochester": [["NY-P-63000", "Rochester city"]]}}}
    P.county_phrase, P.city_phrase = {}, {}
    for st, d in P.places.items():
        for ph, (fips, name) in d["county"].items():
            P.county_phrase.setdefault(ph, []).append((st, fips, name))
        for ph, lst in d["city"].items():
            P.city_phrase.setdefault(ph, []).append((st, lst))

    def got(text, home=None, gd=None, post=False):
        return [(p["place"], p["confidence"]) for p in P.place(text, home, gd, post)]

    cases = [
        ("Jane Example leads in Minnesota governor's race", None, None, False,
         [("T-GOV", "high")]),
        ("Example wins endorsement for governor", "MN", None, False, [("T-GOV", "high")]),
        ("Jane Example speaks in Ohio", "OH", None, False, [("OH", "low")]),
        ("Minnesota governor race tightens", "US", None, False, [("T-GOV", "medium")]),
        ("Lieutenant governor candidates meet in Minnesota", "US", None, False, []),
        ("Voters in Minnesota's 5th Congressional District head to polls", None, None, False, [("T-H05", "medium")]),
        ("Richfield council race draws crowd", "MN", None, False, [("MN-P-54214", "high")]),
        ("TV ad in Minnesota's 5th District race draws accusations", "MN", None, False, [("T-H05", "medium")]),
        ("Hopefuls in the 5th district school board race", "MN", None, False, [("MN", "low")]),
        ("Rochester voters weigh school levy", "US", None, False, []),
        ("Rochester voters weigh school levy", "NY", None, False, [("NY-P-63000", "high")]),
        ("Hennepin County election judges trained", "US", None, False, []),
        ("Hennepin County election judges trained in Minnesota", None, None, False, [("27053", "high")]),
        ("Lake effect snow could slow voters", "MN", None, False, [("MN", "low")]),
        ("Turnout high across the state", "WA", [("2", "USMN", "", "")], False, [("MN", "low")]),
        ("Turnout high across the state", "MN", [("3", "USMN", "MN053", "1"), ("2", "USMN", "", "")], False,
         [("MN", "medium"), ("27053", "medium")]),
        ("Turnout high across the state", "MN", None, True, []),
        ("Jane Example will debate tonight #mnpol minnesota", None, None, True, [("T-GOV", "high")]),
    ]
    for text, home, gd, post, want in cases:
        g = got(text, home, gd, post)
        good = g == want
        ok = ok and good
        say(f"{'PASS' if good else 'FAIL'} placing: {text!r} (outlet {home or '-'}) -> {g}")
    for url, want in (("https://www.example.com/news/story-1/?utm_source=x#top", "https://example.com/news/story-1"),
                      ("https://amp.example.com/news/story-1/amp/", "https://example.com/news/story-1"),
                      ("https://example.com/news/story-1.amp.html", "https://example.com/news/story-1.html"),
                      ("https://example.com/?p=123&utm_medium=rss", "https://example.com/?p=123"),
                      ("https://www.youtube.com/watch?v=abcDEF12345", "https://youtube.com/watch?v=abcDEF12345")):
        c = canonical(url)
        good = c == want
        ok = ok and good
        say(f"{'PASS' if good else 'FAIL'} one story, one address: {url} -> {c}")
    for text, want in (("Early voting opens in Minnesota", True), ("Council race heats up", True),
                       ("Vikings win in overtime", False), ("Race for the cure draws runners", False)):
        good = is_election(text) == want
        ok = ok and good
        say(f"{'PASS' if good else 'FAIL'} election words: {text!r} -> {is_election(text)}")
    # the counter: the same person twice in an hour counts once; a new hour counts again; only numbers are written
    sc = SocialCounter("test")
    mem = sqlite3.connect(":memory:")
    mem.executescript(SCHEMA)
    t0 = dt.datetime(2026, 11, 4, 2, 10, tzinfo=UTC)
    sc.add("x", ["R"], t0)
    sc.add("x", ["R"], t0 + dt.timedelta(minutes=5))
    sc.add("y", ["R"], t0 + dt.timedelta(minutes=5))
    sc.flush(mem, t0 + dt.timedelta(minutes=6))
    sc.add("x", ["R"], t0 + dt.timedelta(hours=1))
    sc.flush(mem, t0 + dt.timedelta(hours=1, minutes=1))
    tot = mem.execute("SELECT SUM(items), SUM(people) FROM counts").fetchone()
    left = sum(len(v) for v in sc._sets.values())
    good = tuple(tot) == (4, 3) and left == 1
    ok = ok and good
    say(f"{'PASS' if good else 'FAIL'} distinct people: once per race per hour (4 posts, 3 person-hours: {tuple(tot)}; "
        f"the finished hour's set dropped: {left} left)")
    return ok


# ==================================================================================================== checks and scans

def run_checks(db=None, say=print):
    ok = True

    def check(cond, line):
        nonlocal ok
        say(("PASS " if cond else "FAIL ") + line)
        ok = ok and bool(cond)

    check(selftest(say=lambda s: say("     " + s)), "the placing rules' self-test")
    from election.feeds import bluesky, mastodon
    check(bluesky.selftest(say=lambda s: say("     " + s)), "Bluesky: counted, kept, deletions honoured (self-test)")
    check(mastodon.selftest(say=lambda s: say("     " + s)), "Mastodon: who is counted, and once (self-test)")
    from election.feeds import rss
    got = rss.items_of(b'<?xml version="1.0" encoding="utf-8"?><rss><channel><item><title>Vote &amp; count</title>'
                       b'<link>https://example.org/a?utm_source=rss</link><description>SECRET ARTICLE TEXT</description>'
                       b'<content:encoded><![CDATA[MORE TEXT]]></content:encoded><pubDate>Tue, 03 Nov 2026 '
                       b'20:00:00 -0600</pubDate></item></channel></rss>')
    check(got == [("Vote & count", "https://example.org/a?utm_source=rss", "Tue, 03 Nov 2026 20:00:00 -0600")],
          "a feed item gives its title, link and time only (never the description or the article)")
    from election.feeds import accounts
    check(accounts.CONTACT_ADDRESS is None or bool(accounts.CONTACT_ADDRESS),
          f"the D8 setting: {'a contact address is set' if accounts.posts_may_be_shown() else 'no contact address yet, so no post is marked for showing'}")
    if db and os.path.exists(db):
        con = open_db(db)
        ok = scan_tables(con, say) and ok
        con.close()
    try:
        P = placer()
        check(len(P.kw) > 5000, f"the placer reads {len(P.kw)} race keyword sets and Census names of "
                                f"{len(P.places)} states")
    except sqlite3.Error as e:
        check(False, f"the placer could not read the keyword sets ({e.__class__.__name__})")
    return ok


def scan_tables(con, say=print):
    """At rest: every post belongs to an official account; nothing shown while D8 is off; places carry their rule."""
    ok = True

    def check(cond, line):
        nonlocal ok
        say(("PASS " if cond else "FAIL ") + line)
        ok = ok and bool(cond)

    n = con.execute("SELECT COUNT(*), SUM(kind='post') FROM items").fetchone()
    stray = con.execute("SELECT COUNT(*) FROM items WHERE kind='post' AND (account_id IS NULL OR account_id NOT IN "
                        "(SELECT account_id FROM accounts))").fetchone()[0] if _has_accounts(con) else \
        con.execute("SELECT COUNT(*) FROM items WHERE kind='post'").fetchone()[0]
    check(stray == 0, f"every post ({n[1] or 0} of {n[0] or 0} items) is from an official account on the list")
    if not posts_shown_now():
        shown = con.execute("SELECT COUNT(*) FROM items WHERE kind='post' AND shown=1").fetchone()[0]
        check(shown == 0, "no post is marked for showing (no contact address yet, D8)")
    bad = con.execute("SELECT COUNT(*) FROM item_places WHERE confidence NOT IN ('high','medium','low') OR rule='' "
                      "OR rule IS NULL").fetchone()[0]
    check(bad == 0, "every place has a confidence and the rule that placed it")
    two = con.execute("SELECT COUNT(*) FROM item_places WHERE (race_id IS NULL) = (place_id IS NULL) OR "
                      "(race_id IS NOT NULL) != (place_kind = 'race')").fetchone()[0]
    check(two == 0, "every place row is either a race or a place, never both or neither")
    cols = {r[1] for r in con.execute("PRAGMA table_info(counts)")}
    check(cols == {"minute", "race_id", "kind", "source", "items", "people"}, "counts hold numbers only")
    return ok


# Shapes an ordinary account's traces could take on disk: a DID, a post's record key, a number id, a Mastodon address,
# a handle (a domain-like name). Each is looked up in the set of needles, so a long word cannot hide a short one.
SHAPES = [re.compile(rb"did:(?:plc|web):[a-z0-9.:%-]+"),
          re.compile(rb"(?<![a-z2-7])[a-z2-7]{13}(?![a-z2-7])"),
          re.compile(rb"(?<!\d)\d{6,20}(?!\d)"),
          re.compile(rb"[a-z0-9_.]{1,30}@[a-z0-9.-]+\.[a-z]{2,}"),
          re.compile(rb"(?<![a-z0-9.-])[a-z0-9][a-z0-9-]*(?:\.[a-z0-9-]+)+")]
SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__"}


def privacy_scan(needles, since, roots=None, say=print, names=()):
    """Every file under the kit's folder (and the temporary folder) written since `since` (epoch seconds), searched for
    any of `needles` (ordinary accounts' ids, handles and post ids, held in memory by the caller) and for any of
    `names` (display names, as plain text). Prints file counts only, never what was searched for. True when clean."""
    roots = roots or [HERE, tempfile.gettempdir()]
    needles = {n.lower().encode("utf-8") for n in needles if n and len(n) >= 6}
    names = [n.lower().encode("utf-8") for n in names if n and len(n) >= 10]
    files = hits = 0
    hit_files = []
    for root in roots:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for fn in filenames:
                p = os.path.join(dirpath, fn)
                try:
                    if os.path.getmtime(p) < since or os.path.getsize(p) > 2_000_000_000:
                        continue
                    with open(p, "rb") as fh:
                        data = fh.read()
                except OSError:
                    continue
                files += 1
                low = data.lower()
                found = any(m.group(0) in needles for rx in SHAPES for m in rx.finditer(low))
                if not found and names:
                    found = any(n in low for n in names)
                if found:
                    hits += 1
                    hit_files.append(os.path.relpath(p, root) if root == HERE else p)
    say(f"privacy scan: {files} files written since the sample began, searched for {len(needles)} ordinary accounts' "
        f"ids, handles and post ids and {len(names)} names; {hits} files hold any of them"
        + (f": {', '.join(hit_files[:8])}" if hit_files else ""))
    return hits == 0


# ==================================================================================================== the live sample

def sample(seconds=60, db=None, say=print):
    """Each collector briefly and politely against the live sources, into a scratch copy of the feed database; the
    ordinary accounts each one saw are held here in memory only, then searched for on disk."""
    import shutil
    from election.feeds import accounts, bluesky, gdelt, mastodon, rss, youtube
    from election.source import Source
    if not db:
        raise SystemExit("give --db: a scratch copy of the feed database (the real one is not written by a sample)")
    if not os.path.exists(db):
        src_con = sqlite3.connect(DB)
        dst = sqlite3.connect(db)
        src_con.backup(dst)
        dst.close()
        src_con.close()
    since = time.time() - 1
    needles, names = set(), set()
    src = Source(stopped_file=os.path.join(CACHE, "stopped_hosts.json"), log=accounts._log)
    ok = True
    say("sample: GDELT's newest 15-minute file")
    say("  " + json.dumps(gdelt.poll(src=src, say=say, db=db, backfill=0)))
    say("sample: twelve news feeds (conditional requests)")
    say("  " + json.dumps(rss.poll(src=src, say=say, db=db, limit=12)))
    say("sample: Mastodon, two servers, two tags each")
    seen = {}
    say("  " + json.dumps(mastodon.sample(src=src, say=say, db=db, requests=4, witness=seen)))
    needles |= seen.get("ids", set())
    names |= seen.get("names", set())
    say("sample: six official YouTube channels")
    say("  " + json.dumps(youtube.poll(src=src, say=say, db=db, limit=6, wait=True)))
    say(f"sample: Bluesky's counting stream and official stream for {seconds} seconds")
    seen = {}
    res = bluesky.sample(seconds=seconds, src=src, say=say, db=db, witness=seen)
    say("  " + json.dumps(res))
    needles |= seen.get("ids", set())
    con = open_db(db)
    ok = scan_tables(con, say) and ok
    n = con.execute("SELECT source, kind, COUNT(*) FROM items GROUP BY 1, 2").fetchall()
    say("items by source: " + "; ".join(f"{s} {k} {c}" for s, k, c in n))
    pl = con.execute("SELECT confidence, COUNT(*) FROM item_places GROUP BY 1").fetchall()
    say("places by confidence: " + "; ".join(f"{c} {k}" for c, k in pl))
    cn = con.execute("SELECT kind, source, SUM(items), SUM(people), COUNT(DISTINCT race_id) FROM counts "
                     "GROUP BY 1, 2").fetchall()
    say("counts: " + "; ".join(f"{k} {s}: {i} items, {p} people, {r} races" for k, s, i, p, r in cn))
    con.close()
    del seen
    # A control first: made-up traces of the same shapes (never a real account's), written to a file in the scratch
    # folder, must be found, or a clean result below would mean nothing.
    import random
    rnd = random.Random()
    fake = {"did:plc:" + "".join(rnd.choice("abcdefghijklmnopqrstuvwxyz234567") for _ in range(24)),
            "zz" + "".join(rnd.choice("abcdefghijklmnopqrstuvwxyz234567") for _ in range(11)),
            "madeup-" + "".join(rnd.choice("abcdefghij") for _ in range(8)) + ".bsky.social",
            "madeup_" + "".join(rnd.choice("abcdefghij") for _ in range(6)) + "@mastodon.example",
            str(rnd.randrange(10 ** 17, 10 ** 18))}
    control_dir = os.path.join(os.path.dirname(os.path.abspath(db)), "privacy_control")
    os.makedirs(control_dir, exist_ok=True)
    ctl_ok = True
    for i, f in enumerate(sorted(fake)):
        path = os.path.join(control_dir, f"control{i}.txt")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(f"something before {f} and after\n")
        found = not privacy_scan({f}, time.time() - 5, roots=[control_dir], say=lambda s: None)
        os.remove(path)
        ctl_ok = ctl_ok and found
    say(("PASS" if ctl_ok else "FAIL") + " the scan finds made-up traces of each shape (DID, record key, handle, "
                                         "Mastodon address, number id) planted in a file")
    ok = ctl_ok and ok
    ok = privacy_scan(needles, since, say=say, names=names) and ok
    needles.clear()
    names.clear()
    return ok


def main(argv):
    ap = argparse.ArgumentParser(prog="geotag")
    ap.add_argument("cmd", choices=["check", "place", "sample", "scan"])
    ap.add_argument("text", nargs="?")
    ap.add_argument("--state")
    ap.add_argument("--seconds", type=int, default=60)
    ap.add_argument("--db")
    a = ap.parse_args(argv)
    if a.cmd == "check":
        return 0 if run_checks(a.db) else 1
    if a.cmd == "place":
        for p in placer().place(a.text or "", a.state):
            print(json.dumps(p))
        return 0
    if a.cmd == "scan":
        con = open_db(a.db) if a.db else open_db()
        r = scan_tables(con)
        con.close()
        return 0 if r else 1
    return 0 if sample(a.seconds, a.db, say=lambda s: print(s, flush=True)) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
