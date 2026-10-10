"""election/readers/_n10_common.py - what the readers written by N10 share (enhanced_voting, pcc_ems, dc_boe, de_json,
hi_text): tying a feed's contests to the ballot databases' race ids, its candidate lines to the names as filed, and
building the reading election.store checks.

The crosswalk (election/crosswalk/<code>.json) is built once from the two ballot databases, read only
(`python -m election.readers._n10_common crosswalk GA VA ...`), so nothing on the night opens them. It holds every
race this reader can tie a contest to (Congress, the statewide offices, the Legislature), each with its candidates as
filed for the general election and the 2026 primaries, the state's counties (name -> five-digit FIPS) and the
contests checked by hand. A contest is tied to a race only when exactly one race fits; anything else is listed with
the reason and never shown. Nothing is guessed.

No request is made here.
"""

import datetime as dt
import json
import os
import re
import sqlite3
import sys
import unicodedata

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

CROSSWALK_DIR = os.path.join(HERE, "election", "crosswalk")
BALLOT_DB = os.path.join(HERE, "ballot_2026.sqlite")
LOCAL_DB = os.path.join(HERE, "ballot_local_2026.sqlite")
ELECTION_DATE = "2026-11-03"

# ---------------------------------------------------------------------------------------------- words and names

SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v", "2nd", "3rd"}
PARTY_CODES = {
    "dem": "DEM", "democrat": "DEM", "democratic": "DEM", "d": "DEM", "democratic party": "DEM",
    "rep": "REP", "republican": "REP", "r": "REP", "gop": "REP", "republican party": "REP",
    "lib": "LIB", "libertarian": "LIB", "l": "LIB", "libertarian party": "LIB",
    "grn": "GRE", "green": "GRE", "g": "GRE", "green party": "GRE",
    "con": "CON", "constitution": "CON",
    "np": "NP", "n": "NP", "nonpartisan": "NP",
}


def text_of(field):
    """An Enhanced Voting text field (a list of {languageId, text}) in English, or a plain string, squashed."""
    if isinstance(field, list):
        pick = next((t for t in field if isinstance(t, dict) and t.get("languageId") in ("en", None)), field[0] if field else {})
        field = pick.get("text") if isinstance(pick, dict) else pick
    return squash(field)


def squash(s):
    return re.sub(r"\s+", " ", str(s or "")).strip()


def fold(s):
    """Lower case, accents set aside, anything but letters, digits and spaces made a space."""
    s = "".join(ch for ch in unicodedata.normalize("NFKD", str(s or "")) if not unicodedata.combining(ch)).lower()
    s = s.replace("’", "'").replace("'", "")
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def clean_printed(name):
    """A candidate line as printed, without the marks feeds add to it: a trailing incumbent mark "(I)" or "*", a
    trailing party in brackets "(Rep)", a leading party in brackets "(D) ". The name itself is not changed."""
    n = squash(name)
    n = re.sub(r"^\((?:[A-Z]{1,4})\)\s+", "", n)
    for _ in range(3):
        n2 = re.sub(r"\s*\((?:I|Inc|Incumbent|Dem|Rep|Lib|Grn|Ind|Con|NP|Npa|[A-Z]{1,4})\)\s*$", "", n, flags=re.I)
        n2 = re.sub(r"\s*\*+\s*$", "", n2)
        if n2 == n:
            break
        n = n2
    return n.strip()


def person(name):
    """(given words, family name) of the first person on a line ("A and B", "A / B" are tickets), with "LAST, First"
    turned round and suffixes set aside."""
    n = clean_printed(name)
    n = re.split(r"\s+/\s+|\s+and\s+|\s*&\s*|\n", n, maxsplit=1, flags=re.I)[0]
    n = re.sub(r"\"[^\"]*\"|“[^”]*”|\([^)]*\)", " ", n)          # nicknames in quotes or brackets
    if "," in n:
        head, tail = n.split(",", 1)
        if fold(tail) and fold(tail).split()[0] not in SUFFIXES:
            n = tail + " " + head
        else:
            n = head
    words = [w for w in fold(n).split() if w not in SUFFIXES]
    if not words:
        return [], ""
    return words[:-1], words[-1]


def nicknames(name):
    found = re.findall(r"\"([^\"]+)\"|“([^”]+)”|\(([^)]+)\)", clean_printed(name))
    return {fold(g) for tup in found for g in tup if g}


def same_person(printed, filed):
    """True when a line as printed is the same person as a name as filed: the family name, and a given name that fits
    (the same first word, the same first letter, or the nickname)."""
    g1, f1 = person(printed)
    g2, f2 = person(filed)
    if not f1 or not f2:
        return False
    fam1 = fold(re.sub(r"[-']", " ", f1)).split()
    fam2 = fold(re.sub(r"[-']", " ", f2)).split()
    if f1 != f2 and not (set(fam1) & set(fam2)):
        # a double family name written two ways ("Copeland Hanzas", "Gluesenkamp Perez")
        all1 = set(g1) | {f1}
        if f2 not in all1:
            return False
    if not g1 or not g2:
        return True
    if g1[0] == g2[0] or g1[0][0] == g2[0][0]:
        return True
    nick = nicknames(printed) | nicknames(filed)
    return bool(nick & ({g1[0], g2[0]} | set(g1) | set(g2)))


def match_line(printed, candidates):
    """The one name as filed (from candidates, [[name, party, write_in], ...]) that is the same person as the printed
    line, or None when none or more than one fits."""
    fits = [c[0] for c in candidates if same_person(printed, c[0])]
    if len(fits) == 1:
        return fits[0]
    if len(fits) > 1:
        exact = [f for f in fits if fold(f) == fold(clean_printed(printed))]
        return exact[0] if len(exact) == 1 else None
    return None


def read_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def read_bytes(path):
    with open(path, "rb") as fh:
        return fh.read()


def slug(name):
    from election.store import slug as _slug
    return _slug(name)


def party_code(word):
    return PARTY_CODES.get(fold(word or ""))


# ---------------------------------------------------------------------------------------------- times

def local_to_utc(naive, std_hours, dst=True):
    """A local wall-clock time (a datetime with no zone) as UTC text, "2026-11-04T03:40:00Z": std_hours is the zone's
    offset in standard time (Eastern -5, Hawaii -10); daylight time from the second Sunday of March to the first Sunday
    of November at 2 a.m. where the zone keeps it."""
    y = naive.year
    off = std_hours
    if dst:
        mar = dt.date(y, 3, 1)
        start = mar + dt.timedelta(days=(6 - mar.weekday()) % 7 + 7)
        nov = dt.date(y, 11, 1)
        end = nov + dt.timedelta(days=(6 - nov.weekday()) % 7)
        if dt.datetime(start.year, start.month, start.day, 2) <= naive < dt.datetime(end.year, end.month, end.day, 2):
            off += 1
    return (naive - dt.timedelta(hours=off)).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------------------------- vote types

def vote_type(group):
    """A feed's own word for a way of voting -> the store's vote type."""
    g = fold(group)
    if "election day" in g or g in ("in person", "in-person", "polls", "machine", "machine votes"):
        return "election_day"
    if "early" in g or "advance" in g:
        return "early"
    if "mail" in g:
        return "mail"
    if "absentee" in g:
        return "absentee"
    if "provisional" in g:
        return "provisional"
    return "other"


# ---------------------------------------------------------------------------------------------- the crosswalk

_CW = {}


def crosswalk_path(code):
    return os.path.join(CROSSWALK_DIR, f"{code.lower()}.json")


def load_crosswalk(code):
    """The state's crosswalk, read again when its file changed; {} when it is not built."""
    p = crosswalk_path(code)
    if not os.path.exists(p):
        return {}
    m = os.path.getmtime(p)
    hit = _CW.get(code)
    if hit and hit[0] == m:
        return hit[1]
    with open(p, encoding="utf-8") as fh:
        doc = json.load(fh)
    _CW[code] = (m, doc)
    return doc


def _ro(path):
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def build_crosswalk(code, keep=None):
    """The crosswalk document for one state, from the ballot databases (read only). keep: the old document, whose
    hand-checked "contests" and "checked" records, and its "night_only" races, are kept."""
    code = code.upper()
    races = {}
    con = _ro(BALLOT_DB)
    for rid, office, district, special in con.execute("SELECT race_id, office, district, special FROM races WHERE state=? ORDER BY race_id", (code,)):
        kind = "senate" if office == "U.S. Senate" else "house"
        races[rid] = {"level": "federal", "kind": kind, "office": office, "district": district, "seat": None, "special": special or 0,
                      "cands": {}}
        for el, name, party, wi in con.execute("SELECT election, name, party, write_in FROM candidates WHERE race_id=? ORDER BY election, name", (rid,)):
            races[rid]["cands"].setdefault(el, []).append([name, party, 1 if wi else 0])
    con.close()
    lcon = _ro(LOCAL_DB)
    for rid, level, kind, office, district, seat, special, partisan in lcon.execute(
            "SELECT race_id, level, office_kind, office, district, seat, special, partisan FROM sl_races WHERE state=? AND level IN "
            "('statewide','legislature') ORDER BY race_id", (code,)):
        races[rid] = {"level": level, "kind": kind, "office": office, "district": district, "seat": seat, "special": special or 0,
                      "partisan": partisan, "cands": {}}
        for el, name, party, wi in lcon.execute("SELECT election, name, party, write_in FROM sl_candidates WHERE race_id=? ORDER BY election, name", (rid,)):
            races[rid]["cands"].setdefault(el, []).append([name, party, 1 if wi else 0])
    fips = {"GA": "13", "VA": "51", "WA": "53", "UT": "49", "ID": "16", "RI": "44", "CT": "09", "VT": "50", "DC": "11", "DE": "10",
            "HI": "15"}.get(code)
    counties = {}
    if fips:
        for pid, name in lcon.execute("SELECT id, name FROM sl_places WHERE kind='county' AND id LIKE ? AND length(id)=5", (fips + "%",)):
            counties[fold(re.sub(r"\s+(County|Parish|Borough)$", "", name))] = pid
            counties[fold(name)] = pid
    lcon.close()
    keep = keep or {}
    extra = {"night_only": keep["night_only"]} if keep.get("night_only") else {}      # races no ballot list carries (the District's), kept by hand
    return {**extra, "v": 1, "state": code, "built": dt.date.today().isoformat(),
            "source": "The ballot databases (Congress, and state and local), read only; the races and the names as filed.",
            "rule": ("A contest is tied to a race only when exactly one race of the same office and district (and seat) fits. "
                     "A candidate line is tied to a name as filed only when exactly one fits: the family name and a given name "
                     "that fits. Everything else is listed with the reason and never shown."),
            "races": races, "counties": counties,
            "contests": keep.get("contests", {}), "checked": keep.get("checked", [])}


def write_crosswalk(code):
    old = load_crosswalk(code)
    doc = build_crosswalk(code, keep=old)
    os.makedirs(CROSSWALK_DIR, exist_ok=True)
    with open(crosswalk_path(code), "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=1, sort_keys=True)
    _CW.pop(code.upper(), None)
    return doc


def county_fips(cw, name_or_code):
    """A county's five-digit FIPS from its name (or a three-digit or two-digit county number as some feeds give it)."""
    s = str(name_or_code or "").strip()
    if re.fullmatch(r"\d{5}", s):
        return s
    return (cw.get("counties") or {}).get(fold(re.sub(r"\s+(County|Parish)$", "", s, flags=re.I))) or (cw.get("counties") or {}).get(fold(s))


# ---------------------------------------------------------------------------------------------- tying a contest to a race

ORDINAL = r"(\d+)(?:st|nd|rd|th)?"
QUESTION = re.compile(r"\b(question|amendment|initiative|proposition|prop\b|referend|measure|levy|bond|charter|advisory|"
                      r"retain|retention|shall\b|yes\b.*\bno\b|recall|lid lift|ordinance|annexation)", re.I)
PARTY_POSTS = re.compile(r"committee(?:man|woman)?|ward committee|delegate to (?:the )?(?:state|national|county) convention|precinct (?:officer|"
                         r"captain)|party (?:chair|officer)", re.I)
STATEWIDE = [
    ("lieutenant_governor", re.compile(r"\blieutenant governor\b|\blt\.? governor\b", re.I), re.compile(r"\bgovernor and lieutenant governor\b", re.I)),
    ("governor", re.compile(r"\bgovernor\b", re.I), re.compile(r"board of governors", re.I)),
    ("secretary_of_state", re.compile(r"\bsecretary of (?:the )?state\b", re.I), None),
    ("attorney_general", re.compile(r"\battorney general\b", re.I), None),
    ("state_treasurer", re.compile(r"\btreasurer\b", re.I), re.compile(r"county|city|town", re.I)),
    ("state_auditor", re.compile(r"\bauditor\b", re.I), re.compile(r"county|city|town", re.I)),
    ("comptroller", re.compile(r"\bcomptroller\b", re.I), re.compile(r"county|city", re.I)),
    ("state_controller", re.compile(r"\bcontroller\b", re.I), re.compile(r"county|city", re.I)),
    ("agriculture_commissioner", re.compile(r"\bagriculture\b", re.I), None),
    ("insurance_commissioner", re.compile(r"\binsurance\b", re.I), None),
    ("labor_commissioner", re.compile(r"\blabor\b", re.I), None),
    ("superintendent_of_public_instruction", re.compile(r"superintendent of public instruction|school superintendent|superintendent of schools", re.I),
     re.compile(r"county", re.I)),
    ("public_service_commissioner", re.compile(r"public service commission", re.I), None),
    ("state_board_of_education", re.compile(r"(?:state )?(?:school board|board of education)", re.I), re.compile(r"county|city|town|local|non ?partisan", re.I)),
    ("oha_trustee", re.compile(r"office of hawaiian affairs|\bOHA\b", re.I), None),
]


def party_of_title(title, item_party=None, election_party=None):
    """(the title without its party words, the party code) for a primary contest; (title, None) otherwise."""
    t = squash(title)
    code = party_code(item_party) if item_party else None
    m = re.match(r"^(DEM|REP|LIB|GRN|CON|Democratic|Republican|Libertarian|Green)\s+(.*)$", t)
    if m:
        code = code or party_code(m.group(1))
        t = m.group(2)
    m = re.match(r"^(.*?)\s*[-–]\s*(Dem|Rep|Lib|Democratic|Republican|Libertarian|Green|Constitution|Nonpartisan)\s*$", t, re.I)
    if m:
        code = code or party_code(m.group(2))
        t = m.group(1)
    return t, code or (party_code(election_party) if election_party else None)


ROMAN = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6, "vii": 7, "viii": 8, "ix": 9, "x": 10}


def numbers(t):
    """The district numbers in a title, Roman numerals after "Dist" or "District" included ("Dist II" -> "2")."""
    out = re.findall(r"\b(\d+)(?:st|nd|rd|th)?\b", t)
    m = re.search(r"\bdist(?:rict)?\.?\s+([ivx]+)\b", t, re.I)
    if m and m.group(1).lower() in ROMAN:
        out.insert(0, str(ROMAN[m.group(1).lower()]))
    return out


def classify(code, title, cw, primary=None):
    """(race id, kind) or (None, why) for one contest's title. primary: None for a general election, else the party
    code of a party primary ("DEM") or "" for a primary with no party (a top-two primary)."""
    t = squash(title)
    t = re.split(r"/\s*Para la ", t)[0].strip()                    # Georgia prints the Spanish title after a slash
    low = t.lower()
    races = cw.get("races") or {}
    hand = (cw.get("contests") or {}).get(t)
    if hand is not None:
        return (hand["race"], hand.get("kind")) if hand.get("race") else (None, hand.get("why") or "set aside by hand")
    if PARTY_POSTS.search(t):
        return None, "a party office, not a public office"
    if re.search(r"\bpresident\b", low) and not re.search(r"council|board|commission", low):
        return None, "no race for President in 2026"
    if QUESTION.search(t) and not re.search(r"\b(senat|representative|governor|congress)", low):
        return None, "a ballot question, not a contest between people"

    def pick(kind, district=None, seat=None, level=None):
        fit = [rid for rid, r in races.items()
               if r["kind"] == kind and (level is None or r["level"] == level)
               and (district is None or (str(r.get("district") or "").lstrip("0") or "0") == (str(district).lstrip("0") or "0"))
               and (seat is None or fold(r.get("seat") or "") == fold(seat) or fold(r.get("seat") or "").endswith(" " + fold(seat)))]
        if len(fit) == 1:
            return fit[0], kind
        if not fit:
            return None, f"no 2026 race on the ballot lists for this office{' and district ' + str(district) if district else ''}"
        return None, f"{len(fit)} races on the ballot lists fit; none is guessed"

    # Congress
    if (re.search(r"\b(united states|u\.?\s?s\.?)\s+senat", low) or re.search(r"member, united states senate|senator in congress", low)) and "state senat" not in low:
        return pick("senate", level="federal")
    if (re.search(r"representative in congress|congressional district|representative to congress|"
                  r"\b(u\.?\s?s\.?|united states)\s+(house|representative)|^(member, )?house of representatives\s*\(", low)
            and not re.search(r"\bstate\b", low.replace("united states", ""))):
        houses = [rid for rid, r in races.items() if r["kind"] == "house" and r["level"] == "federal"]
        nums = numbers(t)
        if len(houses) == 1 and (not nums or nums[0].lstrip("0") in ("", "0", "1")):
            return houses[0], "house"
        if not nums:
            return None, "a House contest with no district number"
        return pick("house", district=nums[0], level="federal")
    if re.search(r"\bdelegate to the (u\.?s\.? )?house\b|delegate to congress", low):
        return pick("house", level="federal")
    # the Legislature
    m = re.search(r"\b(state senat\w*|senator in general assembly|senate district|state senator)\b", low)
    if m and "united states" not in low:
        nums = numbers(t)
        return pick("state_senate", district=nums[0] if nums else None, level="legislature") if nums else (None, "a State Senate contest with no district number")
    if re.search(r"\b(state house|state representative|house of delegates|representative in general assembly|state rep\b|"
                 r"house of representatives - district|legislative district .* representative|representative pos)", low):
        nums = numbers(t)
        if re.search(r"legislative district (\d+)", low):
            d = re.search(r"legislative district (\d+)", low).group(1)
        else:
            d = nums[0] if nums else None
        seat = None
        ms = re.search(r"\bpos(?:ition)?\.?\s*(\d+)", low) or re.search(r"\bseat ([a-z])\b", low)
        if ms:
            seat = ms.group(1)
        if d is None:
            return None, "a State House contest with no district number"
        got = pick("state_house", district=d, seat=seat, level="legislature")
        if got[0] is None and seat is None:
            return got
        return got
    # statewide offices
    if code == "HI" and re.search(r"\btrustee\b", low) and not re.search(r"council|county", low):
        t = "Office of Hawaiian Affairs " + t                    # Hawaii's file titles the OHA seats "At-Large Trustee" and the like
        low = t.lower()
    if re.search(r"\b(county|city|town|village|borough|municipal|school district|district court|probate|magistrate|"
                 r"precinct|ward|parish|port|fire|water|hospital|library|cemetery|park|sewer|transit|mayor|council|alderm\w*|"
                 r"selectm\w*|supervisor|clerk|sheriff|coroner|assessor|recorder|surveyor|district attorney|solicitor|pud|"
                 r"justice of the peace|high bailiff|assistant judge|state'?s attorney|registrar)\b", low) and \
            not re.search(r"office of hawaiian affairs", low):
        return None, "a county, city or district office; not read here yet"
    for kind, yes, no in STATEWIDE:
        if yes.search(t) and not (no and no.search(t)):
            nums = numbers(t)
            if kind in ("public_service_commissioner", "state_board_of_education"):
                if not nums:
                    return None, "a district office with no district number"
                d = nums[0]
                fit = [rid for rid, r in races.items() if r["kind"] == kind and fold(str(r.get("district") or "")).split()[-1:] == [d.lstrip("0")]]
                fit = fit or [rid for rid, r in races.items() if r["kind"] == kind and str(r.get("district") or "").lstrip("0") == d.lstrip("0")]
                return (fit[0], kind) if len(fit) == 1 else (None, "no 2026 race on the ballot lists for this office and district" if not fit
                                                             else f"{len(fit)} races fit; none is guessed")
            if kind == "oha_trustee":
                where = "AL" if re.search(r"at[- ]large", low) else ("MAUI" if "maui" in low else "OAHU" if "oahu" in low or "oʻahu" in low else
                                                                    "KAUAI" if "kauai" in low else "HAWAII" if "hawai" in low.replace("hawaiian", "") else None)
                fit = [rid for rid in races if races[rid]["kind"] == kind and where and rid.endswith("-" + where)]
                return (fit[0], kind) if len(fit) == 1 else (None, "no 2026 trustee race on the ballot lists for this seat")
            return pick(kind, level="statewide")
    if re.search(r"\b(judge|justice|court)\b", low):
        return None, "a judicial contest; not read here yet"
    return None, "not an office this reader ties to a race (Congress, statewide, Legislature)"


def decision(entry, level, kind, general=True, rcv=False):
    """The decision rule of a race, from the registry: the default, a statewide-office rule, ranked choice where the
    feed says so."""
    if rcv:
        return "ranked_choice"
    d = (entry or {}).get("decision") or {}
    rule = d.get("default") or "plurality"
    for r in d.get("rules") or []:
        applies = (r.get("applies") or "").lower()
        if r.get("rule") == "majority_or_legislature" and level == "statewide":
            rule = r["rule"]
        elif r.get("rule") == "majority_runoff" and level in ("federal", "statewide", "legislature"):
            rule = r["rule"]
        elif r.get("rule") == "ranked_choice" and "flag" not in applies and level in ("federal", "statewide"):
            rule = r["rule"]
    if rule == "top_two" and general:
        rule = "plurality"          # the general election between the two who advanced: most votes wins
    return rule


# ---------------------------------------------------------------------------------------------- building the reading

class Reading:
    """Builds election.store's reading contest by contest, and lists every contest not tied to a race."""

    def __init__(self, code, feed, entry, primary=None, cw=None):
        self.code, self.feed, self.entry = code.upper(), feed, entry or {}
        self.cw = cw if cw is not None else load_crosswalk(code)
        self.primary = primary                 # None: a general election; "DEM": a party primary; "": a primary with no party
        self.contests, self.unmatched, self.problems, self.notes = [], [], [], []
        self.seen = {}
        self.source_time = self.source_version = None
        self.test = False

    def election_code(self, party):
        if self.primary is None:
            return "general"
        return f"primary-{party}" if party else "primary"

    def tie(self, key, title, party=None):
        """(race id, race) for a contest, or (None, why); a contest of a party primary gets the id <race>/primary-<party>,
        which no page reads (rehearsals and the replay test only)."""
        rid, info = classify(self.code, title, self.cw, primary=party if self.primary is not None else None)
        if rid is None:
            return None, info
        race = self.cw["races"][rid]
        if self.primary is not None:
            rid = f"{rid}/{self.election_code(party)}"
        if rid in self.seen:
            return None, f"read as the same race as {self.seen[rid]!r}; neither is guessed"
        self.seen[rid] = title
        return rid, race

    def tie_rid(self, rid, title, party=None):
        """(race id, race) for a race found by the reader itself (Vermont's named districts), with the same checks."""
        race = (self.cw.get("races") or {}).get(rid)
        if race is None:
            return None, "no 2026 race on the ballot lists for this office and district"
        if self.primary is not None:
            rid = f"{rid}/{self.election_code(party)}"
        if rid in self.seen:
            return None, f"read as the same race as {self.seen[rid]!r}; neither is guessed"
        self.seen[rid] = title
        return rid, race

    def skip(self, key, title, why):
        self.unmatched.append({"key": str(key), "office": squash(title)[:160], "why": why})

    def add(self, rid, race, key, title, lines, unit_kind, units_in, units_all, seats=1, stated_total=None, rcv=False,
            by_unit=None, unit_meta=None, groups=None, party=None):
        """lines: [(printed name, party as printed, write-in, votes)] in ballot order; by_unit: {unit id: [votes in line
        order]}; unit_meta: {unit id: {kind, name, parent, map_id, in, all, total}}; groups: {vote type: [votes in line
        order]} for the whole contest."""
        cands = (race.get("cands") or {}).get(self.election_code(party), [])
        choices, keys = [], []
        wi_n = 0
        for i, (name, ptxt, wi, _v) in enumerate(lines):
            if wi:
                wi_n += 1
                k = "write-in" if wi_n == 1 else f"write-in-{wi_n}"
                filed = None
                shown = squash(name) if squash(name) and not re.fullmatch(r"(?i)(other\s*)?write[- ]?ins?", squash(name)) else "Write-in"
            else:
                shown = clean_printed(name)
                filed = match_line(name, [c for c in cands if not c[2]] or cands)
                k = slug(shown)
            while k in keys:
                k += "-x"
            keys.append(k)
            choices.append({"key": k, "name": shown, "party": ptxt or None, "ballot_name": filed, "write_in": bool(wi), "order": i + 1})
        rows = [{"unit": "all", "choice": k, "type": "total", "votes": int(v)} for k, (_n, _p, _w, v) in zip(keys, lines)]
        for vt, vals in (groups or {}).items():
            agg = {}
            for k, v in zip(keys, vals):
                agg[k] = agg.get(k, 0) + int(v)
            rows += [{"unit": "all", "choice": k, "type": vt, "votes": v} for k, v in agg.items()]
        units = [{"id": "all", "kind": "all", "name": None}]
        if units_in is not None and units_all is not None and int(units_in) > int(units_all):
            self.notes.append(f"{squash(title)}: the file says {units_in} of {units_all} reporting; that figure is left out, the votes are kept")
            units_in = units_all = None
        reporting = [{"unit": "all", "in": units_in, "all": units_all}]
        stated = [{"unit": "all", "total": int(stated_total)}] if stated_total is not None else []
        for u, vals in (by_unit or {}).items():
            meta = (unit_meta or {}).get(u, {})
            units.append({"id": u, "kind": meta.get("kind") or unit_kind, "name": meta.get("name"), "parent": meta.get("parent"),
                          "map_id": meta.get("map_id")})
            rows += [{"unit": u, "choice": k, "type": "total", "votes": int(v)} for k, v in zip(keys, vals)]
            if meta.get("in") is not None and meta.get("all") is not None and int(meta["in"]) > int(meta["all"]):
                self.notes.append(f"{squash(title)}: {meta.get('name') or u} says {meta['in']} of {meta['all']} reporting; left out")
            elif meta.get("in") is not None or meta.get("all") is not None:
                reporting.append({"unit": u, "in": meta.get("in"), "all": meta.get("all")})
            if meta.get("total") is not None:
                stated.append({"unit": u, "total": int(meta["total"])})
        self.contests.append({"race_id": rid, "key": str(key), "office": squash(title), "level": race["level"],
                              "district": race.get("district"), "seats": int(seats or 1),
                              "rule": decision(self.entry, race["level"], race["kind"], general=self.primary is None, rcv=rcv),
                              "rcv": bool(rcv), "unit_kind": unit_kind, "units_all": units_all,
                              "choices": choices, "units": units, "rows": rows, "reporting": reporting, "stated": stated,
                              "controls": []})

    def done(self):
        out = {"state": self.code, "feed": self.feed, "source_time": self.source_time, "source_version": self.source_version,
               "contests": self.contests, "unmatched": self.unmatched, "problems": self.problems}
        if self.test:
            out["test"] = True
        if self.notes:
            out["notes"] = self.notes
        return out


# ---------------------------------------------------------------------------------------------- the replay test

def compare_primary(code, reading, say=print, need=1):
    """Every contest of a 2026 primary read here against the certified primary votes the ballot loaders stored (only
    official figures are stored there). Returns (contests compared, candidates compared, differences)."""
    cw = load_crosswalk(code)
    diffs, nc, nk = [], 0, 0
    for c in reading["contests"]:
        rid, _, el = c["race_id"].partition("/")
        race = (cw.get("races") or {}).get(rid)
        if not race or not el:
            continue
        stored = None
        db = BALLOT_DB if race["level"] == "federal" else LOCAL_DB
        tab = "candidates" if race["level"] == "federal" else "sl_candidates"
        con = _ro(db)
        stored = con.execute(f"SELECT name, votes FROM {tab} WHERE race_id=? AND election=? AND votes IS NOT NULL AND NOT write_in",
                             (rid, el)).fetchall()
        con.close()
        if not stored:
            continue
        got = {ch["key"]: ch for ch in c["choices"]}
        tot = {r["choice"]: r["votes"] for r in c["rows"] if r["unit"] == "all" and r["type"] == "total"}
        nc += 1
        for name, votes in stored:
            hit = [k for k, ch in got.items() if not ch["write_in"] and (ch.get("ballot_name") == name or same_person(ch["name"], name))]
            nk += 1
            if len(hit) != 1:
                diffs.append(f"{c['race_id']}: {name} not found once in the feed ({len(hit)})")
            elif tot.get(hit[0]) != votes:
                diffs.append(f"{c['race_id']}: {name} {tot.get(hit[0])} in the feed, {votes} certified")
    return nc, nk, diffs


def store_roundtrip(reading):
    """The reading through election.store in memory: (status, {check: (passed, detail)})."""
    from election import store
    con = store.connect(":memory:")
    sid, _ = store.begin_snapshot(con, reading["state"], reading["feed"], store.sha256_bytes(json.dumps(reading, sort_keys=True).encode()))
    st, checks = store.record(con, sid, reading)
    page = store.page_json(con, reading["state"], compact=False)
    con.close()
    return st, {n: (p, d) for n, p, d in checks}, page


# ---------------------------------------------------------------------------------------------- command line

MINE = ("GA", "VA", "WA", "UT", "ID", "RI", "CT", "VT", "DC", "DE", "HI")


def check_replays(codes=MINE, write=True, say=print):
    """Every past or posted election kept for a rehearsal (election_cache/replay/sources/<code>-<id>/) read again with
    its reader: tied contests, lines tied to names as filed, the certified 2026 primary figures compared, the store's
    checks; each result recorded under "checked" in the state's crosswalk, with every contest not tied and why (in full
    for the Nov 3 election, by reason for past ones). Returns the number of failures. Makes no request."""
    import collections
    import glob
    import importlib
    from election import registry
    from election import replay as RP
    bad = 0
    for code in codes:
        e = registry.load(code)
        if not e:
            continue
        mod = importlib.import_module(f"election.readers.{e['family']}")
        nov3 = None
        try:
            nov3 = mod.election_id(e)
        except Exception:  # noqa: BLE001
            pass
        recs = []
        for folder in sorted(glob.glob(os.path.join(RP.REPLAY_SOURCES, f"{code.lower()}-*"))):
            past = os.path.basename(folder)[len(code) + 1:]
            files = sorted(RP.load_final(folder).items())
            ent = dict(e, election=dict(e.get("election") or {}, nov3_id=past))
            rd = mod.read(files, ent)
            st, checks, _page = store_roundtrip(rd)
            nc, nk, diffs = compare_primary(code, rd)
            lines = [ch for c in rd["contests"] for ch in c["choices"] if not ch["write_in"]]
            by = collections.Counter(c["level"] for c in rd["contests"])
            is_nov3 = past == nov3
            rec = {"election": past, "read": dt.date.today().isoformat(), "nov3": is_nov3, "store": st,
                   "problems": rd["problems"][:10], "notes": (rd.get("notes") or [])[:10],
                   "contests_tied": len(rd["contests"]), "by_level": dict(by),
                   "lines_tied": f"{sum(1 for ch in lines if ch['ballot_name'])} of {len(lines)}",
                   "certified_primary": {"contests": nc, "candidates": nk, "differences": diffs[:20]}}
            if is_nov3:
                rec["unmatched"] = [[u["office"], u["why"]] for u in rd["unmatched"]]
                rec["lines_not_tied"] = [[c["race_id"], ch["name"]] for c in rd["contests"] for ch in c["choices"]
                                         if not ch["write_in"] and not ch["ballot_name"]]
            else:
                rec["unmatched_by_reason"] = dict(collections.Counter(u["why"] for u in rd["unmatched"]))
            ok = st == "ok" and not rd["problems"] and not diffs
            bad += 0 if ok else 1
            say(f"  {'ok  ' if ok else 'FAIL'} {code} {past}: {len(rd['contests'])} contests tied ({', '.join(f'{k} {v}' for k, v in sorted(by.items()))}); "
                f"lines tied {rec['lines_tied']}; certified primary: {nc} contests, {nk} candidates, {len(diffs)} differences; store {st}")
            recs.append(rec)
        if write and recs:
            doc = load_crosswalk(code) or build_crosswalk(code)
            doc["checked"] = recs
            with open(crosswalk_path(code), "w", encoding="utf-8") as fh:
                json.dump(doc, fh, ensure_ascii=False, indent=1, sort_keys=True)
            _CW.pop(code, None)
    return bad


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["check-replays"]:
        return 1 if check_replays(tuple(c.upper() for c in argv[1:]) or MINE) else 0
    if argv[:1] == ["crosswalk"]:
        for code in argv[1:] or ["GA", "VA", "WA", "UT", "ID", "RI", "CT", "VT", "DC", "DE", "HI"]:
            doc = write_crosswalk(code)
            n = len(doc["races"])
            by = {}
            for r in doc["races"].values():
                by[r["level"]] = by.get(r["level"], 0) + 1
            print(f"  {code}: {n} races ({', '.join(f'{k} {v}' for k, v in sorted(by.items()))}), {len(set(doc['counties'].values()))} counties")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
