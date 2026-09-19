#!/usr/bin/env python3
"""
load_districts.py - House district boundaries for the vote map's zoom-in view.

    python load_districts.py                       # writes us_districts_albers.json next to this script
    python load_districts.py --out site_data/us_districts_albers.json --tolerance 0.15

Sources, tried in order:
  1. Census Bureau cartographic boundary files for the current Congress (cb_2024_us_cd119_500k, then cb_2023_us_cd118_500k).
     Needs the pyshp package (pip install pyshp). Blocked on some networks; then the loader falls back to:
  2. The unitedstates/districts project on GitHub: 2016 district lines (115th Congress), the last vintage it published.

Every shape is projected into the same 975x610 Albers USA space as the state map (so districts sit exactly inside their
state), simplified, quantized to 1/50 px and delta-encoded. At-large states are skipped: the site draws the state itself.
"""

import argparse
import datetime as dt
import io
import json
import os
import sys
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from albers_usa import AlbersUsa  # noqa: E402

UA = "Mozilla/5.0 (compatible; congress-catalog/1.0; personal legislative research)"
CENSUS = ["https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_cd119_500k.zip",
          "https://www2.census.gov/geo/tiger/GENZ2023/shp/cb_2023_us_cd118_500k.zip"]
GITHUB = "https://raw.githubusercontent.com/unitedstates/districts/gh-pages/cds/2016/{st}-{d}/shape.geojson"
FIPS = {"01": "AL", "02": "AK", "04": "AZ", "05": "AR", "06": "CA", "08": "CO", "09": "CT", "10": "DE", "12": "FL", "13": "GA", "15": "HI",
        "16": "ID", "17": "IL", "18": "IN", "19": "IA", "20": "KS", "21": "KY", "22": "LA", "23": "ME", "24": "MD", "25": "MA", "26": "MI",
        "27": "MN", "28": "MS", "29": "MO", "30": "MT", "31": "NE", "32": "NV", "33": "NH", "34": "NJ", "35": "NM", "36": "NY", "37": "NC",
        "38": "ND", "39": "OH", "40": "OK", "41": "OR", "42": "PA", "44": "RI", "45": "SC", "46": "SD", "47": "TN", "48": "TX", "49": "UT",
        "50": "VT", "51": "VA", "53": "WA", "54": "WV", "55": "WI", "56": "WY"}
STATES = sorted(FIPS.values())
AT_LARGE_2016 = {"AK", "DE", "MT", "ND", "SD", "VT", "WY"}
Q = 50  # quantization: 1/50 px in the 975x610 map space


def log(*a):
    print(*a, flush=True)


def http_get(url, timeout=120):
    return urlopen(Request(url, headers={"User-Agent": UA}), timeout=timeout).read()


# ----------------------------------------------------------------------------- geometry helpers
def simplify(points, tol):
    """Douglas-Peucker on a closed ring (list of (x, y)), tolerance in map px."""
    if len(points) < 5 or tol <= 0:
        return points
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        a, b = stack.pop()
        ax, ay = points[a]
        bx, by = points[b]
        dx, dy = bx - ax, by - ay
        L2 = dx * dx + dy * dy
        best, idx = 0.0, -1
        for i in range(a + 1, b):
            px, py = points[i]
            if L2 == 0:
                d = ((px - ax) ** 2 + (py - ay) ** 2) ** .5
            else:
                t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
                d = ((px - (ax + t * dx)) ** 2 + (py - (ay + t * dy)) ** 2) ** .5
            if d > best:
                best, idx = d, i
        if best > tol:
            keep[idx] = True
            stack.append((a, idx))
            stack.append((idx, b))
    return [p for p, k in zip(points, keep) if k]


def ring_area(points):
    a = 0.0
    for (x0, y0), (x1, y1) in zip(points, points[1:] + points[:1]):
        a += x0 * y1 - x1 * y0
    return abs(a) / 2


def encode_ring(points):
    """Quantize to 1/Q px and delta-encode: [x0, y0, dx1, dy1, ...] (closing point dropped)."""
    if points[0] == points[-1]:
        points = points[:-1]
    out, lx, ly = [], 0, 0
    for x, y in points:
        qx, qy = round(x * Q), round(y * Q)
        out += [qx - lx, qy - ly]
        lx, ly = qx, qy
    return out


def project_geometry(geom, proj, extent, tol):
    """GeoJSON geometry (lon/lat) -> list of encoded rings in map px, dropping slivers and rings outside the inset extent."""
    polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
    rings = []
    for poly in polys:
        for ring in poly:
            pts = [proj(lon, lat) for lon, lat in ring]
            if extent and not any(extent[0] <= x <= extent[2] and extent[1] <= y <= extent[3] for x, y in pts):
                continue
            pts = simplify(pts, tol)
            if len(pts) < 4:
                continue
            rings.append((ring_area(pts), pts))
    if not rings:
        return []
    biggest = max(a for a, _ in rings)
    return [encode_ring(p) for a, p in rings if a >= 0.4 or a == biggest]


# ----------------------------------------------------------------------------- sources
def from_census(cache_dir):
    try:
        import shapefile  # pyshp
    except ImportError:
        log("  pyshp is not installed; skipping the Census source (pip install pyshp)")
        return None, None
    for url in CENSUS:
        name = url.rsplit("/", 1)[-1]
        path = os.path.join(cache_dir, name)
        try:
            if not os.path.exists(path):
                log(f"  downloading {url}")
                data = http_get(url, timeout=300)
                with open(path, "wb") as fh:
                    fh.write(data)
            z = zipfile.ZipFile(path)
            base = next(n[:-4] for n in z.namelist() if n.endswith(".shp"))
            rdr = shapefile.Reader(shp=io.BytesIO(z.read(base + ".shp")), dbf=io.BytesIO(z.read(base + ".dbf")),
                                   shx=io.BytesIO(z.read(base + ".shx")))
            fields = [f[0] for f in rdr.fields[1:]]
            feats = []
            for sr in rdr.iterShapeRecords():
                rec = dict(zip(fields, sr.record))
                st = FIPS.get(str(rec.get("STATEFP", "")).zfill(2))
                cd = str(rec.get("CD119FP", rec.get("CD118FP", rec.get("CDFP", "")))).strip()
                if not st or not cd.isdigit():
                    continue
                d = int(cd)
                feats.append((st, d, sr.shape.__geo_interface__))
            return feats, f"{'119th' if 'cd119' in name else '118th'} Congress lines (Census Bureau {name})"
        except (HTTPError, URLError, TimeoutError, OSError, StopIteration) as e:
            log(f"  Census source unavailable: {e}")
    return None, None


def from_github(cache_dir, workers):
    log("  Using the 2016 district lines from unitedstates/districts (the current Census file was not reachable)")
    os.makedirs(cache_dir, exist_ok=True)

    def fetch(key):
        st, d = key
        path = os.path.join(cache_dir, f"{st}-{d}.geojson")
        if os.path.exists(path):
            return key, open(path, "rb").read()
        try:
            raw = http_get(GITHUB.format(st=st, d=d), timeout=60)
        except HTTPError as e:
            return key, None if e.code == 404 else b""
        except (URLError, TimeoutError, OSError):
            return key, b""
        with open(path, "wb") as fh:
            fh.write(raw)
        return key, raw

    feats, retry = [], []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for st in STATES:
            if st in AT_LARGE_2016:
                continue
            todo = [(st, d) for d in range(1, 56)]
            for (s, d), raw in pool.map(fetch, todo):
                if raw is None:
                    continue
                if raw == b"":
                    retry.append((s, d))
                    continue
                g = json.loads(raw)
                geom = g["features"][0]["geometry"] if g.get("type") == "FeatureCollection" else g.get("geometry", g)
                feats.append((s, d, geom))
    if retry:
        log(f"  {len(retry)} downloads failed; re-run to retry")
    return feats, "2016 district lines (unitedstates/districts, 115th Congress)"


# ----------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    here = os.path.dirname(os.path.abspath(__file__))
    ap.add_argument("--out", default=os.path.join(here, "us_districts_albers.json"))
    ap.add_argument("--cache-dir", default=os.path.join(here, "district_cache"))
    ap.add_argument("--tolerance", type=float, default=0.15, help="simplification tolerance in map px (975x610 space)")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--github-only", action="store_true", help="skip the Census download")
    args = ap.parse_args()
    os.makedirs(args.cache_dir, exist_ok=True)
    t0 = time.time()
    feats = vintage = None
    if not args.github_only:
        feats, vintage = from_census(args.cache_dir)
    if not feats:
        feats, vintage = from_github(args.cache_dir, args.workers)
    if not feats:
        sys.exit("No district shapes could be downloaded.")

    P = AlbersUsa()
    k, x, y = P.k, P.tx, P.ty
    extents = {"AK": (x - 0.425 * k, y + 0.120 * k, x - 0.214 * k, y + 0.234 * k),
               "HI": (x - 0.214 * k, y + 0.166 * k, x - 0.115 * k, y + 0.234 * k)}
    states = {}
    for st, d, geom in feats:
        rings = project_geometry(geom, P.by_state(st), extents.get(st), args.tolerance)
        if rings:
            states.setdefault(st, {})[str(d)] = rings
    # a state with a single district is at-large: the site draws the state shape itself
    for st in [s for s, ds in states.items() if len(ds) == 1]:
        del states[st]
    out = {"vintage": vintage, "generated": dt.date.today().isoformat(), "q": Q,
           "note": "Coordinates are in the 975x610 Albers USA map space; each ring is [x0, y0, dx, dy, ...] in 1/q px.",
           "states": states}
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, separators=(",", ":"))
    n = sum(len(v) for v in states.values())
    log(f"Wrote {args.out}: {n} districts in {len(states)} states, {os.path.getsize(args.out) / 1e6:.2f} MB, "
        f"{vintage}, in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
