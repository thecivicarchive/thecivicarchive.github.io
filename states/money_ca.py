#!/usr/bin/env python3
"""
states/money_ca.py
==================
California campaign money, from the Secretary of State's Cal-Access raw data export (dbwebexport.zip, about 1.6 GB,
refreshed daily, no account): every table of the Cal-Access database as tab-separated text, with the Secretary's
own format guides in the same zip. Three tables do the work. The cover pages of every campaign statement
(CVR_CAMPAIGN_DISCLOSURE) say which committee filed it, for which candidate, office and district; the Secretary's
filer links (FILER_LINKS, "candidate controls this committee") tie every committee to one candidate record, so a
legislator's committees across the years are found through one record rather than by spelling; and Schedule A and
Schedule C of every Form 460 (RCPT) list every gift of $100 or more. Independent spending comes from Schedule D of
Form 460 and Part 5 of Form 461, the schedules on which a spender names the candidate it supported or opposed.

The same rule as everywhere on the site. Organizations are named: political committees, party committees, other
candidates' committees, and the businesses, unions, tribes and associations California lets give directly (Cal-
Access files them all as "other", so they are named as the campaign reported them and labelled other organizations).
People are not named: every gift from an individual goes into a yearly total, and the name on that row is never
written to the database; a gift from the candidate is counted as own money. Campaigns do not always use the codes
as meant, so the loader also reads names: a giver filed as "other" or as a committee whose name reads like a
person's (a given name the file itself knows, two or three words, no organization's word), a person doing business
under a name, a professional with a credential, a family or living trust, an estate, a person "and affiliated
entities", and a major donor registered under a person's name are all counted with people. A contact person's name
that a campaign wrote after a business's name is cut off before the name is kept. A business named after its owner
may be hidden this way; a person is never shown.

Gifts under $100, which the form reports as one sum, are counted as other receipts. Loans received are a yearly
total, except a loan from the member's own other committee, which is that committee's money moving. A transfer
between committees (Cal-Access attributes it to the original givers) is recorded as coming from the committee the
money left, so money moved between a member's own committees is never counted twice. Late-contribution reports
(Form 497) are left out because the same gifts appear on the next Form 460; an amended statement replaces the
original; a statement filed twice under two filing numbers counts once.

What counts as the member's campaign: the committees for the Assembly or Senate seat, that is candidate committees,
officeholder accounts and legal defense funds, read from the cover pages' offices and the committee's own name, and
only the statements whose own cover page names that seat. A legislator's ballot measure committee, a general
purpose committee and a committee for another office (Controller, Insurance Commissioner, a county central
committee, a city council) are left out and listed at the end of the run, so they can be read.

Outside spending names the recipient committees that did the spending. A major donor filing Form 461 on its own may
be a business or a person, and the file does not say which, so a Form 461 spender is named only when its name
carries an organization's word and does not read like a person's; the rest are added into one line that names
nobody. Its "purpose" text stays in the database and never reaches a page.

  state_committees   each committee read as the member's campaign: Cal-Access filer id, chamber, member
  state_gifts        every gift from an organization to one of those committees
  state_sources      yearly totals by source (people, committees, party, other candidates, other organizations,
                     own money, loans, other)
  state_outside      independent spending for or against a sitting member, by spender

    python -m states.money_ca --db state_ca.sqlite --since 2015
"""

import argparse
import collections
import difflib
import io
import os
import re
import sqlite3
import sys
import time
import unicodedata
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from states import net                                     # noqa: E402
from states.money_mn import norm, given_fits               # noqa: E402
from states.money_tx import families_of, givens_of, initials_fit   # noqa: E402

URL = "https://campaignfinance.cdn.sos.ca.gov/dbwebexport.zip"
OFFICE = {"ASM": "House", "SEN": "Senate"}
DATA = "CalAccess/DATA/"

# -- reading a committee's purpose from its name
SEAT_STRONG = re.compile(r"\b(for|re-?elect\w*|elect)\b.{0,40}\b(state )?(assembly|senate)\b|\b(assembly|senate|assemblym[ae]n|assemblywoman|assemblymember|senator)\b.{0,40}\b(20\d\d|officeholder)"
                         r"|\bfor (ad|sd|asm|sen) ?\d", re.I)                   # the name itself says which seat
SEAT_WORD = re.compile(SEAT_STRONG.pattern + r"|\bofficeholder\b|\blegal defense\b", re.I)   # or says it is an officeholder account or legal defense fund
BALLOT_WORD = re.compile(r"ballot measure|ballot committee|\bmeasure committee\b|\bprop(osition)? ?\d|\b(yes|no) on (prop|measure)\b", re.I)
OTHER_OFFICE_WORD = re.compile(r"\b(central committee|county committee|dccc|rccc|community college|trustee|city council|council ?member|mayor|supervisor|"
                               r"school board|board of education|board of equalization|controller|treasurer|insurance commissioner|attorney general|"
                               r"superintendent|secretary of state|lt\.? governor|lieutenant governor|governor|congress|water board|sheriff|district attorney|"
                               r"judge|assessor|auditor)\b", re.I)

# -- reading a giver's kind from its name
PARTY_WORD = re.compile(r"\b(democratic|republican|libertarian|green|peace and freedom|american independent) (party|state central|central committee)\b|"
                        r"\b(county )?central committee\b|\bparty of \w+ county\b|\b(cdp|crp)\b|\bdemocrats of\b|\brepublicans of\b|\bdemocratic caucus\b", re.I)
CAND_WORD = re.compile(r"\b(friends of (?!the\b)|committee to elect|re-?elect|for (state )?(assembly|senate|senator|congress|governor|controller|treasurer|"
                       r"attorney general|secretary of state|superintendent|supervisor|mayor|city council|council|school board|board of|sheriff|district attorney|"
                       r"judge|central committee)|for (asm|sen|ad|sd) ?\d)", re.I)
# words only an organization's name carries (strong), and words that may also be a surname (weak: Frank Church, Susan Wines)
STRONG_ORG = re.compile(r"\b(corp(oration)?|inc(orporated)?|llc|l\.l\.c\.?|ltd|limited|company|co\.|companies|band of|tribe|tribal|rancheria|indians|"
                        r"association|assn|assoc|associates|union|local \d+|committee|pac|partners(hip)?|lp|llp|pc|apc|plc|industries|industrial|enterprises|"
                        r"foundation|council|federation|chamber|league|coalition|alliance|society|institute|healthcare|hospital|medical|dental|group|"
                        r"holdings|properties|realty|systems|technologies|technology|services|farm bureau|growers|orchards|dairies|dairy|winery|vineyards|"
                        r"brewing|brewery|distillery|casinos?|resort|hotel|insurance|energy|utilities|apartments|builders|construction|concrete|development|"
                        r"management|international|brands|stores|markets?|motors|airlines|rail|shipping|logistics|trucking|transport|trust fund|benefit trust|"
                        r"fund|club|network|organization|org|guild|teachers|employees|workers|firefighters|police|deputies|nurses|physicians|dentists|"
                        r"realtors|attorneys|lawyers|engineers|contractors|consulting|advis[eo]rs|strategies|affairs|marketing|advertising|communications|"
                        r"media|studios|entertainment|pictures|films|products|recycling|machinery|architecture|bakery|creamery|restaurants?|cafe|catering|"
                        r"foods|pharmacy|pharmaceuticals?|labs|sciences|lifesciences|solutions|security|schools?|academy|college|university|church of|"
                        r"ministries|charities|community|district|city of|county of|center|project|operations|global|worldwide|mobile|telephone|wireless|"
                        r"software|digital|solar|capital|investments|ventures|resources|agency|education|fuels|burgers|pizza|grill|gaming|hotline|imports|"
                        r"rentals|storage|supply|hardware|tires?|automotive|dealership|cannabis|dispensary|nursery|produce|packing|bonds|pawn|pest control|"
                        r"plumbing|roofing|landscaping|painting|flooring|lumber|mining|quarry|cement|asphalt|paving|engineering|environmental|research|"
                        r"elect|action|issues|voters|political|citizens|federal|national|dba|d/b/a|d\.b\.a\.|usa|u\.s\.a?\.?|us|america|american|bros|brothers|"
                        r"poultry|p\.c\.?|a\.p\.c\.?|l\.p\.?|l\.l\.p\.?|affiliates|affiliated|entities|subsidiaries)(?![a-z])", re.I)     # not \b: "Co." ends in a period
WEAK_ORG = re.compile(r"\b(church|law|bank|cable|nation|wines?|valley|bay|homes?|farms?|estates?|ford|glass|steel|golden|sierra|pacific|western|southern|"
                      r"northern|central|coast|care|the|of|for|and|&)\b", re.I)
DBA = re.compile(r"\b(dba|d/b/a|d\.b\.a\.|sole prop(rietor)?(ship)?|attorney at law)\b", re.I)
AFFILIATED = re.compile(r"\s*(and|&)\s+(its\s+)?affil\w*\s+entit\w*.*$", re.I)
CREDENTIAL = re.compile(r"[,\s]+(m\.?d|d\.?d\.?s|d\.?m\.?d|d\.?c|c\.?p\.?a|esq|ph\.?d|d\.?v\.?m|o\.?d|d\.?o|r\.?n|j\.?d|m\.?s|d\.?p\.?m|n\.?p|pa-c|lcsw|mft|cfp|ret)"
                        r"\.?[.,\s]*$", re.I)                                    # a credential at the end of a name, "Jaclynn Do MD", "Cooley, D.D.S., M.S"
LAST_FIRST = re.compile(r"^[A-Za-z'\-]+,\s*(?!(na|inc|llc|ltd|pc|pbc|lp|llp|usa|ca|co|corp|corporation|company|plc|gmbh|sa|ag|nv|bv|apc|dds|md)\b)[A-Za-z'\-]{2,}(\s+[A-Za-z]\.?)?\.?$", re.I)   # how the Secretary registers a person: "SMALL, KEVIN S."
PROFESSION = re.compile(r"\s+(immigration consultant|consultant|attorney|realtor|architect|insurance agent|broker|dentist|physician|chiropractor|optometrist|"
                        r"contractor|trustee|md inc)\.?\s*$", re.I)
TRUST = re.compile(r"\b(family|living|revocable|irrevocable|marital|survivors?'?|charitable lead|testamentary|residuary|bypass|exempt)\s+trust\b|\btrust\b", re.I)
TRUST_ORG = re.compile(r"\b(trust fund|benefit trust|benefit|pension|retirement|bank|company|inc|llc|association|assoc|assn|officers|foundation|union|committee|"
                       r"pac|hospital|land trust|community|charitable trust|fund)\b", re.I)
ESTATE = re.compile(r"^\s*(the\s+)?estate of\b", re.I)
TITLE = re.compile(r"^(dr|mr|mrs|ms|miss|hon|honorable|rev|senator|sen|assemblymember|assembly ?member|assemblyman|assemblywoman|asm|rep|supervisor|mayor|"
                   r"councilmember)\.?\s+", re.I)
TITLE_WORDS = {"dr", "mr", "mrs", "ms", "miss", "hon", "rev"}
SUFFIX_WORDS = {"jr", "sr", "ii", "iii", "iv", "md", "dds", "dmd", "dvm", "esq", "phd", "cpa", "ret", "dpm"}
TAIL_PAREN = re.compile(r"\s*\(([^()]*)\)\s*(\(\s*\))?\s*$")
TAIL_DASH = re.compile(r"\s+[-–]\s+([^-–]+?)\s*$")
UNNAMED_ID, UNNAMED_NAME = "f461-unnamed", "Major donors filing on their own (Form 461) whose names are not shown here: people, and businesses the file does not mark as such"

SCHEMA = """
CREATE TABLE IF NOT EXISTS state_committees (reg_num TEXT PRIMARY KEY, name TEXT, office TEXT, bioguide_id TEXT);
CREATE TABLE IF NOT EXISTS state_gifts (
  id INTEGER PRIMARY KEY, bioguide_id TEXT NOT NULL, committee TEXT NOT NULL, office TEXT, year INTEGER, date TEXT, amount REAL NOT NULL,
  donor_id TEXT, donor_name TEXT, donor_kind TEXT, in_kind INTEGER);
CREATE TABLE IF NOT EXISTS state_sources (
  bioguide_id TEXT NOT NULL, committee TEXT NOT NULL, office TEXT, year INTEGER NOT NULL, source TEXT NOT NULL, amount REAL NOT NULL, n INTEGER NOT NULL,
  PRIMARY KEY (bioguide_id, committee, year, source));
CREATE TABLE IF NOT EXISTS state_outside (
  id INTEGER PRIMARY KEY, bioguide_id TEXT NOT NULL, committee TEXT NOT NULL, year INTEGER, date TEXT, amount REAL NOT NULL, side TEXT,
  spender_id TEXT, spender_name TEXT, spender_kind TEXT, purpose TEXT);
CREATE INDEX IF NOT EXISTS idx_state_gifts_member ON state_gifts (bioguide_id, year);
CREATE INDEX IF NOT EXISTS idx_state_outside_member ON state_outside (bioguide_id, year);
"""


def iso(text):
    """'1/20/2000 12:00:00 AM' -> '2000-01-20', else None."""
    m = re.match(r"\s*(\d{1,2})/(\d{1,2})/(\d{4})", text or "")
    return f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}" if m else None


def year_of(text):
    m = re.search(r"/(\d{4})", text or "")
    return int(m.group(1)) if m else 0


def table(z, name):
    """One Cal-Access table as a text stream; the caller reads the header line, then splits only the lines it wants."""
    return io.TextIOWrapper(z.open(DATA + name + ".TSV"), encoding="utf-8", errors="replace", newline="")


def norm_words(text):
    """Lower case, accents folded, punctuation to spaces: for comparing the words of two names."""
    plain = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z]+", " ", plain)


def split_name(naml, namf):
    """Cover pages give a candidate's family and given names apart; spenders often write the whole name in one field
    ("Susan Rubio", "Dr. Akilah Weber", "Rubio, Susan"). Returns (family, given) either way."""
    naml, namf = TITLE.sub("", " ".join((naml or "").split())), TITLE.sub("", " ".join((namf or "").split()))
    if not namf and "," in naml:
        naml, namf = (x.strip() for x in naml.split(",", 1))
    elif not namf and " " in naml:
        parts = naml.split(" ")
        namf, naml = parts[0], " ".join(parts[1:])
    return naml, namf


def strip_credentials(text):
    """'Charles H. Cooley, D.D.S., M.S' -> ('Charles H. Cooley', True); credentials come off the end only, so a surname
    such as Do or Ng is never mistaken for one."""
    had = False
    while True:
        m = CREDENTIAL.search(text)
        if not m:
            return text.rstrip(" ,."), had
        text, had = text[:m.start()], True


def name_tokens(text):
    """The name's words with titles, suffixes, credentials and initials set aside."""
    text, _had = strip_credentials(text)
    return [t for t in re.findall(r"[A-Za-z][A-Za-z'\-]*", text) if norm(t) not in TITLE_WORDS | SUFFIX_WORDS and len(norm(t)) > 1]


def near(a, b):
    """Two spellings of one name (Carrillo / Carrilllo, Bennett / Benett)."""
    a, b = norm(a), norm(b)
    return bool(a and b) and (a == b or (min(len(a), len(b)) > 3 and difflib.SequenceMatcher(None, a, b).ratio() >= 0.8))


class People:
    """Tells a person's name from an organization's, using the file's own list of given names (built from the
    individual givers it read) beside the words an organization's name carries. Errs toward the person: a business
    named after its owner may be hidden, a person is never shown."""

    def __init__(self):
        self.given = collections.Counter()

    def common(self, token):
        return self.given[norm(token)] >= 5

    def shaped(self, text, need_given=True):
        """Two to four name words, no digits, no organization's word; the first word a given name the file knows
        (or, when need_given is off, any word: for the head of 'X dba Y' or 'X and Affiliated Entities')."""
        if re.search(r"[\d@#]", text) or STRONG_ORG.search(text):
            return False
        toks = name_tokens(text)
        if not 2 <= len(toks) <= 4:
            return False
        if need_given:
            first = self.common(toks[0]) or (len(toks) >= 3 and self.common(toks[1]) and len(toks[0]) <= 3)      # "J. Robert Smith"
            return first and (len(toks) == 2 or not WEAK_ORG.search(text))       # "Frank Church" is a person; "Foster Poultry Farms" is not
        return not WEAK_ORG.search(text)

    def is_person(self, text):
        """A person's name, a person's trust or estate, a professional, a sole proprietor, or a person and their businesses."""
        t = " ".join((text or "").split())
        if not t:
            return False
        if CAND_WORD.search(t) or PARTY_WORD.search(t) or re.search(r"\bfor\b", t, re.I):
            return False                                                       # "Kevin McCarthy for Congress" is a committee
        if ESTATE.search(t):
            return True
        if TRUST.search(t) and not TRUST_ORG.search(t) and not STRONG_ORG.search(t):
            return True                                                        # a family, living or personal trust
        if AFFILIATED.search(t):
            return self.shaped(AFFILIATED.sub("", t), need_given=False)
        if DBA.search(t):
            head = DBA.split(t)[0]
            return bool(name_tokens(head)) and self.shaped(head, need_given=False)
        bare, had = strip_credentials(t)
        if had and not STRONG_ORG.search(bare):
            return 1 <= len(name_tokens(bare)) <= 4                               # "Jaclynn Do MD", "Andrew L. Say, CPA", "Samrao, MD"
        if LAST_FIRST.match(t) and not STRONG_ORG.search(t):
            return True
        if PROFESSION.search(t):
            return self.shaped(PROFESSION.sub("", t), need_given=False)
        if TITLE.match(t) and not STRONG_ORG.search(t):
            return 2 <= len(name_tokens(t)) <= 4
        return self.shaped(t)

    def person_segment(self, text):
        """A person's name written beside a business in one registration: 'Buckeye Properties; Lyn Konheim',
        'Four Star Fruit Inc. and Joe Campbell', 'Christopher Neale, including aggregated contributions ...'."""
        for seg in re.split(r"[;/]|\s+(?:and|&|including|aka|c/o)\s+", " ".join((text or "").split()), flags=re.I):
            seg = seg.strip(" ,")
            if not seg:
                continue
            toks = name_tokens(seg)
            if self.is_person(seg) or (self.shaped(seg, need_given=False) and 2 <= len(toks) <= 3 and any(self.common(x) for x in toks)):
                return True
        return False

    def strip_contact(self, text):
        """'Amazon.com Services LLC(Andrea Fava)' -> 'Amazon.com Services LLC'; 'Golf Realty Fund - Robert OHill' -> 'Golf Realty Fund'.
        Only a tail that reads like a person's name comes off; '(FEC ID# C00651042)', '(GM PAC)', '(SCC)' stay."""
        t = re.sub(r"\(\s*\)", "", " ".join((text or "").split())).strip()
        for _ in range(2):
            m = TAIL_PAREN.search(t)
            if m and (not m.group(1).strip() or self.shaped(m.group(1), need_given=False) and 2 <= len(name_tokens(m.group(1))) <= 3):
                t = t[:m.start()].rstrip()
                continue
            m = TAIL_DASH.search(t)
            if m and self.shaped(m.group(1), need_given=False) and 2 <= len(name_tokens(m.group(1))) <= 3:
                t = t[:m.start()].rstrip()
                continue
            break
        return t


def purpose(d):
    """What a committee is, from its cover pages and its names: 'ballot', 'other office', 'general purpose', 'legislative' or 'unread'."""
    names = " | ".join(d["names"])
    main = d["names"].most_common(1)[0][0] if d["names"] else ""
    if BALLOT_WORD.search(names) or d["ballot"] or d["entity"]["BMC"] or d["ctype"]["B"]:
        return "ballot"
    if OTHER_OFFICE_WORD.search(main) and not SEAT_STRONG.search(main):
        return "other office"                                                  # "... for Long Beach City Council 2014 Officeholder Account"
    n460 = d["forms"]["F460"]
    codes = collections.Counter()
    for (o, _dist, _sh), n in d["offices"].items():
        codes[o or "-"] += n
    seat_pages = codes["ASM"] + codes["SEN"]
    other_pages = sum(n for o, n in codes.items() if o not in ("ASM", "SEN", "-"))
    if other_pages > seat_pages and not SEAT_STRONG.search(main):
        return "other office"                                                  # "ROBERT GARCIA OFFICEHOLDER ACCOUNT" whose covers say Mayor
    if SEAT_WORD.search(main):
        return "legislative"
    if d["ctype"]["G"] * 2 > n460 and not seat_pages:
        return "general purpose"
    if seat_pages and (d["entity"]["CTL"] + d["entity"]["CAO"]) * 2 >= n460:
        return "legislative"
    if not d["cands"] and not seat_pages:
        return "unread"
    if seat_pages and d["ctype"]["G"] * 2 > n460:
        return "general purpose"
    return "legislative" if seat_pages and SEAT_WORD.search(names) else "unread"


def chamber_of(d, fallback):
    codes = collections.Counter()
    for (o, _dist, _sh), n in d["offices"].items():
        if o in OFFICE:
            codes[OFFICE[o]] += n
    if codes:
        return codes.most_common(1)[0][0]
    name = d["names"].most_common(1)[0][0] if d["names"] else ""
    if re.search(r"\bsenat", name, re.I):
        return "Senate"
    if re.search(r"\bassembly", name, re.I):
        return "House"
    return fallback


def kind_by_name(name, entity, known_cand):
    """A committee giver's kind from its name and code: another candidate's committee, a party unit, else a
    political committee."""
    n = name or ""
    if known_cand or re.search(r"\bfor\b.{0,40}\bcentral committee\b", n, re.I):
        return "cand"
    if entity == "PTY" or PARTY_WORD.search(n):
        return "party"
    if CAND_WORD.search(n) and not re.search(r"\bpac\b", n, re.I):
        return "cand"
    return "pcf"


def kind_of_other(name):
    """An 'other' giver: a business, union, tribe or association, unless its name says it is a committee or a party."""
    n = name or ""
    if PARTY_WORD.search(n) and not re.search(r"\bfor\b.{0,40}\bcentral committee\b", n, re.I):
        return "party"
    if re.search(r"\bpac\b|political action committee", n, re.I):
        return "pcf"
    if CAND_WORD.search(n):
        return "cand"
    if re.search(r"\b(committee|fund)\b", n, re.I) and not re.search(r"\b(inc|llc|corp|company|association|union|local|family)\b", n, re.I):
        return "pcf"
    return "org"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", required=True)
    ap.add_argument("--cache-dir", default="states_cache")
    ap.add_argument("--since", type=int, default=2015, help="first year to keep (the 2016 cycle begins in January 2015)")
    args = ap.parse_args()
    t0 = time.time()
    folder = os.path.join(args.cache_dir, "ca_calaccess")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, "dbwebexport.zip")
    if net.download(URL, path, 3600):
        print(f"    fetched dbwebexport.zip ({os.path.getsize(path) / 1e6:,.0f} MB)")
    z = zipfile.ZipFile(path)

    con = sqlite3.connect(args.db)
    con.executescript(SCHEMA)
    if not con.execute("SELECT 1 FROM sqlite_master WHERE name = 'legislators'").fetchone():
        sys.exit("No members yet. Run the people stage first.")
    members = {}
    for bio, first, last, full, others, district, chamber in con.execute("SELECT bioguide_id, first_name, last_name, official_full, other_names, district, chamber FROM legislators WHERE is_current = 1"):
        names = [o.strip() for o in (others or "").split(";") if o.strip()]
        givens = {first, (full or "").split(" ")[0]} | {o.split(",")[-1].strip().split(" ")[0] if "," in o else o.split(" ")[0] for o in names}
        fams = families_of(last) | {norm((full or "").split(" ")[-1])}
        for o in names:                                                      # "Weber, A." / "Elizabeth Ortega-Toro" / "Tasha Boerner Horvath"
            if "," in o:
                fams |= families_of(o.split(",")[0])
            elif " " in o and "." not in o:
                fams |= families_of(o.split(" ", 1)[1])
        members[bio] = {"family": {f for f in fams if f}, "given": {g for g in givens if g and len(norm(g)) > 1 and "." not in g}, "name": full,
                        "district": str(district or "").lstrip("0"), "chamber": chamber}
    terms = collections.defaultdict(set)
    for bio, typ, district in con.execute("SELECT bioguide_id, type, district FROM member_terms"):
        terms[bio].add(({"rep": "House", "sen": "Senate"}.get(typ, typ), str(district or "").lstrip("0")))
    for bio, m in members.items():
        terms[bio].add((m["chamber"], m["district"]))
    served = {bio: {c for c, _d in t} for bio, t in terms.items()}

    def name_fits(naml, namf, bio):
        """The candidate a committee names is this member, allowing for a misspelling on the Secretary's own record."""
        naml, namf = split_name(naml, namf)
        fams, givs = families_of(naml), givens_of(namf)
        m = members[bio]
        family_ok = bool(fams & m["family"]) or any(near(f, g) for f in fams for g in m["family"])
        given_ok = any(given_fits(c, g) or near(c, g) for c in givs for g in m["given"]) or any(initials_fit(givs, g) for g in m["given"])
        return family_ok and given_ok

    def fits(naml, namf, chamber, dist, chambers=None):
        """Sitting members a candidate's name fits: family name, a compatible given name, a chamber served (or one of
        the chambers given); the district settles a tie."""
        chambers = chambers or served
        naml, namf = split_name(naml, namf)
        fams, givs = families_of(naml), givens_of(namf)
        same = [bio for bio, m in members.items() if fams & m["family"] and chamber in chambers.get(bio, ())]
        out = [bio for bio in same if any(given_fits(c, g) for c in givs for g in members[bio]["given"]) or any(initials_fit(givs, g) for g in members[bio]["given"])]
        if len(out) > 1 and dist:
            narrowed = [bio for bio in out if (chamber, dist) in terms[bio]]
            if len(narrowed) == 1:
                out = narrowed
        return out

    # -- 1. every campaign statement's cover page: which filing is which (and its latest amendment), and what each committee is
    filings, cmte, periods = {}, {}, collections.defaultdict(list)
    with table(z, "CVR_CAMPAIGN_DISCLOSURE_CD") as fh:
        head = fh.readline().rstrip("\r\n").split("\t")
        ix = {c: i for i, c in enumerate(head)}
        i_fid, i_am, i_form, i_filer, i_naml, i_ent, i_cand, i_candf, i_off, i_dist, i_sh, i_from, i_thru, i_rpt, i_ctype, i_bal, i_balnum = (
            ix["FILING_ID"], ix["AMEND_ID"], ix["FORM_TYPE"], ix["FILER_ID"], ix["FILER_NAML"], ix["ENTITY_CD"], ix["CAND_NAML"], ix["CAND_NAMF"],
            ix["OFFICE_CD"], ix["DIST_NO"], ix["OFF_S_H_CD"], ix["FROM_DATE"], ix["THRU_DATE"], ix["RPT_DATE"], ix["CMTTE_TYPE"], ix["BAL_NAME"], ix["BAL_NUM"])
        for line in fh:
            f = line.rstrip("\r\n").split("\t")
            if len(f) < len(head):
                continue
            am, form, filer = int(f[i_am] or 0), f[i_form], f[i_filer]
            office = f[i_off].strip()
            prev = filings.get(f[i_fid])
            if prev is None or prev[0] < am:
                filings[f[i_fid]] = (am, form, filer, year_of(f[i_thru]) or year_of(f[i_rpt]), office)
                if prev is None and form in ("F460", "F461"):
                    periods[(filer, form, iso(f[i_from]), iso(f[i_thru]))].append(f[i_fid])
            d = cmte.get(filer)
            if d is None:
                d = cmte[filer] = {"names": collections.Counter(), "cands": collections.Counter(), "offices": collections.Counter(), "entity": collections.Counter(),
                                   "forms": collections.Counter(), "ctype": collections.Counter(), "years": set(), "ballot": False}
            d["names"][" ".join(f[i_naml].split())] += 1
            d["entity"][f[i_ent].strip()] += 1
            d["forms"][form] += 1
            d["years"].add(year_of(f[i_rpt]))
            if form == "F460":
                d["ctype"][f[i_ctype].strip()] += 1
                if f[i_bal].strip() or f[i_balnum].strip():
                    d["ballot"] = True
                if f[i_cand].strip():
                    d["cands"][(" ".join(f[i_cand].split()), " ".join(f[i_candf].split()))] += 1
                d["offices"][(office, f[i_dist].strip().lstrip("0"), f[i_sh].strip())] += 1
    # a statement filed twice under two filing numbers (same filer, form and period) counts once: the later filing stands
    twice = set()
    for key, ids in periods.items():
        if len(ids) > 1 and key[2] and key[3]:
            keep = max(ids, key=int)
            twice |= {i for i in ids if i != keep}
    print(f"    {len(filings):,} campaign statements from {len(cmte):,} filers indexed; {len(twice):,} filed twice under two numbers ({time.time() - t0:.0f} s)", flush=True)

    # -- 2. the Secretary's own links: which candidate record controls which committee
    cand_of, cmtes_of = collections.defaultdict(set), collections.defaultdict(set)
    with table(z, "FILER_LINKS_CD") as fh:
        head = fh.readline().rstrip("\r\n").split("\t")
        ix = {c: i for i, c in enumerate(head)}
        for line in fh:
            f = line.rstrip("\r\n").split("\t")
            if len(f) >= len(head) and f[ix["LINK_TYPE"]] == "12011":
                cand_of[f[ix["FILER_ID_B"]]].add(f[ix["FILER_ID_A"]])
                cmtes_of[f[ix["FILER_ID_A"]]].add(f[ix["FILER_ID_B"]])

    # -- 3. match: a committee whose Form 460 cover pages name a candidate for the Assembly or Senate
    by_name, unsure, differs = {}, [], []
    for fid, d in cmte.items():
        if not d["cands"] or max(d["years"]) < args.since or purpose(d) == "ballot":
            continue
        seats = {(OFFICE[o], dist) for (o, dist, _sh) in d["offices"] if o in OFFICE}
        if not seats:
            continue
        (naml, namf), _n = d["cands"].most_common(1)[0]
        hits = {}
        for chamber, dist in seats:
            for bio in fits(naml, namf, chamber, dist):
                hits.setdefault(bio, set()).add((chamber, dist))
        if len(hits) == 1:
            bio, at = next(iter(hits.items()))
            by_name[fid] = bio
            if not any(s in terms[bio] for s in at):
                differs.append(f"{d['names'].most_common(1)[0][0]} ({', '.join(c + ' ' + x for c, x in sorted(at))}) -> {members[bio]['name']}")
        elif len(hits) > 1:
            unsure.append(f"{d['names'].most_common(1)[0][0]} ({naml}, {namf}): fits {', '.join(members[b]['name'] for b in hits)}")
    # every committee of a candidate record that has a matched committee belongs to the same member, provided the
    # candidate it names (if any) is that member: Cal-Access has filed two people under one record before
    record_of = collections.defaultdict(set)
    for fid, bio in by_name.items():
        for c in cand_of.get(fid, ()):
            record_of[c].add(bio)
    conflicts = [f"candidate record {c}: {', '.join(members[b]['name'] for b in bios)}" for c, bios in record_of.items() if len(bios) > 1]
    candidates, shared = dict(by_name), []
    for c, bios in record_of.items():
        if len(bios) != 1:
            continue
        bio = next(iter(bios))
        for fid in cmtes_of[c]:
            if fid in candidates or fid not in cmte or max(cmte[fid]["years"]) < args.since:
                continue
            d = cmte[fid]
            if d["cands"]:
                (naml, namf), _n = d["cands"].most_common(1)[0]
                if not name_fits(naml, namf, bio):
                    shared.append(f"{d['names'].most_common(1)[0][0]} names {namf} {naml}, not {members[bio]['name']}")
                    continue
            candidates[fid] = bio
    whose, left_out = {}, collections.defaultdict(list)
    for fid, bio in candidates.items():
        d = cmte[fid]
        p = purpose(d)
        if p == "legislative":
            whose[fid] = (bio, chamber_of(d, members[bio]["chamber"]), d["names"].most_common(1)[0][0])
        else:
            codes = ",".join(sorted({o for (o, _d, _s) in d["offices"]} - {""})) or "no office"
            left_out[p].append(f"{d['names'].most_common(1)[0][0]} ({codes}) of {members[bio]['name']}")
    matched = {b for b, _c, _n in whose.values()}
    print(f"    {len(by_name):,} committees matched by the candidate named on their cover pages, {len(candidates) - len(by_name):,} more through the Secretary's candidate records; "
          f"{len(whose):,} read as committees for the seat, for {len(matched)} of {len(members)} sitting members")
    mine_of = collections.defaultdict(set)                                     # member -> every committee of theirs, kept or left out
    for fid, bio in candidates.items():
        mine_of[bio].add(fid)
    # committees Cal-Access shows as candidate-controlled (any office): a gift from one of these is another candidate's money
    cand_cmtes = set(whose)
    for fid, d in cmte.items():
        n460 = d["forms"]["F460"]
        if n460 and d["cands"] and sum(d["cands"].values()) * 2 >= n460 and purpose(d) not in ("ballot", "general purpose") \
                and not PARTY_WORD.search(d["names"].most_common(1)[0][0]):
            cand_cmtes.add(fid)
    major_donor = {fid for fid, d in cmte.items() if d["entity"] and d["entity"].most_common(1)[0][0] in ("MDI", "IND")}
    registered = lambda fid: cmte[fid]["names"].most_common(1)[0][0] if fid in cmte and cmte[fid]["names"] else ""

    # -- 4. the statements to read: every Form 460 of those committees whose own cover page names the seat (an officeholder
    #       account or legal defense fund counts whole), latest amendment only, each period once
    wanted, off_seat = {}, collections.Counter()
    for fid, (am, form, filer, _yr, office) in filings.items():
        if form != "F460" or filer not in whose or fid in twice:
            continue
        bio, chamber, name = whose[filer]
        if office in OFFICE:
            wanted[fid] = (bio, OFFICE[office])
        elif office in ("", "OTH") or re.search(r"officeholder|legal defense", name, re.I):
            wanted[fid] = (bio, chamber)                                       # no office, or the catch-all code: a mis-keyed field, not another race
        else:
            off_seat[f"{name} ({office})"] += 1
    people = People()
    own_names = {bio: (m["family"], m["given"]) for bio, m in members.items()}
    gifts, sources, kinds_seen = [], {}, collections.defaultdict(collections.Counter)
    held = []                                                                  # rows to judge once the file's given names are known
    n_rows = n_kept = n_short = n_memo = n_stale = n_transfer = n_forgiven = 0

    def add_source(bio, filer, chamber, year, source, amount):
        s = sources.setdefault((bio, filer, chamber, year, source), [0.0, 0])
        s[0] += amount
        s[1] += 1

    with table(z, "RCPT_CD") as fh:
        head = fh.readline().rstrip("\r\n").split("\t")
        ix = {c: i for i, c in enumerate(head)}
        i_am, i_form, i_ent, i_naml, i_namf, i_date, i_amt, i_cmte, i_memo, i_tran, i_icmte, i_inaml, i_inamf = (
            ix["AMEND_ID"], ix["FORM_TYPE"], ix["ENTITY_CD"], ix["CTRIB_NAML"], ix["CTRIB_NAMF"], ix["RCPT_DATE"], ix["AMOUNT"], ix["CMTE_ID"], ix["MEMO_CODE"],
            ix["TRAN_TYPE"], ix["INTR_CMTEID"], ix["INTR_NAML"], ix["INTR_NAMF"])
        for line in fh:
            n_rows += 1
            fid = line[:line.find("\t")]
            w = wanted.get(fid)
            if w is None:
                continue
            f = line.rstrip("\r\n").split("\t")
            if len(f) < len(head):
                n_short += 1
                continue
            if int(f[i_am] or 0) != filings[fid][0]:
                n_stale += 1
                continue
            if f[i_form] not in ("A", "C"):
                continue
            if f[i_memo].strip():
                n_memo += 1
                continue
            date = iso(f[i_date])
            year = int(date[:4]) if date else 0
            if year < args.since:
                continue
            try:
                amount = float(f[i_amt] or 0)
            except ValueError:
                continue
            if not amount:
                continue
            tran = f[i_tran].strip().upper()
            if tran == "F":
                n_forgiven += 1                                                # a forgiven loan: counted when it was received
                continue
            bio, chamber = w
            filer = filings[fid][2]
            n_kept += 1
            entity, naml, namf = f[i_ent].strip(), " ".join(f[i_naml].split()), " ".join(f[i_namf].split())
            in_kind = 1 if f[i_form] == "C" else 0
            if tran == "X" and (f[i_icmte].strip() or f[i_inaml].strip()):
                # a transfer: Cal-Access attributes it to the original givers, but the money came from the committee it left
                n_transfer += 1
                tid, tname = f[i_icmte].strip(), " ".join((f[i_inamf] + " " + f[i_inaml]).split())
                if tid.isdigit() and registered(tid):
                    tname = registered(tid)
                did = tid if tid.isdigit() else "n-" + (norm(tname)[:48] or "unnamed")
                kind = "cand" if (tid in cand_cmtes or not tid.isdigit()) else kind_by_name(tname, "COM", False)
                kinds_seen[did][kind] += 1
                gifts.append([bio, filer, chamber, year, date, amount, did, tname, kind, in_kind])
                add_source(bio, filer, chamber, year, kind, amount)
                continue
            if entity == "IND":
                fam, giv = families_of(naml), givens_of(namf)
                source = "self" if (fam & own_names[bio][0] and any(given_fits(c, g) for c in giv for g in own_names[bio][1])) else "people"
                if giv:
                    people.given[norm(giv[0])] += 1                             # the file's own list of given names
                add_source(bio, filer, chamber, year, source, amount)
            elif entity in ("COM", "RCP", "SCC", "PTY", "OTH"):
                held.append((bio, filer, chamber, year, date, amount, entity, naml, namf, f[i_cmte].strip(), in_kind))
            else:
                add_source(bio, filer, chamber, year, "other", amount)          # no entity code: the file does not say what kind of giver, so no name
            if n_rows % 5_000_000 == 0:
                print(f"    {n_rows:,} receipt rows read, {n_kept:,} kept ({time.time() - t0:.0f} s)", flush=True)

    # judge the committee- and other-coded rows now that the file's given names are known
    set_aside, n_person = collections.Counter(), collections.Counter()
    for bio, filer, chamber, year, date, amount, entity, naml, namf, cmte_id, in_kind in held:
        written = people.strip_contact((namf + " " + naml).strip() if namf else naml)
        if entity == "OTH" and namf and not STRONG_ORG.search(namf + " " + naml):
            add_source(bio, filer, chamber, year, "people", amount)              # filed as "other" but with a given name of its own
            n_person["other, with a given name"] += 1
            set_aside[written] += amount
            continue
        did = name = kind = None
        if cmte_id.isdigit() and cmte_id != filer:
            reg = registered(cmte_id)
            shared_word = bool({t for t in re.findall(r"[a-z]{4,}", norm_words(reg))} & {t for t in re.findall(r"[a-z]{4,}", norm_words(written))})
            if reg and (shared_word or not written):
                did, name = cmte_id, reg
                if cmte_id in major_donor:
                    if people.is_person(reg) or people.person_segment(reg):
                        add_source(bio, filer, chamber, year, "people", amount)
                        n_person["a major donor registered as a person"] += 1
                        set_aside[reg] += amount
                        continue
                    kind = "org"                                                 # a business or tribe registered as a major donor
                else:
                    kind = kind_by_name(reg, entity, cmte_id in cand_cmtes)
        if did is None:
            if people.is_person(written):
                add_source(bio, filer, chamber, year, "people", amount)
                n_person["written like a person's name"] += 1
                set_aside[written] += amount
                continue
            did, name = "n-" + (norm(written)[:48] or "unnamed"), written
            kind = kind_of_other(written) if entity == "OTH" else kind_by_name(written, entity, False)
        kinds_seen[did][kind] += 1
        gifts.append([bio, filer, chamber, year, date, amount, did, name, kind, in_kind])
        add_source(bio, filer, chamber, year, kind, amount)
    for g in gifts:
        g[8] = kinds_seen[g[6]].most_common(1)[0][0]
    print(f"    {n_rows:,} receipt rows read; {n_kept:,} gifts to the matched committees since {args.since} "
          f"({n_stale:,} on superseded statements, {n_memo:,} memo lines, {n_forgiven:,} forgiven loans and {n_short:,} broken rows left out; "
          f"{n_transfer:,} transfers recorded as the committee's the money left; {time.time() - t0:.0f} s)")
    print(f"    {sum(n_person.values()):,} rows filed as a committee or other but read as a person (${sum(set_aside.values()) / 1e6:,.2f}M, {len(set_aside)} names) counted with people and not named: "
          + "; ".join(f"{k} {v:,}" for k, v in n_person.most_common()))
    print("    the largest of those, to read (a business named after its owner may be among them; the log is not the site): "
          + "; ".join(f"{n} ${a:,.0f}" for n, a in set_aside.most_common(15)))

    # -- 5. what the itemized schedules leave out: gifts under $100 as one sum (Schedule A, line 2) and loans received (Schedule B)
    n_unit = 0
    with table(z, "SMRY_CD") as fh:
        head = fh.readline().rstrip("\r\n").split("\t")
        ix = {c: i for i, c in enumerate(head)}
        for line in fh:
            fid = line[:line.find("\t")]
            w = wanted.get(fid)
            if w is None:
                continue
            f = line.rstrip("\r\n").split("\t")
            if len(f) < len(head) or int(f[ix["AMEND_ID"]] or 0) != filings[fid][0] or f[ix["FORM_TYPE"]] != "A" or f[ix["LINE_ITEM"]].strip() != "2":
                continue
            try:
                amount = float(f[ix["AMOUNT_A"]] or 0)
            except ValueError:
                continue
            year = filings[fid][3]
            if not amount or year < args.since:
                continue
            add_source(w[0], filings[fid][2], w[1], year, "other", amount)
            n_unit += 1
    n_loans = n_own_loans = 0
    with table(z, "LOAN_CD") as fh:
        head = fh.readline().rstrip("\r\n").split("\t")
        ix = {c: i for i, c in enumerate(head)}
        for line in fh:
            fid = line[:line.find("\t")]
            w = wanted.get(fid)
            if w is None:
                continue
            f = line.rstrip("\r\n").split("\t")
            if len(f) < len(head) or int(f[ix["AMEND_ID"]] or 0) != filings[fid][0] or f[ix["FORM_TYPE"]] != "B1" or f[ix["MEMO_CODE"]].strip():
                continue
            try:
                amount = float(f[ix["LOAN_AMT1"]] or 0)
            except ValueError:
                continue
            date = iso(f[ix["LOAN_DATE1"]])
            year = int(date[:4]) if date else filings[fid][3]
            if amount <= 0 or year < args.since:
                continue
            bio, chamber = w
            lender = f[ix["CMTE_ID"]].strip()
            if lender.isdigit() and lender in whose and whose[lender][0] == bio:
                # a loan from the member's own other committee: that committee's money moving, not a loan from outside
                gifts.append([bio, filings[fid][2], chamber, year, date, amount, lender, registered(lender) or whose[lender][2], "cand", 0])
                add_source(bio, filings[fid][2], chamber, year, "cand", amount)
                n_own_loans += 1
            else:
                add_source(bio, filings[fid][2], chamber, year, "loans", amount)
                n_loans += 1
    print(f"    {n_unit:,} statements' under-$100 sums, {n_loans:,} loans and {n_own_loans:,} loans from the member's own committee added ({time.time() - t0:.0f} s)")

    # -- 6. outside spending: Schedule D of Form 460 and Part 5 of Form 461, independent expenditures naming an Assembly or Senate candidate
    served_ie = {bio: set(ch) for bio, ch in served.items()}
    for fid, (bio, chamber, _n) in whose.items():
        served_ie.setdefault(bio, set()).add(chamber)                          # a member's race for the other chamber counts too
    outside, n_ie, n_ie_kept, unmatched_ie, side_missing, spender_kind = [], 0, 0, collections.Counter(), 0, {}
    fit_cache = {}
    with table(z, "EXPN_CD") as fh:
        head = fh.readline().rstrip("\r\n").split("\t")
        ix = {c: i for i, c in enumerate(head)}
        i_am, i_form, i_code, i_off, i_dist, i_cand, i_candf, i_sup, i_amt, i_date, i_dscr, i_memo = (
            ix["AMEND_ID"], ix["FORM_TYPE"], ix["EXPN_CODE"], ix["OFFICE_CD"], ix["DIST_NO"], ix["CAND_NAML"], ix["CAND_NAMF"], ix["SUP_OPP_CD"],
            ix["AMOUNT"], ix["EXPN_DATE"], ix["EXPN_DSCR"], ix["MEMO_CODE"])
        for line in fh:
            if "\tASM\t" not in line and "\tSEN\t" not in line:
                continue
            f = line.rstrip("\r\n").split("\t")
            if len(f) < len(head) or f[i_off] not in OFFICE:
                continue
            fid = f[0]
            rec = filings.get(fid)
            if rec is None or int(f[i_am] or 0) != rec[0] or fid in twice:
                continue
            form, code = f[i_form], f[i_code].strip().upper()
            if not ((form == "D" or form == "F461P5") and code == "IND"):
                continue
            if f[i_memo].strip():
                continue
            n_ie += 1
            date = iso(f[i_date])
            year = int(date[:4]) if date else rec[3]
            if year < args.since:
                continue
            try:
                amount = float(f[i_amt] or 0)
            except ValueError:
                continue
            if not amount:
                continue
            side = {"S": "for", "O": "against"}.get(f[i_sup].strip().upper())
            if not side:
                side_missing += 1
                continue
            chamber, dist = OFFICE[f[i_off]], f[i_dist].strip().lstrip("0")
            key = (f[i_cand].strip().lower(), f[i_candf].strip().lower(), chamber, dist)
            if key not in fit_cache:
                fit_cache[key] = fits(f[i_cand], f[i_candf], chamber, dist, served_ie)
            hit = fit_cache[key]
            if len(hit) != 1:
                unmatched_ie[("ambiguous" if hit else "not a sitting member")] += 1
                continue
            bio = hit[0]
            spender = rec[2]
            if spender in mine_of[bio]:
                continue                                                       # the member's own committee: not outside money
            if spender not in spender_kind:
                sname = registered(spender)
                if spender in cand_cmtes:
                    kind = "cand"
                elif PARTY_WORD.search(sname):
                    kind = "party"
                elif rec[1] == "F461" or spender in major_donor:
                    kind = "unnamed" if (people.is_person(sname) or people.person_segment(sname) or not (STRONG_ORG.search(sname) or WEAK_ORG.search(sname))) else "org"
                else:
                    kind = "pcf"
                spender_kind[spender] = (kind, sname)
            kind, sname = spender_kind[spender]
            sid, sname2 = (UNNAMED_ID, UNNAMED_NAME) if kind == "unnamed" else (spender, sname)
            outside.append((bio, spender, year, date, amount, side, sid, sname2, kind, " ".join(f[i_dscr].split())[:200]))
            n_ie_kept += 1
    print(f"    {n_ie:,} independent-expenditure lines name an Assembly or Senate candidate; {n_ie_kept:,} are for or against a sitting member since {args.since} "
          f"({unmatched_ie['not a sitting member']:,} name someone else, {unmatched_ie['ambiguous']:,} fit more than one member and were left out, {side_missing:,} say neither support nor oppose; {time.time() - t0:.0f} s)")

    with con:
        for t in ("state_committees", "state_gifts", "state_sources", "state_outside"):
            con.execute(f"DELETE FROM {t}")
        con.executemany("INSERT INTO state_committees VALUES (?,?,?,?)", [(fid, name, chamber, bio) for fid, (bio, chamber, name) in whose.items()])
        con.executemany("INSERT INTO state_gifts (bioguide_id, committee, office, year, date, amount, donor_id, donor_name, donor_kind, in_kind) VALUES (?,?,?,?,?,?,?,?,?,?)", gifts)
        con.executemany("INSERT INTO state_sources VALUES (?,?,?,?,?,?,?)", [(*k, round(v[0], 2), v[1]) for k, v in sources.items() if v[1] > 0 or abs(v[0]) >= 0.005])
        con.executemany("INSERT INTO state_outside (bioguide_id, committee, year, date, amount, side, spender_id, spender_name, spender_kind, purpose) VALUES (?,?,?,?,?,?,?,?,?,?)", outside)
    by_source = dict(con.execute("SELECT source, ROUND(SUM(amount)) FROM state_sources GROUP BY 1"))
    print(f"    Stored: {len(gifts):,} gifts from organizations (${sum(g[5] for g in gifts) / 1e6:,.1f}M); totals by source: "
          + ", ".join(f"{k} ${v / 1e6:,.1f}M" for k, v in sorted(by_source.items(), key=lambda kv: -kv[1])))
    by_side = dict(con.execute("SELECT side, ROUND(SUM(amount)) FROM state_outside GROUP BY 1"))
    unnamed = con.execute("SELECT ROUND(COALESCE(SUM(amount), 0)) FROM state_outside WHERE spender_kind = 'unnamed'").fetchone()[0]
    print(f"    Outside spending: ${by_side.get('for', 0) / 1e6:,.1f}M for, ${by_side.get('against', 0) / 1e6:,.1f}M against, from {con.execute('SELECT COUNT(DISTINCT spender_id) FROM state_outside').fetchone()[0]:,} spenders; "
          f"${unnamed / 1e6:,.2f}M of it by Form 461 filers not named here")
    top = con.execute("SELECT spender_name, spender_kind, ROUND(SUM(amount)) FROM state_outside GROUP BY spender_id ORDER BY 3 DESC LIMIT 5").fetchall()
    print("    biggest outside spenders: " + "; ".join(f"{n[:60]} ({k}) ${a / 1e6:,.1f}M" for n, k, a in top))
    top = con.execute("SELECT donor_name, donor_kind, ROUND(SUM(amount)) FROM state_gifts GROUP BY donor_id ORDER BY 3 DESC LIMIT 5").fetchall()
    print("    biggest named givers: " + "; ".join(f"{n[:60]} ({k}) ${a / 1e6:,.1f}M" for n, k, a in top))
    if off_seat:
        print(f"    statements of a seat committee whose own cover page names another office, left out ({sum(off_seat.values())}): "
              + "; ".join(f"{k} x{v}" for k, v in off_seat.most_common(8)) + (" ..." if len(off_seat) > 8 else ""))
    if differs:
        print(f"    matched by name though the district on the cover page is not one the member has held ({len(differs)}): " + "; ".join(differs[:12]) + (" ..." if len(differs) > 12 else ""))
    for p, items in sorted(left_out.items()):
        print(f"    left out as {p} ({len(items)}): " + "; ".join(items[:10]) + (" ..." if len(items) > 10 else ""))
    if shared:
        print(f"    left out, the Secretary's record names someone else ({len(shared)}): " + "; ".join(shared[:6]) + (" ..." if len(shared) > 6 else ""))
    if conflicts:
        print(f"    CHECK candidate records tied to two members ({len(conflicts)}): " + "; ".join(conflicts))
    if unsure:
        print(f"    left out, more than one member fits ({len(unsure)}): " + "; ".join(unsure[:8]) + (" ..." if len(unsure) > 8 else ""))
    unmatched = [m["name"] for bio, m in members.items() if bio not in matched]
    if unmatched:
        print(f"    sitting members with no committee matched ({len(unmatched)}): " + ", ".join(sorted(unmatched)[:24]) + (" ..." if len(unmatched) > 24 else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
