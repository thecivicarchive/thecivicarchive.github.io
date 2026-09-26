#!/usr/bin/env python3
"""
run_local.py: the local level of The Civic Archive, one state at a time, counties first.

    python run_local.py mn              # everything for Minnesota's counties: counties, results, check, site
    python run_local.py mn counties     # one stage: counties | results | check | site

Stages:
  counties   the county lines from the Census Bureau's cartographic boundary file (local_<code>_counties.json)
  results    who holds each county office, from the Secretary of State's official results files, which John downloads
             by hand into states_cache/<code>_local/sos/<yyyymmdd>/ (the Secretary's site turns scripts away)
  check      a plain report of what is loaded (local_<code>_report.md)
  site       the county pages (site/dev/<code>/counties/) and the front door

Everything is written next to this script: local_<code>.sqlite, local_<code>_counties.json, local_<code>_report.md.
Every run writes a log to logs/.
"""

import datetime as dt
import os
import sqlite3
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from states.places import place          # noqa: E402

STAGES = ["counties", "results", "check", "site"]


def python():
    venv = os.path.join(HERE, ".venv", "Scripts" if os.name == "nt" else "bin", "python.exe" if os.name == "nt" else "python")
    return venv if os.path.exists(venv) else sys.executable


def run(module, *args):
    cmd = [python(), "-m", module, *args]
    print("$ " + " ".join(os.path.basename(c) if i == 0 else c for i, c in enumerate(cmd)), flush=True)
    r = subprocess.run(cmd, cwd=HERE)
    if r.returncode:
        sys.exit(f"  ({module} failed with exit code {r.returncode})")


def check(code, P, db, lines):
    out = [f"# {P['name']} counties: what is loaded, {dt.datetime.now():%Y-%m-%d %H:%M}", "", "| Part | Result |", "| --- | --- |"]
    waiting = []
    if os.path.exists(lines):
        import json
        d = json.load(open(lines, encoding="utf-8"))
        out.append(f"| County lines | {len(d.get('counties', {}))} counties ({d.get('vintage', '')}) |")
    else:
        waiting.append("county lines: run the counties stage")
    if os.path.exists(db):
        con = sqlite3.connect(db)
        has = lambda t: con.execute("SELECT 1 FROM sqlite_master WHERE name = ?", (t,)).fetchone() is not None
        if has("officials") and con.execute("SELECT COUNT(*) FROM officials").fetchone()[0]:
            n, c = con.execute("SELECT COUNT(*), COUNT(DISTINCT county_id) FROM officials").fetchone()
            els = [r[0] for r in con.execute("SELECT date FROM elections ORDER BY date")]
            out.append(f"| County officials | {n} winners of county offices in {c} counties, from the elections of {', '.join(els)} |")
        else:
            waiting.append("county officials: put the Secretary of State's results files in states_cache/<code>_local/sos/<yyyymmdd>/ and run the results stage")
    else:
        waiting.append("county officials: run the results stage")
    out += ["", "## Still to do", ""] + [f"- {w}" for w in waiting] if waiting else ["", "Everything that can be loaded so far is loaded."]
    path = os.path.join(HERE, f"local_{code}_report.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out) + "\n")
    print("\n".join("  " + line for line in out))


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    code = sys.argv[1].lower()
    P = place(code)
    stages = [s for s in sys.argv[2:] if s in STAGES] or STAGES
    os.makedirs(os.path.join(HERE, "logs"), exist_ok=True)
    log = os.path.join(HERE, "logs", f"local-{dt.datetime.now():%Y%m%d-%H%M%S}-{code}-{'-'.join(stages)}.log")
    db = os.path.join(HERE, f"local_{code}.sqlite")
    lines = os.path.join(HERE, f"local_{code}_counties.json")

    class Tee:
        def __init__(self, path):
            self.fh = open(path, "w", encoding="utf-8")
            self.out = sys.stdout

        def write(self, s):
            self.out.write(s)
            self.fh.write(s)

        def flush(self):
            self.out.flush()
            self.fh.flush()

    sys.stdout = Tee(log)
    print(f"The Civic Archive, local level: {P['name']}, stages {', '.join(stages)}, started {dt.datetime.now():%Y-%m-%d %H:%M}")
    for st in stages:
        print(f"\n=== {st} ===")
        if st == "counties":
            run("states.load_counties", "--place", code, "--out", lines)
        elif st == "results":
            run("states.load_local_results", "--place", code, "--db", db)
        elif st == "check":
            check(code, P, db, lines)
        elif st == "site":
            r = subprocess.run([python(), os.path.join(HERE, "build_local_dev.py"), "--place", code], cwd=HERE)
            if r.returncode:
                sys.exit("  (build_local_dev.py failed)")
            r = subprocess.run([python(), os.path.join(HERE, "build_door.py"), "--out", os.path.join(HERE, "site", "dev", "index.html"), "--draft"], cwd=HERE)
            if r.returncode:
                sys.exit("  (build_door.py failed)")
    print(f"\nDone. Log: {log}")


if __name__ == "__main__":
    main()
