"""
California: the Secretary of State's Statement of Vote for the June 2, 2026 primary, in its machine-readable form
("CSV Files - Voter Nominated", an .xlsx with one row per county, contest and candidate: name, party preference,
incumbent and write-in flags, votes). The county rows are added up to district totals here.

California's primary is top-two: every candidate, of every party preference, is on one primary ballot, and the two
who receive the most votes advance to the November general election, whatever their parties (a tie for second
advances everyone tied). So the primary field is every candidate with their votes, and the November ballot is the
top two.

The November ballot is then checked against the Secretary's Certified List of Candidates for the November 3, 2026
General Election (a PDF linked as "Certified List of Candidates" from the Secretary's page for that election; the
Secretary's certificate on its first page is dated at Sacramento, and every later page repeats the title, the date and
"Page n of N"). Each office is headed in 14-point type centred on the page; under it each candidate takes two rows of
9-point type: the name (with * for an incumbent, "* Incumbent" in the footer) at the left edge and the party preference
in a column to the right, then the ballot designation on the row beneath, indented. The list prints no column headings,
so the two columns' left edges are found from the rows themselves (the pair of places where the name and the party
preference start again and again). Besides the headings, the page titles and the certificate's date, only those two
cells of the name rows under "United States Representative District n" and "United States Senator" are turned into
text; the ballot designation rows and the rows of every other office are never joined. Race by race, the certified names are compared with the Statement of Vote's top two by family name and
party preference. Where they agree the rows stay as they are and name the certified list as their source; where they
differ (a withdrawal, a replacement, a spelling) the certified list is what the ballot prints, so its names are used,
the rows say so, and a check line names the difference. The primary rows are the Statement of Vote's either way.
"""

import collections
import datetime as dt
import os
import re

import openpyxl

from ballot.common import GENERAL, fold, house_id, name_parts, party_code, record_source
from ballot.pdftext import PDF, join, rows as pdf_rows
from states import net

URL = "https://elections.cdn.sos.ca.gov/sov/2026-primary/sov/csv-voter-nominated.xlsx"
PAGE = "https://www.sos.ca.gov/elections/prior-elections/statewide-election-results/primary-election-june-2-2026/statement-vote"
CERT = "https://elections.cdn.sos.ca.gov/statewide-elections/2026-general/cert-list-candidates.pdf"
CERT_PAGE = "https://www.sos.ca.gov/elections/upcoming-elections/general-election-november-3-2026"
PRIMARY = "2026-06-02"
CERT_ID = "ca-cert-2026-general"
FEDERAL = re.compile(r"^United States (?:Representative District (?P<d>\d+)|(?P<s>Senator))$")
MONTHS = {m: i for i, m in enumerate(("January", "February", "March", "April", "May", "June", "July", "August", "September",
                                      "October", "November", "December"), start=1)}


def cells(runs):
    """A printed row's pieces grouped into cells: [(x, pieces)]; a gap wider than six points starts the next cell."""
    out = []
    for r in sorted(runs, key=lambda r: r[0]):
        if out and r[0] - out[-1][2] <= 6:
            out[-1][1].append(r)
            out[-1][2] = max(out[-1][2], r[4])
        else:
            out.append([r[0], [r], r[4]])
    return [(x, rs) for x, rs, _end in out]


def certified(path):
    """(title, published, {race: [(name, party preference, incumbent)]}, problems) from the Certified List of Candidates;
    a United States Senator section, if there is one, is filed under "senate". Only the name and party preference cells of
    the rows under a federal office's heading are turned into text."""
    pdf = PDF(open(path, "rb").read())
    pages = pdf.pages()
    if len(pages) < 2:
        raise SystemExit("California: the Certified List of Candidates has no pages after its certificate")
    # the certificate (page 1): "Dated at Sacramento, California, this 27th day of August, 2026."
    cover = " ".join(join(rs) for _y, rs in pdf_rows(pdf, *pages[0]))
    m = re.search(r"Dated at Sacramento, California, this (\d{1,2})\s*(?:st|nd|rd|th)? day of ([A-Z][a-z]+), (\d{4})", cover)
    dated = dt.date(int(m.group(3)), MONTHS[m.group(2)], int(m.group(1))).isoformat() if m and m.group(2) in MONTHS else ""
    # every later page opens at the left margin with the title, its second line, the date and "Page n of N"
    top = [join(rs) for _y, rs in pdf_rows(pdf, *pages[1]) if min(r[0] for r in rs) < 50][:4]
    if len(top) < 4 or not re.fullmatch(r"\d{1,2}/\d{1,2}/\d{4}", top[2]) or not top[3].startswith("Page "):
        raise SystemExit("California: the Certified List of Candidates' page heading was not found where it was")
    mo, day, yr = (int(x) for x in top[2].split("/"))
    published = dt.date(yr, mo, day).isoformat()
    title = f"{top[1]}, {top[0]}"
    problems = [] if dated in ("", published) else [f"the certificate is dated {dated} and the pages {published}"]
    if not dated:
        problems.append("the certificate's date was not read")
    # the body: every 9-point row, filed under the 14-point heading above it
    body, office = [], None
    for page, res in pages[1:]:
        for _y, rs in pdf_rows(pdf, page, res):
            if min(r[0] for r in rs) < 50:      # title, date, page number and the footer: page furniture
                continue
            size = max(r[2] for r in rs)
            if size >= 13:
                office = join(rs)      # an office's heading
            elif 8.5 <= size <= 9.5:
                body.append((office, cells(rs)))
    pairs = collections.Counter((round(row[0][0]), round(row[-1][0])) for _o, row in body if len(row) == 2)
    if not pairs:
        raise SystemExit("California: no row of the Certified List of Candidates has a name and a party preference")
    name_x, party_x = pairs.most_common(1)[0][0]
    out, odd = collections.defaultdict(list), collections.Counter()
    for office, row in body:
        m = FEDERAL.match(office or "")
        if not m:
            continue      # another office: nothing on its rows is turned into text
        race = house_id("CA", int(m.group("d"))) if m.group("d") else "senate"
        if abs(row[0][0] - name_x) <= 1.5 and len(row) == 2 and abs(row[1][0] - party_x) <= 1.5:
            name = join(row[0][1])
            out[race].append((name.rstrip("* ").strip(), join(row[1][1]), name.endswith("*")))
        elif row[0][0] - name_x > 4 and all(abs(x - party_x) > 1.5 for x, _rs in row):
            continue      # the ballot designation beneath a name: never turned into text
        else:
            odd[office] += 1
    problems += [f"{n} row(s) under {o} were neither a name nor a ballot designation (not read)" for o, n in sorted(odd.items())]
    return title, published, dict(out), problems


def load(con, cache, say=print):
    path = os.path.join(cache, "ca_sov_2026_primary_voter_nominated.xlsx")
    net.download(URL, path, max_age_days=60)
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    it = wb.worksheets[0].iter_rows(values_only=True)
    head = next(it)
    field = collections.defaultdict(dict)      # district -> candidate id -> [name, party, incumbent, write-in, votes]
    for r in it:
        rec = dict(zip(head, r))
        contest = str(rec.get("Contest Name") or "")
        if not contest.startswith("United States Representative District "):
            continue
        d = int(contest.rsplit(" ", 1)[1])
        c = field[d].setdefault(rec["Candidate ID"], [str(rec["Candidate Name"]).strip(), (rec["Party Name"] or "").strip(),
                                                      rec["Incumbent Flag"] == "Y", rec["Write-in Flag"] == "Y", 0])
        c[4] += int(rec["Vote Total"] or 0)
    rows = []
    for d, cands in sorted(field.items()):
        ranked = sorted(cands.values(), key=lambda c: (-c[4], c[0]))
        total = sum(c[4] for c in ranked) or 1
        second = ranked[1][4] if len(ranked) > 1 else ranked[0][4]
        for c in ranked:
            went = c[4] >= second
            rows.append((house_id("CA", d), "primary", PRIMARY, c[0], c[1], party_code(c[1]), None, int(c[2]), int(c[3]),
                         c[4], round(100 * c[4] / total, 2), "advanced" if went else "lost", None, None, "ca-sov-2026-primary", None))
            if went:
                rows.append((house_id("CA", d), "general", GENERAL, c[0], c[1], party_code(c[1]), None, int(c[2]), int(c[3]),
                             None, None, None, None, None, "ca-sov-2026-primary",
                             "Advanced from the June 2 top-two primary. California prints each candidate's party preference."))
    # the November ballot, checked against the Secretary's Certified List of Candidates
    cert_path = os.path.join(cache, "ca_cert_list_2026_general.pdf")
    net.download(CERT, cert_path, max_age_days=30)
    title, published, cert, checks = certified(cert_path)
    when = dt.date.fromisoformat(published).strftime("%B %d, %Y").replace(" 0", " ")
    primary = [r for r in rows if r[1] == "primary"]
    general, agree, differ = check_general(rows, cert, field, when, checks)
    senate = cert.pop("senate", None)
    if senate:
        checks.append(f"the certified list has a United States Senator section ({len(senate)} candidate{"s" if len(senate) != 1 else ""}), but races.py has no "
                      "California Senate race this year: not loaded")
    rows = primary + general
    districts = len({house_id("CA", d) for d in field} | {r[0] for r in general})
    missing = sorted({r[0] for r in general if r[14] != CERT_ID})
    with con:
        con.execute("DELETE FROM candidates WHERE race_id LIKE '2026-CA-%'")
        con.executemany("INSERT OR REPLACE INTO candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        record_source(con, "ca-sov-2026-primary", path=path, level="federal", state="CA", kind="official results",
                      agency="California Secretary of State", title="Statement of Vote, June 2, 2026 Primary Election: CSV Files - Voter Nominated",
                      url=URL, rows=len(primary),
                      note=f"Found on {PAGE}. County rows added up to district totals.")
        record_source(con, CERT_ID, path=cert_path, level="federal", state="CA", kind="official candidate list",
                      agency="California Secretary of State", title=title, url=CERT, published=published,
                      rows=sum(1 for r in general if r[14] == CERT_ID),
                      note=(f"Found on {CERT_PAGE} as \"Certified List of Candidates\"; the Secretary's certificate is dated "
                            f"at Sacramento, {when}. Only the names and party preferences under \"United States Representative\" "
                            + ("and \"United States Senator\" " if senate else "(there is no United States Senator section this year) ")
                            + "are read; ballot designations are not. They are checked race by race against the top two of the "
                            f"June 2 Statement of Vote by family name and party preference: {agree} of {districts} districts agree"
                            + (f"; where they differ ({', '.join(differ)}) the certified list is what the ballot prints, so its names "
                               "are used" if differ else "")
                            + (f"; {', '.join(missing)} not found on the certified list, so the Statement of Vote's top two are kept "
                               "there" if missing else "") + "."))
    for c in checks:
        say(f"      check: {c}")
    say(f"    California: {len(field)} House districts, {len(primary)} primary candidates, {len(general)} on the November ballot; "
        f"the Certified List of Candidates ({when}) agrees with the Statement of Vote's top two in {agree} of {districts} districts")
    return len(field)


def key(name, party):
    """What the two lists are compared by: the family name and the party preference, folded."""
    return name_parts(name)[1], fold(party)


def check_general(rows, cert, field, when, checks):
    """(November rows, districts that agree, [races that differ]). Where the certified list and the Statement of Vote's top
    two agree, the Statement of Vote's rows are kept and name the certified list as their source; where they differ, the
    certified list's names are used, each row says why, and a check line names the difference."""
    sov = collections.defaultdict(list)
    for r in rows:
        if r[1] == "general":
            sov[r[0]].append(r)
    ranked = {house_id("CA", d): sorted(c.values(), key=lambda c: (-c[4], c[0])) for d, c in field.items()}
    say_list = lambda cands: "; ".join(f"{n} ({p})" for n, p in cands)
    out, agree, differ = [], 0, []
    for race in sorted(set(sov) | {k for k in cert if k != "senate"}):
        old, new = sov.get(race, []), cert.get(race, [])
        if not new:
            checks.append(f"{race}: not on the certified list; the Statement of Vote's top two are kept "
                          f"({say_list((r[3], r[4]) for r in old)})")
            out += old
            continue
        if sorted(key(r[3], r[4]) for r in old) == sorted(key(n, p) for n, p, _i in new):
            agree += 1
            out += [r[:14] + (CERT_ID,) + r[15:] for r in old]
            continue
        differ.append(race)
        was = say_list((r[3], r[4]) for r in old) or "nobody"
        gone = [r for r in old if key(r[3], r[4]) not in {key(n, p) for n, p, _i in new}]
        why = []
        for n, p, inc in new:
            same = next((r for r in old if key(r[3], r[4]) == key(n, p)), None)
            if same:
                note = (f"Advanced from the June 2 top-two primary; named as the Secretary of State's Certified List of Candidates "
                        f"({when}) prints it.")
            else:
                spelt = next((r for r in gone if fold(r[4]) == fold(p) and name_parts(r[3])[0][:1] == name_parts(n)[0][:1]), None)
                place = next((k for k, c in enumerate(ranked.get(race, []), start=1) if key(c[0], c[1]) == key(n, p)), None)
                if spelt:
                    gone.remove(spelt)
                    note = (f"Advanced from the June 2 top-two primary, where the Statement of Vote spells the name {spelt[3]}; the "
                            f"Secretary of State's Certified List of Candidates ({when}) spells it {n}, and the ballot follows the "
                            "certified list.")
                    why.append(f"{spelt[3]} is spelled {n}")
                else:
                    instead = gone.pop(0) if gone else None
                    note = ((f"Placed {place}{'th' if 10 <= place % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(place % 10, 'th')} in "
                             "the June 2 top-two primary" if place else "Not in the June 2 Statement of Vote for this district")
                            + f"; the Secretary of State's Certified List of Candidates ({when}) names this candidate for November"
                            + (f" in place of {instead[3]} ({instead[4]})" if instead else "") + ", and the ballot follows the certified list.")
                    why.append(f"{n} ({p}) " + (f"in place of {instead[3]} ({instead[4]})" if instead else "added"))
            out.append((race, "general", GENERAL, n, p, party_code(p), None, int(inc), 0, None, None, None, None, None, CERT_ID,
                        note + f" The June 2 Statement of Vote's top two here were {was}. California prints each candidate's "
                        "party preference."))
        why += [f"{r[3]} ({r[4]}) is not on the certified list" for r in gone]
        checks.append(f"{race}: the Statement of Vote's top two were {was}; the certified list prints "
                      f"{say_list((n, p) for n, p, _i in new)} ({'; '.join(why) or 'the same people, named differently'})")
    return out, agree, differ
