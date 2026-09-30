"""
Missouri: the Secretary of State's Certification of Candidates and Party Emblems for the General Election on Tuesday,
November 3, 2026 (a PDF certified to the election authorities on August 25, 2026, linked as "Certified Candidates -
November 2026" from sos.mo.gov/elections), read with ballot/pdftext.py, and the Secretary's Certified Candidate List
for the 2026 Primary Election (s1.sos.mo.gov/CandidatesOnWeb, election 750006905) with its Withdrawn/Removed Candidates
page. Missouri has eight House seats and no Senate race in 2026.

The certification goes party by party ("REPUBLICAN CANDIDATES", "DEMOCRATIC CANDIDATES", "LIBERTARIAN CANDIDATES",
"INDEPENDENT CANDIDATES"), office by office ("For U.S. Representative"), one line per candidate ("District 5, Rick
Brattin"). The parties' headings are printed in capitals and written here as Republican, Democratic, Libertarian and
Independent; names are printed in ordinary capitals and kept as printed. The certification prints no order numbers, so
a race's ballot order is the certification's own order: the parties in the order it lists them. It lists no write-in
candidates. A party may nominate one candidate per seat; two under one party would stop the loader.

The primary list gives, under each office ("U.S. REPRESENTATIVE - DISTRICT 1"), one table per party (its caption) of
the candidates in ballot order, with Name, Mailing Address, Random Number and Date Filed; only Name is read, and the page
itself is not kept (the cache holds the kept columns as JSON). The removed page's Candidate cell runs the name, the
party in brackets and the mailing address together; only the name and party before the bracket are kept. A party's
primary field is its candidates for a seat when there are two or more; the one on the November certification for that
party advanced. The August 4 primary used the 2025 map; the 2025 map was then paused pending this November's referendum,
so each nominee runs in the seat with the same number under the 2022 lines (see the state note), and the fields are
filed under those numbers.

The primary's vote counts are not loaded: the Secretary's results page still offers only the Election Night Reporting
site (enr.sos.mo.gov, "Unofficial Results"), which answers scripts with a Cloudflare challenge, and no official Grand
Totals file for August 4, 2026 is posted yet (the 2024 one is 2024PrimaryElection.pdf on the same page).
"""

import html as H
import json
import os
import re
import time

from ballot.common import fold, house_id, party_code, record_source
from ballot.pdftext import lines
from states import net

GENERAL_URL = "https://www.sos.mo.gov/CMSImages/ElectionCandidates/2026GeneralElectionCertifiedCandidates.pdf"
PRIMARY_CODE = "750006905"
PRIMARY_URL = f"https://s1.sos.mo.gov/CandidatesOnWeb/DisplayCandidatesPlacement.aspx?ElectionCode={PRIMARY_CODE}"
REMOVED_URL = f"https://s1.sos.mo.gov/CandidatesOnWeb/CandidatesRemoved.aspx?ElectionCode={PRIMARY_CODE}"
RESULTS_PAGE = "https://www.sos.mo.gov/elections/results"
PRIMARY = "2026-08-04"
PARTY = {"REPUBLICAN": "Republican", "DEMOCRATIC": "Democratic", "LIBERTARIAN": "Libertarian", "INDEPENDENT": "Independent",
         "GREEN": "Green", "CONSTITUTION": "Constitution"}
CODE = {"Republican": "REP", "Democratic": "DEM", "Libertarian": "LIB", "Green": "GRE", "Constitution": "CON"}
MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
OFFICE = re.compile(r"U\.S\. REPRESENTATIVE - DISTRICT (\d+)")


def text_of(cell):
    return re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", cell))).strip()


def decode(raw):
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp1252", "replace")


def general_list(path):
    """[(district, party, name)] in the certification's order, and the date it was certified."""
    out, party, office, published = [], None, None, ""
    for page, _y, text in lines(path):
        m = re.fullmatch(rf"({MONTHS}) (\d{{1,2}}), (2026)", text)
        if m and not published and page < 6:
            published = f"{m.group(3)}-{MONTHS.split('|').index(m.group(1)) + 1:02d}-{int(m.group(2)):02d}"
            continue
        m = re.fullmatch(r"([A-Z ]+) CANDIDATES", text)
        if m:
            word = m.group(1).strip()
            party = None if word == "JUDICIAL" else PARTY.get(word, word.title())
            office = None
            continue
        if text in ("CERTIFICATION", "COUNTY CLERK/ELECTION AUTHORITY CERTIFICATION", "NOTICE OF ELECTION"):
            party = office = None
            continue
        if text.startswith("For "):
            if re.match(r"For (U\.S\.|United States) Senator", text):
                raise SystemExit("Missouri: the certification names a candidate for the U.S. Senate, and there is no Senate race this year; read it again")
            office = "H" if text == "For U.S. Representative" else None
            continue
        if office == "H" and party:
            m = re.fullmatch(r"District (\d+), (.+)", text)
            if not m:
                raise SystemExit(f"Missouri: a line under U.S. Representative ({party}) is not \"District N, Name\"; read the certification again")
            out.append((int(m.group(1)), party, m.group(2).strip()))
    return out, published


def primary_list(page):
    """[{district, party, name}] for every candidate for Congress on the certified primary list, in its order."""
    if "2026 Primary Election" not in page or "Certified Candidate List" not in page:
        raise SystemExit("Missouri: the CandidatesOnWeb page is no longer the Certified Candidate List for the 2026 Primary Election")
    page = re.sub(r"<script.*?</script>|<style.*?</style>", "", page, flags=re.S)
    parts = re.split(r"<h3[^>]*>(.*?)</h3>", page, flags=re.S)
    out = []
    for k in range(1, len(parts), 2):
        head = text_of(parts[k])
        if head.upper().startswith("U.S. SENATOR"):
            raise SystemExit("Missouri: the primary list names candidates for the U.S. Senate; read it again")
        m = OFFICE.fullmatch(head.upper())
        if not m:
            continue
        for tab in re.findall(r"<table[^>]*>(.*?)</table>", parts[k + 1], re.S):
            cap = re.search(r"<caption[^>]*>(.*?)</caption>", tab, re.S)
            heads = [text_of(h) for h in re.findall(r"<th[^>]*>(.*?)</th>", tab, re.S)]
            if not cap or "Name" not in heads:
                raise SystemExit(f"Missouri: a table under {head} has no party caption or no Name column ({heads})")
            col = heads.index("Name")
            for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", tab, re.S):
                cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
                if not cells:
                    continue
                if len(cells) != len(heads):
                    raise SystemExit(f"Missouri: a row under {head} does not line up with its headings")
                name = text_of(cells[col])
                if name:
                    out.append({"district": int(m.group(1)), "party": text_of(cap.group(1)), "name": name})
    return out


def removed_list(page):
    """[{office, name, party, reason, date}] for candidates for Congress taken off the primary ballot; the Candidate cell
    also carries the mailing address, and only what comes before the party's bracket is kept."""
    page = re.sub(r"<script.*?</script>|<style.*?</style>", "", page, flags=re.S)
    out = []
    for tab in re.findall(r"<table[^>]*>(.*?)</table>", page, re.S):
        heads = [text_of(h) for h in re.findall(r"<th[^>]*>(.*?)</th>", tab, re.S)]
        if not all(k in heads for k in ("Office", "Candidate", "Reason", "Removal Date")):
            continue
        idx = {k: heads.index(k) for k in ("Office", "Candidate", "Reason", "Removal Date")}
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", tab, re.S):
            cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
            if len(cells) != len(heads):
                continue
            office = text_of(cells[idx["Office"]])
            if not (OFFICE.fullmatch(office.upper()) or office.upper().startswith("U.S. SENATOR")):
                continue
            who = re.match(r"(.+?) \(([A-Za-z ]+)\)", text_of(cells[idx["Candidate"]]))
            out.append({"office": office, "name": who.group(1).strip() if who else None, "party": who.group(2) if who else None,
                        "reason": text_of(cells[idx["Reason"]]), "date": text_of(cells[idx["Removal Date"]]).split(" ")[0]})
    return out


def kept(path, fetch, max_age_days=7):
    """A small JSON of the kept columns, refreshed from the page when it is older than max_age_days."""
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < max_age_days * 86400:
        return json.load(open(path, encoding="utf-8"))
    data = fetch()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(data, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    time.sleep(1.0)
    return data


def load(con, cache, say=print):
    net.patient_lookups()
    folder = os.path.join(cache, "mo")
    gpath = os.path.join(folder, "mo_2026_general_certified_candidates.pdf")
    net.download(GENERAL_URL, gpath, max_age_days=7)
    general, published = general_list(gpath)
    seats = {d for d, _p, _n in general}
    if seats != set(range(1, 9)):
        raise SystemExit(f"Missouri: the certification names candidates for districts {sorted(seats)}; eight were expected")
    twice = [(d, p) for d, p, _n in general if sum(1 for d2, p2, _ in general if (d2, p2) == (d, p)) > 1 and p != "Independent"]
    if twice:
        raise SystemExit(f"Missouri: more than one nominee of one party for one seat: {sorted(set(twice))}")
    rows, order = [], {}
    for d, party, name in general:
        race = house_id("MO", d)
        order[race] = order.get(race, 0) + 1
        rows.append((race, "general", "2026-11-03", name, party, party_code(party), order[race], 0, 0, None, None, None, None, None,
                     "mo-sos-2026-general-certification", None))
    nominee = {(d, party): fold(name) for d, party, name in general}

    ppath = os.path.join(folder, "mo_2026_primary_certified_list_federal.json")
    rpath = os.path.join(folder, "mo_2026_primary_removed_federal.json")
    primary = kept(ppath, lambda: primary_list(decode(net.get(PRIMARY_URL, accept="text/html"))))
    removed = kept(rpath, lambda: removed_list(decode(net.get(REMOVED_URL, accept="text/html"))))
    fields = {}
    for r in primary:
        fields.setdefault((r["district"], r["party"]), []).append(r["name"])
    unsettled = []
    for (d, party), names in sorted(fields.items()):
        if len(names) < 2:
            continue
        won = [n for n in names if nominee.get((d, party)) == fold(n)]
        if len(won) != 1:
            unsettled.append(f"MO-{d} {party}")
        code = CODE.get(party, party[:3].upper())
        for name in names:
            outcome = ("advanced" if nominee.get((d, party)) == fold(name) else "lost") if len(won) == 1 else None
            rows.append((house_id("MO", d), f"primary-{code}", PRIMARY, name, party, party_code(party), None, 0, 0, None, None, outcome,
                         None, None, "mo-sos-2026-primary-certified-list", None))
    with con:
        con.execute("DELETE FROM candidates WHERE race_id LIKE '2026-MO-%'")
        con.executemany("INSERT OR REPLACE INTO candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        record_source(con, "mo-sos-2026-general-certification", path=gpath, level="federal", state="MO", kind="official candidate list",
                      agency="Missouri Secretary of State", title="Certification of Candidates and Party Emblems, General Election, Tuesday, November 3, 2026",
                      url=GENERAL_URL, published=published, rows=len(general),
                      note="Read party by party from the PDF, the U.S. Representative lines only. Ballot order is the certification's own order "
                           "(no order numbers are printed); no withdrawn or write-in candidates are listed in it.")
        record_source(con, "mo-sos-2026-primary-certified-list", path=ppath, level="federal", state="MO", kind="official candidate list",
                      agency="Missouri Secretary of State", title="Certified Candidate List, 2026 Primary Election (August 4, 2026): U.S. Representative",
                      url=PRIMARY_URL, rows=len(primary),
                      note=f"Name and party only; mailing addresses never kept. Withdrawn or removed before the primary, left off: {len(removed)} "
                           f"(from {REMOVED_URL}). Who advanced is read from the November certification. Vote counts are not loaded: "
                           f"the Secretary's results page ({RESULTS_PAGE}) offers only unofficial election-night results on a host that refuses "
                           "scripts, and no official results file for August 4, 2026 is posted yet."
                           + (f" No single advancer found for: {', '.join(unsettled)}." if unsettled else ""))
    n = len(general)
    say(f"    Missouri: 8 House districts (no Senate race in 2026), {n} candidates on the November ballot; "
        f"{sum(1 for v in fields.values() if len(v) > 1)} party primaries with a field ({len(removed)} withdrawn before the primary left off), no vote counts yet"
        + (f"; no single advancer for {', '.join(unsettled)}" if unsettled else ""))
    return n
