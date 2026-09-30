"""
ballot/state_local_me.py - Maine's state races on the November 3, 2026 ballot: Governor, all 35 State Senate seats and
all 151 seats in the House of Representatives, with the June 9 party primaries that chose the nominees. Written into
ballot_local_2026.sqlite (never ballot_2026.sqlite), Maine's rows only.

    python ballot/state_local_me.py --db <database file> [--no-fetch]

Maine elects no other state office by popular vote this year: the general list's only state offices are GOV, SS (State
Senator) and SR (Representative to the Legislature), and every one of the 35 Senate and 151 House districts has
candidates on it. The rest of the list is county offices (Judge and Register of Probate, County Treasurer, Register of
Deeds, Sheriff, District Attorney, County Commissioner, two county budget committees and a charter commission): counted
and left for the county pages. On Maine's lists "SH" is Sheriff; the House is "SR" (race ids here still use SH for a
House seat, as every state's do).

Sources, all the Maine Secretary of State's own (Bureau of Corporations, Elections and Commissions), the same files the
federal loader (ballot/lists/me.py) reads for Congress, plus the state offices' own primary tabulations:

  November ballot   "2026 General Election Candidates List" (Excel, "November 3, 2026"): only Office, Dist, Party and
                    the four name columns are taken, by heading; the Residence Municipality column and the unheaded
                    columns after it are never read. Parties are the qualified parties' letters (D Democratic,
                    R Republican, G Green Independent, L Libertarian) or a non-party candidate's designation, printed in
                    full and kept as printed ("Independent", "Unenrolled", "Undeclared").
  withdrawals       "Candidate Withdrawals and Replacement Candidate Nominations after the June 9, 2026 Primary" (PDF):
                    read by the federal loader's fixed column bands (office, district, party, name, date, replacement);
                    the Residence column is never turned into text. A withdrawn candidate still on the general list is
                    left off (the Candidate's Guide: a withdrawal by August 25 takes the name off the ballot; every one
                    here is dated earlier). The replacement column also carries the Division's remarks ("No
                    replacement allowed", "withdrew after deadline", "non-party candidate"); only a name that is the
                    general list's candidate for that district and party is taken as the replacement.
  write-ins         "Declared Write-In Candidates" for November 3 (PDF): office, district, party and name bands only.
                    Added as write_in 1, no ballot position, the designation as printed.
  ballot order      21-A MRS section 601(2)(B): the ballot lists the candidates "arranged alphabetically with the last
                    name first, under the proper office designation". ballot_order is each printed candidate's place in
                    that order (by last name, then first name); the list's own order is checked against it.
  primary list      "2026 Primary Candidate List" (Excel, 3/16/2026) and the pre-primary withdrawals (PDF, as of May 22,
                    2026). The Candidate's Guide: a withdrawal by 5 p.m. on March 31 took the name off the June ballot;
                    a later one left the name printed, with votes for it not counted. So the names printed on each
                    party's ballot are the list's, less withdrawals dated by March 31; a later withdrawal's column must
                    show no votes, and that candidate is left out of the field and named in the source note.
  primary votes     the Secretary's final tabulations of the June 9 primary (election-results-data): one workbook per
                    office and party for the State Senate and the House (one block per district: a heading row, the
                    municipal rows with district and county, a Total row), and, for the four state contests that went
                    to the central ranked-choice count (Governor, both parties; Senate District 4 and House District 58,
                    Republican), the "RCV Central Count first choice votes" workbook with its RCV Summary Report (PDF).
                    The line printed under each candidate's name in every workbook is the candidate's town of residence
                    and is never read: a district workbook's heading rows are found by column A alone ("DIS"), a
                    ranked-choice workbook's names and heading sit in fixed rows (1 and 4) and the two rows between them
                    are never looked at, a row is taken only when its vote cells hold numbers, and only the district,
                    county and vote cells of such a row are used (the Total label is looked for to find the total row).
                    Checks: every total's candidates plus blanks equal its ballots cast (TBC), and a row whose do not is
                    reported (a CHECK line and the source note), never corrected; every block's rows add up to its total; every district appears once per party; the names printed are exactly the primary
                    list's for that district and party (less withdrawals by March 31); a name in a tabulation that is
                    on no list is a write-in candidate (write_in 1, shown in ordinary capitals); every RCV report's
                    rounds account for the same ballots as its first-choice workbook.

Ranked choice (the Secretary's 2026 Candidate's Guide to Ballot Access, "Ranked-Choice Voting (RCV)"): the June 9
primaries for Governor, State Senate and State Representative were decided by ranked choice when three or more
candidates qualified, or two and a declared write-in; otherwise by plurality. The November election for these offices
is decided by plurality, whatever the number of candidates (the race note says so). votes and pct are first choices; pct
is of the candidates (write-ins included), blank ballots left out. A leader with more than half of the first choices won
without further rounds; otherwise the RCV Summary Report's final-round winner advanced, and the row note gives the
rounds in plain words, as the federal loader does.

Places (sl_places): Maine's 16 counties (Census Bureau 2024 county file, attribute table only: names and GEOIDs), and
each Senate and House district ("ME-4") with the counties it reaches, read from the primary tabulations' own county
column (a district's municipal rows in either party's workbook).

Who holds each seat today comes from state_me.sqlite (the Open States roster the state pages use): ids, names, other
names, parties and districts only; its contact columns are never selected. A candidate is the incumbent only when the
name fits exactly one sitting member of the same chamber and district (or the sitting Governor), and that member fits
only that candidate. The House's two tribal representatives are on the roster but not on the Secretary's list.

The privacy rule: from every file only office, district, county, candidate name, party, status (withdrawal date and
replacement), and votes are read. Addresses, towns of residence, ZIP codes, telephones, websites, e-mail and treasurers
are never read, printed, logged, cached or stored; a file that no longer fits its layout stops the loader with the
file and the check, never the line.
"""

import argparse
import collections
import datetime as dt
import hashlib
import io
import json
import os
import re
import sqlite3
import sys
import time
import zipfile

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ballot.common import CACHE, HERE, fold, name_parts, party_code                     # noqa: E402
from ballot.lists import me as fed                                                        # noqa: E402
from ballot.lists.tx import proper                                                        # noqa: E402
from ballot.match import fits                                                             # noqa: E402
from ballot.pdftext import PDF, join, lines, rows as pdf_rows                             # noqa: E402
from states import net                                                                    # noqa: E402

STATE, NAME, FIPS = "ME", "Maine", "23"
GENERAL, PRIMARY = "2026-11-03", "2026-06-09"
PRIMARY_CUTOFF = "2026-03-31"          # the last day a withdrawal took a name off the June ballot (Candidate's Guide)
GENERAL_CUTOFF = "2026-08-25"          # the same for November
AGENCY = fed.AGENCY
FILES = fed.FILES
RESULTS_PAGE = "https://www.maine.gov/sos/elections-voting/election-results-data"
DEFAULT_CACHE = os.path.join(CACHE, "me")
ROSTER = os.path.join(HERE, "state_me.sqlite")
COUNTY_ZIP = os.path.join(HERE, "states_cache", "census", "cb_2024_us_county_500k.zip")
COUNTY_URL = "https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_county_500k.zip"
GUIDE_URL = FILES + "2026%20Candidates%20Guide%20to%20Ballot%20Access%20Final.pdf"
STATUTE_URL = "https://legislature.maine.gov/statutes/21-A/title21-Asec601.html"

OFFICES = {"GOV": ("statewide", "governor", "Governor"),
           "SS": ("legislature", "state_senate", "State Senator"),
           "SR": ("legislature", "state_house", "Representative to the Legislature")}
SEATS = {"SS": 35, "SR": 151}
CHAMBER = {"SS": "Senate", "SR": "House"}
KEY = {"GOV": "GOV", "SS": "SS", "SR": "SH"}
COUNTY_OFFICES = {"JP": "Judge of Probate", "RP": "Register of Probate", "CT": "County Treasurer", "RD": "Register of Deeds",
                  "SH": "Sheriff", "DA": "District Attorney", "CC": "County Commissioner", "KBC": "Knox County Budget Committee",
                  "KCB": "Knox County Budget Committee", "ACC": "county charter commission"}
FEDERAL = ("US", "CG")
PARTIES = fed.PARTIES                                   # D Democratic, R Republican, G Green Independent, L Libertarian
CODES = {"D": "DEM", "R": "REP", "G": "GRN", "L": "LIB"}
LIST_KEEP = fed.LIST_KEEP
WRITE_IN = fed.WRITE_IN
CAPS = "Not on the Secretary of State's primary list; the tabulation prints the name in capitals, shown here in ordinary capitals."
LATE = "Withdrew after the ballots were printed; votes for this name were not counted."

SS, SR = "SS", "SR"
# the primary tabulations: key -> (cache file, file on the site, title, office, party letter, layout, district)
TABULATIONS = {
    "senate-dem": ("me_2026_sl_primary_state_senate_dem.xlsx", "State%20Senate%20DEM%20-%20FINAL.xlsx",
                   "June 9, 2026 Primary Election: State Senate - Democratic", SS, "D", "blocks", None),
    "senate-rep": ("me_2026_sl_primary_state_senate_rep.xlsx", "State%20Senate%20REP%20-%20FINAL.xlsx",
                   "June 9, 2026 Primary Election: State Senate - Republican", SS, "R", "blocks", None),
    "house-dem": ("me_2026_sl_primary_state_rep_dem.xlsx", "Rep%20to%20the%20Legislature%20DEM%20-%20FINAL.xlsx",
                  "June 9, 2026 Primary Election: Representative to the Legislature - Democratic", SR, "D", "blocks", None),
    "house-grn": ("me_2026_sl_primary_state_rep_grn.xlsx", "Rep%20to%20Legislature%20Green%20Independent.xlsx",
                  "June 9, 2026 Primary Election: Representative to the Legislature - Green Independent", SR, "G", "blocks", None),
    "house-rep": ("me_2026_sl_primary_state_rep_rep.xlsx", "Rep%20to%20the%20Legislature%20REP%20-%20FINAL.xlsx",
                  "June 9, 2026 Primary Election: Representative to the Legislature - Republican", SR, "R", "blocks", None),
    "gov-dem": ("me_2026_sl_primary_gov_dem_first_choice.xlsx", "Governor%20-%20Democratic.xlsx",
                "June 9, 2026 Primary Election: Governor - Democratic, RCV Central Count first choice votes", "GOV", "D", "single", None),
    "gov-rep": ("me_2026_sl_primary_gov_rep_first_choice.xlsx", "Governor%20-%20Republican.xlsx",
                "June 9, 2026 Primary Election: Governor - Republican, RCV Central Count first choice votes", "GOV", "R", "single", None),
    "ss4-rep": ("me_2026_sl_primary_ss4_rep_first_choice.xlsx", "Senate%20District%204%20-%20Republican.xlsx",
                "June 9, 2026 Primary Election: Senate District 4 - Republican, RCV Central Count first choice votes", SS, "R", "single", "4"),
    "sr58-rep": ("me_2026_sl_primary_sr58_rep_first_choice.xlsx", "House%20District%2058%20-%20Republican.xlsx",
                 "June 9, 2026 Primary Election: House District 58 - Republican, RCV Central Count first choice votes", SR, "R", "single", "58"),
}
RCV_REPORTS = {
    "gov-dem": ("me_2026_sl_primary_gov_dem_rcv_summary.pdf", "GOV%20Democratic%20RCV%20Summary%20Report.pdf",
                "Jun26 DEM Gov RCV Summary Report (Governor - Democratic)"),
    "gov-rep": ("me_2026_sl_primary_gov_rep_rcv_summary.pdf", "GOV%20Republican%20RCV%20Summary%20Reportxlsx.pdf",
                "Jun26 REP Gov RCV Summary Report (Governor - Republican)"),
    "ss4-rep": ("me_2026_sl_primary_ss4_rep_rcv_summary.pdf", "REP%20SS4%20RCV%20Summary%20Report.pdf",
                "Jun26 REP SS4 RCV Summary Report (State Senator, District 4 - Republican)"),
    "sr58-rep": ("me_2026_sl_primary_sr58_rep_rcv_summary.pdf", "REP%20SR58%20RCV%20Summary%20Report.pdf",
                 "Jun26 REP SR58 RCV Summary Report (Representative to the Legislature, District 58 - Republican)"),
}
SRC = {"general": "me-sos-2026-sl-general-list", "withdrawals": "me-sos-2026-sl-general-withdrawals",
       "write_ins": "me-sos-2026-sl-general-write-ins", "plist": "me-sos-2026-sl-primary-list",
       "pwithdrawals": "me-sos-2026-sl-primary-withdrawals", "guide": "me-sos-2026-candidates-guide",
       "statute": "me-statute-21a-601", "county": "me-census-2024-counties", "roster": "me-openstates-roster"}

NAME_COL = re.compile(r"[A-Z][A-Z'.\- ]*, [A-Z][A-Z'.\-, ]*")
REMARK = re.compile(r"(?i)\b(no replacement|not permitted|withdrew|non-party|deadline|none|vacancy)\b.*$")
SCHEMA = """
CREATE TABLE IF NOT EXISTS sl_races (race_id TEXT PRIMARY KEY, state TEXT NOT NULL, level TEXT NOT NULL, office_kind TEXT NOT NULL, office TEXT NOT NULL, jurisdiction TEXT, jurisdiction_id TEXT, county_ids TEXT, district TEXT, seat TEXT, special INTEGER NOT NULL DEFAULT 0, partisan INTEGER NOT NULL, holder_id TEXT, holder_name TEXT, holder_party TEXT, election_date TEXT NOT NULL, note TEXT);
CREATE TABLE IF NOT EXISTS sl_candidates (race_id TEXT NOT NULL, election TEXT NOT NULL, election_date TEXT, name TEXT NOT NULL, party TEXT, party_code TEXT, ballot_order INTEGER, incumbent INTEGER NOT NULL DEFAULT 0, write_in INTEGER NOT NULL DEFAULT 0, votes INTEGER, pct REAL, outcome TEXT, state_member_id TEXT, source_id TEXT, note TEXT, PRIMARY KEY (race_id, election, name));
CREATE TABLE IF NOT EXISTS sl_sources (source_id TEXT PRIMARY KEY, state TEXT, kind TEXT, agency TEXT, title TEXT, url TEXT, published TEXT, fetched TEXT, sha256 TEXT, rows INTEGER, note TEXT);
CREATE TABLE IF NOT EXISTS sl_places (kind TEXT NOT NULL, id TEXT NOT NULL, name TEXT NOT NULL, county_ids TEXT, source_id TEXT, PRIMARY KEY (kind, id));
"""

clean, person, key_of, date_of, plain_date = fed.clean, fed.person, fed.key_of, fed.date_of, fed.plain_date


# ------------------------------------------------------------------------------------------------------ small helpers

def race_id(office, district=None):
    return f"2026-{STATE}-{KEY[office]}" + (str(district) if district else "")


def district_of(office, dist, where):
    """'' for the Governor; a district number 1-35 or 1-151 as the state writes it, else the loader stops."""
    d = clean(dist)
    if office == "GOV":
        if d:
            raise SystemExit(f"Maine (state races): a Governor row on {where} names a district ({d!r})")
        return None
    if not re.fullmatch(r"\d{1,3}", d) or not 1 <= int(d) <= SEATS[office]:
        raise SystemExit(f"Maine (state races): a {OFFICES[office][2]} row on {where} has a district that is not read ({d!r})")
    return str(int(d))


def party_label(code, where):
    code = clean(code)
    if code in PARTIES:
        return PARTIES[code]
    if len(code) <= 2:
        raise SystemExit(f"Maine (state races): a party code on {where} that is not read ({code!r})")
    return code                                              # a non-party candidate's designation, printed in full


def isint(c):
    return isinstance(c, int) and not isinstance(c, bool)


def pdf_name(text):
    """A name as the withdrawal PDF gives it; its apostrophes come out as the replacement character."""
    return clean((text or "").replace("�", "'").replace("’", "'"))


def names_fit(a, b):
    return fold(a).split() == fold(b).split() or fits(name_parts(a), name_parts(b))


def sha_file(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest() if path and os.path.exists(path) else ""


def day_of(path):
    return dt.datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d") if path and os.path.exists(path) else ""


def source_row(source_id, kind, agency, title, url, published, fetched, sha256, rows, note):
    return (source_id, STATE, kind, agency, title, url, published or "", fetched or "", sha256 or "", rows, note)


# ------------------------------------------------------------------------------------------------------ the lists

def read_list(path, sheet, where):
    """(state rows, {office code: rows}) from a candidate list workbook: Office, Dist, Party and the name columns only."""
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.worksheets[0]
    if clean(ws.title) != sheet:
        raise SystemExit(f"Maine (state races): {where} is headed {ws.title!r}, not {sheet!r}")
    it = ws.iter_rows(values_only=True)
    heads = [clean(c) for c in next(it)]
    if not all(k in heads for k in LIST_KEEP):
        raise SystemExit(f"Maine (state races): the columns of {where} changed")
    idx = {k: heads.index(k) for k in LIST_KEEP}
    out, counts, seq = [], collections.Counter(), 0
    for n, r in enumerate(it, start=2):
        r = list(r) + [None] * (len(heads) - len(r))
        cell = {k: clean(r[i]) for k, i in idx.items()}
        office = cell["Office"].upper()
        if not office:
            if cell["Last Name"]:
                raise SystemExit(f"Maine (state races): row {n} of {where} has a candidate with no office")
            continue
        counts[office] += 1
        if office in OFFICES:
            seq += 1
            out.append({"office": office, "district": district_of(office, cell["Dist"], where), "party": cell["Party"],
                        "name": person(cell["First Name"], cell["Middle Name"], cell["Last Name"], cell["Suffix"]),
                        "last": cell["Last Name"], "first": cell["First Name"],
                        "key": key_of(cell["Last Name"], cell["First Name"]), "seq": seq})
        elif office not in COUNTY_OFFICES and office not in FEDERAL:
            raise SystemExit(f"Maine (state races): {where} has an office code that is not read ({office!r})")
    wb.close()
    return out, counts


def state_pdf_rows(path, kind, where):
    """The state rows of a withdrawal or write-in PDF, read by the federal loader's column bands: [(office, district, cells)]."""
    title, table = fed.read_pdf(path, kind)
    out, offices = [], collections.Counter()
    for cells in table:
        office = clean(cells["office"]).upper()
        offices[office or "(continued)"] += 1
        if office not in OFFICES:
            continue
        district = district_of(office, cells["district"], where)
        if not re.search(r"[A-Za-z]{2}", cells["name"]) or not cells["party"]:
            raise SystemExit(f"Maine (state races): a state row of {where} has no name or no party where they are expected")
        if "date" in cells and not re.fullmatch(r"\d{1,2}/\d{1,2}/(\d{2}|\d{4})", cells["date"]):
            raise SystemExit(f"Maine (state races): a state row of {where} has no date where one is expected")
        out.append((office, district, cells))
    return title, out, len(table), offices


# ------------------------------------------------------------------------------------------------------ the tabulations

def _labels_say_total(r, upto):
    return any(isinstance(c, str) and re.fullmatch(r"(?i)\s*totals?\s*", c) for c in r[:upto])


def read_blocks(path, where, flags):
    """One block per district from a State Senate or House tabulation: [{"cands": {col: printed name}, "district",
    "counties", "votes": {col: n}, "blank", "ballots", "rows"}]. Only rows whose vote cells hold numbers are used; the
    line under the names (each candidate's town) never is. A row whose candidates plus blanks are not its ballots cast is
    added to flags as (row, difference); the block's Total must balance, and its rows must add up to it."""
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    grid = [list(r) for r in wb.worksheets[0].iter_rows(values_only=True)]
    wb.close()
    blocks, cur = [], None

    def close(b, n):
        if b is None:
            return
        if b["total"] is None:
            raise SystemExit(f"Maine (state races): a block of {where} (heading row {b['head']}) has no Total row")
        if any(b["sums"][j] != b["total"][j] for j in b["cols"]):
            raise SystemExit(f"Maine (state races): the rows of the block at row {b['head']} of {where} do not add up to its Total")
        if len(b["dists"]) != 1:
            raise SystemExit(f"Maine (state races): the block at row {b['head']} of {where} has {len(b['dists'])} districts")

    for n, r in enumerate(grid, start=1):
        if r and isinstance(r[0], str) and r[0].strip().upper() == "DIS":      # a heading row; only column A is looked at elsewhere
            up = [clean(c).upper() if isinstance(c, str) else "" for c in r]
            close(cur, n)
            if "BLANK" not in up or "DIS" not in up or "CTY" not in up:
                raise SystemExit(f"Maine (state races): the heading at row {n} of {where} has no DIS, CTY, BLANK or TBC column")
            blank, tbc = up.index("BLANK"), up.index("TBC")
            cands = {j: clean(r[j]) for j in range(blank) if isinstance(r[j], str) and NAME_COL.fullmatch(clean(r[j]).upper())}
            if not cands or sorted(cands) != list(range(min(cands), blank)) or tbc != blank + 1:
                raise SystemExit(f"Maine (state races): the candidate columns at row {n} of {where} are not where they are expected")
            cur = {"head": n, "cands": cands, "blank": blank, "tbc": tbc, "dis": up.index("DIS"), "cty": up.index("CTY"),
                   "cols": list(cands) + [blank, tbc], "sums": collections.Counter(), "total": None, "dists": set(),
                   "counties": set(), "rows": 0}
            blocks.append(cur)
            continue
        if cur is None:
            if any(isint(c) for c in r):
                raise SystemExit(f"Maine (state races): {where} has figures before its first heading (row {n})")
            continue
        r = r + [None] * (cur["tbc"] + 1 - len(r))
        nums = [r[j] for j in cur["cols"]]
        if not any(isint(c) for c in nums):
            continue                                   # a blank row, or the line under the names: not read
        if not all(isint(c) for c in nums):
            raise SystemExit(f"Maine (state races): row {n} of {where} is not read (its vote cells are not whole numbers)")
        if cur["total"] is not None:
            raise SystemExit(f"Maine (state races): {where} has figures after a Total row (row {n})")
        off = sum(r[j] for j in cur["cands"]) + r[cur["blank"]] - r[cur["tbc"]]
        if r[cur["dis"]] is None and _labels_say_total(r, min(cur["cands"])):
            if off:
                raise SystemExit(f"Maine (state races): the Total row {n} of {where}: candidates plus blanks are not the ballots cast")
            cur["total"] = {j: r[j] for j in cur["cols"]}
            continue
        d = r[cur["dis"]]
        if off:
            flags.append((n, off, f"district {d}"))
        if not isint(d):
            raise SystemExit(f"Maine (state races): row {n} of {where} has no district number")
        cur["dists"].add(str(d))
        cty = r[cur["cty"]]
        if isinstance(cty, str) and re.fullmatch(r"[A-Za-z]{3}", cty.strip()):
            cur["counties"].add(cty.strip().upper())
        elif cty is not None:
            raise SystemExit(f"Maine (state races): row {n} of {where} has a county cell that is not read")
        cur["rows"] += 1
        for j in cur["cols"]:
            cur["sums"][j] += r[j]
    close(cur, len(grid))
    out = []
    for b in blocks:
        out.append({"cands": b["cands"], "district": b["dists"].pop(), "counties": b["counties"], "rows": b["rows"],
                    "votes": {j: b["total"][j] for j in b["cands"]}, "blank": b["total"][b["blank"]],
                    "ballots": b["total"][b["tbc"]], "head": b["head"]})
    return out


def read_single(path, where, district, flags):
    """A ranked-choice contest's first-choice workbook: names in the row that carries BLANK, the heading (OFFICE, DIST,
    CTY, TOWN, WARD-PRECINCT ... TBC) under it, one row per municipality or ward, then the state total and the shares.
    The two lines between the names and the heading (each candidate's town, then party) are never read."""
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    grid = [list(r) for r in wb.worksheets[0].iter_rows(values_only=True)]
    wb.close()
    names_at, head_at = 0, 3                          # fixed rows: the two between them are never looked at
    ups = {i: [clean(c).upper() if isinstance(c, str) else "" for c in grid[i]] for i in (names_at, head_at)}
    if "BLANK" not in ups[names_at] or "TBC" not in ups[head_at]:
        raise SystemExit(f"Maine (state races): {where} has no BLANK and TBC rows where they are expected (rows 1 and 4)")
    blank, tbc = ups[names_at].index("BLANK"), ups[head_at].index("TBC")
    row0 = grid[names_at]
    cands = {j: clean(row0[j]) for j in range(blank) if isinstance(row0[j], str) and NAME_COL.fullmatch(clean(row0[j]).upper())}
    if not cands or sorted(cands) != list(range(min(cands), blank)) or tbc != blank + 1 or "CTY" not in ups[head_at]:
        raise SystemExit(f"Maine (state races): the candidate columns of {where} are not where they are expected")
    cty = ups[head_at].index("CTY")
    dis = ups[head_at].index("DIST") if "DIST" in ups[head_at] else None
    cols = list(cands) + [blank, tbc]
    data = []
    for n, r in enumerate(grid[head_at + 1:], start=head_at + 2):
        r = r + [None] * (tbc + 1 - len(r))
        nums = [r[j] for j in cols]
        if not any(isinstance(c, (int, float)) and not isinstance(c, bool) for c in nums):
            continue
        if all(isinstance(c, (int, float)) for c in nums) and any(isinstance(c, float) for c in nums):
            if not data or not all(0 <= c <= 1 for c in nums):
                raise SystemExit(f"Maine (state races): row {n} of {where} is not read")
            continue                                           # the shares under the total
        if not all(isint(c) for c in nums):
            raise SystemExit(f"Maine (state races): row {n} of {where} is not read (its vote cells are not whole numbers)")
        data.append((n, r))
    if len(data) < 2:
        raise SystemExit(f"Maine (state races): {where} has no rows")
    *places, (tn, total) = data
    if sum(total[j] for j in cands) + total[blank] != total[tbc]:
        raise SystemExit(f"Maine (state races): the state total of {where}: candidates plus blanks are not the ballots cast")
    for n, r in places:
        off = sum(r[j] for j in cands) + r[blank] - r[tbc]
        if off:
            flags.append((n, off, f"district {district}" if district else "the state"))
    sums = collections.Counter()
    counties, dists, subtotals = set(), set(), 0
    by_county = collections.defaultdict(collections.Counter)
    for n, r in places:
        c = r[cty]
        sub = [x for x in r[:min(cands)] if isinstance(x, str) and re.fullmatch(r"(?i)\s*[A-Z]{3} totals?\s*", x)]
        if sub:
            code = sub[0].strip()[:3].upper()
            if any(by_county[code][j] != r[j] for j in cols):
                raise SystemExit(f"Maine (state races): the {code} subtotal of {where} (row {n}) is not the sum of that county's rows")
            subtotals += 1
            continue
        if isinstance(c, str) and re.fullmatch(r"[A-Za-z]{3}", c.strip()):
            counties.add(c.strip().upper())
            for j in cols:
                by_county[c.strip().upper()][j] += r[j]
        elif c is not None:
            raise SystemExit(f"Maine (state races): row {n} of {where} has a county cell that is not read")
        if dis is not None and r[dis] is not None:
            dists.add(str(r[dis]))
        for j in cols:
            sums[j] += r[j]
    if any(sums[j] != total[j] for j in cols):
        raise SystemExit(f"Maine (state races): the rows of {where} do not add up to its state total (row {tn})")
    if dis is not None and dists != {district}:
        raise SystemExit(f"Maine (state races): {where} names districts {sorted(dists)}, not {district}")
    return {"cands": cands, "district": district, "counties": counties, "rows": len(places) - subtotals,
            "votes": {j: total[j] for j in cands}, "blank": total[blank], "ballots": total[tbc], "subtotals": subtotals}


def rcv_report(path, where):
    """The federal loader's RCV Summary Report reader, allowing a comma inside a name ('King, Angus, III', 'Bridges, Dexter
    E., Jr.'), with the same checks: every round accounts for the same ballots, a dropped candidate stays at nought, the
    winner leads the final round above the threshold (half the final round plus one), the eliminated are those dropped."""
    got, cands, exhausted = {}, {}, None
    for _p, _y, t in lines(path):
        m = re.fullmatch(r"(Contest|Jurisdiction|Office|Date|Winner\(s\)|Threshold|Rounds|Eliminated|Elected) ?(.*)", t)
        if m:
            got[m.group(1)] = m.group(2).strip()
            continue
        m = re.fullmatch(r"Exhausted Ballots((?: \d+)+)", t)
        if m:
            exhausted = [int(x) for x in m.group(1).split()]
            continue
        m = re.fullmatch(r"([A-Z][A-Za-z'.\- ]*, [A-Za-z'.,\- ]+?)((?: \d+)+)", t)
        if m:
            cands[m.group(1).strip()] = [int(x) for x in m.group(2).split()]
    rounds = len(re.findall(r"Round \d+", got.get("Rounds", "")))
    if not rounds or exhausted is None or len(exhausted) != rounds or len(cands) < 3 or any(len(v) != rounds for v in cands.values()):
        raise SystemExit(f"Maine (state races): {where} is not laid out as an RCV Summary Report is expected to be")
    ballots = {sum(v[k] for v in cands.values()) + exhausted[k] for k in range(rounds)}
    if len(ballots) != 1:
        raise SystemExit(f"Maine (state races): the rounds of {where} do not each account for the same ballots")
    for name, v in cands.items():
        if any(v[k] == 0 and v[k + 1] for k in range(rounds - 1)):
            raise SystemExit(f"Maine (state races): {where} gives {name} votes after dropping them")
    final = sorted(cands, key=lambda c: -cands[c][-1])
    threshold = int(got.get("Threshold", "0") or 0)
    continuing = sum(v[-1] for v in cands.values())
    if fold(got.get("Winner(s)", "")) != fold(final[0]) or fold(got.get("Elected", "")) != fold(final[0]):
        raise SystemExit(f"Maine (state races): the winner named in {where} does not have the most votes in its final round")
    if threshold != continuing // 2 + 1 or cands[final[0]][-1] < threshold:
        raise SystemExit(f"Maine (state races): the threshold in {where} is not half the final round's votes plus one, or the winner is under it")
    dropped = [[c for c, v in cands.items() if v[k] and not v[k + 1]] for k in range(rounds - 1)]
    if fold(got.get("Eliminated", "")) != fold(" ".join(c for step in dropped for c in step)):
        raise SystemExit(f"Maine (state races): the candidates {where} says were eliminated are not the ones its figures drop")
    return {"winner": final[0], "threshold": threshold, "rounds": rounds, "cands": cands, "exhausted": exhausted,
            "dropped": dropped, "contest": got.get("Office", ""), "jurisdiction": got.get("Jurisdiction", ""), "ballots": ballots.pop()}


SUFFIX = re.compile(r"(?i)^(jr|sr|ii|iii|iv|v)\.?$")


def turned(printed):
    """'Bridges, Dexter E., Jr.' -> 'Dexter E. Bridges Jr.'; 'KING, ANGUS III' -> 'ANGUS KING III'."""
    parts = [clean(x) for x in printed.split(",")]
    last, given, extra = parts[0], parts[1] if len(parts) > 1 else "", parts[2:]
    words = given.split()
    tail = []
    while words and SUFFIX.match(words[-1]):
        tail.insert(0, words.pop())
    return clean(" ".join(words + [last] + tail + extra))


def where_words(rid):
    """2026-ME-SH43 -> 'House District 43'; 2026-ME-GOV -> 'Governor'."""
    code = rid.split("-")[-1]
    m = re.fullmatch(r"(SS|SH)(\d+)", code)
    return f"{'Senate' if m.group(1) == 'SS' else 'House'} District {m.group(2)}" if m else "Governor"


def printed_key(printed):
    last, _, given = printed.partition(",")
    return key_of(last, given)


# ------------------------------------------------------------------------------------------------------ places and roster

def county_names(path=COUNTY_ZIP):
    """{three-letter code as the tabulations write it: (GEOID, 'Name County')} for Maine, from the Census file's attribute
    table only. Each code must be the first three letters of exactly one county's name."""
    import shapefile                                   # pyshp
    z = zipfile.ZipFile(path)
    base = next(n[:-4] for n in z.namelist() if n.endswith(".dbf"))
    rdr = shapefile.Reader(dbf=io.BytesIO(z.read(base + ".dbf")))
    fields = [f[0] for f in rdr.fields[1:]]
    out = {}
    for rec in rdr.iterRecords():
        rec = dict(zip(fields, rec))
        if str(rec.get("STATEFP")) == FIPS:
            code = str(rec["NAME"])[:3].upper()
            if code in out:
                raise SystemExit(f"Maine (state races): two counties begin {code}")
            out[code] = (str(rec["GEOID"]), str(rec.get("NAMELSAD") or f"{rec['NAME']} County"))
    if len(out) != 16:
        raise SystemExit(f"Maine (state races): the Census county file lists {len(out)} Maine counties, not 16")
    return out


def roster(path=ROSTER):
    """Sitting legislators and the Governor: id, names, party and district only."""
    if not os.path.exists(path):
        return [], [], ""
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    members = [dict(zip(("id", "chamber", "district", "first", "last", "full", "party", "other"), r)) for r in con.execute(
        "SELECT bioguide_id, chamber, district, first_name, last_name, official_full, party_name, other_names FROM legislators "
        "WHERE is_current = 1")]
    officials = [dict(zip(("id", "office", "first", "last", "full", "party"), r)) for r in con.execute(
        "SELECT bioguide_id, office, first_name, last_name, official_full, party_name FROM officials")]
    as_of = (con.execute("SELECT MAX(updated_at) FROM legislators").fetchone()[0] or "")[:10]
    con.close()
    for m in members:
        m["district"] = str(int(m["district"])) if str(m["district"] or "").isdigit() else str(m["district"] or "")
    return members, officials, as_of


def person_fits(name, p):
    """The name fits the person's first and last name, full name or one of the roster's other names."""
    parts = name_parts(name)
    forms = [p["full"] or ""] + [f.strip() for f in (p.get("other") or "").split(";") if f.strip()]
    return (fits(parts, (fold(p["first"] or "").split(), " ".join(fold(p["last"] or "").split())))
            or any(fits(parts, name_parts(f)) for f in forms if f))


def official_text(url, needles, say):
    """(sha256, fetched day, found) for a page or PDF read in memory only (never saved): whether each sentence is there."""
    try:
        body = net.get(url, accept="*/*")
    except Exception as e:  # noqa: BLE001  the rule it supports is written in the docstring; the row says it was not re-read
        say(f"      Maine (state races): {url} could not be read this run ({e})")
        return "", "", None
    if body[:4] == b"%PDF":
        pdf = PDF(body)
        text = " ".join(join(runs) for page, res in pdf.pages() for _y, runs in pdf_rows(pdf, page, res))
    else:
        text = re.sub(r"<[^>]+>", " ", body.decode("utf-8", "replace"))
    text = re.sub(r"\s+", " ", text)
    return hashlib.sha256(body).hexdigest(), dt.date.today().isoformat(), all(re.search(n, text) for n in needles)


# ------------------------------------------------------------------------------------------------------ load

def load(db_path, say=print, cache=DEFAULT_CACHE, roster_path=ROSTER, fetch=True):
    os.makedirs(cache, exist_ok=True)
    problems, notes_out = [], []
    paths = {k: os.path.join(cache, v[1]) for k, v in fed.LINKED.items()}
    links = {k: (v[3], "") for k, v in fed.LINKED.items()}
    plist = os.path.join(cache, fed.PRIMARY_LIST[0])
    pwd = os.path.join(cache, fed.PRIMARY_WITHDRAWALS[0])
    tab_paths = {k: os.path.join(cache, v[0]) for k, v in TABULATIONS.items()}
    rcv_paths = {k: os.path.join(cache, v[0]) for k, v in RCV_REPORTS.items()}
    guide = statute = ("", "", None)
    if fetch:
        net.patient_lookups()
        links = fed.linked(say)
        for kind, (_pattern, _name, magic, _default) in fed.LINKED.items():
            fed.fetch(links[kind][0], paths[kind], magic, 2, say)
            time.sleep(1)
        fed.fetch(fed.PRIMARY_LIST[1], plist, "PK", 30, say)
        fed.fetch(fed.PRIMARY_WITHDRAWALS[1], pwd, "%PDF", 30, say)
        for k, v in TABULATIONS.items():
            fed.fetch(FILES + v[1], tab_paths[k], "PK", 30, say)
        for k, v in RCV_REPORTS.items():
            fed.fetch(FILES + v[1], rcv_paths[k], "%PDF", 30, say)
        guide = official_text(GUIDE_URL, [r"General Election on November 3, 2026 for Governor, State Senate,",
                                          r"will be decided by plurality, regardless of the number of"], say)
        statute = official_text(STATUTE_URL, [r"arranged alphabetically with the last name first, under the proper office designation"], say)
        for label, got in (("the Candidate's Guide", guide), ("21-A MRS section 601", statute)):
            if got[2] is False:
                problems.append(f"{label} no longer carries the sentence this loader relies on; read it again")

    # ---- the November list
    general, gen_counts = read_list(paths["general"], "November 3, 2026", "the 2026 General Election Candidates List")
    wd_title, withdrawals, wd_rows, wd_offices = state_pdf_rows(paths["withdrawals"], "withdrawals",
                                                                "the list of withdrawals after the primary")
    wi_title, write_ins, wi_rows, wi_offices = state_pdf_rows(paths["write_ins"], "write_ins", "the list of declared write-in candidates")

    races = {}
    for office in OFFICES:
        for d in ([None] if office == "GOV" else [str(i) for i in range(1, SEATS[office] + 1)]):
            level, kind, title = OFFICES[office]
            races[race_id(office, d)] = {"race_id": race_id(office, d), "office_code": office, "level": level, "office_kind": kind,
                                         "office": title, "district": d, "chamber": CHAMBER.get(office),
                                         "jurisdiction": NAME if not d else f"{CHAMBER[office]} District {d}",
                                         "jurisdiction_id": FIPS if not d else d, "counties": set(), "notes": []}
    listed = collections.defaultdict(list)
    for g in general:
        listed[race_id(g["office"], g["district"])].append(g)
    for rid in races:
        if not listed.get(rid):
            problems.append(f"{rid}: no candidate on the November list")

    # withdrawals after the primary: left off if still listed; the replacement, when one is named, must be on the list
    left_off, replaced, wd_words = [], {}, []
    for office, d, c in withdrawals:
        rid = race_id(office, d)
        letter = clean(c["party"]).upper()
        gone = pdf_name(c["name"])
        when = date_of(c["date"])
        rest = pdf_name(REMARK.sub("", c.get("replacement", ""))).strip(" -–—.,;")
        remark = pdf_name(REMARK.search(c.get("replacement", "")).group(0)).strip(" -–—.,;") if REMARK.search(c.get("replacement", "")) else ""
        repl = None
        if rest and re.search(r"[A-Za-z]{2}", rest):
            hits = [g for g in listed[rid] if g["party"] == letter and names_fit(g["name"], rest)]
            if len(hits) == 1:
                repl = hits[0]["name"]
            else:
                problems.append(f"{rid}: the replacement named for {gone} ({rest!r}) is not the general list's "
                                f"{PARTIES.get(letter, letter)} candidate")
        still = [g for g in listed[rid] if names_fit(g["name"], gone)]
        if still:
            if when and when > GENERAL_CUTOFF:
                problems.append(f"{rid}: {gone} withdrew on {when}, after the day a name could be taken off the ballot, and is on the list")
            for g in still:
                left_off.append((rid, g["name"]))
        if letter in PARTIES:
            replaced[(rid, letter)] = {"withdrawn": gone, "date": when, "replacement": repl}
        wd_words.append(f"{gone} ({where_words(rid)}, {PARTIES.get(letter, 'non-party' if letter == 'U' else letter)}, {plain_date(when)}"
                        + (f", replaced by {repl}" if repl else (f"; {remark}" if remark else "; no replacement named")) + ")")
    left = set(left_off)

    # the November rows, in ballot order (alphabetical by last name, then first name: 21-A MRS section 601(2)(B))
    gen_rows, order_breaks = [], []
    for rid, cands in listed.items():
        keep = [g for g in cands if (rid, g["name"]) not in left]
        by_alpha = sorted(keep, key=lambda g: (fold(g["last"]).replace(" ", ""), fold(g["first"])))
        if [g["seq"] for g in by_alpha] != sorted(g["seq"] for g in keep):
            order_breaks.append(rid)
        seen = set()
        for pos, g in enumerate(by_alpha, start=1):
            label = party_label(g["party"], "the 2026 General Election Candidates List")
            if fold(g["name"]) in seen:
                problems.append(f"{rid}: the same name twice on the November list ({g['name']})")
            seen.add(fold(g["name"]))
            note = None
            repl = replaced.get((rid, g["party"]))
            if repl and repl["replacement"] == g["name"]:
                note = f"Replacement candidate: nominated after {repl['withdrawn']} withdrew on {plain_date(repl['date'])}."
            gen_rows.append({"race_id": rid, "election": "general", "election_date": GENERAL, "name": g["name"], "party": label,
                             "party_code": fed.colour(label), "ballot_order": pos, "incumbent": 0, "write_in": 0, "votes": None,
                             "pct": None, "outcome": None, "state_member_id": None, "source_id": SRC["general"], "note": note,
                             "_letter": g["party"]})
    if order_breaks:
        notes_out.append(f"the list's own order is not alphabetical by last name in {len(order_breaks)} races "
                         f"({', '.join(sorted(order_breaks)[:8])}); ballot_order follows the statute's order")
    for office, d, c in write_ins:
        rid = race_id(office, d)
        name = pdf_name(c["name"])
        if any(names_fit(g["name"], name) for g in gen_rows if g["race_id"] == rid):
            problems.append(f"{rid}: declared write-in {name} is also printed on the November list")
            continue
        label = clean(c["party"])
        gen_rows.append({"race_id": rid, "election": "general", "election_date": GENERAL, "name": name, "party": label,
                         "party_code": fed.colour(label), "ballot_order": None, "incumbent": 0, "write_in": 1, "votes": None,
                         "pct": None, "outcome": None, "state_member_id": None, "source_id": SRC["write_ins"], "note": WRITE_IN,
                         "_letter": None})
    nominee = collections.defaultdict(list)
    for g in gen_rows:
        if g["_letter"] in PARTIES:
            nominee[(g["race_id"], g["_letter"])].append(g)

    # ---- the primary: who was printed on each party's ballot
    plisted, _pcounts = read_list(plist, "June 9, 2026", "the 2026 Primary Candidate List")
    pw_title, pwithdrawn, pw_rows, _pw_offices = state_pdf_rows(pwd, "primary_withdrawals", "the list of withdrawals before the primary")
    off_before, late_set = set(), set()
    pw_words, pre_repl = [], []
    for office, d, c in pwithdrawn:
        rid, letter, when = race_id(office, d), clean(c["party"]).upper(), date_of(c["date"])
        name = pdf_name(c["name"])
        if not when:
            raise SystemExit("Maine (state races): a withdrawal before the primary has no date that is read")
        (off_before if when <= PRIMARY_CUTOFF else late_set).add((rid, letter, name, when))
        rest = pdf_name(REMARK.sub("", c.get("replacement", ""))).strip(" -–—.,;")
        if rest and re.search(r"[A-Za-z]{2}", rest):
            pre_repl.append((rid, letter, rest))
        pw_words.append(f"{name} ({where_words(rid)}, {PARTIES.get(letter, letter)}, {plain_date(when)}"
                        + ("; name taken off the ballot)" if when <= PRIMARY_CUTOFF else "; name stayed on the ballot, votes not counted)"))
    printed, late = collections.defaultdict(list), {}
    for p in plisted:
        party_label(p["party"], "the 2026 Primary Candidate List")
        rid = race_id(p["office"], p["district"])
        if any(r == rid and l == p["party"] and names_fit(p["name"], n) for r, l, n, _w in off_before):
            continue
        hit = [w for r, l, n, w in late_set if r == rid and l == p["party"] and names_fit(p["name"], n)]
        if hit:
            late[(rid, p["party"], p["key"])] = (p["name"], hit[0])
            continue
        printed[(rid, p["party"])].append(p)
    for r, l, n, w in late_set:
        if not any(k[0] == r and k[1] == l and names_fit(v[0], n) for k, v in late.items()):
            problems.append(f"{r} {PARTIES.get(l, l)}: {n} withdrew late ({w}) but is not on the primary list")
    for rid, letter, name in pre_repl:
        problems.append(f"{rid}: a replacement named before the primary ({name}) is not handled; read the withdrawal list")

    # ---- the tabulations
    blocks = {}                      # (race, party letter) -> block, with the file key
    tab_info = {}
    for key, (fname, _url, title, office, letter, layout, district) in TABULATIONS.items():
        path = tab_paths[key]
        flags = []
        got = read_blocks(path, title, flags) if layout == "blocks" else [read_single(path, title, district, flags)]
        for n, off, where in flags:
            problems.append(f"{title}, row {n} ({where}): the candidates plus blanks are {off:+,} against the ballots cast (TBC) "
                            "the row prints; the total balances, and the votes are used as printed")
        tab_info[key] = {"flags": flags, "blocks": len(got), "rows": sum(b["rows"] for b in got), "ballots": sum(b["ballots"] for b in got),
                         "fields": 0, "cands": sum(len(b["cands"]) for b in got), "subtotals": sum(b.get("subtotals", 0) for b in got)}
        for b in got:
            rid = race_id(office, None if office == "GOV" else b["district"])
            if rid not in races:
                raise SystemExit(f"Maine (state races): {title} has a district that is not read ({b['district']})")
            if (rid, letter) in blocks:
                raise SystemExit(f"Maine (state races): {rid} {PARTIES[letter]} is tabulated twice ({blocks[(rid, letter)]['key']} and {key})")
            b["key"] = key
            blocks[(rid, letter)] = b
            races[rid]["counties"] |= b["counties"]
    # every party with a name printed has a tabulation, and every tabulation's names are exactly the names printed
    for k in set(printed) - set(blocks):
        problems.append(f"{k[0]} {PARTIES[k[1]]}: names printed on the primary ballot ({', '.join(p['name'] for p in printed[k])}) but no tabulation")
    fields, primary_rows, late_seen, rcv_used = 0, [], [], {}
    for (rid, letter), b in sorted(blocks.items()):
        title = TABULATIONS[b["key"]][2]
        names = {p["key"]: p for p in printed.get((rid, letter), [])}
        keys = {j: printed_key(n) for j, n in b["cands"].items()}
        for j, n in b["cands"].items():             # a two-word family name the list splits ('TALBOT ROSS, RACHEL', listed as Ross)
            if keys[j] not in names and (rid, letter, keys[j]) not in late:
                whole = fold(turned(n)).split()
                same = [p for p in printed.get((rid, letter), []) if fold(p["name"]).split() == whole]
                if len(same) == 1:
                    keys[j] = same[0]["key"]
        missing = set(names) - set(keys.values())
        if missing:
            problems.append(f"{rid} {PARTIES[letter]}: printed on the primary ballot but not in the tabulation: "
                            f"{', '.join(names[k]['name'] for k in missing)}")
        cols_late, cols_wi, shown = set(), set(), {}
        for j, k in keys.items():
            if (rid, letter, k) in late:
                cols_late.add(j)
                shown[j] = late[(rid, letter, k)][0]
                late_seen.append((rid, letter, shown[j], b["votes"][j]))
                if b["votes"][j]:
                    problems.append(f"{rid} {PARTIES[letter]}: {shown[j]} withdrew late, yet the tabulation counts {b['votes'][j]} votes")
                continue
            if k in names:
                shown[j] = names[k]["name"]
                continue
            if any(r == rid and l == letter and names_fit(turned(b["cands"][j]), n) for r, l, n, _w in off_before):
                problems.append(f"{rid} {PARTIES[letter]}: {b['cands'][j]} withdrew by March 31, yet is in the tabulation")
            cols_wi.add(j)
            shown[j] = proper(turned(b["cands"][j]))
        field = [j for j in b["cands"] if j not in cols_late]
        if len(field) < 2:
            continue
        fields += 1
        tab_info[b["key"]]["fields"] += 1
        on_ballot = [j for j in field if j not in cols_wi]
        total = sum(b["votes"][j] for j in field)
        ranked = sorted(field, key=lambda j: -b["votes"][j])
        if b["votes"][ranked[0]] == b["votes"][ranked[1]]:
            problems.append(f"{rid} {PARTIES[letter]}: a tie on first choices; read the Secretary's own result")
            continue
        rcv = len(on_ballot) >= 3 or (len(on_ballot) == 2 and cols_wi)
        majority = 2 * b["votes"][ranked[0]] > total
        report = RCV_REPORTS.get(b["key"])
        if not rcv:
            if report:
                raise SystemExit(f"Maine (state races): {title} has an RCV report but was not a ranked-choice contest")
            winner = ranked[0]
            note = ("Decided by plurality: with two candidates on the ballot and no declared write-in, Maine does not count a "
                    "primary by ranked choice." if len(on_ballot) == 2 else
                    "Decided by plurality: one name was printed on the ballot, and the other received write-in votes.")
        elif majority:
            if report:
                raise SystemExit(f"Maine (state races): {title} has an RCV report although its leader had a majority of first choices")
            winner = ranked[0]
            note = (f"Counted by ranked choice. {shown[winner]} had more than half of the first choices "
                    f"({b['votes'][winner]:,} of {total:,}), so no further round was counted.")
        else:
            if not report:
                problems.append(f"{rid} {PARTIES[letter]}: no candidate had a majority of first choices, and no RCV report is configured")
                continue
            rpath = rcv_paths[b["key"]]
            rep = rcv_report(rpath, report[2])
            by_key = {printed_key(n): n for n in rep["cands"]}
            col_of = {keys[j]: j for j in field}
            if set(by_key) != set(col_of) or rep["ballots"] != b["ballots"]:
                raise SystemExit(f"Maine (state races): {report[2]} does not count the same candidates and ballots as {title}")
            rep_col = {by_key[k]: col_of[k] for k in by_key}
            winner = rep_col[rep["winner"]]
            steps = [f"{' and '.join(shown[rep_col[c]] for c in out)} after round {k}" for k, out in enumerate(rep["dropped"], start=1) if out]
            final = [c for c in sorted(rep["cands"], key=lambda c: -rep["cands"][c][-1]) if rep["cands"][c][-1]]
            if len(final) != 2:
                raise SystemExit(f"Maine (state races): the final round of {report[2]} does not have two candidates")
            first_round = {rep_col[c]: v[0] for c, v in rep["cands"].items()}
            more = sum(first_round.values()) - total
            skipped = b["blank"] - rep["exhausted"][0]
            note = (f"Counted by ranked choice. The votes shown are first choices; no candidate had more than half of them, so "
                    f"the Secretary of State's central count dropped the last-placed candidate in each round: {', then '.join(steps)}. "
                    f"In the final round {shown[rep_col[final[0]]]} had {rep['cands'][final[0]][-1]:,} votes and "
                    f"{shown[rep_col[final[1]]]} {rep['cands'][final[1]][-1]:,} ({rep['exhausted'][-1]:,} ballots counted for "
                    f"neither), so {shown[winner]} won the nomination.")
            if more and more == skipped and all(first_round[j] >= b["votes"][j] for j in field):
                note += (f" The count's first round credits {more:,} more votes than the first choices shown: ballots that "
                         f"skipped the first choice were counted for their next one.")
            elif more:
                note += f" The count's first round credits {more:,} more votes than the first choices shown."
                problems.append(f"{rid} {PARTIES[letter]}: the RCV report's first round differs from the first choices by {more}, "
                                f"not explained by skipped first choices ({skipped})")
            rcv_used[b["key"]] = (rpath, rep)
        noms = nominee.get((rid, letter), [])
        repl = replaced.get((rid, letter))
        after = None
        if any(names_fit(n["name"], shown[winner]) for n in noms):
            pass
        elif repl and names_fit(repl["withdrawn"], shown[winner]):
            after = (f"Won the nomination, then withdrew on {plain_date(repl['date'])}"
                     + (f"; {repl['replacement']} was nominated as the replacement candidate." if repl["replacement"] else
                        "; no one replaces them on the November list."))
            repl["winner"] = True
        else:
            problems.append(f"{rid} {PARTIES[letter]}: the winner ({shown[winner]}) is not the party's candidate on the November list")
        for j in ranked:
            wi = j in cols_wi
            parts = [WRITE_IN if wi else "", CAPS if wi else "", note, after if j == winner and after else ""]
            primary_rows.append({"race_id": rid, "election": f"primary-{CODES[letter]}", "election_date": PRIMARY, "name": shown[j],
                                 "party": PARTIES[letter], "party_code": fed.colour(PARTIES[letter]), "ballot_order": None,
                                 "incumbent": 0, "write_in": int(wi), "votes": b["votes"][j],
                                 "pct": round(100 * b["votes"][j] / total, 1) if total else None,
                                 "outcome": "advanced" if j == winner else "lost", "state_member_id": None,
                                 "source_id": f"me-sos-2026-sl-primary-{b['key']}", "note": " ".join(p for p in parts if p) or None})
    for (rid, letter, _k), (name, when) in late.items():
        if not any(r == rid and l == letter and n == name for r, l, n, _v in late_seen):
            problems.append(f"{rid} {PARTIES.get(letter, letter)}: {name} withdrew late ({when}) but is not in any tabulation")
    # a replacement for a primary winner says so
    for g in gen_rows:
        repl = replaced.get((g["race_id"], g["_letter"]))
        if not repl or repl["replacement"] != g["name"]:
            continue
        alone = printed.get((g["race_id"], g["_letter"]), [])
        if repl.get("winner"):
            who = ", who won the June 9 primary,"
        elif len(alone) == 1 and names_fit(alone[0]["name"], repl["withdrawn"]):
            who = ", nominated unopposed at the June 9 primary,"
        else:
            who = ""
        g["note"] = f"Replacement candidate: nominated after {repl['withdrawn']}{who} withdrew on {plain_date(repl['date'])}."

    # ---- holders and incumbents
    members, officials, roster_as_of = roster(roster_path)
    incumbents = 0
    for r in races.values():
        if r["chamber"]:
            hold = [m for m in members if m["chamber"] == r["chamber"] and m["district"] == r["district"]]
        else:
            hold = [o for o in officials if o["office"] == "governor"]
        r["holder"] = hold
        if len(hold) != 1:
            problems.append(f"{r['race_id']}: {len(hold)} sitting members on the roster for this seat")
        for h in hold:
            for rows in ([g for g in gen_rows if g["race_id"] == r["race_id"]],
                         *[[p for p in primary_rows if p["race_id"] == r["race_id"] and p["election"] == e]
                           for e in sorted({p["election"] for p in primary_rows if p["race_id"] == r["race_id"]})]):
                hits = [g for g in rows if person_fits(g["name"], h)]
                if len(hits) == 1 and sum(1 for hh in hold if person_fits(hits[0]["name"], hh)) == 1:
                    hits[0]["incumbent"], hits[0]["state_member_id"] = 1, h["id"]
                    if rows and rows[0]["election"] == "general":
                        incumbents += 1
    tribal = [m for m in members if m["chamber"] == "House" and not m["district"].isdigit()]

    # ---- checks against the list
    counted = collections.Counter(g["race_id"] for g in gen_rows if not g["write_in"])
    kept = sum(counted.values())
    state_rows = sum(gen_counts[o] for o in OFFICES)
    if kept + len(left_off) != state_rows:
        problems.append(f"{kept} November rows kept and {len(left_off)} left off, against {state_rows} state rows on the list")
    for rid in races:
        if not counted[rid]:
            problems.append(f"{rid}: no candidate printed on the November ballot")
    no_counties = [rid for rid, r in races.items() if r["district"] and not r["counties"]]
    if no_counties:
        problems.append(f"no county read for {', '.join(no_counties)} (no primary tabulation for the district)")
    uncontested = sorted(rid for rid in races if counted[rid] == 1)
    all_cands = gen_rows + primary_rows
    keys = [(c["race_id"], c["election"], c["name"]) for c in all_cands]
    if len(set(keys)) != len(keys):
        raise SystemExit("Maine (state races): two candidate rows share a race, election and name")

    # ---- rows
    cmap = county_names()
    by_code = {code: geoid for code, (geoid, _n) in cmap.items()}
    bad = sorted({c for r in races.values() for c in r["counties"]} - set(by_code))
    if bad:
        raise SystemExit(f"Maine (state races): county codes in the tabulations that are not Maine's: {bad}")
    plurality = ("Decided by plurality on November 3, whatever the number of candidates (the Secretary of State's 2026 Candidate's "
                 "Guide to Ballot Access).")
    order_words = "Names are printed alphabetically by last name (21-A MRS section 601(2)(B)); ballot_order follows that rule."
    race_rows, place_rows = [], []
    for r in races.values():
        hold = r["holder"]
        cids = sorted(by_code[c] for c in r["counties"])
        notes = list(r["notes"]) + [plurality, order_words]
        if r["office_code"] == "GOV" and hold and not any(g["incumbent"] for g in gen_rows if g["race_id"] == r["race_id"]):
            notes.append(f"The sitting Governor ({hold[0]['full']}) is not on the November list.")
        race_rows.append((r["race_id"], STATE, r["level"], r["office_kind"], r["office"], r["jurisdiction"], r["jurisdiction_id"],
                          json.dumps(cids) if cids else None, r["district"], None, 0, 1,
                          "; ".join(h["id"] for h in hold) or None,
                          "; ".join(h["full"] or f"{h['first']} {h['last']}" for h in hold) or None,
                          "; ".join(h["party"] or "" for h in hold) or None, GENERAL, " ".join(notes)))
        if r["district"]:
            place_rows.append(("senate" if r["office_kind"] == "state_senate" else "house", f"{STATE}-{r['district']}",
                               r["jurisdiction"], json.dumps(cids) if cids else None, "me-sos-2026-sl-primary-results"))
    for code, (geoid, full) in sorted(cmap.items(), key=lambda kv: kv[1][0]):
        place_rows.append(("county", geoid, full, json.dumps([geoid]), SRC["county"]))

    not_loaded = {COUNTY_OFFICES[o]: n for o, n in gen_counts.items() if o in COUNTY_OFFICES}
    fed_rows = sum(gen_counts[o] for o in FEDERAL)
    repl_count = sum(1 for v in replaced.values() if v["replacement"])
    late_words = "; ".join(f"{n} ({where_words(rid)}, {PARTIES[l]}, {v} votes shown)" for rid, l, n, v in late_seen) or "none"
    wi_primary = [p for p in primary_rows if p["write_in"]]
    sources = [
        source_row(SRC["general"], "official candidate list", AGENCY,
                   "2026 General Election Candidates List (November 3, 2026): Governor, State Senator and Representative to the Legislature",
                   links["general"][0], links["general"][1], day_of(paths["general"]), sha_file(paths["general"]), state_rows,
                   f"Every office's rows read ({sum(gen_counts.values())}); only Office, Dist, Party and the name columns taken, the town of "
                   f"residence and the unheaded columns never read. State rows: Governor {gen_counts['GOV']}, State Senator {gen_counts['SS']}, "
                   f"Representative to the Legislature {gen_counts['SR']}; withdrawn and still listed, left off: {len(left_off)}. Not loaded here: "
                   f"Congress ({fed_rows} rows, the federal loader's) and county offices ("
                   + "; ".join(f"{k} {v}" for k, v in sorted(not_loaded.items())) + "). The list gives no ballot positions; ballot_order is "
                   "the statute's alphabetical order by last name" + (f" (the list's own order differs in {len(order_breaks)} races)" if order_breaks else
                                                                     ", which is also the list's own order in every race") + "."),
        source_row(SRC["withdrawals"], "official candidate list", AGENCY,
                   "Candidate Withdrawals and Replacement Candidate Nominations after the June 9, 2026 Primary",
                   links["withdrawals"][0], fed.published_of(wd_title, links["withdrawals"][1]), day_of(paths["withdrawals"]),
                   sha_file(paths["withdrawals"]), len(withdrawals),
                   f"{wd_rows} rows, every office; state offices {len(withdrawals)}: {'; '.join(wd_words) or 'none'}. Only the office, district, "
                   f"party, name, date and replacement columns are read; {repl_count} replacements found on the general list."),
        source_row(SRC["write_ins"], "official candidate list", AGENCY, "Declared Write-in Candidates for the November 3, 2026 General Election",
                   links["write_ins"][0], fed.published_of(wi_title, links["write_ins"][1]), day_of(paths["write_ins"]),
                   sha_file(paths["write_ins"]), len(write_ins),
                   f"{wi_rows} rows, every office; {len(write_ins)} for state offices, added as declared write-in candidates with the "
                   "designation as printed. Only the office, district, party and name columns are read."),
        source_row(SRC["plist"], "official candidate list", AGENCY, "2026 Primary Candidate List (June 9, 2026)", fed.PRIMARY_LIST[1],
                   "2026-03-16", day_of(plist), sha_file(plist), len(plisted),
                   "Used to check the tabulations (the names printed on each party's ballot) and for the names in ordinary capitals. "
                   "Only Office, Dist, Party and the name columns taken."),
        source_row(SRC["pwithdrawals"], "official candidate list", AGENCY,
                   "Candidate Withdrawals and Replacement Candidate Nominations for the June 9, 2026 State Primary Election",
                   fed.PRIMARY_WITHDRAWALS[1], fed.published_of(pw_title), day_of(pwd), sha_file(pwd), len(pwithdrawn),
                   f"{pw_rows} rows, every office; state offices: {'; '.join(pw_words) or 'none'}. Withdrawn after March 31 and still "
                   f"printed (left out of the field): {late_words}."),
    ]
    for key, (fname, url, title, office, letter, layout, district) in TABULATIONS.items():
        t = tab_info[key]
        what = ("The Secretary of State's ranked-choice central count, first choices" if key in RCV_REPORTS
                else "The Secretary of State's final tabulation")
        sources.append(source_row(
            f"me-sos-2026-sl-primary-{key}", "official results", AGENCY, title, FILES + url, "", day_of(tab_paths[key]),
            sha_file(tab_paths[key]), t["cands"],
            f"{what}: {t['blocks']} {('district' if t['blocks'] == 1 else 'districts') if layout == 'blocks' else 'contest'}, {t['rows']} rows (municipalities, wards and the "
            f"UOCAVA ballots) adding up to each total" + (f" and to {t['subtotals']} county subtotals" if t["subtotals"] else "")
            + (f"; each row's candidates plus blanks equal its ballots cast" if not t["flags"] else
               f"; each total's candidates plus blanks equal its ballots cast, and every row's do except "
               + ", ".join(f"row {n} ({where}, {off:+,})" for n, off, where in t["flags"]) + ", where the file's own ballots-cast cell disagrees")
            + f" ({t['ballots']:,} ballots). {t['fields']} with a field. "
            "The line under each name (the candidate's town) is never read. Shares are of the candidates, blank ballots left out."))
    for key, (rpath, rep) in sorted(rcv_used.items()):
        sources.append(source_row(
            f"me-sos-2026-sl-primary-{key}-rcv", "official results", AGENCY, RCV_REPORTS[key][2], FILES + RCV_REPORTS[key][1], "",
            day_of(rpath), sha_file(rpath), len(rep["cands"]),
            f"{rep['rounds']} rounds; threshold {rep['threshold']:,}; won by {turned(rep['winner'])}; each round's candidates plus "
            f"exhausted ballots equal the {rep['ballots']:,} ballots cast in the first-choice tabulation. Gives the outcome and the row "
            "note; the votes stored are the first choices."))
    sources.append(source_row("me-sos-2026-sl-primary-results", "official results", AGENCY,
                              "June 9, 2026 Primary Election tabulations (Election Results/Data page): the counties each district reaches",
                              RESULTS_PAGE, "", "", "", len(place_rows) - len(cmap),
                              "Each Senate and House district's counties are the county column of its municipal rows in either party's "
                              "tabulation (see the me-sos-2026-sl-primary-* rows)."))
    sources.append(source_row(SRC["guide"], "official guide", AGENCY, "2026 Candidate's Guide to Ballot Access", GUIDE_URL, "",
                              guide[1], guide[0], None,
                              "Ranked-Choice Voting (RCV): the June 9 primaries for Governor, State Senate and State Representative were "
                              "decided by ranked choice with three or more candidates, or two and a declared write-in; the November 3 "
                              "election for these offices is decided by plurality. Restrictions on Candidate Withdrawal: a name comes off "
                              "the June ballot on a withdrawal by March 31 and off the November ballot by August 25; later, it stays "
                              "printed and its votes are not counted. Read in memory to check these sentences; not kept."
                              + ("" if guide[0] else " Not re-read this run.")))
    sources.append(source_row(SRC["statute"], "statute", "Maine Legislature, Revisor of Statutes",
                              "21-A MRS section 601, Specifications (ballots), subsection 2, paragraph B", STATUTE_URL, "", statute[1],
                              statute[0], None,
                              "The ballot lists the candidates' names arranged alphabetically with the last name first, under the office: "
                              "the basis of ballot_order. Read in memory; not kept." + ("" if statute[0] else " Not re-read this run.")))
    sources.append(source_row(SRC["county"], "official place names", "U.S. Census Bureau", "Cartographic boundary file, counties, 1:500,000 (2024)",
                              COUNTY_URL, "", day_of(COUNTY_ZIP), sha_file(COUNTY_ZIP), len(cmap),
                              "Maine's 16 counties: names and GEOIDs only; the tabulations' three-letter county codes are the first three "
                              "letters of each name."))
    if members or officials:
        sources.append(source_row(SRC["roster"], "roster", "Open States (people project, CC0)",
                                  "Legislators serving now and statewide officials (state_me.sqlite, from the Open States people project)",
                                  "https://github.com/openstates/people", roster_as_of, day_of(roster_path), sha_file(roster_path),
                                  len(members) + len(officials),
                                  "Used only to say who holds each seat today and to mark incumbents: ids, names, parties and districts. "
                                  f"Not an official record. The House's {len(tribal)} tribal representatives "
                                  f"({', '.join(m['district'] for m in tribal) or 'none'}) are not on the Secretary of State's list."))

    ccols = ("race_id", "election", "election_date", "name", "party", "party_code", "ballot_order", "incumbent", "write_in", "votes",
             "pct", "outcome", "state_member_id", "source_id", "note")
    con = sqlite3.connect(db_path)
    try:
        con.executescript(SCHEMA)
        with con:
            con.execute("DELETE FROM sl_candidates WHERE race_id IN (SELECT race_id FROM sl_races WHERE state = ?) OR race_id LIKE ?",
                        (STATE, f"2026-{STATE}-%"))
            con.execute("DELETE FROM sl_races WHERE state = ?", (STATE,))
            con.execute("DELETE FROM sl_sources WHERE state = ?", (STATE,))
            con.execute("DELETE FROM sl_places WHERE source_id LIKE 'me-%' OR (kind IN ('senate', 'house') AND id LIKE ?) "
                        "OR (kind = 'county' AND id LIKE ?)", (f"{STATE}-%", f"{FIPS}___"))
            con.executemany("INSERT INTO sl_races VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", race_rows)
            con.executemany(f"INSERT INTO sl_candidates VALUES ({','.join('?' * len(ccols))})", [tuple(c[k] for k in ccols) for c in all_cands])
            con.executemany("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", sources)
            con.executemany("INSERT INTO sl_places VALUES (?,?,?,?,?)", place_rows)
    finally:
        con.close()

    by_kind = collections.Counter(r["office_kind"] for r in races.values())
    gen_by_kind = collections.Counter(races[g["race_id"]]["office_kind"] for g in gen_rows)
    say(f"    Maine: {len(races)} state races on the November ballot (Governor {by_kind['governor']}, Senate {by_kind['state_senate']}, "
        f"House {by_kind['state_house']}), {len(gen_rows)} candidates ({sum(g['write_in'] for g in gen_rows)} declared write-ins, "
        f"{len(left_off)} withdrawn and left off, {repl_count} replacements); {fields} primary fields with official votes "
        f"({len(primary_rows)} rows, {len(rcv_used)} decided in the ranked-choice central count, {len(wi_primary)} write-in rows); "
        f"{incumbents} incumbents marked; {len(uncontested)} races with one candidate")
    for p in problems:
        say(f"      CHECK {p}")
    for n in notes_out:
        say(f"      note: {n}")
    return {"races": len(races), "candidates": len(gen_rows), "by_kind": dict(by_kind), "general_by_kind": dict(gen_by_kind),
            "fields": fields, "primary_rows": len(primary_rows), "incumbents": incumbents, "problems": problems, "notes": notes_out,
            "uncontested": uncontested, "left_off": left_off, "replacements": repl_count, "late": late_seen,
            "not_loaded": not_loaded, "rcv": sorted(rcv_used), "write_ins_primary": [(p["race_id"], p["name"]) for p in wi_primary]}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", required=True, help="the state-and-local ballot database to write Maine's rows into")
    ap.add_argument("--cache", default=DEFAULT_CACHE)
    ap.add_argument("--no-fetch", action="store_true", help="use the cached files as they are")
    a = ap.parse_args()
    load(a.db, cache=a.cache, fetch=not a.no_fetch)
