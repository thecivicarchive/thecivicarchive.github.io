#!/usr/bin/env python3
"""
run_ballot.py - On The Ballot: who is on the ballot, race by race, from each state's own official candidate list.

    python run_ballot.py                  everything: races, fec, lists, match, people, campaign, ads, adlib, odds, local, check, site
    python run_ballot.py races            the federal races on the November 3, 2026 ballot, and each state's notes
    python run_ballot.py fec              the 2026 cycle from the FEC's bulk files, for every House and Senate candidate
    python run_ballot.py lists [ca fl]    official candidate lists (every state with a loader, or the ones named)
    python run_ballot.py match            tie candidates to their FEC numbers and to members of Congress
    python run_ballot.py people           age, offices held and a photo, from the official records
    python run_ballot.py campaign         each campaign's website and photo options (to be looked at before use)
    python run_ballot.py ads              ad spending by kind (TV, digital and streaming, print and mail, radio), campaign and outside
    python run_ballot.py adlib            the ads themselves in Google's public ad library, tied to the 2026 candidates (links, never copies)
    python run_ballot.py odds             what Polymarket and Kalshi are trading on the races listed in ballot/odds.py (information only)
    python run_ballot.py local [mn wi]    the states' own races (statewide, legislature, courts; and the county and local races of the
                                          states whose loaders reach them), every ballot/state_local_<code>.py loader, or the ones
                                          named, into ballot_local_2026.sqlite
    python run_ballot.py check            write ballot_report.md: what is loaded, from which files, what is missing
    python run_ballot.py site             build site/dev/ballot/ (its door, the Congress pages, each state's page, with its county
                                          pages where its rows reach the counties, and the states/ chooser) and the front door

The federal rows land in ballot_2026.sqlite, the states' own races in ballot_local_2026.sqlite; downloads are cached in
ballot_cache/ (FEC files in fec_cache/). Each run writes a log to logs/. Nothing here touches congress_119.sqlite. John's decisions (2026-09-29): Congress first;
official lists state by state, biggest states first; after the three-second hover the fireworks wait for a click;
polls only from pollsters in AAPOR's Transparency Initiative (not loaded yet).
"""

import datetime as dt
import importlib
import inspect
import os
import re
import subprocess
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from ballot import campaign, fec26, match, people, races  # noqa: E402
from ballot.common import CACHE, DB, STATE_NAMES, connect  # noqa: E402
from ballot.lists import LOADERS  # noqa: E402

LOG = None
LOCAL_DB = os.path.join(HERE, "ballot_local_2026.sqlite")


def say(msg=""):
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        print(msg.encode("ascii", "replace").decode("ascii"), flush=True)
    if LOG:
        LOG.write(msg + "\n")
        LOG.flush()


def python():
    venv = os.path.join(HERE, ".venv", "Scripts" if os.name == "nt" else "bin", "python.exe" if os.name == "nt" else "python")
    return venv if os.path.exists(venv) else sys.executable


def stage_races(con):
    say("== races: the federal races on the November 3, 2026 ballot")
    house, senate, special = races.build(con)
    say(f"    {house} House districts and {senate} Senate races ({special} of them special elections for the rest of a term)")


def stage_fec(con):
    say("== fec: the 2026 cycle from the FEC's bulk files")
    fec26.load(con, say=say)


def stage_lists(con, codes):
    say("== lists: each state's official candidate list")
    os.makedirs(CACHE, exist_ok=True)
    for code in codes or LOADERS:
        if code not in LOADERS:
            say(f"    {code.upper()}: no loader yet")
            continue
        importlib.import_module(f"ballot.lists.{code}").load(con, CACHE, say=say)


def stage_match(con):
    say("== match: candidates to FEC numbers and members of Congress")
    match.link(con, say=say)


def stage_people(con):
    say("== people: age, offices held and a photo, from the official records")
    people.build(con, say=say)


def stage_campaign(con):
    say("== campaign: each campaign's website (FEC Form 1) and photo options from it, to be looked at before use")
    campaign.list_websites(con, say=say)      # the states' own lists first (Minnesota's gives each campaign's site)
    campaign.websites(con, say=say)
    campaign.apply_choices(con, say=say)      # puts the websites on the people before their pages are read
    campaign.photos(con, say=say)
    campaign.issues(con, say=say)
    campaign.apply_choices(con, say=say)
    sheets, index = campaign.contact_sheet(con)
    if sheets:
        say(f"    {len(index)} candidates' photo options wait to be looked at: " + ", ".join(sheets))


def stage_ads(con):
    say("== ads: what each campaign and the outside spenders reported spending on ads, by kind (FEC bulk files)")
    importlib.import_module("ballot.ads").load(con, say=say)


def stage_adlib(con):
    say("== adlib: the ads in Google's public ad library, tied to the 2026 candidates (the page links to each; nothing is copied)")
    importlib.import_module("ballot.adlibrary").load(con, say=say)


def stage_odds(con):
    say("== odds: what Polymarket and Kalshi are trading on the races listed in ballot/odds.py (information only)")
    importlib.import_module("ballot.odds").load(con, say=say)


def local_loaders():
    """Every state's state-and-local loader: ballot/state_local_<code>.py."""
    return sorted(m.group(1) for f in os.listdir(os.path.join(HERE, "ballot")) for m in [re.fullmatch(r"state_local_([a-z]{2})\.py", f)] if m)


def stage_local(con, codes):
    """Each state's own list of its state races (and its county and local ones, where the loader reaches them) into ballot_local_2026.sqlite. Each
    loader writes only its own state's rows. Their load() signatures differ: Minnesota's takes db= as a keyword, the
    others take the database path first; both take say=. A loader that stops (Minnesota's waits for John's Secretary of
    State files) is reported and the others still run; the rows it loaded before stay as they were."""
    say("== local: each state's own list of state and local races, into ballot_local_2026.sqlite")
    con.commit()
    have = local_loaders()
    want = [c for c in (codes or have)]
    failed = []
    for code in want:
        if code not in have:
            say(f"    {code.upper()}: no state and local loader yet (ballot/state_local_{code}.py)")
            continue
        say(f"  -- {STATE_NAMES.get(code.upper(), code.upper())}")
        try:
            mod = importlib.import_module(f"ballot.state_local_{code}")
            params = inspect.signature(mod.load).parameters
            if "db" in params and "db_path" not in params:
                mod.load(say=say, db=LOCAL_DB)
            else:
                mod.load(LOCAL_DB, say=say)
        except (Exception, SystemExit) as e:      # noqa: BLE001  one state's stop is not everyone's
            failed.append(code.upper())
            say(f"    {code.upper()} stopped: {e}")
            for line in traceback.format_exc().splitlines()[-6:]:
                if LOG:
                    LOG.write("      " + line + "\n")
    if failed:
        say(f"    the loaders for {', '.join(failed)} stopped (see above); their earlier rows, if any, are unchanged. Re-run: python run_ballot.py local {' '.join(c.lower() for c in failed)}")


def stage_check(con):
    say("== check: ballot_report.md")
    q = lambda s, *p: con.execute(s, p).fetchall()
    one = lambda s, *p: con.execute(s, p).fetchone()[0]
    n = {k: one(sql) for k, sql in {
        "house": "SELECT COUNT(*) FROM races WHERE office = 'U.S. House'", "senate": "SELECT COUNT(*) FROM races WHERE office = 'U.S. Senate'",
        "special": "SELECT COUNT(*) FROM races WHERE special = 1", "states": "SELECT COUNT(DISTINCT state) FROM ballot_sources",
        "general": "SELECT COUNT(*) FROM candidates WHERE election = 'general'",
        "matched": "SELECT COUNT(*) FROM candidates WHERE election = 'general' AND fec_id IS NOT NULL",
        "primary": "SELECT COUNT(*) FROM candidates WHERE election <> 'general'", "fec": "SELECT COUNT(*) FROM fec26_candidates"}.items()}
    lines = [f"# On The Ballot: what is loaded, {dt.datetime.now():%Y-%m-%d %H:%M}", "",
             "| Part | Result |", "| --- | --- |",
             f"| Federal races | {n['house']} House, {n['senate']} Senate ({n['special']} special) |",
             f"| States with an official list loaded | {n['states']} of 50 |",
             f"| Candidates on the November ballot | {n['general']} |",
             f"| ...matched to an FEC registration | {n['matched']} |",
             f"| Primary candidates | {n['primary']} |",
             f"| FEC 2026 registrations (House and Senate) | {n['fec']:,} |", "",
             "## Sources", ""]
    for sid, state, kind, agency, title, url, fetched, sha, rows in q("SELECT source_id, state, kind, agency, title, url, fetched, sha256, rows FROM ballot_sources ORDER BY state"):
        lines.append(f"- **{STATE_NAMES.get(state, state)}** ({kind}): {agency}, {title}. {url} (fetched {fetched}, {rows:,} rows, SHA-256 {sha[:16]}...)")
    lines += ["", "## Races with no candidate list yet, by state", ""]
    for st, n in q("SELECT state, COUNT(*) FROM races r WHERE NOT EXISTS (SELECT 1 FROM candidates c WHERE c.race_id = r.race_id) GROUP BY state ORDER BY state"):
        lines.append(f"- {STATE_NAMES.get(st, st)}: {n}")
    lines += ["", "## November candidates with no FEC registration found", ""]
    for race, name, party in q("SELECT race_id, name, party FROM candidates WHERE election = 'general' AND fec_id IS NULL ORDER BY race_id"):
        lines.append(f"- {race}: {name} ({party})")
    open(os.path.join(HERE, "ballot_report.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
    say(f"    wrote ballot_report.md ({len(lines)} lines)")


def stage_site(con):
    say("== site: site/dev/ballot/")
    con.commit()
    steps = [[python(), "build_ballot_dev.py"]]
    if os.path.exists(LOCAL_DB):      # each state's own page and the states/ chooser, before the door counts them
        steps.append([python(), "build_ballot_state_dev.py"])
    else:
        say("    no ballot_local_2026.sqlite yet, so no state pages (python run_ballot.py local)")
    steps += [[python(), "build_door.py", "--out", os.path.join("site", "dev", "ballot", "index.html"), "--ballot", "--draft"],
              [python(), "build_door.py", "--out", os.path.join("site", "dev", "index.html"), "--draft"]]
    for cmd in steps:
        r = subprocess.run(cmd, cwd=HERE, capture_output=True, text=True, encoding="utf-8", errors="replace")
        for line in (r.stdout + r.stderr).splitlines():
            say("    " + (line if len(line) < 400 else line[:400] + " ..."))
        if r.returncode:
            raise SystemExit(f"    {cmd[1]} failed")


def main():
    global LOG
    args = [a.lower() for a in sys.argv[1:]]
    every = ["races", "fec", "lists", "match", "people", "campaign", "ads", "adlib", "odds", "local", "check", "site"]
    stages = [a for a in args if a in every] or every
    codes = [a for a in args if len(a) == 2 and a.upper() in STATE_NAMES]
    os.makedirs(os.path.join(HERE, "logs"), exist_ok=True)
    LOG = open(os.path.join(HERE, "logs", f"ballot-{dt.datetime.now():%Y%m%d-%H%M%S}-{'-'.join(stages)}.log"), "w", encoding="utf-8")
    con = connect(DB)
    for s in stages:
        if s == "lists":
            stage_lists(con, codes)
        elif s == "local":
            stage_local(con, codes)
        else:
            {"races": stage_races, "fec": stage_fec, "match": stage_match, "people": stage_people, "campaign": stage_campaign,
             "ads": stage_ads, "adlib": stage_adlib, "odds": stage_odds, "check": stage_check, "site": stage_site}[s](con)
    say(f"Done. Log: {LOG.name}")


if __name__ == "__main__":
    main()
