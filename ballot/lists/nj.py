"""
New Jersey: the Division of Elections' own candidate lists, certifications and official results (nj.gov/state/elections,
the "2026 Election Year Information" page, election-information-2026.shtml, where every file is linked; the file names
carry the date of issue, -0904, so the links are found by their labels). New Jersey has twelve House seats and the class
2 Senate seat in 2026. The primary was held on June 2, 2026 (the Division's "2026 Primary Election Timeline").

  November ballot   "Official General Election Candidates: U.S. House of Representatives" (headed "09/04/2026 Official
                    List ... For GENERAL ELECTION 11/03/2026", one page per district) and "Official General Election
                    Candidates: U.S. Senate" (headed 07/27/2026).
  certifications    "Certification of General Election Nominees: U.S. Senate & U.S. House of Representatives" (a signed
                    cover page, a scan with no text, then the same report dated 07/27/2026) and every "Amended
                    Certification of Nominees General Election U.S. House of Representatives: <n>th Congressional
                    District" the page links (in 2026 the 7th, 09/04/2026). Used as checks: for each race, the latest
                    certification must name exactly the candidates on the list, and anyone certified on July 27 but no
                    longer certified is counted as left off (withdrawn or removed: in 2026, the Libertarian Party's
                    candidate in the 7th District, certified July 27 and not on the amended certification of September
                    4). Four amended certifications the page also links (the Senate, the 9th District twice, the 10th)
                    answer 404; they appear to be carried over from the 2024 page, and are skipped and named.
  primary results   "Official Primary Election Results: U.S. House of Representatives" and "...: U.S. Senate" (headed
                    07/27/2026 Official List, For PRIMARY ELECTION 06/02/2026): every candidate on each party's primary
                    ballot, the winner marked "(w)", the votes county by county, each candidate's Total, and for a House
                    district a last Total for all its candidates of both parties.
  primary list      "Official Primary Election Candidates: U.S. House of Representatives" and "...: U.S. Senate"
                    (04/02/2026): who was certified to the primary ballot; the results must name exactly these, and any
                    who are not in the results are counted as having left the ballot before June 2.

All are reports in one layout: headings Name, Address, Party, County, Slogan (and Tally in the results), then per
candidate a first line with the name at the Name column's edge and the party at the Party column's edge, the address on
that line and the next ones, and one line per county with the slogan printed beside the name on that county's ballot
(and the county's votes). A district's page opens with "First Congressional District: <counties> Counties". A last page
counts the candidates per party ("Candidate Totals for Party"); those counts, the page numbering ("Page 1 of 13"), the
counties under every district heading, and in the results each candidate's county votes against the Total and the
district's Total against its candidates are all checked.

The Address column is never turned into text. On each line only the pieces of text that begin at the Name, Party and
County columns' left edges, the slogan pieces to the right of a county name, and the numbers under Tally are read; an
address piece can begin anywhere between the Name and Party columns (a long one starts left of its heading), so nothing
there is read by band. A name piece that holds a digit or runs into the next piece stops the loader. The PDFs are read in
memory and never written to disk; the cache (ballot_cache/nj/) holds only what is read, as JSON, with each PDF's
SHA-256. The Division's "Candidates Email" lists are never fetched.

Names are printed in capitals ("CORY BOOKER *", "*" marking the incumbent) and shown in ordinary capitals, the words of a
sitting member's name with the capitals the congress-legislators roster gives them; the rows say so. The Party column
prints Democratic and Republican (New Jersey's only recognized parties), "Green Party" or "Libertarian Party", and for
other candidates nominated by petition the designation they filed, in capitals: "INDEPENDENT", "SOCIALIST WORKERS PARTY",
"SAVE OUR BABIES". Those in capitals are shown in ordinary capitals. Where a candidate's slogan on a county's ballot is
not the party as printed (an independent with a different slogan county by county), the row says which slogan each
county prints. The general lists give no ballot order: in New Jersey each county clerk draws the order for the county's
ballot, so it differs from county to county, and the order kept is the list's own (in 2026: the major parties' nominees,
the sitting member first where one is running, then the candidates nominated by petition). The lists name no write-in
candidates.

A party primary is a field when two or more candidates were on that party's ballot for the race. The votes are the
official Totals. The results print no write-in ("personal choice") votes, so a field's total is the sum of its
candidates' votes. The candidate marked "(w)" advanced; that must be the one with the most votes and the party's
candidate on the November list, or the row says plainly that the nominee is not on it.
"""

import datetime as dt
import hashlib
import html as H
import json
import os
import re
import sqlite3
import time
from collections import Counter
from urllib.error import HTTPError
from urllib.parse import urljoin

from ballot.common import HERE, fold, house_id, name_parts, party_code, record_source, senate_id
from ballot.lists.tx import proper
from ballot.pdftext import PDF, join, rows as pdf_rows
from states import net

PAGE = "https://www.nj.gov/state/elections/election-information-2026.shtml"
PRIMARY = "2026-06-02"
AGENCY = "New Jersey Department of State, Division of Elections"
LABELS = {
    "general-house": "Official General Election Candidates: U.S. House of Representatives",
    "general-senate": "Official General Election Candidates: U.S. Senate",
    "results-house": "Official Primary Election Results: U.S. House of Representatives",
    "results-senate": "Official Primary Election Results: U.S. Senate",
    "primary-house": "Official Primary Election Candidates: U.S. House of Representatives",
    "primary-senate": "Official Primary Election Candidates: U.S. Senate",
    "certification": "Certification of General Election Nominees: U.S. Senate & U.S. House of Representatives",
}
AMENDED = re.compile(r"^Amended Certification of (?:Nominees General Election|General Election Nominees):? "
                     r"(?P<office>U\.S\. House of Representatives|U\.S\. Senate)(?:\s*[-:]\s*(?P<d>\d+)(?:st|nd|rd|th) Congressional District)?$")
HOUSE, SENATE = "House of Representatives", "US Senate"
EXPECT = {"general-house": (HOUSE, "GENERAL"), "general-senate": (SENATE, "GENERAL"), "results-house": (HOUSE, "PRIMARY"),
          "results-senate": (SENATE, "PRIMARY"), "primary-house": (HOUSE, "PRIMARY"), "primary-senate": (SENATE, "PRIMARY")}
DATES = {"GENERAL": "11/03/2026", "PRIMARY": "06/02/2026"}
MAX_AGE = {"general-house": 2, "general-senate": 2, "certifications": 2, "results-house": 30, "results-senate": 30,
           "primary-house": 30, "primary-senate": 30}
ORDINALS = {w: i for i, w in enumerate(("First", "Second", "Third", "Fourth", "Fifth", "Sixth", "Seventh", "Eighth", "Ninth",
                                        "Tenth", "Eleventh", "Twelfth"), start=1)}
HEADING = re.compile(r"^(?P<ord>[A-Z][a-z]+) Congressional District:(?P<counties>.*)$")
PAGE_LINE = re.compile(r"^(?:(?P<date>\d\d/\d\d/\d{4}) Official List|Official List (?P<date2>\d\d/\d\d/\d{4})) Page (?P<k>\d+) of (?P<of>\d+)$")
FOR = re.compile(r"^For (?P<kind>GENERAL|PRIMARY) ELECTION (?P<date>\d\d/\d\d/\d{4}) Election, \* denotes incumbent$")
NUMBER = re.compile(r"^\d{1,3}(?:,\d{3})*$")
MARKS = re.compile(r"\s*(?:\(w\))?\s*\*?\s*")      # the winner's and the incumbent's marks, printed after a name
COUNTIES = {"ATLANTIC", "BERGEN", "BURLINGTON", "CAMDEN", "CAPE MAY", "CUMBERLAND", "ESSEX", "GLOUCESTER", "HUDSON", "HUNTERDON",
            "MERCER", "MIDDLESEX", "MONMOUTH", "MORRIS", "OCEAN", "PASSAIC", "SALEM", "SOMERSET", "SUSSEX", "UNION", "WARREN"}
CODE = {"Democratic": "DEM", "Republican": "REP"}
SMALL = {"a", "an", "and", "the", "of", "for", "in", "on", "to", "or", "by", "at", "with", "from"}
EDGE = 2.5          # points: how close to a column's left edge a piece must begin to belong to it
CAPS = "New Jersey's list prints names in capitals; they are shown here in ordinary capitals."
NOT_ON_LIST = "Won the primary, but is not on the November list for this party."


def squash(text):
    return re.sub(r"\s+", " ", (text or "").replace("\xa0", " ")).strip()


def links():
    """{key: address} for the seven files named in LABELS, and [(label, address)] for every amended certification."""
    page = net.get(PAGE, accept="text/html").decode("utf-8", "replace")
    found, amended = {}, []
    for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', page, re.S | re.I):
        label, href = squash(H.unescape(re.sub(r"<[^>]+>", " ", m.group(2)))), H.unescape(m.group(1))
        if not href.lower().endswith(".pdf"):
            continue
        for key, want in LABELS.items():
            if label == want and key not in found:
                found[key] = urljoin(PAGE, href)
        if AMENDED.match(label) and (label, urljoin(PAGE, href)) not in amended:
            amended.append((label, urljoin(PAGE, href)))
    missing = [LABELS[k] for k in LABELS if k not in found]
    if missing:
        raise SystemExit(f"New Jersey: the 2026 page no longer links {missing}")
    return found, amended


def get_pdf(url, missing_ok=False):
    """A PDF, in memory only. Asked up to three times; a 404 is None when missing_ok."""
    for attempt in range(3):
        try:
            data = net.get(url, accept="application/pdf")
            break
        except HTTPError as e:
            if e.code == 404 and missing_ok:
                return None
            if attempt == 2 or e.code in (403, 429):
                raise SystemExit(f"New Jersey: {url} answered HTTP {e.code}")
            time.sleep(10 * (attempt + 1))
        except OSError as e:
            if attempt == 2:
                raise SystemExit(f"New Jersey: {url} could not be fetched ({e})")
            time.sleep(10 * (attempt + 1))
    if not data.startswith(b"%PDF"):
        raise SystemExit(f"New Jersey: {url} is not a PDF (it begins {data[:8]!r})")
    time.sleep(1.5)
    return data


def text_of(r):
    return squash(r[3])


def name_text(rs, nr, what, n):
    """The name piece at the Name column's edge, with the marks "(w)" and "*" when they are printed as pieces of their own
    touching it. A name piece holding a digit, or running into any other piece, stops the loader: it may carry an address."""
    marks = [r for r in rs if r is not nr and abs(r[0] - nr[4]) < 1 and MARKS.fullmatch(r[3])]
    others = [r[0] for r in rs if r is not nr and r not in marks]
    end = max([nr[4]] + [r[4] for r in marks])
    if re.search(r"\d", nr[3]) or (others and end > min(others) - 1):
        raise SystemExit(f"New Jersey: {what}, page {n}: a name piece that holds a digit or runs into the next piece; "
                         "the loader does not read it (it may carry an address)")
    return squash(" ".join([nr[3]] + [r[3] for r in sorted(marks)]))


def read_report(data, what, office=None):
    """What one of the Division's candidate reports says, the Address column left unread. Only pages whose title names
    the office are read (a certification carries the Senate's report and then the House's); a page with no table (the
    signed cover) is passed over. Returns {"printed", "office", "kind", "date", "pages", "blocks": [{"district", "name",
    "star", "won", "party", "counties": [[county, slogan, tally]], "total"}], "totals": {party: n}, "total_candidates",
    "race_totals": {district: n}, "districts": {district: [counties]}}."""
    pdf = PDF(data)
    out = {"printed": None, "office": None, "kind": None, "date": None, "pages": 0, "tally": False, "blocks": [], "totals": {},
           "total_candidates": None, "race_totals": {}, "districts": {}}
    block, district, of = None, None, None
    for n, (page, res) in enumerate(pdf.pages(), start=1):
        title, body, edges = [], [], None
        for _y, rs in pdf_rows(pdf, page, res):
            rs = sorted(rs, key=lambda r: r[0])
            words = [text_of(r) for r in rs]
            if edges is None:
                if words and words[0] == "Name" and {"Address", "Party", "County", "Slogan"} <= set(words):
                    edges = {w: r[0] for w, r in zip(words, rs)}
                elif words and words[0] == "Candidate Totals for Party":
                    edges = "totals"
                else:
                    title.append(join(rs))      # the page's title lines, above the headings
                continue
            body.append(rs)
        if edges is None:
            continue                            # no table on this page: the signed cover of a certification
        at_office = next((i for i, t in enumerate(title) if t.startswith("Candidates for ")), None)
        p = PAGE_LINE.match(" ".join(title[:at_office])) if at_office else None      # "Official List" can sit on a line of its own
        f = FOR.match(title[at_office + 1]) if at_office is not None and len(title) > at_office + 1 else None
        if not p or not f:
            raise SystemExit(f"New Jersey: {what}, page {n}: the report's title lines changed")
        page_office = title[at_office][len("Candidates for "):]
        if office and page_office != office:
            continue
        meta = (dt.datetime.strptime(p.group("date") or p.group("date2"), "%m/%d/%Y").date().isoformat(), page_office,
                f.group("kind"), f.group("date"))
        if out["printed"] is None:
            out["printed"], out["office"], out["kind"], out["date"] = meta
            of = int(p.group("of"))
        elif meta != (out["printed"], out["office"], out["kind"], out["date"]) or int(p.group("of")) != of:
            raise SystemExit(f"New Jersey: {what}, page {n}: a page from another report ({title[:3]})")
        out["pages"] += 1
        if int(p.group("k")) != out["pages"]:
            raise SystemExit(f"New Jersey: {what}, page {n}: the report's pages are out of order")
        if edges == "totals":
            for rs in body:
                label = [r for r in rs if r[0] < 100]
                count = [r for r in rs if r[0] >= 200 and NUMBER.match(text_of(r))]
                if len(label) == 1 and len(count) == 1:
                    k, v = text_of(label[0]), int(text_of(count[0]).replace(",", ""))
                    if k == "Total Candidates":
                        out["total_candidates"] = v
                    else:
                        out["totals"][k] = v
            continue
        out["tally"] = out["tally"] or "Tally" in edges
        heading, county_seen, name_open, repeat, first = None, False, False, False, True
        for rs in body:
            at = lambda col: [r for r in rs if col in edges and abs(r[0] - edges[col]) < EDGE]
            name_r, party_r, county_r = at("Name"), at("Party"), at("County")
            if party_r:
                # a candidate's first line: the name at the Name edge, the party at the Party edge, the address between (unread)
                if len(name_r) != 1 or len(party_r) != 1:
                    raise SystemExit(f"New Jersey: {what}, page {n}: a candidate line without exactly one name and one party piece")
                if heading is not None and heading["open"]:
                    raise SystemExit(f"New Jersey: {what}, page {n}: a district heading that does not end in \"Counties\"")
                name, party = name_text(rs, name_r[0], what, n), text_of(party_r[0])
                if (first and block is not None and block["total"] is None
                        and (block["district"], block["first_line"], block["party"]) == (district, name, party)):
                    county_seen, name_open, repeat, first = bool(block["counties"]), True, True, False
                    continue          # the last candidate's first line again at the top of a page: its counties go on
                block = {"district": district, "name": name, "first_line": name, "party": party, "counties": [], "total": None}
                out["blocks"].append(block)
                county_seen, name_open, repeat, first = False, True, False, False
                continue
            follows, name_open = name_open, False
            if name_r:
                t = text_of(name_r[0])
                if follows and block is not None and not county_seen and len(name_r) == 1:
                    # the rest of a long name, on the line under it (the rest of the address beside it is not read)
                    rest = name_text(rs, name_r[0], what, n)
                    if not repeat:
                        block["name"] += ("" if block["name"].endswith("-") else " ") + rest
                    name_open = True
                    continue
                h = HEADING.match(t)
                if h and len(rs) == 1:
                    if h.group("ord") not in ORDINALS:
                        raise SystemExit(f"New Jersey: {what}, page {n}: a district heading that is not read ({h.group('ord')!r})")
                    if ORDINALS[h.group("ord")] != district:
                        block = None          # the same heading again at the top of a page: the last candidate's counties go on
                    district = ORDINALS[h.group("ord")]
                    heading = {"text": h.group("counties"), "open": not t.endswith("Counties")}
                    continue
                if heading is not None and heading["open"] and len(rs) == 1:
                    heading["text"] += " " + t
                    heading["open"] = not t.endswith("Counties")
                    continue
                raise SystemExit(f"New Jersey: {what}, page {n}: a line at the Name column that is neither a candidate nor a "
                                 "district heading; the loader does not read it")
            if heading is not None and not heading["open"] and "counties" not in heading:
                heading["counties"] = sorted(squash(c.replace("(part)", "")) for c in
                                             re.sub(r"\s*Counties$", "", squash(heading["text"])).split(" - "))
                if out["districts"].setdefault(str(district), heading["counties"]) != heading["counties"]:
                    raise SystemExit(f"New Jersey: {what}, page {n}: District {district}'s heading names other counties than before")
            if county_r:
                if block is None:
                    raise SystemExit(f"New Jersey: {what}, page {n}: county lines before any candidate")
                cr = county_r[0]
                county = text_of(cr)
                if county not in COUNTIES:
                    raise SystemExit(f"New Jersey: {what}, page {n}: a county that is not one of New Jersey's 21 ({county!r})")
                if any(c[0] == county for c in block["counties"]):
                    raise SystemExit(f"New Jersey: {what}, page {n}: {county} twice under one candidate")
                rest = [r for r in rs if r[0] > cr[4]]
                tally = []
                if "Tally" in edges:          # the county's votes: the last piece on the line (a long slogan pushes it left)
                    if not rest or not NUMBER.match(text_of(rest[-1])):
                        raise SystemExit(f"New Jersey: {what}, page {n}: a county line with no votes")
                    tally = [rest[-1]]
                slogan = [r for r in rest if r not in tally]
                block["counties"].append([county, join(slogan) if slogan else "",
                                          int(text_of(tally[0]).replace(",", "")) if tally else None])
                county_seen = True
                continue
            if block is not None and any(text_of(r) == "Total" for r in rs):
                num = [r for r in rs if r[0] >= 540 and NUMBER.match(text_of(r))]
                if len(num) != 1 or len(rs) != 2:
                    raise SystemExit(f"New Jersey: {what}, page {n}: a Total line that is not read")
                if block["total"] is None:
                    block["total"] = int(text_of(num[0]).replace(",", ""))
                else:                 # a second Total under the last candidate: every candidate in the race, both parties
                    if str(district) in out["race_totals"]:
                        raise SystemExit(f"New Jersey: {what}, page {n}: a third Total line under one candidate")
                    out["race_totals"][str(district)] = int(text_of(num[0]).replace(",", ""))
                continue
            if block is not None and county_seen and all(r[0] >= 360 for r in rs):
                if any(r[0] >= 540 and NUMBER.match(text_of(r)) for r in rs):
                    raise SystemExit(f"New Jersey: {what}, page {n}: a number on a line that is not a county line")
                block["counties"][-1][1] = squash(block["counties"][-1][1] + " " + join(rs))      # a slogan on two lines
                continue
            # anything else is the rest of an address, between the Name and Party columns: never turned into text
    if out["printed"] is None:
        raise SystemExit(f"New Jersey: {what}: no pages for {office or 'any office'}")
    if out["pages"] != of:
        raise SystemExit(f"New Jersey: {what}: {out['pages']} pages read of the {of} the report numbers")
    for b in out["blocks"]:
        del b["first_line"]
        name = b["name"]
        b["star"] = name.endswith("*")
        name = name.rstrip("* ").strip()
        b["won"] = name.endswith("(w)")
        b["name"] = name[:-3].strip() if b["won"] else name
    # the report's own controls: the candidates per party on its last page, and the counties under each heading
    count = Counter(b["party"] for b in out["blocks"])
    if dict(count) != out["totals"] or out["total_candidates"] != len(out["blocks"]):
        raise SystemExit(f"New Jersey: {what}: the candidates read ({dict(count)}) are not the report's own count "
                         f"({out['totals']}, {out['total_candidates']})")
    for b in out["blocks"]:
        want = out["districts"].get(str(b["district"])) if b["district"] else sorted(COUNTIES)
        if sorted(c[0] for c in b["counties"]) != want:
            raise SystemExit(f"New Jersey: {what}: a District {b['district']} candidate's counties are not the district's")
        if out["tally"]:
            if b["total"] is None or sum(c[2] for c in b["counties"]) != b["total"]:
                raise SystemExit(f"New Jersey: {what}: a District {b['district']} candidate's county votes do not add up to the Total")
    for d, v in out["race_totals"].items():
        if sum(b["total"] for b in out["blocks"] if str(b["district"]) == d) != v:
            raise SystemExit(f"New Jersey: {what}: District {d}'s Total is not the sum of its candidates' Totals")
    return out


def slim(report, slogans):
    """What the cache keeps: the slogans only for the November lists (they are what each county's ballot prints)."""
    if not slogans:
        for b in report["blocks"]:
            for c in b["counties"]:
                c[1] = ""
    return report


def kept(path, max_age_days, url_key, build):
    """A small JSON of what is read from a source, rebuilt when older than max_age_days or when the page links another file."""
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < max_age_days * 86400:
        data = json.load(open(path, encoding="utf-8"))
        if data.get("url_key") == url_key:
            return data
    data = build()
    data.update(url_key=url_key, read=dt.date.today().isoformat())
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(data, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return data


def report_of(key, url):
    data = get_pdf(url)
    office, kind = EXPECT[key]
    rep = read_report(data, LABELS[key], office)
    if (rep["office"], rep["kind"], rep["date"]) != (office, kind, DATES[kind]):
        raise SystemExit(f"New Jersey: {LABELS[key]} is headed {rep['office']!r}, {rep['kind']} {rep['date']}")
    rep.update(url=url, sha256=hashlib.sha256(data).hexdigest())
    return slim(rep, key.startswith("general"))


def certifications(cert_url, amended):
    """The July 27 certification's Senate and House reports, and every amended certification the page links."""
    data = get_pdf(cert_url)
    out = {"url": cert_url, "sha256": hashlib.sha256(data).hexdigest(),
           "senate": slim(read_report(data, LABELS["certification"], SENATE), False),
           "house": slim(read_report(data, LABELS["certification"], HOUSE), False), "amended": []}
    for label, url in amended:
        a = get_pdf(url, missing_ok=True)
        if a is None:
            out["amended"].append({"label": label, "url": url, "missing": True})
            continue
        office = SENATE if AMENDED.match(label).group("office") == "U.S. Senate" else HOUSE
        rep = slim(read_report(a, label, office), False)
        if rep["kind"] != "GENERAL" or rep["date"] != DATES["GENERAL"]:
            raise SystemExit(f"New Jersey: {label} is not for the November 3, 2026 general election")
        out["amended"].append({"label": label, "url": url, "missing": False, "sha256": hashlib.sha256(a).hexdigest(), "report": rep})
    return out


def mdy(iso):
    return f"{iso[5:7]}/{iso[8:]}/{iso[:4]}"


def race_of(block):
    return house_id("NJ", block["district"]) if block["district"] else senate_id("NJ", 2)


def party_label(printed):
    """The party as printed; a designation printed in capitals in ordinary capitals ("END THE CORRUPTION!" -> End the Corruption!)."""
    p = squash(printed)
    if p != p.upper():
        return p
    out = []
    for i, w in enumerate(p.split()):
        low = w.lower()
        if i and re.sub(r"[^a-z]", "", low) in SMALL:
            out.append(low)
        else:
            out.append("-".join(part[:1].upper() + part[1:] for part in low.split("-")))
    return " ".join(out)


def roster():
    """The capitals of the New Jersey members' names, from the congress-legislators roster (read only)."""
    rec = sqlite3.connect(f"file:{os.path.join(HERE, 'congress_119.sqlite')}?mode=ro", uri=True)
    full, members = {}, []
    for official, first, last in rec.execute("SELECT official_full, first_name, last_name FROM legislators WHERE is_current = 1 AND state = 'NJ'"):
        for form in (official, f"{first} {last}"):
            if form:
                full[fold(form)] = form
        words = re.findall(r"[^\s,]+", f"{official or ''} {first} {last}")
        members.append(({fold(w): w for w in words if fold(w)}, fold(last).split()))
    rec.close()
    return full, members


def shown(caps, names):
    """A name printed in capitals, in ordinary capitals; a member's name (or its words) as the roster writes it."""
    full, members = names
    caps = squash(caps)
    if fold(caps) in full:
        return full[fold(caps)]
    printed = caps.split()
    out = proper(caps).split()
    folded = [fold(w) for w in printed]
    for words, family in members:
        if family and any(folded[i:i + len(family)] == family for i in range(len(folded))):
            out = [words.get(f, o) if f else o for f, o in zip(folded, out)]
            break
    return re.sub(r"(['\"(])([a-z])", lambda m: m.group(1) + m.group(2).upper(), " ".join(out))


def slogan_note(block):
    """A sentence when a county's ballot prints a slogan other than the party as printed."""
    if all(c[1].upper() == block["party"].upper() for c in block["counties"]):
        return None
    by = {}
    for county, slogan, _t in block["counties"]:
        by.setdefault(party_label(slogan), []).append(county.title())
    parts = [f"“{s}” ({', '.join(cs)})" for s, cs in by.items()]
    return "The ballot prints a slogan beside the name that differs by county: " + "; ".join(parts) + "."


def load(con, cache, say=print):
    net.patient_lookups()
    folder = os.path.join(cache, "nj")
    urls, amended = links()
    paths, reps = {}, {}
    for key in ("general-house", "general-senate", "results-house", "results-senate", "primary-house", "primary-senate"):
        paths[key] = os.path.join(folder, f"nj_2026_{key}.json")
        reps[key] = kept(paths[key], MAX_AGE[key], urls[key], lambda k=key: report_of(k, urls[k]))
    paths["certifications"] = os.path.join(folder, "nj_2026_certifications.json")
    certs = kept(paths["certifications"], MAX_AGE["certifications"], "|".join([urls["certification"]] + [u for _l, u in amended]),
                 lambda: certifications(urls["certification"], amended))
    names = roster()
    races = dict(con.execute("SELECT race_id, holder_name FROM races WHERE state = 'NJ'").fetchall())

    # the November ballot
    rows, order, nominee, general_rows, stars = [], {}, {}, {}, []
    for key in ("general-senate", "general-house"):
        src = f"nj-dos-2026-{key}"
        for b in reps[key]["blocks"]:
            race = race_of(b)
            if race not in races:
                raise SystemExit(f"New Jersey: the list names a race that is not in the races table ({race})")
            party = party_label(b["party"])
            name = shown(b["name"], names)
            if b["won"]:
                raise SystemExit(f"New Jersey: a winner's mark on the November list ({race})")
            order[race] = order.get(race, 0) + 1
            note = " ".join(x for x in (CAPS, slogan_note(b)) if x)
            rows.append((race, "general", "2026-11-03", name, party, party_code(party), order[race], 0, 0, None, None, None, None, None,
                         src, note))
            general_rows.setdefault(race, set()).add((fold(b["name"]), b["party"]))
            if party in CODE:
                if (race, party) in nominee:
                    raise SystemExit(f"New Jersey: two {party} candidates on the November list for {race}")
                nominee[(race, party)] = fold(b["name"])
            if b["star"]:
                held = name_parts(races[race] or "")[1]
                if not held or fold(name_parts(b["name"])[1]) != held:
                    stars.append(f"{name} ({race}; the races table has {races[race]})")

    # the certifications: the latest for each race must be the list; anyone certified on July 27 and not now is left off
    def by_race(rep):
        out = {}
        for b in rep["blocks"]:
            out.setdefault(race_of(b), set()).add((fold(b["name"]), b["party"]))
        return out
    latest, when = {}, {}
    for rep in (certs["senate"], certs["house"]):
        for race, cands in by_race(rep).items():
            latest[race], when[race] = cands, rep["printed"]
    missing_amended, used_amended = [], []
    for a in certs["amended"]:
        if a["missing"]:
            missing_amended.append(a["label"])
            continue
        used_amended.append(f"{a['label']} ({a['report']['printed']})")
        for race, cands in by_race(a["report"]).items():
            if a["report"]["printed"] >= when.get(race, ""):
                latest[race], when[race] = cands, a["report"]["printed"]
    for race in set(latest) | set(general_rows):
        if latest.get(race, set()) != general_rows.get(race, set()):
            raise SystemExit(f"New Jersey: the November list for {race} is not the latest certification "
                             f"({len(general_rows.get(race, set()))} against {len(latest.get(race, set()))} candidates)")
    left_off = []
    for rep in (certs["senate"], certs["house"]):
        for b in rep["blocks"]:
            if (fold(b["name"]), b["party"]) not in latest.get(race_of(b), set()):
                left_off.append(f"{shown(b['name'], names)} ({party_label(b['party'])}, "
                                f"{'District ' + str(b['district']) if b['district'] else 'Senate'})")

    # the primaries: the results must name exactly the April 2 list's candidates, less any who left the ballot
    listed = {}
    for key in ("primary-senate", "primary-house"):
        for b in reps[key]["blocks"]:
            if b["party"] not in CODE:
                raise SystemExit(f"New Jersey: a primary candidate for a party that has no primary ({b['party']!r})")
            listed.setdefault((race_of(b), b["party"]), {})[fold(b["name"])] = b["name"]
    fields, not_on, gone, checked = 0, [], [], 0
    results = {}
    for key in ("results-senate", "results-house"):
        for b in reps[key]["blocks"]:
            if b["party"] not in CODE:
                raise SystemExit(f"New Jersey: a result for a party that has no primary ({b['party']!r})")
            results.setdefault((race_of(b), b["party"]), []).append((key, b))
    for k, cands in listed.items():
        got = {fold(b["name"]) for _key, b in results.get(k, [])}
        extra = got - set(cands)
        if extra:
            raise SystemExit(f"New Jersey: the {k[0]} {k[1]} results name {len(extra)} candidate(s) not on the April 2 primary list")
        gone += [(k[0], f"{shown(cands[f], names)} ({k[1]}, {k[0]})") for f in sorted(set(cands) - got)]
    if set(results) - set(listed):
        raise SystemExit(f"New Jersey: results for races with no one on the April 2 primary list ({sorted(set(results) - set(listed))})")
    for (race, party), cands in sorted(results.items()):
        winners = [b for _key, b in cands if b["won"]]
        if len(winners) != 1:
            raise SystemExit(f"New Jersey: the {race} {party} primary has {len(winners)} winners marked")
        top = max(b["total"] for _key, b in cands)
        if winners[0]["total"] != top or sum(1 for _key, b in cands if b["total"] == top) != 1:
            raise SystemExit(f"New Jersey: the {race} {party} primary's marked winner does not have the most votes")
        checked += len(cands)
        on_list = nominee.get((race, party)) == fold(winners[0]["name"])
        if len(cands) < 2:
            if not on_list:
                not_on.append(f"{shown(winners[0]['name'], names)} ({party}, {race}, unopposed)")
            continue
        fields += 1
        total = sum(b["total"] for _key, b in cands)
        for key, b in sorted(cands, key=lambda kb: (-kb[1]["total"], kb[1]["name"])):
            note = CAPS
            if b["won"] and not on_list:
                note = f"{NOT_ON_LIST} {CAPS}"
                not_on.append(f"{shown(b['name'], names)} ({party}, {race})")
            rows.append((race, f"primary-{CODE[party]}", PRIMARY, shown(b["name"], names), party, party_code(party), None, 0, 0,
                         b["total"], round(100 * b["total"] / total, 1) if total else None, "advanced" if b["won"] else "lost",
                         None, None, f"nj-dos-2026-{key}", note))

    gaps = [(r, "The Division of Elections' November list names no candidates for this race.") for r in sorted(races) if r not in order]
    november = sum(1 for r in rows if r[1] == "general")
    with con:
        con.execute("DELETE FROM candidates WHERE race_id LIKE '2026-NJ-%'")
        con.execute("DELETE FROM list_gaps WHERE state = 'NJ'")
        con.executemany("INSERT OR REPLACE INTO candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        con.executemany("INSERT INTO list_gaps VALUES (?, 'NJ', ?)", gaps)
        read = ("Read by column edges: the Name, Party and County columns, the slogans beside the counties"
                "{}; the Address column is never turned into text, and the PDF is not kept (SHA-256 {}).")
        for key in ("general-house", "general-senate"):
            r = reps[key]
            record_source(con, f"nj-dos-2026-{key}", path=paths[key], level="federal", state="NJ", kind="official candidate list",
                          agency=AGENCY, title=f"{LABELS[key]} (Official List, {mdy(r['printed'])})", url=r["url"],
                          published=r["printed"], rows=len(r["blocks"]),
                          note=read.format("", r["sha256"]) + " The list gives no ballot order (each county clerk draws the order "
                               "for the county's ballot); the order kept is the list's own. Designations printed in capitals are shown "
                               "in ordinary capitals. The list's own count of candidates per party matches. "
                               + (f"Certified on July 27 and no longer certified, left off: {len(left_off)} ({'; '.join(left_off)})."
                                  if key == "general-house" else ""))
        record_source(con, "nj-dos-2026-certifications", path=paths["certifications"], level="federal", state="NJ",
                      kind="official certification", agency=AGENCY, title=LABELS["certification"] + f" ({certs['house']['printed']})"
                      + (" and " + "; ".join(used_amended) if used_amended else ""), url=certs["url"], published=certs["house"]["printed"],
                      rows=len(certs["senate"]["blocks"]) + len(certs["house"]["blocks"]),
                      note=f"A check: for each race the latest certification names exactly the candidates on the list. The signed cover "
                           f"page is a scan and is not read; the reports behind it are read like the lists (SHA-256 {certs['sha256']}). "
                           + (f"Linked from the 2026 page but not found (HTTP 404; they appear to be carried over from the 2024 "
                              f"page): {'; '.join(missing_amended)}." if missing_amended else ""))
        for key, title in (("results-senate", "Official Primary Election Results: U.S. Senate (June 2, 2026)"),
                           ("results-house", "Official Primary Election Results: U.S. House of Representatives (June 2, 2026)")):
            r = reps[key]
            record_source(con, f"nj-dos-2026-{key}", path=paths[key], level="federal", state="NJ", kind="official results",
                          agency=AGENCY, title=title, url=r["url"], published=r["printed"], rows=len(r["blocks"]),
                          note=read.format(" and the votes under Tally", r["sha256"]) + " Every candidate's county votes add up to "
                               "the Total" + (", and each district's last Total to its candidates' Totals" if r["race_totals"] else "")
                               + ". No write-in (personal choice) votes are printed, so a field's total is the sum of its candidates' "
                                 "votes. \"(w)\" marks who won.")
        for key in ("primary-senate", "primary-house"):
            r = reps[key]
            mine = [g for race, g in gone if race.endswith("-S2") == (key == "primary-senate")]
            record_source(con, f"nj-dos-2026-{key}", path=paths[key], level="federal", state="NJ", kind="official candidate list",
                          agency=AGENCY, title=f"{LABELS[key]} (Official List, {mdy(r['printed'])})",
                          url=r["url"], published=r["printed"], rows=len(r["blocks"]),
                          note=read.format("", r["sha256"]) + " Used to check the results: each party's primary ballot for each race "
                               f"must be these candidates. On this list but not in the results (left the ballot before June 2): "
                               f"{'; '.join(mine) or 'none'}.")
    say(f"    New Jersey: 12 House districts and the Senate, {november} candidates on the November ballot (list order; "
        f"{len(left_off)} certified in July and since left off); {fields} party primaries with a field, votes from the official "
        f"results ({checked} candidates, county votes checked against every Total)"
        + (f"; primary winners not on the November list: {', '.join(not_on)}" if not_on else "")
        + (f"; starred as incumbent but not the races table's holder: {', '.join(stars)}" if stars else "")
        + (f"; races with no list: {len(gaps)}" if gaps else ""))
    return november
