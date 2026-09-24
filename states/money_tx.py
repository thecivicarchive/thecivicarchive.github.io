#!/usr/bin/env python3
"""
states/money_tx.py
==================
Texas campaign money, from the Texas Ethics Commission's bulk download of every electronically filed campaign finance
report since July 2000 (TEC_CF_CSV.zip, about 1 GB, no account; the Commission's readme and code list travel in the
zip). The filer index (filers.csv) names every candidate and office holder with the office sought or held and its
district; the contribution files (contribs_##.csv, a hundred parts) carry every gift with the giver's kind.

The same rule as everywhere on the site. Organizations are named: political committees (Texas's general- and
specific-purpose committees), party committees, other candidates' committees, and the partnerships, law firms and
associations Texas allows to give (a corporation or union may not give to a candidate in Texas), each recognised by
the "ENTITY" the campaign reported. People are not named: every gift from an individual goes into a yearly total,
and the name on that row is never written to the database; a gift from the candidate is counted as own money.
Reports superseded by a later filing (infoOnlyFlag = Y) are skipped.

Outside spending is not loaded for Texas: the bulk file lists what a committee spent to benefit a candidate on the
same schedule as the contributions it gave, with no flag to tell them apart and none for support or opposition, so
any figure would either double-count contributions or leave most of it out. The page says so.

Filers are matched to sitting legislators by name and never guessed: the index's family name, a compatible given
name, and an office (State Representative or State Senator) whose chamber the member has served in, and the match
must be the only member who fits; the index's district settles a tie. Anything less is listed at the end of the
run and left out.

  state_committees   each matched filer account: the Commission's filer number, chamber, member
  state_gifts        every gift from an organization to a matched filer
  state_sources      yearly totals by source (people, committees, party, other candidates, other organizations, own money, other)
  state_outside      empty for Texas (see above)

    python -m states.money_tx --db state_tx.sqlite --since 2015
"""

import argparse
import collections
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

URL = "https://prd.tecprd.ethicsefile.com/public/cf/public/TEC_CF_CSV.zip"
OFFICE = {"STATEREP": "House", "STATESEN": "Senate"}
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


def givens_of(first):
    """'Homero R.' -> ['Homero', 'R']; 'Joan (Joanie)' -> ['Joan', 'Joanie']."""
    return [g for g in re.split(r"[\s().,]+", first or "") if len(norm(g)) > 1] + [g for g in re.split(r"[\s().,]+", first or "") if len(norm(g)) == 1]


def initials_fit(givens, roster_given):
    """The roster writes some members by initials ('A.J.'); the Commission writes the name out ('Andrew J.'): the
    initials must agree, in order."""
    ini = norm(roster_given)
    if not (2 <= len(ini) <= 3 and "." in roster_given):
        return False
    return "".join(norm(g)[:1] for g in givens)[:len(ini)] == ini


def families_of(last):
    last = SUFFIX.sub("", " ".join((last or "").split()))
    fams = {norm(last)} | {norm(x) for x in re.split(r"[\s-]+", last) if len(norm(x)) > 3}
    return {f for f in fams if f}


FILER_KIND = {"GPAC": "pcf", "MPAC": "pcf", "SPAC": "pcf", "JSPC": "pcf", "ASIFSPAC": "pcf", "DCE": "pcf", "COH": "cand", "JCOH": "cand", "SCC": "cand",
              "PTYCORP": "party", "CEC": "party", "LEG": "party"}


def kind_of(name, pac_fein, registered):
    """An ENTITY giver's kind: the Commission's own index first (a registered committee is what it is registered as,
    whatever it is called), then the Commission's PAC number, then the name the campaign wrote."""
    n = name or ""
    if re.search(r"\b(republican|democratic|libertarian|green) party\b|\bparty of texas\b", n, re.I):
        return "party"
    reg = registered.get(norm(n)[:60]) or registered.get(norm(re.sub(r"\s*(pac|political action committee)\s*$", "", n, flags=re.I))[:60])
    if reg:
        return reg
    if re.search(r"pac\b|\b(political action committee|committee|fund)\b", n, re.I) or (pac_fein or "").strip():
        if re.search(r"\b(friends of|campaign|for (state )?(rep|sen)|committee to elect)\b", n, re.I) and not re.search(r"pac\b", n, re.I):
            return "cand"
        return "pcf"
    if re.search(r"\b(republican|democrat|democrats|democratic|gop|party)\b", n, re.I):
        return "party"
    if re.search(r"\b(friends of|campaign|for (state )?(rep|sen|representative|senator)|committee to elect|elect\b)", n, re.I):
        return "cand"
    return "org"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", required=True)
    ap.add_argument("--cache-dir", default="states_cache")
    ap.add_argument("--since", type=int, default=2015, help="first year to keep (the 2016 cycle begins in January 2015)")
    args = ap.parse_args()
    folder = os.path.join(args.cache_dir, "tx_tec")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, "TEC_CF_CSV.zip")
    if net.download(URL, path, 3600):
        print(f"    fetched TEC_CF_CSV.zip ({os.path.getsize(path) / 1e6:,.0f} MB)")
    z = zipfile.ZipFile(path)

    con = sqlite3.connect(args.db)
    con.executescript(SCHEMA)
    if not con.execute("SELECT 1 FROM sqlite_master WHERE name = 'legislators'").fetchone():
        sys.exit("No members yet. Run the people stage first.")
    members = {}
    for bio, first, last, full, others, district, chamber in con.execute("SELECT bioguide_id, first_name, last_name, official_full, other_names, district, chamber FROM legislators WHERE is_current = 1"):
        givens = {first, (full or "").split(" ")[0]} | {o.split(",")[-1].strip().split(" ")[0] if "," in o else o.split(" ")[0] for o in (others or "").split(";") if o.strip()}
        members[bio] = {"family": families_of(last) | {norm((full or "").split(" ")[-1])}, "given": {g for g in givens if g and len(norm(g)) > 1}, "name": full,
                        "district": str(district or "").lstrip("0"), "chamber": chamber}
    served = {}
    for bio, typ in con.execute("SELECT DISTINCT bioguide_id, type FROM member_terms"):
        served.setdefault(bio, set()).add({"rep": "House", "sen": "Senate"}.get(typ, typ))

    # -- the filer index: every candidate account for a House or Senate seat, with the office and district the Commission recorded
    filers, registered = {}, {}
    with io.TextIOWrapper(z.open("filers.csv"), encoding="utf-8", errors="replace", newline="") as fh:
        for r in csv.DictReader(fh):
            kind = FILER_KIND.get((r.get("filerTypeCd") or "").strip())
            if kind:
                registered.setdefault(norm(r.get("filerName"))[:60], kind)
                registered.setdefault(norm(re.sub(r"\s*(pac|political action committee)\s*$", "", r.get("filerName") or "", flags=re.I))[:60], kind)     # "Texans for Lawsuit Reform" is its PAC written short
            if r.get("filerTypeCd") != "COH":
                continue
            offices = []
            for oc, dc in (("ctaSeekOfficeCd", "ctaSeekOfficeDistrict"), ("filerHoldOfficeCd", "filerHoldOfficeDistrict")):
                code = (r.get(oc) or "").strip()
                if code in OFFICE:
                    offices.append((OFFICE[code], (r.get(dc) or "").strip().lstrip("0")))
            if not offices:
                continue
            held = (r.get("filerHoldOfficeCd") or "").strip()
            filers[r["filerIdent"].strip()] = {"name": " ".join((r.get("filerName") or "").split()), "families": families_of(r.get("filerNameLast")),
                                               "givens": givens_of(r.get("filerNameFirst")), "offices": offices,
                                               "seat": (OFFICE[held], (r.get("filerHoldOfficeDistrict") or "").strip().lstrip("0")) if held in OFFICE and (r.get("filerFilerpersStatusCd") or "") == "CURRENT_OFFICEHOLDER" else None}
    whose, unsure, by_seat = {}, [], []
    for ident, f in filers.items():
        fits_all = []
        for chamber, district in f["offices"]:
            same_family = [bio for bio, m in members.items() if f["families"] & m["family"] and chamber in served.get(bio, ())]
            fits = [bio for bio in same_family if any(given_fits(c, g) for c in f["givens"] for g in members[bio]["given"]) or any(initials_fit(f["givens"], g) for g in members[bio]["given"])]
            if len(fits) > 1 and district:
                narrowed = [bio for bio in fits if members[bio]["district"] == district]
                if len(narrowed) == 1:
                    fits = narrowed
            fits_all.append((chamber, fits))
        hits = {bio for _c, fits in fits_all for bio in fits}
        if len(hits) == 1:
            bio = hits.pop()
            chamber = next(c for c, fits in fits_all if bio in fits)
            whose[ident] = (bio, chamber, f["name"])
        elif len(hits) > 1:
            unsure.append(f"{f['name']}: fits {', '.join(members[b]['name'] for b in hits)}")
        elif f["seat"]:
            # the Commission's own record says this account belongs to the current holder of a seat: the roster's member
            # for that seat is accepted when the family name or a given name lines up (Roberto D. Guerra for Bobby Guerra,
            # Christian V. Hayes for Christian Manuel)
            chamber, district = f["seat"]
            seat = [bio for bio, m in members.items() if m["chamber"] == chamber and m["district"] == district]
            if len(seat) == 1 and (f["families"] & members[seat[0]]["family"] or any(given_fits(c, g) for c in f["givens"] for g in members[seat[0]]["given"])):
                whose[ident] = (seat[0], chamber, f["name"])
                by_seat.append(f"{f['name']} ({chamber} {district}) -> {members[seat[0]]['name']}")
    matched = {b for b, _c, _n in whose.values()}
    print(f"    {len(filers):,} House and Senate candidate accounts in the Commission's index; {len(whose):,} matched to {len(matched):,} of {len(members):,} sitting members")

    # -- one pass over every contribution part: a fast look at the filer number before the row is parsed at all
    parts = sorted(n for n in z.namelist() if re.match(r"^contribs_\d+\.csv$", n))
    wanted = set(whose)
    gifts, sources, kinds_seen, n_rows, n_kept, superseded = [], {}, collections.defaultdict(collections.Counter), 0, 0, 0
    own_names = {bio: (m["family"], m["given"]) for bio, m in members.items()}
    for k, name in enumerate(parts, 1):
        with io.TextIOWrapper(z.open(name), encoding="utf-8", errors="replace", newline="") as fh:
            head = fh.readline().rstrip("\r\n").split(",")
            ix = {c: i for i, c in enumerate(head)}
            keep = []
            for line in fh:
                n_rows += 1
                bits = line.split(",", 7)
                if len(bits) < 8 or bits[6] not in wanted:
                    continue
                keep.append(line)
            for r in csv.reader(keep):
                if len(r) < len(head):
                    continue
                if r[ix["infoOnlyFlag"]] == "Y":
                    superseded += 1
                    continue
                d = r[ix["contributionDt"]]
                year = int(d[:4]) if d[:4].isdigit() else 0
                if year < args.since:
                    continue
                try:
                    amount = float(r[ix["contributionAmount"]] or 0)
                except ValueError:
                    continue
                if not amount:
                    continue
                ident = r[ix["filerIdent"]]
                bio, chamber, _n = whose[ident]
                n_kept += 1
                date = f"{d[:4]}-{d[4:6]}-{d[6:8]}" if len(d) == 8 else None
                if r[ix["contributorPersentTypeCd"]] == "ENTITY":
                    org = " ".join((r[ix["contributorNameOrganization"]] or "").split())
                    source = kind_of(org, r[ix["contributorPacFein"]], registered)
                    did = norm(org)[:48] or "unnamed"
                    kinds_seen[did][source] += 1
                    gifts.append([bio, ident, chamber, year, date, amount, did, org, source, 0])
                else:
                    fam, giv = families_of(r[ix["contributorNameLast"]]), givens_of(r[ix["contributorNameFirst"]])
                    source = "self" if (fam & own_names[bio][0] and any(given_fits(c, g) for c in giv for g in own_names[bio][1])) else "people"
                s = sources.setdefault((bio, ident, chamber, year, source), [0.0, 0])
                s[0] += amount; s[1] += 1
        if k % 10 == 0:
            print(f"    {k} of {len(parts)} parts read: {n_rows:,} rows, {n_kept:,} kept", flush=True)
    for g in gifts:
        g[8] = kinds_seen[g[6]].most_common(1)[0][0]
    print(f"    {n_rows:,} contribution rows read; {n_kept:,} to matched members since {args.since} ({superseded:,} superseded left out)")
    with con:
        for t in ("state_committees", "state_gifts", "state_sources", "state_outside"):
            con.execute(f"DELETE FROM {t}")
        con.executemany("INSERT INTO state_committees VALUES (?,?,?,?)", [(ident, name, chamber, bio) for ident, (bio, chamber, name) in whose.items()])
        con.executemany("INSERT INTO state_gifts (bioguide_id, committee, office, year, date, amount, donor_id, donor_name, donor_kind, in_kind) VALUES (?,?,?,?,?,?,?,?,?,?)", gifts)
        con.executemany("INSERT INTO state_sources VALUES (?,?,?,?,?,?,?)", [(*k, round(v[0], 2), v[1]) for k, v in sources.items()])
    by_source = dict(con.execute("SELECT source, ROUND(SUM(amount)) FROM state_sources GROUP BY 1"))
    print(f"    Stored: {len(gifts):,} gifts from organizations (${sum(g[5] for g in gifts) / 1e6:,.1f}M); itemized totals by source: "
          + ", ".join(f"{k} ${v / 1e6:,.1f}M" for k, v in sorted(by_source.items(), key=lambda kv: -kv[1])))
    print("    Outside spending: none loaded; the Commission's bulk file lists a committee's spending for a candidate beside its contributions with no flag to tell them apart")
    if by_seat:
        print(f"    matched by the seat the Commission records the account as holding ({len(by_seat)}): " + "; ".join(by_seat[:10]) + (" ..." if len(by_seat) > 10 else ""))
    if unsure:
        print(f"    left out, more than one member fits ({len(unsure)}): " + "; ".join(unsure[:8]) + (" ..." if len(unsure) > 8 else ""))
    unmatched = [m["name"] for bio, m in members.items() if bio not in matched]
    if unmatched:
        print(f"    sitting members with no account matched ({len(unmatched)}): " + ", ".join(sorted(unmatched)[:24]) + (" ..." if len(unmatched) > 24 else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
