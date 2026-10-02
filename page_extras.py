#!/usr/bin/env python3
"""
page_extras.py - two things every builder of the draft adds to its finished page (John, 2026-10-02).

1. "Take a break": a small cabin icon with those words in the page's header, leading to the cabin (cabin.html at the
   root of the draft). Before the reader leaves, the page keeps its own address (with its #part) and its title in
   sessionStorage under "break"; the cabin shows a way back only when that address is on this same site.

2. "Insights on my location" (ballot pages only): a bar that stays at the top of the page. On a click, never before,
   the browser is asked for the reader's location; the state is worked out on the device from the state shapes the
   ballot pages draw (ballot/where.json, the same Albers shapes, fetched only then), and the reader is taken to that
   state's ballot page at "Your ballot". The location is not put in the address: a mark in sessionStorage ("insights")
   is read by the state page on arrival, which then runs its own "Use my location". Nothing is sent anywhere.

    html = page_extras.add(html, root="../")                               a page of the record
    html = page_extras.add(html, root="../../", ballot="../", here="mn")   a ballot page
    page_extras.write_where(<site>/dev/ballot)                             the state shapes and the list of state pages

`root` is where the draft's own root is, seen from the page; `ballot` where the ballot space's root is; `here` the
ballot page's own folder ("us", "states", a state's two letters, or "" for the ballot door). The one-file archive has no
neighbours, so it gets neither.
"""

import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
NOT_STATES = {"DC", "PR", "GU", "VI", "AS", "MP"}

BREAK_CSS = """
/* "Take a break": the way to the cabin, on every page (John, 2026-10-02) */
.tbreak{box-sizing:border-box;display:inline-flex;align-items:center;gap:6px;height:36px;padding:0 12px 0 9px;border-radius:999px;border:1px solid var(--line,rgba(128,128,128,.45));background:var(--surface,transparent);color:var(--muted,inherit);text-decoration:none;font-size:12.5px;font-weight:600;line-height:1;flex:none;white-space:nowrap;transition:color .15s,border-color .15s}
.tbreak:hover{color:var(--ink,inherit);border-color:var(--line-strong,currentColor)}
.tbreak:focus-visible{outline:2px solid var(--accent,currentColor);outline-offset:2px}
.tbreak svg{width:18px;height:18px;flex:none;stroke:currentColor;fill:none;stroke-width:1.7;stroke-linecap:round;stroke-linejoin:round}
__NARROW__{.tbreak{padding:0;width:36px;justify-content:center}.tbreak span{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}__TIGHT__}
/* a header row with no room left lets its section links scroll inside themselves, so the page never scrolls sideways */
.top .wrap>.nav{min-width:0;overflow-x:auto;scrollbar-width:none}.top .wrap>.nav::-webkit-scrollbar{display:none}
@media (max-width:560px){.top .tbreak{width:34px;height:34px}}
@media (prefers-reduced-motion: reduce){.tbreak{transition:none}}
"""

BREAK_HTML = ('<a class="tbreak" id="tbreak" href="__CABIN__" title="Take a break: step into the cabin for a while. A way back to this page waits there.">'
              '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2.8 11.6 12 4l9.2 7.6"/><path d="M5.4 9.6v10h13.2v-10"/><path d="M10 19.6v-5.2h4v5.2"/><path d="M16.6 7.7V4.6"/><path d="M7.4 12.6h1.4"/></svg>'
              '<span>Take a break</span></a>')

BREAK_JS = """
<script>
/* "Take a break": before leaving for the cabin, keep where the reader was, so the cabin can offer the way back */
(function(){ var a = document.getElementById("tbreak"); if (!a) return;
  var keep = function(){ try { var t = "", hs = document.querySelectorAll("h1");      /* the page's own heading when one is showing (a bill, a race, a member), else its title */
      for (var i = 0; i < hs.length && !t; i++) if (hs[i].offsetParent !== null) t = (hs[i].textContent || "").replace(/\\s+/g, " ").trim();
      sessionStorage.setItem("break", JSON.stringify({u: location.href, t: (t || document.title).slice(0, 120)})); } catch (e) {} };
  a.addEventListener("click", keep); a.addEventListener("auxclick", keep);
})();
</script>
"""

INS_CSS = """
/* "Insights on my location": always at the top of every ballot page (John, 2026-10-02) */
.insbar{box-sizing:border-box;width:100%;background:color-mix(in srgb,var(--accent,#2f6fed) 13%,var(--bg,#fff));border-bottom:1px solid color-mix(in srgb,var(--accent,#2f6fed) 35%,transparent);color:var(--ink,inherit);font-size:13px;line-height:1.35}
.insbar.alone{position:sticky;top:0;z-index:60}
.insrow{display:flex;align-items:center;justify-content:center;gap:10px;min-height:38px;padding:4px 14px;flex-wrap:nowrap}
.insgo{all:unset;box-sizing:border-box;cursor:pointer;display:inline-flex;align-items:center;gap:7px;height:30px;padding:0 14px 0 10px;border-radius:999px;background:var(--accent,#2f6fed);color:var(--bg,#fff);font-weight:700;font-size:13px;white-space:nowrap;flex:none}
.insgo:hover{filter:brightness(1.08)}
.insgo:focus-visible{outline:2px solid var(--ink,currentColor);outline-offset:2px}
.insgo[aria-busy="true"]{opacity:.75;cursor:progress}
.insgo svg{width:16px;height:16px;flex:none;stroke:currentColor;fill:none;stroke-width:1.9;stroke-linecap:round;stroke-linejoin:round}
.inshint{color:var(--muted,inherit);min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.insmsg{display:flex;align-items:flex-start;justify-content:center;gap:10px;padding:2px 14px 8px;text-align:center}
.insmsg[hidden]{display:none}
.insmsg p{margin:0;max-width:760px}
.insmsg a{color:inherit;font-weight:700}
.insmsg button{all:unset;box-sizing:border-box;cursor:pointer;flex:none;padding:0 8px;border-radius:999px;border:1px solid var(--line,rgba(128,128,128,.45));font-size:12px;line-height:20px;color:var(--muted,inherit)}
.insmsg button:focus-visible{outline:2px solid var(--accent,currentColor);outline-offset:2px}
@media (max-width:760px){.inshint{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}.insrow{min-height:36px}}
"""

INS_HTML = """<div class="insbar__ALONE__" id="insbar" role="region" aria-label="Insights on my location">
  <div class="insrow"><button type="button" class="insgo" id="insgo" aria-describedby="inshint" title="Asks your browser for your location, works out your state on this device, and opens your own ballot. Your location is never sent anywhere."><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 21s-6-5.3-6-11a6 6 0 0 1 12 0c0 5.7-6 11-6 11z"/><circle cx="12" cy="10" r="2.2"/></svg>Insights on my location</button>
    <span class="inshint" id="inshint">Opens your own ballot. Your location is worked out on this device and never sent anywhere.</span></div>
  <div class="insmsg" id="insmsg" role="status" aria-live="polite" hidden><p id="instext"></p><button type="button" id="insclose" aria-label="Close this message">Close</button></div>
</div>
"""

INS_JS = """
<script>
/* "Insights on my location": on a click, never before, the browser is asked where the reader is; the state is worked out
   on this device from the state shapes the ballot maps draw; the reader is taken to that state's ballot page at "Your
   ballot". The location is not put in any address: a mark in sessionStorage is read by the page they land on, which
   then runs its own "Use my location". Nothing is sent anywhere. */
(function(){
  var btn = document.getElementById("insgo"), box = document.getElementById("insmsg"), text = document.getElementById("instext"); if (!btn) return;
  var ROOT = __BROOT__, HERE = __HEREJS__, WHERE = null;
__GEO__
  function say(words, list){ text.textContent = words; if (list) { text.append(" "); var a = document.createElement("a"); a.href = ROOT + "states/"; a.textContent = "See the list of states"; text.append(a); text.append("."); } box.hidden = false; }
  function done(){ btn.removeAttribute("aria-busy"); }
  document.getElementById("insclose").addEventListener("click", function(){ box.hidden = true; btn.focus(); });
  function stateAt(w, lon, lat){ var pt = albersUsa(lon, lat); if (!pt) return null;
    for (var s in w.map) { var b = w.box[s]; if (!b || pt[0] < b[0] || pt[0] > b[2] || pt[1] < b[1] || pt[1] > b[3]) continue; if (inShape(pt, pathRings(w.map[s]))) return s; }
    return null; }
  btn.addEventListener("click", function(){
    if (btn.getAttribute("aria-busy")) return;
    if (!navigator.geolocation) { say("Location isn't available in this browser, so nothing was looked up. Pick your state from the list instead.", true); return; }
    btn.setAttribute("aria-busy", "true"); say("Finding your state\\u2026");
    var where = WHERE || (WHERE = fetch(ROOT + "where.json").then(function(r){ if (!r.ok) throw new Error(r.status); return r.json(); }));
    where.catch(function(){ WHERE = null; });
    navigator.geolocation.getCurrentPosition(function(pos){ where.then(function(w){
      done();
      var st = stateAt(w, pos.coords.longitude, pos.coords.latitude);
      if (!st) { say("That spot isn't inside one of the fifty states on our map, so there is no state ballot to open for it. Pick a state from the list instead.", true); return; }
      var code = st.toLowerCase(), to = w.pages.indexOf(code) >= 0 ? code : "us", mark = function(){ try { sessionStorage.setItem("insights", String(Date.now())); } catch (e) {} };
      if (to === HERE) {      /* already on the right page: do it in place */
        var y = document.getElementById("yloc"), sec = document.getElementById("yours");
        if (y && sec) { box.hidden = true; sec.scrollIntoView({block: "start"}); y.click(); y.focus({preventScroll: true}); }
        else { mark(); box.hidden = true; location.hash = "yours"; }
        return; }
      mark(); say("You are in " + (w.names[st] || st) + ". Opening your ballot\\u2026"); location.href = ROOT + to + "/#yours";
    }, function(){ done(); say("The map of the states could not be loaded, so your state could not be worked out. Check your connection, or pick a state from the list.", true); }); },
    function(err){ done(); say(err && err.code === 1 ? "Your browser did not share a location, so nothing was looked up and nothing was kept. Pick your state from the list instead."
      : "Your location could not be worked out just now. Try again, or pick your state from the list.", true); },
    {timeout: 15000, maximumAge: 600000});
  });
})();
</script>
"""

# what a ballot page runs once its own "Use my location" button is wired: follow the mark the bar left, once
ARRIVE_JS = ('try { const m = +sessionStorage.getItem("insights"); if (m) { sessionStorage.removeItem("insights"); '
             'if (Date.now() - m < 120000) setTimeout(() => { const y = $("#yloc"), s = $("#yours"); if (y) { if (s) s.scrollIntoView({block: "start"}); y.click(); } }, 0); } } catch (e) {}')


def cabin_name():
    """The cabin's file name at the root of the draft: cabin.html, or the root itself once the cabin is the landing page."""
    try:
        with open(os.path.join(HERE, "build_door.py"), encoding="utf-8") as fh:
            if re.search(r"^CABIN_FIRST\s*=\s*True\b", fh.read(), re.M):
                return ""
    except OSError:
        pass
    return "cabin.html"


def _once(html, mark, what):
    if html.count(mark) != 1:
        raise SystemExit(f"page_extras: the page should have exactly one '{mark}' ({what}); it has {html.count(mark)}.")


def add(html, root="../", ballot=None, here="", words=1100):
    """The finished page with "Take a break" in its header and, when `ballot` is given, the "Insights on my location"
    bar at its top. `words` is the width below which the break link shows its icon alone (0: at every width)."""
    _once(html, "</head>", "the end of the head")
    _once(html, "</body>", "the end of the body")
    _once(html, '<div class="tools">', "the header's tools")
    _once(html, '<header class="top">', "the header")
    # words=0: a header with no room for the words (the record pages, whose row holds a search box too) shows the icon
    # alone at every width, with the words kept for screen readers and as the tooltip, and gives up the search key hint
    css = (BREAK_CSS.replace("__NARROW__", f"@media (max-width:{words}px)" if words else "@media all")
           .replace("__TIGHT__", "" if words else ".top .kbtn kbd{display:none}"))
    cabin = (root + cabin_name()) or "./"
    js = BREAK_JS
    html = html.replace('<div class="tools">', '<div class="tools">\n      ' + BREAK_HTML.replace("__CABIN__", cabin), 1)
    if ballot is not None:
        from build_state_dev import borrow      # the Albers projection and the point-in-shape test, as every map on the site uses them
        css += INS_CSS
        door = here == ""
        bar = INS_HTML.replace("__ALONE__", " alone" if door else "")
        if not door:      # the header is taller by the bar: what a jump lands on still clears it
            css += ".bsec,.fold{scroll-margin-top:118px}#local,#states{scroll-margin-top:124px}\n"
        html = html.replace('<header class="top">', (bar + '<header class="top">') if door else ('<header class="top">\n' + bar), 1)
        js += (INS_JS.replace("__GEO__", borrow("GEO")).replace("__BROOT__", json.dumps(ballot)).replace("__HEREJS__", json.dumps(here)))
    html = html.replace("</head>", "<style>" + css + "</style>\n</head>", 1)
    return html.replace("</body>", js + "</body>", 1)


def write_where(ballot_dir):
    """ballot/where.json: the fifty states' shapes (the same Albers paths the ballot maps draw), their boxes and names,
    and which states have a ballot page of their own right now. Fetched only when the bar is clicked."""
    from build_site_dev import state_paths
    shapes = {k: v for k, v in state_paths(os.path.join(HERE, "us_states_albers.json")).items() if k not in NOT_STATES}
    pages = sorted(d for d in os.listdir(ballot_dir) if len(d) == 2 and d != "us" and os.path.exists(os.path.join(ballot_dir, d, "index.html"))) if os.path.isdir(ballot_dir) else []
    out = {"map": {k: v["d"] for k, v in shapes.items()}, "box": {k: v["bbox"] for k, v in shapes.items()}, "names": {k: v.get("name") or k for k, v in shapes.items()}, "pages": pages}
    os.makedirs(ballot_dir, exist_ok=True)
    text = json.dumps(out, ensure_ascii=False, separators=(",", ":"))
    path = os.path.join(ballot_dir, "where.json")
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    return len(shapes), pages
