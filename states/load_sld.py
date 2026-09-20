#!/usr/bin/env python3
"""
states/load_sld.py
==================
A state's legislative district lines, upper and lower chamber, from the Census Bureau's cartographic boundary
files (cb_<year>_<fips>_sldu_500k and ..._sldl_500k; a few hundred KB each, no account).

Every shape is projected into the same 975x610 Albers USA space the federal maps use, so the page's existing
"where am I" arithmetic (project the point, test which shape holds it) works unchanged, and a state's districts sit
exactly inside the state outline the site already has. State districts are far smaller than congressional ones, a
few city blocks in places, so the lines are kept much finer than the federal file: simplified to about 25 metres
and stored to 1/400 of a map pixel (about 12 metres).

    python -m states.load_sld --place mn --out state_mn_districts.json
"""

import argparse
import datetime as dt
import io
import json
import os
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from albers_usa import AlbersUsa                     # noqa: E402
from load_districts import simplify, ring_area       # noqa: E402
from states import net                               # noqa: E402
from states.places import place                      # noqa: E402

YEARS = (2024, 2023)
Q = 400


def encode_ring(points, q):
    if points[0] == points[-1]:
        points = points[:-1]
    out, lx, ly = [], 0, 0
    for x, y in points:
        qx, qy = round(x * q), round(y * q)
        if out and qx == lx and qy == ly:
            continue
        out += [qx - lx, qy - ly]
        lx, ly = qx, qy
    return out


def district_name(code):
    """Census writes 01A and 062; the roster writes 1A and 62."""
    code = (code or "").strip()
    return code.lstrip("0") or "0"


def read_chamber(path, field, proj, tol):
    import shapefile                                   # pyshp
    z = zipfile.ZipFile(path)
    base = next(n[:-4] for n in z.namelist() if n.endswith(".shp"))
    rdr = shapefile.Reader(shp=io.BytesIO(z.read(base + ".shp")), dbf=io.BytesIO(z.read(base + ".dbf")), shx=io.BytesIO(z.read(base + ".shx")))
    fields = [f[0] for f in rdr.fields[1:]]
    out, points = {}, 0
    for sr in rdr.iterShapeRecords():
        rec = dict(zip(fields, sr.record))
        code = str(rec.get(field) or "")
        if not code or code.upper().startswith("ZZ"):      # ZZZ is water, or land in no district
            continue
        geom = sr.shape.__geo_interface__
        polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
        rings = []
        for poly in polys:
            for ring in poly:
                pts = [proj(lon, lat) for lon, lat in ring]
                pts = [p for p in pts if p]
                pts = simplify(pts, tol)
                if len(pts) >= 4:
                    rings.append((ring_area(pts), pts))
        if not rings:
            continue
        biggest = max(a for a, _ in rings)
        kept = [encode_ring(p, Q) for a, p in rings if a >= 0.0004 or a == biggest]
        points += sum(len(r) // 2 for r in kept)
        out[district_name(code)] = kept
    return out, points


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--place", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--cache-dir", default="states_cache")
    ap.add_argument("--tolerance", type=float, default=0.006, help="simplification, in map pixels (one pixel is about 4.6 km)")
    args = ap.parse_args()
    P = place(args.place)
    proj = AlbersUsa()
    result = {"q": Q, "upper": {}, "lower": {}, "vintage": ""}
    for chamber, stem, field in (("upper", "sldu", "SLDUST"), ("lower", "sldl", "SLDLST")):
        if not P.get(chamber):
            continue
        for year in YEARS:
            name = f"cb_{year}_{P['fips']}_{stem}_500k.zip"
            path = os.path.join(args.cache_dir, "census", name)
            try:
                if net.download(f"https://www2.census.gov/geo/tiger/GENZ{year}/shp/{name}", path, 180):
                    print(f"    fetched {name} ({os.path.getsize(path) / 1e3:,.0f} KB)")
                shapes, points = read_chamber(path, field, lambda lon, lat: proj(lon, lat), args.tolerance)
            except Exception as e:  # noqa: BLE001
                print(f"    {name}: {e}")
                continue
            result[chamber] = shapes
            result["vintage"] = f"{year} Census Bureau cartographic boundary files"
            print(f"    {P[chamber]['name']}: {len(shapes):,} districts ({P[chamber]['seats']} seats), {points:,} points")
            break
    result["generated"] = dt.date.today().isoformat()
    text = json.dumps(result, separators=(",", ":"))
    with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print(f"    Wrote {args.out}: {len(text) / 1e3:,.0f} KB")


if __name__ == "__main__":
    main()
