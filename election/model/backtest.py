"""election/model/backtest.py - how the Minnesota model would have done in 2022 and 2024, and the numbers it is sized
by (ARCHITECTURE.md 4.1 "Calibration"; model.md 3.5). Owned by N16. Analysis; nothing here is a result.

    python -m election.model.backtest --state mn                fit, score, replay, and store a backtest run (the parameters
                                                                forecast.py reads); about ten minutes
    python -m election.model.backtest --state mn --no-replays   the same without the election-night replays
    python -m election.model.backtest --state mn --no-store     print only
    python -m election.model.backtest --selftest                the arithmetic on made-up races; reads no real file

WHAT IS FITTED (each written into the run's frame under "params"; forecast.py uses the newest)
  lean scheme     how past contests are weighted into a precinct's lean (rho per election back, psi on presidential
                  contests, how many elections back): the scheme whose precinct leans best foretold 2022's and 2024's
                  statewide contests (weighted error in log-odds, each contest's own candidates' pull taken out).
  district terms  for U.S. House, state Senate and state House races, with the statewide result known ("oracle"): each
                  district's gap to its prediction, explained by a gap per office and year, an incumbency term (where the
                  record says who held the seat: U.S. House both years from the Clerk's statistics; the state House in 2024
                  from MEDSL's 2022 copy), a regional swing (congressional district) and the district's own error.
  minor parties   what candidates outside the two big parties won, 2012-2024, beside both of them and as the only opponent
                  of one; write-ins likewise.
  offices         how far a statewide office runs from the top of its ticket, 2012-2024 (the spread of an office's offset).
  nonpartisan     county, court and soil and water races of 2022 and 2024 (MEDSL's copies of the Secretary's files,
                  secondary): the edge of the seat's holder (2018's winner of the same office) and each candidate's own
                  unexplained spread, by kind of race.
  widening        after scoring, any spread whose 80 percent ranges held fewer than 80 percent of results is widened until
                  they do (ARCHITECTURE.md 4.1), and the factor is kept.

HOW IT IS SCORED (stored in the backtests and calibration tables; runs.track_json gives the page its #track)
  Scenarios: "oracle" (the statewide result known: tests the district structure), "pre" (as it would have stood: the
  environment from the last presidential result and Minnesota's midterm pattern, with no polls, which the kit lacks for
  those years). Partisan races are scored on one year with the terms fitted on the other ("cross-fitted"); nonpartisan
  races in five folds. Measures: Brier score, log loss, how often the favourite won, how often the 80 and 95 percent
  ranges held the share, the average miss on the share, a calibration table, and two plain rules to beat: "the
  incumbent wins" and "last time repeats". Races never tested (cities, schools, townships, hospital districts: their
  files are John's to save) say so on the page.

THE BLIND SPOTS, MEASURED (in the run's report): roll-off by kind of race (rolloff_summary); how far a rebuilt rotation
can be trusted (position_stability); and the count order, by the replays below.

REPLAYS (the count-order blind spot): 2022 and 2024 replayed precinct by precinct on today's lines in four
orders (random; small and rural first; whole counties with the largest metro counties last; a late absentee batch held
back in every county), scored at 10, 25, 50, 75 and 90 percent counted, with a reference night model (the forecast
moved by the counted precincts' swing against it, by county and statewide, shrunk while few are in). live_model.py
(N17) can be scored the same way through `replay(..., model=)`.
"""

import argparse
import datetime as dt
import json
import math
import os
import random
import re
import sys
import time
from collections import defaultdict

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from election.model import DB, cache_dir, load_json, save_json, sha_file  # noqa: E402
from election.model import data_mn  # noqa: E402
from election.model import forecast as F  # noqa: E402
from election.model import runs as R  # noqa: E402

METHOD = "backtest-1.0"
YEARS = (2022, 2024)
DRAWS = 1000
SCHEMES = [{"rho": rho, "psi": psi, "cycles": k} for rho in (0.05, 0.1, 0.2, 0.3, 0.45, 0.6, 0.75, 0.9)
           for psi in (0.75, 1.0, 1.5, 2.0, 3.0, 5.0, 8.0, 15.0) for k in (1, 2, 3, 4) if not (k == 1 and rho != 0.1)]
NP_TAILS = (None, 10, 6, 4)          # nonpartisan errors: Gaussian, or a race-level scale mixture (Student's t) with these degrees
DISTRICT = {"usrep": "cd", "mnsen": "senate", "mnleg": "house"}
NP_GROUPS = ("county", "judicial", "soil_water")
COUNTY_KINDS = {"COUNTY SHERIFF": "sheriff", "COUNTY ATTORNEY": "county_attorney", "COUNTY AUDITOR/TREASURER": "county_auditor_treasurer",
                "COUNTY AUDITOR": "county_auditor", "COUNTY TREASURER": "county_treasurer", "COUNTY RECORDER": "county_recorder",
                "COUNTY SURVEYOR": "county_surveyor", "COUNTY CORONER": "county_coroner", "COUNTY COMMISSIONER": "county_commissioner",
                "COUNTY PARK COMMISSIONER": "county_park"}
METRO_LAST = ("053", "123", "003", "037", "163", "139", "019")      # Hennepin, Ramsey, Anoka, Dakota, Washington, Scott, Carver
CHECKPOINTS = (0.10, 0.25, 0.50, 0.75, 0.90)
ORDERS = ("random", "small-first", "metro-last", "late-batch")


def say_default(*a):
    print(*a, flush=True)


# ============================================================================================== the shared base

def load_base(db=DB):
    """Today's precincts, their districts, and every feature the backtests read (on today's lines)."""
    ids, props, geo_v = F.precinct_props()
    index = F.members_index(ids, props)
    names = sorted({f"dfl2p_{p}_{y}" for y, ps in F.STATEWIDE_BY_YEAR.items() for p in ps} |
                   {f"ballots_{y}" for y in F.STATEWIDE_BY_YEAR} | {f"registered_{y}" for y in F.STATEWIDE_BY_YEAR} |
                   {f"rolloff_{p}_{y}" for y, ps in F.STATEWIDE_BY_YEAR.items() for p in ps} |
                   {f"rolloff_{c}_{y}" for c in ("usrep", "mnsen", "mnleg") for y in F.STATEWIDE_BY_YEAR} |
                   {f"dfl2p_contested_{c}_{y}" for c in ("usrep", "mnsen", "mnleg") for y in F.STATEWIDE_BY_YEAR} | {"pop2020"})
    feats, state, build = F.read_features(names, db)
    counties = [props[v].get("county") for v in ids]
    return {"ids": ids, "props": props, "index": index, "feats": feats, "state": state, "build": build, "counties": counties,
            "pos": {v: i for i, v in enumerate(ids)}}


def col(base, name):
    """A feature as a list in the precincts' order (None where the record has no figure)."""
    f = base["feats"].get(name, {})
    return [f.get(v) for v in base["ids"]]


def votes_vector(base, year, cls):
    """Expected votes in a class of race by precinct for a year's prediction: the ballots of the same kind of election
    four years before, less that election's roll-off for the class (the state House's where the class did not run)."""
    prev = year - 4
    b = col(base, f"ballots_{prev}")
    ro = col(base, f"rolloff_{cls}_{prev}")
    alt = col(base, f"rolloff_mnleg_{prev}")
    out = []
    for i in range(len(b)):
        r = ro[i] if ro[i] is not None else (alt[i] if alt[i] is not None else 0.05)
        out.append(max(b[i] or 0.0, 0.0) * (1 - F.clamp(r, 0.0, 0.9)))
    return out


# ============================================================================================== past partisan contests

def partisan_contests(year, base, say=say_default):
    """Every partisan contest of a year from the Secretary's certified precinct table (data_mn.contests): statewide
    ones, and districts of the U.S. House, state Senate and state House with today's precincts of the same district
    (the plan of 2022 is today's)."""
    out = []
    statewide = set(F.STATEWIDE_BY_YEAR.get(year, ())) - {"ussse"}
    unmatched = []
    for c in data_mn.contests(year):
        cls = c["prefix"]
        if cls not in statewide and cls not in DISTRICT:
            continue
        T = sum(r["total"] for r in c["by_precinct"].values())
        D = sum(r.get("dfl", 0) for r in c["by_precinct"].values())
        Rv = sum(r.get("r", 0) for r in c["by_precinct"].values())
        wi = sum(r.get("wi", 0) for r in c["by_precinct"].values())
        minors = {}
        for code in c["parties"]:
            if code in ("dfl", "r", "wi"):
                continue
            v = sum(r.get(code, 0) for r in c["by_precinct"].values())
            if v > 0:
                minors[code] = v
        rec = {"id": c["id"], "year": year, "class": cls, "district": c["district"], "D": D, "R": Rv, "T": T, "wi": wi,
               "minors": minors, "statewide": cls in statewide}
        if cls in DISTRICT:
            mem = base["index"].get(f"{DISTRICT[cls]}:{c['district']}", [])
            if not mem:
                unmatched.append(c["id"])
                continue
            rec["members"] = mem
            cds = defaultdict(int)
            for i, _w in mem:
                cds[base["props"][base["ids"][i]].get("cd")] += 1
            rec["region"] = max(cds, key=cds.get)
        out.append(rec)
    if unmatched:
        say(f"      {year}: {len(unmatched)} district contests with no precinct of that district today: {unmatched[:8]}")
    return out


def clerk_house(year):
    """{district: [(name, party letter, votes)]} for Minnesota's U.S. House races from the Clerk's statistics."""
    path, _url = data_mn.clerk_pdf(year)
    out = defaultdict(list)
    for section, dist, lines in data_mn.read_clerk(path):
        if not section.startswith("FOR UNITED STATES REPRESENTATIVE") or not dist:
            continue
        for label, v in lines:
            name, _, party = label.rpartition(",")
            p = data_mn._party_of(label)
            out[str(int(dist))].append((name.strip() or label, {"dfl": "D", "r": "R"}.get(p, "O"), v))
    return out


def medsl_house(year):
    """{district: [(name, party letter, votes)]} for the state House from MEDSL's copy (write-ins left out)."""
    rows, _doc = data_mn.medsl_rows(year)
    tot = defaultdict(lambda: defaultdict(int))
    party = {}
    for r in rows:
        if r["office"] != "STATE HOUSE" or (r.get("writein") or "").upper() == "TRUE":
            continue
        d = re.sub(r"^0+(?=\d)", "", (r.get("district") or "").strip().upper())
        tot[d][r["candidate"]] += r["votes"]
        pd = (r.get("party_detailed") or "").upper()
        party[(d, r["candidate"])] = "D" if pd.startswith("DEMOCRAT") else "R" if pd.startswith("REPUBLICAN") else "O"
    return {d: [(n, party[(d, n)], v) for n, v in c.items()] for d, c in tot.items()}


def _winner(cands):
    return max(cands, key=lambda c: c[2]) if cands else None


def set_incumbency(year, races, say=say_default):
    """inc_dir (+1 a DFL holder runs, -1 a Republican holder runs, 0 open) where the record says who held the seat; inc_known."""
    notes = {}
    try:
        prev = clerk_house(year - 2)
        now = clerk_house(year)
        winners = [_winner(c) for c in prev.values()]
        for r in races:
            if r["class"] != "usrep":
                continue
            cs = now.get(r["district"], [])
            inc = 0
            for name, p, _v in cs:
                if any(w and F.same_person(name, w[0]) for w in winners):
                    inc += 1 if p == "D" else -1 if p == "R" else 0
            r["inc_dir"], r["inc_known"] = inc, True
        notes["usrep"] = f"holders from the Clerk's {year - 2} statistics"
    except Exception as e:  # noqa: BLE001  without the Clerk's pages the U.S. House races count as holder unknown
        notes["usrep"] = f"holders not read ({e.__class__.__name__})"
    if year == 2024:
        prev = medsl_house(2022)
        now = medsl_house(2024)
        for r in races:
            if r["class"] != "mnleg":
                continue
            w = _winner(prev.get(r["district"], []))
            inc = 0
            for name, p, _v in now.get(r["district"], []):
                if w and F.same_person(name, w[0]):
                    inc += 1 if p == "D" else -1 if p == "R" else 0
            r["inc_dir"], r["inc_known"] = inc, bool(w)
        notes["mnleg"] = "holders from MEDSL's copy of the 2022 results (secondary)"
    for r in races:
        r.setdefault("inc_dir", 0)
        r.setdefault("inc_known", False)
    return notes


# ============================================================================================== fitting: the lean scheme

def fit_scheme(base, say=say_default):
    """The lean scheme whose precinct leans best foretold the statewide contests of 2022 and 2024."""
    table = []
    for scheme in SCHEMES:
        errs = []
        for Y in YEARS:
            L, _used = F.lean_vector(base["feats"], base["state"], base["ids"], Y, scheme, base["counties"])
            for p in F.STATEWIDE_BY_YEAR[Y]:
                s = col(base, f"dfl2p_{p}_{Y}")
                S = base["state"].get(f"dfl2p_{p}_{Y}")
                b = col(base, f"ballots_{Y}")
                ro = col(base, f"rolloff_{p}_{Y}")
                pts = []
                for i in range(len(L)):
                    if s[i] is None or not b[i]:
                        continue
                    w = b[i] * (1 - (ro[i] or 0))
                    pts.append((F.logit(F.clamp(s[i], 0.01, 0.99)) - F.logit(S) - L[i], w))
                tw = sum(w for _e, w in pts)
                m = sum(e * w for e, w in pts) / tw
                errs.append(math.sqrt(sum(w * (e - m) ** 2 for e, w in pts) / tw))
        table.append((sum(errs) / len(errs), scheme))
    table.sort(key=lambda t: t[0])
    best = table[0][1]
    say(f"    lean scheme: rho {best['rho']}, psi {best['psi']}, {best['cycles']} elections back "
        f"(precinct error {table[0][0]:.4f} in log-odds; the worst scheme {table[-1][0]:.4f})")
    return best, [[round(e, 5), s] for e, s in table[:10]]


# ============================================================================================== fitting: districts

def anchor_grid(base, year, L):
    top = F.TOP_OF_TICKET[year - 4]
    b = col(base, f"ballots_{year - 4}")
    ro = col(base, f"rolloff_{top}_{year - 4}")
    V = [max(b[i] or 0.0, 0.0) * (1 - (ro[i] or 0.0)) for i in range(len(b))]
    return F.make_grid(base["index"]["state:MN"], L, V)


def district_residuals(base, year, races, scheme):
    """Each contested district race's shift from its prediction with the year's statewide top of the ticket known:
    e = (the statewide shift that reproduces the district's actual two-party share) - (the shift that reproduces the
    statewide result). Also each race's grid, for scoring."""
    L, _ = F.lean_vector(base["feats"], base["state"], base["ids"], year, scheme, base["counties"])
    sg = anchor_grid(base, year, L)
    top = F.TOP_OF_TICKET[year]
    G = base["state"][f"dfl2p_{top}_{year}"]
    mu = F.inverse(sg, G)
    vv = {cls: votes_vector(base, year, cls) for cls in DISTRICT}
    for r in races:
        if r["statewide"]:
            continue
        r["f"] = F.make_grid(r["members"], L, vv[r["class"]])
        r["contested"] = r["D"] > 0 and r["R"] > 0
        if r["contested"]:
            a = r["D"] / (r["D"] + r["R"])
            r["e"] = F.inverse(r["f"], a) - mu
    return {"L": L, "sg": sg, "G": G, "mu": mu}


def fit_districts(races):
    """Gap per (class, year), incumbency slope, region and district spreads, from contested district races."""
    groups = defaultdict(list)
    for r in races:
        if not r["statewide"] and r.get("contested"):
            groups[(r["class"], r["year"])].append(r)
    # the incumbency slope, within groups, on races whose holders are on record
    sxy = sxx = 0.0
    for g, rs in groups.items():
        known = [r for r in rs if r["inc_known"]]
        if len(known) < 3:
            continue
        mi = sum(r["inc_dir"] for r in known) / len(known)
        me = sum(r["e"] for r in known) / len(known)
        for r in known:
            sxy += (r["inc_dir"] - mi) * (r["e"] - me)
            sxx += (r["inc_dir"] - mi) ** 2
    iota = sxy / sxx if sxx else 0.0
    gap = {}
    for g, rs in groups.items():
        gap[g] = sum(r["e"] - (iota * r["inc_dir"] if r["inc_known"] else 0.0) for r in rs) / len(rs)
    for g, rs in groups.items():
        for r in rs:
            r["u"] = r["e"] - gap[g] - (iota * r["inc_dir"] if r["inc_known"] else 0.0)
    # regions: congressional district within a year
    by_reg = defaultdict(list)
    for rs in groups.values():
        for r in rs:
            if r["inc_known"] or r["class"] == "usrep":
                by_reg[(r["year"], r["region"])].append(r["u"])
    within, dof = 0.0, 0
    for us in by_reg.values():
        m = sum(us) / len(us)
        within += sum((u - m) ** 2 for u in us)
        dof += len(us) - 1
    s2w = within / dof if dof else 0.0
    reg_terms = [sum(us) / len(us) for us in by_reg.values() if len(us) >= 3]
    reg_n = [len(us) for us in by_reg.values() if len(us) >= 3]
    sig_reg2 = max(0.0, sum(m * m - s2w / n for m, n in zip(reg_terms, reg_n)) / len(reg_terms)) if reg_terms else 0.0
    # district spread by class (within region): on races whose holders are known where there are eight or more, else on
    # all the class's races, else the state House's (a class with fewer than eight races has no spread of its own)
    dsd, dsd_from = {}, {}
    for cls in DISTRICT:
        known = [r for rs in groups.values() for r in rs if r["class"] == cls and r["inc_known"]]
        every = [r for rs in groups.values() for r in rs if r["class"] == cls]
        sel, how = (known, "holders known") if len(known) >= 8 else (every, "holders not all known") if len(every) >= 8 else (None, None)
        if sel:
            res = [r["u"] for r in sel]
            m = sum(res) / len(res)
            dsd[cls] = math.sqrt(max(sum((x - m) ** 2 for x in res) / max(len(res) - 1, 1) - sig_reg2, 0.0004))
            dsd_from[cls] = f"{len(sel)} races, {how}"
    for cls in DISTRICT:
        if cls not in dsd:
            other = "mnleg" if "mnleg" in dsd else next(iter(dsd), None)
            dsd[cls] = dsd[other] if other else 0.14
            dsd_from[cls] = f"too few races: the spread of {other or 'the default'}"
    unknown = [r["u"] for rs in groups.values() for r in rs if not r["inc_known"] and r["class"] != "usrep"]
    se_iota = math.sqrt(s2w / sxx) if sxx else 0.05
    return {"iota": iota, "iota_se": se_iota, "gap": {f"{c}-{y}": v for (c, y), v in gap.items()},
            "region_sd": math.sqrt(sig_reg2), "district_sd": dsd, "district_sd_from": dsd_from,
            "unknown_holder_sd": (math.sqrt(sum(x * x for x in unknown) / len(unknown)) if unknown else None),
            "n": {f"{c}-{y}": len(rs) for (c, y), rs in groups.items()}}


def params_from(fit, scheme, minor, writein, office_sd, np_fit, gap_years=None, widen=1.0, senate_sd=None):
    """The forecast's parameter set from a district fit (2026 uses both years' fits; a scored year uses the other's)."""
    gaps = defaultdict(list)
    for key, v in fit["gap"].items():
        c, y = key.split("-")
        if gap_years is None or int(y) in gap_years:
            gaps[c].append((v, fit["n"].get(key, 1)))
    gap = {}
    for c in DISTRICT:
        vals = gaps.get(c) or gaps.get("mnleg") or [(0.0, 1)]
        m = sum(v * n for v, n in vals) / sum(n for _v, n in vals)          # each year's gap weighed by its races
        big = [v for v, n in vals if n >= 8]
        spread = (max(big) - min(big)) / 2 if len(big) > 1 else 0.0
        gap[c] = [m, max(0.04, spread)]
    dsd = {c: (fit["district_sd"].get(c) or fit["district_sd"].get("mnleg") or 0.14) * widen for c in DISTRICT}
    return {"fitted": True, "source": f"backtest {METHOD}", "lean": scheme, "gap": gap,
            "inc": [fit["iota"], max(fit["iota_se"], 0.02)], "district_sd": dsd, "region_sd": fit["region_sd"] * widen,
            "minor": minor, "writein": writein, "office_sd": office_sd, "office_sd_senate": senate_sd or office_sd, "np": np_fit,
            "turnout": {"precinct_sd": 0.10}, "widen": widen}


# ============================================================================================== fitting: minor parties, offices

def fit_minor(say=say_default):
    """Log-share of candidates outside the two big parties, 2012-2024: beside both (statewide and district races
    apart) and as the only opponent of one; write-in shares likewise."""
    acc = {"statewide": [], "with_majors": [], "sole": []}
    wi = {"partisan": [], "partisan_sole": []}
    for year in data_mn.YEARS:
        for c in data_mn.contests(year):
            if c["class"] == "question":
                continue
            T = sum(r["total"] for r in c["by_precinct"].values())
            if T <= 0:
                continue
            D = sum(r.get("dfl", 0) for r in c["by_precinct"].values())
            Rv = sum(r.get("r", 0) for r in c["by_precinct"].values())
            both = D > 0 and Rv > 0
            if not both and not (D > 0 or Rv > 0):
                continue
            w = sum(r.get("wi", 0) for r in c["by_precinct"].values())
            wi["partisan" if both else "partisan_sole"].append(w / T)
            for code in c["parties"]:
                if code in ("dfl", "r", "wi"):
                    continue
                v = sum(r.get(code, 0) for r in c["by_precinct"].values())
                if v <= 0:
                    continue
                grp = ("statewide" if c["district"] == "state" else "with_majors") if both else "sole"
                acc[grp].append(math.log(v / T))
    out = {}
    for g, xs in acc.items():
        m = sum(xs) / len(xs)
        # [mean log-share, its spread, the largest share any such candidate won]: a draw is held to 1.5 times that largest
        # share, so the model never gives a kind of candidate a chance the 2012-2024 record does not come near
        out[g] = [m, math.sqrt(sum((x - m) ** 2 for x in xs) / max(len(xs) - 1, 1)), math.exp(max(xs))]
    w = {k: (sum(v) / len(v) if v else 0.002) for k, v in wi.items()}
    say(f"    minor candidates: beside both parties statewide {math.exp(out['statewide'][0]):.1%} (n {len(acc['statewide'])}), "
        f"in districts {math.exp(out['with_majors'][0]):.1%} (n {len(acc['with_majors'])}), as the only opponent "
        f"{math.exp(out['sole'][0]):.1%} (n {len(acc['sole'])}); write-ins {w['partisan']:.2%} / {w['partisan_sole']:.2%}")
    return out, w, {g: len(xs) for g, xs in acc.items()}


def fit_office_sd(state, kinds=("mnsos", "mnag", "mnaud")):
    """The spread of a statewide office's two-party share against its year's top of the ticket (log-odds), 2012-2024,
    for the offices in `kinds` (the constitutional offices against the governor; the U.S. Senate against the top of its
    ticket, whose candidates pull further). Returns (spread, contests, mean)."""
    devs = []
    for y, ps in F.STATEWIDE_BY_YEAR.items():
        top = F.TOP_OF_TICKET[y]
        t = state.get(f"dfl2p_{top}_{y}")
        for p in ps:
            if p == top or p not in kinds or state.get(f"dfl2p_{p}_{y}") is None:
                continue
            devs.append(F.logit(state[f"dfl2p_{p}_{y}"]) - F.logit(t))
    m = sum(devs) / len(devs)
    return math.sqrt(sum((d - m) ** 2 for d in devs) / (len(devs) - 1)), len(devs), m


# ============================================================================================== nonpartisan contests (MEDSL)

ORD = {"1ST": 1, "2ND": 2, "3RD": 3}


def _court_key(year, office, district):
    """("district_court", judicial district, seat) / ("court_of_appeals", seat) / ("supreme_court", seat) or None."""
    o, d = office.upper().strip(), (district or "").upper().strip()
    if "CHIEF JUSTICE" in o:
        return ("supreme_court", "chief")
    if "SUPREME COURT" in o:
        m = re.search(r"COURT\s+(\d+)$", o) or re.search(r"COURT\s+(\d+)", d) or re.match(r"^0*(\d+)$", d)
        return ("supreme_court", int(m.group(1))) if m else None
    if "COURT OF APPEALS" in o:
        m = re.search(r"APPEALS\s+(\d+)$", o) or re.search(r"COURT\s+(\d+)", d) or re.match(r"^0*(\d+)$", d)
        return ("court_of_appeals", int(m.group(1))) if m else None
    if "DISTRICT COURT" in o:
        m = re.match(r"^JUDGE - (\d+)(?:ST|ND|RD|TH) DISTRICT COURT (\d+)$", o)
        if m:
            return ("district_court", int(m.group(1)), int(m.group(2)))
        m = re.match(r"^DISTRICT COURT (\d+) JUDGE$", o)
        md = re.match(r"^0*(\d+)", d)
        if m and md:
            return ("district_court", int(md.group(1)), int(m.group(1)))
        m = re.match(r"^0*(\d+),\s*COURT\s+(\d+)$", d)
        if m:
            return ("district_court", int(m.group(1)), int(m.group(2)))
    return None


def np_contests(year):
    """{race key: {"group", "cands": {name: votes}, "wi": votes, "county", "kind"}} from MEDSL's file of a year."""
    rows, _doc = data_mn.medsl_rows(year)
    out = {}
    for r in rows:
        o = r["office"].upper().strip()
        special = (r.get("special") or "").upper() == "TRUE" or o.startswith("SPECIAL ELECTION")
        base_o = re.sub(r"^SPECIAL ELECTION FOR\s+", "", o)
        county = (r.get("county_fips") or "")[-3:]
        if base_o in COUNTY_KINDS:
            kind = COUNTY_KINDS[base_o]
            d = F._dist_key(r.get("district")) if kind in ("county_commissioner", "county_park") else ""
            key = (year, "county", kind, county, d, special)
            grp = "county"
        elif base_o == "SOIL AND WATER SUPERVISOR":
            key = (year, "soil_water", "soil_water", county, F._dist_key(r.get("district")), special)
            kind, grp = "soil_water", "soil_water"
        else:
            ck = _court_key(year, base_o, r.get("district"))
            if not ck:
                continue
            key = (year, "judicial") + tuple(map(str, ck)) + (special,)
            kind, grp = ck[0], "judicial"
        rec = out.setdefault(key, {"group": grp, "kind": kind, "county": county if grp != "judicial" else None, "cands": defaultdict(int),
                                   "wi": 0, "counties": set(), "year": year})
        rec["counties"].add(county)
        if (r.get("writein") or "").upper() == "TRUE":
            rec["wi"] += r["votes"]
        else:
            rec["cands"][r["candidate"]] += r["votes"]
    for rec in out.values():
        rec["cands"] = dict(rec["cands"])
        rec["counties"] = sorted(rec["counties"])
    return out


def np_incumbency(races, prev):
    """Marks a candidate as the seat's holder when they won the same kind of office in the same place in `prev` (the
    election one term earlier): county offices in the same county (a commissioner in any district of it: the lines
    were redrawn in 2022), soil and water in the same county, a judge on the same court (and judicial district)."""
    winners = defaultdict(list)
    for key, rec in prev.items():
        if not rec["cands"]:
            continue
        w = max(rec["cands"], key=rec["cands"].get)
        place = rec["county"] if rec["group"] != "judicial" else (key[2], key[3] if key[2] == "district_court" else "")
        winners[(rec["group"], rec["kind"], place)].append(w)
    for key, rec in races.items():
        place = rec["county"] if rec["group"] != "judicial" else (key[2], key[3] if key[2] == "district_court" else "")
        ws = winners.get((rec["group"], rec["kind"], place), [])
        rec["inc"] = {n: 1 if any(F.same_person(n, w) for w in ws) else 0 for n in rec["cands"]}
        rec["inc_known"] = True


def fit_np(races):
    """Log-ratio regression: log(votes) centred within each race, on the holder's mark centred likewise. Returns
    beta, its standard error, and the unexplained spread tau by group (pooled where a group has too few races)."""
    sxy = sxx = 0.0
    pts = []
    for rec in races:
        names = [n for n, v in rec["cands"].items() if v > 0]
        if len(names) < 2:
            continue
        y = [math.log(rec["cands"][n]) for n in names]
        x = [rec["inc"].get(n, 0) for n in names]
        my, mx = sum(y) / len(y), sum(x) / len(x)
        pts.append((rec["group"], [(xi - mx, yi - my) for xi, yi in zip(x, y)]))
        for xi, yi in zip(x, y):
            sxy += (xi - mx) * (yi - my)
            sxx += (xi - mx) ** 2
    beta = sxy / sxx if sxx else 0.0
    ss = defaultdict(float)
    dof = defaultdict(int)
    for g, ps in pts:
        ss[g] += sum((yc - beta * xc) ** 2 for xc, yc in ps)
        dof[g] += len(ps) - 1
    pooled = math.sqrt(sum(ss.values()) / max(sum(dof.values()) - 1, 1))
    tau = {g: (math.sqrt(ss[g] / dof[g]) if dof[g] >= 15 else pooled) for g in NP_GROUPS}
    se = pooled / math.sqrt(sxx) if sxx else 0.2
    return {"beta_inc": [beta, se], "tau": tau, "n": {g: dof[g] for g in NP_GROUPS}, "pooled_tau": pooled}


# ============================================================================================== frames for the past

def partisan_frame(base, year, races, params, scenario, ctx):
    """A frame in forecast.py's shape for one past year's partisan races."""
    if scenario == "oracle":
        g_mean, g_sd = F.logit(ctx["G"]), 1e-4
    else:
        g_mean, g_sd = pre_environment(base["state"], year), F.PRIORS["env_no_polls_sd"]
    statewide = sorted({r["class"] for r in races if r["statewide"]} - {F.TOP_OF_TICKET[year]})
    theta = ["G"] + statewide
    m = [g_mean] + [0.0] * len(statewide)
    cov = [[0.0] * len(theta) for _ in theta]
    cov[0][0] = g_sd ** 2
    for k in range(1, len(theta)):
        cov[k][k] = (params["office_sd_senate"] if theta[k] in ("ussen", "ussse") else params["office_sd"]) ** 2
    entries = []
    for r in races:
        if r["statewide"] and scenario == "oracle":
            continue
        if not r["statewide"] and not (r["D"] > 0 or r["R"] > 0):
            continue
        cands = []
        if r["D"] > 0:
            cands.append({"key": "D", "name": "D", "p": "D", "inc": 1 if r.get("inc_dir", 0) > 0 else 0})
        if r["R"] > 0:
            cands.append({"key": "R", "name": "R", "p": "R", "inc": 1 if r.get("inc_dir", 0) < 0 else 0})
        for code in sorted(r["minors"]):
            cands.append({"key": code, "name": code, "p": "O"})
        if len(cands) < 2:
            continue
        e = {"race": r["id"], "kind": "partisan", "class": r["class"], "seats": 1, "cands": cands, "status": "pre",
             "tested": "backtest"}
        if r["statewide"]:
            e["k"] = 0 if r["class"] == F.TOP_OF_TICKET[year] else theta.index(r["class"])
        else:
            e["f"] = [F.r6(x) for x in r["f"]]
            e["region"] = r["region"]
        entries.append(e)
    frame = {"method": F.METHOD, "params": params, "priors": F.PRIORS, "days_to_election": 0,
             "env": {"theta": theta, "mean": m, "cov": cov}, "state_grid": [F.r6(x) for x in ctx["sg"]], "races": entries}
    return json.loads(R.canonical(frame))


def pre_environment(state, year):
    """The environment as it stood before a past election with no polls: the last presidential result, and in a midterm
    the president's party's average loss in Minnesota's earlier midterms (governor against the presidential vote two
    years before), all in log-odds."""
    last_pres = max(y for y, t in F.TOP_OF_TICKET.items() if t == "usprs" and y < year)
    g = F.logit(state[f"dfl2p_usprs_{last_pres}"])
    if F.TOP_OF_TICKET[year] == "mngov":
        pres_party_dfl = {2012: True, 2016: False, 2020: True}       # the party holding the presidency after each election
        losses = []
        for mid in (2014, 2018):
            if mid >= year:
                continue
            d = F.logit(state[f"dfl2p_mngov_{mid}"]) - F.logit(state[f"dfl2p_usprs_{mid - 2}"])
            losses.append(-d if pres_party_dfl[mid - 2] else d)
        loss = sum(losses) / len(losses) if losses else 0.0
        g += -loss if pres_party_dfl[last_pres] else loss
    return g


def np_frame(races, params, base=None):
    entries = []
    for key, rec in sorted(races.items(), key=lambda kv: str(kv[0])):
        names = sorted(n for n, v in rec["cands"].items() if v > 0)
        if len(names) < 2:
            continue
        cands = [{"key": f"c{k}", "name": n, "inc": rec["inc"].get(n, 0) if rec.get("inc_known") else 0} for k, n in enumerate(names)]
        rot = None
        if base is not None and rec["group"] != "judicial" and rec.get("county"):
            mem = base["index"].get(f"county:{rec['county']}", [])
            regs = col(base, "registered_2022")
            if mem:
                rot = F.exposures([(base["ids"][i], regs[i] or 0) for i, _w in mem], [regs[i] or 0 for i, _w in mem], len(names))
        entries.append({"race": rec["rid"], "kind": "nonpartisan", "group": rec["group"], "seats": 1, "cands": cands, "status": "pre",
                        "rot": [F.r6(x) for x in rot] if rot else None, "tested": "backtest"})
    frame = {"method": F.METHOD, "params": params, "priors": F.PRIORS, "days_to_election": 0,
             "env": {"theta": ["G"], "mean": [0.0], "cov": [[1e-8]]}, "races": entries}
    return json.loads(R.canonical(frame))


# ============================================================================================== scoring

def score_rows(out, actual):
    """[(race, choice, chance, median, lo80, hi80, lo95, hi95, actual share, won)] for a simulation's races against what
    happened (actual: {race: {choice: (share, won)}})."""
    rows = []
    for r in out["races"]:
        if r.get("status") != "pre":
            continue
        a = actual.get(r["race"])
        if not a:
            continue
        for c in r["cands"]:
            share, won = a.get(c["key"], (None, None))
            if share is None:
                continue
            rows.append((r["race"], c["key"], c["chance"], c["median"], c["lo80"], c["hi80"], c["lo95"], c["hi95"], share, won))
    return rows


def measures(rows, base_inc=None, base_last=None):
    """Brier score, log loss, favourite's record, ranges held, average miss, and a calibration table."""
    by_race = defaultdict(list)
    for row in rows:
        by_race[row[0]].append(row)
    n = len(by_race)
    if not n:
        return {}
    brier = ll = fav = 0.0
    for race, rs in by_race.items():
        brier += sum((r[2] - r[9]) ** 2 for r in rs)
        w = [r for r in rs if r[9]]
        ll += -math.log(max(w[0][2], 1e-4)) if w else 0.0
        top = max(rs, key=lambda r: r[2])
        fav += 1 if top[9] else 0
    c80 = sum(1 for r in rows if r[4] <= r[8] <= r[5]) / len(rows)
    c95 = sum(1 for r in rows if r[6] <= r[8] <= r[7]) / len(rows)
    mae = sum(abs(r[3] - r[8]) for r in rows) / len(rows)
    bins = defaultdict(lambda: [0, 0, 0.0])
    for r in rows:
        b = min(int(r[2] * 10), 9)
        bins[b][0] += 1
        bins[b][1] += r[9]
        bins[b][2] += r[2]
    out = {"races": n, "brier": brier / n, "logloss": ll / n, "favourite_won": fav / n, "cover80": c80, "cover95": c95,
           "mae_share": mae, "candidates": len(rows)}
    for b, (k, wins, ps) in sorted(bins.items()):
        out[f"bin{b * 10:02d}_{b * 10 + 10:02d}"] = [round(ps / k, 4), round(wins / k, 4), k]
    for name, base in (("incumbent_wins", base_inc), ("last_time_repeats", base_last)):
        if not base:
            continue
        bs, k, right = 0.0, 0, 0
        for race, rs in by_race.items():
            pick = base.get(race)
            if pick is None:
                continue
            k += 1
            for r in rs:
                p = 0.99 if r[1] == pick else 0.01 / max(len(rs) - 1, 1)
                bs += (p - r[9]) ** 2
            right += 1 if any(r[1] == pick and r[9] for r in rs) else 0
        if k:
            out[f"{name}_brier"] = bs / k
            out[f"{name}_right"] = right / k
            out[f"{name}_races"] = k
            # the model on the same races, for a fair comparison
            mb = sum(sum((r[2] - r[9]) ** 2 for r in by_race[race]) for race in base if race in by_race) / k
            out[f"model_brier_on_{name}_races"] = mb
    return out


def widen_factor(rows_fn, target=0.80, lo=1.0, hi=2.5):
    """The smallest factor (in steps of 0.05) on the spreads at which the 80 percent ranges hold at least `target`."""
    f = lo
    while f <= hi + 1e-9:
        c = rows_fn(f)
        if c >= target:
            return round(f, 2), c
        f += 0.05
    return round(hi, 2), rows_fn(hi)


# ============================================================================================== the backtest run

def run(say=say_default, db=DB, draws=DRAWS, replays=False, store=True):
    t0 = time.time()
    started = R.now_utc()
    say("    reading the precincts and features")
    base = load_base(db)
    scheme, scheme_table = fit_scheme(base, say)
    minor, writein, minor_n = fit_minor(say)
    office_sd, office_n, office_mean = fit_office_sd(base["state"])
    senate_sd, senate_n, senate_mean = fit_office_sd(base["state"], ("ussen", "ussse"))
    say(f"    statewide offices against the top of their ticket: constitutional offices {office_sd:.3f} in log-odds over {office_n} "
        f"contests (mean {office_mean:+.3f}); U.S. Senate {senate_sd:.3f} over {senate_n} (mean {senate_mean:+.3f})")
    # partisan races of both years, with holders and residuals
    races, ctx, inc_notes = {}, {}, {}
    for Y in YEARS:
        races[Y] = partisan_contests(Y, base, say)
        inc_notes[Y] = set_incumbency(Y, races[Y], say)
        ctx[Y] = district_residuals(base, Y, races[Y], scheme)
        say(f"    {Y}: {len(races[Y])} partisan contests, {sum(1 for r in races[Y] if r.get('contested'))} contested districts, "
            f"holders known in {sum(1 for r in races[Y] if r.get('inc_known'))}")
    fit_all = fit_districts(races[2022] + races[2024])
    fit_by = {Y: fit_districts(races[Y]) for Y in YEARS}
    say(f"    districts (both years): incumbency {fit_all['iota']:+.3f} (se {fit_all['iota_se']:.3f}), region {fit_all['region_sd']:.3f}, "
        f"district {', '.join(f'{c} {v:.3f}' for c, v in fit_all['district_sd'].items())}; gaps "
        f"{', '.join(f'{k} {v:+.3f}' for k, v in sorted(fit_all['gap'].items()))}")
    # nonpartisan races: 2022 with 2018's holders; 2024's courts with 2018's (six-year terms); 2024's county and soil and
    # water races have no holder on file (2020's file is not read), and are scored as the record-silent case
    say("    nonpartisan races (MEDSL)")
    np_all = {}
    c2018 = np_contests(2018)
    for Y in YEARS:
        cs = np_contests(Y)
        for key, rec in cs.items():
            rec["rid"] = f"{Y}-np-" + "-".join(str(k) for k in key[1:] if k not in (True, False, "")) + ("-special" if key[-1] is True else "")
        if Y == 2022:
            local = {k: v for k, v in cs.items() if v["group"] in ("county", "soil_water")}
            np_incumbency(local, {k: v for k, v in c2018.items() if v["group"] in ("county", "soil_water")})
            for k, v in cs.items():
                if v["group"] == "judicial":          # 2022's judges were last elected in 2016, whose file is not read
                    v["inc"], v["inc_known"] = {n: 0 for n in v["cands"]}, False
        else:
            courts = {k: v for k, v in cs.items() if v["group"] == "judicial"}
            np_incumbency(courts, {k: v for k, v in c2018.items() if v["group"] == "judicial"})
            for k, v in cs.items():
                if v["group"] != "judicial":
                    v["inc"], v["inc_known"] = {n: 0 for n in v["cands"]}, False
        np_all[Y] = cs
    contested = [rec for Y in YEARS for rec in np_all[Y].values() if sum(1 for v in rec["cands"].values() if v > 0) >= 2]
    known = [r for r in contested if r["inc_known"]]
    np_fit = fit_np(known)
    np_fit_silent = fit_np([r for r in contested if not r["inc_known"]])
    say(f"    nonpartisan: {len(contested)} contested races ({len(known)} with the holder on record); holder's edge "
        f"{np_fit['beta_inc'][0]:+.3f} (se {np_fit['beta_inc'][1]:.3f}) in log-share; spread "
        f"{', '.join(f'{g} {t:.3f}' for g, t in np_fit['tau'].items())} (where no holder is on record: {np_fit_silent['pooled_tau']:.3f})")
    np_wi = [rec["wi"] / (rec["wi"] + sum(rec["cands"].values())) for rec in contested if rec["wi"] + sum(rec["cands"].values()) > 0]
    writein = dict(writein, np=sum(np_wi) / len(np_wi) if np_wi else 0.006)

    # --------------------------------------------------------------- scoring: partisan, cross-fitted by year
    report = {"scheme": scheme, "scheme_table": scheme_table, "minor_n": minor_n, "office_sd": [office_sd, office_n, office_mean],
              "senate_sd": [senate_sd, senate_n, senate_mean],
              "incumbency_sources": {str(k): v for k, v in inc_notes.items()}, "fit_all": fit_all,
              "fit_by_year": {str(k): v for k, v in fit_by.items()}, "np_fit": np_fit, "np_fit_silent": np_fit_silent,
              "anchors": {str(Y): {"top": F.TOP_OF_TICKET[Y], "actual": ctx[Y]["G"], "pre": F.expit(pre_environment(base["state"], Y))}
                          for Y in YEARS}}
    rows_store, meas_store = [], []
    base_np = {"np": {"beta_inc": np_fit["beta_inc"], "tau": np_fit["tau"]}}

    def partisan_scores(Y, scenario, widen, n_draws=draws):
        other = [y for y in YEARS if y != Y][0]
        fit = fit_by[other]
        prm = params_from(fit, scheme, minor, writein, office_sd, base_np["np"], widen=widen, senate_sd=senate_sd)
        frame = partisan_frame(base, Y, races[Y], prm, scenario, ctx[Y])
        out = F.simulate(frame, R.seed_of(f"backtest-{Y}-{scenario}"), n_draws)
        actual = {}
        for r in races[Y]:
            T = r["T"] or 1
            win = max([("D", r["D"]), ("R", r["R"])] + list(r["minors"].items()), key=lambda kv: kv[1])[0]
            a = {"D": (r["D"] / T, 1 if win == "D" else 0), "R": (r["R"] / T, 1 if win == "R" else 0)}
            for code, v in r["minors"].items():
                a[code] = (v / T, 1 if win == code else 0)
            actual[r["id"]] = a
        return score_rows(out, actual), out

    widen = {}
    for scenario in ("oracle", "pre"):
        def cover(fct, scenario=scenario):
            rows = []
            for Y in YEARS:
                rs, _ = partisan_scores(Y, scenario, fct, n_draws=min(draws, 400))
                rows += [r for r in rs if r[1] in ("D", "R") and not r[0].split("-")[1] in F.STATEWIDE_OFFICES + ("usprs",)]
            return sum(1 for r in rows if r[4] <= r[8] <= r[5]) / len(rows) if rows else 1.0
        if scenario == "oracle":
            widen["partisan"], c_at = widen_factor(cover)
            say(f"    district spreads widened by {widen['partisan']} so that 80 percent ranges hold {c_at:.0%} (oracle, cross-fitted)")
        for Y in YEARS:
            rs, _out = partisan_scores(Y, scenario, widen["partisan"])
            inc_pick, last_pick = {}, {}
            for r in races[Y]:
                if r.get("inc_known") and r.get("inc_dir"):
                    inc_pick[r["id"]] = "D" if r["inc_dir"] > 0 else "R"
                lt = last_time(base, r, Y)
                if lt:
                    last_pick[r["id"]] = lt
            for row in rs:
                cls = row[0].split("-")[1]
                grp = "statewide" if cls in F.STATEWIDE_OFFICES + ("usprs",) else cls
                rows_store.append((scenario, Y, row[0], grp, row[1], *row[2:8], row[8], row[9],
                                   (0.99 if inc_pick.get(row[0]) == row[1] else 0.01) if row[0] in inc_pick else None,
                                   (0.99 if last_pick.get(row[0]) == row[1] else 0.01) if row[0] in last_pick else None))
            for grp in sorted({"statewide" if r[0].split("-")[1] in F.STATEWIDE_OFFICES + ("usprs",) else r[0].split("-")[1] for r in rs}) + ["all"]:
                sel = [r for r in rs if grp == "all" or ("statewide" if r[0].split("-")[1] in F.STATEWIDE_OFFICES + ("usprs",) else r[0].split("-")[1]) == grp]
                m = measures(sel, inc_pick, last_pick)
                for k, v in m.items():
                    meas_store.append((f"{scenario}", f"partisan {grp} {Y}", k, v))
            say(f"    {scenario} {Y}: " + "; ".join(
                f"{g} " + (lambda m: f"{m.get('races', 0)} races, favourite won {m.get('favourite_won', 0):.0%}, Brier {m.get('brier', 0):.3f}, "
                           f"80% held {m.get('cover80', 0):.0%}, 95% {m.get('cover95', 0):.0%}, miss {m.get('mae_share', 0) * 100:.1f} pts")(
                    measures([r for r in rs if ("statewide" if r[0].split('-')[1] in F.STATEWIDE_OFFICES + ('usprs',) else r[0].split('-')[1]) == g]))
                for g in ("statewide", "usrep", "mnsen", "mnleg") if any(
                    ("statewide" if r[0].split('-')[1] in F.STATEWIDE_OFFICES + ('usprs',) else r[0].split('-')[1]) == g for r in rs)))

    # --------------------------------------------------------------- scoring: nonpartisan, five folds
    rng = random.Random(20261010)
    keys = sorted((rec["rid"], rec) for rec in contested)
    order = list(range(len(keys)))
    rng.shuffle(order)
    folds = [order[k::5] for k in range(5)]

    def np_rows(widen_np, n_draws=draws, df=None):
        allrows = []
        for k in range(5):
            test = {keys[i][0]: keys[i][1] for i in folds[k]}
            train = [keys[i][1] for j in range(5) if j != k for i in folds[j] if keys[i][1]["inc_known"]]
            fit = fit_np(train)
            prm = dict(F.DEFAULT_PARAMS, writein=writein, np={"beta_inc": fit["beta_inc"], "df": df,
                                                              "tau": {g: t * widen_np for g, t in fit["tau"].items()}})
            frame = np_frame({rid: rec for rid, rec in test.items()}, prm, base)
            out = F.simulate(frame, R.seed_of(f"backtest-np-{k}"), n_draws)
            actual = {}
            for rid, rec in test.items():
                names = sorted(n for n, v in rec["cands"].items() if v > 0)
                T = rec["wi"] + sum(rec["cands"].values())
                win = max(names, key=lambda n: rec["cands"][n])
                actual[rid] = {f"c{j}": (rec["cands"][n] / T, 1 if n == win else 0) for j, n in enumerate(names)}
            for row in score_rows(out, actual):
                rec = test[row[0]]
                names = sorted(n for n, v in rec["cands"].items() if v > 0)
                name = names[int(row[1][1:])]
                allrows.append((row, rec, name))
        return allrows

    # the shape of the tails: Gaussian, or Student's t at a few degrees of freedom; for each, the spread widened until
    # 80 percent ranges hold, then the shape whose 80 and 95 percent ranges come nearest their names (log loss to break ties)
    tails = []
    for df in NP_TAILS:
        def np_cover(f, df=df):
            rows = np_rows(f, n_draws=min(draws, 400), df=df)
            return sum(1 for r, _rec, _n in rows if r[4] <= r[8] <= r[5]) / len(rows)
        w, _c = widen_factor(np_cover)
        m = measures([r for r, _rec, _n in np_rows(w, n_draws=min(draws, 400), df=df)])
        tails.append((abs(m["cover80"] - 0.80) + abs(m["cover95"] - 0.95), m["logloss"], df, w, m))
        say(f"      tails {'Gaussian' if df is None else f't({df})'}: widened {w}, 80% held {m['cover80']:.1%}, 95% held {m['cover95']:.1%}, "
            f"log loss {m['logloss']:.4f}, Brier {m['brier']:.4f}")
    tails.sort(key=lambda t: (round(t[0], 3), t[1]))
    _gap, _ll, np_df, widen["nonpartisan"], _m = tails[0]
    report["np_tails"] = [[t[2], t[3], round(t[4]["cover80"], 4), round(t[4]["cover95"], 4), round(t[1], 4)] for t in tails]
    say(f"    nonpartisan errors: {'Gaussian' if np_df is None else f'Student t, {np_df} degrees of freedom'}, spreads widened by "
        f"{widen['nonpartisan']} (five folds)")
    allrows = np_rows(widen["nonpartisan"], df=np_df)
    inc_pick = {}
    for row, rec, name in allrows:
        if rec["inc_known"] and rec["inc"].get(name):
            inc_pick[row[0]] = row[1]
    for row, rec, name in allrows:
        grp = rec["group"] + ("" if rec["inc_known"] else " (no holder on record)")
        rows_store.append(("pre", rec["year"], row[0], grp, row[1], *row[2:8], row[8], row[9],
                           (0.99 if inc_pick.get(row[0]) == row[1] else 0.01) if row[0] in inc_pick else None, None))
    groups = sorted({rec["group"] + ("" if rec["inc_known"] else " (no holder on record)") for _r, rec, _n in allrows})
    for grp in groups + ["all"]:
        sel = [r for r, rec, _n in allrows if grp == "all" or rec["group"] + ("" if rec["inc_known"] else " (no holder on record)") == grp]
        m = measures(sel, inc_pick)
        for k, v in m.items():
            meas_store.append(("pre", f"nonpartisan {grp}", k, v))
        say(f"    nonpartisan {grp}: {m.get('races')} races, favourite won {m.get('favourite_won', 0):.0%}, Brier {m.get('brier', 0):.3f}, "
            f"80% held {m.get('cover80', 0):.0%}, 95% held {m.get('cover95', 0):.0%}, miss {m.get('mae_share', 0) * 100:.1f} pts"
            + (f"; incumbent-wins rule right {m['incumbent_wins_right']:.0%} of {m['incumbent_wins_races']} (model Brier "
               f"{m['model_brier_on_incumbent_wins_races']:.3f} vs rule {m['incumbent_wins_brier']:.3f})" if "incumbent_wins_right" in m else ""))

    # --------------------------------------------------------------- the parameters for 2026
    np_final = {"beta_inc": np_fit["beta_inc"], "df": np_df, "tau": {g: t * widen["nonpartisan"] for g, t in np_fit["tau"].items()}}
    params = params_from(fit_all, scheme, minor, writein, office_sd, np_final, widen=widen["partisan"], senate_sd=senate_sd)
    params["widen_np"] = widen["nonpartisan"]
    report["widen"] = widen
    rep_out = None
    if replays:
        rep_out = run_replays(base, races, ctx, params, say, draws=min(draws, 500))
        for scen, grp, k, v in rep_out["measures"]:
            meas_store.append((scen, grp, k, v))
        report["replays"] = rep_out["summary"]
    report["position"] = position_stability()
    say(f"    ballot position: {report['position']['finding'][:160]}...")
    report["rolloff"] = rolloff_summary(base)
    say("    roll-off (share of voters who skip the race, middle 80 percent of precincts): " + "; ".join(
        f"{k} {v['median']:.0%} ({v['p10']:.0%}-{v['p90']:.0%})" for k, v in report["rolloff"].items()))
    # what the page must say about what was never tested
    report["untested"] = ["city, school, township, hospital and other local races: no past results on file (the Secretary's "
                          "files for them are John's to save)", "Minnesota's own polls: the kit holds no polls of 2022 or 2024",
                          "the first line's edge: no file says which name each precinct printed first"]
    report["seconds"] = round(time.time() - t0, 1)
    doc = {"params": params, "report": report}
    if not store:
        return doc
    con = R.connect(db)
    try:
        run_id = R.new_run_id(con, "backtest", "MN", started)
        with con:
            sha = R.put_blob(con, doc, "backtest")
            con.execute("INSERT INTO runs (run, state, kind, method, code_sha, seed, draws, started, ended, as_of, rehearsal, frame_sha, "
                        "python, races, written, note) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (run_id, "MN", "backtest", METHOD, R.keep_code(con, "backtest"), R.seed_of(run_id), draws, R.iso(started), None,
                         R.iso(started), 0, sha, __import__("platform").python_version(), len({r[2] for r in rows_store}), 0,
                         "backtests on 2022 and 2024, and the parameters the forecasts are sized by"))
            con.executemany("INSERT OR REPLACE INTO run_inputs (run, input, source, sha256, as_of, kind, note) VALUES (?,?,?,?,?,?,?)",
                            [(run_id, "features", f"election_model_2026.sqlite features (data build {base['build']})", None, None, "derived",
                              "precinct figures on today's lines"),
                             (run_id, "commons-tables", "election_cache/model/mn/commons/precinct_<year>.json", None, None, "official",
                              "the Secretary of State's certified precinct tables, 2012-2024"),
                             (run_id, "medsl", "election_cache/model/mn/medsl/medsl_<year>_mn.json", None, None, "secondary",
                              "MEDSL's copies of the Secretary's files, 2018, 2022, 2024 (CC0)"),
                             (run_id, "clerk", "Clerk of the House statistics 2020-2024", None, None, "official", "U.S. House holders"),
                             (run_id, "frame", f"run_blobs:{sha}", sha, R.iso(started), "frame", "the fitted parameters and the report")])
            con.executemany("INSERT OR REPLACE INTO backtests (run, scenario, year, race, grp, choice, chance, median, lo80, hi80, lo95, hi95, "
                            "actual, won, base_inc, base_last) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                            [(run_id, *r) for r in rows_store])
            con.executemany("INSERT OR REPLACE INTO calibration (run, scenario, grp, measure, value, n, note) VALUES (?,?,?,?,?,?,?)",
                            [(run_id, scen, grp, k, (v if not isinstance(v, list) else v[1]), (None if not isinstance(v, list) else v[2]),
                              (None if not isinstance(v, list) else f"predicted {v[0]}, observed {v[1]}"))
                             for scen, grp, k, v in meas_store])
            con.execute("UPDATE runs SET ended = ?, written = ? WHERE run = ?", (R.iso(R.now_utc()), len(rows_store), run_id))
        say(f"    backtest run {run_id} stored: {len(rows_store)} scored candidacies, {len(meas_store)} measures, "
            f"{time.time() - t0:.0f} s in all")
        doc["run"] = run_id
        return doc
    finally:
        con.close()


def rolloff_summary(base):
    """The roll-off blind spot, measured: the share of voters who skip each kind of race (1 minus the race's votes over
    the ballots that could vote in it), as the median precinct and the 10th and 90th percentiles. Partisan offices from
    the Secretary's precinct tables; nonpartisan kinds from MEDSL's 2022 copy (secondary)."""
    out = {}
    names = {"Governor 2022": "rolloff_mngov_2022", "Attorney General 2022": "rolloff_mnag_2022", "U.S. House 2022": "rolloff_usrep_2022",
             "State Senate 2022": "rolloff_mnsen_2022", "State House 2022": "rolloff_mnleg_2022", "U.S. Senate 2024": "rolloff_ussen_2024",
             "State House 2024": "rolloff_mnleg_2024"}
    for label, name in names.items():
        xs = sorted(x for x in col(base, name) if x is not None)
        if xs:
            q = F.quantiles(xs, (0.1, 0.5, 0.9))
            out[label] = {"p10": round(q[0], 4), "median": round(q[1], 4), "p90": round(q[2], 4), "precincts": len(xs), "source": "official"}
    try:
        np_ro = F.np_rolloff(base["ids"])
        for g, label in (("county", "County offices 2022"), ("county_commissioner", "County commissioner 2022"),
                         ("soil_water", "Soil and water 2022"), ("judicial", "Judges 2022")):
            xs = sorted(x for x in np_ro.get(g, []) if x is not None)
            if xs:
                q = F.quantiles(xs, (0.1, 0.5, 0.9))
                out[label] = {"p10": round(q[0], 4), "median": round(q[1], 4), "p90": round(q[2], 4), "precincts": len(xs),
                              "source": "secondary (MEDSL)"}
    except Exception as e:  # noqa: BLE001  the nonpartisan figures are a second source; their absence is said
        out["nonpartisan"] = {"p10": None, "median": None, "p90": None, "precincts": 0, "source": f"not read ({e.__class__.__name__})"}
    return {k: v for k, v in out.items() if v.get("median") is not None}


def last_time(base, r, year):
    """The party that won the same office in the same district the last time, on today's lines (two years before for the
    state House and the U.S. House; four for the state Senate), or None."""
    if r["statewide"]:
        return None
    cls = r["class"]
    prev = year - (4 if cls == "mnsen" else 2)
    s = col(base, f"dfl2p_contested_{cls}_{prev}")
    b = col(base, f"ballots_{prev}")
    num = den = 0.0
    for i, w in r["members"]:
        if s[i] is None or not b[i]:
            continue
        num += w * b[i] * s[i]
        den += w * b[i]
    if den <= 0:
        return None
    return "D" if num / den > 0.5 else "R"


# ============================================================================================== replays: the count-order blind spot

def lines_votes(year, base):
    """A year's precinct results carried onto today's lines (data_mn.on_today_lines), the columns the replays need."""
    path = os.path.join(cache_dir("mn", "forecast"), f"lines_votes_{year}.json")
    doc = data_mn.table(year)
    stamp = [doc["sha256"], data_mn.LINES_METHOD, len(base["ids"])]
    if os.path.exists(path):
        d = load_json(path)
        if d.get("stamp") == stamp:
            return d["lines"]
    pop = {v: (base["feats"]["pop2020"].get(v) or 0) for v in base["ids"]}
    cols = [c for c in doc["fields"] if c in ("totvoting", "ab_mb", "reg7am", "edr") or
            (c.startswith(("usprs", "ussen", "usrep", "mngov", "mnsos", "mnag", "mnaud", "mnsen", "mnleg")) and not c.endswith("est")
             and c not in data_mn.PLACE and c not in data_mn.STATS)]
    lines, _how, _rep = data_mn.on_today_lines(year, pop, doc, columns=cols)
    lines = {v: {k: round(x, 4) for k, x in rec.items()} for v, rec in lines.items()}
    save_json(path, {"stamp": stamp, "lines": lines})
    return lines


def reveal_order(base, lines, order, rng):
    """Precinct indexes in the order they report. random; small-first (fewest ballots first, so rural precincts lead);
    metro-last (whole counties at a time, outstate counties first in random order, then the seven metro counties, the
    largest last); late-batch (random, and every county's late absentee batch held back to the end)."""
    ids = base["ids"]
    have = [i for i, v in enumerate(ids) if v in lines and lines[v].get("totvoting", 0) > 0]
    if order in ("random", "late-batch"):
        rng.shuffle(have)
        return have
    if order == "small-first":
        return sorted(have, key=lambda i: (lines[ids[i]]["totvoting"], ids[i]))
    by_c = defaultdict(list)
    for i in have:
        by_c[base["counties"][i]].append(i)
    outstate = [c for c in by_c if c not in METRO_LAST]
    rng.shuffle(outstate)
    seq = []
    for c in outstate + [c for c in reversed(METRO_LAST) if c in by_c]:
        ps = by_c[c]
        rng.shuffle(ps)
        seq += ps
    return seq


def reference_night(prior, reported, shrink=200.0):
    """The reference night model: each race's forecast (two-party, log-odds, by precinct) moved by the reported precincts'
    swing against it, by county where a county has reported and statewide otherwise, shrunk toward no swing while few
    votes are in (shrink: the votes at which a county's own swing counts half). Returns {race: (mean two-party share
    of the whole race, sd)}.
    prior: {race: {"members": [(i, w)], "pred": {i: (two-party share, expected two-party votes)}, "sd": float}}
    reported: {i: {race: (dfl, rep)}} and the county of each precinct in prior["_county"]."""
    county = prior["_county"]
    out = {}
    for race, pr in prior.items():
        if race.startswith("_"):
            continue
        sw_num = sw_den = 0.0
        by_c = defaultdict(lambda: [0.0, 0.0])
        counted_d = counted_v = 0.0
        for i, w in pr["members"]:
            got = reported.get(i, {}).get(race)
            if not got:
                continue
            d, r = got
            v = d + r
            if v <= 0:
                continue
            p0 = pr["pred"][i][0]
            sw = F.logit(F.clamp(d / v, 0.01, 0.99)) - F.logit(F.clamp(p0, 0.01, 0.99))
            sw_num += sw * v
            sw_den += v
            by_c[county[i]][0] += sw * v
            by_c[county[i]][1] += v
            counted_d += w * d
            counted_v += w * v
        state_sw = sw_num / (sw_den + shrink * 5) if sw_den else 0.0
        rem_d = rem_v = 0.0
        unc = 0.0
        for i, w in pr["members"]:
            if reported.get(i, {}).get(race):
                continue
            p0, ev = pr["pred"][i]
            c = by_c.get(county[i])
            sw = state_sw
            if c and c[1] > 0:
                sw = state_sw + (c[0] / c[1] - state_sw) * (c[1] / (c[1] + shrink))
            rem_d += w * ev * F.expit(F.logit(F.clamp(p0, 0.01, 0.99)) + sw)
            rem_v += w * ev
        tot_v = counted_v + rem_v
        share = (counted_d + rem_d) / tot_v if tot_v > 0 else 0.5
        frac_left = rem_v / tot_v if tot_v > 0 else 0.0
        sd = pr["sd"] * frac_left + 0.002
        out[race] = (share, sd, 1 - frac_left)
    return out


def position_stability(year=2024, noises=(0.02, 0.05, 0.10), seed=11):
    """The ballot-position blind spot, measured: how much of the rebuilt rotation (Minn. R. 8220.0825, state House
    districts of `year`, two names) survives when the registration counts it is dealt by are off by a few percent (the
    May 1 count is not on file; the Election Day count stands in). Agreement of 0.5 is chance. Returns a summary."""
    doc = data_mn.table(year)
    by = defaultdict(list)
    for r in doc["rows"]:
        by[data_mn._dist(r.get("mnlegdist"))].append((r["vtdid"], r.get("reg7am") or 0))
    rng = random.Random(seed)
    out = {"districts": len(by), "precincts_per_district": round(sum(len(v) for v in by.values()) / max(len(by), 1), 1)}
    for noise in noises:
        ag = []
        for d, regs in sorted(by.items()):
            base_rot, _ = F.rotation_subtotals(regs, 2)
            rot2, _ = F.rotation_subtotals([(v, x * (1 + rng.gauss(0, noise))) for v, x in regs], 2)
            same = sum(1 for a, b in zip(base_rot, rot2) if a == b) / len(regs)
            ag.append(max(same, 1 - same))
        out[f"agreement_at_{int(noise * 100)}pct"] = round(sum(ag) / len(ag), 3)
    ags = [out[f"agreement_at_{int(n * 100)}pct"] for n in noises]
    out["finding"] = ("Dealt from counts that are off by a few percent, the rebuilt order agrees with itself in only "
                      f"{min(ags):.0%} to {max(ags):.0%} of precincts (half would be chance), so no precinct's printed order can be "
                      "learned from the rebuild, and "
                      "Minnesota's own first-line edge cannot be measured from it. What the forecast uses is each name's share "
                      "of voters who see it first, which the rule keeps near equal in any race with many precincts whatever the "
                      "counts; the edge's size stays a prior until each precinct's printed order is on file (the counties' "
                      "rotation reports, or the results files' candidate order column if it proves to be the printed position).")
    return out


def run_replays(base, races, ctx, params, say=say_default, draws=500):
    """Replays of 2022 and 2024 on today's lines in the four orders, scored at each checkpoint (ARCHITECTURE.md 4.1)."""
    measures_out, summary = [], {}
    zs = defaultdict(list)                     # (order, checkpoint) -> each race's standardised miss, for the spread's calibration
    for Y in YEARS:
        lines = lines_votes(Y, base)
        L = ctx[Y]["L"]
        dist = [r for r in races[Y] if not r["statewide"] and r.get("contested")]
        stw = [r for r in races[Y] if r["statewide"]]
        # the forecast as it stood before the vote (no polls on file for past years): the environment from the last
        # presidential result and Minnesota's midterm pattern, never the year's actual statewide result
        env_sd = F.PRIORS["env_no_polls_sd"]
        mu = F.inverse(ctx[Y]["sg"], F.expit(pre_environment(base["state"], Y)))
        prior = {"_county": base["counties"]}
        truth = {}
        prev = Y - 4
        b = col(base, f"ballots_{prev}")
        for r in dist + stw:
            cls = r["class"]
            members = r["members"] if not r["statewide"] else base["index"]["state:MN"]
            ro = col(base, f"rolloff_{cls}_{prev}") if not r["statewide"] else col(base, f"rolloff_{F.TOP_OF_TICKET[prev]}_{prev}")
            gap = 0.0 if r["statewide"] else params["gap"][cls][0]
            inc = 0.0 if r["statewide"] else params["inc"][0] * r.get("inc_dir", 0)
            pred = {}
            for i, _w in members:
                ev = max(b[i] or 0, 0) * (1 - (ro[i] or 0.05))
                pred[i] = (F.expit(mu + L[i] + gap + inc), ev)
            sd = math.sqrt((params["district_sd"].get(cls, 0.14) ** 2 if not r["statewide"] else
                            (0.0 if cls == F.TOP_OF_TICKET[Y] else params["office_sd"] ** 2)) + env_sd ** 2)
            prior[r["id"]] = {"members": members, "pred": pred, "sd": sd * 0.25}
            truth[r["id"]] = r["D"] / (r["D"] + r["R"]) if (r["D"] + r["R"]) else None
        # precinct results by race on today's lines (two-party)
        res_by_i = defaultdict(dict)
        for r in dist + stw:
            cls = r["class"]
            for i, _w in (r["members"] if not r["statewide"] else base["index"]["state:MN"]):
                rec = lines.get(base["ids"][i])
                if not rec:
                    continue
                d, rr = rec.get(f"{cls}dfl", 0) or 0, rec.get(f"{cls}r", 0) or 0
                if d + rr > 0:
                    res_by_i[i][r["id"]] = (d, rr)
        total_ballots = sum((lines.get(v) or {}).get("totvoting", 0) for v in base["ids"])
        for order in ORDERS:
            rng = random.Random(f"replay-{Y}-{order}")
            seq = reveal_order(base, lines, order, rng)
            late = {}
            if order == "late-batch":
                # each county's late absentee batch: a share of its absentee and mail ballots, assumed to lean 5 points
                # either way of the county (unknown in advance; drawn once per county)
                for c in set(base["counties"]):
                    late[c] = (0.06, rng.gauss(0, F.logit(0.55)))
            reported, counted = {}, 0.0
            k = 0
            for cp in CHECKPOINTS:
                while k < len(seq) and counted / total_ballots < cp:
                    i = seq[k]
                    k += 1
                    got = dict(res_by_i.get(i, {}))
                    cut = 0.0
                    if late:
                        frac, lean = late[base["counties"][i]]
                        ab = (lines[base["ids"][i]].get("ab_mb", 0) or 0) / max(lines[base["ids"][i]]["totvoting"], 1)
                        cut = frac * ab
                        for rid, (d, rr) in got.items():
                            v = (d + rr) * cut
                            p = F.clamp(F.expit(F.logit(F.clamp(d / (d + rr), 0.01, 0.99)) + lean), 0.0, 1.0)
                            got[rid] = (max(d - v * p, 0.0), max(rr - v * (1 - p), 0.0))
                    reported[i] = got
                    counted += lines[base["ids"][i]].get("totvoting", 0) * (1 - cut)
                est = reference_night(prior, reported)
                rows = []
                for rid, (share, sd, frac) in est.items():
                    t = truth.get(rid)
                    if t is None:
                        continue
                    sdw = max(sd, 1e-4)
                    z = (t - share) / sdw
                    p_d = 0.5 * (1 + math.erf((share - 0.5) / (sdw * math.sqrt(2))))
                    won = 1 if t > 0.5 else 0
                    rows.append((rid, z, p_d, won, abs(t - share)))
                if not rows:
                    continue
                zs[(order, int(cp * 100))] += [r[1] for r in rows]
                c80 = sum(1 for r in rows if abs(r[1]) <= 1.2816) / len(rows)
                brier = sum((r[2] - r[3]) ** 2 for r in rows) / len(rows)
                miss = sum(r[4] for r in rows) / len(rows)
                wrong = sum(1 for r in rows if (r[2] > 0.5) != bool(r[3])) / len(rows)
                grp = f"replay {Y} {order} {int(cp * 100)}%"
                for name, v in (("cover80", c80), ("brier_two_party", brier), ("mae_two_party", miss), ("leader_wrong", wrong),
                                ("races", len(rows))):
                    measures_out.append((f"replay:{order}:{int(cp * 100)}", f"reference night model {Y}", name, v))
                summary[grp] = {"cover80": round(c80, 3), "brier": round(brier, 4), "miss_pts": round(miss * 100, 2),
                                "leader_wrong": round(wrong, 3), "races": len(rows)}
            say(f"    replay {Y} {order}: " + ", ".join(f"{int(cp * 100)}%: held {summary[f'replay {Y} {order} {int(cp * 100)}%']['cover80']:.0%}, "
                                                      f"miss {summary[f'replay {Y} {order} {int(cp * 100)}%']['miss_pts']:.1f}, "
                                                      f"leader wrong {summary[f'replay {Y} {order} {int(cp * 100)}%']['leader_wrong']:.0%}"
                                                      for cp in CHECKPOINTS if f"replay {Y} {order} {int(cp * 100)}%" in summary))
    # the night spread's calibration: the smallest scale on the reference model's spread at which the 80 percent ranges
    # hold at least 78 percent of results at every checkpoint in every order (ARCHITECTURE.md 4.1: "in every order")
    scales = [round(0.1 * k, 1) for k in range(1, 21)]
    table = {}
    best = None
    for s in scales:
        worst = min(sum(1 for z in v if abs(z) <= 1.2816 * s) / len(v) for v in zs.values())
        table[s] = round(worst, 3)
        if best is None and worst >= 0.78:
            best = s
    summary["night_scale"] = {"scale": best, "worst_cover80_by_scale": table,
                              "by_order_at_scale": {f"{o} {c}%": round(sum(1 for z in v if abs(z) <= 1.2816 * (best or 1)) / len(v), 3)
                                                    for (o, c), v in sorted(zs.items())},
                              "what": "the reference night model's spread times this scale holds 80 percent ranges about 80 percent "
                                      "of the time in every counting order; the night's own model can start from it"}
    say(f"    the night spread: scale {best} holds 80% ranges at least 78% of the time in every order and checkpoint "
        f"(worst at scale 1.0: {table.get(1.0)})")
    return {"measures": measures_out, "summary": summary}


# ============================================================================================== self-test

def selftest(say=say_default):
    ok = True

    def check(what, got, want):
        nonlocal ok
        good = (abs(got - want) < 1e-9) if isinstance(want, float) else got == want
        ok &= good
        say(f"    {'ok ' if good else 'BAD'} {what}: {got!r}" + ("" if good else f" (expected {want!r})"))
    check("court key 2018", _court_key(2018, "DISTRICT COURT JUDGE", "001, COURT 10"), ("district_court", 1, 10))
    check("court key 2022", _court_key(2022, "JUDGE - 9TH DISTRICT COURT 6", "009"), ("district_court", 9, 6))
    check("court key 2024", _court_key(2024, "DISTRICT COURT 10 JUDGE", "009"), ("district_court", 9, 10))
    check("appeals key 2022", _court_key(2022, "JUDGE - COURT OF APPEALS 10", ""), ("court_of_appeals", 10))
    check("supreme court key 2024", _court_key(2024, "ASSOCIATE JUSTICE - SUPREME COURT", "005"), ("supreme_court", 5))
    races = [{"group": "county", "cands": {"A": 600, "B": 400}, "inc": {"A": 1, "B": 0}},
             {"group": "county", "cands": {"C": 500, "D": 500}, "inc": {"C": 0, "D": 0}},
             {"group": "county", "cands": {"E": 300, "F": 700}, "inc": {"E": 0, "F": 1}}]
    fit = fit_np(races)
    check("the holder's edge in log-share", round(fit["beta_inc"][0], 6), round((math.log(1.5) + math.log(7 / 3)) / 2, 6))
    rows = [("r1", "D", 0.9, 0.55, 0.5, 0.6, 0.45, 0.65, 0.56, 1), ("r1", "R", 0.1, 0.45, 0.4, 0.5, 0.35, 0.55, 0.44, 0),
            ("r2", "D", 0.4, 0.48, 0.44, 0.52, 0.4, 0.56, 0.53, 1), ("r2", "R", 0.6, 0.52, 0.48, 0.56, 0.44, 0.6, 0.47, 0)]
    m = measures(rows)
    check("Brier over two races", round(m["brier"], 6), round(((0.1 ** 2 + 0.1 ** 2) + (0.6 ** 2 + 0.6 ** 2)) / 2, 6))
    check("favourite won one of two", m["favourite_won"], 0.5)
    check("80 percent ranges held", m["cover80"], 0.5)
    check("widen finds the first factor that holds", widen_factor(lambda f: 0.6 + 0.2 * (f - 1))[0], 2.0)
    state = {"dfl2p_usprs_2012": 0.54, "dfl2p_mngov_2014": 0.53, "dfl2p_usprs_2016": 0.51, "dfl2p_mngov_2018": 0.56, "dfl2p_usprs_2020": 0.536}
    g24 = pre_environment(state, 2024)
    check("2024's environment before the vote is 2020's presidential result", round(F.expit(g24), 6), 0.536)
    g22 = pre_environment(state, 2022)
    check("2022's environment before the vote is lower (a Democratic president's midterm)", g22 < F.logit(0.536), True)
    return ok


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--state", default="mn")
    ap.add_argument("--draws", type=int, default=DRAWS)
    ap.add_argument("--no-replays", action="store_true", help="skip the election-night replays")
    ap.add_argument("--no-store", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--db", default=DB)
    a = ap.parse_args(argv)
    if a.selftest:
        sys.exit(0 if selftest() else 1)
    if a.state.lower() != "mn":
        sys.exit("    only Minnesota is backtested here")
    run(db=a.db, draws=a.draws, replays=not a.no_replays, store=not a.no_store)


if __name__ == "__main__":
    main()
