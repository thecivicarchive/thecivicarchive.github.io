#!/usr/bin/env python3
"""
states/money_fl.py
==================
Florida campaign money, from the Division of Elections' campaign finance database (dos.elections.myflorida.com). The
Division publishes no bulk file; its public query form answers a plain request with a tab-separated file of every
contribution a candidate's campaign account reported, and that is what this loader asks for: one query per family
name among the sitting legislators, every election and office, cached in states_cache/fl_dos/ and refreshed monthly.
Each row carries the candidate's account (name, party and office), the date, amount and type of the contribution,
the giver's name and occupation. Florida requires campaigns to itemize every contribution, so there is no threshold.

The same rule as everywhere on the site. Organizations are named: political committees, party committees, other
candidates' campaigns, and the businesses, unions and associations Florida lets give directly. People are not named:
every gift from an individual goes into a yearly total, and the name on that row is never written to the database;
a gift or loan from the candidate is the candidate's own. The Division's file has no code for what kind of giver a
row is, so an organization is recognised by its name (a committee's or party's words, or a company's) or by an
occupation column that says "political committee"; a giver whose name shows neither is counted with people. A
business written without such a word may be hidden this way; a person is never shown.

What counts as the member's campaign: every account the member opened for a State House or State Senate race, found
by the Division's own candidate record (family name, a fitting given name, office STR or STS), and only those; a
political committee a legislator chairs is a separate filer and is not here, nor is a local or statewide race.

No outside spending is loaded for Florida: the Division's expenditure records name the payee and the purpose of what
a committee spent, not the candidate it spent for or against. The page says so.

  state_committees   each campaign account read as the member's: an id built from the Division's candidate string
  state_gifts        every gift from an organization to one of those accounts
  state_sources      yearly totals by source (people, committees, party, other candidates, other organizations,
                     own money, loans, other)
  state_outside      empty for Florida (see above)

    python -m states.money_fl --db state_fl.sqlite --since 2015
"""

import argparse
import collections
import os
import re
import sqlite3
import sys
import time
import unicodedata
import urllib.parse
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from states import net                                     # noqa: E402
from states.money_mn import norm, given_fits               # noqa: E402
from states.money_tx import families_of, givens_of, initials_fit   # noqa: E402
from states.money_ca import People, STRONG_ORG, CAND_WORD, name_tokens   # noqa: E402

URL = "https://dos.elections.myflorida.com/cgi-bin/contrib.exe"
REFERER = "https://dos.elections.myflorida.com/campaign-finance/contributions/"
OFFICE = {"STR": "House", "STS": "Senate"}
PARTY_CODE = {"REP": "R", "DEM": "D", "NPA": "I", "IND": "I", "LPF": "L", "GRE": "G"}
CAND = re.compile(r"^(?P<last>[^,]+),\s*(?P<first>.*?)\s*\((?P<party>[A-Z]{2,4})\)\((?P<office>[A-Z]{3})\)\s*$")
MONETARY = {"CHE", "CAS", "MO", "CC", "COF", "CHK", "CRE", "WIR", "EFT"}
FL_PARTY = re.compile(r"\b(republican|democratic|democrat|libertarian|green|independent) party\b|\bparty of florida\b|\b(republican|democratic|democrat) (state |county )?executive comm\w*\b|"
                      r"\b(republican|democratic|democrat) (house|senate|senatorial|legislative) (campaign )?comm\w*\b|\b(house|senate) (republican|democratic) (campaign )?comm\w*\b|"
                      r"\b(rec|dec|rpof|fdp)\b", re.I)
FL_PCF_NAME = re.compile(r"\bpac\b|political (action )?committee|political committe\b|\bp\.?c\.?$|\beco\b|committee of continuous existence|\bcce\b|\bfund\b|\balliance\b|"
                         r"\bcoalition\b|\bcitizens for\b|\bfloridians for\b|\bfriends of florida\b|\bfor a (better|stronger) florida\b|\bleadership\b|\bvoters?\b|\bconservatives\b", re.I)
FL_PCF_OCC = re.compile(r"political (action )?committee|political committe\b|\bpac\b|^pc$|\bpc\b|\beco\b|\bcce\b|electioneering|\bcommittee\b", re.I)
FL_PARTY_OCC = re.compile(r"\bparty\b|executive committee", re.I)
FL_ORG = re.compile(r"\b(co|corp|inc|llc|pa|pl|pllc|lp|llp|ltd|dba|assn|assoc|intl|mfg|dist|svcs?|ent|holdings?|grp)\b", re.I)   # the abbreviations Florida filers use


def fold(text):
    """Accents off, for a form that reads plain letters: López -> Lopez."""
    return unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()

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
    m = re.match(r"\s*(\d{1,2})/(\d{1,2})/(\d{4})", text or "")
    return f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}" if m else None


def query(family, folder, max_age_days=30, say=print):
    """The Division's contribution records for every candidate whose family name begins with `family`, all elections
    and offices, as the Division's own tab-separated file. Cached; asked again after max_age_days."""
    path = os.path.join(folder, "name_" + (re.sub(r"[^a-z]", "", norm(family)) or "blank") + ".tsv")
    if os.path.exists(path) and (time.time() - os.path.getmtime(path)) < max_age_days * 86400:
        return open(path, encoding="utf-8", errors="replace").read()
    net.patient_lookups()
    fields = {"election": "All", "search_on": "1", "CanFName": "", "CanLName": fold(family), "CanNameSrch": "1", "office": "All", "cdistrict": "", "cgroup": "", "party": "All",
              "ComName": "", "ComNameSrch": "2", "committee": "All", "cfname": "", "clname": "", "namesearch": "2", "ccity": "", "cstate": "", "czipcode": "", "coccupation": "",
              "cdollar_minimum": "", "cdollar_maximum": "", "rowlimit": "", "cdatefrom": "", "cdateto": "", "csort1": "NAM", "csort2": "CAN", "queryformat": "2", "Submit": "Submit"}
    req = Request(URL, data=urllib.parse.urlencode(fields).encode(), method="POST",
                  headers={"User-Agent": net.UA, "Referer": REFERER, "Content-Type": "application/x-www-form-urlencoded", "Accept": "text/tab-separated-values,text/plain,*/*"})
    for attempt in range(4):
        try:
            with urlopen(req, timeout=300) as r:
                text = r.read().decode("utf-8", "replace")
            break
        except (HTTPError, URLError, OSError) as e:
            if attempt == 3:
                if os.path.exists(path):
                    say(f"      could not refresh {family} ({e}); using the copy on disk")
                    return open(path, encoding="utf-8", errors="replace").read()
                raise
            say(f"      {family}: {e}; trying again in {15 * (attempt + 1)} s")
            time.sleep(15 * (attempt + 1))
    if not text.startswith("Candidate/Committee"):
        raise SystemExit(f"The Division answered the query for {family!r} with something other than its tab-separated file; try again later.")
    os.makedirs(folder, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    time.sleep(1.5)
    return text


def firsts_of(text):
    """'Rodolfo "Rudy"' -> ['Rodolfo', 'Rudy']; 'Franscine C.' -> ['Franscine', 'C']."""
    return [t for t in re.findall(r"[A-Za-z][A-Za-z'\-]*", text or "") if t]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", required=True)
    ap.add_argument("--cache-dir", default="states_cache")
    ap.add_argument("--since", type=int, default=2015, help="first year to keep (the 2016 cycle begins in January 2015)")
    args = ap.parse_args()
    t0 = time.time()
    folder = os.path.join(args.cache_dir, "fl_dos")
    con = sqlite3.connect(args.db)
    con.executescript(SCHEMA)
    if not con.execute("SELECT 1 FROM sqlite_master WHERE name = 'legislators'").fetchone():
        sys.exit("No members yet. Run the people stage first.")
    members = {}
    for bio, first, last, full, others, district, chamber, party, first_term in con.execute(
            "SELECT bioguide_id, first_name, last_name, official_full, other_names, district, chamber, party, first_term_start FROM legislators WHERE is_current = 1"):
        names = [o.strip() for o in (others or "").split(";") if o.strip()]
        givens = {first, (full or "").split(" ")[0]} | {o.split(",")[-1].strip().split(" ")[0] if "," in o else o.split(" ")[0] for o in names}
        givens |= {q for o in names for q in re.findall(r'"([^"]+)"', o)}                       # 'Robert Alexander "Alex" Andrade'
        fams = families_of(last) | {norm((full or "").split(" ")[-1])}
        for o in names:
            if "," in o:
                fams |= families_of(o.split(",")[0])
            elif " " in o and "." not in o:
                fams |= families_of(re.sub(r'"[^"]*"\s*', "", o).split(" ", 1)[1])
        members[bio] = {"family": {f for f in fams if f}, "given": {g for g in givens if g and len(norm(g)) > 1 and "." not in g}, "name": full, "last": last,
                        "initials": norm(first) if "." in (first or "") else "",              # "J.J." is how J.J. Grow files
                        "first_year": int(first_term[:4]) if first_term and first_term[:4].isdigit() else None,
                        "district": str(district or "").lstrip("0"), "chamber": chamber, "party": party}

    # -- 1. one query per family name; every candidacy for the State House or Senate whose name fits exactly one sitting member
    to_ask = set()
    for m in members.values():                                              # "Hart-Lowman" is filed as Hart; "Kincart Jonsson" may be filed either way
        to_ask.add(m["last"])
        to_ask |= {part for part in re.split(r"[\s\-]+", m["last"]) if len(part) > 2}
    to_ask = sorted(to_ask)
    print(f"    asking the Division for {len(to_ask)} family names ({time.time() - t0:.0f} s)", flush=True)
    rows_by_key, key_name, key_bio, key_party, ambiguous, seen_strings = collections.defaultdict(list), {}, {}, {}, {}, set()
    n_q = 0
    for family in to_ask:
        text = query(family, folder)
        n_q += 1
        if n_q % 25 == 0:
            print(f"    {n_q} of {len(to_ask)} names asked ({time.time() - t0:.0f} s)", flush=True)
        for line in text.split("\n")[1:]:
            f = line.rstrip("\r").split("\t")
            if len(f) < 9:
                continue
            cand = f[0].strip()
            m = CAND.match(cand)
            if not m or m.group("office") not in OFFICE:
                continue
            last, firsts = m.group("last").strip(), firsts_of(m.group("first"))
            key = (norm(last), norm(firsts[0]) if firsts else "", m.group("office"))
            if key not in key_bio and key not in ambiguous:
                fam = norm(last)
                fits = [bio for bio, mm in members.items() if fam in mm["family"]
                        and (any(given_fits(c, g) for c in firsts for g in mm["given"]) or any(initials_fit(firsts, g) for g in mm["given"])
                             or (mm["initials"] and norm(m.group("first")) == mm["initials"]))]
                if len(fits) == 1:
                    key_bio[key] = fits[0]
                    key_name[key] = collections.Counter()
                    key_party[key] = m.group("party")
                elif len(fits) > 1:
                    ambiguous[key] = f"{cand}: fits {', '.join(members[b]['name'] for b in fits)}"
                    continue
                else:
                    continue
            if key in key_bio:
                key_name[key][cand] += 1
                rows_by_key[key].append(f)
    # a namesake: an account of another party whose activity overlaps, year for year, with the member's own account for the
    # same office is somebody else (a member who changed party has one account after the other, never two at once)
    def years_of(rows):
        return {int(f[1][-4:]) for f in rows if re.match(r"\d{1,2}/\d{1,2}/\d{4}", f[1] or "")}
    namesakes, idle = [], 0
    for key in list(key_bio):
        bio, years = key_bio[key], years_of(rows_by_key[key])
        if not years or max(years) < args.since:
            idle += 1                                                          # nothing in the window: not shown, not counted
            del key_bio[key], key_name[key], key_party[key], rows_by_key[key]
            continue
        if PARTY_CODE.get(key_party[key], key_party[key]) == members[bio]["party"]:
            continue
        same_party = [k for k in key_bio if key_bio[k] == bio and k != key and k[2] == key[2] and PARTY_CODE.get(key_party[k], key_party[k]) == members[bio]["party"]]
        overlap = any(years & years_of(rows_by_key[k]) for k in same_party)
        before = members[bio]["first_year"] and max(years) < members[bio]["first_year"]
        if overlap or before:
            namesakes.append(f"{key_name[key].most_common(1)[0][0]} ({'active in the same years as' if overlap else 'over before'} {members[bio]['name']}'s own {members[bio]['party']} account)")
            del key_bio[key], key_name[key], key_party[key], rows_by_key[key]
    matched = set(key_bio.values())
    print(f"    {len(key_bio)} House and Senate campaign accounts fit {len(matched)} of {len(members)} sitting members; {idle} older accounts with nothing since {args.since} set aside ({time.time() - t0:.0f} s)")

    # -- 2. the rows: people and the candidate as totals, organizations by name
    people = People()
    gifts, sources, kinds_seen = [], {}, collections.defaultdict(collections.Counter)
    n_rows = n_kept = 0
    by_type = collections.Counter()
    set_aside = collections.Counter()

    def add_source(bio, reg, chamber, year, source, amount):
        s = sources.setdefault((bio, reg, chamber, year, source), [0.0, 0])
        s[0] += amount
        s[1] += 1

    def own(tokens, bio):
        fam, giv = members[bio]["family"], members[bio]["given"]
        toks = [norm(t) for t in tokens if len(norm(t)) > 1]
        return any(t in fam for t in toks) and any(given_fits(t, g) for t in tokens for g in giv)

    def classify(name, occ):
        """What kind of giver a name is: party, pcf, cand, org, or None for a person."""
        n, o = name or "", occ or ""
        toks = name_tokens(n)
        person_shaped = 2 <= len(toks) <= 3 and not STRONG_ORG.search(n) and not FL_PCF_NAME.search(n) and not FL_PARTY.search(n)
        if FL_PARTY.search(n) or (FL_PARTY_OCC.search(o) and not person_shaped):
            return "party"
        if FL_PCF_NAME.search(n) or (FL_PCF_OCC.search(o) and not person_shaped):
            return "pcf"
        if CAND_WORD.search(n) and not STRONG_ORG.search(n):
            return "cand"                                                     # "Mast for Congress", not "Friends of Mount Sinai Medical Center"
        if people.is_person(n):
            return None
        if STRONG_ORG.search(n) or FL_ORG.search(n):
            return "org"
        return None

    for key, rows in rows_by_key.items():
        bio, office = key_bio[key], key[2]
        chamber = OFFICE[office]
        reg = f"fl:{key[0]}:{key[1]}:{office}"
        for f in rows:
            n_rows += 1
            date = iso(f[1])
            year = int(date[:4]) if date else 0
            if year < args.since:
                continue
            try:
                amount = float(f[2].replace(",", "") or 0)
            except ValueError:
                continue
            typ = f[3].strip().upper()
            if not amount or typ == "X":
                continue
            n_kept += 1
            by_type[typ] += 1
            name = " ".join(f[4].split())
            if typ == "LOA":
                add_source(bio, reg, chamber, year, "loans", amount)
                continue
            if typ == "REF" and amount < 0:
                pass                                                                  # a contribution returned to its giver: netted against that giver below
            elif typ not in MONETARY and typ != "INK":
                add_source(bio, reg, chamber, year, "other", amount)                  # interest, a refund the campaign received, and codes the form guide does not list
                continue
            if not name:
                add_source(bio, reg, chamber, year, "other", amount)
                continue
            tokens = re.findall(r"[A-Za-z][A-Za-z'\-]*", name)
            if own(tokens, bio):
                add_source(bio, reg, chamber, year, "self", amount)
                continue
            clean = people.strip_contact(name)
            kind = classify(clean, f[7])
            if kind is None:
                add_source(bio, reg, chamber, year, "people", amount)
                if STRONG_ORG.search(clean) or FL_ORG.search(clean):
                    set_aside[clean] += amount
                continue
            did = "n-" + (norm(clean)[:48] or "unnamed")
            kinds_seen[did][kind] += 1
            gifts.append([bio, reg, chamber, year, date, amount, did, clean, kind, 1 if typ == "INK" else 0])
            add_source(bio, reg, chamber, year, kind, amount)
    for g in gifts:
        g[8] = kinds_seen[g[6]].most_common(1)[0][0]
    print(f"    {n_rows:,} rows for those accounts; {n_kept:,} since {args.since} (types: " + ", ".join(f"{k} {v:,}" for k, v in by_type.most_common()) + f"; {time.time() - t0:.0f} s)")

    with con:
        for t in ("state_committees", "state_gifts", "state_sources", "state_outside"):
            con.execute(f"DELETE FROM {t}")
        con.executemany("INSERT INTO state_committees VALUES (?,?,?,?)",
                        [(f"fl:{k[0]}:{k[1]}:{k[2]}", key_name[k].most_common(1)[0][0], OFFICE[k[2]], bio) for k, bio in key_bio.items()])
        con.executemany("INSERT INTO state_gifts (bioguide_id, committee, office, year, date, amount, donor_id, donor_name, donor_kind, in_kind) VALUES (?,?,?,?,?,?,?,?,?,?)", gifts)
        con.executemany("INSERT INTO state_sources VALUES (?,?,?,?,?,?,?)", [(*k, round(v[0], 2), v[1]) for k, v in sources.items()])
    by_source = dict(con.execute("SELECT source, ROUND(SUM(amount)) FROM state_sources GROUP BY 1"))
    print(f"    Stored: {len(gifts):,} gifts from organizations (${sum(g[5] for g in gifts) / 1e6:,.1f}M); totals by source: "
          + ", ".join(f"{k} ${v / 1e6:,.1f}M" for k, v in sorted(by_source.items(), key=lambda kv: -kv[1])))
    print("    Outside spending: none loaded; the Division's expenditure records do not say which candidate a committee spent for or against")
    top = con.execute("SELECT donor_name, donor_kind, ROUND(SUM(amount)) FROM state_gifts GROUP BY donor_id ORDER BY 3 DESC LIMIT 6").fetchall()
    print("    biggest named givers: " + "; ".join(f"{n[:60]} ({k}) ${a / 1e6:,.1f}M" for n, k, a in top))
    if set_aside:
        print(f"    givers with a company's word in the name but read as people, for reading ({len(set_aside)}): " + "; ".join(f"{n} ${a:,.0f}" for n, a in set_aside.most_common(10)))
    mism = [f"{key_name[k].most_common(1)[0][0]} -> {members[b]['name']} ({members[b]['party']})" for k, b in key_bio.items() if PARTY_CODE.get(key_party[k], key_party[k]) != members[b]["party"]]
    if mism:
        print(f"    accounts whose party differs from the roster's ({len(mism)}): " + "; ".join(mism[:8]) + (" ..." if len(mism) > 8 else ""))
    many = [(members[b]["name"], [key_name[k].most_common(1)[0][0] for k in key_bio if key_bio[k] == b]) for b in matched if sum(1 for k in key_bio if key_bio[k] == b) > 1]
    if many:
        print(f"    members with more than one account string ({len(many)}): " + "; ".join(f"{n}: {' | '.join(s)}" for n, s in many[:6]) + (" ..." if len(many) > 6 else ""))
    if namesakes:
        print(f"    left out as a namesake of another party ({len(namesakes)}): " + "; ".join(namesakes))
    if ambiguous:
        print(f"    left out, more than one member fits ({len(ambiguous)}): " + "; ".join(list(ambiguous.values())[:8]))
    unmatched = [m["name"] for bio, m in members.items() if bio not in matched]
    if unmatched:
        print(f"    sitting members with no account matched ({len(unmatched)}): " + ", ".join(sorted(unmatched)[:30]) + (" ..." if len(unmatched) > 30 else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
