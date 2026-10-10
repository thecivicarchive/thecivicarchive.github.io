"""election/model/other_states.py - before Election Day, a chance and a likely vote range for every race for Congress,
governor and the other statewide offices outside Minnesota, where the record allows one (ARCHITECTURE.md 4.2, 4.6;
model.md 4). Owned by N18. Analysis, never a result.

    python -m election.model.other_states --run [--states tx,oh]     one pre-election run per state, stored as a version
    python -m election.model.other_states --run --dry-run            the same, printed and not stored
    python -m election.model.other_states --backtest                 fit and score on 2022 and 2024; store the backtest run
    python -m election.model.other_states --check [--states ...]     no 0 or 100, nothing for an unopposed race, every stored
                                                                     run redone exactly, every race forecast or listed
    python -m election.model.other_states --left-out [--states ...]  every race with no forecast, and why
    python -m election.model.other_states --selftest                 the arithmetic on made-up races, in a scratch database

    election.model.other_states.run_pre(codes=None, now=None, say=print)   what run_night.py may call once a day
    election.model.other_states.left_out(code)                             {race id: the reason, in plain words}

HOW A RUN IS KEPT: through runs.py exactly as Minnesota's: kind "pre", one run per state (state = its two letters), the
frame kept whole, the seed from the run id. The frame is written in the shape forecast.simulate reads (an environment,
statewide races as offsets from it, district races as a share-by-shift grid), so runs.redo redoes it with the stored code
and runs.page_json writes the state's forecasts file in the same format as Minnesota's. This file only builds frames.

THE MODEL (METHOD; every number below sits in the frame)
  Environment. G, a state's Democratic share of the two-party vote in a generic 2026 contest (log-odds): the state's
    2024 presidential result (the Clerk of the House's statistics) moved by how far Democrats run ahead of (or behind)
    Kamala Harris's 2024 share in the U.S. Senate polls of the OTHER states by members of AAPOR's Transparency
    Initiative (the latest poll of each pollster, at most five a race, ended within 120 days), plus the state's own
    departure from a uniform swing (sized by the backtests).
  Statewide races (U.S. Senate, governor, the other single-seat statewide offices): G plus the race's own offset (sized
    by office on 2022 and 2024); a sitting U.S. senator's edge (measured on the Senate races of 2022 and 2024). The
    state's own member polls of a race, where both names polled are November's, move that race (and a little of G).
  U.S. House: the district's lean (how its precincts voted for President in 2024 against the state, from MEDSL's copy of
    the official returns, a secondary source, blended with how its 2024 House race went against the top of the ticket,
    less a sitting member's edge), plus the House's gap to the top of the ticket, a sitting member's edge and the
    district's own error, each sized on the 2024 House races of states whose lines did not change in 2024.
  Minor-party and independent candidates: shares drawn from what such candidates won in 2022 and 2024.
  Left out, each with its reason: a race whose November list is not on file; seats in states that drew new lines for
    2026 (no official or labelled secondary source on file gives past results on the new lines); several seats from one
    list; nonpartisan offices; offices elected by district; two or more candidates of one party (top-two, open
    primaries, ranked choice with several of a party); no candidate of either major party; an independent or minor-party
    candidate who won 20% or more before or polls 25% or more (the party baselines do not describe that vote).
  Never a chance for an unopposed race; never 0 or 100 (runs.py stores (wins + 0.5) / (draws + 1)).
"""

import argparse
import datetime as dt
import json
import math
import os
import re
import sqlite3
import sys
import time
from collections import defaultdict

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from election.model import DB, load_json, save_json, sha_file  # noqa: E402
from election.model import data_us as U  # noqa: E402
from election.model import runs as R  # noqa: E402

METHOD = "us-pre-1.2"          # 1.1 (2026-10-10): several minor names beside one big party take the ordinary minor prior;
                               # 1.2 (2026-10-10): the likely margin of the top two kept with every race (no number changes)
BT_METHOD = "us-backtest-1.1"  # 1.1: the same, and the measures also stored under the Minnesota backtest's names
DRAWS = 2000
BT_DRAWS = 1000
ELECTION_DAY = dt.date(2026, 11, 3)
POLLS_US = os.path.join(HERE, "ballot", "polls", "polls_2026.json")
POLLS_STATE = os.path.join(HERE, "ballot", "polls", "polls_{c}_state_2026.json")
LEFT_OUT_FILE = os.path.join(U.CACHE, "left_out.json")
SKIP = ("MN",)                         # Minnesota is forecast at every level by forecast.py
A_INC = 0.08                           # log-odds (about 2 points): a sitting member's edge taken out of an old House result
                                       # before it is read as the district's lean (a fixed prior, the same in the backtest)

GRID_X0, GRID_DX, GRID_N = -3.0, 0.025, 241        # forecast.py's grid (its interp and inverse read these constants)

PRIORS = {
    "env_systematic_sd": 0.10,     # log-odds: other states' Senate polls standing in for a state's own environment
    "env_no_polls_sd": 0.16,       # log-odds (about 4 points): the environment with too few member polls
    "poll_house_sd": 0.05,         # log-odds: a poll's house and method error beyond sampling
    "poll_bias_sd": 0.08,          # log-odds (about 2 points): an error every poll of a race shares (a prior)
    "poll_drift_per_sqrt_day": 0.0085,
    "poll_recent_days": 120,
    "turnout_sd": 0.08,            # log of the turnout factor against 2022
    "race_votes_sd": 0.05,
    "pos_partisan": [0.0, 0.0],    # ballot position: not modelled outside Minnesota (no state's rotation is on file)
    "pos_nonpartisan": [0.0, 0.0],
    "endorse_beta": [0.0, 0.0],    # endorsements: not modelled outside Minnesota
    "third_won": 0.20,             # a non-major candidate who won this share before is a main contender: left out
    "third_polled": 0.25,          # or who polls this share in a member poll
    "cover_min": 0.80,             # MEDSL's precincts placed in districts must hold this share of a contest's votes
}
DEFAULT_PARAMS = {
    "fitted": False, "source": "defaults: no backtest on file",
    "state_sd": 0.10, "office_sd": {"ussen": 0.12, "governor": 0.16, "other": 0.10}, "inc_sw": [0.06, 0.03],
    "lean": {"w_pres": 0.7},
    "gap": {"usrep": [0.0, 0.06]}, "inc": [0.08, 0.04], "district_sd": {"usrep": 0.12}, "region_sd": 0.0,
    "minor": {"with_majors": [-3.2, 0.9, 0.15], "sole": [-1.7, 0.6, 0.35], "statewide": [-3.6, 0.9, 0.10]},
    "writein": {"partisan": 0.002, "partisan_sole": 0.01, "np": 0.006},
    "np": {"beta_inc": [0.0, 0.0], "tau": {}},
    "widen": {"ussen": 1.0, "governor": 1.0, "other": 1.0, "house": 1.0},
}
TESTED = {
    "ussen": "tested on the U.S. Senate races of 2022 and 2024 in every state but Minnesota",
    "governor": "tested on the governors' races of 2022 and 2024 (MEDSL's copies of the official results, a secondary source)",
    "other": "tested on the other statewide offices of 2022 and 2024 (MEDSL's copies of the official results, a secondary source)",
    "usrep": ("tested on the 2024 U.S. House races of states whose lines did not change in 2024 (every state drew new lines "
              "for 2022, so 2022 cannot be tested)"),
}
CLASS_OF_KIND = {"us_senate": "ussen", "us_house": "usrep", "governor": "governor"}
OFFICE_WORDS = {"ussen": "U.S. Senate", "governor": "governor", "other": "other statewide offices", "usrep": "U.S. House"}


def say_default(*a):
    print(*a, flush=True)


def r6(x):
    return None if x is None else float(f"{x:.6g}")


def logit(p):
    return U.logit(p)


def expit(x):
    return U.expit(x)


def make_grid(lean):
    """A district's share as a function of the state's shift x (log-odds): expit(x + lean), on forecast.py's grid."""
    return [r6(expit(GRID_X0 + k * GRID_DX + lean)) for k in range(GRID_N)]


def my_code_sha():
    """SHA-256 of this file and data_us.py: what built the frames (the simulation's own code is kept by runs.py)."""
    here = os.path.dirname(os.path.abspath(__file__))
    files = {n: open(os.path.join(here, n), "rb").read().decode("utf-8") for n in ("data_us.py", "other_states.py")}
    return R.sha_text(R.canonical({"files": files}))


def choice_key(name):
    from election import store
    return store.slug(name)


# ============================================================================================== polls

def load_polls(code):
    """{race id: [member polls]} for a state's races: the Senate file and the state's own file, members only."""
    out = defaultdict(list)
    us = load_json(POLLS_US)["races"]
    for rid, rec in us.items():
        if rid.split("-")[1] == code:
            out[rid] += [p for p in rec.get("polls") or [] if p.get("member") and p.get("end")]
    path = POLLS_STATE.format(c=code.lower())
    if os.path.exists(path):
        for rid, rec in load_json(path)["races"].items():
            out[rid] += [p for p in rec.get("polls") or [] if p.get("member") and p.get("end")]
    return dict(out)


def poll_two_party(poll, cands, nominees_only=True):
    """A poll's Democratic share of the two-party vote, read against a race's candidates, or None when it lacks one of the
    two (or, with nominees_only, names someone not on November's list)."""
    d = r = 0.0
    for name, share in (poll.get("shares") or {}).items():
        c = next((c for c in cands if U.same_person(c["name"], name)), None)
        if c is None:
            if nominees_only:
                return None
            continue
        if c["p"] == "D":
            d += share
        elif c["p"] == "R":
            r += share
    return d / (d + r) if d > 0 and r > 0 else None


def poll_sd(poll, share, pri):
    n = max(int(poll.get("n") or 600), 100)
    days = max((ELECTION_DAY - dt.date.fromisoformat(poll["end"])).days, 0)
    sampling = 1.0 / math.sqrt(n * share * (1 - share))
    return math.sqrt(sampling ** 2 + pri["poll_house_sd"] ** 2 + (pri["poll_drift_per_sqrt_day"] ** 2) * days)


def senate_candidates():
    """{race id: [{"name", "p"}]} of every 2026 Senate race's candidates on any list (general, primaries), for reading polls
    taken before the primaries."""
    con = sqlite3.connect(f"file:{U.FED_DB}?mode=ro", uri=True)
    out = defaultdict(list)
    for rid, name, party, pcode in con.execute("SELECT race_id, name, party, party_code FROM candidates WHERE race_id LIKE '2026-__-S%'"):
        out[rid].append({"name": name, "p": U.side(pcode or party)})
    con.close()
    return out


def senate_shifts(as_of, pres24):
    """[(race id, state, polls used, shift)]: in each Senate race with member polls, how far the Democratic share of the
    two-party vote runs from Harris's 2024 share in that state (log-odds), from the latest poll of each pollster (at most
    five), ended within poll_recent_days of the run."""
    as_day = as_of.date() if isinstance(as_of, dt.datetime) else as_of
    cands = senate_candidates()
    out = []
    for rid, rec in sorted(load_json(POLLS_US)["races"].items()):
        st = rid.split("-")[1]
        if st not in pres24:
            continue
        vals = []
        for p in rec.get("polls") or []:
            if not p.get("member") or not p.get("end"):
                continue
            end = dt.date.fromisoformat(p["end"])
            if end > as_day or (as_day - end).days > PRIORS["poll_recent_days"]:
                continue
            tp = poll_two_party(p, cands.get(rid, []), nominees_only=False)
            if tp is not None:
                vals.append((end, logit(tp), p["pollster"]))
        latest = {}
        for end, x, who in sorted(vals, reverse=True):
            latest.setdefault(who, (end, x))
        xs = [x for _e, x in sorted(latest.values(), reverse=True)[:5]]
        if not xs:
            continue
        d, r, _a = pres24[st]
        out.append((rid, st, len(xs), sum(xs) / len(xs) - logit(d / (d + r))))
    return out


def national_shift(shifts, exclude=None):
    """(mean, variance, states used, plain words) of the national environment from the other states' Senate polls."""
    vals = [s for _rid, st, _n, s in shifts if st != exclude]
    if len(vals) >= 3:
        mean = sum(vals) / len(vals)
        sd = math.sqrt(sum((v - mean) ** 2 for v in vals) / (len(vals) - 1))
        var = sd ** 2 / len(vals) + PRIORS["env_systematic_sd"] ** 2
        pts = (expit(mean) - 0.5) * 100
        words = (f"In {len(vals)} other states, U.S. Senate polls by members of AAPOR's Transparency Initiative have Democrats "
                 f"running {abs(pts):.1f} points {'ahead of' if pts >= 0 else 'behind'} Kamala Harris's 2024 share of the "
                 f"two-party vote")
        return mean, var, len(vals), words
    return 0.0, PRIORS["env_no_polls_sd"] ** 2, len(vals), ("too few recent member polls of other states' Senate races: the "
                                                            "state's 2024 presidential result, widened")


# ============================================================================================== the environment

def environment(base_logit, shift, shift_var, params, stat_races, polls=None, pri=PRIORS):
    """The shared Gaussian over [G, each statewide race's offset]: mean, covariance, and the member polls used. A poll of a
    race is y = G + offset + error (forecast.py's update)."""
    theta = ["G"] + [r["race"] for r in stat_races]
    n = len(theta)
    m = [base_logit + shift] + [0.0] * (n - 1)
    P = [[0.0] * n for _ in range(n)]
    P[0][0] = shift_var + params["state_sd"] ** 2
    inc_m, inc_s = params["inc_sw"]
    for k, r in enumerate(stat_races, 1):
        sd = params["office_sd"].get(r["class"], params["office_sd"]["other"])
        inc_dir = r.get("inc_dir", 0)
        if r["class"] == "ussen" and inc_dir:
            m[k] = inc_m * inc_dir
            P[k][k] = sd ** 2 + inc_s ** 2
        else:
            P[k][k] = sd ** 2
    used = []
    for k, r in enumerate(stat_races, 1):
        latest = {}
        for p in sorted((polls or {}).get(r["race"], []), key=lambda p: p["end"], reverse=True):
            tp = poll_two_party(p, r["cands"])
            if tp is None:
                used.append({"race": r["race"], "pollster": p["pollster"], "ended": p["end"], "used": False,
                             "why": "the poll's names are not both November's candidates of the two big parties"})
                continue
            if p["pollster"] in latest or len(latest) >= 5:
                used.append({"race": r["race"], "pollster": p["pollster"], "ended": p["end"], "used": False,
                             "why": "an older poll by the same pollster, or more than five pollsters (the latest of up to five count)"})
                continue
            latest[p["pollster"]] = (p, tp)
        if not latest:
            continue
        # the polls of a race as one reading: their average, with each poll's own error shrunk by their number and an error
        # all of them share (polls of one race tend to miss together)
        ys = [logit(tp) for _p, tp in latest.values()]
        ss = [poll_sd(p, tp, pri) for p, tp in latest.values()]
        y = sum(ys) / len(ys)
        s = math.sqrt(sum(x * x for x in ss) / len(ss) / len(ss) + pri["poll_bias_sd"] ** 2)
        for p, tp in latest.values():
            used.append({"race": r["race"], "pollster": p["pollster"], "ended": p["end"], "used": True, "two_party": round(tp, 4)})
        # y = G + the race's offset + error: a Gaussian update of the whole vector (forecast.py's)
        PH = [P[i][0] + P[i][k] for i in range(n)]
        S = PH[0] + PH[k] + s * s
        K = [x / S for x in PH]
        innov = y - (m[0] + m[k])
        m = [m[i] + K[i] * innov for i in range(n)]
        P = [[P[i][j] - K[i] * PH[j] for j in range(n)] for i in range(n)]
    return {"theta": theta, "mean": [r6(x) for x in m], "cov": [[r6(x) for x in row] for row in P]}, used


# ============================================================================================== a frame

def make_frame(code, entries, env, params, as_of, method, public=None, report=None):
    """A frame in forecast.simulate's shape. entries: [{"race", "class", "cands": [{"key", "name", "p", "inc"}], "k" or
    "lean", "votes", "tested"} or {"race", "status": "unopposed", "cands"}]."""
    races = []
    for e in entries:
        if e.get("status") == "unopposed":
            races.append({"race": e["race"], "status": "unopposed", "seats": 1,
                          "cands": [{"key": c["key"], "name": c["name"], "p": c["p"]} for c in e["cands"]]})
            continue
        r = {"race": e["race"], "status": "pre", "kind": "partisan", "class": e["class"], "seats": 1, "units": None,
             "votes": r6(e.get("votes")), "rot": None, "tested": e.get("tested"),
             "cands": [{"key": c["key"], "name": c["name"], "p": c["p"], "inc": c.get("inc", 0)} for c in e["cands"]]}
        if e["class"] == "usrep":
            r["f"] = make_grid(e["lean"])
            r["region"] = None
        else:
            r["k"] = e["k"]
        races.append(r)
    days = max((ELECTION_DAY - (as_of.date() if isinstance(as_of, dt.datetime) else as_of)).days, 0) if as_of else 0
    frame = {"v": 1, "state": code, "method": method, "as_of": R.iso(as_of) if isinstance(as_of, dt.datetime) else str(as_of),
             "election": ELECTION_DAY.isoformat(), "days_to_election": days, "params": params, "priors": PRIORS,
             "env": env, "grid": {"x0": GRID_X0, "dx": GRID_DX, "n": GRID_N},
             "state_grid": make_grid(0.0), "races": races, "public": public or {}, "report": report or {}}
    return json.loads(R.canonical(frame))


def simulate(frame, seed, draws):
    from election.model import forecast as F
    return F.simulate(frame, seed, draws)


# ============================================================================================== the 2026 races of a state

def strong_third(code, race, polls):
    """(name, words) when a candidate outside the two big parties won PRIORS["third_won"] or more of a statewide or
    district contest in 2022 or 2024, or polls PRIORS["third_polled"] or more in a member poll of this race."""
    others = [c for c in race["cands"] if c["p"] == "O"]
    if not others:
        return None
    for c in others:
        for p in polls.get(race["race"], []):
            tot = sum(p.get("shares", {}).values()) or 100
            for name, share in (p.get("shares") or {}).items():
                if U.same_person(c["name"], name) and share / max(tot, 100) >= PRIORS["third_polled"]:
                    return c["name"], f"{share:g}% in a poll by {p['pollster']} ending {p['end']}"
        for y in (2022, 2024):
            ck = U.clerk(y)["states"].get(code, {})
            contests = [s["cands"] for s in ck.get("senate", [])] + [h["cands"] for h in ck.get("house", {}).values()]
            for cs in contests:
                tot = sum(v or 0 for _n, _p, v in cs)
                for n, _p, v in cs:
                    if v and tot and U.same_person(c["name"], n) and v / tot >= PRIORS["third_won"]:
                        return c["name"], f"{v / tot * 100:.0f}% in {y}"
            doc = U.medsl(y, code, say=lambda *a: None)
            for key, ct in (doc or {}).get("contests", {}).items():
                tot = sum(v for _n, _p, v in ct["cands"])
                for n, _p, v in ct["cands"]:
                    if tot and U.same_person(c["name"], n) and v / tot >= PRIORS["third_won"]:
                        return c["name"], f"{v / tot * 100:.0f}% in {y}"
    return None


def house_leans_2026(code, params, say=say_default):
    """{district: (lean, how)} for a state's districts on the lines of 2024, from 2024's presidential vote placed in
    districts (MEDSL) and 2024's House results (the Clerk)."""
    pres = U.president(2024)[code]
    p24 = pres[0] / (pres[0] + pres[1])
    out = {}
    if code in U.AT_LARGE:
        return {0: (0.0, "an at-large seat: the district is the state")}
    doc = U.medsl(2024, code, say) if U.medsl_reliable(2024, code, say)[0] else None
    b = {}
    if doc:
        key = next((k for k in doc["by_cd"] if k.startswith("US PRESIDENT|")), None)
        if key and doc["cd_cover"].get(key, 0) >= PRIORS["cover_min"]:
            by = doc["by_cd"][key]
            sd_ = sum(v[0] for v in by.values())
            sr_ = sum(v[1] for v in by.values())
            st = sd_ / (sd_ + sr_)
            for dkey, (d, r, _t) in by.items():
                if d > 0 and r > 0:
                    b[int(dkey)] = logit(d / (d + r)) - logit(st)
    a = {}
    members = U.members_on(U.ELECTION_DAY[2024], "House")
    for dkey, h in U.clerk(2024)["states"][code]["house"].items():
        if not str(dkey).isdigit():
            continue
        d, r, _t, contested = U.two_party(h["cands"])
        if not contested:
            continue
        inc_dir = 0
        for n, p, _v in h["cands"]:
            if U.sitting(n, code, members):
                inc_dir += 1 if U.side(p) == "D" else -1 if U.side(p) == "R" else 0
        a[int(dkey)] = logit(d / (d + r)) - logit(p24) - A_INC * inc_dir
    w = params["lean"]["w_pres"]
    for dist in set(a) | set(b):
        if dist in a and dist in b:
            out[dist] = (w * b[dist] + (1 - w) * a[dist], "2024 presidential vote in the district and its 2024 House race")
        elif dist in b:
            out[dist] = (b[dist], "2024 presidential vote in the district (the 2024 House race was not between the two big parties)")
        else:
            out[dist] = (a[dist], "its 2024 House race (the presidential vote could not be placed in districts)")
    return out


def expected_votes(code):
    """(statewide, {district: votes}): the state's 2022 turnout in its top race, and each district's 2022 House votes."""
    ck = U.clerk(2022)["states"].get(code, {})
    sw = None
    sen = [s for s in ck.get("senate", []) if s["cands"]]
    if sen:
        sw = max(sum(v or 0 for _n, _p, v in s["cands"]) for s in sen)
    else:
        doc = U.medsl(2022, code, say=lambda *a: None)
        gov = [c for k, c in (doc or {}).get("contests", {}).items() if c["class"] == "governor"]
        if gov:
            sw = sum(v for _n, _p, v in gov[0]["cands"])
    dist = {}
    for dkey, h in ck.get("house", {}).items():
        if str(dkey).isdigit() and not h["unopposed"]:
            dist[int(dkey)] = sum(v or 0 for _n, _p, v in h["cands"])
    if sw is None and dist:
        sw = sum(dist.values())
    return sw, dist


def decision_rule(code, cls):
    """The rule that decides a class of race in a state, from the state's registry file (plurality, majority_runoff,
    ranked_choice, top_two, open_primary). A rule applies to the Senate when its words name the Senate, federal offices,
    Congress or every office; to the House likewise; to a state office when they name state offices."""
    path = os.path.join(HERE, "election", "registry", f"{code.lower()}.json")
    if not os.path.exists(path):
        return "plurality"
    dec = load_json(path).get("decision") or {}
    rule = dec.get("default") or "plurality"
    want = {"ussen": ("senate", "federal", "congress", "every"), "usrep": ("house", "federal", "congress", "every")}.get(
        cls, ("state", "every"))
    for rr in dec.get("rules") or []:
        ap = (rr.get("applies") or "").lower()
        if cls in ("ussen", "usrep") and "u.s." in ap and not any(w in ap for w in want[:1] + want[2:]):
            continue                                # "U.S. House ..." does not apply to the Senate, and so on
        if any(w in ap for w in want) and not (cls not in ("ussen", "usrep") and ("u.s." in ap and "state" not in ap)):
            rule = rr.get("rule") or rule
    return rule


def plan_state(code, params, as_of, say=say_default):
    """Every 2026 race of a state sorted into forecast, unopposed or left out. Returns (entries, stat_races, left, rules,
    report)."""
    races = U.races_2026(code)
    polls = load_polls(code)
    changed = U.lines_changed_2026()
    leans = None
    sw_votes, d_votes = expected_votes(code)
    members26 = None
    entries, stat, left, rules = [], [], {}, {}
    counts = defaultdict(int)
    for race in races:
        rid = race["race"]
        cands = race["cands"]

        def out(why, tag):
            left[rid] = why
            counts[f"left out: {tag}"] += 1
        if not race["listed"]:
            if race["office_kind"] == "lieutenant_governor":
                out("Elected on one ticket with the governor, or nominated by each party for that ticket; the November list "
                    "for it is not on file on its own.", "ticket")
            else:
                out("The state's November candidate list for this race is not on file yet, so there is nothing to forecast.",
                    "no list")
            continue
        if not cands:
            out("No candidate's name is printed on the November ballot for this race.", "no names")
            continue
        if race["seats"] > 1:
            out("Several seats are filled from one list; the model forecasts single-seat races only.", "several seats")
            continue
        if not race["partisan"] or all(c["p"] == "O" and str(c["party"] or "").lower().startswith(("nonpartisan", "non-partisan"))
                                       for c in cands):
            out("A nonpartisan office: the model is built on party results and has not been tested on nonpartisan races.",
                "nonpartisan")
            continue
        if race["level"] == "statewide" and not race["statewide"]:
            out("Elected by the voters of one district, and the model has no tested past results for these districts.", "district office")
            continue
        if len(cands) <= race["seats"]:
            entries.append({"race": rid, "status": "unopposed", "cands": [{"key": choice_key(c["name"]), "name": c["name"], "p": c["p"]}
                                                                         for c in cands]})
            counts["unopposed"] += 1
            continue
        if race["office_kind"] == "us_house" and changed.get(code, (False,))[0]:
            out("The state drew new congressional lines for 2026, and no official or labelled secondary source on file gives "
                "past results on the new lines, so the model has nothing to start this district from.", "new lines")
            continue
        nd = sum(1 for c in cands if c["p"] == "D")
        nr = sum(1 for c in cands if c["p"] == "R")
        if nd > 1 or nr > 1:
            out("Two or more candidates of one party share the ballot; past party results cannot split that party's vote "
                "among them.", "several of a party")
            continue
        if nd + nr == 0:
            out("No candidate of either major party is on the ballot; the model's past results are party results.", "no major party")
            continue
        third = strong_third(code, race, polls)
        if third:
            out(f"A candidate outside the two big parties is a main contender here ({third[1]}); the model's party baselines "
                f"do not describe that candidate's vote.", "strong third candidate")
            continue
        cls = "ussen" if race["office_kind"] == "us_senate" else "usrep" if race["office_kind"] == "us_house" else \
            "governor" if race["office_kind"] == "governor" else "other"
        ec = [{"key": choice_key(c["name"]), "name": c["name"], "p": c["p"], "inc": c.get("inc", 0)} for c in cands]
        inc_dir = sum((1 if c["p"] == "D" else -1 if c["p"] == "R" else 0) * c.get("inc", 0) for c in ec)
        e = {"race": rid, "class": cls, "cands": ec, "tested": TESTED[cls]}
        if cls == "usrep":
            if leans is None:
                leans = house_leans_2026(code, params, say)
            dist = int(race["district"] or 0)
            if dist not in leans:
                out("No past result on file describes this district.", "no past result")
                continue
            e["lean"] = r6(leans[dist][0])
            e["lean_how"] = leans[dist][1]
            e["votes"] = d_votes.get(dist)
        else:
            e["votes"] = sw_votes
            e["inc_dir"] = inc_dir if cls == "ussen" else 0
            stat.append(e)
        if nd + nr == 1:
            e["one_major"] = True
        entries.append(e)
        counts[f"forecast {cls}"] += 1
        rule = decision_rule(code, cls)
        if rule == "majority_runoff":
            rules[rid] = ("A candidate needs more than half the votes; if no one has it, the top two meet in a runoff. The chance "
                          "shown is of finishing first in the count.")
        elif rule == "ranked_choice":
            rules[rid] = ("Voters rank the candidates. The chance shown is of leading the count once the later choices are added, "
                          "taken as following the two big parties' split; the shares are of first choices.")
    for e in stat:
        e["k"] = stat.index(e) + 1
    report = {"counts": dict(counts), "races": len(races)}
    return entries, stat, left, rules, report, polls


def public_words(code, env, base_p, shift_words, params, params_run, used_polls, counts, left, rules):
    g = expit(env["mean"][0])
    g_sd = math.sqrt(env["cov"][0][0]) * 0.25 * 100
    name = U.NAME_OF.get(code, code)
    inc = params["inc"][0] * 0.25 * 100
    inc_sw = params["inc_sw"][0] * 0.25 * 100
    if params_run:
        d = params_run.split("-")[-1][:8] if re.search(r"\d{8}T", params_run) else None
        stamp = re.search(r"(\d{4})(\d{2})(\d{2})T", params_run)
        when = dt.date(int(stamp.group(1)), int(stamp.group(2)), int(stamp.group(3))) if stamp else None
        bt = f"Sized by the backtests run on {when:%B} {when.day}, {when.year}." if when else "Sized by the backtests."
    else:
        bt = "Not yet sized by a backtest: the spreads are the method's starting assumptions."
    return {
        "environment": (f"{shift_words}. Applied to {name}'s 2024 presidential result ({base_p * 100:.1f}% Democratic of the "
                        f"two-party vote) and moved a little by {name}'s own member polls, a generic 2026 contest in {name} stands "
                        f"near {g * 100:.1f}% Democratic, give or take about {g_sd:.1f} points."),
        "polls": used_polls,
        "statewide": (f"Statewide races: the state's generic contest plus the office's own pull, sized on the 2022 and 2024 "
                      f"results of every state; a sitting U.S. senator's edge is about {inc_sw:.1f} points. For the other "
                      f"offices the record on file does not say who held the seat in past years, so no holder's edge is "
                      f"added and the spread is wider instead."),
        "house": (f"U.S. House: each district's lean is how its precincts voted for President in 2024 against the state (MEDSL's "
                  f"copy of the official returns, a secondary source, placed in districts precinct by precinct), blended with "
                  f"how its 2024 House race went against the top of the ticket; then a sitting member's edge (about {inc:.1f} "
                  f"points) and the district's own error, each sized on the 2024 House races."),
        "minor": ("Candidates outside the two big parties: shares drawn from what such candidates won in 2022 and 2024. Where "
                  "three or more of them run, their total is likely overstated by a point or two, and the two big parties' "
                  "shares understated by as much."),
        "not_used": ("Campaign money, Census figures and ballot position are not used before Election Day: none has been "
                     "tested on past races here yet."),
        "backtest": bt,
        "rules": rules,
        "left_out": left,
        "sources": [
            {"what": "2020, 2022 and 2024 votes for President, Senate and House", "by": "the Clerk of the U.S. House", "kind": "official"},
            {"what": "2022 and 2024 votes for governor and the other statewide offices, and the 2024 presidential vote by "
                     "district and county", "by": "the MIT Election Data and Science Lab's copies of the states' official "
                     "returns (public domain)", "kind": "secondary"},
            {"what": "polls", "by": "members of AAPOR's Transparency Initiative only", "kind": "poll"},
            {"what": "the 2026 candidates", "by": "each state's official candidate list", "kind": "official"},
        ],
        "races": {"forecast": sum(v for k, v in counts.items() if k.startswith("forecast")), "unopposed": counts.get("unopposed", 0),
                  "left_out": len(left)},
    }


def build_frame(code, as_of, params=None, params_run=None, say=say_default):
    """Every input of a state's pre-election run, self-contained. Returns (frame, inputs, left out)."""
    if params is None:
        params, params_run = latest_params()
    pres24 = U.president(2024)
    d, r, _a = pres24[code]
    base_p = d / (d + r)
    shifts = senate_shifts(as_of, pres24)
    mean, var, n_states, words = national_shift(shifts, exclude=code)
    entries, stat, left, rules, report, polls = plan_state(code, params, as_of, say)
    env, used = environment(logit(base_p), mean, var, params, stat, polls)
    env["state_2024"] = r6(base_p)
    env["shift"] = r6(mean)
    env["shift_states"] = n_states
    public = public_words(code, env, base_p, words, params, params_run, used, report["counts"], left, rules)
    report["shifts"] = [[rid, n, r6(s)] for rid, _st, n, s in shifts]
    report["leans"] = {e["race"]: [e["lean"], e["lean_how"]] for e in entries if e.get("lean") is not None}
    frame = make_frame(code, entries, env, params, as_of, METHOD, public, report)
    sha = lambda p: sha_file(p) if os.path.exists(p) else None  # noqa: E731
    inputs = [
        {"input": "params", "source": f"backtest run {params_run}" if params_run else "defaults (no backtest on file)",
         "sha256": R.sha_text(R.canonical(params)), "as_of": None, "kind": "derived" if params_run else "prior", "note": params.get("source")},
        {"input": "clerk-2024", "source": U.CLERK_URL.format(y=2024), "sha256": sha(U.CLERK_PDF[2024]), "as_of": "2024-11-05",
         "kind": "official", "note": "every state's 2024 votes for President and House"},
        {"input": "clerk-2022", "source": U.CLERK_URL.format(y=2022), "sha256": sha(U.CLERK_PDF[2022]), "as_of": "2022-11-08",
         "kind": "official", "note": "2022 votes: the expected turnout, and who ran before"},
        {"input": f"medsl-2024-{code.lower()}", "source": U.medsl_url(2024, code),
         "sha256": sha(U.cache_path("medsl", "2024", os.path.basename(U.medsl_url(2024, code)))), "as_of": "2024-11-05",
         "kind": "secondary", "note": "MIT Election Data and Science Lab (CC0): the 2024 presidential vote placed in districts"},
        {"input": "ballot-congress", "source": U.FED_DB, "sha256": sha(U.FED_DB), "as_of": None, "kind": "official",
         "note": "the 2026 races for Congress (read only)"},
        {"input": "ballot-local", "source": U.LOCAL_DB, "sha256": sha(U.LOCAL_DB), "as_of": None, "kind": "official",
         "note": "the 2026 statewide races (read only)"},
        {"input": "polls-us", "source": POLLS_US, "sha256": sha(POLLS_US), "as_of": None, "kind": "poll",
         "note": "members of AAPOR's Transparency Initiative only"},
        {"input": "frame-builder", "source": "election/model/other_states.py and data_us.py", "sha256": my_code_sha(), "as_of": None,
         "kind": "derived", "note": "the code that built the frame (the simulation's code is kept by runs.py)"},
    ]
    ps = POLLS_STATE.format(c=code.lower())
    if os.path.exists(ps):
        inputs.append({"input": f"polls-{code.lower()}", "source": ps, "sha256": sha(ps), "as_of": None, "kind": "poll",
                       "note": "members of AAPOR's Transparency Initiative only"})
    return frame, inputs, left


def latest_params(db=DB):
    """The newest backtest's fitted parameters (state "US", this method), or DEFAULT_PARAMS."""
    if not os.path.exists(db):
        return dict(DEFAULT_PARAMS), None
    con = R.connect(db)
    try:
        row = con.execute("SELECT run, frame_sha FROM runs WHERE state = 'US' AND kind = 'backtest' AND method LIKE 'us-backtest-%' "
                          "AND ended IS NOT NULL ORDER BY started DESC, run DESC LIMIT 1").fetchone()
        if not row:
            return dict(DEFAULT_PARAMS), None
        doc = R.get_blob(con, row[1]) or {}
        return (doc.get("params") or dict(DEFAULT_PARAMS)), row[0]
    finally:
        con.close()


# ============================================================================================== a run

def run_pre(codes=None, now=None, say=say_default, db=DB, draws=DRAWS, rehearsal=False, dry=False):
    """One pre-election run for each state (every state but Minnesota by default), stored as a version through runs.py.
    The left-out list is written to election_cache/model/us/left_out.json. Returns {code: summary}."""
    started = R.now_utc()
    as_of = now or started
    if isinstance(as_of, dt.datetime) and as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=dt.timezone.utc)
    if as_of.date() < dt.date(2026, 1, 1) or as_of.date() > ELECTION_DAY:
        say(f"    no pre-election run: the clock says {as_of.date()}, outside 2026 before Election Day (a replayed night)")
        return {"skipped": "clock outside 2026 before Election Day"}
    params, params_run = latest_params(db)
    codes = [c.upper() for c in (codes or U.CODES) if c.upper() not in SKIP]
    res, all_left = {}, load_json(LEFT_OUT_FILE) if os.path.exists(LEFT_OUT_FILE) else {"states": {}}
    for code in codes:
        t0 = time.time()
        frame, inputs, left = build_frame(code, as_of, params, params_run, say)
        all_left["states"][code] = {"t": R.iso(as_of), "left_out": left, "counts": frame["report"]["counts"]}
        if not frame["races"]:
            say(f"    {code}: nothing to forecast ({len(left)} races left out)")
            res[code] = {"races": 0, "left_out": len(left)}
            continue
        con = R.connect(db)
        try:
            run = R.new_run_id(con, "pre", code, started)
            seed = R.seed_of(run)
            out = simulate(frame, seed, draws)
            if dry:
                res[code] = {"run": run, "out": out, "frame": frame}
                say(f"    {code} dry run: {len(out['races'])} races ({frame['report']['counts']})")
                continue
            with con:
                rec = R.record_run(con, run=run, state=code, kind="pre", method=METHOD, seed=seed, draws=draws, started=started,
                                   as_of=as_of, frame=frame, outputs=out, inputs=inputs, rehearsal=rehearsal,
                                   note=f"pre-election forecast, other states; parameters from {params_run or 'defaults'}")
            res[code] = {"run": run, **rec, "left_out": len(left), "seconds": round(time.time() - t0, 1)}
            say(f"    {code} run {run}: {rec['races']} races, {rec['written']} with new rows, {len(left)} left out, "
                f"{time.time() - t0:.1f} s")
        finally:
            con.close()
    if not dry:
        all_left["written"] = R.iso(R.now_utc())
        all_left["method"] = METHOD
        save_json(LEFT_OUT_FILE, all_left)
    return res


def left_out(code):
    """{race id: the reason, in plain words} for the races of a state with no forecast (from the newest run's planning)."""
    if not os.path.exists(LEFT_OUT_FILE):
        return {}
    return (load_json(LEFT_OUT_FILE)["states"].get(code.upper()) or {}).get("left_out", {})


# ============================================================================================== the backtest

def past_statewide(year, members_sen, say=say_default):
    """Every contested statewide race of a past year outside Minnesota: [{"id", "state", "class", "cands", "inc_dir",
    "actual" (Democratic share of all votes), "d2p", "won" (the Democrat led), "last" (the 2020 presidential winner's
    party was the Democrats)}]."""
    p20 = U.president(2020)
    out = []
    for code in U.CODES:
        if code in SKIP or code not in p20:
            continue
        for c in U.statewide_contests(year, code, say):
            cs = [x for x in c["cands"] if x[2]]
            d, r, tot, contested = U.two_party(cs)
            if not contested or tot <= 0:
                continue
            inc_dir = 0
            if c["class"] == "ussen":
                for n, p, _v in cs:
                    if U.sitting(n, code, members_sen):
                        inc_dir += 1 if U.side(p) == "D" else -1 if U.side(p) == "R" else 0
            best_other = max([v for _n, p, v in cs if U.side(p) != "D"] or [0])
            out.append({"id": f"{year}-{code}-{c['class']}-{re.sub(r'[^a-z0-9]+', '-', c['key'].lower()).strip('-')}",
                        "state": code, "class": c["class"], "year": year,
                        "cands": [{"key": U.side(p) if U.side(p) != "O" else f"o{k}", "name": n, "p": U.side(p),
                                   "inc": 0} for k, (n, p, _v) in enumerate(cs)],
                        "shares": {U.side(p) if U.side(p) != "O" else f"o{k}": v / tot for k, (n, p, v) in enumerate(cs)},
                        "inc_dir": inc_dir, "d2p": d / (d + r), "won": 1 if d > best_other else 0,
                        "base20": p20[code][0] / (p20[code][0] + p20[code][1]), "kind": c["kind"]})
    return out


def past_house_2024(params, say=say_default):
    """The 2024 House races of states whose lines did not change in 2024, each with its lean from 2022 (the district's
    2022 statewide votes placed by MEDSL, and its 2022 House race). Leans are rebuilt with the parameters given."""
    p24 = U.president(2024)
    p20 = U.president(2020)
    m22 = U.members_on(U.ELECTION_DAY[2022], "House")
    m24 = U.members_on(U.ELECTION_DAY[2024], "House")
    out, skipped = [], defaultdict(int)
    for code in U.CODES:
        if code in SKIP:
            continue
        if code in U.LINES_CHANGED_2024:
            skipped["lines changed in 2024"] += len(U.clerk(2024)["states"][code]["house"])
            continue
        doc = U.medsl(2022, code, say) if U.medsl_reliable(2022, code, say)[0] else None
        tops = []
        if doc:
            for key, c in doc["contests"].items():
                if c["class"] in ("governor", "ussen") and key.endswith("regular") and U.two_party(c["cands"])[3]:
                    tops.append(key)
        t22 = None
        if tops:
            vals = []
            for key in tops:
                d, r, _t, _c = U.two_party(doc["contests"][key]["cands"])
                vals.append(logit(d / (d + r)))
            t22 = sum(vals) / len(vals)
        bmap = defaultdict(list)
        for key in tops:
            if doc["cd_cover"].get(key, 0) < PRIORS["cover_min"]:
                continue
            by = doc["by_cd"][key]
            sd_ = sum(v[0] for v in by.values())
            sr_ = sum(v[1] for v in by.values())
            st = sd_ / (sd_ + sr_)
            for dkey, (d, r, _t) in by.items():
                if d > 0 and r > 0:
                    bmap[int(dkey)].append(logit(d / (d + r)) - logit(st))
        h22 = U.clerk(2022)["states"][code]["house"]
        for dkey, h in U.clerk(2024)["states"][code]["house"].items():
            if not str(dkey).isdigit():
                continue
            dist = int(dkey)
            cs = [x for x in h["cands"] if x[2]]
            d, r, tot, contested = U.two_party(cs)
            if not contested:
                skipped["2024 race not between one Democrat and one Republican"] += 1
                continue
            inc_dir = sum((1 if U.side(p) == "D" else -1 if U.side(p) == "R" else 0) for n, p, _v in cs if U.sitting(n, code, m24))
            b = (0.0 if code in U.AT_LARGE else (sum(bmap[dist]) / len(bmap[dist]) if bmap.get(dist) else None))
            a = None
            old = h22.get(str(dist))
            if old and t22 is not None:
                d0, r0, _t0, c0 = U.two_party(old["cands"])
                if c0:
                    inc0 = sum((1 if U.side(p) == "D" else -1 if U.side(p) == "R" else 0) for n, p, _v in old["cands"] if U.sitting(n, code, m22))
                    a = logit(d0 / (d0 + r0)) - t22 - A_INC * inc0
            if code in U.AT_LARGE and t22 is not None:
                a = 0.0
            if a is None and b is None:
                skipped["no 2022 result describes the district"] += 1
                continue
            best_other = max([v for _n, p, v in cs if U.side(p) != "D"] or [0])
            out.append({"id": f"2024-{code}-usrep-{dist:02d}", "state": code, "class": "usrep", "year": 2024, "dist": dist,
                        "a": a, "b": b, "inc_dir": inc_dir, "d2p": d / (d + r), "won": 1 if d > best_other else 0,
                        "top24": p24[code][0] / (p24[code][0] + p24[code][1]), "base20": p20[code][0] / (p20[code][0] + p20[code][1]),
                        "last": None if not (old and U.two_party(old["cands"])[3]) else (1 if U.two_party(old["cands"])[0] > U.two_party(old["cands"])[1] else 0),
                        "cands": [{"key": U.side(p) if U.side(p) != "O" else f"o{k}", "name": n, "p": U.side(p),
                                   "inc": 1 if U.sitting(n, code, m24) else 0} for k, (n, p, _v) in enumerate(cs)],
                        "shares": {U.side(p) if U.side(p) != "O" else f"o{k}": v / tot for k, (n, p, v) in enumerate(cs)}})
    return out, dict(skipped)


def lean_of(h, params):
    w = params["lean"]["w_pres"]
    if h["a"] is not None and h["b"] is not None:
        return w * h["b"] + (1 - w) * h["a"]
    return h["b"] if h["b"] is not None else h["a"]


def ols(xs, ys):
    """(intercept, slope) of y on x."""
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx <= 0:
        return my, 0.0
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    return my - b * mx, b


def fit_statewide(races):
    """state_sd, office_sd by class and the Senate holder's edge, from races with their year's national shift known."""
    delta = {}
    for y in {r["year"] for r in races}:
        es = [logit(r["d2p"]) - logit(r["base20"]) for r in races if r["year"] == y]
        delta[y] = sum(es) / len(es)
    e = {r["id"]: logit(r["d2p"]) - logit(r["base20"]) - delta[r["year"]] for r in races}
    sen = [r for r in races if r["class"] == "ussen"]
    xs = [r["inc_dir"] for r in sen]
    ys = [e[r["id"]] for r in sen]
    beta = sum(x * y for x, y in zip(xs, ys)) / max(sum(x * x for x in xs), 1e-9) if any(xs) else 0.0
    nx = sum(1 for x in xs if x)
    res_sd = math.sqrt(sum((y - beta * x) ** 2 for x, y in zip(xs, ys)) / max(len(ys) - 1, 1)) if ys else 0.1
    beta_sd = res_sd / math.sqrt(max(nx, 1))
    ep = {r["id"]: e[r["id"]] - (beta * r["inc_dir"] if r["class"] == "ussen" else 0.0) for r in races}
    groups = defaultdict(list)
    for r in races:
        groups[(r["state"], r["year"])].append(ep[r["id"]])
    prods, n = 0.0, 0
    for vals in groups.values():
        for i in range(len(vals)):
            for j in range(i + 1, len(vals)):
                prods += vals[i] * vals[j]
                n += 1
    state_var = max(prods / n if n else 0.01, 0.03 ** 2)
    office = {}
    for cls in ("ussen", "governor", "other"):
        v = [ep[r["id"]] for r in races if r["class"] == cls]
        tot = sum(x * x for x in v) / max(len(v), 1) if v else 0.02
        office[cls] = math.sqrt(max(tot - state_var, 0.03 ** 2))
    return {"state_sd": math.sqrt(state_var), "office_sd": office, "inc_sw": [beta, beta_sd], "delta": delta,
            "n": {c: sum(1 for r in races if r["class"] == c) for c in ("ussen", "governor", "other")}, "pairs": n}


def fit_house(houses, params):
    """The lean blend, the House's gap to the top of the ticket, a sitting member's edge and the district's own error,
    from 2024's House races against 2024's presidential result in the state."""
    best = None
    for w in [k / 10 for k in range(11)]:
        p = dict(params, lean={"w_pres": w})
        rows = [(h["inc_dir"], logit(h["d2p"]) - logit(h["top24"]) - lean_of(h, p)) for h in houses]
        gap, beta = ols([x for x, _y in rows], [y for _x, y in rows])
        sse = sum((y - gap - beta * x) ** 2 for x, y in rows)
        if best is None or sse < best[0]:
            best = (sse, w, gap, beta, len(rows))
    sse, w, gap, beta, n = best
    sd = math.sqrt(sse / max(n - 3, 1))
    nx = sum(1 for h in houses if h["inc_dir"])
    return {"w_pres": w, "gap": gap, "inc": [beta, sd / math.sqrt(max(nx, 1))], "district_sd": sd, "n": n}


def minor_races():
    """{bucket: [(number of candidates outside the big parties, their share in all, [each one's share])]} for 2022 and
    2024: "with_majors" (a district race beside one Democrat and one Republican), "statewide" (likewise statewide) and
    "sole" (beside only one of the big parties). Write-ins are not candidates here."""
    out = defaultdict(list)

    def add(cs, statewide):
        cs = [x for x in cs if x[2]]
        d, r, tot, contested = U.two_party(cs)
        if not tot:
            return
        majors = sum(1 for _n, p, _v in cs if U.side(p) in ("D", "R"))
        ms = [v / tot for _n, p, v in cs if U.side(p) == "O" and p != "Write-in" and v]
        if not ms:
            return
        bucket = ("statewide" if statewide else "with_majors") if contested else "sole" if majors == 1 else None
        if bucket:
            out[bucket].append((len(ms), sum(ms), ms))
    for y in (2022, 2024):
        for code, st in U.clerk(y)["states"].items():
            for h in st["house"].values():
                add(h["cands"], False)
            for s in st["senate"]:
                if not s.get("footnoted"):
                    add(s["cands"], True)
            if U.medsl_reliable(y, code, say=lambda *a: None)[0]:
                for key, c in (U.medsl(y, code, say=lambda *a: None) or {}).get("contests", {}).items():
                    if c["class"] in ("governor", "other"):
                        add([x for x in c["cands"] if x[0] != "Write-in"], True)
    return out


def minor_priors(say=say_default):
    """[mean, sd, typical largest share] of the log share of each candidate outside the two big parties, for the three
    buckets of minor_races. The simulation draws each such candidate on its own, so the mean and spread are fitted
    (on a grid, by likelihood) to the TOTAL share such candidates took race by race, whatever their number; the cap the
    simulation applies is 1.5 times the 95th percentile of one candidate's share."""
    races = minor_races()
    import random as _random
    rnd = _random.Random(20261010)
    Z = [[rnd.gauss(0, 1) for _ in range(8)] for _ in range(400)]
    out = {}
    for name in ("with_majors", "statewide", "sole"):
        rs = races.get(name) or []
        if len(rs) < 10:
            out[name] = DEFAULT_PARAMS["minor"][name]
            continue
        each = sorted(x for _k, _t, ms in rs for x in ms)
        p99 = each[int(0.95 * (len(each) - 1))]          # the 95th percentile: the simulation caps a draw at 1.5 times it
        if name == "sole":
            # the only opponent of one big party: never above the largest share such a candidate took in 2022 or 2024 (none
            # won), so the simulation's cap (1.5 times this figure) is that share
            p99 = min(each[-1], 0.49) / 1.5
        cap = min(1.5 * p99, 0.6)
        ks = sorted({min(k, 8) for k, _t, _m in rs})
        best = None
        for mi in range(-70, -9):
            mu = mi / 10
            for si in range(2, 17):
                sd = si / 10
                stats = {}
                for k in ks:
                    logs = [math.log(max(sum(min(math.exp(mu + sd * zz[j]), cap) for j in range(k)), 1e-6)) for zz in Z]
                    m = sum(logs) / len(logs)
                    v = sum((x - m) ** 2 for x in logs) / (len(logs) - 1)
                    stats[k] = (m, max(v, 1e-4))
                ll = 0.0
                for k, t, _ms in rs:
                    m, v = stats[min(k, 8)]
                    ll += -0.5 * math.log(v) - (math.log(max(t, 1e-6)) - m) ** 2 / (2 * v)
                if best is None or ll > best[0]:
                    best = (ll, mu, sd)
        out[name] = [best[1], best[2], round(p99, 4)]
        say(f"    minor-party shares, {name}: {len(rs)} races, mean {best[1]}, spread {best[2]}, one candidate's 95th percentile {p99:.3f}")
    return out


def bt_params(sw, hs, minors, widen):
    p = json.loads(json.dumps(DEFAULT_PARAMS))
    fh = widen["house"]
    p.update({"fitted": True, "source": "fitted on the 2022 and 2024 races of every state but Minnesota",
              "state_sd": r6(sw["state_sd"]), "office_sd": {k: r6(v * widen.get(k, 1.0)) for k, v in sw["office_sd"].items()},
              "inc_sw": [r6(sw["inc_sw"][0]), r6(sw["inc_sw"][1])], "lean": {"w_pres": hs["w_pres"]},
              "gap": {"usrep": [r6(hs["gap"]), 0.04]}, "inc": [r6(hs["inc"][0]), r6(hs["inc"][1])],
              "district_sd": {"usrep": r6(hs["district_sd"] * fh)}, "minor": minors, "widen": widen})
    return p


def bt_frames(races, houses, params, scenario):
    """One frame per state-year, in the simulation's shape, for a set of past races. scenario "oracle": the year's
    national shift known (statewide) and the state's presidential result of the year known (House); "pre": neither,
    the 2020 presidential result with a wide environment and no polls."""
    by = defaultdict(lambda: {"stat": [], "house": []})
    for r in races:
        by[(r["state"], r["year"])]["stat"].append(r)
    for h in houses:
        by[(h["state"], h["year"])]["house"].append(h)
    frames = []
    delta = params.get("delta", {})
    for (code, year), grp in sorted(by.items()):
        stat = [dict(r, race=r["id"]) for r in grp["stat"]]
        base20 = logit((grp["stat"] or grp["house"])[0]["base20"])
        if scenario == "oracle":
            env_stat, _u = environment(base20, delta.get(str(year), delta.get(year, 0.0)), 1e-8, params, stat)
        else:
            env_stat, _u = environment(base20, 0.0, PRIORS["env_no_polls_sd"] ** 2, params, stat)
        entries = []
        for k, r in enumerate(stat, 1):
            entries.append({"race": r["id"], "class": r["class"], "cands": r["cands"], "k": k, "tested": None})
        frame_s = make_frame(code, entries, env_stat, params, None, BT_METHOD) if entries else None
        if frame_s:
            frames.append(frame_s)
        if grp["house"]:
            if scenario == "oracle":
                top = logit(grp["house"][0]["top24"])
                env_h = {"theta": ["G"], "mean": [r6(top)], "cov": [[1e-8]]}
            else:
                env_h = {"theta": ["G"], "mean": [r6(base20)], "cov": [[r6(PRIORS["env_no_polls_sd"] ** 2 + params["state_sd"] ** 2)]]}
            hentries = [{"race": h["id"], "class": "usrep", "cands": h["cands"], "lean": r6(lean_of(h, params)), "tested": None}
                        for h in grp["house"]]
            frames.append(make_frame(code, hentries, env_h, params, None, BT_METHOD))
    return frames


def score(frames, truth, scenario, draws, seed_base):
    """Simulate every frame and compare with what happened. Returns (rows for the backtests table, measures by group)."""
    rows, by = [], defaultdict(list)
    for i, fr in enumerate(frames):
        out = simulate(fr, R.seed_of(f"{seed_base}:{scenario}:{i}"), draws)
        for race in out["races"]:
            t = truth[race["race"]]
            dc = next((c for c in race["cands"] if c["key"] == "D"), None)
            if dc is None:
                continue
            grp = t["class"]
            actual = t["shares"].get("D")
            inc_base = None
            if t.get("inc_dir"):
                inc_base = 1.0 if t["inc_dir"] > 0 else 0.0
            last = t.get("last")
            if last is None and t["class"] != "usrep":
                last = 1 if t["base20"] > 0.5 else 0
            rows.append((scenario, t["year"], race["race"], grp, "D", dc["chance"], dc["median"], dc["lo80"], dc["hi80"], dc["lo95"],
                         dc["hi95"], actual, t["won"], inc_base, None if last is None else float(last)))
            by[grp].append(rows[-1])
            by["all"].append(rows[-1])
    meas = {}
    for grp, rs in by.items():
        n = len(rs)
        brier = sum((r[5] - r[12]) ** 2 for r in rs) / n
        ll = -sum(math.log(r[5]) if r[12] else math.log(1 - r[5]) for r in rs) / n
        fav = sum(1 for r in rs if (r[5] >= 0.5) == bool(r[12])) / n
        c80 = sum(1 for r in rs if r[7] <= r[11] <= r[8]) / n
        c95 = sum(1 for r in rs if r[9] <= r[11] <= r[10]) / n
        mae = sum(abs(r[6] - r[11]) for r in rs) / n
        m = {"brier": (brier, n), "log_loss": (ll, n), "favourite_won": (fav, n), "range80_held": (c80, n),
             "range95_held": (c95, n), "share_miss": (mae, n)}
        bi = [r for r in rs if r[13] is not None]
        if bi:
            m["rule_incumbent_wins"] = (sum(1 for r in bi if r[13] == r[12]) / len(bi), len(bi))
            m["model_where_incumbent"] = (sum(1 for r in bi if (r[5] >= 0.5) == bool(r[12])) / len(bi), len(bi))
        bl = [r for r in rs if r[14] is not None]
        if bl:
            m["rule_last_time_repeats"] = (sum(1 for r in bl if r[14] == r[12]) / len(bl), len(bl))
            m["model_where_last_time"] = (sum(1 for r in bl if (r[5] >= 0.5) == bool(r[12])) / len(bl), len(bl))
        for lo in range(0, 100, 10):
            b = [r for r in rs if lo / 100 <= max(r[5], 1 - r[5]) < (lo + 10) / 100 or (lo == 90 and max(r[5], 1 - r[5]) >= 1)]
            if b and lo >= 50:
                m[f"calibration_{lo}_{lo + 10}"] = (sum(1 for r in b if (r[5] >= 0.5) == bool(r[12])) / len(b), len(b))
        # The same measures under the names the Minnesota backtest uses (backtest.measures), which the forecasts page's
        # track record reads: races, cover80, cover95, logloss, the plain rules' Brier scores beside the model's on the
        # same races, and the calibration bins (the Democrat's chance against how often the Democrat came first).
        m.update({"races": (n, n), "cover80": (c80, n), "cover95": (c95, n), "logloss": (ll, n)})
        for name, col in (("incumbent_wins", 13), ("last_time_repeats", 14)):
            rr = [r for r in rs if r[col] is not None]
            if rr:
                m[f"{name}_brier"] = (sum(((0.99 if r[col] else 0.01) - r[12]) ** 2 for r in rr) / len(rr), len(rr))
                m[f"{name}_races"] = (len(rr), len(rr))
                m[f"model_brier_on_{name}_races"] = (sum((r[5] - r[12]) ** 2 for r in rr) / len(rr), len(rr))
        for k in range(10):
            b = [r for r in rs if min(int(r[5] * 10), 9) == k]
            if b:
                pred, obs = sum(r[5] for r in b) / len(b), sum(r[12] for r in b) / len(b)
                m[f"bin{k * 10:02d}_{k * 10 + 10:02d}"] = (round(obs, 4), len(b), f"predicted {pred:.4f}, observed {obs:.4f}")
        meas[grp] = m
    return rows, meas


def backtest(say=say_default, db=DB, store=True, draws=BT_DRAWS):
    """Fit on one year and score on the other (statewide); the House on 2024 in two folds by state. Then widen the
    spreads until the 80 percent ranges hold 80 percent of the results (the "oracle" scenario, which tests the
    structure), fit the final parameters on everything, and store a backtest run (state "US")."""
    t0 = time.time()
    started = R.now_utc()
    msen = {y: U.members_on(U.ELECTION_DAY[y], "Senate") for y in (2022, 2024)}
    sw = {y: past_statewide(y, msen[y], say) for y in (2022, 2024)}
    say(f"    statewide races: 2022 {len(sw[2022])}, 2024 {len(sw[2024])}")
    minors = minor_priors(say)
    base = json.loads(json.dumps(DEFAULT_PARAMS))
    houses, h_skip = past_house_2024(base, say)
    say(f"    House races 2024: {len(houses)} ({h_skip})")
    truth = {r["id"]: r for y in sw for r in sw[y]}
    truth.update({h["id"]: h for h in houses})
    folds_h = (sorted({h["state"] for h in houses})[0::2], sorted({h["state"] for h in houses})[1::2])

    def cross(widen):
        """Cross-fitted frames for every scored race, both scenarios."""
        frames = {"oracle": [], "pre": []}
        for train, test in ((2022, 2024), (2024, 2022)):
            f = fit_statewide(sw[train])
            delta_test = fit_statewide(sw[test])["delta"]
            p = bt_params(f, {"w_pres": 0.7, "gap": 0.0, "inc": base["inc"], "district_sd": 0.12}, minors, widen)
            p["delta"] = {str(k): v for k, v in delta_test.items()}
            for sc in frames:
                frames[sc] += bt_frames(sw[test], [], p, sc)
        fs = fit_statewide(sw[2022] + sw[2024])
        for k, test_states in enumerate(folds_h):
            train_h = [h for h in houses if h["state"] not in test_states]
            fh = fit_house(train_h, base)
            p = bt_params(fs, fh, minors, widen)
            p["delta"] = {}
            test_h = [h for h in houses if h["state"] in test_states]
            for sc in frames:
                frames[sc] += bt_frames([], test_h, p, sc)
        return frames
    widen = {"ussen": 1.0, "governor": 1.0, "other": 1.0, "house": 1.0}
    history = []
    for _round in range(15):
        frames = cross(widen)
        _rows, meas = score(frames["oracle"], truth, "oracle", draws, "final")
        held = {g: meas.get("usrep" if g == "house" else g, {}).get("range80_held", (1.0, 0))[0] for g in widen}
        history.append({"widen": dict(widen), "held80": {g: round(v, 3) for g, v in held.items()}})
        say(f"    widening {widen}: 80% ranges held {', '.join(f'{g} {v:.3f}' for g, v in held.items())}")
        moved = False
        for g, v in held.items():
            if v < PRIORS["cover_min"] and widen[g] < 3.0:
                widen[g] = round(widen[g] + 0.1, 2)
                moved = True
        if not moved:
            break
    frames = cross(widen)
    rows, meas = [], {}
    for sc in ("oracle", "pre"):
        r_, m_ = score(frames[sc], truth, sc, draws, "final")
        rows += r_
        for g, m in m_.items():
            meas[(sc, g)] = m
    fs = fit_statewide(sw[2022] + sw[2024])
    fh = fit_house(houses, base)
    final = bt_params(fs, fh, minors, widen)
    final["delta_past"] = {str(k): r6(v) for k, v in fs["delta"].items()}
    report = {"statewide": {"2022": len(sw[2022]), "2024": len(sw[2024]), "by_class": fs["n"], "pairs": fs["pairs"]},
              "house": {"2024": len(houses), "skipped": h_skip, "w_pres": fh["w_pres"], "n": fh["n"]},
              "widening": history, "seconds": round(time.time() - t0, 1),
              "untested": ("U.S. House races of 2022 (every state drew new lines for 2022, and no past result describes "
                           "them); seats on new 2026 lines (left out, not forecast)"),
              "scenarios": {"oracle": "the national shift (statewide) or the state's own presidential result of the year "
                                      "(House) known: tests how races depart from their state",
                            "pre": "as it would have stood before the election from the 2020 presidential result, with no "
                                   "polls (the kit has no member polls of 2022 or 2024): a harder test than 2026's, which has polls"}}
    for (sc, g), m in sorted(meas.items()):
        say(f"    {sc:6} {g:9} n={m['brier'][1]:4}  Brier {m['brier'][0]:.3f}  log loss {m['log_loss'][0]:.3f}  favourite won "
            f"{m['favourite_won'][0]:.3f}  80% held {m['range80_held'][0]:.3f}  95% held {m['range95_held'][0]:.3f}  "
            f"share miss {m['share_miss'][0] * 100:.1f} pts" +
            (f"  incumbent rule {m['rule_incumbent_wins'][0]:.3f} (model {m['model_where_incumbent'][0]:.3f}, n={m['rule_incumbent_wins'][1]})"
             if "rule_incumbent_wins" in m else "") +
            (f"  last-time rule {m['rule_last_time_repeats'][0]:.3f} (model {m['model_where_last_time'][0]:.3f})"
             if "rule_last_time_repeats" in m else ""))
    say(f"    final parameters: state {final['state_sd']}, offices {final['office_sd']}, senator's edge {final['inc_sw']}, "
        f"House: blend {final['lean']}, gap {final['gap']}, member's edge {final['inc']}, district {final['district_sd']}")
    if not store:
        return {"params": final, "measures": meas, "report": report}
    con = R.connect(db)
    try:
        run = R.new_run_id(con, "backtest", "US", started)
        seed = R.seed_of(run)
        frame = {"params": final, "report": report, "method": BT_METHOD}
        inputs = [{"input": f"clerk-{y}", "source": U.CLERK_URL.format(y=y), "sha256": sha_file(U.CLERK_PDF[y]), "as_of": U.ELECTION_DAY[y],
                   "kind": "official", "note": "votes for President, Senate and House"} for y in (2020, 2022, 2024)]
        inputs.append({"input": "medsl-2022-2024", "source": "https://github.com/MEDSL (2022-elections-official, 2024-elections-official)",
                       "sha256": R.sha_text(R.canonical({f"{y}-{c}": (U.medsl(y, c, say=lambda *a: None) or {}).get("sha256")
                                                         for y in (2022, 2024) for c in U.CODES})),
                       "as_of": None, "kind": "secondary", "note": "governors and the other statewide offices; votes placed in districts"})
        inputs.append({"input": "frame-builder", "source": "election/model/other_states.py and data_us.py", "sha256": my_code_sha(),
                       "as_of": None, "kind": "derived", "note": "the code that fitted and scored"})
        with con:
            R.record_run(con, run=run, state="US", kind="backtest", method=BT_METHOD, seed=seed, draws=draws, started=started,
                         as_of=started, frame=frame, outputs={"races": []}, inputs=inputs,
                         note="backtest of the other states' model on 2022 and 2024")
            con.executemany("INSERT OR REPLACE INTO backtests (run, scenario, year, race, grp, choice, chance, median, lo80, hi80, lo95, "
                            "hi95, actual, won, base_inc, base_last) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                            [(run, *r) for r in rows])
            crow = []
            for (sc, g), m in meas.items():
                for k, (v, n, *note) in m.items():
                    crow.append((run, sc, g, k, v, n, note[0] if note else None))
            con.executemany("INSERT OR REPLACE INTO calibration (run, scenario, grp, measure, value, n, note) VALUES (?,?,?,?,?,?,?)", crow)
        say(f"    stored backtest {run} in {time.time() - t0:.0f} s")
        return {"run": run, "params": final, "measures": meas, "report": report}
    finally:
        con.close()


# ============================================================================================== checks

def check(codes=None, db=DB, say=say_default):
    """Every check this part owns, state by state. Returns True when all hold."""
    ok = True
    codes = [c.upper() for c in (codes or U.CODES) if c.upper() not in SKIP]
    lo = load_json(LEFT_OUT_FILE)["states"] if os.path.exists(LEFT_OUT_FILE) else {}
    totals = defaultdict(int)
    for code in codes:
        races = U.races_2026(code)
        e = R.check_no_extremes(code, db)
        u = R.check_unopposed(code, db)
        ok &= e["holds"] and u["holds"]
        runs = [r for r in R.list_runs(db, code) if r["kind"] == "pre" and not r["rehearsal"] and r["method"].startswith("us-pre")]
        redo_ok = True
        for r in runs:
            res = R.redo(r["run"], db, say=lambda *a: None)
            redo_ok &= res["exact"]
            if not res["exact"]:
                say(f"    {code}: run {r['run']} did NOT redo exactly: {res}")
        ok &= redo_ok
        # every race forecast, unopposed or listed with a reason
        con = R.connect(db)
        try:
            stored = {race: st for race, st in con.execute(
                "SELECT rr.race, rr.status FROM race_runs rr JOIN runs r ON r.run = rr.run WHERE rr.state = ? AND r.method LIKE 'us-pre-%' "
                "AND r.rehearsal = 0", (code,))}
        finally:
            con.close()
        left = (lo.get(code) or {}).get("left_out", {})
        missing = [r["race"] for r in races if r["race"] not in stored and r["race"] not in left]
        ok &= not missing
        totals["races"] += len(races)
        totals["forecast"] += sum(1 for s in stored.values() if s == "pre")
        totals["unopposed"] += sum(1 for s in stored.values() if s == "unopposed")
        totals["left out"] += len(left)
        say(f"    {code}: races {len(races)}, forecast {sum(1 for s in stored.values() if s == 'pre')}, unopposed "
            f"{sum(1 for s in stored.values() if s == 'unopposed')}, left out {len(left)}; no 0 or 100 {e['holds']}; "
            f"unopposed carry none {u['holds']}; {len(runs)} runs redone exactly {redo_ok}"
            + (f"; NOT ACCOUNTED FOR: {missing}" if missing else ""))
    say(f"    in all: {dict(totals)}; {'every check holds' if ok else 'a check FAILED'}")
    return ok


def selftest(say=print):
    import tempfile
    ok = True

    def chk(what, got, want):
        nonlocal ok
        good = got == want
        ok &= good
        say(f"    {'ok ' if good else 'BAD'} {what}: {got!r}" + ("" if good else f" (expected {want!r})"))
    p = json.loads(json.dumps(DEFAULT_PARAMS))
    stat = [{"race": "S1", "class": "ussen", "inc_dir": 1, "cands": [{"key": "a", "name": "Ann Able", "p": "D", "inc": 1},
                                                                      {"key": "b", "name": "Bob Baker", "p": "R", "inc": 0}]},
            {"race": "G1", "class": "governor", "inc_dir": 0, "cands": [{"key": "c", "name": "Cy Cole", "p": "D"},
                                                                         {"key": "d", "name": "Di Dunn", "p": "R"},
                                                                         {"key": "e", "name": "Ed Eel", "p": "O"}]}]
    polls = {"S1": [{"pollster": "X", "end": "2026-10-01", "n": 800, "shares": {"Ann Able": 55, "Bob Baker": 45}}]}
    env, used = environment(0.0, 0.0, 0.01, p, stat, polls)
    chk("a poll moves its race toward it", env["mean"][1] > 0.06, True)
    chk("and moves G a little", 0 < env["mean"][0] < 0.2, True)
    chk("the covariance stays symmetric", abs(env["cov"][0][1] - env["cov"][1][0]) < 1e-9, True)
    chk("a poll naming someone else is not used", poll_two_party({"shares": {"Zed": 50, "Bob Baker": 50}}, stat[0]["cands"]), None)
    entries = [dict(stat[0], k=1, tested="t"), dict(stat[1], k=2, tested="t"),
               {"race": "H1", "class": "usrep", "lean": 1.0, "tested": "t",
                "cands": [{"key": "f", "name": "Fay", "p": "D", "inc": 0}, {"key": "g", "name": "Gus", "p": "R", "inc": 1}]},
               {"race": "U1", "status": "unopposed", "cands": [{"key": "h", "name": "Hal", "p": "R"}]}]
    fr = make_frame("XX", entries, env, p, dt.datetime(2026, 10, 10, tzinfo=dt.timezone.utc), METHOD)
    a, b = simulate(fr, 11, 500), simulate(fr, 11, 500)
    chk("the same frame and seed give the same numbers", R.canonical(a) == R.canonical(b), True)
    races = {r["race"]: r for r in a["races"]}
    chk("a strong-Democratic district favours the Democrat", races["H1"]["cands"][0]["chance"] > 0.8, True)
    chk("an unopposed race carries no chance", [c.get("chance") for c in races["U1"]["cands"]], [None])
    chk("no chance is 0 or 1", all(0 < c["chance"] < 1 for r in a["races"] if r["status"] == "pre" for c in r["cands"]), True)
    chk("a grid at zero shift is the lean's share", round(make_grid(0.4)[120], 5), round(expit(0.4), 5))
    d = tempfile.mkdtemp()
    db = os.path.join(d, "t.sqlite")
    con = R.connect(db)
    run = R.new_run_id(con, "pre", "XX")
    out = simulate(fr, R.seed_of(run), 300)
    with con:
        R.record_run(con, run=run, state="XX", kind="pre", method=METHOD, seed=R.seed_of(run), draws=300, started=R.now_utc(),
                     as_of=R.now_utc(), frame=fr, outputs=out, inputs=[])
    con.close()
    chk("a stored run redoes exactly", R.redo(run, db, say=lambda *x: None)["exact"], True)
    chk("no 0 or 100 in the page file", R.check_no_extremes("XX", db)["holds"], True)
    chk("nothing for the unopposed race", R.check_unopposed("XX", db)["holds"], True)
    doc = R.page_json("XX", db)
    chk("the page file holds the three forecast races", sorted(doc["r"]), ["G1", "H1", "S1"])
    hs = [{"a": 0.1, "b": 0.3, "inc_dir": 0, "d2p": expit(0.25), "top24": 0.5}, {"a": -0.2, "b": -0.1, "inc_dir": 1, "d2p": expit(0.0), "top24": 0.5},
          {"a": 0.5, "b": 0.6, "inc_dir": -1, "d2p": expit(0.45), "top24": 0.5}, {"a": None, "b": 0.2, "inc_dir": 0, "d2p": expit(0.2), "top24": 0.5}]
    fh = fit_house(hs, p)
    chk("the House fit finds a blend between 0 and 1", 0.0 <= fh["w_pres"] <= 1.0, True)
    return ok


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--backtest", action="store_true")
    ap.add_argument("--no-store", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--left-out", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--states")
    ap.add_argument("--draws", type=int, default=DRAWS)
    ap.add_argument("--db", default=DB)
    a = ap.parse_args(argv)
    codes = [c.strip().upper() for c in a.states.split(",")] if a.states else None
    if a.selftest:
        sys.exit(0 if selftest() else 1)
    if a.backtest:
        backtest(db=a.db, store=not a.no_store)
    if a.run:
        run_pre(codes, db=a.db, draws=a.draws, dry=a.dry_run)
    if a.check:
        sys.exit(0 if check(codes, a.db) else 1)
    if a.left_out:
        for code in codes or [c for c in U.CODES if c not in SKIP]:
            for rid, why in sorted(left_out(code).items()):
                print(f"    {rid}: {why}")
    if not (a.backtest or a.run or a.check or a.left_out):
        ap.print_help()


if __name__ == "__main__":
    main()
