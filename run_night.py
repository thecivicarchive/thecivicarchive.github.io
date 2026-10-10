#!/usr/bin/env python3
"""
run_night.py - Election Night's one command (ARCHITECTURE.md 3.1). John starts the night with
"Start Election Night.bat" (Mon Nov 2, 6 p.m.) and stops it with "Stop Election Night.bat".

    python run_night.py check                  Python, the databases, the registry, the never lists, every reader's
                                               self-test, the updater's own self-tests. Downloads nothing.
    python run_night.py build [--practice]     the Night pages that exist (practice figures only to site/practice/)
    python run_night.py discover               each live state's reader looks for its Nov 3 election (one request a
                                               state); prints what is found and what is missing
    python run_night.py once [--publish] [--state xx] [--from-file <raw file or folder>]
                                               one cycle (Update Election Night once.bat); --from-file tests a mended
                                               reader on a held file
    python run_night.py live                   the night: cycles until stopped (Start Election Night.bat)
    python run_night.py stop                   asks the running updater to finish, publish "updates paused" and stop
                                               (Stop Election Night.bat)
    python run_night.py replay --election 2024-11-05 [--states mn] [--speed 6] [--order random|small-first|metro-last]
                               [--late] [--source fixture|2024-senate|saved:<yyyymmdd>] [--hours 12] [--resume]
                                               a past election as if live, to the rehearsal folder (/night-live/rehearsal/)
    python run_night.py preview                serves site/ at http://127.0.0.1:8791/ (the draft and the live figures
                                               side by side, as on GitHub)
    python run_night.py status                 rewrites election_night_status.md
    python run_night.py forecast               the day's pre-election forecasts (Minnesota and the other states), each
                                               stored as a version; the updater runs them once a day by itself
    python run_night.py scan                   the built pages and live files: contact-like text, social accounts not
                                               on the official list, names of the kit's files
    python run_night.py certify <code> [--folder <saved certified files>] [--date yyyy-mm-dd]
                                               a state's certified results after its canvass
    python run_night.py publish [--setup]      publishes the live folder now (once John has named the repository)
    python run_night.py folder <code> [--open] where a hand state's files go (Open Minnesota results folder.bat)

Nothing here asks a Minnesota Secretary of State host for anything, or any host on a registry's never list
(election/source.py refuses them before a request is made).
"""

import argparse
import datetime as dt
import glob
import gzip
import importlib
import inspect
import json
import os
import re
import shutil
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

SITE = os.path.join(HERE, "site")
DEV = os.path.join(SITE, "dev")
BUILDERS = ("build_night_home", "build_night_us", "build_night_state", "build_night_feed", "build_night_forecasts")
DBS = (("results", "election_2026.sqlite"), ("feed", "night_feed_2026.sqlite"), ("forecasts", "election_model_2026.sqlite"))
TMP = os.path.join(HERE, "election_cache", "tmp")


def say(*a):
    print(*a, flush=True)


def version():
    try:
        import version as V
        top = V.top_entry()
        return top[0] if top else None
    except Exception:  # noqa: BLE001
        return None


# ============================================================================================== check

def cmd_check(a):
    from election import live as L
    bad = []

    def line(ok, text):
        say(f"  {'ok  ' if ok else 'FAIL'} {text}")
        if not ok:
            bad.append(text)

    say("Election Night: checks (nothing is downloaded)")
    line(sys.version_info >= (3, 9), f"Python {sys.version.split()[0]}")
    inside = os.path.abspath(sys.prefix).lower().startswith(os.path.join(HERE, ".venv").lower())
    say(f"  {'ok  ' if inside else 'note'} running from {'the private environment (.venv)' if inside else sys.prefix}")
    free = shutil.disk_usage(HERE).free
    line(free > 2e9, f"{free / 1e9:,.0f} GB free on this drive (the night needs about 2 GB)")
    for what, name in DBS:
        p = os.path.join(HERE, name)
        say(f"  {'ok  ' if os.path.exists(p) else 'note'} the {what} database: " +
            (f"{os.path.getsize(p) / 1e6:,.1f} MB" if os.path.exists(p) else "not made yet (made on first use)"))
    for name in ("ballot_2026.sqlite", "ballot_local_2026.sqlite"):
        line(os.path.exists(os.path.join(HERE, name)), f"{'the Congress' if name == 'ballot_2026.sqlite' else 'the state and local'} ballot database, read only: "
             f"{'there' if os.path.exists(os.path.join(HERE, name)) else 'missing'}")
    from election import registry
    out = []
    reg_bad = registry.selftest(say=out.append) + registry.run_checks(say=out.append)
    for ln in out:
        if ln.startswith(("check", "selftest", "statuses")) or "FAIL" in ln:
            say("       " + ln)
    line(reg_bad == 0, "the registry: every state present and valid")
    from election.source import Refused, Source
    calls = []
    src = Source(replay=lambda u: calls.append(u) or (200, b"", {}), log=lambda *_: None, stopped_file=None)
    refused = 0
    tests = ["https://electionresults.sos.mn.gov/", "https://electionresultsfiles.sos.mn.gov/x.txt", "https://www.sos.mn.gov/",
             "https://vrsws.sos.ky.gov/", "https://results.okelections.us/OKER/", "https://api.gdeltproject.org/api/v2/doc/doc"]
    for u in tests:
        try:
            src.get(u)
        except Refused:
            refused += 1
    line(refused == len(tests) and not calls, f"the never lists: {refused} of {len(tests)} forbidden addresses refused before any request")
    for path in sorted(glob.glob(os.path.join(HERE, "election", "readers", "*.py"))):
        name = os.path.splitext(os.path.basename(path))[0]
        if name.startswith("_"):
            continue
        try:
            mod = importlib.import_module(f"election.readers.{name}")
        except Exception as e:  # noqa: BLE001
            line(False, f"reader {name}: does not load ({e.__class__.__name__}: {e})")
            continue
        test = getattr(mod, "selftest", None) or getattr(mod, "check_fixture", None)
        if test is None:
            say(f"  note reader {name}: no self-test")
            continue
        quiet = []
        try:
            ok = bool(test(say=quiet.append))
        except TypeError:
            ok = bool(test())
        line(ok, f"reader {name}: its self-test on its fixture" + (f" ({quiet[-1].strip()[:150]})" if quiet else ""))
    from election import store
    line(store.selftest(say=lambda *_: None), "the results store's self-test")
    try:
        from election.feeds import measures
        got = []
        line(bool(measures.selftest(say=got.append)), "the feed measures' self-test" +
             ("" if not any("BAD" in g for g in got) else " (" + "; ".join(g.strip() for g in got if "BAD" in g)[:200] + ")"))
    except ImportError as e:
        say(f"  note the feed measures: not there yet ({e})")
    tmp = tempfile.mkdtemp(prefix="night_check_", dir=_tmp())
    try:
        from election import awake, publish, replay
        for name, fn in (("stay awake", lambda s: awake.selftest(say=s)), ("publishing", lambda s: publish.selftest(tmp, say=s)),
                         ("rehearsals", lambda s: replay.selftest(tmp, say=s)), ("the cycle", lambda s: selftest_cycle(tmp, say=s))):
            got = []
            ok = fn(got.append)
            for g in got:
                if a.verbose or "FAIL" in g:
                    say("     " + g)
            line(ok, f"the updater's own self-test: {name}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    from election import publish as P
    p = P.Publisher(remote=None)
    say(f"  {'ok  ' if p.enabled else 'note'} {p.describe() if p.enabled else p.why_off}")
    gitv = os.popen("git --version").read().strip()
    line(bool(gitv), f"git: {gitv or 'not found'}")
    for code in ("MN", "OK"):
        e = registry.load(code) or {}
        f = L.hand_folder(e)
        has = f and os.path.isdir(f)
        say(f"  note {code}'s files go in {os.path.relpath(f, HERE) if f else '(none)'} ({'there' if has else 'made when John opens it'})")
    from election import live
    sec = []
    for name, (modname, fn, *_r) in live.SECTIONS.items():
        try:
            m = live.optional(modname)
            sec.append(f"{name} {'there' if m is not None and hasattr(m, fn) else 'not yet'}")
        except Exception as e:  # noqa: BLE001
            line(False, f"section {name}: does not load ({e.__class__.__name__}: {e})")
    for modname in ("election.model.live_model", "election.model.runs", "election.feeds.bluesky"):
        try:
            sec.append(f"{modname.split('.')[-1]} {'there' if live.optional(modname) is not None else 'not yet'}")
        except Exception as e:  # noqa: BLE001
            line(False, f"{modname}: does not load ({e.__class__.__name__}: {e})")
    say("  note the other sections: " + "; ".join(sec))
    say("PASS" if not bad else f"FAIL ({len(bad)})")
    return 0 if not bad else 1


def _tmp():
    os.makedirs(TMP, exist_ok=True)
    return TMP


def selftest_cycle(tmp, say=print):
    """The cycle with no network: a made-up reader family read through a replay; test figures before the polls close
    are never published; three failures make a state stale and an answer clears it; a refusal stops the state; a file
    that does not read holds the state and the last good figures stay; Minnesota's folder read after it settles; a
    snapshot written whole, the unchanged next one not written twice, now.json under 4 KB, the files read back as a page
    would; pruning; a restart resumes the numbering; stop publishes 'paused'."""
    import types
    from election import live as L
    from election import livejson, publish, store
    from election.replay import ReplayClock
    from election.source import Source
    ok = True

    def expect(c, what):
        nonlocal ok
        say(f"      {'ok  ' if c else 'FAIL'} {what}")
        ok = ok and bool(c)

    base = tempfile.mkdtemp(prefix="cycle_", dir=tmp)
    close = dt.datetime(2026, 11, 4, 2, 0, tzinfo=dt.timezone.utc)
    clock = ReplayClock(close - dt.timedelta(hours=1), L.utcnow(), 1)
    answers = {"mode": "ok", "ver": "1", "votes": [10, 5]}

    def replay_fn(url):
        if answers["mode"] == "down":
            from election.source import SourceError
            raise SourceError("no answer (test)")
        if answers["mode"] == "refuse":
            return 403, b"", {}
        if url.endswith("ver.txt"):
            return 200, answers["ver"].encode(), {}
        return 200, json.dumps({"v": answers["votes"]}).encode(), {}

    fake = types.ModuleType("election.readers.zz_test")
    fake.FEED = "zz-test"

    def check(src, entry):
        r = src.get("https://zz.example.gov/ver.txt", state="ZZ")
        if r.refused:
            from election.source import Refused
            raise Refused(r.url, r.why)
        return {"version": r.body.decode(), "time": None}

    def fetch(src, entry, version):
        r = src.get("https://zz.example.gov/data.json", state="ZZ")
        return [(r.url, r.body)]

    def read(files, entry):
        doc = json.loads(files[0][1])
        if doc.get("v") == "broken":
            raise ValueError("the layout changed")
        a, b = doc["v"]
        return {"state": "ZZ", "feed": "zz-test", "source_time": None, "source_version": None, "contests": [{
            "race_id": "2026-ZZ-S1", "key": "S1", "office": "Test Senate", "level": "congress", "seats": 1, "unit_kind": "race", "units_all": 2,
            "choices": [{"key": "a", "name": "Pat A", "party": "D", "ballot_name": "Pat A", "order": 1},
                        {"key": "b", "name": "Lee B", "party": "R", "ballot_name": "Lee B", "order": 2}],
            "units": [{"id": "all", "kind": "race"}], "rows": [{"unit": "all", "choice": "a", "votes": a}, {"unit": "all", "choice": "b", "votes": b}],
            "reporting": [{"unit": "all", "in": 1, "all": 2}], "stated": [], "controls": []}], "unmatched": [], "problems": []}
    fake.check, fake.fetch, fake.read = check, fetch, read
    sys.modules["election.readers.zz_test"] = fake
    reg_zz = {"code": "ZZ", "name": "Test", "status": "live", "family": "zz_test", "approved": True, "units": "precinct",
              "cadence": {"check_every_s": 120, "hosts": ["zz.example.gov"]}, "certify": {"body": "the test board"}, "hand": None}
    bare = os.path.join(base, "remote.git")
    import subprocess
    subprocess.run(["git", "init", "-q", "--bare", bare], capture_output=True)
    lines = []
    from election.readers import mn_media as M
    mn_folder = os.path.join(base, "mn_saves")
    os.makedirs(mn_folder)

    def make(clock_):
        n = L.Night(mode="replay", db=os.path.join(base, "t.sqlite"), live_root=os.path.join(base, "live", "rehearsal"),
                    publish_root=os.path.join(base, "live"), work=os.path.join(base, "work"), clock=clock_,
                    states=["MN"], src=Source(replay=replay_fn, log=lambda *_: None, never_extra=(), stopped_file=None),
                    say=lines.append, status_path=os.path.join(base, "status.md"), log_path=os.path.join(base, "night.log"),
                    label="a test", raw_dir=os.path.join(base, "raw"), hand_folders={"MN": mn_folder}, closes={"MN": close, "ZZ": close},
                    remote=bare, day=dt.date(2026, 11, 3))
        n.reg["ZZ"] = reg_zz
        n.codes = ["MN", "ZZ"]
        n.close_override["ZZ"] = close
        n.st.pop("ZZ", None)
        s = {"entry": reg_zz, "kind": "live", "family": "zz_test", "first_close": close, "last_close": close, "next": None, "why": "",
             "note": "", "fails": 0, "fail_since": None, "refused": None, "fp_seen": None, "seen_at": None, "fp_read": None, "last_version": None,
             "changed": False, "held_at": None, "mod": fake, "mtime": None, "feed": "zz-test"}
        n.st["ZZ"] = s
        n._reader = lambda code, _orig=n._reader: (fake, "") if code == "ZZ" else _orig(code)
        store.ensure_feed(n.con, "ZZ", "zz-test", "zz_test", "test", "live")
        return n

    night = make(clock)
    st = night.poll_state("ZZ", clock.now())
    expect(st == "test", "figures before the polls close are a test")
    snap = night.snapshot("running", publish=False)
    expect(night.status_word("ZZ") == "wait" and not os.path.exists(os.path.join(base, "live", "rehearsal", "s", f"{snap['seq']:06d}", "zz.json")),
           "and are never published (the state waits)")
    clock.night_start = close + dt.timedelta(minutes=5)
    clock.wall_start = L.utcnow()
    answers["ver"] = "2"
    expect(night.poll_state("ZZ", clock.now()) == "ok", "after the polls close the figures are read")
    expect(night.poll_state("ZZ", clock.now()) == "same", "an unchanged version is not fetched again")
    answers["mode"] = "down"
    for _i in range(3):
        night.poll_state("ZZ", clock.now())
    night.snapshot("running", publish=False)
    expect(night.status_word("ZZ") == "stale", "three failures in a row: the state's site has not answered")
    answers["mode"], answers["ver"], answers["votes"] = "ok", "3", [20, 9]
    night.poll_state("ZZ", clock.now())
    night.snapshot("running", publish=False)
    expect(night.status_word("ZZ") == "counting", "a dropped connection catches up with the newest figures")
    answers["ver"], answers["votes"] = "4", "broken"
    night.poll_state("ZZ", clock.now())
    night.snapshot("running", publish=False)
    zz = json.load(open(os.path.join(base, "live", "rehearsal", night.live.base, "zz.json"), encoding="utf-8"))
    expect(night.status_word("ZZ") == "held" and store.expand_page(zz)["r"]["2026-ZZ-S1"]["v"] == [20, 9],
           "a file that does not read holds the state; the last good figures stay")
    answers["ver"], answers["votes"] = "5", [30, 12]
    night.poll_state("ZZ", clock.now())
    night.snapshot("running", publish=False)
    expect(night.status_word("ZZ") == "counting", "the next good file clears the hold")
    # Minnesota's folder, from the reader's test files
    for f in ("ussenate_precincts.txt", "ussenate_summary.txt"):
        shutil.copy2(os.path.join(HERE, "election", "fixtures", "mn", "night", f), mn_folder)
    t = clock.now()
    expect(night.look_folder("MN", t) is None, "a changed folder waits until it has been quiet")
    st = night.look_folder("MN", t + dt.timedelta(seconds=L.SETTLE + 1))
    expect(st == "ok", "then it is read")
    later = os.path.join(mn_folder, "ussenate_summary (1).txt")         # the browser saved a file again under a new name
    shutil.copy2(os.path.join(mn_folder, "ussenate_summary.txt"), later)
    os.utime(later, None)
    t2 = clock.now()
    night.look_folder("MN", t2)
    st2 = night.look_folder("MN", t2 + dt.timedelta(seconds=L.SETTLE + 1))
    expect(st2 == "ok" and "older copies of files saved again are set aside" in open(os.path.join(base, "night.log"), encoding="utf-8").read(),
           "a file saved again as 'name (1)': only the newest copy is read")
    s1 = night.snapshot("running", publish=False)
    s2 = night.snapshot("running", publish=False)
    expect(s1["new"] and not s2["new"] and s1["seq"] == s2["seq"], "a snapshot is written once; an unchanged next one only refreshes now.json")
    root = os.path.join(base, "live", "rehearsal")
    probs = livejson.verify(root)
    expect(not probs, f"the live files read back as a page reads them ({'; '.join(probs[:3]) or 'sound'})")
    expect(os.path.getsize(os.path.join(root, "now.json")) < 4000, "now.json is under 4 KB")
    for v in range(6, 12):
        answers["ver"], answers["votes"] = str(v), [30 + v, 12]
        night.poll_state("ZZ", clock.now())
        night.snapshot("running", publish=False)
    expect(len(night.live.seqs()) == livejson.KEEP, f"pruned to the newest {livejson.KEEP} folders ({night.live.seqs()})")
    last = night.live.seq
    night.con.close()
    night2 = make(clock)
    expect(night2.live.seq == last, "a restart resumes the numbering from the live folder")
    answers["ver"], answers["votes"] = "40", [99, 12]
    night2.poll_state("ZZ", clock.now())
    s3 = night2.snapshot("running", publish=False)
    expect(s3["seq"] == last + 1, "and the next snapshot follows on")
    s4 = night2.snapshot("paused", publish=True, wait=True)
    now_remote = subprocess.run(["git", "--git-dir", bare, "show", "main:rehearsal/now.json"], capture_output=True, text=True).stdout
    expect('"run":"paused"' in now_remote and f'"seq":{s4["seq"]}' in now_remote, "stop publishes 'updates paused'")
    night2.con.close()
    sys.modules.pop("election.readers.zz_test", None)
    shutil.rmtree(base, ignore_errors=True)
    return ok


# ============================================================================================== build

def cmd_build(a):
    v = version()
    practice = "2024" if a.practice else None
    done, missing = [], []
    for name in BUILDERS:
        if not os.path.exists(os.path.join(HERE, name + ".py")):
            missing.append(name)
            continue
        mod = importlib.import_module(name)
        sig = inspect.signature(mod.build)
        codes = [None]
        if "code" in sig.parameters and isinstance(getattr(mod, "STATES", None), dict):
            codes = sorted(mod.STATES)
        for code in codes:
            kw = {"version": v, "practice": practice, "say": say}
            if code:
                kw["code"] = code
            mod.build(DEV, **kw)
        done.append(name + (f" ({', '.join(codes)})" if codes != [None] else ""))
    say(f"Election Night pages built: {', '.join(done) or 'none'}" + (f"; not written yet: {', '.join(missing)}" if missing else "") +
        (" (practice figures, into site/practice/)" if practice else ""))
    return 0


# ============================================================================================== discover

def cmd_discover(a):
    from election import live as L
    from election import registry
    from election.source import Refused, Source, SourceError
    src = Source()
    found, waiting = [], []
    for code, e in sorted(registry.load_all().items()):
        if e.get("status") not in ("live", "care"):
            continue
        el = e.get("election") or {}
        fam = e.get("family")
        path = os.path.join(HERE, "election", "readers", f"{fam}.py")
        if not fam or not os.path.exists(path):
            waiting.append(f"{code}: its reader is not written yet; the registry says Nov 3 is {el.get('nov3_id') or 'not known'}"
                           f"{' (posted)' if el.get('posted') else ''}. No request made.")
            continue
        mod = importlib.import_module(f"election.readers.{fam}")
        if not hasattr(mod, "discover"):
            waiting.append(f"{code}: its reader does not look for the election yet; registry: {el.get('nov3_id') or 'not known'}. No request made.")
            continue
        try:
            got = mod.discover(src, e) or {}
        except (Refused, SourceError) as ex:
            waiting.append(f"{code}: {ex}")
            continue
        if got.get("nov3_id"):
            same = str(got["nov3_id"]) == str(el.get("nov3_id"))
            found.append(f"{code}: Nov 3 is {got['nov3_id']}{'' if same else ' (the registry says ' + str(el.get('nov3_id')) + ': update it)'}"
                         f"{'; ' + got['note'] if got.get('note') else ''}")
        else:
            waiting.append(f"{code}: not posted yet{'; ' + got['note'] if got.get('note') else ''}")
    say("Found:")
    for x in found or ["(none)"]:
        say("  " + x)
    say("Missing or waiting:")
    for x in waiting or ["(none)"]:
        say("  " + x)
    return 0


# ============================================================================================== once, live, stop

def cmd_once(a):
    from election import live as L
    holder = L.Lock(L.WORK).holder()
    states = [a.state.upper()] if a.state else None
    if a.from_file:
        if not a.state:
            say("--from-file needs --state")
            return 2
        if holder:
            # the night is running: the mended reader is tested on a scratch copy of the figures, so the checks are
            # reported and the live figures, the live folder and the publisher are never touched
            from election import store
            tmp = tempfile.mkdtemp(prefix=f"from_file_{a.state.lower()}_", dir=_tmp())
            try:
                db = os.path.join(tmp, "election_2026.sqlite")
                src_con = store.connect(store.DB)
                try:
                    dst = __import__("sqlite3").connect(db)
                    src_con.backup(dst)
                    dst.close()
                finally:
                    src_con.close()
                night = L.Night(mode="once", states=states, db=db, publisher=None, live_root=os.path.join(tmp, "live"),
                                work=os.path.join(tmp, "work"), status_path=None, raw_dir=os.path.join(tmp, "raw"), sections=False)
                say("Election Night is running: the mended reader is tested on a scratch copy of the figures (nothing live changes).")
                code = from_file(night, a.state.upper(), a.from_file)
                night.con.close()
                return code
            finally:
                shutil.rmtree(tmp, ignore_errors=True)
        return from_file(L.Night(mode="once", states=states), a.state.upper(), a.from_file)
    if holder:
        say(f"Election Night is running (since {L.clock_words(L.parse(holder.get('started')), day=True)}); it reads and publishes by itself. "
            "Nothing was done.")
        return 0
    night = L.Night(mode="once", states=states)
    night.say = say
    snap = night.once(publish=a.publish)
    say(f"One cycle done: snapshot {snap['seq']} ({'new figures' if snap['new'] else 'figures unchanged'}), {snap['files']} files.")
    if a.publish and (night.publisher is None or not night.publisher.enabled):
        say("Not published: " + night.publisher.why_off)
    return 0


def from_file(night, code, path):
    """Reads one raw file (or a folder of saved files, or a kept raw folder) with the state's reader as it is now, and
    stores the result: how a reader mended on the night is tested on the file that was held."""
    from election import live as L
    s = night.st.get(code)
    if not s:
        say(f"{code} is not in the registry")
        return 2
    reader, why = night._reader(code)
    if not reader:
        say(f"{code}: {why}")
        return 1
    tmpdir = None
    files = []
    if os.path.isdir(path) and os.path.exists(os.path.join(path, "manifest.json")):
        man = json.load(open(os.path.join(path, "manifest.json"), encoding="utf-8"))
        for f in man["files"]:
            with gzip.open(os.path.join(path, f["file"]), "rb") as fh:
                files.append((f["name"], fh.read()))
    elif os.path.isdir(path):
        files = [(n, open(os.path.join(path, n), "rb").read()) for n in sorted(os.listdir(path)) if os.path.isfile(os.path.join(path, n))]
    else:
        files = [(os.path.basename(path), open(path, "rb").read())]
    now = night.clock.now()
    if s["kind"] == "hand":
        tmpdir = tempfile.mkdtemp(prefix=f"from_file_{code.lower()}_", dir=_tmp())
        for n, body in files:
            with open(os.path.join(tmpdir, os.path.basename(n)), "wb") as fh:
                fh.write(body)
        reading, info = reader.read_folder(tmpdir)
        sha = info.get("sha256") or L.sha_files(files)
        st = night._store(code, reading, sha, path, info.get("saved_at"), None, now)
    else:
        reading = reader.read(files, night.entry(code))
        st = night._store(code, reading, L.sha_files(files), path, reading.get("source_time"), reading.get("source_version"), now)
    sid = night.con.execute("SELECT MAX(snapshot_id) FROM snapshots WHERE state=?", (code,)).fetchone()[0]
    say(f"{code}: read with the reader as it is now: {st}")
    for n, p, d in night.con.execute("SELECT check_name, passed, detail FROM checks WHERE snapshot_id=?", (sid,)):
        say(f"  {'ok  ' if p else 'FAIL'} {n}: {(d or '')[:200]}")
    if tmpdir:
        shutil.rmtree(tmpdir, ignore_errors=True)
    return 0 if st in ("ok", "same", "test") else 1


def cmd_live(a):
    from election import live as L
    say("Election Night: the updater. Keep this window open; it prints one line each time it writes new figures.")
    say("To stop it: double-click Stop Election Night.bat (or press Ctrl+C here).")
    from election import registry
    for code in ("MN", "OK"):
        f = L.hand_folder(registry.load(code) or {})
        if f:
            os.makedirs(f, exist_ok=True)
            say(f"{code}: save the files into {os.path.relpath(f, HERE)}")
    night = L.Night(mode="live")
    return night.run()


def cmd_stop(a):
    from election import live as L
    lock = L.Lock(L.WORK)
    holder = lock.holder()
    if not holder:
        say("Election Night is not running here. (If its window was closed, the pages say updates paused after 25 minutes.)")
        root = os.path.join(L.LIVE_ROOT, "now.json")
        try:
            doc = json.load(open(root, encoding="utf-8"))
        except (OSError, ValueError):
            return 0
        if doc.get("run") == "running":
            night = L.Night(mode="status")
            night.next_snap = None
            snap = night.snapshot("paused", publish=True, wait=True)
            say(f"Wrote 'updates paused' (snapshot {snap['seq']})" + ("" if night.publisher.enabled else "; publishing is off, so it stays on this computer"))
        return 0
    lock.request_stop()
    say(f"Asked the updater (started {L.clock_words(L.parse(holder.get('started')), day=True)}) to finish and publish 'updates paused' ...")
    end = time.time() + 600
    while time.time() < end:
        if not lock.holder():
            say("Stopped. The pages now say updates have paused. Double-click Start Election Night.bat to start again.")
            return 0
        time.sleep(2)
    say("It has not stopped after 10 minutes. Close its window; the pages will say updates paused after 25 minutes.")
    return 1


# ============================================================================================== replay

def parse_elections(text, states):
    """'2024-11-05' for every state named, or 'mn=2024-11-05,nd=346@2026-06-09' (a feed state's past id and its date)."""
    out = {}
    for part in text.split(","):
        part = part.strip()
        if "=" in part:
            k, v = part.split("=", 1)
            out[k.strip().upper()] = v.strip()
        elif part:
            for s in states:
                out.setdefault(s, part)
    return out


def cmd_replay(a):
    from election import live as L
    from election import registry
    from election import replay as R
    from election.source import Source
    base = os.path.join(L.WORK, "rehearsal")
    if a.resume:
        run = R.Run.newest(base)
        if not run or run.doc.get("finished"):
            say("No unfinished rehearsal to resume.")
            return 1
        say(f"Resuming the rehearsal {run.doc['id']} (its night went on while it was stopped).")
    else:
        states = [s.strip().upper() for s in (a.states or "mn").split(",") if s.strip()]
        elections = parse_elections(a.election, states)
        closes, ids = {}, {}
        poll = json.load(open(L.POLL_HOURS, encoding="utf-8"))["states"]
        for code in states:
            v = elections.get(code)
            if not v:
                say(f"{code}: no past election named")
                return 2
            past_id, _, day = v.partition("@")
            day = day or past_id
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
                say(f"{code}: give the past election's date, as in {code.lower()}=<id>@2026-06-09")
                return 2
            zones = (poll.get(code) or {}).get("zones") or [{"tz": "America/Chicago", "closes": "20:00"}]
            d = dt.date.fromisoformat(day)
            closes[code] = min(L.from_local(dt.datetime.combine(d, dt.time(*map(int, z["closes"].split(":")))), z["tz"]) for z in zones)
            if v != day:
                ids[code] = past_id
        source, label = None, None
        if "MN" in states:
            day = (elections["MN"].partition("@")[2] or elections["MN"]).replace("-", "")
            kind = a.source or R.best_mn_source(day)
            if kind == "2024-senate" and day != "20241105":
                say(f"There are no saved Minnesota files for {day}: John saves them into states_cache\\mn_local\\sos\\{day}\\")
                return 1
            _folder, label = R.mn_source(kind)
            source = kind
        label = label or ", ".join(f"{c} {elections[c]}" for c in states)
        run = R.Run.new(base, a.election, states, a.speed, a.order, a.late, source, label, closes, a.hours, seed=a.seed)
        run.doc["ids"] = ids
        run.save()
        say(f"Rehearsal {run.doc['id']}: {label}; {a.speed:g} times as fast; {a.order} order" + ("; late batches held back" if a.late else "") +
            f"; the night runs {a.hours} hours ({a.hours * 60 / a.speed:.0f} minutes here).")
    clock = run.clock
    closes = run.closes
    savers = {}
    if "MN" in run.doc["states"]:
        folder, _label = R.mn_source(run.doc["source"])
        savers["MN"] = R.MnSaver(folder, run.watch_folder("MN"), closes["MN"], order=run.doc["order"], late=run.doc["late"],
                                 seed=run.doc.get("seed", 7), hours=run.doc["hours"])
        say("MN: " + savers["MN"].describe())
    feed_states = [c for c in run.doc["states"] if c != "MN"]
    hosts = {}
    for code in feed_states:
        e = registry.load(code) or {}
        for h in (e.get("cadence") or {}).get("hosts", []):
            hosts[h] = code
        steps = os.path.join(run.folder, "steps", code.lower())
        if not os.path.isdir(steps):
            prepare_feed_state(run, code, e)
    src = Source(replay=R.StepReplay(os.path.join(run.folder, "steps"), clock, closes, hosts), log=None)
    hand = {"MN": run.watch_folder("MN")} if "MN" in savers else {}
    remote = a.remote or None
    if remote and not os.path.isabs(remote) and not remote.startswith("file://"):
        say("--remote takes a test repository on this computer (a folder); the live repository is named in election/publish.py")
        return 2
    night = L.Night(mode="replay", db=run.db, live_root=os.path.join(L.LIVE_ROOT, "rehearsal"), publish_root=L.LIVE_ROOT,
                    clock=clock, states=run.doc["states"], src=src, say=say, label=run.doc["label"], raw_dir=os.path.join(run.folder, "raw"),
                    hand_folders=hand, closes=closes, end=run.end, remote=remote, savers=savers, run=run, elections=run.doc.get("ids") or {},
                    day=L.local(min(closes.values())).date())
    if a.min_gap is not None and night.publisher is not None:
        night.publisher.min_gap = a.min_gap
    return night.run()


def prepare_feed_state(run, code, entry):
    """A feed state's past election, fetched once through its reader (politely, through election/source.py), cut into
    the step folders the rehearsal answers from."""
    from election import replay as R
    from election.source import Source
    fam = entry.get("family")
    if not fam or not os.path.exists(os.path.join(HERE, "election", "readers", f"{fam}.py")):
        say(f"{code}: its reader is not written yet, so its past election cannot be replayed")
        return
    mod = importlib.import_module(f"election.readers.{fam}")
    past = (run.doc.get("ids") or {}).get(code)
    e = dict(entry, election=dict(entry.get("election") or {}, nov3_id=past))
    final = os.path.join(R.REPLAY_SOURCES, f"{code.lower()}-{past}")
    if not os.path.isdir(final):
        from election.source import Refused, SourceError
        src = Source()
        try:
            sig = mod.check(src, e)
            if not sig:
                say(f"{code}: its past election {past} is not posted")
                return
            R.save_final(mod.fetch(src, e, str(sig.get("version"))), final)
        except (Refused, SourceError) as ex:
            say(f"{code}: its past election could not be fetched ({ex}); it is left out of this rehearsal")
            return
    steps = R.make_steps(code, mod, final, os.path.join(run.folder, "steps"), order=run.doc["order"], seed=run.doc.get("seed", 7))
    say(f"{code}: {len(steps)} steps of its past night, every 10 minutes after its polls closed")


# ============================================================================================== preview, status, scan

def cmd_preview(a):
    import functools
    import http.server
    os.makedirs(os.path.join(SITE, "night-live"), exist_ok=True)

    class H(http.server.SimpleHTTPRequestHandler):
        def end_headers(self):
            self.send_header("Cache-Control", "no-store")
            super().end_headers()

        def log_message(self, *args):
            pass

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", a.port), functools.partial(H, directory=SITE))
    say(f"Serving the draft and the live figures together at http://127.0.0.1:{a.port}/dev/night/ "
        f"(a state: /dev/night/mn/; a rehearsal: /dev/night/mn/#rehearsal). Ctrl+C or closing this window stops it.")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


def cmd_forecast(a):
    from election import live as L
    say("Election Night: the day's pre-election forecasts (Analysis; stored as versions, published only once John says yes)")
    got = L.run_pre_all(say=say, log=say)
    say("Ran: " + ("; ".join(got) if got else "nothing (the forecast modules are not there)"))
    return 0 if got else 1


def cmd_status(a):
    from election import live as L
    from election import livejson
    night = L.Night(mode="status")
    _files, night.summ = livejson.results_files(night.con, night.codes)
    holder = L.Lock(L.WORK).holder()
    if holder:
        say(f"The updater is running (since {L.clock_words(L.parse(holder.get('started')), day=True)}); it rewrites the status file itself.")
        return 0
    night.write_status()
    say(f"Wrote {os.path.relpath(L.STATUS_MD, HERE)}")
    return 0


SOCIAL = re.compile(r"(?:bsky\.app/profile/[A-Za-z0-9._:-]+|@[A-Za-z0-9_]{1,30}@[A-Za-z0-9.-]+\.[a-z]{2,}|"
                    r"youtube\.com/(?:channel/[A-Za-z0-9_-]+|@[A-Za-z0-9._-]+)|[A-Za-z0-9.-]+\.bsky\.social|"
                    r"https?://[a-z0-9.-]+/@[A-Za-z0-9_]+)")
LINK_KEYS = {"url", "u", "link", "href", "results", "finder", "page", "site", "source", "addr", "address_of_page"}


def _strings(x, key=None):
    if isinstance(x, dict):
        for k, v in x.items():
            yield from _strings(v, k)
    elif isinstance(x, list):
        for v in x:
            yield from _strings(v, key)
    elif isinstance(x, str):
        yield key, x


def cmd_scan(a):
    """Contact-like text, social accounts not on the official list, and names of the kit's files, in the built Night
    pages and every live file. Prints only file names and counts, never the text found."""
    import night_common as N
    from ballot.check_local import EMAIL, PHONE, POBOX, contact_like
    official = set()
    try:
        import sqlite3
        con = sqlite3.connect(f"file:{os.path.join(HERE, 'night_feed_2026.sqlite')}?mode=ro", uri=True)
        for acc, pid in con.execute("SELECT account, platform_id FROM accounts WHERE active=1"):
            official.update({str(acc).lower().lstrip("@"), str(pid).lower()})
    except Exception:  # noqa: BLE001
        pass
    roots = [os.path.join(DEV, "night"), os.path.join(SITE, "night-live")]
    findings = {"contact": [], "social": [], "kit": []}
    n_files = 0
    for root in roots:
        for path in glob.glob(os.path.join(root, "**", "*"), recursive=True):
            if not os.path.isfile(path) or not path.endswith((".html", ".js", ".json")):
                continue
            n_files += 1
            text = open(path, encoding="utf-8", errors="replace").read()
            rel = os.path.relpath(path, HERE)
            if N.kit_names(text):
                findings["kit"].append(rel)
            if path.endswith(".json"):
                try:
                    doc = json.loads(text)
                except ValueError:
                    doc = None
                hits = 0
                for k, s in _strings(doc) if doc is not None else []:
                    if k in LINK_KEYS or s.startswith(("http://", "https://", "../", "./", "s/", "#")):
                        continue
                    if contact_like(s, False):
                        hits += 1
                if hits:
                    findings["contact"].append(f"{rel} ({hits})")
            else:
                body = re.sub(r"https?://[^\s\"'<>)]+", " ", text)
                if EMAIL.search(body) or PHONE.search(body) or POBOX.search(body):
                    findings["contact"].append(rel)
            for m in SOCIAL.finditer(text):
                handle = m.group(0).lower().split("/")[-1].lstrip("@")
                mm = re.match(r"https?://([a-z0-9.-]+)/@([a-z0-9_]+)$", m.group(0).lower())
                if mm and "youtube.com" not in mm.group(1):
                    handle = f"{mm.group(2)}@{mm.group(1)}"           # a Mastodon profile link: user@server, as the list keeps it
                if handle not in official:                        # an exact match only; a name that merely starts alike is not official
                    findings["social"].append(rel)
                    break
    say(f"Scanned {n_files} files in the Night pages and the live figures.")
    for k, words in (("contact", "contact-like text"), ("social", "social accounts not on the official list"), ("kit", "names of the kit's files")):
        say(f"  {'ok  ' if not findings[k] else 'FAIL'} {words}: " + (", ".join(sorted(set(findings[k]))[:12]) if findings[k] else "none"))
    return 0 if not any(findings.values()) else 1


# ============================================================================================== certify, publish, folder

def cmd_certify(a):
    from election import live as L
    from election import registry, store
    code = a.code.upper()
    e = registry.load(code)
    if not e:
        say(f"{code} is not in the registry")
        return 2
    con = store.connect(store.DB)
    body = (e.get("certify") or {}).get("body") or "the state"
    day = a.date or (e.get("certify") or {}).get("date")
    figures = {}
    if e.get("status") == "hand":
        if not a.folder:
            say(f"Give the folder of the certified files John saved: run_night.py certify {code.lower()} --folder <folder>")
            return 2
        night = L.Night(mode="status", states=[code])
        reader, why = night._reader(code)
        if not reader:
            say(f"{code}: {why}")
            return 1
        reading, _info = reader.read_folder(a.folder)
        for c in reading["contests"]:
            rows = [r for r in c["rows"] if r["unit"] == "all" and r.get("type", "total") == "total"]
            if not rows:
                rep = [r for r in c["reporting"] if r["unit"] != "all"]
                if rep and all((r["in"] or 0) >= (r["all"] or 0) for r in rep):
                    agg = {}
                    for r in c["rows"]:
                        if r["unit"] != "all" and r.get("type", "total") == "total":
                            agg[r["choice"]] = agg.get(r["choice"], 0) + int(r["votes"])
                    rows = [{"choice": k, "votes": v} for k, v in agg.items()]
            if rows:
                figures[c["race_id"]] = {r["choice"]: int(r["votes"]) for r in rows}
    else:
        fam = e.get("family")
        try:
            mod = importlib.import_module(f"election.readers.{fam}")
        except ImportError:
            say(f"{code}: its reader is not written yet")
            return 1
        if not hasattr(mod, "certified"):
            say(f"{code}: its reader cannot read certified results yet")
            return 1
        from election.source import Source
        figures, body2, day2 = mod.certified(Source(), e)
        body, day = body2 or body, day2 or day
    if not figures:
        say(f"{code}: no certified figures found")
        return 1
    for rid, f in figures.items():
        store.add_certified(con, rid, f, body, day)
    say(f"{code}: certified figures loaded for {len(figures):,} races ({body}, {day}). The next snapshot marks them certified.")
    return 0


def cmd_publish(a):
    from election import live as L
    from election import publish as P
    if not P.LIVE_REPO:
        say("Publishing is off: " + P.Publisher(remote=None).why_off + ". Set LIVE_REPO in election/publish.py once John names the repository.")
        return 1
    if L.Lock(L.WORK).holder():
        say("The updater is running and publishes by itself.")
        return 0
    from election.source import Source
    p = P.Publisher(log=lambda line: None, src=Source(), history=os.path.join(L.WORK, "publish_log.jsonl"))
    if a.setup:
        P.prepare(P.CLONE, P.repo_url(), lambda *_: None)
        say(f"Prepared {os.path.relpath(P.CLONE, HERE)} for {P.LIVE_REPO}.")
    if not os.path.exists(os.path.join(P.SOURCE, "now.json")):
        night = L.Night(mode="status")
        night.snapshot("paused", publish=False)
    try:
        seq = json.load(open(os.path.join(P.SOURCE, "now.json"), encoding="utf-8")).get("seq")
    except (OSError, ValueError):
        seq = None
    e = p.publish_now(seq)
    say(("Published snapshot " + str(e.get("seq")) + f" to {P.LIVE_REPO}; it shows at {P.LIVE_URL} within about 10 minutes.") if e.get("ok")
        else f"Not published: {e.get('why')}")
    return 0 if e.get("ok") else 1


def cmd_folder(a):
    from election import live as L
    from election import registry
    code = a.code.upper()
    f = L.hand_folder(registry.load(code) or {})
    if not f:
        say(f"{code} is not a state whose files are saved by hand.")
        return 1
    os.makedirs(f, exist_ok=True)
    say(f"{registry.STATES.get(code, code)}'s results files go in: {f}")
    if a.open:
        try:
            os.startfile(f)                                  # noqa: S606 - opens the folder in Explorer for John
        except AttributeError:
            os.system(f'open "{f}"')
    return 0


# ============================================================================================== main

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    p = sub.add_parser("check")
    p.add_argument("--verbose", action="store_true")
    p = sub.add_parser("build")
    p.add_argument("--practice", action="store_true")
    sub.add_parser("discover")
    p = sub.add_parser("once")
    p.add_argument("--publish", action="store_true")
    p.add_argument("--state")
    p.add_argument("--from-file")
    sub.add_parser("live")
    sub.add_parser("stop")
    p = sub.add_parser("replay")
    p.add_argument("--election", default="2024-11-05")
    p.add_argument("--states", default="mn")
    p.add_argument("--speed", type=float, default=6.0)
    p.add_argument("--order", choices=("random", "small-first", "metro-last"), default="random")
    p.add_argument("--late", action="store_true")
    p.add_argument("--source", help="Minnesota: fixture, 2024-senate or saved:<yyyymmdd>")
    p.add_argument("--hours", type=float, default=12.0)
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--resume", action="store_true")
    p.add_argument("--remote", help="a test repository on this computer, in place of the live one (for checks)")
    p.add_argument("--min-gap", type=int, default=None, help="seconds between pushes (default 360)")
    p = sub.add_parser("preview")
    p.add_argument("--port", type=int, default=8791)
    sub.add_parser("status")
    sub.add_parser("forecast")
    sub.add_parser("scan")
    p = sub.add_parser("certify")
    p.add_argument("code")
    p.add_argument("--folder")
    p.add_argument("--date")
    p = sub.add_parser("publish")
    p.add_argument("--setup", action="store_true")
    p = sub.add_parser("folder")
    p.add_argument("code")
    p.add_argument("--open", action="store_true")
    a = ap.parse_args(argv)
    if not a.cmd:
        ap.print_help()
        return 2
    return {"check": cmd_check, "build": cmd_build, "discover": cmd_discover, "once": cmd_once, "live": cmd_live, "stop": cmd_stop,
            "replay": cmd_replay, "preview": cmd_preview, "status": cmd_status, "forecast": cmd_forecast, "scan": cmd_scan, "certify": cmd_certify,
            "publish": cmd_publish, "folder": cmd_folder}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
