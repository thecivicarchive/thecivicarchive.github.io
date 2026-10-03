#!/usr/bin/env python3
"""
states/load_counties.py
=======================
A state's county lines, from the Census Bureau's cartographic boundary file for the whole country
(cb_<year>_us_county_500k.zip, about 11 MB, no account), projected into the same 975x610 Albers USA space every map on
the site uses, so a county sits exactly inside the state outline the site already has and the page's "where am I"
arithmetic works unchanged.

    python -m states.load_counties --place mn --out local_mn_counties.json
"""

import argparse
import datetime as dt
import hashlib
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
from states.load_sld import encode_ring, Q           # noqa: E402

YEARS = (2024, 2023)


def read_counties(path, fips, proj, tol):
    import shapefile                                   # pyshp
    z = zipfile.ZipFile(path)
    base = next(n[:-4] for n in z.namelist() if n.endswith(".shp"))
    rdr = shapefile.Reader(shp=io.BytesIO(z.read(base + ".shp")), dbf=io.BytesIO(z.read(base + ".dbf")), shx=io.BytesIO(z.read(base + ".shx")))
    fields = [f[0] for f in rdr.fields[1:]]
    out, info, points = {}, {}, 0
    for sr in rdr.iterShapeRecords():
        rec = dict(zip(fields, sr.record))
        if str(rec.get("STATEFP")) != fips:
            continue
        code = str(rec.get("COUNTYFP"))
        info[code] = {"name": str(rec.get("NAME") or ""), "full": str(rec.get("NAMELSAD") or ""), "geoid": str(rec.get("GEOID") or ""),
                      "land": int(rec.get("ALAND") or 0), "water": int(rec.get("AWATER") or 0)}
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
        out[code] = kept
    return out, info, points


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--place", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--cache-dir", default="states_cache")
    ap.add_argument("--tolerance", type=float, default=0.006, help="simplification, in map pixels (one pixel is about 4.6 km)")
    args = ap.parse_args()
    P = place(args.place)
    proj = AlbersUsa().by_state(P["code"])      # the state's own part of the map (Alaska and Hawaii are insets), as load_districts.py does
    result = {"q": Q, "counties": {}, "info": {}, "vintage": "", "source": {}}
    for year in YEARS:
        name = f"cb_{year}_us_county_500k.zip"
        path = os.path.join(args.cache_dir, "census", name)
        try:
            if net.download(f"https://www2.census.gov/geo/tiger/GENZ{year}/shp/{name}", path, 300):
                print(f"    fetched {name} ({os.path.getsize(path) / 1e6:,.1f} MB)")
            shapes, info, points = read_counties(path, P["fips"], lambda lon, lat: proj(lon, lat), args.tolerance)
        except Exception as e:  # noqa: BLE001
            print(f"    {name}: {e}")
            continue
        sha = hashlib.sha256(open(path, "rb").read()).hexdigest()
        result.update({"counties": shapes, "info": info, "vintage": f"{year} Census Bureau cartographic boundary file (counties, 1:500,000)",
                       "source": {"file": name, "url": f"https://www2.census.gov/geo/tiger/GENZ{year}/shp/{name}", "sha256": sha}})
        print(f"    {P['name']}: {len(shapes)} counties, {points:,} points")
        break
    result["generated"] = dt.date.today().isoformat()
    text = json.dumps(result, separators=(",", ":"))
    with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print(f"    Wrote {args.out}: {len(text) / 1e3:,.0f} KB")


if __name__ == "__main__":
    main()
