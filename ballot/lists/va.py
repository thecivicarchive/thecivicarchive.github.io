"""
Virginia: the Virginia Department of Elections' own list and results. Virginia has eleven House seats and the Senate
seat of class 2 (Mark R. Warner) on the ballot in 2026; the districts are the 2024 lines (the August primary's
precinct results fall in each district's 2024 localities).

  November ballot   the Department's "2026 November Federal Offices Candidate List", a workbook linked as "Download
                    this file" from its page "November 3, 2026 - Federal Offices" (elections.virginia.gov, Candidates &
                    Referendums). The page is read first and the link followed, so a revised list (the file's name
                    carries its revision date: rev-9-14-2026 on the copy read first) is picked up by itself. Its one
                    sheet has the columns Office Title, District, Candidate Party, Candidate Name and Incumbent, then
                    the campaign's e-mail, website, phone and address. Columns are taken by name: only the first five
                    (and a Status or Ballot Order column if a later revision adds one); the contact columns are never
                    read, and the cache keeps only the columns taken, as JSON, with the workbook's SHA-256. The list
                    names only candidates who qualified (it has no status column), so nothing is left off; it gives no
                    ballot order, so its own order is kept (Democratic, Republican, then the others). Parties are printed
                    in full (Democratic, Republican, Libertarian, Green, Independent) and kept as printed; names are
                    printed first name first in ordinary capitals, with nicknames in quotation marks, and kept as
                    printed. The Incumbent column is used only to check the seat's holder; the match stage sets the rest.
  primary fields    the Department's official results of the August 4, 2026 Democratic and Republican primaries (the
                    primaries were held on August 4 this year, not in June), from its election results site
                    (enr.elections.virginia.gov, linked from Results/Reports, Election Results). Each election's
                    record on the site says whether its results are official; the loader requires it. The statewide
                    summary (the site's own data for the election) gives every candidate's votes and the winner; the
                    site's "Election Results" report (a CSV of every candidate's votes in every precinct: candidate,
                    votes, party, locality, precinct, district, office) is added up and must agree with the summary,
                    candidate by candidate. Neither carries a write-in line (Virginia's primaries have none), so a
                    field's total is the sum of its candidates' votes. A field is a party primary with two candidates
                    or more. A nominee chosen by a party convention or a party-run ("firehouse") primary, or unopposed
                    (Virginia holds no primary for a single candidate), has no official vote count and no field. The
                    Libertarian and Green candidates are nominated outside the state's primaries.
Both hosts answer scripts. The Department's folder of individual results CSVs (apps.elections.virginia.gov/SBE_CSV/)
answers scripts with Akamai's "Access Denied" and is not used.
"""

import collections
import csv
import datetime as dt
import hashlib
import html as H
import io
import json
import os
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urljoin

import openpyxl

from ballot.common import fold, house_id, name_parts, party_code, record_source, senate_id
from ballot.lists.tx import proper
from states import net

PAGE = "https://www.elections.virginia.gov/casting-a-ballot/candidate-list/november-3-2026-gen-elect-federal-offices/"
PAGE_HEADING = "November 3, 2026 - Federal Offices"
LINK = re.compile(r"/candidatelist/2026/2026-November-Federal-Offices-Candidate-List[^\"'<>]*\.xlsx$", re.I)
ENR_API = "https://enr.elections.virginia.gov/results/public/api/elections/virginia/"
ENR_CDN = "https://enr.elections.virginia.gov/cdn/results/"
ENR_SITE = "https://enr.elections.virginia.gov/results/public/virginia/elections/"
PRIMARY = "2026-08-04"
PRIMARIES = {"Democratic": "2026-August-Democratic-Primary", "Republican": "2026-August-Republican-Primary"}
CODE = {"Democratic": "DEM", "Republican": "REP"}
KEEP = ("Office Title", "District", "Candidate Party", "Candidate Name", "Incumbent")
OPTIONAL = ("Status", "Candidate Status", "Ballot Order")
SENATE = "Member, United States Senate"
HOUSE = "Member, House of Representatives"
GONE = ("withdr", "disqual", "remov", "denied", "deceas", "inactive")
SUFFIX = re.compile(r"(JR|SR|II|III|IV|V)\.?", re.I)
CAPS_NOTE = "Virginia's list prints names in capitals; they are shown here in ordinary capitals."
WRITE_IN_NOTE = "Write-in candidate: the name is not printed on the ballot."
NOT_ON_LIST = "Won the primary but is not on the Department's November list."


def race_of(office, district):
    """The race key for an office on the list or in the results; None for any other office."""
    office = re.sub(r"\s+", " ", office or "").strip()
    if office == SENATE:
        return senate_id("VA", 2)
    m = re.fullmatch(re.escape(HOUSE) + r"(?: \((\d+)(?:st|nd|rd|th) District\))?", office)
    if not m:
        return None
    d = m.group(1) or (re.fullmatch(r"(\d+)(?:st|nd|rd|th) District", (district or "").strip()) or [None, None])[1]
    if not d or not 1 <= int(d) <= 11:
        raise SystemExit(f"Virginia: could not read the district of {office!r} ({district!r})")
    return house_id("VA", int(d))


def shown(raw):
    """(name as shown, whether it was printed in capitals). 'Rivera, Edwin' -> 'Edwin Rivera'; 'Edwin Rivera, Jr.' stays."""
    name = re.sub(r"\s+", " ", str(raw or "")).strip()
    last, sep, rest = name.partition(",")
    if sep and rest.strip() and not SUFFIX.fullmatch(rest.strip()) and '"' not in last:
        words = last.split()
        name = " ".join(rest.split() + [w for w in words if not SUFFIX.fullmatch(w)] + [w for w in words if SUFFIX.fullmatch(w)])
    caps = any(c.isalpha() for c in name) and name == name.upper()
    return (proper(name) if caps else name), caps


def get(url, accept="*/*"):
    time.sleep(1.0)
    return net.get(url, accept=accept)


def general_list(folder, say):
    """The November list's federal rows (KEEP columns only), as JSON in the cache, fetched afresh when two days old."""
    path = os.path.join(folder, "va_2026_general_federal_list.json")
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < 2 * 86400:
        return path
    try:
        page = net.get(PAGE).decode("utf-8", "replace")
        h1 = re.search(r"<h1[^>]*>(.*?)</h1>", page, re.S | re.I)
        heading = re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", h1.group(1)))).strip() if h1 else ""
        if heading != PAGE_HEADING:
            raise SystemExit(f"Virginia: the federal candidate list page's heading reads {heading!r}, not {PAGE_HEADING!r}")
        links = [urljoin(PAGE, H.unescape(h)) for h in re.findall(r'<a[^>]+href="([^"]+)"', page, re.I)]
        links = [u for u in links if LINK.search(u)]
        if not links:
            raise SystemExit("Virginia: the federal candidate list page no longer links the 2026 November Federal Offices Candidate List workbook")
        url = links[0]
        data = get(url, accept="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,*/*")
    except (HTTPError, URLError, OSError) as e:
        if os.path.exists(path):
            say(f"      could not refresh the November list ({e}); using the copy read earlier")
            return path
        raise
    if data[:2] != b"PK":
        raise SystemExit(f"Virginia: {url} did not give a workbook")
    wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    if len(wb.worksheets) != 1:
        raise SystemExit(f"Virginia: the November list has {len(wb.worksheets)} sheets; read it again")
    rows = wb.worksheets[0].iter_rows(values_only=True)
    heads = None
    for i, r in enumerate(rows):
        cells = [str(c).strip() if c is not None else "" for c in r]
        if all(k in cells for k in KEEP):
            heads = cells
            break
        if i > 10:
            break
    if not heads:
        raise SystemExit(f"Virginia: the November list's columns changed (no row with {', '.join(KEEP)})")
    idx = {k: heads.index(k) for k in KEEP + OPTIONAL if k in heads}
    kept = []
    for r in rows:
        rec = {k: (re.sub(r"\s+", " ", str(r[i])).strip() if i < len(r) and r[i] is not None else "") for k, i in idx.items()}
        if not rec["Office Title"] and not rec["Candidate Name"]:
            continue
        if race_of(rec["Office Title"], rec["District"]) is None:
            raise SystemExit(f"Virginia: the federal list names an office that is not the Senate or the House ({rec['Office Title']!r})")
        kept.append(rec)
    m = re.search(r"rev-(\d{1,2})-(\d{1,2})-(\d{4})", url)
    meta = {"url": url, "page": PAGE, "heading": heading, "sha256": hashlib.sha256(data).hexdigest(),
            "published": f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}" if m else "",
            "revision": f"rev. {m.group(1)}-{m.group(2)}-{m.group(3)}" if m else "", "columns": list(idx),
            "read": dt.date.today().isoformat(), "rows": kept}
    json.dump(meta, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return path


def primary_results(folder, party, say):
    """One party's official August 4 results for the Senate and the House, as JSON in the cache: the statewide summary
    and the precinct report's sums, candidate by candidate. Read afresh when thirty days old."""
    slug = PRIMARIES[party]
    path = os.path.join(folder, f"va_2026_primary_{CODE[party].lower()}_federal.json")
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < 30 * 86400:
        return path
    try:
        raw = get(ENR_API + slug + "/data", accept="application/json")
        data = json.loads(raw.decode("utf-8-sig"))
        el = data["election"]
        name = el["name"][0]["text"]
        if el.get("electionDate") != PRIMARY or party not in name or "Primary" not in name:
            raise SystemExit(f"Virginia: the results site's {slug} is {name!r} of {el.get('electionDate')}, not the {party} primary of {PRIMARY}")
        if el.get("isOfficialResults") is not True:
            raise SystemExit(f"Virginia: the results site does not mark the {party} primary's results official")
        reports = [r for c in el.get("publicReportCategories") or [] for r in c.get("reports") or [] if r.get("reportName") == "Election Results"]
        if len(reports) != 1:
            raise SystemExit(f"Virginia: the results site lists {len(reports)} Election Results reports for the {party} primary")
        csv_url = ENR_CDN + el["jurisdictionId"] + "/" + quote(reports[0]["blobName"])
        report = get(csv_url, accept="text/csv,*/*")
    except (HTTPError, URLError, OSError) as e:
        if os.path.exists(path):
            say(f"      could not refresh the {party} primary results ({e}); using the copy read earlier")
            return path
        raise
    if report[:1] in (b"<",) or b"CandidateName" not in report[:400]:
        raise SystemExit(f"Virginia: the {party} primary's Election Results report is not the CSV it was")
    contests = []
    for item in data["ballotItems"]:
        if item.get("parentId"):
            continue
        office = item["name"][0]["text"]
        race = race_of(office, "")
        if not race:
            continue
        options = []
        for o in item["summaryResults"]["ballotOptions"]:
            p = o.get("party") or {}
            label = next((t["text"] for t in p.get("name") or [] if t.get("languageId") == "en"), p.get("standardName") or "")
            options.append({"name": o["name"][0]["text"], "party": label, "votes": int(o["voteCount"] or 0),
                            "winner": bool(o.get("isWinner")), "write_in": bool(o.get("isWriteIn"))})
        contests.append({"office": office, "race": race, "vote_total": int(item.get("voteTotal") or 0), "options": options})
    sums, places = collections.defaultdict(collections.Counter), collections.defaultdict(set)
    for r in csv.DictReader(io.StringIO(report.decode("utf-8-sig"))):      # only these columns are read
        office = r["OfficeTitle"]
        if not race_of(office, ""):
            continue
        sums[office][r["CandidateName"]] += int(float(r["TOTAL_VOTES"] or 0))
        places[office].add((r["LocalityCode"], r["PrecinctId"]))
        if r["ElectionDate"] != PRIMARY:
            raise SystemExit(f"Virginia: the {party} primary's report carries a row dated {r['ElectionDate']}")
    for c in contests:
        c["precinct_sums"] = dict(sums.get(c["office"], {}))
        c["precincts"] = len(places.get(c["office"], ()))
    missing = set(sums) - {c["office"] for c in contests}
    if missing:
        raise SystemExit(f"Virginia: the {party} primary's report has federal contests the summary lacks: {sorted(missing)}")
    keep = {"slug": slug, "name": name, "date": el["electionDate"], "official": el["isOfficialResults"], "as_of": el.get("asOf"),
            "last_updated": el.get("lastUpdated"), "site": ENR_SITE + slug, "data_url": ENR_API + slug + "/data",
            "data_sha256": hashlib.sha256(raw).hexdigest(), "report_url": csv_url, "report_sha256": hashlib.sha256(report).hexdigest(),
            "read": dt.date.today().isoformat(), "contests": contests}
    json.dump(keep, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return path


def load(con, cache, say=print):
    net.patient_lookups()
    folder = os.path.join(cache, "va")
    os.makedirs(folder, exist_ok=True)
    gpath = general_list(folder, say)
    glist = json.load(open(gpath, encoding="utf-8"))

    # the November ballot
    rows, general, gone, order, marked = [], [], [], {}, {}
    for r in glist["rows"]:
        status = (r.get("Status") or r.get("Candidate Status") or "").lower()
        if any(g in status for g in GONE):
            gone.append(r)
            continue
        race = race_of(r["Office Title"], r["District"])
        name, caps = shown(r["Candidate Name"])
        party = r["Candidate Party"]
        write_in = int("write" in (party + " " + status).lower())
        order[race] = order.get(race, 0) + 1
        given = r.get("Ballot Order", "")
        note = " ".join(n for n in (CAPS_NOTE if caps else "", WRITE_IN_NOTE if write_in else "") if n) or None
        general.append((race, "general", "2026-11-03", name, party, party_code(party), int(given) if str(given).isdigit() else order[race],
                        0, write_in, None, None, None, None, None, "va-elections-2026-general-federal-list", note))
        if r["Incumbent"].strip().lower() == "yes":
            marked.setdefault(race, []).append(name)
    races = dict(con.execute("SELECT race_id, holder_name FROM races WHERE state = 'VA'").fetchall())
    empty = sorted(set(races) - {g[0] for g in general})
    stray = sorted({g[0] for g in general} - set(races))
    if stray:
        raise SystemExit(f"Virginia: the November list names races that are not in the races table: {stray}")
    holders = []
    for race, holder in races.items():
        said = marked.get(race, [])
        if holder and not any(name_parts(n)[1] == name_parts(holder)[1] for n in said):
            holders.append(f"{race}: list marks {said or 'no one'}, the seat's holder is {holder}")
    nominee = {(g[0], g[4]): g[3] for g in general}

    # the primary fields
    sources, nfields, unreconciled, upsets = [], 0, [], []
    for party, slug in PRIMARIES.items():
        rpath = primary_results(folder, party, say)
        res = json.load(open(rpath, encoding="utf-8"))
        n_rows = 0
        for c in res["contests"]:
            race = c["race"]
            names = [o for o in c["options"] if not o["write_in"]]
            write_ins = sum(o["votes"] for o in c["options"] if o["write_in"])
            total = sum(o["votes"] for o in names) + write_ins
            if total != c["vote_total"]:
                unreconciled.append(f"{race} {party}: candidates {total:,} against the summary's total {c['vote_total']:,}")
            for o in c["options"]:
                if c["precinct_sums"].get(o["name"], 0) != o["votes"]:
                    unreconciled.append(f"{race} {party} {o['name']}: precincts {c['precinct_sums'].get(o['name'], 0):,}, summary {o['votes']:,}")
            if set(c["precinct_sums"]) - {o["name"] for o in c["options"]}:
                unreconciled.append(f"{race} {party}: the precinct report names {sorted(set(c['precinct_sums']) - {o['name'] for o in c['options']})}")
            wrong = [o["name"] for o in c["options"] if o["party"] and o["party"] != party]
            if wrong:
                raise SystemExit(f"Virginia: the {party} primary for {race} lists candidates of another party: {wrong}")
            winners = [o for o in names if o["winner"]]
            if len(names) < 2:
                continue
            if len(winners) != 1:
                raise SystemExit(f"Virginia: the {party} primary for {race} has {len(winners)} winners marked")
            top = max(names, key=lambda o: o["votes"])
            if top is not winners[0]:
                raise SystemExit(f"Virginia: the {party} primary for {race} marks {winners[0]['name']} the winner, not the top vote-getter")
            on_list = nominee.get((race, party))
            if on_list is not None and fold(on_list) != fold(shown(winners[0]["name"])[0]):
                upsets.append(f"{race} {party}: primary won by {winners[0]['name']}, the list's nominee is {on_list}")
            nfields += 1
            for o in names:
                name, caps = shown(o["name"])
                notes = [CAPS_NOTE if caps else "", NOT_ON_LIST if o["winner"] and on_list is None else ""]
                rows.append((race, f"primary-{CODE[party]}", PRIMARY, name, party, party_code(party), None, 0, 0, o["votes"],
                             round(100 * o["votes"] / total, 1) if total else None, "advanced" if o["winner"] else "lost",
                             None, None, f"va-elections-2026-primary-{CODE[party].lower()}", " ".join(n for n in notes if n) or None))
                n_rows += 1
        sources.append((party, rpath, res, n_rows))
    rows = general + rows

    with con:
        con.execute("DELETE FROM candidates WHERE race_id LIKE '2026-VA-%'")
        con.executemany("INSERT OR REPLACE INTO candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        record_source(con, "va-elections-2026-general-federal-list", path=gpath, level="federal", state="VA", kind="official candidate list",
                      agency="Virginia Department of Elections",
                      title=f"2026 November Federal Offices Candidate List ({glist['heading']}" + (f", {glist['revision']})" if glist["revision"] else ")"),
                      url=glist["url"], published=glist["published"], rows=len(glist["rows"]),
                      note=f"Workbook SHA-256 {glist['sha256'][:16]}..., linked from {glist['page']}. Office, district, party, name and the "
                           f"incumbent mark kept; the campaign e-mail, website, phone and address columns are never read. The list gives no "
                           f"ballot order; its own order is kept. It carries no status column (only qualified candidates are listed); "
                           f"withdrawn or removed, left off: {len(gone)}.")
        for party, rpath, res, n_rows in sources:
            checks = [u for u in unreconciled if f" {party}" in u]
            record_source(con, f"va-elections-2026-primary-{CODE[party].lower()}", path=rpath, level="federal", state="VA", kind="official results",
                          agency="Virginia Department of Elections",
                          title=f"Election results: {res['name']} (August 4, 2026), U.S. Senate and House of Representatives, official results",
                          url=res["site"], published=(res.get("as_of") or "")[:10], rows=n_rows,
                          note=f"The results site marks these results official (as of {(res.get('as_of') or '')[:10]}). Votes from the site's statewide "
                               f"summary ({res['data_url']}, SHA-256 {res['data_sha256'][:16]}...), checked against its precinct-by-precinct "
                               f"Election Results report (CSV, SHA-256 {res['report_sha256'][:16]}...): "
                               + ("every candidate's precincts add up to the summary. " if not checks else "differences: " + "; ".join(checks) + ". ")
                               + "No write-in line (Virginia's primaries have none); a field's total is the sum of its candidates' votes. "
                                 "Nominees chosen by convention, a party-run primary or unopposed have no field.")
    for label, items in (("the list's incumbent marks differ from the seat holders", holders),
                         ("primary counts that do not reconcile", unreconciled),
                         ("the November nominee is not the primary winner", upsets),
                         ("races with no November candidate", empty)):
        if items:
            say(f"    Virginia: {label}: " + "; ".join(items))
    n = len(general)
    say(f"    Virginia: the Senate race and {len({g[0] for g in general if '-H' in g[0]})} House districts, {n} candidates on the November ballot "
        f"({len(gone)} withdrawn left off); {nfields} party primaries with a field (August 4), votes from the official results")
    return n
