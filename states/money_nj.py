#!/usr/bin/env python3
"""
states/money_nj.py
==================
New Jersey campaign money, from the Election Law Enforcement Commission's public reports and data search system
(njelecefilesearch.com, the Commission's own search site). The Commission no longer publishes a bulk file; its search
pages are fed by a few JSON calls that answer a plain request, and this loader asks them the way the pages do: one
call for the register of every State Senate and General Assembly candidacy, one for every joint candidates committee,
and one call per office and election year for the contribution rows. Everything is kept in states_cache/nj_elec/ and
asked again after a month.

What a row carries: the account it went to (candidate, office, legislative district, party, election year and type),
the giver's name, the Commission's own code for what kind of giver it is (individual, business, union, PACs of
several kinds, party committee, legislative leadership committee, candidate committee ...), the kind of receipt
(monetary, in-kind, currency, loan, adjustment, interest ...), the date and the amount.

The same rule as everywhere on the site. Organizations are named: political committees and funds, party and
legislative leadership committees, other candidates' committees, and the businesses and unions New Jersey lets give
directly. People are not named: every gift from an individual goes into a yearly total, and the name on that row is
never written to the database; a gift from the candidate is the candidate's own. A giver the campaign filed with no
kind ("not provided") is read from its name, and counted with people when the name looks like a person's.

Joint candidates committees. New Jersey's legislative candidates raise much of their money through a committee formed
by a district's running mates (a senator and two Assembly members of one party), and the Commission files those as
committees of their own, in the district, named for the candidates ("SARLO SCHAER & CALABRESE"). This loader finds
the candidates a joint committee was formed for by the family names in its title, checked against the Commission's
register of that district's candidates of that party and election, and divides every gift equally among them; each
sitting member's share is stored under the joint committee, so the page can show it as coming through that committee.
A member's own candidate committee giving to their joint committee, or the joint committee passing money to the
member's own account, is the member's own money moving, and is reported as "moved in".

No outside spending is loaded for New Jersey: the Commission's expenditure records name the payee and purpose of
what a committee spent, not the candidate it spent for or against, and its independent expenditure reports are PDFs.

  state_committees   each account read as the member's: their own candidacies, and each joint committee they were in
  state_gifts        every gift from an organization to one of those accounts (the member's share, for a joint committee)
  state_sources      yearly totals by source (people, committees, party, other candidates, businesses, unions,
                     other organizations, own money, loans, other)
  state_outside      empty for New Jersey (see above)

    python -m states.money_nj --db state_nj.sqlite --since 2015
"""

import argparse
import collections
import datetime as dt
import json
import os
import re
import sqlite3
import sys
import time
import urllib.parse
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from states import net                                               # noqa: E402
from states.money_mn import norm, given_fits                         # noqa: E402
from states.money_tx import families_of, initials_fit                # noqa: E402
from states.money_ca import People, STRONG_ORG, CAND_WORD, name_tokens   # noqa: E402

BASE = "https://www.njelecefilesearch.com"
OFFICE = {"1": "Senate", "2": "House"}                # the roster files the General Assembly as "House", as every state database does
PARTY = {"DEMOCRAT": "D", "REPUBLICAN": "R", "INDEPENDENT": "I", "1": "D", "2": "R", "3": "I"}
DISTRICT = re.compile(r"^\s*(\d+)(?:ST|ND|RD|TH) LEGISLATIVE DISTRICT\s*$")
ELECTION = {"P": "primary", "G": "general", "S": "special", "R": "runoff", "D": "runoff"}
MAX_AGE_DAYS = 30

# The Commission's own giver codes (its search page lists them) and the kinds this site names. Individuals are never
# named; interest, miscellaneous lines, public solicitation and public financing are totals only.
KIND = {"B": "biz", "H": "union", "C": "party", "R": "party", "Q": "cand", "D": "cand",
        "E": "pcf", "F": "pcf", "G": "pcf", "I": "pcf", "J": "pcf", "V": "pcf", "W": "pcf", "X": "pcf", "O": "pcf", "Z": "pcf"}
PERSON_CODES = {"A"}
OTHER_CODES = {"K", "L", "N", "S", "T", "U", "M"}
PARTY_WORD = re.compile(r"\b(democrat\w*|republican\w*|gop|dems?|conservative party|libertarian\w*|green party|working families)\b", re.I)
LEADERSHIP = re.compile(r"\b(assembly|senate) (democratic |republican )?(campaign committee|majority|victory)\b|\bassembly campaign committee\b", re.I)
PAC_WORD = re.compile(r"\bpac\b|political action|political (committee|cmte)|continuing political|\bcpc\b|\bpec\b|\bfund\b|\bcoalition\b|\balliance\b|\bcommittee\b|\bcmte\b", re.I)
LUMP = re.compile(r"\b(contributions?|donations?|receipts?)\b.*\b(under|less than|below|and under|or less)\b|\bunder \$?\d|\bless than \$?\d|\blump\b|unitemized|un-itemized|anonymous|no name|not listed|\bonline\b.*\bdonat|fundrais|\bmisc\b|miscellaneous", re.I)
OWN_WORD = re.compile(r"\bfor\b|friends of|election fund|committee to elect|\bteam\b|\bre-?elect\b|\bcampaign\b", re.I)
CORP = re.compile(r"\b(corp(oration)?|inc(orporated)?|llc|l\.l\.c\.?|ltd|limited|company|co\.|companies|pllc|lp|llp|pa|pc|dba)\b", re.I)
STOP = {"for", "of", "the", "and", "friends", "election", "fund", "committee", "cmte", "to", "elect", "assembly", "senate", "senator", "state",
        "district", "ld", "team", "democrats", "democrat", "democratic", "republicans", "republican", "gop", "campaign", "re", "reelect", "council",
        "mayor", "freeholder", "commissioner", "county", "township", "twp", "boro", "borough", "city", "citizens", "efo", "in", "a", "an", "jr", "sr", "ii", "iii"}
CONT_COLS = ["CONTRIBUTOR", "STREET1", "EMP_NAME", "EMP_STREET1", "OccupationName", "CAND_NAME", "ContributorType", "ContributionType", "CONT_DATE", "CONT_AMT", "CONTRIB_S"]
ENTITY_COLS = ["ENTITYNAME", "LOCATION", "OFFICE", "PARTY", "ELECTIONTYPE", "ELECTIONYEAR"]
CONT_BLANK = {"ENTITY_S": "", "NONPACOnly": "true", "FirstName": "", "LastName": "", "NonIndName": "", "OfficeCodes": "", "PartyCodes": "", "LocationCodes": "",
              "ElectionTypeCodes": "", "ElectionYears": "", "ContributorFirstName": "", "ContributorLastName": "", "ContributorMI": "", "ContributorSuffix": "",
              "ContributorNonIndName": "", "ContributorTypeCodes": "", "EMP_NAME": "", "OccupationCodes": "", "DateFrom": "", "DateTo": "", "AmountFrom": "", "AmountTo": ""}
ENTITY_BLANK = {"NONPACOnly": "true", "FirstName": "", "LastName": "", "MI": "", "Suffix": "", "NonIndName": "", "PACName": "", "OfficeCodes": "", "PartyCodes": "",
                "LocationCodes": "", "ElectionTypeCodes": "", "ElectionYears": "", "SortColumn": "ElectionYear", "SortBy": "DESC"}

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


# ----------------------------------------------------------------------------------------------------------------
# the Commission's search system

def table_params(cols, start, length, order_col=0):
    """What the search pages' DataTables send with every request."""
    d = {"draw": "1", "start": str(start), "length": str(length), "search[value]": "", "search[regex]": "false", "order[0][column]": str(order_col), "order[0][dir]": "asc"}
    for i, c in enumerate(cols):
        d[f"columns[{i}][data]"] = c
        d[f"columns[{i}][name]"] = c
        d[f"columns[{i}][searchable]"] = "true"
        d[f"columns[{i}][orderable]"] = "true"
        d[f"columns[{i}][search][value]"] = ""
        d[f"columns[{i}][search][regex]"] = "false"
    return d


def post_rows(path, obj, cols, page, referer, say=print):
    """Every row the search system holds for one query, fetched the way its own pages do (a form-encoded POST, JSON back)."""
    net.patient_lookups()
    rows, start = [], 0
    while True:
        fields = dict(obj, **table_params(cols, start, page))
        req = Request(BASE + path, data=urllib.parse.urlencode(fields).encode(), method="POST",
                      headers={"User-Agent": net.UA, "Referer": BASE + referer, "X-Requested-With": "XMLHttpRequest", "Accept": "application/json, text/javascript, */*",
                               "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"})
        for attempt in range(4):
            try:
                with urlopen(req, timeout=600) as r:
                    d = json.loads(r.read().decode("utf-8", "replace"))
                break
            except (HTTPError, URLError, OSError, ValueError) as e:
                if attempt == 3:
                    raise
                say(f"      {path}: {e}; trying again in {15 * (attempt + 1)} s")
                time.sleep(15 * (attempt + 1))
        got = d.get("data") or []
        rows += got
        total = d.get("recordsTotal", len(rows))
        if not got or len(rows) >= total:
            break
        start += len(got)
        time.sleep(1.5)
    time.sleep(1.5)
    return rows


def cached(path, fetch, say=print):
    """The rows on disk if fresh; else fetched, saved, and returned. A failed refresh falls back to the copy on disk."""
    if os.path.exists(path) and (time.time() - os.path.getmtime(path)) < MAX_AGE_DAYS * 86400:
        return json.load(open(path, encoding="utf-8"))
    try:
        rows = fetch()
    except (HTTPError, URLError, OSError, ValueError) as e:
        if os.path.exists(path):
            say(f"      could not refresh {os.path.basename(path)} ({e}); using the copy on disk")
            return json.load(open(path, encoding="utf-8"))
        raise
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(rows, fh)
    return rows


def register(folder, offices, say=print):
    """Every account the Commission lists for these office codes ('1,2' the two chambers, 'E' joint candidates committees)."""
    path = os.path.join(folder, f"entities_{offices.replace(',', '_')}.json")
    return cached(path, lambda: post_rows("/api/VWEntity/Entities20", dict(ENTITY_BLANK, OfficeCodes=offices), ENTITY_COLS, 10000, "/SearchEntityList", say), say)


def contributions(folder, office, year, say=print):
    """Every contribution row for one office code and election year."""
    path = os.path.join(folder, f"cont_{office}_{year}.json")
    return cached(path, lambda: post_rows("/api/VWContributionDetail/GetContBitsDataByObject", dict(CONT_BLANK, OfficeCodes=office, ElectionYears=str(year)),
                                          CONT_COLS, 100000, "/SearchContributionToEntity", say), say)


# ----------------------------------------------------------------------------------------------------------------
# names

def district_of(location):
    m = DISTRICT.match(location or "")
    return int(m.group(1)) if m else None


def family_of(entityname):
    """'GREENWALD, LOUIS D' -> 'GREENWALD'; 'BROWN BLAEUER, MELISSA' -> 'BROWN BLAEUER'."""
    return (entityname or "").split(",")[0].strip()


def firsts_of(entityname):
    """'GREENWALD, LOUIS D' -> ['LOUIS', 'D']."""
    rest = (entityname or "").split(",", 1)[1] if "," in (entityname or "") else ""
    return [t for t in re.findall(r"[A-Za-z][A-Za-z'\-]*", rest) if t]


def title_tokens(text):
    return [t for t in re.findall(r"[A-Za-z][A-Za-z']+", (text or "").upper()) if t]


def close(a, b):
    """Two family names one slip apart ('KONAWELL' and 'KONAWEL', 'MYHRE' and 'MHYRE'), for names of five letters or more."""
    a, b = norm(a), norm(b)
    if a == b:
        return True
    if min(len(a), len(b)) < 5 or abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        diff = [i for i in range(len(a)) if a[i] != b[i]]
        return len(diff) == 1 or (len(diff) == 2 and diff[1] == diff[0] + 1 and a[diff[0]] == b[diff[1]] and a[diff[1]] == b[diff[0]])
    s, l = (a, b) if len(a) < len(b) else (b, a)
    for i in range(len(l)):
        if l[:i] + l[i + 1:] == s:
            return True
    return False


def named_in(title, family):
    """Whether a family name ('VON ACHEN', 'WHITE MORRIS', 'PU') is written in a joint committee's title."""
    toks = title_tokens(title)
    parts = [p for p in re.split(r"[\s\-]+", family.upper()) if p]
    if not parts:
        return False
    if len(parts) > 1 and all(any(norm(p) == norm(t) for t in toks) for p in parts):
        return True
    for p in parts:
        if len(p) <= 2:
            if any(norm(p) == norm(t) for t in toks):
                return True
        elif any(close(p, t) for t in toks if len(norm(t)) >= 3):
            return True
    return False


def donor_key(name):
    """One id for one organization however the campaigns spelled it: 'NJ REPUBLICAN STATE CMTE' and
    'NEW JERSEY REPUBLICAN STATE COMMITTEE' are the same giver."""
    n = " ".join((name or "").upper().split())
    n = re.sub(r"\bN\.?J\.?\b", "NEW JERSEY", n)
    n = re.sub(r"\bCMTE\b", "COMMITTEE", n)
    n = re.sub(r"\bORG\b", "ORGANIZATION", n)
    n = re.sub(r"\bASSN\b|\bASSOC\b", "ASSOCIATION", n)
    n = re.sub(r"\bPOL\b", "POLITICAL", n)
    n = re.sub(r"\bINC\b|\bLLC\b|\bCORP\b|\bTHE\b", "", n)
    return "n-" + (norm(n)[:48] or "unnamed")


# ----------------------------------------------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", required=True)
    ap.add_argument("--cache-dir", default="states_cache")
    ap.add_argument("--since", type=int, default=2015, help="first year to keep (the 2016 cycle begins in January 2015)")
    args = ap.parse_args()
    t0 = time.time()
    folder = os.path.join(args.cache_dir, "nj_elec")
    con = sqlite3.connect(args.db)
    con.executescript(SCHEMA)
    if not con.execute("SELECT 1 FROM sqlite_master WHERE name = 'legislators'").fetchone():
        sys.exit("No members yet. Run the people stage first.")
    members = {}
    for bio, first, last, full, others, district, chamber, party, first_term in con.execute(
            "SELECT bioguide_id, first_name, last_name, official_full, other_names, district, chamber, party, first_term_start FROM legislators WHERE is_current = 1"):
        names = [o.strip() for o in (others or "").split(";") if o.strip()]
        givens = {first, (full or "").split(" ")[0]} | {o.split(",")[-1].strip().split(" ")[0] if "," in o else o.split(" ")[0] for o in names}
        givens |= {q for o in names for q in re.findall(r'"([^"]+)"', o)}
        fams = families_of(last) | {norm((full or "").split(" ")[-1])}
        for o in names:
            if "," in o:
                fams |= families_of(o.split(",")[0])
        members[bio] = {"family": {f for f in fams if f}, "family_text": last, "given": {g for g in givens if g and len(norm(g)) > 1 and "." not in g},
                        "name": full, "initials": norm(first) if "." in (first or "") else "",
                        "first_year": int(first_term[:4]) if first_term and first_term[:4].isdigit() else None,
                        "district": int(str(district or "0").lstrip("0") or 0), "chamber": chamber, "party": party}

    def fits(bio, family, firsts):
        m = members[bio]
        fam = norm(family)
        if fam not in m["family"] and not any(norm(p) in m["family"] for p in re.split(r"[\s\-]+", family) if len(norm(p)) > 3):
            return False
        if not firsts:
            return False
        for c in firsts:
            for g in m["given"]:
                if given_fits(c, g) or (len(norm(g)) == 2 and norm(c).startswith(norm(g))):      # the roster's "Al" for the Commission's "ALI"
                    return True
        return any(initials_fit(firsts, g) for g in m["given"]) or (m["initials"] and norm(" ".join(firsts)) == m["initials"])

    # -- 1. the register: every candidacy for the Senate or Assembly, and every joint candidates committee
    print(f"    asking the Commission's search system for its register of candidacies and joint committees ({time.time() - t0:.0f} s)", flush=True)
    cands = [e for e in register(folder, "1,2") if district_of(e.get("LOCATION"))]
    joints = [e for e in register(folder, "E") if district_of(e.get("LOCATION"))]
    for e in cands + joints:
        e["ENTITY_S"] = str(e["ENTITY_S"])
        e["ELECTIONYEAR"] = int(e["ELECTIONYEAR"])
    print(f"    {len(cands):,} legislative candidacies and {len(joints):,} joint candidates committees in legislative districts, all years ({time.time() - t0:.0f} s)")

    # -- 2. the rows, one call per office and election year
    this_year = dt.date.today().year
    rows = []
    for office in ("1", "2", "E"):
        for year in range(args.since - 2, this_year + 3):
            got = contributions(folder, office, year)
            n = 0
            for r in got:
                if (r.get("CONT_DATE") or "")[:4] >= str(args.since) and district_of(r.get("LOCATION")):
                    r["ENTITY_S"] = str(r["ENTITY_S"])
                    rows.append(r)
                    n += 1
            if got:
                print(f"      {'Senate' if office == '1' else 'Assembly' if office == '2' else 'joint committees'} {year}: {len(got):,} rows, {n:,} dated {args.since} or later ({time.time() - t0:.0f} s)", flush=True)
    active = collections.Counter(r["ENTITY_S"] for r in rows)
    print(f"    {len(rows):,} rows dated {args.since} or later for {len(active):,} accounts ({time.time() - t0:.0f} s)")

    # -- 3. match candidacies to sitting members: every candidacy since the window opened, money or not, because a
    # member whose own account took nothing (all of it went through the joint committee) still names the joint committee
    by_id = {e["ENTITY_S"]: e for e in cands}
    cand_bio, ambiguous = {}, {}
    for eid, e in by_id.items():
        if eid not in active and e["ELECTIONYEAR"] < args.since - 2:
            continue
        fam, firsts = family_of(e["ENTITYNAME"]), firsts_of(e["ENTITYNAME"])
        hit = [bio for bio in members if fits(bio, fam, firsts)]
        if len(hit) > 1:
            same = [b for b in hit if members[b]["district"] == district_of(e["LOCATION"])]
            hit = same if len(same) == 1 else hit
        if len(hit) == 1:
            cand_bio[eid] = hit[0]
        elif len(hit) > 1:
            ambiguous[eid] = f"{e['ENTITYNAME']} ({e['ELECTIONYEAR']}, {e['LOCATION'].strip()}): fits {', '.join(members[b]['name'] for b in hit)}"
    # a namesake: an account of another party in the same election as the member's own, or over before the member's first term
    namesakes = []
    for eid in list(cand_bio):
        e, bio = by_id[eid], cand_bio[eid]
        if PARTY.get(e["PARTY"], e["PARTY"]) == members[bio]["party"]:
            continue
        own_same = [by_id[k] for k, b in cand_bio.items() if b == bio and k != eid and PARTY.get(by_id[k]["PARTY"], by_id[k]["PARTY"]) == members[bio]["party"]]
        overlap = any(o["ELECTIONYEAR"] == e["ELECTIONYEAR"] and o["ELECTIONTYPE"] == e["ELECTIONTYPE"] for o in own_same)
        before = members[bio]["first_year"] and e["ELECTIONYEAR"] < members[bio]["first_year"]
        if overlap or before:
            namesakes.append(f"{e['ENTITYNAME']} {e['PARTY'].title()} {e['ELECTIONYEAR']} ({'the same election as' if overlap else 'over before'} {members[bio]['name']}'s own {members[bio]['party']} account)")
            del cand_bio[eid]
    cand_bio_all = dict(cand_bio)                                                 # every candidacy, for reading the joint committees
    cand_bio = {eid: bio for eid, bio in cand_bio.items() if eid in active}       # the accounts with money, stored as the member's
    matched = set(cand_bio.values())
    print(f"    {len(cand_bio)} Senate and Assembly accounts with money fit {len(matched)} of {len(members)} sitting members "
          f"({len(cand_bio_all)} candidacies read in all; {time.time() - t0:.0f} s)")

    # -- 4. joint candidates committees: who each was formed for, from the names in its title
    slate = collections.defaultdict(list)
    for e in cands:
        slate[(district_of(e["LOCATION"]), e["ELECTIONYEAR"], e["ELECTIONTYPE"], e["PARTY"])].append(e)
    joint_members = {}                 # joint entity id -> {bio: office}
    joint_shares = {}                  # joint entity id -> how many candidates share it
    joint_left = []
    for j in joints:
        if j["ENTITY_S"] not in active:
            continue
        key = (district_of(j["LOCATION"]), j["ELECTIONYEAR"], j["ELECTIONTYPE"], j["PARTY"])
        named = {}                                                                # family text -> (bio or None, office)
        for c in slate.get(key, []):
            fam = family_of(c["ENTITYNAME"])
            if named_in(j["ENTITYNAME"], fam):
                named[norm(fam)] = (cand_bio_all.get(c["ENTITY_S"]), "Senate" if "SENATE" in c["OFFICE"] else "House")
        for bio, m in members.items():                                            # a running mate whose candidacy is not registered yet (a coming primary)
            if norm(m["family_text"]) not in named and m["district"] == key[0] and m["party"] == PARTY.get(key[3], key[3]) and named_in(j["ENTITYNAME"], m["family_text"]):
                named[norm(m["family_text"])] = (bio, m["chamber"])
        if not named:
            joint_left.append(f"{j['ENTITYNAME']} ({j['ELECTIONYEAR']} {j['ELECTIONTYPE'].lower()}, {j['LOCATION'].strip()}, {j['PARTY'].title()}): ${sum(r['CONT_AMT'] for r in rows if r['ENTITY_S'] == j['ENTITY_S']):,.0f}")
            continue
        joint_shares[j["ENTITY_S"]] = len(named)
        joint_members[j["ENTITY_S"]] = {bio: office for bio, office in named.values() if bio}
    joint_names = collections.defaultdict(set)                                   # member -> the normalized titles of their own joint committees
    for jid, who in joint_members.items():
        for bio in who:
            joint_names[bio].add(donor_key(next(j["ENTITYNAME"] for j in joints if j["ENTITY_S"] == jid)))
    with_joint = {bio for who in joint_members.values() for bio in who}
    print(f"    {len(joint_shares)} joint candidates committees with money read for their candidates; {len(with_joint)} sitting members share in one ({time.time() - t0:.0f} s)")

    # -- 5. the rows: people and the candidate as totals, organizations by name; a joint committee's gift in equal shares
    people = People()
    for r in rows:
        if r.get("IsIndividual") == "Y" and r.get("FIRST_NAME"):
            people.given[norm(r["FIRST_NAME"].split()[0])] += 1
    joint_by_id = {j["ENTITY_S"]: j for j in joints}
    gifts, sources, kinds_seen = [], {}, collections.defaultdict(collections.Counter)
    by_type, by_code, unknown_types = collections.Counter(), collections.Counter(), collections.Counter()
    own_by_name, y_kinds, set_aside, odd_dates = collections.Counter(), collections.Counter(), collections.Counter(), collections.Counter()
    n_kept = 0

    def add_source(bio, reg, office, year, source, amount):
        s = sources.setdefault((bio, reg, office, year, source), [0.0, 0])
        s[0] += amount
        s[1] += 1

    def is_self(r, bio):
        if r.get("IsIndividual") != "Y":
            return False
        return fits(bio, r.get("LAST_NAME") or "", [t for t in re.findall(r"[A-Za-z][A-Za-z'\-]*", r.get("FIRST_NAME") or "") if t])

    def is_own(name, bio):
        """The member's own other committee: one of their joint committees, or a candidate committee named for them alone."""
        if donor_key(name) in joint_names[bio]:
            return True
        m = members[bio]
        toks = [norm(t) for t in re.findall(r"[A-Za-z][A-Za-z'\-]*", name or "")]
        if not any(t in m["family"] for t in toks) or not OWN_WORD.search(name or ""):
            return False
        for t in toks:
            if t in m["family"] or t in STOP or t.isdigit() or len(t) <= 1:
                continue
            if not any(given_fits(t, g) for g in m["given"]):
                return False                                                      # another name in the title: somebody else's committee
        return True

    def kind_of(r, name):
        code = (r.get("CONT_TYPE") or "").upper()
        if code in PERSON_CODES:
            return None
        if code in OTHER_CODES:
            return "other"
        if code in KIND:
            k = KIND[code]
            if code in ("E", "Z", "C", "R") and (PARTY_WORD.search(name) or LEADERSHIP.search(name)):
                return "party"
            if code == "B" and people.is_person(name):
                y_kinds["business filed under a person's name"] += 1
                return None                                                       # a sole proprietor: a business named after its owner may be hidden, a person is never shown
            return k
        # "not provided" and anything unlisted: read the name
        if r.get("IsIndividual") == "Y":
            y_kinds["person (flagged)"] += 1
            return None
        if LUMP.search(name):
            y_kinds["unitemized sum"] += 1
            return "other"                                                        # "CONTRIBUTIONS LESS THAN $300": a sum, not a giver
        if PARTY_WORD.search(name) or LEADERSHIP.search(name):
            y_kinds["party"] += 1
            return "party"
        if CAND_WORD.search(name) and not STRONG_ORG.search(name):
            y_kinds["cand"] += 1
            return "cand"
        if PAC_WORD.search(name):
            y_kinds["pcf"] += 1
            return "pcf"
        if people.is_person(name):
            y_kinds["person (by name)"] += 1
            return None
        if CORP.search(name):
            y_kinds["biz"] += 1
            return "biz"
        y_kinds["org"] += 1
        return "org"

    for r in rows:
        eid = r["ENTITY_S"]
        if eid in cand_bio:
            targets = [(cand_bio[eid], f"nj:{eid}", OFFICE.get(str(r.get("OFFICECODE")), members[cand_bio[eid]]["chamber"]), 1.0)]
        elif eid in joint_members:
            share = 1.0 / joint_shares[eid]
            targets = [(bio, f"nj:{eid}:{bio}", office, share) for bio, office in joint_members[eid].items()]
        else:
            continue
        amount = float(r.get("CONT_AMT") or 0)
        date = (r.get("CONT_DATE") or "")[:10]
        if not amount or not date:
            continue
        year = int(date[:4])
        if year > this_year:
            year = min(int(r.get("ELECTIONYEAR") or this_year), this_year)        # a slip in the filing ("3026", or next year's date): filed under this year or the account's election year, the date kept as filed
            odd_dates[date] += 1
        typ = (r.get("ContributionType") or "").upper()
        name = " ".join((r.get("CONTRIBUTOR") or "").split())
        n_kept += 1
        by_type[typ] += 1
        by_code[(r.get("CONT_TYPE") or "?").upper()] += 1
        for bio, reg, office, share in targets:
            amt = amount * share
            if typ in ("LOAN", "CURRENCY LOAN", "LOAN PAY"):
                add_source(bio, reg, office, year, "loans", amt)
                continue
            if typ in ("INTEREST", "REFUND-FS", "REBURS/REFD"):
                add_source(bio, reg, office, year, "other", amt)
                continue
            if typ not in ("MONETARY", "IN-KIND", "CURRENCY", "ADJUSTMENTS", "NON-DEPOSITED", "CASH N/SUBM"):
                unknown_types[typ] += 1
            if not name:
                add_source(bio, reg, office, year, "other", amt)
                continue
            if is_self(r, bio):
                add_source(bio, reg, office, year, "self", amt)
                continue
            kind = kind_of(r, name)
            if kind is None:
                add_source(bio, reg, office, year, "people", amt)
                if r.get("IsIndividual") != "Y" and (STRONG_ORG.search(name) or CORP.search(name)):
                    set_aside[name] += amt
                continue
            if kind == "other":
                add_source(bio, reg, office, year, "other", amt)
                continue
            if kind == "cand" and is_own(name, bio):
                did = reg                                                         # the member's own money moving: "moved in", never a donor
                own_by_name[f"{name} -> {members[bio]['name']}"] += amt
            else:
                did = donor_key(name)
                kinds_seen[did][kind] += 1
            gifts.append([bio, reg, office, year, date, round(amt, 2), did, name, kind, 1 if typ == "IN-KIND" else 0])
            add_source(bio, reg, office, year, kind, amt)
    for g in gifts:
        if g[6] in kinds_seen:
            g[8] = kinds_seen[g[6]].most_common(1)[0][0]
    print(f"    {n_kept:,} rows kept (receipt types: " + ", ".join(f"{k} {v:,}" for k, v in by_type.most_common(8)) + f"; {time.time() - t0:.0f} s)")

    # -- 6. store
    committees = [(f"nj:{eid}", f"{by_id[eid]['ENTITYNAME']} · {by_id[eid]['ELECTIONYEAR']} {by_id[eid]['ELECTIONTYPE'].lower()}",
                   "Senate" if "SENATE" in by_id[eid]["OFFICE"] else "House", bio) for eid, bio in cand_bio.items()]
    for jid, who in joint_members.items():
        j = joint_by_id[jid]
        for bio, office in who.items():
            committees.append((f"nj:{jid}:{bio}", f"{j['ENTITYNAME']} · {j['ELECTIONYEAR']} {j['ELECTIONTYPE'].lower()} (shared by {joint_shares[jid]} candidates)", office, bio))
    with con:
        for t in ("state_committees", "state_gifts", "state_sources", "state_outside"):
            con.execute(f"DELETE FROM {t}")
        con.executemany("INSERT INTO state_committees VALUES (?,?,?,?)", committees)
        con.executemany("INSERT INTO state_gifts (bioguide_id, committee, office, year, date, amount, donor_id, donor_name, donor_kind, in_kind) VALUES (?,?,?,?,?,?,?,?,?,?)", gifts)
        con.executemany("INSERT INTO state_sources VALUES (?,?,?,?,?,?,?)", [(*k, round(v[0], 2), v[1]) for k, v in sources.items()])
    by_source = dict(con.execute("SELECT source, ROUND(SUM(amount)) FROM state_sources GROUP BY 1"))
    joint_total = con.execute("SELECT ROUND(SUM(amount)) FROM state_sources WHERE committee LIKE 'nj:%:%'").fetchone()[0] or 0
    print(f"    Stored: {len(gifts):,} gifts from organizations (${sum(g[5] for g in gifts) / 1e6:,.1f}M); totals by source: "
          + ", ".join(f"{k} ${v / 1e6:,.1f}M" for k, v in sorted(by_source.items(), key=lambda kv: -kv[1])))
    print(f"    of which members' shares of joint candidates committees: ${joint_total / 1e6:,.1f}M across {len(joint_members)} committees")
    print("    Outside spending: none loaded; the Commission's expenditure records do not say which candidate a committee spent for or against")
    top = con.execute("SELECT donor_name, donor_kind, ROUND(SUM(amount)) FROM state_gifts WHERE donor_id LIKE 'n-%' GROUP BY donor_id ORDER BY 3 DESC LIMIT 8").fetchall()
    print("    biggest named givers: " + "; ".join(f"{n[:60]} ({k}) ${a / 1e6:,.1f}M" for n, k, a in top))
    if y_kinds:
        print("    givers filed with no kind, read from the name: " + ", ".join(f"{k} {v:,}" for k, v in y_kinds.most_common()))
    if set_aside:
        print(f"    givers with a company's word in the name but counted with people, for reading ({len(set_aside)}): " + "; ".join(f"{n} ${a:,.0f}" for n, a in set_aside.most_common(10)))
    if unknown_types:
        print("    receipt types the loader does not list, counted as monetary: " + ", ".join(f"{k} {v}" for k, v in unknown_types.most_common()))
    if odd_dates:
        print("    rows dated in the far future, filed under the account's election year: " + ", ".join(f"{d} x{n}" for d, n in odd_dates.most_common(5)))
    if own_by_name:
        print(f"    treated as the member's own committee, moved in ({len(own_by_name)}): " + "; ".join(f"{k} ${v:,.0f}" for k, v in own_by_name.most_common(12)) + (" ..." if len(own_by_name) > 12 else ""))
    if joint_left:
        print(f"    joint committees with money whose title names no candidate the register knows ({len(joint_left)}): " + "; ".join(joint_left[:8]))
    mism = [f"{by_id[k]['ENTITYNAME']} {by_id[k]['PARTY'].title()} {by_id[k]['ELECTIONYEAR']} -> {members[b]['name']} ({members[b]['party']})" for k, b in cand_bio.items() if PARTY.get(by_id[k]["PARTY"], by_id[k]["PARTY"]) != members[b]["party"]]
    if mism:
        print(f"    accounts whose party differs from the roster's ({len(mism)}): " + "; ".join(mism[:8]) + (" ..." if len(mism) > 8 else ""))
    if namesakes:
        print(f"    left out as a namesake of another party ({len(namesakes)}): " + "; ".join(namesakes[:10]))
    if ambiguous:
        print(f"    left out, more than one member fits ({len(ambiguous)}): " + "; ".join(list(ambiguous.values())[:8]))
    unmatched = [m["name"] for bio, m in members.items() if bio not in matched and bio not in with_joint]
    if unmatched:
        print(f"    sitting members with no account matched ({len(unmatched)}): " + ", ".join(sorted(unmatched)[:30]) + (" ..." if len(unmatched) > 30 else ""))
    only_joint = [members[b]["name"] for b in with_joint if b not in matched]
    if only_joint:
        print(f"    members found only through a joint committee ({len(only_joint)}): " + ", ".join(sorted(only_joint)[:20]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
