"""election/model/blindspots.py - John's three blind spots on election night: count order, roll-off and ballot position
(ARCHITECTURE.md 4.1; model.md 2). Owned by N17. Analysis, never a result.

    python -m election.model.blindspots --calibrate [--state mn]     the night model replayed on 2022 and 2024 in N16's four
                                                                     counting orders; its spreads sized so that 80 percent
                                                                     ranges hold about 80 percent of the time in every order;
                                                                     how much an early lead means; stored as a run of kind
                                                                     "replay" (the parameters live_model.py reads)
    python -m election.model.blindspots --calibrate --no-store       the same, printed only
    python -m election.model.blindspots --selftest                   the arithmetic on made-up precincts; reads no file

COUNT ORDER (Minnesota: which precincts report first, and each county's late absentee ballots)
  The night's model never assumes the precincts counted first are typical: each is compared with its own expectation and
  the gaps are explained by the state, the congressional district, the county and the Census terms (live_model.py).
  late_added()      a county's late absentee batch (ballots that reach it after 3 p.m. on Election Day, Minn. Stat. 204C.19
                    subd. 3) is outstanding until the store shows a precinct of that county counted again after its first
                    report; until then the model holds a block of the county's absentee share times a prior (about 3
                    percent, give or take a factor of two) with a lean of the county's own plus an unknown offset of about
                    5 points.
  calibrate()       the replays: N16's own orders (backtest.reveal_order: random; small and rural first; whole counties
                    with the largest metro counties last; a late absentee batch held back in every county), on the 2022
                    and 2024 precinct results carried onto today's lines (backtest.lines_votes), scored at 5, 10, 25, 50,
                    75 and 90 percent counted; partisan races with the night's model as it runs tonight, nonpartisan races
                    (county, court, soil and water, MEDSL's copies of the Secretary's files) likewise. A few settings of
                    the model's spreads are tried (for nonpartisan races also how much wider a range grows when the
                    precincts counted are smaller or larger than those still out); for each, the smallest scale whose 80
                    percent ranges hold at least 78 percent of results in every order and checkpoint; the setting with
                    the best log score is kept, with how often the candidate ahead at each point finished first ("how
                    much an early lead means").
  type_order()      for states whose files split votes by ballot type, which types arrive first (the registry's own notes);
                    the night's model reads Minnesota only, where there is one total a precinct.
ROLL-OFF (18 to 52 percent of voters skip a county or judicial race)
  rolloff_arrays()  each precinct's 2022 share of voters skipping each kind of race (forecast.py's rules), so a race's
                    expected votes are the precinct's ballots less those who skip it;
  rolloff_update()  tonight's correction: in the precincts counted, a race's votes against the governor's race's, compared
                    with what the roll-off figures expected, pulled toward none while few are in;
  incomplete()      counted precincts where a race has more votes than the governor's race (listed, never changed).
BALLOT POSITION (Minnesota rotates names precinct by precinct; town ballots are alphabetical)
  rotation_of()     the rebuilt rotation (Minn. R. 8220.0825, forecast.rotation_subtotals): which base position each of a
                    race's precincts prints first, dealt by registered voters;
  exposure_gap()    each base position's share of the votes still out less its share of the votes counted: the first-line
                    edge (a prior: 0 to 1 point partisan, 1 to 4 nonpartisan) moves the projection by that difference. The
                    base order is drawn by lot and not on file, so every draw takes a fresh one. Town races list names
                    alphabetically everywhere, so the counted shares already carry the edge and nothing moves.
"""

import argparse
import json
import math
import os
import random
import sys
import time
from collections import defaultdict

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from election.model import DB  # noqa: E402
from election.model import runs as R  # noqa: E402

CHECKPOINTS = (0.05, 0.10, 0.25, 0.50, 0.75, 0.90)   # ARCHITECTURE.md 4.1's five, and 5 percent: the night's first saves
ORDERS = ("random", "small-first", "metro-last", "late-batch")
LATE_REPLAY = (0.06, 0.55)        # N16's late-batch scenario: 6% of each precinct's absentee share, a county lean of logit(0.55)
SHARE_BINS = ((0.0, 0.10), (0.10, 0.25), (0.25, 0.50), (0.50, 0.75), (0.75, 1.01))
LEAD_BINS = ((0.0, 2.0), (2.0, 5.0), (5.0, 10.0), (10.0, 1000.0))
Z80, Z95 = 1.2816, 1.96
TARGET = 0.78                      # the worst order and checkpoint's 80 percent coverage must reach this (N16's rule)
MIN_CELL = 30                      # a cell of fewer races says too little to steer the rule (reported all the same)


def say_default(*a):
    print(*a, flush=True)


def _quiet(*_a, **_k):
    return None


# ============================================================================================== roll-off

def rolloff_arrays(ids, feats):
    """{"partisan": {class: [share skipping, by precinct]}, "np": {group: [...]}}: forecast.py's own rules (2022's
    figures; the U.S. Senate's from 2018; a precinct with no figure takes the median; nonpartisan groups from MEDSL's
    2022 copy carried onto today's lines)."""
    from election.model import forecast as F
    ro = {}
    for c in ("mngov", "mnsos", "mnag", "mnaud", "usrep", "mnsen", "mnleg", "ussen"):
        name = f"rolloff_{c}_2018" if c == "ussen" else f"rolloff_{c}_2022"
        vals = [feats.get(name, {}).get(v) for v in ids]
        known = sorted(x for x in vals if x is not None)
        med = known[len(known) // 2] if known else 0.03
        ro[c] = [F.clamp(x if x is not None else med, 0.0, 0.9) for x in vals]
    return {"partisan": ro, "np": F.np_rolloff(ids)}


def rolloff_update(spec, rep, anchor_rep, ev_anchor, n, prm):
    """Tonight's roll-off correction for one race (log factor on its remaining expected votes, and its variance): in each
    counted precinct, the race's votes over the governor's race's votes, against the expected ratio. None counted: none."""
    ev = defaultdict(float)
    for (i, _w), x in zip(spec.get("members") or [], spec.get("ev") or []):
        ev[i] += x
    ro = prm["rolloff"]
    prior_sd = ro["prior_sd_p"] if spec.get("kind") == "partisan" else ro["prior_sd_np"]
    num, prec = 0.0, 1.0 / prior_sd ** 2
    for i, v in rep.items():
        a = anchor_rep.get(i)
        e_r, e_a = ev.get(i, 0.0), ev_anchor.get(i, 0.0)
        if a is None or e_r <= 0 or e_a <= 0 or a[2] <= 0:
            continue
        tot = sum(v[:n + 1])
        x = math.log((tot + 0.5) / (a[2] + 0.5)) - math.log(e_r / e_a)
        w = 1.0 / (ro["sigma"] ** 2 + 1.0 / (tot + 1.0))
        num += w * x
        prec += w
    return num / prec, 1.0 / prec


def incomplete(rep, anchor_rep, n, ratio=1.10):
    """Counted precincts where a race has more votes than the governor's race (a check that a precinct's count is whole;
    listed, never changed)."""
    out = []
    for i, v in rep.items():
        a = anchor_rep.get(i)
        if a and sum(v[:n + 1]) > ratio * a[2] + 10:
            out.append(i)
    return out


# ============================================================================================== count order: late batches

def late_added(con, anchor_race, base):
    """The counties whose late absentee ballots have been added: a precinct of the county counted again (its votes in the
    anchor race changed) after its first report. Returns a frozenset of county codes (three digits)."""
    if not anchor_race:
        return frozenset()
    U = base["U"]
    first = {u: sid for u, sid in con.execute("SELECT unit_id, MIN(snapshot_id) FROM reporting WHERE race_id = ? AND units_in > 0 "
                                               "GROUP BY unit_id", (anchor_race,))}
    out = set()
    for u, sid in con.execute("SELECT unit_id, MAX(snapshot_id) FROM counts WHERE race_id = ? AND vote_type = 'total' GROUP BY unit_id",
                              (anchor_race,)):
        f = first.get(u)
        i = U["pos"].get(u)
        if f is not None and i is not None and sid > f:
            out.add(U["counties"][U["cty"][i]])
    return frozenset(out)


def type_order(code):
    """What a state's registry says about the order its votes arrive in, and its vote types (the registry's own words).
    Minnesota: one total a precinct, so the order is which precincts report first and each county's late batch."""
    p = os.path.join(HERE, "election", "registry", f"{code.lower()}.json")
    if not os.path.exists(p):
        return None
    doc = json.load(open(p, encoding="utf-8"))
    return {"count_order": doc.get("count_order"), "vote_types": doc.get("vote_types"), "how_counted": doc.get("how_counted")}


# ============================================================================================== ballot position

def rotation_of(members, U, n):
    """The rebuilt rotation of a race (Minn. R. 8220.0825): each member precinct's rotation, dealt by registered voters
    (2024's count on today's lines stands in for the May 1, 2026 count: an estimate). In members' order."""
    from election.model import forecast as F
    regs = [(U["ids"][i], (U["regs"][i] or 0) * w) for i, w in members]
    rot, _sub = F.rotation_subtotals(regs, n)
    return rot


def exposure_gap(rot, members, counted_w, remaining_w, n):
    """Each base position's share of the votes still out less its share of the votes counted (positions printed first,
    rotation r printing base position r first). None when nothing is counted or nothing is out."""
    rep = [0.0] * n
    rem = [0.0] * n
    for (i, _w), r in zip(members, rot):
        if i in counted_w:
            rep[r] += counted_w[i]
        elif i in remaining_w:
            rem[r] += remaining_w[i]
    a, b = sum(rep), sum(rem)
    if a <= 0 or b <= 0:
        return None
    return [rem[k] / b - rep[k] / a for k in range(n)]


# ============================================================================================== the replays: data of past years

def _replay_units(base_bt, Y, L):
    """The night model's units for a past year on today's lines (backtest.load_base): lean, county, district, Census
    terms as they stood before that year, absentee share of the election four years earlier."""
    from election.model import forecast as F
    from election.model import live_model as LM
    ids = base_bt["ids"]
    counties = sorted(set(base_bt["counties"]))
    cpos = {c: k for k, c in enumerate(counties)}
    cds = [str((base_bt["props"][v] or {}).get("cd") or "0") for v in ids]
    regions = sorted(set(cds))
    rpos = {r: k for k, r in enumerate(regions)}
    feats = dict(base_bt["feats"])
    extra = sorted({"share_bachelors_plus", "density2020", "share_65plus", "lean_usprs_2020", "lean_usprs_2016",
                    f"share_absentee_mail_{Y - 4}", f"registered_{Y - 2}"} - set(feats))
    if extra:
        more, _st, _b = F.read_features(extra)
        feats.update(more)
    ab = []
    for v in ids:
        x = feats.get(f"share_absentee_mail_{Y - 4}", {}).get(v)
        ab.append(min(max(x, 0.0), 1.0) if x is not None else 0.2)
    return {"ids": ids, "pos": {v: i for i, v in enumerate(ids)}, "L": list(L), "cty": [cpos[c] for c in base_bt["counties"]],
            "counties": counties, "reg": [rpos[c] for c in cds], "regions": regions, "Z": LM.census_terms(feats, ids, L, Y),
            "fnames": list(LM.FEATURES), "ab": ab, "regs": [feats.get(f"registered_{Y - 2}", {}).get(v) or 0 for v in ids]}


def partisan_year(base_bt, Y, params_bt):
    """A past year's partisan races as the night model sees them: units, race specs (the forecast as it stood before the
    vote, with no polls: backtest.pre_environment), every member precinct's votes [DFL, Republican, other] and the truth."""
    from election.model import backtest as BT
    from election.model import forecast as F
    races = BT.partisan_contests(Y, base_bt, say=_quiet)
    BT.set_incumbency(Y, races, say=_quiet)
    L, _used = F.lean_vector(base_bt["feats"], base_bt["state"], base_bt["ids"], Y, params_bt["lean"], base_bt["counties"])
    U = _replay_units(base_bt, Y, L)
    sg = BT.anchor_grid(base_bt, Y, L)
    g_pre = BT.pre_environment(base_bt["state"], Y)
    top = F.TOP_OF_TICKET[Y]
    lines = BT.lines_votes(Y, base_bt)

    def X(y):
        return F.inverse(sg, F.expit(y))
    slope = (X(g_pre + 0.02) - X(g_pre - 0.02)) / 0.04
    m0 = X(g_pre)
    vv = {}
    specs, votes, truth = [], {}, {}
    anchor_id = None
    cands = [{"key": "D", "name": "DFL", "p": "D"}, {"key": "R", "name": "Republican", "p": "R"}]
    for r in races:
        cls = r["class"]
        if cls not in vv:
            vv[cls] = BT.votes_vector(base_bt, Y, cls)
        members = base_bt["index"]["state:MN"] if r["statewide"] else r["members"]
        per = {}
        D = Rv = T = 0.0
        for i, w in members:
            rec = lines.get(base_bt["ids"][i])
            if not rec:
                continue
            d, rr = rec.get(cls + "dfl", 0) or 0, rec.get(cls + "r", 0) or 0
            t = rec.get(cls + "total", rec.get(cls + "tot", 0)) or 0
            o = max(t - d - rr, 0.0)
            if d + rr + o <= 0:
                continue
            per[i] = (d, rr, o)
            D += d
            Rv += rr
            T += d + rr + o
        if D <= 0 or Rv <= 0:
            continue
        rid = r["id"]
        spec = {"race": rid, "kind": "partisan", "seats": 1, "cands": cands, "members": members,
                "ev": [vv[cls][i] * w for i, w in members], "iD": 0, "iR": 1, "tested": "replay", "rot": False, "first": None}
        if r["statewide"]:
            spec["m"] = m0
            if cls == top:
                spec.update(anchor=True, v_s=slope * slope * F.PRIORS["env_no_polls_sd"] ** 2, vd=0.0)
                anchor_id = rid
            else:
                osd = params_bt["office_sd_senate"] if cls in ("ussen", "ussse") else params_bt["office_sd"]
                spec["vd"] = slope * slope * osd * osd + 0.02 ** 2
        else:
            gap = params_bt["gap"].get(cls, [0.0, 0.06])
            iota = params_bt["inc"]
            dirn = r.get("inc_dir", 0)
            spec["m"] = m0 + gap[0] + iota[0] * dirn
            spec["vd"] = gap[1] ** 2 + (iota[1] * dirn) ** 2 + params_bt["region_sd"] ** 2 + params_bt["district_sd"].get(cls, 0.14) ** 2
        spec["oth_prior"] = (T - D - Rv) / T if T else 0.02
        specs.append(spec)
        votes[rid] = per
        truth[rid] = {"two": D / (D + Rv), "d_share": D / T, "won": 0 if D > Rv else 1, "total": T,
                      "group": "statewide" if r["statewide"] else cls}
    return {"kind": "partisan", "U": U, "specs": specs, "votes": votes, "truth": truth, "anchor": anchor_id, "lines": lines,
            "base": {"ids": base_bt["ids"], "counties": base_bt["counties"]}}


def _np_key(year, r):
    """A MEDSL row's nonpartisan race key, as backtest.np_contests makes it."""
    from election.model import backtest as BT
    from election.model import forecast as F
    o = r["office"].upper().strip()
    special = (r.get("special") or "").upper() == "TRUE" or o.startswith("SPECIAL ELECTION")
    base_o = o.replace("SPECIAL ELECTION FOR ", "")
    county = (r.get("county_fips") or "")[-3:]
    if base_o in BT.COUNTY_KINDS:
        kind = BT.COUNTY_KINDS[base_o]
        d = F._dist_key(r.get("district")) if kind in ("county_commissioner", "county_park") else ""
        return (year, "county", kind, county, d, special), "county", kind, county
    if base_o == "SOIL AND WATER SUPERVISOR":
        return (year, "soil_water", "soil_water", county, F._dist_key(r.get("district")), special), "soil_water", "soil_water", county
    ck = BT._court_key(year, base_o, r.get("district"))
    if not ck:
        return None, None, None, None
    return (year, "judicial") + tuple(map(str, ck)) + (special,), "judicial", ck[0], None


def nonpartisan_year(Y, params_bt):
    """A past year's nonpartisan races (county, court, soil and water) precinct by precinct from MEDSL's copy (secondary),
    on that year's own precincts: units, specs, votes and the truth. Expected votes of a precinct still out are its own
    eventual number of voters in the race, give or take about 15 percent (the replays test the shares, not turnout)."""
    from election.model import backtest as BT
    from election.model import data_mn
    from election.model import live_model as LM
    rows, _info = data_mn.medsl_by_vtdid(Y, say=_quiet)
    tab = data_mn.table(Y)["rows"]
    ids = sorted(r["vtdid"] for r in tab if (r.get("totvoting") or 0) > 0)
    pos = {v: i for i, v in enumerate(ids)}
    counties = sorted({v[2:5] for v in ids})
    cpos = {c: k for k, c in enumerate(counties)}
    trow = {r["vtdid"]: r for r in tab}
    U = {"ids": ids, "pos": pos, "L": [0.0] * len(ids), "cty": [cpos[v[2:5]] for v in ids], "counties": counties, "reg": [0] * len(ids),
         "regions": ["0"], "Z": [[0.0] * len(LM.FEATURES) for _ in ids], "fnames": list(LM.FEATURES),
         "ab": [min(max((trow[v].get("ab_mb") or 0) / max(trow[v].get("totvoting") or 1, 1), 0.0), 1.0) for v in ids],
         "regs": [trow[v].get("reg7am") or 0 for v in ids]}
    races = {}
    for r in rows:
        key, grp, kind, county = _np_key(Y, r)
        if key is None or r.get("vtdid") not in pos:
            continue
        rec = races.setdefault(key, {"group": grp, "kind": kind, "county": county, "cands": defaultdict(int), "wi": 0,
                                     "by": defaultdict(lambda: defaultdict(int))})
        i = pos[r["vtdid"]]
        if (r.get("writein") or "").upper() == "TRUE":
            rec["wi"] += r["votes"]
            rec["by"][i]["_wi"] += r["votes"]
        else:
            rec["cands"][r["candidate"]] += r["votes"]
            rec["by"][i][r["candidate"]] += r["votes"]
    for rec in races.values():
        rec["cands"] = dict(rec["cands"])
    # holders: 2022's county and soil and water races from 2018's winners, 2024's courts from 2018's (backtest's rules)
    prev = BT.np_contests(2018)
    if Y == 2022:
        BT.np_incumbency({k: v for k, v in races.items() if v["group"] in ("county", "soil_water")},
                         {k: v for k, v in prev.items() if v["group"] in ("county", "soil_water")})
    else:
        BT.np_incumbency({k: v for k, v in races.items() if v["group"] == "judicial"},
                         {k: v for k, v in prev.items() if v["group"] == "judicial"})
    npf = params_bt["np"]
    specs, votes, truth = [], {}, {}
    for key, rec in sorted(races.items(), key=lambda kv: str(kv[0])):
        names = sorted(n for n, v in rec["cands"].items() if v > 0)
        if len(names) < 2:
            continue
        rid = f"{Y}-np-" + "-".join(str(k) for k in key[1:] if k not in (True, False, ""))
        members = sorted(rec["by"])
        rng = random.Random(f"np-ev-{rid}")
        per = {}
        ev = []
        for i in members:
            b = rec["by"][i]
            row = [b.get(n, 0) for n in names] + [b.get("_wi", 0)]
            per[i] = row
            ev.append(sum(row) * math.exp(rng.gauss(0.0, 0.15)))
        inc = rec.get("inc") or {}
        cands = [{"key": f"c{k}", "name": n, "inc": inc.get(n, 0)} for k, n in enumerate(names)]
        tau = npf["tau"].get(rec["group"], 0.42)
        mu = [npf["beta_inc"][0] * c["inc"] for c in cands]
        specs.append({"race": rid, "kind": "multi", "seats": 1, "cands": cands, "members": [(i, 1.0) for i in members], "ev": ev,
                      "mu": mu, "tau": tau, "df": npf.get("df"), "pg": "np", "rot": True, "first": None, "wi_prior": 0.007,
                      "tested": "replay"})
        votes[rid] = per
        tot = sum(rec["cands"].values()) + rec["wi"]
        won = max(names, key=lambda n: rec["cands"][n])
        truth[rid] = {"shares": [rec["cands"][n] / tot for n in names], "won": names.index(won), "total": tot, "group": rec["group"]}
    lines = {v: {"totvoting": trow[v].get("totvoting") or 0, "ab_mb": trow[v].get("ab_mb") or 0} for v in ids}
    return {"kind": "multi", "U": U, "specs": specs, "votes": votes, "truth": truth, "anchor": None, "lines": lines,
            "base": {"ids": ids, "counties": [v[2:5] for v in ids]}}


def steps_of(yd, Y):
    """N16's orders (backtest.reveal_order) over the year's precincts, each with its own seed (the same as N16's for the
    partisan replays, "replay-<year>-<order>"), cut at each checkpoint: [(order, checkpoint, precincts in, county leans
    of the late-batch scenario)]."""
    from election.model import backtest as BT
    from election.model import forecast as F
    lines, base = yd["lines"], yd["base"]
    total = sum((lines.get(v) or {}).get("totvoting", 0) for v in base["ids"])
    out = []
    for order in ORDERS:
        seed = f"replay-{Y}-{order}" if yd["kind"] == "partisan" else f"replay-np-{Y}-{order}"
        seq = BT.reveal_order(base, lines, order, random.Random(seed))
        late = {}
        if order == "late-batch":
            lr = random.Random(seed + "-late")
            for c in sorted(set(base["counties"])):
                late[c] = lr.gauss(0.0, F.logit(LATE_REPLAY[1]))
        reported, counted, k = set(), 0.0, 0
        for cp in CHECKPOINTS:
            while k < len(seq) and counted / total < cp:
                i = seq[k]
                k += 1
                reported.add(i)
                counted += (lines.get(base["ids"][i]) or {}).get("totvoting", 0)
            out.append((order, cp, frozenset(reported), late))
    return out


def observe(yd, reported, late):
    """The votes counted with `reported` in: {race: {"rep": {unit: [...]}}}; in the late-batch scenario each precinct's
    late part (6 percent of its absentee share) is held back, leaning its county's way in a partisan race and split like
    the precinct in a nonpartisan one."""
    from election.model import forecast as F
    U, lines = yd["U"], yd["lines"]
    obs = {}
    for rid, per in yd["votes"].items():
        rep = {}
        for i, row in per.items():
            if i not in reported:
                continue
            if not late:
                rep[i] = list(row)
                continue
            rec = lines.get(U["ids"][i]) or {}
            cut = LATE_REPLAY[0] * (rec.get("ab_mb", 0) or 0) / max(rec.get("totvoting", 0) or 1, 1)
            if yd["kind"] == "partisan":
                d, r, o = row
                two = d + r
                held = two * cut
                lean = late.get(U["counties"][U["cty"][i]], 0.0)
                p = F.expit(F.logit(F.clamp(d / two, 0.01, 0.99)) + lean) if two > 0 else 0.5
                rep[i] = [max(d - held * p, 0.0), max(r - held * (1 - p), 0.0), o * (1 - cut)]
            else:
                rep[i] = [x * (1 - cut) for x in row]
        obs[rid] = {"rep": rep}
    return obs


def _phi(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


# ============================================================================================== the replays: scoring

def score_partisan(yd, entries, shared):
    """One row a race with votes still out: {race, group, z (truth less the mean over the spread, at scale 1), F, sd,
    truth, won_d, lead (counted, points), frac (share of the race counted), leader_is_d, leader_won}."""
    from election.model import live_model as LM
    out = []
    for e in entries:
        t = yd["truth"].get(e["race"])
        if not t or e.get("kind") != "partisan":
            continue
        C = e["C"]
        frac = (sum(C) + (e.get("Cwi") or 0)) / t["total"] if t["total"] else 0.0
        if frac >= 0.999:
            continue
        F_, sd = LM.predictive_two_party(e, shared)
        cnt = C[0] + C[1]
        out.append({"race": e["race"], "group": t["group"], "z": (t["two"] - F_) / sd, "F": F_, "sd": sd, "truth": t["two"],
                    "won_d": 1 - t["won"], "lead": (abs(C[0] - C[1]) / cnt * 100) if cnt else 0.0, "frac": frac,
                    "leader_is_d": (C[0] >= C[1]) if cnt else None,
                    "leader_won": (int((C[0] >= C[1]) == (t["won"] == 0)) if cnt else None)})
    return out


def coverage(rows, scale, z=Z80):
    return sum(1 for r in rows if abs(r["z"]) <= z * scale) / len(rows) if rows else None


def choose_scale(cells, target=TARGET, lo=0.5, hi=3.0):
    """The smallest scale (steps of 0.05) at which the 80 percent ranges hold at least `target` of results in every cell
    (order and checkpoint) of at least MIN_CELL races, with the worst such cell's coverage at each scale tried."""
    table, best = {}, None
    big = [rows for rows in cells.values() if len(rows) >= MIN_CELL] or [rows for rows in cells.values() if rows]
    s = lo
    while s <= hi + 1e-9:
        worst = min(coverage(rows, s) for rows in big)
        table[f"{s:.2f}"] = round(worst, 3)
        if best is None and worst >= target:
            best = round(s, 2)
        s += 0.05
    return best or hi, table


def neg_log_score(rows, scale):
    """The mean negative log density of the truth under the normal predictive (a proper score: lower is better)."""
    return sum(0.5 * (r["z"] / scale) ** 2 + math.log(r["sd"] * scale) for r in rows) / len(rows)


def lead_table(rows, scale):
    """How much an early lead means: by share of the race counted and size of the counted lead, how often the candidate
    ahead finished first, beside the model's average chance for that candidate (at the chosen scale)."""
    cells = defaultdict(lambda: [0, 0, 0.0])
    for r in rows:
        if r["leader_won"] is None:
            continue
        sb = next((b for b in SHARE_BINS if b[0] <= r["frac"] < b[1]), None)
        lb = next((b for b in LEAD_BINS if b[0] <= r["lead"] < b[1]), None)
        if not sb or not lb:
            continue
        p_d = _phi((r["F"] - 0.5) / (r["sd"] * scale))
        c = cells[(sb, lb)]
        c[0] += 1
        c[1] += r["leader_won"]
        c[2] += p_d if r["leader_is_d"] else 1 - p_d
    return [{"counted": [round(sb[0] * 100), round(min(sb[1], 1.0) * 100)], "lead": [lb[0], None if lb[1] >= 1000 else lb[1]],
             "races": n, "leader_finished_first": held, "share": round(held / n, 3), "model_chance": round(ch / n, 3)}
            for (sb, lb), (n, held, ch) in sorted(cells.items())]


def partisan_cells(setups, prm):
    """The night model on every step of the partisan replays at one setting: {(order, checkpoint): [score rows]}, and
    every step's entries and shared block (for the simulated check)."""
    from election.model import live_model as LM
    cells = defaultdict(list)
    steps_out = []
    for Y, yd, steps in setups:
        for order, cp, reported, late in steps:
            obs = observe(yd, reported, late)
            entries, shared, _rep, _f = LM.build_entries(yd["U"], yd["specs"], obs, prm, frozenset(), yd["anchor"], say=_quiet)
            rows = score_partisan(yd, entries, shared)
            cells[(order, int(cp * 100))] += rows
            steps_out.append((Y, yd, order, cp, entries, shared))
    return cells, steps_out


def simulated_check(steps_out, scale, draws=400):
    """The chosen setting through simulate.py itself (the night's code): Brier score, log loss and how often the 80 and
    95 percent ranges of the DFL candidate's share held, by order and checkpoint."""
    from election.model import live_model as LM
    from election.model import simulate as Sim
    cells = defaultdict(list)
    for Y, yd, order, cp, entries, shared in steps_out:
        es = []
        for e in entries:
            if e.get("kind") != "partisan":
                continue
            e = dict(e)
            e["h"] = [[j, c * scale] for j, c in (e.get("h") or [])]
            e["xc"] = [[j, c * scale] for j, c in (e.get("xc") or [])]
            e["ve"] = (e.get("ve") or 0.0) * scale * scale
            es.append(e)
        frame = json.loads(R.canonical({"method": LM.LIVE_METHOD, "params": {}, "shared": shared, "races": es}))
        sim = Sim.simulate(frame, R.seed_of(f"replay-{Y}-{order}-{cp}"), draws)
        for e, out in zip(frame["races"], sim["races"]):
            t = yd["truth"].get(e["race"])
            frac = (sum(e["C"]) + (e.get("Cwi") or 0)) / t["total"] if t and t["total"] else 0.0
            if not t or frac >= 0.999:
                continue
            c = out["cands"][0]
            cells[(order, int(cp * 100))].append({"p": c["chance"], "won": 1 - t["won"], "in80": int(c["lo80"] <= t["d_share"] <= c["hi80"]),
                                                  "in95": int(c["lo95"] <= t["d_share"] <= c["hi95"])})
    out = {}
    for (order, cp), rows in sorted(cells.items()):
        n = len(rows)
        out[f"{order} {cp}%"] = {"brier": round(sum((r["p"] - r["won"]) ** 2 for r in rows) / n, 4),
                                 "logloss": round(sum(-math.log(max(r["p"] if r["won"] else 1 - r["p"], 1e-4)) for r in rows) / n, 4),
                                 "cover80": round(sum(r["in80"] for r in rows) / n, 3), "cover95": round(sum(r["in95"] for r in rows) / n, 3),
                                 "races": n}
    return out


def np_rows(np_setups, prm, draws=300):
    """The night model on every step of the nonpartisan replays at one setting, through simulate.py: one row a race with
    votes counted and votes still out."""
    from election.model import live_model as LM
    from election.model import simulate as Sim
    out = []
    for Y, yd, steps in np_setups:
        for order, cp, reported, late in steps:
            obs = observe(yd, reported, late)
            specs = [s for s in yd["specs"] if obs[s["race"]]["rep"] and len(obs[s["race"]]["rep"]) < len(s["members"])]
            if not specs:
                continue
            entries, shared, _rep, _f = LM.build_entries(yd["U"], specs, obs, prm, frozenset(), None, say=_quiet)
            frame = json.loads(R.canonical({"method": LM.LIVE_METHOD, "params": {}, "shared": shared, "races": entries}))
            sim = Sim.simulate(frame, R.seed_of(f"np-replay-{Y}-{order}-{cp}"), draws)
            for e, res in zip(frame["races"], sim["races"]):
                t = yd["truth"][e["race"]]
                C = e["C"]
                cs = res["cands"]
                srt = sorted(C)
                out.append({"year": Y, "order": order, "cp": int(cp * 100), "race": e["race"], "group": t["group"],
                            "frac": (sum(C) + (e.get("Cwi") or 0)) / t["total"] if t["total"] else 0.0,
                            "leader": max(range(len(C)), key=lambda q: C[q]), "won": t["won"],
                            "lead": (srt[-1] - srt[-2]) / max(sum(C), 1) * 100, "chances": [c["chance"] for c in cs],
                            "in80": [int(c["lo80"] <= s <= c["hi80"]) for c, s in zip(cs, t["shares"])],
                            "in95": [int(c["lo95"] <= s <= c["hi95"]) for c, s in zip(cs, t["shares"])]})
    return out


def np_measures(rows):
    if not rows:
        return {}
    n = len(rows)
    brier = sum(sum((p - (1 if k == r["won"] else 0)) ** 2 for k, p in enumerate(r["chances"])) for r in rows) / n
    ll = sum(-math.log(max(r["chances"][r["won"]], 1e-4)) for r in rows) / n
    c80 = sum(sum(r["in80"]) for r in rows) / sum(len(r["in80"]) for r in rows)
    c95 = sum(sum(r["in95"]) for r in rows) / sum(len(r["in95"]) for r in rows)
    fav = sum(1 for r in rows if max(range(len(r["chances"])), key=lambda k: r["chances"][k]) == r["won"]) / n
    lw = sum(1 for r in rows if r["leader"] != r["won"]) / n
    return {"races": n, "brier": round(brier, 4), "logloss": round(ll, 4), "cover80": round(c80, 3), "cover95": round(c95, 3),
            "favourite_won": round(fav, 3), "leader_wrong": round(lw, 3)}


def np_cells(rows):
    cells = defaultdict(list)
    for r in rows:
        cells[(r["order"], r["cp"])].append(r)
    return cells


def np_lead_table(rows):
    cells = defaultdict(lambda: [0, 0, 0.0])
    for r in rows:
        sb = next((b for b in SHARE_BINS if b[0] <= r["frac"] < b[1]), None)
        lb = next((b for b in LEAD_BINS if b[0] <= r["lead"] < b[1]), None)
        if not sb or not lb:
            continue
        c = cells[(sb, lb)]
        c[0] += 1
        c[1] += int(r["leader"] == r["won"])
        c[2] += r["chances"][r["leader"]]
    return [{"counted": [round(sb[0] * 100), round(min(sb[1], 1.0) * 100)], "lead": [lb[0], None if lb[1] >= 1000 else lb[1]], "races": n,
             "leader_finished_first": held, "share": round(held / n, 3), "model_chance": round(ch / n, 3)}
            for (sb, lb), (n, held, ch) in sorted(cells.items())]


def lead_sentence(table, kind_words, min_races=20):
    """One plain sentence from an early-lead table: with a quarter to half of a race counted, how often the candidate ahead
    by 2 to 5 points, and by 5 to 10 points, finished first in the replays (cells of at least `min_races` races)."""
    cells = []
    for lo, hi in ((2.0, 5.0), (5.0, 10.0)):
        c = next((c for c in table if c["counted"] == [25, 50] and c["lead"] == [lo, hi] and c["races"] >= min_races), None)
        if c:
            cells.append((lo, hi, c))
    if not cells:
        return None
    lo, hi, c = cells[0]
    s = (f"In the replays of {kind_words}, with a quarter to half of a race counted, a candidate ahead by {lo:g} to {hi:g} points "
         f"finished first in {c['leader_finished_first']} of {c['races']} races")
    if len(cells) > 1:
        lo, hi, c = cells[1]
        s += f", and one ahead by {lo:g} to {hi:g} points in {c['leader_finished_first']} of {c['races']}"
    return s + "."


# ============================================================================================== the calibration run

PARTISAN_SETTINGS = [{"tau_c": tc, "tau_r": tr, "sigma_v": sv, "tau_b": tb} for tc in (0.05, 0.08, 0.12) for tr in (0.045, 0.08)
                     for sv in (0.05, 0.08) for tb in (0.005, 0.03)]
NP_SETTINGS = [{"sigma_h": sh, "rho": rho, "kappa": ka} for sh in (0.25, 0.35) for rho in (0.05, 0.15) for ka in (0.0, 0.2, 0.35)]
NP_SCALES = (0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.15, 1.3, 1.5, 1.75, 2.0, 2.5)


def np_worst(rows):
    """The worst 80 percent coverage over the cells (order and checkpoint) of at least MIN_CELL races."""
    vals = [np_measures(v)["cover80"] for v in np_cells(rows).values() if len(v) >= MIN_CELL]
    return min(vals) if vals else None


def calibrate(say=say_default, db=DB, store=True, years=(2022, 2024), np_draws=300, sim_draws=400, quick=False):
    """The night model replayed on 2022 and 2024 in every order (module docstring); stored as a run of kind "replay"
    whose frame holds the night's parameters (live_model.night_params reads them) and the report (#track)."""
    from election.model import backtest as BT
    from election.model import forecast as F
    from election.model import live_model as LM
    t0 = time.time()
    started = R.now_utc()
    params_bt, bt_run = F.latest_params(db)
    if not bt_run:
        raise SystemExit("    no backtest run on file: the replays use its fitted parameters (python -m election.model.backtest)")
    say(f"    backtest parameters from {bt_run}")
    base_bt = BT.load_base(db)
    setups = []
    for Y in years:
        yd = partisan_year(base_bt, Y, params_bt)
        setups.append((Y, yd, steps_of(yd, Y)))
        say(f"    {Y}: {len(yd['specs'])} partisan races; the anchor is {yd['anchor']}")
    report = {"backtest_run": bt_run, "orders": list(ORDERS), "checkpoints": [int(c * 100) for c in CHECKPOINTS], "target": TARGET}
    # ---- partisan
    settings = PARTISAN_SETTINGS[:2] if quick else PARTISAN_SETTINGS
    tried, best = [], None
    for st in settings:
        prm = LM.merge(LM.DEFAULT_NIGHT, st)
        prm["scale_p"] = 1.0
        t1 = time.time()
        cells, steps_out = partisan_cells(setups, prm)
        scale, table = choose_scale(cells)
        rows = [r for v in cells.values() for r in v]
        nls = neg_log_score(rows, scale)
        tried.append({**st, "scale": scale, "neg_log_score": round(nls, 4), "worst_cover80_by_scale": table})
        say(f"      partisan {st}: scale {scale}, negative log score {nls:.4f} ({time.time() - t1:.0f} s)")
        if best is None or nls < best[0]:
            best = (nls, st, scale, cells, steps_out)
    _nls, st, scale, cells, steps_out = best
    prm_final = LM.merge(LM.DEFAULT_NIGHT, st)
    prm_final["scale_p"] = scale
    meas, by_order = [], {}
    for (order, cp), rows in sorted(cells.items()):
        lw_rows = [r for r in rows if r["leader_won"] is not None]
        m = {"cover80": round(coverage(rows, scale), 3), "cover95": round(coverage(rows, scale, Z95), 3),
             "brier": round(sum((_phi((r["F"] - 0.5) / (r["sd"] * scale)) - r["won_d"]) ** 2 for r in rows) / len(rows), 4),
             "leader_wrong": round(sum(1 for r in lw_rows if not r["leader_won"]) / len(lw_rows), 3) if lw_rows else None,
             "miss_pts": round(sum(abs(r["truth"] - r["F"]) for r in rows) / len(rows) * 100, 2), "races": len(rows)}
        by_order[f"{order} {cp}%"] = m
        for k, v in m.items():
            meas.append((f"replay:{order}:{cp}", "night model partisan", k, v))
    all_rows = [r for v in cells.values() for r in v]
    report["partisan"] = {"setting": st, "scale": scale, "settings_tried": tried, "by_order": by_order}
    report["partisan_lead"] = lead_table(all_rows, scale)
    say(f"    partisan: kept {st} at scale {scale}; worst 80% coverage {min(m['cover80'] for m in by_order.values()):.0%}")
    sim = simulated_check(steps_out, scale, draws=sim_draws)
    report["partisan_simulated"] = sim
    for key, m in sim.items():
        order, cp = key.rsplit(" ", 1)
        for k in ("brier", "logloss", "cover80", "cover95"):
            meas.append((f"replay:{order}:{cp.rstrip('%')}", "night model partisan (simulated)", k, m[k]))
    say(f"    partisan, through the simulation: worst 80% coverage {min(m['cover80'] for m in sim.values()):.0%}, "
        f"Brier {sum(m['brier'] for m in sim.values()) / len(sim):.4f} on average")
    # ---- nonpartisan
    np_setups = []
    for Y in years:
        yd = nonpartisan_year(Y, params_bt)
        np_setups.append((Y, yd, steps_of(yd, Y)))
        say(f"    {Y}: {len(yd['specs'])} contested nonpartisan races")
    # each setting at the smallest scale whose 80 percent ranges hold in every cell; the best log loss of those that do
    tried_np, best_np = [], None
    for sset in (NP_SETTINGS[:1] if quick else NP_SETTINGS):
        t1 = time.time()
        got = None
        for s in NP_SCALES:
            rows = np_rows(np_setups, LM.merge(prm_final, {"np": dict(sset, scale=s)}), np_draws)
            worst = np_worst(rows)
            got = (s, worst, rows)
            if worst is not None and worst >= TARGET:
                break
        s, worst, rows = got
        m_all = np_measures(rows)
        tried_np.append({**sset, "scale": s, "worst_cover80": worst, **m_all})
        say(f"      nonpartisan {sset}: scale {s}, worst 80% coverage {worst:.0%}, log loss {m_all['logloss']:.4f} ({time.time() - t1:.0f} s)")
        key = (worst is None or worst < TARGET, m_all["logloss"] if worst is not None and worst >= TARGET else -(worst or 0))
        if best_np is None or key < best_np[0]:
            best_np = (key, sset, s, rows)
    _key, sset, np_scale, rows_np = best_np
    prm_final = LM.merge(prm_final, {"np": dict(sset, scale=np_scale)})
    np_by = {}
    for (order, cp), rows in sorted(np_cells(rows_np).items()):
        m = np_measures(rows)
        np_by[f"{order} {cp}%"] = m
        for k, v in m.items():
            meas.append((f"replay:{order}:{cp}", "night model nonpartisan", k, v))
    report["nonpartisan"] = {"setting": sset, "scale": np_scale, "settings_tried": tried_np, "by_order": np_by,
                             "all": np_measures(rows_np)}
    report["nonpartisan_lead"] = np_lead_table(rows_np)
    say(f"    nonpartisan: kept {sset} at scale {np_scale}; overall {report['nonpartisan']['all']}")
    worst_p = min(m["cover80"] for m in by_order.values() if m["races"] >= MIN_CELL)
    worst_np = np_worst(rows_np)
    prm_final["fitted"] = True
    prm_final["source"] = f"replays of {' and '.join(map(str, years))} in {len(ORDERS)} counting orders ({LM.LIVE_METHOD})"
    prm_final["summary"] = (f"80 percent ranges held at least {worst_p:.0%} of the time for partisan races"
                            + (f" and at least {worst_np:.0%} for county, court and soil and water races" if worst_np is not None else "")
                            + f", in every order and at every stage of the count that had {MIN_CELL} races or more")
    notes = [x for x in (lead_sentence(report["partisan_lead"], "partisan races"),
                         lead_sentence(report["nonpartisan_lead"], "county, court and soil and water races")) if x]
    if notes:
        prm_final["lead_note"] = " ".join(notes)
    report["seconds"] = round(time.time() - t0, 1)
    doc = {"params": prm_final, "report": report}
    if not store:
        return doc
    con = R.connect(db)
    try:
        run_id = R.new_run_id(con, "replay", "MN", started)
        with con:
            sha = R.put_blob(con, doc, "replay")
            con.execute("INSERT INTO runs (run, state, kind, method, code_sha, seed, draws, started, ended, as_of, rehearsal, frame_sha, "
                        "python, races, written, note) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (run_id, "MN", "replay", LM.LIVE_METHOD, R.keep_code(con, "replay"), R.seed_of(run_id), sim_draws, R.iso(started), None,
                         R.iso(started), 0, sha, __import__("platform").python_version(), len(all_rows) + len(rows_np), 0,
                         "the night model replayed on 2022 and 2024 in four counting orders: its spreads, and how much an early lead means"))
            con.executemany("INSERT OR REPLACE INTO run_inputs (run, input, source, sha256, as_of, kind, note) VALUES (?,?,?,?,?,?,?)",
                            [(run_id, "backtest", f"run {bt_run}", None, None, "derived", "the forecast's fitted parameters"),
                             (run_id, "commons-tables", "the Secretary of State's certified precinct tables, 2018-2024", None, None, "official",
                              "carried onto today's precincts"),
                             (run_id, "medsl", "MEDSL's copies of the Secretary's files, 2018, 2022, 2024 (CC0)", None, None, "secondary",
                              "county, court and soil and water races by precinct"),
                             (run_id, "frame", f"run_blobs:{sha}", sha, R.iso(started), "frame", "the night's parameters and the report")])
            con.executemany("INSERT OR REPLACE INTO calibration (run, scenario, grp, measure, value, n, note) VALUES (?,?,?,?,?,?,?)",
                            [(run_id, scen, grp, k, float(v), None, None) for scen, grp, k, v in meas if v is not None])
            lrows = []
            for tag, table in (("partisan", report["partisan_lead"]), ("nonpartisan", report["nonpartisan_lead"])):
                for c in table:
                    g = (f"early lead, {tag}: {c['counted'][0]}-{c['counted'][1]}% counted, ahead by {c['lead'][0]:g}"
                         + (f"-{c['lead'][1]:g}" if c["lead"][1] is not None else "+") + " points")
                    lrows.append((run_id, "lead", g, "leader_finished_first", c["share"], c["races"], f"the model's chance {c['model_chance']}"))
            con.executemany("INSERT OR REPLACE INTO calibration (run, scenario, grp, measure, value, n, note) VALUES (?,?,?,?,?,?,?)", lrows)
            con.execute("UPDATE runs SET ended = ?, written = ? WHERE run = ?", (R.iso(R.now_utc()), len(meas) + len(lrows), run_id))
        say(f"    replay run {run_id} stored: {len(meas)} measures, {len(lrows)} early-lead cells, {time.time() - t0:.0f} s in all")
        doc["run"] = run_id
        return doc
    finally:
        con.close()


# ============================================================================================== self-test

def selftest(say=say_default):
    ok = True

    def check(what, cond):
        nonlocal ok
        ok &= bool(cond)
        say(f"    {'ok ' if cond else 'BAD'} {what}")
    members = [(0, 1.0), (1, 1.0), (2, 1.0), (3, 1.0)]
    rot = [0, 1, 1, 0]
    gap = exposure_gap(rot, members, {0: 100.0, 1: 100.0}, {2: 300.0, 3: 100.0}, 2)
    check("exposure gap: still out leans to position 1", gap is not None and abs(gap[1] - (0.75 - 0.5)) < 1e-12 and abs(sum(gap)) < 1e-12)
    check("nothing out: no gap", exposure_gap(rot, members, {0: 1.0}, {}, 2) is None)
    prm = {"rolloff": {"prior_sd_p": 0.08, "prior_sd_np": 0.2, "sigma": 0.15}}
    spec = {"kind": "multi", "members": members, "ev": [80.0, 80.0, 80.0, 80.0]}
    rep = {0: [40, 30, 0], 1: [35, 35, 0]}
    anc = {0: (55, 45, 100), 1: (50, 50, 100)}
    f, v = rolloff_update(spec, rep, anc, {0: 100.0, 1: 100.0}, 2, prm)
    check(f"roll-off: fewer votes than expected pulls the factor down ({f:.3f})", f < 0 and v > 0)
    f0, v0 = rolloff_update(spec, {}, anc, {}, 2, prm)
    check("roll-off: nothing counted, no correction", f0 == 0 and abs(v0 - 0.04) < 1e-12)
    check("a precinct with more votes in a race than at the top is listed", incomplete({0: [100, 30, 0], 1: [50, 40, 0]},
                                                                                       {0: (50, 50, 100), 1: (50, 50, 100)}, 2) == [0])
    rows = [{"z": 0.1, "F": 0.55, "sd": 0.02, "truth": 0.552, "won_d": 1, "lead": 6.0, "frac": 0.3, "leader_is_d": True, "leader_won": 1},
            {"z": 2.0, "F": 0.48, "sd": 0.02, "truth": 0.52, "won_d": 1, "lead": 1.0, "frac": 0.05, "leader_is_d": False, "leader_won": 0}]
    lt = lead_table(rows, 1.0)
    check("the early-lead table counts each cell", sum(c["races"] for c in lt) == 2 and sum(c["leader_finished_first"] for c in lt) == 1)
    s, _t = choose_scale({("random", 10): rows}, target=0.5)
    check("the chosen scale holds the target", coverage(rows, s) >= 0.5)
    check("a wider scale never holds less", coverage(rows, s + 0.5) >= coverage(rows, s))
    check("the log score prefers the right spread", neg_log_score(rows, 1.0) < neg_log_score(rows, 10.0))
    t = [{"counted": [25, 50], "lead": [2.0, 5.0], "races": 60, "leader_finished_first": 45, "share": 0.75, "model_chance": 0.7}]
    check("the early-lead sentence names its cell", "45 of 60" in (lead_sentence(t, "partisan races") or ""))
    check("no sentence from too few races", lead_sentence([dict(t[0], races=5)], "partisan races") is None)
    return ok


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--state", default="mn")
    ap.add_argument("--calibrate", action="store_true")
    ap.add_argument("--no-store", action="store_true")
    ap.add_argument("--quick", action="store_true", help="two partisan settings and one nonpartisan (a trial)")
    ap.add_argument("--db", default=DB)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        sys.exit(0 if selftest() else 1)
    if a.calibrate:
        if a.state.lower() != "mn":
            sys.exit("    only Minnesota's night is replayed here")
        doc = calibrate(db=a.db, store=not a.no_store, quick=a.quick)
        print(json.dumps(doc["params"], indent=1)[:2500])
        return
    ap.print_help()


if __name__ == "__main__":
    main()
