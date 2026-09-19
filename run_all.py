#!/usr/bin/env python3
"""
run_all.py - build Plain Congress for the current Congress, start to finish.

    python run_all.py              # everything: check, roster, catalog, rollcalls, photos, districts, ratings, build, verify
    python run_all.py check        # environment, disk and network checks only (nothing downloaded)
    python run_all.py smoke        # 30-second offline test on the bundled sample files
    python run_all.py refresh      # weekly update: re-download the catalog, then the rest
    python run_all.py <stage>      # one stage: roster | catalog | rollcalls | photos | districts | ratings | build | verify
    python run_all.py rate         # optional, costs money: rate bills with the Claude API (asks you to type YES)
    python run_all.py collect      # write finished API ratings and rebuild the site

Options: --db congress_119.sqlite  --congress 119  --since 2025-01-01  --all-types  --skip-excel  --no-venv

Works on macOS, Windows and Linux with Python 3.10+. The first run creates a private Python environment in
.venv and installs two packages (openpyxl, pyyaml); nothing is installed system-wide. Every stage can be re-run;
downloads are cached, so a re-run only fetches what is missing. A log of each run is written to ./logs.
"""

import argparse
import datetime as dt
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
from urllib.request import Request, urlopen

HERE = os.path.dirname(os.path.abspath(__file__))
STAGES = ["check", "roster", "catalog", "rollcalls", "photos", "districts", "ratings", "build", "verify"]
UA = "Mozilla/5.0 (compatible; congress-catalog/1.0; personal legislative research)"
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


def banner(title):
    say("")
    say("=" * 72)
    say(f"  {title}")
    say("=" * 72)


# ----------------------------------------------------------------------------- private Python environment
def venv_python():
    sub = ("Scripts", "python.exe") if os.name == "nt" else ("bin", "python")
    return os.path.join(HERE, ".venv", *sub)


def ensure_venv(argv):
    """Create .venv on first run, install requirements, and re-run this script inside it."""
    if sys.prefix != sys.base_prefix:          # already inside a virtual environment
        return
    py = venv_python()
    if not os.path.exists(py):
        print("Creating a private Python environment in .venv (first run only) ...", flush=True)
        subprocess.check_call([sys.executable, "-m", "venv", os.path.join(HERE, ".venv")])
    need = subprocess.run([py, "-c", "import openpyxl, yaml, certifi, PIL, shapefile"], capture_output=True).returncode != 0
    if need:
        print("Installing openpyxl, pyyaml, certifi, pillow and pyshp into .venv ...", flush=True)
        subprocess.check_call([py, "-m", "pip", "install", "--quiet", "--disable-pip-version-check",
                               "-r", os.path.join(HERE, "requirements.txt")])
    sys.exit(subprocess.call([py, os.path.abspath(__file__)] + argv))


# ----------------------------------------------------------------------------- running the pipeline scripts
def run(script, *args, allow_fail=False):
    cmd = [sys.executable, os.path.join(HERE, script)] + [str(a) for a in args]
    say(f"$ python {script} {' '.join(str(a) for a in args)}")
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    t0 = time.time()
    proc = subprocess.Popen(cmd, cwd=HERE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)
    for raw in proc.stdout:
        say("    " + raw.decode("utf-8", "replace").rstrip())
    code = proc.wait()
    say(f"  ({script} finished in {fmt_secs(time.time() - t0)}, exit code {code})")
    if code and not allow_fail:
        raise SystemExit(f"\nStage failed: {script} exited with code {code}. The log above shows why; "
                         f"fix it and re-run the same stage (cached downloads are kept).")
    return code


def fmt_secs(s):
    return f"{s:.0f}s" if s < 90 else f"{s / 60:.1f} min"


# ----------------------------------------------------------------------------- stages
def stage_check(args):
    banner("Stage: check (Python, packages, disk, network)")
    ok = True
    v = sys.version_info
    say(f"  Python {v.major}.{v.minor}.{v.micro} at {sys.executable}")
    if (v.major, v.minor) < (3, 10):
        say("  FAIL  Python 3.10 or newer is required (3.11+ recommended).")
        ok = False
    for mod in ("openpyxl", "yaml", "certifi", "PIL", "shapefile"):
        try:
            __import__(mod)
            say(f"  OK    package {mod}")
        except ImportError:
            say(f"  FAIL  package {mod} missing: run  python -m pip install -r requirements.txt")
            ok = False
    free = shutil.disk_usage(HERE).free / 1e9
    say(f"  {'OK  ' if free >= 2 else 'WARN'}  {free:.1f} GB free disk (about 2 GB needed)")
    tests = [
        ("GovInfo bill data", "https://www.govinfo.gov/bulkdata/json/BILLSTATUS/119", "application/json"),
        ("House Clerk roll calls", "https://clerk.house.gov/evs/2025/roll102.xml", None),
        ("Senate roll calls", "https://www.senate.gov/legislative/LIS/roll_call_votes/vote1191/vote_119_1_00007.xml", None),
        ("Member roster (GitHub)", "https://raw.githubusercontent.com/unitedstates/congress-legislators/main/legislators-current.yaml", None),
        ("Member portraits (GitHub)", "https://raw.githubusercontent.com/unitedstates/images/gh-pages/congress/225x275/K000367.jpg", None),
        ("District lines (Census Bureau, optional)", "https://www2.census.gov/geo/tiger/GENZ2024/shp/", None),
    ]
    for label, url, accept in tests:
        optional = "optional" in label
        headers = {"User-Agent": UA}
        if accept:
            headers["Accept"] = accept
        try:
            with urlopen(Request(url, headers=headers), timeout=30) as r:
                r.read(2048)
                say(f"  OK    {label} reachable (HTTP {r.status})")
        except Exception as e:  # noqa: BLE001
            if optional:
                say(f"  WARN  {label}: {e}  (the districts stage will use the 2016 lines from GitHub instead)")
            else:
                say(f"  FAIL  {label}: {e}")
                ok = False
    say("  All checks passed." if ok else "  Some checks failed; see CLAUDE.md > Troubleshooting before continuing.")
    return ok


def stage_smoke(args):
    banner("Stage: smoke test (offline, bundled sample files)")
    out = os.path.join(HERE, "smoke")
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out)
    db = os.path.join(out, "smoke.sqlite")
    run("congress_catalog.py", "--local-dir", os.path.join(HERE, "tests", "samples"), "--since", "1900-01-01",
        "--db", db, "--out", os.path.join(out, "smoke.xlsx"))
    run("score_bills.py", "--db", db, "--backing-only")
    run("build_site.py", "--db", db, "--out", os.path.join(out, "smoke_site.html"))
    n = sqlite3.connect(db).execute("SELECT COUNT(*) FROM bills").fetchone()[0]
    say(f"  Smoke test passed: {n} sample measures parsed, database, workbook and page written to ./smoke")


def stage_roster(args):
    banner("Stage: roster (current and former members of Congress)")
    run("load_legislators.py", "--db", args.db)


def stage_catalog(args, refresh=False):
    banner("Stage: catalog (every bill's Bill Status record from GovInfo)")
    a = ["--congress", args.congress, "--types", "all" if args.all_types else "law", "--since", args.since,
         "--db", args.db, "--cache", os.path.join(HERE, "billstatus_cache")]
    if args.local_dir:
        a += ["--local-dir", args.local_dir]
    a += ["--no-xlsx"] if args.skip_excel else ["--out", os.path.join(HERE, f"congress_{args.congress}.xlsx")]
    if refresh:
        a.append("--refresh")
    run("congress_catalog.py", *a)


def stage_rollcalls(args):
    banner("Stage: rollcalls (every recorded vote, member by member)")
    run("load_roll_calls.py", "--db", args.db, "--cache-dir", os.path.join(HERE, "rollcall_cache"), "--workers", "4")


def stage_photos(args):
    banner("Stage: photos (official portraits for members on the site)")
    run("load_photos.py", "--db", args.db, "--cache-dir", os.path.join(HERE, "photo_cache"))


def stage_districts(args):
    banner("Stage: districts (House district lines for the map's zoom-in view)")
    run("load_districts.py", "--out", os.path.join(os.path.dirname(args.db), "us_districts_albers.json"),
        "--cache-dir", os.path.join(HERE, "district_cache"))


def stage_ratings(args):
    banner("Stage: ratings (seed ratings + party backing from the roll calls; no API)")
    con = sqlite3.connect(args.db)
    seed = os.path.join(HERE, "seed", "seed_ratings_119.json")
    have_runs = con.execute("SELECT 1 FROM sqlite_master WHERE name = 'rating_runs'").fetchone()
    done = have_runs and con.execute("SELECT 1 FROM rating_runs WHERE scope = 'import:seed_ratings_119.json'").fetchone()
    if os.path.exists(seed) and not done:
        items = json.load(open(seed, encoding="utf-8"))
        keep = [i for i in items if con.execute("SELECT 1 FROM bills WHERE bill_key = ?", (i["bill_key"],)).fetchone()]
        con.close()
        tmp = os.path.join(HERE, "seed", "_seed_ratings_119.json")
        os.makedirs(os.path.dirname(tmp), exist_ok=True)
        json.dump(keep, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
        say(f"  Importing {len(keep)} hand-applied preview ratings ({len(items) - len(keep)} skipped: not in this catalog)")
        run("score_bills.py", "--db", args.db, "--import", tmp, "--rater", "hand preview, not yet reviewed")
        sqlite3.connect(args.db).execute("UPDATE rating_runs SET scope = 'import:seed_ratings_119.json' "
                                         "WHERE scope = 'import:_seed_ratings_119.json'").connection.commit()
        os.remove(tmp)
    else:
        con.close()
        say("  Seed ratings already imported (or no seed file); skipping.")
    run("score_bills.py", "--db", args.db, "--backing-only")


def stage_build(args):
    banner("Stage: build (the one-file website)")
    os.makedirs(os.path.join(HERE, "site"), exist_ok=True)
    run("build_site.py", "--db", args.db, "--out", os.path.join(HERE, "site", "index.html"))


def stage_verify(args):
    banner("Stage: verify (reconcile member votes to official totals, coverage, size)")
    con = sqlite3.connect(args.db)
    q = lambda sql, *p: con.execute(sql, p).fetchall()
    one = lambda sql, *p: con.execute(sql, p).fetchone()[0]
    has = lambda t: one("SELECT COUNT(*) FROM sqlite_master WHERE name = ?", t) > 0
    lines, problems = [], []
    lines.append(f"# Verify report, {dt.datetime.now():%Y-%m-%d %H:%M}\n")
    lines.append(f"Database: `{os.path.basename(args.db)}`\n")
    lines.append("| Check | Result |\n| --- | --- |")
    by_type = ", ".join(f"{t} {n:,}" for t, n in q("SELECT bill_type, COUNT(*) FROM bills GROUP BY bill_type ORDER BY COUNT(*) DESC"))
    lines.append(f"| Measures | {one('SELECT COUNT(*) FROM bills'):,} ({by_type}) |")
    laws = one("SELECT COUNT(*) FROM bills WHERE law_number <> ''")
    lines.append(f"| Became law | {laws:,} |")
    lines.append(f"| Latest action in the data | {one('SELECT MAX(latest_action_date) FROM bills') or 'n/a'} |")
    linked = one("SELECT COUNT(DISTINCT roll_call_xml) FROM floor_votes WHERE roll_call_xml <> ''")
    with_mv = one("SELECT COUNT(DISTINCT f.roll_call_xml) FROM floor_votes f WHERE f.roll_call_xml <> '' AND EXISTS "
                  "(SELECT 1 FROM member_votes m WHERE m.vote_id = f.vote_id)") if has("member_votes") else 0
    lines.append(f"| Roll calls linked to these measures | {linked:,} |")
    lines.append(f"| ...with member-level votes loaded | {with_mv:,} ({(100 * with_mv / linked if linked else 0):.1f}%) |")
    if linked and with_mv < linked:
        problems.append(f"{linked - with_mv} roll call(s) still lack member votes: re-run `python run_all.py rollcalls`.")
    mismatches = []
    if has("member_votes"):
        for vid, yeas, nays, url in q("SELECT vote_id, yeas, nays, roll_call_url FROM floor_votes WHERE yeas IS NOT NULL AND nays IS NOT NULL "
                                      "AND vote_id IN (SELECT DISTINCT vote_id FROM member_votes)"):
            y = one("SELECT COUNT(*) FROM member_votes WHERE vote_id = ? AND position IN ('Yea', 'Aye')", vid)
            n = one("SELECT COUNT(*) FROM member_votes WHERE vote_id = ? AND position IN ('Nay', 'No')", vid)
            if (y, n) != (yeas, nays):
                mismatches.append(f"{vid}: members {y}-{n} vs official {yeas}-{nays} {url or ''}")
        checked = one("SELECT COUNT(*) FROM floor_votes WHERE yeas IS NOT NULL AND vote_id IN (SELECT DISTINCT vote_id FROM member_votes)")
        lines.append(f"| Member votes add up to the official tally | {checked - len(mismatches):,} of {checked:,} votes match |")
        if mismatches:
            problems.append(f"{len(mismatches)} vote(s) where member counts differ from the official tally (listed below).")
        if has("legislators"):
            unresolved = q("SELECT DISTINCT member_key FROM member_votes WHERE member_key NOT IN (SELECT bioguide_id FROM legislators)")
            lines.append(f"| Members on roll calls matched to the roster | {'all' if not unresolved else str(len(unresolved)) + ' unmatched'} |")
            if unresolved:
                problems.append("Unmatched member ids: " + ", ".join(u[0] for u in unresolved[:10]) + " (re-run the roster stage).")
    if has("ratings"):
        voted = one("SELECT COUNT(DISTINCT bill_key) FROM floor_votes WHERE key_vote = 1 AND category = 'Passage' "
                    "AND result IN ('Passed', 'Agreed to', 'Failed')")
        backed = one("SELECT COUNT(DISTINCT bill_key) FROM ratings WHERE axis = 'backing' AND is_current = 1")
        rated = one("SELECT COUNT(DISTINCT bill_key) FROM ratings WHERE axis <> 'backing' AND is_current = 1")
        lines.append(f"| Party backing computed from roll calls | {backed:,} measures (of {voted:,} with a recorded passage vote) |")
        lines.append(f"| Measures with full ratings | {rated:,} |")
    if has("photos"):
        cur = one("SELECT COUNT(*) FROM legislators WHERE is_current = 1") if has("legislators") else 0
        with_photo = one("SELECT COUNT(*) FROM legislators l JOIN photos p ON p.bioguide_id = l.bioguide_id WHERE l.is_current = 1 AND p.webp IS NOT NULL") if has("legislators") else 0
        lines.append(f"| Current members with a portrait | {with_photo:,} of {cur:,} |")
    dist = os.path.join(os.path.dirname(args.db), "us_districts_albers.json")
    if os.path.exists(dist):
        dj = json.load(open(dist, encoding="utf-8"))
        n = sum(len(v) for v in dj.get("states", {}).values())
        lines.append(f"| District lines | {n} districts, {dj.get('vintage', '')} |")
        if "2016" in dj.get("vintage", ""):
            problems.append("District lines are the 2016 vintage (the Census file was not reachable); run `python run_all.py districts` on a network that can reach census.gov.")
    else:
        problems.append("No district lines file: run `python run_all.py districts`.")
    site = os.path.join(HERE, "site", "index.html")
    if os.path.exists(site):
        mb = os.path.getsize(site) / 1e6
        lines.append(f"| Site file | site/index.html, {mb:.1f} MB ({'fits' if mb <= 16 else 'too big for'} a claude.ai artifact) |")
        if mb > 16:
            problems.append("Site file is over 16 MB: run  python build_site.py --db ... --out site/index.html --summary-chars 80")
    else:
        problems.append("site/index.html not built yet: run  python run_all.py build")
    lines.append("")
    lines.append("## Result\n")
    lines.append("PASS: everything reconciles." if not problems else "CHECK:\n\n" + "\n".join(f"- {p}" for p in problems))
    if mismatches:
        lines.append("\n## Votes that do not reconcile\n")
        lines += [f"- {m}" for m in mismatches[:50]]
    report = "\n".join(lines) + "\n"
    open(os.path.join(HERE, "verify_report.md"), "w", encoding="utf-8").write(report)
    for ln in lines:
        say("  " + ln)
    say("\n  Written to verify_report.md")
    return not problems


RATE_SCOPE = "bill_key IN (SELECT bill_key FROM floor_votes WHERE key_vote = 1) OR law_number <> ''"
BATCH_FILE = os.path.join(HERE, "logs", "pending_batches.txt")


def stage_rate(args):
    """Paid, optional: rate bills with the Claude API (Batch API, half price). Run it yourself, not through Claude Code."""
    banner("Stage: rate (Claude API, Batch pricing; costs money)")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit("ANTHROPIC_API_KEY is not set in this terminal. Set it here (not in Claude Code) and run again.")
    scope = args.where or RATE_SCOPE
    run("score_bills.py", "--db", args.db, "--where", scope, "--dry-run")
    folder = os.path.join(HERE, "scoring_prompts")
    files = [f for f in os.listdir(folder) if f.endswith(".txt") and not f.startswith("_")] if os.path.isdir(folder) else []
    if not files:
        say("  Nothing to rate: every bill in scope already has a current rating.")
        return
    sys_tok = os.path.getsize(os.path.join(folder, "_system_prompt.txt")) / 4
    user_tok = sum(os.path.getsize(os.path.join(folder, f)) for f in files) / 4
    in_tok = (sys_tok * len(files) + user_tok) * 1.3          # newer tokenizer counts ~30% more than chars/4
    low = in_tok / 1e6 * 1.0 + len(files) * 1500 / 1e6 * 5.0  # Sonnet 5 Batch: $1 in, $5 out per million tokens
    high = in_tok / 1e6 * 1.0 + len(files) * 3000 / 1e6 * 5.0
    say(f"  {len(files):,} bills to rate, about {in_tok / 1e6:.1f} million input tokens.")
    say(f"  Estimated cost at Batch prices (Claude Sonnet 5): ${low:,.2f} to ${high:,.2f}.")
    try:
        answer = input("  Type YES to submit the batch, anything else to stop: ").strip()
    except EOFError:
        answer = ""
    if answer != "YES":
        say("  Stopped. Nothing was sent.")
        return
    out = []
    cmd = [sys.executable, os.path.join(HERE, "score_bills.py"), "--db", args.db, "--where", scope, "--batch"]
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    proc = subprocess.Popen(cmd, cwd=HERE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)
    for raw in proc.stdout:
        line = raw.decode("utf-8", "replace").rstrip()
        out.append(line)
        say("    " + line)
    proc.wait()
    ids = [w for line in out for w in line.replace(";", " ").split() if w.startswith("msgbatch_")]
    if ids:
        with open(BATCH_FILE, "a", encoding="utf-8") as fh:
            fh.write("\n".join(sorted(set(ids))) + "\n")
        say(f"  Saved batch id(s) to logs/pending_batches.txt. Batches usually finish within a few hours;")
        say(f"  then run:  python run_all.py collect")


def stage_collect(args):
    banner("Stage: collect (write finished Claude API ratings, rebuild the site)")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit("ANTHROPIC_API_KEY is not set in this terminal. Set it here and run again.")
    ids = [x.strip() for x in open(BATCH_FILE, encoding="utf-8")] if os.path.exists(BATCH_FILE) else []
    ids = [x for x in ids if x]
    if not ids:
        say("  No pending batches recorded in logs/pending_batches.txt.")
        return
    for bid in ids:
        run("score_bills.py", "--db", args.db, "--collect", bid)
    say("  If a batch said it is still in progress, run collect again later. Rebuilding the site now.")
    stage_build(args)


# ----------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stage", nargs="?", default="all", choices=["all", "refresh", "smoke", "rate", "collect"] + STAGES)
    ap.add_argument("--db", default="congress_119.sqlite")
    ap.add_argument("--congress", default="119")
    ap.add_argument("--since", default="2025-01-01")
    ap.add_argument("--all-types", action="store_true", help="also include simple and concurrent resolutions (H.Res., S.Res. ...)")
    ap.add_argument("--skip-excel", action="store_true", help="skip the Excel workbook (faster)")
    ap.add_argument("--no-venv", action="store_true", help="use the current Python as-is")
    ap.add_argument("--local-dir", help="catalog stage: parse Bill Status XML already on disk instead of downloading")
    ap.add_argument("--where", help="rate stage: SQL condition choosing which bills to rate (default: floor vote or became law)")
    args = ap.parse_args()
    if not args.no_venv:
        ensure_venv(sys.argv[1:])
    args.db = os.path.abspath(os.path.join(HERE, args.db)) if not os.path.isabs(args.db) else args.db
    try:                                   # python.org builds on macOS ship without root certificates; use certifi's
        import certifi
        os.environ.setdefault("SSL_CERT_FILE", certifi.where())
    except ImportError:
        pass

    global LOG
    os.makedirs(os.path.join(HERE, "logs"), exist_ok=True)
    LOG = open(os.path.join(HERE, "logs", f"run-{dt.datetime.now():%Y%m%d-%H%M%S}-{args.stage}.log"), "w", encoding="utf-8")
    t0 = time.time()
    say(f"Plain Congress build: stage '{args.stage}', database {os.path.basename(args.db)}, started {dt.datetime.now():%Y-%m-%d %H:%M}")

    if args.stage == "smoke":
        stage_smoke(args)
    elif args.stage == "rate":
        stage_rate(args)
    elif args.stage == "collect":
        stage_collect(args)
    elif args.stage in ("all", "refresh"):
        if not stage_check(args):
            raise SystemExit("\nChecks failed; nothing was downloaded. Fix the items marked FAIL and run again.")
        stage_roster(args)
        stage_catalog(args, refresh=(args.stage == "refresh"))
        stage_rollcalls(args)
        stage_photos(args)
        stage_districts(args)
        stage_ratings(args)
        stage_build(args)
        stage_verify(args)
    else:
        {"check": stage_check, "roster": stage_roster, "catalog": stage_catalog, "rollcalls": stage_rollcalls, "photos": stage_photos, "districts": stage_districts,
         "ratings": stage_ratings, "build": stage_build, "verify": stage_verify}[args.stage](args)
    say(f"\nDone in {fmt_secs(time.time() - t0)}. Log: {LOG.name}")


if __name__ == "__main__":
    main()
