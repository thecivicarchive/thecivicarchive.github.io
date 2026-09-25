#!/usr/bin/env python3
"""
run_states.py - the state side of The Civic Archive, one state at a time.

    python run_states.py mn              # everything for Minnesota: people, districts, bills, money, check, site
    python run_states.py mn people       # one stage: people | districts | bills | money | check | site

It uses the same private Python environment as run_all.py (.venv) and writes a log to ./logs. Each state has its
own database, state_<code>.sqlite, laid out like congress_119.sqlite, and its own district file,
state_<code>_districts.json. Downloads are kept in states_cache/, so a re-run fetches only what is stale.

Stages
  people     sitting legislators, their service, committees, Wikipedia paragraph and portrait (Open States, CC0)
  districts  upper- and lower-chamber district lines (Census Bureau), and the shape of each district measured from them
  bills      bills and recorded votes (LegiScan weekly files; needs John's free key in legiscan_key.txt)
  money      campaign money from the state's own agency, where a loader exists (Minnesota: Campaign Finance Board)
  check      a short report: what is loaded, what is missing, what does not add up
  site       the state's draft pages, written to site/dev/<code>/ (build_state_dev.py), and the front door beside them
"""

import argparse
import datetime as dt
import json
import os
import sqlite3
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
STAGES = ["people", "districts", "bills", "money", "check", "site"]
LOG = None


def say(msg=""):
    line = str(msg)
    try:
        print(line, flush=True)
    except UnicodeEncodeError:
        print(line.encode("ascii", "replace").decode("ascii"), flush=True)
    if LOG:
        LOG.write(line + "\n")
        LOG.flush()


def venv_python():
    sub = ("Scripts", "python.exe") if os.name == "nt" else ("bin", "python")
    return os.path.join(HERE, ".venv", *sub)


def run(module, *args, allow_fail=False):
    script = module.endswith(".py")                     # the page builders are scripts next to this one, not modules in states/
    cmd = [sys.executable] + ([os.path.join(HERE, module)] if script else ["-m", module]) + [str(a) for a in args]
    say(f"$ python {'' if script else '-m '}{module} {' '.join(str(a) for a in args)}")
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    t0 = time.time()
    proc = subprocess.Popen(cmd, cwd=HERE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)
    for raw in proc.stdout:
        say("    " + raw.decode("utf-8", "replace").rstrip())
    code = proc.wait()
    say(f"  ({module} finished in {time.time() - t0:.0f}s, exit code {code})")
    if code and not allow_fail:
        raise SystemExit(f"\nStage failed: {module} exited with code {code}. Fix it and run the same stage again (downloads are kept).")
    return code


def check(code, db, districts):
    """What is loaded for this state, in plain words. Returns the lines; nothing is changed."""
    sys.path.insert(0, HERE)
    from states.places import place
    P = place(code)
    con = sqlite3.connect(db)
    has = lambda t: con.execute("SELECT 1 FROM sqlite_master WHERE name = ?", (t,)).fetchone() is not None
    one = lambda q, *a: con.execute(q, a).fetchone()[0]
    lines, waiting = [f"# {P['name']}: what is loaded, {dt.datetime.now():%Y-%m-%d %H:%M}\n", "| Part | Result |", "| --- | --- |"], []
    if has("legislators"):
        for ch, key in (("Senate" if P.get("lower") else "Legislature", "upper"), ("House", "lower")):
            if P.get(key):
                n = one("SELECT COUNT(*) FROM legislators WHERE is_current = 1 AND chamber = ?", ch)
                lines.append(f"| {P[key]['name']} members | {n} of {P[key]['seats']} seats{'' if n == P[key]['seats'] else ' (the rest are vacant or not yet on file)'} |")
        parties = ", ".join(f"{k} {v}" for k, v in con.execute("SELECT party_name, COUNT(*) FROM legislators WHERE is_current = 1 GROUP BY 1 ORDER BY 2 DESC"))
        lines.append(f"| Parties | {parties} |")
        lines.append(f"| Portraits / Wikipedia paragraphs | {one('SELECT COUNT(*) FROM photos WHERE webp IS NOT NULL') if has('photos') else 0} / {one('SELECT COUNT(*) FROM member_wikipedia') if has('member_wikipedia') else 0} |")
    else:
        waiting.append("members: run the people stage")
    if os.path.exists(districts):
        d = json.load(open(districts, encoding="utf-8"))
        lines.append(f"| District lines | {len(d.get('upper', {}))} upper, {len(d.get('lower', {}))} lower ({d.get('vintage', '')}) |")
        if has("legislators"):
            for ch, key in (("Senate" if P.get("lower") else "Legislature", "upper"), ("House", "lower")):
                lost = [r[0] for r in con.execute("SELECT district FROM legislators WHERE is_current = 1 AND chamber = ?", (ch,)) if r[0] not in d.get(key, {})]
                if lost:
                    waiting.append(f"{len(lost)} {ch} member(s) sit in a district with no shape: {', '.join(lost[:8])}")
    else:
        waiting.append("district lines: run the districts stage")
    if has("bills"):
        lines.append(f"| Bills / roll calls with member votes | {one('SELECT COUNT(*) FROM bills'):,} / {one('SELECT COUNT(DISTINCT vote_id) FROM member_votes') if has('member_votes') else 0:,} |")
    elif has("legiscan_datasets") and one("SELECT COUNT(*) FROM legiscan_datasets"):
        lines.append(f"| Bills and votes | {one('SELECT COUNT(*) FROM legiscan_datasets')} LegiScan session file(s) fetched; not yet turned into tables |")
    else:
        waiting.append("bills and votes: waiting for John's LegiScan key (legiscan_key.txt), then run the bills stage")
    if has("state_gifts"):
        m = one("SELECT COUNT(DISTINCT bioguide_id) FROM state_committees")
        cur = one("SELECT COUNT(*) FROM legislators WHERE is_current = 1")
        g, o = one("SELECT COALESCE(SUM(amount), 0) FROM state_gifts"), one("SELECT COALESCE(SUM(amount), 0) FROM state_outside")
        y0, y1 = con.execute("SELECT MIN(year), MAX(year) FROM state_sources").fetchone()
        lines.append(f"| Campaign money, {y0} to {y1} | {m} of {cur} members matched to a committee; ${g / 1e6:,.1f}M from named organizations; ${o / 1e6:,.1f}M of outside spending |")
        from states.money_views import KINDS                              # the kinds a page may name; anything else must never carry a name
        named = one(f"SELECT COUNT(*) FROM state_gifts WHERE donor_kind NOT IN ({','.join('?' * len(KINDS))}) OR donor_kind = 'unnamed'", *KINDS)
        if named:
            waiting.append(f"{named} gift row(s) carry a donor kind that should not be named; check the money loader")
    elif P.get("money"):
        waiting.append("campaign money: run the money stage")
    else:
        lines.append("| Campaign money | no loader for this state yet |")
    lines += ["", "## Still to do\n", *(f"- {w}" for w in waiting)] if waiting else ["", "Everything that can be loaded so far is loaded."]
    return lines


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("place", help="two-letter code, for example mn")
    ap.add_argument("stage", nargs="?", default="all", choices=["all"] + STAGES)
    ap.add_argument("--no-venv", action="store_true")
    args = ap.parse_args()
    py = venv_python()
    if not args.no_venv and sys.prefix == sys.base_prefix and os.path.exists(py):
        sys.exit(subprocess.call([py, os.path.abspath(__file__)] + sys.argv[1:]))
    try:
        import certifi
        os.environ.setdefault("SSL_CERT_FILE", certifi.where())
    except ImportError:
        pass
    code = args.place.lower()
    db, districts = os.path.join(HERE, f"state_{code}.sqlite"), os.path.join(HERE, f"state_{code}_districts.json")
    cache = os.path.join(HERE, "states_cache")
    global LOG
    os.makedirs(os.path.join(HERE, "logs"), exist_ok=True)
    LOG = open(os.path.join(HERE, "logs", f"states-{dt.datetime.now():%Y%m%d-%H%M%S}-{code}-{args.stage}.log"), "w", encoding="utf-8")
    sys.path.insert(0, HERE)
    from states.places import place
    P = place(code)
    say(f"The Civic Archive, state side: {P['name']}, stage '{args.stage}', started {dt.datetime.now():%Y-%m-%d %H:%M}")
    todo = STAGES if args.stage == "all" else [args.stage]
    for st in todo:
        say(f"\n=== {st} ===")
        if st == "people":
            run("states.load_people", "--place", code, "--db", db, "--cache-dir", cache)
        elif st == "districts":
            run("states.load_sld", "--place", code, "--out", districts, "--cache-dir", cache)
            # the first districting lens: how compact each district's shape is, from the same Census files (self-test first)
            run("district_shapes.py", "--selftest")
            run("district_shapes.py", "--state", code)
        elif st == "bills":
            run("states.load_legiscan", "--place", code, "--db", db, "--cache-dir", cache, allow_fail=True)
        elif st == "money":
            if P.get("money") == "mn_cfb":
                # the same window as the federal donor pages: the 2016 through 2026 cycles, and the 2016 cycle begins in January 2015
                run("states.money_mn", "--db", db, "--cache-dir", cache, "--since", "2015")
            elif P.get("money") == "ia_iecdb":
                run("states.money_ia", "--db", db, "--cache-dir", cache, "--since", "2015")
            elif P.get("money") == "wa_pdc":
                run("states.money_wa", "--db", db, "--cache-dir", cache, "--since", "2015")
            elif P.get("money") == "co_tracer":
                run("states.money_co", "--db", db, "--cache-dir", cache, "--since", "2015")
            elif P.get("money") == "tx_tec":
                run("states.money_tx", "--db", db, "--cache-dir", cache, "--since", "2015")
            elif P.get("money") == "ca_calaccess":
                run("states.money_ca", "--db", db, "--cache-dir", cache, "--since", "2015")
            elif P.get("money") == "fl_dos":
                run("states.money_fl", "--db", db, "--cache-dir", cache, "--since", "2015")
            elif P.get("money") == "nj_elec":
                run("states.money_nj", "--db", db, "--cache-dir", cache, "--since", "2015")
            else:
                say(f"  No campaign-money loader for {P['name']} yet; the site will say it is coming.")
        elif st == "check":
            lines = check(code, db, districts)
            open(os.path.join(HERE, f"state_{code}_report.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
            for ln in lines:
                say("  " + ln)
        elif st == "site":
            site = os.path.join(HERE, "site", "dev")
            run("build_state_dev.py", "--place", code, "--split", os.path.join(site, code))
            run("build_door.py", "--out", os.path.join(site, "index.html"), "--draft")      # the front door lists which states are open
    say(f"\nDone. Log: {LOG.name}")


if __name__ == "__main__":
    main()
