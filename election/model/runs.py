"""election/model/runs.py - every model run kept as a version, and the files the pages read from them
(ARCHITECTURE.md 2.4, 2.6, 3.2; model.md 3.6). Owned by N16.

    python -m election.model.runs --list [--state mn]       the runs on file
    python -m election.model.runs --redo <run id>          redo a stored run from its stored inputs and seed; exact or not
    python -m election.model.runs --check [--state mn]     no 0 or 100 anywhere, nothing for an unopposed race, every stored
                                                           pre-election and election-night run redone exactly
    python -m election.model.runs --selftest               the store's arithmetic on a made-up run; touches no real table

WHAT IS KEPT (election_model_2026.sqlite; the features and run_inputs tables are election/model/__init__.py's)
  runs            one row a run: id, state, kind (pre, live, backtest, replay), method version, the SHA-256 of the model's
                  code, the random seed (from the run id), draws, start and end, the moment it stands for (as_of), the
                  rehearsal flag, the SHA-256 of its frame (every input the simulation read, kept whole in run_blobs),
                  Python's version (a redo on another version may differ in the last digit, and says so)
  run_inputs      one row an input of a run: its name, file or address, SHA-256, as of, kind (official, secondary, census,
                  derived, poll, prior, frame)
  run_blobs       the frames, gzipped canonical JSON, by SHA-256 (the same inputs are stored once)
  race_runs       one row a race and run, written only when the race's inputs changed since its last row (a new method
                  version counts as a change): status, seats, units counted, ballots, share counted, the expected total
                  votes (10th, 50th, 90th percentile), equal chances by the record, tested or not, the inputs' and outputs'
                  SHA-256
  candidate_runs  one row a candidate of such a race: the store's choice key, the name as filed, the chance of winning (of a
                  seat where several are elected), the median share, the 80 and 95 percent ranges
  backtests       one row a race (and candidate) of a backtest: what the model said before (or during) a past election and
                  what happened
  calibration     one row a measure of a backtest: Brier score, log loss, how often the ranges held, by scenario and group

A CHANCE IS NEVER 0 OR 1: a run stores (wins + 0.5) / (draws + 1), and the pages' files carry whole percents from 1 to
99 with a mark (">" over 99, "<" under 1), so no page can say 0% or 100% before the canvass.

THE SEED comes from the run id (SHA-256 of the id), so any run can be redone from its stored frame: `redo` loads the frame,
runs the kind's simulation (SIMULATORS) with the stored seed and draws, and compares every stored number.
"""

import argparse
import datetime as dt
import gzip
import hashlib
import importlib
import json
import math
import os
import platform
import re
import sqlite3
import sys

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from election.model import DB  # noqa: E402
from election.model import connect as _connect_base  # noqa: E402

RUNS_METHOD = "runs-1.1"                  # 1.1 (2026-10-10): the likely margin of the top two and the chance of no majority kept
KINDS = ("pre", "live", "backtest", "replay")
PUBLIC_KINDS = ("pre", "live")            # what the pages show; backtests and replays stay on #track
# family -> "module:function" taking (frame, seed, draws) and returning {"races": [race output, ...]}. A family is a run's
# kind, except that the night's runs of the other states (kind "live", method "us-live-...") are their own family:
# "live": Minnesota's night (live_model.py builds the frame, simulate.py draws it; N17).
# "live/us": every other state's night (night_us.py builds the frame, simulate_us.py draws it; N17b).
# A kept simulation file imports only runs.py, so a stored run is redone exactly with the code it was made with.
SIMULATORS = {"pre": "election.model.forecast:simulate", "live": "election.model.simulate:simulate",
              "live/us": "election.model.simulate_us:simulate"}
MODEL_FILES = {"pre": ("forecast.py", "runs.py"), "backtest": ("backtest.py", "forecast.py", "runs.py"),
               "live": ("simulate.py", "live_model.py", "blindspots.py", "runs.py"),
               "live/us": ("simulate_us.py", "night_us.py", "runs.py"),
               "replay": ("blindspots.py", "live_model.py", "simulate.py", "backtest.py", "forecast.py", "runs.py"),
               "replay/us": ("night_us.py", "simulate_us.py", "runs.py")}
US_NIGHT_PREFIX = "us-live"               # the method versions of the other states' night model


def family(kind, method=None):
    """The simulation family of a run: its kind, or "<kind>/us" for the other states' night model (its live runs and its
    replays), whose frames are drawn by simulate_us.py."""
    if kind in ("live", "replay") and str(method or "").startswith(US_NIGHT_PREFIX):
        return f"{kind}/us"
    return kind

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run        TEXT PRIMARY KEY,
    state      TEXT NOT NULL,          -- two letters, upper case
    kind       TEXT NOT NULL,          -- pre, live, backtest, replay
    method     TEXT NOT NULL,          -- the method version
    code_sha   TEXT NOT NULL,          -- SHA-256 of the model's code files
    seed       INTEGER NOT NULL,       -- from the run id
    draws      INTEGER NOT NULL,
    started    TEXT NOT NULL,          -- UTC
    ended      TEXT,
    as_of      TEXT,                   -- the moment the run stands for (UTC)
    rehearsal  INTEGER NOT NULL DEFAULT 0,
    frame_sha  TEXT,                   -- run_blobs key of every input the simulation read
    python     TEXT,
    races      INTEGER,                -- races the run looked at
    written    INTEGER,                -- races given a new row
    note       TEXT
);
CREATE TABLE IF NOT EXISTS run_blobs (
    sha256     TEXT PRIMARY KEY,
    kind       TEXT,
    bytes      BLOB NOT NULL,          -- gzipped canonical JSON
    size       INTEGER,
    created    TEXT
);
CREATE TABLE IF NOT EXISTS race_runs (
    run        TEXT NOT NULL,
    race       TEXT NOT NULL,
    state      TEXT NOT NULL,
    status     TEXT NOT NULL,          -- pre, counting, done, official, unopposed, no-candidates, not-modelled
    seats      INTEGER,
    units_in   INTEGER,
    units_all  INTEGER,
    ballots    INTEGER,
    share_counted REAL,                -- of the expected vote; 0 before results
    exp_lo     REAL,                   -- expected total votes in the race: 10th, 50th, 90th percentile
    exp_mid    REAL,
    exp_hi     REAL,
    equal      INTEGER,                -- 1: nothing on the record separates the candidates
    tested     TEXT,                   -- which backtest covers this kind of race, or "untested: <why>"
    in_sha     TEXT,
    out_sha    TEXT,
    note       TEXT,
    mg_a       TEXT,                   -- the likely margin of the top two: the favourite's choice key
    mg_b       TEXT,                   --   and the runner-up's
    mg_med     REAL,                   --   the favourite's share less the runner-up's: median, 80 and 95 percent ranges
    mg_lo80    REAL,
    mg_hi80    REAL,
    mg_lo95    REAL,
    mg_hi95    REAL,
    ro         REAL,                   -- where the law asks for more than half: the chance no candidate passes half
    PRIMARY KEY (run, race)
);
CREATE INDEX IF NOT EXISTS race_runs_race ON race_runs (race, run);
CREATE INDEX IF NOT EXISTS race_runs_state ON race_runs (state, run);
CREATE TABLE IF NOT EXISTS candidate_runs (
    run        TEXT NOT NULL,
    race       TEXT NOT NULL,
    choice     TEXT NOT NULL,          -- the results store's choice key
    name       TEXT,                   -- as filed
    chance     REAL,                   -- of winning (of a seat where several are elected); never 0 or 1
    median     REAL,                   -- share of the race's votes
    lo80       REAL,
    hi80       REAL,
    lo95       REAL,
    hi95       REAL,
    PRIMARY KEY (run, race, choice)
);
CREATE TABLE IF NOT EXISTS backtests (
    run        TEXT NOT NULL,          -- the backtest run
    scenario   TEXT NOT NULL,          -- oracle, pre, replay:<order>:<percent counted>
    year       INTEGER NOT NULL,
    race       TEXT NOT NULL,          -- the past contest's own id (2022-mnleg-12A, 2022-np-<office>-<place>)
    grp        TEXT NOT NULL,          -- the kind of race it is scored under
    choice     TEXT NOT NULL,          -- a party code or a candidate's key
    chance     REAL,
    median     REAL,
    lo80       REAL,
    hi80       REAL,
    lo95       REAL,
    hi95       REAL,
    actual     REAL,                   -- the share the official count gave
    won        INTEGER,
    base_inc   REAL,                   -- the plain rule "the incumbent wins" (NULL where no incumbent ran)
    base_last  REAL,                   -- the plain rule "last time repeats" (NULL where there is no last time)
    PRIMARY KEY (run, scenario, race, choice)
);
CREATE TABLE IF NOT EXISTS calibration (
    run        TEXT NOT NULL,
    scenario   TEXT NOT NULL,
    grp        TEXT NOT NULL,
    measure    TEXT NOT NULL,
    value      REAL,
    n          INTEGER,
    note       TEXT,
    PRIMARY KEY (run, scenario, grp, measure)
);
"""


# ============================================================================================== the database

ADDED_COLUMNS = (("race_runs", "mg_a", "TEXT"), ("race_runs", "mg_b", "TEXT"), ("race_runs", "mg_med", "REAL"),
                 ("race_runs", "mg_lo80", "REAL"), ("race_runs", "mg_hi80", "REAL"), ("race_runs", "mg_lo95", "REAL"),
                 ("race_runs", "mg_hi95", "REAL"), ("race_runs", "ro", "REAL"))


def connect(db=DB):
    con = _connect_base(db)
    con.execute("PRAGMA busy_timeout = 30000")
    con.executescript(SCHEMA)
    # a database made before a column was added gets it (no row is changed: the column is empty for older runs)
    have = {}
    for table, col, typ in ADDED_COLUMNS:
        if table not in have:
            have[table] = {r[1] for r in con.execute(f"PRAGMA table_info({table})")}
        if col not in have[table]:
            con.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typ}")
            have[table].add(col)
    return con


def now_utc():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0)


def iso(t):
    if t is None:
        return None
    if isinstance(t, str):
        return t
    if t.tzinfo is None:
        t = t.replace(tzinfo=dt.timezone.utc)
    return t.astimezone(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def canonical(obj):
    """The one way a frame is written, so the same inputs always give the same bytes and SHA-256."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def sha_text(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def code_files(kind):
    """{file name: its text} for the model's code files of this family of run (family())."""
    here = os.path.dirname(os.path.abspath(__file__))
    out = {}
    for name in MODEL_FILES.get(kind, ("forecast.py", "runs.py")):
        p = os.path.join(here, name)
        if os.path.exists(p):
            with open(p, "rb") as fh:
                out[name] = fh.read().decode("utf-8")
    return out


def code_sha(kind):
    """SHA-256 of the model's code for this family of run: the run_blobs key under which that code is kept whole."""
    return sha_text(canonical({"files": code_files(kind)}))


def keep_code(con, kind):
    """Keep the model's code for this family of run in run_blobs (once per version); returns its SHA-256."""
    return put_blob(con, {"files": code_files(kind)}, "code")


def load_code(con, sha, kind):
    """The simulation function of a stored code version: its runs.py and forecast.py (or the family's own files) read
    from run_blobs into fresh modules, the stored forecast.py importing the stored runs.py. None if not kept."""
    import types
    doc = get_blob(con, sha)
    if not doc or "files" not in doc:
        return None
    files = doc["files"]
    spec = SIMULATORS.get(kind)
    if not spec:
        return None
    modname, fn = spec.split(":")
    target = modname.rsplit(".", 1)[1] + ".py"
    if target not in files or "runs.py" not in files:
        return None
    saved = sys.modules.get("election.model.runs")
    try:
        mruns = types.ModuleType(f"election.model._kept_runs_{sha[:10]}")
        mruns.__file__ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "runs.py")
        exec(compile(files["runs.py"], f"<kept runs.py {sha[:10]}>", "exec"), mruns.__dict__)
        sys.modules["election.model.runs"] = mruns
        import election.model as pkg
        old_attr = getattr(pkg, "runs", None)
        pkg.runs = mruns
        try:
            mod = types.ModuleType(f"election.model._kept_{target[:-3]}_{sha[:10]}")
            mod.__file__ = os.path.join(os.path.dirname(os.path.abspath(__file__)), target)
            exec(compile(files[target], f"<kept {target} {sha[:10]}>", "exec"), mod.__dict__)
        finally:
            if old_attr is not None:
                pkg.runs = old_attr
        return getattr(mod, fn), mruns
    finally:
        if saved is not None:
            sys.modules["election.model.runs"] = saved


def seed_of(run_id):
    return int(hashlib.sha256(run_id.encode("utf-8")).hexdigest()[:15], 16)


def new_run_id(con, kind, state, when=None):
    """<kind>-<state>-<UTC time>, with -2, -3 ... when that second is taken."""
    stamp = iso(when or now_utc()).replace("-", "").replace(":", "")
    base = f"{kind}-{state.lower()}-{stamp}"
    rid, n = base, 1
    while con.execute("SELECT 1 FROM runs WHERE run = ?", (rid,)).fetchone():
        n += 1
        rid = f"{base}-{n}"
    return rid


def put_blob(con, obj, kind="frame"):
    """Keep an object whole (gzipped canonical JSON); returns its SHA-256. Stored once whatever the number of runs."""
    text = canonical(obj)
    sha = sha_text(text)
    if not con.execute("SELECT 1 FROM run_blobs WHERE sha256 = ?", (sha,)).fetchone():
        data = gzip.compress(text.encode("utf-8"), compresslevel=6, mtime=0)
        con.execute("INSERT INTO run_blobs (sha256, kind, bytes, size, created) VALUES (?,?,?,?,?)",
                    (sha, kind, data, len(text), iso(now_utc())))
    return sha


def get_blob(con, sha):
    row = con.execute("SELECT bytes FROM run_blobs WHERE sha256 = ?", (sha,)).fetchone()
    if not row:
        return None
    text = gzip.decompress(row[0]).decode("utf-8")
    if sha_text(text) != sha:
        raise ValueError(f"the stored blob {sha[:12]} does not match its own SHA-256")
    return json.loads(text)


# ============================================================================================== a chance as it may be shown

def stored_chance(wins, draws):
    """(wins + 0.5) / (draws + 1): never 0 and never 1, so nothing stored can read as certain."""
    return (wins + 0.5) / (draws + 1)


def shown_chance(p):
    """A chance as the pages print it: a whole percent from 1 to 99, and ">" (over 99%) or "<" (under 1%) beyond."""
    if p is None:
        return None, ""
    if p >= 0.995:
        return 99, ">"
    if p < 0.005:
        return 1, "<"
    return min(99, max(1, int(math.floor(p * 100 + 0.5)))), ""


def tenths(x):
    """A share as tenths of a percent (52.4% -> 524)."""
    return None if x is None else int(math.floor(x * 1000 + 0.5))


def _q(s, qs):
    n = len(s)
    out = []
    for q in qs:
        pos = q * (n - 1)
        i = int(math.floor(pos))
        f = pos - i
        out.append(s[i] if i + 1 >= n else s[i] * (1 - f) + s[i + 1] * f)
    return out


def margin_of(cands, shares, wins):
    """The likely margin of the top two from a simulation's draws: {"a": the favourite's key, "b": the runner-up's,
    "q": [median, 10th, 90th, 2.5th, 97.5th percentile]} of the favourite's share less the runner-up's, draw by draw; the
    two named by their wins, then their middle share, then their names (the pages' own order). None for fewer than two."""
    n = len(cands)
    if n < 2 or not shares or not shares[0]:
        return None
    med = [_q(sorted(shares[k]), (0.5,))[0] for k in range(n)]
    order = sorted(range(n), key=lambda k: (-wins[k], -med[k], cands[k].get("name") or cands[k]["key"]))
    a, b = order[0], order[1]
    diff = sorted(x - y for x, y in zip(shares[a], shares[b]))
    return {"a": cands[a]["key"], "b": cands[b]["key"], "q": _q(diff, (0.5, 0.1, 0.9, 0.025, 0.975))}


def out_digest(race):
    """SHA-256 of a race's outputs as stored (status, seats, expected totals and every candidate's numbers; the likely
    margin of the top two and the chance of no majority where the run made them)."""
    keep = {k: race.get(k) for k in ("status", "seats", "equal", "units_in", "units_all", "ballots", "share_counted",
                                     "exp", "tested")}
    keep["cands"] = [[c["key"], c.get("chance"), c.get("median"), c.get("lo80"), c.get("hi80"), c.get("lo95"), c.get("hi95")]
                     for c in race.get("cands", [])]
    for k in ("mg", "ro"):              # only where present, so a run made before they existed keeps its digest
        if race.get(k) is not None:
            keep[k] = race[k]
    return sha_text(canonical(keep))


def margin_columns(race):
    """(mg_a, mg_b, mg_med, mg_lo80, mg_hi80, mg_lo95, mg_hi95) of a race's output, or Nones."""
    mg = race.get("mg") or {}
    q = list(mg.get("q") or []) + [None] * 5
    return (mg.get("a"), mg.get("b"), q[0], q[1], q[2], q[3], q[4]) if mg else (None,) * 7


# ============================================================================================== recording a run

def record_run(con, *, run, state, kind, method, seed, draws, started, as_of, frame, outputs, inputs, rehearsal=False,
               note=None, write_all=False):
    """Writes one run: its row, its inputs, its frame, and a race row (with its candidates) for every race whose inputs
    changed since that race's last row of the same family (pre and live share one family; a backtest or replay is its own)
    or whose method version differs. Returns {"races": n, "written": n}. `outputs` is the simulation's {"races": [...]},
    each race carrying "in_sha" (the digest of its own inputs)."""
    frame_sha = put_blob(con, frame, "frame")
    csha = keep_code(con, family(kind, method))
    fam = PUBLIC_KINDS if kind in PUBLIC_KINDS else (kind,)
    last = {}
    if not write_all:
        q = (f"SELECT rr.race, rr.in_sha, r.method FROM race_runs rr JOIN runs r ON r.run = rr.run "
             f"WHERE rr.state = ? AND r.kind IN ({','.join('?' * len(fam))}) AND r.rehearsal = ? "
             f"ORDER BY r.started, r.run")
        for race, in_sha, meth in con.execute(q, (state.upper(), *fam, 1 if rehearsal else 0)):
            last[race] = (in_sha, meth)
    written = 0
    con.execute("INSERT INTO runs (run, state, kind, method, code_sha, seed, draws, started, ended, as_of, rehearsal, frame_sha, "
                "python, races, written, note) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (run, state.upper(), kind, method, csha, seed, draws, iso(started), None, iso(as_of), 1 if rehearsal else 0,
                 frame_sha, platform.python_version(), len(outputs["races"]), 0, note))
    rows_in = [(run, i["input"], i["source"], i.get("sha256"), i.get("as_of"), i.get("kind"), i.get("note")) for i in inputs]
    rows_in.append((run, "frame", f"run_blobs:{frame_sha}", frame_sha, iso(as_of), "frame",
                    "every input the simulation read, kept whole; a redo reads only this"))
    con.executemany("INSERT OR REPLACE INTO run_inputs (run, input, source, sha256, as_of, kind, note) VALUES (?,?,?,?,?,?,?)", rows_in)
    for race in outputs["races"]:
        prev = last.get(race["race"])
        if prev and prev[0] == race["in_sha"] and prev[1] == method:
            continue
        exp = race.get("exp") or [None, None, None]
        con.execute("INSERT INTO race_runs (run, race, state, status, seats, units_in, units_all, ballots, share_counted, exp_lo, "
                    "exp_mid, exp_hi, equal, tested, in_sha, out_sha, note, mg_a, mg_b, mg_med, mg_lo80, mg_hi80, mg_lo95, mg_hi95, ro) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (run, race["race"], state.upper(), race["status"], race.get("seats"), race.get("units_in"), race.get("units_all"),
                     race.get("ballots"), race.get("share_counted"), exp[0], exp[1], exp[2], 1 if race.get("equal") else 0,
                     race.get("tested"), race["in_sha"], out_digest(race), race.get("note")) + margin_columns(race) + (race.get("ro"),))
        con.executemany("INSERT INTO candidate_runs (run, race, choice, name, chance, median, lo80, hi80, lo95, hi95) "
                        "VALUES (?,?,?,?,?,?,?,?,?,?)",
                        [(run, race["race"], c["key"], c.get("name"), c.get("chance"), c.get("median"), c.get("lo80"), c.get("hi80"),
                          c.get("lo95"), c.get("hi95")) for c in race.get("cands", [])])
        written += 1
    con.execute("UPDATE runs SET ended = ?, written = ? WHERE run = ?", (iso(now_utc()), written, run))
    return {"races": len(outputs["races"]), "written": written, "frame_sha": frame_sha}


# ============================================================================================== reading runs back

def _latest(con, state, rehearsal=False, kinds=PUBLIC_KINDS):
    """{race: (run row dict, race row dict)} for the newest row of every race in the public family."""
    q = (f"SELECT r.run, r.kind, r.method, r.started, r.as_of, rr.* FROM race_runs rr JOIN runs r ON r.run = rr.run "
         f"WHERE rr.state = ? AND r.kind IN ({','.join('?' * len(kinds))}) AND r.rehearsal = ? ORDER BY r.started, r.run")
    cur = con.execute(q, (state.upper(), *kinds, 1 if rehearsal else 0))
    cols = [d[0] for d in cur.description]
    out = {}
    for row in cur:
        rec = dict(zip(cols, row))
        out[rec["race"]] = rec
    return out


def _cands(con, run, race):
    cur = con.execute("SELECT choice, name, chance, median, lo80, hi80, lo95, hi95 FROM candidate_runs WHERE run = ? AND race = ? "
                      "ORDER BY name, choice", (run, race))
    return [dict(zip(("choice", "name", "chance", "median", "lo80", "hi80", "lo95", "hi95"), r)) for r in cur]


def chance_cell(p):
    """A chance as a page file carries it: a whole percent from 1 to 99, or the string ">99" (over 99%) or "<1" (under
    1%). Never 0 and never 100."""
    if p is None:
        return None
    pct, mark = shown_chance(p)
    return f"{mark}{pct}" if mark else pct


def _compact_cands(cands):
    """[[name as filed, chance cell, median, 80% low, 80% high]], favourite first (shares in tenths of a percent)."""
    out = []
    for c in sorted(cands, key=lambda c: (-(c["chance"] or 0), -(c["median"] or 0), c["name"] or c["choice"])):
        out.append([c["name"] or c["choice"], chance_cell(c["chance"]), tenths(c["median"]), tenths(c["lo80"]), tenths(c["hi80"])])
    return out


FILE_KEY = {
    "r": "races by id, the state's prefix (\"pre\") taken off",
    "c": "candidates, favourite first: [name as filed, chance, median share, 80% low, 80% high]; a chance is a whole percent "
         "from 1 to 99, or \">99\" (over 99 percent) or \"<1\" (under 1 percent); shares in tenths of a percent",
    "eq": "where nothing on the record separates the candidates: their one shared [chance, median, 80% low, 80% high], and "
          "\"c\" holds the names alone, in alphabetical order (the page says the record gives no reason to favour any of them)",
    "s": "seats when more than one (the chance is then of finishing among the winners)",
    "v": "expected voters in the race: [10th, 50th, 90th percentile]",
    "x": "which past races the method was tested on (a code of \"tested\")",
    "sc": "share of the expected vote counted when the model ran (absent before results)",
    "t, m, k": "the race's own run time, method version and kind where they differ from the file's",
    "about": "the newest run's inputs and method in plain words (\"ran\": when the model last ran, though no race may have "
             "changed; \"t\" at the top: when the newest change was made)",
    "st": "the count's state when the model ran, where it is not \"pre\": counting (some of the race's precincts in) or done "
          "(every precinct in, the counties' last absentee ballots perhaps still to come); absent: none of the race's "
          "precincts counted yet",
    "k values": "pre: the forecast before results; live: the election-night model, from the votes counted so far",
    "mg": "the likely margin of the top two: the first candidate's share less the second's (the first two of \"c\"), "
          "[median, 80% low, 80% high], in tenths of a percentage point; a range below 0 means the second could finish "
          "ahead (absent where several are elected or nothing on the record separates the candidates)",
    "ro": "where the law asks for more than half the votes: the chance that no candidate passes half (a runoff, or the "
          "legislature decides), as a chance cell",
}


def margin_cell(rec, cands, compact):
    """A race's "mg" for a page file: the margin of the file's first candidate over its second, [median, 80% low, 80%
    high] in tenths of a point; None when the run kept no margin or its two are not the file's first two."""
    if rec.get("mg_med") is None or not rec.get("mg_a") or len(compact) < 2:
        return None
    name = {c["choice"]: (c["name"] or c["choice"]) for c in cands}
    a, b = name.get(rec["mg_a"]), name.get(rec["mg_b"])
    first, second = compact[0][0], compact[1][0]
    if (a, b) == (first, second):
        return [tenths(rec["mg_med"]), tenths(rec["mg_lo80"]), tenths(rec["mg_hi80"])]
    if (b, a) == (first, second):
        return [tenths(-rec["mg_med"]), tenths(-rec["mg_hi80"]), tenths(-rec["mg_lo80"])]
    return None


def _tested_codes(texts):
    """A short code for each distinct "tested" text: t1, t2 ... and u for the first "untested" one (u2, u3 ... for any
    other: a race before results and the same kind of race on election night are described differently)."""
    codes, out = {}, {}
    nt = nu = 0
    for t in sorted(t for t in texts if t):
        if t.startswith("untested"):
            nu += 1
            k = "u" if nu == 1 else f"u{nu}"
        else:
            nt += 1
            k = f"t{nt}"
        codes[t] = k
        out[k] = t
    return codes, out


def page_json(code, db=DB, rehearsal=False):
    """A state's forecasts file, fc/<code>.json (ARCHITECTURE.md 2.6; budget 300 KB): every forecast race's latest row,
    in the compact shape FILE_KEY describes (it travels in the file as "key"). Races with one name per seat and races
    with no names are left out (the page says "Unopposed" from its own race list). None when nothing has run."""
    if not os.path.exists(db):
        return None
    con = connect(db)
    try:
        latest = _latest(con, code, rehearsal)
        if not latest:
            return None
        newest = max(latest.values(), key=lambda r: (r["started"], r["run"]))
        shown = {race: rec for race, rec in latest.items() if rec["status"] not in ("unopposed", "no-candidates", "not-modelled")}
        codes, legend = _tested_codes({rec["tested"] for rec in shown.values()})
        pre = f"2026-{code.upper()}-"
        last = con.execute("SELECT run, started, draws, frame_sha FROM runs WHERE state = ? AND kind IN ('pre', 'live') AND rehearsal = ? "
                           "AND ended IS NOT NULL ORDER BY started DESC, run DESC LIMIT 1", (code.upper(), 1 if rehearsal else 0)).fetchone()
        about = {}
        if last:
            frame = get_blob(con, last[3]) or {}
            about = dict(frame.get("public") or {}, draws=last[2], ran=last[1])
        doc = {"v": 1, "state": code.upper(), "t": newest["started"], "m": newest["method"], "run": newest["run"],
               "k": newest["kind"], "rehearsal": bool(rehearsal), "pre": pre, "tested": legend, "key": FILE_KEY,
               "about": json.loads(scrub(canonical(about))), "r": {}}
        for race, rec in sorted(shown.items()):
            cands = _cands(con, rec["run"], race)
            r = {}
            if rec["equal"] and cands:
                c0 = cands[0]
                r["c"] = [[c["name"] or c["choice"]] for c in cands]
                r["eq"] = [chance_cell(c0["chance"]), tenths(c0["median"]), tenths(c0["lo80"]), tenths(c0["hi80"])]
            else:
                r["c"] = _compact_cands(cands)
                mg = margin_cell(rec, cands, r["c"]) if (rec["seats"] or 1) == 1 else None
                if mg:
                    r["mg"] = mg
            if rec.get("ro") is not None:
                r["ro"] = chance_cell(rec["ro"])
            if (rec["seats"] or 1) > 1:
                r["s"] = rec["seats"]
            if rec["tested"]:
                r["x"] = codes[rec["tested"]]
            if rec["exp_mid"] is not None:
                r["v"] = [int(round(rec["exp_lo"] or 0)), int(round(rec["exp_mid"])), int(round(rec["exp_hi"] or 0))]
            if rec["share_counted"]:
                r["sc"] = round(rec["share_counted"], 3)
            if rec["status"] != "pre":
                r["st"] = rec["status"]
            if rec["started"] != doc["t"]:
                r["t"] = rec["started"]
            if rec["method"] != doc["m"]:
                r["m"] = rec["method"]
            if rec["kind"] != doc["k"]:
                r["k"] = rec["kind"]
            doc["r"][race[len(pre):] if race.startswith(pre) else race] = r
        return doc
    finally:
        con.close()


def history(code, db=DB, rehearsal=False, races=None):
    """{race id: history doc} for h/<code>/<race>.json: every stored row of the race, oldest first, each
    [time, method version, kind, share counted, [[name, chance, median, 80% low, 80% high], ...]] (chance and shares as
    in the forecasts file). A change of method version starts a new segment ("segments" lists where each begins)."""
    if not os.path.exists(db):
        return {}
    con = connect(db)
    try:
        q = ("SELECT rr.race, r.run, r.started, r.method, r.kind, rr.share_counted, rr.status FROM race_runs rr JOIN runs r "
             "ON r.run = rr.run WHERE rr.state = ? AND r.kind IN ('pre', 'live') AND r.rehearsal = ? ORDER BY r.started, r.run")
        rows = {}
        for race, run, started, method, kind, sc, status in con.execute(q, (code.upper(), 1 if rehearsal else 0)):
            if races is not None and race not in races:
                continue
            rows.setdefault(race, []).append((run, started, method, kind, sc, status))
        out = {}
        for race, pts in rows.items():
            if all(p[5] in ("unopposed", "no-candidates", "not-modelled") for p in pts):
                continue
            seq, segs = [], []
            for run, started, method, kind, sc, status in pts:
                if status in ("unopposed", "no-candidates", "not-modelled"):
                    continue
                if not segs or segs[-1][1] != method:
                    segs.append([len(seq), method])
                seq.append([started, method, kind, round(sc or 0, 3), _compact_cands(_cands(con, run, race))])
            out[race] = {"v": 1, "race": race, "state": code.upper(), "p": seq, "segments": segs}
        return out
    finally:
        con.close()


def newest(db=DB, rehearsal=False):
    """{"t": UTC of the newest pre-election or live run, "m": its method version} for now.json's "fc", or None."""
    if not os.path.exists(db):
        return None
    con = connect(db)
    try:
        row = con.execute("SELECT started, method FROM runs WHERE kind IN ('pre', 'live') AND rehearsal = ? AND ended IS NOT NULL "
                          "ORDER BY started DESC, run DESC LIMIT 1", (1 if rehearsal else 0,)).fetchone()
        return {"t": row[0], "m": row[1]} if row else None
    finally:
        con.close()


def list_runs(db=DB, state=None):
    con = connect(db)
    try:
        q = "SELECT run, kind, method, started, ended, draws, races, written, rehearsal, note FROM runs"
        args = ()
        if state:
            q += " WHERE state = ?"
            args = (state.upper(),)
        return [dict(zip(("run", "kind", "method", "started", "ended", "draws", "races", "written", "rehearsal", "note"), r))
                for r in con.execute(q + " ORDER BY started, run", args)]
    finally:
        con.close()


# ============================================================================================== the backtest report

def track_json(code, db=DB):
    """The backtest report for the forecasts page's #track: the newest backtest run's measures by scenario and group,
    its calibration table, and what was never tested. None when no backtest has run."""
    if not os.path.exists(db):
        return None
    con = connect(db)
    try:
        row = con.execute("SELECT run, method, started, note, frame_sha FROM runs WHERE state = ? AND kind = 'backtest' AND ended IS NOT NULL "
                          "ORDER BY started DESC, run DESC LIMIT 1", (code.upper(),)).fetchone()
        if not row:
            return None
        run, method, started, note, frame_sha = row
        meas = {}
        for scen, grp, measure, value, n, mnote in con.execute(
                "SELECT scenario, grp, measure, value, n, note FROM calibration WHERE run = ? ORDER BY scenario, grp, measure", (run,)):
            meas.setdefault(scen, {}).setdefault(grp, {})[measure] = [None if value is None else round(value, 4), n] + ([mnote] if mnote else [])
        params = get_blob(con, frame_sha) if frame_sha else None
        doc = {"v": 1, "state": code.upper(), "run": run, "method": method, "t": started, "measures": meas,
               "about": (params or {}).get("report", {})}
        night = night_track(con, code)
        if night:
            doc["night"] = night
        return json.loads(scrub(canonical(doc)))
    finally:
        con.close()


def night_track(con, code):
    """The night model's replays (blindspots.calibrate, kind "replay"), for #track beside the backtest: how its 80 and 95
    percent ranges held in each counting order and at each share counted, its Brier score, how often the candidate ahead
    in the count was not the one who finished first, and how much an early lead meant ("lead": by share of the race
    counted and size of the lead, how often the candidate ahead finished first, beside the model's average chance)."""
    row = con.execute("SELECT run, method, started, frame_sha FROM runs WHERE state = ? AND kind = 'replay' AND ended IS NOT NULL "
                      "ORDER BY started DESC, run DESC LIMIT 1", (code.upper(),)).fetchone()
    if not row:
        return None
    run, method, started, frame_sha = row
    doc = get_blob(con, frame_sha) or {}
    rep = doc.get("report") or {}
    prm = doc.get("params") or {}
    if str(method or "").startswith(US_NIGHT_PREFIX):
        # the other states' night model (night_us.replays): each state's past count replayed in the state's own order
        return {"run": run, "method": method, "t": started, "summary": prm.get("summary"), "what": rep.get("what"),
                "checkpoints": rep.get("checkpoints"), "all": rep.get("all"), "overall": rep.get("overall"),
                "states": [dict(v, c=k) for k, v in sorted((rep.get("states") or {}).items())],
                "untested": rep.get("untested"), "scale": rep.get("scale")}
    return {"run": run, "method": method, "t": started, "summary": prm.get("summary"), "orders": rep.get("orders"),
            "checkpoints": rep.get("checkpoints"),
            "partisan": {"by_order": (rep.get("partisan") or {}).get("by_order"), "simulated": rep.get("partisan_simulated"),
                         "lead": rep.get("partisan_lead")},
            "nonpartisan": {"by_order": (rep.get("nonpartisan") or {}).get("by_order"), "all": (rep.get("nonpartisan") or {}).get("all"),
                            "lead": rep.get("nonpartisan_lead")},
            "what": ("The election-night model was replayed on Minnesota's 2022 and 2024 results, with the precincts revealed in "
                     "four orders (random; small and rural first; whole counties with the largest metro counties last; each "
                     "county's last absentee ballots held back), and scored at " +
                     ", ".join(str(c) for c in (rep.get("checkpoints") or [])[:-1]) +
                     (f" and {(rep.get('checkpoints') or [None])[-1]}" if rep.get("checkpoints") else "") + " percent counted.")}


KIT_NAME = re.compile(r"\b[\w./\\-]+\.(?:py|sqlite|bat|ps1|js|json|md)\b")


def scrub(text):
    """No page names the kit's own files or programs (ARCHITECTURE.md 1.2): any such name in a text bound for a page is
    replaced by plain words."""
    return KIT_NAME.sub("the kit's own file", text)


# ============================================================================================== redo and checks

def _simulator(kind):
    spec = SIMULATORS.get(kind)
    if not spec:
        return None
    mod, fn = spec.split(":")
    return getattr(importlib.import_module(mod), fn)


def redoable(kind, method=None):
    """Whether runs of this kind and method have a registered simulation (backtests and replays keep reports, not frames)."""
    return kind in PUBLIC_KINDS and family(kind, method) in SIMULATORS


def redo(run_id, db=DB, say=print):
    """Redo a stored run from its stored frame and seed, and compare every stored number. Returns {"exact": bool, ...}."""
    con = connect(db)
    try:
        row = con.execute("SELECT kind, seed, draws, frame_sha, code_sha, python, method, written, started, state, rehearsal FROM runs "
                          "WHERE run = ?", (run_id,)).fetchone()
        if not row:
            return {"exact": False, "why": "no such run"}
        run_kind, seed, draws, frame_sha, csha, py, method, written, started, state, reh = row
        kind = family(run_kind, method)             # the simulation family: Minnesota's night or the other states'
        notes = []
        digest = out_digest
        if csha == code_sha(kind):
            sim = _simulator(kind)
        else:
            kept = load_code(con, csha, kind)
            if kept is None:
                return {"exact": False, "why": "the code this run was made with was not kept"}
            sim, kept_runs = kept
            digest = kept_runs.out_digest
            notes.append("redone with the code the run was made with (the model's code has changed since)")
        if sim is None:
            return {"exact": False, "why": f"no simulation is registered for runs of kind {kind}"}
        frame = get_blob(con, frame_sha)
        if frame is None:
            return {"exact": False, "why": "the run's frame is not on file"}
        if not written:
            # a run whose races' inputs had not changed wrote no rows: its frame must give exactly the inputs of the rows
            # standing at that moment (each race's newest row of the same family, before or at this run)
            fam = PUBLIC_KINDS if run_kind in PUBLIC_KINDS else (run_kind,)
            standing = {}
            q = (f"SELECT rr.race, rr.in_sha FROM race_runs rr JOIN runs r ON r.run = rr.run WHERE rr.state = ? AND r.rehearsal = ? "
                 f"AND r.kind IN ({','.join('?' * len(fam))}) AND (r.started < ? OR (r.started = ? AND r.run <= ?)) ORDER BY r.started, r.run")
            for race, in_sha in con.execute(q, (state, reh, *fam, started, started, run_id)):
                standing[race] = in_sha
            out = sim(frame, seed, min(draws, 20))
            diffs = [r["race"] for r in out["races"] if standing.get(r["race"]) != r["in_sha"]]
            res = {"exact": not diffs and bool(out["races"]), "compared": len(out["races"]), "differ": diffs[:20], "n_differ": len(diffs),
                   "notes": notes + ["no race changed in this run: its frame was checked against the standing rows' inputs"],
                   "method": method}
            say(f"    redo {run_id}: wrote no rows; {len(out['races'])} races' inputs checked against the standing rows, {len(diffs)} differ")
            return res
        out = sim(frame, seed, draws)
        stored = {}
        for race, status, in_sha, out_sha in con.execute("SELECT race, status, in_sha, out_sha FROM race_runs WHERE run = ?", (run_id,)):
            stored[race] = (in_sha, out_sha)
        diffs, compared = [], 0
        for race in out["races"]:
            if race["race"] not in stored:
                continue
            compared += 1
            in_sha, out_sha = stored[race["race"]]
            if race["in_sha"] != in_sha or digest(race) != out_sha:
                diffs.append(race["race"])
        if py != platform.python_version():
            notes.append(f"the run was made on Python {py}, this redo on {platform.python_version()}")
        res = {"exact": not diffs and compared > 0, "compared": compared, "differ": diffs[:20], "n_differ": len(diffs), "notes": notes,
               "method": method}
        say(f"    redo {run_id}: {compared} races compared, {len(diffs)} differ" + (f" ({'; '.join(notes)})" if notes else ""))
        return res
    finally:
        con.close()


def check_no_extremes(code, db=DB):
    """No 0 and no 100: every stored chance strictly between 0 and 1, and every chance the pages' files carry from 1 to 99."""
    con = connect(db)
    try:
        bad_db = con.execute("SELECT COUNT(*) FROM candidate_runs cr JOIN runs r ON r.run = cr.run WHERE r.state = ? AND "
                             "cr.chance IS NOT NULL AND (cr.chance <= 0 OR cr.chance >= 1)", (code.upper(),)).fetchone()[0]
    finally:
        con.close()
    def bad(cell):
        return not (cell is None or cell in (">99", "<1") or (isinstance(cell, int) and 1 <= cell <= 99))
    bad_page = 0
    doc = page_json(code, db) or {"r": {}}
    for r in doc["r"].values():
        cells = [r["eq"][0]] if "eq" in r else [c[1] for c in r["c"]]
        if "ro" in r:
            cells.append(r["ro"])
        bad_page += sum(1 for cell in cells if bad(cell))
    text = canonical(doc)
    hist = history(code, db)
    for h in hist.values():
        for p in h["p"]:
            bad_page += sum(1 for c in p[4] if bad(c[1]))
    return {"stored_out_of_range": bad_db, "page_out_of_range": bad_page, "holds": bad_db == 0 and bad_page == 0,
            "page_bytes": len(text.encode("utf-8")), "races_in_page": len(doc["r"])}


def check_unopposed(code, db=DB):
    """No forecast for a race with one name per seat: every such race's rows carry no chance, and the page leaves it out."""
    con = connect(db)
    try:
        bad = con.execute("SELECT COUNT(*) FROM race_runs rr JOIN candidate_runs cr ON cr.run = rr.run AND cr.race = rr.race "
                          "WHERE rr.state = ? AND rr.status = 'unopposed' AND cr.chance IS NOT NULL", (code.upper(),)).fetchone()[0]
        unopp = {r for (r,) in con.execute("SELECT DISTINCT race FROM race_runs WHERE state = ? AND status = 'unopposed'", (code.upper(),))}
    finally:
        con.close()
    doc = page_json(code, db) or {"r": {}}
    ids = {(k if k.startswith("2026-") or not doc.get("pre") else doc["pre"] + k) for k in doc["r"]}
    shown = sorted(ids & unopp)
    return {"unopposed_races": len(unopp), "with_a_chance_stored": bad, "in_the_page": len(shown), "holds": bad == 0 and not shown,
            "page_races": len(ids)}


# ============================================================================================== self-test

def selftest(say=print):
    import tempfile
    ok = True

    def check(what, got, want):
        nonlocal ok
        good = got == want
        ok &= good
        say(f"    {'ok ' if good else 'BAD'} {what}: {got!r}" + ("" if good else f" (expected {want!r})"))
    check("a chance from no wins is above 0", stored_chance(0, 999) > 0, True)
    check("a chance from every win is below 1", stored_chance(999, 999) < 1, True)
    check("shown: 0.996 is over 99", shown_chance(0.996), (99, ">"))
    check("shown: 0.004 is under 1", shown_chance(0.004), (1, "<"))
    check("shown: 0.625 rounds to 63", shown_chance(0.625), (63, ""))
    check("shown: 0.006 is 1, no mark", shown_chance(0.006), (1, ""))
    check("tenths of a percent", tenths(0.5244), 524)
    check("the seed is the run id's", seed_of("pre-mn-20261027T140000Z") == seed_of("pre-mn-20261027T140000Z"), True)
    d = tempfile.mkdtemp()
    db = os.path.join(d, "t.sqlite")
    con = connect(db)
    frame = {"races": [{"id": "R1"}]}

    def race(chance, in_sha="a"):
        return {"race": "R1", "status": "pre", "seats": 1, "in_sha": in_sha, "exp": [90, 100, 110],
                "cands": [{"key": "a", "name": "A", "chance": chance, "median": 0.52, "lo80": 0.48, "hi80": 0.56, "lo95": 0.46, "hi95": 0.58},
                          {"key": "b", "name": "B", "chance": 1 - chance, "median": 0.48, "lo80": 0.44, "hi80": 0.52, "lo95": 0.42, "hi95": 0.54}]}
    unopp = {"race": "R2", "status": "unopposed", "seats": 1, "in_sha": "u", "cands": [{"key": "c", "name": "C"}]}
    t0 = now_utc()
    with con:
        r1 = record_run(con, run="pre-xx-1", state="XX", kind="pre", method="pre-1.0", seed=1, draws=10, started=t0, as_of=t0,
                        frame=frame, outputs={"races": [race(0.6), unopp]}, inputs=[])
        r2 = record_run(con, run="pre-xx-2", state="XX", kind="pre", method="pre-1.0", seed=2, draws=10,
                        started=t0 + dt.timedelta(minutes=1), as_of=t0, frame=frame, outputs={"races": [race(0.61), unopp]}, inputs=[])
        r3 = record_run(con, run="pre-xx-3", state="XX", kind="pre", method="pre-1.0", seed=3, draws=10,
                        started=t0 + dt.timedelta(minutes=2), as_of=t0, frame=frame, outputs={"races": [race(0.7, "b"), unopp]}, inputs=[])
        r4 = record_run(con, run="pre-xx-4", state="XX", kind="pre", method="pre-1.1", seed=4, draws=10,
                        started=t0 + dt.timedelta(minutes=3), as_of=t0, frame=frame, outputs={"races": [race(0.7, "b"), unopp]}, inputs=[])
    con.close()
    check("first run writes both races", r1["written"], 2)
    check("the same inputs again write nothing", r2["written"], 0)
    check("changed inputs write that race only", r3["written"], 1)
    check("a new method version writes the changed-method race again", r4["written"], 2)
    doc = page_json("XX", db)
    check("the page leaves the unopposed race out", sorted(doc["r"]), ["R1"])
    check("the page's chance is a whole percent", doc["r"]["R1"]["c"][0][1], 70)
    check("a chance over 99 is a mark, never 100", chance_cell(0.9996), ">99")
    check("a chance under 1 is a mark, never 0", chance_cell(0.0004), "<1")
    h = history("XX", db)
    check("history keeps three points for R1", len(h["R1"]["p"]), 3)
    check("a method change starts a segment", [s[1] for s in h["R1"]["segments"]], ["pre-1.0", "pre-1.1"])
    check("newest is the last run", newest(db)["m"], "pre-1.1")
    check("no 0 or 100", check_no_extremes("XX", db)["holds"], True)
    check("nothing for the unopposed race", check_unopposed("XX", db)["holds"], True)
    con = connect(db)
    check("the frame and the code are each stored once", con.execute("SELECT COUNT(*) FROM run_blobs").fetchone()[0], 2)
    check("a blob comes back whole", get_blob(con, put_blob(con, frame)), frame)
    # a kept code version runs exactly as the code it was kept from
    from election.model import forecast
    tiny = {"method": forecast.METHOD, "params": forecast.DEFAULT_PARAMS, "priors": forecast.PRIORS, "days_to_election": 1,
            "env": {"theta": ["G"], "mean": [0.0], "cov": [[1e-8]]},
            "races": [{"race": "N1", "kind": "nonpartisan", "group": "county", "seats": 1, "status": "pre", "rot": [0.6, 0.4],
                       "cands": [{"key": "a", "name": "A", "inc": 1}, {"key": "b", "name": "B", "inc": 0}]}]}
    tiny = json.loads(canonical(tiny))
    kept = load_code(con, keep_code(con, "pre"), "pre")
    check("the kept code loads", kept is not None, True)
    if kept:
        check("the kept code gives the same numbers", canonical(kept[0](tiny, 5, 200)) == canonical(forecast.simulate(tiny, 5, 200)), True)
    con.close()
    return ok


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--state", default="mn")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--redo")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--db", default=DB)
    a = ap.parse_args(argv)
    if a.selftest:
        sys.exit(0 if selftest() else 1)
    if a.list:
        for r in list_runs(a.db, a.state):
            print(f"    {r['run']}  {r['kind']:8} {r['method']:10} {r['started']}  draws {r['draws']}  races {r['races']}  "
                  f"written {r['written']}{'  rehearsal' if r['rehearsal'] else ''}")
        return
    if a.redo:
        res = redo(a.redo, a.db)
        print(f"    {'exact' if res['exact'] else 'NOT exact'}: {res}")
        sys.exit(0 if res["exact"] else 1)
    if a.check:
        ok = True
        e = check_no_extremes(a.state, a.db)
        print(f"    no 0 or 100: {e}")
        u = check_unopposed(a.state, a.db)
        print(f"    unopposed races carry no forecast: {u}")
        ok &= e["holds"] and u["holds"]
        for r in list_runs(a.db, a.state):
            if redoable(r["kind"], r["method"]):
                res = redo(r["run"], a.db)
                ok &= res["exact"]
        sys.exit(0 if ok else 1)
    ap.print_help()


if __name__ == "__main__":
    main()
