"""
Texas: the Secretary of State's own records.

  November ballot   the Ballot Certification Report for the November 3, 2026 general election, a PDF of 1,395 pages
                    dated August 28, 2026, read with ballot/pdftext.py. It goes county by county; under each county,
                    every office on that county's ballot and, under each office, its candidates in ballot order with
                    their party (REP, DEM, LIB, GRE, IND). The congressional races are taken from it. A district that
                    spans several counties is listed once per county, and every county's list must agree; any that
                    does not is reported and the race is left out.

  primary fields    the Official Canvass Reports of the March 3, 2026 Republican and Democratic primaries and of the
                    May 26, 2026 Republican and Democratic primary runoffs, from the Secretary of State's election
                    results system (goelect.txelections.civixapps.com, "Civix Election Night Results", the page the
                    Secretary's Election Results page links as "Election Results (2025-current)"). The system's list
                    of elections (/api-ivis-system/api/s3/enr/electionConstants, base64 JSON) marks each election's
                    results official ("O": "Y", required here); each election's record names the reports it offers,
                    and its "OfficialCanvassReport" comes as a PDF (base64 in JSON) headed "Texas Secretary of State,
                    Official Canvass Report": per office, each candidate's name as on the ballot, party (REP, DEM),
                    canvass votes and percent, then a Total line. A long name runs onto a second line; it is joined.
                    The report carries no write-in line for these offices, so a field's total is its candidates'
                    votes, and each Total line must equal their sum. The election record's
                    own federal figures must equal the report's, race by race. "(I)", the report's mark of an
                    incumbent, is taken off the name.
                    A field is a party primary with two candidates or more. A nominee needs a majority; a candidate
                    with one advanced. Otherwise the two with the most votes met in the May 26 runoff: both advanced
                    (noted), and the runoff, stored as its own election (runoff-REP, runoff-DEM), was won by the one
                    with more votes. The runoff's pair must be the primary's top two. Where no one had a majority and
                    the runoff canvass has no contest for the nomination (two Republican fields, districts 23 and 32),
                    the leader advanced only because the November certification names the leader and not the
                    runner-up, and both rows say so; why no runoff was held is not in these records, so the page
                    does not say. The four reports are cached in
                    ballot_cache/tx/ (results only; they carry no contact details), with the election records'
                    federal sections and a small JSON of each election's record.

results.texas-election.com (the 2019-2024 results site) answers scripts with a Cloudflare challenge and is not asked.

The certification and the canvass print names in capitals; the page shows them in ordinary capitals (a member of
Congress with the spelling the congress-legislators roster gives), and says so.
"""

import base64
import datetime as dt
import hashlib
import json
import os
import re
import time

from ballot.common import fold, house_id, name_parts, party_code, record_source, senate_id
from ballot.pdftext import lines
from states import net

URL = "https://www.sos.texas.gov/elections/forms/2026-ballot-cert.pdf"
PARTIES = {"REP": "Republican", "DEM": "Democratic", "LIB": "Libertarian", "GRE": "Green", "IND": "Independent", "W-I": "Write-in"}
HEADER = re.compile(r"^(Texas Secretary of State|Ballot Certification Report|2026 NOVEMBER GENERAL ELECTION|November 03, 2026)$|"
                    r"^\d\d/\d\d/\d{4} \d\d:\d\d [AP]M Page \d+ of \d+$")
SMALL = {"DE", "LA", "DEL", "VAN", "VON", "DER"}

ENR = "https://goelect.txelections.civixapps.com"
API = ENR + "/api-ivis-system/api/s3/enr"
REPORTS_PAGE = ENR + "/ivis-enr-ui/reports"
PRIMARY, RUNOFF = "2026-03-03", "2026-05-26"
ELECTIONS = {      # (kind, party code): (date, the election's name as the results system lists it, its type there)
    ("primary", "REP"): (PRIMARY, "2026 REPUBLICAN PRIMARY ELECTION", "P"),
    ("primary", "DEM"): (PRIMARY, "2026 DEMOCRATIC PRIMARY ELECTION", "P"),
    ("runoff", "REP"): (RUNOFF, "2026 REPUBLICAN PRIMARY RUNOFF ELECTION", "RU"),
    ("runoff", "DEM"): (RUNOFF, "2026 DEMOCRATIC PRIMARY RUNOFF ELECTION", "RU"),
}
CANVASS_HEAD = re.compile(r"^(Texas Secretary of State|Official Canvass Report|2026 (REPUBLICAN|DEMOCRATIC) PRIMARY( RUNOFF)? ELECTION|"
                          r"(March 03|May 26), 2026|VOTER|OFFICE NAME CANVASS CANVASS TURNOUT|REGISTRATION|VOTES PERCENT|COUNT)$")
STAMP = re.compile(r"^(\d\d/\d\d/\d{4}) \d\d:\d\d [AP]M Page (\d+) of (\d+)$")
RUNOFF_NOTE = "Went to the May 26, 2026 runoff: no candidate won a majority on March 3."
NO_RUNOFF_LEAD = ("Led without a majority on March 3. The May 26 runoff canvass has no contest for this nomination, and the "
                  "Secretary of State's November certification names this candidate as the party's nominee.")
NO_RUNOFF_SECOND = "Second on March 3, a place in a runoff; the May 26 runoff canvass has no contest for this nomination."


def proper(name):
    """KEVIN MCCORMICK -> Kevin McCormick; V. ALONZO ECHAVARRIA-GARZA -> V. Alonzo Echavarria-Garza; JR. and III kept."""
    out = []
    for i, w in enumerate(name.split()):
        if re.fullmatch(r"(JR|SR)\.?", w):
            out.append(w.title())
        elif re.fullmatch(r"[IVX]+", w) and i:
            out.append(w)
        elif i and w in SMALL and i < len(name.split()) - 1:
            out.append(w.lower() if w != "LA" else "La")
        else:
            parts = []
            for p in w.split("-"):
                p2 = p.capitalize()
                p2 = re.sub(r"^Mc([a-z])", lambda m: "Mc" + m.group(1).upper(), p2)
                p2 = re.sub(r"^O'([a-z])", lambda m: "O'" + m.group(1).upper(), p2)
                parts.append(p2)
            out.append("-".join(parts))
    return " ".join(out)


def roster_names():
    """{NAME IN CAPITALS: the name as the congress-legislators roster spells it} for Texas's sitting members."""
    import sqlite3
    from ballot.common import HERE
    rec = sqlite3.connect(f"file:{os.path.join(HERE, 'congress_119.sqlite')}?mode=ro", uri=True)
    fixed = {}
    for full, first, last in rec.execute("SELECT official_full, first_name, last_name FROM legislators WHERE is_current = 1 AND state = 'TX'"):
        for form in (full, f"{first} {last}"):
            if form:
                fixed[form.upper()] = full or form
    return fixed


def canvass_name(raw, fixed):
    """The canvass's 'JOHN CORNYN (I)' -> 'John Cornyn'; a nickname in quotes keeps its capital ('"Steve"'), and
    initials written together stay capitals ('TJ WARE' -> 'TJ Ware')."""
    name = re.sub(r"\s*\(I\)\s*$", "", re.sub(r"\s+", " ", raw)).strip()
    if name in fixed:
        return fixed[name]
    words = proper(name).split()
    for i, w in enumerate(name.split()):
        if i < len(words) and re.fullmatch(r"[B-DF-HJ-NP-TV-XZ]{2,3}", w) and w not in ("JR", "SR"):
            words[i] = w
    return re.sub(r"(^|\s)([\"\u201c(])([a-z])", lambda m: m.group(1) + m.group(2) + m.group(3).upper(), " ".join(words))


def same_person(a, b):
    """The same name, allowing for a nickname in quotes or a middle initial: same family name and first given name."""
    if fold(a) == fold(b):
        return True
    (ga, fa), (gb, fb) = name_parts(re.sub(r'"[^"]*"', "", a)), name_parts(re.sub(r'"[^"]*"', "", b))
    return bool(fa and fa == fb and ga and gb and ga[0] == gb[0])


def unpack(raw):
    """The results system wraps its answers as base64 in JSON."""
    return base64.b64decode(json.loads(raw)["upload"])


def election_records(folder, say):
    """{"<kind>-<party>": record} for the two primaries and the two runoffs, each with its Official Canvass Report
    fetched into the cache. Kept 30 days: the results are canvassed."""
    meta_path = os.path.join(folder, "tx_2026_results_elections.json")
    if os.path.exists(meta_path) and time.time() - os.path.getmtime(meta_path) < 30 * 86400:
        meta = json.load(open(meta_path, encoding="utf-8"))
        if all(os.path.exists(os.path.join(folder, m[f])) for m in meta.values() for f in ("file", "federal")):
            return meta
    info = json.loads(unpack(net.get(API + "/electionConstants", accept="application/json")))["electionInfo"].get("2026", {})
    meta = {}
    for (kind, code), (date, name, etype) in ELECTIONS.items():
        found = [e for e in (info.get(etype) or {}).values() if re.sub(r"\s+", " ", e.get("N", "")).strip() == name]
        if len(found) != 1:
            raise SystemExit(f"Texas: the results system lists {len(found)} elections named \"{name}\"; expected one")
        e = found[0]
        if e.get("O") != "Y":
            raise SystemExit(f"Texas: the results system does not mark the {name} official; unofficial figures are never stored")
        time.sleep(1.0)
        rec = json.loads(net.get(f"{API}/election/{e['ID']}", accept="application/json"))
        home = json.loads(base64.b64decode(rec["Home"]))
        reports = json.loads(base64.b64decode(rec["ReportList"]))
        federal = json.loads(base64.b64decode(rec["Federal"]))
        if home.get("ElecDate") != dt.date.fromisoformat(date).strftime("%m%d%Y"):
            raise SystemExit(f"Texas: the results system dates the {name} {home.get('ElecDate')}, not {date}")
        canv = reports.get("OfficialCanvassReport") or {}
        if canv.get("view") not in (True, "true", "Y") or "pdf" not in (canv.get("fileTypes") or []):
            raise SystemExit(f"Texas: the {name} does not offer its Official Canvass Report as a PDF")
        url = f"{API}/electionReports/{e['ID']}/OfficialCanvassReport/pdf"
        time.sleep(1.0)
        pdf = unpack(net.get(url, accept="application/json"))
        if pdf[:5] != b"%PDF-":
            raise SystemExit(f"Texas: {url} did not give a PDF")
        key = f"{kind}-{code}"
        fname, jname = f"tx_2026_{kind}_{code.lower()}_official_canvass.pdf", f"tx_2026_{kind}_{code.lower()}_federal_results.json"
        open(os.path.join(folder, fname), "wb").write(pdf)
        json.dump({"Home": home, "Federal": federal}, open(os.path.join(folder, jname), "w", encoding="utf-8"), ensure_ascii=False)
        meta[key] = {"id": e["ID"], "name": name, "date": date, "official": e["O"], "last_updated": home.get("LastUpdatedTime"),
                     "counties": home.get("CountiesReporting"), "url": url, "file": fname, "federal": jname,
                     "sha256": hashlib.sha256(pdf).hexdigest(), "read": dt.date.today().isoformat()}
    json.dump(meta, open(meta_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return meta


def race_of(office):
    """'2026-TX-S2' or '2026-TX-H07' from the canvass's office heading; None for a state or local office."""
    t = re.sub(r"\s+", " ", office).strip()
    if not re.match(r"^U\. ?S\. ", t):
        return None
    if re.fullmatch(r"U\. ?S\. SENATOR", t):
        return senate_id("TX", 2)
    m = re.fullmatch(r"U\. ?S\. REPRESENTATIVE,? DISTRICT (\d+)", t)
    if m and 1 <= int(m.group(1)) <= 38:
        return house_id("TX", int(m.group(1)))
    raise SystemExit(f"Texas: a federal office in the canvass the loader does not know: {t!r}")


def canvass(path, name, code, federal_path):
    """({race: {"office", "cands": [(name as printed, votes)], "total"}}, printed date, [differences]) for the federal
    offices of one Official Canvass Report, checked against its Total lines, its percents, its page count and the
    election record's own federal figures."""
    out, differ, office, last, printed, pages, seen = {}, [], None, None, "", 0, set()
    got_title = got_name = False
    for page, y, text in lines(path):
        seen.add(page)
        m = STAMP.match(text)
        if m:
            printed, pages = m.group(1), int(m.group(3))
            continue
        if CANVASS_HEAD.match(text):
            got_title |= text == "Official Canvass Report"
            got_name |= text == name
            continue
        m = re.match(rf"^(.+?) ({code}) ([\d,]+) (\d+\.\d\d) %$", text)
        if m and office:
            last = [m.group(1).strip(), int(m.group(3).replace(",", "")), float(m.group(4)), page, y]
            out[office]["cands"].append(last)
            continue
        m = re.match(r"^Total ([\d,]+)$", text)
        if m and office:
            out[office]["total"], last = int(m.group(1).replace(",", "")), None
            continue
        m = re.match(r"^(.+?) ([\d,]+) (\d+\.\d\d) %$", text)
        if m:
            office, last = race_of(m.group(1)), None
            if office:
                if office in out:
                    raise SystemExit(f"Texas: {os.path.basename(path)} lists {office} twice")
                out[office] = {"office": re.sub(r"\s+", " ", m.group(1)).strip(), "cands": [], "total": None}
            continue
        if office:
            if last and last[3] == page and 0 < last[4] - y < 16:      # the rest of a long name, on the line just below
                last[0] = f"{last[0]} {text.strip()}"
                last[4] = y
                continue
            raise SystemExit(f"Texas: a line in {os.path.basename(path)} under {office} the loader cannot read: {text!r}")
    if not (got_title and got_name):
        raise SystemExit(f"Texas: {os.path.basename(path)} is not the Official Canvass Report of the {name}")
    if pages != len(seen):
        differ.append(f"{name}: the report says {pages} pages and {len(seen)} were read")
    for race, c in out.items():
        total = sum(v for _n, v, *_ in c["cands"])
        if c["total"] != total:
            differ.append(f"{name}, {c['office']}: Total {c['total']} is not the sum of its candidates ({total})")
        for n, v, pct, *_ in c["cands"]:
            if total and abs(100 * v / total - pct) > 0.006:
                differ.append(f"{name}, {c['office']}: {n}'s printed percent {pct} is not {100 * v / total:.2f}")
        c["cands"] = [(n, v) for n, v, *_ in c["cands"]]
    fed = json.load(open(federal_path, encoding="utf-8"))["Federal"]
    record = {}
    for r in fed.get("Races") or []:
        race = race_of(r["N"])
        if race:
            record[race] = (sorted((re.sub(r"\s+", " ", x["N"]).strip(), int(x["V"])) for x in r["Candidates"]), int(r["T"]))
    for race in sorted(set(record) | set(out)):
        mine = (sorted(out[race]["cands"]), out[race]["total"]) if race in out else None
        if record.get(race) != mine:
            differ.append(f"{name}, {race}: the election record's figures differ from the canvass report's")
    stamp = dt.datetime.strptime(printed, "%m/%d/%Y").strftime("%Y-%m-%d") if printed else ""
    return out, stamp, differ


def primaries(folder, fixed, general, say):
    """(rows, per-election source facts, the summary's words, differences) for the March 3 primaries and May 26 runoffs."""
    meta = election_records(folder, say)
    books, differ = {}, []
    for (kind, code), (_date, name, _t) in ELECTIONS.items():
        m = meta[f"{kind}-{code}"]
        races, stamp, d = canvass(os.path.join(folder, m["file"]), name, code, os.path.join(folder, m["federal"]))
        books[(kind, code)] = races
        m["printed"] = stamp
        differ += d
    rows, nominee, unsettled, norunoff, nfields, nrunoffs = [], {}, [], [], 0, 0
    for code in ("REP", "DEM"):
        party = PARTIES[code]
        primary, runoff = books[("primary", code)], books[("runoff", code)]
        for race, c in sorted(primary.items()):
            cands, total = c["cands"], c["total"]
            ranked = sorted(cands, key=lambda x: -x[1])
            if len(cands) == 1:
                nominee[(race, code)] = ("primary", cands[0][0])
                continue
            nfields += 1
            went, notes = set(), {}
            if ranked[0][1] * 2 > total:
                winners = {ranked[0][0]}
                nominee[(race, code)] = ("primary", ranked[0][0])
            else:
                r = runoff.get(race)
                on = [g[3] for g in general if g[0] == race and g[5] == code[0] and not g[8]]
                lead, second = canvass_name(ranked[0][0], fixed), canvass_name(ranked[1][0], fixed)
                if not r and any(same_person(x, lead) for x in on) and not any(same_person(x, second) for x in on):
                    # no runoff was held for this nomination: the leader is the nominee on the November certification
                    winners = {ranked[0][0]}
                    nominee[(race, code)] = ("primary", ranked[0][0])
                    notes = {ranked[0][0]: NO_RUNOFF_LEAD, ranked[1][0]: NO_RUNOFF_SECOND}
                    norunoff.append(f"{race} {party}: no majority on March 3 and no runoff on May 26; the November certification names "
                                    f"the leader, {lead}")
                elif not r:
                    unsettled.append(f"{race} {party}: no majority on March 3 and no runoff in the May 26 canvass")
                    winners = set()
                else:
                    pair = {n for n, _v in r["cands"]}
                    if len(ranked) > 2 and ranked[1][1] == ranked[2][1]:
                        unsettled.append(f"{race} {party}: a tie for second place on March 3")
                    if pair != {ranked[0][0], ranked[1][0]}:
                        unsettled.append(f"{race} {party}: the runoff's pair {sorted(pair)} is not the primary's top two")
                    winners = went = pair
            for n, votes in cands:
                rows.append([race, f"primary-{code}", PRIMARY, canvass_name(n, fixed), party, party_code(party), None, 0, 0, votes,
                             round(100 * votes / total, 1) if total else None, "advanced" if n in winners else "lost",
                             None, None, f"tx-sos-2026-primary-{code.lower()}-canvass", RUNOFF_NOTE if n in went else notes.get(n)])
        for race, c in sorted(runoff.items()):
            cands, total = c["cands"], c["total"]
            if race not in primary:
                unsettled.append(f"{race} {party}: a runoff with no March 3 contest")
            ranked = sorted(cands, key=lambda x: -x[1])
            if len(cands) != 2 or ranked[0][1] == ranked[1][1]:
                unsettled.append(f"{race} {party}: the runoff has {len(cands)} candidates or a tie")
                continue
            nrunoffs += 1
            nominee[(race, code)] = ("runoff", ranked[0][0])
            for n, votes in cands:
                rows.append([race, f"runoff-{code}", RUNOFF, canvass_name(n, fixed), party, party_code(party), None, 0, 0, votes,
                             round(100 * votes / total, 1) if total else None, "advanced" if n == ranked[0][0] else "lost",
                             None, None, f"tx-sos-2026-runoff-{code.lower()}-canvass", None])
    # each nominee must be the party's candidate on the November certification; if not, the nominee keeps "advanced"
    # and the row says so plainly
    for (race, code), (stage, raw) in sorted(nominee.items()):
        shown = canvass_name(raw, fixed)
        on = [r[3] for r in general if r[0] == race and r[5] == code[0] and not r[8]]
        if any(same_person(x, shown) for x in on):
            continue
        differ.append(f"{race}: the {PARTIES[code]} nominee in the canvass, {shown}, is not on the November certification"
                      + (f" (it names {on[0]})" if on else ""))
        note = ("Won the nomination; the Secretary of State's November certification names " + on[0] + " as the party's candidate instead."
                if on else "Won the nomination; not on the Secretary of State's November certification.")
        for r in rows:
            if r[0] == race and r[1] == f"{stage}-{code}" and r[3] == shown:
                r[15] = " ".join(x for x in (r[15], note) if x)
    words = f"{nfields} party primaries with a field and {nrunoffs} runoffs, votes from the official canvass"
    return [tuple(r) for r in rows], meta, books, words, differ + unsettled + norunoff


def load(con, cache, say=print):
    path = os.path.join(cache, "tx_ballot_cert_2026.pdf")
    net.download(URL, path, max_age_days=30)
    races, county, office, listed = {}, None, None, {}
    for page, y, text in lines(path):
        if HEADER.match(text):
            continue
        m = re.match(r"^County (.+)$", text)
        if m:
            county, office = m.group(1).strip(), None
            continue
        m = re.match(r"^(.+?) (REP|DEM|LIB|GRE|IND|W-I)$", text)
        if m and office:
            listed.setdefault((office, county), []).append((m.group(1).strip(), m.group(2)))
            continue
        if m:
            continue
        # anything else is the next office's heading
        if re.fullmatch(r"U\. ?S\. SENATOR", text):
            office = ("S", 2)
        else:
            h = re.fullmatch(r"U\. ?S\. REPRESENTATIVE,? DISTRICT (\d+)( \(UNEXPIRED TERM\))?", text)
            office = ("H", int(h.group(1))) if h and not h.group(2) else None
    disagree = []
    for (off, cty), cands in listed.items():
        first = races.setdefault(off, (cty, cands))
        if first[1] != cands:
            disagree.append(f"{off} {first[0]} / {cty}")
    rows = []
    fixed = roster_names()      # a sitting member's name as the congress-legislators roster spells it
    for (kind, n), (_cty, cands) in sorted(races.items()):
        if any(d.startswith(f"{(kind, n)} ") for d in disagree):
            continue
        race = senate_id("TX", 2) if kind == "S" else house_id("TX", n)
        for order, (name, code) in enumerate(cands, start=1):
            party = PARTIES[code]
            rows.append((race, "general", "2026-11-03", fixed.get(name, proper(name)), party, party_code(party), order, 0, int(code == "W-I"),
                         None, None, None, None, None, "tx-sos-2026-ballot-cert",
                         "Texas's certification prints names in capitals; they are shown here in ordinary capitals."))

    # the March 3 primaries and May 26 runoffs, from the official canvass; a failure here leaves the November list as it is
    folder = os.path.join(cache, "tx")
    os.makedirs(folder, exist_ok=True)
    prows, meta, books, pwords, pdiffer = [], {}, {}, "", []
    try:
        net.patient_lookups()
        prows, meta, books, pwords, pdiffer = primaries(folder, fixed, rows, say)
    except (Exception, SystemExit) as e:  # noqa: BLE001
        pwords = f"primaries not loaded ({e})"

    with con:
        con.execute("DELETE FROM candidates WHERE race_id LIKE '2026-TX-%'")
        con.executemany("INSERT OR REPLACE INTO candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows + prows)
        record_source(con, "tx-sos-2026-ballot-cert", path=path, level="federal", state="TX", kind="official candidate list",
                      agency="Texas Secretary of State", title="Ballot Certification Report, 2026 November General Election (certified August 28, 2026)",
                      url=URL, published="2026-08-28", rows=len(rows),
                      note=f"Read county by county from the PDF; {len(listed):,} county lists of federal races agreed" + (f"; {len(disagree)} disagreed" if disagree else ""))
        if prows:
            for (kind, code), (date, name, _t) in ELECTIONS.items():
                m = meta[f"{kind}-{code}"]
                book = books[(kind, code)]
                title = name.title().replace("2026 ", "")
                record_source(con, f"tx-sos-2026-{kind}-{code.lower()}-canvass", path=os.path.join(folder, m["file"]), level="federal", state="TX",
                              kind="official results", agency="Texas Secretary of State, Elections Division",
                              title=f"Official Canvass Report: 2026 {title}, {dt.date.fromisoformat(date).strftime('%B %d, %Y').replace(' 0', ' ')}",
                              url=m["url"], published=m.get("printed", ""), rows=sum(len(c["cands"]) for c in book.values()),
                              note=f"The Official Canvass Report the Secretary of State's election results system offers for this election "
                                   f"({REPORTS_PAGE}, election {m['id']}, marked official), printed {m.get('printed', '')}. The federal offices "
                                   "read: each candidate's canvass votes, and every office's Total line equals the sum of its candidates; the "
                                   "election record's own federal figures equal the report's. The report carries no write-in line. Names "
                                   "are printed in capitals and shown in ordinary capitals; the report's incumbent mark \"(I)\" is taken off.")
    house = len({r[0] for r in rows if "-H" in r[0]})
    say(f"    Texas: {house} House districts and {'the' if any('-S' in r[0] for r in rows) else 'no'} Senate race, {len(rows)} candidates on the November ballot"
        + (f"; left out where counties disagreed: {'; '.join(disagree[:6])}" if disagree else "") + f"; {pwords}")
    for d in pdiffer:
        say("      " + d)
    return len(rows)
