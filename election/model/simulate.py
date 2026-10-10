"""election/model/simulate.py - the night's simulation (ARCHITECTURE.md 4.1 "On the night"; model.md 3.3 and 3.4). Owned
by N17. Analysis, never a result.

    simulate(frame, seed, draws) -> {"races": [race output, ...]}         runs.SIMULATORS["live"] and ["replay"]
    race_in_sha(entry, frame) -> the digest of what one race's numbers depend on
    python -m election.model.simulate --selftest                          the arithmetic on made-up races; reads no file

A PURE FUNCTION of (frame, seed, draws). live_model.py builds the frame (every number this file reads), runs.py keeps it
whole, and the seed comes from the run id; nothing else is read. runs.py also keeps this file's own text with every run
and redoes an old run with the text it was made with, so this file imports nothing from the kit but runs.py: any helper
it needs is written here.

WHAT ONE DRAW IS (one possible end of the count)
  Shared by every race in a draw:
    the swing surface's error: the statewide shift, the regional shifts and the Census terms (one Gaussian draw of the
      "g" block, by its Cholesky factor), and one standard normal per county for the county shifts of the counties
      with precincts still out (each race carries its own coefficient on each county, already scaled);
    the late absentee batches (the count-order blind spot): one statewide factor on their size, one factor and one lean
      offset per county whose batch is still outstanding;
    the first-line edges (the ballot-position blind spot): one partisan and one nonpartisan size, from their priors.
  Partisan races ("partisan": one DFL and one Republican candidate):
    the remaining precincts' two-party share moves from its point estimate s0 by the shared shift and the race's own
      error (its offset from the governor's race and the precincts' own noise, "ve"), through the remaining precincts'
      own curve (kap); the remaining votes are R, give or take Rsd (log); minor candidates and write-ins take their
      expected share of what is left; each county's late batch votes like the county plus its lean offset; the
      first-line edge moves the remaining precincts by the difference between their rotation and the counted ones'.
  Races of several names ("multi": nonpartisan races, and partisan races without exactly one candidate of each big
  party): each name's share of the remaining vote follows exp(mu + error), the error drawn once per name (with a
  race-level scale mixture where the backtests chose heavier tails), plus the first-line edge; the late batch votes
  like the remaining precincts.
  The winners are the most votes (the top `seats` where several are elected). A chance is (wins + 0.5) / (draws + 1),
  never 0 or 1; a race with nothing to tell its names apart ("equal") gets exactly equal chances.
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

SIM_VERSION = "sim-1.0"


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


def cholesky(A):
    n = len(A)
    L = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1):
            s = A[i][j] - sum(L[i][k] * L[j][k] for k in range(j))
            if i == j:
                L[i][j] = math.sqrt(max(s, 1e-12))
            else:
                L[i][j] = s / L[j][j]
    return L


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


# ============================================================================================== the shared draws

def shared_draws(frame, seed, draws):
    """[(dg, zc, late_size, late_lean, g_partisan, g_nonpartisan)] for every draw, in a fixed order from the seed."""
    sh = frame["shared"]
    rng = rng_for(seed, "shared")
    cov = (sh.get("g") or {}).get("cov") or []
    Lg = cholesky(cov) if cov else []
    k = len(Lg)
    nc = len(sh.get("counties") or [])
    late = sh.get("late") or {}
    nl = len(late.get("counties") or [])
    sd_state, sd_county, sd_lean = late.get("sdlog", 0.0), late.get("county_sdlog", 0.0), late.get("lean_sd", 0.0)
    pp = (sh.get("pos") or {}).get("partisan") or [0.0, 0.0]
    pn = (sh.get("pos") or {}).get("nonpartisan") or [0.0, 0.0]
    out = []
    for _d in range(draws):
        zg = [rng.gauss(0.0, 1.0) for _ in range(k)]
        dg = [sum(Lg[i][j] * zg[j] for j in range(i + 1)) for i in range(k)]
        zc = [rng.gauss(0.0, 1.0) for _ in range(nc)]
        lam = math.exp(rng.gauss(0.0, sd_state)) if nl else 1.0
        lf = [lam * math.exp(rng.gauss(0.0, sd_county)) for _ in range(nl)]
        lo = [rng.gauss(0.0, sd_lean) for _ in range(nl)]
        gp = rng.uniform(pp[0], pp[1])
        gn = rng.uniform(pn[0], pn[1])
        out.append((dg, zc, lf, lo, gp, gn))
    return out


# ============================================================================================== one race

def _summarise(e, shares, wins, votes, draws, equal=False):
    n = len(e["cands"])
    seats = e.get("seats") or 1
    pooled = sorted(x for k in range(n) for x in shares[k]) if equal else None
    cands = []
    for k, c in enumerate(e["cands"]):
        s = pooled if equal else sorted(shares[k])
        q = quantiles_sorted(s, (0.5, 0.1, 0.9, 0.025, 0.975))
        chance = (seats / n) if equal else R.stored_chance(wins[k], draws)
        cands.append({"key": c["key"], "name": c["name"], "chance": chance, "median": q[0], "lo80": q[1], "hi80": q[2],
                      "lo95": q[3], "hi95": q[4]})
    out = {"race": e["race"], "status": e["status"], "seats": seats, "equal": bool(equal), "units_in": e.get("units_in", 0),
           "units_all": e.get("units_all"), "ballots": int(e.get("counted") or 0), "tested": e.get("tested"), "cands": cands}
    if votes:
        vs = sorted(votes)
        q = quantiles_sorted(vs, (0.1, 0.5, 0.9))
        out["exp"] = [q[0], q[1], q[2]]
        out["share_counted"] = round(min(1.0, (e.get("counted") or 0) / q[1]), 6) if q[1] > 0 else 0.0
    else:
        out["share_counted"] = 0.0
    if e.get("note"):
        out["note"] = e["note"]
    return out


def _partisan(e, shared, rng, draws):
    cands = e["cands"]
    n = len(cands)
    C = [float(x) for x in e["C"]]
    cwi = float(e.get("Cwi") or 0)
    iD, iR = e["iD"], e["iR"]
    minors = e.get("minors") or []
    mix = e.get("mix") or [1.0]
    R0, Rsd = float(e.get("R") or 0), float(e.get("Rsd") or 0)
    ls0, kap = logit(e.get("s0", 0.5)), float(e.get("kap", 1.0))
    h = e.get("h") or []
    xc = e.get("xc") or []
    ve_sd = math.sqrt(max(float(e.get("ve") or 0), 0.0))
    oth, oth_sd = float(e.get("oth") or 0), float(e.get("oth_sd") or 0)
    late = [(li, float(v), logit(q)) for li, v, q in (e.get("late") or [])]
    pos = e.get("pos")
    shares = [[] for _ in range(n)]
    wins = [0] * n
    votes = []
    perm = list(range(n))
    for d in range(draws):
        dg, zc, lf, lo, gp, _gn = shared[d]
        delta = rng.gauss(0.0, ve_sd) if ve_sd > 0 else 0.0
        for j, c in h:
            delta += c * dg[j]
        for j, c in xc:
            delta += c * zc[j]
        if pos is not None:
            rng.shuffle(perm)
            delta += gp * (pos[perm[iD]] - pos[perm[iR]])
        srem = expit(ls0 + kap * delta)
        Rd = R0 * math.exp(rng.gauss(0.0, Rsd)) if R0 > 0 else 0.0
        o = min(0.9, oth * math.exp(rng.gauss(0.0, oth_sd))) if oth > 0 else 0.0
        Ls = Ld = 0.0
        for li, lv, lq in late:
            L = lv * lf[li]
            Ls += L
            Ld += L * expit(lq + lo[li])
        v = C[:]
        two = (Rd + Ls) * (1.0 - o)
        dfl = Rd * (1.0 - o) * srem + Ld * (1.0 - o)
        v[iD] += dfl
        v[iR] += two - dfl
        rest = (Rd + Ls) * o
        for m, k in enumerate(minors):
            v[k] += rest * mix[m]
        tot = sum(v) + cwi + rest * mix[-1]
        best = 0
        for k in range(1, n):
            if v[k] > v[best]:
                best = k
        wins[best] += 1
        inv = 1.0 / tot if tot > 0 else 0.0
        for k in range(n):
            shares[k].append(v[k] * inv)
        votes.append(tot)
    return _summarise(e, shares, wins, votes, draws)


def _multi(e, shared, rng, draws):
    cands = e["cands"]
    n = len(cands)
    seats = e.get("seats") or 1
    C = [float(x) for x in e["C"]]
    cwi = float(e.get("Cwi") or 0)
    R0, Rsd = float(e.get("R") or 0), float(e.get("Rsd") or 0)
    mu = [float(x) for x in e["mu"]]
    sd_ = e.get("sd") or 0
    sds = [float(x) for x in sd_] if isinstance(sd_, list) else [float(sd_)] * n
    df = e.get("df")
    wi = float(e.get("wi") or 0)
    late = [(li, float(v)) for li, v in (e.get("late") or [])]
    pos = e.get("pos")
    first = e.get("first")
    g_kind = e.get("pg", "np")
    equal = bool(e.get("equal"))
    shares = [[] for _ in range(n)]
    wins = [0] * n
    votes = []
    perm = list(range(n))
    for d in range(draws):
        _dg, _zc, lf, _lo, gp, gn = shared[d]
        g = gn if g_kind == "np" else gp
        f = math.sqrt((df - 2) / rng.gammavariate(df / 2.0, 2.0)) if df else 1.0
        lw = [mu[k] + (rng.gauss(0.0, sds[k] * f) if sds[k] > 0 else 0.0) for k in range(n)]
        if first is not None:
            lw[first] += g
        elif pos is not None:
            rng.shuffle(perm)
            for k in range(n):
                lw[k] += g * pos[perm[k]]
        top = max(lw)
        ex = [math.exp(x - top) for x in lw]
        t = sum(ex)
        Rd = R0 * math.exp(rng.gauss(0.0, Rsd)) if R0 > 0 else 0.0
        for li, lv in late:
            Rd += lv * lf[li]
        named = Rd * (1.0 - wi) / t
        v = [C[k] + named * ex[k] for k in range(n)]
        tot = sum(v) + cwi + Rd * wi
        if seats == 1:
            best = 0
            for k in range(1, n):
                if v[k] > v[best]:
                    best = k
            wins[best] += 1
        else:
            for k in sorted(range(n), key=lambda k: -v[k])[:seats]:
                wins[k] += 1
        inv = 1.0 / tot if tot > 0 else 0.0
        for k in range(n):
            shares[k].append(v[k] * inv)
        votes.append(tot)
    return _summarise(e, shares, wins, votes, draws, equal=equal)


# ============================================================================================== the run

def race_in_sha(entry, frame):
    """The digest of everything one race's numbers depend on: its own entry, the method and parameters, and the shared
    blocks it reads (a partisan race the swing surface's; every race the late batches' and the first-line priors)."""
    sh = frame.get("shared") or {}
    keep = {"race": entry, "method": frame.get("method"), "sim": SIM_VERSION, "params": frame.get("params"),
            "late": sh.get("late"), "pos": sh.get("pos")}
    if entry.get("kind") == "partisan":
        keep["g"] = sh.get("g")
        keep["counties"] = sh.get("counties")
    return R.sha_text(canonical(keep))


def simulate(frame, seed, draws):
    """Every race's numbers from a frame: {"races": [race output]} (runs.record_run's shape). The same frame, seed and
    draws always give the same numbers (runs.redo checks it)."""
    shared = shared_draws(frame, seed, draws)
    out = []
    for e in frame["races"]:
        st = e.get("status")
        if st in ("unopposed", "no-candidates", "not-modelled"):
            res = {"race": e["race"], "status": st, "seats": e.get("seats") or 1,
                   "cands": [{"key": c["key"], "name": c["name"]} for c in e["cands"]], "note": e.get("note")}
        else:
            rng = rng_for(seed, e["race"])
            res = _partisan(e, shared, rng, draws) if e["kind"] == "partisan" else _multi(e, shared, rng, draws)
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
    shared = {"g": {"dims": ["S"], "cov": [[0.0025]]}, "counties": ["001"],
              "late": {"counties": ["001"], "sdlog": 0.5, "county_sdlog": 0.3, "lean_sd": 0.2},
              "pos": {"partisan": [0.0, 0.04], "nonpartisan": [0.04, 0.16]}}
    two = {"race": "P1", "kind": "partisan", "status": "counting", "seats": 1, "units_in": 5, "units_all": 10, "counted": 1000,
           "cands": [{"key": "d", "name": "D", "p": "D"}, {"key": "r", "name": "R", "p": "R"}, {"key": "g", "name": "G", "p": "O"}],
           "iD": 0, "iR": 1, "minors": [2], "mix": [0.8, 0.2], "C": [500, 480, 20], "Cwi": 0, "R": 1000, "Rsd": 0.05,
           "s0": 0.5, "kap": 0.95, "h": [[0, 1.0]], "xc": [[0, 0.03]], "ve": 0.002, "oth": 0.02, "oth_sd": 0.2,
           "late": [[0, 30, 0.5]], "pos": [0.01, -0.01, 0.0]}
    lead = dict(two, race="P2", C=[700, 280, 20], units_in=9)
    multi = {"race": "N1", "kind": "multi", "status": "counting", "seats": 1, "units_in": 1, "units_all": 4, "counted": 200,
             "cands": [{"key": "a", "name": "A"}, {"key": "b", "name": "B"}], "C": [120, 78], "Cwi": 2, "R": 600, "Rsd": 0.1,
             "mu": [0.2, -0.2], "sd": 0.3, "df": 6, "wi": 0.006, "late": [[0, 10]], "pos": [0.05, -0.05], "pg": "np"}
    eq = {"race": "N2", "kind": "multi", "status": "pre", "seats": 1, "units_in": 0, "units_all": 3, "counted": 0, "equal": True,
          "cands": [{"key": "a", "name": "A"}, {"key": "b", "name": "B"}, {"key": "c", "name": "C"}], "C": [0, 0, 0], "Cwi": 0,
          "R": 300, "Rsd": 0.1, "mu": [0.0, 0.0, 0.0], "sd": 0.4, "df": None, "wi": 0.006, "late": []}
    seats2 = dict(multi, race="N3", seats=2, cands=multi["cands"] + [{"key": "c", "name": "C"}], C=[100, 60, 38], mu=[0.1, 0.0, -0.1],
                  pos=None)
    unopp = {"race": "U1", "kind": "multi", "status": "unopposed", "seats": 1, "cands": [{"key": "z", "name": "Z"}]}
    frame = json.loads(canonical({"method": "live-test", "params": {}, "shared": shared, "races": [two, lead, multi, eq, seats2, unopp]}))
    a = simulate(frame, 11, 600)
    b = simulate(frame, 11, 600)
    check("the same frame and seed give the same numbers", canonical(a) == canonical(b))
    rs = {r["race"]: r for r in a["races"]}
    check("a race ahead in the count and in the remaining precincts favours the leader", rs["P2"]["cands"][0]["chance"] > 0.95)
    check("a close count stays uncertain", 0.2 < rs["P1"]["cands"][0]["chance"] < 0.95)
    check("no chance is 0 or 1", all(0 < c["chance"] < 1 for r in a["races"] if r["status"] not in ("unopposed",) for c in r["cands"]))
    check("equal chances where nothing tells the names apart", [round(c["chance"], 9) for c in rs["N2"]["cands"]] == [round(1 / 3, 9)] * 3)
    check("two seats: the chances add to two", abs(sum(c["chance"] for c in rs["N3"]["cands"]) - 2.0) < 0.01)
    check("an unopposed race carries no chance", [c.get("chance") for c in rs["U1"]["cands"]] == [None])
    check("the share counted is the counted votes over the expected total", 0.3 < rs["P1"]["share_counted"] < 0.7)
    check("80 percent ranges sit inside 95 percent ranges", all(c["lo95"] <= c["lo80"] <= c["median"] <= c["hi80"] <= c["hi95"]
                                                                 for r in a["races"] if r["status"] != "unopposed" for c in r["cands"]))
    other = simulate(frame, 12, 600)
    check("another seed gives other draws", canonical(other) != canonical(a))
    check("a race's inputs digest ignores the seed", other["races"][0]["in_sha"] == a["races"][0]["in_sha"])
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
