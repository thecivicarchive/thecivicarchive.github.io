#!/usr/bin/env python3
"""
states/money_ny.py
==================
New York campaign money, from the State Board of Elections' public reporting system (publicreporting.elections.ny.gov):
its bulk download of every itemized disclosure transaction filed since July 1999, its register of every filer, and its
own record of which candidate each authorized committee was formed for.

The Board's site sits behind a Cloudflare challenge that a plain script cannot pass and must not try to get around, so
this loader downloads nothing. The files are carried out of the Browser pane by hand and put in states_cache/ny_boe/:

  ALL_REPORTS_StateCommittee.zip   Bulk Download: Disclosure Report, year All, type State Committee (every state-level
                                   committee's transactions, all years; about 440 MB zipped, 5 GB of text)
  ALL_REPORTS_StateCandidate.zip   the same for candidates who file on their own (small)
  <year><period>.zip               any Bulk Download for one year and one report period (2025jul.zip and the like),
                                   read after the all-years files so a newer copy of a transaction replaces the older
  filers.json                      the List of Filers page's data (every filer: id, name, candidate or committee, office,
                                   district, status)
  links.json                       for every authorized candidate committee, the candidates the Board lists for it
                                   (the List of Filers page's candidate lookup, one call per committee)

The loader tells the two bulk layouts apart by width (the all-years files carry a FILER_PREVIOUS_ID column, the period
files do not) and reads every transaction once, by its TRANS_NUMBER, the last copy read winning (an amended report
lists the transaction again).

The same rule as everywhere on the site. Organizations are named: political committees and PACs, party committees,
other candidates' committees, unions, and the corporations, LLCs, partnerships and associations New York lets give
directly. People are not named: every gift from an individual, from a candidate's family, or from a sole proprietor
goes into a yearly total, and no name from those rows is written anywhere; the employer and occupation columns the
public financing program adds are never read. The candidate's own money, and the candidate's spouse's, which the Board
files under one code, is "own money". A transfer between two committees of the same candidate is the candidate's own
money moving and is reported as "moved in".

What counts as the member's campaign: every committee the Board lists as authorized for the member's candidacy for
State Senator or Member of Assembly, and the member's own filings as a candidate. A committee the Board ties only to
another office is left out and listed.

Outside spending: an independent expenditure committee reports what it spent for or against candidates on Schedule R
with a support/oppose flag, the office and the district, but the bulk file carries no candidate name on those rows, so
they cannot be tied to one candidate and no outside spending is shown for New York. The page says so.

  state_committees   each committee (or candidate filing) read as the member's
  state_gifts        every gift from an organization to one of those committees
  state_sources      yearly totals by source
  state_outside      empty for New York (see above)

    python -m states.money_ny --db state_ny.sqlite --since 2015
"""

import argparse
import collections
import csv
import glob
import io
import json
import os
import re
import sqlite3
import sys
import time
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from states.money_mn import norm, given_fits                         # noqa: E402
from states.money_tx import families_of, initials_fit                # noqa: E402
from states.money_ca import People, STRONG_ORG, CAND_WORD, name_tokens   # noqa: E402

OFFICE = {"State Senator": "Senate", "Member of Assembly": "House"}   # the roster files the Assembly as "House", as every state database does
COLS = ["FILER_ID", "CAND_COMM_NAME", "ELECTION_YEAR", "ELECTION_TYPE", "COUNTY_DESC", "FILING_ABBREV", "FILING_DESC", "R_AMEND", "FILING_CAT_DESC",
        "FILING_SCHED_ABBREV", "FILING_SCHED_DESC", "LOAN_LIB_NUMBER", "TRANS_NUMBER", "TRANS_MAPPING", "SCHED_DATE", "ORG_DATE", "CNTRBR_TYPE_DESC",
        "CNTRBN_TYPE_DESC", "TRANSFER_TYPE_DESC", "RECEIPT_TYPE_DESC", "RECEIPT_CODE_DESC", "PURPOSE_CODE_DESC", "R_SUBCONTRACTOR", "FLNG_ENT_NAME",
        "FLNG_ENT_FIRST_NAME", "FLNG_ENT_MIDDLE_NAME", "FLNG_ENT_LAST_NAME", "FLNG_ENT_ADD1", "FLNG_ENT_CITY", "FLNG_ENT_STATE", "FLNG_ENT_ZIP",
        "FLNG_ENT_COUNTRY", "PAYMENT_TYPE_DESC", "PAY_NUMBER", "OWED_AMT", "ORG_AMT", "LOAN_OTHER_DESC", "TRANS_EXPLNTN", "R_ITEMIZED", "R_LIABILITY",
        "ELECTION_YEAR_R", "OFFICE_DESC", "DISTRICT", "DIST_OFF_CAND_BAL_PROP"]
IDX = {c: i for i, c in enumerate(COLS)}
PARTY_WORD = re.compile(r"\b(democrat\w*|republican\w*|conservative party|working families|independence party|green party|libertarian\w*|"
                        r"party committee|county committee|state committee|town committee|city committee|village committee|senate campaign committee|"
                        r"assembly campaign committee|campaign committee)\b", re.I)
LEADERSHIP = re.compile(r"\b(democratic|republican) (senate|assembly) campaign committee\b|\bdsc\b|\brsc\b|\bdacc\b|\bracc\b|\bsenate republican campaign\b|\bhousekeeping\b", re.I)
PAC_WORD = re.compile(r"\bpac\b|political action|political committee|\bfund\b|\bcommittee\b|\bcoalition\b|\balliance\b|\bcitizens\b|\bvoters\b", re.I)
CORP = re.compile(r"\b(corp(oration)?|inc(orporated)?|llc|l\.l\.c\.?|ltd|limited|company|co\.|companies|pllc|lp|llp|pc|p\.c\.|dba|realty|associates|"
                  r"holdings?|group|enterprises|industries|partners(hip)?|services|systems|management|development|construction|contracting)\b", re.I)
LUMP = re.compile(r"unitemized|un-itemized|\banonymous\b|\bunder \$?\d|\bless than\b|\blump\b|\bmisc\b|\bvarious\b|\bnot itemized\b", re.I)
PRACTICE = re.compile(r"\b(pllc|p\.?c\.?|llp|m\.?d\.?|d\.?d\.?s\.?|dmd|c\.?p\.?a\.?|esq\.?|attorney|law office|law offices|architect|dba|d/b/a)\b", re.I)
UNION_WORD = re.compile(r"\bunion\b|\blocal \d+|\bafl-?cio\b|\bcope\b|\blaborers\b|\bteamsters\b|\bcarpenters\b|\bfire ?fighters\b|\bpba\b|\bcsea\b|\bnysut\b|\buft\b|\bseiu\b|\bcwa\b|\bibew\b|\buaw\b|\bpef\b|\bdc ?37\b|\bbrotherhood\b|\bworkers\b", re.I)
SUFFIX = {"jr", "sr", "ii", "iii", "iv", "esq", "md", "phd", "dds", "cpa"}

# the Board's contributor types (CNTRBR_TYPE_DESC) on the receipt schedules, and the kinds this site names
KIND = {"Political Action Committee (PAC)": "pcf", "Political Committee": "pcf", "Committee": "pcf", "Union": "union",
        "Corporation": "biz", "Professional/Limited Liability Company (PLLC/LLC)": "biz", "Partnership including LLPs": "org", "Partnership, including LLPs": "org",
        "Association": "org", "Other": "org"}
PERSON = {"Individual", "Candidate Family Member", "Sole Proprietorship"}
SELF = {"Candidate/Candidate Spouse"}

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


def csv_rows(folder):
    """Every transaction row in every bulk file in the cache, all-years files first, then the period files by name, as
    (source file, list of 44 named fields)."""
    paths = sorted(glob.glob(os.path.join(folder, "ALL_REPORTS_*.zip"))) + sorted(p for p in glob.glob(os.path.join(folder, "*.zip")) if not os.path.basename(p).startswith("ALL_REPORTS_"))
    for path in paths:
        with zipfile.ZipFile(path) as outer:
            members = []
            for info in outer.infolist():
                if info.filename.lower().endswith(".csv"):
                    members.append((outer, info.filename))
                elif info.filename.lower().endswith(".zip"):
                    inner = zipfile.ZipFile(io.BytesIO(outer.read(info.filename)))
                    members += [(inner, i.filename) for i in inner.infolist() if i.filename.lower().endswith(".csv")]
            for z, name in members:
                with z.open(name) as fh:
                    for row in csv.reader(io.TextIOWrapper(fh, encoding="utf-8", errors="replace", newline="")):
                        if len(row) < 45:
                            continue
                        if len(row) == 59 or not re.fullmatch(r"\d{4}", row[2]):      # the all-years layout carries FILER_PREVIOUS_ID second
                            row = row[:1] + row[2:]
                        yield os.path.basename(path), row


def person_name(row):
    return " ".join(t for t in (row[IDX["FLNG_ENT_FIRST_NAME"]], row[IDX["FLNG_ENT_MIDDLE_NAME"]], row[IDX["FLNG_ENT_LAST_NAME"]]) if t)


ALIAS = {"DACC": "DEMOCRATIC ASSEMBLY CAMPAIGN COMMITTEE", "RACC": "REPUBLICAN ASSEMBLY CAMPAIGN COMMITTEE", "DSCC": "DEMOCRATIC SENATE CAMPAIGN COMMITTEE",
         "SRCC": "SENATE REPUBLICAN CAMPAIGN COMMITTEE", "NYSDCC": "NEW YORK STATE DEMOCRATIC COMMITTEE"}


def donor_key(name):
    """One id for one organization however the campaigns spelled it: 'DACC', 'Democratic Assembly Campaign Committee' and
    'NYS Democratic Assembly Campaign Committee (DACC)' are the same giver."""
    n = " ".join((name or "").upper().split())
    n = re.sub(r"\([^)]*\)", " ", n)
    n = re.sub(r"\bN\.?Y\.?S\.?\b", "NEW YORK STATE", n)
    n = re.sub(r"\bN\.?Y\.?C\.?\b", "NEW YORK CITY", n)
    n = re.sub(r"\bN\.?Y\.?\b", "NEW YORK", n)
    n = re.sub(r"\bCMTE\b|\bCOMM\b|\bCOMMITTE\b|\bCOMITTEE\b", "COMMITTEE", n)
    n = re.sub(r"\bSENATORIAL\b", "SENATE", n)
    n = re.sub(r"\bASSN\b|\bASSOC\b", "ASSOCIATION", n)
    n = re.sub(r"\bPOL\b", "POLITICAL", n)
    words = n.split()
    if words and words[0] in ALIAS and len(words) <= 2:
        n = ALIAS[words[0]]
    n = re.sub(r"^NEW YORK STATE (?=(DEMOCRATIC|REPUBLICAN) (ASSEMBLY|SENATE) CAMPAIGN COMMITTEE)", "", n)
    n = re.sub(r"\bINC\b|\bLLC\b|\bCORP\b|\bTHE\b|\bOF\b", " ", n)
    return "n-" + (norm(n)[:48] or "unnamed")


STOP = {"friends", "of", "for", "the", "and", "committee", "cmte", "to", "elect", "re", "reelect", "team", "assemblyman", "assemblywoman", "assemblymember",
        "assembly", "senator", "senate", "state", "council", "nyc", "ny", "nys", "new", "york", "district", "ad", "sd", "campaign", "fund", "political",
        "citizens", "people", "neighbors", "a", "an", "in", "jr", "sr", "ii", "iii", "local", "city", "county", "town", "victory", "leadership"}
OWN_WORD = re.compile(r"\bfriends of\b|\bfor\b|committee to elect|\bre-?elect\b|\bteam\b|\bcampaign\b|\bcommittee\b|\bfund\b|\bcitizens\b|\bpeople\b|\bneighbors\b", re.I)


def own_committee(name, member):
    """A committee named for the member alone: the family name, a committee word, and no other name in the title."""
    toks = [norm(t) for t in re.findall(r"[A-Za-zÀ-ſ][A-Za-zÀ-ſ'\-]*", name or "")]
    if not any(t in member["family"] for t in toks) or not OWN_WORD.search(name or ""):
        return False
    for t in toks:
        if t in member["family"] or t in STOP or len(t) <= 1 or t.isdigit():
            continue
        if not any(given_fits(t, g) for g in member["given"]):
            return False
    return True


def name_parts(text):
    """'Thomas R Simmons' -> (['Thomas', 'R'], 'Simmons'); 'Rodneyse Bichotte Hermelyn' -> (['Rodneyse'], 'Bichotte Hermelyn') is not
    knowable from the string alone, so the family name is tried at every split from the right."""
    toks = [t for t in re.findall(r"[A-Za-zÀ-ſ][A-Za-zÀ-ſ'\-.]*", text or "") if norm(t) not in SUFFIX]
    return toks


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", required=True)
    ap.add_argument("--cache-dir", default="states_cache")
    ap.add_argument("--since", type=int, default=2015, help="first year to keep (the 2016 cycle begins in January 2015)")
    args = ap.parse_args()
    t0 = time.time()
    folder = os.path.join(args.cache_dir, "ny_boe")
    con = sqlite3.connect(args.db)
    con.executescript(SCHEMA)
    if not con.execute("SELECT 1 FROM sqlite_master WHERE name = 'legislators'").fetchone():
        sys.exit("No members yet. Run the people stage first.")
    for need in ("filers.json", "links.json"):
        if not os.path.exists(os.path.join(folder, need)):
            sys.exit(f"{need} is not in {folder}. The Board's site cannot be fetched by a script; carry the file out of the Browser pane (see the notes at the top of this loader).")
    if not glob.glob(os.path.join(folder, "*.zip")):
        sys.exit(f"No bulk download in {folder}. Put the Board's Bulk Download zips there (see the notes at the top of this loader).")

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
                        "district": str(district or "").lstrip("0"), "chamber": chamber, "party": party}

    def fits(bio, text):
        """Whether a name written in natural order ('Thomas R Simmons', 'Jessica Gonzalez-Rojas') is this member's."""
        m = members[bio]
        toks = name_parts(text)
        if len(toks) < 2:
            return False
        for cut in range(1, len(toks)):
            family = " ".join(toks[cut:])
            fam_ok = norm(family) in m["family"] or (norm(family) and norm(family) == norm(m["family_text"])) or any(norm(p) in m["family"] for p in re.split(r"[\s\-]+", family) if len(norm(p)) > 3)
            if not fam_ok:
                continue
            firsts = toks[:cut]
            if any(given_fits(c, g) or (len(norm(g)) == 2 and norm(c).startswith(norm(g))) for c in firsts for g in m["given"]):
                return True
            if any(initials_fit(firsts, g) for g in m["given"]) or (m["initials"] and norm(" ".join(firsts)) == m["initials"]):
                return True
        return False

    # -- 1. the register: candidate filers for the two chambers, matched to sitting members
    filers = json.load(open(os.path.join(folder, "filers.json"), encoding="utf-8"))
    filers = filers.get("aaData", filers)
    reg = {}                                                  # filer id -> row
    for r in filers:
        reg[str(r[5])] = {"linked": r[1] == "YES", "kind": r[2], "level": r[3], "ctype": r[4], "id": str(r[5]), "name": r[6], "office": r[7], "district": str(r[8]).lstrip("0"),
                          "status": r[14], "since": r[12], "ended": r[13]}
    fam_count = collections.Counter(norm(m["family_text"]) for m in members.values())

    def year_of(text):
        m = re.search(r"(\d{4})", text or "")
        return int(m.group(1)) if m else None

    def who_is(name, office, district, since=None, ended=None, active=False):
        """The one sitting member a registered candidacy belongs to. Either chamber counts (a member may have run for the
        other one); the chamber and district break a tie. A candidacy for the member's own seat whose family name is
        unique among sitting members is theirs even when the Board writes a different given name (Palmo for Paul), but
        only when it was registered in the member's own time and is still open or ended after they took the seat: a
        parent or a predecessor of the same name on the same seat is somebody else."""
        hit = [bio for bio in members if fits(bio, name)]
        if len(hit) > 1:
            same = [b for b in hit if members[b]["chamber"] == OFFICE.get(office) and members[b]["district"] == str(district).lstrip("0")]
            hit = same if len(same) == 1 else hit
        if len(hit) == 1:
            return hit[0], None
        if len(hit) > 1:
            return None, f"{name} ({office} {district}): fits {', '.join(members[b]['name'] for b in hit)}"
        toks = name_parts(name)
        if toks and fam_count.get(norm(toks[-1])) == 1:
            seat = [b for b, m in members.items() if norm(m["family_text"]) == norm(toks[-1]) and m["chamber"] == OFFICE.get(office) and m["district"] == str(district).lstrip("0")]
            if len(seat) == 1:
                first = members[seat[0]]["first_year"]
                y0, y1 = year_of(since), year_of(ended)
                if first and y0 and y0 >= first - 1 and (active or (y1 and y1 >= first)):
                    by_seat[f"{name} -> {members[seat[0]]['name']}"] += 1
                    return seat[0], None
        return None, None

    by_seat = collections.Counter()
    cand_bio, ambiguous = {}, {}
    for f in reg.values():
        if f["level"] != "State" or f["kind"] != "CANDIDATE" or f["office"] not in OFFICE:
            continue
        bio, why = who_is(f["name"], f["office"], f["district"], f["since"], f["ended"], f["status"] == "ACTIVE")
        if bio:
            cand_bio[f["id"]] = bio
        elif why:
            ambiguous[f["id"]] = why
    print(f"    {len(cand_bio)} candidate registrations for the Senate or Assembly fit {len(set(cand_bio.values()))} of {len(members)} sitting members ({time.time() - t0:.0f} s)")

    # -- 2. the committees: the Board's own list of the candidates each authorized committee was formed for
    links = json.load(open(os.path.join(folder, "links.json"), encoding="utf-8"))
    links = links.get("links", links)
    comm_bio, other_office, comm_offices = {}, [], {}
    shared = {}                                                                    # committee -> {bio: share} when the Board lists it for several candidates
    shared_n = {}
    for cid, cands in links.items():
        if not cands:
            continue
        who, offices, everyone = {}, set(), set()                                  # everyone: the distinct people the committee was formed for
        for c in cands:                                                            # ["", "State", cand id, name, year, office, district, ...]
            office = c[5] if len(c) > 5 else ""
            offices.add(office)
            f = reg.get(str(c[2]), {})
            bio = cand_bio.get(str(c[2]))
            if not bio:
                bio, _why = who_is(c[3], office, c[6] if len(c) > 6 else "", f.get("since") or str(c[4]), f.get("ended"), f.get("status") == "ACTIVE")
            everyone.add(bio or norm(c[3]))                                        # the same person registered twice is one person
            if office in OFFICE and bio:
                who[bio] = str(c[2])
        if len(who) == 1 and len(everyone) == 1:
            comm_bio[cid] = next(iter(who))
            comm_offices[cid] = offices
        elif who:
            shared[cid] = {bio: 1.0 / len(everyone) for bio in who}               # a committee formed for several candidates: equal shares
            shared_n[cid] = len(everyone)
            comm_offices[cid] = offices
        elif offices and not who:
            for c in cands:
                if c[5] not in OFFICE and any(fits(b, c[3]) for b in members):
                    other_office.append(f"{reg.get(cid, {}).get('name', cid)} ({c[5]} {c[6]}, {c[4]})")
                    break
    mine = set(cand_bio) | set(comm_bio) | set(shared)
    whose = dict(cand_bio)
    whose.update(comm_bio)
    matched = set(whose.values()) | {b for s in shared.values() for b in s}
    print(f"    {len(comm_bio)} authorized committees fit {len(set(comm_bio.values()))} members, and {len(shared)} committees formed for several candidates are shared by "
          f"{len({b for s in shared.values() for b in s})}; with candidates' own filings, {len(matched)} of {len(members)} members have an account ({time.time() - t0:.0f} s)")

    # -- 3. the rows
    people = People()
    rows, n_all, n_files = {}, 0, collections.Counter()
    for fname, row in csv_rows(folder):
        n_all += 1
        if n_all % 2000000 == 0:
            print(f"      {n_all:,} rows read ({time.time() - t0:.0f} s)", flush=True)
        if row[IDX["FILER_ID"]] not in mine:
            continue
        if row[IDX["SCHED_DATE"]][:4] < str(args.since):
            continue
        n_files[fname] += 1
        key = (row[IDX["FILER_ID"]], row[IDX["FILING_SCHED_ABBREV"]], row[IDX["TRANS_NUMBER"]] or f"{fname}:{n_all}")
        rows[key] = row                                                            # the last copy of a transaction wins (an amended report repeats it)
    print(f"    {n_all:,} rows in the bulk files; {len(rows):,} transactions since {args.since} for these accounts ({', '.join(f'{k} {v:,}' for k, v in n_files.most_common())}; {time.time() - t0:.0f} s)")
    for row in rows.values():
        if row[IDX["FILING_SCHED_ABBREV"]] in "AD" and row[IDX["CNTRBR_TYPE_DESC"]] in PERSON and row[IDX["FLNG_ENT_FIRST_NAME"]]:
            people.given[norm(row[IDX["FLNG_ENT_FIRST_NAME"]].split()[0])] += 1

    gifts, sources, kinds_seen = [], {}, collections.defaultdict(collections.Counter)
    by_sched, by_type, unknown_type, set_aside, moved, r_seen = collections.Counter(), collections.Counter(), collections.Counter(), collections.Counter(), collections.Counter(), collections.Counter()
    own_ids = collections.defaultdict(set)                                         # member -> the ids of their own committees' names, for a gift written under one of them
    for cid, bio in whose.items():
        own_ids[bio].add(donor_key(reg.get(cid, {}).get("name", "")))
    for cid, s in shared.items():
        for bio in s:
            own_ids[bio].add(donor_key(reg.get(cid, {}).get("name", "")))

    def add_source(bio, cid, office, year, source, amount):
        s = sources.setdefault((bio, cid, office, year, source), [0.0, 0])
        s[0] += amount
        s[1] += 1

    def org_kind(row, name):
        """What kind of organization a receipt row's giver is, from the Board's type first and the name second. Schedules
        B and C are for organizations by the Board's own definition, so a name there is a person's only when it is a
        professional practice under the person's own name (a PLLC, an attorney at law), which is hidden as elsewhere."""
        t = row[IDX["CNTRBR_TYPE_DESC"]]
        sched = row[IDX["FILING_SCHED_ABBREV"]]
        if PARTY_WORD.search(name) or LEADERSHIP.search(name):
            return "party"
        if PRACTICE.search(name) and people.is_person(name):
            return None
        if t in KIND:
            k = KIND[t]
            if k in ("pcf",) and CAND_WORD.search(name) and not STRONG_ORG.search(name):
                return "cand"
            return k
        if sched == "B":
            return "biz"
        if CAND_WORD.search(name) and not STRONG_ORG.search(name):
            return "cand"
        if PAC_WORD.search(name) or UNION_WORD.search(name):
            return "pcf" if not UNION_WORD.search(name) else "union"
        if sched in ("A", "D", "G") and people.is_person(name):
            return None
        if CORP.search(name) or STRONG_ORG.search(name):
            return "biz" if sched == "B" else "org"
        return "org"

    this_year = time.localtime().tm_year
    for row in rows.values():
        cid = row[IDX["FILER_ID"]]
        legs = [OFFICE[o] for o in comm_offices.get(cid, ()) if o in OFFICE]
        if cid in shared:
            targets = [(bio, f"ny:{cid}:{bio}", legs[0] if len(set(legs)) == 1 else members[bio]["chamber"], share) for bio, share in shared[cid].items()]
        else:
            bio = whose[cid]
            targets = [(bio, f"ny:{cid}", legs[0] if len(set(legs)) == 1 else members[bio]["chamber"], 1.0)]
        sched = row[IDX["FILING_SCHED_ABBREV"]]
        by_sched[sched] += 1
        try:
            amount = float(row[IDX["ORG_AMT"]] or 0)
        except ValueError:
            continue
        date = row[IDX["SCHED_DATE"]][:10]
        year = int(date[:4]) if date[:4].isdigit() else 0
        if not amount or not year:
            continue
        if year > this_year:
            year = min(int(row[IDX["ELECTION_YEAR"]] or year), this_year)          # a slip in the filing, filed under this year or the report's
        if sched in ("F", "H", "J", "K", "N", "O", "Q", "T", "U"):
            continue                                                               # spending, transfers out, loan repayments, liabilities, the owners behind an LLC
        if sched == "R":
            r_seen[(row[IDX["OFFICE_DESC"]], row[IDX["DISTRICT"]])] += 1
            continue
        if sched not in ("A", "B", "C", "D", "E", "G", "I", "L", "M", "P", "S"):
            unknown_type[sched] += 1
            continue
        t = row[IDX["CNTRBR_TYPE_DESC"]]
        ent = " ".join((row[IDX["FLNG_ENT_NAME"]] or "").split())
        pname = person_name(row)
        if sched in ("A", "B", "C", "D", "M"):
            by_type[(sched, t)] += 1
        for bio, reg_id, office, share in targets:
            amt = amount * share
            if sched == "I":
                add_source(bio, reg_id, office, year, "loans", amt)
                continue
            if sched in ("E", "L", "S", "P"):
                add_source(bio, reg_id, office, year, "other", amt)                # interest and other receipts, expenditure refunds, public matching funds
                continue
            if sched == "G":
                name = ent or pname
                if not name:
                    add_source(bio, reg_id, office, year, "other", amt)
                    continue
                if row[IDX["TRANSFER_TYPE_DESC"]].startswith("Type 2") or own_committee(name, members[bio]) or donor_key(name) in own_ids.get(bio, ()):
                    moved[f"{name} -> {members[bio]['name']}"] += amt              # between the member's own committees: moved in, never a donor
                    gifts.append([bio, reg_id, office, year, date, round(amt, 2), reg_id, name, "cand", 0])
                    add_source(bio, reg_id, office, year, "cand", amt)
                    continue
                kind = org_kind(row, name) or "org"
                if kind == "biz" and not CORP.search(name):
                    kind = "party" if PARTY_WORD.search(name) else "pcf"           # a transfer comes from a committee, not a business
                did = donor_key(name)
                kinds_seen[did][kind] += 1
                gifts.append([bio, reg_id, office, year, date, round(amt, 2), did, name, kind, 0])
                add_source(bio, reg_id, office, year, kind, amt)
                continue
            if sched == "M":
                amt = -amt                                                         # a contribution refunded: netted against its giver
            in_kind = 1 if sched == "D" else 0
            if t in SELF:
                add_source(bio, reg_id, office, year, "self", amt)
                continue
            if t == "Unitemized" or row[IDX["R_ITEMIZED"]] == "N" or (t == "" and not ent and not pname) or LUMP.search(ent):
                add_source(bio, reg_id, office, year, "people" if (sched == "A" and not ent) else "other", amt)
                continue
            if t in PERSON or (not ent and pname):
                add_source(bio, reg_id, office, year, "self" if (pname and fits(bio, pname)) else "people", amt)
                continue
            name = ent or pname
            kind = org_kind(row, name)
            if kind is None:
                add_source(bio, reg_id, office, year, "people", amt)
                set_aside[name] += amt
                continue
            if kind == "cand" and (own_committee(name, members[bio]) or donor_key(name) in own_ids.get(bio, ())):
                moved[f"{name} -> {members[bio]['name']}"] += amt
                gifts.append([bio, reg_id, office, year, date, round(amt, 2), reg_id, name, "cand", in_kind])
                add_source(bio, reg_id, office, year, "cand", amt)
                continue
            did = donor_key(name)
            kinds_seen[did][kind] += 1
            gifts.append([bio, reg_id, office, year, date, round(amt, 2), did, name, kind, in_kind])
            add_source(bio, reg_id, office, year, kind, amt)
    for g in gifts:
        if g[6] in kinds_seen:
            g[8] = kinds_seen[g[6]].most_common(1)[0][0]

    # -- 4. store
    committees = []
    for cid, bio in whose.items():
        f = reg.get(cid, {})
        legs = [OFFICE[o] for o in comm_offices.get(cid, ()) if o in OFFICE]
        office = legs[0] if len(set(legs)) == 1 else members[bio]["chamber"]
        label = f.get("name") or cid
        if f.get("kind") == "CANDIDATE":
            label += " (filing as a candidate)"
        committees.append((f"ny:{cid}", label, office, bio))
    for cid, s in shared.items():
        f = reg.get(cid, {})
        legs = [OFFICE[o] for o in comm_offices.get(cid, ()) if o in OFFICE]
        for bio in s:
            office = legs[0] if len(set(legs)) == 1 else members[bio]["chamber"]
            committees.append((f"ny:{cid}:{bio}", f"{f.get('name') or cid} (shared by {shared_n[cid]} candidates)", office, bio))
    with con:
        for t in ("state_committees", "state_gifts", "state_sources", "state_outside"):
            con.execute(f"DELETE FROM {t}")
        con.executemany("INSERT INTO state_committees VALUES (?,?,?,?)", committees)
        con.executemany("INSERT INTO state_gifts (bioguide_id, committee, office, year, date, amount, donor_id, donor_name, donor_kind, in_kind) VALUES (?,?,?,?,?,?,?,?,?,?)", gifts)
        con.executemany("INSERT INTO state_sources VALUES (?,?,?,?,?,?,?)", [(*k, round(v[0], 2), v[1]) for k, v in sources.items()])
    by_source = dict(con.execute("SELECT source, ROUND(SUM(amount)) FROM state_sources GROUP BY 1"))
    print(f"    schedules seen: " + ", ".join(f"{k} {v:,}" for k, v in by_sched.most_common()))
    print(f"    Stored: {len(gifts):,} gifts from organizations (${sum(g[5] for g in gifts) / 1e6:,.1f}M); totals by source: "
          + ", ".join(f"{k} ${v / 1e6:,.1f}M" for k, v in sorted(by_source.items(), key=lambda kv: -kv[1])))
    print("    Outside spending: none loaded; the Board's Schedule R rows carry an office and a district but no candidate's name"
          + (f" ({sum(r_seen.values())} such rows were filed by these committees themselves, party spending allocated to races)" if r_seen else ""))
    top = con.execute("SELECT donor_name, donor_kind, ROUND(SUM(amount)) FROM state_gifts WHERE donor_id LIKE 'n-%' GROUP BY donor_id ORDER BY 3 DESC LIMIT 8").fetchall()
    print("    biggest named givers: " + "; ".join(f"{n[:60]} ({k}) ${a / 1e6:,.1f}M" for n, k, a in top))
    print("    giver types on the receipt schedules: " + ", ".join(f"{s} {t or 'blank'} {v:,}" for (s, t), v in by_type.most_common(16)))
    if set_aside:
        print(f"    organizations' rows whose name reads as a person's, counted with people ({len(set_aside)}): " + "; ".join(f"{n} ${a:,.0f}" for n, a in set_aside.most_common(10)))
    if moved:
        print(f"    moved in from the member's own other committee ({len(moved)}): " + "; ".join(f"{k} ${v:,.0f}" for k, v in moved.most_common(10)) + (" ..." if len(moved) > 10 else ""))
    if unknown_type:
        print("    schedules the loader does not read: " + ", ".join(f"{k} {v}" for k, v in unknown_type.most_common()))
    if by_seat:
        print(f"    matched by the seat alone, the family name being unique ({len(by_seat)}): " + "; ".join(by_seat))
    if other_office:
        print(f"    committees the Board ties to a member's run for another office, left out ({len(other_office)}): " + "; ".join(other_office[:10]) + (" ..." if len(other_office) > 10 else ""))
    if ambiguous:
        print(f"    left out, more than one member fits ({len(ambiguous)}): " + "; ".join(list(ambiguous.values())[:8]))
    unmatched = [m["name"] for bio, m in members.items() if bio not in matched]
    if unmatched:
        print(f"    sitting members with no account matched ({len(unmatched)}): " + ", ".join(sorted(unmatched)[:40]) + (" ..." if len(unmatched) > 40 else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
