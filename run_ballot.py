#!/usr/bin/env python3
"""
run_ballot.py - On The Ballot: who is on the ballot, race by race, from each state's own official candidate list.

    python run_ballot.py                  everything: races, fec, lists, match, check, site
    python run_ballot.py races            the federal races on the November 3, 2026 ballot, and each state's notes
    python run_ballot.py fec              the 2026 cycle from the FEC's bulk files, for every House and Senate candidate
    python run_ballot.py lists [ca fl]    official candidate lists (every state with a loader, or the ones named)
    python run_ballot.py match            tie candidates to their FEC numbers and to members of Congress
    python run_ballot.py check            write ballot_report.md: what is loaded, from which files, what is missing
    python run_ballot.py site             build site/dev/ballot/ (its door and the Congress pages) and the front door

Everything lands in ballot_2026.sqlite; downloads are cached in ballot_cache/ (FEC files in fec_cache/). Each run
writes a log to logs/. Nothing here touches congress_119.sqlite. John's decisions (2026-09-29): Congress first;
official lists state by state, biggest states first; after the three-second hover the fireworks wait for a click;
polls only from pollsters in AAPOR's Transparency Initiative (not loaded yet).
"""

import datetime as dt
import importlib
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from ballot import campaign, fec26, match, people, races  # noqa: E402
from ballot.common import CACHE, DB, STATE_NAMES, connect  # noqa: E402
from ballot.lists import LOADERS  # noqa: E402

LOG = None


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
    campaign.websites(con, say=say)
    campaign.photos(con, say=say)
    campaign.apply_choices(con, say=say)
    sheets, index = campaign.contact_sheet(con)
    if sheets:
        say(f"    {len(index)} candidates' photo options wait to be looked at: " + ", ".join(sheets))


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
    for cmd in ([python(), "build_ballot_dev.py"],
                [python(), "build_door.py", "--out", os.path.join("site", "dev", "ballot", "index.html"), "--ballot", "--draft"],
                [python(), "build_door.py", "--out", os.path.join("site", "dev", "index.html"), "--draft"]):
        r = subprocess.run(cmd, cwd=HERE, capture_output=True, text=True, encoding="utf-8", errors="replace")
        for line in (r.stdout + r.stderr).splitlines():
            say("    " + (line if len(line) < 400 else line[:400] + " ..."))
        if r.returncode:
            raise SystemExit(f"    {cmd[1]} failed")


def main():
    global LOG
    args = [a.lower() for a in sys.argv[1:]]
    every = ["races", "fec", "lists", "match", "people", "campaign", "check", "site"]
    stages = [a for a in args if a in every] or every
    codes = [a for a in args if len(a) == 2 and a.upper() in STATE_NAMES]
    os.makedirs(os.path.join(HERE, "logs"), exist_ok=True)
    LOG = open(os.path.join(HERE, "logs", f"ballot-{dt.datetime.now():%Y%m%d-%H%M%S}-{'-'.join(stages)}.log"), "w", encoding="utf-8")
    con = connect(DB)
    for s in stages:
        if s == "lists":
            stage_lists(con, codes)
        else:
            {"races": stage_races, "fec": stage_fec, "match": stage_match, "people": stage_people, "campaign": stage_campaign,
             "check": stage_check, "site": stage_site}[s](con)
    say(f"Done. Log: {LOG.name}")


if __name__ == "__main__":
    main()
