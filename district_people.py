#!/usr/bin/env python3
"""
district_people.py
==================
The second "lens" on the district maps: who lives in each district, from the Census Bureau's own counts and
estimates, tabulated the same way for every district of the 119th Congress and of every state legislature. It
reports; it never says why a district holds the people it holds.

    python district_people.py                   # Congress and every state in states/places.py, in one run
    python district_people.py --state mn        # one state: state_mn_people.json and .csv
    python district_people.py --congress-only   # the 119th Congress: us_district_people.json and .csv
    python district_people.py --selftest        # checks the arithmetic against the Bureau's own worked examples

SOURCES (primary, official; files anyone can download without an account):
  1. 2020 Census counts, summed by the Bureau into the current districts: CD119_UR_POPAREA.txt (the 119th Congress),
     SLDU2024_UR_POPAREA.txt and SLDL2024_UR_POPAREA.txt (2024 state legislative districts): resident population as
     of April 1, 2020, land area, and how much of each is urban. www2.census.gov/geo/docs/maps-data/data/rel2020/cd-sld/
  2. American Community Survey 2020-2024 five-year estimates, table-based summary file: Geos20245YR.txt (which row is
     which district) and acsdt5y2024-<table>.dat for tables B01001 (age), B01002 (median age), B01003 (population),
     B03002 (Hispanic origin by race), B05002 (place of birth), B09001 (under 18, used as a check), B15003 (education),
     B17001 (poverty), B19013 (median household income), B25003 (owners and renters).
     www2.census.gov/programs-surveys/acs/summary_file/2024/table-based-SF/
  Every file's SHA-256 is written with the results, so anyone can confirm they read the same file.

MEASURES (each reproducible from the files alone):
  population 2020        the Bureau's count of residents in the district's blocks, the number the lines were drawn on
  people per seat        population / seats the district elects; the ideal is the state's population / the chamber's
                         seats; deviation = (people per seat - ideal) / ideal. A chamber's "spread" is the largest
                         deviation minus the smallest (the "overall range" of Brown v. Thomson, 462 U.S. 835 (1983);
                         congressional districts are held to near equality, Karcher v. Daggett, 462 U.S. 725 (1983)).
                         Where districts elect different numbers of members, the seat count comes from the roster and
                         the page says so; this program then leaves the deviation blank.
  density                population 2020 / land area (square miles), and the urban share of the population
  ACS estimates          median age; share under 18 and 65 or older; Hispanic or Latino, and by race for those who are
                         not: White alone, Black alone, Asian alone, American Indian and Alaska Native alone, Native
                         Hawaiian and Other Pacific Islander alone, some other race alone, two or more races; born
                         outside the United States; below the poverty line; bachelor's degree or higher (25 and over);
                         owner-occupied homes; median household income. Each carries the Bureau's margin of error.

MARGINS OF ERROR (90 percent, as the Bureau publishes them; standard error = MOE / 1.645):
  a sum                  MOE = sqrt(sum of the squared MOEs)                                              formula (1)
  a proportion p = a/b   MOE = sqrt(MOE_a^2 - p^2 * MOE_b^2) / b; if the root would be of a negative number, the ratio
                         form sqrt(MOE_a^2 + p^2 * MOE_b^2) / b                                        formulas (6), (7)
  U.S. Census Bureau, "Understanding and Using American Community Survey Data: What All Data Users Need to Know",
  September 2020, chapter 8, "Calculating Measures of Error for Derived Estimates". A controlled estimate (the
  Bureau's code -555555555) has no sampling error and counts as zero in these sums. The Bureau notes the approximation
  understates error when components are correlated; the self-test reproduces its worked examples.

CONTROLS (written to the results and printed by the run):
  a. The three 2020 tabulations (Congress, upper chamber, lower chamber) of the same blocks give the same state total,
     and that total equals the state's 2020 resident population in the apportionment tables.
  b. ACS district populations sum to the Bureau's own published state population (a controlled estimate), exactly.
  c. Under-18 derived from the age bands equals the Bureau's own table B09001 in every district.

LIMITS, stated on the page as well: ACS figures are five-year averages centred on 2022, with sampling error, not this
year's population; the 2020 count is what the lines were drawn on and is five years old; race and Hispanic origin are
self-reported in the Bureau's categories; a district's residents are not its voters (children, non-citizens and people
not registered are counted); a small district has wide margins; nothing here says who was placed where, or why.
"""

import argparse
import csv
import datetime as dt
import hashlib
import json
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
METHOD_VERSION = "people-1.0"
ACS_DIR = os.path.join(HERE, "states_cache", "acs2024")
REL_DIR = os.path.join(HERE, "states_cache", "census_rel")
ACS_URL = "https://www2.census.gov/programs-surveys/acs/summary_file/2024/table-based-SF/"
REL_URL = "https://www2.census.gov/geo/docs/maps-data/data/rel2020/cd-sld/"
TABLES = ("b01001", "b01002", "b01003", "b03002", "b05002", "b09001", "b15003", "b17001", "b19013", "b25003")
CONTROLLED = -555555555
MISSING = {-666666666, -999999999, -888888888, -222222222, -333333333}

FIPS = {"01": "AL", "02": "AK", "04": "AZ", "05": "AR", "06": "CA", "08": "CO", "09": "CT", "10": "DE", "11": "DC", "12": "FL",
        "13": "GA", "15": "HI", "16": "ID", "17": "IL", "18": "IN", "19": "IA", "20": "KS", "21": "KY", "22": "LA", "23": "ME",
        "24": "MD", "25": "MA", "26": "MI", "27": "MN", "28": "MS", "29": "MO", "30": "MT", "31": "NE", "32": "NV", "33": "NH",
        "34": "NJ", "35": "NM", "36": "NY", "37": "NC", "38": "ND", "39": "OH", "40": "OK", "41": "OR", "42": "PA", "44": "RI",
        "45": "SC", "46": "SD", "47": "TN", "48": "TX", "49": "UT", "50": "VT", "51": "VA", "53": "WA", "54": "WV", "55": "WI", "56": "WY"}

# 2020 resident population, U.S. Census Bureau, "Apportionment Population and Number of Representatives by State: 2020
# Census" (Table 1, April 26, 2021) and the resident population in Table 2. Known answers for the self-test and control a.
RESIDENT_2020 = {"MN": 5706494, "CA": 39538223, "TX": 29145505, "WY": 576851, "AK": 733391, "VT": 643077, "NY": 20201249}

# Which columns of each table this lens reads, and the label the table shell must carry for that column: the run
# checks the shell before it trusts a column number.
COLS = {
    "b01003": {"pop": ("001", "Total")},
    "b01002": {"median_age": ("001", "Total")},
    "b09001": {"under18_published": ("001", "Total")},
    "b19013": {"income": ("001", "Median household income")},
    "b17001": {"poverty_universe": ("001", "Total"), "poverty": ("002", "Income in the past 12 months below poverty level")},
    "b05002": {"born_universe": ("001", "Total"), "foreign": ("013", "Foreign-born")},
    "b25003": {"households": ("001", "Total"), "owner": ("002", "Owner occupied")},
    "b15003": {"adults25": ("001", "Total"), "bachelors": ("022", "Bachelor's degree"), "masters": ("023", "Master's degree"),
               "professional": ("024", "Professional school degree"), "doctorate": ("025", "Doctorate degree")},
    "b03002": {"race_universe": ("001", "Total"), "white": ("003", "White alone"), "black": ("004", "Black or African American alone"),
               "aian": ("005", "American Indian and Alaska Native alone"), "asian": ("006", "Asian alone"),
               "nhpi": ("007", "Native Hawaiian and Other Pacific Islander alone"), "other": ("008", "Some other race alone"),
               "multi": ("009", "Two or more races"), "hispanic": ("012", "Hispanic or Latino")},
}
# B01001 (sex by age): the bands that make up "under 18" and "65 and over", male then female
AGE_UNDER18 = [f"{n:03d}" for n in (3, 4, 5, 6, 27, 28, 29, 30)]
AGE_65PLUS = [f"{n:03d}" for n in (20, 21, 22, 23, 24, 25, 44, 45, 46, 47, 48, 49)]
AGE_LABELS = {"003": "Under 5 years", "006": "15 to 17 years", "020": "65 and 66 years", "025": "85 years and over",
              "027": "Under 5 years", "030": "15 to 17 years", "044": "65 and 66 years", "049": "85 years and over"}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def moe_sum(moes):
    """Formula (1): the margin of a sum or difference of independent estimates."""
    return math.sqrt(sum(m * m for m in moes))


def moe_share(a, moe_a, b, moe_b):
    """Formulas (6) and (7): the margin of a proportion a/b, the numerator being part of the denominator."""
    if not b:
        return None, None
    p = a / b
    under = moe_a * moe_a - p * p * moe_b * moe_b
    if under < 0:
        under = moe_a * moe_a + p * p * moe_b * moe_b
    return p, math.sqrt(under) / b


def source_record(path, url_base):
    return {"publisher": "U.S. Census Bureau", "file": os.path.basename(path), "url": url_base + os.path.basename(path),
            "sha256": sha256(path), "bytes": os.path.getsize(path), "fetched": dt.date.fromtimestamp(os.path.getmtime(path)).isoformat()}


def need(path, hint):
    if not os.path.exists(path):
        sys.exit(f"{path} is not there. {hint}")
    return path


def fetch_all():
    """Every source file, into the caches, through states/net.py (polite and patient); nothing is fetched twice."""
    sys.path.insert(0, HERE)
    from states import net
    os.makedirs(ACS_DIR, exist_ok=True)
    os.makedirs(REL_DIR, exist_ok=True)
    for name in ("CD119_UR_POPAREA.txt", "SLDU2024_UR_POPAREA.txt", "SLDL2024_UR_POPAREA.txt"):
        if net.download(REL_URL + name, os.path.join(REL_DIR, name), 300):
            print(f"    fetched {name}")
    for name in ["documentation/Geos20245YR.txt", "documentation/ACS20245YR_Table_Shells.txt"] + [f"data/5YRData/acsdt5y2024-{t}.dat" for t in TABLES]:
        if net.download(ACS_URL + name, os.path.join(ACS_DIR, os.path.basename(name)), 1800):
            print(f"    fetched {os.path.basename(name)}")


# ---------------------------------------------------------------- the 2020 counts by district
def counts(name, code_len):
    """{(state fips, district code): (population, land square miles, urban percent)} from a UR_POPAREA file."""
    out = {}
    path = need(os.path.join(REL_DIR, name), "Run: python district_people.py --fetch")
    with open(path, encoding="utf-8") as fh:
        rdr = csv.DictReader(fh)
        for row in rdr:
            geoid = row[rdr.fieldnames[0]].strip()
            st, code = geoid[:2], geoid[2:]
            if code.upper().startswith("ZZ") or len(code) != code_len:
                continue
            pop = int(row[rdr.fieldnames[1]] or 0)
            out[(st, code)] = (pop, float(row["AREALAND_SQMI"] or 0), float(row["URBAN_BLK_POP_PCT"] or 0))
    return out


# ---------------------------------------------------------------- the ACS estimates by district
def geographies():
    """GEO_ID -> (summary level, state fips, district code, name) for the rows this lens uses."""
    path = need(os.path.join(ACS_DIR, "Geos20245YR.txt"), "Run: python district_people.py --fetch")
    out = {}
    with open(path, encoding="utf-8", errors="replace") as fh:
        cols = fh.readline().rstrip("\n").split("|")
        ix = {c: i for i, c in enumerate(cols)}
        for line in fh:
            p = line.rstrip("\n").split("|")
            sl = p[ix["SUMLEVEL"]]
            if sl not in ("040", "500", "610", "620") or p[ix["COMPONENT"]] != "00":
                continue
            code = {"040": "", "500": p[ix["CDCURR"]], "610": p[ix["SLDU"]], "620": p[ix["SLDL"]]}[sl]
            if code.upper().startswith("ZZ"):
                continue
            out[p[ix["GEO_ID"]]] = (sl, p[ix["STATE"]], code, p[ix["NAME"]])
    return out


def check_shells():
    """The table shells must say what this program assumes each column is; otherwise stop."""
    path = need(os.path.join(ACS_DIR, "ACS20245YR_Table_Shells.txt"), "Run: python district_people.py --fetch")
    labels = {}
    with open(path, encoding="utf-8", errors="replace") as fh:
        next(fh)
        for line in fh:
            p = line.rstrip("\n").split("|")
            if len(p) >= 5:
                labels[p[3]] = p[4].rstrip(":")
    bad = []
    for table, cols in COLS.items():
        for _, (col, want) in cols.items():
            got = labels.get(f"{table.upper()}_{col}", "")
            if not got.lower().startswith(want.lower()):
                bad.append((table, col, want, got))
    for col, want in AGE_LABELS.items():
        got = labels.get(f"B01001_{col}", "")
        if got != want:
            bad.append(("b01001", col, want, got))
    if bad:
        sys.exit("The table shells do not say what this program expects; nothing written. " + "; ".join(f"{t}_{c}: wanted '{w}', shell says '{g}'" for t, c, w, g in bad))
    return labels


def read_table(table, geo_ids):
    """{GEO_ID: {column: (estimate, moe or None, controlled?)}} for the rows in geo_ids."""
    path = need(os.path.join(ACS_DIR, f"acsdt5y2024-{table}.dat"), "Run: python district_people.py --fetch")
    out = {}
    with open(path, encoding="utf-8", errors="replace") as fh:
        head = fh.readline().rstrip("\n").split("|")
        est = {h.split("_E")[1]: i for i, h in enumerate(head) if "_E" in h}
        moe = {h.split("_M")[1]: i for i, h in enumerate(head) if "_M" in h}
        for line in fh:
            gid = line[:line.index("|")]
            if gid not in geo_ids:
                continue
            p = line.rstrip("\n").split("|")
            row = {}
            for col, i in est.items():
                e = p[i]
                if e in ("", ".") or (e.lstrip("-").isdigit() and int(e) in MISSING):
                    row[col] = (None, None, False)
                    continue
                e = float(e) if "." in e else int(e)
                m_raw = p[moe[col]] if col in moe else ""
                if m_raw in ("", "."):
                    row[col] = (e, None, False)
                else:
                    m = float(m_raw) if "." in m_raw else int(m_raw)
                    if m == CONTROLLED:
                        row[col] = (e, 0, True)
                    elif m < 0:
                        row[col] = (e, None, False)
                    else:
                        row[col] = (e, m, False)
            out[gid] = row
    return out


def acs_for(gid, T):
    """One district's (or state's) ACS figures: counts with margins, then shares with derived margins."""
    def em(table, col):
        r = T[table].get(gid, {}).get(col)
        return (r[0], r[1]) if r and r[0] is not None else (None, None)

    def summed(cols):
        vals = [T["b01001"].get(gid, {}).get(c) for c in cols]
        if any(v is None or v[0] is None for v in vals):
            return None, None
        return sum(v[0] for v in vals), round(moe_sum([v[1] or 0 for v in vals]), 1)

    c = {}
    c["pop"] = em("b01003", COLS["b01003"]["pop"][0])
    c["median_age"] = em("b01002", COLS["b01002"]["median_age"][0])
    c["income"] = em("b19013", COLS["b19013"]["income"][0])
    c["under18"] = summed(AGE_UNDER18)
    c["over65"] = summed(AGE_65PLUS)
    c["under18_published"] = em("b09001", "001")
    for table in ("b17001", "b05002", "b25003", "b15003", "b03002"):
        for k, (col, _) in COLS[table].items():
            c[k] = em(table, col)
    if c["bachelors"][0] is not None:
        parts = [c[k] for k in ("bachelors", "masters", "professional", "doctorate")]
        c["degree"] = (sum(p[0] for p in parts), round(moe_sum([p[1] or 0 for p in parts]), 1))
    else:
        c["degree"] = (None, None)
    shares = {}
    for k, base in (("under18", "pop"), ("over65", "pop"), ("hispanic", "race_universe"), ("white", "race_universe"), ("black", "race_universe"),
                    ("asian", "race_universe"), ("aian", "race_universe"), ("nhpi", "race_universe"), ("other", "race_universe"),
                    ("multi", "race_universe"), ("foreign", "born_universe"), ("poverty", "poverty_universe"), ("degree", "adults25"),
                    ("owner", "households")):
        a, ma = c.get(k, (None, None))
        b, mb = c.get(base, (None, None))
        if a is None or b is None or not b:
            shares[k] = None
            continue
        p, mp = moe_share(a, ma or 0, b, mb or 0)
        shares[k] = [round(p * 100, 2), round(mp * 100, 2)]
    counts_out = {k: [c[k][0], c[k][1]] for k in ("pop", "median_age", "income", "under18", "over65", "hispanic", "white", "black", "asian",
                                                  "aian", "nhpi", "other", "multi", "foreign", "poverty", "degree", "owner", "households",
                                                  "adults25", "poverty_universe", "born_universe", "race_universe") if c.get(k, (None,))[0] is not None}
    return counts_out, shares, c["under18_published"]


# ---------------------------------------------------------------- putting a chamber together
def seats_by_district(codes, seats):
    """How many members each district elects, when the file alone can say: the same number everywhere when the seat
    count divides evenly (one, or two in the Dakotas' Houses, Arizona's, Washington's), and where a few districts are
    split into lettered single-member pieces (North Dakota's 4A and 4B), the plain-numbered districts share the rest.
    Returns ({code: seats}, per_district or None); None where districts elect varying numbers (the roster knows)."""
    n = len(codes)
    if not seats or not n:
        return {}, None
    if seats % n == 0:
        return {c: seats // n for c in codes}, seats // n
    plain = [c for c in codes if c.isdigit()]
    if plain and len(plain) < n:
        per = round((seats - (n - len(plain))) / len(plain))
        if per >= 1 and per * len(plain) + (n - len(plain)) == seats:
            return {c: (per if c.isdigit() else 1) for c in codes}, per
    return {}, None


def chamber_rows(st, rows_2020, geo_rows, T, seats, key_of):
    """rows_2020: {code: (pop, land, urban)}; geo_rows: {code: (gid, name)}; seats: the chamber's seats (None if unknown)."""
    codes = sorted(set(rows_2020) | set(geo_rows), key=natural)
    total = sum(rows_2020[c][0] for c in codes if c in rows_2020)
    seats_of, per = seats_by_district(codes, seats)
    ideal = (total / seats) if seats else None
    rows, mismatched = [], []
    for code in codes:
        pop, land, urban = rows_2020.get(code, (None, None, None))
        gid, name = geo_rows.get(code, (None, ""))
        k = seats_of.get(code)
        r = {"key": key_of(code), "d": code, "name": name, "pop2020": pop, "land_sqmi": land, "urban_pct": urban,
             "density": round(pop / land, 1) if pop is not None and land else None, "seats": k,
             "dev_pct": round((pop / k - ideal) / ideal * 100, 2) if (pop is not None and k and ideal) else None}
        if gid:
            counts_out, shares, published = acs_for(gid, T)
            r["acs"], r["share"] = counts_out, shares
            if published[0] is not None and counts_out.get("under18") and counts_out["under18"][0] != published[0]:
                mismatched.append(code)
        rows.append(r)
    return rows, total, ideal, per, mismatched


def natural(d):
    m = re.match(r"^0*(\d+)(.*)$", str(d or ""))
    return (int(m.group(1)), m.group(2)) if m else (10 ** 9, str(d))


def summarize(rows, total, ideal, per, seats, mismatched, state_acs, resident):
    devs = [r["dev_pct"] for r in rows if r["dev_pct"] is not None]
    acs_pops = [r["acs"]["pop"] for r in rows if r.get("acs") and r["acs"].get("pop")]
    acs_sum = sum(p[0] for p in acs_pops)
    return ({"districts": len(rows), "pop2020_total": total, "seats": seats, "per_district": per, "ideal_per_seat": round(ideal, 1) if ideal else None,
             "dev": {"min": min(devs), "max": max(devs), "spread": round(max(devs) - min(devs), 2), "n": len(devs)} if devs else None,
             "why_no_dev": None if devs else ("seats per district vary, so the page reads them from the roster" if seats else "the chamber's seat count is not on file"),
             "acs_total": [acs_sum, round(moe_sum([p[1] or 0 for p in acs_pops]))] if acs_pops else None},
            {"count_vs_resident_2020": [total, resident] if resident else None, "count_matches_resident": (total == resident) if resident else None,
             "acs_sum_vs_state": [acs_sum, state_acs[0]] if state_acs and acs_pops else None,
             "acs_sum_matches_state": (acs_sum == state_acs[0]) if state_acs and acs_pops else None,
             "under18_mismatches": mismatched, "under18_checked": sum(1 for r in rows if r.get("acs") and r["acs"].get("under18"))})


CSV_HEAD = ["census_name", "population_2020", "land_sq_mi", "people_per_sq_mi", "urban_pct", "deviation_pct", "acs_population", "acs_population_moe",
            "median_age", "median_age_moe", "median_household_income", "median_household_income_moe",
            "under_18_pct", "under_18_pct_moe", "65_and_over_pct", "65_and_over_pct_moe", "hispanic_pct", "hispanic_pct_moe",
            "white_alone_not_hispanic_pct", "white_alone_not_hispanic_pct_moe", "black_alone_not_hispanic_pct", "black_alone_not_hispanic_pct_moe",
            "asian_alone_not_hispanic_pct", "asian_alone_not_hispanic_pct_moe", "aian_alone_not_hispanic_pct", "aian_alone_not_hispanic_pct_moe",
            "nhpi_alone_not_hispanic_pct", "nhpi_alone_not_hispanic_pct_moe", "other_race_not_hispanic_pct", "other_race_not_hispanic_pct_moe",
            "two_or_more_races_not_hispanic_pct", "two_or_more_races_not_hispanic_pct_moe", "foreign_born_pct", "foreign_born_pct_moe",
            "below_poverty_pct", "below_poverty_pct_moe", "bachelors_or_higher_pct", "bachelors_or_higher_pct_moe", "owner_occupied_pct", "owner_occupied_pct_moe"]


def csv_tail(r):
    a, s = r.get("acs") or {}, r.get("share") or {}
    pair = lambda k: (a.get(k) or [None, None])
    sh = lambda k: (s.get(k) or [None, None])
    return [r["name"], r["pop2020"], r["land_sqmi"], r["density"], r["urban_pct"], r["dev_pct"], *pair("pop"), *pair("median_age"), *pair("income"),
            *sh("under18"), *sh("over65"), *sh("hispanic"), *sh("white"), *sh("black"), *sh("asian"), *sh("aian"), *sh("nhpi"), *sh("other"),
            *sh("multi"), *sh("foreign"), *sh("poverty"), *sh("degree"), *sh("owner")]


def report(name, s, c):
    print(f"  {name}: {s['districts']} districts, {s['pop2020_total']:,} people in 2020"
          + (f"; {s['seats']} seats, ideal {s['ideal_per_seat']:,.0f} a seat" if s.get("seats") else ""))
    if s.get("dev"):
        print(f"  Deviation from the ideal: {s['dev']['min']:+.2f}% to {s['dev']['max']:+.2f}%, a spread of {s['dev']['spread']:.2f} points")
    elif s.get("why_no_dev"):
        print(f"  Deviation not computed: {s['why_no_dev']}")
    if c.get("count_vs_resident_2020"):
        a, b = c["count_vs_resident_2020"]
        print(f"  Control a: 2020 count {a:,} vs resident population {b:,}: {'agree' if a == b else 'DIFFER by ' + format(a - b, ',')}")
    if c.get("acs_sum_vs_state"):
        a, b = c["acs_sum_vs_state"]
        print(f"  Control b: ACS district populations sum to {a:,}; the Bureau's state figure is {b:,}: {'agree' if a == b else 'DIFFER by ' + format(a - b, ',')}")
    print(f"  Control c: under-18 from the age bands equals table B09001 in {c['under18_checked'] - len(c['under18_mismatches'])} of {c['under18_checked']} districts"
          + (f"; differs in {', '.join(c['under18_mismatches'][:6])}" if c["under18_mismatches"] else ""))


class Sources:
    def __init__(self):
        self.acs = [source_record(os.path.join(ACS_DIR, n), ACS_URL + ("documentation/" if n.endswith(".txt") else "data/5YRData/"))
                    for n in ["Geos20245YR.txt", "ACS20245YR_Table_Shells.txt"] + [f"acsdt5y2024-{t}.dat" for t in TABLES]]
        for s in self.acs:
            s["product"] = "American Community Survey 2020-2024 five-year estimates, table-based summary file"
        self.counts = {n: dict(source_record(os.path.join(REL_DIR, n), REL_URL), product="2020 Census counts by 119th Congress and 2024 state legislative district")
                       for n in ("CD119_UR_POPAREA.txt", "SLDU2024_UR_POPAREA.txt", "SLDL2024_UR_POPAREA.txt")}


def load_everything():
    print("Reading the Census files ...")
    check_shells()
    geo = geographies()
    gids = set(geo)
    T = {t: read_table(t, gids) for t in TABLES}
    cd, up, lo = counts("CD119_UR_POPAREA.txt", 2), counts("SLDU2024_UR_POPAREA.txt", 3), counts("SLDL2024_UR_POPAREA.txt", 3)
    by_level = {"500": {}, "610": {}, "620": {}, "040": {}}
    for gid, (sl, st, code, name) in geo.items():
        by_level[sl][(st, code)] = (gid, name)
    state_acs = {st: T["b01003"][gid]["001"] for (st, _), (gid, _n) in by_level["040"].items() if gid in T["b01003"]}
    return geo, T, cd, up, lo, by_level, state_acs


def congress(loaded, S):
    geo, T, cd, up, lo, by_level, state_acs = loaded
    rows, states, csv_rows = [], {}, []
    for fips, st in sorted(FIPS.items(), key=lambda kv: kv[1]):
        if st == "DC":
            continue
        rows_2020 = {code: v for (s, code), v in cd.items() if s == fips}
        geo_rows = {code: v for (s, code), v in by_level["500"].items() if s == fips}
        if not rows_2020 and geo_rows:
            # a state with one representative has no row in the Bureau's congressional file: its district is the whole
            # state, so the count comes from the legislative tabulation of the same blocks
            parts = [v for (s, _), v in up.items() if s == fips] or [v for (s, _), v in lo.items() if s == fips]
            pop = sum(v[0] for v in parts)
            land = round(sum(v[1] for v in parts), 2)
            urban = round(sum(v[0] * v[2] for v in parts) / pop, 2) if pop else 0
            rows_2020 = {"00": (pop, land, urban)}
        seats = len(rows_2020)
        key_of = lambda code, st=st: f"{st}-{'AL' if code == '00' else int(code)}"
        drows, total, ideal, per, mism = chamber_rows(st, rows_2020, geo_rows, T, seats, key_of)
        for r in drows:
            r["st"], r["d"] = st, (0 if r["d"] == "00" else int(r["d"]))
            r["at_large"] = r["d"] == 0
        upper_total = sum(v[0] for (s, _), v in up.items() if s == fips)
        lower_total = sum(v[0] for (s, _), v in lo.items() if s == fips)
        summ, ctl = summarize(drows, total, ideal, per, seats, mism, state_acs.get(fips), RESIDENT_2020.get(st))
        ctl["tabulations_agree"] = {"congress": total, "upper": upper_total or None, "lower": lower_total or None,
                                    "agree": all(t in (0, total) for t in (upper_total, lower_total)),
                                    "at_large_from_legislative_tabulation": len(drows) == 1}
        states[st] = {"summary": summ, "control": ctl}
        rows += drows
    devs = [r["dev_pct"] for r in rows if r["dev_pct"] is not None]
    out = {"method": METHOD_VERSION, "generated": dt.date.today().isoformat(), "congress": 119,
           "sources": [S.counts["CD119_UR_POPAREA.txt"]] + S.acs,
           "summary": {"districts": len(rows), "states": len(states), "pop2020_total": sum(r["pop2020"] or 0 for r in rows),
                       "dev": {"min": min(devs), "max": max(devs)} if devs else None,
                       "spreads": sorted(((v["summary"]["dev"]["spread"], k) for k, v in states.items() if v["summary"].get("dev")), reverse=True)},
           "control": {"states_matching_resident_2020": [k for k, v in states.items() if v["control"]["count_matches_resident"]],
                       "states_where_tabulations_agree": sum(1 for v in states.values() if v["control"]["tabulations_agree"]["agree"]),
                       "states_acs_sum_matches": sum(1 for v in states.values() if v["control"]["acs_sum_matches_state"]),
                       "under18_mismatches": [c for v in states.values() for c in v["control"]["under18_mismatches"]]},
           "states": states, "districts": rows}
    return out


def one_state(code, loaded, S):
    geo, T, cd, up, lo, by_level, state_acs = loaded
    sys.path.insert(0, HERE)
    from states.places import place
    P = place(code)
    fips = P["fips"]
    chambers, csv_rows = {}, []
    for key, table2020, level in (("upper", up, "610"), ("lower", lo, "620")):
        if not P.get(key):
            continue
        rows_2020 = {c: v for (s, c), v in table2020.items() if s == fips}
        geo_rows = {c: v for (s, c), v in by_level[level].items() if s == fips}
        # the district file and the pages write 062 as 62 and 01A as 1A; the Census code is kept in "census_code"
        trim = lambda c: (c.lstrip("0") or "0")
        drows, total, ideal, per, mism = chamber_rows(P["code"], rows_2020, geo_rows, T, P[key]["seats"], trim)
        for r in drows:
            r["census_code"], r["d"] = r["d"], trim(r["d"])
        summ, ctl = summarize(drows, total, ideal, per, P[key]["seats"], mism, state_acs.get(fips), RESIDENT_2020.get(P["code"]))
        cd_total = sum(v[0] for (s, _), v in cd.items() if s == fips)          # 0 for a state with one representative: the file has no row for it
        ctl["count_vs_congress_tabulation"] = [total, cd_total] if cd_total else None
        ctl["tabulations_agree"] = (total == cd_total) if cd_total else None
        name = "CD119_UR_POPAREA.txt" if False else ("SLDU2024_UR_POPAREA.txt" if key == "upper" else "SLDL2024_UR_POPAREA.txt")
        chambers[key] = {"name": P[key]["name"], "sources": [S.counts[name]] + S.acs, "summary": summ, "control": ctl, "districts": drows}
        csv_rows += [[P[key]["name"], r["d"]] + csv_tail(r) for r in drows]
        report(f"{P['name']} {P[key]['name']}", summ, ctl)
        if cd_total:
            print(f"  Control a': the {P[key]['name']} tabulation totals {total:,}; the congressional tabulation of the same state totals {cd_total:,}: {'agree' if total == cd_total else 'DIFFER'}")
        else:
            print(f"  Control a': the state has one representative, so the Bureau's congressional file has no row to compare")
    out = {"method": METHOD_VERSION, "generated": dt.date.today().isoformat(), "place": P["code"], "name": P["name"], "legislature": P["legislature"], "chambers": chambers}
    out_path = os.path.join(HERE, f"state_{P['code'].lower()}_people.json")
    with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, separators=(",", ":"))
    with open(os.path.splitext(out_path)[0] + ".csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["chamber", "district"] + CSV_HEAD)
        w.writerows(csv_rows)
    print(f"  Wrote {out_path} and its .csv")


def write_congress(out):
    out_path = os.path.join(HERE, "us_district_people.json")
    with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, separators=(",", ":"))
    with open(os.path.splitext(out_path)[0] + ".csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["district", "state", "number"] + CSV_HEAD)
        for r in out["districts"]:
            w.writerow([r["key"], r["st"], r["d"]] + csv_tail(r))
    s, c = out["summary"], out["control"]
    print(f"  The 119th Congress: {s['districts']} districts in {s['states']} states, {s['pop2020_total']:,} people in 2020; "
          f"deviation from each state's ideal {s['dev']['min']:+.3f}% to {s['dev']['max']:+.3f}%; widest spreads: "
          + ", ".join(f"{k} {v:.2f}" for v, k in s["spreads"][:5]))
    print(f"  Control a: 2020 counts equal the apportionment resident population in {len(c['states_matching_resident_2020'])} of {len(RESIDENT_2020) - 0} states checked "
          f"({', '.join(c['states_matching_resident_2020'])}); the three tabulations agree in {c['states_where_tabulations_agree']} of {s['states']} states")
    print(f"  Control b: ACS district sums equal the state figure in {c['states_acs_sum_matches']} of {s['states']} states")
    print(f"  Control c: under-18 differs from B09001 in {len(c['under18_mismatches'])} districts" + (f": {', '.join(c['under18_mismatches'][:8])}" if c["under18_mismatches"] else ""))
    print(f"  Wrote {out_path} and its .csv")


def selftest():
    """The Bureau's own worked examples (handbook chapter 8, 2020 edition): Example 1, never-married females in Fairfax
    County, Arlington County and Alexandria, 2015: 135,173 +/-3,860; 43,104 +/-2,642; 24,842 +/-1,957 -> 203,119 +/-5,070.
    Example 3: that number over all females 15 and over, 466,037 +/-391, 97,360 +/-572, 67,101 +/-459 -> 0.322 +/-0.008."""
    good = True
    total = 135173 + 43104 + 24842
    m = moe_sum([3860, 2642, 1957])
    ok = total == 203119 and round(m) == 5070
    print(f"  sum: {total:,} +/-{m:,.0f} (the handbook says 203,119 +/-5,070) {'ok' if ok else 'FAIL'}"); good &= ok
    den, mden = 466037 + 97360 + 67101, moe_sum([391, 572, 459])
    p, mp = moe_share(203119, 5070, den, mden)
    ok = round(p, 3) == 0.322 and round(mp, 3) == 0.008
    print(f"  proportion: {p:.3f} +/-{mp:.3f} (the handbook says 0.322 +/-0.008) {'ok' if ok else 'FAIL'}"); good &= ok
    # the ratio form must take over when the proportion form would take the root of a negative number
    p2, mp2 = moe_share(50, 30, 60, 100)
    ok = mp2 is not None and mp2 > 0
    print(f"  ratio fallback: {p2:.3f} +/-{mp2:.3f} {'ok' if ok else 'FAIL'}"); good &= ok
    # the table shells must carry the labels this program assumes for every column it reads
    try:
        check_shells()
        print("  table shells: every column this lens reads carries the expected label ok")
    except SystemExit as e:
        print(f"  table shells: {e}"); good = False
    return good


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--state", default="", help="one state's two-letter code from states/places.py")
    ap.add_argument("--congress-only", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--fetch", action="store_true", help="download the source files into the caches (done automatically when missing)")
    args = ap.parse_args()
    if args.selftest:
        good = selftest()
        print("Self-test passed." if good else "SELF-TEST FAILED.")
        return 0 if good else 1
    if args.fetch or not all(os.path.exists(os.path.join(ACS_DIR, f"acsdt5y2024-{t}.dat")) for t in TABLES):
        fetch_all()
    S = Sources()
    loaded = load_everything()
    if args.state:
        one_state(args.state, loaded, S)
        return 0
    write_congress(congress(loaded, S))
    if args.congress_only:
        return 0
    sys.path.insert(0, HERE)
    from states.places import PLACES
    for code in sorted(PLACES):
        one_state(code, loaded, S)
    return 0


if __name__ == "__main__":
    sys.exit(main())
