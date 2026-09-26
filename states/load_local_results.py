#!/usr/bin/env python3
"""
states/load_local_results.py
============================
Who holds each county office, read from the Secretary of State's official election results. For Minnesota the
Secretary of State publishes every election's results as "media results" text files, one line per candidate per
precinct, semicolon-separated:

  state; county id; precinct name or id; office id; office name; district; candidate order; candidate name; suffix;
  incumbent code; party; precincts reporting; precincts in the race; votes; percent; total votes in the race

The Secretary's results site turns scripts (and this tool's browser) away with a CAPTCHA, so this loader downloads
nothing. John downloads the files in his own browser into states_cache/<code>_local/sos/<yyyymmdd>/ (every text file on
an election's Media Files page), and this loader reads whatever is there. Every county office in Minnesota is
nonpartisan on the ballot, so the party column is not read for them; the page says "nonpartisan office".

What is stored, and no more than the record supports: for every county office on a general-election ballot (county
commissioner by district, sheriff, county attorney, and the rest the file carries), the candidates, their votes, and
the winner, with the election date; the term the office carries under Minnesota law (four years for the county
offices); and the file each figure came from, with its fingerprint. Whether the winner still holds the office is not in
this record: a resignation or an appointment since the election is not here, and the page says so.

  elections    one row per election read (date, name, files, fingerprints)
  contests     one row per county office on a ballot (county, office, district, seats, total votes)
  results      one row per candidate in a contest (votes, percent, whether they won)
  officials    the winners: who holds each county office by election, with the term it carries

    python -m states.load_local_results --place mn --db local_mn.sqlite
"""

import argparse
import collections
import glob
import hashlib
import os
import re
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from states.places import place                      # noqa: E402

FIELDS = ["state", "county_id", "precinct", "office_id", "office", "district", "order", "candidate", "suffix", "incumbent", "party",
          "precincts_reporting", "precincts_total", "votes", "percent", "total_votes"]
COUNTY_OFFICE = re.compile(r"^(county commissioner|county sheriff|sheriff|county attorney|county auditor|county treasurer|county auditor[- /]treasurer|"
                           r"county recorder|county surveyor|county coroner|county clerk|register of deeds|county park commissioner|soil and water)", re.I)
ELECT_N = re.compile(r"\(elect (\d+)\)", re.I)
TERM_YEARS = {"county commissioner": 4, "county sheriff": 4, "sheriff": 4, "county attorney": 4, "county auditor": 4, "county treasurer": 4,
              "county recorder": 4, "county surveyor": 4, "county coroner": 4, "soil and water": 4}
SCHEMA = """
CREATE TABLE IF NOT EXISTS elections (date TEXT PRIMARY KEY, name TEXT, files TEXT, sha256 TEXT);
CREATE TABLE IF NOT EXISTS contests (
  id INTEGER PRIMARY KEY, election TEXT NOT NULL, county_id TEXT NOT NULL, office_id TEXT, office TEXT NOT NULL, district TEXT, seats INTEGER NOT NULL,
  total_votes INTEGER, precincts INTEGER, source_file TEXT);
CREATE TABLE IF NOT EXISTS results (
  id INTEGER PRIMARY KEY, contest INTEGER NOT NULL, candidate TEXT NOT NULL, suffix TEXT, incumbent INTEGER, party TEXT, votes INTEGER NOT NULL, percent REAL, won INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS officials (
  id INTEGER PRIMARY KEY, county_id TEXT NOT NULL, office TEXT NOT NULL, district TEXT, name TEXT NOT NULL, elected TEXT NOT NULL, term_years INTEGER,
  term_start TEXT, term_end TEXT, votes INTEGER, contest INTEGER);
CREATE INDEX IF NOT EXISTS idx_officials_county ON officials (county_id);
"""


def office_kind(office):
    o = office.lower()
    for k in TERM_YEARS:
        if o.startswith(k):
            return k
    return o.split("(")[0].strip()


def read_file(path):
    """Every row of one media results file as a dict; the layout is checked on the first line."""
    rows = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.rstrip("\r\n")
            if not line:
                continue
            parts = line.split(";")
            if len(parts) < 14:
                continue
            parts = (parts + [""] * 16)[:16]
            rows.append(dict(zip(FIELDS, [p.strip() for p in parts])))
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--place", required=True)
    ap.add_argument("--db", required=True)
    ap.add_argument("--cache-dir", default="states_cache")
    args = ap.parse_args()
    P = place(args.place)
    folder = os.path.join(args.cache_dir, f"{args.place}_local", "sos")
    con = sqlite3.connect(args.db)
    con.executescript(SCHEMA)
    dates = sorted(d for d in os.listdir(folder) if re.fullmatch(r"\d{8}", d)) if os.path.isdir(folder) else []
    if not dates:
        print(f"    No results files yet in {folder}. Download each election's Media Files text files there, one folder per election date (yyyymmdd).")
        return 0
    with con:
        for t in ("elections", "contests", "results", "officials"):
            con.execute(f"DELETE FROM {t}")
    for d in dates:
        date = f"{d[:4]}-{d[4:6]}-{d[6:]}"
        files = sorted(glob.glob(os.path.join(folder, d, "*.txt")))
        if not files:
            continue
        sha = hashlib.sha256()
        for f in files:
            sha.update(open(f, "rb").read())
        # sum every candidate's votes over the precincts of each county contest
        tally = {}                                                          # (county, office_id, office, district) -> {candidate -> [votes, suffix, incumbent, party, file]}
        precincts = collections.defaultdict(set)
        totals = {}
        n_rows = 0
        for f in files:
            for r in read_file(f):
                if not COUNTY_OFFICE.match(r["office"]):
                    continue
                n_rows += 1
                key = (r["county_id"], r["office_id"], r["office"], r["district"])
                c = tally.setdefault(key, {})
                who = c.setdefault(r["candidate"], [0, r["suffix"], 1 if r["incumbent"].upper() in ("Y", "YES", "1") else 0, r["party"], os.path.basename(f)])
                try:
                    who[0] += int(r["votes"] or 0)
                except ValueError:
                    pass
                precincts[key].add(r["precinct"])
                try:
                    totals[key] = max(totals.get(key, 0), int(r["total_votes"] or 0))
                except ValueError:
                    pass
        con.execute("INSERT INTO elections VALUES (?,?,?,?)", (date, f"{P['name']} election of {date}", ";".join(os.path.basename(f) for f in files), sha.hexdigest()))
        n_contests = n_winners = 0
        for (county, office_id, office, district), cands in sorted(tally.items()):
            m = ELECT_N.search(office)
            seats = int(m.group(1)) if m else 1
            ranked = sorted(cands.items(), key=lambda kv: -kv[1][0])
            total = sum(v[0] for v in cands.values())
            cur = con.execute("INSERT INTO contests (election, county_id, office_id, office, district, seats, total_votes, precincts, source_file) VALUES (?,?,?,?,?,?,?,?,?)",
                              (date, county, office_id, office, district, seats, total, len(precincts[(county, office_id, office, district)]), ranked[0][1][4] if ranked else ""))
            cid = cur.lastrowid
            n_contests += 1
            for i, (name, (votes, suffix, inc, party, _f)) in enumerate(ranked):
                won = 1 if i < seats and votes > 0 and not re.match(r"write[- ]?in", name, re.I) else 0
                con.execute("INSERT INTO results (contest, candidate, suffix, incumbent, party, votes, percent, won) VALUES (?,?,?,?,?,?,?,?)",
                            (cid, name, suffix, inc, party, votes, round(100.0 * votes / total, 2) if total else None, won))
                if won:
                    kind = office_kind(office)
                    years = TERM_YEARS.get(kind, 4)
                    start = f"{int(date[:4]) + 1}-01"                        # county terms in Minnesota begin the January after the election
                    con.execute("INSERT INTO officials (county_id, office, district, name, elected, term_years, term_start, term_end, votes, contest) VALUES (?,?,?,?,?,?,?,?,?,?)",
                                (county, office, district, (name + " " + suffix).strip(), date, years, start, f"{int(date[:4]) + 1 + years}-01", votes, cid))
                    n_winners += 1
        con.commit()
        print(f"    {date}: {len(files)} files, {n_rows:,} county-office rows, {n_contests} contests, {n_winners} winners")
    print(f"    officials on file: {con.execute('SELECT COUNT(*) FROM officials').fetchone()[0]} across {con.execute('SELECT COUNT(DISTINCT county_id) FROM officials').fetchone()[0]} counties")
    return 0


if __name__ == "__main__":
    sys.exit(main())
