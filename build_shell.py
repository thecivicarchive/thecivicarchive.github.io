#!/usr/bin/env python3
"""
build_shell.py - the shell every page of The Civic Archive shares (John's Shell Spec v1.3, 2026-10-03).

    python build_shell.py [--root site/dev]

Copies the shell's sources from shell_src/ into <root>/shell/, each file named by a hash of its contents so a browser
never keeps an old copy: the stylesheet, the script, the icon registry, the companion's dock, the companions themselves
(shell_src/companions/<id>.js, listed in shell_src/companions/registry.json) and the type (fonts/: Instrument Sans and
Serif, Lexend, Atkinson Hyperlegible, each with its Open Font License). The companion's dock draws with the site's own
copy of three.js, which sits at <root>/vendor/three.module.min.js; it is copied there too if it is missing.

A page builder then takes its shared pieces from here, so every page carries the same top bar, menus, panels and tab
bar, drawn from one place:

    import build_shell as S
    A = S.build(dev_root)                                # copy the assets; returns their names and the boot script
    S.head(A, root, title, description, version)         # the <head>: settings applied before the first frame
    S.top_bar(root, current, places)                     # skip link, the top bar, its two menus, the phone menu
    S.panels(root, A, faq_html, inline_access=False)     # Help, Reading & access, the live region
    S.tab_bar(root, current, places)                     # the bottom tab bar on phones
    S.icon("bills")                                      # one of the five icons, drawn

`root` is the way from the page to the draft's root ("./" on the front door, "../" one folder down). Nothing here
fetches anything from another server, and the pages it helps write name none of the kit's own files or programs.
"""

import argparse
import hashlib
import html
import json
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "shell_src")
FONTS = ["InstrumentSans-Variable.ttf", "InstrumentSerif-Regular.ttf", "InstrumentSerif-Italic.ttf", "Lexend-Variable.ttf",
         "AtkinsonHyperlegible-Regular.ttf", "AtkinsonHyperlegible-Bold.ttf", "AtkinsonHyperlegible-Italic.ttf", "AtkinsonHyperlegible-BoldItalic.ttf",
         "OFL-InstrumentSans.txt", "OFL-InstrumentSerif.txt", "OFL-Lexend.txt", "OFL-AtkinsonHyperlegible.txt"]
# the seven companions of the Companion Field Guide, in its order; registry.json, when present, is the authority
COMPANIONS = [
    {"id": "penguin", "name": "Adélie penguin", "latin": "Pygoscelis adeliae", "rests": "floor", "default": True},
    {"id": "chickadee", "name": "Black-capped chickadee", "latin": "Poecile atricapillus", "rests": "perch"},
    {"id": "retriever", "name": "Golden retriever", "latin": "Canis familiaris", "rests": "floor"},
    {"id": "cat", "name": "Tabby cat", "latin": "Felis catus", "rests": "floor"},
    {"id": "squirrel", "name": "Eastern gray squirrel", "latin": "Sciurus carolinensis", "rests": "floor"},
    {"id": "chipmunk", "name": "Eastern chipmunk", "latin": "Tamias striatus", "rests": "floor"},
    {"id": "snail", "name": "Garden snail", "latin": "Cornu aspersum", "rests": "floor"},
]
HASHED = re.compile(r"^(shell|icons|dock)\.[0-9a-f]{10}\.(js|css)$")
esc = lambda s: html.escape(str(s), quote=True)


def _h(data):
    return hashlib.sha256(data if isinstance(data, bytes) else data.encode("utf-8")).hexdigest()[:10]


def _write(path, data):
    """Writes bytes or text to path unless it already holds exactly that; True if it wrote."""
    body = data if isinstance(data, bytes) else data.encode("utf-8")
    if os.path.exists(path):
        with open(path, "rb") as fh:
            if fh.read() == body:
                return False
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(body)
    return True


def _read(name):
    with open(os.path.join(SRC, name), encoding="utf-8") as fh:
        return fh.read()


def icons():
    """The five icons, from the one registry the pages' script also reads (the JSON between the two markers)."""
    text = _read("icons.js")
    m = re.search(r"/\*ICONS-BEGIN\*/\s*export const ICONS = (\{.*?\});\s*/\*ICONS-END\*/", text, re.S)
    if not m:
        raise SystemExit("build_shell: the icon registry's markers are missing from shell_src/icons.js")
    return json.loads(m.group(1))


def icon(name, cls=""):
    """One icon, fully drawn, as a page carries it: decorative, hidden from screen readers, never focusable."""
    i = icons()[name]
    return (f'<span class="tca-ico{(" " + cls) if cls else ""}" data-icon="{name}" data-tile="{i["tile"]}">'
            f'<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">{i["svg"]}</svg></span>')


def companions():
    """The seven companions: registry.json's list when it is there, the Field Guide's otherwise; each marked ready
    when its module file exists."""
    reg_path = os.path.join(SRC, "companions", "registry.json")
    out = [dict(c) for c in COMPANIONS]
    if os.path.exists(reg_path):
        try:
            with open(reg_path, encoding="utf-8") as fh:
                reg = json.load(fh)
            reg = reg.get("companions", reg) if isinstance(reg, dict) else reg
            if isinstance(reg, list) and reg:
                out = [{"id": str(c["id"]), "name": str(c.get("name") or c["id"]), "latin": str(c.get("latin") or ""),
                        "rests": "perch" if c.get("rests") == "perch" else "floor", "default": bool(c.get("default"))} for c in reg if c.get("id")]
        except (OSError, ValueError, KeyError, TypeError) as e:
            print(f"build_shell: could not read the companions' registry ({e}); using the Field Guide's list")
    for c in out:
        c["src"] = os.path.join(SRC, "companions", c["id"] + ".js")
        c["ready"] = os.path.exists(c["src"])
    if not any(c.get("default") for c in out) and out:
        out[0]["default"] = True
    return out


def test_page(dev_root, comps, on, say=print, kit_name=None):
    """The companions' side-by-side page (shell_src/companions_test.html), for judging them in a browser. It reads plain,
    unhashed copies of the modules, the kit and the registry. Written only with --test; every other build removes it and
    those copies again, so neither is ever published."""
    page = os.path.join(dev_root, "companions.html")
    comp_dir = os.path.join(dev_root, "shell", "companions")
    plain = [os.path.join(comp_dir, c["id"] + ".js") for c in comps] + [os.path.join(comp_dir, "registry.json"), os.path.join(comp_dir, "kit.js")]
    if on:
        with open(os.path.join(SRC, "companions_test.html"), "rb") as fh:
            _write(page, fh.read())
        for c in comps:
            if c["ready"]:
                with open(c["src"], "rb") as fh:
                    _write(os.path.join(comp_dir, c["id"] + ".js"), fh.read())
        kit_src = os.path.join(SRC, "companions", "kit.js")
        if os.path.exists(kit_src):
            with open(kit_src, "rb") as fh:
                _write(os.path.join(comp_dir, "kit.js"), fh.read())
        with open(os.path.join(SRC, "companions", "registry.json"), "rb") as fh:
            _write(os.path.join(comp_dir, "registry.json"), fh.read())
        say("Shell: the companions' test page is written (companions.html); build again without --test before publishing")
        return
    gone = 0
    for p in [page] + plain:
        if os.path.exists(p):
            os.remove(p)
            gone += 1
    if gone:
        say(f"Shell: removed the companions' test page and its {gone - 1} plain copies")


def _mirror(src_dir, dst_dir):
    """Copies a folder tree as it is (models, textures) and removes files under dst that src no longer has."""
    wrote = removed = 0
    if not os.path.isdir(src_dir):
        return wrote, removed
    want = set()
    for dirpath, _, files in os.walk(src_dir):
        for f in files:
            src = os.path.join(dirpath, f)
            rel = os.path.relpath(src, src_dir)
            want.add(os.path.normcase(rel))
            with open(src, "rb") as fh:
                wrote += _write(os.path.join(dst_dir, rel), fh.read())
    if os.path.isdir(dst_dir):
        for dirpath, _, files in os.walk(dst_dir):
            for f in files:
                rel = os.path.relpath(os.path.join(dirpath, f), dst_dir)
                if os.path.normcase(rel) not in want:
                    os.remove(os.path.join(dirpath, f))
                    removed += 1
    return wrote, removed


def lab_page(dev_root, public, kit_name, on, say=print):
    """The companions' still-frame lab (shell_src/companion_lab.html -> <root>/_companion_lab.html): one frame of any
    clip at any moment, drawn as the dock draws it, as a PNG. Written only with --lab; every other build removes it, and
    the publish scripts leave it out besides, so it is never published."""
    page = os.path.join(dev_root, "_companion_lab.html")
    if on:
        if not kit_name:
            say("Shell: no companions kit (shell_src/companions/kit.js), so no lab page")
            return
        text = (_read("companion_lab.html").replace("__KIT__", kit_name)
                .replace("__COMPANIONS__", json.dumps(public, ensure_ascii=False, separators=(",", ":"))))
        _write(page, text)
        say("Shell: the companions' lab is written (_companion_lab.html); it is not linked and the publish scripts leave it out")
        return
    if os.path.exists(page):
        os.remove(page)
        say("Shell: removed the companions' lab page")


def build(dev_root, say=print, test=False, lab=False):
    """Copies the shell into <dev_root>/shell/ and returns what the pages need: the stylesheet's and the script's
    names (relative to dev_root), the boot script to put inline in each head, and the companions."""
    dev_root = os.path.abspath(dev_root)
    out_dir = os.path.join(dev_root, "shell")
    comp_dir = os.path.join(out_dir, "companions")
    os.makedirs(comp_dir, exist_ok=True)
    keep, keep_comp, wrote = set(), set(), 0
    # the companions first: their hashed names go into the script
    comps = companions()
    for c in comps:
        c["file"] = None
        if c["ready"]:
            with open(c["src"], "rb") as fh:
                body = fh.read()
            c["file"] = f'{c["id"]}.{_h(body)}.js'
            wrote += _write(os.path.join(comp_dir, c["file"]), body)
            keep_comp.add(c["file"])
    public = [{k: c[k] for k in ("id", "name", "latin", "rests", "default", "file")} for c in comps]
    # the realism kit the companions share, hashed like them; the dock imports it by that name
    kit_src, kit_name = os.path.join(SRC, "companions", "kit.js"), None
    if os.path.exists(kit_src):
        with open(kit_src, "rb") as fh:
            kit_body = fh.read()
        kit_name = f"kit.{_h(kit_body)}.js"
        wrote += _write(os.path.join(comp_dir, kit_name), kit_body)
        keep_comp.add(kit_name)
    # downloaded models and the credits that go with them, copied as they are
    credits = os.path.join(SRC, "companions", "credits.json")
    if os.path.exists(credits):
        with open(credits, "rb") as fh:
            wrote += _write(os.path.join(comp_dir, "credits.json"), fh.read())
    w_models, r_models = _mirror(os.path.join(SRC, "companions", "models"), os.path.join(comp_dir, "models"))
    wrote += w_models
    icons_js = _read("icons.js")
    icons_name = f"icons.{_h(icons_js)}.js"
    dock_js = _read("dock.js")
    if kit_name:
        dock_js = dock_js.replace('"./companions/kit.js"', f'"./companions/{kit_name}"')
        if '"./companions/kit.js"' in dock_js:
            raise SystemExit("build_shell: the kit's name was not written into the dock; check shell_src/dock.js")
    dock_name = f"dock.{_h(dock_js)}.js"
    shell_js = (_read("shell.js").replace('from "./icons.js"', f'from "./{icons_name}"').replace('import("./dock.js")', f'import("./{dock_name}")')
                .replace("__COMPANIONS__", json.dumps(public, ensure_ascii=False, separators=(",", ":"))))
    for token in ('"./icons.js"', '"./dock.js"', "__COMPANIONS__"):
        if token in shell_js:
            raise SystemExit(f"build_shell: {token} was not replaced in the script; check shell_src/shell.js")
    shell_name = f"shell.{_h(shell_js)}.js"
    css = _read("shell.css")
    css_name = f"shell.{_h(css)}.css"
    for name, body in ((icons_name, icons_js), (dock_name, dock_js), (shell_name, shell_js), (css_name, css)):
        wrote += _write(os.path.join(out_dir, name), body)
        keep.add(name)
    # the type, with its licences, served from the site itself
    missing = []
    for f in FONTS:
        src = os.path.join(HERE, "fonts", f)
        if os.path.exists(src):
            with open(src, "rb") as fh:
                wrote += _write(os.path.join(out_dir, "fonts", f), fh.read())
        else:
            missing.append(f)
    # three.js for the dock: the kit's own copy (MIT), where the front door already keeps it, and its add-ons (the glTF
    # loader and the room environment the companions' kit uses)
    three_src, three_dst = os.path.join(HERE, "vendor", "three.module.min.js"), os.path.join(dev_root, "vendor", "three.module.min.js")
    if os.path.exists(three_src):
        with open(three_src, "rb") as fh:
            wrote += _write(three_dst, fh.read())
    jsm_src = os.path.join(HERE, "vendor", "jsm")
    if os.path.isdir(jsm_src):
        for dirpath, _, files in os.walk(jsm_src):
            for f in files:
                src = os.path.join(dirpath, f)
                with open(src, "rb") as fh:
                    wrote += _write(os.path.join(dev_root, "vendor", "jsm", os.path.relpath(src, jsm_src)), fh.read())
    # old copies go, so the folder holds only what the pages name
    removed = r_models
    for name in os.listdir(out_dir):
        if HASHED.match(name) and name not in keep:
            os.remove(os.path.join(out_dir, name))
            removed += 1
    for name in os.listdir(comp_dir):
        if re.match(r"^[\w-]+\.[0-9a-f]{10}\.js$", name) and name not in keep_comp:
            os.remove(os.path.join(comp_dir, name))
            removed += 1
    test_page(dev_root, comps, test, say, kit_name)
    lab_page(dev_root, public, kit_name, lab, say)
    perch = [c["id"] for c in public if c["rests"] == "perch"]
    boot = re.sub(r"/\*.*?\*/", "", _read("boot.js").replace("__PERCH__", json.dumps(perch)), flags=re.S)      # its comments stay in the source
    boot = "\n".join(line.rstrip() for line in boot.splitlines() if line.strip())
    ready = [c["name"] for c in public if c["file"]]
    say(f"Shell: {shell_name}, {css_name}, {icons_name}, {dock_name}, {kit_name or 'no kit'}; {len(ready)} of {len(public)} companions ready"
        + (f" ({', '.join(ready)})" if ready else "") + f"; {len(FONTS) - len(missing)} type files" + (f" (missing: {', '.join(missing)})" if missing else "")
        + f"; {wrote} file(s) written, {removed} old copies removed")
    return {"css": f"shell/{css_name}", "js": f"shell/{shell_name}", "boot": boot, "companions": public, "kit": kit_name}


# ============================== the shared pieces of every page ==============================

MARK = ('<svg viewBox="0 0 28 28" aria-hidden="true" focusable="false"><path class="b" d="M14 3v2.5"/><path class="b" d="M6.5 13.5a7.5 7.5 0 0 1 15 0"/>'
        '<path d="M4 13.5h20"/><path d="M6.5 16.5v6M11.5 16.5v6M16.5 16.5v6M21.5 16.5v6"/><path d="M3 24h22"/></svg>')
CHEV = '<svg class="chev" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M6 9l6 6 6-6"/></svg>'
X = '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M6 6l12 12M18 6L6 18"/></svg>'
BUBBLE = ('<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M4 5.5h16v10.5H10l-4.5 3.5V16H4z"/>'
          '<path d="M9.2 9.4a2.8 2.8 0 0 1 5.5.6c0 1.6-2.2 1.9-2.2 3.2"/><path d="M12.5 15.6v.01"/></svg>')
SLIDERS = ('<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M4 7h9M17 7h3M4 17h3M11 17h9"/>'
           '<path d="M15 4.6a2.4 2.4 0 1 1 0 4.8a2.4 2.4 0 1 1 0-4.8zM9 14.6a2.4 2.4 0 1 1 0 4.8a2.4 2.4 0 1 1 0-4.8z"/></svg>')


def head(A, root, title, desc, version, extra=""):
    """Everything inside <head>: the settings are on <html> before the first frame; the stylesheet and the script come
    from the site itself."""
    return (f'<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
            f'<title>{esc(title)}</title>\n<meta name="description" content="{esc(desc)}">\n<meta name="version" content="{esc(version)}">\n'
            f'<meta name="color-scheme" content="light dark">\n<link rel="icon" href="{root}us/icon-192.png">\n'
            f'<script>{A["boot"]}</script>\n<link rel="stylesheet" href="{root}{A["css"]}">\n'
            f'<script type="module" src="{root}{A["js"]}"></script>\n{extra}')


def site_places(dev_root):
    """What the draft holds, seen from its folders: the federal side, the ballot, every state page, county pages."""
    sys.path.insert(0, HERE)
    try:
        from states.places import PLACES
    except Exception:      # the shell still builds without the state list
        PLACES = {}
    dev_root = os.path.abspath(dev_root)
    exists = lambda *p: os.path.exists(os.path.join(dev_root, *p))
    states = sorted(((P.get("name") or code.upper(), code) for code, P in PLACES.items() if exists(code, "index.html")), key=lambda t: t[0])
    counties = [(PLACES[c]["name"], f"{c}/counties/") for c in sorted(PLACES) if exists(c, "counties", "index.html")]
    return {"us": exists("us", "index.html"), "ballot": exists("ballot", "index.html"), "ballot_us": exists("ballot", "us", "index.html"),
            "ballot_states": exists("ballot", "states", "index.html"), "states": states, "counties": counties,
            "rooms": exists("rooms.html"), "cabin": exists("cabin.html")}


def _cur(current, key):
    return ' aria-current="page"' if current == key else ""


def state_picker(root, places, pid):
    """Pick a state, then Go: a select never moves the page by itself."""
    if not places["states"]:
        return ""
    opts = "".join(f'<option value="{root}{code}/">{esc(name)}</option>' for name, code in places["states"])
    return (f'<form class="tca-pick" action="#"><label for="{pid}">Your state<select id="{pid}"><option value="">Choose a state</option>{opts}</select></label>'
            f'<button type="submit">Go</button></form>')


SKIP = '<a class="tca-skip" href="#main">Skip to content</a>'


def top_bar(root, current=None, places=None, skip=True):
    """The skip link, the top bar (wordmark, the five sections, Help, Reading & access, Motion, the phone menu's
    button), the two mega-menus and the phone menu. `current` names the section the page belongs to ("method",
    "access"); the front door has none, its wordmark is home. A page that puts anything before the top bar (a draft
    note) writes SKIP first itself and passes skip=False, so the skip link is always the first thing the keyboard reaches."""
    P = places or {"states": [], "counties": [], "rooms": True, "cabin": True, "ballot_states": True}
    bills = f"""<div class="tca-mega" id="tca-mega-bills" hidden>
<div class="tca-wrap">
<div><a class="lead-link" href="{root}us/">{icon("bills")}<span><b>Plain Congress</b><br><small>Every bill and recorded vote of the 119th Congress</small></span></a>
<h2>Browse</h2><ul>
<li><a href="{root}us/#bills">Every bill<small>Newest action first. Filter by status or topic there</small></a></li>
<li><a href="{root}us/#nowmoving">Moving now, and already law<small>Ten bills worth knowing about</small></a></li>
<li><a href="{root}us/#yours">How did your members vote?<small>Pick your state</small></a></li></ul></div>
<div><h2>Tools</h2><ul>
<li><a href="{root}us/#map">Who voted how, state by state<small>The vote map</small></a></li>
<li><a href="{root}us/#shapes">The shape of every district<small>Measured, never judged</small></a></li>
<li><a href="{root}us/#people">Who lives in each district<small>The Census Bureau's counts</small></a></li>
<li><a href="{root}us/#money">Follow the money<small>Organizations behind each campaign</small></a></li></ul></div>
<div><h2>How it works</h2><ul>
<li><a href="{root}us/#how">How the ratings work<small>Evidence grades and reasons</small></a></li>
<li><a href="{root}method/">Method<small>Sources, the rubric, and what the site refuses to do</small></a></li></ul>
<p class="note">There is no corrections log yet.</p></div>
</div></div>"""
    counties = "".join(f'<li><a href="{root}{url}">{esc(name)}&rsquo;s counties<small>Who holds each county office</small></a></li>' for name, url in P["counties"])
    officials = f"""<div class="tca-mega" id="tca-mega-officials" hidden>
<div class="tca-wrap">
<div><a class="lead-link" href="{root}us/#members">{icon("officials")}<span><b>Your members of Congress</b><br><small>Service, votes, and who funds them</small></span></a>
<h2>In Congress</h2><ul>
<li><a href="{root}us/#members">Find a senator or representative<small>With their party, and against it</small></a></li>
<li><a href="{root}us/#money">Who funds them<small>Organizations only; people as totals</small></a></li></ul></div>
<div><h2>In the states</h2>{state_picker(root, P, "tca-pick-mega")}<ul>
<li><a href="{root}rooms.html#states">Choose a state on the map<small>Every state legislature, its districts and members</small></a></li></ul></div>
<div><h2>Closer to home</h2><ul>{counties}
{f'<li><a href="{root}ballot/states/#local">County and local races<small>On the November 3 ballot</small></a></li>' if P.get("ballot_states") else ""}</ul></div>
</div></div>"""
    rows = [("bills", f"{root}us/", "Bills", "Plain Congress: every bill and vote"),
            ("ballot", f"{root}ballot/", "Ballot", "Who is on your November ballot"),
            ("officials", f"{root}#officials" if root != "./" else "#officials", "Officials", "Congress and your statehouse"),
            ("method", f"{root}method/", "Method", "How each page is made"),
            ("access", f"{root}access/", "Access", "Reading and access, and what is not done yet")]
    sheet_rows = "".join(f'<li><a href="{href}"{_cur(current, key)}>{icon(key)}<span><b>{label}</b><span class="d">{d}</span></span></a></li>'
                         for key, href, label, d in rows)
    tail = "".join(x for x in (
        f'<li><a href="{root}rooms.html">All levels: the ring of cards</a></li>' if P.get("rooms", True) else "",
        f'<li><a href="{root}cabin.html">Take a break: the cabin</a></li>' if P.get("cabin", True) else "",
        f'<li><a href="{root}method/#sources">Sources</a></li>'))
    return f"""{SKIP if skip else ""}
<header class="tca-top">
<div class="tca-bar">
<a class="tca-brand" href="{root}" aria-label="The Civic Archive, home">{MARK}<span class="wm">The Civic Archive</span></a>
<nav class="tca-nav" aria-label="Main">
<ul>
<li><button type="button" aria-expanded="false" aria-controls="tca-mega-bills"{_cur(current, "bills")}>Bills{CHEV}</button>{bills}</li>
<li><a href="{root}ballot/"{_cur(current, "ballot")}>Ballot</a></li>
<li><button type="button" aria-expanded="false" aria-controls="tca-mega-officials"{_cur(current, "officials")}>Officials{CHEV}</button>{officials}</li>
<li><a href="{root}method/"{_cur(current, "method")}>Method</a></li>
<li><a href="{root}access/"{_cur(current, "access")}>Access</a></li>
</ul>
</nav>
<div class="tca-tools">
<button class="tca-tb help" type="button" data-tca-open aria-controls="tca-help" aria-expanded="false">{BUBBLE}<span class="lab-help">Help</span></button>
<button class="tca-tb access" type="button" data-tca-open aria-controls="tca-access" aria-expanded="false">{SLIDERS}<span class="lab-access">Reading &amp; access</span></button>
<button class="tca-tb motion" id="tca-motion" type="button" aria-pressed="true"><span class="tca-switch" aria-hidden="true"></span><span class="lab-motion">Motion</span></button>
<button class="tca-tb tca-burger" id="tca-burger" type="button" aria-expanded="false" aria-controls="tca-sheet" aria-label="Menu"><span class="bl" aria-hidden="true"></span></button>
</div>
</div>
</header>
<nav class="tca-sheet" id="tca-sheet" aria-label="Menu" hidden>
<ul class="tca-rows">{sheet_rows}</ul>
<div class="tca-tail"><h2>More</h2><ul>{tail}</ul></div>
</nav>
<div class="tca-progress" aria-hidden="true"></div>"""


def tab_bar(root, current=None):
    """The bottom tab bar on phones: the same five, in the thumb's reach. Only the section a page is in is marked."""
    tabs = [("bills", f"{root}us/", "Bills"), ("ballot", f"{root}ballot/", "Ballot"),
            ("officials", "#officials" if root == "./" else f"{root}#officials", "Officials"),
            ("method", f"{root}method/", "Method"), ("access", f"{root}access/", "Access")]
    items = "".join(f'<li><a href="{href}"{_cur(current, key)}>{icon(key)}<span>{label}</span></a></li>' for key, href, label in tabs)
    return f'<nav class="tca-tabs" aria-label="Sections"><ul>{items}</ul></nav>'


AXIS_UI = [      # the order the settings are listed in, the words for each, and a line of help where one is needed
    ("scale", "Text size", [("100", "100%"), ("115", "115%"), ("130", "130%"), ("150", "150%"), ("200", "200%")], ""),
    ("face", "Typeface", [("standard", "Standard"), ("dyslexia", "Lexend"), ("hyperlegible", "Atkinson Hyperlegible")],
     "Lexend and Atkinson Hyperlegible were each designed to be easier to read."),
    ("space", "Spacing", [("standard", "Standard"), ("generous", "Generous")], ""),
    ("contrast", "Contrast", [("standard", "Standard"), ("high", "High"), ("dark", "Dark")], ""),
    ("lang", "Words", [("standard", "Standard"), ("plain", "Plain")], "Plain words where a plain version is written."),
    ("depth", "Detail", [("standard", "Standard"), ("detailed", "More structure"), ("focus", "Focus")],
     "More structure adds section labels, reading times and a progress line. Focus puts the extras away."),
    ("motion", "Motion", [("full", "On"), ("reduced", "Reduced")], ""),
    ("reveal", "Scroll fade", [("full", "Full"), ("subtle", "Subtle"), ("off", "Off")], "How text fades in and out at the edges of the screen."),
    ("calm", "Calm", [("off", "Off"), ("on", "On")], "No countdowns and no motion. Chart bars get patterns."),
    ("palette", "Chart colours", [("standard", "Standard"), ("deut", "Red-green (deuteranopia)"), ("prot", "Red-green (protanopia)"),
                                  ("trit", "Blue-yellow (tritanopia)"), ("mono", "Grey only")], "Changes the colours of charts only, and adds patterns."),
    ("companion", "Companion", [("on", "On"), ("still", "Still"), ("off", "Off")], "Still draws it once. Off never loads it."),
]
PRESET_UI = [
    ("adhd", "ADHD", "Section labels, reading times and a progress line. Less motion."),
    ("focus", "Focus", "One column, the extras put away, no companion."),
    ("dyslexia", "Dyslexia", "Lexend type, more space, plain words, larger text."),
    ("lowvision", "Low vision", "Atkinson Hyperlegible at 150%, high contrast, more space."),
    ("colour", "Colour vision", "Chart colours for red-green colour blindness, with patterns."),
    ("screenreader", "Screen reader and keyboard", "No motion, more space, no companion."),
    ("plain", "Plain language", "Plain words where a plain version is written."),
    ("calm", "Calm", "No motion, no countdowns, grey charts."),
]


def seg(axis, legend, opts, hint, name=None):
    """One setting as a group of real radio buttons."""
    name = name or f"tca-ax-{axis}"
    radios = "".join(f'<label><input type="radio" name="{name}" value="{v}"{" checked" if i == 0 else ""}><span>{esc(t)}</span></label>' for i, (v, t) in enumerate(opts))
    return (f'<fieldset class="tca-seg" data-axis="{axis}"><legend>{esc(legend)}</legend><div class="opts">{radios}</div>'
            + (f'<span class="hint">{esc(hint)}</span>' if hint else "") + "</fieldset>")


def access_panel(inline=False):
    presets = "".join(f'<li><button type="button" data-preset="{pid}" aria-pressed="false"><b>{esc(name)}</b><span>{esc(say)}</span></button></li>'
                      for pid, name, say in PRESET_UI)
    segs = "".join(seg(*a) for a in AXIS_UI)
    attrs = 'class="tca-panel wide inline" id="tca-access" aria-labelledby="tca-access-h"' if inline else \
        'class="tca-panel wide" id="tca-access" role="dialog" aria-modal="false" aria-labelledby="tca-access-h" hidden'
    close = "" if inline else f'<button class="x" type="button" aria-label="Close reading and access">{X}</button>'
    return f"""<section {attrs}>
{close}<h2 id="tca-access-h" tabindex="-1">Reading &amp; access</h2>
<p>Kept on this device only. Nothing is sent anywhere. Turn on as many as help: they combine. Where two differ, the larger text, the more space, the less motion and the quieter companion win. Otherwise the one you chose last wins.</p>
<h3>Presets</h3>
<ul class="tca-presets">{presets}</ul>
<h3>Each setting</h3>
{segs}
<div class="tca-row"><button class="tca-btn" type="button" data-tca-reset>Put everything back</button></div>
</section>"""


def help_panel(root, A, faq_html):
    quick = [("bills", f"{root}us/#bills", "Find a bill"), ("ballot", f"{root}ballot/", "See who is on your ballot"),
             ("officials", "#officials" if root == "./" else f"{root}#officials", "Find who represents you"),
             ("method", f"{root}method/", "See how pages are made")]
    items = "".join(f'<li><a href="{href}">{icon(name)}<span>{esc(label)}</span></a></li>' for name, href, label in quick)
    items += f'<li><button type="button" data-tca-open aria-controls="tca-access" aria-expanded="false">{icon("access")}<span>Change reading and access</span></button></li>'
    pick = "".join(f'<li><button type="button" data-skin="{esc(c["id"])}" aria-pressed="false"{"" if c.get("file") else " disabled"}><b>{esc(c["name"])}</b>'
                   f'<i>{esc(c["latin"])}{"" if c.get("file") else " &middot; not ready yet"}</i></button></li>' for c in A["companions"])
    return f"""<section class="tca-panel" id="tca-help" role="dialog" aria-modal="false" aria-labelledby="tca-help-h" hidden>
<button class="x" type="button" aria-label="Close help">{X}</button>
<h2 id="tca-help-h" tabindex="-1">Help</h2>
<p>Five ways in, three plain answers, and your companion.</p>
<h3>Quick actions</h3>
<ul class="tca-quick">{items}</ul>
<h3>Plain answers</h3>
<div class="tca-faq">{faq_html}</div>
<h3>Your companion</h3>
<p>It is here only to open this panel. It never speaks on its own, and screen readers pass over it. Help stays in the top bar either way.</p>
{seg("companion", "Companion", [("on", "On"), ("still", "Still"), ("off", "Off")], "Still draws it once. Off never loads it.", name="tca-ax-companion-help")}
<ul class="tca-pickers" aria-label="Choose a companion">{pick}</ul>
</section>"""


def panels(root, A, faq_html, inline_access=False):
    """Help, Reading & access (unless the page carries it inline) and the live region that says each change aloud."""
    return (help_panel(root, A, faq_html) + "\n" + ("" if inline_access else access_panel()) +
            '\n<div id="tca-live" class="tca-sr" role="status" aria-live="polite"></div>')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=os.path.join(HERE, "site", "dev"), help="the draft's root folder (default site/dev)")
    ap.add_argument("--test", action="store_true", help="also write the companions' side-by-side test page (never publish it)")
    ap.add_argument("--lab", action="store_true", help="also write the companions' still-frame lab, _companion_lab.html (never publish it)")
    a = ap.parse_args()
    build(a.root, test=a.test, lab=a.lab)


if __name__ == "__main__":
    main()
