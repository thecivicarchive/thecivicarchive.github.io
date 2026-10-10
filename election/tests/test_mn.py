"""Tests for Minnesota's reader (election/readers/mn_media.py), its crosswalks and the never list in election/source.py.
Nothing here makes a request: the never-list tests replace the network with a function that fails the test if called.

    .venv\\Scripts\\python.exe -m unittest election.tests.test_mn
"""

import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from election import source, store  # noqa: E402
from election.readers import mn_media as M  # noqa: E402

FIX = os.path.join(M.FIXTURES, "night")
OFFICIAL_2024 = {"royce-white": 8371, "amy-klobuchar": 7373, "rebecca-whiting": 222, "joyce-lacey": 212, "write-in": 13}


def cells(line):
    return line.rstrip("\r\n").split(";")


class Folder:
    """A temporary copy of the fixture folder that a test may change."""

    def __init__(self):
        self.dir = tempfile.mkdtemp(prefix="mn_fixture_")
        for f in os.listdir(FIX):
            shutil.copy(os.path.join(FIX, f), self.dir)

    def path(self, name):
        return os.path.join(self.dir, name)

    def lines(self, name):
        with open(self.path(name), encoding="utf-8") as fh:
            return [ln for ln in fh.read().splitlines() if ln]

    def write(self, name, lines):
        with open(self.path(name), "w", encoding="utf-8", newline="\r\n") as fh:
            fh.write("\n".join(lines) + "\n")

    def close(self):
        shutil.rmtree(self.dir, ignore_errors=True)


def hold_back(f, county_id):
    """Precinct lines of one county not yet in (0 votes, 0 in); the summary then counts the rest."""
    prec = []
    for ln in f.lines("ussenate_precincts.txt"):
        c = cells(ln)
        if c[1] == str(county_id):
            c[11], c[13], c[14], c[15] = "0", "0", "0.00", "0"
        prec.append(";".join(c))
    f.write("ussenate_precincts.txt", prec)
    sums, n_in, n_all = {}, 0, 0
    seen = set()
    for ln in prec:
        c = cells(ln)
        sums[c[7]] = sums.get(c[7], 0) + int(c[13])
        if (c[1], c[2]) not in seen:
            seen.add((c[1], c[2]))
            n_all += 1
            n_in += int(c[11])
    total = sum(sums.values())
    summ = []
    for ln in f.lines("ussenate_summary.txt"):
        c = cells(ln)
        c[11], c[12], c[13], c[15] = str(n_in), str(n_all), str(sums[c[7]]), str(total)
        summ.append(";".join(c))
    f.write("ussenate_summary.txt", summ)


class MinnesotaReaderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cw = json.load(open(M.CROSSWALK, encoding="utf-8"))
        cls.pc = json.load(open(M.PRECINCTS, encoding="utf-8"))
        cls.matcher = M.Matcher(cls.cw)

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="mn_store_")
        self.con = store.connect(os.path.join(self.tmp, "t.sqlite"))
        self.folders = []

    def tearDown(self):
        self.con.close()
        for f in self.folders:
            f.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def folder(self):
        f = Folder()
        self.folders.append(f)
        return f

    def load(self, folder):
        return M.load_folder(self.con, folder, practice=True, crosswalk=self.matcher, precincts=self.pc, say=lambda *_: None)

    # ------------------------------------------------------------------ the crosswalks

    def test_every_contest_in_crosswalk_or_listed(self):
        races = self.cw["races"]
        state_local = [r for r in races if not r.startswith(("2026-MN-H", "2026-MN-S"))]
        congress = [r for r in races if r.startswith(("2026-MN-H", "2026-MN-S"))]
        self.assertEqual(len(state_local), 4721)
        self.assertEqual(len(congress), 9)
        listed = {x["race"] for x in self.cw["not_tied"]}
        for rid, e in races.items():
            self.assertTrue(e["titles"] or rid in listed, rid)
        ok, info = M.check_crosswalk(say=lambda *_: None, cw=self.cw)
        self.assertTrue(ok, info["lost"][:5])

    def test_crosswalk_against_ballot_database(self):
        import sqlite3
        con = sqlite3.connect(f"file:{M.BALLOT_LOCAL}?mode=ro", uri=True)
        ids = {r for (r,) in con.execute("SELECT race_id FROM sl_races WHERE state='MN'")}
        self.assertEqual(ids, {r for r in self.cw["races"] if not r.startswith(("2026-MN-H", "2026-MN-S"))})

    def test_county_race_needs_its_county(self):
        e = self.cw["races"]["2026-MN-0391-057"]                     # County Commissioner District 1, Hubbard County
        title = e["titles"][0]
        rid, _how, _why = self.matcher.resolve(e["oid"], title, "", str(e["counties"][0]), [])
        self.assertEqual(rid, "2026-MN-0391-057")
        rid, _how, why = self.matcher.resolve(e["oid"], title, "", "88", [])
        self.assertIsNone(rid)
        self.assertIn("races fit", why)

    def test_every_map_precinct_reachable(self):
        self.assertEqual(len(self.pc["precincts"]), 4105)
        for vid, (cid, code, _name, _mcd) in self.pc["precincts"].items():
            self.assertEqual(M.vtdid(cid, code), vid)
            self.assertTrue(1 <= cid <= 87)
        self.assertEqual(self.pc["checks"]["county_id_disagrees_with_secretary_table"], [])
        self.assertTrue(M.check_precincts(say=lambda *_: None, pc=self.pc))

    # ------------------------------------------------------------------ reading files

    def test_fixture_adds_up_to_official_totals(self):
        sid, status, info = self.load(FIX)
        self.assertEqual(status, "ok", info.get("checks"))
        checks = {n: p for n, p, _d in info["checks"]}
        self.assertTrue(checks["units_add_up"])
        published = store.page_json(self.con, "MN")
        self.assertEqual(store.expand_page(published), store.page_json(self.con, "MN", compact=False))
        page = store.expand_page(published)["r"]["2026-MN-S2"]
        keys = [c[0] for c in page["ch"]]
        self.assertEqual(dict(zip(keys, page["v"])), OFFICIAL_2024)
        self.assertEqual(page["p"], [82, 82])
        # the fifth item, each candidate's name as filed on this year's list: the fixture is 2024's count replayed onto the
        # 2026 race, whose list names only one of 2024's candidates (Rebecca Whiting); the other lines have none (written 0)
        filed = {c[0]: c[4] for c in page["ch"]}
        self.assertEqual(filed, {"royce-white": None, "amy-klobuchar": None, "rebecca-whiting": "Rebecca Whiting", "joyce-lacey": None, "write-in": None})
        short = {c[1]: c for c in published["r"]["S2"]["ch"]}
        self.assertEqual(short["Amy Klobuchar"][4:], [0])
        self.assertEqual(short["Rebecca Whiting"], ["", "Rebecca Whiting", "LIB"], "the name as filed is left off when it is the name as printed")
        self.assertEqual(len(short["WRITE-IN"]), 4)
        units = self.con.execute("SELECT COUNT(*), COUNT(map_id) FROM units WHERE kind='precinct'").fetchone()
        self.assertEqual(units, (82, 82))
        self.assertIn("27001", store.county_units(self.con, "MN"))
        cj = store.county_json(self.con, "MN", "27001")
        self.assertEqual((len(cj["u"]), cj["part"]), (51, ""))
        lines = {rid: len(e["ch"]) for rid, e in store.page_json(self.con, "MN", compact=False)["r"].items()}
        self.assertEqual(len(store.county_rows(cj, lines)["2026-MN-S2"]), 51)
        total = [0] * len(keys)
        for cu in store.county_units(self.con, "MN"):
            for v in store.county_rows(store.county_json(self.con, "MN", cu), lines).get("2026-MN-S2", {}).values():
                total = [a + b for a, b in zip(total, v)]
        self.assertEqual(total, page["v"], "the precinct files add up to the race's total")
        self.assertEqual(store.county_json(self.con, "MN", "27001", "court")["races"], [])
        self.assertEqual(store.county_file("MN", "27001"), "mn/c/27001.json")
        self.assertEqual(store.county_file("MN", "27001", "court"), "mn/c/27001-court.json")
        self.assertLess(len(json.dumps(cj, separators=(",", ":"))), 150_000)

    def test_partial_then_complete(self):
        f = self.folder()
        hold_back(f, 16)                                          # Cook County not in yet
        _sid, status, info = self.load(f.dir)
        self.assertEqual(status, "ok", info.get("checks"))
        page = store.page_json(self.con, "MN", compact=False)["r"]["2026-MN-S2"]
        self.assertEqual(page["p"], [68, 82])
        cook = store.county_json(self.con, "MN", "27031")
        self.assertEqual(store.county_rows(cook).get("2026-MN-S2", {}), {}, "a county with none in lists no precinct")
        _sid, status, _info = self.load(f.dir)
        self.assertEqual(status, "same")
        sid, status, _info = self.load(FIX)
        self.assertEqual(status, "ok")
        changed_units = {u for (u,) in self.con.execute("SELECT DISTINCT unit_id FROM counts WHERE snapshot_id=?", (sid,))}
        self.assertTrue(all(u == "all" or u.startswith("27031") for u in changed_units), changed_units)

    def test_files_saved_at_different_moments(self):
        f = self.folder()
        hold_back(f, 16)
        shutil.copy(os.path.join(FIX, "ussenate_summary.txt"), f.path("ussenate_summary.txt"))     # the summary saved later
        _sid, status, info = self.load(f.dir)
        self.assertEqual(status, "ok", info.get("checks"))
        detail = {n: d for n, _p, d in info["checks"]}["units_add_up"]
        self.assertIn("not compared", detail)

    def test_disagreement_holds(self):
        f = self.folder()
        summ = []
        for ln in f.lines("ussenate_summary.txt"):
            c = cells(ln)
            if c[7] == "Royce White":
                c[13] = str(int(c[13]) + 1)
                c[15] = str(int(c[15]) + 1)
            summ.append(";".join(c))
        f.write("ussenate_summary.txt", summ)
        _sid, status, _info = self.load(f.dir)
        self.assertEqual(status, "held")

    def test_precinct_line_must_add_up(self):
        f = self.folder()
        lines = f.lines("ussenate_precincts.txt")
        c = cells(lines[0])
        c[15] = str(int(c[15]) + 5)
        lines[0] = ";".join(c)
        f.write("ussenate_precincts.txt", lines)
        _sid, status, _info = self.load(f.dir)
        self.assertEqual(status, "held")

    def test_broken_line_holds(self):
        f = self.folder()
        lines = f.lines("ussenate_precincts.txt")
        lines[3] = "MN;1;0005;0102;U.S. Senator;;04;Somebody;;;DFL;1;1;abc;0;0"
        f.write("ussenate_precincts.txt", lines)
        _sid, status, info = self.load(f.dir)
        self.assertEqual(status, "held")

    def test_web_page_save_holds(self):
        f = self.folder()
        f.write("results.htm", ["<!DOCTYPE html>", "<html><body>Results</body></html>"])
        _sid, status, _info = self.load(f.dir)
        self.assertEqual(status, "held")

    def test_candidate_file_left_aside(self):
        f = self.folder()
        f.write("candidates.md", [";".join(["x"] * 21)] * 3)
        _sid, status, info = self.load(f.dir)
        self.assertEqual(status, "ok")
        self.assertNotIn("candidates.md", info["files"])

    def test_unknown_contest_listed(self):
        f = self.folder()
        f.write("question.txt", ["MN;1;0005;9999;Question 1;;01;YES;;;;1;1;10;50.00;20",
                                 "MN;1;0005;9999;Question 1;;02;NO;;;;1;1;10;50.00;20"])
        _sid, status, info = self.load(f.dir)
        self.assertEqual(status, "ok")
        self.assertEqual(len(info["unmatched"]), 1)
        self.assertTrue(info["unmatched"][0]["why"])

    def test_precinct_not_on_map_is_noted(self):
        f = self.folder()
        f.write("extra.txt", ["MN;1;9999;0102;U.S. Senator;;03;Royce White;;;R;1;1;0;0.00;0"])
        _sid, _status, info = self.load(f.dir)
        self.assertTrue(any("not on the ballot map" in n for n in info["notes"]))

    def test_layout_from_first_lines_not_name(self):
        f = self.folder()
        os.rename(f.path("ussenate_precincts.txt"), f.path("whatever name.md"))
        _sid, status, info = self.load(f.dir)
        self.assertEqual(status, "ok")
        self.assertIn("whatever name.md", info["files"])


class NeverListTest(unittest.TestCase):
    """source.py refuses every Minnesota Secretary of State address before anything is sent; the network is replaced
    by a function that fails the test if it is ever reached."""

    def no_network(self, *a, **k):
        raise AssertionError("a request was attempted")

    def test_sos_mn_refused_live_without_network(self):
        src = source.Source(log=lambda *_: None, never_extra=(), stopped_file=None)
        with mock.patch.object(source, "urlopen", self.no_network), mock.patch("socket.create_connection", self.no_network):
            for url in ("https://electionresults.sos.mn.gov/Select/MediaFiles/Index?ersElectionId=170",
                        "https://electionresultsfiles.sos.mn.gov/20261103/allracesbyprecinct.txt",
                        "https://candidates.sos.mn.gov/", "https://www.sos.mn.gov/", "https://SOS.MN.GOV/", "https://pollfinder.sos.mn.gov/",
                        "http://electionresults.sos.state.mn.us/Results/MediaResult/115?mediafileid=13"):
                with self.assertRaises(source.Refused, msg=url):
                    src.get(url)

    def test_registry_never_lists_apply(self):
        src = source.Source(log=lambda *_: None, stopped_file=None)
        self.assertIn("*.sos.mn.gov", src.never_extra)
        with mock.patch.object(source, "urlopen", self.no_network):
            with self.assertRaises(source.Refused):
                src.get("https://vrsws.sos.ky.gov/")

    def test_refusal_stops_host_for_the_night(self):
        calls = []

        def replay(url):
            calls.append(url)
            return 403, b"forbidden", {}
        src = source.Source(replay=replay, log=lambda *_: None, never_extra=(), stopped_file=None)
        r = src.get("https://results.example.gov/a.json")
        self.assertTrue(r.refused)
        with self.assertRaises(source.Refused):
            src.get("https://results.example.gov/b.json")
        self.assertEqual(len(calls), 1)

    def test_challenge_page_stops_host(self):
        src = source.Source(replay=lambda url: (200, b"<!DOCTYPE html><title>Just a moment...</title>", {"Content-Type": "text/html"}),
                            log=lambda *_: None, never_extra=(), stopped_file=None)
        self.assertTrue(src.get("https://results.example.gov/").refused)

    def test_honest_user_agent(self):
        seen = {}

        class Fake:
            status = 200
            headers = {}

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return b"{}"

        def fake_urlopen(req, timeout=None, context=None):
            seen["ua"] = req.get_header("User-agent")
            return Fake()
        src = source.Source(log=lambda *_: None, never_extra=(), stopped_file=None)
        with mock.patch.object(source, "urlopen", fake_urlopen), mock.patch.object(source.net, "patient_lookups", lambda: None):
            src.get("https://results.example.gov/x.json")
        self.assertEqual(seen["ua"], source.net.UA)


if __name__ == "__main__":
    unittest.main()
