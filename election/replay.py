"""election/replay.py - a past election replayed as if it were tonight (ARCHITECTURE.md 3.9), so that a rehearsal runs
the night's own code: the same updater, the same readers, the same store, the same snapshot files and publisher.

  The clock     a replay runs on a night clock: it starts a little before the replayed election's polls closed and
                runs `speed` times faster than the wall clock (6 times: a 12-hour night in 2 hours). Everything the
                updater decides by time (when a state's polls close, when a snapshot is due, when John would have saved
                files) follows the night clock; every time written into the figures is the real time, so the pages'
                own clocks (stale after 25 minutes, the reader's time zone) work as they will on the night.

  Minnesota     the replayed night's results files are revealed precinct by precinct and written into a rehearsal
                folder the updater watches, at the moments John's saves would arrive (from about 8:15 p.m. every 20
                minutes or so, and once more in the morning). Sources, in this order of preference:
                  saved:<yyyymmdd>  John's own saved Media Files for a past election (states_cache/mn_local/sos/<date>/)
                  2024-senate       the 2024 U.S. Senate count in every precinct, from the Secretary of State's
                                    official precinct results (Minnesota Geospatial Commons), written in the results
                                    files' layout the way the reader's own test files are (election/fixtures/mn/README.md)
                  fixture           the reader's test files: the same count in three counties
                Orders (which precincts come first): random; small-first (the smallest precincts first); metro-last
                (the seven Twin Cities counties last). With late, part of each precinct's absentee and mail ballots
                (an assumed 5 percent; the 2024 table gives each precinct's absentee and mail ballots) is held back
                and added in the morning save, as counties add their last absentee ballots. When precincts arrive is
                a plain assumed curve (ARRIVAL below), not data: the real order is learned on the night (D7).

  Other states  a state's past election, fetched once through its reader (election/source.py, politely) into a
                "final" folder, is cut into step folders, one for every 10 minutes after the polls closed, each
                holding what the reader's own reveal() makes of the final files with only the counties reported by
                then; StepReplay then answers the reader's requests from the step the night clock has reached. A
                reader that offers no reveal() is replayed with its final files only (one step).

Rehearsals write only to the rehearsal folder (site/night-live/rehearsal/) and their own database, never the night's.
The pages read it only with #rehearsal in the address, and say "Rehearsal: replayed figures from <label>. Not 2026
results."
"""

import collections
import datetime as dt
import hashlib
import json
import math
import os
import random
import shutil
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

UTC = dt.timezone.utc
REPLAY_SOURCES = os.path.join(HERE, "election_cache", "replay", "sources")
TABLE_N6 = os.path.join(HERE, "election_cache", "model", "mn", "commons", "precinct_2024.json")
TABLE_KIT = os.path.join(HERE, "states_cache", "mn_local", "sos_electionresults_2024.json")
SAVED = os.path.join(HERE, "states_cache", "mn_local", "sos")
METRO_FIPS = {"003", "019", "037", "053", "123", "139", "163"}    # Anoka, Carver, Dakota, Hennepin, Ramsey, Scott, Washington
# minutes after the polls close -> share of precincts in. An assumption for rehearsals, not data (see the docstring).
ARRIVAL = [(10, 0.0), (40, .10), (70, .28), (100, .46), (130, .62), (160, .75), (190, .85), (220, .92), (250, .96), (280, .985), (330, 1.0)]
FIRST_SAVE, SAVE_EVERY, SAVE_JITTER, MORNING = 15, 20, 5, 11 * 60 + 30     # minutes after the polls close
LATE_SHARE = 0.05
ORDERS = ("random", "small-first", "metro-last")
MONTHS = ("Jan.", "Feb.", "March", "April", "May", "June", "July", "Aug.", "Sept.", "Oct.", "Nov.", "Dec.")


def utcnow():
    return dt.datetime.now(UTC)


def iso(t):
    return t.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z") if t else None


def parse(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None


# ---------------------------------------------------------------------------------------------- clocks

class RealClock:
    speed = 1.0

    def now(self):
        return utcnow()

    def wall_seconds(self, night_seconds):
        return night_seconds


class ReplayClock:
    """Night time = night_start + (wall time - wall_start) x speed."""

    def __init__(self, night_start, wall_start=None, speed=6.0):
        self.night_start, self.wall_start, self.speed = night_start, wall_start or utcnow(), float(speed)

    def now(self):
        return self.night_start + (utcnow() - self.wall_start) * self.speed

    def wall_seconds(self, night_seconds):
        return night_seconds / self.speed


# ---------------------------------------------------------------------------------------------- Minnesota's sources

def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build_mn_2024_senate(out_dir=None, say=print):
    """The 2024 U.S. Senate count in every precinct, in the results files' layout (as election/fixtures/mn/ is made):
    the Secretary of State's official precinct results; the office ID, order codes and summary lines are the layout's.
    Also late.json (each precinct's absentee and mail ballots, where the table gives them). Returns the folder."""
    from election.readers import mn_media as M
    out_dir = out_dir or os.path.join(REPLAY_SOURCES, "mn-2024-senate")
    path = TABLE_N6 if os.path.exists(TABLE_N6) else TABLE_KIT
    src = json.load(open(path, encoding="utf-8"))
    rows = sorted(src["rows"], key=lambda r: r["vtdid"])
    prec, county_lines, state_lines = [], [], []
    tot = collections.Counter()
    by_cty = collections.defaultdict(collections.Counter)
    n_cty = collections.Counter()
    late, mismatched = {}, 0
    for r in rows:
        cid = (int(r["countyfips"]) + 1) // 2
        code = r["vtdid"][5:]
        votes = [int(r.get(col) or 0) for col, *_ in M.FIXTURE_SENATE]
        total = sum(votes)
        if int(r.get("ussentotal") or 0) != total:
            mismatched += 1
        for (col, order, name, party), v in zip(M.FIXTURE_SENATE, votes):
            pct = f"{100.0 * v / total:.2f}" if total else "0.00"
            prec.append(f"MN;{cid};{code};0102;U.S. Senator;;{order};{name};;;{party};1;1;{v};{pct};{total}")
            tot[col] += v
            by_cty[cid][col] += v
        tot["total"] += total
        by_cty[cid]["total"] += total
        n_cty[cid] += 1
        try:
            ab = int(float(r.get("ab_mb") or 0))
        except (TypeError, ValueError):
            ab = 0
        if ab > 0:
            late[r["vtdid"]] = ab
    for cid in sorted(by_cty):
        for col, order, name, party in M.FIXTURE_SENATE:
            v, t = by_cty[cid][col], by_cty[cid]["total"]
            county_lines.append(f"MN;{cid};;0102;U.S. Senator;;{order};{name};;;{party};{n_cty[cid]};{n_cty[cid]};{v};{100.0 * v / t if t else 0:.2f};{t}")
    n = len(rows)
    for col, order, name, party in M.FIXTURE_SENATE:
        state_lines.append(f"MN;88;;0102;U.S. Senator;;{order};{name};;;{party};{n};{n};{tot[col]};{100.0 * tot[col] / tot['total']:.2f};{tot['total']}")
    os.makedirs(out_dir, exist_ok=True)
    for name, lines in (("ussenate_precincts.txt", prec), ("ussenate_county.txt", county_lines), ("ussenate_statewide.txt", state_lines)):
        with open(os.path.join(out_dir, name), "w", encoding="utf-8", newline="\r\n") as fh:
            fh.write("\n".join(lines) + "\n")
    with open(os.path.join(out_dir, "late.json"), "w", encoding="utf-8") as fh:
        json.dump({"what": "each precinct's absentee and mail ballots (the official table's ab_mb), for the late-batch rehearsal",
                   "ballots": late}, fh, separators=(",", ":"))
    about = {"what": "The 2024 U.S. Senate count in every Minnesota precinct, in the results files' layout, for rehearsals.",
             "source": src.get("service"), "layer": src.get("layer_name"), "fetched": src.get("fetched"), "file": os.path.relpath(path, HERE),
             "sha256": _sha(path), "precincts": n, "totals": {c: tot[c] for c, *_ in M.FIXTURE_SENATE} | {"total": tot["total"]},
             "precinct_total_differs_from_its_lines": mismatched,
             "layout": "office ID 0102, the order codes and the summary lines are the layout's, as in election/fixtures/mn/README.md"}
    with open(os.path.join(out_dir, "about.json"), "w", encoding="utf-8") as fh:
        json.dump(about, fh, indent=1)
    say(f"    rehearsal source: {n:,} precincts, {len(prec):,} precinct lines; totals " +
        ", ".join(f"{name} {tot[col]:,}" for col, _o, name, _p in M.FIXTURE_SENATE) +
        (f"; {mismatched} precinct totals differ from their lines (the lines' sum is used)" if mismatched else ""))
    return out_dir


def mn_source(kind):
    """(folder, label) for a Minnesota rehearsal source."""
    if kind.startswith("saved:"):
        day = kind.split(":", 1)[1]
        folder = os.path.join(SAVED, day)
        d = dt.date(int(day[:4]), int(day[4:6]), int(day[6:8]))
        what = "primary" if (d.month == 8) else "general election"
        return folder, f"the {MONTHS[d.month - 1]} {d.day}, {d.year} {what}, as saved from the Secretary of State's results files"
    if kind == "2024-senate":
        folder = os.path.join(REPLAY_SOURCES, "mn-2024-senate")
        if not os.path.exists(os.path.join(folder, "ussenate_precincts.txt")):
            build_mn_2024_senate(folder, say=lambda *_: None)
        return folder, "the Nov. 5, 2024 U.S. Senate count in Minnesota (official precinct results)"
    if kind == "fixture":
        return os.path.join(HERE, "election", "fixtures", "mn", "night"), "the Nov. 5, 2024 U.S. Senate count in three Minnesota counties (test files)"
    raise ValueError(f"no Minnesota rehearsal source called {kind!r}")


def best_mn_source(day=None):
    """John's saved files for a past election when he has saved them, else the statewide 2024 Senate count."""
    from election.readers import mn_media as M
    days = [day] if day else ["20241105", "20260811", "20221108"]
    for d in days:
        folder = os.path.join(SAVED, d)
        if os.path.isdir(folder) and M.folder_files(folder)[0]:
            return f"saved:{d}"
    return "2024-senate"


# ---------------------------------------------------------------------------------------------- Minnesota's saver

def _arrival_minutes(r):
    """Minutes after the polls close at which a share r (0 to 1) of precincts is in."""
    for (m0, f0), (m1, f1) in zip(ARRIVAL, ARRIVAL[1:]):
        if r <= f1:
            return m0 + (m1 - m0) * ((r - f0) / (f1 - f0) if f1 > f0 else 0)
    return ARRIVAL[-1][0]


class MnSaver:
    """Writes the replayed night's results files into the watched rehearsal folder, as John's saves would arrive."""

    FILES_HELD = (".crdownload", ".part", ".tmp")

    def __init__(self, source, out_dir, close, order="random", late=False, seed=7, hours=12):
        from election.readers import mn_media as M
        self.M = M
        self.source, self.out_dir, self.close = source, out_dir, close
        self.order, self.late, self.seed = order, late, seed
        results, _refs, _other = M.folder_files(source)
        if not results:
            raise ValueError(f"no results files in {source}")
        self.files = []                 # [(name, [cells or raw line])]
        sizes = collections.Counter()
        self.contest_precincts = collections.defaultdict(set)
        for path, _k, _raw, lines in results:
            parsed = []
            for ln in lines:
                c = [x.strip() for x in ln.split(";")]
                if len(c) >= 14 and c[0] == "MN":
                    c = (c + [""] * 16)[:16]
                    if c[2]:
                        vid = M.vtdid(int(c[1]), c[2]) if c[1].isdigit() else None
                        c.append(vid)
                        if vid:
                            t = int(c[15]) if c[15].isdigit() else int(c[13] or 0)
                            sizes[vid] = max(sizes[vid], t)
                            self.contest_precincts[(c[3], c[4], c[5])].add(vid)
                    parsed.append(c)
                else:
                    parsed.append(ln)
            self.files.append((os.path.basename(path), parsed))
        self.precincts = sorted(sizes)
        rng = random.Random(seed)
        if order == "small-first":
            ranked = sorted(self.precincts, key=lambda v: (math.log1p(sizes[v]) + rng.gauss(0, 0.35), v))
        elif order == "metro-last":
            ranked = sorted(self.precincts, key=lambda v: (v[2:5] in METRO_FIPS, rng.random()))
        else:
            ranked = sorted(self.precincts, key=lambda v: rng.random())
        n = len(ranked)
        self.at = {v: close + dt.timedelta(minutes=_arrival_minutes((i + 1) / n)) for i, v in enumerate(ranked)}
        held = {}
        self.late_note = None
        if late:
            lj = os.path.join(source, "late.json")
            ballots = json.load(open(lj, encoding="utf-8"))["ballots"] if os.path.exists(lj) else {}
            for v in self.precincts:
                b = int(ballots.get(v) or 0)
                if b and sizes[v]:
                    held[v] = min(sizes[v], int(round(b * LATE_SHARE)))
            self.late_note = (f"late batches: {LATE_SHARE:.0%} of each precinct's absentee and mail ballots held back until the morning save "
                              f"({sum(held.values()):,} ballots in {len(held):,} precincts)" if held else
                              "late batches asked for, but this source does not give absentee ballots by precinct; none held back")
        self.held, self.sizes = held, sizes
        rngs = random.Random(seed + 1)
        saves, m = [], FIRST_SAVE
        last_in = (max(self.at.values()) - close).total_seconds() / 60
        while m <= last_in + SAVE_EVERY:
            saves.append(m)
            m += SAVE_EVERY + rngs.randint(-SAVE_JITTER, SAVE_JITTER)
        if MORNING < hours * 60 - 10:
            saves.append(MORNING)
        self.saves = [close + dt.timedelta(minutes=x) for x in saves]
        self.morning = close + dt.timedelta(minutes=MORNING)

    # ------------------------------------------------------------------ one save
    def due(self, night_now):
        """The index of the newest save due by night_now, or -1."""
        k = -1
        for i, t in enumerate(self.saves):
            if t <= night_now:
                k = i
        return k

    def reported(self, t):
        return {v for v, at in self.at.items() if at <= t}

    def write(self, i):
        """Writes save i into the watched folder (each file whole under a temporary name, then renamed). Returns
        (precincts in, precincts in all)."""
        t = self.saves[i]
        rep = self.reported(t)
        morning = t >= self.morning
        os.makedirs(self.out_dir, exist_ok=True)

        def precinct_votes(c):
            """A precinct line's figures at this save: (votes, in, total)."""
            vid = c[16]
            if vid not in rep:
                return 0, 0, 0
            v, total = int(c[13] or 0), int(c[15]) if c[15].isdigit() else None
            if self.held.get(vid) and not morning:
                keep = 1 - self.held[vid] / self.sizes[vid]
                v = int(math.floor(v * keep))
            return v, 1, total

        # the precinct lines first, so every summary line can be added up from them
        sums = collections.defaultdict(lambda: [0, 0, 0])           # (contest, county or '*', order, name) -> [votes, in, total]
        office_tot = collections.defaultdict(int)                   # (contest, precinct) -> the precinct's total for the office
        new_lines = {}
        for name, parsed in self.files:
            for k, c in enumerate(parsed):
                if isinstance(c, list) and c[2] and len(c) > 16 and c[16]:
                    v, inn, _t = precinct_votes(c)
                    new_lines[(name, k)] = (v, inn)
                    office_tot[((c[3], c[4], c[5]), c[16])] += v
        def county_key(x):
            return str(int(x)) if str(x).isdigit() else str(x)

        for name, parsed in self.files:
            for k, c in enumerate(parsed):
                if (name, k) in new_lines:
                    v, inn = new_lines[(name, k)]
                    key = (c[3], c[4], c[5])
                    for scope in (county_key(c[1]), "*"):
                        s = sums[(key, scope, c[6], c[7])]
                        s[0] += v
                        s[1] += inn
        out_files = {}
        for name, parsed in self.files:
            lines = []
            for k, c in enumerate(parsed):
                if not isinstance(c, list):
                    lines.append(c)
                    continue
                cells = list(c[:16])
                key = (c[3], c[4], c[5])
                if (name, k) in new_lines:
                    v, inn = new_lines[(name, k)]
                    tot = office_tot[(key, c[16])]
                    cells[11], cells[13], cells[15] = str(inn), str(v), str(tot)
                    cells[14] = f"{100.0 * v / tot:.2f}" if tot else "0.00"
                elif not c[2]:
                    scope = "*" if county_key(c[1]) in ("88", "") else county_key(c[1])
                    precincts = self.contest_precincts.get(key)
                    if precincts:
                        s = sums[(key, scope, c[6], c[7])]
                        pool = [p for p in precincts if scope == "*" or (p[2:5] == f"{2 * int(scope) - 1:03d}")]
                        inn = sum(1 for p in pool if p in rep)
                        tot = sum(office_tot[(key, p)] for p in pool)
                        cells[11], cells[13], cells[15] = str(inn), str(s[0]), str(tot)
                        cells[14] = f"{100.0 * s[0] / tot:.2f}" if tot else "0.00"
                    else:
                        # no precinct lines for this contest in the set: its figures grow with its area's share of precincts in
                        pool = [p for p in self.precincts if scope == "*" or (p[2:5] == f"{2 * int(scope) - 1:03d}")]
                        f = (sum(1 for p in pool if p in rep) / len(pool)) if pool else 0
                        v, a, tot = int(c[13] or 0), int(c[12] or 0), int(c[15]) if c[15].isdigit() else 0
                        cells[13], cells[11], cells[15] = str(int(v * f)), str(int(round(a * f))), str(int(tot * f))
                        cells[14] = f"{100.0 * int(v * f) / int(tot * f):.2f}" if int(tot * f) else "0.00"
                lines.append(";".join(cells))
            out_files[name] = "\r\n".join(lines) + "\r\n"
        for name, text in out_files.items():
            p = os.path.join(self.out_dir, name)
            with open(p + ".part", "w", encoding="utf-8", newline="") as fh:
                fh.write(text)
            os.replace(p + ".part", p)
        return len(rep), len(self.precincts)

    def describe(self):
        return (f"{len(self.precincts):,} precincts in {self.order} order, {len(self.saves)} saves from "
                f"{self.saves[0]:%H:%M} UTC" + (f"; {self.late_note}" if self.late_note else ""))


# ---------------------------------------------------------------------------------------------- other states

class StepReplay:
    """A Source replay: answers a request from the newest step folder the night clock has reached.
    <root>/<code>/<minutes after the state's polls closed, four digits>/<host>/<path> (FolderReplay's layout)."""

    def __init__(self, root, clock, closes, hosts):
        from election.source import FolderReplay
        self.root, self.clock, self.closes, self.hosts = root, clock, closes, hosts
        self.FolderReplay = FolderReplay

    def step_for(self, code):
        d = os.path.join(self.root, code.lower())
        steps = sorted(int(n) for n in os.listdir(d) if n.isdigit()) if os.path.isdir(d) else []
        m = (self.clock.now() - self.closes[code]).total_seconds() / 60
        got = [s for s in steps if s <= m]
        return got[-1] if got else None

    def __call__(self, url):
        from election.source import host_of
        code = self.hosts.get(host_of(url))
        if not code:
            return 404, b"", {}
        step = self.step_for(code)
        if step is None:
            return 404, b"", {}
        return self.FolderReplay(os.path.join(self.root, code.lower(), f"{step:04d}"))(url)


def save_final(files, final_dir):
    """A past election's files ([(address, bytes)] as a reader's fetch returns them) kept by address."""
    from election.source import FolderReplay
    fr = FolderReplay(final_dir)
    for url, body in files:
        p = fr.path_for(url)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as fh:
            fh.write(body)


def load_final(final_dir):
    """{relative path: bytes} of a final folder."""
    out = {}
    for root, _d, names in os.walk(final_dir):
        for n in names:
            p = os.path.join(root, n)
            out[os.path.relpath(p, final_dir).replace(os.sep, "/")] = open(p, "rb").read()
    return out


def make_steps(code, reader, final_dir, out_root, order="random", seed=7, every=10):
    """Step folders for one state from its final files, through the reader's units() and reveal(). Returns the steps."""
    files = load_final(final_dir)
    dest = os.path.join(out_root, code.lower())
    shutil.rmtree(dest, ignore_errors=True)
    if not (hasattr(reader, "units") and hasattr(reader, "reveal")):
        _write_step(dest, 0, files)
        return [0]
    units = list(reader.units(files))                   # [(unit id, county, size)]
    rng = random.Random(seed)
    if order == "small-first":
        ranked = sorted(units, key=lambda u: (math.log1p(u[2] or 0) + rng.gauss(0, 0.35), u[0]))
    elif order == "metro-last":
        big = sorted(units, key=lambda u: -(u[2] or 0))[:max(1, len(units) // 10)]
        ranked = sorted(units, key=lambda u: (u in big, rng.random()))
    else:
        ranked = sorted(units, key=lambda u: rng.random())
    at = {u[0]: _arrival_minutes((i + 1) / len(ranked)) for i, u in enumerate(ranked)} if ranked else {}
    steps, m, last = [], 0, max(at.values()) if at else 0
    while True:
        keep = {u for u, t in at.items() if t <= m}
        _write_step(dest, m, reader.reveal(files, keep, len(steps)))
        steps.append(m)
        if m >= last:
            break
        m += every
    return steps


def _write_step(dest, m, files):
    for rel, body in files.items():
        p = os.path.join(dest, f"{m:04d}", *rel.split("/"))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as fh:
            fh.write(body)


# ---------------------------------------------------------------------------------------------- a rehearsal run

class Run:
    """A rehearsal's own folder, database and clock, kept so a restart resumes the same night (the night went on while
    the program was stopped, as it would have)."""

    def __init__(self, folder, doc):
        self.folder, self.doc = folder, doc

    @classmethod
    def new(cls, base, election, states, speed, order, late, source, label, closes, hours, seed=7):
        rid = utcnow().strftime("%Y%m%d-%H%M%S") + "-" + "-".join(s.lower() for s in states)
        folder = os.path.join(base, rid)
        os.makedirs(folder, exist_ok=True)
        first = min(closes.values())
        doc = {"id": rid, "election": election, "states": states, "speed": speed, "order": order, "late": late, "source": source,
               "label": label, "closes": {k: iso(v) for k, v in closes.items()}, "night_start": iso(first - dt.timedelta(minutes=10)),
               "night_end": iso(first - dt.timedelta(minutes=10) + dt.timedelta(hours=hours)), "wall_start": iso(utcnow()), "hours": hours,
               "seed": seed, "saver": {}, "finished": False}
        r = cls(folder, doc)
        r.save()
        return r

    @classmethod
    def newest(cls, base):
        if not os.path.isdir(base):
            return None
        for n in sorted(os.listdir(base), reverse=True):
            p = os.path.join(base, n, "run.json")
            if os.path.exists(p):
                return cls(os.path.join(base, n), json.load(open(p, encoding="utf-8")))
        return None

    def save(self):
        tmp = os.path.join(self.folder, "run.json.part")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(self.doc, fh, indent=1)
        os.replace(tmp, os.path.join(self.folder, "run.json"))

    @property
    def clock(self):
        return ReplayClock(parse(self.doc["night_start"]), parse(self.doc["wall_start"]), self.doc["speed"])

    @property
    def db(self):
        return os.path.join(self.folder, "election.sqlite")

    def watch_folder(self, code):
        return os.path.join(self.folder, f"{code.lower()}_saves")

    @property
    def closes(self):
        return {k: parse(v) for k, v in self.doc["closes"].items()}

    @property
    def end(self):
        return parse(self.doc["night_end"])


# ---------------------------------------------------------------------------------------------- self-test

def selftest(tmp, say=print):
    """No network: the night clock; the saver on the reader's test files (every order, the summary lines adding up to
    the precincts, the last save equal to the source); a step replay with a made-up reader family."""
    import tempfile
    from election import store
    from election.readers import mn_media as M
    ok = True

    def expect(c, what):
        nonlocal ok
        say(f"      {'ok  ' if c else 'FAIL'} {what}")
        ok = ok and bool(c)

    c = ReplayClock(dt.datetime(2024, 11, 6, 1, 50, tzinfo=UTC), utcnow() - dt.timedelta(seconds=100), 6)
    expect(abs((c.now() - dt.datetime(2024, 11, 6, 2, 0, tzinfo=UTC)).total_seconds()) < 2, "the night clock runs six times as fast")
    base = tempfile.mkdtemp(prefix="replay_", dir=tmp)
    close = dt.datetime(2024, 11, 6, 2, 0, tzinfo=UTC)
    fixture = os.path.join(HERE, "election", "fixtures", "mn", "night")
    final, _info = M.read_folder(fixture)
    want = {(r["unit"], r["choice"]): r["votes"] for ct in final["contests"] for r in ct["rows"]}
    for order in ORDERS:
        out = os.path.join(base, order)
        s = MnSaver(fixture, out, close, order=order, seed=3)
        firsts = [s.at[v] for v in sorted(s.at, key=lambda v: s.at[v])]
        s.write(min(2, len(s.saves) - 1))
        reading, _ = M.read_folder(out)
        checks = {n: p for n, p, _d in store.run_checks(store.connect(":memory:"), reading)}
        part_in = sum(1 for r in reading["contests"][0]["reporting"] if r["unit"] != "all" and r["in"])
        expect(checks.get("units_add_up") and checks.get("structure") and 0 < part_in < len(s.precincts),
               f"{order}: a partial save reads cleanly and adds up ({part_in} of {len(s.precincts)} precincts in)")
        s.write(len(s.saves) - 1)
        reading, _ = M.read_folder(out)
        got = {(r["unit"], r["choice"]): r["votes"] for ct in reading["contests"] for r in ct["rows"]}
        expect(got == want and firsts == sorted(firsts), f"{order}: the last save equals the source")
    # a made-up family: two units, each reveal makes a JSON file with the units kept
    class Fake:
        @staticmethod
        def units(files):
            return [("u1", "001", 10), ("u2", "003", 500)]

        @staticmethod
        def reveal(files, keep, step):
            return {"example.gov/data.json": json.dumps({"in": sorted(keep), "v": step}).encode(), "example.gov/ver.txt": str(step).encode()}
    final_dir = os.path.join(base, "final")
    save_final([("https://example.gov/data.json", b'{"in":["u1","u2"]}')], final_dir)
    steps = make_steps("ZZ", Fake, final_dir, os.path.join(base, "steps"), order="small-first")
    clock = ReplayClock(close - dt.timedelta(minutes=5), utcnow(), 1)
    sr = StepReplay(os.path.join(base, "steps"), clock, {"ZZ": close}, {"example.gov": "ZZ"})
    st0, _b, _h = sr("https://example.gov/data.json")
    clock.night_start = close + dt.timedelta(minutes=steps[-1] + 1)
    st1, b1, _h = sr("https://example.gov/data.json")
    expect(st0 == 404 and st1 == 200 and json.loads(b1)["in"] == ["u1", "u2"] and len(steps) > 2,
           f"a feed state's past night is answered step by step ({len(steps)} steps; nothing before its polls closed)")
    shutil.rmtree(base, ignore_errors=True)
    return ok

