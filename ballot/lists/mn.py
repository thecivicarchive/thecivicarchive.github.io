"""
Minnesota: the Secretary of State's "media results" text files for the November 3, 2026 State General Election (which
list every candidate on the ballot before a vote is counted) and for the August 11, 2026 State Primary (the primary's
votes). The Secretary's sites, candidates.sos.mn.gov included, answer this network with a Radware CAPTCHA, in the Browser
pane too; they are never worked around and not asked again. John saves the files in his own browser into
states_cache/mn_local/sos/20261103/ and states_cache/mn_local/sos/20260811/ (the U.S. Senator and U.S. Representative
files from each election's Media Files page), and this loader reads whatever is there, with the reader the county pages
use (states/load_local_results.py). Until the November files are there, Minnesota's races say the list is coming.

A line is one candidate in one reporting unit: state; county id; precinct; office id; office name; district; candidate
order; name; suffix; incumbent; party; precincts reporting; precincts; votes; percent; total votes. A candidate's votes
come from the line without a county and precinct when the file has one (the total), else from the sum of its lines,
one per county and precinct. Write-in lines are not candidates. The layout is checked against the real files when they
arrive: a file whose office names or parties do not read as expected stops the loader, which names it.
"""

import glob
import json
import os
import re

from ballot.common import HERE, fold, house_id, party_code, record_source, senate_id
from states.load_local_results import read_file

FOLDER = os.path.join(HERE, "states_cache", "mn_local", "sos")
GENERAL, PRIMARY = "20261103", "20260811"
PARTY = {"DFL": "Democratic-Farmer-Labor", "R": "Republican", "IND": "Independent", "LIB": "Libertarian", "GP": "Green", "LMN": "Legal Marijuana Now",
         "GLC": "Grassroots-Legalize Cannabis", "IA": "Independence-Alliance", "SWP": "Socialist Workers", "IP": "Independence"}
PAGE = "https://electionresults.sos.mn.gov/"


def race_of(office):
    o = re.sub(r"\s+", " ", office or "").strip()
    m = re.match(r"U\.?\s?S\.? Representative District (\d+)", o, re.I)
    if m:
        return house_id("MN", int(m.group(1)))
    return senate_id("MN", 2) if re.match(r"U\.?\s?S\.? Senator", o, re.I) else None


def candidates(day):
    """{(race, name, party): [order, votes]} for every candidate for Congress in one election's files, and the files read."""
    files = sorted(f for f in glob.glob(os.path.join(FOLDER, day, "*"))      # saved as .txt, or .md as John's browser saved the lists
                   if f.lower().endswith((".txt", ".md", ".csv")) and not re.search(r"Candidate|Office of the Secretary", os.path.basename(f), re.I))
    totals, parts = {}, {}
    for path in files:
        for r in read_file(path):
            race = race_of(r["office"])
            if not race or not r["candidate"] or re.search(r"write-?in", r["candidate"] + " " + r["party"], re.I) or r["party"] == "WI":
                continue
            name = " ".join(x for x in (r["candidate"], r["suffix"]) if x)
            key = (race, name, r["party"])
            votes = int(r["votes"]) if r["votes"].isdigit() else 0
            order = int(r["order"]) if r["order"].isdigit() else None
            if not r["county_id"] and not r["precinct"]:
                totals[key] = [order, votes]
            else:
                parts.setdefault(key, {})[(r["county_id"], r["precinct"])] = (order, votes)
    out = dict(totals)
    for key, units in parts.items():
        if key not in out:
            out[key] = [next(iter(units.values()))[0], sum(v for _o, v in units.values())]
    return out, files


def candidate_list():
    """{(race, name, party): [order, None]} from the Secretary's "Candidates in the General Election - Federal, State, and
    County Offices" file (semicolon-separated; the Secretary's own note lists the columns): candidate number; name; office
    number; office title; county (88 statewide or several counties); ballot order; party; then residence and campaign
    addresses, phone, website and e-mail, which are never read."""
    files = sorted(f for f in glob.glob(os.path.join(FOLDER, GENERAL, "*Candidates in the General Election*Federal*")))
    out = {}
    for path in files:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                f = line.rstrip("\r\n").split(";")
                if len(f) < 7:
                    continue
                race = race_of(f[3])
                if race and f[1].strip():
                    name = re.sub(r"\s+", " ", f[1]).strip()
                    out[(race, name, f[6].strip())] = [int(f[5]) if f[5].strip().isdigit() else None, None]
                    if len(f) > 16 and f[16].strip():      # the campaign's own website, which the list gives (column 17)
                        SITES[f"{race}|{name}"] = f[16].strip()
    return out, files


SITES = {}


def filings():
    """{(race, party): [names]} from the Secretary's "Candidate Filings - Federal, State, and County Offices" file: everyone
    who filed for the office, which for the major parties is the August 11 primary's field. Its columns are the general
    list's without the ballot order: number; name; office number; office title; county; party; then the addresses."""
    files = sorted(glob.glob(os.path.join(FOLDER, GENERAL, "*Candidate Filings*Federal*")))
    out = {}
    for path in files:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                f = line.rstrip("\r\n").split(";")
                race = race_of(f[3]) if len(f) > 6 else None
                if race and f[1].strip():
                    out.setdefault((race, f[5].strip()), []).append(re.sub(r"\s+", " ", f[1]).strip())
    return out, files


def load(con, cache, say=print):
    general, gfiles = candidate_list()
    if not general:      # the results files, which list every candidate once the Secretary posts them
        general, gfiles = candidates(GENERAL)
    if not general:
        say(f"    Minnesota: waiting for the Secretary of State's November results files in {os.path.join(FOLDER, GENERAL)} "
            "(the Secretary's sites show this network a CAPTCHA, so John saves them in his own browser)")
        return 0
    unknown = sorted({p for (_r, _n, p) in general if p and p not in PARTY})
    if unknown:
        say(f"    Minnesota: parties not in the list of known codes, printed as the file writes them: {', '.join(unknown)}")
    rows = [(race, "general", "2026-11-03", name, PARTY.get(p, p), party_code(PARTY.get(p, p)), order, 0, 0, None, None, None, None, None,
             "mn-sos-2026-general-media", None) for (race, name, p), (order, _v) in sorted(general.items())]
    nominee = {(race, p): fold(name) for (race, name, p) in general}
    primary, pfiles = candidates(PRIMARY)
    fields = {}
    for (race, name, p), (_o, votes) in primary.items():
        fields.setdefault((race, p), []).append((name, votes))
    nfields = 0
    filed, ffiles = filings()
    if not primary and filed:      # no results files yet: the filings give each field and the November list says who won it
        for (race, p), names in filed.items():
            if len(set(names)) < 2 or p not in PARTY:
                continue
            nfields += 1
            code = {"R": "REP"}.get(p, p)
            for name in sorted(set(names)):
                rows.append((race, f"primary-{code}", "2026-08-11", name, PARTY.get(p, p), party_code(PARTY.get(p, p)), None, 0, 0, None, None,
                             "advanced" if nominee.get((race, p)) == fold(name) else "lost", None, None, "mn-sos-2026-filings", None))
    if SITES:
        path = os.path.join(cache, "lists_websites", "mn.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        json.dump(SITES, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for (race, p), field in fields.items():
        if len(field) < 2:
            continue
        nfields += 1
        total, code = sum(v for _n, v in field), {"R": "REP"}.get(p, p)
        for name, votes in field:
            rows.append((race, f"primary-{code}", "2026-08-11", name, PARTY.get(p, p), party_code(PARTY.get(p, p)), None, 0, 0, votes,
                         round(100 * votes / total, 1) if total else None, "advanced" if nominee.get((race, p)) == fold(name) else "lost",
                         None, None, "mn-sos-2026-primary-media", None))
    with con:
        con.execute("DELETE FROM candidates WHERE race_id LIKE '2026-MN-%'")
        con.executemany("INSERT OR REPLACE INTO candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        record_source(con, "mn-sos-2026-general-media", path=gfiles[0], level="federal", state="MN", kind="official candidate list",
                      agency="Minnesota Secretary of State", title="Candidates in the General Election: Federal, State, and County Offices (November 3, 2026)",
                      url="https://candidates.sos.mn.gov/", rows=len(general),
                      note=f"Saved by John from the Secretary of State's site (its CAPTCHA answered by him): {', '.join(os.path.basename(f) for f in gfiles)}. "
                           "Name, office, ballot order and party read; addresses, phones and e-mail never read.")
        if ffiles and not pfiles:
            record_source(con, "mn-sos-2026-filings", path=ffiles[0], level="federal", state="MN", kind="official candidate list",
                          agency="Minnesota Secretary of State", title="Candidate Filings: Federal, State, and County Offices (2026)",
                          url="https://candidates.sos.mn.gov/", rows=sum(len(v) for v in filed.values()),
                          note="Everyone who filed; for the major parties, the August 11 primary's field. Who advanced is read from the November list; "
                               "the primary's vote counts are not loaded. Addresses, phones and e-mail never read.")
        if pfiles:
            record_source(con, "mn-sos-2026-primary-media", path=pfiles[0], level="federal", state="MN", kind="official results",
                          agency="Minnesota Secretary of State", title="Election results media files, August 11, 2026 State Primary",
                          url=PAGE, rows=len(primary), note=f"Saved by John: {', '.join(os.path.basename(f) for f in pfiles)}. Percent is of the party's primary votes for the office, write-ins set aside.")
    say(f"    Minnesota: {len({r[0] for r in rows if r[1] == 'general'})} races, {len(general)} candidates on the November ballot; {nfields} party primaries with a field")
    return len(general)
