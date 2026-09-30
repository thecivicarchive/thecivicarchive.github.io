"""
Idaho: the Secretary of State's Elections Division (voteidaho.gov). Two sources, both answering scripts.

The November ballot is the Division's "Search Filed Candidates List" (run.voteidaho.gov/search, linked from
voteidaho.gov/candidate-filing/), a page of the Idaho Candidate Filing Portal that asks the portal's own public service
(api-run.voteidaho.gov/api) for its rows; the loader asks the same service the same questions the page does: the
public list of elections ("November 03, 2026 - 2026 GENERAL", "May 19, 2026 - 2026 PRIMARY"), the district types
(Federal is code FED), then every filed candidate for that election and district type, 100 to a page, the count checked
against the service's own "candidatesFound". The service also says whether the Division has marked the list final
("isFinalList"), and the note on the source says which. Its rows carry, besides what the page shows, a mailing address
and a voter number, which are never read: only the ballot name, the office, the district, the party, the write-in mark,
the filing status and a withdrawal date are taken, and the cached copy (ballot_cache/id/) keeps only those.

A row with the status Approved is on the November ballot; Withdrawn is left off and counted (with its date); any other
status stops the loader. A write-in mark would make a declared write-in (write_in 1, no ballot position); there is none
for Congress in 2026. The list gives no ballot order, so its own order is kept. Parties are printed in full and kept as
printed (Constitution, Democratic, Libertarian, Republican, Independent, Non-Partisan); the election codes come from the
portal's own party key (CON, DEM, LIB, REP, IND, NOP). Names are printed in ordinary capitals and kept as printed.

The May 19 primary is the Division's "Canvass Report" (archive.voteidaho.gov/results/2026/primary/canvass_report_2026_
primary.pdf, linked from voteidaho.gov/election-results/; its pages are headed "Idaho Detailed Results by Contest,
Primary Election - May 19, 2026"), read with ballot/pdftext.py. Each contest ("United States Representative District 1
- Democratic") has the candidates across the top with the party's code under each, then Over Votes, Under Votes, Total
Registered Voters and Total Votes Cast, county by county, and a "Contest Total" row; a contest runs over pages with its
headings repeated. Cells are placed in columns by the headings' left edges. Checks: every county row's candidates, over
votes and under votes add up to its Total Votes Cast; the county rows add up to the Contest Total, column by column;
every name under a contest is on the same party's primary ballot in the filing portal's "2026 PRIMARY" list, and the
other way round. A count the canvass protects is printed "**" (footnoted "Protected"; in 2026 only some small counties'
over votes in the Libertarian contests); such a row is not added up, the protected column's county sum need only not
exceed the Contest Total, and a protected candidate count or Contest Total stops the loader. Only the Contest Total is stored. The canvass prints no write-in column for Congress, so a field's total
is its candidates' votes; over and under votes are left out. A party primary becomes a field when two or more were on
its ballot. The nominee is the one the November list names for that party, in any status (a nominee who withdrew later
stays on the list as Withdrawn), and must be the field's top vote-getter; a nominee not on the November ballot keeps
"advanced" with a note saying so. Independents file in the primary period but are not on a primary ballot. The two
Constitution Party candidates (one in each House district, each alone) are on the portal's primary list but have no
contest in the canvass; neither was a field.
"""

import datetime as dt
import json
import os
import re
import time
from urllib.request import Request, urlopen

from ballot.common import fold, house_id, party_code, record_source, senate_id
from ballot.pdftext import PDF, join, rows as pdf_rows
from states import net

PAGE = "https://run.voteidaho.gov/search"
API = "https://api-run.voteidaho.gov/api/"
CANVASS_URL = "https://archive.voteidaho.gov/results/2026/primary/canvass_report_2026_primary.pdf"
ELECTIONS = {"general": "2026 GENERAL", "primary": "2026 PRIMARY"}
KEEP = ("candidateName", "officeName", "districtType", "district", "seat", "partyName", "isWriteIn", "filingStatus",
        "filingStatusCode", "withdrawalDate")
OFFICES = ("United States Senator", "United States Representative")
HEADING = re.compile(r"^United States (?:Senator|Representative District (?P<district>\d+)) - (?P<party>[A-Z][a-z]+(?:[- ][A-Z][a-z]+)*)$")
WRITE_IN = "Write-in candidate: the name is not printed on the ballot."
PROTECTED = object()      # "**": a count the canvass protects (small numbers in a county); its footnote says only "Protected"
MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")


def post(path, body):
    req = Request(API + path, data=json.dumps(body).encode(), method="POST",
                  headers={"User-Agent": net.UA, "Content-Type": "application/json", "Accept": "application/json",
                           "Origin": "https://run.voteidaho.gov", "Referer": "https://run.voteidaho.gov/"})
    with urlopen(req, timeout=120) as r:
        got = json.loads(r.read())
    time.sleep(1.5)
    if not got.get("succeeded"):
        raise SystemExit(f"Idaho: the filing portal's service refused {path} ({got.get('error')})")
    return got["data"]


def iso(text):
    """'May 19, 2026' or '2026-09-01T21:08:45.123' -> '2026-05-19' / '2026-09-01'."""
    m = re.fullmatch(r"([A-Z][a-z]+) (\d\d?), (\d{4})", (text or "").strip())
    if m and m.group(1) in MONTHS:
        return f"{m.group(3)}-{MONTHS.index(m.group(1)) + 1:02d}-{int(m.group(2)):02d}"
    m = re.match(r"(\d{4})-(\d\d)-(\d\d)", text or "")
    return "-".join(m.groups()) if m else ""


def spoken(day):
    d = dt.date.fromisoformat(day)
    return f"{MONTHS[d.month - 1]} {d.day}, {d.year}"


def read_lists(folder, say):
    """{"general": {...}, "primary": {...}} from the filing portal, kept on disk (kept columns only) for two days."""
    path = os.path.join(folder, "id_2026_filed_candidates_federal.json")
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < 2 * 86400:
        return json.load(open(path, encoding="utf-8")), path
    elections = post("PublicLookup/GetAllElections", {"isFutureElections": False})
    kinds = post("Filing/GetAllDistrictTypes", {"isSearch": True})
    fed = next((k["value"] for k in kinds if k.get("code") == "FED"), None)
    parties = {p["name"]: p["code"] for p in post("Filing/GetLookupValues", {"tableName": "Party"})}
    if not fed or not parties:
        raise SystemExit("Idaho: the filing portal no longer lists the Federal district type or its party key")
    out = {"page": PAGE, "service": API + "FiledCandidates/SearchCandidates", "parties": parties}
    for kind, label in ELECTIONS.items():
        e = [x for x in elections if re.sub(r"\s+", " ", x["name"]).strip().endswith(label)]
        if len(e) != 1:
            raise SystemExit(f"Idaho: the filing portal lists {len(e)} elections named {label!r}")
        rows, n, found, final = [], 1, None, None
        while found is None or len(rows) < found:
            data = post("FiledCandidates/SearchCandidates", {
                "candidateName": None, "electionGuid": e[0]["value"], "districtTypeGuid": fed, "districtNumber": None,
                "countyGuid": None, "officeGuid": None, "district": None, "seat": None, "partyGuid": None,
                "filingStatusGuids": None, "pageNumber": n, "pageSize": 100, "sortBy": None, "sortType": "asc"})
            found, final = data["candidatesFound"], data["isFinalList"]
            got = data.get("candidates") or []
            if not got:
                break
            rows += [{k: c.get(k) for k in KEEP} for c in got]      # the kept columns only; address and voter number never read
            n += 1
        if len(rows) != found:
            raise SystemExit(f"Idaho: the filing portal counts {found} federal candidates for {label}; {len(rows)} were read")
        for r in rows:
            r["candidateName"] = re.sub(r"\s+", " ", r["candidateName"] or "").strip()
            if r["districtType"] != "Federal" or r["officeName"] not in OFFICES:
                raise SystemExit(f"Idaho: a federal row of the {label} list names an office that is not read ({r['officeName']!r})")
        out[kind] = {"election": re.sub(r"\s+", " ", e[0]["name"]).strip(), "date": iso(e[0].get("attribute1")), "final": final,
                     "rows": rows}
        say(f"      Filed Candidates List, {label}: {found} federal candidates{' (marked final)' if final else ''}")
    os.makedirs(folder, exist_ok=True)
    json.dump(out, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return out, path


def race_of(office, district):
    if office == "United States Senator":
        return senate_id("ID", 2)
    if office == "United States Representative" and str(district or "").isdigit():
        return house_id("ID", int(district))
    raise SystemExit(f"Idaho: a row names an office or district that is not read ({office!r}, {district!r})")


def canvass(path, codes):
    """{(race, party code): {"names": [...], "votes": [...], "write_ins", "over", "under", "cast", "counties"}} for every
    congressional party contest, from the Contest Total rows, after the checks in the note above."""
    pdf = PDF(open(path, "rb").read())
    num = lambda s: int(s.replace(",", "")) if re.fullmatch(r"\d{1,3}(?:,\d{3})*", s) else None
    contests, titled = {}, False
    for n, (page, res) in enumerate(pdf.pages(), start=1):
        prow = pdf_rows(pdf, page, res)
        texts = [(y, join(rs), rs) for y, rs in prow]
        titled = titled or any(t == "Primary Election - May 19, 2026" for _y, t, _rs in texts)
        heads = [(y, HEADING.match(t)) for y, t, _rs in texts if HEADING.match(t)]
        if not heads:
            continue
        if len(heads) > 1 or sum(1 for _y, t, _rs in texts if t.startswith("Vote For")) != 1:
            raise SystemExit(f"Idaho: page {n} of the canvass holds more than one contest; the reader expects one a page")
        hy, m = heads[0]
        party = m.group("party")
        if party not in codes:
            raise SystemExit(f"Idaho: the canvass names a party not in the filing portal's key ({party!r})")
        race = house_id("ID", int(m.group("district"))) if m.group("district") else senate_id("ID", 2)
        over = next(((y, rs) for y, t, rs in texts if t.startswith("Over Votes Under Votes")), None)
        vote_for = next((y for y, t, _rs in texts if t.startswith("Vote For")), hy)
        if not over:
            raise SystemExit(f"Idaho: page {n} of the canvass has no Over Votes heading")
        oy, ors = over
        right = {join([r]): r[0] for r in ors}
        if not {"Over Votes", "Under Votes", "Voters", "Total Votes Cast"} <= set(right):
            raise SystemExit(f"Idaho: page {n} of the canvass has headings that are not read ({sorted(right)})")
        cols = []      # candidate columns: name pieces between "Vote For" and the Over Votes line, left of Over Votes
        for y, rs in prow:
            if oy < y < vote_for:
                for r in rs:
                    if r[0] < right["Over Votes"] - 5:
                        c = next((c for c in cols if abs(c[0] - r[0]) < 10), None)
                        (c[1].append(r) if c else cols.append([r[0], [r]]))
        cols.sort(key=lambda c: c[0])
        names = [" ".join(join([r for r in rs if round(r[1]) == y]) for y in sorted({round(r[1]) for r in rs}, reverse=True))
                 for _x, rs in cols]      # a name that wraps is read line by line, top to bottom
        edges = [x for x, _rs in cols] + [right["Over Votes"], right["Under Votes"], right["Voters"] - 11, right["Total Votes Cast"]]
        labels = names + ["over", "under", "registered", "cast"]
        f = contests.setdefault((race, codes[party]), {"party": party, "names": names, "sum": [0] * len(labels), "total": None,
                                                        "counties": 0, "pages": [], "hidden": set()})
        if f["names"] != names:
            raise SystemExit(f"Idaho: the candidates under {m.group(0)} differ from one page of the canvass to the next")
        f["pages"].append(n)
        f["labels"] = labels
        below = [(y, rs) for y, rs in prow if y < oy - 1]
        pcodes = next((rs for y, rs in below if all(join([r]).isupper() and len(join([r])) <= 4 for r in rs)), [])
        if [join([r]) for r in sorted(pcodes)] != [codes[party]] * len(names):
            raise SystemExit(f"Idaho: the party codes under the names on page {n} of the canvass are not all {codes[party]}")
        for y, rs in below:
            first = join([r for r in rs if r[0] < edges[0] - 20])
            if not (first.endswith(" County") or first == "Contest Total"):
                continue
            vals = [None] * len(labels)
            for r in rs:
                if r[0] < edges[0] - 20:
                    continue
                k = min(range(len(edges)), key=lambda i: abs(edges[i] - r[0]))
                cell = r[3].strip()
                if abs(edges[k] - r[0]) > 20 or vals[k] is not None or (num(cell) is None and cell != "**"):
                    raise SystemExit(f"Idaho: a cell on page {n} of the canvass under {m.group(0)} is not read ({first})")
                vals[k] = num(cell) if cell != "**" else PROTECTED
            if None in vals:
                raise SystemExit(f"Idaho: a row on page {n} of the canvass under {m.group(0)} is missing a cell ({first})")
            hidden = {i for i, v in enumerate(vals) if v is PROTECTED}
            if hidden & set(range(len(names))) or (hidden and first == "Contest Total"):
                raise SystemExit(f"Idaho: the canvass protects (**) a count that is needed, under {m.group(0)} ({first})")
            if not hidden and sum(vals[:len(names)]) + vals[-4] + vals[-3] != vals[-1]:
                raise SystemExit(f"Idaho: {first} under {m.group(0)}: candidates, over and under votes do not add up to votes cast")
            if first == "Contest Total":
                f["total"] = vals
            else:
                f["counties"] += 1
                f["hidden"] |= hidden
                f["sum"] = [a + (0 if b is PROTECTED else b) for a, b in zip(f["sum"], vals)]
    if not titled:
        raise SystemExit("Idaho: the file is not the canvass of the May 19, 2026 primary")
    out = {}
    for key, f in contests.items():
        if not f["total"]:
            raise SystemExit(f"Idaho: no Contest Total for {key} in the canvass")
        for i, label in enumerate(f["labels"]):
            if label == "registered":      # a county split between districts counts all its voters under each
                continue
            if f["sum"][i] != f["total"][i] and not (i in f["hidden"] and f["sum"][i] <= f["total"][i]):
                raise SystemExit(f"Idaho: the county rows for {key} do not add up to the canvass's Contest Total ({label})")
        k = len(f["names"])
        writes = [i for i, nm in enumerate(f["names"]) if re.search(r"write", nm, re.I)]
        out[key] = {"names": [nm for i, nm in enumerate(f["names"]) if i not in writes],
                    "votes": [v for i, v in enumerate(f["total"][:k]) if i not in writes],
                    "write_ins": sum(f["total"][i] for i in writes), "over": f["total"][k], "under": f["total"][k + 1],
                    "cast": f["total"][-1], "counties": f["counties"], "party": f["party"], "hidden": bool(f["hidden"])}
    return out


def load(con, cache, say=print):
    net.patient_lookups()
    folder = os.path.join(cache, "id")
    lists, lpath = read_lists(folder, say)
    cpath = os.path.join(folder, "id_2026_primary_canvass.pdf")
    net.download(CANVASS_URL, cpath, max_age_days=30)
    if open(cpath, "rb").read(5) != b"%PDF-":
        raise SystemExit(f"Idaho: {CANVASS_URL} did not return a PDF")
    codes = lists["parties"]
    gen, pri = lists["general"], lists["primary"]

    rows, gone, write_ins, order, nominee = [], [], [], {}, {}
    for r in gen["rows"]:
        race, party, name = race_of(r["officeName"], r["district"]), r["partyName"], r["candidateName"]
        if party not in codes:
            raise SystemExit(f"Idaho: the general list names a party not in the portal's key ({party!r})")
        if codes[party] not in ("IND", "NOP"):
            if (race, codes[party]) in nominee:
                raise SystemExit(f"Idaho: the general list names two {party} candidates for {race}")
            nominee[(race, codes[party])] = (fold(name), r["filingStatusCode"], iso(r["withdrawalDate"]))
        if r["filingStatusCode"] == "W":
            gone.append(f"{name} ({party}, {race}, withdrew {spoken(iso(r['withdrawalDate']))})" if r["withdrawalDate"] else f"{name} ({party}, {race})")
            continue
        if r["filingStatusCode"] != "A":
            raise SystemExit(f"Idaho: a status on the general list that is not read ({r['filingStatus']!r}, {race})")
        if r["isWriteIn"]:
            write_ins.append(name)
            rows.append((race, "general", "2026-11-03", name, party, party_code(party), None, 0, 1, None, None, None, None, None,
                         "id-sos-2026-general-list", WRITE_IN))
            continue
        order[race] = order.get(race, 0) + 1
        rows.append((race, "general", "2026-11-03", name, party, party_code(party), order[race], 0, 0, None, None, None, None, None,
                     "id-sos-2026-general-list", None))

    # who was on each party's primary ballot, from the portal's primary list
    ballot = {}
    for r in pri["rows"]:
        race, code = race_of(r["officeName"], r["district"]), codes.get(r["partyName"])
        if code is None:
            raise SystemExit(f"Idaho: the primary list names a party not in the portal's key ({r['partyName']!r})")
        if code in ("IND", "NOP") or r["filingStatusCode"] == "W":
            continue
        if r["filingStatusCode"] != "A":
            raise SystemExit(f"Idaho: a status on the primary list that is not read ({r['filingStatus']!r}, {race})")
        ballot.setdefault((race, code), set()).add(fold(r["candidateName"]))

    contests = canvass(cpath, codes)
    primary, fields, not_counted, upset, gone_nominees = pri["date"], 0, [], [], []
    for key, f in sorted(contests.items()):
        if {fold(n) for n in f["names"]} != ballot.get(key, set()):
            raise SystemExit(f"Idaho: the canvass's candidates for {key} are not the primary list's")
    not_counted = sorted(k for k in ballot if k not in contests)
    if any(len(ballot[k]) > 1 for k in not_counted):
        raise SystemExit(f"Idaho: a contested party primary on the list has no contest in the canvass ({not_counted})")
    for (race, code), f in sorted(contests.items()):
        if len(f["names"]) < 2:
            continue
        fields += 1
        total = sum(f["votes"]) + f["write_ins"]
        won = nominee.get((race, code))
        top = f["names"][max(range(len(f["votes"])), key=lambda i: f["votes"][i])]
        if not won or won[0] != fold(top):
            upset.append(f"{race} {f['party']}")
        for name, v in sorted(zip(f["names"], f["votes"]), key=lambda nv: -nv[1]):
            advanced = bool(won) and won[0] == fold(name)
            note = None
            if advanced and won[1] == "W":
                note = (f"Won the primary, then withdrew{' on ' + spoken(won[2]) if won[2] else ''}; "
                        "not on the November list.")
                gone_nominees.append(f"{name} ({race}, {f['party']})")
            rows.append((race, f"primary-{code}", primary, name, f["party"], party_code(f["party"]), None, 0, 0, v,
                         round(100 * v / total, 1) if total else None, "advanced" if advanced else "lost", None, None,
                         "id-sos-2026-primary-canvass", note))
    if upset:
        raise SystemExit(f"Idaho: the November list's nominee is not the primary's top vote-getter in {', '.join(upset)}; read the files again")

    general = [r for r in rows if r[1] == "general"]
    missing = [race for (race,) in con.execute("SELECT race_id FROM races WHERE state = 'ID'") if not any(r[0] == race for r in general)]
    if missing:
        raise SystemExit(f"Idaho: no November candidates read for {', '.join(missing)}")
    no_dem = [race for race in sorted({r[0] for r in general}) if not any(r[0] == race and r[5] == "D" for r in general)]
    with con:
        con.execute("DELETE FROM candidates WHERE race_id LIKE '2026-ID-%'")
        con.executemany("INSERT OR REPLACE INTO candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        record_source(con, "id-sos-2026-general-list", path=lpath, level="federal", state="ID", kind="official candidate list",
                      agency="Idaho Secretary of State, Elections Division",
                      title=f"Filed Candidates List, Idaho Candidate Filing Portal: {gen['election']}, Federal offices "
                            "(United States Senator and United States Representative)",
                      url=PAGE, rows=len(gen["rows"]),
                      note=f"Read from the portal's public service ({lists['service']}), the questions the search page asks; "
                           f"{'the Division marks the list final' if gen['final'] else 'the Division has not yet marked the list final'}. "
                           "Ballot name, office, district, party, write-in mark and status only; mailing addresses and voter numbers are "
                           "never read. The list gives no ballot order; its order is kept. Withdrawn, left off: "
                           f"{'; '.join(gone) or 'none'}. Declared write-ins: {len(write_ins)}.")
        record_source(con, "id-sos-2026-primary-list", path=lpath, level="federal", state="ID", kind="official candidate list",
                      agency="Idaho Secretary of State, Elections Division",
                      title=f"Filed Candidates List, Idaho Candidate Filing Portal: {pri['election'].strip()}, Federal offices",
                      url=PAGE, rows=len(pri["rows"]),
                      note="Used to check the canvass: every name under a party's contest is on that party's primary list, and the other "
                           "way round. Independents file in the primary period but are not on a primary ballot. Alone on a party's "
                           "primary list with no contest in the canvass: "
                           + ("; ".join(f"{race} {next(p for p, c in codes.items() if c == code)}" for race, code in not_counted) or "none") + ".")
        record_source(con, "id-sos-2026-primary-canvass", path=cpath, level="federal", state="ID", kind="official results",
                      agency="Idaho Secretary of State, Elections Division",
                      title="Canvass Report, Primary Election - May 19, 2026 (Idaho Detailed Results by Contest)",
                      url=CANVASS_URL, rows=sum(len(f["names"]) for f in contests.values() if len(f["names"]) > 1),
                      note="Votes from each contest's Contest Total row; the county rows add up to it, and each row's candidates, over votes "
                           "and under votes add up to its votes cast. No write-in column is printed for Congress, so a field's total is its "
                           "candidates' votes; over and under votes are left out."
                           + (" Some small counties' over votes are printed ** (\"Protected\") in "
                              + "; ".join(f"{r} {f['party']}" for (r, _c), f in sorted(contests.items()) if f["hidden"])
                              + "; those rows are not added up, and the column's county sum is checked "
                              "only to be no more than the Contest Total." if any(f["hidden"] for f in contests.values()) else "")
                           + (f" Won the primary and later withdrew: {'; '.join(gone_nominees)}." if gone_nominees else ""))
    say(f"    Idaho: 2 House districts and the Senate race, {len(general)} candidates on the November ballot "
        f"({len(gone)} withdrawn left off{', ' + str(len(write_ins)) + ' declared write-in' if write_ins else ''}"
        f"{'; no Democrat in ' + ', '.join(no_dem) if no_dem else ''}); {fields} party primaries with a field, "
        f"votes from the official canvass report")
    return len(general)
