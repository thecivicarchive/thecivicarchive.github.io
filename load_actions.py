#!/usr/bin/env python3
"""Every action the official record carries for each measure, in the order it happened.

The catalog keeps what the site needs most (committee steps, the floor votes, the status a measure has reached).
The Bill Status files hold the whole story: each referral to a committee, each report, each passage, every time a
measure went back to the other chamber with changes, each message between the chambers, its presentation to the
President, the signature or the veto, and every override vote. This reads them all from the cached Bill Status
files (nothing is downloaded) into an `actions` table, so the site can draw a measure's real path, back and forth
between the chambers, with a date on every step.

The files list a measure's actions newest first, and many share a day; the file's own order is kept (reversed, so
`seq` counts up in time) and used to order actions on the same day, which is how the Library of Congress orders them.

These are facts from the record. Nothing here is typed in by hand.

    python load_actions.py --db congress_119.sqlite --cache billstatus_cache
"""
import argparse
import os
import re
import sqlite3
import sys
import time
import zipfile
import xml.etree.ElementTree as ET

MEMBER = re.compile(r"BILLSTATUS-(\d+)([a-z]+)(\d+)\.xml$")
LOC_CHAMBER = re.compile(r"^(?:Passed/agreed to in (House|Senate)|Failed of passage/not agreed to in (House|Senate)|"
                         r"Resolving differences -- (House|Senate) actions)", re.I)
SCHEMA = """
CREATE TABLE IF NOT EXISTS actions (
  bill_key TEXT NOT NULL, seq INTEGER NOT NULL, action_date TEXT, action_time TEXT, source TEXT, action_type TEXT,
  action_code TEXT, chamber TEXT, text TEXT, rolls TEXT, committees TEXT,
  PRIMARY KEY (bill_key, seq));
"""


def chamber_of(source, code, text):
    """Which chamber an action happened in, from the system that recorded it; the Library of Congress restatements
    name the chamber in their text or their code."""
    s = (source or "").lower()
    if s.startswith("house"):
        return "House"
    if s == "senate":
        return "Senate"
    m = LOC_CHAMBER.match(text or "")
    if m:
        return (m.group(1) or m.group(2) or m.group(3)).title()
    c = code or ""
    if c in ("1000", "Intro-H", "1010", "5000", "5500", "8000", "9000", "19500", "33000"):
        return "House"
    if c in ("10000", "Intro-S", "14000", "14500", "14900", "17000", "18000", "20500"):
        return "Senate"
    if c in ("28000", "31000", "32000", "36000", "41000", "E20000", "E30000", "E40000"):
        return "President"
    return ""


def actions_in(xml_bytes):
    """[(date, time, source, type, code, chamber, text, rolls, committees)] in the order they happened."""
    root = ET.fromstring(xml_bytes)
    bill = root.find("bill")
    acts = bill.find("actions") if bill is not None else None
    if acts is None:
        return []
    out = []
    for a in acts.findall("item"):
        text = re.sub(r"\s+", " ", a.findtext("text") or "").strip()
        src = (a.findtext("sourceSystem/name") or "").strip()
        code = (a.findtext("actionCode") or "").strip()
        date = (a.findtext("actionDate") or "").strip()
        if not date or (not text and code not in ("Intro-S", "Intro-H")):
            continue
        rolls = []
        for v in a.findall("recordedVotes/recordedVote"):
            ch, roll = (v.findtext("chamber") or "").strip(), (v.findtext("rollNumber") or "").strip()
            if ch and roll:
                rolls.append(ch[0].upper() + roll)
        cms = [(c.findtext("name") or "").strip() for c in a.findall("committees/item")]
        out.append((date, (a.findtext("actionTime") or "").strip(), src, (a.findtext("type") or "").strip(), code,
                    chamber_of(src, code, text), text, ",".join(rolls), "; ".join(c for c in cms if c)))
    out.reverse()                                            # the file lists newest first; same-day actions keep their order
    return sorted(out, key=lambda r: r[0])                   # a stable sort: by day, and within a day as the record ordered them


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", required=True)
    ap.add_argument("--cache", default="billstatus_cache", help="the folder the catalog stage keeps the Bill Status zips in")
    args = ap.parse_args()
    if not os.path.isdir(args.cache):
        sys.exit(f"No cache folder at {args.cache}. Run the catalog stage first: python run_all.py catalog")
    t0, rows, files = time.time(), [], 0
    for folder, _dirs, names in os.walk(args.cache):
        for name in sorted(names):
            if not name.lower().endswith(".zip"):
                continue
            with zipfile.ZipFile(os.path.join(folder, name)) as z:
                for member in z.namelist():
                    m = MEMBER.search(member)
                    if not m:
                        continue
                    files += 1
                    key = f"{m.group(2)}{m.group(3)}-{m.group(1)}"
                    for seq, r in enumerate(actions_in(z.read(member))):
                        rows.append((key, seq) + r)
                    if files % 4000 == 0:
                        print(f"    {files:,} files read", flush=True)
    if not files:
        sys.exit(f"No Bill Status files found under {args.cache}. Run the catalog stage first: python run_all.py catalog")
    con = sqlite3.connect(args.db)
    with con:
        con.executescript(SCHEMA)
        con.execute("DELETE FROM actions")
        con.executemany("INSERT INTO actions (bill_key, seq, action_date, action_time, source, action_type, action_code, chamber, text, rolls, committees) "
                        "VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows)
        con.execute("CREATE INDEX IF NOT EXISTS ix_actions_bill ON actions (bill_key, seq)")
    back = con.execute("SELECT COUNT(DISTINCT bill_key) FROM actions WHERE action_code IN ('19500', '20500')").fetchone()[0]
    print(f"    Stored {len(rows):,} actions for {files:,} measures; {back:,} went back to a chamber to settle differences "
          f"({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
