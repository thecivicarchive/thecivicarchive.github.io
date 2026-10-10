#!/usr/bin/env python3
"""
build_night_feed.py - Election Night, the feed: site/dev/night/feed/.

    python build_night_feed.py                  (into site/dev/night/feed/)
    python build_night_feed.py --practice       (the same page, into site/practice/night/feed/; never published)
    python build_night_feed.py --root site/dev

The page shows news headlines with links (each outlet named on its own headline, GDELT credited wherever its items
appear), posts from newsrooms, election offices and candidates' official accounts once the site may show them, a map of
coverage by state, and the leaderboard: four measures for every race, each race ranked only against the races of its own
board, each figure with its arithmetic. Routes (after #):
  ""                 the country: the map, the boards, the newest headlines, official posts
  #state=MN          one state: its boards, its headlines (and those placed only by where the outlet is), its poll hours
  #race=<race id>    one race: its four measures worked out, its headlines, how many people posted about it
  #board=<board>     the country's boards, open at one board (statewide, house, legislature, county, local);
                     #board=local&measure=g opens it at one measure (c coverage, g attention gap, m momentum, b breadth)
  #how               how it is counted: the rules, the formulas, the sources, what is not read and why, privacy

What it writes beside index.html:
  data/map.json             the states' shapes (night_common.us_map_doc)
  data/races/<code>.json    every race the feed knows in a state: its short name, its board, its residents and which
                            Census geography they come from (election.feeds.measures.residents), nothing else
  fonts/                    the site's own type
The live figures are not part of the page: it reads now.json, then feed/us.json and a state's feed/<code>.json from the
same snapshot folder of the live site (/night-live/), as election.feeds.measures.page_json writes them.

--practice writes the same page to site/practice/night/feed/; it reads the practice live folder, where the feed's files
are only if the updater's practice run wrote them (this builder never writes there).
"""

import argparse
import datetime as dt
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import night_common as N  # noqa: E402

POLL_HOURS = os.path.join(HERE, "election", "poll_hours.json")
GENERAL = "2026-11-03"
SHELL_LIMIT = 380_000
RACES_LIMIT = 400_000            # one state's race file
GDELT = "https://www.gdeltproject.org/"
NASS = "https://www.nass.org/can-I-vote"
PRACTICE_LABEL = "Practice: this page with no figures of its own. Not 2026 coverage."
RIDER = '<script type="module" src="../../shell/rider.js" data-tca-rider></script>\n'


def esc(s):
    return (str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;"))


def sha10(text):
    return N.sha10(text)


# ============================================================ the static files

def race_files(say=print):
    """{code: doc} for data/races/<code>.json: every race the feed knows, its short name, board and residents."""
    from election.feeds import measures as M
    con = M.ro(M.DB)
    try:
        races = M.load_races(con, say)
    finally:
        con.close()
    res = M.residents(races, say=say)
    out = {}
    for rid, r in sorted(races.items()):
        code = r["state"]
        d = out.setdefault(code, {"v": 1, "code": code, "pre": f"2026-{code}-", "how": [], "r": {}})
        pop, how, approx = res.get(rid) or [None, "", 0]
        if how not in d["how"]:
            d["how"].append(how)
        short = rid[len(d["pre"]):] if rid.startswith(d["pre"]) else rid
        d["r"][short] = [r["label"], r["board"], pop, approx, d["how"].index(how)]
    return out, races


def polls_boot(P):
    """Each state's latest-closing zone, for the "polls are still open" notice: date, opening and closing time, time zone,
    the state's own polling place lookup, the sentence about voters in line."""
    out = {}
    for code, e in (P.get("states") or {}).items():
        zones = [z for z in (e.get("zones") or []) if re.fullmatch(r"[A-Za-z_]+(?:/[A-Za-z_]+){1,2}", str(z.get("tz") or ""))
                 and re.fullmatch(r"\d\d:\d\d", str(z.get("closes") or ""))]
        if not zones:
            continue
        z = max(zones, key=lambda z: str(z.get("closes_utc") or ""))
        p = {"date": GENERAL, "open": z.get("opens") if re.fullmatch(r"\d\d:\d\d", str(z.get("opens") or "")) else "07:00",
             "close": z["closes"], "tz": z["tz"]}
        look = e.get("lookup")
        url = look.get("url") if isinstance(look, dict) else look
        if isinstance(url, str) and url.startswith("https://"):
            p["finder"] = url
        line = e.get("in_line")
        if isinstance(line, str) and 10 < len(line) < 200 and not re.search(r"https?://|www\.", line):
            p["line"] = line
        out[code] = p
    return out


def sources_boot():
    """What the #how page counts: outlets and the states they cover, official accounts by kind, the feeds that refused."""
    from election.feeds import measures as M
    con = M.ro(M.DB)
    out = {"outlets": 0, "outlet_states": 0, "national": 0, "accounts": {}, "refused": 0, "posts": False}
    try:
        t = M.tables(con)
        if "outlets" in t:
            out["outlets"] = con.execute("SELECT COUNT(DISTINCT outlet_key) FROM outlets WHERE active = 1").fetchone()[0]
            out["outlet_states"] = con.execute("SELECT COUNT(DISTINCT home_state) FROM outlets WHERE active = 1 AND home_state NOT IN ('US', 'DC')").fetchone()[0]
            out["national"] = con.execute("SELECT COUNT(DISTINCT outlet_key) FROM outlets WHERE active = 1 AND home_state = 'US'").fetchone()[0]
            out["by_state"] = {st: [n for (n,) in con.execute("SELECT DISTINCT name FROM outlets WHERE active = 1 AND home_state = ? ORDER BY name", (st,))]
                               for (st,) in con.execute("SELECT DISTINCT home_state FROM outlets WHERE active = 1")}
        if "outlets_refused" in t:
            out["refused"] = con.execute("SELECT COUNT(*) FROM outlets_refused").fetchone()[0]
        if "accounts" in t:
            out["accounts"] = dict(con.execute("SELECT owner_kind, COUNT(*) FROM accounts WHERE active = 1 GROUP BY owner_kind").fetchall())
    finally:
        con.close()
    try:
        from election.feeds import accounts
        out["posts"] = bool(accounts.posts_may_be_shown())
    except Exception:  # noqa: BLE001
        out["posts"] = False
    return out


# ============================================================ the page

PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Election Night: the feed · The Civic Archive</title>
<meta name="description" content="__DESC__">
<meta name="version" content="__VERSION__">
__BRAND__
__HEADSCRIPT__
<style>
__FONTS__
</style>
<style>__CSS__</style>
<style>__BALLOT_CSS__</style>
<style>__NIGHT_CSS__
__USMAP_CSS__
.nhero{padding:28px 0 4px}
.nhero h1{font-family:var(--serif);font-weight:400;font-size:clamp(38px,6vw,72px);line-height:1;margin:10px 0 0;overflow-wrap:break-word}
.nhero .lede{color:var(--muted);max-width:68ch;font-size:clamp(15px,1.5vw,18px);margin:12px 0 0}
.draftnote{background:var(--brass-soft);color:var(--ink);padding:6px 16px;font:600 12.5px/1.4 var(--sans);text-align:center;border-bottom:1px solid var(--line)}
.draftnote a{color:inherit}
.nempty{border:1px dashed var(--line-strong);border-radius:14px;padding:12px 14px;color:var(--muted);font-size:14px;margin-top:12px;max-width:96ch}
.fanote{font-size:14px;line-height:1.5;margin:14px 0 0;max-width:96ch}
.fanote .tag{margin-right:8px}
.fseg{display:flex;flex-wrap:wrap;gap:6px;margin:12px 0 0;padding:0;border:0}
.fseg button{all:unset;box-sizing:border-box;cursor:pointer;min-height:36px;display:inline-flex;align-items:center;padding:0 14px;border-radius:999px;border:1px solid var(--line-strong);background:var(--surface);color:var(--ink);font:600 13.5px var(--sans)}
.fseg button[aria-pressed="true"]{background:var(--ink);color:var(--bg);border-color:var(--ink)}
.fseg button:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
@media (pointer:coarse){.fseg button{min-height:44px}}
.mhelp{font-size:13.5px;color:var(--muted);margin:10px 0 0;max-width:90ch;line-height:1.5}
.heads{list-style:none;margin:12px 0 0;padding:0;display:grid;gap:10px;max-width:96ch}
.heads li{border:1px solid var(--line);background:var(--surface);border-radius:14px;padding:10px 14px;min-width:0}
.heads li>a{font-weight:700;font-size:15px;color:var(--ink);text-decoration:none;overflow-wrap:anywhere;line-height:1.35}
.heads li>a:hover{text-decoration:underline}
.heads li>a:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.heads .meta{display:flex;flex-wrap:wrap;gap:3px 10px;font-size:12.5px;color:var(--muted);margin-top:5px;align-items:center}
.heads .meta b{color:var(--ink);font-weight:700}
.heads .meta a{color:var(--accent-ink)}
.conf{display:inline-flex;align-items:center;border:1px solid var(--line-strong);border-radius:10px;padding:0 7px;font:600 11px/1.6 var(--sans);color:var(--muted)}
.gt-more[hidden]{display:none}
#boardhost .gt td:nth-child(2){min-width:170px}#boardhost .gt td{vertical-align:top}
.conf.h{border-color:var(--verd);color:var(--ink)}.conf.l{border-style:dashed}
.measures{display:grid;gap:12px;grid-template-columns:repeat(auto-fill,minmax(min(100%,300px),1fr));margin-top:14px}
.meas{border:1px solid var(--line);background:var(--surface);border-radius:18px;padding:14px 16px;min-width:0}
.meas h3{font:700 12px var(--sans);letter-spacing:.1em;text-transform:uppercase;color:var(--accent);margin:0}
.meas .fbig{font-family:var(--serif);font-size:34px;line-height:1.05;margin:8px 0 0}
.meas .fbig small{font-family:var(--sans);font-size:13px;color:var(--muted);margin-left:6px}
.meas .fwhy{font-size:13.5px;line-height:1.5;margin:8px 0 0;color:var(--ink)}
.meas .math{font:500 13px/1.55 var(--sans);font-variant-numeric:tabular-nums;background:var(--bg);border:1px solid var(--line);border-radius:10px;padding:8px 10px;margin:10px 0 0;overflow-wrap:anywhere}
.meas .not{font-size:12.5px;color:var(--muted);margin:8px 0 0}
.rising{display:inline-flex;align-items:center;gap:4px;font:700 11px var(--sans);letter-spacing:.06em;text-transform:uppercase;color:var(--ink);border:1px solid var(--verd);background:var(--verd-soft);border-radius:999px;padding:1px 8px}
.gt td .linkbtn{font-size:13px}
.gt td a{color:var(--accent-ink);font-weight:600}
.gt-detail td{background:var(--bg)}
.gt-detail .math{font-size:13px;line-height:1.55;overflow-wrap:anywhere;max-width:90ch}
.fhow h3{font-family:var(--serif);font-weight:400;font-size:26px;margin:26px 0 0}
.fhow p,.fhow li{max-width:80ch;line-height:1.6;font-size:15px}
.fhow .formula{font:600 14px/1.6 var(--sans);background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:8px 12px;max-width:80ch;overflow-wrap:anywhere}
.stl{columns:3 220px;font-size:13.5px;margin:10px 0 0;padding-left:18px}
.stl li{break-inside:avoid;margin-bottom:3px}
.mapcol .mnote{font-size:12.5px;color:var(--muted);margin:6px 0 0}
#feedside .kick{font-size:11.5px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--accent)}
#feedside h3{font-family:var(--serif);font-weight:400;font-size:26px;margin:6px 0 0}
#feedside p{font-size:14px;margin:8px 0 0}
.rlinks{display:flex;gap:6px 18px;flex-wrap:wrap;margin-top:18px;font-size:14px}
.rlinks a{color:var(--accent-ink);font-weight:600;min-height:32px;display:inline-flex;align-items:center}
.usvg path.s{stroke:var(--surface)}
:root[data-contrast="high"] .usvg path.s{stroke:#000;stroke-width:.6}
.toplist{list-style:none;margin:10px 0 0;padding:0;display:grid;gap:6px;font-size:14px}
.toplist a{display:flex;justify-content:space-between;gap:10px;text-decoration:none;color:inherit;border-bottom:1px dashed var(--line);padding:6px 0;min-height:32px;align-items:center}
.toplist a:hover b{text-decoration:underline}
.toplist a:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.toplist span{color:var(--muted);font-variant-numeric:tabular-nums;white-space:nowrap}
</style>
</head>
<body>
__BANNER__<div class="nbanner" id="nreh" hidden></div>
<div class="draftnote">A draft for feedback, not the finished site. <a href="https://thecivicarchive.github.io/">Go to the live site</a></div>
__TOPBAR__
<main id="app" class="bwrap" tabindex="-1"><p class="loading muted">Loading the feed&hellip;</p></main>
<p class="sr" id="nlive" aria-live="polite"></p>
<footer class="bwrap bfoot">
  <p>Election Night, from The Civic Archive v__VERSION__. Generated on __GENERATED__. The feed is counted from public headlines and posts: a measure of coverage, not of importance or of support. Headlines link to the outlets that published them; some are found through the <a href="https://www.gdeltproject.org/">GDELT Project</a>. Posts by people who are not newsrooms, election offices or candidates are counted, never shown or named.</p>
  <p>__FOOTLINKS__</p>
</footer>
__CLBOX__
<script>
const BOOT = __BOOT__;
const CODE = "US";
const $ = (s, el) => (el || document).querySelector(s), $$ = (s, el) => [...(el || document).querySelectorAll(s)];
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
const store = {get: k => { try { return localStorage.getItem(k); } catch (e) { return null; } }, set: (k, v) => { try { localStorage.setItem(k, v); } catch (e) {} },
  del: k => { try { localStorage.removeItem(k); } catch (e) {} }};
/* ===== parts shared with the rest of the site (taken from their pages when this page is built) ===== */
__CHANGELOG__
__GRID__
__GEO__
/* ===== end of the shared parts ===== */
__NIGHT_JS__
__USMAP_JS__
__PAGE_JS__
</script>
</body>
</html>
"""

PAGE_JS = r"""
/* ---------- the feed ---------- */
const app = $("#app");
const FEED = {us: null, st: {}, seq: null, base: "", why: ""};
const RACEF = {};        // a state's race file (names, boards, residents), fetched once
let MAPD = null, BOARD = (() => { const b = store.get("night:feedboard"); return BOOT.boards.some(x => x[0] === b) ? b : "statewide"; })();
let MEAS = (() => { const m = store.get("night:feedmeasure"); return ["c", "g", "m", "b"].includes(m) ? m : "c"; })();
const BNAME = Object.fromEntries(BOOT.boards);
const MWORD = {c: "Coverage per 100,000 residents", g: "Attention gap", m: "Momentum", b: "Source breadth"};
const SNAME = c => (BOOT.states[c] || c);
const f2 = x => x == null ? "" : (x > 0 && x < .01) ? Number(x).toLocaleString("en-US", {maximumSignificantDigits: 2, maximumFractionDigits: 12})
  : Number(x).toLocaleString("en-US", {maximumFractionDigits: 2, minimumFractionDigits: x < 10 && x % 1 ? 2 : 0});
const f1 = x => x == null ? "" : Number(x).toLocaleString("en-US", {maximumFractionDigits: 1});
const ord = n => { n = Math.round(n); const s = (n % 100 >= 11 && n % 100 <= 13) ? "th" : ({1: "st", 2: "nd", 3: "rd"}[n % 10] || "th"); return n + s; };
const sgn = x => (x > 0 ? "+" : x < 0 ? "\u2212" : "") + f1(Math.abs(x));
const safeURL = u => /^https?:\/\//i.test(String(u || "")) ? String(u) : "";
function getJSON(u) { return fetch(u).then(r => r.ok ? r.json() : Promise.reject(new Error(String(r.status)))); }

/* ---------- the routes ---------- */
function route() {
  const h = decodeURIComponent(location.hash.replace(/^#/, ""));
  let m;
  if ((m = h.match(/^state=([A-Za-z]{2})\b/))) return {v: "state", code: m[1].toUpperCase()};
  if ((m = h.match(/^race=([A-Za-z0-9-]+)/))) return {v: "race", id: m[1], code: m[1].slice(5, 7).toUpperCase()};
  if ((m = h.match(/^board=([a-z]+)(?:&measure=([cgmb]))?/)) && BNAME[m[1]]) return {v: "home", board: m[1], measure: m[2] || null};
  if (/^how\b/.test(h)) return {v: "how"};
  return {v: "home"};
}
const wantCode = () => { const r = route(); return r.code && BOOT.states[r.code] ? r.code : null; };

/* ---------- the live figures: now.json, then the country's file and the state's, from one snapshot ---------- */
function feedGet() {
  const root = liveRoot();
  return fetch(root + "now.json", {cache: "no-store"}).then(r => { if (!r.ok) throw new Error("now " + r.status); return r.json(); }).then(now => {
    if (!now || now.v !== 1) throw new Error("now unreadable");
    const code = wantCode();
    if (FEED.us && FEED.seq === now.seq && (!code || code in FEED.st)) return {now, same: true};
    if (!now.base || !now.fd) return {now, none: true};
    const base = root + now.base, j = u => fetch(base + u, {cache: "force-cache"}).then(r => r.ok ? r.json() : null, () => null);
    return Promise.all([j("feed/us.json"), code ? j("feed/" + code.toLowerCase() + ".json") : Promise.resolve(null)])
      .then(([us, st]) => ({now, us, st, code, base, seq: now.seq}));
  });
}
function feedCommit(g) {      // true when the page has new figures
  LIVE.now = g.now;
  if (g.same) return false;
  if (g.none || !g.us) { if (!FEED.us) FEED.why = "nofeed"; return false; }
  if (FEED.seq !== g.seq) FEED.st = {};
  FEED.us = g.us; FEED.seq = g.seq; FEED.base = g.base; FEED.why = "";
  if (g.code) FEED.st[g.code] = g.st || null;
  return true;
}
function stateDoc(code) {      // a state's feed file from the snapshot already in hand (never another snapshot's)
  if (!code) return Promise.resolve(null);
  if (code in FEED.st) return Promise.resolve(FEED.st[code]);
  if (!FEED.base) return Promise.resolve(null);
  const seq = FEED.seq;
  return fetch(FEED.base + "feed/" + code.toLowerCase() + ".json", {cache: "force-cache"}).then(r => r.ok ? r.json() : null, () => null)
    .then(d => { if (FEED.seq === seq) FEED.st[code] = d; return FEED.seq === seq ? d : FEED.st[code] || null; });
}
function raceFile(code) {
  if (!BOOT.states[code]) return Promise.resolve(null);
  return RACEF[code] || (RACEF[code] = getJSON(BOOT.races + code.toLowerCase() + ".json?v=" + (BOOT.rv[code] || "")).catch(() => { delete RACEF[code]; return null; }));
}
const full = (doc, k) => (doc.pre || "") + k;
const shortOf = (doc, id) => id.startsWith(doc.pre || "") ? id.slice((doc.pre || "").length) : id;
function entry(doc, id) { return doc && doc.r ? doc.r[shortOf(doc, id)] || null : null; }
function labelOf(doc, id, rf) {
  const k = doc && doc.rl ? doc.rl[shortOf(doc, id)] : null;
  if (k) return k[0];
  if (rf && rf.r) { const x = rf.r[shortOf(rf, id)]; if (x) return x[0]; }
  return id;
}
function boardOf(doc, id, rf) {
  const k = doc && doc.rl ? doc.rl[shortOf(doc, id)] : null;
  if (k) return k[2];
  if (rf && rf.r) { const x = rf.r[shortOf(rf, id)]; if (x) return x[1]; }
  return null;
}

/* ---------- words for the state of the figures ---------- */
function asOfHTML(doc) {
  if (!doc) return "";
  const w = doc.w >= 1440 ? "over the last 24 hours" : `over the last ${doc.w} minutes`;
  return `<p class="asof">Counted at <b>${esc(fmtTime(doc.t))}</b>, ${w}. Source breadth always looks back 24 hours; momentum compares the last hour with the hour before.</p>`;
}
function noFiguresHTML() {
  if (NIGHTLIVE.off()) return `<p class="nempty">This preview of the draft has no live figures. On the published site the feed&rsquo;s figures appear here once the night&rsquo;s updater is running.</p>`;
  if (FEED.why === "nofeed") return `<p class="nempty">The feed has no figures in the newest update yet. Its headlines and counts are added while the night&rsquo;s updater runs, from the evening before Election Day.</p>`;
  return `<p class="nempty">No feed figures yet. The feed starts when the night&rsquo;s updater starts, the evening before Election Day, and counts the day before the polls close and then the night itself, hour by hour.</p>`;
}
function pausedHTML() {
  const p = livePause(); if (!p || !FEED.us) return "";      /* with no feed figures in hand there is nothing to say is old */
  return `<div class="nstat" role="note">${statusChip("stale")}<p>Updates have paused. The figures below are from ${esc(fmtTime(p.since))}.<small>They stay as they were until the updater writes again.</small></p></div>`;
}
const ANALYSIS = `<p class="fanote"><span class="tag analysis">Analysis</span>Counted from public headlines and posts. Not a measure of importance or of support.</p>`;
function heroHTML(kick, title, lede) { return `<section class="bhero nhero"><span class="eyebrow">${kick}</span><h1>${title}</h1>${lede ? `<p class="lede">${lede}</p>` : ""}</section>`; }

/* ---------- the arithmetic of each measure, in words and numbers ---------- */
const RATE = (doc, b) => (doc && doc.rates && doc.rates[b]) || 0;
function coverageMath(e, b, doc) {
  if (!e || !e.pop) return "This race&rsquo;s area has no Census figure on file, so it has no coverage figure.";
  const R = RATE(doc, b);
  return `raw = 100,000 &times; ${num(e.n)} &divide; ${num(e.pop)} = <b>${f2(e.cr || 0)}</b><br>shown = 100,000 &times; (${num(e.n)} + ${f2(R)}) &divide; (${num(e.pop)} + 100,000) = <b>${f2(e.cs || 0)}</b><br>`
    + `<small>${f2(R)} is the board&rsquo;s own rate: all its races&rsquo; items per 100,000 of all their residents. The extra 100,000 residents at that rate keep a small place with two stories from topping the board.</small>`;
}
function gapMath(e, b, doc) {
  if (!e || e.gap == null) return "";
  const src = e.ms === "c" ? `the count so far${e.sc ? ` (${Math.round(e.sc * 100)}% of the expected vote counted)` : ""}` : "the forecast&rsquo;s median, before 20% of the expected vote is counted";
  const n = ((doc.boards || {})[b] || {}).ng;
  return `margin = ${f1(Math.abs(e.mg) * 100)} points of the top two&rsquo;s votes, from ${src}<br>closeness = 1 &minus; ${f2(Math.abs(e.mg))} = ${f2(1 - Math.abs(e.mg))}, the ${ord(e.pc)} percentile${n ? ` of the board&rsquo;s ${num(n)} races with a margin` : ""}<br>`
    + `coverage shown ${f2(e.cs || 0)}, the ${ord(e.pv)} percentile<br>gap = ${f1(e.pc)} &minus; ${f1(e.pv)} = <b>${sgn(e.gap)}</b>`;
}
function momentumMath(e) {
  if (!e) return "";
  const c1 = e.c1 || 0, c0 = e.c0 || 0;
  return `(${num(c1)} + 1) &divide; (${num(c0)} + 1) = <b>${f2(e.mo || 1)}</b><br>`
    + (e.ri ? `${num(c1)} is above ${f2(e.ub)}, the 95% upper bound for an hour that had ${num(c0)}: rising.` : `${num(c1)} is not above ${f2(e.ub)}, the 95% upper bound for an hour that had ${num(c0)}: within the ordinary ups and downs.`)
    + `<br><small>Each hour counts news items and the people who posted about the race (each person once).</small>`;
}
function breadthMath(e) {
  if (!e || !e.i24) return "";
  const os = e.os || [], tot = os.reduce((a, b) => a + b, 0);
  const parts = os.length && tot ? os.slice(0, 8).map(c => `${f2(c / tot)} ln ${f2(c / tot)}`).join(" + ") + (os.length > 8 ? " + &hellip;" : "") : "";
  return `${num(e.o24 || 0)} distinct outlet${e.o24 === 1 ? "" : "s"} among ${num(e.i24)} item${e.i24 === 1 ? "" : "s"}${os.length ? ` (${andList(os.map(num))})` : ""}<br>`
    + (parts ? `effective = exp(&minus;(${parts})) = <b>${f2(e.eff || 0)}</b>` : `effective = <b>${f2(e.eff || 0)}</b>`);
}
const NOT = {c: "Ranked once a race has 3 or more items from 2 or more outlets.", g: "Ranked when the race has a margin (the count, or the forecast before then); retention votes and races with one name a seat are left out.",
  m: "Ranked once the two hours hold 10 or more items and people together.", b: "Ranked once a race has 3 or more items in 24 hours."};
function measuresHTML(e, b, doc, pop) {
  if (!doc || !doc.r) return `<p class="nempty">No figures for this race yet. The four measures are worked out every five minutes while the night&rsquo;s updater runs.</p>`;
  if (!e) { const R = RATE(doc, b);      /* nothing about this race in the window: its figures are the empty ones */
    e = {n: 0, o: 0, c1: 0, c0: 0, i24: 0, o24: 0, mo: 1, ub: 2.996, rk: "", pop: pop || null, cr: pop ? 0 : null, cs: pop ? 100000 * R / (pop + 100000) : null}; }
  const has = k => e && (e.rk || "").includes(k);
  const card = (k, big, why, math) => `<div class="meas"><h3>${MWORD[k]}</h3><p class="fbig">${big}</p>${why ? `<p class="fwhy">${why}</p>` : ""}${math ? `<div class="math">${math}</div>` : ""}${has(k) ? "" : `<p class="not">Not on the board yet. ${NOT[k]}</p>`}</div>`;
  const e0 = e || {n: 0, o: 0, c1: 0, c0: 0, i24: 0, o24: 0};
  return `<div class="measures">`
    + card("c", e0.cs != null ? `${f2(e0.cs)}<small>per 100,000 (raw ${f2(e0.cr || 0)})</small>` : "&mdash;", `${plural(e0.n || 0, "news item")} from ${plural(e0.o || 0, "outlet")} in the window.`, coverageMath(e0, b, doc))
    + card("g", e0.gap != null ? sgn(e0.gap) : "&mdash;", e0.gap != null ? (e0.gap > 0 ? "Closer than its coverage suggests." : e0.gap < 0 ? "More coverage than its closeness suggests." : "Coverage in step with closeness.") : "No margin yet: neither a count with 20% of the expected vote nor a forecast.", gapMath(e0, b, doc))
    + card("m", `${f2(e0.mo || 1)}${e0.ri ? ` <span class="rising">Rising</span>` : ""}`, `${num(e0.c1 || 0)} in the last hour, ${num(e0.c0 || 0)} in the hour before.`, momentumMath(e0))
    + card("b", e0.i24 ? `${num(e0.o24 || 0)}<small>${(e0.o24 || 0) === 1 ? "outlet" : "outlets"}, ${f2(e0.eff || 0)} effective</small>` : "&mdash;", "Over the last 24 hours.", breadthMath(e0))
    + `</div>`;
}

/* ---------- the boards ---------- */
let GRID_ = null;
function boardRows(doc, b, k) {
  const ids = (((doc.boards || {})[b] || {})[k] || []);
  return ids.map((s, i) => { const id = full(doc, s); return {i: i + 1, id, st: id.slice(5, 7), label: labelOf(doc, id), e: entry(doc, id) || {}}; });
}
const linkRace = r => `<a href="#race=${esc(r.id)}">${esc(r.label)}</a>`;
function colsFor(doc, b, k) {
  const base = [{key: "i", label: "#", num: true, val: r => r.i, first: "asc"}, {key: "race", label: "Race", val: r => r.label, html: linkRace},
    {key: "st", label: "State", val: r => r.st, html: r => `<a href="#state=${esc(r.st)}">${esc(r.st)}</a>`}];
  const more = {key: "x", label: "Worked out", val: () => "", html: () => `<button type="button" class="linkbtn" data-x>Show</button>`};
  if (k === "c") return base.concat([{key: "cs", label: "Per 100,000", num: true, val: r => r.e.cs, html: r => f2(r.e.cs)}, {key: "cr", label: "Raw", num: true, val: r => r.e.cr, html: r => f2(r.e.cr)},
    {key: "n", label: "Items", num: true, val: r => r.e.n || 0}, {key: "o", label: "Outlets", num: true, val: r => r.e.o || 0}, more]);
  if (k === "g") return base.concat([{key: "gap", label: "Gap", num: true, val: r => r.e.gap, html: r => sgn(r.e.gap)},
    {key: "mg", label: "Margin", num: true, val: r => Math.abs(r.e.mg), html: r => `${f1(Math.abs(r.e.mg) * 100)} pts <small class="muted">${r.e.ms === "c" ? "count" : "forecast"}</small>`},
    {key: "n", label: "Items", num: true, val: r => r.e.n || 0}, more]);
  if (k === "m") return base.concat([{key: "mo", label: "Momentum", num: true, val: r => r.e.mo, html: r => f2(r.e.mo) + (r.e.ri ? ` <span class="rising">Rising</span>` : "")},
    {key: "c1", label: "Last hour", num: true, val: r => r.e.c1 || 0}, {key: "c0", label: "Hour before", num: true, val: r => r.e.c0 || 0}, more]);
  return base.concat([{key: "eff", label: "Effective", num: true, val: r => r.e.eff, html: r => f2(r.e.eff)}, {key: "o24", label: "Outlets", num: true, val: r => r.e.o24 || 0},
    {key: "i24", label: "Items, 24 h", num: true, val: r => r.e.i24 || 0}, more]);
}
function detailFor(doc, b, k) {
  return r => `<div class="math">${k === "c" ? coverageMath(r.e, b, doc) : k === "g" ? gapMath(r.e, b, doc) : k === "m" ? momentumMath(r.e) : breadthMath(r.e)}</div>`;
}
const EMPTY = {c: "No race on this board has 3 items from 2 outlets in the window yet.", g: "No race on this board has a margin yet.",
  m: "No race on this board has 10 items and people in the last two hours yet.", b: "No race on this board has 3 items in the last 24 hours yet."};
function boardsHTML(doc, where) {
  return `<section class="bsec" id="boards"><h2>The leaderboard${where ? ": " + esc(where) : ""}</h2>
    <p class="sub">One board for each level of office: a race is ranked only against races like it. Pick a board and a measure; each row shows how its figure is worked out.</p>${ANALYSIS}
    <div class="fseg" role="group" aria-label="Board" id="bseg">${BOOT.boards.map(([k, w]) => `<button type="button" data-b="${k}" aria-pressed="${k === BOARD}">${esc(w)}</button>`).join("")}</div>
    <div class="fseg" role="group" aria-label="Measure" id="mseg">${["c", "g", "m", "b"].map(k => `<button type="button" data-m="${k}" aria-pressed="${k === MEAS}">${MWORD[k]}</button>`).join("")}</div>
    <p class="mhelp" id="mhelp"></p><div class="tblwrap" id="boardhost"></div></section>`;
}
const MHELP = {c: "News items in the window for every 100,000 people who live in the race&rsquo;s area, steadied by the board&rsquo;s own rate. The raw figure is beside it.",
  g: "How close the race is, against how much coverage it gets, both as percentiles within the board. Positive: closer than its coverage suggests. Close races with no coverage at all are included.",
  m: "The last hour against the hour before, items and people together. &ldquo;Rising&rdquo; only when the last hour is beyond the ordinary ups and downs of the hour before.",
  b: "How many outlets wrote about the race in 24 hours, and the effective number: ten stories with eight from one paper count as about two."};
function drawBoard(doc) {
  const host = $("#boardhost"); if (!host || !doc) return;
  const b = BOARD, k = MEAS, rows = boardRows(doc, b, k);
  $("#mhelp").innerHTML = MHELP[k] + ` <span class="muted">${NOT[k]}</span>`;
  $$("#bseg button").forEach(x => x.setAttribute("aria-pressed", String(x.dataset.b === b)));
  $$("#mseg button").forEach(x => x.setAttribute("aria-pressed", String(x.dataset.m === k)));
  GRID_ = gridTable(host, {cols: colsFor(doc, b, k), rows, sort: [{key: "i", dir: "asc"}], page: 25, rowId: r => r.id, detail: detailFor(doc, b, k),
    empty: EMPTY[k], count: rs => `${plural(rs.length, "race")} ranked on this board` + (((doc.boards || {})[b] || {}).n ? ` of ${num(doc.boards[b].n)} on it` : "")});
}
function wireBoards(doc) {
  $$("#bseg button").forEach(x => x.addEventListener("click", () => { BOARD = x.dataset.b; store.set("night:feedboard", BOARD); NIGHTLIVE.ready($("#boardhost")); drawBoard(doc); }));
  $$("#mseg button").forEach(x => x.addEventListener("click", () => { MEAS = x.dataset.m; store.set("night:feedmeasure", MEAS); NIGHTLIVE.ready($("#boardhost")); drawBoard(doc); }));
  drawBoard(doc);
}

/* ---------- headlines and posts ---------- */
const CONF = {h: ["h", "placed by a candidate&rsquo;s name or the race&rsquo;s own words"], m: ["m", "placed by the places the story names"], l: ["l", "placed by where the outlet is"]};
function headsHTML(list, doc, opt) {
  opt = opt || {};
  if (!list.length) return `<p class="nempty">${opt.empty || "No headlines yet."}</p>`;
  return `<ul class="heads">${list.map(h => {
    const [t, outlet, head, url, rk, st, conf] = h, u = safeURL(url), id = rk ? full(doc, rk) : "", c = CONF[conf] || CONF.l;
    return `<li>${u ? `<a href="${esc(u)}" target="_blank" rel="noopener noreferrer">${esc(head)}</a>` : `<span>${esc(head)}</span>`}
      <div class="meta"><b>${esc(outlet)}</b><span>${esc(fmtTime(t))}</span>${id ? `<a href="#race=${esc(id)}">${esc(labelOf(doc, id))}${opt.state ? "" : ", " + esc(id.slice(5, 7))}</a>` : st ? `<a href="#state=${esc(st)}">${esc(SNAME(st))}</a>` : ""}<span class="conf ${c[0]}">${c[1]}</span></div></li>`; }).join("")}</ul>`
    + `<p class="mhelp">Headline, outlet, time and a link only; the stories are the outlets&rsquo; own. Some are found through the <a href="${esc(BOOT.gdelt)}" target="_blank" rel="noopener">GDELT Project</a>.</p>`;
}
function postsHTML(doc) {
  if (!doc || doc.posts === "off" || !BOOT.src.posts) return `<p class="nempty">Posts from newsrooms, election offices and candidates&rsquo; official accounts will appear here once the site has a public address for reports, which the services&rsquo; rules ask for. Until then the feed shows headlines and counts.</p>`;
  if (!doc.posts.length) return `<p class="nempty">No official posts yet.</p>`;
  return `<ul class="heads">${doc.posts.map(p => { const u = safeURL(p[4]); return `<li><span>${esc(p[3])}</span><div class="meta"><b>${esc(p[1])}</b><span>${esc(capital(p[2]))}</span><span>${esc(fmtTime(p[0]))}</span>${u ? `<a href="${esc(u)}" target="_blank" rel="noopener noreferrer">The post</a>` : ""}</div></li>`; }).join("")}</ul>`;
}

/* ---------- the map of coverage ---------- */
let MAPV = null;
const NOFILL = "color-mix(in srgb,var(--ink) 7%,var(--surface))";      /* no items: a faint grey in every look (high contrast's --line is black) */
function mapHTML() {
  return `<section class="bsec" id="map"><h2>Coverage by state</h2><p class="sub">Each state shaded by its news items in the window for every 100,000 residents, counting items placed on its races or its places. Tap a state for its own boards and headlines.</p>
    <div class="usmapgrid"><div class="mapcol"><div class="usbox"><svg class="usvg" id="feedmap" viewBox="0 0 975 610" role="group" aria-label="Map of the states: coverage per 100,000 residents" aria-describedby="feedmaphelp"></svg></div>
      <div class="nlegend" id="feedlegend"></div><p class="sr" id="feedmaphelp">The map is a picture of the list beside it and of the table of every state below it.</p></div>
      <aside class="mapside" id="feedside" aria-live="polite"></aside></div>
    <details class="nfold"><summary>Every state, as a table</summary><div class="tblwrap" id="sttbl"></div></details></section>`;
}
function stepsOf(vals) {      // five steps between the states' own figures (equal groups), for the shading
  const v = vals.filter(x => x > 0).sort((a, b) => a - b); if (!v.length) return [];
  return [1, 2, 3, 4].map(q => v[Math.min(v.length - 1, Math.floor(q * v.length / 5))]);
}
const stepOf = (x, br) => !(x > 0) ? -1 : br.filter(b => x >= b).length;
function drawMap(doc) {
  const svg = $("#feedmap"); if (!svg || !MAPD) return;
  const st = (doc && doc.st) || {}, br = stepsOf(Object.values(st).map(s => s[3])), ops = [.26, .42, .58, .76, .95];
  const body = [defsHTML("fd", 7)];
  Object.keys(MAPD.d).forEach(c => {
    const s = st[c], k = s ? stepOf(s[3], br) : -1, label = `${SNAME(c)}: ${s ? `${plural(s[0], "item")}, ${f2(s[3] || 0)} per 100,000 residents` : "no items"}`;
    body.push(shapeHTML(MAPD.d[c], k < 0 ? {cls: "nr"} : {c: "var(--verd)", op: ops[k]}, "fd", `data-st="${c}" tabindex="0" role="link" aria-label="${esc(label)}"`));
  });
  svg.innerHTML = body.join("");
  $$("path.s", svg).forEach(p => p.classList.remove("nr"));      /* every state can be opened, items or none */
  $$("path.s", svg).forEach(p => { if (!st[p.dataset.st] || !(st[p.dataset.st][0] > 0)) { p.style.fill = NOFILL; } });
  const lab = ["fewest", "", "", "", "most"];
  $("#feedlegend").innerHTML = `<span><i class="lgsw" style="background:${NOFILL}"></i>No items</span>` + (br.length ? ops.map((o, i) => `<span><i class="lgsw" style="background:color-mix(in srgb,var(--verd) ${Math.round(o * 100)}%,var(--surface))"></i>${i === 0 ? "Fewest per 100,000" : i === 4 ? "Most" : ""}</span>`).join("") : "");
  const top = Object.entries(st).filter(([c, s]) => s[0] > 0).sort((a, b) => b[1][3] - a[1][3]).slice(0, 8);
  $("#feedside").innerHTML = `<span class="kick">Most coverage per 100,000 residents</span>` + (top.length ? `<ol class="toplist">${top.map(([c, s]) => `<li><a href="#state=${c}"><b>${esc(SNAME(c))}</b><span>${f2(s[3])} &middot; ${plural(s[0], "item")}</span></a></li>`).join("")}</ol>` : `<p class="muted">No state has items in the window yet.</p>`);
  if (MAPV) MAPV.abort();
  MAPV = new AbortController();
  const pz = svgPanZoom(svg, svg.parentNode, [0, 0, 975, 610], {signal: MAPV.signal});
  svg.addEventListener("click", e => { if (pz.wasDrag()) return; const p = e.target.closest("path.s[data-st]"); if (p) location.hash = "state=" + p.dataset.st; });
  svg.addEventListener("keydown", e => { const p = e.target.closest("path.s[data-st]"); if (p && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); location.hash = "state=" + p.dataset.st; } });
  const rows = Object.keys(BOOT.states).filter(c => MAPD.d[c] || st[c]).map(c => ({c, name: SNAME(c), s: st[c] || [0, 0, null, 0]}));
  gridTable($("#sttbl"), {cols: [{key: "name", label: "State", val: r => r.name, html: r => `<a href="#state=${r.c}">${esc(r.name)}</a>`},
    {key: "cr", label: "Per 100,000", num: true, val: r => r.s[3] || 0, html: r => f2(r.s[3] || 0)}, {key: "n", label: "Items", num: true, val: r => r.s[0] || 0},
    {key: "o", label: "Outlets", num: true, val: r => r.s[1] || 0}, {key: "pop", label: "Residents", num: true, val: r => r.s[2] || 0, html: r => r.s[2] ? num(r.s[2]) : ""}],
    rows, sort: [{key: "cr", dir: "desc"}], page: 60});
}

/* ---------- the pages ---------- */
function homeHTML(doc) {
  return heroHTML("Election Night", "The feed", "News headlines about the races, posts from official accounts, and a leaderboard of the races getting the most attention, and the least for how close they are.")
    + pausedHTML() + (doc ? asOfHTML(doc) : noFiguresHTML())
    + (doc ? mapHTML() + boardsHTML(doc) : "")
    + `<section class="bsec" id="heads"><h2>The newest headlines</h2><p class="sub">Placed on a race or a state by the words in the headline. Tap a race for its own figures.</p>${doc ? headsHTML(doc.h || [], doc) : `<p class="nempty">No headlines yet.</p>`}</section>`
    + `<section class="bsec" id="posts"><h2>Official posts</h2>${postsHTML(doc)}</section>`
    + `<p class="rlinks"><a href="#how">How the feed is counted</a><a href="${esc(BOOT.links.night)}">Election Night</a>${BOOT.links.us ? `<a href="${esc(BOOT.links.us)}">Results across the country</a>` : ""}</p>`;
}
function stateHTML(code, doc, rf) {
  const S = doc && doc.st && doc.st[code], name = SNAME(code);
  const ws = rf ? Object.keys(rf.r).length : 0;
  return heroHTML(`<a href="#">The feed</a> &middot; ${esc(name)}`, esc(name), `News headlines about ${esc(name)}&rsquo;s races and the leaderboard of its races${ws ? `, ${plural(ws, "race")} in all` : ""}, each ranked against the races of its own level across the country.`)
    + pollsHTML(BOOT.polls[code], name) + pausedHTML() + (doc ? asOfHTML(doc) : noFiguresHTML())
    + (S ? `<div class="nstat"><p><b>${plural(S[0], "news item")}</b> from ${plural(S[1], "outlet")} in the window: ${f2(S[3] || 0)} for every 100,000 of the state&rsquo;s ${num(S[2])} residents.</p></div>` : "")
    + (doc ? boardsHTML(doc, name) : "")
    + `<section class="bsec"><h2>Headlines</h2>${doc ? headsHTML((doc.h || []).filter(h => h[6] !== "l"), doc, {state: true, empty: "No headlines placed on this state&rsquo;s races or places yet."}) : `<p class="nempty">No headlines yet.</p>`}
      ${doc && (doc.h || []).some(h => h[6] === "l") ? `<details class="nfold"><summary>Headlines placed only by where the outlet is</summary><p class="mhelp">These stories come from outlets based in ${esc(name)}, but nothing in the headline ties them to a race or a place. They count for no race.</p>${headsHTML(doc.h.filter(h => h[6] === "l"), doc, {state: true})}</details>` : ""}</section>`
    + `<section class="bsec"><h2>Official posts</h2>${postsHTML(doc)}</section>`
    + outletsHTML(code)
    + `<p class="rlinks"><a href="#">Every state</a><a href="#how">How the feed is counted</a>${BOOT.links.states[code] ? `<a href="${esc(BOOT.links.states[code])}">${esc(name)}&rsquo;s results</a>` : ""}</p>`;
}
function outletsHTML(code) {
  const os = (BOOT.src.by_state || {})[code] || [];
  return `<details class="nfold"><summary>The outlets read for ${esc(SNAME(code))}</summary><p class="mhelp">${os.length ? `${andList(os.map(esc))}, read through their own public feeds, with the ${num(BOOT.src.national)} national outlets and everything the GDELT Project finds.` : "No outlet of this state answered with a public feed; its stories reach the feed through the GDELT Project and the national outlets."}</p></details>`;
}
function raceHTML(id, doc, rf) {
  const code = id.slice(5, 7), name = SNAME(code), e = entry(doc, id), lab = labelOf(doc, id, rf), b = boardOf(doc, id, rf);
  const x = rf && rf.r ? rf.r[shortOf(rf, id)] : null;
  if (!x && !(doc && doc.rl && doc.rl[shortOf(doc, id)])) return heroHTML(`<a href="#">The feed</a>`, "Not a race this feed follows", "") + `<p class="nempty">The feed follows the races for Congress, governor and the other statewide offices in every state, and every race in Minnesota.</p>`;
  const pop = (e && e.pop) || (x && x[2]), how = x ? (rf.how[x[4]] || "") : "", approx = x ? x[3] : (e && e.ax);
  const heads = doc ? (doc.h || []).filter(h => h[4] && full(doc, h[4]) === id) : [];
  const results = id.length > 9 && BOOT.links.mn && code === "MN" && !/^2026-MN-[HS]\d/.test(id) ? BOOT.links.mn + "#race=" + id : BOOT.links.us ? BOOT.links.us + "#race=" + id : "";
  return heroHTML(`<a href="#">The feed</a> &middot; <a href="#state=${code}">${esc(name)}</a>`, esc(lab), b ? `On the board for ${esc(BNAME[b] || b)}.` : "")
    + pollsHTML(BOOT.polls[code], name) + pausedHTML() + (doc ? asOfHTML(doc) : noFiguresHTML())
    + `<section class="bsec"><h2>The four measures</h2>${ANALYSIS}${measuresHTML(e, b, doc, pop)}
      <p class="mhelp">Residents: ${pop ? num(pop) : "no Census figure"}${how ? `, from the Census Bureau&rsquo;s American Community Survey (2020 to 2024) for ${esc(how)}` : ""}.${approx ? " The district&rsquo;s own count is not on file, so the counties it lies in stand in, and its rate per 100,000 reads low." : ""}</p>
      ${e && e.sp ? `<p class="mhelp"><b>${plural(e.sp, "person", "people")}</b> posted about this race in the window (each person once an hour, counted from Bluesky&rsquo;s and Mastodon&rsquo;s open streams; never shown or named).</p>` : ""}</section>`
    + `<section class="bsec"><h2>Headlines about this race</h2>${headsHTML(heads, doc || {}, {state: true, empty: "No headline has named this race in the newest update."})}</section>`
    + `<p class="rlinks">${results ? `<a href="${esc(results)}">The count</a>` : ""}${BOOT.links.fc ? `<a href="${esc(BOOT.links.fc + "#race=" + id)}">The forecast</a>` : ""}<a href="#state=${code}">${esc(name)} in the feed</a><a href="#how">How the feed is counted</a></p>`;
}
function howHTML() {
  const S = BOOT.src, A = S.accounts || {};
  return heroHTML(`<a href="#">The feed</a>`, "How the feed is counted", "Every figure on the feed is counted from public headlines and posts by the rules below, and each one shows its own arithmetic.")
    + `<section class="bsec fhow">${ANALYSIS}
    <h3>What is read</h3>
    <p>Headlines from ${num(S.outlets)} news outlets&rsquo; own public feeds (${num(S.national)} national outlets, and outlets in ${num(S.outlet_states)} states${(S.by_state || {}).DC ? " and the District of Columbia" : ""}), and the stories the <a href="${esc(BOOT.gdelt)}" target="_blank" rel="noopener">GDELT Project</a> finds in its files every 15 minutes. The page shows a headline, its outlet, its time and a link: never the story itself or a summary of it.</p>
    <p>Posts are read from Bluesky&rsquo;s open stream, Mastodon&rsquo;s public tag timelines and official YouTube channels. Only newsrooms&rsquo;, election offices&rsquo; and candidates&rsquo; official accounts can be shown (${num(A.newsroom || 0)} newsroom, ${num(A["election office"] || 0)} election office and ${num(A.candidate || 0)} candidate accounts so far), each one linked from the owner&rsquo;s own website and pointing back to it. ${S.posts ? "" : "None is shown until the site has a public address for reports. "}Everyone else is counted, never shown or named: a post is matched to a race in memory and adds one to that race&rsquo;s count; who posted is never kept.</p>
    <p>Most candidates post where this site does not read: X needs a paid service; Facebook, Instagram and Threads give no open access; TikTok and Reddit need a sign-up or approval. The Associated Press and Reuters publish no public feeds; their stories reach the feed through the outlets that carry them.</p>
    <h3>Placing a story</h3>
    <ul><li><b>A candidate&rsquo;s name or the race&rsquo;s own words</b> in the headline, in the right state: the story counts for that race.</li>
      <li><b>The places the story names</b> (as GDELT reads them), where they agree with the outlet&rsquo;s own state: the story counts for that place&rsquo;s races.</li>
      <li><b>Only where the outlet is</b>: shown on that state&rsquo;s page alone, and it counts for no race.</li></ul>
    <p>A post is placed only by a race or a place named in its text, never by where anyone is.</p>
    <h3>The counting rules</h3>
    <ul><li>One story is one address: the same story found twice counts once.</li><li>The same wire story counts once for each outlet that runs it.</li>
      <li>At most 3 items an outlet a race in each window, so one big outlet cannot carry a race alone.</li><li>A site that links to others&rsquo; stories counts as the outlet it links to.</li>
      <li>People who post are counted once a race an hour; reposts are not read.</li>
      <li>The window is the last 24 hours before Election Day&rsquo;s first polls close, then the last 60 minutes. News items and posts are separate numbers.</li></ul>
    <h3>Coverage per 100,000 residents</h3>
    <p class="formula">raw = 100,000 &times; N &divide; residents<br>shown = 100,000 &times; (N + R) &divide; (residents + 100,000)</p>
    <p>N is the race&rsquo;s news items in the window. R is the board&rsquo;s own rate: all its races&rsquo; items per 100,000 of all their residents. Adding 100,000 residents at that rate keeps a school board of 5,000 people with two stories from scoring 40 and topping the board; its raw figure is printed beside it. A race is ranked once it has 3 or more items from 2 or more outlets. Residents come from the Census Bureau&rsquo;s American Community Survey, 2020 to 2024 (table B01003), for the race&rsquo;s own area: the state, the congressional district, the legislative district, the county, the city or township, the school district. Where a district has no figure of its own, the counties it lies in stand in and the page says so. Census figures describe places, never voters.</p>
    <h3>Attention gap</h3>
    <p class="formula">gap = percentile of closeness &minus; percentile of coverage, within the board (&minus;100 to +100)<br>closeness = 1 &minus; |margin|, margin = (first &minus; second) &divide; (first + second)</p>
    <p>The margin is the count&rsquo;s once 20% of the expected vote is counted; before that it is the forecast&rsquo;s median. With neither, the race is not ranked. Where several seats are filled, the margin is between the last seat and the first name below it. Retention votes and races with one name a seat are left out, and so are races where the forecast finds nothing in the record to favour anyone. Close races with no coverage at all are included: that is the point. A positive gap means closer than its coverage suggests.</p>
    <h3>Momentum</h3>
    <p class="formula">momentum = (last hour + 1) &divide; (hour before + 1)</p>
    <p>Each hour counts news items and the people who posted. A race is ranked once the two hours hold 10 or more. It is marked rising only when the last hour is above the 95% upper bound of the hour before: the rate at which a count as low as the hour before&rsquo;s has only a 5% chance (3 to 6 is ordinary; 30 to 60 is not).</p>
    <h3>Source breadth</h3>
    <p class="formula">outlets = distinct outlets in 24 hours<br>effective = exp(&minus;&Sigma; p ln p), p each outlet&rsquo;s share of the race&rsquo;s items</p>
    <p>Ten stories with eight from one paper are 3 outlets but about 1.9 effective. A race is ranked once it has 3 or more items in 24 hours.</p>
    <h3>The boards</h3>
    <p>${BOOT.boards.map(([k, w]) => esc(w)).join("; ")}. A national outlet counts like any other, and a race for the Senate is ranked only against other statewide races, so a big market does not top a board by being big.</p>
    <h3>What it is not</h3>
    <p>These figures count attention, not importance and not support: a race can be important and quiet, and a story can be critical. They are labelled Analysis everywhere they appear.</p></section>`;
}

/* ---------- drawing a route ---------- */
let DRAWN = null;
function render(keepScroll) {
  const r = route(), doc = FEED.us;
  DRAWN = r;
  if (MAPV) { MAPV.abort(); MAPV = null; }
  if (r.v === "how") { app.innerHTML = howHTML(); finish(r, keepScroll); return; }
  if (r.v === "home") {
    if (r.board) BOARD = r.board;
    if (r.measure) MEAS = r.measure;
    app.innerHTML = homeHTML(doc);
    if (doc) { drawMap(doc); wireBoards(doc); }
    finish(r, keepScroll);
    if (r.board && !keepScroll) { const b = $("#boards"); if (b) b.scrollIntoView({block: "start"}); }
    return;
  }
  if (!BOOT.states[r.code]) { app.innerHTML = heroHTML(`<a href="#">The feed</a>`, "Not found", "") + `<p class="nempty">There is no such state or race in the feed.</p>`; finish(r, keepScroll); return; }
  app.innerHTML = `<p class="loading muted">Loading&hellip;</p>`;
  Promise.all([stateDoc(r.code), raceFile(r.code)]).then(([sd, rf]) => {
    if (DRAWN !== r) return;
    app.innerHTML = r.v === "state" ? stateHTML(r.code, sd, rf) : raceHTML(r.id, sd, rf);
    if (r.v === "state" && sd) wireBoards(sd);
    finish(r, keepScroll);
  });
}
function finish(r, keepScroll) {
  document.title = (r.v === "home" ? "Election Night: the feed" : r.v === "how" ? "How the feed is counted" : r.v === "state" ? `The feed: ${SNAME(r.code)}` : "The feed: a race") + " \u00b7 The Civic Archive";
  if (!keepScroll && r.v !== "home") { scrollTo(0, 0); try { app.focus({preventScroll: true}); } catch (e) {} }
}
function onNew() {
  const host = $("#boardhost");
  if (host && document.activeElement && host.contains(document.activeElement)) { NIGHTLIVE.ready(host, () => render(true)); return; }
  if (host && GRID_ && scrollY > 200) { NIGHTLIVE.ready(host, () => render(true)); return; }
  render(true);
}
if (LIVE.rehearsal) { const b = $("#nreh"); if (b) { b.hidden = false; b.innerHTML = "<b>Rehearsal:</b> replayed figures. Not 2026 coverage."; } }
Promise.all([getJSON(BOOT.map), NIGHTLIVE.off() ? Promise.resolve(null) : feedGet().then(feedCommit, () => { FEED.why = FEED.why || "nofile"; })]).then(([m]) => {
  MAPD = m;
  render();
  addEventListener("hashchange", () => { const r = route(); if (r.code && !(r.code in FEED.st) && FEED.us) { stateDoc(r.code).then(() => render()); } else render(); });
  document.addEventListener("night:look", () => render(true));
  NIGHTLIVE.start({get: feedGet, commit: feedCommit, when: () => FEED.us && FEED.us.t, onNew, onTick: () => { const p = $(".nstat [class~=stale]"); if (!!livePause() !== !!p) render(true); }});
}, () => { app.innerHTML = `<p class="nempty">The feed could not be loaded. Check your connection and open the page again.</p>`; });
"""


def page_html(P, boot, practice, generated, version, links):
    nav = "".join(f'<a href="{h}"{c}>{w}</a>' for h, w, c in (("#map", "Map", ' class="x"'), ("#boards", "Leaderboard", ""), ("#heads", "Headlines", ""),
                                                               ("#posts", "Posts", ' class="x"'), ("#how", "How it is counted", "")))
    foot = " &middot; ".join(x for x in (
        f'<a href="{links["night"]}">Election Night</a>',
        f'<a href="{links["night"]}us/">Results across the country</a>' if links.get("us") else "",
        f'<a href="{links["night"]}forecasts/">Forecasts</a>' if links.get("fc") else "",
        f'<a href="{links["front"]}">The Civic Archive front door</a>') if x)
    desc = ("News headlines and official posts about the races on election night, with a leaderboard of coverage per 100,000 "
            "residents, attention against closeness, momentum and source breadth, each figure with its arithmetic.")
    page = PAGE
    for key, value in (("__CSS__", P["CSS"]), ("__BALLOT_CSS__", P["BALLOT_CSS"]), ("__NIGHT_CSS__", N.NIGHT_CSS), ("__USMAP_CSS__", N.USMAP_CSS),
                       ("__FONTS__", N.fonts_css()), ("__HEADSCRIPT__", N.head_script()), ("__CHANGELOG__", P["CHANGELOG"]), ("__GRID__", P["GRID"]),
                       ("__GEO__", P["GEO"]), ("__NIGHT_JS__", N.NIGHT_JS), ("__USMAP_JS__", N.USMAP_JS), ("__PAGE_JS__", PAGE_JS),
                       ("__TOPBAR__", N.top_bar("Election Night: the feed", nav, door_href=links["night"])),
                       ("__CLBOX__", N.changelog_box()),
                       ("__BANNER__", f'<div class="nbanner" role="note"><b>{PRACTICE_LABEL.split(".")[0]}.</b> Not 2026 coverage.</div>\n' if practice else ""),
                       ("__BRAND__", N.brand_tags(links["icons"], "Election Night: the feed · The Civic Archive", desc, "feed.png", "night/feed/")),
                       ("__FOOTLINKS__", foot)):
        if page.count(key) != 1:
            raise SystemExit(f"build_night_feed: the page should hold {key} exactly once (it holds it {page.count(key)} times)")
        page = page.replace(key, value)
    page = page.replace("__DESC__", esc(desc)).replace("__VERSION__", esc(version)).replace("__GENERATED__", generated)
    return page.replace("__BOOT__", json.dumps(boot, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/"))


def build(dev_root, version=None, practice=None, say=print, sample_db=None, sample_now=None):
    """The feed page. Returns {path written: bytes}. sample_db (tests only): with practice, the feed's files worked out
    from that database are written into the practice live folder beside the page, unless that folder is the kit's own
    site/practice/night-live (another builder's)."""
    from build_ballot_state_dev import copy_fonts, slim_page, write_if_changed
    from build_site_dev import read_changelog
    from election.feeds.keywords import STATE_NAMES
    from build_state_dev import borrow
    dev_root = os.path.abspath(dev_root)
    changelog = read_changelog(os.path.join(HERE, "CHANGELOG.md"))
    version = version or ((changelog[0].get("version") if changelog else "") or "")
    if practice:
        root = N.practice_root(dev_root)
        out_dir = os.path.join(root, "night", "feed")
        links = {"night": "../../../dev/night/", "front": "../../../dev/", "icons": "../../../dev/"}
        live = "../../night-live/"
        rel_night = os.path.join(root, "night")
    else:
        out_dir = os.path.join(dev_root, "night", "feed")
        links = {"night": "../", "front": "../../", "icons": "../../"}
        live = "../../../night-live/"
        rel_night = os.path.join(dev_root, "night")
    links["us"] = os.path.exists(os.path.join(rel_night, "us", "index.html"))
    links["fc"] = os.path.exists(os.path.join(rel_night, "forecasts", "index.html"))
    has_mn = os.path.exists(os.path.join(rel_night, "mn", "index.html"))
    say(f"Election Night, the feed{' (practice)' if practice else ''}: building {os.path.relpath(out_dir, HERE)}")
    written = {}
    files, races = race_files(say)
    rv = {}
    for code, doc in sorted(files.items()):
        text = json.dumps(doc, ensure_ascii=False, separators=(",", ":"))
        bad = N.kit_names(text)
        if bad:
            raise SystemExit(f"build_night_feed: the races file of {code} would name the kit's own files: {bad}")
        p = os.path.join(out_dir, "data", "races", f"{code.lower()}.json")
        write_if_changed(p, text)
        written[p] = len(text.encode("utf-8"))
        rv[code] = sha10(text)
        if written[p] > RACES_LIMIT:
            say(f"  WARNING: data/races/{code.lower()}.json is {written[p] / 1e3:,.0f} KB, over its {RACES_LIMIT / 1e3:,.0f} KB budget")
    mp = N.us_map_doc()
    map_text = json.dumps(mp, ensure_ascii=False, separators=(",", ":"))
    write_if_changed(os.path.join(out_dir, "data", "map.json"), map_text)
    written[os.path.join(out_dir, "data", "map.json")] = len(map_text.encode("utf-8"))
    copy_fonts(out_dir)
    with open(POLL_HOURS, encoding="utf-8") as fh:
        polls = polls_boot(json.load(fh))
    codes = sorted(set(files) | set(polls) | set(mp["d"]))
    states = {c: STATE_NAMES.get(c, c) for c in codes}
    state_links = {}
    for c in codes:
        if has_mn and c == "MN":
            state_links[c] = links["night"] + "mn/"
        elif links["us"]:
            state_links[c] = links["night"] + "us/#state=" + c
    from election.feeds import measures as M
    boot = {"map": f"data/map.json?v={sha10(map_text)}", "races": "data/races/", "rv": rv, "live": {"base": live, "dir": ""},
            "changelog": changelog, "states": states, "boards": [list(b) for b in M.BOARDS], "polls": polls, "gdelt": GDELT,
            "src": sources_boot(),
            "links": {"night": links["night"], "us": links["night"] + "us/" if links["us"] else "", "fc": links["night"] + "forecasts/" if links["fc"] else "",
                      "mn": links["night"] + "mn/" if has_mn else "", "states": state_links, "nass": NASS}}
    if practice:
        boot["practice"] = {"label": PRACTICE_LABEL}
        if sample_db:
            live_root = os.path.join(N.practice_root(dev_root), "night-live")
            if os.path.abspath(live_root) == os.path.abspath(os.path.join(HERE, "site", "practice", "night-live")):
                raise SystemExit("build_night_feed: sample figures are written only into a scratch practice folder, never site/practice/night-live")
            now = M.parse_time(sample_now) if sample_now else None
            doc = M.compute(now=now, db=sample_db, say=say)
            boot["practice"]["now"] = M.iso(doc["t"])
            seq = 1
            base = f"s/{seq:06d}/"
            for code in ["US"] + sorted(files):
                fd = M.page_json(code, db=sample_db, now=doc["t"])
                if fd:
                    text = json.dumps(fd, ensure_ascii=False, separators=(",", ":"))
                    p = os.path.join(live_root, "s", f"{seq:06d}", "feed", f"{code.lower()}.json")
                    write_if_changed(p, text)
                    written[p] = len(text.encode("utf-8"))
            nowdoc = {"v": 1, "seq": seq, "at": M.iso(doc["t"]), "next": M.iso(doc["t"] + dt.timedelta(minutes=10)), "run": "running",
                      "rehearsal": False, "practice": True, "label": "test items", "base": base, "st": {}, "fd": M.newest()}
            write_if_changed(os.path.join(live_root, "now.json"), json.dumps(nowdoc, separators=(",", ":")))
    P = N.parts()
    P["GEO"] = borrow("GEO")
    page = page_html(P, boot, practice, N.generated(), version, links)
    whole = len(page.encode("utf-8"))
    page = slim_page(page, "Election Night feed")
    page = N.quiet(page)
    checks = N.page_checks("night/feed/index.html", page, SHELL_LIMIT, say)
    if not practice and os.path.exists(os.path.join(dev_root, "shell", "rider.js")):
        i = page.rfind("</body>")
        page = page[:i] + RIDER + page[i:]      # the companion and the page guide, as build_shell.ride() puts them on every page with its own top bar
    write_if_changed(os.path.join(out_dir, "index.html"), page)
    written[os.path.join(out_dir, "index.html")] = len(page.encode("utf-8"))
    rtotal = sum(v for k, v in written.items() if os.sep + "races" + os.sep in k)
    say(f"  {len(races):,} races in {len(files)} states; wrote index.html {checks['bytes'] / 1e3:,.0f} KB ({whole / 1e3:,.0f} KB before slimming; "
        f"budget {SHELL_LIMIT / 1e3:,.0f} KB), data/races/ {rtotal / 1e3:,.0f} KB (largest {max((v for k, v in written.items() if os.sep + 'races' + os.sep in k), default=0) / 1e3:,.0f} KB), "
        f"data/map.json {written[os.path.join(out_dir, 'data', 'map.json')] / 1e3:,.0f} KB")
    return written


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=os.path.join(HERE, "site", "dev"), help="the draft's root (default site/dev)")
    ap.add_argument("--practice", action="store_true", help="into site/practice/ (never published)")
    ap.add_argument("--sample-db", default=None, help="tests only, with --practice and a scratch --root: feed files from this database")
    ap.add_argument("--sample-now", default=None)
    a = ap.parse_args()
    build(a.root, practice="2024" if a.practice else None, sample_db=a.sample_db, sample_now=a.sample_now)


if __name__ == "__main__":
    main()
