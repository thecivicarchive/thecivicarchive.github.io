"""election/readers/la_portal.py - Louisiana's results, from the Secretary of State's Voter Portal (the "Graphical election
results" app, whose data are JSON and CSV files served through one address: ElectionResults/ElectionResults/Data?blob=).

Files read (every one through election/source.py; fields allowlisted):
  <yyyymmdd>/Votes_Multiparish.htm            each multi-parish race's votes: race ID, precincts reporting and expected,
                                              absentee reporting and expected, voters qualified and voted, each choice's
                                              ID and vote total. The moving part on the night: the cheap "what's new" look
                                              asks for it (its VersionDateTime is a placeholder, so its fingerprint is the
                                              version).
  <yyyymmdd>/RacesCandidates_Multiparish.htm  the races and their choices: race ID, title, office level, number to be
                                              elected, whether it can have a runoff, each choice's ID and printed name
                                              with its party tag. Ballot questions' text is never kept.
  <yyyymmdd>/csv/ByParish_<race ID>.csv       one race's votes parish by parish (columns: Office, Parish, then one per
                                              choice, named as printed)
  ElectionDates.htm                           whether the Secretary marks the election's results official
                                              (ResultsOfficial); nothing else from it is kept.
Every race these pages read (Congress, the statewide boards, the Legislature, the appellate and supreme courts) is a
multi-parish race in Louisiana's files; single-parish contests are parish and city offices, not read here.

Louisiana's House contest on November 3 is an open primary: more than half the votes wins, otherwise the top two meet
on December 12 (the races carry CanHaveRunoff). The figures are "as reported" until ElectionDates.htm turns
ResultsOfficial to 1.

The night's election is the data folder named in the registry ("20261103"); a rehearsal names a past one ("20241105").

    python -m election.readers.la_portal --crosswalk     rebuild election/crosswalk/la.json from the ballot databases and the
                                                         Secretary's posted Nov 3 race file (one request)
    python -m election.readers.la_portal --replay        fetch the 2024 general once (kept in election_cache/replay/sources/),
                                                         read it, and check its totals against the source's own official
                                                         figures and its parish files
    python -m election.readers.la_portal --selftest      the reader's test on its fixture (no network)
"""

import argparse
import csv
import hashlib
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from election.readers import _common_n11 as K  # noqa: E402

STATE = "LA"
FAMILY = "la_portal"
FEED = "la-la_portal"
DATA = "https://voterportal.sos.la.gov/ElectionResults/ElectionResults/Data?blob="
NOV3_FOLDER = "20261103"
REPLAY_FOLDER = "20241105"
ACCEPT = "application/json, text/csv, */*"
OFFICE = "the Louisiana Secretary of State"
_LAST = {}          # the "what's new" answer, kept so fetch need not ask twice


def folder_of(entry):
    ids = K.election_ids(entry, r"\d{8}")
    return ids[0] if ids else NOV3_FOLDER


def as_list(x):
    return x if isinstance(x, list) else [x] if x else []


def ordinal(s):
    m = re.search(r"(\d+)", s or "")
    return str(int(m.group(1))) if m else ""


def key_of(title):
    """What a contest is, from the Secretary's title; None for a contest these pages do not read."""
    t = re.sub(r"\s+", " ", title or "").strip()
    if re.match(r"U\. ?S\. Senator\b", t):
        return "us_senate:special" if "unexpired" in t.lower() else "us_senate"
    m = re.match(r"U\. ?S\. Representative -- (\d+)\w* Congressional District", t)
    if m:
        return f"us_house:{int(m.group(1))}"
    m = re.match(r"PSC -- District (\d+)", t)
    if m:
        return f"public_service_commissioner:{int(m.group(1))}"
    m = re.match(r"BESE -- District (\d+)", t)
    if m:
        return f"state_board_of_education:{int(m.group(1))}"
    m = re.match(r"State Representative -- +(\d+)\w* Representative District", t)
    if m:
        return f"state_house:{int(m.group(1))}"
    m = re.match(r"State Senator -- +(\d+)\w* Senatorial District", t)
    if m:
        return f"state_senate:{int(m.group(1))}"
    m = re.match(r"Associate Justice, Supreme Court -- (\d+)\w* Supreme Court District", t)
    if m:
        return f"supreme_court:{int(m.group(1))}"
    m = re.match(r"Judge, Court of Appeal -- (\d+)\w* Circuit, (\d+)\w* Dist\.(.*)", t)
    if m:
        rest = m.group(3)
        d = re.search(r"Div\. ?([A-Z])\b", rest)
        seat = f"division {d.group(1).lower()}" if d else ("at large" if re.search(r"at[- ]large", rest, re.I) else "")
        return f"court_of_appeals:{int(m.group(1))}-{int(m.group(2))}:{seat}"
    return None


PARTY_TAG = re.compile(r"\s*\(([A-Z]{2,6})\)\s*$")
OLD_PARTY = re.compile(r"\s+(Democratic|Republican|Libertarian|Green|No Party|Other|Independent|"
                       r"American Solidarity Party|Constitution Party)$")


def split_desc(desc):
    """(name as printed, party as printed) from a choice's text: 'Steve Scalise (REP)'."""
    d = re.sub(r"\s+", " ", desc or "").strip()
    m = PARTY_TAG.search(d)
    if m:
        return d[:m.start()].strip(), m.group(1)
    m = OLD_PARTY.search(d)
    if m:
        return d[:m.start()].strip(), m.group(1)
    return d, None


def rule_of(race):
    return "open_primary" if race.get("CanHaveRunoff") == "1" else "plurality"


# ---------------------------------------------------------------------------------------------- requests


def check(src, entry):
    folder = folder_of(entry)
    r = src.get(DATA + f"{folder}/Votes_Multiparish.htm", state=STATE, accept=ACCEPT, conditional=False)
    if r.status == 404:
        return None
    body = K.body_ok(r, "the votes file")
    _LAST[folder] = body
    return {"version": hashlib.sha256(body).hexdigest()[:16], "time": None}


def in_scope_ids(races_body):
    """The race IDs to fetch parish files for: those this site reads."""
    keep = []
    cw = K.load_crosswalk(STATE).get("keys", {})
    for r in as_list(json.loads(races_body.decode("utf-8-sig"))["Races"].get("Race")):
        k = key_of(r.get("SpecificTitle"))
        if k and k in cw:
            keep.append(r["ID"])
    return keep


def discover(src, entry):
    """The Secretary's list of elections: November 3's election id and whether its results are official."""
    d = json.loads(K.body_ok(src.get(DATA + "ElectionDates.htm", state=STATE, accept=ACCEPT), "the list of elections").decode("utf-8-sig"))
    x = next((x for x in as_list(d.get("Dates", {}).get("Date")) if x.get("ElectionDate") == "11/03/2026"), None)
    if not x:
        return {"note": "the Secretary's list has no November 3, 2026 election"}
    return {"nov3_id": f"PKElectionID {x.get('PKElectionID')}; folder {NOV3_FOLDER}",
            "note": "results marked official" if x.get("ResultsOfficial") == "1" else "results not yet official"}


def fetch(src, entry, version):
    folder = folder_of(entry)
    out = []
    votes = _LAST.pop(folder, None)
    if votes is None or hashlib.sha256(votes).hexdigest()[:16] != version:
        votes = K.body_ok(src.get(DATA + f"{folder}/Votes_Multiparish.htm", state=STATE, accept=ACCEPT), "the votes file")
    out.append((DATA + f"{folder}/Votes_Multiparish.htm", votes))
    races = K.body_ok(src.get(DATA + f"{folder}/RacesCandidates_Multiparish.htm", state=STATE, accept=ACCEPT), "the race file")
    out.append((DATA + f"{folder}/RacesCandidates_Multiparish.htm", races))
    dates = src.get(DATA + "ElectionDates.htm", state=STATE, accept=ACCEPT)
    if dates.ok:
        out.append((DATA + "ElectionDates.htm", dates.body))
    for rid in in_scope_ids(races):
        r = src.get(DATA + f"{folder}/csv/ByParish_{rid}.csv", state=STATE, accept=ACCEPT)
        if r.ok:
            out.append((DATA + f"{folder}/csv/ByParish_{rid}.csv", r.body))
        elif r.refused:
            K.body_ok(r, "a parish file")
    return out


# ---------------------------------------------------------------------------------------------- reading


def _json(files, needle):
    _n, b = K.file_named(files, needle)
    return json.loads(b.decode("utf-8-sig")) if b is not None else None


def official_flag(files, folder):
    d = _json(files, "ElectionDates.htm")
    if not d:
        return None
    day = f"{folder[4:6]}/{folder[6:]}/{folder[:4]}"
    for x in as_list(d.get("Dates", {}).get("Date")):
        if x.get("ElectionDate") == day:
            return x.get("ResultsOfficial") == "1"
    return None


def folder_in(files):
    for n, _b in files:
        m = re.search(r"(\d{8})[/_](?:Votes|RacesCandidates)_Multiparish", str(n))
        if m:
            return m.group(1)
    return None


def read(files, entry):
    folder = folder_in(files) or folder_of(entry)
    nov3 = folder == NOV3_FOLDER
    C = K.Contests(STATE, nov3=nov3)
    races = _json(files, "RacesCandidates_Multiparish")
    votes = _json(files, "Votes_Multiparish")
    if not races or not votes:
        C.problems.append("the race file or the votes file is missing")
        return C.reading(FEED)
    try:
        vby = {v["ID"]: v for v in as_list(votes["Races"].get("Race"))}
        rlist = as_list(races["Races"].get("Race"))
    except (KeyError, TypeError, AttributeError) as e:
        C.problems.append(f"the files' layout changed ({e.__class__.__name__})")
        return C.reading(FEED)
    for r in rlist:
        title = re.sub(r"\s+", " ", r.get("SpecificTitle") or "").strip()
        rid = C.race_for(key_of(title), title, r.get("ID"))
        if not rid:
            continue
        v = vby.get(r["ID"])
        if v is None:
            C.problems.append(f"race {r['ID']} ({title}) has no votes in the votes file")
            continue
        c = C.contest(rid, r["ID"], title, rule=rule_of(r), seats=int(r.get("NumberToBeElected") or 1))
        C.unit(c, "all", "race", "the whole contest")
        ids = {}
        for i, ch in enumerate(as_list(r.get("Choice"))):
            name, party = split_desc(ch.get("Desc"))
            ids[ch["ID"]] = (C.choice(c, name, party, order=i + 1), ch.get("Desc"))
        for ch in as_list(v.get("Choice")):
            if ch.get("ID") not in ids:
                C.problems.append(f"race {r['ID']}: a vote line names a choice the race file does not list")
                continue
            C.row(c, "all", ids[ch["ID"]][0], int(ch.get("VoteTotal") or 0))
        C.report(c, "all", v.get("PrecinctsReporting"), v.get("PrecinctsExpected"),
                 ballots=int(v["VoterCountVoted"]) if str(v.get("VoterCountVoted") or "").isdigit() else None,
                 registered=int(v["VoterCountQualified"]) if str(v.get("VoterCountQualified") or "").isdigit() else None)
        ab_in, ab_all = v.get("NumAbsenteeReporting"), v.get("NumAbsenteeExpected")
        if ab_in is not None and ab_all is not None and ab_in != ab_all:
            C.notes.append(f"{rid}: {ab_in} of {ab_all} absentee reports in")
        # parish by parish
        _n, pb = K.file_named(files, f"ByParish_{r['ID']}.csv")
        if pb is None:
            continue
        rows = list(csv.reader(io.StringIO(pb.decode("utf-8-sig"))))
        head = rows[0] if rows else []
        by_desc = {d: k for k, d in ids.values()}
        if head[:2] != ["Office", "Parish"] or any(h not in by_desc for h in head[2:]):
            C.problems.append(f"race {r['ID']}: its parish file does not name the race file's choices")
            continue
        c["units_all"] = 0
        for row in rows[1:]:
            if len(row) < 2 or not row[1].strip():
                continue
            fips = K.county_unit(STATE, row[1])
            if not fips:
                C.problems.append(f"race {r['ID']}: the parish {row[1]!r} is not one of Louisiana's 64")
                continue
            C.unit(c, fips, "county", row[1].strip(), parent=STATE, map_id=fips)
            c["units_all"] += 1
            for h, x in zip(head[2:], row[2:]):
                C.row(c, fips, by_desc[h], int(x.replace(",", "") or 0))
    off = official_flag(files, folder)
    if off:
        C.notes.append("the Secretary marks these results official")
    sha = hashlib.sha256(K.file_named(files, "Votes_Multiparish")[1]).hexdigest()[:16]
    return C.reading(FEED, source_time=None, source_version=sha)


# ---------------------------------------------------------------------------------------------- rehearsals


def units(files):
    """[(parish, county code, size)] for a rehearsal: every parish in the parish files, sized by its votes."""
    size = {}
    for n, b in (files.items() if isinstance(files, dict) else files):
        if "ByParish_" in str(n) and str(n).endswith(".csv"):
            rows = list(csv.reader(io.StringIO(b.decode("utf-8-sig"))))
            for row in rows[1:]:
                if len(row) > 2:
                    size[row[1]] = size.get(row[1], 0) + sum(int(x.replace(",", "") or 0) for x in row[2:])
    return [(p, K.county_unit(STATE, p) or "", n) for p, n in sorted(size.items())]


def reveal(files, keep, step):
    """The files as they would have stood with only the kept parishes in: parish rows of the others left out, each
    race's totals the sum of its kept parishes, its precincts in as the same share of its votes."""
    files = dict(files)
    sums, share = {}, {}
    out = {}
    for n, b in files.items():
        if "ByParish_" in n and n.endswith(".csv"):
            rid = re.search(r"ByParish_(\d+)\.csv", n).group(1)
            rows = list(csv.reader(io.StringIO(b.decode("utf-8-sig"))))
            kept = [rows[0]] + [r for r in rows[1:] if len(r) > 1 and r[1] in keep]
            full = sum(int(x.replace(",", "") or 0) for r in rows[1:] for x in r[2:])
            got = sum(int(x.replace(",", "") or 0) for r in kept[1:] for x in r[2:])
            sums[rid] = {h: sum(int(r[i].replace(",", "") or 0) for r in kept[1:]) for i, h in enumerate(rows[0]) if i >= 2}
            share[rid] = (got / full) if full else 0
            buf = io.StringIO()
            csv.writer(buf, quoting=csv.QUOTE_ALL, lineterminator="\r\n").writerows(kept)
            out[n] = buf.getvalue().encode("utf-8")
    races = next((json.loads(b.decode("utf-8-sig")) for n, b in files.items() if "RacesCandidates_Multiparish" in n), None)
    desc = {}
    if races:
        for r in as_list(races["Races"].get("Race")):
            desc[r["ID"]] = {c["ID"]: c["Desc"] for c in as_list(r.get("Choice"))}
    for n, b in files.items():
        if "Votes_Multiparish" in n:
            v = json.loads(b.decode("utf-8-sig"))
            for r in as_list(v["Races"].get("Race")):
                if r["ID"] in sums:
                    for ch in as_list(r.get("Choice")):
                        ch["VoteTotal"] = str(sums[r["ID"]].get(desc.get(r["ID"], {}).get(ch["ID"]), 0))
                    r["PrecinctsReporting"] = str(round(int(r["PrecinctsExpected"]) * share[r["ID"]]))
                    r["VoterCountVoted"] = str(round(int(r.get("VoterCountVoted") or 0) * share[r["ID"]]))
                else:
                    for ch in as_list(r.get("Choice")):
                        ch["VoteTotal"] = "0"
                    r["PrecinctsReporting"] = "0"
            out[n] = json.dumps(v).encode("utf-8")
        elif n not in out:
            out[n] = b
    return out


# ---------------------------------------------------------------------------------------------- crosswalk, replay, self-test


def build_crosswalk(src=None, say=print):
    from election.source import Source
    src = src or Source()
    body = K.body_ok(src.get(DATA + f"{NOV3_FOLDER}/RacesCandidates_Multiparish.htm", state=STATE, accept=ACCEPT), "the race file")
    posted = []
    for r in as_list(json.loads(body.decode("utf-8-sig"))["Races"].get("Race")):
        title = re.sub(r"\s+", " ", r.get("SpecificTitle") or "").strip()
        posted.append({"id": r["ID"], "title": title, "key": key_of(title),
                       "names": [split_desc(c.get("Desc"))[0] for c in as_list(r.get("Choice"))]})
    return K.build_crosswalk(STATE, "Voter Portal Data?blob=20261103/RacesCandidates_Multiparish.htm", (
        "Louisiana's races on the November 3, 2026 ballot that the Election Night pages read (Congress from ballot_2026.sqlite; "
        "the statewide boards, the Legislature and the appellate and supreme courts from ballot_local_2026.sqlite), each with the "
        "key a contest of the Secretary of State's results files is tied by (read from its title) and the candidates as filed; "
        "and the Secretary's posted Nov 3 race file tied to them. A race the posted file does not carry was decided without a "
        "contest (one candidate qualified) or is not on this ballot."), feed_contests=posted, say=say,
        feed_note="Races with one qualified candidate are elected unopposed and do not appear in the results files.")


def fixture_dir():
    return os.path.join(K.FIXTURE_DIR, "la")


def replay(say=print, refetch=False):
    """The 2024 general: fetched once through the reader into the replay sources folder, read, and checked: each race's
    statewide totals equal the sum of its parish rows, every precinct in, and the Secretary marks it official."""
    from election import replay as R
    from election.source import Source
    final = os.path.join(K.REPLAY_SOURCES, f"la-{REPLAY_FOLDER}")
    entry = {"election": {"nov3_id": REPLAY_FOLDER}}
    if refetch or not os.path.isdir(final):
        src = Source()
        sig = check(src, entry)
        R.save_final(fetch(src, entry, sig["version"]), final)
    files = [(k, v) for k, v in R.load_final(final).items()]
    return check_reading(read(files, entry), files, REPLAY_FOLDER, say)


def check_reading(rd, files, folder, say, need_official=True):
    ok = True
    if rd["problems"]:
        say("  FAIL problems: " + "; ".join(rd["problems"][:5]))
        ok = False
    off = official_flag(files, folder)
    if need_official and off is not True:
        say(f"  FAIL the Secretary does not mark {folder} official")
        ok = False
    n_bad = 0
    for c in rd["contests"]:
        whole, parts = {}, {}
        for r in c["rows"]:
            (whole if r["unit"] == "all" else parts)[r["choice"]] = (whole if r["unit"] == "all" else parts).get(r["choice"], 0) + r["votes"]
        rep = next((x for x in c["reporting"] if x["unit"] == "all"), {})
        if whole != parts or rep.get("in") != rep.get("all"):
            n_bad += 1
            say(f"  FAIL {c['race_id']}: statewide {sum(whole.values()):,} against parishes {sum(parts.values()):,}; "
                f"{rep.get('in')} of {rep.get('all')} precincts")
    ok = ok and n_bad == 0 and bool(rd["contests"])
    votes = sum(r["votes"] for c in rd["contests"] for r in c["rows"] if r["unit"] == "all")
    say(f"  {'ok  ' if ok else 'FAIL'} Louisiana {folder}: {len(rd['contests'])} contests read ({votes:,} votes), each statewide total "
        f"equal to its parish rows and every precinct in; the Secretary marks the results official: {off}; "
        f"{len(rd['unmatched'])} contests listed, not read")
    return ok


def make_fixture(say=print):
    """A small fixture from the 2024 replay files: the Senate-less 2024 general's House 1st and 4th districts."""
    from election import replay as R
    final = os.path.join(K.REPLAY_SOURCES, f"la-{REPLAY_FOLDER}")
    files = R.load_final(final)
    keep_ids = {"67171", "67174"}
    out = {}
    for n, b in files.items():
        if "ByParish_" in n:
            if re.search(r"ByParish_(\d+)", n).group(1) in keep_ids:
                out[n] = b
        elif "Multiparish" in n:
            d = json.loads(b.decode("utf-8-sig"))
            d["Races"]["Race"] = [r for r in as_list(d["Races"]["Race"]) if r["ID"] in keep_ids]
            out[n] = json.dumps(d, ensure_ascii=False).encode("utf-8")
        elif "ElectionDates" in n:
            d = json.loads(b.decode("utf-8-sig"))
            d["Dates"]["Date"] = [x for x in as_list(d["Dates"]["Date"]) if x.get("ElectionDate") == "11/05/2024"]
            out[n] = json.dumps(d).encode("utf-8")
    fd = fixture_dir()
    os.makedirs(fd, exist_ok=True)
    for n, b in out.items():
        p = os.path.join(fd, *n.split("/"))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "wb").write(b)
    say(f"  fixture written: {len(out)} files in {fd}")


def selftest(say=print):
    """The fixture (two 2024 House races, official) read and checked, and a partial reveal that still adds up."""
    from election import replay as R
    fd = fixture_dir()
    if not os.path.isdir(fd):
        say("  FAIL no fixture")
        return False
    files = list(R.load_final(fd).items())
    ok = check_reading(read(files, {"election": {"nov3_id": REPLAY_FOLDER}}), files, REPLAY_FOLDER, say)
    us = units(files)
    half = {u[0] for u in us[: len(us) // 2]}
    part = list(reveal(files, half, 1).items())
    rd = read(part, {"election": {"nov3_id": REPLAY_FOLDER}})
    sums = [sum(r["votes"] for r in c["rows"] if r["unit"] == "all") == sum(r["votes"] for r in c["rows"] if r["unit"] != "all")
            for c in rd["contests"]]
    ok2 = bool(sums) and all(sums) and not rd["problems"]
    say(f"  {'ok  ' if ok2 else 'FAIL'} a rehearsal step with {len(half)} of {len(us)} parishes in reads and adds up")
    return ok and ok2


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--crosswalk", action="store_true")
    ap.add_argument("--replay", action="store_true")
    ap.add_argument("--refetch", action="store_true")
    ap.add_argument("--fixture", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    ok = True
    if a.crosswalk:
        build_crosswalk()
    if a.replay:
        ok = replay(refetch=a.refetch) and ok
    if a.fixture:
        make_fixture()
    if a.selftest:
        ok = selftest() and ok
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
