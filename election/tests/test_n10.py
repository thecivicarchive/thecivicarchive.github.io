"""Tests for the readers N10 wrote: enhanced_voting (GA VA WA UT ID RI), pcc_ems (CT VT), dc_boe, de_json, hi_text, and
what they share (election/readers/_n10_common.py). Nothing here makes a request: each Source is given a replay.

    .venv\\Scripts\\python.exe -m unittest election.tests.test_n10

The replay tests read every past or posted election kept for rehearsals (election_cache/replay/sources/<code>-<id>/,
fetched once on 2026-10-10 through election/source.py) and are skipped where that folder is not on this computer.
Their measure: every contest of a 2026 primary read here equals the certified primary figures the ballot loaders
stored (only official figures are stored there); every past general reads cleanly into the store, its lines adding to
the source's own totals (each source marks those figures official or certified).
"""

import csv
import glob
import io
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from election import registry, store  # noqa: E402
from election import replay as RP  # noqa: E402
from election.readers import _n10_common as C  # noqa: E402
from election.readers import dc_boe, de_json, enhanced_voting, hi_text, pcc_ems  # noqa: E402
from election.source import Refused, Source  # noqa: E402

FIX = os.path.join(HERE, "election", "fixtures")
MINE = ("GA", "VA", "WA", "UT", "ID", "RI", "CT", "VT", "DC", "DE", "HI")


def quiet(*_a):
    pass


def replay_source(answers):
    """A Source answering from a dict {url: bytes}; any other address is a 404; nothing reaches the network."""
    asked = []

    def fn(url):
        asked.append(url)
        return (200, answers[url], {}) if url in answers else (404, b"", {})
    src = Source(replay=fn, log=quiet, stopped_file=None)
    return src, asked


class SelfTests(unittest.TestCase):
    def test_each_reader_passes_its_fixture(self):
        for mod in (enhanced_voting, pcc_ems, dc_boe, de_json, hi_text):
            out = []
            self.assertTrue(mod.selftest(say=out.append), f"{mod.__name__}: " + " | ".join(out))


class Names(unittest.TestCase):
    def test_same_person(self):
        self.assertTrue(C.same_person('Earl L. "Buddy" Carter (I) (Rep)', 'Earl L. "Buddy" Carter'))
        self.assertTrue(C.same_person("CASE, Ed", "Ed Case"))
        self.assertTrue(C.same_person("Edith H. Ajello*", "Edith H. Ajello"))
        self.assertTrue(C.same_person("SARAH COPELAND HANZAS", "Sarah Copeland Hanzas"))
        self.assertFalse(C.same_person("Mike Simpson", "Mike Kennedy"))

    def test_match_line_needs_one_fit(self):
        cands = [["Jane Sauter", "Republican", 0], ["Mark Sauter", "Republican", 0]]
        self.assertEqual(C.match_line("Jane Sauter", cands), "Jane Sauter")
        self.assertIsNone(C.match_line("J. Sauter", [["Jane Sauter", "R", 0], ["Joe Sauter", "R", 0]]))

    def test_classify(self):
        cw = C.load_crosswalk("GA")
        self.assertEqual(C.classify("GA", "US House of Representatives - District 5", cw)[0], "2026-GA-H05")
        self.assertEqual(C.classify("GA", "State Senate - District 1", cw)[0], "2026-GA-SS1")
        self.assertEqual(C.classify("GA", "Governor", cw)[0], "2026-GA-GOV")
        self.assertEqual(C.classify("GA", "Lieutenant Governor", cw)[0], "2026-GA-LTG")
        self.assertIsNone(C.classify("GA", "Proposed Constitutional Amendment 1", cw)[0])
        self.assertIsNone(C.classify("GA", "District Attorney - Alcovy Judicial Circuit", cw)[0])
        hi = C.load_crosswalk("HI")
        self.assertEqual(C.classify("HI", "U.S. Representative, Dist II", hi)[0], "2026-HI-H02")
        self.assertEqual(C.classify("HI", "Governor and Lieutenant Governor", hi)[0], "2026-HI-GOV")
        self.assertEqual(C.classify("HI", "At-Large Trustee", hi)[0], "2026-HI-OHA-AL")
        ri = C.load_crosswalk("RI")
        self.assertEqual(C.classify("RI", "Senator in Congress", ri)[0], "2026-RI-S2")


class Requests(unittest.TestCase):
    """check, fetch and read through a Source with a replay: the addresses asked, and the never lists."""

    def test_enhanced_voting_cycle(self):
        data = C.read_bytes(os.path.join(FIX, "enhanced_voting", "va_2026_general_data.json"))
        e = registry.load("VA")
        rec, url = enhanced_voting.addresses(e)
        src, asked = replay_source({url: data})
        sig = enhanced_voting.check(src, e)                         # in a replay the data file's own record is read
        self.assertTrue(sig and sig["version"].startswith("2026-10-07"))
        files = enhanced_voting.fetch(src, e, sig["version"])
        rd = enhanced_voting.read(files, e)
        self.assertIn("2026-VA-S2", {c["race_id"] for c in rd["contests"]})
        self.assertEqual(asked, [url, url])
        self.assertIsNone(enhanced_voting.check(src, dict(e, election=dict(e["election"], nov3_id=None))))

    def test_pcc_ems_ct_cycle(self):
        e = registry.load("CT")
        base = "https://ctemspublic.pcctg.net/ng-app/data/election/108/"
        answers = {base + "Version.json": b'{"Version":7}'}
        for n in pcc_ems.CT_FILES:
            answers[f"{base}7/{n}.json"] = C.read_bytes(os.path.join(FIX, "pcc_ems", "ct_2026", n + ".json"))
        src, asked = replay_source(answers)
        sig = pcc_ems.check(src, e)
        files = pcc_ems.fetch(src, e, sig["version"])
        rd = pcc_ems.read(files, e)
        self.assertEqual(sig["version"], "7")
        self.assertEqual(len(asked), 1 + len(pcc_ems.CT_FILES))
        self.assertIn("2026-CT-H03", {c["race_id"] for c in rd["contests"]})

    def test_hi_check_reads_both_layouts(self):
        """2026's file (UTF-8, tab-separated) and 2022's (UTF-16 with no byte-order mark, comma-separated) both pass
        check() and read; the posted folder's address is the one asked."""
        e = registry.load("HI")
        for past, fix in (("2026 Primary", "summary_2026_primary.txt"), ("2022-general", "summary_2022_general.txt")):
            ent = dict(e, election=dict(e["election"], nov3_id=past))
            url = hi_text.address(ent)
            src, asked = replay_source({url: C.read_bytes(os.path.join(FIX, "hi_text", fix))})
            sig = hi_text.check(src, ent)
            rd = hi_text.read(hi_text.fetch(src, ent, sig["version"]), ent)
            self.assertTrue(rd["contests"] and not rd["problems"], past)
            self.assertEqual(asked, [url], past)
        self.assertEqual(hi_text.address(e), "https://elections.hawaii.gov/wp-content/results/2026%20General/summary.txt")

    def test_ct_address_field_never_read(self):
        """A sentinel put into Lookupdata's address and contact fields never reaches the reading."""
        docs = {}
        for n in os.listdir(os.path.join(FIX, "pcc_ems", "ct_2026")):
            docs["x/" + n] = C.read_json(os.path.join(FIX, "pcc_ems", "ct_2026", n))
        look = docs["x/Lookupdata.json"]
        for rec in look["candidateIds"].values():
            rec["AD"] = "SENTINEL-ADDRESS 12 Main Street"
            rec["CO"] = "SENTINEL-CONTACT"
        rd = pcc_ems.read_ct(docs, {"code": "CT"})
        self.assertNotIn("SENTINEL", json.dumps(rd))

    def test_never_lists_refused_before_any_request(self):
        src, asked = replay_source({})
        for url in ("https://mvp.sos.ga.gov/x", "https://elections.ri.gov/elections/", "https://vote.sos.ri.gov/",
                    "https://electionresults.sos.mn.gov/"):
            with self.assertRaises(Refused):
                src.get(url)
        self.assertEqual(asked, [])

    def test_hosts_read_are_on_no_never_list(self):
        src, _ = replay_source({})
        for site, *_r in enhanced_voting.SITES.values():
            src.check(site + "/results/public/api/x")
        for url in (pcc_ems.CT_DATA, pcc_ems.VT_DATA, dc_boe.SITE, de_json.BASE, hi_text.BASE, hi_text.PAST["2022-general"]):
            src.check(url)


class Registry(unittest.TestCase):
    def test_my_states_name_the_readers(self):
        fams = {"GA": "enhanced_voting", "VA": "enhanced_voting", "WA": "enhanced_voting", "UT": "enhanced_voting",
                "ID": "enhanced_voting", "RI": "enhanced_voting", "CT": "pcc_ems", "VT": "pcc_ems", "DC": "dc_boe",
                "DE": "de_json", "HI": "hi_text"}
        for code, fam in fams.items():
            e = registry.load(code)
            self.assertEqual(e["family"], fam, code)
            self.assertEqual(registry.validate(e), [], code)
            self.assertTrue(os.path.exists(C.crosswalk_path(code)), code)


def kept(code):
    return sorted(glob.glob(os.path.join(RP.REPLAY_SOURCES, f"{code.lower()}-*")))


class Replays(unittest.TestCase):
    """Every kept election through its reader and the store; primaries against the certified figures."""

    def test_replays(self):
        folders = [f for code in MINE for f in kept(code)]
        if not folders:
            self.skipTest("no past elections kept on this computer")
        compared = 0
        for folder in folders:
            code = os.path.basename(folder).split("-", 1)[0].upper()
            past = os.path.basename(folder)[len(code) + 1:]
            e = registry.load(code)
            mod = {"enhanced_voting": enhanced_voting, "pcc_ems": pcc_ems, "dc_boe": dc_boe, "de_json": de_json, "hi_text": hi_text}[e["family"]]
            rd = mod.read(sorted(RP.load_final(folder).items()), dict(e, election=dict(e["election"], nov3_id=past)))
            with self.subTest(election=os.path.basename(folder)):
                self.assertEqual(rd["problems"], [])
                st, checks, _page = C.store_roundtrip(rd)
                self.assertEqual(st, "ok", {k: v for k, v in checks.items() if not v[0]})
                self.assertTrue(all(u["why"] for u in rd["unmatched"]))
                nc, nk, diffs = C.compare_primary(code, rd)
                self.assertEqual(diffs, [])
                compared += nk
        self.assertGreater(compared, 900, "the certified primary figures compared")

    def test_rehearsal_steps_ct_vt(self):
        """A past night cut into steps (election/replay.py with pcc_ems.units and reveal): every step reads cleanly and
        adds up, each step has a new version, and the last step equals the final file."""
        import shutil
        import tempfile
        from election.source import FolderReplay
        for code, past, rid in (("CT", "80", "2026-CT-H01"), ("VT", "67a35c79-05a2-4ae3-a77d-97812256188b", "2026-VT-H00")):
            final = os.path.join(RP.REPLAY_SOURCES, f"{code.lower()}-{past}")
            if not os.path.isdir(final):
                continue
            tmp = tempfile.mkdtemp(prefix="n10steps_")
            try:
                steps = RP.make_steps(code, pcc_ems, final, tmp, order="metro-last", seed=7, every=60)
                e = registry.load(code)
                e = dict(e, election=dict(e["election"], nov3_id=past))
                versions, last = set(), None
                for m in steps:
                    src = Source(replay=FolderReplay(os.path.join(tmp, code.lower(), f"{m:04d}")), log=quiet, stopped_file=None)
                    sig = pcc_ems.check(src, e)
                    rd = pcc_ems.read(pcc_ems.fetch(src, e, sig["version"]), e)
                    st, _c, _p = C.store_roundtrip(rd)
                    self.assertEqual((st, rd["problems"]), ("ok", []), f"{code} step {m}")
                    versions.add(sig["version"])
                    h = next(c for c in rd["contests"] if c["race_id"] == rid)
                    last = sum(r["votes"] for r in h["rows"] if r["unit"] == "all" and r["type"] == "total")
                self.assertEqual(len(versions), len(steps))
                full = pcc_ems.read(sorted(RP.load_final(final).items()), e)
                hf = next(c for c in full["contests"] if c["race_id"] == rid)
                self.assertEqual(last, sum(r["votes"] for r in hf["rows"] if r["unit"] == "all" and r["type"] == "total"))
            finally:
                shutil.rmtree(tmp, ignore_errors=True)

    def test_vt_2024_house_equals_official(self):
        f = [x for x in kept("VT") if "67a35c79" in x]
        if not f:
            self.skipTest("Vermont 2024 not kept")
        rd = pcc_ems.read(sorted(RP.load_final(f[0]).items()), registry.load("VT"))
        h = next(c for c in rd["contests"] if c["race_id"] == "2026-VT-H00")
        tot = {r["choice"]: r["votes"] for r in h["rows"] if r["unit"] == "all" and r["type"] == "total"}
        self.assertEqual(tot["becca-balint"], 218398)         # the index marks these figures official
        self.assertEqual(h["reporting"][0]["in"], h["reporting"][0]["all"])

    def test_dc_2024_equals_certified_csv(self):
        """The Board's certified precinct file (November_5_2024_General_Election_Certified_Results.csv), added up by
        contest and line, equals the citywide figures the reader reads."""
        p = os.path.join(HERE, "election_cache", "n10", "probe", "electionresults.dcboe.org", "Downloads", "Reports",
                         "November_5_2024_General_Election_Certified_Results.csv.body")
        if not os.path.exists(p):
            self.skipTest("the certified CSV is not kept on this computer")
        sums = {}
        for r in csv.DictReader(io.StringIO(C.read_bytes(p).decode("utf-8-sig"))):
            if int(r["ContestNumber"]) < 0:
                continue
            k = (r["ContestNumber"], r["Candidate"])
            sums[k] = sums.get(k, 0) + int(r["Votes"] or 0)
        city = C.read_json(os.path.join(FIX, "dc_boe", "citywide_2024_general.json"))
        n = 0
        for c in city:
            for x in c["ElectionData"]:
                k = (str(c["ContestNumber"]), x["Contestant"])
                if k in sums:
                    self.assertEqual(sums[k], x["Votes"], k)
                    n += 1
        self.assertGreater(n, 40)


if __name__ == "__main__":
    unittest.main()
