"""election/model/census.py - who lives in each Minnesota precinct and school district, from the Census Bureau's own
files, carried down through the 2020 blocks (model.md 1.3; ARCHITECTURE.md 4.1). Figures describe places, never voters.

    python -m election.model.census            fetch what is missing (once), build, print the controls
    python -m election.model.census --selftest the arithmetic on a made-up state; downloads nothing

SOURCES (U.S. Census Bureau, keyless static files on www2.census.gov; John's yes of 2026-10-10, D5):
  - 2020 blocks: TIGER/Line 2020 tl_2020_27_tabblock20.zip (each block's 2020 population POP20, housing units HOUSING20,
    land area and internal point; the shapes themselves are not read).
  - ACS 2020-2024 five-year table-based summary files, block-group rows: B01001, B01002, B01003, B03002, B15003, B19013,
    B25003 (already in states_cache/acs2024/, read only) and B11005, B12001, B25038, B29001, C17002 (fetched here).
  - The citizen voting-age population special tabulation 2020-2024 (CVAP_2020-2024_ACS_csv_files.zip, BlockGr.csv).
  Every file's SHA-256 goes into run_inputs.

METHOD (version CENSUS_METHOD):
  1. Each 2020 block goes to the precinct of today's "Voting Districts, Minnesota" table (and to today's school district,
     Minnesota Department of Education lines) that holds its internal point (even-odd rule over the shape's rings). A
     block whose point falls in no precinct (a shoreline, a sliver) goes to the nearest precinct by distance to its
     edge, and is counted.
  2. Each block group's estimate is shared among its blocks in proportion to 2020 population (people tables), housing
     units (household tables); a block group whose blocks hold no one in 2020 shares by land area.
  3. Blocks are added into precincts and school districts. Margins: the share of a block group's margin goes with its
     share of the estimate (parts of one block group fully correlated); parts of different block groups add as the
     root of the sum of squares (Census Bureau handbook, 2020, ch. 8, formula 1); shares use formulas 6 and 7.
  4. Medians (age, household income) cannot be added up: a precinct gets the average of its block groups' medians
     weighted by its people (or households) in each, marked "average of block-group medians", no margin.
CONTROLS: the blocks add up to the state's 2020 resident population (5,706,494); every block is placed; the ACS block
groups add up to the Bureau's own state figure for B01003 (a controlled estimate); people shared to precincts add up
to the block groups' total.
"""

import argparse
import csv
import io
import json
import math
import os
import re
import sys
import zipfile

from election.model import HERE, cache_dir, fetch, load_json, save_json, sha_file, FetchError

CENSUS_METHOD = "census-1.0"
STATE_FIPS = "27"
RESIDENT_2020 = 5706494          # Census Bureau, Apportionment Population and Number of Representatives: 2020, Table 2
ACS_LOCAL = os.path.join(HERE, "states_cache", "acs2024")
ACS_URL = "https://www2.census.gov/programs-surveys/acs/summary_file/2024/table-based-SF/data/5YRData/"
BLOCK_URL = "https://www2.census.gov/geo/tiger/TIGER2020/TABBLOCK20/tl_2020_27_tabblock20.zip"
CVAP_URL = "https://www2.census.gov/programs-surveys/decennial/rdo/datasets/2024/2024-cvap/CVAP_2020-2024_ACS_csv_files.zip"
BAF_URL = "https://www2.census.gov/geo/docs/maps-data/data/baf2020/BlockAssign_ST27_MN.zip"
PRECINCTS = os.path.join(HERE, "states_cache", "mn_local", "sos_votingdistricts_geometry_4326.json.gz")
SCHOOLS = os.path.join(HERE, "states_cache", "mn_local", "mde_school_district_geometry_4326.json.gz")
HAVE = ("b01001", "b01002", "b01003", "b03002", "b15003", "b19013", "b25003")
FETCH = ("b11005", "b12001", "b25038", "b29001", "c17002")
CONTROLLED = -555555555
SCHOOL_PREFIX = {"01": "ISD", "02": "CSD", "03": "SSD"}

# Which cells each table gives, and the label the Bureau's table shell must carry for it (checked before use).
# weight: what a block group's estimate is shared by (pop: 2020 people; hu: 2020 housing units).
CELLS = {
    "b01003": ("pop", {"001": "Total"}),
    "b01001": ("pop", {"001": "Total", "026": "Female", "003": "Under 5 years", "006": "15 to 17 years", "007": "18 and 19 years",
                       "011": "25 to 29 years", "020": "65 and 66 years", "025": "85 years and over", "027": "Under 5 years",
                       "030": "15 to 17 years", "031": "18 and 19 years", "035": "25 to 29 years", "044": "65 and 66 years",
                       "049": "85 years and over"}),
    "b03002": ("pop", {"001": "Total", "003": "White alone", "004": "Black or African American alone",
                       "005": "American Indian and Alaska Native alone", "006": "Asian alone",
                       "007": "Native Hawaiian and Other Pacific Islander alone", "008": "Some other race alone",
                       "009": "Two or more races", "012": "Hispanic or Latino"}),
    "b15003": ("pop", {"001": "Total", "022": "Bachelor's degree", "023": "Master's degree", "024": "Professional school degree",
                       "025": "Doctorate degree"}),
    "b25003": ("hu", {"001": "Total", "002": "Owner occupied"}),
    "b12001": ("pop", {"001": "Total", "003": "Never married", "004": "Now married", "012": "Never married", "013": "Now married"}),
    "b11005": ("hu", {"001": "Total", "002": "Households with one or more people under 18 years"}),
    "c17002": ("pop", {"001": "Total", "002": "Under .50", "003": ".50 to .99"}),
    "b25038": ("hu", {"001": "Total", "003": "Moved in 2023 or later", "004": "Moved in 2020 to 2022", "010": "Moved in 2023 or later",
                      "011": "Moved in 2020 to 2022"}),
    "b29001": ("pop", {"001": "Total", "002": "18 to 29 years", "005": "65 years and over"}),
    "b01002": ("median", {"001": "Total"}),
    "b19013": ("median", {"001": "Median household income"}),
}
UNDER18 = ["003", "004", "005", "006", "027", "028", "029", "030"]
AGE18_29 = ["007", "008", "009", "010", "011", "031", "032", "033", "034", "035"]
AGE65 = ["020", "021", "022", "023", "024", "025", "044", "045", "046", "047", "048", "049"]


class Stop(SystemExit):
    pass


# ---------------------------------------------------------------- margins (handbook formulas, as district_people.py)

def moe_sum(moes):
    return math.sqrt(sum(m * m for m in moes))


def moe_share(a, moe_a, b, moe_b):
    if not b:
        return None, None
    p = a / b
    under = moe_a * moe_a - p * p * moe_b * moe_b
    if under < 0:
        under = moe_a * moe_a + p * p * moe_b * moe_b
    return p, math.sqrt(under) / b


# ---------------------------------------------------------------- the files

def files(say=print):
    """Fetch what is missing (each file once) and return {name: (path, url)}."""
    d = cache_dir("mn", "census")
    out = {"tabblock20": (os.path.join(d, os.path.basename(BLOCK_URL)), BLOCK_URL),
           "cvap": (os.path.join(d, os.path.basename(CVAP_URL)), CVAP_URL),
           "blockassign": (os.path.join(d, os.path.basename(BAF_URL)), BAF_URL)}
    for t in HAVE:
        p = os.path.join(ACS_LOCAL, f"acsdt5y2024-{t}.dat")
        out[t] = (p, ACS_URL + os.path.basename(p))
    for t in FETCH:
        p = os.path.join(d, f"acsdt5y2024-{t}.dat")
        out[t] = (p, ACS_URL + os.path.basename(p))
    out["shells"] = (os.path.join(ACS_LOCAL, "ACS20245YR_Table_Shells.txt"), ACS_URL.replace("data/5YRData/", "documentation/") +
                     "ACS20245YR_Table_Shells.txt")
    for name, (path, url) in out.items():
        if not os.path.exists(path):
            if path.startswith(ACS_LOCAL):
                raise Stop(f"    {path} is missing; it is the kit's own copy and this program does not replace it")
            say(f"    fetching {os.path.basename(path)} from the Census Bureau (once)")
            fetch(url, path, say=say)
    return out


def check_shells(path):
    want = {(t.upper(), c): lab for t, (_w, cells) in CELLS.items() for c, lab in cells.items()}
    got = {}
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            p = line.split("|")
            if len(p) > 4 and "_" in p[3]:
                tid, cell = p[3].split("_", 1)
                if (tid, cell) in want:
                    got[(tid, cell)] = p[4].strip().rstrip(":")
    bad = [f"{t}_{c} is '{got.get((t, c))}', expected '{lab}'" for (t, c), lab in want.items() if not (got.get((t, c)) or "").startswith(lab)]
    if bad:
        raise Stop("    the table shells do not say what this program expects: " + "; ".join(bad))


def read_acs(path, table):
    """{block group (12 digits): {cell: (estimate, moe)}} for Minnesota's block groups, and the state row."""
    cells = CELLS[table][1]
    rows, state = {}, None
    with open(path, encoding="utf-8", errors="replace") as fh:
        head = fh.readline().rstrip("\n").split("|")
        idx = {}
        for c in cells:
            e, m = f"{table.upper()}_E{c}", f"{table.upper()}_M{c}"
            if e not in head or m not in head:
                raise Stop(f"    {os.path.basename(path)} has no column {e}")
            idx[c] = (head.index(e), head.index(m))
        for line in fh:
            if line.startswith("1500000US27") or line.startswith("0400000US27|"):
                p = line.rstrip("\n").split("|")
                rec = {}
                for c, (ie, im) in idx.items():
                    e, m = float(p[ie]), float(p[im])
                    if e <= -100000000:
                        e = None
                    if m == CONTROLLED or m <= -100000000:
                        m = 0.0
                    rec[c] = (e, m)
                if p[0].startswith("0400000US27"):
                    state = rec
                else:
                    rows[p[0][9:]] = rec
    return rows, state


def read_cvap(path):
    """{block group: (cvap, moe, citizens, moe)} from BlockGr.csv, line 1 (Total) only."""
    out = {}
    with zipfile.ZipFile(path) as z:
        name = next(n for n in z.namelist() if n.lower().endswith("blockgr.csv"))
        with z.open(name) as raw:
            rd = csv.DictReader(io.TextIOWrapper(raw, encoding="latin-1"))
            need = {"geoid", "lnnumber", "cvap_est", "cvap_moe", "cit_est", "cit_moe"}
            if not need <= set(rd.fieldnames or []):
                raise Stop(f"    the CVAP file's BlockGr.csv lacks {sorted(need - set(rd.fieldnames or []))}")
            for r in rd:
                g = r["geoid"]
                if r["lnnumber"] != "1" or not g.startswith("1500000US27"):
                    continue
                out[g[9:]] = tuple(float(r[k] or 0) for k in ("cvap_est", "cvap_moe", "cit_est", "cit_moe"))
    return out


def read_blocks(path, say=print):
    """Every 2020 block of Minnesota: [geoid, pop, housing units, land m2, lon, lat], from the zip's attribute table."""
    import shapefile
    cache = os.path.join(cache_dir("mn", "census"), "blocks_2020_mn.json")
    if os.path.exists(cache):
        doc = load_json(cache)
        if doc.get("sha256") == sha_file(path):
            return doc["blocks"]
    with zipfile.ZipFile(path) as z:
        dbf = next(n for n in z.namelist() if n.lower().endswith(".dbf"))
        rd = shapefile.Reader(dbf=io.BytesIO(z.read(dbf)))
        names = [f[0] for f in rd.fields[1:]]
        need = ["GEOID20", "POP20", "HOUSING20", "ALAND20", "INTPTLAT20", "INTPTLON20"]
        if any(n not in names for n in need):
            raise Stop(f"    the block file lacks {[n for n in need if n not in names]}")
        ix = [names.index(n) for n in need]
        blocks = []
        for rec in rd.iterRecords():
            g, pop, hu, aland, lat, lon = (rec[i] for i in ix)
            blocks.append([g, int(pop), int(hu), int(aland or 0), float(lon), float(lat)])
    save_json(cache, {"sha256": sha_file(path), "blocks": blocks})
    say(f"    read {len(blocks):,} blocks from {os.path.basename(path)}")
    return blocks


# ---------------------------------------------------------------- placing points in shapes

class Shapes:
    """Point-in-polygon for a set of shapes (each a list of rings, even-odd rule), with a coarse grid of boxes and
    each shape's edges filed by latitude band so a test reads only the edges near the point."""

    def __init__(self, items, cell=0.05, bands=64):
        self.ids, self.boxes, self.bands, self.rings = [], [], [], []
        self.cell = cell
        self.grid = {}
        for sid, rings in items:
            pts = [p for r in rings for p in r]
            if not pts:
                continue
            x0, y0 = min(p[0] for p in pts), min(p[1] for p in pts)
            x1, y1 = max(p[0] for p in pts), max(p[1] for p in pts)
            k = len(self.ids)
            self.ids.append(sid)
            self.boxes.append((x0, y0, x1, y1))
            self.rings.append(rings)
            h = max((y1 - y0) / bands, 1e-9)
            table = [[] for _ in range(bands)]
            for r in rings:
                for i in range(len(r)):
                    ax, ay = r[i - 1]
                    bx, by = r[i]
                    lo, hi = int((min(ay, by) - y0) / h), int((max(ay, by) - y0) / h)
                    for b in range(max(lo, 0), min(hi, bands - 1) + 1):
                        table[b].append((ax, ay, bx, by))
            self.bands.append((y0, h, bands, table))
            for gx in range(int(math.floor(x0 / cell)), int(math.floor(x1 / cell)) + 1):
                for gy in range(int(math.floor(y0 / cell)), int(math.floor(y1 / cell)) + 1):
                    self.grid.setdefault((gx, gy), []).append(k)

    def _inside(self, k, x, y):
        y0, h, n, table = self.bands[k]
        b = int((y - y0) / h)
        if b < 0 or b >= n:
            return False
        c = False
        for ax, ay, bx, by in table[b]:
            if (ay > y) != (by > y) and x < (bx - ax) * (y - ay) / (by - ay) + ax:
                c = not c
        return c

    def find(self, x, y):
        for k in self.grid.get((int(math.floor(x / self.cell)), int(math.floor(y / self.cell))), ()):
            x0, y0, x1, y1 = self.boxes[k]
            if x0 <= x <= x1 and y0 <= y <= y1 and self._inside(k, x, y):
                return self.ids[k]
        return None

    def nearest(self, x, y, reach=0.2):
        """The shape whose edge is nearest the point (in degrees, longitude scaled by the latitude), within reach."""
        best, bid = None, None
        sx = math.cos(math.radians(y))
        for k, (x0, y0, x1, y1) in enumerate(self.boxes):
            if x < x0 - reach or x > x1 + reach or y < y0 - reach or y > y1 + reach:
                continue
            for r in self.rings[k]:
                for i in range(len(r)):
                    ax, ay = r[i - 1]
                    bx, by = r[i]
                    dx, dy = (bx - ax) * sx, by - ay
                    px, py = (x - ax) * sx, y - ay
                    t = 0.0 if dx == dy == 0 else max(0.0, min(1.0, (px * dx + py * dy) / (dx * dx + dy * dy)))
                    d = (px - t * dx) ** 2 + (py - t * dy) ** 2
                    if best is None or d < best:
                        best, bid = d, self.ids[k]
        return bid


def load_shapes(path, key):
    import gzip
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        doc = json.load(fh)
    return [(key(attrs), rings) for attrs, rings in doc["rows"]], doc


def school_key(a):
    return SCHOOL_PREFIX.get(a["sdtype"], "SD") + a["sdnumber"]


def assign(blocks, say=print):
    """{block geoid: (precinct VTDID, school id, how)}; cached against the three files' fingerprints."""
    cache = os.path.join(cache_dir("mn", "census"), "blocks_assigned.json")
    stamp = [sha_file(PRECINCTS), sha_file(SCHOOLS), len(blocks)]
    if os.path.exists(cache):
        doc = load_json(cache)
        if doc.get("stamp") == stamp:
            return doc["assigned"], doc["counts"]
    pitems, _ = load_shapes(PRECINCTS, lambda a: a["vtdid"])
    sitems, _ = load_shapes(SCHOOLS, school_key)
    P, S = Shapes(pitems), Shapes(sitems)
    out, counts = {}, {"precinct_inside": 0, "precinct_nearest": 0, "precinct_none": 0, "school_inside": 0, "school_nearest": 0,
                       "school_none": 0, "people_nearest": 0}
    for i, (g, pop, hu, aland, x, y) in enumerate(blocks):
        p = P.find(x, y)
        how = "inside"
        if p is None:
            p = P.nearest(x, y)
            how = "nearest"
            counts["precinct_nearest" if p else "precinct_none"] += 1
            counts["people_nearest"] += pop if p else 0
        else:
            counts["precinct_inside"] += 1
        s = S.find(x, y)
        if s is None:
            s = S.nearest(x, y) if (pop or hu) else None
            counts["school_nearest" if s else "school_none"] += 1
        else:
            counts["school_inside"] += 1
        out[g] = [p, s, how]
        if i and i % 25000 == 0:
            say(f"      placed {i:,} of {len(blocks):,} blocks")
    save_json(cache, {"stamp": stamp, "assigned": out, "counts": counts})
    return out, counts


def vtd2020(blocks, assigned, path):
    """{2020 Census voting district as a precinct code (27 + county + last four digits): {today's VTDID: [2020 people, blocks]}},
    from the Bureau's 2020 block assignment file: how each 2020 voting district's people lie in today's precincts."""
    out = {}
    pop = {b[0]: b[1] for b in blocks}
    with zipfile.ZipFile(path) as z:
        name = next(n for n in z.namelist() if n.upper().endswith("_VTD.TXT"))
        with z.open(name) as fh:
            head = fh.readline().decode().strip().split("|")
            if head != ["BLOCKID", "COUNTYFP", "DISTRICT"]:
                raise Stop(f"    the block assignment file's columns are {head}")
            for line in fh:
                g, county, dist = line.decode().strip().split("|")
                if not dist.startswith("00"):
                    continue                       # ZZ: no voting district (water)
                vid = STATE_FIPS + county + dist[2:]
                p = assigned.get(g, [None])[0]
                if p is not None:
                    d = out.setdefault(vid, {}).setdefault(p, [0, 0])
                    d[0] += pop.get(g, 0)
                    d[1] += 1
    return out


# ---------------------------------------------------------------- carrying block groups down

def carry(blocks, assigned, tables, cvap):
    """{unit kind: {unit id: {feature: [estimate, moe]}}} and the controls."""
    by_bg = {}
    for g, pop, hu, aland, _x, _y in blocks:
        by_bg.setdefault(g[:12], []).append((g, pop, hu, aland))
    units = {"precinct": {}, "school": {}}
    # 2020 counts, exact
    for g, pop, hu, aland, _x, _y in blocks:
        p, s, _how = assigned[g]
        for kind, uid in (("precinct", p), ("school", s)):
            if uid is None:
                continue
            u = units[kind].setdefault(uid, {"_parts": {}, "pop2020": 0, "hu2020": 0, "land_m2": 0})
            u["pop2020"] += pop
            u["hu2020"] += hu
            u["land_m2"] += aland
    # each block group's weight in each unit
    weights = {}            # bg -> {"pop": {(kind, uid): share}, "hu": ...}
    leftovers = 0
    for bg, bl in by_bg.items():
        w = {}
        for basis, col in (("pop", 1), ("hu", 2)):
            tot = sum(b[col] for b in bl)
            area = sum(b[3] for b in bl) or len(bl)
            sh = {}
            for b in bl:
                part = (b[col] / tot) if tot else ((b[3] or (1 if not sum(x[3] for x in bl) else 0)) / area)
                if not part:
                    continue
                p, s, _how = assigned[b[0]]
                for kind, uid in (("precinct", p), ("school", s)):
                    if uid is not None:
                        sh[(kind, uid)] = sh.get((kind, uid), 0.0) + part
            w[basis] = sh
            w[basis + "_total"] = tot
        weights[bg] = w
    acs_in = {}
    for t, (basis, cells) in CELLS.items():
        rows = tables[t][0]
        for bg, rec in rows.items():
            w = weights.get(bg)
            if w is None:
                if rec.get("001", (0, 0))[0]:
                    leftovers += 1
                continue
            sh = w["pop" if basis in ("pop", "median") else "hu"]
            for (kind, uid), share in sh.items():
                u = units[kind].setdefault(uid, {"_parts": {}, "pop2020": 0, "hu2020": 0, "land_m2": 0})
                parts = u["_parts"]
                if basis == "median":
                    e = rec["001"][0]
                    if e is None:
                        continue
                    wt = share * (w["pop_total"] if t == "b01002" else w["hu_total"])
                    acc = parts.setdefault(f"{t}_median", [0.0, 0.0])
                    acc[0] += e * wt
                    acc[1] += wt
                    continue
                for c, (e, m) in rec.items():
                    if e is None:
                        continue
                    acc = parts.setdefault(f"{t}_{c}", [0.0, 0.0])
                    acc[0] += share * e
                    acc[1] += (share * m) ** 2
            if t == "b01003" and rec["001"][0] is not None:
                acs_in[bg] = rec["001"][0]
    for bg, (cv, cvm, ci, cim) in cvap.items():
        w = weights.get(bg)
        if not w:
            continue
        for (kind, uid), share in w["pop"].items():
            parts = units[kind].setdefault(uid, {"_parts": {}, "pop2020": 0, "hu2020": 0, "land_m2": 0})["_parts"]
            for name, e, m in (("cvap", cv, cvm), ("cit", ci, cim)):
                acc = parts.setdefault(f"cvapfile_{name}", [0.0, 0.0])
                acc[0] += share * e
                acc[1] += (share * m) ** 2
    return units, acs_in, leftovers


def derive(u):
    """The features of one unit from its carried cells: {name: (value, moe, note)}."""
    P = u["_parts"]

    def c(t, cell):
        e, v = P.get(f"{t}_{cell}", (0.0, 0.0))
        return e, math.sqrt(v)

    def total(t, cells):
        es = [c(t, x) for x in cells]
        return sum(e for e, _m in es), moe_sum([m for _e, m in es])

    def share(num, den):
        p, m = moe_share(num[0], num[1], den[0], den[1])
        return (p, m)

    out = {}
    land = u["land_m2"] / 2589988.11
    out["pop2020"] = (u["pop2020"], 0.0, "2020 census count, exact")
    out["housing2020"] = (u["hu2020"], 0.0, "2020 census count, exact")
    out["land_sqmi"] = (round(land, 4), 0.0, "land area of the 2020 blocks placed here")
    out["density2020"] = ((u["pop2020"] / land) if land else None, 0.0, "people per square mile of land, 2020")
    pop = c("b01003", "001")
    out["acs_pop"] = (pop[0], pop[1], None)
    tot = c("b01001", "001")
    u18 = total("b01001", UNDER18)
    out["acs_adults"] = (tot[0] - u18[0], moe_sum([tot[1], u18[1]]), "population minus the under-18 bands of B01001")
    out["share_under18"] = share(u18, tot)
    out["share_18_29"] = share(total("b01001", AGE18_29), tot)
    out["share_65plus"] = share(total("b01001", AGE65), tot)
    out["share_female"] = share(c("b01001", "026"), tot)
    r = c("b03002", "001")
    out["share_hispanic"] = share(c("b03002", "012"), r)
    out["share_white_nh"] = share(c("b03002", "003"), r)
    out["share_black_nh"] = share(c("b03002", "004"), r)
    out["share_aian_nh"] = share(c("b03002", "005"), r)
    out["share_asian_nh"] = share(c("b03002", "006"), r)
    out["share_other_multi_nh"] = share(total("b03002", ["007", "008", "009"]), r)
    out["share_bachelors_plus"] = share(total("b15003", ["022", "023", "024", "025"]), c("b15003", "001"))
    hh = c("b25003", "001")
    out["acs_households"] = (hh[0], hh[1], None)
    out["share_owner"] = share(c("b25003", "002"), hh)
    m15 = c("b12001", "001")
    out["share_now_married"] = share(total("b12001", ["004", "013"]), m15)
    out["share_never_married"] = share(total("b12001", ["003", "012"]), m15)
    out["share_households_children"] = share(c("b11005", "002"), c("b11005", "001"))
    out["share_below_poverty"] = share(total("c17002", ["002", "003"]), c("c17002", "001"))
    out["share_moved_since_2020"] = share(total("b25038", ["003", "004", "010", "011"]), c("b25038", "001"))
    cv = c("b29001", "001")
    out["acs_cvap"] = (cv[0], cv[1], "B29001 total")
    out["share_cvap_18_29"] = share(c("b29001", "002"), cv)
    out["share_cvap_65plus"] = share(c("b29001", "005"), cv)
    for name, key in (("cvap", "cvapfile_cvap"), ("citizens", "cvapfile_cit")):
        e, v = P.get(key, (0.0, 0.0))
        out[name] = (e, math.sqrt(v), "CVAP special tabulation 2020-2024, line 1 (Total)")
    for name, key, what in (("median_age_avg", "b01002_median", "average of block-group median ages, weighted by 2020 people"),
                            ("median_income_avg", "b19013_median", "average of block-group median household incomes, weighted by 2020 housing units")):
        e, w = P.get(key, (0.0, 0.0))
        out[name] = ((e / w) if w else None, None, what)
    return {k: (v[0], v[1], v[2] if len(v) > 2 else None) for k, v in out.items()}


# ---------------------------------------------------------------- the build

def build(say=print):
    """Everything above. Returns {"units": {kind: {id: {feature: (value, moe, note)}}}, "controls": {...},
    "inputs": [run_inputs rows without the run]}."""
    f = files(say)
    check_shells(f["shells"][0])
    blocks = read_blocks(f["tabblock20"][0], say)
    say(f"    placing {len(blocks):,} blocks in today's precincts and school districts")
    assigned, counts = assign(blocks, say)
    tables = {}
    for t in CELLS:
        tables[t] = read_acs(f[t][0], t)
    cvap = read_cvap(f["cvap"][0])
    units, acs_in, leftovers = carry(blocks, assigned, tables, cvap)
    feats = {kind: {uid: derive(u) for uid, u in us.items()} for kind, us in units.items()}
    vtd = vtd2020(blocks, assigned, f["blockassign"][0])

    total_blocks = sum(b[1] for b in blocks)
    placed = sum(u["pop2020"] for u in units["precinct"].values())
    in_school = sum(u["pop2020"] for u in units["school"].values())
    bg_sum = sum(acs_in.values())
    state_acs = tables["b01003"][1]["001"][0] if tables["b01003"][1] else None
    carried = sum(v["acs_pop"][0] for v in feats["precinct"].values())
    cv_bg = sum(v[0] for v in cvap.values())
    cv_carried = sum(v["cvap"][0] for v in feats["precinct"].values())
    controls = {
        "blocks_vs_2020_count": {"blocks": total_blocks, "official": RESIDENT_2020, "holds": total_blocks == RESIDENT_2020,
                                 "source": "Census Bureau, 2020 apportionment and resident population, Table 2"},
        "blocks_placed_in_precincts": {"people": placed, "of": total_blocks, "holds": placed == total_blocks,
                                       "by_nearest_edge": counts["precinct_nearest"], "people_by_nearest_edge": counts["people_nearest"],
                                       "not_placed": counts["precinct_none"]},
        "blocks_placed_in_school_districts": {"people": in_school, "of": total_blocks, "holds": in_school == total_blocks,
                                              "by_nearest_edge": counts["school_nearest"], "not_placed": counts["school_none"]},
        "acs_block_groups_vs_state": {"block_groups": round(bg_sum), "state_row": state_acs,
                                      "holds": state_acs is not None and round(bg_sum) == round(state_acs)},
        "acs_carried_to_precincts": {"carried": round(carried, 1), "block_groups": bg_sum, "holds": abs(carried - bg_sum) < 0.5,
                                     "block_groups_with_people_but_no_blocks": leftovers},
        "cvap_carried_to_precincts": {"carried": round(cv_carried, 1), "block_groups": cv_bg, "holds": abs(cv_carried - cv_bg) < 0.5},
        "precincts_with_figures": len(feats["precinct"]),
        "school_districts_with_figures": len(feats["school"]),
    }
    inputs = [("census-blocks-2020", f["tabblock20"], "census", "2020 blocks: POP20, HOUSING20, ALAND20 and internal points"),
              ("census-cvap-2020-2024", f["cvap"], "census", "citizen voting-age population special tabulation, BlockGr.csv"),
              ("census-block-assignment-2020", f["blockassign"], "census", "2020 blocks to 2020 voting districts (carrying past precincts)")]
    inputs += [(f"acs-2020-2024-{t}", f[t], "census", f"ACS 2020-2024 five-year, table {t.upper()}, Minnesota block groups") for t in CELLS]
    inputs += [("mn-precinct-shapes", (PRECINCTS, "https://enterprise.gisdata.mn.gov/aghost/rest/services/us_mn_state_sos/bdry_votingdistricts/FeatureServer/0"),
                "official", "Voting Districts, Minnesota (Secretary of State), the kit's copy of 2026-10-01"),
               ("mn-school-district-shapes", (SCHOOLS, "https://enterprise.gisdata.mn.gov/aghost/rest/services/us_mn_state_mde/bdry_school_district_boundaries/FeatureServer/0"),
                "official", "School district boundaries 2025-26 (Department of Education), the kit's copy of 2026-10-01")]
    rows = []
    for name, (path, url), kind, note in inputs:
        rows.append({"input": name, "source": f"{url} (file {os.path.relpath(path, HERE)})", "sha256": sha_file(path),
                     "as_of": __import__("datetime").datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d"), "kind": kind, "note": note})
    return {"units": feats, "controls": controls, "inputs": rows, "method": CENSUS_METHOD, "vtd2020": vtd}


# ---------------------------------------------------------------- self-test

def selftest(say=print):
    ok = True

    def check(what, got, want):
        nonlocal ok
        good = (abs(got - want) < 1e-6) if isinstance(want, float) else got == want
        ok &= good
        say(f"    {'ok ' if good else 'BAD'} {what}: {got!r}" + ("" if good else f" (expected {want!r})"))
    sq = [[(0, 0), (2, 0), (2, 2), (0, 2)], [(0.5, 0.5), (1, 0.5), (1, 1), (0.5, 1)]]          # a square with a hole
    S = Shapes([("A", sq), ("B", [[(2, 0), (4, 0), (4, 2), (2, 2)]])], cell=1.0, bands=8)
    check("a point in the square", S.find(1.5, 1.5), "A")
    check("a point in the hole", S.find(0.75, 0.75), None)
    check("a point in the next square", S.find(3, 1), "B")
    check("nearest edge for a point outside", S.nearest(4.05, 1.0), "B")
    blocks = [["270010001001000", 60, 20, 100, 1.5, 1.5], ["270010001001001", 40, 20, 100, 3, 1], ["270010001002000", 0, 0, 50, 3, 1.5]]
    assigned = {"270010001001000": ["A", "S1", "inside"], "270010001001001": ["B", "S1", "inside"], "270010001002000": ["B", "S1", "inside"]}
    t = {k: ({}, None) for k in CELLS}
    t["b01003"] = ({"270010001001": {"001": (110.0, 30.0)}, "270010001002": {"001": (10.0, 8.0)}}, {"001": (120.0, 0.0)})
    units, acs_in, left = carry(blocks, assigned, t, {})
    check("people shared by 2020 population (A)", units["precinct"]["A"]["_parts"]["b01003_001"][0], 66.0)
    check("an empty block group shared by land area (B)", units["precinct"]["B"]["_parts"]["b01003_001"][0], 44.0 + 10.0)
    check("a part's margin goes with its share", math.sqrt(units["precinct"]["A"]["_parts"]["b01003_001"][1]), 18.0)
    check("margins of two block groups add as squares (B)", round(math.sqrt(units["precinct"]["B"]["_parts"]["b01003_001"][1]), 6),
          round(math.sqrt(12.0 ** 2 + 8.0 ** 2), 6))
    p, m = moe_share(3.0, 1.0, 10.0, 2.0)
    check("handbook proportion formula", round(m, 6), round(math.sqrt(1 - 0.09 * 4) / 10, 6))
    return ok


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        sys.exit(0 if selftest() else 1)
    doc = build()
    for k, v in doc["controls"].items():
        print(f"    control {k}: {v}")


if __name__ == "__main__":
    main()
