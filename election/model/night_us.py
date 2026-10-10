"""election/model/night_us.py - the night's model for every state but Minnesota: each race for Congress, governor and the
other statewide offices that has a pre-election forecast moves with the votes counted, county by county (ARCHITECTURE.md
4.1 "On the night", 4.2, 4.6). Owned by N17b. Analysis, never a result.

    election.model.night_us.run(state=, now=, db=, rehearsal=, say=)     what the updater (election/live.py) calls after a
                                                                         state's new results, at most once a cycle
    python -m election.model.night_us --state fl [--db <results db>] [--model-db <model db>] [--dry-run]
    python -m election.model.night_us --replays [--no-store]             the 2024 generals the readers hold (Florida, North
                                                                         Carolina, Pennsylvania, Louisiana, Georgia) replayed
                                                                         in each state's own counting order and scored at 10,
                                                                         25, 50, 75 and 90 percent counted; the night's spread
                                                                         sized on them; stored as a run of kind "replay"
                                                                         (state "US") that the track record shows
    python -m election.model.night_us --check --scratch <folder>         this part's checks on scratch copies (made-up counts
                                                                         for every state read live, and Minnesota's practice
                                                                         figures): one full night run timed (limit 30 s),
                                                                         every stored run redone exactly, no 0 or 100,
                                                                         nothing for an unopposed race
    python -m election.model.night_us --selftest                         the arithmetic on made-up counties

WHERE IT STARTS: the state's newest pre-election run (other_states.py: its environment and every race's prior), each
county's past votes (data_us.county_baseline: how the county voted for President in 2024 against the state, how it voted
in 2022's top race, its Census figures), and the state's own count-order note in its registry file.

WHAT IT DOES WITH THE VOTES COUNTED (county by county; where a feed reports precincts, they are added up to their county,
and the share of the county's precincts in says how complete it is; where a feed gives one statewide figure, the state
is one unit)
  1. The swing. Every two-party race counted in a county says how far that county ran from the forecast there. Those
     gaps are explained together, for all of the state's races at once: a statewide shift, each race's own offset, a shift
     for each region (the state's congressional districts, where it has two to fourteen), how far the county moved from
     2022 to 2024 (past swing), four Census figures (size, degree holders, Black and Hispanic residents) and each county's
     own shift; each pulled toward none while few counties are in (Gaussian priors; the counties' block is diagonal, so
     it is solved exactly).
  2. Count order (John's first blind spot), as each state counts (its registry note, kept here as ORDER): where the feed
     reports Election Day, early and mail ballots apart, each kind of ballot gets its own lean, learned from the
     counties where it is counted, and the ballots of each kind still out are estimated kind by kind; where it gives
     totals only, the ballots counted first in a county may lean apart from those counted last by an unknown gap (its
     spread set by how the state counts: Florida's mail first, Pennsylvania's and New York's mail late, the all-mail
     states' upload order), so early figures are never taken as typical.
  3. Turnout: each county's expected votes (2022's turnout spread over the state, the race's own expected total) and
     a statewide turnout factor learned from counties that are complete; the votes still out in each county by the
     state's way of counting (precincts still out, ballots of each kind not yet reported, mail still arriving).
  4. The decision rule: the most votes (plurality, top two); more than half where the law asks for it (Georgia's runoff,
     Vermont's legislature, Louisiana's open primary: the chance shown is of finishing first, beside the chance no one
     passes half); ranked choice (Alaska, Maine): first choices on the night, said so.
  5. simulate_us.py draws 1,500 possible ends of the count: each candidate's chance (never 0 or 100), median share, 80 and
     95 percent ranges, the likely margin of the top two and the race's expected total. Every run is kept as a version
     (runs.py, kind "live", method US_LIVE_METHOD).
A race with no pre-election forecast gets none on the night; an unopposed race never gets one; a certified race is not
modelled (the official count decides).
"""

import argparse
import datetime as dt
import json
import math
import os
import random
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
from election.model import simulate_us as S  # noqa: E402

US_LIVE_METHOD = "us-live-1.0"
DRAWS = 1500
BT_DRAWS = 800
SKIP = ("MN",)                     # Minnesota's night has its own model (live_model.py)
CHECKPOINTS = (0.10, 0.25, 0.50, 0.75, 0.90)
TARGET = 0.78                      # the 80 percent ranges must hold at least this often at every checkpoint (N16's rule)
STATE_FLOOR, STATE_MIN = 0.6, 8    # and at least this often within any one state replayed with this many races or more
TYPES = ("early", "mail", "election_day", "provisional", "other")
TYPE_OF = {"early": "early", "mail": "mail", "absentee": "mail", "election_day": "election_day", "provisional": "provisional",
           "other": "other"}
TYPE_WORDS = {"early": "early in-person ballots", "mail": "mail ballots", "election_day": "Election Day ballots",
              "provisional": "provisional ballots", "other": "other ballots"}
FEATURES = ("size", "degree", "black", "hispanic")
NAMES = {"AK": "Alaska", "AL": "Alabama", "AR": "Arkansas", "AZ": "Arizona", "CA": "California", "CO": "Colorado",
         "CT": "Connecticut", "DC": "the District of Columbia", "DE": "Delaware", "FL": "Florida", "GA": "Georgia", "HI": "Hawaii",
         "IA": "Iowa", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana",
         "MA": "Massachusetts", "MD": "Maryland", "ME": "Maine", "MI": "Michigan", "MN": "Minnesota", "MO": "Missouri",
         "MS": "Mississippi", "MT": "Montana", "NC": "North Carolina", "ND": "North Dakota", "NE": "Nebraska", "NH": "New Hampshire",
         "NJ": "New Jersey", "NM": "New Mexico", "NV": "Nevada", "NY": "New York", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon",
         "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas",
         "UT": "Utah", "VA": "Virginia", "VT": "Vermont", "WA": "Washington", "WI": "Wisconsin", "WV": "West Virginia", "WY": "Wyoming"}

# ============================================================================================== how each state counts
# The count-order blind spot as each state counts, from its registry note (election/registry/<code>.json "count_order"
# and "vote_types", checked 2026-10-09):
#   dump      early and mail ballots counted before the polls close and released first; Election Day votes follow
#   late      Election Day (and early in-person) votes first; mail or absentee ballots counted later
#   mail      all or nearly all by mail; ballots counted as they arrive and uploaded batch by batch, for days
#   precinct  precincts report whole, their absentee ballots included
#   unknown   the order has not been seen
ORDER = {"AK": "late", "AL": "precinct", "AR": "unknown", "AZ": "mail", "CA": "mail", "CO": "mail", "CT": "unknown",
         "DC": "unknown", "DE": "unknown", "FL": "dump", "GA": "dump", "HI": "dump", "IA": "unknown", "ID": "unknown", "IL": "late",
         "IN": "unknown", "KS": "unknown", "KY": "unknown", "LA": "unknown", "MA": "unknown", "MD": "late", "ME": "unknown",
         "MI": "unknown", "MO": "unknown", "MS": "precinct", "MT": "unknown", "NC": "dump", "ND": "precinct", "NE": "unknown",
         "NH": "unknown", "NJ": "unknown", "NM": "unknown", "NV": "mail", "NY": "late", "OH": "dump", "OK": "unknown",
         "OR": "mail", "PA": "late", "RI": "unknown", "SC": "unknown", "SD": "unknown", "TN": "unknown", "TX": "dump",
         "UT": "mail", "VA": "unknown", "VT": "unknown", "WA": "mail", "WI": "unknown", "WV": "unknown", "WY": "precinct"}
ORDER_WORDS = {
    "FL": "Florida counts mail and early ballots before the polls close and releases them first; Election Day votes follow.",
    "NC": "North Carolina reports early in-person and mail ballots first, then Election Day votes precinct by precinct.",
    "GA": "Georgia reports early in-person and mail ballots first, then Election Day votes.",
    "TX": "Texas releases its early votes first, then Election Day votes precinct by precinct.",
    "HI": "Hawaii reports mail ballots first and in-person votes after.",
    "OH": ("Ohio reports early and absentee ballots received by Election Day first, then Election Day votes; late absentee "
           "and provisional ballots come in the canvass."),
    "PA": ("Pennsylvania may not start on its mail ballots until 7 a.m. on Election Day, so Election Day votes often come "
           "first and mail ballots later, county by county."),
    "NY": "New York counts early voting and Election Day ballots first and mail and absentee ballots later.",
    "AK": ("Alaska's figures on the night are mostly ballots cast in person; absentee and questioned ballots are added on "
           "later count days."),
    "MD": "Maryland reports early voting and Election Day ballots on the night; mail ballots are counted over the following days.",
    "IL": "Illinois counts mail ballots that arrive up to 14 days after Election Day, so they are added late.",
    "CA": ("California counts for weeks: mail ballots that arrive after Election Day are counted last, so the count on the "
           "night is far from the whole."),
}
KIND_WORDS = {
    "mail": ("{name} votes by mail: ballots are counted as they arrive and uploaded batch by batch, for days after "
             "Election Day, so the order of the uploads is the count order."),
    "precinct": "{name}'s counties report their precincts whole, so the first counties in may not be typical of the rest.",
    "unknown": "How {name} orders its count has not been seen here, so the first figures may lean either way.",
    "dump": "{name} releases its early and mail ballots first and its Election Day votes after.",
    "late": "{name} counts its Election Day votes first and its mail or absentee ballots later.",
}
MODEL_ORDER_WORDS = ("The model never treats the first figures as typical: it compares each county counted with what the "
                     "forecast expected there, and lets the ballots still to come lean differently from those counted so far.")
TYPED_WORDS = ("{name}'s results give the kinds of ballot apart, so the model also learns how each kind leans tonight and "
               "estimates the ballots of each kind still to come.")
FIRST = {"dump": ("early", "mail"), "late": ("early", "election_day"), "precinct": (), "unknown": (), "mail": ()}
BATCH = {"dump": ("early", "mail"), "late": ("early",), "precinct": (), "unknown": (), "mail": ()}   # whole once posted

DEFAULT_NIGHT_US = {
    "fitted": False, "source": "starting values: no replay of past counts on file",
    "sigma_u": 0.08,               # a county's own shift beyond the state's, regions', past swing's and Census terms' (log-odds)
    "tau_r": 0.05,                 # a region's (a congressional district's) shift, prior spread
    "tau_beta": 0.4,               # the past-swing coefficient, prior spread
    "tau_b": 0.03,                 # a Census term, per standard deviation, prior spread
    "tau_d": 0.6,                  # a kind of ballot's lean against the county's whole, prior spread (mail and Election Day
                                   # ballots have run a point of log-odds apart since 2020)
    "type_prior": {},              # a kind of ballot's lean before tonight (the 2024 counts replayed), where known: the same
    "type_prior_sd": 0.6,          # spread as without it, so that the spreads sized on the replays still hold
    "gap_sd": {"dump": 0.15, "late": 0.15, "mail": 0.15, "precinct": 0.06, "unknown": 0.12},   # first-counted against last
    "sigma_sw": 0.04,              # a statewide race's own gap in one county (its candidates)
    "sigma_part": 0.08,            # a district race in a county that lies wholly in the district
    "sigma_split": 0.25,           # a district race in part of a county split between districts
    "sigma_typed": 0.15,           # a kind of ballot's own lean in one county, beyond the state's lean for that kind
    "sigma_w": 0.12,               # the part of a county (or of its Election Day vote) still out against the part counted
    "sigma_xi": 0.05,              # all of a race's votes still out leaning together beyond everything above (log-odds)
    "gap_ed_sd": 0.06,             # Election Day precincts counted first against those counted last, statewide
    "turn": {"sd_state": 0.10, "sd_unit": 0.10, "sd_prior_unit": 0.15},
    "ed_share": {"dump": 0.3, "late": 0.65, "mail": 0.0, "precinct": 1.0, "unknown": 0.6},   # reported through precincts
    "late": {"dump": 0.02, "late": 0.03, "mail": 0.25, "precinct": 0.01, "unknown": 0.02},   # still to count when all are in
    "mix": {"early": 0.35, "mail": 0.20, "election_day": 0.43, "provisional": 0.02, "other": 0.0},
    "other": {"k0": 500, "sd_few": 0.25, "sd_many": 0.10},
    "multi": {"sigma_h": 0.35, "rho": 0.10, "tau": 0.5},
    "scale_p": 1.0,                # partisan spreads times this where the feed gives county totals (sized on the replays)
    "scale_typed": 1.0,            # and where it gives the kinds of ballot apart
    "pseudo_counties": 0,
}


def say_default(*a):
    print(*a, flush=True)


def quiet(*_a, **_k):
    return None


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


def inverse_spd(A):
    n = len(A)
    L = chol(A)
    out = [[0.0] * n for _ in range(n)]
    for c in range(n):
        y = [0.0] * n
        for i in range(n):
            y[i] = ((1.0 if i == c else 0.0) - sum(L[i][k] * y[k] for k in range(i))) / L[i][i]
        x = [0.0] * n
        for i in reversed(range(n)):
            x[i] = (y[i] - sum(L[k][i] * x[k] for k in range(i + 1, n))) / L[i][i]
        for r in range(n):
            out[r][c] = x[r]
    return out


def name_key(name):
    s = str(name or "").lower()
    s = re.sub(r"\([^)]*\)", " ", s)
    return re.sub(r"[^a-z0-9]+", "", s)


def party_letter(p):
    """A party as a file prints it: Democratic, Republican, or another."""
    q = re.sub(r"[^A-Z]", "", str(p or "").upper())
    if q in ("D", "DEM", "DFL") or q.startswith("DEMOCRAT"):
        return "D"
    if q in ("R", "REP", "GOP") or q.startswith("REPUBLICAN"):
        return "R"
    return "O"


def state_name(code):
    return NAMES.get(code.upper(), code.upper())


def order_kind(code):
    return ORDER.get(code.upper(), "unknown")


def feed_gives_kinds(code):
    """Whether the state's results feed gives the kinds of ballot apart (Election Day, early, mail), by its registry note."""
    try:
        from election import registry
        e = registry.load(code.upper()) or {}
    except Exception:  # noqa: BLE001
        return False
    if e.get("family") in ("nc_sbe", "pa_returns", "civix", "ok_export", "de_json", "md_pages"):
        return True
    return bool(re.match(r"\s*(yes|partly)\b", str(e.get("vote_types") or ""), re.I))


def order_words(code, typed=False):
    """The count-order blind spot for a state, in plain words: how it counts, and what the model does about it."""
    code = code.upper()
    name = state_name(code)
    first = ORDER_WORDS.get(code) or KIND_WORDS[order_kind(code)].format(name=name)
    first = first[:1].upper() + first[1:]
    out = first + " " + MODEL_ORDER_WORDS
    if typed:
        out += " " + TYPED_WORDS.format(name=name)
    return out


# ============================================================================================== each county's past votes

_BASE = {}


def baseline(code, year=2026, say=quiet):
    """Each county's past votes and Census figures for a state, as the night reads them: {"c": {five-digit FIPS: {"L": lean
    (its two-party Democratic share against the state's, log-odds), "sw": its past swing (the 2024 lean less 2022's), "w":
    its share of the state's expected votes, "Z": the standardised Census terms}}, "sources": [...], "lean_year": ...}.
    year 2026: leans from 2024's presidential vote, turnout from 2022's top race (a midterm); year 2024 (the replays):
    leans and turnout from 2022's top race only, so that nothing of the election replayed is used. Kept in memory."""
    key = (code.upper(), year)
    if key in _BASE:
        return _BASE[key]
    from election.model import data_us as U
    code = code.upper()
    cb = U.county_baseline(code, say=quiet)
    counties = cb.get("counties") or {}
    ok24 = U.medsl_reliable(2024, code, say=quiet)[0] if U.medsl(2024, code, say=quiet) else False
    ok22 = U.medsl_reliable(2022, code, say=quiet)[0] if U.medsl(2022, code, say=quiet) else False

    def leans(field, ok):
        if not ok:
            return {}
        vals = {f: v[field] for f, v in counties.items() if field in v and (v[field][0] + v[field][1]) > 0}
        D = sum(v[0] for v in vals.values())
        Rv = sum(v[1] for v in vals.values())
        if D <= 0 or Rv <= 0:
            return {}
        s = logit(D / (D + Rv))
        return {f: logit((d + 0.5) / (d + r + 1.0)) - s for f, (d, r) in vals.items()}
    L24 = leans("pres24", ok24) if year >= 2026 else {}
    L22 = leans("top22", ok22)
    lean = L24 or L22
    sw = {f: L24[f] - L22[f] for f in L24 if f in L22} if (L24 and L22) else {}
    w = {}
    for f, v in counties.items():
        t22 = sum(v.get("top22") or [0, 0])
        if t22 > 0 and ok22:
            w[f] = float(t22)
    if not w:
        for f, v in counties.items():
            t24 = sum(v.get("pres24") or [0, 0])
            if t24 > 0 and year >= 2026:
                w[f] = float(t24)
    tot = sum(w.values()) or 1.0
    raw = {}
    for f, v in counties.items():
        c = v.get("census") or {}
        raw[f] = [math.log(c["pop"]) if c.get("pop") else None, c.get("bachelors_plus"), c.get("black"), c.get("hispanic")]
    Z = {f: [0.0] * len(FEATURES) for f in raw}
    for j in range(len(FEATURES)):
        vals = [r[j] for r in raw.values() if r[j] is not None]
        if len(vals) < 3:
            continue
        m = sum(vals) / len(vals)
        sd = math.sqrt(sum((x - m) ** 2 for x in vals) / (len(vals) - 1)) or 1.0
        for f, r in raw.items():
            Z[f][j] = 0.0 if r[j] is None else max(min((r[j] - m) / sd, 4.0), -4.0)
    out = {"c": {}, "sources": cb.get("sources") or [], "lean_year": (2024 if L24 else 2022 if L22 else None),
           "swing": bool(sw), "medsl_ok": {"2024": ok24, "2022": ok22}}
    for f in sorted(set(lean) | set(w)):
        out["c"][f] = {"L": r6(lean.get(f, 0.0)), "sw": r6(sw.get(f, 0.0)), "w": r6(w.get(f, 0.0) / tot), "Z": [r6(z) for z in Z.get(f, [0.0] * 4)]}
    _BASE[key] = out
    return out


# ============================================================================================== the pre-election run

def newest_pre(model_db, state):
    """(run id, (frame, frame SHA-256)) of a state's newest finished pre-election run (never a rehearsal), or (None, None)."""
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


def night_params(model_db=MODEL_DB):
    """The newest replay calibration of the other states' night (kind "replay", state "US", this method), or the starting
    values. Returns (params, run id or None)."""
    if os.path.exists(model_db):
        con = R.connect(model_db)
        try:
            row = con.execute("SELECT run, frame_sha FROM runs WHERE state = 'US' AND kind = 'replay' AND method = ? AND ended IS NOT NULL "
                              "ORDER BY started DESC, run DESC LIMIT 1", (US_LIVE_METHOD,)).fetchone()
            if row:
                doc = R.get_blob(con, row[1]) or {}
                if doc.get("params"):
                    return merge(DEFAULT_NIGHT_US, doc["params"]), row[0]
        finally:
            con.close()
    return json.loads(json.dumps(DEFAULT_NIGHT_US)), None


SIM_RULE = {"plurality": "plurality", "top_two": "plurality", "majority_runoff": "majority", "open_primary": "majority",
            "majority_or_legislature": "majority", "ranked_choice": "rcv"}


def rule_words(code, rule):
    """What a decision rule means for the forecast, in plain words (None for plurality)."""
    name = state_name(code)
    if rule == "majority_runoff":
        return ("A candidate needs more than half the votes; if no one has it, the top two meet in a runoff. The chance shown is "
                "of finishing first in the count; the chance that no one passes half is shown beside it.")
    if rule == "open_primary":
        return ("Every candidate is on the November ballot; more than half the votes wins outright, otherwise the top two meet "
                "in a runoff. The chance shown is of finishing first; the chance that no one passes half is shown beside it.")
    if rule == "majority_or_legislature":
        return (f"Without more than half the votes, {name}'s legislature chooses. The chance shown is of finishing first in the "
                f"count; the chance that no one passes half is shown beside it.")
    if rule == "ranked_choice":
        return ("Voters rank the candidates. On election night the count is of first choices; the state counts the later rounds "
                "in the days after. The chance shown is of leading once the later choices are added, taken as following the two "
                "big parties' split.")
    if rule == "top_two":
        return "The two candidates who advanced from the primary meet here; the most votes wins."
    return None


_RULES = {}


def decision_rule(code, cls):
    """The rule that decides a class of race in a state (other_states.decision_rule, from the registry), kept in memory."""
    key = (code.upper(), cls)
    if key not in _RULES:
        from election.model import other_states as OS
        _RULES[key] = OS.decision_rule(code.upper(), cls)
    return _RULES[key]


def race_specs(code, frame):
    """Each forecast race of a pre-election frame, as the night reads it: its candidates, the prior of its Democratic
    two-party share (log-odds mean and variance), its expected votes, the minor candidates' expected share, its rule."""
    env = frame["env"]
    mean, cov = env["mean"], env["cov"]
    P = frame["params"]
    leans = (frame.get("report") or {}).get("leans") or {}
    var_g = cov[0][0]
    specs = []
    for e in frame["races"]:
        if e.get("status") != "pre":
            continue
        cands = [{"key": c["key"], "name": c["name"], "p": c.get("p") or "O", "inc": c.get("inc", 0)} for c in e["cands"]]
        p = [c["p"] for c in cands]
        cls = e.get("class") or "other"
        rule = decision_rule(code, cls)
        sp = {"race": e["race"], "class": cls, "cands": cands, "votes": e.get("votes"), "tested": e.get("tested"),
              "rule": SIM_RULE.get(rule, "plurality"), "rule_name": rule, "house": cls == "usrep"}
        inc_dir = sum((1 if c["p"] == "D" else -1 if c["p"] == "R" else 0) * (c.get("inc") or 0) for c in cands)
        if cls == "usrep":
            lean = None
            if e["race"] in leans:
                lean = leans[e["race"]][0]
            elif e.get("f"):
                lean = logit(e["f"][len(e["f"]) // 2])
            gap = (P.get("gap") or {}).get("usrep", [0.0, 0.06])
            inc = P.get("inc", [0.08, 0.04])
            dsd = (P.get("district_sd") or {}).get("usrep", 0.12)
            m = mean[0] + gap[0] + inc[0] * inc_dir + (lean or 0.0)
            v = var_g + gap[1] ** 2 + (inc[1] * inc_dir) ** 2 + dsd ** 2 + P.get("region_sd", 0.0) ** 2
        else:
            k = e.get("k") or 0
            m = mean[0] + (mean[k] if k else 0.0)
            v = cov[0][0] + ((cov[k][k] + 2 * cov[0][k]) if k else 0.0)
        sp["m"], sp["v"], sp["var_g"] = m, max(v, 0.0004), var_g
        minor = (P.get("minor") or {})
        if p.count("D") == 1 and p.count("R") == 1:
            sp["kind"] = "partisan"
            sp["iD"], sp["iR"] = p.index("D"), p.index("R")
            prior = minor.get("statewide", minor.get("with_majors", [-3.2, 0.9, 0.15])) if cls != "usrep" else minor.get("with_majors", [-3.2, 0.9, 0.15])
            n_o = sum(1 for x in p if x not in ("D", "R"))
            sp["oth_prior"] = min(n_o * math.exp(prior[0] + prior[1] ** 2 / 2), 0.3) + (P.get("writein") or {}).get("partisan", 0.002)
        else:
            sp["kind"] = "multi"
            prior = minor.get("sole", [-1.7, 0.6, 0.35]) if (p.count("D") + p.count("R")) == 1 else minor.get("with_majors", [-3.2, 0.9, 0.15])
            majors = [k for k, x in enumerate(p) if x in ("D", "R")]
            mm = math.exp(prior[0])
            sp["mu"] = [(math.log(max(1.0 - mm * (len(cands) - len(majors)), 0.05) / max(len(majors), 1)) if x in ("D", "R") else prior[0])
                        for x in p]
            sp["tau"] = max(prior[1], 0.2)
            sp["wi_prior"] = (P.get("writein") or {}).get("partisan_sole", 0.01)
        specs.append(sp)
    # a district with no contested 2022 race has no expected total of its own: the other districts' middle one, else the
    # state's expected votes shared among its districts
    known = sorted(float(s["votes"]) for s in specs if s.get("house") and s.get("votes"))
    statewide = max((float(s["votes"]) for s in specs if not s.get("house") and s.get("votes")), default=None)
    for s in specs:
        if s.get("house") and not s.get("votes"):
            if known:
                s["votes"] = known[len(known) // 2]
            elif statewide:
                try:
                    from election.model import data_us as U
                    n_d = sum(1 for k in U.clerk(2024)["states"].get(code.upper(), {}).get("house", {}) if str(k).isdigit()) or 1
                except Exception:  # noqa: BLE001
                    n_d = 1
                s["votes"] = statewide / n_d
    return specs


# ============================================================================================== the votes counted (results store)

def snapshot_info(con, state):
    row = con.execute("SELECT snapshot_id, sha256, source_time, fetched_at FROM snapshots WHERE state = ? AND status = 'ok' "
                      "ORDER BY snapshot_id DESC LIMIT 1", (state.upper(),)).fetchone()
    return {"snapshot": row[0], "sha256": row[1], "at": row[2] or row[3]} if row else None


def observations(con, state, specs):
    """{race: {"units": {county: {"in", "all", "t": {kind of ballot or "total": [votes of each candidate (the spec's order)...,
    other]}}}, "whole": the same for the whole contest}} from the results store's newest good figures, and an account
    (precincts in and in all are the county's own row where it has one, else its precincts counted whole). A county's
    own row carries its votes; its precincts' rows are added up only where it has none. Each line of the file is tied to a candidate on the forecast's
    list by the name as filed (else as printed), else, in a two-party race, by party when one name of that party is on
    each side; write-ins and lines tied to nobody are "other". Precincts with a five-digit county as parent are added up
    to it; a race whose figures are only by town, ward or precinct with no county is read as one statewide unit."""
    st = state.upper()
    pre = f"2026-{st}-"
    spec = {s["race"]: s for s in specs}
    kinds, parent = {}, {}
    for unit, kind, par in con.execute("SELECT unit_id, kind, parent FROM units WHERE state = ?", (st,)):
        kinds[unit] = kind
        parent[unit] = par
    choice = defaultdict(dict)
    for rid, ck, name, party, bname, wi in con.execute("SELECT race_id, choice_key, name, party, ballot_name, write_in FROM choices "
                                                       "WHERE race_id LIKE ?", (pre + "%",)):
        choice[rid][ck] = (name, party, bname, wi)
    tie = {}
    for rid, chs in choice.items():
        if rid not in spec:
            continue
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
        for letter in ("D", "R"):
            fr = [k for k, c in enumerate(cands) if c.get("p") == letter]
            sl = [ck for ck, (n_, party, b_, wi) in chs.items() if not wi and party_letter(party) == letter and m.get(ck) is None]
            if len(fr) == 1 and len(sl) == 1 and fr[0] not in m.values():
                m[sl[0]] = fr[0]
        tie[rid] = m

    def county_of(unit):
        k = kinds.get(unit)
        if k == "county" and re.fullmatch(r"\d{5}", unit):
            return unit
        if k in ("precinct", "town", "ward") and re.fullmatch(r"\d{5}", str(parent.get(unit) or "")):
            return parent[unit]
        return None
    rep = defaultdict(dict)                      # race -> unit -> (in, all)
    for rid, unit, uin, uall in con.execute("SELECT race_id, unit_id, units_in, units_all FROM latest_reporting WHERE race_id LIKE ?",
                                            (pre + "%",)):
        if rid in spec:
            rep[rid][unit] = (uin, uall)
    raw = defaultdict(lambda: defaultdict(lambda: defaultdict(dict)))     # race -> unit -> type -> choice -> votes
    for rid, unit, ck, vt, v in con.execute("SELECT race_id, unit_id, choice_key, vote_type, votes FROM latest_counts WHERE race_id LIKE ?",
                                            (pre + "%",)):
        if rid in spec:
            raw[rid][unit][vt][ck] = v
    out, unmatched_votes = {}, 0
    for rid, sp in spec.items():
        n = len(sp["cands"])
        m = tie.get(rid, {})

        def vec(by_choice):
            row = [0] * (n + 1)
            for ck, v in by_choice.items():
                k = m.get(ck)
                row[n if k is None else k] += int(v or 0)
            return row
        units = raw.get(rid) or {}
        r_rep = rep.get(rid) or {}
        whole = {}
        if "all" in units:
            whole = {"t": {TYPE_OF.get(vt, vt) if vt != "total" else "total": vec(bc) for vt, bc in units["all"].items()},
                     "in": (r_rep.get("all") or (None, None))[0], "all": (r_rep.get("all") or (None, None))[1]}
        cty = {}
        prec = defaultdict(lambda: [0, 0])
        own_row = {u for u in units if u != "all" and kinds.get(u) == "county" and county_of(u)}
        for unit, by_type in units.items():
            if unit == "all":
                continue
            c = county_of(unit)
            if c is None:
                continue
            if c in own_row and unit != c:
                continue                          # the county's own row carries its votes; its precincts say how complete
            d = cty.setdefault(c, {"t": {}, "in": None, "all": None})
            for vt, bc in by_type.items():
                t = TYPE_OF.get(vt, vt) if vt != "total" else "total"
                row = vec(bc)
                if t in d["t"]:
                    d["t"][t] = [a + b for a, b in zip(d["t"][t], row)]
                else:
                    d["t"][t] = row
        for unit, (i, a) in r_rep.items():
            c = county_of(unit)
            if c and kinds.get(unit) == "county":
                cty.setdefault(c, {"t": {}, "in": None, "all": None})
                cty[c]["in"], cty[c]["all"] = i, a
            elif c and kinds.get(unit) == "precinct":       # a precinct reports whole: in or not
                prec[c][0] += 1 if (i or 0) > 0 else 0
                prec[c][1] += 1
        for c, (i, a) in prec.items():
            d = cty.setdefault(c, {"t": {}, "in": None, "all": None})
            if d["all"] is None:
                d["in"], d["all"] = i, a
        o = {"units": {}, "whole": whole}
        if cty:
            o["units"] = cty
        elif whole:
            o["units"] = {"ST": whole}
        if o["units"]:
            out[rid] = o
        for ck, k in m.items():
            if k is None and not (choice.get(rid, {}).get(ck) or (None, None, None, 1))[3]:
                unmatched_votes += sum(units.get(u, {}).get("total", {}).get(ck, 0) for u in units if u == "all")
    return out, {"unmatched_votes": unmatched_votes}


def regions_of(con, state):
    """{county: its region} from the store's House contests: each county in the congressional district holding most of its
    precincts (or its votes). The state's districts are its regions where it has two to fourteen of them."""
    st = state.upper()
    size = defaultdict(dict)
    for rid, unit, uall in con.execute("SELECT r.race_id, r.unit_id, r.units_all FROM latest_reporting r JOIN units u ON u.unit_id = r.unit_id "
                                       "AND u.state = ? WHERE r.race_id LIKE ? AND u.kind = 'county'", (st, f"2026-{st}-H%")):
        if re.fullmatch(r"2026-[A-Z]{2}-H\d+", rid):
            size[unit][rid] = max(size[unit].get(rid, 0), uall or 0)
    for rid, unit, v in con.execute("SELECT c.race_id, c.unit_id, SUM(c.votes) FROM latest_counts c JOIN units u ON u.unit_id = c.unit_id "
                                    "AND u.state = ? WHERE c.race_id LIKE ? AND c.vote_type = 'total' AND u.kind = 'county' "
                                    "GROUP BY c.race_id, c.unit_id", (st, f"2026-{st}-H%")):
        if re.fullmatch(r"2026-[A-Z]{2}-H\d+", rid) and not size[unit].get(rid):
            size[unit][rid] = 1e-6 * (v or 0) + 1e-9
    return {c: max(d, key=lambda r: (d[r], r)) for c, d in size.items() if d}


# ============================================================================================== the joint swing fit

def fit(G, prior_prec, prior_mean, rows, nC, sigma_u2):
    """The Gaussian posterior of the global terms (G of them) and each county's own shift, from observation rows
    [(global terms [(index, value)], county index or None, y, variance)]. The counties' block is diagonal, so the global
    block is solved by its Schur complement. Returns {"g", "cov", "C" (each county's mean given the global terms at their
    mean), "cd" (its variance given them), "a" (its coefficients on them: C_c(g) = C_c - a_c . (g - g_hat))}."""
    Pgg = [[0.0] * G for _ in range(G)]
    bg = [0.0] * G
    for j in range(G):
        Pgg[j][j] = prior_prec[j]
        bg[j] = prior_prec[j] * prior_mean[j]
    Dc = [1.0 / sigma_u2] * nC
    bc = [0.0] * nC
    pgc = [dict() for _ in range(nC)]
    for idx, c, y, var in rows:
        w = 1.0 / var
        for a, va in idx:
            bg[a] += w * va * y
            row = Pgg[a]
            for b, vb in idx:
                row[b] += w * va * vb
        if c is not None:
            Dc[c] += w
            bc[c] += w * y
            pc = pgc[c]
            for a, va in idx:
                pc[a] = pc.get(a, 0.0) + w * va
    M = [row[:] for row in Pgg]
    rhs = bg[:]
    for c in range(nC):
        pc = pgc[c]
        if not pc:
            continue
        dc = Dc[c]
        items = list(pc.items())
        for a, va in items:
            ra = M[a]
            for b, vb in items:
                ra[b] -= va * vb / dc
            rhs[a] -= va * bc[c] / dc
    cov = inverse_spd(M)
    g = [sum(cov[a][b] * rhs[b] for b in range(G)) for a in range(G)]
    C, cd, A = [], [], []
    for c in range(nC):
        pc = pgc[c]
        C.append((bc[c] - sum(v * g[a] for a, v in pc.items())) / Dc[c])
        cd.append(1.0 / Dc[c])
        A.append({a: v / Dc[c] for a, v in pc.items()})
    return {"g": g, "cov": cov, "C": C, "cd": cd, "a": A}


# ============================================================================================== turnout and the votes still out

def mean_shift(weights, leans, target):
    """The shift mu at which the weighted average of expit(lean + mu) equals target (Newton's method)."""
    tw = sum(weights) or 1.0
    t = min(max(target, 1e-4), 1 - 1e-4)
    mu = logit(t)
    for _ in range(30):
        f = sum(w * expit(l + mu) for w, l in zip(weights, leans)) / tw - t
        d = sum(w * expit(l + mu) * (1 - expit(l + mu)) for w, l in zip(weights, leans)) / tw
        if d <= 1e-12:
            break
        step = f / d
        mu -= step
        if abs(step) < 1e-10:
            break
    return mu


def unit_complete(K, p, V, kind):
    """Whether a unit's count is whole but for a few late ballots: every precinct in, in a state where that ends the count
    (not an all-mail state); where mail is counted after the precincts ("late"), only once the votes counted come near the
    county's expected turnout too, since no feed says when a county's mail is all in."""
    if p is None or p < 0.999 or kind == "mail":
        return False
    return kind != "late" or K >= 0.97 * V


def _phi(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _excess(V, c, s):
    """E[V X - c | V X >= c] for X lognormal with mean 1 and log spread s: the votes still out, on average, given that the
    final total is at least what is already counted."""
    if c <= 0:
        return V - c
    d1 = (math.log(V / c) + s * s / 2) / s
    d2 = d1 - s
    p = _phi(d2)
    if p < 1e-12:
        # far in the tail: the mean excess of a lognormal beyond c is about c s^2 / log(c / V)
        return c * s * s / max(math.log(c / V), 1e-6)
    return max((V * _phi(d1) - c * p) / p, 0.0)


def expected_rest(V, c, s):
    """The votes a unit still has to count, on average, when its final total is V times a turnout surprise of log spread s
    (mean 1) and c are counted, given that the final total cannot be less than c (so a unit whose count has passed its
    expected turnout still has a few votes out, never none), and its elasticity to turnout (d log rest / d log V).
    Returns (rest, elasticity)."""
    if V <= 0:
        return 0.0, 0.0
    if s <= 1e-6:
        r = max(V - c, 0.0)
        return r, (V / r if r > 0 else 0.0)
    r = _excess(V, c, s)
    if r <= 1e-9:
        return 0.0, 0.0
    h = 0.01
    up, dn = _excess(V * math.exp(h), c, s), _excess(V * math.exp(-h), c, s)
    el = (math.log(max(up, 1e-9)) - math.log(max(dn, 1e-9))) / (2 * h)
    return r, max(el, 0.0)


def unit_remaining(t, p, V, kind, typed, prm, pi, s=0.14):
    """The votes still out in one unit of one race, by kind of ballot: (expected final total, {kind or "total": votes still
    out}, complete?, elasticity of the votes still out to turnout). t: {kind or "total": votes counted [..., other]}; p: the
    share of the unit's precincts in (None when the feed does not say); V: the expected total (turnout factor applied);
    s: the log spread of that expected total (the statewide factor's and the unit's own)."""
    late, eds = prm["late"].get(kind, 0.02), prm["ed_share"].get(kind, 0.6)
    K = sum((t.get("total") or [0])) if "total" in t else sum(sum(v) for k, v in t.items() if k != "total")
    if K <= 0:
        return V, ({b: pi[b] * V for b in pi} if typed else {"total": V}), False, 1.0
    complete = unit_complete(K, p, V, kind)
    if complete:
        rem = late * K
        return K + rem, ({b: rem * pi[b] for b in pi} if typed else {"total": rem}), True, 0.0
    if typed:
        # a kind released whole once posted (BATCH: early and mail ballots in a state that releases them first) leaves only
        # its late ballots; the other kinds not yet in (mail counted later, provisional) take their share of the expected
        # votes less what they have counted; Election Day takes what turnout leaves, moved toward what its own precincts say
        batch = BATCH.get(kind, ())
        Kb = {b: sum(t.get(b) or [0]) for b in pi}
        miss = {}
        for b in pi:
            if b in batch and Kb.get(b, 0) > 0:
                miss[b] = late * Kb[b]
        open_ = [b for b in pi if b not in miss]
        # what the county's expected turnout leaves for the kinds still open (its expected positive part)
        rest, el = expected_rest(V, K + sum(miss.values()), s)
        # each open kind's own shortfall against its expected share of the county's votes says how to split that rest
        gaps = {b: max(pi[b] * V - Kb.get(b, 0), 0.0) for b in open_}

        def split(total, kinds):
            g_tot = sum(gaps[b] for b in kinds)
            if g_tot > 0:
                return {b: total * gaps[b] / g_tot for b in kinds}
            s_tot = sum(pi[b] for b in kinds) or 1.0
            return {b: total * pi[b] / s_tot for b in kinds}
        K_ed = Kb.get("election_day", 0)
        if "election_day" in open_ and p is not None and (p >= 0.999 or (p > 0 and K_ed > 0)):
            # Election Day pinned by its own precincts: the share of them in says how much of it is still out
            if p >= 0.999:
                ed = late * K_ed
            else:
                ed = p * (K_ed * (1 - p) / max(p, 0.05)) + (1 - p) * split(rest, open_)["election_day"]
                ed = max(ed, (1 - p) * 0.25 * K_ed / max(p, 0.05))
            miss["election_day"] = ed
            left = max(rest - ed, 0.0)
            miss.update(split(left, [b for b in open_ if b != "election_day"]))
            tot = sum(miss.values()) or 1.0
            el = (el * left + 0.3 * ed) / tot                  # the pinned part follows its precincts more than turnout
        else:
            miss.update(split(rest, open_))
            if "election_day" in open_ and p is not None and p < 0.999:
                miss["election_day"] = max(miss["election_day"], (1 - p) * 0.25 * pi["election_day"] * V)
        return K + sum(miss.values()), miss, False, min(el, 6.0)
    floor = 0.0
    if kind == "mail":
        floor = late * K
    elif p is not None and p < 1:
        floor = (1 - p) * eds * V
    if kind == "precinct" and p is not None and p > 0.05:
        V = p * (K / p) + (1 - p) * V
    rest, el = expected_rest(V, K, s)
    if floor > rest:
        rest, el = floor, 0.5
    return K + rest, {"total": rest}, False, min(el, 6.0)


# ============================================================================================== the night's entries

def night_entries(code, specs, base, obs, prm, regions=None, typed_mix=None, say=quiet):
    """The frame's races from the races' priors (race_specs), each county's past votes (baseline), the votes counted
    (observations) and the night's parameters. The same code serves the night (run) and the replays (replays).
    Returns (entries, report)."""
    t0 = time.time()
    kind = order_kind(code)
    sp_by = {s["race"]: s for s in specs}
    counties = base["c"]
    # ---- the units of each race, and how much of each county a district race holds
    part = {}
    house_cty = defaultdict(set)
    for rid, o in obs.items():
        if rid in sp_by and sp_by[rid].get("house"):
            for u in o["units"]:
                if u != "ST":
                    house_cty[u].add(rid)
    for s in specs:
        rid = s["race"]
        o = obs.get(rid) or {"units": {}}
        us = [u for u in o["units"] if u != "ST"]
        if s.get("house"):
            if us:
                sizes = {}
                for u in us:
                    a = o["units"][u].get("all")
                    sizes[u] = a
                part[rid] = {}
                for u in us:
                    others = house_cty.get(u, {rid})
                    a = sizes[u]
                    tot_a = sum((obs.get(r2, {}).get("units", {}).get(u, {}).get("all") or 0) for r2 in others)
                    if a and tot_a:
                        part[rid][u] = a / tot_a
                    else:
                        part[rid][u] = 1.0 / max(len(others), 1)
            else:
                part[rid] = {"ST": 1.0}
        else:
            known = [u for u in us if u in counties]
            if us and len(known) >= 0.8 * len(us):
                # the feed's counties are the past votes' counties: every county of the state, counted or not yet listed
                part[rid] = {u: 1.0 for u in set(us) | set(counties)}
            elif us:
                part[rid] = {u: 1.0 for u in us}     # units the past votes do not know: their own figures only
            else:
                part[rid] = {"ST": 1.0}
    # ---- the unit index: every county any race uses
    unit_ids = sorted({u for d in part.values() for u in d})
    upos = {u: i for i, u in enumerate(unit_ids)}
    nC = len(unit_ids)

    def cinfo(u):
        c = counties.get(u)
        if c is None:
            return 0.0, 0.0, [0.0] * len(FEATURES), None
        return c["L"] or 0.0, c["sw"] or 0.0, c["Z"], c["w"]
    # ---- each race's expected votes in each of its units, and its prior shift in county space
    def counted_in(rid, u):
        return sum(((((obs.get(rid) or {}).get("units") or {}).get(u) or {}).get("t") or {}).get("total") or [0])
    V0, lean_u, mu = {}, {}, {}
    order = [s for s in specs if not s.get("house")] + [s for s in specs if s.get("house")]
    anchor = None
    for s in order:
        rid = s["race"]
        d = part[rid]
        us = sorted(d)
        votes = float(s.get("votes") or 0.0) or 1.0
        if s.get("house") and anchor and any(u in V0[anchor] for u in us):
            # a district's part of a county: its votes counted against the statewide race's in the same county (both are
            # counted together, so the ratio says how much of the county the district holds and how many skip it);
            # before either is counted, the share of the county's precincts the district holds
            vals = {}
            for u in us:
                ka, kr = counted_in(anchor, u), counted_in(rid, u)
                ratio = min(max(kr / ka, 0.02), 1.2) if (ka > 0 and kr > 0) else 0.95 * d[u]
                vals[u] = V0[anchor].get(u, 0.0) * ratio
            if sum(vals.values()) > 0:
                V0[rid] = vals
                ws = [vals[u] for u in us]
                ls = [cinfo(u)[0] for u in us]
                lean_u[rid] = dict(zip(us, ls))
                mu[rid] = mean_shift(ws, ls, expit(s["m"])) if s["kind"] == "partisan" else 0.0
                continue
        ws, ls = [], []
        for u in us:
            L, _sw, _Z, w = cinfo(u)
            if w is None:                       # a unit the past votes do not know: its size from what it has counted
                k_u = counted_in(rid, u)
                w = (k_u / votes) if k_u else 0.0
            ws.append(max(w * d[u], 0.0))
            ls.append(L)
        tw = sum(ws)
        if tw <= 0:
            ws = [1.0 / len(ws)] * len(ws)
            tw = 1.0
        V0[rid] = {u: votes * w / tw for u, w in zip(us, ws)}
        lean_u[rid] = dict(zip(us, ls))
        mu[rid] = mean_shift(ws, ls, expit(s["m"])) if s["kind"] == "partisan" else 0.0
        if not s.get("house") and len(us) > 1 and (anchor is None or sum(counted_in(rid, u) for u in us) >
                                                   sum(counted_in(anchor, u) for u in V0[anchor])):
            anchor = rid                        # the statewide race counted furthest, county by county
    # ---- the kinds of ballot reported, and their mix
    typed_units = set()
    present = set()
    for rid, o in obs.items():
        for u, d in o["units"].items():
            ks = [k for k in d["t"] if k != "total"]          # a kind the feed lists counts, even before any of it is in
            if ks:
                typed_units.add((rid, u))
                present.update(ks)
    types = [t for t in TYPES if t in present]
    pi = dict(typed_mix or {})
    if types:
        base_mix = {t: prm["mix"].get(t, 0.05) for t in types}
        tot = sum(base_mix.values()) or 1.0
        prior_pi = {t: v / tot for t, v in base_mix.items()}
        # the mix seen tonight in the units whose every precinct is in and every main kind of ballot has votes (not one
        # whose mail is still to come), weighed against the prior as 50,000 votes
        seen = defaultdict(float)
        main = [t for t in types if t not in ("provisional", "other")]
        for (rid, u) in typed_units:
            d = obs[rid]["units"][u]
            K_u = sum(sum(d["t"].get(t) or [0]) for t in types)
            if (d.get("all") and d.get("in") is not None and all(sum(d["t"].get(t) or [0]) > 0 for t in main)
                    and unit_complete(K_u, d["in"] / d["all"], V0.get(rid, {}).get(u) or 0.0, kind)):
                for t in types:
                    seen[t] += sum(d["t"].get(t) or [0])
        n_seen = sum(seen.values())
        pi = {t: (seen[t] + 50000.0 * prior_pi[t]) / (n_seen + 50000.0) for t in types}
    # ---- turnout: a statewide factor from the units that are complete
    tu = prm["turn"]
    num, den = 0.0, 1.0 / tu["sd_state"] ** 2
    for s in specs:
        rid = s["race"]
        o = obs.get(rid)
        if not o:
            continue
        for u, d in o["units"].items():
            V = V0[rid].get(u)
            if not V:
                continue
            K = sum(d["t"].get("total") or [0]) if "total" in d["t"] else 0
            p = (d["in"] / d["all"]) if d.get("all") else None
            # turnout is learned only where a whole count can be seen (every precinct in, the count ended by it): not in an
            # all-mail state, nor where mail is counted after the precincts
            if K > 0 and kind not in ("mail", "late") and unit_complete(K, p, V, kind):
                w = 1.0 / (tu["sd_unit"] ** 2)
                num += w * math.log((K + 1.0) / (V + 1.0))
                den += w
    log_tau, var_tau = num / den, 1.0 / den
    tau = math.exp(log_tau)
    # ---- the remaining votes of each race in each unit
    rem, complete, q, el_u, final, ped = {}, {}, {}, {}, {}, {}
    s_unit = math.sqrt(var_tau + tu["sd_unit"] ** 2)
    for s in specs:
        rid = s["race"]
        o = obs.get(rid) or {"units": {}}
        rem[rid], complete[rid], q[rid], el_u[rid], final[rid], ped[rid] = {}, {}, {}, {}, {}, {}
        for u, V in V0[rid].items():
            d = o["units"].get(u) or {"t": {}, "in": None, "all": None}
            if "total" not in d["t"] and d["t"]:
                d["t"]["total"] = [sum(x) for x in zip(*d["t"].values())]
            p = (d["in"] / d["all"]) if d.get("all") else None
            typed = (rid, u) in typed_units
            fin, miss, comp, el = unit_remaining(d["t"], p, V * tau, kind, typed, prm, pi if typed else {"total": 1.0}, s_unit)
            rem[rid][u], complete[rid][u], el_u[rid][u], final[rid][u] = miss, comp, el, fin
            K = sum(d["t"].get("total") or [0])
            q[rid][u] = (K / fin) if fin > 0 else 0.0
            # Election Day part counted where the feed gives kinds apart: its precincts' share in (None: not said, or none
            # of it counted, or all of it)
            k_ed = sum(d["t"].get("election_day") or [0]) if typed else 0
            ped[rid][u] = p if (typed and k_ed > 0 and p is not None and 0 < p < 0.999) else None
    # ---- the global terms
    pspecs = [s for s in specs if s["kind"] == "partisan"]
    reg_list = sorted({r for r in (regions or {}).values()})
    use_reg = 2 <= len(reg_list) <= 14
    gi = {"g0": 0}
    for s in pspecs:
        gi["e:" + s["race"]] = len(gi)
    if use_reg:
        for r in reg_list:
            gi["r:" + r] = len(gi)
    gi["beta"] = len(gi)
    for f in FEATURES:
        gi["z:" + f] = len(gi)
    for t in types:
        gi["d:" + t] = len(gi)
    gi["gap"] = len(gi)
    gi["gap_ed"] = len(gi)
    G = len(gi)
    prec, pmean = [0.0] * G, [0.0] * G
    var_g = max(min((s["var_g"] for s in pspecs), default=0.02), 0.0004)
    prec[0] = 1.0 / var_g
    for s in pspecs:
        prec[gi["e:" + s["race"]]] = 1.0 / max(s["v"] - var_g, 0.03 ** 2)
    if use_reg:
        for r in reg_list:
            prec[gi["r:" + r]] = 1.0 / prm["tau_r"] ** 2
    prec[gi["beta"]] = 1.0 / prm["tau_beta"] ** 2
    for f in FEATURES:
        prec[gi["z:" + f]] = 1.0 / prm["tau_b"] ** 2
    tprior = prm.get("type_prior") or {}
    for t in types:
        if t in tprior:                                  # how this kind of ballot leaned before tonight (the replays' counts)
            prec[gi["d:" + t]] = 1.0 / prm.get("type_prior_sd", 0.35) ** 2
            pmean[gi["d:" + t]] = float(tprior[t])
        else:
            prec[gi["d:" + t]] = 1.0 / prm["tau_d"] ** 2
    gap_sd = prm["gap_sd"].get(kind, 0.12)
    prec[gi["gap"]] = 1.0 / gap_sd ** 2
    prec[gi["gap_ed"]] = 1.0 / prm["gap_ed_sd"] ** 2

    def design(rid, u, t, a_gap, a_ged=0.0):
        L, sw, Z, _w = cinfo(u)
        idx = [(0, 1.0)]
        if ("e:" + rid) in gi:
            idx.append((gi["e:" + rid], 1.0))
        if use_reg and (regions or {}).get(u) in reg_list:
            idx.append((gi["r:" + regions[u]], 1.0))
        if sw:
            idx.append((gi["beta"], sw))
        for j, f in enumerate(FEATURES):
            if Z[j]:
                idx.append((gi["z:" + f], Z[j]))
        if t in pi and t != "total" and types:
            for t2 in types:
                v = (1.0 if t2 == t else 0.0) - pi.get(t2, 0.0)
                if v:
                    idx.append((gi["d:" + t2], v))
        if a_gap:
            idx.append((gi["gap"], a_gap))
        if a_ged:
            idx.append((gi["gap_ed"], a_ged))
        return idx

    def noise(s, u):
        if not s.get("house"):
            return prm["sigma_sw"] ** 2
        return (prm["sigma_split"] if len(house_cty.get(u, ())) > 1 else prm["sigma_part"]) ** 2
    rows = []
    typed_rows = []
    obs_rc = {}
    st2 = prm["sigma_typed"] ** 2
    for s in pspecs:
        rid = s["race"]
        o = obs.get(rid)
        if not o:
            continue
        iD, iR = s["iD"], s["iR"]
        for u, d in o["units"].items():
            if u not in upos:
                continue
            typed = (rid, u) in typed_units
            blocks = [(t, v) for t, v in d["t"].items() if t != "total"] if typed else [("total", d["t"].get("total") or [])]
            for t, v in blocks:
                if not v:
                    continue
                D, Rv = v[iD], v[iR]
                n2 = D + Rv
                if n2 < 1:
                    continue
                ph = (D + 0.5) / (n2 + 1.0)
                binom = 1.0 / ((n2 + 1.0) * ph * (1 - ph))
                y = logit(ph) - mu[rid] - lean_u[rid].get(u, 0.0)
                a_gap = (1.0 - q[rid][u]) if (not typed and not complete[rid][u]) else 0.0
                a_ged = (1.0 - ped[rid][u]) if (typed and t == "election_day" and ped[rid][u] is not None) else 0.0
                idx = design(rid, u, t, a_gap, a_ged)
                # a kind of ballot in one county leans its own way beyond the state's lean for that kind (shared by the
                # county's races): in the noise here, and carried to that kind's ballots still out in the county below
                var = binom + noise(s, u) + (st2 if typed else 0.0)
                rows.append((idx, upos[u], y, var))
                if typed:
                    typed_rows.append((rid, u, t, idx, upos[u], y, binom + noise(s, u)))
            tot = d["t"].get("total") or []
            if tot and tot[iD] + tot[iR] >= 1:
                n2 = tot[iD] + tot[iR]
                ph = (tot[iD] + 0.5) / (n2 + 1.0)
                obs_rc[(rid, u)] = (logit(ph) - mu[rid] - lean_u[rid].get(u, 0.0), 1.0 / ((n2 + 1.0) * ph * (1 - ph)),
                                    {t: sum(v) for t, v in d["t"].items() if t != "total"} if typed else None)
    F = fit(G, prec, pmean, rows, nC, prm["sigma_u"] ** 2)
    g, cov = F["g"], F["cov"]

    def pred(idx, c):
        return sum(g[a] * v for a, v in idx) + (F["C"][c] if c is not None else 0.0)
    # ---- each race's own residual in each county counted (its candidates there), kept for the votes still out there
    eta = {}
    for (rid, u), (y, binom, tmix) in obs_rc.items():
        s = sp_by[rid]
        sig2 = noise(s, u)
        if tmix:
            tot = sum(tmix.values()) or 1.0
            p_hat = sum(pred(design(rid, u, t, 0.0, (1.0 - ped[rid][u]) if (t == "election_day" and ped[rid][u] is not None) else 0.0),
                             upos[u]) * n / tot for t, n in tmix.items())
        else:
            a_gap = (1.0 - q[rid][u]) if not complete[rid][u] else 0.0
            p_hat = pred(design(rid, u, "total", a_gap), upos[u])
        k = sig2 / (sig2 + binom)
        eta[(rid, u)] = ((y - p_hat) * k, sig2 * (1 - k))
    # ---- each county's own lean of each kind of ballot, from what is left once the race's own residual is taken out
    acc = defaultdict(lambda: [0.0, 0.0])
    for rid, u, t, idx, c, y, var in typed_rows:
        res = y - pred(idx, c) - eta.get((rid, u), (0.0, 0.0))[0]
        acc[(u, t)][0] += res / var
        acc[(u, t)][1] += 1.0 / var
    eta_t = {key: (sw / (w + 1.0 / st2), 1.0 / (w + 1.0 / st2)) for key, (sw, w) in acc.items()}
    # ---- the entries
    typed_races = {rid for (rid, _u) in typed_units}
    entries, counts = [], defaultdict(int)
    surface_units = sum(1 for (rid, u) in obs_rc if not sp_by[rid].get("house"))
    for s in specs:
        rid = s["race"]
        o = obs.get(rid) or {"units": {}}
        cands = s["cands"]
        n = len(cands)
        C = [0.0] * n
        cwi = 0.0
        units_in = units_all = 0
        any_rep = False
        for u, d in o["units"].items():
            tot = d["t"].get("total") or [0] * (n + 1)
            for k in range(n):
                C[k] += tot[k]
            cwi += tot[n] if len(tot) > n else 0
            if d.get("all") is not None:
                any_rep = True
                units_in += d.get("in") or 0
                units_all += d.get("all") or 0
        whole = o.get("whole") or {}
        if not any_rep and whole.get("all") is not None:
            units_in, units_all = whole.get("in") or 0, whole.get("all") or 0
        counted = sum(C) + cwi
        R_tot = sum(sum(m.values()) for m in rem[rid].values())
        # the turnout spread of the votes still out: the statewide factor and each unit's own
        rsd2 = 0.0
        if R_tot > 0:
            # the statewide turnout factor moves every unit's votes still out together, each by its elasticity (fully where
            # nothing is counted yet, far more where a unit is near its expected turnout and its rest is small); each unit's
            # own turnout moves its part alone
            corr = ind = 0.0
            for u, m in rem[rid].items():
                x = sum(m.values()) / R_tot
                e_ = el_u[rid][u]
                sdu = tu["sd_prior_unit"] if sum(((o["units"].get(u) or {}).get("t") or {}).get("total") or [0]) <= 0 else tu["sd_unit"]
                corr += x * e_
                ind += (x * e_ * sdu) ** 2
            rsd2 = var_tau * corr * corr + ind + 0.03 ** 2
        all_done = all(complete[rid].values()) and bool(complete[rid])
        status = "done" if (all_done and R_tot <= 0.005 * max(counted, 1.0)) else ("counting" if counted > 0 else "pre")
        e = {"race": rid, "kind": s["kind"], "status": status, "seats": 1, "rule": s["rule"], "typed": rid in typed_races,
             "cands": [{"key": c["key"], "name": c["name"], "p": c["p"]} for c in cands],
             "units_in": units_in, "units_all": units_all or None, "counted": int(round(counted)), "C": [int(round(x)) for x in C],
             "Cwi": int(round(cwi)), "R": r6(R_tot), "Rsd": r4(math.sqrt(max(rsd2, 0.0))), "tested": s.get("tested")}
        if s["kind"] == "partisan":
            iD, iR = s["iD"], s["iR"]
            k0 = prm["other"]["k0"]
            oth_c = counted - C[iD] - C[iR]
            oth = (oth_c + k0 * s.get("oth_prior", 0.02)) / (counted + k0)
            minors = [k for k in range(n) if k not in (iD, iR)]
            mix_raw = [C[k] + 1.0 for k in minors] + [cwi + 0.5]
            if not counted:
                mix_raw = [1.0 for _k in minors] + [0.2]
            ms = sum(mix_raw)
            hsum = [0.0] * G
            Wc = defaultdict(float)
            T_tot = Tp = wpp = 0.0
            noise_v = 0.0
            sw2 = prm["sigma_w"] ** 2
            batch = BATCH.get(kind, ())
            ou = o["units"]
            for u, miss in rem[rid].items():
                c = upos.get(u)
                eta_m, eta_v = eta.get((rid, u), (0.0, noise(s, u)))
                w_ru = 0.0                              # the race's own gap in the county is one draw for all its kinds
                tt = ((ou.get(u) or {}).get("t") or {})
                for t, R_u in miss.items():
                    if R_u <= 0:
                        continue
                    typed = (rid, u) in typed_units
                    a_gap = (-q[rid][u]) if (not typed and q[rid][u] > 0 and not complete[rid][u]) else 0.0
                    a_ged = (-ped[rid][u]) if (typed and t == "election_day" and ped[rid][u] is not None) else 0.0
                    idx = design(rid, u, t if typed else "total", a_gap, a_ged)
                    x = mu[rid] + lean_u[rid].get(u, 0.0) + pred(idx, c) + eta_m
                    tv = 0.0
                    if typed:
                        tm, tv = eta_t.get((u, t), (0.0, st2))
                        x += tm
                    # the part of a block still out, where part of it is counted, leans its own way against the part counted
                    # (precincts within a county differ): one draw of its own for each county
                    k_part = sum(tt.get(t if typed else "total") or [0])
                    if k_part > 0 and not complete[rid][u] and not (typed and t in batch):
                        tv += sw2
                    p_ = expit(x)
                    T = R_u * (1.0 - oth)
                    w = T * p_ * (1 - p_)
                    T_tot += T
                    Tp += T * p_
                    wpp += w
                    w_ru += w
                    for a, v in idx:
                        hsum[a] += w * v
                    if c is not None:
                        Wc[c] += w
                    noise_v += w * w * tv
                noise_v += w_ru * w_ru * eta_v
            if T_tot > 0 and wpp > 0:
                s0 = Tp / T_tot
                kap = wpp / (T_tot * s0 * (1 - s0))
                h = hsum[:]
                for c, wcv in Wc.items():
                    for a, v in F["a"][c].items():
                        h[a] -= wcv * v
                var = sum(h[a] * cov[a][b] * h[b] for a in range(G) for b in range(G) if h[a] and h[b])
                var += sum(wcv * wcv * F["cd"][c] for c, wcv in Wc.items())
                var += noise_v
                # the votes still out are never as typical as many independent counties would make them: one shared draw
                sp = prm.get("scale_typed", prm["scale_p"]) if rid in typed_races else prm["scale_p"]
                ve = sp * sp * (var / (wpp * wpp) + prm.get("sigma_xi", 0.0) ** 2)
                e.update(s0=r6(s0), kap=r6(kap), ve=r6(ve))
            else:
                e.update(s0=0.5, kap=1.0, ve=0.0)
            e.update(iD=iD, iR=iR, minors=minors, mix=[r4(x / ms) for x in mix_raw], oth=r4(oth),
                     oth_sd=prm["other"]["sd_many"] if counted > 2000 else prm["other"]["sd_few"])
            counts["partisan " + ("counted" if counted else "none counted")] += 1
        else:
            mp = prm["multi"]
            mu0 = list(s["mu"])
            tau_m = s.get("tau", mp["tau"])
            if counted > 0:
                tot_named = sum(C)
                ell = [math.log((C[k] + 0.5) / (tot_named + 0.5 * n)) for k in range(n)]
                n_rep = max(1.0, float(sum(1 for d in o["units"].values() if sum(d["t"].get("total") or [0]) > 0)))
                sh2, rho = mp["sigma_h"] ** 2, mp["rho"]
                v_base = sh2 * ((1 - rho) / n_rep + rho)
                mu_c, ell_c = sum(mu0) / n, sum(ell) / n
                post, sds = [], []
                for k in range(n):
                    v_rep = v_base + 1.0 / (C[k] + 1.0)
                    pr = 1.0 / (tau_m * tau_m) + 1.0 / v_rep
                    post.append(((mu0[k] - mu_c) / (tau_m * tau_m) + (ell[k] - ell_c) / v_rep) / pr)
                    sds.append(math.sqrt(1.0 / pr + sh2 * rho))
                wi = (cwi + 200 * s.get("wi_prior", 0.01)) / (counted + 200)
                e.update(mu=[r6(x) for x in post], sd=[r6(x) for x in sds], wi=r4(wi))
            else:
                e.update(mu=[r6(x) for x in mu0], sd=[r6(tau_m)] * n, wi=r4(s.get("wi_prior", 0.01)))
            counts["multi " + ("counted" if counted else "none counted")] += 1
        entries.append(e)
    # ---- what the statewide races (else every race) counted so far say against the forecast there, for the words
    def gap_of(keep):
        got = exp_ = tw = 0.0
        for (rid, u), (_y, _binom, _tm) in obs_rc.items():
            s = sp_by[rid]
            if not keep(s):
                continue
            tot = obs[rid]["units"][u]["t"].get("total") or []
            n2 = tot[s["iD"]] + tot[s["iR"]] if tot else 0
            if n2 > 0:
                got += tot[s["iD"]]
                exp_ += n2 * expit(mu[rid] + lean_u[rid].get(u, 0.0))
                tw += n2
        return got, exp_, tw
    got, exp_, tw = gap_of(lambda s: not s.get("house"))
    gap_scope = "statewide"
    if not tw:
        got, exp_, tw = gap_of(lambda s: True)
        gap_scope = "all"
    report = {"kind": kind, "units": nC, "types": types, "mix": {t: r4(v) for t, v in pi.items()} if types else None,
              "regions": len(reg_list) if use_reg else 0, "turnout": r4(tau), "turnout_sd": r4(math.sqrt(var_tau)),
              "surface_units": surface_units, "counted_gap_pts": r4((got - exp_) / tw * 100) if tw else None, "gap_scope": gap_scope,
              "by_county": any(u != "ST" for (_r, u) in obs_rc),
              "statewide_shift": r4(g[0]), "statewide_sd": r4(math.sqrt(cov[0][0])), "gap": r4(g[gi["gap"]]),
              "race_shift": {s["race"]: r4(g[0] + g[gi["e:" + s["race"]]]) for s in pspecs},
              "type_lean": {t: r4(g[gi["d:" + t]] - sum(pi[t2] * g[gi["d:" + t2]] for t2 in types)) for t in types} if types else None,
              "races": dict(counts), "built_in": round(time.time() - t0, 3)}
    return entries, report


def predictive_two_party(e):
    """A partisan entry's final Democratic share of the two-party vote, as a mean and a standard deviation, by the same
    terms simulate_us.py draws (linearised): for scoring the replays at many spreads without drawing."""
    C = e["C"]
    iD, iR = e["iD"], e["iR"]
    o = e.get("oth") or 0.0
    T = (e.get("R") or 0.0) * (1 - o)
    s0 = e.get("s0", 0.5)
    T2 = C[iD] + C[iR] + T
    if T2 <= 0:
        return 0.5, 0.25
    F = (C[iD] + T * s0) / T2
    dF = T * s0 * (1 - s0) * e.get("kap", 1.0) / T2
    var = dF * dF * (e.get("ve") or 0.0) + (T * (s0 - F) / T2) ** 2 * (e.get("Rsd") or 0.0) ** 2
    return F, math.sqrt(max(var, 1e-10))


# ============================================================================================== the frame and the run

def public_words(code, pre_public, report, prm, params_run, rules):
    """What the forecasts page may say about a night run, in plain words (no file or program names)."""
    out = dict(pre_public or {})
    name = state_name(code)
    typed = bool(report.get("types"))
    out["night"] = ("On election night the model compares each county counted so far with what the forecast expected there, "
                    "learns how the vote has moved (statewide, in each region, with each county's swing between 2022 and 2024 and "
                    "its Census figures), and estimates the counties and ballots still out. Each race's own results so far set "
                    "how far it runs ahead of or behind the others.") if report.get("by_county", report.get("units", 0) > 1) else (
                    f"On election night {name}'s figures read here are statewide totals, so the model compares the count so far "
                    f"with what the forecast expected and estimates the ballots still out from the state's way of counting.")
    gap = report.get("counted_gap_pts")
    where = "counties" if report.get("by_county") else "votes"
    races = "the statewide races" if report.get("gap_scope") == "statewide" else "the races"
    out["night_now"] = (f"In the {where} counted so far, the Democrats' share of the two-party vote in {races} is {abs(gap):.1f} points "
                        f"{'above' if gap >= 0 else 'below'} what the forecast expected in those same {where}."
                        if gap is not None else "No race with a Democrat and a Republican has been counted yet.")
    out["count_order"] = order_words(code, typed)
    if typed:
        tl = report.get("type_lean") or {}
        parts = [f"{TYPE_WORDS.get(t, t)} {abs(v) * 25:.1f} points {'more' if v >= 0 else 'less'} Democratic" for t, v in tl.items()
                 if v is not None and abs(v) >= 0.02]
        if parts:
            out["types_now"] = ("Against each county's whole vote tonight, the model reads " + "; ".join(parts) + ".")
    out["turnout_night"] = ("Expected votes in each county come from 2022's turnout, moved by how complete counties are turning out "
                            "tonight; the votes still out follow the state's way of counting (precincts still to report, kinds of "
                            "ballot not yet in, mail still arriving).")
    out["night_tested"] = ((f"Sized by replays of the 2024 general in Florida, North Carolina, Pennsylvania, Louisiana and Georgia, "
                            f"counted in each state's own order{(' (' + prm.get('summary') + ')') if prm.get('summary') else ''}.")
                           if params_run else "The night's spreads are starting values; the replays that size them have not been run.")
    if rules:
        out["rules"] = dict(out.get("rules") or {}, **rules)
    return json.loads(R.scrub(R.canonical(out)))


def tested_words(s, fitted):
    t = s.get("tested") or ""
    if not fitted:
        return t
    return t + "; on election night, sized by replays of the 2024 general counted in each state's own order"


def run(state, now=None, db=None, rehearsal=False, say=say_default, model_db=MODEL_DB, draws=DRAWS, dry=False, params=None,
        params_run=None):
    """One night run for a state (not Minnesota) from its results so far, stored as a version (runs.py, kind "live",
    method US_LIVE_METHOD). Returns a summary."""
    from election import store
    t0 = time.time()
    st = state.upper()
    if st in SKIP:
        return {"skipped": "Minnesota has its own night model"}
    started = R.now_utc()
    as_of = now or started
    if isinstance(as_of, dt.datetime) and as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=dt.timezone.utc)
    pre_run, got = newest_pre(model_db, st)
    if not got:
        return {"skipped": "no pre-election forecast on file"}
    frame_pre, frame_sha = got
    specs = race_specs(st, frame_pre)
    if not specs:
        return {"skipped": "no forecast race"}
    db = db or store.DB
    if not os.path.exists(db):
        return {"skipped": "no results database"}
    con = sqlite3.connect(db)
    con.execute("PRAGMA busy_timeout = 30000")
    try:
        obs, info = observations(con, st, specs)
        snap = snapshot_info(con, st)
        regions = regions_of(con, st)
        certified = {r for (r,) in con.execute("SELECT DISTINCT race_id FROM certified WHERE race_id LIKE ?", (f"2026-{st}-%",))}
    finally:
        con.close()
    counted_any = any(sum((d["t"].get("total") or [0])) > 0 or any(sum(v) > 0 for v in d["t"].values())
                      for o in obs.values() for d in o["units"].values())
    if not counted_any:
        return {"skipped": "no votes counted"}
    if params is None:
        params, params_run = night_params(model_db)
    base = baseline(st, 2026)
    specs = [s for s in specs if s["race"] not in certified]
    entries, report = night_entries(st, specs, base, obs, params, regions)
    for e in entries:
        s = next(x for x in specs if x["race"] == e["race"])
        e["tested"] = tested_words(s, bool(params_run))
    for rid in sorted(certified):
        entries.append({"race": rid, "kind": "multi", "status": "not-modelled", "seats": 1, "cands": [],
                        "note": "certified: the official count decides; no forecast after certification"})
    rules = {s["race"]: rule_words(st, s["rule_name"]) for s in specs if rule_words(st, s["rule_name"])}
    frame = {"v": 1, "state": st, "kind": "live", "method": US_LIVE_METHOD, "as_of": R.iso(as_of), "pre_run": pre_run,
             "pre_frame": frame_sha, "results": snap, "params": params, "params_run": params_run, "races": entries,
             "report": report, "public": public_words(st, frame_pre.get("public"), report, params, params_run, rules)}
    frame = json.loads(R.canonical(frame))
    inputs = [
        {"input": "results", "source": f"results store, snapshot {snap['snapshot']}" if snap else "results store",
         "sha256": (snap or {}).get("sha256"), "as_of": (snap or {}).get("at"), "kind": "official",
         "note": "the counts as the state's office posted them (read only)"},
        {"input": "pre-run", "source": f"run {pre_run}", "sha256": frame_sha, "as_of": frame_pre.get("as_of"), "kind": "derived",
         "note": "the pre-election forecast the night starts from"},
        {"input": "night-params", "source": f"replay run {params_run}" if params_run else "starting values (no replay on file)",
         "sha256": R.sha_text(R.canonical(frame["params"])), "as_of": None, "kind": "derived" if params_run else "prior",
         "note": frame["params"].get("source")},
        {"input": "county-baseline", "source": "MEDSL's copies of the 2022 and 2024 official returns by county; ACS 2020-2024 county figures",
         "sha256": R.sha_text(R.canonical(base)), "as_of": None, "kind": "secondary",
         "note": "how each county voted before, and its Census figures (secondary sources, labelled)"},
    ]
    con = R.connect(model_db)
    try:
        run_id = R.new_run_id(con, "live", st, started)
        seed = R.seed_of(run_id)
        t1 = time.time()
        out = S.simulate(frame, seed, draws)
        sim_s = time.time() - t1
        if dry:
            return {"run": run_id, "out": out, "frame": frame, "seconds": round(time.time() - t0, 2), "simulate_s": round(sim_s, 2)}
        with con:
            res = R.record_run(con, run=run_id, state=st, kind="live", method=US_LIVE_METHOD, seed=seed, draws=draws, started=started,
                               as_of=as_of, frame=frame, outputs=out, inputs=inputs, rehearsal=rehearsal,
                               note=f"election-night forecast from {(snap or {}).get('snapshot')}; starts from {pre_run}; "
                                    f"parameters from {params_run or 'starting values'}")
    finally:
        con.close()
    secs = round(time.time() - t0, 2)
    say(f"    {st} night run {run_id}: {res['races']} races, {res['written']} with new rows, {secs} s")
    return {"run": run_id, **res, "seconds": secs, "simulate_s": round(sim_s, 2), "report": report}


# ============================================================================================== the replays of past generals

REPLAY_DIR = os.path.join(HERE, "election_cache", "replay", "sources")
DUMP_SHARE = 0.7             # Florida's file gives county totals only: this share of each county's votes is taken as its
                             # early and mail ballots, released first (an assumption, said so on the track record)
REPLAY_STATES = ("FL", "NC", "PA", "LA", "GA")
NC_OTHER = ("NC LIEUTENANT GOVERNOR", "NC ATTORNEY GENERAL", "NC AUDITOR", "NC COMMISSIONER OF AGRICULTURE",
            "NC COMMISSIONER OF INSURANCE", "NC COMMISSIONER OF LABOR", "NC SECRETARY OF STATE",
            "NC SUPERINTENDENT OF PUBLIC INSTRUCTION", "NC TREASURER")
PA_OFFICES = {"5": ("ag", "other"), "6": ("aud", "other"), "7": ("tre", "other")}


class _Race:
    """One past contest read from a state's own files: its candidates (each name as printed, its party) and its votes by
    unit and kind of ballot (write-ins and lines of no candidate kept apart as "other")."""

    def __init__(self, code, key, cls, dist=None):
        self.code, self.key, self.cls, self.dist = code, key, cls, dist
        self.rid = f"2024-{code}-{key}"
        self.cands, self.pos = [], {}
        self.votes = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))     # unit -> kind -> candidate index or -1
        self._final = None

    def add(self, unit, kind, name, party, votes, write_in=False):
        self._final = None
        if write_in or not str(name or "").strip():
            k = -1
        else:
            nk = name_key(name)
            if nk not in self.pos:
                self.pos[nk] = len(self.cands)
                self.cands.append({"key": re.sub(r"[^a-z0-9]+", "-", str(name).lower()).strip("-")[:48] or f"c{len(self.cands)}",
                                   "name": re.sub(r"\s+", " ", str(name)).strip(), "p": party_letter(party)})
            k = self.pos[nk]
        self.votes[unit][kind][k] += int(votes or 0)

    def final(self):
        """{unit: {kind: [votes of each candidate ..., other]}} (kept once made)."""
        if self._final is not None:
            return self._final
        n = len(self.cands)
        out = {}
        for u, by in self.votes.items():
            out[u] = {}
            for t, d in by.items():
                row = [0] * (n + 1)
                for k, v in d.items():
                    row[n if k < 0 else k] += v
                out[u][t] = row
        self._final = out
        return out


def _src_fl():
    from election.readers import _common_n11 as K
    from election.readers import fl_watch as FW
    from election.replay import load_final
    files = load_final(os.path.join(REPLAY_DIR, "fl-20241105"))
    _n, body = K.file_named(files.items(), "ElecResultsFL")
    races, prec = {}, {}
    for r in FW.rows_of(body):
        code = r["RaceCode"]
        if code == "PRE":
            key, cls, dist = "pres", "usprs", None
        elif code == "USS":
            key, cls, dist = "ussen", "ussen", None
        elif code == "USR":
            dist = int(K.num(r["Juris1num"]) or 0)
            key, cls = f"usrep-{dist:02d}", "usrep"
        else:
            continue
        fips = K.county_unit("FL", r["CountyName"])
        if not fips:
            continue
        rc = races.setdefault(key, _Race("FL", key, cls, dist))
        rc.add(fips, "total", FW.person(r), r["PartyCode"], int(r["CanVotes"] or 0), write_in=(r["PartyCode"] == "WRI"))
        prec[fips] = max(prec.get(fips, 0), int(r["Precincts"] or 0))
    return {"code": "FL", "year": 2024, "typed": False, "statewide": False, "races": races, "prec": prec, "top": "pres",
            "label": "Florida's 2024 general election (the Division of Elections' election-night file, county totals)"}


def _src_nc():
    from election.readers import _common_n11 as K
    from election.readers import nc_sbe as N
    from election.replay import load_final
    files = load_final(os.path.join(REPLAY_DIR, "nc-20241105"))
    cfile = next(n for n in files if n.endswith("county.txt"))
    cname = {c["cid"]: c["cnm"] for c in N._counties(files[cfile])}
    races, prec = {}, {}
    for n, b in files.items():
        m = re.search(r"results_(\d+)\.txt$", n)
        if not m or m.group(1) == "0":
            continue
        fips = K.county_unit("NC", cname.get(m.group(1)))
        if not fips:
            continue
        for r in N._rows(b):
            title = re.sub(r"\s+", " ", re.sub(r"\s*\(VOTE FOR \d+\)\s*$", "", (r.get("cnm") or "").strip().upper()))
            if title == "US PRESIDENT":
                key, cls = "pres", "usprs"
            elif title == "NC GOVERNOR":
                key, cls = "gov", "governor"
            elif title in NC_OTHER:
                key, cls = re.sub(r"[^a-z]+", "-", title.lower().replace("nc ", "")).strip("-"), "other"
            else:
                continue
            rc = races.setdefault(key, _Race("NC", key, cls))
            wi = bool(re.search(r"write[- ]?in", r.get("bnm") or "", re.I))
            for f, t in (("evc", "election_day"), ("ovc", "early"), ("avc", "mail"), ("pvc", "provisional")):
                rc.add(fips, t, r.get("bnm"), r.get("pty"), int(r.get(f) or 0), wi)
            prec[fips] = max(prec.get(fips, 0), int(r.get("ptl") or 0))
    return {"code": "NC", "year": 2024, "typed": True, "statewide": False, "races": races, "prec": prec, "top": "pres",
            "label": "North Carolina's 2024 general election (the State Board's results files, by county and kind of ballot)"}


def _src_pa():
    from election.readers import _common_n11 as K
    from election.readers import pa_returns as P
    from election.replay import load_final
    files = load_final(os.path.join(REPLAY_DIR, "pa-105G"))
    dnum, races = {}, {}
    for n, b in files.items():
        m = re.search(r"GetOfficeData__officeId=(\d+)", n)
        if not m:
            continue
        for d in P.districts(P.unjson(b)):
            dnum[(m.group(1), d["id"])] = int(K.num(d["name"]) or 0)
            if m.group(1) == "2":                              # the U.S. Senate: statewide figures only
                rc = _Race("PA", "ussen", "ussen")
                for cd in d["cands"]:
                    for f, t in (("ElectionDayVotes", "election_day"), ("MailInVotes", "mail"), ("ProvisionalVotes", "provisional")):
                        rc.add("ST", t, P.printed(cd), cd.get("PartyName"), int(cd.get(f) or 0))
                races["ussen"] = rc
    for n, b in files.items():
        m = re.search(r"GetCountyBreak__officeId=(\d+)_districtId=(\d+)", n)
        if not m:
            continue
        oid, did = m.group(1), m.group(2)
        if oid in PA_OFFICES:
            key, cls, dist = PA_OFFICES[oid][0], PA_OFFICES[oid][1], None
        elif oid == "11":
            dist = dnum.get((oid, did))
            if not dist:
                continue
            key, cls = f"usrep-{dist:02d}", "usrep"
        else:
            continue
        rc = races.setdefault(key, _Race("PA", key, cls, dist))
        doc = P.unjson(b)
        for _dname, blocks in (doc.get("Election") or {}).items():
            for block in blocks:
                for county, plist in block.items():
                    fips = K.county_unit("PA", county)
                    if not fips:
                        continue
                    for cd in P.cands(plist):
                        for f, t in (("ElectionDayVotes", "election_day"), ("MailInVotes", "mail"), ("ProvisionalVotes", "provisional")):
                            rc.add(fips, t, P.printed(cd), cd.get("PartyName"), int(cd.get(f) or 0))
    return {"code": "PA", "year": 2024, "typed": True, "statewide": False, "races": races, "prec": {}, "top": "ag",
            "label": "Pennsylvania's 2024 general election (the Department of State's returns, by county and kind of ballot)"}


def _src_la():
    from election.readers import la_portal as LA
    from election.replay import load_final
    files = load_final(os.path.join(REPLAY_DIR, "la-20241105"))
    rc_doc = next(json.loads(b.decode("utf-8-sig")) for n, b in files.items() if "RacesCandidates_Multiparish" in n)
    vo_doc = next(json.loads(b.decode("utf-8-sig")) for n, b in files.items() if "Votes_Multiparish" in n)
    pres = next(r for r in LA.as_list(rc_doc["Races"].get("Race")) if "President" in (r.get("SpecificTitle") or ""))
    vote = next(v for v in LA.as_list(vo_doc["Races"].get("Race")) if v["ID"] == pres["ID"])
    desc = {c["ID"]: LA.split_desc(c.get("Desc")) for c in LA.as_list(pres.get("Choice"))}
    rc = _Race("LA", "pres", "usprs")
    for ch in LA.as_list(vote.get("Choice")):
        name, party = desc.get(ch.get("ID"), (None, None))
        rc.add("ST", "total", name, party, int(ch.get("VoteTotal") or 0))
    return {"code": "LA", "year": 2024, "typed": False, "statewide": True, "races": {"pres": rc}, "prec": {"ST": 64}, "top": "pres",
            "label": "Louisiana's 2024 presidential count (the Secretary of State's statewide figures)"}


def _src_ga():
    from election.readers import _n10_common as C
    p = os.path.join(REPLAY_DIR, "ga-2024NovGen", "results.sos.ga.gov", "results", "public", "api", "elections", "Georgia",
                     "2024NovGen", "data")
    with open(p, encoding="utf-8-sig") as fh:
        d = json.load(fh)
    item = next(it for it in d["ballotItems"] if C.text_of(it.get("name")).startswith("President") and not it.get("parentId"))
    rc = _Race("GA", "pres", "usprs")
    for o in ((item.get("summaryResults") or {}).get("ballotOptions")) or []:
        pty = o.get("party") or {}
        party = C.text_of(pty.get("name")) or pty.get("standardName") or pty.get("abbreviation")
        name = C.text_of(o.get("name"))
        for g in o.get("groupResults") or []:
            t = TYPE_OF.get(C.vote_type(C.text_of(g.get("groupName"))), "other")
            rc.add("ST", t, name, party, int(g.get("voteCount") or 0), write_in=bool(o.get("isWriteIn")))
    total_units = ((item.get("reportingStatus") or {}).get("totalUnits")) or 159
    return {"code": "GA", "year": 2024, "typed": True, "statewide": True, "races": {"pres": rc}, "prec": {"ST": int(total_units)},
            "top": "pres", "label": "Georgia's 2024 presidential count (the Secretary of State's statewide figures, by kind of ballot)"}


SOURCES = {"FL": _src_fl, "NC": _src_nc, "PA": _src_pa, "LA": _src_la, "GA": _src_ga}
_HOUSE_2024 = {}


def _bt_specs(src, params):
    """Each replayed race's prior as the night would have had it before the vote: the state's 2020 presidential share with
    a wide spread and no polls (the other states' backtest's "pre" scenario), each office's own spread, a sitting senator's
    edge, and for the House a district's lean from 2022 (other_states.past_house_2024). Nothing of 2024 is used."""
    from election.model import data_us as U
    from election.model import other_states as OS
    code = src["code"]
    d20, r20, all20 = U.president(2020)[code]
    G = logit(d20 / (d20 + r20))
    var_G = OS.PRIORS["env_no_polls_sd"] ** 2 + params["state_sd"] ** 2
    members = U.members_on(U.ELECTION_DAY[2024], "Senate")
    if not _HOUSE_2024:
        houses, _skip = OS.past_house_2024(params, say=quiet)
        _HOUSE_2024.update({h["id"]: h for h in houses})
    h22 = U.clerk(2022)["states"].get(code, {}).get("house", {})
    h22_tot = sum(sum(v or 0 for _n, _p, v in h["cands"]) for h in h22.values()) or 1
    office_sd = params["office_sd"]
    minor = params.get("minor") or {}
    specs = []
    for _key, rc in sorted(src["races"].items()):
        cands = rc.cands
        p = [c["p"] for c in cands]
        if p.count("D") != 1 or p.count("R") != 1:
            continue
        sp = {"race": rc.rid, "class": rc.cls, "cands": cands, "tested": "replay", "rule": "plurality", "rule_name": "plurality",
              "house": rc.cls == "usrep", "kind": "partisan", "iD": p.index("D"), "iR": p.index("R"), "var_g": var_G}
        if rc.cls == "usprs":
            sp.update(m=G, v=var_G, votes=all20)
        elif rc.cls == "ussen":
            inc = sum((1 if c["p"] == "D" else -1 if c["p"] == "R" else 0) for c in cands if U.sitting(c["name"], code, members))
            b, bsd = params["inc_sw"]
            sp.update(m=G + b * inc, v=var_G + office_sd["ussen"] ** 2 + (bsd * inc) ** 2, votes=all20)
        elif rc.cls in ("governor", "other"):
            sp.update(m=G, v=var_G + office_sd.get(rc.cls, office_sd["other"]) ** 2, votes=all20)
        else:
            h = _HOUSE_2024.get(f"2024-{code}-usrep-{rc.dist:02d}")
            if not h:
                continue
            gap, inc, dsd = params["gap"]["usrep"], params["inc"], params["district_sd"]["usrep"]
            lean = OS.lean_of(h, params)
            old = h22.get(str(rc.dist)) or {}
            votes = sum(v or 0 for _n, _p, v in old.get("cands") or []) * all20 / h22_tot if old else all20 / max(len(h22), 1)
            sp.update(m=G + gap[0] + inc[0] * h["inc_dir"] + lean, v=var_G + gap[1] ** 2 + (inc[1] * h["inc_dir"]) ** 2 + dsd ** 2,
                      votes=votes)
        prior = minor.get("statewide", [-3.6, 0.9, 0.1]) if rc.cls != "usrep" else minor.get("with_majors", [-3.2, 0.9, 0.15])
        n_o = sum(1 for x in p if x not in ("D", "R"))
        sp["oth_prior"] = min(n_o * math.exp(prior[0] + prior[1] ** 2 / 2), 0.3) + (params.get("writein") or {}).get("partisan", 0.002)
        specs.append(sp)
    return specs


def _parts_of(src):
    """How a replayed unit's count is split for the reveal: kinds of ballot where the files give them; for a county total
    in a state that releases its early and mail ballots first, "_dump" (DUMP_SHARE) and "_ed"; else "_all"."""
    if src["typed"]:
        return None
    if ORDER.get(src["code"]) == "dump" and not src["statewide"]:
        return {"_dump": DUMP_SHARE, "_ed": 1 - DUMP_SHARE}
    return {"_all": 1.0}


def _plan(src, seed):
    """The pieces a past count is revealed in, in the state's own order (ORDER, from its registry note): [(unit, part,
    share of that part)], each unit's pieces arriving in a drawn order among the others'."""
    rng = random.Random(f"night-us-replay-{src['code']}-{seed}")
    kind = ORDER.get(src["code"], "unknown")
    units = ["ST"] if src["statewide"] else sorted({u for rc in src["races"].values() for u in rc.votes if u != "ST"})
    if src["typed"]:
        kinds = sorted({t for rc in src["races"].values() for by in rc.votes.values() for t in by})
        first = [t for t in kinds if t in FIRST.get(kind, ())]
        ed = [t for t in kinds if t == "election_day" and t not in first]
        later = [t for t in kinds if t not in first and t not in ed and t != "provisional"]
        prov = [t for t in kinds if t == "provisional"]
        n_first = 3 if src["statewide"] else 1
        n_ed = 6 if src["statewide"] else 3
        a = [(u, t, 1.0 / n_first) for u in units for t in first for _ in range(n_first)]
        rng.shuffle(a)
        b = [(u, t, 1.0 / n_ed) for u in units for t in ed for _ in range(n_ed)]
        rng.shuffle(b)
        c = [(u, t, 0.5) for u in units for t in later for _ in range(2)]
        rng.shuffle(c)
        if kind == "late" and c:
            # mail later: the first half of the Election Day pieces alone, then the rest mixed with the mail pieces
            half = len(b) // 2
            rest = b[half:] + c
            rng.shuffle(rest)
            pieces = a + b[:half] + rest
        else:
            pieces = a + b + c
        return pieces + [(u, t, 1.0) for u in units for t in prov]
    parts = _parts_of(src)
    if "_dump" in parts:
        a = [(u, "_dump", 1.0) for u in units]
        rng.shuffle(a)
        b = [(u, "_ed", 1.0 / 3) for u in units for _ in range(3)]
        rng.shuffle(b)
        return a + b
    pieces = [(u, "_all", 0.1) for u in units for _ in range(10)]
    rng.shuffle(pieces)
    return pieces


def _share_of(src, frac, u, t):
    """The share of a unit's votes of one kind counted, with the revealed shares `frac` ({(unit, part): share})."""
    if src["typed"]:
        return min(frac.get((u, t), 0.0), 1.0)
    return min(sum(w * frac.get((u, p), 0.0) for p, w in _parts_of(src).items()), 1.0)


def _kind_shares(src, frac):
    """For a race with statewide figures only in a state replayed county by county: the share of each kind of ballot the
    counties have counted (weighed by the top race's votes)."""
    top = src["races"][src["top"]].final()
    num, den = defaultdict(float), defaultdict(float)
    for u, by in top.items():
        for t, row in by.items():
            tot = sum(row)
            num[t] += tot * _share_of(src, frac, u, t)
            den[t] += tot
    return {t: (num[t] / den[t]) if den[t] else 0.0 for t in den}


def _counted(src, frac, rc):
    """A replayed race's votes counted at a moment: {unit: {kind: [...]}}."""
    out = {}
    shares = None
    for u, by in rc.final().items():
        if u == "ST" and not src["statewide"]:
            shares = shares or _kind_shares(src, frac)
            out[u] = {t: [int(v * shares.get(t, 0.0)) for v in row] for t, row in by.items()}
            continue
        out[u] = {t: [int(v * _share_of(src, frac, u, t)) for v in row] for t, row in by.items()}
    return out


def _reporting(src, u, frac):
    """(in, all) of a unit at a moment: the share of its Election Day (or whole) count in, of its precincts."""
    a = src["prec"].get(u) or 100
    if src["typed"]:
        p = frac.get((u, "election_day"), 0.0)
    elif "_ed" in (_parts_of(src) or {}):
        p = frac.get((u, "_ed"), 0.0)
    else:
        p = frac.get((u, "_all"), 0.0)
    p = min(p, 1.0)
    return (a if p >= 0.999 else int(a * p)), a


def _top_share(src, frac):
    rc = src["races"][src["top"]]
    fin = rc.final()
    total = sum(sum(row) for by in fin.values() for row in by.values()) or 1
    got = sum(sum(row) * _share_of(src, frac, u, t) for u, by in fin.items() for t, row in by.items())
    return got / total


def replay_points(src, seed=7, cps=CHECKPOINTS):
    """The moments a past count is scored at: [(checkpoint, share of the top race counted, {(unit, part): share})], each the
    first moment in the state's own order at which the top race's count reaches the checkpoint."""
    pieces = _plan(src, seed)
    frac = defaultdict(float)
    out, k = [], 0
    for cp in cps:
        share = _top_share(src, frac)
        while k < len(pieces) and share < cp:
            u, part, f = pieces[k]
            frac[(u, part)] = min(frac[(u, part)] + f, 1.0)
            k += 1
            share = _top_share(src, frac)
        out.append((cp, share, dict(frac)))
    return out


def replay_obs(src, frac, specs):
    """The night's observations of every replayed race at one moment, in the shape observations() gives."""
    obs = {}
    rcs = {rc.rid: rc for rc in src["races"].values()}
    for s in specs:
        rc = rcs[s["race"]]
        units = {}
        for u, by in _counted(src, frac, rc).items():
            t = dict(by)
            if "total" not in t:
                t["total"] = [sum(x) for x in zip(*by.values())]
            i, a = _reporting(src, u, frac) if (u != "ST" or src["statewide"]) else (None, None)
            units[u] = {"t": t, "in": i, "all": a}
        obs[s["race"]] = {"units": units, "whole": {}}
    return obs


def truth_of(rc):
    n = len(rc.cands)
    tot = [0] * (n + 1)
    for by in rc.final().values():
        for row in by.values():
            for k in range(n + 1):
                tot[k] += row[k]
    return tot


def _regions_replay(src):
    """{county: its 2024 congressional district} from the replayed House contests (the district holding most of its votes)."""
    size = defaultdict(dict)
    for rc in src["races"].values():
        if rc.cls != "usrep":
            continue
        for u, by in rc.votes.items():
            size[u][str(rc.dist)] = sum(sum(d.values()) for d in by.values())
    return {u: max(d, key=lambda r: (d[r], r)) for u, d in size.items() if d}


def type_gaps(src, points=True):
    """How each kind of ballot leaned in a replayed count, against each county's whole vote (two-party log-odds, weighed
    by votes), in the top race: {kind: points of share near an even race} (or log-odds, points=False)."""
    if not src["typed"]:
        return {}
    rc = src["races"][src["top"]]
    p = [c["p"] for c in rc.cands]
    if p.count("D") != 1 or p.count("R") != 1:
        return {}
    iD, iR = p.index("D"), p.index("R")
    acc = defaultdict(lambda: [0.0, 0.0])
    for _u, by in rc.final().items():
        tot = [sum(x) for x in zip(*by.values())]
        if tot[iD] + tot[iR] < 100:
            continue
        lt = logit(tot[iD] / (tot[iD] + tot[iR]))
        for t, row in by.items():
            n2 = row[iD] + row[iR]
            if n2 < 50:
                continue
            acc[t][0] += n2 * (logit((row[iD] + 0.5) / (n2 + 1)) - lt)
            acc[t][1] += n2
    return {t: (round(s / w * 25, 1) if points else round(s / w, 4)) for t, (s, w) in acc.items() if w}


def predictive_parts(e):
    """(mean, spread from the lean, spread from turnout) of a partisan entry's final two-party share, at the entry's own
    spread (predictive_two_party, its two parts kept apart so the spread can be scaled)."""
    C = e["C"]
    iD, iR = e["iD"], e["iR"]
    o = e.get("oth") or 0.0
    T = (e.get("R") or 0.0) * (1 - o)
    s0 = e.get("s0", 0.5)
    T2 = C[iD] + C[iR] + T
    if T2 <= 0:
        return 0.5, 0.25, 0.0
    F = (C[iD] + T * s0) / T2
    dF = T * s0 * (1 - s0) * e.get("kap", 1.0) / T2
    return F, abs(dF) * math.sqrt(max(e.get("ve") or 0.0, 0.0)), abs(T * (s0 - F) / T2) * (e.get("Rsd") or 0.0)


def score_rows(src, entries, sims, cp, share):
    """One row per replayed race with votes still out: the Democrat's chance, share and ranges against the official end."""
    rcs = {rc.rid: rc for rc in src["races"].values()}
    rows = []
    for e, sim in zip(entries, sims):
        if e.get("kind") != "partisan":
            continue
        rc = rcs[e["race"]]
        tot = truth_of(rc)
        T = sum(tot)
        if T <= 0:
            continue
        frac = (sum(e["C"]) + (e.get("Cwi") or 0)) / T
        if frac >= 0.999:
            continue
        iD = e["iD"]
        n = len(rc.cands)
        winner = max(range(n), key=lambda k: tot[k])
        cs = sim["cands"]
        d = cs[iD]
        actual = tot[iD] / T
        lead = max(range(n), key=lambda k: e["C"][k]) if sum(e["C"]) > 0 else None
        fav = max(range(n), key=lambda k: cs[k]["chance"])
        mg = sim.get("mg") or {}
        keys = [c["key"] for c in rc.cands]
        mg_held = None
        if mg.get("a") in keys and mg.get("b") in keys:
            a, b = keys.index(mg["a"]), keys.index(mg["b"])
            m_act = (tot[a] - tot[b]) / T
            mg_held = int(mg["q"][1] <= m_act <= mg["q"][2])
        rows.append({"race": e["race"], "cls": rc.cls, "state": src["code"], "cp": int(round(cp * 100)), "counted": share,
                     "frac": frac, "chance": d["chance"], "median": d["median"], "lo80": d["lo80"], "hi80": d["hi80"],
                     "lo95": d["lo95"], "hi95": d["hi95"], "actual": actual, "won": int(winner == iD),
                     "in80": int(d["lo80"] <= actual <= d["hi80"]), "in95": int(d["lo95"] <= actual <= d["hi95"]),
                     "leader_wrong": None if lead is None else int(lead != winner), "fav_wrong": int(fav != winner),
                     "mg_held": mg_held})
    return rows


def _measures(rows):
    n = len(rows)
    if not n:
        return {}
    lw = [r["leader_wrong"] for r in rows if r["leader_wrong"] is not None]
    mh = [r["mg_held"] for r in rows if r["mg_held"] is not None]
    return {"races": n, "cover80": round(sum(r["in80"] for r in rows) / n, 4), "cover95": round(sum(r["in95"] for r in rows) / n, 4),
            "brier": round(sum((r["chance"] - r["won"]) ** 2 for r in rows) / n, 4),
            "logloss": round(sum(-math.log(max(r["chance"] if r["won"] else 1 - r["chance"], 1e-4)) for r in rows) / n, 4),
            "leader_wrong": round(sum(lw) / len(lw), 4) if lw else None, "favourite_wrong": round(sum(r["fav_wrong"] for r in rows) / n, 4),
            "margin80": round(sum(mh) / len(mh), 4) if mh else None, "counted": round(sum(r["counted"] for r in rows) / n, 4),
            "miss_pts": round(sum(abs(r["median"] - r["actual"]) for r in rows) / n * 100, 2)}


def replays(say=say_default, db=MODEL_DB, store=True, draws=BT_DRAWS, states=REPLAY_STATES, scales=None):
    """The 2024 generals the readers hold, replayed in each state's own counting order and scored at 10, 25, 50, 75 and 90
    percent counted; the night's spread sized so that the 80 percent ranges hold about 80 percent of the time at every
    checkpoint; stored as a run of kind "replay", state "US" (the parameters run() reads, and the track record's report)."""
    from election.model import other_states as OS
    t0 = time.time()
    started = R.now_utc()
    params_us, params_run = OS.latest_params(db)
    srcs = []
    for code in states:
        try:
            src = SOURCES[code]()
        except (OSError, StopIteration, KeyError) as e:
            say(f"    {code}: its past files are not on this computer ({e.__class__.__name__}); left out")
            continue
        specs = _bt_specs(src, params_us)
        base = baseline(code, 2024)
        points = replay_points(src)
        srcs.append({"src": src, "specs": specs, "base": base, "points": points, "regions": _regions_replay(src)})
        say(f"    {code}: {len(specs)} races replayed ({', '.join(sorted({s['class'] for s in specs}))}); checkpoints at "
            + ", ".join(f"{int(cp * 100)}% ({sh * 100:.0f}% counted)" for cp, sh, _f in points))
    for S_ in srcs:
        S_["obs"] = {cp: replay_obs(S_["src"], frac, S_["specs"]) for cp, _share, frac in S_["points"]}

    def scored(scale, n_draws, scale_typed=None):
        """Every replayed race-moment scored at one spread (both families of feed at the same scale unless told)."""
        prm_s = merge(DEFAULT_NIGHT_US, {"scale_p": scale, "scale_typed": scale if scale_typed is None else scale_typed})
        out = []
        for S_ in srcs:
            src = S_["src"]
            for cp, share, _frac in S_["points"]:
                entries, _rep = night_entries(src["code"], S_["specs"], S_["base"], S_["obs"][cp], prm_s, S_["regions"])
                frame = json.loads(R.canonical({"method": US_LIVE_METHOD, "params": prm_s, "races": entries}))
                sim = S.simulate(frame, R.seed_of(f"night-us-replay-{src['code']}-{int(cp * 100)}"), n_draws)
                typed = {e["race"]: bool(e.get("typed")) for e in frame["races"]}
                for r in score_rows(src, frame["races"], sim["races"], cp, share):
                    r["typed"] = typed.get(r["race"], False)
                    out.append(r)
        return out
    # the spread, for each family of feed (kinds of ballot apart, or totals): the smallest scale at which the 80 percent
    # ranges of a candidate's share, as the page shows them, hold at least TARGET at every checkpoint (the family's states
    # together) and at least STATE_FLOOR within any one state of STATE_MIN races or more (a state's races miss together,
    # so a pooled figure alone can hide one state's miss), each scale tried through the simulation itself
    grid = scales or [round(0.5 + 0.1 * k, 2) for k in range(22)]
    chosen, table = {}, {"kinds apart": {}, "totals": {}}
    for s in grid:
        rs = scored(s, draws)
        for typed in (True, False):
            if typed in chosen:
                continue
            fam = [r for r in rs if r["typed"] == typed]
            if not fam:
                chosen[typed] = 1.0
                continue
            worst = worst_state = 1.0
            for cp in {r["cp"] for r in fam}:
                cell = [r for r in fam if r["cp"] == cp]
                worst = min(worst, sum(r["in80"] for r in cell) / len(cell))
                for code in {r["state"] for r in cell}:
                    zz = [r for r in cell if r["state"] == code]
                    if len(zz) >= STATE_MIN:
                        worst_state = min(worst_state, sum(r["in80"] for r in zz) / len(zz))
            table["kinds apart" if typed else "totals"][f"{s:.2f}"] = [round(worst, 3), round(worst_state, 3)]
            if worst >= TARGET and worst_state >= STATE_FLOOR:
                chosen[typed] = s
        if len(chosen) == 2:
            break
    for typed in (True, False):
        chosen.setdefault(typed, grid[-1])
        tab = table["kinds apart" if typed else "totals"]
        say(f"    the night's spread, feeds giving {'kinds of ballot apart' if typed else 'totals only'}: scale {chosen[typed]}; the worst "
            f"checkpoint's 80% coverage (all, and the worst state) by scale: " + ", ".join(f"{k} {v[0]:.2f}/{v[1]:.2f}" for k, v in tab.items()))
    type_prior = {}
    gaps = [type_gaps(S_["src"], points=False) for S_ in srcs if S_["src"]["typed"]]
    for t in sorted({t for g_ in gaps for t in g_}):
        vals = [g_[t] for g_ in gaps if t in g_]
        type_prior[t] = r4(sum(vals) / len(vals))
    prm = merge(DEFAULT_NIGHT_US, {"scale_p": chosen[False], "scale_typed": chosen[True]})
    rows = scored(chosen[False], draws, chosen[True])           # the very draws the spreads were chosen on
    by_cp = defaultdict(list)
    by_state = defaultdict(lambda: defaultdict(list))
    for r in rows:
        by_cp[r["cp"]].append(r)
        by_state[r["state"]][r["cp"]].append(r)
    report = {"what": ("The election-night model for the other states replayed on the 2024 general elections whose files this site's "
                       "readers hold, each counted in the state's own order, and scored at 10, 25, 50, 75 and 90 percent counted."),
              "checkpoints": [int(c * 100) for c in CHECKPOINTS], "target": TARGET,
              "scale": {"kinds apart": chosen[True], "totals": chosen[False]}, "worst_cover80_by_scale": table, "type_prior": type_prior,
              "all": {str(cp): _measures(rs) for cp, rs in sorted(by_cp.items())}, "states": {},
              "untested": [
                  "House races on lines first used in 2024 (North Carolina, Georgia and Louisiana): no earlier result describes them, so they were not replayed.",
                  "How counties' swings follow their past swing: the replays had one earlier election by county on file, so that term was not tested.",
                  "Florida's and Louisiana's files give totals only, not the kinds of ballot: their replays reveal early and late votes that lean alike, so they test the counties' order and turnout, not how early ballots lean.",
                  "States whose results this site reads as statewide totals only were replayed with Georgia's and Louisiana's presidential counts.",
                  "The real order of a past night is not on record: each replay follows the order the state's own rules describe, with the counties in a drawn order.",
                  "The spread was sized on these same replays, so how often its ranges held here is not a test it could fail."]}
    for S_ in srcs:
        src = S_["src"]
        code = src["code"]
        report["states"][code] = {"label": src["label"], "races": len(S_["specs"]), "order": order_words(code, src["typed"]),
                                  "kind": ORDER.get(code, "unknown"), "typed": src["typed"], "statewide": src["statewide"],
                                  "counted": {str(int(cp * 100)): round(sh, 3) for cp, sh, _f in S_["points"]},
                                  "cells": {str(cp): _measures(rs) for cp, rs in sorted(by_state[code].items())},
                                  "type_gaps": type_gaps(src)}
    worst = min(m["cover80"] for m in report["all"].values()) if report["all"] else None
    allm = _measures(rows)
    # for the nights to come (not the replays just scored): how each kind of ballot leaned in the 2024 counts replayed
    prm["type_prior"] = type_prior
    prm["fitted"] = True
    prm["source"] = f"replays of the 2024 general in {len(srcs)} states, each counted in its own order ({US_LIVE_METHOD})"
    prm["summary"] = (f"80 percent ranges held {allm.get('cover80', 0):.0%} of the time over {allm.get('races', 0)} race-moments, and at "
                      f"least {worst:.0%} at every stage of the count" if worst is not None else "no race was replayed")
    report["overall"] = allm
    report["seconds"] = round(time.time() - t0, 1)
    say(f"    replays: {allm.get('races', 0)} race-moments; 80% held {allm.get('cover80')}, 95% held {allm.get('cover95')}, "
        f"Brier {allm.get('brier')}, count leader not first {allm.get('leader_wrong')}, model favourite not first "
        f"{allm.get('favourite_wrong')}; {report['seconds']} s")
    for cp, m in sorted(report["all"].items(), key=lambda kv: int(kv[0])):
        say(f"      {cp}% counted: {m['races']} races, 80% held {m['cover80']:.2f}, 95% held {m['cover95']:.2f}, leader not first "
            f"{m['leader_wrong']}, favourite not first {m['favourite_wrong']}, margin range held {m['margin80']}")
    for code, sd in report["states"].items():
        say(f"      {code}: " + "; ".join(f"{cp}%: 80% held {m['cover80']:.2f} of {m['races']}, leader not first {m['leader_wrong']}"
                                         for cp, m in sorted(sd["cells"].items(), key=lambda kv: int(kv[0]))))
    doc = {"params": prm, "report": report, "method": US_LIVE_METHOD}
    if not store:
        return {"params": prm, "report": report, "rows": rows}
    con = R.connect(db)
    try:
        run_id = R.new_run_id(con, "replay", "US", started)
        with con:
            sha = R.put_blob(con, doc, "replay")
            con.execute("INSERT INTO runs (run, state, kind, method, code_sha, seed, draws, started, ended, as_of, rehearsal, frame_sha, "
                        "python, races, written, note) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (run_id, "US", "replay", US_LIVE_METHOD, R.keep_code(con, R.family("replay", US_LIVE_METHOD)), R.seed_of(run_id),
                         draws, R.iso(started), None, R.iso(started), 0, sha, __import__("platform").python_version(), len(rows), 0,
                         "the other states' night model replayed on the 2024 generals the readers hold, in each state's own order"))
            con.executemany("INSERT OR REPLACE INTO run_inputs (run, input, source, sha256, as_of, kind, note) VALUES (?,?,?,?,?,?,?)",
                            [(run_id, f"replay-{S_['src']['code'].lower()}", S_["src"]["label"], None, "2024-11-05", "official",
                              "the state's own files of its 2024 count, kept for rehearsals") for S_ in srcs] +
                            [(run_id, "priors", f"backtest run {params_run}" if params_run else "defaults", None, None, "derived",
                              "the other states' pre-election parameters, as they stood before 2024"),
                             (run_id, "frame", f"run_blobs:{sha}", sha, R.iso(started), "frame", "the night's parameters and the report")])
            meas = []
            for cp, m in report["all"].items():
                for k, v in m.items():
                    if v is not None:
                        meas.append((run_id, f"replay:own:{cp}", "all", k, float(v), m["races"], None))
            for code, sd in report["states"].items():
                for cp, m in sd["cells"].items():
                    for k, v in m.items():
                        if v is not None:
                            meas.append((run_id, f"replay:own:{cp}", f"{code} 2024", k, float(v), m["races"], None))
            con.executemany("INSERT OR REPLACE INTO calibration (run, scenario, grp, measure, value, n, note) VALUES (?,?,?,?,?,?,?)", meas)
            con.executemany("INSERT OR REPLACE INTO backtests (run, scenario, year, race, grp, choice, chance, median, lo80, hi80, lo95, hi95, "
                            "actual, won, base_inc, base_last) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                            [(run_id, f"replay:own:{r['cp']}", 2024, r["race"], r["cls"], "D", r["chance"], r["median"], r["lo80"], r["hi80"],
                              r["lo95"], r["hi95"], r["actual"], r["won"], None, None) for r in rows])
            con.execute("UPDATE runs SET ended = ?, written = ? WHERE run = ?", (R.iso(R.now_utc()), len(meas), run_id))
        say(f"    replay run {run_id} stored: {len(meas)} measures, {len(rows)} race-moments")
        return {"run": run_id, "params": prm, "report": report, "rows": rows}
    finally:
        con.close()


# ============================================================================================== made-up counts, for the checks

TYPED_FAMILIES = {"nc_sbe": ("early", "mail", "election_day", "provisional"), "pa_returns": ("election_day", "mail", "provisional"),
                  "civix": ("early", "election_day"), "ok_export": ("mail", "early", "election_day"),
                  "de_json": ("election_day", "mail", "early"), "md_pages": ("early", "election_day", "mail", "provisional")}
STATEWIDE_FAMILIES = ("enhanced_voting", "resultssw", "md_pages", "pcc_ems", "ak_csv", "hi_text", "dc_boe")


def live_states(model_db=MODEL_DB):
    """The states the updater reads (live, care or by hand) that have a pre-election forecast on file, Minnesota aside."""
    from election import registry
    reg = registry.load_all()
    have = set()
    if os.path.exists(model_db):
        con = sqlite3.connect(f"file:{model_db}?mode=ro", uri=True)
        try:
            have = {s for (s,) in con.execute("SELECT DISTINCT state FROM runs WHERE kind = 'pre' AND rehearsal = 0 AND ended IS NOT NULL")}
        finally:
            con.close()
    return sorted(c for c, e in reg.items() if c not in SKIP and c in have and (e or {}).get("status") in ("live", "care", "hand"))


def synthetic_store(results_db, codes, model_db=MODEL_DB, share=0.6, seed=11, say=quiet):
    """Made-up counts for every race with a forecast in each state, written into a scratch results database (test data,
    never the night's): each county's share drawn about the forecast, some counties complete, some part counted, some
    not yet in; kinds of ballot where the state's feed gives them; statewide totals only where its feed gives only those."""
    from election import registry, store
    reg = registry.load_all()
    con = store.connect(results_db)
    rng = random.Random(seed)
    made = {}
    try:
        for code in codes:
            _pre_run, got = newest_pre(model_db, code)
            if not got:
                continue
            specs = race_specs(code, got[0])
            fam = (reg.get(code) or {}).get("family") or ""
            kinds = TYPED_FAMILIES.get(fam) or (("early", "mail", "election_day") if code in ("GA", "RI") else ())
            statewide = fam in STATEWIDE_FAMILIES
            base = baseline(code, 2026)
            counties = sorted(base["c"]) if not statewide else []
            store.ensure_election(con, code, certifying_body="(scratch)")
            store.ensure_feed(con, code, f"{code.lower()}-test", "test", "made-up counts for a check", "test")
            shift = rng.gauss(0, 0.08)
            rep_of = {}
            for c in counties:
                r = rng.random()
                rep_of[c] = 1.0 if r < share * 0.7 else (rng.uniform(0.2, 0.8) if r < share * 1.15 else 0.0)
            sw_p = (sum(rep_of.values()) / len(rep_of)) if rep_of else share
            contests = []
            for s in specs:
                cands = s["cands"]
                n = len(cands)
                keys = [f"c{k}" for k in range(n)] + ["write-in"]
                choices = [{"key": keys[k], "name": c["name"], "party": {"D": "Democratic", "R": "Republican"}.get(c["p"], "Other"),
                            "ballot_name": c["name"], "write_in": False, "order": k + 1} for k, c in enumerate(cands)]
                choices.append({"key": "write-in", "name": "Write-in", "party": None, "ballot_name": None, "write_in": True, "order": n + 1})
                units = [{"id": "all", "kind": "race", "name": "the whole contest"}]
                rows, rep = [], []
                votes = float(s.get("votes") or 100000)
                if counties and not s.get("house"):
                    ulist = counties
                elif counties:
                    ulist = rng.sample(counties, min(len(counties), rng.randint(1, 6)))
                else:
                    ulist = []

                def split(V, p_c, lean):
                    pd = expit(lean)
                    row = [0] * (n + 1)
                    oth = 0.03 if n > 2 else 0.0
                    for k, cc in enumerate(cands):
                        if s["kind"] == "partisan":
                            row[k] = int(V * p_c * ((1 - oth) * pd if k == s["iD"] else (1 - oth) * (1 - pd) if k == s["iR"] else oth / max(n - 2, 1)))
                        else:
                            row[k] = int(V * p_c * (0.85 if cc["p"] in ("D", "R") else 0.15 / max(n - 1, 1)))
                    row[n] = int(V * p_c * 0.002)
                    return row
                tot_all = [0] * (n + 1)
                tp_all = defaultdict(lambda: [0] * (n + 1))
                n_in = n_all = 0
                for c in ulist:
                    w = base["c"][c]["w"] or 0.0
                    V = votes * (w if not s.get("house") else 1.0 / len(ulist))
                    p_c = rep_of.get(c, 0.0)
                    units.append({"id": c, "kind": "county", "name": c, "parent": code, "map_id": c})
                    row = split(V, p_c, (base["c"][c]["L"] or 0.0) + s.get("m", 0.0) + shift + rng.gauss(0, 0.08))
                    for k in range(n + 1):
                        rows.append({"unit": c, "choice": keys[k], "type": "total", "votes": row[k]})
                        tot_all[k] += row[k]
                    if kinds:
                        mix = [rng.uniform(0.2, 1.0) for _ in kinds]
                        ms = sum(mix)
                        left = list(row)
                        for j, t in enumerate(kinds):
                            part = [int(x * mix[j] / ms) for x in row] if j < len(kinds) - 1 else left
                            left = [x - y for x, y in zip(left, part)] if j < len(kinds) - 1 else left
                            for k in range(n + 1):
                                rows.append({"unit": c, "choice": keys[k], "type": t, "votes": part[k]})
                                tp_all[t][k] += part[k]
                    a = rng.randint(5, 80)
                    i = a if p_c >= 1 else int(a * p_c)
                    n_in, n_all = n_in + i, n_all + a
                    rep.append({"unit": c, "in": i, "all": a})
                if not ulist:
                    tot_all = split(votes, sw_p, s.get("m", 0.0) + shift)
                    for j, t in enumerate(kinds):
                        for k in range(n + 1):
                            tp_all[t][k] += tot_all[k] // len(kinds) + (tot_all[k] % len(kinds) if j == 0 else 0)
                    n_in, n_all = int(100 * sw_p), 100
                for k in range(n + 1):
                    rows.append({"unit": "all", "choice": keys[k], "type": "total", "votes": tot_all[k]})
                    for t, tp in tp_all.items():
                        rows.append({"unit": "all", "choice": keys[k], "type": t, "votes": tp[k]})
                rep.append({"unit": "all", "in": n_in, "all": n_all})
                contests.append({"race_id": s["race"], "key": s["race"], "office": s["race"], "level": "statewide", "district": None,
                                 "seats": 1, "rule": "plurality", "rcv": False, "unit_kind": "county", "units_all": len(ulist) or None,
                                 "choices": choices, "units": units, "rows": rows, "reporting": rep, "stated": [], "controls": []})
            reading = {"state": code, "feed": f"{code.lower()}-test", "source_time": "2026-11-04T03:50:00Z", "source_version": "test",
                       "contests": contests, "unmatched": [], "problems": []}
            sha = store.sha256_bytes(json.dumps([code, seed, share]).encode("utf-8"))
            sid, status = store.begin_snapshot(con, code, f"{code.lower()}-test", sha, source_time="2026-11-04T03:50:00Z")
            if status != "same":
                status, _checks = store.record(con, sid, reading)
            made[code] = {"races": len(contests), "status": status, "counties": len(counties)}
            say(f"    made-up counts for {code}: {len(contests)} races, {len(counties) or 'statewide only'} counties ({status})")
    finally:
        con.close()
    return made


# ============================================================================================== checks

def newest_practice_snapshot():
    root = os.path.join(HERE, "site", "practice", "night-live", "s")
    if not os.path.isdir(root):
        return None
    for name in sorted(os.listdir(root), reverse=True):
        p = os.path.join(root, name)
        if os.path.exists(os.path.join(p, "mn.json")):
            return p
    return None


def check(scratch, say=say_default, draws=DRAWS, mn_snapshot=None):
    """This part's checks on scratch copies of one's own (the real databases are only read): made-up counts for every
    state read live are written into a scratch results database beside Minnesota's practice figures, and one full night
    run (every such state and Minnesota) is made into a scratch copy of the model database and timed (limit 30 s); every
    stored night run is then redone exactly; no 0 or 100 anywhere; nothing for an unopposed race; the likely margin of the
    top two in every page file. Returns True when all hold."""
    from election.model import live_model as LM
    os.makedirs(scratch, exist_ok=True)
    rdb = os.path.join(scratch, "check_results_us.sqlite")
    mdb = os.path.join(scratch, "check_model_us.sqlite")
    for p in (rdb, rdb + "-wal", rdb + "-shm", mdb, mdb + "-wal", mdb + "-shm"):
        if os.path.exists(p):
            os.remove(p)
    shutil.copyfile(MODEL_DB, mdb)
    ok = True
    codes = live_states(mdb)
    made = synthetic_store(rdb, codes, mdb, say=say)
    snap = mn_snapshot or newest_practice_snapshot()
    if snap:
        LM.load_snapshot(snap, rdb, "MN", say=quiet)
    LM._BASE.clear()
    _BASE.clear()
    t = time.time()
    per = {}
    for code in sorted(made):
        t1 = time.time()
        res = run(code, db=rdb, model_db=mdb, draws=draws, say=quiet)
        per[code] = (round(time.time() - t1, 2), res.get("written"), res.get("skipped"))
    t_us = time.time() - t
    t1 = time.time()
    mn = LM.run("MN", db=rdb, model_db=mdb, say=quiet) if snap else {"skipped": "no practice snapshot"}
    t_mn = time.time() - t1
    total = time.time() - t
    good = total < 30 and all(v[2] is None for v in per.values()) and not mn.get("skipped")
    ok &= good
    say(f"    {'ok ' if good else 'BAD'} one full night run, cold: {len(per)} states in {t_us:.1f} s and Minnesota in {t_mn:.1f} s, "
        f"{total:.1f} s in all (limit 30); slowest " + ", ".join(f"{c} {v[0]} s" for c, v in sorted(per.items(), key=lambda kv: -kv[1][0])[:4])
        + (f"; skipped: {[c for c, v in per.items() if v[2]]}" if any(v[2] for v in per.values()) else "")
        + (f"; Minnesota: {mn.get('skipped')}" if mn.get("skipped") else ""))
    n_redo = bad_redo = 0
    for code in sorted(made) + (["MN"] if snap else []):
        for r in R.list_runs(mdb, code):
            if r["kind"] == "live":
                res = R.redo(r["run"], mdb, say=quiet)
                n_redo += 1
                if not res["exact"]:
                    bad_redo += 1
                    say(f"    BAD redo {r['run']}: {res}")
    good = n_redo > 0 and bad_redo == 0
    ok &= good
    say(f"    {'ok ' if good else 'BAD'} every night run redone exactly: {n_redo} runs, {bad_redo} differ")
    ext_bad, un_bad, margins, mraces = 0, 0, 0, 0
    for code in sorted(made) + (["MN"] if snap else []):
        e = R.check_no_extremes(code, mdb)
        u = R.check_unopposed(code, mdb)
        ext_bad += e["stored_out_of_range"] + e["page_out_of_range"]
        un_bad += u["with_a_chance_stored"] + u["in_the_page"]
        doc = R.page_json(code, mdb) or {"r": {}}
        live_rows = [r for r in doc["r"].values() if r.get("k", doc.get("k")) == "live"]
        mraces += sum(1 for r in live_rows if "eq" not in r and len(r.get("c") or []) > 1 and not r.get("s"))
        margins += sum(1 for r in live_rows if "mg" in r)
    say(f"    {'ok ' if ext_bad == 0 else 'BAD'} no 0 or 100: {ext_bad} chances out of range in the database or the page files")
    say(f"    {'ok ' if un_bad == 0 else 'BAD'} nothing for an unopposed race: {un_bad} with a chance")
    say(f"    {'ok ' if margins == mraces and mraces else 'BAD'} the likely margin of the top two in the page files: {margins} of "
        f"{mraces} single-seat races with a night forecast")
    ok &= ext_bad == 0 and un_bad == 0 and margins == mraces and mraces > 0
    return ok


# ============================================================================================== self-test

def selftest(say=say_default):
    """Made-up counties: the swing is found and pulled toward none while few are in; a kind of ballot's lean is learned;
    the votes still out follow the state's way of counting; a frame through simulate_us.py twice, the same."""
    ok = True

    def chk(what, cond):
        nonlocal ok
        ok &= bool(cond)
        say(f"    {'ok ' if cond else 'BAD'} {what}")
    rng = random.Random(3)
    counties = {f"99{k:03d}": {"L": r6(rng.gauss(0, 0.5)), "sw": 0.0, "w": 1.0 / 60, "Z": [0.0] * 4} for k in range(60)}
    base = {"c": counties}
    cands = [{"key": "d", "name": "Dee", "p": "D"}, {"key": "r", "name": "Arr", "p": "R"}]
    spec = {"race": "2026-ZZ-S1", "class": "ussen", "cands": cands, "votes": 600000.0, "tested": "t", "rule": "plurality",
            "rule_name": "plurality", "house": False, "kind": "partisan", "iD": 0, "iR": 1, "m": 0.0, "v": 0.03, "var_g": 0.02,
            "oth_prior": 0.0}
    true_shift = 0.2
    finals = {}
    for c, d in counties.items():
        p = expit(d["L"] + true_shift + rng.gauss(0, 0.05))
        finals[c] = (int(10000 * p), 10000 - int(10000 * p))

    def obs_with(cs, part=1.0, p=None):
        units = {}
        for c in cs:
            D, Rv = finals[c]
            units[c] = {"t": {"total": [int(D * part), int(Rv * part), 0]}, "in": (p if p is not None else 10), "all": 10}
        return {spec["race"]: {"units": units, "whole": {}}}
    prm = json.loads(json.dumps(DEFAULT_NIGHT_US))
    # the prior: the counties as they leaned before, with no shift (so the shift learned is the made-up one)
    spec["m"] = logit(sum(expit(d["L"]) for d in counties.values()) / len(counties))
    rid = spec["race"]
    e_all, rep_all = night_entries("ZZ", [spec], base, obs_with(list(counties)[:50]), prm)
    e_few, rep_few = night_entries("ZZ", [spec], base, obs_with(list(counties)[:3]), prm)
    chk(f"the race's shift is found with 50 counties in ({rep_all['race_shift'][rid]} against {true_shift})",
        abs(rep_all["race_shift"][rid] - true_shift) < 0.05)
    chk(f"with three counties in it is pulled toward none ({rep_few['race_shift'][rid]}), and less certain",
        abs(rep_few["race_shift"][rid]) < abs(rep_all["race_shift"][rid]) and rep_few["statewide_sd"] > rep_all["statewide_sd"])
    F, sl, st = predictive_parts(e_all[0])
    D = sum(v[0] for v in finals.values())
    T = sum(sum(v) for v in finals.values())
    chk(f"the final share is near the truth ({F:.4f} against {D / T:.4f})", abs(F - D / T) < 3 * math.sqrt(sl * sl + st * st) + 0.003)
    e_d, _rep_d = night_entries("FL", [spec], base, obs_with(list(counties), part=0.7, p=0), prm)
    chk("in a state that releases early ballots first, a county with no precincts in still has votes out",
        e_d[0]["R"] > 0.2 * e_d[0]["counted"])
    units = {}
    for c in list(counties)[:40]:
        D_, R_ = finals[c]
        units[c] = {"t": {"mail": [int(D_ * 0.3 * 1.2), int(R_ * 0.3 * 0.8), 0], "election_day": [int(D_ * 0.4 * 0.85), int(R_ * 0.4 * 1.15), 0]},
                    "in": 4, "all": 10}
    e_t, rep_t = night_entries("PA", [spec], base, {spec["race"]: {"units": units, "whole": {}}}, prm)
    tl = rep_t.get("type_lean") or {}
    chk(f"a kind of ballot's lean is learned (mail {tl.get('mail')} above Election Day {tl.get('election_day')})",
        (tl.get("mail") or 0) > (tl.get("election_day") or 0))
    frame = json.loads(R.canonical({"method": US_LIVE_METHOD, "params": prm, "races": e_all + e_t}))
    a = S.simulate(frame, 5, 300)
    b = S.simulate(frame, 5, 300)
    chk("the same frame and seed give the same numbers", R.canonical(a) == R.canonical(b))
    chk("no chance is 0 or 1", all(0 < c["chance"] < 1 for r in a["races"] for c in r["cands"]))
    chk("every race carries the likely margin of the top two", all("mg" in r for r in a["races"]))
    chk("the count order's words name the state's way of counting", "mail" in order_words("PA") and "early" in order_words("FL"))
    return ok


# ============================================================================================== command line

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--state")
    ap.add_argument("--db", help="the results database (default: the night's)")
    ap.add_argument("--model-db", default=MODEL_DB)
    ap.add_argument("--draws", type=int, default=DRAWS)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--rehearsal", action="store_true")
    ap.add_argument("--replays", action="store_true")
    ap.add_argument("--no-store", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--scratch", help="a folder of one's own for the scratch databases (with --check)")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        good = selftest()
        good = S.selftest() and good
        sys.exit(0 if good else 1)
    if a.replays:
        replays(db=a.model_db, store=not a.no_store)
        return
    if a.check:
        if not a.scratch:
            sys.exit("    --check needs --scratch <a folder of your own>")
        sys.exit(0 if check(a.scratch, draws=a.draws) else 1)
    if a.state:
        res = run(a.state, db=a.db, model_db=a.model_db, draws=a.draws, dry=a.dry_run, rehearsal=a.rehearsal)
        print(json.dumps({k: v for k, v in res.items() if k not in ("out", "frame")}, indent=1)[:3000])
        return
    ap.print_help()


if __name__ == "__main__":
    main()
