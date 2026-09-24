#!/usr/bin/env python3
"""
states/money_co.py
==================
Colorado campaign money, from the Secretary of State's TRACER bulk downloads (public records, no account): one
contributions file a year, <year>_ContributionData.csv.zip, from 2015 on (about 2 to 16 MB each). Colorado's files
carry the giver's type, the recipient committee's type and name, the candidate's name and the jurisdiction, but not
the office sought, and the expenditure files do not say which candidate an independent spender supported or opposed.

The same rule as everywhere on the site. Organizations are named: political committees, small donor committees,
party committees, other candidates' committees, federal PACs, and (Colorado lets them give) businesses, corporations
and unions, each under the type the campaign reported. People are not named: every gift from an individual, from a
member of an LLC, from the candidate, and every small gift reported as one non-itemized sum, goes into a yearly
total, and the name on those rows is never written to the database. Returned contributions and bounced payments are
left out; "other receipts" are totalled as other.

Campaigns are matched to sitting legislators by name and never guessed. Because the file names no office, a match
is accepted only when the campaign is a statewide-jurisdiction candidate committee whose name carries no other
office (governor, attorney general, treasurer, secretary of state, district attorney, regent, RTD and the like) and
whose candidate's full name, family name and a compatible given name, fits exactly one sitting legislator. Anything
less is listed at the end of the run and left out. A superseded record (Amended = Y) is skipped in favour of its
amendment.

  state_committees   each matched campaign committee: TRACER's committee number, chamber (from the roster), member
  state_gifts        every gift from an organization to a matched committee
  state_sources      yearly totals by source
  state_outside      empty for Colorado: the bulk files do not attribute independent spending to candidates

    python -m states.money_co --db state_co.sqlite --since 2015
"""

import argparse
import collections
import csv
import io
import os
import re
import sqlite3
import sys
import time
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from states import net                                     # noqa: E402
from states.money_mn import norm, given_fits               # noqa: E402

BASE = "https://tracer.sos.colorado.gov/PublicSite/Docs/BulkDataDownloads/"
KINDS = {"Political Committee": "pcf", "Small Donor Committee": "pcf", "Federal PAC": "pcf", "Independent Expenditure Committee": "pcf",
         "527 Political Organization": "pcf", "Issue Committee": "pcf", "Political Party Committee": "party", "Candidate Committee": "cand",
         "Business": "biz", "Corporation": "biz", "Labor Union": "union", "Individual": "people", "Candidate": "self"}
OTHER_OFFICE = re.compile(r"\b(governor|gov|attorney general|ag|treasurer|secretary of state|sos|district attorney|da|regent|cu|rtd|board of education|"
                          r"state board|judge|congress|mayor|council|commissioner|sheriff|assessor|clerk|coroner|president|school)\b", re.I)
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


def rows_of(path):
    """The rows of a TRACER zip: one CSV, written in UTF-16 or UTF-8 with a byte-order mark."""
    z = zipfile.ZipFile(path)
    for name in z.namelist():
        raw = z.read(name)
        text = raw.decode("utf-16", "replace") if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else raw.decode("utf-8-sig", "replace")
        yield from csv.DictReader(io.StringIO(text))


def person_parts(text):
    """'RICHARD MICHAEL ALONSO HOLTORF' -> ({'holtorf'}, ['RICHARD', 'MICHAEL', 'ALONSO'])."""
    text = SUFFIX.sub("", " ".join((text or "").replace(",", " ").replace(".", " ").split()))
    parts = [p for p in text.split(" ") if norm(p)]
    if not parts:
        return None
    family = parts[-1]
    families = {norm(family)} | {norm(x) for x in family.split("-") if len(norm(x)) > 3}
    if len(parts) >= 3 and len(norm(parts[-2])) > 3 and norm(parts[-2]) not in ("van", "von", "de", "la", "del", "mac", "mc"):
        families.add(norm(parts[-2] + parts[-1]))
    return families, [p for p in parts[:-1] if len(norm(p)) > 1]


LEAD = re.compile(r"^(the\s+)?(committee\s+to\s+(re-?)?elect|(re-?)?elect|friends\s+(of|for)|citizens\s+(for|to\s+elect)|coloradans\s+for|people\s+for|neighbors\s+for|vote|team)\s+", re.I)
HINT = re.compile(r"\b(house|hd|senate|sd|state\s+house|state\s+senate|colorado\s+house|colorado\s+senate)\s*(district)?\s*(\d{1,2})\b", re.I)


def title_reading(title):
    """What a committee's own name says: the given names written before FOR ("JULIE FOR COLORADO", "CHAD FOR COLORADO",
    "ELECT THOMAS TONY EXUM") and, when the name carries one, the chamber and district ("TAGGART FOR HOUSE DISTRICT 55")."""
    t = " ".join((title or "").split())
    hint = None
    m = HINT.search(t)
    if m:
        hint = ("Senate" if m.group(1).lower().replace("state ", "").replace("colorado ", "") in ("senate", "sd") else "House", str(int(m.group(3))))
    t = LEAD.sub("", t)
    t = re.split(r"\s+(for|4)\s+", t, maxsplit=1, flags=re.I)[0]
    t = re.sub(r"\s+(campaign|committee|election committee)\s*$", "", t, flags=re.I).strip(" -,")
    words = [w for w in t.split() if norm(w) and not re.search(r"\d", w)]
    return words, hint


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", required=True)
    ap.add_argument("--cache-dir", default="states_cache")
    ap.add_argument("--since", type=int, default=2015, help="first year to keep (the 2016 cycle begins in January 2015)")
    args = ap.parse_args()
    folder = os.path.join(args.cache_dir, "co_tracer")
    os.makedirs(folder, exist_ok=True)
    this_year = int(time.strftime("%Y"))
    files = []
    for year in range(args.since, this_year + 1):
        name = f"{year}_ContributionData.csv.zip"
        path = os.path.join(folder, name)
        if net.download(BASE + name, path, 900):
            print(f"    fetched {name} ({os.path.getsize(path) / 1e6:,.1f} MB)")
        files.append(path)

    con = sqlite3.connect(args.db)
    con.executescript(SCHEMA)
    if not con.execute("SELECT 1 FROM sqlite_master WHERE name = 'legislators'").fetchone():
        sys.exit("No members yet. Run the people stage first.")
    members = {}
    for bio, first, last, full, others, chamber, district in con.execute("SELECT bioguide_id, first_name, last_name, official_full, other_names, chamber, district FROM legislators WHERE is_current = 1"):
        givens = {first, (full or "").split(" ")[0]} | {o.split(",")[-1].strip().split(" ")[0] if "," in o else o.split(" ")[0] for o in (others or "").split(";") if o.strip()}
        members[bio] = {"family": {norm(last), norm((full or "").split(" ")[-1])}, "given": {g for g in givens if g and len(norm(g)) > 1}, "name": full, "chamber": chamber,
                        "district": str(district or "").lstrip("0")}

    # -- one pass over every year: keep what went to a statewide candidate committee, superseded records left out
    kept, committees, n, superseded, returned = [], {}, 0, 0, 0
    for path in files:
        for r in rows_of(path):
            n += 1
            if r.get("CommitteeType") != "Candidate Committee" or r.get("Jurisdiction") != "STATEWIDE":
                continue
            if r.get("Amended") == "Y":
                superseded += 1
                continue
            ctype = re.sub(r"\s*\(Total Amount:.*\)", "", r.get("ContributionType") or "").strip()
            if ctype.startswith(("Returned", "NSF")):
                returned += 1
                continue
            try:
                amount = float(r.get("ContributionAmount") or 0)
            except ValueError:
                continue
            date = (r.get("ContributionDate") or "")[:10]
            year = int(date[:4]) if date[:4].isdigit() else 0
            if year < args.since or not amount:
                continue
            code = r["CO_ID"].strip()
            committees.setdefault(code, (" ".join((r.get("CandidateName") or "").split()), " ".join((r.get("CommitteeName") or "").split())))
            giver_type = (r.get("ContributorType") or "").strip()
            giver = " ".join(" ".join(filter(None, (r.get("FirstName"), r.get("MI"), r.get("LastName"), r.get("Suffix")))).split())
            kept.append((code, year, date, amount, ctype, giver_type, giver))
    print(f"    {n:,} contribution rows read; {len(kept):,} to statewide candidate committees since {args.since} ({superseded:,} superseded records and {returned:,} returned or bounced gifts left out); {len(committees):,} committees")

    # -- which committee is whose: the candidate's full name must fit exactly one sitting legislator, and the committee's name no other office
    whose, unsure, by_title, skipped_office = {}, [], [], 0
    for code, (candidate, title) in committees.items():
        parts = person_parts(candidate)
        if not parts:
            continue
        families, givens = parts
        if OTHER_OFFICE.search(re.sub(r"\bFOR\s+COLORADO\b", "", title, flags=re.I)):
            skipped_office += 1
            continue
        same_family = [bio for bio, m in members.items() if families & m["family"]]
        fits = [bio for bio in same_family if givens and any(given_fits(c, g) for c in givens for g in members[bio]["given"])]
        how = "full name"
        if not fits and same_family:
            # the file's name does not fit (Julia for Julie, Merrick for Rick): the committee's own title may carry the
            # name the member goes by, or the seat itself; either must still point at exactly one sitting member
            words, hint = title_reading(title)
            title_givens = [w for w in words if norm(w) not in families]
            fits = [bio for bio in same_family if any(given_fits(c, g) for c in title_givens for g in members[bio]["given"])]
            how = "the committee's own name"
            if not fits and hint:
                fits = [bio for bio in same_family if (members[bio]["chamber"], members[bio]["district"]) == hint]
                how = "family name and the seat named by the committee"
        if len(fits) == 1:
            whose[code] = (fits[0], members[fits[0]]["chamber"], title)
            if how != "full name":
                by_title.append(f"{title} ({candidate}) -> {members[fits[0]]['name']}, by {how}")
        elif len(fits) > 1:
            unsure.append(f"{title} ({candidate}): fits {', '.join(members[b]['name'] for b in fits)}")
    matched = {b for b, _c, _t in whose.values()}
    print(f"    {len(committees):,} statewide candidate committees; {len(whose):,} matched to {len(matched):,} of {len(members):,} sitting members "
          f"({skipped_office:,} named another office and were not considered)")

    # -- gifts and totals
    gifts, sources, kinds_seen = [], {}, collections.defaultdict(collections.Counter)
    for code, year, date, amount, ctype, giver_type, giver in kept:
        hit = whose.get(code)
        if not hit:
            continue
        bio, chamber, _title = hit
        if ctype.startswith("Other Receipts") or ctype.startswith("Non-Aggregated"):
            source = "other"
        elif "Non-Itemized" in ctype or not giver_type:
            source = "people"                                          # small gifts reported as one sum: individuals, not named in the file either
        elif giver_type.startswith("Individual"):
            source = "people"                                          # includes members of an LLC giving through it
        else:
            source = KINDS.get(giver_type, "org")                      # Other, Unknown: an organization the file does not classify
        s = sources.setdefault((bio, code, chamber, year, source), [0.0, 0])
        s[0] += amount; s[1] += 1
        if source in ("pcf", "party", "cand", "biz", "union", "org"):
            did = norm(giver)[:48] or "unnamed"
            kinds_seen[did][source] += 1
            gifts.append([bio, code, chamber, year, date or None, amount, did, giver, source, 1 if ctype.startswith("Non-Monetary") else 0])
    for g in gifts:
        g[8] = kinds_seen[g[6]].most_common(1)[0][0]
    with con:
        for t in ("state_committees", "state_gifts", "state_sources", "state_outside"):
            con.execute(f"DELETE FROM {t}")
        con.executemany("INSERT INTO state_committees VALUES (?,?,?,?)", [(code, title, chamber, bio) for code, (bio, chamber, title) in whose.items()])
        con.executemany("INSERT INTO state_gifts (bioguide_id, committee, office, year, date, amount, donor_id, donor_name, donor_kind, in_kind) VALUES (?,?,?,?,?,?,?,?,?,?)", gifts)
        con.executemany("INSERT INTO state_sources VALUES (?,?,?,?,?,?,?)", [(*k, round(v[0], 2), v[1]) for k, v in sources.items()])
    by_source = dict(con.execute("SELECT source, ROUND(SUM(amount)) FROM state_sources GROUP BY 1"))
    print(f"    Stored: {len(gifts):,} gifts from organizations (${sum(g[5] for g in gifts) / 1e6:,.1f}M); itemized totals by source: "
          + ", ".join(f"{k} ${v / 1e6:,.1f}M" for k, v in sorted(by_source.items(), key=lambda kv: -kv[1])))
    print("    Outside spending: none loaded; Colorado's bulk expenditure files do not say which candidate an independent spender supported or opposed")
    if by_title:
        print(f"    matched through the committee's own name ({len(by_title)}): " + "; ".join(by_title[:8]) + (" ..." if len(by_title) > 8 else ""))
    if unsure:
        print(f"    left out, more than one member fits ({len(unsure)}): " + "; ".join(unsure[:8]) + (" ..." if len(unsure) > 8 else ""))
    unmatched = [m["name"] for bio, m in members.items() if bio not in matched]
    if unmatched:
        print(f"    sitting members with no committee matched ({len(unmatched)}): " + ", ".join(sorted(unmatched)[:24]) + (" ..." if len(unmatched) > 24 else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
