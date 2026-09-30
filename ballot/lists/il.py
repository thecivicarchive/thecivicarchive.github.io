"""
Illinois: the State Board of Elections' Website Candidate List for the General Election of November 3, 2026 (the
"Print This List" PDF of the election's Candidate List page, every office, "All Candidates as of" the moment it is
printed), read with ballot/pdftext.py. Under each office, one line per candidate: party, name, filing date and time.
Candidates who filed by petition as independents or new parties have their address on the next lines; a candidate
the Board removed or who withdrew is marked there ("REMOVED 7/21/2026"). Addresses are never kept; removed and
withdrawn candidates are left off the November ballot.

The March 17, 2026 General Primary comes from the Board's "Official Canvass, General Primary Election, March 17, 2026"
(2026GPOfficialVote.pdf, linked as "Candidate Totals" on the Board's Downloadable Vote Totals page for 2026), read with
ballot/pdftext.py's parts. Each office and district opens with a summary: one line per candidate, "(Won)" before each
party's nominee, the name in capitals, the party's short code (DEM, REP, WCP), the statewide votes and the share of the
party's vote, and "W-I" after a declared write-in candidate, whose votes the canvass counts. A long name runs on to the
next line. County tables follow, up to five candidates a band, each band headed by a row of party codes and a row of
family names; the bands' codes must follow the summary's candidates in order, every band must list the same counties
(all 102 for the Senate), and each candidate's county rows must add up to the summary's total. The canvass's text puts
letters so close that a space can vanish ("BUSHRAAMIWALA"), so the summary lines are joined with a finer gap than
pdftext's, and every name and total is checked against the Board's own Election Results page for the primary
(ElectionVoteTotals.aspx, Federal / Statewide: candidate, party and total votes only; its share column is not read),
whose spelling is used where the two agree letter for letter.

A field is a party primary with two candidates or more printed on that party's ballot; write-in votes count toward its
total and a declared write-in is shown as one. The canvass's "(Won)" must be the field's top vote-getter and the one on
the November list for that party; that person advanced. Names are printed in capitals and shown in ordinary capitals
(the nominee as the November list spells them), and the rows say so. Both files answer scripts.
"""

import html as H
import json
import os
import re
import time

from ballot.common import house_id, name_parts, party_code, record_source, senate_id
from ballot.lists.ky import created
from ballot.lists.tx import proper
from ballot.pdftext import PDF, lines, rows as pdf_rows
from states import net

PAGE = "https://elections.il.gov/ElectionOperations/CandidateList.aspx?ElectionID=sejIrI%2bQmww%3d"
URL = ("https://elections.il.gov/ElectionOperations/EOPDFViewer.aspx?ElectionID=sejIrI%2bQmww%3d"
       "&QueryType=xF443FTCAJbIL3atac%2fUjEg7Y4yklgT1&Status=P2wRQXkiFoo%3d")
CAND = re.compile(r"^(?P<rest>.+?) (?P<date>\d{1,2}/\d{1,2}/\d{4}) \d{1,2}:\d\d ?[AP]M$")

PRIMARY = "2026-03-17"
SENATE = senate_id("IL", 2)
TOTALS_PAGE = "https://www.elections.il.gov/ElectionOperations/DownloadVoteTotals.aspx"
CANVASS_URL = ("https://elections.il.gov/NewDocDisplay.aspx?khDtbt6dhc8zLboSZnz8zqVh5SQVox7uAOAe2nieWDAlNyd4%2btjArHsz9xVXIJ4p6Y57u3Fv"
               "Ww0%2bgnNWdT3uKyV44EJPSNKJqSNPoTMrt%2fmA2Vga9kq1ZX6%2f0lBROK1DmIXy%2fEucNyaXZqwll6ndvejVr6lkKL1sYsp9%2bSoVxwaiQnLwAg2b4"
               "luOIfhlfUOEBRcbFpfKMR3bLc4VhWFcPamR2xaYTSdw")
RESULTS_URL = ("https://www.elections.il.gov/ElectionOperations/ElectionVoteTotals.aspx?ID=Z2J%2fvYpKX8w%3d"
               "&OfficeType=LpWf6lpbWOfBN3kEuxRi3A%3d%3d")
ORDINALS = ("FIRST", "SECOND", "THIRD", "FOURTH", "FIFTH", "SIXTH", "SEVENTH", "EIGHTH", "NINTH", "TENTH", "ELEVENTH",
            "TWELFTH", "THIRTEENTH", "FOURTEENTH", "FIFTEENTH", "SIXTEENTH", "SEVENTEENTH")
SUMMARY = re.compile(r"^(?P<won>\(Won\) )?(?P<name>.+?) (?P<code>[A-Z]{2,5}) (?P<votes>\d{1,3}(?:,\d{3})*) "
                     r"(?P<pct>< \.01|\d{1,3}\.\d\d)%(?P<wi> W-I)?$")
COUNTY_ROW = re.compile(r"^(?P<county>[A-Za-z][A-Za-z. ]*?)(?P<nums>(?: \d{1,3}(?:,\d{3})*)+)$")
NAME_PART = re.compile(r"^[A-Z][A-Z .,'\"()-]*$")
PARTY_WORD = {"DEM": "Democratic", "REP": "Republican"}      # as the November list prints them
COUNTIES = 102
WRITE_IN = "Write-in candidate: the name is not printed on the ballot."
CAPS = "Illinois's official canvass prints names in capitals; they are shown here in ordinary capitals."
NOT_ON_LIST = "Won the primary, but is not on the November list for this party."


def split_party(rest):
    """DEMOCRATIC La Shawn K. Ford -> (DEMOCRATIC, La Shawn K. Ford): the party is the words before the first word
    with a small letter in it."""
    words = rest.split()
    k = next((i for i, w in enumerate(words) if re.search(r"[a-z]", w)), None)
    if not k:
        return None, None
    return " ".join(words[:k]), " ".join(words[k:])


# ---------- the March 17 primary ----------

def tight_join(runs):
    """pdftext.join with a finer gap: in the canvass a space before a narrow letter can be less than a fifth of the type
    wide, while letters of one word never stand more than a twentieth apart."""
    text, end = "", None
    for x0, _y, size, t, x1 in sorted(runs, key=lambda r: r[0]):
        if end is not None and x0 - end > 0.1 * size and not text.endswith(" ") and not t.startswith(" "):
            text += " "
        text += t
        end = max(end or x1, x1)
    return re.sub(r"\s+", " ", text).strip()


def canvass_lines(path):
    pdf = PDF(open(path, "rb").read())
    for n, (page, res) in enumerate(pdf.pages(), start=1):
        for y, rs in pdf_rows(pdf, page, res):
            text = tight_join(rs)
            if text:
                yield n, y, text


def canvass(path):
    """{race: {"cands": [{name, code, votes, pct, won, wi}], "bands": [{codes, head, rows: {county: [votes]}}]}} for the
    Senate and the House, and the problems found reading it (an empty list when every check holds)."""
    cover, headings, sections, problems = "", set(), {}, []
    office = sec = pending = None
    after_cand = False
    for page, _y, t in canvass_lines(path):
        if page == 1:
            cover += " " + t
            continue
        if page == 3 and re.search(r"(?:\. ?){5,}", t):      # the table of contents: every office's heading
            headings.add(re.sub(r"\s*(?:\. ?){5,}.*$", "", t).strip().upper())
            continue
        if t in headings:
            office = "S" if t == "UNITED STATES SENATOR" else "H" if t == "REPRESENTATIVE IN CONGRESS" else None
            sec = sections.setdefault(SENATE, {"cands": [], "bands": []}) if office == "S" else None
            pending, after_cand = None, False
            continue
        if office is None:
            continue
        m = re.fullmatch(r"([A-Z]+) CONGRESSIONAL DISTRICT", t)
        if office == "H" and m:
            if m.group(1) not in ORDINALS:
                problems.append(f"a district heading not read: {t}")
                sec = None
                continue
            sec = sections.setdefault(house_id("IL", ORDINALS.index(m.group(1)) + 1), {"cands": [], "bands": []})
            pending, after_cand = None, False
            continue
        if sec is None:
            continue
        m = SUMMARY.match(t)
        if m and not sec["bands"]:
            sec["cands"].append({"name": m.group("name"), "code": m.group("code"), "votes": int(m.group("votes").replace(",", "")),
                                 "pct": 0.0 if m.group("pct").startswith("<") else float(m.group("pct")),
                                 "small": m.group("pct").startswith("<"), "won": bool(m.group("won")), "wi": bool(m.group("wi"))})
            after_cand = True
            continue
        words = t.split()
        codes = {c["code"] for c in sec["cands"]}
        if codes and all(w in codes for w in words):
            pending, after_cand = words, False
            continue
        if t.startswith("COUNTY ") and pending:
            head = (tuple(pending), t)
            if not sec["bands"] or sec["bands"][-1]["head"] != head:
                sec["bands"].append({"head": head, "codes": pending, "rows": {}})
            pending = None
            continue
        if after_cand and NAME_PART.match(t):
            sec["cands"][-1]["name"] += " " + t      # a long name runs on to the next line
            continue
        after_cand = False
        m = COUNTY_ROW.match(t)
        if m and sec["bands"]:
            band = sec["bands"][-1]
            nums = [int(x.replace(",", "")) for x in m.group("nums").split()]
            if len(nums) != len(band["codes"]):
                problems.append(f"a county row with {len(nums)} numbers under a band of {len(band['codes'])}: {m.group('county')}")
                continue
            if m.group("county") in band["rows"]:      # the next band has the same heading
                band = {"head": band["head"], "codes": band["codes"], "rows": {}}
                sec["bands"].append(band)
            band["rows"][m.group("county")] = nums
    if not re.search(r"OFFICIAL CANVASS", cover) or not re.search(r"General Primary Election", cover) or "March 17, 2026" not in cover:
        raise SystemExit("Illinois: the primary file is no longer the Official Canvass of the March 17, 2026 General Primary")
    if not {"UNITED STATES SENATOR", "REPRESENTATIVE IN CONGRESS"} <= headings:
        raise SystemExit("Illinois: the canvass's table of contents no longer names the Senate and the House")
    for race, s in sorted(sections.items()):
        seq = [code for b in s["bands"] for code in b["codes"]]
        if seq != [c["code"] for c in s["cands"]]:
            problems.append(f"{race}: the county tables' party codes {seq} do not follow the summary's candidates")
            continue
        counties = [sorted(b["rows"]) for b in s["bands"]]
        if any(c != counties[0] for c in counties):
            problems.append(f"{race}: the county tables' bands do not list the same counties")
        if race == SENATE and len(counties[0]) != COUNTIES:
            problems.append(f"{race}: {len(counties[0])} counties listed, not {COUNTIES}")
        k = 0
        for b in s["bands"]:
            for j in range(len(b["codes"])):
                summed = sum(v[j] for v in b["rows"].values())
                if summed != s["cands"][k]["votes"]:
                    problems.append(f"{race}: {s['cands'][k]['name']}'s county rows add to {summed:,}, the summary says {s['cands'][k]['votes']:,}")
                k += 1
        for code in {c["code"] for c in s["cands"]}:
            mine = [c for c in s["cands"] if c["code"] == code]
            total = sum(c["votes"] for c in mine)
            for c in mine:
                share = 100 * c["votes"] / total if total else 0
                if (c["small"] and share >= 0.01) or (not c["small"] and abs(share - c["pct"]) > 0.006):
                    problems.append(f"{race} {code}: {c['name']}'s printed share {c['pct']}% is not {share:.2f}% of the party's votes")
    expected = {SENATE} | {house_id("IL", d) for d in range(1, 18)}
    if set(sections) != expected:
        problems.append(f"the canvass covers {sorted(sections)}, not the Senate and the 17 districts")
    return sections, problems


def text_of(cell):
    return re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", cell)).replace("\xa0", " ")).strip()


def results_page(path):
    """{race: [[name, party, votes]]} from the Board's Election Results page for the primary (kept on disk for 30 days:
    those three columns only, for the Senate and the House)."""
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < 30 * 86400:
        return json.load(open(path, encoding="utf-8"))
    page = net.get(RESULTS_URL, accept="text/html").decode("utf-8", "replace")
    chosen = re.search(r'<option selected="selected" value="[^"]*">([^<]*)</option>', page)
    if not chosen or chosen.group(1).strip() != "2026 GENERAL PRIMARY":
        raise SystemExit("Illinois: the Election Results page is no longer the 2026 General Primary's")
    out = {}
    for m in re.finditer(r'<asp:Label runat="server"[^>]*>([^<]*)</asp:Label>(.*?)(?=<asp:Label runat="server"|$)', page, re.S):
        office = m.group(1).strip()
        d = re.fullmatch(r"(\d{1,2})(?:ST|ND|RD|TH) CONGRESS", office)
        race = SENATE if office == "UNITED STATES SENATOR" else house_id("IL", int(d.group(1))) if d else None
        if not race:
            continue
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", m.group(2), re.S):
            tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
            if len(tds) != 4 or text_of(tds[0]) == "Vote Totals":
                continue
            out.setdefault(race, []).append([text_of(tds[0]), text_of(tds[1]), int(text_of(tds[2]).replace(",", "") or 0)])
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump({"url": RESULTS_URL, "election": "2026 GENERAL PRIMARY", "columns": ["Candidate", "Party", "Total Votes"], "rows": out},
              open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return json.load(open(path, encoding="utf-8"))


def made_on(path):
    """The PDF's own creation date: its Info dictionary's, else its XMP metadata's (xmp:CreateDate 2026-04-16T...)."""
    got = created(path)
    if got:
        return got
    m = re.search(rb"<xmp:CreateDate>(\d{4}-\d\d-\d\d)", open(path, "rb").read())
    return m.group(1).decode() if m else ""


def letters(name):
    return re.sub(r"[^A-Z0-9]", "", name.upper())


def shown(printed):
    """ROBIN KELLY -> Robin Kelly; DARIN LaHOOD -> Darin LaHood (a small letter the canvass prints is kept); initials in
    quotes ("PJK") as printed."""
    words, fixed = printed.split(), proper(printed).split()
    out = []
    for w, f in zip(words, fixed):
        m = re.fullmatch(r"([A-Z][a-z]+)([A-Z]{2}.*)", w)
        if m:
            f = m.group(1) + proper(m.group(2))
        elif re.fullmatch(r"\"[B-DF-HJ-NP-TV-Z]{2,4}\"", w):
            f = w
        out.append(f)
    return re.sub(r"(['\"(])([a-z])", lambda m: m.group(1) + m.group(2).upper(), " ".join(out))


def same_person(a, b):
    ga, fa = name_parts(re.sub(r'"[^"]*"', " ", a))
    gb, fb = name_parts(re.sub(r'"[^"]*"', " ", b))
    return bool(fa == fb and ga and gb and (ga[0] == gb[0] or set(ga) & set(gb) or ga[0][0] == gb[0][0]))


def primary_rows(cache, nominee, say):
    """The primary's rows, the files read, and what to say about them."""
    folder = os.path.join(cache, "il")
    cpath = os.path.join(folder, "il_2026_primary_official_canvass.pdf")
    net.download(CANVASS_URL, cpath, max_age_days=90, say=say)
    if not open(cpath, "rb").read(5).startswith(b"%PDF"):
        raise SystemExit("Illinois: the Official Canvass downloaded is not a PDF; read the Downloadable Vote Totals page again")
    sections, problems = canvass(cpath)
    rpath = os.path.join(folder, "il_2026_primary_results_federal.json")
    try:
        page = results_page(rpath)["rows"]
    except Exception as e:  # noqa: BLE001  the check waits; the canvass alone is the record
        say(f"      Illinois: the Election Results page was not read ({e}); names are the canvass's own")
        page, rpath = None, None
    respelled, unmatched = 0, []
    if page is not None:
        for race, s in sections.items():
            theirs = page.get(race, [])
            if len(theirs) != len(s["cands"]):
                unmatched.append(f"{race}: the canvass lists {len(s['cands'])} candidates, the results page {len(theirs)}")
                continue
            for c in s["cands"]:
                hit = [r for r in theirs if letters(r[0]) == letters(c["name"])]
                word = hit[0][1].upper() if len(hit) == 1 else ""
                if len(hit) != 1 or hit[0][2] != c["votes"] or not (word.startswith(c["code"][:3]) or "".join(w[0] for w in word.split()) == c["code"]):
                    unmatched.append(f"{race}: {c['name']} {c['code']} {c['votes']:,} is not on the results page as printed")
                    continue
                if hit[0][0] != c["name"]:
                    c["name"] = hit[0][0]
                    respelled += 1
    rows, fields, upset, lone = [], 0, [], []
    for race, s in sorted(sections.items()):
        for code in sorted({c["code"] for c in s["cands"]}):
            mine = [c for c in s["cands"] if c["code"] == code]
            printed = [c for c in mine if not c["wi"]]
            if len(printed) < 2:
                if len(mine) > 1:
                    lone.append(f"{race} {code}")
                continue
            if code not in PARTY_WORD:
                raise SystemExit(f"Illinois: a {code} primary with a field for {race}; its election code and party name are not set")
            fields += 1
            party = PARTY_WORD[code]
            total = sum(c["votes"] for c in mine)
            won = [c for c in mine if c["won"]]
            top = max(mine, key=lambda c: c["votes"])
            if len(won) != 1 or won[0] is not top or sum(1 for c in mine if c["votes"] == top["votes"]) > 1:
                problems.append(f"{race} {code}: the canvass's (Won) mark is not on the one top vote-getter")
            listed = nominee.get((race, party))
            winner = won[0] if len(won) == 1 else top
            if listed and not same_person(winner["name"], listed):
                upset.append(f"{race} {code}: the canvass's winner is {winner['name']}; the November list names {listed}")
            for c in mine:
                notes = [WRITE_IN] if c["wi"] else []
                if c is winner and listed and same_person(c["name"], listed):
                    name = listed      # the nominee as the November list spells the name
                else:
                    name = shown(c["name"])
                    notes.append(CAPS)
                if c is winner and not listed:
                    notes.append(NOT_ON_LIST)
                elif c is winner and not same_person(c["name"], listed):
                    notes.append(f"Won the primary; the November list names {listed} as the party's candidate instead.")
                rows.append((race, f"primary-{code}", PRIMARY, name, party, party_code(party), None, 0, int(c["wi"]), c["votes"],
                             round(100 * c["votes"] / total, 1) if total else None, "advanced" if c is winner else "lost",
                             None, None, "il-sbe-2026-primary-canvass", " ".join(notes) or None))
    info = {"cpath": cpath, "rpath": rpath, "fields": fields, "problems": problems, "unmatched": unmatched, "upset": upset,
            "lone": lone, "respelled": respelled, "cands": sum(len(s["cands"]) for s in sections.values())}
    return rows, info


def load(con, cache, say=print):
    path = os.path.join(cache, "il_2026_general_candidate_list.pdf")
    net.patient_lookups()
    net.download(URL, path, max_age_days=2)
    office, out, removed = None, [], []
    for page, y, text in lines(path):
        if re.fullmatch(r"UNITED STATES SENATOR", text):
            office = ("S", 2)
            continue
        m = re.fullmatch(r"(\d+)(ST|ND|RD|TH) CONGRESS", text)
        if m:
            office = ("H", int(m.group(1)))
            continue
        if re.fullmatch(r"[0-9A-Z ,.&'()-]+", text) and not CAND.match(text) and not re.search(r"\d{1,2}/\d{1,2}/\d{4}", text):
            if re.search(r"SENATE|REPRESENTATIVE|GOVERNOR|ATTORNEY|SECRETARY|COMPTROLLER|TREASURER|CIRCUIT|SUPREME|APPELLATE|JUDGE|DISTRICT", text):
                office = None      # the next office's heading
            continue
        if office is None:
            continue
        if re.search(r"\b(REMOVED|WITHDRAWN|DISQUALIFIED)\b", text):      # on the address line under a candidate
            if out:
                removed.append(out.pop())
            continue
        if re.match(r"^\d", text):      # an address line
            continue
        m = CAND.match(text)
        if m:
            party, name = split_party(m.group("rest"))
            if party and name:
                race = senate_id("IL", 2) if office[0] == "S" else house_id("IL", office[1])
                out.append([race, party.title(), name])
            continue
    rows = [(race, "general", "2026-11-03", name, party, party_code(party), None, 0, 0, None, None, None, None, None, "il-sbe-2026-candidate-list", None)
            for race, party, name in out]
    nominee = {}
    for race, party, name in out:
        if party in PARTY_WORD.values():
            if (race, party) in nominee:
                raise SystemExit(f"Illinois: two {party} candidates for {race} on the November list")
            nominee[(race, party)] = name
    try:
        prows, info = primary_rows(cache, nominee, say)
    except (OSError, ValueError) as e:      # the canvass could not be fetched: the November list still loads
        say(f"    Illinois: the primary's Official Canvass was not read ({e}); primaries wait")
        prows, info = [], None
    with con:
        con.execute("DELETE FROM candidates WHERE race_id LIKE '2026-IL-%'")
        con.executemany("INSERT OR REPLACE INTO candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows + prows)
        record_source(con, "il-sbe-2026-candidate-list", path=path, level="federal", state="IL", kind="official candidate list",
                      agency="Illinois State Board of Elections", title="Website Candidate List, General Election November 3, 2026 (all candidates as printed)",
                      url=URL, rows=len(rows), note=f"The Candidate List page's Print This List. Removed or withdrawn, left off: {len(removed)}. Addresses not kept.")
        if info:
            record_source(con, "il-sbe-2026-primary-canvass", path=info["cpath"], level="federal", state="IL", kind="official results",
                          agency="Illinois State Board of Elections",
                          title="Official Canvass, General Primary Election, March 17, 2026 (2026GPOfficialVote.pdf, Candidate Totals)",
                          url=CANVASS_URL, published=made_on(info["cpath"]), rows=info["cands"],
                          note=f"Linked as \"Candidate Totals\" on {TOTALS_PAGE} (year 2026). The United States Senator and Representative in "
                               f"Congress sections: each candidate's statewide votes, the (Won) mark and W-I for declared write-ins (their votes "
                               f"count toward a field's total). Each candidate's county rows checked against the summary. The date given is the "
                               f"file's own creation date. "
                               + ("Every check holds." if not info["problems"] else "Did not hold: " + "; ".join(info["problems"]) + ".")
                               + (f" One-candidate primaries with only write-ins beside, not fields: {', '.join(info['lone'])}." if info["lone"] else ""))
            if info["rpath"]:
                record_source(con, "il-sbe-2026-primary-results-page", path=info["rpath"], level="federal", state="IL", kind="official results",
                              agency="Illinois State Board of Elections",
                              title="Election Results, 2026 General Primary: Federal / Statewide (Election Vote Totals)",
                              url=RESULTS_URL, rows=sum(len(v) for v in json.load(open(info["rpath"], encoding="utf-8"))["rows"].values()),
                              note="Candidate, party and total votes for the Senate and the House, kept to check the canvass's names and totals; "
                                   "the share column is not read. Names spelled as this page spells them where the two agree letter for letter "
                                   f"(the canvass's text runs some words together): {info['respelled']} respelled. "
                                   + ("Every candidate agrees." if not info["unmatched"] else "Did not agree: " + "; ".join(info["unmatched"]) + "."))
    tail = f"; {info['fields']} party primaries with a field, votes from the official canvass" if info else ""
    say(f"    Illinois: {len({r[0] for r in rows if '-H' in r[0]})} House districts and {'the' if any('-S' in r[0] for r in rows) else 'no'} Senate race, "
        f"{len(rows)} candidates on the November ballot ({len(removed)} removed or withdrawn left off){tail}")
    if info:
        for p in info["problems"] + info["unmatched"] + info["upset"]:
            say(f"      check: {p}")
    return len(rows)
