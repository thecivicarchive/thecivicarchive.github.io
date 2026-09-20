#!/usr/bin/env python3
"""
build_site.py
=============
Turns a congress_catalog.py database (plus its ratings) into one self-contained HTML page:
a working prototype of the public site. No server, no framework; the data is embedded.

    python build_site.py --db congress_119.sqlite --out site.html
    python build_site.py --db demo_catalog.sqlite --out congress_site_demo.html

Every measure on the page comes from the database; nothing is hand-entered here. (The five 2025-26
measures in the demo were transcribed into Bill Status XML with facts_to_billstatus.py.)
"""

import argparse
import base64
import datetime as dt
import json
import os
import re
import sqlite3

FIPS = {"01": "AL", "02": "AK", "04": "AZ", "05": "AR", "06": "CA", "08": "CO", "09": "CT", "10": "DE", "11": "DC", "12": "FL",
        "13": "GA", "15": "HI", "16": "ID", "17": "IL", "18": "IN", "19": "IA", "20": "KS", "21": "KY", "22": "LA", "23": "ME",
        "24": "MD", "25": "MA", "26": "MI", "27": "MN", "28": "MS", "29": "MO", "30": "MT", "31": "NE", "32": "NV", "33": "NH",
        "34": "NJ", "35": "NM", "36": "NY", "37": "NC", "38": "ND", "39": "OH", "40": "OK", "41": "OR", "42": "PA", "44": "RI",
        "45": "SC", "46": "SD", "47": "TN", "48": "TX", "49": "UT", "50": "VT", "51": "VA", "53": "WA", "54": "WV", "55": "WI", "56": "WY"}


def state_paths(topo_path):
    """Decode the pre-projected us-atlas TopoJSON (Albers USA, 975x610) into SVG path strings per state."""
    t = json.load(open(topo_path, encoding="utf-8"))
    sc, tr = t["transform"]["scale"], t["transform"]["translate"]

    def decode(arc):
        x = y = 0
        pts = []
        for dx, dy in arc:
            x += dx
            y += dy
            pts.append((x * sc[0] + tr[0], y * sc[1] + tr[1]))
        return pts
    arcs = [decode(a) for a in t["arcs"]]

    def ring(idxs):
        pts = []
        for i in idxs:
            seg = arcs[i] if i >= 0 else arcs[~i][::-1]
            pts.extend(seg if not pts else seg[1:])
        return pts
    out = {}
    for g in t["objects"]["states"]["geometries"]:
        st = FIPS.get(g["id"])
        if not st:
            continue
        polys = g["arcs"] if g["type"] == "MultiPolygon" else [g["arcs"]]
        d, xs, ys = [], [], []
        for poly in polys:
            for r in poly:
                pts = ring(r)
                d.append("M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in pts) + "Z")
                xs += [p[0] for p in pts]
                ys += [p[1] for p in pts]
        out[st] = {"d": "".join(d), "bbox": [round(min(xs), 1), round(min(ys), 1), round(max(xs), 1), round(max(ys), 1)],
                   "name": g["properties"]["name"]}
    return out


def legislator_rows(con, ids):
    if not con.execute("SELECT 1 FROM sqlite_master WHERE name = 'legislators'").fetchone():
        return {}
    cols = [d[0] for d in con.execute("SELECT * FROM legislators LIMIT 0").description]
    rows = {}
    q = "SELECT * FROM legislators WHERE is_current = 1"
    if ids:
        q += f" OR bioguide_id IN ({','.join('?' * len(ids))})"
    for r in con.execute(q, tuple(ids)):
        m = dict(zip(cols, r))
        rows[m["bioguide_id"]] = {"n": m["official_full"], "p": m["party"], "st": m["state"], "d": m["district"],
                                  "ch": m["chamber"], "b": m["birthday"], "f": m["first_term_start"], "u": m["url"],
                                  "ph": m["phone"], "cf": m["contact_form"], "of": m["office"], "cur": m["is_current"]}
    return rows


def jload(s, default):
    try:
        return json.loads(s) if s else default
    except ValueError:
        return default


def display_title(title, short):
    """A readable card title: the official short title when the pipeline found one, else a plain rewrite."""
    if short:
        return short
    m = re.search(r'disapproval .*?rule submitted by the (.+?) relating to ["\u201c]?(.+?)["\u201d]?\.?$', title, re.I | re.S)
    if m:
        rule = re.sub(r"\s+", " ", m.group(2)).strip(' ."\u201c\u201d')
        return f"Repeal of the {m.group(1).strip()} rule on {rule[:80]}{'\u2026' if len(rule) > 80 else ''}"
    m = re.match(r"Proposing an amendment to the Constitution of the United States (?:to |relative to |relating to )?(.+?)\.?$", title, re.I | re.S)
    if m:
        return "Constitutional amendment to " + m.group(1).strip()[:90]
    m = re.match(r"(?:An original )?(?:A )?concurrent resolution setting forth the congressional budget .*?for fiscal year (\d{4})", title, re.I | re.S)
    if m:
        return f"Budget resolution for fiscal year {m.group(1)}"
    t = re.sub(r"^(A bill |A joint resolution |A resolution |A concurrent resolution )", "", title).strip()
    t = t[0].upper() + t[1:] if t else t
    return t if len(t) <= 90 else t[:88].rsplit(" ", 1)[0] + "…"


FORMAL_TITLE = re.compile(r"^(An act |To |A bill |A joint resolution|A concurrent resolution|A resolution|An original|Providing for|"
                          r"Proposing|Making |Expressing|Recognizing|Authorizing|Designating|Disapproving|Approving|Provides for|Relating to)", re.I)


def same_name(a, b):
    """True when two titles are the same name give or take a year, "Act", "of", "the"."""
    norm = lambda t: re.sub(r"[^a-z]", "", re.sub(r"\b(of|act|the|and)\b|\d{4}", "", (t or "").lower()))
    x, y = norm(a), norm(b)
    return bool(x and y) and (x == y or x in y or y in x)


def lead_names(con):
    """The names the record itself offers to lead with: bill_key -> {"popular", "short", "amend"}.

    `popular` is the popular title the Library of Congress records for a few measures ("One Big Beautiful
    Bill Act"). `short` is the short title a measure carried at its latest stage, for measures whose only
    other title is a formal one ("An act to provide for..."). `amend` lists the short titles the other
    chamber's amendment gave the bill, as (chamber, title): when none of them is the name the bill is known
    by, that chamber replaced the bill's text with something else (the Veterans Accessibility Advisory
    Committee Act became the SAVE America Act), and the bill should lead with what it became.
    Needs the `titles` table that `python run_all.py titles` loads; without it nothing changes."""
    if not con.execute("SELECT 1 FROM sqlite_master WHERE name = 'titles'").fetchone():
        return {}
    rank = lambda tt: 0 if ("Enacted" in tt or "ENR" in tt) else 1 if "Passed" in tt else 2 if ("Reported" in tt or "PCS" in tt or "RFS" in tt) else 3
    out, best = {}, {}
    for key, tt, ti in con.execute("SELECT bill_key, title_type, title FROM titles ORDER BY rowid"):
        low, e = tt.lower(), out.setdefault(key, {})
        if low.startswith("popular"):
            e.setdefault("popular", ti)
        elif low.startswith("short title") and "portions" not in low:
            if "engrossed amendment" in low and "bill text" in low:
                e.setdefault("amend", []).append(("House" if "House" in tt else "Senate", ti))
            if not FORMAL_TITLE.match(ti) and (key not in best or rank(tt) < best[key]):
                best[key], e["short"] = rank(tt), ti
    return out


def load_nicknames():
    """Names in common use that are not in the official record, kept by hand in nicknames.json and shown as
    "commonly called ...". Only entries John has approved ("approved": true) are used, and each needs a source."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nicknames.json")
    try:
        raw = json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    out = {}
    for key, e in (raw.get("names") or {}).items():
        if isinstance(e, dict) and e.get("approved") is True and e.get("name") and e.get("source"):
            out[key] = {"name": str(e["name"]).strip(), "source": str(e["source"]).strip(), "lead": bool(e.get("lead"))}
    return out


LITE_STATUSES = {"", "Introduced", "In committee"}
POSITION_CODE = {"Yea": "Y", "Aye": "Y", "Nay": "N", "No": "N", "Present": "P"}


def member_profiles(con, legislators, vote_meta):
    """Who each member is, beyond the vote in front of the reader: bioguide_id -> profile.

    `service`, `committees` and `social` are facts from the roster project (the `profiles` stage loads them).
    `votes` and `focus` are worked out here from this database by rules the page states in full: a vote is a
    party split when most Democrats voted one way and most Republicans the other, and party is the one
    recorded on each roll call. `wiki` is the opening of the member's Wikipedia article, which the page fences
    off as not an official record. Nothing here characterises anyone; it counts."""
    has = lambda t: con.execute("SELECT 1 FROM sqlite_master WHERE name = ?", (t,)).fetchone() is not None
    out = {bio: {} for bio in legislators}

    if has("member_terms"):
        by = {}
        for bio, typ, start, end, party, how in con.execute("SELECT bioguide_id, type, start, end, party, how FROM member_terms ORDER BY bioguide_id, seq"):
            by.setdefault(bio, []).append({"type": typ, "start": start or "", "end": end or "", "party": party or "", "how": how or ""})
        chamber = lambda t: "Senate" if t == "sen" else "House"
        for bio, ts in by.items():
            if bio not in out or not ts:
                continue
            run = [ts[-1]]                                   # the unbroken run of terms in the chamber they sit in now
            for t in reversed(ts[:-1]):
                if t["type"] != run[0]["type"]:
                    break
                run.insert(0, t)
            other = [t for t in ts if t["type"] != run[0]["type"]]
            parties = []
            for t in ts:
                if t["party"] and (not parties or parties[-1] != t["party"]):
                    parties.append(t["party"])
            end_year = int(run[-1]["end"][:4]) if run[-1]["end"][:4].isdigit() else 0
            cur = bool((legislators.get(bio) or {}).get("cur"))
            out[bio]["service"] = {
                "chamber": chamber(run[0]["type"]), "since": run[0]["start"], "terms": len(run), "all_terms": len(ts),
                "appointed": run[0]["how"] == "appointment",
                "other": ({"chamber": chamber(other[0]["type"]), "from": min(t["start"] for t in other)[:4],
                           "to": max(t["end"] for t in other)[:4]} if other else None),
                "parties": parties, "next": (end_year - 1) if (cur and end_year) else None}

    if has("member_committees"):
        full, subs = {}, {}
        for bio, name, parent, title, rank in con.execute("SELECT bioguide_id, name, parent, title, rank FROM member_committees ORDER BY rank"):
            if bio not in out:
                continue
            if parent:
                subs.setdefault((bio, parent), []).append({"name": name, "title": title or ""})
            else:
                full.setdefault(bio, []).append({"name": name, "title": title or ""})
        for bio, cs in full.items():
            for c in cs:
                c["subs"] = sorted(subs.get((bio, c["name"]), []), key=lambda x: (not x["title"], x["name"]))
            out[bio]["committees"] = sorted(cs, key=lambda x: (not x["title"], x["name"]))

    if has("member_social"):
        for bio, tw, fb, yt, ig in con.execute("SELECT bioguide_id, twitter, facebook, youtube, instagram FROM member_social"):
            if bio in out:
                out[bio]["social"] = {k: v for k, v in (("twitter", tw), ("facebook", fb), ("youtube", yt), ("instagram", ig)) if v}

    if has("member_wikipedia"):
        for bio, title, extract, url in con.execute("SELECT bioguide_id, title, extract, url FROM member_wikipedia"):
            if bio in out and extract:
                out[bio]["wiki"] = {"title": title, "extract": extract, "url": url}

    if has("member_votes"):
        side = {"Yea": "Y", "Aye": "Y", "Nay": "N", "No": "N"}
        rows, tally = {}, {}
        for vid, mk, party, pos in con.execute("SELECT vote_id, member_key, party, position FROM member_votes"):
            p = "D" if party == "D" else ("R" if party == "R" else "")
            s = side.get(pos or "")
            rows.setdefault(mk, []).append((vid, p, s, pos or ""))
            if p and s:
                t = tally.setdefault(vid, {"D": [0, 0], "R": [0, 0]})
                t[p][0 if s == "Y" else 1] += 1
        lean = {}
        for vid, t in tally.items():
            d = "Y" if t["D"][0] > t["D"][1] else ("N" if t["D"][1] > t["D"][0] else "")
            r = "Y" if t["R"][0] > t["R"][1] else ("N" if t["R"][1] > t["R"][0] else "")
            lean[vid] = (d, r)
        meta = {v["vote_id"]: v for v in vote_meta}
        for bio, votes in rows.items():
            if bio not in out:
                continue
            n = agree = split_n = split_with = missed = cast = 0
            breaks, party = [], ""
            for vid, p, s, pos in votes:
                if pos == "Not Voting":
                    missed += 1
                if s:
                    cast += 1                                  # a yes or a no, whatever the party
                if not s or not p or vid not in lean:
                    continue
                party = p
                mine, theirs = lean[vid][0 if p == "D" else 1], lean[vid][1 if p == "D" else 0]
                n += 1
                agree += 1 if (mine and s == mine) else 0
                if mine and theirs and mine != theirs:
                    split_n += 1
                    if s == mine:
                        split_with += 1
                    elif vid in meta:
                        breaks.append(vid)
            breaks.sort(key=lambda v: (meta[v].get("date") or "", meta[v].get("roll") or 0), reverse=True)
            out[bio]["votes"] = {
                "party": party, "n": n, "cast": cast, "with": agree, "split_n": split_n, "split_with": split_with,
                "missed": missed, "eligible": len(votes), "breaks_n": len(breaks),
                "breaks": [{"vote_id": v, "bill": meta[v]["bill"], "title": meta[v]["title"], "date": meta[v]["date"],
                            "category": meta[v]["category"], "pos": next(s for x, _p, s, _o in votes if x == v)} for v in breaks[:5]]}

    areas, counts = {}, {}
    for bio, area, k in con.execute("SELECT s.bioguide_id, b.policy_area, COUNT(*) FROM sponsorships s JOIN bills b ON b.bill_key = s.bill_key "
                                    "WHERE s.role = 'sponsor' AND b.policy_area <> '' GROUP BY 1, 2 ORDER BY 3 DESC"):
        areas.setdefault(bio, []).append([area, k])
    for bio, role, k, laws in con.execute("SELECT s.bioguide_id, s.role, COUNT(*), SUM(CASE WHEN b.law_number IS NOT NULL AND b.law_number <> '' THEN 1 ELSE 0 END) "
                                          "FROM sponsorships s JOIN bills b ON b.bill_key = s.bill_key GROUP BY 1, 2"):
        c = counts.setdefault(bio, {"sponsored": 0, "cosponsored": 0, "laws": 0})
        if role == "sponsor":
            c["sponsored"], c["laws"] = k, laws or 0
        else:
            c["cosponsored"] += k
    for bio, c in counts.items():
        if bio in out and (c["sponsored"] or c["cosponsored"]):
            out[bio]["focus"] = dict(c, areas=(areas.get(bio) or [])[:4])
    return out


STALL_DAYS = 180


def journey_for(con, b, cutoff):
    """Where a measure stands on the road from introduction to law, from the record alone.

    Six stops: introduced, committee, the chamber it started in, the other chamber, the President, law
    (a constitutional amendment goes to the states instead of the President). `at` is the furthest stop
    reached; `dates` holds the day each stop was reached when the record says; `fail` marks the stop it
    fell at and why; `st` flags a measure nothing has happened to for STALL_DAYS, counted from the newest
    action anywhere in the data rather than from today, so an old copy of the database still reads sensibly.
    """
    key = b["bill_key"]
    first, second = ("Senate", "House") if (b["origin_chamber"] or "") == "Senate" else ("House", "Senate")
    amend = (b["title"] or "").startswith("Proposing an amendment to the Constitution")
    status, law = b["status"] or "", b["law_number"] or ""
    dates = [b["introduced_date"] or "", "", "", "", "", ""]
    row = con.execute("SELECT MIN(action_date) FROM committee_actions WHERE bill_key = ? AND action_date <> ''", (key,)).fetchone()
    dates[1] = (row[0] or "") if row else ""
    voted = {}                                   # the day each chamber passed it: an outright "Passed" beats "Agreed to", latest wins
    for ch, res, day in con.execute("SELECT chamber, result, MAX(vote_date) FROM floor_votes WHERE bill_key = ? AND category = 'Passage' "
                                    "AND result IN ('Passed', 'Agreed to') GROUP BY chamber, result", (key,)):
        if res == "Passed" or ch not in voted:
            voted[ch] = day or ""
    texts = dict(con.execute("SELECT version_type, MIN(version_date) FROM text_versions WHERE bill_key = ? AND version_date <> '' "
                             "GROUP BY version_type", (key,)))
    passed_on = lambda ch: voted.get(ch) or texts.get(f"Engrossed in {ch}") or texts.get(f"Considered and Passed {ch}") or ""
    got = {"House": bool(b["passed_house"]), "Senate": bool(b["passed_senate"])}
    at = 0 if status == "Introduced" else 1
    if got[first] or got[second]:
        at, dates[2] = 2, passed_on(first)
    if got[second]:
        at, dates[3] = 3, passed_on(second)
    if status == "Presented to President" or status.startswith("Vetoed") or law:
        at = 4
        dates[4] = texts.get("Enrolled Bill") or (b["latest_action_date"] if status == "Presented to President" else "") or ""
    if law:
        at = 5
        dates[5] = (b["latest_action_date"] if (b["latest_action"] or "").startswith("Became") else "") or texts.get("Public Law") or b["latest_action_date"] or ""
    fail = None
    if status.startswith("Failed floor vote in"):
        ch = "House" if "in House" in status else "Senate"
        i = 2 if ch == first else 3
        r = con.execute("SELECT vote_date, yeas, nays FROM floor_votes WHERE bill_key = ? AND chamber = ? AND result IN ('Failed', 'Rejected', "
                        "'Not invoked') ORDER BY vote_date DESC LIMIT 1", (key, ch)).fetchone()
        tally = f", {r[1]}\u2013{r[2]}" if r and r[1] is not None else ""
        fail = {"i": i, "why": f"Failed a floor vote in the {ch}{tally}", "d": (r[0] if r else "") or b["latest_action_date"] or ""}
        at = i - 1
    elif status.startswith("Vetoed"):
        fail = {"i": 4, "why": "Vetoed by the President" + ("; the override failed" if "override failed" in status else ""),
                "d": b["latest_action_date"] or ""}
        at = 3
    if fail:
        note = fail["why"]
    elif law:
        note = f"Became law: {'Private' if (b['law_kind'] or '') == 'Private' else 'Public'} Law {law}"
    elif at == 4:
        note = "Passed both chambers; waiting on the President"
    elif at == 3:
        note = ("Passed both chambers in different forms; the differences are not settled yet" if "unresolved" in status
                else ("Passed both chambers; it goes to the states next" if amend else "Passed both chambers; on its way to the President"))
    elif at == 2:
        note = f"Passed the {first}; waiting on the {second}"
    elif at == 1:
        note = "Reported by committee; waiting for a floor vote" if status.startswith("Reported") else "In committee"
    else:
        note = "Introduced; not yet sent to a committee"
    stalled = not fail and not law and (b["latest_action_date"] or "") < cutoff
    return {"at": at, "o": first[0], "am": 1 if amend else 0, "fail": fail, "st": 1 if stalled else 0, "note": note, "dates": dates}


def collect(db_path):
    """Everything the page needs. Measures with any floor vote, law, rating or committee report get a full
    record; introduced-only measures (most of a Congress) get a compact row the page expands on load."""
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    for sql in ("CREATE INDEX IF NOT EXISTS ix_fv_bill ON floor_votes (bill_key)",
                "CREATE INDEX IF NOT EXISTS ix_sum_bill ON summaries (bill_key)",
                "CREATE INDEX IF NOT EXISTS ix_rat_bill ON ratings (bill_key, is_current)",
                "CREATE INDEX IF NOT EXISTS ix_subj_bill ON subjects (bill_key)",
                "CREATE INDEX IF NOT EXISTS ix_sp_bill ON sponsorships (bill_key)",
                "CREATE INDEX IF NOT EXISTS ix_mv_vote ON member_votes (vote_id)"):
        try:
            con.execute(sql)
        except sqlite3.OperationalError:
            pass
    has = lambda t: con.execute("SELECT 1 FROM sqlite_master WHERE name = ?", (t,)).fetchone() is not None
    members = {}
    for m in con.execute("SELECT * FROM members"):
        members[m["bioguide_id"]] = {"id": m["bioguide_id"], "name": m["full_name"], "party": m["party"], "state": m["state"],
                                     "chamber": m["chamber"], "sponsored": 0, "cosponsored": 0, "_idx": []}
    dicts = {k: [] for k in ("policy", "subject", "status", "action", "lens", "committee")}
    lookup = {k: {} for k in dicts}

    def di(kind, val):
        val = val or ""
        if val not in lookup[kind]:
            lookup[kind][val] = len(dicts[kind])
            dicts[kind].append(val)
        return lookup[kind][val]

    leads, nicks, led = lead_names(con), load_nicknames(), {"popular": 0, "short": 0, "rewritten": 0}
    full, lite, rated, years = [], [], 0, set()
    newest = con.execute("SELECT MAX(latest_action_date) FROM bills").fetchone()[0] or dt.date.today().isoformat()
    cutoff = (dt.date.fromisoformat(newest[:10]) - dt.timedelta(days=STALL_DAYS)).isoformat()
    for b in con.execute("SELECT * FROM bills ORDER BY congress DESC, bill_type, number"):
        key = b["bill_key"]
        if b["introduced_date"]:
            years.add(int(b["introduced_date"][:4]))
        votes = [{"vote_id": v["vote_id"], "chamber": v["chamber"], "date": v["vote_date"], "category": v["category"], "result": v["result"],
                  "method": v["method"], "yeas": v["yeas"], "nays": v["nays"], "roll": v["roll_number"],
                  "url": v["roll_call_url"] or "", "split": v["party_split"] or ""}
                 for v in con.execute("SELECT * FROM floor_votes WHERE bill_key = ? AND key_vote = 1 ORDER BY vote_date", (key,))]
        ratings = {}
        if has("ratings"):
            for r in con.execute("SELECT * FROM ratings WHERE bill_key = ? AND is_current = 1", (key,)):
                ratings[r["axis"]] = {"position": r["position"], "low": r["position_low"], "high": r["position_high"],
                                      "position2": r["position2"], "low2": r["position2_low"], "high2": r["position2_high"],
                                      "magnitude": r["magnitude_label"], "magnitude_note": r["magnitude_note"],
                                      "grade": r["evidence_grade"], "confidence": r["confidence"], "justification": r["justification"],
                                      "sources": jload(r["sources_json"], []), "flags": jload(r["flags_json"], {}),
                                      "plain": jload(r["plain_json"], {}), "rater": r["rater"], "rated_at": r["rated_at"],
                                      "version": r["method_version"]}
        real = {a: r for a, r in ratings.items() if a != "backing"}
        rated += 1 if real else 0
        summ = con.execute("SELECT action_desc, action_date, text_plain FROM summaries WHERE bill_key = ? "
                           "ORDER BY action_date DESC, version_code DESC LIMIT 1", (key,)).fetchone()
        subjects = [s[0] for s in con.execute("SELECT subject FROM subjects WHERE bill_key = ? ORDER BY subject LIMIT 8", (key,))]
        lens = [x.strip() for x in (b["lens_flags"] or "").split(";") if x.strip()]
        own_short, lead_kind, names, was, by = b["short_title"] or "", "", leads.get(key) or {}, "", ""   # the name to lead with, from the record
        if names.get("popular"):
            own_short, lead_kind = names["popular"], "popular"
        elif names.get("amend") and not any(same_name(t, own_short or b["title"]) for _c, t in names["amend"]):
            was = display_title(b["title"] or "", own_short)          # the other chamber replaced the text: lead with what it became
            (by, own_short), lead_kind = names["amend"][0], "rewritten"
        elif names.get("short") and not own_short and FORMAL_TITLE.match(b["title"] or ""):
            own_short, lead_kind = names["short"], "short"
        if lead_kind:
            led[lead_kind] += 1
        is_lite = (not votes and not ratings and not (b["law_number"] or "") and (b["status"] or "") in LITE_STATUSES
                   and (b["outcome"] or "Pending") == "Pending")
        if is_lite:
            lite.append([key, display_title(b["title"] or "", own_short), b["sponsor_bioguide"] or "",
                         b["cosponsors_active"] or 0, b["cosponsors_by_party"] or "", 1 if b["bipartisan"] else 0,
                         di("policy", b["policy_area"]), [di("subject", x) for x in subjects], di("status", b["status"]),
                         b["introduced_date"] or "", b["latest_action_date"] or "", di("action", (b["latest_action"] or "")[:220]),
                         [di("lens", x) for x in lens], (summ["text_plain"] or "") if summ else "",
                         di("committee", b["committees_referred"] or "")])
            continue
        rater = next((r["rater"] for r in real.values() if r["rater"]), "")
        review = (("Automated rating, not yet reviewed" if rater.startswith("model:") else "Preview rating, applied by hand, not yet reviewed")
                  if real else ("Party backing computed from the roll-call record; the other ratings are not applied yet" if ratings else ""))
        full.append({
            "key": key, "id": b["display_id"], "congress": b["congress"], "title": b["title"] or "",
            "short_title": display_title(b["title"] or "", own_short),
            "kind": b["kind"] or "", "source_update": (b["source_update"] or "")[:10],
            "introduced": b["introduced_date"] or "", "origin": b["origin_chamber"] or "",
            "sponsor": ({"id": b["sponsor_bioguide"], "name": members[b["sponsor_bioguide"]]["name"], "party": members[b["sponsor_bioguide"]]["party"],
                         "state": members[b["sponsor_bioguide"]]["state"]} if b["sponsor_bioguide"] in members else None),
            "cosponsors": {"total": b["cosponsors_active"] or 0, "by_party": b["cosponsors_by_party"] or ""},
            "bipartisan": bool(b["bipartisan"]), "policy_area": b["policy_area"] or "", "subjects": subjects,
            "committees": b["committee_path"] or b["committees_referred"] or "", "committee_votes": b["committee_votes"] or "",
            "status": b["status"] or "", "outcome": b["outcome"] or "", "law": b["law_number"] or "", "law_kind": b["law_kind"] or "",
            "latest_action_date": b["latest_action_date"] or "", "latest_action": b["latest_action"] or "", "lens": lens,
            "votes": votes, "summary": (summ["text_plain"] or "")[:900] if summ else "",
            "summary_desc": summ["action_desc"] if summ else "", "summary_date": summ["action_date"] if summ else "",
            "related_enacted": b["related_enacted"] or "", "links": {"pdf": b["latest_text_pdf"] or ""},
            "ratings": ratings or None, "review": review, "journey": journey_for(con, b, cutoff),
            "lead_kind": lead_kind, "was": was, "rewritten_by": by, "nick": nicks.get(key)})

    # position of every measure in the page's list (full records first, then compact rows)
    index = {r["key"]: i for i, r in enumerate(full)}
    index.update({row[0]: len(full) + j for j, row in enumerate(lite)})
    for key, bio, role in con.execute("SELECT bill_key, bioguide_id, role FROM sponsorships"):
        m, i = members.get(bio), index.get(key)
        if m is not None and i is not None:
            m["sponsored" if role == "sponsor" else "cosponsored"] += 1
            m["_idx"].append(i)
    for m in members.values():
        idx = sorted(set(m.pop("_idx")))
        m["bd"] = [idx[0]] + [y - x for x, y in zip(idx, idx[1:])] if idx else []   # delta-encoded list positions

    # member-level roll calls: one position string per vote over a per-chamber member list; party as recorded on
    # the roll call when it differs from today's roster (members who switched parties show as they were then)
    mv, vote_meta = {"H": {"ids": [], "votes": {}}, "S": {"ids": [], "votes": {}}}, []
    if has("member_votes"):
        roster = dict(con.execute("SELECT bioguide_id, party FROM legislators")) if has("legislators") else {}
        per = {}
        for vid, mk, party, pos in con.execute("SELECT vote_id, member_key, party, position FROM member_votes"):
            per.setdefault(vid, []).append((mk, party or "", pos or ""))
        vrows = [fv for fv in con.execute(
            "SELECT f.vote_id, f.bill_key, f.chamber, f.vote_date, f.category, f.result, f.yeas, f.nays, f.roll_number, "
            "f.roll_call_url, f.party_split, b.display_id, b.short_title, b.title FROM floor_votes f JOIN bills b "
            "ON b.bill_key = f.bill_key") if fv["vote_id"] in per]
        ch = lambda fv: "S" if fv["chamber"] == "Senate" else "H"
        for c in mv:
            mv[c]["ids"] = sorted({mk for fv in vrows if ch(fv) == c for mk, _p, _v in per[fv["vote_id"]]})
        where = {c: {k: i for i, k in enumerate(mv[c]["ids"])} for c in mv}
        for fv in vrows:
            c, vid = ch(fv), fv["vote_id"]
            chars, po = ["."] * len(mv[c]["ids"]), {}
            for mk, party, pos in per[vid]:
                i = where[c][mk]
                chars[i] = POSITION_CODE.get(pos, "X")
                p = "I" if party == "ID" else party
                if p in ("D", "R", "I", "L") and roster.get(mk) and roster[mk] != p:
                    po[str(i)] = p
            mv[c]["votes"][vid] = "".join(chars)
            meta = {"vote_id": vid, "bill_key": fv["bill_key"], "chamber": fv["chamber"], "date": fv["vote_date"],
                    "category": fv["category"], "result": fv["result"], "yeas": fv["yeas"], "nays": fv["nays"], "roll": fv["roll_number"],
                    "url": fv["roll_call_url"] or "", "split": fv["party_split"] or "", "bill": fv["display_id"],
                    "title": display_title(fv["title"] or "", fv["short_title"] or "")}
            if po:
                meta["po"] = po
            vote_meta.append(meta)
    vote_meta.sort(key=lambda v: (v["date"] or "", v["roll"] or 0), reverse=True)
    # a bill's vote can link to the map only when that roll call carries member-level positions
    with_members = set(mv["H"]["votes"]) | set(mv["S"]["votes"])
    for b in full:
        for v in b["votes"]:
            if v["vote_id"] in with_members:
                v["map"] = 1
    ids = set(mv["H"]["ids"]) | set(mv["S"]["ids"])
    legislators = legislator_rows(con, sorted(ids))
    photos, photo_bytes = {}, {}
    if has("photos"):
        need = set(legislators) | {m["id"] for m in members.values() if m["bd"]}
        for bid, blob in con.execute("SELECT bioguide_id, webp FROM photos WHERE webp IS NOT NULL"):
            if bid in need:
                photos[bid] = base64.b64encode(blob).decode("ascii")
                photo_bytes[bid] = bytes(blob)
    ys = sorted(years)
    stats = {"measures": len(full) + len(lite), "laws": sum(1 for b in full if b["law"]),
             "votes": sum(len(b["votes"]) for b in full), "rated": rated, "members": len(members),
             "current": sum(1 for b in full if int(b["congress"] or 0) >= 119) + sum(1 for r in lite if r[0].endswith(("-119", "-120", "-121"))),
             "years": f"{ys[0]} to {ys[-1]}" if ys else "", "roll_calls": len(vote_meta), "compact": len(lite),
             "rc_total": con.execute("SELECT COUNT(DISTINCT roll_call_xml) FROM floor_votes WHERE roll_call_xml <> ''").fetchone()[0]}
    topo = os.path.join(os.path.dirname(os.path.abspath(db_path)), "us_states_albers.json")
    if not os.path.exists(topo):
        topo = os.path.join(os.path.dirname(os.path.abspath(__file__)), "us_states_albers.json")
    dist = os.path.join(os.path.dirname(os.path.abspath(db_path)), "us_districts_albers.json")
    if not os.path.exists(dist):
        dist = os.path.join(os.path.dirname(os.path.abspath(__file__)), "us_districts_albers.json")
    districts = json.load(open(dist, encoding="utf-8")) if os.path.exists(dist) else {"states": {}, "q": 50, "vintage": ""}
    welcome = welcome_picks(con)
    by_key = {b["key"]: b for b in full}
    for name in ("live", "laws"):
        for pick in welcome.get(name, []):
            fb = by_key.get(pick["key"]) or {}
            pick["journey"] = fb.get("journey")
            pick["title"] = fb.get("short_title") or pick["title"]           # the Start here lists lead with the same name the bill does
            pick["nick"], pick["was"] = fb.get("nick"), fb.get("was")
    for m in vote_meta:                                                     # and so does every roll call on the map
        fb = by_key.get(m["bill_key"])
        if fb:
            m["title"] = (fb["nick"]["name"] if (fb.get("nick") or {}).get("lead") else fb["short_title"]) or m["title"]
    print(f"    Lead names from the record: {led['popular']:,} popular title(s), {led['rewritten']:,} rewritten by the other chamber, "
          f"{led['short']:,} earlier short title(s); "
          f"{len(nicks):,} approved nickname(s) from nicknames.json")
    profiles = member_profiles(con, legislators, vote_meta)
    for bio, prof in profiles.items():                         # the party-line table on the Members page reads these five counts
        v = prof.get("votes")
        if v and bio in legislators:
            legislators[bio]["vs"] = [v["split_n"], v["split_with"], v["breaks_n"], v["missed"], v["eligible"]]
    closest = closest_votes(con, vote_meta)
    return {"generated": dt.datetime.now().strftime("%B %d, %Y"), "bills": full, "lite": {"rows": lite, "dict": dicts},
            "members": sorted(members.values(), key=lambda m: m["name"] or ""), "stats": stats,
            "rubric": next((r["version"] for b in full for a, r in (b["ratings"] or {}).items() if a != "backing"), "v1.1"),
            "legislators": legislators, "photos": photos, "photo_bytes": photo_bytes, "mv": mv, "vote_meta": vote_meta,
            "states": state_paths(topo) if os.path.exists(topo) else {}, "districts": districts,
            "welcome": welcome, "stall_cutoff": cutoff, "profiles": profiles, "closest": closest,
            "changelog": read_changelog(os.path.join(os.path.dirname(os.path.abspath(__file__)), "CHANGELOG.md"))}


def vote_needs(category, action_text):
    """What a roll call needed in order to carry, read from the record's own words: a majority, two-thirds
    (suspension of the rules, a veto override), or the Senate's sixty."""
    t = (action_text or "").lower()
    if category == "Veto override" or "2/3" in t or "two-thirds" in t:
        return "two_thirds"
    if category == "Cloture" or "60 votes" in t or "three-fifths" in t or "3/5" in t:
        return "sixty"
    return "majority"


def closest_votes(con, vote_meta, n=12):
    """The recorded votes that came down to the fewest votes: how far the yes count landed from what it needed.
    A vote whose recorded result does not fit the threshold read from its text is left out rather than guessed at."""
    meta = {v["vote_id"]: v for v in vote_meta}
    if not meta:
        return []
    carried = {"Passed", "Agreed to", "Invoked", "Sustained"}
    weight = {"Passage": 0, "Resolve differences": 0, "Veto override": 0}
    out = []
    for vid, category, result, yeas, nays, text in con.execute(
            "SELECT vote_id, category, result, yeas, nays, action_text FROM floor_votes WHERE yeas IS NOT NULL AND nays IS NOT NULL"):
        m = meta.get(vid)
        if not m:
            continue
        needs = vote_needs(category, text)
        if needs == "majority":
            need, margin, won = None, abs(yeas - nays), yeas > nays
            if yeas == nays:
                won = result in carried                          # a Senate tie is settled by the Vice President
        elif needs == "sixty":
            need = 60
            margin, won = abs(yeas - need), yeas >= need
        else:
            need = -(-2 * (yeas + nays) // 3)                   # two-thirds of those voting, rounded up
            margin, won = abs(yeas - need), yeas >= need
        if won != (result in carried):
            continue
        out.append({"vote_id": vid, "bill_key": m["bill_key"], "bill": m["bill"], "title": trim_text(m["title"], 90), "chamber": m["chamber"],
                    "category": category, "date": m["date"], "yeas": yeas, "nays": nays, "result": result, "needs": needs,
                    "need": need, "margin": margin, "won": won, "_w": weight.get(category, 1)})
    out.sort(key=lambda v: (v["margin"], v["_w"], -int((v["date"] or "0000-00-00").replace("-", ""))))
    for v in out:
        v.pop("_w")
    return out[:n]


def welcome_picks(con, n=5):
    """Bills to feature on the welcome screen, and the headline counts beside them.

    Ordering rule, stated plainly on the page itself so a reader can check it:
    a bill scores 3 if the Congressional Budget Office costed it, 2 if a
    committee filed a written report, plus 1 for every recorded floor vote it
    drew. Ties break on cosponsors. Every input is a fact from the record; the
    weighting is ours, which is why the page labels these lists as analysis.

    Costing is what separates consequence from popularity here. Commemorative
    coin and gold-medal bills collect hundreds of cosponsors precisely because
    nobody objects to them, and CBO never scores them, so they settle to the
    bottom instead of crowding out appropriations and authorisations.
    """
    score = ("((SELECT COUNT(*) FROM cbo_estimates e WHERE e.bill_key=b.bill_key)>0)*3"
             " + (SELECT COUNT(*) FROM floor_votes f WHERE f.bill_key=b.bill_key)"
             " + ((SELECT COUNT(*) FROM committee_reports r WHERE r.bill_key=b.bill_key)>0)*2")
    cols = ("b.bill_key, b.display_id, COALESCE(NULLIF(b.short_title,''), b.title) AS t,"
            " b.status, b.latest_action_date, b.cosponsors_active, b.bipartisan, b.law_number")

    def rows(where, extra=""):
        q = (f"SELECT {cols}, {score} AS sc FROM bills b WHERE {where}"
             f" {extra} ORDER BY sc DESC, b.cosponsors_active DESC LIMIT {n}")
        out = []
        for r in con.execute(q):
            out.append({"key": r[0], "id": r[1], "title": r[2] or "", "status": r[3] or "",
                        "date": r[4] or "", "cos": r[5] or 0, "bi": bool(r[6]),
                        "law": r[7] or "", "score": r[8]})
        return out

    # "Moving now" means moving now: without the 90-day window the list fills up
    # with bills that cleared both chambers months ago and are only waiting on a
    # signature, which reads as stale to anyone checking what Congress is doing
    # this week. The window is measured from the newest action in the data, not
    # from today, so the list stays sensible if a build runs against an old copy.
    latest = con.execute("SELECT MAX(latest_action_date) FROM bills").fetchone()[0] or ""
    recent = f"AND b.latest_action_date >= date('{latest}','-90 day')" if latest else ""
    live = rows("b.status NOT LIKE 'Became law%' AND b.status NOT LIKE 'Failed%' "
                "AND b.status NOT LIKE 'Vetoed%'", recent)
    laws = rows("b.status LIKE 'Became law%'")

    def count(where):
        return con.execute(f"SELECT COUNT(*) FROM bills WHERE {where}").fetchone()[0]

    counts = {
        "introduced": count("1=1"),
        "law": count("status LIKE 'Became law%'"),
        "failed": count("status LIKE 'Failed%' OR status LIKE 'Vetoed%'"),
        "half": count("status LIKE 'Passed House only' OR status LIKE 'Passed Senate only'"),
        "committee": count("status LIKE 'In committee'"),
        "awaiting": count("status LIKE 'Presented to President' OR status LIKE 'Passed both chambers%'"),
    }
    return {"live": live, "laws": laws, "counts": counts}


def read_changelog(path, limit=6):
    """Parse CHANGELOG.md into [{date, title, items}], newest first.

    Kept deliberately dumb: headings are '## v4.0.001 - YYYY-MM-DD - title' (the
    version is optional; older entries have only a date) and bullets are '- text'.
    Anything else in the file is ignored, so the prose at the top of the changelog
    can explain the format without ending up on the page.
    """
    if not os.path.exists(path):
        return []
    entries, cur = [], None
    for line in open(path, encoding="utf-8"):
        line = line.rstrip()
        m = re.match(r"^##\s+(?:v?(\d+\.\d+\.\d+)\s*[—\-]+\s*)?(\d{4}-\d{2}-\d{2})\s*[—\-]+\s*(.+?)\s*$", line)
        if m:
            cur = {"version": m.group(1) or "", "date": m.group(2), "title": m.group(3), "items": []}
            entries.append(cur)
        elif cur is not None and line.startswith("- "):
            cur["items"].append(line[2:].strip())
        elif cur is not None and line.startswith("  ") and cur["items"] and line.strip():
            cur["items"][-1] += " " + line.strip()
    return entries[:limit]


def trim_lite(data, n_chars, n_subjects):
    """Copy of the payload with compact-row summaries cut to n_chars (word boundary) and n_subjects subject terms."""
    out = dict(data)
    rows = []
    for r in data["lite"]["rows"]:
        r = list(r)
        text = r[13]
        r[13] = "" if n_chars <= 0 else (text if len(text) <= n_chars else text[:n_chars].rsplit(" ", 1)[0] + "\u2026")
        r[7] = r[7][:n_subjects]
        rows.append(r)
    out["lite"] = {"rows": rows, "dict": data["lite"]["dict"]}
    return out


# --- the split site ---------------------------------------------------------
# The page is a small shell (markup, styles, code and the numbers the welcome
# screen shows). Everything else arrives when a page needs it: the bill list
# and compact rows when Bills opens, one small file per bill when its details
# open, the roll calls when the map opens, portraits as images. The one-file
# archive inlines the same bundles under the same names, so the page code has
# a single path.

LIST_FIELDS = ("key", "id", "congress", "title", "short_title", "kind", "introduced", "origin", "sponsor", "cosponsors",
               "bipartisan", "policy_area", "subjects", "status", "outcome", "law", "law_kind", "latest_action_date",
               "latest_action", "lens", "review", "links", "lead_kind", "was", "rewritten_by", "nick")


def trim_text(text, n):
    text = text or ""
    return text if len(text) <= n else text[:n].rsplit(" ", 1)[0] + "\u2026"


def ratings_summary(ratings):
    """What a card needs from the ratings: positions, grades and the one-sentence plain reading. The
    justifications and sources stay in the bill's own file."""
    if not ratings:
        return None
    out = {}
    for axis, r in ratings.items():
        keep = {k: r.get(k) for k in ("position", "low", "high", "position2", "low2", "high2", "grade", "version", "rated_at")
                if r.get(k) is not None}
        fl = r.get("flags") or {}
        flags = {k: fl[k] for k in ("label", "business_tag") if k in fl}
        if flags:
            keep["flags"] = flags
        pl = r.get("plain") or {}
        if axis == "plain_language" and pl.get("one_sentence"):
            keep["plain"] = {"one_sentence": pl["one_sentence"]}
        out[axis] = keep
    return out


def list_record(b, n_chars=220):
    """The card view of a full record. `trim` tells the page the rest is in data/bill/<key>.json."""
    r = {k: b[k] for k in LIST_FIELDS if k in b}
    r["summary"] = trim_text(b.get("summary", ""), n_chars)
    r["latest_action"] = trim_text(b.get("latest_action", ""), 110)   # the card shows 90 characters of it
    r["nvotes"] = len(b.get("votes") or [])
    r["ratings"] = ratings_summary(b.get("ratings"))
    if b.get("journey"):                                  # the dates under each stop stay in the bill's own file
        r["journey"] = {k: v for k, v in b["journey"].items() if k != "dates"}
    r["trim"] = 1
    return r


def detail_record(b):
    # links are derived on the page from the list record; leaving them out keeps the merge from undoing that
    return {k: v for k, v in b.items() if k != "links"}


def bundles(data):
    """The data files of the split site, by name. The one-file archive inlines the same set."""
    return {"members": {"members": data["members"], "legislators": data["legislators"]},
            "lite": data["lite"],
            "votes": {"vote_meta": data["vote_meta"], "mv": data["mv"], "states": data["states"]},
            "districts": data["districts"]}


def boot_for(data, version, base_url=""):
    """What the shell carries inline: the welcome screen's numbers and picks, the changelog, and the
    rated bills the hero panel rotates through."""
    has_pos = lambda r: bool(r) and r.get("position") is not None
    natkey = lambda t: [int(x) if x.isdigit() else x for x in re.split(r"(\d+)", t)]
    feat = [b for b in data["bills"] if b.get("ratings")
            and (has_pos(b["ratings"].get("income")) or has_pos(b["ratings"].get("households_business")))]
    feat.sort(key=lambda b: (-int(b["congress"] or 0), 0 if ((b["ratings"].get("income") or {}).get("grade") == "A") else 1,
                             natkey(b["key"])))
    # the newest roll calls, for the moving line under the hero (vote_meta is already newest first)
    ticker = [{"v": m["vote_id"], "b": m["bill"], "t": trim_text(m["title"], 64), "c": m["chamber"], "d": m["date"],
               "y": m["yeas"], "n": m["nays"], "r": m["result"]} for m in data["vote_meta"][:14]]
    return {"version": version, "generated": data["generated"], "stats": data["stats"], "rubric": data["rubric"],
            "ticker": ticker, "closest": data.get("closest") or [],
            "welcome": data["welcome"], "changelog": data["changelog"], "featured": [list_record(b) for b in feat],
            "photo_ids": sorted(data["photos"]), "base": base_url.rstrip("/"),
            "state_names": {st: s["name"] for st, s in data["states"].items()},
            "stall_cutoff": data.get("stall_cutoff", ""), "inline": None}


def html_attr(text):
    return str(text).replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")


def render_page(boot, data, version, foot):
    payload = json.dumps(boot, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    st, wc = data["stats"], data["welcome"]["counts"]
    demo = st["current"] < st["measures"]
    gc = boot.get("analytics") or ""
    tag = ('<script data-goatcounter="%s" data-goatcounter-settings=\'{"no_onload": true, "allow_frame": false}\' '
           'async src="https://gc.zgo.at/count.js" onload="if(window.__gcflush)__gcflush()"></script>' % html_attr(gc)) if gc else ""
    if gc:
        foot += (" Visits are counted by GoatCounter, which sets no cookies and keeps no personal data; "
                 "share taps are counted the same way.")
    return (TEMPLATE.replace("__BOOT__", payload).replace("__FOOTNOTE__", foot).replace("__VERSION__", version)
            .replace("__BASE__", boot.get("base") or "").replace("__ANALYTICS__", tag)
            .replace("__SETLABEL__", "measures in this demo set" if demo else "measures this Congress")
            .replace("__MEASURES__", str(st["measures"]))
            .replace("__LAWS__", str(st["laws"])).replace("__VOTES__", str(st["votes"])).replace("__MEMBERS__", str(st["members"]))
            .replace("__CURRENT__", str(st["current"])).replace("__RATED__", str(st["rated"])).replace("__YEARS__", st["years"])
            .replace("__CBILL__", str(wc["committee"])).replace("__CHALF__", str(wc["half"]))
            .replace("__CWAIT__", str(wc["awaiting"])).replace("__CFAIL__", str(wc["failed"]))
            .replace("__GENERATED__", data["generated"]).replace("__RUBRIC__", data["rubric"]))


def write_split(folder, html, data, photo_bytes):
    """index.html plus data/ and photos/ under `folder`. The two subfolders are rebuilt from scratch."""
    import shutil
    folder = os.path.abspath(folder)
    for sub in ("data", "photos"):
        shutil.rmtree(os.path.join(folder, sub), ignore_errors=True)
    os.makedirs(os.path.join(folder, "data", "bill"), exist_ok=True)
    os.makedirs(os.path.join(folder, "photos"), exist_ok=True)
    dump = lambda obj: json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    sizes = {}

    def put(rel, text):
        with open(os.path.join(folder, rel), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        sizes[rel] = len(text.encode("utf-8"))

    put("index.html", html)
    version = data.get("_version") or "0"
    put("manifest.webmanifest", json.dumps({
        "name": "The Civic Archive", "short_name": "Civic Archive",
        "description": "Every bill in Congress, in plain words. Every recorded vote, member by member.",
        "start_url": "./", "scope": "./", "display": "standalone", "background_color": "#0C0E12", "theme_color": "#0C0E12",
        "icons": [{"src": "icon-192.png", "sizes": "192x192", "type": "image/png"},
                  {"src": "icon-512.png", "sizes": "512x512", "type": "image/png"},
                  {"src": "icon-512-maskable.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"}]}, indent=1))
    put("sw.js", SERVICE_WORKER.replace("__VERSION__", version))
    import share_cards
    for name, size, maskable in (("icon-192.png", 192, False), ("icon-512.png", 512, False), ("icon-512-maskable.png", 512, True)):
        share_cards.draw_icon(size, maskable).save(os.path.join(folder, name), optimize=True)
    put("data/bills-list.json", dump({"bills": [list_record(b) for b in data["bills"]]}))
    for name, obj in bundles(data).items():
        put(f"data/{name}.json", dump(obj))
    n_detail = detail_bytes = 0
    for b in data["bills"]:
        text = dump(detail_record(b))
        with open(os.path.join(folder, "data", "bill", b["key"] + ".json"), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        n_detail += 1
        detail_bytes += len(text.encode("utf-8"))
    os.makedirs(os.path.join(folder, "data", "member"), exist_ok=True)       # one small file per member, read when their card opens
    for bio, prof in (data.get("_profiles") or {}).items():
        with open(os.path.join(folder, "data", "member", bio + ".json"), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(dump(prof))
    for bid, blob in photo_bytes.items():
        with open(os.path.join(folder, "photos", bid + ".webp"), "wb") as fh:
            fh.write(blob)
    return sizes, n_detail, detail_bytes, sum(len(v) for v in photo_bytes.values())


# The service worker keeps the site usable offline without ever serving a stale
# page: the shell is fetched from the network first and only falls back to the
# copy it kept; data, portraits and previews carry the version in their address,
# so they are safe to keep and are dropped wholesale when the version changes.
SERVICE_WORKER = r"""const V = "civic-__VERSION__";
const SHELL = ["./", "./index.html", "./manifest.webmanifest"];
self.addEventListener("install", e => { e.waitUntil(caches.open(V).then(c => c.addAll(SHELL)).then(() => self.skipWaiting())); });
self.addEventListener("activate", e => { e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== V).map(k => caches.delete(k)))).then(() => self.clients.claim())); });
self.addEventListener("fetch", e => {
  const r = e.request; if (r.method !== "GET") return;
  const u = new URL(r.url); if (u.origin !== location.origin) return;
  if (/\/(data|photos|og)\//.test(u.pathname)) {
    e.respondWith(caches.open(V).then(c => c.match(r).then(hit => hit || fetch(r).then(res => { if (res.ok) c.put(r, res.clone()); return res; }))));
    return;
  }
  if (r.mode === "navigate" || /\/index\.html$/.test(u.pathname)) {
    e.respondWith(fetch(r).then(res => { if (res.ok) caches.open(V).then(c => c.put("./index.html", res.clone())); return res; })
      .catch(() => caches.match("./index.html")));
  }
});
"""

TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>The Civic Archive: every bill in Congress, in plain words</title>
<meta name="description" content="Every bill in Congress with plain-language summaries, transparent ratings, and a state-by-state map of every recorded vote.">
<meta name="version" content="__VERSION__">
<link rel="canonical" href="__BASE__/">
<meta property="og:type" content="website">
<meta property="og:site_name" content="The Civic Archive">
<meta property="og:title" content="The Civic Archive: every bill in Congress, in plain words">
<meta property="og:description" content="Every bill in Congress with plain-language summaries, transparent ratings, and a state-by-state map of every recorded vote.">
<meta property="og:url" content="__BASE__/">
<meta property="og:image" content="__BASE__/og/site.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="The Civic Archive: every bill in Congress, in plain words">
<meta name="twitter:description" content="Every bill in Congress with plain-language summaries, transparent ratings, and a state-by-state map of every recorded vote.">
<meta name="twitter:image" content="__BASE__/og/site.png">
<link rel="manifest" href="manifest.webmanifest">
<link rel="icon" href="icon-192.png" type="image/png">
<link rel="apple-touch-icon" href="icon-192.png">
__ANALYTICS__
<meta name="theme-color" content="#0C0E12">
<script>try{document.documentElement.dataset.theme=localStorage.getItem("theme")||"dark"}catch(e){document.documentElement.dataset.theme="dark"}</script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Instrument+Sans:ital,wght@0,400..700;1,400..700&family=Instrument+Serif:ital@0;1&display=swap" rel="stylesheet">
<style>
:root{
  --bg:#F5F5F2; --surface:#FFFFFF; --ink:#15171B; --muted:#5C6169; --line:#E4E5E1; --line-strong:#C3C5BF; --hair:rgba(21,23,27,.08);
  --accent:#0F7A6A; --accent-ink:#0A5A4E; --accent-soft:#DDF0EB; --accent-line:#8FCDC0;
  --cobalt:#2E5BE6; --cobalt-ink:#1F42B0; --cobalt-soft:#E3EAFF;
  --teal:#0F7A6A; --teal-ink:#0A5A4E; --teal-soft:#DDF0EB;
  --amber:#D19A1F; --amber-ink:#7A560A; --amber-soft:#F9EFD4;
  --plum:#7A52C7; --plum-soft:#EDE6FB;
  --dem:#2E5BE6; --rep:#D8453A; --bad-soft:#FBE7E5; --bad-ink:#8E2A22;
  --shadow-1:0 1px 2px rgba(21,23,27,.04);
  --shadow-2:0 1px 2px rgba(21,23,27,.05),0 14px 36px -18px rgba(21,23,27,.2);
  --shadow-3:0 2px 4px rgba(21,23,27,.05),0 28px 72px -28px rgba(21,23,27,.3);
  --r-sm:8px; --r-md:12px; --r-lg:16px; --r-xl:24px;
  --serif:"Instrument Serif",Georgia,"Times New Roman",serif;
  --sans:"Instrument Sans",-apple-system,"Segoe UI",Helvetica,Arial,sans-serif;
  --ease:cubic-bezier(.2,.8,.2,1);
  color-scheme:light;
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    --bg:#0F1114; --surface:#171A1F; --ink:#ECEDE9; --muted:#9BA1A9; --line:#272B32; --line-strong:#3D424B; --hair:rgba(236,237,233,.09);
    --accent:#4CC5B0; --accent-ink:#9FE3D6; --accent-soft:#12302B; --accent-line:#2B6C61;
    --cobalt:#7E9BFF; --cobalt-ink:#B9C8FF; --cobalt-soft:#1E2A52;
    --teal:#4CC5B0; --teal-ink:#9FE3D6; --teal-soft:#12302B;
    --amber:#E8B44A; --amber-ink:#F5D48A; --amber-soft:#3A2B0D;
    --plum:#B49BF2; --plum-soft:#2A2247;
    --dem:#7E9BFF; --rep:#FF7B72; --bad-soft:#44201D; --bad-ink:#FFB3AC;
    --shadow-1:none; --shadow-2:0 0 0 1px rgba(255,255,255,.03); --shadow-3:0 28px 72px -28px rgba(0,0,0,.7);
    color-scheme:dark;
  }
}
:root[data-theme="dark"]{
  --bg:#0F1114; --surface:#171A1F; --ink:#ECEDE9; --muted:#9BA1A9; --line:#272B32; --line-strong:#3D424B; --hair:rgba(236,237,233,.09);
  --accent:#4CC5B0; --accent-ink:#9FE3D6; --accent-soft:#12302B; --accent-line:#2B6C61;
  --cobalt:#7E9BFF; --cobalt-ink:#B9C8FF; --cobalt-soft:#1E2A52;
  --teal:#4CC5B0; --teal-ink:#9FE3D6; --teal-soft:#12302B;
  --amber:#E8B44A; --amber-ink:#F5D48A; --amber-soft:#3A2B0D;
  --plum:#B49BF2; --plum-soft:#2A2247;
  --dem:#7E9BFF; --rep:#FF7B72; --bad-soft:#44201D; --bad-ink:#FFB3AC;
  --shadow-1:none; --shadow-2:0 0 0 1px rgba(255,255,255,.03); --shadow-3:0 28px 72px -28px rgba(0,0,0,.7);
  color-scheme:dark;
}

*{box-sizing:border-box}
html{scroll-behavior:smooth;-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--sans);font-size:16px;line-height:1.55;-webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility;font-variant-numeric:tabular-nums}
body.noscroll{overflow:hidden}
img,svg{max-width:100%}
a{color:var(--accent-ink);text-decoration-thickness:1px;text-underline-offset:2px}
button{font:inherit;color:inherit;background:none;border:0;cursor:pointer;padding:0}
kbd{font:inherit;font-size:11px;font-weight:600;padding:2px 6px;border-radius:6px;border:1px solid var(--line);background:var(--bg);color:var(--muted);line-height:1.2}
:focus-visible{outline:2px solid var(--accent);outline-offset:3px;border-radius:8px}
::selection{background:var(--accent-soft)}
.wrap{max-width:1180px;margin:0 auto;padding:0 20px}
@media (min-width:900px){.wrap{padding:0 32px}}
h1,h2{font-family:var(--serif);font-weight:400;letter-spacing:-.012em;margin:0}
h2{font-size:clamp(34px,4.4vw,50px);line-height:1.02}
h3{font-size:20px;font-weight:600;letter-spacing:-.01em;line-height:1.2;margin:0}
h4{font-size:15px;font-weight:600;margin:0 0 8px}
p{margin:0 0 12px}
.muted{color:var(--muted)}
.sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
.skip{position:absolute;left:-999px;top:10px;background:var(--ink);color:var(--bg);padding:8px 12px;border-radius:8px;z-index:100;text-decoration:none}
.skip:focus{left:12px}

/* top bar */
.top{position:sticky;top:0;z-index:30;background:color-mix(in srgb,var(--bg) 80%,transparent);backdrop-filter:saturate(1.5) blur(16px);-webkit-backdrop-filter:saturate(1.5) blur(16px);border-bottom:1px solid var(--hair)}
.top .wrap{display:flex;align-items:center;gap:8px;height:62px}
.brand{display:inline-flex;align-items:center;gap:10px;text-decoration:none;color:var(--ink);font-weight:600;font-size:17px;letter-spacing:-.01em}
.brand .mark{width:28px;height:28px;stroke:currentColor;fill:none;stroke-width:1.75;stroke-linecap:round;stroke-linejoin:round;flex:none}
.top .brand .mark path{stroke-dasharray:90;stroke-dashoffset:90;animation:draw 1.2s var(--ease) forwards}
.top .brand .mark path:nth-child(2){animation-delay:.12s}.top .brand .mark path:nth-child(3){animation-delay:.22s}.top .brand .mark path:nth-child(4){animation-delay:.32s}.top .brand .mark path:nth-child(5){animation-delay:.42s}
@keyframes draw{to{stroke-dashoffset:0}}
.top .wrap{transition:height .3s var(--ease)}
.top.scrolled .wrap{height:54px}
.top.scrolled{box-shadow:0 8px 24px -18px rgba(0,0,0,.3)}
.nav{margin:0 auto;display:flex;gap:2px}
.nav a{text-decoration:none;color:var(--muted);padding:8px 12px;border-radius:999px;font-size:14.5px;font-weight:500;transition:color .15s,background .15s}
.nav a:hover{color:var(--ink);background:var(--hair)}
.tools{margin-left:auto;display:flex;gap:8px;align-items:center}
.kbtn{display:inline-flex;align-items:center;gap:8px;height:38px;padding:0 10px 0 12px;border-radius:999px;border:1px solid var(--line);background:var(--surface);color:var(--muted);font-size:14px;transition:border-color .15s,color .15s}
.kbtn:hover{border-color:var(--line-strong);color:var(--ink)}
.kbtn svg{width:16px;height:16px;stroke:currentColor;fill:none;stroke-width:2;stroke-linecap:round}
.iconbtn{width:38px;height:38px;border-radius:999px;display:grid;place-items:center;border:1px solid var(--line);background:var(--surface);color:var(--ink);transition:border-color .15s;flex:none}
.iconbtn:hover{border-color:var(--line-strong)}
.iconbtn svg{width:18px;height:18px;stroke:currentColor;fill:none;stroke-width:1.9;stroke-linecap:round;stroke-linejoin:round}
#theme .sun{display:none}
:root[data-theme="dark"] #theme .sun{display:block}:root[data-theme="dark"] #theme .moon{display:none}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]) #theme .sun{display:block}:root:not([data-theme="light"]) #theme .moon{display:none}}
.top.over-dark{--bg:#0C0E12;--surface:#14171C;--ink:#ECEDE9;--muted:#9BA1A9;--line:#262A31;--line-strong:#3A3F48;--hair:rgba(236,237,233,.09);color:var(--ink);border-bottom-color:var(--hair)}
.top{transition:background .25s,color .25s}
@media (max-width:1000px){.kbtn span,.kbtn kbd{display:none}.kbtn{width:38px;padding:0;justify-content:center}.nav a{padding:8px 9px;font-size:14px}}
@media (max-width:760px){.nav{display:none}}

/* hero */
.hero{padding:56px 0 44px;position:relative}
.hero .wrap{display:grid;gap:36px;grid-template-columns:1fr}
@media (min-width:960px){.hero{padding:72px 0 64px}.hero .wrap{grid-template-columns:minmax(210px,250px) minmax(0,1fr);align-items:start;gap:44px}}
.hero .spotlight{margin-top:34px}
.hero h1{font-size:clamp(44px,16.2vw,118px);line-height:.94;max-width:none}
@media (min-width:960px){.hero h1{font-size:clamp(96px,11.2vw,148px)}}
.hero h1 .h1a,.hero h1 .h1b{display:block;white-space:nowrap}
.hero h1 .h1b{font-style:italic;color:var(--accent)}
.hero h1 .h1b .w{padding-right:.12em;margin-right:-.12em}
.hero .lede{font-size:clamp(17px,1.6vw,20px);line-height:1.5;color:var(--muted);max-width:46ch;margin:22px 0 28px}
.cta{display:flex;gap:10px;flex-wrap:wrap}
.btn{display:inline-flex;align-items:center;gap:8px;height:46px;padding:0 20px;border-radius:999px;border:1px solid var(--line-strong);background:var(--surface);color:var(--ink);font-weight:600;font-size:15px;text-decoration:none;transition:transform .15s var(--ease),border-color .15s,background .15s,color .15s}
.btn:hover{border-color:var(--ink)}
.btn:active{transform:scale(.98)}
.btn.primary{background:var(--ink);color:var(--bg);border-color:var(--ink)}
.btn.primary:hover{background:var(--accent-ink);border-color:var(--accent-ink)}
.btn svg{width:16px;height:16px;stroke:currentColor;fill:none;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
.stats{display:grid;grid-template-columns:repeat(2,1fr);gap:0 20px;margin:36px 0 0;padding:0;border-top:1px solid var(--line)}
@media (min-width:600px){.stats{display:flex;gap:0 28px;flex-wrap:wrap}}
.stats div{display:flex;flex-direction:column;padding:18px 0 0;min-width:110px}
.stats dt{font-size:13px;color:var(--muted);margin:2px 0 0;order:2}
.stats dd{margin:0;font-family:var(--serif);font-size:36px;line-height:1;letter-spacing:-.01em}
.hero .lede{animation:rise .9s .5s var(--ease) both}.hero .cta{animation:rise .9s .65s var(--ease) both}.hero .stats{animation:rise .9s .8s var(--ease) both}
.hero .lede+.lede{margin-top:-14px}
.nosell{margin:22px 0 0;font-size:13.5px;color:var(--muted);letter-spacing:.01em;animation:rise .9s .8s var(--ease) both}

/* --- hero scene: the drawn Capitol sits behind the words ----------------- */
.hero{isolation:isolate}
.hero>.wrap{position:relative;z-index:2}
.hero canvas{z-index:0}
.hero::after{content:"";position:absolute;inset:0;z-index:1;pointer-events:none;background:linear-gradient(to bottom,var(--bg) 0%,rgba(245,245,242,.86) 26%,rgba(245,245,242,.70) 52%,rgba(245,245,242,.82) 100%)}
:root[data-theme="dark"] .hero::after{background:linear-gradient(to bottom,var(--bg) 0%,rgba(15,17,20,.86) 26%,rgba(15,17,20,.70) 52%,rgba(15,17,20,.84) 100%)}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]) .hero::after{background:linear-gradient(to bottom,var(--bg) 0%,rgba(15,17,20,.86) 26%,rgba(15,17,20,.70) 52%,rgba(15,17,20,.84) 100%)}}
.wx{position:absolute;right:16px;bottom:12px;z-index:3;margin:0;display:flex;align-items:center;gap:7px;font-size:11.5px;letter-spacing:.02em;color:var(--muted);background:var(--surface);border:1px solid var(--line);border-radius:999px;padding:5px 12px;box-shadow:var(--shadow-1)}
.wx[hidden]{display:none!important}
.wxdot{width:6px;height:6px;border-radius:50%;background:var(--accent);box-shadow:0 0 0 3px var(--accent-soft);flex:none}
.wxbtn{border:0;background:none;padding:0;margin-left:2px;font:inherit;color:var(--accent-ink);text-decoration:underline;text-underline-offset:2px;cursor:pointer}
.wxbtn:hover{color:var(--ink)}

/* --- wordmark: the initials carry the name ------------------------------ */
.wm{font-family:var(--serif);font-size:1.28em;line-height:1;letter-spacing:-.005em;font-weight:400;color:var(--muted);white-space:nowrap}
.wm b{font-weight:400;font-size:1.22em;color:var(--ink);letter-spacing:-.02em}
.brand:hover .wm b{color:var(--accent-ink)}
.wm b{transition:color .15s}

/* --- provenance tags: fact / analysis / opinion ------------------------- */
.tag{display:inline-flex;align-items:center;height:20px;padding:0 8px;border-radius:999px;font-size:11px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;white-space:nowrap;flex:none}
.tag.fact{background:var(--teal-soft);color:var(--teal-ink);border:1px solid var(--accent-line)}
.tag.analysis{background:var(--cobalt-soft);color:var(--cobalt-ink);border:1px solid rgba(46,91,230,.35)}
.tag.opinion{background:var(--amber-soft);color:var(--amber-ink);border:1px solid rgba(209,154,31,.45)}
.srcnote{display:flex;gap:10px;align-items:flex-start;margin:22px 0 0;font-size:13px;line-height:1.55;color:var(--muted);max-width:76ch}
.srcnote .tag{margin-top:1px}

/* --- KPI rail: the standing of this Congress, one glance, left column ---- */
.kpirail{order:2;border-top:1px solid var(--line);padding-top:20px;animation:rise .9s .35s var(--ease) both}
@media (min-width:960px){.kpirail{order:0;border-top:0;border-right:1px solid var(--line);padding:4px 30px 4px 0}}
.kpihead{display:flex;align-items:center;gap:8px;font-size:12px;color:var(--muted);margin-bottom:16px;flex-wrap:wrap}
.kpis{margin:0;padding:0;display:grid;grid-template-columns:repeat(2,1fr);gap:16px 18px}
@media (min-width:560px){.kpis{grid-template-columns:repeat(3,1fr)}}
@media (min-width:960px){.kpis{grid-template-columns:1fr;gap:15px}}
.kpis div{display:flex;flex-direction:column;position:relative;padding-left:0}
@media (min-width:960px){.kpis div{padding-left:13px}
  .kpis div::before{content:"";position:absolute;left:0;top:4px;bottom:4px;width:2px;border-radius:2px;background:var(--line-strong)}
  .kpis .good::before{background:var(--accent)}
  .kpis .bad::before{background:var(--rep)}}
.kpis dd{margin:0;font-family:var(--serif);font-size:clamp(26px,2.6vw,34px);line-height:1;letter-spacing:-.015em;order:1}
.kpis dt{font-size:12.5px;color:var(--muted);margin:3px 0 0;order:2;line-height:1.35}
.kpis .good dd{color:var(--accent-ink)}
.kpis .bad dd{color:var(--bad-ink)}
.kpifoot{margin:18px 0 0;font-size:11.5px;line-height:1.5;color:var(--muted)}

/* --- start here: the two pick lists ------------------------------------- */
.picks{padding:12px 0 52px}
.pickcols{display:grid;gap:28px;grid-template-columns:1fr;margin-top:26px}
@media (min-width:860px){.pickcols{grid-template-columns:1fr 1fr;gap:40px}}
.pickhead h3{margin:0;font-size:15px;font-weight:700;letter-spacing:.01em;display:flex;align-items:center;gap:9px}
.pickhead p{margin:4px 0 0;font-size:13px;color:var(--muted)}
.dot{width:9px;height:9px;border-radius:50%;flex:none}
.dot.live{background:var(--cobalt);box-shadow:0 0 0 4px var(--cobalt-soft)}
.dot.done{background:var(--accent);box-shadow:0 0 0 4px var(--accent-soft)}
.picklist{list-style:none;margin:16px 0 0;padding:0;counter-reset:pick}
.picklist li{counter-increment:pick}
.pickitem{display:grid;grid-template-columns:auto 1fr;gap:14px;align-items:start;width:100%;text-align:left;padding:14px 14px 14px 12px;border:1px solid var(--line);border-radius:var(--r-md);background:var(--surface);cursor:pointer;margin-bottom:8px;transition:border-color .15s,transform .15s var(--ease),box-shadow .15s;font:inherit;color:inherit}
.pickitem:hover{border-color:var(--line-strong);transform:translateY(-1px);box-shadow:var(--shadow-2)}
.pickitem:active{transform:none}
.pickitem .n{font-family:var(--serif);font-size:22px;line-height:1;color:var(--muted);min-width:22px;padding-top:2px}
.pickitem .n::before{content:counter(pick)}
.pickitem .t{font-weight:600;font-size:15px;line-height:1.35;margin:0 0 6px;text-wrap:pretty}
.pickitem .meta{display:flex;flex-wrap:wrap;gap:6px;align-items:center;font-size:12px;color:var(--muted)}
.pickitem .pill{display:inline-flex;align-items:center;height:20px;padding:0 8px;border-radius:999px;border:1px solid var(--line);background:var(--bg);font-size:11.5px;font-weight:600;color:var(--ink);white-space:nowrap}
.pickitem .pill.law{background:var(--accent-soft);border-color:var(--accent-line);color:var(--accent-ink)}
.pickitem .pill.bi{background:var(--plum-soft);border-color:rgba(122,82,199,.35);color:var(--plum)}

/* --- how to read this site: modal over a blurred page -------------------- */
.hmodal{position:fixed;inset:0;z-index:90;display:grid;place-items:center;padding:20px}
.hmodal[hidden]{display:none!important}
.card.sk{min-height:150px;pointer-events:none;opacity:.7}
.skl{height:14px;border-radius:7px;background:var(--hair);margin:14px 0;animation:skl 1.2s ease-in-out infinite}
.skl.w3{width:30%}.skl.w8{width:82%;height:20px}.skl.w6{width:60%}
@keyframes skl{50%{opacity:.45}}
.loading{padding:12px 0}
.sharemenu{position:absolute;z-index:95;min-width:200px;background:var(--surface);border:1px solid var(--line);border-radius:var(--r-md);box-shadow:var(--shadow-3);padding:6px;display:flex;flex-direction:column}
.sharemenu[hidden]{display:none!important}
.sharemenu a,.sharemenu button{display:block;text-align:left;padding:9px 12px;border:0;background:none;font:inherit;font-size:14px;color:var(--ink);border-radius:8px;cursor:pointer;text-decoration:none}
.sharemenu a:hover,.sharemenu button:hover{background:var(--hair)}
.tally .sharebtn{margin-left:auto}
.yours{padding:10px 0 18px}
.yours-bar{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:14px 0 18px}
.ynote{font-size:13.5px}
.yours-head{display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:6px}
.yours-head h3{margin:0;font-size:18px}
.yvote{border:1px solid var(--line);border-radius:var(--r-lg);background:var(--surface);padding:16px 18px;margin:12px 0}
.yv-head{font-size:15px;line-height:1.4;margin-bottom:10px}
.yv-members{display:grid;gap:6px;grid-template-columns:repeat(auto-fill,minmax(250px,1fr))}
.ymem{display:flex;align-items:center;gap:10px;border:1px solid var(--line);background:var(--bg);border-radius:12px;padding:8px 10px;font:inherit;font-size:14px;color:var(--ink);text-align:left;cursor:pointer;min-width:0}
.ymem:hover{border-color:var(--line-strong)}
.ymem{transition:transform .25s var(--ease),box-shadow .25s}
.ymem.mine{border-color:var(--accent);box-shadow:0 0 0 2px var(--accent-soft),0 12px 30px -16px color-mix(in srgb,var(--accent) 70%,transparent);transform:scale(1.045);z-index:1;background:var(--surface)}
@keyframes sheen{0%{background-position:220% 0}60%,100%{background-position:-120% 0}}
.shimmer{position:relative}
.shimmer::after{content:"";position:absolute;inset:-1px;border-radius:inherit;padding:1.5px;pointer-events:none;background:linear-gradient(115deg,transparent 35%,color-mix(in srgb,var(--accent) 75%,#fff) 50%,transparent 65%) 0 0/220% 100% no-repeat;-webkit-mask:linear-gradient(#000 0 0) content-box,linear-gradient(#000 0 0);-webkit-mask-composite:xor;mask-composite:exclude;animation:sheen 3.6s ease-in-out infinite}
.calm .shimmer::after{animation:none;background:var(--accent)}
.rep-top{display:flex;flex-wrap:wrap;gap:6px;justify-content:flex-end;padding-right:48px;margin:-2px 0 14px}
.ract{display:inline-flex;align-items:center;gap:7px;height:34px;padding:0 12px 0 10px;border:1px solid var(--line);border-radius:999px;background:var(--bg);color:var(--ink);font:inherit;font-size:13px;font-weight:500;text-decoration:none;cursor:pointer;transition:border-color .15s;white-space:nowrap}
.ract:hover{border-color:var(--ink)}
.ract svg,.know-line svg{width:16px;height:16px;flex:none;stroke:var(--accent);fill:none;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}
.rep-social{display:contents}
@media (max-width:560px){.rep-top{justify-content:flex-start;padding-right:44px}}
.know{margin:0 0 16px}
.know h3{font-family:var(--serif);font-weight:400;font-size:26px;margin:0 0 12px}
.know-b{background:var(--bg);border-radius:var(--r-lg);padding:14px 16px;margin-bottom:12px;font-size:14px;line-height:1.55}
.know-b h4{margin:0 0 8px;font-size:13px;color:var(--muted);font-weight:600;display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.know-b p{margin:0 0 8px}.know-b p:last-child{margin-bottom:0}
.know-line{display:flex;align-items:center;gap:8px;color:var(--muted)}
.know-list{margin:0;padding:0;list-style:none}
.know-list>li{padding:7px 0;border-bottom:1px solid var(--line)}.know-list>li:last-child{border-bottom:0}
.know-list .role{font-size:12px;font-weight:600;color:var(--accent-ink);background:var(--accent-soft);padding:2px 8px;border-radius:999px;margin-left:8px}
.know-list details{margin-top:4px;color:var(--muted);font-size:13px}.know-list details summary{cursor:pointer}
.know-list details ul{margin:6px 0 0;padding-left:18px}.know-list details li{padding:2px 0}
.know-list a{color:var(--ink);text-decoration:none}.know-list a:hover{text-decoration:underline}
.know-big{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap}
.know-big b{font-family:var(--serif);font-weight:400;font-size:44px;line-height:1}
.know-big span{color:var(--muted);flex:1;min-width:180px}
.know-bar{height:8px;border-radius:4px;background:var(--line);overflow:hidden;margin:10px 0 12px}
.know-bar i{display:block;height:100%;background:var(--pc);border-radius:4px}
.know-sub{font-weight:600;margin-top:10px!important}
.know-chips{display:flex;flex-wrap:wrap;gap:6px;margin:4px 0 8px}
.know-rule{font-size:12.5px;color:var(--muted)}
.know-wiki{border:1px dashed var(--line-strong);background:transparent}
.tag.wiki{background:var(--hair);color:var(--muted)}
.ymem>span:nth-child(2){flex:1;min-width:0;display:flex;flex-direction:column;line-height:1.25}
.ymem>span:nth-child(2) .muted{font-size:12.5px}
.ymem .vtag{flex:none}
.yv-acts{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}
.aka{display:block;font-size:13px;color:var(--muted);margin:-2px 0 8px}
.aka b{color:var(--ink);font-weight:600}
.pickitem .aka{margin:2px 0 4px}
.bmap{border:1px solid var(--line);border-radius:var(--r-lg);background:var(--bg);padding:14px 16px 16px;margin:16px 0 18px}
.bmap-head{display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:12px}
.bmap-head h4{margin:0;font-size:15px}
.bmap .mapsub{margin-top:14px}
.bmap .tally .num{font-size:38px}
.bmap .tsub{font-size:13.5px;color:var(--muted);margin-top:6px}
.bmap .mapframe{max-width:780px;margin:12px auto 0}
.bmap svg.usmap{width:100%;height:auto;display:block}
.bmap-side{margin-top:14px;font-size:13.5px}
.bmap-side h5{margin:0 0 8px;font-size:14px}
.bmap-mems{display:flex;flex-wrap:wrap;gap:6px}
.bmem{display:inline-flex;align-items:center;gap:8px;border:1px solid var(--line);border-radius:999px;padding:4px 10px 4px 4px;font-size:13px;background:var(--surface)}
.mapfilter{display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:12px;font-size:13.5px;color:var(--muted)}
.mapfilter[hidden]{display:none!important}
.mapfilter b{color:var(--ink)}
.trk{display:block;margin:12px 0 8px;text-align:left}
.trk .rail{display:block;position:relative;height:4px;border-radius:2px;background:var(--hair);margin:8px 8px 0}
.trk .fill,.trk .fillbad{position:absolute;top:0;bottom:0;border-radius:2px;width:0}
.trk .fill{left:0;background:var(--accent);transition:width 1.5s var(--ease) .15s}
.trk.go .fill{width:calc(var(--a) * 100%)}
.trk .fillbad{left:calc(var(--a) * 100%);background:var(--rep);transition:width .6s var(--ease) 1.5s}
.trk.go .fillbad{width:calc((var(--p) - var(--a)) * 100%)}
.trk .stop{position:absolute;top:50%;width:10px;height:10px;margin:-5px 0 0 -5px;border-radius:50%;background:var(--surface);border:2px solid var(--line-strong);transition:background .3s,border-color .3s;transition-delay:calc(.15s + var(--t) * 1.5s)}
.trk.go .stop.done,.trk.go .stop.now{background:var(--accent);border-color:var(--accent)}
.trk.go .stop.fail{background:var(--rep);border-color:var(--rep)}
.trk .run{position:absolute;top:50%;left:0;width:16px;height:16px;margin:-8px 0 0 -8px;border-radius:50%;background:var(--accent);box-shadow:0 0 0 4px color-mix(in srgb,var(--accent) 28%,transparent);opacity:0;transition:left 1.5s var(--ease) .15s,opacity .3s}
.trk.go .run{left:calc(var(--p) * 100%);opacity:1}
.trk.active.go .run{animation:trkpulse 2.4s ease-in-out 1.9s infinite}
@keyframes trkpulse{50%{box-shadow:0 0 0 10px color-mix(in srgb,var(--accent) 0%,transparent)}}
.trk.failed .run{background:var(--rep);box-shadow:0 0 0 4px color-mix(in srgb,var(--rep) 28%,transparent)}
.trk.stalled .fill,.trk.stalled.go .stop.done,.trk.stalled.go .stop.now{background:var(--line-strong);border-color:var(--line-strong)}
.trk.stalled .run{background:var(--muted);box-shadow:none}
.trk-labels{display:block;position:relative;height:18px;margin:12px 8px 0}
.trk.full .trk-labels{height:36px}
.trk-labels>span{position:absolute;top:0;transform:translateX(-50%);display:flex;flex-direction:column;align-items:center;font-size:11.5px;line-height:1.35;color:var(--muted);white-space:nowrap}
.trk-labels>span:first-child{transform:none;align-items:flex-start;margin-left:-8px}
.trk-labels>span:last-child{transform:translateX(-100%);align-items:flex-end;margin-left:8px}
.trk-labels b{font-weight:600}
.trk-labels .done b,.trk-labels .now b{color:var(--ink)}
.trk-labels .fail b{color:var(--bad-ink)}
.trk-labels em{font-style:normal;font-size:11px}
.trk-cap{display:block;margin-top:8px;font-size:12.5px;color:var(--muted);font-weight:500}
.trk.failed .trk-cap{color:var(--bad-ink)}
.trk-cap .quiet{font-weight:400}
.trk.slim{margin:10px 0 12px}
.pickitem .trk{margin:12px 0 2px}
.calm .trk .fill,.calm .trk .fillbad,.calm .trk .run,.calm .trk .stop{transition:none}
.calm .trk.active.go .run{animation:none}
@media (max-width:560px){
  .trk.pick .trk-labels>span:not(.now):not(.fail):not(:first-child):not(:last-child){display:none}
  .trk.full .trk-labels{position:static;height:auto;display:grid;grid-template-columns:1fr 1fr;gap:4px 14px;margin:12px 0 0}
  .trk.full .trk-labels>span{position:static;transform:none;flex-direction:row;gap:6px;align-items:baseline;margin:0}
  .trk.full .trk-labels>span:last-child{transform:none}
}
.hm-back{position:absolute;inset:0;background:rgba(21,23,27,.42);backdrop-filter:blur(9px) saturate(.9);-webkit-backdrop-filter:blur(9px) saturate(.9);animation:fadein .25s var(--ease) both}
:root[data-theme="dark"] .hm-back{background:rgba(0,0,0,.58)}
@keyframes fadein{from{opacity:0}to{opacity:1}}
.hm-card{position:relative;width:min(880px,100%);max-height:calc(100vh - 40px);overflow:auto;background:var(--surface);border:1px solid var(--line);border-radius:var(--r-xl);box-shadow:var(--shadow-3);padding:30px clamp(20px,4vw,38px) 28px;animation:rise .32s var(--ease) both}
.hm-card h2{font-size:clamp(26px,3.4vw,34px);margin:0 0 10px}
.hm-lede{margin:0 0 22px;font-size:15px;line-height:1.6;color:var(--muted);max-width:62ch}
.hm-foot{margin:22px 0 0;padding-top:16px;border-top:1px solid var(--line);font-size:12.5px;color:var(--muted)}
.hm-x{position:absolute;top:14px;right:16px;border:0;background:none;font-size:26px;line-height:1;color:var(--muted);cursor:pointer;padding:2px 6px;border-radius:8px}
.hm-x:hover{color:var(--ink);background:var(--hair)}
.hm-grid{display:grid;gap:16px;grid-template-columns:1fr}
@media (min-width:720px){.hm-grid{grid-template-columns:repeat(3,1fr)}}
.labelcard{border:1px solid var(--line);border-radius:var(--r-lg);background:var(--bg);padding:20px}
.labelcard h3{margin:12px 0 8px;font-size:16px;font-weight:700}
.labelcard p{margin:0;font-size:13.5px;line-height:1.6;color:var(--muted)}
.hero h1 .w{display:inline-block;overflow:hidden;vertical-align:bottom;padding:0 .04em .14em 0;margin:0 -.04em -.14em 0}
.hero h1 .w>span{display:inline-block;transform:translateY(108%);animation:wordup .95s var(--ease) forwards}
@keyframes wordup{to{transform:none}}
.hero{overflow:hidden}
.hero canvas{position:absolute;inset:0;width:100%;height:100%;pointer-events:none}
.hero:after{content:"";position:absolute;inset:0;pointer-events:none;background:radial-gradient(75% 85% at 22% 45%,var(--bg) 30%,transparent 72%)}
.hero .wrap{position:relative;z-index:2}
/* on a wide dark page the lit Capitol stands at the right edge: keep the veil behind the words, thin it over the building */
@media (min-width:1180px){
  :root[data-theme="dark"] .hero::after{background:linear-gradient(to bottom,var(--bg) 0%,rgba(15,17,20,0) 14%),linear-gradient(to right,rgba(15,17,20,.88) 0%,rgba(15,17,20,.80) 50%,rgba(15,17,20,.30) 80%,rgba(15,17,20,.12) 100%)}
}
.hero h1 .w>span.out{animation:wordout .5s var(--ease) forwards}
@keyframes wordout{from{transform:none}to{transform:translateY(-112%)}}
/* depth on scroll: the headline drifts and thins as the page moves under it (--par is set by the scene, 0 to 1) */
.motion .hero h1{transform:translate3d(0,calc(var(--par,0) * 56px),0);opacity:calc(1 - var(--par,0) * .6)}
/* the rail's entrance animation holds its transform, so its drift uses the separate translate property */
.motion .hero .kpirail{translate:0 calc(var(--par,0) * 24px)}
/* the featured bill's card leans toward the pointer */
.hero-copy{perspective:1400px}
.spotlight{transition:rotate .5s var(--ease)}
/* the latest recorded votes, as a moving line */
.ticker{display:flex;align-items:stretch;position:relative;z-index:2;background:var(--surface);border-top:1px solid var(--hair);border-bottom:1px solid var(--hair)}
.ticker[hidden]{display:none!important}
.ticker-label{flex:none;display:flex;align-items:center;gap:9px;padding:0 16px 0 20px;font-size:11.5px;font-weight:700;letter-spacing:.09em;text-transform:uppercase;color:var(--ink);border-right:1px solid var(--hair)}
.ticker-label i{width:7px;height:7px;border-radius:2px;background:var(--accent);transform:rotate(45deg)}
.ticker-view{flex:1;min-width:0;overflow:hidden;-webkit-mask-image:linear-gradient(to right,transparent 0,#000 26px,#000 calc(100% - 44px),transparent 100%);mask-image:linear-gradient(to right,transparent 0,#000 26px,#000 calc(100% - 44px),transparent 100%)}
.ticker-track{display:flex;width:max-content;animation:tick var(--tick,70s) linear infinite}
.ticker-track .half{display:flex;flex:none}
.ticker:hover .ticker-track{animation-play-state:paused}
@keyframes tick{to{transform:translate3d(-50%,0,0)}}
.tk{display:inline-flex;align-items:baseline;gap:9px;padding:12px 20px;font-size:13.5px;line-height:1.3;white-space:nowrap;text-decoration:none;color:var(--ink);border-right:1px solid var(--hair);transition:background .15s}
.tk:hover{background:var(--hair)}
.tk b{font-weight:600}
.tk .tkt{color:var(--muted);max-width:34ch;overflow:hidden;text-overflow:ellipsis}
.tk .tkres{font-weight:600;font-variant-numeric:tabular-nums;color:var(--accent-ink)}
.tk .tkres.no{color:var(--bad-ink)}
.tk .tkd{color:var(--muted);font-size:12.5px}
.ticker.kb .ticker-view,html.calm .ticker-view{overflow-x:auto;scrollbar-width:thin;-webkit-mask-image:none;mask-image:none}
.ticker.kb .ticker-track,html.calm .ticker-track{animation:none}
.ticker.kb .half+.half,html.calm .half+.half{display:none}
@media (prefers-reduced-motion: reduce){.ticker-view{overflow-x:auto;-webkit-mask-image:none;mask-image:none}.ticker-track{animation:none}.half+.half{display:none}}
@media (max-width:560px){.ticker-label{padding:0 12px 0 14px;font-size:10.5px}.tk{padding:11px 16px;font-size:13px}}
.spotlight{background:var(--surface);border:1px solid var(--hair);border-radius:var(--r-xl);padding:22px 22px 16px;box-shadow:var(--shadow-3);position:relative;animation:spotin 1.1s .55s var(--ease) both}
@keyframes spotin{from{opacity:0;transform:translateY(34px) scale(.96)}to{opacity:1;transform:none}}
.spot-spon{display:flex;align-items:center;gap:10px;font-size:13.5px;color:var(--muted);margin:0 0 14px;line-height:1.3}
.spot-spon b{color:var(--ink);font-weight:600}
.spot-head{display:flex;justify-content:space-between;align-items:center;gap:4px 12px;flex-wrap:wrap;font-size:13px;color:var(--muted);margin-bottom:14px}
.spot-head b{white-space:nowrap}
.spot-head b{color:var(--ink);font-weight:600}
.spotlight .pid{display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin-bottom:10px}
.spotlight .ptitle{font-weight:600;font-size:21px;line-height:1.22;letter-spacing:-.012em;margin-bottom:8px;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
.spotlight .pplain{font-size:15px;color:var(--muted);margin-bottom:16px;min-height:46px}
.pfoot{display:flex;justify-content:space-between;align-items:center;margin-top:14px;padding-top:12px;border-top:1px solid var(--line);gap:10px}
.dots{display:flex;gap:6px}
.dots button{width:8px;height:8px;border-radius:4px;background:var(--line-strong);transition:background .3s,width .3s var(--ease);position:relative;overflow:hidden}
.dots button[aria-current="true"]{background:var(--line-strong);width:26px}
.dots button[aria-current="true"]:after{content:"";position:absolute;inset:0;background:var(--ink);transform-origin:left;transform:scaleX(0);animation:fillbar 9s linear forwards}
@keyframes fillbar{to{transform:scaleX(1)}}
.fade{transition:opacity .35s ease,transform .35s var(--ease)}
.fade.out{opacity:0;transform:translateY(4px)}

/* pills, grades */
.pill{display:inline-flex;align-items:center;gap:6px;font-size:12.5px;font-weight:600;padding:4px 9px;border-radius:999px;line-height:1.2;white-space:nowrap}
.pill.id{background:var(--ink);color:var(--bg)}
.pill.law{background:var(--teal-soft);color:var(--teal-ink)}
.pill.pending{background:var(--amber-soft);color:var(--amber-ink)}
.pill.failed{background:var(--bad-soft);color:var(--bad-ink)}
.pill.adopted{background:var(--plum-soft);color:var(--plum)}
.pill.intro{background:transparent;color:var(--muted);border:1px solid var(--line)}
.pill.lens{background:transparent;color:var(--muted);border:1px dashed var(--line-strong);font-weight:500}
.grade{display:inline-grid;place-items:center;width:20px;height:20px;border-radius:5px;font-weight:700;font-size:11.5px;background:var(--bg);border:1px solid var(--line);color:var(--ink)}
.grade[data-g="A"]{background:var(--teal-soft);color:var(--teal-ink);border-color:transparent}
.grade[data-g="B"]{background:var(--cobalt-soft);color:var(--cobalt-ink);border-color:transparent}
.grade[data-g="C"]{background:var(--amber-soft);color:var(--amber-ink);border-color:transparent}

/* gauges: the signature element */
.axes{display:grid;gap:14px}
.axis{display:grid;gap:7px}
.axis .lab{font-size:13px;color:var(--muted);display:flex;justify-content:space-between;gap:8px;align-items:center}
.axis .lab b{color:var(--ink);font-weight:600}
.gauge{position:relative;height:8px;border-radius:4px;background:var(--line)}
.gauge .range{position:absolute;top:0;height:8px;border-radius:4px;left:var(--lo,50%);width:0;background:var(--accent-line);opacity:.75;transition:width .9s var(--ease)}
.gauge .mid{position:absolute;left:50%;top:-4px;width:1px;height:16px;background:var(--line-strong)}
.gauge .dot{position:absolute;top:50%;left:50%;width:16px;height:16px;margin:-8px 0 0 -8px;border-radius:50%;background:var(--ink);border:2.5px solid var(--surface);box-shadow:0 0 0 1px var(--line-strong),0 2px 6px rgba(0,0,0,.18);transition:left 1.1s cubic-bezier(.34,1.35,.64,1)}
.gauge.backing{background:linear-gradient(90deg,var(--dem) 0 14%,var(--line) 30% 70%,var(--rep) 86% 100%)}
.live .gauge .dot{left:var(--pos,50%)}
.live .gauge .range{width:var(--w,0%)}
.ends{display:flex;justify-content:space-between;font-size:11.5px;color:var(--muted);margin-top:-2px}
.quad{display:grid;grid-template-columns:64px 1fr;gap:12px;align-items:center}
.quad svg{width:64px;height:64px}
.quad .q{fill:none;stroke:var(--line-strong);stroke-width:1}
.quad .pt{fill:var(--accent);transition:transform .9s var(--ease)}
.live .quad .pt{transform:translate(var(--dx,0px),var(--dy,0px))}
.quad small{font-size:13px;color:var(--muted);line-height:1.45;display:block}
.quad small b{color:var(--ink);font-weight:600}
.na{font-size:13px;color:var(--muted);font-style:italic}
.axes-empty{font-size:13px;color:var(--muted);background:var(--bg);border-radius:var(--r-sm);padding:9px 12px;line-height:1.45}

/* sections */
section.block{padding:72px 0;scroll-margin-top:72px}
@media (min-width:960px){section.block{padding:104px 0}}
.sechead{display:flex;align-items:flex-end;justify-content:space-between;gap:20px;flex-wrap:wrap}
.sechead p{max-width:58ch;font-size:16px;color:var(--muted);margin:12px 0 0}
#bills{padding-top:40px;scroll-margin-top:62px;border-top:1px solid var(--line)}
.controls{position:relative;z-index:20;background:color-mix(in srgb,var(--bg) 88%,transparent);backdrop-filter:blur(14px);-webkit-backdrop-filter:blur(14px);padding:12px 0 8px;margin:18px 0 6px}
.controls:after{content:"";position:absolute;left:0;right:0;bottom:0;height:1px;background:var(--hair)}
@media (min-width:760px){.controls{position:sticky;top:62px}}
.bar{display:flex;gap:10px;align-items:center}
.search{flex:1;display:flex;align-items:center;gap:10px;background:var(--surface);border:1px solid var(--line);border-radius:999px;padding:0 10px 0 16px;height:46px;transition:border-color .15s,box-shadow .15s;min-width:0}
.search:focus-within{border-color:var(--ink);box-shadow:0 0 0 4px var(--hair)}
.search svg{width:18px;height:18px;stroke:var(--muted);fill:none;stroke-width:2;stroke-linecap:round;flex:none}
.search input{flex:1;border:0;background:transparent;font:inherit;color:inherit;height:100%;min-width:0;font-size:15.5px}
.search input:focus{outline:none}
.search input::-webkit-search-cancel-button{-webkit-appearance:none}
.search kbd{flex:none}
@media (max-width:760px){.search kbd{display:none}}
.selwrap{position:relative;display:inline-flex;align-items:center;gap:8px;height:46px;padding:0 34px 0 14px;border:1px solid var(--line);border-radius:999px;background:var(--surface);font-size:14px;color:var(--muted);white-space:nowrap;flex:none}
.selwrap select{appearance:none;-webkit-appearance:none;border:0;background-color:var(--surface);font:inherit;font-weight:600;color:var(--ink);cursor:pointer;padding:0}
/* The open dropdown list is drawn by the browser, not by this page. It took the
   near-white dark-theme text but not the transparent background it used to have,
   so on Windows the list came out white-on-white. Name the colours for the list
   itself; the closed control looks the same, because the pill behind it is already
   this colour. */
.selwrap select option{background-color:var(--surface);color:var(--ink)}
.selwrap select optgroup{background-color:var(--surface);color:var(--muted);font-weight:600}
.selwrap select:focus{outline:none}
.selwrap:focus-within{border-color:var(--ink)}
.selwrap>svg{position:absolute;right:12px;width:14px;height:14px;stroke:var(--muted);fill:none;stroke-width:2;stroke-linecap:round;stroke-linejoin:round;pointer-events:none}
.chips{display:flex;gap:6px;flex-wrap:nowrap;overflow-x:auto;padding:10px 20px 4px;margin:0 -20px;scrollbar-width:none;position:relative}
.chip-ind{position:absolute;top:10px;left:0;width:0;height:34px;border-radius:999px;background:var(--ink);transition:left .4s var(--ease),width .4s var(--ease);pointer-events:none}
.chips::-webkit-scrollbar{display:none}
@media (min-width:900px){.chips{margin:0;padding-left:0;padding-right:0}}
.chip{flex:none;height:34px;padding:0 13px;border-radius:999px;border:1px solid var(--line);background:var(--surface);font-size:13.5px;font-weight:500;color:var(--ink);display:inline-flex;align-items:center;position:relative;z-index:1;transition:background .2s,color .25s,border-color .2s,transform .1s}
.chip:hover{border-color:var(--line-strong)}
.chip[aria-pressed="true"]{background:var(--ink);color:var(--bg);border-color:var(--ink)}
#chips .chip[aria-pressed="true"]{background:transparent;border-color:transparent}
.chip:active{transform:scale(.97)}
.row{display:flex;justify-content:space-between;align-items:center;gap:10px;margin:10px 0 14px;flex-wrap:wrap}
.selwrap.compact{height:36px;font-size:13.5px;padding-right:30px}
#count{font-size:14px}

/* cards */
.grid{display:grid;gap:14px;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));margin:0 0 8px;align-items:start}
@media (max-width:420px){.grid{grid-template-columns:1fr}}
.showmore{grid-column:1/-1;justify-self:center;height:44px;padding:0 22px;font-size:14.5px;margin:12px 0 24px;border-color:var(--line-strong)}
.card{background:var(--surface);border:1px solid var(--line);border-radius:var(--r-lg);padding:18px 18px 12px;display:flex;flex-direction:column;gap:12px;box-shadow:var(--shadow-1);transition:border-color .2s,box-shadow .3s,transform .3s var(--ease),opacity .75s var(--ease)}
.card:hover{border-color:var(--line-strong);transform:translateY(-3px);box-shadow:var(--shadow-2)}
.card.open:hover{transform:none}
.card .meta .spon{display:inline-flex;align-items:center;gap:6px}
.card.open{grid-column:1/-1;border-color:var(--line-strong);box-shadow:var(--shadow-2)}
.card .head{display:flex;gap:6px;flex-wrap:wrap;align-items:center}
.card .title{font-weight:600;font-size:18px;line-height:1.25;letter-spacing:-.012em;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden;text-wrap:pretty}
.card.open .title{-webkit-line-clamp:unset;font-size:22px}
.card .plain{font-size:15px;color:var(--muted);line-height:1.5}
.card .meta{font-size:13px;color:var(--muted);display:flex;gap:4px 16px;flex-wrap:wrap}
.card .meta b{color:var(--ink);font-weight:600}
.card .foot{display:flex;justify-content:space-between;align-items:center;margin-top:auto;padding-top:10px;border-top:1px solid var(--line);gap:8px}
.card .foot .status{font-size:13px;color:var(--muted);min-width:0}
.acts{display:flex;gap:2px;flex:none}
.more,.copylink{display:inline-flex;align-items:center;gap:6px;font-weight:600;font-size:14px;color:var(--ink);padding:7px 10px;border-radius:999px;transition:background .15s}
.more:hover,.copylink:hover{background:var(--hair)}
.more svg,.copylink svg{width:15px;height:15px;stroke:currentColor;fill:none;stroke-width:2.25;stroke-linecap:round;stroke-linejoin:round;transition:transform .3s var(--ease)}
.card.open .more svg{transform:rotate(180deg)}
.detail{display:grid;grid-template-rows:0fr;transition:grid-template-rows .45s var(--ease)}
.card.open .detail{grid-template-rows:1fr}
.detail>div{overflow:hidden;min-height:0}
.tabs{display:flex;gap:4px;border-bottom:1px solid var(--line);margin:6px 0 16px;overflow-x:auto;scrollbar-width:none}
.tabs::-webkit-scrollbar{display:none}
.tab{padding:10px;border-bottom:2px solid transparent;margin-bottom:-1px;font-size:14px;font-weight:500;color:var(--muted);white-space:nowrap;border-radius:0;transition:color .15s}
.tab:hover{color:var(--ink)}
.tab[aria-selected="true"]{color:var(--ink);border-bottom-color:var(--ink);font-weight:600}
.pane{display:none;animation:rise .35s var(--ease)}
.pane.show{display:block}
@keyframes rise{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
.who{display:grid;gap:8px;grid-template-columns:repeat(auto-fill,minmax(240px,1fr))}
.who div{background:var(--bg);border-radius:var(--r-md);padding:12px 14px;font-size:14px;line-height:1.5}
.who div b{display:block;margin-bottom:3px;font-weight:600}
.tl{list-style:none;margin:0;padding:0;display:grid}
.tl li{display:grid;grid-template-columns:104px 1fr;gap:10px;font-size:14px;padding:9px 0;border-bottom:1px solid var(--line)}
.tl li b{font-weight:600}
.flag{display:grid;grid-template-columns:auto 1fr;gap:10px;align-items:start;padding:9px 0;border-bottom:1px solid var(--line);font-size:14px}
.flag .k{background:var(--amber-soft);color:var(--amber-ink);border-radius:6px;padding:2px 8px;font-size:12px;font-weight:600;white-space:nowrap}
.vote{display:grid;grid-template-columns:80px 1fr auto;gap:10px;font-size:14px;padding:9px 0;border-bottom:1px solid var(--line);align-items:center}
.vote .tally{font-family:var(--serif);font-size:22px;line-height:1;text-align:right;white-space:nowrap}
.vote .tally a{font-family:var(--sans)}
.vote .ch{font-weight:600}
.why{display:grid;gap:10px}
.why article{background:var(--bg);border-radius:var(--r-md);padding:14px 16px;font-size:14px;line-height:1.5}
.why article h4{margin:0 0 6px;font-size:15px;display:flex;align-items:center;gap:8px}
.links{display:flex;gap:8px;flex-wrap:wrap;margin-top:6px}
.links a{text-decoration:none;border:1px solid var(--line);border-radius:999px;padding:7px 13px;font-size:13.5px;font-weight:500;background:var(--surface);color:var(--ink);transition:border-color .15s}
.links a:hover{border-color:var(--ink)}
.note{font-size:13px;color:var(--muted);background:var(--bg);border-radius:var(--r-sm);padding:9px 12px;margin:10px 0 0;line-height:1.5}
.empty{grid-column:1/-1;padding:56px 20px;text-align:center;color:var(--muted);border:1px dashed var(--line);border-radius:var(--r-lg)}

/* vote map: the one dramatic moment on the page */
.theater{background:#0C0E12;color:#ECEDE9;border-top:1px solid #1B1F26;border-bottom:1px solid #1B1F26;
  --bg:#0C0E12;--surface:#14171C;--ink:#ECEDE9;--muted:#9BA1A9;--line:#262A31;--line-strong:#3A3F48;--hair:rgba(236,237,233,.09);
  --dem:#7E9BFF;--rep:#FF7B72;--plum:#B49BF2;--teal-soft:#12302B;--teal-ink:#9FE3D6;--bad-soft:#44201D;--bad-ink:#FFB3AC;--cobalt-ink:#B9C8FF;
  --accent:#4CC5B0;--accent-ink:#9FE3D6;--accent-soft:#12302B;--shadow-1:none;--shadow-2:none;color-scheme:dark}
.theater .sechead p{color:var(--muted)}
.theater-grid{display:grid;gap:18px;grid-template-columns:1fr;margin-top:28px}
@media (min-width:1000px){.theater-grid{grid-template-columns:minmax(0,1.55fr) minmax(300px,.85fr);gap:24px;align-items:start}}
.stage{background:var(--surface);border:1px solid var(--line);border-radius:var(--r-xl);padding:18px}
@media (min-width:600px){.stage{padding:22px}}
.votebar{display:flex;gap:8px;align-items:center}
.votebar .selwrap{flex:1;min-width:0;height:44px;border-radius:12px;padding-left:14px}
.votebar .selwrap select{width:100%;text-overflow:ellipsis;overflow:hidden;white-space:nowrap;min-width:0}
.mapsub{margin-top:18px}
.tally{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap}
.tally .num{font-family:var(--serif);font-size:48px;line-height:1;letter-spacing:-.01em;font-weight:400}
.tally .num span{color:var(--muted);margin:0 3px}
.tally .res{font-size:13.5px;font-weight:600;padding:5px 10px;border-radius:999px;background:var(--hair)}
.tally .res.pass{background:var(--teal-soft);color:var(--teal-ink)}
.tally .res.fail{background:var(--bad-soft);color:var(--bad-ink)}
.tsub{font-size:14px;color:var(--muted);margin-top:8px;line-height:1.5;max-width:70ch}
.tsub b{color:var(--ink);font-weight:600}
.split{display:grid;gap:7px;margin-top:14px;font-size:12.5px;color:var(--muted)}
.split div{display:grid;grid-template-columns:92px 1fr auto;gap:10px;align-items:center}
.split .bar{height:8px;border-radius:4px;background:var(--line);overflow:hidden;display:flex}
.split .bar i{display:block;height:100%;transition:width .6s var(--ease)}
.split .bar i.y{background:var(--pc)}
.split .bar i.n{background:var(--pc);opacity:.32}
.split b{color:var(--ink);font-weight:600}
.legend2{display:flex;gap:8px 16px;flex-wrap:wrap;font-size:12.5px;color:var(--muted);margin-top:14px}
.legend2 span{display:inline-flex;align-items:center;gap:6px}
.sw{display:inline-block;width:12px;height:12px;border-radius:3px}
.mapframe{position:relative;margin-top:16px}
.viewsw{display:flex;gap:6px;flex-wrap:wrap;margin-top:16px}
.viewsw[hidden]{display:none!important}
.viewsw .chip[aria-pressed="true"]{background:var(--ink);color:var(--bg);border-color:var(--ink)}
.chamber{display:block;width:100%;aspect-ratio:975/610;border-radius:var(--r-lg);background:radial-gradient(120% 90% at 50% 100%,#1A2033 0%,#0E1118 55%,#0A0C11 100%);touch-action:pan-y;cursor:grab;outline:none}
.chamber.grabbing{cursor:grabbing}
.chamber:focus-visible{box-shadow:0 0 0 2px var(--accent)}
.chamber[hidden]{display:none!important}
.ch-tip{position:absolute;z-index:3;transform:translate(-50%,calc(-100% - 14px));background:var(--ink);color:var(--bg);font-size:12.5px;line-height:1.35;padding:6px 10px;border-radius:8px;white-space:nowrap;pointer-events:none;opacity:0;transition:opacity .12s}
.ch-tip.show{opacity:1}.ch-tip b{display:block;font-weight:600}
.ch-info{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-top:12px;min-height:44px;font-size:14px}
.ch-info[hidden]{display:none!important}
.ch-mine{display:inline-flex;align-items:center;gap:7px;color:var(--ink);font-size:13.5px}
.ch-mine i{width:11px;height:11px;border-radius:50%;border:2px solid #E0B040;flex:none}
.ch-yours{font-size:11px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#7A560A;background:#F9E7B0;border-radius:999px;padding:4px 10px}
.ch-who{display:flex;flex-direction:column;line-height:1.3;margin-right:auto}.ch-who .muted{font-size:12.5px}
.stage.chamber-on .legend2{display:none}
@media (max-width:560px){.chamber{aspect-ratio:4/3.4}}
svg.usmap{width:100%;height:auto;display:block}
.mapback{position:absolute;left:8px;top:8px;z-index:2;height:38px;padding:0 14px 0 8px;font-size:14px;border-color:var(--line-strong);background:var(--surface);color:var(--ink);animation:rowin .35s var(--ease) both}
.mapback[hidden]{display:none!important}
svg.usmap g.state{transition:opacity .55s var(--ease)}
svg.usmap g.state.dim{opacity:.16;pointer-events:none}
svg.usmap.blur g.state.dim{filter:blur(1.3px)}
svg.usmap.zoomed g.state:not(.dim) .abbr{display:none}
svg.usmap path.dist{stroke:var(--bg);stroke-width:1;cursor:pointer;transition:filter .15s}
svg.usmap path.dist:hover,svg.usmap path.dist.hl{stroke:#fff;stroke-width:2;filter:brightness(1.18)}
svg.usmap path.dist:focus-visible{outline:none;stroke:#fff;stroke-width:2.5}
svg.usmap path.dout{fill:none;stroke:#fff;stroke-width:1.6;pointer-events:none;opacity:.9}
svg.usmap text.dlab{font-family:var(--sans);font-weight:700;fill:#fff;pointer-events:none;paint-order:stroke;stroke:rgba(0,0,0,.6);stroke-linejoin:round}
.mapside .side-head{display:flex;justify-content:space-between;align-items:center;gap:10px;margin-bottom:8px}
.mapside .side-head h3{margin:0}
.mapside .side-head .chip{height:30px;font-size:12.5px}
.mrow.click{cursor:pointer;border-radius:10px;margin:0 -8px;padding:10px 8px;transition:background .15s}
.mrow.click:hover{background:var(--hair)}
.mrow.d4{grid-template-columns:auto auto 1fr auto}
.mrow .dnum{font-family:var(--serif);font-size:22px;line-height:1;color:var(--muted);min-width:28px;text-align:center}
.mapside .hint{font-size:12.5px;color:var(--muted);margin:6px 0 4px}
/* the representative card */
.repmodal{position:fixed;inset:0;z-index:55}
.repmodal[hidden]{display:none!important}
.rep-back{position:absolute;inset:0;background:rgba(10,12,16,.55);backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px)}
.rep{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);width:min(760px,calc(100vw - 24px));max-height:min(86vh,900px);overflow:auto;background:var(--surface);color:var(--ink);border:1px solid var(--line);border-radius:var(--r-xl);box-shadow:var(--shadow-3);padding:26px;animation:pop .28s var(--ease)}
@media (max-width:640px){.rep{left:0;right:0;top:auto;bottom:0;transform:none;width:100%;max-height:90vh;border-radius:24px 24px 0 0;padding:22px 18px 30px;animation:sheet .35s var(--ease)}}
@keyframes sheet{from{transform:translateY(40px);opacity:0}to{transform:none;opacity:1}}
.rep-x{position:absolute;right:14px;top:14px}
.rep-head{display:grid;grid-template-columns:auto 1fr;gap:18px;align-items:center;margin-bottom:18px;padding-right:44px}
.rep-head h2{font-size:clamp(28px,4vw,40px);line-height:1.02}
.rep-head .seat{font-size:15px;color:var(--muted);margin-top:6px;line-height:1.45}
.rep-head .seat b{color:var(--ink);font-weight:600}
.rep-grid{display:grid;gap:14px;grid-template-columns:1fr;align-items:start}
@media (min-width:640px){.rep-grid{grid-template-columns:1fr 1fr}}
.rep-block{background:var(--bg);border-radius:var(--r-lg);padding:14px 16px;font-size:14px;line-height:1.5}
.rep-block h4{margin:0 0 8px;font-size:13px;color:var(--muted);font-weight:600}
.rep-block .big{font-family:var(--serif);font-size:30px;line-height:1;margin:2px 0 6px}
.rep-block .mini{width:100%;height:auto;max-height:170px;display:block;margin:6px 0 8px}
.rep-block .mini .st{fill:var(--line);stroke:var(--surface);stroke-width:.6}
.rep-block .mini .me{stroke:var(--surface);stroke-width:.8}
.rep-votes{display:grid;gap:6px}
.rep-votes div{display:grid;grid-template-columns:1fr auto;gap:10px;align-items:center;padding:6px 0;border-bottom:1px solid var(--line)}
.rep-votes div:last-child{border-bottom:0}
.rep-votes .muted{font-size:12.5px}
.rep-links{display:flex;gap:8px;flex-wrap:wrap;margin-top:16px}
.rep-links a,.rep-links button{text-decoration:none;border:1px solid var(--line);border-radius:999px;padding:8px 14px;font-size:13.5px;font-weight:500;background:var(--surface);color:var(--ink);transition:border-color .15s}
.rep-links a:hover,.rep-links button:hover{border-color:var(--ink)}
.rep .vtag{font-size:14px;padding:6px 12px}
.rep .rec{display:inline-flex;align-items:center;gap:8px}
svg.usmap .outline{fill:none;stroke:var(--bg);stroke-width:1.1;pointer-events:none}
svg.usmap .hit{fill:transparent;cursor:pointer}
svg.usmap g.state.sel .outline,svg.usmap g.state:hover .outline{stroke:#fff;stroke-width:2}
svg.usmap .fill rect,svg.usmap .fill polygon{transition:width .6s var(--ease),x .6s var(--ease)}
svg.usmap .fill{transition:opacity .55s var(--ease);transition-delay:var(--d,0ms)}
svg.usmap.swap .fill{opacity:0;transition:none}
svg.usmap g.state .outline{transition:stroke .2s}
svg.usmap g.state.sel .outline{animation:pulse 1.1s ease 2}
@keyframes pulse{0%,100%{stroke-width:2}50%{stroke-width:4.5}}
.stage{position:relative}
.mtip{position:absolute;z-index:3;pointer-events:none;background:var(--ink);color:var(--bg);font-size:12.5px;font-weight:500;padding:6px 10px;border-radius:8px;white-space:nowrap;transform:translate(-50%,calc(-100% - 12px));opacity:0;transition:opacity .15s}
.mtip.show{opacity:1}
.mtip b{font-weight:700;margin-right:6px}
.tally .num span.v{display:inline-block;min-width:1.2ch;text-align:center}
svg.usmap .abbr{font-family:var(--sans);font-size:10.5px;font-weight:600;fill:#fff;pointer-events:none;paint-order:stroke;stroke:rgba(0,0,0,.55);stroke-width:2.5px;stroke-linejoin:round}
.mapside{background:var(--surface);border:1px solid var(--line);border-radius:var(--r-xl);padding:18px;min-height:200px}
@media (min-width:1000px){.mapside{position:sticky;top:80px;max-height:calc(100vh - 104px);overflow:auto}}
.mapside h3{font-size:17px;margin-bottom:8px}
.mapside>.muted{font-size:14px}
.mrow{display:grid;grid-template-columns:auto 1fr auto;gap:12px;align-items:center;padding:10px 0;border-bottom:1px solid var(--line);font-size:14px;animation:rowin .5s var(--ease) both;animation-delay:calc(var(--i,0)*45ms)}
@keyframes rowin{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}
.mrow:last-child{border-bottom:0}
.mrow b{font-weight:600}
.mrow .meta{color:var(--muted);font-size:12.5px;line-height:1.5}
.mrow .meta a{color:var(--accent-ink);text-decoration:none}
.mrow .meta a:hover{text-decoration:underline}
.mrow .meta>span{display:block}
.mrow .meta>span.mlinks{display:flex;gap:12px;flex-wrap:wrap;margin-top:2px}
.party{display:inline-grid;place-items:center;width:26px;height:26px;border-radius:50%;font-size:12px;font-weight:700;color:#fff;flex:none}
.party.D{background:var(--dem)}.party.R{background:var(--rep)}.party.I,.party.ID{background:var(--plum)}.party.L{background:var(--amber)}
.vtag{display:inline-block;padding:4px 10px;border-radius:999px;font-size:12px;font-weight:600;white-space:nowrap}
.vtag.Y{background:var(--teal-soft);color:var(--teal-ink)}.vtag.N{background:var(--bad-soft);color:var(--bad-ink)}.vtag.X,.vtag.P{background:var(--hair);color:var(--muted)}
.maplink{font-size:12px;color:var(--accent-ink);text-decoration:none;border:1px solid var(--line);border-radius:999px;padding:2px 9px;margin-left:6px;font-weight:500}
.theater .note{background:var(--hair);color:var(--muted);margin-top:16px}

/* how the ratings work */
.how{display:grid;gap:36px 32px;grid-template-columns:1fr;margin-top:36px}
@media (min-width:860px){.how{grid-template-columns:repeat(3,1fr)}}
.how article{border-top:1px solid var(--ink);padding-top:18px;display:grid;gap:14px;align-content:start}
.how article p{font-size:14.5px;color:var(--muted);line-height:1.55;margin:0}
.legend{display:flex;gap:10px 18px;flex-wrap:wrap;margin-top:34px;font-size:13.5px;color:var(--muted)}
.legend span{display:inline-flex;gap:8px;align-items:center}
.steps{list-style:none;margin:24px 0 0;padding:0;display:grid;gap:12px;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));counter-reset:s}
.steps li{background:var(--surface);border:1px solid var(--line);border-radius:var(--r-lg);padding:18px;font-size:14px;line-height:1.5;counter-increment:s;color:var(--muted)}
.steps li b{color:var(--ink);font-weight:600}
.steps li:before{content:counter(s);font-family:var(--serif);font-size:30px;line-height:1;color:var(--ink);display:block;margin-bottom:10px}

/* members */
.members{display:grid;gap:18px;grid-template-columns:1fr;margin-top:28px}
@media (min-width:860px){.members{grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:28px}}
.mlist{list-style:none;margin:12px 0 0;padding:0;display:grid;gap:6px}
.mlist li{animation:rowin .45s var(--ease) both;animation-delay:calc(var(--i,0)*35ms)}
.mlist li button{width:100%;text-align:left;display:grid;grid-template-columns:auto 1fr auto;gap:12px;align-items:center;padding:10px 14px;border-radius:var(--r-md);border:1px solid var(--line);background:var(--surface);font-size:14.5px;transition:border-color .15s}
.mlist li button:hover{border-color:var(--ink)}
.mname{display:flex;flex-direction:column;line-height:1.3;min-width:0}
.mname b{font-weight:600}
.mname .muted{font-size:12.5px}
.mcount{font-size:13px;color:var(--muted);text-align:right;white-space:nowrap}
@media (max-width:420px){.mcount{white-space:normal;max-width:96px}}
.mpick{background:var(--surface);border:1px solid var(--line);border-radius:var(--r-lg);padding:20px;font-size:14.5px;color:var(--muted);align-self:start;line-height:1.55}
.mpick b{color:var(--ink)}
.mpick .chip{margin-left:6px;height:30px}
.mpick p{margin:14px 0 0}
.prof{display:flex;gap:14px;align-items:center;animation:rowin .45s var(--ease) both}
.prof>div>b{font-size:17px;font-weight:600;color:var(--ink)}
.prof .muted{font-size:13.5px;line-height:1.4;margin-top:2px}
.prof .mlinks{display:flex;gap:12px;flex-wrap:wrap;font-size:13px;margin-top:6px}
.prof .mlinks a{text-decoration:none}
.prof .mlinks a:hover{text-decoration:underline}

/* footer, toast, palette */
footer{border-top:1px solid var(--line);padding:48px 0 56px;color:var(--muted);font-size:14px;line-height:1.55}
.fgrid{display:grid;gap:28px;grid-template-columns:1fr}
@media (min-width:860px){.fgrid{grid-template-columns:1.4fr 1fr 1fr;gap:40px}}
footer h4{color:var(--ink);margin:0 0 10px}
footer ul{list-style:none;margin:0;padding:0;display:grid;gap:6px}
footer a{color:var(--ink)}
footer .brand{margin-bottom:14px}
.fineprint{font-size:12.5px;margin-top:28px;padding-top:18px;border-top:1px solid var(--line)}
/* --- changelog badge, bottom right -------------------------------------- */
.cl{position:fixed;right:18px;bottom:18px;z-index:41;display:flex;flex-direction:column;align-items:flex-end;gap:8px}
.cl[hidden]{display:none!important}
.cl-tab{display:inline-flex;align-items:center;gap:8px;height:34px;padding:0 13px;border-radius:999px;border:1px solid var(--line);background:var(--surface);box-shadow:var(--shadow-2);color:var(--ink);font:600 12.5px/1 var(--sans);cursor:pointer;transition:border-color .15s,transform .15s var(--ease)}
.cl-tab:hover{border-color:var(--line-strong);transform:translateY(-1px)}
.cl-dot{width:7px;height:7px;border-radius:50%;background:var(--accent);box-shadow:0 0 0 3px var(--accent-soft);flex:none}
.cl-v{font-variant-numeric:tabular-nums;color:var(--muted)}
.cl-w{display:none}
@media (min-width:560px){.cl-w{display:inline}}
.cl-panel{width:min(330px,calc(100vw - 36px));max-height:min(60vh,440px);overflow:auto;background:var(--surface);border:1px solid var(--line);border-radius:var(--r-lg);box-shadow:var(--shadow-3);padding:14px 16px 16px;animation:rise .28s var(--ease) both}
.cl-head{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:10px}
.cl-head b{font-size:14px}
.cl-x{border:0;background:none;font-size:20px;line-height:1;color:var(--muted);cursor:pointer;padding:0 2px}
.cl-x:hover{color:var(--ink)}
.cl-e{padding:10px 0;border-top:1px solid var(--line)}
.cl-e:first-child{border-top:0;padding-top:0}
.cl-e .d{font-size:11.5px;color:var(--muted);letter-spacing:.03em;text-transform:uppercase;font-weight:700}
.cl-e .t{font-size:13.5px;font-weight:600;margin:3px 0 6px}
.cl-e ul{margin:0;padding-left:17px}
.cl-e li{font-size:12.5px;line-height:1.55;color:var(--muted);margin:3px 0}
.totop{position:fixed;right:18px;bottom:64px;width:44px;height:44px;border-radius:50%;background:var(--surface);border:1px solid var(--line);box-shadow:var(--shadow-2);display:grid;place-items:center;z-index:40;opacity:0;transform:translateY(12px);pointer-events:none;transition:opacity .3s,transform .3s var(--ease),border-color .15s}
.totop.show{opacity:1;transform:none;pointer-events:auto}
.totop:hover{border-color:var(--ink)}
.totop svg{width:18px;height:18px;stroke:currentColor;fill:none;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
.toast{position:fixed;left:50%;bottom:22px;transform:translate(-50%,16px);opacity:0;background:var(--ink);color:var(--bg);padding:10px 16px;border-radius:999px;font-size:14px;font-weight:500;transition:opacity .25s,transform .3s var(--ease);pointer-events:none;z-index:60;box-shadow:var(--shadow-3)}
.tabbar{display:none}
@media (max-width:760px){
  .tabbar{position:fixed;left:0;right:0;bottom:0;z-index:45;display:flex;justify-content:space-around;padding:6px 4px calc(6px + env(safe-area-inset-bottom));background:color-mix(in srgb,var(--bg) 88%,transparent);backdrop-filter:saturate(1.5) blur(16px);-webkit-backdrop-filter:saturate(1.5) blur(16px);border-top:1px solid var(--hair)}
  .tabbar a{flex:1;display:flex;flex-direction:column;align-items:center;gap:3px;padding:6px 2px;text-decoration:none;color:var(--muted);font-size:11px;font-weight:600;letter-spacing:.01em;border-radius:12px}
  .tabbar a svg{width:22px;height:22px;stroke:currentColor;fill:none;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}
  .tabbar a[aria-current="page"]{color:var(--ink)}
  .tabbar a[aria-current="page"] svg{stroke:var(--accent)}
  body{padding-bottom:calc(66px + env(safe-area-inset-bottom))}
  .cl{bottom:calc(80px + env(safe-area-inset-bottom))}
  .totop{bottom:calc(126px + env(safe-area-inset-bottom))}
  .toast{bottom:calc(84px + env(safe-area-inset-bottom))}
}
.toast.show{opacity:1;transform:translate(-50%,0)}
.palette{position:fixed;inset:0;z-index:50}
.palette[hidden]{display:none!important}
.pal-back{position:absolute;inset:0;background:rgba(10,12,16,.45);backdrop-filter:blur(6px);-webkit-backdrop-filter:blur(6px)}
.pal{position:relative;width:min(640px,calc(100vw - 24px));margin:min(14vh,120px) auto 0;background:var(--surface);border:1px solid var(--line);border-radius:var(--r-lg);box-shadow:var(--shadow-3);overflow:hidden;animation:pop .2s var(--ease)}
@keyframes pop{from{opacity:0;transform:translateY(-6px) scale(.985)}to{opacity:1;transform:none}}
.pal-in{display:flex;align-items:center;gap:10px;padding:0 14px 0 16px;height:56px;border-bottom:1px solid var(--line)}
.pal-in svg{width:18px;height:18px;stroke:var(--muted);fill:none;stroke-width:2;stroke-linecap:round;flex:none}
.pal-in input{flex:1;border:0;background:transparent;font:inherit;font-size:17px;color:inherit;height:100%;min-width:0}
.pal-in input:focus{outline:none}
.pal-list{list-style:none;margin:0;padding:8px;max-height:min(58vh,440px);overflow:auto}
.pal-list li[data-i]{display:grid;grid-template-columns:auto 1fr auto;gap:12px;align-items:center;padding:10px 12px;border-radius:10px;font-size:14.5px;cursor:pointer;animation:rowin .3s var(--ease) both;animation-delay:calc(var(--i,0)*22ms)}
.pal-list li[aria-selected="true"]{background:var(--hair)}
.pal-list li .t{font-weight:500;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.pal-list li .s{font-size:12.5px;color:var(--muted);white-space:nowrap}
.pal-list .grp{padding:10px 12px 4px;font-size:12px;color:var(--muted);font-weight:600}
.pal-list .none{padding:20px 12px;color:var(--muted);font-size:14px}
.pal-foot{display:flex;gap:16px;padding:10px 16px;border-top:1px solid var(--line);font-size:12px;color:var(--muted)}
.pal-foot kbd{margin-right:4px}
/* reveal on scroll */
.rv{opacity:0;transform:translateY(22px);transition:opacity .8s var(--ease),transform .8s var(--ease);transition-delay:calc(var(--i,0)*70ms)}
.rv.in{opacity:1;transform:none}
.card.rv{transition:border-color .2s,box-shadow .3s,transform .8s var(--ease),opacity .8s var(--ease);transition-delay:calc(var(--i,0)*70ms)}
.card.rv.in{transition:border-color .2s,box-shadow .3s,transform .3s var(--ease),opacity .3s;transition-delay:0s}
html.theming,html.theming *{transition:background-color .45s,color .45s,border-color .45s,fill .45s,stroke .45s!important}
/* portraits: a clipped circle (tilts), a parallax layer (shifts), the picture (slow drift and zoom) */
.avw{position:relative;display:inline-grid;place-items:center;flex:none;width:44px;height:44px;--pc:var(--plum);isolation:isolate}
.avc{width:100%;height:100%;border-radius:50%;overflow:hidden;background:var(--line);box-shadow:0 0 0 2px var(--surface),0 0 0 3.5px var(--pc);transform:perspective(260px) rotateX(var(--rx,var(--gy,0deg))) rotateY(var(--ry,var(--gx,0deg)));transition:transform .4s var(--ease);will-change:transform;transform-style:preserve-3d}
.avz{width:100%;height:100%;display:block;transform:translate(var(--px,var(--gpx,0px)),var(--py,var(--gpy,0px)));transition:transform .4s var(--ease)}
.avw .av{width:100%;height:100%;object-fit:cover;object-position:50% 20%;display:block;transform-origin:50% 38%}
html.motion .avw.kb .av{animation:kburns var(--kbd,13s) ease-in-out infinite alternate;animation-delay:var(--kbo,0s)}
@keyframes kburns{from{transform:scale(1.03) translate(0,0)}to{transform:scale(1.18) translate(var(--kbx,-3%),var(--kby,2%))}}
.avw .av-txt{display:grid;place-items:center;background:var(--pc);color:#fff;font-weight:700;font-size:14px;width:100%;height:100%}
.avw .pb{position:absolute;right:-4px;bottom:-4px;width:18px;height:18px;border-radius:50%;background:var(--pc);color:#fff;font-size:10px;font-weight:700;display:grid;place-items:center;font-style:normal;box-shadow:0 0 0 2px var(--surface);z-index:2}
.avw.md{width:36px;height:36px}.avw.md .pb{width:16px;height:16px;font-size:9px;right:-3px;bottom:-3px}
.avw.sm{width:22px;height:22px}.avw.sm .pb{display:none}.avw.sm .avc{box-shadow:0 0 0 1.5px var(--pc)}.avw.sm .av-txt{font-size:10px}
.avw.xl{width:56px;height:56px}
.avw.xxl{width:92px;height:92px}
.avw.xxl:before{content:"";position:absolute;inset:-8px;border-radius:50%;background:conic-gradient(from 0deg,var(--pc),transparent 35%,var(--pc) 65%,transparent 100%);opacity:.6;z-index:-1}
.mp-head{display:grid;grid-template-columns:auto 1fr;gap:24px;align-items:center;margin:14px 0 18px}
.mp-name{font-family:var(--serif);font-weight:400;font-size:clamp(36px,5.4vw,60px);line-height:1.02;margin:0;letter-spacing:-.012em}
.mp-head .seat{font-size:16px;color:var(--muted);margin-top:8px}.mp-head .seat b{color:var(--ink);font-weight:600}
#pg-member .rep-top{justify-content:flex-start;padding-right:0;margin:0 0 22px}
#pg-member .know-b{background:var(--surface);border:1px solid var(--line)}
#pg-member .know-wiki{background:transparent;border-style:dashed}
.mp-grid{display:grid;gap:18px;grid-template-columns:1fr;align-items:start}
@media (min-width:980px){.mp-grid{grid-template-columns:minmax(0,1fr) minmax(0,1fr)}}
.mp-filters{display:flex;gap:6px;flex-wrap:wrap;margin:2px 0 10px}
.mvrow{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:10px;align-items:center;padding:10px 0;border-bottom:1px solid var(--line);color:var(--ink);font-size:14px;line-height:1.4}
.mvrow:last-child{border-bottom:0}
.mv-main{text-decoration:none;color:inherit}.mv-main:hover b{text-decoration:underline}
.mv-side{display:flex;gap:8px;align-items:center;flex-wrap:wrap;justify-content:flex-end}
.mv-bill{font-size:12.5px;color:var(--muted);text-decoration:underline;text-underline-offset:2px;white-space:nowrap}.mv-bill:hover{color:var(--ink)}
@media (max-width:560px){.mvrow{grid-template-columns:1fr}.mv-side{justify-content:flex-start}}
.know-breaks{margin:10px 0 2px;height:32px}
/* a table a reader can sort: click a column, shift-click another to sort within it */
.gt-wrap{overflow-x:auto;border:1px solid var(--line);border-radius:var(--r-md);background:var(--surface)}
.gt{width:100%;border-collapse:collapse;font-size:13.5px;line-height:1.35}
.gt th{position:sticky;top:0;z-index:1;background:var(--surface);text-align:left;padding:0;border-bottom:1px solid var(--line-strong);white-space:nowrap}
.gt th button{all:unset;box-sizing:border-box;display:flex;align-items:center;gap:6px;width:100%;padding:10px 12px;font-size:12px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;color:var(--muted);cursor:pointer}
.gt th button:hover,.gt th[aria-sort="ascending"] button,.gt th[aria-sort="descending"] button{color:var(--ink)}
.gt th button:focus-visible{outline:2px solid var(--accent);outline-offset:-2px}
.gt th.num button{justify-content:flex-end}
.gt .srt{display:inline-flex;align-items:center;gap:1px;font-size:10px;color:var(--accent-ink);min-width:16px}
.gt .srt sup{font-size:9px;font-weight:700}
.gt td{padding:9px 12px;border-bottom:1px solid var(--line);vertical-align:top}
.gt tr:last-child td{border-bottom:0}
.gt td.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.gt tbody tr:hover,.gt tbody tr.hot{background:var(--hair)}
.gt a{color:inherit;text-underline-offset:2px}
.gt .pty{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:7px;vertical-align:baseline}
/* on a narrow screen the table scrolls sideways; the first column stays put so a row never loses its name */
@media (max-width:760px){.gt th:first-child,.gt td:first-child{position:sticky;left:0;z-index:2;background:var(--surface);box-shadow:1px 0 0 var(--line);max-width:46vw}.gt th:first-child{z-index:3}}
.gt-tools{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin:12px 0}
.gt-tools .grow{flex:1;min-width:180px}
.gt-tools input[type=search]{height:34px;width:100%;border:1px solid var(--line);border-radius:999px;background:var(--surface);color:var(--ink);padding:0 14px;font:inherit;font-size:13.5px}
.gt-foot{display:flex;gap:10px;flex-wrap:wrap;align-items:center;justify-content:space-between;margin-top:10px;font-size:12.5px;color:var(--muted)}
.gt-foot .chip{height:30px}
.chip[aria-pressed="true"].gt-multi{background:var(--ink);color:var(--bg);border-color:var(--ink)}
.partyline{margin-top:34px}
.partyline h3{font-family:var(--serif);font-weight:400;font-size:26px;margin:0 0 8px;display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.partyline .lead{color:var(--muted);max-width:70ch;margin:0 0 4px;font-size:15px}
/* decided by a handful */
.closest{padding:26px 0 8px}
.closelist{list-style:none;margin:22px 0 0;padding:0;display:grid;gap:10px;grid-template-columns:1fr}
@media (min-width:860px){.closelist{grid-template-columns:1fr 1fr}}
.closeitem{display:grid;grid-template-columns:78px minmax(0,1fr);gap:14px;align-items:center;background:var(--surface);border:1px solid var(--line);border-radius:var(--r-lg);padding:14px 16px;transition:border-color .15s,transform .15s var(--ease)}
.closeitem:hover{border-color:var(--line-strong)}
.closeitem .by{display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;border-right:1px solid var(--line);padding-right:12px;min-height:64px}
.closeitem .by b{font-family:var(--serif);font-weight:400;font-size:40px;line-height:1}
.closeitem .by span{font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);margin-top:4px}
.closeitem .what{font-size:14.5px;line-height:1.4}
.closeitem .what a.main{color:var(--ink);text-decoration:none}.closeitem .what a.main:hover b{text-decoration:underline}
.closeitem .what .muted{display:block;font-size:12.5px;margin-top:3px}
.closeitem .what .how{display:block;font-size:13px;margin-top:3px}
.closeitem .what .how.won{color:var(--accent-ink)}.closeitem .what .how.lost{color:var(--bad-ink)}
.mv-main .muted{display:block;font-size:12.5px}
.mv-flag{font-size:11.5px;font-weight:600;color:var(--amber-ink);background:var(--amber-soft);padding:2px 8px;border-radius:999px;white-space:nowrap}
#mpmore{margin-top:10px}
@media (max-width:560px){.mp-head{gap:16px}.avw.xxl{width:72px;height:72px}}
.avw.xl:before{content:"";position:absolute;inset:-7px;border-radius:50%;background:conic-gradient(from 0deg,var(--pc),transparent 35%,var(--pc) 65%,transparent 100%);opacity:.6;z-index:-1}
html.motion .avw.xl:before{animation:spin 7s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
/* the motion switch */
.mtog{display:inline-flex;align-items:center;gap:8px;height:38px;padding:0 12px 0 8px;border-radius:999px;border:1px solid var(--line);background:var(--surface);color:var(--muted);font-size:13.5px;font-weight:500;transition:border-color .15s,color .15s}
.mtog:hover{border-color:var(--line-strong);color:var(--ink)}
.mtog .sw{position:relative;width:30px;height:18px;border-radius:999px;background:var(--line-strong);transition:background .25s;flex:none}
.mtog .sw i{position:absolute;top:2px;left:2px;width:14px;height:14px;border-radius:50%;background:#fff;transition:transform .25s var(--ease);box-shadow:0 1px 2px rgba(0,0,0,.3)}
.mtog[aria-pressed="true"] .sw{background:var(--accent)}
.mtog[aria-pressed="true"] .sw i{transform:translateX(12px)}
@media (max-width:1000px){.mtog .lab{display:none}.mtog{padding:0 8px}}
@media (max-width:560px){.top .wrap{gap:6px;padding-left:14px;padding-right:14px}.tools{gap:5px}.top .brand{font-size:15px;gap:7px}.top .brand .mark{width:24px;height:24px}.top .iconbtn,.top .kbtn{width:34px;height:34px}.top .mtog{height:34px;padding:0 6px}}
@media (max-width:340px){.top .brand .wm{display:none}}
/* static mode: everything holds still */
html.calm *,html.calm *:before,html.calm *:after{animation-duration:.001s!important;transition-duration:.001s!important;transition-delay:0s!important}
html.calm{scroll-behavior:auto}
html.calm .rv{opacity:1;transform:none}
html.calm .mtog .sw,html.calm .mtog .sw i{transition-duration:.25s!important}
@media (prefers-reduced-motion: reduce){
  *,*:before,*:after{animation-duration:.001s!important;transition-duration:.001s!important;transition-delay:0s!important;scroll-behavior:auto!important}
  .rv{opacity:1;transform:none}
}
</style>
</head>
<body>
<div style="background:#7c2d12;color:#fff;padding:.5rem 1rem;font:600 13px/1.4 system-ui,sans-serif;text-align:center;letter-spacing:.02em">
  WORK IN PROGRESS &mdash; this is a draft for feedback, not the real site.
  <a href="https://thecivicarchive.github.io/" style="color:#fed7aa;text-decoration:underline">Go to the live site</a>
</div>
<a class="skip" href="#bills">Skip to bills</a>
<header class="top">
  <div class="wrap">
    <a class="brand" href="#top" aria-label="The Civic Archive, home"><svg class="mark" viewBox="0 0 28 28" aria-hidden="true"><path d="M14 3v2.5"/><path d="M6.5 13.5a7.5 7.5 0 0 1 15 0"/><path d="M4 13.5h20"/><path d="M6.5 16.5v6M11.5 16.5v6M16.5 16.5v6M21.5 16.5v6"/><path d="M3 24h22"/></svg><span class="wm"><b>T</b>he <b>C</b>ivic <b>A</b>rchive</span></a>
    <nav class="nav" aria-label="Sections">
      <a href="#home" data-go="home">Home</a><a href="#bills" data-go="bills">Bills</a><a href="#map" data-go="map">Vote map</a><a href="#how" data-go="how">How ratings work</a><a href="#members" data-go="members">Your members</a>
    </nav>
    <div class="tools">
      <button class="kbtn" id="palettebtn" aria-label="Search bills and members"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/></svg><span>Search</span><kbd>⌘K</kbd></button>
      <button class="mtog" id="motion" aria-pressed="true" title="Living portraits and page motion: on or off"><span class="sw" aria-hidden="true"><i></i></span><span class="lab">Motion</span></button>
      <button class="iconbtn" id="helpbtn" aria-label="How to read this site" title="How to read this site"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M9.2 9.3a2.9 2.9 0 0 1 5.6 1c0 1.9-2.8 2.4-2.8 4"/><path d="M12 17.6h.01"/></svg></button>
      <button class="iconbtn" id="theme" aria-label="Switch between light and dark" title="Light / dark">
        <svg class="moon" viewBox="0 0 24 24" aria-hidden="true"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>
        <svg class="sun" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>
      </button>
    </div>
  </div>
</header>

<div class="page" id="pg-home" data-page="home">
<div class="ticker" id="ticker" hidden>
  <div class="ticker-label"><i aria-hidden="true"></i>Latest votes</div>
  <div class="ticker-view" role="region" aria-label="The latest recorded votes"><div class="ticker-track" id="tickertrack"></div></div>
</div>
<section class="hero" id="top">
  <canvas id="field" aria-hidden="true"></canvas>
  <p class="wx" id="wx" hidden></p>
  <div class="wrap">
    <aside class="kpirail" aria-label="Where this Congress stands">
      <div class="kpihead"><span class="tag fact">Fact</span><span>Where the 119th Congress stands</span></div>
      <dl class="kpis">
        <div><dd data-count="__MEASURES__">0</dd><dt>bills introduced</dt></div>
        <div><dd data-count="__CBILL__">0</dd><dt>sitting in committee</dt></div>
        <div><dd data-count="__CHALF__">0</dd><dt>passed one chamber</dt></div>
        <div><dd data-count="__CWAIT__">0</dd><dt>awaiting a signature</dt></div>
        <div class="good"><dd data-count="__LAWS__">0</dd><dt>became law</dt></div>
        <div class="bad"><dd data-count="__CFAIL__">0</dd><dt>failed or vetoed</dt></div>
      </dl>
      <p class="kpifoot">Counted from the congressional record.<br>Updated __GENERATED__.</p>
    </aside>
    <div class="hero-copy">
      <h1 aria-label="Congress, in plain words."><span class="h1a">Congress,</span> <span class="h1b" id="h1rot">in plain words.</span></h1>
      <p class="lede">Thousands of bills move through Congress every year. Almost nothing reaches you unfiltered &mdash; it arrives as a press release, a cable segment, a fundraising email.</p>
      <p class="lede">This place skips all of that. Every bill and every recorded vote, straight from the official record, written so you can follow it &mdash; and decide for yourself what you think.</p>
      <div class="cta"><a class="btn primary" href="#yours">How did my members vote?</a><a class="btn" href="#nowmoving">See what's moving</a><a class="btn" href="#bills">Browse every bill</a></div>
      <p class="nosell">No ads. No donors. No take to sell you.</p>
      <div class="spotlight" id="heropanel" aria-live="polite">
        <div class="spot-head"><b>A rated bill</b><span>Facts from the record, ratings with their evidence</span></div>
        <div class="fade" id="herobody"></div>
        <div class="pfoot">
          <div class="dots" id="herodots" role="tablist" aria-label="Featured bills"></div>
          <button class="more" id="herogo">Open this bill <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 9l6 6 6-6"/></svg></button>
        </div>
      </div>
    </div>
  </div>
</section>

<section class="yours" id="yours">
  <div class="wrap">
    <div class="sechead rv">
      <div><h2>How did your members vote?</h2><p>Pick your state to see how its senators and representatives voted on the latest roll calls, member by member, from the official record. Share any one of them.</p></div>
    </div>
    <div class="yours-bar rv" style="--i:1">
      <label class="selwrap"><span>State</span><select id="ystate" aria-label="Your state"></select><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 9l6 6 6-6"/></svg></label>
      <button class="btn shimmer" id="yloc" type="button">Use my location</button>
      <span class="muted ynote" id="ynote"></span>
    </div>
    <div class="yours-list" id="ylist" hidden></div>
  </div>
</section>

<section class="closest" id="closest" hidden>
  <div class="wrap">
    <div class="sechead rv">
      <div><h2>Decided by a handful</h2><p>The recorded votes of this Congress that came down to the fewest votes. Open one to see how every member voted, state by state or seat by seat.</p></div>
    </div>
    <ol class="closelist" id="closelist"></ol>
    <p class="srcnote"><span class="tag fact">Fact</span> From the official tallies. Most votes need a majority. A few need more, and the record says so: two-thirds to pass a bill under suspension of the rules or to override a veto, sixty in the Senate to end debate. Each line counts how far the yes votes landed from what that vote needed.</p>
  </div>
</section>

<section class="picks" id="nowmoving">
  <div class="wrap">
    <div class="sechead">
      <div>
        <h2>Start here</h2>
        <p>Ten bills worth knowing about &mdash; five still in play, five already law. Tap any one to see who it helps, who backed it and how your member voted.</p>
      </div>
    </div>
    <div class="pickcols">
      <div class="pickcol">
        <div class="pickhead">
          <h3><span class="dot live" aria-hidden="true"></span>Moving right now</h3>
          <p>Active in the last 90 days and not yet finished.</p>
        </div>
        <ol class="picklist" id="picklive"></ol>
      </div>
      <div class="pickcol">
        <div class="pickhead">
          <h3><span class="dot done" aria-hidden="true"></span>Already law</h3>
          <p>Signed this Congress. These are in force now.</p>
        </div>
        <ol class="picklist" id="picklaws"></ol>
      </div>
    </div>
    <p class="srcnote"><span class="tag analysis">Analysis</span> Our ordering, not an official ranking. A bill scores 3 if the Congressional Budget Office costed it, 2 if a committee filed a written report, and 1 for each recorded floor vote. Ties go to the bill with more cosponsors. Every input is a fact from the record; the weighting is a judgment, so we show it.</p>
  </div>
</section>
</div><!-- /home -->

<div class="page" id="pg-bills" data-page="bills" hidden>
<section id="bills">
  <div class="wrap">
    <div class="sechead rv">
      <div><h2>Bills</h2><p>Every measure on record, newest action first. Open one for who it helps, when it starts, the votes, and the reasoning behind each rating.</p></div>
    </div>
  </div>
  <div class="controls">
    <div class="wrap">
      <div class="bar">
        <label class="search"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/></svg>
          <input id="q" type="search" placeholder="Search by number, title, topic or member" autocomplete="off" aria-label="Search bills"><kbd aria-hidden="true">/</kbd></label>
      </div>
      <div class="chips" id="chips" role="group" aria-label="Filters">
        <button class="chip" data-f="all" aria-pressed="true">All</button>
        <button class="chip" data-f="rated">Rated</button>
        <button class="chip" data-f="law">Became law</button>
        <button class="chip" data-f="pending">Still moving</button>
        <button class="chip" data-f="Tax">Tax</button>
        <button class="chip" data-f="Employment">Work and pay</button>
        <button class="chip" data-f="Disability">Disability</button>
        <button class="chip" data-f="119">2025 and later</button>
      </div>
    </div>
  </div>
  <div class="wrap">
    <div class="row"><div class="muted" id="count" aria-live="polite"></div><label class="selwrap compact"><span>Sort</span><select id="sort"><option value="recent">Latest action</option><option value="rated">Rated first</option><option value="number">Bill number</option></select><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 9l6 6 6-6"/></svg></label></div>
    <div class="grid" id="grid"></div>
  </div>
</section>
</div><!-- /bills -->

<main>
  <div class="page" id="pg-map" data-page="map" hidden>
  <section class="theater block" id="map">
    <div class="wrap">
      <div class="sechead rv">
        <div><h2>Who voted how, state by state</h2><p>Pick a recorded vote. Each state is colored by the party of its members and how they voted: solid means yes, striped means no, gray means not voting. A split delegation shows the split. Tap a state for the names.</p></div>
      </div>
      <div class="theater-grid">
        <div class="stage rv">
          <div class="mtip" id="mtip" role="tooltip"></div>
          <div class="mapfilter" id="mapfilter" hidden></div>
          <div class="votebar">
            <button class="iconbtn" id="vprev" aria-label="Newer vote"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M15 6l-6 6 6 6"/></svg></button>
            <label class="selwrap"><span class="sr-only">Vote</span><select id="vsel" aria-label="Choose a recorded vote"></select><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 9l6 6 6-6"/></svg></label>
            <button class="iconbtn" id="vnext" aria-label="Older vote"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 6l6 6-6 6"/></svg></button>
          </div>
          <div class="mapsub" id="mapsub"></div>
          <div class="viewsw" id="viewsw" role="group" aria-label="Two ways to see this vote" hidden><button class="chip" type="button" data-view="map" aria-pressed="true">State map</button><button class="chip" type="button" data-view="chamber" aria-pressed="false">Chamber floor, in 3D</button></div>
          <div class="mapframe">
            <button class="btn mapback" id="mapback" hidden><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M15 6l-6 6 6 6"/></svg>All states</button>
            <svg class="usmap" id="usmap" viewBox="0 0 975 610" role="img" aria-label="Map of the United States colored by how each state's members voted"></svg>
            <canvas class="chamber" id="chamber" tabindex="0" role="img" aria-label="The chamber floor: one seat for every member who took part in this vote" hidden></canvas>
            <div class="ch-tip" id="chtip" role="tooltip"></div>
            <div class="ch-info" id="chinfo" aria-live="polite" hidden></div>
          </div>
          <div class="legend2">
            <span><i class="sw" style="background:var(--rep)"></i> Republican, yes</span><span><i class="sw" style="background:repeating-linear-gradient(45deg,var(--rep) 0 3px,transparent 3px 6px)"></i> Republican, no</span>
            <span><i class="sw" style="background:var(--dem)"></i> Democrat, yes</span><span><i class="sw" style="background:repeating-linear-gradient(45deg,var(--dem) 0 3px,transparent 3px 6px)"></i> Democrat, no</span>
            <span><i class="sw" style="background:var(--plum)"></i> Independent</span><span><i class="sw" style="background:var(--line-strong)"></i> Not voting, or no member</span>
          </div>
        </div>
        <aside class="mapside rv" id="mapside" aria-live="polite" style="--i:2"><span class="muted">Tap a state to zoom in. On a House vote you'll see its districts; tap one for the representative.</span></aside>
      </div>
      <p class="note" id="mapnote"></p>
    </div>
  </section>
  </div><!-- /map -->

  <div class="page" id="pg-how" data-page="how" hidden>
  <section class="block" id="how">
    <div class="wrap">
      <div class="sechead rv">
        <div><h2>How the ratings work</h2><p>Facts come from the official record and are never edited. Ratings are judgments, and every one shows its evidence grade, its reasoning and the rubric version it was made under. The rater never sees who sponsored a bill or how the parties voted.</p></div>
      </div>
      <div class="how">
        <article class="rv" style="--i:0">
          <h3>Who gains, by income</h3>
          <div class="axes"><div class="axis"><div class="gauge"><span class="range" style="--lo:48%;--w:30%"></span><span class="mid"></span><span class="dot" style="--pos:66%"></span></div>
            <div class="ends"><span>Lower-income</span><span>Broad-based</span><span>High-income</span></div></div></div>
          <p>The slope of the change in after-tax income across income groups, from official analyses when they exist. A bar shows the range for a bill that helps one group and costs another; it never averages them away.</p>
        </article>
        <article class="rv" style="--i:1">
          <h3>Who backed it</h3>
          <div class="axes"><div class="axis"><div class="gauge backing"><span class="mid"></span><span class="dot" style="--pos:72%"></span></div>
            <div class="ends"><span>Democrats only</span><span>Bipartisan</span><span>Republicans only</span></div></div></div>
          <p>Measured, not guessed: each party's yes-rate on the recorded passage votes. The label tells you how much of the other party came along.</p>
        </article>
        <article class="rv" style="--i:2">
          <h3>Households vs. businesses</h3>
          <div class="axes"><div class="quad"><svg viewBox="0 0 64 64" aria-hidden="true"><rect class="q" x="1" y="1" width="62" height="62" rx="6"/><path class="q" d="M32 3v58M3 32h58"/><circle class="pt" cx="32" cy="32" r="6" style="--dx:-3px;--dy:-20px"/></svg><small><b>Right</b> helps households<br><b>Up</b> helps businesses</small></div></div>
          <p>Two separate scores, because a bill can help both. Corporate tax changes count 25 percent to workers and 75 percent to owners, the official convention.</p>
        </article>
      </div>
      <div class="legend rv"><span><i class="grade" data-g="A">A</i> official analysis (CBO, JCT)</span><span><i class="grade" data-g="B">B</i> independent models</span><span><i class="grade" data-g="C">C</i> reading of the text</span><span><i class="grade" data-g="N">N</i> not assessable</span></div>
      <ol class="steps">
        <li class="rv" style="--i:0"><b>Official record.</b> Every bill, vote, cosponsor and summary is pulled from the Library of Congress feed each morning.</li>
        <li class="rv" style="--i:1"><b>Blinded rating.</b> A model applies the published rubric to the summary and text, with sponsor and party removed.</li>
        <li class="rv" style="--i:2"><b>Human review.</b> Every law and every bill with a floor vote is checked by a person; disagreements are published.</li>
        <li class="rv" style="--i:3"><b>Versioned.</b> A re-score never erases the old rating. You can always see what changed and why.</li>
      </ol>
    </div>
  </section>
  </div><!-- /how -->

  <div class="page" id="pg-members" data-page="members" hidden>
  <section class="block" id="members">
    <div class="wrap">
      <div class="sechead rv">
        <div><h2>Your members</h2><p>Find a senator or representative and get to know them: how long they have served, how they vote, what they work on, and every recorded vote they have cast.</p></div>
      </div>
      <div class="members">
        <div class="rv">
          <label class="search"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/></svg>
            <input id="mq" type="search" placeholder="Name or state, for example Klobuchar or MN" autocomplete="off" aria-label="Search members"></label>
          <ul class="mlist" id="mlist"></ul>
        </div>
        <div id="mpick" class="mpick rv" style="--i:1">Pick a member to filter the bill list above.</div>
      </div>
      <div class="partyline rv" style="--i:2" id="partyline">
        <h3><span class="tag analysis">Analysis</span>With their party, and against it</h3>
        <p class="lead">Every sitting member, counted from this Congress's recorded votes. Tap a number under "Broke with party" to see those votes, then open any one to see how everyone else voted, or open the bill itself.</p>
        <div class="gt-tools" id="pltools">
          <button class="chip" type="button" data-ch="" aria-pressed="true">Both chambers</button><button class="chip" type="button" data-ch="House" aria-pressed="false">House</button><button class="chip" type="button" data-ch="Senate" aria-pressed="false">Senate</button>
          <button class="chip" type="button" data-pt="" aria-pressed="true">All parties</button><button class="chip" type="button" data-pt="D" aria-pressed="false">Democrats</button><button class="chip" type="button" data-pt="R" aria-pressed="false">Republicans</button>
          <label class="grow"><span class="sr-only">Filter by name or state</span><input id="plq" type="search" placeholder="Filter by name or state" autocomplete="off"></label>
        </div>
        <div id="pltable"></div>
        <p class="know-rule">How this is worked out: a vote counts as a party split when most Democrats voted one way and most Republicans the other. "Broke with party" counts the split votes on which a member voted against most of their own party. Party is the one recorded on each roll call. Only this Congress's recorded votes are counted, and only those this site holds member by member. Independents have no party line to measure against.</p>
      </div>
    </div>
  </section>
  </div><!-- /members -->

  <div class="page" id="pg-member" data-page="member" hidden>
  <section class="block" id="member">
    <div class="wrap"><div id="mpage"></div></div>
  </section>
  </div><!-- /member -->
</main>

<footer>
  <div class="wrap">
    <div class="fgrid">
      <div class="rv">
        <a class="brand" href="#top"><svg class="mark" viewBox="0 0 28 28" aria-hidden="true"><path d="M14 3v2.5"/><path d="M6.5 13.5a7.5 7.5 0 0 1 15 0"/><path d="M4 13.5h20"/><path d="M6.5 16.5v6M11.5 16.5v6M16.5 16.5v6M21.5 16.5v6"/><path d="M3 24h22"/></svg><span class="wm"><b>T</b>he <b>C</b>ivic <b>A</b>rchive</span></a>
        <p>__FOOTNOTE__</p>
        <p class="offline" id="offline" hidden><a href="offline.html" download>Download the offline copy</a>: the whole site in one file, for reading without a connection.</p>
      </div>
      <div class="rv" style="--i:1">
        <h4>Sources</h4>
        <ul>
          <li><a href="https://www.govinfo.gov/bulkdata/BILLSTATUS" target="_blank" rel="noopener">GovInfo Bill Status</a>, GPO and the Library of Congress</li>
          <li><a href="https://clerk.house.gov/Votes" target="_blank" rel="noopener">House Clerk roll calls</a></li>
          <li><a href="https://www.senate.gov/legislative/votes_new.htm" target="_blank" rel="noopener">Senate roll-call votes</a></li>
          <li><a href="https://www.cbo.gov/" target="_blank" rel="noopener">CBO</a> and <a href="https://www.jct.gov/" target="_blank" rel="noopener">JCT</a> analyses</li>
        </ul>
      </div>
      <div class="rv" style="--i:2">
        <h4>Method</h4>
        <p>Ratings are judgments and show their evidence, their confidence and the rubric version they were made under. The factual record is never edited. Members are shown with the party they held at the time of each vote.</p>
      </div>
    </div>
    <p class="fineprint">Motion switch (top bar): on, portraits drift and tilt toward your pointer or your phone's tilt and the page animates; off, everything holds still. Keyboard: press / to search bills, ⌘K or Ctrl+K to search everything, Esc to close.</p>
  </div>
</footer>
<nav class="tabbar" aria-label="Pages">
  <a href="#home" data-go="home"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 11l9-8 9 8"/><path d="M5 10v10h14V10"/></svg><span>Home</span></a>
  <a href="#bills" data-go="bills"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 4h14v16H5z"/><path d="M8 9h8M8 13h8M8 17h5"/></svg><span>Bills</span></a>
  <a href="#map" data-go="map"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 6l6-2 6 2 6-2v14l-6 2-6-2-6 2z"/><path d="M9 4v14M15 6v14"/></svg><span>Votes</span></a>
  <a href="#members" data-go="members"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0"/><circle cx="17" cy="9" r="2.5"/><path d="M15.5 14.5a5 5 0 0 1 6 5"/></svg><span>Members</span></a>
  <a href="#how" data-go="how"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M9.2 9.3a2.9 2.9 0 0 1 5.6 1c0 1.9-2.8 2.4-2.8 4"/><path d="M12 17.6h.01"/></svg><span>Ratings</span></a>
</nav>
<div class="toast" id="toast" role="status"></div>
<button class="totop" id="totop" aria-label="Back to top"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 19V5M5 12l7-7 7 7"/></svg></button>

<div class="hmodal" id="help" hidden>
  <div class="hm-back" id="helpback"></div>
  <div class="hm-card" role="dialog" aria-modal="true" aria-labelledby="helptitle">
    <button class="hm-x" id="helpx" aria-label="Close">&times;</button>
    <h2 id="helptitle">How to read this site</h2>
    <p class="hm-lede">Three kinds of claim appear here, and they are never mixed. Every one is labelled wherever it appears &mdash; so you always know whether you are looking at the record, at reasoning, or at a judgment.</p>
    <div class="hm-grid">
      <div class="labelcard">
        <span class="tag fact">Fact</span>
        <h3>From the record</h3>
        <p>Bill text, sponsors, dates, committee actions, and every recorded vote member by member. Taken straight from GovInfo, the House Clerk and the Senate. If we have it wrong, the official source will say so &mdash; and we link to it every time.</p>
      </div>
      <div class="labelcard">
        <span class="tag analysis">Analysis</span>
        <h3>Derived, and shown</h3>
        <p>Plain-language summaries, the ordering of lists like &ldquo;Start here&rdquo;, and party-backing figures worked out from roll calls. Built from facts by a stated rule, and the rule is always on the page so you can check it yourself.</p>
      </div>
      <div class="labelcard">
        <span class="tag opinion">Opinion</span>
        <h3>A judgment, labelled</h3>
        <p>Ratings of who a bill helps and by how much. These are arguments, not measurements. Each one carries its evidence and its reasoning, and anything scored by machine says so until a person has reviewed it.</p>
      </div>
    </div>
    <p class="hm-foot">Everything factual here comes from public records published by the United States government. Nothing on this site is edited by hand.</p>
  </div>
</div>

<div class="cl" id="cl" hidden>
  <button class="cl-tab" id="cltab" aria-expanded="false" aria-controls="clpanel">
    <span class="cl-dot" aria-hidden="true"></span><span class="cl-v" id="clv">v1</span><span class="cl-w">What&rsquo;s new</span>
  </button>
  <div class="cl-panel" id="clpanel" hidden>
    <div class="cl-head"><b>What&rsquo;s changed</b><button class="cl-x" id="clx" aria-label="Close">&times;</button></div>
    <div class="cl-body" id="clbody"></div>
  </div>
</div>

<div class="repmodal" id="repmodal" hidden>
  <div class="rep-back"></div>
  <div class="rep" role="dialog" aria-modal="true" aria-label="Member of Congress">
    <button class="iconbtn rep-x" id="repclose" aria-label="Close"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg></button>
    <div id="repbody"></div>
  </div>
</div>

<div class="palette" id="palette" hidden>
  <div class="pal-back"></div>
  <div class="pal" role="dialog" aria-modal="true" aria-label="Search bills and members">
    <label class="pal-in"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/></svg><input id="palq" type="text" placeholder="Search bills and members" autocomplete="off" spellcheck="false"><kbd>esc</kbd></label>
    <ul class="pal-list" id="pallist" role="listbox" aria-label="Results"></ul>
    <div class="pal-foot"><span><kbd>↑</kbd><kbd>↓</kbd> move</span><span><kbd>↵</kbd> open</span></div>
  </div>
</div>

<script>
const BOOT = __BOOT__;
/* Data arrives when a page needs it. `need(name)` fetches data/<name>.json once
   and caches the promise; in the one-file archive the same bundles are inlined
   under BOOT.inline, so nothing else on the page knows the difference. */
const DATA = {bills: [], members: [], legislators: {}, vote_meta: [], mv: {}, states: {}, lite: null};
const PHOTO = new Set(BOOT.photo_ids || []);
const DATA_V = encodeURIComponent(BOOT.version || "0");
const loads = {};
let MEMBER = {}, byKey = {}, MEMBERS_READY = false, CATALOG_READY = false;
const VOTE_IDS = new Set();
function need(name){
  if (loads[name]) return loads[name];
  if (BOOT.inline) return loads[name] = Promise.resolve(BOOT.inline[name]);
  return loads[name] = fetch(`data/${name}.json?v=${DATA_V}`).then(r => { if (!r.ok) throw new Error(name + " " + r.status); return r.json(); })
    .catch(e => { delete loads[name]; throw e; });
}
function needBill(b){
  if (!b.trim) return Promise.resolve(b);
  if (b._detail) return b._detail;
  return b._detail = fetch(`data/bill/${encodeURIComponent(b.key)}.json?v=${DATA_V}`).then(r => { if (!r.ok) throw new Error(r.status); return r.json(); })
    .then(d => { Object.assign(b, d); delete b.trim; b._hay = undefined; return b; }).catch(e => { delete b._detail; throw e; });
}
function needMember(id){
  if (BOOT.inline) return Promise.resolve((BOOT.inline.profiles || {})[id] || {});
  const k = "_m_" + id; if (loads[k]) return loads[k];
  return loads[k] = fetch(`data/member/${encodeURIComponent(id)}.json?v=${DATA_V}`).then(r => r.ok ? r.json() : {}).catch(e => { delete loads[k]; throw e; });
}
const $ = (s, r=document) => r.querySelector(s);
const $$ = (s, r=document) => [...r.querySelectorAll(s)];
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const fmtDate = d => d ? new Date(d + "T12:00:00").toLocaleDateString("en-US", {year:"numeric", month:"short", day:"numeric"}) : "";
const signed = n => (n == null ? "n/a" : (n > 0 ? "+" : "") + Math.round(n));
const pct = v => ((Math.max(-100, Math.min(100, v)) + 100) / 2) + "%";

/* ---------- data: expand compact rows, derive Congress.gov links ---------- */
const PC_TYPES = {hr: ["H.R.", "house-bill", "House", "Bill"], s: ["S.", "senate-bill", "Senate", "Bill"],
  hjres: ["H.J.Res.", "house-joint-resolution", "House", "Joint resolution"], sjres: ["S.J.Res.", "senate-joint-resolution", "Senate", "Joint resolution"],
  hconres: ["H.Con.Res.", "house-concurrent-resolution", "House", "Concurrent resolution"], sconres: ["S.Con.Res.", "senate-concurrent-resolution", "Senate", "Concurrent resolution"],
  hres: ["H.Res.", "house-resolution", "House", "Simple resolution"], sres: ["S.Res.", "senate-resolution", "Senate", "Simple resolution"]};
const pcOrdinal = n => n + ((n % 100 >= 11 && n % 100 <= 13) ? "th" : ({1: "st", 2: "nd", 3: "rd"}[n % 10] || "th"));
function membersReady(){
  if (loads._members) return loads._members;
  return loads._members = need("members").then(M => {
    DATA.members = M.members || []; DATA.legislators = M.legislators || {};
    MEMBER = Object.fromEntries(DATA.members.map(m => [m.id, m]));
    DATA.members.forEach(m => { let acc = 0; m.bills = (m.bd || []).map(d => (acc += d)); });
    MEMBERS_READY = true;
  }).catch(e => { delete loads._members; throw e; });
}
function catalogReady(){
  if (loads._catalog) return loads._catalog;
  return loads._catalog = Promise.all([membersReady(), need("bills-list"), need("lite")]).then(([, B, L]) => {
    DATA.bills = B.bills || [];
    if (L && L.rows) { const D = L.dict;
      for (const r of L.rows) {
        const [key, title, sp, ct, cp, bip, pol, subj, stc, intro, lad, la, lens, summ, cmt] = r;
        const k = key.match(/^([a-z]+)(\d+)-(\d+)$/) || [key, "", "", "0"], T = PC_TYPES[k[1]] || [k[1].toUpperCase(), "", "", "Bill"], s = MEMBER[sp];
        DATA.bills.push({key, id: `${T[0]} ${k[2]}`, congress: Number(k[3]), title, short_title: "", kind: T[3], introduced: intro, origin: T[2],
          sponsor: s ? {id: sp, name: s.name, party: s.party, state: s.state} : null, cosponsors: {total: ct, by_party: cp}, bipartisan: !!bip,
          policy_area: D.policy[pol] || "", subjects: subj.map(i => D.subject[i]), committees: D.committee[cmt] || "", committee_votes: "",
          status: D.status[stc] || "", outcome: "Pending", law: "", law_kind: "", latest_action_date: lad, latest_action: D.action[la] || "",
          lens: lens.map(i => D.lens[i]), votes: [], summary: summ, summary_desc: "", summary_date: "", related_enacted: "",
          links: {}, ratings: null, review: "", lite: true});
      }
    }
    DATA.bills.forEach((b, i) => {
      b._i = i;
      const k = b.key.match(/^([a-z]+)(\d+)-(\d+)$/), T = k && PC_TYPES[k[1]];
      const own = Object.fromEntries(Object.entries(b.links || {}).filter(([, v]) => v));
      if (T) { const page = `https://www.congress.gov/bill/${pcOrdinal(Number(k[3]))}-congress/${T[1]}/${k[2]}`;
        b.links = Object.assign({page, text: page + "/text", actions: page + "/all-actions", cosponsors: page + "/cosponsors", committees: page + "/committees"}, own); }
      else b.links = own;
    });
    byKey = Object.fromEntries(DATA.bills.map(b => [b.key, b]));
    CATALOG_READY = true;
  }).catch(e => { delete loads._catalog; throw e; });
}
const TYPE_ORDER = {hr: 0, s: 1, hjres: 2, sjres: 3, hconres: 4, sconres: 5, hres: 6, sres: 7};
const keyParts = key => { const m = key.match(/^([a-z]+)(\d+)-(\d+)$/); return m ? [+m[3], TYPE_ORDER[m[1]] ?? 9, +m[2]] : [0, 9, 0]; };
const isRated = b => !!(b.ratings && (b.ratings.income || b.ratings.households_business || b.ratings.plain_language || b.ratings.timing || b.ratings.rights));

/* ---------- theme ---------- */
(function(){
  /* Dark by default; a reader's choice, once made, wins. The same line runs in
     the head before anything paints, so there is no flash of the other theme. */
  let saved = null; try { saved = localStorage.getItem("theme"); } catch(e) {}
  document.documentElement.dataset.theme = saved || "dark";
  const tc = $('meta[name="theme-color"]');
  const syncColor = () => { if (tc) tc.content = document.documentElement.dataset.theme === "dark" ? "#0C0E12" : "#F5F5F2"; };
  syncColor();
  $("#theme").addEventListener("click", () => {
    const dark = document.documentElement.dataset.theme === "dark" || (!document.documentElement.dataset.theme && matchMedia("(prefers-color-scheme: dark)").matches);
    const next = dark ? "light" : "dark";
    document.documentElement.classList.add("theming"); setTimeout(() => document.documentElement.classList.remove("theming"), 520);
    document.documentElement.dataset.theme = next; syncColor();
    try { localStorage.setItem("theme", next); } catch(e) {}
  });
})();

/* ---------- pieces ---------- */
function statusPill(b){
  const o = b.outcome || "";
  let cls = "intro", txt = "Introduced";
  if (o.includes("became law")) { cls = "law"; txt = "Became law"; }
  else if (o.startsWith("Vetoed") || o.startsWith("Failed")) { cls = "failed"; txt = o.startsWith("Vetoed") ? "Vetoed" : "Failed a floor vote"; }
  else if (o.startsWith("Adopted")) { cls = "adopted"; txt = "Adopted"; }
  else if (o.includes("passed one chamber")) { cls = "pending"; txt = "Passed " + (b.status.includes("House") ? "the House" : "the Senate"); }
  else if (o.includes("passed both")) { cls = "pending"; txt = "Passed both, not final"; }
  else if (o.includes("awaiting")) { cls = "pending"; txt = "Waiting on the President"; }
  else if (o === "Pending") { cls = "intro"; txt = b.status.startsWith("Reported") ? "Reported by committee" : (b.status === "In committee" ? "In committee" : "Introduced"); }
  return `<span class="pill ${cls}">${esc(txt)}</span>`;
}
function backingLabel(r){ return (r && r.flags && r.flags.label) ? r.flags.label : ""; }
function gaugeIncome(r, rated){
  if (!r || r.position == null) return `<div class="axis"><div class="lab"><b>Who gains, by income</b><span class="na">${rated ? "not assessable" : "not rated yet"}</span></div></div>`;
  const lo = r.low != null ? r.low : r.position, hi = r.high != null ? r.high : r.position;
  const w = ((hi - lo) / 200 * 100).toFixed(1) + "%";
  const g = r.grade ? `<i class="grade" data-g="${esc(r.grade)}">${esc(r.grade)}</i>` : "";
  return `<div class="axis"><div class="lab"><b>Who gains, by income</b><span>${esc(signed(r.position))}${r.low != null ? " (range " + signed(lo) + " to " + signed(hi) + ")" : ""} ${g}</span></div>
    <div class="gauge" role="img" aria-label="Income axis position ${esc(signed(r.position))} on a scale from lower-income at minus 100 to high-income at plus 100"><span class="range" style="--lo:${pct(lo)};--w:${w}"></span><span class="mid"></span><span class="dot" style="--pos:${pct(r.position)}"></span></div>
    <div class="ends" style="grid-column:1/-1"><span>Lower-income</span><span>Broad-based</span><span>High-income</span></div></div>`;
}
function gaugeBacking(r, rated){
  if (!r || r.position == null) return `<div class="axis"><div class="lab"><b>Who backed it</b><span class="na">no recorded vote yet</span></div></div>`;
  return `<div class="axis"><div class="lab"><b>Who backed it</b><span>${esc(backingLabel(r))} ${esc(signed(r.position))} <i class="grade" data-g="${esc(r.grade||"")}">${esc(r.grade||"")}</i></span></div>
    <div class="gauge backing" role="img" aria-label="Party backing ${esc(signed(r.position))}, from Democrats only at minus 100 to Republicans only at plus 100"><span class="mid"></span><span class="dot" style="--pos:${pct(r.position)}"></span></div>
    <div class="ends" style="grid-column:1/-1"><span>Democrats only</span><span>Bipartisan</span><span>Republicans only</span></div></div>`;
}
function gaugeQuad(r, rated){
  if (!r || (r.position == null && r.position2 == null)) return `<div class="axis"><div class="lab"><b>Households vs. businesses</b><span class="na">${rated ? "not assessable" : "not rated yet"}</span></div></div>`;
  const h = r.position || 0, b = r.position2 || 0, tag = (r.flags && r.flags.business_tag && r.flags.business_tag !== "n/a") ? r.flags.business_tag : "";
  return `<div class="axis"><div class="lab"><b>Households vs. businesses</b><span>households ${esc(signed(r.position))}, businesses ${esc(signed(r.position2))} <i class="grade" data-g="${esc(r.grade||"")}">${esc(r.grade||"")}</i></span></div>
    <div class="quad" style="grid-column:1/-1"><svg viewBox="0 0 64 64" role="img" aria-label="Households ${esc(signed(h))}, businesses ${esc(signed(b))}"><rect class="q" x="1" y="1" width="62" height="62" rx="6"/><path class="q" d="M32 3v58M3 32h58"/><circle class="pt" cx="32" cy="32" r="6" style="--dx:${(h*0.27).toFixed(1)}px;--dy:${(-b*0.27).toFixed(1)}px"/></svg>
    <small><b>Right</b> helps households, <b>up</b> helps businesses${tag ? "<br>" + esc(tag === "both" ? "Small firms and large corporations" : "Mostly " + tag) : ""}</small></div></div>`;
}
function axes(b){
  const r = b.ratings || {};
  if (!isRated(b)) {
    if (!r.backing) return `<div class="axes"><div class="axes-empty">Not rated yet. Ratings follow the first committee action or an official cost estimate.</div></div>`;
    return `<div class="axes">${gaugeBacking(r.backing, false)}<div class="axes-empty">Income and household ratings not applied yet.</div></div>`;
  }
  return `<div class="axes">${gaugeIncome(r.income, true)}${gaugeBacking(r.backing, true)}${gaugeQuad(r.households_business, true)}</div>`;
}
function plainLine(b){
  const p = b.ratings && b.ratings.plain_language && b.ratings.plain_language.plain;
  if (p && p.one_sentence) return esc(p.one_sentence);
  if (b.summary) return esc(b.summary.slice(0, 220)) + (b.summary.length > 220 ? "…" : "") + ` <span class="na">(official summary; plain-language version not yet written)</span>`;
  return `<span class="na">No summary yet. New bills get a summary from the Library of Congress within a few weeks.</span>`;
}
/* The name to lead with. The record's popular or short title is already in short_title; a nickname John approved
   leads only when its entry says so, and otherwise rides beneath as "commonly called". */
const leadTitle = b => (b.nick && b.nick.lead) ? b.nick.name : (b.short_title || b.title);
const wasHTML = b => b.was ? `<span class="aka">began as <b>${esc(b.was)}</b>; the ${esc(b.rewritten_by || "other chamber")} replaced its text</span>` : "";
const akaHTML = b => wasHTML(b) + (!b.nick ? "" : (b.nick.lead ? ((b.short_title || b.title) ? `<span class="aka">officially <b>${esc(b.short_title || b.title)}</b></span>` : "") : `<span class="aka">commonly called <b>${esc(b.nick.name)}</b></span>`));
function lensChips(b){ return (b.lens || []).map(l => `<span class="pill lens">${esc(l.replace(" (subj.)", ""))}</span>`).join(""); }

/* ---------- the journey: from introduction to law, or to where it fell ----------
   Six stops. The build works out where each full record stands, with a date for every
   stop the record dates; introduced-only measures are worked out here from their status.
   "slim" rides on every bill card, "pick" on the Start here lists, "full" (with dates)
   heads the Votes and path tab. The marker travels to its stop when the track scrolls
   into view, then keeps a slow pulse while the measure is still alive. */
function journeyOf(b){
  if (b.journey) return b.journey;
  const at = b.status === "Introduced" ? 0 : 1, when = b.latest_action_date || "";
  return b.journey = {at, o: b.origin === "Senate" ? "S" : "H", am: /^Proposing an amendment to the Constitution/.test(b.title || "") ? 1 : 0, fail: null,
    st: when && BOOT.stall_cutoff && when < BOOT.stall_cutoff ? 1 : 0, note: at ? "In committee" : "Introduced; not yet sent to a committee", dates: [b.introduced || "", "", "", "", "", ""]};
}
const journeyStops = j => { const c = j.o === "S" ? ["Senate", "House"] : ["House", "Senate"]; return ["Introduced", "Committee", c[0], c[1], j.am ? "To the states" : "President", j.am ? "Ratified" : "Law"]; };
function trackHTML(b, mode){
  const j = journeyOf(b), names = journeyStops(j), n = names.length - 1, f = j.fail, a = j.at / n, p = (f ? f.i : j.at) / n;
  const state = i => f && i === f.i ? "fail" : (i < j.at || (i === j.at && j.at === n) ? "done" : (i === j.at ? "now" : "todo"));
  const dots = names.map((nm, i) => `<i class="stop ${state(i)}" style="left:${(100 * i / n).toFixed(1)}%;--t:${p ? Math.min(1, (i / n) / p).toFixed(2) : 0}"></i>`).join("");
  const labels = mode === "slim" ? "" : `<span class="trk-labels">${names.map((nm, i) => { const d = f && i === f.i ? f.d : (j.dates || [])[i]; return `<span class="${state(i)}" style="left:${(100 * i / n).toFixed(1)}%"><b>${esc(nm)}</b>${mode === "full" && d ? `<em>${esc(fmtDate(d))}</em>` : ""}</span>`; }).join("")}</span>`;
  const since = b.latest_action_date || b.date || "";
  const cap = `<span class="trk-cap">${esc(j.note)}${j.st && since ? `<span class="quiet"> \u00b7 no action since ${esc(fmtDate(since))}</span>` : ""}</span>`;
  const cls = `trk ${mode}${f ? " failed" : ""}${j.st ? " stalled" : ""}${!f && !j.st && j.at < n ? " active" : ""}${!f && j.at === n ? " complete" : ""}`;
  return `<span class="${cls}" style="--a:${a.toFixed(3)};--p:${p.toFixed(3)}" role="img" aria-label="${esc(`Where it stands: ${j.note}. Stop ${(f ? f.i : j.at) + 1} of ${names.length}.`)}"><span class="rail"><span class="fill"></span>${f ? `<span class="fillbad"></span>` : ""}${dots}<span class="run"></span></span>${labels}${cap}</span>`;
}
const trkIO = new IntersectionObserver(es => es.forEach(e => { if (e.isIntersecting) { e.target.classList.add("go"); trkIO.unobserve(e.target); } }), {threshold: .35});
function watchTracks(root){ $$(".trk:not(.w)", root || document).forEach(el => { el.classList.add("w"); trkIO.observe(el); }); }

/* ---------- detail panes ---------- */
function paneFor(b){
  const r = b.ratings || {}, p = r.plain_language && r.plain_language.plain, t = r.timing && r.timing.plain, rf = r.rights && r.rights.flags;
  const who = p && p.if_you_are ? `<div class="who">` + Object.entries(p.if_you_are).map(([k, v]) => `<div><b>${esc({worker:"If you work for a living", parent:"If you have kids", retiree:"If you are retired", small_business_owner:"If you run a small business", disability:"If you or someone you care for has a disability"}[k] || k)}</b>${esc(v)}</div>`).join("") + `</div>` : `<p class="na">Not rated yet.</p>`;
  const notdo = p && p.what_it_does_not_do ? `<p class="note">What it does not do: ${esc(p.what_it_does_not_do)}</p>` : "";
  const timeline = t ? `<p style="font-size:15px">${esc(t.plain || "")}</p><ul class="tl"><li><b>Starts</b><span>${esc(t.effective || "")}</span></li>${(t.phase_changes || []).map(c => `<li><b>${esc(c.date || "")}</b><span>${esc(c.what || "")}</span></li>`).join("")}<li><b>Ends</b><span>${esc(t.sunset || "")}</span></li></ul>${t.delayed_cost && String(t.delayed_cost).startsWith("yes") ? `<p class="note">Watch the timing: ${esc(t.delayed_cost)}</p>` : ""}` : `<p class="na">Not rated yet.</p>`;
  const flags = rf ? ((rf.flags || []).length ? rf.flags.map(f => `<div class="flag"><span class="k">${esc(f.flag.replace(/_/g, " "))}</span><span>${esc(f.plain)}</span></div>`).join("") : `<p class="muted">No changes to who can sue, which laws apply, or who decides.</p>`) + (rf.election_rules ? `<p class="note">This bill changes election rules.</p>` : "") : `<p class="na">Not rated yet.</p>`;
  const votes = b.votes && b.votes.length ? b.votes.slice().reverse().map(v => `<div class="vote"><span class="ch">${esc(v.chamber)}</span><span>${esc(v.category)}: ${esc(v.result || "")}${v.note ? " (" + esc(v.note) + ")" : ""}${(v.map || VOTE_IDS.has(v.vote_id)) ? `<a class="maplink" href="#map" data-vote="${esc(v.vote_id)}">see the map</a>` : ""}<br><span class="muted">${esc(fmtDate(v.date))}${v.split ? " · " + esc(v.split) : ""}</span></span>${v.yeas != null ? `<span class="tally">${v.yeas}–${v.nays}${v.url ? ` <a href="${esc(v.url)}" target="_blank" rel="noopener" style="font-size:12px;font-weight:400">roll call</a>` : ""}</span>` : `<span class="muted">${esc(v.method || "")}</span>`}</div>`).join("") : `<p class="muted">No floor votes yet.</p>`;
  const path = `<p style="font-size:14px"><b>Committees.</b> ${esc(b.committees || "None recorded")}</p>${b.committee_votes ? `<p style="font-size:14px"><b>Committee votes.</b> ${esc(b.committee_votes)}</p>` : ""}${b.related_enacted ? `<p class="note">Related measure became law: ${esc(b.related_enacted)}. The text may have been enacted inside another bill.</p>` : ""}`;
  const why = ["income", "households_business", "backing"].filter(a => r[a]).map(a => { const x = r[a]; return `<article><h4>${esc({income:"Who gains, by income", households_business:"Households vs. businesses", backing:"Who backed it"}[a])} <i class="grade" data-g="${esc(x.grade||"")}">${esc(x.grade||"")}</i>${x.confidence != null ? `<span class="muted" style="font-weight:400;font-size:13px">confidence ${Math.round(x.confidence * 100)}%</span>` : ""}</h4><p>${esc(x.justification || "")}</p>${x.magnitude_note ? `<p class="muted">${x.magnitude ? "<b>" + esc(x.magnitude) + ".</b> " : ""}${esc(x.magnitude_note)}</p>` : ""}${(x.sources || []).length ? `<p class="muted">Sources: ${x.sources.map(s => esc((s.type || "") + (s.ref ? ": " + s.ref : ""))).join("; ")}</p>` : ""}</article>`; }).join("");
  const whyBlock = b.ratings ? `<div class="why">${why}</div><p class="note">${esc(b.review)}. Rubric ${esc((r.income || r.plain_language || r.backing || {}).version || "")}, rated ${esc(((r.income || r.plain_language || r.backing || {}).rated_at || "").slice(0, 10))}.</p>` : `<p class="na">Not rated yet. Bills are rated after their first committee action or when an official cost estimate is published.</p>`;
  const L = b.links || {};
  const links = [["page", "Congress.gov page"], ["text", "Bill text"], ["pdf", "Latest text (PDF)"], ["actions", "All actions"], ["cosponsors", "Cosponsors"], ["committees", "Committees"], ["cbo", "CBO cost estimate"]].filter(([k]) => L[k]).map(([k, lab]) => `<a href="${esc(L[k])}" target="_blank" rel="noopener">${lab}</a>`).join("");
  const named = (b.lead_kind === "popular" ? `<p class="note"><b>${esc(b.short_title)}</b> is this measure's popular title in the Library of Congress record. It is not the title in the final text, which is below.</p>` : (b.lead_kind === "short" ? `<p class="note"><b>${esc(b.short_title)}</b> is the short title this measure carried at an earlier stage, per the Library of Congress record.</p>` : (b.lead_kind === "rewritten" ? `<p class="note">This measure began as <b>${esc(b.was)}</b>. The ${esc(b.rewritten_by || "other chamber")} replaced its text; its amendment carries the short title <b>${esc(b.short_title)}</b>, per the Library of Congress record. Earlier votes on this number were on the original bill.</p>` : "")))
    + (b.nick ? `<p class="note">Commonly called <b>${esc(b.nick.name)}</b> (<a href="${esc(b.nick.source)}" target="_blank" rel="noopener">where that name is used</a>). That is a label we keep by hand; it is not part of the official record.</p>` : "");
  const facts = `${named}${b.short_title && b.short_title !== b.title ? `<p style="font-size:14px"><b>Official title.</b> ${esc(b.title)}</p>` : ""}${b.source_update ? `<p class="note">Record last updated by the Library of Congress on ${esc(fmtDate(b.source_update))}.${Number(b.congress) < 119 ? " Sample files are snapshots." : ""}</p>` : ""}<p style="font-size:14px"><b>${esc(b.kind || "Bill")}</b> introduced ${esc(fmtDate(b.introduced))} in the ${esc(b.origin)}${b.sponsor ? ` by ${esc(b.sponsor.name)}` : ""}. ${b.cosponsors && b.cosponsors.total ? `${b.cosponsors.total} cosponsors${b.cosponsors.by_party ? " (" + esc(b.cosponsors.by_party) + ")" : ""}.` : "No cosponsors."} ${b.policy_area ? "Policy area: " + esc(b.policy_area) + "." : ""}</p>${b.subjects && b.subjects.length ? `<p class="muted" style="font-size:13px">Subjects: ${b.subjects.map(esc).join(", ")}</p>` : ""}${b.summary ? `<p style="font-size:14px"><b>Official summary</b> (${esc(b.summary_desc)}, ${esc(fmtDate(b.summary_date))}): ${esc(b.summary)}</p>` : ""}`;
  const tabs = [["you", "For you", who + notdo], ["time", "When it hits", timeline], ["rights", "Your rights", flags], ["votes", "Votes and path", trackHTML(b, "full") + billMapHTML(b) + votes + path], ["why", "Why this rating", whyBlock], ["facts", "Facts and links", facts + `<div class="links">${links}</div>`]];
  const first = isRated(b) ? 0 : (b.votes && b.votes.length ? 3 : 5);
  return `<div class="tabs" role="tablist">${tabs.map(([k, lab], i) => `<button class="tab" role="tab" data-t="${k}" aria-selected="${i === first}">${lab}</button>`).join("")}</div>${tabs.map(([k, , html], i) => `<div class="pane${i === first ? " show" : ""}" data-p="${k}">${html}</div>`).join("")}`;
}

/* ---------- cards ---------- */
function cardHTML(b){
  return `<article class="card" data-key="${esc(b.key)}"><div class="head"><span class="pill id">${esc(b.id)}</span>${statusPill(b)}${b.law ? `<span class="pill intro">P.L. ${esc(b.law)}</span>` : ""}${lensChips(b)}</div>
  <div class="title">${esc(leadTitle(b))}</div>${akaHTML(b)}<p class="plain">${plainLine(b)}</p>${trackHTML(b, "slim")}${axes(b)}
  <div class="meta"><span>Latest: <b>${esc(fmtDate(b.latest_action_date))}</b></span>${b.sponsor ? `<span class="spon">${avatar(b.sponsor.id, b.sponsor.party, "sm")}<b>${esc(prettyStr(b.sponsor.name))}</b> ${esc((b.sponsor.name.match(/\[(.*?)\]/) || [,""])[1])}</span>` : ""}${b.cosponsors && b.cosponsors.total ? `<span><b>${b.cosponsors.total}</b> cosponsors${b.bipartisan ? ", both parties" : ""}</span>` : ""}</div>
  <div class="detail"><div></div></div>
  <div class="foot"><span class="status">${b.review ? esc(b.review) : (b.latest_action ? esc(b.latest_action.length > 90 ? b.latest_action.slice(0, 88).replace(/\s+\S*$/, "") + "…" : b.latest_action) : "Not rated yet")}</span><span class="acts"><button class="copylink sharebtn" aria-label="Share ${esc(b.id)}" title="Share"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><path d="M8.6 13.5l6.8 4M15.4 6.5l-6.8 4"/></svg></button><button class="more" aria-expanded="false">Details <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 9l6 6 6-6"/></svg></button></span></div></article>`;
}

const grid = $("#grid"), state = { q: "", f: "all", sort: "recent", member: null, pin: null };
const hay = b => b._hay ?? (b._hay = [b.id, b.title, b.short_title, b.nick ? b.nick.name : "", b.policy_area, (b.subjects || []).join(" "), b.sponsor ? b.sponsor.name : "", b.law ? "p.l. " + b.law : "", b.summary].join(" ").toLowerCase());
const statusText = b => statusPill(b).replace(/<[^>]+>/g, "");
const prettyStr = s => String(s || "").replace(/\s*\[.*\]$/, "").replace(/^(Rep|Sen|Del|Res\. Comm)\.\s*/, "").replace(/^([^,]+),\s*(.+)$/, "$2 $1");
const prettyName = m => prettyStr(m.name);
/* ---------- motion preference: living portraits and page motion, or everything still ---------- */
const MOTION = (function(){
  const root = document.documentElement, btn = $("#motion");
  let saved = null; try { saved = localStorage.getItem("motion"); } catch(e) {}
  let on = saved ? saved === "on" : !matchMedia("(prefers-reduced-motion: reduce)").matches;
  const apply = () => { root.classList.toggle("motion", on); root.classList.toggle("calm", !on); btn.setAttribute("aria-pressed", on); };
  btn.addEventListener("click", () => {
    on = !on; try { localStorage.setItem("motion", on ? "on" : "off"); } catch(e) {}
    apply();
    if (on) { if (window.gyroStart) gyroStart(); if (window.fieldResume) fieldResume(); if (window.heroRestart) heroRestart(); }
    else if (window.heroPause) heroPause();
    toast(on ? "Motion on: portraits drift and tilt" : "Motion off: everything holds still");
  });
  apply();
  return { get on(){ return on; } };
})();
const calm = () => !MOTION.on;
(function(){
  const root = document.documentElement; let cur = null;
  const clear = el => ["--rx", "--ry", "--px", "--py"].forEach(v => el.style.removeProperty(v));
  document.addEventListener("pointermove", e => {
    if (e.pointerType !== "mouse") return;
    const w = MOTION.on ? e.target.closest(".avw.kb") : null;
    if (cur && cur !== w) clear(cur);
    cur = w; if (!w) return;
    const r = w.getBoundingClientRect(), dx = (e.clientX - r.left) / r.width - .5, dy = (e.clientY - r.top) / r.height - .5;
    w.style.setProperty("--ry", (dx * 28).toFixed(1) + "deg"); w.style.setProperty("--rx", (-dy * 28).toFixed(1) + "deg");
    w.style.setProperty("--px", (-dx * 9).toFixed(1) + "px"); w.style.setProperty("--py", (-dy * 9).toFixed(1) + "px");
  }, {passive: true});
  let armed = false, base = null, gyroSeen = false;
  function onOrient(e){
    if (!MOTION.on || e.gamma == null || e.beta == null) return;
    gyroSeen = true;
    if (!base) base = {g: e.gamma, b: e.beta}; else { base.g += (e.gamma - base.g) * .015; base.b += (e.beta - base.b) * .015; }
    const gx = Math.max(-1, Math.min(1, (e.gamma - base.g) / 22)), gy = Math.max(-1, Math.min(1, (e.beta - base.b) / 22));
    root.style.setProperty("--gx", (gx * 16).toFixed(1) + "deg"); root.style.setProperty("--gy", (-gy * 16).toFixed(1) + "deg");
    root.style.setProperty("--gpx", (-gx * 6).toFixed(1) + "px"); root.style.setProperty("--gpy", (-gy * 6).toFixed(1) + "px");
  }
  window.gyroStart = function(){
    if (armed) return;
    if (typeof DeviceOrientationEvent !== "undefined" && typeof DeviceOrientationEvent.requestPermission === "function") {
      DeviceOrientationEvent.requestPermission().then(st => { if (st === "granted") { armed = true; addEventListener("deviceorientation", onOrient, {passive: true}); } }).catch(() => {});
    } else if ("DeviceOrientationEvent" in window) { armed = true; addEventListener("deviceorientation", onOrient, {passive: true}); }
  };
  const coarse = matchMedia("(pointer: coarse)").matches;
  if (coarse) gyroStart();
  // phones without tilt data: portraits pan a little with the scroll instead
  const vis = new Set(), io = new IntersectionObserver(es => es.forEach(x => x.isIntersecting ? vis.add(x.target) : vis.delete(x.target)));
  const watch = () => $$(".avw.kb:not(.w)").forEach(el => { el.classList.add("w"); io.observe(el); });
  let mo = 0; new MutationObserver(() => { if (!mo) mo = requestAnimationFrame(() => { mo = 0; watch(); }); }).observe(document.body, {childList: true, subtree: true});
  let tick = false;
  addEventListener("scroll", () => {
    if (!coarse || gyroSeen || !MOTION.on || tick) return; tick = true;
    requestAnimationFrame(() => { tick = false; const vh = innerHeight; vis.forEach(el => { const r = el.getBoundingClientRect(), d = ((r.top + r.height / 2) - vh / 2) / vh; el.style.setProperty("--py", (d * 10).toFixed(1) + "px"); el.style.setProperty("--rx", (d * -12).toFixed(1) + "deg"); }); });
  }, {passive: true});
  watch();
})();
const photo = id => { if (!id) return ""; if (BOOT.inline) { const P = BOOT.inline.photos || {}; return P[id] ? "data:image/webp;base64," + P[id] : ""; } return PHOTO.has(id) ? `photos/${id}.webp?v=${DATA_V}` : ""; };
function avatar(id, party, cls){
  const src = photo(id), p = esc(party || ""), pc = party === "R" ? "rep" : (party === "D" ? "dem" : (party === "L" ? "amber" : "plum"));
  let h = 0; for (const ch of String(id || "")) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  const kb = src && cls !== "sm" ? ` kb" style="--pc:var(--${pc});--kbd:${11 + h % 7}s;--kbo:-${h % 11}s;--kbx:${(h % 3) - 1 ? ((h % 3) - 1) * 3 : 2}%;--kby:${(h >> 3) % 2 ? 3 : -2}%` : `" style="--pc:var(--${pc})`;
  return `<span class="avw ${cls || ""}${kb}"><span class="avc"><span class="avz">${src ? `<img class="av" src="${src}" alt="" decoding="async" loading="lazy">` : `<span class="av av-txt">${p.slice(0, 1)}</span>`}</span></span><i class="pb">${p}</i></span>`;
}
const rvIO = new IntersectionObserver(es => es.forEach(e => { if (e.isIntersecting) { e.target.classList.add("in", "live"); rvIO.unobserve(e.target); } }), {threshold: .12, rootMargin: "0px 0px -6% 0px"});
const reveal = root => { $$(".rv:not(.obs)", root).forEach(el => { el.classList.add("obs"); rvIO.observe(el); }); watchTracks(root); };
const roleOf = m => m.name.startsWith("Sen.") ? "Senator" : (m.chamber === "Senate" ? "Senator" : "Representative");
function matches(b){
  const q = state.q.trim().toLowerCase();
  if (q && !hay(b).includes(q)) return false;
  if (state.member && !state.member.set.has(b._i)) return false;
  switch (state.f) {
    case "rated": return isRated(b);
    case "law": return !!b.law;
    case "pending": return !b.law && (b.outcome || "").startsWith("Pending");
    case "119": return Number(b.congress) >= 119;
    case "Tax": case "Employment": case "Disability": return (b.lens || []).some(l => l.startsWith(state.f));
    default: return true;
  }
}
function sorter(a, b){
  if (state.sort === "rated") return (isRated(b) ? 1 : 0) - (isRated(a) ? 1 : 0) || (b.latest_action_date || "").localeCompare(a.latest_action_date || "");
  if (state.sort === "number") { const ka = keyParts(a.key), kb = keyParts(b.key); return kb[0] - ka[0] || ka[1] - kb[1] || ka[2] - kb[2]; }
  return (b.latest_action_date || "").localeCompare(a.latest_action_date || "");
}
const PAGE = 30;
let listed = [], shown = 0;
function renderLoading(){
  $("#count").textContent = `Loading ${(BOOT.stats.measures || 0).toLocaleString()} bills\u2026`;
  grid.innerHTML = Array.from({length: 6}, (_, i) => `<div class="card sk" style="--i:${i}"><div class="skl w3"></div><div class="skl w8"></div><div class="skl w6"></div></div>`).join("");
}
function renderFailed(){
  $("#count").textContent = "The bill list didn't load.";
  grid.innerHTML = `<div class="empty">Couldn't load the bill list. Check your connection. <button class="chip" id="retrylist">Try again</button></div>`;
  $("#retrylist").addEventListener("click", render);
}
function render(){
  if (!CATALOG_READY) { renderLoading(); catalogReady().then(render, renderFailed); return; }
  listed = DATA.bills.filter(matches).sort(sorter); shown = 0;
  if (state.pin) { const i = listed.findIndex(b => b.key === state.pin); if (i > 0) listed.unshift(listed.splice(i, 1)[0]); else if (i < 0 && byKey[state.pin]) listed.unshift(byKey[state.pin]); }
  $("#count").textContent = `${listed.length.toLocaleString()} of ${DATA.bills.length.toLocaleString()} measures${state.member ? " for " + prettyName(state.member) : ""}`;
  grid.innerHTML = listed.length ? "" : `<div class="empty">Nothing matches. Try fewer words, or clear the filters.</div>`;
  showMore();
}
function showMore(){
  const btn = $("#showmore"); if (btn) btn.remove();
  const slice = listed.slice(shown, shown + PAGE); shown += slice.length;
  grid.insertAdjacentHTML("beforeend", slice.map(cardHTML).join(""));
  $$(".card:not(.obs)", grid).forEach((el, i) => { el.classList.add("rv"); el.style.setProperty("--i", i % 6); });
  reveal(grid);
  const left = listed.length - shown;
  if (left > 0) grid.insertAdjacentHTML("beforeend", `<button class="chip showmore" id="showmore">Show ${Math.min(PAGE, left)} more (${left.toLocaleString()} left)</button>`);
}
grid.addEventListener("click", e => {
  if (e.target.closest("#showmore")) { showMore(); return; }
  const sb = e.target.closest(".sharebtn");
  if (sb) { const b = byKey[sb.closest(".card").dataset.key]; if (b) share({title: `${b.id}: ${leadTitle(b)}`, text: shareTextBill(b), url: shareUrlBill(b), kind: "bill", key: b.key}, sb); return; }
  const more = e.target.closest(".more"), tab = e.target.closest(".tab");
  if (tab) {
    const card = tab.closest(".card");
    $$(".tab", card).forEach(t => t.setAttribute("aria-selected", t === tab));
    $$(".pane", card).forEach(p => p.classList.toggle("show", p.dataset.p === tab.dataset.t));
    armBillMap(card);
    return;
  }
  if (!more) return;
  const card = more.closest(".card"), open = !card.classList.contains("open");
  if (open && !card.dataset.built) {
    const b = byKey[card.dataset.key], box = $(".detail > div", card); card.dataset.built = "1";
    if (b.trim) { box.innerHTML = `<p class="muted loading">Loading the full record\u2026</p>`; needBill(b).then(() => { box.innerHTML = paneFor(b); watchTracks(box); armBillMap(card); }, () => { box.innerHTML = `<p class="muted">Couldn't load this bill's details. Check your connection and open it again.</p>`; delete card.dataset.built; }); }
    else { box.innerHTML = paneFor(b); watchTracks(box); armBillMap(card); }
  }
  card.classList.toggle("open", open);
  const bill = byKey[card.dataset.key]; if (bill && leadTitle(bill) !== bill.title) $(".title", card).textContent = open ? bill.title : leadTitle(bill);
  more.setAttribute("aria-expanded", open);
  more.firstChild.textContent = open ? "Close " : "Details ";
  if (open) setTimeout(() => card.scrollIntoView({block: "nearest", behavior: "smooth"}), 60);
});
let qTimer; $("#q").addEventListener("input", e => { clearTimeout(qTimer); qTimer = setTimeout(() => { state.q = e.target.value; render(); }, 140); });
if ((BOOT.stats.current || 0) >= (BOOT.stats.measures || 0)) { const c = $('.chip[data-f="119"]'); if (c) c.remove(); }
$("#sort").addEventListener("change", e => { state.sort = e.target.value; render(); });
const chipInd = document.createElement("span"); chipInd.className = "chip-ind"; $("#chips").prepend(chipInd);
function moveChipInd(){ const c = $('#chips .chip[aria-pressed="true"]'); if (!c) return; chipInd.style.left = c.offsetLeft + "px"; chipInd.style.width = c.offsetWidth + "px"; }
$("#chips").addEventListener("click", e => {
  const c = e.target.closest(".chip"); if (!c) return;
  $$("#chips .chip").forEach(x => x.setAttribute("aria-pressed", x === c)); state.f = c.dataset.f; moveChipInd(); render();
});
addEventListener("resize", moveChipInd);

function openBill(key){
  if (!byKey[key]) return false;
  state.q = ""; $("#q").value = ""; state.f = "all"; $$("#chips .chip").forEach(x => x.setAttribute("aria-pressed", x.dataset.f === "all")); moveChipInd();
  state.member = null; $("#mpick").textContent = "Pick a member to filter the bill list above.";
  state.pin = key; render(); state.pin = null;
  pageview("/bill/" + key, byKey[key].id + ": " + (byKey[key].short_title || byKey[key].title));
  const card = $(`.card[data-key="${CSS.escape(key)}"]`); if (!card) return false;
  card.classList.add("in", "live");
  if (!card.classList.contains("open")) $(".more", card).click();
  setTimeout(() => card.scrollIntoView({block: "start", behavior: "smooth"}), 80);
  return true;
}

/* Bills are listed on the Bills page, so anything that opens one from
   somewhere else - the hero panel, the Start here lists, the search palette -
   has to take the reader there first. Going through the #bill= route keeps the
   address shareable and leaves a history entry, so Back returns where they were. */
function goToBill(key){
  history.pushState({page: "bills"}, "", "#bill=" + key);
  routeFromHash(false);
  return true;
}

/* ---------- hero carousel ---------- */
const hasPos = r => r && r.position != null;
const featured = BOOT.featured || [];   // rated bills, sorted at build time: current Congress first, A-grade income evidence first
let hi = 0, htimer;
function heroShow(i, animate){
  hi = (i + featured.length) % featured.length;
  const b = featured[hi], body = $("#herobody");
  const paint = () => {
    body.innerHTML = `<div class="pid"><span class="pill id">${esc(b.id)}</span>${statusPill(b)}${b.law ? `<span class="pill intro">P.L. ${esc(b.law)}</span>` : ""}${lensChips(b)}</div><div class="ptitle">${esc(leadTitle(b))}</div>${akaHTML(b)}<p class="pplain">${plainLine(b)}</p>${trackHTML(b, "slim")}${b.sponsor ? `<div class="spot-spon">${avatar(b.sponsor.id, b.sponsor.party, "md")}<span>Sponsored by <b>${esc(prettyStr(b.sponsor.name))}</b>, ${esc(b.sponsor.party)}-${esc(b.sponsor.state)}</span></div>` : ""}${axes(b)}`;
    body.classList.remove("out"); watchTracks(body);
    requestAnimationFrame(() => requestAnimationFrame(() => $(".axes", body).classList.add("live")));
  };
  if (animate) { body.classList.add("out"); setTimeout(paint, 360); } else paint();
  $$("#herodots button").forEach((d, j) => d.setAttribute("aria-current", j === hi));
}
if (featured.length) {
  $("#herodots").innerHTML = featured.map((b, i) => `<button role="tab" aria-label="Show ${esc(b.id)}" aria-current="${i === 0}"></button>`).join("");
  $("#herodots").addEventListener("click", e => { const i = $$("#herodots button").indexOf(e.target.closest("button")); if (i >= 0) { heroShow(i, true); restart(); } });
  $("#herogo").addEventListener("click", () => goToBill(featured[hi].key));
  const restart = () => { clearInterval(htimer); if (!calm()) htimer = setInterval(() => heroShow(hi + 1, true), 9000); };
  window.heroRestart = restart; window.heroPause = () => clearInterval(htimer);
  $("#heropanel").addEventListener("mouseenter", () => clearInterval(htimer));
  $("#heropanel").addEventListener("mouseleave", restart);
  heroShow(0, false); restart();
} else { $("#heropanel").style.display = "none"; }

/* ---------- hero: word reveal and the member field ---------- */
(function(){
  /* The headline rises word by word; then its second line turns over a few times, naming what is here,
     and comes to rest where it began. With Motion off it simply reads "in plain words." */
  const h = $(".hero h1"), a = h && $(".h1a", h), rot = $("#h1rot"); if (!h || !a || !rot) return;
  const words = (txt, d0, step) => txt.trim().split(/\s+/).map((w, i) => `<span class="w"><span style="animation-delay:${d0 + i * step}ms">${esc(w)}</span></span>`).join(" ");
  const PH = ["in plain words.", "bill by bill.", "vote by vote.", "seat by seat."];
  let i = 0, turns = 0, timer = 0, seen = true;
  a.innerHTML = words(a.textContent, 60, 60); rot.innerHTML = words(PH[0], 120, 60);
  const arm = () => { if (!timer && turns < 2) timer = setTimeout(next, i === 0 ? 4200 : 2400); };
  function next(){
    timer = 0;
    if (calm()) { if (i) { i = 0; rot.innerHTML = words(PH[0], 0, 40); } arm(); return; }
    if (document.hidden || !seen) { arm(); return; }
    $$(".w>span", rot).forEach((sp, k) => { sp.style.animationDelay = (k * 40) + "ms"; sp.classList.add("out"); });
    setTimeout(() => { i = (i + 1) % PH.length; if (!i) turns++; rot.innerHTML = words(PH[i], 0, 40); arm(); }, 560);
  }
  new IntersectionObserver(es => es.forEach(e => { seen = e.isIntersecting; })).observe(h);
  arm();
  window.headlineStats = () => ({i, turns, text: rot.textContent});
})();
(function(){
  /* The Capitol at the hour you are reading this, under the weather that is
     actually outside. Drawn flat and layered, like a screen print: wide bands
     of warm colour, an offset "misprint" edge on the building, grain over
     everything. No photograph, nothing to download.

     Weather comes from Open-Meteo, which needs no key. It defaults to the
     Capitol itself - the honest default for a site about Congress, and it
     asks nobody for their location. The caption offers to use yours instead.
     If the request fails, or the page is opened offline, the scene still
     draws under a clear sky: the building is the point, weather is garnish. */
  const c = $("#field"); if (!c) return;
  const ctx = c.getContext("2d");
  let W = 0, H = 0, raf = 0;
  const t0 = performance.now();

  const DC = {lat: 38.8899, lon: -77.0091, name: "Washington, DC"};
  let wx = {cloud: .25, rain: 0, snow: 0, fog: 0, night: null, temp: null, place: DC.name, text: "", ok: false};

  /* Two palettes, chosen by the page's theme so the words always read over the sky: a lit Capitol under a
     night sky on the dark page, the screen-print day on the light one. The hour still shows. By day the dark
     page warms to dusk along the horizon; by night the light page cools to dawn, and its orb is the moon. */
  const SKY = {
    day:   [[0, "#BBD0DB"], [.40, "#E3D8C6"], [.72, "#F0CBA6"], [1, "#E6B18C"]],
    dawn:  [[0, "#BFC6DE"], [.42, "#DAD3E0"], [.74, "#ECCFC6"], [1, "#E6BCA8"]],
    night: [[0, "#05070F"], [.40, "#0B1030"], [.74, "#19174A"], [1, "#2B2060"]],
    dusk:  [[0, "#070A18"], [.38, "#12163F"], [.68, "#37236A"], [.88, "#8A3A70"], [1, "#DE6F50"]]};
  const hero = c.parentElement, isDark = () => document.documentElement.dataset.theme !== "light";
  const drifters = [$("h1", hero), $(".kpirail", hero)].filter(Boolean);      // the two things that drift as the page scrolls
  let lay = {wide: false, base: 0, cx: 0, bw: 0};          // where the building stands; worked out in size()
  let sy = 0, mx = 0, my = 0, tmx = 0, tmy = 0, lastPar = "";   // scroll and pointer, for depth

  function drawSky(pal){
    const g = ctx.createLinearGradient(0, 0, 0, lay.base);
    for (const st of SKY[pal]) g.addColorStop(st[0], st[1]);
    ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
  }

  const STARS = (() => { let q = 7; const r = () => (q = (q * 16807) % 2147483647) / 2147483647;
    return Array.from({length: 120}, () => ({x: r(), y: r(), m: .5 + r() * .9, p: r() * 6.283, v: .4 + r() * 1.3})); })();
  function drawStars(t, cover, strength){
    const still = calm(); ctx.fillStyle = "#E8ECFF";
    for (const st of STARS) {
      ctx.globalAlpha = (still ? .7 : (.35 + .65 * Math.abs(Math.sin(t * st.v + st.p)))) * (1 - cover * .8) * (1 - st.y * .6) * strength;
      ctx.beginPath(); ctx.arc(st.x * W, st.y * lay.base * .84, st.m, 0, 6.283); ctx.fill();
    }
    ctx.globalAlpha = 1;
  }

  function drawOrb(t, night, dark){
    const d = new Date(), p = (d.getHours() + d.getMinutes() / 60) / 24, B = lay.base;
    const sweep = (p * 2 + t * .0008) % 1;
    const x = lay.wide ? W * (.86 + .10 * sweep) : W * (.12 + .76 * sweep);                       // wide: the top right corner, clear of the headline
    const y = lay.wide ? B * .19 - Math.sin(sweep * Math.PI) * B * .07 : B * (night ? .24 : .32) - Math.sin(sweep * Math.PI) * B * .13;
    const r = Math.max(15, Math.min(W, B) * .042);
    const halo = ctx.createRadialGradient(x, y, r * .2, x, y, r * 5);
    halo.addColorStop(0, night ? (dark ? "rgba(214,224,255,.30)" : "rgba(255,255,255,.55)") : "rgba(255,226,168,.50)");
    halo.addColorStop(1, "rgba(255,255,255,0)");
    ctx.fillStyle = halo; ctx.beginPath(); ctx.arc(x, y, r * 5, 0, 6.283); ctx.fill();
    ctx.fillStyle = night ? (dark ? "#EDF0FF" : "#FBFBFF") : "#FFE7B4";
    ctx.beginPath(); ctx.arc(x, y, r, 0, 6.283); ctx.fill();
    if (night) { ctx.fillStyle = dark ? SKY.night[1][1] : SKY.dawn[1][1]; ctx.beginPath(); ctx.arc(x + r * .38, y - r * .26, r * .92, 0, 6.283); ctx.fill(); }
  }

  function cloudBand(t, y, speed, scale, alpha, tint){
    const span = W + 400, off = ((t * speed) % span) - 200;
    ctx.fillStyle = tint; ctx.globalAlpha = Math.min(.85, alpha);
    for (let i = -1; i < 7; i++) {
      const x = off + i * (span / 6), w = scale * (90 + (i % 3) * 46), h = scale * (16 + (i % 2) * 7);
      ctx.beginPath(); ctx.ellipse(x, y + (i % 2) * 9, w, h, 0, 0, 6.283); ctx.fill();
      ctx.beginPath(); ctx.ellipse(x + w * .52, y + 6 + (i % 2) * 5, w * .62, h * .78, 0, 0, 6.283); ctx.fill();
    }
    ctx.globalAlpha = 1;
  }

  function ridges(base, dark){
    const tones = dark ? ["#0D1129", "#080B1A"] : ["#C7C2A6", "#B1B092"];
    for (let k = 0; k < 2; k++) {
      const y = base - 6 + k * 26, amp = 12 - k * 4;
      ctx.fillStyle = tones[k]; ctx.beginPath(); ctx.moveTo(-80, y + 30);
      for (let x = -80; x <= W + 80; x += 24) ctx.lineTo(x, y + Math.sin(x / (170 + k * 90) + k * 2.1) * amp);
      ctx.lineTo(W + 80, H + 120); ctx.lineTo(-80, H + 120); ctx.closePath(); ctx.fill();
    }
  }

  function capitol(cx, base, w, fill, detail){
    const u = w / 2, y = v => base - v * u;
    ctx.fillStyle = fill; ctx.beginPath();
    ctx.moveTo(cx - u, base);
    ctx.lineTo(cx - u, y(.155)); ctx.lineTo(cx - u * .62, y(.155));
    ctx.lineTo(cx - u * .62, y(.235)); ctx.lineTo(cx - u * .34, y(.235));
    ctx.lineTo(cx - u * .34, y(.30)); ctx.lineTo(cx - u * .30, y(.33));
    ctx.lineTo(cx - u * .155, y(.345));
    ctx.lineTo(cx - u * .155, y(.50));
    ctx.bezierCurveTo(cx - u * .150, y(.635), cx - u * .085, y(.715), cx, y(.735));
    ctx.bezierCurveTo(cx + u * .085, y(.715), cx + u * .150, y(.635), cx + u * .155, y(.50));
    ctx.lineTo(cx + u * .155, y(.345));
    ctx.lineTo(cx + u * .30, y(.33)); ctx.lineTo(cx + u * .34, y(.30));
    ctx.lineTo(cx + u * .34, y(.235)); ctx.lineTo(cx + u * .62, y(.235));
    ctx.lineTo(cx + u * .62, y(.155)); ctx.lineTo(cx + u, y(.155));
    ctx.lineTo(cx + u, base); ctx.closePath(); ctx.fill();
    ctx.fillRect(cx - u * .042, y(.80), u * .084, u * .066);
    ctx.beginPath(); ctx.arc(cx, y(.815), u * .030, 0, 6.283); ctx.fill();
    ctx.fillRect(cx - u * .008, y(.868), u * .016, u * .050);
    if (!detail) return;
    ctx.globalAlpha = detail === "lit" ? .34 : .16; ctx.fillStyle = detail === "lit" ? "#1A2050" : "#FFFFFF";
    for (let i = -4; i <= 4; i++) ctx.fillRect(cx + i * u * .030 - u * .005, y(.495), u * .009, u * .145);
    for (let i = -7; i <= 7; i++) ctx.fillRect(cx + i * u * .038 - u * .006, y(.165), u * .011, u * .062);
    ctx.globalAlpha = 1;
  }

  function building(dark){
    const cx = lay.cx, base = lay.base, bw = lay.bw, u = bw / 2;
    if (!dark) {
      capitol(cx - bw * .014, base - 5, bw, "rgba(180,108,72,.28)", false);
      capitol(cx, base, bw, "#493A33", true);
      return;
    }
    // at night the building is lit from below: a warm wash behind it, a teal "misprint" edge, pale stone
    const glow = ctx.createRadialGradient(cx, base - u * .40, u * .08, cx, base - u * .40, u * 1.35);
    glow.addColorStop(0, "rgba(255,228,176,.36)"); glow.addColorStop(.5, "rgba(255,214,160,.12)"); glow.addColorStop(1, "rgba(255,214,160,0)");
    ctx.fillStyle = glow; ctx.fillRect(cx - u * 1.4, base - u * 1.8, u * 2.8, u * 1.9);
    capitol(cx - bw * .014, base - 5, bw, "rgba(76,197,176,.55)", false);
    const stone = ctx.createLinearGradient(0, base - u * .9, 0, base);
    stone.addColorStop(0, "#A9B2D4"); stone.addColorStop(.55, "#E4DDCE"); stone.addColorStop(1, "#FFF0CC");
    capitol(cx, base, bw, stone, "lit");
  }

  function precip(t, dark){
    if (!wx.rain && !wx.snow) return;
    const n = Math.round((wx.rain ? 110 : 64) * Math.min(1, W / 900));
    ctx.strokeStyle = dark ? "rgba(198,212,240,.40)" : "rgba(116,138,170,.36)";
    ctx.fillStyle = ctx.strokeStyle; ctx.lineWidth = 1.1;
    for (let i = 0; i < n; i++) {
      const sx = (i * 137.5) % W, sp = wx.snow ? 26 : 150, drift = wx.snow ? Math.sin(t * .8 + i) * 16 : 12;
      const yy = ((t * sp + i * 53) % (H + 60)) - 30, x = (sx + drift + (yy / H) * 24) % W;
      if (wx.snow) { ctx.beginPath(); ctx.arc(x, yy, 1.7, 0, 6.283); ctx.fill(); }
      else { ctx.beginPath(); ctx.moveTo(x, yy); ctx.lineTo(x - 2, yy + 11); ctx.stroke(); }
    }
  }

  let grain = null;
  function makeGrain(){
    const n = 96, off = document.createElement("canvas"); off.width = off.height = n;
    const g = off.getContext("2d"), img = g.createImageData(n, n);
    for (let i = 0; i < n * n; i++) { const v = 128 + (Math.random() - .5) * 56; img.data[i * 4] = img.data[i * 4 + 1] = img.data[i * 4 + 2] = v; img.data[i * 4 + 3] = 20; }
    g.putImageData(img, 0, 0); grain = ctx.createPattern(off, "repeat");
  }

  function size(){
    const r = hero.getBoundingClientRect(), dpr = Math.min(2, devicePixelRatio || 1);
    W = Math.max(1, r.width); H = Math.max(1, r.height);
    c.width = W * dpr; c.height = H * dpr; ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    if (!grain) makeGrain();
    /* Where the building stands. On a wide screen: at the right edge, on the line where the first screen ends
       or the featured bill's card begins, and no taller than the room under the headline allows, so it never
       sits behind the words. Anywhere else: at the foot of the hero, as before. */
    const h1 = $("h1", hero), panel = $("#heropanel"), top = r.top + scrollY;
    const fold = innerHeight - top - 6, card = panel && panel.offsetParent ? panel.getBoundingClientRect().top - r.top + 2 : 1e9;
    const base = Math.min(H * .96, fold, card), clear = h1 ? h1.getBoundingClientRect().bottom - r.top + 14 : 0, u = Math.min(W * .30, (base - clear) / .87);
    lay = (W >= 1180 && u >= 150) ? {wide: true, base, cx: W - u * .42, bw: u * 2}
      : {wide: false, base: H * .96, cx: W * .5, bw: Math.max(300, Math.min(W * .88, 720))};
  }

  function paint(now, once){
    const t = (now - t0) / 1000, hr = new Date().getHours(), live = !calm();
    const night = wx.night === null ? (hr < 6 || hr >= 19) : wx.night, dark = isDark(), pal = dark ? (night ? "night" : "dusk") : (night ? "dawn" : "day");
    // depth: far layers keep up with the scroll (so they seem slow), near ones stay with the page; the pointer nudges them the other way
    sy = live ? Math.max(0, Math.min(H, scrollY)) : 0;
    mx += ((live ? tmx : 0) - mx) * .07; my += ((live ? tmy : 0) - my) * .07;
    const pv = live ? Math.min(1, scrollY / Math.max(1, innerHeight * .9)).toFixed(3) : "0";
    if (pv !== lastPar) { lastPar = pv; drifters.forEach(el => el.style.setProperty("--par", pv)); }
    const layer = (k, m, fn) => { ctx.save(); ctx.translate(-mx * m, sy * k - my * m * .4); fn(); ctx.restore(); };
    ctx.clearRect(0, 0, W, H);
    drawSky(pal);
    const cover = Math.min(1, wx.cloud + wx.fog * .6), B = lay.base;
    if (dark) layer(.50, 4, () => drawStars(t, cover, night ? 1 : .55));
    if (!dark || night) layer(.42, 6, () => drawOrb(t, night, dark));
    const tint = dark ? "rgba(128,138,188,.34)" : "rgba(255,255,255,.70)";
    if (cover > .04) layer(.30, 10, () => cloudBand(t, B * .26, 5.5, 1.15, .26 + cover * .40, tint));
    if (cover > .30) layer(.36, 8, () => cloudBand(t, B * .17, 9.0, .85, .20 + cover * .32, tint));
    if (cover > .62) layer(.24, 12, () => cloudBand(t, B * .36, 3.2, 1.45, .18 + cover * .28, tint));
    layer(.10, 14, () => ridges(B, dark));
    layer(.05, 20, () => { const z = 1 + (sy / Math.max(1, H)) * .05; ctx.translate(lay.cx, B); ctx.scale(z, z); ctx.translate(-lay.cx, -B); building(dark); });
    precip(t, dark);
    if (grain) { ctx.globalAlpha = dark ? .48 : .72; ctx.fillStyle = grain; ctx.fillRect(0, 0, W, H); ctx.globalAlpha = 1; }
    const vg = ctx.createRadialGradient(W / 2, H * .45, Math.min(W, H) * .3, W / 2, H * .5, Math.max(W, H) * .78);
    vg.addColorStop(0, "rgba(0,0,0,0)"); vg.addColorStop(1, dark ? "rgba(0,0,0,.40)" : "rgba(80,55,35,.18)");
    ctx.fillStyle = vg; ctx.fillRect(0, 0, W, H);
    if (once !== true) raf = calm() ? 0 : requestAnimationFrame(paint);       // a one-off repaint leaves the loop as it found it
  }

  const CODE = {0: [0, "Clear"], 1: [.2, "Mostly clear"], 2: [.5, "Partly cloudy"], 3: [.9, "Overcast"],
    45: [.8, "Fog"], 48: [.8, "Freezing fog"], 51: [.7, "Light drizzle"], 53: [.8, "Drizzle"], 55: [.9, "Heavy drizzle"],
    61: [.8, "Light rain"], 63: [.9, "Rain"], 65: [1, "Heavy rain"], 66: [.9, "Freezing rain"], 67: [1, "Freezing rain"],
    71: [.8, "Light snow"], 73: [.9, "Snow"], 75: [1, "Heavy snow"], 77: [.8, "Snow grains"],
    80: [.8, "Showers"], 81: [.9, "Showers"], 82: [1, "Violent showers"], 85: [.9, "Snow showers"], 86: [1, "Snow showers"],
    95: [1, "Thunderstorm"], 96: [1, "Thunderstorm"], 99: [1, "Thunderstorm"]};

  function caption(txt, offer){
    const el = $("#wx"); if (!el) return;
    el.innerHTML = '<span class="wxdot" aria-hidden="true"></span>' + esc(txt)
      + (offer ? ' <button class="wxbtn" id="wxme" type="button">use my location</button>' : "");
    el.hidden = false;
    const b = $("#wxme");
    if (b) b.addEventListener("click", () => {
      if (!navigator.geolocation) return;
      caption("Finding you\u2026", false);
      navigator.geolocation.getCurrentPosition(
        pos => load(pos.coords.latitude, pos.coords.longitude, "Your area", false),
        () => caption(wx.place + (wx.text ? " \u00b7 " + wx.text : ""), true), {timeout: 8000});
    });
  }

  function load(lat, lon, place, offer){
    const u = "https://api.open-meteo.com/v1/forecast?latitude=" + lat + "&longitude=" + lon
      + "&current=temperature_2m,is_day,weather_code&temperature_unit=fahrenheit";
    fetch(u).then(r => r.ok ? r.json() : Promise.reject()).then(j => {
      const cur = j.current || {}, code = CODE[cur.weather_code] || [.3, "Clear"];
      wx.cloud = code[0];
      wx.rain = /rain|drizzle|shower|thunder/i.test(code[1]) ? 1 : 0;
      wx.snow = /snow/i.test(code[1]) ? 1 : 0;
      wx.fog = /fog/i.test(code[1]) ? 1 : 0;
      wx.night = cur.is_day === 0;
      wx.temp = Math.round(cur.temperature_2m);
      wx.place = place; wx.text = wx.temp + "\u00b0F, " + code[1].toLowerCase(); wx.ok = true;
      caption(place + " \u00b7 " + wx.text, offer);
      paint(performance.now(), true);
    }).catch(() => caption(place, offer));
  }

  size(); paint(t0);
  load(DC.lat, DC.lon, DC.name, true);
  const again = () => { if (!hero.offsetHeight) return; size(); paint(performance.now(), true); };      // sizing wipes the canvas, so always draw it again
  addEventListener("resize", again);
  if (window.ResizeObserver) { let rh = hero.offsetHeight, rt = 0; new ResizeObserver(() => { const h = hero.offsetHeight; if (!h || h === rh) return; rh = h; clearTimeout(rt); rt = setTimeout(again, 120); }).observe(hero); }
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(again);
  new MutationObserver(() => paint(performance.now(), true)).observe(document.documentElement, {attributes: true, attributeFilter: ["data-theme"]});
  hero.addEventListener("pointermove", e => { if (e.pointerType !== "mouse") return; const r = hero.getBoundingClientRect(); tmx = ((e.clientX - r.left) / r.width - .5) * 2; tmy = ((e.clientY - r.top) / Math.max(1, Math.min(r.height, innerHeight)) - .5) * 2; }, {passive: true});
  hero.addEventListener("pointerleave", () => { tmx = tmy = 0; });
  window.sceneStats = () => ({W, H, lay, sy, dark: isDark(), par: lastPar, night: wx.night});
  window.sceneNight = v => { wx.night = v; paint(performance.now(), true); };      // for checking the other palette by daylight
  window.fieldResume = () => { if (!raf) raf = requestAnimationFrame(paint); };
  new IntersectionObserver(es => es.forEach(e => { if (e.isIntersecting) { if (!raf && !calm()) raf = requestAnimationFrame(paint); } else if (raf) { cancelAnimationFrame(raf); raf = 0; } })).observe(c);
})();

/* ---------- counters ---------- */
$$("[data-count]").forEach(el => {
  const target = Number(el.dataset.count), t0 = performance.now() + 700, dur = calm() ? 1 : 1600;
  const tick = now => { const p = Math.max(0, Math.min(1, (now - t0) / dur)), e = 1 - Math.pow(1 - p, 3); el.textContent = Math.round(target * e).toLocaleString(); if (p < 1) requestAnimationFrame(tick); };
  requestAnimationFrame(tick);
});

/* ---------- the latest recorded votes, as a moving line under the hero ---------- */
(function(){
  const box = $("#ticker"), rail = $("#tickertrack"), list = BOOT.ticker || []; if (!box || !rail || !list.length) return;
  const lost = r => /^(not|fail|reject|defeat)/i.test(r || ""), day = d => d ? new Date(d + "T12:00:00").toLocaleDateString("en-US", {month: "short", day: "numeric"}) : "";
  const item = (v, dup) => `<a class="tk" href="#vote=${esc(String(v.v).replace(/\|/g, "_"))}" data-tk="${esc(v.v)}"${dup ? ' tabindex="-1" aria-hidden="true"' : ""}><b>${esc(v.b)}</b><span class="tkt">${esc(v.t)}</span><span class="tkres ${lost(v.r) ? "no" : "ok"}">${esc(v.r || "")} ${v.y ?? "?"}\u2013${v.n ?? "?"}</span><span class="tkd">${esc(v.c)}, ${esc(day(v.d))}</span></a>`;
  rail.innerHTML = `<span class="half">${list.map(v => item(v, false)).join("")}</span><span class="half">${list.map(v => item(v, true)).join("")}</span>`;
  rail.style.setProperty("--tick", Math.max(40, list.length * 5) + "s");
  box.hidden = false;
  // a keyboard reader gets a plain row they can move along, not a moving target
  box.addEventListener("focusin", e => { if (e.target.matches && e.target.matches(":focus-visible")) box.classList.add("kb"); });
  box.addEventListener("focusout", e => { if (!box.contains(e.relatedTarget)) box.classList.remove("kb"); });
  box.addEventListener("click", e => { const a = e.target.closest("[data-tk]"); if (a) track("ticker", {key: a.dataset.tk.replace(/\|/g, "_")}); });
})();

/* ---------- the featured bill's card leans a degree or two toward the pointer (mouse only, Motion on) ---------- */
(function(){
  const card = $("#heropanel"); if (!card || !matchMedia("(hover: hover) and (pointer: fine)").matches) return;
  card.addEventListener("pointermove", e => {
    if (calm() || e.pointerType !== "mouse") return;
    const r = card.getBoundingClientRect(), dx = (e.clientX - r.left) / r.width - .5, dy = (e.clientY - r.top) / r.height - .5, m = Math.hypot(dx, dy);
    card.style.rotate = m < .02 ? "" : `${(-dy).toFixed(3)} ${dx.toFixed(3)} 0 ${(m * 3).toFixed(2)}deg`;
  }, {passive: true});
  card.addEventListener("pointerleave", () => { card.style.rotate = ""; });
})();

/* ---------- members ---------- */
const mlist = $("#mlist");
function renderMembers(){
  if (!MEMBERS_READY) { mlist.innerHTML = `<li class="empty" style="padding:24px">Loading members\u2026</li>`; membersReady().then(renderMembers, () => { mlist.innerHTML = `<li class="empty" style="padding:24px">Couldn't load the member list. Check your connection and try again.</li>`; }); return; }
  const q = $("#mq").value.trim().toLowerCase();
  const list = DATA.members.filter(m => m.bills.length && (!q || m.name.toLowerCase().includes(q) || m.state.toLowerCase() === q)).sort((a, b) => b.bills.length - a.bills.length).slice(0, 12);
  mlist.innerHTML = list.map((m, i) => `<li style="--i:${i}"><button data-m="${esc(m.id)}">${avatar(m.id, m.party, "md")}<span class="mname"><b>${esc(prettyName(m))}</b><span class="muted">${esc(roleOf(m))}, ${esc(m.state)}</span></span><span class="mcount">${m.sponsored ? m.sponsored + " sponsored" : ""}${m.sponsored && m.cosponsored ? ", " : ""}${m.cosponsored ? m.cosponsored + " cosponsored" : ""}</span></button></li>`).join("") || `<li class="empty" style="padding:24px">No member matches. Try a last name or a two-letter state.</li>`;
}
$("#mq").addEventListener("input", renderMembers);
function pickMember(id){
  if (!CATALOG_READY) { catalogReady().then(() => pickMember(id), () => {}); return; }
  const m = MEMBER[id]; if (!m) return;
  m.set = m.set || new Set(m.bills); state.member = m;
  const L = (DATA.legislators || {})[id] || {}, yrs = d => d ? Math.floor((Date.now() - new Date(d + "T12:00:00")) / 3.15576e10) : null;
  const facts = [roleOf(m) + (L.d ? `, district ${L.d}` : "") + `, ${m.state}`, L.f ? `in Congress since ${L.f.slice(0, 4)} (${yrs(L.f)} yrs)` : "", L.b ? `age ${yrs(L.b)}` : ""].filter(Boolean).join(", ");
  const links = [L.u ? `<a href="${esc(L.u)}" target="_blank" rel="noopener">Official site</a>` : "", L.ph ? `<a href="tel:${esc(L.ph)}">${esc(L.ph)}</a>` : "", L.cf ? `<a href="${esc(L.cf)}" target="_blank" rel="noopener">Contact form</a>` : "", `<a href="https://www.congress.gov/member/${encodeURIComponent(prettyName(m).toLowerCase().replace(/[^a-z0-9]+/g, "-"))}/${esc(id)}" target="_blank" rel="noopener">Congress.gov</a>`].filter(Boolean).join("");
  $("#mpick").innerHTML = `<div class="prof">${avatar(id, m.party, "xl")}<div><b>${esc(prettyName(m))}</b><div class="muted">${esc(facts)}</div><div class="mlinks">${links}</div></div></div>
    <p><b>${m.bills.length}</b> bill${m.bills.length === 1 ? "" : "s"} in this set${m.sponsored ? `, ${m.sponsored} sponsored` : ""}${m.cosponsored ? `, ${m.cosponsored} cosponsored` : ""}. The list above now shows only theirs. <button class="chip" id="mclear">Show all bills</button></p>`;
  showPage("bills", true); render(); toast(`Showing bills for ${prettyName(m)}`);
}
mlist.addEventListener("click", e => { const btn = e.target.closest("button[data-m]"); if (btn) openMember(btn.dataset.m); });
$("#mpick").addEventListener("click", e => { if (e.target.id === "mclear") { state.member = null; $("#mpick").textContent = "Pick a member to filter the bill list above."; render(); } });
function toast(msg){ const t = $("#toast"); t.textContent = msg; t.classList.add("show"); clearTimeout(t._t); t._t = setTimeout(() => t.classList.remove("show"), 2200); }

/* ---------- sharing ----------
   Every bill with a full record and every roll call has its own small page
   (b/<key>.html, v/<vote>.html) that carries the link preview and sends the
   reader on to the site, so a pasted link shows a card. On a phone the
   system share sheet opens; on a desktop a small menu of places to post. */
const SHARE_BASE = BOOT.base || location.href.split("#")[0].replace(/\/[^\/]*$/, "");
const voteSlug = id => String(id).replace(/\|/g, "_");
const shareUrlBill = b => b.lite ? `${SHARE_BASE}/#bill=${b.key}` : `${SHARE_BASE}/b/${b.key}.html`;
const shareUrlVote = v => `${SHARE_BASE}/v/${voteSlug(v.vote_id)}.html`;
/* Counting, when a GoatCounter address was given at build time: page views per
   page, bill and vote, and share taps as events. No cookies, no personal data;
   nothing at all is sent when the address is empty. Calls made before the
   counter script has loaded wait in a queue. */
const gcq = [];
function gcSend(o){ if (!BOOT.analytics) return; if (window.goatcounter && goatcounter.count) { try { goatcounter.count(o); } catch (e) {} } else gcq.push(o); }
window.__gcflush = () => { while (gcq.length) gcSend(gcq.shift()); };
function track(name, props){ gcSend({path: name + (props && props.key ? "/" + props.key : ""), title: name, event: true}); }
function pageview(path, title){ gcSend({path, title: title || document.title}); }
function copyText(text){ (navigator.clipboard ? navigator.clipboard.writeText(text) : Promise.reject()).then(() => toast("Link copied"), () => prompt("Copy this link", text)); }
let shareMenu = null;
function share(o, anchor){
  track("share", o);
  if (navigator.share && matchMedia("(pointer: coarse)").matches) { navigator.share({title: o.title, text: o.text, url: o.url}).catch(() => {}); return; }
  if (!shareMenu) {
    shareMenu = document.createElement("div"); shareMenu.className = "sharemenu"; shareMenu.setAttribute("role", "menu"); shareMenu.hidden = true; document.body.appendChild(shareMenu);
    document.addEventListener("click", e => { if (!shareMenu.hidden && !shareMenu.contains(e.target) && !e.target.closest(".sharebtn")) shareMenu.hidden = true; });
    document.addEventListener("keydown", e => { if (e.key === "Escape" && !shareMenu.hidden) shareMenu.hidden = true; });
  }
  const text = o.text || o.title, u = encodeURIComponent(o.url), t = encodeURIComponent(text), tu = encodeURIComponent(text + " " + o.url);
  shareMenu.innerHTML = `<button class="sm-copy" role="menuitem">Copy link</button>
    <a role="menuitem" href="https://twitter.com/intent/tweet?text=${t}&url=${u}" target="_blank" rel="noopener">Post on X</a>
    <a role="menuitem" href="https://bsky.app/intent/compose?text=${tu}" target="_blank" rel="noopener">Post on Bluesky</a>
    <a role="menuitem" href="https://www.threads.net/intent/post?text=${tu}" target="_blank" rel="noopener">Post on Threads</a>
    <a role="menuitem" href="https://www.facebook.com/sharer/sharer.php?u=${u}" target="_blank" rel="noopener">Share on Facebook</a>
    <a role="menuitem" href="mailto:?subject=${encodeURIComponent(o.title)}&body=${encodeURIComponent(text + "\n\n" + o.url)}">Email</a>`;
  shareMenu.querySelector(".sm-copy").addEventListener("click", () => { copyText(o.url); shareMenu.hidden = true; });
  shareMenu.hidden = false;
  const r = anchor.getBoundingClientRect(), mw = shareMenu.offsetWidth;
  shareMenu.style.left = Math.max(8, Math.min(r.right + scrollX - mw, innerWidth + scrollX - mw - 8)) + "px";
  shareMenu.style.top = (r.bottom + scrollY + 6) + "px";
}
const shareTextBill = b => { const st = statusText(b); return `${b.id}, ${leadTitle(b)}: ${st.charAt(0).toLowerCase() + st.slice(1)}. Who backed it and how every member voted, from the record.`; };

/* ---------- top bar follows the dark map section ---------- */
(function(){
  const bar = $(".top"), th = $("#map"); if (!bar || !th) return;
  let tick = false;
  const check = () => { tick = false; const r = th.getBoundingClientRect(); bar.classList.toggle("over-dark", r.top < 62 && r.bottom > 62 && th.style.display !== "none"); bar.classList.toggle("scrolled", scrollY > 12); $("#totop").classList.toggle("show", scrollY > 1400); };
  addEventListener("scroll", () => { if (!tick) { tick = true; requestAnimationFrame(check); } }, {passive: true});
  check();
})();

/* ---------- the chamber floor, in 3D ----------
   Every member who took part in a roll call, seated in a hemicycle: Democrats to the left, Republicans to the
   right, independents between them, each party's seats grouped by state. A bright seat voted yes, a hollow one
   voted no, a gray one did not vote. Drag to look around; tap a seat for the member. It is drawn with WebGL and
   nothing else (no library to download), and where WebGL is missing the switch never appears. The seating is a
   diagram, not a seating chart: the House has no assigned seats. */
function makeChamber(canvas, onSeat){
  let gl = null;
  try { gl = canvas.getContext("webgl", {antialias: true, alpha: true, premultipliedAlpha: false, preserveDrawingBuffer: true}); } catch (e) {}
  if (!gl) return null;
  const compile = (type, src) => { const sh = gl.createShader(type); gl.shaderSource(sh, src); gl.compileShader(sh); return gl.getShaderParameter(sh, gl.COMPILE_STATUS) ? sh : null; };
  const program = (vs, fs) => { const a = compile(gl.VERTEX_SHADER, vs), b = compile(gl.FRAGMENT_SHADER, fs); if (!a || !b) return null; const pr = gl.createProgram(); gl.attachShader(pr, a); gl.attachShader(pr, b); gl.linkProgram(pr); return gl.getProgramParameter(pr, gl.LINK_STATUS) ? pr : null; };
  const seatsPr = program(`attribute vec3 aPos; attribute vec3 aCol; attribute float aKind; attribute float aDelay; attribute float aIdx; attribute float aMine;
    uniform mat4 uMVP; uniform float uScale; uniform float uSize; uniform float uT; uniform float uSel; uniform mediump float uGlow;
    varying vec3 vCol; varying float vKind; varying float vSel; varying float vMine;
    void main(){ vec4 q = uMVP * vec4(aPos, 1.0); gl_Position = q;
      float s = clamp((uT - aDelay) / 0.32, 0.0, 1.0); s = 1.0 - pow(1.0 - s, 3.0);
      vSel = abs(aIdx - uSel) < 0.5 ? 1.0 : 0.0;
      vMine = uGlow > 0.5 ? 0.0 : aMine;
      float grow = uGlow > 0.5 ? (aKind < 0.5 ? 2.7 : 0.0) : (1.0 + 0.42 * aMine);
      gl_PointSize = uSize * uScale / q.w * s * grow * (1.0 + 0.55 * vSel);
      vCol = aCol; vKind = aKind; }`,
    `precision mediump float; varying vec3 vCol; varying float vKind; varying float vSel; varying float vMine; uniform mediump float uGlow;
    void main(){ vec2 c = gl_PointCoord * 2.0 - 1.0; float r2 = dot(c, c); if (r2 > 1.0) discard;
      if (uGlow > 0.5) { float a = 1.0 - r2; gl_FragColor = vec4(vCol, a * a * 0.42); return; }
      float r = sqrt(r2);
      if (vMine > 0.5) {                                   // a reader's own members: a gold ring, a gap, then the seat as usual
        if (r > 0.82) { gl_FragColor = vec4(1.0, 0.84, 0.40, 1.0); return; }
        if (r > 0.70) discard;
        r = r / 0.70; r2 = r * r; }
      float z = sqrt(1.0 - r2), light = 0.50 + 0.50 * z;
      vec3 col = vCol * light + vec3(0.30) * pow(z, 8.0);
      if (vKind > 0.5 && vKind < 1.5) { float ring = smoothstep(0.52, 0.66, r); col = mix(vCol * 0.13, vCol * 0.95, ring); }
      if (vKind > 1.5) col = vCol * (0.55 + 0.25 * z);
      if (vSel > 0.5) { float ring = smoothstep(0.74, 0.84, r); col = mix(col, vec3(1.0), ring); }
      gl_FragColor = vec4(col, 1.0); }`);
  const linesPr = program(`attribute vec3 aPos; uniform mat4 uMVP; void main(){ gl_Position = uMVP * vec4(aPos, 1.0); }`,
    `precision mediump float; uniform vec4 uColor; void main(){ gl_FragColor = uColor; }`);
  if (!seatsPr || !linesPr) return null;
  const U = (pr, n) => gl.getUniformLocation(pr, n), A = (pr, n) => gl.getAttribLocation(pr, n);
  const buf = {pos: gl.createBuffer(), col: gl.createBuffer(), kind: gl.createBuffer(), delay: gl.createBuffer(), idx: gl.createBuffer(), mine: gl.createBuffer(), lines: gl.createBuffer()};
  const TONE = {D: [.494, .608, 1], R: [1, .482, .447], I: [.706, .608, .949], X: [.30, .33, .38]};
  let seats = [], P = new Float32Array(0), n = 0, senate = false, nLines = 0, nFloor = 0, mvp = new Float32Array(16), sizeWorld = .2, sizeNow = .2, scalePx = 1;
  let yaw = 0, pitch = .60, vyaw = 0, drag = null, moved = 0, sel = -1, t0 = performance.now(), raf = 0, idle = performance.now(), visible = true, dead = false;

  function layout(count){
    const rows = senate ? 4 : 10, r0 = senate ? 2.7 : 2.3, r1 = senate ? 4.7 : 6.4, rise = senate ? .30 : .21, radii = [];
    for (let k = 0; k < rows; k++) radii.push(r0 + (r1 - r0) * k / (rows - 1));
    const total = radii.reduce((a, b) => a + b, 0), per = radii.map(r => Math.floor(count * r / total));
    let left = count - per.reduce((a, b) => a + b, 0); for (let k = rows - 1; left > 0; k = (k - 1 + rows) % rows, left--) per[k]++;
    const out = [];
    per.forEach((c, k) => { for (let i = 0; i < c; i++) { const a = Math.PI * (.965 - .93 * (c === 1 ? .5 : i / (c - 1))); out.push({a, k, x: radii[k] * Math.cos(a), y: k * rise, z: -radii[k] * Math.sin(a)}); } });
    return out.sort((p, q) => q.a - p.a || p.k - q.k);
  }
  function show(isSenate, members){
    senate = isSenate; sel = -1;
    const rank = m => (m.p === "D" ? 0 : (m.p === "R" ? 2 : 1));
    seats = members.slice().sort((a, b) => rank(a) - rank(b) || String(a.L.st).localeCompare(String(b.L.st)) || (a.L.d || 0) - (b.L.d || 0) || String(a.L.n).localeCompare(String(b.L.n)));
    n = seats.length; const spots = layout(n); sizeWorld = senate ? .34 : .205;
    P = new Float32Array(n * 3); const C = new Float32Array(n * 3), K = new Float32Array(n), D = new Float32Array(n), I = new Float32Array(n), M = new Float32Array(n);
    seats.forEach((m, i) => { const sp = spots[i]; P.set([sp.x, sp.y, sp.z], i * 3);
      const kind = m.pos === "Y" ? 0 : (m.pos === "N" ? 1 : 2), tone = kind === 2 ? TONE.X : (TONE[m.p] || TONE.I);
      C.set(tone, i * 3); K[i] = kind; D[i] = (i / Math.max(1, n - 1)) * .62; I[i] = i; M[i] = m.mine ? 1 : 0; });
    const put = (b, data) => { gl.bindBuffer(gl.ARRAY_BUFFER, b); gl.bufferData(gl.ARRAY_BUFFER, data, gl.STATIC_DRAW); };
    put(buf.pos, P); put(buf.col, C); put(buf.kind, K); put(buf.delay, D); put(buf.idx, I); put(buf.mine, M);
    // the floor: three faint arcs, the centre aisle and the rostrum, so the seats sit in a room
    const L = [], arc = (r, y) => { for (let i = 0; i < 48; i++) { const a = Math.PI * i / 48, b = Math.PI * (i + 1) / 48; L.push(r * Math.cos(a), y, -r * Math.sin(a), r * Math.cos(b), y, -r * Math.sin(b)); } };
    const r0 = senate ? 2.7 : 2.3, r1 = senate ? 4.7 : 6.4; arc(r0 - .55, -.02); arc((r0 + r1) / 2, -.02); arc(r1 + .5, -.02);
    L.push(0, -.02, -(r0 - .55), 0, -.02, -(r1 + .5)); nFloor = L.length / 3;
    for (const [x0, x1, z0, z1] of [[-.9, .9, .35, .35], [-.9, .9, -.35, -.35], [-.9, -.9, .35, -.35], [.9, .9, .35, -.35]]) L.push(x0, .02, z0, x1, .02, z1);
    put(buf.lines, new Float32Array(L)); nLines = L.length / 3;
    t0 = performance.now(); idle = t0; yaw = calm() ? 0 : -.3; vyaw = 0; kick();
  }
  function camera(w, h){
    const f = 1 / Math.tan(.42), asp = w / Math.max(1, h), near = .1, far = 60, ty = senate ? .7 : 1.0, tz = senate ? -2.6 : -3.3;
    // far enough back that the ends of the back row fit across the frame, whatever its shape
    const dist = Math.max(senate ? 8.4 : 10.6, ((senate ? 4.7 : 6.4) + (senate ? .85 : .7)) / (Math.tan(.42) * asp) + (senate ? 1.85 : 2.65));
    sizeNow = sizeWorld * (asp < 1.3 ? 1.2 : 1);
    const pit = asp < 1.3 ? Math.max(pitch, .92) : pitch;                  // a taller frame (a phone): look down from higher, so the seats fill it
    const ex = Math.sin(yaw) * Math.cos(pit) * dist, ey = ty + Math.sin(pit) * dist, ez = tz + Math.cos(yaw) * Math.cos(pit) * dist;
    let fx = -ex, fy = ty - ey, fz = tz - ez; const fl = Math.hypot(fx, fy, fz); fx /= fl; fy /= fl; fz /= fl;
    let sx = -fz, sy = 0, sz = fx; const sl = Math.hypot(sx, sz) || 1; sx /= sl; sz /= sl;          // side = forward x up(0,1,0)
    const ux = sy * fz - sz * fy, uy = sz * fx - sx * fz, uz = sx * fy - sy * fx;
    const V = [sx, ux, -fx, 0, sy, uy, -fy, 0, sz, uz, -fz, 0, -(sx * ex + sy * ey + sz * ez), -(ux * ex + uy * ey + uz * ez), (fx * ex + fy * ey + fz * ez), 1];
    const Pm = [f / asp, 0, 0, 0, 0, f, 0, 0, 0, 0, (far + near) / (near - far), -1, 0, 0, 2 * far * near / (near - far), 0];
    for (let c = 0; c < 4; c++) for (let r = 0; r < 4; r++) { let t = 0; for (let k = 0; k < 4; k++) t += Pm[k * 4 + r] * V[c * 4 + k]; mvp[c * 4 + r] = t; }
    scalePx = h * .5 * f;
  }
  function draw(){
    const dpr = Math.min(2, window.devicePixelRatio || 1), w = Math.max(1, Math.round(canvas.clientWidth * dpr)), h = Math.max(1, Math.round(canvas.clientHeight * dpr));
    if (canvas.width !== w || canvas.height !== h) { canvas.width = w; canvas.height = h; }
    gl.viewport(0, 0, w, h); gl.clearColor(0, 0, 0, 0); gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
    if (!n) return;
    camera(w, h);
    const T = calm() ? 9 : (performance.now() - t0) / 1000;
    gl.useProgram(linesPr); gl.disable(gl.DEPTH_TEST); gl.enable(gl.BLEND); gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
    gl.uniformMatrix4fv(U(linesPr, "uMVP"), false, mvp); gl.uniform4f(U(linesPr, "uColor"), .62, .68, .78, .30);
    gl.bindBuffer(gl.ARRAY_BUFFER, buf.lines); const lp = A(linesPr, "aPos"); gl.enableVertexAttribArray(lp); gl.vertexAttribPointer(lp, 3, gl.FLOAT, false, 0, 0); gl.drawArrays(gl.LINES, 0, nFloor);
    gl.uniform4f(U(linesPr, "uColor"), .80, .84, .92, .62); gl.drawArrays(gl.LINES, nFloor, nLines - nFloor);      // the rostrum, a little brighter
    gl.useProgram(seatsPr);
    const bind = (name, b, size) => { const loc = A(seatsPr, name); if (loc < 0) return; gl.bindBuffer(gl.ARRAY_BUFFER, b); gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc, size, gl.FLOAT, false, 0, 0); };
    bind("aPos", buf.pos, 3); bind("aCol", buf.col, 3); bind("aKind", buf.kind, 1); bind("aDelay", buf.delay, 1); bind("aIdx", buf.idx, 1); bind("aMine", buf.mine, 1);
    gl.uniformMatrix4fv(U(seatsPr, "uMVP"), false, mvp); gl.uniform1f(U(seatsPr, "uScale"), scalePx); gl.uniform1f(U(seatsPr, "uSize"), sizeNow);
    gl.uniform1f(U(seatsPr, "uT"), T); gl.uniform1f(U(seatsPr, "uSel"), sel);
    gl.uniform1f(U(seatsPr, "uGlow"), 1); gl.blendFunc(gl.SRC_ALPHA, gl.ONE); gl.depthMask(false); gl.drawArrays(gl.POINTS, 0, n);      // the glow under the yes votes
    gl.uniform1f(U(seatsPr, "uGlow"), 0); gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA); gl.depthMask(true); gl.enable(gl.DEPTH_TEST); gl.drawArrays(gl.POINTS, 0, n);
  }
  function frame(){
    raf = 0; if (dead) return;
    const now = performance.now(), sweeping = !calm() && (now - t0) < 1300;
    if (!drag && !calm()) { if (Math.abs(vyaw) > .0004) { yaw += vyaw; vyaw *= .92; } else yaw += ((now - idle > 2600 ? .24 * Math.sin((now - idle - 2600) / 5200) : 0) - yaw) * .03; }
    yaw = Math.max(-1.25, Math.min(1.25, yaw));
    draw();
    if (visible && (sweeping || drag || (!calm() && (Math.abs(vyaw) > .0004 || Math.abs(yaw) > .002 || now - idle > 2600)))) kick();
  }
  function kick(){ if (!raf && !dead) raf = requestAnimationFrame(frame); }
  function pick(cx, cy){
    const r = canvas.getBoundingClientRect(), dpr = canvas.width / Math.max(1, r.width), px = (cx - r.left) * dpr, py = (cy - r.top) * dpr; let best = -1, bw = 1e9;
    for (let i = 0; i < n; i++) { const x = P[i * 3], y = P[i * 3 + 1], z = P[i * 3 + 2], w = mvp[3] * x + mvp[7] * y + mvp[11] * z + mvp[15]; if (w <= 0) continue;
      const sx = ((mvp[0] * x + mvp[4] * y + mvp[8] * z + mvp[12]) / w * .5 + .5) * canvas.width, sy = (1 - ((mvp[1] * x + mvp[5] * y + mvp[9] * z + mvp[13]) / w * .5 + .5)) * canvas.height;
      const rad = Math.max(sizeNow * scalePx / w * .5, 9 * dpr), d = Math.hypot(sx - px, sy - py); if (d <= rad && d < bw) { bw = d; best = i; } }      // the seat nearest the finger
    return best;
  }
  canvas.addEventListener("pointerdown", e => { drag = {x: e.clientX, y: e.clientY}; moved = 0; vyaw = 0; idle = performance.now(); canvas.classList.add("grabbing"); try { canvas.setPointerCapture(e.pointerId); } catch (x) {} });
  canvas.addEventListener("pointermove", e => {
    if (drag) { const dx = e.clientX - drag.x, dy = e.clientY - drag.y; moved += Math.abs(dx) + Math.abs(dy); yaw -= dx * .006; vyaw = -dx * .006; if (e.pointerType === "mouse") pitch = Math.max(.22, Math.min(1.25, pitch + dy * .004)); drag = {x: e.clientX, y: e.clientY}; idle = performance.now(); kick(); return; }
    if (e.pointerType === "mouse") { const i = pick(e.clientX, e.clientY); canvas.style.cursor = i >= 0 ? "pointer" : ""; onSeat(i >= 0 ? seats[i] : null, e.clientX, e.clientY, true); }
  });
  const release = e => { if (!drag) return; const tap = moved < 7; drag = null; canvas.classList.remove("grabbing"); idle = performance.now();
    if (tap) { const i = pick(e.clientX, e.clientY); sel = i; onSeat(i >= 0 ? seats[i] : null, e.clientX, e.clientY, false); } kick(); };
  canvas.addEventListener("pointerup", release); canvas.addEventListener("pointercancel", () => { drag = null; canvas.classList.remove("grabbing"); });
  canvas.addEventListener("pointerleave", () => onSeat(null, 0, 0, true));
  canvas.addEventListener("keydown", e => { if (e.key === "ArrowLeft" || e.key === "ArrowRight") { e.preventDefault(); yaw += e.key === "ArrowLeft" ? .16 : -.16; idle = performance.now(); kick(); } });
  new IntersectionObserver(es => es.forEach(x => { visible = x.isIntersecting; if (visible) kick(); })).observe(canvas);
  addEventListener("resize", kick);
  return {show, redraw: kick, draw, pick, select: i => { sel = i; kick(); }, selectId: id => { sel = seats.findIndex(m => m.id === id); kick(); return sel; }, stats: () => ({n, senate, lines: nLines, w: canvas.width, h: canvas.height, yaw, err: gl.getError()})};
}

/* ---------- roll calls: one load, used by the map and by "your members" ---------- */
function votesReady(){
  if (loads._votes) return loads._votes;
  return loads._votes = Promise.all([membersReady(), need("votes")]).then(([, V]) => {
    DATA.vote_meta = V.vote_meta || []; DATA.mv = V.mv || {}; DATA.states = V.states || {};
    DATA.vote_meta.forEach(v => VOTE_IDS.add(v.vote_id));
  }).catch(e => { delete loads._votes; throw e; });
}
/* every member of `st` on roll call `v`: their position, and their party as recorded that day */
function positionsFor(v, st){
  const C = (DATA.mv || {})[v.chamber === "Senate" ? "S" : "H"] || {ids: [], votes: {}}, str = C.votes[v.vote_id] || "", po = v.po || {}, out = [];
  for (let i = 0; i < str.length; i++) { const pos = str[i]; if (pos === ".") continue; const id = C.ids[i], L = DATA.legislators[id]; if (L && L.st === st) out.push({id, pos, L, p: po[i] || L.p}); }
  return out;
}

/* ---------- who a member is: the contact row and "Get to know" ----------
   The contact row sits at the top of the card, each entry with a symbol for what it is. There is no email:
   Congress publishes none, so the row offers the contact form where the roster has one. "Get to know" says
   who the member is without characterising anyone: facts from the roster, counts worked out from this site's
   own roll calls by a rule stated on the page, and one fenced paragraph from Wikipedia for life before Congress. */
const ICO = {
  web: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/>',
  phone: '<path d="M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2z"/>',
  mail: '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 7l9 6 9-6"/>',
  pin: '<path d="M12 21s-7-6.2-7-11a7 7 0 0 1 14 0c0 4.8-7 11-7 11z"/><circle cx="12" cy="10" r="2.5"/>',
  gov: '<path d="M3 21h18M5 21V10M9 21V10M15 21V10M19 21V10M3 10h18L12 4z"/>',
  x: '<path d="M5 4l14 16M19 4L5 20"/>',
  fb: '<path d="M14 8h3V4h-3a4 4 0 0 0-4 4v3H7v4h3v6h4v-6h3l1-4h-4V8z"/>',
  yt: '<rect x="3" y="6" width="18" height="12" rx="3"/><path d="M10 9.5v5l4.5-2.5z"/>',
  ig: '<rect x="4" y="4" width="16" height="16" rx="4"/><circle cx="12" cy="12" r="3.5"/><path d="M17 7h.01"/>',
  share: '<circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><path d="M8.6 13.5l6.8 4M15.4 6.5l-6.8 4"/>'
};
const ico = k => `<svg viewBox="0 0 24 24" aria-hidden="true">${ICO[k]}</svg>`;
const ract = (k, label, href, plain) => `<a class="ract" href="${esc(href)}"${plain ? "" : ' target="_blank" rel="noopener"'}>${ico(k)}<span>${esc(label)}</span></a>`;
ICO.user = '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>';
const contactRow = (L, cg, shareLabel, pre, profileId) => `<div class="rep-top">${profileId ? `<button class="ract" type="button" data-profile="${esc(profileId)}">${ico("user")}<span>Full profile</span></button>` : ""}${L.u ? ract("web", "Website", L.u) : ""}${L.ph ? ract("phone", L.ph, "tel:" + L.ph, true) : ""}${L.cf ? ract("mail", "Contact form", L.cf) : ""}${ract("gov", "Congress.gov", cg)}<span class="rep-social" id="${pre}social"></span><button class="ract sharebtn" id="share${pre}" type="button">${ico("share")}<span>${esc(shareLabel)}</span></button></div>`;
const socialRow = S => !S ? "" : (S.twitter ? ract("x", "@" + S.twitter, "https://x.com/" + S.twitter) : "") + (S.facebook ? ract("fb", "Facebook", "https://www.facebook.com/" + S.facebook) : "")
  + (S.youtube ? ract("yt", "YouTube", "https://www.youtube.com/" + S.youtube) : "") + (S.instagram ? ract("ig", "Instagram", "https://www.instagram.com/" + S.instagram) : "");
function knowHTML(P, L, party, id){
  const S = P.service, C = P.committees || [], V = P.votes, F = P.focus, W = P.wiki, last = L.n.split(" ").slice(-1)[0];
  const fact = `<span class="tag fact">Fact</span>`, ana = `<span class="tag analysis">Analysis</span>`;
  const mon = d => d ? new Date(d + "T12:00:00").toLocaleDateString("en-US", {month: "long", year: "numeric"}) : "";
  const years = d => d ? Math.max(0, Math.floor((Date.now() - new Date(d + "T12:00:00")) / 3.15576e10)) : null;
  const pctOf = (a, b) => b ? Math.round(100 * a / b) : 0, plural = (n, w) => `${n.toLocaleString()} ${w}${n === 1 ? "" : "s"}`;
  let h = "";
  if (S) {
    const y = years(S.since);
    h += `<div class="know-b"><h4>${fact} In office</h4><p>In the ${esc(S.chamber)} since <b>${esc(mon(S.since))}</b>${S.appointed ? " (first appointed to the seat)" : ""}: term ${S.terms}${y != null ? `, ${plural(y, "year")}` : ""}.${S.other ? ` Before that, in the ${esc(S.other.chamber)} from ${esc(S.other.from)} to ${esc(S.other.to)}.` : ""}${S.parties && S.parties.length > 1 ? ` Party over time: ${S.parties.map(esc).join(", then ")}.` : ""}${S.next ? ` The seat is next on the ballot in <b>November ${esc(String(S.next))}</b>.` : ""}</p>${L.of ? `<p class="know-line">${ico("pin")}<span>${esc(L.of)}, Washington, DC</span></p>` : ""}</div>`;
  }
  if (C.length) h += `<div class="know-b"><h4>${fact} Committees</h4><ul class="know-list">${C.map(c => `<li><b>${esc(c.name)}</b>${c.title ? `<span class="role">${esc(c.title)}</span>` : ""}${c.subs && c.subs.length ? `<details><summary>${plural(c.subs.length, "subcommittee")}</summary><ul>${c.subs.map(s => `<li>${esc(s.name)}${s.title ? `<span class="role">${esc(s.title)}</span>` : ""}</li>`).join("")}</ul></details>` : ""}</li>`).join("")}</ul></div>`;
  if (V && !V.n && V.eligible) h += `<div class="know-b"><h4>${ana} How ${esc(last)} votes</h4><p>${esc(last)} sits as an independent, so there is no party line to measure against. Cast a yes or a no on ${plural(V.cast || 0, "recorded vote")} and missed ${V.missed.toLocaleString()} of ${plural(V.eligible, "roll call")} (${pctOf(V.missed, V.eligible)}%).</p><p class="know-rule">Counted from this Congress's recorded votes, as far as this site holds them member by member. Party is the one recorded on each roll call.</p></div>`;
  if (V && V.n) {
    const side = V.party === "R" ? "Republicans" : "Democrats", tone = V.party === "R" ? "rep" : "dem";
    const head = V.split_n ? `<div class="know-big"><b>${pctOf(V.split_with, V.split_n)}%</b><span>of the ${plural(V.split_n, "vote")} where the two parties split, ${esc(last)} sided with ${side}</span></div><div class="know-bar" style="--pc:var(--${tone})"><i style="width:${pctOf(V.split_with, V.split_n)}%"></i></div>` : "";
    const breaks = V.split_n ? (V.breaks && V.breaks.length ? `<p class="know-sub">${V.breaks_n > V.breaks.length ? `The ${V.breaks.length} most recent of ${V.breaks_n} breaks with the party` : (V.breaks_n === 1 ? "The one break with the party" : `All ${V.breaks_n} breaks with the party`)}</p><ul class="know-list">${V.breaks.map(b => `<li><a class="replink" href="#vote=${esc(voteSlug(b.vote_id))}" data-vote="${esc(b.vote_id)}"><b>${esc(b.bill)}</b> ${esc(b.title)}</a> <span class="muted">${esc(String(b.category).toLowerCase())}, ${esc(fmtDate(b.date))}: voted ${b.pos === "Y" ? "yes" : "no"}</span></li>`).join("")}</ul>` : `<p class="muted">No break with the party on a split vote in this record.</p>`) : "";
    const allBreaks = (id && V.breaks_n) ? `<a class="chip know-breaks" href="#member=${esc(id)}/breaks" data-profile="${esc(id)}" data-show="breaks">See ${V.breaks_n === 1 ? "that vote" : "all " + V.breaks_n.toLocaleString() + " of those votes"}, and how everyone else voted</a>` : "";
    h += `<div class="know-b"><h4>${ana} How ${esc(last)} votes</h4>${head}<p>Across all ${plural(V.n, "recorded vote")} cast, voted the way most ${side} did ${pctOf(V.with, V.n)}% of the time.${V.eligible ? ` Missed ${V.missed.toLocaleString()} of ${plural(V.eligible, "roll call")} (${pctOf(V.missed, V.eligible)}%).` : ""}</p>${breaks}${allBreaks}<p class="know-rule">How this is worked out: a vote counts as a party split when most Democrats voted one way and most Republicans the other. Party is the one recorded on each roll call. Only this Congress's recorded votes are counted, and only those this site holds member by member.</p></div>`;
  }
  if (F && (F.sponsored || F.cosponsored)) h += `<div class="know-b"><h4>${ana} What ${esc(last)} works on</h4><p>Sponsored <b>${plural(F.sponsored, "bill")}</b> this Congress${F.laws ? `; ${F.laws === 1 ? "one became law" : F.laws + " became law"}` : ""}.${F.cosponsored ? ` Cosponsored ${F.cosponsored.toLocaleString()}.` : ""}</p>${F.areas && F.areas.length ? `<div class="know-chips">${F.areas.map(a => `<span class="pill">${esc(a[0])} <b>${a[1]}</b></span>`).join("")}</div><p class="know-rule">The subjects are the Library of Congress policy areas of the bills ${esc(last)} sponsored, most frequent first.</p>` : ""}</div>`;
  if (W && W.extract) h += `<div class="know-b know-wiki"><h4><span class="tag wiki">From Wikipedia</span> Before Congress, and beyond it</h4><p>${esc(W.extract)}</p><p class="know-rule">This is the opening of the Wikipedia article <a href="${esc(W.url)}" target="_blank" rel="noopener">${esc(W.title)}</a>. It is <b>not an official record</b>, and anyone can edit it. Text under <a href="https://creativecommons.org/licenses/by-sa/4.0/" target="_blank" rel="noopener">CC BY-SA 4.0</a>.</p></div>`;
  return h;
}

/* ---------- a bill's own vote maps ----------
   The Vote map page lists every roll call there is. Inside a bill the same map is
   offered for that bill's roll calls only, so a reader can flip from the House vote
   to the Senate vote without leaving the bill. States are drawn the way the big map
   draws them; district lines and member cards stay on the big map, which opens from
   here already narrowed to this bill. */
let bmapSeq = 0;
function billMapHTML(b){
  const n = (b.votes || []).filter(v => v.map).length; if (!n) return "";
  return `<div class="bmap" data-key="${esc(b.key)}"><div class="bmap-head"><h4>This bill's recorded votes, state by state</h4><button class="chip" type="button" data-full>Open on the full map</button></div><div class="bmap-body"><p class="muted loading">Loading the roll calls\u2026</p></div></div>`;
}
function armBillMap(card){ const bm = $(".pane.show .bmap", card); if (bm) initBillMap(bm); }
function initBillMap(host){
  if (host.dataset.ready) return; host.dataset.ready = "1";
  votesReady().then(() => drawBillMap(host), () => { delete host.dataset.ready; $(".bmap-body", host).innerHTML = `<p class="muted">Couldn't load the roll calls. Check your connection and open this tab again.</p>`; });
}
function drawBillMap(host){
  const key = host.dataset.key, uid = "bm" + (++bmapSeq), votes = DATA.vote_meta.filter(v => v.bill_key === key), body = $(".bmap-body", host), states = DATA.states || {};
  if (!votes.length) { body.innerHTML = `<p class="muted">No member-level roll calls for this bill.</p>`; return; }
  $("h4", host).textContent = votes.length === 1 ? "The recorded vote, state by state" : `This bill's ${votes.length} recorded votes, state by state`;
  const NS = "http://www.w3.org/2000/svg", el = (tag, attrs) => { const e = document.createElementNS(NS, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); return e; };
  const arrow = d => `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="${d}"/></svg>`, many = votes.length > 1, legend = $("#pg-map .legend2");
  body.innerHTML = `<div class="votebar">${many ? `<button class="iconbtn" type="button" data-step="-1" aria-label="Newer vote">${arrow("M15 6l-6 6 6 6")}</button>` : ""}<label class="selwrap"><span class="sr-only">Vote</span><select aria-label="Choose one of this bill's recorded votes">${votes.map(v => `<option value="${esc(v.vote_id)}">${esc(v.chamber)} ${esc(v.category.toLowerCase())}, ${esc(fmtDate(v.date))} (${v.yeas ?? "?"}\u2013${v.nays ?? "?"})</option>`).join("")}</select>${arrow("M6 9l6 6 6-6")}</label>${many ? `<button class="iconbtn" type="button" data-step="1" aria-label="Older vote">${arrow("M9 6l6 6-6 6")}</button>` : ""}</div>
    <div class="mapsub"></div><div class="mapframe"><svg class="usmap" viewBox="0 0 975 610" role="img" aria-label="Map of the United States colored by how each state's members voted on this bill"></svg></div>${legend ? legend.outerHTML : ""}<div class="bmap-side"><span class="muted">Tap a state for its members' names.</span></div>`;
  const svg = $("svg.usmap", body), pick = $("select", body), sub = $(".mapsub", body), side = $(".bmap-side", body);
  const defs = el("defs", {});
  for (const base of ["rep", "dem", "plum"]) {
    const pat = el("pattern", {id: `${uid}-hatch-${base}`, patternUnits: "userSpaceOnUse", width: 6, height: 6, patternTransform: "rotate(45)"});
    const bg = el("rect", {width: 6, height: 6}); bg.setAttribute("style", `fill:var(--${base});opacity:.22`);
    const bar = el("rect", {width: 2.4, height: 6}); bar.setAttribute("style", `fill:var(--${base})`);
    pat.appendChild(bg); pat.appendChild(bar); defs.appendChild(pat);
  }
  svg.appendChild(defs);
  const groups = {};
  for (const [st, s] of Object.entries(states)) {
    const g = el("g", {class: "state", "data-st": st}), cp = el("clipPath", {id: `${uid}-cp-${st}`}); cp.appendChild(el("path", {d: s.d})); g.appendChild(cp);
    const fill = el("g", {class: "fill", "clip-path": `url(#${uid}-cp-${st})`}); g.appendChild(fill); g.appendChild(el("path", {class: "outline", d: s.d}));
    const hit = el("path", {class: "hit", d: s.d}); hit.addEventListener("click", () => showState(st)); g.appendChild(hit);
    const [x0, y0, x1, y1] = s.bbox;
    if ((x1 - x0) > 24 && (y1 - y0) > 18) { const t = el("text", {class: "abbr", x: (x0 + x1) / 2, y: (y0 + y1) / 2 + 4, "text-anchor": "middle"}); t.textContent = st; g.appendChild(t); }
    svg.appendChild(g); groups[st] = {fill, s};
  }
  const tone = p => p === "R" ? "rep" : (p === "D" ? "dem" : "plum");
  const fillFor = (p, pos) => (pos === "X" || pos === "P") ? "var(--line-strong)" : (pos === "Y" ? `var(--${tone(p)})` : `url(#${uid}-hatch-${tone(p)})`);
  const order = m => ({R: 0, D: 4, I: 2}[m.p] ?? 2) + (m.pos === "Y" ? (m.p === "D" ? 1 : 0) : (m.pos === "N" ? (m.p === "D" ? 0 : 1) : .5));
  const POSN = {Y: "Yes", N: "No", P: "Present", X: "Not voting"};
  let current = votes[0], picked = null;
  function paint(vid){
    current = votes.find(v => v.vote_id === vid) || votes[0];
    for (const [st, {fill, s}] of Object.entries(groups)) {
      fill.innerHTML = "";
      const ms = positionsFor(current, st).sort((a, b) => order(a) - order(b)), [x0, y0, x1, y1] = s.bbox, w = x1 - x0, h = y1 - y0;
      if (!ms.length) { const r = el("rect", {x: x0, y: y0, width: w, height: h}); r.setAttribute("style", "fill:var(--line-strong);opacity:.55"); fill.appendChild(r); continue; }
      if (current.chamber === "Senate" && ms.length === 2 && fillFor(ms[0].p, ms[0].pos) !== fillFor(ms[1].p, ms[1].pos)) {
        const a = el("polygon", {points: `${x0},${y0} ${x1},${y0} ${x0},${y1}`}); a.setAttribute("style", `fill:${fillFor(ms[0].p, ms[0].pos)}`);
        const c = el("polygon", {points: `${x1},${y0} ${x1},${y1} ${x0},${y1}`}); c.setAttribute("style", `fill:${fillFor(ms[1].p, ms[1].pos)}`);
        fill.appendChild(a); fill.appendChild(c); continue;
      }
      const bands = []; for (const m of ms) { const f = fillFor(m.p, m.pos); if (bands.length && bands[bands.length - 1].f === f) bands[bands.length - 1].n++; else bands.push({f, n: 1}); }
      let x = x0; for (const bd of bands) { const bw = w * bd.n / ms.length, r = el("rect", {x, y: y0, width: bw, height: h}); r.setAttribute("style", `fill:${bd.f}`); fill.appendChild(r); x += bw; }
    }
    const rows = []; for (const m of String(current.split || "").matchAll(/\b([A-Z]+)\s+(\d+)\s*-\s*(\d+)/g)) { const q = m[1][0]; rows.push({p: q, y: +m[2], n: +m[3], name: q === "D" ? "Democrats" : (q === "R" ? "Republicans" : "Independents"), c: tone(q)}); }
    const max = Math.max(1, ...rows.map(r => r.y + r.n)); rows.sort((a, b) => ({D: 0, I: 1, R: 2}[a.p] ?? 1) - ({D: 0, I: 1, R: 2}[b.p] ?? 1));
    const passed = /passed|agreed|invoked|adopted|confirmed/i.test(current.result || "");
    sub.innerHTML = `<div class="tally"><b class="num"><span class="v">${esc(String(current.yeas ?? "?"))}</span><span>\u2013</span><span class="v">${esc(String(current.nays ?? "?"))}</span></b><span class="res ${passed ? "pass" : "fail"}">${esc(current.result || "")}</span><button class="chip sharebtn" type="button" data-sharevote>Share this vote</button></div>
      <div class="tsub">${esc(current.chamber)} ${esc(current.category.toLowerCase())}, ${esc(fmtDate(current.date))}.${current.url ? ` <a href="${esc(current.url)}" target="_blank" rel="noopener">Official roll call</a>` : ""}</div>
      ${rows.length ? `<div class="split">${rows.map(r => `<div style="--pc:var(--${r.c})"><span>${esc(r.name)}</span><span class="bar" aria-hidden="true"><i class="y" style="width:${(100 * r.y / max).toFixed(1)}%"></i><i class="n" style="width:${(100 * r.n / max).toFixed(1)}%"></i></span><span><b>${r.y}</b> yes, <b>${r.n}</b> no</span></div>`).join("")}</div>` : ""}`;
    if (picked) showState(picked);
  }
  function showState(st){
    picked = st; $$("g.state", svg).forEach(g => g.classList.toggle("sel", g.dataset.st === st));
    const name = (states[st] || {}).name || st, ms = positionsFor(current, st).sort((a, b) => ((a.L.d || 0) - (b.L.d || 0)) || a.L.n.localeCompare(b.L.n));
    side.innerHTML = ms.length ? `<h5>${esc(name)}: ${esc(current.chamber)}</h5><div class="bmap-mems">${ms.map(m => `<span class="bmem">${avatar(m.id, m.p, "sm")}<b>${esc(m.L.n)}</b><span class="vtag ${esc(m.pos)}">${POSN[m.pos] || m.pos}</span></span>`).join("")}</div>`
      : `<span class="muted">No ${esc(current.chamber)} members from ${esc(name)} appear in this roll call.</span>`;
  }
  pick.addEventListener("change", () => paint(pick.value));
  body.addEventListener("click", e => {
    const st = e.target.closest("[data-step]"); if (st) { const i = pick.selectedIndex + (+st.dataset.step); if (i >= 0 && i < pick.options.length) { pick.selectedIndex = i; paint(pick.value); } return; }
    const sv = e.target.closest("[data-sharevote]"); if (sv) share({title: `${current.bill}: ${current.chamber} ${current.category.toLowerCase()}, ${current.yeas ?? "?"}\u2013${current.nays ?? "?"}`, text: `How every ${current.chamber} member voted on ${current.bill}, ${current.title}, state by state:`, url: shareUrlVote(current), kind: "vote", key: current.vote_id}, sv);
  });
  $("[data-full]", host).addEventListener("click", () => { showPage("map", true); mapReady().then(() => { if (window.mapFilter) mapFilter(key, current.vote_id); }); });
  paint(votes[0].vote_id);
}

/* ---------- vote map ---------- */
let mapInit = null;
function mapReady(){
  if (mapInit) return mapInit;
  const note = $("#mapnote"); if (note) note.textContent = "Loading the vote record\u2026";
  return mapInit = votesReady().then(() => initMap()).catch(e => { mapInit = null; if (note) note.textContent = "Couldn't load the vote record. Check your connection and open the map again."; });
}
function initMap(){
  const svg = $("#usmap"), sel = $("#vsel"), side = $("#mapside"), states = DATA.states || {}, LEG = DATA.legislators || {}, MVC = DATA.mv || {};
  let DIST = BOOT.inline ? (BOOT.inline.districts || {states: {}, q: 50}) : {states: {}, q: 50, pending: true}, DQ = DIST.q || 50;
  const VB0 = [0, 0, 975, 610];
  let vb = VB0.slice(), zoomed = null, zoomAnim = 0;
  const votes = DATA.vote_meta || [];
  if (!votes.length || !Object.keys(states).length) { $("#map").style.display = "none"; return; }
  const NS = "http://www.w3.org/2000/svg";
  const el = (tag, attrs) => { const e = document.createElementNS(NS, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); return e; };
  const fillFor = (p, pos) => {
    if (pos === "X" || pos === "P") return "var(--line-strong)";
    const base = p === "R" ? "rep" : (p === "D" ? "dem" : "plum");
    return pos === "Y" ? `var(--${base})` : `url(#hatch-${base})`;
  };
  // defs: hatch patterns
  const defs = el("defs", {});
  for (const base of ["rep", "dem", "plum"]) {
    const pat = el("pattern", {id: `hatch-${base}`, patternUnits: "userSpaceOnUse", width: 6, height: 6, patternTransform: "rotate(45)"});
    const bg = el("rect", {width: 6, height: 6}); bg.setAttribute("style", `fill:var(--${base});opacity:.22`);
    const bar = el("rect", {width: 2.4, height: 6}); bar.setAttribute("style", `fill:var(--${base})`);
    pat.appendChild(bg); pat.appendChild(bar); defs.appendChild(pat);
  }
  svg.appendChild(defs);
  const groups = {};
  for (const [st, s] of Object.entries(states)) {
    const g = el("g", {class: "state", "data-st": st});
    const cp = el("clipPath", {id: `cp-${st}`}); cp.appendChild(el("path", {d: s.d})); g.appendChild(cp);
    const fill = el("g", {class: "fill", "clip-path": `url(#cp-${st})`}); g.appendChild(fill);
    g.appendChild(el("path", {class: "outline", d: s.d}));
    const hit = el("path", {class: "hit", d: s.d}); hit.addEventListener("click", () => pick(st)); g.appendChild(hit);
    const [x0, y0, x1, y1] = s.bbox;
    if ((x1 - x0) > 24 && (y1 - y0) > 18) { const t = el("text", {class: "abbr", x: (x0 + x1) / 2, y: (y0 + y1) / 2 + 4, "text-anchor": "middle"}); t.textContent = st; g.appendChild(t); }
    svg.appendChild(g); groups[st] = {g, fill, s};
  }
  let current = null, selected = null;
  const VM = Object.fromEntries(votes.map(v => [v.vote_id, v]));
  /* two ways to see a roll call: the state map, and the chamber floor */
  const chCanvas = $("#chamber"), chInfo = $("#chinfo"), chTip = $("#chtip"), viewSw = $("#viewsw"); let view = "map", chamber = null;
  const CHHINT = `<span class="muted">One seat for every member who took part. Bright is yes, hollow is no, gray did not vote. Drag to look around; tap a seat.</span>`;
  const everyone = vid => { const v = VM[vid], C = MVC[v && v.chamber === "Senate" ? "S" : "H"] || {ids: [], votes: {}}, str = C.votes[vid] || "", po = (v && v.po) || {}, out = [];
    for (let i = 0; i < str.length; i++) { const pos = str[i]; if (pos === ".") continue; const id = C.ids[i], L = LEG[id]; if (L) out.push({id, pos, L, p: po[i] || L.p}); } return out; };
  function onSeat(m, x, y, hover){
    if (hover) { if (!m) { chTip.classList.remove("show"); return; } const r = $(".stage").getBoundingClientRect(); chTip.style.left = (x - r.left) + "px"; chTip.style.top = (y - r.top) + "px";
      chTip.innerHTML = `<b>${esc(m.L.n)}</b>${esc(m.p)}-${esc(m.L.st)}: ${{Y: "Yes", N: "No", P: "Present", X: "Not voting"}[m.pos] || esc(m.pos)}`; chTip.classList.add("show"); return; }
    chTip.classList.remove("show");
    if (!m) { chInfo.innerHTML = CHHINT; return; }
    const seat = current.chamber === "Senate" ? "Senator" : (m.L.d ? `District ${m.L.d}` : "At large");
    chInfo.innerHTML = `${avatar(m.id, m.p, "md")}<span class="ch-who"><b>${esc(m.L.n)}</b><span class="muted">${esc(PARTY[m.p] || m.p)}, ${esc((states[m.L.st] || {}).name || m.L.st)} \u00b7 ${esc(seat)}</span></span><span class="vtag ${esc(m.pos)}">${POSW[m.pos] || m.pos}</span><button class="chip" type="button" data-card="${esc(m.id)}">Their card</button><button class="chip" type="button" data-profile="${esc(m.id)}">Full profile</button>`;
  }
  chInfo.addEventListener("click", e => { const c = e.target.closest("[data-card]"), f = e.target.closest("[data-profile]");
    if (c) { const m = everyone(current.vote_id).find(x => x.id === c.dataset.card); if (m) openRep(m, m.L.st); } else if (f) openMember(f.dataset.profile); });
  /* The reader's own members, if they have told the site where they live: the state they picked under "How did
     your members vote?", and the district "Use my location" found. Both are kept on this device only. */
  const myPlace = () => { let st = "", d = null; try { st = localStorage.getItem("state") || ""; const sd = localStorage.getItem("district"); d = (sd === null || sd === "") ? null : +sd; } catch (e) {} return {st, d}; };
  function showChamber(){
    if (!chamber) return;
    const {st, d} = myPlace(), all = everyone(current.vote_id), name = (states[st] || {}).name || st;
    all.forEach(m => { m.mine = !!st && m.L.st === st; });
    chamber.show(current.chamber === "Senate", all);
    const mine = all.filter(m => m.mine), own = (d != null && current.chamber !== "Senate") ? mine.find(m => (m.L.d || 0) === d) : null;
    if (own && chamber.selectId(own.id) >= 0) { onSeat(own, 0, 0, false); chInfo.insertAdjacentHTML("afterbegin", `<span class="ch-yours">Your representative</span>`); return; }
    const said = m => `${esc(m.L.n.split(" ").slice(-1)[0])} ${(POSW[m.pos] || m.pos).toLowerCase()}`;
    chInfo.innerHTML = CHHINT + (mine.length ? `<span class="ch-mine"><i aria-hidden="true"></i>${esc(name)}'s ${mine.length <= 3 ? "members: " + mine.map(said).join(", ") : mine.length + " members are ringed in gold"}</span>`
      : (st ? "" : `<span class="ch-mine"><a href="#yours">Pick your state</a>&nbsp;and its seats are ringed in gold here.</span>`));
  }
  function setView(v){
    if (v === "chamber" && !chamber) { chamber = makeChamber(chCanvas, onSeat); if (!chamber) { viewSw.hidden = true; v = "map"; } }
    view = v; try { localStorage.setItem("mapview", v); } catch (e) {}
    $$("button", viewSw).forEach(b => b.setAttribute("aria-pressed", b.dataset.view === v));
    if (v === "chamber") zoomOut();
    svg.style.display = v === "map" ? "" : "none"; chCanvas.hidden = v !== "chamber"; chInfo.hidden = v !== "chamber"; $(".stage").classList.toggle("chamber-on", v === "chamber");
    if (v === "chamber" && current) showChamber();
  }
  if (window.WebGLRenderingContext) { viewSw.hidden = false; viewSw.addEventListener("click", e => { const b = e.target.closest("button[data-view]"); if (b) setView(b.dataset.view); }); }
  window.mapView = setView; window.chamberStats = () => chamber && chamber.stats();
  const membersByState = vid => {
    const v = VM[vid], C = MVC[v && v.chamber === "Senate" ? "S" : "H"] || {ids: [], votes: {}}, str = C.votes[vid] || "", po = (v && v.po) || {}, out = {};
    for (let i = 0; i < str.length; i++) {
      const pos = str[i]; if (pos === ".") continue;
      const id = C.ids[i], L = LEG[id]; if (!L) continue;
      (out[L.st] = out[L.st] || []).push({id, pos, L, p: po[i] || L.p});
    }
    return out;
  };
  const parseSplit = s => {
    const out = [];
    for (const m of String(s || "").matchAll(/\b([A-Z]+)\s+(\d+)\s*-\s*(\d+)/g)) {
      const p = m[1][0], y = +m[2], n = +m[3];
      out.push({p, y, n, name: p === "D" ? "Democrats" : (p === "R" ? "Republicans" : "Independents"), c: p === "D" ? "dem" : (p === "R" ? "rep" : "plum")});
    }
    const max = Math.max(1, ...out.map(r => r.y + r.n));
    out.forEach(r => { r.yp = 100 * r.y / max; r.np = 100 * r.n / max; });
    return out.sort((a, b) => ({D: 0, I: 1, R: 2}[a.p] ?? 1) - ({D: 0, I: 1, R: 2}[b.p] ?? 1));
  };
  const order = m => ({R: 0, D: 4, I: 2}[m.p] ?? 2) + (m.pos === "Y" ? (m.p === "D" ? 1 : 0) : (m.pos === "N" ? (m.p === "D" ? 0 : 1) : 0.5));
  function paint(vid){
    current = votes.find(v => v.vote_id === vid); if (!current) return;
    const by = membersByState(vid);
    svg.classList.add("swap");
    for (const [st, {fill, s}] of Object.entries(groups)) {
      fill.innerHTML = "";
      const ms = (by[st] || []).sort((a, b) => order(a) - order(b));
      const [x0, y0, x1, y1] = s.bbox, w = x1 - x0, h = y1 - y0;
      fill.style.setProperty("--d", Math.round(x0 / 975 * 520) + "ms");
      if (!ms.length) { const r = el("rect", {x: x0, y: y0, width: w, height: h}); r.setAttribute("style", "fill:var(--line-strong);opacity:.55"); fill.appendChild(r); continue; }
      if (current.chamber === "Senate" && ms.length === 2 && fillFor(ms[0].p, ms[0].pos) !== fillFor(ms[1].p, ms[1].pos)) {
        const a = el("polygon", {points: `${x0},${y0} ${x1},${y0} ${x0},${y1}`}); a.setAttribute("style", `fill:${fillFor(ms[0].p, ms[0].pos)}`);
        const b = el("polygon", {points: `${x1},${y0} ${x1},${y1} ${x0},${y1}`}); b.setAttribute("style", `fill:${fillFor(ms[1].p, ms[1].pos)}`);
        fill.appendChild(a); fill.appendChild(b); continue;
      }
      // proportional vertical bands, merged by fill
      const bands = []; for (const m of ms) { const f = fillFor(m.p, m.pos); if (bands.length && bands[bands.length - 1].f === f) bands[bands.length - 1].n++; else bands.push({f, n: 1}); }
      let x = x0; for (const b of bands) { const bw = w * b.n / ms.length; const r = el("rect", {x, y: y0, width: bw, height: h}); r.setAttribute("style", `fill:${b.f}`); fill.appendChild(r); x += bw; }
    }
    void svg.offsetWidth; svg.classList.remove("swap");
    const yes = (current.yeas ?? "?"), no = (current.nays ?? "?");
    const passed = /passed|agreed|invoked|adopted|confirmed/i.test(current.result || ""), rows = parseSplit(current.split);
    $("#mapsub").innerHTML = `<div class="tally"><b class="num"><span class="v yv">${esc(String(yes))}</span><span>–</span><span class="v nv">${esc(String(no))}</span></b><span class="res ${passed ? "pass" : "fail"}">${esc(current.result || "")}</span><button class="chip sharebtn" id="sharevote" type="button">Share this vote</button></div>
      <div class="tsub"><b>${esc(current.bill)}</b> ${esc(current.title)}. ${esc(current.chamber)} ${esc(current.category.toLowerCase())}, ${esc(fmtDate(current.date))}.${current.url ? ` <a href="${esc(current.url)}" target="_blank" rel="noopener">Official roll call</a>` : ""}</div>
      ${rows.length ? `<div class="split">${rows.map(r => `<div style="--pc:var(--${r.c})"><span>${esc(r.name)}</span><span class="bar" aria-hidden="true"><i class="y" style="width:${r.yp.toFixed(1)}%"></i><i class="n" style="width:${r.np.toFixed(1)}%"></i></span><span><b>${r.y}</b> yes, <b>${r.n}</b> no</span></div>`).join("")}</div>` : ""}`;
    if (typeof yes === "number" && typeof no === "number") { tween($(".yv"), lastTally[0], yes); tween($(".nv"), lastTally[1], no); lastTally = [yes, no]; }
    $("#sharevote").addEventListener("click", e => share({title: `${current.bill}: ${current.chamber} ${current.category.toLowerCase()}, ${yes}–${no}`, text: `How every ${current.chamber} member voted on ${current.bill}, ${current.title}, state by state:`, url: shareUrlVote(current), kind: "vote", key: current.vote_id}, e.currentTarget));
    if (page === "map") { history.replaceState(history.state, "", "#vote=" + voteSlug(vid)); pageview("/vote/" + voteSlug(vid), current.bill + ": " + current.chamber + " " + current.category); }
    if (zoomed) { if (current.chamber === "Senate" && DIST.states[zoomed]) { /* keep the zoom; senators show as the split state */ } buildDistricts(zoomed); }
    if (selected) showState(selected); else side.innerHTML = `<span class="muted" style="font-size:14px">Tap a state to zoom in. On a House vote you'll see its districts; tap one for the representative.</span>`;
    if (view === "chamber") showChamber();
  }
  let lastTally = [0, 0];
  function tween(el, from, to){
    if (!el || calm() || from === to) return;
    const t0 = performance.now(), dur = 700;
    const step = now => { const p = Math.min(1, (now - t0) / dur), e = 1 - Math.pow(1 - p, 3); el.textContent = Math.round(from + (to - from) * e); if (p < 1) requestAnimationFrame(step); };
    requestAnimationFrame(step);
  }
  const tip = $("#mtip");
  svg.addEventListener("mousemove", e => {
    const g = e.target.closest("g.state"); if (!g || !current) { tip.classList.remove("show"); return; }
    const st = g.dataset.st, ms = membersByState(current.vote_id)[st] || [];
    const r = $(".stage").getBoundingClientRect();
    tip.style.left = (e.clientX - r.left) + "px"; tip.style.top = (e.clientY - r.top) + "px";
    const dp = e.target.closest("path.dist");
    if (dp) {
      const m = ms.find(x => String(x.L.d || 0) === dp.dataset.d);
      tip.innerHTML = `<b>${esc(st)}-${esc(dp.dataset.d)}</b>${m ? `${esc(m.L.n)} (${esc(m.p)}): ${{Y: "Yes", N: "No", P: "Present", X: "Not voting"}[m.pos] || m.pos}` : "no member on record"}`;
    } else {
      const y = ms.filter(m => m.pos === "Y").length, n = ms.filter(m => m.pos === "N").length, o = ms.length - y - n;
      tip.innerHTML = `<b>${esc((states[st] || {}).name || st)}</b>${ms.length ? `${y} yes, ${n} no${o ? `, ${o} not voting` : ""}` : "no members in this roll call"}`;
    }
    tip.classList.add("show");
  });
  svg.addEventListener("mouseleave", () => tip.classList.remove("show"));
  const yrs = (d) => { if (!d) return null; const y = (Date.now() - new Date(d + "T12:00:00")) / 3.15576e10; return y; };
  function showState(st){
    selected = st;
    $$("#usmap g.state").forEach(g => g.classList.toggle("sel", g.dataset.st === st));
    const house = current.chamber !== "Senate";
    const ms = (membersByState(current.vote_id)[st] || []).sort((a, b) => zoomed && house ? (a.L.d || 0) - (b.L.d || 0) : order(a) - order(b));
    const name = (states[st] || {}).name || st;
    const head = `<div class="side-head"><h3>${esc(name)}: ${esc(current.chamber)}, ${esc(current.bill)}</h3>${zoomed ? `<button class="chip" id="sideback">All states</button>` : ""}</div>`;
    if (!ms.length) { side.innerHTML = head + `<p class="muted" style="font-size:14px">No ${esc(current.chamber)} members from ${esc(name)} appear in this roll call.</p>`; return; }
    const pos = {Y: "Yea", N: "Nay", P: "Present", X: "Not voting"};
    side.innerHTML = head + `<p class="hint">${house ? "Tap a district on the map, or a name here, for the full card." : "Tap a name for the full card."}</p>` + ms.map((m, i) => {
      const L = m.L, age = yrs(L.b), since = L.f ? L.f.slice(0, 4) : "", tenure = yrs(L.f);
      const seat = current.chamber === "Senate" ? "Senator" : (L.d ? `District ${L.d}` : "At-large");
      const cg = `https://www.congress.gov/member/${encodeURIComponent(L.n.toLowerCase().replace(/[^a-z0-9]+/g, "-"))}/${m.id}`;
      return `<div class="mrow click${zoomed && house ? " d4" : ""}" style="--i:${i}" data-id="${esc(m.id)}" data-d="${L.d || 0}" role="button" tabindex="0">${zoomed && house ? `<span class="dnum">${L.d || "AL"}</span>` : ""}${avatar(m.id, m.p, "")}<span><b>${esc(L.n)}</b>${L.cur ? "" : ' <span class="muted">(no longer serving)</span>'}<div class="meta"><span>${seat}${since ? `, in Congress since ${since}${tenure != null ? ` (${Math.floor(tenure)} yrs)` : ""}` : ""}${age != null ? `, age ${Math.floor(age)}` : ""}</span><span class="mlinks">${L.u ? `<a href="${esc(L.u)}" target="_blank" rel="noopener">Official site</a>` : ""}${L.ph ? `<a href="tel:${esc(L.ph)}">${esc(L.ph)}</a>` : ""}${L.cf ? `<a href="${esc(L.cf)}" target="_blank" rel="noopener">Contact form</a>` : ""}<a href="${cg}" target="_blank" rel="noopener">Congress.gov</a></span></div></span><span class="vtag ${esc(m.pos)}">${pos[m.pos] || m.pos}</span></div>`;
    }).join("");
    const sb = $("#sideback"); if (sb) sb.addEventListener("click", zoomOut);
  }
  side.addEventListener("keydown", e => { if ((e.key === "Enter" || e.key === " ") && e.target.classList.contains("mrow")) { e.preventDefault(); e.target.click(); } });
  /* ---------- zoom into a state, draw its districts ---------- */
  const setVB = v => { vb = v; svg.setAttribute("viewBox", v.map(n => n.toFixed(2)).join(" ")); const z = v[2] / 975; svg.style.setProperty("--z", z.toFixed(4)); $$("pattern", defs).forEach(p => p.setAttribute("patternTransform", `rotate(45) scale(${z.toFixed(3)})`)); };
  function animateVB(to, ms){
    cancelAnimationFrame(zoomAnim);
    const from = vb.slice(), t0 = performance.now();
    const step = now => { const p = calm() ? 1 : Math.min(1, (now - t0) / ms), e = 1 - Math.pow(1 - p, 3); setVB(from.map((a, i) => a + (to[i] - a) * e)); if (p < 1) zoomAnim = requestAnimationFrame(step); else if (zoomed) svg.classList.add("blur"); };
    zoomAnim = requestAnimationFrame(step);
  }
  const fitBox = b => { let w = (b[2] - b[0]) * 1.14, h = (b[3] - b[1]) * 1.14; if (w / h > 975 / 610) h = w * 610 / 975; else w = h * 975 / 610; return [(b[0] + b[2]) / 2 - w / 2, (b[1] + b[3]) / 2 - h / 2, w, h]; };
  const decode = ring => { let x = 0, y = 0; const pts = []; for (let i = 0; i < ring.length; i += 2) { x += ring[i]; y += ring[i + 1]; pts.push([x / DQ, y / DQ]); } return pts; };
  const pathOf = rings => rings.map(pts => "M" + pts.map(p => p[0].toFixed(2) + "," + p[1].toFixed(2)).join("L") + "Z").join("");
  const areaOf = pts => { let a = 0; for (let i = 0, n = pts.length; i < n; i++) { const [x0, y0] = pts[i], [x1, y1] = pts[(i + 1) % n]; a += x0 * y1 - x1 * y0; } return Math.abs(a) / 2; };
  const centroidOf = pts => { let a = 0, cx = 0, cy = 0; for (let i = 0, n = pts.length; i < n; i++) { const [x0, y0] = pts[i], [x1, y1] = pts[(i + 1) % n], f = x0 * y1 - x1 * y0; a += f; cx += (x0 + x1) * f; cy += (y0 + y1) * f; } a *= .5; return a ? [cx / (6 * a), cy / (6 * a)] : pts[0]; };
  const distCache = {};
  function districtsOf(st){
    if (distCache[st]) return distCache[st];
    const raw = DIST.states[st], s = states[st];
    let list;
    if (raw) {
      list = Object.entries(raw).map(([n, rings]) => { const pts = rings.map(decode), big = pts.reduce((m, r) => areaOf(r) > areaOf(m) ? r : m, pts[0]); return {n: +n, d: pathOf(pts), area: pts.reduce((t, r) => t + areaOf(r), 0), c: centroidOf(big)}; }).sort((a, b) => a.n - b.n);
    } else {
      const [x0, y0, x1, y1] = s.bbox; list = [{n: 0, d: s.d, area: (x1 - x0) * (y1 - y0), c: [(x0 + x1) / 2, (y0 + y1) / 2], whole: true}];
    }
    return distCache[st] = list;
  }
  function clearDistricts(st){ const G = groups[st]; if (!G) return; $$("g.districts", G.g).forEach(x => x.remove()); G.fill.style.display = ""; }
  function buildDistricts(st){
    const G = groups[st]; clearDistricts(st);
    if (current.chamber === "Senate") return;
    const ms = membersByState(current.vote_id)[st] || [], byD = {}; ms.forEach(m => { byD[String(m.L.d || 0)] = m; });
    const list = districtsOf(st), dg = el("g", {class: "districts"});
    for (const D of list) {
      const m = byD[String(D.n)];
      const p = el("path", {class: "dist", d: D.d, "data-d": D.n, tabindex: 0, role: "button", "aria-label": m ? `${states[st].name} district ${D.n || "at large"}: ${m.L.n}, ${{Y: "yes", N: "no", P: "present", X: "not voting"}[m.pos] || m.pos}` : `District ${D.n}: no member on record`});
      p.setAttribute("style", `fill:${m ? fillFor(m.p, m.pos) : "var(--line-strong)"}`); p.setAttribute("vector-effect", "non-scaling-stroke"); dg.appendChild(p);
    }
    const target = fitBox(G.s.bbox), fs = 11.5 * target[2] / Math.max(1, svg.clientWidth || 640);
    if (list.length > 1) for (const D of list) { const t = el("text", {class: "dlab", x: D.c[0], y: D.c[1], dy: ".36em", "text-anchor": "middle", "font-size": fs.toFixed(2)}); t.setAttribute("style", `stroke-width:${(fs * .28).toFixed(2)}px`); t.textContent = D.n; dg.appendChild(t); }
    const out = el("path", {class: "dout", d: G.s.d}); out.setAttribute("vector-effect", "non-scaling-stroke"); dg.appendChild(out);
    dg.addEventListener("click", e => { const p = e.target.closest("path.dist"); if (!p) return; const m = byD[p.dataset.d]; if (m) openRep(m, st); else toast(`No member on record for district ${p.dataset.d} in this vote`); });
    dg.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { const p = e.target.closest("path.dist"); if (p) { e.preventDefault(); p.click(); } } });
    G.g.appendChild(dg); G.fill.style.display = "none";
  }
  function zoomTo(st){
    if (DIST.pending) { need("districts").then(d => { DIST = d || {states: {}, q: 50}; DQ = DIST.q || 50; zoomTo(st); }, () => { DIST = {states: {}, q: 50}; zoomTo(st); }); return; }
    if (zoomed && zoomed !== st) clearDistricts(zoomed);
    zoomed = st; svg.classList.add("zoomed"); svg.classList.remove("blur"); $("#mapback").hidden = false;
    for (const [s2, {g}] of Object.entries(groups)) g.classList.toggle("dim", s2 !== st);
    buildDistricts(st);
    animateVB(fitBox(groups[st].s.bbox), 700);
    showState(st);
  }
  function zoomOut(){
    if (!zoomed) return;
    const st = zoomed; zoomed = null; svg.classList.remove("zoomed", "blur"); $("#mapback").hidden = true;
    Object.values(groups).forEach(({g}) => g.classList.remove("dim")); clearDistricts(st);
    animateVB(VB0, 650); selected = null; $$("#usmap g.state").forEach(g => g.classList.remove("sel"));
    side.innerHTML = `<span class="muted" style="font-size:14px">Tap a state to zoom in. On a House vote you'll see its districts; tap one for the representative.</span>`;
  }
  $("#mapback").addEventListener("click", zoomOut);
  document.addEventListener("keydown", e => { if (e.key === "Escape" && zoomed && $("#repmodal").hidden && $("#palette").hidden) zoomOut(); });
  side.addEventListener("click", e => { const r = e.target.closest(".mrow.click"); if (!r) return; const m = (membersByState(current.vote_id)[selected] || []).find(x => x.id === r.dataset.id); if (m) openRep(m, selected); });
  side.addEventListener("mouseover", e => { const r = e.target.closest(".mrow.click"); $$("path.dist.hl", svg).forEach(x => x.classList.remove("hl")); if (r && zoomed) { const d = $(`path.dist[data-d="${r.dataset.d}"]`, svg); if (d) d.classList.add("hl"); } });
  side.addEventListener("mouseleave", () => $$("path.dist.hl", svg).forEach(x => x.classList.remove("hl")));
  /* ---------- the representative card ---------- */
  const PARTY = {R: "Republican", D: "Democrat", I: "Independent", ID: "Independent", L: "Libertarian"};
  const POSW = {Y: "Yes", N: "No", P: "Present", X: "Not voting"};
  let repSeq = 0;
  function openRep(m, st){
    const token = ++repSeq;
    const L = m.L, name = (states[st] || {}).name || st, house = current.chamber !== "Senate", age = yrs(L.b), since = L.f ? L.f.slice(0, 4) : "", tenure = yrs(L.f);
    const seat = house ? (L.d ? `${name}'s ${pcOrdinal(L.d)} district` : `${name}'s at-large district`) : `Senator from ${name}`;
    const cg = `https://www.congress.gov/member/${encodeURIComponent(L.n.toLowerCase().replace(/[^a-z0-9]+/g, "-"))}/${m.id}`;
    const ms = membersByState(current.vote_id)[st] || [], tally = {};
    ms.forEach(x => { tally[x.p] = (tally[x.p] || 0) + 1; });
    const delegation = Object.entries(tally).sort((a, b) => b[1] - a[1]).map(([p, n]) => `${n} ${PARTY[p] || p}${n === 1 ? "" : "s"}`).join(", ");
    let districtBlock = "";
    if (house) {
      const list = districtsOf(st), D = list.find(x => x.n === (L.d || 0)), total = list.reduce((t, x) => t + x.area, 0);
      const box = fitBox(groups[st].s.bbox);
      const mini = D ? `<svg class="mini" viewBox="${box.map(n => n.toFixed(1)).join(" ")}" aria-hidden="true"><path class="st" d="${esc(groups[st].s.d)}"/><path class="me" d="${esc(D.d)}" style="fill:${fillFor(m.p, m.pos)}"/></svg>` : "";
      districtBlock = `<div class="rep-block"><h4>The district</h4>${mini}<div><b>${L.d ? `District ${L.d} of ${Math.max(list.length, ms.length)}` : "At-large seat"}</b>${D && !D.whole && total ? `, about ${Math.max(1, Math.round(100 * D.area / total))}% of ${name}'s land area` : ""}.</div><div class="muted" style="margin-top:4px">${name}'s House delegation on this vote: ${delegation || "n/a"}.${DIST.vintage && !D?.whole ? ` District lines: ${esc(DIST.vintage)}.` : ""}</div></div>`;
    } else {
      districtBlock = `<div class="rep-block"><h4>The seat</h4><div><b>One of ${name}'s two senators.</b></div><div class="muted" style="margin-top:4px">Senators on this vote from ${name}: ${delegation || "n/a"}.</div></div>`;
    }
    const chamberKey = house ? "H" : "S", C = MVC[chamberKey] || {ids: [], votes: {}}, idx = C.ids.indexOf(m.id);
    const record = idx < 0 ? [] : votes.filter(v => (v.chamber !== "Senate") === house && (C.votes[v.vote_id] || "")[idx] && (C.votes[v.vote_id] || "")[idx] !== ".").map(v => ({v, pos: C.votes[v.vote_id][idx]}));
    const recordHtml = record.length ? `<div class="rep-votes">${record.slice(0, 12).map(({v, pos}) => `<div><span><b>${esc(v.bill)}</b> <span class="muted">${esc(v.category.toLowerCase())}, ${esc(fmtDate(v.date))}</span><br><span class="muted">${esc(v.title)}</span></span><span class="vtag ${esc(pos)}">${POSW[pos] || pos}</span></div>`).join("")}${record.length > 12 ? `<div class="muted">and ${record.length - 12} more</div>` : ""}</div>` : `<p class="muted">No other roll calls on record here.</p>`;
    const mem = MEMBER[m.id];
    const bills = mem && mem.bills.length ? `<b>${mem.bills.length}</b> bill${mem.bills.length === 1 ? "" : "s"} in this catalog${mem.sponsored ? `, ${mem.sponsored} sponsored` : ""}${mem.cosponsored ? `, ${mem.cosponsored} cosponsored` : ""}.` : `No bills sponsored or cosponsored in this catalog.`;
    $("#repbody").innerHTML = `${contactRow(L, cg, "Share how " + L.n.split(" ").slice(-1)[0] + " voted", "rep", m.id)}<div class="rep-head">${avatar(m.id, m.p, "xl")}<div><h2>${esc(L.n)}</h2><div class="seat"><b>${esc(PARTY[m.p] || m.p)}</b>, ${esc(seat)}${L.cur ? "" : " (no longer serving)"}${since ? `<br>In Congress since ${since}${tenure != null ? ` (${Math.floor(tenure)} years)` : ""}` : ""}${age != null ? `, age ${Math.floor(age)}` : ""}</div></div></div>
      <div class="know" id="know"><h3>Get to know ${esc(L.n)}</h3><p class="muted loading">Loading\u2026</p></div>
      <div class="rep-grid">
        <div class="rep-block"><h4>This vote</h4><div class="rec"><span class="vtag ${esc(m.pos)}">${POSW[m.pos] || m.pos}</span><span>on <b>${esc(current.bill)}</b></span></div><div class="muted" style="margin-top:6px">${esc(current.title)}. ${esc(current.chamber)} ${esc(current.category.toLowerCase())}, ${esc(fmtDate(current.date))}: ${current.yeas ?? "?"} to ${current.nays ?? "?"}, ${esc((current.result || "").toLowerCase())}.</div></div>
        ${districtBlock}
        <div class="rep-block"><h4>Their votes on record here</h4>${recordHtml}</div>
        <div class="rep-block"><h4>Their bills</h4><div>${bills}</div>${mem && mem.bills.length ? `<div class="rep-links" style="margin-top:10px"><button id="repbills">Show their bills</button></div>` : ""}</div>
      </div>`;
    $("#sharerep").addEventListener("click", e => share({title: `${L.n} voted ${(POSW[m.pos] || m.pos).toLowerCase()} on ${current.bill}`, text: `${L.n} (${m.p}-${st}) voted ${(POSW[m.pos] || m.pos).toLowerCase()} on ${current.bill}, ${current.title}. The whole ${current.chamber}, state by state:`, url: shareUrlVote(current), kind: "rep", key: m.id}, e.currentTarget));
    const modal = $("#repmodal"); modal.hidden = false; document.body.classList.add("noscroll");
    pageview("/member/" + m.id, L.n);
    const knowHead = `<h3>Get to know ${esc(L.n)}</h3>`;
    needMember(m.id).then(P => {
      if (token !== repSeq) return;                 // another card was opened while this one loaded
      const soc = $("#repsocial"), k = $("#know"); if (soc) soc.innerHTML = socialRow(P.social);
      if (k) k.innerHTML = knowHead + (knowHTML(P, L, m.p, m.id) || `<p class="muted">Nothing more on record for this member yet.</p>`);
    }, () => { const k = $("#know"); if (k && token === repSeq) k.innerHTML = knowHead + `<p class="muted">Couldn't load this member's profile. Check your connection and open the card again.</p>`; });
    const rb = $("#repbills"); if (rb) rb.addEventListener("click", () => { closeRep(); pickMember(m.id); });
    requestAnimationFrame(() => $("#repclose").focus());
  }
  function closeRep(){ $("#repmodal").hidden = true; document.body.classList.remove("noscroll"); }
  $("#repclose").addEventListener("click", closeRep); $(".rep-back").addEventListener("click", closeRep);
  $("#repbody").addEventListener("click", e => {
    const pf = e.target.closest("[data-profile]"); if (pf) { e.preventDefault(); closeRep(); openMember(pf.dataset.profile, pf.dataset.show); return; }
    const a = e.target.closest("a.replink"); if (!a) return; e.preventDefault(); closeRep(); mapShow(a.dataset.vote);
  });
  document.addEventListener("keydown", e => { if (e.key === "Escape" && !$("#repmodal").hidden) { e.stopPropagation(); closeRep(); } }, true);
  function pick(st){ if (zoomed === st) { showState(st); return; } zoomTo(st); }
  const monthOf = d => d ? new Date(d.slice(0, 7) + "-15T12:00:00").toLocaleDateString("en-US", {year: "numeric", month: "long"}) : "Undated";
  const vgroups = new Map(); votes.forEach(v => { const g = monthOf(v.date); if (!vgroups.has(g)) vgroups.set(g, []); vgroups.get(g).push(v); });
  const optionFor = v => `<option value="${esc(v.vote_id)}">${esc(v.bill)}: ${esc(v.chamber)} ${esc(v.category.toLowerCase())}, ${esc(fmtDate(v.date))} (${v.yeas ?? "?"}\u2013${v.nays ?? "?"})</option>`;
  const everyOption = () => [...vgroups].map(([g, vs]) => `<optgroup label="${esc(g)}">` + vs.map(optionFor).join("") + `</optgroup>`).join("");
  sel.innerHTML = everyOption();
  sel.addEventListener("change", () => paint(sel.value));
  const step = d => { const i = sel.selectedIndex + d; if (i < 0 || i >= sel.options.length) return; sel.selectedIndex = i; paint(sel.value); };
  $("#vprev").addEventListener("click", () => step(-1)); $("#vnext").addEventListener("click", () => step(1));
  let narrowed = null;
  const widen = () => { if (!narrowed) return; narrowed = null; $("#mapfilter").hidden = true; const keep = sel.value; sel.innerHTML = everyOption(); sel.value = keep; };
  window.mapShow = vid => { if (!VM[vid]) return; if (narrowed && VM[vid].bill_key !== narrowed) widen(); zoomOut(); sel.value = vid; paint(vid); selected = null; };
  /* the full map, showing only one bill's roll calls; the line above the picker says so and offers the way back */
  window.mapFilter = (billKey, vid) => {
    const mine = votes.filter(v => v.bill_key === billKey); if (!mine.length) return;
    narrowed = billKey; zoomOut(); sel.innerHTML = mine.map(optionFor).join("");
    const f = $("#mapfilter"); f.hidden = false;
    f.innerHTML = `<span>Showing only <b>${esc(mine[0].bill)}</b>: ${mine.length} recorded vote${mine.length === 1 ? "" : "s"}</span><button class="chip" type="button" id="mapfilteroff">Show every vote</button>`;
    $("#mapfilteroff").addEventListener("click", widen);
    sel.value = vid && mine.some(v => v.vote_id === vid) ? vid : mine[0].vote_id; paint(sel.value); selected = null;
  };
  window.mapFocus = (vid, st, id) => {
    const ready = DIST.pending ? need("districts").then(d => { DIST = d || {states: {}, q: 50}; DQ = DIST.q || 50; }, () => { DIST = {states: {}, q: 50}; }) : Promise.resolve();
    ready.then(() => { mapShow(vid); if (!groups[st]) return; zoomTo(st); const m = id && (membersByState(vid)[st] || []).find(x => x.id === id); if (m) openRep(m, st); });
  };
  const missing = Math.max(0, (BOOT.stats.rc_total || 0) - votes.length);
  $("#mapnote").textContent = `${votes.length.toLocaleString()} roll calls carry member-level votes${missing ? `; ${missing.toLocaleString()} more are listed on their bills without member data yet` : ""}. Party is shown as recorded on each roll call.${DIST.vintage ? ` District lines: ${DIST.vintage}.` : ""}`;
  paint(votes[0].vote_id);
  try { if (localStorage.getItem("mapview") === "chamber" && window.WebGLRenderingContext) setView("chamber"); } catch (e) {}
}
document.addEventListener("click", e => {
  const a = e.target.closest("a.maplink"); if (!a) return;
  e.preventDefault();
  const host = a.closest(".card"), bm = host && $(".bmap", host);
  if (bm) {                                     // stay in the bill: pick this vote on the bill's own map
    initBillMap(bm);
    votesReady().then(() => setTimeout(() => { const pick = $("select", bm); if (!pick) return; pick.value = a.dataset.vote; pick.dispatchEvent(new Event("change")); bm.scrollIntoView({block: "center", behavior: calm() ? "auto" : "smooth"}); }, 40), () => {});
    return;
  }
  showPage("map", true);
  mapReady().then(() => { if (window.mapShow) mapShow(a.dataset.vote); });
});

/* ---------- a table a reader can sort ----------
   Click a column to sort by it, click again to turn it round. Shift-click another column to sort within the
   first, and another within that, the way a spreadsheet does; a third shift-click lets a column go. On a
   touch screen there is no Shift key, so a "several columns" switch does the same job. Only the rows on
   show are built, so the same table serves five hundred members or a hundred thousand payments.
     cols: [{key, label, num, val: row => what to sort by, html: row => what to show, title}] */
function gridTable(host, opt){
  const cols = opt.cols, col = Object.fromEntries(cols.map(c => [c.key, c])), page = opt.page || 50;
  let rows = opt.rows || [], sort = (opt.sort || []).slice(), shown = page, multi = false;
  host.innerHTML = `<div class="gt-wrap"><table class="gt"><thead><tr>${cols.map(c => `<th scope="col" class="${c.num ? "num" : ""}"${c.title ? ` title="${esc(c.title)}"` : ""}><button type="button" data-k="${esc(c.key)}">${esc(c.label)}<span class="srt" aria-hidden="true"></span></button></th>`).join("")}</tr></thead><tbody></tbody></table></div>
    <div class="gt-foot"><span class="gt-count"></span><span><button class="chip gt-multi" type="button" aria-pressed="false" title="Or hold Shift while you click a column">Sort by several columns</button> <button class="chip gt-more" type="button" hidden></button></span></div>`;
  const head = $("thead", host), body = $("tbody", host), more = $(".gt-more", host), count = $(".gt-count", host), mbtn = $(".gt-multi", host);
  const cmp = (a, b) => {
    for (const st of sort) {
      const c = col[st.key]; if (!c) continue;
      const x = c.val(a), y = c.val(b);
      if (x == null || y == null) { if (x == null && y == null) continue; return x == null ? 1 : -1; }      // blanks always sink
      const d = (typeof x === "number" && typeof y === "number") ? x - y : String(x).localeCompare(String(y), "en", {numeric: true, sensitivity: "base"});
      if (d) return st.dir === "desc" ? -d : d;
    }
    return 0;
  };
  function draw(){
    if (sort.length) rows.sort(cmp);
    $$("th", head).forEach((th, i) => { const k = cols[i].key, at = sort.findIndex(x => x.key === k), st = sort[at];
      th.setAttribute("aria-sort", st ? (st.dir === "asc" ? "ascending" : "descending") : "none");
      $(".srt", th).innerHTML = st ? (st.dir === "asc" ? "\u25B2" : "\u25BC") + (sort.length > 1 ? `<sup>${at + 1}</sup>` : "") : ""; });
    body.innerHTML = rows.slice(0, shown).map((r, i) => `<tr data-i="${i}">${cols.map(c => `<td class="${c.num ? "num" : ""}">${c.html ? c.html(r) : esc(c.val(r) ?? "")}</td>`).join("")}</tr>`).join("")
      || `<tr><td colspan="${cols.length}" class="muted" style="padding:18px">${esc(opt.empty || "Nothing matches.")}</td></tr>`;
    const left = rows.length - shown; more.hidden = left <= 0; if (left > 0) more.textContent = `Show ${Math.min(page, left).toLocaleString()} more (${left.toLocaleString()} left)`;
    count.textContent = (opt.count ? opt.count(rows) : `${rows.length.toLocaleString()} row${rows.length === 1 ? "" : "s"}`) + (sort.length > 1 ? " \u00b7 sorted by " + sort.map(x => col[x.key].label.toLowerCase()).join(", then ") : "");
    if (opt.after) opt.after(rows.slice(0, shown));
  }
  head.addEventListener("click", e => {
    const b = e.target.closest("button[data-k]"); if (!b) return;
    const k = b.dataset.k, i = sort.findIndex(x => x.key === k), first = col[k].num ? "desc" : "asc", flip = d => d === "asc" ? "desc" : "asc";
    if (e.shiftKey || multi) { if (i < 0) sort.push({key: k, dir: first}); else if (sort[i].dir === first) sort[i].dir = flip(first); else sort.splice(i, 1); }
    else sort = [{key: k, dir: (i === 0 && sort.length === 1) ? flip(sort[0].dir) : first}];
    shown = page; draw();
  });
  mbtn.addEventListener("click", () => { multi = !multi; mbtn.setAttribute("aria-pressed", multi); });
  more.addEventListener("click", () => { shown += page; draw(); });
  if (opt.onHover) { body.addEventListener("pointerover", e => { const tr = e.target.closest("tr[data-i]"); opt.onHover(tr ? rows[+tr.dataset.i] : null); }); body.addEventListener("pointerleave", () => opt.onHover(null)); }
  draw();
  return {setRows(r){ rows = r; shown = page; draw(); }, setSort(x){ sort = x.slice(); draw(); }, get sort(){ return sort.slice(); }, get rows(){ return rows; },
    mark(test){ $$("tr[data-i]", body).forEach(tr => tr.classList.toggle("hot", !!test && test(rows[+tr.dataset.i]))); }, redraw: draw};
}

/* ---------- with their party, and against it: every sitting member's party-line record ---------- */
let partyTable = null;
function renderPartyLine(){
  const host = $("#pltable"); if (!host) return;
  if (!MEMBERS_READY) { host.innerHTML = `<p class="muted">Loading members\u2026</p>`; membersReady().then(renderPartyLine, () => { host.innerHTML = `<p class="muted">Couldn't load the member list. Check your connection and try again.</p>`; }); return; }
  const NAMES = BOOT.state_names || {}, tone = {D: "var(--dem)", R: "var(--rep)"}, PW = {D: "Democrat", R: "Republican", I: "Independent", ID: "Independent", L: "Libertarian"};
  const lastName = n => { const t = String(n).replace(/,?\s+(Jr\.|Sr\.|II|III|IV)$/, "").split(" "); return t[t.length - 1] + " " + n; };
  const all = Object.entries(DATA.legislators).filter(([, L]) => L.cur && L.vs).map(([id, L]) => ({id, L, sn: L.vs[0], sw: L.vs[1], bn: L.vs[2], ms: L.vs[3], el: L.vs[4]}));
  const pct = (a, b) => b ? Math.round(1000 * a / b) / 10 : null;
  const cols = [
    {key: "name", label: "Member", val: r => lastName(r.L.n), html: r => `<span class="pty" style="background:${tone[r.L.p] || "var(--plum)"}"></span><a href="#member=${esc(r.id)}"><b>${esc(r.L.n)}</b></a>`},
    {key: "party", label: "Party", val: r => PW[r.L.p] || r.L.p},
    {key: "state", label: "State", val: r => NAMES[r.L.st] || r.L.st, html: r => esc(NAMES[r.L.st] || r.L.st) + (r.L.ch !== "Senate" && r.L.d ? ` <span class="muted">${esc(String(r.L.d))}</span>` : "")},
    {key: "chamber", label: "Chamber", val: r => r.L.ch},
    {key: "split", label: "Party-split votes", num: true, val: r => r.sn, title: "Votes this member cast where most Democrats went one way and most Republicans the other"},
    {key: "with", label: "With party", num: true, val: r => pct(r.sw, r.sn), html: r => r.sn ? pct(r.sw, r.sn).toFixed(1) + "%" : `<span class="muted">n/a</span>`},
    {key: "broke", label: "Broke with party", num: true, val: r => r.sn ? r.bn : null, html: r => r.sn ? (r.bn ? `<a href="#member=${esc(r.id)}/breaks" title="See these votes"><b>${r.bn.toLocaleString()}</b></a>` : "0") : `<span class="muted">n/a</span>`},
    {key: "missed", label: "Did not vote", num: true, val: r => pct(r.ms, r.el), html: r => r.el ? (r.ms ? `<a href="#member=${esc(r.id)}/missed" title="See these roll calls">${pct(r.ms, r.el).toFixed(1)}%</a>` : "0%") : ""}];
  const f = {ch: "", pt: "", q: ""};
  const rowsNow = () => { const q = f.q.trim().toLowerCase(); return all.filter(r => (!f.ch || r.L.ch === f.ch) && (!f.pt || r.L.p === f.pt) && (!q || r.L.n.toLowerCase().includes(q) || (NAMES[r.L.st] || "").toLowerCase().includes(q) || r.L.st.toLowerCase() === q)); };
  partyTable = gridTable(host, {cols, rows: rowsNow(), sort: [{key: "broke", dir: "desc"}, {key: "with", dir: "asc"}], page: 25, empty: "No member matches.",
    count: rows => `${rows.length.toLocaleString()} member${rows.length === 1 ? "" : "s"}`});
  if (!renderPartyLine.wired) { renderPartyLine.wired = true;
    $("#pltools").addEventListener("click", e => { const b = e.target.closest("button.chip"); if (!b) return; const kind = "ch" in b.dataset ? "ch" : "pt"; f[kind] = b.dataset[kind];
      $$(`#pltools button[data-${kind}]`).forEach(x => x.setAttribute("aria-pressed", x === b)); partyTable.setRows(rowsNow()); });
    $("#plq").addEventListener("input", e => { f.q = e.target.value; partyTable.setRows(rowsNow()); }); }
}

/* ---------- a member's own page ----------
   The card on the map answers "how did they vote on this"; the page answers "who is this". It carries the
   same Get to know sections, then every recorded vote the member took part in, newest first, which can be
   narrowed to the votes where they broke with their party or did not vote. Its address (#member=C001119)
   has a share page of its own, so a link to someone's record shows a proper preview. */
function openMember(id, show){ history.pushState({page: "member"}, "", "#member=" + id + (show ? "/" + show : "")); routeFromHash(false); }
let mpSeq = 0;
function renderMemberPage(id, show){
  const token = ++mpSeq, box = $("#mpage"); if (!box) return;
  box.innerHTML = `<p class="muted loading">Loading\u2026</p>`;
  Promise.all([membersReady(), needMember(id), votesReady()]).then(([, P]) => {
    if (token !== mpSeq) return;
    const L = DATA.legislators[id];
    if (!L) { box.innerHTML = `<div class="empty">That member isn't in this catalog. <a href="#members">See all members</a></div>`; return; }
    const PARTYW = {R: "Republican", D: "Democrat", I: "Independent", ID: "Independent", L: "Libertarian"}, POSW = {Y: "Yes", N: "No", P: "Present", X: "Not voting"};
    const stName = (BOOT.state_names || {})[L.st] || L.st, house = L.ch !== "Senate", last = L.n.split(" ").slice(-1)[0], mem = MEMBER[id];
    const seat = house ? (L.d ? `${stName}'s ${pcOrdinal(L.d)} district` : `${stName}'s at-large district`) : `Senator from ${stName}`;
    const cg = `https://www.congress.gov/member/${encodeURIComponent(L.n.toLowerCase().replace(/[^a-z0-9]+/g, "-"))}/${id}`;
    pageview("/member/" + id, L.n); document.title = `${L.n}: The Civic Archive`;
    // how each party leaned on a roll call, worked out once per vote from the same strings the map draws
    const lean = v => {
      if (v._lean) return v._lean;
      const C = DATA.mv[v.chamber === "Senate" ? "S" : "H"] || {ids: [], votes: {}}, str = C.votes[v.vote_id] || "", po = v.po || {}, t = {D: [0, 0], R: [0, 0]};
      for (let i = 0; i < str.length; i++) { const s = str[i]; if (s !== "Y" && s !== "N") continue; const Lg = DATA.legislators[C.ids[i]], p = po[i] || (Lg && Lg.p); if (p === "D" || p === "R") t[p][s === "Y" ? 0 : 1]++; }
      const side = a => a[0] > a[1] ? "Y" : (a[1] > a[0] ? "N" : "");
      return v._lean = {D: side(t.D), R: side(t.R)};
    };
    const at = {H: DATA.mv.H ? DATA.mv.H.ids.indexOf(id) : -1, S: DATA.mv.S ? DATA.mv.S.ids.indexOf(id) : -1}, rec = [];
    for (const v of DATA.vote_meta) {
      const c = v.chamber === "Senate" ? "S" : "H", i = at[c]; if (i < 0) continue;
      const pos = ((DATA.mv[c].votes[v.vote_id] || "")[i]) || "."; if (pos === ".") continue;
      const p = (v.po || {})[i] || L.p, ln = lean(v), mine = ln[p], other = ln[p === "D" ? "R" : "D"];
      rec.push({v, pos, broke: !!(mine && other && mine !== other && (pos === "Y" || pos === "N") && pos !== mine)});
    }
    const counts = {all: rec.length, broke: rec.filter(r => r.broke).length, missed: rec.filter(r => r.pos === "X").length};
    let filter = show === "breaks" ? "broke" : (show === "missed" ? "missed" : "all"), shown = 25;
    const rowsFor = () => rec.filter(r => filter === "all" || (filter === "broke" ? r.broke : r.pos === "X"));
    const drawVotes = () => {
      const rows = rowsFor(), list = $("#mpvotes");
      list.innerHTML = rows.slice(0, shown).map(r => `<div class="mvrow"><a class="mv-main" href="#vote=${esc(voteSlug(r.v.vote_id))}" title="How everyone voted"><b>${esc(r.v.bill)}</b> ${esc(r.v.title)}<span class="muted">${esc(r.v.chamber)} ${esc(String(r.v.category).toLowerCase())}, ${esc(fmtDate(r.v.date))}: ${r.v.yeas ?? "?"}\u2013${r.v.nays ?? "?"}, ${esc(String(r.v.result || "").toLowerCase())}</span></a><span class="mv-side">${r.broke ? `<span class="mv-flag">broke with party</span>` : ""}<span class="vtag ${esc(r.pos)}">${POSW[r.pos] || r.pos}</span>${r.v.bill_key ? `<a class="mv-bill" href="#bill=${esc(r.v.bill_key)}">The bill</a>` : ""}</span></div>`).join("")
        || `<p class="muted">${filter === "broke" ? "No breaks with the party on a split vote in this record." : (filter === "missed" ? "No missed roll calls in this record." : "No recorded votes here yet.")}</p>`;
      const more = $("#mpmore"); more.hidden = rows.length <= shown; more.textContent = `Show ${Math.min(25, rows.length - shown)} more (${(rows.length - shown).toLocaleString()} left)`;
      $$("#mpfilters .chip").forEach(c => c.setAttribute("aria-pressed", c.dataset.f === filter));
    };
    const bills = mem && mem.bills.length ? `<b>${mem.bills.length.toLocaleString()}</b> bill${mem.bills.length === 1 ? "" : "s"} in this catalog${mem.sponsored ? `, ${mem.sponsored} sponsored` : ""}${mem.cosponsored ? `, ${mem.cosponsored} cosponsored` : ""}.` : "No bills sponsored or cosponsored in this catalog.";
    box.innerHTML = `<div class="mp-head">${avatar(id, L.p, "xxl")}<div><h1 class="mp-name">${esc(L.n)}</h1><div class="seat"><b>${esc(PARTYW[L.p] || L.p)}</b>, ${esc(seat)}${L.cur ? "" : " (no longer serving)"}</div></div></div>
      ${contactRow(L, cg, "Share this profile", "mp", null)}
      <div class="mp-grid">
        <div class="know" id="mpknow"><h3>Get to know ${esc(L.n)}</h3>${knowHTML(P, L, L.p, id) || `<p class="muted">Nothing more on record for this member yet.</p>`}</div>
        <div class="mp-side">
          <div class="know-b"><h4><span class="tag fact">Fact</span> Every recorded vote</h4>
            <div class="mp-filters" id="mpfilters" role="group" aria-label="Narrow the votes"><button class="chip" data-f="all" aria-pressed="true">All ${counts.all.toLocaleString()}</button><button class="chip" data-f="broke">Broke with party ${counts.broke.toLocaleString()}</button><button class="chip" data-f="missed">Did not vote ${counts.missed.toLocaleString()}</button></div>
            <div id="mpvotes"></div><button class="chip" id="mpmore" type="button" hidden></button>
            <p class="know-rule">Each line opens that vote, where you can see how everyone else voted; "The bill" opens the bill itself. "Broke with party" means most of ${esc(last)}'s party voted the other way while most of the other party did not; party is the one recorded on each roll call.</p></div>
          <div class="know-b"><h4><span class="tag fact">Fact</span> Their bills</h4><p>${bills}</p>${mem && mem.bills.length ? `<button class="chip" id="mpbills" type="button">Show ${esc(last)}'s bills</button>` : ""}</div>
        </div>
      </div>`;
    $("#mpsocial").innerHTML = socialRow(P.social);
    drawVotes();
    if (show) setTimeout(() => { const t = $("#mpfilters"); if (t) t.scrollIntoView({block: "start", behavior: "auto"}); scrollBy(0, -80); }, 60);
    $("#mpfilters").addEventListener("click", e => { const c = e.target.closest(".chip"); if (!c) return; filter = c.dataset.f; shown = 25; drawVotes(); });
    $("#mpmore").addEventListener("click", () => { shown += 25; drawVotes(); });
    const mb = $("#mpbills"); if (mb) mb.addEventListener("click", () => pickMember(id));
    const V = P.votes || {}, side = V.party === "R" ? "Republicans" : "Democrats";
    const text = V.split_n ? `${L.n} sided with ${side} on ${Math.round(100 * V.split_with / V.split_n)}% of the ${V.split_n} votes where the two parties split. Every recorded vote, from the public record:` : `How ${L.n} votes and what ${last} works on, from the public record:`;
    $("#sharemp").addEventListener("click", e => share({title: `Get to know ${L.n}`, text, url: `${SHARE_BASE}/m/${id}.html`, kind: "member", key: id}, e.currentTarget));
    watchTracks(box);
  }, () => { if (token === mpSeq) box.innerHTML = `<div class="empty">Couldn't load this member. Check your connection and try again.</div>`; });
}

/* ---------- command palette, shortcuts, deep links ---------- */
(function(){
  const pal = $("#palette"), inp = $("#palq"), list = $("#pallist"); let items = [], idx = 0;
  const open = () => { pal.hidden = false; document.body.classList.add("noscroll"); inp.value = ""; run(""); requestAnimationFrame(() => inp.focus()); };
  const close = () => { pal.hidden = true; document.body.classList.remove("noscroll"); };
  const mark = () => { $$("li[data-i]", list).forEach(li => li.setAttribute("aria-selected", +li.dataset.i === idx)); const cur = $(`li[data-i="${idx}"]`, list); if (cur) cur.scrollIntoView({block: "nearest"}); };
  const go = i => { const it = items[i]; if (!it) return; close(); if (it.kind === "bill") goToBill(it.key); else openMember(it.id); };
  function run(q){
    if (!CATALOG_READY) { items = []; list.innerHTML = `<li class="none">Loading the catalog\u2026</li>`; catalogReady().then(() => { if (!pal.hidden) run(inp.value); }, () => { list.innerHTML = `<li class="none">Couldn't load the catalog. Check your connection and try again.</li>`; }); return; }
    q = q.trim().toLowerCase();
    const bills = (q ? DATA.bills.filter(b => hay(b).includes(q)) : DATA.bills.filter(isRated)).slice(0, 7);
    const mems = q ? DATA.members.filter(m => m.bills.length && (m.name.toLowerCase().includes(q) || m.state.toLowerCase() === q)).sort((a, b) => b.bills.length - a.bills.length).slice(0, 4) : [];
    items = [...bills.map(b => ({kind: "bill", key: b.key})), ...mems.map(m => ({kind: "member", id: m.id}))]; idx = 0;
    let n = 0;
    list.innerHTML = (bills.length ? `<li class="grp">${q ? "Bills" : "Rated bills"}</li>` + bills.map(b => `<li role="option" data-i="${n++}" style="--i:${n}"><span class="pill id">${esc(b.id)}</span><span class="t">${esc(leadTitle(b))}</span><span class="s">${esc(statusText(b))}</span></li>`).join("") : "")
      + (mems.length ? `<li class="grp">Members</li>` + mems.map(m => `<li role="option" data-i="${n++}">${avatar(m.id, m.party, "sm")}<span class="t">${esc(prettyName(m))}</span><span class="s">${esc(roleOf(m))}, ${esc(m.state)}, ${m.bills.length} bill${m.bills.length === 1 ? "" : "s"}</span></li>`).join("") : "")
      || `<li class="none">Nothing matches. Try a bill number like H.R. 1, a topic like housing, or a last name.</li>`;
    mark();
  }
  $("#palettebtn").addEventListener("click", open);
  $(".pal-back").addEventListener("click", close);
  inp.addEventListener("input", () => run(inp.value));
  inp.addEventListener("keydown", e => {
    if (e.key === "ArrowDown") { e.preventDefault(); idx = Math.min(items.length - 1, idx + 1); mark(); }
    else if (e.key === "ArrowUp") { e.preventDefault(); idx = Math.max(0, idx - 1); mark(); }
    else if (e.key === "Enter") { e.preventDefault(); go(idx); }
  });
  list.addEventListener("click", e => { const li = e.target.closest("li[data-i]"); if (li) go(+li.dataset.i); });
  document.addEventListener("keydown", e => {
    const tag = (e.target.tagName || "").toLowerCase(), typing = tag === "input" || tag === "select" || tag === "textarea";
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); if (pal.hidden) open(); else close(); return; }
    if (e.key === "Escape" && !pal.hidden) { close(); return; }
    if (e.key === "/" && !typing) { e.preventDefault(); $("#q").focus(); }
  });
  if (!/Mac|iPhone|iPad/.test(navigator.platform || "")) $$(".kbtn kbd").forEach(k => k.textContent = "Ctrl K");
})();

/* --- pages -------------------------------------------------------------
   One file, five pages. Everything still lives in a single document, so the
   data is loaded once and bill links keep working; only one page is visible
   at a time. Hashes stay what they always were (#bills, #map, #bill=hr1-119)
   so links already in the wild keep landing in the right place. */
const PAGES = ["home", "bills", "map", "how", "members", "member"];
const BASE_TITLE = document.title;
let page = "home", billsShown = false;
function showPage(name, push){
  if (!PAGES.includes(name)) name = "home";
  page = name;
  PAGES.forEach(p => { const el = $("#pg-" + p); if (el) el.hidden = p !== name; });
  $$(".nav a[data-go], .tabbar a[data-go]").forEach(a => a.setAttribute("aria-current", (a.dataset.go === name || (name === "member" && a.dataset.go === "members")) ? "page" : "false"));
  if (name !== "member") document.title = BASE_TITLE;
  document.body.dataset.page = name;
  pageview("/" + (name === "home" ? "" : name), "The Civic Archive: " + name);
  if (name === "bills" && !billsShown) { billsShown = true; render(); }
  if (name === "members") { renderMembers(); if (!partyTable) renderPartyLine(); }
  if (name === "map") mapReady();
  if (push) { const h = "#" + name; if (location.hash !== h) history.pushState({page: name}, "", h); }
  scrollTo({top: 0, behavior: "auto"});
  // The map is drawn into a sized SVG; if it was built while hidden it has no
  // box to measure, so give it a nudge once it is actually on screen.
  if (name === "map") requestAnimationFrame(() => dispatchEvent(new Event("resize")));
}
function routeFromHash(push){
  const h = (location.hash || "").replace(/^#/, "");
  const bill = h.match(/^bill=([a-z0-9-]+)/i);
  if (bill) { showPage("bills", false); catalogReady().then(() => { if (byKey[bill[1]]) setTimeout(() => openBill(bill[1]), 60); else toast("That bill isn't in this catalog."); }, () => {}); return; }
  const vote = h.match(/^vote=(.+)$/);
  if (vote) { showPage("map", false); mapReady().then(() => { if (window.mapShow) mapShow(decodeURIComponent(vote[1]).replace(/_/g, "|")); }); return; }
  const mem = h.match(/^member=([A-Za-z]\d{6})(?:\/(breaks|missed))?$/);
  if (mem) { showPage("member", false); renderMemberPage(mem[1].toUpperCase(), mem[2]); return; }
  if (h === "nowmoving" || h === "yours" || h === "top" || h === "") { showPage("home", false); if (h === "yours") { const t = $("#yours"); if (t) setTimeout(() => t.scrollIntoView({behavior: "auto"}), 30); } return; }
  showPage(PAGES.includes(h) ? h : "home", false);
}
document.addEventListener("click", e => {
  const a = e.target.closest('a[href^="#"]'); if (!a || a.classList.contains("maplink")) return;
  const h = a.getAttribute("href").slice(1);
  if (h === "nowmoving" || h === "yours") { e.preventDefault(); showPage("home", true); const t = $("#" + h); if (t) setTimeout(() => t.scrollIntoView({behavior: calm() ? "auto" : "smooth"}), 30); return; }
  if (h === "top") { e.preventDefault(); showPage("home", true); return; }
  if (PAGES.includes(h)) { e.preventDefault(); showPage(h, true); }
});
addEventListener("popstate", () => routeFromHash(false));
/* A plain link such as #vote=... or #member=... changes the address without going through the router; follow it. */
addEventListener("hashchange", () => { const h = location.hash.slice(1); if (/^(vote|member|bill)=/.test(h)) routeFromHash(false); });

/* Changelog badge. The label is the version named by the newest changelog
   entry (4.x.xxx); entries from before version numbers fall back to a count.
   Adding an entry to CHANGELOG.md is still the whole release process. */
(function(){
  if (!BOOT.inline) { const o = $("#offline"); if (o) o.hidden = false; }
  const log = BOOT.changelog || []; if (!log.length) return;
  const wrap = $("#cl"), tab = $("#cltab"), panel = $("#clpanel"), body = $("#clbody");
  $("#clv").textContent = log[0].version ? "v" + log[0].version : "v" + log.length;
  body.innerHTML = log.map(e => `<div class="cl-e"><div class="d">${e.version ? "v" + esc(e.version) + " · " : ""}${esc(e.date)}</div><div class="t">${esc(e.title)}</div>${e.items.length ? `<ul>${e.items.map(i => `<li>${esc(i)}</li>`).join("")}</ul>` : ""}</div>`).join("");
  const setOpen = on => { panel.hidden = !on; tab.setAttribute("aria-expanded", on ? "true" : "false"); };
  tab.addEventListener("click", () => setOpen(panel.hidden));
  $("#clx").addEventListener("click", () => { setOpen(false); tab.focus(); });
  document.addEventListener("keydown", e => { if (e.key === "Escape" && !panel.hidden) { setOpen(false); tab.focus(); } });
  document.addEventListener("click", e => { if (!panel.hidden && !wrap.contains(e.target)) setOpen(false); });
  wrap.hidden = false;
})();

/* Welcome-screen pick lists. Each row opens the same bill detail the rest of
   the site uses, so nothing here is a separate copy of the truth. */
(function(){
  const W = BOOT.welcome; if (!W) return;
  const shortStatus = s => String(s || "")
    .replace(/^Became law.*/, "Law")
    .replace(/^Passed both chambers - differences unresolved$/, "Passed both, unresolved")
    .replace(/^Passed both chambers$/, "Passed both chambers")
    .replace(/^Presented to President$/, "On the President's desk")
    .replace(/^Reported by committee \/ on calendar$/, "On the calendar")
    .replace(/^Passed House only$/, "Passed the House")
    .replace(/^Passed Senate only$/, "Passed the Senate");
  const when = d => {
    if (!d) return "";
    const t = new Date(d + "T00:00:00");
    return isNaN(t) ? "" : t.toLocaleDateString(undefined, {month: "short", day: "numeric", year: "numeric"});
  };
  function row(b, isLaw){
    const li = document.createElement("li");
    const pills = [
      `<span class="pill">${esc(b.id)}</span>`,
      isLaw && b.law ? `<span class="pill law">P.L. ${esc(b.law)}</span>` : `<span class="pill">${esc(shortStatus(b.status))}</span>`,
      b.bi ? `<span class="pill bi">Bipartisan</span>` : "",
      b.cos ? `<span>${b.cos} cosponsor${b.cos === 1 ? "" : "s"}</span>` : "",
      b.date ? `<span>${esc(when(b.date))}</span>` : "",
    ].filter(Boolean).join("");
    li.innerHTML = `<button class="pickitem" type="button"><span class="n" aria-hidden="true"></span><span><span class="t">${esc(b.nick && b.nick.lead ? b.nick.name : (b.title || b.id))}</span>${b.was ? `<span class="aka">began as <b>${esc(b.was)}</b></span>` : ""}${b.nick && !b.nick.lead ? `<span class="aka">commonly called <b>${esc(b.nick.name)}</b></span>` : ""}<span class="meta">${pills}</span>${b.journey ? trackHTML(b, "pick") : ""}</span></button>`;
    li.querySelector("button").addEventListener("click", () => goToBill(b.key));
    return li;
  }
  const fill = (sel, list, isLaw) => {
    const ol = $(sel); if (!ol) return;
    list.forEach(b => ol.appendChild(row(b, isLaw)));
  };
  fill("#picklive", W.live || [], false);
  fill("#picklaws", W.laws || [], true);
})();

/* ---------- decided by a handful: the closest recorded votes ---------- */
(function(){
  const list = BOOT.closest || [], box = $("#closest"), ol = $("#closelist"); if (!box || !ol || !list.length) return;
  const votes = n => `${n} vote${n === 1 ? "" : "s"}`;
  const how = v => {
    const tally = `${v.yeas}\u2013${v.nays}`;
    if (v.needs === "majority") return v.margin === 0 ? `${v.result} on a tie, ${tally}${v.chamber === "Senate" && v.won ? ". The Vice President's vote settles a Senate tie" : ""}` : `${v.result} by ${votes(v.margin)}, ${tally}`;
    const needed = v.needs === "sixty" ? "the 60 votes it needed" : `the two-thirds it needed (${v.need})`;
    return v.won ? (v.margin === 0 ? `${v.result} with exactly ${needed}, ${tally}` : `${v.result}, clearing ${needed} by ${v.margin}, ${tally}`) : `${v.result}, ${votes(v.margin)} short of ${needed}, ${tally}`;
  };
  ol.innerHTML = list.map(v => `<li class="closeitem rv"><div class="by"><b>${v.margin === 0 && v.needs === "majority" ? "Tie" : v.margin}</b><span>${v.margin === 0 ? (v.needs === "majority" ? `${v.yeas}\u2013${v.nays}` : "to spare") : (v.needs === "majority" ? (v.margin === 1 ? "vote" : "votes") : (v.won ? "to spare" : "short"))}</span></div>
    <div class="what"><a class="main" href="#vote=${esc(String(v.vote_id).replace(/\|/g, "_"))}"><b>${esc(v.bill)}</b> ${esc(v.title)}</a><span class="how ${v.won ? "won" : "lost"}">${esc(how(v))}</span><span class="muted">${esc(v.chamber)} ${esc(String(v.category).toLowerCase())}, ${esc(fmtDate(v.date))} \u00b7 <a href="#vote=${esc(String(v.vote_id).replace(/\|/g, "_"))}">how everyone voted</a> \u00b7 <a href="#bill=${esc(v.bill_key)}">the bill</a></span></div></li>`).join("");
  box.hidden = false;
})();

$("#totop").addEventListener("click", () => scrollTo({top: 0, behavior: calm() ? "auto" : "smooth"}));
reveal(document); moveChipInd();
/* Warm the list and the member roster once the page has settled, unless the visitor asked to save data. */
if (!BOOT.inline && !(navigator.connection && navigator.connection.saveData)) setTimeout(() => { need("bills-list").catch(() => {}); membersReady().catch(() => {}); }, 2500);

/* ---------- your members: the shortest path from "who represents me" to a shareable vote ---------- */
(function(){
  const sel = $("#ystate"), list = $("#ylist"), note = $("#ynote"), NAMES = BOOT.state_names || {}; if (!sel) return;
  const POS = {Y: "Yes", N: "No", P: "Present", X: "Not voting"};
  sel.innerHTML = `<option value="">Choose your state</option>` + Object.entries(NAMES).sort((a, b) => a[1].localeCompare(b[1])).map(([st, n]) => `<option value="${esc(st)}">${esc(n)}</option>`).join("");
  let myDistrict = null, current = "";
  const byRow = (a, b) => ((a.L.ch === "Senate" ? 0 : 1) - (b.L.ch === "Senate" ? 0 : 1)) || ((a.L.d || 0) - (b.L.d || 0)) || a.L.n.localeCompare(b.L.n);
  const mineFor = (v, ms) => (myDistrict != null && v.chamber !== "Senate") ? ms.find(m => (m.L.d || 0) === myDistrict) : null;
  const seat = (v, m) => v.chamber === "Senate" ? "Senator" : (m.L.d ? "District " + m.L.d : "At large");
  function paintState(st){
    const name = NAMES[st] || st, votes = [];
    for (const v of DATA.vote_meta) { if (positionsFor(v, st).length) votes.push(v); if (votes.length === 6) break; }
    list.innerHTML = `<div class="yours-head"><h3>${esc(name)}'s members on the latest roll calls</h3><a class="chip" href="#map">Every vote, on the map</a></div>` + (votes.map(v => {
      const ms = positionsFor(v, st).sort(byRow), mine = mineFor(v, ms);
      if (mine) { ms.splice(ms.indexOf(mine), 1); ms.unshift(mine); }      // your own member comes first
      return `<article class="yvote" data-vote="${esc(v.vote_id)}"><div class="yv-head"><b>${esc(v.bill)}</b> ${esc(v.title)}<div class="muted">${esc(v.chamber)} ${esc(v.category.toLowerCase())}, ${esc(fmtDate(v.date))}: ${v.yeas ?? "?"}\u2013${v.nays ?? "?"}, ${esc((v.result || "").toLowerCase())}</div></div>
        <div class="yv-members">${ms.map(m => `<button class="ymem${mine && mine.id === m.id ? " mine shimmer" : ""}" type="button" data-id="${esc(m.id)}">${avatar(m.id, m.p, "sm")}<span><b>${esc(m.L.n)}</b><span class="muted">${esc(seat(v, m))}${mine && mine.id === m.id ? " \u00b7 yours" : ""}</span></span><span class="vtag ${esc(m.pos)}">${POS[m.pos] || m.pos}</span></button>`).join("")}</div>
        <div class="yv-acts"><button class="chip sharebtn" type="button" data-share="1">Share how ${esc(name)} voted</button><a class="chip" href="#vote=${esc(voteSlug(v.vote_id))}">Open on the map</a></div></article>`;
    }).join("") || `<p class="muted">No roll calls with members from ${esc(name)} yet.</p>`);
  }
  function show(st){
    current = st; if (!st) { list.hidden = true; return; }
    try { localStorage.setItem("state", st); } catch (e) {}
    list.hidden = false; list.innerHTML = `<p class="muted loading">Loading the roll calls\u2026</p>`;
    pageview("/yours/" + st, "Your members: " + (NAMES[st] || st));
    votesReady().then(() => { if (current === st) paintState(st); }, () => { list.innerHTML = `<p class="muted">Couldn't load the roll calls. Check your connection and try again.</p>`; });
  }
  sel.addEventListener("change", () => { myDistrict = null; try { localStorage.removeItem("district"); } catch (e) {} note.textContent = ""; show(sel.value); });
  list.addEventListener("click", e => {
    const art = e.target.closest(".yvote"); if (!art) return;
    const v = DATA.vote_meta.find(x => x.vote_id === art.dataset.vote); if (!v) return;
    const mem = e.target.closest(".ymem");
    if (mem) { showPage("map", true); mapReady().then(() => { if (window.mapFocus) mapFocus(v.vote_id, current, mem.dataset.id); }); return; }
    const sb = e.target.closest(".sharebtn"); if (!sb) return;
    const name = NAMES[current] || current, ms = positionsFor(v, current).sort(byRow), mine = mineFor(v, ms);
    const one = m => `${m.L.n.split(" ").slice(-1)[0]} ${(POS[m.pos] || m.pos).toLowerCase()}`;
    const text = mine ? `My representative, ${mine.L.n}, voted ${(POS[mine.pos] || mine.pos).toLowerCase()} on ${v.bill}, ${v.title}. The whole ${v.chamber}, state by state:`
      : `How ${name}'s members voted on ${v.bill}, ${v.title}: ${ms.slice(0, 6).map(one).join(", ")}${ms.length > 6 ? `, and ${ms.length - 6} more` : ""}. The whole ${v.chamber}, state by state:`;
    share({title: `${v.bill}: how ${name} voted`, text, url: shareUrlVote(v), kind: "state", key: current}, sb);
  });
  /* "Use my location": the browser asks first. The position is placed on the site's own map, the same
     Albers projection and district lines the vote map draws, so the lookup happens on this device and
     the coordinates never leave it. */
  const conic = (parallels, rotLon, center, scale, tx, ty) => {
    const rad = Math.PI / 180, y0 = parallels[0] * rad, sy0 = Math.sin(y0), n = (sy0 + Math.sin(parallels[1] * rad)) / 2, c = 1 + sy0 * (2 * n - sy0), r0 = Math.sqrt(c) / n;
    const raw = (lam, phi) => { const r = Math.sqrt(c - 2 * n * Math.sin(phi)) / n, x = lam * n; return [r * Math.sin(x), r0 - r * Math.cos(x)]; };
    const [cx, cy] = raw(center[0] * rad, center[1] * rad), dx = tx - scale * cx, dy = ty + scale * cy;
    return (lon, lat) => { const lam = ((((lon + rotLon + 180) % 360) + 360) % 360 - 180) * rad, [x, y] = raw(lam, lat * rad); return [scale * x + dx, dy - scale * y]; };
  };
  const albersUsa = (() => {
    const k = 1300, tx = 487.5, ty = 305, E = 1e-6;
    const lower48 = conic([29.5, 45.5], 96, [-0.6, 38.7], k, tx, ty), alaska = conic([55, 65], 154, [-2, 58.5], k * .35, tx - .307 * k, ty + .201 * k), hawaii = conic([8, 18], 157, [-3, 19.9], k, tx - .205 * k, ty + .212 * k);
    // as d3 does it going forward: each part of the map accepts only points that land inside its own frame
    const inBox = (p, x0, y0, x1, y1) => p[0] >= tx + x0 * k - E && p[0] < tx + x1 * k + E && p[1] >= ty + y0 * k - E && p[1] < ty + y1 * k + E;
    return (lon, lat) => { let p = lower48(lon, lat); if (inBox(p, -.455, -.238, .455, .238)) return p;
      p = alaska(lon, lat); if (inBox(p, -.425, .120, -.214, .234)) return p;
      p = hawaii(lon, lat); if (inBox(p, -.214, .166, -.115, .234)) return p;
      return null; };
  })();
  const inRing = (pt, ring) => { let inside = false; for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) { const [xi, yi] = ring[i], [xj, yj] = ring[j]; if ((yi > pt[1]) !== (yj > pt[1]) && pt[0] < (xj - xi) * (pt[1] - yi) / (yj - yi) + xi) inside = !inside; } return inside; };
  const inShape = (pt, rings) => rings.reduce((n, r) => n + (inRing(pt, r) ? 1 : 0), 0) % 2 === 1;
  const pathRings = d => d.split("M").filter(Boolean).map(seg => seg.replace(/Z$/, "").split("L").map(p => p.split(",").map(Number)));
  const decodeRing = (ring, q) => { let x = 0, y = 0; const pts = []; for (let i = 0; i < ring.length; i += 2) { x += ring[i]; y += ring[i + 1]; pts.push([x / q, y / q]); } return pts; };
  function locate(lon, lat){
    const pt = albersUsa(lon, lat); let st = null; if (!pt) return null;
    for (const [s, shp] of Object.entries(DATA.states)) { const [x0, y0, x1, y1] = shp.bbox; if (pt[0] < x0 || pt[0] > x1 || pt[1] < y0 || pt[1] > y1) continue; if (inShape(pt, pathRings(shp.d))) { st = s; break; } }
    if (!st) return null;
    const D = DATA.districts && DATA.districts.states && DATA.districts.states[st], q = (DATA.districts && DATA.districts.q) || 50; let d = null;
    if (D) for (const [n, rings] of Object.entries(D)) { if (inShape(pt, rings.map(r => decodeRing(r, q)))) { d = +n; break; } }
    return {st, d};
  }
  window.civicLocate = (lon, lat) => Promise.all([votesReady(), need("districts")]).then(([, D]) => { DATA.districts = D; return locate(lon, lat); });
  $("#yloc").addEventListener("click", () => {
    if (!navigator.geolocation) { note.textContent = "Location isn't available in this browser. Pick your state instead."; return; }
    note.textContent = "Finding your district\u2026";
    navigator.geolocation.getCurrentPosition(pos => {
      civicLocate(pos.coords.longitude, pos.coords.latitude).then(hit => {
        if (!hit || !NAMES[hit.st]) { note.textContent = "That spot isn't inside a state on our map. Pick your state instead."; return; }
        myDistrict = hit.d; sel.value = hit.st;
        try { if (hit.d == null) localStorage.removeItem("district"); else localStorage.setItem("district", String(hit.d)); } catch (e) {}      // kept on this device, so your own representative is marked next time too
        note.textContent = `${NAMES[hit.st]}${hit.d ? ", and it looks like district " + hit.d : ""}. Worked out on your device; your location never leaves it. Near a district line the guess can be off by one.`;
        show(hit.st); track("locate", {key: hit.st});
      }, () => { note.textContent = "Couldn't load the map lines. Check your connection, or pick your state."; });
    }, () => { note.textContent = "Location wasn't shared. Pick your state instead."; }, {timeout: 10000, maximumAge: 600000});
  });
  let saved = null, savedD = null; try { saved = localStorage.getItem("state"); savedD = localStorage.getItem("district"); } catch (e) {}
  if (saved && NAMES[saved]) { if (savedD !== null && savedD !== "" && !isNaN(+savedD)) myDistrict = +savedD; sel.value = saved; show(saved); }
})();

/* Help modal: the Fact / Analysis / Opinion guide, over a blurred page. */
(function(){
  const box = $("#help"), btn = $("#helpbtn");
  const open = () => { box.hidden = false; document.body.classList.add("noscroll"); $("#helpx").focus(); };
  const close = () => { box.hidden = true; document.body.classList.remove("noscroll"); btn.focus(); };
  btn.addEventListener("click", open);
  $("#helpx").addEventListener("click", close);
  $("#helpback").addEventListener("click", close);
  document.addEventListener("keydown", e => { if (e.key === "Escape" && !box.hidden) close(); });
})();

routeFromHash(false);
if (!BOOT.inline && "serviceWorker" in navigator && (location.protocol === "https:" || /[?&]sw=1\b/.test(location.search)))
  addEventListener("load", () => navigator.serviceWorker.register("./sw.js").catch(() => {}));
</script>
</body>
</html>
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", required=True)
    ap.add_argument("--out", default="site.html", help="the one-file archive (everything inline; works from a double-click)")
    ap.add_argument("--split", default="", help="also write the fast site into this folder: index.html plus data/ and photos/")
    ap.add_argument("--max-mb", type=float, default=15.0, help="size budget for the one-file archive (claude.ai artifacts allow 16 MB)")
    ap.add_argument("--summary-chars", type=int, default=220, help="summary length kept for introduced-only measures")
    ap.add_argument("--as-of", default="", help="date to print as the generation date (YYYY-MM-DD); default today")
    ap.add_argument("--base-url", default="https://thecivicarchive.github.io/dev",
                    help="where the fast site will live; share pages and link previews need absolute addresses")
    ap.add_argument("--analytics", default="",
                    help="GoatCounter endpoint, e.g. https://civicarchive.goatcounter.com/count; default: the one line of "
                         "analytics.txt next to this script, if that file exists; empty means no analytics at all")
    args = ap.parse_args()
    if not args.analytics:
        cfg = os.path.join(os.path.dirname(os.path.abspath(__file__)), "analytics.txt")
        if os.path.exists(cfg):
            args.analytics = open(cfg, encoding="utf-8").read().strip()
    data = collect(args.db)
    photo_bytes, profiles = data.pop("photo_bytes"), data.pop("profiles")
    version = (data["changelog"][0].get("version") if data["changelog"] else "") or ""
    if args.as_of:
        data["generated"] = dt.datetime.strptime(args.as_of, "%Y-%m-%d").strftime("%B %d, %Y")
    st = data["stats"]
    demo = st["current"] < st["measures"]
    if demo:
        foot = (f"<b>Demo data.</b> This page was generated from <code>{os.path.basename(args.db)}</code> on {data['generated']}: "
                f"{st['measures']:,} measures introduced {st['years']}, most of them the sample files GPO publishes for the Bill Status "
                f"format, plus {st['current']:,} measures from the current Congress; {st['rated']:,} carry ratings under rubric "
                f"{data['rubric']}, and {st['members']:,} members appear as sponsors or cosponsors.")
    else:
        foot = (f"Generated from <code>{os.path.basename(args.db)}</code> on {data['generated']}: {st['measures']:,} measures introduced "
                f"{st['years']}, {st['roll_calls']:,} roll calls with member-level votes, {st['rated']:,} measures rated under rubric "
                f"{data['rubric']}, and {st['members']:,} members who sponsored or cosponsored them.")
    if version:
        foot += f" Version {version}."
    print(f"Version {version or '(none: no version in CHANGELOG.md)'}")

    # the one-file archive: the same shell with every bundle inlined, trimmed to the size budget
    boot = boot_for(data, version, args.base_url)
    boot["analytics"] = args.analytics
    for n_chars, n_subj in ((args.summary_chars, 4), (140, 3), (80, 2), (0, 0)):
        shaped = trim_lite(data, n_chars, n_subj)
        boot["inline"] = dict(bundles(shaped), **{"bills-list": {"bills": shaped["bills"]}, "photos": shaped["photos"], "profiles": profiles})
        html = render_page(boot, shaped, version, foot)
        mb = len(html.encode("utf-8")) / 1e6
        if mb <= args.max_mb - 0.3 or n_chars == 0:
            break
        print(f"  archive {mb:.1f} MB is over the {args.max_mb:g} MB budget; trimming summaries on introduced-only measures")
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(html)
    size = os.path.getsize(args.out) / 1e6
    print(f"Wrote {args.out}: {st['measures']:,} measures ({st['compact']:,} compact), {st['rated']:,} rated, "
          f"{st['roll_calls']:,} roll calls with member votes, {st['members']:,} members, {len(data['photos']):,} portraits, "
          f"{sum(len(v) for v in data['districts'].get('states', {}).values()):,} district shapes, {size:.1f} MB")
    if size > 16:
        print("WARNING: over 16 MB, too large to publish as a single claude.ai artifact; lower --summary-chars or host it elsewhere")

    # the fast site: a small shell, data on demand
    if args.split:
        boot["inline"] = None
        shaped = trim_lite(data, args.summary_chars, 4)   # compact rows carry a short summary; the full one is on Congress.gov
        shaped["_version"], shaped["_profiles"] = version, profiles
        shell = render_page(boot, shaped, version, foot)
        sizes, n_detail, detail_bytes, photo_total = write_split(args.split, shell, shaped, photo_bytes)
        kb = lambda n: f"{n / 1e3:,.0f} KB" if n < 1e6 else f"{n / 1e6:.1f} MB"
        import shutil
        shutil.copyfile(args.out, os.path.join(args.split, "offline.html"))   # the archive travels with the fast site
        print(f"Wrote {args.split}/: shell {kb(sizes['index.html'])}; "
              + "; ".join(f"{os.path.basename(k)[:-5]} {kb(v)}" for k, v in sizes.items() if k.startswith("data/"))
              + f"; {n_detail:,} bill files ({kb(detail_bytes)}); {len(photo_bytes):,} portraits ({kb(photo_total)})")
        import share_cards
        sh = share_cards.write_share_pages(args.split, shaped, args.base_url, data["states"], photo_bytes)
        print(f"Share pages: {sh['bill_pages']:,} bills, {sh['vote_pages']:,} votes, {sh['member_pages']:,} members; preview images: {sh['cards_drawn']:,} drawn, "
              f"{sh['cards_kept']:,} unchanged, {kb(sh['cards_bytes'])} in all")


if __name__ == "__main__":
    main()
