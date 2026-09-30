"""
ballot/state_local_az.py - Arizona's state races on the November 3, 2026 ballot: all 30 seats of the State Senate and
all 60 seats of the House of Representatives (two members a district), Governor with Lieutenant Governor (one ticket),
Secretary of State, Attorney General, State Treasurer, Superintendent of Public Instruction, State Mine Inspector and
the Corporation Commission seats on this year's ballot, with each party's July 21 primary field and its official votes.
Written into ballot_local_2026.sqlite (never ballot_2026.sqlite).

    python -m ballot.state_local_az <database file> [folder]      load (folder: where the saved files are)
    python -m ballot.state_local_az --probe general|writein|canvass [folder]

Which seats and offices are on the 2026 ballot, from the Arizona Constitution as the Legislature publishes it
(azleg.gov, which answers scripts; read into memory at each run, checked for the sentences below, fingerprinted, and
kept as a small extract, az_constitution_2026.json, beside the saved files for a run when azleg.gov cannot be reached):
  Article 4, Part 2, Section 1   one senator and two representatives from each of the thirty legislative districts;
  Article 4, Part 2, Section 21  every legislator's term is two years, so both chambers are elected in full;
  Article 5, Section 1           Governor, Lieutenant Governor, Secretary of State, Attorney General, State Treasurer and
                                 Superintendent of Public Instruction serve four years from January 1971, after the 1970
                                 election (so 2026 is an election year); each nominee for Governor names a running mate
                                 and one vote chooses the ticket;
  Article 19                     the Mine Inspector is elected at general elections (the Legislature prints two versions:
                                 four-year terms from the 1994 election, and two-year terms; either way 2026 elects one);
  Article 15, Section 1          five Corporation Commissioners with four-year terms. How many seats are up in 2026 is not
                                 in the text, so that race comes only from the candidate listing or the canvass (its
                                 "Vote for" line gives the number of seats).
Judicial retention questions (Supreme Court, Court of Appeals, superior courts) are not loaded; rows under a judicial
heading are counted and reported, never stored.

The candidates come from the Arizona Secretary of State's own files, the same ones the federal loader
(ballot/lists/az.py) reads. Every Secretary of State host (azsos.gov, apps.azsos.gov, results.arizona.vote) answers
scripts with a Cloudflare challenge, which is never worked around, so this loader downloads nothing from them. It reads
what John saves from his own browser into ballot_cache/az/:
  az_2026_general_candidates.pdf (or .xlsx / .csv)   the Candidate Listing for the 2026 General Election
  az_2026_general_write_in_withdrawn.pdf              the 2026 General Write-In and Withdrawn Candidate List (optional)
  az_2026_primary_canvass.pdf                         the Official Canvass of the July 21, 2026 primary
Until the listing is saved, the races are stored with today's holders and no candidates, and the report says what is
waiting. Until the canvass is saved, no primary fields are stored.

Privacy, in every step. The listing may carry addresses, cities, ZIP codes, phones, websites and e-mail. On a PDF page
the row of column headings is found by its words and only the bands under Candidate Name (or Last, First, Middle,
Suffix), Party, Office, District, Status and Ballot Order are ever turned into text; a row with nothing in the name
band is looked at only through its first cell, and only when that cell starts in one of those bands (an office heading
printed from the left margin). A workbook or CSV is cut to the same columns as each row is read. Only name, office,
district, party, status and ballot order reach the database; nothing else from any file is printed, logged, cached or
stored, and a message about a row names its page and the allowlisted cells at most. A listing with no row of headings
is read line by line only under state office headings, where a line is taken only when it is a name and a party and
any other line stops the loader without printing it. The canvass is a results book (offices, names, votes).

Parties are kept as printed and written out where abbreviated, as ballot/lists/az.py does. Names printed "Last, First"
are turned round; names printed in capitals are shown in ordinary capitals (with the Open States roster's capitals for
a sitting member whose letters are the same), with a note. No ballot order is stored unless the listing has a Ballot
Order column: the listing's own order is not taken for the order on the ballot.

Who holds each seat comes from state_az.sqlite (legislators serving today, by chamber and district; the officials
table for Governor, Secretary of State and Attorney General). A candidate is the sitting member (incumbent 1,
state_member_id) only when the name fits a holder of that same seat, and that holder fits no one else in the race.

Primaries: a party primary is a field when more names were printed on that party's ballot than it nominates (two for a
House district, the "Vote for" number for the Corporation Commission, one otherwise). Arizona nominates by plurality:
the candidates with the most votes advanced; a tie at the cut stops the loader. Shares are of all votes cast in that
party's contest, unnamed write-ins included. Every table's counties must add up to its totals.
"""

import datetime as dt
import hashlib
import html
import json
import os
import re
import sqlite3
import sys
from collections import Counter, defaultdict

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ballot.common import CACHE, HERE, fold, name_parts, party_code  # noqa: E402
from ballot.lists import az as fed                                    # noqa: E402
from ballot.lists.tx import proper                                    # noqa: E402
from ballot.match import fits                                         # noqa: E402
from ballot.pdftext import PDF, join, rows as pdf_rows                # noqa: E402
from states import net                                                # noqa: E402

STATE, FIPS, NAME = "AZ", "04", "Arizona"
GENERAL, PRIMARY = fed.GENERAL_DATE, fed.PRIMARY
DISTRICTS = 30
ROSTER_DB = os.path.join(HERE, "state_az.sqlite")
EXTRACT = "az_constitution_2026.json"
AGENCY = fed.AGENCY
SRC_LIST, SRC_WRITEIN, SRC_CANVASS = "az-sos-2026-general-list-state", "az-sos-2026-general-write-in-state", "az-sos-2026-primary-canvass-state"
SRC_ROSTER, SRC_CONST = "az-openstates-roster", "az-constitution"

SCHEMA = """
CREATE TABLE IF NOT EXISTS sl_races (race_id TEXT PRIMARY KEY, state TEXT NOT NULL, level TEXT NOT NULL, office_kind TEXT NOT NULL, office TEXT NOT NULL, jurisdiction TEXT, jurisdiction_id TEXT, county_ids TEXT, district TEXT, seat TEXT, special INTEGER NOT NULL DEFAULT 0, partisan INTEGER NOT NULL, holder_id TEXT, holder_name TEXT, holder_party TEXT, election_date TEXT NOT NULL, note TEXT);
CREATE TABLE IF NOT EXISTS sl_candidates (race_id TEXT NOT NULL, election TEXT NOT NULL, election_date TEXT, name TEXT NOT NULL, party TEXT, party_code TEXT, ballot_order INTEGER, incumbent INTEGER NOT NULL DEFAULT 0, write_in INTEGER NOT NULL DEFAULT 0, votes INTEGER, pct REAL, outcome TEXT, state_member_id TEXT, source_id TEXT, note TEXT, PRIMARY KEY (race_id, election, name));
CREATE TABLE IF NOT EXISTS sl_sources (source_id TEXT PRIMARY KEY, state TEXT, kind TEXT, agency TEXT, title TEXT, url TEXT, published TEXT, fetched TEXT, sha256 TEXT, rows INTEGER, note TEXT);
CREATE TABLE IF NOT EXISTS sl_places (kind TEXT NOT NULL, id TEXT NOT NULL, name TEXT NOT NULL, county_ids TEXT, source_id TEXT, PRIMARY KEY (kind, id));
"""

# The Constitution, as the Legislature publishes it: (key, address, sentences that must still be there, lower case)
CONSTITUTION = (
    ("legislature", "https://www.azleg.gov/const/4/1.p2.htm",
     ("the senate shall be composed of one member elected from each of the thirty legislative districts",
      "the house of representatives shall be composed of two members elected from each of the thirty legislative districts")),
    ("terms", "https://www.azleg.gov/const/4/21.p2.htm",
     ("the terms of office of the members of succeeding legislatures shall be two years",)),
    ("executive", "https://www.azleg.gov/const/5/1.htm",
     ("the executive department shall consist of the governor, lieutenant governor, secretary of state, attorney general, state "
      "treasurer and superintendent of public instruction, each of whom shall hold office for four years beginning on the first "
      "monday of january, 1971 next after the regular general election in 1970",
      "a single vote for a nominee for governor shall constitute a vote for that nominee's ticket")),
    ("mine", "https://www.azleg.gov/const/19/0.htm",
     ("shall be elected at general elections, and shall serve for four years",
      "the initial four year term shall be served by the mine inspector elected in the general election held in november, 1994")),
    ("commission", "https://www.azleg.gov/const/15/1.htm",
     ("composed of five persons who shall be elected at the general election, and whose term of office shall be four years",)),
)
CONST_PAGE = "https://www.azleg.gov/constitution/"

# statewide offices: key -> (office_kind, office as shown, what the roster's officials.office calls it)
SW = {
    "GOV": ("governor", "Governor and Lieutenant Governor", ("governor",)),
    "SOS": ("secretary_of_state", "Secretary of State", ("secretary of state",)),
    "AG": ("attorney_general", "Attorney General", ("attorney general",)),
    "TREAS": ("state_treasurer", "State Treasurer", ("treasurer", "state treasurer")),
    "SPI": ("superintendent_of_public_instruction", "Superintendent of Public Instruction", ("superintendent of public instruction",)),
    "MINE": ("state_mine_inspector", "State Mine Inspector", ("mine inspector", "state mine inspector")),
    "CC": ("corporation_commissioner", "Corporation Commissioner", ("corporation commissioner",)),
}
FROM_RECORD = ("GOV", "SOS", "AG", "TREAS", "SPI", "MINE")      # on the 2026 ballot by the Constitution's own words
NEW_KINDS = ("state_mine_inspector", "corporation_commissioner")

FEDERAL = re.compile(r"(?i)\b(?:U\.?\s*S\.?|United\s+States)\s+(?:Senat|Rep|House|Congress)|\bRep(?:resentative|\.)?\s+in\s+Congress\b"
                     r"|\bCongressional\b")
COURT = re.compile(r"(?i)^(?:retention\b|shall\b|justice\b|judge\b|(?:arizona\s+)?supreme\s+court\b|court\s+of\s+appeals\b|superior\s+court\b)")
OTHER_OFFICE = re.compile(r"(?i)^(?:precinct\s+committee|board\s+of\s+supervisors|county\b|constable|mayor|council|school|community\s+college|"
                          r"proposition|prop\.?\s*\d|justice\s+of\s+the\s+peace|sheriff|recorder|assessor|clerk|treasurer\s*-\s*county|"
                          r"special\s+district|fire\s+district|central\s+arizona)")
DIST = re.compile(r"(?i)\b(?:Legislative\s+)?Dist(?:rict|\.)?\s*(?:No\.?\s*|Number\s+|#\s*)?0*(\d{1,2})\b|\bLD\s*-?\s*0*(\d{1,2})\b")
LD_LINE = re.compile(r"(?i)^\W*(?:Legislative\s+District|LD)\s*(?:No\.?\s*|#\s*)?0*(\d{1,2})\W*$")
SPECIAL = re.compile(r"(?i)\b(?:short\s+term|unexpired|vacancy|special)\b")
VOTE_FOR = re.compile(r"(?i)\bvote\s+for\s+(?:not\s+more\s+than\s+|up\s+to\s+|no\s+more\s+than\s+)?(\d)\b")
OFFICE_WORDS = re.compile(r"(?i)\bState\s+Rep(?:resentative|\.)?\b|\bState\s+Senat(?:or|e)\b|\bState\s+House\b|\bHouse\s+of\s+Representatives\b"
                          r"|\bDist(?:rict|\.)?\s*(?:No\.?\s*|#\s*)?\d{1,2}\b|\bLD\s*-?\s*\d{1,2}\b|\bLegislative\b|\bCorporation\s+Commission(?:ers?)?\b"
                          r"|\bvote\s+for\b[^)]*|\bGovernor\b|\bLieutenant\b|\bSecretary\s+of\s+State\b|\bAttorney\s+General\b|\bTreasurer\b"
                          r"|\bSuperintendent\s+of\s+Public\s+Instruction\b|\bMine\s+Inspector\b|\bState\b")
TICKET = re.compile(r"\s+/\s+|\s+&\s+|\s+and\s+(?=[A-Z])")
WRITE_IN_NOTE = fed.WRITE_IN_NOTE
CAPS_LIST, CAPS_CANVASS = fed.CAPS_LIST, fed.CAPS_CANVASS
NOT_ON_LIST = "Won the primary but is not on the November list."


class Stop(SystemExit):
    pass


def stop(msg):
    raise Stop(f"Arizona (state races): {msg}")


# ------------------------------------------------------------------------------------------------------ offices

def office_of(text, ld=None):
    """What a printed office names: a race dict for a state office on this ballot; "federal", "court" or "other" for
    an office this loader does not store; "mate" for a Lieutenant Governor heading; "need_district" for a legislative
    office printed without its district; None when the text is not an office at all. The office words must begin the
    text (after "For" or "Candidates for"), so a sentence that mentions an office is never taken for one."""
    t = " ".join(str(text or "").split())
    t = re.sub(r"(?i)^(?:official\s+)?(?:candidates?\s+for|for)\s+", "", t)
    if not t or len(t) > 120:
        return None
    u = t.upper()
    if FEDERAL.search(t):
        return "federal"
    if OTHER_OFFICE.match(t):
        return "other"
    if re.match(r"LIEUTENANT GOVERNOR\b", u):
        return "mate"
    if re.match(r"(?:STATE\s+)?GOVERNOR\b", u):
        return race("GOV")
    for key, pattern in (("SOS", r"SECRETARY OF STATE\b"), ("AG", r"ATTORNEY GENERAL\b"), ("TREAS", r"(?:STATE\s+)?TREASURER\b"),
                         ("SPI", r"(?:STATE\s+)?SUPERINTENDENT OF PUBLIC INSTRUCTION\b"), ("MINE", r"(?:STATE\s+)?MINE INSPECTOR\b"),
                         ("CC", r"(?:ARIZONA\s+)?CORPORATION COMMISSION(?:ER|ERS)?\b")):
        if re.match(pattern, u):
            vf = VOTE_FOR.search(t) if key == "CC" else None
            return race(key, special=bool(SPECIAL.search(t)), seats=int(vf.group(1)) if vf else None)
    chamber = "SS" if re.match(r"STATE\s+SENAT(?:OR|E)\b", u) else "SH" if re.match(r"STATE\s+(?:REP(?:RESENTATIVE|\.)?|HOUSE)\b", u) else None
    if chamber:
        m = DIST.search(t)
        d = int(next(g for g in m.groups() if g)) if m else ld
        if d is None:
            return "need_district"
        if not 1 <= int(d) <= DISTRICTS:
            stop(f"an office heading names legislative district {d}; Arizona has {DISTRICTS}")
        return race(chamber, int(d), special=bool(SPECIAL.search(t)))
    if COURT.search(t):
        return "court"
    return None


def race(key, district=None, special=False, seats=None):
    """The race a key stands for: race_id, level, office_kind, office, jurisdiction, district, seats, chamber. The
    Corporation Commission's seats are None until a file's "Vote for" line gives them."""
    if key in ("SS", "SH"):
        d = str(int(district))
        senate = key == "SS"
        return {"race_id": f"2026-{STATE}-{key}{d}" + ("-S" if special else ""), "key": key, "level": "legislature",
                "office_kind": "state_senate" if senate else "state_house", "office": "State Senator" if senate else "State Representative",
                "jurisdiction": f"Legislative District {d}", "jurisdiction_id": d, "district": d, "special": int(bool(special)),
                "seats": 1 if (senate or special) else 2, "chamber": "Senate" if senate else "House", "roster": None}
    kind, office, roster_names = SW[key]
    return {"race_id": f"2026-{STATE}-{key}" + ("-S" if special else ""), "key": key, "level": "statewide", "office_kind": kind,
            "office": office + (" (unexpired term)" if special else ""), "jurisdiction": NAME, "jurisdiction_id": FIPS, "district": None,
            "special": int(bool(special)), "seats": seats if key == "CC" else 1, "chamber": None, "roster": roster_names}


def title_party(text):
    """The party a contest title names, as (label, code), with the office's own words set aside first (so the "Rep." of
    "State Rep." is never read as Republican), else None."""
    rest = OFFICE_WORDS.sub(" ", text or "")
    for m in reversed(list(re.finditer(rf"\b({fed.PARTY_ANY})\b", rest, re.I))):
        p = fed.party_of(m.group(1))
        if p:
            return p
    return None


# ------------------------------------------------------------------------------------------------------ names

def spellings(members):
    out = {}
    for p in members:
        for form in (p["full"], f"{p['first']} {p['last']}"):
            if form and form.strip():
                out[" ".join(form.upper().split())] = " ".join(form.split())
    return out


def shown(raw, spell):
    """(name as shown, printed in capitals?): 'DOE, JANE Q.' -> 'Jane Q. Doe'; the roster's capitals for a sitting
    member whose letters are the same; otherwise ordinary capitals."""
    name = " ".join(str(raw or "").split())
    name = fed.WIN_MARK.sub("", name).strip()
    name = re.sub(r"(?i)\s*\((?:i|inc\.?|incumbent)\)\s*$", "", name).strip()
    given = family = None
    last, sep, rest = name.partition(",")
    if sep and rest.strip() and not fed.SUFFIX.match(rest.strip()):
        words, rest_words = last.split(), rest.replace(",", " ").split()
        suffixes = [w for w in words + rest_words if fed.SUFFIX.match(w)]
        given = " ".join(w for w in rest_words if not fed.SUFFIX.match(w))
        family = " ".join([w for w in words if not fed.SUFFIX.match(w)] + suffixes)
        name = f"{given} {family}"
    caps = any(c.isalpha() for c in name) and name == name.upper()
    if not caps:
        return name, False
    if name in spell:
        return spell[name], True
    fixed = f"{proper(given)} {proper(family)}" if family else proper(name)
    return re.sub(r"(['\"(“])([a-z])", lambda m: m.group(1) + m.group(2).upper(), fixed), True


def same(a, b):
    return fits(name_parts(a), name_parts(b))


# ------------------------------------------------------------------------------------------------ the listings

def first_cell(runs, bands):
    """The leftmost cell of a printed row, when it starts inside an allowlisted band (an office heading printed from
    the left margin); else ''. Nothing else of a row without a name is turned into text."""
    cs = fed.cells(runs)
    if not cs:
        return ""
    a, _b, rs = cs[0]
    band = next((f for lo, hi, f in bands if lo <= a < hi), None) if bands else "margin"
    return join(rs) if band else ""


def no_name(t, st, report):
    """A row with nothing in the name band, seen through its first cell: an office heading, a legislative district
    heading, a party alone, a write-in or withdrawn section, or nothing (let go unread)."""
    if not t or fed.CONTACTISH.search(t):
        return
    m = LD_LINE.match(t)
    if m:
        st.update(ld=int(m.group(1)), heading="", party=None)
        return
    got = office_of(t, st["ld"])
    if got is not None:
        st.update(heading=t, party=None, office=None)
        report["headings"].append(t[:60])
        return
    p = fed.party_line(t)
    if p and len(t) <= 40:
        st["party"] = t
        return
    if len(t) <= 80 and fed.SECTION_WI.search(t) and not fed.SECTION_WD.search(t):
        st["section"] = "write-in"
    elif len(t) <= 80 and fed.SECTION_WD.search(t) and not fed.SECTION_WI.search(t):
        st["section"] = "withdrawn"


def band_records(pdf, report):
    """A PDF listing read by the bands of its column headings: [{field: text, heading, ld, section, page}], or None when
    no page has a row of headings."""
    out, bands, found = [], None, False
    st = {"heading": "", "ld": None, "party": None, "section": None, "office": None}
    for pno, (page, res) in enumerate(pdf.pages(), start=1):
        for _y, runs in pdf_rows(pdf, page, res):
            b = fed.header_bands(runs)
            if b:
                bands, found = b, True
                heads = [join(rs) for _a, _b, rs in fed.cells(runs)]
                report["heading_rows"].append(([h for h in heads if fed.head_field(h)], sum(1 for h in heads if not fed.head_field(h))))
                continue
            if not bands:
                no_name(first_cell(runs, None), st, report)      # a title or an office heading above the first row of headings
                continue
            got = {}
            for r in runs:
                field = next((f for lo, hi, f in bands if lo <= r[0] < hi), None)
                if field:
                    got.setdefault(field, []).append(r)
            rec = fed.compose({f: join(rs) for f, rs in got.items()})
            nm = rec.get("name", "")
            kind = office_of(nm, st["ld"])            # a candidate row has a party; a judge's row ("JUDGE, JUDY") has a comma
            heading_like = kind is not None and not fed.party_of(rec.get("party", "")) and not (kind in ("court", "other") and "," in nm)
            if not nm or heading_like or LD_LINE.match(nm) or fed.SECTION_LINE.match(nm) \
                    or (fed.party_line(nm) and len(got) == 1):
                no_name(first_cell(runs, bands), st, report)
                continue
            if rec.get("office"):
                st["office"] = (rec["office"], rec.get("district", ""))
            elif any(f == "office" for _lo, _hi, f in bands) and st["office"]:
                rec["office"], d = st["office"]                   # an office printed once for the rows under it
                rec.setdefault("district", d)
            if not rec.get("party") and st["party"]:
                rec["party"] = st["party"]
            rec.update({"heading": st["heading"], "ld": st["ld"], "section": st["section"], "page": pno})
            out.append(rec)
    return out if found else None


def line_records(pdf, report):
    """A PDF listing with no row of column headings, line by line: under a state office heading a line is taken only
    when it is a name and a party (printed apart, or 'Name (DEM)'), or a name under a line naming the party alone. Any
    other line there stops the loader, which prints none of them. Lines under other headings are let go unread."""
    out, odd = [], Counter()
    st = {"heading": "", "ld": None, "party": None, "section": None, "office": None}
    party_first = re.compile(rf"^\(?({fed.PARTY_ANY})\)?\s+(.+)$", re.I)
    for pno, (page, res) in enumerate(pdf.pages(), start=1):
        for _y, runs in pdf_rows(pdf, page, res):
            t = join(runs)
            if fed.FOOTER.match(t) or fed.NOT_HEAD.match(t):
                continue
            kind = office_of(t, st["ld"])             # "SHERIFF, SAM (REP)" is a candidate, not a sheriff's heading
            if LD_LINE.match(t) or (kind is not None and not (kind in ("court", "other") and fed.split_party(t)[1])) \
                    or (fed.party_line(t) and len(t) <= 40) or fed.SECTION_LINE.match(t):
                no_name(t, st, report)
                continue
            if not isinstance(office_of(st["heading"], st["ld"]), dict) and office_of(st["heading"], st["ld"]) != "mate":
                continue
            name = party = None
            cs = [join(rs) for _a, _b, rs in fed.cells(runs)]
            if len(cs) == 2 and fed.party_of(cs[1]):
                name, party = cs
            elif len(cs) == 2 and fed.party_of(cs[0]):
                party, name = cs
            elif len(cs) == 1 and fed.split_party(t)[1]:
                name, party = fed.split_party(t)
            elif len(cs) == 1 and party_first.match(t) and len(party_first.match(t).group(1)) <= 4:
                party, name = party_first.match(t).group(1), party_first.match(t).group(2)
            elif len(cs) == 1 and (st["party"] or st["section"] == "write-in"):
                name, party = t, st["party"]
            if name and fed.NAME_OK.match(name.replace("/", " ").replace("&", " ")) and len(name.split()) <= 12 and not fed.CONTACTISH.search(t):
                out.append({"name": name, "party": party or "", "heading": st["heading"], "ld": st["ld"], "section": st["section"], "page": pno})
            else:
                odd[pno] += 1
    if odd:
        stop(f"the listing has no row of column headings, and {sum(odd.values())} line(s) under state office headings (pages "
             f"{sorted(odd)[:10]}) are not a name and a party alone; run python -m ballot.state_local_az --probe general")
    return out


def read_listing(path, report):
    """The rows of a saved listing, allowlisted fields only."""
    if path.lower().endswith((".xlsx", ".csv")):
        recs, heads = fed.records_from_book(path)
        report["heading_rows"].append(([h for h in heads if fed.head_field(h)], 0))
        for r in recs:
            r.setdefault("ld", None)
        return recs
    pdf = PDF(fed.saved(path, "pdf"))
    recs = band_records(pdf, report)
    return recs if recs is not None else line_records(pdf, report)


def place_rows(recs, spell, report):
    """Each listing row placed: [(race dict or kind, name as printed, party as printed, status, order, section, page)]."""
    out = []
    for rec in recs:
        if rec.get("office"):
            district = (rec.get("district") or "").strip()
            text = rec["office"]
            if district and not DIST.search(text):
                text += f" District {district}" if re.fullmatch(r"(?:No\.?\s*)?\d{1,2}", district) else f" {district}"
            got = office_of(text, rec.get("ld"))
        else:
            got = office_of(rec.get("heading", ""), rec.get("ld"))
        name, party = rec.get("name", ""), (rec.get("party") or "").strip()
        if not party:
            name, p2 = fed.split_party(name)
            party = p2 or ""
        out.append((got, name, party, rec.get("status", "") or "", rec.get("order", "") or "", rec.get("section"), rec.get("page")))
    return out


# ------------------------------------------------------------------------------------------------ the canvass

def table_a(block, total_at, first, what):
    """Counties as rows, candidates as columns, closed (or opened) by a Total row: ([(heading, total)], counties)."""
    import statistics
    _label, cols = fed.label_and_numbers(block[total_at][1])
    rights = [b for _a, b, _v in cols]
    gaps = [rights[i + 1] - rights[i] for i in range(len(rights) - 1)]
    width = statistics.median(gaps) if gaps else 60.0
    if total_at > first:
        county_rows = block[first:total_at]
    else:
        county_rows = []
        for y, runs in block[total_at + 1:]:
            lab, ns = fed.label_and_numbers(runs)
            if not ns or not fed.county_of(lab):
                break
            county_rows.append((y, runs))
    sums, counties = [0] * len(cols), 0
    for _y, runs in county_rows:
        lab, ns = fed.label_and_numbers(runs)
        if not ns:
            continue
        if not fed.county_of(lab):
            stop(f"in the canvass, a row labelled {lab!r} sits among the county rows of the {what} table")
        counties += 1
        seen = set()
        for _a, b, v in ns:
            k = min(range(len(cols)), key=lambda i: abs(rights[i] - b))
            if abs(rights[k] - b) > max(6.0, 0.45 * width) or k in seen:
                stop(f"in the canvass, {lab}'s figures in the {what} table do not line up with its Total row")
            seen.add(k)
            sums[k] += v
        if len(seen) != len(cols):
            stop(f"in the canvass, {lab}'s row in the {what} table has {len(seen)} figures; its Total row has {len(cols)}")
    if counties and sums != [v for _a, _b, v in cols]:
        stop(f"in the canvass, the counties of the {what} table do not add up to its Total row ({sums} against {[v for *_x, v in cols]})")
    heads = [[] for _ in cols]
    for _y, runs in block[:min(first, total_at)]:
        if fed.NOT_HEAD.match(join(runs)):
            continue
        for r in runs:
            text = r[3].strip()
            if not text or not fed.HEAD_NOISE.sub("", text).strip(" %()") or fed.LABEL_HEAD.match(text):
                continue
            c = r[0] if r[4] - r[0] < 0.5 else (r[0] + r[4]) / 2
            if c < rights[0] - 1.3 * width:
                continue
            k = next((i for i, rt in enumerate(rights) if rt + 3 >= c), None)
            if k is not None:
                heads[k].append(r)
    out = []
    for k, rs in enumerate(heads):
        text = fed.header_text(rs)
        if not text:
            stop(f"in the canvass, column {k + 1} of the {what} table has no heading")
        out.append((text, cols[k][2]))
    return out, counties


def table_b(block, hdr, what):
    """Candidates as rows, counties (and Total) as columns: ([(row label, total)], counties)."""
    heads = fed.words(block[hdr][1])
    cols, i = [], 0
    while i < len(heads):
        a, b, t, _s = heads[i]
        if i + 1 < len(heads) and fed.county_of(t + " " + heads[i + 1][2]):
            cols.append(((a + heads[i + 1][1]) / 2, fed.county_of(t + " " + heads[i + 1][2])))
            i += 2
            continue
        if fed.county_of(t):
            cols.append(((a + b) / 2, fed.county_of(t)))
        elif fed.TOTAL_ROW.match(t):
            cols.append(((a + b) / 2, "total"))
        i += 1
    centres = [c for c, _n in cols]
    out, pending, n_counties, closing = [], [], sum(1 for _c, n in cols if n != "total"), None
    for _y, runs in block[hdr + 1:]:
        lab, ns = fed.label_and_numbers(runs)
        if not ns:
            if lab and not fed.FOOTER.match(lab) and not fed.NOT_HEAD.match(lab):
                pending.append(lab)
            continue
        lab = " ".join(pending + [lab]).strip()
        pending = []
        vals = {}
        for a, b, v in ns:
            k = min(range(len(cols)), key=lambda j: abs(centres[j] - (a + b) / 2))
            if cols[k][1] in vals:
                stop(f"in the canvass, the row {lab!r} of the {what} table has two figures under {cols[k][1]}")
            vals[cols[k][1]] = v
        county_sum = sum(v for n, v in vals.items() if n != "total")
        total = vals.get("total", county_sum)
        if "total" in vals and n_counties and county_sum != total:
            stop(f"in the canvass, the row {lab!r} of the {what} table does not add up ({county_sum} against {total})")
        if fed.TOTAL_ROW.match(lab):
            closing = total
            break
        out.append((lab, total))
    if closing is not None and closing != sum(v for lab, v in out if not fed.STATS.search(lab)):
        stop(f"in the canvass, the rows of the {what} table do not add up to its Total row")
    return out, n_counties


def contest_title(texts, i, ld):
    """(lines used, race) when a state contest's title starts at line i; (-1, None) when another office's title does
    (it closes the contest before); (0, None) otherwise."""
    for k in (1, 2, 3):
        if i + k > len(texts):
            break
        got = office_of(" ".join(texts[i:i + k]), ld)
        if isinstance(got, dict):
            return k, got
        if got == "need_district":
            continue
        figures = len(re.findall(r"(?<![\w.])\d{1,3}(?:,\d{3})+(?![\w.])|(?<![\w.])\d+(?![\w.])", texts[i]))
        if k == 1 and (got == "federal" or (got in ("court", "other") and figures < 2)):
            return -1, None                           # a row of figures ("SHERIFF, SAM 1,204 3,088") is a candidate, not a title
        break
    return 0, None


def canvass_tables(path, report=None):
    """[{race, party, page, title, columns: [(heading, votes)], counties, shape, vote_for}] for every state contest."""
    pdf = PDF(fed.saved(path, "pdf"))
    out, section, current = [], None, None
    for pno, (page, res) in enumerate(pdf.pages(), start=1):
        rws = pdf_rows(pdf, page, res)
        texts = [join(rs) for _y, rs in rws]
        starts, i = [], 0
        while i < len(texts):
            used, got = contest_title(texts, i, None)
            if used > 0:
                current = (" ".join(texts[i:i + used]), got)
                title = current[0]
                if i + used < len(texts) and fed.party_line(texts[i + used]) and len(texts[i + used]) <= 40:
                    title += " " + texts[i + used]
                    used += 1
                starts.append((i, used, title, got, section))
                i += used
                continue
            if used < 0:
                starts.append((i, 0, None, None, section))
                current = None
            elif fed.party_line(texts[i]) and len(texts[i]) <= 40 and not re.search(r"\d", texts[i]):
                section = fed.party_line(texts[i])
                if current:
                    starts.append((i, 1, f"{current[0]} {texts[i]}", current[1], section))
            i += 1
        for n, (i, used, title, got, section_then) in enumerate(starts):
            if title is None:
                continue
            end = starts[n + 1][0] if n + 1 < len(starts) else len(rws)
            block = rws[i + used:end]
            party = title_party(title) or section_then
            vf = next((int(m.group(1)) for t in [title] + [join(rs) for _y, rs in block[:6]] for m in [VOTE_FOR.search(t)] if m), None)
            read = [fed.label_and_numbers(rs) for _y, rs in block]
            first = next((k for k, (lab, ns) in enumerate(read) if ns and (fed.county_of(lab) or fed.TOTAL_ROW.match(lab))), None)
            total_at = next((k for k, (lab, ns) in enumerate(read) if ns and fed.TOTAL_ROW.match(lab)), None)
            hdr = next((k for k, (_y, rs) in enumerate(block)
                        if not read[k][1] and
                        sum(1 for w in fed.words(rs) if fed.county_of(w[2])) + sum(1 for w in fed.words(rs) if fed.TOTAL_ROW.match(w[2])) >= 2), None)
            what = got["office"] + (f" District {got['district']}" if got["district"] else "")
            if total_at is not None and first is not None and (hdr is None or hdr > first):
                cols, counties = table_a(block, total_at, first, what)
                shape = "counties as rows"
            elif hdr is not None:
                cols, counties = table_b(block, hdr, what)
                shape = "candidates as rows"
            elif not any(ns for _lab, ns in read):
                if report is not None:
                    report.append(f"page {pno}: {title} (no table under it)")
                continue
            else:
                stop(f"page {pno} of the canvass has a {what} contest whose table is not read ({title!r}); "
                     "run python -m ballot.state_local_az --probe canvass")
            out.append({"race": got, "party": party, "page": pno, "title": title, "columns": cols, "counties": counties,
                        "shape": shape, "vote_for": vf})
            if report is not None:
                report.append(f"page {pno}: {title} -> {got['race_id']} {party[0] if party else '(party after each name)'}"
                              f"{f' vote for {vf}' if vf else ''}: {'; '.join(f'{t} {v}' for t, v in cols)} ({counties} counties, {shape})")
    return out


def primary_contests(tables):
    """{(race_id, code): {"race", "label", "code", "vote_for", "cands": {printed name: [votes, write_in]}, "writein"}}.
    A contest printed in two halves is joined; the same table printed twice is counted once."""
    out = {}
    for tb in tables:
        named, unnamed = [], []
        for text, votes in tb["columns"]:
            if fed.STATS.search(text):
                continue
            core, mark = fed.split_party(fed.WIN_MARK.sub("", text).strip())
            party = (fed.party_of(mark) if mark else None) or tb["party"]
            if not party:
                stop(f"page {tb['page']} of the canvass has a column for {tb['race']['race_id']} with no party in the contest's title or after the name")
            if fed.WRITE_COL.match(core):
                unnamed.append((party, votes))
            else:
                named.append((party, fed.WRITE_MARK.sub(" ", core).strip(" -,*"), votes, bool(fed.WRITE_MARK.search(core))))

        def slot(party):
            c = out.setdefault((tb["race"]["race_id"], party[1] or party[0]),
                               {"race": tb["race"], "label": party[0], "code": party[1], "vote_for": None, "cands": {}, "writein": 0})
            if tb["vote_for"]:
                if c["vote_for"] and c["vote_for"] != tb["vote_for"]:
                    stop(f"the canvass gives {tb['race']['race_id']} two different 'Vote for' numbers")
                c["vote_for"] = tb["vote_for"]
            return c
        if named and all(slot(p)["cands"].get(nm, [None])[0] == v for p, nm, v, _w in named):
            continue
        for party, nm, votes, write_in in named:
            c = slot(party)
            if nm in c["cands"] and c["cands"][nm][0] != votes:
                stop(f"the canvass gives {nm} two different totals for {tb['race']['race_id']} ({c['cands'][nm][0]} and {votes})")
            c["cands"][nm] = [votes, write_in]
        for party, votes in unnamed:
            slot(party)["writein"] += votes
    return {k: v for k, v in out.items() if v["cands"] or v["writein"]}


# ------------------------------------------------------------------------------------------ the record: seats and holders

def norm_text(raw):
    t = raw.decode("utf-8", "replace")
    t = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", t)
    t = html.unescape(re.sub(r"<[^>]+>", " ", t)).replace("’", "'").replace("‘", "'")
    return " ".join(t.split()).lower()


def constitution(folder, say):
    """Checks the Constitution's words that put each seat and office on the 2026 ballot. Returns (extract, how): the
    extract is {key: {"url", "sha256", "fetched"}}; read afresh from azleg.gov, else from the extract kept last time."""
    path = os.path.join(folder, EXTRACT)
    fresh, failed = {}, []
    for key, url, sentences in CONSTITUTION:
        try:
            raw = net.get(url, timeout=60)
        except Exception as e:  # noqa: BLE001  unreachable: the kept extract stands in, and the report says so
            failed.append(f"{url} ({type(e).__name__})")
            continue
        text = norm_text(raw)
        missing = [s for s in sentences if s not in text]
        if missing:
            stop(f"the Constitution at {url} no longer says {missing[0][:90]!r}...; read it and update the loader")
        fresh[key] = {"url": url, "sha256": hashlib.sha256(raw).hexdigest(), "fetched": dt.date.today().isoformat(), "checked": list(sentences)}
    if (2026 - 1970) % 4 or (2026 - 1994) % 4:
        stop("the four-year cycles counted from 1970 and 1994 do not reach 2026")
    if not failed:
        try:
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(fresh, fh, indent=1)
        except OSError:
            pass
        return fresh, "read afresh from azleg.gov"
    if os.path.exists(path):
        kept = json.load(open(path, encoding="utf-8"))
        if all(k in kept for k, _u, _s in CONSTITUTION):
            say(f"      azleg.gov could not be reached for {len(failed)} page(s); the extract checked on {kept['executive']['fetched']} is used")
            return kept, f"checked on {kept['executive']['fetched']} (azleg.gov not reached this run)"
    stop(f"the Constitution could not be read ({'; '.join(failed)}), and no extract was kept from an earlier run")


def roster(path=ROSTER_DB):
    """(seats {(chamber, district): [person]}, offices {roster office: person}, as of). Names, parties, seats only."""
    if not os.path.exists(path):
        return {}, {}, ""
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    seats, offices, as_of = defaultdict(list), {}, ""
    try:
        for bid, first, last, full, pname, party, chamber, district, upd in con.execute(
                "SELECT bioguide_id, first_name, last_name, official_full, party_name, party, chamber, district, updated_at "
                "FROM legislators WHERE is_current = 1 AND state = 'AZ'"):
            seats[(chamber, str(int(district)) if str(district or "").isdigit() else str(district))].append(
                {"id": bid, "first": first or "", "last": last or "", "full": full or f"{first} {last}", "party": pname or party or ""})
            as_of = max(as_of, upd or "")
        for bid, first, last, full, office, pname, party, term_end, upd in con.execute(
                "SELECT bioguide_id, first_name, last_name, official_full, office, party_name, party, term_end, updated_at FROM officials "
                "WHERE state = 'AZ'"):
            offices[(office or "").lower()] = {"id": bid, "first": first or "", "last": last or "", "full": full or f"{first} {last}",
                                               "party": pname or party or "", "term_end": term_end or ""}
            as_of = max(as_of, upd or "")
    finally:
        con.close()
    return seats, offices, as_of[:10]


def holder_fits(name, h):
    cand = name_parts(name)
    return fits(cand, name_parts(h["full"])) or fits(cand, (fold(h["first"]).split(), fold(h["last"])))


def sha_of(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def mdate(path):
    return dt.date.fromtimestamp(os.path.getmtime(path)).isoformat()


# ------------------------------------------------------------------------------------------------------ load

def load(db_path, say=print, folder=None):
    net.patient_lookups()
    folder = folder or os.path.join(CACHE, "az")
    os.makedirs(folder, exist_ok=True)
    gpath = fed.find_general(folder)
    wpath = os.path.join(folder, fed.WRITEIN_FILE)
    wpath = wpath if os.path.exists(wpath) else None
    cpath = os.path.join(folder, fed.CANVASS_FILE)
    cpath = cpath if os.path.exists(cpath) else None
    extract, const_how = constitution(folder, say)
    seats, offices, as_of = roster()
    members = [p for ps in seats.values() for p in ps] + list(offices.values())
    spell = spellings(members)
    checks = []

    # ---- the seats and offices the Constitution puts on the 2026 ballot
    races = {}
    for d in range(1, DISTRICTS + 1):
        for key in ("SS", "SH"):
            r = race(key, d)
            races[r["race_id"]] = r
    for key in FROM_RECORD:
        r = race(key)
        races[r["race_id"]] = r

    # ---- the November listing (when saved): state rows only
    general, mates, gone, unread, dup = [], defaultdict(list), [], Counter(), 0
    caps_n, has_order, n_rows = 0, False, Counter()
    report = {"heading_rows": [], "headings": []}

    def take(placed, source, from_writein=False):
        nonlocal caps_n, has_order, dup
        for got, raw, praw, status, given, section, page in placed:
            if not isinstance(got, dict) and got != "mate":
                unread[got or "no office heading"] += 1
                continue
            n_rows[source] += 1
            wi = bool(fed.SECTION_WI.search(status) or section == "write-in" or fed.WRITE_MARK.search(raw))
            is_gone = bool(fed.GONE.search(status) or section == "withdrawn")
            parts = [x for x in TICKET.split(fed.WRITE_MARK.sub(" ", raw).strip()) if x.strip()] if (got == "mate" or got["key"] == "GOV") else [fed.WRITE_MARK.sub(" ", raw).strip()]
            name, caps = shown(parts[0] if parts else "", spell)
            p = fed.party_of(praw) if praw else None
            label = p[0] if p else (" ".join(praw.split()) or ("Write-in" if wi else ""))
            if got == "mate":
                if not is_gone:
                    mates[label].append(name)
                continue
            rid = got["race_id"]
            if from_writein and not wi and not is_gone:
                unread["neither write-in nor withdrawn on the write-in list"] += 1
                continue
            if is_gone:
                before = len(general)
                general[:] = [g for g in general if not (g["race"] == rid and same(g["name"], name))]
                gone.append((rid, source, before != len(general)))
                continue
            if rid not in races:
                races[rid] = got
            if from_writein and any(g["race"] == rid and same(g["name"], name) for g in general):
                continue
            if any(g["race"] == rid and fold(g["name"]) == fold(name) for g in general):
                dup += 1
                continue
            if not label and not wi:
                stop(f"a candidate for {rid} on page {page} of {os.path.basename(gpath if source == SRC_LIST else wpath)} has no party")
            caps_n += caps
            order = int(given) if str(given).strip().isdigit() and not wi else None
            has_order = has_order or order is not None
            mate = shown(parts[1], spell)[0] if got["key"] == "GOV" and len(parts) > 1 else None
            general.append({"race": rid, "name": name, "party": label, "code": p[1] if p else None, "order": order, "write_in": wi,
                            "caps": caps, "mate": mate, "src": source})

    if gpath:
        take(place_rows(read_listing(gpath, report), spell, report), SRC_LIST)
    if wpath:
        take(place_rows(read_listing(wpath, {"heading_rows": [], "headings": []}), spell, report), SRC_WRITEIN, from_writein=True)
    has_list = gpath is not None

    # running mates: one to a party, paired with that party's candidate for Governor
    unpaired = []
    for g in general:
        if races[g["race"]]["key"] == "GOV" and not g["write_in"] and not g["mate"]:
            ms = mates.get(g["party"], [])
            if len(ms) == 1:
                g["mate"] = ms[0]
            else:
                unpaired.append(f"{g['party']}: {len(ms)} running mates listed")

    # ---- the primary fields (when the canvass is saved)
    seats_from = {rid: "listing" for rid, r in races.items() if r["key"] == "CC" and r["seats"]}
    contests = {}
    if cpath:
        contests = primary_contests(canvass_tables(cpath))
        for (rid, _code), c in contests.items():
            if rid not in races:
                races[rid] = c["race"]
            if c["vote_for"]:
                have = races[rid]["seats"]
                if have is None:
                    races[rid]["seats"], seats_from[rid] = c["vote_for"], "canvass"
                elif c["vote_for"] != have:
                    stop(f"the canvass says 'Vote for {c['vote_for']}' for {rid}, which has {have} seat(s)")
        missing = sorted(rid for rid in races if not any(k[0] == rid for k in contests))
        if missing and len(missing) > len(races) // 2:
            stop(f"the canvass gives no primary for {len(missing)} of {len(races)} races; run python -m ballot.state_local_az --probe canvass")
    cc = [rid for rid in races if races[rid]["key"] == "CC"]
    if (has_list or cpath) and not cc:
        checks.append("no Corporation Commission race on the saved files")
    for rid in cc:
        if races[rid]["seats"] is None:
            checks.append(f"{rid}: how many Corporation Commission seats are up is not read from the files (no 'Vote for' line), so "
                          "no seat count and no primary field is given")

    # one printed candidate per party and seat
    per = Counter((g["race"], g["party"]) for g in general if not g["write_in"] and g["party"] not in ("Independent", "Party Not Designated"))
    over = [f"{rid} {p} ({n})" for (rid, p), n in per.items() if races[rid]["seats"] and n > races[rid]["seats"]]
    if over:
        stop(f"more candidates of one party than seats on the November list: {', '.join(over[:8])}; run --probe general")

    # ---- today's holders
    holders, notes = {}, defaultdict(list)
    for rid, r in races.items():
        if r["chamber"]:
            hs = seats.get((r["chamber"], r["district"]), [])
            if len(hs) != (2 if r["chamber"] == "House" else 1):
                checks.append(f"{rid}: the roster lists {len(hs)} sitting member(s)")
            holders[rid] = hs
            if not hs:
                notes[rid].append(f"The Open States roster ({as_of}) lists no sitting member for this seat.")
        else:
            h = next((offices[o] for o in r["roster"] if o in offices), None)
            holders[rid] = [h] if h else []
            if h and h["term_end"] and not h["term_end"].startswith("2027-01"):
                checks.append(f"{rid}: the roster's holder's term ends {h['term_end']}, not January 2027")
            if not h:
                notes[rid].append("The Open States roster this site uses does not carry this office, so today's holder is not shown.")
        if r["key"] == "SH" and not r["special"]:
            notes[rid].insert(0, "Elect 2. Each legislative district elects two members of the Arizona House of Representatives "
                                 "(Arizona Constitution, Article 4, Part 2, Section 1); the two candidates with the most votes are elected.")
        if r["key"] == "GOV":
            notes[rid].insert(0, "Arizona elects the Governor and Lieutenant Governor on one ticket: each nominee for Governor names a "
                                 "running mate, and a single vote chooses the ticket (Arizona Constitution, Article 5, Section 1). "
                                 "A running mate is named in the candidate's note.")
        if r["key"] == "CC":
            n = r["seats"]
            said = (f"{n} seat{'s are' if n > 1 else ' is'} on this ballot, as the Secretary of State's {seats_from.get(rid, 'listing')} "
                    "says.") if n else "how many seats are on this ballot is not read from the Secretary of State's files yet."
            notes[rid].insert(0, (f"Elect {n}. " if n else "") + "The Corporation Commission has five members with four-year terms "
                                 f"(Arizona Constitution, Article 15, Section 1); {said}")
        if not has_list:
            notes[rid].append("The candidates wait for the Arizona Secretary of State's candidate listing for November 3, 2026: its "
                              "sites answer scripts with a Cloudflare challenge, and the listing has not been saved from a browser yet.")
        if not cpath:
            notes[rid].append("The July 21, 2026 primary results are not loaded yet.")

    # the sitting member on the ballot: a holder fits exactly one person in the race, and that person no other holder
    names_in = defaultdict(set)
    for g in general:
        names_in[g["race"]].add(g["name"])
    for (rid, _code), c in contests.items():
        names_in[rid].update(shown(n, spell)[0] for n in c["cands"])
    sitting = {}                                                     # (race, folded name) -> member id
    for rid, hs in holders.items():
        for h in hs:
            fit = [n for n in names_in.get(rid, ()) if holder_fits(n, h)]
            people = []
            for n in fit:
                if not any(same(n, x) for x in people):
                    people.append(n)
            others = [h2 for h2 in hs if h2 is not h and any(holder_fits(n, h2) for n in fit)]
            if len(people) == 1 and not others:
                for n in fit:
                    sitting[(rid, fold(n))] = h["id"]
    member = lambda rid, name: sitting.get((rid, fold(name)))

    # ---- the primary rows
    cand, fields, n_primary, upset, leaders = [], Counter(), 0, [], {}
    for (rid, _key), c in sorted(contests.items()):
        label, code = c["label"], c["code"]
        k = races[rid]["seats"]
        if not k:
            continue                                  # a Commission primary without its number of seats: reported above
        ranked = sorted(c["cands"].items(), key=lambda kv: -kv[1][0])
        printed = [n for n, (_v, wi) in c["cands"].items() if not wi]
        won = [n for n, _x in ranked[:k]]
        leaders[(rid, code or label)] = [shown(n, spell)[0] for n in won]
        nominees = [g for g in general if g["race"] == rid and not g["write_in"] and (g["code"] or g["party"]) == (code or label)]
        if has_list and nominees:
            for g in nominees:
                if not any(same(g["name"], w) for w in leaders[(rid, code or label)]):
                    upset.append(f"{rid} {label}: {g['name']} is on the November list")
        if len(printed) <= k:
            continue
        if len(ranked) > k and ranked[k - 1][1][0] == ranked[k][1][0]:
            stop(f"the {rid} {label} primary is a tie at the cut in the canvass; read the canvass's own note")
        fields[races[rid]["level"] if races[rid]["level"] != "legislature" else races[rid]["office_kind"]] += 1
        total = sum(v for v, _wi in c["cands"].values()) + c["writein"]
        for nm, (votes, wi) in ranked:
            name, caps = shown(nm, spell)
            outcome = "advanced" if nm in won else "lost"
            note = [WRITE_IN_NOTE if wi else "", CAPS_CANVASS if caps else ""]
            if outcome == "advanced" and has_list and not any(same(g["name"], name) for g in nominees):
                note.append(NOT_ON_LIST)
            m = member(rid, name)
            cand.append((rid, f"primary-{fed.election_code(label, code)}", PRIMARY, name, label, party_code(label), None, int(bool(m)),
                         int(wi), votes, round(100 * votes / total, 1) if total else None, outcome, m, SRC_CANVASS,
                         " ".join(x for x in note if x) or None))
            n_primary += 1

    # ---- the November rows
    for g in general:
        rid = g["race"]
        note = []
        if races[rid]["key"] == "GOV" and g["mate"]:
            note.append(f"Running mate for Lieutenant Governor: {g['mate']}.")
        if g["caps"]:
            note.append(CAPS_LIST)
        if g["write_in"]:
            note.append(WRITE_IN_NOTE)
        elif cpath and (rid, g["code"] or g["party"]) in leaders and not any(same(g["name"], w) for w in leaders[(rid, g["code"] or g["party"])]):
            note.append(f"Not among the July 21 {g['party']} primary's winners in the canvass; the list does not say how the nomination was made.")
        m = member(rid, g["name"])
        cand.append((rid, "general", GENERAL, g["name"], g["party"] or "Write-in",
                     "W" if g["write_in"] and not fed.party_of(g["party"] or "") else party_code(g["party"]),
                     g["order"], int(bool(m)), int(g["write_in"]), None, None, None, m, g["src"], " ".join(note) or None))

    # ---- every seat has its candidates
    listed = Counter(g["race"] for g in general if not g["write_in"])
    empty = sorted(rid for rid in races if not listed[rid]) if has_list else []
    short = sorted(f"{rid} ({listed[rid]} for {races[rid]['seats']} seats)" for rid in races
                   if has_list and races[rid]["seats"] and 0 < listed[rid] < races[rid]["seats"])

    race_rows = []
    for rid, r in sorted(races.items()):
        hs = holders.get(rid) or []
        race_rows.append((rid, STATE, r["level"], r["office_kind"], r["office"], r["jurisdiction"], r["jurisdiction_id"], None,
                          r["district"], None, r["special"], 1, "; ".join(h["id"] for h in hs) or None,
                          "; ".join(h["full"] for h in hs) or None, "; ".join(h["party"] for h in hs) or None, GENERAL,
                          " ".join(notes[rid]) or None))

    src = [(SRC_CONST, STATE, "law", "Arizona State Legislature", "Arizona Constitution: Article 4, Part 2, Sections 1 and 21; "
            "Article 5, Section 1; Article 15, Section 1; Article 19", CONST_PAGE, "", extract["executive"]["fetched"],
            hashlib.sha256("".join(extract[k]["sha256"] for k, _u, _s in CONSTITUTION).encode()).hexdigest(), len(CONSTITUTION),
            "Which seats and offices are on the 2026 ballot: thirty districts of one senator and two representatives, two-year "
            "legislative terms; Governor (with Lieutenant Governor on one ticket), Secretary of State, Attorney General, State "
            "Treasurer and Superintendent of Public Instruction elected every four years from 1970; the Mine Inspector at general "
            "elections (four-year terms from 1994 in one printed version, two-year terms in the other); five Corporation "
            "Commissioners with four-year terms, the number up this year not stated. Each section's page was checked for its words "
            f"({const_how}); the fingerprint is of the five pages' own SHA-256 values: "
            + "; ".join(f"{extract[k]['url']} {extract[k]['sha256'][:12]}" for k, _u, _s in CONSTITUTION) + "."),
           (SRC_ROSTER, STATE, "roster", "Open States people project (CC0)", "Arizona legislators and statewide officials, as loaded into "
            "state_az.sqlite", "https://github.com/openstates/people", as_of, as_of, "", len(members),
            "Today's holder of each seat and office: names, party and seat only. The roster carries the Governor, Secretary of State "
            "and Attorney General, and no State Treasurer, Superintendent of Public Instruction, Mine Inspector or Corporation "
            "Commissioner. A candidate is marked as the sitting member only when the name fits a holder of that seat and that "
            "holder fits no one else in the race. Not an official record.")]
    if gpath:
        src.append((SRC_LIST, STATE, "official candidate list", AGENCY, "Candidate Listing, 2026 General Election (November 3, 2026): "
                    "statewide and legislative offices", fed.INFO_PAGE, fed.published(gpath) if gpath.endswith(".pdf") else "",
                    mdate(gpath), sha_of(gpath), n_rows[SRC_LIST],
                    f"{fed.BLOCKED} Only the name, party, office, district, status and ballot order columns are read; the listing's "
                    "other columns are never turned into text. " + ("Ballot order as the listing prints it. " if has_order else
                    "The listing prints no ballot order column, so none is stored. ")
                    + f"Withdrawn or removed, left off: {sum(1 for x in gone if x[1] == SRC_LIST)}. Federal, judicial and other rows "
                    f"passed over: {sum(unread.values())}."))
    if wpath:
        src.append((SRC_WRITEIN, STATE, "official candidate list", AGENCY, "2026 General Write-In and Withdrawn Candidate List: "
                    "statewide and legislative offices", fed.WRITEIN_URL, fed.published(wpath), mdate(wpath), sha_of(wpath),
                    n_rows[SRC_WRITEIN], f"{fed.BLOCKED} Write-in candidates added: "
                    f"{sum(1 for g in general if g['src'] == SRC_WRITEIN)}. Withdrawn: {sum(1 for x in gone if x[1] == SRC_WRITEIN)}."))
    if cpath:
        src.append((SRC_CANVASS, STATE, "official results", AGENCY, "Official Canvass, 2026 Primary Election (July 21, 2026): "
                    "statewide and legislative offices", fed.CANVASS_URL, "2026-08-06", mdate(cpath), sha_of(cpath), n_primary,
                    f"{fed.BLOCKED} Each table's counties checked against its totals. Unnamed write-in votes count toward each party "
                    "primary's total; a share is of all votes cast in that party's contest. The candidates with the most votes "
                    "advanced (Arizona nominates by plurality), two in a House district."))

    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA)
    with con:
        con.execute("DELETE FROM sl_candidates WHERE race_id IN (SELECT race_id FROM sl_races WHERE state = 'AZ') OR race_id LIKE '2026-AZ-%'")
        con.execute("DELETE FROM sl_races WHERE state = 'AZ'")
        con.execute("DELETE FROM sl_sources WHERE state = 'AZ'")
        con.execute("DELETE FROM sl_places WHERE source_id LIKE 'az-%'")
        con.executemany("INSERT INTO sl_races VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", race_rows)
        con.executemany("INSERT INTO sl_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", cand)
        con.executemany("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", src)
    con.close()

    # ---- the report: counts only
    bucket = lambda rid: races[rid]["office_kind"] if races[rid]["level"] == "legislature" else "statewide"
    by = Counter(bucket(rid) for rid in races)
    gen_by = Counter(bucket(g["race"]) for g in general)
    inc_by = Counter(bucket(rid) for rid, _m in {(rid, mid) for (rid, _n), mid in sitting.items()})
    house_seats = sum(races[rid]["seats"] for rid in races if races[rid]["office_kind"] == "state_house")
    say(f"    Arizona (state races): {by['state_senate']} State Senate seats, {by['state_house']} House districts ({house_seats} seats), "
        f"{by['statewide']} statewide races; "
        + (f"{len(general)} candidates on the November ballot (Senate {gen_by['state_senate']}, House {gen_by['state_house']}, "
           f"statewide {gen_by['statewide']}; {sum(1 for g in general if g['write_in'])} write-in; {len(gone)} withdrawn left off)"
           if has_list else "no November candidates yet (the listing is not saved)")
        + f"; primary fields: Senate {fields['state_senate']}, House {fields['state_house']}, statewide {fields['statewide']} "
          f"({n_primary} rows" + (")" if cpath else ", the canvass is not saved)")
        + f"; sitting member in the race: Senate {inc_by['state_senate']}, House {inc_by['state_house']}, statewide {inc_by['statewide']}")
    waiting = [n for n, p in ((f"{fed.GENERAL_STEM}.pdf (the Candidate Listing on {fed.INFO_PAGE})", gpath),
                              (f"{fed.CANVASS_FILE} ({fed.CANVASS_URL})", cpath),
                              (f"{fed.WRITEIN_FILE} ({fed.WRITEIN_URL}, optional)", wpath)) if not p]
    if waiting:
        say(f"      waiting: every Secretary of State host answers scripts with a Cloudflare challenge; save from a browser into {folder}: "
            + "; ".join(waiting))
    if not has_list:
        say("      waiting: the Corporation Commission race (the Constitution does not say how many seats are up in 2026) and every "
            "race's candidates")
    if dup:
        say(f"      the listing names {dup} candidate(s) twice for the same race; each is stored once")
    if unread:
        say(f"      rows passed over on the listing: {dict(unread)} (judicial retention and other offices are not loaded)")
    for c in checks:
        say(f"    CHECK Arizona (state races): {c}")
    if empty:
        say(f"    CHECK Arizona (state races): no November candidate for {len(empty)} races: {', '.join(empty[:12])}" + (" ..." if len(empty) > 12 else ""))
    if short:
        say(f"    CHECK Arizona (state races): fewer candidates than seats: {', '.join(short[:12])}")
    if upset:
        say(f"    CHECK Arizona (state races): a November candidate is not among the canvass's winners for {len(upset)} party primaries: "
            f"{', '.join(upset[:8])}")
    if unpaired:
        say(f"    CHECK Arizona (state races): running mates not paired: {unpaired}")
    return len(cand)


# ------------------------------------------------------------------------------------------------------ probe

def probe(kind, folder):
    """What a reader needs to fix the layout rules, and nothing the privacy rule keeps back: for the canvass (a results
    book), its lines on pages with a state contest; for the listings, the allowlisted headings, the office headings and
    the allowlisted cells of state rows."""
    if kind == "canvass":
        path = os.path.join(folder, fed.CANVASS_FILE)
        pdf = PDF(fed.saved(path, "pdf"))
        for pno, (page, res) in enumerate(pdf.pages(), start=1):
            texts = [join(rs) for _y, rs in pdf_rows(pdf, page, res)]
            if any(isinstance(office_of(t), dict) or office_of(t) == "need_district" for t in texts):
                print(f"--- page {pno}")
                for t in texts:
                    print("   ", t)
        report = []
        try:
            canvass_tables(path, report)
        finally:
            print("\n".join(report))
        return
    path = fed.find_general(folder) if kind == "general" else os.path.join(folder, fed.WRITEIN_FILE)
    report = {"heading_rows": [], "headings": []}
    placed = place_rows(read_listing(path, report), {}, report)
    print(f"heading rows found: {len(report['heading_rows'])}")
    for allowed, others in report["heading_rows"][:3]:
        print("   ", allowed, f"and {others} other heading(s)")
    print(f"office headings: {len(report['headings'])}")
    for h in report["headings"][:80]:
        print("   ", h)
    for got, name, party, status, order, section, page in placed:
        where = got["race_id"] if isinstance(got, dict) else got
        if isinstance(got, dict) or got == "mate":
            print("   ", page, "|", where, "|", name, "|", party, "|", status, "|", order, "|", section or "")
    print("rows passed over:", dict(Counter(g if not isinstance(g, dict) else "state" for g, *_x in placed if not isinstance(g, dict) and g != "mate")))


if __name__ == "__main__":
    args = sys.argv[1:]
    if len(args) >= 2 and args[0] == "--probe":
        probe(args[1], args[2] if len(args) > 2 else os.path.join(CACHE, "az"))
    elif 1 <= len(args) <= 2:
        load(args[0], folder=args[1] if len(args) > 1 else None)
    else:
        raise SystemExit("usage: python -m ballot.state_local_az <database file> [folder] | --probe general|writein|canvass [folder]")
