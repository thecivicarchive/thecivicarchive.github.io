#!/usr/bin/env python3
"""
build_cabin.py - the landing page: a log cabin a visitor walks around in (John, 2026-10-01).

    python build_cabin.py --out site/dev/index.html [--draft]

The page is one small file. It draws the room with cabin_room3d.js (copied beside the page as cabin3d.js), the kit's
own copy of three.js (vendor/three.module.min.js, MIT) and its add-ons from the same release (vendor/jsm/), and the
materials, furniture and photographs kept in cabin_assets/ (CC0 textures and models from Poly Haven and ambientCG,
public-domain National Park Service photographs; credits.json there lists every one). All of it is copied beside the
page, so nothing comes from another server. Two posters glow on the far wall, either side of a gable wall of windows on
the Rocky Mountains, which show the visitor's own time of day and season (worked out on the device; nothing is sent
anywhere): one poster opens On The Ballot, the other the ring of cards for Legislation & Legislatures (rooms.html,
written by build_door.py, which also calls this builder whenever it builds the front door).

The room is never the only way in: the same two doors are ordinary links at the foot of the page, with a "Plain view"
link to the ring of cards. A device that cannot draw the room, and a visitor who has turned Motion off, get those links
on a still page. Add ?time=morning|afternoon|dusk|night or ?season=winter|spring|summer|autumn to the address to see
another hour or season.
"""

import argparse
import hashlib
import html as html_mod
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOM_JS = "cabin_room3d.js"
THREE_JS = os.path.join("vendor", "three.module.min.js")
ADDONS = os.path.join("vendor", "jsm")
ASSETS = "cabin_assets"

POSTERS = [
    {"url": "ballot/", "look": "ballot", "kicker": "On The Ballot", "head": "Meet everyone asking for your vote.",
     "sub": "Every race, from Congress to your county, straight from the official lists.", "cta": "Step in", "foot": "November 3, 2026",
     "name": "On The Ballot", "line": "Meet everyone asking for your vote"},
    {"url": "rooms.html", "look": "record", "kicker": "Legislation & Legislatures", "head": "See what they did with the last one.",
     "sub": "Every bill, every vote, every member. Congress and all fifty statehouses, on the record.", "cta": "Open the record",
     "foot": "Congress and the fifty states", "name": "Legislation & Legislatures", "line": "See what they did with the last one"},
]

PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>The Civic Archive</title>
<meta name="description" content="The public record and who is on your ballot. Step into the cabin and pick a door: On The Ballot, or Legislation and Legislatures.">
<meta name="version" content="__VERSION__">
__BRAND__
<meta name="theme-color" content="#1a120b">
<style>
:root{--ink:#f6ecd6;--dim:#d9c9a8;--chip:rgba(22,15,9,.72);--line:rgba(246,236,214,.28);--gold:#f0c060;--serif:Georgia,"Times New Roman",serif;--sans:system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
*{box-sizing:border-box}
html,body{margin:0;height:100%;background:#1a120b;color:var(--ink);font-family:var(--sans);font-size:16px;line-height:1.4;overflow:hidden;-webkit-font-smoothing:antialiased}
#room{position:fixed;inset:0;width:100%;height:100%;display:block;outline:none}
.brand{position:fixed;left:16px;top:14px;z-index:3;max-width:calc(100% - 32px);pointer-events:none;text-shadow:0 1px 10px rgba(0,0,0,.75)}
.brand b{display:block;font-family:var(--serif);font-weight:400;font-size:clamp(22px,2.6vw,32px);line-height:1.05}
.brand span{display:block;font-size:13.5px;color:var(--dim);margin-top:3px}
.wip{position:fixed;right:14px;top:14px;z-index:3;background:var(--chip);border:1px solid var(--line);border-radius:999px;padding:6px 12px;font-size:12px;color:var(--dim);backdrop-filter:blur(6px)}
.wip a{color:var(--ink)}
.hint{position:fixed;left:50%;top:22%;transform:translateX(-50%);z-index:3;margin:0;background:var(--chip);border:1px solid var(--line);border-radius:14px;padding:10px 16px;font-size:14.5px;text-align:center;max-width:min(560px,calc(100% - 32px));backdrop-filter:blur(6px);transition:opacity .9s ease;pointer-events:none}
.hint.gone{opacity:0}
.load{position:fixed;left:50%;bottom:calc(84px + env(safe-area-inset-bottom));transform:translateX(-50%);z-index:3;margin:0;background:var(--chip);border:1px solid var(--line);border-radius:999px;padding:6px 14px;font-size:12.5px;color:var(--dim);backdrop-filter:blur(6px);transition:opacity .8s ease;pointer-events:none;white-space:nowrap}
.load.gone{opacity:0}
.ways{position:fixed;left:50%;bottom:calc(14px + env(safe-area-inset-bottom));transform:translateX(-50%);z-index:3;display:flex;gap:10px;justify-content:center;align-items:stretch;flex-wrap:wrap;width:max-content;max-width:calc(100% - 24px)}
.ways a{display:flex;flex-direction:column;justify-content:center;text-decoration:none;color:var(--ink);background:var(--chip);border:1px solid var(--line);border-radius:14px;padding:9px 16px;backdrop-filter:blur(6px);transition:border-color .2s ease,background .2s ease,box-shadow .2s ease}
.ways a b{font-size:15px;font-weight:650}.ways a span{font-size:12.5px;color:var(--dim)}
.ways a:hover,.ways a:focus-visible,.ways a.hot{border-color:var(--gold);background:rgba(40,28,14,.86);box-shadow:0 0 0 1px var(--gold),0 0 22px rgba(240,192,96,.35);outline:none}
/* the two doors, as signs that glow like the posters they stand for (John, 2026-10-01: bolder, stylish, glowing) */
.ways a[data-i]{--glow:240,192,96;position:relative;padding:13px 22px 13px 20px;border:1.5px solid rgba(var(--glow),.85);border-radius:16px;
  background:linear-gradient(180deg,rgba(58,39,18,.9),rgba(22,15,9,.92));box-shadow:0 0 0 1px rgba(var(--glow),.25),0 0 26px rgba(var(--glow),.42),inset 0 0 20px rgba(var(--glow),.14);
  animation:sign 2.6s ease-in-out infinite;transition:transform .18s ease,border-color .2s ease,box-shadow .2s ease}
.ways a[data-look="ballot"]{--glow:140,186,255;animation-delay:-1.3s}
.ways a[data-i] b{font-family:var(--serif);font-size:20px;font-weight:700;letter-spacing:.01em;color:#fff6de;text-shadow:0 0 14px rgba(var(--glow),.75)}
.ways a[data-i] b::after{content:"\00a0\203A";color:rgb(var(--glow))}
.ways a[data-i] span{font-size:13px;color:#eadcbd}
.ways a[data-i]:hover,.ways a[data-i]:focus-visible,.ways a[data-i].hot{transform:translateY(-3px) scale(1.035);border-color:rgb(var(--glow));background:linear-gradient(180deg,rgba(74,50,22,.94),rgba(30,20,11,.94));
  box-shadow:0 0 0 2px rgba(var(--glow),.9),0 0 44px rgba(var(--glow),.75),inset 0 0 26px rgba(var(--glow),.25);animation:none}
@keyframes sign{0%,100%{box-shadow:0 0 0 1px rgba(var(--glow),.25),0 0 22px rgba(var(--glow),.34),inset 0 0 18px rgba(var(--glow),.12)}50%{box-shadow:0 0 0 1px rgba(var(--glow),.55),0 0 40px rgba(var(--glow),.62),inset 0 0 24px rgba(var(--glow),.2)}}
.ways a[hidden]{display:none}
/* the way back (John, 2026-10-02): a third sign, shown only when the visitor came here from a page of this site */
.ways a.back{--glow:255,226,170;position:relative;padding:13px 22px 13px 20px;border:1.5px solid rgba(var(--glow),.85);border-radius:16px;max-width:min(340px,100%);
  background:linear-gradient(180deg,rgba(58,39,18,.9),rgba(22,15,9,.92));box-shadow:0 0 0 1px rgba(var(--glow),.25),0 0 26px rgba(var(--glow),.42),inset 0 0 20px rgba(var(--glow),.14);
  animation:sign 2.6s ease-in-out infinite;animation-delay:-.6s;transition:transform .18s ease,border-color .2s ease,box-shadow .2s ease}
.ways a.back b{font-family:var(--serif);font-size:20px;font-weight:700;letter-spacing:.01em;color:#fff6de;text-shadow:0 0 14px rgba(var(--glow),.75)}
.ways a.back b::before{content:"\2039\00a0";color:rgb(var(--glow))}
.ways a.back span{font-size:13px;color:#eadcbd;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.ways a.back:hover,.ways a.back:focus-visible,.ways a.back.hot{transform:translateY(-3px) scale(1.035);border-color:rgb(var(--glow));background:linear-gradient(180deg,rgba(74,50,22,.94),rgba(30,20,11,.94));
  box-shadow:0 0 0 2px rgba(var(--glow),.9),0 0 44px rgba(var(--glow),.75),inset 0 0 26px rgba(var(--glow),.25);animation:none}
.ways a.plain{padding:9px 14px;font-size:13.5px;color:var(--dim);align-self:center}
.foot{position:fixed;right:12px;bottom:calc(6px + env(safe-area-inset-bottom));z-index:2;margin:0;font-size:11px;color:rgba(246,236,214,.6);text-shadow:0 1px 6px rgba(0,0,0,.8);max-width:min(60vw,560px);text-align:right}
.foot button{font:inherit;color:inherit;background:none;border:0;padding:0;text-decoration:underline;cursor:pointer}
#fade{position:fixed;inset:0;z-index:5;background:#120c07;opacity:0;pointer-events:none;transition:opacity .45s ease}
#fade.on{opacity:1}
dialog.credits{max-width:min(620px,calc(100% - 32px));border:1px solid var(--line);border-radius:14px;background:#221710;color:var(--ink);padding:18px 20px;font-size:14px}
dialog.credits::backdrop{background:rgba(0,0,0,.55)}
dialog.credits h2{font-family:var(--serif);font-weight:400;font-size:22px;margin:0 0 6px}
dialog.credits p{margin:6px 0;color:var(--dim)}
dialog.credits ul{margin:8px 0 0;padding-left:18px}dialog.credits li{margin:3px 0}
dialog.credits a{color:var(--ink)}
dialog.credits form{margin:14px 0 0;text-align:right}dialog.credits button{font:inherit;color:var(--ink);background:var(--chip);border:1px solid var(--line);border-radius:999px;padding:6px 14px;cursor:pointer}
/* the still page: no 3D on this device, or Motion is off */
body.flat{overflow:auto;background:radial-gradient(1200px 700px at 50% 0%,#3a2916 0%,#1a120b 70%)}
body.flat #room,body.flat .hint,body.flat .load{display:none}
body.flat .brand{position:static;padding:10vh 20px 0;text-align:center;max-width:none}
body.flat .brand b{font-size:clamp(34px,7vw,64px)}
body.flat .ways{position:static;transform:none;margin:6vh auto 0;flex-direction:column;width:min(520px,calc(100% - 32px))}
body.flat .ways a{padding:18px 20px}body.flat .ways a b{font-size:19px}
body.flat .foot{position:static;text-align:center;margin:5vh auto 24px;max-width:none}
body.flat .flatnote{display:block}
.flatnote{display:none;text-align:center;color:var(--dim);font-size:14px;margin:18px auto 0;max-width:520px;padding:0 20px}
@media (prefers-reduced-motion: reduce){.ways a[data-i],.ways a.back{animation:none}}
@media (max-width:640px){.ways a span{display:none}.ways a,.ways a[data-i],.ways a.back{padding:11px 14px}.ways a[data-i] b,.ways a.back b{font-size:16.5px}body.flat .ways a.back span{display:block}.foot{display:none}.wip{font-size:11px;padding:5px 9px;top:68px;left:16px;right:auto;white-space:nowrap}.hint{top:16%}.load{bottom:calc(96px + env(safe-area-inset-bottom))}}
@media (prefers-reduced-motion: reduce){.hint,#fade,.ways a,.load{transition:none}}
</style>
</head>
<body>
<canvas id="room" tabindex="0" role="img" aria-label="A log great room in the Rockies: round-log walls and rafters under a vaulted roof, a stacked-stone fireplace with a fire burning, leather and upholstered seating on a red rug, and a gable wall of windows on the mountains. Two glowing posters on the far wall are the doors to the site: On The Ballot, and Legislation and Legislatures. The same two doors are links at the foot of this page. When you came here from a page of this site, the plank door behind you glows and leads back to it, and a third link at the foot of the page does the same."></canvas>
<header class="brand"><b>The Civic Archive</b><span>The public record, and who is on your ballot</span></header>
__WIP__
<p class="hint" id="hint"></p>
<p class="load" id="load" role="status" aria-live="polite"></p>
<p class="flatnote">This device is showing the plain page. The two doors are below.</p>
<nav class="ways" aria-label="The doors">
__WAYS__
  <a class="back" id="back" href="__RING__" hidden><b>Back to where you were</b><span id="backt"></span></a>
  <a class="plain" href="__RING__" title="The same doors as a ring of cards, with no room to walk around">Plain view</a>
</nav>
<p class="foot" id="foot">v__VERSION__</p>
<dialog class="credits" id="credits">
<h2>What the room is made of</h2>
<p>The materials, furniture and photographs in this room are free works, kept with the site and credited here.</p>
__CREDITS__
<form method="dialog"><button>Close</button></form>
</dialog>
<div id="fade" aria-hidden="true"></div>
<script type="module">
const POSTERS = __POSTERS__, VIEWS = __VIEWS__;
const $ = s => document.querySelector(s), q = new URLSearchParams(location.search);
const stored = k => { try { return localStorage.getItem(k); } catch (e) { return null; } };
const calm = stored("motion") ? stored("motion") === "off" : matchMedia("(prefers-reduced-motion: reduce)").matches;
const touch = matchMedia("(pointer: coarse)").matches;
const ways = [...document.querySelectorAll(".ways a[data-i]")], hint = $("#hint"), fade = $("#fade"), load = $("#load"), foot = $("#foot");
let room = null, leaving = false, view = null, when = "";
/* the way back: a page of this site kept its own address before its "Take a break" link was followed. Only an address
   on this same site, under this page's own folder, is ever followed; anything else is ignored. */
function wayBack(){
  try { const o = JSON.parse(sessionStorage.getItem("break") || "null"); if (!o || typeof o.u !== "string") return null;
    const u = new URL(o.u, location.href), root = new URL("./", location.href), self = p => p.replace(/index\.html$/, "");
    if (!/^https?:$/.test(u.protocol) || u.origin !== location.origin || u.username || u.password || !u.pathname.startsWith(root.pathname) || self(u.pathname) === self(location.pathname)) return null;
    return {url: u.href, title: typeof o.t === "string" ? o.t.replace(/\s+/g, " ").trim().slice(0, 90) : ""};
  } catch (e) { return null; }
}
const prior = wayBack(), backA = $("#back");
if (prior) { backA.href = prior.url; $("#backt").textContent = prior.title || "The page you came from"; backA.hidden = false; }
const forget = () => { try { sessionStorage.removeItem("break"); } catch (e) {} };
function goPrior(){ if (!prior || leaving) return; forget(); leave(prior.url); }
backA.addEventListener("click", e => { if (!prior) { e.preventDefault(); return; } forget(); });
function leave(url){ if (leaving) return; leaving = true; if (calm) { location.href = url; return; } fade.classList.add("on"); setTimeout(() => { location.href = url; }, 430); }
addEventListener("pageshow", () => { leaving = false; fade.classList.remove("on"); });      /* coming back with the Back button */
function footer(){
  const words = {morning: "morning", afternoon: "afternoon", dusk: "dusk", night: "night"}[when] || when;
  let s = `v__VERSION__ · Outside it is ${words}, by your device’s clock. Nothing is sent anywhere.`;
  if (view) s += ` The view is a National Park Service photograph` + (view.caption ? `: ${view.caption}` : "") + (view.shown ? "" : ` (shown for ${view.season}; there is no ${view.wanted} picture yet)`) + ".";
  foot.innerHTML = ""; foot.append(s + " "); const b = document.createElement("button"); b.type = "button"; b.textContent = "Credits"; b.addEventListener("click", () => $("#credits").showModal()); foot.append(b);
}
try {
  const m = await import("./cabin3d.js?v=__ROOMHASH__");
  load.textContent = "Setting the room up…";
  room = m.start($("#room"), {back: !!prior, onBack: () => goPrior(), posters: POSTERS, views: VIEWS, assets: "cabin_assets/", when: q.get("time") || undefined, season: q.get("season") || undefined, calm,
    lite: q.has("lite") ? q.get("lite") !== "0" : undefined,
    onHover: i => { ways.forEach((a, k) => a.classList.toggle("hot", k === i)); backA.classList.toggle("hot", i === 2); },
    onLeave: url => { forget(); leave(url); },
    onMove: () => setTimeout(() => hint.classList.add("gone"), 2600),
    onProgress: (done, total) => { load.textContent = `Setting the room up… ${Math.min(100, Math.round(done / Math.max(total, 1) * 100))}%`; },
    onReady: () => { load.textContent = "The room is ready."; setTimeout(() => load.classList.add("gone"), 1200); },
    onView: v => { view = v; footer(); }});
  if (room) {
    window.__cabin = room;
    when = q.get("time") || m.whenNow(); footer();
    hint.textContent = touch ? "Drag to look around. Tap the floor to walk there. The glowing posters are doors: tap one to go in."
                             : "Walk with the arrow keys or W, A, S, D. Drag to look around. The glowing posters are doors: click one to go in.";
    if (prior) { hint.textContent += " The door behind you glows too: it leads back to where you were.";
      backA.addEventListener("focus", () => room.look(2)); backA.addEventListener("click", e => { if (calm || e.metaKey || e.ctrlKey || e.shiftKey) return; e.preventDefault(); room.goBack(); setTimeout(goPrior, 2600); }); }      /* the timer: a page that is not being drawn still gets there */
    ways.forEach((a, i) => { a.addEventListener("focus", () => room.look(i)); a.addEventListener("click", e => { if (calm || e.metaKey || e.ctrlKey || e.shiftKey) return; e.preventDefault(); room.go(i); }); });
    setTimeout(() => hint.classList.add("gone"), 14000);
    setTimeout(() => { if (!load.classList.contains("gone")) load.classList.add("gone"); }, 40000);
  }
} catch (e) { room = null; }
if (!room) { document.body.classList.add("flat"); foot.textContent = "v__VERSION__"; }
</script>
<noscript><style>#room,.hint,.load{display:none}html,body{overflow:auto}</style></noscript>
</body>
</html>
"""


def version_now():
    """The newest heading of CHANGELOG.md: '## v4.0.078 — 2026-10-01 — title'."""
    try:
        with open(os.path.join(HERE, "CHANGELOG.md"), encoding="utf-8") as fh:
            for line in fh:
                m = re.match(r"##\s+v(\d+\.\d+\.\d+)\b", line)
                if m:
                    return m.group(1)
    except OSError:
        pass
    return ""


def copy_file(src, dst):
    """Copies src to dst unless dst already holds the same bytes; True if it wrote."""
    data = open(src, "rb").read()
    if os.path.exists(dst) and open(dst, "rb").read() == data:
        return False
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with open(dst, "wb") as fh:
        fh.write(data)
    return True


def copy_tree(src, dst, skip=()):
    """Copies every file under src to the same place under dst (unchanged files are left alone). Returns (files, bytes)."""
    n = total = 0
    for root, _dirs, files in os.walk(src):
        for f in files:
            if f in skip:
                continue
            s = os.path.join(root, f)
            copy_file(s, os.path.join(dst, os.path.relpath(s, src)))
            n += 1
            total += os.path.getsize(s)
    return n, total


def read_json(path, default):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def credits_html(credits, views):
    """The list behind the page's Credits button: every free work in the room, with its author, licence and source."""
    e = html_mod.escape
    items = []
    for c in credits:
        who = ", ".join(c.get("authors") or [])
        kind = {"texture": "material", "model": "model"}.get(c.get("kind"), c.get("kind", ""))
        items.append(f'<li><a href="{e(c["source"])}" rel="noopener" target="_blank">{e(c.get("name") or c["id"])}</a> ({e(kind)})'
                     + (f" by {e(who)}" if who else "") + f", {e(c.get('licence', 'CC0'))}</li>")
    seen = set()
    for hour, lst in (views or {}).items():
        for v in lst:
            key = v.get("file")
            if key in seen:
                continue
            seen.add(key)
            items.append(f'<li><a href="{e(v.get("source", "https://www.nps.gov/npgallery"))}" rel="noopener" target="_blank">{e(v.get("caption") or "Photograph")}</a>'
                         f' (photograph, {e(v.get("credit") or "NPS photo")}), public domain</li>')
    items.append('<li><a href="https://threejs.org/" rel="noopener" target="_blank">three.js</a> r169 draws the room (MIT licence)</li>')
    return "<ul>" + "\n".join(items) + "</ul>"


def _brand_tags():
    """The tab icon and the share tags (brand.py); the cabin shares the home's card. Its own dark theme colour stays."""
    import brand
    from build_shell import BASE_URL
    return brand.head_tags("./", BASE_URL, "The Civic Archive: the cabin",
                           "Step into a log cabin in the Rockies and pick a door: On The Ballot, or Legislation and Legislatures.",
                           f"{BASE_URL}/og/home.png", f"{BASE_URL}/cabin.html", theme=False)


def write(out, version=None, draft=False, ring="rooms.html", say=print):
    """Writes the cabin page to `out`, and beside it cabin3d.js, vendor/three.module.min.js and its add-ons, and the
    room's assets. `ring` is where the ring of cards lives, seen from the cabin: rooms.html, beside the front door."""
    out = os.path.abspath(out)
    root = os.path.dirname(out)
    version = version if version is not None else version_now()
    doors = [dict(p, url=ring if p["look"] == "record" else p["url"]) for p in POSTERS]
    ways = "\n".join(f'  <a data-i="{i}" data-look="{p["look"]}" href="{p["url"]}"><b>{p["name"].replace("&", "&amp;")}</b><span>{p["line"]}</span></a>' for i, p in enumerate(doors))
    wip = ('<div class="wip">A draft for feedback. <a href="https://thecivicarchive.github.io/">The live site</a></div>') if draft else ""
    posters = [{k: p[k] for k in ("url", "look", "kicker", "head", "sub", "cta", "foot")} for p in doors]
    views = read_json(os.path.join(HERE, ASSETS, "view", "views.json"), {})
    credits = read_json(os.path.join(HERE, ASSETS, "credits.json"), [])
    js = lambda v: json.dumps(v, ensure_ascii=False).replace("</", "<\\/")
    room_hash = hashlib.sha1(open(os.path.join(HERE, ROOM_JS), "rb").read()).hexdigest()[:10]      # a browser keeps the old room otherwise
    html = (PAGE.replace("__POSTERS__", js(posters)).replace("__VIEWS__", js(views)).replace("__CREDITS__", credits_html(credits, views))
            .replace("__WAYS__", ways).replace("__WIP__", wip).replace("__RING__", ring).replace("__VERSION__", version).replace("__ROOMHASH__", room_hash)
            .replace("__BRAND__", _brand_tags()))
    os.makedirs(root, exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(html)
    copy_file(os.path.join(HERE, ROOM_JS), os.path.join(root, "cabin3d.js"))
    copy_file(os.path.join(HERE, THREE_JS), os.path.join(root, "vendor", "three.module.min.js"))
    n_add, b_add = copy_tree(os.path.join(HERE, ADDONS), os.path.join(root, "vendor", "jsm"))
    n_assets, b_assets = copy_tree(os.path.join(HERE, ASSETS), os.path.join(root, ASSETS), skip=("views.json",))
    weight = (len(html.encode("utf-8")) + os.path.getsize(os.path.join(HERE, ROOM_JS)) + os.path.getsize(os.path.join(HERE, THREE_JS)) + b_add + b_assets) / 1e6
    say(f"Wrote {os.path.relpath(out, HERE)}: the cabin, {len(html.encode('utf-8')) / 1e3:,.0f} KB, with cabin3d.js "
        f"({os.path.getsize(os.path.join(HERE, ROOM_JS)) / 1e3:,.0f} KB), the kit's three.js and {n_add} add-on files, and {n_assets} asset files "
        f"({b_assets / 1e6:,.1f} MB; {len(credits)} credited works, photographs for {len(views)} hours); the whole room weighs {weight:,.1f} MB; doors: "
        + ", ".join(f"{p['name']} -> {p['url']}" for p in doors))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True, help="where to write the page, for example site/dev/index.html")
    ap.add_argument("--draft", action="store_true", help="show the small 'draft for feedback' note the draft site carries")
    a = ap.parse_args()
    write(a.out, draft=a.draft)


if __name__ == "__main__":
    main()
