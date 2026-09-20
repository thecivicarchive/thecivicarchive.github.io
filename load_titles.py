#!/usr/bin/env python3
"""Every title the official record carries for each measure.

The catalog keeps one display title and, sometimes, one short title. The Bill
Status files hold more: the popular title, when the Library of Congress records
one ("One Big Beautiful Bill Act"), and the short title a measure carried at each
stage of its life, which can differ from its final one or have been struck from
the final text altogether. This reads them all from the cached Bill Status files
(nothing is downloaded) into a `titles` table, so the site can lead with the name
people know while the formal title stays one tap away.

These are facts from the record. Nothing here is typed in by hand; names that are
in common use but not in the record live in nicknames.json, which John approves.

    python load_titles.py --db congress_119.sqlite --cache billstatus_cache
"""
import argparse
import html
import os
import re
import sqlite3
import sys
import time
import zipfile

MEMBER = re.compile(r"BILLSTATUS-(\d+)([a-z]+)(\d+)\.xml$")
TITLES = re.compile(r"<titles>(.*?)</titles>", re.S)
ITEM = re.compile(r"<item>(.*?)</item>", re.S)
FIELD = {name: re.compile(rf"<{name}>(.*?)</{name}>", re.S) for name in ("titleType", "title", "chamberName")}


def titles_in(xml_text):
    """[(title type, title, chamber)] from one Bill Status file, in the file's order, without repeats."""
    block = TITLES.search(xml_text)
    if not block:
        return []
    out, seen = [], set()
    for item in ITEM.findall(block.group(1)):
        got = {k: (rx.search(item).group(1) if rx.search(item) else "") for k, rx in FIELD.items()}
        tt, ti = html.unescape(got["titleType"]).strip(), re.sub(r"\s+", " ", html.unescape(got["title"])).strip()
        if tt and ti and (tt, ti) not in seen:
            seen.add((tt, ti))
            out.append((tt, ti, html.unescape(got["chamberName"]).strip()))
    return out


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
                    for tt, ti, ch in titles_in(z.read(member).decode("utf-8", "ignore")):
                        rows.append((key, tt, ti, ch))
                    if files % 4000 == 0:
                        print(f"    {files:,} files read", flush=True)
    if not files:
        sys.exit(f"No Bill Status files found under {args.cache}. Run the catalog stage first: python run_all.py catalog")
    con = sqlite3.connect(args.db)
    with con:
        con.execute("CREATE TABLE IF NOT EXISTS titles (bill_key TEXT NOT NULL, title_type TEXT NOT NULL, title TEXT NOT NULL, chamber TEXT)")
        con.execute("DELETE FROM titles")
        con.executemany("INSERT INTO titles (bill_key, title_type, title, chamber) VALUES (?, ?, ?, ?)", rows)
        con.execute("CREATE INDEX IF NOT EXISTS ix_titles_bill ON titles (bill_key)")
    popular = con.execute("SELECT COUNT(DISTINCT bill_key) FROM titles WHERE title_type LIKE 'Popular%'").fetchone()[0]
    print(f"    Stored {len(rows):,} titles for {files:,} measures; {popular:,} carry a popular title in the record "
          f"({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
