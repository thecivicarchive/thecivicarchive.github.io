#!/usr/bin/env python3
"""
states/money_views.py
=====================
Shapes a state's campaign-money tables for the pages, the way money_views.py does for the federal side. It reads
what the state's money loader stored (state_committees, state_gifts, state_sources, state_outside) and downloads
nothing.

The same rule as everywhere on the site. Organizations are named: political committees and funds, party units,
other candidates' committees. People are not: gifts from individuals, from lobbyists (who are people) and from the
candidate arrive here already added into totals, and no name was ever stored. Outside spending is kept apart,
because the campaign never received it; its "purpose" text is left out, since free text can name a person.

Two things the data needs:

  * Money is grouped into two-year election segments, the way the Campaign Finance Board itself files it
    (2023-2024 is "2024"), so a state page reads like a federal one.
  * A legislator who moves from the House to the Senate usually passes the old committee's balance to the new
    one. That is the member's own money moving, not a donor, so it is reported as "moved in" and kept out of the
    donor list: exactly the federal rule for a member's own committees.

    python -m states.money_views --db state_mn.sqlite        # prints what it would hand the page builder
"""

import argparse
import datetime as dt
import os
import re
import sqlite3
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from states.money_mn import given_fits, norm          # noqa: E402

EPOCH = dt.date(2015, 1, 1)                           # the pages count days from here, as the federal pages do
KINDS = {"pcf": "Political committee or fund", "party": "Party unit", "cand": "Another candidate's committee",
         "biz": "Business", "union": "Union", "org": "Other organization",          # the last three where a state lets them give directly (Washington)
         "unnamed": "Not named here"}                                              # outside spenders a file cannot tell from people (California's Form 461 filers)
SOURCE_KEYS = {"people": "people", "lobbyists": "lobbyists", "pcf": "orgs", "party": "party", "cand": "cand", "self": "self",
               "biz": "biz", "union": "union", "org": "org", "loans": "loans", "other": "other"}
MAX_PAYMENTS = 200                                    # per donor, newest first; the rest are counted, not listed


def day(date):
    try:
        return (dt.date.fromisoformat((date or "")[:10]) - EPOCH).days
    except ValueError:
        return None


def segment(year):
    """The two-year election segment a calendar year belongs to, named by its even year."""
    return year if year % 2 == 0 else year + 1


def own_committees(con, legislators):
    """(member, donor registration number) pairs where the donor is that member's own other committee.

    Sure: the donor's registration number is one of the committees already matched to the same member. Also
    accepted: a candidate committee whose name carries the member's family name and a fitting given name, and
    which is not matched to anybody else. Both kinds are listed by the build so they can be read."""
    whose = dict(con.execute("SELECT reg_num, bioguide_id FROM state_committees"))
    names = {bio: (norm(L["last"]), L["first"]) for bio, L in legislators.items()}
    own, by_name = set(), []
    for bio, donor_id, donor_name in con.execute("SELECT DISTINCT bioguide_id, donor_id, donor_name FROM state_gifts WHERE donor_kind = 'cand'"):
        if whose.get(donor_id) == bio:
            own.add((bio, donor_id))
            continue
        if donor_id in whose or bio not in names:
            continue                                           # somebody else's committee, by registration number
        family, given = names[bio]
        tokens = [t for t in re.split(r"[^A-Za-z]+", donor_name or "") if t]
        if family and family in {norm(t) for t in tokens} and any(given_fits(given, t) for t in tokens if norm(t) != family):
            own.add((bio, donor_id))
            by_name.append(f"{donor_name} -> {legislators[bio]['n']}")
    return own, sorted(set(by_name))


def build_state_money(con, legislators):
    """{"profiles": member -> summary for their card, "members": member -> everything for their page,
        "kinds": labels, "summary": state-wide numbers, "own_by_name": what was treated as a member's own committee}"""
    has = lambda t: con.execute("SELECT 1 FROM sqlite_master WHERE name = ?", (t,)).fetchone() is not None
    if not (has("state_gifts") and has("state_sources")):
        return {"profiles": {}, "members": {}, "kinds": KINDS, "summary": {}, "own_by_name": []}
    own, own_by_name = own_committees(con, legislators)

    donors, moved, names = {}, {}, {}
    for bio, year, date, amount, did, dname, kind, in_kind in con.execute(
            "SELECT bioguide_id, year, date, amount, donor_id, donor_name, donor_kind, in_kind FROM state_gifts ORDER BY date"):
        if bio not in legislators:
            continue
        seg = segment(year)
        if (bio, did) in own:
            moved.setdefault(bio, Counter())[seg] += amount
            continue
        names.setdefault(did, Counter())[dname] += 1
        d = donors.setdefault(bio, {}).setdefault(did, {"id": did, "k": kind, "c": {}, "_p": {}})
        c = d["c"].setdefault(seg, [0.0, 0, None, None, 0.0])
        n = day(date)
        c[0] += amount
        c[1] += 1
        if n is not None:
            c[2] = n if c[2] is None else min(c[2], n)
            c[3] = n if c[3] is None else max(c[3], n)
        if in_kind:
            c[4] += amount
        p = d["_p"].setdefault((n, seg, 1 if in_kind else 0), 0.0)          # same-day payments are added together
        d["_p"][(n, seg, 1 if in_kind else 0)] = p + amount

    outside = {}
    if has("state_outside"):
        for bio, year, date, amount, side, sid, sname, skind in con.execute(
                "SELECT bioguide_id, year, date, amount, side, spender_id, spender_name, spender_kind FROM state_outside ORDER BY date"):
            if bio not in legislators:
                continue
            seg, n = segment(year), day(date)
            names.setdefault(sid, Counter())[sname] += 1
            d = outside.setdefault(bio, {"for": {}, "against": {}})["for" if side == "for" else "against"].setdefault(
                sid, {"id": sid, "k": skind if skind in KINDS else "pcf", "c": {}, "_p": {}})
            c = d["c"].setdefault(seg, [0.0, 0, None, None, 0.0])
            c[0] += amount
            c[1] += 1
            if n is not None:
                c[2] = n if c[2] is None else min(c[2], n)
                c[3] = n if c[3] is None else max(c[3], n)
            d["_p"][(n, seg, 0)] = d["_p"].get((n, seg, 0), 0.0) + amount

    # committees formed for several candidates (New Jersey's joint candidates committees, New York's multi-candidate
    # committees): the loader files them as "TITLE · 2025 general (shared by 3 candidates)" or "TITLE (shared by 3
    # candidates)", one row per member, so the page can name them
    shared = {}
    for reg, name, bio in con.execute("SELECT reg_num, name, bioguide_id FROM state_committees WHERE name LIKE '%(shared by %'"):
        m = re.match(r"(.*?)(?: · (\d{4}) \w+)? \(shared by (\d+) candidates?\)$", name or "")
        if m and bio in legislators:
            s = shared.setdefault(bio, {}).setdefault(m.group(1), {"n": m.group(1), "y": set(), "k": int(m.group(3))})
            if m.group(2):
                s["y"].add(int(m.group(2)))

    sources, offices = {}, {}
    for bio, office, year, source, amount in con.execute("SELECT bioguide_id, office, year, source, amount FROM state_sources"):
        if bio not in legislators:
            continue
        seg = segment(year)
        sources.setdefault(bio, {}).setdefault(seg, Counter())[SOURCE_KEYS.get(source, "other")] += amount
        if office:
            offices.setdefault(bio, {}).setdefault(seg, set()).add(office)

    best = lambda did: names[did].most_common(1)[0][0] if did in names else did

    def finish(d):
        pays = sorted(((n, round(a, 2), seg, ik) for (n, seg, ik), a in d.pop("_p").items()), key=lambda x: (x[0] is None, -(x[0] or 0)))
        d["n"] = best(d["id"])
        d["c"] = {str(seg): [round(c[0], 2), c[1], c[2], c[3], round(c[4], 2)] for seg, c in sorted(d["c"].items())}
        d["p"] = [[n, a, seg, ik] for n, a, seg, ik in pays[:MAX_PAYMENTS]]
        if len(pays) > MAX_PAYMENTS:
            d["more"] = len(pays) - MAX_PAYMENTS
        return d

    total = lambda d, seg=None: sum(c[0] for s, c in d["c"].items() if seg is None or s == str(seg))
    profiles, members = {}, {}
    grand = {"orgs": 0.0, "org_names": set(), "for": 0.0, "against": 0.0, "moved": 0.0}
    for bio in legislators:
        mine = [finish(d) for d in (donors.get(bio) or {}).values()]
        side = {k: [finish(d) for d in v.values()] for k, v in (outside.get(bio) or {"for": {}, "against": {}}).items()}
        segs = sorted({int(s) for d in mine for s in d["c"]} | set(sources.get(bio) or {}) | {int(s) for v in side.values() for d in v for s in d["c"]} | set(moved.get(bio) or {}), reverse=True)
        if not segs:
            continue
        mine.sort(key=lambda d: -total(d))
        for k in side:
            side[k].sort(key=lambda d: -total(d))
        views = [("all", None)] + [(str(s), s) for s in segs]
        top, summ, out, totals = {}, {}, {}, {}
        for name, seg in views:
            ranked = sorted(((total(d, seg), d) for d in mine), key=lambda x: -x[0])
            ranked = [(t, d) for t, d in ranked if t > 0]
            if ranked:
                top[name] = [[d["id"], d["n"], d["k"], round(t, 2)] for t, d in ranked[:10]]
            summ[name] = [round(sum(t for t, _d in ranked), 2), len(ranked)]
            out[name] = [round(sum(total(d, seg) for d in side["for"]), 2), round(sum(total(d, seg) for d in side["against"]), 2)]
            src = Counter()
            for s, c in (sources.get(bio) or {}).items():
                if seg is None or s == seg:
                    src.update(c)
            mv = sum(a for s, a in (moved.get(bio) or {}).items() if seg is None or s == seg)
            if mv:
                src["cand"] -= mv
                src["moved"] += mv
            if src:
                t = {k: round(v, 2) for k, v in src.items() if round(v, 2)}
                t["receipts"] = round(sum(t.values()), 2)
                totals[name] = t
        m = {"cycles": segs, "top": top, "sum": summ, "outside": out, "totals": totals,
             "offices": {str(s): sorted(o) for s, o in (offices.get(bio) or {}).items()}}
        profiles[bio] = m
        members[bio] = {"donors": mine, "for": side["for"], "against": side["against"],
                        "moved": {str(s): round(a, 2) for s, a in (moved.get(bio) or {}).items()}}
        if shared.get(bio):
            members[bio]["shared"] = [{"n": s["n"], "y": sorted(s["y"]), "k": s["k"]} for s in sorted(shared[bio].values(), key=lambda s: (-max(s["y"] or {0}), s["n"]))]
        grand["orgs"] += summ["all"][0]
        grand["org_names"] |= {d["id"] for d in mine}
        grand["for"] += out["all"][0]
        grand["against"] += out["all"][1]
        grand["moved"] += sum((moved.get(bio) or {}).values())
    y0, y1 = con.execute("SELECT MIN(year), MAX(year) FROM state_sources").fetchone()
    newest = con.execute("SELECT MAX(date) FROM state_gifts").fetchone()[0] or ""
    summary = {"from_orgs": round(grand["orgs"]), "orgs": len(grand["org_names"]), "outside_for": round(grand["for"]),
               "outside_against": round(grand["against"]), "moved": round(grand["moved"]), "members": len(profiles),
               "years": [y0, y1], "newest": newest[:10]}
    return {"profiles": profiles, "members": members, "kinds": KINDS, "summary": summary, "own_by_name": own_by_name}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", required=True)
    args = ap.parse_args()
    con = sqlite3.connect(args.db)
    legislators = {bio: {"n": full, "first": first, "last": last} for bio, full, first, last in
                   con.execute("SELECT bioguide_id, official_full, first_name, last_name FROM legislators WHERE is_current = 1")}
    money = build_state_money(con, legislators)
    s = money["summary"]
    print(f"{s.get('members', 0)} members with money on file, {s.get('years')}: ${s.get('from_orgs', 0):,} from {s.get('orgs', 0):,} named organizations; "
          f"outside spending ${s.get('outside_for', 0):,} for and ${s.get('outside_against', 0):,} against; "
          f"${s.get('moved', 0):,} moved in from members' own other committees")
    for line in money["own_by_name"]:
        print("  treated as the member's own committee, by name:", line)


if __name__ == "__main__":
    main()
