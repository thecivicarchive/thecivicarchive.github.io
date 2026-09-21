#!/usr/bin/env python3
"""
states/load_legiscan.py
=======================
A state's bills and recorded votes, from LegiScan's weekly datasets: one ZIP per legislative session holding every
bill, every roll call with each member's vote, and every member, as JSON. LegiScan covers the 50 states and DC.

It needs a free LegiScan "public service" API key, which John gets himself. The key lives in one line of
`legiscan_key.txt` next to run_states.py. It is never printed, never logged and never put in a web address that
is shown; git ignores the file. The free key allows 30,000 queries a month; this stage uses one query to list a
state's sessions and one more per session only when LegiScan says that session's file has changed.

This first version fetches and inventories: it keeps each session's ZIP under states_cache/legiscan/, records which
version it holds, and reports what is inside. Turning those files into the bills, votes and member-vote tables
is the next step, written against the real files.

    python -m states.load_legiscan --place mn --db state_mn.sqlite
"""

import argparse
import base64
import io
import json
import os
import sqlite3
import sys
import time
import zipfile
from urllib.parse import urlencode

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from states import net                     # noqa: E402
from states.places import place            # noqa: E402

API = "https://api.legiscan.com/"
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SCHEMA = """
CREATE TABLE IF NOT EXISTS legiscan_datasets (
  session_id INTEGER PRIMARY KEY, state TEXT, session_name TEXT, year_start INTEGER, year_end INTEGER, special INTEGER,
  dataset_hash TEXT, dataset_date TEXT, dataset_size INTEGER, path TEXT, fetched_at TEXT);
"""


def read_key():
    path = os.path.join(HERE, "legiscan_key.txt")
    if not os.path.exists(path):
        return None
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#"):
            return line
    return None


def call(key, **params):
    """One API query. The key is only ever in the request itself; errors are reported without the address."""
    try:
        raw = net.get(API + "?" + urlencode(dict(params, key=key)), timeout=300, accept="application/json")
    except Exception as e:  # noqa: BLE001
        raise SystemExit(f"LegiScan did not answer ({type(e).__name__}). Check the connection and run this stage again.") from None
    j = json.loads(raw)
    if j.get("status") != "OK":
        msg = (j.get("alert") or {}).get("message") or "the request was refused"
        raise SystemExit(f"LegiScan said: {msg}. If this is about the key, check the one line in legiscan_key.txt.")
    return j


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--place", required=True)
    ap.add_argument("--db", required=True)
    ap.add_argument("--cache-dir", default="states_cache")
    args = ap.parse_args()
    P = place(args.place)
    key = read_key()
    if not key:
        print("    Waiting for the LegiScan key. Bills and votes cannot be loaded without it.")
        print("    John: make a free account at legiscan.com, confirm it from the email they send, then fill in the short form")
        print("    on the LegiScan API page (https://legiscan.com/legiscan); the key appears on that same page. To save it,")
        print("    double-click \"Save LegiScan key.bat\" in this folder and paste the key there. Do not paste it into a chat.")
        return 2
    since = int(P["since"][:4])
    con = sqlite3.connect(args.db)
    con.executescript(SCHEMA)
    folder = os.path.join(args.cache_dir, "legiscan")
    os.makedirs(folder, exist_ok=True)

    sessions = [s for s in call(key, op="getDatasetList", state=P["code"]).get("datasetlist", []) if int(s.get("year_end") or 0) >= since]
    print(f"    {P['name']}: {len(sessions)} session(s) since {since}: " + "; ".join(s.get("session_name", "?") for s in sessions))
    for s in sessions:
        sid = int(s["session_id"])
        have = con.execute("SELECT dataset_hash, path FROM legiscan_datasets WHERE session_id = ?", (sid,)).fetchone()
        path = os.path.join(folder, f"{P['code']}_{sid}.zip")
        if have and have[0] == s.get("dataset_hash") and os.path.exists(path):
            print(f"      {s.get('session_name')}: unchanged since {s.get('dataset_date')}")
        else:
            d = call(key, op="getDataset", id=sid, access_key=s["access_key"]).get("dataset", {})
            open(path, "wb").write(base64.b64decode(d.get("zip") or ""))
            with con:
                con.execute("INSERT OR REPLACE INTO legiscan_datasets VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                            (sid, P["code"], s.get("session_name"), s.get("year_start"), s.get("year_end"), s.get("special"), s.get("dataset_hash"),
                             s.get("dataset_date"), s.get("dataset_size"), path, time.strftime("%Y-%m-%dT%H:%M:%S")))
            print(f"      {s.get('session_name')}: fetched the {s.get('dataset_date')} file ({os.path.getsize(path) / 1e6:,.1f} MB)")
            time.sleep(1.0)
        with zipfile.ZipFile(path) as z:
            names = z.namelist()
            kinds = {k: sum(1 for n in names if f"/{k}/" in n and n.endswith(".json")) for k in ("bill", "vote", "people")}
            print(f"        inside: {kinds['bill']:,} bills, {kinds['vote']:,} roll calls, {kinds['people']:,} members")
            sample = next((n for n in names if "/vote/" in n and n.endswith(".json")), None)
            if sample:
                rc = json.loads(z.read(sample)).get("roll_call", {})
                print(f"        a roll call: {rc.get('date')} {rc.get('desc', '')[:60]!r} yea {rc.get('yea')} nay {rc.get('nay')}, {len(rc.get('votes') or [])} member votes")
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
