#!/usr/bin/env python3
"""
build_home.py - the front door of The Civic Archive, and its Method and Access pages (John, 2026-10-03, from his
Shell Spec v1.3 and Companion Field Guide v0.1).

    python build_home.py [--root site/dev] [--draft]

writes <root>/index.html (the front door), <root>/method/index.html and <root>/access/index.html, all three on the shared
shell (build_shell.py: the top bar, Reading & access, Help, the companion, the tab bar on phones). The ring of cards
lives beside them as rooms.html and the cabin as cabin.html; build_door.py writes those and then calls build() here, so
every build of the front door makes these pages too.

Every number on the pages is counted at build time from the records on this computer (read only): the federal
database, the two ballot databases, each state's database and the site's own folders. The Method page describes the
rating rubric as written and says plainly where the ratings stand today. The words follow the house voice: short
declarative sentences, no hype, no exclamation marks. Each main paragraph has a plain-language twin; their reading
level is checked here (Flesch-Kincaid grade 7 or lower) and printed.
"""

import argparse
import datetime as dt
import html
import json
import os
import re
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_shell as S      # noqa: E402

ELECTION_DAY = "2026-11-03"
LOCAL_LEVELS = ("county", "soil_water", "city", "township", "school", "hospital", "other")
esc = lambda s: html.escape(str(s), quote=True)
PLAIN = []      # every plain-language block written, for the reading-level check


# ============================== what the records hold ==============================

def _ro(path):
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def _has(con, t):
    return con.execute("SELECT 1 FROM sqlite_master WHERE name = ?", (t,)).fetchone() is not None


def facts(look):
    """Counts from the databases (read only) and from the site's folders under `look`."""
    F = {"bills": 0, "laws": 0, "votes": 0, "members": 0, "judged": 0, "hand": 0, "model": 0, "backing": 0, "replaced": 0,
         "races": 0, "candidates": 0, "ballot_states": 0, "sl_states": 0, "local_states": 0, "states_open": 0, "state_legislators": 0,
         "money_states": 0, "counties": [], "verify": None, "rubric": "", "analytics": os.path.exists(os.path.join(HERE, "analytics.txt"))}
    db = os.path.join(HERE, "congress_119.sqlite")
    if os.path.exists(db):
        con = _ro(db)
        one = lambda q, *p: con.execute(q, p).fetchone()[0] or 0
        F["bills"] = one("SELECT COUNT(*) FROM bills")
        F["laws"] = one("SELECT COUNT(*) FROM bills WHERE law_number <> ''")
        if _has(con, "member_votes"):
            F["votes"] = one("SELECT COUNT(DISTINCT vote_id) FROM member_votes")
        if _has(con, "legislators"):
            F["members"] = one("SELECT COUNT(*) FROM legislators WHERE is_current = 1")
        if _has(con, "ratings"):
            J = "axis IN ('income','households_business','timing','rights','plain_language') AND is_current = 1"
            F["judged"] = one(f"SELECT COUNT(DISTINCT bill_key) FROM ratings WHERE {J}")
            F["model"] = one(f"SELECT COUNT(DISTINCT bill_key) FROM ratings WHERE {J} AND rater LIKE 'model:%'")
            F["hand"] = one(f"SELECT COUNT(DISTINCT bill_key) FROM ratings WHERE {J} AND rater NOT LIKE 'model:%' AND rater LIKE '%by hand%'")
            F["backing"] = one("SELECT COUNT(DISTINCT bill_key) FROM ratings WHERE axis = 'backing' AND is_current = 1 AND rater = 'computed:roll-calls'")
            F["replaced"] = one("SELECT COUNT(*) FROM ratings WHERE is_current = 0 AND superseded_by IS NOT NULL AND superseded_by <> ''")
        con.close()
    db = os.path.join(HERE, "ballot_2026.sqlite")
    if os.path.exists(db):
        con = _ro(db)
        one = lambda q: con.execute(q).fetchone()[0] or 0
        F["races"] = one("SELECT COUNT(*) FROM races WHERE level = 'federal'")
        F["candidates"] = one("SELECT COUNT(*) FROM candidates c JOIN races r USING (race_id) WHERE r.level = 'federal' AND c.election IN ('general', 'open-primary')")
        F["ballot_states"] = one("SELECT COUNT(DISTINCT substr(race_id, 6, 2)) FROM candidates WHERE election IN ('general', 'open-primary')")
        con.close()
    db = os.path.join(HERE, "ballot_local_2026.sqlite")
    if os.path.exists(db):
        con = _ro(db)
        try:
            sts = [s for (s,) in con.execute("SELECT DISTINCT state FROM sl_races") if os.path.exists(os.path.join(look, "ballot", s.lower(), "index.html"))]
            F["sl_states"] = len(sts)
            ph = ",".join("?" * len(LOCAL_LEVELS))
            F["local_states"] = sum(1 for s in sts if con.execute(f"SELECT 1 FROM sl_races WHERE state = ? AND level IN ({ph}) LIMIT 1", (s, *LOCAL_LEVELS)).fetchone())
        except sqlite3.Error:
            pass
        con.close()
    try:
        from states.places import PLACES
    except Exception:
        PLACES = {}
    for code in sorted(PLACES):
        db = os.path.join(HERE, f"state_{code}.sqlite")
        if os.path.exists(os.path.join(look, code, "index.html")):
            F["states_open"] += 1
        if os.path.exists(db):
            con = _ro(db)
            if _has(con, "legislators"):
                F["state_legislators"] += con.execute("SELECT COUNT(*) FROM legislators WHERE is_current = 1").fetchone()[0] or 0
            if _has(con, "state_gifts") and con.execute("SELECT 1 FROM state_gifts LIMIT 1").fetchone():
                F["money_states"] += 1
            con.close()
        if os.path.exists(os.path.join(look, code, "counties", "index.html")):
            n = 0
            ldb = os.path.join(HERE, f"local_{code}.sqlite")
            if os.path.exists(ldb):
                con = _ro(ldb)
                if _has(con, "officials"):
                    n = con.execute("SELECT COUNT(*) FROM officials").fetchone()[0] or 0
                con.close()
            F["counties"].append({"name": PLACES[code]["name"], "url": f"{code}/counties/", "officials": n})
    rep = os.path.join(HERE, "verify_report.md")
    if os.path.exists(rep):
        text = open(rep, encoding="utf-8").read()
        m = re.search(r"Member votes add up to the official tally \|\s*([\d,]+) of ([\d,]+) votes match", text)
        when = re.search(r"# Verify report, (\d{4}-\d{2}-\d{2})", text)
        ties = len(re.findall(r"\|S\|[^:]*: members (\d+)-(\1) vs official \d+-\1", text))
        if m:
            F["verify"] = {"match": int(m.group(1).replace(",", "")), "of": int(m.group(2).replace(",", "")), "date": when.group(1) if when else "",
                           "senate_ties": ties}
    rub = os.path.join(HERE, "rubric_v1.md")
    if os.path.exists(rub):
        m = re.search(r"version\s+(\d+\.\d+)", open(rub, encoding="utf-8").readline())
        F["rubric"] = m.group(1) if m else ""
    return F


def version_now():
    try:
        with open(os.path.join(HERE, "CHANGELOG.md"), encoding="utf-8") as fh:
            for line in fh:
                m = re.match(r"##\s+v(\d+\.\d+\.\d+)\b", line)
                if m:
                    return m.group(1)
    except OSError:
        pass
    return ""


def day(d):
    return f"{d:%B} {d.day}, {d.year}"


def nice_date(iso):
    try:
        return day(dt.date.fromisoformat(iso))
    except ValueError:
        return iso


# ============================== writing helpers ==============================

def para(std, plain=None, cls=""):
    """A paragraph, with its plain-language twin when one is written. Only one of the two is ever shown."""
    c = f" {cls}" if cls else ""
    if not plain:
        return f'<p class="{cls}">{std}</p>' if cls else f"<p>{std}</p>"
    PLAIN.append(re.sub(r"<[^>]+>", "", plain))
    return f'<p class="say-std{c}">{std}</p><p class="say-plain{c}">{plain}</p>'


TERMS = []


def term(word, meaning):
    """A word explained where it is first used: a real button, then its meaning in place (Shell Spec 2.1)."""
    tid = f"term-{len(TERMS) + 1}"
    TERMS.append(word)
    return (f'<button type="button" class="tca-term" aria-expanded="false" aria-controls="{tid}">{word}</button>'
            f'<span class="tca-def" id="{tid}" hidden>{meaning}</span>')


def words_of(h):
    """The headline split into words for the load animation; the spaces stay as text so it reads as one sentence."""
    out, i = [], 0
    for chunk in re.split(r"(<[^>]+>)", h):
        if chunk.startswith("<"):
            out.append(chunk)
            continue
        parts = re.split(r"(\s+)", chunk)
        for p in parts:
            if not p:
                continue
            if p.isspace():
                out.append(p)
            else:
                out.append(f'<span class="w" style="--i:{i}">{p}</span>')
                i += 1
    return "".join(out)


def syllables(w):
    w = re.sub(r"[^a-z]", "", w.lower())
    if not w:
        return 0
    if len(w) <= 3:
        return 1
    w = re.sub(r"(?:[^laeiouy]es|ed|[^laeiouy]e)$", "", w)
    w = re.sub(r"^y", "", w)
    return max(1, len(re.findall(r"[aeiouy]{1,2}", w)))


def fk_grade(text):
    sents = max(1, len(re.findall(r"[.!?](?:\s|$)", text)))
    ws = re.findall(r"[A-Za-z][A-Za-z'’-]*|\d[\d,.%]*", text)
    if not ws:
        return 0.0
    syl = sum(syllables(w) if w[0].isalpha() else 1 for w in ws)
    return 0.39 * len(ws) / sents + 11.8 * syl / len(ws) - 15.59


def chunked(sections):
    """ADHD's scaffolding: 'Part 2 of 5 · About 1 minute' above each section, from its own length."""
    n, out = len(sections), []
    for i, body in enumerate(sections, 1):
        words = len(re.findall(r"\w+", re.sub(r"<[^>]+>", " ", re.sub(r'<p class="say-plain[^"]*">.*?</p>', " ", body, flags=re.S))))
        mins = max(1, round(words / 200))
        out.append(body.replace("__CHUNK__", f'<p class="tca-chunk">Part {i} of {n} &middot; About {mins} minute{"" if mins == 1 else "s"}</p>'))
    return out


ARROW = '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M5 12h14M13 6l6 6-6 6"/></svg>'
RING = ('<svg class="glyph" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M3 13.6c0 2.6 4 4.6 9 4.6s9-2 9-4.6"/>'
        '<path d="M4.4 7.2h4v6h-4zM10 5h4v7.6h-4zM15.6 7.2h4v6h-4z"/></svg>')
CABIN = ('<svg class="glyph" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M2.8 11.6 12 4l9.2 7.6"/><path d="M5.4 9.6v10h13.2v-10"/>'
         '<path d="M10 19.6v-5.2h4v5.2"/><path d="M16.6 7.7V4.6"/><path d="M7.4 12.6h1.4"/></svg>')


def n(x):
    return f"{x:,}"


WORDS = "no one two three four five six seven eight nine ten eleven twelve".split()


def nw(x, cap=False):
    """A count in words up to twelve, as the house style writes it; figures above that."""
    s = WORDS[x] if isinstance(x, int) and 0 <= x < len(WORDS) else n(x)
    return s[:1].upper() + s[1:] if cap else s


def page(A, root, title, desc, version, body, current, places, faq, generated, draft, inline_access=False):
    wip = ('<aside class="tca-draft" aria-label="Draft">A draft for feedback, not the live site. <a href="https://thecivicarchive.github.io/">Go to the live site</a></aside>') if draft else ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
{S.head(A, root, title, desc, version)}</head>
<body>
{S.SKIP}
{wip}
{S.top_bar(root, current, places, skip=False)}
<main id="main">
{body}
</main>
{footer(root, version, generated)}
{S.tab_bar(root, current)}
{S.panels(root, A, faq, inline_access=inline_access)}
</body>
</html>
"""


def footer(root, version, generated):
    return f"""<footer class="tca-foot">
<div class="tca-wrap">
<div class="grid">
<div><h2>The Civic Archive</h2><p class="house">Built from public records. No scores or ratings of any person, no advertising of its own, no donors.</p></div>
<div><h2>Go</h2><ul>
<li><a href="{root}us/">Plain Congress</a></li><li><a href="{root}ballot/">On The Ballot</a></li><li><a href="{"#officials" if root == "./" else root + "#officials"}">Officials</a></li>
<li><a href="{root}rooms.html">All levels</a></li><li><a href="{root}cabin.html" data-tca-break>Take a break</a></li></ul></div>
<div><h2>This site</h2><ul>
<li><a href="{root}method/">Method</a></li><li><a href="{root}method/#sources">Sources</a></li><li><a href="{root}access/">Access</a></li></ul></div>
</div>
<p class="fine"><span>The Civic Archive v{esc(version)}</span><span>Generated on {esc(generated)}</span></p>
</div>
</footer>"""


def faq_html(F):
    count = ("Some pages of the record count visits with GoatCounter, which sets no cookies and keeps no personal data. This page counts nothing. "
             if F["analytics"] else "No page counts visits. ")
    trust_now = (f"So far {nw(F['judged'])} bills carry a full set of ratings. They were applied by hand, as a preview, and each says so. "
                 if F["judged"] and F["hand"] == F["judged"] else (f"So far {nw(F['judged'])} bills carry a full set of ratings. " if F["judged"] else ""))
    return f"""<details><summary>Who pays for this site?</summary><div class="a"><p>Nobody pays to appear on it. The site runs no advertising of its own and has no donors. It is published on GitHub's free public hosting.</p></div></details>
<details><summary>Does this site track me?</summary><div class="a"><p>{count}There is no account and no sign-in. Your reading settings and your companion are kept in this browser, on this device, and are never sent anywhere.</p>
<p>Where a page offers "Use my location", your place is worked out on your device. Some pages of the record and the ballot still load their type from Google Fonts, so Google's servers see that request. This page does not. If you switch on street maps on a ballot page, OpenStreetMap's servers see which map squares are asked for, and the page says so.</p></div></details>
<details><summary>Why should I trust the ratings?</summary><div class="a"><p>You do not have to take them on trust. Facts come from official records and link back to them. Ratings are judgments, kept apart and labelled. Each one shows its evidence grade, its reasons, its sources and the version of the rubric it was made under.</p>
<p>{trust_now}Who backed a bill is worked out from the recorded votes by a published formula. <a href="__ROOT__method/">The Method page</a> has the whole rubric.</p></div></details>"""


# ============================== the front door ==============================

def home_body(F, places, root="./"):
    b = places
    open_states = F["states_open"] or len(b["states"])
    kpis = [(n(F["bills"]), "bills and joint resolutions in the 119th Congress"), (n(F["votes"]), "recorded votes, member by member"),
            (n(F["state_legislators"]), f"state legislators, in {n(open_states)} states"), (n(F["races"]), "races for Congress on the November ballot")]
    kpi_dl = "".join(f"<div><dd>{v}</dd><dt>{esc(t)}</dt></div>" for v, t in kpis if v not in ("0", ""))
    hero = f"""<section class="tca-hero split" aria-labelledby="hero-h">
<div class="tca-wrap">
<div>
<p class="kicker">The Civic Archive</p>
<h1 id="hero-h">{words_of("The public record, <em>for everyone.</em>")}</h1>
{para("What Congress and the fifty state legislatures do, who sits in them, and who is on your November ballot. Taken from official records, written so you can follow it, and linked back to the source.",
      "See what Congress and your state lawmakers do. See who is running for office. All of it comes from official records.", "lede")}
<p class="vow-line"><span>No ads.</span><span>No donors.</span><span>No account.</span><span>Your settings stay on this device.</span></p>
</div>
<aside class="tca-kpi lvl-detail" aria-labelledby="kpi-h">
<p class="tag">Fact</p>
<h2 id="kpi-h">On file today</h2>
<dl>{kpi_dl}</dl>
<p class="note">Counted from the records when this page was built.</p>
</aside>
</div>
</section>"""

    def door(key, href, kick, title, std, plain, facts_, go, extra=""):
        dl = "".join(f"<div><dd>{esc(v)}</dd><dt>{esc(t)}</dt></div>" for v, t in facts_ if v not in (None, "", 0))
        return f"""<article class="tca-door" data-door="{key}">
<div class="top">{S.icon(key)}<span class="kick">{esc(kick)}</span></div>
<h3><a id="door-{key}" href="{href}" aria-labelledby="door-{key} door-{key}-go">{esc(title)}</a></h3>
{para(std, plain)}{extra}
{f'<dl class="facts lvl-detail">{dl}</dl>' if dl else ''}
<span class="go" id="door-{key}-go" aria-hidden="true">{esc(go)} {ARROW}</span>
</article>"""
    when = (f'<p class="when">Election Day is {day(dt.date.fromisoformat(ELECTION_DAY))}<span class="urgency" data-tca-days="{ELECTION_DAY}"></span>.</p>')
    doors = "\n".join([
        door("bills", "us/", "Plain Congress", "See what they did with the last one.",
             "Every bill and " + term("joint resolution", "A joint resolution passes like a bill and can become law. It is also how Congress proposes an amendment to the Constitution.")
             + " of the 119th Congress, every " + term("recorded vote", "A vote in which each member&rsquo;s yes or no is written down by name, also called a roll call.")
             + " member by member, and who funds each campaign. Straight from the official record.",
             "Every bill in this Congress. How each member voted. Who gives money to their campaigns.",
             [(n(F["bills"]), "bills"), (n(F["laws"]), "became law"), (n(F["votes"]), "recorded votes")], "Open Plain Congress"),
        door("ballot", "ballot/", "On The Ballot", "Meet everyone asking for your vote.",
             "Every race for Congress on the November 3 ballot, then governors, legislatures, courts and local offices, each from the state's own official candidate list.",
             "Who is running in November, from Congress down to your county. Only from official lists.",
             [(n(F["races"]), "races for Congress"), (n(F["ballot_states"]), "states' lists for Congress"), (n(F["local_states"]), "states' local races")], "Open On The Ballot", when),
        door("officials", "#officials", "Officials", "Find who represents you.",
             f"The {n(F['members'])} members of Congress and the legislators of all fifty states: their districts, committees and time in office. Campaign money for Congress and for {n(F['money_states'])} states so far.",
             "Find your members of Congress and your state lawmakers. See their districts, and who funds them.",
             [(n(F["members"]), "members of Congress"), (n(open_states), "states open"), (n(F["state_legislators"]), "state legislators")], "Choose where to look"),
        door("method", "method/", "Method", "See how every page is made.",
             "Where each fact comes from, how bills are rated and checked, and what this site will not do. Facts and judgments are kept apart, and each is labelled.",
             "How we build each page. What is a fact, and what is a judgment.",
             [(F["rubric"], "rubric version"), (n(F["judged"]), "bills rated in full"), (n(F["backing"]), "bills with party backing counted")], "Read the method"),
        door("access", "access/", "Access", "Read it your way.",
             "Type, size, spacing, contrast, motion and chart colours, set once and kept on this device. And a plain list of what is done and what is not.",
             "Make the text bigger, the colours stronger, or the page calmer. See what still needs work.",
             [("8", "presets"), ("11", "settings")], "See access"),
    ])
    minor = f"""<div class="tca-pair lvl-extra">
<article class="tca-door minor">{RING}<div><h3><a href="rooms.html">All levels</a></h3><p>The ring of cards: Congress, the states and the local level, one card each.</p></div></article>
<article class="tca-door minor">{CABIN}<div><h3><a href="cabin.html" data-tca-break>Take a break</a></h3><p>A log cabin in the Rockies, at your own time of day. Two posters lead back in.</p></div></article>
</div>"""
    sec_doors = f"""<section class="tca-sec" id="doors" aria-labelledby="doors-h">
<div class="tca-wrap">
<header>__CHUNK__<p class="tca-kick">Where to go</p><h2 id="doors-h">Five ways in</h2>
{para("Each door opens one part of the record. The same five are in the bar at the top of this page, and at the bottom of your screen on a phone. The record and ballot pages still have their own bar for now.",
      "Pick a door. The same five doors are in the bar at the top of this page.")}</header>
<div class="tca-doors">
{doors}
{minor}
</div>
</div>
</section>"""
    counties = "".join(
        f'<li><a href="{c["url"]}">{esc(c["name"])}&rsquo;s counties<small>'
        + ("Every county on one map, and who holds each county office" if c["officials"] else "Every county on one map. Who holds each office is still to come")
        + "</small></a></li>" for c in F["counties"]) or \
        '<li><span class="tca-soon">County and city officials<small>Who holds each office, for every state. Coming soon</small></span></li>'
    state_links = "".join(f'<li><a href="{code}/">{esc(name)}</a></li>' for name, code in b["states"])
    sec_off = f"""<section class="tca-sec" id="officials" aria-labelledby="off-h">
<div class="tca-wrap">
<header>__CHUNK__<p class="tca-kick">Officials</p><h2 id="off-h">Who represents you</h2>
{para("Start with Congress or your state legislature. Each page shows the record: time in office, committees, votes where they are loaded, and who funds the campaigns. County and city officials are coming soon.",
      "Start with Congress or your state. Each page shows what the official record says. County and city officials are coming soon.")}</header>
<div class="tca-cols">
<div class="tca-col"><h3>In Congress</h3><ul>
<li><a href="us/#members">Your members<small>Service, committees, votes and money</small></a></li>
<li><a href="us/#yours">How did your members vote?<small>Pick your state, see each recorded vote</small></a></li>
<li><a href="us/#map">Who voted how, state by state<small>The vote map</small></a></li>
<li><a href="us/#money">Follow the money<small>The organizations behind each campaign</small></a></li></ul></div>
<div class="tca-col"><h3>In your statehouse</h3>
{S.state_picker("", b, "tca-pick-home")}
<ul><li><a href="rooms.html#states">Choose a state on the map<small>{n(open_states)} state legislatures: districts, members, committees</small></a></li></ul>
{f'<details><summary>All {n(len(b["states"]))} states, by name</summary><ul class="tca-states">{state_links}</ul></details>' if state_links else ''}</div>
<div class="tca-col"><h3>Closer to home</h3><ul>{counties}
<li><a href="ballot/states/#local">County and local races<small>Sheriffs, county boards, mayors, councils and school boards on the November ballot</small></a></li></ul></div>
</div>
</div>
</section>"""
    rows = [("Lowest fifth", 1.6, -0.7), ("Second fifth", 1.1, None), ("Middle fifth", 0.6, None), ("Fourth fifth", 0.3, None), ("Top fifth", None, -0.4)]
    top = 2.0

    def pct(v):
        return ("+" if v > 0 else "−") + f"{abs(v):.1f}%"

    def side(cls, v):      # the bar from zero, its number outside it, never on the fill
        if not v:
            return ""
        return f'<span class="bar {cls}" style="--v:{abs(v) / top:.3f}"></span><span class="val">{pct(v)}</span>'
    bars = "".join(f'<div class="row"><span class="grp">{g}</span><div class="plot"><div class="side neg">{side("cost", c)}</div>'
                   f'<div class="side pos">{side("gain", p)}</div></div></div>' for g, p, c in rows)
    said = "; ".join(f"{g}: " + " and ".join(x for x in ((f"gains {p:.1f} percent" if p else ""), (f"pays {abs(c):.1f} percent" if c else "")) if x) for g, p, c in rows)
    table = "".join(f'<tr><th scope="row">{g}</th><td class="num">{pct(p) if p else "none"}</td><td class="num">{pct(c) if c else "none"}</td></tr>' for g, p, c in rows)
    sec_chart = f"""<section class="tca-sec lvl-extra" id="reading" aria-labelledby="read-h">
<div class="tca-wrap">
<header>__CHUNK__<p class="tca-kick">How to read a rating</p><h2 id="read-h">Who gains, drawn from zero</h2>
{para("Ratings that say who gains and who pays are drawn as bars from zero. The direction carries the sign, the number sits outside the bar, and colour only adds to both. A group that both gains and pays gets a bar on each side, never one averaged number.",
      "Bars to the right mean a group gains. Bars to the left mean it pays. Some groups do both, so they get two bars.")}</header>
<figure class="tca-chart" aria-labelledby="chart-h">
<span class="tag">Illustration</span>
<h3 id="chart-h">Change in after-tax income, by income group</h3>
<p class="sub">Invented numbers. Not a real bill.</p>
<div class="tca-visual">
<div class="tca-bars" role="img" aria-label="Illustration with invented numbers, not a real bill. {esc(said)}.">
{bars}
<div class="axis" aria-hidden="true"><span></span><span class="ends"><span>&larr; pays</span><span>gains &rarr;</span></span></div>
</div>
<div class="key" aria-hidden="true"><span><i class="gain"></i>Gains</span><span><i class="cost"></i>Costs</span></div>
</div>
<div id="chart-table" hidden><table><caption>Illustration with invented numbers: change in after-tax income, in percent</caption>
<thead><tr><th scope="col">Income group</th><th scope="col" class="num">Gains</th><th scope="col" class="num">Costs</th></tr></thead><tbody>{table}</tbody></table></div>
<div class="tca-row"><button class="tca-btn" type="button" data-tca-table aria-controls="chart-table" aria-expanded="false">View as table</button></div>
<figcaption>Illustration. The numbers are invented to show how a rating is drawn; no bill is named because none is shown. With a colour-vision palette, Calm or high contrast, the bars also carry stripes: rising for gains, falling for costs.</figcaption>
</figure>
</div>
</section>"""
    vows = [("Official records first.", "Every bill, vote, member and candidate list comes from the office that keeps the record, and links back to it.",
             "Facts come from official sources. We link to them."),
            ("Facts and judgments apart.", "Ratings are judgments. Each shows its evidence grade, its reasons and the version of the rubric it was made under.",
             "A rating is an opinion. It shows its reasons."),
            ("Bills are rated. People are not.", "No candidate or member is given a score or a rating.", "No person gets a score."),
            ("No ads, no donors.", "The site runs no advertising of its own and has no donors.", "There are no ads. No one gives us money."),
            ("Organizations, not people.", "Donor lists name organizations. People who gave appear only in totals.", "We name groups that give money. We do not name people."),
            ("Red and blue mean party.", "Red and blue are used for party data and for nothing else. Everything else is brass and green.",
             "Red and blue only ever mean a party.")]
    vow_items = "".join(f'<li class="tca-vow"><h3>{esc(h)}</h3>{para(esc(s), esc(p))}</li>' for h, s, p in vows)
    sec_vows = f"""<section class="tca-sec lvl-extra" id="promises" aria-labelledby="vow-h">
<div class="tca-wrap">
<header>__CHUNK__<p class="tca-kick">What it does, and what it will not do</p><h2 id="vow-h">How this site works</h2>
{para("These are the rules every page keeps. The Method page shows how each one is kept.", "Each page keeps these rules.")}</header>
<ul class="tca-vows">{vow_items}</ul>
</div>
</section>"""
    return hero + "\n" + "\n".join(chunked([sec_doors, sec_off, sec_chart, sec_vows]))


# ============================== Method ==============================

def method_body(F):
    v = F["verify"]
    votes_check = ""
    if v:
        diff = v["of"] - v["match"]
        votes_check = (f" At the last check, on {nice_date(v['date'])}, {n(v['match'])} of {n(v['of'])} matched."
                       + (f" The other {'two are' if diff == 2 else str(diff) + ' are'} Senate votes tied among the senators and decided by the Vice President, whose vote counts in the official tally but is not a senator's vote."
                          if diff and v.get("senate_ties") == diff else (f" The {n(diff)} that do not are listed for a person to compare with the official roll call." if diff else "")))
    status_hand = (f"{nw(F['judged'], True)} bills carry a full set of ratings so far. All {nw(F['judged'])} were applied by hand, as a preview, in a working session, and each says so where it appears. "
                   "They were not made by the scoring step the rubric describes, which builds its input without the sponsor, the parties, cosponsor counts, vote tallies or member names. "
                   "So the rubric's rule about what a rater may see was not tested on them."
                   if F["judged"] and F["hand"] == F["judged"] else
                   (f"{nw(F['judged'], True)} bills carry a full set of ratings so far." if F["judged"] else "No bill carries a full set of ratings yet."))
    model = ("No rating on the site has been made by a model yet. When one is, it will say &ldquo;Automated rating, not yet reviewed&rdquo; until a person has reviewed it."
             if not F["model"] else f"{n(F['model'])} bills carry ratings made by a model. Each says &ldquo;Automated rating, not yet reviewed&rdquo; until a person has reviewed it.")
    secs = []
    secs.append(f"""__CHUNK__<h2 id="record">Where the facts come from</h2>
{para("Every fact on this site comes from the public office that keeps it. The site copies the record, loads it, and shows it. It does not edit it by hand. When a number looks wrong, the fix is made where the record is loaded, never in the record.",
      "Every fact comes from the office that keeps the record. We copy it. We do not change it by hand.")}
<ul>
<li>Bills, their actions and their summaries: the Government Publishing Office and the Library of Congress (GovInfo Bill Status).</li>
<li>Recorded votes, member by member: the Clerk of the House and the Senate.</li>
<li>Members of Congress: the public roster kept by the congress-legislators project.</li>
<li>Campaign money for Congress: the Federal Election Commission's public files, 2016 through 2026.</li>
<li>State legislators, their districts and committees: the Open States project and the Census Bureau's boundary files. Campaign money in {n(F['money_states'])} states so far, each from the state's own campaign finance agency.</li>
<li>Who is on the ballot: each state's own official candidate list, loaded one state at a time.</li>
</ul>""")
    secs.append(f"""__CHUNK__<h2 id="claims">Three kinds of claim</h2>
{para("Everything on the site is one of three kinds of claim, and each is labelled where it appears.", "There are three kinds of claim. Each one has a label.")}
<table><caption>The three labels</caption><thead><tr><th scope="col">Label</th><th scope="col">What it means</th></tr></thead><tbody>
<tr><th scope="row">Fact</th><td>From the record: bill text, sponsors, dates, committee actions, every recorded vote. Linked to the official source.</td></tr>
<tr><th scope="row">Analysis</th><td>Worked out from facts by a stated rule, with the rule on the page so it can be checked.</td></tr>
<tr><th scope="row">Opinion</th><td>A judgment, such as a rating of who a bill helps. It carries its evidence and its reasons.</td></tr></tbody></table>""")
    grade_rows = "".join(f'<tr><th scope="row"><span class="tca-grade">{g}</span></th><td>{t}</td></tr>' for g, t in [
        ("A", "An official analysis of this bill exists, such as a Joint Committee on Taxation distribution table or a Congressional Budget Office estimate, and the rating follows it."),
        ("B", "Independent models of this bill exist, and the rating reflects their range. Models from more than one part of the spectrum are used, and where they disagree, that is reported."),
        ("C", "The rating rests on a reading of the bill text or its " + term("Congressional Research Service", "The office of the Library of Congress that writes a plain summary of each bill for Congress.")
         + " summary, by the rubric's text rules."),
        ("N", "Not assessable on this scale. This is a real answer, not a gap.")])
    slope = "".join(f"<tr><td>{a}</td><td>{b}</td></tr>" for a, b in [
        ("The bottom groups gain at least three times the top group's percentage", "&minus;80 to &minus;100"),
        ("The bottom gains clearly more than the top", "&minus;40 to &minus;79"),
        ("Roughly even percentage gains across groups", "&minus;15 to +15"),
        ("The top gains clearly more than the bottom", "+40 to +79"),
        ("The top gains at least three times the bottom's percentage, or the bottom loses while the top gains", "+80 to +100")])
    text_rules = "".join(f"<tr><td>{a}</td><td>{b}</td></tr>" for a, b in [
        ("A " + term("refundable", "A refundable tax credit is paid out even to people who owe little or no income tax.") + " credit; a larger earned income or child tax credit; more SSI, SNAP, Medicaid or housing help; a higher minimum wage; overtime protection", "&minus;20 to &minus;40 each"),
        ("A consumer rule that limits fees or interest charged mainly to customers with small balances", "&minus;15 to &minus;30"),
        ("A cut or a new condition on SNAP, Medicaid, SSI, housing help or student aid", "+20 to +40 each"),
        ("A tax credit or deduction with no income limit that cannot be refunded; a larger state and local tax or mortgage interest deduction", "+15 to +30"),
        ("A cut to tax rates on capital gains, dividends, estates, pass-through income or corporations", "+30 to +50"),
        ("An income limit, a phase-out at high income, or a refundable credit", "toward 0 by 10 to 20"),
        ("A benefit for everyone, such as a Social Security cost-of-living rise or a broad rebate", "toward 0")])
    flags = ["overrides state or local laws", "limits lawsuits", "creates or widens a right to sue", "forces disputes into arbitration",
             "leaves the rules to an agency", "cancels an agency's rule", "adds detention or penalties", "adds inspection, surveillance or data-collection power",
             "shifts costs to the states", "changes who can get a public benefit", "reaches back to past years or past conduct", "gives the executive new waiver or emergency power"]
    secs.append(f"""__CHUNK__<h2 id="rubric">How bills are rated</h2>
{para(f"A rating is a judgment, so the rules for making one are written down first. They are called the rubric, and it is at version {esc(F['rubric'] or '1.1')}. Every rating names the version it was made under. When a scale or a threshold changes, the version changes, and nothing is re-rated under an old one.",
      "A rating is an opinion. The rules for it are written down first. Each rating says which rules it used.")}
<h3 id="parts">Every rating has four parts</h3>
<ul><li>A position on its scale.</li><li>A size: how much money or how many people are at stake.</li><li>An evidence grade.</li>
<li>Two to four sentences of reasons that cite the section, the summary passage or the analysis they rest on.</li></ul>
<p>A bill that helps one group and costs another gets a range, never an average, so the two effects cannot cancel out. &ldquo;Not assessable&rdquo; is a real answer, used for naming bills, commemorations, procedural measures and anything the record gives no basis to judge. The latest text is rated. Reasons are written in plain words.</p>
<p>The rubric asks a rater to work without sponsor names, party labels, vote tallies or the President's name. It names its own limit: a widely covered bill can be recognised from its text alone, and hiding the labels does not hide what a rater already knows. <a href="#status">Where the ratings stand today</a> says how far this has been put to work.</p>
<h3 id="grades">Evidence grades</h3>
<table><caption>Only grades A and B may carry a confidence above 0.7. Grade C stops at 0.6.</caption><thead><tr><th scope="col">Grade</th><th scope="col">What it means</th></tr></thead><tbody>{grade_rows}</tbody></table>
<h3 id="income">Who gains, by income</h3>
<p>The scale runs from &minus;100, benefits going overwhelmingly to lower-income households, through 0, broad-based or even, to +100, benefits going overwhelmingly to high-income households. Costs are the mirror image: a cut to a program used mainly by lower-income households scores positive, because the burden falls at the bottom.</p>
<p>With an official or independent analysis, the measure is the change in after-tax-and-transfer income for each income group, the standard the Congressional Budget Office and the Joint Committee on Taxation use. The position is the slope of that change. Beside it goes the share of all the dollars that reaches the top fifth, because an even percentage cut can still send most of the money to the top.</p>
<table><caption>From the pattern of change to a position</caption><thead><tr><th scope="col">Pattern of percent change in income</th><th scope="col">Position</th></tr></thead><tbody>{slope}</tbody></table>
<p>The size of a bill is its ten-year effect on the federal budget: none under $1 billion, small to $10 billion, moderate to $100 billion, large to $1 trillion, major above that.</p>
<table><caption>Grade C, a reading of the text: start at 0 and move</caption><thead><tr><th scope="col">What the bill does</th><th scope="col">Move</th></tr></thead><tbody>{text_rules}</tbody></table>
<h3 id="backing">Who backed it</h3>
<p>This is measured, not judged. For the final passage vote in each chamber that had a recorded vote:</p>
<div class="formula"><p><b>r</b> = Republican yes votes &divide; (Republican yes + Republican no)<br><b>d</b> = Democratic yes votes &divide; (Democratic yes + Democratic no)<br><b>Position</b> = 100 &times; (r &minus; d), averaged across the two chambers</p>
<p>&minus;100 is Democrats only, 0 is bipartisan, +100 is Republicans only. Independents count with the party they caucus with.</p></div>
<p>The label comes from the smaller of the two yes rates: 50 percent or more is &ldquo;bipartisan&rdquo;, 15 to 49 percent is &ldquo;one party plus crossover&rdquo;, under 15 percent is &ldquo;party-line&rdquo;. Where the tallies are loaded but not the party split, a passage vote with at least 85 percent in favour is scored 0, at grade C. Where no passage vote was recorded, the rubric falls back on the mix of {term("cosponsors", "Members who formally sign on to support a bill another member introduced.")}, and says so.</p>
<p>Two more things are reported as text and never scored: where a bill's benefits land by state, only when a source allocates them; and whether a bill changes voting, districting, campaign finance or how elections are run, with one factual sentence and no forecast of who gains.</p>
<h3 id="households">Households and businesses</h3>
<p>Two separate scores, because a bill can help both. A change to corporate tax counts 25 percent to households as workers and 75 percent to the owners of capital, the convention the Budget Office and the Joint Committee use, and the rating says so. Repealing a rule is scored on both sides: what the industry gains and what households lose. Lobbying reports that name a bill show attention, never support.</p>
<h3 id="timing">Timing</h3>
<p>When a bill takes effect, when it changes, and when it ends, with the end always filled in. A benefit that runs out while a cost goes on is the most common way a bill's real effect differs from its headline, and the rating says so in a plain sentence.</p>
<h3 id="rights">Your rights and who decides</h3>
<p>A fixed list of twelve flags, each with one plain sentence. A bill that:</p>
<ul>{"".join(f"<li>{f}</li>" for f in flags)}</ul>
<p>An empty list is a valid answer.</p>
<h3 id="plainlayer">The plain-language layer</h3>
<p>One sentence of thirty words or fewer on what the bill does. Where it stands, in plain words. One line each for a worker, a parent, a retiree, a small business owner and a person with a disability or their caregiver, or the words &ldquo;No direct effect&rdquo;. And the most common misreading, if there is one.</p>""")
    secs.append(f"""__CHUNK__<h2 id="status">Where the ratings stand today</h2>
<div class="status">
<p>{status_hand}</p>
<p>Who backed it is worked out from the recorded votes, by the formula above, for {n(F['backing'])} bills.</p>
<p>{model}</p>
<p>When a rating is redone, the old one is kept, marked as replaced and pointed at the new one. {nw(F['replaced'], True)} {"rating has" if F['replaced'] == 1 else "ratings have"} been replaced so far.</p>
</div>
{para("Before ratings are made at scale, the rubric sets three checks. A person reviews the first 25 laws of this Congress on every scale, and the rate of disagreement is published. Thirty bills are rated three ways, with no party named, with Democratic named and with Republican named, and a shift of more than 10 points fails the version. And a person reviews every law and every bill with a floor vote within 30 days. No full scoring run has been made yet, so none of these results exists yet.",
      "The rules call for three checks before many bills are rated. None has been done yet, because that rating has not started.")}""")
    secs.append(f"""__CHUNK__<h2 id="votes">How the votes are checked</h2>
{para("Every recorded vote on these bills and joint resolutions is loaded member by member, and the members' votes are added up and compared with the official tally." + votes_check + " A vote that does not add up is reported for a person to look at. The record is never changed to make it add up.",
      "We add up how each member voted. Then we compare the total with the official count. We never change the record to make it match.")}""")
    secs.append(f"""__CHUNK__<h2 id="money">Campaign money</h2>
{para("Donor lists name organizations only: political action committees, party committees and other candidates' committees. People who gave are public record at the Federal Election Commission, but here they appear only in totals. Spending by outside groups is always shown apart from donations, with a sentence saying the campaign never received it. Money passed along by joint fundraising committees, or between a member's own committees, is shown as moved in, not as a gift.",
      "We name the groups that give money. People who give are counted, not named. Money spent by outside groups is shown on its own.")}""")
    secs.append(f"""__CHUNK__<h2 id="districts">District maps</h2>
{para("The district pages measure. They never say a map was drawn unfairly, and they never rank the worst districts. Every figure names its source, with its address, date and fingerprint; gives its formula and where it comes from; passes a test against known answers; matches the source's own totals; says what it cannot tell you; and can be downloaded whole.",
      "The district pages give numbers and their sources. They do not say a map is unfair. You decide.")}""")
    secs.append(f"""__CHUNK__<h2 id="ballot">On The Ballot</h2>
{para("Who is running comes only from each state's official candidate list, loaded one state at a time. Primary votes are shown only once they are official. Polls come only from members of the American Association for Public Opinion Research's Transparency Initiative, each checked against the pollster's own release. Betting-market prices are labelled as what bettors are paying, not a poll, a forecast or an official record. Advertising is shown from the spenders' own federal filings, with links to the public ad libraries.",
      "Candidates come from official state lists. Polls come only from pollsters who show their methods. Betting prices are labelled as bets.")}""")
    secs.append(f"""__CHUNK__<h2 id="refuse">What the site will not do</h2>
<ul>
<li>Score or rate any person.</li>
<li>Guess anyone's politics. A candidate's leaning is shown only from the record: a party's own published endorsement, an earlier run or office under a party label, or the candidate's own words.</li>
<li>Name individual donors.</li>
<li>Describe a member's character, beliefs or politics. A member's page shows the record. The one piece of outside writing is the first paragraph of their Wikipedia article, fenced off and labelled as not an official record.</li>
<li>Use red or blue for anything but party data.</li>
<li>Put a real bill number on an illustration.</li>
</ul>""")
    secs.append(f"""__CHUNK__<h2 id="sources">Sources</h2>
<ul class="links">
<li><a href="https://www.govinfo.gov/bulkdata/BILLSTATUS" rel="noopener">GovInfo Bill Status</a>, the Government Publishing Office and the Library of Congress</li>
<li><a href="https://clerk.house.gov/Votes" rel="noopener">Roll call votes</a>, the Clerk of the House</li>
<li><a href="https://www.senate.gov/legislative/votes_new.htm" rel="noopener">Roll call votes</a>, the United States Senate</li>
<li><a href="https://github.com/unitedstates/congress-legislators" rel="noopener">congress-legislators</a>, the members' roster</li>
<li><a href="https://www.fec.gov/data/browse-data/?tab=bulk-data" rel="noopener">Bulk data</a>, the Federal Election Commission</li>
<li><a href="https://www.cbo.gov/" rel="noopener">The Congressional Budget Office</a> and <a href="https://www.jct.gov/" rel="noopener">the Joint Committee on Taxation</a></li>
<li><a href="https://www.census.gov/geographies/mapping-files.html" rel="noopener">Boundary files</a> and counts, the Census Bureau</li>
<li><a href="https://open.pluralpolicy.com/data/" rel="noopener">Open States</a>, state legislators and committees</li>
<li>Each state's election office, for its candidate lists and results, and each state's campaign finance agency, for its money. Every state page names its own.</li>
</ul>""")
    secs.append(f"""__CHUNK__<h2 id="corrections">Corrections</h2>
{para("There is no corrections log yet. When there is one, it will be listed here.", "There is no list of fixes yet.")}""")
    toc = "".join(f'<li><a href="#{m.group(1)}">{m.group(2)}</a></li>' for s in secs for m in [re.search(r'<h2 id="([^"]+)">(.*?)</h2>', s)])
    secs = chunked(secs)
    return f"""<div class="tca-wrap">
<div class="tca-doc">
<section class="tca-hero" aria-labelledby="m-h" style="padding-bottom:0">
<p class="kicker">Method</p>
<h1 id="m-h">{words_of("How every page is made.")}</h1>
{para("Where each fact comes from, how bills are rated, and what this site will not do. Facts and judgments are kept apart, and each is labelled.",
      "Where our facts come from. How we rate bills. What we will never do.", "lede")}
</section>
<nav class="tca-toc" aria-labelledby="m-toc"><h2 id="m-toc">On this page</h2><ol>{toc}</ol></nav>
{"".join(secs)}
</div>
</div>"""


# ============================== Access ==============================

def access_body(F, version, generated):
    done = [
        "A &ldquo;Skip to content&rdquo; link is the first thing the keyboard reaches.",
        "One header, one main area and one footer, with every navigation area named.",
        "A visible focus ring on everything the keyboard can reach. No outline is taken away.",
        "Every button, menu item and link on its own is at least 44 by 44 pixels. A link inside a sentence is the size of its words.",
        "Nothing works by hovering alone. The menus open with a click, a tap or the keyboard, and Esc closes them.",
        "No single-key shortcuts, so voice control cannot set one off by accident.",
        "Eleven settings and eight presets, which combine. They are kept on this device and nowhere else.",
        "A device set to reduce motion is honoured on the first visit, before anything is touched.",
        "The fade at the edges of the screen is off under high contrast and reduced motion, replays the same way scrolling up as down, and never dims a section parked in the middle of the screen.",
        "The five icons are fully drawn even when no script runs, and every one of their moves ends at rest.",
        "The chart never puts a number on a bar, has a table version, and adds patterns under the colour-vision palettes, Calm and high contrast. Its colours hold at least 3 to 1 against every background in light, dark and high contrast, and stay apart for three kinds of colour blindness, checked by simulation.",
        "The companion is hidden from screen readers. Its control is a real button named &ldquo;Open help&rdquo;. Off loads nothing. Still draws it once.",
        "The pages reflow to 320 pixels wide without scrolling sideways.",
    ]
    notyet = [
        "The rest of the site does not have these settings yet: Plain Congress, On The Ballot, the state and county pages, the ring of cards and the cabin. Only light or dark, and motion on or off, carry across today.",
        "No one has yet walked through the site with a screen reader such as VoiceOver or NVDA. Automated checks find only part of what stops people.",
        "Plain-language versions exist only for the main text of the front door, this page and the Method page. Their reading level is checked each time the pages are built.",
        "The pages have not been timed on a four-year-old phone.",
        "The vote map and the district maps on other pages have not been checked against this list.",
        "This site makes no claim yet to meet the Web Content Accessibility Guidelines.",
    ]
    secs = [
        f"""__CHUNK__<h2 id="settings">Your settings</h2>
{para("Change these and every page that has the new shell follows. Nothing is sent anywhere: the settings live in this browser.", "Change these to make the site easier for you. They stay on this device.")}
{S.access_panel(inline=True)}""",
        f"""__CHUNK__<h2 id="aim">What we aim for</h2>
{para("The aim is the Web Content Accessibility Guidelines, version 2.2, at level AA, on every page. The site does not claim to meet them yet. This page says what is done and what is not.",
      "We want every page to work for everyone. We are not there yet. This page shows what is done.")}""",
        f"""__CHUNK__<h2 id="done">What is done</h2>
{para("On the front door, the Method page and this page:", "On these three pages:")}
<ul class="tca-check done">{"".join(f"<li>{x}</li>" for x in done)}</ul>""",
        f"""__CHUNK__<h2 id="notyet">What is not done yet</h2>
<ul class="tca-check todo">{"".join(f"<li>{x}</li>" for x in notyet)}</ul>""",
        f"""__CHUNK__<h2 id="companion">The companion</h2>
{para("The animal at the corner of the screen is optional. Its only job is to open Help, which is also in the top bar. It never speaks on its own and never makes a sound. It steps aside while you scroll, unless motion is reduced or it is Still. With motion on, pointing at it or reaching it with the keyboard makes it do a short dance made of the real animal's own moves. Choose it, still it or switch it off under Help or in the settings above.",
      "The animal in the corner only opens Help. Point at it and it does a little dance. You can stop it or turn it off.")}
<p>The seven animals are drawn on your own device with three.js (MIT licence). Each is sculpted in code from studies of how the real animal is built and how it moves. The snail's shell is shaped from a scan of a real shell by TinyWorlds, given to the public domain (CC0) at <a href="https://opengameart.org/content/snail-3d-model" rel="noopener">OpenGameArt</a>.</p>""",
        f"""__CHUNK__<h2 id="report">Report a barrier</h2>
{para("A way to report a barrier is coming. There is none on the site yet.", "Soon you will be able to tell us when something does not work for you.")}
<p>This statement was written on {esc(generated)}, for version {esc(version)}.</p>""",
    ]
    toc = "".join(f'<li><a href="#{m.group(1)}">{m.group(2)}</a></li>' for s in secs for m in [re.search(r'<h2 id="([^"]+)">(.*?)</h2>', s)])
    secs = chunked(secs)
    return f"""<div class="tca-wrap">
<div class="tca-doc">
<section class="tca-hero" aria-labelledby="a-h" style="padding-bottom:0">
<p class="kicker">Access</p>
<h1 id="a-h">{words_of("Read it your way.")}</h1>
{para("What this site does for readers with disabilities, what it does not do yet, and how to change the pages to suit you.",
      "How to make the site easier to use. What works now. What does not work yet.", "lede")}
</section>
<nav class="tca-toc" aria-labelledby="a-toc"><h2 id="a-toc">On this page</h2><ol>{toc}</ol></nav>
{"".join(secs)}
</div>
</div>"""


# ============================== build ==============================

def build(dev_root, version=None, draft=False, look=None, say=print, test=False, lab=False):
    """Writes the front door, Method and Access into dev_root. `look` is the site folder whose pages are counted (the
    same folder, unless the pages are written somewhere else to be tried)."""
    dev_root = os.path.abspath(dev_root)
    look = os.path.abspath(look or dev_root)
    version = version if version is not None else version_now()
    generated = day(dt.date.today())
    PLAIN.clear()
    A = S.build(dev_root, say=say, test=test, lab=lab)
    places = S.site_places(look)
    F = facts(look)
    faq = faq_html(F)
    out = {}
    pages = [
        ("index.html", "./", None, "The Civic Archive",
         "The public record of Congress and the fifty state legislatures, and who is on your ballot. From official sources, on one site.", home_body(F, places), False),
        (os.path.join("method", "index.html"), "../", "method", "Method: The Civic Archive",
         "Where each fact comes from, how bills are rated, and what this site will not do.", method_body(F), False),
        (os.path.join("access", "index.html"), "../", "access", "Access: The Civic Archive",
         "Reading and access settings, and a plain list of what is done and what is not.", access_body(F, version, generated), True),
    ]
    for rel, root, current, title, desc, body, inline in pages:
        text = page(A, root, title, desc, version, body, current, places, faq.replace("__ROOT__", root), generated, draft, inline_access=inline)
        if root != "./":      # the pages one folder down reach the rest of the site one level up (links only; a setting's value is left alone)
            text = re.sub(r'href="(?!https?:|#|\.\./|mailto:|data:)([^"]+)"', lambda m: f'href="../{m.group(1)}"', text)
        bad = re.findall(r"\b[a-z]+(?:_[a-z0-9]+)+\.py\b|\b[\w-]+\.sqlite\b|\brubric_v1\b|\bCHANGELOG\b", text)
        if bad:
            raise SystemExit(f"build_home: {rel} names the kit's own files: {sorted(set(bad))}")
        path = os.path.join(dev_root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        out[rel] = len(text.encode("utf-8"))
    grades = [(round(fk_grade(t), 1), t) for t in PLAIN]
    worst = max(grades) if grades else (0, "")
    over = [g for g in grades if g[0] > 7.0]
    say(f"Home: wrote " + ", ".join(f"{k.replace(os.sep, '/')} ({v / 1e3:,.0f} KB)" for k, v in out.items())
        + f"; {len(PLAIN)} plain-language blocks, Flesch-Kincaid grade at most {worst[0]}"
        + (f"; {len(over)} above 7: " + " | ".join(f"{g}: {t[:60]}" for g, t in over) if over else " (all at 7 or below)"))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=os.path.join(HERE, "site", "dev"), help="where to write the pages (default site/dev)")
    ap.add_argument("--look", default=None, help="the site folder to count pages in, when writing somewhere else to try them")
    ap.add_argument("--draft", action="store_true", help="show the small 'draft for feedback' note the draft site carries")
    ap.add_argument("--test", action="store_true", help="also write the companions' side-by-side test page (never publish it)")
    ap.add_argument("--lab", action="store_true", help="also write the companions' still-frame lab, _companion_lab.html (never publish it)")
    a = ap.parse_args()
    build(a.root, draft=a.draft, look=a.look, test=a.test, lab=a.lab)


if __name__ == "__main__":
    main()
