"""election/model/live_model.py - the night's model: every Minnesota race's chances and likely vote ranges from the votes
counted so far (ARCHITECTURE.md 4.1 "On the night", 4.6; model.md 3.3). Owned by N17. Analysis, never a result.

    election.model.live_model.run(state=, now=, db=, rehearsal=, say=)    what run_night.py calls after a state's new
                                                                           results (at most once a cycle)
    python -m election.model.live_model --state mn [--db <results db>] [--model-db <model db>] [--dry-run]
    python -m election.model.live_model --snapshot <published snapshot folder> --scratch <folder>
                                       a snapshot folder (the practice figures) read into a scratch results database, the
                                       model run on it against a scratch copy of the model database
    python -m election.model.live_model --check --snapshot <folder> --scratch <folder>
                                       ARCHITECTURE.md 5.3's checks on scratch copies: two moments of a replayed night, each
                                       run timed (limit 30 s), every stored run redone exactly, no 0 or 100, nothing for an
                                       unopposed race, the replays' calibration on file
    python -m election.model.live_model --selftest                         the arithmetic on made-up precincts

WHERE IT STARTS: the newest pre-election run (forecast.py) - its precinct leans, expected ballots, environment and every
race's prior - and the night's parameters, sized by the replays of 2022 and 2024 (blindspots.py, kind "replay"; until
one is on file, the starting values below, and the run says so).

WHAT IT DOES WITH THE VOTES COUNTED (each precinct in Minnesota reports once, complete, Minn. Stat. 204C.19)
  1. The swing surface. The governor's race is on every ballot, so it is the anchor: in each precinct counted, how far
     its DFL share of the two-party vote (log-odds) is from the forecast's expectation there. Those gaps are explained
     by a statewide shift, a shift for each congressional district, a shift for each county and five Census terms (the
     precinct's recent trend, education, density, age, lean), each pulled toward no shift while few precincts are in
     (a Gaussian prior, sized by how far 2022's and 2024's precincts moved from their own forecasts). A precinct's own
     noise is learned from the night once enough precincts are in. Solved exactly (the counties' block is diagonal).
  2. Each other partisan race runs ahead of or behind the governor's race by an offset (its candidates, its district),
     learned from its own precincts counted, against the governor's race in the same precincts; before any are in, the
     offset is the forecast's. Its precincts still out are projected: lean + the race's forecast + the swing surface +
     the offset, each with its uncertainty.
  3. Turnout: each counted precinct's votes in the governor's race against what was expected there give a turnout ratio,
     pulled toward the state's and the county's; the precincts still out are expected to vote likewise.
  4. Nonpartisan races (and partisan ones without one DFL and one Republican name): each name's share in the precincts
     still out starts from the forecast and is moved by the share counted so far, by how much the counted precincts can
     say: candidates' home bases make early precincts unrepresentative, so the counted share is trusted by the number of
     precincts behind it, a part of a home-base lean never averages away, and the range widens the more the precincts
     counted differ in size from those still out (small rural precincts often come first). A race with nothing counted
     keeps its pre-election forecast.
  5. John's three blind spots (blindspots.py): count order - the precincts counted first are never assumed typical (1 to
     4 take the counted precincts' places into account), each county's late absentee ballots (received after 3 p.m. on
     Election Day, added later, Minn. Stat. 204C.19 subd. 3) are an outstanding block of their own with an unknown lean,
     until the county adds them, and the ranges are sized by replays counted in four orders; roll-off - each race's
     expected votes come from each precinct's 2022 share of voters skipping that kind of race, corrected by what tonight's
     precincts show; ballot position - the rebuilt rotation says which names led the ballot where the votes counted came
     from and where those still out will, and the first-line edge (a prior) moves the projection by the difference.
  6. simulate.py draws 1,500 possible ends of the count; each candidate's chance (never 0 or 100), median share, 80 and
     95 percent ranges and the race's expected total follow. Every run is kept as a version (runs.py, kind "live").

RACES IN A LIVE RUN: every contested partisan race (the swing surface moves them all, counted or not) and every other
contested race with votes counted; a race with nothing counted keeps its pre-election row, and an unopposed race never
gets a forecast. A certified race is not modelled: the official count decides.
"""

import argparse
import datetime as dt
import json
import math
import os
import re
import shutil
import sqlite3
import sys
import time
from collections import defaultdict

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from election.model import DB as MODEL_DB  # noqa: E402
from election.model import runs as R  # noqa: E402
from election.model import simulate as S  # noqa: E402

LIVE_METHOD = "live-1.0"
DRAWS = 1500
STATE = "MN"
ANCHOR_KINDS = ("governor", "us_senate", "attorney_general", "secretary_of_state", "state_auditor")
FEATURES = ("trend", "education", "density", "age65", "lean")
NP_GROUP_RO = {"county": "county", "judicial": "judicial", "soil_water": "soil_water"}

# The night's parameters before any replay has sized them (blindspots.calibrate writes fitted ones, kind "replay"). The
# precinct spreads are 2022's and 2024's own (precincts moved about 0.12 in log-odds from their forecasts, within
# counties; counties about 0.06; congressional districts about 0.045; a down-ballot race's precincts about 0.07 from
# the top of the ticket).
DEFAULT_NIGHT = {
    "fitted": False, "source": "starting values: no replay calibration on file",
    "sigma_u": 0.12,              # a precinct's own gap from the swing surface (log-odds)
    "tau_c": 0.07,                # a county's shift, prior spread
    "tau_r": 0.045,               # a congressional district's shift, prior spread
    "tau_b": 0.03,                # a Census term per standard deviation, prior spread
    "sigma_v": 0.07,              # a precinct's gap between a race and the governor's race, beyond the race's offset
    "tau_g": 0.04,                # a race's offset in one county beyond its offset overall
    "scale_p": 1.0,               # partisan spreads times this (the replays' calibration)
    "adapt_k0": 200,              # precincts' worth of weight on sigma_u before the night's own spread is used
    "turn": {"sd_state": 0.08, "tau_c": 0.08, "sigma": 0.15},
    "rolloff": {"prior_sd_p": 0.08, "prior_sd_np": 0.2, "sigma": 0.15},
    "np": {"sigma_h": 0.35, "rho": 0.10, "scale": 1.0, "k0_wi": 200, "kappa": 0.0},
    "late": {"median": 0.03, "sdlog": 0.7, "county_sdlog": 0.3, "lean_sd": 0.2},
    "other": {"k0": 500, "sd_few": 0.25, "sd_many": 0.1},
}


def say_default(*a):
    print(*a, flush=True)


# ============================================================================================== small helpers

def logit(p):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def expit(x):
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    e = math.exp(x)
    return e / (1.0 + e)


def r6(x):
    return None if x is None else float(f"{x:.6g}")


def r4(x):
    return None if x is None else float(f"{x:.4g}")


def r3(x):
    return None if x is None else float(f"{x:.3g}")


def merge(base, over):
    out = json.loads(json.dumps(base))
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = merge(out[k], v)
        else:
            out[k] = v
    return out


def chol(A):
    n = len(A)
    L = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1):
            s = A[i][j] - sum(L[i][k] * L[j][k] for k in range(j))
            if i == j:
                L[i][j] = math.sqrt(max(s, 1e-14))
            else:
                L[i][j] = s / L[j][j]
    return L


def chol_solve(L, b):
    n = len(L)
    y = [0.0] * n
    for i in range(n):
        y[i] = (b[i] - sum(L[i][k] * y[k] for k in range(i))) / L[i][i]
    x = [0.0] * n
    for i in reversed(range(n)):
        x[i] = (y[i] - sum(L[k][i] * x[k] for k in range(i + 1, n))) / L[i][i]
    return x


def inverse_spd(A):
    L = chol(A)
    n = len(A)
    cols = [chol_solve(L, [1.0 if r == c else 0.0 for r in range(n)]) for c in range(n)]
    return [[cols[c][r] for c in range(n)] for r in range(n)]


def name_key(name):
    s = str(name or "").lower()
    s = re.sub(r"\([^)]*\)", " ", s)
    return re.sub(r"[^a-z0-9]+", "", s)


# ============================================================================================== the swing surface

def unit_row(U, i):
    """The swing surface's design for unit i: indexes into the "g" block and their values (statewide, its district, the
    Census terms); the county is apart (its block is diagonal)."""
    nR = len(U["regions"])
    idx = [0, 1 + U["reg"][i]] + [1 + nR + f for f in range(len(U["fnames"]))]
    return idx, [1.0, 1.0] + list(U["Z"][i])


def fit_surface(U, rep, m_a, v_s, prm, adapt=True):
    """The anchor race's gaps in the counted units, explained (module docstring, 1). rep: [(unit, DFL votes, Republican
    votes)]. Returns the posterior: g (statewide, districts, Census terms) with its covariance, each county's shift given
    g (mean, conditional variance and its coefficients on g), and the precinct spread used."""
    nR, k, nC = len(U["regions"]), len(U["fnames"]), len(U["counties"])
    G = 1 + nR + k
    pri = [1.0 / max(v_s, 1e-6)] + [1.0 / prm["tau_r"] ** 2] * nR + [1.0 / prm["tau_b"] ** 2] * k
    obs = []
    for i, d, r in rep:
        n2 = d + r
        if n2 < 1:
            continue
        p = (d + 0.5) / (n2 + 1.0)
        e = math.log(p / (1 - p)) - U["L"][i] - m_a
        obs.append((i, e, 1.0 / ((n2 + 1.0) * p * (1 - p))))

    def solve(su2):
        Pgg = [[0.0] * G for _ in range(G)]
        bg = [0.0] * G
        pgc = [[0.0] * G for _ in range(nC)]
        Dc = [1.0 / prm["tau_c"] ** 2] * nC
        bc = [0.0] * nC
        for i, e, binom in obs:
            w = 1.0 / (su2 + binom)
            idx, vals = unit_row(U, i)
            c = U["cty"][i]
            for a in range(len(idx)):
                va = vals[a] * w
                bg[idx[a]] += va * e
                pgc[c][idx[a]] += va
                row = Pgg[idx[a]]
                for b in range(len(idx)):
                    row[idx[b]] += va * vals[b]
            Dc[c] += w
            bc[c] += e * w
        for j in range(G):
            Pgg[j][j] += pri[j]
        M = [row[:] for row in Pgg]
        rhs = bg[:]
        for c in range(nC):
            if Dc[c] <= 1.0 / prm["tau_c"] ** 2 + 1e-12:
                continue                      # a county with nothing counted adds nothing
            pc, dc = pgc[c], Dc[c]
            nz = [j for j in range(G) if pc[j]]
            for a in nz:
                for b in nz:
                    M[a][b] -= pc[a] * pc[b] / dc
                rhs[a] -= pc[a] * bc[c] / dc
        cov = inverse_spd(M)
        g = [sum(cov[a][b] * rhs[b] for b in range(G)) for a in range(G)]
        Ch = [(bc[c] - sum(pgc[c][j] * g[j] for j in range(G))) / Dc[c] for c in range(nC)]
        return {"G": G, "g": g, "cov": cov, "C": Ch, "cd": [1.0 / x for x in Dc], "a": [[x / Dc[c] for x in pgc[c]] for c in range(nC)]}

    su2 = prm["sigma_u"] ** 2
    fit = solve(su2)
    n = len(obs)
    if adapt and n >= 30:
        ex = []
        for i, e, binom in obs:
            idx, vals = unit_row(U, i)
            pred = sum(fit["g"][j] * v for j, v in zip(idx, vals)) + fit["C"][U["cty"][i]]
            ex.append((e - pred) ** 2 - binom)
        s2 = max(sum(ex) / len(ex), 0.25 * su2)
        k0 = prm.get("adapt_k0", 200)
        new = (k0 * su2 + n * s2) / (k0 + n)
        new = min(max(new, 0.5 * su2), 2.5 * su2)
        if abs(new - su2) > 0.05 * su2:
            su2 = new
            fit = solve(su2)
    fit["sigma_u"] = math.sqrt(su2)
    fit["n"] = n
    return fit


def surface_at(U, fit, i):
    """The fitted gap of the anchor race in unit i (mean)."""
    idx, vals = unit_row(U, i)
    return sum(fit["g"][j] * v for j, v in zip(idx, vals)) + fit["C"][U["cty"][i]]


def fit_turnout(U, rep, prm):
    """Turnout against the forecast's expected votes: rep [(unit, votes counted in the anchor race, expected)]. A
    statewide log ratio and county ones, pulled toward none. Returns (S, var S, county means, county conditional
    variances, county coefficients on S)."""
    t = prm["turn"]
    nC = len(U["counties"])
    P, b = 1.0 / t["sd_state"] ** 2, 0.0
    Dc = [1.0 / t["tau_c"] ** 2] * nC
    bc = [0.0] * nC
    pc = [0.0] * nC
    for i, tot, ev in rep:
        if ev <= 0:
            continue
        x = math.log((tot + 1.0) / (ev + 1.0))
        w = 1.0 / (t["sigma"] ** 2 + 1.0 / (tot + 1.0))
        c = U["cty"][i]
        P += w
        b += x * w
        Dc[c] += w
        bc[c] += x * w
        pc[c] += w
    M, rhs = P, b
    for c in range(nC):
        if pc[c]:
            M -= pc[c] * pc[c] / Dc[c]
            rhs -= pc[c] * bc[c] / Dc[c]
    s = rhs / M
    C = [(bc[c] - pc[c] * s) / Dc[c] for c in range(nC)]
    return {"S": s, "vS": 1.0 / M, "C": C, "cd": [1.0 / x for x in Dc], "a": [pc[c] / Dc[c] for c in range(nC)]}


# ============================================================================================== the races' entries

def race_offset(spec, ob, U, anchor_rep, fit, prm, dm, m_a):
    """A partisan race's offset from the anchor race (log-odds), beyond the forecast's expected difference dm: its
    posterior mean and variance from the race's own counted precincts, each compared with the anchor race in the same
    precinct (or with the swing surface where the anchor is not counted there). Counties are clusters."""
    if spec.get("anchor"):
        return 0.0, 0.0
    iD, iR = spec["iD"], spec["iR"]
    byc = defaultdict(lambda: [0.0, 0.0, 0.0])           # county -> [sum w x, sum w, n]
    su2, sv2 = fit["sigma_u"] ** 2, prm["sigma_v"] ** 2
    for i, v in ob["rep"].items():
        d, r = v[iD], v[iR]
        if d + r < 1:
            continue
        p = (d + 0.5) / (d + r + 1.0)
        y = math.log(p / (1 - p))
        binom = 1.0 / ((d + r + 1.0) * p * (1 - p))
        a = anchor_rep.get(i)
        if a is not None:
            pa = (a[0] + 0.5) / (a[0] + a[1] + 1.0)
            x = y - math.log(pa / (1 - pa)) - dm
            var = sv2 + binom + 1.0 / ((a[0] + a[1] + 1.0) * pa * (1 - pa))
        else:
            x = y - (U["L"][i] + m_a + surface_at(U, fit, i)) - dm
            var = sv2 + su2 + binom
        w = 1.0 / var
        acc = byc[U["cty"][i]]
        acc[0] += w * x
        acc[1] += w
        acc[2] += 1
    prec = 1.0 / max(spec["vd"], 1e-6)
    num = 0.0
    tg2 = prm["tau_g"] ** 2
    for c, (swx, sw, _n) in byc.items():
        mean_c = swx / sw
        var_c = 1.0 / sw + tg2
        prec += 1.0 / var_c
        num += mean_c / var_c
    return num / prec, 1.0 / prec


def rotation_gap(spec, members, U, counted_w, remaining_w):
    """The ballot-position blind spot on the night: under the rebuilt rotation, each base position's share of the votes
    still out less its share of the votes counted (where the race is rotated); None where nothing would move."""
    from election.model import blindspots as B
    n = len(spec["cands"])
    if not spec.get("rot") or spec.get("first") is not None or n < 2:
        return None
    rot = B.rotation_of(members, U, n)
    gap = B.exposure_gap(rot, members, counted_w, remaining_w, n)
    if gap is None or max(abs(x) for x in gap) < 0.005:
        return None
    return [r4(x) for x in gap]


def build_entries(U, specs, obs, prm, late_done=frozenset(), anchor_id=None, say=say_default):
    """The frame's races and shared block from the units U, the races' specs and the votes counted (obs). The same code
    serves the night (live_model.run) and the replays of past nights (blindspots.replays).

    U: {"ids", "L" (lean, log-odds), "cty" (county index), "counties", "reg" (district index), "regions", "Z" (Census
        terms, standardised), "fnames", "ab" (absentee share), "regs" (registered, for the rotation)}
    specs: [{"race", "kind": "partisan" | "multi", "seats", "cands": [{"key", "name", "p", ...}], "members": [(unit,
        weight)], "ev": [expected votes of each member], "status" (unopposed, ...), partisan "two" races: "iD", "iR",
        "m" (the forecast's shift), "vd" (prior variance of the offset from the anchor), "anchor"; multi races: "mu",
        "tau", "df", "first", "rot"; "tested"}
    obs: {race: {"rep": {unit: [votes of each candidate ..., other votes]}, "in": units in or None, "all": or None,
        "offmap": votes in units not on the map}}"""
    from election.model import blindspots as B
    t0 = time.time()
    nC = len(U["counties"])
    specs_by = {s["race"]: s for s in specs}
    anchor = specs_by.get(anchor_id) if anchor_id else None
    report = {"anchor": anchor_id}
    # ---- 1. the swing surface from the anchor race
    anchor_rep = {}
    if anchor is not None and anchor_id in obs:
        iD, iR = anchor["iD"], anchor["iR"]
        for i, v in obs[anchor_id]["rep"].items():
            anchor_rep[i] = (v[iD], v[iR], sum(v))
    v_s = anchor["v_s"] if anchor else 0.02
    m_a = anchor["m"] if anchor else 0.0
    fit = fit_surface(U, [(i, a[0], a[1]) for i, a in sorted(anchor_rep.items())], m_a, v_s, prm)
    # how the anchor race's counted precincts compare with what the forecast expected in those same precincts
    got = exp_ = tw = 0.0
    for i, a in anchor_rep.items():
        n2 = a[0] + a[1]
        if n2 > 0:
            got += a[0]
            exp_ += n2 * expit(U["L"][i] + m_a)
            tw += n2
    report["surface"] = {"units": fit["n"], "statewide_shift": r4(fit["g"][0]), "statewide_sd": r4(math.sqrt(fit["cov"][0][0])),
                         "sigma_u": r4(fit["sigma_u"]), "counted_gap_pts": r4((got - exp_) / tw * 100) if tw else None}
    # ---- 3. turnout from the anchor race (expected votes of the anchor in each unit)
    ev_anchor = {}
    if anchor is not None:
        for (i, w), ev in zip(anchor["members"], anchor["ev"]):
            ev_anchor[i] = ev_anchor.get(i, 0.0) + ev
    turn = fit_turnout(U, [(i, a[2], ev_anchor.get(i, 0.0)) for i, a in sorted(anchor_rep.items())], prm)
    report["turnout"] = {"ratio": r4(math.exp(turn["S"])), "units": len(anchor_rep)}
    tf = [math.exp(turn["S"] + turn["C"][U["cty"][i]]) for i in range(len(U["ids"]))]
    # ---- the late absentee batches (count order): which counties still have theirs out
    late = prm["late"]
    late_counties = [c for c in range(nC) if U["counties"][c] not in late_done]
    late_index = {c: k for k, c in enumerate(late_counties)}
    sp = prm["scale_p"]
    entries = []
    counts = defaultdict(int)
    for spec in specs:
        rid = spec["race"]
        if spec.get("status") in ("unopposed", "no-candidates", "not-modelled"):
            entries.append({"race": rid, "kind": spec.get("kind", "multi"), "status": spec["status"], "seats": spec.get("seats", 1),
                            "cands": [{"key": c["key"], "name": c["name"]} for c in spec["cands"]], "note": spec.get("note")})
            counts[spec["status"]] += 1
            continue
        ob = obs.get(rid) or {"rep": {}}
        n = len(spec["cands"])
        members = spec.get("members") or []
        mem_set = {i for i, _w in members}
        rep = ob["rep"]
        C = [0.0] * n
        cwi = float(ob.get("offmap_other") or 0)
        for i, v in rep.items():
            for k in range(n):
                C[k] += v[k]
            cwi += v[n]
        for k, x in enumerate(ob.get("offmap") or []):
            C[k] += x
        counted = sum(C) + cwi
        units_in = sum(1 for i in mem_set if i in rep)
        units_all = len(mem_set)
        # the file's own count of precincts in (its summary line) is used only where it agrees with the map's count of the
        # race's precincts; a summary saved at another moment, or covering part of the race, is set aside (and said)
        store_ok = False
        if ob.get("all"):
            s_in, s_all = int(ob.get("in") or 0), int(ob["all"])
            if not units_all or abs(s_all - units_all) <= max(2, 0.1 * units_all):
                units_in, units_all, store_ok = s_in, s_all, True
            else:
                counts["summary set aside"] += 1
        if spec["kind"] == "multi" and counted <= 0 and not spec.get("keep_without_votes"):
            continue                                # nothing counted: the pre-election row stands
        # roll-off on the night: the race's votes against the anchor's in the same counted units
        ro = B.rolloff_update(spec, rep, anchor_rep, ev_anchor, n, prm) if not spec.get("anchor") else (0.0, 0.0)
        # the remaining units: expected votes after turnout and roll-off, less the late batch they will not include
        rem = []
        for (i, w), ev in zip(members, spec.get("ev") or []):
            if i in rep or ev <= 0:
                continue
            rem.append((i, ev * tf[i] * math.exp(ro[0]) * (1.0 - late["median"] * U["ab"][i])))
        adj = 1.0
        if store_ok and ob.get("in") is not None:
            left = max(int(ob["all"]) - int(ob["in"]), 0)
            unrep = sum(1 for i in mem_set if i not in rep)
            if left == 0:
                rem = []
            elif unrep > 0:
                adj = min(max(left / unrep, 0.0), 2.0)
        if adj != 1.0:
            rem = [(i, x * adj) for i, x in rem]
        Rv = sum(x for _i, x in rem)
        # turnout and roll-off uncertainty of what is still out (log scale)
        rsd2 = ro[1]
        if Rv > 0:
            byc = defaultdict(float)
            sq = 0.0
            for i, x in rem:
                byc[U["cty"][i]] += x / Rv
                sq += (x / Rv) ** 2
            lin = sum(w_c * (1.0 - turn["a"][c]) for c, w_c in byc.items())
            rsd2 += turn["vS"] * lin * lin + sum(w_c * w_c * turn["cd"][c] for c, w_c in byc.items()) + prm["turn"]["sigma"] ** 2 * sq
        # each county's outstanding late batch for this race
        late_by = defaultdict(float)
        for (i, w), ev in zip(members, spec.get("ev") or []):
            c = U["cty"][i]
            if c in late_index and ev > 0:
                late_by[c] += ev * tf[i] * U["ab"][i] * late["median"]
        status = "done" if units_all and units_in >= units_all and not rem else ("counting" if units_in > 0 or counted > 0 else "pre")
        e = {"race": rid, "kind": spec["kind"], "status": status, "seats": spec.get("seats", 1),
             "cands": [{"key": c["key"], "name": c["name"], **({"p": c["p"]} if c.get("p") else {})} for c in spec["cands"]],
             "units_in": units_in, "units_all": units_all, "counted": int(round(counted)), "C": [int(round(x)) for x in C],
             "Cwi": int(round(cwi)), "R": r3(Rv) or 0.0, "Rsd": r3(math.sqrt(max(rsd2, 0.0))), "tested": spec.get("tested")}
        if spec["kind"] == "partisan":
            iD, iR = spec["iD"], spec["iR"]
            dm = spec["m"] - m_a
            d_hat, v_d = race_offset(spec, ob, U, {i: a[:2] for i, a in anchor_rep.items()}, fit, prm, dm, m_a)
            # the other names' share of what is still out (minor parties and write-ins)
            oth_c = counted - C[iD] - C[iR]
            k0 = prm["other"]["k0"]
            o = (oth_c + k0 * spec.get("oth_prior", 0.02)) / (counted + k0)
            minors = [k for k in range(n) if k not in (iD, iR)]
            mix_raw = [C[k] + 1.0 for k in minors] + [cwi + 0.5]
            if not counted:
                mix_raw = [spec.get("minor_prior", 1.0) for _k in minors] + [spec.get("wi_prior", 0.2)]
            ms = sum(mix_raw)
            # the remaining units' expected DFL share and its curve
            ws = wpp = 0.0
            sp_ = 0.0
            xg = [0.0] * fit["G"]
            xcty = defaultdict(float)
            sq = 0.0
            q_c = defaultdict(lambda: [0.0, 0.0])           # county -> [DFL, two-party], counted and projected
            for i, v in rep.items():
                q_c[U["cty"][i]][0] += v[iD]
                q_c[U["cty"][i]][1] += v[iD] + v[iR]
            for i, x in rem:
                eta = U["L"][i] + spec["m"] + surface_at(U, fit, i) + d_hat
                p = expit(eta)
                two = x * (1.0 - o)
                wv = two * p * (1 - p)
                ws += two
                sp_ += two * p
                wpp += wv
                idx, vals = unit_row(U, i)
                for j, val in zip(idx, vals):
                    xg[j] += wv * val
                xcty[U["cty"][i]] += wv
                sq += wv * wv
                q_c[U["cty"][i]][0] += two * p
                q_c[U["cty"][i]][1] += two
            if ws > 0 and wpp > 0:
                s0 = sp_ / ws
                kap = wpp / (ws * s0 * (1 - s0))
                xg = [x / wpp for x in xg]
                h = xg[:]
                xc = []
                tg = 0.0
                for c, wc in xcty.items():
                    f = wc / wpp
                    for j in range(fit["G"]):
                        if fit["a"][c][j]:
                            h[j] -= f * fit["a"][c][j]
                    xc.append([c, r6(sp * f * math.sqrt(fit["cd"][c]))])
                    tg += f * f
                noise = (fit["sigma_u"] ** 2 + (0.0 if spec.get("anchor") else prm["sigma_v"] ** 2)) * sq / (wpp * wpp)
                ve = sp * sp * (v_d + prm["tau_g"] ** 2 * tg * (0.0 if spec.get("anchor") else 1.0) + noise)
                e.update(s0=r6(s0), kap=r6(kap), h=[[j, r6(sp * x)] for j, x in enumerate(h) if abs(x) > 1e-9],
                         xc=sorted(xc), ve=r6(ve))
            else:
                e.update(s0=0.5, kap=1.0, h=[], xc=[], ve=0.0)
            e.update(iD=iD, iR=iR, minors=minors, mix=[r4(x / ms) for x in mix_raw], oth=r4(o),
                     oth_sd=prm["other"]["sd_many"] if counted > 2000 else prm["other"]["sd_few"])
            lt = []
            tot_d = sum(x[0] for x in q_c.values())
            tot_2 = sum(x[1] for x in q_c.values())
            q_all = tot_d / tot_2 if tot_2 > 0 else 0.5
            for c, lv in sorted(late_by.items()):
                qq = q_c.get(c)
                q = (qq[0] / qq[1]) if qq and qq[1] > 0 else q_all
                lt.append([late_index[c], r3(lv), r4(min(max(q, 0.01), 0.99))])
            e["late"] = lt
            e["pos"] = rotation_gap(spec, members, U, {i: sum(v[:n]) for i, v in rep.items()}, dict(rem)) if (rem and rep) else None
            e["offset"] = [r4(d_hat), r4(math.sqrt(v_d))]
            counts["partisan " + ("counted" if units_in else "none counted")] += 1
        else:
            npp = prm["np"]
            mu = list(spec["mu"])
            tau = spec["tau"]
            first = spec.get("first")
            if counted > 0:
                tot_named = sum(C)
                ell = [math.log((C[k] + 0.5) / (tot_named + 0.5 * n)) for k in range(n)]
                wts = [sum(v[:n]) for v in rep.values()]
                sw, sw2 = sum(wts), sum(x * x for x in wts)
                n_rep = (sw * sw / sw2) if sw2 > 0 else 1.0
                remv = [x for _i, x in rem]
                rw, rw2 = sum(remv), sum(x * x for x in remv)
                n_rem = (rw * rw / rw2) if rw2 > 0 else 1.0
                sh2, rho = npp["sigma_h"] ** 2, npp["rho"]
                v_rep_base = sh2 * ((1 - rho) / max(n_rep, 1.0) + rho)
                v_rem = sh2 * ((1 - rho) / max(n_rem, 1.0) + rho) if remv else 0.0
                # count order: precincts counted that are much smaller (or larger) than those still out say less about
                # them (small rural precincts first, the towns later); the gap in their typical size widens the range
                if remv and npp.get("kappa"):
                    lrep = [math.log1p(sum(v[:n + 1])) for v in rep.values()]
                    lrem = [math.log1p(x) for x in remv]
                    imb = sum(lrep) / len(lrep) - sum(lrem) / len(lrem)
                    v_rem += (npp["kappa"] * imb) ** 2
                mu_c = sum(mu) / n
                ell_c = sum(ell) / n
                post, sds = [], []
                for k in range(n):
                    v_rep = v_rep_base + 1.0 / (C[k] + 1.0)
                    pr = 1.0 / (tau * tau) + 1.0 / v_rep
                    post.append(((mu[k] - mu_c) / (tau * tau) + (ell[k] - ell_c) / v_rep) / pr)
                    sds.append(npp["scale"] * math.sqrt(1.0 / pr + v_rem))
                k0 = npp["k0_wi"]
                wi = (cwi + k0 * spec.get("wi_prior", 0.006)) / (counted + k0)
                e.update(mu=[r6(x) for x in post], sd=[r6(x) for x in sds], df=None, wi=r4(wi), equal=False)
                first = None                               # the counted shares already carry the first line's edge
            else:
                e.update(mu=[r6(x) for x in mu], sd=[r6(tau)] * n, df=spec.get("df"), wi=r4(spec.get("wi_prior", 0.006)),
                         equal=bool(spec.get("equal")))
            e["first"] = first
            e["pg"] = spec.get("pg", "np")
            e["pos"] = (rotation_gap(spec, members, U, {i: sum(v[:n]) for i, v in rep.items()}, dict(rem))
                        if (rem and rep and first is None) else None)
            e["late"] = [[late_index[c], r3(lv)] for c, lv in sorted(late_by.items())]
            counts["multi " + ("counted" if counted > 0 else "none counted")] += 1
        entries.append(e)
    shared = {"g": {"dims": ["statewide"] + [f"district {x}" for x in U["regions"]] + [f"census {x}" for x in U["fnames"]],
                    "cov": [[r6(x) for x in row] for row in fit["cov"]]},
              "counties": list(U["counties"]),
              "late": {"counties": [U["counties"][c] for c in late_counties], "sdlog": late["sdlog"], "county_sdlog": late["county_sdlog"],
                       "lean_sd": late["lean_sd"]},
              "pos": {"partisan": list(prm.get("pos_partisan", [0.0, 0.04])), "nonpartisan": list(prm.get("pos_nonpartisan", [0.04, 0.16]))}}
    report["races"] = dict(counts)
    report["late_outstanding"] = len(late_counties)
    report["built_in"] = round(time.time() - t0, 2)
    return entries, shared, report, {"fit": fit, "turn": turn}


# ============================================================================================== the analytic summary (replays)

def predictive_two_party(e, shared):
    """A partisan entry's final DFL share of the two-party vote, as a mean and a standard deviation, by the same terms
    simulate.py draws (linearised): for scoring replays at many settings without drawing."""
    from election.model import simulate as Sim
    C = e["C"]
    iD, iR = e["iD"], e["iR"]
    o = e.get("oth") or 0.0
    Rtwo = (e.get("R") or 0.0) * (1 - o)
    late = e.get("late") or []
    Ltwo = sum(lv for _c, lv, _q in late) * (1 - o)
    Ld = sum(lv * q for _c, lv, q in late) * (1 - o)
    s0 = e.get("s0", 0.5)
    T2 = C[iD] + C[iR] + Rtwo + Ltwo
    if T2 <= 0:
        return 0.5, 0.25
    F = (C[iD] + Rtwo * s0 + Ld) / T2
    cov = shared["g"]["cov"]
    hv = dict((j, c) for j, c in (e.get("h") or []))
    var_d = sum(hv[a] * cov[a][b] * hv[b] for a in hv for b in hv) + sum(c * c for _j, c in (e.get("xc") or [])) + (e.get("ve") or 0.0)
    dF = Rtwo * s0 * (1 - s0) * e.get("kap", 1.0) / T2
    var = dF * dF * var_d
    ls = shared["late"]
    for _c, lv, q in late:
        lt = lv * (1 - o)
        var += (lt * q * (1 - q) * ls["lean_sd"] / T2) ** 2 + (lt * (q - F) / T2) ** 2 * (ls["sdlog"] ** 2 + ls["county_sdlog"] ** 2)
    var += (Rtwo * (s0 - F) / T2) ** 2 * (e.get("Rsd") or 0.0) ** 2
    _ = Sim
    return F, math.sqrt(max(var, 1e-10))


# ============================================================================================== Minnesota's base (cached)

_BASE = {}
_SAID = set()


def newest_pre(model_db, state):
    """(run id, frame) of the newest finished pre-election run of a state (never a rehearsal), or (None, None)."""
    if not os.path.exists(model_db):
        return None, None
    con = R.connect(model_db)
    try:
        row = con.execute("SELECT run, frame_sha FROM runs WHERE state = ? AND kind = 'pre' AND rehearsal = 0 AND ended IS NOT NULL "
                          "ORDER BY started DESC, run DESC LIMIT 1", (state.upper(),)).fetchone()
        if not row:
            return None, None
        return row[0], (R.get_blob(con, row[1]), row[1])
    finally:
        con.close()


def night_params(model_db, state="MN"):
    """The newest replay calibration's parameters (blindspots.calibrate), or the starting values."""
    if os.path.exists(model_db):
        con = R.connect(model_db)
        try:
            row = con.execute("SELECT run, frame_sha FROM runs WHERE state = ? AND kind = 'replay' AND method = ? AND ended IS NOT NULL "
                              "ORDER BY started DESC, run DESC LIMIT 1", (state.upper(), LIVE_METHOD)).fetchone()
            if row:
                doc = R.get_blob(con, row[1]) or {}
                if doc.get("params"):
                    return merge(DEFAULT_NIGHT, doc["params"]), row[0]
        finally:
            con.close()
    return json.loads(json.dumps(DEFAULT_NIGHT)), None


def feature_names_for(year):
    if year >= 2026:
        return ("lean_usprs_2024", "lean_usprs_2020")
    return ("lean_usprs_2020", "lean_usprs_2016")


def census_terms(feats, ids, L, year):
    """The swing surface's Census terms for each precinct, standardised: the precinct's recent trend (its presidential
    lean's change over the last two presidential elections before `year`), education (share with a bachelor's degree),
    density (log), age (share 65 and over) and its lean. A missing figure is the average."""
    a, b = feature_names_for(year)
    raw = []
    for i, v in enumerate(ids):
        x1, x0 = feats.get(a, {}).get(v), feats.get(b, {}).get(v)
        dens = feats.get("density2020", {}).get(v)
        raw.append([(x1 - x0) if (x1 is not None and x0 is not None) else None,
                    feats.get("share_bachelors_plus", {}).get(v),
                    math.log1p(dens) if dens is not None else None,
                    feats.get("share_65plus", {}).get(v),
                    L[i]])
    k = len(FEATURES)
    out = [[0.0] * k for _ in ids]
    for f in range(k):
        vals = [r[f] for r in raw if r[f] is not None]
        if len(vals) < 2:
            continue
        m = sum(vals) / len(vals)
        sd = math.sqrt(sum((x - m) ** 2 for x in vals) / (len(vals) - 1)) or 1.0
        for i, r in enumerate(raw):
            out[i][f] = 0.0 if r[f] is None else max(min((r[f] - m) / sd, 4.0), -4.0)
    return out


def base_for(pre_run, frame, frame_sha, say=say_default):
    """Everything static the night needs from the pre-election run and the precincts' features, cached per pre run."""
    key = (pre_run, frame_sha)
    if key in _BASE:
        return _BASE[key]
    from election.model import blindspots as B
    from election.model import forecast as F
    t0 = time.time()
    P = frame["precincts"]
    ids = P["ids"]
    _ids_map, props_map, geo_v = F.precinct_props()
    props = {v: props_map.get(v) or {} for v in ids}         # a precinct the map no longer has keeps no district
    off_map = sum(1 for v in ids if v not in props_map)
    index = F.members_index(ids, props)
    names = sorted({f"rolloff_{c}_2022" for c in ("mngov", "mnsos", "mnag", "mnaud", "usrep", "mnsen", "mnleg")} |
                   {"rolloff_ussen_2018", "registered_2024", "share_absentee_mail_2022", "share_bachelors_plus", "density2020",
                    "share_65plus", *feature_names_for(2026)})
    feats, _state, build = F.read_features(names)
    L = [float(x) for x in P["lean"]]
    counties = sorted({(props.get(v) or {}).get("county") or "000" for v in ids})
    cpos = {c: k for k, c in enumerate(counties)}
    regions = sorted({str(x) for x in P["cd"] if x is not None})
    rpos = {r: k for k, r in enumerate(regions)}
    ab = []
    for v in ids:
        x = feats.get("share_absentee_mail_2022", {}).get(v)
        ab.append(min(max(x, 0.0), 1.0) if x is not None else 0.27)
    U = {"ids": ids, "pos": {v: i for i, v in enumerate(ids)}, "L": L,
         "cty": [cpos[(props.get(v) or {}).get("county") or "000"] for v in ids], "counties": counties,
         "reg": [rpos.get(str(x), 0) for x in P["cd"]], "regions": regions,
         "Z": census_terms(feats, ids, L, 2026), "fnames": list(FEATURES), "ab": ab,
         "regs": [feats.get("registered_2024", {}).get(v) or 0 for v in ids]}
    ro = B.rolloff_arrays(ids, feats)
    B_ = [float(x or 0) for x in P["ballots"]]
    base = {"pre_run": pre_run, "frame": frame, "frame_sha": frame_sha, "U": U, "index": index, "ro": ro, "B": B_,
            "build": build, "map_v": geo_v, "built_in": round(time.time() - t0, 1)}
    _BASE.clear()
    _BASE[key] = base
    say(f"    night base from {pre_run}: {len(ids):,} precincts, {len(counties)} counties, built in {base['built_in']} s"
        + (f"; {off_map} precincts of the forecast are no longer on the ballot map (they keep no district)" if off_map else ""))
    return base


def prior_terms(frame):
    """Each partisan race's prior shift (log-odds added to every precinct's lean) and the spread of its own part, from
    the pre-election frame's environment, grids and parameters (forecast.py's model, linearised)."""
    from election.model import forecast as F
    env = frame["env"]
    mean, cov = env["mean"], env["cov"]
    sg = frame["state_grid"]
    P = frame["params"]

    def X(y):
        return F.inverse(sg, F.expit(y))

    def slope(y):
        return (X(y + 0.02) - X(y - 0.02)) / 0.04
    out = {}
    mG = mean[0]
    for e in frame["races"]:
        if e.get("kind") != "partisan" or e.get("status") != "pre":
            continue
        k = e.get("k")
        inc_dir = sum(c.get("inc", 0) for c in e["cands"] if c.get("p") == "D") - sum(c.get("inc", 0) for c in e["cands"] if c.get("p") == "R")
        if k is not None:
            y = mG + (mean[k] if k else 0.0)
            sl = slope(y)
            v_all = cov[0][0] + ((cov[k][k] + 2 * cov[0][k]) if k else 0.0)
            out[e["race"]] = {"m": X(y), "v_all": sl * sl * v_all, "own": k, "slope": sl}
        else:
            cls = e.get("class") or "mnleg"
            gap = P["gap"].get(cls, [0.0, 0.06])
            dsd = P["district_sd"].get(cls, 0.14)
            iota = P["inc"]
            sl = slope(mG)
            own = gap[1] ** 2 + (iota[1] * inc_dir) ** 2 + P["region_sd"] ** 2 + dsd ** 2
            out[e["race"]] = {"m": X(mG) + gap[0] + iota[0] * inc_dir, "v_all": sl * sl * cov[0][0] + own, "own": None, "v_own": own,
                              "slope": sl}
    return out


def anchor_of(frame, have):
    """The anchor race: the governor's race when it is counted, else the statewide race with the most precincts counted."""
    best = None
    for e in frame["races"]:
        if e.get("kind") != "partisan" or e.get("status") != "pre" or e.get("office_kind") not in ANCHOR_KINDS:
            continue
        p = [c.get("p") for c in e["cands"]]
        if p.count("D") != 1 or p.count("R") != 1:
            continue
        n = have.get(e["race"], 0)
        rank = (n > 0, e.get("office_kind") == "governor", n)
        if best is None or rank > best[0]:
            best = (rank, e["race"])
    return best[1] if best else None


def specs_for(base, terms, anchor_id, params):
    """Every race's spec for build_entries, from the pre-election frame."""
    frame = base["frame"]
    U = base["U"]
    P = frame["params"]
    pri = frame["priors"]
    ro, B_ = base["ro"], base["B"]
    env = frame["env"]
    cov = env["cov"]
    specs = []
    a_terms = terms.get(anchor_id) or {}
    for e in frame["races"]:
        st = e.get("status")
        cands = e["cands"]
        spec = {"race": e["race"], "seats": e.get("seats", 1), "cands": cands, "tested": e.get("tested"), "kind": "multi"}
        if st in ("unopposed", "no-candidates"):
            spec["status"] = st
            spec["note"] = "one name for each seat: unopposed, no forecast" if st == "unopposed" else "no candidate filed"
            specs.append(spec)
            continue
        if st != "pre":
            continue
        g = e.get("geo")
        members = base["index"].get(g, []) if g else []
        if e.get("kind") == "partisan":
            cls = e.get("class") or "mnleg"
            rc = ro["partisan"].get(cls) or ro["partisan"]["mnleg"]
        else:
            okind = e.get("office_kind")
            grp = e.get("group")
            rg = "county_commissioner" if okind in ("county_commissioner", "county_park") else (NP_GROUP_RO.get(grp) if NP_GROUP_RO.get(grp) in ro["np"] else "county_commissioner")
            rc = ro["np"].get(rg) or ro["np"]["county_commissioner"]
        spec["members"] = members
        spec["ev"] = [B_[i] * (1.0 - rc[i]) * w for i, w in members]
        spec["rot"] = bool(e.get("rot"))
        spec["first"] = e.get("first")
        p = [c.get("p") for c in cands]
        if e.get("kind") == "partisan" and p.count("D") == 1 and p.count("R") == 1:
            t = terms[e["race"]]
            spec.update(kind="partisan", iD=p.index("D"), iR=p.index("R"), m=t["m"], anchor=(e["race"] == anchor_id))
            minor = P["minor"]["statewide"] if e.get("k") is not None else P["minor"]["with_majors"]
            spec["oth_prior"] = min(sum(math.exp(minor[0] + minor[1] ** 2 / 2) for c in cands if c.get("p") not in ("D", "R")), 0.3) + \
                P["writein"]["partisan"]
            # the offset from the anchor race: its own part and the anchor's own part, less what they share
            if e["race"] == anchor_id:
                spec["v_s"] = t["v_all"]
                spec["vd"] = 0.0
            else:
                k, ka = t.get("own"), a_terms.get("own")
                if k is not None and ka is not None:
                    own = cov[k][k] + cov[ka][ka] - 2 * cov[k][ka] if k != ka else 0.0
                    spec["vd"] = t["slope"] ** 2 * own + 0.02 ** 2
                elif k is None and ka is not None:
                    spec["vd"] = t["v_own"] + a_terms["slope"] ** 2 * cov[ka][ka]
                else:
                    spec["vd"] = t.get("v_own", 0.02) + 0.02 ** 2
            spec["pg"] = "p"
        else:
            # several names (nonpartisan, or partisan without exactly one of each big party): log-share priors
            if e.get("kind") == "partisan":
                minor = P["minor"]["sole"] if (p.count("D") + p.count("R")) == 1 else P["minor"]["with_majors"]
                majors = [k for k, x in enumerate(p) if x in ("D", "R")]
                mm = math.exp(minor[0])
                spec["mu"] = [(math.log(max(1.0 - mm * (len(cands) - len(majors)), 0.05) / max(len(majors), 1)) if x in ("D", "R") else minor[0])
                              for x in p]
                spec["tau"] = max(minor[1], 0.2)
                spec["df"] = None
                spec["pg"] = "p"
                spec["wi_prior"] = P["writein"].get("partisan_sole", 0.01)
            else:
                np_ = P["np"]
                b_inc = np_["beta_inc"][0]
                eb = pri["endorse_beta"][0]
                spec["mu"] = [b_inc * c.get("inc", 0) + eb * c.get("end", 0.0) for c in cands]
                spec["tau"] = np_["tau"].get(e.get("group"), np_["tau"].get("county", 0.45))
                spec["df"] = np_.get("df")
                spec["pg"] = "np"
                spec["wi_prior"] = P["writein"].get("np", 0.006)
                spec["equal"] = len(set(spec["mu"])) == 1 and spec["first"] is None
        specs.append(spec)
    return specs


# ============================================================================================== the votes counted (results store)

def party_letter(p):
    """A party as printed on a results line: DFL (or Democratic), Republican, or another."""
    p = re.sub(r"[^A-Z]", "", str(p or "").upper())
    if p in ("D", "DFL", "DEM") or p.startswith("DEMOCRAT"):
        return "D"
    if p in ("R", "REP", "GOP") or p.startswith("REPUBLICAN"):
        return "R"
    return "O"


def observations(con, state, base, races):
    """{race: {"rep": {unit: [votes of each candidate (the frame's order) ..., other]}, "in", "all", "offmap", ...}} from
    the results store's newest good figures: a precinct counts once the store says it is in. Each line of the file is
    tied to a candidate on the frame's list by the name as filed (else as printed), else, in a partisan race, by party
    when one name of that party is on each side; write-ins and lines tied to nobody are "other"."""
    U = base["U"]
    pre = f"2026-{state.upper()}-"
    spec = {r["race"]: r for r in races}
    kinds = {}
    parent = {}
    for unit, kind, par in con.execute("SELECT unit_id, kind, parent FROM units WHERE state = ?", (state.upper(),)):
        kinds[unit] = kind
        parent[unit] = par
    choice = defaultdict(dict)
    for rid, ck, name, party, bname, wi in con.execute("SELECT race_id, choice_key, name, party, ballot_name, write_in FROM choices "
                                                       "WHERE race_id LIKE ?", (pre + "%",)):
        if rid in spec:
            choice[rid][ck] = (name, party, bname, wi)
    tie = {}
    unusable = []
    for rid, chs in choice.items():
        cands = spec[rid]["cands"]
        keys = {name_key(c["name"]): k for k, c in enumerate(cands)}
        m = {}
        for ck, (name, party, bname, wi) in chs.items():
            if wi:
                m[ck] = None
                continue
            k = keys.get(name_key(bname)) if bname else None
            if k is None:
                k = keys.get(name_key(name))
            m[ck] = k
        if spec[rid].get("kind") == "partisan" or any(c.get("p") in ("D", "R") for c in cands):
            for letter in ("D", "R"):
                fr = [k for k, c in enumerate(cands) if c.get("p") == letter]
                st = [ck for ck, (n_, party, b_, wi) in chs.items() if not wi and party_letter(party) == letter and m.get(ck) is None]
                if len(fr) == 1 and len(st) == 1 and fr[0] not in m.values():
                    m[st[0]] = fr[0]
        tie[rid] = m
    rep_in = {}
    for rid, unit, uin, uall in con.execute("SELECT race_id, unit_id, units_in, units_all FROM latest_reporting WHERE race_id LIKE ?",
                                            (pre + "%",)):
        if rid not in spec:
            continue
        if unit == "all":
            rep_in.setdefault(rid, {})["_all"] = (uin, uall)
        elif kinds.get(unit) == "precinct" and uin:
            rep_in.setdefault(rid, {})[unit] = True
    obs = {}
    off_units = 0
    for rid, unit, ck, v in con.execute("SELECT race_id, unit_id, choice_key, votes FROM latest_counts WHERE vote_type = 'total' AND race_id LIKE ?",
                                        (pre + "%",)):
        if rid not in spec or kinds.get(unit) != "precinct" or not rep_in.get(rid, {}).get(unit):
            continue
        n = len(spec[rid]["cands"])
        ob = obs.setdefault(rid, {"rep": {}, "offmap": [0] * n, "offmap_other": 0, "unmatched": 0, "named": 0})
        k = tie.get(rid, {}).get(ck)
        i = U["pos"].get(unit)
        if i is None:
            off_units += 1
            if k is None:
                ob["offmap_other"] += v
            else:
                ob["offmap"][k] += v
            continue
        row = ob["rep"].setdefault(i, [0] * (n + 1))
        if k is None:
            row[n] += v
            if not (choice.get(rid, {}).get(ck) or (None, None, None, 1))[3]:
                ob["unmatched"] += v
        else:
            row[k] += v
            ob["named"] += v
    for rid, ob in list(obs.items()):
        allp = rep_in.get(rid, {}).get("_all")
        if allp and allp[1]:
            ob["in"], ob["all"] = allp
        tot = ob["named"] + ob["unmatched"]
        if spec[rid].get("kind") != "partisan" and tot > 0 and ob["unmatched"] > 0.05 * tot:
            unusable.append(rid)                     # the names on the file are not the names on the list
            del obs[rid]
    return obs, {"unusable": unusable, "offmap_units": off_units, "parent": parent}


def snapshot_info(con, state):
    row = con.execute("SELECT snapshot_id, sha256, source_time, fetched_at FROM snapshots WHERE state = ? AND status = 'ok' "
                      "ORDER BY snapshot_id DESC LIMIT 1", (state.upper(),)).fetchone()
    return {"snapshot": row[0], "sha256": row[1], "at": row[2] or row[3]} if row else None


# ============================================================================================== the frame and the run

def public_words(pre_public, report, params, params_run):
    """What the forecasts page may say about a night run, in plain words (no file or program names). The pre-election
    words are kept (the page's format) and the night's are added."""
    out = dict(pre_public or {})
    s = report.get("surface") or {}
    pts = s.get("counted_gap_pts") or 0.0
    late_n = report.get("late_outstanding", 0)
    aw = report.get("anchor_words") or "the governor's race"
    census_on = (params.get("tau_b") or 0) >= 0.01
    out["night"] = ("On election night the model compares each precinct counted so far with what the forecast expected there, "
                    "learns how the vote has moved (statewide, in each congressional district and in each county"
                    + (", and with the Census figures of each place" if census_on else "") +
                    f"), and projects the precincts still out. Each race's own results so far set how far it runs ahead of or "
                    f"behind {aw}.")
    if not census_on:
        out["night_census"] = ("Census figures (education, age, density, a place's recent trend) were tried as explanations of how "
                               "the vote moves on the night; in the replays of 2022 and 2024 they did not help, so they carry next to "
                               "no weight.")
    out["night_now"] = (f"In the {s.get('units', 0):,} precincts counted so far in {aw}, the DFL's share of the two-party vote is "
                        f"{abs(pts):.1f} points {'above' if pts >= 0 else 'below'} what the forecast expected in those same precincts."
                        ) if s.get("units") else f"No precinct of {aw} has been counted yet."
    out["count_order"] = ("Precincts do not report in a random order, so the model never treats the first ones in as typical: it "
                          "compares each with its own expectation and lets each county and district move on its own; in a "
                          "nonpartisan race, the more the precincts counted differ in size from those still out, the wider "
                          "the range. "
                          + (f"Each county also adds its last absentee ballots later (those that reach it after 3 p.m. on Election Day); "
                             f"{late_n} counties' are not yet counted in, and the model holds an estimate of their number and a lean "
                             f"a few points either way of the county." if late_n else "Every county has added its last absentee ballots."))
    out["rolloff_night"] = ("Expected votes in each race come from each precinct's turnout so far and the share of voters who skipped "
                            "that kind of race in 2022, corrected by the precincts counted tonight.")
    out["position_night"] = ("Names are rotated from precinct to precinct; the model allows a small edge for the first name on the "
                             "ballot where the precincts still out printed the names in another order than those counted (the order is "
                             "rebuilt from the rotation rule, an estimate).")
    out["night_tested"] = (f"Sized by replays of 2022 and 2024 counted in four orders{(' (' + params.get('summary') + ')') if params.get('summary') else ''}."
                           if params_run else "The night's spreads are starting values; the replays that size them have not been run.")
    if params_run and params.get("lead_note"):
        out["early_lead"] = params["lead_note"]
    return json.loads(R.scrub(R.canonical(out)))


ANCHOR_WORDS = {"governor": "the governor's race", "us_senate": "the U.S. Senate race", "attorney_general": "the attorney general's race",
                "secretary_of_state": "the secretary of state's race", "state_auditor": "the state auditor's race"}


def tested_words(spec, fitted):
    """What a live row says about how its kind of race was tested (the pre-election words, and the night's replays)."""
    t = spec.get("tested") or ""
    if not fitted:
        return t
    if spec.get("kind") == "partisan":
        return t + "; on election night, sized by replays of the 2022 and 2024 counts in four counting orders"
    if t.startswith("untested"):
        return t + "; on election night, its spreads come from replays of county, court and soil and water races"
    return t + "; on election night, sized by replays of the 2022 and 2024 counts in four counting orders"


def build_live_frame(base, obs, info, params, params_run, as_of, late_done=frozenset(), say=say_default):
    frame_pre = base["frame"]
    have = {rid: len(ob["rep"]) for rid, ob in obs.items()}
    anchor_id = anchor_of(frame_pre, have)
    terms = prior_terms(frame_pre)
    prm = merge(params, {"pos_partisan": frame_pre["priors"]["pos_partisan"], "pos_nonpartisan": frame_pre["priors"]["pos_nonpartisan"]})
    specs = specs_for(base, terms, anchor_id, prm)
    for s in specs:
        if s.get("status") is None:
            s["tested"] = tested_words(s, bool(params_run))
    entries, shared, report, _fits = build_entries(base["U"], specs, obs, prm, late_done, anchor_id, say)
    akind = next((e.get("office_kind") for e in frame_pre["races"] if e["race"] == anchor_id), None)
    report.update(unusable=len(info.get("unusable") or []), offmap_units=info.get("offmap_units", 0),
                  anchor_words=ANCHOR_WORDS.get(akind, "the statewide race"))
    frame = {"v": 1, "state": STATE, "kind": "live", "method": LIVE_METHOD, "as_of": R.iso(as_of), "pre_run": base["pre_run"],
             "pre_frame": base["frame_sha"], "results": info.get("snapshot"), "params": prm, "params_run": params_run,
             "shared": shared, "races": entries, "report": report,
             "public": public_words(frame_pre.get("public"), report, prm, params_run)}
    return frame


def run(state="MN", now=None, db=None, rehearsal=False, say=say_default, model_db=MODEL_DB, draws=DRAWS, dry=False, params=None,
        params_run=None):
    """One live run for a state from its results so far, stored as a version (runs.py, kind "live"). Returns a summary."""
    from election import store
    from election.model import blindspots as B
    t0 = time.time()
    st = state.upper()
    if st != STATE:
        if st not in _SAID:
            _SAID.add(st)
            say(f"    {st}: the night's model reads Minnesota's precincts; other states keep their pre-election forecasts tonight")
        return {"skipped": "not Minnesota"}
    started = R.now_utc()
    as_of = now or started
    if isinstance(as_of, dt.datetime) and as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=dt.timezone.utc)
    pre_run, got = newest_pre(model_db, st)
    if not got:
        say(f"    {st}: no pre-election forecast on file; the night's model starts from one")
        return {"skipped": "no pre-election run"}
    frame_pre, frame_sha = got
    base = base_for(pre_run, frame_pre, frame_sha, say)
    db = db or store.DB
    if not os.path.exists(db):
        return {"skipped": "no results database"}
    con = sqlite3.connect(db)
    con.execute("PRAGMA busy_timeout = 30000")
    try:
        races_for_obs = [{"race": e["race"], "cands": e["cands"], "kind": e.get("kind")} for e in frame_pre["races"] if e.get("status") == "pre"]
        obs, info = observations(con, st, base, races_for_obs)
        snap = snapshot_info(con, st)
        info["snapshot"] = snap
        certified = {r for (r,) in con.execute("SELECT DISTINCT race_id FROM certified WHERE race_id LIKE ?", (f"2026-{st}-%",))}
        anchor_guess = anchor_of(frame_pre, {rid: len(ob["rep"]) for rid, ob in obs.items()})
        late_done = B.late_added(con, anchor_guess, base) if anchor_guess else frozenset()
    finally:
        con.close()
    if not obs:
        say(f"    {st}: no votes counted yet; the pre-election forecast stands")
        return {"skipped": "no votes counted"}
    if params is None:
        params, params_run = night_params(model_db, st)
    frame = build_live_frame(base, obs, info, params, params_run, as_of, late_done, say)
    for e in frame["races"]:
        if e["race"] in certified:
            e.clear()
    frame["races"] = [e for e in frame["races"] if e]
    for rid in sorted(certified):
        frame["races"].append({"race": rid, "kind": "multi", "status": "not-modelled", "seats": 1, "cands": [],
                               "note": "certified: the official count decides; no forecast after certification"})
    frame = json.loads(R.canonical(frame))
    inputs = [
        {"input": "results", "source": f"results store, snapshot {snap['snapshot']}" if snap else "results store", "sha256": (snap or {}).get("sha256"),
         "as_of": (snap or {}).get("at"), "kind": "official", "note": "the counts as the state's office posted them (read only)"},
        {"input": "pre-run", "source": f"run {pre_run}", "sha256": frame_sha, "as_of": frame_pre.get("as_of"), "kind": "derived",
         "note": "the pre-election forecast the night starts from"},
        {"input": "night-params", "source": f"replay run {params_run}" if params_run else "starting values (no replay on file)",
         "sha256": R.sha_text(R.canonical(frame["params"])), "as_of": None, "kind": "derived" if params_run else "prior",
         "note": frame["params"].get("source")},
        {"input": "features", "source": f"features (data build {base['build']})", "sha256": None, "as_of": None, "kind": "derived",
         "note": "the Census terms, absentee shares, registration and roll-off of each precinct"},
    ]
    con = R.connect(model_db)
    try:
        run_id = R.new_run_id(con, "live", st, started)
        seed = R.seed_of(run_id)
        t1 = time.time()
        out = S.simulate(frame, seed, draws)
        sim_s = time.time() - t1
        if dry:
            say(f"    dry run {run_id}: {len(out['races'])} races simulated in {sim_s:.1f} s (not stored)")
            return {"run": run_id, "out": out, "frame": frame, "seconds": round(time.time() - t0, 1), "simulate_s": round(sim_s, 1)}
        with con:
            res = R.record_run(con, run=run_id, state=st, kind="live", method=LIVE_METHOD, seed=seed, draws=draws, started=started,
                               as_of=as_of, frame=frame, outputs=out, inputs=inputs, rehearsal=rehearsal,
                               note=f"election-night forecast from {(snap or {}).get('snapshot')}; starts from {pre_run}; "
                                    f"parameters from {params_run or 'starting values'}")
    finally:
        con.close()
    secs = round(time.time() - t0, 1)
    say(f"    live run {run_id}: {res['races']} races, {res['written']} with new rows; simulated in {sim_s:.1f} s, {secs} s in all")
    return {"run": run_id, **res, "seconds": secs, "simulate_s": round(sim_s, 1), "report": frame["report"]}


# ============================================================================================== a published snapshot as results

def snapshot_reading(folder, code="MN"):
    """A published snapshot folder (the state's file and every county's two precinct files) read back into the results
    store's reading, so a model can be run on figures already published (the practice figures). Reads only those files."""
    from election import store
    lc = code.lower()
    doc = store.expand_page(json.load(open(os.path.join(folder, f"{lc}.json"), encoding="utf-8")))
    lines = {rid: len(e.get("ch") or []) for rid, e in doc["r"].items()}
    rows = defaultdict(dict)
    cdir = os.path.join(folder, lc, "c")
    units = {}
    for name in sorted(os.listdir(cdir)) if os.path.isdir(cdir) else []:
        if not name.endswith(".json"):
            continue
        cd = json.load(open(os.path.join(cdir, name), encoding="utf-8"))
        for u in cd.get("u") or []:
            units[u] = cd["county"]
        for rid, got in store.county_rows(cd, lines).items():
            rows[rid].update(got)
    contests = []
    for rid, e in sorted(doc["r"].items()):
        chs = e.get("ch") or []
        choices = [{"key": c[0], "name": c[1], "party": c[2], "write_in": bool(c[3]), "ballot_name": c[4], "order": k + 1}
                   for k, c in enumerate(chs)]
        got = rows.get(rid, {})
        us = sorted(got)
        cont = {"race_id": rid, "key": rid, "office": rid, "level": None, "district": None, "seats": 1, "unit_kind": "precinct",
                "units_all": (e.get("p") or [None, None])[1], "choices": choices,
                "units": [{"id": u, "kind": "precinct", "name": None, "parent": units.get(u), "map_id": u} for u in us] +
                         [{"id": "all", "kind": "race", "name": "the whole contest", "parent": None, "map_id": None}],
                "rows": [{"unit": u, "choice": chs[k][0], "type": "total", "votes": int(v)} for u in us for k, v in enumerate(got[u])],
                "reporting": [{"unit": u, "in": 1, "all": 1} for u in us] +
                             [{"unit": "all", "in": (e.get("p") or [0, 0])[0], "all": (e.get("p") or [0, 0])[1]}],
                "stated": [], "controls": []}
        contests.append(cont)
    return {"state": code.upper(), "feed": f"{lc}-snapshot", "source_time": doc.get("at"), "source_version": None, "contests": contests,
            "unmatched": [], "problems": []}


def load_snapshot(folder, scratch_db, code="MN", say=say_default, keep=None):
    """The snapshot folder into a scratch results database (made new). keep: an optional set of precinct ids; the others
    are left out (an earlier moment of the same night). Returns the snapshot id."""
    from election import store
    reading = snapshot_reading(folder, code)
    if keep is not None:
        for c in reading["contests"]:
            c["rows"] = [r for r in c["rows"] if r["unit"] in keep]
            ins = [r for r in c["reporting"] if r["unit"] != "all" and r["unit"] in keep]
            c["reporting"] = ins + [{"unit": "all", "in": len(ins), "all": next((r["all"] for r in c["reporting"] if r["unit"] == "all"), None)}]
    con = store.connect(scratch_db)
    try:
        store.ensure_election(con, code.upper(), certifying_body="(scratch)")
        store.ensure_feed(con, code.upper(), reading["feed"], "snapshot", "a published snapshot folder", "test")
        sha = store.sha256_bytes(json.dumps(reading, sort_keys=True).encode("utf-8"))
        sid, status = store.begin_snapshot(con, code.upper(), reading["feed"], sha, raw_path=folder, source_time=reading["source_time"])
        if status != "same":
            status, checks = store.record(con, sid, reading)
            bad = [d for n, p, d in checks if not p]
            if bad:
                say("    snapshot checks: " + "; ".join(bad)[:300])
        say(f"    scratch results: snapshot {sid} {status} ({sum(len(c['rows']) for c in reading['contests']):,} numbers)")
        return sid
    finally:
        con.close()


# ============================================================================================== self-test

def selftest(say=say_default):
    """Made-up precincts: the surface finds a known shift, pulled toward none while few are in; a race's offset; the
    entries' arithmetic; a frame through simulate.py twice, the same."""
    import random
    ok = True

    def check(what, cond):
        nonlocal ok
        ok &= bool(cond)
        say(f"    {'ok ' if cond else 'BAD'} {what}")
    rng = random.Random(5)
    n = 400
    U = {"ids": [f"p{i}" for i in range(n)], "L": [rng.gauss(0, 0.5) for _ in range(n)], "cty": [i % 8 for i in range(n)],
         "counties": [f"{c:03d}" for c in range(8)], "reg": [i % 2 for i in range(n)], "regions": ["1", "2"],
         "Z": [[rng.gauss(0, 1) for _ in FEATURES] for _ in range(n)], "fnames": list(FEATURES), "ab": [0.3] * n, "regs": [1000] * n}
    prm = json.loads(json.dumps(DEFAULT_NIGHT))
    true_shift = 0.15
    votes = {}
    for i in range(n):
        p = expit(U["L"][i] + true_shift + rng.gauss(0, 0.1))
        tot = 800
        d = int(tot * p)
        votes[i] = (d, tot - d)
    fit_all = fit_surface(U, [(i, *votes[i]) for i in range(n)], 0.0, 0.03, prm)
    check(f"the statewide shift is found ({fit_all['g'][0]:.3f} against {true_shift})", abs(fit_all["g"][0] - true_shift) < 0.03)
    fit_few = fit_surface(U, [(i, *votes[i]) for i in range(3)], 0.0, 0.03, prm)
    check("with three precincts the shift is pulled toward none", abs(fit_few["g"][0]) < abs(fit_all["g"][0]))
    check("and is less certain", fit_few["cov"][0][0] > fit_all["cov"][0][0])
    # a two-race night: the anchor and a district race 0.2 behind it
    mem = [(i, 1.0) for i in range(n)]
    dmem = [(i, 1.0) for i in range(0, n, 4)]
    cands = [{"key": "d", "name": "D", "p": "D"}, {"key": "r", "name": "R", "p": "R"}]
    specs = [{"race": "A", "kind": "partisan", "seats": 1, "cands": cands, "members": mem, "ev": [800.0] * n, "iD": 0, "iR": 1, "m": 0.0,
              "v_s": 0.03, "vd": 0.0, "anchor": True, "tested": "t"},
             {"race": "B", "kind": "partisan", "seats": 1, "cands": cands, "members": dmem, "ev": [700.0] * len(dmem), "iD": 0, "iR": 1,
              "m": 0.0, "vd": 0.02, "tested": "t"},
             {"race": "N", "kind": "multi", "seats": 1, "cands": [{"key": "a", "name": "A"}, {"key": "b", "name": "B"}], "members": dmem,
              "ev": [600.0] * len(dmem), "mu": [0.0, 0.0], "tau": 0.4, "df": 6, "tested": "t"}]
    reported = set(range(0, n, 2))
    obs = {"A": {"rep": {i: [votes[i][0], votes[i][1], 0] for i in reported}},
           "B": {"rep": {}}, "N": {"rep": {}}}
    for i, _w in dmem:
        if i in reported:
            pa = votes[i][0] / 800
            pb = expit(logit(pa) - 0.2)
            obs["B"]["rep"][i] = [int(700 * pb), 700 - int(700 * pb), 0]
            obs["N"]["rep"][i] = [400, 200, 0]
    entries, shared, report, fits = build_entries(U, specs, obs, prm, frozenset(), "A", say=lambda *a: None)
    eb = next(e for e in entries if e["race"] == "B")
    check(f"a district race's offset from the anchor is learned ({eb['offset'][0]:.3f} against -0.2)", abs(eb["offset"][0] + 0.2) < 0.05)
    en = next(e for e in entries if e["race"] == "N")
    check("a nonpartisan race moves toward its counted shares", en["mu"][0] > en["mu"][1])
    frame = json.loads(R.canonical({"method": LIVE_METHOD, "params": prm, "shared": shared, "races": entries}))
    a = S.simulate(frame, 3, 400)
    b = S.simulate(frame, 3, 400)
    check("the same frame and seed give the same numbers", R.canonical(a) == R.canonical(b))
    ra = next(r for r in a["races"] if r["race"] == "A")
    F_, sd = predictive_two_party(next(e for e in entries if e["race"] == "A"), shared)
    true_final = sum(votes[i][0] for i in range(n)) / sum(sum(votes[i]) for i in range(n))
    check(f"the anchor's final share is near the truth ({F_:.4f} against {true_final:.4f}, sd {sd:.4f})", abs(F_ - true_final) < 4 * sd + 0.002)
    check("half the precincts in: the share counted is about half", 0.35 < ra["share_counted"] < 0.65)
    check("no chance is 0 or 1", all(0 < c["chance"] < 1 for r in a["races"] for c in r["cands"]))
    return ok


# ============================================================================================== the role's checks, on scratch copies

def check(snapshot, scratch, draws=DRAWS, say=say_default):
    """ARCHITECTURE.md 5.3's checks for the night's model, on copies in a scratch folder of one's own (the real databases
    are only read): two moments of a replayed night (part of the snapshot's precincts, then all of them) read into a
    scratch results database and the model run after each into a scratch copy of the model database, each under 30
    seconds; every stored pre-election and night run redone exactly; no 0 or 100 anywhere; nothing for an unopposed
    race; the replays' calibration on file. Returns True when every check holds."""
    import random
    os.makedirs(scratch, exist_ok=True)
    rdb = os.path.join(scratch, "check_results.sqlite")
    mdb = os.path.join(scratch, "check_model.sqlite")
    for p in (rdb, rdb + "-wal", rdb + "-shm", mdb):
        if os.path.exists(p):
            os.remove(p)
    shutil.copyfile(MODEL_DB, mdb)
    _BASE.clear()
    reading = snapshot_reading(snapshot, STATE)
    units = sorted({r["unit"] for c in reading["contests"] for r in c["rows"]})
    early = {u for u in units if random.Random(f"check-{u}").random() < 0.4}
    ok = True
    secs = []
    for label, keep in (("an earlier moment (about 40 percent of the snapshot's precincts)", early), ("the whole snapshot", None)):
        load_snapshot(snapshot, rdb, STATE, say=lambda *a: None, keep=keep)
        t = time.time()
        res = run(STATE, db=rdb, model_db=mdb, draws=draws, say=lambda *a: None)
        secs.append(time.time() - t)
        good = bool(res.get("run")) and secs[-1] < 30
        ok &= good
        say(f"    {'ok ' if good else 'BAD'} live run on {label}: {secs[-1]:.1f} s (limit 30), {res.get('races')} races, "
            f"{res.get('written')} new rows, {draws:,} draws")
        time.sleep(1.1)
    for r in R.list_runs(mdb, STATE):
        if R.redoable(r["kind"], r["method"]):
            res = R.redo(r["run"], mdb, say=lambda *a: None)
            ok &= res["exact"]
            say(f"    {'ok ' if res['exact'] else 'BAD'} redo {r['run']} ({r['kind']}): {res.get('compared')} races compared, "
                f"{res.get('n_differ')} differ")
    e = R.check_no_extremes(STATE, mdb)
    u = R.check_unopposed(STATE, mdb)
    ok &= e["holds"] and u["holds"]
    say(f"    {'ok ' if e['holds'] else 'BAD'} no 0 or 100: {e['stored_out_of_range']} stored chances out of range, "
        f"{e['page_out_of_range']} in the page files; forecasts file {e['page_bytes'] / 1e3:,.0f} KB (budget 300)")
    say(f"    {'ok ' if u['holds'] else 'BAD'} no forecast for an unopposed race: {u['unopposed_races']:,} unopposed, "
        f"{u['with_a_chance_stored']} with a chance stored, {u['in_the_page']} in the page")
    prm, prun = night_params(MODEL_DB)
    good = bool(prun)
    ok &= good
    say(f"    {'ok ' if good else 'BAD'} the count-order replays: " + (f"run {prun}; {prm.get('summary')}" if prun else
                                                                       "no replay calibration on file (python -m election.model.blindspots --calibrate)"))
    return ok


# ============================================================================================== command line

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--state", default="mn")
    ap.add_argument("--db", help="the results database (default: the night's)")
    ap.add_argument("--model-db", default=MODEL_DB)
    ap.add_argument("--draws", type=int, default=DRAWS)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--rehearsal", action="store_true")
    ap.add_argument("--snapshot", help="a published snapshot folder to run on (read into a scratch results database)")
    ap.add_argument("--scratch", help="a folder of one's own for the scratch databases (with --snapshot)")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--check", action="store_true", help="the role's checks on scratch copies (with --snapshot and --scratch)")
    a = ap.parse_args(argv)
    if a.selftest:
        sys.exit(0 if selftest() else 1)
    if a.check:
        if not (a.snapshot and a.scratch):
            sys.exit("    --check needs --snapshot <a published snapshot folder> and --scratch <a folder of your own>")
        sys.exit(0 if check(a.snapshot, a.scratch, a.draws) else 1)
    if a.snapshot:
        if not a.scratch:
            sys.exit("    --snapshot needs --scratch <a folder of your own>")
        os.makedirs(a.scratch, exist_ok=True)
        rdb = os.path.join(a.scratch, "results_scratch.sqlite")
        for p in (rdb, rdb + "-wal", rdb + "-shm"):
            if os.path.exists(p):
                os.remove(p)
        load_snapshot(a.snapshot, rdb, a.state.upper())
        mdb = a.model_db
        if os.path.abspath(mdb) == os.path.abspath(MODEL_DB):
            mdb = os.path.join(a.scratch, "model_scratch.sqlite")
            if not os.path.exists(mdb):
                shutil.copyfile(MODEL_DB, mdb)
        res = run(a.state, db=rdb, model_db=mdb, draws=a.draws, dry=a.dry_run, rehearsal=True)
        print(json.dumps({k: v for k, v in res.items() if k not in ("out", "frame")}, indent=1)[:3000])
        return
    res = run(a.state, db=a.db, model_db=a.model_db, draws=a.draws, dry=a.dry_run, rehearsal=a.rehearsal)
    print(json.dumps({k: v for k, v in res.items() if k not in ("out", "frame")}, indent=1)[:3000])


if __name__ == "__main__":
    main()
