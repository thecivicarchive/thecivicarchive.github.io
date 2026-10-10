"""election/store.py - the results database, election_2026.sqlite (ARCHITECTURE.md 2.2).

Official counts only, as each state's office posts them, each with the time of the file it came from. A reader turns
one fetched or hand-saved file (or one set of files saved together) into a "reading" (the shape is described at
`record`); the store checks it and writes only the numbers that changed since the last good snapshot, so every night
can be replayed in order. No count is ever edited by hand.

Tables (one row per ...):
  elections    state and election
  feeds        a state's feed: family, address pattern, status, approval, last success and failure
  snapshots    a file (or set of files) read: times, version, SHA-256, raw path, status, rows, note
  contests     a contest in a feed, tied to the ballot databases' race id
  choices      a candidate line, tied to the ballot database's candidate (race id plus name as filed)
  units        a reporting unit: precinct, county, town, parish, ward, or "all" (the whole contest)
  counts       a changed number: snapshot, race, unit, choice, vote type, votes
  reporting    a changed status: snapshot, race, unit, units in, units in all, ballots, registered
  checks       a check run on a snapshot: name, passed, detail
  certified    a certified figure, after the canvass
  latest_counts, latest_reporting   the newest good value of each number (a cache; `rebuild_latest` remakes it
               from counts and reporting)

Snapshot status: ok, same (the file had not changed), held (a check failed: the last good figures stay), failed (no
file), test (before the state's first poll closing: never published), refused (the host refused).

Checks: units add up to the source's own totals; units in never exceed units in all; every contest in the file is
matched or listed; a fall in a candidate's votes is flagged (corrections happen), never refused.

    python -m election.store --selftest
"""

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sqlite3
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(HERE, "election_2026.sqlite")
ELECTION = "2026-11-03"
VOTE_TYPES = ("total", "election_day", "early", "mail", "absentee", "provisional", "other")
HARD = ("structure", "units_add_up", "units_in_le_all")        # a failure holds the snapshot
STATUSES = ("ok", "same", "held", "failed", "test", "refused")

SCHEMA = """
CREATE TABLE IF NOT EXISTS elections (election_id TEXT NOT NULL, state TEXT NOT NULL, kind TEXT, date TEXT, certified_on TEXT,
  certifying_body TEXT, note TEXT, PRIMARY KEY (election_id, state));
CREATE TABLE IF NOT EXISTS feeds (state TEXT NOT NULL, feed_id TEXT NOT NULL, family TEXT, address_pattern TEXT, status TEXT,
  approved INTEGER NOT NULL DEFAULT 0, last_ok TEXT, last_failure TEXT, failures_in_a_row INTEGER NOT NULL DEFAULT 0, why_stopped TEXT,
  vote_type_words TEXT, PRIMARY KEY (state, feed_id));
CREATE TABLE IF NOT EXISTS snapshots (snapshot_id INTEGER PRIMARY KEY, state TEXT NOT NULL, feed_id TEXT NOT NULL, fetched_at TEXT NOT NULL,
  source_time TEXT, source_version TEXT, sha256 TEXT, raw_path TEXT, status TEXT NOT NULL, rows INTEGER, note TEXT);
CREATE INDEX IF NOT EXISTS idx_snapshots_feed ON snapshots (state, feed_id, snapshot_id);
CREATE TABLE IF NOT EXISTS contests (race_id TEXT PRIMARY KEY, state TEXT NOT NULL, feed_key TEXT, office TEXT, level TEXT, district TEXT,
  seats INTEGER NOT NULL DEFAULT 1, decision_rule TEXT NOT NULL DEFAULT 'plurality', ranked_choice INTEGER NOT NULL DEFAULT 0,
  unit_kind TEXT, units_all INTEGER);
CREATE TABLE IF NOT EXISTS choices (race_id TEXT NOT NULL, choice_key TEXT NOT NULL, name TEXT NOT NULL, party TEXT,
  ballot_race_id TEXT, ballot_name TEXT, write_in INTEGER NOT NULL DEFAULT 0, ord INTEGER, PRIMARY KEY (race_id, choice_key));
CREATE TABLE IF NOT EXISTS units (state TEXT NOT NULL, unit_id TEXT NOT NULL, kind TEXT NOT NULL, name TEXT, parent TEXT, map_id TEXT,
  PRIMARY KEY (state, unit_id));
CREATE TABLE IF NOT EXISTS counts (snapshot_id INTEGER NOT NULL, race_id TEXT NOT NULL, unit_id TEXT NOT NULL, choice_key TEXT NOT NULL,
  vote_type TEXT NOT NULL DEFAULT 'total', votes INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS idx_counts_race ON counts (race_id, unit_id, choice_key, vote_type, snapshot_id);
CREATE TABLE IF NOT EXISTS reporting (snapshot_id INTEGER NOT NULL, race_id TEXT NOT NULL, unit_id TEXT NOT NULL, units_in INTEGER,
  units_all INTEGER, ballots INTEGER, registered INTEGER);
CREATE INDEX IF NOT EXISTS idx_reporting_race ON reporting (race_id, unit_id, snapshot_id);
CREATE TABLE IF NOT EXISTS checks (snapshot_id INTEGER NOT NULL, check_name TEXT NOT NULL, passed INTEGER NOT NULL, detail TEXT);
CREATE TABLE IF NOT EXISTS certified (race_id TEXT NOT NULL, choice_key TEXT NOT NULL, votes INTEGER NOT NULL, source TEXT, date TEXT,
  PRIMARY KEY (race_id, choice_key));
CREATE TABLE IF NOT EXISTS latest_counts (race_id TEXT NOT NULL, unit_id TEXT NOT NULL, choice_key TEXT NOT NULL, vote_type TEXT NOT NULL,
  votes INTEGER NOT NULL, snapshot_id INTEGER NOT NULL, PRIMARY KEY (race_id, unit_id, choice_key, vote_type));
CREATE TABLE IF NOT EXISTS latest_reporting (race_id TEXT NOT NULL, unit_id TEXT NOT NULL, units_in INTEGER, units_all INTEGER,
  ballots INTEGER, registered INTEGER, snapshot_id INTEGER NOT NULL, PRIMARY KEY (race_id, unit_id));
"""


def utcnow():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def connect(path=DB):
    con = sqlite3.connect(path)
    con.execute("PRAGMA journal_mode=WAL") if path != ":memory:" else None
    con.executescript(SCHEMA)
    return con


def sha256_bytes(*blobs):
    h = hashlib.sha256()
    for b in blobs:
        h.update(b)
    return h.hexdigest()


# ---------------------------------------------------------------------------------------------- feeds and elections

def ensure_election(con, state, election_id=ELECTION, kind="general", date=None, certifying_body=None, certified_on=None, note=None):
    with con:
        con.execute("INSERT INTO elections (election_id, state, kind, date, certified_on, certifying_body, note) VALUES (?,?,?,?,?,?,?) "
                    "ON CONFLICT (election_id, state) DO UPDATE SET kind=excluded.kind, date=excluded.date, "
                    "certified_on=COALESCE(excluded.certified_on, certified_on), certifying_body=excluded.certifying_body, note=excluded.note",
                    (election_id, state, kind, date or election_id, certified_on, certifying_body, note))


def ensure_feed(con, state, feed_id, family, address_pattern, status, approved=True, vote_type_words=None):
    with con:
        con.execute("INSERT INTO feeds (state, feed_id, family, address_pattern, status, approved, vote_type_words) VALUES (?,?,?,?,?,?,?) "
                    "ON CONFLICT (state, feed_id) DO UPDATE SET family=excluded.family, address_pattern=excluded.address_pattern, "
                    "status=excluded.status, approved=excluded.approved, vote_type_words=excluded.vote_type_words",
                    (state, feed_id, family, address_pattern, status, 1 if approved else 0,
                     json.dumps(vote_type_words) if vote_type_words else None))


def feed_outcome(con, state, feed_id, ok, why=None):
    """After each try: a success clears the failure count; a failure adds one (three in a row: the page says the
    state's site has not answered since the first)."""
    with con:
        if ok:
            con.execute("UPDATE feeds SET last_ok=?, failures_in_a_row=0, why_stopped=NULL WHERE state=? AND feed_id=?", (utcnow(), state, feed_id))
        else:
            con.execute("UPDATE feeds SET last_failure=?, failures_in_a_row=failures_in_a_row+1, why_stopped=COALESCE(?, why_stopped) "
                        "WHERE state=? AND feed_id=?", (utcnow(), why, state, feed_id))


# ---------------------------------------------------------------------------------------------- snapshots

def last_snapshot(con, state, feed_id, status=None):
    q = "SELECT snapshot_id, sha256, status, source_time, fetched_at FROM snapshots WHERE state=? AND feed_id=?"
    args = [state, feed_id]
    if status:
        q += " AND status=?"
        args.append(status)
    return con.execute(q + " ORDER BY snapshot_id DESC LIMIT 1", args).fetchone()


def begin_snapshot(con, state, feed_id, sha256, raw_path=None, source_time=None, source_version=None, fetched_at=None, note=None, test=False):
    """(snapshot id, status). When the SHA-256 equals the last snapshot's that was read (ok, held or test), the new
    snapshot is 'same' and nothing more need be read."""
    prev = con.execute("SELECT sha256 FROM snapshots WHERE state=? AND feed_id=? AND status IN ('ok','held','test') "
                       "ORDER BY snapshot_id DESC LIMIT 1", (state, feed_id)).fetchone()
    status = "same" if prev and prev[0] == sha256 else ("test" if test else "reading")
    with con:
        cur = con.execute("INSERT INTO snapshots (state, feed_id, fetched_at, source_time, source_version, sha256, raw_path, status, rows, note) "
                          "VALUES (?,?,?,?,?,?,?,?,?,?)", (state, feed_id, fetched_at or utcnow(), source_time, source_version, sha256,
                                                           raw_path, status, None, note))
    return cur.lastrowid, status


def end_snapshot(con, snapshot_id, status, rows=None, note=None):
    assert status in STATUSES, status
    with con:
        con.execute("UPDATE snapshots SET status=?, rows=COALESCE(?, rows), note=COALESCE(?, note) WHERE snapshot_id=?",
                    (status, rows, note, snapshot_id))


def failed_snapshot(con, state, feed_id, status, note):
    """A try that produced no file: 'failed' or 'refused'."""
    sid, _ = begin_snapshot(con, state, feed_id, sha256=None, note=note)
    end_snapshot(con, sid, status, rows=0, note=note)
    return sid


# ---------------------------------------------------------------------------------------------- checking a reading

def run_checks(con, reading):
    """[(check, passed, detail)] for a reading, before anything is written.

    A reading is a dict:
      state, feed, source_time, source_version
      contests: [ {race_id, key, office, level, district, seats, rule, rcv, unit_kind, units_all,
                   choices:   [{key, name, party, ballot_name, write_in, order}],
                   units:     [{id, kind, name, parent, map_id}],
                   rows:      [{unit, choice, type, votes}]           the source's numbers, one per unit, choice and type
                   reporting: [{unit, in, all, ballots, registered}]
                   stated:    [{unit, total}]                          the source's own total of a unit (all choices)
                   controls:  [{choice, votes, in, from}]              the source's own contest totals, to compare with
                                                                       the sum of its units when as many units are in
                 } ]
      unmatched: [ {key, office, why} ]   contests in the file not tied to a race (listed, never shown)
      problems:  [ str ]                  the file's layout did not fit (holds the snapshot)
    """
    out = []
    probs = reading.get("problems") or []
    out.append(("structure", not probs, "; ".join(probs[:20]) or f"{len(reading.get('contests', []))} contests read"))

    bad_sum, bad_ctl, not_compared = [], [], 0
    bad_in = []
    for c in reading.get("contests", []):
        sums = {}
        for r in c.get("rows", []):
            if r.get("type", "total") == "total":
                sums[r["unit"]] = sums.get(r["unit"], 0) + int(r["votes"])
        for s in c.get("stated", []):
            if s.get("total") is not None and sums.get(s["unit"], 0) != int(s["total"]):
                bad_sum.append(f"{c['race_id']} unit {s['unit']}: candidates {sums.get(s['unit'], 0):,} against the file's total {int(s['total']):,}")
        unit_kind = {u["id"]: u["kind"] for u in c.get("units", [])}
        rep = {r["unit"]: r for r in c.get("reporting", [])}
        for r in c.get("reporting", []):
            if r.get("in") is not None and r.get("all") is not None and int(r["in"]) > int(r["all"]):
                bad_in.append(f"{c['race_id']} unit {r['unit']}: {r['in']} in of {r['all']}")
        if c.get("controls"):
            small = {u for u, k in unit_kind.items() if k == "precinct"}
            if small:
                units_in = sum(1 for u in small if rep.get(u, {}).get("in"))
                by_choice = {}
                for r in c.get("rows", []):
                    if r["unit"] in small and r.get("type", "total") == "total":
                        by_choice[r["choice"]] = by_choice.get(r["choice"], 0) + int(r["votes"])
                for ctl in c["controls"]:
                    if ctl.get("in") is not None and int(ctl["in"]) != units_in:
                        not_compared += 1           # the two files were saved at different moments for this contest
                        continue
                    if by_choice.get(ctl["choice"], 0) != int(ctl["votes"]):
                        bad_ctl.append(f"{c['race_id']} {ctl['choice']}: precincts add to {by_choice.get(ctl['choice'], 0):,}, "
                                       f"the {ctl.get('from') or 'summary'} says {int(ctl['votes']):,}")
    detail = "; ".join((bad_sum + bad_ctl)[:12])
    if not_compared:
        detail = (detail + "; " if detail else "") + (f"{not_compared} contest totals not compared: the files were saved when "
                                                       f"different numbers of precincts were in")
    out.append(("units_add_up", not (bad_sum or bad_ctl), detail or "every unit adds up to the file's own totals"))
    out.append(("units_in_le_all", not bad_in, "; ".join(bad_in[:12]) or "no unit reports more than it has"))
    um = reading.get("unmatched") or []
    out.append(("contests_matched", all(u.get("why") for u in um),
                f"{len(reading.get('contests', []))} matched; {len(um)} listed: " + "; ".join(f"{u.get('office')} ({u.get('why')})" for u in um[:8])))
    falls = []
    for c in reading.get("contests", []):
        for r in c.get("rows", []):
            old = con.execute("SELECT votes FROM latest_counts WHERE race_id=? AND unit_id=? AND choice_key=? AND vote_type=?",
                              (c["race_id"], r["unit"], r["choice"], r.get("type", "total"))).fetchone()
            if old and int(r["votes"]) < old[0]:
                falls.append(f"{c['race_id']} {r['unit']} {r['choice']}: {old[0]:,} to {int(r['votes']):,}")
    out.append(("fall_flag", not falls, (f"{len(falls)} falls (a correction; flagged, not refused): " + "; ".join(falls[:8])) if falls
                else "no candidate's votes fell"))
    return out


def record(con, snapshot_id, reading):
    """Checks the reading and, when every hard check passes, writes contests, choices, units and only the numbers that
    changed. Returns (status, checks). A held snapshot writes nothing but its checks."""
    checks = run_checks(con, reading)
    with con:
        con.executemany("INSERT INTO checks (snapshot_id, check_name, passed, detail) VALUES (?,?,?,?)",
                        [(snapshot_id, n, 1 if p else 0, d) for n, p, d in checks])
    if any(not p for n, p, _d in checks if n in HARD):
        end_snapshot(con, snapshot_id, "held", rows=0, note="a check failed; the last good figures stay")
        return "held", checks
    state = reading["state"]
    changed = 0
    with con:
        for c in reading.get("contests", []):
            rid = c["race_id"]
            con.execute("INSERT INTO contests (race_id, state, feed_key, office, level, district, seats, decision_rule, ranked_choice, unit_kind, units_all) "
                        "VALUES (?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT (race_id) DO UPDATE SET feed_key=excluded.feed_key, office=excluded.office, "
                        "level=excluded.level, district=excluded.district, seats=excluded.seats, decision_rule=excluded.decision_rule, "
                        "ranked_choice=excluded.ranked_choice, unit_kind=excluded.unit_kind, units_all=COALESCE(excluded.units_all, units_all)",
                        (rid, state, c.get("key"), c.get("office"), c.get("level"), c.get("district"), int(c.get("seats") or 1),
                         c.get("rule") or "plurality", 1 if c.get("rcv") else 0, c.get("unit_kind"), c.get("units_all")))
            for ch in c.get("choices", []):
                con.execute("INSERT INTO choices (race_id, choice_key, name, party, ballot_race_id, ballot_name, write_in, ord) VALUES (?,?,?,?,?,?,?,?) "
                            "ON CONFLICT (race_id, choice_key) DO UPDATE SET name=excluded.name, party=excluded.party, "
                            "ballot_race_id=excluded.ballot_race_id, ballot_name=excluded.ballot_name, write_in=excluded.write_in, ord=excluded.ord",
                            (rid, ch["key"], ch["name"], ch.get("party"), rid if ch.get("ballot_name") else None, ch.get("ballot_name"),
                             1 if ch.get("write_in") else 0, ch.get("order")))
            for u in c.get("units", []):
                con.execute("INSERT INTO units (state, unit_id, kind, name, parent, map_id) VALUES (?,?,?,?,?,?) ON CONFLICT (state, unit_id) "
                            "DO UPDATE SET kind=excluded.kind, name=COALESCE(excluded.name, name), parent=COALESCE(excluded.parent, parent), "
                            "map_id=COALESCE(excluded.map_id, map_id)", (state, u["id"], u["kind"], u.get("name"), u.get("parent"), u.get("map_id")))
            for r in c.get("rows", []):
                vt = r.get("type", "total")
                v = int(r["votes"])
                old = con.execute("SELECT votes FROM latest_counts WHERE race_id=? AND unit_id=? AND choice_key=? AND vote_type=?",
                                  (rid, r["unit"], r["choice"], vt)).fetchone()
                if old is None or old[0] != v:
                    con.execute("INSERT INTO counts (snapshot_id, race_id, unit_id, choice_key, vote_type, votes) VALUES (?,?,?,?,?,?)",
                                (snapshot_id, rid, r["unit"], r["choice"], vt, v))
                    con.execute("INSERT OR REPLACE INTO latest_counts VALUES (?,?,?,?,?,?)", (rid, r["unit"], r["choice"], vt, v, snapshot_id))
                    changed += 1
            for r in c.get("reporting", []):
                new = (r.get("in"), r.get("all"), r.get("ballots"), r.get("registered"))
                old = con.execute("SELECT units_in, units_all, ballots, registered FROM latest_reporting WHERE race_id=? AND unit_id=?",
                                  (rid, r["unit"])).fetchone()
                if old is None or tuple(old) != new:
                    con.execute("INSERT INTO reporting (snapshot_id, race_id, unit_id, units_in, units_all, ballots, registered) VALUES (?,?,?,?,?,?,?)",
                                (snapshot_id, rid, r["unit"]) + new)
                    con.execute("INSERT OR REPLACE INTO latest_reporting VALUES (?,?,?,?,?,?,?)", (rid, r["unit"]) + new + (snapshot_id,))
                    changed += 1
    end_snapshot(con, snapshot_id, "ok", rows=changed)
    return "ok", checks


def rebuild_latest(con):
    """Remakes the latest_* caches from the counts and reporting logs (good snapshots only)."""
    with con:
        con.execute("DELETE FROM latest_counts")
        con.execute("DELETE FROM latest_reporting")
        con.execute("INSERT INTO latest_counts SELECT c.race_id, c.unit_id, c.choice_key, c.vote_type, c.votes, c.snapshot_id FROM counts c "
                    "JOIN (SELECT race_id, unit_id, choice_key, vote_type, MAX(snapshot_id) m FROM counts GROUP BY 1,2,3,4) x "
                    "ON x.race_id=c.race_id AND x.unit_id=c.unit_id AND x.choice_key=c.choice_key AND x.vote_type=c.vote_type AND x.m=c.snapshot_id")
        con.execute("INSERT INTO latest_reporting SELECT r.race_id, r.unit_id, r.units_in, r.units_all, r.ballots, r.registered, r.snapshot_id "
                    "FROM reporting r JOIN (SELECT race_id, unit_id, MAX(snapshot_id) m FROM reporting GROUP BY 1,2) x "
                    "ON x.race_id=r.race_id AND x.unit_id=r.unit_id AND x.m=r.snapshot_id")


def add_certified(con, race_id, figures, source, date):
    """figures: {choice key: votes}, from the certifying body's own document."""
    with con:
        con.executemany("INSERT OR REPLACE INTO certified (race_id, choice_key, votes, source, date) VALUES (?,?,?,?,?)",
                        [(race_id, k, int(v), source, date) for k, v in figures.items()])


# ---------------------------------------------------------------------------------------------- what the pages read

def _snap_times(con):
    return {sid: (st or fa) for sid, st, fa in con.execute("SELECT snapshot_id, source_time, fetched_at FROM snapshots")}


# The published files are written short (ARCHITECTURE.md 2.6's budgets: a state's file 800 KB, a county's 150 KB). Nothing a
# page shows is left out: what is dropped is what the page puts back by a fixed rule, and expand_page / county_rows below
# put it back the same way (the tests check that the short and the long forms agree).
#   - race ids are written without the prefix every one of them shares ("pre": "2026-MN-");
#   - a race's "t" is left off when it equals the file's "at";
#   - a line's choice key is written "" when it is the line's own name made into a key (slug below);
#   - a line's trailing items are left off when they hold their usual value: the name as filed when it is the name as
#     printed (or, on a write-in line, when there is none), the write-in mark when 0, the party when there is none; a
#     line tied to no candidate on the list has 0 as its name as filed;
#   - a county's figures in a race are one list, [in, all, votes ...];
#   - a county's precinct rows are kept in two files, the judges apart (county_part), and race by race: the precincts
#     that have reported, by their place in the file's list of precincts, then their votes one after another.
COUNTY_PARTS = ("", "court")            # "" = 27053.json, every contest but the judges; "court" = 27053-court.json


def slug(name):
    """A line's own name made into a key: letters and digits, lower case, accents set aside, runs of anything else as one
    hyphen, at most 48 characters ("WRITE-IN" -> "write-in")."""
    import unicodedata
    s = "".join(ch for ch in unicodedata.normalize("NFKD", str(name or "")) if not unicodedata.combining(ch)).lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:48] or "unnamed"


def county_part(level):
    """Which of a county's two precinct files a race of this level is in."""
    return "court" if level == "court" else ""


def county_file(code, county_unit, part=""):
    """The one name of a county's precinct file inside a snapshot folder: <state code>/c/<state FIPS + county FIPS>.json,
    and -court before .json for the judges ("mn/c/27053.json", "mn/c/27053-court.json")."""
    if not re.fullmatch(r"\d{5}", str(county_unit)) or part not in COUNTY_PARTS:
        raise ValueError(f"a county file is named by its five-digit county unit and a part in {COUNTY_PARTS}: {county_unit!r}, {part!r}")
    return f"{code.lower()}/c/{county_unit}{'-' + part if part else ''}.json"


def _prefix(ids):
    pre = os.path.commonprefix(list(ids)) if ids else ""
    return pre[:pre.rfind("-") + 1] if "-" in pre else ""


def _short_line(c):
    key, name, party, wi, filed = (list(c) + [None] * 5)[:5]
    wi = 1 if wi else 0
    out = ["" if key == slug(name) else key, name, party, wi]
    if (not wi and filed == name) or (wi and filed is None):      # the usual value: left off
        if not wi:
            out.pop()
            if party is None:
                out.pop()
    else:
        out.append(0 if filed is None else filed)
    return out


def _long_line(c):
    c = list(c)
    name = c[1]
    party = c[2] if len(c) > 2 else None
    wi = 1 if len(c) > 3 and c[3] else 0
    if len(c) > 4:
        filed = None if c[4] == 0 else c[4]
    else:
        filed = None if wi else name
    return [c[0] or slug(name), name, party, wi, filed]


def compact_page(doc):
    """A state's file in its long form (page_json(..., compact=False)) written short, as published."""
    at = doc.get("at")
    pre = _prefix(doc.get("r") or {})
    out = {k: v for k, v in doc.items() if k != "r"}
    if pre:
        out["pre"] = pre
    out["r"] = {}
    for rid, e in (doc.get("r") or {}).items():
        s = {}
        if e.get("t") != at:
            s["t"] = e.get("t")
        for k in ("p", "ch", "v", "off", "k"):
            if k not in e:
                continue
            if k == "ch":
                s["ch"] = [_short_line(c) for c in e["ch"]]
            elif k == "k":
                s["k"] = {cu: [(ce.get("p") or [None, None])[0], (ce.get("p") or [None, None])[1]] + list(ce.get("v") or []) for cu, ce in e["k"].items()}
            else:
                s[k] = e[k]
        out["r"][rid[len(pre):]] = s
    return out


def expand_page(doc):
    """A published state's file back in its long form: what a page reads from it, item by item."""
    pre = doc.get("pre") or ""
    out = {k: v for k, v in doc.items() if k not in ("r", "pre")}
    out["r"] = {}
    for key, s in (doc.get("r") or {}).items():
        e = {"t": s.get("t", doc.get("at"))}
        for k in ("p", "ch", "v", "off", "k"):
            if k not in s:
                continue
            if k == "ch":
                e["ch"] = [_long_line(c) for c in s["ch"]]
            elif k == "k":
                e["k"] = {cu: {"p": None if ce[0] is None and ce[1] is None else [ce[0], ce[1]], "v": list(ce[2:])} for cu, ce in s["k"].items()}
            else:
                e[k] = s[k]
        out["r"][pre + key] = e
    return out


def page_json(con, state, compact=True):
    """The state's file in a snapshot folder: every contest the state's feed carries, its totals, reporting and time,
    the official flag, and by county where reported. Choices are listed once per race in ballot order; votes follow
    that order. Published short (compact_page); its long form:

    {"v":1, "state", "at": the newest good file's time,
     "r": {race: {"t": time of the newest figure, "p": [units in, units in all],
                  "ch": [[key, name as printed, party as printed, write-in, name as filed on the list or None], ...],
                  "v": [votes in choice order], "off": 1 when certified, "k": {county unit: {"p": [in, all], "v": [...]}}}}}"""
    times = _snap_times(con)
    newest = con.execute("SELECT MAX(snapshot_id) FROM snapshots WHERE state=? AND status='ok'", (state,)).fetchone()[0]
    out = {"v": 1, "state": state, "at": times.get(newest), "r": {}}
    kinds = {u: k for u, k in con.execute("SELECT unit_id, kind FROM units WHERE state=?", (state,))}
    cert = {}
    for rid, ck, v in con.execute("SELECT c.race_id, c.choice_key, c.votes FROM certified c JOIN contests t USING (race_id) WHERE t.state=?", (state,)):
        cert.setdefault(rid, {})[ck] = v
    for (rid,) in con.execute("SELECT race_id FROM contests WHERE state=? ORDER BY race_id", (state,)).fetchall():
        chs = con.execute("SELECT choice_key, name, party, write_in, ballot_name FROM choices WHERE race_id=? ORDER BY write_in, COALESCE(ord, 999), name",
                          (rid,)).fetchall()
        order = [c[0] for c in chs]
        votes = {}
        last = 0
        for unit, ck, v, sid in con.execute("SELECT unit_id, choice_key, votes, snapshot_id FROM latest_counts WHERE race_id=? AND vote_type='total'", (rid,)):
            votes.setdefault(unit, {})[ck] = v
            last = max(last, sid)
        rep = {}
        for unit, i, a, sid in con.execute("SELECT unit_id, units_in, units_all, snapshot_id FROM latest_reporting WHERE race_id=?", (rid,)):
            rep[unit] = [i, a]
            last = max(last, sid)
        e = {"t": times.get(last), "ch": [list(c) for c in chs]}
        if rid in cert:
            e["v"], e["off"] = [cert[rid].get(k, 0) for k in order], 1
        elif "all" in votes:
            e["v"] = [votes["all"].get(k, 0) for k in order]
        else:
            e["v"] = [sum(v.get(k, 0) for u, v in votes.items() if kinds.get(u) == "precinct") for k in order]
        if "all" in rep:
            e["p"] = rep["all"]
        else:
            pr = [p for u, p in rep.items() if kinds.get(u) == "precinct"]
            if pr:
                e["p"] = [sum(p[0] or 0 for p in pr), sum(p[1] or 0 for p in pr)]
        counties = {u for u in votes if kinds.get(u) == "county"}
        if counties:
            e["k"] = {u: {"p": rep.get(u), "v": [votes[u].get(k, 0) for k in order]} for u in sorted(counties)}
        out["r"][rid] = e
    return compact_page(out) if compact else out


def _runs(idx):
    """Sorted whole numbers as runs: a number alone, or [first, last]."""
    out, i = [], 0
    while i < len(idx):
        j = i
        while j + 1 < len(idx) and idx[j + 1] == idx[j] + 1:
            j += 1
        out.append(idx[i] if i == j else [idx[i], idx[j]])
        i = j + 1
    return out


def encode_county(county_unit, part, at, units, rows):
    """One county's precinct file, as published. units: every precinct of the county (sorted); rows: {race id: {precinct:
    votes in the race's line order}}, holding only the precincts that have reported.

    {"v":1, "county": "27053", "part": "" or "court", "at": UTC, "u": [precinct ids], "races": [race ids],
     "r": [[[the reported precincts, by their place in u, as runs: 4 or [4, 9]], [votes: the race's lines for the first
            reported precinct, then for the next, ...]], ...]}      one entry for each race, in the order of races
    A precinct not listed for a race has not reported."""
    pos = {u: i for i, u in enumerate(units)}
    races = sorted(rows)
    r = []
    for rid in races:
        got = sorted((pos[u], v) for u, v in rows[rid].items() if u in pos)
        r.append([_runs([i for i, _v in got]), [n for _i, v in got for n in v]])
    return {"v": 1, "county": county_unit, "part": part, "at": at, "u": list(units), "races": races, "r": r}


def county_rows(doc, lines=None):
    """A published county file read back: {race id: {precinct: votes in the race's line order}}. lines: {race id: the number
    of lines} (from the state's file); without it, each race's votes are split evenly among its reported precincts."""
    out = {}
    for rid, (runs, votes) in zip(doc.get("races") or [], doc.get("r") or []):
        idx = []
        for x in runs:
            idx.extend(range(x[0], x[1] + 1) if isinstance(x, list) else [x])
        n = (lines or {}).get(rid) or (len(votes) // len(idx) if idx else 0)
        out[rid] = {doc["u"][i]: votes[k * n:(k + 1) * n] for k, i in enumerate(idx)}
    return out


def county_json(con, state, county_unit, part=""):
    """One county's precinct rows for one of its two files (county_part), as published (encode_county). A precinct's
    figures in a race are listed once its units in is more than 0. The race's line order is page_json's."""
    times = _snap_times(con)
    precincts = [u for (u,) in con.execute("SELECT unit_id FROM units WHERE state=? AND kind='precinct' AND parent=? ORDER BY unit_id",
                                            (state, county_unit))]
    pset = set(precincts)
    level = {rid: lv for rid, lv in con.execute("SELECT race_id, level FROM contests WHERE state=?", (state,))}
    rows, last, orders = {}, 0, {}
    rep = {}
    for rid, unit, i, sid in con.execute("SELECT race_id, unit_id, units_in, snapshot_id FROM latest_reporting WHERE unit_id IN "
                                         "(SELECT unit_id FROM units WHERE state=? AND kind='precinct' AND parent=?)", (state, county_unit)):
        rep[(rid, unit)] = (i, sid)
    q = ("SELECT race_id, unit_id, choice_key, votes, snapshot_id FROM latest_counts WHERE vote_type='total' AND unit_id IN "
         "(SELECT unit_id FROM units WHERE state=? AND kind='precinct' AND parent=?) ORDER BY race_id")
    for rid, unit, ck, v, sid in con.execute(q, (state, county_unit)):
        if unit not in pset or county_part(level.get(rid)) != part or not (rep.get((rid, unit)) or (0,))[0]:
            continue
        if rid not in orders:
            orders[rid] = [c for (c,) in con.execute("SELECT choice_key FROM choices WHERE race_id=? ORDER BY write_in, COALESCE(ord, 999), name", (rid,))]
        rows.setdefault(rid, {}).setdefault(unit, {})[ck] = v
        last = max(last, sid, rep[(rid, unit)][1])
    votes = {rid: {u: [got.get(k, 0) for k in orders[rid]] for u, got in us.items()} for rid, us in rows.items()}
    return encode_county(county_unit, part, times.get(last), precincts, votes)


def county_units(con, state):
    """Every county unit that has precincts: each has both its files in every snapshot, so that a page can tell "none in
    yet" from a file it could not fetch."""
    return [u for (u,) in con.execute("SELECT DISTINCT parent FROM units WHERE state=? AND kind='precinct' AND parent IS NOT NULL ORDER BY 1", (state,))]


# ---------------------------------------------------------------------------------------------- self-test

def selftest(say=print):
    """Builds a store in memory and runs a small night through it: a first file, an unchanged file, a file with
    changes and a correction, a file that does not add up (held), and the pages' JSON."""
    con = connect(":memory:")
    ensure_election(con, "ZZ", certifying_body="Test Canvassing Board")
    ensure_feed(con, "ZZ", "zz-test", "test", "fixture", "live")

    def reading(a_votes, b_votes, a_in, stated_a=None):
        pa, pb = "ZZ0001", "ZZ0002"
        rows = [{"unit": pa, "choice": "smith", "votes": a_votes[0]}, {"unit": pa, "choice": "jones", "votes": a_votes[1]},
                {"unit": pb, "choice": "smith", "votes": b_votes[0]}, {"unit": pb, "choice": "jones", "votes": b_votes[1]}]
        return {"state": "ZZ", "feed": "zz-test", "contests": [{
            "race_id": "2026-ZZ-T1", "key": "T1", "office": "Test Office", "level": "statewide", "seats": 1, "unit_kind": "precinct", "units_all": 2,
            "choices": [{"key": "smith", "name": "Pat Smith", "party": "A", "ballot_name": "Pat Smith", "order": 1},
                        {"key": "jones", "name": "Lee Jones", "party": "B", "ballot_name": "Lee Jones", "order": 2}],
            "units": [{"id": pa, "kind": "precinct", "name": "One", "parent": "Z001", "map_id": pa},
                      {"id": pb, "kind": "precinct", "name": "Two", "parent": "Z001", "map_id": pb}],
            "rows": rows,
            "reporting": [{"unit": pa, "in": a_in, "all": 1}, {"unit": pb, "in": 1, "all": 1}],
            "stated": [{"unit": pa, "total": stated_a if stated_a is not None else sum(a_votes)}, {"unit": pb, "total": sum(b_votes)}],
            "controls": [{"choice": "smith", "votes": a_votes[0] + b_votes[0], "in": a_in + 1, "from": "summary"}],
        }], "unmatched": [{"key": "X", "office": "Question 1", "why": "a ballot question, not a contest between people"}], "problems": []}

    ok = True

    def expect(cond, what):
        nonlocal ok
        say(f"      {'ok  ' if cond else 'FAIL'} {what}")
        ok = ok and bool(cond)

    sid, st = begin_snapshot(con, "ZZ", "zz-test", sha256_bytes(b"one"))
    expect(st == "reading", "a new file is read")
    st, _ = record(con, sid, reading((0, 0), (10, 5), 0))
    expect(st == "ok", "first file stored")
    n1 = con.execute("SELECT COUNT(*) FROM counts").fetchone()[0]
    expect(n1 == 4, f"four counts written ({n1})")
    sid, st = begin_snapshot(con, "ZZ", "zz-test", sha256_bytes(b"one"))
    expect(st == "same", "an unchanged file is 'same'")
    end_snapshot(con, sid, "same", rows=0)
    sid, st = begin_snapshot(con, "ZZ", "zz-test", sha256_bytes(b"two"))
    st, checks = record(con, sid, reading((7, 3), (9, 5), 1))
    expect(st == "ok", "second file stored")
    n2 = con.execute("SELECT COUNT(*) FROM counts WHERE snapshot_id=?", (sid,)).fetchone()[0]
    expect(n2 == 3, f"only the three changed numbers written ({n2})")
    flag = dict((n, (p, d)) for n, p, d in checks)["fall_flag"]
    expect(not flag[0] and "10 to 9" in flag[1], "a fall in votes is flagged")
    sid, st = begin_snapshot(con, "ZZ", "zz-test", sha256_bytes(b"three"))
    st, checks = record(con, sid, reading((8, 3), (9, 5), 1, stated_a=99))
    expect(st == "held", "a file that does not add up is held")
    expect(con.execute("SELECT COUNT(*) FROM counts WHERE snapshot_id=?", (sid,)).fetchone()[0] == 0, "a held file writes no counts")
    bad = reading((8, 3), (9, 5), 1)
    bad["contests"][0]["reporting"][0]["in"] = 5
    sid, st = begin_snapshot(con, "ZZ", "zz-test", sha256_bytes(b"four"))
    st, _ = record(con, sid, bad)
    expect(st == "held", "more units in than in all is held")
    pj = page_json(con, "ZZ")
    r = pj["r"]["T1"]
    expect(r["v"] == [16, 8] and r["p"] == [2, 2], f"page totals from the last good file ({r['v']}, {r['p']})")
    expect(r["ch"][0] == ["smith", "Pat Smith", "A"] and expand_page(pj) == page_json(con, "ZZ", compact=False),
           "the published file is written short and reads back whole")
    expect(page_json(con, "ZZ", compact=False)["r"]["2026-ZZ-T1"]["ch"][0][4] == "Pat Smith", "each line carries the name as filed")
    cj = county_json(con, "ZZ", "Z001")
    expect(county_rows(cj)["2026-ZZ-T1"] == {"ZZ0001": [7, 3], "ZZ0002": [9, 5]}, "county file carries precinct rows")
    expect(county_json(con, "ZZ", "Z001", "court")["races"] == [], "the judges' file holds the judges only")
    before = con.execute("SELECT * FROM latest_counts ORDER BY 1,2,3,4").fetchall()
    rebuild_latest(con)
    expect(before == con.execute("SELECT * FROM latest_counts ORDER BY 1,2,3,4").fetchall(), "the latest figures can be rebuilt from the log")
    add_certified(con, "2026-ZZ-T1", {"smith": 17, "jones": 8}, "Test Canvassing Board", "2026-11-19")
    r = page_json(con, "ZZ", compact=False)["r"]["2026-ZZ-T1"]
    expect(r.get("off") == 1 and r["v"] == [17, 8], "certified figures replace the count")
    return ok


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--db", default=DB)
    a = ap.parse_args(argv)
    if a.selftest:
        print("    results store self-test")
        good = selftest()
        print("    PASS" if good else "    FAIL")
        return 0 if good else 1
    con = connect(a.db)
    print(f"    {a.db}: " + ", ".join(f"{t} {con.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]:,}"
                                   for t in ("snapshots", "contests", "counts", "reporting")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
