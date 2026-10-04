#!/usr/bin/env python3
"""
build_local_dev.py
==================
The local level's draft pages, one state at a time, counties first: site/dev/<code>/counties/index.html, a single
page with the county map, a card for every county, and a page for each county's offices, opened by hash
(#c=<county fips>). It reads local_<code>_counties.json (the Census lines) and local_<code>.sqlite (who holds each
county office, from the Secretary of State's official results, when loaded), borrows the styles and the top bar from
the federal draft the way the state builder does, and says plainly what is not loaded yet.

What the page never does: guess a party (Minnesota's county offices are nonpartisan on the ballot, and the page says
so), fill in an officeholder from memory (only the winners in the Secretary's results appear), or describe anyone.

    python build_local_dev.py --place mn
"""

import argparse
import datetime as dt
import json
import os
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from build_site_dev import html_attr, read_changelog, state_paths      # noqa: E402
from build_state_dev import borrow, decode_rings                        # noqa: E402
from states.places import place                                         # noqa: E402

OFFICE_ORDER = ["county commissioner", "county sheriff", "sheriff", "county attorney", "county auditor", "county treasurer", "county recorder", "county surveyor", "county coroner"]


def collect(P, code):
    lines = json.load(open(os.path.join(HERE, f"local_{code}_counties.json"), encoding="utf-8"))
    q = lines.get("q", 400)
    counties = {}
    for fips, rings in lines["counties"].items():
        info = lines["info"].get(fips, {})
        dec = decode_rings(rings, q)
        xs = [x for r in dec for x, _ in r]
        ys = [y for r in dec for _, y in r]
        counties[fips] = {"fips": fips, "name": info.get("name", fips), "full": info.get("full", ""), "land": info.get("land", 0), "rings": rings,
                          "bbox": [min(xs), min(ys), max(xs), max(ys)] if xs else [0, 0, 0, 0]}
    officials, elections = {}, []
    db = os.path.join(HERE, f"local_{code}.sqlite")
    if os.path.exists(db):
        con = sqlite3.connect(db)
        has = lambda t: con.execute("SELECT 1 FROM sqlite_master WHERE name = ?", (t,)).fetchone() is not None
        if has("elections"):
            elections = [dict(zip(("date", "name", "files", "sha256"), r)) for r in con.execute("SELECT date, name, files, sha256 FROM elections ORDER BY date")]
        if has("officials"):
            for county, office, district, name, elected, years, start, end, votes, contest in con.execute(
                    "SELECT county_id, office, district, name, elected, term_years, term_start, term_end, votes, contest FROM officials ORDER BY county_id, office, district, elected"):
                total = con.execute("SELECT total_votes FROM contests WHERE id = ?", (contest,)).fetchone()
                officials.setdefault(str(county).zfill(3), []).append({"office": office, "d": district or "", "n": name, "elected": elected, "years": years, "start": start, "end": end,
                                                                        "votes": votes, "total": total[0] if total else None})
    for fips, c in counties.items():
        offs = officials.get(fips, [])
        offs.sort(key=lambda o: (next((i for i, k in enumerate(OFFICE_ORDER) if o["office"].lower().startswith(k)), 99), int(o["d"]) if str(o["d"]).isdigit() else 0, o["d"]))
        c["officials"] = offs
    outline = state_paths(os.path.join(HERE, "us_states_albers.json")).get(P["code"]) or {"d": "", "bbox": [0, 0, 975, 610]}
    return {"q": q, "counties": counties, "outline": {"d": outline["d"], "bbox": outline["bbox"]}, "vintage": lines.get("vintage", ""), "source": lines.get("source", {}),
            "elections": elections, "generated": dt.datetime.now().strftime("%B %d, %Y")}


PAGE = r"""<!DOCTYPE html>
<html lang="en" data-level="local">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>__NAME__ counties: The Civic Archive</title>
<meta name="description" content="Every county in __NAME__: its board, sheriff and county attorney as the official election results record them, on one map.">
<meta name="version" content="__VERSION__">
<script>try{document.documentElement.dataset.theme=localStorage.getItem("theme")||"light"}catch(e){document.documentElement.dataset.theme="light"}</script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Instrument+Sans:ital,wght@0,400..700;1,400..700&family=Instrument+Serif:ital@0;1&display=swap" rel="stylesheet">
<style>__CSS__</style>
<style>
.cgrid{display:grid;gap:12px;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));margin-top:18px}
.ccard{display:block;text-align:left;background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 16px;color:inherit;text-decoration:none;cursor:pointer;transition:transform .2s,border-color .2s}
.ccard:hover{transform:translateY(-2px);border-color:var(--accent)}
.ccard h3{margin:0 0 4px;font-size:17px}.ccard p{margin:0;color:var(--muted);font-size:13.5px}
.cmap{width:100%;height:auto;aspect-ratio:975/610;display:block}
.cmap .cc{fill:var(--card);stroke:var(--line);stroke-width:.35px;cursor:pointer;transition:fill .15s}
.cmap .cc:hover,.cmap .cc.hot{fill:var(--accent-soft, #2d5f8a)}
.cmap .cc.sel{fill:var(--accent);stroke:#fff}
.cmap .cout{fill:none;stroke:var(--fg);stroke-width:.6px;pointer-events:none}
.cmap .cl{font:12px 'Instrument Sans',system-ui,sans-serif;fill:var(--fg);pointer-events:none;text-anchor:middle}
.offices{display:grid;gap:10px;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));margin:16px 0}
.office{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 14px}
.office .t{font-size:13px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}.office .n{font-size:18px;font-weight:600;margin:2px 0}.office .s{font-size:13px;color:var(--muted)}
.notyet{border:1px dashed var(--line);border-radius:12px;padding:14px 16px;color:var(--muted)}
.crumbs a{color:var(--muted)}
</style>
</head>
<body>
<div style="background:#7c2d12;color:#fff;padding:.5rem 1rem;font:600 13px/1.4 system-ui,sans-serif;text-align:center;letter-spacing:.02em">
  WORK IN PROGRESS &mdash; this is a draft for feedback, not the real site.
  <a href="https://thecivicarchive.github.io/" style="color:#fed7aa;text-decoration:underline">Go to the live site</a>
</div>
<header class="top">
  <div class="wrap">
    <a class="doorlink" href="../../rooms.html" title="Every level of government: the ring of cards" aria-label="All levels of government, the ring of cards"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 21V5l10-2v18"/><path d="M14 6h6v15"/><path d="M2 21h20"/><path d="M10.5 12.5v.01"/></svg><span>All levels</span></a>
    <a class="brand" href="#top" aria-label="The Civic Archive, __NAME__ counties, home"><svg class="mark" viewBox="0 0 28 28" aria-hidden="true"><path d="M14 3v2.5"/><path d="M6.5 13.5a7.5 7.5 0 0 1 15 0"/><path d="M4 13.5h20"/><path d="M6.5 16.5v6M11.5 16.5v6M16.5 16.5v6M21.5 16.5v6"/><path d="M3 24h22"/></svg><span class="word">The Civic Archive</span><span class="sub">__NAME__ counties</span></a>
    <nav class="nav" aria-label="Sections">
      <a href="#top">Counties</a><a href="#map">County map</a><a href="../">__NAME__'s legislature</a><a href="#sources">Sources</a>
    </nav>
    <div class="tools">
      <button class="iconbtn" id="theme" aria-label="Switch between light and dark" title="Light / dark">
        <svg class="moon" viewBox="0 0 24 24" aria-hidden="true"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>
        <svg class="sun" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>
      </button>
    </div>
  </div>
</header>

<main>
<div id="pg-home">
<section class="hero" id="top">
  <div class="wrap">
    <aside class="kpirail" aria-label="Where __NAME__'s counties stand">
      <div class="kpihead"><span class="tag fact">Fact</span><span>__NAME__'s counties<br>the local level, opening</span></div>
      <dl class="kpis">__KPIS__</dl>
      <p class="kpinote">Counted from public records. Updated __GENERATED__.</p>
    </aside>
    <div class="herotext">
      <h1 class="h1"><span class="line">__NAME__'s counties,</span> <span class="line">closer to home.</span></h1>
      <p class="lede">A county board sets the levy, runs the roads, the jail, the courthouse and the human services office. Every county office in __NAME__ is elected on a nonpartisan ballot. This page shows who holds each one, as the Secretary of State's official election results record it, and nothing that is not in that record.</p>
      <div class="cta"><a class="btn primary" href="#map">See the county map</a><a class="btn" href="#list">Browse all __N__ counties</a></div>
    </div>
  </div>
</section>

<section class="theater block" id="map">
  <div class="wrap">
    <div class="sechead"><div><h2>Every county on one map</h2><p>Tap a county for its offices. __OFFICIALS_NOTE__</p></div></div>
    <div class="theater-grid">
      <div class="stage"><div class="mapframe"><svg class="cmap" id="cmap" role="img" aria-label="Map of __NAME__'s counties"></svg></div></div>
      <aside class="mapside" id="mapside" aria-live="polite"><span class="muted">Tap a county to see its offices.</span></aside>
    </div>
    <p class="note">County lines: __VINTAGE__.</p>
  </div>
</section>

<section class="block" id="list">
  <div class="wrap">
    <div class="sechead"><div><h2>All __N__ counties</h2><p>Alphabetical. Each opens the county's own page.</p></div></div>
    <div class="cgrid" id="cgrid"></div>
  </div>
</section>

<section class="block" id="sources">
  <div class="wrap">
    <div class="sechead"><div><h2>Sources</h2><p>Where every figure on these pages comes from.</p></div></div>
    <div class="labelgrid">
      <div class="labelcard"><span class="tag fact">Fact</span><h3>County lines</h3><p>The <a href="https://www.census.gov/geographies/mapping-files/time-series/geo/cartographic-boundary.html" target="_blank" rel="noopener">Census Bureau's cartographic boundary file</a> for counties (__VINTAGE__), file <code>__SRC_FILE__</code>, SHA-256 <code>__SRC_SHA__</code>.</p></div>
      <div class="labelcard"><span class="tag fact">Fact</span><h3>Who holds each office</h3><p>The <a href="https://www.sos.mn.gov/elections-voting/election-results/" target="_blank" rel="noopener">Minnesota Secretary of State's official election results</a>: the winner of each county office on the general-election ballot, with the votes. __ELECTIONS__ A resignation or an appointment since an election is not in this record; the county's own site is the authority for who holds an office today.</p></div>
      <div class="labelcard"><span class="tag fact">Fact</span><h3>Party</h3><p>Every county office in __NAME__ is nonpartisan on the ballot, so no party is shown, and none is guessed.</p></div>
    </div>
  </div>
</section>
</div>

<div id="pg-county" hidden><section class="block"><div class="wrap" id="countybox"></div></section></div>
</main>

<footer class="foot"><div class="wrap"><p>The Civic Archive, __NAME__ counties, draft __VERSIONTEXT__. Built from public records; nothing here is a take.</p></div></footer>
<script>
const DATA = __DATA__;
const $ = (s, r) => (r || document).querySelector(s), $$ = (s, r) => Array.from((r || document).querySelectorAll(s));
const esc = s => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
const store = {get: k => { try { return localStorage.getItem(k); } catch (e) { return null; } }, set: (k, v) => { try { localStorage.setItem(k, v); } catch (e) {} }};
$("#theme").addEventListener("click", () => { const t = document.documentElement.dataset.theme === "dark" ? "light" : "dark"; document.documentElement.dataset.theme = t; store.set("theme", t); });
function decodeRing(r, q){ let x = 0, y = 0; const out = []; for (let i = 0; i < r.length - 1; i += 2) { x += r[i]; y += r[i + 1]; out.push([x / q, y / q]); } return out; }
const ringsPath = rings => rings.map(r => "M" + r.map(p => p[0].toFixed(2) + " " + p[1].toFixed(2)).join("L") + "Z").join("");
const C = DATA.counties, LIST = Object.values(C).sort((a, b) => a.name.localeCompare(b.name));
for (const c of LIST) { const rings = c.rings.map(r => decodeRing(r, DATA.q)); c.d = ringsPath(rings); let best = null, bestA = 0;
  for (const r of rings) { let a = 0, cx = 0, cy = 0; for (let i = 0, j = r.length - 1; i < r.length; j = i++) { const f = r[j][0] * r[i][1] - r[i][0] * r[j][1]; a += f; cx += (r[j][0] + r[i][0]) * f; cy += (r[j][1] + r[i][1]) * f; }
    if (Math.abs(a) > bestA) { bestA = Math.abs(a); best = a ? [cx / (3 * a), cy / (3 * a)] : r[0]; } }
  c.at = best || [(c.bbox[0] + c.bbox[2]) / 2, (c.bbox[1] + c.bbox[3]) / 2]; c.room = Math.sqrt(bestA / 2); }
/* the map: the state's outline and its counties, in the same Albers space as every map on the site */
const svg = $("#cmap"), [bx0, by0, bx1, by1] = DATA.outline.bbox, pad = Math.max(bx1 - bx0, by1 - by0) * .04;
svg.setAttribute("viewBox", `${(bx0 - pad).toFixed(3)} ${(by0 - pad).toFixed(3)} ${(bx1 - bx0 + 2 * pad).toFixed(3)} ${(by1 - by0 + 2 * pad).toFixed(3)}`);
const px = (bx1 - bx0 + 2 * pad) / 700;
svg.innerHTML = LIST.map(c => `<path class="cc" d="${c.d}" data-c="${c.fips}" tabindex="0" role="button" aria-label="${esc(c.name)} County"><title>${esc(c.name)} County</title></path>`).join("")
  + `<path class="cout" d="${DATA.outline.d}"></path>`
  + LIST.map(c => c.room / px > 26 ? `<text class="cl" transform="translate(${c.at[0].toFixed(3)} ${c.at[1].toFixed(3)}) scale(${(px * 0.9).toFixed(5)})">${esc(c.name)}</text>` : "").join("");
function offices(c){
  if (!c.officials.length) return `<div class="notyet">Who holds ${esc(c.name)} County's offices is not loaded yet. It will come from the Secretary of State's official election results, nothing else.</div>`;
  return `<div class="offices">${c.officials.map(o => `<div class="office"><div class="t">${esc(o.office)}${o.d ? ", District " + esc(o.d) : ""}</div><div class="n">${esc(o.n)}</div><div class="s">Elected ${esc(o.elected)}${o.votes ? ", " + Number(o.votes).toLocaleString() + " votes" + (o.total ? " of " + Number(o.total).toLocaleString() : "") : ""}; term to ${esc((o.end || "").slice(0, 4))}. Nonpartisan office.</div></div>`).join("")}</div>`;
}
function side(c){ $("#mapside").innerHTML = `<div class="side-head"><h3>${esc(c.name)} County</h3></div><p class="muted">${(c.land / 2589988.11).toFixed(0).replace(/\B(?=(\d{3})+(?!\d))/g, ",")} square miles of land. ${c.officials.length ? c.officials.length + " county offices on file." : "County offices not loaded yet."}</p><p><a class="btn" href="#c=${c.fips}">Open ${esc(c.name)} County</a></p>`; $$("#cmap .cc").forEach(p => p.classList.toggle("sel", p.dataset.c === c.fips)); }
svg.addEventListener("click", e => { const p = e.target.closest(".cc"); if (p) side(C[p.dataset.c]); });
svg.addEventListener("keydown", e => { if ((e.key === "Enter" || e.key === " ") && e.target.classList.contains("cc")) { e.preventDefault(); location.hash = "#c=" + e.target.dataset.c; } });
$("#cgrid").innerHTML = LIST.map(c => `<a class="ccard" href="#c=${c.fips}"><h3>${esc(c.name)} County</h3><p>${c.officials.length ? c.officials.length + " county offices on file" : "offices not loaded yet"}</p></a>`).join("");
function county(fips){
  const c = C[fips]; if (!c) return route("");
  $("#pg-home").hidden = true; $("#pg-county").hidden = false; scrollTo(0, 0);
  $("#countybox").innerHTML = `<p class="crumbs"><a href="#top">← All ${LIST.length} counties</a></p><div class="sechead"><div><h1 class="h1" style="font-size:34px">${esc(c.name)} County</h1><p>${esc(DATA.name)}. ${(c.land / 2589988.11).toFixed(0).replace(/\B(?=(\d{3})+(?!\d))/g, ",")} square miles of land. Every office below is nonpartisan on the ballot.</p></div></div>
    <h2>Who holds each county office</h2>${offices(c)}
    <p class="note">From the Minnesota Secretary of State's official election results${DATA.elections.length ? " (" + DATA.elections.map(e => e.date).join(", ") + ")" : ""}. A resignation or an appointment since an election is not in this record; the county's own site is the authority for who holds an office today.</p>
    <svg class="cmap" style="max-width:420px;margin-top:18px" viewBox="${(c.bbox[0] - (c.bbox[2] - c.bbox[0]) * .3).toFixed(3)} ${(c.bbox[1] - (c.bbox[3] - c.bbox[1]) * .3).toFixed(3)} ${((c.bbox[2] - c.bbox[0]) * 1.6).toFixed(3)} ${((c.bbox[3] - c.bbox[1]) * 1.6).toFixed(3)}" role="img" aria-label="${esc(c.name)} County on the map"><path class="cout" d="${DATA.outline.d}"></path><path class="cc sel" d="${c.d}"></path></svg>`;
}
function route(h){ const m = /^#c=(\d{3})$/.exec(h || location.hash); if (m) return county(m[1]); $("#pg-county").hidden = true; $("#pg-home").hidden = false; if (h === "") history.replaceState(null, "", "#top"); }
addEventListener("hashchange", () => route());
route();
</script>
</body>
</html>
"""


def kpis(data):
    n_off = sum(len(c["officials"]) for c in data["counties"].values())
    with_off = sum(1 for c in data["counties"].values() if c["officials"])
    rows = [f'<div><dd>{len(data["counties"])}</dd><dt>counties</dt></div>']
    if n_off:
        rows.append(f'<div><dd>{n_off:,}</dd><dt>county offices on file, in {with_off} counties</dt></div>')
        rows.append(f'<div><dd>{len(data["elections"])}</dd><dt>elections read</dt></div>')
    else:
        rows.append('<div><dd>0</dd><dt>county offices on file yet</dt></div>')
    return "\n".join(rows)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--place", required=True)
    ap.add_argument("--out", default="", help="default site/dev/<place>/counties/index.html")
    args = ap.parse_args()
    code = args.place.lower()
    P = place(code)
    data = collect(P, code)
    data["name"] = P["name"]
    log = read_changelog(os.path.join(HERE, "CHANGELOG.md"))
    version = (log[0].get("version") if log else "") or ""
    n_off = sum(len(c["officials"]) for c in data["counties"].values())
    note = (f"Who holds each office is on file for {sum(1 for c in data['counties'].values() if c['officials'])} counties." if n_off
            else "Who holds each office is not loaded yet; the Secretary of State's results files are the next step.")
    elections = ("Elections read: " + "; ".join(f"{e['date']} ({e['files']}, SHA-256 {e['sha256'][:12]}…)" for e in data["elections"]) + ".") if data["elections"] else "No election has been read yet."
    page_data = {"q": data["q"], "name": P["name"], "outline": data["outline"], "elections": data["elections"],
                 "counties": {k: {"fips": c["fips"], "name": c["name"], "land": c["land"], "rings": c["rings"], "bbox": c["bbox"], "officials": c["officials"]} for k, c in data["counties"].items()}}
    html = (PAGE.replace("__CSS__", borrow("CSS")).replace("__DATA__", json.dumps(page_data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/"))
            .replace("__KPIS__", kpis(data)).replace("__OFFICIALS_NOTE__", html_attr(note)).replace("__ELECTIONS__", html_attr(elections))
            .replace("__VINTAGE__", html_attr(data["vintage"])).replace("__SRC_FILE__", html_attr(data["source"].get("file", ""))).replace("__SRC_SHA__", html_attr(data["source"].get("sha256", "")))
            .replace("__N__", str(len(data["counties"]))).replace("__GENERATED__", data["generated"])
            .replace("__VERSIONTEXT__", f"v{version}" if version else "").replace("__VERSION__", version).replace("__NAME__", html_attr(P["name"])))
    out = args.out or os.path.join(HERE, "site", "dev", code, "counties", "index.html")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    import page_extras      # "Take a break" in the header
    html = page_extras.add(html, root="../../")
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(html)
    print(f"    Wrote {out}: {P['name']}, {len(data['counties'])} counties, {n_off} county offices on file, {len(html.encode('utf-8')) / 1e3:,.0f} KB (version {version})")


if __name__ == "__main__":
    main()
