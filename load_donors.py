#!/usr/bin/env python3
"""
load_donors.py
==============
Who gives to the campaigns of the people in Congress, and who spends money for or against them, from the
Federal Election Commission's own bulk files (public record, no key, no sign-up):

  member_fec             which FEC candidate numbers belong to which member (from the `congress-legislators` roster)
  fec_candidates         each of those candidate numbers in each two-year cycle: office sought, state, district,
                         incumbent or challenger
  fec_committees         every committee that gave or spent: its name, its kind, the organization behind it
  fec_candidate_totals   what each campaign itself reported for the cycle: money from people, from PACs, from the
                         party, from the candidate, and so on
  fec_gifts              every itemized payment by a committee to, for, or against one of these members:
                           gift      a contribution to the campaign, in money or in kind (FEC types 24K, 24Z, 24P)
                           for       an independent expenditure supporting the candidate (24E)
                           against   an independent expenditure opposing the candidate (24A)
                           party     a party's coordinated expenditure (24C)
                           talk_for / talk_against   a membership group's communication to its own members (24F, 24N)

Only organizations appear here. Money from individual people is carried as totals (fec_candidate_totals), never
as names. Rows the filer marked as memo items (MEMO_CD = X) are left out, as the FEC's own totals leave them out:
they repeat money that is already counted on another line.

The four files per cycle are cn (candidates), cm (committees), weball (campaign totals) and pas2 (committee
payments). pas2 is about 25 MB a cycle; the others are under 1 MB. Files are cached under fec_cache/ and fetched
again only when they are stale: a week for the two newest cycles, two months for older ones.

    python load_donors.py --db congress_119.sqlite --cache-dir fec_cache --cycles 2016-2026
"""

import argparse
import datetime as dt
import io
import os
import sqlite3
import sys
import time
import zipfile
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("pip install pyyaml")

ROSTER = "https://raw.githubusercontent.com/unitedstates/congress-legislators/main/"
FEC = "https://www.fec.gov/files/bulk-downloads/"
UA = "congress-catalog/1.0 (personal legislative research; thecivicarchive.github.io)"

KIND = {"24K": "gift", "24Z": "gift", "24P": "gift", "24E": "for", "24A": "against", "24C": "party",
        "24F": "talk_for", "24N": "talk_against"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS member_fec (
  bioguide_id TEXT NOT NULL, cand_id TEXT NOT NULL, PRIMARY KEY (bioguide_id, cand_id));
CREATE TABLE IF NOT EXISTS fec_candidates (
  cand_id TEXT NOT NULL, cycle INTEGER NOT NULL, name TEXT, party TEXT, election_year INTEGER, office TEXT, state TEXT,
  district TEXT, ici TEXT, principal_committee TEXT, PRIMARY KEY (cand_id, cycle));
CREATE TABLE IF NOT EXISTS fec_committees (
  cmte_id TEXT PRIMARY KEY, name TEXT, designation TEXT, type TEXT, party TEXT, org_type TEXT, connected_org TEXT,
  cand_id TEXT, state TEXT, last_cycle INTEGER);
CREATE TABLE IF NOT EXISTS fec_candidate_totals (
  cand_id TEXT NOT NULL, cycle INTEGER NOT NULL, receipts REAL, from_individuals REAL, from_committees REAL,
  from_party REAL, from_candidate REAL, candidate_loans REAL, other_loans REAL, transfers_in REAL, disbursements REAL,
  cash_on_hand REAL, coverage_end TEXT, PRIMARY KEY (cand_id, cycle));
CREATE TABLE IF NOT EXISTS fec_gifts (
  sub_id INTEGER PRIMARY KEY, cycle INTEGER NOT NULL, cmte_id TEXT NOT NULL, cand_id TEXT NOT NULL, bioguide_id TEXT NOT NULL,
  kind TEXT NOT NULL, fec_type TEXT, election TEXT, date TEXT, amount REAL NOT NULL, image_num TEXT);
CREATE INDEX IF NOT EXISTS idx_fec_gifts_member ON fec_gifts (bioguide_id, cycle, kind);
CREATE INDEX IF NOT EXISTS idx_fec_gifts_cmte ON fec_gifts (cmte_id, cycle);
"""


def patient_lookups(tries=24):
    """Some home routers drop one address lookup in three, and the FEC's storage host has a long name that seems
    to make it worse. Ask again, a little slower each time, before calling it a failure. Nothing else changes:
    the same servers, the same one-at-a-time requests."""
    import socket
    plain = socket.getaddrinfo

    def lookup(host, port, family=0, *rest, **kw):
        last = None
        for i in range(tries):
            try:
                return plain(host, port, family if (family or i % 2) else socket.AF_INET, *rest, **kw)
            except socket.gaierror as e:
                last = e
                time.sleep(min(3.0, 0.3 + i * 0.25))
        raise last
    socket.getaddrinfo = lookup


def fetch(url, timeout=120):
    with urlopen(Request(url, headers={"User-Agent": UA, "Accept": "*/*"}), timeout=timeout) as r:
        return r.read()


def roster(name, local_dir):
    if local_dir and os.path.exists(os.path.join(local_dir, name)):
        data = open(os.path.join(local_dir, name), "rb").read()
    else:
        data = fetch(ROSTER + name, timeout=180)
    return yaml.load(data, Loader=getattr(yaml, "CSafeLoader", yaml.SafeLoader))


def download(url, path, max_age_days):
    """One file, streamed to disk; kept until it is older than max_age_days. One at a time, politely."""
    if os.path.exists(path) and (time.time() - os.path.getmtime(path)) < max_age_days * 86400 and os.path.getsize(path) > 0:
        return False
    part = path + ".part"
    tries = 8                                                  # the FEC's storage address sometimes fails to resolve for a minute; be patient
    for attempt in range(tries):
        try:
            with urlopen(Request(url, headers={"User-Agent": UA, "Accept": "*/*"}), timeout=120) as r, open(part, "wb") as fh:
                total, got, told = int(r.headers.get("Content-Length") or 0), 0, 0
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    fh.write(chunk)
                    got += len(chunk)
                    if got - told >= 8 << 20:
                        told = got
                        print(f"      {os.path.basename(path)}: {got / 1e6:,.0f} MB" + (f" of {total / 1e6:,.0f}" if total else ""), flush=True)
            if total and got != total:
                raise OSError(f"short read: {got:,} of {total:,} bytes")
            os.replace(part, path)
            time.sleep(1.0)
            return True
        except (HTTPError, URLError, OSError) as e:
            if attempt == tries - 1:
                if os.path.exists(path):                       # an older copy is better than none
                    print(f"      could not refresh {os.path.basename(path)} ({e}); using the copy on disk", flush=True)
                    return False
                raise
            print(f"      {os.path.basename(path)}: {e}; trying again in {15 * (attempt + 1)} s", flush=True)
            time.sleep(15 * (attempt + 1))


def rows(zip_path, encoding="utf-8"):
    """Every line of the one text file inside an FEC zip, split on the pipe."""
    with zipfile.ZipFile(zip_path) as z:
        names = [n for n in z.namelist() if n.lower().endswith(".txt")]
        if not names:
            return
        with z.open(names[0]) as raw:
            for line in io.TextIOWrapper(raw, encoding=encoding, errors="replace", newline=""):
                yield line.rstrip("\r\n").split("|")


def money(text):
    try:
        return float(text) if text not in ("", None) else 0.0
    except ValueError:
        return 0.0


def iso(mmddyyyy):
    t = (mmddyyyy or "").strip().replace("/", "")               # pas2 writes 01312024, weball writes 01/31/2024
    if len(t) == 8 and t.isdigit():
        m, d, y = int(t[:2]), int(t[2:4]), int(t[4:])
        if 1 <= m <= 12 and 1 <= d <= 31 and 1990 <= y <= 2100:
            return f"{y:04d}-{m:02d}-{d:02d}"
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", required=True)
    ap.add_argument("--cache-dir", default="fec_cache")
    ap.add_argument("--cycles", default="2016-2026", help="first and last election year, e.g. 2016-2026")
    ap.add_argument("--dir", default="", help="folder with local copies of the roster files")
    args = ap.parse_args()
    first, last = (int(x) for x in args.cycles.split("-"))
    cycles = [y for y in range(first + first % 2, last + 1, 2)]
    newest = max(cycles)
    os.makedirs(args.cache_dir, exist_ok=True)
    patient_lookups()

    con = sqlite3.connect(args.db)
    old = con.execute("SELECT type FROM pragma_table_info('fec_gifts') WHERE name = 'sub_id'").fetchone()
    if old and old[0].upper() != "INTEGER":                    # an earlier layout kept the FEC's row number as text, which doubled the table
        con.execute("DROP TABLE fec_gifts")
    con.executescript(SCHEMA)
    if not con.execute("SELECT 1 FROM sqlite_master WHERE name = 'legislators'").fetchone():
        sys.exit("No roster yet. Run the roster stage first: python run_all.py roster")
    wanted = {r[0] for r in con.execute("SELECT bioguide_id FROM legislators WHERE is_current = 1")}
    if con.execute("SELECT 1 FROM sqlite_master WHERE name = 'member_votes'").fetchone():
        wanted |= {r[0] for r in con.execute("SELECT DISTINCT member_key FROM member_votes") if r[0]}

    # -- which FEC candidate numbers are whose
    whose, seen = {}, set()
    for name in ("legislators-current.yaml", "legislators-historical.yaml"):
        if name.endswith("historical.yaml") and not (wanted - seen):
            break
        for m in roster(name, args.dir):
            ids = m.get("id") or {}
            bio = ids.get("bioguide")
            if bio in wanted and bio not in seen:
                seen.add(bio)
                for cid in ids.get("fec") or []:
                    whose[str(cid).strip()] = bio
    have = {b for b in whose.values()}
    print(f"    {len(wanted):,} members; {len(have):,} have FEC candidate numbers ({len(whose):,} numbers in all)")
    missing = sorted(wanted - have)
    if missing:
        print(f"    no FEC number in the roster for: {', '.join(missing[:12])}{' ...' if len(missing) > 12 else ''}")

    committees, cand_rows, total_rows = {}, [], []
    summary = []
    for cycle in cycles:
        yy = f"{cycle % 100:02d}"
        age = 7 if cycle >= newest - 2 else 60
        paths = {}
        for stem in ("cn", "cm", "weball", "pas2"):
            paths[stem] = os.path.join(args.cache_dir, f"{stem}{yy}.zip")
            fresh = download(f"{FEC}{cycle}/{stem}{yy}.zip", paths[stem], age)
            if fresh:
                print(f"    {cycle}: fetched {stem}{yy}.zip ({os.path.getsize(paths[stem]) / 1e6:,.1f} MB)", flush=True)

        for f in rows(paths["cn"]):                              # candidates
            if len(f) >= 10 and f[0] in whose:
                cand_rows.append((f[0], cycle, f[1], f[2], int(f[3]) if f[3].isdigit() else None, f[5], f[4], f[6], f[7], f[9]))
        for f in rows(paths["cm"]):                              # committees: the newest cycle's description wins
            if len(f) >= 15:
                committees[f[0]] = (f[0], f[1], f[8], f[9], f[10], f[12], f[13], f[14], f[6], cycle)
        for f in rows(paths["weball"]):                          # what each campaign reported for the cycle
            if len(f) >= 28 and f[0] in whose:
                total_rows.append((f[0], cycle, money(f[5]), money(f[17]), money(f[25]), money(f[26]), money(f[11]), money(f[12]),
                                   money(f[13]), money(f[6]), money(f[7]), money(f[10]), iso(f[27])))

        gifts, memo, kinds = [], 0, {}
        for f in rows(paths["pas2"]):                            # committee payments to, for, or against a candidate
            if len(f) < 22 or f[16] not in whose:
                continue
            kind = KIND.get(f[5])
            if not kind:
                continue
            if (f[19] or "").strip().upper() == "X":
                memo += 1
                continue
            amt = money(f[14])
            if not f[21].isdigit():
                continue
            gifts.append((int(f[21]), cycle, f[0], f[16], whose[f[16]], kind, f[5], (f[3] or "").strip(), iso(f[13]), amt, f[4]))
            k = kinds.setdefault(kind, [0, 0.0]); k[0] += 1; k[1] += amt
        with con:
            con.execute("DELETE FROM fec_gifts WHERE cycle = ?", (cycle,))
            con.executemany("INSERT OR REPLACE INTO fec_gifts VALUES (?,?,?,?,?,?,?,?,?,?,?)", gifts)
        said = ", ".join(f"{k} {v[0]:,} rows ${v[1] / 1e6:,.1f}M" for k, v in sorted(kinds.items()))
        print(f"    {cycle}: {len(gifts):,} payments kept ({said}); {memo:,} memo lines left out", flush=True)
        summary.append((cycle, len(gifts)))

    used = {r[0] for r in con.execute("SELECT DISTINCT cmte_id FROM fec_gifts")}
    with con:
        con.execute("DELETE FROM member_fec")
        con.executemany("INSERT OR REPLACE INTO member_fec VALUES (?,?)", [(b, c) for c, b in whose.items()])
        con.execute("DELETE FROM fec_candidates")
        con.executemany("INSERT OR REPLACE INTO fec_candidates VALUES (?,?,?,?,?,?,?,?,?,?)", cand_rows)
        con.execute("DELETE FROM fec_candidate_totals")
        con.executemany("INSERT OR REPLACE INTO fec_candidate_totals VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", total_rows)
        con.execute("DELETE FROM fec_committees")
        con.executemany("INSERT OR REPLACE INTO fec_committees VALUES (?,?,?,?,?,?,?,?,?,?)", [v for k, v in committees.items() if k in used])
    if old and old[0].upper() != "INTEGER":
        con.execute("VACUUM")                                   # hand back the space the old layout used
    n = con.execute("SELECT COUNT(*) FROM fec_gifts").fetchone()[0]
    unnamed = con.execute("SELECT COUNT(DISTINCT cmte_id) FROM fec_gifts WHERE cmte_id NOT IN (SELECT cmte_id FROM fec_committees)").fetchone()[0]
    print(f"    Stored: {n:,} payments from {len(used):,} committees to {len(have):,} members over {len(cycles)} cycles "
          f"({dt.date.today():%Y-%m-%d}); {len(cand_rows):,} candidate-cycles, {len(total_rows):,} campaign totals"
          + (f"; {unnamed} committee(s) not in the committee files" if unnamed else ""))


if __name__ == "__main__":
    main()
