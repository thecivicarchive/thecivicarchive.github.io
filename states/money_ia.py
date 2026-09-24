#!/usr/bin/env python3
"""
states/money_ia.py
==================
Iowa campaign money, from the Iowa Ethics and Campaign Disclosure Board's public datasets on data.iowa.gov (no
account; published under Creative Commons Attribution-NonCommercial, credit required; Iowa Code chapter 68A bars
commercial use of the lists, and this site is not commercial): every contribution received by every committee
since 2003 (dataset 917, about 3.2 million rows, 405 MB zipped), the register of committees (704) and independent
expenditures for or against candidates (966).

The same rule as the federal side and Minnesota. Organizations are named: political action committees, party
committees (Iowa's state and county central committees) and other candidates' committees, each recognised by the
committee number the Board assigned it. People are not. Every gift from an individual is added into a yearly total,
and the name on that row is never written to the database. A giver named in the file without a committee number
(a bank paying interest, a business, "Un-itemized") cannot be verified from the file, so it is totalled as "other"
and not named either. Independent expenditures go in their own table: the campaign never received that money, and
the free-text description of each is left out.

Committees are matched to sitting legislators by name and never guessed. The Board's register gives the candidate's
name, chamber and district for committees still registered; for committees that have since closed, the name comes
from the committee's own title ("Committee to Elect Zach Wahls", "Pellant for Iowa House"). A match needs the family
name, a compatible given name where one is written (Zach and Zachary), and a chamber the member has actually served
in, and it must be the only member who fits; where two fit, the register's district decides; anything less is
listed at the end of the run and left out.

  state_committees   each matched campaign committee: committee number, chamber, which member
  state_gifts        every gift from a registered committee to a matched committee
  state_sources      yearly totals by source for each matched committee (people, committees and funds, party
                     committees, other candidates, loans, other)
  state_outside      every independent expenditure for or against a matched committee

    python -m states.money_ia --db state_ia.sqlite --since 2015
"""

import argparse
import csv
import io
import os
import re
import sqlite3
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from states import net                                     # noqa: E402
from states.money_mn import norm, given_fits               # noqa: E402

BASE = "https://data.iowa.gov/api/dataset-download?path=datasets/{id}/rows.csv"
FILES = {"contributions.zip": "917", "committees.zip": "704", "independent_expenditures.zip": "966"}
CHAMBER = {"State House": "House", "State Senate": "Senate"}
PAC_TYPES = {"Iowa PAC", "County PAC", "City PAC", "School Board or Other Political Subdivision PAC"}
PARTY_TYPES = {"County Central Committee", "State Central Committee"}
LEAD = re.compile(r"^(the\s+)?((re-?)?elect|committee\s+to\s+(re-?)?elect|committee\s+for|friends\s+(of|for)|citizens\s+(for|to\s+elect)|iowans\s+(for|to\s+elect)|people\s+for|neighbors\s+for|team|vote)\s+", re.I)
TAILS = [re.compile(p, re.I) for p in (
    r"\s*-\s*dissolved\s*$", r"\s+aka\s+.*$", r"\s+20\d\d\s*$", r"-\d+\s*$",
    r"\s+(for|4)\s+(the\s+)?(iowa('s)?\s+|ia\s+)?(state\s+)?(house(\s+of\s+representatives?)?|senate|representative|rep\.?|senator|sen\.?|statehouse|legislature|iowa|iowans|hd|sd|hr|dist\.?|district)?(\s*-?\s*#?\d+(st|nd|rd|th|[a-z])?)?(\s+(dist\.?|district)(\s*\d+)?)?\s*$",
    r"\s+(state\s+)?(representative|senator)(\s*\d+)?\s*$", r"\s+(ia|iowa)\s+(house|senate)\s+dist\.?\s*\d+\s*$", r"\s+(hd|sd|hr)\s*-?\s*\d+\s*$",
    r"\s+(election|campaign)(\s+committee)?\s*$", r"\s+committee\s*$", r"\s+for\s+(southern|northern|eastern|western|central|north|south|east|west)(east|west)?\s+iowa\s*$")]
SUFFIX = re.compile(r"\s+(jr|sr|ii|iii|iv)\.?$", re.I)

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


def rows_of(zip_path):
    """Every row of every CSV inside one of the Board's zips (the contributions come in four parts)."""
    z = zipfile.ZipFile(zip_path)
    for name in sorted(z.namelist()):
        if name.lower().endswith(".csv"):
            with io.TextIOWrapper(z.open(name), encoding="utf-8", errors="replace", newline="") as fh:
                yield from csv.DictReader(fh)


def person_parts(text):
    """'Zach Wahls' -> ({'wahls'}, ['Zach']); 'Pellant' -> ({'pellant'}, []); 'Kelcey Brackett' likewise. Family names
    keep their parts (a two-word family name fits a member filed under either part)."""
    text = SUFFIX.sub("", " ".join((text or "").replace(",", " ").split()))
    parts = [p for p in re.split(r"\s+", text) if norm(p)]
    if not parts:
        return None
    family = parts[-1]
    families = {norm(family)} | {norm(x) for x in re.split(r"-", family) if len(norm(x)) > 3}
    if len(parts) >= 3 and len(norm(parts[-2])) > 3 and norm(parts[-2]) not in ("van", "von", "de", "la", "del", "mac", "mc"):
        families.add(norm(parts[-2] + parts[-1]))
    givens = [p for p in parts[:-1] if len(norm(p)) > 1]
    return families, givens


def name_from_title(title):
    """The candidate's name inside a committee title, or None when the title does not carry one: "Committee to Elect
    Zach Wahls" -> "Zach Wahls"; "Pellant for Iowa House" -> "Pellant"; "Cheevers4House" -> "Cheevers"."""
    t = " ".join((title or "").split())
    if re.search(r"\w\.\w", t):
        t = t.replace(".", " ")                                                # Keith.Puntenney4iasenatedistrict24
    t = re.sub(r"(?<=[A-Za-z])4(?=(iowa|house|senate|ia\b|state))", " for ", t, flags=re.I)      # Cheevers4House, Finn4Iowa
    t = re.sub(r"(?<=[a-z])for(?=iowa)", " for ", t, flags=re.I)                                  # VanfleetforIowaHousedistrict70
    t = re.sub(r"(ia|iowa)\s*(house|senate)\s*(district)?\s*(\d+)", r"\1 \2 \3 \4", t, flags=re.I)
    t = LEAD.sub("", t)
    for _ in range(6):
        t2 = t
        for pat in TAILS:
            t2 = pat.sub("", t2)
        if t2 == t:
            break
        t = t2
    t = t.strip(" -,")
    if not t or re.search(r"\d", t) or len(t.split()) > 4:
        return None
    return t


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", required=True)
    ap.add_argument("--cache-dir", default="states_cache")
    ap.add_argument("--since", type=int, default=2015, help="first year to keep (the 2016 cycle begins in January 2015)")
    args = ap.parse_args()
    folder = os.path.join(args.cache_dir, "ia_iecdb")
    for name, ds in FILES.items():
        path = os.path.join(folder, name)
        if net.download(BASE.format(id=ds), path, 3600):
            print(f"    fetched {name} ({os.path.getsize(path) / 1e6:,.1f} MB)")

    con = sqlite3.connect(args.db)
    con.executescript(SCHEMA)
    if not con.execute("SELECT 1 FROM sqlite_master WHERE name = 'legislators'").fetchone():
        sys.exit("No members yet. Run the people stage first.")
    members = {}
    for bio, first, last, full, others, district in con.execute("SELECT bioguide_id, first_name, last_name, official_full, other_names, district FROM legislators WHERE is_current = 1"):
        givens = {first, (full or "").split(" ")[0]} | {o.split(",")[-1].strip().split(" ")[0] if "," in o else o.split(" ")[0] for o in (others or "").split(";") if o.strip()}
        members[bio] = {"family": {norm(last), norm((full or "").split(" ")[-1])}, "given": {g for g in givens if g and len(norm(g)) > 1}, "name": full, "district": str(district or "")}
    served = {}
    for bio, typ in con.execute("SELECT DISTINCT bioguide_id, type FROM member_terms"):
        served.setdefault(bio, set()).add({"rep": "House", "sen": "Senate"}.get(typ, typ))

    # -- the register: what kind of committee each number is, and the candidate behind a legislative one
    register = {}
    for r in rows_of(os.path.join(folder, "committees.zip")):
        register[(r.get("committee_number") or "").strip()] = {"type": (r.get("committee_type") or "").strip(), "name": " ".join((r.get("committee_name") or "").split()),
                                                              "candidate": " ".join((r.get("candidate_name") or "").split()), "district": (r.get("district") or "").strip()}

    # -- one pass over 3.2 million rows: keep what went to a House or Senate campaign in the window
    kept, titles, malformed, n = [], {}, 0, 0
    for r in rows_of(os.path.join(folder, "contributions.zip")):
        n += 1
        tt = r.get("transaction_type") or ""
        if tt not in ("CON", "INK", "LOANREC"):
            malformed += 1
            continue
        chamber = CHAMBER.get((r.get("committee_type") or "").strip())
        if not chamber:
            continue
        date = (r.get("contribution_received_date") or "")[:10]
        year = int(date[:4]) if date[:4].isdigit() else 0
        if year < args.since:
            continue
        try:
            amount = float(r.get("amount") or 0)
        except ValueError:
            continue
        if not amount:
            continue
        code = (r.get("committee_cd") or "").strip()
        titles.setdefault(code, (" ".join((r.get("committee_nm") or "").split()), chamber))
        kept.append((code, year, date, amount, tt, (r.get("contr_committee_cd") or "").strip(), " ".join((r.get("organization_nm") or "").split()),
                     bool((r.get("last_nm") or "").strip() or (r.get("first_nm") or "").strip())))
    print(f"    {n:,} contribution rows read ({malformed} malformed and skipped); {len(kept):,} to House and Senate campaigns since {args.since}, {len(titles):,} committees")

    # -- which committee is whose
    whose, unsure, by_family_only, other_office, unparsed = {}, [], [], [], []
    parsed = {}
    for code, (title, chamber) in titles.items():
        reg = register.get(code)
        texts = [t for t in ((reg or {}).get("candidate"), name_from_title(title)) if t]       # the register's name first, then the title's own
        parsed[code] = ([person_parts(t) for t in texts], chamber, (reg or {}).get("district", ""), title, bool((reg or {}).get("candidate")))

    def who(parts, chamber, district):
        """(the one member who fits, how) or (None, why): family name, a compatible given name, a chamber served."""
        families, givens = parts
        same_family = [bio for bio, m in members.items() if families & m["family"] and chamber in served.get(bio, ())]
        fits = [bio for bio in same_family if any(given_fits(c, g) for c in givens for g in members[bio]["given"])] if givens else same_family
        if len(fits) > 1 and district:
            narrowed = [bio for bio in fits if members[bio]["district"] == district]
            if len(narrowed) == 1:
                fits = narrowed
        if len(fits) == 1:
            return fits[0], ("family" if not givens else "full")
        if len(fits) > 1:
            return None, f"fits {', '.join(members[b]['name'] for b in fits)}"
        if len(same_family) == 1 and givens:
            # the given names do not line up (a nickname the roster does not carry); accept the family name alone only
            # when nobody else could be meant: one sitting member has it in that chamber, and every committee title
            # under that family name in that chamber resolves to the same person
            people = {norm(" ".join(pp[1][:1])) for p in parsed.values() if p[1] == chamber for pp in p[0] if pp and pp[0] & families}
            if len(people) == 1:
                return same_family[0], "family"
        return None, ""

    for code, (parts_list, chamber, district, title, registered) in parsed.items():
        parts_list = [p for p in parts_list if p]
        if not parts_list:
            unparsed.append(title)
            continue
        hit, how, why = None, "", ""
        for parts in parts_list:
            hit, how = who(parts, chamber, district)
            if hit:
                break
            why = why or how
        if not hit and registered:
            # a sitting member's committee for another office (a representative running for the Senate): the register
            # names the candidate, so accept it when exactly one sitting member carries that full name in any chamber
            families, givens = parts_list[0]
            fits = [bio for bio, m in members.items() if families & m["family"] and givens and any(given_fits(c, g) for c in givens for g in m["given"])]
            if len(fits) == 1:
                hit, how = fits[0], "other office"
        if hit:
            whose[code] = (hit, chamber, title)
            if how == "family":
                by_family_only.append(f"{title} -> {members[hit]['name']}")
            elif how == "other office":
                other_office.append(f"{title} ({chamber}) -> {members[hit]['name']}")
        elif why.startswith("fits"):
            unsure.append(f"{title}: {why}")
    matched = {b for b, _c, _t in whose.values()}
    print(f"    {len(titles):,} House and Senate committees on file; {len(whose):,} matched to {len(matched):,} of {len(members):,} sitting members")

    # -- gifts and totals
    kind_of = {}
    for code, reg in register.items():
        t = reg["type"]
        kind_of[code] = "pcf" if t in PAC_TYPES else ("party" if t in PARTY_TYPES else "cand")
    guess_kind = lambda name: ("party" if re.search(r"central committee|democrat|republican|party\b", name, re.I) else
                               ("cand" if re.search(r"\bfor\b|committee to elect|friends (of|for)|citizens for|\belect\b", name, re.I) else "pcf"))
    gifts, sources = [], {}
    for code, year, date, amount, tt, giver_code, org, is_person in kept:
        hit = whose.get(code)
        if not hit:
            continue
        bio, chamber, _title = hit
        if tt == "LOANREC":
            source = "loans"
        elif giver_code:
            source = kind_of.get(giver_code) or guess_kind(org or (register.get(giver_code) or {}).get("name", ""))
        elif is_person and not org:
            source = "people"
        else:
            source = "other"                                       # an organization the file cannot vouch for, or an unitemized sum
        s = sources.setdefault((bio, code, chamber, year, source), [0.0, 0])
        s[0] += amount; s[1] += 1
        if source in ("pcf", "party", "cand"):                     # a registered committee: named. Everyone else stays a total.
            gname = (register.get(giver_code) or {}).get("name") or org or giver_code
            gifts.append((bio, code, chamber, year, date or None, amount, giver_code, gname, source, 1 if tt == "INK" else 0))
    outside = []
    for r in rows_of(os.path.join(folder, "independent_expenditures.zip")):
        target, side = (r.get("for_candidate") or "").strip(), "for"
        if not target:
            target, side = (r.get("against_candidate") or "").strip(), "against"
        m = re.match(r"^#?([A-Z]*\d+)\s*-", target)
        if not m or m.group(1) not in whose:
            continue
        date = (r.get("expenditure_date") or "")[:10]
        year = int(date[:4]) if date[:4].isdigit() else 0
        try:
            amount = float(r.get("amount") or 0)
        except ValueError:
            continue
        if year < args.since or not amount:
            continue
        code = m.group(1)
        spender = " ".join((r.get("organization_name") or "").split())
        outside.append((whose[code][0], code, year, date or None, amount, side, norm(spender)[:40] or "unknown", spender, guess_kind(spender) if not re.search(r"\bfor\b", spender, re.I) else "pcf",
                        (r.get("description_of_communication") or "")[:120]))
    with con:
        for t in ("state_committees", "state_gifts", "state_sources", "state_outside"):
            con.execute(f"DELETE FROM {t}")
        con.executemany("INSERT INTO state_committees VALUES (?,?,?,?)", [(code, title, chamber, bio) for code, (bio, chamber, title) in whose.items()])
        con.executemany("INSERT INTO state_gifts (bioguide_id, committee, office, year, date, amount, donor_id, donor_name, donor_kind, in_kind) VALUES (?,?,?,?,?,?,?,?,?,?)", gifts)
        con.executemany("INSERT INTO state_sources VALUES (?,?,?,?,?,?,?)", [(*k, round(v[0], 2), v[1]) for k, v in sources.items()])
        con.executemany("INSERT INTO state_outside (bioguide_id, committee, year, date, amount, side, spender_id, spender_name, spender_kind, purpose) VALUES (?,?,?,?,?,?,?,?,?,?)", outside)
    by_source = dict(con.execute("SELECT source, ROUND(SUM(amount)) FROM state_sources GROUP BY 1"))
    print(f"    Stored: {len(gifts):,} gifts from organizations (${sum(g[5] for g in gifts) / 1e6:,.1f}M); itemized totals by source: "
          + ", ".join(f"{k} ${v / 1e6:,.1f}M" for k, v in sorted(by_source.items(), key=lambda kv: -kv[1])))
    print(f"    Outside spending: {len(outside):,} payments, ${sum(o[4] for o in outside if o[5] == 'for') / 1e6:,.1f}M for and "
          f"${sum(o[4] for o in outside if o[5] == 'against') / 1e6:,.1f}M against sitting members")
    unmatched = [m["name"] for bio, m in members.items() if bio not in matched]
    if other_office:
        print(f"    a sitting member's committee for another office ({len(other_office)}): " + "; ".join(other_office[:8]) + (" ..." if len(other_office) > 8 else ""))
    if by_family_only:
        print(f"    matched on the family name alone ({len(by_family_only)}): " + "; ".join(by_family_only[:12]) + (" ..." if len(by_family_only) > 12 else ""))
    if unsure:
        print(f"    left out, more than one member fits ({len(unsure)}): " + "; ".join(unsure[:8]) + (" ..." if len(unsure) > 8 else ""))
    if unparsed:
        print(f"    committee titles with no name to match ({len(unparsed)}): " + "; ".join(sorted(unparsed)[:10]) + (" ..." if len(unparsed) > 10 else ""))
    if unmatched:
        print(f"    sitting members with no committee matched ({len(unmatched)}): " + ", ".join(sorted(unmatched)[:20]) + (" ..." if len(unmatched) > 20 else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
