#!/usr/bin/env python3
"""
build_night_home.py - the home of Election Night, the site's third space (John, 2026-10-09 and 2026-10-10).

    python build_night_home.py [--root site/dev]

writes <root>/night/index.html on the shared shell (the top bar, Reading & access, Help, the companion, the tab bar on
phones), as the front door, Method and Access are, and the four share images in <root>/night/og/ (home, results, feed,
forecasts), drawn by brand.site_card with words only: no count, percentage or chance ever goes on an image.

The page: three doors (Results, The feed, Forecasts) and Minnesota at every level; when the polls close, state by state,
from election/poll_hours.json (each state's statute or election office, checked by hand), shown in the reader's own
time zone; each state's polling-place lookup; what is read live and how; the rules the space keeps. Every number is
counted at build time from the records on this computer (read only). A door whose page is not built yet says so and
links nowhere. Each main paragraph has a plain-language twin, checked here at Flesch-Kincaid grade 7 or lower.

The shell's files are not rebuilt here (the front door's build owns them): the page uses the stylesheet, script and
boot code the front door already links, unless a caller that has just built the shell passes its result as `A`.

build(dev_root, version=None, practice=None, say=print, A=None) -> {written path: bytes}. The home carries no live
figures, so a practice build writes nothing.
"""

import argparse
import datetime as dt
import glob
import html
import io
import json
import os
import re
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_shell as S      # noqa: E402
import build_home as H       # noqa: E402

ELECTION_DAY = "2026-11-03"
esc = lambda s: html.escape(str(s), quote=True)
ZONE_WORDS = {"ET": "Eastern time", "CT": "Central time", "MT": "Mountain time", "PT": "Pacific time", "AKT": "Alaska time", "HT": "Hawaii-Aleutian time"}
GRADE_MAX = 7.0
KIT_NAMES = re.compile(r"\b[a-z]+(?:_[a-z0-9]+)+\.(?:py|json|sqlite)\b|\b[\w-]+\.sqlite\b|\brubric_v1\b|\bCHANGELOG\b|\bpoll_hours\b")


# ============================== what the records hold (read only) ==============================

def _ro(path):
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def _one(con, q, *p):
    try:
        r = con.execute(q, p).fetchone()
        return (r[0] or 0) if r else 0
    except sqlite3.Error:
        return 0


def facts(dev_root):
    F = {"congress": 0, "senate": 0, "statewide": 0, "statewide_states": 0, "mn_races": 0, "states_live": 0, "states_care": 0,
         "states_hand": 0, "states_link": 0, "registry": 0, "outlets": 0, "forecast_races": 0, "pages": {}}
    db = os.path.join(HERE, "ballot_2026.sqlite")
    if os.path.exists(db):
        con = _ro(db)
        F["congress"] = _one(con, "SELECT COUNT(*) FROM races")
        F["senate"] = _one(con, "SELECT COUNT(*) FROM races WHERE race_id LIKE '%-S%'")
        con.close()
    db = os.path.join(HERE, "ballot_local_2026.sqlite")
    if os.path.exists(db):
        con = _ro(db)
        F["statewide"] = _one(con, "SELECT COUNT(*) FROM sl_races WHERE level = 'statewide'")
        F["statewide_states"] = _one(con, "SELECT COUNT(DISTINCT state) FROM sl_races WHERE level = 'statewide'")
        F["mn_races"] = _one(con, "SELECT COUNT(*) FROM sl_races WHERE state = 'MN'")
        con.close()
    # each state's registry entry, once written: how its results are read on the night
    for path in glob.glob(os.path.join(HERE, "election", "registry", "*.json")):
        try:
            with open(path, encoding="utf-8") as fh:
                st = (json.load(fh).get("status") or "").lower()
        except (OSError, ValueError, AttributeError):
            continue
        if st in ("live", "care", "hand", "link"):
            F["registry"] += 1
            F["states_" + st] += 1
    db = os.path.join(HERE, "night_feed_2026.sqlite")
    if os.path.exists(db):
        con = _ro(db)
        F["outlets"] = _one(con, "SELECT COUNT(*) FROM outlets")
        con.close()
    db = os.path.join(HERE, "election_model_2026.sqlite")
    if os.path.exists(db):
        con = _ro(db)
        F["forecast_races"] = _one(con, "SELECT COUNT(DISTINCT race_id) FROM race_runs")
        con.close()
    for key in ("us", "mn", "feed", "forecasts"):
        F["pages"][key] = os.path.exists(os.path.join(dev_root, "night", key, "index.html"))
    return F


def poll_hours():
    with open(os.path.join(HERE, "election", "poll_hours.json"), encoding="utf-8") as fh:
        P = json.load(fh)
    missing = [k for k, v in P["states"].items() if not (v.get("source") or {}).get("url") or not (v.get("lookup") or {}).get("url")]
    if len(P["states"]) != 51 or missing:
        raise SystemExit(f"build_night_home: poll hours must cover the 50 states and DC, each with a source and a lookup "
                         f"({len(P['states'])} states; without a source or lookup: {missing})")
    return P


# ============================== the shell's files, as the front door links them ==============================

def shell_assets(dev_root):
    """The stylesheet, script and boot code the front door already uses, so this page never rebuilds the shell."""
    door = os.path.join(dev_root, "index.html")
    try:
        with open(door, encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        raise SystemExit("build_night_home: the front door is not built yet; build it first (it writes the shell this page uses)")
    css = re.search(r'href="\./(shell/shell\.[0-9a-f]{10}\.css)"', text)
    js = re.search(r'src="\./(shell/shell\.[0-9a-f]{10}\.js)"', text)
    boot = re.search(r"<script>(.*?)</script>\s*<link rel=\"stylesheet\" href=\"\./shell/", text, re.S)
    if not (css and js and boot):
        raise SystemExit("build_night_home: could not find the shell's files in the front door's head")
    for rel in (css.group(1), js.group(1)):
        if not os.path.exists(os.path.join(dev_root, rel)):
            raise SystemExit(f"build_night_home: the front door names {rel}, which is missing; rebuild the front door")
    comp_dir = os.path.join(dev_root, "shell", "companions")
    comps = []
    for c in S.companions():
        files = sorted(glob.glob(os.path.join(comp_dir, f'{c["id"]}.*.js')))
        comps.append({k: c[k] for k in ("id", "name", "latin", "rests", "default")} | {"file": os.path.basename(files[-1]) if files else None})
    return {"css": css.group(1), "js": js.group(1), "boot": boot.group(1), "companions": comps}


# ============================== pieces ==============================

def nice_time(local):
    h, m = map(int, local.split(":"))
    ap = "a.m." if h < 12 else "p.m."
    h12 = h % 12 or 12
    return f"{h12}{'' if m == 0 else f':{m:02d}'} {ap}"


def central(utc_iso):
    t = dt.datetime.strptime(utc_iso, "%Y-%m-%dT%H:%M:%SZ") - dt.timedelta(hours=6)
    return nice_time(t.strftime("%H:%M")) + " CST"


def timetable(P):
    """Rows of (moment, [labels]) in closing order; a state whose zones close at different moments is listed in each."""
    rows = {}
    for code, s in P["states"].items():
        zones = s["zones"]
        same = len({z["closes_utc"] for z in zones}) == 1
        mail = " (mail ballots due)" if code in ("OR", "WA") else ""
        for z in (zones[:1] if same else zones):
            if same or len(zones) == 1:
                label = s["name"]
            elif z.get("counties"):
                label = f'{s["name"]}: {ZONE_WORDS[z["zone"]]}, {z["where"][:1].lower() + z["where"][1:]}'
            else:
                label = f'{s["name"]}: {ZONE_WORDS[z["zone"]]}'
            gap = (int(z["latest"][:2]) - int(z["closes"][:2])) if z.get("latest") else 0
            later = (f' (some places stay open up to {H.nw(gap)} hour{"" if gap == 1 else "s"} later)' if gap else "")
            later = later.replace("up to one hour", "up to an hour")
            rows.setdefault(z["closes_utc"], []).append((s["name"], label + mail + later))
    return [(k, [l for _, l in sorted(v)]) for k, v in sorted(rows.items())]


def tile(svg, t="verd"):
    return (f'<span class="tca-ico" data-tile="{t}"><svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">{svg}</svg></span>')


ICONS = {      # drawn like the shell's five: one stroke weight, rounded ends; brass or verdigris tiles, never red or blue
    "results": '<path d="M4 20h16"/><path d="M6.5 20v-6M11 20V9M15.5 20v-8M20 20V5"/><path d="M4 4.5l4 3 4-2.5 4 2"/>',
    "mn": '<path d="M7 3.5h7.5l.8 2.6 2.4 1-.6 2.2 1.4 1.8-1 2.5.9 6.9H7z"/><path d="M10.5 12.5h4M10.5 15.5h4"/>',
    "feed": '<path d="M5 5.5h14v9.5H10.5L6.5 18.5V15H5z"/><path d="M8.5 9h7M8.5 11.8h4.5"/>',
    "forecasts": '<path d="M4 18.5c3.5-1 5-5.5 8-7.5s5.5-1.8 8-4.5"/><path d="M4 14.5c3.5 0 5.5-3.5 8.5-4.5s5-.6 7.5-2.5" stroke-dasharray="1.6 2.6"/><path d="M4 20h16"/>',
}


def door(key, href, kick, title, std, plain, facts_, go, ready, extra=""):
    dl = "".join(f"<div><dd>{esc(v)}</dd><dt>{esc(t)}</dt></div>" for v, t in facts_ if v not in (None, "", 0, "0"))
    head = (f'<h3><a id="door-{key}" href="{href}" aria-labelledby="door-{key} door-{key}-go">{esc(title)}</a></h3>' if ready else
            f'<h3 id="door-{key}">{esc(title)}</h3>')
    go_ = (f'<span class="go" id="door-{key}-go" aria-hidden="true">{esc(go)} {H.ARROW}</span>' if ready else
           '<p class="nh-soon">Opens before Election Day.</p>')
    return f"""<article class="tca-door{'' if ready else ' nh-wait'}" data-door="night-{key}">
<div class="top">{tile(ICONS[key], "brass" if key in ("mn", "forecasts") else "verd")}<span class="kick">{esc(kick)}</span></div>
{head}
{H.para(std, plain)}{extra}
{f'<dl class="facts lvl-detail">{dl}</dl>' if dl else ''}
{go_}
</article>"""


STYLE = """<style>
.nh-notice{display:flex;flex-wrap:wrap;gap:8px 16px;align-items:center;border:1px solid var(--verd);background:var(--verd-soft);border-radius:var(--radius-l);
  padding:calc(var(--sp-unit) * 2) calc(var(--sp-unit) * 2.4);margin-top:calc(var(--sp-unit) * 3);font-family:var(--font-ui)}
.nh-notice p{margin:0;color:var(--ink);font-weight:600}
.nh-notice a{font-weight:700;color:var(--verd-ink)}
:root[data-contrast="high"] .nh-notice{border-width:2px}
.nh-soon{margin:auto 0 0;font-family:var(--font-ui);font-size:var(--fs-s);font-weight:650;color:var(--brass-ink)}
.tca-door.nh-wait{background:var(--surface-2);box-shadow:none}
.nh-when{font-family:var(--font-ui);font-size:var(--fs-s);color:var(--ink);font-weight:600;margin-top:calc(var(--sp-unit) * 1.4)}
.nh-times{width:100%;border-collapse:collapse;font-family:var(--font-ui);font-size:var(--fs-s);line-height:var(--lh-tight)}
.nh-times caption{text-align:left;color:var(--ink-2);font-size:var(--fs-xs);padding-bottom:8px}
.nh-times th,.nh-times td{text-align:left;vertical-align:top;padding:10px 12px 10px 0;border-top:1px solid var(--line)}
.nh-times thead th{font-size:var(--fs-xs);font-weight:750;letter-spacing:.08em;text-transform:uppercase;color:var(--ink-2);border-top:0}
.nh-times tbody th{white-space:nowrap;font-weight:700;color:var(--ink);width:9.5em}
.nh-times td{color:var(--ink-2)}
.nh-times td span{display:inline}
.nh-times td span+span::before{content:" \\00B7 ";color:var(--ink-3, var(--ink-2))}
@media (max-width:520px){.nh-times tbody th{width:auto;white-space:normal}.nh-times thead{position:absolute;clip:rect(0 0 0 0);width:1px;height:1px;overflow:hidden}
  .nh-times tr{display:block;border-top:1px solid var(--line);padding:8px 0}.nh-times th,.nh-times td{display:block;border:0;padding:2px 0}
  .nh-times td span{display:block;padding:2px 0}.nh-times td span+span::before{content:none}}
.nh-wrap{margin-top:calc(var(--sp-unit) * 2.4);overflow-wrap:anywhere}
.nh-src{list-style:none;margin:calc(var(--sp-unit) * 1.4) 0 0;padding:0;display:grid;gap:10px;font-size:var(--fs-s)}
.nh-src li{border-top:1px solid var(--line);padding-top:10px}
.nh-src b{font-family:var(--font-ui)}
.nh-src small{color:var(--ink-2);display:block}
.nh-fold{margin-top:calc(var(--sp-unit) * 2)}
.nh-fold>summary{cursor:pointer;min-height:var(--hit);display:flex;align-items:center;font-weight:650;font-family:var(--font-ui);border-radius:var(--radius-s)}
.nh-fold>summary:focus-visible{outline:var(--focus-w) solid var(--focus);outline-offset:2px}
.nh-tag{display:inline-block;font-family:var(--font-ui);font-size:var(--fs-xs);font-weight:750;letter-spacing:.12em;text-transform:uppercase;border-radius:999px;padding:2px 9px;margin-right:6px;vertical-align:2px}
.nh-tag.fact{color:var(--verd-ink);border:1px solid var(--verd)}
.nh-tag.analysis{color:var(--brass-ink);border:1px solid var(--brass-ink)}
.nh-zone{font-family:var(--font-ui);font-size:var(--fs-xs);color:var(--ink-2);margin-top:6px}
</style>"""


# reader's own clock: times shown in the reader's zone; the polls-open notice while any polls are open on Nov 3; the
# countdown to the first poll closing. Nothing is sent anywhere.
SCRIPT = """<script>
(function () {
  var D = document, B = window.NIGHT_HOME || {};
  var fmt;
  try { fmt = new Intl.DateTimeFormat(undefined, {hour: "numeric", minute: "2-digit", timeZoneName: "short"}); } catch (e) { fmt = null; }
  function show(iso) { if (!fmt) return null; try { return fmt.format(new Date(iso)); } catch (e) { return null; } }
  var els = D.querySelectorAll("time[data-utc]");
  for (var i = 0; i < els.length; i++) { var s = show(els[i].getAttribute("data-utc")); if (s) els[i].textContent = s; }
  var z = D.getElementById("nh-zone");
  if (z && fmt) { try { z.textContent = "Times are in your own time zone (" + Intl.DateTimeFormat().resolvedOptions().timeZone.replace(/_/g, " ") + "), worked out on this device."; } catch (e) {} }
  var now = Date.now(), open = Date.parse(B.firstOpen), last = Date.parse(B.lastClose), first = Date.parse(B.firstClose);
  var n = D.getElementById("nh-open");
  if (n && now >= open && now < last) n.hidden = false;
  var c = D.getElementById("nh-count");
  if (c && now < first && first - now < 864e5) {      /* the days are counted beside the date already; on the day, the hours */
    var mins = Math.round((first - now) / 60000), h = Math.floor(mins / 60);
    c.textContent = h >= 1 ? " That is in about " + h + " hour" + (h === 1 ? "" : "s") + "." : " That is within the hour.";
  }
})();
</script>"""


def faq_html():
    return """<details><summary>Where do the numbers come from?</summary><div class="a"><p>Only from each state's own election office, as it posts them, each with its time. Minnesota's come from the Secretary of State's results files. Where a state publishes no live count this site may read, the page links to the state's own results and adds the official totals when the state certifies them.</p></div></details>
<details><summary>Does this site call races?</summary><div class="a"><p>No. A candidate is &ldquo;ahead in the count so far&rdquo; until the state certifies the result. Forecasts are a computer model's estimate, labelled Analysis, with a range and a track record. The official count decides.</p></div></details>
<details><summary>How fresh are the figures?</summary><div class="a"><p>The pages look for new figures every few minutes. A figure usually reaches this site 10 to 20 minutes after the state posts it, and every number carries the time the state gave it.</p></div></details>
<details><summary>Does this site track me?</summary><div class="a"><p>No page here counts visits. Times are shown in your own time zone, worked out on your device. Where a page offers &ldquo;Use my location&rdquo;, your place is worked out on your device and is not sent anywhere.</p></div></details>"""


def body(F, P, places):
    tt = timetable(P)
    first_close = tt[0][0]
    first_names = " and ".join(sorted({l.split(":")[0] for l in tt[0][1]}))
    last_close = tt[-1][0]
    opens = [z for s in P["states"].values() for z in s["zones"] if z.get("opens")]
    first_open = min(dt.datetime(2026, 11, 3, *map(int, z["opens"].split(":"))) - dt.timedelta(hours={"ET": -5, "CT": -6, "MT": -7, "PT": -8, "AKT": -9, "HT": -10}[z["zone"]])
                     for z in opens).strftime("%Y-%m-%dT%H:%M:%SZ")
    boot = json.dumps({"firstOpen": first_open, "firstClose": first_close, "lastClose": last_close}, separators=(",", ":"))

    vow = '<p class="vow-line"><span>Official counts only.</span><span>Every number with its time.</span><span>No race is called.</span><span>Forecasts labelled Analysis.</span></p>'
    kpis = [(H.n(F["congress"]), "races for Congress"), (H.n(F["statewide"]), f"statewide races, in {H.n(F['statewide_states'])} states"),
            (H.n(F["mn_races"]), "Minnesota races, every level")]
    if F["registry"]:
        kpis.append((H.n(F["states_live"]), "states whose live count is read here"))
    kpi_dl = "".join(f"<div><dd>{v}</dd><dt>{esc(t)}</dt></div>" for v, t in kpis if v not in ("0", ""))
    notice = (f'<div class="nh-notice" id="nh-open" role="status" hidden><p>Polls are still open in some states. If you haven&rsquo;t voted, your vote still counts.</p>'
              f'<a href="#where-to-vote">Find your polling place</a></div>')
    hero = f"""<section class="tca-hero split" aria-labelledby="hero-h">
<div class="tca-wrap">
<div>
<p class="kicker">Election Night</p>
<h1 id="hero-h">{H.words_of("Follow the count, <em>race by race.</em>")}</h1>
{H.para("Results of the November 3 election as each state's own election office posts them, with the time on every number. Minnesota at every level, from the governor to the school board, and every state's races for Congress, governor and the other statewide offices.",
        "See the votes as each state counts them. Each number shows when the state posted it. Minnesota is covered all the way down to school boards.", "lede")}
{vow}
<p class="nh-when">Election Day is {H.day(dt.date.fromisoformat(ELECTION_DAY))}<span class="urgency" data-tca-days="{ELECTION_DAY}"></span>. The first polls close at <time data-utc="{first_close}" datetime="{first_close}">{central(first_close)}</time>, in {esc(first_names)}.<span id="nh-count"></span></p>
{notice}
</div>
<aside class="tca-kpi lvl-detail" aria-labelledby="kpi-h">
<p class="tag">Fact</p>
<h2 id="kpi-h">On the ballot</h2>
<dl>{kpi_dl}</dl>
<p class="note">Counted from the official candidate lists when this page was built.</p>
</aside>
</div>
</section>"""

    pg = F["pages"]
    doors = "\n".join([
        door("results", "us/", "Results", "Results across the country.",
             "Every state's races for Congress, governor and the other statewide offices on one map, with each state's count as its election office posts it. Where a state publishes no live count, the page links to its own results.",
             "See every state's big races on one map. The numbers come from each state.",
             [(H.n(F["congress"]), "races for Congress"), (H.n(F["statewide"]), "statewide races"),
              (H.n(F["states_live"]) if F["registry"] else None, "states read live")], "Open the results", pg["us"]),
        door("mn", "mn/", "Minnesota", "Minnesota at every level.",
             "Every race on Minnesota's ballot, precinct by precinct on one map: statewide, the Legislature, courts, counties, cities, townships and school districts. Use your location to see your own ballot's results.",
             "Every race in Minnesota, down to your precinct. Find your own ballot on the map.",
             [(H.n(F["mn_races"]), "races")], "Open Minnesota", pg["mn"]),
        door("feed", "feed/", "The feed", "What the news is covering.",
             "Headlines from news organizations, with links, and posts from election offices and candidates' official accounts. Everyone else is counted, never shown or named. A leaderboard shows which races draw the most coverage for their size.",
             "See news headlines about each race. Posts from regular people are only counted, never shown.",
             [(H.n(F["outlets"]), "news outlets read")], "Open the feed", pg["feed"]),
        door("forecasts", "forecasts/", "Forecasts", "A model's estimate, never a call.",
             "Each race's chances and likely range of votes from a computer model, labelled Analysis, with its inputs, every run kept, and a record of how it did. The official count decides.",
             "A computer guesses each race's result and shows how sure it is. It is a guess. The vote count decides.",
             [(H.n(F["forecast_races"]), "races with a forecast")], "Open the forecasts", pg["forecasts"]),
    ])
    sec_doors = f"""<section class="tca-sec" id="doors" aria-labelledby="doors-h">
<div class="tca-wrap">
<header>__CHUNK__<p class="tca-kick">Where to go</p><h2 id="doors-h">Three ways in, and Minnesota</h2>
{H.para("The results, the coverage and the forecasts each have their own page, and Minnesota has one for every race on its ballot. The figures come in on the night; until then the pages show the races and who is on the ballot.",
        "Pick a door. The vote counts start on election night. Until then you can see the races.")}</header>
<div class="tca-doors">
{doors}
</div>
</div>
</section>"""

    rows = "".join(f'<tr><th scope="row"><time data-utc="{u}" datetime="{u}">{central(u)}</time></th><td>{"".join(f"<span>{esc(l)}</span>" for l in labels)}</td></tr>'
                   for u, labels in tt)
    split = sorted(s["name"] for s in P["states"].values() if len(s["zones"]) > 1)
    srcs = "".join(
        f'<li><b>{esc(s["name"])}</b>: {esc(s["rule"])}<small>Source: <a href="{esc(s["source"]["url"])}" rel="noopener">{esc(s["source"]["title"])}</a>, checked {esc(H.nice_date(s["source"]["checked"]))}.'
        + (f' {esc(s["source"]["note"])}' if s["source"].get("note") else "")
        + (' Time zones by county: <a href="' + esc(s["zone_source"]["url"]) + '" rel="noopener">the federal time zone boundaries</a>.' if s.get("zone_source") else "")
        + "</small></li>" for s in sorted(P["states"].values(), key=lambda s: s["name"]))
    sec_times = f"""<section class="tca-sec" id="poll-hours" aria-labelledby="times-h">
<div class="tca-wrap">
<header>__CHUNK__<p class="tca-kick"><span class="nh-tag fact">Fact</span>From each state's law or election office</p><h2 id="times-h">When the polls close</h2>
{H.para(f"No state releases results before its polls close. Here is when that happens on November 3, from first to last. {H.nw(len(split), cap=True)} states span two time zones, so their counties close at different moments where the law sets the same clock time. Anyone in line when the polls close may still vote.",
        "No state shows results before its polls close. This list shows when each state closes. If you are in line at closing time, you can still vote.")}</header>
<div class="nh-wrap">
<table class="nh-times"><caption>Poll closing times on November 3, 2026, earliest first</caption>
<thead><tr><th scope="col">Polls close</th><th scope="col">Where</th></tr></thead>
<tbody>{rows}</tbody></table>
<p class="nh-zone" id="nh-zone">Times are in Central Standard Time. Daylight time ends on November 1.</p>
<details class="nh-fold"><summary>Where these times come from, state by state</summary>
<ul class="nh-src">{srcs}</ul></details>
</div>
</div>
</section>"""

    opts = "".join(f'<option value="{esc(s["lookup"]["url"])}">{esc(s["name"])}</option>' for s in sorted(P["states"].values(), key=lambda s: s["name"]))
    fb = P["_about"]["fallback_lookup"]
    sec_vote = f"""<section class="tca-sec" id="where-to-vote" aria-labelledby="vote-h">
<div class="tca-wrap">
<header>__CHUNK__<p class="tca-kick">Before you go</p><h2 id="vote-h">Find your polling place</h2>
{H.para("Each state keeps its own lookup of where to vote. Choose your state and you go straight to it. This site does not see what you type there.",
        "Pick your state. You go to your state's own page to find where you vote.")}</header>
<form class="tca-pick" action="#"><label for="nh-pick">Your state<select id="nh-pick"><option value="">Choose a state</option>{opts}</select></label><button type="submit">Go</button></form>
<p class="nh-zone">Each choice opens the state's own page. The National Association of Secretaries of State also keeps a guide: <a href="{esc(fb["url"])}" rel="noopener">{esc(fb["title"])}</a>.</p>
</div>
</section>"""

    if F["registry"]:
        how = (f"{H.nw(F['states_live'], cap=True)} states publish a live count this site reads as it comes in"
               + (f", and {H.nw(F['states_care'])} more can be read with care" if F["states_care"] else "")
               + (". Minnesota's figures come from the Secretary of State's results files, saved through the night" if F["states_hand"] else "")
               + (f". For the other {H.nw(F['states_link'])}, the page links to the state's own results and adds the official totals when the state certifies them." if F["states_link"] else "."))
    else:
        how = ("Where a state publishes a live count that a program may read, this site reads it as it comes in. Minnesota's figures come from the Secretary of State's results files, saved through the night. "
               "Where a state publishes no such count, the page links to the state's own results and adds the official totals when the state certifies them.")
    sec_how = f"""<section class="tca-sec lvl-extra" id="how" aria-labelledby="how-h">
<div class="tca-wrap">
<header>__CHUNK__<p class="tca-kick">What is read live, and how</p><h2 id="how-h">Straight from each state</h2>
{H.para(how + " The pages look for new figures every few minutes, and a figure usually appears here 10 to 20 minutes after the state posts it.",
        "Some states share their count as it comes in, and this site reads it. For the rest, we link to the state's own page. New numbers show up here within about 20 minutes.")}</header>
</div>
</section>"""

    vows = [("Official counts only.", "Every result comes from the state's own election office, with the time the state gave it, and says it is not final until the state certifies it.",
             "Every number comes from the state. Each one shows when it was posted."),
            ("No race is called.", "A candidate is ahead in the count so far until the result is certified. The site never says projected, called or won before then.",
             "We never say who won until the state says so."),
            ("Forecasts are Analysis.", "A forecast is a model's estimate with a range, its inputs and its track record, and it is labelled Analysis everywhere it appears.",
             "A forecast is a guess. It is always marked as one."),
            ("Headlines, not articles.", "The feed shows a headline, the outlet, the time and a link. It never copies a story.",
             "We show news headlines with links. We do not copy stories."),
            ("People are counted, not shown.", "Posts are shown only from news organizations, election offices and candidates' official accounts. Everyone else is counted, never shown or named.",
             "We never show or name regular people. We only count their posts."),
            ("Red and blue mean party.", "Red and blue are used for party data and for nothing else. Everything else is brass and green.",
             "Red and blue only ever mean a party.")]
    vow_items = "".join(f'<li class="tca-vow"><h3>{esc(h)}</h3>{H.para(esc(s), esc(p))}</li>' for h, s, p in vows)
    sec_vows = f"""<section class="tca-sec lvl-extra" id="promises" aria-labelledby="vow-h">
<div class="tca-wrap">
<header>__CHUNK__<p class="tca-kick">The rules this space keeps</p><h2 id="vow-h">How Election Night works</h2>
{H.para("Every page of Election Night keeps these rules, on the night and after it.", "Every page here keeps these rules.")}</header>
<ul class="tca-vows">{vow_items}</ul>
</div>
</section>"""
    page = hero + "\n" + "\n".join(H.chunked([sec_doors, sec_times, sec_vote, sec_how, sec_vows]))
    return page, boot


def page_html(A, version, generated, places, main, boot):
    root = "../"
    title = "Election Night: The Civic Archive"
    desc = "Follow the count, race by race: official results of the November 3, 2026 election as each state posts them, with the time on every number."
    extra = STYLE + "\n"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
{S.head(A, root, title, desc, version, extra=extra, og_image=f"{S.BASE_URL}/night/og/home.png", url=f"{S.BASE_URL}/night/")}</head>
<body>
{S.top_bar(root, "night", places)}
<main id="main">
{main}
</main>
{H.footer(root, version, generated)}
{S.tab_bar(root, "night")}
{S.panels(root, A, faq_html())}
<script>window.NIGHT_HOME={boot};</script>
{SCRIPT}
</body>
</html>
"""


CARDS = {      # words only: never a count, a percentage or a chance on an image
    "home": ("Election Night", "Follow the count, race by race.",
             "Official results as each state posts them, with the time on every number. Minnesota at every level."),
    "results": ("Results", "Every state's count, from the state itself.",
                "Congress, governors and the other statewide offices, from each state's own election office. Never a call."),
    "feed": ("The feed", "What the news is covering, race by race.",
             "Headlines with links, and posts from election offices and candidates' official accounts. Everyone else is counted, never shown."),
    "forecasts": ("Forecasts", "A model's estimate, never a call.",
                  "Each forecast labelled Analysis, with its range, its inputs and its track record. The official count decides."),
}


def write_if_changed(path, data):
    try:
        with open(path, "rb") as fh:
            if fh.read() == data:
                return False
    except OSError:
        pass
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(data)
    return True


def cards(dev_root, say=print):
    import brand
    from PIL import Image
    out = {}
    for name, (t, lead, line) in CARDS.items():
        if re.search(r"\d", t + lead + line):
            raise SystemExit(f"build_night_home: the {name} card's words carry a figure")
        im = brand.site_card(t, lead, line, kicker="The Civic Archive · Election Night")
        buf = io.BytesIO()
        im.quantize(colors=128, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE).save(buf, format="PNG", optimize=True)
        data = buf.getvalue()
        path = os.path.join(dev_root, "night", "og", f"{name}.png")
        write_if_changed(path, data)
        out[os.path.join("night", "og", f"{name}.png")] = len(data)
    return out


# ============================== build ==============================

def build(dev_root, version=None, practice=None, say=print, A=None):
    dev_root = os.path.abspath(dev_root)
    if practice:
        say("Night home: the home carries no live figures, so a practice build writes nothing for it")
        return {}
    version = version if version is not None else H.version_now()
    generated = H.day(dt.date.today())
    H.PLAIN.clear()
    A = A or shell_assets(dev_root)
    places = S.site_places(dev_root)
    F = facts(dev_root)
    P = poll_hours()
    main, boot = body(F, P, places)
    text = page_html(A, version, generated, places, main, boot)
    bad = sorted(set(KIT_NAMES.findall(text)))
    if bad:
        raise SystemExit(f"build_night_home: the page names the kit's own files: {bad}")
    if re.search(r"\b(projected|called for|declared the winner)\b", re.sub(r"<[^>]+>", " ", text.replace("projected, called or won", "")), re.I):
        raise SystemExit("build_night_home: the page uses a word Election Night never uses about a result")
    out = cards(dev_root, say)
    data = text.encode("utf-8")
    write_if_changed(os.path.join(dev_root, "night", "index.html"), data)
    out[os.path.join("night", "index.html")] = len(data)
    grades = [(round(H.fk_grade(t), 1), t) for t in H.PLAIN]
    worst = max(grades) if grades else (0, "")
    over = [g for g in grades if g[0] > GRADE_MAX]
    say(f"Night home: wrote night/index.html ({len(data) / 1e3:,.0f} KB) and {len(CARDS)} share images; "
        f"{len(H.PLAIN)} plain-language blocks, Flesch-Kincaid grade at most {worst[0]}"
        + (f"; {len(over)} above {GRADE_MAX:g}: " + " | ".join(f"{g}: {t[:60]}" for g, t in over) if over else f" (all at {GRADE_MAX:g} or below)")
        + f"; poll hours for {len(P['states'])} states and DC" .replace("51 states and DC", "the 50 states and DC"))
    if over:
        raise SystemExit("build_night_home: a plain-language twin reads above grade 7")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=os.path.join(HERE, "site", "dev"), help="the draft's folder (default site/dev)")
    a = ap.parse_args()
    build(a.root)


if __name__ == "__main__":
    main()
