"""election/feeds/keywords.py - what each race is called in a headline, and which names collide.

    python -m election.feeds.keywords build    write a keyword set for every race in scope, and the collision list,
                                               into night_feed_2026.sqlite (tables race_keywords, name_collisions)
    python -m election.feeds.keywords check    the checks (every race in scope has a set; every candidate on the
                                               November list is in its race's set; every collision has a rule; the
                                               self-test of the matching rules); exit 1 on failure
    python -m election.feeds.keywords collisions [STATE]   the collision list, one line a name, with its rule
    python -m election.feeds.keywords show RACE_ID         one race's set

Scope (ARCHITECTURE.md 5.3, N7): every Minnesota race (state and local, ballot_local_2026.sqlite) and every federal
(ballot_2026.sqlite) and statewide race (ballot_local_2026.sqlite, level statewide) in every state. Both ballot
databases are opened read only. Candidates are those on the November 3 list (election "general"; Louisiana's House
"open-primary"). A race whose list is not loaded yet gets a set without names, and says so.

A keyword set holds, all folded the same way as `norm()` (lower case, accents off, letters and digits only):
  office_words    what the office is called (governor, gubernatorial; county attorney; school board ...)
  district_words  the district or seat (5th district, mn 05, cd 5; senate district 13, sd 13; ward 2 ...)
  place_words     the place the race is in (richfield; oshawa township; red wing ... school)
  county_words    the counties the race reaches (hennepin county), for county-level and smaller races
  state_words     the state (minnesota, minn, minnesotans); the outlet's home state also counts as state context
  specific_words  the words that tell this race from others of the same office in the state (district and place
                  words, or the office words for a statewide race): one of them must be in the headline
  specific_also   and, when not empty, one of these too (a county board's district beside its county's name)
  candidates      [{name (the ballot line as filed), person (one name of a ticket: "Lisa Demuth and Ryan Wilson"
                  gives two entries), party, alone: [full-name phrases], family, family_needs, full_needs, rules}]
  tags            state hashtags for Mastodon, NOT yet checked against real volume (the dry run, Oct 22, decides)

The matching rules (geotag.py, phase 4, applies them; `mentions()` here is the reference and the self-test):
  - Everything needs state context: a state word in the headline, or the outlet's home state is the race's state.
  - A full name ("Ilhan Omar") places alone, unless `full_needs` is "specific" (another candidate in the same state
    has the same name: then the race's specific words must be in the headline too).
  - A family name places only with words of the race: `family_needs` "office" (the default: "Omar" with
    "congress" or "5th district"), "specific" (a common or shared family name: "Anderson" needs "Richfield" or
    "district 3", not just "council"), or "never" (an ordinary word, a place's name, a famous name or too short: only
    the full name places).

Collisions (table name_collisions, one row per state, kind and name): full-name twins in a state, family names shared
by candidates in different races of a state, family names common across the country (20 or more different
candidates on the 2026 lists, about 54,650 names), family names that are ordinary words, place or state names, or the
names of national figures who fill headlines, and names too short to match safely. Each row says which rule follows.
"""

import datetime as dt
import json
import os
import re
import sys
import unicodedata
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from election.feeds import connect, ro  # noqa: E402

BALLOT = os.path.join(HERE, "ballot_2026.sqlite")
LOCAL = os.path.join(HERE, "ballot_local_2026.sqlite")
NOV3 = ("general", "open-primary")
COMMON_AT = 20          # a family name carried by this many different candidates on the 2026 lists is "common"
METHOD = "1.0"

STATE_NAMES = {
    "AK": "Alaska", "AL": "Alabama", "AR": "Arkansas", "AZ": "Arizona", "CA": "California", "CO": "Colorado",
    "CT": "Connecticut", "DC": "District of Columbia", "DE": "Delaware", "FL": "Florida", "GA": "Georgia",
    "HI": "Hawaii", "IA": "Iowa", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "KS": "Kansas", "KY": "Kentucky",
    "LA": "Louisiana", "MA": "Massachusetts", "MD": "Maryland", "ME": "Maine", "MI": "Michigan", "MN": "Minnesota",
    "MO": "Missouri", "MS": "Mississippi", "MT": "Montana", "NC": "North Carolina", "ND": "North Dakota",
    "NE": "Nebraska", "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NV": "Nevada", "NY": "New York",
    "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VA": "Virginia", "VT": "Vermont",
    "WA": "Washington", "WI": "Wisconsin", "WV": "West Virginia", "WY": "Wyoming",
}
# The AP's abbreviations, as headlines and datelines write them (only the ones that are not ordinary words).
AP_ABBR = {
    "AL": ["ala"], "AZ": ["ariz"], "AR": ["ark"], "CA": ["calif"], "CO": ["colo"], "CT": ["conn"], "DE": ["del"],
    "FL": ["fla"], "IL": ["ill"], "IN": ["ind"], "KS": ["kan"], "KY": [], "LA": [], "MD": [], "MA": ["mass"],
    "MI": ["mich"], "MN": ["minn"], "MS": ["miss"], "MO": [], "MT": ["mont"], "NE": ["neb"], "NV": ["nev"],
    "NH": ["n h"], "NJ": ["n j"], "NM": ["n m"], "NY": ["n y"], "NC": ["n c"], "ND": ["n d"], "OK": ["okla"],
    "OR": ["ore"], "PA": [], "RI": ["r i"], "SC": ["s c"], "SD": ["s d"], "TN": ["tenn"], "VT": [], "VA": [],
    "WA": ["wash"], "WV": ["w va"], "WI": ["wis"], "WY": ["wyo"], "GA": [], "DC": ["d c"],
}
DEMONYM = {"MN": ["minnesotan", "minnesotans"], "WI": ["wisconsinite", "wisconsinites"], "IA": ["iowan", "iowans"],
           "TX": ["texan", "texans"], "CA": ["californian", "californians"], "NY": ["new yorker", "new yorkers"],
           "FL": ["floridian", "floridians"], "GA": ["georgian", "georgians"], "OH": ["ohioan", "ohioans"],
           "MI": ["michigander", "michiganders"], "AZ": ["arizonan", "arizonans"], "NV": ["nevadan", "nevadans"],
           "PA": ["pennsylvanian", "pennsylvanians"], "NC": ["north carolinian", "north carolinians"],
           "AK": ["alaskan", "alaskans"], "CO": ["coloradan", "coloradans"], "VA": ["virginian", "virginians"]}

# Family names that are ordinary English words (or office words), so a family name alone is never enough.
ORDINARY = set("""
able adams aide alley allen angel apple archer arm armstrong ash bacon bain baker ball bank banks barber bare barn
barnes baron barr bass bates beach bean bear bell bells berry best bird bishop black blank bliss block bloom blue bond
book booth boss bow bowman box boyd brand brave bread brewer brick bridge bridges bright brook brooks brown buck burn
burns bush butcher butler cain camp cannon cardinal carpenter carr carter case cash castle chain chance chase cherry
church clay clear cliff close coach coffee cole collar cook cooke cooper corn cotton couch cross crow crown cruz cup
dale dance dare darling dash day dean dear deer dick dodge doll door dove drake drew drum duke dunn dye early east
eagle easter english even fair faith falls farmer farmers ferry field fields finch fine fish fisher fleet fletcher
flood flower flowers ford forest fortune foster fowler fox frank free freeman friend frost fry fuller gale gardner
garner gay gentle gift glass glover gold golden good goodman grace grant grave gray green greene grey griffin grove
guard gunn hale hall hand hardy harper hart haven hawk hay hays head heart hill hills hogg holiday holland holly holmes
honey hood hope horn horne house howe huff hunt hunter ivy jay judge just keen key kidd kind king kirk knight lake
lamb lane law lawless lord love lowe luck lucky major mann march marsh marshall mason may mayor meadows merry mill
miller mills moon moore more morning moss mullet nash new newman noble north oak oakes oats page paine palmer park
parks parker parson patton peace pearl penny person pepper pierce pike pine pitt plain plant platt pond pool poole pope
porter post potter pound powell power powers pratt preacher price prince proud quick rain rains ramsey rand ray reed
rich rice ricks ridge rivers roach robin rock rose ross rowe rush russell sale salmon sanders savage sawyer scales
senior sharp shaw sheriff shepherd short silver sing singer slater small smart smith snow south spark sparks speaker
spears speed spring springs stamp stark steel steele stern stewart stone storm story strange street strong summer
summers swan sweet swift tanner taylor teague thorn tower travis trout tucker turner vance victory voter wade wagner
wall walls ward warden warren waters watt way weaver webb well wells west wheeler white wild wilde will williams wing
winter winters wise wolf wood woods worth wren wright young
""".split())
# Names of national figures that fill headlines whatever the race: a candidate who shares one is matched by full name.
FAMOUS = set("""
trump biden obama harris vance clinton bush kennedy pelosi schumer thune mcconnell jeffries johnson musk newsom
desantis walz hegseth rubio sanders warren cruz carter reagan lincoln washington jefferson roosevelt nixon ford
adams jackson madison grant truman hoover kavanaugh roberts alito thomas gorsuch barrett sotomayor kagan jackson
leavitt bondi patel noem kennedy vought miller bessent lutnick
""".split())
SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v", "md", "phd", "esq", "dds", "dr", "mr", "mrs", "ms", "rev", "hon"}
PARTICLES = {"de", "del", "della", "di", "da", "van", "von", "der", "den", "le", "la", "du", "des", "st", "ter", "ten",
             "al", "el", "bin", "mac", "dos", "das"}
# The usual short forms of given names, for a name filed in full with no nickname of its own. Each is only another
# phrase for the same full name: it never places alone without the state, and a family name's rule is unchanged.
SHORT_FORMS = {
    "joshua": ["josh"], "william": ["bill", "will"], "robert": ["bob", "rob"], "james": ["jim"],
    "michael": ["mike"], "thomas": ["tom"], "joseph": ["joe"], "daniel": ["dan"], "christopher": ["chris"],
    "matthew": ["matt"], "nicholas": ["nick"], "anthony": ["tony"], "edward": ["ed"], "steven": ["steve"],
    "stephen": ["steve"], "timothy": ["tim"], "gregory": ["greg"], "jeffrey": ["jeff"], "kenneth": ["ken"],
    "donald": ["don"], "ronald": ["ron"], "douglas": ["doug"], "patrick": ["pat"], "peter": ["pete"],
    "samuel": ["sam"], "benjamin": ["ben"], "jonathan": ["jon"], "katherine": ["kathy", "kate"],
    "catherine": ["cathy", "kate"], "kathleen": ["kathy"], "elizabeth": ["liz", "beth"], "jennifer": ["jen"],
    "rebecca": ["becky"], "susan": ["sue"], "deborah": ["deb"], "patricia": ["pat", "patty"], "kimberly": ["kim"],
    "alexander": ["alex"], "andrew": ["andy"], "charles": ["charlie", "chuck"], "gerald": ["jerry"],
    "lawrence": ["larry"], "raymond": ["ray"], "frederick": ["fred"], "theodore": ["ted"], "zachary": ["zach"],
    "nathaniel": ["nate"], "nathan": ["nate"], "abigail": ["abby"], "jacob": ["jake"], "david": ["dave"],
    "richard": ["rick"], "margaret": ["maggie"], "victoria": ["vicky"],
}
TICKET = re.compile(r"\s+(?:and|&)\s+|\s*/\s*")


def people_on_line(name):
    """A ballot line can name a ticket ("Lisa Demuth and Ryan Wilson", "Josh Shapiro / Austin Davis"): one name a
    person. A line is split only when every part has at least two words."""
    parts = [p.strip() for p in TICKET.split(name or "") if p.strip()]
    if len(parts) > 1 and all(len(p.split()) >= 2 for p in parts):
        return parts
    return [name]

SCHEMA = """
CREATE TABLE IF NOT EXISTS race_keywords (
  race_id TEXT PRIMARY KEY, state TEXT NOT NULL, level TEXT NOT NULL, office TEXT, scope TEXT NOT NULL,
  candidates INTEGER NOT NULL, keywords TEXT NOT NULL, method TEXT NOT NULL, built TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS name_collisions (
  state TEXT NOT NULL, kind TEXT NOT NULL, name TEXT NOT NULL, reasons TEXT NOT NULL, rule TEXT NOT NULL,
  races TEXT NOT NULL, n_races INTEGER NOT NULL, built TEXT NOT NULL,
  PRIMARY KEY (state, kind, name)
);
"""


# ---------------------------------------------------------------------------------------------------- folding

def norm(text):
    """Lower case, accents off, letters and digits only, single spaces. Headlines are folded the same way."""
    t = unicodedata.normalize("NFKD", text or "")
    t = "".join(c for c in t if not unicodedata.combining(c)).lower().replace("’", "'")
    t = re.sub(r"'s\b", "", t).replace("'", "")          # "Minnesota's" -> "minnesota"; "O'Neill" -> "oneill"
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def ordinal(n):
    n = int(n)
    suf = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suf}"


def name_variants(name):
    """(phrases a headline may use for the whole name, family name, extra family spellings) from a name as filed:
    'James C. "Jim" McDermott', 'Anton (Tony) Berg', 'Dalia Al-Aqidi', 'SMITH, JOHN', 'Donald S. Beyer, Jr.'."""
    raw = re.sub(r"\s+-\s+([^-]+?)\s+-\s+", r' "\1" ', (name or "").strip())     # "Emily - Em - Antin"
    nicks = re.findall(r'"([^"]+)"|“([^”]+)”|\(([^)]+)\)', raw)
    nicks = [norm(next(x for x in t if x)) for t in nicks]
    base = re.sub(r'"[^"]*"|“[^”]*”|\([^)]*\)', " ", raw)
    head, sep, tail = base.rpartition(",")
    if sep and all(w in SUFFIXES for w in norm(tail).split()):
        base = head
    if "," in base:                                         # LAST, FIRST
        last, _, first = base.partition(",")
        base = f"{first} {last}"
    words = [w for w in base.split() if norm(w) and norm(w) not in SUFFIXES]
    if not words:
        return [], "", []
    fam_words = [words[-1]]
    i = len(words) - 2
    while i >= 1 and norm(words[i]) in PARTICLES:          # "de la Cruz", "Van Hollen"; never the given name
        fam_words.insert(0, words[i])
        i -= 1
    given = [norm(w) for w in words[:len(words) - len(fam_words)]]
    family = norm(" ".join(fam_words))
    given = [g for g in given if g]
    phrases = []
    if given or nicks:
        if given:
            phrases.append(" ".join(given + [family]))
            first = given[0]
            if len(first.replace(" ", "")) > 1:
                phrases.append(f"{first} {family}")
            if len(given) > 1 and len(given[0]) == 1 and len(given[1]) > 1:    # "J. Michael Smith" -> "michael smith"
                phrases.append(f"{given[1]} {family}")
        for nk in nicks:
            if nk and len(nk.replace(" ", "")) > 1:
                phrases.append(f"{nk} {family}")
        if given and not nicks:                             # "Joshua D Shapiro" is "Josh Shapiro" in headlines
            for nk in SHORT_FORMS.get(given[0], ()):
                phrases.append(f"{nk} {family}")
    extra = []
    if " " in family:                                       # "al aqidi": headlines also write "alaqidi"
        extra.append(family.replace(" ", ""))
    seen, out = set(), []
    for p in phrases:
        p = " ".join(p.split())
        if p and p != family and p not in seen:
            seen.add(p)
            out.append(p)
    return out, family, extra


# ---------------------------------------------------------------------------------------------------- race words

OFFICE_WORDS = {
    "U.S. Senate": ["senate", "senator", "sen", "us senate", "u s senate"],
    "U.S. House": ["congress", "congressional", "house", "representative", "rep", "congressman", "congresswoman",
                   "us house", "u s house"],
    "governor": ["governor", "gubernatorial", "gov"],
    "lieutenant_governor": ["lieutenant governor", "lt governor", "lt gov", "lieutenant gov"],
    "attorney_general": ["attorney general"],
    "secretary_of_state": ["secretary of state"],
    "state_auditor": ["auditor", "state auditor"],
    "state_treasurer": ["treasurer", "state treasurer"],
    "comptroller": ["comptroller"], "state_controller": ["controller"],
    "chief_financial_officer": ["chief financial officer", "cfo"],
    "superintendent_of_public_instruction": ["superintendent", "school superintendent"],
    "state_board_of_education": ["board of education", "state board of education", "school board"],
    "agriculture_commissioner": ["agriculture commissioner", "commissioner of agriculture"],
    "secretary_of_agriculture": ["secretary of agriculture", "agriculture secretary"],
    "insurance_commissioner": ["insurance commissioner", "commissioner of insurance"],
    "labor_commissioner": ["labor commissioner", "commissioner of labor"],
    "land_commissioner": ["land commissioner", "land office", "public lands", "state lands"],
    "school_and_public_lands_commissioner": ["school and public lands", "land commissioner"],
    "railroad_commissioner": ["railroad commissioner", "railroad commission"],
    "public_service_commissioner": ["public service commission", "psc"],
    "public_utilities_commissioner": ["public utilities commission", "puc"],
    "corporation_commissioner": ["corporation commission", "corporation commissioner"],
    "tax_commissioner": ["tax commissioner"], "state_mine_inspector": ["mine inspector"],
    "board_of_equalization": ["board of equalization"], "executive_council": ["executive council"],
    "governors_council": ["governors council"], "oha_trustee": ["office of hawaiian affairs", "oha"],
    "public_education_commission": ["public education commission"],
    "university_board": ["regent", "regents", "board of regents", "trustee", "trustees", "board of governors"],
    "state_senate": ["state senate", "state senator", "senate", "senator", "legislature", "legislative", "sen"],
    "state_house": ["state house", "state representative", "house", "representative", "rep", "legislature",
                    "legislative"],
    "supreme_court": ["supreme court", "justice"], "court_of_appeals": ["court of appeals", "appeals court", "judge"],
    "district_court": ["district court", "judge", "judicial"],
    "county_commissioner": ["county commissioner", "county commission", "county board", "commissioner"],
    "county_attorney": ["county attorney"], "sheriff": ["sheriff"],
    "county_auditor": ["county auditor", "auditor"], "county_auditor_treasurer": ["auditor treasurer", "county auditor"],
    "county_treasurer": ["county treasurer", "treasurer"], "county_recorder": ["county recorder", "recorder"],
    "county_surveyor": ["county surveyor", "surveyor"], "county_park": ["park commissioner", "park district"],
    "soil_water": ["soil and water", "swcd", "soil water"],
    "mayor": ["mayor", "mayoral"], "council": ["city council", "council", "council member", "councilmember"],
    "city_clerk": ["city clerk"], "city_clerk_treasurer": ["clerk treasurer"], "city_treasurer": ["city treasurer"],
    "town_supervisor": ["town board", "township board", "supervisor"], "town_clerk": ["town clerk", "township clerk"],
    "town_clerk_treasurer": ["town clerk", "clerk treasurer"], "town_treasurer": ["town treasurer"],
    "school_board": ["school board", "board of education", "school district"],
    "hospital_board": ["hospital board", "hospital district"], "sanitary_board": ["sanitary district"],
    "utility_board": ["utility board", "utilities commission"],
}
SCHOOL_TAILS = re.compile(r"\b(independent school district|public school district|public schools|area public schools|"
                          r"area schools|school district|schools|isd|district)\b.*$", re.I)


def office_words(kind, office):
    words = list(OFFICE_WORDS.get(kind, []))
    o = norm(office)
    if o and o not in words and len(o) <= 60:
        words.append(o)
    return words


def clean_place(name, kind):
    n = re.sub(r"\([^)]*\)", " ", name or "")
    if kind == "school":
        core = norm(SCHOOL_TAILS.sub("", n))
        return [core] if core else []
    n = norm(n)
    for tail in (" city", " village", " township", " town"):
        if n.endswith(tail):
            n = n[: -len(tail)]
    out = [n] if n else []
    if n.startswith("st "):
        out.append("saint " + n[3:])
    return out


def district_words(level, kind, district, seat, state, jurisdiction):
    st = state.lower()
    d = (district or "").strip()
    out = []
    if kind == "U.S. House":
        if not d or d in ("00", "AL", "0"):
            return ["at large", "at large district"]
        n = int(d)
        return [f"{ordinal(n)} district", f"{ordinal(n)} congressional district", f"district {n}", f"cd {n}",
                f"cd{n}", f"{st} {n:02d}", f"{st} {n}", f"{st}{n:02d}"]
    if kind in ("state_senate", "state_house") and d:
        dd = norm(d)
        pre = "senate district" if kind == "state_senate" else "house district"
        ab = "sd" if kind == "state_senate" else "hd"
        out = [f"{pre} {dd}", f"{ab} {dd}", f"{ab}{dd.replace(' ', '')}", f"district {dd}"]
        return out
    if level == "court":
        if d and d.isdigit():
            out += [f"{ordinal(int(d))} judicial district"]
        return out
    if d:
        dd = norm(d)
        if dd and dd not in ("at large",):
            out += [f"district {dd}", f"ward {dd}"] if level == "city" else [f"district {dd}"]
    if seat and norm(seat) not in ("", "at large"):
        out.append(f"seat {norm(seat)}")
    return out


def state_words(code):
    words = [norm(STATE_NAMES[code])] + AP_ABBR.get(code, []) + DEMONYM.get(code, [])
    return [w for w in dict.fromkeys(words) if w]


# ---------------------------------------------------------------------------------------------------- the build

def scope_races():
    """Every race in scope, with its candidates on the November list: [{race_id, state, level, kind, office, ...}]."""
    races = []
    fed = ro(BALLOT)
    cands = defaultdict(list)
    for rid, name, party, wi in fed.execute(
            f"SELECT race_id, name, party, write_in FROM candidates WHERE election IN ({','.join('?' * len(NOV3))}) "
            "ORDER BY race_id, COALESCE(ballot_order, 999), name", NOV3):
        cands[rid].append({"name": name, "party": party or "", "write_in": int(wi or 0)})
    for rid, office, state, district in fed.execute("SELECT race_id, office, state, district FROM races ORDER BY race_id"):
        races.append({"race_id": rid, "state": state, "level": "federal", "kind": office, "office": office,
                      "district": district, "seat": None, "jurisdiction": STATE_NAMES.get(state, state),
                      "jurisdiction_id": None, "county_ids": [], "partisan": 1, "scope": "federal",
                      "candidates": cands.get(rid, [])})
    fed.close()
    loc = ro(LOCAL)
    cands = defaultdict(list)
    for rid, name, party, wi in loc.execute(
            "SELECT c.race_id, c.name, c.party, c.write_in FROM sl_candidates c JOIN sl_races r USING (race_id) "
            f"WHERE (r.state='MN' OR r.level='statewide') AND c.election IN ({','.join('?' * len(NOV3))}) "
            "ORDER BY c.race_id, COALESCE(c.ballot_order, 999), c.name", NOV3):
        cands[rid].append({"name": name, "party": party or "", "write_in": int(wi or 0)})
    counties = {(k, i): n for k, i, n in loc.execute("SELECT kind, id, name FROM sl_places WHERE kind='county'")}
    for row in loc.execute("SELECT race_id, state, level, office_kind, office, jurisdiction, jurisdiction_id, county_ids, "
                           "district, seat, partisan FROM sl_races WHERE state='MN' OR level='statewide' "
                           "ORDER BY race_id"):
        rid, state, level, kind, office, jur, jid, cids, district, seat, partisan = row
        try:
            cids = json.loads(cids or "[]")
        except ValueError:
            cids = []
        if not isinstance(cids, list):
            cids = []
        races.append({"race_id": rid, "state": state, "level": level, "kind": kind, "office": office,
                      "district": district, "seat": seat, "jurisdiction": jur, "jurisdiction_id": jid,
                      "county_ids": cids, "partisan": int(partisan or 0),
                      "scope": "statewide" if level == "statewide" else "minnesota",
                      "county_names": [counties.get(("county", c), "") for c in cids],
                      "candidates": cands.get(rid, [])})
    loc.close()
    return races


def place_names_by_state():
    """Folded names of every place the local database knows, by state where it can tell (for the place-name rule)."""
    loc = ro(LOCAL)
    out = defaultdict(set)
    for state, jur, level in loc.execute("SELECT DISTINCT state, jurisdiction, level FROM sl_races"):
        if level in ("city", "township", "county", "soil_water"):
            for p in clean_place(re.sub(r"\b(county|township|parish)\b", "", jur or "", flags=re.I), level):
                out[state].add(p)
    loc.close()
    for code, name in STATE_NAMES.items():
        out["*"].add(norm(name))
    return out


def all_family_counts():
    """How many different candidates on all the 2026 lists carry each family name (the 'common' measure)."""
    names = set()
    for path, sql in ((BALLOT, "SELECT DISTINCT name FROM candidates"), (LOCAL, "SELECT DISTINCT name FROM sl_candidates")):
        con = ro(path)
        names |= {r[0] for r in con.execute(sql)}
        con.close()
    cnt = Counter()
    for n in names:
        _, fam, _ = name_variants(n)
        if fam:
            cnt[fam] += 1
    return cnt, len(names)


def race_words(r):
    kind = r["kind"]
    ow = office_words(kind, r["office"])
    dw = district_words(r["level"], kind, r["district"], r["seat"], r["state"], r["jurisdiction"])
    pw, cw = [], []
    if r["level"] in ("city", "township", "school", "hospital", "other"):
        pw = clean_place(r["jurisdiction"], r["level"])
        if r["level"] == "township":
            pw = [f"{p} township" for p in pw]
        if r["level"] == "school":
            pw = [f"{p} school" for p in pw] + [f"{p} schools" for p in pw] + pw
            m = re.search(r"#\s*0*(\d+)", r["jurisdiction"] or "")
            if m:
                # "isd 625", never a bare "district 625": a district number alone reads as any county's or city's
                pw += [f"isd {m.group(1)}", f"isd{m.group(1)}", f"school district {m.group(1)}"]
    if r["level"] in ("county", "soil_water", "city", "township", "school", "hospital", "other", "court"):
        for cn in r.get("county_names", []):
            if cn:
                cw.append(norm(cn))
                if r["level"] in ("county", "soil_water"):
                    core = norm(re.sub(r"\bcounty\b", "", cn, flags=re.I))
                    if core:
                        cw.append(f"{core} county")
    if r["level"] == "soil_water" and r["jurisdiction"] and "soil" in (r["jurisdiction"] or "").lower():
        pw = [norm(re.sub(r"\([^)]*\)", "", r["jurisdiction"]))]
    pw = list(dict.fromkeys(p for p in pw if p))
    cw = list(dict.fromkeys(c for c in cw if c))
    # specific: any one of these must be in the headline; also: and, when not empty, any one of these too.
    also = []
    if r["level"] == "federal" and kind == "U.S. Senate":
        specific = ow
    elif r["level"] == "federal":
        specific = dw
    elif r["level"] == "statewide":
        specific, also = ow, dw
    elif r["level"] == "legislature":
        specific = [w for w in dw if not (kind == "state_senate" and w.startswith("district "))]
    elif r["level"] == "court":
        specific = dw or ow
        if r["kind"] == "district_court" and not dw:
            specific = cw
    elif r["level"] in ("county", "soil_water"):
        specific, also = (pw or cw), dw
    else:                                        # city, township, school, hospital, other
        specific, also = pw or cw, dw
    if not specific:
        specific = ow
    return ow, dw, pw, cw, list(dict.fromkeys(specific)), list(dict.fromkeys(also))


def build(con=None, say=print):
    own = con is None
    con = con or connect()
    con.executescript(SCHEMA)
    races = scope_races()
    counts, n_names = all_family_counts()
    places = place_names_by_state()
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

    # every candidate's variants, then the collisions within each state
    full_by_state = defaultdict(lambda: defaultdict(set))
    fam_by_state = defaultdict(lambda: defaultdict(set))
    for r in races:
        for c in r["candidates"]:
            c["_people"] = []
            for person in people_on_line(c["name"]):
                phrases, fam, extra = name_variants(person)
                c["_people"].append((person, phrases, fam, extra))
                for p in phrases[:2]:
                    full_by_state[r["state"]][p].add(r["race_id"])
                if fam:
                    fam_by_state[r["state"]][fam].add(r["race_id"])

    collisions = {}

    def collide(state, kind, name, reason, rule, races_):
        key = (state, kind, name)
        cur = collisions.setdefault(key, {"reasons": [], "rule": rule, "races": set()})
        if reason not in cur["reasons"]:
            cur["reasons"].append(reason)
        order = {"specific": 1, "never": 2}
        if order.get(rule, 0) > order.get(cur["rule"], 0):
            cur["rule"] = rule
        cur["races"] |= set(races_)

    for state, fams in fam_by_state.items():
        for fam, rids in fams.items():
            if len(rids) > 1:
                collide(state, "family", fam, f"carried by candidates in {len(rids)} races in this state",
                        "specific", rids)
            if counts.get(fam, 0) >= COMMON_AT:
                collide(state, "family", fam, f"common: {counts[fam]} different candidates on the 2026 lists",
                        "specific", rids)
            if fam in ORDINARY:
                collide(state, "family", fam, "an ordinary word", "never", rids)
            if fam in FAMOUS:
                collide(state, "family", fam, "the name of a national figure who fills headlines", "never", rids)
            if fam in places.get(state, set()) or fam in places["*"]:
                collide(state, "family", fam, "the name of a place in the state, or of a state", "never", rids)
            if len(fam.replace(" ", "")) <= 2:
                collide(state, "family", fam, "too short to match safely", "never", rids)
        for full, rids in full_by_state[state].items():
            if len(rids) > 1:
                collide(state, "full", full, f"the same full name in {len(rids)} races in this state", "specific", rids)

    n_sets = n_cands = 0
    rows = []
    for r in races:
        ow, dw, pw, cw, specific, also = race_words(r)
        cands = []
        for c in r["candidates"]:
            for person, phrases, fam, extra in c["_people"]:
                fcol = collisions.get((r["state"], "family", fam))
                family_needs = fcol["rule"] if fcol else "office"
                full_needs = "state"
                rules = []
                if fcol:
                    rules.append(f"family:{fam}")
                for p in phrases:
                    if (r["state"], "full", p) in collisions:
                        full_needs = "specific"
                        rules.append(f"full:{p}")
                if not phrases:
                    family_needs = "specific" if family_needs != "never" else "never"
                    rules.append("no given name on the list")
                cands.append({"name": c["name"], "person": person, "party": c["party"], "write_in": c["write_in"],
                              "alone": phrases, "family": fam, "family_also": extra,
                              "family_needs": family_needs, "full_needs": full_needs, "rules": rules})
            n_cands += 1
        kw = {"race_id": r["race_id"], "state": r["state"], "level": r["level"], "kind": r["kind"],
              "office": r["office"], "office_words": ow, "district_words": dw, "place_words": pw,
              "county_words": cw, "state_words": state_words(r["state"]), "specific_words": specific,
              "specific_also": also, "candidates": cands, "list_loaded": bool(cands),
              "tags": [f"{r['state'].lower()}pol", f"{r['state'].lower()}leg"], "tags_checked": False}
        rows.append((r["race_id"], r["state"], r["level"], r["office"], r["scope"], len(cands),
                     json.dumps(kw, ensure_ascii=False, separators=(",", ":")), METHOD, now))
        n_sets += 1
    with con:
        con.execute("DELETE FROM race_keywords")
        con.execute("DELETE FROM name_collisions")
        con.executemany("INSERT INTO race_keywords VALUES (?,?,?,?,?,?,?,?,?)", rows)
        con.executemany("INSERT INTO name_collisions VALUES (?,?,?,?,?,?,?,?)",
                        [(s, k, n, json.dumps(v["reasons"]), v["rule"], json.dumps(sorted(v["races"])),
                          len(v["races"]), now) for (s, k, n), v in sorted(collisions.items())])
    say(f"keywords: {n_sets} race sets ({n_cands} candidacies; family names measured over {n_names:,} names); "
        f"{len(collisions)} collisions")
    if own:
        con.close()
    return n_sets


# ---------------------------------------------------------------------------------------------------- matching

RULE_TEXT = {
    "office": "family name only with the race's office or district words",
    "specific": "only with the words that tell this race apart (its district, place or county)",
    "never": "family name alone never; full name only",
    "state": "full name, with the state named or the outlet in the state",
}


def _has(text, phrases):
    return any(f" {p} " in text for p in phrases if p)


def mentions(headline, kw, outlet_state=None):
    """The reference matcher: [(candidate name, how)] for one race's keyword set. High confidence only (rule 1 of
    ARCHITECTURE.md 4.4); placing by place names and GDELT's places is geotag.py's work."""
    t = f" {norm(headline)} "
    state_ctx = outlet_state == kw["state"] or _has(t, kw["state_words"])
    if not state_ctx:
        return []
    office = _has(t, kw["office_words"]) or _has(t, kw["district_words"])
    specific = _has(t, kw["specific_words"]) and (not kw.get("specific_also") or _has(t, kw["specific_also"]))
    hits = []
    for c in kw["candidates"]:
        if any(n == c["name"] for n, _ in hits):
            continue
        if _has(t, c["alone"]) and (c["full_needs"] == "state" or specific):
            hits.append((c["name"], "full name"))
            continue
        fams = [c["family"]] + c.get("family_also", [])
        if c["family_needs"] != "never" and _has(t, fams):
            if (c["family_needs"] == "office" and office) or (c["family_needs"] == "specific" and specific):
                hits.append((c["name"], f"family name with {'office' if c['family_needs'] == 'office' else 'race'} words"))
    return hits


def selftest(say=print):
    """The matching rules on made-up headlines (no feed text)."""
    ok = True
    kwa = {"state": "MN", "state_words": state_words("MN"), "office_words": office_words("U.S. House", "U.S. House"),
           "district_words": district_words("federal", "U.S. House", "05", None, "MN", ""),
           "specific_words": district_words("federal", "U.S. House", "05", None, "MN", ""), "specific_also": [],
           "candidates": []}
    for nm, fn, ff in (("Jane Q. Example", "office", "state"), ('Robert "Bob" Anderson', "specific", "state"),
                       ("Mary Lake", "never", "state")):
        ph, fam, ex = name_variants(nm)
        kwa["candidates"].append({"name": nm, "alone": ph, "family": fam, "family_also": ex,
                                  "family_needs": fn, "full_needs": ff})
    cases = [
        ("Jane Example leads early count in Minnesota", None, ["Jane Q. Example"]),
        ("Example wins endorsement in congressional race", "MN", ["Jane Q. Example"]),
        ("Example wins endorsement", "MN", []),                                  # family, no office words
        ("Jane Example speaks in Ohio", "OH", []),                               # no state context
        ("Anderson ahead in House race", "MN", []),                              # common family: needs district words
        ("Anderson ahead in Minnesota's 5th District", None, ['Robert "Bob" Anderson']),
        ("Bob Anderson rallies voters", "MN", ['Robert "Bob" Anderson']),         # nickname plus family
        ("Lake levels fall in Minnesota congressional district 5", None, []),   # ordinary word: never alone
        ("Mary Lake on the ballot in MN-05", "MN", ["Mary Lake"]),
    ]
    for text, ost, want in cases:
        got = [n for n, _ in mentions(text, kwa, ost)]
        good = got == want
        ok = ok and good
        say(f"{'PASS' if good else 'FAIL'} self-test: {text!r} -> {got}")
    pv = name_variants('James C. "Jim" McDermott')
    good = pv[1] == "mcdermott" and "jim mcdermott" in pv[0] and "james mcdermott" in pv[0]
    say(f"{'PASS' if good else 'FAIL'} self-test: name variants {pv}")
    ok = ok and good
    pv = name_variants("Dalia Al-Aqidi")
    good = pv[1] == "al aqidi" and "dalia al aqidi" in pv[0] and "alaqidi" in pv[2]
    say(f"{'PASS' if good else 'FAIL'} self-test: name variants {pv}")
    ok = ok and good
    pv = name_variants("Donald S. Beyer, Jr.")
    good = pv[1] == "beyer" and "donald beyer" in pv[0]
    say(f"{'PASS' if good else 'FAIL'} self-test: name variants {pv}")
    ok = ok and good
    pv = name_variants("Emily - Em - Antin")
    good = pv[1] == "antin" and "em antin" in pv[0] and "emily antin" in pv[0]
    say(f"{'PASS' if good else 'FAIL'} self-test: name variants {pv}")
    ok = ok and good
    pl = people_on_line("Amy Klobuchar and Ben Schierer") + people_on_line("Joshua D Shapiro / Austin Davis") + \
        people_on_line("Barnes & Noble")
    good = pl == ["Amy Klobuchar", "Ben Schierer", "Joshua D Shapiro", "Austin Davis", "Barnes & Noble"]
    say(f"{'PASS' if good else 'FAIL'} self-test: tickets split {pl}")
    ok = ok and good
    # a county race: a shared family name needs the county AND the district
    r = {"race_id": "t", "state": "MN", "level": "county", "kind": "county_commissioner", "office": "County Commissioner",
         "district": "2", "seat": None, "jurisdiction": "Olmsted County", "county_names": ["Olmsted County"]}
    ow, dw, pw, cw, spec, also = race_words(r)
    ph, fam, ex = name_variants("Pat Anderson")
    kwc = {"state": "MN", "state_words": state_words("MN"), "office_words": ow, "district_words": dw,
           "specific_words": spec, "specific_also": also,
           "candidates": [{"name": "Pat Anderson", "alone": ph, "family": fam, "family_also": ex,
                           "family_needs": "specific", "full_needs": "state"}]}
    for text, want in (("Anderson leads Olmsted County board race", []),
                       ("Anderson leads in Olmsted County District 2", ["Pat Anderson"])):
        got = [n for n, _ in mentions(text, kwc, "MN")]
        good = got == want
        ok = ok and good
        say(f"{'PASS' if good else 'FAIL'} self-test: {text!r} -> {got}")
    return ok


# ---------------------------------------------------------------------------------------------------- checks

def run_checks(con=None, say=print):
    own = con is None
    con = con or connect()
    ok = True

    def check(cond, line):
        nonlocal ok
        say(("PASS " if cond else "FAIL ") + line)
        ok = ok and bool(cond)

    races = scope_races()
    have = {r[0]: json.loads(r[1]) for r in con.execute("SELECT race_id, keywords FROM race_keywords")}
    by_scope = Counter(r["scope"] for r in races)
    mn = [r for r in races if r["state"] == "MN"]
    missing = [r["race_id"] for r in races if r["race_id"] not in have]
    check(not missing, f"a keyword set for every race in scope: {len(races)} ({by_scope['federal']} federal, "
                       f"{by_scope['statewide']} statewide in {len({r['state'] for r in races if r['scope'] == 'statewide'})} "
                       f"states, {by_scope['minnesota']} other Minnesota); Minnesota {len(mn)} in all"
          + (f"; missing {missing[:5]}" if missing else ""))
    lost = 0
    for r in races:
        kw = have.get(r["race_id"])
        names = {c["name"] for c in (kw or {}).get("candidates", [])}
        lost += sum(1 for c in r["candidates"] if c["name"] not in names)
    check(lost == 0, f"every candidate on a November list is in its race's set ({sum(len(r['candidates']) for r in races)})")
    nolist = [r for r in races if not r["candidates"]]
    say(f"     {len(nolist)} races have no November list loaded yet (sets carry office, district and place words "
        f"only): {', '.join(sorted({r['state'] for r in nolist}))}")
    noname = sum(1 for kw in have.values() for c in kw["candidates"] if not c["alone"] and c["family_needs"] == "never")
    say(f"     {noname} candidates can be placed by no phrase at all (no given name and an unsafe family name)")
    generic = [rid for rid, kw in have.items() if kw["level"] == "school"
               and any(re.fullmatch(r"district \d+", w) for w in kw["specific_words"])]
    check(not generic, "no school board is told apart by a bare district number"
          + (f"; not {generic[:3]}" if generic else ""))
    empty = [rid for rid, kw in have.items() if not kw["office_words"]]
    check(not empty, "every set has office words" + (f"; not {empty[:5]}" if empty else ""))
    nores = con.execute("SELECT COUNT(*) FROM name_collisions WHERE rule NOT IN ('specific','never')").fetchone()[0]
    check(nores == 0, "every collision has a rule (specific or never)")
    by = con.execute("SELECT kind, rule, COUNT(*) FROM name_collisions GROUP BY kind, rule").fetchall()
    say("     collisions: " + "; ".join(f"{k} names, rule {r}: {n}" for k, r, n in by))
    unhandled = 0
    for kw in have.values():
        for c in kw["candidates"]:
            row = con.execute("SELECT rule FROM name_collisions WHERE state=? AND kind='family' AND name=?",
                              (kw["state"], c["family"])).fetchone()
            if row and c["family_needs"] != row[0] and c["alone"]:
                unhandled += 1
    check(unhandled == 0, "every candidate whose family name collides carries that collision's rule")
    check(selftest(say=lambda s: say("     " + s)), "the matching rules' self-test")
    if own:
        con.close()
    return ok


def main(argv):
    cmd = argv[0] if argv else "check"
    if cmd == "build":
        build()
        return 0
    if cmd == "check":
        return 0 if run_checks() else 1
    if cmd == "collisions":
        con = connect()
        q = "SELECT state, kind, name, rule, reasons, n_races FROM name_collisions"
        args = ()
        if len(argv) > 1:
            q += " WHERE state=?"
            args = (argv[1].upper(),)
        for s, k, n, rule, reasons, nr in con.execute(q + " ORDER BY state, kind, n_races DESC, name", args):
            print(f"{s} {k:<6} {n:<24} {rule:<8} {nr:>4} races  {'; '.join(json.loads(reasons))}")
        return 0
    if cmd == "show" and len(argv) > 1:
        con = connect()
        row = con.execute("SELECT keywords FROM race_keywords WHERE race_id=?", (argv[1],)).fetchone()
        print(json.dumps(json.loads(row[0]), indent=1, ensure_ascii=False) if row else "no such race")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
