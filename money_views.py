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

Passed along. Some committees collect gifts that individual people earmark for a candidate and hand them on
(AIPAC's PAC, WinRed, Club for Growth's PAC and others). The law counts those as the people's gifts, not the
committee's, which is why a committee limited to $5,000 per election can show $300,000 to one candidate. They are
kept in the committee's total, because that is how the filing reads, and split out beside it: every line the
filer marked EARMARK, plus anything over $5,000 that a committee other than a party or a candidate sent one
candidate for one election. The split is a rule applied to public filings, and the page states the rule.

Outside spending is kept apart from donations everywhere. It is money a group spent on its own to support or
oppose the member (independent expenditures, and membership groups' communications to their own members). The
campaign never received it.

    build_money(con, legislators) -> {"profiles": {bioguide: card summary}, "members": {bioguide: full file},
                                       "kinds": {code: label}, "master": {...}, "summary": {...}}

The master list is the same set of donors the member pages show (each member's top hundred over all years, and
the top hundred of each cycle), one row per donor, member, cycle and election. The summary is worked out over
every gift, not only the kept ones. The donor map is a principal-component picture: each member is a list of what
the most widespread donors gave them (log dollars); the two directions along which members differ most are drawn.
It is arithmetic on public filings, and the page says how it is made.
"""

import datetime as dt

EPOCH = dt.date(2015, 1, 1)
TOP = 100                       # donors kept per member, overall and in each cycle
PAC_LIMIT = 5000.0              # what a multicandidate PAC may give one candidate for one election from its own funds
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
    def cap(w):      # capitalize from the first letter, so "(CALIFORNIA" becomes "(California", not "(california"
        k = next((j for j, ch in enumerate(w) if ch.isalpha()), None)
        return w if k is None else w[:k] + w[k:].capitalize()
    out = []
    for i, w in enumerate(n.split(" ")):
        core = w.strip("().,'\"")
        if core.upper() in keep or (len(core) <= 4 and core.isupper() and not core.isalpha()):
            out.append(w.upper())
        elif i and core.upper() in small:
            out.append(w.lower())
        elif "-" in w:
            out.append("-".join(cap(p) for p in w.split("-")))
        elif w.upper().startswith("MC") and len(w) > 3:
            out.append("Mc" + w[2:].capitalize())
        else:
            out.append(cap(w))
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
    BYE = {}                                                     # (bio, cmte, cycle, election) -> [total, n, first, last], gifts only
    CAP = {}                                                     # (bio, cmte, cycle, full election code) -> [not marked, marked earmark]
    group_of = {"gift": "gift", "for": "for", "talk_for": "for", "against": "against", "talk_against": "against"}
    has_flag = con.execute("SELECT 1 FROM pragma_table_info('fec_gifts') WHERE name = 'earmark'").fetchone() is not None
    for bio, cid, cycle, kind, election, date, amount, marked in con.execute(
            f"SELECT bioguide_id, cmte_id, cycle, kind, election, date, amount, {'earmark' if has_flag else '0'} FROM fec_gifts"):
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
        key = (day(date), cycle, e, 1 if (marked and grp == "gift") else 0)
        p[key] = p.get(key, 0.0) + amount
        if grp == "gift":
            c2 = CAP.setdefault((bio, cid, cycle, (election or "").strip().upper()), [0.0, 0.0])
            c2[1 if marked else 0] += amount
            x = BYE.setdefault((bio, cid, cycle, e), [0.0, 0, None, None])
            x[0] += amount; x[1] += 1
            if date:
                x[2] = date if x[2] is None or date < x[2] else x[2]
                x[3] = date if x[3] is None or date > x[3] else x[3]

    all_cycles = sorted({r[0] for r in con.execute("SELECT DISTINCT cycle FROM fec_gifts")}, reverse=True)

    # what each committee passed along from individual people, by member and cycle, and by election for the master list
    PASSED, PASSED_E = {}, {}
    for (bio, cid, cycle, code), (plain, flagged) in CAP.items():
        k = (cm.get(cid) or {}).get("k", "other")
        over = max(0.0, plain - PAC_LIMIT) if k not in ("party", "cand") else 0.0
        amt = max(0.0, flagged) + over
        if amt > 0:
            e = code[:1] if code[:1] in "PGRSCE" and code else "O"
            PASSED[(bio, cid, cycle)] = PASSED.get((bio, cid, cycle), 0.0) + amt
            PASSED_E[(bio, cid, cycle, e)] = PASSED_E.get((bio, cid, cycle, e), 0.0) + amt

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
            cyc = {str(y): [round(v[0]), v[1], day(v[2]), day(v[3]), round(v[4]), round(v[5]), round(v[6]),
                            round(min(max(v[0], 0.0), PASSED.get((bio, cid, y), 0.0))) if grp == "gift" else 0] for y, v in by_cmte[cid].items()}
            pays = sorted(((d if d is not None else -1, y, e, round(a), em) for (d, y, e, em), a in PAY[bio][grp][cid].items() if round(a)), reverse=True)
            row = {"id": cid, "n": c["n"], "k": c["k"], "c": cyc, "p": [[d, a, y, e] + ([1] if em else []) for d, y, e, a, em in pays[:MAX_PAYMENTS]]}
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
            pick = lambda d, i: sum(v[i] for v in d["c"].values()) if view == "all" else (d["c"].get(view) or [0] * 8)[i]
            best = sorted(((pick(d, 0), d) for d in donors), key=lambda x: -x[0])[:10]
            return [[d["id"], d["n"], d["k"], t, pick(d, 7)] for t, d in best if t > 0]

        profiles[bio] = {"cycles": cycles, "races": race, "totals": tot, "sum": sums, "outside": outside,
                         "top": {v: top10(v) for v in ["all"] + [str(y) for y in cycles]}}
        members[bio] = {"cycles": cycles, "races": race, "totals": tot, "sum": sums, "outside": outside, "moved": mv, "coordinated": co,
                        "donors": donors, "for": out_for, "against": out_against}
    master = build_master(members, BYE, all_cycles, PASSED_E)
    summary = build_summary(G, cm, legislators, profiles, all_cycles, PASSED)
    return {"profiles": profiles, "members": members, "kinds": KIND_LABELS, "cycles": all_cycles, "master": master, "summary": summary}


def build_master(members, BYE, cycles, passed_e):
    """index: the donors and members the rows point at.
    rows[cycle]: [donor, member, election, amount, payments, first, last, of which passed along from individuals]."""
    donors, d_at, m_list = [], {}, sorted(members)
    m_at = {bio: i for i, bio in enumerate(m_list)}
    kept = {}
    for bio, m in members.items():
        for d in m["donors"]:
            if d["id"] not in d_at:
                d_at[d["id"]] = len(donors)
                donors.append([d["id"], d["n"], d["k"], d.get("o", "")])
            kept.setdefault(bio, set()).add(d["id"])
    rows = {str(c): [] for c in cycles}
    for (bio, cid, cycle, e), v in BYE.items():
        if cid in kept.get(bio, ()) and round(v[0]):
            rows[str(cycle)].append([d_at[cid], m_at[bio], "PGRSCEO".index(e), round(v[0]), v[1], day(v[2]), day(v[3]),
                                     round(min(max(v[0], 0.0), passed_e.get((bio, cid, cycle, e), 0.0)))])
    for r in rows.values():
        r.sort(key=lambda x: -x[3])
    return {"index": {"cycles": cycles, "donors": donors, "members": m_list, "rows": {c: len(r) for c, r in rows.items()}}, "rows": rows}


def principal_axes(vectors, n_cols, iters=120):
    """The first two principal components of sparse rows ({col: value}), by power iteration with the column means
    taken out on the fly (so the rows stay sparse). Returns (scores per row for each axis, share of variance, loadings)."""
    n = len(vectors)
    mean = [0.0] * n_cols
    for row in vectors:
        for j, v in row.items():
            mean[j] += v / n
    total_var = sum(sum((v - mean[j]) ** 2 for j, v in row.items()) + sum(mean[j] ** 2 for j in range(n_cols) if j not in row) for row in vectors) or 1.0

    def times(vec):                                              # X_c . vec
        mv = sum(m * x for m, x in zip(mean, vec))
        return [sum(v * vec[j] for j, v in row.items()) - mv for row in vectors]

    def times_t(u):                                              # X_c^T . u
        out, su = [0.0] * n_cols, sum(u)
        for row, ui in zip(vectors, u):
            if ui:
                for j, v in row.items():
                    out[j] += v * ui
        return [o - m * su for o, m in zip(out, mean)]

    axes, shares = [], []
    for k in range(2):
        vec = [(1.0 if (j * (k + 3)) % 7 < 4 else -1.0) for j in range(n_cols)]      # a fixed start, so every build gives the same picture
        lam = 0.0
        for _ in range(iters):
            for prev in axes:                                    # keep clear of the axes already found
                dot = sum(a * b for a, b in zip(vec, prev))
                vec = [a - dot * b for a, b in zip(vec, prev)]
            w = times_t(times(vec))
            norm = sum(x * x for x in w) ** .5 or 1.0
            nxt = [x / norm for x in w]
            done = sum(abs(a - b) for a, b in zip(nxt, vec)) < 1e-7
            vec, lam = nxt, norm
            if done:
                break
        axes.append(vec); shares.append(lam / total_var)
    return [times(a) for a in axes], shares, axes


def build_summary(G, cm, legislators, profiles, cycles, passed):
    party = lambda bio: {"D": "D", "R": "R"}.get((legislators.get(bio) or {}).get("p"), "I")
    chamber = lambda bio: "S" if (legislators.get(bio) or {}).get("ch") == "Senate" else "H"
    current = {bio for bio, L in legislators.items() if L.get("cur")}
    views = ["all"] + [str(c) for c in cycles]

    # where the money came from, added up for groups of members (from the campaigns' own reports)
    keys = ("receipts", "people", "orgs", "party", "self", "moved", "other")
    sources = {v: {} for v in views}
    for bio, prof in profiles.items():
        if bio not in current:
            continue
        for v in views:
            t = (prof.get("totals") or {}).get(v)
            if not t:
                continue
            for grp in ("all", party(bio), chamber(bio)):
                s_ = sources[v].setdefault(grp, dict.fromkeys(keys, 0) | {"n": 0})
                for k in keys:
                    s_[k] += t[k]
                s_["n"] += 1

    # who gave the most, split by the party of the members they gave to
    top, top_own, totals = {v: {} for v in views}, {v: {} for v in views}, {v: {} for v in views}
    give = {}                                                    # (view, chamber) -> cmte -> [D, R, I, members, D own, R own, I own]
    for bio, groups in G.items():
        if bio not in current:
            continue
        pi = "DRI".index(party(bio))
        for cid, cyc in (groups.get("gift") or {}).items():
            whole = own_whole = 0.0
            for y, a in cyc.items():
                own_amt = a[0] - min(max(a[0], 0.0), passed.get((bio, cid, y), 0.0))
                whole += a[0]; own_whole += own_amt
                for ch in ("all", chamber(bio)):
                    g = give.setdefault((str(y), ch), {}).setdefault(cid, [0.0, 0.0, 0.0, 0, 0.0, 0.0, 0.0])
                    g[pi] += a[0]; g[3] += 1 if a[0] > 0 else 0; g[4 + pi] += own_amt
            for ch in ("all", chamber(bio)):
                g = give.setdefault(("all", ch), {}).setdefault(cid, [0.0, 0.0, 0.0, 0, 0.0, 0.0, 0.0])
                g[pi] += whole; g[3] += 1 if whole > 0 else 0; g[4 + pi] += own_whole
    for (v, ch), by in give.items():
        line = lambda cid, g: [cid, (cm.get(cid) or {}).get("n", cid), (cm.get(cid) or {}).get("k", "other"), round(g[0]), round(g[1]), round(g[2]), g[3],
                               round(g[4]), round(g[5]), round(g[6])]
        ranked = sorted(by.items(), key=lambda kv: -(kv[1][0] + kv[1][1] + kv[1][2]))
        top[v][ch] = [line(cid, g) for cid, g in ranked[:25] if g[0] + g[1] + g[2] > 0]
        ranked_own = sorted(by.items(), key=lambda kv: -(kv[1][4] + kv[1][5] + kv[1][6]))      # the same list, counting only each committee's own money
        top_own[v][ch] = [line(cid, g) for cid, g in ranked_own[:25] if g[4] + g[5] + g[6] > 0]
        pos = [g for g in by.values() if g[0] + g[1] + g[2] > 0]
        totals[v][ch] = [round(sum(g[0] + g[1] + g[2] for g in pos)), len(pos), round(sum(g[0] for g in pos)), round(sum(g[1] for g in pos)), round(sum(g[2] for g in pos)),
                         round(sum(g[4] + g[5] + g[6] for g in pos))]

    # the donor map: members placed by the donors they share, over the two newest cycles
    recent = [c for c in cycles[:2]]
    reach = {}
    for bio, groups in G.items():
        if bio in current:
            for cid, cyc in (groups.get("gift") or {}).items():
                if sum(cyc[y][0] for y in recent if y in cyc) > 0:
                    reach[cid] = reach.get(cid, 0) + 1
    cols = [cid for cid, n in sorted(reach.items(), key=lambda kv: (-kv[1], kv[0])) if n >= 12][:400]
    at = {cid: j for j, cid in enumerate(cols)}
    import math
    who, vectors = [], []
    for bio in sorted(current):
        row = {}
        for cid, cyc in ((G.get(bio) or {}).get("gift") or {}).items():
            amt = sum(cyc[y][0] for y in recent if y in cyc)
            if amt > 0 and cid in at:
                row[at[cid]] = math.log10(1 + amt)
        if len(row) >= 5:
            who.append(bio); vectors.append(row)
    points, axes_info = {}, {}
    if len(who) >= 20 and cols:
        scores, shares, axes = principal_axes(vectors, len(cols))
        d_mean = [sum(s for s, b in zip(sc, who) if party(b) == "D") / max(1, sum(1 for b in who if party(b) == "D")) for sc in scores]
        r_mean = [sum(s for s, b in zip(sc, who) if party(b) == "R") / max(1, sum(1 for b in who if party(b) == "R")) for sc in scores]
        flip = [-1.0 if d_mean[0] > r_mean[0] else 1.0, 1.0]     # Democrats to the left, as on the chamber floor
        for k in range(2):
            hi = max(abs(x) for x in scores[k]) or 1.0
            scores[k] = [flip[k] * x / hi for x in scores[k]]
            order = sorted(range(len(cols)), key=lambda j: flip[k] * axes[k][j])
            name = lambda j: (cm.get(cols[j]) or {}).get("n", cols[j])
            axes_info[str(k)] = {"share": round(shares[k], 4), "low": [name(j) for j in order[:4]], "high": [name(j) for j in order[-4:][::-1]]}
        for i, bio in enumerate(who):
            points[bio] = [round(scores[0][i], 4), round(scores[1][i], 4)]
    dots = {}
    for bio in sorted(current):
        prof = profiles.get(bio)
        if not prof:
            continue
        rec = [(prof.get("totals") or {}).get(str(y)) for y in recent]
        receipts = sum(t["receipts"] for t in rec if t)
        orgs = sum(t["orgs"] + t["party"] for t in rec if t)
        gifts = (G.get(bio) or {}).get("gift") or {}
        best = sorted(((sum(cyc[y][0] for y in recent if y in cyc), cid) for cid, cyc in gifts.items()), reverse=True)[:3]
        dots[bio] = {"xy": points.get(bio), "orgs": round(orgs), "receipts": round(receipts),
                     "top": [[(cm.get(cid) or {}).get("n", cid), round(t)] for t, cid in best if t > 0]}
    return {"views": views, "sources": sources, "top": top, "top_own": top_own, "totals": totals, "limit": PAC_LIMIT,
            "map": {"cycles": recent, "donors": len(cols), "members": len(who), "axes": axes_info, "dots": dots}}


if __name__ == "__main__":                                       # a quick look: python money_views.py congress_119.sqlite K000367
    import json, sqlite3, sys
    con = sqlite3.connect(sys.argv[1])
    legs = {r[0]: {"p": r[1], "ch": r[2], "cur": r[3]} for r in con.execute("SELECT bioguide_id, party, chamber, is_current FROM legislators")}
    out = build_money(con, legs)
    bio = sys.argv[2] if len(sys.argv) > 2 else next(iter(out["profiles"]))
    print(json.dumps(out["profiles"].get(bio), indent=1)[:3000])
    m = out["members"].get(bio) or {}
    print("donors kept:", len(m.get("donors", [])), " for:", len(m.get("for", [])), " against:", len(m.get("against", [])),
          " file bytes:", len(json.dumps(m, separators=(",", ":"))))
    sizes = sorted(len(json.dumps(v, separators=(",", ":"))) for v in out["members"].values())
    print("members:", len(sizes), " total MB:", round(sum(sizes) / 1e6, 1), " median KB:", sizes[len(sizes) // 2] // 1000, " max KB:", sizes[-1] // 1000)
    ms = out["master"]
    print("master: donors", len(ms["index"]["donors"]), " rows per cycle", ms["index"]["rows"], " index KB", len(json.dumps(ms["index"], separators=(",", ":"))) // 1000,
          " rows MB", {c: round(len(json.dumps(r, separators=(",", ":"))) / 1e6, 2) for c, r in ms["rows"].items()})
    sm = out["summary"]
    print("summary KB:", len(json.dumps(sm, separators=(",", ":"))) // 1000, " map:", {k: v for k, v in sm["map"].items() if k != "dots"})
    print("top 5, all years:", [(t[1][:40], t[3], t[4]) for t in sm["top"]["all"]["all"][:5]])
    print("top 5, 2024, all money:", [(t[1][:34], t[3] + t[4] + t[5]) for t in sm["top"]["2024"]["all"][:5]])
    print("top 5, 2024, own money:", [(t[1][:34], t[7] + t[8] + t[9]) for t in sm["top_own"]["2024"]["all"][:5]])
    print("2024 totals [all, orgs, D, R, I, own]:", sm["totals"]["2024"]["all"])
    print("sources 2024 all:", sm["sources"].get("2024", {}).get("all"))
