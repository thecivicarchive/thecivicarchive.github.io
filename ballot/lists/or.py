"""
Oregon: the Secretary of State's Elections Division (sos.oregon.gov/elections). Two sources, both answering scripts.

The November ballot is the Division's candidate filing search in ORESTAR ("Search Candidate & Campaign Filings", linked
from sos.oregon.gov/elections; secure.sos.state.or.us/orestar/CFSearchPage.do, "Candidate Filings"). The loader asks it
what the page asks: the elections of 2026 (the page's own list, /orestar/ajaxdataserver/getCandidateElectionByYear,
names "2026 General Election" and "2026 Primary Election"), then every filing for US Senator and for US Representative in
each, with the page's "include disqualified" box ticked, and once more by withdrawal date (1 January 2025 to 31 December
2026), which is the only way the search shows a withdrawn filing. The form carries the site's anti-forgery token, which
the page's own script fetches (POST /orestar/JavaScriptServlet with FETCH-CSRF-TOKEN) and adds; the loader does the
same. The result grid has seven columns (Ballot Name, Party, Office, Election, Filing Method, Filing Date, Qualified), none
of them contact details; each is taken by name, and the row count is checked against the page's own "N found" line (the
page shows at most 50 rows, so 50 or more stops the loader). The page's Export and Printable Report files and each
filing's detail page are never fetched. The cached copy (ballot_cache/or/) keeps the seven columns for the federal rows.

Oregon lets more than one party nominate the same candidate, and ORESTAR lists each nomination as a filing of its own
(Filing Method "Nominated" for the primary's nominee, "Minor Party" for a minor party's nomination). The November ballot
is one row per candidate, with every nominating party, shown in the order the nominations were filed ("Democrat, Working
Families"); the list does not say in which order the ballot prints them. A filing with Qualified "No" is left off and
counted; so are withdrawn filings; any other value stops the loader. A "Write In" filing would be a declared write-in
(write_in 1, no ballot position); there is none for Congress in 2026. The list gives no ballot order, so its own order (by
surname) is kept. Parties are printed in full and kept as printed ("Democrat", "Pacific Green"). "Independent" on
Oregon's lists is a political party, apart from "Nonaffiliated" (no party): ORESTAR's own party key lists both, and those
rows say so. Names are printed in ordinary capitals and kept as printed.

The May 19 primary is the Division's "2026 May Primary Election Official Results" (record EPD/26/3 in the Secretary's
records system: records.sos.state.or.us/ORSOSCMSearch/Search/DocumentStream.ashx?uri=16180585; its pages are headed "May
19, 2026, Primary Election Abstract of Votes"), found through the Election History page's own list
(sos.oregon.gov/elections/Lists/History, asked through SharePoint's REST address, the row for the May 19, 2026 Primary
and its "Official Results" link), and read with ballot/pdftext.py. A contest is an office (US Senator; US
Representative, with its district) and a party (Democrat, Republican): the candidates' family names across the top (the
nominee marked *), their given names under them, then one row per county and a Total row, all right-aligned in columns,
so each cell is placed in a column by its right edge, the columns taken from the Total row. "Misc." is write-in votes
(votes for names not printed on the ballot, not a candidate). Checks: every column's county rows add up to its Total;
each contest's names are exactly that party's qualified filings on ORESTAR's 2026 Primary Election list, and every
filing there has a contest; the nominee marked * is the top vote-getter and is the party's "Nominated" filing on the
November list. A party primary becomes a field when two or more were on its ballot; a field's total is its candidates'
votes plus Misc.; only Democrats and Republicans held primaries for Congress in 2026 (the minor parties' nominations
were filed with the Division in July and August, Filing Method "Minor Party"). Names on primary rows are the ORESTAR
ballot names, matched to the abstract's family and given names. Every November candidate matched an FEC registration
when the loader was written (2026-09-30).
"""

import collections
import html as H
import http.cookiejar
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

from ballot.common import fold, house_id, party_code, record_source, senate_id
from ballot.pdftext import PDF, rows as pdf_rows
from states import net

ORESTAR = "https://secure.sos.state.or.us/orestar/"
SEARCH_PAGE = ORESTAR + "CFSearchPage.do"
HISTORY_API = "https://sos.oregon.gov/elections/_api/web/GetList('/elections/Lists/History')/items?$top=500"
HISTORY_PAGE = "https://sos.oregon.gov/elections/Pages/historical-data.aspx"
RECORDS = "https://records.sos.state.or.us/ORSOSCMSearch/Search/"
ELECTIONS = {"general": "2026 General Election", "primary": "2026 Primary Election"}
OFFICES = {"USS": "US Senator", "USR": "US Representative"}
KEEP = ("Ballot Name", "Party", "Office", "Election", "Filing Method", "Filing Date", "Qualified")
PRIMARY = "2026-05-19"
CODES = {"Democrat": "DEM", "Republican": "REP", "Libertarian": "LIB"}      # other parties would take ORESTAR's own code
TITLE = "May 19, 2026, Primary Election Abstract of Votes"
NUM = re.compile(r"\d{1,3}(?:,\d{3})*")
WRITE_IN = "Write-in candidate: the name is not printed on the ballot."
INDEPENDENT = "On Oregon's lists Independent is a political party, apart from Nonaffiliated (no party)."


def text(cell):
    return re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", cell)).replace("\xa0", " ")).strip()


def race_of(office):
    if office == "US Senator":
        return senate_id("OR", 2)
    m = re.fullmatch(r"US Representative, (\d+)(?:st|nd|rd|th) District", office or "")
    if m:
        return house_id("OR", int(m.group(1)))
    raise SystemExit(f"Oregon: an ORESTAR row names an office that is not read ({office!r})")


def us_date(d):
    """06/25/2026 -> 2026-06-25."""
    m = re.fullmatch(r"(\d\d)/(\d\d)/(\d{4})", d or "")
    if not m:
        raise SystemExit(f"Oregon: a filing date on ORESTAR that is not read ({d!r})")
    return f"{m.group(3)}-{m.group(1)}-{m.group(2)}"


class Orestar:
    """One ORESTAR session: its cookies, the search form's address and the anti-forgery token the page's script adds."""

    def __init__(self):
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.op.addheaders = [("User-Agent", net.UA)]
        page = self.open(SEARCH_PAGE).decode("utf-8", "replace")
        m = re.search(r'<form name="cfSearchPageForm" method="post" action="([^"]+)"', page)
        if not m:
            raise SystemExit(f"Oregon: {SEARCH_PAGE} no longer has the candidate filing search form")
        self.action = urllib.parse.urljoin(SEARCH_PAGE, H.unescape(m.group(1)))
        self.parties = dict(re.findall(r'<option value="([A-Z]+)">([^<]+)</option>',
                                       re.search(r'<select name="cfPartyAffiliation".*?</select>', page, re.S).group(0)))
        pair = self.open(ORESTAR + "JavaScriptServlet", data=b"", headers={"FETCH-CSRF-TOKEN": "1", "X-Requested-With": "XMLHttpRequest"})
        name, _, value = pair.decode().strip().partition(":")
        if not re.fullmatch(r"[A-Z_]+", name) or not value:
            raise SystemExit("Oregon: ORESTAR's search page no longer hands out its form token as it did")
        self.token = (name, value)
        got = self.open(ORESTAR + "ajaxdataserver/getCandidateElectionByYear?elecYear=2026").decode("utf-8", "replace")
        self.elections = {text(n): v for n, v in re.findall(r"<item><name>(.*?)</name><value>(\d+)</value></item>", got)}
        for label in ELECTIONS.values():
            if label not in self.elections:
                raise SystemExit(f"Oregon: ORESTAR's list of 2026 elections no longer names {label!r} ({sorted(self.elections)})")

    def open(self, url, data=None, headers=None):
        for attempt in range(3):
            try:
                req = urllib.request.Request(url, data=data, headers={"Referer": SEARCH_PAGE, **(headers or {})})
                with self.op.open(req, timeout=120) as r:
                    body = r.read()
                time.sleep(1.5)
                return body
            except urllib.error.HTTPError as e:      # asked at most twice more, then left alone
                if attempt == 2:
                    raise SystemExit(f"Oregon: ORESTAR answered {e.code} for {url.split('?')[0]} three times; nothing is loaded")
                time.sleep(15 * (attempt + 1))

    def search(self, election, office, withdrawn=False):
        """The kept columns of every filing the search returns, and the page's own count."""
        fields = {"cfSearchButtonName": "", "cfName": "", "cfyearActive": "2026", "cfElection": self.elections[election],
                  "cfOffice": office, "cfOfficeGrp": "", "cfPartyAffiliation": "", "cfDisqualifiedCandidates": "on",
                  "cfFilingType": "", "cfFilingFromDate": "", "cfFilingToDate": "",
                  "cfWithDrawFromDate": "01/01/2025" if withdrawn else "", "cfWithDrawToDate": "12/31/2026" if withdrawn else "",
                  self.token[0]: self.token[1]}
        page = self.open(self.action, data=urllib.parse.urlencode(fields).encode()).decode("utf-8", "replace")
        if "Candidate Filing Search Results" not in page:
            raise SystemExit(f"Oregon: ORESTAR did not return its search results for {election}, {OFFICES[office]}")
        crit = re.search(r"Election Year: 2026, Election: ([^,<]+), Office: ([^,<]+?)\s*(?:,[^<]*)?</td>", page)
        if not crit or crit.group(1).strip() != election or crit.group(2).strip() != OFFICES[office]:
            raise SystemExit(f"Oregon: ORESTAR answered a different search than {election}, {OFFICES[office]}")
        found = re.search(r"(\d+) found for the above search criteria", page)
        if not found:
            raise SystemExit(f"Oregon: ORESTAR's results for {election}, {OFFICES[office]} no longer say how many were found")
        n = int(found.group(1))
        table = re.search(r'<table id="cfSearchResults".*?</table>', page, re.S)
        out = []
        if table:
            heads = [text(h) for h in re.findall(r"<th[^>]*>(.*?)</th>", table.group(0), re.S)]
            if not all(k in heads for k in KEEP) or len(set(heads)) != len(heads):
                raise SystemExit(f"Oregon: ORESTAR's result columns changed ({heads})")
            idx = {k: heads.index(k) for k in KEEP}
            for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", table.group(0), re.S):
                tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
                if not tds or (n == 0 and len(tds) == 1 and text(tds[0]).startswith("No data found")):
                    continue
                if len(tds) != len(heads):
                    raise SystemExit("Oregon: an ORESTAR result row does not line up with its headings")
                out.append({k: text(tds[i]) for k, i in idx.items()})
        if n >= 50 or len(out) != n:
            raise SystemExit(f"Oregon: ORESTAR counts {n} filings for {election}, {OFFICES[office]}; {len(out)} were read "
                             "(the page shows at most 50)")
        for r in out:
            if r["Election"] != election:
                raise SystemExit(f"Oregon: an ORESTAR row for {election} names another election ({r['Election']!r})")
        return out


def read_lists(folder, say):
    """{"general": {...}, "primary": {...}} from ORESTAR, kept on disk (kept columns only) for two days."""
    path = os.path.join(folder, "or_2026_orestar_federal.json")
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < 2 * 86400:
        return json.load(open(path, encoding="utf-8")), path
    s = Orestar()
    out = {"page": SEARCH_PAGE, "parties": s.parties}
    for kind, label in ELECTIONS.items():
        filed, withdrawn = [], []
        for office in OFFICES:
            filed += s.search(label, office)
            withdrawn += s.search(label, office, withdrawn=True)
        out[kind] = {"election": label, "id": s.elections[label], "rows": filed, "withdrawn": withdrawn}
        say(f"      ORESTAR Candidate Filings, {label}: {len(filed)} federal filings, {len(withdrawn)} withdrawn")
    os.makedirs(folder, exist_ok=True)
    json.dump(out, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return out, path


def results_pdf(folder):
    """The official results of the May 19 primary, found through the Election History page's own list."""
    info_path = os.path.join(folder, "or_2026_primary_results_record.json")
    pdf = os.path.join(folder, "or_2026_primary_official_results.pdf")
    if not (os.path.exists(info_path) and os.path.exists(pdf) and time.time() - os.path.getmtime(info_path) < 30 * 86400):
        items = json.loads(net.get(HISTORY_API, accept="application/json;odata=nometadata"))["value"]
        row = [x for x in items if (x.get("Election_x0020_Date") or "").startswith(PRIMARY) and x.get("Election_x0020_Type") == "Primary"]
        if len(row) != 1:
            raise SystemExit(f"Oregon: the Election History list has {len(row)} rows for the {PRIMARY} primary")
        links = [(H.unescape(h), text(t)) for h, t in re.findall(r'href="([^"]+)"[^>]*>(.*?)</a>', row[0].get("Results") or "", re.S)]
        uri = [re.search(r"uri=(\d+)", h).group(1) for h, t in links if "official results" in t.lower() and re.search(r"uri=(\d+)", h)]
        if len(uri) != 1:
            raise SystemExit("Oregon: the Election History list's May 19, 2026 row no longer links one Official Results record")
        info = {"record": RECORDS + "RecordViewer.aspx?uri=" + uri[0], "url": RECORDS + "DocumentStream.ashx?uri=" + uri[0],
                "title": row[0].get("Title")}
        if os.path.exists(pdf):
            os.remove(pdf)
        net.download(info["url"], pdf, max_age_days=30)
        os.makedirs(folder, exist_ok=True)
        json.dump(info, open(info_path, "w", encoding="utf-8"), indent=1)
    info = json.load(open(info_path, encoding="utf-8"))
    data = open(pdf, "rb").read()
    if data[:5] != b"%PDF-":
        raise SystemExit(f"Oregon: {os.path.basename(pdf)} is not a PDF; delete it and run again")
    m = re.search(rb"/CreationDate\s*\(D:(\d{4})(\d\d)(\d\d)", data)
    info["published"] = "-".join(x.decode() for x in m.groups()) if m else ""
    return pdf, info


def cells(runs):
    """A printed row's runs as cells [x0, x1, text]: pieces closer than a fifth of the type are one cell."""
    out = []
    for x0, _y, size, t, x1 in sorted(runs, key=lambda r: r[0]):
        if out and x0 - out[-1][1] <= 0.18 * size:
            out[-1][1], out[-1][2] = max(out[-1][1], x1), out[-1][2] + t
        else:
            out.append([x0, x1, t])
    return [(x0, x1, re.sub(r"\s+", " ", t).strip()) for x0, x1, t in out if t.strip()]


def abstract(path, parties):
    """{(race, party): {"names": [(given, family, nominee)], "votes": [...], "misc": n, "counties": n}} for every congressional
    party contest, from its Total rows, after the checks in the note above."""
    pdf = PDF(open(path, "rb").read())
    contests, titled = {}, False
    for n, (page, res) in enumerate(pdf.pages(), start=1):
        prow = [(y, cells(rs)) for y, rs in pdf_rows(pdf, page, res)]
        prow = [(y, cs) for y, cs in prow if cs]
        heads = [" ".join(c[2] for c in cs) for _y, cs in prow[:3]] + ["", "", ""]
        if heads[1] not in ("US Senator", "US Representative"):
            continue
        if heads[0] != TITLE:
            raise SystemExit(f"Oregon: page {n} of the official results is not headed {TITLE!r}")
        titled = True
        if heads[1] == "US Senator":
            race, start = senate_id("OR", 2), 2
        elif heads[1] == "US Representative":
            m = re.fullmatch(r"(\d)(?:st|nd|rd|th) District", heads[2])
            if not m:
                raise SystemExit(f"Oregon: page {n} of the official results names no district under US Representative")
            race, start = house_id("OR", int(m.group(1))), 3
        sections, cur = [], None
        for y, cs in prow[start:]:
            line = " ".join(c[2] for c in cs)
            party = re.sub(r" \(cont\.\)$", "", line)
            if party in parties and all(c[0] < 150 for c in cs):
                cur = {"party": party, "head": [], "given": [], "data": [], "total": None, "phase": "head"}
                sections.append(cur)
            elif line in ("* Nominee", "** Elected", "WI = Write In"):
                cur = None
            elif cur is None:
                raise SystemExit(f"Oregon: a line on page {n} of the official results is not read ({line[:40]!r})")
            elif cur["phase"] == "head" and cs[0][2] == "County":
                cur["given"].append(cs[1:])
                cur["phase"] = "given"
            elif cur["phase"] == "head":
                cur["head"].append(cs)
            elif cur["phase"] in ("given", "data") and cs[0][2] == "Total":
                cur["total"], cur["phase"] = cs[1:], "done"
            elif cur["phase"] in ("given", "data") and len(cs) > 1 and not NUM.fullmatch(cs[0][2]) and all(NUM.fullmatch(c[2]) for c in cs[1:]):
                cur["data"].append(cs)
                cur["phase"] = "data"
            elif cur["phase"] == "given":
                cur["given"].append(cs)
            else:
                raise SystemExit(f"Oregon: a line on page {n} of the official results is not read ({cs[0][2]!r})")
        if not sections:
            raise SystemExit(f"Oregon: page {n} of the official results has no party contest")
        for s in sections:
            where = f"{race} {s['party']} (page {n})"
            if not s["total"] or not all(NUM.fullmatch(c[2]) for c in s["total"]):
                raise SystemExit(f"Oregon: no Total row read for {where}")
            cols = [c[1] for c in s["total"]]
            col_of = lambda x1: next((i for i, c in enumerate(cols) if c >= x1 - 3), None)
            labels = [[] for _ in cols], [[] for _ in cols]
            for k, rows_ in ((0, s["head"]), (1, s["given"])):
                for cs in rows_:
                    for x0, x1, t in cs:
                        i = col_of(x1)
                        if i is None:
                            raise SystemExit(f"Oregon: a name under {where} lies right of every column ({t!r})")
                        labels[k][i].append(t)
            fam = [" ".join(x) for x in labels[0]]
            giv = [" ".join(x) for x in labels[1]]
            if any(re.search(r"\bWI\b|write", f, re.I) for f in fam):
                raise SystemExit(f"Oregon: a write-in candidate has a column of its own under {where}; the reader does not expect one")
            misc = fam[-1] == "Misc."
            if misc and giv[-1]:
                raise SystemExit(f"Oregon: the Misc. column under {where} has a given name")
            k = len(cols) - (1 if misc else 0)
            if not all(fam[:k]) or not all(giv[:k]) or any(f == "Misc." for f in fam[:k]):
                raise SystemExit(f"Oregon: a candidate column under {where} is missing a name")
            sums, counties = [0] * len(cols), 0
            for cs in s["data"]:
                county = " ".join(c[2] for c in cs if not NUM.fullmatch(c[2]))
                vals = [None] * len(cols)
                for x0, x1, t in cs:
                    if NUM.fullmatch(t):
                        i = next((i for i, c in enumerate(cols) if abs(c - x1) <= 2.5), None)
                        if i is None or vals[i] is not None:
                            raise SystemExit(f"Oregon: a count under {where} is not in a column ({county})")
                        vals[i] = int(t.replace(",", ""))
                if None in vals:
                    raise SystemExit(f"Oregon: {county} under {where} is missing a count")
                sums = [a + b for a, b in zip(sums, vals)]
                counties += 1
            total = [int(c[2].replace(",", "")) for c in s["total"]]
            if sums != total:
                raise SystemExit(f"Oregon: the county rows under {where} do not add up to the Total row")
            f = contests.setdefault((race, s["party"]), {"names": [], "votes": [], "misc": 0, "counties": counties, "pages": []})
            f["pages"].append(n)
            for i in range(k):
                f["names"].append((giv[i], fam[i].lstrip("*"), fam[i].startswith("*") and not fam[i].startswith("**")))
                f["votes"].append(total[i])
            f["misc"] += total[-1] if misc else 0
    if not titled:
        raise SystemExit("Oregon: the file is not the abstract of votes of the May 19, 2026 primary")
    return contests


def load(con, cache, say=print):
    net.patient_lookups()
    folder = os.path.join(cache, "or")
    lists, lpath = read_lists(folder, say)
    rpath, info = results_pdf(folder)
    gen, pri, key = lists["general"], lists["primary"], lists["parties"]
    names = set(key.values())

    # the November ballot: one row per candidate, every nominating party in the order filed
    by_cand, order, off, write_ins, nominated = collections.OrderedDict(), [], [], [], {}
    for r in gen["rows"]:
        race, name, party = race_of(r["Office"]), r["Ballot Name"].replace("*", "").strip(), r["Party"]
        if party not in names:
            raise SystemExit(f"Oregon: the general list names a party not in ORESTAR's party key ({party!r})")
        if r["Qualified"] == "No":
            off.append(f"{name} ({party}, {race}, not qualified)")
            continue
        if r["Qualified"] != "Yes":
            raise SystemExit(f"Oregon: a Qualified value on the general list that is not read ({r['Qualified']!r})")
        if r["Filing Method"] == "Nominated":
            if (race, party) in nominated:
                raise SystemExit(f"Oregon: the general list names two {party} nominees for {race}")
            nominated[(race, party)] = fold(name)
        c = by_cand.setdefault((race, fold(name)), {"race": race, "name": name, "filings": []})
        if c["name"] != name:
            raise SystemExit(f"Oregon: one candidate's ballot name differs between filings ({c['name']!r}, {name!r})")
        c["filings"].append((us_date(r["Filing Date"]), party, r["Filing Method"]))
    off += [f"{r['Ballot Name']} ({r['Party']}, {race_of(r['Office'])}, withdrew)" for r in gen["withdrawn"]]

    rows, count = [], collections.Counter()
    for (race, _k), c in by_cand.items():
        filings = sorted(c["filings"], key=lambda f: f[0])
        methods = {m for _d, _p, m in filings}
        if methods - {"Nominated", "Minor Party", "Completed Petitions", "Assembly", "Auto Nominated", "Write In", "Vacancy",
                      "Selected by Secretary of State"}:
            raise SystemExit(f"Oregon: a filing method on the general list that is not read ({sorted(methods)}, {c['name']})")
        wi = methods == {"Write In"}
        if "Write In" in methods and not wi:
            raise SystemExit(f"Oregon: {c['name']} is both nominated and a declared write-in for {race}")
        parties = [p for _d, p, _m in filings]
        if len(set(parties)) != len(parties):
            raise SystemExit(f"Oregon: {c['name']} has two filings for one party for {race}")
        party = ", ".join(parties)
        notes = []
        if len(parties) > 1:
            notes.append(f"Nominated by more than one party; Oregon's list has a filing for each ({', then '.join(parties)}), "
                         "and the parties are shown in the order the nominations were filed.")
        if "Independent" in parties:
            notes.append(INDEPENDENT)
        if wi:
            notes.append(WRITE_IN)
            write_ins.append(c["name"])
            position = None
        else:
            count[race] += 1
            position = count[race]
        rows.append((race, "general", "2026-11-03", c["name"], party, party_code(party), position, 0, int(wi), None, None, None,
                     None, None, "or-sos-2026-general-list", " ".join(notes) or None))

    # who was on each party's primary ballot, from ORESTAR's primary list
    ballot, not_qualified = collections.defaultdict(dict), []
    for r in pri["rows"]:
        race, name, party = race_of(r["Office"]), r["Ballot Name"].replace("*", "").strip(), r["Party"]
        if r["Qualified"] == "No":
            not_qualified.append(f"{name} ({party}, {race})")
            continue
        if r["Qualified"] != "Yes" or r["Filing Method"] not in ("Fee", "Completed Petitions"):
            raise SystemExit(f"Oregon: a primary filing that is not read ({r['Qualified']!r}, {r['Filing Method']!r}, {race})")
        ballot[(race, party)][fold(name)] = name
    withdrew = [f"{r['Ballot Name']} ({r['Party']}, {race_of(r['Office'])})" for r in pri["withdrawn"]]
    for kind in (gen, pri):
        filing = lambda r: (fold(r["Ballot Name"]), r["Office"], r["Party"])
        both = {filing(r) for r in kind["rows"]} & {filing(r) for r in kind["withdrawn"]}
        if both:
            raise SystemExit(f"Oregon: ORESTAR lists a filing as both standing and withdrawn ({sorted(both)})")

    contests = abstract(rpath, {p for _race, p in ballot} | {"Democrat", "Republican"})
    if set(contests) != set(ballot):
        raise SystemExit(f"Oregon: the official results' contests ({sorted(contests)}) are not the primary list's ({sorted(ballot)})")
    fields, primary_rows, upset = 0, 0, []
    for (race, party), f in sorted(contests.items()):
        filed = ballot[(race, party)]
        shown = []
        for given, family, _nom in f["names"]:
            full = fold(f"{given} {family}")
            if full not in filed:
                hits = [k for k in filed if k.split()[-1] == fold(family).split()[-1]]
                if len(hits) != 1:
                    raise SystemExit(f"Oregon: {given} {family} ({race} {party}) in the official results is not on the primary list")
                full = hits[0]
            shown.append(filed[full])
        if sorted(fold(s) for s in shown) != sorted(filed):
            raise SystemExit(f"Oregon: the official results' candidates for {race} {party} are not the primary list's")
        marked = [i for i, (_g, _f, nom) in enumerate(f["names"]) if nom]
        top = max(range(len(f["votes"])), key=lambda i: f["votes"][i])
        if marked != [top] or sorted(f["votes"])[-2:-1] == [f["votes"][top]]:
            upset.append(f"{race} {party} (marked nominee is not the one top vote-getter)")
        if nominated.get((race, party)) != fold(shown[top]):
            upset.append(f"{race} {party} (the November list's nominee is not the primary's)")
        if len(shown) < 2:
            continue
        fields += 1
        total = sum(f["votes"]) + f["misc"]
        code = CODES.get(party) or next(c for c, p in key.items() if p == party)
        for i in sorted(range(len(shown)), key=lambda i: -f["votes"][i]):
            v = f["votes"][i]
            rows.append((race, f"primary-{code}", PRIMARY, shown[i], party, party_code(party), None, 0, 0, v,
                         round(100 * v / total, 1) if total else None, "advanced" if i == top else "lost", None, None,
                         "or-sos-2026-primary-results", None))
            primary_rows += 1
    if upset:
        raise SystemExit(f"Oregon: the primary and the November list disagree: {'; '.join(upset)}; read the files again")
    stray = sorted(f"{race} {p}" for race, p in nominated if (race, p) not in contests)
    if stray:
        raise SystemExit(f"Oregon: a primary nominee on the November list has no contest in the official results ({stray})")

    races = [r for (r,) in con.execute("SELECT race_id FROM races WHERE state = 'OR' ORDER BY race_id")]
    general = [r for r in rows if r[1] == "general"]
    gaps = [(race, "Oregon's candidate list for November names no candidates for this race yet.")
            for race in races if not any(r[0] == race for r in general)]
    unknown = sorted({r[0] for r in rows} - set(races))
    if unknown:
        raise SystemExit(f"Oregon: rows for races that are not in the races table ({unknown})")
    fusion = sum(1 for r in general if "," in (r[4] or ""))
    with con:
        con.execute("DELETE FROM candidates WHERE race_id LIKE '2026-OR-%'")
        con.execute("DELETE FROM list_gaps WHERE state = 'OR'")
        con.executemany("INSERT OR REPLACE INTO candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        con.executemany("INSERT INTO list_gaps VALUES (?, 'OR', ?)", gaps)
        record_source(con, "or-sos-2026-general-list", path=lpath, level="federal", state="OR", kind="official candidate list",
                      agency="Oregon Secretary of State, Elections Division",
                      title="ORESTAR Candidate Filings: 2026 General Election, US Senator and US Representative",
                      url=SEARCH_PAGE, rows=len(gen["rows"]),
                      note="Read through the search page's own form (with its anti-forgery token), every filing for each office with "
                           "disqualified filings included, and again by withdrawal date; the page's count checked. Ballot name, party, "
                           "office, election, filing method, filing date and Qualified only; the Export file, the printable report and "
                           "the filings' detail pages are never fetched. One row per candidate: a candidate nominated by several "
                           f"parties has a filing for each, and the parties are shown in filing order ({fusion} such candidates). The "
                           f"list gives no ballot order; its order (by surname) is kept. Left off: {'; '.join(off) or 'none'}. "
                           f"Declared write-ins: {len(write_ins)}.")
        record_source(con, "or-sos-2026-primary-list", path=lpath, level="federal", state="OR", kind="official candidate list",
                      agency="Oregon Secretary of State, Elections Division",
                      title="ORESTAR Candidate Filings: 2026 Primary Election, US Senator and US Representative",
                      url=SEARCH_PAGE, rows=len(pri["rows"]),
                      note="Used to check the official results (every name under a party's contest is that party's qualified filing, "
                           "and the other way round) and for the ballot names on the primary rows. Not qualified, not on the ballot: "
                           f"{'; '.join(not_qualified) or 'none'}. Withdrawn before the primary: {'; '.join(withdrew) or 'none'}.")
        record_source(con, "or-sos-2026-primary-results", path=rpath, level="federal", state="OR", kind="official results",
                      agency="Oregon Secretary of State, Elections Division",
                      title="2026 May Primary Election Official Results (May 19, 2026, Primary Election Abstract of Votes)",
                      url=info["url"], published=info.get("published", ""), rows=primary_rows,
                      note=f"Linked as Official Results from the Election History page ({HISTORY_PAGE}); record viewer "
                           f"{info['record']}. Votes from each contest's Total row; every column's county rows add up to it. A field's "
                           "total is its candidates' votes plus Misc. (write-in votes). Names are the ORESTAR ballot names, matched to "
                           "the abstract's family and given names; the nominee marked * is the top vote-getter and the November "
                           "list's nominee in every contest.")
    say(f"    Oregon: 6 House districts and the Senate race, {len(general)} candidates on the November ballot "
        f"({fusion} nominated by more than one party; {len(off)} left off{', ' + str(len(write_ins)) + ' declared write-in' if write_ins else ''}); "
        f"{fields} party primaries with a field ({primary_rows} candidates), votes from the official abstract, county sums checked"
        + (f"; no list yet for {', '.join(g[0] for g in gaps)}" if gaps else ""))
    return len(general)
