"""election/model/simulate_us.py - the night's simulation for every state but Minnesota (ARCHITECTURE.md 4.1 "On the
night", 4.2). Analysis, never a result.

    simulate(frame, seed, draws) -> {"races": [race output, ...]}         runs.SIMULATORS["live/us"]
    race_in_sha(entry, frame) -> the digest of what one race's numbers depend on
    python -m election.model.simulate_us --selftest                       the arithmetic on made-up races; reads no file

A PURE FUNCTION of (frame, seed, draws). night_us.py builds the frame (every number this file reads), runs.py keeps it
whole with this file's own text, and the seed comes from the run id. This file imports nothing from the kit but
runs.py, so a stored run is redone exactly with the code it was made with.

WHAT ONE DRAW IS (one possible end of the count), race by race
  Two-party races ("partisan": one Democrat and one Republican on the list):
    the votes still out split between the two big parties at the model's projected share s0, moved by one draw of
      its uncertainty (the state's swing, the race's own offset, each county's own swing, the gap between the ballots
      counted first and those counted last, and the noise of the precincts still out, already added up into "ve");
    the votes still out number R, give or take Rsd (on the log scale), from the expected turnout;
    candidates outside the two big parties and write-ins take their expected share of what is left.
  Races of several names ("multi": one big party against others, or none): each name's share of the votes still out
    follows exp(mu + error), the error drawn once per name.
  The decision rule: the most votes wins (plurality, top two); where the law asks for more than half ("majority"), the
  chance shown is still of finishing first in the count, and "ro" is the chance that no candidate passes half (a runoff,
  or the legislature decides); ranked choice ("rcv"): first choices, the later choices taken to split like the two big
  parties' own votes, so the chance is of leading the two-party count.
  A chance is (wins + 0.5) / (draws + 1): never 0 or 1.
  The likely margin of the top two ("mg"): the favourite's share less the runner-up's, draw by draw (median, 80 and 95
  percent ranges), the two named by their chances.
"""

import hashlib
import json
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from election.model import runs as R  # noqa: E402

SIM_VERSION = "sim-us-1.0"


# ============================================================================================== small helpers (own copies)

def logit(p):
    p = min(max(p, 1e-9), 1 - 1e-9)
    return math.log(p / (1 - p))


def expit(x):
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    e = math.exp(x)
    return e / (1.0 + e)


def quantiles_sorted(s, qs):
    n = len(s)
    out = []
    for q in qs:
        pos = q * (n - 1)
        i = int(math.floor(pos))
        f = pos - i
        out.append(s[i] if i + 1 >= n else s[i] * (1 - f) + s[i + 1] * f)
    return out


def rng_for(seed, *parts):
    h = hashlib.sha256(":".join([str(seed), *map(str, parts)]).encode("utf-8")).hexdigest()
    return random.Random(int(h[:16], 16))


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


# ============================================================================================== one race

def _summarise(e, shares, wins, votes, draws, no_majority=None):
    n = len(e["cands"])
    seats = e.get("seats") or 1
    cands = []
    for k, c in enumerate(e["cands"]):
        s = sorted(shares[k])
        q = quantiles_sorted(s, (0.5, 0.1, 0.9, 0.025, 0.975))
        cands.append({"key": c["key"], "name": c["name"], "chance": R.stored_chance(wins[k], draws), "median": q[0], "lo80": q[1],
                      "hi80": q[2], "lo95": q[3], "hi95": q[4]})
    out = {"race": e["race"], "status": e["status"], "seats": seats, "equal": False, "units_in": e.get("units_in", 0),
           "units_all": e.get("units_all"), "ballots": int(e.get("counted") or 0), "tested": e.get("tested"), "cands": cands}
    vs = sorted(votes)
    q = quantiles_sorted(vs, (0.1, 0.5, 0.9))
    out["exp"] = [q[0], q[1], q[2]]
    out["share_counted"] = round(min(1.0, (e.get("counted") or 0) / q[1]), 6) if q[1] > 0 else 0.0
    if seats == 1:
        mg = R.margin_of(e["cands"], shares, wins)
        if mg:
            out["mg"] = mg
    if no_majority is not None:
        out["ro"] = R.stored_chance(no_majority, draws)
    if e.get("note"):
        out["note"] = e["note"]
    return out


def _partisan(e, rng, draws):
    cands = e["cands"]
    n = len(cands)
    C = [float(x) for x in e["C"]]
    cwi = float(e.get("Cwi") or 0)
    iD, iR = e["iD"], e["iR"]
    minors = e.get("minors") or []
    mix = e.get("mix") or [1.0]
    R0, Rsd = float(e.get("R") or 0), float(e.get("Rsd") or 0)
    ls0, kap = logit(e.get("s0", 0.5)), float(e.get("kap", 1.0))
    ve_sd = math.sqrt(max(float(e.get("ve") or 0), 0.0))
    oth, oth_sd = float(e.get("oth") or 0), float(e.get("oth_sd") or 0)
    rule = e.get("rule") or "plurality"
    shares = [[] for _ in range(n)]
    wins = [0] * n
    votes = []
    nomaj = 0
    for _d in range(draws):
        delta = rng.gauss(0.0, ve_sd) if ve_sd > 0 else 0.0
        srem = expit(ls0 + kap * delta)
        Rd = R0 * math.exp(rng.gauss(0.0, Rsd)) if R0 > 0 else 0.0
        o = min(0.9, oth * math.exp(rng.gauss(0.0, oth_sd))) if oth > 0 else 0.0
        v = C[:]
        two = Rd * (1.0 - o)
        v[iD] += two * srem
        v[iR] += two * (1.0 - srem)
        rest = Rd * o
        for m, k in enumerate(minors):
            v[k] += rest * mix[m]
        tot = sum(v) + cwi + rest * mix[-1]
        if rule == "rcv":
            # first choices are counted; the later choices are taken to split like the two big parties' own votes, so
            # the race goes to whichever of the two leads the two-party count
            best = iD if v[iD] >= v[iR] else iR
        else:
            best = 0
            for k in range(1, n):
                if v[k] > v[best]:
                    best = k
        wins[best] += 1
        inv = 1.0 / tot if tot > 0 else 0.0
        for k in range(n):
            shares[k].append(v[k] * inv)
        if rule == "majority" and v[best] * inv <= 0.5:
            nomaj += 1
        votes.append(tot)
    return _summarise(e, shares, wins, votes, draws, nomaj if rule == "majority" else None)


def _multi(e, rng, draws):
    cands = e["cands"]
    n = len(cands)
    C = [float(x) for x in e["C"]]
    cwi = float(e.get("Cwi") or 0)
    R0, Rsd = float(e.get("R") or 0), float(e.get("Rsd") or 0)
    mu = [float(x) for x in e["mu"]]
    sd_ = e.get("sd") or 0
    sds = [float(x) for x in sd_] if isinstance(sd_, list) else [float(sd_)] * n
    wi = float(e.get("wi") or 0)
    rule = e.get("rule") or "plurality"
    shares = [[] for _ in range(n)]
    wins = [0] * n
    votes = []
    nomaj = 0
    for _d in range(draws):
        lw = [mu[k] + (rng.gauss(0.0, sds[k]) if sds[k] > 0 else 0.0) for k in range(n)]
        top = max(lw)
        ex = [math.exp(x - top) for x in lw]
        t = sum(ex)
        Rd = R0 * math.exp(rng.gauss(0.0, Rsd)) if R0 > 0 else 0.0
        named = Rd * (1.0 - wi) / t
        v = [C[k] + named * ex[k] for k in range(n)]
        tot = sum(v) + cwi + Rd * wi
        best = 0
        for k in range(1, n):
            if v[k] > v[best]:
                best = k
        wins[best] += 1
        inv = 1.0 / tot if tot > 0 else 0.0
        for k in range(n):
            shares[k].append(v[k] * inv)
        if rule == "majority" and v[best] * inv <= 0.5:
            nomaj += 1
        votes.append(tot)
    return _summarise(e, shares, wins, votes, draws, nomaj if rule == "majority" else None)


# ============================================================================================== the run

def race_in_sha(entry, frame):
    """The digest of everything one race's numbers depend on: its own entry, the method, the simulation's version and
    the night's parameters."""
    keep = {"race": entry, "method": frame.get("method"), "sim": SIM_VERSION, "params": frame.get("params")}
    return R.sha_text(canonical(keep))


def simulate(frame, seed, draws):
    """Every race's numbers from a frame: {"races": [race output]} (runs.record_run's shape). The same frame, seed and
    draws always give the same numbers (runs.redo checks it)."""
    out = []
    for e in frame["races"]:
        st = e.get("status")
        if st in ("unopposed", "no-candidates", "not-modelled"):
            res = {"race": e["race"], "status": st, "seats": e.get("seats") or 1,
                   "cands": [{"key": c["key"], "name": c["name"]} for c in e["cands"]], "note": e.get("note")}
        else:
            rng = rng_for(seed, e["race"])
            res = _partisan(e, rng, draws) if e["kind"] == "partisan" else _multi(e, rng, draws)
        res["in_sha"] = race_in_sha(e, frame)
        out.append(res)
    return {"races": out}


# ============================================================================================== self-test

def selftest(say=print):
    ok = True

    def check(what, cond):
        nonlocal ok
        ok &= bool(cond)
        say(f"    {'ok ' if cond else 'BAD'} {what}")
    cands = [{"key": "d", "name": "D", "p": "D"}, {"key": "r", "name": "R", "p": "R"}, {"key": "g", "name": "G", "p": "O"}]
    close = {"race": "P1", "kind": "partisan", "status": "counting", "seats": 1, "units_in": 5, "units_all": 10, "counted": 1000,
             "cands": cands, "iD": 0, "iR": 1, "minors": [2], "mix": [0.8, 0.2], "C": [500, 480, 20], "Cwi": 0, "R": 1000, "Rsd": 0.05,
             "s0": 0.5, "kap": 0.95, "ve": 0.01, "oth": 0.02, "oth_sd": 0.2, "rule": "plurality"}
    lead = dict(close, race="P2", C=[700, 280, 20], s0=0.6)
    maj = dict(close, race="P3", rule="majority", C=[470, 470, 60], oth=0.06)
    rcv = dict(close, race="P4", rule="rcv", C=[450, 420, 130], oth=0.13)
    multi = {"race": "M1", "kind": "multi", "status": "counting", "seats": 1, "units_in": 1, "units_all": 4, "counted": 200,
             "cands": [{"key": "a", "name": "A", "p": "R"}, {"key": "b", "name": "B", "p": "O"}], "C": [150, 48], "Cwi": 2,
             "R": 600, "Rsd": 0.1, "mu": [0.9, -0.9], "sd": [0.2, 0.3], "wi": 0.006, "rule": "plurality"}
    pre = dict(close, race="P5", status="pre", C=[0, 0, 0], counted=0, units_in=0, R=2000, s0=0.53, ve=0.03)
    unopp = {"race": "U1", "kind": "multi", "status": "unopposed", "seats": 1, "cands": [{"key": "z", "name": "Z"}]}
    frame = json.loads(canonical({"method": "us-live-test", "params": {}, "races": [close, lead, maj, rcv, multi, pre, unopp]}))
    a = simulate(frame, 11, 800)
    b = simulate(frame, 11, 800)
    check("the same frame and seed give the same numbers", canonical(a) == canonical(b))
    rs = {r["race"]: r for r in a["races"]}
    check("a race ahead in the count and in the votes still out favours the leader", rs["P2"]["cands"][0]["chance"] > 0.95)
    check("a close count stays uncertain", 0.2 < rs["P1"]["cands"][0]["chance"] < 0.8)
    check("no chance is 0 or 1", all(0 < c["chance"] < 1 for r in a["races"] if r["status"] != "unopposed" for c in r["cands"]))
    check("an unopposed race carries no chance and no margin", [c.get("chance") for c in rs["U1"]["cands"]] == [None] and "mg" not in rs["U1"])
    check("a majority rule gives the chance of no majority", 0 < rs["P3"].get("ro", 0) < 1 and "ro" not in rs["P1"])
    check("ranked choice: the chance is of leading the two-party count", rs["P4"]["cands"][0]["chance"] > rs["P4"]["cands"][1]["chance"])
    mg = rs["P2"]["mg"]
    check("the margin is the favourite's lead over the runner-up", mg["a"] == "d" and mg["b"] == "r" and mg["q"][0] > 0.3 and mg["q"][1] <= mg["q"][0] <= mg["q"][2])
    check("a close race's margin range crosses zero", rs["P1"]["mg"]["q"][1] < 0 < rs["P1"]["mg"]["q"][2])
    check("80 percent ranges sit inside 95 percent ranges", all(c["lo95"] <= c["lo80"] <= c["median"] <= c["hi80"] <= c["hi95"]
                                                                 for r in a["races"] if r["status"] != "unopposed" for c in r["cands"]))
    check("before any vote, the share counted is 0", rs["P5"]["share_counted"] == 0.0)
    check("a race's inputs digest ignores the seed", simulate(frame, 12, 50)["races"][0]["in_sha"] == a["races"][0]["in_sha"])
    return ok


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        sys.exit(0 if selftest() else 1)
    ap.print_help()


if __name__ == "__main__":
    main()
