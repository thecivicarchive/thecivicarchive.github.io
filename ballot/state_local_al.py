"""
ballot/state_local_al.py - Alabama's state races on the November 3, 2026 ballot, into ballot_local_2026.sqlite.

What is on the ballot. Alabama elects its whole Legislature every four years, in the governor's year: all 35 Senate
seats and all 105 House seats are up in 2026 (four-year terms; states/places.py records the same). The statewide
executive offices on the ballot are Governor, Lieutenant Governor (elected separately), Attorney General, Secretary of
State, State Treasurer, State Auditor, the Commissioner of Agriculture and Industries and two Public Service Commission
places; the State Board of Education's districts up this year, the Supreme Court, Court of Civil Appeals and Court of
Criminal Appeals places up this year, and the circuit and district judgeships up this year are on it too. Every one of
these offices is partisan in Alabama. Which of them are up is read from the ballots themselves, not assumed (in the
September 2026 ballots: State Board of Education districts 2, 4, 6 and 8; Supreme Court places 7 and 8; places 4 and 5
of each appeals court; 22 circuit and 34 district judgeships). U.S. Senator and Representative are left to the federal
pages, and county offices, district attorneys, county school boards and local questions to a later phase (they are
counted and named in the report). The federal ballot database (ballot_2026.sqlite) is never opened here.

Race keys: 2026-AL-SS<n> and -SH<n> for the Legislature; -GOV, -LTG, -AG, -SOS, -TREAS, -AUD, -AGR; -PSC<place>,
-SBOE<district>, -SC<place> (Supreme Court), -CIVA<place> and -CRIMA<place> (the appeals courts), -CC<circuit>-<place>
(circuit courts) and -DC<county FIPS>[-<place>] (district courts).

Checks, all printed and kept in the source notes: every seat of both chambers has a race, and every race whose ballots
agree has its candidates or says why not; statewide contests are printed in all 67 counties; each primary field's
winner (or runoff pair) must be the party's candidate on the November ballot, and a winner printed for another seat
instead is named (Senate District 25 in 2026: the Democratic primary was voted in Crenshaw and Montgomery counties and
won by Kirk Hatcher, while the November ballots print the seat in Crenshaw, Elmore and Montgomery with Phadra Carson
Foster, and Hatcher for District 26); the counties a primary was voted in are compared with the counties whose
November ballots print the seat; each statewide contest's votes (with over and under votes) are compared with the
party's BALLOTS CAST line county by county; and the parties' typeset certifications are compared contest by contest.

Sources: the Secretary of State's own files, the same ones ballot/lists/al.py reads for the federal races, cached in
ballot_cache/al/.
  - November ballot: the "2026 General Election Sample Ballots", one typeset PDF per county, 67 in all
    (sos.alabama.gov/alabama-votes/2026-general-election-sample-ballots). Each draws every ballot style of the county
    one over another, so the text is read in drawing order (ballot/lists/al.ballot_lines), a style at a time: the date
    heading, each "FOR <office>" contest, its "(Vote for One)" line, each candidate's name in capitals with the party in
    small type beneath, and the Write-in line. Only styles dated NOVEMBER 3, 2026 count (a few counties also draw a
    2022 style beneath). Every 2026 style of every county must print a contest identically (letters compared, spacing
    and case aside), or the race is left out and named. Ballot order is the ballot's own. The State Certifications of
    candidates are scans with no text, so the typeset sample ballots are read instead; a ballot shows no withdrawn
    candidates and no declared write-ins, so none are loaded.
  - Primary fields: the Secretary's precinct results files for the May 19 primary and the June 16 runoff
    (2026_Primary_Election.zip and 2026_PRIMARY_RUNOFF_ELECTION.zip on Elections Data Downloads): one .xls per county
    (Contest Title, Party, Candidate, a column per precinct, ABSENTEE, PROVISIONAL), summed over the counties; the Over
    Votes and Under Votes lines are kept out of the share. A nominee needs a majority; without one the top two go to
    the runoff. They are checked against the parties' certified vote totals where those are typeset (the Democratic
    workbooks for the primary and the runoff, the Republican workbook for the primary; the Republican runoff's
    certification is a scan), and every difference is named in the source note. Alabama prints only contested
    primaries, so every state contest in these files is a field.
  - Who holds each seat: the Open States roster in state_al.sqlite (legislators with is_current = 1 by chamber and
    district; the officials table for the six executive offices it carries). Names, party and ids only.
  - County codes: the Census Bureau's 2024 county file (states_cache/census/cb_2024_us_county_500k.zip). The counties
    a legislative district, a judicial circuit or a State Board of Education district reaches are the counties whose
    sample ballots print its contest (derived, and said so).

Privacy. None of these files carries an address, telephone, e-mail, website or treasurer: the sample ballots print
offices, names, parties and ballot questions; the results print contest titles, names, parties and vote columns. Even
so, only the office, district, name, party, order and vote cells are kept (as JSON of those cells alone), nothing is
printed but counts and checks, and before anything is written every stored text is checked for anything that looks
like a contact detail. The roster is read for ids, names, party, chamber and district only.

    python -m ballot.state_local_al <path to a test database> [--keep <folder for the kept-cells JSON>]
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
import zipfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from ballot.common import CACHE, fold, name_parts, party_code  # noqa: E402
from ballot.lists.al import (DATA_PAGE, FILES, GENERAL, MONTHS, PRIMARY, REP_RUNOFF_SCAN, RUNOFF, SAMPLE_PAGES, SOS,  # noqa: E402
                             ballot_lines, fetch, number, same_person, sample_links, sha256, xls_sheets)
from ballot.lists.tx import proper  # noqa: E402
from ballot.match import fits  # noqa: E402

STATE, FIPS, NAME = "AL", "01", "Alabama"
FOLDER = os.path.join(CACHE, "al")
ROSTER = os.path.join(HERE, "state_al.sqlite")
COUNTY_ZIP = os.path.join(HERE, "states_cache", "census", "cb_2024_us_county_500k.zip")
COUNTY_URL = "https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_county_500k.zip"
SENATE_SEATS, HOUSE_SEATS, COUNTIES = 35, 105, 67
AGENCY = "Alabama Secretary of State, Elections Division"
KEPT = "al_2026_general_sample_ballots_state.json"
KEPT_VERSION = 1

SRC_GENERAL = "al-sos-2026-sl-general-sample-ballots"
SRC_PRIMARY = "al-sos-2026-sl-primary-precinct-results"
SRC_RUNOFF = "al-sos-2026-sl-runoff-precinct-results"
SRC_DEM_P, SRC_REP_P, SRC_DEM_R = "al-dem-2026-sl-primary-certified-totals", "al-gop-2026-sl-primary-certified-totals", "al-dem-2026-sl-runoff-certified-totals"
SRC_ROSTER, SRC_COUNTY = "al-openstates-roster", "al-census-2024-county-codes"

PARTY = {"REP": "Republican", "DEM": "Democrat"}                      # as the ballot prints them
PARTY_OF = {"REP": "Republican", "DEM": "Democratic"}                  # "the Democratic primary"
PRINTED = {"democrat": "Democrat", "democratic": "Democrat", "republican": "Republican", "libertarian": "Libertarian",
           "independent": "Independent"}
DATE = re.compile(r"^(%s) (\d{1,2}), (20\d\d)$" % "|".join(MONTHS))
VOTE_FOR = re.compile(r"^\(\s*Vote\s*for\s*(\w+)\s*\)", re.I)
NAME_LINE = re.compile(r"^[\"'“‘]?[^\W\d_][^\d]*$")
CONTACT = re.compile(r"@|https?:|www\.|\.(?:com|org|net|gov|us)\b|\d{3}|P\.?\s?O\.?\s+Box|\bSuite\b", re.I)

# ---------- offices ----------
# key -> (level, office_kind, office as shown, the roster's officials.office or None)
EXEC = {"GOV": ("statewide", "governor", "Governor", "governor"),
        "LTG": ("statewide", "lieutenant_governor", "Lieutenant Governor", "lt_governor"),
        "AG": ("statewide", "attorney_general", "Attorney General", "attorney general"),
        "SOS": ("statewide", "secretary_of_state", "Secretary of State", "secretary of state"),
        "TREAS": ("statewide", "state_treasurer", "State Treasurer", "treasurer"),
        "AUD": ("statewide", "state_auditor", "State Auditor", "auditor"),
        "AGR": ("statewide", "agriculture_commissioner", "Commissioner of Agriculture and Industries", None)}
PLACED = {"PSC": ("statewide", "public_service_commissioner", "Public Service Commissioner"),
          "SC": ("court", "supreme_court", "Associate Justice of the Supreme Court"),
          "CIVA": ("court", "court_of_civil_appeals", "Judge of the Court of Civil Appeals"),
          "CRIMA": ("court", "court_of_criminal_appeals", "Judge of the Court of Criminal Appeals")}

# on the letters and digits of a contest's title alone, "FOR" and any party mark taken off
OFFICE_PATTERNS = [
    (re.compile(r"(?:GOVENOR|GOVERNOR)"), "GOV"),
    (re.compile(r"(?:LIEUTENANT|LT)(?:GOVENOR|GOVERNOR)"), "LTG"),
    (re.compile(r"ATTORNEYGENERAL"), "AG"),
    (re.compile(r"SECRETARYOFSTATE"), "SOS"),
    (re.compile(r"(?:STATE)?TREASURER"), "TREAS"),
    (re.compile(r"(?:STATE)?AUDITOR"), "AUD"),
    (re.compile(r"COMMISSIONEROFAGRICULTURE(?:AND)?INDUSTRIES"), "AGR"),
    (re.compile(r"PUBLICSERVICECOMMISSION(?:ER)?(?:PLACE)?(?:NO)?(?P<a>\d{1,2})"), "PSC"),
    (re.compile(r"(?:MEMBER)?STATEBOARDOFEDUCATION(?:MEMBER)?DISTRICT(?:NO)?(?P<a>\d{1,2})"), "SBOE"),
    (re.compile(r"STATESENATOR(?:DISTRICT)?(?:NO)?(?P<a>\d{1,2})"), "SS"),
    (re.compile(r"STATEREPRESENTATIVE(?:DISTRICT)?(?:NO)?(?P<a>\d{1,3})"), "SH"),
    (re.compile(r"ASSOCIATEJUSTICEOFTHESUPREMECOURTPLACE(?:NO)?(?P<a>\d{1,2})"), "SC"),
    (re.compile(r"COURTOFCIVILAPPEALS(?:JUDGE)?PLACE(?:NO)?(?P<a>\d{1,2})"), "CIVA"),
    (re.compile(r"COURTOFCRIMINALAPPEALS(?:JUDGE)?PLACE(?:NO)?(?P<a>\d{1,2})"), "CRIMA"),
    (re.compile(r"CIRCUITCOURTJUDGE(?P<a>\d{1,2})(?:ST|ND|RD|TH)JUDICIALCIRCUITPLACE(?:NO)?(?P<b>\d{1,2})"), "CC"),
    (re.compile(r"DISTRICTCOURTJUDGE(?P<c>[A-Z]+?)(?:COUNTY)?(?:PLACE(?:NO)?(?P<b>\d{1,2}))?"), "DC"),
]
# contests that are not this loader's, by what they are (counted for the report)
COURT_UNREAD = "court contest not understood"
OTHER_PATTERNS = [
    (re.compile(r"^UNITEDSTATES|^USREPRESENTATIVE|^USSENATOR|CONGRESSIONAL"), "federal (the federal pages)"),
    (re.compile(r"EXEC(?:UTIVE)?COMM|REPUBEXE|DEMEXEC|EXECCOMM|GOPEXECUTIVE|REPEXECCOMM"), "party executive committee"),
    (re.compile(r"DISTRICTATTORNEY"), "district attorney (local phase)"),
    (re.compile(r"PROBATE"), "county office (local phase)"),
    (re.compile(r"CHIEFJUSTICE|SUPREMECOURT|APPEALS|JUDGE"), COURT_UNREAD),
    (re.compile(r"BOARDOFEDUCATION|BOARDOFEDU|SUPERINTENDENT"), "county or city school office (local phase)"),
    (re.compile(r"COUNTY|COMMISSION|SHERIFF|CORONER|REVENUE|TAXASSESSOR|TAXCOLLECTOR|LICENSE|BESSEMER"), "county office (local phase)"),
    (re.compile(r"STATEWIDEAMENDMENT"), "statewide ballot question (not an office)"),
    (re.compile(r"TAX|MILL|REFERENDUM|AMENDMENT|FIREDISTRICT|ELECTION|PROPOSED"), "local question (local phase)"),
    (re.compile(r"^BALLOTSCAST|^REGISTEREDVOTERS"), "turnout line"),
]
KIND_OF = {"SS": "state_senate", "SH": "state_house", "SBOE": "state_board_of_education", "CC": "circuit_court",
           "DC": "district_court", **{k: v[1] for k, v in EXEC.items()}, **{k: v[1] for k, v in PLACED.items()}}

LEG_NOTE = ("Alabama elects all 35 senators and all 105 representatives every four years, in the governor's year; every seat "
            "is on the 2026 ballot.")
NO_HOLDER = "The roster this site reads does not carry who holds this office today."
VACANT = "The roster shows no one holding this seat today."
CAPS = "Alabama's sample ballots print names in capitals; they are shown here in ordinary capitals."
RUNOFF_NOTE = "No candidate had a majority; the top two went to the June 16 runoff."
NO_RUNOFF = "No candidate had a majority, and the Secretary of State's runoff results have no runoff for this contest."
NOT_ON_BALLOT = "Won the {party} nomination but is not on the November sample ballots."
NOT_PRINTED = ("No candidate for this seat is printed on any county's November sample ballot (no one qualified, or every "
               "nominee withdrew).")
SPLIT_NOTE = "The counties' sample ballots do not print this race the same way; its candidates are left out until they agree."
DERIVED = "The counties listed are those whose sample ballots print this contest (derived from the ballots)."
DERIVED_RESULTS = "The counties listed are those whose primary results carry this contest (derived from the results)."


def shown(name):
    """A name printed in capitals, in ordinary capitals (ballot.lists.tx.proper), a quoted nickname included:
    ANGELO "Doc" MANCUSO -> Angelo "Doc" Mancuso."""
    raw = name.split()
    out = proper(" ".join(raw)).split()
    if len(out) != len(raw):
        return proper(name)
    for i, w in enumerate(raw):
        m = re.fullmatch(r"([\"'“‘(]+)([^\W\d_][^\"'”’)]*)([\"'”’)]*)(,?)", w)
        if m:
            out[i] = m.group(1) + proper(m.group(2).upper()) + m.group(3) + m.group(4)
    return " ".join(out)


def ordinal(n):
    n = int(n)
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def squash(text):
    """Letters and digits only, in capitals: how contest titles are compared, whatever their spacing."""
    return re.sub(r"[^A-Z0-9]", "", (text or "").upper())


def county_key(name):
    return re.sub(r"[^a-z]", "", fold((name or "").replace("_", " ")))


def classify(title):
    """(key, groups) for one of this loader's offices, ("other", why) for anything else, (None, None) if not understood."""
    s = squash(title)
    s = re.sub(r"^FOR", "", s)
    s = re.sub(r"(?:REP|DEM)$", "", s) if re.search(r"\((?:REP|DEM)\)\s*$", title or "") else s
    for pat, key in OFFICE_PATTERNS:
        m = pat.fullmatch(s)
        if m:
            return key, m.groupdict()
    for pat, why in OTHER_PATTERNS:
        if pat.search(s):
            return "other", why
    return None, None


# ---------- the counties ----------

def census_counties(path=COUNTY_ZIP):
    """{GEOID: "Autauga County"} for Alabama's 67 counties, from the Census Bureau's file."""
    import shapefile                                   # pyshp
    if not os.path.exists(path):
        raise SystemExit(f"Alabama (state races): the Census county file is missing ({path}); the county pages' stage fetches it")
    z = zipfile.ZipFile(path)
    base = next(n[:-4] for n in z.namelist() if n.endswith(".dbf"))
    rdr = shapefile.Reader(dbf=io.BytesIO(z.read(base + ".dbf")))
    fields = [f[0] for f in rdr.fields[1:]]
    out = {}
    for rec in rdr.iterRecords():
        rec = dict(zip(fields, rec))
        if str(rec.get("STATEFP")) == FIPS:
            out[str(rec["GEOID"])] = str(rec["NAMELSAD"])
    if len(out) != COUNTIES:
        raise SystemExit(f"Alabama (state races): the county file gives {len(out)} Alabama counties, not {COUNTIES}")
    return out


# ---------- the races ----------

def race_of(key, g, geoid_of):
    """The race a classified contest belongs to: (race_id, fields), or (None, why)."""
    base = dict(district=None, seat=None, jurisdiction=NAME, jurisdiction_id=FIPS)
    if key in EXEC:
        level, kind, office, _h = EXEC[key]
        return f"2026-{STATE}-{key}", dict(base, level=level, office_kind=kind, office=office)
    if key in PLACED:
        level, kind, office = PLACED[key]
        n = int(g["a"])
        return f"2026-{STATE}-{key}{n}", dict(base, level=level, office_kind=kind, office=office, seat=f"Place {n}")
    if key == "SBOE":
        d = str(int(g["a"]))
        return f"2026-{STATE}-SBOE{d}", dict(base, level="statewide", office_kind="state_board_of_education",
                                              office="Member of the State Board of Education", district=d,
                                              jurisdiction=f"State Board of Education District {d}", jurisdiction_id=f"SBOE{d}")
    if key in ("SS", "SH"):
        d = str(int(g["a"]))
        if not 1 <= int(d) <= (SENATE_SEATS if key == "SS" else HOUSE_SEATS):
            return None, f"a {'Senate' if key == 'SS' else 'House'} district that does not exist ({d})"
        word = "Senate" if key == "SS" else "House"
        return f"2026-{STATE}-{key}{d}", dict(base, level="legislature", office_kind=KIND_OF[key],
                                               office="State Senator" if key == "SS" else "State Representative", district=d,
                                               jurisdiction=f"{word} District {d}", jurisdiction_id=d)
    if key == "CC":
        c, p = int(g["a"]), int(g["b"])
        return f"2026-{STATE}-CC{c}-{p}", dict(base, level="court", office_kind="circuit_court", office="Circuit Court Judge",
                                                district=str(c), seat=f"Place {p}", jurisdiction=f"{ordinal(c)} Judicial Circuit",
                                                jurisdiction_id=f"JC{c}")
    if key == "DC":
        geoid = geoid_of.get(county_key(g["c"]))
        if not geoid:
            return None, f"a district court whose county could not be read ({g['c']!r})"
        p = int(g["b"]) if g.get("b") else None
        return (f"2026-{STATE}-DC{geoid[2:]}" + (f"-{p}" if p else ""),
                dict(base, level="court", office_kind="district_court", office="District Court Judge", seat=f"Place {p}" if p else None,
                     jurisdiction=geoid_of["_name"][geoid], jurisdiction_id=geoid))
    return None, f"an office this loader does not know ({key})"


# ---------- the sample ballots ----------

def contests(path):
    """Every contest drawn on one county's sample ballot, with the date heading of the style it belongs to:
    [(date, title, [[name, party], ...], write-in line, vote for)]. Text below 2 points (a tagged copy of a heading
    that some counties' files carry) is not ballot text and is skipped."""
    L = [ln for ln in ballot_lines(path) if ln[2] >= 2]
    out, when, i = [], None, 0
    while i < len(L):
        t = L[i][3]
        m = DATE.match(t)
        if m:
            when = f"{m.group(3)}-{MONTHS.index(m.group(1)) + 1:02d}-{int(m.group(2)):02d}"
        if not t.startswith("FOR ") or VOTE_FOR.search(t):
            i += 1
            continue
        head, j = [t], i + 1
        while j < len(L) and not VOTE_FOR.match(L[j][3]) and j - i < 6:
            head.append(L[j][3])
            j += 1
        if j >= len(L) or not VOTE_FOR.match(L[j][3]):
            i += 1                                          # not a contest ("FOR PROPOSED TAXATION" and the like)
            continue
        vote_for = VOTE_FOR.match(L[j][3]).group(1).lower()
        cands, x0, size0 = [], None, None
        j += 1
        while j < len(L) and not L[j][3].startswith("Write-in"):
            x, _y, size, name = L[j]
            if x0 is None:
                x0, size0 = x, size
            elif abs(x - x0) > 1.5 or abs(size - size0) > 0.3:
                break
            if not NAME_LINE.match(name) or name.startswith("SAMPLE") or name.startswith("FOR ") or DATE.match(name):
                break
            party = None
            if j + 1 < len(L) and abs(L[j + 1][0] - x0) <= 1.5 and L[j + 1][2] < 0.8 * size0 and not L[j + 1][3].startswith("Write-in"):
                party = L[j + 1][3]
                j += 1
            cands.append([name, party])
            j += 1
        out.append((when, re.sub(r"\s+", " ", " ".join(head).replace(" ,", ",")).strip(), cands,
                    j < len(L) and L[j][3].startswith("Write-in"), vote_for))
        i = j
    return out


def manifest(folder, say):
    """[(county, file name, address)] for the 67 general election sample ballots: from the federal loader's record
    of them when it is there, else from the Secretary's page."""
    fed = os.path.join(folder, "al_2026_general_sample_ballots_federal.json")
    if os.path.exists(fed):
        data = json.load(open(fed, encoding="utf-8"))
        return [(f["county"], f["file"], f["url"], f.get("sha256")) for f in data["files"]], data.get("read")
    say("      reading the Secretary's list of sample ballots")
    return [(c, f, u, None) for c, _p, f, u in sample_links("general")], dt.date.today().isoformat()


def read_ballots(folder, keep, geoid_of, say):
    """The kept cells of every county's sample ballot (this loader's contests only, and counts of the rest), cached as
    JSON in `keep` by each file's SHA-256, so a ballot is read again only when its file changes."""
    files, listed = manifest(folder, say)
    if len(files) != COUNTIES:
        raise SystemExit(f"Alabama (state races): {len(files)} county sample ballots are listed, not {COUNTIES}")
    pdfs = os.path.join(folder, "sample_general")
    os.makedirs(pdfs, exist_ok=True)
    path = os.path.join(keep, KEPT)
    old = {}
    if os.path.exists(path):
        prev = json.load(open(path, encoding="utf-8"))
        if prev.get("version") == KEPT_VERSION:
            old = {f["sha256"]: f for f in prev["files"]}
    out, changed, warn = [], 0, []
    for county, file, url, fed_sha in files:
        pdf = os.path.join(pdfs, file)
        if not os.path.exists(pdf):
            fetch(url, pdf, b"%PDF-", f"the {county} County sample ballot", say, days=3650)
        sha = sha256(pdf)
        if fed_sha and sha != fed_sha:
            warn.append(f"{county} County's sample ballot on disk is not the one the federal loader read (it was replaced since)")
        if sha in old and old[sha]["file"] == file:
            out.append(old[sha])
            continue
        changed += 1
        kept, other, unknown = collections.defaultdict(int), collections.Counter(), collections.Counter()
        for when, title, cands, write_in, vote_for in contests(pdf):
            key, g = classify(title)
            if key == "other":
                other[f"{g}|{when}"] += 1
                continue
            if key is None:
                unknown[when] += 1
                continue
            rid, info = race_of(key, g, geoid_of)
            if rid is None:
                unknown[when] += 1
                continue
            kept[json.dumps([when, rid, title, cands, bool(write_in), vote_for])] += 1
        out.append({"county": county, "file": file, "url": url, "sha256": sha, "bytes": os.path.getsize(pdf),
                    "contests": [dict(zip(("date", "race", "title", "cands", "write_in", "vote_for"), json.loads(k)), drawn=n)
                                 for k, n in sorted(kept.items())],
                    "other": dict(sorted(other.items())), "unknown": dict(sorted(unknown.items(), key=str))})
    if changed or not os.path.exists(path):
        os.makedirs(keep, exist_ok=True)
        json.dump({"version": KEPT_VERSION, "page": SAMPLE_PAGES["general"], "listed": listed, "read": dt.date.today().isoformat(),
                   "files": out}, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    say(f"    Alabama (state races): {len(out)} county sample ballots ({changed} read afresh, the rest from the kept cells)")
    return out, path, warn


def name_forms(name):
    """A name as printed, and with a quoted nickname in place of the given names (J.T. "Jabo" Waggoner -> Jabo Waggoner)."""
    out = [name]
    m = re.search(r"[\"“]([^\"”]+)[\"”]", name)
    if m:
        rest = (name[:m.start()] + name[m.end():]).split()
        family = [w for w in rest if fold(w) and fold(w) not in ("jr", "sr", "ii", "iii", "iv")]
        if family:
            out.append(f"{m.group(1)} {family[-1]}")
        out.append(re.sub(r"\s+", " ", name[:m.start()] + name[m.end():]).strip())
    return out


def alike(a, b):
    """Two printings of one person: the same letters, or the same family name and a given name (or nickname) that fits."""
    if same_person(a, b):
        return True
    return any(fits(name_parts(x), name_parts(y)) for x in name_forms(a) for y in name_forms(b))


def on_every_ballot(r):
    """An office every voter in the state votes for."""
    return (r["level"] == "statewide" and r["office_kind"] != "state_board_of_education") or r["office_kind"] in (
        "supreme_court", "court_of_civil_appeals", "court_of_criminal_appeals")


def agreed(files, geoid_of, problems, checks):
    """{race: ([[name, party], ...], write-in, {counties}, styles drawn)} for every race whose 2026 styles, in every
    county, print it the same way (letters compared: a space or a capital aside); the races whose counties disagree;
    styles of other dates set aside. Where counties space or capitalize a name differently, the printing of the most
    counties (then the most styles) is kept, and the check says so."""
    seen = collections.defaultdict(lambda: collections.defaultdict(lambda: collections.defaultdict(set)))
    styles = collections.Counter()
    counties, fields, older, drawn = collections.defaultdict(set), {}, collections.Counter(), collections.Counter()
    for f in files:
        geoid = geoid_of[county_key(f["county"])]
        for k in f["contests"]:
            if k["date"] != GENERAL:
                older[(f["county"], k["date"])] += k["drawn"]
                continue
            if k["vote_for"] != "one":
                problems.append(f"{k['race']}: {f['county']} County's ballot says 'Vote for {k['vote_for']}'")
            cands = []
            for name, printed in k["cands"]:
                if printed is not None:
                    if printed.strip().lower() not in PRINTED:
                        raise SystemExit(f"Alabama (state races): {f['county']} County's sample ballot prints a party this loader "
                                         f"does not know for {k['race']}")
                    printed = PRINTED[printed.strip().lower()]
                cands.append((name, printed))
            letters = (tuple((squash(n), p) for n, p in cands), bool(k["write_in"]))
            seen[k["race"]][letters][tuple(cands)].add(f["county"])
            styles[(k["race"], tuple(cands))] += k["drawn"]
            counties[k["race"]].add(geoid)
            drawn[k["race"]] += k["drawn"]
            if k["race"] not in fields:
                fields[k["race"]] = k["title"]
    races, split = {}, {}
    for race, versions in seen.items():
        if len(versions) > 1:
            split[race] = {"; ".join(f"{n} ({p})" for n, p in next(iter(v))): sorted(set().union(*v.values()))
                           for _letters, v in versions.items()}
            continue
        (letters, printings), = versions.items()
        best = max(printings, key=lambda c: (len(printings[c]), styles[(race, c)], c))
        if len(printings) > 1:
            names = sorted({n for c in printings for n, _p in c} - {n for n, _p in best})
            where = sorted(set().union(*(v for c, v in printings.items() if c != best)))
            checks.append(f"{race}: {'; '.join(names)} is spaced or capitalized differently on some styles in "
                          f"{', '.join(where)} (county ballots); the printing used by {len(printings[best])} "
                          f"{'county' if len(printings[best]) == 1 else 'counties'} is kept")
        races[race] = ([list(c) for c in best], letters[1], counties[race], drawn[race])
    return races, split, older


# ---------- the results ----------

def precinct_results(path, geoid_of, problems, variants, what):
    """This loader's contests in one precinct results zip: {(race, code): {candidate: votes}}, the over and under
    votes {(race, code, kind): votes}, the counties each race was voted in, the titles set aside by kind, and the
    counties read. A name printed with different punctuation or capitals in different county files is one candidate
    (the printing of the most files is shown), and `variants` says so."""
    tally = collections.defaultdict(lambda: collections.defaultdict(int))
    printed = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
    blanks = collections.defaultdict(int)
    where, other, counties = collections.defaultdict(set), collections.Counter(), []
    cast, by_county = {}, collections.defaultdict(int)
    with zipfile.ZipFile(path) as z:
        for n in sorted(z.namelist()):
            m = re.fullmatch(r"2026_PRIMARY(?:_RUNOFF)?_ELECTION-(.+)\.xls", n)
            if not m:
                raise SystemExit(f"Alabama (state races): an unexpected file in {os.path.basename(path)}: {n}")
            geoid = geoid_of.get(county_key(m.group(1)))
            if not geoid:
                raise SystemExit(f"Alabama (state races): {n}: the county could not be read")
            counties.append(geoid)
            for sheet, rows in xls_sheets(z.read(n)).items():
                if not rows:
                    continue
                if [str(c or "").strip() for c in rows[0][:3]] != ["Contest Title", "Party", "Candidate"]:
                    raise SystemExit(f"Alabama (state races): {n} ({sheet}) does not begin Contest Title, Party, Candidate")
                for r in rows[1:]:
                    title = re.sub(r"\s+", " ", str(r[0] or "")).strip()
                    if not title:
                        continue
                    m = re.fullmatch(r"BALLOTS CAST - (REPUBLICAN|DEMOCRAT) \((REP|DEM)\)", title)
                    if m:
                        cast[(geoid, m.group(2))] = number(sum(v for v in r[3:] if isinstance(v, float)))
                    key, g = classify(title)
                    if key == "other":
                        other[g] += 1
                        continue
                    if key is None:
                        other["not understood"] += 1
                        problems.append(f"{what}: a contest title in {n} was not understood (row {rows.index(r) + 1})")
                        continue
                    rid, info = race_of(key, g, geoid_of)
                    if rid is None:
                        problems.append(f"{what}: {n} row {rows.index(r) + 1}: {info}")
                        continue
                    code = str(r[1] or "").strip()
                    mark = re.search(r"\((REP|DEM)\)\s*$", title)
                    if code not in PARTY or (mark and mark.group(1) != code):
                        raise SystemExit(f"Alabama (state races): {n}: {rid} lists a candidate of an unexpected party")
                    cand = re.sub(r"\s+", " ", str(r[2] or "")).strip()
                    if any(v is not None and not isinstance(v, float) and str(v).strip() for v in r[3:]):
                        problems.append(f"{what}: {n}: a vote cell of {rid} is not a number (the row's other cells are counted)")
                    votes = number(sum(v for v in r[3:] if isinstance(v, float)))
                    where[rid].add(geoid)
                    if info["level"] == "statewide" and info["office_kind"] != "state_board_of_education":
                        by_county[(rid, code, geoid)] += votes
                    if cand in ("Over Votes", "Under Votes"):
                        blanks[(rid, code, cand)] += votes
                        continue
                    if not cand:
                        raise SystemExit(f"Alabama (state races): {n}: a row of {rid} has no candidate name")
                    k = fold(cand).replace(" ", "")                     # O'Hara-Grant in one county's file, O`hara-Grant in another's
                    tally[(rid, code)][k] += votes
                    printed[(rid, code)][k][cand] += 1
    totals = {}
    for key, per in tally.items():
        totals[key] = {}
        for k, votes in per.items():
            forms = printed[key][k]
            name = max(forms, key=lambda f: ("`" not in f, forms[f], f))    # a backtick for an apostrophe is a typing slip
            if len(forms) > 1:
                variants.append(f"{key[0]} ({PARTY_OF[key[1]]} {what}): {' / '.join(sorted(forms))} printed in different county files; "
                                f"counted as one, shown as {name}")
            totals[key][name] = votes
        names = sorted(totals[key])
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                if alike(a, b):
                    variants.append(f"{key[0]} ({PARTY_OF[key[1]]} {what}): {a} and {b} may be one person printed two ways; kept apart")
    # a statewide contest's votes, with its over and under votes, against the party's ballots cast in each county
    diffs = [abs(n - cast[(g, c)]) for (rid, c, g), n in by_county.items() if (g, c) in cast]
    recon = (sum(1 for d in diffs if d == 0), len(diffs), max(diffs, default=0), len(by_county) - len(diffs))
    return totals, blanks, where, other, counties, recon


def dem_workbook(path, geoid_of):
    """The Democratic Party's certified totals (sheet Candidates: Office, District/Jurisdiction, Place, Ballot Name, a
    column per county, TOTAL) for this loader's offices: {(race, name): total}."""
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    rows = wb["Candidates"].iter_rows(values_only=True)
    head = [str(c or "").strip() for c in next(rows)]
    if head[:4] != ["Office", "District/Jurisdiction", "Place", "Ballot Name"] or head[-1] != "TOTAL":
        raise SystemExit(f"Alabama (state races): {os.path.basename(path)} does not have the columns it had")
    out = {}
    for r in rows:
        office = str(r[0] or "").strip()
        if not office:
            continue
        district, place = (str(int(v)) if isinstance(v, (int, float)) else str(v or "").strip() for v in (r[1], r[2]))
        title = office + (f" District {district}" if district and not re.search(r"[A-Za-z]", district) else f" {district}")
        if place:
            title += f" Place {place}"
        key, g = classify(title)
        if key in (None, "other"):
            continue
        rid, _info = race_of(key, g, geoid_of)
        if rid:
            out[(rid, str(r[3] or "").strip())] = number(r[len(head) - 1])
    wb.close()
    return out


def rep_workbook(path, geoid_of):
    """The Republican Party's certified totals, from its Summary sheet (blocks: the office with "Votes" and
    "Percentage", a row per candidate, a Total row): {(race, name): total}."""
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    out, race = {}, None
    for r in wb["Summary"].iter_rows(values_only=True):
        a = str(r[0] or "").strip() if r else ""
        b = str(r[1] or "").strip() if len(r) > 1 else ""
        if b == "Votes":
            key, g = classify(a)
            race = race_of(key, g, geoid_of)[0] if key not in (None, "other") else None
            continue
        if a == "Total":
            race = None
            continue
        if race and a:
            out[(race, a)] = number(b)
    wb.close()
    return out


def compare(totals, cert, code, stage):
    """Where a party's certified workbook differs from the Secretary's precinct files, in words; and how many of the
    Secretary's contests the workbook carries."""
    out, carried, of = [], 0, 0
    races = {r for r, _n in cert}
    for (race, c), cands in sorted(totals.items()):
        if c != code:
            continue
        of += 1
        if race not in races:
            continue
        carried += 1
        diffs, used = [], set()
        names = [n for r, n in cert if r == race]
        for name, votes in sorted(cands.items()):
            hit = ([n for n in names if fold(n) == fold(name)] or [n for n in names if alike(n, name)]
                   or [n for n in names if name_parts(n)[1] == name_parts(name)[1]])
            if len(hit) != 1:
                diffs.append(f"{name} is not in the workbook")
                continue
            used.add(hit[0])
            spelled = "" if fold(hit[0]) == fold(name) else f" (spelled {hit[0]} there)"
            theirs = cert[(race, hit[0])]
            if theirs != votes:
                diffs.append(f"{name}{spelled}: the workbook gives {'no figure' if theirs is None else format(theirs, ',')}, the precinct "
                             f"files {votes:,}")
            elif spelled:
                diffs.append(f"{name}{spelled}: the same votes")
        extra = [n for n in names if n not in used]
        if extra:
            diffs.append("the workbook also names " + ", ".join(extra))
        if diffs:
            out.append(f"{race} ({PARTY_OF[code]} {stage}): {'; '.join(diffs)}")
    return out, carried, of


# ---------- the roster ----------

def roster(path):
    """Sitting legislators {(chamber, district): [member]} and the officials {office: member}: ids, names, party only."""
    if not os.path.exists(path):
        return {}, {}, ""
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    seats = collections.defaultdict(list)
    for r in con.execute("SELECT bioguide_id, first_name, last_name, official_full, other_names, party_name, chamber, district "
                         "FROM legislators WHERE is_current = 1"):
        seats[(r[6], str(r[7]).strip())].append({"id": r[0], "first": r[1], "last": r[2], "full": r[3], "other": r[4], "party": r[5]})
    offs = {}
    for r in con.execute("SELECT bioguide_id, first_name, last_name, official_full, party_name, office FROM officials"):
        offs[r[5]] = {"id": r[0], "first": r[1], "last": r[2], "full": r[3], "other": None, "party": r[4]}
    as_of = (con.execute("SELECT max(updated_at) FROM legislators").fetchone()[0] or "")[:10]
    con.close()
    return seats, offs, as_of


def member_fits(name, m):
    """The roster's own full name, or its given and family names (its "other names" are initials, too loose to use)."""
    forms = [m["full"], f"{m['first']} {m['last']}"]
    return any(fits(name_parts(x), name_parts(f)) for x in name_forms(name) for f in forms if f)


# ---------- sources ----------

def mdate(path):
    return dt.date.fromtimestamp(os.path.getmtime(path)).isoformat() if os.path.exists(path) else ""


def local_or_fetch(folder, key, say):
    """A results file from the cache the federal loader fills; fetched from the Secretary's site only if missing."""
    url, name = FILES[key]
    path = os.path.join(folder, name)
    if not os.path.exists(path):
        fetch(SOS + url, path, b"PK", f"the file {name}", say, days=3650)
    return path


# ---------- the load ----------

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


def load(db_path, say=print, folder=FOLDER, roster_db=ROSTER, county_zip=COUNTY_ZIP, keep=None):
    keep = keep or folder
    problems, checks = [], []
    counties = census_counties(county_zip)
    geoid_of = {county_key(n.replace(" County", "")): g for g, n in counties.items()}
    geoid_of["_name"] = counties

    # 1. the November ballot
    files, kept_path, warn = read_ballots(folder, keep, geoid_of, say)
    problems += warn
    general, split, older = agreed(files, geoid_of, problems, checks)
    other_general = collections.Counter()
    unknown_general = 0
    for f in files:
        for k, n in f["other"].items():
            why, when = k.rsplit("|", 1)
            if when == GENERAL:
                other_general[why] += n
        unknown_general += sum(n for when, n in f["unknown"].items() if when == GENERAL)
    if unknown_general:
        problems.append(f"{unknown_general} contests drawn on the November styles were not understood (not loaded)")
    if other_general.get(COURT_UNREAD):
        problems.append(f"{other_general[COURT_UNREAD]} court contests drawn on the November styles were not understood (not loaded)")

    races = {}

    def add_race(rid, info, why=None):
        if rid in races:
            return races[rid]
        r = dict(info, race_id=rid, note=[], county_set=set(), prim_set=set(), holder=None)
        races[rid] = r
        return r

    for d in range(1, SENATE_SEATS + 1):
        add_race(*race_of("SS", {"a": str(d)}, geoid_of))
    for d in range(1, HOUSE_SEATS + 1):
        add_race(*race_of("SH", {"a": str(d)}, geoid_of))
    titles = {k["race"]: k["title"] for f in files for k in f["contests"]}
    for rid in sorted(set(general) | set(split)):
        added = race_of(*classify(titles[rid]), geoid_of)
        if added[0] != rid:
            raise SystemExit(f"Alabama (state races): the kept title of {rid} no longer gives the same race")
        add_race(*added)

    # 2. who holds each seat
    seats, offs, as_of = roster(roster_db)
    if not seats:
        problems.append("the roster (state_al.sqlite) is missing; no holders or incumbents are marked")
    for rid, r in races.items():
        h = None
        if r["office_kind"] in ("state_senate", "state_house"):
            r["note"].append(LEG_NOTE)
            hs = seats.get(("Senate" if r["office_kind"] == "state_senate" else "House", r["district"]), [])
            if len(hs) == 1:
                h = hs[0]
            elif not hs and seats:
                r["note"].append(VACANT)
                checks.append(f"{rid}: no sitting member in the roster")
            elif hs:
                checks.append(f"{rid}: the roster lists {len(hs)} sitting members for one seat; none is shown")
        else:
            key = re.match(rf"2026-{STATE}-([A-Z]+)", rid).group(1)
            office = EXEC.get(key, (None, None, None, None))[3]
            h = offs.get(office) if office else None
            if not h:
                r["note"].append(NO_HOLDER)
        r["holder"] = h

    # 3. the November candidates
    cands = []                 # [race, election, date, name, party, code, order, incumbent, write_in, votes, pct, outcome, member, source, note]
    nominees = collections.defaultdict(dict)
    for rid in sorted(split):
        races[rid]["note"].append(SPLIT_NOTE)
        problems.append(f"{rid}: the counties' sample ballots disagree: {split[rid]}")
    for rid, (clist, write_in, where, _drawn) in sorted(general.items()):
        r = races[rid]
        r["county_set"] |= where
        if not write_in:
            problems.append(f"{rid}: no Write-in line on the sample ballots")
        seen_parties = set()
        for order, (name, printed) in enumerate(clist, start=1):
            if not printed:
                problems.append(f"{rid}: a candidate has no party printed beneath the name (not loaded)")
                continue
            if printed in seen_parties and printed != "Independent":         # a party nominates one; independents qualify each on their own
                raise SystemExit(f"Alabama (state races): {rid}: two {printed} candidates on the sample ballots")
            seen_parties.add(printed)
            display = shown(name)
            if printed != "Independent":
                nominees[rid][printed] = display
            cands.append([rid, "general", GENERAL, display, printed, party_code(printed), order, 0, 0, None, None, None, None, SRC_GENERAL, CAPS])
        if on_every_ballot(r):
            if len(where) != COUNTIES:
                problems.append(f"{rid}: printed on {len(where)} of {COUNTIES} counties' sample ballots")
    set_aside = collections.Counter()
    for (county, date), n in older.items():
        set_aside[date] += n
        if date is None:
            problems.append(f"{county} County's sample ballot draws a contest before any date heading")

    # 4. the primary and the runoff
    paths = {k: local_or_fetch(folder, k, say) for k in ("primary", "runoff", "dem_primary", "rep_primary", "dem_runoff")}
    variants = []
    ptot, pblank, pwhere, pother, pcounties, precon = precinct_results(paths["primary"], geoid_of, problems, variants, "primary")
    rtot, rblank, rwhere, rother, rcounties, rrecon = precinct_results(paths["runoff"], geoid_of, problems, variants, "runoff")
    checks += variants

    def settle(tot, where, what):
        """A district court contest whose results title names no place (DISTRICT COURT JUDGE, PICKENS COUNTY) belongs to
        the county's one district court race on the November ballot, when there is exactly one."""
        out = {}
        for (rid, code), cc in tot.items():
            m = re.fullmatch(rf"2026-{STATE}-DC(\d{{3}})", rid)
            if rid not in races and m:
                one = [r for r in races if r.startswith(f"2026-{STATE}-DC{m.group(1)}-")]
                if len(one) == 1:
                    checks.append(f"{rid} ({PARTY_OF[code]} {what}): the results title names no place; filed under {one[0]}, the "
                                  "county's one district court race on the November ballot")
                    where[one[0]] = where.get(one[0], set()) | where.pop(rid, set())
                    rid = one[0]
            out[(rid, code)] = cc
        return out

    ptot, rtot = settle(ptot, pwhere, "primary"), settle(rtot, rwhere, "runoff")
    fields = collections.Counter()
    orphan = []

    def nominee(rid, code):
        return nominees.get(rid, {}).get(PARTY[code])

    def elsewhere(name, rid):
        """Other races of the same office whose November ballot prints this person."""
        kind = races[rid]["office_kind"]
        return sorted({c[0] for c in cands if c[1] == "general" and c[0] != rid and races[c[0]]["office_kind"] == kind and alike(name, c[3])})

    def not_nominee(rid, code, winner, final, stage):
        other = elsewhere(winner, rid)
        where_now = " and ".join(races[o]["jurisdiction"] for o in other)
        problems.append(f"{rid} {code}: the {stage}'s winner ({winner}) is not the party's candidate on the sample ballots ({final})"
                        + (f"; the ballots print {winner} for {where_now}" if other else ""))
        races[rid]["note"].append(f"The {PARTY_OF[code]} candidate on the November ballot, {final}, is not the winner of the party's "
                                  f"{stage}; the files read here do not say why (the parties' certifications of their nominees are "
                                  "scanned documents).")
        return (f"Won the {PARTY_OF[code]} {stage} for this seat; the November sample ballots print this candidate for {where_now} "
                "instead.") if other else NOT_ON_BALLOT.format(party=PARTY_OF[code])

    for (rid, code), cc in sorted(ptot.items()):
        if rid not in races:
            orphan.append(f"{rid} ({PARTY_OF[code]} primary)")
            continue
        races[rid]["prim_set"] |= pwhere[rid]
        if len(cc) < 2:
            continue
        fields["primary"] += 1
        total = sum(cc.values())
        ranked = sorted(cc, key=lambda n: (-cc[n], n))
        runoff = 2 * cc[ranked[0]] <= total
        won = ranked[:2] if runoff else ranked[:1]
        final = nominee(rid, code)
        held = (rid, code) in rtot
        win_note = None
        if runoff and held:
            pair = rtot[(rid, code)]
            if len(pair) != 2 or not all(any(alike(a, b) for b in pair) for a in won):
                problems.append(f"{rid} {code}: the runoff lists {sorted(pair)}, the primary's top two were {won}")
        elif runoff:
            checks.append(f"{rid} {code}: no majority on May 19 and no runoff in the runoff results "
                          f"(the November ballot prints {final or 'no one'} for the party)")
        elif final and not alike(won[0], final):
            win_note = not_nominee(rid, code, won[0], final, "primary")
        elif not final and rid in general:
            win_note = NOT_ON_BALLOT.format(party=PARTY_OF[code])
        for name in ranked:
            note = None
            if runoff and name in won:
                note = RUNOFF_NOTE if held else NO_RUNOFF
            elif name in won:
                note = win_note
            cands.append([rid, f"primary-{code}", PRIMARY, name, PARTY[code], party_code(PARTY[code]), None, 0, 0, cc[name],
                          round(100 * cc[name] / total, 1) if total else None, "advanced" if name in won else "lost", None, SRC_PRIMARY, note])
    for (rid, code), cc in sorted(rtot.items()):
        if rid not in races:
            orphan.append(f"{rid} ({PARTY_OF[code]} runoff)")
            continue
        races[rid]["prim_set"] |= rwhere[rid]
        if len(cc) < 2:
            continue
        fields["runoff"] += 1
        total = sum(cc.values())
        ranked = sorted(cc, key=lambda n: (-cc[n], n))
        if 2 * cc[ranked[0]] == total:
            problems.append(f"{rid} {code}: the runoff is tied")
        final = nominee(rid, code)
        if (rid, code) not in ptot:
            problems.append(f"{rid} {code}: a runoff with no primary in the May 19 results")
        win_note = None
        if final and not alike(ranked[0], final):
            win_note = not_nominee(rid, code, ranked[0], final, "runoff")
        elif not final and rid in general:
            win_note = NOT_ON_BALLOT.format(party=PARTY_OF[code])
        for name in ranked:
            cands.append([rid, f"runoff-{code}", RUNOFF, name, PARTY[code], party_code(PARTY[code]), None, 0, 0, cc[name],
                          round(100 * cc[name] / total, 1) if total else None, "advanced" if name == ranked[0] else "lost", None, SRC_RUNOFF,
                          win_note if name == ranked[0] else None])
    for o in orphan:
        problems.append(f"{o}: in the results but not printed on any November sample ballot (not stored)")

    # the parties' certified workbooks, as a check on the precinct files
    dem_p, rep_p, dem_r = (dem_workbook(paths["dem_primary"], geoid_of), rep_workbook(paths["rep_primary"], geoid_of),
                           dem_workbook(paths["dem_runoff"], geoid_of))
    chk = {"dem_primary": compare(ptot, dem_p, "DEM", "primary"), "rep_primary": compare(ptot, rep_p, "REP", "primary"),
           "dem_runoff": compare(rtot, dem_r, "DEM", "runoff")}

    # 5. incumbents: a candidate who fits the sitting member, one fit only in each election of the race
    by_election = collections.defaultdict(list)
    for c in cands:
        by_election[(c[0], c[1])].append(c)
    for (rid, _e), rows in by_election.items():
        h = races[rid]["holder"]
        if not h:
            continue
        hit = [c for c in rows if member_fits(c[3], h)]
        if len(hit) == 1:
            hit[0][7], hit[0][12] = 1, h["id"]
        elif len(hit) > 1:
            checks.append(f"{rid} {_e}: more than one name fits the sitting member; none is marked")

    # 6. every seat has its candidates, or says why not
    for rid, r in races.items():
        if rid in split:
            continue
        if not any(c[0] == rid and c[1] == "general" for c in cands):
            r["note"].append(NOT_PRINTED)
            checks.append(f"{rid}: no candidate printed on any November sample ballot")
        if on_every_ballot(r):
            r["county_set"] = set(counties)
            continue
        if r["county_set"] and r["prim_set"] and r["prim_set"] != r["county_set"]:
            name = lambda gs: ", ".join(counties[g].replace(" County", "") for g in sorted(gs))
            checks.append(f"{rid}: the primary was voted in {name(r['prim_set'])}; the November ballots print the seat in "
                          f"{name(r['county_set'])}")
            r["note"].append(f"The party primaries for this seat were voted in {name(r['prim_set'])} "
                             f"{'County' if len(r['prim_set']) == 1 else 'counties'}; the November sample ballots print it in "
                             f"{name(r['county_set'])} {'County' if len(r['county_set']) == 1 else 'counties'}.")
        if r["county_set"]:
            r["note"].append(DERIVED)
        elif r["prim_set"]:
            r["county_set"] = set(r["prim_set"])
            r["note"].append(DERIVED_RESULTS)

    # 7. the last look at every stored text: nothing that looks like a contact detail reaches the database
    for c in cands:
        if CONTACT.search(c[3]) or CONTACT.search(c[4] or ""):
            raise SystemExit(f"Alabama (state races): a stored name for {c[0]} failed the contact-detail check (not shown)")
    keys = [(c[0], c[1], c[3]) for c in cands]
    dup = [k for k, n in collections.Counter(keys).items() if n > 1]
    if dup:
        raise SystemExit(f"Alabama (state races): two candidate rows share race, election and name: {dup[:3]}")

    # 8. places
    place_rows = [("county", g, n, json.dumps([g]), SRC_COUNTY) for g, n in sorted(counties.items())]
    for rid, r in sorted(races.items()):
        kind = {"state_senate": "senate", "state_house": "house", "circuit_court": "judicial", "state_board_of_education": "sboe"}.get(r["office_kind"])
        if kind and r["county_set"]:
            pid = f"{STATE}-{r['district']}" if kind in ("senate", "house", "sboe") else f"{STATE}-{r['jurisdiction_id']}"
            if not any(p[0] == kind and p[1] == pid for p in place_rows):
                place_rows.append((kind, pid, r["jurisdiction"], json.dumps(sorted(r["county_set"])), SRC_GENERAL))

    # 9. write Alabama's rows only, in one transaction
    race_rows = []
    for rid, r in sorted(races.items()):
        h = r["holder"]
        race_rows.append((rid, STATE, r["level"], r["office_kind"], r["office"], r["jurisdiction"], r["jurisdiction_id"],
                          json.dumps(sorted(r["county_set"])) if r["county_set"] else None, r["district"], r["seat"], 0, 1,
                          h["id"] if h else None, h["full"] if h else None, h["party"] if h else None, GENERAL,
                          " ".join(r["note"]) or None))
    gen_rows = [c for c in cands if c[1] == "general"]
    older_note = (", ".join(f"{n} contests dated {d}" for d, n in sorted(set_aside.items(), key=str))
                  + " (in " + ", ".join(sorted({c for c, _d in older})) + ")") if older else "none"
    other_note = "; ".join(f"{why}: {n}" for why, n in sorted(other_general.items()))
    kept_sha = hashlib.sha256(json.dumps(sorted(f["sha256"] for f in files)).encode()).hexdigest()

    def blanks_note(blanks, recon):
        over = sum(v for (r, c, k), v in blanks.items() if k == "Over Votes")
        under = sum(v for (r, c, k), v in blanks.items() if k == "Under Votes")
        ok, n, most, _none = recon
        return (f"{over:,} over votes and {under:,} under votes in these contests are not counted in anyone's share. Each "
                f"statewide contest's votes, with its over and under votes, equal the party's BALLOTS CAST line in {ok} of the {n} "
                f"county returns" + (f" and differ by at most {most:,} in the rest" if ok < n else ""))

    def chk_note(key, stage):
        diffs, carried, of = chk[key]
        return (f"The party's workbook carries {carried} of the {of} contests; " +
                ("where it differs: " + "; ".join(diffs) + "." if diffs else "it agrees with every one."))

    sources = [
        (SRC_GENERAL, STATE, "official sample ballots", AGENCY,
         "2026 General Election Sample Ballots, November 3, 2026 (state offices, every county)", SAMPLE_PAGES["general"], "2026-09-10",
         mdate(kept_path), kept_sha, len(gen_rows),
         f"{len(files)} county sample ballots (PDF; every ballot style of the county drawn one over another), read in drawing order "
         "style by style; only the offices, names, parties, order and Write-in lines of the state contests are kept "
         f"({KEPT}). The sha256 here is of the list of the files' own SHA-256s. Every 2026 style of every county prints each race "
         f"the same way unless named in the loader's report. Styles of an older ballot drawn beneath, set aside: {older_note}. "
         f"Contests on the November styles that are not state offices, left to other pages: {other_note}. The State "
         "Certifications of candidates (August 26, 2026) are scans with no text, so the typeset sample ballots are read "
         "instead. A ballot shows no withdrawn candidates and no declared write-ins, so none are loaded. Ballot order as "
         "printed. Names printed in capitals are shown in ordinary capitals."),
        (SRC_PRIMARY, STATE, "official results", AGENCY, "2026 Primary Election, May 19, 2026: precinct results by county (state offices)",
         SOS + FILES["primary"][0], "2026-07-31", mdate(paths["primary"]), sha256(paths["primary"]),
         sum(len(v) for (rid, _c), v in ptot.items() if rid in races),
         f"{len(pcounties)} county files (.xls; Contest Title, Party, Candidate, a column per precinct, ABSENTEE, PROVISIONAL), "
         f"summed over the counties; {blanks_note(pblank, precon)}. Linked from {DATA_PAGE}. Checked against the parties' certified "
         f"vote totals: Democratic: {chk_note('dem_primary', 'primary')} Republican: {chk_note('rep_primary', 'primary')}"),
        (SRC_RUNOFF, STATE, "official results", AGENCY, "2026 Primary Runoff Election, June 16, 2026: precinct results by county (state offices)",
         SOS + FILES["runoff"][0], "2026-07-31", mdate(paths["runoff"]), sha256(paths["runoff"]),
         sum(len(v) for (rid, _c), v in rtot.items() if rid in races),
         f"{len(rcounties)} county files, read as the primary's; {blanks_note(rblank, rrecon)}. Checked against the Democratic Party's "
         f"certified workbook: {chk_note('dem_runoff', 'runoff')} The Republican Party's certification of the runoff "
         f"({REP_RUNOFF_SCAN}) is a scan with no text, so the Republican runoff is checked only against the November ballot."),
    ]
    for key, sid, title in (("dem_primary", SRC_DEM_P, "Certification of Results, Democratic Party: vote totals, 2026 Primary Election"),
                            ("rep_primary", SRC_REP_P, "Certification of Results, Republican Party: vote totals, 2026 Primary Election"),
                            ("dem_runoff", SRC_DEM_R, "Certification of Results, Democratic Party: vote totals, 2026 Primary Runoff")):
        sources.append((sid, STATE, "official results (a check)", ("Alabama Democratic Party" if key.startswith("dem") else
                        "Alabama Republican Party") + ", posted by the Alabama Secretary of State", title, SOS + FILES[key][0], "",
                        mdate(paths[key]), sha256(paths[key]), 0,
                        "Used only to check the Secretary of State's precinct files; the differences are named in their notes."))
    sources.append((SRC_ROSTER, STATE, "roster", "Open States people project (CC0), as loaded into state_al.sqlite",
                    "Alabama legislators and statewide officials", "https://github.com/openstates/people", "", as_of,
                    "", sum(1 for r in races.values() if r["holder"]),
                    "Who holds each seat today: names, party and ids only."))
    sources.append((SRC_COUNTY, STATE, "county codes", "U.S. Census Bureau", "2024 cartographic boundary file, counties (500k)",
                    COUNTY_URL, "", mdate(county_zip), sha256(county_zip) if os.path.exists(county_zip) else "", len(counties),
                    "County names and FIPS codes only."))

    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA)
    with con:
        con.execute("DELETE FROM sl_candidates WHERE race_id IN (SELECT race_id FROM sl_races WHERE state = ?) OR race_id LIKE ?",
                    (STATE, f"2026-{STATE}-%"))
        con.execute("DELETE FROM sl_races WHERE state = ?", (STATE,))
        con.execute("DELETE FROM sl_sources WHERE state = ?", (STATE,))
        con.execute("DELETE FROM sl_places WHERE source_id LIKE ?", (f"{STATE.lower()}-%",))
        con.executemany("INSERT INTO sl_races VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", race_rows)
        con.executemany("INSERT INTO sl_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [tuple(c) for c in cands])
        con.executemany("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", sources)
        con.executemany("INSERT INTO sl_places VALUES (?,?,?,?,?)", place_rows)
    con.close()

    # 10. say what happened
    per = collections.Counter(races[c[0]]["office_kind"] for c in gen_rows)
    seats_per = collections.Counter(r["office_kind"] for r in races.values())
    filled = collections.Counter(races[rid]["office_kind"] for rid in {c[0] for c in gen_rows})
    say(f"    Alabama (state races): {len(races)} races, {len(gen_rows)} candidates on the November ballot; "
        f"{fields['primary']} primary fields on May 19, {fields['runoff']} runoffs on June 16; "
        f"{sum(1 for c in cands if c[7] and c[1] == 'general')} sitting members or officials on the November ballot")
    for kind in sorted(seats_per):
        say(f"      {kind}: {seats_per[kind]} races, {filled[kind]} with candidates, {per[kind]} candidates")
    for key, stage in (("dem_primary", "Democratic primary"), ("rep_primary", "Republican primary"), ("dem_runoff", "Democratic runoff")):
        diffs, carried, of = chk[key]
        say(f"      check against the {stage} workbook: {carried} of {of} contests carried, {len(diffs)} differ")
        for d in diffs:
            say(f"        {d}")
    for stage, (ok, n, most, _none) in (("primary", precon), ("runoff", rrecon)):
        say(f"      check: {stage} statewide contests against the party's ballots cast: {ok} of {n} county returns equal"
            + (f", the rest differ by at most {most:,}" if ok < n else ""))
    for p in problems:
        say(f"      problem: {p}")
    for c in checks:
        say(f"      check: {c}")
    return {"races": len(races), "general": len(gen_rows), "fields": dict(fields), "problems": problems, "checks": checks}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("db")
    ap.add_argument("--keep", help="folder for the kept-cells JSON (default ballot_cache/al)")
    a = ap.parse_args()
    load(a.db, keep=a.keep)
