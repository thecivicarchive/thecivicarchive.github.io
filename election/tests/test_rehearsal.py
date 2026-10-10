"""Tests for the rehearsal's fidelity and the night's time and waiting rules (election/live.py, election/replay.py,
election/livejson.py): figures' times on a rehearsal's night clock, the live night's guard against a misread clock, a
state waiting (never stale) before its polls close, what runs beside the results in each mode, a rehearsal's forecasts
kept out of anything published, and the replay's plan words. Nothing here makes a request.

    .venv\\Scripts\\python.exe -m unittest election.tests.test_rehearsal
"""

import datetime as dt
import json
import os
import shutil
import sys
import tempfile
import types
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from election import live as L  # noqa: E402
from election import livejson, store  # noqa: E402
from election import replay as R  # noqa: E402

UTC = dt.timezone.utc


class _Src:
    """A stand-in for election.source.Source: never asked anything here."""

    def __init__(self, replay=None):
        self.replay = replay

    def stopped(self, host):
        return None


class _Pub:
    def __init__(self, enabled):
        self.enabled = enabled
        self.why_off = "" if enabled else "off (test)"

    def describe(self):
        return "test"

    def recent_seqs(self, minutes):
        return set()


def night(tmp, mode="once", clock=None, src=None, publisher=None, savers=None, feed=False, sections=True):
    n = L.Night(mode=mode, db=os.path.join(tmp, "t.sqlite"), live_root=os.path.join(tmp, "live", "rehearsal"),
                publish_root=os.path.join(tmp, "live"), work=os.path.join(tmp, "work"), clock=clock, states=["ZZ"],
                src=src or _Src(), say=lambda *_: None, status_path=None, log_path=os.path.join(tmp, "night.log"),
                raw_dir=os.path.join(tmp, "raw"), publisher=publisher, savers=savers, feed=feed, sections=sections)
    return n


def add_state(n, first_close):
    entry = {"code": "ZZ", "status": "live", "family": "zz_test", "cadence": {"hosts": ["zz.example.gov"]}}
    n.st["ZZ"] = {"entry": entry, "kind": "live", "family": "zz_test", "first_close": first_close, "last_close": first_close,
                  "next": None, "why": "", "note": "", "fails": 0, "fail_since": None, "refused": None, "fp_seen": None,
                  "seen_at": None, "fp_read": None, "last_version": None, "changed": False, "held_at": None, "mod": None,
                  "mtime": None, "feed": "zz-test"}
    n.codes = ["ZZ"]
    store.ensure_feed(n.con, "ZZ", "zz-test", "zz_test", "test", "live")


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rehearsal_test_")
        self.nights = []

    def tearDown(self):
        for n in self.nights:
            n.con.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def make(self, **kw):
        n = night(self.tmp, **kw)
        self.nights.append(n)
        return n


class TestLiveClockGuard(Base):
    def test_future_time_shown_as_fetch_time(self):
        n = self.make()
        add_state(n, L.utcnow() - dt.timedelta(hours=1))
        fetched = L.utcnow()
        later = L.iso(fetched + dt.timedelta(hours=5))
        self.assertEqual(n.figures_time("ZZ", later, fetched), L.iso(fetched))
        self.assertTrue(any("misread" in x for x in n.notes), "John is told plainly")
        self.assertEqual(n.figures_time("ZZ", L.iso(fetched + dt.timedelta(hours=6)), fetched), L.iso(fetched))
        self.assertEqual(sum("misread" in x for x in n.notes), 1, "said once on the console, then only in the log")

    def test_time_within_slack_is_kept(self):
        n = self.make()
        add_state(n, L.utcnow() - dt.timedelta(hours=1))
        fetched = L.utcnow()
        for t in (fetched - dt.timedelta(minutes=30), fetched + dt.timedelta(minutes=10)):
            self.assertEqual(n.figures_time("ZZ", L.iso(t), fetched), L.iso(t))
        self.assertIsNone(n.figures_time("ZZ", None, fetched))

    def test_naive_time_is_read_as_utc(self):
        n = self.make()
        add_state(n, L.utcnow() - dt.timedelta(hours=1))
        fetched = L.utcnow()
        naive = (fetched + dt.timedelta(hours=3)).replace(tzinfo=None).isoformat(timespec="seconds")
        self.assertEqual(n.figures_time("ZZ", naive, fetched), L.iso(fetched))


class TestRehearsalClock(Base):
    def test_feed_state_time_is_its_step_on_the_night_clock(self):
        close = dt.datetime(2024, 11, 6, 1, 0, tzinfo=UTC)
        wall0 = L.utcnow() - dt.timedelta(minutes=10)
        clock = R.ReplayClock(close - dt.timedelta(minutes=10), wall0, 12)      # 120 night minutes in
        step = types.SimpleNamespace(step_time=lambda code: close + dt.timedelta(minutes=100))
        n = self.make(mode="replay", clock=clock, src=_Src(replay=step))
        add_state(n, close)
        now = clock.now()
        got = L.parse(n.figures_time("ZZ", "2024-11-06T05:40:00Z", now))
        self.assertLessEqual(got, L.utcnow())
        self.assertAlmostEqual((n.shown(got) - (close + dt.timedelta(minutes=100))).total_seconds(), 0, delta=13)   # times are kept to the second, x12 on the night clock

    def test_a_certification_time_never_shows(self):
        close = dt.datetime(2024, 11, 6, 0, 0, tzinfo=UTC)
        clock = R.ReplayClock(close - dt.timedelta(minutes=10), L.utcnow() - dt.timedelta(seconds=60), 12)
        step = types.SimpleNamespace(step_time=lambda code: close)
        n = self.make(mode="replay", clock=clock, src=_Src(replay=step))
        add_state(n, close)
        got = L.parse(n.figures_time("ZZ", "2025-01-07T16:55:00Z", clock.now()))
        self.assertAlmostEqual((n.shown(got) - close).total_seconds(), 0, delta=13)   # times are kept to the second, x12 on the night clock

    def test_minnesota_time_is_its_save(self):
        close = dt.datetime(2024, 11, 6, 2, 0, tzinfo=UTC)
        clock = R.ReplayClock(close, L.utcnow() - dt.timedelta(minutes=5), 12)           # 60 night minutes in
        saver = types.SimpleNamespace(saves=[close + dt.timedelta(minutes=15), close + dt.timedelta(minutes=35),
                                             close + dt.timedelta(minutes=80)])
        saver.due = lambda t: max([i for i, s in enumerate(saver.saves) if s <= t], default=-1)
        n = self.make(mode="replay", clock=clock, savers={"ZZ": saver})
        add_state(n, close)
        got = L.parse(n.figures_time("ZZ", None, clock.now()))
        self.assertAlmostEqual((n.shown(got) - (close + dt.timedelta(minutes=35))).total_seconds(), 0, delta=13)   # times are kept to the second, x12 on the night clock

    def test_step_replay_remembers_the_step_served(self):
        base = os.path.join(self.tmp, "steps")
        for m in (0, 10, 20):
            p = os.path.join(base, "zz", f"{m:04d}", "example.gov", "data.json")
            os.makedirs(os.path.dirname(p))
            with open(p, "wb") as fh:
                fh.write(b"{}")
        close = dt.datetime(2024, 11, 6, 1, 0, tzinfo=UTC)
        clock = R.ReplayClock(close + dt.timedelta(minutes=15), L.utcnow(), 1)
        sr = R.StepReplay(base, clock, {"ZZ": close}, {"example.gov": "ZZ"})
        self.assertIsNone(sr.step_time("ZZ"))
        status, _b, _h = sr("https://example.gov/data.json")
        self.assertEqual(status, 200)
        self.assertEqual(sr.step_time("ZZ"), close + dt.timedelta(minutes=10))


class TestWaitingBeforeClose(Base):
    def test_failures_before_close_are_waiting(self):
        n = self.make()
        add_state(n, L.utcnow() + dt.timedelta(hours=2))
        for _i in range(L.STALE_AFTER + 2):
            self.assertEqual(n._failed("ZZ", "answered 404"), "wait")
        self.assertEqual(n.st["ZZ"]["fails"], 0)
        self.assertEqual(n.status_word("ZZ"), "wait")

    def test_failures_after_close_make_it_stale(self):
        n = self.make()
        add_state(n, L.utcnow() - dt.timedelta(minutes=5))
        for _i in range(L.STALE_AFTER):
            self.assertEqual(n._failed("ZZ", "answered 404"), "failed")
        self.assertEqual(n.status_word("ZZ"), "stale")

    def test_stale_is_never_said_before_close(self):
        n = self.make()
        add_state(n, L.utcnow() + dt.timedelta(minutes=30))
        n.st["ZZ"]["fails"] = 5                     # however it came about
        self.assertEqual(n.status_word("ZZ"), "wait")


class TestModes(Base):
    def test_what_runs_beside_the_results(self):
        r = self.make(mode="replay", clock=R.ReplayClock(L.utcnow(), L.utcnow(), 6))
        self.assertTrue(r.models_on and not r.feed_on and r.results_on and r.rehearsal)
        rf = self.make(mode="replay", clock=R.ReplayClock(L.utcnow(), L.utcnow(), 6), feed=True)
        self.assertTrue(rf.models_on and rf.feed_on)
        f = self.make(mode="feed")
        self.assertTrue(f.feed_on and not f.models_on and not f.results_on and f.rehearsal)
        live = self.make(mode="once")
        self.assertTrue(live.models_on and live.feed_on and not live.rehearsal)

    def test_a_replay_runs_the_models_and_skips_the_pre_election_runs(self):
        n = self.make(mode="replay", clock=R.ReplayClock(L.utcnow(), L.utcnow(), 6))
        add_state(n, L.utcnow())
        calls = []
        fake = types.ModuleType("fake_model")
        fake.run = lambda **kw: calls.append(kw) or {"run": "x", "races": 1, "written": 1}
        real_optional = L.optional
        try:
            L.optional = lambda name: fake if name in ("election.model.live_model", "election.model.night_us") else None
            n._model_queue = {"MN", "ZZ"}
            got = n.sections_tick({})
        finally:
            L.optional = real_optional
        self.assertEqual(sorted(c["state"] for c in calls), ["MN", "ZZ"])
        self.assertTrue(all(c["rehearsal"] and c["db"] == n.db_path for c in calls))
        self.assertEqual(got, ["model MN", "model ZZ"])
        with open(os.path.join(self.tmp, "night.log"), encoding="utf-8") as fh:
            self.assertIn("stored as a rehearsal run", fh.read())

    def test_forecasts_out(self):
        public = L.forecasts_public()
        clock = R.ReplayClock(L.utcnow(), L.utcnow(), 6)
        self.assertTrue(self.make(mode="replay", clock=clock, publisher=None).forecasts_out())
        self.assertEqual(self.make(mode="replay", clock=clock, publisher=_Pub(True)).forecasts_out(), public)
        self.assertEqual(self.make(mode="once", publisher=None).forecasts_out(), public)


class TestStripForecasts(unittest.TestCase):
    def test_strip(self):
        tmp = tempfile.mkdtemp(prefix="strip_test_")
        try:
            def put(rel, text="{}"):
                p = os.path.join(tmp, *rel.split("/"))
                os.makedirs(os.path.dirname(p), exist_ok=True)
                with open(p, "w", encoding="utf-8") as fh:
                    fh.write(text)
            keep = ["now.json", "s/000001/mn.json", "s/000001/mn/c/27053.json", "s/000001/feed/us.json", "rehearsal/s/000002/ga.json"]
            for k in keep:
                put(k)
            for k in ("s/000001/fc/mn.json", "h/mn/2026-MN-S2.json", "rehearsal/s/000002/fc/ga.json", "rehearsal/h/ga/x.json"):
                put(k)
            put("rehearsal/now.json", json.dumps({"seq": 2, "fc": {"t": "x"}, "st": {}}))
            self.assertEqual(len(livejson.forecast_files(tmp)), 5)
            livejson.strip_forecasts(tmp)
            self.assertEqual(livejson.forecast_files(tmp), [])
            for k in keep:
                self.assertTrue(os.path.exists(os.path.join(tmp, *k.split("/"))), k)
            with open(os.path.join(tmp, "rehearsal", "now.json"), encoding="utf-8") as fh:
                self.assertNotIn("fc", json.load(fh))
            self.assertFalse(os.path.exists(os.path.join(tmp, "h")))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestPlanWords(unittest.TestCase):
    def test_one_step_says_complete(self):
        line = R.plan_line("GA", [0], has_reveal=False)
        self.assertIn("one step only", line)
        self.assertIn("complete", line)
        self.assertIn("final figures", line)

    def test_many_steps(self):
        line = R.plan_line("PA", list(range(0, 340, 10)))
        self.assertIn("34 steps", line)
        self.assertIn("5 h 30 min", line)


if __name__ == "__main__":
    unittest.main()
