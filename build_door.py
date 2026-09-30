#!/usr/bin/env python3
"""
build_door.py - the front door of The Civic Archive: one small page that welcomes everyone and leads to each
level of government. The federal side lives under us/, each state under its own two-letter folder (mn/).

    python build_door.py --out site/dev/index.html

The page is a ring of cards turning in 3D, one card per level of government (so a county or city level can be
added later without redesign). Choosing a card turns the page like a book, three seconds, and opens that space.
The State card opens a map of the country: finished states are lit, states being built say what is loaded so far.
With Motion off (the same switch and the same saved choice as the rest of the site) nothing spins and the
page-turn is skipped.

At the top middle sits the On The Ballot switch (John, 2026-09-29). A click pulls the page into a wormhole and out
into the On The Ballot space (ballot/); resting the pointer on it for three seconds first sets off fireworks over a
blurred night sky that spell ON THE BALLOT, CLICK TO SEE, and a click then goes through (without one the sky
clears and the reader stays). With Motion off there are no fireworks and the wormhole is a plain fade.

    python build_door.py --out site/dev/ballot/index.html --ballot

writes the On The Ballot door: the same ring, one card per level (Congress first; the states and the local level
are marked as coming), with the switch lit; a click on it goes back through the wormhole.

Everything the page shows is counted at build time from the databases on this computer: congress_119.sqlite for
the federal card, state_<code>.sqlite and state_<code>_districts.json for each state in states/places.py, and
ballot_2026.sqlite for the On The Ballot door.
"""

import argparse
import json
import os
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from build_site_dev import read_changelog, state_paths     # noqa: E402
from states.places import PLACES                           # noqa: E402

# the jurisdictions John has named that the country map file does not draw
OFF_MAP = [("DC", "Washington, D.C."), ("PR", "Puerto Rico"), ("GU", "Guam")]


def federal_facts(db):
    if not os.path.exists(db):
        return {}
    con = sqlite3.connect(db)
    one = lambda q: con.execute(q).fetchone()[0]
    has = lambda t: con.execute("SELECT 1 FROM sqlite_master WHERE name = ?", (t,)).fetchone() is not None
    return {"bills": one("SELECT COUNT(*) FROM bills"), "laws": one("SELECT COUNT(*) FROM bills WHERE law_number <> ''"),
            "votes": one("SELECT COUNT(DISTINCT vote_id) FROM member_votes") if has("member_votes") else 0,
            "members": one("SELECT COUNT(*) FROM legislators WHERE is_current = 1") if has("legislators") else 0}


def state_facts(code, site_root):
    """What is loaded for a state, and whether its pages exist yet."""
    P = PLACES[code]
    db, shapes = os.path.join(HERE, f"state_{code}.sqlite"), os.path.join(HERE, f"state_{code}_districts.json")
    out = {"code": P["code"], "name": P["name"], "legislature": P["legislature"], "live": os.path.exists(os.path.join(site_root, code, "index.html")),
           "loaded": [], "coming": []}
    if os.path.exists(db):
        con = sqlite3.connect(db)
        has = lambda t: con.execute("SELECT 1 FROM sqlite_master WHERE name = ?", (t,)).fetchone() is not None
        if has("legislators"):
            n = con.execute("SELECT COUNT(*) FROM legislators WHERE is_current = 1").fetchone()[0]
            out["loaded"].append(f"{n} legislators")
        if has("bills"):
            out["loaded"].append(f"{con.execute('SELECT COUNT(*) FROM bills').fetchone()[0]:,} bills")
        if has("member_votes"):
            out["loaded"].append(f"{con.execute('SELECT COUNT(DISTINCT vote_id) FROM member_votes').fetchone()[0]:,} recorded votes")
        if has("state_gifts") and con.execute("SELECT COUNT(*) FROM state_gifts").fetchone()[0]:
            out["loaded"].append("campaign money")
        if not (has("state_gifts") and con.execute("SELECT COUNT(*) FROM state_gifts").fetchone()[0]):
            out["coming"].append("campaign money")               # each state's own agency, added one state at a time
        if not (has("bills") and has("member_votes")):          # a state can open before its bills arrive; the card says so
            out["coming"].append("bills and recorded votes")
    if os.path.exists(shapes):
        d = json.load(open(shapes, encoding="utf-8"))
        out["loaded"].insert(1 if out["loaded"] else 0, f"{len(d.get('upper', {})) + len(d.get('lower', {}))} districts")
    return out


def local_facts(site_root):
    """The local level: the first state whose county pages exist (Minnesota first), and what is on file there."""
    for code in sorted(PLACES):
        page = os.path.join(site_root, code, "counties", "index.html")
        if not os.path.exists(page):
            continue
        out = {"code": PLACES[code]["code"], "name": PLACES[code]["name"], "live": True, "url": f"{code}/counties/", "counties": 0, "officials": 0}
        lines = os.path.join(HERE, f"local_{code}_counties.json")
        if os.path.exists(lines):
            out["counties"] = len(json.load(open(lines, encoding="utf-8")).get("counties", {}))
        db = os.path.join(HERE, f"local_{code}.sqlite")
        if os.path.exists(db):
            con = sqlite3.connect(db)
            if con.execute("SELECT 1 FROM sqlite_master WHERE name = 'officials'").fetchone():
                out["officials"] = con.execute("SELECT COUNT(*) FROM officials").fetchone()[0]
        return out
    return {"live": False}


PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>__TITLE__</title>
<meta name="description" content="__DESC__">
<meta name="version" content="__VERSION__">
<meta name="theme-color" content="#0C0E12">
<script>try{document.documentElement.dataset.theme=localStorage.getItem("theme")||"light"}catch(e){document.documentElement.dataset.theme="light"}</script>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@400..700&family=Instrument+Serif:ital@0;1&display=swap" rel="stylesheet">
<style>
:root{--bg:#F5F5F2;--surface:#FFFFFF;--ink:#15171B;--muted:#5C6169;--line:#E4E5E1;--line-strong:#C3C5BF;--hair:rgba(21,23,27,.08);
  --accent:#0F7A6A;--accent-soft:#DDF0EB;--gold:#B8860B;--paper:#FBFAF6;--paper-ink:#1B1D21;
  --serif:"Instrument Serif",Georgia,"Times New Roman",serif;--sans:"Instrument Sans",-apple-system,"Segoe UI",Helvetica,Arial,sans-serif;--ease:cubic-bezier(.2,.8,.2,1)}
:root[data-theme="dark"]{--bg:#0B0D11;--surface:#15181D;--ink:#ECEDE9;--muted:#9BA1A9;--line:#272B32;--line-strong:#3D424B;--hair:rgba(236,237,233,.09);
  --accent:#4CC5B0;--accent-soft:#12302B;--gold:#E0B040;--paper:#EFEBDD;--paper-ink:#1B1D21}
*{box-sizing:border-box}
html,body{height:100%}
html{overflow-x:hidden}
body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--sans);font-size:16px;line-height:1.5;-webkit-font-smoothing:antialiased;overflow-x:hidden}
[hidden]{display:none!important}
a{color:inherit}
.wip{background:#7c2d12;color:#fff;padding:.5rem 1rem;font:600 13px/1.4 system-ui,sans-serif;text-align:center;letter-spacing:.02em}
.wip a{color:#fed7aa}
.top{display:flex;align-items:center;gap:10px;padding:16px clamp(16px,4vw,40px)}
.brand{display:inline-flex;align-items:center;gap:10px;font-weight:600;font-size:17px;text-decoration:none}
.brand svg{width:28px;height:28px;stroke:currentColor;fill:none;stroke-width:1.75;stroke-linecap:round;stroke-linejoin:round}
.tools{margin-left:auto;display:flex;gap:8px}
.tbtn{all:unset;box-sizing:border-box;cursor:pointer;height:36px;padding:0 12px;border-radius:999px;border:1px solid var(--line);background:var(--surface);color:var(--muted);font-size:13px;font-weight:600;display:inline-flex;align-items:center;gap:8px}
.tbtn:focus-visible,.lv:focus-visible,.nav:focus-visible,.st:focus-visible{outline:2px solid var(--accent);outline-offset:3px}
.tbtn[aria-pressed="true"]{color:var(--ink);border-color:var(--line-strong)}
main{min-height:calc(100vh - 150px);display:flex;flex-direction:column}
.hello{text-align:center;padding:clamp(8px,3vh,36px) 16px 0}
.hello h1{font-family:var(--serif);font-weight:400;font-size:clamp(40px,7.4vw,92px);line-height:.98;margin:0;letter-spacing:-.01em}
.hello h1 em{color:var(--accent);font-style:italic}
.hello p{color:var(--muted);max-width:60ch;margin:16px auto 0;font-size:clamp(15px,1.5vw,18px)}
/* the ring of cards */
.stage{overflow-x:clip;position:relative;flex:1;min-height:clamp(380px,56vh,560px);perspective:1500px;perspective-origin:50% 42%;touch-action:pan-y;cursor:grab;user-select:none;-webkit-user-select:none;margin-top:8px}
.stage.grab{cursor:grabbing}
.ring{position:absolute;inset:0;transform-style:preserve-3d}
.lv{all:unset;box-sizing:border-box;position:absolute;left:50%;top:50%;width:min(340px,78vw);height:min(430px,58vh);margin:calc(min(430px,58vh) / -2) 0 0 calc(min(340px,78vw) / -2);
  border-radius:26px;background:var(--surface);border:1px solid var(--line);padding:24px 24px 22px;display:flex;flex-direction:column;cursor:pointer;
  box-shadow:0 30px 80px -40px rgba(0,0,0,.65);will-change:transform,opacity;backface-visibility:hidden}
.lv .tag{font-size:11px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:var(--accent)}
.lv h2{font-family:var(--serif);font-weight:400;font-size:clamp(28px,3.2vw,38px);line-height:1.05;margin:8px 0 8px}
.lv p{color:var(--muted);font-size:14.5px;margin:0}
.lv .art{flex:1;display:grid;place-items:center;min-height:0;margin:8px 0}
.lv .art svg{width:100%;height:100%;max-height:150px;stroke:var(--ink);fill:none;stroke-width:1.4;stroke-linecap:round;stroke-linejoin:round;opacity:.9}
.lv .art svg .fill{fill:var(--accent);stroke:none;opacity:.22}
.lv dl{display:flex;gap:14px;margin:0 0 14px;padding:12px 0 0;border-top:1px solid var(--line)}
.lv dl div{flex:1;min-width:0}.lv dd{margin:0;font-family:var(--serif);font-size:24px;line-height:1}.lv dt{font-size:11.5px;color:var(--muted);margin-top:3px}
.lv .go{display:inline-flex;align-items:center;gap:8px;align-self:flex-start;height:40px;padding:0 18px;border-radius:999px;background:var(--ink);color:var(--bg);font-weight:600;font-size:14.5px;opacity:0;transform:translateY(6px);transition:opacity .3s,transform .3s var(--ease)}
.lv.front .go{opacity:1;transform:none}
.lv.soon{cursor:default}.lv.soon .tag{color:var(--muted)}.lv.soon .go{background:none;color:var(--muted);border:1px dashed var(--line-strong)}
.lv.front{border-color:var(--line-strong)}
/* arriving at the front: a sweep of light across the card, four star sparkles, then a slow gold shimmer round the edge */
.lv::before{content:"";position:absolute;inset:0;border-radius:inherit;pointer-events:none;opacity:0;mix-blend-mode:screen;
  background:linear-gradient(112deg,transparent 38%,rgba(255,255,255,.14) 44%,rgba(255,255,255,.9) 50%,rgba(255,255,255,.14) 56%,transparent 62%) no-repeat;background-size:260% 100%;background-position:130% 0}
:root[data-theme="light"] .lv::before{mix-blend-mode:normal}
:root:not(.calm) .lv.arrived::before{animation:sheen 1.2s cubic-bezier(.3,.1,.2,1) 1}
@keyframes sheen{0%{opacity:0;background-position:130% 0}12%{opacity:1}85%{opacity:1}100%{opacity:0;background-position:-40% 0}}
.lv::after{content:"";position:absolute;inset:-1px;border-radius:inherit;padding:2px;pointer-events:none;opacity:0;
  background:linear-gradient(115deg,transparent 30%,#FFE9A8 45%,#FFFFFF 50%,#FFD24A 55%,transparent 70%) 130% 0/240% 100% no-repeat;
  -webkit-mask:linear-gradient(#000 0 0) content-box,linear-gradient(#000 0 0);-webkit-mask-composite:xor;mask-composite:exclude}
:root:not(.calm) .lv.front::after{opacity:1;animation:rim 3.6s ease-in-out infinite}
@keyframes rim{0%{background-position:130% 0}65%,100%{background-position:-40% 0}}
.spk{position:absolute;inset:0;pointer-events:none}
.spk i{position:absolute;width:28px;height:28px;opacity:0;background:radial-gradient(circle,#fff 0 20%,#FFE27A 21% 42%,transparent 44%);
  clip-path:polygon(50% 0,58% 42%,100% 50%,58% 58%,50% 100%,42% 58%,0 50%,42% 42%);filter:drop-shadow(0 0 7px #FFD24A)}
.spk i:nth-child(1){left:-12px;top:-14px}.spk i:nth-child(2){right:-14px;top:16%;width:20px;height:20px}
.spk i:nth-child(3){right:9%;bottom:-13px;width:24px;height:24px}.spk i:nth-child(4){left:9%;bottom:14%;width:15px;height:15px}
:root:not(.calm) .lv.arrived .spk i{animation:twinkle .95s ease-in-out both}
.lv.arrived .spk i:nth-child(1){animation-delay:.3s}.lv.arrived .spk i:nth-child(2){animation-delay:.5s}.lv.arrived .spk i:nth-child(3){animation-delay:.7s}.lv.arrived .spk i:nth-child(4){animation-delay:.9s}
@keyframes twinkle{0%{opacity:0;transform:scale(0) rotate(0)}40%{opacity:1;transform:scale(1.3) rotate(45deg)}100%{opacity:0;transform:scale(0) rotate(90deg)}}
.navrow{display:flex;justify-content:center;align-items:center;gap:14px;padding:6px 0 22px}
.nav{all:unset;box-sizing:border-box;cursor:pointer;width:46px;height:46px;border-radius:50%;border:1px solid var(--line);background:var(--surface);display:grid;place-items:center}
.nav svg{width:20px;height:20px;stroke:currentColor;fill:none;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
.dots{display:flex;gap:8px}.dots i{width:8px;height:8px;border-radius:50%;background:var(--line-strong);transition:background .2s,transform .2s}.dots i.on{background:var(--accent);transform:scale(1.35)}
.promise{text-align:center;color:var(--muted);font-size:13.5px;padding:0 16px 26px}
/* the states view */
.states{padding:8px clamp(16px,4vw,40px) 40px;max-width:1180px;margin:0 auto;width:100%}
.states h1{font-family:var(--serif);font-weight:400;font-size:clamp(34px,5vw,60px);margin:6px 0 6px;line-height:1}
.states .lead{color:var(--muted);max-width:70ch;margin:0 0 14px}
.back{all:unset;cursor:pointer;display:inline-flex;gap:8px;align-items:center;color:var(--muted);font-size:14px;font-weight:600;margin:6px 0 10px}
.usmap{width:100%;height:auto;display:block}
.usmap .st{fill:var(--surface);stroke:var(--line-strong);stroke-width:.8;transition:fill .15s}
.usmap .st.building{fill:url(#hatch);cursor:pointer}
.usmap .st.live{fill:var(--accent);cursor:pointer}
.usmap .st.mine{stroke:var(--gold);stroke-width:2.4}
.usmap .st.building:hover,.usmap .st.live:hover{filter:brightness(1.15)}
.key{display:flex;gap:8px 18px;flex-wrap:wrap;font-size:13px;color:var(--muted);margin:10px 0 18px}
.key span{display:inline-flex;gap:7px;align-items:center}.key i{width:13px;height:13px;border-radius:3px;display:inline-block;border:1px solid var(--line-strong)}
.cards{display:grid;gap:12px;grid-template-columns:repeat(auto-fill,minmax(260px,1fr))}
.scard{border:1px solid var(--line);background:var(--surface);border-radius:18px;padding:16px 18px}
.scard h3{margin:0 0 4px;font-size:18px}.scard p{margin:0;color:var(--muted);font-size:14px}
.scard .pill{display:inline-block;font-size:11px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;border-radius:999px;padding:3px 10px;margin-bottom:8px;background:var(--accent-soft);color:var(--accent)}
.scard a.open{display:inline-flex;margin-top:10px;height:36px;padding:0 16px;align-items:center;border-radius:999px;background:var(--ink);color:var(--bg);font-weight:600;font-size:14px;text-decoration:none}
.chips{display:flex;gap:8px;flex-wrap:wrap;margin-top:14px}.chips span{border:1px dashed var(--line-strong);border-radius:999px;padding:5px 12px;font-size:13px;color:var(--muted)}
footer{border-top:1px solid var(--hair);padding:18px clamp(16px,4vw,40px);color:var(--muted);font-size:13px;display:flex;gap:8px 18px;flex-wrap:wrap;justify-content:space-between}
/* the page turn: the chosen card grows into a cover, the cover turns on its spine, the space beneath opens */
.turn{position:fixed;inset:0;z-index:50;perspective:2400px;perspective-origin:0% 50%;background:var(--bg);overflow:hidden}
.turn .under{position:absolute;inset:0;display:grid;place-items:center;text-align:center;background:radial-gradient(90% 80% at 50% 45%,var(--surface),var(--bg));padding:24px}
.turn .under h2{font-family:var(--serif);font-weight:400;font-size:clamp(40px,7vw,88px);line-height:1;margin:0}
.turn .under p{color:var(--muted);margin:14px 0 0}
.turn .under .shade{position:absolute;inset:0;background:linear-gradient(to right,rgba(0,0,0,.55),rgba(0,0,0,0) 45%);opacity:0;pointer-events:none}
.turn .leaf{position:absolute;inset:0;transform-origin:0% 50%;transform-style:preserve-3d;will-change:transform}
.turn .face{position:absolute;inset:0;backface-visibility:hidden;display:grid;place-items:center;text-align:center;padding:24px;background:var(--paper);color:var(--paper-ink)}
.turn .face.front{background:linear-gradient(to right,rgba(0,0,0,.18),rgba(0,0,0,0) 7%),var(--paper)}
.turn .face.back{transform:rotateY(180deg);background:linear-gradient(to left,rgba(0,0,0,.22),rgba(0,0,0,0) 9%),repeating-linear-gradient(0deg,rgba(27,29,33,.05) 0 1px,transparent 1px 34px),var(--paper)}
.turn .face .tag{font-size:12px;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:#0F7A6A}
.turn .face h2{font-family:var(--serif);font-weight:400;font-size:clamp(44px,8vw,104px);line-height:.98;margin:10px 0 0}
.turn .face .gloss{position:absolute;inset:0;background:linear-gradient(100deg,rgba(255,255,255,0) 30%,rgba(255,255,255,.55) 50%,rgba(255,255,255,0) 70%);opacity:0;pointer-events:none}
.turn.go .leaf{animation:leafturn 2.1s .55s cubic-bezier(.45,.05,.25,1) forwards}
.turn.go .face.front{animation:coverin .55s var(--ease) both}
.turn.go .gloss{animation:gloss 2.1s .55s ease-in-out forwards}
.turn.go .under .shade{animation:shade 2.1s .55s ease-in-out forwards}
.turn.go .under h2,.turn.go .under p{animation:rise .7s 2.15s var(--ease) both}
@keyframes coverin{from{opacity:0;transform:scale(.82)}to{opacity:1;transform:none}}
@keyframes leafturn{0%{transform:rotateY(0)}100%{transform:rotateY(-179deg)}}
@keyframes gloss{0%{opacity:0}35%{opacity:.9}100%{opacity:0}}
@keyframes shade{0%{opacity:0}30%{opacity:1}100%{opacity:0}}
@keyframes rise{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:none}}
.skip{position:absolute;right:18px;bottom:16px;z-index:3;font-size:12.5px;color:var(--muted)}
@media (max-width:560px){.lv{padding:20px 18px 18px;border-radius:22px}.lv dd{font-size:21px}}
@media (prefers-reduced-motion: reduce){.turn.go .leaf,.turn.go .face.front,.turn.go .gloss,.turn.go .under .shade,.turn.go .under h2,.turn.go .under p{animation:none}}
/* On The Ballot: the switch at the top middle, the fireworks it sets off, and the wormhole it opens */
.top{position:relative}
.bsw{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);display:flex;flex-direction:column;align-items:center;gap:3px;text-decoration:none;color:inherit;z-index:6;-webkit-tap-highlight-color:transparent;outline:none}
.bsw .trk{position:relative;display:inline-flex;align-items:center;gap:10px;height:42px;padding:0 18px 0 6px;border-radius:999px;overflow:hidden;isolation:isolate;white-space:nowrap;
  background:radial-gradient(140% 170% at 14% 0%,#27366F 0%,#0E1739 52%,#060A1E 100%);color:#FFF4D6;font-weight:700;font-size:14.5px;letter-spacing:.03em;
  box-shadow:0 10px 26px -12px rgba(8,16,52,.85),inset 0 0 0 1px rgba(255,214,110,.45);transition:box-shadow .35s,transform .35s var(--ease)}
.bsw .trk::before{content:"";position:absolute;inset:0;z-index:-1;animation:bstars 2.6s ease-in-out infinite alternate;
  background-image:radial-gradient(1.3px 1.3px at 16% 30%,#fff 55%,transparent 60%),radial-gradient(1px 1px at 34% 72%,#FFE9A8 55%,transparent 60%),radial-gradient(1.4px 1.4px at 57% 24%,#fff 55%,transparent 60%),radial-gradient(1px 1px at 71% 66%,#CFE3FF 55%,transparent 60%),radial-gradient(1.2px 1.2px at 88% 34%,#fff 55%,transparent 60%),radial-gradient(1px 1px at 46% 52%,#fff 55%,transparent 60%)}
.bsw .trk::after{content:"";position:absolute;inset:0;z-index:-1;background:linear-gradient(112deg,transparent 36%,rgba(255,226,140,.34) 47%,rgba(255,255,255,.6) 50%,rgba(255,226,140,.34) 53%,transparent 64%) 160% 0/260% 100% no-repeat;animation:bsheen 3.6s ease-in-out infinite}
.bsw .knob{width:30px;height:30px;border-radius:50%;flex:none;display:grid;place-items:center;background:linear-gradient(150deg,#FFF1C2,#E7A928 68%,#B57708);box-shadow:0 0 14px rgba(255,205,90,.65),inset 0 -2px 3px rgba(120,70,0,.35)}
.bsw .knob svg{width:17px;height:17px;fill:none;stroke:#3A2600;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
.bsw .when{font-size:11.5px;font-weight:600;color:var(--muted);letter-spacing:.02em;min-height:1.2em}
.bsw:hover .trk{transform:translateY(-1px);box-shadow:0 14px 30px -10px rgba(8,16,52,.9),inset 0 0 0 1px rgba(255,214,110,.8),0 0 0 5px rgba(255,205,90,.16)}
.bsw:focus-visible .trk{outline:2px solid var(--gold);outline-offset:3px}
.bsw.charge .trk{animation:bcharge 3s linear forwards}
.bsw.on .trk{flex-direction:row-reverse;padding:0 6px 0 18px;background:radial-gradient(140% 170% at 86% 0%,#1E8574 0%,#0F5248 55%,#072722 100%);
  box-shadow:0 10px 26px -12px rgba(5,40,34,.85),inset 0 0 0 1px rgba(160,255,230,.45),0 0 18px rgba(76,197,176,.35)}
@keyframes bstars{from{opacity:.35}to{opacity:1}}
@keyframes bsheen{0%{background-position:160% 0}62%,100%{background-position:-60% 0}}
@keyframes bcharge{from{box-shadow:0 10px 26px -12px rgba(8,16,52,.85),inset 0 0 0 1px rgba(255,214,110,.8),0 0 0 0 rgba(255,205,90,0)}to{box-shadow:0 10px 26px -12px rgba(8,16,52,.85),inset 0 0 0 1px #FFF1C2,0 0 34px 10px rgba(255,205,90,.6)}}
:root.calm .bsw .trk::before,:root.calm .bsw .trk::after,:root.calm .bsw.charge .trk{animation:none}
@media (max-width:760px){.top{flex-wrap:wrap}.bsw{position:static;transform:none;order:3;flex-basis:100%;margin-top:12px}}
.page{transform-origin:50% 42%}
body.pull .page{transition:transform 1s cubic-bezier(.62,0,.88,.3),filter 1s ease-in,opacity .9s ease-in .1s;transform:scale(.05) rotate(40deg);filter:blur(7px);opacity:0}
body.arrive .page{animation:emerge 1.05s cubic-bezier(.16,.7,.2,1) both}
@keyframes emerge{from{transform:scale(.18) rotate(-30deg);filter:blur(8px);opacity:0}to{transform:none;filter:none;opacity:1}}
body.fadeout .page{transition:opacity .2s;opacity:0}
.sky canvas{transform-origin:50% 44%}
.sky.pull canvas{transition:transform 1.1s cubic-bezier(.62,0,.88,.3),opacity 1s ease-in .15s;transform:scale(.04) rotate(40deg);opacity:0}
.sky{position:fixed;inset:0;z-index:70;cursor:pointer;opacity:0;transition:opacity .7s ease;outline:none;
  background:radial-gradient(130% 100% at 50% 115%,rgba(30,36,84,.7),rgba(4,6,20,.93) 62%);-webkit-backdrop-filter:blur(12px) saturate(.6);backdrop-filter:blur(12px) saturate(.6)}
.sky.show{opacity:1}
.sky canvas,.wh canvas{position:absolute;inset:0;width:100%;height:100%;display:block}
.sky .hint{position:absolute;left:0;right:0;bottom:26px;margin:0;text-align:center;color:rgba(255,244,214,.72);font-size:13px;letter-spacing:.04em;opacity:0;transition:opacity .6s 1.2s}
.sky.show .hint{opacity:1}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
.wh{position:fixed;inset:0;z-index:80;cursor:pointer}
</style>
</head>
<body>
<div class="page" id="page">
__WIP__
<header class="top">
  <a class="brand" href="__HOME__" aria-label="The Civic Archive, front door"><svg viewBox="0 0 28 28" aria-hidden="true"><path d="M14 3v2.5"/><path d="M6.5 13.5a7.5 7.5 0 0 1 15 0"/><path d="M4 13.5h20"/><path d="M6.5 16.5v6M11.5 16.5v6M16.5 16.5v6M21.5 16.5v6"/><path d="M3 24h22"/></svg><span>The Civic Archive</span></a>
  __SWITCH__
  <div class="tools">
    <button class="tbtn" id="motion" type="button" aria-pressed="true" title="Spinning cards and the page-turn: on or off">Motion</button>
    <button class="tbtn" id="theme" type="button" title="Light / dark">Light / dark</button>
  </div>
</header>

<main id="door">
  <section class="hello">
    <h1>__H1__</h1>
    <p>__LEAD__</p>
  </section>
  <div class="stage" id="stage" role="group" aria-roledescription="carousel" aria-label="Levels of government">
    <div class="ring" id="ring"></div>
  </div>
  <div class="navrow"><button class="nav" id="prev" type="button" aria-label="Previous card"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M15 6l-6 6 6 6"/></svg></button><div class="dots" id="dots" aria-hidden="true"></div><button class="nav" id="next" type="button" aria-label="Next card"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 6l6 6-6 6"/></svg></button></div>
  <p class="promise">No ads. No donors. No take to sell you. Drag the cards, use the arrow keys, or tap one.</p>
</main>

<main id="states" class="states" hidden>
  <button class="back" id="backdoor" type="button"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M15 6l-6 6 6 6"/></svg>Back to the front door</button>
  <h1>Choose a state</h1>
  <p class="lead" id="stateslead"></p>
  <svg class="usmap" id="usmap" viewBox="0 0 975 610" role="img" aria-label="Map of the United States: states that are open are filled, states being built are hatched"><defs><pattern id="hatch" patternUnits="userSpaceOnUse" width="7" height="7" patternTransform="rotate(45)"><rect width="7" height="7" fill="var(--surface)"/><rect width="3" height="7" fill="var(--accent)" opacity=".55"/></pattern></defs></svg>
  <div class="key"><span><i style="background:var(--accent)"></i>Open now</span><span><i style="background:repeating-linear-gradient(45deg,var(--accent) 0 3px,var(--surface) 3px 7px)"></i>Being built</span><span><i style="background:var(--surface)"></i>Not started</span><span><i style="border:2px solid var(--gold);background:none"></i>Your state, if you have picked one</span></div>
  <div class="cards" id="statecards"></div>
  <div class="chips" id="offmap"></div>
</main>

<footer><span>__FOOTER__</span><span id="builton">Built __GENERATED__</span></footer>
</div>

<div class="turn" id="turn" hidden aria-live="polite">
  <div class="under"><div><h2 id="turnunder"></h2><p id="turnsub">Opening&hellip;</p></div><div class="shade"></div></div>
  <div class="leaf"><div class="face front"><div><div class="tag" id="turntag"></div><h2 id="turntitle"></h2></div><div class="gloss"></div></div><div class="face back"></div></div>
  <div class="skip">Click, or press any key, to skip</div>
</div>

<div class="sky" id="sky" hidden tabindex="-1" role="dialog" aria-modal="true" aria-label="__SKYLABEL__"><canvas id="skyfx" aria-hidden="true"></canvas><p class="sr">__SKYLABEL__. Click to see.</p><p class="hint" aria-hidden="true">Click anywhere to step through. Wait, and the sky clears.</p></div>
<div class="wh" id="wh" hidden aria-hidden="true"><canvas id="whfx"></canvas></div>

<script>
const DOOR = __DATA__;
const $ = (s, el) => (el || document).querySelector(s), $$ = (s, el) => [...(el || document).querySelectorAll(s)];
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
const store = {get: k => { try { return localStorage.getItem(k); } catch (e) { return null; } }, set: (k, v) => { try { localStorage.setItem(k, v); } catch (e) {} }};

/* the same two switches, and the same saved choices, as the rest of the site */
let motionOn = store.get("motion") ? store.get("motion") === "on" : !matchMedia("(prefers-reduced-motion: reduce)").matches;
const calm = () => !motionOn;
const showMotion = () => { $("#motion").setAttribute("aria-pressed", motionOn); document.documentElement.classList.toggle("calm", !motionOn); };
showMotion();
$("#motion").addEventListener("click", () => { motionOn = !motionOn; store.set("motion", motionOn ? "on" : "off"); showMotion(); idle = performance.now(); kick(); });
$("#theme").addEventListener("click", () => { const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark"; document.documentElement.dataset.theme = next; store.set("theme", next); });

/* ---------- the levels ---------- */
const F = DOOR.federal || {}, myState = store.get("state"), mine = (DOOR.states || []).find(s => s.code === myState);
const ART = {
  federal: `<svg viewBox="0 0 200 120" aria-hidden="true"><path class="fill" d="M20 104h160v6H20z"/><path d="M100 8v10M100 18a6 6 0 0 1 6 6v6h-12v-6a6 6 0 0 1 6-6zM76 62a24 30 0 0 1 48 0M70 62h60M74 62v18M84 62v18M94 62v18M106 62v18M116 62v18M126 62v18M58 80h84M46 80v24M154 80v24M28 92h144M28 92v12M172 92v12M20 104h160"/></svg>`,
  state: `<svg viewBox="0 0 200 120" aria-hidden="true"><path class="fill" d="M58 14h62l4 10 22 4 6 16-10 18 8 22-14 20H62l-6-26 8-16-10-22z"/><path d="M58 14h62l4 10 22 4 6 16-10 18 8 22-14 20H62l-6-26 8-16-10-22zM64 48h76M60 76h84M92 14v90M120 28v76"/></svg>`,
  local: `<svg viewBox="0 0 200 120" aria-hidden="true"><path class="fill" d="M30 104h140v6H30z"/><path d="M100 16l44 26H56zM64 42v50M84 42v50M116 42v50M136 42v50M52 92h96M40 104h120M100 16V8M100 58a7 7 0 1 1 0 .1"/></svg>`};
const LEVELS = DOOR.levels || [      // the On The Ballot door brings its own cards
  {key: "federal", tag: "Federal", title: "The United States Congress", text: "Every bill and joint resolution of the 119th Congress, every recorded vote member by member, and who funds each campaign.",
    facts: [[F.bills, "bills"], [F.votes, "recorded votes"], [F.members, "members"]], go: "Step inside", url: "us/", under: "The U.S. Congress"},
  {key: "state", tag: "State", title: mine ? `${mine.name}, and every state` : "Your state legislature", text: "The same record for state capitols: your districts, who represents them, how they voted and who funds them. Minnesota first, then outward.",
    facts: [[(DOOR.states || []).filter(s => s.live).length, "open now"], [(DOOR.states || []).filter(s => !s.live && s.loaded.length).length, "being built"], [56, "planned"]], go: "Choose a state", view: "states", under: "The states"},
  DOOR.local && DOOR.local.live ? {key: "local", tag: "County and city", title: `${DOOR.local.name}'s counties`, text: `The local level is opening, ${DOOR.local.name} first: every county on one map, and who holds each county office as the official election results record it. Cities and school boards follow.`,
    facts: [[DOOR.local.counties, "counties"], [DOOR.local.officials, "county offices on file"]], go: "Step inside", url: DOOR.local.url, under: `${DOOR.local.name}'s counties`}
  : {key: "local", tag: "County and city", title: "Closer to home", text: "County boards and city councils are not built yet. The ring has room for them.", facts: [], go: "Not built yet", soon: true}];
const ring = $("#ring"), stage = $("#stage"), dots = $("#dots"), N = LEVELS.length, STEP = 2 * Math.PI / N;
ring.innerHTML = LEVELS.map((L, i) => `<button class="lv${L.soon ? " soon" : ""}" type="button" data-i="${i}" aria-label="${esc(L.tag)}: ${esc(L.title)}"${L.soon ? ' aria-disabled="true"' : ""}>
  <span class="tag">${esc(L.tag)}</span><h2>${esc(L.title)}</h2><p>${esc(L.text)}</p><span class="art">${ART[L.key] || ""}</span>
  ${L.facts.length ? `<dl>${L.facts.map(f => `<div><dd>${f[0] == null ? "–" : Number(f[0]).toLocaleString()}</dd><dt>${esc(f[1])}</dt></div>`).join("")}</dl>` : ""}<span class="go">${esc(L.go)}</span><span class="spk" aria-hidden="true"><i></i><i></i><i></i><i></i></span></button>`).join("");
dots.innerHTML = LEVELS.map(() => "<i></i>").join("");
const cards = $$(".lv", ring);

/* ---------- the ring: cards ride a circle, always facing you; the nearest one is in front ---------- */
let angle = 0, target = 0, drag = null, downCard = null, moved = 0, raf = 0, idle = performance.now(), last = performance.now(), front = 0, rested = -1;
const GLIDE = 2600, WAIT = 12000;     // milliseconds for a card to travel one place round the ring; milliseconds of stillness before the ring moves on by itself
let from = 0, began = 0, span = 0;
const ease = p => p < .5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2;        // slow away, slow home
const glideTo = t => { from = angle; target = t; began = performance.now(); span = GLIDE * Math.min(1.4, Math.max(.4, Math.abs(t - angle) / STEP)); rested = -1; };
const radius = () => Math.min(460, Math.max(210, stage.clientWidth * .42));
function place(){
  const R = radius(); let best = 0, bestZ = -1e9;
  cards.forEach((c, i) => { const a = i * STEP + angle, x = Math.sin(a) * R, z = Math.cos(a) * R - R, depth = (z + 2 * R) / (2 * R);      // depth: 1 in front, 0 at the back
    c.style.transform = `translate3d(${x.toFixed(1)}px,${((1 - depth) * -18).toFixed(1)}px,${z.toFixed(1)}px)`; c.style.opacity = (.28 + .72 * depth).toFixed(3);
    c.style.zIndex = String(Math.round(depth * 100)); c.style.filter = depth > .97 ? "" : `brightness(${(.62 + .38 * depth).toFixed(3)})`;
    if (z > bestZ) { bestZ = z; best = i; } });
  if (best !== front || !cards[best].classList.contains("front")) { front = best; cards.forEach((c, i) => { c.classList.toggle("front", i === best); c.tabIndex = i === best ? 0 : -1; }); $$("i", dots).forEach((d, i) => d.classList.toggle("on", i === best)); }
}
function frame(now){
  raf = 0;
  if (!drag) {
    if (!calm() && angle === target && now - idle > WAIT) { glideTo(target - STEP); idle = now; }      // when nobody is touching it, the ring moves on by itself
    if (angle !== target) { const p = span ? Math.min(1, (now - began) / span) : 1; angle = p >= 1 ? target : from + (target - from) * ease(p); }
  }
  place();
  if (!drag && angle === target && rested !== front) arrive();
  if (drag || angle !== target || (!calm() && document.visibilityState !== "hidden")) kick();
}
/* a card has come to the front and stopped: light sweeps across it and a few stars twinkle */
function arrive(){ rested = front; cards.forEach((c, i) => c.classList.toggle("arrived", i === front)); clearTimeout(arrive.t); arrive.t = setTimeout(() => cards.forEach(c => c.classList.remove("arrived")), 2100); }
function kick(){ if (!raf) raf = requestAnimationFrame(frame); }
const snap = () => { glideTo(Math.round(angle / STEP) * STEP); idle = performance.now(); kick(); };
const turnBy = n => { glideTo(Math.round(target / STEP) * STEP - n * STEP); idle = performance.now(); if (calm()) { angle = target; place(); arrive(); } else kick(); };
$("#prev").addEventListener("click", () => turnBy(-1)); $("#next").addEventListener("click", () => turnBy(1));
stage.addEventListener("pointerdown", e => { downCard = e.target.closest ? e.target.closest(".lv") : null; drag = {x: e.clientX}; moved = 0; rested = -1; last = performance.now(); stage.classList.add("grab"); try { stage.setPointerCapture(e.pointerId); } catch (x) {} kick(); });
stage.addEventListener("pointermove", e => { if (!drag) return; const dx = e.clientX - drag.x; moved += Math.abs(dx); angle += dx / radius(); target = angle; drag.x = e.clientX; idle = performance.now(); });
const release = e => { if (!drag) return; drag = null; stage.classList.remove("grab"); const c = downCard; downCard = null; last = performance.now(); snap(); if (moved < 8 && c) choose(+c.dataset.i); };
stage.addEventListener("pointerup", release); stage.addEventListener("pointercancel", () => { drag = null; stage.classList.remove("grab"); snap(); });
stage.addEventListener("click", e => { if (e.detail === 0) { const c = e.target.closest(".lv"); if (c) choose(+c.dataset.i); } });      // keyboard "clicks" (Enter, Space) carry no pointer
document.addEventListener("keydown", e => { if (!$("#turn").hidden) { finish(); return; } if ($("#door").hidden || !$("#sky").hidden) return; if (e.key === "ArrowLeft") { turnBy(-1); e.preventDefault(); } else if (e.key === "ArrowRight") { turnBy(1); e.preventDefault(); } });
addEventListener("resize", () => { place(); });

function choose(i){
  const L = LEVELS[i]; if (!L) return;
  const at = ((Math.round(-target / STEP) % N) + N) % N;
  if (i !== at) { let d = i - at; if (d > N / 2) d -= N; if (d < -N / 2) d += N; turnBy(d); return; }       // a card at the side comes to the front first
  if (L.soon) return;
  turnPage(L);
}

/* ---------- the page turn: three seconds, like opening a book ---------- */
let pending = null, timer = 0;
function turnPage(L){
  pending = L;
  if (calm()) { finish(); return; }
  const t = $("#turn"); $("#turntag").textContent = L.tag; $("#turntitle").textContent = L.title; $("#turnunder").textContent = L.under || L.title; $("#turnsub").innerHTML = L.view ? "" : "Opening&hellip;";
  t.hidden = false; t.classList.remove("go"); void t.offsetWidth; t.classList.add("go");
  timer = setTimeout(finish, 3000);
}
function finish(){
  clearTimeout(timer); const L = pending; pending = null; if (!L) return;
  if (L.view === "states") { showStates(); $("#turn").hidden = true; $("#turn").classList.remove("go"); return; }
  location.href = L.url;
}
$("#turn").addEventListener("click", finish);
addEventListener("pageshow", () => { $("#turn").hidden = true; $("#turn").classList.remove("go"); pending = null; });      // coming back with the Back button

/* ---------- the states ---------- */
function showStates(){
  $("#door").hidden = true; $("#states").hidden = false; scrollTo(0, 0); history.replaceState(null, "", "#states");
  const S = DOOR.states || [], by = Object.fromEntries(S.map(s => [s.code, s])), live = S.filter(s => s.live), building = S.filter(s => !s.live && s.loaded.length);
  $("#stateslead").textContent = live.length ? `${live.length === 1 ? "One state is" : live.length + " states are"} open. The rest are on the way, Minnesota outward.` : "No state is open yet. Minnesota is first, and it is being built now; every other state, the District of Columbia, Puerto Rico and Guam follow.";
  const svg = $("#usmap");
  if (!svg.dataset.drawn) { svg.dataset.drawn = "1";
    svg.insertAdjacentHTML("beforeend", Object.entries(DOOR.map).map(([code, s]) => { const p = by[code], cls = p ? (p.live ? "live" : (p.loaded.length ? "building" : "")) : "";
      return `<path class="st ${cls}${code === myState ? " mine" : ""}" d="${s.d}" data-code="${code}" ${cls ? 'tabindex="0" role="button"' : ""}><title>${esc(s.name)}${p ? (p.live ? ": open" : ": being built") : ": not started"}</title></path>`; }).join(""));
    svg.addEventListener("click", e => { const st = e.target.closest(".st"); if (st) openState(st.dataset.code); });
    svg.addEventListener("keydown", e => { if ((e.key === "Enter" || e.key === " ") && e.target.classList.contains("st")) { e.preventDefault(); openState(e.target.dataset.code); } }); }
  $("#statecards").innerHTML = S.map(s => `<article class="scard" id="sc-${esc(s.code)}"><span class="pill">${s.live ? ((s.coming || []).length ? "Open, still filling in" : "Open now") : (s.loaded.length ? "Being built" : "Planned")}</span><h3>${esc(s.name)}</h3>
    <p>${s.live ? esc(s.legislature) + ": " + esc(s.loaded.join(", ")) + "." + ((s.coming || []).length ? " Still to come: " + esc(s.coming.join(", ")) + "." : "") : (s.loaded.length ? "Loaded so far: " + esc(s.loaded.join(", ")) + ". Bills and recorded votes come next, then the pages open." : "Not started.")}</p>${s.live ? `<a class="open" href="${esc(s.code.toLowerCase())}/" data-state="${esc(s.code)}">Open ${esc(s.name)}</a>` : ""}</article>`).join("");
  $("#offmap").innerHTML = (DOOR.offmap || []).map(o => `<span>${esc(o[1])}: planned</span>`).join("");
}
function openState(code){
  const s = (DOOR.states || []).find(x => x.code === code);
  if (s && s.live) { turnPage({tag: "State", title: s.name, under: s.legislature, url: code.toLowerCase() + "/"}); return; }
  const card = $("#sc-" + code); if (card) card.scrollIntoView({block: "center", behavior: calm() ? "auto" : "smooth"});
}
$("#statecards").addEventListener("click", e => { const a = e.target.closest("a.open"); if (!a || calm()) return; e.preventDefault(); openState(a.dataset.state); });
$("#backdoor").addEventListener("click", () => { $("#states").hidden = true; $("#door").hidden = false; history.replaceState(null, "", "./"); place(); kick(); });

/* ---------- On The Ballot: the switch, the fireworks and the wormhole ---------- */
const SW = $("#bsw"), sky = $("#sky"), skyfx = $("#skyfx");
let skyRaf = 0, skyOpen = false, armed = true, chargeT = 0, going = false;
(function when(){      /* the days left until Election Day, counted on the reader's own calendar */
  const el = $("#bwhen"); if (!el) return;
  if (DOOR.whenText) { el.textContent = DOOR.whenText; return; }
  const [y, m, d] = String(DOOR.election || "").split("-").map(Number); if (!y) return;
  const day = new Date(y, m - 1, d), now = new Date(), n = Math.round((day - new Date(now.getFullYear(), now.getMonth(), now.getDate())) / 864e5);
  el.textContent = n > 1 ? `Election Day in ${n} days` : n === 1 ? "Election Day is tomorrow" : n === 0 ? "Election Day is today"
    : `Election Day was ${day.toLocaleDateString("en-US", {month: "long", day: "numeric"})}`;
})();
function glow(color){      /* one soft point of light, drawn once and stamped many times */
  const c = document.createElement("canvas"); c.width = c.height = 32; const g = c.getContext("2d"), r = g.createRadialGradient(16, 16, 0, 16, 16, 16);
  r.addColorStop(0, "#FFFFFF"); r.addColorStop(.2, color); r.addColorStop(.5, color + "70"); r.addColorStop(1, color + "00"); g.fillStyle = r; g.fillRect(0, 0, 32, 32); return c;
}
/* what the fireworks spell, word by word in red, white and blue (John, 2026-09-29), with CLICK TO SEE in silver beneath */
const RED = "#FF3B3B", WHITE = "#FFFFFF", BLUE = "#3D7BFF", SILVER = ["#F2F4F7", "#A9B0BA"];
const SKYWORDS = DOOR.sky || [[["ON", RED], ["THE", WHITE], ["BALLOT", BLUE]]];
function letterPoints(W, H){      /* where each spark comes to rest: the words drawn off screen, then sampled on a grid */
  const c = document.createElement("canvas"); c.width = W; c.height = H; const g = c.getContext("2d"), FONT = '"Instrument Sans", system-ui, sans-serif';
  const texts = SKYWORDS.map(l => l.map(w => w[0]).join(" "));
  let f1 = Math.max(30, Math.min(W * .11, H * (SKYWORDS.length > 1 ? .14 : .19), 150)); g.font = `700 ${f1}px ${FONT}`;
  const widest = Math.max(...texts.map(t => g.measureText(t).width)); if (widest > W * .9) f1 *= W * .9 / widest;
  const f2 = f1 * .5, step = f1 * 1.06, words = [];
  let y = H * .42 - ((SKYWORDS.length - 1) * step + f1 * .5 + f2 * 1.05) / 2;
  g.fillStyle = "#fff"; g.textAlign = "left"; g.textBaseline = "middle";
  SKYWORDS.forEach(line => {      // each word drawn in its own place, so each spark knows its word and its colour
    g.font = `700 ${f1}px ${FONT}`;
    const space = g.measureText(" ").width, total = line.reduce((s, w, i) => s + g.measureText(w[0]).width + (i ? space : 0), 0);
    let x = W / 2 - total / 2;
    line.forEach(([t, color]) => { const w = g.measureText(t).width; g.fillText(t, x, y); words.push({x0: x, x1: x + w, y, h: f1, color}); x += w + space; });
    y += step;
  });
  const ySub = y - step + f1 * .5 + f2 * 1.05;
  g.font = `700 ${f2}px ${FONT}`; const sw = g.measureText("CLICK TO SEE").width; g.fillText("CLICK TO SEE", W / 2 - sw / 2, ySub);
  words.push({x0: W / 2 - sw / 2, x1: W / 2 + sw / 2, y: ySub, h: f2, color: "silver", sub: true});
  const gap = Math.max(4, Math.round(f1 / 23)), d = g.getImageData(0, 0, W, H).data, pts = [];
  for (let yy = 0; yy < H; yy += gap) for (let xx = 0; xx < W; xx += gap) if (d[(yy * W + xx) * 4 + 3] > 140) {
    const wi = words.findIndex(w => Math.abs(yy - w.y) <= w.h * .72 && xx >= w.x0 - 3 && xx <= w.x1 + 3);
    if (wi >= 0) pts.push({x: xx, y: yy, w: wi});
  }
  const main = words.filter(w => !w.sub);      // the block the big words fill, for the flag's canton and stripes
  const block = {bx0: Math.min(...main.map(w => w.x0)), bx1: Math.max(...main.map(w => w.x1)),
                 by0: Math.min(...main.map(w => w.y)) - f1 * .5, by1: Math.max(...main.map(w => w.y)) + f1 * .5};
  return {pts, words, gap, f1, block};
}
function fireworks(){
  if (skyOpen || going) return; skyOpen = true; armed = false;
  sky.hidden = false; void sky.offsetWidth; sky.classList.add("show"); sky.focus({preventScroll: true});
  const dpr = Math.min(2, devicePixelRatio || 1), W = innerWidth, H = innerHeight, g = skyfx.getContext("2d");
  skyfx.width = Math.round(W * dpr); skyfx.height = Math.round(H * dpr); g.setTransform(dpr, 0, 0, dpr, 0, 0);
  const COLORS = [RED, WHITE, BLUE, ...SILVER], SPR = Object.fromEntries(COLORS.map(c => [c, glow(c)]));
  const tint = c => c === "silver" ? SILVER[(Math.random() * 2) | 0] : c;      // silver twinkles between a bright and a darker grey
  const stars = Array.from({length: Math.round(W * H / 8000)}, () => ({x: Math.random() * W, y: Math.random() * H * .9, r: Math.random() * 1.3 + .3, p: Math.random() * 6.28}));
  const T = letterPoints(W, H), groups = [];
  T.words.forEach((wd, wi) => {      // one burst for a short word, two or three along a long one, left to right
    const P = T.pts.filter(p => p.w === wi); if (!P.length) return;
    const n = wd.sub ? 3 : Math.max(1, Math.min(3, Math.round((wd.x1 - wd.x0) / (T.f1 * 1.9))));
    for (let k = 0; k < n; k++) { const a = wd.x0 + (wd.x1 - wd.x0) * k / n, b = wd.x0 + (wd.x1 - wd.x0) * (k + 1) / n;
      const Q = P.filter(p => p.x >= a - 3 && (k === n - 1 ? p.x <= b + 3 : p.x < b));
      if (Q.length) groups.push({pts: Q, cx: (a + b) / 2, cy: wd.y - (wd.sub ? 0 : 10), color: wd.color, sub: !!wd.sub}); }
  });
  const rockets = groups.map((G, i) => ({at: 150 + i * 230 + (G.sub ? 260 : 0), x0: G.cx + (Math.random() - .5) * 90, G, color: G.color}));
  const later = groups.length * 230 + 700;      // when the words are nearly whole, a few more bursts around them
  for (let k = 0; k < 7; k++) rockets.push({at: later + k * 380, x0: W * (.1 + .8 * Math.random()), G: {cx: W * (.08 + .84 * Math.random()), cy: H * (.1 + .2 * Math.random()), pts: []}, color: [RED, WHITE, BLUE][k % 3], deco: true});
  const parts = [], t0 = performance.now(), HOLD = 7000, FADE = 1500; let lastT = t0;      // the words are whole by about 3.9 s and hold till 7
  /* the way back is drawn as the flag (John, 2026-09-29): a blue canton with white stars at the top left of the words,
     thirteen red and white stripes across the rest, rippling as if it were flying */
  const FLAG = DOOR.skyStyle === "flag", B = T.block, BW = B.bx1 - B.bx0, BH = B.by1 - B.by0;
  function flagColor(p){
    if (p.x < B.bx0 + BW * .4 && p.y < B.by0 + BH * .54) {
      const cols = 6, rows = 3, cw = BW * .4 / cols, ch = BH * .54 / rows, i = Math.floor((p.x - B.bx0) / cw), j = Math.floor((p.y - B.by0) / ch);
      const cx = B.bx0 + (i + (j % 2 ? .75 : .35)) * cw, cy = B.by0 + (j + .5) * ch;      // staggered rows of stars
      return Math.hypot(p.x - cx, p.y - cy) < Math.min(cw, ch) * .3 ? "star" : BLUE;
    }
    return Math.floor((p.y - B.by0) / (BH / 13)) % 2 ? WHITE : RED;
  }
  const whole = Math.max(...rockets.filter(R => !R.deco && !R.G.sub).map(R => R.at)) + 650 + 1370;      // when the big words are complete
  let popped = false;
  function pop(t){      // the words complete: a flash of light and a ring of red, white and blue sparks
    popped = true;
    for (let k = 0; k < 190; k++) {
      const a = Math.random() * 6.283, v = 220 + Math.random() * 380, ex = B.bx0 + BW / 2 + Math.cos(a) * BW * .45, ey = B.by0 + BH / 2 + Math.sin(a) * BH * .6;
      parts.push({x: ex, y: ey, vx: Math.cos(a) * v, vy: Math.sin(a) * v, born: t, life: 800 + Math.random() * 700, s: 5 + Math.random() * 7, c: [RED, WHITE, BLUE][k % 3]});
    }
  }
  function explode(R, t){
    const {G} = R, s = T.gap * 2.2;
    G.pts.forEach(p => { const a = Math.random() * 6.283, v = 170 + Math.random() * 260, fc = FLAG && !G.sub ? flagColor(p) : null;
      parts.push({x: G.cx, y: G.cy, vx: Math.cos(a) * v, vy: Math.sin(a) * v, tx: p.x, ty: p.y, born: t, s: fc === "star" ? s * 1.5 : s,
                  c: fc ? (fc === "star" ? WHITE : fc) : tint(R.color), star: fc === "star", flag: !!fc, tw: Math.random() * 6.28}); });
    for (let k = 0, n = R.deco ? 120 : 70; k < n; k++) { const a = Math.random() * 6.283, v = 80 + Math.random() * (R.deco ? 330 : 250);
      parts.push({x: G.cx, y: G.cy, vx: Math.cos(a) * v, vy: Math.sin(a) * v, born: t, life: 900 + Math.random() * 1000, s: 4 + Math.random() * 6, c: tint(R.color)}); }
  }
  function step(now){
    const t = now - t0, dt = Math.min(40, now - lastT) / 1000; lastT = now;
    g.globalCompositeOperation = "source-over"; g.clearRect(0, 0, W, H); g.fillStyle = "#FFFFFF";
    for (const s of stars) { g.globalAlpha = .3 + .3 * Math.sin(s.p + t / 650); g.fillRect(s.x, s.y, s.r, s.r); }
    g.globalCompositeOperation = "lighter";
    if (!popped && t >= whole) pop(t);
    if (popped && t < whole + 650) {      // the flash as the words complete
      const f = 1 - (t - whole) / 650, gl = g.createRadialGradient(B.bx0 + BW / 2, B.by0 + BH / 2, 0, B.bx0 + BW / 2, B.by0 + BH / 2, BW * .75);
      gl.addColorStop(0, "rgba(255,255,255,.55)"); gl.addColorStop(.5, "rgba(170,200,255,.18)"); gl.addColorStop(1, "rgba(255,255,255,0)");
      g.globalAlpha = f; g.fillStyle = gl; g.fillRect(0, 0, W, H); g.fillStyle = "#FFFFFF";
    }
    for (const R of rockets) {      // each rocket climbs from below the screen, trailing sparks, and bursts where its letters are
      if (t < R.at || R.fired) continue;
      const u = Math.min(1, (t - R.at) / 650), at = q => { const e = 1 - Math.pow(1 - Math.max(0, q), 2.2); return [R.x0 + (R.G.cx - R.x0) * e, H + 12 + (R.G.cy - H - 12) * e]; };
      for (let k = 0; k < 7; k++) { const [x, y] = at(u - k * .035); g.globalAlpha = (1 - k / 7) * .85; g.drawImage(SPR[SILVER[0]], x - 5, y - 5, 10, 10); }
      if (u >= 1) { R.fired = true; explode(R, t); }
    }
    for (let i = parts.length - 1; i >= 0; i--) {
      const P = parts[i], age = t - P.born;
      if (P.tx != null) {      // a letter spark: out with the burst, then home to its place in the words
        let home = 0;
        if (age < 420) { P.x += P.vx * dt; P.y += P.vy * dt; P.vx *= .92; P.vy = P.vy * .92 + 40 * dt; P.hx = P.x; P.hy = P.y; }
        else { home = Math.min(1, (age - 420) / 950); const e = 1 - Math.pow(1 - home, 3); P.x = P.hx + (P.tx - P.hx) * e; P.y = P.hy + (P.ty - P.hy) * e; }
        let a = age < 420 ? 1 : (P.star ? .6 + .4 * Math.sin(P.tw + t / 90) : .72 + .28 * Math.sin(P.tw + t / 150));
        let wave = 0;
        if (P.flag && home > 0) {      // the flag flies: a ripple runs along it, lighter on the crests
          const ph = (P.tx - B.bx0) / (T.f1 * 2.4) * 6.283 - t / 320;
          wave = Math.sin(ph) * T.f1 * .05 * home;
          a *= .8 + .2 * Math.sin(ph + 1);
        }
        if (t > HOLD) { const f = Math.min(1, (t - HOLD) / FADE); a *= 1 - f; P.ty += 22 * dt * f; }
        if (t > HOLD + FADE) { parts.splice(i, 1); continue; }
        g.globalAlpha = a; g.drawImage(SPR[P.c], P.x - P.s / 2, P.y + wave - P.s / 2, P.s, P.s);
      } else {      // a loose spark: drifts down and fades
        const life = 1 - age / P.life; if (life <= 0) { parts.splice(i, 1); continue; }
        P.x += P.vx * dt; P.y += P.vy * dt; P.vx *= .985; P.vy = P.vy * .985 + 70 * dt;
        g.globalAlpha = life; g.drawImage(SPR[P.c], P.x - P.s / 2, P.y - P.s / 2, P.s, P.s);
      }
    }
    g.globalAlpha = 1;
    if (t < HOLD + FADE + 150) skyRaf = requestAnimationFrame(step); else closeSky();
  }
  skyRaf = requestAnimationFrame(step);
}
function closeSky(){
  cancelAnimationFrame(skyRaf); skyRaf = 0; skyOpen = false; sky.classList.remove("show"); SW && SW.classList.remove("charge");
  setTimeout(() => { if (!skyOpen) sky.hidden = true; }, 750);
}
/* the wormhole: rings and starlight rushing past, the page pulled into the middle; out the far side, the other space */
function tunnel(cv, dir, dur, done){
  const dpr = Math.min(2, devicePixelRatio || 1), W = innerWidth, H = innerHeight, g = cv.getContext("2d"), X = W / 2, Y = H * .44;
  cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr); g.setTransform(dpr, 0, 0, dpr, 0, 0);
  const stars = Array.from({length: 560}, () => ({a: Math.random() * 6.283, z: .05 + Math.random() * .95, w: Math.random()})), RINGS = 30, t0 = performance.now();
  let lastT = t0, phase = 0, stop = false;
  function frame(now){
    if (stop) return;
    const t = now - t0, p = Math.min(1, t / dur), dt = Math.min(40, now - lastT) / 1000; lastT = now;
    const speed = dir > 0 ? .12 + 2.4 * p * p : .05 + 2 * (1 - p) * (1 - p), A = dir > 0 ? Math.min(1, p * 2.2) : 1 - p;
    phase = (phase + speed * dt * .9) % (1 / RINGS);
    g.globalCompositeOperation = "source-over"; g.clearRect(0, 0, W, H);
    g.globalAlpha = dir > 0 ? Math.min(1, p * 1.7) : Math.max(0, 1 - p * 1.25); g.fillStyle = "#03040E"; g.fillRect(0, 0, W, H);
    g.globalCompositeOperation = "lighter";
    for (let k = 0; k < RINGS; k++) {      // rings at every depth, twisting, gold near and violet far
      const z = ((k / RINGS) + 1 / RINGS - phase) || .001; if (z <= .02) continue;
      const r = 26 / z, wob = (1 - z) * 16, cx = X + Math.cos(z * 9 + t / 260) * wob, cy = Y + Math.sin(z * 9 + t / 260) * wob * .7;
      g.globalAlpha = A * Math.min(1, (1 - z) * 1.3) * .75; g.lineWidth = .8 + 5 * (1 - z);
      g.strokeStyle = `hsl(${Math.round(265 - 225 * (1 - z))},95%,${Math.round(52 + 22 * (1 - z))}%)`;
      g.beginPath(); g.ellipse(cx, cy, r, r * .82, z * 2, 0, 6.283); g.stroke();
    }
    g.lineCap = "round";
    for (const s of stars) {      // starlight streaks, longer the faster we go
      s.z -= speed * dt * .55; if (s.z <= .02) { s.z = 1; s.a = Math.random() * 6.283; }
      const r1 = 14 / s.z, r2 = 14 / Math.min(1, s.z + speed * .045), c = Math.cos(s.a), n = Math.sin(s.a);
      g.globalAlpha = A * Math.min(1, (1 - s.z) * 1.6); g.strokeStyle = s.w > .7 ? "#FFE9A8" : (s.w > .4 ? "#CFE3FF" : "#FFFFFF"); g.lineWidth = .6 + 1.8 * (1 - s.z);
      g.beginPath(); g.moveTo(X + c * r2, Y + n * r2 * .82); g.lineTo(X + c * r1, Y + n * r1 * .82); g.stroke();
    }
    const glowR = 40 + (dir > 0 ? 520 * p * p : 260 * (1 - p)), core = g.createRadialGradient(X, Y, 0, X, Y, glowR);
    core.addColorStop(0, "rgba(255,255,255,.95)"); core.addColorStop(.25, "rgba(255,226,150,.55)"); core.addColorStop(1, "rgba(120,90,255,0)");
    g.globalAlpha = A * (dir > 0 ? .35 + .65 * p : .8); g.fillStyle = core; g.fillRect(0, 0, W, H);
    if (dir > 0 && p > .86) { g.globalCompositeOperation = "source-over"; g.globalAlpha = (p - .86) / .14; g.fillStyle = "#FFFFFF"; g.fillRect(0, 0, W, H); }
    g.globalAlpha = 1;
    if (p < 1) requestAnimationFrame(frame); else { stop = true; done && done(); }
  }
  requestAnimationFrame(frame);
  return () => { stop = true; };
}
function go(url){
  if (!url) return;
  if (going) { location.href = url; return; }      // a second click skips the ride
  going = true; clearTimeout(chargeT);
  try { sessionStorage.setItem("wormhole", "1"); } catch (e) {}
  if (calm()) { document.body.classList.add("fadeout"); setTimeout(() => { location.href = url; }, 220); return; }
  const wh = $("#wh"); wh.hidden = false; document.body.classList.add("pull"); sky.classList.add("pull");      // the words in the sky go down the wormhole too
  tunnel($("#whfx"), 1, 2000, () => { location.href = url; });
  wh.addEventListener("click", () => { location.href = url; }, {once: true});
}
if (SW) {
  SW.addEventListener("pointermove", e => {      // rest the pointer here for three seconds and the sky lights up; it takes a real
    if (e.pointerType !== "mouse" || calm() || !armed || skyOpen || going || SW.classList.contains("charge")) return;      // move onto the switch, so
    SW.classList.add("charge"); clearTimeout(chargeT); chargeT = setTimeout(fireworks, 3000);      // a pointer already resting there when the page opens sets nothing off
  });
  SW.addEventListener("pointerleave", () => { clearTimeout(chargeT); SW.classList.remove("charge"); if (!skyOpen) armed = true; });
  SW.addEventListener("click", e => { if (e.button || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return; e.preventDefault(); go(SW.href); });
}
sky.addEventListener("click", () => go(SW ? SW.href : ""));
sky.addEventListener("keydown", e => {
  if (e.key === "Escape") { e.preventDefault(); closeSky(); SW && SW.focus(); }
  else if (e.key === "Enter" || e.key === " ") { e.preventDefault(); go(SW ? SW.href : ""); }
});
(function emerge(){      /* arriving through the wormhole: the tunnel slows and the page opens out of its middle */
  let came = null; try { came = sessionStorage.getItem("wormhole"); sessionStorage.removeItem("wormhole"); } catch (e) {}
  if (!came || calm()) return;
  const wh = $("#wh"); wh.hidden = false; document.body.classList.add("arrive");
  tunnel($("#whfx"), -1, 1100, () => { wh.hidden = true; document.body.classList.remove("arrive"); });
})();
addEventListener("pageshow", e => { if (!e.persisted) return; going = false; document.body.classList.remove("pull", "fadeout", "arrive"); sky.classList.remove("pull"); $("#wh").hidden = true; if (skyOpen) closeSky(); });

place(); kick();
if (location.hash === "#states" && DOOR.map) showStates();
window.doorStats = () => ({angle, target, front, n: N, calm: calm(), turning: !$("#turn").hidden, view: $("#states").hidden ? "door" : "states"});
window.doorKick = () => { raf = 0; kick(); };      // for checking the ring in a window that is not on screen, where the browser never fires the first frame
</script>
</body>
</html>
"""


ELECTION_DAY = "2026-11-03"      # the next general election; the switch counts the days to it
BALLOT_DB = os.path.join(HERE, "ballot_2026.sqlite")
BALLOT_ICON = ('<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 12h16v8H4z"/><path d="M8 12V5h8v7"/>'
               '<path d="M10 8.6l1.5 1.5 2.8-2.9"/></svg>')
RECORD_ICON = ('<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3l8 4H4z"/><path d="M6 9v8M10 9v8M14 9v8M18 9v8"/>'
               '<path d="M3 20h18"/></svg>')
RED, WHITE, BLUE = "#FF3B3B", "#FFFFFF", "#3D7BFF"
SKY_BACK = [[["LEGISLATION", RED], ["&", WHITE]], [["LEGISLATURES", BLUE]]]      # the fireworks on the ballot door, for the way back


def switch(on):
    """The switch at the top middle names where it goes (John, 2026-09-29): On The Ballot on the front door; on the
    ballot door, Legislation & Legislatures, the way back. Both set off fireworks after three seconds' rest."""
    if on:
        href, label, text, icon = "../", "Legislation and Legislatures: back to the public record", "Legislation &amp; Legislatures", RECORD_ICON
    else:
        href, label, text, icon = "ballot/", "On The Ballot: who is on the ballot, race by race", "On The Ballot", BALLOT_ICON
    return (f'<a class="bsw{" on" if on else ""}" id="bsw" href="{href}" aria-label="{label}" title="{label}"><span class="trk">'
            f'<span class="knob">{icon}</span><span class="lbl">{text}</span></span><span class="when" id="bwhen"></span></a>')


def ballot_facts(db=BALLOT_DB):
    """What the On The Ballot space holds so far, counted from ballot_2026.sqlite."""
    if not os.path.exists(db):
        return {}
    con = sqlite3.connect(db)
    one = lambda q: con.execute(q).fetchone()[0]
    return {"races": one("SELECT COUNT(*) FROM races WHERE level = 'federal'"),
            "candidates": one("SELECT COUNT(*) FROM candidates c JOIN races r USING (race_id) WHERE r.level = 'federal' AND c.election = 'general'"),
            "states": one("SELECT COUNT(DISTINCT state) FROM ballot_sources WHERE level = 'federal'")}


def ballot_levels(B):
    """The On The Ballot door's cards: Congress first; the states and the local level are marked as coming."""
    return [
        {"key": "federal", "tag": "U.S. Congress", "title": "The House and the Senate",
         "text": "Every House and Senate race on the November 3 ballot: who is running, how they got there, and who funds them.",
         "facts": [[B.get("races"), "races"], [B.get("candidates"), "candidates listed"], [B.get("states"), "states' official lists"]],
         "go": "Step inside", "url": "us/", "under": "On the ballot: Congress"},
        {"key": "state", "tag": "State", "title": "Governors and legislatures",
         "text": "Races for governor, the state legislatures and the other statewide offices, state by state. They come after Congress.",
         "facts": [], "go": "Coming next", "soon": True},
        {"key": "local", "tag": "County and city", "title": "Closer to home",
         "text": "Sheriffs, county boards, mayors, councils and school boards, Minnesota first.", "facts": [], "go": "Coming later", "soon": True}]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True, help="where to write the page, for example site/dev/index.html")
    ap.add_argument("--db", default=os.path.join(HERE, "congress_119.sqlite"))
    ap.add_argument("--draft", action="store_true", help="show the work-in-progress strip the draft site carries")
    ap.add_argument("--ballot", action="store_true", help="write the On The Ballot door (site/dev/ballot/index.html) instead")
    args = ap.parse_args()
    log = read_changelog(os.path.join(HERE, "CHANGELOG.md"))
    version = (log[0].get("version") if log else "") or ""
    site_root = os.path.dirname(os.path.abspath(args.out))
    import datetime as dt
    if args.ballot:
        B = ballot_facts()
        data = {"space": "ballot", "election": ELECTION_DAY, "version": version, "levels": ballot_levels(B),
                "sky": SKY_BACK, "skyStyle": "flag", "whenText": "Back to the public record"}
        words = {"__TITLE__": "On The Ballot · The Civic Archive",
                 "__DESC__": "Who is on the ballot, race by race: every candidate the states have certified, the primaries that chose them, and who funds them.",
                 "__HOME__": "../", "__SWITCH__": switch(True), "__SKYLABEL__": "Legislation and Legislatures",
                 "__H1__": "Who&rsquo;s on the ballot, <em>race by race.</em>",
                 "__LEAD__": "Every candidate the states have certified for the November 3, 2026 general election, the primaries that chose them, "
                             "and the money behind them. Official lists only, loaded one state at a time. Pick a level of government.",
                 "__FOOTER__": f"On The Ballot, from The Civic Archive v{version}. Candidate lists from each state&rsquo;s election office; "
                               "campaign money from the Federal Election Commission."}
    else:
        data = {"federal": federal_facts(args.db), "states": [state_facts(code, site_root) for code in sorted(PLACES)],
                "map": {k: {"d": v["d"], "name": v["name"]} for k, v in state_paths(os.path.join(HERE, "us_states_albers.json")).items()},
                "version": version, "election": ELECTION_DAY}
        data["offmap"] = [o for o in OFF_MAP if o[0] not in data["map"]]      # the map file draws the District of Columbia; it does not draw the territories
        data["local"] = local_facts(site_root)
        words = {"__TITLE__": "The Civic Archive",
                 "__DESC__": "One shared place for the public record: every bill, every recorded vote, who represents you and who funds them. Federal and state.",
                 "__HOME__": "./", "__SWITCH__": switch(False) if os.path.exists(os.path.join(site_root, "ballot", "index.html")) else "",
                 "__SKYLABEL__": "On The Ballot",
                 "__H1__": "The public record, <em>for everyone.</em>",
                 "__LEAD__": "Every bill, every recorded vote, who represents you and who funds them, straight from official sources and written so you can follow it. Pick a level of government to step inside.",
                 "__FOOTER__": f"The Civic Archive v{version}. Built from public records: GovInfo, the House Clerk and the Senate, the Federal Election Commission, "
                               "the Census Bureau, the states' own agencies, the Open States project, and LegiScan."}
    wip = ('<div class="wip">WORK IN PROGRESS &mdash; this is a draft for feedback, not the real site. '
           '<a href="https://thecivicarchive.github.io/">Go to the live site</a></div>') if args.draft else ""
    html = PAGE.replace("__DATA__", json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/"))
    for key, value in words.items():
        html = html.replace(key, value)
    html = html.replace("__VERSION__", version).replace("__WIP__", wip).replace("__GENERATED__", dt.datetime.now().strftime("%B %d, %Y"))
    os.makedirs(site_root, exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(html)
    if args.ballot:
        print(f"Wrote {args.out}: the On The Ballot door, {len(html.encode('utf-8')) / 1e3:,.0f} KB; {ballot_facts() or 'no ballot database yet'}")
        return
    print(f"Wrote {args.out}: the front door, {len(html.encode('utf-8')) / 1e3:,.0f} KB; federal {data['federal']}; "
          + ("the On The Ballot switch; " if words["__SWITCH__"] else "no ballot space yet, so no switch; ")
          + "; ".join(f"{s['name']} {'open' if s['live'] else 'being built'} ({', '.join(s['loaded']) or 'nothing yet'})" for s in data["states"]))


if __name__ == "__main__":
    main()
