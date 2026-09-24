#!/usr/bin/env python3
"""
district_shapes.py
==================
The first "lens" on the district maps: how compact each district's shape is, measured the same way for every
district from the Census Bureau's own boundary file. It measures; it never says why a district has the shape it has.

    python district_shapes.py                       # the 119th Congress: writes us_district_shapes.json and .csv
    python district_shapes.py --state mn            # Minnesota's Senate and House districts: state_mn_shapes.json and .csv
    python district_shapes.py --selftest            # checks the geometry against shapes whose answers are known

SOURCE (primary, official): U.S. Census Bureau cartographic boundary files, 1:500,000, clipped to the shoreline:
cb_2024_us_cd119_500k (the 119th Congress, kept in district_cache/ by the districts stage) and, for a state,
cb_2024_<fips>_sldu_500k and _sldl_500k (its upper and lower chambers, kept in states_cache/census/ by the state
districts stage). Each file's SHA-256 is recorded with the results, so anyone can confirm they measured the same file.

MEASURES (each published, each reproducible from the file alone):
  Polsby-Popper   4 * pi * area / perimeter^2. The district's area over the area of a circle with the same
                  perimeter; 1 is a circle. Polsby & Popper, Yale Law & Policy Review 9 (1991) 301.
  Reock           area / area of the smallest circle that contains the district; 1 is a circle.
                  Reock, Midwest Journal of Political Science 5 (1961) 70.
  Convex hull     area / area of the smallest convex shape that contains the district; 1 has no indentations.
                  Niemi, Grofman, Carlucci & Hofeller, Journal of Politics 52 (1990) 1155.

GEOMETRY (no map projection is chosen for area or perimeter, so there is none to argue with):
  area            on the GRS80 ellipsoid, exactly: every point's latitude is converted to authalic latitude and the
                  district is laid on a Lambert azimuthal equal-area plane centred on itself, where areas are true
                  (Snyder, Map Projections: A Working Manual, USGS Professional Paper 1395, 1987, pp. 16 and 182).
  perimeter       the sum of geodesic lengths of every boundary segment on GRS80, by Vincenty's inverse formula
                  (Vincenty, Survey Review 23 (1975) 88). Islands and holes count: their edges are boundary too.
  circle, hull    found in that same equal-area plane (Welzl's algorithm; Andrew's monotone chain). That plane keeps
                  areas true but not shapes: it stretches them by at most 0.11 percent one way and shrinks them as much
                  the other (the price of exact areas on a flattened Earth), so a perfect circle scores 0.998 on Reock
                  at the equator and 0.999 at 45 degrees north rather than 1.000. Away from a very large district's
                  centre the plane bends shapes further; for Alaska that is about 1 percent. Both effects are far
                  smaller than the difference between boundary files (see LIMITS).

CONTROL: the file carries the Bureau's own land and water areas for each district (ALAND, AWATER). The run reports
how far this module's areas fall from ALAND + AWATER. They differ where the Bureau counts coastal water that the
shoreline-clipped shape leaves out, and otherwise agree closely; the comparison is written to the results.

LIMITS, stated on the page as well: a jagged coast or river lowers a score through no one's choice; so do state
borders; a 1:500,000 boundary is smoother than the legal line, so scores here run a little higher than ones taken
from full-detail lines, and scores from different sources should not be mixed; districts drawn to comply with the
Voting Rights Act, or to follow city and county lines, may score low for that reason; an at-large district is the
whole state and was drawn by no one. A low score is a fact about a shape, not a finding about intent.
"""

import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import math
import os
import random
import re
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
METHOD_VERSION = "shapes-1.0"

# GRS80, the ellipsoid of NAD83, which is what the Census Bureau's files are in
A_AXIS = 6378137.0
FLAT = 1 / 298.257222101
E2 = FLAT * (2 - FLAT)
ECC = math.sqrt(E2)
B_AXIS = A_AXIS * (1 - FLAT)

FIPS = {"01": "AL", "02": "AK", "04": "AZ", "05": "AR", "06": "CA", "08": "CO", "09": "CT", "10": "DE", "11": "DC", "12": "FL",
        "13": "GA", "15": "HI", "16": "ID", "17": "IL", "18": "IN", "19": "IA", "20": "KS", "21": "KY", "22": "LA", "23": "ME",
        "24": "MD", "25": "MA", "26": "MI", "27": "MN", "28": "MS", "29": "MO", "30": "MT", "31": "NE", "32": "NV", "33": "NH",
        "34": "NJ", "35": "NM", "36": "NY", "37": "NC", "38": "ND", "39": "OH", "40": "OK", "41": "OR", "42": "PA", "44": "RI",
        "45": "SC", "46": "SD", "47": "TN", "48": "TX", "49": "UT", "50": "VT", "51": "VA", "53": "WA", "54": "WV", "55": "WI", "56": "WY"}


def _q(sin_phi):
    """Snyder (3-12): the quantity from which authalic latitude is found."""
    es = ECC * sin_phi
    return (1 - E2) * (sin_phi / (1 - es * es) - (1 / (2 * ECC)) * math.log((1 - es) / (1 + es)))


Q_POLE = _q(1.0)
R_AUTHALIC = A_AXIS * math.sqrt(Q_POLE / 2)               # 6,371,007.2 m: the sphere with the ellipsoid's surface area


def authalic(lat_deg):
    """Geodetic latitude (degrees) to authalic latitude (radians): Snyder (3-11). Areas on the authalic sphere equal
    areas on the ellipsoid."""
    return math.asin(max(-1.0, min(1.0, _q(math.sin(math.radians(lat_deg))) / Q_POLE)))


def vincenty(lon1, lat1, lon2, lat2):
    """Geodesic distance in metres on GRS80 (Vincenty 1975, inverse). Boundary segments are short, so it converges in
    a few rounds; for the rare nearly antipodal pair it falls back to the authalic great circle."""
    if lon1 == lon2 and lat1 == lat2:
        return 0.0
    u1 = math.atan((1 - FLAT) * math.tan(math.radians(lat1)))
    u2 = math.atan((1 - FLAT) * math.tan(math.radians(lat2)))
    big_l = math.radians(lon2 - lon1)
    if big_l > math.pi:
        big_l -= 2 * math.pi
    elif big_l < -math.pi:
        big_l += 2 * math.pi
    su1, cu1, su2, cu2 = math.sin(u1), math.cos(u1), math.sin(u2), math.cos(u2)
    lam = big_l
    for _ in range(60):
        sl, cl = math.sin(lam), math.cos(lam)
        sin_sigma = math.hypot(cu2 * sl, cu1 * su2 - su1 * cu2 * cl)
        if sin_sigma == 0:
            return 0.0
        cos_sigma = su1 * su2 + cu1 * cu2 * cl
        sigma = math.atan2(sin_sigma, cos_sigma)
        sin_alpha = cu1 * cu2 * sl / sin_sigma
        cos2_alpha = 1 - sin_alpha * sin_alpha
        cos_2sm = cos_sigma - 2 * su1 * su2 / cos2_alpha if cos2_alpha else 0.0
        c = FLAT / 16 * cos2_alpha * (4 + FLAT * (4 - 3 * cos2_alpha))
        new = big_l + (1 - c) * FLAT * sin_alpha * (sigma + c * sin_sigma * (cos_2sm + c * cos_sigma * (-1 + 2 * cos_2sm * cos_2sm)))
        if abs(new - lam) < 1e-12:
            lam = new
            break
        lam = new
    else:                                                  # did not settle: nearly antipodal, which a district edge never is
        b1, b2 = authalic(lat1), authalic(lat2)
        h = math.sin((b2 - b1) / 2) ** 2 + math.cos(b1) * math.cos(b2) * math.sin(big_l / 2) ** 2
        return 2 * R_AUTHALIC * math.asin(min(1.0, math.sqrt(h)))
    usq = cos2_alpha * (A_AXIS * A_AXIS - B_AXIS * B_AXIS) / (B_AXIS * B_AXIS)
    big_a = 1 + usq / 16384 * (4096 + usq * (-768 + usq * (320 - 175 * usq)))
    big_b = usq / 1024 * (256 + usq * (-128 + usq * (74 - 47 * usq)))
    d_sigma = big_b * sin_sigma * (cos_2sm + big_b / 4 * (cos_sigma * (-1 + 2 * cos_2sm * cos_2sm)
                                                          - big_b / 6 * cos_2sm * (-3 + 4 * sin_sigma * sin_sigma) * (-3 + 4 * cos_2sm * cos_2sm)))
    return B_AXIS * big_a * (sigma - d_sigma)


def centre_of(rings):
    """Where to centre the equal-area plane: the mean direction of the vertices, as a point on the globe. (A plain
    average of longitudes would fail for Alaska, whose islands cross the 180th meridian.)"""
    x = y = z = 0.0
    for ring in rings:
        for lon, lat in ring:
            la, lo = math.radians(lat), math.radians(lon)
            x += math.cos(la) * math.cos(lo)
            y += math.cos(la) * math.sin(lo)
            z += math.sin(la)
    return math.degrees(math.atan2(y, x)), math.degrees(math.atan2(z, math.hypot(x, y)))


def equal_area_plane(rings, centre):
    """Lambert azimuthal equal-area, authalic sphere, centred on the district: Snyder (24-2) to (24-4). Metres."""
    lon0, b0 = math.radians(centre[0]), authalic(centre[1])
    sb0, cb0 = math.sin(b0), math.cos(b0)
    out = []
    for ring in rings:
        pts = []
        for lon, lat in ring:
            b, dl = authalic(lat), math.radians(lon) - lon0
            sb, cb, cdl = math.sin(b), math.cos(b), math.cos(dl)
            k = math.sqrt(2 / (1 + sb0 * sb + cb0 * cb * cdl))
            pts.append((R_AUTHALIC * k * cb * math.sin(dl), R_AUTHALIC * k * (cb0 * sb - sb0 * cb * cdl)))
        out.append(pts)
    return out


def signed_area(pts):
    s = 0.0
    for i in range(len(pts)):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % len(pts)]
        s += x1 * y2 - x2 * y1
    return s / 2


def convex_hull(points):
    """Andrew's monotone chain."""
    pts = sorted(set(points))
    if len(pts) < 3:
        return pts
    cross = lambda o, a, b: (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def enclosing_circle(points):
    """The smallest circle containing every point (Welzl 1991, the iterative form). The shuffle only sets the order
    of the work; the circle it finds is the same one whatever the order, and the seed is fixed regardless."""
    pts = list(points)
    random.Random(20260920).shuffle(pts)

    def inside(c, p):
        return c is not None and math.hypot(p[0] - c[0], p[1] - c[1]) <= c[2] * (1 + 1e-12) + 1e-9

    def two(a, b):
        return ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, math.hypot(a[0] - b[0], a[1] - b[1]) / 2)

    def three(a, b, c):
        ox, oy = (min(a[0], b[0], c[0]) + max(a[0], b[0], c[0])) / 2, (min(a[1], b[1], c[1]) + max(a[1], b[1], c[1])) / 2
        ax, ay, bx, by, cx, cy = a[0] - ox, a[1] - oy, b[0] - ox, b[1] - oy, c[0] - ox, c[1] - oy
        d = (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by)) * 2
        if d == 0:
            return None
        x = ox + ((ax * ax + ay * ay) * (by - cy) + (bx * bx + by * by) * (cy - ay) + (cx * cx + cy * cy) * (ay - by)) / d
        y = oy + ((ax * ax + ay * ay) * (cx - bx) + (bx * bx + by * by) * (ax - cx) + (cx * cx + cy * cy) * (bx - ax)) / d
        return (x, y, max(math.hypot(x - p[0], y - p[1]) for p in (a, b, c)))

    c = None
    for i, p in enumerate(pts):
        if inside(c, p):
            continue
        c = (p[0], p[1], 0.0)
        for j in range(i):
            q = pts[j]
            if inside(c, q):
                continue
            c = two(p, q)
            for k in range(j):
                r = pts[k]
                if not inside(c, r):
                    t = three(p, q, r)
                    c = t if t is not None else max((two(p, q), two(p, r), two(q, r)), key=lambda z: z[2])
    return c


def measure(rings):
    """rings: every ring of the district (outer edges, islands and holes), each a list of (longitude, latitude)
    in degrees as the Census file gives them, clockwise for an outer edge and counter-clockwise for a hole."""
    plane = equal_area_plane(rings, centre_of(rings))
    area = abs(sum(signed_area(r) for r in plane))
    perimeter = 0.0
    for ring in rings:
        for i in range(len(ring) - 1):
            perimeter += vincenty(ring[i][0], ring[i][1], ring[i + 1][0], ring[i + 1][1])
        if ring and ring[0] != ring[-1]:
            perimeter += vincenty(ring[-1][0], ring[-1][1], ring[0][0], ring[0][1])
    hull = convex_hull([p for r in plane for p in r])
    hull_area = abs(signed_area(hull)) if len(hull) >= 3 else 0.0
    circle = enclosing_circle(hull)
    circle_area = math.pi * circle[2] ** 2 if circle else 0.0
    return {"area_m2": area, "perimeter_m": perimeter,
            "polsby_popper": 4 * math.pi * area / (perimeter * perimeter) if perimeter else None,
            "reock": area / circle_area if circle_area else None,
            "hull": area / hull_area if hull_area else None,
            "parts": len([r for r in plane if signed_area(r) < 0]) or 1}


def read_census(zip_path, fields):
    """Yield (attributes, rings) for every shape in a Census cartographic boundary ZIP."""
    try:
        import shapefile                                    # pyshp
    except ImportError:
        sys.exit("pyshp is missing; run: python run_all.py check")
    z = zipfile.ZipFile(zip_path)
    base = next(n[:-4] for n in z.namelist() if n.endswith(".shp"))
    rdr = shapefile.Reader(shp=io.BytesIO(z.read(base + ".shp")), dbf=io.BytesIO(z.read(base + ".dbf")), shx=io.BytesIO(z.read(base + ".shx")))
    names = [f[0] for f in rdr.fields[1:]]
    for sr in rdr.iterShapeRecords():
        rec = dict(zip(names, sr.record))
        pts, parts = sr.shape.points, list(sr.shape.parts) + [len(sr.shape.points)]
        rings = [[(float(x), float(y)) for x, y in pts[parts[i]:parts[i + 1]]] for i in range(len(parts) - 1)]
        yield {k: rec.get(k) for k in fields}, [r for r in rings if len(r) >= 4]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def quantiles(values):
    v = sorted(values)
    at = lambda p: v[min(len(v) - 1, max(0, round(p * (len(v) - 1))))]
    return {"min": v[0], "q1": at(.25), "median": at(.5), "q3": at(.75), "max": v[-1], "n": len(v)} if v else {}


def fields_of(m, official):
    """The measured fields of one district, the same at every level of government."""
    return {"pp": round(m["polsby_popper"], 4), "reock": round(m["reock"], 4), "hull": round(m["hull"], 4),
            "area_sqmi": round(m["area_m2"] / 2589988.110336, 1), "perim_mi": round(m["perimeter_m"] / 1609.344, 1), "parts": m["parts"],
            "census_area_sqmi": round(official / 2589988.110336, 1),
            "area_vs_census": round(m["area_m2"] / official, 4) if official else None,
            # Shoreline, by an objective test: the Bureau's land + water area is more than 1.5% larger than the
            # shoreline-clipped shape, which happens where a district fronts the sea, a bay or the Great Lakes.
            # A jagged natural shore lowers a perimeter score through no one's choice, so the page marks these.
            "shore": bool(official and m["area_m2"] / official < .985)}


def congress(zip_path, congress_no=119):
    field = f"CD{congress_no}FP"
    rows = []
    for rec, rings in read_census(zip_path, ("STATEFP", field, "NAMELSAD", "ALAND", "AWATER", "GEOID")):
        st, code = FIPS.get(str(rec["STATEFP"])), str(rec[field] or "")
        if not st or st == "DC" or not code.isdigit() or code in ("98", "99"):      # delegates' districts and undefined areas are whole jurisdictions, not drawn districts
            continue
        m = measure(rings)
        official = float(rec["ALAND"] or 0) + float(rec["AWATER"] or 0)
        rows.append(dict({"key": f"{st}-{int(code) if int(code) else 'AL'}", "st": st, "d": int(code), "name": rec["NAMELSAD"], "at_large": int(code) == 0},
                         **fields_of(m, official)))
    rows.sort(key=lambda r: (r["st"], r["d"]))
    return rows


def natural(d):
    m = re.match(r"^(\d+)(.*)$", str(d))
    return (int(m.group(1)), m.group(2)) if m else (10 ** 9, str(d))


def chamber(zip_path, field):
    """Every district of one state legislative chamber in its Census file (upper chamber: field SLDUST; lower:
    SLDLST). The keys are the district names the site uses: the Census writes 01A and 062, the roster 1A and 62."""
    rows = []
    for rec, rings in read_census(zip_path, ("STATEFP", field, "NAMELSAD", "ALAND", "AWATER", "GEOID")):
        code = str(rec[field] or "").strip()
        if not code or code.upper().startswith("ZZ"):          # ZZZ is water, or land that lies in no district
            continue
        name = code.lstrip("0") or "0"
        m = measure(rings)
        official = float(rec["ALAND"] or 0) + float(rec["AWATER"] or 0)
        rows.append(dict({"key": name, "d": name, "name": rec["NAMELSAD"], "at_large": False}, **fields_of(m, official)))
    rows.sort(key=lambda r: natural(r["d"]))
    return rows


def pack(rows, zip_path):
    """The results for one file: where it came from and its fingerprint, the summary, the control against the
    Bureau's own areas, and every district."""
    drawn = [r for r in rows if not r["at_large"]]
    ratios = sorted(r["area_vs_census"] for r in rows if r["area_vs_census"])
    near = sum(1 for x in ratios if abs(x - 1) <= .01)
    name = os.path.basename(zip_path)
    year = re.search(r"cb_(\d{4})_", name)
    return {"source": {"publisher": "U.S. Census Bureau", "product": "Cartographic Boundary Files, 1:500,000", "file": name,
                       "url": f"https://www2.census.gov/geo/tiger/GENZ{year.group(1) if year else '2024'}/shp/{name}",
                       "sha256": sha256(zip_path), "bytes": os.path.getsize(zip_path),
                       "fetched": dt.date.fromtimestamp(os.path.getmtime(zip_path)).isoformat()},
            "summary": {"districts": len(rows), "drawn": len(drawn), "at_large": len(rows) - len(drawn), "shore": sum(1 for r in drawn if r["shore"]),
                        "inland": {k: quantiles([r[k] for r in drawn if not r["shore"]]) for k in ("pp", "reock", "hull")},
                        "pp": quantiles([r["pp"] for r in drawn]), "reock": quantiles([r["reock"] for r in drawn]), "hull": quantiles([r["hull"] for r in drawn])},
            "control": {"compared": len(ratios), "within_1_percent": near, "median_ratio": ratios[len(ratios) // 2] if ratios else None,
                        "lowest": sorted(((r["area_vs_census"], r["key"]) for r in rows if r["area_vs_census"]))[:8]},
            "districts": rows}


def report(p, what):
    s, c = p["summary"], p["control"]
    print(f"  {what}: {s['districts']} districts" + (f" ({s['at_large']} at large)" if s["at_large"] else "")
          + (f". Medians: Polsby-Popper {s['pp']['median']:.3f}, Reock {s['reock']['median']:.3f}, convex hull {s['hull']['median']:.3f}" if s["drawn"] else ""))
    low = [(v, k) for v, k in c["lowest"] if v < .985]
    print(f"  Control: {c['within_1_percent']} of {c['compared']} areas within 1% of the Bureau's own land + water area; median ratio {c['median_ratio']:.4f}; "
          + (f"{s['shore']} marked shoreline, the furthest below: " + ", ".join(f"{k} {v:.2f}" for v, k in low[:5]) if s["shore"]
             else "no district more than 1.5% below, so none is marked shoreline"))
    print(f"  Source file {p['source']['file']}, SHA-256 {p['source']['sha256'][:16]}...")


CSV_HEAD = ["census_name", "at_large", "polsby_popper", "reock", "convex_hull", "area_sq_mi", "perimeter_mi", "parts",
            "census_land_plus_water_sq_mi", "area_over_census_area", "shoreline"]


def csv_tail(r):
    return [r["name"], int(r["at_large"]), r["pp"], r["reock"], r["hull"], r["area_sqmi"], r["perim_mi"], r["parts"],
            r["census_area_sqmi"], r["area_vs_census"], int(r["shore"])]


def selftest():
    """Shapes whose answers are known: a small circle and a small square on the equator and at 60 degrees north, and a
    one-degree cell whose area the ellipsoid formulas give in closed form."""
    ok = True

    def direct(lon1, lat1, azimuth, dist):
        """Vincenty's direct formula: the point `dist` metres from (lon1, lat1) along the geodesic leaving at `azimuth`."""
        a1, u1 = math.radians(azimuth), math.atan((1 - FLAT) * math.tan(math.radians(lat1)))
        sa1, ca1, su1, cu1 = math.sin(a1), math.cos(a1), math.sin(u1), math.cos(u1)
        sigma1 = math.atan2(math.tan(u1), ca1)
        sin_alpha = cu1 * sa1
        cos2_alpha = 1 - sin_alpha ** 2
        usq = cos2_alpha * (A_AXIS ** 2 - B_AXIS ** 2) / B_AXIS ** 2
        big_a = 1 + usq / 16384 * (4096 + usq * (-768 + usq * (320 - 175 * usq)))
        big_b = usq / 1024 * (256 + usq * (-128 + usq * (74 - 47 * usq)))
        sigma = dist / (B_AXIS * big_a)
        for _ in range(60):
            cos_2sm, ss, cs = math.cos(2 * sigma1 + sigma), math.sin(sigma), math.cos(sigma)
            d_sigma = big_b * ss * (cos_2sm + big_b / 4 * (cs * (-1 + 2 * cos_2sm ** 2) - big_b / 6 * cos_2sm * (-3 + 4 * ss ** 2) * (-3 + 4 * cos_2sm ** 2)))
            new = dist / (B_AXIS * big_a) + d_sigma
            if abs(new - sigma) < 1e-13:
                sigma = new
                break
            sigma = new
        cos_2sm, ss, cs = math.cos(2 * sigma1 + sigma), math.sin(sigma), math.cos(sigma)
        lat2 = math.atan2(su1 * cs + cu1 * ss * ca1, (1 - FLAT) * math.hypot(sin_alpha, su1 * ss - cu1 * cs * ca1))
        lam = math.atan2(ss * sa1, cu1 * cs - su1 * ss * ca1)
        c = FLAT / 16 * cos2_alpha * (4 + FLAT * (4 - 3 * cos2_alpha))
        big_l = lam - (1 - c) * FLAT * sin_alpha * (sigma + c * ss * (cos_2sm + c * cs * (-1 + 2 * cos_2sm ** 2)))
        return lon1 + math.degrees(big_l), math.degrees(lat2)

    def ring_circle(lon0, lat0, radius_m, n=720):
        """Every point exactly radius_m from the centre along a geodesic: a true circle on the ellipsoid. Clockwise,
        as the Census writes an outer edge."""
        return [direct(lon0, lat0, 360.0 * i / n, radius_m) for i in range(n + 1)]
    for lat0 in (0.0, 45.0, 60.0):
        m = measure([ring_circle(-93.0, lat0, 20000.0)])
        # The equal-area plane keeps areas true but not shapes: along a parallel it stretches by k and along a meridian
        # it shrinks by 1/k, so a true circle becomes an ellipse there and its enclosing circle is k times too wide.
        # k is known exactly, so the test demands exactly the Reock that follows from it (0.9978 at the equator).
        n_rad = A_AXIS / math.sqrt(1 - E2 * math.sin(math.radians(lat0)) ** 2)
        k = n_rad * math.cos(math.radians(lat0)) / (R_AUTHALIC * math.cos(authalic(lat0)))
        expect = 1 / max(k, 1 / k) ** 2
        good = abs(m["polsby_popper"] - 1) < 1e-4 and abs(m["reock"] - expect) < 3e-4 and abs(m["hull"] - 1) < 1e-3 and abs(m["area_m2"] / (math.pi * 20000.0 ** 2) - 1) < 1e-4
        print(f"  circle, 20 km, at {lat0:>4} N: Polsby-Popper {m['polsby_popper']:.4f}, Reock {m['reock']:.4f} (the plane's known stretch gives {expect:.4f}), "
              f"hull {m['hull']:.4f}, area/true {m['area_m2'] / (math.pi * 4e8):.5f}  {'ok' if good else 'WRONG'}")
        ok &= good
    # a geodesic-sided near-square: Polsby-Popper of a square is pi/4 = 0.7854, Reock 2/pi = 0.6366, hull 1
    side = 0.2
    sq = [(-93.0, 45.0), (-93.0, 45.0 + side * .7071), (-93.0 + side, 45.0 + side * .7071), (-93.0 + side, 45.0), (-93.0, 45.0)]
    m = measure([sq])
    w = vincenty(-93.0, 45.0, -93.0 + side, 45.0)
    hgt = vincenty(-93.0, 45.0, -93.0, 45.0 + side * .7071)
    expect_pp = 4 * math.pi * (w * hgt) / (2 * (w + hgt)) ** 2
    good = abs(m["polsby_popper"] - expect_pp) < 3e-3 and abs(m["hull"] - 1) < 1e-3
    print(f"  rectangle {w / 1000:.1f} by {hgt / 1000:.1f} km: Polsby-Popper {m['polsby_popper']:.4f} (a flat rectangle gives {expect_pp:.4f}), hull {m['hull']:.4f}  {'ok' if good else 'WRONG'}")
    ok &= good
    # a one-degree cell, 44 to 45 N: its ellipsoidal area in closed form is R_q^2 * dlon * (sin b2 - sin b1)
    cell = [(-94.0, 44.0), (-94.0, 45.0), (-93.0, 45.0), (-93.0, 44.0), (-94.0, 44.0)]
    dense = []
    for (x1, y1), (x2, y2) in zip(cell, cell[1:]):
        dense += [(x1 + (x2 - x1) * i / 200, y1 + (y2 - y1) * i / 200) for i in range(200)]
    dense.append(cell[0])
    exact = R_AUTHALIC ** 2 * math.radians(1.0) * (math.sin(authalic(45.0)) - math.sin(authalic(44.0)))
    got = measure([dense])["area_m2"]
    good = abs(got / exact - 1) < 1e-6
    print(f"  one-degree cell, 44 to 45 N: {got / 1e6:,.3f} sq km against {exact / 1e6:,.3f} in closed form ({(got / exact - 1) * 100:+.5f} %)  {'ok' if good else 'WRONG'}")
    ok &= good
    # a known geodesic: one degree of longitude on the equator is a * pi / 180
    got, exact = vincenty(0, 0, 1, 0), A_AXIS * math.pi / 180
    good = abs(got - exact) < 1e-3
    print(f"  one degree along the equator: {got:,.3f} m against {exact:,.3f} m  {'ok' if good else 'WRONG'}")
    ok &= good
    print("  authalic radius:", f"{R_AUTHALIC:,.1f} m (published: 6,371,007.2 m)")
    return ok and abs(R_AUTHALIC - 6371007.2) < 1


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--zip", default=os.path.join(HERE, "district_cache", "cb_2024_us_cd119_500k.zip"))
    ap.add_argument("--congress", type=int, default=119)
    ap.add_argument("--out", default=os.path.join(HERE, "us_district_shapes.json"))
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--state", default="", help="a state's two-letter code from states/places.py: measure its legislative chambers instead of Congress")
    args = ap.parse_args()
    if args.selftest:
        good = selftest()
        print("Self-test passed." if good else "SELF-TEST FAILED.")
        return 0 if good else 1
    if args.state:
        return state(args.state)
    if not os.path.exists(args.zip):
        sys.exit(f"{args.zip} is not there. Run: python run_all.py districts")
    print(f"Measuring every district of the {args.congress}th Congress in {os.path.basename(args.zip)} ...")
    out = dict({"method": METHOD_VERSION, "generated": dt.date.today().isoformat(), "congress": args.congress}, **pack(congress(args.zip, args.congress), args.zip))
    with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, separators=(",", ":"))
    with open(os.path.splitext(args.out)[0] + ".csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["district", "state", "number"] + CSV_HEAD)
        for r in out["districts"]:
            w.writerow([r["key"], r["st"], r["d"]] + csv_tail(r))
    report(out, f"The {args.congress}th Congress")
    print(f"  Wrote {args.out} and its .csv")
    return 0


def state(code):
    """A state's legislative chambers, from the Census files the state districts stage keeps: state_<code>_shapes.json and .csv."""
    sys.path.insert(0, HERE)
    from states.places import place
    P = place(code)
    code = P["code"].lower()
    chambers, csv_rows = {}, []
    for key, stem, field in (("upper", "sldu", "SLDUST"), ("lower", "sldl", "SLDLST")):
        if not P.get(key):
            continue
        path = next((p for p in (os.path.join(HERE, "states_cache", "census", f"cb_{y}_{P['fips']}_{stem}_500k.zip") for y in (2024, 2023)) if os.path.exists(p)), None)
        if not path:
            sys.exit(f"No Census file for {P['name']}'s {P[key]['name']} districts in states_cache/census. Run: python run_states.py {code} districts")
        print(f"Measuring every {P[key]['name']} district of {P['name']} in {os.path.basename(path)} ...")
        packed = pack(chamber(path, field), path)
        packed["name"] = P[key]["name"]
        chambers[key] = packed
        csv_rows += [[P[key]["name"], r["key"]] + csv_tail(r) for r in packed["districts"]]
        report(packed, f"{P['name']} {P[key]['name']}")
    out = {"method": METHOD_VERSION, "generated": dt.date.today().isoformat(), "place": P["code"], "name": P["name"], "legislature": P["legislature"], "chambers": chambers}
    out_path = os.path.join(HERE, f"state_{code}_shapes.json")
    with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, separators=(",", ":"))
    with open(os.path.splitext(out_path)[0] + ".csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["chamber", "district"] + CSV_HEAD)
        w.writerows(csv_rows)
    print(f"  Wrote {out_path} and its .csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
