"""
Georgia: the Secretary of State's own records. Georgia has fourteen House seats (the 2024 lines) and the Senate seat
of class 2 (Jon Ossoff) on the November 3, 2026 ballot. A party's nominee needs a majority in the May 19 general
primary; where no one had one, the two with the most votes met in the June 16 general primary runoff.

  primary fields    the official results of the May 19, 2026 General Primary and of the June 16, 2026 General Primary
                    Runoff, from the Secretary of State's results site (results.sos.ga.gov, "Georgia Election
                    Results"). The site's own API (/results/public/api/jurisdictions/Georgia) lists its elections;
                    each election's record says whether its results are official (isOfficialResults, required here)
                    and names its "Total Votes Excel" report, a workbook on the site's file host (/cdn/results/). Its
                    "Total Votes" sheet gives, per contest ("US Senate - Rep", "US House of Representatives - District
                    7 - Dem"), each candidate's name as on the ballot, party (REP, DEM) and votes, then a "Total Votes"
                    line; its "County Results" sheet gives the same per county, and the county sums must equal the
                    statewide figures. The results carry no write-in line, and each contest's Total Votes line must
                    equal the sum of its candidates, so a field's total is its candidates' votes. "(I)", the results' mark of an incumbent, is taken off the
                    name. The parties are written out: REP Republican, DEM Democratic.
                    A field is a party primary with two candidates or more: a candidate with a majority advanced;
                    otherwise the two in the runoff advanced (noted), and the runoff, stored as its own election
                    (runoff-REP, runoff-DEM), was won by the one with more votes. The runoff's pair must be the
                    primary's top two. Both workbooks are cached whole in ballot_cache/ga/ (results only; they carry
                    no contact details), with a small JSON of each election's record.
  November ballot   the Secretary of State's "Qualifying Candidate Information" on its My Voter Page
                    (mvp.sos.ga.gov/s/qualifying-candidate-information). Its search runs only after a reCAPTCHA check
                    (the site's own setting says reCAPTCHA is active, and the server checks the answer), so a script
                    must not ask it. A person runs the search for the November 3, 2026 General Election and presses
                    the page's "Download Qualified candidates" button, which saves "Qualified Candidates.csv"; the
                    file (or several, if the offices were searched one at a time) goes in ballot_cache/ga/20261103/,
                    and this loader reads whatever is there. The file's columns are CONTEST NAME, COUNTY,
                    MUNICIPALITY, CANDIDATE NAME, CANDIDATE STATUS, POLITICAL PARTY, QUALIFIED DATE, INCUMBENT,
                    OCCUPATION, EMAIL ADDRESS and WEBSITE; only CONTEST NAME, CANDIDATE NAME, CANDIDATE STATUS and
                    POLITICAL PARTY are read, taken by name, and nothing else is ever read or kept. Qualified
                    candidates are on the ballot, in the file's own order (it prints no ballot order); withdrawn and
                    disqualified candidates are left off and counted. Parties are kept as printed (written out if
                    the file abbreviates them). The file does not name its election, so it is checked instead: one
                    Republican and one Democrat at most per race, and each must be the nominee the official results
                    give. Without the file no November candidates are stored: the nominees alone would leave off the
                    Libertarian, independent and write-in candidates.

sos.ga.gov and elections.sos.ga.gov answer scripts with a Cloudflare challenge and are not asked.
"""

import csv
import datetime as dt
import glob
import hashlib
import io
import json
import os
import re
import time
from urllib.parse import quote

import openpyxl

from ballot.common import fold, house_id, name_parts, party_code, record_source, senate_id
from ballot.lists.tx import proper
from states import net

SITE = "https://results.sos.ga.gov"
API = SITE + "/results/public/api"
PAGE = SITE + "/results/public/Georgia/elections/"
MVP = "https://mvp.sos.ga.gov/s/qualifying-candidate-information"
HAND = "20261103"
PRIMARY, RUNOFF = "2026-05-19", "2026-06-16"
ELECTIONS = {"primary": (PRIMARY, "General Primary"), "runoff": (RUNOFF, "General Primary Runoff")}
PARTY = {"REP": "Republican", "DEM": "Democratic"}
CONTEST = re.compile(r"^US (?:Senate|House of Representatives - District (\d+)) - (Rep|Dem)$")
LIST_COLS = ("CONTEST NAME", "CANDIDATE NAME", "CANDIDATE STATUS", "POLITICAL PARTY")
ABBR = {"REP": "Republican", "DEM": "Democratic", "LIB": "Libertarian", "IND": "Independent", "GRN": "Green", "GRE": "Green"}
GONE = ("withdr", "disqual", "remov", "deceas", "denied", "reject")
SUFFIX = re.compile(r"(JR|SR|II|III|IV|V)\.?", re.I)
CAPS_NOTE = "Georgia's list prints names in capitals; they are shown here in ordinary capitals."
WRITE_IN_NOTE = "Write-in candidate: the name is not printed on the ballot."


def race_of(office):
    """('2026-GA-H07', 'DEM') from 'US House of Representatives - District 7 - Dem'; None for any other office."""
    m = CONTEST.match((office or "").strip())
    if not m:
        return None
    return (house_id("GA", int(m.group(1))) if m.group(1) else senate_id("GA", 2)), m.group(2).upper()


def bare(name):
    """The name as on the ballot, without the results' incumbent mark: 'Jon Ossoff (I)' -> 'Jon Ossoff'."""
    return re.sub(r"\s*\(I\)\s*$", "", re.sub(r"\s+", " ", str(name or ""))).strip()


def election_records(folder, say):
    """{kind: record} for the May 19 primary and the June 16 runoff, from the results site's own list of elections,
    each with its report workbook fetched into the cache. Kept 30 days: the results are certified."""
    meta_path = os.path.join(folder, "ga_2026_results_elections.json")
    if os.path.exists(meta_path) and time.time() - os.path.getmtime(meta_path) < 30 * 86400:
        meta = json.load(open(meta_path, encoding="utf-8"))
        if all(os.path.exists(os.path.join(folder, m["file"])) for m in meta.values()):
            return meta
    jur = json.loads(net.get(API + "/jurisdictions/Georgia", accept="application/json"))
    meta = {}
    for kind, (date, words) in ELECTIONS.items():
        found = [e for e in jur.get("elections", []) if e.get("electionDate") == date
                 and re.search(rf"\b{words}$", e["name"][0]["text"].strip()) and "recount" not in e["name"][0]["text"].lower()]
        if len(found) != 1:
            raise SystemExit(f"Georgia: the results site lists {len(found)} elections named \"{words}\" on {date}; expected one")
        eid = found[0]["publicElectionId"]
        time.sleep(1.0)
        rec = json.loads(net.get(f"{API}/elections/Georgia/{quote(eid)}", accept="application/json"))
        if not rec.get("isOfficialResults"):
            raise SystemExit(f"Georgia: the results site does not mark the {date} results official; unofficial figures are never stored")
        reports = [r for c in rec.get("publicReportCategories") or [] for r in c.get("reports") or [] if r.get("reportName") == "Total Votes Excel"]
        if len(reports) != 1:
            raise SystemExit(f"Georgia: the {date} results do not offer one \"Total Votes Excel\" report")
        url = f"{SITE}/cdn/results/{rec['jurisdictionId']}/{quote(reports[0]['blobName'])}"
        time.sleep(1.0)
        data = net.get(url, accept="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,*/*")
        if data[:2] != b"PK":
            raise SystemExit(f"Georgia: {url} did not give a workbook")
        name = f"ga_2026_{kind}_total_votes.xlsx"
        open(os.path.join(folder, name), "wb").write(data)
        meta[kind] = {"id": eid, "name": rec["name"][0]["text"], "date": rec["electionDate"], "official": rec["isOfficialResults"],
                      "last_updated": rec.get("lastUpdated"), "as_of": rec.get("asOf"), "page": PAGE + eid, "url": url,
                      "file": name, "sha256": hashlib.sha256(data).hexdigest(), "read": dt.date.today().isoformat()}
    json.dump(meta, open(meta_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return meta


def sheet(wb, title, need):
    """Rows of one sheet as dicts of the named columns only."""
    rows = wb[title].iter_rows(values_only=True)
    head = [str(c).strip() if c is not None else "" for c in next(rows)]
    if not all(k in head for k in need):
        raise SystemExit(f"Georgia: the results sheet \"{title}\" no longer has the columns {', '.join(need)}")
    idx = {k: head.index(k) for k in need}
    for r in rows:
        yield {k: (r[i] if i < len(r) else None) for k, i in idx.items()}


def contests(path):
    """({(race, party code): {"cands": [(name, votes)], "total": n}}, [differences]) for every congressional contest in
    one results workbook; the differences list the checks that failed (county sums, Total Votes lines, parties)."""
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    out, differ = {}, []
    for r in sheet(wb, "Total Votes", ("Office Name", "Ballot Name", "Party", "Total")):
        office = str(r["Office Name"] or "").strip()
        key = race_of(office)
        if not key:
            if office.startswith("US "):
                raise SystemExit(f"Georgia: a federal contest the loader does not know: {office!r}")
            continue
        c = out.setdefault(key, {"office": office, "cands": [], "total": None})
        name, votes = bare(r["Ballot Name"]), int(r["Total"] or 0)
        if name == "Total Votes":
            c["total"] = votes
            continue
        if str(r["Party"] or "").strip() != key[1]:
            differ.append(f"{office}: {name} is listed under party {r['Party']!r}")
        c["cands"].append((name, votes))
    county, county_total = {}, {}
    for r in sheet(wb, "County Results", ("County", "Office Name", "Ballot Name", "Total")):
        key = race_of(str(r["Office Name"] or ""))
        if not key:
            continue
        name, votes = bare(r["Ballot Name"]), int(r["Total"] or 0)
        if name == "Total Votes":
            county_total[key] = county_total.get(key, 0) + votes
        elif name != "Ballots Cast":
            county[(key, name)] = county.get((key, name), 0) + votes
    for key, c in out.items():
        if c["total"] != sum(v for _n, v in c["cands"]):
            differ.append(f"{c['office']}: Total Votes {c['total']} is not the sum of its candidates ({sum(v for _n, v in c['cands'])})")
        if county_total.get(key) != c["total"]:
            differ.append(f"{c['office']}: the counties add to {county_total.get(key)}, the statewide total is {c['total']}")
        for name, votes in c["cands"]:
            if county.get((key, name)) != votes:
                differ.append(f"{c['office']}: {name}'s counties add to {county.get((key, name))}, statewide {votes}")
    return out, differ


def same_person(a, b):
    """The same name, allowing for a nickname in quotes or a middle initial: same family name and first given name."""
    if fold(a) == fold(b):
        return True
    (ga, fa), (gb, fb) = name_parts(re.sub(r'"[^"]*"', "", a)), name_parts(re.sub(r'"[^"]*"', "", b))
    return bool(fa and fa == fb and ga and gb and ga[0] == gb[0])


def shown(raw):
    """(name as shown, printed in capitals?). 'Hall, Thomas' -> 'Thomas Hall'; 'Thomas D. Hall, Jr.' stays."""
    name = re.sub(r"\s+", " ", str(raw or "")).strip()
    last, sep, rest = name.partition(",")
    if sep and rest.strip() and not SUFFIX.fullmatch(rest.strip()):
        words = last.split()
        name = " ".join(rest.split() + [w for w in words if not SUFFIX.fullmatch(w)] + [w for w in words if SUFFIX.fullmatch(w)])
    caps = any(c.isalpha() for c in name) and name == name.upper()
    return (proper(name) if caps else name), caps


def list_race(contest):
    """The race a contest on the qualifying list names, 'skip' for a special election, None for a state or local office.
    The list's wording for federal offices is not known in advance, so several forms are read, and a contest that looks
    federal but cannot be read stops the loader."""
    t = re.sub(r"\s+", " ", contest or "").strip()
    federal = re.match(r"^(U\.? ?S\.?|United States)\b", t, re.I) or re.search(r"\b(Representative in Congress|Congressional District)\b", t, re.I)
    if not federal:
        return None
    if re.search(r"special|unexpired", t, re.I):
        return "skip"
    if re.search(r"\bSenat(e|or)\b", t, re.I):
        return senate_id("GA", 2)
    m = re.search(r"\b(?:District|Dist\.?)\s*(\d+)\b", t, re.I) or re.search(r"\b(\d+)(?:st|nd|rd|th)\s+(?:Congressional\s+)?District\b", t, re.I)
    if m and re.search(r"House|Representative|Congress", t, re.I):
        return house_id("GA", int(m.group(1)))
    raise SystemExit(f"Georgia: a federal contest on the qualifying list the loader cannot read: {t!r}")


def november_list(folder):
    """[(file, race, name, party, status)] in the files' own order, from every CSV saved in folder; the same row in two
    files is read once. Only the four columns in LIST_COLS are read."""
    out, seen, files = [], set(), sorted(glob.glob(os.path.join(folder, "*.csv")))
    for path in files:
        raw = open(path, "rb").read()
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = raw.decode("cp1252", "replace")
        rows = csv.reader(io.StringIO(text))
        head = [h.strip().upper() for h in next(rows, [])]
        if not all(k in head for k in LIST_COLS):
            raise SystemExit(f"Georgia: {os.path.basename(path)} is not the Qualified Candidates download (no {', '.join(LIST_COLS)} columns)")
        idx = {k: head.index(k) for k in LIST_COLS}
        for r in rows:
            rec = {k: (r[i].strip() if i < len(r) else "") for k, i in idx.items()}
            if not rec["CANDIDATE NAME"]:
                continue
            race = list_race(rec["CONTEST NAME"])
            if race is None:
                continue
            key = (race, rec["CANDIDATE NAME"], rec["POLITICAL PARTY"], rec["CANDIDATE STATUS"])
            if key in seen:
                continue
            seen.add(key)
            out.append((os.path.basename(path),) + key)
    return files, out


def load(con, cache, say=print):
    net.patient_lookups()
    folder = os.path.join(cache, "ga")
    os.makedirs(folder, exist_ok=True)
    meta = election_records(folder, say)
    primary, p_differ = contests(os.path.join(folder, meta["primary"]["file"]))
    runoff, r_differ = contests(os.path.join(folder, meta["runoff"]["file"]))
    differ = p_differ + r_differ

    rows, nominee, unsettled, nfields = [], {}, [], 0
    for (race, code), c in sorted(primary.items()):
        party, cands, total = PARTY[code], c["cands"], c["total"]
        ranked = sorted(cands, key=lambda x: -x[1])
        if len(cands) == 1:
            nominee[(race, code)] = cands[0][0]
            continue
        nfields += 1
        went = []
        if ranked[0][1] * 2 > total:
            winners = {ranked[0][0]}
            nominee[(race, code)] = ranked[0][0]
        else:
            r = runoff.get((race, code))
            if not r:
                unsettled.append(f"{race} {party}: no majority on May 19 and no runoff in the June 16 results")
                winners = set()
            else:
                pair = {n for n, _v in r["cands"]}
                if pair != {ranked[0][0], ranked[1][0]}:
                    unsettled.append(f"{race} {party}: the runoff's pair {sorted(pair)} is not the primary's top two")
                winners = went = pair
        for name, votes in cands:
            note = "Went to the June 16, 2026 runoff: no candidate won a majority on May 19." if name in went else None
            rows.append((race, f"primary-{code}", PRIMARY, name, party, party_code(party), None, 0, 0, votes,
                         round(100 * votes / total, 1) if total else None, "advanced" if name in winners else "lost",
                         None, None, "ga-sos-2026-primary-results", note))
    nrunoffs = 0
    for (race, code), c in sorted(runoff.items()):
        party, cands, total = PARTY[code], c["cands"], c["total"]
        if (race, code) not in primary:
            unsettled.append(f"{race} {party}: a runoff with no May 19 contest")
        ranked = sorted(cands, key=lambda x: -x[1])
        if len(cands) != 2 or ranked[0][1] == ranked[1][1]:
            unsettled.append(f"{race} {party}: the runoff has {len(cands)} candidates or a tie")
            continue
        nrunoffs += 1
        nominee[(race, code)] = ranked[0][0]
        for name, votes in cands:
            rows.append((race, f"runoff-{code}", RUNOFF, name, party, party_code(party), None, 0, 0, votes,
                         round(100 * votes / total, 1) if total else None, "advanced" if name == ranked[0][0] else "lost",
                         None, None, "ga-sos-2026-runoff-results", None))

    # the November ballot, from the qualifying list saved by hand
    hand = os.path.join(folder, HAND)
    files, listed = november_list(hand) if os.path.isdir(hand) else ([], [])
    general, gone, skipped, order = [], [], 0, {}
    ids = {os.path.basename(f): "ga-sos-2026-general-qualified" + (f"-{k + 1}" if len(files) > 1 else "") for k, f in enumerate(files)}
    for src, race, raw, printed, status in listed:
        if race == "skip":
            skipped += 1
            continue
        st = status.lower()
        if any(g in st for g in GONE):
            gone.append((race, raw, status))
            continue
        write_in = int("write" in (printed + " " + status).lower())
        if not (st.startswith("qualif") or write_in):
            raise SystemExit(f"Georgia: a candidate for {race} on the qualifying list has the status {status!r}; read the list again")
        name, caps = shown(raw)
        party = ABBR.get(printed.strip().upper(), printed.strip())
        if not write_in:
            order[race] = order.get(race, 0) + 1
        note = " ".join(n for n in (CAPS_NOTE if caps else "", WRITE_IN_NOTE if write_in else "") if n) or None
        general.append((race, "general", "2026-11-03", name, party, party_code(party), None if write_in else order[race], 0, write_in,
                        None, None, None, None, None, ids[src], note))
    if general:
        for race in {r[0] for r in general}:
            for code in ("R", "D"):
                two = [r[3] for r in general if r[0] == race and r[5] == code and not r[8]]
                if len(two) > 1:
                    raise SystemExit(f"Georgia: the saved list has {len(two)} candidates of one party for {race} ({', '.join(two)}); "
                                     "it looks like a primary's list, not the November 3 general election's")
        # each nominee of the official results must be the party's candidate on the November list (a race the saved
        # file does not cover at all is reported as missing, not marked)
        covered = {r[0] for r in general} | {g[0] for g in gone}
        for (race, code), name in sorted(nominee.items()):
            if race not in covered:
                continue
            on = [r[3] for r in general if r[0] == race and r[5] == code[0] and not r[8]]
            if any(same_person(x, name) for x in on):
                continue
            differ.append(f"{race}: the official results' {PARTY[code]} nominee, {name}, is not on the November list"
                          + (f" (the list's {PARTY[code]} candidate is {on[0]})" if on else ""))
            final = f"runoff-{code}" if any(r[0] == race and r[1] == f"runoff-{code}" for r in rows) else f"primary-{code}"
            rows = [r[:15] + (" ".join(x for x in (r[15], "Not on the Secretary of State's November list.") if x),)
                    if r[0] == race and r[1] == final and r[3] == name else r for r in rows]
        rows = general + rows

    with con:
        con.execute("DELETE FROM candidates WHERE race_id LIKE '2026-GA-%'")
        con.executemany("INSERT OR REPLACE INTO candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        for kind, sid in (("primary", "ga-sos-2026-primary-results"), ("runoff", "ga-sos-2026-runoff-results")):
            m = meta[kind]
            book = primary if kind == "primary" else runoff
            record_source(con, sid, path=os.path.join(folder, m["file"]), level="federal", state="GA", kind="official results",
                          agency="Georgia Secretary of State, Elections Division",
                          title=f"Georgia Election Results: {m['name']}, Total Votes (official results)",
                          url=m["url"], published=(m.get("last_updated") or "")[:10], rows=sum(len(c["cands"]) for c in book.values()),
                          note=f"The \"Total Votes Excel\" report of {m['page']}, marked official on the results site. The congressional contests "
                               "read; votes as the Total Votes sheet gives them, and every candidate's county figures add to the statewide figure"
                               + (" (except as listed: " + "; ".join(d for d in (p_differ if kind == "primary" else r_differ)) + ")" if (p_differ if kind == "primary" else r_differ) else "")
                               + ". The results carry no write-in line; each contest's Total Votes equals the sum of its candidates. The results' incumbent mark \"(I)\" is taken off the names.")
        for path in files:
            n = sum(1 for x in listed if x[0] == os.path.basename(path))
            record_source(con, ids[os.path.basename(path)], path=path, level="federal", state="GA", kind="official candidate list",
                          agency="Georgia Secretary of State, Elections Division",
                          title="Qualifying Candidate Information: November 3, 2026 General Election (Qualified Candidates download)",
                          url=MVP, rows=n,
                          note="Saved by hand from the page's own Download button: the search is behind reCAPTCHA, which only a person answers. "
                               "Columns read: contest name, candidate name, candidate status, political party; occupation, e-mail and website "
                               f"are never read. No ballot order is printed, so the file's own order is kept. Withdrawn or disqualified, left off: "
                               f"{len(gone)}" + (f"; special elections set aside: {skipped}" if skipped else "") + ".")
    n = len(general)
    if files:
        races = [r[0] for r in con.execute("SELECT race_id FROM races WHERE state = 'GA' ORDER BY race_id")]
        missing = [r for r in races if r not in {g[0] for g in general}]
        if missing:
            differ.append("no candidate on the saved November list for " + ", ".join(missing))
    tail = f"{nfields} party primaries with a field and {nrunoffs} runoffs, votes from the official results"
    if files:
        say(f"    Georgia: {len({r[0] for r in general if '-H' in r[0]})} House districts and {'the' if any('-S' in r[0] for r in general) else 'no'} "
            f"Senate race, {n} candidates on the November ballot ({len(gone)} withdrawn or disqualified left off); {tail}")
    else:
        say(f"    Georgia: the November list is not saved yet. The Secretary of State's Qualifying Candidate Information search ({MVP}) "
            f"is behind reCAPTCHA; search the November 3, 2026 General Election, press \"Download Qualified candidates\" and save the "
            f"file in {hand}. {tail}")
    for d in differ + unsettled:
        say("      " + d)
    return n
