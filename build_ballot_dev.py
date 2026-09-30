#!/usr/bin/env python3
"""
build_ballot_dev.py - On The Ballot, the Congress pages: site/dev/ballot/us/index.html.

    python build_ballot_dev.py

One page, routed by its address: the home page (your ballot, the Senate races, every state), a page per state
(#state=FL) and a page per race (#race=2026-FL-H07). A race page shows the November general election as an arena of
cards, one per candidate on the ballot, and the primaries that chose them as fields, one lane per candidate. The
arena opens into a side-by-side comparison: what each candidate is on the ballot as, their record in Congress if
they serve there today, and their campaign money from the FEC (organizations named, people as a total, outside
spending kept apart).

Rules the page keeps, as the rest of the site does: every card is the same size; candidates are shown in the order
the state's list gives, or by surname where the list gives no ballot order, never by money or polls; no score or
grade of any person; parties are printed exactly as the official list prints them. Nothing is shown for a state
until its official list is loaded; the page says which states are still to come.

Data: ballot_2026.sqlite (run_ballot.py), congress_119.sqlite for who holds each seat, and the draft site's member
files (site/dev/us/data/member/) for a sitting member's record, so both sides say the same thing. The page takes
the site's stylesheet and a few shared script parts from build_site_dev.py by the landmarks build_state_dev.py uses.
"""

import argparse
import datetime as dt
import json
import os
import sqlite3
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from ballot.common import DB, GENERAL, STATE_NAMES                              # noqa: E402
from build_site_dev import read_changelog, state_paths                          # noqa: E402
from build_state_dev import borrow                                              # noqa: E402
from money_views import KIND_LABELS, PAC_LIMIT, committee_kind, tidy_name       # noqa: E402

ELECTION_NAMES = {"general": "General election", "primary": "Top-two primary", "primary-DEM": "Democratic primary",
                  "primary-REP": "Republican primary", "primary-LPF": "Libertarian primary", "primary-GRE": "Green primary"}


def money(con, ids):
    """Each campaign's 2026 money as the FEC's files report it, for the candidates on a loaded list."""
    out = {}
    ids = sorted(i for i in ids if i)
    if not ids:
        return out
    q = ",".join("?" * len(ids))
    for r in con.execute(f"SELECT * FROM fec26_totals WHERE cand_id IN ({q})", ids):
        cid, receipts, indiv, cmte, party, self_, cloan, oloan, transfers, disb, coh, end = r
        out[cid] = {"r": receipts, "ind": indiv, "cmte": cmte, "pty": party, "self": (self_ or 0) + (cloan or 0), "coh": coh,
                    "end": end, "orgs": [], "moved": 0.0, "passed": 0.0, "for": 0.0, "against": 0.0, "forw": [], "agw": []}
    cm = {r[0]: r[1:] for r in con.execute("SELECT cmte_id, name, designation, type, party, org_type, connected_org, cand_id FROM fec26_committees")}
    gifts = defaultdict(lambda: defaultdict(float))
    per_election = defaultdict(float)
    outside = defaultdict(lambda: defaultdict(float))
    for cmte_id, cid, kind, election, amount, earmark in con.execute(
            f"SELECT cmte_id, cand_id, kind, election, amount, earmark FROM fec26_gifts WHERE cand_id IN ({q})", ids):
        m = out.setdefault(cid, {"r": None, "ind": None, "cmte": None, "pty": None, "self": None, "coh": None, "end": None, "orgs": [],
                                 "moved": 0.0, "passed": 0.0, "for": 0.0, "against": 0.0, "forw": [], "agw": []})
        name, dsgn, tp, _pty, org, _conn, owner = cm.get(cmte_id, ("", "", "", "", "", "", ""))
        k = committee_kind(tp, dsgn, org)
        if kind == "gift":
            if k == "joint" or (owner and owner == cid):      # the candidate's own fundraising passing through: moved in, not a donor
                m["moved"] += amount
                continue
            gifts[cid][cmte_id] += amount
            if earmark:
                m["passed"] += amount
            elif k not in ("party", "cand"):
                per_election[(cid, cmte_id, election)] += amount
        elif kind in ("for", "against", "talk_for", "talk_against"):
            side = "for" if kind in ("for", "talk_for") else "against"
            m[side] += amount
            outside[(cid, side)][cmte_id] += amount
    for (cid, cmte_id, election), total in per_election.items():      # the money_views rule: over $5,000 an election was passed along
        if total > PAC_LIMIT:
            out[cid]["passed"] += total - PAC_LIMIT
    for cid, by in gifts.items():
        top = sorted(by.items(), key=lambda kv: -kv[1])[:6]
        out[cid]["orgs"] = [[tidy_name(cm.get(c, ("",))[0]) or c, committee_kind(*[cm.get(c, ("",) * 7)[i] for i in (2, 1, 4)]), round(a)] for c, a in top]
    for (cid, side), by in outside.items():
        out[cid]["forw" if side == "for" else "agw"] = [[tidy_name(cm.get(c, ("",))[0]) or c, round(a)] for c, a in sorted(by.items(), key=lambda kv: -kv[1])[:3]]
    for m in out.values():
        for k in ("moved", "passed", "for", "against"):
            m[k] = round(m[k])
    return out


def member_facts(bios, site_root):
    """A sitting member's record, read from the draft site's own member files so both sides say the same thing."""
    out = {}
    for bio in sorted(b for b in bios if b):
        p = os.path.join(site_root, "us", "data", "member", f"{bio}.json")
        if not os.path.exists(p):
            continue
        d = json.load(open(p, encoding="utf-8"))
        s, v, f = d.get("service") or {}, d.get("votes") or {}, d.get("focus") or {}
        out[bio] = {"ch": s.get("chamber"), "since": (s.get("since") or "")[:4], "terms": s.get("terms"),
                    "cast": v.get("cast"), "elig": v.get("eligible"), "split": v.get("split_n"), "breaks": v.get("breaks_n"),
                    "spon": f.get("sponsored"), "laws": f.get("laws")}
    return out


def build(db, record_db, site_root):
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    rec = sqlite3.connect(f"file:{record_db}?mode=ro", uri=True)
    party_of = dict(rec.execute("SELECT bioguide_id, party FROM legislators WHERE is_current = 1"))
    chamber_of = dict(rec.execute("SELECT bioguide_id, chamber FROM legislators WHERE is_current = 1"))
    cands = defaultdict(lambda: defaultdict(list))
    runs = defaultdict(list)
    fec_ids, bios = set(), set()
    for (race, election, date, name, party, code, order, inc, wi, votes, pct, outcome, fec, bio, src, note) in con.execute(
            "SELECT race_id, election, election_date, name, party, party_code, ballot_order, incumbent, write_in, votes, pct, outcome, "
            "fec_id, bioguide_id, source_id, note FROM candidates"):
        office = "H" if "-H" in race else "S"
        sitting = int(bool(bio) and chamber_of.get(bio) == ("House" if office == "H" else "Senate"))
        c = {"n": name, "p": party, "pc": code, "inc": int(bool(inc) or sitting), "wi": wi, "o": order, "v": votes, "pct": pct,
             "out": outcome, "fec": fec, "bio": bio, "note": note, "src": src, "date": date}
        cands[race][election].append(c)
        fec_ids.add(fec)
        if bio:
            bios.add(bio)
            runs[bio].append([race, election, outcome])
    notes = {r[0]: {"changed": r[1], "note": r[2], "st": r[3], "su": r[4], "asof": r[5]} for r in con.execute("SELECT * FROM state_notes")}
    sources = {r[0]: {"state": r[2], "kind": r[3], "agency": r[4], "title": r[5], "url": r[6], "fetched": r[8], "sha": r[9], "rows": r[10], "note": r[11]}
               for r in con.execute("SELECT * FROM ballot_sources")}
    listed = {s["state"] for s in sources.values()}
    races = []
    for race, _level, office, st, dist, cls, special, holder, hname, hparty, gdate, note in con.execute(
            "SELECT * FROM races WHERE level = 'federal' ORDER BY state, office DESC, district"):
        if holder:
            bios.add(holder)
        races.append({"id": race, "st": st, "o": "H" if office == "U.S. House" else "S", "d": dist, "cls": cls, "sp": special,
                      "h": [holder, hname, hparty] if holder else None, "note": note, "date": gdate,
                      "el": {e: v for e, v in cands.get(race, {}).items()}})
    boot = {"election": GENERAL, "generated": dt.date.today().isoformat(), "names": STATE_NAMES, "notes": notes, "sources": sources,
            "listed": sorted(listed), "races": races, "money": money(con, fec_ids), "members": member_facts(bios, site_root),
            "runs": runs, "kinds": KIND_LABELS, "elections": ELECTION_NAMES, "party": party_of,
            "map": {k: v["d"] for k, v in state_paths(os.path.join(HERE, "us_states_albers.json")).items()},
            "changelog": read_changelog(os.path.join(HERE, "CHANGELOG.md"))}
    return boot


PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>On The Ballot: Congress · The Civic Archive</title>
<meta name="description" content="Every House and Senate race on the November 3, 2026 ballot: who is running, from each state's official list, the primaries that chose them, and who funds them.">
<meta name="version" content="__VERSION__">
<meta name="theme-color" content="#0C0E12">
<script>try{document.documentElement.dataset.theme=localStorage.getItem("theme")||"light";if(localStorage.getItem("motion")==="off")document.documentElement.classList.add("calm")}catch(e){document.documentElement.dataset.theme="light"}</script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Instrument+Sans:ital,wght@0,400..700;1,400..700&family=Instrument+Serif:ital@0;1&display=swap" rel="stylesheet">
<style>__CSS__</style>
<style>
:root{--pR:var(--rep);--pD:var(--dem);--pL:#B07C00;--pG:#2F8F4E;--pI:#6E62A8;--pO:#646B76;--pW:#7C828C;--gold:#B8860B;
  --night:#0B1030;--night2:#070A1C;--cream:#F4F1E8}
:root[data-theme="dark"]{--pL:#E3B53A;--pG:#5CC98A;--pI:#A99CE0;--pO:#9AA3AF;--pW:#9AA0A8;--gold:#E0B040}
.bwrap{max-width:1180px;margin:0 auto;padding:0 20px}
.crumbs{display:flex;gap:8px;flex-wrap:wrap;align-items:center;font-size:13.5px;color:var(--muted);margin:22px 0 6px}
.crumbs a{color:var(--muted);text-decoration:none;border-bottom:1px solid var(--line-strong)}
.bhero{padding:34px 0 8px}
.bhero .eyebrow{display:inline-flex;gap:8px;align-items:center;font-size:12px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:var(--accent)}
.bhero h1{font-family:var(--serif);font-weight:400;font-size:clamp(40px,6.4vw,78px);line-height:1;margin:10px 0 0;letter-spacing:-.01em}
.bhero h1 em{color:var(--accent)}
.bhero .lede{color:var(--muted);max-width:66ch;font-size:clamp(15px,1.5vw,18px);margin:14px 0 0}
.kchips{display:flex;gap:10px;flex-wrap:wrap;margin:18px 0 0}
.kchip{border:1px solid var(--line);background:var(--surface);border-radius:16px;padding:10px 14px;min-width:120px}
.kchip b{display:block;font-family:var(--serif);font-weight:400;font-size:28px;line-height:1}.kchip span{font-size:12px;color:var(--muted)}
.countdown{display:inline-flex;align-items:center;gap:8px;margin-top:16px;padding:6px 12px;border-radius:999px;background:var(--night);color:#FFF4D6;font-size:13px;font-weight:600}
.countdown i{width:8px;height:8px;border-radius:50%;background:#FFD86B;box-shadow:0 0 10px #FFD86B}
.bsec{padding:30px 0 6px}
.bsec h2{font-family:var(--serif);font-weight:400;font-size:clamp(28px,3.4vw,40px);margin:0;line-height:1.05}
.bsec .sub{color:var(--muted);max-width:70ch;margin:8px 0 0}
.mybar{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin:14px 0 0}
.mybar select{height:44px;border-radius:999px;border:1px solid var(--line-strong);background:var(--surface);color:var(--ink);padding:0 14px;font:600 14.5px var(--sans)}
.mine{display:grid;gap:12px;margin-top:14px}
.chip{display:inline-flex;align-items:center;gap:6px;height:26px;padding:0 10px;border-radius:999px;border:1px solid var(--line);background:var(--surface);font-size:12.5px;font-weight:600;white-space:nowrap}
.chip i{width:9px;height:9px;border-radius:50%;background:var(--pc)}
.chip.inc::after{content:"\2605";color:var(--gold);font-size:11px}
.rgrid{display:grid;gap:10px;grid-template-columns:repeat(auto-fill,minmax(270px,1fr));margin-top:14px}
.rcard{display:block;text-decoration:none;color:inherit;border:1px solid var(--line);background:var(--surface);border-radius:18px;padding:14px 16px;transition:border-color .15s,transform .15s var(--ease)}
.rcard:hover{border-color:var(--line-strong);transform:translateY(-1px)}
.rcard .rt{display:flex;justify-content:space-between;gap:8px;align-items:baseline}.rcard .rt b{font-size:16px}.rcard .rt span{font-size:12px;color:var(--muted)}
.rcard .rchips{display:flex;gap:6px;flex-wrap:wrap;margin-top:10px}
.rcard .soon{font-size:13px;color:var(--muted);margin-top:8px}
.tagsp{display:inline-block;font-size:10.5px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;border-radius:999px;padding:2px 8px;background:rgba(184,134,11,.14);color:var(--gold);margin-left:6px}
.rlist{display:grid;gap:8px;margin-top:12px}
.rrow{display:grid;grid-template-columns:150px 1fr auto;gap:12px;align-items:center;text-decoration:none;color:inherit;border:1px solid var(--line);background:var(--surface);border-radius:14px;padding:10px 14px}
.rrow:hover{border-color:var(--line-strong)}.rrow .rl{font-weight:700;font-size:14px}.rrow .rc{display:flex;gap:6px;flex-wrap:wrap}.rrow .go{color:var(--muted)}
@media (max-width:640px){.rrow{grid-template-columns:1fr auto}.rrow .rc{grid-column:1/-1;order:3}}
.usballot{width:100%;height:auto;display:block;margin-top:10px}
.usballot path{fill:var(--surface);stroke:var(--line-strong);stroke-width:.8;cursor:pointer;transition:fill .15s}
.usballot path.on{fill:var(--accent)}.usballot path.off{fill:url(#bhatch)}.usballot path:hover{filter:brightness(1.12)}
.mkey{display:flex;gap:8px 18px;flex-wrap:wrap;font-size:13px;color:var(--muted);margin:8px 0 0}.mkey span{display:inline-flex;gap:7px;align-items:center}.mkey i{width:13px;height:13px;border-radius:3px;display:inline-block;border:1px solid var(--line-strong)}
.sgrid{display:grid;gap:10px;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));margin-top:14px}
.scard2{display:block;text-decoration:none;color:inherit;border:1px solid var(--line);border-radius:14px;padding:12px 14px;background:var(--surface)}
.scard2 b{display:block}.scard2 span{font-size:12.5px;color:var(--muted)}.scard2 .pill2{display:inline-block;margin-top:6px;font-size:10.5px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;border-radius:999px;padding:2px 8px;background:var(--accent-soft,rgba(15,122,106,.12));color:var(--accent)}
.scard2 .pill2.no{background:none;border:1px dashed var(--line-strong);color:var(--muted)}
.notebox{border:1px solid var(--line);border-left:4px solid var(--gold);background:var(--surface);border-radius:12px;padding:12px 14px;margin-top:12px;font-size:14px}
.notebox .src{display:block;color:var(--muted);font-size:12.5px;margin-top:4px}
.holder{margin:10px 0 0;color:var(--muted);font-size:15px}
.holder b{color:var(--ink)}
/* the arena: the general election, candidates face to face */
.arena{position:relative;border-radius:30px;padding:30px clamp(12px,3vw,34px) 24px;margin:20px 0 6px;overflow:hidden;isolation:isolate;color:var(--cream);
  background:radial-gradient(120% 95% at 50% 0%,#1D2856 0%,var(--night) 52%,var(--night2) 100%);box-shadow:inset 0 0 0 1px rgba(255,214,110,.25),0 30px 60px -40px rgba(0,0,0,.7)}
.arena::before{content:"";position:absolute;inset:0;z-index:-1;background:radial-gradient(34% 70% at 22% -6%,rgba(255,236,170,.22),transparent 70%),radial-gradient(34% 70% at 78% -6%,rgba(255,236,170,.22),transparent 70%)}
.arena::after{content:"";position:absolute;left:6%;right:6%;bottom:40px;height:46%;border-radius:50%;z-index:-1;border:1px solid rgba(255,214,110,.26);background:radial-gradient(closest-side,rgba(255,214,110,.10),transparent)}
.arena .ahead{display:flex;justify-content:space-between;align-items:baseline;gap:10px;flex-wrap:wrap;margin-bottom:16px}
.arena .ahead b{font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:#FFD86B}.arena .ahead span{font-size:13px;color:rgba(244,241,232,.72)}
.acards{display:flex;justify-content:center;align-items:center;gap:clamp(8px,2.4vw,28px);perspective:1100px;flex-wrap:wrap}
.vs{font-family:var(--serif);font-style:italic;font-size:clamp(30px,4.6vw,54px);color:#FFD86B;text-shadow:0 0 24px rgba(255,200,80,.6);line-height:1;flex:none}
.bcard{--pc:var(--pO);position:relative;width:clamp(148px,22vw,220px);aspect-ratio:5/7.2;border-radius:18px;overflow:hidden;display:flex;flex-direction:column;
  background:linear-gradient(165deg,#FFFFFF,#F3EFE4);color:#15171B;box-shadow:0 24px 44px -20px rgba(0,0,0,.85),0 0 0 1px rgba(255,255,255,.3);transition:transform .35s var(--ease)}
.acards[data-n="2"] .bcard:first-child{transform:rotateY(12deg)}.acards[data-n="2"] .bcard:last-child{transform:rotateY(-12deg)}
.bcard .band{background:var(--pc);color:#fff;font:700 10.5px/1 var(--sans);letter-spacing:.12em;text-transform:uppercase;padding:9px 11px;display:flex;justify-content:space-between;gap:6px}
.bcard .band span:last-child{opacity:.85}
.bcard .mono{flex:1;display:grid;place-items:center;min-height:0;background:repeating-linear-gradient(135deg,color-mix(in srgb,var(--pc) 9%,transparent) 0 7px,transparent 7px 14px)}
.bcard .mono span{width:min(40%,78px);aspect-ratio:1;border-radius:50%;display:grid;place-items:center;font-family:var(--serif);font-size:clamp(24px,3vw,34px);color:var(--pc);border:2px solid var(--pc);background:#fff}
.bcard .who{padding:9px 11px 6px}.bcard .who b{display:block;font-family:var(--serif);font-weight:400;font-size:clamp(17px,1.9vw,21px);line-height:1.06}
.bcard .who small{display:block;color:#5C6169;font-size:11.5px;margin-top:2px}
.bcard dl{margin:0;padding:7px 11px 10px;display:grid;grid-template-columns:auto 1fr;gap:2px 8px;font-size:11.5px;border-top:1px solid #E4E5E1}
.bcard dt{color:#5C6169}.bcard dd{margin:0;text-align:right;font-weight:600}
.bcard .flag{position:absolute;top:34px;right:9px;font:700 9.5px/1 var(--sans);letter-spacing:.08em;text-transform:uppercase;padding:4px 7px;border-radius:999px;background:#15171B;color:#FFD86B}
.bcard.wi{border:2px dashed #9AA0A8}
.bcard.solo{width:clamp(170px,26vw,240px)}
.aopen{all:unset;box-sizing:border-box;cursor:pointer;display:flex;align-items:center;gap:8px;margin:20px auto 0;height:44px;padding:0 20px;border-radius:999px;border:1px solid rgba(255,214,110,.6);color:#FFE9A8;font-weight:700;font-size:14.5px;width:max-content}
.aopen:hover,.aopen:focus-visible{background:rgba(255,214,110,.12)}
.aopen svg{width:16px;height:16px;fill:none;stroke:currentColor;stroke-width:2}
.anote{font-size:12.5px;color:rgba(244,241,232,.7);text-align:center;margin:12px auto 0;max-width:70ch}
@media (max-width:640px){      /* on a phone the cards stand in a column, each laid on its side, with "vs" between */
  .acards{flex-direction:column;gap:6px}.acards .bcard,.acards[data-n="2"] .bcard:first-child,.acards[data-n="2"] .bcard:last-child{transform:none}
  .bcard,.bcard.solo{width:min(100%,360px);aspect-ratio:auto;flex-direction:row;flex-wrap:wrap}
  .bcard .band{width:100%}.bcard .mono{flex:0 0 88px;min-height:88px}.bcard .mono span{width:58px;font-size:24px}
  .bcard .who{flex:1;min-width:0;align-self:center}.bcard dl{width:100%}.bcard .flag{top:40px}
  .vs{font-size:30px}}
:root:not(.calm) .arena.deal .bcard{animation:deal .85s var(--ease) both;animation-delay:calc(var(--k) * .14s)}
:root:not(.calm) .arena.deal .vs{animation:vspop .6s .5s cubic-bezier(.3,1.7,.5,1) both}
@keyframes deal{from{opacity:0;transform:translateY(46px) rotateX(38deg) scale(.82)}}
@keyframes vspop{from{opacity:0;transform:scale(.2) rotate(-24deg)}to{opacity:1;transform:none}}
.cmp{margin-top:18px;overflow-x:auto;border-radius:18px;background:rgba(255,255,255,.04);box-shadow:inset 0 0 0 1px rgba(255,214,110,.18)}
.cmp table{border-collapse:collapse;width:100%;min-width:560px;font-size:13.5px}
.cmp th,.cmp td{padding:10px 12px;border-bottom:1px solid rgba(255,255,255,.08);vertical-align:top;text-align:left}
.cmp thead th{font-family:var(--serif);font-weight:400;font-size:19px;color:#fff;border-bottom:2px solid var(--pc)}
.cmp tbody th{color:rgba(244,241,232,.7);font-weight:600;font-size:12.5px;white-space:nowrap;width:1%}
.cmp td small{display:block;color:rgba(244,241,232,.62);font-size:12px;margin-top:3px}
.cmp a{color:#FFE9A8}
.cmp .soon{color:rgba(244,241,232,.55);font-style:italic}
.cmp .grp th{padding-top:16px;color:#FFD86B;font-size:11px;letter-spacing:.14em;text-transform:uppercase;border-bottom-color:rgba(255,214,110,.3)}
/* the field: a primary, every candidate in a lane */
.field{border:1px solid var(--line);border-radius:22px;padding:16px 18px 14px;background:var(--surface);margin:14px 0}
.field .fh{display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap;align-items:baseline}
.field .fh b{font-size:15px}.field .fh span{font-size:12.5px;color:var(--muted)}
.lanes{list-style:none;margin:12px 0 0;padding:0;display:grid;gap:7px}
.lane{--pc:var(--pO);display:grid;grid-template-columns:minmax(130px,1.1fr) 3fr minmax(110px,auto);gap:12px;align-items:center;padding:7px 10px;border-radius:12px;border-left:4px solid var(--pc);background:linear-gradient(90deg,color-mix(in srgb,var(--pc) 7%,transparent),transparent 60%)}
.lane .nm{font-weight:600;font-size:14px}.lane .nm small{display:block;font-weight:400;color:var(--muted);font-size:11.5px}
.lane .bar{height:12px;border-radius:6px;background:var(--line);overflow:hidden}.lane .bar i{display:block;height:100%;width:var(--w,0);background:var(--pc);border-radius:6px}
:root:not(.calm) .field.run .lane .bar i{animation:grow 1s var(--ease) both;animation-delay:calc(var(--k) * .06s)}
@keyframes grow{from{width:0}}
.lane .vv{font-variant-numeric:tabular-nums;font-size:13px;text-align:right;color:var(--muted)}
.lane.won{box-shadow:inset 0 0 0 1px color-mix(in srgb,var(--pc) 45%,transparent)}
.lane.won .nm::after{content:"\2713\00a0advanced";color:var(--accent);font-size:11.5px;font-weight:700;margin-left:6px}
.lane.nobar{grid-template-columns:1fr auto}.lane.nobar .bar{display:none}
@media (max-width:640px){.lane{grid-template-columns:1fr auto}.lane .bar{grid-column:1/-1;order:3}}
.fnote{font-size:12.5px;color:var(--muted);margin:10px 0 0}
.srclist{display:grid;gap:10px;margin-top:12px}
.srcitem{border:1px solid var(--line);border-radius:14px;padding:12px 14px;background:var(--surface);font-size:14px}
.srcitem small{display:block;color:var(--muted);margin-top:4px;word-break:break-all}
.method li{margin:6px 0}
.bfoot{border-top:1px solid var(--hair,var(--line));margin-top:40px;padding:20px 0 90px;color:var(--muted);font-size:13px}
.bfoot a{color:inherit}
.backlink{display:inline-flex;align-items:center;gap:8px;text-decoration:none;color:var(--muted);font-weight:600;font-size:14px}
</style>
</head>
<body>
<div style="background:#7c2d12;color:#fff;padding:.5rem 1rem;font:600 13px/1.4 system-ui,sans-serif;text-align:center;letter-spacing:.02em">
  WORK IN PROGRESS &mdash; this is a draft for feedback, not the real site.
  <a href="https://thecivicarchive.github.io/" style="color:#fed7aa;text-decoration:underline">Go to the live site</a>
</div>
<header class="top">
  <div class="wrap">
    <a class="doorlink" href="../" title="On The Ballot: every level" aria-label="Back to the On The Ballot door"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 12h16v8H4z"/><path d="M8 12V5h8v7"/><path d="M10 8.6l1.5 1.5 2.8-2.9"/></svg><span>On The Ballot</span></a>
    <a class="brand" href="#" aria-label="On The Ballot: Congress, home"><svg class="mark" viewBox="0 0 28 28" aria-hidden="true"><path d="M14 3v2.5"/><path d="M6.5 13.5a7.5 7.5 0 0 1 15 0"/><path d="M4 13.5h20"/><path d="M6.5 16.5v6M11.5 16.5v6M16.5 16.5v6M21.5 16.5v6"/><path d="M3 24h22"/></svg><span class="wm"><b>T</b>he <b>C</b>ivic <b>A</b>rchive</span></a>
    <nav class="nav" aria-label="Sections"><a href="#">Congress</a><a href="#senate">Senate races</a><a href="#states">States</a><a href="#sources">Sources</a></nav>
    <div class="tools">
      <button class="mtog" id="motion" aria-pressed="true" title="Page motion: on or off"><span class="sw" aria-hidden="true"><i></i></span><span class="lab">Motion</span></button>
      <button class="iconbtn" id="theme" aria-label="Switch between light and dark" title="Light / dark">
        <svg class="moon" viewBox="0 0 24 24" aria-hidden="true"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>
        <svg class="sun" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>
      </button>
    </div>
  </div>
</header>
<main id="app" class="bwrap" tabindex="-1"></main>
<footer class="bwrap bfoot">
  <p>On The Ballot, from The Civic Archive v__VERSION__. Who is running comes only from each state's official candidate list, loaded one state at a time; campaign money from the Federal Election Commission's bulk files. No scores, no ratings of any person, no ads, no donors. Built __GENERATED__.</p>
  <p><a href="../">On The Ballot: every level</a> &middot; <a href="../../">The Civic Archive front door</a> &middot; <a href="../../us/">The record of the 119th Congress</a></p>
</footer>
<div class="cl" id="cl" hidden>
  <button class="cl-tab" id="cltab" aria-expanded="false" aria-controls="clpanel"><span class="cl-dot" aria-hidden="true"></span><span class="cl-v" id="clv">v1</span><span class="cl-w">What&rsquo;s new</span></button>
  <div class="cl-panel" id="clpanel" hidden><div class="cl-head"><b>What&rsquo;s changed</b><button class="cl-x" id="clx" aria-label="Close">&times;</button></div><div class="cl-body" id="clbody"></div></div>
</div>
<script>
const BOOT = __BOOT__;
const $ = (s, el) => (el || document).querySelector(s), $$ = (s, el) => [...(el || document).querySelectorAll(s)];
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
const store = {get: k => { try { return localStorage.getItem(k); } catch (e) { return null; } }, set: (k, v) => { try { localStorage.setItem(k, v); } catch (e) {} }};
__MONEYFMT__
__CHANGELOG__
/* ---------- the two switches, with the same saved choices as the rest of the site ---------- */
const calm = () => document.documentElement.classList.contains("calm");
const showMotion = () => $("#motion").setAttribute("aria-pressed", calm() ? "false" : "true");
showMotion();
$("#motion").addEventListener("click", () => { const off = !calm(); document.documentElement.classList.toggle("calm", off); store.set("motion", off ? "off" : "on"); showMotion(); });
$("#theme").addEventListener("click", () => { const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark"; document.documentElement.dataset.theme = next; store.set("theme", next); });

/* ---------- words ---------- */
const NAMES = BOOT.names, R = Object.fromEntries(BOOT.races.map(r => [r.id, r]));
const byState = {}; BOOT.races.forEach(r => (byState[r.st] = byState[r.st] || []).push(r));
const listed = new Set(BOOT.listed);
const ORD = n => n + (["th", "st", "nd", "rd"][((n % 100) - 20) % 10] || ["th", "st", "nd", "rd"][n % 100] || "th");
const raceName = r => r.o === "S" ? `U.S. Senate, ${NAMES[r.st]}${r.sp ? " (special election)" : ""}` : (+r.d === 0 ? `${NAMES[r.st]}, at large` : `${NAMES[r.st]}'s ${ORD(+r.d)} District`);
const raceShort = r => r.o === "S" ? `Senate${r.sp ? ", special" : ""}` : (+r.d === 0 ? "At large" : `${ORD(+r.d)} District`);
const PARTY = {R: "Republican", D: "Democratic", L: "Libertarian", G: "Green", W: "Write-in"};
const bare = p => String(p || "").replace(/ Party of [A-Z][a-z]+( [A-Z][a-z]+)?$| Party$/, "");
const shortParty = c => PARTY[c.pc] || (c.pc === "I" ? (/preference/i.test(c.p) ? "No party preference" : /affiliation/i.test(c.p) ? "No party affiliation" : bare(c.p) || "Independent") : bare(c.p) || "Other");
const pcVar = c => `var(--p${c.pc || "O"})`;
const HOLDPARTY = {Republican: "R", Democrat: "D", Democratic: "D", Independent: "I"};
const fmtDate = iso => { const [y, m, d] = String(iso || "").split("-").map(Number); return y ? new Date(y, m - 1, d).toLocaleDateString("en-US", {month: "long", day: "numeric", year: "numeric"}) : ""; };
const surname = n => String(n).replace(/\s+(Jr\.?|Sr\.?|II|III|IV)$/i, "").trim().split(/\s+/).pop().toLowerCase();
const inOrder = list => [...list].sort((a, b) => (a.o ?? 1e9) - (b.o ?? 1e9) || surname(a.n).localeCompare(surname(b.n)));
const initials = n => { const w = String(n).replace(/["“”].*?["“”]/g, "").replace(/\b(Jr|Sr|II|III|IV)\.?$/i, "").trim().split(/\s+/); return ((w[0] || "")[0] || "") + ((w.length > 1 ? w[w.length - 1] : "")[0] || ""); };
const general = r => r.el && r.el.general ? inOrder(r.el.general) : [];
const days = () => { const [y, m, d] = BOOT.election.split("-").map(Number), n = new Date(); return Math.round((new Date(y, m - 1, d) - new Date(n.getFullYear(), n.getMonth(), n.getDate())) / 864e5); };
const dayWords = () => { const n = days(); return n > 1 ? `Election Day in ${n} days` : n === 1 ? "Election Day is tomorrow" : n === 0 ? "Election Day is today" : `Election Day was ${fmtDate(BOOT.election)}`; };

/* ---------- small pieces ---------- */
const chip = c => `<span class="chip${c.inc ? " inc" : ""}" style="--pc:${pcVar(c)}" title="${esc(shortParty(c))}${c.inc ? ", serves in this chamber today" : ""}"><i></i>${esc(c.n)}</span>`;
function raceCard(r){
  const g = general(r);
  return `<a class="rcard" href="#race=${esc(r.id)}"><div class="rt"><b>${esc(r.o === "S" ? NAMES[r.st] : raceShort(r))}${r.sp ? '<span class="tagsp">Special</span>' : ""}</b><span>${esc(r.o === "S" ? "U.S. Senate" : NAMES[r.st])}</span></div>
    ${g.length ? `<div class="rchips">${g.map(chip).join("")}</div>` : `<div class="soon">${listed.has(r.st) ? "No candidate on the list" : "Official list coming"}${r.h ? ` &middot; held today by ${esc(r.h[1])}` : ""}</div>`}</a>`;
}
function raceRow(r){
  const g = general(r);
  return `<a class="rrow" href="#race=${esc(r.id)}"><span class="rl">${esc(raceShort(r))}${r.sp ? '<span class="tagsp">Special</span>' : ""}</span><span class="rc">${g.length ? g.map(chip).join("") : `<span class="muted">${listed.has(r.st) ? "No candidate on the list" : "Official list coming"}${r.h ? ` &middot; held today by ${esc(r.h[1])}` : ""}</span>`}</span><span class="go" aria-hidden="true">&rsaquo;</span></a>`;
}
function stateNote(st){
  const n = BOOT.notes[st]; if (!n) return "";
  return `<div class="notebox">${esc(n.note)}<span class="src">Source: <a href="${esc(n.su)}" target="_blank" rel="noopener">${esc(n.st)}</a>. A secondary source; the state's own election office is the authority on its districts.</span></div>`;
}

/* ---------- a candidate's card, and the arena ---------- */
function money(c){ return c.fec ? BOOT.money[c.fec] : null; }
function officeNow(c){
  const m = c.bio && BOOT.members[c.bio]; if (!m) return null;
  return `${m.ch === "Senate" ? "U.S. Senator" : "U.S. Representative"}${m.since ? ` since ${m.since}` : ""}`;
}
function card(c, r, k, solo){
  const M = money(c), off = officeNow(c);
  const flag = c.out === "unopposed" ? "Unopposed" : c.wi ? "Write-in" : c.inc ? "Incumbent" : "";
  const rows = [["Office now", off ? esc(off.replace("U.S. ", "")) : "None in Congress"], ["Raised, 2026", M && M.r != null ? usdShort(M.r) : (c.fec ? "Not yet reported" : "No FEC filing")]];
  if (M && M.coh != null) rows.push(["Cash on hand", usdShort(M.coh)]);
  return `<article class="bcard${c.wi ? " wi" : ""}${solo ? " solo" : ""}" style="--pc:${pcVar(c)};--k:${k}" aria-label="${esc(c.n)}, ${esc(shortParty(c))}">
    <div class="band"><span>${esc(shortParty(c))}</span><span>${esc(r.o === "S" ? "Senate" : r.st + "-" + (+r.d || "AL"))}</span></div>
    ${flag ? `<span class="flag">${esc(flag)}</span>` : ""}
    <div class="mono"><span aria-hidden="true">${esc(initials(c.n).toUpperCase())}</span></div>
    <div class="who"><b>${esc(c.n)}</b><small>${esc(c.p || "")}</small></div>
    <dl>${rows.map(([a, b]) => `<dt>${a}</dt><dd>${b}</dd>`).join("")}</dl></article>`;
}
function arena(r){
  const g = general(r); if (!g.length) return "";
  const parts = []; g.forEach((c, i) => { if (i) parts.push(`<span class="vs" aria-hidden="true">vs</span>`); parts.push(card(c, r, i, g.length === 1)); });
  const lone = g.length === 1;
  return `<section class="arena deal" id="arena" aria-label="The general election, ${esc(fmtDate(r.date))}">
    <div class="ahead"><b>General election &middot; ${esc(fmtDate(r.date))}</b><span>${lone ? "One name for this office" : `${g.length} candidates, in the order the state's list gives, or by surname`}</span></div>
    <div class="acards" data-n="${g.length}">${parts.join("")}</div>
    <button class="aopen" id="aopen" type="button" aria-expanded="false" aria-controls="cmp"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 12h16M12 4l8 8-8 8"/></svg><span>Step into the arena: compare them side by side</span></button>
    <div class="cmp" id="cmp" hidden></div>
    <p class="anote">Every card is the same size. The cards show what the record holds: the office a candidate holds in Congress today, and the money their campaign reported to the FEC. No score or grade of any person.</p>
  </section>`;
}
function compare(r){
  const g = general(r), n = g.length;
  const cell = (fn) => g.map(c => `<td>${fn(c)}</td>`).join("");
  const M = c => money(c) || {}, mem = c => (c.bio && BOOT.members[c.bio]) || null;
  const soon = t => `<span class="soon">${t}</span>`;
  const row = (label, fn) => `<tr><th scope="row">${label}</th>${cell(fn)}</tr>`;
  const grp = label => `<tr class="grp"><th colspan="${n + 1}">${label}</th></tr>`;
  const orgs = c => { const o = M(c).orgs || []; return o.length ? o.map(x => `${esc(x[0])} <small>${esc(BOOT.kinds[x[1]] || "")}: ${usd(x[2])}</small>`).join("") : (c.fec ? "None itemized yet" : "&ndash;"); };
  const side = (c, s) => { const m = M(c), t = m[s] || 0, w = m[s === "for" ? "forw" : "agw"] || []; return t ? `${usd(t)}${w.map(x => `<small>${esc(x[0])}: ${usd(x[1])}</small>`).join("")}` : "None reported"; };
  const html = `<table><thead><tr><th></th>${g.map(c => `<th scope="col" style="--pc:${pcVar(c)}">${esc(c.n)}</th>`).join("")}</tr></thead><tbody>
    ${grp("On the ballot")}
    ${row("Party, as printed", c => esc(c.p || "") + (c.wi ? "<small>Write-in: the name is not printed on the ballot</small>" : ""))}
    ${row("Notes from the list", c => c.note ? esc(c.note) : "&ndash;")}
    ${grp("In office")}
    ${row("In Congress today", c => { const m = mem(c); return m ? `${m.ch === "Senate" ? "U.S. Senator" : "U.S. Representative"}${m.since ? `, since ${m.since}` : ""}${m.terms ? `<small>${m.terms} term${m.terms === 1 ? "" : "s"}</small>` : ""}` : "No"; })}
    ${row("Votes this Congress", c => { const m = mem(c); return m && m.elig ? `Voted on ${Number(m.cast).toLocaleString()} of ${Number(m.elig).toLocaleString()}${m.split ? `<small>Voted against most of their party on ${m.breaks || 0} of the ${m.split} votes that split the parties</small>` : ""}` : "&ndash;"; })}
    ${row("Bills this Congress", c => { const m = mem(c); return m && m.spon != null ? `Sponsored ${m.spon}${m.laws ? `, ${m.laws} became law` : ""}` : "&ndash;"; })}
    ${row("Their full record", c => c.bio && mem(c) ? `<a href="../../us/#member=${esc(c.bio)}">Open their page on the record side</a>` : `&ndash;<small>No record in Congress. Records of state and local offices come later.</small>`)}
    ${grp("Campaign money, 2026 (FEC)")}
    ${row("Raised", c => M(c).r != null ? `${usd(M(c).r)}${M(c).end ? `<small>Through ${esc(fmtDate(M(c).end))}</small>` : ""}` : (c.fec ? "Not yet reported" : "No FEC filing"))}
    ${row("From people", c => M(c).ind != null ? `${usd(M(c).ind)}<small>A total; people who give are never named here</small>` : "&ndash;")}
    ${row("From organizations", c => M(c).cmte != null ? `${usd(M(c).cmte)}${M(c).passed ? `<small>${usd(M(c).passed)} of it passed along from people who earmarked it</small>` : ""}` : "&ndash;")}
    ${row("Largest organizations", orgs)}
    ${row("From the party", c => M(c).pty != null ? usd(M(c).pty) : "&ndash;")}
    ${row("From the candidate", c => M(c).self != null ? usd(M(c).self) + "<small>Their own gifts and loans</small>" : "&ndash;")}
    ${row("Cash on hand", c => M(c).coh != null ? usd(M(c).coh) : "&ndash;")}
    ${row("FEC filings", c => c.fec ? `<a href="https://www.fec.gov/data/candidate/${esc(c.fec)}/" target="_blank" rel="noopener">${esc(c.fec)}</a>` : "No registration found")}
    ${grp("Outside spending, 2026 (never received by the campaign)")}
    ${row("Spent to support", c => side(c, "for"))}
    ${row("Spent to oppose", c => side(c, "against"))}
    ${grp("Still to come")}
    ${row("Ads", c => soon("TV, radio, digital and mail spending for and against, and links to the public ad libraries"))}
    ${row("Polls", c => soon("From pollsters in AAPOR's Transparency Initiative"))}
    ${row("In their own words", c => soon("A link to their campaign's own issues page"))}
  </tbody></table>`;
  return html;
}

/* ---------- a primary, and its field ---------- */
function field(r, key){
  const list = r.el[key] || []; if (!list.length) return "";
  const votes = list.some(c => c.v != null), max = Math.max(1, ...list.map(c => c.pct || 0));
  const rows = [...list].sort((a, b) => votes ? (b.v || 0) - (a.v || 0) : surname(a.n).localeCompare(surname(b.n)));
  const date = list[0].date, topTwo = key === "primary";
  const src = BOOT.sources[list[0].src];
  return `<section class="field run"><div class="fh"><b>${esc(BOOT.elections[key] || key)} &middot; ${esc(fmtDate(date))}</b><span>${list.length} candidates${topTwo ? ", every party on one ballot; the two with the most votes advance" : ""}</span></div>
    <ol class="lanes">${rows.map((c, i) => `<li class="lane${c.out === "advanced" ? " won" : ""}${votes ? "" : " nobar"}" style="--pc:${pcVar(c)};--k:${i}"><span class="nm">${esc(c.n)}<small>${esc(c.p || "")}${c.inc ? " &middot; serves in this chamber today" : ""}</small></span>
      <span class="bar"><i style="--w:${votes ? (100 * (c.pct || 0) / max).toFixed(1) : 0}%"></i></span>
      <span class="vv">${votes ? `${Number(c.v).toLocaleString()} &middot; ${(c.pct || 0).toFixed(1)}%` : (c.out === "advanced" ? "Won" : "Lost")}</span></li>`).join("")}</ol>
    <p class="fnote">${votes ? `Votes as certified in the official results (${esc(src ? src.agency : "the state")}).` : `The official vote counts for this primary are not loaded yet; who won comes from the candidate list of the ${esc(src ? src.agency : "state")}.`}</p></section>`;
}

/* ---------- pages ---------- */
function home(anchor){
  const H = BOOT.races.filter(r => r.o === "H").length, S = BOOT.races.filter(r => r.o === "S");
  const cands = BOOT.races.reduce((n, r) => n + general(r).length, 0);
  const mine = JSON.parse(store.get("ballot:mine") || "null") || {st: store.get("state") || "", d: ""};
  const opts = Object.keys(NAMES).sort((a, b) => NAMES[a].localeCompare(NAMES[b])).map(s => `<option value="${s}"${s === mine.st ? " selected" : ""}>${esc(NAMES[s])}</option>`).join("");
  $("#app").innerHTML = `<section class="bhero"><span class="eyebrow">On The Ballot &middot; U.S. Congress</span>
    <h1>Who&rsquo;s running for <em>Congress</em></h1>
    <p class="lede">Every House seat and 35 Senate seats are on the November 3, 2026 ballot. Who is running comes from each state&rsquo;s own official list of candidates, added one state at a time; the primaries that chose them come from the official results.</p>
    <span class="countdown"><i></i>${esc(dayWords())}</span>
    <div class="kchips"><div class="kchip"><b>${H}</b><span>House races</span></div><div class="kchip"><b>${S.length}</b><span>Senate races</span></div><div class="kchip"><b>${listed.size} of 50</b><span>states' lists loaded</span></div><div class="kchip"><b>${cands}</b><span>candidates listed so far</span></div></div></section>
  <section class="bsec" id="yours"><h2>Your ballot</h2><p class="sub">Pick your state and your congressional district. The choice stays on this device.</p>
    <div class="mybar"><select id="mst" aria-label="Your state"><option value="">Your state</option>${opts}</select><select id="mdi" aria-label="Your district"></select></div>
    <div class="mine" id="minelist"></div></section>
  <section class="bsec" id="senate"><h2>The Senate races</h2><p class="sub">Thirty-three seats whose terms end in January, and ${S.filter(r => r.sp).length} special elections for the rest of a term.</p>
    <div class="rgrid">${S.map(raceCard).join("")}</div></section>
  <section class="bsec" id="states"><h2>Every state</h2><p class="sub">Filled states have their official candidate list loaded. The rest are coming, largest first.</p>
    <svg class="usballot" id="usballot" viewBox="0 0 975 610" role="img" aria-label="Map of the states: filled where the official candidate list is loaded"><defs><pattern id="bhatch" patternUnits="userSpaceOnUse" width="7" height="7" patternTransform="rotate(45)"><rect width="7" height="7" fill="var(--surface)"/><rect width="2.5" height="7" fill="var(--accent)" opacity=".35"/></pattern></defs>
      ${Object.entries(BOOT.map).map(([s, d]) => NAMES[s] ? `<path class="${listed.has(s) ? "on" : "off"}" d="${d}" data-st="${s}"><title>${esc(NAMES[s])}: ${listed.has(s) ? "list loaded" : "list coming"}</title></path>` : "").join("")}</svg>
    <div class="mkey"><span><i style="background:var(--accent)"></i>Official list loaded</span><span><i style="background:repeating-linear-gradient(45deg,var(--accent) 0 2px,var(--surface) 2px 7px)"></i>Coming</span></div>
    <div class="sgrid">${Object.keys(NAMES).sort((a, b) => NAMES[a].localeCompare(NAMES[b])).map(s => `<a class="scard2" href="#state=${s}"><b>${esc(NAMES[s])}</b><span>${(byState[s] || []).filter(r => r.o === "H").length} House ${(byState[s] || []).filter(r => r.o === "H").length === 1 ? "seat" : "seats"}${(byState[s] || []).some(r => r.o === "S") ? ", a Senate race" : ""}${BOOT.notes[s] && BOOT.notes[s].changed ? ", new district lines" : ""}</span><br><span class="pill2${listed.has(s) ? "" : " no"}">${listed.has(s) ? "List loaded" : "Coming"}</span></a>`).join("")}</div></section>
  ${sourcesHTML()}`;
  const mst = $("#mst"), mdi = $("#mdi");
  const fill = () => { const st = mst.value, hs = (byState[st] || []).filter(r => r.o === "H");
    mdi.innerHTML = hs.length ? hs.map(r => `<option value="${esc(r.d)}"${r.d === mine.d ? " selected" : ""}>${esc(raceShort(r))}</option>`).join("") : `<option value="">District</option>`;
    mdi.hidden = !st || hs.length <= 1; showMine(); };
  const showMine = () => { const st = mst.value; if (!st) { $("#minelist").innerHTML = ""; return; }
    const d = (byState[st] || []).filter(r => r.o === "H").length === 1 ? "00" : mdi.value;
    store.set("ballot:mine", JSON.stringify({st, d}));
    const mineR = (byState[st] || []).filter(r => r.o === "S" || r.d === d);
    $("#minelist").innerHTML = `${stateNote(st)}<div class="rgrid">${mineR.map(raceCard).join("")}</div>`; };
  mst.addEventListener("change", () => { mine.d = ""; fill(); }); mdi.addEventListener("change", showMine); fill();
  $("#usballot").addEventListener("click", e => { const p = e.target.closest("path[data-st]"); if (p) location.hash = "state=" + p.dataset.st; });
  if (anchor && $("#" + anchor)) $("#" + anchor).scrollIntoView();
}
function statePage(st){
  const rs = byState[st] || []; if (!rs.length) { home(); return; }
  const src = Object.values(BOOT.sources).filter(s => s.state === st);
  $("#app").innerHTML = `<nav class="crumbs"><a href="#">Congress</a><span>&rsaquo;</span><span>${esc(NAMES[st])}</span></nav>
  <section class="bhero"><span class="eyebrow">On The Ballot &middot; ${esc(NAMES[st])}</span><h1>${esc(NAMES[st])}</h1>
    <p class="lede">${rs.filter(r => r.o === "H").length} House ${rs.filter(r => r.o === "H").length === 1 ? "seat" : "seats"}${rs.some(r => r.o === "S") ? " and a Senate seat" : ""} on the November 3 ballot. ${listed.has(st) ? "Candidates from the state's official list." : "The state's official candidate list is not loaded yet; each race says who holds the seat today."}</p>
    ${stateNote(st)}</section>
  ${rs.some(r => r.o === "S") ? `<section class="bsec"><h2>Senate</h2><div class="rlist">${rs.filter(r => r.o === "S").map(raceRow).join("")}</div></section>` : ""}
  <section class="bsec"><h2>House</h2><div class="rlist">${rs.filter(r => r.o === "H").map(raceRow).join("")}</div></section>
  ${src.length ? `<section class="bsec"><h2>Where this comes from</h2><div class="srclist">${src.map(srcItem).join("")}</div></section>` : ""}`;
}
function holderLine(r){
  if (!r.h) return `<p class="holder">The seat is vacant today.</p>`;
  const [bio, name, party] = r.h, g = general(r), runs = BOOT.runs[bio] || [];
  let tail = "";
  if (listed.has(r.st)) {
    if (g.some(c => c.bio === bio)) tail = ", who is on the ballot again";
    else { const lost = runs.find(x => x[0] === r.id && x[2] === "lost"), elsewhere = runs.find(x => x[0] !== r.id && x[1] === "general");
      const pn = lost ? (BOOT.elections[lost[1]] || "primary") : "", when = lost ? ((r.el[lost[1]] || [])[0] || {}).date : "";
      tail = lost ? `, who lost the ${esc(pn.startsWith("Top") ? pn.toLowerCase() : pn)}${when ? " on " + esc(fmtDate(when).replace(/, \d{4}$/, "")) : ""}`
        : elsewhere ? `, who is on the ballot for ${esc(raceName(R[elsewhere[0]]))} instead` : ", who is not on the November ballot for this seat"; }
  }
  const moved = r.o === "H" && BOOT.notes[r.st] && BOOT.notes[r.st].changed ? " The district's lines changed for 2026, so the seat numbered here may cover different ground." : "";
  return `<p class="holder">Held today by <b><a href="../../us/#member=${esc(bio)}">${esc(name)}</a></b> (${esc(party)})${tail}.${moved}</p>`;
}
function racePage(id){
  const r = R[id]; if (!r) { home(); return; }
  const prim = Object.keys(r.el || {}).filter(k => k !== "general").sort();
  const srcs = [...new Set(Object.values(r.el || {}).flat().map(c => c.src))].map(s => BOOT.sources[s]).filter(Boolean);
  $("#app").innerHTML = `<nav class="crumbs"><a href="#">Congress</a><span>&rsaquo;</span><a href="#state=${r.st}">${esc(NAMES[r.st])}</a><span>&rsaquo;</span><span>${esc(raceShort(r))}</span></nav>
  <section class="bhero"><span class="eyebrow">${r.o === "S" ? "U.S. Senate" : "U.S. House"} &middot; ${esc(fmtDate(r.date))}</span><h1>${esc(raceName(r))}</h1>
    ${holderLine(r)}${r.note ? `<p class="holder">${esc(r.note)}</p>` : ""}</section>
  ${general(r).length ? arena(r) : `<div class="notebox">${listed.has(r.st) ? "No candidate for this race is on the state's list." : `The official candidate list for ${esc(NAMES[r.st])} is not loaded yet. We add each state from its own election office, largest first.`}</div>`}
  ${prim.length ? `<section class="bsec"><h2>How they got here</h2><p class="sub">${prim.length === 1 && prim[0] === "primary" ? "California's primary is top-two: every candidate, of every party preference, on one ballot." : "Each party chose its nominee in its own primary. A party with a single candidate held none."}</p>${prim.map(k => field(r, k)).join("")}</section>` : ""}
  ${srcs.length ? `<section class="bsec"><h2>Where this comes from</h2><div class="srclist">${srcs.map(srcItem).join("")}</div></section>` : ""}`;
  const b = $("#aopen");
  if (b) b.addEventListener("click", () => { const c = $("#cmp"); if (c.hidden) { c.innerHTML = compare(r); c.hidden = false; b.setAttribute("aria-expanded", "true"); b.querySelector("span").textContent = "Close the comparison"; c.scrollIntoView({block: "nearest", behavior: calm() ? "auto" : "smooth"}); }
    else { c.hidden = true; b.setAttribute("aria-expanded", "false"); b.querySelector("span").textContent = "Step into the arena: compare them side by side"; } });
}
const srcItem = s => `<div class="srcitem"><b>${esc(s.agency)}</b>: ${esc(s.title)}<small><span class="tag fact">Fact</span> <a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.url)}</a> &middot; fetched ${esc(s.fetched)} &middot; ${Number(s.rows || 0).toLocaleString()} rows &middot; SHA-256 ${esc((s.sha || "").slice(0, 16))}&hellip;${s.note ? " &middot; " + esc(s.note) : ""}</small></div>`;
function sourcesHTML(){
  return `<section class="bsec" id="sources"><h2>Sources and methods</h2>
    <ul class="method sub">
      <li><b>Who is running</b> comes only from each state's own election office: its certified list of candidates, or its official results where the list is the result of a primary. A state appears once its list is loaded; until then its races say who holds the seat today and nothing more.</li>
      <li><b>Order.</b> Candidates appear in the order the state's list gives them, or by surname where the list gives no ballot order. Never by money, polls or party.</li>
      <li><b>Parties</b> are printed exactly as the official list prints them. Colours are for telling the cards apart only.</li>
      <li><b>Money</b> is the 2026 cycle from the Federal Election Commission's bulk files: what each campaign reported, organizations named, people only as a total. A candidate's own fundraising committees and joint fundraising committees are moved in, not donors. Outside spending is kept apart, because the campaign never received it.</li>
      <li><b>Nobody is scored or graded.</b> The cards show the record; the judging is yours.</li>
      <li><b>Still to come:</b> vote counts for primaries where only the winner is loaded, ads (spending by kind, for and against, and links to the public ad libraries), polls from pollsters in AAPOR's Transparency Initiative, each campaign's own issues page, and then state and local races.</li>
    </ul>
    <div class="srclist">${Object.values(BOOT.sources).sort((a, b) => NAMES[a.state].localeCompare(NAMES[b.state])).map(srcItem).join("")}
      <div class="srcitem"><b>Federal Election Commission</b>: bulk data files for the 2025&ndash;2026 cycle (candidates, committees, campaign totals, committee payments)<small><span class="tag fact">Fact</span> <a href="https://www.fec.gov/data/browse-data/?tab=bulk-data" target="_blank" rel="noopener">fec.gov/data/browse-data/?tab=bulk-data</a></small></div>
      <div class="srcitem"><b>National Conference of State Legislatures</b>: the notes on new district lines<small><span class="tag analysis">Secondary</span> <a href="https://www.ncsl.org/redistricting-and-census/changing-the-maps-tracking-mid-decade-redistricting" target="_blank" rel="noopener">Changing the Maps: Tracking Mid-Decade Redistricting</a>, updated September 11, 2026</small></div>
    </div></section>`;
}

/* ---------- the address decides the page ---------- */
function route(){
  const h = decodeURIComponent(location.hash.slice(1));
  if (h.startsWith("race=")) racePage(h.slice(5));
  else if (h.startsWith("state=")) statePage(h.slice(6).toUpperCase());
  else { home(h); if (!h) scrollTo(0, 0); return; }
  scrollTo(0, 0);
}
addEventListener("hashchange", route);
route();
</script>
</body>
</html>
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=DB)
    ap.add_argument("--record", default=os.path.join(HERE, "congress_119.sqlite"))
    ap.add_argument("--out", default=os.path.join(HERE, "site", "dev", "ballot", "us", "index.html"))
    args = ap.parse_args()
    if not os.path.exists(args.db):
        sys.exit("No ballot database yet. Run: python run_ballot.py")
    site_root = os.path.join(HERE, "site", "dev")
    boot = build(args.db, args.record, site_root)
    version = (boot["changelog"][0].get("version") if boot["changelog"] else "") or ""
    page = PAGE.replace("__CSS__", borrow("CSS")).replace("__MONEYFMT__", borrow("MONEYFMT")).replace("__CHANGELOG__", borrow("CHANGELOG"))
    page = page.replace("__VERSION__", version).replace("__GENERATED__", dt.datetime.now().strftime("%B %d, %Y"))
    page = page.replace("__BOOT__", json.dumps(boot, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/"))
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(page)
    loaded = sum(1 for r in boot["races"] if r["el"].get("general"))
    print(f"Version {version}")
    print(f"Wrote {args.out}: {len(boot['races'])} races ({loaded} with the official list loaded), "
          f"{len(boot['listed'])} states listed, {len(boot['money'])} campaigns' money, {len(boot['members'])} members' records, "
          f"{len(page.encode('utf-8')) / 1e3:,.0f} KB")


if __name__ == "__main__":
    main()
