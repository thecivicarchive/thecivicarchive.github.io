"""election/model - the forecasts' data and models (ARCHITECTURE.md 2.4, 4.1).

Minnesota's model data (built by data_mn.py, census.py and features.py; `python -m election.model.features --state mn`
runs all three):
  data_mn.py    the Secretary of State's certified precinct results 2012-2024 (Minnesota Geospatial Commons), MEDSL's
                public-domain precinct files (labelled secondary), the official totals each contest is checked against,
                and every past precinct carried onto today's precinct lines
  census.py     2020 blocks into today's precincts and school districts; ACS 2020-2024 block-group estimates carried to
                them through the blocks, with margins of error; the citizen voting-age population (CVAP) file
  features.py   one row per precinct (and school district) and feature in the `features` table of
                election_model_2026.sqlite, the inputs' fingerprints in `run_inputs`, and the three checks

Everything downloaded lands once in election_cache/model/mn/ (never published). Every request goes through
election/source.py. Nothing here describes a voter: every figure is about a place, and every derived figure is Analysis.
"""

import datetime as dt
import hashlib
import json
import os
import sqlite3
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

DB = os.path.join(HERE, "election_model_2026.sqlite")
CACHE_ROOT = os.path.join(HERE, "election_cache", "model")

SCHEMA = """
CREATE TABLE IF NOT EXISTS features (
    state      TEXT NOT NULL,          -- two letters, lower case
    unit_kind  TEXT NOT NULL,          -- precinct (today's VTDID), school (ISD0001 ...), state
    unit_id    TEXT NOT NULL,
    name       TEXT NOT NULL,          -- the feature's name, see features.FEATURES
    value      REAL,                   -- NULL when the record gives none (the reason is in note)
    moe        REAL,                   -- 90 percent margin of error where the source has one
    source     TEXT NOT NULL,          -- which input it comes from (an input name of run_inputs)
    method     TEXT NOT NULL,          -- the method version that made it
    build      TEXT NOT NULL,          -- the data build (a run of run_inputs) that wrote it
    note       TEXT,
    PRIMARY KEY (state, unit_kind, unit_id, name)
);
CREATE INDEX IF NOT EXISTS features_name ON features (state, name);
CREATE TABLE IF NOT EXISTS run_inputs (
    run      TEXT NOT NULL,            -- a model run, or a data build ("data-mn-<UTC time>")
    input    TEXT NOT NULL,            -- a short name
    source   TEXT NOT NULL,            -- the file or the address it was read from
    sha256   TEXT,
    as_of    TEXT,                     -- the source's own date, else when it was fetched
    kind     TEXT,                     -- official, secondary, derived, census
    note     TEXT,
    PRIMARY KEY (run, input)
);
"""


def connect(db=DB):
    con = sqlite3.connect(db)
    con.executescript(SCHEMA)
    return con


def cache_dir(code="mn", *parts):
    path = os.path.join(CACHE_ROOT, code, *parts)
    os.makedirs(path, exist_ok=True)
    return path


def now_utc():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def save_json(path, doc):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + ".part"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, path)


def load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


_SOURCE = None


def source():
    """The one Source of this process (politeness and the never lists live there)."""
    global _SOURCE
    if _SOURCE is None:
        from election.source import Source
        _SOURCE = Source()
    return _SOURCE


class FetchError(Exception):
    pass


def fetch(url, path, say=print, accept="*/*", expect_html=False, keep=True):
    """One file, fetched once through election/source.py and kept at `path`. A file already on disk is never asked
    for again (the downloads John approved are made once). Returns the bytes."""
    if os.path.exists(path) and os.path.getsize(path) > 0:
        with open(path, "rb") as fh:
            return fh.read()
    from election.source import Refused, SourceError
    src = source()
    t0 = time.time()
    try:
        r = src.get(url, state="MN", accept=accept, timeout=180, expect_html=expect_html)
    except (Refused, SourceError) as e:
        raise FetchError(str(e)) from e
    if r.refused:
        raise FetchError(f"{url}: the host refused ({r.why}); it is not asked again tonight")
    if not r.ok:
        raise FetchError(f"{url}: answered {r.status}")
    if keep:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path + ".part", "wb") as fh:
            fh.write(r.body)
        os.replace(path + ".part", path)
    say(f"      fetched {os.path.basename(path)}: {len(r.body) / 1e6:,.1f} MB in {time.time() - t0:,.0f} s")
    return r.body
