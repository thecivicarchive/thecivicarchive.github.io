"""
ballot/state_local_md.py - Maryland's state races on the November 3, 2026 ballot: all 47 seats of the State Senate and
all 141 seats of the House of Delegates (71 districts and subdistricts, electing one, two or three delegates each), the
Governor and Lieutenant Governor (one ticket), the Comptroller and the Attorney General, the Circuit Court judgeships
contested this year and the two appellate judges standing for continuance in office, with the June 23 Democratic and
Republican primaries and their official votes. Maryland elects its whole General Assembly and its statewide officers
together, every four years, in the Governor's year; the State Board's list names every seat. Written into
ballot_local_2026.sqlite (never ballot_2026.sqlite), Maryland's rows only.

Sources, all the State Board of Elections' own (elections.maryland.gov, 2026 page), and the same kind the federal loader
(ballot/lists/md.py) reads for Congress:
  - The "2026 Gubernatorial General Election State Candidates List" (general_candidates/, "Download (CSV)", the
    statewide file holding every state office and Congress): one row per filing. Columns are taken by their headings,
    and only these are read: Office Name, Contest Run By District Name and Number, Candidate Ballot Last Name and Suffix,
    Candidate First Name and Middle Name, Office Political Party, Candidate Status, Filing Type and Date, and, for the
    Governor's ticket, Has Related Candidate and the related candidate's names, party and status. The file also carries
    mailing addresses, phones, e-mail, websites, social accounts, committee names, county of residence and gender, for
    both candidates of a ticket: none of those is ever read, printed or kept. The file is never saved; only the read
    cells go to ballot_cache/md/sl_md_2026_general_statewide_list.json, with the file's SHA-256. The page's "Last
    updated" date is read and nothing else from the page is kept.
  - The "2026 Gubernatorial Primary" candidate list, the same statewide CSV for the primary (primary_candidates/), read
    and kept the same way: it says who was on each party's June ballot, and the results must name exactly those people.
  - The official primary results: the statewide breakdown by legislative district, one CSV per party
    (election_data/GP26_LegislativeBreakDownDemocratic.csv and ...Republican.csv): the "00 State of Maryland" rows for
    the statewide and legislative offices and each county's rows for the Circuit Court, with the Board's Winner mark.
    Controls: every county's own results file (GP26_01DemocraticResults.csv ... GP26_24RepublicanResults.csv) summed per
    candidate must equal the breakdown, and so must every candidate's Total on the "Official 2026 Gubernatorial Primary
    Election Results" pages (primary_results/gen_results_2026_*.html), whose Totals rows must equal the sum of their
    candidates. The results pages also give each contest's "Vote for" number, which is how many seats a House of
    Delegates district or a county's Circuit Court contest fills. No file carries write-in votes, so a field's total is
    the sum of its candidates' votes. Results files are cached as the Board publishes them (names and votes only); the
    county files and the results pages are kept as the figures read from them, as JSON.
  - Who holds each seat today, from state_md.sqlite (the Open States roster the state pages use): sitting legislators
    by chamber and district, and the statewide officials it carries (Governor, Lieutenant Governor, Attorney General; it
    carries no Comptroller and no judges). Only ids, names, parties, chambers, districts and offices are selected.
  - The Census Bureau's cartographic county file (cb_2024_us_county_500k, already in states_cache/census/), for the
    county GEOID of each Circuit Court contest: names and GEOIDs only.

What is stored. A race per seat or contest: 2026-MD-SS<district> (State Senator), 2026-MD-SH<district> (House of
Delegates, the district as the Board writes it: 1A, 12B, 23), 2026-MD-GOV, 2026-MD-COMP, 2026-MD-AG, 2026-MD-CC-<county
GEOID> (Judge of the Circuit Court, one contest per county, voters choosing as many as there are seats) and
2026-MD-SCRET-<family name> / 2026-MD-COARET-<family name> (a retention vote; Maryland calls it continuance in office).
The November candidates are every row marked Active. A row marked Withdrawn, Declined (a nominee who turned the
nomination down), Failed to Submit Required Number of Signatures (an independent petition that fell short),
Disqualified or Deceased is left off and counted; any other status stops the loader. A row whose filing type is
Write-In is a certified write-in candidate: stored with write_in 1, no ballot position and the note that the name is not
printed. The others take ballot positions in the list's own order within each contest, as on the federal side; the
loader checks that the order is the pattern Maryland's ballots follow (Democratic, then Republican, then the other
parties, each alphabetical by surname; judges alphabetical) and reports any contest that departs from it, which is then
stored with no ballot order. Parties are printed in full on the list and kept as printed ("Judicial" filings are stored
as "Nonpartisan office"); the Governor's running mate is named in the row's note.

A party's primary is stored as a field when more of its candidates were on the ballot than the contest could send on
(two or more for a one-seat contest; more than the "Vote for" number elsewhere). The Winner mark says who advanced; the
winners must be the top vote-getters, and a winner who is not on the November list (declined, withdrew) is noted, as is a
November candidate named later by a central committee. Circuit Court candidates run in both the Democratic and the
Republican primary whatever their own party, and win a place on the November ballot by winning either; their primary
rows are stored under the primary they ran in, with "Nonpartisan office" as the party.

A candidate is the incumbent (incumbent 1, state_member_id) only when the name fits exactly one sitting member of the same
chamber and district, and that member fits only that candidate; a statewide officer the same way. A sitting legislator
running for another office is given their roster id (not incumbent) when the name fits exactly one legislator of the same
party. A judge standing for continuance is by definition the sitting judge of that seat, so that one name is the holder.

    python -m ballot.state_local_md <path to a test database>
"""

import csv
import datetime as dt
import hashlib
import html as H
import io
import json
import os
import re
import sqlite3
import sys
import time
import zipfile
from urllib.error import HTTPError

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from ballot.common import CACHE, fold, name_parts, party_code  # noqa: E402
from ballot.lists import md as MD  # noqa: E402
from ballot.match import fits  # noqa: E402
from states import net  # noqa: E402

STATE, FIPS = "MD", "24"
GENERAL, PRIMARY = "2026-11-03", MD.PRIMARY
ROSTER = os.path.join(HERE, "state_md.sqlite")
COUNTY_ZIP = os.path.join(HERE, "states_cache", "census", "cb_2024_us_county_500k.zip")
COUNTY_URL = "https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_county_500k.zip"

GENERAL_PAGE = MD.GENERAL_PAGE
GENERAL_CSV = MD.BASE + "general_candidates/2026_GG_statewide_candidatelist.csv"
PRIMARY_PAGE = MD.PRIMARY_PAGE
PRIMARY_CSV = MD.BASE + "primary_candidates/2026_GP_statewide_candidatelist.csv"
BREAKDOWN = MD.DATA + "GP26_LegislativeBreakDown{party}.csv"
COUNTY_FILE = MD.DATA + "GP26_{cc:02d}{party}Results.csv"
RESULTS = MD.BASE + "primary_results/"
RESULTS_INDEX = RESULTS + "index.html"

SRC_GEN, SRC_PRI = "md-sbe-2026-sl-general-list", "md-sbe-2026-sl-primary-list"
SRC_BOOK = "md-sbe-2026-sl-primary-breakdown-{p}"
SRC_COUNTIES, SRC_PAGES = "md-sbe-2026-sl-primary-counties", "md-sbe-2026-sl-primary-results-pages"
SRC_ROSTER, SRC_CENSUS = "md-openstates-roster", "md-census-cb-2024-county"
GEN_FILE, PRI_FILE = "sl_md_2026_general_statewide_list.json", "sl_md_2026_primary_statewide_list.json"
COUNTY_JSON, PAGES_JSON = "sl_md_2026_primary_county_state.json", "sl_md_2026_primary_results_pages_state.json"

SCHEMA = """
CREATE TABLE IF NOT EXISTS sl_races (race_id TEXT PRIMARY KEY, state TEXT NOT NULL, level TEXT NOT NULL, office_kind TEXT NOT NULL,
  office TEXT NOT NULL, jurisdiction TEXT, jurisdiction_id TEXT, county_ids TEXT, district TEXT, seat TEXT, special INTEGER NOT NULL DEFAULT 0,
  partisan INTEGER NOT NULL, holder_id TEXT, holder_name TEXT, holder_party TEXT, election_date TEXT NOT NULL, note TEXT);
CREATE TABLE IF NOT EXISTS sl_candidates (race_id TEXT NOT NULL, election TEXT NOT NULL, election_date TEXT, name TEXT NOT NULL, party TEXT,
  party_code TEXT, ballot_order INTEGER, incumbent INTEGER NOT NULL DEFAULT 0, write_in INTEGER NOT NULL DEFAULT 0, votes INTEGER, pct REAL,
  outcome TEXT, state_member_id TEXT, source_id TEXT, note TEXT, PRIMARY KEY (race_id, election, name));
CREATE TABLE IF NOT EXISTS sl_sources (source_id TEXT PRIMARY KEY, state TEXT, kind TEXT, agency TEXT, title TEXT, url TEXT, published TEXT,
  fetched TEXT, sha256 TEXT, rows INTEGER, note TEXT);
CREATE TABLE IF NOT EXISTS sl_places (kind TEXT NOT NULL, id TEXT NOT NULL, name TEXT NOT NULL, county_ids TEXT, source_id TEXT,
  PRIMARY KEY (kind, id));
"""

# The only columns ever read from a candidate list; the related candidate's are read only on a Governor's row.
KEEP = ("Office Name", "Contest Run By District Name and Number", "Candidate Ballot Last Name and Suffix",
        "Candidate First Name and Middle Name", "Office Political Party", "Candidate Status", "Filing Type and Date")
RELATED = ("Has Related Candidate", "Related Candidate Last Name and Suffix", "Related Candidate First Name and Middle Name",
           "Related Office Political Party", "Related Candidate Status")
GOV, COMP, AG = "Governor / Lt. Governor", "Comptroller", "Attorney General"
SENATE, HOUSE, CIRCUIT = "State Senator", "House of Delegates", "Judge of the Circuit Court"
SUPREME, APPELLATE = "Justice Supreme Court of Maryland", "Judge Appellate Court of Maryland At Large"
CONGRESS = "Representative in Congress"
LOADED = (GOV, COMP, AG, SENATE, HOUSE, CIRCUIT, SUPREME, APPELLATE)
# the office names in the results files, and the list's names they stand for
RESULT_OFFICE = {"Governor / Lt. Governor": GOV, "Comptroller": COMP, "Attorney General": AG, "State Senator": SENATE,
                 "House of Delegates": HOUSE, "Judge Circuit Court": CIRCUIT}
PAGE_OFFICE = {"Governor / Lt. Governor": GOV, "Comptroller": COMP, "Attorney General": AG, "State Senator": SENATE,
               "House of Delegates": HOUSE, "Judge of the Circuit Court": CIRCUIT}
PARTY_OF = MD.PARTY_OF                                                            # DEM, REP -> Democratic, Republican
CODE = MD.CODE                                                                    # Democratic -> DEM
FILE_PARTY = MD.FILE_PARTY
OFF = MD.OFF
NONPARTISAN = "Nonpartisan office"
WRITE_IN = MD.WRITE_IN
SENATE_SEATS, HOUSE_SEATS, HOUSE_DISTRICTS = 47, 141, 71
NUMBER_WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten"}

SENATE_NOTE = ("Maryland elects its whole Senate every four years, with the Governor; all 47 legislative districts elect a senator "
               "on the 2026 ballot.")
GOV_NOTE = ("The Governor and Lieutenant Governor are elected together, one ticket to a party, in the primary as in November; the "
            "State Board's list names each ticket's candidate for Lieutenant Governor on the Governor's row.")
COMP_NOTE = "The Open States roster this site uses does not carry the Comptroller, so today's holder is not shown."
CIRCUIT_NOTE = ("A nonpartisan office: no party is printed on the November ballot. Circuit Court candidates run in both the Democratic "
                "and the Republican primary whatever their own party, and a candidate who wins either primary is on the November "
                "ballot. The Open States roster does not carry judges, so no holder is shown.")
RETENTION_NOTE = ("A retention vote: voters answer For or Against continuing this judge in office (Maryland calls it continuance in "
                  "office). No party is printed.")
ORDER_NOTE = ("Ballot order is the State Board's list's own order (Democratic, then Republican, then the other parties, each "
              "alphabetical by surname), as on the federal side; certified write-in candidates are not printed.")


# ------------------------------------------------------------------------------------------------ fetching and caching

def fetch(url, accept="*/*", say=print):
    """One request, asked at most twice more on a refusal or a server error (never past a challenge page)."""
    for attempt in range(3):
        try:
            raw = net.get(url, accept=accept)
        except HTTPError as e:
            if e.code not in (403, 429, 500, 502, 503, 504) or attempt == 2:
                raise
            say(f"      {url.rsplit('/', 1)[1]}: HTTP {e.code}; asking again in {10 * (attempt + 1)} s")
            time.sleep(10 * (attempt + 1))
            continue
        head = raw[:4000].lower()
        if b"captcha" in head or b"challenge-platform" in head or b"incapsula" in head:
            raise SystemExit(f"Maryland (state races): {url} answered with a bot check; it was not worked around. A person in a "
                             "browser would have to fetch it.")
        return raw


def fresh(path, days):
    return os.path.exists(path) and time.time() - os.path.getmtime(path) < days * 86400


def kept(path, max_age_days, make):
    """A small JSON of what is read from a source, refreshed when older than max_age_days; on a failed refresh the older
    copy is used."""
    if fresh(path, max_age_days):
        return json.load(open(path, encoding="utf-8"))
    try:
        data = make()
    except (HTTPError, OSError) as e:
        if os.path.exists(path):
            print(f"      could not refresh {os.path.basename(path)} ({e}); using the copy read earlier")
            return json.load(open(path, encoding="utf-8"))
        raise
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(data, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return data


def candidate_list(csv_url, page_url, say):
    """The kept cells of every row of a statewide candidate list CSV, and the file's SHA-256. The file itself is held
    in memory only; the columns outside KEEP and RELATED are never turned into text."""
    raw = fetch(csv_url, say=say)
    rows = list(csv.reader(io.StringIO(MD.decode(raw))))
    heads = [MD.squash(h) for h in rows[0]]
    need = KEEP + RELATED
    if not all(k in heads for k in need):
        raise SystemExit(f"Maryland (state races): the candidate list's columns changed ({[k for k in need if k not in heads]} missing)")
    idx = {k: heads.index(k) for k in need}
    out = []
    for r in rows[1:]:
        if not any(c.strip() for c in r):
            continue
        if len(r) < len(heads) - 1:
            raise SystemExit("Maryland (state races): a candidate list row does not line up with its headings")
        row = {k: MD.squash(r[idx[k]]) for k in KEEP}
        if row["Office Name"] == GOV:
            row.update({k: MD.squash(r[idx[k]]) for k in RELATED})
        out.append(row)
    time.sleep(1.5)
    try:
        published = MD.last_updated(page_url)
    except (HTTPError, OSError):
        published = ""
    return {"url": csv_url, "published": published, "fetched": dt.date.today().isoformat(),
            "sha256": hashlib.sha256(raw).hexdigest(), "rows": out}


def county_sums(say):
    """{"<office>|<district or county>|<party>|<name>": votes} over the 24 counties' own results files (state offices only)."""
    sums, files = {}, 0
    need = ("Office Name", "Office District", "Candidate Name", "Party", "Total Votes")
    for party in FILE_PARTY.values():
        for cc in range(1, MD.COUNTIES + 1):
            url = COUNTY_FILE.format(cc=cc, party=party)
            heads, rows = MD.csv_rows(fetch(url, say=say))
            if not all(k in heads for k in need):
                raise SystemExit(f"Maryland (state races): {url.rsplit('/', 1)[1]}'s columns changed ({[k for k in need if k not in heads]} missing)")
            idx = {k: heads.index(k) for k in need}
            for r in rows:
                office = RESULT_OFFICE.get(MD.squash(r[idx["Office Name"]]))
                if not office:
                    continue
                code = MD.squash(r[idx["Party"]])
                if PARTY_OF.get(code) != party:
                    raise SystemExit(f"Maryland (state races): the {party} file for county {cc:02d} carries a {code!r} row")
                where = f"{cc:02d}" if office == CIRCUIT else district_norm(r[idx["Office District"]]) if office in (SENATE, HOUSE) else ""
                key = f"{office}|{where}|{party}|{bare_name(MD.squash(r[idx['Candidate Name']]))[0]}"
                sums[key] = sums.get(key, 0) + MD.ints(r[idx["Total Votes"]])
            files += 1
            time.sleep(1.0)
    say(f"      county results: {files} files read")
    return {"files": files, "sums": sums}


def page_list(say):
    """The official results pages for the state offices, from the results index: 1-3 (statewide), 5_n (State Senator),
    6_n (House of Delegates), 7_n (Judge of the Circuit Court)."""
    raw = MD.decode(fetch(RESULTS_INDEX, accept="text/html", say=say))
    names = sorted(set(re.findall(r"gen_results_2026_(?:[123]|[567]_\d+)\.html", raw)),
                   key=lambda n: [int(x) for x in re.findall(r"\d+", n)[1:]])
    if not names:
        raise SystemExit("Maryland (state races): the primary results index lists no results pages")
    return names


RESIDENCE = re.compile(r"^(.*\S)\s+\((?:[A-Z][A-Za-z.' ]+ County|Baltimore City)\)$")


def bare_name(name):
    """(name, True) with the county of residence the results print after a name in a district that limits delegates per
    county taken off (it is never kept or printed), else (name, False)."""
    m = RESIDENCE.match(name)
    return (m.group(1), True) if m else (name, False)


def cell_text(c):
    return MD.squash(H.unescape(re.sub(r"<[^>]+>", " ", c)))


def page_figures(raw, name):
    """[{office, where, party, vote_for, totals: {name: total}, sum}] from one official results page (names and votes only)."""
    page = MD.decode(raw)
    if "Official 2026 Gubernatorial Primary Election Results" not in page:
        raise SystemExit(f"Maryland (state races): {name} is no longer the official primary results page")
    refreshed = re.search(r"Last refreshed:\s*(\d\d)/(\d\d)/(\d{4})", page)
    body = page[page.find("divRefreshResults"):]
    heads, out, cur, cols = [], [], None, None
    for m in re.finditer(r"<h(\d)[^>]*>(.*?)</h\1>|<tr[^>]*>(.*?)</tr>", body, re.S):
        if m.group(2) is not None:
            t = cell_text(m.group(2))
            v = re.fullmatch(r"(Democratic|Republican) (?:Candidates|Ballots) - Vote for (?:up to )?(\d+)(?: - (.+))?", t)
            if v:
                if not heads:
                    raise SystemExit(f"Maryland (state races): {name} has a party section before any office heading")
                where, res = heads[-1] if len(heads) > 1 else "", False
                if heads[0] in ("State Senator", "House of Delegates"):
                    dist = [h for h in heads if re.fullmatch(r"District \w+", h)]
                    if not dist:
                        raise SystemExit(f"Maryland (state races): a section of {name} names no district")
                    # a section by county of residence: only the fact is kept, never which county
                    where, res = dist[-1], heads[-1] != dist[-1]
                cur = {"office": heads[0], "where": where, "res": res, "party": v.group(1), "vote_for": int(v.group(2)),
                       "rule": v.group(3) or "", "totals": {}, "sum": None}
                out.append(cur)
                cols = None
            elif t:
                heads.append(t)
                cur = None
            continue
        if cur is None:
            continue
        cells = [cell_text(c) for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", m.group(3), re.S)]
        if cells and cells[0] == "Name":
            cols = cells
            continue
        if not cols or len(cells) != len(cols):
            continue
        row = dict(zip(cols, cells))
        if row["Name"] == "Totals":
            cur["sum"] = MD.ints(row["Total"])
            cur = None
            continue
        if "Party" in row and row["Party"] != cur["party"]:
            raise SystemExit(f"Maryland (state races): a {row['Party']} candidate in the {cur['party']} section of {name}")
        nm, _res = bare_name(row["Name"])
        if nm in cur["totals"]:
            raise SystemExit(f"Maryland (state races): {nm} is listed twice in one section of {name}")
        cur["totals"][nm] = MD.ints(row["Total"])
    for s in out:
        if s["sum"] is None:
            raise SystemExit(f"Maryland (state races): a section of {name} has no Totals row")
    return out, (f"{refreshed.group(3)}-{refreshed.group(1)}-{refreshed.group(2)}" if refreshed else "")


def results_pages(say):
    names = page_list(say)
    pages, refreshed = {}, ""
    for n in names:
        secs, ref = page_figures(fetch(RESULTS + n, accept="text/html", say=say), n)
        pages[n] = secs
        refreshed = refreshed or ref
        time.sleep(1.0)
    say(f"      official results pages: {len(names)} read")
    return {"refreshed": refreshed, "pages": pages}


# --------------------------------------------------------------------------------------------------------- reading

def district_norm(text):
    """'01A' or '1A' or 'Legislative District 1A' -> '1A'."""
    m = re.fullmatch(r"(?:Legislative District |District )?0*(\d+)([A-C]?)", MD.squash(text))
    if not m:
        raise SystemExit(f"Maryland (state races): a legislative district written {text!r} is not read")
    return f"{int(m.group(1))}{m.group(2)}"


def family_key(last):
    return re.sub(r"[^A-Z]", "", fold(re.sub(r",.*$", "", last)).upper())


def tkey(text):
    """Letters only, one space between words: a ticket as the list and the results both write it."""
    return " ".join(fold(text).split())


def related_name(row):
    return MD.squash(f"{row['Related Candidate First Name and Middle Name']} {row['Related Candidate Last Name and Suffix']}")


def breakdown(path):
    """{(office, where, party): {name: (votes, winner)}} from a legislative breakdown file: the "00" rows for the statewide
    and legislative offices, each county's rows for the Circuit Court. A candidate's votes must lie in the columns of the
    candidate's own legislative district."""
    heads, rows = MD.csv_rows(open(path, "rb").read())
    need = ("County", "County Name", "Office Name", "Office District", "Candidate Name", "Party", "Winner")
    if not all(k in heads for k in need):
        raise SystemExit(f"Maryland (state races): {os.path.basename(path)}'s columns changed ({[k for k in need if k not in heads]} missing)")
    idx = {k: heads.index(k) for k in need}
    ld = {i: district_norm(h.replace("Legislative District ", "")) for i, h in enumerate(heads) if h.startswith("Legislative District ")}
    if not ld:
        raise SystemExit(f"Maryland (state races): {os.path.basename(path)} has no legislative district columns")
    out, circuits, odd = {}, {}, []
    for r in rows:
        office = RESULT_OFFICE.get(MD.squash(r[idx["Office Name"]]))
        county = MD.squash(r[idx["County"]])
        if not office or (office != CIRCUIT) != (county == "00"):
            continue
        code = MD.squash(r[idx["Party"]])
        if code not in PARTY_OF:
            raise SystemExit(f"Maryland (state races): a party code in the results that is not read ({code!r})")
        cols = {d: MD.ints(r[i]) for i, d in ld.items()}
        name = bare_name(MD.squash(r[idx["Candidate Name"]]))[0]
        if office in (SENATE, HOUSE):
            where = district_norm(r[idx["Office District"]])
            mine = (lambda d: re.sub(r"[A-C]$", "", d) == where) if office == SENATE else (lambda d: d == where)
            if any(v for d, v in cols.items() if not mine(d)):
                odd.append(f"{office} {where} {code} {name}")
        elif office == CIRCUIT:
            where = f"{int(county):02d}"
            m = re.fullmatch(r"(.+?) Circuit Court 0*(\d+)", MD.squash(r[idx["Office District"]]))
            if not m:
                raise SystemExit(f"Maryland (state races): a Circuit Court contest written {r[idx['Office District']]!r} is not read")
            circuits[where] = (m.group(1), str(int(m.group(2))))
        else:
            where = ""
        cell = out.setdefault((office, where, PARTY_OF[code]), {})
        if name in cell:
            raise SystemExit(f"Maryland (state races): {name} is listed twice in the {office} {where} {code} results")
        cell[name] = (sum(cols.values()), MD.squash(r[idx["Winner"]]).upper() == "Y")
    return out, circuits, odd


def census_counties():
    """{folded county name: (GEOID, NAMELSAD)} for Maryland from the Census Bureau's cartographic county file."""
    import shapefile                                   # pyshp
    if not os.path.exists(COUNTY_ZIP):
        net.download(COUNTY_URL, COUNTY_ZIP, max_age_days=3650)
    z = zipfile.ZipFile(COUNTY_ZIP)
    base = next(n[:-4] for n in z.namelist() if n.endswith(".dbf"))
    rdr = shapefile.Reader(dbf=io.BytesIO(z.read(base + ".dbf")))
    fields = [f[0] for f in rdr.fields[1:]]
    out = {}
    for rec in rdr.iterRecords():
        rec = dict(zip(fields, rec))
        if str(rec.get("STATEFP")) == FIPS:
            out[county_fold(str(rec["NAMELSAD"]))] = (str(rec["GEOID"]), str(rec["NAMELSAD"]))
    if len(out) != 24:
        raise SystemExit(f"Maryland (state races): the county file gives {len(out)} Maryland counties, not 24")
    return out


def county_fold(name):
    return re.sub(r"^saint ", "st ", " ".join(fold(name).split()))


# ---------------------------------------------------------------------------------------------------------- the roster

def roster(path):
    """Sitting legislators and the statewide officials the roster carries: ids, names, parties, chambers, districts and
    offices only (the roster's contact columns are never selected)."""
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    legs = [dict(zip(("id", "first", "last", "full", "other", "party", "chamber", "district"), r)) for r in con.execute(
        "SELECT bioguide_id, first_name, last_name, official_full, other_names, party_name, chamber, district "
        "FROM legislators WHERE is_current = 1")]
    offs = [dict(zip(("id", "first", "last", "full", "office", "party"), r)) for r in con.execute(
        "SELECT bioguide_id, first_name, last_name, official_full, office, party_name FROM officials")]
    con.close()
    for p in offs:
        p["other"] = ""
    return legs, offs


def readings(first, last):
    """The (given names, family name) readings of a name filed as first and middle names plus a ballot last name and
    suffix: with and without a quoted nickname, and the nickname alone as a given name."""
    fam = " ".join(w for w in fold(re.sub(r",.*$", "", last)).split() if w not in ("jr", "sr", "ii", "iii", "iv"))
    plain = fold(re.sub(r'"[^"]*"', " ", first)).split()
    nick = [fold(n) for n in re.findall(r'"([^"]*)"', first) if fold(n)]
    out = [(fold(first).split(), fam), (plain, fam)]
    out += [(n.split(), fam) for n in nick]
    return out


def person_fits(reads, p):
    forms = [(fold(p["first"] or "").split(), " ".join(fold(p["last"] or "").split()))]
    forms += [name_parts(o.strip()) for o in (p.get("other") or "").split(";") if o.strip() and "," not in o and "." not in o]
    return any(f[1] and r[1] and fits(r, f) for r in reads for f in forms)


def chamber_words(p):
    return f"Maryland {'Senate' if p['chamber'] == 'Senate' else 'House of Delegates'}, Legislative District {p['district']}"


# ------------------------------------------------------------------------------------------------------------ loading

def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def mtime(path):
    return dt.datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d")


def seats_words(n, what):
    return f"{NUMBER_WORDS.get(n, n)} {what}{'s' if n != 1 else ''}"


def load(db_path, say=print, cache=CACHE, roster_db=ROSTER):
    net.patient_lookups()
    folder = os.path.join(cache, "md")
    os.makedirs(folder, exist_ok=True)
    report = []

    gpath, ppath = os.path.join(folder, GEN_FILE), os.path.join(folder, PRI_FILE)
    general = kept(gpath, 2, lambda: candidate_list(GENERAL_CSV, GENERAL_PAGE, say))
    primary = kept(ppath, 30, lambda: candidate_list(PRIMARY_CSV, PRIMARY_PAGE, say))
    books = {}
    for party_name, word in FILE_PARTY.items():
        books[party_name] = os.path.join(folder, f"GP26_LegislativeBreakDown{word}.csv")
        net.download(BREAKDOWN.format(party=word), books[party_name], max_age_days=30, say=say)
        if open(books[party_name], "rb").read(64).lstrip(b"\xef\xbb\xbf").lstrip()[:1] not in (b'"', b"C"):
            raise SystemExit(f"Maryland (state races): {os.path.basename(books[party_name])} is not the Board's results file")
    cpath, rpath = os.path.join(folder, COUNTY_JSON), os.path.join(folder, PAGES_JSON)
    counties = kept(cpath, 30, lambda: county_sums(say))
    pages = kept(rpath, 30, lambda: results_pages(say))
    legs, offs = roster(roster_db)
    ctab = census_counties()

    # ---- the official primary results: breakdown files, then the counties' sums and the results pages against them
    votes, circuits, odd = {}, {}, []
    for party_name, path in books.items():
        got, circ, o = breakdown(path)
        for key, cands in got.items():
            if key[2] != party_name:
                raise SystemExit(f"Maryland (state races): the {party_name} breakdown file carries a {key[2]} row")
            votes[key] = cands
        for cc, v in circ.items():
            if circuits.setdefault(cc, v) != v:
                raise SystemExit(f"Maryland (state races): county {cc}'s Circuit Court contest is written two ways in the results")
        odd += o
    if odd:
        report.append(f"legislative candidates with votes outside their own district's columns in the breakdown: {odd[:5]}")

    vote_for, page_totals, page_sums, vf, residence, rules = {}, {}, {}, {}, {}, {}
    circuit_names = {county_fold(v[0]): cc for cc, v in circuits.items()}
    for n, secs in pages["pages"].items():
        for s in secs:
            office = PAGE_OFFICE.get(s["office"])
            if not office:
                raise SystemExit(f"Maryland (state races): {n} is headed {s['office']!r}, an office not read")
            if office in (SENATE, HOUSE):
                where = district_norm(s["where"])
                if s["res"]:                                  # a district whose contest is divided by county of residence
                    residence[(office, where)] = True
            elif office == CIRCUIT:
                where = circuit_names.get(county_fold(s["where"]))
                if where is None:
                    raise SystemExit(f"Maryland (state races): {n} names a Circuit Court contest ({s['where']!r}) not in the breakdown")
            else:
                where = ""
            key = (office, where, s["party"])
            if key in page_sums and (office, where) not in residence:
                raise SystemExit(f"Maryland (state races): two results pages give {office} {where} {s['party']}")
            page_sums[key] = page_sums.get(key, 0) + s["sum"]
            tot = page_totals.setdefault(key, {})
            if set(tot) & set(s["totals"]):
                raise SystemExit(f"Maryland (state races): a candidate is in two sections of {office} {where} {s['party']}")
            tot.update(s["totals"])
            vf[key] = vf.get(key, 0) + s["vote_for"]
            if s.get("rule"):
                rules.setdefault((office, where), set()).add(s["rule"])
    for (office, where, party_name), n in vf.items():
        if vote_for.setdefault((office, where), n) != n:
            report.append(f"{office} {where}: the two parties' sections give different Vote for numbers")
    checked, bad = 0, []
    for key, cands in votes.items():
        office, where, party_name = key
        for name, (v, _w) in cands.items():
            ck = f"{office}|{where}|{party_name}|{name}"
            if counties["sums"].get(ck) != v:
                bad.append(f"{name} ({office} {where}, {party_name}): counties {counties['sums'].get(ck)}, breakdown {v}")
            if page_totals.get(key, {}).get(name) != v:
                bad.append(f"{name} ({office} {where}, {party_name}): results page {page_totals.get(key, {}).get(name)}, breakdown {v}")
            checked += 1
        if page_sums.get(key) != sum(v for v, _w in cands.values()):
            bad.append(f"{office} {where} {party_name}: the Totals row ({page_sums.get(key)}) is not the sum of its candidates")
    known = {f"{o}|{w}|{p}|{n}" for (o, w, p), cands in votes.items() for n in cands}
    extra = set(counties["sums"]) - known
    extra |= {f"{o}|{w}|{p}|{n}" for (o, w, p), t in page_totals.items() for n in t} - known
    if extra:
        bad.append(f"results in one file and not another: {sorted(extra)[:5]}")
    if bad:
        raise SystemExit("Maryland (state races): the primary results do not reconcile: " + "; ".join(bad[:8]))

    # ---- who was on each party's June ballot, from the primary list
    on_ballot, withdrew, tickets, other_status, parts = {}, [], {}, [], {}
    for r in primary["rows"]:
        office, party_name, status = r["Office Name"], r["Office Political Party"], r["Candidate Status"]
        if office not in LOADED or party_name not in CODE and not (office == CIRCUIT and party_name == "Judicial"):
            continue
        name = MD.name_of(r)
        where = district_norm(r["Contest Run By District Name and Number"]) if office in (SENATE, HOUSE) else ""
        if OFF.match(status):
            withdrew.append(f"{name} ({office}{' ' + where if where else ''}, {party_name})")
            continue
        if status != "Active":
            other_status.append(f"{name} ({office}, {party_name}, {status})")
            continue
        if office == GOV:
            if r["Has Related Candidate"] != "Yes":
                raise SystemExit(f"Maryland (state races): the primary ticket of {name} names no candidate for Lieutenant Governor")
            tickets[tkey(f"{name} and {related_name(r)}")] = (name, related_name(r))     # the list writes "Rhodes Sr.", the results "Rhodes, Sr."
        parts[(office, where, name)] = (r["Candidate First Name and Middle Name"], r["Candidate Ballot Last Name and Suffix"])
        if office == CIRCUIT:
            on_ballot.setdefault((office, "circuit", r["Contest Run By District Name and Number"]), set()).add(name)
        else:
            on_ballot.setdefault((office, where, party_name), set()).add(name)
    if other_status:
        report.append(f"primary list rows with a status not read (left out): {other_status}")
    for key, cands in votes.items():
        office, where, party_name = key
        names = {tickets[tkey(n)][0] if office == GOV and tkey(n) in tickets else n for n in cands}
        if office == GOV and {tkey(n) for n in cands} - set(tickets):
            raise SystemExit(f"Maryland (state races): Governor tickets in the results not on the primary list: "
                             f"{sorted(n for n in cands if tkey(n) not in tickets)}")
        if office == CIRCUIT:
            circ = f"Judicial Circuit {circuits[where][1]}"
            if names - on_ballot.get((office, "circuit", circ), set()):
                raise SystemExit(f"Maryland (state races): Circuit Court candidates in the county {where} results not on the {circ} primary list: "
                                 f"{sorted(names - on_ballot.get((office, 'circuit', circ), set()))}")
        elif names != on_ballot.get(key, set()):
            raise SystemExit(f"Maryland (state races): the {office} {where} {party_name} results do not name the primary list's candidates "
                             f"({sorted(names ^ on_ballot.get(key, set()))})")
    for (office, _c, circ), names in on_ballot.items():
        if office != CIRCUIT:
            continue
        for party_name in CODE:
            got = {n for (o, w, p), cands in votes.items() if o == CIRCUIT and p == party_name and f"Judicial Circuit {circuits[w][1]}" == circ
                   for n in cands}
            if got != names:
                raise SystemExit(f"Maryland (state races): the {circ} primary list and the {party_name} Circuit Court results differ "
                                 f"({sorted(got ^ names)})")
    missing_primary = sorted(f"{k[0]} {k[1]} {k[2]}" for k in on_ballot if k[1] != "circuit" and k not in votes)
    if missing_primary:
        raise SystemExit(f"Maryland (state races): primary ballots with no results: {missing_primary}")

    # ---- races, from the November list
    judge_county = {}
    for (office, where, _p), cands in votes.items():
        if office == CIRCUIT:
            for n in cands:
                if judge_county.setdefault(n, where) != where:
                    raise SystemExit(f"Maryland (state races): {n} is in two counties' Circuit Court results")
    races, listed, gone, write_ins, skipped, off_status = {}, {}, [], [], {}, {}

    def holders_for(chamber, d):
        return [p for p in legs if p["chamber"] == chamber and str(p["district"]).upper().lstrip("0") == d]

    def add(rid, **kw):
        if rid not in races:
            races[rid] = dict(race_id=rid, state=STATE, jurisdiction_id=None, county_ids=None, district=None, seat=None, special=0,
                              holder_id=None, holder_name=None, holder_party=None, election_date=GENERAL, note=None,
                              _holders=[], _chamber=None, _seats=1, _notes=[], **kw)
        return races[rid]

    for r in general["rows"]:
        office, contest, status, filing = r["Office Name"], r["Contest Run By District Name and Number"], r["Candidate Status"], r["Filing Type and Date"]
        if office not in LOADED:
            skipped[office] = skipped.get(office, 0) + 1
            continue
        name = MD.name_of(r)
        if office in (SENATE, HOUSE):
            d = district_norm(contest)
            senate = office == SENATE
            rid = f"2026-{STATE}-{'SS' if senate else 'SH'}{d}"
            chamber = "Senate" if senate else "House"
            race = add(rid, level="legislature", office_kind="state_senate" if senate else "state_house", office=office,
                       jurisdiction=f"Legislative District {d}", partisan=1)
            race.update(jurisdiction_id=d, district=d, _chamber=chamber)
            if not race["_holders"]:
                race["_holders"] = holders_for(chamber, d)
        elif office in (GOV, COMP, AG):
            if contest != "State Of Maryland":
                raise SystemExit(f"Maryland (state races): a {office} row filed under {contest!r}")
            kind, words, okind = {GOV: ("GOV", "Governor and Lieutenant Governor", "governor"), COMP: ("COMP", "Comptroller", "comptroller"),
                                  AG: ("AG", "Attorney General", "attorney_general")}[office]
            race = add(f"2026-{STATE}-{kind}", level="statewide", office_kind=okind, office=words, jurisdiction="Maryland", partisan=1)
            race["jurisdiction_id"] = FIPS
            if not race["_holders"]:
                race["_holders"] = [p for p in offs if p["office"] == {GOV: "governor", AG: "attorney general"}.get(office)]
            rid = race["race_id"]
        elif office == CIRCUIT:
            m = re.fullmatch(r"Judicial Circuit (\d+)", contest)
            if not m:
                raise SystemExit(f"Maryland (state races): a Circuit Court row filed under {contest!r}")
            cc = judge_county.get(name)
            if cc is None:
                report.append(f"{name} ({contest}) is on the November list but in no county's Circuit Court primary results; not placed")
                continue
            cname, circ = circuits[cc]
            if circ != m.group(1):
                raise SystemExit(f"Maryland (state races): {name} is filed under {contest} but ran in the Circuit {circ} results")
            geo = ctab.get(county_fold(cname))
            if geo is None:
                raise SystemExit(f"Maryland (state races): {cname!r} is not a county in the Census file")
            race = add(f"2026-{STATE}-CC-{geo[0]}", level="court", office_kind="circuit_court", office="Judge of the Circuit Court",
                       jurisdiction=f"{cname} (Judicial Circuit {circ})", partisan=0)
            race.update(jurisdiction_id=geo[0], county_ids=json.dumps([geo[0]]), district=circ, _cc=cc)
            rid = race["race_id"]
        else:                                                                     # the two retention votes
            fam = family_key(r["Candidate Ballot Last Name and Suffix"])
            if office == SUPREME:
                m = re.fullmatch(r"Appellate Circuit (\d+)", contest)
                if not m:
                    raise SystemExit(f"Maryland (state races): a Supreme Court row filed under {contest!r}")
                race = add(f"2026-{STATE}-SCRET-{fam}", level="court", office_kind="supreme_court_retention",
                           office="Justice, Supreme Court of Maryland (retention vote)", jurisdiction=f"Appellate Circuit {m.group(1)}", partisan=0)
                race["district"] = m.group(1)
                race["_notes"] = [RETENTION_NOTE, f"The State Board's list files this seat under Appellate Circuit {m.group(1)}: it is on the "
                                                  "ballot in that appellate judicial circuit only."]
            else:
                if contest != "State Of Maryland":
                    raise SystemExit(f"Maryland (state races): an Appellate Court at large row filed under {contest!r}")
                race = add(f"2026-{STATE}-COARET-{fam}", level="court", office_kind="court_of_appeals_retention",
                           office="Judge, Appellate Court of Maryland, At Large (retention vote)", jurisdiction="Maryland", partisan=0)
                race["jurisdiction_id"] = FIPS
                race["_notes"] = [RETENTION_NOTE, "An at-large seat on the Appellate Court of Maryland (the intermediate appellate court): on "
                                                  "every ballot in the state."]
            rid = race["race_id"]
        if OFF.match(status):
            gone.append(f"{name} ({rid}, {status.split(' - ')[0]})")
            off_status[(rid, fold(name))] = status
            continue
        if status != "Active":
            raise SystemExit(f"Maryland (state races): a status on the general list that is not read ({status!r}, {rid})")
        party_name = r["Office Political Party"]
        if not party_name:
            raise SystemExit(f"Maryland (state races): a candidate for {rid} with no party on the list")
        write_in = filing.startswith("Write-In")
        if not write_in and not re.match(r"(Regular|Designated|Party Designated|Petition)\b", filing):
            raise SystemExit(f"Maryland (state races): a filing type on the general list that is not read ({filing!r}, {rid})")
        if race["partisan"] and party_name == "Judicial" or not race["partisan"] and party_name not in ("Judicial", "Other Candidates"):
            report.append(f"{rid}: {name} is filed with the party {party_name!r}")
        mate = None
        if office == GOV:
            if r.get("Has Related Candidate") != "Yes" or r.get("Related Candidate Status") != "Active":
                report.append(f"{rid}: the ticket of {name} names no active candidate for Lieutenant Governor")
            else:
                mate = related_name(r)
                if r.get("Related Office Political Party") != party_name:
                    report.append(f"{rid}: {name}'s running mate is filed under another party")
        if any(fold(c["name"]) == fold(name) for c in listed.get(rid, [])):
            raise SystemExit(f"Maryland (state races): {name} is on the {rid} list twice as Active")
        listed.setdefault(rid, []).append(dict(name=name, party=party_name, write_in=write_in, filing=filing, mate=mate,
                                               last=r["Candidate Ballot Last Name and Suffix"], first=r["Candidate First Name and Middle Name"]))
        if write_in:
            write_ins.append(f"{name} ({rid})")

    # ---- seats: the House of Delegates districts from the results pages' Vote for numbers, checked against the roster
    for rid, race in races.items():
        if race["office_kind"] == "state_house":
            n = vote_for.get((HOUSE, race["district"]))
            if n is None:
                n = len(race["_holders"]) or 1
                report.append(f"{rid}: no primary results page gives its Vote for number; the roster's {n} members taken as its seats")
            elif n != len(race["_holders"]):
                report.append(f"{rid}: the results page says Vote for {n}, the roster has {len(race['_holders'])} sitting members")
            race["_seats"] = n
        elif race["office_kind"] == "circuit_court":
            n = vote_for.get((CIRCUIT, race["_cc"]))
            if n is None:
                report.append(f"{rid}: no results page gives its Vote for number")
                n = None
            race["_seats"] = n

    # ---- notes and holders
    for rid, race in races.items():
        hs, okind = race["_holders"], race["office_kind"]
        notes = list(race["_notes"])
        if okind == "state_senate":
            notes.insert(0, SENATE_NOTE)
            if len(hs) != 1:
                report.append(f"{rid}: {len(hs)} sitting senators in the roster for this district")
                notes.append("The roster shows no single sitting senator for this district.")
                hs = race["_holders"] = hs if len(hs) == 1 else []
        elif okind == "state_house":
            n = race["_seats"]
            notes.insert(0, f"{seats_words(n, 'seat').capitalize()}: Legislative District {race['district']} elects "
                            f"{seats_words(n, 'delegate')}; voters choose {'one' if n == 1 else 'up to ' + NUMBER_WORDS.get(n, str(n))}.")
            if len(hs) < n:
                notes.append(f"The roster shows {len(hs)} sitting delegate{'s' if len(hs) != 1 else ''} for {seats_words(n, 'seat')}.")
            if residence.get((HOUSE, race["district"])):
                notes.append("The State Board's primary results divide this district's contest into sections by the candidates' county "
                             "of residence, one to choose in each; the November list files every candidate under the district.")
            for rule in sorted(rules.get((HOUSE, race["district"]), ())):
                notes.append(f"The official results print this district's rule: {rule}.")
        elif okind == "governor":
            notes.insert(0, GOV_NOTE)
            lt = [p for p in offs if p["office"] == "lt_governor"]
            if len(lt) == 1:
                notes.append(f"Today's Lieutenant Governor, from the roster: {lt[0]['full']}.")
        elif okind == "comptroller":
            notes.insert(0, COMP_NOTE)
        elif okind == "circuit_court":
            n = race["_seats"]
            if n:
                notes.insert(0, f"Voters in {race['jurisdiction'].split(' (')[0]} choose {'one judge' if n == 1 else 'up to ' + seats_words(n, 'judge')} "
                                f"(the primary results' Vote for number).")
            notes.append(CIRCUIT_NOTE)
            notes.append("Ballot order is the State Board's list's own order, alphabetical by surname.")
        elif okind.endswith("_retention"):
            judge = [c for c in listed.get(rid, []) if not c["write_in"]]
            if len(judge) != 1:
                report.append(f"{rid}: a retention vote with {len(judge)} names")
            else:
                race["holder_name"] = judge[0]["name"]
        if race["partisan"] and race["level"] == "legislature" or okind in ("governor", "comptroller", "attorney_general"):
            notes.append(ORDER_NOTE)
        if hs:
            race["holder_id"] = "; ".join(p["id"] for p in hs)
            race["holder_name"] = "; ".join(p["full"] for p in hs)
            race["holder_party"] = "; ".join(p["party"] or "" for p in hs)
        race["note"] = " ".join(notes) or None

    def identify(race, reads, party):
        """(incumbent, state_member_id, note) for one name: the seat's holder when the name fits exactly one of them, else a
        sitting legislator of the same party elsewhere when the name fits exactly one."""
        hs = race["_holders"]
        got = [p for p in hs if person_fits(reads, p)]
        if len(got) == 1:
            return 1, got[0]["id"], None
        if race["level"] == "court":
            return 0, None, None
        pool = [p for p in legs if (p["party"] or "") == party and person_fits(reads, p) and p not in hs]
        if len(pool) == 1:
            return 0, pool[0]["id"], f"Serves today in the {chamber_words(pool[0])}."
        return 0, None, None

    def one_holder_each(rows):
        """A sitting member's id goes to one candidate per election only: the one holding that seat when exactly one does, else
        nobody (a second Mark Fisher running elsewhere is not the delegate running for his own seat)."""
        seen = {}
        for i, c in enumerate(rows):
            if c[12]:
                seen.setdefault((c[1], c[12]), []).append(i)
        for (election, mid), idx in seen.items():
            if len(idx) < 2:
                continue
            inc = [i for i in idx if rows[i][7]]
            keep = inc[0] if len(inc) == 1 else None
            for i in idx:
                if i == keep:
                    continue
                report.append(f"{rows[i][0]} {election}: {rows[i][3]} fits the sitting member {mid}, who is matched elsewhere or twice; "
                              "not tied")
                rows[i][7], rows[i][12] = 0, None
                rows[i][14] = re.sub(r"\s*Serves today in the [^.]*\.", "", rows[i][14] or "").strip() or None

    # ---- November candidates, with the ballot order checked against the ballot's pattern
    cands, nominee, order_odd = [], {}, []
    RANK = {"Democratic": 0, "Republican": 1}
    for rid, rows in listed.items():
        race = races[rid]
        printed = [c for c in rows if not c["write_in"]]
        if race["partisan"]:
            key = [(RANK.get(c["party"], 2), "" if c["party"] in RANK else c["party"], family_key(c["last"]), fold(c["first"])) for c in printed]
            blocks = [c["party"] for c in printed]
            seq = [p for i, p in enumerate(blocks) if i == 0 or blocks[i - 1] != p]
            contiguous = len(seq) == len(set(seq))
            ok = contiguous and [k[0] for k in key] == sorted(k[0] for k in key) and all(
                [k[2:] for k in key if k[1] == pb and k[0] == rb] == sorted(k[2:] for k in key if k[1] == pb and k[0] == rb)
                for rb, pb in {(k[0], k[1]) for k in key})
        else:
            key = [(family_key(c["last"]), fold(c["first"])) for c in printed]
            ok = key == sorted(key)
        if not ok:
            order_odd.append(rid)
        pos = 0
        for c in rows:
            reads = readings(c["first"], c["last"])
            notes = []
            if race["partisan"]:
                party, code = c["party"], party_code(c["party"])
            else:
                party, code = NONPARTISAN, "N"
            if c["write_in"]:
                bo = None
                notes.append(WRITE_IN)
            else:
                pos += 1
                bo = pos if ok else None
                if race["partisan"] and c["party"] in CODE:
                    nominee.setdefault((rid, c["party"]), []).append(c["name"])
            if c["mate"]:
                notes.append(f"Running mate for Lieutenant Governor: {c['mate'].rstrip('.')}.")
            m = re.match(r"(Designated by Central Committee|Party Designated) - (\d\d)/(\d\d)/(\d{4})", c["filing"])
            if m and c["party"] in CODE and f"{m.group(4)}-{m.group(2)}-{m.group(3)}" > PRIMARY:
                notes.append(f"Named by the party after the June 23 primary (the State Board's list: {m.group(1)}, "
                             f"{m.group(2)}/{m.group(3)}/{m.group(4)}).")
            if race["office_kind"].endswith("_retention"):
                inc, mid = 1, None
                notes.append("Standing for continuance in office as the sitting judge.")
            else:
                inc, mid, n2 = identify(race, reads, c["party"])
                if n2:
                    notes.append(n2)
            cands.append([rid, "general", GENERAL, c["name"], party, code, bo, inc, 1 if c["write_in"] else 0, None, None, None, mid, SRC_GEN,
                          " ".join(notes) or None])
    if order_odd:
        report.append(f"contests whose list order is not the ballot's pattern (stored with no ballot order): {order_odd}")
    one_holder_each(cands)

    # ---- which seats: the whole Senate and House of Delegates, and every contest has printed names
    sen = sorted(int(r["district"]) for r in races.values() if r["office_kind"] == "state_senate")
    house = [r for r in races.values() if r["office_kind"] == "state_house"]
    if sen != list(range(1, SENATE_SEATS + 1)):
        report.append(f"Senate districts missing from the November list: {sorted(set(range(1, SENATE_SEATS + 1)) - set(sen))}")
    roster_house = {str(p["district"]).upper() for p in legs if p["chamber"] == "House"}
    if {r["district"] for r in house} != roster_house or len(house) != HOUSE_DISTRICTS:
        report.append(f"House of Delegates districts on the list and in the roster differ: {sorted(roster_house ^ {r['district'] for r in house})}")
    if sum(r["_seats"] for r in house) != HOUSE_SEATS:
        report.append(f"the House of Delegates districts add up to {sum(r['_seats'] for r in house)} seats, not {HOUSE_SEATS}")
    for rid, race in races.items():
        printed = [c for c in listed.get(rid, []) if not c["write_in"]]
        if not printed:
            report.append(f"{rid}: no printed candidate on the November list")
        elif race["_seats"] and len(printed) < race["_seats"] and race["level"] != "court":
            report.append(f"{rid}: {len(printed)} printed candidates for {race['_seats']} seats")
    for g in ("governor", "comptroller", "attorney_general"):
        if not any(r["office_kind"] == g for r in races.values()):
            report.append(f"no {g} race on the November list")

    # ---- the primary fields
    primary_rows, nfields, not_on, later, wins_odd = [], {}, [], [], []
    rid_of = {}
    for rid, race in races.items():
        if race["office_kind"] in ("state_senate", "state_house"):
            rid_of[(SENATE if race["office_kind"] == "state_senate" else HOUSE, race["district"])] = rid
        elif race["office_kind"] == "circuit_court":
            rid_of[(CIRCUIT, race["_cc"])] = rid
        elif race["office_kind"] in ("governor", "comptroller", "attorney_general"):
            rid_of[({"governor": GOV, "comptroller": COMP, "attorney_general": AG}[race["office_kind"]], "")] = rid
    general_names = {rid: {fold(c["name"]) for c in rows} for rid, rows in listed.items()}
    for (office, where, party_name), cands_v in sorted(votes.items()):
        rid = rid_of.get((office, where))
        if rid is None:
            report.append(f"{office} {where} {party_name}: primary results for a contest not on the November list (not loaded)")
            continue
        race = races[rid]
        seats = race["_seats"] or 1
        winners = {n for n, (_v, w) in cands_v.items() if w}
        ranked = sorted(cands_v.items(), key=lambda kv: -kv[1][0])
        top = {n for n, _ in ranked[:seats]}
        if len(cands_v) > seats and len(ranked) > seats and ranked[seats - 1][1][0] == ranked[seats][1][0]:
            report.append(f"{rid} {party_name} primary: a tie for the last place that advances")
        if winners != (top if len(cands_v) > seats else set(cands_v)):
            wins_odd.append(f"{rid} {party_name}")
        shown = {n: (tickets[tkey(n)][0] if office == GOV else n) for n in cands_v}
        # a winner not on the November list, and (for a party office) a November nominee who was not a winner
        for n in winners:
            if fold(shown[n]) not in general_names.get(rid, set()):
                not_on.append(f"{shown[n]} ({rid}, {party_name})")
        if race["partisan"]:
            for nm in nominee.get((rid, party_name), []):
                if fold(nm) not in {fold(shown[n]) for n in winners}:
                    later.append(f"{nm} ({rid}, {party_name})")
        if len(cands_v) <= seats:
            continue
        nfields[race["office_kind"]] = nfields.get(race["office_kind"], 0) + 1
        total = sum(v for v, _w in cands_v.values())
        for n, (v, w) in sorted(cands_v.items(), key=lambda kv: (-kv[1][0], kv[0])):
            name = shown[n]
            notes = []
            if office == GOV:
                notes.append(f"Running mate for Lieutenant Governor: {tickets[tkey(n)][1].rstrip('.')}.")
            if w and fold(name) not in general_names.get(rid, set()):
                st = re.match(r"(Declined|Withdrawn|Disqualified|Deceased) - (\d\d/\d\d/\d{4})", off_status.get((rid, fold(name)), ""))
                notes.append({"Declined": f"Won the primary and declined the nomination on {st.group(2)} (the State Board's list); "
                                          "not on the November ballot.",
                              "Withdrawn": f"Won the primary and withdrew on {st.group(2)} (the State Board's list); not on the "
                                           "November ballot."}.get(st.group(1), f"Won the primary; the State Board's list marks the "
                                                                              f"candidacy {st.group(1)} ({st.group(2)}).")
                             if st else "Won the primary but is not on the November list.")
            if race["partisan"]:
                party, code = party_name, party_code(party_name)
                inc, mid, n2 = identify(race, readings(*parts.get((office, where, name), split_name(name))), party_name)
                if n2:
                    notes.append(n2)
            else:
                party, code, inc, mid = NONPARTISAN, "N", 0, None
                notes.append(f"On the {party_name} primary ballot, as every Circuit Court candidate is.")
            primary_rows.append([rid, f"primary-{CODE[party_name]}", PRIMARY, name, party, code, None, inc, 0, v,
                                 round(100 * v / total, 1) if total else None, "advanced" if w else "lost", mid,
                                 SRC_BOOK.format(p=CODE[party_name].lower()), " ".join(notes) or None])
    if wins_odd:
        report.append(f"primaries whose Winner marks are not the top vote-getters: {wins_odd}")
    one_holder_each(primary_rows)
    cands += primary_rows

    seen = set()
    for c in cands:
        k = (c[0], c[1], c[3])
        if k in seen:
            raise SystemExit(f"Maryland (state races): {c[3]} is listed twice in {c[0]} {c[1]}")
        seen.add(k)

    # ---- write: Maryland's rows only, in one transaction
    cols = ["race_id", "state", "level", "office_kind", "office", "jurisdiction", "jurisdiction_id", "county_ids", "district", "seat",
            "special", "partisan", "holder_id", "holder_name", "holder_party", "election_date", "note"]
    race_rows = [tuple(r[c] for c in cols) for r in races.values()]
    gen_rows = [c for c in cands if c[1] == "general"]
    n_state = sum(1 for r in general["rows"] if r["Office Name"] in LOADED)
    src = [
        (SRC_GEN, STATE, "official candidate list", "Maryland State Board of Elections",
         "2026 Gubernatorial General Election State Candidates List (CSV, all offices)", GENERAL_CSV, general.get("published", ""),
         general.get("fetched", mtime(gpath)), general["sha256"], n_state,
         "Seven columns read by heading (office, contest, the two name columns, party, status, filing type), and on a Governor's row "
         "the running mate's names, party and status; addresses, phones, e-mail, websites, social accounts, committee names, county "
         "of residence and gender never read, and the file is not kept (the SHA-256 is of the file as downloaded). Ballot order is "
         f"the list's own order. Withdrawn, declined or failed petitions, left off: {len(gone)} ({'; '.join(gone) or 'none'}). "
         f"Certified write-in candidates: {len(write_ins)} ({', '.join(write_ins) or 'none'}). Also on the list and loaded by the "
         f"federal side: {', '.join(f'{k} ({v})' for k, v in skipped.items()) or 'nothing else'}."),
        (SRC_PRI, STATE, "official candidate list", "Maryland State Board of Elections",
         "2026 Gubernatorial Primary Election State Candidates List (CSV, all offices)", PRIMARY_CSV, primary.get("published", ""),
         primary.get("fetched", mtime(ppath)), primary["sha256"], sum(1 for r in primary["rows"] if r["Office Name"] in LOADED),
         "Used to check the results: each contest's Democratic and Republican candidates marked Active (and the Circuit Court's "
         "candidates) must be exactly the candidates in the results. Filings withdrawn, disqualified or deceased before the June 23 "
         f"primary: {len(withdrew)}."),
    ]
    for party_name, path in books.items():
        src.append((SRC_BOOK.format(p=CODE[party_name].lower()), STATE, "official results", "Maryland State Board of Elections",
                    f"2026 Gubernatorial Primary Election (June 23, 2026), statewide breakdown by legislative district, {party_name}",
                    BREAKDOWN.format(party=FILE_PARTY[party_name]), "", mtime(path), sha(path),
                    sum(len(c) for k, c in votes.items() if k[2] == party_name),
                    "The State of Maryland (county 00) rows for Governor / Lt. Governor, Comptroller, Attorney General, State Senator and "
                    "House of Delegates, and each county's Judge Circuit Court rows, with the Board's Winner mark. No write-in votes are "
                    "in the file, so a field's total is the sum of its candidates' votes."))
    src += [
        (SRC_COUNTIES, STATE, "official results", "Maryland State Board of Elections",
         "2026 Gubernatorial Primary Election, results by county (GP26_01 to GP26_24, Democratic and Republican)",
         COUNTY_FILE.format(cc=1, party="Democratic").replace("01Democratic", "<county><party>"), "", mtime(cpath), sha(cpath),
         len(counties["sums"]),
         f"Control: the state offices' rows of all {counties['files']} county files, summed per candidate, equal the breakdown files "
         f"({checked} candidates checked). Kept as the sums read from them."),
        (SRC_PAGES, STATE, "official results", "Maryland State Board of Elections",
         "Official 2026 Gubernatorial Primary Election Results: Governor / Lt. Governor, Comptroller, Attorney General, State "
         "Senator, House of Delegates, Judge of the Circuit Court", RESULTS + "gen_results_2026_<office>_<contest>.html",
         pages.get("refreshed", ""), mtime(rpath), sha(rpath), sum(len(s["totals"]) for secs in pages["pages"].values() for s in secs),
         f"Control: every candidate's Total on the {len(pages['pages'])} official results pages equals the breakdown files' figure and "
         "each Totals row equals the sum of its candidates. Each contest's Vote for number gives the seats of a House of Delegates "
         "district or a county's Circuit Court contest."),
        (SRC_ROSTER, STATE, "roster", "Open States people project (CC0), as loaded into state_md.sqlite",
         "Sitting Maryland legislators and statewide officials", "https://github.com/openstates/people", "", mtime(roster_db),
         sha(roster_db), len(legs) + len(offs),
         "Who holds each legislative seat today (chamber and district), and the Governor, Lieutenant Governor and Attorney General; "
         "the roster carries no Comptroller and no judges."),
        (SRC_CENSUS, STATE, "geography", "U.S. Census Bureau",
         "Cartographic boundary file, counties, 2024, 1:500,000 (cb_2024_us_county_500k)", COUNTY_URL, "", mtime(COUNTY_ZIP),
         sha(COUNTY_ZIP), len(ctab), "Maryland's 24 counties (23 and Baltimore City): names and GEOIDs only, for the Circuit Court contests."),
    ]
    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA)
    with con:
        con.execute("DELETE FROM sl_candidates WHERE race_id IN (SELECT race_id FROM sl_races WHERE state = ?)", (STATE,))
        con.execute("DELETE FROM sl_candidates WHERE race_id LIKE ?", (f"2026-{STATE}-%",))
        con.execute("DELETE FROM sl_races WHERE state = ?", (STATE,))
        con.execute("DELETE FROM sl_sources WHERE state = ?", (STATE,))
        con.executemany(f"INSERT INTO sl_races VALUES ({','.join('?' * len(cols))})", race_rows)
        con.executemany("INSERT INTO sl_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", cands)
        con.executemany("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", src)
    con.close()

    by = lambda kind, rows: sum(1 for c in rows if races[c[0]]["office_kind"] == kind)
    statewide = ("governor", "comptroller", "attorney_general")
    say(f"    Maryland: {len(races)} races ({len(sen)} Senate, {len(house)} House of Delegates districts for "
        f"{sum(r['_seats'] for r in house)} seats, {sum(1 for r in races.values() if r['level'] == 'statewide')} statewide, "
        f"{sum(1 for r in races.values() if r['office_kind'] == 'circuit_court')} Circuit Court contests, "
        f"{sum(1 for r in races.values() if r['office_kind'].endswith('_retention'))} retention votes); {len(gen_rows)} candidates on the "
        f"November list (Senate {by('state_senate', gen_rows)}, House {by('state_house', gen_rows)}, statewide "
        f"{sum(by(k, gen_rows) for k in statewide)}, courts {sum(1 for c in gen_rows if races[c[0]]['level'] == 'court')}; "
        f"{len(write_ins)} certified write-ins, {len(gone)} left off); primary fields: Senate {nfields.get('state_senate', 0)}, House "
        f"{nfields.get('state_house', 0)}, statewide {sum(nfields.get(k, 0) for k in statewide)}, Circuit Court "
        f"{nfields.get('circuit_court', 0)} ({len(primary_rows)} rows), official votes reconciled with {counties['files']} county files "
        f"and {len(pages['pages'])} results pages")
    for c in cands:
        if c[12]:
            say(f"      matched: {c[0]} {c[1]}: {c[3]} -> {c[12]}{' (holds this seat)' if c[7] else ''}")
    if not_on:
        report.append(f"primary winners not on the November list: {not_on}")
    if later:
        report.append(f"November nominees who did not win the party's primary: {later}")
    for line in report:
        say(f"      check: {line}")
    return len(gen_rows)


def split_name(name):
    """A shown name back into (first and middle, ballot last name and suffix) for matching: the last word, with a trailing
    suffix kept with it."""
    m = re.fullmatch(r"(.+?) (\S+(?:,? (?:Jr\.|Sr\.|II|III|IV))?)", name)
    return (m.group(1), m.group(2)) if m else ("", name)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m ballot.state_local_md <database>")
    load(sys.argv[1])
