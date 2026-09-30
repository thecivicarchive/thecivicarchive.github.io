"""
Nebraska: the Secretary of State's Final Statewide General Candidate List for the November 3, 2026 General Election
(a PDF dated 9/11/2026, linked from sos.nebraska.gov/elections as "Final_Statewide_General_Candidate_Filing_List_...pdf";
the address carries the date, so the page is read first), and the Board of State Canvassers' Official Report of the
May 12, 2026 Primary Election (the canvass book, linked there as "Primary Election Official Results"). Both answer
scripts.

The list is a table printed on its side: every candidate is a strip across the page, and the column headings (Office,
District Name, Term, Vote For, Party, Candidate Name, City of Residence, Incumbency Status, Mailing Address,
Phone/Email) sit in a strip of their own on the left. Each heading's position gives its column's band; a candidate's
strip runs from its Vote For figure to the next one. Only the bands for Office, District Name, Vote For, Party,
Candidate Name and Incumbency Status are turned into text; city of residence, mailing address, phone and e-mail stay
in the file. The list gives no ballot order, so candidates are numbered in the list's own order (by party, as it prints
them). It has no withdrawn or write-in entries. Names and parties are printed as the list prints them; "By Petition"
(a candidate put on the ballot by voters' petition rather than a party's primary) is kept as the label and coloured as
an independent.

The canvass book has, for each federal contest, a table per party: a heading row of candidates (first names on a line
above family names where they wrap), the nominee marked with a check, a Total row and a row per county, sometimes in
two halves side by side, sometimes two parties' tables side by side, sometimes running onto the next page. Every
county column is added up and must equal the printed Total. A party primary becomes a field when two or more names
were on that party's ballot; the checked candidate advanced. The report prints no write-in votes for these contests,
so a field's total is its candidates' votes added together. Legal Marijuana NOW's primaries are stored as
"primary-LMN".
"""

import os
import re
import html as H
from urllib.parse import urljoin

from ballot.common import fold, house_id, party_code, record_source, senate_id
from ballot.pdftext import PDF, join, page_runs, rows as pdf_rows
from states import net

PAGE = "https://sos.nebraska.gov/elections"
PRIMARY = "2026-05-12"
LIST_KEEP = ("Office", "District Name (if applicable)", "Vote For", "Party (if applicable)", "Candidate Name", "Incumbency Status")
CODES = {"Republican": "REP", "Democratic": "DEM", "Libertarian": "LIB", "Legal Marijuana NOW": "LMN"}
TITLE = re.compile(r"^(?P<party>.+?)\s*Party\s*Nomination\s*(?:\((?P<contest>[^)]*)\))?\s*(?P<cont>—\s*continued)?$")
NONE = re.compile(r"^(?P<party>.+?)\s*Party\s*did not make a nomination")
NUMBER = re.compile(r"^\d{1,3}(?:,\d{3})*$")
CHECK = "✓"


def cells(runs):
    """A printed row's pieces grouped into table cells, [(x, runs)]: a gap wider than six points starts the next cell."""
    out = []
    for r in sorted(runs, key=lambda r: r[0]):
        if out and r[0] - out[-1][2] <= 6:
            out[-1][1].append(r)
            out[-1][2] = max(out[-1][2], r[4])
        else:
            out.append([r[0], [r], r[4]])
    return [(x, rs) for x, rs, _end in out]


def links():
    """The addresses of the final candidate list and the primary canvass book, from the 2026 Elections page."""
    page = net.get(PAGE).decode("utf-8", "replace")
    found = {}
    for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', page, re.S | re.I):
        href, label = H.unescape(m.group(1)), re.sub(r"<[^>]+>|\s+", " ", m.group(2)).strip()
        if re.search(r"/Final_Statewide_General_Candidate[^/]*\.pdf$", href, re.I):
            found.setdefault("list", urljoin(PAGE, href))
        elif label == "Primary Election Official Results" and href.lower().endswith(".pdf"):
            found.setdefault("canvass", urljoin(PAGE, href))
    missing = {"list", "canvass"} - set(found)
    if missing:
        raise SystemExit(f"Nebraska: the 2026 Elections page no longer links the {' and the '.join(sorted(missing))} PDF")
    return found


def race_of(office, district):
    if office == "For United States Senator":
        return senate_id("NE", 2)
    if office == "For Representative in Congress":
        m = re.fullmatch(r"District (\d+)", district or "")
        if not m:
            raise SystemExit(f"Nebraska: a candidate for Congress with no district on the list ({district!r})")
        return house_id("NE", int(m.group(1)))
    return None


def general_list(path):
    """(printed date, [(race, party, name, incumbency)]) for the candidates for Congress, in the list's order."""
    pdf = PDF(open(path, "rb").read())
    out, printed, titled = [], "", False
    for page, res in pdf.pages():
        runs = page_runs(pdf, page, res)
        heads = {}
        for x0, y0, _s, t, _x1 in runs:
            if 55 <= x0 < 76 and t.strip():
                heads.setdefault(round(y0), []).append((x0, t.strip()))
            elif x0 < 55 and re.fullmatch(r"\d{1,2}/\d{1,2}/20\d\d", t.strip()) and not printed:
                mo, d, y = t.strip().split("/")
                printed = f"{y}-{int(mo):02d}-{int(d):02d}"
            elif x0 < 55 and "November 3, 2026 General Election" in t:
                titled = True
        fields = sorted((y, " ".join(t for _x, t in sorted(v))) for y, v in heads.items())
        names = [n for _y, n in fields]
        if not all(k in names for k in LIST_KEEP):
            raise SystemExit(f"Nebraska: the candidate list's column headings changed ({names})")
        bands = [(y - 3, (fields[i + 1][0] - 3) if i + 1 < len(fields) else 1e9, n) for i, (y, n) in enumerate(fields)]
        band = lambda y: next((n for lo, hi, n in bands if lo <= y < hi), None)
        starts = sorted({round(x0, 1) for x0, y0, _s, _t, _x1 in runs if x0 >= 76 and band(y0) == "Vote For"})
        for i, sx in enumerate(starts):
            ex = starts[i + 1] if i + 1 < len(starts) else sx + 21
            got = {}
            for x0, y0, _s, t, _x1 in sorted(runs, key=lambda r: (round(r[0], 1), r[1])):
                if sx - 0.5 <= x0 < ex - 0.5:
                    k = band(y0)
                    if k in LIST_KEEP:      # the city, address and phone/e-mail bands are never turned into text
                        got.setdefault(k, []).append(t.strip())
            rec = {k: re.sub(r"\s+", " ", " ".join(v)).strip() for k, v in got.items()}
            race = race_of(rec.get("Office", ""), rec.get("District Name (if applicable)", ""))
            if not race:
                continue
            if rec.get("Vote For") != "1" or not rec.get("Candidate Name") or not rec.get("Party (if applicable)"):
                raise SystemExit(f"Nebraska: a candidate strip for {race} did not read whole")
            out.append((race, rec["Party (if applicable)"], rec["Candidate Name"], rec.get("Incumbency Status", "")))
    if not titled:
        raise SystemExit("Nebraska: the candidate list is no longer the November 3, 2026 General Election")
    return printed, out


def canvass_tables(path):
    """{(race, party): {"names": [(name, checked)], "total": [...], "sum": [...]}} for every party's table in the
    federal section of the canvass book."""
    pdf = PDF(open(path, "rb").read())
    tables, contest, started = {}, None, False
    for page, res in pdf.pages():
        rows = [(y, [(x, rs, join(rs), max(r[4] for r in rs)) for x, rs in cells(runs)]) for y, runs in pdf_rows(pdf, page, res)]
        texts = [" ".join(c[2] for c in cs) for _y, cs in rows]
        if not started:
            started = any(t == "Federal Offices" for t in texts)
            if not started:
                continue
        if any(t == "Statewide Constitutional Offices" for t in texts):
            break
        titles, subs, first = None, None, None
        prev_title = False
        for (y, cs), text in zip(rows, texts):
            if re.search(r"Page \| ?\d+$", text):
                continue
            if text.startswith("Member of the United States Senate"):
                contest, titles, subs = senate_id("NE", 2), None, None
                continue
            m = re.match(r"Congressional District\s*(\d+)\s*–", text)
            if m:
                contest, titles, subs = house_id("NE", int(m.group(1))), None, None
                continue
            got = [TITLE.match(c[2]) for c in cs]
            if any(got):
                if not all(got):
                    raise SystemExit(f"Nebraska: a canvass title row could not be read ({text!r})")
                titles = []
                for g, c in zip(got, cs):
                    race = contest
                    if g.group("contest"):
                        cm = re.fullmatch(r"(United States Senate)|Congressional District (\d+)", g.group("contest").strip())
                        if not cm:
                            raise SystemExit(f"Nebraska: an unknown contest in the canvass book ({g.group('contest')!r})")
                        race = senate_id("NE", 2) if cm.group(1) else house_id("NE", int(cm.group(2)))
                    if not race:
                        raise SystemExit(f"Nebraska: a party's table with no contest heading before it ({text!r})")
                    titles.append(((c[0] + c[3]) / 2, (race, g.group("party").strip()), bool(g.group("cont"))))
                subs, first, prev_title = None, None, True
                continue
            if NONE.match(text):
                titles, subs, prev_title = None, None, False
                continue
            labels = [c for c in cs if c[2] == "County"]
            if labels:
                if not titles:
                    raise SystemExit(f"Nebraska: a canvass table on page with no party heading ({text!r})")
                xs = [c[0] for c in labels]
                subs = []
                for i, x in enumerate(xs):
                    lo, hi = x - 3, (xs[i + 1] - 3) if i + 1 < len(xs) else 1e9
                    heads = [c for c in cs if lo <= c[0] < hi and c[2] != "County"]
                    names = []
                    for c in heads:
                        given = ""
                        if first:
                            over = [(min(c[3], f[3]) - max(c[0], f[0]), f) for f in first if lo <= f[0] < hi]
                            over = [o for o in over if o[0] > 0]
                            if over:
                                given = max(over, key=lambda o: o[0])[1][2]
                        family = c[2]
                        checked = family.endswith(CHECK)
                        names.append((re.sub(r"\s+", " ", f"{given} {family.rstrip(CHECK)}").strip(), checked))
                    subs.append((lo, hi, names))
                if len(titles) == len(subs):
                    keys = [t[1] for t in sorted(titles)]
                elif len(titles) == 1:
                    keys = [titles[0][1]] * len(subs)
                else:
                    raise SystemExit(f"Nebraska: {len(titles)} party headings over {len(subs)} tables ({text!r})")
                subs = [(lo, hi, names, key) for (lo, hi, names), key in zip(subs, keys)]
                for _lo, _hi, names, key in subs:
                    t = tables.setdefault(key, {"names": names, "total": None, "sum": [0] * len(names)})
                    if t["names"] != names:
                        raise SystemExit(f"Nebraska: the canvass table for {key} names different candidates in different places")
                first, prev_title = None, False
                continue
            if prev_title and not any(NUMBER.match(c[2]) for c in cs):
                first, prev_title = cs, False      # first names, on the line above the family names
                continue
            prev_title = False
            if not subs:
                continue
            for lo, hi, names, key in subs:
                part = [c for c in cs if lo <= c[0] < hi]
                if not part:
                    continue
                label, nums = part[0][2], [c[2] for c in part[1:]]
                if not all(NUMBER.match(n) for n in nums) or len(nums) != len(names) or NUMBER.match(label):
                    raise SystemExit(f"Nebraska: a canvass row for {key} does not line up with its candidates ({label!r}, {len(nums)} figures)")
                vals = [int(n.replace(",", "")) for n in nums]
                t = tables[key]
                if label == "Total":
                    if t["total"] is not None:
                        raise SystemExit(f"Nebraska: two Total rows for {key}")
                    t["total"] = vals
                else:
                    t["sum"] = [a + b for a, b in zip(t["sum"], vals)]
    if not tables:
        raise SystemExit("Nebraska: no federal party tables were found in the canvass book")
    for key, t in tables.items():
        if t["total"] is None:
            raise SystemExit(f"Nebraska: no Total row for {key}")
        if t["total"] != t["sum"]:
            raise SystemExit(f"Nebraska: the counties for {key} add up to {t['sum']}, the report's Total is {t['total']}")
        marks = [i for i, (_n, c) in enumerate(t["names"]) if c]
        if len(marks) != 1 or t["total"][marks[0]] != max(t["total"]):
            raise SystemExit(f"Nebraska: the nominee's check mark for {key} is not on the top vote-getter")
    return tables


def load(con, cache, say=print):
    net.patient_lookups()
    url = links()
    folder = os.path.join(cache, "ne")
    os.makedirs(folder, exist_ok=True)
    list_path = os.path.join(folder, "ne_2026_general_candidate_filing_list.pdf")
    book_path = os.path.join(folder, "ne_2026_primary_canvass_book.pdf")
    net.download(url["list"], list_path, max_age_days=2)
    net.download(url["canvass"], book_path, max_age_days=30)
    printed, listed = general_list(list_path)
    held = {r: fold(n) for r, n in con.execute("SELECT race_id, holder_name FROM races WHERE state = 'NE'")}
    for race, _p, name, inc in listed:
        if (inc == "Incumbent") != (held.get(race) == fold(name)):
            raise SystemExit(f"Nebraska: the list's incumbency mark for {name} ({race}) does not agree with who holds the seat")
    rows, order = [], {}
    for race, party, name, _inc in listed:
        order[race] = order.get(race, 0) + 1
        code = "I" if party == "By Petition" else party_code(party)
        rows.append((race, "general", "2026-11-03", name, party, code, order[race], 0, 0, None, None, None, None, None, "ne-sos-2026-general-list", None))
    on_list = {(race, party, fold(name)) for race, party, name, _i in listed}
    tables = canvass_tables(book_path)
    fields = 0
    for (race, party), t in sorted(tables.items()):
        if len(t["names"]) < 2:
            continue
        fields += 1
        code = CODES.get(party) or re.sub(r"[^A-Z]", "", party.upper())[:3]
        total = sum(t["total"])
        for (name, checked), votes in zip(t["names"], t["total"]):
            note = None
            if checked and (race, party, fold(name)) not in on_list:
                note = "Won the nomination; not on the Secretary of State's final list of candidates for November."
            rows.append((race, f"primary-{code}", PRIMARY, name, party, party_code(party), None, 0, 0, votes,
                         round(100 * votes / total, 1) if total else None, "advanced" if checked else "lost",
                         None, None, "ne-sos-2026-primary-canvass", note))
    with con:
        con.execute("DELETE FROM candidates WHERE race_id LIKE '2026-NE-%'")
        con.executemany("INSERT OR REPLACE INTO candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        record_source(con, "ne-sos-2026-general-list", path=list_path, level="federal", state="NE", kind="official candidate list",
                      agency="Nebraska Secretary of State", title="Final Statewide General Candidate List, November 3, 2026 General Election",
                      url=url["list"], published=printed, rows=len(listed),
                      note="Every office; the candidates for Congress read (office, district, party, name, incumbency). City of residence, "
                           "mailing address, phone and e-mail never read. No ballot order is printed: the list's own order is kept. "
                           "The final list has no withdrawn or write-in entries.")
        record_source(con, "ne-sos-2026-primary-canvass", path=book_path, level="federal", state="NE", kind="official results",
                      agency="Nebraska Board of State Canvassers (compiled by the Secretary of State)",
                      title="Official Report of the Board of State Canvassers: Primary Election, May 12, 2026",
                      url=url["canvass"], rows=sum(len(t["names"]) for t in tables.values()),
                      note=f"{len(tables)} party tables for Congress read; every county column added up to the printed Total. The report "
                           "prints no write-in votes for these contests; a field's total is its candidates' votes. The nominee is the one "
                           "the report checks.")
    n = len(listed)
    say(f"    Nebraska: {len({r[0] for r in listed if '-H' in r[0]})} House districts and the Senate race, {n} candidates on the November ballot; "
        f"{fields} party primaries with a field, votes from the official canvass")
    return n
