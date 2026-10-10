"""election/model/forecast.py - Minnesota before Election Day: a chance and a likely vote range for every contested race
(ARCHITECTURE.md 4.1, 4.6; model.md 2 and 3.2-3.6). Owned by N16. Analysis, never a result.

    python -m election.model.forecast --state mn              one pre-election run, stored as a version (runs.py)
    python -m election.model.forecast --state mn --dry-run    the same, printed and not stored
    python -m election.model.forecast --selftest              the arithmetic on made-up races; reads no real file

    election.model.forecast.run_pre(now=, say=)               what run_night.py calls once a day before results

WHAT IT READS (never writes): the precinct features and fitted parameters in election_model_2026.sqlite (features.py,
backtest.py), the 2026 races and candidates in ballot_local_2026.sqlite and ballot_2026.sqlite, each race's precincts from
the ballot map's files (ballot_geo/mn/), the polls by members of AAPOR's Transparency Initiative (ballot/polls/), the
parties' published endorsements (ballot/lean/mn_endorsements.json), the Clerk of the House's 2024 statistics (every
state's presidential result, to measure the polls against) and MEDSL's 2022 precinct file (who won each county and soil
and water seat in 2022, and how many voters skip those races).

THE MODEL (method METHOD; every number below is written into the run's frame, so a run can be redone exactly)
  Environment. G, the DFL's share of the two-party vote in a generic 2026 Minnesota contest (log-odds), centred on
    Minnesota's 2024 presidential result moved by how far Democrats run ahead of (or behind) the 2024 presidential
    result in the U.S. Senate polls of other states by Transparency Initiative members; its spread is those polls'
    disagreement plus a margin for polls of other states standing in for Minnesota. Minnesota's own member polls of a
    race, where both names polled are November's, move that office (and a little of G) by a small Gaussian update;
    an older poll counts for less (its error grows with the time from its last day to Election Day).
  Statewide offices: G plus the office's own offset (candidates differ; spread from 2014-2024 Minnesota results).
  District races (U.S. House, state Senate, state House): every precinct's lean (its DFL two-party share against the
    state's, in log-odds, weighted over past contests by the backtest's scheme), added up over the district's precincts
    by expected votes (2022's ballots grown with registration, less each precinct's roll-off for that office), at the
    environment, plus the class's gap to the top of the ticket, the incumbency term, a regional swing (congressional
    district) and the district's own error, all sized by the backtests on 2022 and 2024.
  Minor-party and independent candidates and write-ins: shares drawn from what such candidates won in 2012-2024, held
    to 1.5 times the largest share any of them won in that kind of race (5.9 percent statewide; 13.2 percent in a
    district beside both big parties; 24.5 percent as a big party's only opponent).
  Nonpartisan races: each candidate's share in proportion to exp(sum of terms): holding the seat (2022's winner by
    MEDSL's copy for county and soil and water seats; an office held today by the candidate's own official page
    elsewhere), a party's published endorsement combined with how the place voted (a prior: no earlier endorsement lists
    are on file to test it), the first line of the ballot, and a candidate's own unexplained error sized by the
    backtests. Where nothing on the record separates the candidates, their chances are exactly equal and the page says
    so. Several seats: the chance of finishing among the winners.
  John's three blind spots:
    roll-off    each precinct's share of voters who skip each kind of race (2022), used for the expected vote in every
                race and for how much each precinct weighs inside a race;
    position    Minn. R. 8220.0825 rebuilt: a race's precincts sorted by registered voters (2024's count on today's lines
                stands in for the May 1, 2026 count until John saves it) and dealt to one rotation per candidate, so each
                candidate's share of voters who see their name first is known up to the base order, which the county
                draws by lot and is not on file: every draw takes a fresh base order. Town ballots list names
                alphabetically by surname (Minn. Stat. 205.17), so there the first name is known. An estimate, and labelled
                so; the size of the first-line edge is a prior (0 to 1 point in partisan races, 1 to 4 in nonpartisan).
    count order belongs to the night (live_model.py) and to the replays (backtest.py); before results it changes nothing.
  Every chance comes from DRAWS draws: wins + 0.5 over draws + 1, so never 0 or 1.
"""

import argparse
import bisect
import datetime as dt
import hashlib
import json
import math
import os
import random
import re
import sqlite3
import sys
import time
from collections import defaultdict

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from election.model import DB, cache_dir, load_json, save_json, sha_file  # noqa: E402
from election.model import runs as R  # noqa: E402

METHOD = "pre-1.1"          # 1.1 (2026-10-10): several minor names beside one big party take the ordinary minor prior, not "sole"
DRAWS = 2000
STATE = "MN"
ELECTION_DAY = dt.date(2026, 11, 3)
LOCAL_DB = os.path.join(HERE, "ballot_local_2026.sqlite")
FED_DB = os.path.join(HERE, "ballot_2026.sqlite")
CROSSWALK = os.path.join(HERE, "election", "crosswalk", "mn.json")
GEO_DIR = os.path.join(HERE, "ballot_geo", "mn")
POLLS_STATE = os.path.join(HERE, "ballot", "polls", "polls_mn_state_2026.json")
POLLS_US = os.path.join(HERE, "ballot", "polls", "polls_2026.json")
ENDORSE = os.path.join(HERE, "ballot", "lean", "mn_endorsements.json")
CLERK_2024 = os.path.join(HERE, "states_cache", "mn_local", "clerk_statistics2024.pdf")

GRID_X0, GRID_DX, GRID_N = -3.0, 0.025, 241          # a district's share as a function of the statewide shift (log-odds)
STATEWIDE_BY_YEAR = {2012: ("usprs", "ussen"), 2014: ("ussen", "mngov", "mnsos", "mnag", "mnaud"), 2016: ("usprs",),
                     2018: ("ussen", "ussse", "mngov", "mnsos", "mnag", "mnaud"), 2020: ("usprs", "ussen"),
                     2022: ("mngov", "mnsos", "mnag", "mnaud"), 2024: ("usprs", "ussen")}
TOP_OF_TICKET = {2012: "usprs", 2014: "mngov", 2016: "usprs", 2018: "mngov", 2020: "usprs", 2022: "mngov", 2024: "usprs"}
OFFICE_OF_KIND = {"governor": "mngov", "secretary_of_state": "mnsos", "attorney_general": "mnag", "state_auditor": "mnaud",
                  "us_senate": "ussen", "us_house": "usrep", "state_senate": "mnsen", "state_house": "mnleg"}
STATEWIDE_OFFICES = ("mngov", "mnsos", "mnag", "mnaud", "ussen")
DISTRICT_CLASSES = ("usrep", "mnsen", "mnleg")
THETA = ("G",) + STATEWIDE_OFFICES               # the shared Gaussian: environment and the statewide offices' offsets
NP_GROUP = {"county": "county", "court": "judicial", "soil_water": "soil_water"}
UNTESTED_NP = ("untested: no past results for these offices are on file (the Secretary's files for city, school, "
               "township and hospital races have not been saved), so the method borrows its spread from county races")
SUFFIXES = {"JR", "SR", "II", "III", "IV", "V"}
STATES = {"ALABAMA": "AL", "ALASKA": "AK", "ARIZONA": "AZ", "ARKANSAS": "AR", "CALIFORNIA": "CA", "COLORADO": "CO",
          "CONNECTICUT": "CT", "DELAWARE": "DE", "DISTRICT OF COLUMBIA": "DC", "FLORIDA": "FL", "GEORGIA": "GA", "HAWAII": "HI",
          "IDAHO": "ID", "ILLINOIS": "IL", "INDIANA": "IN", "IOWA": "IA", "KANSAS": "KS", "KENTUCKY": "KY", "LOUISIANA": "LA",
          "MAINE": "ME", "MARYLAND": "MD", "MASSACHUSETTS": "MA", "MICHIGAN": "MI", "MINNESOTA": "MN", "MISSISSIPPI": "MS",
          "MISSOURI": "MO", "MONTANA": "MT", "NEBRASKA": "NE", "NEVADA": "NV", "NEW HAMPSHIRE": "NH", "NEW JERSEY": "NJ",
          "NEW MEXICO": "NM", "NEW YORK": "NY", "NORTH CAROLINA": "NC", "NORTH DAKOTA": "ND", "OHIO": "OH", "OKLAHOMA": "OK",
          "OREGON": "OR", "PENNSYLVANIA": "PA", "RHODE ISLAND": "RI", "SOUTH CAROLINA": "SC", "SOUTH DAKOTA": "SD",
          "TENNESSEE": "TN", "TEXAS": "TX", "UTAH": "UT", "VERMONT": "VT", "VIRGINIA": "VA", "WASHINGTON": "WA",
          "WEST VIRGINIA": "WV", "WISCONSIN": "WI", "WYOMING": "WY"}

# Priors, used where the record cannot size a term (each named on the forecasts page as an assumption).
PRIORS = {
    "env_systematic_sd": 0.10,     # log-odds: polls of other states' Senate races standing in for Minnesota's environment
    "env_no_polls_sd": 0.16,       # log-odds (about 4 points): the environment with no member poll at all (model.md 3.2)
    "office_sd": 0.14,             # log-odds: a statewide office's own offset (2014-2024 offices against the top of the ticket)
    "poll_house_sd": 0.05,         # log-odds: a poll's house and method error beyond sampling
    "poll_drift_per_sqrt_day": 0.0085,   # log-odds: how far opinion drifts from a poll's last day to Election Day
    "poll_recent_days": 120,       # national environment: member Senate polls ending within this many days of the run
    "turnout_sd": 0.08,            # log of the statewide turnout factor against 2022 (2014-2022 midterms moved -3% to +31%)
    "race_votes_sd": 0.05,         # log: a race's own roll-off uncertainty
    "pos_partisan": [0.0, 0.04],   # log-share edge of the first line, partisan races (about 0 to 1 point)
    "pos_nonpartisan": [0.04, 0.16],   # nonpartisan races (about 1 to 4 points)
    "endorse_beta": [0.5, 0.25],   # log-share per unit of (endorsing party's two-party share in the place - 0.5) x 2
}
# What the backtest fits (backtest.py writes the fitted values; these stand in until it has run, and the run says so).
DEFAULT_PARAMS = {
    "fitted": False, "source": "defaults: no backtest on file",
    "lean": {"rho": 0.6, "psi": 1.0, "cycles": 3},
    "gap": {"usrep": [0.0, 0.06], "mnsen": [0.0, 0.06], "mnleg": [0.0, 0.06]},
    "inc": [0.08, 0.04],
    "district_sd": {"usrep": 0.10, "mnsen": 0.14, "mnleg": 0.14},
    "region_sd": 0.04,
    "minor": {"with_majors": [-2.9, 0.45, 0.13], "sole": [-1.7, 0.33, 0.25], "statewide": [-5.0, 1.6, 0.06]},
    "writein": {"partisan": 0.002, "partisan_sole": 0.01, "np": 0.006},
    "np": {"beta_inc": [0.6, 0.15], "tau": {"county": 0.45, "judicial": 0.40, "soil_water": 0.45}},
    "turnout": {"precinct_sd": 0.10},
}


# ============================================================================================== small helpers

def logit(p):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def expit(x):
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    e = math.exp(x)
    return e / (1.0 + e)


def clamp(x, lo, hi):
    return lo if x < lo else hi if x > hi else x


def r6(x):
    return None if x is None else float(f"{x:.6g}")


def quantiles(xs, qs):
    s = sorted(xs)
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


def person_tokens(name):
    """A person's name as tokens for matching across files: upper case, letters only, no suffix, no lone initials,
    nothing in brackets or quotes. For a ticket ("A and B") the first person."""
    n = re.split(r"\s+and\s+", str(name or ""), maxsplit=1, flags=re.I)[0]
    n = re.sub(r"\([^)]*\)|\"[^\"]*\"|“[^”]*”", " ", n)
    toks = [t for t in re.sub(r"[^A-Z ]", " ", n.upper().replace("'", "")).split() if t not in SUFFIXES]
    toks = [t for t in toks if len(t) > 1] or toks
    return toks


def same_person(a, b):
    ta, tb = person_tokens(a), person_tokens(b)
    if not ta or not tb or ta[-1] != tb[-1]:
        return False
    fa, fb = ta[0], tb[0]
    return fa == fb or (len(fa) >= 3 and len(fb) >= 3 and (fa.startswith(fb) or fb.startswith(fa)))


def surname_key(name):
    toks = person_tokens(name)
    return (toks[-1] if toks else "", " ".join(toks))


def party_of(party):
    p = str(party or "").lower()
    if p.startswith("democratic") or p in ("dfl", "d"):
        return "D"
    if p.startswith("republican") or p in ("r", "rep"):
        return "R"
    return "O"


# ============================================================================================== geography

GEO_KEYS = ("county", "mcd", "cd", "house", "senate", "judicial", "com", "swcd", "hospital", "park", "ward", "school", "school_pct")


def precinct_props():
    """Today's precincts on the ballot map (ballot_geo/mn/precincts/*.json): ([VTDID], {VTDID: districts}, the map's version)."""
    idx = load_json(os.path.join(GEO_DIR, "index.json"))
    props = {}
    for c in idx["counties"]:
        doc = load_json(os.path.join(GEO_DIR, c["file"]))
        for g in doc["objects"]["precincts"]["geometries"]:
            p = g.get("properties") or {}
            props[str(g["id"])] = {k: p[k] for k in GEO_KEYS if k in p}
    return sorted(props), props, idx.get("v")


def members_index(ids, props):
    """{"layer:id": [(precinct index, weight)]}: a ward's precincts share a precinct split among wards equally; a school
    district takes each split precinct's share of area (the map files' school_pct)."""
    ix = defaultdict(list)
    for i, v in enumerate(ids):
        p = props[v]
        ix["state:MN"].append((i, 1.0))
        for layer in ("county", "mcd", "cd", "house", "senate", "judicial", "com", "swcd", "hospital", "park"):
            if p.get(layer) not in (None, ""):
                ix[f"{layer}:{p[layer]}"].append((i, 1.0))
        wards = p.get("ward") or []
        for w in wards:
            ix[f"ward:{w}"].append((i, 1.0 / len(wards)))
        schools = p.get("school") or []
        pct = p.get("school_pct")
        for k, s in enumerate(schools):
            ix[f"school:{s}"].append((i, (pct[k] / 100.0) if pct and k < len(pct) else 1.0 / len(schools)))
    return dict(ix)


def race_geo(race, geo=None):
    """The ballot map's "layer:id" for a race (the ballot pages' own rule, build_ballot_state_dev.race_shape)."""
    if race["level"] == "federal":
        return "state:MN" if race["office_kind"] == "us_senate" else f"cd:{int(race['district'])}"
    import build_ballot_state_dev as B
    geo = geo or B.geo_for("mn")
    g = B.race_shape(geo, "MN", race["level"], race["office_kind"], race.get("jurisdiction_id"), race.get("jurisdiction"),
                     race.get("district"), race.get("counties"))
    return g or B.race_said(geo, race.get("jurisdiction_id"), race["office_kind"], race.get("district")) or \
        B.place_shape(geo, race["level"], race.get("jurisdiction_id"), race.get("district"))


# ============================================================================================== the 2026 races

def races_2026():
    """Every Minnesota race on the November 3, 2026 ballot with its candidates as filed (both ballot databases, read only)."""
    cw = load_json(CROSSWALK)["races"]
    out = []
    con = sqlite3.connect(f"file:{LOCAL_DB}?mode=ro", uri=True)
    cands = defaultdict(list)
    for rid, name, party, inc, wi, member in con.execute(
            "SELECT c.race_id, c.name, c.party, c.incumbent, c.write_in, c.state_member_id FROM sl_candidates c JOIN sl_races r "
            "USING (race_id) WHERE r.state = 'MN' AND c.election = 'general' ORDER BY c.race_id, c.name"):
        if wi:
            continue
        cands[rid].append({"name": name, "party": party, "p": party_of(party), "inc": 1 if inc else 0, "member": member})
    for (rid, level, kind, office, jur, jid, cids, dist, seat, special, partisan, holder_party, note) in con.execute(
            "SELECT race_id, level, office_kind, office, jurisdiction, jurisdiction_id, county_ids, district, seat, special, "
            "partisan, holder_party, note FROM sl_races WHERE state = 'MN' ORDER BY race_id"):
        m = re.search(r"Voters choose (\d+)", note or "")
        seats = (cw.get(rid) or {}).get("seats") or (int(m.group(1)) if m else 1)
        out.append({"race": rid, "level": level, "office_kind": kind, "office": office, "jurisdiction": jur, "jurisdiction_id": jid,
                    "counties": json.loads(cids) if cids else None, "district": dist, "seat": seat, "special": special,
                    "partisan": bool(partisan), "holder_party": holder_party, "seats": int(seats), "cands": cands.get(rid, [])})
    con.close()
    con = sqlite3.connect(f"file:{FED_DB}?mode=ro", uri=True)
    fed = defaultdict(list)
    for rid, name, party, pcode, wi, bio in con.execute(
            "SELECT race_id, name, party, party_code, write_in, bioguide_id FROM candidates WHERE race_id LIKE '2026-MN-%' "
            "AND election = 'general' ORDER BY race_id, name"):
        if not wi:
            fed[rid].append({"name": name, "party": party, "p": party_of(pcode or party), "bio": bio})
    for rid, office, dist, holder, holder_party in con.execute(
            "SELECT race_id, office, district, holder, holder_party FROM races WHERE state = 'MN' ORDER BY race_id"):
        cs = fed.get(rid, [])
        for c in cs:
            c["inc"] = 1 if holder and c.pop("bio") == holder else 0
        kind = "us_senate" if office == "U.S. Senate" else "us_house"
        out.append({"race": rid, "level": "federal", "office_kind": kind, "office": office, "jurisdiction": "Minnesota",
                    "jurisdiction_id": "MN", "counties": None, "district": dist, "seat": None, "special": 0, "partisan": True,
                    "holder_party": holder_party, "seats": 1, "cands": cs})
    con.close()
    return out


# ============================================================================================== precinct inputs

def read_features(names, db=DB):
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    out = {n: {} for n in names}
    for k in range(0, len(names), 200):
        part = names[k:k + 200]
        q = f"SELECT unit_id, name, value FROM features WHERE state = 'mn' AND unit_kind = 'precinct' AND name IN ({','.join('?' * len(part))})"
        for uid, name, val in con.execute(q, part):
            out[name][uid] = val
    state = {n: v for n, v in con.execute("SELECT name, value FROM features WHERE state = 'mn' AND unit_kind = 'state'")}
    build = con.execute("SELECT MAX(build) FROM features WHERE state = 'mn'").fetchone()[0]
    con.close()
    return out, state, build


def lean_vector(feats, state, ids, target_year, scheme, counties=None):
    """Each precinct's lean in log-odds: its DFL two-party share against the state's, weighted over the statewide
    contests of the `cycles` elections before `target_year` (weight rho per cycle back, psi on presidential contests).
    A precinct with no figure takes its county's average lean (by 2020 people), else 0. Returns (L, contests used)."""
    rho, psi, k = scheme["rho"], scheme["psi"], scheme["cycles"]
    contests = [(p, y) for y, ps in sorted(STATEWIDE_BY_YEAR.items()) if target_year - 2 * k <= y < target_year for p in ps]
    L = []
    for v in ids:
        num = den = 0.0
        for p, y in contests:
            s = feats.get(f"dfl2p_{p}_{y}", {}).get(v)
            S = state.get(f"dfl2p_{p}_{y}")
            if s is None or S is None:
                continue
            w = rho ** ((target_year - y) / 2 - 1) * (psi if p == "usprs" else 1.0)
            num += w * (logit(clamp(s, 0.01, 0.99)) - logit(S))
            den += w
        L.append(num / den if den else None)
    if counties is not None:
        acc = defaultdict(lambda: [0.0, 0.0])
        for i, v in enumerate(ids):
            if L[i] is not None:
                acc[counties[i]][0] += L[i]
                acc[counties[i]][1] += 1
        L = [x if x is not None else (acc[counties[i]][0] / acc[counties[i]][1] if acc[counties[i]][1] else 0.0)
             for i, x in enumerate(L)]
    else:
        L = [0.0 if x is None else x for x in L]
    return L, contests


def make_grid(members, L, V):
    """The share of a set of precincts as a function of a statewide shift x (log-odds), at GRID_N points from GRID_X0."""
    tot = sum(w * V[i] for i, w in members)
    if tot <= 0:
        V = [1.0] * len(L)
        tot = sum(w for _i, w in members)
    pts = [(L[i], w * V[i] / tot) for i, w in members if w * V[i] > 0]
    out = []
    for k in range(GRID_N):
        x = GRID_X0 + k * GRID_DX
        out.append(sum(wt * expit(x + l) for l, wt in pts))
    return out


def interp(f, x):
    pos = (x - GRID_X0) / GRID_DX
    if pos <= 0:
        return f[0]
    if pos >= GRID_N - 1:
        return f[-1]
    i = int(pos)
    t = pos - i
    return f[i] * (1 - t) + f[i + 1] * t


def inverse(f, share):
    """The shift x at which a grid gives `share` (f rises with x)."""
    if share <= f[0]:
        return GRID_X0
    if share >= f[-1]:
        return GRID_X0 + (GRID_N - 1) * GRID_DX
    k = bisect.bisect_left(f, share)
    a, b = f[k - 1], f[k]
    t = (share - a) / (b - a) if b > a else 0.0
    return GRID_X0 + (k - 1 + t) * GRID_DX


# ============================================================================================== ballot position (blind spot)

def rotation_subtotals(regs, n):
    """Minn. R. 8220.0825 subp. 3: precincts sorted by registered voters, largest first (ties by the precinct's id); the
    first n go one to each rotation; after that each next precinct goes to the rotation with the lowest running
    subtotal (a tie to the lowest-numbered rotation: the rule does not say). regs: [(precinct id, registered)].
    Returns ([rotation of each precinct, in regs' order], [subtotal of each rotation])."""
    order = sorted(range(len(regs)), key=lambda k: (-regs[k][1], regs[k][0]))
    sub = [0.0] * n
    rot = [None] * len(regs)
    for j, k in enumerate(order):
        r = j if j < n else min(range(n), key=lambda q: (sub[q], q))
        rot[k] = r
        sub[r] += regs[k][1]
    return rot, sub


def exposures(regs, votes, n):
    """Each base position's share of a race's expected votes cast where that position's name stands first: rotation r
    prints base position r first (the rotations are the base order turned r places). Precincts are dealt by
    registration (the rule) and weighed by expected votes (who actually sees the ballot)."""
    if n < 2 or not regs:
        return None
    rot, _sub = rotation_subtotals(regs, n)
    e = [0.0] * n
    for k, r in enumerate(rot):
        e[r] += votes[k]
    tot = sum(e)
    return [x / tot for x in e] if tot > 0 else [1.0 / n] * n


# ============================================================================================== the environment and polls

def clerk_president_2024(path=CLERK_2024):
    """{state code: (Democratic, Republican, all)} from the Clerk of the House's statistics of the 2024 election
    ("FOR PRESIDENTIAL ELECTORS" under each state's heading). Cached against the PDF's SHA-256."""
    cache = os.path.join(cache_dir("mn", "forecast"), "clerk_president_2024.json")
    sha = sha_file(path)
    if os.path.exists(cache):
        doc = load_json(cache)
        if doc.get("sha256") == sha:
            return {k: tuple(v) for k, v in doc["states"].items()}, sha
    from ballot import pdftext
    lines = [t.strip() for _p, _y, t in pdftext.lines(path)]
    out, state, section = {}, None, None
    for t in lines:
        if t in STATES:
            state, section = STATES[t], None
            continue
        if t.startswith("FOR "):
            section = t
            continue
        if state and section == "FOR PRESIDENTIAL ELECTORS":
            m = re.match(r"^(.*?)\s*\.{3,}\s*([\d,]+)$", t)
            if not m:
                continue
            label, v = m.group(1).strip().lower(), int(m.group(2).replace(",", ""))
            rec = out.setdefault(state, [0, 0, 0])
            rec[2] += v
            if label.startswith("democrat"):
                rec[0] += v
            elif label.startswith("republican"):
                rec[1] += v
    save_json(cache, {"sha256": sha, "source": "Clerk of the U.S. House, Statistics of the Presidential and Congressional Election of "
                      "November 5, 2024", "states": out})
    return {k: tuple(v) for k, v in out.items()}, sha


def _party_lookup():
    """{race id: {name key: party letter}} for every 2026 Senate race's candidates (general and primary lists)."""
    con = sqlite3.connect(f"file:{FED_DB}?mode=ro", uri=True)
    out = defaultdict(dict)
    for rid, name, party, pcode in con.execute("SELECT race_id, name, party, party_code FROM candidates WHERE race_id LIKE '2026-__-S%'"):
        out[rid][" ".join(person_tokens(name))] = party_of(pcode or party)
    con.close()
    return out


def _two_party(poll, parties, nominees=None):
    """A poll's DFL/Democratic share of the two-party vote, or None when it lacks one of the two (or names someone who
    is not on November's list, when `nominees` is given)."""
    d = r = 0.0
    for name, share in (poll.get("shares") or {}).items():
        key = " ".join(person_tokens(name))
        p = parties.get(key)
        if p is None:
            p = next((pp for k, pp in parties.items() if same_person(k, name)), None)
        if nominees is not None and not any(same_person(name, n) for n in nominees):
            return None
        if p == "D":
            d += share
        elif p == "R":
            r += share
    return d / (d + r) if d > 0 and r > 0 else None


def poll_sd(poll, share):
    n = max(int(poll.get("n") or 600), 100)
    days = max((ELECTION_DAY - dt.date.fromisoformat(poll["end"])).days, 0)
    sampling = 1.0 / math.sqrt(n * share * (1 - share))
    return math.sqrt(sampling ** 2 + PRIORS["poll_house_sd"] ** 2 + (PRIORS["poll_drift_per_sqrt_day"] ** 2) * days)


def environment(as_of, races, office_sd=None, senate_sd=None):
    """The shared Gaussian over THETA (G and each statewide office's offset): mean, covariance, and an account of the
    inputs (for the page and run_inputs). office_sd: the backtest's measured spread of a constitutional office's offset
    against the top of its ticket (the governor's too); senate_sd: a U.S. Senate race's, whose candidates pull further."""
    office_sd = office_sd or PRIORS["office_sd"]
    senate_sd = senate_sd or office_sd
    as_day = as_of.date() if isinstance(as_of, dt.datetime) else as_of
    pres, pres_sha = clerk_president_2024()
    mn = pres["MN"]
    p_mn = mn[0] / (mn[0] + mn[1])
    parties = _party_lookup()
    us = load_json(POLLS_US)["races"]
    shifts, used = [], []
    for rid, rec in sorted(us.items()):
        st = rid.split("-")[1]
        if st == "MN" or st not in pres:
            continue
        vals = []
        for p in rec.get("polls") or []:
            if not p.get("member") or not p.get("end"):
                continue
            end = dt.date.fromisoformat(p["end"])
            if end > as_day or (as_day - end).days > PRIORS["poll_recent_days"]:
                continue
            tp = _two_party(p, parties.get(rid, {}))
            if tp is not None:
                vals.append((end, logit(tp), p["pollster"]))
        if not vals:
            continue
        # the latest poll of each pollster, at most five pollsters (the polls file's own rule)
        latest = {}
        for end, x, who in sorted(vals, reverse=True):
            latest.setdefault(who, (end, x))
        xs = [x for _e, x in sorted(latest.values(), reverse=True)[:5]]
        d, r_, _all = pres[st]
        shift = sum(xs) / len(xs) - logit(d / (d + r_))
        shifts.append(shift)
        used.append({"race": rid, "polls": len(xs), "shift": round(shift, 4)})
    if len(shifts) >= 3:
        mean = sum(shifts) / len(shifts)
        sd = math.sqrt(sum((s - mean) ** 2 for s in shifts) / (len(shifts) - 1))
        g_mean = logit(p_mn) + mean
        g_var = (sd ** 2) / len(shifts) + PRIORS["env_systematic_sd"] ** 2
        pts = (expit(mean) - 0.5) * 100
        env_note = (f"In {len(shifts)} states, U.S. Senate polls by members of AAPOR's Transparency Initiative have Democrats running "
                    f"{abs(pts):.1f} points {'ahead of' if pts >= 0 else 'behind'} Kamala Harris's 2024 share of the two-party vote")
    else:
        mean, sd = 0.0, None
        g_mean = logit(p_mn)
        g_var = PRIORS["env_no_polls_sd"] ** 2
        env_note = "too few recent member polls of other states' Senate races: Minnesota's 2024 presidential result, widened"
    m = [g_mean] + [0.0] * len(STATEWIDE_OFFICES)
    P = [[0.0] * len(THETA) for _ in THETA]
    P[0][0] = g_var
    for k in range(1, len(THETA)):
        P[k][k] = (senate_sd if THETA[k] == "ussen" else office_sd) ** 2
    # Minnesota's own member polls: y = G + kappa_office + error, a race's poll used only when both names are November's
    st = load_json(POLLS_STATE)["races"]
    by_id = {r["race"]: r for r in races}
    mine = []
    for rid, rec in list(st.items()) + [("2026-MN-S2", us.get("2026-MN-S2", {}))]:
        race = by_id.get(rid)
        if not race:
            continue
        office = OFFICE_OF_KIND.get(race["office_kind"])
        if office not in STATEWIDE_OFFICES:
            continue
        nominees = [c["name"] for c in race["cands"]]
        pmap = {" ".join(person_tokens(c["name"])): c["p"] for c in race["cands"]}
        for p in rec.get("polls") or []:
            if not p.get("member") or dt.date.fromisoformat(p["end"]) > as_day:
                continue
            tp = _two_party(p, pmap, nominees)
            if tp is None:
                mine.append({"race": rid, "pollster": p["pollster"], "end": p["end"], "used": False,
                             "why": "the poll's names are not both on November's list"})
                continue
            y, s = logit(tp), poll_sd(p, tp)
            k = THETA.index(office)
            H = [0.0] * len(THETA)
            H[0], H[k] = 1.0, 1.0
            PH = [sum(P[i][j] * H[j] for j in range(len(THETA))) for i in range(len(THETA))]
            S = sum(H[i] * PH[i] for i in range(len(THETA))) + s * s
            K = [x / S for x in PH]
            innov = y - sum(H[i] * m[i] for i in range(len(THETA)))
            m = [m[i] + K[i] * innov for i in range(len(THETA))]
            P = [[P[i][j] - K[i] * PH[j] for j in range(len(THETA))] for i in range(len(THETA))]
            mine.append({"race": rid, "pollster": p["pollster"], "end": p["end"], "used": True, "two_party": round(tp, 4),
                         "sd": round(s, 4)})
    return {"theta": list(THETA), "mean": [r6(x) for x in m], "cov": [[r6(x) for x in row] for row in P],
            "mn_pres_2024": r6(p_mn), "shift": r6(mean), "shift_sd": r6(sd) if sd is not None else None, "states": used,
            "mn_polls": mine, "note": env_note, "clerk_sha": pres_sha}


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


# ============================================================================================== nonpartisan facts on the record

NP_MEDSL_OFFICE = {"COUNTY SHERIFF": "sheriff", "COUNTY ATTORNEY": "county_attorney", "COUNTY AUDITOR/TREASURER": "county_auditor_treasurer",
                   "COUNTY AUDITOR": "county_auditor", "COUNTY TREASURER": "county_treasurer", "COUNTY RECORDER": "county_recorder",
                   "COUNTY SURVEYOR": "county_surveyor", "COUNTY CORONER": "county_coroner", "COUNTY COMMISSIONER": "county_commissioner",
                   "COUNTY PARK COMMISSIONER": "county_park", "SOIL AND WATER SUPERVISOR": "soil_water"}


def _dist_key(d):
    d = str(d or "").strip().upper()
    m = re.match(r"^0*(\d+)\s*(\(([A-Z]+)\))?", d)
    if m:
        return m.group(1) + (f" {m.group(3)}" if m.group(3) else "")
    return d


def medsl_winners_2022():
    """{(office kind, county three digits, district key): [(name, share, won)]} for 2022's county and soil and water
    contests, from MEDSL's copy (secondary, labelled), with write-ins left out of the names (cached)."""
    from election.model import data_mn
    path = os.path.join(cache_dir("mn", "medsl"), "medsl_2022_mn.json")
    cache = os.path.join(cache_dir("mn", "forecast"), "medsl_2022_contests.json")
    sha = sha_file(path) if os.path.exists(path) else None
    if os.path.exists(cache):
        doc = load_json(cache)
        if doc.get("sha256") == sha:
            return {tuple(k.split("|")): v for k, v in doc["contests"].items()}, sha
    rows, _doc = data_mn.medsl_rows(2022)
    tot = defaultdict(lambda: defaultdict(int))
    for r in rows:
        kind = NP_MEDSL_OFFICE.get(r["office"].upper().strip())
        if not kind or (r.get("special") or "").upper() == "TRUE" or (r.get("writein") or "").upper() == "TRUE":
            continue
        key = (kind, (r.get("county_fips") or "")[-3:], _dist_key(r.get("district")) if kind in ("county_commissioner", "county_park", "soil_water") else "")
        tot[key][r["candidate"]] += r["votes"]
    out = {}
    for key, c in tot.items():
        s = sum(c.values())
        if not s:
            continue
        top = max(c.values())
        out[key] = [[name, round(v / s, 5), 1 if v == top else 0] for name, v in sorted(c.items())]
    save_json(cache, {"sha256": sha, "source": "MEDSL 2022 Minnesota precinct file (CC0), summed by contest", "contests":
                      {"|".join(k): v for k, v in out.items()}})
    return out, sha


def office_held_now(race, found):
    """Whether the record says a candidate holds this very office today: an office the candidate's own official page
    states as held now, naming the office and the race's place. Returns the fact's words or None."""
    want = {"mayor": ("mayor",), "council": ("council",), "school_board": ("school board", "board of education", "school"),
            "town_supervisor": ("supervisor",), "town_clerk": ("clerk",), "town_treasurer": ("treasurer",),
            "hospital_board": ("hospital",), "county_commissioner": ("commissioner",), "sheriff": ("sheriff",),
            "county_attorney": ("county attorney",), "district_court": ("judge", "district court"),
            "soil_water": ("soil", "water")}.get(race["office_kind"])
    if not want:
        return None
    place = re.sub(r"\s+(city|township|county|public school district.*|\(.*\))$", "", str(race.get("jurisdiction") or ""), flags=re.I).lower()
    seat = re.search(r"(\d+)", str(race.get("district") or ""))
    for office, to, kind in found:
        o = str(office or "").lower()
        if str(to or "").lower() != "now" or kind != "official":
            continue
        if not any(w in o for w in want) or (place and place.split()[0] not in o):
            continue
        named = re.search(r"\b(?:district|ward)\s+(\d+)", o)
        if seat and named and int(named.group(1)) != int(seat.group(1)):
            continue                                # another district's or ward's seat of the same body
        return office
    return None


def found_offices():
    """{(race id, name): [(office, to, kind)]} from the verified findings on file (sl_found_facts, offices only)."""
    con = sqlite3.connect(f"file:{LOCAL_DB}?mode=ro", uri=True)
    out = defaultdict(list)
    for rid, name, office, to, kind in con.execute("SELECT race_id, name, office, to_year, kind FROM sl_found_facts "
                                                   "WHERE race_id LIKE '2026-MN-%' AND field = 'office'"):
        out[(rid, name)].append((office, to, kind))
    con.close()
    return out


def endorsements():
    """{(race id, name): [party letter]} from the parties' own published endorsement lists (never 'other support')."""
    doc = load_json(ENDORSE)
    out = defaultdict(set)
    for e in doc.get("endorsements") or []:
        if e.get("election"):
            continue
        out[(e["race_id"], e["name"])].add(party_of(e.get("party")))
    return {k: sorted(v) for k, v in out.items()}, sha_file(ENDORSE)


# ============================================================================================== the frame

def latest_params(db=DB):
    """The newest backtest's fitted parameters (backtest.py), or DEFAULT_PARAMS with a note."""
    if not os.path.exists(db):
        return dict(DEFAULT_PARAMS), None
    con = R.connect(db)
    try:
        row = con.execute("SELECT run, frame_sha FROM runs WHERE state = 'MN' AND kind = 'backtest' AND ended IS NOT NULL "
                          "ORDER BY started DESC, run DESC LIMIT 1").fetchone()
        if not row:
            return dict(DEFAULT_PARAMS), None
        doc = R.get_blob(con, row[1]) or {}
        params = doc.get("params")
        if not params:
            return dict(DEFAULT_PARAMS), None
        return params, row[0]
    finally:
        con.close()


def build_frame(as_of=None, params=None, params_run=None, say=print, db=DB):
    """Every input of a pre-election run, in one self-contained object (the run keeps it whole). Returns (frame, inputs)."""
    t0 = time.time()
    as_of = as_of or R.now_utc()
    if params is None:
        params, params_run = latest_params(db)
    ids, props, geo_v = precinct_props()
    index = members_index(ids, props)
    races = races_2026()
    names = sorted({f"dfl2p_{p}_{y}" for y, ps in STATEWIDE_BY_YEAR.items() for p in ps} |
                   {"ballots_2022", "registered_2022", "registered_2024", "pop2020"} |
                   {f"rolloff_{c}_2022" for c in ("mngov", "mnsos", "mnag", "mnaud", "usrep", "mnsen", "mnleg")} |
                   {"rolloff_ussen_2018"})
    feats, state, build = read_features(names, db)
    counties = [props[v].get("county") for v in ids]
    L, used = lean_vector(feats, state, ids, 2026, params["lean"], counties)
    # expected ballots: 2022's, grown with each precinct's registration against the state's (2022 to 2024)
    reg22 = sum(feats["registered_2022"].get(v) or 0 for v in ids)
    reg24 = sum(feats["registered_2024"].get(v) or 0 for v in ids)
    state_growth = reg24 / reg22 if reg22 else 1.0
    B, how_b = [], defaultdict(int)
    for v in ids:
        b22 = feats["ballots_2022"].get(v)
        r22, r24 = feats["registered_2022"].get(v), feats["registered_2024"].get(v)
        if b22 and r22 and r24:
            B.append(b22 * clamp((r24 / r22) / state_growth, 0.5, 2.0))
            how_b["2022 ballots, grown with registration"] += 1
        elif b22:
            B.append(float(b22))
            how_b["2022 ballots"] += 1
        elif r24:
            B.append(r24 * state.get("turnout_2022", 0.68))
            how_b["2024 registration at 2022's turnout"] += 1
        else:
            B.append(0.0)
            how_b["no figure: counted as no votes"] += 1
    # roll-off for each partisan class (2022; the U.S. Senate's from 2018, the last midterm with one)
    ro = {}
    for c in ("mngov", "mnsos", "mnag", "mnaud", "usrep", "mnsen", "mnleg", "ussen"):
        name = f"rolloff_{c}_2018" if c == "ussen" else f"rolloff_{c}_2022"
        vals = [feats[name].get(v) for v in ids]
        med = sorted(x for x in vals if x is not None)
        med = med[len(med) // 2] if med else 0.03
        ro[c] = [r6(clamp(x if x is not None else med, 0.0, 0.9)) for x in vals]
    np_ro = np_rolloff(ids)
    regs = [feats["registered_2024"].get(v) or 0 for v in ids]
    env = environment(as_of, races, params.get("office_sd"), params.get("office_sd_senate"))
    winners22, medsl_sha = medsl_winners_2022()
    found = found_offices()
    ends, end_sha = endorsements()
    # place lean for endorsements: the DFL two-party share of 2024's presidential and 2022's governor's votes in the place
    pv = [((feats["dfl2p_usprs_2024"].get(v) if feats["dfl2p_usprs_2024"].get(v) is not None else feats["dfl2p_mngov_2022"].get(v)), B[i])
          for i, v in enumerate(ids)]
    try:
        import build_ballot_state_dev as Bsd
        geo = Bsd.geo_for("mn")
    except Exception:  # noqa: BLE001  without the map's rule every race stays without precincts, and says so
        geo = None
    fr_races, counts = [], defaultdict(int)
    statewide_members = index["state:MN"]
    for race in races:
        rid = race["race"]
        cands = race["cands"]
        seats = race["seats"]
        entry = {"race": rid, "level": race["level"], "office_kind": race["office_kind"], "seats": seats,
                 "cands": [{"key": choice_key(c["name"]), "name": c["name"], "p": c["p"]} for c in cands]}
        if not cands:
            entry["status"] = "no-candidates"
            fr_races.append(entry)
            counts["no candidates"] += 1
            continue
        if len(cands) <= seats:
            entry["status"] = "unopposed"
            fr_races.append(entry)
            counts["unopposed"] += 1
            continue
        g = race_geo(race, geo) if (geo or race["level"] == "federal") else None
        mem = index.get(g, []) if g else []
        entry["geo"] = g
        entry["units"] = len(mem)
        office = OFFICE_OF_KIND.get(race["office_kind"])
        if race["partisan"] and office:
            ro_c = ro.get(office) or ro["mnleg"]
            V = [B[i] * (1 - ro_c[i]) for i in range(len(ids))]
            entry["kind"] = "partisan"
            entry["class"] = office
            for c, ec in zip(cands, entry["cands"]):
                ec["inc"] = c.get("inc", 0)
            if office in STATEWIDE_OFFICES:
                entry["k"] = THETA.index(office)
            if office in DISTRICT_CLASSES:
                entry["members"] = [[i, r6(w)] for i, w in mem]
                cds = defaultdict(float)
                for i, w in mem:
                    cds[props[ids[i]].get("cd")] += w * V[i]
                entry["region"] = max(cds, key=cds.get) if cds else None
            entry["votes"] = r6(sum(w * V[i] for i, w in mem)) if mem else None
            entry["rot"] = [r6(x) for x in (exposures([(ids[i], regs[i] * w) for i, w in mem], [w * V[i] for i, w in mem], len(cands)) or [])] or None
            entry["tested"] = ("tested on 2022 and 2024 statewide races (few)" if office in STATEWIDE_OFFICES else
                               "tested on 2022 and 2024 races for this office")
            counts[f"partisan {office}"] += 1
        else:
            group = NP_GROUP.get(race["level"])
            # roll-off: a commissioner's race skips like 2022's commissioner races, other county offices like 2022's
            # countywide ones, judges like 2022's judges, soil and water likewise; cities, schools, towns and hospital
            # districts have no file of their own, and borrow the commissioner races' (a local race on the same ballot)
            ro_group = ("county_commissioner" if race["office_kind"] in ("county_commissioner", "county_park") else
                        group if group in np_ro else "county_commissioner")
            ro_c = np_ro.get(ro_group) or np_ro["county_commissioner"]
            V = [B[i] * (1 - ro_c[i]) for i in range(len(ids))]
            entry["kind"] = "nonpartisan"
            entry["group"] = group or "local"
            entry["tested"] = ("tested on 2022 and 2024 county, court and soil and water races (MEDSL's copies of the "
                               "Secretary's files)") if group else UNTESTED_NP
            place = [(pv[i][0], w * pv[i][1]) for i, w in mem if pv[i][0] is not None]
            tw = sum(x[1] for x in place)
            dfl = (sum(x[0] * x[1] for x in place) / tw) if tw else None
            entry["place_dfl"] = r6(dfl)
            for c, ec in zip(cands, entry["cands"]):
                inc, why = 0, None
                if race["level"] in ("county", "soil_water") and race["office_kind"] in NP_MEDSL_OFFICE.values():
                    key = (race["office_kind"], str(race.get("jurisdiction_id") or "")[-3:],
                           _dist_key(race.get("district")) if race["office_kind"] in ("county_commissioner", "county_park", "soil_water") else "")
                    for name, share, won in winners22.get(key, []):
                        if won and same_person(c["name"], name):
                            inc, why = 1, "won this seat in 2022 (MEDSL's copy of the Secretary's results)"
                if not inc:
                    held = office_held_now(race, found.get((rid, c["name"]), []))
                    if held:
                        inc, why = 1, "holds the office today, by the candidate's own official page"
                ec["inc"] = inc
                if why:
                    ec["inc_why"] = why
                e = ends.get((rid, c["name"]), [])
                score = 0.0
                if dfl is not None:
                    for party in e:
                        if party == "D":
                            score += (dfl - 0.5) * 2
                        elif party == "R":
                            score += (0.5 - dfl) * 2
                if e:
                    ec["end"] = r6(score)
                    ec["end_by"] = e
            if race["level"] == "township":
                order = sorted(range(len(cands)), key=lambda k: surname_key(cands[k]["name"]))
                entry["first"] = order[0]
                entry["first_why"] = "town ballots list names alphabetically by surname (Minn. Stat. 205.17); an estimate"
            else:
                entry["rot"] = [r6(x) for x in (exposures([(ids[i], regs[i] * w) for i, w in mem], [w * V[i] for i, w in mem],
                                                          len(cands)) or [])] or None
            entry["votes"] = r6(sum(w * V[i] for i, w in mem)) if mem else None
            counts[f"nonpartisan {entry['group']}"] += 1
        entry["status"] = "pre"
        fr_races.append(entry)
    # the statewide grid (for turning the environment into a precinct shift) and each district's grid
    V_top = [B[i] * (1 - ro["mngov"][i]) for i in range(len(ids))]
    frame = {
        "v": 1, "state": STATE, "method": METHOD, "as_of": R.iso(as_of), "election": ELECTION_DAY.isoformat(),
        "days_to_election": max((ELECTION_DAY - as_of.date()).days, 0),
        "params": params, "params_run": params_run, "priors": PRIORS,
        "precincts": {"ids": ids, "lean": [r6(x) for x in L], "ballots": [r6(x) for x in B], "top_votes": [r6(x) for x in V_top],
                      "cd": [props[v].get("cd") for v in ids]},
        "env": env,
        "grid": {"x0": GRID_X0, "dx": GRID_DX, "n": GRID_N},
        "races": fr_races,
    }
    for entry in fr_races:
        if entry.get("kind") == "partisan" and entry.get("members"):
            Vc = [B[i] * (1 - ro[entry["class"]][i]) for i in range(len(ids))]
            entry["f"] = [r6(x) for x in make_grid([(i, w) for i, w in entry["members"]], L, Vc)]
            del entry["members"]
    frame["state_grid"] = [r6(x) for x in make_grid(statewide_members, L, V_top)]
    report = {"counts": dict(counts), "ballots_how": dict(how_b), "lean_contests": [f"{p} {y}" for p, y in used],
              "expected_ballots": round(sum(B)), "built_in": round(time.time() - t0, 1)}
    frame["report"] = report
    frame["public"] = public_words(env, params, params_run, used, counts)
    inputs = [
        {"input": "features", "source": f"election_model_2026.sqlite features (data build {build})", "sha256": None,
         "as_of": None, "kind": "derived", "note": "precinct figures on today's lines (features.py)"},
        {"input": "params", "source": f"backtest run {params_run}" if params_run else "defaults (no backtest on file)",
         "sha256": R.sha_text(R.canonical(params)), "as_of": None, "kind": "derived" if params_run else "prior", "note": params.get("source")},
        {"input": "ballot-local", "source": LOCAL_DB, "sha256": sha_file(LOCAL_DB), "as_of": None, "kind": "official",
         "note": "the 2026 races and candidates as filed (read only)"},
        {"input": "ballot-congress", "source": FED_DB, "sha256": sha_file(FED_DB), "as_of": None, "kind": "official",
         "note": "the 2026 races for Congress (read only)"},
        {"input": "map", "source": os.path.join(GEO_DIR, "index.json"), "sha256": sha_file(os.path.join(GEO_DIR, "index.json")),
         "as_of": str(geo_v), "kind": "official", "note": "each race's precincts by the ballot map's rule"},
        {"input": "polls-us", "source": POLLS_US, "sha256": sha_file(POLLS_US), "as_of": None, "kind": "poll",
         "note": "members of AAPOR's Transparency Initiative only"},
        {"input": "polls-mn", "source": POLLS_STATE, "sha256": sha_file(POLLS_STATE), "as_of": None, "kind": "poll",
         "note": "members of AAPOR's Transparency Initiative only"},
        {"input": "clerk-2024", "source": CLERK_2024, "sha256": env["clerk_sha"], "as_of": "2024-11-05", "kind": "official",
         "note": "every state's 2024 presidential result, to measure the Senate polls against"},
        {"input": "endorsements", "source": ENDORSE, "sha256": end_sha, "as_of": None, "kind": "party",
         "note": "the parties' own published endorsement lists"},
        {"input": "medsl-2022", "source": "election_cache/model/mn/medsl/medsl_2022_mn.json", "sha256": medsl_sha, "as_of": "2022-11-08",
         "kind": "secondary", "note": "MIT Election Data and Science Lab (CC0): who won each county and soil and water seat in 2022"},
    ]
    say(f"    frame built in {report['built_in']} s: {len(fr_races)} races ({dict(counts)})")
    return frame, inputs


OFFICE_WORDS = {"usprs": "presidential", "ussen": "U.S. Senate", "ussse": "U.S. Senate special", "mngov": "governor's",
                "mnsos": "secretary of state's", "mnag": "attorney general's", "mnaud": "state auditor's"}


def public_words(env, params, params_run, used, counts):
    """What a forecasts page may say about a run's inputs and method, in plain words with the run's own numbers (no
    file or program names; ARCHITECTURE.md 4.6)."""
    g = expit(env["mean"][0])
    g_sd = math.sqrt(env["cov"][0][0]) * 0.25 * 100           # log-odds to points of share, near an even race
    by_year = defaultdict(list)
    for p, y in used:
        by_year[y].append(OFFICE_WORDS.get(p, p))
    def words(v):
        return v[0] if len(v) == 1 else ", ".join(v[:-1]) + " and " + v[-1]
    lean = "; ".join(f"{y}: the {words(v)} race{'s' if len(v) > 1 else ''}" for y, v in sorted(by_year.items(), reverse=True))
    polls = [{"race": p["race"], "pollster": p["pollster"], "ended": p["end"], "used": p["used"],
              **({} if p["used"] else {"why": p.get("why")})} for p in env.get("mn_polls", [])]
    inc = params.get("inc", [0.0])[0] * 0.25 * 100
    np_inc = params.get("np", {}).get("beta_inc", [0.0])[0]
    np_share = math.exp(np_inc) / (1 + math.exp(np_inc)) * 100
    out = {
        "environment": (f"{env['note']}. Applied to Minnesota's 2024 presidential result ({env['mn_pres_2024'] * 100:.1f}% DFL of the "
                        f"two-party vote) and moved a little by Minnesota's own member polls, a generic 2026 Minnesota contest "
                        f"stands near {g * 100:.1f}% DFL, give or take about {g_sd:.1f} points."),
        "mn_polls": polls,
        "lean": (f"Each precinct's lean is its DFL share against the state's in these past contests: {lean} (presidential "
                 f"contests weighted {params['lean']['psi']:g} times; each older election {params['lean']['rho']:g} times the next)."),
        "district": (f"District races add their precincts' leans by expected votes, then a sitting member's edge (about "
                     f"{inc:.1f} points), a regional swing and the district's own error, each sized on the 2022 and 2024 results."),
        "nonpartisan": (f"Nonpartisan races: a seat's holder is expected to take about {np_share:.0f}% against one challenger, as in "
                        f"the 2022 and 2024 county, court and soil and water races; a party's published endorsement counts for a "
                        f"little, more where the place leans to that party; where the record names no holder and no endorsement, "
                        f"chances are equal."),
        "turnout": ("Expected voters: each precinct's 2022 ballots, grown with its registration since 2022, less the share that "
                    "skipped that office in 2022 (roll-off)."),
        "position": ("Ballot position: each name's share of voters who see it first, rebuilt from Minnesota's rotation rule with "
                     "2024's registration counts (an estimate: the counties draw the starting order by lot, and it is not on file); "
                     "town ballots list names alphabetically, so there the first name is known."),
        "not_used": "Campaign money and Census figures are not used before Election Day: neither has been tested on past races yet.",
        "untested": ("City, school, township and hospital races are untested: no past results for them are on file, so their "
                     "spread is borrowed from county races."),
        "backtest": (f"Sized by the backtests run on {dt.date(int(params_run.split('-')[2][:4]), int(params_run.split('-')[2][4:6]), int(params_run.split('-')[2][6:8])):%B} "
                     f"{int(params_run.split('-')[2][6:8])}, {params_run.split('-')[2][:4]}." if params_run else
                     "Not yet sized by a backtest: the spreads are the method's starting assumptions."),
        "races": {"forecast": sum(v for k, v in counts.items() if k.startswith(("partisan", "nonpartisan"))),
                  "unopposed": counts.get("unopposed", 0)},
    }
    return out


def choice_key(name):
    try:
        from election.readers.mn_media import choice_key as ck
        return ck(name)
    except Exception:  # noqa: BLE001
        return re.sub(r"[^a-z0-9]+", "-", str(name or "").lower()).strip("-")[:48] or "unnamed"


def np_rolloff(ids):
    """{group: [roll-off of each precinct]} for nonpartisan races, from MEDSL's 2022 file carried onto today's lines:
    1 minus the votes for named candidates over the state ballots, averaged over the group's races in the precinct.
    Groups: county (countywide offices), county_commissioner, soil_water, judicial; a precinct with no such race takes
    the group's median. Cached."""
    from election.model import data_mn
    path = os.path.join(cache_dir("mn", "medsl"), "medsl_2022_mn.json")
    cache = os.path.join(cache_dir("mn", "forecast"), "np_rolloff_2022.json")
    sha = sha_file(path) if os.path.exists(path) else None
    if os.path.exists(cache):
        doc = load_json(cache)
        if doc.get("sha256") == sha and doc.get("ids") == len(ids):
            return doc["groups"]
    rows, _rep = data_mn.medsl_by_vtdid(2022)
    group_of = {"COUNTY SHERIFF": "county", "COUNTY ATTORNEY": "county", "COUNTY AUDITOR/TREASURER": "county", "COUNTY RECORDER": "county",
                "COUNTY AUDITOR": "county", "COUNTY TREASURER": "county", "COUNTY COMMISSIONER": "county_commissioner",
                "SOIL AND WATER SUPERVISOR": "soil_water"}
    acc = defaultdict(lambda: defaultdict(float))
    races_in = defaultdict(lambda: defaultdict(set))
    for r in rows:
        o = r["office"].upper().strip()
        g = group_of.get(o) or ("judicial" if ("JUDGE" in o or "JUSTICE" in o) else None)
        if not g or not r.get("vtdid") or (r.get("writein") or "").upper() == "TRUE":
            continue
        acc[r["vtdid"]][g] += r["votes"]
        races_in[r["vtdid"]][g].add((o, r.get("district")))
    doc = data_mn.table(2022)
    cols = [f"np_{g}" for g in ("county", "county_commissioner", "soil_water", "judicial")] + \
           [f"npn_{g}" for g in ("county", "county_commissioner", "soil_water", "judicial")]
    rows2 = []
    for row in doc["rows"]:
        rec = {k: row.get(k) for k in ("vtdid", "pctname", "pctcode", "mcdfips", "mcdname", "countyfips", "countyname", "totvoting",
                                       "fedonlyab", "presonlyab")}
        for g in ("county", "county_commissioner", "soil_water", "judicial"):
            rec[f"np_{g}"] = acc.get(row["vtdid"], {}).get(g, 0.0)
            rec[f"npn_{g}"] = len(races_in.get(row["vtdid"], {}).get(g, ()))
        rows2.append(rec)
    pdoc = {"fields": list(rows2[0].keys()) if rows2 else [], "rows": rows2}
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    pop = {u: v for u, v in con.execute("SELECT unit_id, value FROM features WHERE state='mn' AND unit_kind='precinct' AND name='pop2020'")}
    con.close()
    lines, _how, _rep2 = data_mn.on_today_lines(2022, pop, pdoc, columns=cols + ["totvoting", "fedonlyab", "presonlyab"])
    out = {}
    for g in ("county", "county_commissioner", "soil_water", "judicial"):
        vals = []
        for v in ids:
            rec = lines.get(v)
            if not rec or not rec.get(f"npn_{g}"):
                vals.append(None)
                continue
            base = (rec["totvoting"] - rec.get("fedonlyab", 0) - rec.get("presonlyab", 0))
            n_races = rec[f"npn_{g}"]
            vals.append(clamp(1 - rec[f"np_{g}"] / (base * n_races), 0.0, 0.95) if base > 0 and n_races > 0 else None)
        known = sorted(x for x in vals if x is not None)
        med = known[len(known) // 2] if known else 0.25
        out[g] = [r6(x if x is not None else med) for x in vals]
    save_json(cache, {"sha256": sha, "ids": len(ids), "groups": out})
    return out


# ============================================================================================== the simulation

def _shared_draws(frame, seed, draws):
    """Every draw's shared terms: the environment and statewide offsets (THETA), each district class's gap, the incumbency
    term, each region's swing, the statewide turnout factor, and the nonpartisan coefficients."""
    rng = rng_for(seed, "shared")
    P = frame["params"]
    env = frame["env"]
    Lc = cholesky(env["cov"])
    m = env["mean"]
    regions = sorted({r.get("region") for r in frame["races"] if r.get("region")})
    out = []
    pos_p, pos_np = frame["priors"]["pos_partisan"], frame["priors"]["pos_nonpartisan"]
    eb = frame["priors"]["endorse_beta"]
    classes = sorted(P["gap"])
    for _d in range(draws):
        z = [rng.gauss(0, 1) for _ in m]
        theta = [m[i] + sum(Lc[i][k] * z[k] for k in range(i + 1)) for i in range(len(m))]
        gap = {c: rng.gauss(P["gap"][c][0], P["gap"][c][1]) for c in classes}
        reg = {r: rng.gauss(0, P["region_sd"]) for r in regions}
        out.append({
            "theta": theta, "gap": gap, "region": reg,
            "inc": rng.gauss(P["inc"][0], P["inc"][1]),
            "turnout": math.exp(rng.gauss(0, frame["priors"]["turnout_sd"])),
            "b_inc": rng.gauss(P["np"]["beta_inc"][0], P["np"]["beta_inc"][1]),
            "b_end": max(0.0, rng.gauss(eb[0], eb[1])),
            "g_p": rng.uniform(pos_p[0], pos_p[1]),
            "g_np": rng.uniform(pos_np[0], pos_np[1]),
        })
    return out


def _race_in_sha(entry, frame):
    """The digest of everything a race's numbers depend on: its own inputs, the shared numbers the simulation reads (the
    environment's mean and spread, the parameters and priors) and the method. Words about the inputs are not inputs."""
    env = frame["env"]
    keep = {"race": entry, "method": frame["method"], "params": frame["params"], "priors": frame["priors"],
            "env": {"theta": env.get("theta"), "mean": env.get("mean"), "cov": env.get("cov")}}
    if entry.get("kind") == "partisan" and entry.get("class") in DISTRICT_CLASSES:
        keep["state_grid"] = frame["state_grid"]
    return R.sha_text(R.canonical(keep))


def _summarise(entry, shares, wins, votes, draws, equal=False):
    seats = entry["seats"]
    cands = []
    n = len(entry["cands"])
    pooled = None
    if equal:
        pooled = sorted(x for k in range(n) for x in shares[k])
    for k, c in enumerate(entry["cands"]):
        xs = pooled if equal else shares[k]
        q = quantiles(xs, (0.5, 0.1, 0.9, 0.025, 0.975))
        chance = (seats / n) if equal else R.stored_chance(wins[k], draws)
        cands.append({"key": c["key"], "name": c["name"], "chance": chance, "median": q[0], "lo80": q[1], "hi80": q[2],
                      "lo95": q[3], "hi95": q[4]})
    out = {"race": entry["race"], "status": "pre", "seats": seats, "equal": equal, "units_in": 0, "units_all": entry.get("units"),
           "ballots": 0, "share_counted": 0.0, "tested": entry.get("tested"), "cands": cands}
    if votes:
        q = quantiles(votes, (0.1, 0.5, 0.9))
        out["exp"] = [q[0], q[1], q[2]]
    return out


def _sim_partisan(entry, frame, shared, rng, draws):
    P = frame["params"]
    pri = frame["priors"]
    cands = entry["cands"]
    n = len(cands)
    office = entry["class"]
    idx_d = [k for k, c in enumerate(cands) if c["p"] == "D"]
    idx_r = [k for k, c in enumerate(cands) if c["p"] == "R"]
    idx_o = [k for k, c in enumerate(cands) if c["p"] not in ("D", "R")]
    two = len(idx_d) == 1 and len(idx_r) == 1
    inc_dir = 0
    for k in idx_d:
        inc_dir += cands[k].get("inc", 0)
    for k in idx_r:
        inc_dir -= cands[k].get("inc", 0)
    f = entry.get("f")
    sg = frame.get("state_grid")
    k_off = entry.get("k")                          # statewide: its place in the shared Gaussian (0: the environment itself)
    dsd = P["district_sd"].get(office, 0.14)
    if two or len(idx_o) > 1:
        # "sole" was sized on races with one other name beside one big party; drawn for each of several such names,
        # their shares add up far past anything on record, so several minor names take the ordinary prior
        prior = P["minor"].get("statewide", P["minor"]["with_majors"]) if k_off is not None else P["minor"]["with_majors"]
    else:
        prior = P["minor"]["sole"]
    minor_mu, minor_sd = prior[0], prior[1]
    minor_cap = min(1.5 * prior[2], 0.6) if len(prior) > 2 else 0.6     # 1.5 times the largest share on record
    wi = P["writein"]["partisan"] if two else P["writein"]["partisan_sole"]
    rot = entry.get("rot")
    shares = [[] for _ in range(n)]
    wins = [0] * n
    votes = []
    base_votes = entry.get("votes")
    for d in range(draws):
        sh = shared[d]
        th = sh["theta"]
        if k_off is not None:
            s2 = expit(th[0] + (th[k_off] if k_off else 0.0))   # the office's offset already holds its candidates' own pull
        elif f:
            mu = inverse(sg, expit(th[0]))
            x = mu + sh["gap"].get(office, 0.0) + sh["inc"] * inc_dir + sh["region"].get(entry.get("region"), 0.0) + rng.gauss(0, dsd)
            s2 = interp(f, x)
        else:
            s2 = expit(th[0] + rng.gauss(0, dsd))
        if rot and two:
            perm = list(range(n))
            rng.shuffle(perm)
            s2 = expit(logit(s2) + sh["g_p"] * (rot[perm[idx_d[0]]] - rot[perm[idx_r[0]]]))
        minors = [min(math.exp(rng.gauss(minor_mu, minor_sd)), minor_cap) for _ in idx_o]
        mt = sum(minors)
        if mt + wi > 0.9:
            scale = 0.9 / (mt + wi)
            minors = [m_ * scale for m_ in minors]
            mt = sum(minors)
        rest = 1.0 - mt - wi
        vals = [0.0] * n
        for j, k in enumerate(idx_o):
            vals[k] = minors[j]
        if two:
            vals[idx_d[0]] = s2 * rest
            vals[idx_r[0]] = (1 - s2) * rest
        else:
            majors = idx_d + idx_r
            for k in majors:
                vals[k] = rest / len(majors)
            if not majors and idx_o:
                pass
        best = max(range(n), key=lambda k: vals[k])
        wins[best] += 1
        for k in range(n):
            shares[k].append(vals[k])
        if base_votes:
            votes.append(base_votes * sh["turnout"] * math.exp(rng.gauss(0, pri["race_votes_sd"])))
    return _summarise(entry, shares, wins, votes, draws)


def _sim_nonpartisan(entry, frame, shared, rng, draws):
    P = frame["params"]
    pri = frame["priors"]
    cands = entry["cands"]
    n = len(cands)
    seats = entry["seats"]
    tau = P["np"]["tau"].get(entry.get("group"), P["np"]["tau"].get("county", 0.45))
    wi = P["writein"]["np"]
    inc = [c.get("inc", 0) for c in cands]
    end = [c.get("end", 0.0) for c in cands]
    first = entry.get("first")
    rot = entry.get("rot")
    df = P["np"].get("df")                          # heavier tails: a race-level scale mixture (Student's t), variance kept
    equal = len(set(inc)) == 1 and len(set(end)) == 1 and first is None
    shares = [[] for _ in range(n)]
    wins = [0] * n
    votes = []
    base_votes = entry.get("votes")
    perm = list(range(n))
    for d in range(draws):
        sh = shared[d]
        t = tau * math.sqrt((df - 2) / rng.gammavariate(df / 2.0, 2.0)) if df else tau
        lw = [sh["b_inc"] * inc[k] + sh["b_end"] * end[k] + rng.gauss(0, t) for k in range(n)]
        if first is not None:
            lw[first] += sh["g_np"]
        elif rot:
            rng.shuffle(perm)
            for k in range(n):
                lw[k] += sh["g_np"] * rot[perm[k]]
        top = max(lw)
        ex = [math.exp(x - top) for x in lw]
        tot = sum(ex)
        vals = [(1 - wi) * x / tot for x in ex]
        if seats == 1:
            wins[max(range(n), key=lambda k: vals[k])] += 1
        else:
            for k in sorted(range(n), key=lambda k: -vals[k])[:seats]:
                wins[k] += 1
        for k in range(n):
            shares[k].append(vals[k])
        if base_votes:
            votes.append(base_votes * sh["turnout"] * math.exp(rng.gauss(0, pri["race_votes_sd"])))
    return _summarise(entry, shares, wins, votes, draws, equal=equal)


def simulate(frame, seed, draws):
    """Every race's numbers from a frame: {"races": [race output]} (runs.record_run's shape). A pure function of
    (frame, seed, draws): the same three always give the same numbers (runs.redo checks it)."""
    shared = _shared_draws(frame, seed, draws)
    out = []
    for entry in frame["races"]:
        st = entry.get("status")
        if st in ("unopposed", "no-candidates"):
            out.append({"race": entry["race"], "status": st, "seats": entry["seats"], "in_sha": _race_in_sha(entry, frame),
                        "cands": [{"key": c["key"], "name": c["name"]} for c in entry["cands"]],
                        "note": "one name for each seat: unopposed, no forecast" if st == "unopposed" else "no candidate filed"})
            continue
        rng = rng_for(seed, entry["race"])
        if entry["kind"] == "partisan":
            res = _sim_partisan(entry, frame, shared, rng, draws)
        else:
            res = _sim_nonpartisan(entry, frame, shared, rng, draws)
        res["in_sha"] = _race_in_sha(entry, frame)
        out.append(res)
    return {"races": out}


# ============================================================================================== a run

def run_pre(now=None, say=print, db=DB, draws=DRAWS, rehearsal=False, dry=False, params=None, params_run=None):
    """One pre-election run for Minnesota, stored as a version (runs.py). `now` is the moment the run stands for (polls
    that ended after it are left out). Returns the run's summary."""
    t0 = time.time()
    started = R.now_utc()
    as_of = now or started
    if isinstance(as_of, dt.datetime) and as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=dt.timezone.utc)
    if as_of.date() < dt.date(2026, 1, 1) or as_of.date() > ELECTION_DAY:
        # a rehearsal replays a past night on its own clock: no 2026 forecast is made from that clock, and nothing is stored
        say(f"    no pre-election run: the clock says {as_of.date()}, outside 2026 before Election Day (a replayed night)")
        return {"skipped": "clock outside 2026 before Election Day"}
    frame, inputs = build_frame(as_of, params, params_run, say, db)
    frame = json.loads(R.canonical(frame))          # the simulation reads exactly what the run keeps
    con = R.connect(db)
    try:
        run = R.new_run_id(con, "pre", STATE, started)
        seed = R.seed_of(run)
        t1 = time.time()
        out = simulate(frame, seed, draws)
        sim_s = time.time() - t1
        if dry:
            say(f"    dry run {run}: {len(out['races'])} races simulated in {sim_s:.1f} s (not stored)")
            return {"run": run, "out": out, "frame": frame, "seconds": round(time.time() - t0, 1), "simulate_s": round(sim_s, 1)}
        with con:
            res = R.record_run(con, run=run, state=STATE, kind="pre", method=METHOD, seed=seed, draws=draws, started=started,
                               as_of=as_of, frame=frame, outputs=out, inputs=inputs, rehearsal=rehearsal,
                               note=f"pre-election forecast; parameters from {frame.get('params_run') or 'defaults'}")
        say(f"    run {run}: {res['races']} races, {res['written']} with new rows; simulated in {sim_s:.1f} s, "
            f"{time.time() - t0:.1f} s in all")
        return {"run": run, **res, "seconds": round(time.time() - t0, 1), "simulate_s": round(sim_s, 1)}
    finally:
        con.close()


# ============================================================================================== self-test

def selftest(say=print):
    ok = True

    def check(what, got, want):
        nonlocal ok
        good = (abs(got - want) < 1e-9) if isinstance(want, float) else got == want
        ok &= good
        say(f"    {'ok ' if good else 'BAD'} {what}: {got!r}" + ("" if good else f" (expected {want!r})"))
    check("logit and expit undo each other", round(expit(logit(0.37)), 12), 0.37)
    rot, sub = rotation_subtotals([("a", 500), ("b", 400), ("c", 300), ("d", 200), ("e", 100)], 2)
    # 500 -> r0, 400 -> r1, 300 -> r1 (lowest 400), 200 -> r0 (500 vs 700), 100 -> r0 (700 vs 700: tie to r0)
    check("rotation: the rule's dealing", rot, [0, 1, 1, 0, 0])
    check("rotation: subtotals", sub, [800.0, 700.0])
    check("rotation: more names than precincts", rotation_subtotals([("a", 10)], 3)[1], [10.0, 0.0, 0.0])
    e = exposures([("a", 500), ("b", 400), ("c", 300), ("d", 200), ("e", 100)], [5, 4, 3, 2, 1], 2)
    check("exposure weighed by expected votes", [round(x, 6) for x in e], [round(8 / 15, 6), round(7 / 15, 6)])
    L = [0.0, 1.0, -1.0]
    f = make_grid([(0, 1.0), (1, 1.0), (2, 1.0)], L, [1.0, 1.0, 1.0])
    check("a grid at zero shift is the average of the precincts", round(interp(f, 0.0), 9), round((0.5 + expit(1) + expit(-1)) / 3, 9))
    check("the grid's inverse finds the shift", round(inverse(f, interp(f, 0.4)), 6), 0.4)
    check("same person across files", same_person("Jane Q. Doe", "JANE DOE"), True)
    check("not the same person", same_person("Jane Doe", "John Doe"), False)
    check("a surname past a suffix", surname_key("John Smith Jr.")[0], "SMITH")
    # a made-up frame: one partisan district, one equal nonpartisan race, one township race, one unopposed race
    params = json.loads(json.dumps(DEFAULT_PARAMS))
    env = {"theta": list(THETA), "mean": [0.1] + [0.0] * len(STATEWIDE_OFFICES),
           "cov": [[0.01 if i == j else 0.0 for j in range(len(THETA))] for i in range(len(THETA))]}
    frame = {"method": METHOD, "params": params, "priors": PRIORS, "env": env, "days_to_election": 20,
             "state_grid": make_grid([(0, 1.0), (1, 1.0), (2, 1.0)], L, [1, 1, 1]),
             "races": [{"race": "D1", "kind": "partisan", "class": "mnleg", "seats": 1, "region": "1", "units": 3, "votes": 1000.0,
                        "f": make_grid([(1, 1.0)], L, [1, 1, 1]), "rot": [0.5, 0.5],
                        "cands": [{"key": "a", "name": "A", "p": "D", "inc": 1}, {"key": "b", "name": "B", "p": "R", "inc": 0}]},
                       {"race": "N1", "kind": "nonpartisan", "group": "county", "seats": 1, "rot": [0.6, 0.4], "units": 2, "votes": 500.0,
                        "cands": [{"key": "c", "name": "C"}, {"key": "d", "name": "D"}]},
                       {"race": "T1", "kind": "nonpartisan", "group": "local", "seats": 1, "first": 1, "units": 1, "votes": 50.0,
                        "cands": [{"key": "e", "name": "E Zed"}, {"key": "f", "name": "F Able"}]},
                       {"race": "U1", "status": "unopposed", "seats": 2, "cands": [{"key": "g", "name": "G"}, {"key": "h", "name": "H"}]}]}
    frame = json.loads(R.canonical(frame))
    a = simulate(frame, 7, 400)
    b = simulate(frame, 7, 400)
    check("the same frame and seed give the same numbers", R.canonical(a) == R.canonical(b), True)
    races = {r["race"]: r for r in a["races"]}
    check("a lean-DFL district with a DFL incumbent favours the DFL", races["D1"]["cands"][0]["chance"] > 0.6, True)
    check("equal chances where nothing separates the candidates", [c["chance"] for c in races["N1"]["cands"]], [0.5, 0.5])
    check("the race says so", races["N1"]["equal"], True)
    check("the first name on a town ballot is favoured", races["T1"]["cands"][1]["chance"] > races["T1"]["cands"][0]["chance"], True)
    check("an unopposed race carries no chance", [c.get("chance") for c in races["U1"]["cands"]], [None, None])
    check("no chance is 0 or 1", all(0 < c["chance"] < 1 for r in a["races"] if r["status"] == "pre" for c in r["cands"]), True)
    return ok


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--state", default="mn")
    ap.add_argument("--draws", type=int, default=DRAWS)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--as-of", help="the moment the run stands for (UTC, ISO), for a rerun of a past day")
    ap.add_argument("--db", default=DB)
    a = ap.parse_args(argv)
    if a.selftest:
        sys.exit(0 if selftest() else 1)
    if a.state.lower() != "mn":
        sys.exit("    only Minnesota is forecast here before Election Day (other states: other_states.py)")
    now = dt.datetime.fromisoformat(a.as_of.replace("Z", "+00:00")) if a.as_of else None
    res = run_pre(now=now, draws=a.draws, dry=a.dry_run, db=a.db)
    if a.dry_run:
        for r in res["out"]["races"][:0]:
            print(r)


if __name__ == "__main__":
    main()
