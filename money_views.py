#!/usr/bin/env python3
"""
money_views.py
==============
Shapes the FEC tables that load_donors.py fills into what the site shows. It reads the database and returns
plain data; build_site_dev.py writes the files. Nothing here judges anyone: it adds up public filings.

Who counts as a donor. An organization that gave to the member's own campaign: a PAC, a party committee,
another politician's committee. Two kinds of committee are set aside, because the money in them is the member's
own fundraising passing through, not a gift from someone else: joint fundraising committees, and the member's
own campaign committees. What they moved in is reported as a separate line.

Outside spending is kept apart from donations everywhere. It is money a group spent on its own to support or
oppose the member (independent expenditures, and membership groups' communications to their own members). The
campaign never received it.

    build_money(con, legislators) -> {"profiles": {bioguide: card summary}, "members": {bioguide: full file},
                                       "kinds": {code: label}}
"""

import datetime as dt

EPOCH = dt.date(2015, 1, 1)
TOP = 100                       # donors kept per member, overall and in each cycle
TOP_OUTSIDE = 50
MAX_PAYMENTS = 60               # per donor and member; same-day payments are added together first

KIND_LABELS = {
    "corp": "Corporate PAC", "labor": "Labor union PAC", "trade": "Trade association PAC",
    "memb": "Membership organization PAC", "coop": "Cooperative PAC", "cws": "Non-stock corporation PAC",
    "pac": "PAC with no sponsoring organization", "lead": "A politician's leadership PAC",
    "cand": "Another candidate's campaign", "party": "Party committee", "super": "Super PAC",
    "ie": "Group or person, not a committee", "comm": "Communication to its own members", "joint": "Joint fundraising committee",
    "other": "Other committee"}


def committee_kind(tp, dsgn, org):
    """One plain label for a committee, from the FEC's own three codes: committee type, designation, and the
    kind of organization connected to it."""
    tp, dsgn, org = (tp or "").upper(), (dsgn or "").upper(), (org or "").upper()
    if dsgn == "J":
        return "joint"
    if tp in ("X", "Y", "Z"):
        return "party"
    if dsgn == "D":
        return "lead"
    if tp in ("H", "S", "P"):
        return "cand"
    if tp in ("O", "U"):
        return "super"
    if tp == "I":
        return "ie"
    if tp in ("C", "E"):
        return "comm"
    if tp in ("Q", "N", "V", "W"):
        return {"C": "corp", "L": "labor", "T": "trade", "M": "memb", "V": "coop", "W": "cws"}.get(org, "pac")
    return "other"


def day(iso):
    try:
        return (dt.date(int(iso[:4]), int(iso[5:7]), int(iso[8:10])) - EPOCH).days if iso else None
    except (ValueError, TypeError):
        return None


def tidy_name(name):
    """FEC names are upper case and often end in the legal boilerplate; keep the name, drop the shouting."""
    n = " ".join((name or "").split())
    if not n:
        return ""
    small = {"OF", "THE", "AND", "FOR", "IN", "ON", "TO", "A", "AN", "AT", "BY"}
    keep = {"PAC", "USA", "US", "LLC", "LLP", "INC", "AFL-CIO", "AFL", "CIO", "UAW", "IBEW", "NRA", "AT&T", "UPS", "GE", "IBM", "BNSF",
            "CSX", "AIPAC", "AFSCME", "SEIU", "NEA", "AFT", "NAR", "ABA", "AMA", "CPA", "CPAS", "PEOPLE", "II", "III", "IV", "DC", "NY",
            "UFCW", "IAFF", "NATCA", "ALPA", "IUOE", "LIUNA", "BAC", "SMART", "USW", "CWA", "IAM", "UNITE", "HERE", "ACEC", "NFIB", "NAHB",
            "RNC", "DNC", "DCCC", "DSCC", "NRCC", "NRSC", "JPMORGAN", "BP", "3M", "HCA", "KPMG", "PWC", "EY", "RTX", "L3HARRIS", "CVS", "AFLAC"}
    out = []
    for i, w in enumerate(n.split(" ")):
        core = w.strip("().,'\"")
        if core.upper() in keep or (len(core) <= 4 and core.isupper() and not core.isalpha()):
            out.append(w.upper())
        elif i and core.upper() in small:
            out.append(w.lower())
        elif "-" in w:
            out.append("-".join(p.capitalize() for p in w.split("-")))
        elif w.upper().startswith("MC") and len(w) > 3:
            out.append("Mc" + w[2:].capitalize())
        else:
            out.append(w.capitalize())
    return " ".join(out)


def build_money(con, legislators):
    has = lambda t: con.execute("SELECT 1 FROM sqlite_master WHERE name = ?", (t,)).fetchone() is not None
    if not (has("fec_gifts") and has("fec_committees") and has("member_fec")):
        return {"profiles": {}, "members": {}, "kinds": KIND_LABELS, "cycles": []}

    cm = {}
    for cid, name, dsgn, tp, org, conn, cand in con.execute("SELECT cmte_id, name, designation, type, org_type, connected_org, cand_id FROM fec_committees"):
        cm[cid] = {"n": tidy_name(name) or cid, "k": committee_kind(tp, dsgn, org), "o": tidy_name(conn) if conn and conn.strip().upper() not in ("NONE", "N/A", "NA") else "", "cand": cand or ""}

    cands = {}
    for bio, cand in con.execute("SELECT bioguide_id, cand_id FROM member_fec"):
        cands.setdefault(bio, set()).add(cand)
    own = {}                                                     # each member's own committees: never a donor to themselves
    for cand, pcc in con.execute("SELECT DISTINCT cand_id, principal_committee FROM fec_candidates WHERE principal_committee <> ''"):
        for bio, cs in cands.items():
            if cand in cs:
                own.setdefault(bio, set()).add(pcc)
    for cid, c in cm.items():
        if c["cand"]:
            for bio, cs in cands.items():
                if c["cand"] in cs:
                    own.setdefault(bio, set()).add(cid)

    races, totals = {}, {}
    for cand, cycle, party, year, office, state, district, ici in con.execute(
            "SELECT cand_id, cycle, party, election_year, office, state, district, ici FROM fec_candidates"):
        races[(cand, cycle)] = {"o": office, "st": state, "d": district, "ici": ici or "", "y": year}
    for row in con.execute("SELECT cand_id, cycle, receipts, from_individuals, from_committees, from_party, from_candidate, candidate_loans, "
                           "other_loans, transfers_in, disbursements, cash_on_hand, coverage_end FROM fec_candidate_totals"):
        totals[(row[0], row[1])] = row[2:]

    terms = {}
    if has("member_terms"):
        for bio, typ, start, end in con.execute("SELECT bioguide_id, type, start, end FROM member_terms"):
            terms.setdefault(bio, []).append((typ, start or "", end or ""))

    # ---- one pass over every payment
    G = {}                                                       # bio -> group -> cmte -> cycle -> [total, n, first, last, P, G, other]
    PAY = {}                                                     # bio -> group -> cmte -> {(day, cycle, e): amount}
    moved, coord = {}, {}                                        # bio -> cycle -> [joint, own] ; bio -> cycle -> party coordinated spending
    group_of = {"gift": "gift", "for": "for", "talk_for": "for", "against": "against", "talk_against": "against"}
    for bio, cid, cycle, kind, election, date, amount in con.execute(
            "SELECT bioguide_id, cmte_id, cycle, kind, election, date, amount FROM fec_gifts"):
        if bio not in legislators:
            continue
        if kind == "party":
            c = coord.setdefault(bio, {}); c[cycle] = c.get(cycle, 0.0) + amount
            continue
        grp = group_of.get(kind)
        if not grp:
            continue
        if grp == "gift":
            k = (cm.get(cid) or {}).get("k", "other")
            mine = cid in own.get(bio, ())
            if mine or k == "joint":
                m = moved.setdefault(bio, {}).setdefault(cycle, [0.0, 0.0]); m[1 if mine else 0] += amount
                continue
        e = (election or " ")[0].upper()
        e = e if e in "PGRSCE" else "O"
        a = G.setdefault(bio, {}).setdefault(grp, {}).setdefault(cid, {}).setdefault(cycle, [0.0, 0, None, None, 0.0, 0.0, 0.0])
        a[0] += amount; a[1] += 1
        if date:
            a[2] = date if a[2] is None or date < a[2] else a[2]
            a[3] = date if a[3] is None or date > a[3] else a[3]
        a[4 if e == "P" else (5 if e == "G" else 6)] += amount
        p = PAY.setdefault(bio, {}).setdefault(grp, {}).setdefault(cid, {})
        key = (day(date), cycle, e)
        p[key] = p.get(key, 0.0) + amount

    all_cycles = sorted({r[0] for r in con.execute("SELECT DISTINCT cycle FROM fec_gifts")}, reverse=True)

    def ranked(by_cmte, top):
        """The committees to keep: the top `top` over all years, and the top `top` of each cycle."""
        overall = sorted(((sum(c[0] for c in cyc.values()), cid) for cid, cyc in by_cmte.items()), reverse=True)
        keep = [cid for t, cid in overall[:top] if t > 0]
        seen = set(keep)
        for cycle in all_cycles:
            per = sorted(((cyc[cycle][0], cid) for cid, cyc in by_cmte.items() if cycle in cyc), reverse=True)
            for t, cid in per[:top]:
                if t > 0 and cid not in seen:
                    seen.add(cid); keep.append(cid)
        return keep

    def rows_for(bio, grp, top):
        by_cmte = (G.get(bio) or {}).get(grp) or {}
        out = []
        for cid in ranked(by_cmte, top):
            c = cm.get(cid) or {"n": cid, "k": "other", "o": ""}
            cyc = {str(y): [round(v[0]), v[1], day(v[2]), day(v[3]), round(v[4]), round(v[5]), round(v[6])] for y, v in by_cmte[cid].items()}
            pays = sorted(((d if d is not None else -1, y, e, round(a)) for (d, y, e), a in PAY[bio][grp][cid].items() if round(a)), reverse=True)
            row = {"id": cid, "n": c["n"], "k": c["k"], "c": cyc, "p": [[d, a, y, e] for d, y, e, a in pays[:MAX_PAYMENTS]]}
            if c["o"] and c["o"].lower() not in c["n"].lower():
                row["o"] = c["o"]
            if len(pays) > MAX_PAYMENTS:
                row["more"] = len(pays) - MAX_PAYMENTS
            out.append(row)
        return out

    def office_at(bio, cycle):
        """What the member held during the two years of the cycle, from their terms."""
        a, b = f"{cycle - 1}-01-03", f"{cycle}-12-31"
        held = {typ for typ, start, end in terms.get(bio, []) if start <= b and end >= a}
        return "S" if "sen" in held else ("H" if "rep" in held else "")

    profiles, members = {}, {}
    for bio in legislators:
        if bio not in cands:
            continue
        cyc_set = set()
        for grp in ("gift", "for", "against"):
            for cyc in ((G.get(bio) or {}).get(grp) or {}).values():
                cyc_set |= set(cyc)
        tot, race = {}, {}
        for cycle in all_cycles:
            best = None
            for cand in cands[bio]:
                t = totals.get((cand, cycle))
                if t and (best is None or (t[0] or 0) > (best[1][0] or 0)):
                    best = (cand, t)
            sums = [0.0] * 10
            for cand in cands[bio]:
                t = totals.get((cand, cycle))
                if t:
                    for i in range(10):
                        sums[i] += t[i] or 0.0
            if best:
                receipts, people, pacs, party, self_c, self_l, other_l, transfers, spent, cash = sums
                rest = max(0.0, receipts - people - pacs - party - self_c - self_l - other_l - transfers)
                tot[str(cycle)] = {"receipts": round(receipts), "people": round(people), "orgs": round(pacs), "party": round(party),
                                   "self": round(self_c + self_l), "moved": round(transfers), "other": round(rest + other_l),
                                   "spent": round(spent), "cash": round(cash), "through": best[1][10] or ""}
                r = dict(races.get((best[0], cycle)) or {})
                r["held"] = office_at(bio, cycle)
                r["also"] = sorted({(races.get((c, cycle)) or {}).get("o", "") for c in cands[bio] if c != best[0] and (c, cycle) in totals} - {""})
                race[str(cycle)] = r
                cyc_set.add(cycle)
        if not cyc_set:
            continue
        if tot:                                                  # all years together, for the "2016 to now" view
            keys = ("receipts", "people", "orgs", "party", "self", "moved", "other", "spent")
            tot["all"] = dict({k: sum(t[k] for t in tot.values()) for k in keys}, through=max(t["through"] for t in tot.values()))
        cycles = sorted(cyc_set, reverse=True)
        donors = rows_for(bio, "gift", TOP)
        out_for, out_against = rows_for(bio, "for", TOP_OUTSIDE), rows_for(bio, "against", TOP_OUTSIDE)
        gifts = (G.get(bio) or {}).get("gift") or {}
        sums = {"all": [0, 0]}
        for cid, cyc in gifts.items():
            t = sum(v[0] for v in cyc.values())
            if t > 0:
                sums["all"][0] += t; sums["all"][1] += 1
            for y, v in cyc.items():
                if v[0] > 0:
                    s = sums.setdefault(str(y), [0, 0]); s[0] += v[0]; s[1] += 1
        sums = {k: [round(v[0]), v[1]] for k, v in sums.items()}
        outside = {"all": [0, 0]}
        for i, grp in enumerate(("for", "against")):
            for cid, cyc in ((G.get(bio) or {}).get(grp) or {}).items():
                for y, v in cyc.items():
                    o = outside.setdefault(str(y), [0, 0]); o[i] += v[0]; outside["all"][i] += v[0]
        outside = {k: [round(v[0]), round(v[1])] for k, v in outside.items()}
        mv = {str(y): [round(v[0]), round(v[1])] for y, v in (moved.get(bio) or {}).items()}
        co = {str(y): round(v) for y, v in (coord.get(bio) or {}).items() if round(v)}

        def top10(view):
            pick = lambda d: sum(v[0] for v in d["c"].values()) if view == "all" else (d["c"].get(view) or [0])[0]
            best = sorted(((pick(d), d) for d in donors), key=lambda x: -x[0])[:10]
            return [[d["id"], d["n"], d["k"], t] for t, d in best if t > 0]

        profiles[bio] = {"cycles": cycles, "races": race, "totals": tot, "sum": sums, "outside": outside,
                         "top": {v: top10(v) for v in ["all"] + [str(y) for y in cycles]}}
        members[bio] = {"cycles": cycles, "races": race, "totals": tot, "sum": sums, "outside": outside, "moved": mv, "coordinated": co,
                        "donors": donors, "for": out_for, "against": out_against}
    return {"profiles": profiles, "members": members, "kinds": KIND_LABELS, "cycles": all_cycles}


if __name__ == "__main__":                                       # a quick look: python money_views.py congress_119.sqlite K000367
    import json, sqlite3, sys
    con = sqlite3.connect(sys.argv[1])
    legs = {r[0]: {} for r in con.execute("SELECT bioguide_id FROM legislators")}
    out = build_money(con, legs)
    bio = sys.argv[2] if len(sys.argv) > 2 else next(iter(out["profiles"]))
    print(json.dumps(out["profiles"].get(bio), indent=1)[:3000])
    m = out["members"].get(bio) or {}
    print("donors kept:", len(m.get("donors", [])), " for:", len(m.get("for", [])), " against:", len(m.get("against", [])),
          " file bytes:", len(json.dumps(m, separators=(",", ":"))))
    sizes = sorted(len(json.dumps(v, separators=(",", ":"))) for v in out["members"].values())
    print("members:", len(sizes), " total MB:", round(sum(sizes) / 1e6, 1), " median KB:", sizes[len(sizes) // 2] // 1000, " max KB:", sizes[-1] // 1000)
