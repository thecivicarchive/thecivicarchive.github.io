"""
South Carolina: the State Election Commission's own records. South Carolina has seven House seats and the class 2 Senate
seat on the November 3, 2026 ballot. A party's nominee needs a majority in its primary (June 9); where no one had one, the
two with the most votes met in the runoff two weeks later (June 23). The Republican nominee for the Senate, Lindsey
Graham, died after winning the June primary; under S.C. Code section 7-11-55 the Commission held a special Republican
primary on August 11 and its runoff on August 25, and that nominee is on the November ballot (the Commission's notice,
scvotes.gov/u-s-senate-special-republican-party-filing-primary/, July 13, 2026).

  November ballot   the Commission's Candidate Tracking System (vrems.scvotes.sc.gov/Candidate/SelectElection, linked
                    as "Candidate Tracking System" from scvotes.gov/candidates/). The page's own calls are made in order:
                    the list of 2026 statewide elections (/Candidate/GetElections?electionType=General&year=2026), the
                    election chosen ("11/3/2026 Statewide General Election"), then the search (a POST to
                    /Candidate/CandidateSearch/) for the office "U.S. Senate" and for "U.S. House of Representatives",
                    every status and every party. The answer is a table with the columns Office, Associated Counties,
                    Name on Ballot, Running Mate, Party, Location of Filing and Candidate Status; columns are taken by
                    name, and only Office, Name on Ballot, Party and Candidate Status (with the row's own candidate
                    number) are kept, in ballot_cache/sc/sc_2026_candidate_lists.json with each answer's SHA-256. The
                    table carries no address, telephone or e-mail; each row links a detail page that does, and those
                    pages are never asked for. The export link on the page is not used either.
                    The general election's list holds every candidate of the year for the office. Candidates whose
                    status is Active (after the election, Elected or Defeated in Election) are on the November ballot;
                    every other status (Defeated In Primary, Defeated At Convention, Withdrew, Not Certified for
                    General, Deceased After Primary and the rest) is left off and counted by status. The list gives no
                    ballot positions; it is sorted by surname, and that order is kept. Parties are printed in full
                    ("Forward Party", "Workers"); "Petition" (put on the ballot by voters' petition) is coloured as an
                    independent. The list carries no write-in candidates.
  primary fields    the Commission's official results site (www.enr-scvotes.org, hosted by Clarity Elections, linked
                    from scvotes.gov/elections-statistics/election-results/ under 2026): "Statewide Primaries" (June 9),
                    "Statewide Primary Runoffs" (June 23), "U.S. Senate Special Republican Primary" (August 11) and
                    "U.S. Senate Special Republican Runoff" (August 25). For each, the site's current version, its
                    settings (the heading its page template shows must read "Official Results"; the older template's
                    leftover heading, "UNOFFICIAL RESULTS", is not what the site shows) and its county statuses (all
                    46 counties completely reported and marked certified, "County results have been validated and are
                    official") are read, then its detail report (reports/detailxml.zip): one Contest per office and
                    party ("U.S.  Senate  - REP", "U.S.  House of Representatives, District  1 - DEM"), each candidate's
                    statewide total and the same by vote type and county; every candidate's vote types and counties
                    must add to the total, every precinct must have reported, and the summary report
                    (reports/summary.zip) must give the same totals. The "Primaries Recount" site (June 12) is read too,
                    and must hold no federal contest. The results carry no write-in line, so a field's total is the sum
                    of its candidates' votes. Every result's candidates must be on the Commission's list of that
                    election (the "6/9/2026 Statewide Primary" and "8/11/2026 US Senate Special Republican Primary"
                    lists, read the same way), names matched letters only, and every candidate the list marks Defeated
                    In Primary must be in the results.
                    A field is a party's primary with two candidates or more (South Carolina prints no uncontested
                    primary). A candidate with a majority advanced; otherwise the two in the runoff advanced (noted),
                    and the runoff, stored as its own election (runoff-REP, runoff-DEM), was won by the one with more
                    votes; the runoff's pair must be the primary's top two. The Senate's special primary and its runoff
                    are stored as special-primary-REP and special-runoff-REP.

The Commission's own site and the results site answer scripts; nothing was fetched through a browser.
"""

import csv
import datetime as dt
import gzip
import hashlib
import html
import http.cookiejar
import io
import json
import os
import re
import time
import uuid
import zipfile
import xml.etree.ElementTree as ET
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener

from ballot.common import fold, house_id, party_code, record_source, senate_id
from ballot.lists.tx import proper
from states import net

CTS = "https://vrems.scvotes.sc.gov"
CTS_PAGE = CTS + "/Candidate/SelectElection"
OFFICES = ("U.S. Senate", "U.S. House of Representatives")
LISTS = {"general": ("11/3/2026 Statewide General Election", "2026-11-03", OFFICES),
         "primary": ("6/9/2026 Statewide Primary", "2026-06-09", OFFICES),
         "special": ("8/11/2026 US Senate Special Republican Primary", "2026-08-11", ("U.S. Senate",))}
KEEP = ("Office", "Name on Ballot", "Party", "Candidate Status")
SEC = "https://scvotes.gov/"
RESULTS_PAGE = SEC + "elections-statistics/election-results/"
NOTICE = SEC + "u-s-senate-special-republican-party-filing-primary/"
ENR = "https://www.enr-scvotes.org/SC/"
# kind: (label on the Commission's results page, the site's own election name, its date, election code prefix, date stored)
RESULTS = {"primary": ("Statewide Primaries", "2026 Statewide Primary", "6/9/2026", "primary", "2026-06-09"),
           "runoff": ("Statewide Primary Runoffs", "2026 Statewide Primaries *RUNOFFS*", "6/23/2026", "runoff", "2026-06-23"),
           "special": ("U.S. Senate Special Republican Primary", "US Senate Special Republican Primary", "8/11/2026",
                       "special-primary", "2026-08-11"),
           "special-runoff": ("U.S. Senate Special Republican Runoff", "U.S. Senate Special Republican Primary - Runoff", "8/25/2026",
                              "special-runoff", "2026-08-25"),
           "recount": ("Primaries Recount", "2026 Statewide Primaries *RECOUNT*", "6/12/2026", None, None)}
ORDER = ("primary", "runoff", "special", "special-runoff")          # the order the rounds were held
RUNOFF_OF = {"primary": "runoff", "special": "special-runoff"}
PARTY = {"REP": "Republican", "DEM": "Democratic"}
LIST_CODE = {"Republican": "REP", "Democratic": "DEM"}
ON = {"Active", "Elected", "Defeated in Election"}
BEFORE = {"Withdrew Before Primary", "Deceased Before Primary", "Decertified before Primary", "Disqualified before Primary",
          "Not Certified for Primary", "Petition Failed", "Defeated At Convention"}
KNOWN = ON | BEFORE | {"Defeated In Primary", "Withdrew", "Withdrew After Primary", "Not Certified for General",
                       "Deceased After Primary", "Disqualified after Primary", "Decertified after Primary", "Deceased Before Election"}
COUNTIES = 46
CAPS = "South Carolina's list prints names in capitals; they are shown here in ordinary capitals."


# ---------------------------------------------------------------- the Candidate Tracking System

class Session:
    """The candidate pages keep the chosen election in a session cookie, as a browser would."""

    def __init__(self):
        self.op = build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def ask(self, url, data=None, ctype=None, accept="text/html"):
        head = {"User-Agent": net.UA, "Accept": accept}
        if ctype:
            head["Content-Type"] = ctype
        for attempt in range(3):                       # a refusal is asked at most twice more, then reported
            try:
                with self.op.open(Request(url, data=data, headers=head), timeout=120) as r:
                    body = r.read()
                time.sleep(1.0)
                return body
            except HTTPError as e:
                if attempt == 2 or e.code not in (403, 429, 500, 502, 503, 504):
                    raise SystemExit(f"South Carolina: {url} answered HTTP {e.code}; not asked again")
                time.sleep(15 * (attempt + 1))
            except URLError:
                if attempt == 2:
                    raise
                time.sleep(15 * (attempt + 1))


def grid(body):
    """[(candidate number, {kept column: cell})] from the search answer, columns taken by name from its header."""
    t = body.decode("utf-8", "replace")
    head = [re.sub(r"<[^>]+>|\s+", " ", h).strip() for h in re.findall(r"<th[^>]*>(.*?)</th>", t, re.S)]
    missing = [k for k in KEEP if k not in head]
    if missing:
        raise SystemExit(f"South Carolina: the candidate search's columns changed (no {', '.join(missing)})")
    idx = {k: head.index(k) for k in KEEP}
    rows, n = [], 0
    for m in re.finditer(r"<tr([^>]*)>(.*?)</tr>", t, re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", m.group(2), re.S)
        if not cells:
            continue
        if len(cells) != len(head):
            raise SystemExit("South Carolina: a row of the candidate search does not match its header")
        key = re.search(r'data-key="(\d+)"', m.group(1))
        at = re.search(r'data-index="(\d+)"', m.group(1))
        if not key or not at or int(at.group(1)) != n:
            raise SystemExit("South Carolina: the candidate search's rows are not numbered as expected")
        n += 1
        rows.append((key.group(1), {k: html.unescape(re.sub(r"<[^>]+>|\s+", " ", cells[i])).strip() for k, i in idx.items()}))
    return rows


def candidate_lists(folder, say):
    """{kind: {"id", "display", "url", "offices": {office: {"sha256", "rows": [...]}}}} for the three elections; the kept
    columns only. Asked afresh after two days."""
    path = os.path.join(folder, "sc_2026_candidate_lists.json")
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < 2 * 86400:
        return path, json.load(open(path, encoding="utf-8"))
    s = Session()
    elections = json.loads(s.ask(f"{CTS}/Candidate/GetElections?electionType=General&year=2026", accept="application/json"))
    out = {"read": dt.date.today().isoformat(), "page": CTS_PAGE, "elections": {}}
    for kind, (display, date, offices) in LISTS.items():
        found = [e for e in elections if e.get("displayName") == display and str(e.get("electionDate", "")).startswith(date)]
        if len(found) != 1:
            raise SystemExit(f"South Carolina: the Candidate Tracking System lists {len(found)} elections named {display!r}")
        eid = str(found[0]["electionId"])
        first = s.ask(CTS_PAGE).decode("utf-8", "replace")
        tok = re.search(r'name="__RequestVerificationToken" type="hidden" value="([^"]+)"', first)
        if not tok:
            raise SystemExit("South Carolina: the Candidate Tracking System's election page changed (no form token)")
        page = s.ask(CTS_PAGE, urlencode({"ElectionKindSid": "General", "ElectionYear": "2026", "ElectionID": eid,
                                          "__RequestVerificationToken": tok.group(1)}).encode(),
                     ctype="application/x-www-form-urlencoded").decode("utf-8", "replace")
        form = re.search(r'<form id="searchForm">(.*?)</form>', page, re.S)
        if not form or f'name="ElectionId" value="{eid}"' not in form.group(1):
            raise SystemExit(f"South Carolina: the candidate search for {display} did not open")
        export = re.search(r'name="ExportFileName" value="([^"]*)"', form.group(1))
        opts = dict((html.unescape(b).strip(), a) for a, b in
                    re.findall(r'<option[^>]*value="([^"]*)"[^>]*>([^<]*)',
                               re.search(r'<select[^>]*id="SelectedOffice"[^>]*>(.*?)</select>', form.group(1), re.S).group(1)))
        rec = {"id": eid, "display": display, "url": f"{CTS}/Candidate/CandidateSearch?electionId={eid}", "offices": {}}
        for office in offices:
            if office not in opts:
                raise SystemExit(f"South Carolina: the candidate search for {display} offers no office {office!r}")
            fields = [("ElectionId", eid), ("ExportFileName", export.group(1) if export else ""), ("SelectedOffice", opts[office]),
                      ("CandidateFirstName", ""), ("CandidateLastName", ""), ("SelectedCandidateStatus", "All"),
                      ("SelectedPoliticalParty", "All"), ("SelectedFilingLocation", "All")]
            b = "----sc" + uuid.uuid4().hex
            data = "".join(f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n' for k, v in fields) + f"--{b}--\r\n"
            body = s.ask(f"{CTS}/Candidate/CandidateSearch/", data.encode(), ctype=f"multipart/form-data; boundary={b}")
            rows = grid(body)
            bad = [r["Office"] for _k, r in rows if not r["Office"].startswith(office)]
            if bad:
                raise SystemExit(f"South Carolina: the search for {office} answered rows for {bad[0]!r}")
            rec["offices"][office] = {"sha256": hashlib.sha256(body).hexdigest(),
                                      "rows": [dict(r, id=k) for k, r in rows]}
        out["elections"][kind] = rec
        say(f"      {display}: {sum(len(o['rows']) for o in rec['offices'].values())} candidates for Congress on the list")
    json.dump(out, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return path, out


def race_of_list(office):
    o = re.sub(r"\s+", " ", office).strip()
    if o == "U.S. Senate":
        return senate_id("SC", 2)
    m = re.fullmatch(r"U\.S\. House of Representatives, District (\d+)", o)
    if m:
        return house_id("SC", int(m.group(1)))
    raise SystemExit(f"South Carolina: an office on the candidate list the loader does not read ({office!r})")


# ---------------------------------------------------------------- the results site

def long_date(iso):
    d = dt.date.fromisoformat(iso)
    return f"{d:%B} {d.day}, {d.year}"


def unzip_json(raw):
    return json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)


def results_links():
    """{label: election id} for the 2026 part of the Commission's results page."""
    t = net.get(RESULTS_PAGE, accept="text/html").decode("utf-8", "replace")
    a, b = t.find('id="2026"'), t.find('id="2025"')
    if a < 0 or b < a:
        raise SystemExit("South Carolina: the Commission's results page has no 2026 section")
    links = {}
    for m in re.finditer(r'<a[^>]+href="https://www\.enr-scvotes\.org/SC/(\d+)/[^"]*"[^>]*>(.*?)</a>', t[a:b], re.S):
        links[re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", m.group(2)))).strip()] = m.group(1)
    return links


def fetch_results(folder, say):
    """Each results site's detail and summary reports, with its heading and county statuses; kept for 30 days."""
    meta_path = os.path.join(folder, "sc_2026_results_meta.json")
    if os.path.exists(meta_path) and time.time() - os.path.getmtime(meta_path) < 30 * 86400:
        meta = json.load(open(meta_path, encoding="utf-8"))
        if all(os.path.exists(os.path.join(folder, m[f])) for m in meta["sites"].values() for f in ("detail", "summary")):
            return meta
    links = results_links()
    want = {v[0]: k for k, v in RESULTS.items()}
    local = r"(?i)House District|Senate District|State (?:House|Senate)|City|Town|County|Municipal"
    stray = [lab for lab in links if lab not in want and (re.search(r"(?i)\bU\.?\s?S\.|Congress|Statewide", lab)
                                                          or (re.search(r"(?i)recount|runoff", lab) and not re.search(local, lab)))]
    if stray:
        raise SystemExit(f"South Carolina: the results page lists 2026 elections the loader does not read: {stray}")
    meta = {"page": RESULTS_PAGE, "read": dt.date.today().isoformat(), "sites": {}}
    for kind, (label, name, date, _code, _d) in RESULTS.items():
        if label not in links:
            raise SystemExit(f"South Carolina: the results page no longer links {label!r}")
        base = f"{ENR}{links[label]}/"
        ver = net.get(base + "current_ver.txt").decode("ascii", "replace").strip()
        if not ver.isdigit():
            raise SystemExit(f"South Carolina: the results site's current version for {label} is not a number")
        settings = unzip_json(net.get(f"{base}{ver}/json/en/electionsettings.json"))
        time.sleep(1)
        status = unzip_json(net.get(f"{base}{ver}/json/status.json"))
        ed = settings["settings"]["electiondetails"]
        if ed.get("internalname") != name or ed.get("electiondate") != date:
            raise SystemExit(f"South Carolina: {base} is {ed.get('internalname')!r} of {ed.get('electiondate')}, not {name!r} of {date}")
        heading = re.sub(r"<[^>]+>", "", settings["pagesettings"]["web"].get("header") or "").strip()
        if heading != "Official Results":
            raise SystemExit(f"South Carolina: the results site for {label} is headed {heading or 'nothing'!r}; unofficial figures are never stored")
        counties = {p: (s, c) for p, s, c in zip(status["P"], status["S"], status["C"])}
        behind = {p: sc for p, sc in counties.items() if sc != (4, 1)}
        if behind:
            raise SystemExit(f"South Carolina: {label}: counties not completely reported and certified: {sorted(behind)}")
        rec = {"id": links[label], "label": label, "name": name, "date": date, "version": ver,
               "updated": settings.get("websiteupdatedat"), "heading": heading, "counties": len(counties),
               "page": f"{base}web.345435/#/summary", "detail_url": f"{base}{ver}/reports/detailxml.zip",
               "summary_url": f"{base}{ver}/reports/summary.zip",
               "detail": f"sc_2026_{kind}_detailxml.zip", "summary": f"sc_2026_{kind}_summary.zip"}
        for url, fname in ((rec["detail_url"], rec["detail"]), (rec["summary_url"], rec["summary"])):
            p = os.path.join(folder, fname)
            net.download(url, p, max_age_days=0, say=say)
            if open(p, "rb").read(2) != b"PK":
                os.remove(p)
                raise SystemExit(f"South Carolina: {url} is not a zip file")
            time.sleep(1)
        meta["sites"][kind] = rec
        say(f"      {label}: version {ver}, updated {rec['updated']}, headed {heading}, {len(counties)} counties certified")
    json.dump(meta, open(meta_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return meta


def contest_of(text):
    """(race, party code) for a federal contest of the results; None for any other contest."""
    t = re.sub(r"\s+", " ", text or "").strip()
    m = re.fullmatch(r"U\.S\. Senate - ([A-Z]+)", t)
    if m:
        return senate_id("SC", 2), m.group(1)
    m = re.fullmatch(r"U\.S\. House of Representatives, District (\d+) - ([A-Z]+)", t)
    if m:
        return house_id("SC", int(m.group(1))), m.group(2)
    if t.startswith("U.S.") or "Congress" in t:
        raise SystemExit(f"South Carolina: a federal contest in the results that is not read ({t!r})")
    return None


def contests(folder, rec):
    """{(race, party code): [(name as reported, votes)]} for every federal contest of one results site; every check made."""
    root = ET.fromstring(zipfile.ZipFile(os.path.join(folder, rec["detail"])).read("detail.xml"))
    if root.findtext("ElectionDate") != rec["date"]:
        raise SystemExit(f"South Carolina: the detail report of {rec['label']} is dated {root.findtext('ElectionDate')}")
    out = {}
    for c in root.findall("Contest"):
        key = contest_of(c.get("text"))
        if not key:
            continue
        if key[1] not in PARTY:
            raise SystemExit(f"South Carolina: a party in the results that is not read ({c.get('text')})")
        if c.get("precinctsReported") != c.get("precinctsParticipating") or c.get("countiesReported") != c.get("countiesParticipating"):
            raise SystemExit(f"South Carolina: {c.get('text')} is not completely reported in {rec['label']}")
        field = []
        for ch in c.findall("Choice"):
            total = int(ch.get("totalVotes"))
            by_type = sum(int(vt.get("votes")) for vt in ch.findall("VoteType"))
            by_county = sum(int(cc.get("votes")) for vt in ch.findall("VoteType") for cc in vt.findall("County"))
            if by_type != total or by_county != total:
                raise SystemExit(f"South Carolina: {ch.get('text')}'s votes in {c.get('text')} ({rec['label']}) do not add up")
            if re.search(r"(?i)write[- ]?in", ch.get("text", "")):
                raise SystemExit(f"South Carolina: {c.get('text')} reports write-in votes; read how the total is made")
            if ch.get("party") != key[1]:
                raise SystemExit(f"South Carolina: {ch.get('text')} is reported under {ch.get('party')} in {c.get('text')}")
            field.append((re.sub(r"\s+", " ", ch.get("text")).strip(), total))
        if key in out:
            raise SystemExit(f"South Carolina: {c.get('text')} appears twice in {rec['label']}")
        out[key] = field
    # control: the summary report gives the same totals
    z = zipfile.ZipFile(os.path.join(folder, rec["summary"]))
    rows = list(csv.reader(io.StringIO(z.read("summary.csv").decode("utf-8-sig", "replace"))))
    ci, ni, vi = rows[0].index("contest name"), rows[0].index("choice name"), rows[0].index("total votes")
    seen = {}
    for r in rows[1:]:
        key = contest_of(re.sub(r" \(Vote For \d+\)$", "", r[ci])) if r else None
        if key:
            seen.setdefault(key, {})[fold(r[ni])] = int(r[vi])
    if seen != {k: {fold(n): v for n, v in f} for k, f in out.items()}:
        raise SystemExit(f"South Carolina: the summary and detail reports of {rec['label']} differ for Congress")
    return out


# ---------------------------------------------------------------- load

def load(con, cache, say=print):
    net.patient_lookups()
    folder = os.path.join(cache, "sc")
    os.makedirs(folder, exist_ok=True)
    lpath, lists = candidate_lists(folder, say)
    meta = fetch_results(folder, say)
    sites = meta["sites"]
    if contests(folder, sites["recount"]):
        raise SystemExit("South Carolina: the June 12 recount holds a federal contest; read which figures stand")
    rounds = {kind: contests(folder, sites[kind]) for kind in ORDER}

    def shown(raw):
        name = re.sub(r"\s+", " ", raw or "").strip()
        caps = any(c.isalpha() for c in name) and name == name.upper()
        return (proper(name) if caps else name), caps

    def listed(kind):
        """[(race, row)] of one election's list, both offices."""
        e = lists["elections"][kind]
        return [(race_of_list(r["Office"]), r) for o in e["offices"] for r in e["offices"][o]["rows"]]

    unknown = sorted({r["Candidate Status"] for k in LISTS for _race, r in listed(k)} - KNOWN)
    if unknown:
        raise SystemExit(f"South Carolina: statuses on the candidate list the loader does not read: {unknown}")

    # the November ballot
    general, off, order, november, status_of = [], {}, {}, {}, {}
    for race, r in listed("general"):
        status_of[(race, fold(r["Name on Ballot"]))] = r["Candidate Status"]
        if r["Candidate Status"] not in ON:
            off[r["Candidate Status"]] = off.get(r["Candidate Status"], 0) + 1
            continue
        name, caps = shown(r["Name on Ballot"])
        party = r["Party"].strip()
        if not party:
            raise SystemExit(f"South Carolina: {name} ({race}) has no party on the list")
        code = "I" if party == "Petition" else party_code(party)
        order[race] = order.get(race, 0) + 1
        november.setdefault(race, []).append((name, party))
        general.append((race, "general", "2026-11-03", name, party, code, order[race], 0, 0, None, None, None, None, None,
                        "sc-sec-2026-general-list", CAPS if caps else None))
    for race, names in november.items():
        for p in LIST_CODE:
            two = [n for n, q in names if q == p]
            if len(two) > 1:
                raise SystemExit(f"South Carolina: the November list has {len(two)} {p} candidates for {race} ({', '.join(two)})")

    # who was on each party's ballot in each round, from the Commission's lists
    differ = []
    ballot = {"primary": {}, "special": {}}
    printed = {}
    for kind in ballot:
        for race, r in listed(kind):
            printed[fold(r["Name on Ballot"])] = r["Name on Ballot"]
            if r["Candidate Status"] in BEFORE:
                continue
            ballot[kind].setdefault((race, LIST_CODE.get(r["Party"], r["Party"])), set()).add(fold(r["Name on Ballot"]))
    for first, second, later in (("primary", "runoff", ("special", "special-runoff")), ("special", "special-runoff", ())):
        done = {k for k in list(rounds[first]) + list(rounds[second])}
        for key, names in ballot[first].items():
            counted = {fold(n) for n, _v in rounds[first].get(key, [])}
            excused = {fold(n) for k2 in later for n, _v in rounds[k2].get(key, [])}
            if key in rounds[first]:
                if counted - names:
                    differ.append(f"{key[0]} {key[1]} ({RESULTS[first][0]}): in the results but not on the list: {sorted(counted - names)}")
                if names - counted - excused:
                    differ.append(f"{key[0]} {key[1]} ({RESULTS[first][0]}): on the list but not in the results: {sorted(names - counted - excused)}")
            elif len(names - excused) > 1:
                differ.append(f"{key[0]} {key[1]}: the list names {len(names)} candidates but the results hold no primary")
        for key in done:
            if key not in ballot[first]:
                differ.append(f"{key[0]} {key[1]} ({RESULTS[first][0]}): a contest in the results with no candidates on the list")
        for race, r in listed(first):
            if r["Candidate Status"] == "Defeated In Primary":
                key = (race, LIST_CODE.get(r["Party"], r["Party"]))
                if fold(r["Name on Ballot"]) not in {fold(n) for k2 in (first, second) for n, _v in rounds[k2].get(key, [])}:
                    differ.append(f"{r['Name on Ballot']} ({race}) is marked Defeated In Primary but is in no {RESULTS[first][0]} result")

    # the primary fields, round by round
    rows, nominee, fields, runoffs, gone = [], {}, 0, 0, []
    went = {}
    for first, second in RUNOFF_OF.items():
        pre1, date1 = RESULTS[first][3], RESULTS[first][4]
        pre2, date2 = RESULTS[second][3], RESULTS[second][4]
        for key, cands in sorted(rounds[first].items()):
            race, code = key
            party = PARTY[code]
            total = sum(v for _n, v in cands)
            ranked = sorted(cands, key=lambda x: -x[1])
            if len(cands) < 2:
                nominee[key] = cands[0][0] if cands else None
                continue
            fields += 1
            pair = set()
            if ranked[0][1] * 2 > total:
                winners = {ranked[0][0]}
                nominee[key] = ranked[0][0]
            else:
                r2 = rounds[second].get(key)
                if not r2:
                    raise SystemExit(f"South Carolina: {race} {party} ({RESULTS[first][0]}): no majority and no runoff in the results; read how it was settled")
                pair = {n for n, _v in r2}
                if {fold(n) for n in pair} != {fold(ranked[0][0]), fold(ranked[1][0])}:
                    raise SystemExit(f"South Carolina: {race} {party}: the runoff's pair {sorted(pair)} is not the primary's top two")
                winners = {n for n, _v in cands if fold(n) in {fold(x) for x in pair}}
                went[(second, key)] = RESULTS[second][4]
            for name, votes in ranked:
                note = []
                if name in winners and pair:
                    note.append(f"Went to the {long_date(date2)} runoff: no candidate won a majority.")
                shown_name, caps = shown(printed.get(fold(name), name))
                if caps:
                    note.append(CAPS)
                rows.append([race, f"{pre1}-{code}", date1, shown_name, party, party_code(party), None, 0, 0, votes,
                             round(100 * votes / total, 1) if total else None, "advanced" if name in winners else "lost",
                             None, None, f"sc-sec-2026-{first}-results", note])
        for key, cands in sorted(rounds[second].items()):
            race, code = key
            party = PARTY[code]
            if key not in rounds[first]:
                raise SystemExit(f"South Carolina: a runoff for {race} {party} with no first round")
            total = sum(v for _n, v in cands)
            ranked = sorted(cands, key=lambda x: -x[1])
            if len(cands) != 2 or ranked[0][1] == ranked[1][1]:
                raise SystemExit(f"South Carolina: the runoff for {race} {party} has {len(cands)} candidates or a tie")
            runoffs += 1
            nominee[key] = ranked[0][0]
            for name, votes in ranked:
                shown_name, caps = shown(printed.get(fold(name), name))
                rows.append([race, f"{pre2}-{code}", date2, shown_name, party, party_code(party), None, 0, 0, votes,
                             round(100 * votes / total, 1) if total else None, "advanced" if name == ranked[0][0] else "lost",
                             None, None, f"sc-sec-2026-{second}-results", [CAPS] if caps else []])

    # each round's winner: the nominee of the last round held must be the party's candidate in November; a winner
    # of an earlier round who is not on the November list keeps "advanced", with a plain note
    last = {}
    for kind in ORDER:
        for key, cands in rounds[kind].items():
            last[key] = kind
    for row in rows:
        if row[11] != "advanced":
            continue
        race, election = row[0], row[1]
        code = election.rsplit("-", 1)[1]
        key = (race, code)
        kind = next(k for k in ORDER if election == f"{RESULTS[k][3]}-{code}")
        if (RUNOFF_OF.get(kind), key) in went:
            continue                                   # went to a runoff; the runoff's own row says who won it
        on = [n for n, p in november.get(race, []) if LIST_CODE.get(p) == code]
        if any(fold(n) == fold(row[3]) for n in on):
            continue
        st = status_of.get((race, fold(row[3])))
        text = (f"Won the {'runoff' if 'runoff' in kind else 'primary'} but is not on the Election Commission's November list"
                + (f", which gives the status \"{st}\"." if st else "."))
        later = [k for k in ORDER[ORDER.index(kind) + 1:] if key in rounds[k] and k.startswith("special")]
        if later and not kind.startswith("special"):
            text += (f" The {PARTY[code]} nominee was chosen again in a special primary on August 11, 2026 (S.C. Code section "
                     f"7-11-55), and its runoff on August 25.")
        elif on:
            text += f" The list's {PARTY[code]} candidate is {on[0]}."
        row[15] = row[15] + [text]
        if last.get(key) == kind:
            differ.append(f"{race}: the {PARTY[code]} nominee of the last round held, {row[3]}, is not on the November list")
        gone.append(f"{row[3]} ({race} {election})")
    for key, name in nominee.items():
        if name and last.get(key) and key[0] in november:
            on = [n for n, p in november[key[0]] if LIST_CODE.get(p) == key[1]]
            if on and not any(fold(n) == fold(name) for n in on):
                differ.append(f"{key[0]}: the {PARTY[key[1]]} candidate on the November list is {on[0]}, not the nominee {name}")
    rows = [tuple(r[:15]) + (" ".join(r[15]) or None,) for r in rows]

    races = [r for (r,) in con.execute("SELECT race_id FROM races WHERE state = 'SC' ORDER BY race_id")]
    stray = [r for r in november if races and r not in races]
    if stray:
        raise SystemExit(f"South Carolina: the list names races not in the races table: {stray}")
    gaps = [(r, "The Election Commission's candidate list names no one on the November ballot for this race.") for r in races if r not in november]

    gen = lists["elections"]["general"]
    counts = "; ".join(f"{k}: {v}" for k, v in sorted(off.items()))
    with con:
        con.execute("DELETE FROM candidates WHERE race_id LIKE '2026-SC-%'")
        con.execute("DELETE FROM list_gaps WHERE state = 'SC'")
        con.executemany("INSERT OR REPLACE INTO candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", general + rows)
        con.executemany("INSERT INTO list_gaps VALUES (?, 'SC', ?)", gaps)
        record_source(con, "sc-sec-2026-general-list", path=lpath, level="federal", state="SC", kind="official candidate list",
                      agency="South Carolina State Election Commission",
                      title="Candidate Tracking System: 11/3/2026 Statewide General Election, U.S. Senate and U.S. House of Representatives",
                      url=gen["url"], published="", rows=sum(len(o["rows"]) for o in gen["offices"].values()),
                      note=f"Read through the page's own search ({CTS_PAGE}, then /Candidate/CandidateSearch/), every status and party; "
                           "columns taken by name: Office, Name on Ballot, Party, Candidate Status (the table has no contact columns; the "
                           "detail pages that do are never asked for). Status Active is on the November ballot. Left off, by the list's "
                           f"own status: {counts or 'none'}. The list gives no ballot positions; it is sorted by surname, and that order is "
                           "kept. It carries no write-in candidates. The same system's \"6/9/2026 Statewide Primary\" and \"8/11/2026 US "
                           "Senate Special Republican Primary\" lists were read to check the primary results"
                           + (": " + "; ".join(differ) + "." if differ else ": every candidate agrees.")
                           + (" Primary winners not on the November list: " + "; ".join(gone) + "." if gone else ""))
        for kind in ORDER + ("recount",):
            m = sites[kind]
            n = sum(len(v) for v in rounds[kind].values()) if kind in rounds else 0
            if kind == "recount":
                body = (f"Control only: the June 12 recount ({m['page']}, linked as \"{m['label']}\" from {RESULTS_PAGE}; headed "
                        f"\"{m['heading']}\", {m['counties']} counties) holds no federal contest, so the June 9 figures stand.")
            else:
                body = (f"The Commission's results site ({m['page']}, hosted by Clarity Elections, linked as \"{m['label']}\" from "
                        f"{RESULTS_PAGE}), headed \"{m['heading']}\", version {m['version']}, last updated {m['updated']}; all "
                        f"{m['counties']} counties completely reported and marked certified. Every candidate's vote types and counties "
                        "add up to the statewide total, and the summary report (summary.csv) gives the same totals. No write-in line "
                        "is reported, so a field's total is the sum of its candidates' votes."
                        + (f" Held under S.C. Code section 7-11-55 after the death of the Republican nominee ({NOTICE})."
                           if kind == "special" else ""))
            m_up = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", m["updated"] or "")
            record_source(con, f"sc-sec-2026-{kind}-results", path=os.path.join(folder, m["detail"]), level="federal", state="SC",
                          kind="official results", agency="South Carolina State Election Commission",
                          title=f"{m['name']} ({m['date']}), Official Results: detail report (XML)",
                          url=m["detail_url"], rows=n,
                          published=f"{m_up.group(3)}-{int(m_up.group(1)):02d}-{int(m_up.group(2)):02d}" if m_up else "",
                          note=body)
    say(f"    South Carolina: {sum(1 for r in november if '-H' in r)} House districts and {'the' if senate_id('SC', 2) in november else 'no'} "
        f"Senate race, {len(general)} candidates on the November ballot ({sum(off.get(s, 0) for s in off if s not in ('Defeated In Primary', 'Defeated At Convention', 'Withdrew Before Primary'))} "
        f"withdrawn, removed or deceased left off); {fields} party primaries with a field and {runoffs} runoffs, the Senate's special "
        f"Republican primary included, votes from the official results" + (f"; primary winners not on the November list: {', '.join(gone)}" if gone else ""))
    for d in differ:
        say("      " + d)
    if gaps:
        say("      races with no November candidates on the list: " + ", ".join(g[0] for g in gaps))
    return len(general)
