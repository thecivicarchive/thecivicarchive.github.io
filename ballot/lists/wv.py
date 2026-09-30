"""
West Virginia: the Secretary of State's 2026 candidate listing (candidates.wvsos.gov, linked as "2026 General Candidate
Listing" from sos.wv.gov/elections), and its official results of the May 12, 2026 primary (the Secretary's results site,
hosted by Clarity Elections, linked as "2026 Primary Election" from sos.wv.gov's Historical Election Results page).

The listing is a page that fetches its rows from the Secretary's own data service (candidate-web-api/candidates, a JSON
POST with the page's own filters: the election, the office level FEDERAL, and the candidate type, R for the Regular
Candidates tab and W for the Write-In Candidates tab). Every page of rows is read and counted against the service's own
total. Each row also carries the candidate's e-mail, telephones, residential and mailing addresses, website and
committee; only these fields are kept, as each page arrives: the election, the office and its level, the party code
and party, the name as printed on the ballot (candidateBallotName), the candidate type and the filing date. The cached
copy keeps nothing else. The host leaves its issuer's certificate out of the handshake; the POST repairs that the way
states/net.get does, and no less strictly.

The November ballot is every federal row of "11/03/2026 - GENERAL 2026" on the Regular tab, in the listing's own order
(Republican, Democrat, then the others); the listing gives no ballot positions. The Write-In tab's federal rows are
declared write-in candidates: write_in 1, no ballot position, party shown as "Write-in" (the tab gives none). The
listing has no status column: a candidate who withdrew or was removed is no longer listed, so none can be counted.
Parties are printed in full, in capitals, and shown in ordinary capitals: R REPUBLICAN, D DEMOCRAT, C1 CONSTITUTION,
L LIBERTARIAN, M MOUNTAIN, IND INDEPENDENT, N NO PARTY AFFILIATION.

The primary: the same listing's "05/12/2026 - PRIMARY 2026" rows say who was on each party's primary ballot and how their
names are printed; the votes come from the results site's detail report (reports/detailxml.zip for the site's current
version): one Contest per office and party ("U.S. SENATOR - REP", "U.S. HOUSE OF REPRESENTATIVES, 1st Congressional
District - DEM"), each candidate's statewide total, and the same votes county by county. Every candidate's county votes
must add up to the statewide total, every precinct must have reported, and the candidates of each party primary must be
exactly the listing's for that party and office (names matched letters only; the report writes McNULTY and 'BRIT' where
the listing prints MCNULTY and "BRIT"). The site's summary report (reports/summary.zip) must give the same totals. The
site is headed "Official Results"; its settings and county statuses are kept beside the report, and the loader stops if
the heading ever says unofficial or a county has not completely reported. No write-in votes are reported for these
contests (the Secretary publishes primary write-in results separately, and the 2026 file is not yet posted), so a
field's total is the sum of its candidates' votes. A field is a party primary with two candidates or more; West Virginia
nominates the leader, who must be the party's candidate on the November listing.

Names are printed in capitals everywhere; the page shows them in ordinary capitals (a sitting member with the
capitals the congress-legislators roster gives the same words) and says so.
"""

import csv
import gzip
import io
import json
import os
import re
import sqlite3
import time
import zipfile
import xml.etree.ElementTree as ET
from urllib.error import URLError
from urllib.request import Request, urlopen

from ballot.common import HERE, fold, house_id, party_code, record_source, senate_id
from ballot.lists.tx import proper
from states import net

SITE = "https://candidates.wvsos.gov/"
API = "https://candidates.wvsos.gov/candidate-web-api/candidates"
ELECTIONS = {"general": ("11/03/2026 - GENERAL 2026", "11/03/2026"), "primary": ("05/12/2026 - PRIMARY 2026", "05/12/2026")}
KEEP = ("candidateType", "electionName", "electionDate", "officeName", "officeDescription", "partyCode", "partyDescription",
        "candidateBallotName", "filingDate")
CLARITY = "https://results.enr.clarityelections.com/WV/126209/"
RESULTS_PAGE = CLARITY + "web.345435/#/summary"
PRIMARY = "2026-05-12"
PAGE_SIZE = 100
CODES = {"R": "REP", "D": "DEM", "L": "LIB", "M": "MTN", "C1": "CON"}            # listing party code -> election code
RESULT_CODES = {"REP": "REP", "DEM": "DEM", "LBN": "LIB", "MTN": "MTN", "CST": "CON"}  # results party -> election code
DONE = {0: "certified", 4: "completely reported"}                              # the results site's county statuses
CAPS = "West Virginia's list prints names in capitals; they are shown here in ordinary capitals."
WRITE_IN = "Write-in candidate: the name is not printed on the ballot."


def post(payload):
    """One POST to the listing's data service, JSON in and out."""
    req = Request(API, data=json.dumps(payload).encode(), method="POST",
                  headers={"User-Agent": net.UA, "Content-Type": "application/json", "Accept": "application/json"})
    try:
        with urlopen(req, timeout=120) as r:
            return json.loads(r.read())
    except URLError as e:
        if getattr(getattr(e, "reason", None), "verify_code", None) != 20:   # 20: the server left out its issuer's certificate
            raise
        ctx = net._context_with_issuer(req.host)
        if ctx is None:
            raise
        with urlopen(req, timeout=120, context=ctx) as r:
            return json.loads(r.read())


def read_tab(election, ctype):
    """Every federal row of one election on one tab (R regular, W write-in), the kept fields only."""
    rows, page = [], 0
    while True:
        got = post({"page": page, "size": PAGE_SIZE, "candidateType": ctype, "electionName": election, "officeDescription": ["FEDERAL"]})
        if got.get("error") or not isinstance(got.get("data"), dict):
            raise SystemExit(f"West Virginia: the candidate listing's service answered with an error ({got.get('message')!r})")
        meta = got.get("meta") or {}
        rows += [{k: c.get(k) for k in KEEP} for c in got["data"].get("candidates") or []]
        if meta.get("last", True):
            break
        page += 1
        time.sleep(1.5)
    if len(rows) != meta.get("totalElements", len(rows)):
        raise SystemExit(f"West Virginia: the listing counts {meta.get('totalElements')} rows for {election} ({ctype}); {len(rows)} were read")
    fed = [r for r in rows if r["officeDescription"] == "FEDERAL" and r["electionName"] == election]
    if len(fed) != len(rows):
        raise SystemExit(f"West Virginia: the listing's service did not apply its own filters ({len(rows)} rows, {len(fed)} federal)")
    return fed


def read_list(kind, path, say):
    """The federal rows of one election, both tabs; kept on disk (kept fields only) for two days."""
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < 2 * 86400:
        return json.load(open(path, encoding="utf-8"))
    net.patient_lookups()
    election, date = ELECTIONS[kind]
    regular = read_tab(election, "R")
    time.sleep(1.5)
    write_in = read_tab(election, "W")
    for r in regular + write_in:
        if r["electionDate"] != date:
            raise SystemExit(f"West Virginia: a row of {election} is dated {r['electionDate']}")
    kept = {"election": election, "url": SITE, "service": API, "regular": regular, "write_in": write_in}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(kept, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    say(f"      {election}: {len(regular)} regular and {len(write_in)} write-in candidates for Congress")
    return kept


def race_of(office):
    office = re.sub(r"\s+", " ", office or "").strip().upper()
    if office == "U.S. SENATE":
        return senate_id("WV", 2)
    m = re.fullmatch(r"U\.S\. HOUSE OF REPRESENTATIVES - DISTRICT (\d+)", office)
    if m:
        return house_id("WV", int(m.group(1)))
    raise SystemExit(f"West Virginia: a federal office on the listing that is not read ({office!r})")


def contest_of(text):
    """(race, election code) for a federal contest of the results report."""
    t = re.sub(r"\s+", " ", text).strip()
    m = re.fullmatch(r"U\.S\. SENATOR - ([A-Z]+)", t)
    if m:
        race, party = senate_id("WV", 2), m.group(1)
    else:
        m = re.fullmatch(r"U\.S\. HOUSE OF REPRESENTATIVES, (\d+)(?:st|nd|rd|th) Congressional District - ([A-Z]+)", t, re.I)
        if not m:
            raise SystemExit(f"West Virginia: a federal contest in the results that is not read ({t!r})")
        race, party = house_id("WV", int(m.group(1))), m.group(2).upper()
    if party not in RESULT_CODES:
        raise SystemExit(f"West Virginia: a party in the results that is not read ({party!r}, {t})")
    return race, RESULT_CODES[party]


def unzip_json(raw):
    return json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)


def fetch_results(folder, say):
    """The results site's detail and summary reports, with its heading and county statuses; kept for 30 days."""
    detail, summary = os.path.join(folder, "wv_2026_primary_detailxml.zip"), os.path.join(folder, "wv_2026_primary_summary.zip")
    meta_path = os.path.join(folder, "wv_2026_primary_results_meta.json")
    if all(os.path.exists(p) for p in (detail, summary, meta_path)) and time.time() - os.path.getmtime(meta_path) < 30 * 86400:
        return detail, summary, json.load(open(meta_path, encoding="utf-8"))
    net.patient_lookups()
    ver = net.get(CLARITY + "current_ver.txt").decode("ascii", "replace").strip()
    if not ver.isdigit():
        raise SystemExit(f"West Virginia: the results site's current version is not a number ({ver[:40]!r})")
    settings = unzip_json(net.get(f"{CLARITY}{ver}/json/en/electionsettings.json"))
    time.sleep(1)
    status = unzip_json(net.get(f"{CLARITY}{ver}/json/status.json"))
    heads = []
    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k == "header" and isinstance(v, str) and v.strip():
                    heads.append(re.sub(r"<[^>]+>", "", v).strip())
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(settings)
    heading = heads[0] if len(set(heads)) == 1 else " / ".join(heads)
    if heading != "Official Results":
        raise SystemExit(f"West Virginia: the results site is not headed Official Results ({heading or 'no heading'}); "
                         "unofficial figures are never stored")
    counties = dict(zip(status["P"], status["S"]))
    meta = {"version": ver, "updated": settings.get("websiteupdatedat"), "heading": heading,
            "election": settings["settings"]["electiondetails"].get("internalname"),
            "date": settings["settings"]["electiondetails"].get("electiondate"),
            "counties": {name: DONE.get(s, f"status {s}") for name, s in counties.items()},
            "detail_url": f"{CLARITY}{ver}/reports/detailxml.zip", "summary_url": f"{CLARITY}{ver}/reports/summary.zip"}
    for url, path in ((meta["detail_url"], detail), (meta["summary_url"], summary)):
        net.download(url, path, max_age_days=0)
        if open(path, "rb").read(2) != b"PK":
            raise SystemExit(f"West Virginia: {url} is not a zip file")
    json.dump(meta, open(meta_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    say(f"      results site version {ver}, updated {meta['updated']}, headed {heading}")
    return detail, summary, meta


def primary_votes(detail, summary, meta):
    """{(race, code): [(name as reported, votes)], write-in votes} for every federal party primary; every check made."""
    if meta["election"] != "2026 Primary" or meta["date"] != "5/12/2026":
        raise SystemExit(f"West Virginia: the results site is for {meta['election']} {meta['date']}, not the 2026 primary")
    behind = {c: s for c, s in meta["counties"].items() if s not in DONE.values()}
    if len(meta["counties"]) != 55 or behind:
        raise SystemExit(f"West Virginia: not every county has completely reported ({len(meta['counties'])} counties; {behind})")
    root = ET.fromstring(zipfile.ZipFile(detail).read("detail.xml"))
    if root.findtext("ElectionName") != "2026 Primary" or root.findtext("ElectionDate") != "5/12/2026":
        raise SystemExit("West Virginia: the detail report is not the 2026 primary's")
    out = {}
    for c in root.findall("Contest"):
        if not c.get("text", "").upper().startswith("U.S."):
            continue
        race, code = contest_of(c.get("text"))
        if c.get("precinctsReported") != c.get("precinctsParticipating") or c.get("countiesReported") != c.get("countiesParticipating"):
            raise SystemExit(f"West Virginia: {c.get('text')} is not completely reported in the detail report")
        field, write_ins = [], 0
        for ch in c.findall("Choice"):
            total = int(ch.get("totalVotes"))
            by_type = sum(int(vt.get("votes")) for vt in ch.findall("VoteType"))
            by_county = sum(int(cc.get("votes")) for vt in ch.findall("VoteType") for cc in vt.findall("County"))
            if by_type != total or by_county != total:
                raise SystemExit(f"West Virginia: {ch.get('text')}'s votes in {c.get('text')} do not add up ({total}, by type {by_type}, by county {by_county})")
            if re.search(r"write[- ]?in", ch.get("text", ""), re.I):
                write_ins += total
                continue
            if RESULT_CODES.get(ch.get("party")) != code:
                raise SystemExit(f"West Virginia: {ch.get('text')} is reported under {ch.get('party')} in {c.get('text')}")
            field.append((re.sub(r"\s+", " ", ch.get("text")).strip(), total))
        if (race, code) in out:
            raise SystemExit(f"West Virginia: {c.get('text')} appears twice in the detail report")
        out[(race, code)] = (field, write_ins)
    # control: the summary report gives the same totals
    rows = list(csv.reader(io.StringIO(zipfile.ZipFile(summary).read("summary.csv").decode("utf-8-sig", "replace"))))
    head = rows[0]
    ci, ni, vi = head.index("contest name"), head.index("choice name"), head.index("total votes")
    seen = {}
    for r in rows[1:]:
        if r and r[ci].upper().startswith("U.S."):
            key = contest_of(re.sub(r" \(Vote For \d+\)$", "", r[ci]))
            seen.setdefault(key, {})[fold(r[ni])] = int(r[vi])
    for key, (field, write_ins) in out.items():
        if {fold(n): v for n, v in field} != {k: v for k, v in seen.get(key, {}).items() if "write" not in k}:
            raise SystemExit(f"West Virginia: the summary report's totals for {key} differ from the detail report's")
    if set(seen) != set(out):
        raise SystemExit("West Virginia: the summary and detail reports list different federal contests")
    return out


def load(con, cache, say=print):
    net.patient_lookups()
    folder = os.path.join(cache, "wv")
    gen_path, pri_path = os.path.join(folder, "wv_2026_general_federal.json"), os.path.join(folder, "wv_2026_primary_federal.json")
    gen = read_list("general", gen_path, say)
    pri = read_list("primary", pri_path, say)
    detail, summary, meta = fetch_results(folder, say)

    rec = sqlite3.connect(f"file:{os.path.join(HERE, 'congress_119.sqlite')}?mode=ro", uri=True)
    fixed = {}
    for full, first, last in rec.execute("SELECT official_full, first_name, last_name FROM legislators WHERE is_current = 1 AND state = 'WV'"):
        for form in (full, f"{first} {last}"):
            if form:
                fixed[fold(form)] = form
    rec.close()

    def shown(caps):
        caps = re.sub(r"\s+", " ", caps or "").strip()
        if fold(caps) in fixed:                     # the roster's capitals, only where its words are the same words
            return fixed[fold(caps)]
        return re.sub(r"(['\"(])([a-z])", lambda m: m.group(1) + m.group(2).upper(), proper(caps))

    def party_of(r):
        if not r["partyDescription"]:
            raise SystemExit(f"West Virginia: a candidate for {r['officeName']} with no party on the listing")
        return proper(r["partyDescription"])

    rows, order, nominee = [], {}, {}
    for r in gen["regular"]:
        race, party = race_of(r["officeName"]), party_of(r)
        order[race] = order.get(race, 0) + 1
        rows.append((race, "general", "2026-11-03", shown(r["candidateBallotName"]), party, party_code(party), order[race], 0, 0,
                     None, None, None, None, None, "wv-sos-2026-general-list", CAPS))
        if r["partyCode"] in CODES:
            nominee[(race, CODES[r["partyCode"]])] = fold(r["candidateBallotName"])
    for r in gen["write_in"]:
        rows.append((race_of(r["officeName"]), "general", "2026-11-03", shown(r["candidateBallotName"]), "Write-in", "W", None, 0, 1,
                     None, None, None, None, None, "wv-sos-2026-general-list", f"{WRITE_IN} {CAPS}"))

    # who was on each party's May ballot, as the listing prints them
    filed = {}
    for r in pri["regular"]:
        if r["partyCode"] not in CODES:
            raise SystemExit(f"West Virginia: a primary candidate for {r['officeName']} of a party that is not read ({r['partyCode']})")
        filed.setdefault((race_of(r["officeName"]), CODES[r["partyCode"]]), {})[fold(r["candidateBallotName"])] = (r["candidateBallotName"], party_of(r))
    if pri["write_in"]:
        raise SystemExit("West Virginia: the primary listing names write-in candidates for Congress; read how the results report them")

    votes = primary_votes(detail, summary, meta)
    if set(votes) != set(filed):
        raise SystemExit(f"West Virginia: the party primaries in the results and on the listing differ ({sorted(set(votes) ^ set(filed))})")
    fields = 0
    for (race, code), (field, write_ins) in sorted(votes.items()):
        listed = filed[(race, code)]
        if {fold(n) for n, _v in field} != set(listed):
            raise SystemExit(f"West Virginia: the results' candidates for {race} {code} are not the listing's")
        if len(field) < 2:
            continue
        fields += 1
        total = sum(v for _n, v in field) + write_ins
        leader = max(field, key=lambda nv: nv[1])
        if sum(1 for _n, v in field if v == leader[1]) > 1:
            raise SystemExit(f"West Virginia: the {race} {code} primary is tied at the top; read how it was settled")
        won = nominee.get((race, code))
        if won and won != fold(leader[0]):
            raise SystemExit(f"West Virginia: the {race} {code} primary's leader is not the party's candidate on the November listing")
        for name, v in sorted(field, key=lambda nv: -nv[1]):
            printed, party = listed[fold(name)]
            note = CAPS
            if fold(name) == fold(leader[0]) and not won:
                note = f"Not on the November list. {CAPS}"
            rows.append((race, f"primary-{code}", PRIMARY, shown(printed), party, party_code(party), None, 0, 0, v,
                         round(100 * v / total, 1) if total else None, "advanced" if fold(name) == fold(leader[0]) else "lost",
                         None, None, "wv-sos-2026-primary-results", note))

    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", meta["updated"] or "")
    updated = f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}" if m else ""
    general = [r for r in rows if r[1] == "general"]
    write_in_n = sum(1 for r in general if r[8])
    counties = sum(1 for s in meta["counties"].values() if s in DONE.values())
    with con:
        con.execute("DELETE FROM candidates WHERE race_id LIKE '2026-WV-%'")
        con.executemany("INSERT OR REPLACE INTO candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        record_source(con, "wv-sos-2026-general-list", path=gen_path, level="federal", state="WV", kind="official candidate list",
                      agency="West Virginia Secretary of State",
                      title="2026 General Candidate Listing: 11/03/2026 - GENERAL 2026, U.S. Senate and U.S. House of Representatives "
                            "(Regular and Write-In Candidates)",
                      url=SITE, rows=len(gen["regular"]) + len(gen["write_in"]),
                      note=f"Read through the listing's own data service ({API}, office level FEDERAL), every page counted against its "
                           "total; only the name as printed on the ballot, party, office, election and filing date kept; e-mail, phones, "
                           "addresses, website and committee never kept or shown. The listing gives no ballot positions; its order is kept "
                           "(Republican, Democrat, then others). It has no status column, so withdrawn or removed candidates, no longer "
                           f"listed, cannot be counted. Declared write-ins (Write-In Candidates tab): {write_in_n}.")
        record_source(con, "wv-sos-2026-primary-list", path=pri_path, level="federal", state="WV", kind="official candidate list",
                      agency="West Virginia Secretary of State",
                      title="2026 Candidate Listing: 05/12/2026 - PRIMARY 2026, U.S. Senate and U.S. House of Representatives",
                      url=SITE, rows=len(pri["regular"]),
                      note="Used for who was on each party's primary ballot and how the names are printed; the results' candidates must "
                           "be exactly these. The same kept fields only.")
        record_source(con, "wv-sos-2026-primary-results", path=detail, level="federal", state="WV", kind="official results",
                      agency="West Virginia Secretary of State",
                      title="2026 Primary Election (May 12, 2026), Official Results: detail report (XML)",
                      url=meta["detail_url"], published=updated, rows=len(rows) - len(general),
                      note=f"The Secretary's results site ({RESULTS_PAGE}, hosted by Clarity Elections), headed \"{meta['heading']}\", "
                           f"version {meta['version']}, last updated {meta['updated']}, after the county canvasses. All {counties} counties "
                           "completely reported (the site marks no county certified). Every candidate's county votes add up to the "
                           "statewide total. No write-in votes are reported for these contests, so a field's total is its candidates' votes.")
        record_source(con, "wv-sos-2026-primary-summary", path=summary, level="federal", state="WV", kind="official results",
                      agency="West Virginia Secretary of State",
                      title="2026 Primary Election (May 12, 2026), Official Results: summary report (CSV)",
                      url=meta["summary_url"], published=updated, rows=len(votes),
                      note="Control: every federal party primary's totals here match the detail report's.")
    say(f"    West Virginia: 2 House districts and the Senate race, {len(general)} candidates on the November ballot "
        f"({write_in_n} declared write-in); {fields} party primaries with a field, votes from the Secretary of State's official "
        f"results, county sums and the summary report checked")
    return len(general)
