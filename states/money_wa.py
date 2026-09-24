#!/usr/bin/env python3
"""
states/money_wa.py
==================
Washington campaign money, from the Public Disclosure Commission's open data on data.wa.gov (public domain, no
account): every contribution to a candidate for the last ten years (dataset 2jwd-akfb, filtered here to House and
Senate campaigns since 2015, about 480,000 rows), the Commission's campaign register (3h9x-7bvm: every legislative
campaign with the candidate's name, district, party and a person number that ties one candidate's campaigns
together) and independent expenditures and electioneering communications for or against candidates (67cp-h962).

The same rule as everywhere on the site. Organizations are named. In Washington that is more than committees:
businesses, unions and associations may give directly to a campaign, and the Commission's file carries the code the
campaign reported each giver under (Political Action Committee, Party, Caucus, Business, Union, Other organization).
People are not named: every gift coded Individual, Self or Low-cost fundraiser goes into a yearly total, and the name
on that row is never written to the database. "Miscellaneous receipts" and anonymous lines are totalled as other.
Independent expenditures go in their own table: the campaign never received that money, and the description of each
is left out of the pages.

Campaigns are matched to sitting legislators by name and never guessed. The register writes a name three ways
("CAYLOR KENNETH E", "Clifford Mark Greene", "GREGORY CAROL J (CAROL GREGORY)"); each is read, and a match needs the
family name, a compatible given name, and a chamber the member has served in, and must be the only member who fits;
the register's district settles a tie; a sitting representative's Senate campaign is accepted when exactly one
sitting member carries the name. Anything less is listed at the end of the run and left out.

  state_committees   each matched campaign (one per election year): the Commission's filer number, chamber, member
  state_gifts        every gift from an organization to a matched campaign
  state_sources      yearly totals by source (people, committees and funds, party and caucus, businesses, unions,
                     other organizations, the candidate, other)
  state_outside      every independent expenditure or electioneering communication for or against a matched campaign

    python -m states.money_wa --db state_wa.sqlite --since 2015 [--refresh]
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
from urllib.parse import quote

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from states import net                                     # noqa: E402
from states.money_mn import norm, given_fits               # noqa: E402

SODA = "https://data.wa.gov/resource/{ds}.csv?"
OFFICES = "office in('STATE REPRESENTATIVE','STATE SENATOR')"
CHAMBER = {"STATE REPRESENTATIVE": "House", "STATE SENATOR": "Senate"}
CODES = {"Political Action Committee": "pcf", "Party": "party", "Caucus": "party", "Business": "biz", "Union": "union",
         "Individual": "people", "Self": "self", "Low-cost Fundraiser": "people"}
PAGE = 100000
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


def soql(ds, params, timeout=600):
    url = SODA.format(ds=ds) + "&".join(f"{k}={quote(v, safe='(),*:=<>_')}" for k, v in params.items())
    return net.get(url, timeout)


def fetch_pages(path, ds, select, where, order=":id"):
    """A SoQL query in pages of PAGE rows, saved as one CSV. Keyless requests are polite: one page at a time, a pause between."""
    rows, offset, head = [], 0, None
    while True:
        data = soql(ds, {"$select": select, "$where": where, "$order": order, "$limit": str(PAGE), "$offset": str(offset)}).decode("utf-8", "replace")
        lines = data.splitlines()
        if head is None:
            head = lines[0]
        body = lines[1:]
        rows += body
        print(f"    {os.path.basename(path)}: {len(rows):,} rows", flush=True)
        if len(body) < PAGE:
            break
        offset += PAGE
        time.sleep(1.5)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(head + "\n" + "\n".join(rows) + "\n")


def when(text):
    """The Commission's CSV writes dates as 08/25/2026 (and its JSON as 2026-08-25T00:00:00); both come back as 2026-08-25."""
    t = (text or "").strip()
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})", t)
    if m:
        return f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
    return t[:10] if re.match(r"^\d{4}-\d{2}-\d{2}", t) else ""


def person_parts(text):
    """({family spellings}, [given names]) from a name in natural order: 'Carol J Gregory' -> ({'gregory'}, ['Carol', 'J'])."""
    text = SUFFIX.sub("", " ".join((text or "").replace(",", " ").replace(".", " ").split()))
    parts = [p for p in text.split(" ") if norm(p)]
    if not parts:
        return None
    family = parts[-1]
    families = {norm(family)} | {norm(x) for x in family.split("-") if len(norm(x)) > 3}
    if len(parts) >= 3 and len(norm(parts[-2])) > 3 and norm(parts[-2]) not in ("van", "von", "de", "la", "del", "mac", "mc"):
        families.add(norm(parts[-2] + parts[-1]))
    return families, [p for p in parts[:-1] if len(norm(p)) > 1]


def readings(filer_name):
    """Every way the Commission's name could be read: the bracketed plain name if there is one, then natural order,
    and for an all-capitals name the Commission's older LAST FIRST MIDDLE order too."""
    out = []
    m = re.search(r"\(([^)]+)\)\s*$", filer_name or "")
    if m:
        out.append(person_parts(m.group(1)))
        base = filer_name[:m.start()].strip()
    else:
        base = (filer_name or "").strip()
    if base:
        if base.isupper():
            parts = [p for p in base.replace(",", " ").split() if norm(p)]
            if len(parts) >= 2:
                fam, giv = parts[0], parts[1:]
                out.append(({norm(fam)} | {norm(x) for x in fam.split("-") if len(norm(x)) > 3}, [g for g in giv if len(norm(g)) > 1]))
        out.append(person_parts(base))
    return [p for p in out if p]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", required=True)
    ap.add_argument("--cache-dir", default="states_cache")
    ap.add_argument("--since", type=int, default=2015, help="first year to keep (the 2016 cycle begins in January 2015)")
    ap.add_argument("--refresh", action="store_true", help="fetch the Commission's data again (it is posted daily)")
    args = ap.parse_args()
    folder = os.path.join(args.cache_dir, "wa_pdc")
    os.makedirs(folder, exist_ok=True)
    since = f"{args.since}-01-01T00:00:00"
    files = {
        "legislative_campaigns.csv": ("3h9x-7bvm", "filer_id,filer_name,office,legislative_district,party,election_year,person_id,candidacy_id,committee_id,candidate_committee_status",
                                      f"{OFFICES} AND election_year>={args.since}", "election_year,filer_id"),
        "contributions_legislative.csv": ("2jwd-akfb", "id,filer_id,filer_name,office,legislative_district,party,election_year,amount,cash_or_in_kind,receipt_date,code,contributor_category,contributor_name",
                                          f"{OFFICES} AND receipt_date>='{since}'", ":id"),
        "independent_legislative.csv": ("67cp-h962", "id,report_number,report_type,sponsor_name,election_year,portion_of_amount,for_or_against,candidate_filer_id,candidate_name,candidate_office,date_expense_obligated,expenditure_description",
                                        f"candidate_office in('STATE REPRESENTATIVE','STATE SENATOR') AND election_year>={args.since}", ":id"),
    }
    for name, (ds, select, where, order) in files.items():
        path = os.path.join(folder, name)
        if args.refresh or not os.path.exists(path):
            fetch_pages(path, ds, select, where, order)

    con = sqlite3.connect(args.db)
    con.executescript(SCHEMA)
    if not con.execute("SELECT 1 FROM sqlite_master WHERE name = 'legislators'").fetchone():
        sys.exit("No members yet. Run the people stage first.")
    members = {}
    for bio, first, last, full, others, district in con.execute("SELECT bioguide_id, first_name, last_name, official_full, other_names, district FROM legislators WHERE is_current = 1"):
        givens = {first, (full or "").split(" ")[0]} | {o.split(",")[-1].strip().split(" ")[0] if "," in o else o.split(" ")[0] for o in (others or "").split(";") if o.strip()}
        members[bio] = {"family": {norm(last), norm((full or "").split(" ")[-1])}, "given": {g for g in givens if g and len(norm(g)) > 1}, "name": full, "district": str(district or "").lstrip("0")}
    served = {}
    for bio, typ in con.execute("SELECT DISTINCT bioguide_id, type FROM member_terms"):
        served.setdefault(bio, set()).add({"rep": "House", "sen": "Senate"}.get(typ, typ))

    # -- the register: every legislative campaign, grouped by the person behind it
    campaigns, persons = {}, collections.defaultdict(set)
    with open(os.path.join(folder, "legislative_campaigns.csv"), encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            fid = r["filer_id"].strip()
            campaigns[fid] = {"name": r["filer_name"].strip(), "chamber": CHAMBER.get(r["office"].strip(), ""), "district": r["legislative_district"].strip().lstrip("0"),
                              "year": r["election_year"], "person": r["person_id"].strip() or fid}
            persons[campaigns[fid]["person"]].add(fid)
    with open(os.path.join(folder, "contributions_legislative.csv"), encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            fid = r["filer_id"].strip()
            if fid and fid not in campaigns:                                   # a campaign the register does not carry: read the row's own name
                campaigns[fid] = {"name": r["filer_name"].strip(), "chamber": CHAMBER.get(r["office"].strip(), ""), "district": r["legislative_district"].strip().lstrip("0"),
                                  "year": r["election_year"], "person": fid}
                persons[fid].add(fid)

    def who(parts_list, chamber, district):
        same_family = [bio for bio, m in members.items() if any(p[0] & m["family"] for p in parts_list) and chamber in served.get(bio, ())]
        fits = [bio for bio in same_family if any(given_fits(c, g) for p in parts_list for c in p[1] for g in members[bio]["given"])]
        if len(fits) > 1 and district:
            narrowed = [bio for bio in fits if members[bio]["district"] == district]
            if len(narrowed) == 1:
                fits = narrowed
        return fits, same_family

    whose, unsure, other_office, unmatched_titles = {}, [], [], []
    for person, fids in persons.items():
        parts_list = [p for fid in fids for p in readings(campaigns[fid]["name"])]
        if not parts_list:
            continue
        hit = None
        for fid in sorted(fids, key=lambda f: campaigns[f]["year"], reverse=True):
            c = campaigns[fid]
            fits, same_family = who(parts_list, c["chamber"], c["district"])
            if len(fits) == 1:
                hit = fits[0]
                break
            if len(fits) > 1:
                unsure.append(f"{c['name']} ({c['chamber']} {c['district']}): fits {', '.join(members[b]['name'] for b in fits)}")
                break
        if hit is None and not any(u.startswith(campaigns[f]["name"]) for f in fids for u in unsure):
            fits = [bio for bio, m in members.items() if any(p[0] & m["family"] and any(given_fits(c, g) for c in p[1] for g in m["given"]) for p in parts_list)]
            if len(fits) == 1:
                hit = fits[0]
                other_office.append(f"{campaigns[sorted(fids)[0]]['name']} -> {members[hit]['name']}")
        if hit is None:
            continue
        for fid in fids:                                                      # the person is settled, so every legislative campaign of theirs is theirs
            c = campaigns[fid]
            whose[fid] = (hit, c["chamber"], f"{c['name']} {c['year']}")
    matched = {b for b, _c, _t in whose.values()}
    print(f"    {len(campaigns):,} House and Senate campaigns on file for {len(persons):,} people; {len(whose):,} matched to {len(matched):,} of {len(members):,} sitting members")

    # -- gifts and totals
    gifts, sources, kinds_seen = [], {}, collections.defaultdict(collections.Counter)
    with open(os.path.join(folder, "contributions_legislative.csv"), encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        hit = whose.get(r["filer_id"].strip())
        if not hit:
            continue
        try:
            amount = float(r["amount"] or 0)
        except ValueError:
            continue
        date = when(r["receipt_date"])
        year = int(date[:4]) if date[:4].isdigit() else 0
        if year > int(time.strftime("%Y")) + 1:                                # a receipt dated in the future is a filing slip: file it under the campaign's election year
            year = int(r["election_year"] or year)
        if year < args.since or not amount:
            continue
        code, cat, name = (r["code"] or "").strip(), (r["contributor_category"] or "").strip(), " ".join((r["contributor_name"] or "").split())
        if re.search(r"miscellaneous receipts|anonymous|unitemized|un-itemized", name, re.I):
            source = "other"
        elif code in CODES:
            source = CODES[code]
        elif cat == "Organization":
            source = "org"
        else:
            source = "people" if cat == "Individual" else "other"
        bio, chamber, _title = hit
        s = sources.setdefault((bio, r["filer_id"].strip(), chamber, year, source), [0.0, 0])
        s[0] += amount; s[1] += 1
        if source in ("pcf", "party", "biz", "union", "org", "cand"):        # an organization: named, as the campaign reported it
            did = norm(name)[:48] or "unnamed"
            kinds_seen[did][source] += 1
            gifts.append([bio, r["filer_id"].strip(), chamber, year, date or None, amount, did, name, source, 1 if (r["cash_or_in_kind"] or "").lower().startswith("in") else 0])
    for g in gifts:                                                           # one kind per organization: the one the campaigns used most
        g[8] = kinds_seen[g[6]].most_common(1)[0][0]
    outside, seen = [], set()
    with open(os.path.join(folder, "independent_legislative.csv"), encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            fid = (r["candidate_filer_id"] or "").strip()
            if fid not in whose or r["id"] in seen:
                continue
            seen.add(r["id"])
            try:
                amount = float(r["portion_of_amount"] or 0)
            except ValueError:
                continue
            date = when(r["date_expense_obligated"])
            year = int(date[:4]) if date[:4].isdigit() else int(r["election_year"] or 0)
            if year < args.since or not amount:
                continue
            side = "for" if (r["for_or_against"] or "").strip().lower() == "for" else "against"
            spender = " ".join((r["sponsor_name"] or "").split())
            outside.append((whose[fid][0], fid, year, date or None, amount, side, norm(spender)[:48] or "unknown", spender, "pcf", (r["expenditure_description"] or "")[:120]))
    with con:
        for t in ("state_committees", "state_gifts", "state_sources", "state_outside"):
            con.execute(f"DELETE FROM {t}")
        con.executemany("INSERT INTO state_committees VALUES (?,?,?,?)", [(fid, title, chamber, bio) for fid, (bio, chamber, title) in whose.items()])
        con.executemany("INSERT INTO state_gifts (bioguide_id, committee, office, year, date, amount, donor_id, donor_name, donor_kind, in_kind) VALUES (?,?,?,?,?,?,?,?,?,?)", gifts)
        con.executemany("INSERT INTO state_sources VALUES (?,?,?,?,?,?,?)", [(*k, round(v[0], 2), v[1]) for k, v in sources.items()])
        con.executemany("INSERT INTO state_outside (bioguide_id, committee, year, date, amount, side, spender_id, spender_name, spender_kind, purpose) VALUES (?,?,?,?,?,?,?,?,?,?)", outside)
    by_source = dict(con.execute("SELECT source, ROUND(SUM(amount)) FROM state_sources GROUP BY 1"))
    print(f"    Stored: {len(gifts):,} gifts from organizations (${sum(g[5] for g in gifts) / 1e6:,.1f}M); itemized totals by source: "
          + ", ".join(f"{k} ${v / 1e6:,.1f}M" for k, v in sorted(by_source.items(), key=lambda kv: -kv[1])))
    print(f"    Outside spending: {len(outside):,} payments, ${sum(o[4] for o in outside if o[5] == 'for') / 1e6:,.1f}M for and "
          f"${sum(o[4] for o in outside if o[5] == 'against') / 1e6:,.1f}M against sitting members")
    if other_office:
        print(f"    a sitting member's campaign for another office ({len(other_office)}): " + "; ".join(other_office[:8]) + (" ..." if len(other_office) > 8 else ""))
    if unsure:
        print(f"    left out, more than one member fits ({len(unsure)}): " + "; ".join(unsure[:8]) + (" ..." if len(unsure) > 8 else ""))
    unmatched = [m["name"] for bio, m in members.items() if bio not in matched]
    if unmatched:
        print(f"    sitting members with no campaign matched ({len(unmatched)}): " + ", ".join(sorted(unmatched)[:20]) + (" ..." if len(unmatched) > 20 else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
