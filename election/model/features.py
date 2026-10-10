"""election/model/features.py - Minnesota's precinct features for the forecasts, in election_model_2026.sqlite
(tables `features` and `run_inputs`), with the three checks of ARCHITECTURE.md 5.3 (N6).

    python -m election.model.features --state mn            build everything (fetching what is missing, once)
    python -m election.model.features --state mn --no-archive   skip the archive's pages (state contests then unchecked)
    python -m election.model.features --selftest            the arithmetic on made-up rows; downloads nothing

WHAT A PRECINCT GETS (unit_kind "precinct", unit_id today's VTDID; method FEATURE_METHOD):
  census      2020 counts (exact) and ACS 2020-2024 estimates with margins: census.py's list (people, adults, age bands,
              sex, Hispanic origin and race, education, owning, marriage, children at home, poverty, moving, citizens of
              voting age from the CVAP file and B29001, averages of block-group medians).
  turnout     for each general election 2012-2024, on today's lines (data_mn.on_today_lines): ballots, registered by the
              end of the day (7 a.m. plus Election Day registrations), turnout = ballots / registered, the absentee and
              mail share, the Election Day registration share; the midterm average (2014, 2018, 2022); all-mail in 2024.
  lean        the DFL share of the two-party vote for every partisan contest, and for statewide contests that share minus
              the statewide share ("lean"); district contests only where both parties ran ("contested_..."). lean_recent
              is the plain average of the leans of 2024 President, 2024 U.S. Senate and 2022 Governor: a starting point,
              not the backtest's weights.
  roll-off    1 minus a contest's votes over the ballots that could vote in it (state and legislative contests leave out
              federal-only and president-only ballots), per contest.
School districts (unit_kind "school") get the census features only. The state (unit_kind "state", "MN") gets the
statewide shares and turnout each contest is measured against.

THE THREE CHECKS (written to election_cache/model/mn/check_*.json and printed):
  1. blocks: the 2020 blocks add up to the state's 2020 count, and every block is placed (census.py).
  2. registration: each precinct's 2024 registration against its citizens of voting age (CVAP 2020-2024, carried from
     block groups); precincts far from the rest, or above their CVAP beyond its margin, are listed with their figures.
  3. contests: every 2012-2024 contest's precinct sum against its official total (data_mn.check_contests).
Figures describe places, never voters; every derived figure is Analysis.
"""

import argparse
import datetime as dt
import math
import os
import statistics
import sys

from election.model import DB, HERE, cache_dir, connect, load_json, now_utc, save_json, sha_bytes, sha_file
from election.model import census, data_mn

FEATURE_METHOD = "features-1.0"
PARTISAN = ("usprs", "ussen", "ussse", "usrep", "mngov", "mnsos", "mnag", "mnaud", "mnsen", "mnleg")
STATEWIDE = ("usprs", "ussen", "ussse", "mngov", "mnsos", "mnag", "mnaud")
STATE_LEVEL = ("mngov", "mnsos", "mnag", "mnaud", "mnsen", "mnleg")         # ballots for these leave out federal-only ones
MIDTERMS = (2014, 2018, 2022)
RECENT = (("usprs", 2024), ("ussen", 2024), ("mngov", 2022))
MIN_TWO_PARTY = 20                 # fewer two-party votes than this: the share is left out (the kit's too_few rule)
OUTLIER_Z = 3.5                    # robust z of log(registered / CVAP)


def _ratio(a, b):
    return (a / b) if b else None


def results_features(year, lines, contests_by_id, district_of):
    """{vtdid: {name: (value, note)}} for one year on today's lines, and the state's own figures."""
    out, state = {}, {}
    doc_fields = set(next(iter(lines.values())).keys()) if lines else set()
    tot = {k: sum(v.get(k, 0) or 0 for v in lines.values()) for k in ("totvoting", "reg7am", "edr")}
    state[f"ballots_{year}"] = (tot["totvoting"], "precincts' ballots, today's lines")
    state[f"turnout_{year}"] = (_ratio(tot["totvoting"], tot["reg7am"] + tot["edr"]), "ballots over registered by the end of the day")
    shares = {}
    for prefix in PARTISAN:
        tcol = prefix + ("total" if prefix + "total" in doc_fields else "tot")
        if prefix + "dfl" not in doc_fields or prefix + "r" not in doc_fields:
            continue
        d = sum(v.get(prefix + "dfl", 0) for v in lines.values())
        r = sum(v.get(prefix + "r", 0) for v in lines.values())
        if prefix in STATEWIDE and d + r:
            shares[prefix] = d / (d + r)
            state[f"dfl2p_{prefix}_{year}"] = (shares[prefix], "statewide DFL share of the two-party vote")
    for v, rec in lines.items():
        f = {}
        ballots = rec.get("totvoting", 0) or 0
        reg = (rec.get("reg7am", 0) or 0) + (rec.get("edr", 0) or 0)
        f[f"ballots_{year}"] = (ballots, None)
        f[f"registered_{year}"] = (reg, "registered at 7 a.m. plus Election Day registrations")
        f[f"turnout_{year}"] = (_ratio(ballots, reg), None)
        if "ab_mb" in rec:
            f[f"share_absentee_mail_{year}"] = (_ratio(rec.get("ab_mb", 0), ballots), "absentee, military, overseas and mail ballots")
        f[f"share_edr_{year}"] = (_ratio(rec.get("edr", 0), ballots), "Election Day registrations over ballots")
        state_ballots = ballots - (rec.get("fedonlyab", 0) or 0) - (rec.get("presonlyab", 0) or 0)
        for prefix in PARTISAN:
            tcol = prefix + ("total" if prefix + "total" in rec else "tot")
            if tcol not in rec:
                continue
            total = rec.get(tcol, 0) or 0
            if not total:
                continue
            base = state_ballots if prefix in STATE_LEVEL else (ballots - (rec.get("presonlyab", 0) or 0) if prefix != "usprs" else ballots)
            f[f"rolloff_{prefix}_{year}"] = (1 - total / base if base else None, "1 minus the contest's votes over the ballots that could vote in it")
            d, r = rec.get(prefix + "dfl", 0) or 0, rec.get(prefix + "r", 0) or 0
            if d + r < MIN_TWO_PARTY:
                continue
            if prefix in STATEWIDE:
                share = d / (d + r)
                f[f"dfl2p_{prefix}_{year}"] = (share, None)
                if prefix in shares:
                    f[f"lean_{prefix}_{year}"] = (share - shares[prefix], "DFL two-party share minus the statewide share")
            elif d and r:
                # a party with no candidate has no votes anywhere in the district, so votes for both mean both ran
                f[f"dfl2p_contested_{prefix}_{year}"] = (d / (d + r), "both parties ran in the district")
        out[v] = f
    return out, state


def registration_check(pfeat, today_rows, reg2024):
    """Check 2: 2024 registration against CVAP, precinct by precinct. Returns the summary and the list."""
    name = {r["vtdid"]: (r.get("countyname"), r.get("mcdname")) for r in today_rows}
    rows = []
    for v, f in pfeat.items():
        cv, cvm = f.get("cvap", (None, None, None))[:2]
        reg = reg2024.get(v)
        if reg is None or not cv:
            continue
        rows.append((v, reg, cv, cvm or 0.0, f["pop2020"][0]))
    logs = [math.log(reg / cv) for v, reg, cv, cvm, pop in rows if reg > 0 and cv >= 50]
    med = statistics.median(logs)
    mad = statistics.median([abs(x - med) for x in logs]) * 1.4826
    listed = []
    for v, reg, cv, cvm, pop in rows:
        why = []
        if reg > 0 and cv >= 50:
            z = (math.log(reg / cv) - med) / mad if mad else 0.0
            if abs(z) > OUTLIER_Z:
                why.append(f"far from the other precincts (robust z {z:+.1f})")
        else:
            z = None
        if reg > cv + cvm:
            why.append("more registered than the citizens of voting age, beyond the estimate's margin")
        if why:
            c, m = name.get(v, (None, None))
            listed.append({"vtdid": v, "county": c, "place": m, "registered_2024": round(reg), "cvap": round(cv), "cvap_moe": round(cvm),
                           "ratio": round(reg / cv, 3) if cv else None, "pop2020": pop, "why": why})
    listed.sort(key=lambda x: -(x["ratio"] or 0))
    total_reg = sum(r[1] for r in rows)
    total_cv = sum(r[2] for r in rows)
    summary = {"precincts_compared": len(rows), "median_ratio": round(math.exp(med), 3), "robust_sd_log": round(mad, 3),
               "state_ratio": round(total_reg / total_cv, 3), "listed": len(listed),
               "above_cvap_beyond_margin": sum(1 for x in listed if any("beyond" in w for w in x["why"])),
               "far_from_the_rest": sum(1 for x in listed if any("robust" in w for w in x["why"])),
               "what_it_means": ("Registration above the citizen voting-age estimate is not a fault in itself: Minnesota keeps people "
                                 "who moved on the rolls until they are removed by the process the law sets, the estimate is a "
                                 "2020-2024 average with a margin, college and new-housing precincts change fast, and precinct lines "
                                 "that cut a block group are shared by population. The list is for looking at, not a finding.")}
    return summary, listed


def build(say=print, archive=True, db=DB):
    run = "data-mn-" + now_utc().replace(":", "").replace("-", "")
    cache = cache_dir("mn")
    say("    census: blocks, block groups and CVAP into today's precincts and school districts")
    cdoc = census.build(say)
    save_json(os.path.join(cache, "check_blocks.json"), {"run": run, "controls": cdoc["controls"], "method": cdoc["method"]})
    pfeat = cdoc["units"]["precinct"]
    pop = {v: f["pop2020"][0] for v, f in pfeat.items()}
    today_rows = data_mn.today_precincts()
    tids = [r["vtdid"] for r in today_rows]

    say("    past results: every contest against its official total")
    results, inputs = data_mn.check_contests(say, archive=archive)
    try:
        medsl = data_mn.medsl_check(results, say)
        for y, (url, name) in data_mn.MEDSL.items():
            p = os.path.join(cache_dir("mn", "medsl"), name)
            if os.path.exists(p):
                inputs.append({"input": f"medsl-mn-{y}", "source": f"{url} (file {os.path.relpath(p, HERE)})", "sha256": sha_file(p),
                               "as_of": data_mn.DATES[y], "kind": "secondary",
                               "note": "MIT Election Data and Science Lab, CC0; compiled from the Secretary's results files; labelled secondary"})
    except Exception as e:  # noqa: BLE001  MEDSL is a second look; its absence is said, never hidden
        medsl = {"unread": str(e)}
        say(f"    MEDSL could not be read: {e}")
    arch = sorted(os.listdir(cache_dir("mn", "official", "archive")))
    if arch:
        shas = "".join(load_json(os.path.join(cache_dir("mn", "official", "archive"), a)).get("sha256", "") for a in arch)
        inputs.append({"input": "mn-historical-election-archive", "source": "https://mn.electionarchives.lib.umn.edu/election/<id>/ "
                       f"({len(arch)} pages; party and votes only, in {os.path.relpath(cache_dir('mn', 'official', 'archive'), HERE)})",
                       "sha256": sha_bytes(shas.encode()), "as_of": dt.date.today().isoformat(), "kind": "academic",
                       "note": "University of Minnesota Libraries Publishing; transcribes the State Canvassing Board's reports"})
    inputs.append({"input": "mn-precincts-today", "source": f"{data_mn.TODAY} (Voting Districts, Minnesota)", "sha256": sha_file(data_mn.TODAY),
                   "as_of": load_json(data_mn.TODAY).get("fetched"), "kind": "official", "note": "today's precincts, the kit's copy"})
    held = sum(1 for r in results if r["holds"])
    differ = [r for r in results if r["holds"] is False]
    none = [r for r in results if r["holds"] is None]
    save_json(os.path.join(cache, "check_contests.json"), {"run": run, "contests": len(results), "equal": held, "differ": len(differ),
                                                           "no_official_total": len(none), "medsl_second_look": medsl, "results": results})

    say("    past results onto today's precinct lines")
    feats = {v: {} for v in tids}
    state_feats = {}
    line_reports = {}
    reg2024 = {}
    for year in data_mn.YEARS:
        doc = data_mn.table(year)
        lines, how, rep = data_mn.on_today_lines(year, pop, doc, vtd=cdoc["vtd2020"], t2020=data_mn.table(2020)["rows"], today=today_rows)
        line_reports[year] = rep
        cs = {c["id"]: c for c in data_mn.contests(year, doc)}
        old = {r["vtdid"]: r for r in doc["rows"]}
        today_by = {r["vtdid"]: r for r in today_rows}

        def district_of(v, prefix, old=old, today_by=today_by):
            col = data_mn.OFFICES[prefix][1]
            row = old.get(v) or (today_by.get(v) if year >= 2022 else None)
            return data_mn._dist(row.get(col)) if row and col else None
        f, st = results_features(year, lines, cs, district_of)
        for v, x in f.items():
            if v in feats:
                for k, val in x.items():
                    feats[v][k] = (val[0], None, val[1], how.get(v))
        for k, val in st.items():
            state_feats[k] = (val[0], None, val[1], None)
        if year == 2024:
            reg2024 = {v: (r.get("reg7am", 0) or 0) + (r.get("edr", 0) or 0) for v, r in lines.items()}
        mail = {r["vtdid"]: r.get("mailballot") for r in doc["rows"]}
        if year == 2024:
            for v in feats:
                if v in mail and how.get(v) in ("same name", "same code in the same city or township"):
                    feats[v]["mail_precinct_2024"] = (1.0 if str(mail[v]).strip().upper() == "YES" else 0.0, None,
                                                      "voted entirely by mail in 2024", "same precinct code")
    save_json(os.path.join(cache, "check_lines.json"), {"run": run, "method": data_mn.LINES_METHOD, "years": line_reports})
    for v, f in feats.items():
        mids = [f[f"turnout_{y}"][0] for y in MIDTERMS if f.get(f"turnout_{y}") and f[f"turnout_{y}"][0] is not None]
        if mids:
            f["turnout_midterm_avg"] = (sum(mids) / len(mids), None, f"average of {len(mids)} midterms' turnout", None)
        leans = [f[f"lean_{p}_{y}"][0] for p, y in RECENT if f.get(f"lean_{p}_{y}")]
        if len(leans) == len(RECENT):
            f["lean_recent"] = (sum(leans) / len(leans), None, "plain average of the 2024 President, 2024 U.S. Senate and 2022 Governor leans",
                                None)

    say("    registration against citizens of voting age")
    summary, listed = registration_check(pfeat, today_rows, reg2024)
    save_json(os.path.join(cache, "check_registration_2024.json"), {"run": run, "summary": summary, "listed": listed})

    say("    writing the features")
    con = connect(db)
    with con:
        con.execute("DELETE FROM features WHERE state = 'mn'")
        rows = []
        for kind, units in (("precinct", pfeat), ("school", cdoc["units"]["school"])):
            for uid, f in units.items():
                for name, (val, moe, note) in f.items():
                    rows.append(("mn", kind, uid, name, val, moe, "census", census.CENSUS_METHOD, run, note))
        for v, f in feats.items():
            for name, (val, moe, note, how) in f.items():
                plain = how in (None, "same name", "2020 geography", "2020 geography, by name")
                n = "; ".join(x for x in (note, None if plain else f"carried onto today's lines: {how}") if x) or None
                rows.append(("mn", "precinct", v, name, val, moe, "past-results", FEATURE_METHOD, run, n))
        for v in tids:
            if v not in pfeat:
                rows.append(("mn", "precinct", v, "pop2020", 0, 0.0, "census", census.CENSUS_METHOD, run,
                             "no 2020 block's internal point falls in this precinct"))
        for name, (val, moe, note, _how) in state_feats.items():
            rows.append(("mn", "state", "MN", name, val, moe, "past-results", FEATURE_METHOD, run, note))
        con.executemany("INSERT OR REPLACE INTO features (state, unit_kind, unit_id, name, value, moe, source, method, build, note) "
                        "VALUES (?,?,?,?,?,?,?,?,?,?)", rows)
        con.execute("DELETE FROM run_inputs WHERE run LIKE 'data-mn-%'")
        con.executemany("INSERT OR REPLACE INTO run_inputs (run, input, source, sha256, as_of, kind, note) VALUES (?,?,?,?,?,?,?)",
                        [(run, i["input"], i["source"], i["sha256"], i["as_of"], i["kind"], i["note"]) for i in cdoc["inputs"] + inputs])
    n_feat = len(rows)
    con.close()
    return {"run": run, "features": n_feat, "blocks": cdoc["controls"], "contests": {"total": len(results), "equal": held,
            "differ": [(r["id"], r.get("diff")) for r in differ], "no_official_total": len(none)},
            "registration": summary, "lines": {y: {"placed_by": r["placed_by"], "control": r["control"], "today_without_figures": len(r["today_without_figures"]),
                                                 "gone_unplaced": len(r["gone_unplaced"])}
                                             for y, r in line_reports.items()}, "medsl": medsl}


def selftest(say=print):
    ok = True

    def check(what, got, want):
        nonlocal ok
        good = got == want
        ok &= good
        say(f"    {'ok ' if good else 'BAD'} {what}: {got!r}" + ("" if good else f" (expected {want!r})"))
    lines = {"A": {"totvoting": 100, "reg7am": 110, "edr": 10, "ab_mb": 40, "fedonlyab": 0, "usprsdfl": 60, "usprsr": 30, "usprstotal": 95},
             "B": {"totvoting": 50, "reg7am": 80, "edr": 0, "ab_mb": 10, "fedonlyab": 0, "usprsdfl": 10, "usprsr": 30, "usprstotal": 45}}
    f, st = results_features(2024, lines, {}, lambda v, p: None)
    check("statewide two-party share", round(st["dfl2p_usprs_2024"][0], 6), round(70 / 130, 6))
    check("a precinct's lean", round(f["A"]["lean_usprs_2024"][0], 6), round(60 / 90 - 70 / 130, 6))
    check("turnout", round(f["B"]["turnout_2024"][0], 4), 0.625)
    check("roll-off", round(f["A"]["rolloff_usprs_2024"][0], 4), 0.05)
    pf = {f"P{i}": {"cvap": (1000.0, 50.0), "pop2020": (1300, 0)} for i in range(30)}
    pf["Pbig"] = {"cvap": (1000.0, 50.0), "pop2020": (1300, 0)}
    reg = {k: 900.0 + i for i, k in enumerate(pf)}
    reg["Pbig"] = 2000.0
    summary, listed = registration_check(pf, [], reg)
    check("a precinct registered far above its CVAP is listed", [x["vtdid"] for x in listed], ["Pbig"])
    return ok


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--state", default="mn")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--no-archive", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        ok = census.selftest() & data_mn.selftest() & selftest()
        sys.exit(0 if ok else 1)
    if a.state != "mn":
        sys.exit("    only Minnesota is built here (other states: data_us.py, later)")
    out = build(archive=not a.no_archive)
    print(f"    run {out['run']}: {out['features']:,} feature rows")
    for k, v in out["blocks"].items():
        print(f"    check 1, {k}: {v}")
    print(f"    check 2, registration: {out['registration']}")
    c = out["contests"]
    print(f"    check 3, contests: {c['total']} in all, {c['equal']} equal their official total, {len(c['differ'])} differ, "
          f"{c['no_official_total']} with no official total reachable")
    for cid, diff in c["differ"]:
        print(f"      differs: {cid} {diff}")
    for y, r in out["lines"].items():
        print(f"    lines {y}: {r}")
    print(f"    MEDSL second look: { {y: (v['contests_equal'], v['contests_differ']) for y, v in out['medsl'].items()} if 'unread' not in out['medsl'] else out['medsl'] }")


if __name__ == "__main__":
    main()
