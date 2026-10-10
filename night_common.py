#!/usr/bin/env python3
"""
night_common.py - what Election Night's inner pages share (a state's page now; the US page, the feed and the forecasts
later): the parts they borrow from the rest of the site by landmark, the Night stylesheet and script pieces, the results
kit the ballot map is given, the head and footer of a page, the checks every builder runs, and the one account of the
live figures' files that the pages read and the updater writes.

Nothing here downloads anything or writes anything by itself; the builders call it.

Borrowed, never copied by hand (the build stops and names a landmark that moved):
  - the site's stylesheet, the changelog badge and the sortable table from the federal page (build_state_dev.borrow);
  - the ballot pages' stylesheet and the source folds from the Congress ballot page (build_ballot_state_dev.borrow_ballot);
  - the ballot map (BallotMap) from the start of build_ballot_state_dev.MAPKIT up to the landmark where its page-only part
    begins. BallotMap carries one hook for this space, under the landmark "results paint (Election Night)": a page that
    passes opt.paint is handed a kit to fill shapes with; the ballot pages pass none and draw as before.

THE LIVE FIGURES (the contract between the updater, which writes them, and the pages, which read them)

Published beside the draft as /night-live/ (site/night-live/ on this computer; practice figures in site/practice/night-live/,
rehearsals in <live>/rehearsal/). A page asks for now.json, then only the files it shows, all from the same snapshot.
The state and county files are the results store's own (election/store.py: page_json and county_json); a page reads them
as they are and turns them into its own shape (normState and normCounty in NIGHT_JS below).

  now.json        the only file at a fixed address (at most 4 KB), the updater's
    {"v": 1, "seq": 184, "at": "<UTC>", "next": "<UTC>", "run": "running" | "paused" | "stopped", "rehearsal": false,
     "practice": false, "label": "<what a rehearsal or practice replays>", "base": "s/000184/",
     "st": {"MN": {"s": "<status word>", "t": "<UTC of the state's figures>", "f": "mn.json", "by": "hand" | "feed"}, ...}}
    Status words: wait (polls open), none (no votes yet), counting, done (every unit in, not certified), official
    (certified), held (the state's file changed; last good figures shown), stale (the source has not answered), link (not
    read here), refused.

  <base><code>.json   a state's figures, every race its file carries (store.page_json, written short by store.compact_page;
  store.expand_page reads it back, as normState does on the page)
    {"v": 1, "state": "MN", "at": "<UTC: the newest good file's time; for a state saved by hand, when it was saved>",
     "pre": "2026-MN-" (the start every race id shares, left off the keys of r),
     "r": {"<race id less pre>": {"t": "<UTC of the race's newest figure>" (left off when it is "at"),
                        "p": [units in, units in all],
                        "ch": [[choice key, name as printed, party as printed, 1 for a write-in line, name as filed on the
                                list], ...]   written short: the key "" when it is the name made into a key; the name as
                                filed left off when it is the name as printed (or, on a write-in line, when there is none),
                                0 when the line is tied to no candidate on the list; then the write-in mark left off when
                                0 and the party when there is none,
                        "v": [votes, one for each line of ch, in its order],
                        "off": 1 once certified,
                        "k": {"<county unit: state FIPS + county FIPS, 27053>": [in, all, votes in ch order ...]} (by
                              county, where the state's file gives county lines)}}}
    A page matches each line of ch to a candidate on its own list (data/races.json) by the name as filed (else the name
    as printed), letters and digits only, case set aside; a line whose name as filed is 0 is shown as printed, as is a
    line that matches nobody; a write-in line's votes are the race's write-ins. Optional, read when present: "s" (the
    status word) and "units" ([in, all] for the whole state; else the race that reaches the most units).

  <base><code>/c/<county unit>.json and <base><code>/c/<county unit>-court.json   one county's precinct rows (store.
  county_json; the name from store.county_file), for a state whose file reports by precinct, in two files: the judges'
  contests in -court, every other contest in the first. The county unit is the five-digit county FIPS code everywhere
  (the store's county units, the keys of k, these file names): "27053", never "053".
    {"v": 1, "county": "27053", "part": "" or "court", "at": "<UTC>", "u": [every precinct id of the county],
     "races": [race ids], "r": [[[reported precincts, by their place in u, as runs: 4 or [4, 9]], [votes: the race's
     ch lines for the first reported precinct, then the next ...]], ...]}      (one entry per race, in the order of races)
    A precinct not listed for a race has not reported. Every county has both files in every snapshot (store.
    county_units), so that a page can tell "none in yet" from a file it could not fetch.

The race ids are the ballot databases' own; a precinct id is the map's own (Minnesota: the VTDID).
check_state_live() and check_county_live() test the files against this account.
"""

import datetime as dt
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

FORMAT_VERSION = 1
STATUS = ("wait", "none", "counting", "done", "official", "held", "stale", "link", "refused")

# The landmark in the ballot map where Election Night's paint hook sits, and the one where the ballot page's own part of
# the map's script begins (that part uses the ballot page's globals and is never taken).
PAINT_LANDMARK = "/* ---------- results paint (Election Night) ---------- */"
GEOKIT_LANDMARK = '/* ---------- the map set into the page\'s "your ballot"'

# The names a public page must not carry: the kit's programs and databases (the same test build_home.py makes).
KIT_NAMES = re.compile(r"\b[a-z]+(?:_[a-z0-9]+)+\.py\b|\b[\w-]+\.sqlite\b|\brubric_v1\b")
# Words the results never use before certification (ARCHITECTURE.md 4.6).
NEVER_WORDS = re.compile(r"\b(?:projected|projection|called|wins|will win|victory|winner)\b", re.I)


# ============================================================ borrowing

def parts():
    """The pieces every inner page borrows, each by landmark: {name: text}."""
    from build_state_dev import borrow
    from build_ballot_state_dev import borrow_ballot
    return {"CSS": borrow("CSS"), "CHANGELOG": borrow("CHANGELOG"), "GRID": borrow("GRID"),
            "BALLOT_CSS": borrow_ballot("BALLOT_CSS"), "SOURCEFOLD": borrow_ballot("SOURCEFOLD")}


def ballot_map():
    """BallotMap alone: the ballot map's script from its start up to the landmark where the ballot page's own part begins.
    The paint hook must be in it, or the results could not be drawn."""
    from build_ballot_state_dev import MAPKIT
    if MAPKIT.count(GEOKIT_LANDMARK) != 1:
        raise SystemExit(f"night_common: the ballot map's script (build_ballot_state_dev.MAPKIT) no longer has exactly one '{GEOKIT_LANDMARK}' "
                         f"(it has {MAPKIT.count(GEOKIT_LANDMARK)}). Election Night takes the map up to that landmark; update GEOKIT_LANDMARK.")
    part = MAPKIT[:MAPKIT.index(GEOKIT_LANDMARK)]
    if part.count(PAINT_LANDMARK) != 1 or "opt.paint(paintKit(" not in part:
        raise SystemExit(f"night_common: the ballot map no longer carries the paint hook under '{PAINT_LANDMARK}'. Election Night's results "
                         "are drawn through it; put it back in build_ballot_state_dev.MAPKIT's draw().")
    return part.rstrip() + "\n"


def mapkit(extra=""):
    """The map's script written beside a Night page: BallotMap, then the Night results kit, then a page's own map part."""
    return ballot_map() + "\n" + NIGHTMAP_JS + ("\n" + extra if extra else "")


# ============================================================ places, files and checks

def practice_root(dev_root):
    """Where a practice build goes: site/practice beside site/dev. No publish script copies it."""
    return os.path.join(os.path.dirname(os.path.abspath(dev_root)), "practice")


def sha10(text):
    return hashlib.sha1(text.encode("utf-8") if isinstance(text, str) else text).hexdigest()[:10]


def kit_names(text):
    """The kit's file names a page would show (none is allowed)."""
    return sorted(set(KIT_NAMES.findall(text)))


def quiet(text):
    """The last pass every published page gets (quiet_pages.py), run here too, so that what is checked is what is shipped."""
    import quiet_pages
    return quiet_pages.quiet(text)[0]


def page_checks(name, text, limit=None, say=print):
    """The checks every Night builder runs on a finished page: no kit names, none of the words the results never use, and
    the size limit. Stops the build on a kit name; reports the rest."""
    bad = kit_names(text)
    if bad:
        raise SystemExit(f"night_common: {name} names the kit's own files: {bad}")
    # the whole page, its script included: a Night page writes most of its words from its script
    words = sorted(set(m.group(0).lower() for m in NEVER_WORDS.finditer(re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.S | re.I))))
    size = len(text.encode("utf-8"))
    if words:
        say(f"  WARNING: {name} uses words the results never use: {words}")
    if limit and size > limit:
        say(f"  WARNING: {name} is {size / 1e3:,.0f} KB, over its {limit / 1e3:,.0f} KB budget")
    return {"bytes": size, "never_words": words}


def _pair(p):
    return isinstance(p, list) and len(p) == 2 and all(isinstance(x, int) or x is None for x in p) and (p[0] or 0) <= (p[1] if p[1] is not None else 10 ** 9)


def check_state_live(doc, races=None):
    """Problems with a state's figures file against the account above (an empty list when it is sound). races: the page's
    own races ({id: [names on the list]}), to check that every race is the page's and every named line matches a candidate."""
    from election.store import expand_page
    out = []
    if not isinstance(doc, dict) or doc.get("v") != FORMAT_VERSION:
        return ["not a version 1 state file"]
    if doc.get("s") is not None and doc.get("s") not in STATUS:
        out.append(f"status word {doc.get('s')!r} is not one of {STATUS}")
    for key in ("state", "at", "r"):
        if key not in doc:
            out.append(f"no {key}")
    for k, e in (doc.get("r") or {}).items():
        if not (isinstance(e, dict) and isinstance(e.get("ch"), list) and all(isinstance(c, list) and 2 <= len(c) <= 5 for c in e["ch"])):
            out.append(f"{k}: no list of lines (ch) of two to five items")
        elif not all(isinstance(ce, list) and len(ce) >= 2 for ce in (e.get("k") or {}).values()):
            out.append(f"{k}: a county's figures are not [in, all, votes ...]")
    if out:
        return out
    doc = expand_page(doc)
    key = lambda s: " ".join(re.sub(r"[^a-z0-9]+", " ", str(s or "").lower()).split())
    for rid, e in (doc.get("r") or {}).items():
        ch, v = e.get("ch"), e.get("v")
        if "p" in e and not _pair(e["p"]):
            out.append(f"{rid}: units {e['p']!r} are not [in, all] with in <= all")
        if not (isinstance(v, list) and len(v) == len(ch) and all(isinstance(x, int) and x >= 0 for x in v)):
            out.append(f"{rid}: votes do not line up with the lines")
        for cu, ce in (e.get("k") or {}).items():
            if not re.fullmatch(r"\d{5}", str(cu)) or len(ce.get("v") or []) != len(ch) or ("p" in ce and ce["p"] is not None and not _pair(ce["p"])):
                out.append(f"{rid}: county {cu} does not line up")
        if races is not None:
            if rid not in races:
                out.append(f"{rid}: no such race on the page")
            else:
                names = {key(n) for n in races[rid]}
                # a line the store tied to a candidate (its name as filed) must be on the page's list; a line tied to
                # nobody is shown as printed
                lost = [c[1] for c in ch if not c[3] and c[4] is not None and key(c[4]) not in names]
                if lost:
                    out.append(f"{rid}: {len(lost)} line(s) match no candidate on the list")
    return out


def check_county_live(doc, lines=None, races=None):
    """Problems with one of a county's precinct files (store.county_json) against the account above. lines: {race id: its
    number of lines in the state's file}, to check each race's votes are its lines for each reported precinct; races: the
    page's races ({id: level}), to check that each race is in the file its level says."""
    from election.store import COUNTY_PARTS, county_part
    out = []
    if not isinstance(doc, dict) or doc.get("v") != FORMAT_VERSION or not isinstance(doc.get("races"), list) \
            or not isinstance(doc.get("u"), list) or not isinstance(doc.get("r"), list) or len(doc["r"]) != len(doc["races"]):
        return ["not a version 1 county file"]
    if not re.fullmatch(r"\d{5}", str(doc.get("county"))) or doc.get("part") not in COUNTY_PARTS:
        out.append(f"county {doc.get('county')!r}, part {doc.get('part')!r}: not a five-digit county unit and a known part")
    for rid, entry in zip(doc["races"], doc["r"]):
        if races is not None and county_part(races.get(rid)) != doc.get("part"):
            out.append(f"{rid}: in the {doc.get('part') or 'main'} file, but its level is {races.get(rid)!r}")
        if not (isinstance(entry, list) and len(entry) == 2 and isinstance(entry[0], list) and isinstance(entry[1], list)):
            out.append(f"{rid}: not [precincts, votes]")
            continue
        idx = []
        for x in entry[0]:
            if isinstance(x, list) and len(x) == 2 and isinstance(x[0], int) and isinstance(x[1], int) and 0 <= x[0] < x[1]:
                idx.extend(range(x[0], x[1] + 1))
            elif isinstance(x, int):
                idx.append(x)
            else:
                idx = None
                break
        if idx is None or idx != sorted(set(idx)) or (idx and (idx[0] < 0 or idx[-1] >= len(doc["u"]))):
            out.append(f"{rid}: the precincts are not runs of places in the list, in order")
            continue
        n = (lines or {}).get(rid)
        if n and len(entry[1]) != n * len(idx):
            out.append(f"{rid}: {len(entry[1])} figures for {len(idx)} precincts of {n} lines")
        if not all(isinstance(v, int) and v >= 0 for v in entry[1]):
            out.append(f"{rid}: a figure that is not a whole number")
    return out


# ============================================================ the head, the top bar, the footer

def head_script():
    """Before the first frame: the reader's theme, contrast, colour-vision palette and Calm, from the choices the rest of
    the site keeps on this device (the home page's reading and access settings, and the older theme and motion
    switches); on a first visit, the device's own wish for more contrast or less motion. The newer choice wins and high
    contrast is never undone, as on every other page."""
    return ('<script>(function(){var d=document.documentElement,g=function(k){try{return localStorage.getItem(k)}catch(e){return null}},'
            'm=function(q){try{return matchMedia(q).matches}catch(e){return false}},a=null;try{a=JSON.parse(g("tca.a11y.v1")||"null")}catch(e){a=null}'
            'a=a&&typeof a==="object"?a:{};var c=["standard","high","dark"].indexOf(a.contrast)>=0?a.contrast:(m("(prefers-contrast: more)")?"high":"standard"),'
            't=g("theme"),mo=g("motion");if(t==="dark"&&c==="standard")c="dark";if(t==="light"&&c==="dark")c="standard";'
            'd.dataset.theme=c==="dark"?"dark":"light";d.setAttribute("data-contrast",c);'
            'd.setAttribute("data-palette",["deut","prot","trit","mono"].indexOf(a.palette)>=0?a.palette:"standard");'
            'd.setAttribute("data-calm",a.calm==="on"?"on":"off");'
            'var calm=a.calm==="on"||mo==="off"||(mo!=="on"&&(a.motion==="reduced"||(!a.motion&&m("(prefers-reduced-motion: reduce)"))));'
            'if(calm)d.classList.add("calm")})()</script>')


def fonts_css():
    return ('@font-face{font-family:"Instrument Serif";font-style:normal;font-weight:400;font-display:swap;src:url(fonts/InstrumentSerif-Regular.ttf) format("truetype")}\n'
            '@font-face{font-family:"Instrument Serif";font-style:italic;font-weight:400;font-display:swap;src:url(fonts/InstrumentSerif-Italic.ttf) format("truetype")}\n'
            '@font-face{font-family:"Instrument Sans";font-style:normal;font-weight:400 700;font-display:swap;src:url(fonts/InstrumentSans-Variable.ttf) format("truetype")}')


def brand_tags(icons_root, title, desc, card, path):
    """The emblem's icons and the share tags (brand.head_tags). card: the section's share image under night/og/, made by
    the Night home's builder; path: this page's address below the draft's root."""
    import brand
    from build_shell import BASE_URL
    return brand.head_tags(icons_root, BASE_URL, title, desc, f"{BASE_URL}/night/og/{card}", f"{BASE_URL}/{path}")


NIGHT_MARK = ('<svg class="mark" viewBox="0 0 28 28" aria-hidden="true"><path d="M14 3v2.5"/><path d="M6.5 13.5a7.5 7.5 0 0 1 15 0"/>'
              '<path d="M4 13.5h20"/><path d="M6.5 16.5v6M11.5 16.5v6M16.5 16.5v6M21.5 16.5v6"/><path d="M3 24h22"/></svg>')
MOON = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20.5 14.2A8.5 8.5 0 1 1 9.8 3.5a6.6 6.6 0 0 0 10.7 10.7z"/></svg>'


def top_bar(home_title, nav_html, door_href="../", door_label="Election Night"):
    """A Night inner page's own top bar, as the ballot pages have theirs: the way back to the Night home, the site's name,
    the page's sections, and the two switches every page keeps (motion, light or dark)."""
    return f"""<header class="top">
  <div class="wrap">
    <a class="doorlink" href="{door_href}" title="{door_label}: every state" aria-label="Back to {door_label}">{MOON}<span>{door_label}</span></a>
    <a class="brand" href="#" aria-label="{home_title}, home">{NIGHT_MARK}<span class="wm"><b>T</b>he <b>C</b>ivic <b>A</b>rchive</span></a>
    <nav class="nav" aria-label="Sections">{nav_html}</nav>
    <div class="tools">
      <button class="mtog" id="motion" aria-pressed="true" title="Page motion: on or off"><span class="sw" aria-hidden="true"><i></i></span><span class="lab">Motion</span></button>
      <button class="iconbtn" id="theme" aria-label="Switch between light and dark" title="Light / dark">
        <svg class="moon" viewBox="0 0 24 24" aria-hidden="true"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>
        <svg class="sun" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>
      </button>
    </div>
  </div>
</header>"""


def changelog_box():
    return """<div class="cl" id="cl" hidden>
  <button class="cl-tab" id="cltab" aria-expanded="false" aria-controls="clpanel"><span class="cl-dot" aria-hidden="true"></span><span class="cl-v" id="clv">v1</span><span class="cl-w">What&rsquo;s new</span></button>
  <div class="cl-panel" id="clpanel" hidden><div class="cl-head"><b>What&rsquo;s changed</b><button class="cl-x" id="clx" aria-label="Close">&times;</button></div><div class="cl-body" id="clbody"></div></div>
</div>"""


def generated():
    d = dt.date.today()
    return f"{d:%B} {d.day}, {d.year}"


# ============================================================ the Night stylesheet

# What every Night page adds to the site's and the ballot pages' look. Red and blue stay the parties' (the ballot pages'
# --pD and --pR); everything else is verdigris, brass, ink and greys. A nonpartisan race's candidates take the neutral
# tones --n1 to --n6 in ballot order. Under a colour-vision palette, Calm or high contrast, fills also carry patterns.
NIGHT_CSS = r"""
:root{--n1:#2F6B5E;--n2:#A8762E;--n3:#6B7A2E;--n4:#7A5A44;--n5:#3D9A7C;--n6:#B8964F;--nstripe:rgba(255,255,255,.62);--hatch-ink:#8A8F96;
  --st-live:#2F6B5E;--st-hold:#A8762E;--brass:#A8762E;--brass-soft:#F3E8D3;--verd:#2F6B5E;--verd-soft:#E2EDE8}
:root[data-theme="dark"]{--n1:#6DBBA8;--n2:#D9A657;--n3:#A9BA62;--n4:#C29A7E;--n5:#5FD0AA;--n6:#E2C784;--nstripe:rgba(15,17,20,.55);--hatch-ink:#7B828C;
  --st-live:#6DBBA8;--st-hold:#C9944A;--brass:#C9944A;--brass-soft:#2F2618;--verd:#6DBBA8;--verd-soft:#1B302B}
/* high contrast: the site's own tokens set to black on white (the shell's high-contrast look), the parties' colours deepened */
:root[data-contrast="high"]{--bg:#FFFFFF;--surface:#FFFFFF;--ink:#000000;--muted:#1F1F1F;--line:#000000;--line-strong:#000000;--hair:#000000;
  --accent:#000000;--accent-ink:#000000;--accent-soft:#FFFFFF;--accent-line:#000000;--gold:#000000;--gold-ink:#000000;
  --pD:#1238B8;--pR:#A51E16;--pI:#4F3594;--pL:#6B4E00;--pG:#14592A;--pO:#2E3238;--pW:#3B3F45;--pN:#2E3238;
  --n1:#174F44;--n2:#6E4A10;--n3:#3E4A10;--n4:#4A3324;--n5:#0F5F47;--n6:#6B5410;--nstripe:rgba(255,255,255,.75);--hatch-ink:#000000;
  --st-live:#000000;--st-hold:#000000;--brass:#000000;--brass-soft:#FFFFFF;--verd:#000000;--verd-soft:#FFFFFF;color-scheme:light}
:root[data-contrast="high"] .top{border-bottom:2px solid #000}
:root[data-contrast="high"] .ln .nbar{background:#fff;box-shadow:inset 0 0 0 1px #000}
:root[data-contrast="high"] .res,:root[data-contrast="high"] .nrow,:root[data-contrast="high"] .mapcol,:root[data-contrast="high"] .mapside,
:root[data-contrast="high"] .nstat,:root[data-contrast="high"] .lvcard,:root[data-contrast="high"] .scard2{border-width:2px;border-color:#000}
html,body{overflow-x:hidden}
#app:focus{outline:none}
.sr{position:absolute;width:1px;height:1px;margin:-1px;padding:0;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap;border:0}
@media (max-width:900px){.nav a.x{display:none}}
@media (max-width:760px){.top .wrap{flex-wrap:wrap;height:auto;min-height:62px;row-gap:0}
  .top .nav{display:flex;order:9;flex:0 0 100%;min-width:0;margin:0 -4px;padding:0 0 7px;gap:2px;overflow-x:auto;-webkit-overflow-scrolling:touch;scrollbar-width:none}
  .top .nav::-webkit-scrollbar{display:none}
  .top .nav a,.top .nav a.x{display:block;flex:0 0 auto;padding:7px 10px;font-size:14px}}
.bhero h1{overflow-wrap:break-word}
/* practice and rehearsal figures say so on every page, before anything else */
.nbanner{background:var(--brass-soft);color:var(--ink);border-bottom:2px solid var(--brass);padding:9px 16px;font:600 14px/1.4 var(--sans);text-align:center}
.nbanner b{font-weight:800}
/* the state of the count: a word, the time, how the state counts */
.nstat{display:flex;gap:10px 14px;align-items:flex-start;flex-wrap:wrap;border:1px solid var(--line);background:var(--surface);border-radius:16px;padding:12px 16px;margin-top:16px;max-width:96ch}
.nstat p{margin:0;font-size:14.5px;line-height:1.5;flex:1 1 280px;min-width:0}
.nstat small{display:block;color:var(--muted);font-size:13px;margin-top:3px}
.stw{display:inline-flex;align-items:center;gap:7px;flex:none;font:700 12px var(--sans);letter-spacing:.08em;text-transform:uppercase;border-radius:999px;padding:5px 11px;border:1px solid var(--line-strong);color:var(--muted)}
.stw i{width:8px;height:8px;border-radius:50%;background:currentColor}
.stw.counting{color:var(--st-live);border-color:var(--st-live)}.stw.done,.stw.official{color:var(--ink);border-color:var(--ink)}
.stw.held,.stw.stale,.stw.refused{color:var(--st-hold);border-color:var(--st-hold)}
:root:not(.calm) .stw.counting i{animation:npulse 2.4s ease-in-out infinite}
@keyframes npulse{50%{opacity:.25}}
/* polls still open (John's words): before anything else on the page */
.pollsopen{border:1px solid var(--line);border-left:5px solid var(--verd);background:var(--surface);border-radius:14px;padding:12px 16px;margin-top:16px;max-width:96ch;font-size:15px;line-height:1.5}
.pollsopen b{display:block;font-size:16px}
.pollsopen a{color:var(--accent-ink);font-weight:700}
/* chips: Fact for an official count; Analysis for an estimate or a measure */
.tag.fact,.tag.analysis{display:inline-flex;align-items:center;height:20px;padding:0 8px;border-radius:999px;font:700 10.5px var(--sans);letter-spacing:.08em;text-transform:uppercase;vertical-align:1px}
.tag.fact{background:var(--verd-soft);color:var(--ink);border:1px solid var(--verd)}
.tag.analysis{background:var(--brass-soft);color:var(--ink);border:1px solid var(--brass)}
.asof{font-size:12.5px;color:var(--muted);margin:8px 0 0;line-height:1.45}
.asof b{color:var(--ink);font-weight:600}
/* a result: one line a candidate, a bar of the share, the share and the votes */
.res{border:1px solid var(--line);background:var(--surface);border-radius:18px;padding:14px 16px;min-width:0}
.res h3{font-family:var(--serif);font-weight:400;font-size:clamp(22px,2.6vw,28px);line-height:1.08;margin:0;overflow-wrap:anywhere}
.res h3 a{color:inherit;text-decoration:none}.res h3 a:hover{text-decoration:underline}
.res .where{font-size:13px;color:var(--muted);margin:3px 0 0}
.res .nrep{font-size:13px;color:var(--muted);margin:8px 0 0}
.res .nrep b{color:var(--ink)}
.lns{display:grid;gap:7px;margin-top:10px}
.ln{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:2px 12px;align-items:baseline;font-size:14px}
.ln .nm{min-width:0;overflow-wrap:anywhere;font-weight:600}
.ln .nm small{font-weight:400;color:var(--muted);margin-left:1px;white-space:nowrap}
.ln .fig{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.ln .fig b{font-weight:700}.ln .fig span{color:var(--muted);margin-left:8px;font-size:13px}
.ln .nbar{display:block;grid-column:1/-1;height:9px;border-radius:5px;background:var(--line);overflow:hidden}
.ln .nbar i{display:block;height:100%;border-radius:5px;background:var(--c,var(--muted));min-width:0}
.ln .badge{display:inline-block;margin-left:4px;font:700 10px/1.5 var(--sans);font-style:normal;letter-spacing:.06em;text-transform:uppercase;color:var(--ink);border:1px solid var(--line-strong);border-radius:999px;padding:0 7px;vertical-align:2px;white-space:nowrap}
.ln .badge.el{color:var(--bg);background:var(--ink);border-color:var(--ink)}
.ln.wl .nm{font-weight:400;color:var(--muted)}
.nsw{display:inline-block;width:10px;height:10px;border-radius:3px;background:var(--c,var(--muted));margin-right:7px;vertical-align:0;flex:none}
.res .one{font-size:12.5px;color:var(--muted);margin:8px 0 0}
.res .rfoot{display:flex;gap:6px 12px;flex-wrap:wrap;align-items:center;margin-top:10px;font-size:12.5px;color:var(--muted)}
.res .rfoot a{color:var(--accent-ink)}
.res.small h3{font-family:var(--sans);font-weight:700;font-size:15.5px;line-height:1.25}
/* patterns on top of colour, where the reader's settings ask for them (a colour-vision palette, Calm, high contrast) */
:root:is([data-palette="deut"],[data-palette="prot"],[data-palette="trit"],[data-palette="mono"],[data-calm="on"],[data-contrast="high"]) :is(.nbar i,.nsw,.lgsw)[data-p="hatch"]{background-image:repeating-linear-gradient(45deg,var(--nstripe) 0 2px,transparent 2px 6px)}
:root:is([data-palette="deut"],[data-palette="prot"],[data-palette="trit"],[data-palette="mono"],[data-calm="on"],[data-contrast="high"]) :is(.nbar i,.nsw,.lgsw)[data-p="back"]{background-image:repeating-linear-gradient(135deg,var(--nstripe) 0 2px,transparent 2px 6px)}
:root:is([data-palette="deut"],[data-palette="prot"],[data-palette="trit"],[data-palette="mono"],[data-calm="on"],[data-contrast="high"]) :is(.nbar i,.nsw,.lgsw)[data-p="cross"]{background-image:repeating-linear-gradient(45deg,var(--nstripe) 0 2px,transparent 2px 6px),repeating-linear-gradient(135deg,var(--nstripe) 0 2px,transparent 2px 6px)}
:root:is([data-palette="deut"],[data-palette="prot"],[data-palette="trit"],[data-palette="mono"],[data-calm="on"],[data-contrast="high"]) :is(.nbar i,.nsw,.lgsw)[data-p="dots"]{background-image:radial-gradient(var(--nstripe) 1.3px,transparent 1.6px);background-size:5px 5px}
:root:is([data-palette="deut"],[data-palette="prot"],[data-palette="trit"],[data-palette="mono"],[data-calm="on"],[data-contrast="high"]) :is(.nbar i,.nsw,.lgsw)[data-p="rows"]{background-image:repeating-linear-gradient(0deg,var(--nstripe) 0 2px,transparent 2px 5px)}
:root:is([data-palette="deut"],[data-palette="prot"],[data-palette="trit"],[data-palette="mono"],[data-calm="on"],[data-contrast="high"]) :is(.nbar i,.nsw,.lgsw)[data-p="cols"]{background-image:repeating-linear-gradient(90deg,var(--nstripe) 0 2px,transparent 2px 5px)}
/* a compact row: one race, who is ahead, how much is in */
.nrows{display:grid;gap:8px;margin-top:12px}
.nrow{display:grid;grid-template-columns:minmax(0,1.3fr) minmax(0,1fr) auto;gap:6px 14px;align-items:center;text-decoration:none;color:inherit;border:1px solid var(--line);background:var(--surface);border-radius:14px;padding:10px 14px;min-height:44px}
.nrow:hover{border-color:var(--line-strong)}
.nrow:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.nrow .t{font-weight:700;font-size:14px;min-width:0;overflow-wrap:anywhere}.nrow .t small{display:block;font-weight:400;color:var(--muted);font-size:12.5px;margin-top:1px}
.nrow .l{font-size:13.5px;min-width:0;overflow-wrap:anywhere}.nrow .l b{font-weight:700}.nrow .l small{display:block;color:var(--muted);font-size:12px}
.nrow .u{font-size:12.5px;color:var(--muted);text-align:right;white-space:nowrap}
.nrow .nmine{grid-column:1/-1;order:4;font-size:13px;border-top:1px dashed var(--line);padding-top:6px;margin-top:2px;overflow-wrap:anywhere}
.nrow .nmine b{font-weight:700}
@media (max-width:640px){.nrow{grid-template-columns:minmax(0,1fr) auto}.nrow .l{grid-column:1/-1;order:3}}
.rgrid2{display:grid;gap:12px;grid-template-columns:repeat(auto-fill,minmax(min(100%,340px),1fr));margin-top:14px}
details.nfold>summary{cursor:pointer;font:600 14.5px var(--sans);color:var(--accent-ink);min-height:44px;display:flex;align-items:center;max-width:96ch}
details.nfold>summary:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.lvl{margin-top:22px}.lvl>h3{font:700 12px var(--sans);letter-spacing:.12em;text-transform:uppercase;color:var(--accent);margin:0}
.lvl>p{font-size:13.5px;color:var(--muted);margin:6px 0 0;max-width:90ch}
.lvl .grp{margin-top:14px}.lvl .grp h4{font:700 15px var(--sans);margin:0}
.lvgrid{display:grid;gap:12px;grid-template-columns:repeat(auto-fill,minmax(min(100%,230px),1fr));margin-top:14px}
.lvcard{display:block;text-decoration:none;color:inherit;border:1px solid var(--line);background:var(--surface);border-radius:18px;padding:14px 16px;min-height:44px}
.lvcard:hover{border-color:var(--line-strong)}
.lvcard b{display:block;font-family:var(--serif);font-weight:400;font-size:26px;line-height:1.05}.lvcard span{display:block;font-size:13px;color:var(--muted);margin-top:6px}
.lvcard .go{color:var(--accent-ink);font-weight:700;font-size:13.5px;margin-top:10px}
/* the map, with its legend */
.nmapgrid{margin-top:14px}
.nmap{position:relative;height:clamp(320px,60vh,600px);border-radius:14px;overflow:hidden;background:var(--bg);touch-action:pan-y;user-select:none;-webkit-user-select:none;cursor:pointer}
.nmap.zoomed{touch-action:none;cursor:grab}.nmap.drag{cursor:grabbing}
.nmap:focus{outline:none}.nmap:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.nmap canvas{position:absolute;inset:0;width:100%;height:100%;display:block}
.nmap .gtiles{position:absolute;inset:0;overflow:hidden;background:#e9e6df}
.nmap:not(.streets) .gtiles{display:none}
.nmap .gtiles img{position:absolute;left:0;top:0;max-width:none;transform-origin:0 0;pointer-events:none}
.nmap .gpin{position:absolute;left:0;top:0;width:26px;height:34px;margin:-33px 0 0 -13px;pointer-events:none;filter:drop-shadow(0 3px 3px rgba(0,0,0,.35))}
.nmap .gpin[hidden]{display:none}
.nmap .gpin svg{display:block;width:26px;height:34px}.nmap .gpin path{fill:var(--ink);stroke:var(--bg);stroke-width:1.6}.nmap .gpin circle{fill:var(--bg)}
.nmap .gattr{position:absolute;right:6px;bottom:6px;font:600 11px var(--sans);color:#14171c;background:rgba(255,255,255,.88);padding:2px 7px;border-radius:6px;text-decoration:underline}
.nmap .gattr[hidden],.nmap .gbusy[hidden]{display:none}
.nmap .gbusy{position:absolute;left:8px;bottom:8px;font:600 11.5px var(--sans);color:var(--ink);background:var(--surface);border:1px solid var(--line);padding:3px 9px;border-radius:999px}
.mapbar .pick{flex:1 1 220px;min-width:0}
.zoom button{min-width:38px;height:38px}
.zoom button svg{width:15px;height:15px;fill:none;stroke:currentColor;stroke-width:2}
.zoom button[hidden]{display:none}
.nlegend{display:flex;flex-wrap:wrap;gap:6px 14px;margin:10px 2px 0;font-size:12.5px;color:var(--muted);align-items:center}
.nlegend span{display:inline-flex;align-items:center;gap:6px;min-width:0}
.lgsw{display:inline-block;width:14px;height:14px;border-radius:4px;background:var(--c,var(--muted));flex:none;border:1px solid var(--line)}
.lgsw.wait{background:repeating-linear-gradient(45deg,var(--hatch-ink) 0 1.5px,transparent 1.5px 5px)}
.lgsw.shade{background:linear-gradient(90deg,color-mix(in srgb,var(--ink) 25%,transparent),var(--ink))}
#nside{min-width:0;overflow-wrap:anywhere}
.mapside .kick{font-size:11.5px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--accent)}
.mapside h3{overflow-wrap:anywhere}
.pick{height:44px;max-width:100%;min-width:0;border-radius:999px;border:1px solid var(--line-strong);background:var(--surface);color:var(--ink);padding:0 14px;font:600 14.5px var(--sans)}
.locbtn{all:unset;box-sizing:border-box;cursor:pointer;height:44px;padding:0 18px;border-radius:999px;background:var(--ink);color:var(--bg);font:700 14px var(--sans);display:inline-flex;align-items:center;gap:8px}
.locbtn svg{width:16px;height:16px;fill:none;stroke:currentColor;stroke-width:2}
.locbtn:focus-visible,.linkbtn:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.linkbtn{all:unset;cursor:pointer;color:var(--accent-ink);font-weight:600;font-size:14px;text-decoration:underline;text-underline-offset:3px;min-height:32px;display:inline-flex;align-items:center}
.linkbtn[hidden]{display:none}
.ynote{font-size:13.5px;color:var(--muted);margin:10px 0 0;max-width:80ch;line-height:1.45}
.tblwrap{overflow-x:auto;-webkit-overflow-scrolling:touch;margin-top:12px;border:1px solid var(--line);border-radius:14px;background:var(--surface)}
.tblwrap .gt-wrap{border:0;margin:0}
.loading{padding:60px 0;text-align:center}
.crumbs a{min-height:32px;display:inline-flex;align-items:center}
.backlink{display:inline-flex;align-items:center;min-height:44px;color:var(--accent-ink);font-weight:600}
"""


# ============================================================ the Night script pieces

# What every inner page's script shares: the reader's own time, the words for the state of a count, a result drawn as
# lines and bars, the colours and patterns of the lines, and the reading of the live figures. It needs from the page:
# BOOT, $, $$, esc, store, and the page's own CODE (two letters).
NIGHT_JS = r"""
/* ---------- Election Night: the shared script ---------- */
const calm = () => document.documentElement.classList.contains("calm");
const num = n => Number(n || 0).toLocaleString("en-US");
const plural = (n, one, many) => `${num(n)} ${n === 1 ? one : (many || one + "s")}`;
const capital = s => String(s).charAt(0).toUpperCase() + String(s).slice(1);
const andList = a => a.length < 2 ? (a[0] || "") : a.slice(0, -1).join(", ") + " and " + a[a.length - 1];
const pct = (v, t) => t ? (Math.round(v / t * 1000) / 10).toFixed(1) + "%" : "";
const cssv = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const patterned = () => { const d = document.documentElement.dataset; return (d.palette && d.palette !== "standard") || d.calm === "on" || d.contrast === "high"; };

/* the switches every page keeps: motion, and light or dark (high contrast is never undone here; it is the Access page's) */
(function () {
  const root = document.documentElement, m = $("#motion"), t = $("#theme");
  const showMotion = () => { if (m) m.setAttribute("aria-pressed", calm() ? "false" : "true"); };
  showMotion();
  if (m) m.addEventListener("click", () => { const off = !calm(); root.classList.toggle("calm", off); store.set("motion", off ? "off" : "on"); showMotion(); document.dispatchEvent(new Event("night:look")); });
  if (t) t.addEventListener("click", () => { const next = root.dataset.theme === "dark" ? "light" : "dark"; root.dataset.theme = next; store.set("theme", next);
    if (root.getAttribute("data-contrast") !== "high") root.setAttribute("data-contrast", next === "dark" ? "dark" : "standard"); document.dispatchEvent(new Event("night:look")); });
})();

/* ---------- the clock: the reader's own zone, worked out on the device ---------- */
const NOW = () => (BOOT.practice && BOOT.practice.now ? new Date(CLOCK.at.getTime() + (Date.now() - CLOCK.t0)) : new Date());
const CLOCK = (() => { let at = BOOT.practice && BOOT.practice.now ? new Date(BOOT.practice.now) : null;
  if (BOOT.practice) { const q = new URLSearchParams(location.search).get("now"); if (q && !isNaN(Date.parse(q))) at = new Date(q); }      /* a practice page only: ?now= shows another hour */
  return {at: at || new Date(), t0: Date.now()}; })();
function fmtTime(iso, withDay) {
  const d = iso instanceof Date ? iso : new Date(iso); if (isNaN(d)) return "";
  let s = d.toLocaleTimeString("en-US", {hour: "numeric", minute: "2-digit", timeZoneName: "short"}).replace(/\s?AM\b/, " a.m.").replace(/\s?PM\b/, " p.m.");
  const day = d.toLocaleDateString("en-US", {weekday: "short", month: "short", day: "numeric"});
  if (withDay || day !== NOW().toLocaleDateString("en-US", {weekday: "short", month: "short", day: "numeric"})) s = `${day}, ${s}`;
  return s;
}
const fmtDay = iso => { const [y, m, d] = String(iso || "").split("-").map(Number); return y ? new Date(y, m - 1, d).toLocaleDateString("en-US", {month: "long", day: "numeric", year: "numeric"}) : ""; };
/* a wall-clock time in a zone ("2026-11-03", "20:00", "America/Chicago") as an instant */
function zoned(day, hm, tz) {
  const [y, mo, d] = day.split("-").map(Number), [h, mi] = hm.split(":").map(Number), guess = Date.UTC(y, mo - 1, d, h, mi);
  const parts = new Intl.DateTimeFormat("en-US", {timeZone: tz, hourCycle: "h23", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit"}).formatToParts(new Date(guess));
  const p = Object.fromEntries(parts.map(x => [x.type, x.value])), seen = Date.UTC(+p.year, +p.month - 1, +p.day, +p.hour % 24, +p.minute);
  return new Date(guess - (seen - guess));
}

/* ---------- polls: still open, not open yet, closed (John's words, his veto) ---------- */
function pollsNow(P) {      // P: {date, open, close, tz, finder, early}
  if (!P || !P.date) return null;
  const open = zoned(P.date, P.open || "07:00", P.tz), close = zoned(P.date, P.close, P.tz), now = NOW();
  return {open, close, state: now < open ? (now.toDateString() === open.toDateString() ? "today" : "before") : now < close ? "open" : "closed"};
}
function pollsHTML(P, where) {
  const s = pollsNow(P); if (!s) return "";
  const find = P.finder ? `<a href="${esc(P.finder)}" target="_blank" rel="noopener">Find your polling place</a>` : `<a href="https://www.nass.org/can-I-vote" target="_blank" rel="noopener">Find your polling place</a>`;
  if (s.state === "open") return `<div class="pollsopen" role="note"><b>Polls are still open here. If you haven&rsquo;t voted, your vote still counts.</b>Polls in ${esc(where)} close at ${esc(fmtTime(s.close))}.${P.line ? " " + esc(P.line) : ""} ${find}.</div>`;
  if (s.state === "today") return `<div class="pollsopen" role="note"><b>Election Day is today.</b>Polls in ${esc(where)} open at ${esc(fmtTime(s.open))} and close at ${esc(fmtTime(s.close))}. ${find}.</div>`;
  return "";
}

/* ---------- the state of a count, in words ---------- */
const STATUS_WORDS = {wait: "Polls open", none: "No votes yet", counting: "Counting", done: "Every precinct in", official: "Certified", held: "Figures held", stale: "Updates paused", link: "Not read here", refused: "Not read here"};
const statusChip = s => `<span class="stw ${esc(s)}"><i aria-hidden="true"></i>${esc(STATUS_WORDS[s] || "Waiting")}</span>`;

/* ---------- the live figures: now.json, then only the files a page shows, all from one snapshot ---------- */
const LIVE = {now: null, raw: null, st: null, cty: {}, got: {}, wait: {}, base: "", seq: null, why: "", rehearsal: false};
(function () {      /* #rehearsal in the address reads the rehearsal folder, for the whole visit, with its banner */
  try { if (/^#rehearsal\b/.test(location.hash)) { sessionStorage.setItem("night:rehearsal", "1"); history.replaceState(null, "", location.pathname + location.search + "#" + location.hash.replace(/^#rehearsal&?/, "")); }
    LIVE.rehearsal = sessionStorage.getItem("night:rehearsal") === "1"; } catch (e) {}
})();
const liveRoot = () => BOOT.live.base + (LIVE.rehearsal ? "rehearsal/" : "");
/* now.json and the state's file as the store wrote them (raw); liveReady turns the file into the page's own shape once the
   page has its races. The two are separate so that the page can fetch its races and the figures side by side. */
function liveFetch() {
  const root = liveRoot();
  return fetch(root + "now.json", {cache: "no-store"}).then(r => r.ok ? r.json() : Promise.reject(new Error("now " + r.status))).then(now => {
    LIVE.now = now; const s = (now.st || {})[CODE];
    if (!s || !s.f) { LIVE.raw = null; LIVE.why = "nostate"; return null; }
    if (LIVE.seq === now.seq && LIVE.raw) return LIVE.raw;
    const base = root + now.base;
    return fetch(base + s.f, {cache: "force-cache"}).then(r => r.ok ? r.json() : Promise.reject(new Error("state " + r.status))).then(raw => {
      LIVE.raw = raw; LIVE.seq = now.seq; LIVE.base = base; LIVE.cty = {}; LIVE.got = {}; LIVE.wait = {}; LIVE.why = ""; return raw; });
  }).catch(e => { LIVE.raw = null; LIVE.why = /^now /.test(String(e && e.message)) || e instanceof TypeError ? "nofile" : "broken"; return null; });
}
function liveReady(raceOf) { LIVE.st = LIVE.raw ? normState(LIVE.raw, raceOf) : null; return LIVE.st; }
/* the store's lines (ch) against the page's own list: each line is a candidate on the list (its index), the race's
   write-ins ("w"), or a line the list does not have (-1), shown as printed. Names compared as letters and digits only. */
const nameKey = s => String(s || "").normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
function choiceMap(r, ch) {
  const names = r.cs.map(c => nameKey(c[0])), used = new Set(), first = n => n.replace(/ and .*$/, "");
  return ch.map(c => {
    if (c[3]) return "w";
    if (c[4] === 0) return -1;      /* the store tied this line to nobody on the list: shown as printed */
    const k = nameKey(c[4] || c[1]);
    let i = names.findIndex((n, j) => !used.has(j) && n === k);
    if (i < 0) i = names.findIndex((n, j) => !used.has(j) && k && first(n) === first(k));      /* a ticket printed with its first name only */
    if (i >= 0) used.add(i);
    return i;
  });
}
function foldLines(map, n, vals) {      // one count in the store's line order, into the list's order, the unmatched lines and the write-ins
  const v = new Array(n).fill(0), x = []; let w = 0;
  (vals || []).forEach((num, k) => { const m = map[k]; if (m === "w") w += num || 0; else if (m >= 0) v[m] += num || 0; else x.push(num || 0); });
  return {v, x, w};
}
function normState(doc, raceOf) {
  if (!doc || !doc.r) return null;
  const out = {v: doc.v, state: doc.state, t: doc.t || doc.at, saved: doc.saved || doc.at, s: doc.s, units: doc.units, r: {}};
  let widest = null;
  for (const [key, e] of Object.entries(doc.r)) {
    const rid = (doc.pre || "") + key, r = raceOf(rid); if (!r) continue;      // a contest the page does not have: the updater lists it, the page leaves it out
    if (!e.ch) { out.r[rid] = e; if (e.u && (!widest || e.u[1] > widest[1])) widest = e.u; continue; }      // already the page's own shape
    const map = choiceMap(r, e.ch), n = r.cs.length, wi = map.includes("w"), f = foldLines(map, n, e.v);
    const xs = e.ch.filter((c, k) => map[k] === -1);
    const ne = {u: e.p || [0, 0], v: f.v, t: e.t || doc.at, _m: map};
    if (xs.length) ne.x = xs.map((c, k) => [c[1], c[2] || "", f.x[k] || 0]);
    if (wi) ne.w = f.w;
    if (e.off) ne.of = 1;
    if (e.k) { ne.c = {}; for (const [cu, ce] of Object.entries(e.k)) { const g = foldLines(map, n, ce.slice(2));      /* [in, all, votes ...] */
      ne.c[String(cu).slice(-3)] = Object.assign({u: [ce[0] || 0, ce[1] || 0], v: g.v}, xs.length ? {x: g.x} : {}, wi ? {w: g.w} : {}); } }
    out.r[rid] = ne;
    if (!widest || ne.u[1] > widest[1]) widest = ne.u;
  }
  if (!out.units) out.units = widest;      /* the whole state's count: the race that reaches the most units */
  return out;
}
/* A county's precinct rows come in two files from the same snapshot as the state's file: every contest but the judges,
   and the judges ("-court"), each named by the five-digit county unit (27053.json, 27053-court.json). A page fetches only
   the file a race needs, and both for "your ballot"; what it has is merged into LIVE.cty[county]. */
const CPARTS = ["", "court"];
const partOf = r => r && r.lv === "court" ? "court" : "";
const countyFile = (c, part) => (String(c).length === 5 ? String(c) : (BOOT.live.fips || "") + String(c).padStart(3, "0")) + (part ? "-" + part : "") + ".json";
const ctyHas = (c, part) => !!LIVE.got[c + "|" + part];
function normCounty(doc) {      // one county file: {part, t, p: {race: {precinct: [the list's order, the unmatched lines, the write-ins]}}}
  const out = {county: String(doc.county).slice(-3), part: doc.part || "", t: doc.at, p: {}};
  (doc.races || []).forEach((rid, i) => {
    const e = E(rid), ent = (doc.r || [])[i]; if (!e || !e._m || !ent) return;      // a contest the page does not have
    const n = e._m.length, wi = e._m.includes("w"), idx = [], o = out.p[rid] = {};
    (ent[0] || []).forEach(x => { if (Array.isArray(x)) { for (let k = x[0]; k <= x[1]; k++) idx.push(k); } else idx.push(x); });      /* runs of places in u */
    idx.forEach((u, k) => { const f = foldLines(e._m, e.v.length, ent[1].slice(k * n, (k + 1) * n)); o[doc.u[u]] = f.v.concat(f.x, wi ? [f.w] : []); });
  });
  return out;
}
function liveCounty(c, part) {      // a county's precinct rows: the file a race needs (part), or both when none is named
  if (!LIVE.st || !LIVE.base) return Promise.reject(new Error("no figures"));
  const seq = LIVE.seq;
  return Promise.all((part == null ? CPARTS : [part]).map(p => {
    const key = c + "|" + p;
    if (LIVE.got[key]) return null;
    if (!LIVE.wait[key]) LIVE.wait[key] = fetch(LIVE.base + BOOT.live.dir + "c/" + countyFile(c, p), {cache: "force-cache"})
      .then(r => r.ok ? r.json() : Promise.reject(new Error(String(r.status))))
      .then(d => { if (LIVE.seq !== seq) return;      /* a newer snapshot arrived meanwhile: never mix two */
        const f = normCounty(d), have = LIVE.cty[c] || (LIVE.cty[c] = {county: String(c), t: null, tp: {}, p: {}});
        Object.assign(have.p, f.p); have.tp[p] = f.t; if (f.t && (!have.t || f.t > have.t)) have.t = f.t; LIVE.got[key] = 1; },
        e => { delete LIVE.wait[key]; throw e; });
    return LIVE.wait[key];
  })).then(() => { if (!LIVE.cty[c]) throw new Error("no county file"); return LIVE.cty[c]; });
}
const stale = () => LIVE.now && LIVE.now.at && (NOW() - new Date(LIVE.now.at)) > 25 * 60000 && !["done", "official"].includes(liveStatus());
function liveStatus() {
  const s = LIVE.now && (LIVE.now.st || {})[CODE];
  return LIVE.st ? (LIVE.st.s || (s && s.s) || "counting") : (s && s.s) || "";
}

/* ---------- a race's figures ---------- */
const E = id => (LIVE.st && LIVE.st.r && LIVE.st.r[id]) || null;
const PCODE = ["D", "R", "I", "L", "G", "O", "W"];
const PPAT = {D: "", R: "hatch", I: "dots", L: "cross", G: "rows", O: "cols", W: "back"}, NPAT = ["", "hatch", "dots", "cross", "rows", "cols", "back"];
/* every line a result shows: the candidates on the list, any line of the state's file that matches none of them, and the
   write-in votes; with each its colour (a party's for a partisan race, a neutral tone in ballot order otherwise) and pattern */
function lines(r, e) {
  const v = (e && e.v) || [], out = r.cs.map((c, i) => ({i, name: c[0], party: c[1] || "", pc: c[2] || "O", votes: v[i] || 0}));
  ((e && e.x) || []).forEach((x, k) => out.push({i: r.cs.length + k, name: x[0], party: x[1] || "", pc: "O", votes: x[2] || 0, x: 1}));
  out.forEach(L => { const k = r.pt ? (PCODE.includes(L.pc) ? L.pc : "O") : null;
    L.c = r.pt ? `var(--p${k})` : `var(--n${L.i % 6 + 1})`; L.p = r.pt ? PPAT[k] : NPAT[L.i % NPAT.length]; });
  if (e && e.w) out.push({i: -1, name: "Write-in votes", party: "", votes: e.w, wl: 1, c: "var(--pW)", p: ""});
  const total = out.reduce((t, L) => t + L.votes, 0);
  if (total) out.sort((a, b) => (a.wl || 0) - (b.wl || 0) || b.votes - a.votes || a.i - b.i);
  return {lines: out, total};
}
const seatsOf = r => r.n || 1;
/* the candidates ahead in the count so far: as many as there are seats, where the count says so without a tie at the line */
function aheadSet(r, L) {
  const named = L.lines.filter(x => !x.wl), n = seatsOf(r), out = new Set();
  if (!L.total || named.length <= n && r.cs.length <= n) return out;      // one name a seat: nobody is "ahead" of anybody
  for (let k = 0; k < Math.min(n, named.length); k++) { if (named[k].votes <= 0) break; if (named[n] && named[k].votes === named[n].votes) break; out.add(named[k]); }
  return out;
}
"""

# The Night results kit, written into the map's script beside each page (after BallotMap): how a count colours a shape.
# The page hands it the shapes' votes; it hands BallotMap's paint kit the fills. A shape whose count is in is the colour of
# the line ahead there, deeper as the lead grows (under 5 points, 5 to 15, 15 or more); a shape of the race's area that has
# not reported is hatched; a tie is grey. Under a colour-vision palette, Calm or high contrast, each fill also carries the
# pattern of the line ahead.
NIGHTMAP_JS = r"""/* ---------- Election Night: the results kit. A shape's fill from its count; BallotMap's paint kit does the drawing. ---------- */
window.NightKit = (function () {
  "use strict";
  const STEPS = [[5, .4], [15, .64], [Infinity, .88]];
  const memo = {};
  function rgb(colour) {      // "#rrggbb", "#rgb" or "rgb(a)(...)" as [r, g, b]
    if (memo[colour]) return memo[colour];
    let m = /^#([0-9a-f]{6})$/i.exec(colour), out = null;
    if (m) out = [0, 2, 4].map(k => parseInt(m[1].slice(k, k + 2), 16));
    else if ((m = /^#([0-9a-f]{3})$/i.exec(colour))) out = [0, 1, 2].map(k => parseInt(m[1][k] + m[1][k], 16));
    else if ((m = /rgba?\(([^)]+)\)/.exec(colour))) out = m[1].split(/[ ,/]+/).slice(0, 3).map(Number);
    return (memo[colour] = out || [128, 128, 128]);
  }
  const rgba = (colour, a) => { const c = rgb(colour); return `rgba(${c[0]},${c[1]},${c[2]},${a})`; };
  function lead(v) {      // the line ahead in one shape's count: its index, its lead in points of the named lines' total, a tie
    let tot = 0, a = -1, b = -1;
    for (let i = 0; i < v.length; i++) { const x = v[i] || 0; tot += x; if (a < 0 || x > v[a]) { b = a; a = i; } else if (b < 0 || x > v[b]) b = i; }
    if (!tot) return null;
    const top = v[a] || 0, next = b >= 0 ? v[b] || 0 : 0;
    return {i: a, tie: top === next, margin: (top - next) / tot * 100, total: tot};
  }
  const step = m => (STEPS.find(s => m < s[0]) || STEPS[STEPS.length - 1])[1];
  /* paint(kit, kind, countOf, look): countOf(id, props) gives a shape's count, {v: [one figure a named line], cols: [each
     line's colour], pats: [each line's pattern, or ""]}; "wait" for a shape of the race's area that has not reported; or
     null for a shape outside it. look: {tie, empty, wait, overlay, patterned, edge (the thin line between filled shapes)}.
     Returns how many fills were drawn. */
  function paint(kit, kind, countOf, look) {
    const hatch = kit.pattern(look.wait, "hatch"), seen = {};
    const n = kit.fill(kind, (id, p) => { const k = countOf(id, p); if (k == null) return null; if (k === "wait") return hatch;
      const L = lead(k.v); seen[id] = [L, k]; if (!L) return look.empty; if (L.tie) return look.tie; return rgba(k.cols[L.i] || look.tie, step(L.margin)); }, 1, look.edge);
    if (look.patterned) kit.fill(kind, id => { const s = seen[id]; if (!s || !s[0] || s[0].tie) return null; const pat = (s[1].pats || [])[s[0].i];
      return pat ? kit.pattern(look.overlay, pat) : null; }, 1);
    return n;
  }
  return {STEPS, rgba, lead, paint};
})();
"""
