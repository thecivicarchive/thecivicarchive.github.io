"""
Utah: the Lieutenant Governor's Office of Elections. Utah has four House seats, all on the new lines adopted by court
order on November 10, 2025, and no Senate race in 2026.

The November ballot is the Lieutenant Governor's "2026 General Election Certification" (the copy read first is marked
***AMENDED*** and signed September 21, 2026), linked as "Official Certified Candidates" from vote.utah.gov's Current
Election Information page; the page is read each time for the newest link. The certification says the names "shall
appear on the 2026 General Election ballot as written and in the order listed on the attached list", so its order is
the ballot order; that order is also checked against the office's 2026-2027 Master Ballot Position List (the drawn
alphabet applied to surnames) and any difference is printed. Each race is headed "U.S. House of Representatives District
N." and lists Candidate and Party only (no addresses or telephones are printed). Parties are printed in full and kept as
printed: Democratic, Republican, Libertarian, Constitution, Independent American, Forward, and Unaffiliated for a
candidate with no party.

The certification is a signed scan with a machine-read text layer, printed sideways on its candidate pages (the page's
own /Rotate says which way), so rows are read along the right axis and the Party column is found from the "Candidate
Party" heading above each race. Machine reading splits and misreads letters (HOOSL YN, RlLEY), so every name is matched,
letters only, to the office's own typed "2026 Candidate Filings" page (vote.utah.gov/2026-candidate-filings/, Federal
Offices table: Candidate, Office, Party, Status, the only columns it has) in the same district and party, and the typed
spelling is shown; a name that matches nothing stops the loader. The filings page also gives who withdrew or was
disqualified (left off and counted) and who went out at a party convention or in the primary.

Declared write-in candidates are the Lieutenant Governor's "2026 Write-In Certification" (linked as "Write-In
Certification" from the same page, a sideways scan read the same way): under FEDERAL OFFICE, each district heading and
the names that follow. They are stored as write-ins (no party, no ballot position) and must be listed as Write-In on the
filings page.

The June 23 primary: Utah's parties nominate by convention and signatures, and a party primary is held only where two or
more qualify for its ballot. The votes are the Lieutenant Governor's results system's "All Results Excel" workbook
(electionresults.utah.gov, election Primary06232026, its Reports page), "Summary Results" sheet (Office Name, Ballot Name,
Party, Total), with each field's ballots cast, over- and undervotes. Controls: its "Precinct Results" sheet (one row per
county) sums to every total; ballots cast = candidates + over + under; for a multi-county race, every candidate's total,
the contest total and the county columns (matched to the totals by position) of the Lieutenant Governor's signed
"2026 Primary Election Certification", the statewide canvass (vote.utah.gov, the same file as the results system's
"State Of Utah 2026 Primary Election Canvass Report"), must agree; for a single-county race, which the canvass says was
certified at the county level and lists by its nominee only, that nominee must agree, and the figures must match the
county's own final official summary report posted on the same results system. No write-in votes are reported. The
nominee is the party's candidate on the November certification. Names in results are printed in capitals and shown in
ordinary capitals (a sitting member as the congress-legislators roster spells them), as are the certification's.

The primary ballot certification (April 2026) is a scan with no text layer and is not read. Both hosts answer scripts.
"""

import html as H
import json
import os
import re
import sqlite3
import time
import urllib.parse

import openpyxl

from ballot.common import HERE, fold, house_id, name_parts, party_code, record_source
from ballot.lists.tx import proper
from ballot.pdftext import PDF, join, lines, page_runs, rows as pdf_rows
from states import net

INFO_URL = "https://vote.utah.gov/current-election-information/"
FILINGS_URL = "https://vote.utah.gov/2026-candidate-filings/"
MASTER_URL = "https://vote.utah.gov/wp-content/uploads/2026/04/2026-2027-Master-Ballot-Position-List.pdf"
RESULTS_API = "https://electionresults.utah.gov/results/public/api/elections/Utah/Primary06232026"
RESULTS_PAGE = "https://electionresults.utah.gov/results/public/Utah/elections/Primary06232026/reports"
CDN = "https://electionresults.utah.gov/cdn/results/"
PRIMARY = "2026-06-23"
SEATS = 4
FILINGS_HEADS = ["Candidate", "Office", "Party", "Status"]
HEAD = re.compile(r"^U\.S\. House of Representatives District ([0-9lI]{1,2})\.")
OTHER_HEAD = re.compile(r"^[A-Z][A-Za-z.' ]+ District [0-9lI]{1,2}\.")
SECTION = re.compile(r"^(FEDERAL|STATE|COUNTY|JUDICIAL|LOCAL|SCHOOL|MUNICIPAL|MULTI)\b")
MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")
CODES = {"DEM": "Democratic", "REP": "Republican", "LIB": "Libertarian", "CON": "Constitution", "IAP": "Independent American",
         "FWD": "Forward", "GRN": "Green"}
STATS = ("Ballots Cast", "Over Votes", "Under Votes")
CAPS = "Utah's list prints names in capitals; they are shown here in ordinary capitals."
CAPS_RESULTS = "Utah's results print names in capitals; they are shown here in ordinary capitals."
WRITE_IN = "Write-in candidate: the name is not printed on the ballot."


def fresh(path, days):
    return os.path.exists(path) and os.path.getsize(path) > 0 and time.time() - os.path.getmtime(path) < days * 86400


def decode(raw):
    """The pages are UTF-8 with a stray Windows-1252 byte here and there (curly quotes typed into a name)."""
    out, i = [], 0
    while True:
        try:
            out.append(raw[i:].decode("utf-8"))
            return "".join(out)
        except UnicodeDecodeError as e:
            out.append(raw[i:i + e.start].decode("utf-8"))
            out.append(raw[i + e.start:i + e.start + 1].decode("cp1252", "replace"))
            i += e.start + 1


def text(cell):
    t = H.unescape(re.sub(r"<[^>]+>", " ", cell)).replace("\xa0", " ")
    t = t.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
    return re.sub(r"\s+", " ", t).strip()


def letters(name):
    """A name as bare letters, for matching a machine-read scan to the typed list: l and 1 read as I, 0 as O."""
    t = (name or "").replace("l", "I").replace("1", "I").replace("0", "O").upper()
    return re.sub(r"[^A-Z]", "", fold(t).upper())


def links(folder, say):
    """The newest links on the Current Election Information page, kept for two days."""
    path = os.path.join(folder, "ut_2026_links.json")
    if fresh(path, 2):
        return json.load(open(path, encoding="utf-8"))
    page = decode(net.get(INFO_URL, accept="text/html"))
    found = {}
    for href, body in re.findall(r'<a[^>]*href="([^"]+\.pdf)"[^>]*>(.*?)</a>', page, re.S):
        label = text(body)
        name = href.rsplit("/", 1)[-1]
        if "Official Certified Candidates" in label and "General-Election-Certification" in name:
            found.setdefault("general", href)
        elif "Write-In Certification" in label and "2026" in name:
            found.setdefault("write_in", href)
        elif re.fullmatch(r"(?:\W*\s*)?2026 Primary Election Certification", label):
            found.setdefault("canvass", href)
    missing = [k for k in ("general", "write_in", "canvass") if k not in found]
    if missing:
        raise SystemExit(f"Utah: the Current Election Information page no longer links the {', '.join(missing)} file(s)")
    json.dump(found, open(path, "w", encoding="utf-8"), indent=1)
    say(f"      Current Election Information: {', '.join(v.rsplit('/', 1)[-1] for v in found.values())}")
    return found


def filings(folder, say):
    """The Federal Offices table of the 2026 Candidate Filings page: [{name, district, party, status}], and when it was last updated."""
    path = os.path.join(folder, "ut_2026_candidate_filings_federal.json")
    if fresh(path, 2):
        kept = json.load(open(path, encoding="utf-8"))
        return kept["rows"], kept["updated"]
    page = decode(net.get(FILINGS_URL, accept="text/html"))
    m = re.search(r"Last updated:\s*(\d{1,2})/(\d{1,2})/(\d{4})", page)
    updated = f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}" if m else ""
    at = re.search(r"<h\d[^>]*>\s*Federal Offices\s*</h\d>", page)
    table = re.search(r"<table.*?</table>", page[at.end():], re.S) if at else None
    if not table:
        raise SystemExit("Utah: the 2026 Candidate Filings page no longer has its Federal Offices table")
    trs = re.findall(r"<tr[^>]*>(.*?)</tr>", table.group(0), re.S)
    heads = [text(h) for h in re.findall(r"<th[^>]*>(.*?)</th>", trs[0], re.S)]
    if heads != FILINGS_HEADS:
        raise SystemExit(f"Utah: the Federal Offices table's columns changed ({heads})")
    out = []
    for tr in trs[1:]:
        cells = [text(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        if len(cells) != len(heads):
            raise SystemExit("Utah: a Federal Offices row does not line up with its headings")
        rec = dict(zip(heads, cells))
        m = re.fullmatch(r"U\.S\. House District (\d+)", rec["Office"])
        if not m:
            raise SystemExit(f"Utah: a federal office on the filings page that is not read ({rec['Office']!r})")
        out.append({"name": rec["Candidate"], "district": int(m.group(1)), "party": rec["Party"], "status": rec["Status"]})
    json.dump({"url": FILINGS_URL, "updated": updated, "rows": out}, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    say(f"      2026 Candidate Filings (updated {updated}): {len(out)} rows for Congress")
    return out, updated


def scan_rows(path):
    """Every printed row of a scan's text layer, in reading order: [(page, [(position along the row, text)])]. The page's
    /Rotate says which axis the rows run along; machine-read words carry their own trailing spaces."""
    pdf = PDF(open(path, "rb").read())
    out = []
    for n, (page, res) in enumerate(pdf.pages(), start=1):
        rot = int(page.get("Rotate") or 0) % 360
        key, pos = {0: (lambda r: -r[1], lambda r: r[0]), 90: (lambda r: r[0], lambda r: r[1]),
                    180: (lambda r: r[1], lambda r: -r[0]), 270: (lambda r: -r[0], lambda r: -r[1])}[rot]
        grouped = []
        for r in sorted(page_runs(pdf, page, res), key=key):
            if grouped and abs(grouped[-1][0] - key(r)) <= 3:
                grouped[-1][1].append(r)
            else:
                grouped.append([key(r), [r]])
        for _k, rs in grouped:
            out.append((n, sorted((pos(r), r[3]) for r in rs)))
    return out


def words(cells):
    return re.sub(r"\s+", " ", "".join(t for _p, t in cells)).strip()


def district_of(m):
    return int(m.group(1).replace("l", "1").replace("I", "1"))


def general_list(path):
    """([(race, name as read, party)] in the certification's order, the date it was signed, whether it is amended)."""
    out, race, edge, signed, amended, day = [], None, None, "", False, None
    for page, cells in scan_rows(path):
        t = words(cells)
        if page == 1:
            amended = amended or "AMENDED" in t
            m = re.search(r"this (\d{1,2})(?:st|nd|rd|th)\b", t)
            day = int(m.group(1)) if m else day
            m = re.search(r"day of ([A-Z][a-z]+), (\d{4})", t)
            if m and m.group(1) in MONTHS and day:
                signed = f"{m.group(2)}-{MONTHS.index(m.group(1)) + 1:02d}-{day:02d}"
            continue
        m = HEAD.match(t)
        if m:
            race, edge = house_id("UT", district_of(m)), None
            continue
        if OTHER_HEAD.match(t) or SECTION.match(t):
            race, edge = None, None
            continue
        if race and edge is None and t.startswith("Candidate") and "Party" in t:
            edge = next(p for p, w in cells if w.strip() == "Party") - 15
            continue
        if race and edge is not None:
            name = words([c for c in cells if c[0] < edge])
            party = words([c for c in cells if c[0] >= edge])
            if name and party:
                out.append((race, name, party))
            elif name or party:
                raise SystemExit(f"Utah: a row under {race} on the certification has a name or a party but not both ({party or 'no party'})")
    return out, signed, amended


def write_in_list(path):
    """[(race, name as read)] from the FEDERAL OFFICE part of the Write-In Certification, and the date it was signed."""
    out, race, federal, day, signed = [], None, False, None, ""
    for page, cells in scan_rows(path):
        t = words(cells)
        if page == 1:      # "... this 10th / day of September, 2026." (machine reading drops letters: "da eptember,")
            m = re.search(r"\bthis (\d{1,2})(?:st|nd|rd|th)\b", t)
            day = day or (int(m.group(1)) if m else None)
            m = re.search(r"(ugust|eptember|ctober),? (\d{4})", t)
            if m and day and not signed:
                signed = f"{m.group(2)}-{ {'ugust': 8, 'eptember': 9, 'ctober': 10}[m.group(1)]:02d}-{day:02d}"
        if SECTION.match(t):
            federal, race = t.startswith("FEDERAL"), None
            continue
        m = HEAD.match(t)
        if m:
            race = house_id("UT", district_of(m)) if federal else None
            continue
        if OTHER_HEAD.match(t):
            race = None
            continue
        if race and re.search(r"[a-z]", t) is None and re.search(r"[A-Z]", t):
            out.append((race, t))
    return out, signed


def master_alphabet(path):
    letters_ = {}
    for _page, _y, t in lines(path):
        m = re.fullmatch(r"(\d{1,2})\. ([A-Z])", t)
        if m:
            letters_[int(m.group(1))] = m.group(2)
    if sorted(letters_) != list(range(1, 27)) or len(set(letters_.values())) != 26:
        raise SystemExit("Utah: the Master Ballot Position List's drawn alphabet was not read whole")
    return [letters_[k] for k in range(1, 27)]


def results_links(folder, say):
    """The All Results workbook and each county's summary report on the results system, kept for thirty days."""
    path = os.path.join(folder, "ut_2026_primary_results_links.json")
    if fresh(path, 30):
        return json.load(open(path, encoding="utf-8"))
    j = json.loads(net.get(RESULTS_API, accept="application/json"))
    if j.get("electionDate") != PRIMARY:
        raise SystemExit(f"Utah: the results system's election Primary06232026 is dated {j.get('electionDate')}")
    base = CDN + j["jurisdictionId"] + "/"
    found = {"all_results": None, "canvass": None, "counties": {}, "last_updated": j.get("lastUpdated", "")[:10]}
    for cat in j.get("publicReportCategories") or []:
        for r in cat.get("reports") or []:
            url = base + urllib.parse.quote(r["blobName"])
            name = re.sub(r"\s+", " ", r["reportName"]).strip()
            if name == "All Results Excel":
                found["all_results"] = url
            elif name.startswith("State Of Utah") and "Canvass" in name:
                found["canvass"] = url
            elif cat.get("categoryName") == "Summary Results":
                m = re.match(r"(.+? County) Summary Results", name)
                if m:
                    found["counties"][m.group(1)] = url
    if not found["all_results"]:
        raise SystemExit("Utah: the results system no longer lists its All Results Excel workbook")
    json.dump(found, open(path, "w", encoding="utf-8"), indent=1)
    say(f"      results system: All Results workbook and {len(found['counties'])} county summaries listed")
    return found


def primary_book(path):
    """{(district, party code): {"names": {name: votes}, "cast", "over", "under", "write_ins", "counties": {county: {name: votes}}}}."""
    if open(path, "rb").read(2) != b"PK":
        raise SystemExit("Utah: the All Results workbook is not a workbook")
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)

    def sheet(title, need):
        it = wb[title].iter_rows(values_only=True)
        heads = [str(c or "").strip() for c in next(it)]
        if not all(k in heads for k in need):
            raise SystemExit(f"Utah: the All Results workbook's {title} columns changed ({[h for h in heads if h]})")
        idx = {k: heads.index(k) for k in need}
        for r in it:
            yield {k: r[i] for k, i in idx.items()}

    def race_of(office):
        m = re.fullmatch(r"([A-Z]{3}) U\.S\. House District (\d+)", re.sub(r"\s+", " ", str(office or "")).strip())
        return (int(m.group(2)), m.group(1)) if m else None

    out = {}
    for r in sheet("Summary Results", ("Office Name", "Ballot Name", "Party", "Total")):
        key = race_of(r["Office Name"])
        if not key:
            if "U.S." in str(r["Office Name"] or ""):
                raise SystemExit(f"Utah: a federal contest in the results that is not read ({r['Office Name']!r})")
            continue
        f = out.setdefault(key, {"names": {}, "cast": None, "over": 0, "under": 0, "write_ins": 0, "counties": {}})
        name, votes = re.sub(r"\s+", " ", str(r["Ballot Name"] or "")).strip(), int(r["Total"] or 0)
        if name == "Ballots Cast":
            f["cast"] = votes
        elif name in ("Over Votes", "Under Votes"):
            f[name.split()[0].lower()] = votes
        elif "write" in name.lower():
            f["write_ins"] += votes
        else:
            if r["Party"] and CODES.get(key[1]) != str(r["Party"]).strip():
                raise SystemExit(f"Utah: {name} is listed as {r['Party']} in the {key[1]} primary")
            f["names"][name] = votes
    for r in sheet("Precinct Results", ("Precinct", "Office Name", "Ballot Name", "Total")):
        key = race_of(r["Office Name"])
        if key in out:
            county = str(r["Precinct"]).strip()
            cell = out[key]["counties"].setdefault(county, {})
            name = re.sub(r"\s+", " ", str(r["Ballot Name"] or "")).strip()
            cell[name] = cell.get(name, 0) + int(r["Total"] or 0)
    wb.close()
    return out


def cells(runs):
    """A printed row's pieces grouped into cells: [(x, x_end, text)]; a gap wider than six points starts the next cell."""
    out = []
    for r in sorted(runs, key=lambda r: r[0]):
        if out and r[0] - out[-1][2] <= 6:
            out[-1][1].append(r)
            out[-1][2] = max(out[-1][2], r[4])
        else:
            out.append([r[0], [r], r[4]])
    return [(x, end, join(rs)) for x, rs, end in out]


def number(t):
    return int(t.replace(",", "")) if re.fullmatch(r"\d{1,3}(?:,\d{3})*", t) else None


def canvass(path, counts):
    """From the statewide canvass: {(district, party): {"names", "votes", "county_sums", "total"}} for the multi-county
    House primaries, and {district: (party, nominee)} for the single-county ones it lists by nominee only. A page's
    candidates run across the page in its races' order; counts gives each race's number of candidates (from the
    workbook), and the names must then agree."""
    pdf = PDF(open(path, "rb").read())
    multi, single = {}, {}
    for _n, (page, res) in enumerate(pdf.pages(), start=1):
        heads, parties, names, per, contest, counties, want, single_page = [], [], [], [], [], [], None, False
        for _y, runs in pdf_rows(pdf, page, res):
            row = cells(runs)
            texts = [c[2] for c in row]
            if "Single-County Races" in " ".join(texts):
                single_page = True
            if single_page:
                m = re.fullmatch(r"U\.S\. House District (\d+)", texts[0]) if texts else None
                if m and len(texts) == 3:
                    single[int(m.group(1))] = (texts[1], texts[2])
                continue
            hs = [(c[0], int(re.fullmatch(r"U\.S\. House District (\d+)", c[2]).group(1))) for c in row
                  if re.fullmatch(r"U\.S\. House District (\d+)", c[2])]
            if hs:
                heads = sorted(hs)
                continue
            if not heads:
                continue
            nums = [number(c[2]) for c in row]
            if not parties and texts and all(t in CODES.values() for t in texts):
                parties = texts
            elif texts and texts[0].startswith("Total Votes Cast Per"):
                want = "per"
            elif texts and texts[0].startswith("Total Votes Cast in"):
                want = "contest"
            elif texts and texts[0].endswith("County"):
                counties.append([(c[1], number(c[2])) for c in row[1:] if number(c[2]) is not None])
            elif row and all(n is not None for n in nums) and want:
                if want == "per":
                    per = [(c[1], n) for c, n in zip(row, nums)]
                else:
                    contest = nums
                want = None
            elif parties and not names and row and all(t == t.upper() and re.search(r"[A-Z]", t) for t in texts):
                names = texts
        if not heads:
            continue
        if not (len(parties) == len(heads) == len(contest) and names and len(names) == len(per)):
            raise SystemExit("Utah: a U.S. House page of the statewide canvass was not read whole")
        sums = [0] * len(per)
        for row in counties:
            for end, n in row:
                k = min(range(len(per)), key=lambda i: abs(per[i][0] - end))
                if abs(per[k][0] - end) > 12:
                    raise SystemExit("Utah: a county figure on the statewide canvass lines up with no candidate's column")
                sums[k] += n
        at = 0
        for (_x, district), party, total in zip(heads, parties, contest):
            n = counts.get((district, party), 0)
            span = range(at, at + n)
            at += n
            multi[(district, party)] = {"names": [names[i] for i in span if i < len(names)], "votes": [per[i][1] for i in span if i < len(per)],
                                        "county_sums": [sums[i] for i in span if i < len(sums)], "total": total}
        if at != len(names):
            raise SystemExit("Utah: the statewide canvass's candidates do not add up to the workbook's races on its U.S. House page")
    return multi, single


def county_summary(path, district, party):
    """{name: votes} for one House primary from a county's final official summary report."""
    out, on = {}, False
    for _page, _y, t in lines(path):
        m = re.match(r"U\.S\. HOUSE DISTRICT (\d+) \((\w+)\)", t)
        if m:
            on = int(m.group(1)) == district and m.group(2) == party
            continue
        if on:
            if t.startswith("Total Votes"):
                break
            m = re.fullmatch(r"(.+?) ([\d,]+) [\d.]+%", t)
            if m and not t.startswith("Times Cast"):
                out[m.group(1).strip()] = int(m.group(2).replace(",", ""))
    return out


def load(con, cache, say=print):
    net.patient_lookups()
    folder = os.path.join(cache, "ut")
    os.makedirs(folder, exist_ok=True)
    found = links(folder, say)
    gpath = os.path.join(folder, "ut_" + found["general"].rsplit("/", 1)[-1].lower())
    wpath = os.path.join(folder, "ut_" + found["write_in"].rsplit("/", 1)[-1].lower())
    cpath = os.path.join(folder, "ut_2026_primary_state_canvass.pdf")
    mpath = os.path.join(folder, "ut_2026_2027_master_ballot_position_list.pdf")
    net.download(found["general"], gpath, max_age_days=2)
    net.download(found["write_in"], wpath, max_age_days=2)
    net.download(found["canvass"], cpath, max_age_days=30)
    net.download(MASTER_URL, mpath, max_age_days=30)
    for p in (gpath, wpath, cpath, mpath):
        if open(p, "rb").read(4) != b"%PDF":
            raise SystemExit(f"Utah: {os.path.basename(p)} is not a PDF")
    filed, updated = filings(folder, say)

    rec = sqlite3.connect(f"file:{os.path.join(HERE, 'congress_119.sqlite')}?mode=ro", uri=True)
    fixed = {}
    for full, first, last in rec.execute("SELECT official_full, first_name, last_name FROM legislators WHERE is_current = 1 AND state = 'UT'"):
        for form in (full, f"{first} {last}"):
            if form:
                fixed[form.upper()] = full or form

    def shown(caps):
        caps = re.sub(r"\s+", " ", caps.strip())
        if caps in fixed:
            return fixed[caps]
        return re.sub(r"(['\"(])([a-z])", lambda m: m.group(1) + m.group(2).upper(), proper(caps))

    def code_of(party):
        return "O" if party == "Independent American" else party_code(party)   # a party of its own, not an independent

    def typed(race, read, party, statuses):
        """The filings page's own spelling of a name read from a scan: same district, same party, same letters."""
        district = int(race[-2:])
        hits = [r for r in filed if r["district"] == district and r["party"] == party and r["status"] in statuses
                and letters(r["name"]) == letters(read)]
        if len(hits) != 1:
            raise SystemExit(f"Utah: the name read from the certification under {race} ({party or 'write-in'}) matches "
                             f"{len(hits)} names on the filings page; read the scan again")
        return hits[0]["name"]

    listed, signed, amended = general_list(gpath)
    races = sorted({r for r, _n, _p in listed})
    want = [house_id("UT", d) for d in range(1, SEATS + 1)]
    if races != want:
        raise SystemExit(f"Utah: the certification's U.S. House races are {races}, not districts 1 to {SEATS}")
    rows, order, nominee = [], {}, {}
    for race, read, party in listed:
        name = typed(race, read, party, ("Election Candidate",))
        order[race] = order.get(race, 0) + 1
        rows.append((race, "general", "2026-11-03", shown(name), party, code_of(party), order[race], 0, 0, None, None, None, None,
                     None, "ut-ltg-2026-general-certification", CAPS))
        nominee[(race, party)] = fold(name)
    on_list = {(r[0], fold(r[3])) for r in rows}
    unlisted = [f"{r['name']} (District {r['district']})" for r in filed if r["status"] == "Election Candidate"
                and (house_id("UT", r["district"]), fold(shown(r["name"]))) not in on_list]
    if unlisted:
        say("    Utah: on the filings page as election candidates but not on the certification: " + "; ".join(unlisted))

    alphabet = master_alphabet(mpath)
    rank = {c: i for i, c in enumerate(alphabet)}
    misordered = []
    for race in want:
        names = [r[3] for r in rows if r[0] == race]
        drawn = sorted(names, key=lambda n: ([rank.get(c, 99) for c in name_parts(n)[1].replace(" ", "").upper()], name_parts(n)[0]))
        if drawn != names:
            misordered.append(race)
    if misordered:
        say("    Utah: the certification's order differs from the Master Ballot Position List's in " + ", ".join(misordered)
            + " (a legal surname may differ from the ballot name); the certification's order is kept")

    write_ins, wsigned = write_in_list(wpath)
    for race, read in write_ins:
        name = typed(race, read, "", ("Write-In",))
        rows.append((race, "general", "2026-11-03", shown(name), None, party_code("write-in"), None, 0, 1, None, None, None, None,
                     None, "ut-ltg-2026-write-in-certification", f"{WRITE_IN} {CAPS}"))
    declared = [r for r in filed if r["status"] == "Write-In"]
    if len(declared) != len(write_ins):
        say(f"    Utah: the filings page lists {len(declared)} federal write-in(s); the Write-In Certification lists {len(write_ins)}")
    gone = [f"{shown(r['name'])}, District {r['district']} ({r['status'].lower()})" for r in filed
            if re.search(r"withdr|disqual|remov|deceas", r["status"], re.I)]
    known = {"Election Candidate", "Out in Convention", "Out in Primary", "Write-In"}
    odd = sorted({r["status"] for r in filed if r["status"] not in known and not re.search(r"withdr|disqual|remov|deceas", r["status"], re.I)})
    if odd:
        raise SystemExit(f"Utah: a status on the filings page that is not read ({odd})")
    convention = sum(1 for r in filed if r["status"] == "Out in Convention")

    # the June 23 primary
    rl = results_links(folder, say)
    bpath = os.path.join(folder, "ut_2026_primary_all_results.xlsx")
    net.download(rl["all_results"], bpath, max_age_days=30)
    book = primary_book(bpath)
    multi, single = canvass(cpath, {(d, CODES.get(c)): len(f["names"]) for (d, c), f in book.items()})
    problems, checked, county_files = [], [], []
    fields = 0
    for (district, code), f in sorted(book.items()):
        race, party = house_id("UT", district), CODES.get(code)
        if not party:
            raise SystemExit(f"Utah: a party code in the primary results that is not read ({code})")
        counted = sum(f["names"].values()) + f["write_ins"]
        if f["cast"] is not None and counted + f["over"] + f["under"] != f["cast"]:
            problems.append(f"{race} {code}: candidates, over- and undervotes {counted + f['over'] + f['under']:,} against {f['cast']:,} ballots cast")
        for name, votes in f["names"].items():
            summed = sum(c.get(name, 0) for c in f["counties"].values())
            if summed != votes:
                problems.append(f"{race} {code}: {name}'s county rows sum to {summed:,}, the total is {votes:,}")
        if (district, party) in multi:
            c = multi[(district, party)]
            theirs = {fold(n): (v, cs) for n, v, cs in zip(c["names"], c["votes"], c["county_sums"])}
            ours = {fold(n): v for n, v in f["names"].items()}
            if set(theirs) != set(ours) or any(theirs[n][0] != v or theirs[n][1] != v for n, v in ours.items()) \
                    or c["total"] != sum(f["names"].values()):
                problems.append(f"{race} {code}: the statewide canvass does not agree with the workbook")
            else:
                checked.append(f"{race} {code} (statewide canvass: totals and county columns)")
        elif district in single:
            cparty, cname = single[district]
            top = max(f["names"], key=f["names"].get)
            if cparty != party or fold(cname) != fold(top):
                problems.append(f"{race} {code}: the canvass names {cname} ({cparty}) as the nominee; the workbook's leader is {top}")
            counties = sorted(f["counties"])
            url = rl["counties"].get(counties[0]) if len(counties) == 1 else None
            if not url:
                problems.append(f"{race} {code}: no county summary report found to check this single-county race against")
            else:
                spath = os.path.join(folder, f"ut_2026_primary_{fold(counties[0]).replace(' ', '_')}_summary.pdf")
                net.download(url, spath, max_age_days=30)
                theirs = county_summary(spath, district, code)
                if {fold(n): v for n, v in theirs.items()} != {fold(n): v for n, v in f["names"].items()}:
                    problems.append(f"{race} {code}: {counties[0]}'s final official summary does not agree with the workbook")
                else:
                    checked.append(f"{race} {code} ({counties[0]}'s final official summary)")
                    county_files.append((counties[0], spath, url, race, code))
        else:
            problems.append(f"{race} {code}: the statewide canvass neither lists nor names this primary")
        out_in_primary = {fold(r["name"]) for r in filed if r["district"] == district and r["party"] == party and r["status"] == "Out in Primary"}
        if {fold(n) for n in f["names"]} != out_in_primary | {nominee.get((race, party), "")}:
            problems.append(f"{race} {code}: the primary's candidates are not the filings page's nominee and those out in the primary")
        if len(f["names"]) < 2:
            continue
        fields += 1
        top = max(f["names"], key=f["names"].get)
        winner = nominee.get((race, party), fold(top))
        if winner != fold(top):
            problems.append(f"{race} {code}: the November nominee is not the primary's leader ({top})")
        for name, votes in sorted(f["names"].items(), key=lambda kv: (-kv[1], kv[0])):
            won = winner == fold(name)
            note = CAPS_RESULTS
            if won and (race, party) not in nominee:
                note += f" Won the primary but is not on the November list; the certification lists no {party} candidate in this race."
            rows.append((race, f"primary-{code}", PRIMARY, shown(name), party, code_of(party), None, 0, 0, votes,
                         round(100 * votes / counted, 1) if counted else None, "advanced" if won else "lost", None, None,
                         "ut-ltg-2026-primary-results", note))
    if problems:
        say("    Utah: primary figures that do not reconcile: " + "; ".join(problems))

    general = [r for r in rows if r[1] == "general"]
    n_write = sum(1 for r in general if r[8])
    with con:
        con.execute("DELETE FROM candidates WHERE race_id LIKE '2026-UT-%'")
        con.executemany("INSERT OR REPLACE INTO candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        record_source(con, "ut-ltg-2026-general-certification", path=gpath, level="federal", state="UT", kind="official candidate list",
                      agency="Utah Office of the Lieutenant Governor, Office of Elections",
                      title=("***AMENDED*** " if amended else "") + "2026 General Election Certification"
                            + (f" (signed {signed})" if signed else "") + ": U.S. House of Representatives, Districts 1 to 4",
                      url=found["general"], published=signed, rows=len(listed),
                      note="A signed scan read through its machine-read text layer (candidate and party only; the certification prints nothing "
                           "else); every name matched letter for letter to the office's typed Candidate Filings page, whose spelling is shown. "
                           "The certification's order is the ballot order, as it says"
                           + ("; it agrees with the Master Ballot Position List. " if not misordered else
                              f"; it differs from the Master Ballot Position List in {', '.join(misordered)}. ")
                           + f"Withdrawn or disqualified, left off: {len(gone)} ({'; '.join(gone) or 'none'}). "
                           f"Out at a party convention, not on any ballot: {convention}.")
        record_source(con, "ut-ltg-2026-write-in-certification", path=wpath, level="federal", state="UT", kind="official candidate list",
                      agency="Utah Office of the Lieutenant Governor, Office of Elections",
                      title="2026 Write-In Candidate Certification" + (f" (signed {wsigned})" if wsigned else "") + ": Federal Office",
                      url=found["write_in"], published=wsigned, rows=len(write_ins),
                      note="Declared write-in candidates for the November 3, 2026 general election (Utah Code 20A-9-601(5)); their names are not "
                           "printed on the ballot. A signed scan read through its text layer; each name matched to a Write-In row of the filings page.")
        record_source(con, "ut-ltg-2026-candidate-filings", path=os.path.join(folder, "ut_2026_candidate_filings_federal.json"),
                      level="federal", state="UT", kind="official candidate list",
                      agency="Utah Office of the Lieutenant Governor, Office of Elections",
                      title="2026 Candidate Filings: Federal Offices" + (f" (last updated {updated})" if updated else ""),
                      url=FILINGS_URL, published=updated, rows=len(filed),
                      note="Its four columns (Candidate, Office, Party, Status) only; used for the typed spelling of each certified name, for who "
                           "withdrew or was disqualified, and to check the primaries (Out in Primary).")
        record_source(con, "ut-ltg-2026-master-ballot-position-list", path=mpath, level="federal", state="UT", kind="official procedure",
                      agency="Utah Office of the Lieutenant Governor", title="2026 - 2027 Master Ballot Position List (drawn April 6, 2026)",
                      url=MASTER_URL, rows=26, note="The drawn alphabet (Utah Code 20A-6-110), used only to check the certification's order.")
        record_source(con, "ut-ltg-2026-primary-results", path=bpath, level="federal", state="UT", kind="official results",
                      agency="Utah Office of the Lieutenant Governor, Office of Elections (election results system)",
                      title="2026 Utah Primary Election (June 23, 2026): All Results Excel", url=RESULTS_PAGE,
                      published=rl.get("last_updated", ""), rows=sum(len(f["names"]) for f in book.values() if len(f["names"]) > 1),
                      note="Summary Results sheet; every total equals the sum of the Precinct Results sheet's county rows, and candidates plus over- "
                           "and undervotes equal ballots cast. No write-in votes are reported. Checked: " + ("; ".join(checked) or "none") + "."
                           + (" Did not reconcile: " + "; ".join(problems) + "." if problems else ""))
        record_source(con, "ut-ltg-2026-primary-canvass", path=cpath, level="federal", state="UT", kind="official results",
                      agency="Utah Office of the Lieutenant Governor, Office of Elections",
                      title="2026 Primary Election Certification: June 23, 2026 Primary Election Statewide Canvass", url=found["canvass"],
                      rows=len(multi) + len(single),
                      note="The signed statewide canvass (the same file as the results system's State Of Utah 2026 Primary Election Canvass Report). "
                           "Multi-county races: candidate totals, contest totals and county columns checked against the workbook. Single-county "
                           "races are certified by the county and listed by nominee only.")
        for county, spath, url, race, code in county_files:
            record_source(con, f"ut-{fold(county).replace(' ', '-')}-2026-primary-summary", path=spath, level="federal", state="UT",
                          kind="official results", agency=f"{county} Clerk (posted on the Lieutenant Governor's election results system)",
                          title=f"2026 Primary Election: Final Official Election Results summary ({county})", url=url, rows=0,
                          note=f"A control only: the {race} {code} primary lies wholly in {county}, whose board of canvassers certified it; "
                               "its figures match the workbook's.")
    say(f"    Utah: {SEATS} House districts on the new lines, {len(general)} candidates on the November ballot "
        f"({n_write} declared write-in, {len(gone)} withdrawn or disqualified left off); {fields} party primaries with a field, "
        f"votes from the official results, checked against the statewide canvass and the county's final summary")
    return len(general)
