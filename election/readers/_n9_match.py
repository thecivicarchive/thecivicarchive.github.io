"""election/readers/_n9_match.py - what the four phase-3 readers written by N9 share (clarity, tally, in_enr, resultssw):
the crosswalk from a feed's contest titles to the ballot databases' race ids, candidate names to the names as filed,
county names to county FIPS codes, and the replay check against certified totals.

The crosswalk (election/crosswalk/<code>.json, one per state) is built from the ballot databases, read only:
  races      every race for Congress (ballot_2026.sqlite) and every statewide and legislative race
             (ballot_local_2026.sqlite) on the state's 2026 list, with its kind, district and the names as filed
  counties   the state's county names (folded) -> five-digit county FIPS (sl_places, from the Census Bureau's file)
  aliases    hand-kept: a feed title (folded) -> race id, for a title the rules below cannot read; never guessed
  elections  past elections a rehearsal replays, by the feed's own id: {kind: primary|general, date, label}
  checked    what the last check against a posted Nov 3 contest list found (matched, listed, missing)

A contest is tied to a race by its title (and the district cell where the feed has one): the office words decide the
kind (U.S. Senate, U.S. House, a statewide office, state senate or house), the number the district, and words such as
"unexpired" or "special" choose between a regular and a special race for the same seat. A title that fits no race, or
more than one, is listed with the reason and never shown. In a primary the party in the title (or the party column)
makes the race id "<race id>~<PARTY>" (2026-IA-H01~REP), so that each party's primary is a contest of its own; a
rehearsal of a past general election ties its contests to the 2026 race for the same seat, and the candidates' names
then match no name on the 2026 list (kept as printed, with no filed name).

    python -m election.readers._n9_match --crosswalk [codes]     (re)build the crosswalk files (downloads nothing)
    python -m election.readers._n9_match --show <code>           one line per race in a state's crosswalk
"""

import argparse
import datetime as dt
import json
import os
import re
import sqlite3
import sys

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from ballot.common import fold, name_parts  # noqa: E402
from election import store  # noqa: E402

BALLOT_US = os.path.join(HERE, "ballot_2026.sqlite")
BALLOT_LOCAL = os.path.join(HERE, "ballot_local_2026.sqlite")
CROSSWALK_DIR = os.path.join(HERE, "election", "crosswalk")
FIXTURES = os.path.join(HERE, "election", "fixtures")

# N9's states (and Michigan, whose Oakland County Clarity page is read as a labelled partial source)
STATES = {"IA": "19", "CO": "08", "SC": "45", "WV": "54", "MI": "26", "ND": "38", "AR": "05", "IN": "18", "NE": "31",
          "NM": "35", "MT": "30", "SD": "46", "OR": "41"}
FAMILY = {"IA": "clarity", "CO": "clarity", "SC": "clarity", "WV": "clarity", "MI": "clarity", "ND": "tally", "AR": "tally",
          "IN": "in_enr", "NE": "resultssw", "NM": "resultssw", "MT": "resultssw", "SD": "resultssw", "OR": "resultssw"}

PARTY_WORDS = {
    "rep": "REP", "republican": "REP", "r": "REP", "gop": "REP",
    "dem": "DEM", "democratic": "DEM", "democrat": "DEM", "democratic npl": "DEM", "dem npl": "DEM", "d": "DEM",
    "lib": "LIB", "libertarian": "LIB", "l": "LIB", "grn": "GRN", "green": "GRN", "con": "CON", "constitution": "CON",
    "lmn": "LMN", "legal marijuana now": "LMN", "uni": "UNI", "unity": "UNI", "np": "NP", "nonpartisan": "NP",
    "afp": "AFP", "america first": "AFP", "fwd": "FWD", "forward": "FWD",
}
WRITE_IN = re.compile(r"^\s*(write[\s-]*ins?|scattering|qualified write[\s-]*ins?)\b", re.I)
SPECIAL = re.compile(r"\b(unexpired|special|vacancy|remainder|short term)\b", re.I)

# statewide offices: (pattern on the folded title, the ballot's office_kind). Order matters: the first that fits wins.
STATEWIDE = [
    (r"\blieutenant governor\b|\blt governor\b", "lieutenant_governor", r"^(for )?governor\b"),
    (r"^(for )?governor\b|\bgovernor\b(?! s)", "governor", None),
    (r"\battorney general\b", "attorney_general", None),
    (r"\bsecretary of state\b", "secretary_of_state", None),
    (r"\bschool and public lands\b", "school_and_public_lands_commissioner", None),
    (r"\bpublic lands\b|\bstate lands\b|\bland commissioner\b|\bcommissioner of public lands\b", "land_commissioner", None),
    (r"\bsecretary of agriculture\b", "secretary_of_agriculture", None),
    (r"\bagricultur", "agriculture_commissioner", None),
    (r"\bcomptroller\b", "comptroller", None),
    (r"\bauditor\b", "state_auditor", None),
    (r"\btreasurer\b", "state_treasurer", None),
    (r"\bsuperintendent\b", "superintendent_of_public_instruction", None),
    (r"\bpublic service commission", "public_service_commissioner", None),
    (r"\bpublic utilities commission", "public_utilities_commissioner", None),
    (r"\btax commissioner\b", "tax_commissioner", None),
    (r"\bpublic education commission", "public_education_commission", None),
    (r"\bboard of education\b", "state_board_of_education", None),
    (r"\bregents?\b", "university_board", None),
    (r"\binsurance commissioner\b", "insurance_commissioner", None),
    (r"\blabor commissioner\b|\bcommissioner of labor\b", "labor_commissioner", None),
]
LOCAL_WORDS = re.compile(r"\b(county|city|town|township|village|school|ward|mayor|council|commissioner district|sheriff|clerk|"
                         r"coroner|recorder|assessor|surveyor|park|soil|water|hospital|library|fire|precinct committee|delegate|"
                         r"magistrate|alderman|board member|trustee|constable|prosecut|district attorney|probate|judge|justice|"
                         r"court|retain|retention)\b")
ORD = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9,
       "tenth": 10, "eleventh": 11, "twelfth": 12, "thirteenth": 13, "fourteenth": 14, "fifteenth": 15, "sixteenth": 16,
       "seventeenth": 17}


# ============================================================================================== small helpers

def norm(t):
    """A title folded for matching: lower case, accents off, punctuation as spaces, '1st' kept as '1st'."""
    t = (t or "").replace("&", " and ").replace("Lt.", "Lieutenant").replace("U.S.", "US").replace("U. S.", "US")
    return " ".join(re.sub(r"[^a-z0-9]+", " ", t.lower()).split())


def norm_district(d):
    """'District 01' -> '1', '1st' -> '1', '(1)' -> '1', '26A' -> '26A', '' -> None."""
    s = str(d or "").strip()
    if not s:
        return None
    m = re.search(r"(\d+)\s*([A-Za-z])?\b", s)
    if not m:
        w = norm(s)
        for k, v in ORD.items():
            if re.search(rf"\b{k}\b", w):
                return str(v)
        return None
    return str(int(m.group(1))) + (m.group(2).upper() if m.group(2) and m.group(2).lower() not in ("s", "n", "r", "t") else "")


def district_in(title):
    """The district number a title names: 'District 1', 'District 01', '1st District', '(1) District', 'Dist. 4',
    'Congressional District 2', 'First District'."""
    t = title or ""
    for pat in (r"\bdist(?:rict|\.)?\s*(?:no\.?\s*)?#?\s*(\d+[A-Za-z]?)\b", r"\b(\d+[A-Za-z]?)(?:st|nd|rd|th)?\s+(?:[A-Za-z]+\s+)?dist",
                r"\((\d+)\)\s*dist", r"\bcd\s*(\d+)\b", r"\b(\d+)(?:st|nd|rd|th)?\s+(?:congressional|senatorial|legislative)\b", r"\bseat\s*(\d+[A-Za-z]?)\b",
                r"\b(?:representative|senator|delegate|commissioner)\s+(\d+[A-Za-z]?)\s*$"):
        m = re.search(pat, t, re.I)
        if m:
            return norm_district(m.group(1))
    w = norm(t)
    for k, v in ORD.items():
        if re.search(rf"\b{k} (congressional )?district\b", w):
            return str(v)
    return None


def split_party(title):
    """('United States Senator', 'REP') from 'United States Senator - Rep.', 'Governor - REP', 'Representative in
    Congress Democratic-NPL', 'U.S. Senate (DEM)'; (title, None) when the title names no party at its end."""
    t = tidy(title)
    segs = re.split(r"\s+[-–]\s+", t)
    for i, seg in enumerate(segs[1:], 1):
        w = re.sub(r"\s+party$", "", norm(seg))
        if len(w) > 1 and PARTY_WORDS.get(w):
            return " - ".join(segs[:i] + segs[i + 1:]), PARTY_WORDS[w]
    for pat in (r"^(.*?)\s*(?:-|–|,)\s*([A-Za-z][A-Za-z .\-]{0,24}?)\.?\s*$", r"^(.*?)\s*\(\s*([A-Za-z][A-Za-z .\-]{0,24}?)\.?\s*\)\s*$"):
        m = re.match(pat, t)
        if m and len(norm(m.group(2))) > 1 and PARTY_WORDS.get(norm(m.group(2))):
            return m.group(1).strip(), PARTY_WORDS[norm(m.group(2))]
    for words, code in sorted(PARTY_WORDS.items(), key=lambda kv: -len(kv[0])):
        if len(words) < 3:
            continue
        m = re.match(r"^(.*\S)[\s\-]+" + r"[\s\-]+".join(re.escape(w) for w in words.split()) + r"\s*$", t, re.I)
        if m:
            return m.group(1).strip(), code
    return t, None


def party_code(p):
    """A party as printed ('REP', 'Republican', 'R') -> REP, DEM, LIB ...; another label in capitals (at most 8)."""
    k = norm(p)
    return PARTY_WORDS.get(k) or (re.sub(r"[^A-Z0-9]", "", (p or "").upper())[:8] or None)


def choice_key(name):
    return "write-in" if WRITE_IN.match(name or "") else store.slug(name)


def is_write_in(name):
    """A write-in line: the generic line ('Write-in', 'Scattering'), a named write-in candidate ('Justin Blackburn
    (Write-In)') or a category of write-ins ('Rejected write-ins', 'Unassigned write-ins')."""
    return bool(WRITE_IN.match(name or "") or re.search(r"\bwrite[\s-]*ins?\b", name or "", re.I))


def tidy(name):
    """A name as printed, with runs of spaces made one ('Alex  Balazs ' -> 'Alex Balazs')."""
    return " ".join(str(name or "").split())


def _people(name):
    """The people a ballot line names: a ticket 'Jim Pillen and Joe Kelly', 'REYNOLDS/GREGG' is two."""
    return [p.strip() for p in re.split(r"\s+and\s+|\s*/\s*|\s*&\s*", name or "") if p.strip()]


def _key(name):
    given, family = name_parts(name)
    return fold(family).replace(" ", ""), (given[0][:1] if given else "")


def filed_name(printed, filed):
    """The name as filed on the 2026 list that a printed name is, or None. Family name and first initial of the first
    person on the line must agree, and only one name on the list may fit."""
    if not printed or not filed or WRITE_IN.match(printed):
        return None
    # a note printed after the name ('- *Decertified before Primary*', '(Withdrawn)') is not part of it
    printed = re.sub(r"\s*(?:[-–]\s*)?(?:\*[^*]*\*|\((?:withdr|decert|deceas|remov|disqual|write)[^)]*\))\s*$", "", printed, flags=re.I).strip() or printed
    ppl = _people(printed)
    if not ppl:
        return None
    fam, ini = _key(ppl[0])
    if not fam:
        return None
    exact = [f for f in filed if fold(f) == fold(printed)]
    if len(exact) == 1:
        return exact[0]
    fits = []
    for f in filed:
        fp = _people(f)
        if not fp:
            continue
        ffam, fini = _key(fp[0])
        if ffam == fam and (not ini or not fini or ini == fini):
            fits.append(f)
    if len(fits) == 1:
        return fits[0]
    if not fits:
        # a nickname on one list and the full given name on the other ('Bill' and 'William'): the family name alone,
        # when only one name on the race's list has it
        fam_only = [f for f in filed if _people(f) and _key(_people(f)[0])[0] == fam]
        if len(fam_only) == 1:
            return fam_only[0]
    return None


# ============================================================================================== the crosswalk

def _ro(path):
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def _kind_of(level, office, office_kind, race_id):
    if level == "federal":
        return "S" if re.search(r"-S\d", race_id) else "H"
    if level == "statewide":
        return "statewide:" + office_kind
    if level == "legislature":
        return "SS" if office_kind == "state_senate" else "SH"
    return level


def build(code, say=print):
    """The crosswalk for one state, written to election/crosswalk/<code>.json. Hand-kept sections are kept."""
    code = code.upper()
    path = os.path.join(CROSSWALK_DIR, f"{code.lower()}.json")
    old = {}
    if os.path.exists(path):
        try:
            old = json.load(open(path, encoding="utf-8"))
        except ValueError:
            old = {}
    us, loc = _ro(BALLOT_US), _ro(BALLOT_LOCAL)
    races = []
    for rid, level, office, district, special in us.execute(
            "SELECT race_id, level, office, district, special FROM races WHERE state=? ORDER BY race_id", (code,)):
        names = [[n, p] for n, p in us.execute("SELECT name, party FROM candidates WHERE race_id=? AND election='general' ORDER BY "
                                                "COALESCE(ballot_order, 99), name", (rid,))]
        races.append({"id": rid, "level": "federal", "kind": _kind_of(level, office, None, rid), "office": office,
                      "district": norm_district(district) if district and district != "00" else None, "special": int(special or 0),
                      "seats": 1, "names": names})
    for rid, level, kind, office, district, seat, special in loc.execute(
            "SELECT race_id, level, office_kind, office, district, seat, special FROM sl_races WHERE state=? AND level IN "
            "('statewide','legislature') ORDER BY race_id", (code,)):
        names = [[n, p] for n, p in loc.execute("SELECT name, party FROM sl_candidates WHERE race_id=? AND election='general' ORDER BY "
                                                 "COALESCE(ballot_order, 99), name", (rid,))]
        races.append({"id": rid, "level": level, "kind": _kind_of(level, office, kind, rid), "office": office,
                      "district": norm_district(district), "seat": seat, "special": int(special or 0) or (1 if SPECIAL.search(seat or "") else 0),
                      "seats": 1, "names": names})
    fips = STATES.get(code)
    counties = {}
    if fips:
        for cid, name in loc.execute("SELECT id, name FROM sl_places WHERE kind='county' AND length(id)=5 AND substr(id,1,2)=?", (fips,)):
            counties[county_word(name)] = cid
    doc = {"v": 1, "state": code, "family": FAMILY.get(code), "built": dt.date.today().isoformat(),
           "from": ["ballot_2026.sqlite: races, candidates (general list)", "ballot_local_2026.sqlite: sl_races, sl_candidates "
                    "(statewide and legislature), sl_places (county names, from the Census Bureau's county file)"],
           "rule": ("A feed contest is tied to a race by its title (office words, district number, unexpired or special) and, in "
                    "a primary, its party; a contest that fits no race or more than one is listed, never shown. Names as "
                    "printed are tied to names as filed by family name and first initial, one fit only."),
           "counties": counties, "races": races,
           "aliases": old.get("aliases") or {}, "elections": old.get("elections") or {}, "checked": old.get("checked") or {},
           "notes": old.get("notes") or []}
    for k in ("tally_types", "pages", "csv_types", "categories", "partial"):
        if k in old:
            doc[k] = old[k]
    os.makedirs(CROSSWALK_DIR, exist_ok=True)
    tmp = path + ".part"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, path)
    say(f"{code}: {len(races)} races ({sum(r['level'] == 'federal' for r in races)} for Congress, "
        f"{sum(r['level'] == 'statewide' for r in races)} statewide, {sum(r['level'] == 'legislature' for r in races)} legislative), "
        f"{len(counties)} counties -> {os.path.relpath(path, HERE)}")
    return doc


def county_word(name):
    """'Lac qui Parle County' -> 'lac qui parle'; 'St. Clair' -> 'saint clair'; 'De Kalb' and 'DeKalb' -> 'dekalb'."""
    t = fold(re.sub(r"\b(County|Parish)\b", "", name or "", flags=re.I).replace("St.", "Saint").replace("Ste.", "Sainte"))
    t = re.sub(r"\bst\b", "saint", t)
    return t.replace(" ", "")


def load(code):
    path = os.path.join(CROSSWALK_DIR, f"{code.lower()}.json")
    return json.load(open(path, encoding="utf-8"))


def save_section(code, key, value):
    """Writes one hand-kept or check section into a state's crosswalk file (the rest unchanged)."""
    path = os.path.join(CROSSWALK_DIR, f"{code.lower()}.json")
    doc = json.load(open(path, encoding="utf-8"))
    doc[key] = value
    tmp = path + ".part"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


# ============================================================================================== matching

class Matcher:
    def __init__(self, code, cw=None):
        self.code = code.upper()
        self.cw = cw if isinstance(cw, dict) else load(self.code)
        self.races = {r["id"]: r for r in self.cw["races"]}
        self.by_kind = {}
        for r in self.cw["races"]:
            self.by_kind.setdefault(r["kind"], []).append(r)
        self.aliases = {norm(k): v for k, v in (self.cw.get("aliases") or {}).items()}
        self.counties = self.cw.get("counties") or {}
        self.house_seats = len(self.by_kind.get("H", []))

    def county(self, name):
        """A county name as a feed prints it -> its five-digit FIPS code, or None."""
        n = str(name or "").strip()
        if re.fullmatch(r"\d{5}", n) and n[:2] == STATES.get(self.code):
            return n
        return self.counties.get(county_word(n))

    def classify(self, title, district=None):
        """(kind, district, special) from a title; kind None when the title is not a statewide, congressional or
        legislative office; ('local', ...) when it reads as a local office."""
        w = norm(title)
        sp = bool(SPECIAL.search(title or ""))
        dist = norm_district(district) if district else None
        dist = dist or district_in(title)
        if re.search(r"\b(us|united states)\s+senat|\bsenator in congress\b|\bus senate\b", w):
            return "S", None, sp
        if (re.search(r"\b(representative in congress|(us|united states) (representative|house|congress)|congressional district|"
                      r"member of congress|us rep)\b", w) or (re.search(r"\bcongress\b", w) and not re.search(r"\bstate\b", w))) \
                and not re.search(r"\b(board|regents?|commission|commissioner|trustees?)\b", w):
            return "H", dist, sp
        if re.search(r"\bstate senat|\bsenate district\b|\bstate senator\b", w) or (re.search(r"\bsenator\b", w) and dist):
            return "SS", dist, sp
        if re.search(r"\b(state representative|state house|house of delegates|house of representatives|representative district|"
                     r"house district|legislative district)\b", w) or (re.search(r"\brepresentative\b", w) and dist):
            return "SH", dist, sp
        if re.search(r"\bmember of the legislature\b|\blegislature\b", w):
            return ("SS" if self.by_kind.get("SS") and not self.by_kind.get("SH") else "SH"), dist, sp
        if LOCAL_WORDS.search(w) and not re.search(r"\b(state|public service|public education|board of education|regent|"
                                                   r"school and public lands|superintendent of public)\b", w):
            return "local", dist, sp
        for pat, kind, unless in STATEWIDE:
            if re.search(pat, w) and not (unless and re.search(unless, w)):
                return "statewide:" + kind, dist, sp
        return None, dist, sp

    def resolve(self, title, district=None, names=(), party=None):
        """(race id, why) for one contest. party: the primary's party (makes the id <race>~<PARTY>), or None."""
        t, p = split_party(title)
        party = party or p
        alias = self.aliases.get(norm(title)) or self.aliases.get(norm(t))
        if alias:
            return (alias + (f"~{party}" if party else ""), "") if alias in self.races else (None, f"the hand-kept alias names {alias}, not on the list")
        kind, dist, sp = self.classify(t, district)
        if kind is None:
            return None, "not an office this reader ties to a race (statewide, Congress or the Legislature)"
        if kind == "local":
            return None, "a local, judicial or party contest: this feed is read for statewide, congressional and legislative races"
        cands = list(self.by_kind.get(kind, []))
        if not cands:
            return None, f"no 2026 race of this kind ({kind}) on the state's list"
        if kind in ("H", "SS", "SH") or len(cands) > 1:
            if dist is not None:
                cands = [r for r in cands if r.get("district") == dist or (r.get("district") or "").lstrip("0") == dist]
            elif kind == "H" and self.house_seats == 1:
                pass
            elif kind in ("H", "SS", "SH"):
                return None, "the title names no district"
        if len(cands) > 1:
            spec = [r for r in cands if r.get("special")]
            reg = [r for r in cands if not r.get("special")]
            cands = spec if sp and spec else reg if not sp and reg else cands
        if len(cands) > 1 and names:
            hit = [r for r in cands if any(filed_name(n, [x[0] for x in r["names"]]) for n in names)]
            if len(hit) == 1:
                cands = hit
        if len(cands) != 1:
            return None, (f"no 2026 race for this seat ({kind}{' ' + dist if dist else ''})" if not cands else
                          "more than one race fits: " + ", ".join(r["id"] for r in cands))
        return cands[0]["id"] + (f"~{party}" if party else ""), ""

    def race(self, rid):
        return self.races.get(rid.split("~")[0])

    def choice(self, rid, printed, party=None, order=None):
        """A choice line for the store: key, name as printed, party, the name as filed (or None), write-in, order."""
        r = self.race(rid) or {}
        name = tidy(printed)
        filed = filed_name(name, [x[0] for x in r.get("names", [])])
        return {"key": choice_key(name), "name": name, "party": party or None, "ballot_name": filed, "write_in": is_write_in(name),
                "order": order}


def contest_base(m, rid, key, office):
    """The contest fields every reader fills the same way."""
    r = m.race(rid) or {}
    return {"race_id": rid, "key": key, "office": office, "level": r.get("level") or "federal", "district": r.get("district"),
            "seats": r.get("seats") or 1, "rule": "plurality", "rcv": False}


def unit_county(code, fips, name=None):
    return {"id": fips, "kind": "county", "name": name, "parent": code, "map_id": fips}


UNIT_ALL = {"id": "all", "kind": "race", "name": "the whole contest", "parent": None, "map_id": None}


# ============================================================================================== the replay check

def certified_primary(code, write_ins=None):
    """{"<race>~<PARTY>": {folded name: votes}} and {race: source id} from the ballot databases' official primary figures
    (canvassed or certified; the ballot pages store primary votes only when official). write_ins, a set, is given each
    "<race>~<PARTY>|<name>" the list marks as a declared write-in."""
    out, srcs = {}, {}
    party_of = lambda e: e.split("-", 1)[1] if "-" in e else e  # noqa: E731
    for path, q in ((BALLOT_US, "SELECT race_id, election, name, votes, source_id, 0 FROM candidates WHERE race_id LIKE ? AND election LIKE "
                                "'primary-%' AND votes IS NOT NULL"),
                    (BALLOT_LOCAL, "SELECT c.race_id, c.election, c.name, c.votes, c.source_id, c.write_in FROM sl_candidates c JOIN sl_races r "
                                   "USING (race_id) WHERE c.race_id LIKE ? AND c.election LIKE 'primary-%' AND c.votes IS NOT NULL "
                                   "AND r.level IN ('statewide','legislature')")):
        con = _ro(path)
        for rid, el, name, votes, sid, wi in con.execute(q, (f"2026-{code}-%",)):
            k = f"{rid}~{party_of(el)}"
            out.setdefault(k, {})[name] = int(votes)
            srcs[k] = sid
            if wi and write_ins is not None:
                write_ins.add(f"{k}|{name}")
    return out, srcs


def compare_primary(code, reading, say=print, levels=("federal", "statewide", "legislature")):
    """Each primary contest of the reading (its 'all' unit) against the certified figures. Returns (equal, differ,
    not_in_reading). A race is equal when every certified candidate's votes are found under the same name. Two
    differences are explained, not the reader's: a declared write-in the feed does not list by name (it counts write-ins
    as one line, or not at all), and a certified figure from a recount (the feed holds the first count). A race whose
    every difference is explained counts as equal, and each explanation is said."""
    write_ins = set()
    cert, srcs = certified_primary(code, write_ins)
    got = {}
    for c in reading.get("contests", []):
        if "~" not in c["race_id"] or c.get("level") not in levels:
            continue
        names = {ch["key"]: ch["name"] for ch in c["choices"]}
        tot = {}
        for r in c["rows"]:
            if r["unit"] == "all" and r.get("type", "total") == "total":
                tot[names.get(r["choice"], r["choice"])] = int(r["votes"])
        got[c["race_id"]] = tot
    equal, differ, missing = [], [], []
    for k, want in sorted(cert.items()):
        base = k.split("~")[0]
        lvl = "federal" if re.search(r"-(H\d+|S\d)$", base) else None
        if k not in got:
            if lvl or any(c["race_id"].split("~")[0] == base for c in reading.get("contests", [])):
                missing.append(k)
            continue
        have = got[k]
        bad, why = [], []
        recount = "recount" in str(srcs.get(k) or "").lower()
        for name, v in want.items():
            hit = filed_name(name, list(have)) or next((h for h in have if fold(h) == fold(name)), None)
            if hit is None:
                hit = next((h for h in have if filed_name(h, [name])), None)
            if hit is None or have[hit] != v:
                line = f"{name}: certified {v:,}, feed {have.get(hit, 'not found') if hit else 'not found'}"
                if hit is None and f"{k}|{name}" in write_ins:
                    why.append(line + " (a declared write-in the feed does not list by name)")
                elif hit is not None and recount and abs(have[hit] - v) <= max(25, v // 100):      # a recount moves a handful of votes, not a reader's mistake
                    why.append(line + " (the certified figure is the recount's; the feed holds the first count)")
                else:
                    bad.append(line)
        if why:
            say(f"  EXPLAINED {k} ({srcs.get(k)}): " + "; ".join(why))
        (differ if bad else equal).append((k, srcs.get(k), bad))
    return equal, differ, missing


def check_posted(code, reading, election, say=print, levels=("federal", "statewide")):
    """A posted Nov 3 contest list (zero counts) against the 2026 list: every race for Congress and every statewide race
    must be tied to exactly one contest. Writes the crosswalk's "checked" section; returns the races not found."""
    m = Matcher(code)
    tied = {c["race_id"]: c["office"] for c in reading.get("contests", [])}
    want = [r["id"] for r in m.cw["races"] if r["level"] in levels]
    missing = [r for r in want if r not in tied]
    names_off = []
    for c in reading.get("contests", []):
        r = m.race(c["race_id"]) or {}
        filed = [x[0] for x in r.get("names", [])]
        for ch in c["choices"]:
            if not ch["write_in"] and filed and not ch.get("ballot_name"):
                names_off.append(f"{c['race_id']}: {ch['name']}")
    save_section(code, "checked", {
        "election": str(election), "on": dt.date.today().isoformat(),
        "tied": dict(sorted(tied.items())),
        "listed": [{"office": u.get("office"), "why": u.get("why")} for u in reading.get("unmatched", [])],
        "missing": missing, "names_not_tied": names_off,
        "note": "Races for Congress and statewide races on the 2026 list that the posted Nov 3 contest list does not carry are "
                "'missing'; printed names with no name as filed are 'names_not_tied' (kept as printed)."})
    say(f"{code} Nov 3 ({election}): {len(tied)} contests tied, {len(reading.get('unmatched', []))} listed; "
        f"{len(want) - len(missing)} of {len(want)} federal and statewide races found" + (f"; missing: {', '.join(missing)}" if missing else "")
        + (f"; names not tied: {'; '.join(names_off[:6])}" if names_off else ""))
    return missing


# ============================================================================================== command line

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--crosswalk", nargs="*", metavar="CODE")
    ap.add_argument("--show", metavar="CODE")
    a = ap.parse_args(argv)
    if a.crosswalk is not None:
        for code in (a.crosswalk or sorted(STATES)):
            build(code)
    if a.show:
        cw = load(a.show)
        for r in cw["races"]:
            print(r["id"], r["kind"], r.get("district"), r["office"], len(r["names"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
