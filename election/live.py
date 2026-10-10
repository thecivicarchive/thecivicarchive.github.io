"""election/live.py - Election Night's cycle, and the night itself (ARCHITECTURE.md 3.2 to 3.8). run_night.py is its
front door; John starts it with "Start Election Night.bat" and stops it with "Stop Election Night.bat".

ONE CYCLE
  1. Results, live and care states: from about half an hour before a state's first poll closing, its cheap "what's new"
     address every 2 minutes (5 after 3 a.m. Central, 10 after 8 a.m.); before that once an hour, and whatever it
     carries then is a test: checked, never published. The data is fetched only when the version changed, kept raw
     (election_cache/<code>/<feed>/), read, checked and stored (election/store.py); a state's figures are never edited.
  2. Hand-saved files (Minnesota; Oklahoma once its reader exists): each watched folder is looked at every 30 seconds;
     a changed folder is read once it has been quiet for 45 seconds (John saves several files in a row), the same way.
  3. The feed, the forecasts and the measures, each on its own clock, in a thread of their own, once their modules
     exist (SECTIONS below); until then they are skipped and the status file says so.
  4. On the clock (every 10 minutes from 5 p.m. to 3 a.m. Central on election night, every 30 minutes before and
     until 8 a.m., hourly after): the snapshot folder, the history files and now.json (election/livejson.py), pruning,
     and publishing (election/publish.py) in a thread of its own.
  5. The log (logs/night_<date>.log: every request, snapshot and publish; never a feed's text or an account), one
     console line for each state that changed, and election_night_status.md, John's file to open.

WHAT A READER OFFERS (election/readers/<family>.py, the registry's "family"; phase 3's agents write them)
  A live or care state's reader:
    check(src, entry) -> {"version": str, "time": str or None} or None
        The cheap "what's new" request, through src (election.source.Source). None when nothing is posted for the
        election yet. entry is the state's registry entry; entry["election"]["nov3_id"] is the election to read (a
        rehearsal puts the past election's id there).
    fetch(src, entry, version) -> [(address, bytes), ...]
        The data files of that version, each request through src. The updater keeps every file raw, gzipped.
    read(files, entry) -> reading
        election.store's reading (store.run_checks says its shape), from those files, fields allowlisted; set
        "source_time" and "source_version" where the files state them, and "test": True when the file says its
        figures are test figures. Levels as the ballot databases have them ("congress" or "federal" for Congress,
        "statewide", "legislature", "court" ...), so that us.json carries the right races.
    A refused answer (src's Response.refused) is raised as election.source.Refused, no answer as SourceError.
  Optional: FEED (the store's feed id; default "<code>-<family>"), discover(src, entry) for `run_night.py discover`,
  certified(src, entry) -> ({race id: {choice key: votes}}, source, date) for `run_night.py certify`,
  selftest(say) -> bool for `run_night.py check`, and units(files) and reveal(files, keep, step) for rehearsals
  (election/replay.py).
  A hand state's reader offers read_folder(folder) -> (reading, info), info holding "files" (the names it read),
  "sha256" (over all of them), "saved_at" (the newest file's own time, or when it was saved) and "notes".
  A reader's file is read again when it changes, so a reader mended on the night is picked up without a restart.

WHAT THE OTHER SECTIONS OFFER (each skipped until its module exists; an import error inside one is reported)
  election.feeds.gdelt.poll, .rss.poll, .mastodon.poll, .youtube.poll, .measures.update
        called as fn(src=, now=, rehearsal=, say=) on their own clocks (SECTIONS); return a short dict for the log
  election.feeds.bluesky.start(src=, say=) -> an object with stop()
  election.feeds.measures.page_json(code or "US") -> the feed file of a state, or of the country
  election.feeds.measures.newest() -> {"t": UTC} or None (now.json's "fd")
  election.model.live_model.run(state=, now=, db=, rehearsal=, say=) after a state's new results (at most once a cycle)
  election.model.forecast.run_pre(now=, say=) once a day before results
  election.model.runs.page_json(code) -> a state's forecasts file; runs.history(code) -> {race id: history doc};
  runs.newest() -> {"t": UTC, "m": method version} or None (now.json's "fc")
"""

import collections
import ctypes
import datetime as dt
import gzip
import hashlib
import importlib
import json
import os
import re
import shutil
import sys
import threading
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from election import livejson, registry, store  # noqa: E402
from election.source import Refused, Source, SourceError, host_of  # noqa: E402

UTC = dt.timezone.utc
WORK = os.path.join(HERE, "election_cache", "live")
LIVE_ROOT = os.path.join(HERE, "site", "night-live")
STATUS_MD = os.path.join(HERE, "election_night_status.md")
LOG_DIR = os.path.join(HERE, "logs")
POLL_HOURS = os.path.join(HERE, "election", "poll_hours.json")
RAW = os.path.join(HERE, "election_cache")
ELECTION_DAY = dt.date(2026, 11, 3)

HAND_EVERY = 30              # seconds between looks at a watched folder (no network)
SETTLE = 45                  # a changed folder is read once it has been unchanged this long
PRE_CLOSE_EVERY = 3600       # a live state's "what's new" before its polls close (a test then)
WARM_UP = 30                 # minutes before a state's first poll closing when the night's cadence starts
STALE_AFTER = 3              # failures in a row before a state says its site has not answered
PARTIAL = (".crdownload", ".part", ".tmp", ".download", ".partial")
CENTRAL = "America/Chicago"

SECTIONS = {
    # name: (module, function, seconds between calls on election night, seconds in the day before)
    "gdelt": ("election.feeds.gdelt", "poll", 15 * 60, 15 * 60),
    "rss": ("election.feeds.rss", "poll", 10 * 60, 30 * 60),
    "mastodon": ("election.feeds.mastodon", "poll", 3 * 60, 3 * 60),
    "youtube": ("election.feeds.youtube", "poll", 30 * 60, 30 * 60),
    "measures": ("election.feeds.measures", "update", 5 * 60, 5 * 60),
}


# ============================================================================================== time

# Standard offsets (hours) of the zones the poll hours name, and whether they keep daylight time (US rules: from the
# second Sunday of March to the first Sunday of November, changing at 2 a.m. local). No time zone database is needed.
_ZONES = (("America/Phoenix", -7, False), ("Pacific/Honolulu", -10, False), ("America/Adak", -10, True),
          ("America/Anchorage", -9, True), ("America/Juneau", -9, True), ("America/Sitka", -9, True), ("America/Nome", -9, True),
          ("America/Yakutat", -9, True), ("America/Metlakatla", -9, True), ("America/Los_Angeles", -8, True), ("America/Denver", -7, True),
          ("America/Boise", -7, True), ("America/Chicago", -6, True), ("America/Menominee", -6, True), ("America/North_Dakota", -6, True),
          ("America/Indiana/Knox", -6, True), ("America/Indiana/Tell_City", -6, True), ("America/New_York", -5, True),
          ("America/Detroit", -5, True), ("America/Indiana", -5, True), ("America/Kentucky", -5, True), ("America/Puerto_Rico", -4, False))


def zone(tz):
    for name, off, dst in _ZONES:
        if tz == name or tz.startswith(name + "/"):
            return off, dst
    return -6, True


def _sunday(y, m, nth):
    d = dt.date(y, m, 1)
    d += dt.timedelta(days=(6 - d.weekday()) % 7)
    return d + dt.timedelta(weeks=nth - 1)


def utc_offset(tz, t):
    """Hours from UTC of the zone tz at the moment t (UTC)."""
    std, dst = zone(tz)
    if not dst:
        return std
    y = t.year
    start = dt.datetime.combine(_sunday(y, 3, 2), dt.time(2), UTC) - dt.timedelta(hours=std)          # 2 a.m. standard
    end = dt.datetime.combine(_sunday(y, 11, 1), dt.time(2), UTC) - dt.timedelta(hours=std + 1)       # 2 a.m. daylight
    return std + 1 if start <= t < end else std


def local(t, tz=CENTRAL):
    return (t + dt.timedelta(hours=utc_offset(tz, t))).replace(tzinfo=None)


def from_local(naive, tz=CENTRAL):
    """A wall-clock time in tz as UTC."""
    guess = naive.replace(tzinfo=UTC) - dt.timedelta(hours=zone(tz)[0])
    return naive.replace(tzinfo=UTC) - dt.timedelta(hours=utc_offset(tz, guess))


def clock_words(t, tz=CENTRAL, day=False):
    """'9:52 p.m.' (with 'Tue Nov 3, ' when day is asked for)."""
    if t is None:
        return "never"
    lt = local(t, tz)
    h = lt.hour % 12 or 12
    s = f"{h}:{lt.minute:02d} {'a.m.' if lt.hour < 12 else 'p.m.'}"
    return (lt.strftime("%a %b ") + str(lt.day) + ", " + s) if day else s


def utcnow():
    return dt.datetime.now(UTC)


def iso(t):
    return livejson.iso(t)


def parse(s):
    try:
        return dt.datetime.fromisoformat(str(s).replace("Z", "+00:00")) if s else None
    except ValueError:
        return None


def snapshot_every(night, day):
    """Minutes between snapshots: every 10 from 5 p.m. to 3 a.m. Central on the night, every 30 before and to 8 a.m.,
    hourly after (ARCHITECTURE.md 3.3)."""
    t = local(night)
    d0 = dt.datetime.combine(day, dt.time(17))
    if t < d0:
        return 30
    if t < d0 + dt.timedelta(hours=10):
        return 10
    if t < d0 + dt.timedelta(hours=15):
        return 30
    return 60


def next_snapshot(night, day):
    """The next moment on the clock (:00, :10 ...) after `night`, by snapshot_every."""
    m = snapshot_every(night, day)
    t = local(night)
    mins = t.hour * 60 + t.minute
    nxt = (mins // m + 1) * m
    nt = dt.datetime.combine(t.date(), dt.time()) + dt.timedelta(minutes=nxt)
    return from_local(nt)


def poll_floor(night, day):
    t = local(night)
    d0 = dt.datetime.combine(day, dt.time(17))
    if t < d0 + dt.timedelta(hours=10):
        return 120
    if t < d0 + dt.timedelta(hours=15):
        return 300
    return 600


# ============================================================================================== small helpers

def optional(name):
    """A module of another section, or None while it is not written. An error inside a module that exists is raised."""
    try:
        return importlib.import_module(name)
    except ModuleNotFoundError as e:
        if e.name and (name == e.name or name.startswith(e.name + ".")):
            return None
        raise


def pid_alive(pid):
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    if os.name == "nt":
        k32 = ctypes.WinDLL("kernel32")
        h = k32.OpenProcess(0x1000 | 0x00100000, False, pid)        # query limited information, synchronize
        if not h:
            return False
        code = ctypes.c_ulong(0)
        ok = k32.GetExitCodeProcess(h, ctypes.byref(code))
        k32.CloseHandle(h)
        return bool(ok) and code.value == 259                         # STILL_ACTIVE
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def sha_files(files):
    h = hashlib.sha256()
    for name, body in files:
        h.update(str(name).encode("utf-8") + b"\0" + body)
    return h.hexdigest()


def safe_name(s):
    s = re.sub(r"^https?://", "", str(s))
    return re.sub(r"[^A-Za-z0-9._-]+", "_", s)[-90:] or "file"


def hand_folder(entry):
    f = ((entry or {}).get("hand") or {}).get("folder")
    return os.path.join(HERE, *f.strip("/").split("/")) if f else None


COPY_MARK = re.compile(r"^(.*?)(?:\s\(\d+\))?(\.[A-Za-z0-9]{1,6})?$")


def newest_copies(folder, names):
    """The names to read: of a file saved more than once (a browser saves it again as "name (1).txt", "name (2).txt"),
    only the newest copy."""
    best = {}
    for n in names:
        m = COPY_MARK.match(n)
        key = ((m.group(1) if m else n) + ((m.group(2) or "") if m else "")).lower()
        try:
            t = os.path.getmtime(os.path.join(folder, n))
        except OSError:
            continue
        if key not in best or t > best[key][1]:
            best[key] = (n, t)
    return sorted(v[0] for v in best.values())


# ============================================================================================== the lock and the stop request

class Lock:
    """One updater at a time on a live folder: work/running.json names the running program."""

    def __init__(self, work):
        self.path = os.path.join(work, "running.json")
        self.stop_path = os.path.join(work, "stop.request")
        os.makedirs(work, exist_ok=True)

    def holder(self):
        try:
            doc = json.load(open(self.path, encoding="utf-8"))
        except (OSError, ValueError):
            return None
        return doc if pid_alive(doc.get("pid")) else None

    def take(self, mode, root):
        h = self.holder()
        if h and int(h.get("pid", 0)) != os.getpid():
            return False, h
        prev = None
        if os.path.exists(self.path):
            try:
                prev = json.load(open(self.path, encoding="utf-8"))
            except (OSError, ValueError):
                prev = {}
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump({"pid": os.getpid(), "started": iso(utcnow()), "mode": mode, "root": root}, fh)
        if os.path.exists(self.stop_path):
            os.remove(self.stop_path)
        return True, prev

    def release(self):
        for p in (self.path, self.stop_path):
            try:
                os.remove(p)
            except OSError:
                pass

    def stop_requested(self):
        return os.path.exists(self.stop_path)

    def request_stop(self):
        with open(self.stop_path, "w", encoding="utf-8") as fh:
            fh.write(iso(utcnow()))


# ============================================================================================== the night

class Night:
    """The updater. mode: "live" (the night), "once" (one cycle), "replay" (a rehearsal), "status" (no cycle)."""

    def __init__(self, mode="live", db=None, live_root=LIVE_ROOT, publish_root=LIVE_ROOT, work=WORK, clock=None, states=None,
                 src=None, say=print, status_path=STATUS_MD, log_path=None, day=ELECTION_DAY, label=None, raw_dir=RAW,
                 hand_folders=None, closes=None, end=None, sections=True, remote=None, publisher="auto", savers=None, run=None,
                 elections=None):
        from election import publish as P
        from election.replay import RealClock
        self.mode = mode
        self.rehearsal = mode == "replay"
        self.clock = clock or RealClock()
        self.day = day
        self.db_path = db or store.DB
        self.con = store.connect(self.db_path)
        self.lock = threading.Lock()
        self.work = work
        self.status_path = status_path
        self.log_path = log_path
        self.label = label
        self.raw_dir = raw_dir
        self.say = say
        self.end = end
        self.run_ = run
        self.savers = savers or {}
        self.elections = elections or {}
        self.live = livejson.LiveRoot(live_root, log=self.log)
        self.src = src or Source(log=self._source_log)
        self.sections_on = sections and mode in ("live", "once")
        if publisher == "auto":
            publisher = P.Publisher(source=publish_root, clone=P.CLONE if remote is None else os.path.join(work, "clone"),
                                    remote=remote, lock=self.lock, log=self.log, say=self.note,
                                    watch_path="rehearsal/now.json" if self.rehearsal else "now.json",
                                    history=os.path.join(work, "publish_log.jsonl"), src=Source(log=self._source_log))
        self.publisher = publisher
        self.reg = registry.load_all()
        try:
            self.poll = json.load(open(POLL_HOURS, encoding="utf-8"))["states"]
        except (OSError, ValueError, KeyError):
            self.poll = {}
        self.codes = [c.upper() for c in states] if states else sorted(self.reg)
        self.hand_override = {k.upper(): v for k, v in (hand_folders or {}).items()}
        self.close_override = {k.upper(): v for k, v in (closes or {}).items()}
        self.st = {}
        self.notes = collections.deque(maxlen=30)
        self.summ = {}
        self.last_snap = None
        self.next_snap = None
        self.started = utcnow()
        self.sections_state = {}
        self._model_queue = set()
        self._sec_stop = threading.Event()
        self._sec_thread = None
        self._bluesky = None
        self._pre_day = None
        self.awake = None
        self.awake_seen = None
        self._setup()

    # ------------------------------------------------------------------ log, notes, console
    def log(self, line):
        path = self.log_path or os.path.join(LOG_DIR, f"night_{dt.date.today().isoformat()}.log")
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(f"{dt.datetime.now().isoformat(timespec='seconds')} {'[rehearsal] ' if self.rehearsal else ''}{line}\n")
        except OSError:
            pass

    def _source_log(self, line):
        self.log(line)

    def note(self, text, console=True, at=None):
        """A plain sentence for John: the console, the status file's recent notes and the log. at: the moment it is
        about (the night clock's, in a rehearsal), when not now."""
        stamp = clock_words(at or (self.clock.now() if self.rehearsal else utcnow()))
        self.notes.append(f"{stamp} {text}")
        self.log(text)
        if console:
            self.say(("[rehearsal, night clock " + stamp + "] " if self.rehearsal else stamp + "  ") + text)

    def shown(self, t):
        """A time written into the figures (always the real time), as John should read it: in a rehearsal, the moment
        it was on the replayed night's clock."""
        if t is None or not self.rehearsal or not hasattr(self.clock, "night_start"):
            return t
        return self.clock.night_start + (t - self.clock.wall_start) * self.clock.speed

    # ------------------------------------------------------------------ the states
    def _setup(self):
        for code in self.codes:
            e = self.reg.get(code)
            if not e:
                continue
            kind = e.get("status")
            ph = self.poll.get(code) or {}
            first = self.close_override.get(code) or parse(ph.get("first_close_utc")) or dt.datetime.combine(self.day, dt.time(2), UTC)
            last = self.close_override.get(code) or parse(ph.get("last_close_utc")) or first
            s = {"entry": e, "kind": kind, "family": e.get("family"), "first_close": first, "last_close": last, "next": None,
                 "why": "", "note": "", "fails": 0, "fail_since": None, "refused": None, "fp_seen": None, "seen_at": None,
                 "fp_read": None, "last_version": None, "changed": False, "held_at": None, "mod": None, "mtime": None}
            if kind == "hand":
                s["folder"] = self.hand_override.get(code) or hand_folder(e)
            self.st[code] = s
            if kind in ("live", "care", "hand"):
                mod, why = self._reader(code)
                s["why"] = why
                s["feed"] = getattr(mod, "FEED", None) if mod else None
            s["feed"] = s.get("feed") or f"{code.lower()}-{e.get('family') or 'none'}"
            if kind in ("live", "care", "hand") and not s["why"]:
                store.ensure_election(self.con, code, kind="general", date=self.day.isoformat(),
                                      certifying_body=(e.get("certify") or {}).get("body"),
                                      certified_on=None, note=None)
                store.ensure_feed(self.con, code, s["feed"], s["family"], s.get("folder") or (e.get("cadence") or {}).get("signal") or "",
                                  kind, approved=bool(e.get("approved")))
                row = self.con.execute("SELECT source_version FROM snapshots WHERE state=? AND feed_id=? AND status IN ('ok','held','same') "
                                       "AND source_version IS NOT NULL ORDER BY snapshot_id DESC LIMIT 1", (code, s["feed"])).fetchone()
                s["last_version"] = row[0] if row else None
                stopped = [h for h in (e.get("cadence") or {}).get("hosts", []) if self.src.stopped(h)]
                if stopped:
                    s["refused"] = f"{stopped[0]} refused a request earlier tonight"

    def entry(self, code):
        """The registry entry, with a rehearsal's past election id put in its place."""
        e = self.st[code]["entry"]
        if code in self.elections:
            e = dict(e, election=dict(e.get("election") or {}, nov3_id=self.elections[code]))
        return e

    def _reader(self, code):
        """The state's reader module, read again when its file changed (a reader mended on the night is picked up)."""
        s = self.st.get(code)
        fam = (s or {}).get("family") or (self.reg.get(code) or {}).get("family")
        kind = (s or {}).get("kind") or (self.reg.get(code) or {}).get("status")
        if not fam or not re.fullmatch(r"[a-z0-9_]+", fam):
            return None, "no reader is named for it"
        path = os.path.join(HERE, "election", "readers", fam + ".py")
        if not os.path.exists(path):
            return None, "its reader is not written yet"
        mtime = os.path.getmtime(path)
        mod = s.get("mod") if s else None
        try:
            if mod is None:
                mod = importlib.import_module(f"election.readers.{fam}")
            elif s.get("mtime") != mtime:
                mod = importlib.reload(mod)
                self.note(f"{code}: its reader changed on disk and was read again")
        except Exception as e:  # noqa: BLE001 - a broken reader holds its state, never the night
            if s is not None:
                s["mtime"] = mtime
            return None, f"its reader did not load ({e.__class__.__name__}: {str(e)[:160]})"
        if s is not None:
            s["mod"], s["mtime"] = mod, mtime
        need = ("read_folder",) if kind == "hand" else ("check", "fetch", "read")
        missing = [f for f in need if not hasattr(mod, f)]
        if missing:
            return None, f"its reader does not offer {', '.join(missing)} yet"
        return mod, ""

    # ------------------------------------------------------------------ one look at everything that is due
    def step(self, force=False):
        now = self.clock.now()
        for code, saver in self.savers.items():
            self._tick_saver(code, saver, now)
        for code, s in self.st.items():
            if s["kind"] not in ("live", "care", "hand"):
                continue
            if not force and s["next"] and now < s["next"]:
                continue
            if s["kind"] == "hand":
                s["next"] = now + dt.timedelta(seconds=HAND_EVERY)
                self.look_folder(code, now, force=force)
            else:
                warm = s["first_close"] - dt.timedelta(minutes=WARM_UP)
                every = PRE_CLOSE_EVERY if now < warm else max(int((s["entry"].get("cadence") or {}).get("check_every_s") or 120),
                                                              poll_floor(now, self.day))
                s["next"] = min(now + dt.timedelta(seconds=every), warm) if now < warm else now + dt.timedelta(seconds=every)
                if not s["refused"]:
                    self.poll_state(code, now)

    def _tick_saver(self, code, saver, now):
        i = saver.due(now)
        done = (self.run_.doc.get("saver") or {}).get(code, -1) if self.run_ else getattr(saver, "_done", -1)
        if i > done:
            n_in, n_all = saver.write(i)
            if self.run_:
                self.run_.doc.setdefault("saver", {})[code] = i
                self.run_.save()
            else:
                saver._done = i
            self.note(f"{code}: the rehearsal saved the results files, as John would ({n_in:,} of {n_all:,} precincts in)", console=True)

    # ------------------------------------------------------------------ a state read by a program
    def poll_state(self, code, now):
        s = self.st[code]
        reader, why = self._reader(code)
        if not reader:
            s["why"] = why
            return None
        s["why"] = ""
        e = self.entry(code)
        try:
            sig = reader.check(self.src, e)
        except Refused as ex:
            return self._refused(code, ex)
        except SourceError as ex:
            return self._failed(code, str(ex))
        except Exception as ex:  # noqa: BLE001 - the reader broke: the state is held, the night goes on
            return self._broke(code, "asking what is new", ex)
        if not sig:
            self._answered(code)
            s["note"] = "nothing posted for this election yet"
            return None
        version = str(sig.get("version"))
        if version == s["last_version"]:
            self._answered(code)
            return "same"
        try:
            files = reader.fetch(self.src, e, version)
        except Refused as ex:
            return self._refused(code, ex)
        except SourceError as ex:
            return self._failed(code, str(ex))
        except Exception as ex:  # noqa: BLE001
            return self._broke(code, "fetching", ex)
        if not files:
            return self._failed(code, "the data files came back empty")
        files = [(str(n), b if isinstance(b, (bytes, bytearray)) else str(b).encode("utf-8")) for n, b in files]
        sha = sha_files(files)
        raw = self._keep_raw(code, s["feed"], files, sha)
        try:
            reading = reader.read(files, e)
        except Exception as ex:  # noqa: BLE001
            reading = {"state": code, "feed": s["feed"], "contests": [], "unmatched": [],
                       "problems": [f"the file did not read ({ex.__class__.__name__}: {str(ex)[:200]})"]}
        status = self._store(code, reading, sha, raw, reading.get("source_time") or sig.get("time"), version, now)
        if status in ("ok", "same", "held", "test"):
            s["last_version"] = version
        return status

    def _answered(self, code):
        s = self.st[code]
        if s["fails"] >= STALE_AFTER:
            self.note(f"{code}: the state's site is answering again")
        s["fails"], s["fail_since"] = 0, None
        store.feed_outcome(self.con, code, s["feed"], True)

    def _failed(self, code, why):
        s = self.st[code]
        store.failed_snapshot(self.con, code, s["feed"], "failed", why[:300])
        store.feed_outcome(self.con, code, s["feed"], False, why[:200])
        s["fails"] += 1
        s["fail_since"] = s["fail_since"] or self.clock.now()
        self.log(f"{code}: no answer ({why[:200]}); {s['fails']} in a row")
        if s["fails"] == STALE_AFTER:
            self.note(f"{code}: the state's site has not answered since {clock_words(s['fail_since'])}; its last figures stay, with their time")
        return "failed"

    def _refused(self, code, ex):
        s = self.st[code]
        why = getattr(ex, "why", str(ex))
        store.failed_snapshot(self.con, code, s["feed"], "refused", str(ex)[:300])
        store.feed_outcome(self.con, code, s["feed"], False, f"refused: {why}"[:200])
        s["refused"] = why
        self.note(f"{code}: the state's site refused this request ({why}); it is not asked again tonight, and its page links to the "
                  f"state's own results")
        return "refused"

    def _broke(self, code, doing, ex):
        s = self.st[code]
        self.note(f"{code}: its reader failed while {doing} ({ex.__class__.__name__}: {str(ex)[:160]}); the state's last good figures stay. "
                  f"Mend election/readers/{s['family']}.py and test it with: run_night.py once --state {code.lower()} --from-file <the raw file>")
        s["held_at"] = s["held_at"] or self.clock.now()
        return "held"

    # ------------------------------------------------------------------ a folder John saves files into
    def look_folder(self, code, now, force=False):
        s = self.st[code]
        folder = s.get("folder")
        if not folder or not os.path.isdir(folder):
            s["note"] = "the folder for the saved files is not there yet"
            return None
        try:
            names = [n for n in os.listdir(folder) if os.path.isfile(os.path.join(folder, n)) and not n.startswith(".")
                     and n.lower() not in ("desktop.ini", "thumbs.db")]
        except OSError:
            return None
        if any(n.lower().endswith(PARTIAL) for n in names):
            s["note"] = "a file is still being saved"
            return None
        fp = []
        for n in sorted(names):
            try:
                stt = os.stat(os.path.join(folder, n))
                fp.append((n, stt.st_size, stt.st_mtime_ns))
            except OSError:
                return None
        fp = tuple(fp)
        if fp == s["fp_read"] and not force:
            return None
        if not force:
            if fp != s["fp_seen"]:
                s["fp_seen"], s["seen_at"] = fp, now
                return None
            if (now - s["seen_at"]).total_seconds() < SETTLE:
                return None
        reader, why = self._reader(code)
        if not reader:
            s["why"] = why
            s["fp_read"] = fp
            return None
        s["why"] = ""
        read_from = folder
        keep = newest_copies(folder, names)
        if len(keep) < len(names):
            # the same file saved more than once: read the newest copy of each, from a folder of their own
            read_from = os.path.join(self.work, "stage", code.lower())
            shutil.rmtree(read_from, ignore_errors=True)
            os.makedirs(read_from, exist_ok=True)
            for n in keep:
                shutil.copy2(os.path.join(folder, n), os.path.join(read_from, n))
            self.log(f"{code}: {len(names) - len(keep)} older copies of files saved again are set aside; the newest of each is read")
        try:
            reading, info = reader.read_folder(read_from)
        except Exception as ex:  # noqa: BLE001
            s["fp_read"] = fp
            return self._broke(code, "reading the saved files", ex)
        s["fp_read"] = fp
        if not info.get("files"):
            s["note"] = "no results files in the folder yet"
            return None
        s["note"] = ""
        files = [(n, open(os.path.join(read_from, n), "rb").read()) for n in info["files"] if os.path.exists(os.path.join(read_from, n))]
        raw = self._keep_raw(code, s["feed"], files, info.get("sha256") or sha_files(files))
        for n in (info.get("notes") or [])[:5]:
            self.log(f"{code}: {n}")
        return self._store(code, reading, info.get("sha256") or sha_files(files), raw, info.get("saved_at"), None, now)

    # ------------------------------------------------------------------ storing a reading
    def _keep_raw(self, code, feed, files, sha):
        """Every file read, kept whole (gzipped) for audit under election_cache/<code>/<feed>/<UTC>-<sha8>/; never published."""
        stamp = utcnow().strftime("%Y%m%dT%H%M%SZ")
        folder = os.path.join(self.raw_dir, code.lower(), feed, f"{stamp}-{(sha or 'none')[:8]}")
        try:
            os.makedirs(folder, exist_ok=True)
            manifest = []
            for i, (name, body) in enumerate(files):
                fn = f"{i:03d}-{safe_name(name)}.gz"
                with gzip.open(os.path.join(folder, fn), "wb", compresslevel=6) as fh:
                    fh.write(body)
                manifest.append({"name": name, "file": fn, "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()})
            with open(os.path.join(folder, "manifest.json"), "w", encoding="utf-8") as fh:
                json.dump({"state": code, "feed": feed, "kept": iso(utcnow()), "files": manifest}, fh, indent=1)
        except OSError as e:
            self.log(f"{code}: the raw files could not be kept ({e.__class__.__name__})")
        return folder

    def _store(self, code, reading, sha, raw, source_time, version, now):
        s = self.st[code]
        test = now < s["first_close"] or bool(reading.get("test"))
        reading = dict(reading, state=code, feed=s["feed"])
        if test:
            checks = store.run_checks(self.con, reading)
            sid, _st = store.begin_snapshot(self.con, code, s["feed"], None, raw_path=raw, source_time=source_time, source_version=version,
                                            test=True, note=f"read before the polls closed; never published; sha256 {sha}")
            with self.con:
                self.con.executemany("INSERT INTO checks (snapshot_id, check_name, passed, detail) VALUES (?,?,?,?)",
                                     [(sid, n, 1 if p else 0, d) for n, p, d in checks])
            store.end_snapshot(self.con, sid, "test", rows=0)
            self._answered(code)
            good = all(p for n, p, _d in checks if n in store.HARD)
            s["note"] = f"a test file before the polls closed ({'it reads cleanly' if good else 'it does not read cleanly'}); never published"
            self.log(f"{code} test snapshot {sid}: version {version}; " + "; ".join(f"{n} {'ok' if p else 'FAIL'}" for n, p, _d in checks))
            return "test"
        sid, status = store.begin_snapshot(self.con, code, s["feed"], sha, raw_path=raw, source_time=source_time, source_version=version)
        if status == "same":
            store.end_snapshot(self.con, sid, "same", rows=0)
            self._answered(code)
            return "same"
        status, checks = store.record(self.con, sid, reading)
        self._answered(code)
        rows = self.con.execute("SELECT rows FROM snapshots WHERE snapshot_id=?", (sid,)).fetchone()[0]
        self.log(f"{code} snapshot {sid}: {status}; version {version}; {rows or 0} changed numbers; " +
                 "; ".join(f"{n} {'ok' if p else 'FAIL'}" for n, p, _d in checks))
        if status == "ok":
            s["changed"] = True
            s["held_at"] = None
            self._model_queue.add(code)
            um = reading.get("unmatched") or []
            if um:
                self.log(f"{code}: {len(um)} contests in the file are listed, not shown: " + "; ".join(f"{u.get('office')} ({u.get('why')})" for u in um[:8]))
        else:
            first = s["held_at"] is None
            s["held_at"] = s["held_at"] or now
            bad = [d for n, p, d in checks if not p and n in store.HARD]
            if first:
                self.note(f"{code}: the state's file changed tonight; figures held as of the last good file. Why: {'; '.join(bad)[:300]}. "
                          f"The raw file is kept in {os.path.relpath(raw, HERE)}")
        return status

    # ------------------------------------------------------------------ the state of a count, in a word
    def status_word(self, code, now=None):
        now = now or self.clock.now()
        s = self.st.get(code)
        if not s or s["kind"] == "link":
            return "link"
        summ = self.summ.get(code)
        if s["refused"]:
            return "refused"
        if s["why"] and not summ:
            return "link"
        if s["kind"] != "hand" and s["fails"] >= STALE_AFTER:
            return "stale"
        last = self.con.execute("SELECT status FROM snapshots WHERE state=? AND feed_id=? AND status IN ('ok','held') "
                                "ORDER BY snapshot_id DESC LIMIT 1", (code, s["feed"])).fetchone()
        if (last and last[0] == "held") or (s["held_at"] and summ):
            return "held"
        if summ:
            if summ.get("official"):
                return "official"
            if summ.get("done"):
                return "done"
            return "counting"
        if now < s["last_close"]:
            return "wait"
        return "none"

    # ------------------------------------------------------------------ the snapshot
    def snapshot(self, run="running", publish=True, wait=False):
        """Writes the snapshot folder (when the figures changed) and now.json, prunes, and asks for a publish."""
        t0 = time.monotonic()
        wall = utcnow()
        night = self.clock.now()
        with self.lock:
            files, summ = livejson.results_files(self.con, [c for c in self.codes if c in self.st])
            self.summ = summ
            extra, hist, fc, fd = self._section_files()
            files.update(extra)
            seq, base, new = self.live.write_snapshot(files)
            states = {}
            for code in self.codes:
                if code not in self.st:
                    continue
                w = self.status_word(code, night)
                ent = {"s": w}
                if code in summ:
                    ent.update(t=summ[code]["at"], f=f"{code.lower()}.json", by="hand" if self.st[code]["kind"] == "hand" else "feed")
                states[code] = ent
            nxt = None
            if run == "running" and self.next_snap:
                speed = getattr(self.clock, "speed", 1.0)
                nxt = self.next_snap if speed == 1 else wall + dt.timedelta(seconds=max(0.0, (self.next_snap - night).total_seconds()) / speed)
            doc = livejson.now_doc(seq, base, wall, nxt, run, states, rehearsal=self.rehearsal, label=self.label, fc=fc, fd=fd)
            nbytes = self.live.write_now(doc)
            nh = self.live.write_history(hist) if hist else 0
            keep = self.publisher.recent_seqs(livejson.KEEP_PUBLISHED_MINUTES) if self.publisher else set()
            gone = self.live.prune(keep)
        if self.awake is not None and self.awake.ok:
            held, detail = self.awake.check()
            self.awake_seen = (held, utcnow())
            if not held:
                self.note("the request that keeps the computer awake is no longer in place: " + detail)
        over = livejson.over_budget(files)
        size = sum(len(v.encode("utf-8")) if isinstance(v, str) else len(v) for v in files.values())
        self.last_snap = {"seq": seq, "new": new, "at": wall, "night": night, "files": len(files), "bytes": size, "over": over,
                          "now_bytes": nbytes, "seconds": round(time.monotonic() - t0, 2), "run": run, "pruned": gone, "history": nh}
        self.log(f"snapshot {seq} ({'new folder' if new else 'figures unchanged; pointer refreshed'}): {len(files)} files, "
                 f"{size / 1e6:.2f} MB, now.json {nbytes} bytes, run {run}, written in {self.last_snap['seconds']} s; pruned {gone or 'none'}")
        for rel, n, b in over:
            self.log(f"over budget: {rel} {n / 1e3:,.0f} KB (budget {b / 1e3:,.0f} KB)")
        changed = [c for c, s in self.st.items() if s["changed"]]
        for code in changed:
            self.st[code]["changed"] = False
            u = summ.get(code, {}).get("units")
            unit = str(self.st[code]["entry"].get("units") or "unit").split()[0]
            words = f"{u[0]:,} of {u[1]:,} {unit}s in" if u else "figures read"
            self.note(f"{code}: {words} (figures as of {clock_words(self.shown(parse(summ.get(code, {}).get('at'))))})", at=night)
        if publish and self.publisher is not None and self.publisher.enabled:
            if wait:
                self.publisher.stop(wait=True, timeout=600)
                e = self.publisher.publish_now(seq, wall, label="updates paused" if run != "running" else "")
                self.note(("published: " if e.get("ok") else "publishing did not go through: ") + (
                    f"snapshot {seq}, {e.get('seconds')} s after it was written" if e.get("ok") else str(e.get("why"))), at=night)
            else:
                self.publisher.request(seq, wall)
        if self.mode != "status":
            states_line = collections.Counter(states[c]["s"] for c in states)
            self.say(f"{'[rehearsal, night clock ' + clock_words(night) + '] ' if self.rehearsal else clock_words(wall) + '  '}"
                     f"snapshot {seq}{'' if new else ' (unchanged)'}: " + ", ".join(f"{n} {w}" for w, n in sorted(states_line.items())) +
                     (f"; next at {clock_words(self.next_snap)}" if run == "running" and self.next_snap else f"; run {run}") +
                     ("" if not self.publisher or self.publisher.enabled else "; not published (publishing is off)"))
        self.write_status()
        return self.last_snap

    def _section_files(self):
        """The forecasts' and the feed's files, history and pointers, from the sections that exist."""
        files, hist, fc, fd = {}, {}, None, None
        try:
            runs = optional("election.model.runs")
            if runs is not None:
                for code in self.codes:
                    if hasattr(runs, "page_json"):
                        doc = runs.page_json(code)
                        if doc:
                            files[f"fc/{code.lower()}.json"] = livejson.dumps(doc)
                    if hasattr(runs, "history"):
                        for rid, d in (runs.history(code) or {}).items():
                            hist[f"{code.lower()}/{rid}.json"] = livejson.dumps(d)
                fc = runs.newest() if hasattr(runs, "newest") else None
            meas = optional("election.feeds.measures")
            if meas is not None and hasattr(meas, "page_json"):
                for code in ["US"] + self.codes:
                    doc = meas.page_json(code)
                    if doc:
                        files[f"feed/{code.lower()}.json"] = livejson.dumps(doc)
                fd = meas.newest() if hasattr(meas, "newest") else None
        except Exception as e:  # noqa: BLE001 - a section's failure never stops the results
            self.note(f"a section's files could not be written this time ({e.__class__.__name__}: {str(e)[:160]}); the results go out without them")
        return files, hist, fc, fd

    # ------------------------------------------------------------------ the other sections, in a thread of their own
    def _start_sections(self):
        if not self.sections_on:
            return
        bs = None
        try:
            bs = optional("election.feeds.bluesky")
        except Exception as e:  # noqa: BLE001
            self.note(f"the Bluesky collector did not load ({e.__class__.__name__}); the feed goes on without it")
        if bs is not None and hasattr(bs, "start"):
            try:
                self._bluesky = bs.start(src=self.src, say=lambda t: self.note(t, console=False))
                self.sections_state["bluesky"] = "running"
            except Exception as e:  # noqa: BLE001
                self.sections_state["bluesky"] = f"did not start ({e.__class__.__name__})"
        self._sec_thread = threading.Thread(target=self._sections_loop, name="sections", daemon=True)
        self._sec_thread.start()

    def _stop_sections(self):
        self._sec_stop.set()
        if self._bluesky is not None:
            try:
                self._bluesky.stop()
            except Exception:  # noqa: BLE001
                pass
        if self._sec_thread is not None:
            self._sec_thread.join(60)

    def _sections_loop(self):
        due = {}
        while not self._sec_stop.is_set():
            self.sections_tick(due)
            self._sec_stop.wait(5)

    def sections_tick(self, due=None):
        """Every section whose time has come, once. Returns what was called."""
        due = due if due is not None else {}
        now = self.clock.now()
        before = local(now) < dt.datetime.combine(self.day, dt.time(17))
        called = []
        for name, (modname, fn, every_night, every_before) in SECTIONS.items():
            if due.get(name) and now < due[name]:
                continue
            due[name] = now + dt.timedelta(seconds=every_before if before else every_night)
            try:
                mod = optional(modname)
            except Exception as e:  # noqa: BLE001
                self.sections_state[name] = f"did not load ({e.__class__.__name__}: {str(e)[:120]})"
                continue
            if mod is None or not hasattr(mod, fn):
                self.sections_state[name] = "not there yet"
                continue
            try:
                out = getattr(mod, fn)(src=self.src, now=now, rehearsal=self.rehearsal, say=lambda t: self.note(t, console=False))
                self.sections_state[name] = f"ran at {clock_words(utcnow())}"
                self.log(f"{name}: {json.dumps(out)[:300] if out else 'done'}")
                called.append(name)
            except Exception as e:  # noqa: BLE001
                self.sections_state[name] = f"failed at {clock_words(utcnow())} ({e.__class__.__name__})"
                self.log(f"{name} failed: {e.__class__.__name__}: {str(e)[:200]}")
        try:
            lm = optional("election.model.live_model")
            fm = optional("election.model.forecast")
        except Exception as e:  # noqa: BLE001
            self.sections_state["forecasts"] = f"did not load ({e.__class__.__name__})"
            return called
        if lm is None and fm is None:
            self.sections_state["forecasts"] = "not there yet"
            return called
        queue, self._model_queue = self._model_queue, set()
        for code in sorted(queue):
            if lm is not None and hasattr(lm, "run"):
                try:
                    lm.run(state=code, now=now, db=self.db_path, rehearsal=self.rehearsal, say=lambda t: self.note(t, console=False))
                    self.sections_state["forecasts"] = f"{code} ran at {clock_words(utcnow())}"
                    called.append(f"model {code}")
                except Exception as e:  # noqa: BLE001
                    self.sections_state["forecasts"] = f"{code} failed ({e.__class__.__name__})"
                    self.log(f"model {code} failed: {e.__class__.__name__}: {str(e)[:200]}")
        today = local(now).date()
        if fm is not None and hasattr(fm, "run_pre") and not self.summ and self._pre_day != today:
            self._pre_day = today
            try:
                fm.run_pre(now=now, say=lambda t: self.note(t, console=False))
                called.append("pre-election forecast")
            except Exception as e:  # noqa: BLE001
                self.log(f"pre-election forecast failed: {e.__class__.__name__}: {str(e)[:200]}")
        return called

    # ------------------------------------------------------------------ the night
    def run(self, lock=None):
        """Cycles until a stop is asked for (Stop Election Night.bat, Ctrl+C) or a rehearsal's night ends."""
        from election.awake import Awake
        lock = lock or Lock(self.work)
        took, prev = lock.take(self.mode, self.live.root)
        if not took:
            self.say(f"Election Night is already running (since {clock_words(parse(prev.get('started')), day=True)}, program {prev.get('pid')}). "
                     "Use its window, or Stop Election Night.bat.")
            return 2
        if prev and prev.get("pid") and not pid_alive(prev.get("pid")):
            self.note("the last run ended without stopping (the window was closed or the computer stopped); resuming from the databases")
        awake = Awake("Election Night is reading and publishing results").start()
        self.awake = awake
        self.note(awake.how)
        if self.publisher is not None:
            self.note(self.publisher.describe())
            self.publisher.start()
        reason = "end"
        try:
            self._start_sections()
            self.step(force=True)
            self.next_snap = next_snapshot(self.clock.now(), self.day)
            self.snapshot("running")
            while True:
                if lock.stop_requested():
                    reason = "stop"
                    break
                now = self.clock.now()
                if self.end and now >= self.end:
                    reason = "end"
                    break
                self.step()
                if now >= self.next_snap:
                    self.next_snap = next_snapshot(now, self.day)
                    self.snapshot("running")
                time.sleep(0.5 if getattr(self.clock, "speed", 1) > 1 else 1.0)
        except KeyboardInterrupt:
            reason = "stop"
        finally:
            self._stop_sections()
            word = "stopped" if reason == "end" else "paused"
            self.note("stopping: the last figures go out with 'updates paused'" if word == "paused" else
                      "the rehearsal's night is over: the last figures go out")
            try:
                if self.rehearsal and self.run_:
                    self.run_.doc["finished"] = reason == "end"
                    self.run_.save()
                self.snapshot(word, publish=True, wait=True)
            finally:
                awake.stop()
                lock.release()
                self.write_status(stopped=True)
        return 0

    def once(self, publish=False):
        """One cycle: every state read now, every section once, a snapshot, and a publish when asked for."""
        self.step(force=True)
        if self.sections_on:
            self.sections_tick({})
        self.next_snap = None
        snap = self.snapshot("paused", publish=publish, wait=True)
        return snap

    # ------------------------------------------------------------------ John's file
    def write_status(self, stopped=False):
        now = self.clock.now()
        L = ["# Election Night: where things stand", ""]
        L.append(f"Written {clock_words(utcnow(), day=True)} (Central time) by the updater. Open it again for the newest; it is rewritten "
                 f"after every snapshot.")
        L.append("")
        if self.rehearsal:
            L.append(f"- **Rehearsal**: replayed figures from {self.label}, {getattr(self.clock, 'speed', 1):g} times as fast as real time "
                     f"(the replayed night's clock: {clock_words(now, day=True)}; the times below are on that clock, except when the "
                     f"program started). Written only to the rehearsal folder; pages show it only with #rehearsal in their address.")
        if self.mode in ("live", "replay"):
            L.append(f"- **{'Stopped' if stopped else 'Running'}** since {clock_words(self.started, day=True)}" +
                     (f"; stopped {clock_words(utcnow(), day=True)}" if stopped else ""))
        elif self.mode == "once":
            L.append("- **One cycle** (Update Election Night once): read everything once and wrote one snapshot.")
        else:
            L.append("- **Not running.** Double-click Start Election Night.bat to start it (John's step on Mon Nov 2 at 6 p.m.).")
        pub = self.publisher
        if pub is None or not pub.enabled:
            L.append("- **Publishing: off.** " + (pub.why_off if pub else "no publisher") + ". The figures are written on this computer "
                     "(site/night-live/); `run_night.py preview` shows them at http://127.0.0.1:8791/dev/night/.")
        else:
            last = pub.last or {}
            L.append(f"- **Publishing**: {pub.describe()}. Last: " + (
                f"snapshot {last.get('seq')} sent {clock_words(self.shown(parse(last.get('pushed'))))}, {last.get('seconds')} s after it was written"
                if last.get("ok") else (f"did not go through ({last.get('why')})" if last else "nothing sent yet")))
            if pub.measured:
                m = pub.measured[-1]
                L.append(f"- **Measured**: snapshot {m['seq']} was seen at the live address {m['minutes']} minutes after it was written.")
        if self.awake is not None:
            held = self.awake_seen[0] if self.awake_seen else self.awake.ok
            L.append(f"- **Sleep**: " + ("the computer is asked not to sleep while this runs (the request read back as held at "
                                         f"{clock_words(self.shown(self.awake_seen[1])) if self.awake_seen else 'start'})" if held and not stopped else
                                         "the request ended with the run" if stopped else self.awake.how))
        if self.last_snap:
            sn = self.last_snap
            L.append(f"- **Snapshot {sn['seq']}** ({'new figures' if sn['new'] else 'figures unchanged'}): {sn['files']} files, "
                     f"{sn['bytes'] / 1e6:.1f} MB, written at {clock_words(self.shown(sn['at']))}" +
                     (f"; next at {clock_words(self.next_snap)}" if self.next_snap and not stopped and self.mode != "once" else ""))
            for rel, n, b in sn["over"][:6]:
                L.append(f"  - over its size budget: {rel}, {n / 1e3:,.0f} KB (budget {b / 1e3:,.0f} KB)")
        L += ["", "## States", "", "| State | How it is read | Now | Figures as of | Reported | Note |", "| --- | --- | --- | --- | --- | --- |"]
        how = {"live": "read live", "care": "read with care", "hand": "John saves the files", "link": "linked, not read"}
        words = {"wait": "polls open", "none": "no votes yet", "counting": "counting", "done": "every unit in", "official": "certified",
                 "held": "figures held", "stale": "site not answering", "link": "not read here", "refused": "site refused"}
        for code in self.codes:
            s = self.st.get(code)
            if not s:
                continue
            w = self.status_word(code, now)
            sm = self.summ.get(code) or {}
            u = sm.get("units")
            note = s["why"] or (f"refused: {s['refused']}" if s["refused"] else s["note"])
            if s["kind"] == "hand" and s.get("folder"):
                note = (note + "; " if note else "") + "files go in " + os.path.relpath(s["folder"], HERE)
            L.append(f"| {code} | {how.get(s['kind'], s['kind'])} | {words.get(w, w)} | {clock_words(self.shown(parse(sm.get('at'))), day=True) if sm.get('at') else ''} "
                     f"| {f'{u[0]:,} of {u[1]:,}' if u else ''} | {note} |")
        L += ["", "## What waits on John", ""]
        waits = []
        if pub is None or not pub.enabled:
            waits.append("Create the public repository for the live figures (D1), switch on its Pages (main branch, root), and say its "
                         "name; until then nothing is published.")
        for code in self.codes:
            s = self.st.get(code)
            if s and s["kind"] == "hand" and code in self.savers:
                continue                                  # a rehearsal saves the replayed files itself, as John would
            if s and s["kind"] == "hand":
                has = s.get("folder") and os.path.isdir(s["folder"]) and any(os.scandir(s["folder"]))
                waits.append(f"{code}: on the night, save the files into {os.path.relpath(s['folder'], HERE) if s.get('folder') else '(no folder)'}"
                             + (" (it is empty now)" if not has else "") + (f"; {s['why']}" if s["why"] else ""))
        try:
            acc = optional("election.feeds.accounts")
            if acc is not None and hasattr(acc, "posts_may_be_shown") and not acc.posts_may_be_shown():
                waits.append("The site's public contact address (D8): no official social post is shown until it exists.")
        except Exception:  # noqa: BLE001
            pass
        L += [f"- {w}" for w in waits] or ["- Nothing."]
        L += ["", "## The other sections", ""]
        for name in list(SECTIONS) + ["bluesky", "forecasts"]:
            L.append(f"- {name}: {self.sections_state.get(name, 'not asked yet' if self.sections_on else 'not run in this mode')}")
        if self.notes:
            L += ["", "## Recent notes", ""] + [f"- {n}" for n in list(self.notes)[-15:]]
        text = "\n".join(L) + "\n"
        if self.status_path:
            try:
                tmp = self.status_path + ".part"
                with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
                    fh.write(text)
                os.replace(tmp, self.status_path)
            except OSError:
                pass
        return text
