#!/usr/bin/env python3
"""
states/money_mn.py
==================
Minnesota campaign money, from the Campaign Finance and Public Disclosure Board's public downloads (cfb.mn.gov,
no account): itemized contributions to candidates (every gift over $200, 2015 on) and independent expenditures
for or against candidates.

The same rule as the federal side. Organizations are named: political committees and funds, party units, other
candidates' committees. People are not. Every row from an individual, a registered lobbyist (a person) or the
candidate is added into a yearly total by source, and the name on that row is never written to the database.
Independent expenditures go in their own table: the campaign never received that money.

Committees are matched to sitting legislators by name: "Howe, Jeff Senate Committee" is family name, given name,
office. A match needs the family name, a compatible given name (Zach and Zachary, Bill and William) and a chamber
that member has actually served in, and it must be the only member who fits; anything less is listed at the end
of the run and left out, never guessed. Committees for other offices (Governor, Attorney General, judges) are not
matched in this version.

  state_committees   each matched campaign committee: registration number, office, which member
  state_gifts        every itemized gift from an organization to a matched committee
  state_sources      yearly totals by source for each matched committee (people, lobbyists, committees and funds,
                     party units, other candidates, the candidate, loans, other)
  state_outside      every independent expenditure for or against a matched committee

    python -m states.money_mn --db state_mn.sqlite
"""

import argparse
import csv
import os
import re
import sqlite3
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from states import net                     # noqa: E402

BASE = "https://cfb.mn.gov/reports-and-data/self-help/data-downloads/campaign-finance/?download="
FILES = {"contributions_candidates.csv": "-2026985457", "independent_expenditures_all.csv": "-617535497"}
ORG = {"Political Committee/Fund": "pcf", "Party Unit": "party", "Candidate Committee": "cand"}
PERSON = {"Individual": "people", "Lobbyist": "lobbyists", "Self": "self"}
SPENDER = {"PTU": "party", "PCF": "pcf", "PCC": "cand"}
NICK = [{"william", "bill", "will"}, {"robert", "bob", "rob", "bobby"}, {"james", "jim", "jimmy"}, {"thomas", "tom"}, {"michael", "mike"},
        {"david", "dave"}, {"steven", "stephen", "steve"}, {"elizabeth", "liz", "beth", "betsy"}, {"katherine", "kathryn", "kathleen", "kathy", "kate", "katie"},
        {"patricia", "pat", "patty", "tricia"}, {"patrick", "pat"}, {"matthew", "matt"}, {"daniel", "dan", "danny"}, {"andrew", "andy", "drew"},
        {"richard", "rick", "rich", "dick"}, {"gregory", "greg"}, {"jeffrey", "jeff"}, {"ronald", "ron"}, {"timothy", "tim"}, {"samuel", "samantha", "sam"},
        {"benjamin", "ben"}, {"nicholas", "nick"}, {"joseph", "joe"}, {"jennifer", "jen", "jenny"}, {"susan", "sue"}, {"christopher", "chris"},
        {"christine", "christina", "chris"}, {"anthony", "tony"}, {"edward", "ed", "eddie"}, {"kenneth", "ken"}, {"lawrence", "larry"}, {"peter", "pete"},
        {"donald", "don"}, {"douglas", "doug"}, {"gerald", "jerry"}, {"john", "jon", "jack"}, {"charles", "chuck", "charlie"}, {"nathan", "nate"},
        {"zachary", "zach", "zack"}, {"joshua", "josh"}, {"jacob", "jake"}, {"alexander", "alex"}, {"rebecca", "becky"}, {"deborah", "debra", "deb"},
        {"margaret", "peggy", "maggie", "meg"}, {"pamela", "pam"}, {"cynthia", "cindy"}, {"judith", "judy"}, {"bradley", "brad"}, {"frederick", "fred"},
        {"sandra", "sandy"}, {"bernadette", "bernard", "bernie"}, {"virginia", "ginny"}, {"patricia", "patti", "patty"}, {"james", "jamie"},
        {"alexandra", "ali", "alex", "lexi"}]

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


def norm(text):
    """Lower case, accents folded (Maria for María), letters only."""
    plain = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z]", "", plain.lower())


def given_fits(a, b):
    a, b = norm(a), norm(b)
    if not a or not b:
        return False
    if a == b or (len(a) >= 3 and b.startswith(a)) or (len(b) >= 3 and a.startswith(b)):
        return True
    return any(a in s and b in s for s in NICK)


def parse_committee(name):
    """'Klevorn, Virginia (Ginny) House Committee' -> ({'klevorn'}, ['Virginia', 'Ginny'], 'House').
    Family names keep their parts ('Momanyi Hiltsley' fits a member filed under Hiltsley); every given name,
    middle name and nickname in brackets counts. None for anything that is not a House or Senate campaign."""
    m = re.match(r"^\s*(.+?),\s*(.+?)\s+(House|Senate)\s+Committee\s*$", name or "")
    if not m:
        return None
    family = re.sub(r"\s+(Jr|Sr|II|III|IV)\.?$", "", m.group(1).strip(), flags=re.I)
    given = re.sub(r"\s+(Jr|Sr|II|III|IV)\.?$", "", m.group(2).strip(), flags=re.I)
    families = {norm(family)} | {norm(x) for x in re.split(r"[\s-]+", family) if len(norm(x)) > 3}
    givens = [g for g in re.split(r"[\s()]+", given) if len(norm(g)) > 1]
    return families, givens, m.group(3)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", required=True)
    ap.add_argument("--cache-dir", default="states_cache")
    ap.add_argument("--since", type=int, default=2015, help="first year to keep (the Board's files begin in 2015)")
    args = ap.parse_args()
    folder = os.path.join(args.cache_dir, "mn_cfb")
    for name, code in FILES.items():
        path = os.path.join(folder, name)
        if net.download(BASE + code, path, 7):
            print(f"    fetched {name} ({os.path.getsize(path) / 1e6:,.1f} MB)")

    con = sqlite3.connect(args.db)
    con.executescript(SCHEMA)
    if not con.execute("SELECT 1 FROM sqlite_master WHERE name = 'legislators'").fetchone():
        sys.exit("No members yet. Run the people stage first.")
    members = {}
    for bio, first, last, full, others in con.execute("SELECT bioguide_id, first_name, last_name, official_full, other_names FROM legislators WHERE is_current = 1"):
        givens = {first, (full or "").split(" ")[0]} | {o.split(",")[-1].strip().split(" ")[0] if "," in o else o.split(" ")[0] for o in (others or "").split(";") if o.strip()}
        members[bio] = {"family": {norm(last), norm((full or "").split(" ")[-1])}, "given": {g for g in givens if g}, "name": full}
    served = {}
    for bio, typ in con.execute("SELECT DISTINCT bioguide_id, type FROM member_terms"):
        served.setdefault(bio, set()).add({"rep": "House", "sen": "Senate"}.get(typ, typ))

    # -- which committee is whose
    names = {}
    with open(os.path.join(folder, "contributions_candidates.csv"), newline="", encoding="utf-8", errors="replace") as fh:
        for r in csv.DictReader(fh):
            names.setdefault(r["Recipient reg num"], r["Recipient"])
    with open(os.path.join(folder, "independent_expenditures_all.csv"), newline="", encoding="utf-8", errors="replace") as fh:
        for r in csv.DictReader(fh):
            if r.get("Affected Cmte Reg Num"):
                names.setdefault(r["Affected Cmte Reg Num"], r.get("Affected Comte Name") or "")
    whose, unsure, by_family_only = {}, [], []
    parsed_all = {reg: parse_committee(name) for reg, name in names.items()}
    for reg, name in names.items():
        parsed = parsed_all[reg]
        if not parsed:
            continue
        families, givens, office = parsed
        same_family = [bio for bio, m in members.items() if families & m["family"] and office in served.get(bio, ())]
        fits = [bio for bio in same_family if any(given_fits(c, g) for c in givens for g in members[bio]["given"])]
        if len(fits) == 1:
            whose[reg] = (fits[0], office, name)
        elif len(fits) > 1:
            unsure.append(f"{name}: fits {', '.join(members[b]['name'] for b in fits)}")
        elif len(same_family) == 1:
            # The given names do not line up (Liish for Alicia, Ripper for Aaron). Accept the family name alone only
            # when nobody else could be meant: one sitting member has it, and every committee under that family name
            # in the Board's files is for one and the same person.
            people = {norm(" ".join(pa[1][:1])) for pa in parsed_all.values() if pa and pa[0] & families}
            if len(people) == 1:
                whose[reg] = (same_family[0], office, name)
                by_family_only.append(f"{name} -> {members[same_family[0]]['name']}")
    matched = {b for b, _o, _n in whose.values()}
    print(f"    {len(names):,} campaign committees on file; {len(whose):,} matched to {len(matched):,} of {len(members):,} sitting members")

    # -- gifts and totals
    gifts, sources = [], {}
    with open(os.path.join(folder, "contributions_candidates.csv"), newline="", encoding="utf-8", errors="replace") as fh:
        for r in csv.DictReader(fh):
            hit = whose.get(r["Recipient reg num"])
            if not hit:
                continue
            bio, office, _name = hit
            try:
                amount, year = float(r["Amount"] or 0), int(r["Year"] or 0)
            except ValueError:
                continue
            if year < args.since or not amount:
                continue
            kind, receipt = r["Contrib type"], (r["Receipt type"] or "").replace(" ", "").lower()
            if receipt.startswith("loan"):
                source = "loans"
            elif receipt.startswith("misc"):
                source = "other"
            else:
                source = ORG.get(kind) or PERSON.get(kind) or "other"
            s = sources.setdefault((bio, r["Recipient reg num"], office, year, source), [0.0, 0])
            s[0] += amount; s[1] += 1
            if source in ("pcf", "party", "cand"):                 # an organization: named. Everyone else stays a total.
                gifts.append((bio, r["Recipient reg num"], office, year, r["Receipt date"] or None, amount, r["Contrib Reg Num"] or "",
                              " ".join((r["Contributor"] or "").split()), source, 1 if (r["In kind?"] or "").lower().startswith("y") else 0))
    outside = []
    with open(os.path.join(folder, "independent_expenditures_all.csv"), newline="", encoding="utf-8", errors="replace") as fh:
        for r in csv.DictReader(fh):
            hit = whose.get(r.get("Affected Cmte Reg Num") or "")
            if not hit:
                continue
            try:
                amount, year = float(r["Amount"] or 0), int(r["Year"] or 0)
            except ValueError:
                continue
            if year < args.since or not amount:
                continue
            side = "for" if (r.get("For /Against") or "").strip().lower() == "for" else "against"
            outside.append((hit[0], r["Affected Cmte Reg Num"], year, r["Date"] or None, amount, side, r["Spender Reg Num"] or "",
                            " ".join((r["Spender"] or "").split()), SPENDER.get(r["Spender type"], "other"), (r["Purpose"] or "")[:120]))
    with con:
        for t in ("state_committees", "state_gifts", "state_sources", "state_outside"):
            con.execute(f"DELETE FROM {t}")
        con.executemany("INSERT INTO state_committees VALUES (?,?,?,?)", [(reg, name, office, bio) for reg, (bio, office, name) in whose.items()])
        con.executemany("INSERT INTO state_gifts (bioguide_id, committee, office, year, date, amount, donor_id, donor_name, donor_kind, in_kind) VALUES (?,?,?,?,?,?,?,?,?,?)", gifts)
        con.executemany("INSERT INTO state_sources VALUES (?,?,?,?,?,?,?)", [(*k, round(v[0], 2), v[1]) for k, v in sources.items()])
        con.executemany("INSERT INTO state_outside (bioguide_id, committee, year, date, amount, side, spender_id, spender_name, spender_kind, purpose) VALUES (?,?,?,?,?,?,?,?,?,?)", outside)
    by_source = dict(con.execute("SELECT source, ROUND(SUM(amount)) FROM state_sources GROUP BY 1"))
    print(f"    Stored: {len(gifts):,} gifts from organizations (${sum(g[5] for g in gifts) / 1e6:,.1f}M); itemized totals by source: "
          + ", ".join(f"{k} ${v / 1e6:,.1f}M" for k, v in sorted(by_source.items(), key=lambda kv: -kv[1])))
    print(f"    Outside spending: {len(outside):,} payments, ${sum(o[4] for o in outside if o[5] == 'for') / 1e6:,.1f}M for and "
          f"${sum(o[4] for o in outside if o[5] == 'against') / 1e6:,.1f}M against sitting members")
    missing = sorted(members[b]["name"] for b in members if b not in matched)
    if missing:
        print(f"    No committee matched for {len(missing)} member(s): {', '.join(missing[:14])}{' ...' if len(missing) > 14 else ''}")
    for u in unsure[:8]:
        print(f"    left out, more than one member fits: {u}")
    if by_family_only:
        print(f"    matched on family name alone, because no one else in the Board's files shares it: {'; '.join(sorted(set(by_family_only)))}")


if __name__ == "__main__":
    main()
