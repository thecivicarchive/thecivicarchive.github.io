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
                                  "ph": m["phone"], "cf": m["contact_form"], "cur": m["is_current"]}
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


LITE_STATUSES = {"", "Introduced", "In committee"}
POSITION_CODE = {"Yea": "Y", "Aye": "Y", "Nay": "N", "No": "N", "Present": "P"}


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

    full, lite, rated, years = [], [], 0, set()
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
        is_lite = (not votes and not ratings and not (b["law_number"] or "") and (b["status"] or "") in LITE_STATUSES
                   and (b["outcome"] or "Pending") == "Pending")
        if is_lite:
            lite.append([key, display_title(b["title"] or "", b["short_title"] or ""), b["sponsor_bioguide"] or "",
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
            "short_title": display_title(b["title"] or "", b["short_title"] or ""),
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
            "ratings": ratings or None, "review": review})

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
    ids = set(mv["H"]["ids"]) | set(mv["S"]["ids"])
    legislators = legislator_rows(con, sorted(ids))
    photos = {}
    if has("photos"):
        need = set(legislators) | {m["id"] for m in members.values() if m["bd"]}
        for bid, blob in con.execute("SELECT bioguide_id, webp FROM photos WHERE webp IS NOT NULL"):
            if bid in need:
                photos[bid] = base64.b64encode(blob).decode("ascii")
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
    return {"generated": dt.datetime.now().strftime("%B %d, %Y"), "bills": full, "lite": {"rows": lite, "dict": dicts},
            "members": sorted(members.values(), key=lambda m: m["name"] or ""), "stats": stats,
            "rubric": next((r["version"] for b in full for a, r in (b["ratings"] or {}).items() if a != "backing"), "v1.1"),
            "legislators": legislators, "photos": photos, "mv": mv, "vote_meta": vote_meta,
            "states": state_paths(topo) if os.path.exists(topo) else {}, "districts": districts}


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


TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Plain Congress: every bill, who it helps, in plain words</title>
<meta name="description" content="Every bill in Congress with plain-language summaries, transparent ratings, and a state-by-state map of every recorded vote.">
<meta name="theme-color" content="#F5F5F2" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#0F1114" media="(prefers-color-scheme: dark)">
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
@media (max-width:760px){.nav{display:none}.kbtn span,.kbtn kbd{display:none}.kbtn{width:38px;padding:0;justify-content:center}}

/* hero */
.hero{padding:56px 0 44px;position:relative}
.hero .wrap{display:grid;gap:36px;grid-template-columns:1fr}
@media (min-width:960px){.hero{padding:88px 0 76px}.hero .wrap{grid-template-columns:minmax(0,1.1fr) minmax(0,.9fr);align-items:center;gap:56px}}
.hero h1{font-size:clamp(46px,7vw,84px);line-height:.98;max-width:12ch;text-wrap:balance}
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
.hero h1 .w{display:inline-block;overflow:hidden;vertical-align:bottom;padding:0 .04em .14em 0;margin:0 -.04em -.14em 0}
.hero h1 .w>span{display:inline-block;transform:translateY(108%);animation:wordup .95s var(--ease) forwards}
@keyframes wordup{to{transform:none}}
.hero{overflow:hidden}
.hero canvas{position:absolute;inset:0;width:100%;height:100%;pointer-events:none}
.hero:after{content:"";position:absolute;inset:0;pointer-events:none;background:radial-gradient(75% 85% at 22% 45%,var(--bg) 30%,transparent 72%)}
.hero .wrap{position:relative;z-index:1}
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
.selwrap select{appearance:none;-webkit-appearance:none;border:0;background:transparent;font:inherit;font-weight:600;color:var(--ink);cursor:pointer;padding:0}
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
svg.usmap{width:100%;height:auto;display:block}
.mapback{position:absolute;left:8px;top:8px;z-index:2;height:38px;padding:0 14px 0 8px;font-size:14px;border-color:var(--line-strong);background:var(--surface);color:var(--ink);animation:rowin .35s var(--ease) both}
.mapback[hidden]{display:none}
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
.repmodal[hidden]{display:none}
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
.totop{position:fixed;right:18px;bottom:18px;width:44px;height:44px;border-radius:50%;background:var(--surface);border:1px solid var(--line);box-shadow:var(--shadow-2);display:grid;place-items:center;z-index:40;opacity:0;transform:translateY(12px);pointer-events:none;transition:opacity .3s,transform .3s var(--ease),border-color .15s}
.totop.show{opacity:1;transform:none;pointer-events:auto}
.totop:hover{border-color:var(--ink)}
.totop svg{width:18px;height:18px;stroke:currentColor;fill:none;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
.toast{position:fixed;left:50%;bottom:22px;transform:translate(-50%,16px);opacity:0;background:var(--ink);color:var(--bg);padding:10px 16px;border-radius:999px;font-size:14px;font-weight:500;transition:opacity .25s,transform .3s var(--ease);pointer-events:none;z-index:60;box-shadow:var(--shadow-3)}
.toast.show{opacity:1;transform:translate(-50%,0)}
.palette{position:fixed;inset:0;z-index:50}
.palette[hidden]{display:none}
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
@media (max-width:760px){.mtog .lab{display:none}.mtog{padding:0 8px}}
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
<a class="skip" href="#bills">Skip to bills</a>
<header class="top">
  <div class="wrap">
    <a class="brand" href="#top" aria-label="Plain Congress, top of page"><svg class="mark" viewBox="0 0 28 28" aria-hidden="true"><path d="M14 3v2.5"/><path d="M6.5 13.5a7.5 7.5 0 0 1 15 0"/><path d="M4 13.5h20"/><path d="M6.5 16.5v6M11.5 16.5v6M16.5 16.5v6M21.5 16.5v6"/><path d="M3 24h22"/></svg><span>Plain Congress</span></a>
    <nav class="nav" aria-label="Sections">
      <a href="#bills">Bills</a><a href="#map">Vote map</a><a href="#how">How ratings work</a><a href="#members">Your members</a>
    </nav>
    <div class="tools">
      <button class="kbtn" id="palettebtn" aria-label="Search bills and members"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/></svg><span>Search</span><kbd>⌘K</kbd></button>
      <button class="mtog" id="motion" aria-pressed="true" title="Living portraits and page motion: on or off"><span class="sw" aria-hidden="true"><i></i></span><span class="lab">Motion</span></button>
      <button class="iconbtn" id="theme" aria-label="Switch between light and dark" title="Light / dark">
        <svg class="moon" viewBox="0 0 24 24" aria-hidden="true"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>
        <svg class="sun" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>
      </button>
    </div>
  </div>
</header>

<section class="hero" id="top">
  <canvas id="field" aria-hidden="true"></canvas>
  <div class="wrap">
    <div class="hero-copy">
      <h1>Every bill in Congress. Who it helps, in plain words.</h1>
      <p class="lede">Search any bill, see how it moved and who voted, and get a short answer to the questions people actually ask: who gains, who backed it, and when it hits.</p>
      <div class="cta"><a class="btn primary" href="#map">See who voted</a><a class="btn" href="#bills">Browse bills</a></div>
      <dl class="stats" aria-label="What is on record">
        <div><dd data-count="__MEASURES__">0</dd><dt>__SETLABEL__</dt></div>
        <div><dd data-count="__LAWS__">0</dd><dt>became law</dt></div>
        <div><dd data-count="__VOTES__">0</dd><dt>floor votes recorded</dt></div>
        <div><dd data-count="__MEMBERS__">0</dd><dt>members on record</dt></div>
      </dl>
    </div>
    <div class="spotlight" id="heropanel" aria-live="polite">
      <div class="spot-head"><b>A rated bill</b><span>Facts from the record, ratings with their evidence</span></div>
      <div class="fade" id="herobody"></div>
      <div class="pfoot">
        <div class="dots" id="herodots" role="tablist" aria-label="Featured bills"></div>
        <button class="more" id="herogo">Open this bill <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 9l6 6 6-6"/></svg></button>
      </div>
    </div>
  </div>
</section>

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

<main>
  <section class="theater block" id="map">
    <div class="wrap">
      <div class="sechead rv">
        <div><h2>Who voted how, state by state</h2><p>Pick a recorded vote. Each state is colored by the party of its members and how they voted: solid means yes, striped means no, gray means not voting. A split delegation shows the split. Tap a state for the names.</p></div>
      </div>
      <div class="theater-grid">
        <div class="stage rv">
          <div class="mtip" id="mtip" role="tooltip"></div>
          <div class="votebar">
            <button class="iconbtn" id="vprev" aria-label="Newer vote"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M15 6l-6 6 6 6"/></svg></button>
            <label class="selwrap"><span class="sr-only">Vote</span><select id="vsel" aria-label="Choose a recorded vote"></select><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 9l6 6 6-6"/></svg></label>
            <button class="iconbtn" id="vnext" aria-label="Older vote"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 6l6 6-6 6"/></svg></button>
          </div>
          <div class="mapsub" id="mapsub"></div>
          <div class="mapframe">
            <button class="btn mapback" id="mapback" hidden><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M15 6l-6 6 6 6"/></svg>All states</button>
            <svg class="usmap" id="usmap" viewBox="0 0 975 610" role="img" aria-label="Map of the United States colored by how each state's members voted"></svg>
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

  <section class="block" id="members">
    <div class="wrap">
      <div class="sechead rv">
        <div><h2>Your members</h2><p>Find a senator or representative to see which bills they sponsored or cosponsored, then read how they voted on the map.</p></div>
      </div>
      <div class="members">
        <div class="rv">
          <label class="search"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/></svg>
            <input id="mq" type="search" placeholder="Name or state, for example Klobuchar or MN" autocomplete="off" aria-label="Search members"></label>
          <ul class="mlist" id="mlist"></ul>
        </div>
        <div id="mpick" class="mpick rv" style="--i:1">Pick a member to filter the bill list above.</div>
      </div>
    </div>
  </section>
</main>

<footer>
  <div class="wrap">
    <div class="fgrid">
      <div class="rv">
        <a class="brand" href="#top"><svg class="mark" viewBox="0 0 28 28" aria-hidden="true"><path d="M14 3v2.5"/><path d="M6.5 13.5a7.5 7.5 0 0 1 15 0"/><path d="M4 13.5h20"/><path d="M6.5 16.5v6M11.5 16.5v6M16.5 16.5v6M21.5 16.5v6"/><path d="M3 24h22"/></svg><span>Plain Congress</span></a>
        <p>__FOOTNOTE__</p>
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
<div class="toast" id="toast" role="status"></div>
<button class="totop" id="totop" aria-label="Back to top"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 19V5M5 12l7-7 7 7"/></svg></button>

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
const DATA = __DATA__;
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
const MEMBER = Object.fromEntries(DATA.members.map(m => [m.id, m]));
DATA.members.forEach(m => { let acc = 0; m.bills = (m.bd || []).map(d => (acc += d)); });
(function(){
  const L = DATA.lite; if (!L) return; const D = L.dict;
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
})();
DATA.bills.forEach((b, i) => {
  b._i = i;
  const k = b.key.match(/^([a-z]+)(\d+)-(\d+)$/), T = k && PC_TYPES[k[1]];
  const own = Object.fromEntries(Object.entries(b.links || {}).filter(([, v]) => v));
  if (T) { const page = `https://www.congress.gov/bill/${pcOrdinal(Number(k[3]))}-congress/${T[1]}/${k[2]}`;
    b.links = Object.assign({page, text: page + "/text", actions: page + "/all-actions", cosponsors: page + "/cosponsors", committees: page + "/committees"}, own); }
  else b.links = own;
});
const VOTE_IDS = new Set((DATA.vote_meta || []).map(v => v.vote_id));
const TYPE_ORDER = {hr: 0, s: 1, hjres: 2, sjres: 3, hconres: 4, sconres: 5, hres: 6, sres: 7};
const keyParts = key => { const m = key.match(/^([a-z]+)(\d+)-(\d+)$/); return m ? [+m[3], TYPE_ORDER[m[1]] ?? 9, +m[2]] : [0, 9, 0]; };
const isRated = b => !!(b.ratings && (b.ratings.income || b.ratings.households_business || b.ratings.plain_language || b.ratings.timing || b.ratings.rights));

/* ---------- theme ---------- */
(function(){
  let saved = null; try { saved = localStorage.getItem("theme"); } catch(e) {}
  if (saved) document.documentElement.dataset.theme = saved;
  $("#theme").addEventListener("click", () => {
    const dark = document.documentElement.dataset.theme === "dark" || (!document.documentElement.dataset.theme && matchMedia("(prefers-color-scheme: dark)").matches);
    const next = dark ? "light" : "dark";
    document.documentElement.classList.add("theming"); setTimeout(() => document.documentElement.classList.remove("theming"), 520);
    document.documentElement.dataset.theme = next;
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
function lensChips(b){ return (b.lens || []).map(l => `<span class="pill lens">${esc(l.replace(" (subj.)", ""))}</span>`).join(""); }

/* ---------- detail panes ---------- */
function paneFor(b){
  const r = b.ratings || {}, p = r.plain_language && r.plain_language.plain, t = r.timing && r.timing.plain, rf = r.rights && r.rights.flags;
  const who = p && p.if_you_are ? `<div class="who">` + Object.entries(p.if_you_are).map(([k, v]) => `<div><b>${esc({worker:"If you work for a living", parent:"If you have kids", retiree:"If you are retired", small_business_owner:"If you run a small business", disability:"If you or someone you care for has a disability"}[k] || k)}</b>${esc(v)}</div>`).join("") + `</div>` : `<p class="na">Not rated yet.</p>`;
  const notdo = p && p.what_it_does_not_do ? `<p class="note">What it does not do: ${esc(p.what_it_does_not_do)}</p>` : "";
  const timeline = t ? `<p style="font-size:15px">${esc(t.plain || "")}</p><ul class="tl"><li><b>Starts</b><span>${esc(t.effective || "")}</span></li>${(t.phase_changes || []).map(c => `<li><b>${esc(c.date || "")}</b><span>${esc(c.what || "")}</span></li>`).join("")}<li><b>Ends</b><span>${esc(t.sunset || "")}</span></li></ul>${t.delayed_cost && String(t.delayed_cost).startsWith("yes") ? `<p class="note">Watch the timing: ${esc(t.delayed_cost)}</p>` : ""}` : `<p class="na">Not rated yet.</p>`;
  const flags = rf ? ((rf.flags || []).length ? rf.flags.map(f => `<div class="flag"><span class="k">${esc(f.flag.replace(/_/g, " "))}</span><span>${esc(f.plain)}</span></div>`).join("") : `<p class="muted">No changes to who can sue, which laws apply, or who decides.</p>`) + (rf.election_rules ? `<p class="note">This bill changes election rules.</p>` : "") : `<p class="na">Not rated yet.</p>`;
  const votes = b.votes && b.votes.length ? b.votes.map(v => `<div class="vote"><span class="ch">${esc(v.chamber)}</span><span>${esc(v.category)}: ${esc(v.result || "")}${v.note ? " (" + esc(v.note) + ")" : ""}${VOTE_IDS.has(v.vote_id) ? `<a class="maplink" href="#map" data-vote="${esc(v.vote_id)}">see the map</a>` : ""}<br><span class="muted">${esc(fmtDate(v.date))}${v.split ? " · " + esc(v.split) : ""}</span></span>${v.yeas != null ? `<span class="tally">${v.yeas}–${v.nays}${v.url ? ` <a href="${esc(v.url)}" target="_blank" rel="noopener" style="font-size:12px;font-weight:400">roll call</a>` : ""}</span>` : `<span class="muted">${esc(v.method || "")}</span>`}</div>`).join("") : `<p class="muted">No floor votes yet.</p>`;
  const path = `<p style="font-size:14px"><b>Committees.</b> ${esc(b.committees || "None recorded")}</p>${b.committee_votes ? `<p style="font-size:14px"><b>Committee votes.</b> ${esc(b.committee_votes)}</p>` : ""}${b.related_enacted ? `<p class="note">Related measure became law: ${esc(b.related_enacted)}. The text may have been enacted inside another bill.</p>` : ""}`;
  const why = ["income", "households_business", "backing"].filter(a => r[a]).map(a => { const x = r[a]; return `<article><h4>${esc({income:"Who gains, by income", households_business:"Households vs. businesses", backing:"Who backed it"}[a])} <i class="grade" data-g="${esc(x.grade||"")}">${esc(x.grade||"")}</i>${x.confidence != null ? `<span class="muted" style="font-weight:400;font-size:13px">confidence ${Math.round(x.confidence * 100)}%</span>` : ""}</h4><p>${esc(x.justification || "")}</p>${x.magnitude_note ? `<p class="muted">${x.magnitude ? "<b>" + esc(x.magnitude) + ".</b> " : ""}${esc(x.magnitude_note)}</p>` : ""}${(x.sources || []).length ? `<p class="muted">Sources: ${x.sources.map(s => esc((s.type || "") + (s.ref ? ": " + s.ref : ""))).join("; ")}</p>` : ""}</article>`; }).join("");
  const whyBlock = b.ratings ? `<div class="why">${why}</div><p class="note">${esc(b.review)}. Rubric ${esc((r.income || r.plain_language || r.backing || {}).version || "")}, rated ${esc(((r.income || r.plain_language || r.backing || {}).rated_at || "").slice(0, 10))}.</p>` : `<p class="na">Not rated yet. Bills are rated after their first committee action or when an official cost estimate is published.</p>`;
  const L = b.links || {};
  const links = [["page", "Congress.gov page"], ["text", "Bill text"], ["pdf", "Latest text (PDF)"], ["actions", "All actions"], ["cosponsors", "Cosponsors"], ["committees", "Committees"], ["cbo", "CBO cost estimate"]].filter(([k]) => L[k]).map(([k, lab]) => `<a href="${esc(L[k])}" target="_blank" rel="noopener">${lab}</a>`).join("");
  const facts = `${b.short_title && b.short_title !== b.title ? `<p style="font-size:14px"><b>Official title.</b> ${esc(b.title)}</p>` : ""}${b.source_update ? `<p class="note">Record last updated by the Library of Congress on ${esc(fmtDate(b.source_update))}.${Number(b.congress) < 119 ? " Sample files are snapshots." : ""}</p>` : ""}<p style="font-size:14px"><b>${esc(b.kind || "Bill")}</b> introduced ${esc(fmtDate(b.introduced))} in the ${esc(b.origin)}${b.sponsor ? ` by ${esc(b.sponsor.name)}` : ""}. ${b.cosponsors && b.cosponsors.total ? `${b.cosponsors.total} cosponsors${b.cosponsors.by_party ? " (" + esc(b.cosponsors.by_party) + ")" : ""}.` : "No cosponsors."} ${b.policy_area ? "Policy area: " + esc(b.policy_area) + "." : ""}</p>${b.subjects && b.subjects.length ? `<p class="muted" style="font-size:13px">Subjects: ${b.subjects.map(esc).join(", ")}</p>` : ""}${b.summary ? `<p style="font-size:14px"><b>Official summary</b> (${esc(b.summary_desc)}, ${esc(fmtDate(b.summary_date))}): ${esc(b.summary)}</p>` : ""}`;
  const tabs = [["you", "For you", who + notdo], ["time", "When it hits", timeline], ["rights", "Your rights", flags], ["votes", "Votes and path", votes + path], ["why", "Why this rating", whyBlock], ["facts", "Facts and links", facts + `<div class="links">${links}</div>`]];
  const first = isRated(b) ? 0 : (b.votes && b.votes.length ? 3 : 5);
  return `<div class="tabs" role="tablist">${tabs.map(([k, lab], i) => `<button class="tab" role="tab" data-t="${k}" aria-selected="${i === first}">${lab}</button>`).join("")}</div>${tabs.map(([k, , html], i) => `<div class="pane${i === first ? " show" : ""}" data-p="${k}">${html}</div>`).join("")}`;
}

/* ---------- cards ---------- */
function cardHTML(b){
  return `<article class="card" data-key="${esc(b.key)}"><div class="head"><span class="pill id">${esc(b.id)}</span>${statusPill(b)}${b.law ? `<span class="pill intro">P.L. ${esc(b.law)}</span>` : ""}${lensChips(b)}</div>
  <div class="title">${esc(b.short_title || b.title)}</div><p class="plain">${plainLine(b)}</p>${axes(b)}
  <div class="meta"><span>Latest: <b>${esc(fmtDate(b.latest_action_date))}</b></span>${b.sponsor ? `<span class="spon">${avatar(b.sponsor.id, b.sponsor.party, "sm")}<b>${esc(prettyStr(b.sponsor.name))}</b> ${esc((b.sponsor.name.match(/\[(.*?)\]/) || [,""])[1])}</span>` : ""}${b.cosponsors && b.cosponsors.total ? `<span><b>${b.cosponsors.total}</b> cosponsors${b.bipartisan ? ", both parties" : ""}</span>` : ""}</div>
  <div class="detail"><div></div></div>
  <div class="foot"><span class="status">${b.review ? esc(b.review) : (b.latest_action ? esc(b.latest_action.length > 90 ? b.latest_action.slice(0, 88).replace(/\s+\S*$/, "") + "…" : b.latest_action) : "Not rated yet")}</span><span class="acts"><button class="copylink" aria-label="Copy a link to ${esc(b.id)}" title="Copy link"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M10 13a5 5 0 0 0 7.5.5l3-3a5 5 0 0 0-7-7l-1.7 1.7"/><path d="M14 11a5 5 0 0 0-7.5-.5l-3 3a5 5 0 0 0 7 7l1.7-1.7"/></svg></button><button class="more" aria-expanded="false">Details <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 9l6 6 6-6"/></svg></button></span></div></article>`;
}

const grid = $("#grid"), state = { q: "", f: "all", sort: "recent", member: null, pin: null };
const hay = b => b._hay ?? (b._hay = [b.id, b.title, b.short_title, b.policy_area, (b.subjects || []).join(" "), b.sponsor ? b.sponsor.name : "", b.law ? "p.l. " + b.law : "", b.summary].join(" ").toLowerCase());
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
const photo = id => (id && DATA.photos && DATA.photos[id]) ? "data:image/webp;base64," + DATA.photos[id] : "";
function avatar(id, party, cls){
  const src = photo(id), p = esc(party || ""), pc = party === "R" ? "rep" : (party === "D" ? "dem" : (party === "L" ? "amber" : "plum"));
  let h = 0; for (const ch of String(id || "")) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  const kb = src && cls !== "sm" ? ` kb" style="--pc:var(--${pc});--kbd:${11 + h % 7}s;--kbo:-${h % 11}s;--kbx:${(h % 3) - 1 ? ((h % 3) - 1) * 3 : 2}%;--kby:${(h >> 3) % 2 ? 3 : -2}%` : `" style="--pc:var(--${pc})`;
  return `<span class="avw ${cls || ""}${kb}"><span class="avc"><span class="avz">${src ? `<img class="av" src="${src}" alt="" decoding="async">` : `<span class="av av-txt">${p.slice(0, 1)}</span>`}</span></span><i class="pb">${p}</i></span>`;
}
const rvIO = new IntersectionObserver(es => es.forEach(e => { if (e.isIntersecting) { e.target.classList.add("in", "live"); rvIO.unobserve(e.target); } }), {threshold: .12, rootMargin: "0px 0px -6% 0px"});
const reveal = root => $$(".rv:not(.obs)", root).forEach(el => { el.classList.add("obs"); rvIO.observe(el); });
const roleOf = m => m.name.startsWith("Sen.") ? "Senator" : (m.chamber === "Senate" ? "Senator" : "Representative");
const byKey = Object.fromEntries(DATA.bills.map(b => [b.key, b]));
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
function render(){
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
  const cl = e.target.closest(".copylink");
  if (cl) {
    const url = location.href.split("#")[0] + "#bill=" + cl.closest(".card").dataset.key;
    (navigator.clipboard ? navigator.clipboard.writeText(url) : Promise.reject()).then(() => toast("Link copied"), () => prompt("Copy this link", url));
    return;
  }
  const more = e.target.closest(".more"), tab = e.target.closest(".tab");
  if (tab) {
    const card = tab.closest(".card");
    $$(".tab", card).forEach(t => t.setAttribute("aria-selected", t === tab));
    $$(".pane", card).forEach(p => p.classList.toggle("show", p.dataset.p === tab.dataset.t));
    return;
  }
  if (!more) return;
  const card = more.closest(".card"), open = !card.classList.contains("open");
  if (open && !card.dataset.built) { $(".detail > div", card).innerHTML = paneFor(byKey[card.dataset.key]); card.dataset.built = "1"; }
  card.classList.toggle("open", open);
  const bill = byKey[card.dataset.key]; if (bill && bill.short_title && bill.short_title !== bill.title) $(".title", card).textContent = open ? bill.title : bill.short_title;
  more.setAttribute("aria-expanded", open);
  more.firstChild.textContent = open ? "Close " : "Details ";
  if (open) setTimeout(() => card.scrollIntoView({block: "nearest", behavior: "smooth"}), 60);
});
let qTimer; $("#q").addEventListener("input", e => { clearTimeout(qTimer); qTimer = setTimeout(() => { state.q = e.target.value; render(); }, 140); });
if (DATA.bills.every(b => Number(b.congress) >= 119)) { const c = $('.chip[data-f="119"]'); if (c) c.remove(); }
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
  const card = $(`.card[data-key="${CSS.escape(key)}"]`); if (!card) return false;
  card.classList.add("in", "live");
  if (!card.classList.contains("open")) $(".more", card).click();
  setTimeout(() => card.scrollIntoView({block: "start", behavior: "smooth"}), 80);
  return true;
}

/* ---------- hero carousel ---------- */
const hasPos = r => r && r.position != null;
const featured = DATA.bills.filter(b => b.ratings && (hasPos(b.ratings.income) || hasPos(b.ratings.households_business)))
  .sort((a, b) => Number(b.congress) - Number(a.congress) || (b.ratings.income && b.ratings.income.grade === "A" ? 1 : 0) - (a.ratings.income && a.ratings.income.grade === "A" ? 1 : 0) || a.key.localeCompare(b.key, undefined, {numeric: true}));
let hi = 0, htimer;
function heroShow(i, animate){
  hi = (i + featured.length) % featured.length;
  const b = featured[hi], body = $("#herobody");
  const paint = () => {
    body.innerHTML = `<div class="pid"><span class="pill id">${esc(b.id)}</span>${statusPill(b)}${b.law ? `<span class="pill intro">P.L. ${esc(b.law)}</span>` : ""}${lensChips(b)}</div><div class="ptitle">${esc(b.short_title || b.title)}</div><p class="pplain">${plainLine(b)}</p>${b.sponsor ? `<div class="spot-spon">${avatar(b.sponsor.id, b.sponsor.party, "md")}<span>Sponsored by <b>${esc(prettyStr(b.sponsor.name))}</b>, ${esc(b.sponsor.party)}-${esc(b.sponsor.state)}</span></div>` : ""}${axes(b)}`;
    body.classList.remove("out");
    requestAnimationFrame(() => requestAnimationFrame(() => $(".axes", body).classList.add("live")));
  };
  if (animate) { body.classList.add("out"); setTimeout(paint, 360); } else paint();
  $$("#herodots button").forEach((d, j) => d.setAttribute("aria-current", j === hi));
}
if (featured.length) {
  $("#herodots").innerHTML = featured.map((b, i) => `<button role="tab" aria-label="Show ${esc(b.id)}" aria-current="${i === 0}"></button>`).join("");
  $("#herodots").addEventListener("click", e => { const i = $$("#herodots button").indexOf(e.target.closest("button")); if (i >= 0) { heroShow(i, true); restart(); } });
  $("#herogo").addEventListener("click", () => openBill(featured[hi].key));
  const restart = () => { clearInterval(htimer); if (!calm()) htimer = setInterval(() => heroShow(hi + 1, true), 9000); };
  window.heroRestart = restart; window.heroPause = () => clearInterval(htimer);
  $("#heropanel").addEventListener("mouseenter", () => clearInterval(htimer));
  $("#heropanel").addEventListener("mouseleave", restart);
  heroShow(0, false); restart();
} else { $("#heropanel").style.display = "none"; }

/* ---------- hero: word reveal and the member field ---------- */
(function(){
  const h = $(".hero h1"); if (!h) return;
  h.innerHTML = h.textContent.trim().split(/\s+/).map((w, i) => `<span class="w"><span style="animation-delay:${60 + i * 60}ms">${esc(w)}</span></span>`).join(" ");
})();
(function(){
  const c = $("#field"); if (!c) return;
  const ctx = c.getContext("2d");
  const L = Object.values(DATA.legislators || {}).filter(l => l.cur);
  let mix = L.length >= 400 ? L.map(l => l.p === "R" ? "R" : (l.p === "D" ? "D" : "I")) : [].concat(Array(273).fill("R"), Array(258).fill("D"), Array(4).fill("I"));
  let W = 0, H = 0, dots = [], raf = 0, colors = null, frame = 0;
  const t0 = performance.now();
  const readColors = () => { const cs = getComputedStyle(document.documentElement); colors = {R: cs.getPropertyValue("--rep").trim(), D: cs.getPropertyValue("--dem").trim(), I: cs.getPropertyValue("--plum").trim()}; };
  function size(){
    const r = c.parentElement.getBoundingClientRect(), dpr = Math.min(2, devicePixelRatio || 1);
    W = r.width; H = r.height; c.width = W * dpr; c.height = H * dpr; ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const pool = W < 640 ? mix.filter((_, i) => i % 2 === 0) : mix, n = pool.length;
    const cols = Math.ceil(Math.sqrt(n * W / Math.max(1, H))), rows = Math.ceil(n / cols), gx = W / cols, gy = H / rows;
    let seed = 7; const rnd = () => (seed = (seed * 9301 + 49297) % 233280) / 233280;
    const order = pool.slice().sort(() => rnd() - .5);
    dots = order.map((p, i) => ({p, x: (i % cols + .5) * gx, y: (Math.floor(i / cols) + .5) * gy, ph: rnd() * 6.283, s: .6 + rnd() * .8}));
    readColors();
  }
  function paint(now){
    const t = (now - t0) / 1000; if (++frame % 90 === 0) readColors();
    ctx.clearRect(0, 0, W, H);
    const wave = ((t % 8) / 8) * (W + 360) - 180;
    for (const d of dots) {
      const dx = Math.sin(t * .45 * d.s + d.ph) * 5, dy = Math.cos(t * .38 * d.s + d.ph) * 5;
      const near = Math.max(0, 1 - Math.abs(d.x + dx - wave) / 150);
      ctx.globalAlpha = .2 + near * .6; ctx.fillStyle = colors[d.p] || colors.I;
      ctx.beginPath(); ctx.arc(d.x + dx, d.y + dy, 2.4 + near * 2.2, 0, 6.283); ctx.fill();
    }
    raf = calm() ? 0 : requestAnimationFrame(paint);
  }
  size(); paint(t0);
  addEventListener("resize", () => { size(); if (calm()) paint(performance.now()); });
  window.fieldResume = () => { if (!raf) raf = requestAnimationFrame(paint); };
  new IntersectionObserver(es => es.forEach(e => { if (e.isIntersecting) { if (!raf && !calm()) raf = requestAnimationFrame(paint); } else if (raf) { cancelAnimationFrame(raf); raf = 0; } })).observe(c);
})();

/* ---------- counters ---------- */
$$("[data-count]").forEach(el => {
  const target = Number(el.dataset.count), t0 = performance.now() + 700, dur = calm() ? 1 : 1600;
  const tick = now => { const p = Math.max(0, Math.min(1, (now - t0) / dur)), e = 1 - Math.pow(1 - p, 3); el.textContent = Math.round(target * e).toLocaleString(); if (p < 1) requestAnimationFrame(tick); };
  requestAnimationFrame(tick);
});

/* ---------- members ---------- */
const mlist = $("#mlist");
function renderMembers(){
  const q = $("#mq").value.trim().toLowerCase();
  const list = DATA.members.filter(m => m.bills.length && (!q || m.name.toLowerCase().includes(q) || m.state.toLowerCase() === q)).sort((a, b) => b.bills.length - a.bills.length).slice(0, 12);
  mlist.innerHTML = list.map((m, i) => `<li style="--i:${i}"><button data-m="${esc(m.id)}">${avatar(m.id, m.party, "md")}<span class="mname"><b>${esc(prettyName(m))}</b><span class="muted">${esc(roleOf(m))}, ${esc(m.state)}</span></span><span class="mcount">${m.sponsored ? m.sponsored + " sponsored" : ""}${m.sponsored && m.cosponsored ? ", " : ""}${m.cosponsored ? m.cosponsored + " cosponsored" : ""}</span></button></li>`).join("") || `<li class="empty" style="padding:24px">No member matches. Try a last name or a two-letter state.</li>`;
}
$("#mq").addEventListener("input", renderMembers);
function pickMember(id){
  const m = MEMBER[id]; if (!m) return;
  m.set = m.set || new Set(m.bills); state.member = m;
  const L = (DATA.legislators || {})[id] || {}, yrs = d => d ? Math.floor((Date.now() - new Date(d + "T12:00:00")) / 3.15576e10) : null;
  const facts = [roleOf(m) + (L.d ? `, district ${L.d}` : "") + `, ${m.state}`, L.f ? `in Congress since ${L.f.slice(0, 4)} (${yrs(L.f)} yrs)` : "", L.b ? `age ${yrs(L.b)}` : ""].filter(Boolean).join(", ");
  const links = [L.u ? `<a href="${esc(L.u)}" target="_blank" rel="noopener">Official site</a>` : "", L.ph ? `<a href="tel:${esc(L.ph)}">${esc(L.ph)}</a>` : "", L.cf ? `<a href="${esc(L.cf)}" target="_blank" rel="noopener">Contact form</a>` : "", `<a href="https://www.congress.gov/member/${encodeURIComponent(prettyName(m).toLowerCase().replace(/[^a-z0-9]+/g, "-"))}/${esc(id)}" target="_blank" rel="noopener">Congress.gov</a>`].filter(Boolean).join("");
  $("#mpick").innerHTML = `<div class="prof">${avatar(id, m.party, "xl")}<div><b>${esc(prettyName(m))}</b><div class="muted">${esc(facts)}</div><div class="mlinks">${links}</div></div></div>
    <p><b>${m.bills.length}</b> bill${m.bills.length === 1 ? "" : "s"} in this set${m.sponsored ? `, ${m.sponsored} sponsored` : ""}${m.cosponsored ? `, ${m.cosponsored} cosponsored` : ""}. The list above now shows only theirs. <button class="chip" id="mclear">Show all bills</button></p>`;
  render(); toast(`Showing bills for ${prettyName(m)}`);
  document.getElementById("bills").scrollIntoView({behavior: "smooth"});
}
mlist.addEventListener("click", e => { const btn = e.target.closest("button[data-m]"); if (btn) pickMember(btn.dataset.m); });
$("#mpick").addEventListener("click", e => { if (e.target.id === "mclear") { state.member = null; $("#mpick").textContent = "Pick a member to filter the bill list above."; render(); } });
function toast(msg){ const t = $("#toast"); t.textContent = msg; t.classList.add("show"); clearTimeout(t._t); t._t = setTimeout(() => t.classList.remove("show"), 2200); }

/* ---------- top bar follows the dark map section ---------- */
(function(){
  const bar = $(".top"), th = $("#map"); if (!bar || !th) return;
  let tick = false;
  const check = () => { tick = false; const r = th.getBoundingClientRect(); bar.classList.toggle("over-dark", r.top < 62 && r.bottom > 62 && th.style.display !== "none"); bar.classList.toggle("scrolled", scrollY > 12); $("#totop").classList.toggle("show", scrollY > 1400); };
  addEventListener("scroll", () => { if (!tick) { tick = true; requestAnimationFrame(check); } }, {passive: true});
  check();
})();

/* ---------- vote map ---------- */
(function(){
  const svg = $("#usmap"), sel = $("#vsel"), side = $("#mapside"), states = DATA.states || {}, LEG = DATA.legislators || {}, MVC = DATA.mv || {};
  const DIST = DATA.districts || {states: {}, q: 50}, DQ = DIST.q || 50, VB0 = [0, 0, 975, 610];
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
    $("#mapsub").innerHTML = `<div class="tally"><b class="num"><span class="v yv">${esc(String(yes))}</span><span>–</span><span class="v nv">${esc(String(no))}</span></b><span class="res ${passed ? "pass" : "fail"}">${esc(current.result || "")}</span></div>
      <div class="tsub"><b>${esc(current.bill)}</b> ${esc(current.title)}. ${esc(current.chamber)} ${esc(current.category.toLowerCase())}, ${esc(fmtDate(current.date))}.${current.url ? ` <a href="${esc(current.url)}" target="_blank" rel="noopener">Official roll call</a>` : ""}</div>
      ${rows.length ? `<div class="split">${rows.map(r => `<div style="--pc:var(--${r.c})"><span>${esc(r.name)}</span><span class="bar" aria-hidden="true"><i class="y" style="width:${r.yp.toFixed(1)}%"></i><i class="n" style="width:${r.np.toFixed(1)}%"></i></span><span><b>${r.y}</b> yes, <b>${r.n}</b> no</span></div>`).join("")}</div>` : ""}`;
    if (typeof yes === "number" && typeof no === "number") { tween($(".yv"), lastTally[0], yes); tween($(".nv"), lastTally[1], no); lastTally = [yes, no]; }
    if (zoomed) { if (current.chamber === "Senate" && DIST.states[zoomed]) { /* keep the zoom; senators show as the split state */ } buildDistricts(zoomed); }
    if (selected) showState(selected); else side.innerHTML = `<span class="muted" style="font-size:14px">Tap a state to zoom in. On a House vote you'll see its districts; tap one for the representative.</span>`;
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
  function openRep(m, st){
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
    $("#repbody").innerHTML = `<div class="rep-head">${avatar(m.id, m.p, "xl")}<div><h2>${esc(L.n)}</h2><div class="seat"><b>${esc(PARTY[m.p] || m.p)}</b>, ${esc(seat)}${L.cur ? "" : " (no longer serving)"}${since ? `<br>In Congress since ${since}${tenure != null ? ` (${Math.floor(tenure)} years)` : ""}` : ""}${age != null ? `, age ${Math.floor(age)}` : ""}</div></div></div>
      <div class="rep-grid">
        <div class="rep-block"><h4>This vote</h4><div class="rec"><span class="vtag ${esc(m.pos)}">${POSW[m.pos] || m.pos}</span><span>on <b>${esc(current.bill)}</b></span></div><div class="muted" style="margin-top:6px">${esc(current.title)}. ${esc(current.chamber)} ${esc(current.category.toLowerCase())}, ${esc(fmtDate(current.date))}: ${current.yeas ?? "?"} to ${current.nays ?? "?"}, ${esc((current.result || "").toLowerCase())}.</div></div>
        ${districtBlock}
        <div class="rep-block"><h4>Their votes on record here</h4>${recordHtml}</div>
        <div class="rep-block"><h4>Their bills</h4><div>${bills}</div>${mem && mem.bills.length ? `<div class="rep-links" style="margin-top:10px"><button id="repbills">Show their bills</button></div>` : ""}</div>
      </div>
      <div class="rep-links">${L.u ? `<a href="${esc(L.u)}" target="_blank" rel="noopener">Official site</a>` : ""}${L.ph ? `<a href="tel:${esc(L.ph)}">${esc(L.ph)}</a>` : ""}${L.cf ? `<a href="${esc(L.cf)}" target="_blank" rel="noopener">Contact form</a>` : ""}<a href="${cg}" target="_blank" rel="noopener">Congress.gov</a></div>`;
    const modal = $("#repmodal"); modal.hidden = false; document.body.classList.add("noscroll");
    const rb = $("#repbills"); if (rb) rb.addEventListener("click", () => { closeRep(); pickMember(m.id); });
    requestAnimationFrame(() => $("#repclose").focus());
  }
  function closeRep(){ $("#repmodal").hidden = true; document.body.classList.remove("noscroll"); }
  $("#repclose").addEventListener("click", closeRep); $(".rep-back").addEventListener("click", closeRep);
  document.addEventListener("keydown", e => { if (e.key === "Escape" && !$("#repmodal").hidden) { e.stopPropagation(); closeRep(); } }, true);
  function pick(st){ if (zoomed === st) { showState(st); return; } zoomTo(st); }
  const monthOf = d => d ? new Date(d.slice(0, 7) + "-15T12:00:00").toLocaleDateString("en-US", {year: "numeric", month: "long"}) : "Undated";
  const vgroups = new Map(); votes.forEach(v => { const g = monthOf(v.date); if (!vgroups.has(g)) vgroups.set(g, []); vgroups.get(g).push(v); });
  sel.innerHTML = [...vgroups].map(([g, vs]) => `<optgroup label="${esc(g)}">` + vs.map(v => `<option value="${esc(v.vote_id)}">${esc(v.bill)}: ${esc(v.chamber)} ${esc(v.category.toLowerCase())}, ${esc(fmtDate(v.date))} (${v.yeas ?? "?"}–${v.nays ?? "?"})</option>`).join("") + `</optgroup>`).join("");
  sel.addEventListener("change", () => paint(sel.value));
  const step = d => { const i = sel.selectedIndex + d; if (i < 0 || i >= sel.options.length) return; sel.selectedIndex = i; paint(sel.value); };
  $("#vprev").addEventListener("click", () => step(-1)); $("#vnext").addEventListener("click", () => step(1));
  document.addEventListener("click", e => { const a = e.target.closest("a.maplink"); if (!a) return; e.preventDefault(); zoomOut(); sel.value = a.dataset.vote; paint(sel.value); selected = null; document.getElementById("map").scrollIntoView({behavior: "smooth"}); });
  const missing = Math.max(0, (DATA.stats.rc_total || 0) - votes.length);
  $("#mapnote").textContent = `${votes.length.toLocaleString()} roll calls carry member-level votes${missing ? `; ${missing.toLocaleString()} more are listed on their bills without member data yet` : ""}. Party is shown as recorded on each roll call.${DIST.vintage ? ` District lines: ${DIST.vintage}.` : ""}`;
  paint(votes[0].vote_id);
})();

/* ---------- command palette, shortcuts, deep links ---------- */
(function(){
  const pal = $("#palette"), inp = $("#palq"), list = $("#pallist"); let items = [], idx = 0;
  const open = () => { pal.hidden = false; document.body.classList.add("noscroll"); inp.value = ""; run(""); requestAnimationFrame(() => inp.focus()); };
  const close = () => { pal.hidden = true; document.body.classList.remove("noscroll"); };
  const mark = () => { $$("li[data-i]", list).forEach(li => li.setAttribute("aria-selected", +li.dataset.i === idx)); const cur = $(`li[data-i="${idx}"]`, list); if (cur) cur.scrollIntoView({block: "nearest"}); };
  const go = i => { const it = items[i]; if (!it) return; close(); if (it.kind === "bill") openBill(it.key); else pickMember(it.id); };
  function run(q){
    q = q.trim().toLowerCase();
    const bills = (q ? DATA.bills.filter(b => hay(b).includes(q)) : DATA.bills.filter(isRated)).slice(0, 7);
    const mems = q ? DATA.members.filter(m => m.bills.length && (m.name.toLowerCase().includes(q) || m.state.toLowerCase() === q)).sort((a, b) => b.bills.length - a.bills.length).slice(0, 4) : [];
    items = [...bills.map(b => ({kind: "bill", key: b.key})), ...mems.map(m => ({kind: "member", id: m.id}))]; idx = 0;
    let n = 0;
    list.innerHTML = (bills.length ? `<li class="grp">${q ? "Bills" : "Rated bills"}</li>` + bills.map(b => `<li role="option" data-i="${n++}" style="--i:${n}"><span class="pill id">${esc(b.id)}</span><span class="t">${esc(b.short_title || b.title)}</span><span class="s">${esc(statusText(b))}</span></li>`).join("") : "")
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

$("#totop").addEventListener("click", () => scrollTo({top: 0, behavior: calm() ? "auto" : "smooth"}));
render(); renderMembers(); reveal(document); moveChipInd();
(function(){ const m = location.hash.match(/bill=([a-z0-9-]+)/i); if (m && byKey[m[1]]) setTimeout(() => openBill(m[1]), 60); })();
</script>
</body>
</html>
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", required=True)
    ap.add_argument("--out", default="site.html")
    ap.add_argument("--max-mb", type=float, default=15.0, help="size budget for the single-file page (claude.ai artifacts allow 16 MB)")
    ap.add_argument("--summary-chars", type=int, default=220, help="summary length kept for introduced-only measures")
    ap.add_argument("--as-of", default="", help="date to print as the generation date (YYYY-MM-DD); default today")
    args = ap.parse_args()
    data = collect(args.db)
    if args.as_of:
        data["generated"] = dt.datetime.strptime(args.as_of, "%Y-%m-%d").strftime("%B %d, %Y")
    for n_chars, n_subj in ((args.summary_chars, 4), (140, 3), (80, 2), (0, 0)):
        shaped = trim_lite(data, n_chars, n_subj)
        payload = json.dumps(shaped, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
        mb = len(payload.encode("utf-8")) / 1e6
        if mb <= args.max_mb - 0.3 or n_chars == 0:
            break
        print(f"  payload {mb:.1f} MB is over the {args.max_mb:g} MB budget; trimming summaries on introduced-only measures")
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
    html = (TEMPLATE.replace("__DATA__", payload).replace("__FOOTNOTE__", foot)
            .replace("__SETLABEL__", "measures in this demo set" if demo else "measures this Congress")
            .replace("__MEASURES__", str(st["measures"]))
            .replace("__LAWS__", str(st["laws"])).replace("__VOTES__", str(st["votes"])).replace("__MEMBERS__", str(st["members"]))
            .replace("__CURRENT__", str(st["current"])).replace("__RATED__", str(st["rated"])).replace("__YEARS__", st["years"])
            .replace("__GENERATED__", data["generated"]).replace("__RUBRIC__", data["rubric"]))
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(html)
    size = os.path.getsize(args.out) / 1e6
    print(f"Wrote {args.out}: {st['measures']:,} measures ({st['compact']:,} compact), {st['rated']:,} rated, "
          f"{st['roll_calls']:,} roll calls with member votes, {st['members']:,} members, {len(data['photos']):,} portraits, "
          f"{sum(len(v) for v in data['districts'].get('states', {}).values()):,} district shapes, {size:.1f} MB")
    if size > 16:
        print("WARNING: over 16 MB, too large to publish as a single claude.ai artifact; lower --summary-chars or host it elsewhere")

if __name__ == "__main__":
    main()
