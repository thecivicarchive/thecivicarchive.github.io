"""Tests for election/store.py (the results database). Nothing here touches the network or a real database file.

    .venv\\Scripts\\python.exe -m unittest election.tests.test_store
"""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from election import store  # noqa: E402


def contest(votes_a, votes_b, in_a=1, stated_a=None, rid="2026-ZZ-T1"):
    return {"race_id": rid, "key": "T1", "office": "Test", "level": "statewide", "seats": 1, "unit_kind": "precinct", "units_all": 2,
            "choices": [{"key": "a", "name": "A Person", "party": "X", "ballot_name": "A Person", "order": 1},
                        {"key": "b", "name": "B Person", "party": "Y", "ballot_name": None, "order": 2}],
            "units": [{"id": "P1", "kind": "precinct", "parent": "C1", "map_id": "P1"}, {"id": "P2", "kind": "precinct", "parent": "C1", "map_id": "P2"}],
            "rows": [{"unit": "P1", "choice": "a", "votes": votes_a[0]}, {"unit": "P1", "choice": "b", "votes": votes_a[1]},
                     {"unit": "P2", "choice": "a", "votes": votes_b[0]}, {"unit": "P2", "choice": "b", "votes": votes_b[1]}],
            "reporting": [{"unit": "P1", "in": in_a, "all": 1}, {"unit": "P2", "in": 1, "all": 1}],
            "stated": [{"unit": "P1", "total": sum(votes_a) if stated_a is None else stated_a}, {"unit": "P2", "total": sum(votes_b)}],
            "controls": []}


def reading(*contests, problems=(), unmatched=()):
    return {"state": "ZZ", "feed": "zz", "contests": list(contests), "problems": list(problems), "unmatched": list(unmatched)}


class StoreTest(unittest.TestCase):
    def setUp(self):
        self.con = store.connect(":memory:")
        store.ensure_feed(self.con, "ZZ", "zz", "test", "fixture", "live")

    def snap(self, data, r):
        sid, st = store.begin_snapshot(self.con, "ZZ", "zz", store.sha256_bytes(data))
        if st == "same":
            store.end_snapshot(self.con, sid, "same", rows=0)
            return sid, "same", []
        status, checks = store.record(self.con, sid, r)
        return sid, status, checks

    def test_selftest(self):
        self.assertTrue(store.selftest(say=lambda *_: None))

    def test_tables_present(self):
        names = {r[0] for r in self.con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for t in ("elections", "feeds", "snapshots", "contests", "choices", "units", "counts", "reporting", "checks", "certified"):
            self.assertIn(t, names)

    def test_only_changes_written(self):
        self.snap(b"1", reading(contest((1, 2), (3, 4))))
        sid, st, _ = self.snap(b"2", reading(contest((1, 5), (3, 4))))
        self.assertEqual(st, "ok")
        rows = self.con.execute("SELECT unit_id, choice_key, votes FROM counts WHERE snapshot_id=?", (sid,)).fetchall()
        self.assertEqual(rows, [("P1", "b", 5)])
        rep = self.con.execute("SELECT COUNT(*) FROM reporting WHERE snapshot_id=?", (sid,)).fetchone()[0]
        self.assertEqual(rep, 0, "reporting unchanged, so nothing written")

    def test_same_file(self):
        self.snap(b"1", reading(contest((1, 2), (3, 4))))
        _sid, st, _ = self.snap(b"1", reading(contest((1, 2), (3, 4))))
        self.assertEqual(st, "same")

    def test_held_keeps_last_good(self):
        self.snap(b"1", reading(contest((1, 2), (3, 4))))
        _sid, st, checks = self.snap(b"2", reading(contest((9, 9), (3, 4), stated_a=17)))
        self.assertEqual(st, "held")
        self.assertFalse(dict((n, p) for n, p, _d in checks)["units_add_up"])
        self.assertEqual(store.page_json(self.con, "ZZ", compact=False)["r"]["2026-ZZ-T1"]["v"], [4, 6])

    def test_published_layout(self):
        """The published file is short and reads back whole; each line carries the name as filed, as its fifth item."""
        c = contest((1, 2), (3, 4))
        c["choices"].append({"key": "write-in", "name": "WRITE-IN", "party": None, "ballot_name": None, "write_in": True, "order": None})
        c["choices"].append({"key": "c-person", "name": "C PERSON", "party": None, "ballot_name": "C. Person", "order": 3})
        c["choices"].append({"key": "d-person", "name": "D Person", "party": "Z", "ballot_name": None, "order": 4})
        self.snap(b"1", reading(c, contest((5, 6), (7, 8), rid="2026-ZZ-T2")))
        long = store.page_json(self.con, "ZZ", compact=False)
        short = store.page_json(self.con, "ZZ")
        self.assertEqual(store.expand_page(short), long)
        self.assertEqual(short["pre"], "2026-ZZ-")
        self.assertEqual(set(short["r"]), {"T1", "T2"})
        self.assertNotIn("t", short["r"]["T1"], "a race's time is left off when it is the file's")
        lines = {c[0]: c for c in long["r"]["2026-ZZ-T1"]["ch"]}
        self.assertEqual(lines["a"][4], "A Person")
        self.assertEqual(lines["c-person"][4], "C. Person")
        self.assertIsNone(lines["b"][4])
        self.assertEqual({tuple(x) for x in short["r"]["T1"]["ch"]},
                         {("a", "A Person", "X"), ("b", "B Person", "Y", 0, 0), ("", "C PERSON", None, 0, "C. Person"),
                          ("", "D Person", "Z", 0, 0), ("", "WRITE-IN", None, 1)})

    def test_county_files(self):
        c = contest((1, 2), (3, 4), in_a=0, rid="2026-ZZ-T1")
        j = contest((5, 6), (7, 8), rid="2026-ZZ-J1")
        j["level"] = "court"
        self.snap(b"1", reading(c, j))
        main, court = store.county_json(self.con, "ZZ", "C1"), store.county_json(self.con, "ZZ", "C1", "court")
        self.assertEqual((main["races"], court["races"]), (["2026-ZZ-T1"], ["2026-ZZ-J1"]))
        self.assertEqual(store.county_rows(main), {"2026-ZZ-T1": {"P2": [3, 4]}}, "a precinct not in yet is not listed")
        self.assertEqual(store.county_rows(court), {"2026-ZZ-J1": {"P1": [5, 6], "P2": [7, 8]}})
        self.assertEqual(court["r"][0][0], [[0, 1]], "reported precincts as runs")
        self.assertEqual(store.county_file("ZZ", "12345", "court"), "zz/c/12345-court.json")
        with self.assertRaises(ValueError):
            store.county_file("ZZ", "345")

    def test_structure_problem_holds(self):
        _sid, st, _ = self.snap(b"1", reading(contest((1, 2), (3, 4)), problems=["line 3: 7 cells"]))
        self.assertEqual(st, "held")

    def test_unmatched_listed_not_held(self):
        _sid, st, checks = self.snap(b"1", reading(contest((1, 2), (3, 4)), unmatched=[{"key": "q", "office": "Question", "why": "not a contest"}]))
        self.assertEqual(st, "ok")
        self.assertTrue(dict((n, p) for n, p, _d in checks)["contests_matched"])

    def test_fall_flagged_not_refused(self):
        self.snap(b"1", reading(contest((5, 2), (3, 4))))
        _sid, st, checks = self.snap(b"2", reading(contest((4, 2), (3, 4))))
        self.assertEqual(st, "ok")
        self.assertFalse(dict((n, p) for n, p, _d in checks)["fall_flag"])

    def test_controls_compared_only_when_same_precincts_in(self):
        c = contest((1, 2), (3, 4), in_a=0)
        c["controls"] = [{"choice": "a", "votes": 100, "in": 2, "from": "summary"}]      # saved at another moment: not compared
        _sid, st, _ = self.snap(b"1", reading(c))
        self.assertEqual(st, "ok")
        c = contest((1, 2), (3, 4))
        c["controls"] = [{"choice": "a", "votes": 100, "in": 2, "from": "summary"}]      # same precincts in, different votes
        _sid, st, _ = self.snap(b"2", reading(c))
        self.assertEqual(st, "held")

    def test_feed_outcome(self):
        store.feed_outcome(self.con, "ZZ", "zz", False, "no answer")
        store.feed_outcome(self.con, "ZZ", "zz", False)
        self.assertEqual(self.con.execute("SELECT failures_in_a_row FROM feeds").fetchone()[0], 2)
        store.feed_outcome(self.con, "ZZ", "zz", True)
        self.assertEqual(self.con.execute("SELECT failures_in_a_row FROM feeds").fetchone()[0], 0)

    def test_failed_snapshot(self):
        sid = store.failed_snapshot(self.con, "ZZ", "zz", "refused", "answered 403")
        self.assertEqual(self.con.execute("SELECT status FROM snapshots WHERE snapshot_id=?", (sid,)).fetchone()[0], "refused")


if __name__ == "__main__":
    unittest.main()
