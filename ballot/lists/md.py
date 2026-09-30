"""
Maryland: the State Board of Elections' own candidate lists and official results (elections.maryland.gov, 2026 page).
Maryland has eight House seats on the 2024 lines and no Senate race in 2026. The gubernatorial primary was held on
June 23, 2026 (the 2026 page's timeline).

  November ballot   the "2026 Gubernatorial General Election State Candidates List" (general_candidates/, "Download
                    Representative in Congress (CSV)"): one row per filing, with the office, the district, the ballot
                    last name and suffix, the first and middle names, the party, the status and the filing type and date.
                    The page's "Last updated" line is read for the date and nothing else from the page is kept.
  primary list      the "2026 Gubernatorial Primary" candidate list, the same CSV for the primary (primary_candidates/),
                    used to check that the results name exactly the Democratic and Republican candidates who were on
                    each district's primary ballot, and to count filings withdrawn before it.
  primary results   the Board's data files for the official primary results (election_data/): the statewide breakdown
                    by congressional district, one CSV per party (GP26_CongressionalBreakDownDemocratic.csv and
                    ...Republican.csv; the "00 State of Maryland" rows, with a Winner mark), checked against every
                    county's own file (GP26_01DemocraticResults.csv ... GP26_24RepublicanResults.csv: the county sums
                    must equal the statewide figures) and against the "Official 2026 Gubernatorial Primary Election
                    Results" page for each district (primary_results/gen_results_2026_4_<d>.html: every candidate's
                    Total and the Totals row). No file carries write-in votes, so a field's total is the sum of its
                    candidates' votes.

The candidate CSVs also carry mailing addresses, phones, e-mail, websites, social accounts, committee names and the
same for any related candidate. Columns are taken by name, only Office Name, Contest Run By District Name and Number,
Candidate Ballot Last Name and Suffix, Candidate First Name and Middle Name, Office Political Party, Candidate Status
and Filing Type and Date; nothing else is read, and the cache (ballot_cache/md/) keeps only those columns for the
Representative in Congress rows, as JSON. The results files are cached as the Board publishes them (results only);
the county files and the results pages are kept as the figures read from them, as JSON.

Names are printed first name first ("John "Johnny O" Olszewski, Jr."), in ordinary capitals, and are shown as the
list prints them: first and middle names, then the ballot last name and suffix. Parties are printed in full on the
lists (Democratic, Republican, Green, Unaffiliated, and "Other Candidates" for a write-in candidate the Board files
that way) and kept as printed; the results files write DEM and REP, read as Democratic and Republican (their results
pages print the same words). The Green Party nominates by its own process ("Party Designated" filings), so only the
Democratic and Republican primaries have fields.

The November ballot is every Representative in Congress row with the status Active. A filing marked withdrawn or
"Failed to Submit Required Number of Signatures" (an independent petition that fell short) is left off and counted;
any other status stops the loader. A row whose filing type is Write-In is a certified write-in candidate: stored with
write_in 1, no ballot position and the note that the name is not printed. The others take ballot positions in the
list's own order, which is the ballot's order (Democratic, Republican, then the other parties; checked by eye against
Montgomery County's certified general ballot for District 8). A party primary is a field when two or more of its
candidates were on the ballot; the Winner mark says who advanced, and it must be the party's candidate on the November
list, or the row says plainly that the nominee is not on it.
"""

import csv
import html as H
import io
import json
import os
import re
import time

from ballot.common import fold, house_id, party_code, record_source
from states import net

BASE = "https://elections.maryland.gov/elections/2026/"
GENERAL_PAGE = BASE + "general_candidates/2026_GG_statewide_candidatelist.html"
GENERAL_CSV = BASE + "general_candidates/2026_GG_representativeincongressbydistrict_candidatelist.csv"
PRIMARY_PAGE = BASE + "primary_candidates/2026_GP_statewide_candidatelist.html"
PRIMARY_CSV = BASE + "primary_candidates/2026_GP_representativeincongressbydistrict_candidatelist.csv"
DATA = BASE + "election_data/"
BREAKDOWN = DATA + "GP26_CongressionalBreakDown{party}.csv"
COUNTY = DATA + "GP26_{cc:02d}{party}Results.csv"
RESULTS_PAGE = BASE + "primary_results/gen_results_2026_4_{d}.html"
PRIMARY = "2026-06-23"
COUNTIES = 24
DISTRICTS = range(1, 9)
KEEP = ("Office Name", "Contest Run By District Name and Number", "Candidate Ballot Last Name and Suffix",
        "Candidate First Name and Middle Name", "Office Political Party", "Candidate Status", "Filing Type and Date")
OFFICE = "Representative in Congress"
OFF = re.compile(r"^(Withdrawn|Failed to Submit|Disqualified|Removed|Deceased|Declined|Ineligible)\b", re.I)
PARTY_OF = {"DEM": "Democratic", "REP": "Republican"}
FILE_PARTY = {"Democratic": "Democratic", "Republican": "Republican"}          # the word in the data files' names
CODE = {"Democratic": "DEM", "Republican": "REP"}
WRITE_IN = "Write-in candidate: the name is not printed on the ballot."


def decode(raw):
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("cp1252", "replace")


def squash(text):
    return re.sub(r"\s+", " ", (text or "").replace("\xa0", " ")).strip()


def district_of(contest):
    m = re.fullmatch(r"Congressional District (\d+)", squash(contest))
    if not m or int(m.group(1)) not in DISTRICTS:
        raise SystemExit(f"Maryland: a Representative in Congress row names a district that is not read ({contest!r})")
    return int(m.group(1))


def last_updated(url):
    """The "Last updated" date printed on a candidate list page (MM/DD/YYYY -> YYYY-MM-DD); nothing else is kept."""
    m = re.search(r"Last updated:\s*(\d\d)/(\d\d)/(\d{4})", decode(net.get(url, accept="text/html")))
    return f"{m.group(3)}-{m.group(1)}-{m.group(2)}" if m else ""


def kept(path, max_age_days, fetch):
    """A small JSON of what is read from a source, refreshed when older than max_age_days."""
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < max_age_days * 86400:
        return json.load(open(path, encoding="utf-8"))
    data = fetch()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(data, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return data


def candidate_list(csv_url, page_url):
    """The Representative in Congress rows of one candidate list CSV, the kept columns only."""
    rows = list(csv.reader(io.StringIO(decode(net.get(csv_url)))))       # the Board answers Accept: text/csv with 406
    heads = [squash(h) for h in rows[0]]
    if not all(k in heads for k in KEEP):
        raise SystemExit(f"Maryland: the candidate list's columns changed ({[k for k in KEEP if k not in heads]} missing)")
    idx = {k: heads.index(k) for k in KEEP}
    out = []
    for r in rows[1:]:
        if not any(c.strip() for c in r):
            continue
        if len(r) < len(heads) - 1:
            raise SystemExit("Maryland: a candidate list row does not line up with its headings")
        row = {k: squash(r[i]) for k, i in idx.items()}
        if row["Office Name"] != OFFICE:
            raise SystemExit(f"Maryland: the Representative in Congress list carries another office ({row['Office Name']!r})")
        out.append(row)
    time.sleep(1.5)
    return {"url": csv_url, "published": last_updated(page_url), "rows": out}


def name_of(row):
    return squash(f"{row['Candidate First Name and Middle Name']} {row['Candidate Ballot Last Name and Suffix']}")


def ints(cell):
    t = squash(cell).replace(",", "")
    return int(t) if t else 0


def csv_rows(raw):
    rows = list(csv.reader(io.StringIO(decode(raw))))
    heads = [squash(h) for h in rows[0]]
    return heads, [r for r in rows[1:] if any(c.strip() for c in r)]


def statewide(path):
    """{(district, party): {name: (votes, winner)}} from the "00 State of Maryland" U.S. Congress rows of a breakdown file."""
    heads, rows = csv_rows(open(path, "rb").read())
    need = ("County", "Office Name", "Office District", "Candidate Name", "Party", "Winner") + tuple(f"Congressional District {d}" for d in DISTRICTS)
    if not all(k in heads for k in need):
        raise SystemExit(f"Maryland: the congressional breakdown file's columns changed ({[k for k in need if k not in heads]} missing)")
    idx = {k: heads.index(k) for k in need}
    out = {}
    for r in rows:
        if squash(r[idx["Office Name"]]) != "U.S. Congress" or squash(r[idx["County"]]) != "00":
            continue
        d, code = int(r[idx["Office District"]]), squash(r[idx["Party"]])
        if code not in PARTY_OF:
            raise SystemExit(f"Maryland: a party code in the results that is not read ({code!r})")
        cols = {k: ints(r[idx[f"Congressional District {k}"]]) for k in DISTRICTS}
        if any(v for k, v in cols.items() if k != d):
            raise SystemExit(f"Maryland: a District {d} candidate has votes filed under another district in the breakdown file")
        name = squash(r[idx["Candidate Name"]])
        cell = out.setdefault((d, PARTY_OF[code]), {})
        if name in cell:
            raise SystemExit(f"Maryland: {name} is listed twice in the District {d} {code} results")
        cell[name] = (cols[d], squash(r[idx["Winner"]]).upper() == "Y")
    return out


def county_sums(say):
    """{"<district>|<party>|<name>": votes} summed over the 24 county files, and how many counties had rows."""
    sums, counted = {}, {}
    for party in FILE_PARTY.values():
        for cc in range(1, COUNTIES + 1):
            url = COUNTY.format(cc=cc, party=party)
            raw = net.get(url)
            heads, rows = csv_rows(raw)
            need = ("Office Name", "Office District", "Candidate Name", "Party", "Total Votes")
            if not all(k in heads for k in need):
                raise SystemExit(f"Maryland: {url.rsplit('/', 1)[1]}'s columns changed ({[k for k in need if k not in heads]} missing)")
            idx = {k: heads.index(k) for k in need}
            for r in rows:
                if squash(r[idx["Office Name"]]) != "U.S. Congress":
                    continue
                code = squash(r[idx["Party"]])
                if PARTY_OF.get(code) != party:
                    raise SystemExit(f"Maryland: the {party} file for county {cc:02d} carries a {code!r} row")
                key = f"{int(r[idx['Office District']])}|{party}|{squash(r[idx['Candidate Name']])}"
                sums[key] = sums.get(key, 0) + ints(r[idx["Total Votes"]])
                counted.setdefault(party, set()).add(cc)
            time.sleep(1.0)
    say(f"      county results: {COUNTIES * len(FILE_PARTY)} files read")
    return {"sums": sums, "counties": {p: len(v) for p, v in counted.items()}}


def results_pages(say):
    """{"<district>|<party>|<name>": total} and {"<district>|<party>": Totals row} from the official results pages."""
    totals, sums, refreshed = {}, {}, ""
    for d in DISTRICTS:
        page = decode(net.get(RESULTS_PAGE.format(d=d), accept="text/html"))
        if "Official 2026 Gubernatorial Primary Election Results" not in page:
            raise SystemExit(f"Maryland: {RESULTS_PAGE.format(d=d)} is no longer the official primary results page")
        m = re.search(r"Last refreshed:\s*(\d\d)/(\d\d)/(\d{4})", page)
        if m and not refreshed:
            refreshed = f"{m.group(3)}-{m.group(1)}-{m.group(2)}"
        heads = party = None
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", page, re.S):
            cells = [squash(H.unescape(re.sub(r"<[^>]+>", " ", c))) for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", tr, re.S)]
            if cells and cells[0] == "Name":
                heads = cells
                continue
            if not heads or len(cells) != len(heads):
                continue
            row = dict(zip(heads, cells))
            if row["Name"] == "Totals":
                if party is None:
                    raise SystemExit(f"Maryland: a Totals row with no candidates above it on the District {d} results page")
                sums[f"{d}|{party}"] = ints(row["Total"])
                heads = party = None
                continue
            party = row["Party"]
            if party not in FILE_PARTY:
                raise SystemExit(f"Maryland: a party on the District {d} results page that is not read ({party!r})")
            totals[f"{d}|{party}|{row['Name']}"] = ints(row["Total"])
        time.sleep(1.0)
    say(f"      official results pages: {len(DISTRICTS)} districts read")
    return {"refreshed": refreshed, "totals": totals, "sums": sums}


def load(con, cache, say=print):
    net.patient_lookups()
    folder = os.path.join(cache, "md")
    gpath = os.path.join(folder, "md_2026_general_congress.json")
    ppath = os.path.join(folder, "md_2026_primary_congress.json")
    general = kept(gpath, 2, lambda: candidate_list(GENERAL_CSV, GENERAL_PAGE))
    primary = kept(ppath, 30, lambda: candidate_list(PRIMARY_CSV, PRIMARY_PAGE))

    rows, off, write_ins, order, nominee, seen = [], [], [], {}, {}, set()
    for r in general["rows"]:
        d = district_of(r["Contest Run By District Name and Number"])
        race, status, filing, party_name = house_id("MD", d), r["Candidate Status"], r["Filing Type and Date"], r["Office Political Party"]
        name = name_of(r)
        if OFF.match(status):
            off.append(f"{name} (District {d}, {status.split(' - ')[0]})")
            continue
        if status != "Active":
            raise SystemExit(f"Maryland: a status on the general list that is not read ({status!r}, District {d})")
        if not party_name:
            raise SystemExit(f"Maryland: a candidate for District {d} with no party on the list")
        if (race, fold(name)) in seen:
            raise SystemExit(f"Maryland: {name} is on the District {d} list twice as Active")
        seen.add((race, fold(name)))
        if filing.startswith("Write-In"):
            write_ins.append(name)
            rows.append((race, "general", "2026-11-03", name, party_name, party_code(party_name), None, 0, 1, None, None, None, None, None,
                         "md-sbe-2026-general-list", WRITE_IN))
            continue
        if not re.match(r"(Federal|Party Designated|Petition)\b", filing):
            raise SystemExit(f"Maryland: a filing type on the general list that is not read ({filing!r}, District {d})")
        if party_name in CODE:
            if (d, party_name) in nominee:
                raise SystemExit(f"Maryland: two {party_name} candidates printed for District {d}")
            nominee[(d, party_name)] = fold(name)
        order[race] = order.get(race, 0) + 1
        rows.append((race, "general", "2026-11-03", name, party_name, party_code(party_name), order[race], 0, 0, None, None, None, None, None,
                     "md-sbe-2026-general-list", None))
    missing = [d for d in DISTRICTS if house_id("MD", d) not in order]
    if missing:
        raise SystemExit(f"Maryland: no printed candidates read for districts {missing}")

    # who was on each party's June ballot, from the primary list
    on_ballot, withdrew = {}, []
    for r in primary["rows"]:
        d, party_name, status = district_of(r["Contest Run By District Name and Number"]), r["Office Political Party"], r["Candidate Status"]
        if party_name not in CODE:
            continue                                  # Green nominees, independents' petitions and write-ins are not in a primary
        if OFF.match(status):
            withdrew.append(f"{name_of(r)} ({party_name}, District {d})")
        elif status == "Active":
            on_ballot.setdefault((d, party_name), set()).add(name_of(r))
        else:
            raise SystemExit(f"Maryland: a status on the primary list that is not read ({status!r}, District {d})")

    # the official results: statewide, the counties' sums, and the results pages
    books = {}
    for party_name, word in FILE_PARTY.items():
        books[party_name] = os.path.join(folder, f"GP26_CongressionalBreakDown{word}.csv")
        net.download(BREAKDOWN.format(party=word), books[party_name], max_age_days=30, say=say)
        if open(books[party_name], "rb").read(64).lstrip(b"\xef\xbb\xbf").lstrip()[:1] not in (b'"', b"C"):
            raise SystemExit(f"Maryland: {os.path.basename(books[party_name])} is not the Board's results file")
    votes = {}
    for party_name, path in books.items():
        for key, cands in statewide(path).items():
            if key[1] != party_name:
                raise SystemExit(f"Maryland: the {party_name} breakdown file carries a {key[1]} row")
            votes[key] = cands
    cpath = os.path.join(folder, "md_2026_primary_county_congress.json")
    rpath = os.path.join(folder, "md_2026_primary_results_pages.json")
    counties = kept(cpath, 30, lambda: county_sums(say))
    pages = kept(rpath, 30, lambda: results_pages(say))

    checked = 0
    for (d, party_name), cands in votes.items():
        if set(cands) != on_ballot.get((d, party_name), set()):
            raise SystemExit(f"Maryland: the District {d} {party_name} results do not name the primary list's candidates "
                             f"({sorted(set(cands) ^ on_ballot.get((d, party_name), set()))})")
        for name, (v, _w) in cands.items():
            key = f"{d}|{party_name}|{name}"
            if counties["sums"].get(key) != v:
                raise SystemExit(f"Maryland: {name} (District {d}, {party_name}): the counties sum to {counties['sums'].get(key)}, "
                                 f"the statewide file says {v}")
            if pages["totals"].get(key) != v:
                raise SystemExit(f"Maryland: {name} (District {d}, {party_name}): the results page says {pages['totals'].get(key)}, "
                                 f"the statewide file says {v}")
            checked += 1
        if pages["sums"].get(f"{d}|{party_name}") != sum(v for v, _w in cands.values()):
            raise SystemExit(f"Maryland: the District {d} {party_name} Totals row does not equal the sum of its candidates")
    known = {f"{d}|{p}|{n}" for (d, p), cands in votes.items() for n in cands}
    extra = (set(counties["sums"]) | set(pages["totals"])) - known
    if extra or set(on_ballot) - set(votes):
        raise SystemExit(f"Maryland: results read in one file and not another ({sorted(extra)[:5]}, {sorted(set(on_ballot) - set(votes))})")

    fields, not_on = 0, []
    for (d, party_name), cands in sorted(votes.items()):
        if len(cands) < 2:
            continue
        winners = [n for n, (_v, w) in cands.items() if w]
        if len(winners) != 1:
            raise SystemExit(f"Maryland: the District {d} {party_name} primary has {len(winners)} winners marked")
        fields += 1
        total = sum(v for v, _w in cands.values())
        for name, (v, w) in sorted(cands.items(), key=lambda kv: (-kv[1][0], kv[0])):
            note = None
            if w and nominee.get((d, party_name)) != fold(name):
                note = "Won the primary but is not on the November list."
                not_on.append(f"{name} (District {d}, {party_name})")
            rows.append((house_id("MD", d), f"primary-{CODE[party_name]}", PRIMARY, name, party_name, party_code(party_name), None, 0, 0,
                         v, round(100 * v / total, 1) if total else None, "advanced" if w else "lost", None, None,
                         "md-sbe-2026-primary-statewide", note))

    general_rows = [r for r in rows if r[1] == "general"]
    with con:
        con.execute("DELETE FROM candidates WHERE race_id LIKE '2026-MD-%'")
        con.executemany("INSERT OR REPLACE INTO candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        record_source(con, "md-sbe-2026-general-list", path=gpath, level="federal", state="MD", kind="official candidate list",
                      agency="Maryland State Board of Elections",
                      title="2026 Gubernatorial General Election State Candidates List: Representative in Congress (CSV)",
                      url=GENERAL_CSV, published=general.get("published", ""), rows=len(general["rows"]),
                      note=f"Seven columns read by name (office, district, names, party, status, filing type); addresses, phones, e-mail, "
                           f"websites, social accounts and committee names never read. Ballot order is the list's own order. Withdrawn or "
                           f"failed petition, left off: {len(off)} ({'; '.join(off) or 'none'}). Certified write-in candidates: "
                           f"{len(write_ins)} ({', '.join(write_ins) or 'none'}).")
        record_source(con, "md-sbe-2026-primary-list", path=ppath, level="federal", state="MD", kind="official candidate list",
                      agency="Maryland State Board of Elections",
                      title="2026 Gubernatorial Primary Candidate List: Representative in Congress (CSV)",
                      url=PRIMARY_CSV, published=primary.get("published", ""), rows=len(primary["rows"]),
                      note="Used to check the results: each district's Democratic and Republican candidates marked Active must be exactly "
                           f"the candidates in the results. Democratic and Republican filings withdrawn before the June 23 primary "
                           f"(some refiled for another district or party): {'; '.join(withdrew) or 'none'}.")
        for party_name, path in books.items():
            record_source(con, f"md-sbe-2026-primary-statewide-{CODE[party_name].lower()}", path=path, level="federal", state="MD",
                          kind="official results", agency="Maryland State Board of Elections",
                          title=f"2026 Gubernatorial Primary Election (June 23, 2026), statewide breakdown by congressional district, {party_name}",
                          url=BREAKDOWN.format(party=FILE_PARTY[party_name]),
                          rows=sum(len(c) for k, c in votes.items() if k[1] == party_name),
                          note="The U.S. Congress rows for the State of Maryland (county 00), with the Board's Winner mark. The file carries no "
                               "write-in votes, so a field's total is the sum of its candidates' votes.")
        record_source(con, "md-sbe-2026-primary-counties", path=cpath, level="federal", state="MD", kind="official results",
                      agency="Maryland State Board of Elections",
                      title="2026 Gubernatorial Primary Election, results by county (GP26_01 to GP26_24, Democratic and Republican)",
                      url=COUNTY.format(cc=1, party="Democratic").replace("01Democratic", "<county><party>"), rows=len(counties["sums"]),
                      note=f"Control: the U.S. Congress rows of all {COUNTIES} counties' files, summed per candidate, equal the statewide figures "
                           f"({checked} candidates checked).")
        record_source(con, "md-sbe-2026-primary-results-pages", path=rpath, level="federal", state="MD", kind="official results",
                      agency="Maryland State Board of Elections",
                      title="Official 2026 Gubernatorial Primary Election Results: Representative in Congress, Districts 1 to 8",
                      url=RESULTS_PAGE.format(d="<district>"), published=pages.get("refreshed", ""), rows=len(pages["totals"]),
                      note="Control: every candidate's Total on the official results pages equals the data files' figure, and each "
                           "party's Totals row equals the sum of its candidates.")
    say(f"    Maryland: 8 House districts (no Senate race in 2026), {len(general_rows)} candidates on the November ballot "
        f"({len(write_ins)} certified write-in, {len(off)} withdrawn or failed petitions left off); {fields} party primaries with a field, "
        f"votes from the official results, county sums and results pages checked"
        + (f"; primary winners not on the November list: {', '.join(not_on)}" if not_on else ""))
    return len(general_rows)
