#!/usr/bin/env python3
"""
load_legislators.py
===================
Loads the official member roster (the `congress-legislators` dataset maintained with the
GovTrack / Sunlight lineage, mirrored on GitHub) into a `legislators` table: every current and
former member with bioguide ID, Senate LIS ID (the crosswalk Senate roll calls need), party,
state, district, birthday, first and latest term dates, official website, contact form and
office phone.

    pip install pyyaml
    python load_legislators.py --db congress_119.sqlite            # downloads both files
    python load_legislators.py --db congress_119.sqlite --dir ./ext  # uses local copies

Re-running refreshes in place. No API key.
"""

import argparse
import datetime as dt
import os
import sqlite3
import sys
from urllib.request import urlopen

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("pip install pyyaml")

BASE = "https://raw.githubusercontent.com/unitedstates/congress-legislators/main/"
FILES = ("legislators-current.yaml", "legislators-historical.yaml")
PARTY_CODE = {"Democrat": "D", "Republican": "R", "Independent": "I", "Libertarian": "L",
              "Independent Democrat": "ID", "Democrat-Farmer-Labor": "D", "Democratic-Farmer-Labor": "D"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS legislators (
  bioguide_id TEXT PRIMARY KEY, lis_id TEXT, govtrack_id INTEGER,
  first_name TEXT, last_name TEXT, official_full TEXT, birthday TEXT, gender TEXT,
  party TEXT, party_name TEXT, state TEXT, district INTEGER, chamber TEXT, senate_class INTEGER,
  is_current INTEGER, term_start TEXT, term_end TEXT, first_term_start TEXT, terms_count INTEGER,
  url TEXT, contact_form TEXT, phone TEXT, office TEXT, wikipedia TEXT, updated_at TEXT
);
CREATE INDEX IF NOT EXISTS ix_legislators_lis ON legislators (lis_id);
CREATE INDEX IF NOT EXISTS ix_legislators_state ON legislators (state, chamber);
"""


def fetch(name, local_dir):
    if local_dir and os.path.exists(os.path.join(local_dir, name)):
        return open(os.path.join(local_dir, name), "rb").read()
    with urlopen(BASE + name, timeout=120) as r:
        return r.read()


def rows_from(data, is_current):
    loader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)
    for m in yaml.load(data, Loader=loader):
        ids, name, bio, terms = m.get("id", {}), m.get("name", {}), m.get("bio", {}), m.get("terms", [])
        if not terms or not ids.get("bioguide"):
            continue
        last = terms[-1]
        starts = sorted(str(t.get("start", "")) for t in terms if t.get("start"))
        party_name = last.get("party", "")
        yield (
            ids["bioguide"], ids.get("lis"), ids.get("govtrack"),
            name.get("first"), name.get("last"), name.get("official_full") or f"{name.get('first', '')} {name.get('last', '')}".strip(),
            str(bio.get("birthday")) if bio.get("birthday") else None, bio.get("gender"),
            PARTY_CODE.get(party_name, (party_name[:1] if party_name else "")), party_name,
            last.get("state"), last.get("district") if last.get("type") == "rep" else None,
            "Senate" if last.get("type") == "sen" else "House", last.get("class"),
            1 if is_current else 0, str(last.get("start", "")), str(last.get("end", "")),
            starts[0] if starts else None, len(terms),
            last.get("url"), last.get("contact_form"), last.get("phone"), last.get("office"), ids.get("wikipedia"),
            dt.datetime.now().isoformat(timespec="seconds"),
        )


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", required=True)
    ap.add_argument("--dir", default="", help="folder with local copies of the two YAML files")
    args = ap.parse_args()
    con = sqlite3.connect(args.db)
    con.executescript(SCHEMA)
    total = 0
    for name in FILES:
        data = fetch(name, args.dir)
        rows = list(rows_from(data, name.startswith("legislators-current")))
        con.executemany("INSERT OR REPLACE INTO legislators VALUES (" + ",".join("?" * 25) + ")", rows)
        con.commit()
        total += len(rows)
        print(f"{name}: {len(rows):,} members")
    cur = con.execute("SELECT COUNT(*) FROM legislators WHERE is_current = 1").fetchone()[0]
    print(f"legislators table: {total:,} rows ({cur} current)")


if __name__ == "__main__":
    main()
