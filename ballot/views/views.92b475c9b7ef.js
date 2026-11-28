/* Ways to read a race (John, 2026-11-11): the core. One shared script for every race page of On The Ballot (the Congress page
   and each state's). It holds the registry the four views sign into (VIEWS.add), the "Read this race as" row under a race
   page's crumbs, the reader's choice (localStorage "tca.view.v1" and &view= in the address), the helpers every view uses,
   the L object (the links a view may make), the notebook panel (&nb=<path>, a step of history) with the race's entries, and
   the crossing that plays the first time in a visit a reader follows a notebook link.

   The page it runs on hands it a small bridge, window.__vw (written by the page's own script): what it knows about a race,
   where its data files are, the live figures' folder, and closures over the page's own functions so that nothing shown in
   the notebook is written twice (the polls tab's body, the Coverage file, the splits kit, this seat before, who lives here,
   the sources fold). Nothing here loads from another server; every localStorage and sessionStorage access is in try/catch;
   no pointer capture. The full page is always there: with no bridge, no renderer or any error, this script does nothing to it. */
(() => {
"use strict";
if (window.VIEWS) return;
const D = document, H = D.documentElement, W = window;
const P = () => W.__vw || null;
const $ = (s, el) => (el || D).querySelector(s), $$ = (s, el) => [...(el || D).querySelectorAll(s)];

/* ================================ helpers (VIEWS.esc, num, pct, when, day, chance, partyVar, calm, T) ================================ */
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
const sub = (s, v) => String(s).replace(/\{(\w+)\}/g, (m, k) => v && v[k] != null ? String(v[k]) : m);
/* every sentence a reader sees goes through the page's language layer when the page has one */
const T = (s, v) => { const p = P(); try { if (p && typeof p.T === "function") { const out = p.T(s, v || {}); if (out != null) return String(out); } } catch (e) {} return sub(s, v); };
const num = n => (n == null || n === "" || isNaN(n)) ? "" : Number(n).toLocaleString("en-US");
const pct = (x, d = 1) => (x == null || x === "" || isNaN(x)) ? "" : Number(x).toFixed(d) + "%";
const level = () => { const p = P(); try { if (p && typeof p.level === "function") return +p.level() || 3; } catch (e) {} return +H.dataset.level || 3; };
/* each state's own time, by its capital's zone; the zone's family name as the pages write it ("ET", "CT") */
const TZ = {AL: "America/Chicago", AK: "America/Anchorage", AZ: "America/Phoenix", AR: "America/Chicago", CA: "America/Los_Angeles", CO: "America/Denver",
  CT: "America/New_York", DE: "America/New_York", DC: "America/New_York", FL: "America/New_York", GA: "America/New_York", HI: "Pacific/Honolulu", ID: "America/Boise",
  IL: "America/Chicago", IN: "America/Indiana/Indianapolis", IA: "America/Chicago", KS: "America/Chicago", KY: "America/Kentucky/Louisville", LA: "America/Chicago",
  ME: "America/New_York", MD: "America/New_York", MA: "America/New_York", MI: "America/Detroit", MN: "America/Chicago", MS: "America/Chicago", MO: "America/Chicago",
  MT: "America/Denver", NE: "America/Chicago", NV: "America/Los_Angeles", NH: "America/New_York", NJ: "America/New_York", NM: "America/Denver", NY: "America/New_York",
  NC: "America/New_York", ND: "America/Chicago", OH: "America/New_York", OK: "America/Chicago", OR: "America/Los_Angeles", PA: "America/New_York", RI: "America/New_York",
  SC: "America/New_York", SD: "America/Chicago", TN: "America/Chicago", TX: "America/Chicago", UT: "America/Denver", VT: "America/New_York", VA: "America/New_York",
  WA: "America/Los_Angeles", WV: "America/New_York", WI: "America/Chicago", WY: "America/Denver", PR: "America/Puerto_Rico"};
const ZN = {EST: "ET", EDT: "ET", CST: "CT", CDT: "CT", MST: "MT", MDT: "MT", PST: "PT", PDT: "PT", AKST: "AKT", AKDT: "AKT", HST: "HT", HDT: "HT", AST: "AT"};
const CUR = {st: ""};
const parts = (d, tz, o) => { try { return new Intl.DateTimeFormat("en-US", Object.assign({timeZone: tz}, o)).formatToParts(d); } catch (e) { return null; } };
const partOf = (ps, k) => ((ps || []).find(p => p.type === k) || {}).value || "";
const dateOnly = s => /^\d{4}-\d{2}-\d{2}$/.test(String(s || "").slice(0, 10)) && String(s).length <= 10;
function when(iso, st){      /* "November 10, 9:04 p.m. ET": the day and the time in the state's own zone */
  if (!iso) return "";
  if (dateOnly(iso)) return day(iso);
  const d = new Date(iso); if (isNaN(d)) return String(iso);
  const tz = TZ[(st || CUR.st || "").toUpperCase()] || "America/New_York";
  const ps = parts(d, tz, {month: "long", day: "numeric", hour: "numeric", minute: "2-digit", hour12: true, timeZoneName: "short"});
  if (!ps) return d.toLocaleString("en-US");
  const ap = partOf(ps, "dayPeriod").toLowerCase().replace(/^am$/, "a.m.").replace(/^pm$/, "p.m."), zn = partOf(ps, "timeZoneName");
  return `${partOf(ps, "month")} ${partOf(ps, "day")}, ${partOf(ps, "hour")}:${partOf(ps, "minute")} ${ap} ${ZN[zn] || zn}`;
}
function day(iso, st){      /* "November 3, 2026"; a date alone is the same day everywhere, a time stamp is read in the state's zone */
  if (!iso) return "";
  const s = String(iso);
  if (dateOnly(s)) { const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(s); const d = new Date(Date.UTC(+m[1], +m[2] - 1, +m[3]));
    const ps = parts(d, "UTC", {month: "long", day: "numeric", year: "numeric"}); return ps ? `${partOf(ps, "month")} ${partOf(ps, "day")}, ${partOf(ps, "year")}` : s; }
  const d = new Date(s); if (isNaN(d)) return s;
  const ps = parts(d, TZ[(st || CUR.st || "").toUpperCase()] || "America/New_York", {month: "long", day: "numeric", year: "numeric"});
  return ps ? `${partOf(ps, "month")} ${partOf(ps, "day")}, ${partOf(ps, "year")}` : d.toLocaleDateString("en-US");
}
const chance = p => { const v = 100 * Number(p); if (isNaN(v)) return ""; if (v > 99) return T("more than 99 in 100"); if (v < 1) return T("less than 1 in 100"); return T("about {n} in 100", {n: Math.round(v)}); };
function partyVar(code){      /* the page's colour variable for a party code (the list's one-letter codes and the count's three-letter ones); "" for none */
  const c = String(code || "").trim().toUpperCase(); if (!c) return "";
  if (/^(D|DEM|DFL|NPL|DEMOCRAT(IC)?(-.*)?)$/.test(c) || /^DEMOCRATIC/.test(c)) return "var(--pD)";
  if (/^(R|REP|GOP|REPUBLICAN)$/.test(c)) return "var(--pR)";
  if (/^(L|LIB|LBT|LIBERTARIAN)$/.test(c)) return "var(--pL)";
  if (/^(G|GRE|GRN|GREEN|PACIFIC GREEN)$/.test(c)) return "var(--pG)";
  if (/^(I|IND|INDEPENDENT|NPA|UND|UNA|UNAFFILIATED)$/.test(c)) return "var(--pI)";
  if (/^(N|NP|NON|NONPARTISAN|WI|WRITE-?IN)$/.test(c)) return "";
  return "var(--pO)";
}
const calm = () => { try { if (H.classList.contains("calm")) return true; const m = H.getAttribute("data-motion"); if (m && m !== "full") return true;
  if (H.getAttribute("data-calm") === "on") return true; if (matchMedia("(prefers-reduced-motion: reduce)").matches) return true; } catch (e) {} return false; };
/* the reading settings on <html>, as the shell's head script writes them on every page it rides (data-motion, data-calm): a page built on its
   own lacks them until the shell rides it, so they are written here too, from the same saved choices, and data-calm follows the page's own
   Motion switch (html.calm) from then on, so a view's CSS gate (html[data-motion="full"]:not([data-calm="on"])) agrees with VIEWS.calm() */
function settings(){
  const g = k => { try { return localStorage.getItem(k); } catch (e) { return null; } };
  let s = null; try { s = JSON.parse(g("tca.a11y.v1") || "null"); } catch (e) { s = null; }
  let motion = "full", c = "off";
  if (s && typeof s === "object") { if (s.motion === "reduced") motion = "reduced"; if (s.calm === "on") c = "on"; }
  else { try { if (matchMedia("(prefers-reduced-motion: reduce)").matches) motion = "reduced"; } catch (e) {} }
  const mo = g("motion"); if (mo === "off" && c !== "on") motion = "reduced"; if (mo === "on") motion = "full";
  if (H.classList.contains("calm")) c = "on";
  if (!H.hasAttribute("data-motion")) H.setAttribute("data-motion", motion);
  if (!H.hasAttribute("data-calm")) H.setAttribute("data-calm", c);
  try { new MutationObserver(() => { const on = H.classList.contains("calm"); if ((H.getAttribute("data-calm") === "on") !== on) H.setAttribute("data-calm", on ? "on" : "off"); }).observe(H, {attributes: true, attributeFilter: ["class"]}); } catch (e) {}
}
settings();
const kept = {get: (k, d) => { try { const v = localStorage.getItem(k); return v ? JSON.parse(v) : d; } catch (e) { return d; } },
  set: (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} },
  sget: k => { try { return sessionStorage.getItem(k); } catch (e) { return null; } }, sset: (k, v) => { try { sessionStorage.setItem(k, v); } catch (e) {} }};
const soft = (p, ms) => new Promise(ok => { let done = false; const end = v => { if (!done) { done = true; ok(v); } };
  Promise.resolve(p).then(end, () => end(null)); setTimeout(() => end(null), ms || 4000); });
const FILES = {};
const json = url => FILES[url] || (FILES[url] = fetch(url).then(x => x.ok ? x.json() : Promise.reject(x.status)).catch(e => { delete FILES[url]; return Promise.reject(e); }));
const last = n => String(n || "").trim().replace(/,?\s+(Jr\.?|Sr\.?|II|III|IV)$/i, "").split(/\s+/).pop();
const andList = a => a.length < 2 ? (a[0] || "") : a.slice(0, -1).join(", ") + " " + T("and") + " " + a[a.length - 1];

/* ================================ the registry ================================ */
const REG = new Map();
const ORDER_FULL = 1e6;
function add(def){
  if (!def || !def.id || typeof def.render !== "function" || def.id === "full") return;
  REG.set(def.id, Object.assign({order: 50, label: def.id}, def));
  if (M.host) { drawBar(); if (M.view === def.id || (M.view === "full" && wanted() === def.id)) show(wanted()); }
}
const list = () => [...REG.values()].sort((a, b) => (a.order || 50) - (b.order || 50));

/* ================================ the address and the reader's choice ================================ */
const KEY = "tca.view.v1";
const hashOf = () => { try { return decodeURIComponent(location.hash.slice(1)); } catch (e) { return location.hash.slice(1); } };
const param = (h, k) => { const m = new RegExp("(?:^|&)" + k + "=([^&]*)").exec(h || ""); return m ? m[1] : null; };
const raceOf = h => (h || "").startsWith("race=") ? h.slice(5).split("&")[0] : "";
function setParam(k, v, push, state){
  let h = location.hash.replace(new RegExp("&" + k + "=[^&]*(?=&|$)", "g"), "");
  if (v != null && v !== "") h += "&" + k + "=" + encodeURIComponent(v).replace(/%2F/gi, "/").replace(/%3A/gi, ":");
  try { history[push ? "pushState" : "replaceState"](state === undefined ? history.state : state, "", location.pathname + location.search + h); } catch (e) {}
  lastHash = location.href;
}
const stored = () => { const v = kept.get(KEY, null); return v && v.v ? String(v.v) : ""; };
const store = id => kept.set(KEY, {v: id});
function wanted(){
  const ids = list().map(x => x.id), ok = v => v === "full" || ids.includes(v);
  const a = param(hashOf(), "view"); if (a && ok(a)) return a;
  const s = stored(); if (s && ok(s)) return s;
  return ids.includes("front") ? "front" : ids[0] || "full";
}

/* ================================ the race page: the switch row, the host, the view shown ================================ */
const M = {host: null, bar: null, race: "", S: null, L: null, part: null, info: null, view: "", clean: null, ready: null};
function mount(host){
  host = host || $("#vwhost"); if (!host || !P()) return;
  const id = host.dataset.race || raceOf(hashOf()); if (!id) return;
  const p = P();
  let part = null; try { part = p.race(id); } catch (e) { console.error("views: the page's account of this race failed", e); part = null; }
  M.host = host; M.bar = $("#vwbar"); M.race = id; M.S = null; M.L = null; M.part = part; M.info = null;
  host.dataset.ready = "1"; CUR.st = part && part.S && part.S.st || "";
  if (!part || !part.S) { show("full"); return; }
  drawBar();
  show(wanted());
  M.ready = assemble(id, part).then(([S, info]) => { if (M.race !== id || !M.host || !M.host.isConnected) return; M.S = S; M.info = info; M.L = makeL(S); show(wanted(), true);
    const nb = param(hashOf(), "nb"); if (nb) NB.open(nb, {push: false}); else if (param(hashOf(), "go")) goFull(param(hashOf(), "go")); },
    e => { console.error("views: the race's figures could not be gathered", e); if (M.race === id) show("full"); });
}
function drawBar(){
  const bar = M.bar; if (!bar) return;
  const cur = M.view || wanted(), items = list().map(v => ({id: v.id, label: v.label})).concat([{id: "full", label: T("The full page")}]);
  const S0 = (M.part && M.part.S) || {};
  /* the page's one <h1> while a view is shown (the full page's hero, with its own h1, is put away then; the views use h2 and h3) */
  const head = S0.title ? `<div class="vwbar-head"><p class="vwbar-eyebrow">${esc(S0.office || "")}${S0.date ? ` &middot; ${esc(day(S0.date))}` : ""}${S0.special ? ` &middot; ${esc(T("Special election"))}` : ""}</p><h1 class="vwbar-h1" translate="no">${esc(stripTags(S0.title))}</h1></div>` : "";
  bar.innerHTML = head + `<div class="vwbar-row"><span class="vwbar-l">${esc(T("Read this race as"))}</span><div class="vwbar-c" role="group" aria-label="${esc(T("Ways to read this race"))}">`
    + items.map(v => `<button type="button" class="vwbtn" data-view="${esc(v.id)}" aria-pressed="${v.id === cur ? "true" : "false"}">${esc(T(v.label))}</button>`).join("") + "</div></div>";
  bar.hidden = false;
}
function pressBar(id){ if (M.bar) $$(".vwbtn", M.bar).forEach(b => b.setAttribute("aria-pressed", b.dataset.view === id ? "true" : "false")); }
function show(id, fromData){
  const app = $("#app"), host = M.host; if (!app || !host) return;
  if (id !== "full" && !REG.has(id)) id = wanted();
  if (M.clean) { try { M.clean(); } catch (e) {} M.clean = null; }
  M.view = id; app.dataset.view = id; pressBar(id);
  if (M.bar) M.bar.classList.remove("has-h1");
  if (id === "full") {
    app.classList.remove("vw-on"); host.hidden = true; host.innerHTML = "";
    const p = P(); try { if (p && p.shown) p.shown(); } catch (e) {}
    return;
  }
  app.classList.add("vw-on"); host.hidden = false;
  if (!M.S) { host.innerHTML = `<p class="vwload" role="status">${esc(T("Loading the figures for this race…"))}</p>`; return; }
  const def = REG.get(id);
  let html = "";
  try { html = def.render(M.S, M.L); } catch (e) { console.error("views: the " + id + " view could not be drawn", e); show("full"); return; }
  host.innerHTML = `<div class="vw vw-${esc(id)}" data-view="${esc(id)}">${html}</div>`;
  const root = host.firstElementChild;
  if (M.bar) M.bar.classList.toggle("has-h1", !!root.querySelector("h1"));      /* a view with a heading of its own: the page's one h1 is that */
  try { if (typeof def.wire === "function") { const c = def.wire(root, M.S, M.L); if (typeof c === "function") M.clean = c; } } catch (e) { console.error("views: the " + id + " view could not be wired", e); }
  if (fromData) { try { const p = P(); if (p && p.dom) p.dom(root); } catch (e) {} }
}
function choose(id, o = {}){
  if (id !== "full" && !REG.has(id)) return;
  if (o.store !== false) store(id);
  setParam("view", id, !!o.push);
  if (M.view !== id) show(id);
}
/* the full page, with one of its sections brought into view (L.full): the tabs open themselves, the comparison too */
function goFull(section){
  if (M.view !== "full") show("full");
  setParam("go", null, false);
  const p = P(); let el = null;
  try { el = p && p.fullSection ? p.fullSection(section) : null; } catch (e) { el = null; }
  try { if (p && p.openFull) p.openFull(section); } catch (e) {}
  if (!el) return;
  const go = () => { if (!el.isConnected) return; el.scrollIntoView({block: "start", behavior: calm() ? "auto" : "smooth"}); };
  requestAnimationFrame(go); setTimeout(go, 120);
  const f = el.matches("button,a,[tabindex]") ? el : (el.querySelector("h2,h3,summary,button") || el);
  try { if (!f.hasAttribute("tabindex") && !f.matches("button,a,summary")) f.tabIndex = -1; f.focus({preventScroll: true}); } catch (e) {}
}

/* ================================ S: the race's figures, gathered from what the page already has ================================ */
async function assemble(id, part){
  const p = P();
  const S = Object.assign({v: 1}, part.S);
  (S.list || []).forEach(c => { c.code = S.partisan ? codeOf(c.code) : ""; });
  if (S.holder) { S.holder.code = S.partisan ? codeOf(S.holder.code) : ""; if (S.kind === "retention") S.holder.running = true; }      /* a retention vote is about the holder */
  const info = (await soft(p.st ? p.st(S.st) : null, 9000)) || {};
  if (typeof p.fixture === "function") { const F = p.fixture(id); if (F) return [Object.assign({v: 1}, F), info]; }      /* a lab page: the figures as given */
  const noFc = S.kind === "unopposed" || S.kind === "none" || S.kind === "retention";
  const [live, fc, cov] = await Promise.all([soft(liveCount(p, S, info), 9000), noFc ? null : soft(chartOf(p, id), 7000), soft(coverageOf(p, id), 7000)]);
  if (live && live.count) { S.count = live.count; if (live.counties) S.counties = live.counties; }
  if (fc) S.forecast = fc;
  if (cov) S.coverage = cov;
  const polls = pollsOf(p, id); if (polls) S.polls = polls;
  S.source = {office: info.office || "", page: info.page || "", label: info.label || ""};
  S.read = new Date().toISOString().slice(0, 10);
  return [S, info];
}
const NOW = {at: 0, p: null};
function getNow(live){
  if (NOW.p && Date.now() - NOW.at < 60000) return NOW.p;
  NOW.at = Date.now(); NOW.p = fetch(live + "now.json", {cache: "no-store"}).then(x => x.ok ? x.json() : Promise.reject(x.status)).catch(e => { NOW.p = null; return Promise.reject(e); });
  return NOW.p;
}
const PARTY = {DEM: "Democratic", REP: "Republican", LIB: "Libertarian", GRE: "Green", GRN: "Green", DFL: "Democratic-Farmer-Labor", IND: "Independent", NPL: "Democratic-NPL",
  CON: "Constitution", WI: "", NP: "", N: ""};
/* one form for a party code inside S: the one-letter codes the ballot lists carry (D, R, L, G, I; "" for none or a write-in); a code the
   results file writes long (DEM, REP, LIB, GRE, DFL) is shortened to the same letters, and a code neither knows is kept as written */
function codeOf(code){
  const c = String(code || "").trim().toUpperCase(); if (!c) return "";
  if (/^(D|DEM|DFL|NPL)$/.test(c) || /^DEMOCRAT/.test(c)) return "D";
  if (/^(R|REP|GOP|REPUBLICAN)$/.test(c)) return "R";
  if (/^(L|LIB|LBT|LIBERTARIAN)$/.test(c)) return "L";
  if (/^(G|GRE|GRN|GREEN)$/.test(c)) return "G";
  if (/^(I|IND|INDEPENDENT|NPA|UND|UNA|UNAFFILIATED)$/.test(c)) return "I";
  if (/^(N|NP|NON|NONPARTISAN|WI|WRITE-?IN)$/.test(c)) return "";
  return c;
}
function countyName(info, fips){ try { const cn = info && info.cn; if (typeof cn === "function") return cn(fips) || fips; if (cn && cn[fips]) return cn[fips]; } catch (e) {} return fips; }
async function liveCount(p, S, info){
  if (!p.live) return null;
  const now = await getNow(p.live); if (!now || !now.st) return null;
  const stx = now.st[S.st]; if (!stx || !stx.f) return null;
  const file = await json(p.live + now.base + stx.f); if (!file || !file.r) return null;
  const pre = file.pre || "", key = pre && S.id.startsWith(pre) ? S.id.slice(pre.length) : S.id;
  const r = file.r[key]; if (!r) return null;
  const ch = r.ch || [], v = r.v || [];
  const total = v.reduce((a, b) => a + (+b || 0), 0);
  const byName = new Map((S.list || []).map(c => [c.n, c]));
  const partyOf = c => { const l = byName.get(c[1]); if (l && l.party) return l.party; if (!S.partisan) return ""; const k = String(c[2] || "").toUpperCase(); return PARTY[k] != null ? PARTY[k] : (c[2] || ""); };
  const inOrder = ch.map((c, i) => ({n: c[3] ? T("Write-ins") : c[1], party: c[3] ? "" : partyOf(c), code: S.partisan && !c[3] ? codeOf(c[2]) : "", votes: +v[i] || 0,
    share: total ? Math.round(10000 * (+v[i] || 0) / total) / 100 : 0, wi: !!c[3]}));
  const names = inOrder.map(c => c.n), cands = [...inOrder].sort((a, b) => b.votes - a.votes);
  const K = r.k || {}; let pin = 0, pof = 0, csum = 0; const top = [], won = {};
  for (const [fips, row] of Object.entries(K)) {
    const inn = +row[0] || 0, of = +row[1] || 0; pin += inn; pof += of;
    const votes = row.slice(2).map(x => +x || 0), t = votes.reduce((a, b) => a + b, 0); csum += t;
    if (!t) continue;
    let mi = 0; for (let i = 1; i < votes.length; i++) if (votes[i] > votes[mi]) mi = i;
    const lead = names[mi] || ""; if (lead) won[lead] = (won[lead] || 0) + 1;
    top.push({fips, name: countyName(info, fips), total: t, shares: Object.fromEntries(names.map((n, i) => [n, Math.round(1000 * (votes[i] || 0) / t) / 10])), lead, done: of > 0 && inn >= of});
  }
  top.sort((a, b) => b.total - a.total);
  const reporting = Array.isArray(r.p) && r.p.length === 2 ? [+r.p[0] || 0, +r.p[1] || 0] : (pof ? [pin, pof] : null);
  const count = {at: stx.t || file.at || now.at || "", status: stx.s || "", reporting, total, cands, county_sum: csum, final: stx.s === "official"};
  const counties = Object.keys(K).length ? {n: top.length, won, top: top.slice(0, 8), all_done: top.length > 0 && top.every(c => c.done)} : null;
  return {count, counties};
}
const pick = (o, ks) => Object.fromEntries(ks.filter(k => o && o[k] !== undefined).map(k => [k, o[k]]));
async function chartOf(p, id){
  const C = p.chart; if (!C || !C.has || !C.has(id)) return null;
  const d = await json(C.base + encodeURIComponent(id) + ".json?v=" + encodeURIComponent((typeof C.v === "function" ? C.v() : C.v) || ""));
  const fc = d && d.fc; if (!fc || !(fc.top || []).length || fc.top.length < 2) return null;
  return {at: fc.at || "", model: fc.m || "", draws: fc.draws || null, env: fc.env || "", top: fc.top.map(c => pick(c, ["n", "ch", "md", "l80", "h80", "l95", "h95"])),
    rest: (fc.rest || []).map(c => pick(c, ["n", "md", "l80", "h80"])), track: fc.track || null,
    hist: (fc.hist || []).map(h => ({at: h.at, c: Object.fromEntries(Object.entries(h.c || {}).map(([n, v]) => [n, (v || []).slice(0, 4)]))}))};
}
async function coverageOf(p, id){
  const C = p.cov; if (!C || !C.n || !C.n(id)) return null;
  const d = await json(C.base + encodeURIComponent(id) + ".json?v=" + encodeURIComponent(C.v || "")); if (!d) return null;
  const news = {};
  for (const [k, b] of Object.entries(d.news || {})) { const items = b.i || []; news[k] = {n: items.length + (+b.more || 0), top: items.slice(0, 3).map(x => pick(x, ["h", "o", "t", "u"]))}; }
  return {n: d.n || C.n(id) || [0, 0, 0, 0], checked: d.ck || "", calls: (d.calls || []).map(c => ({o: c.o, n: c.n, t: c.t || "", u: c.u || "", by: c.by || null})),
    said: (d.said || []).map(s => ({n: s.n, s: (s.s || []).map(x => pick(x, ["k", "m", "by", "d", "u"]))})), news};
}
function pollsOf(p, id){
  const P0 = p.polls ? p.polls(id) : null; if (!P0) return null;
  const polls = [...(P0.polls || [])].sort((a, b) => String(b.end || "").localeCompare(String(a.end || ""))), other = (P0.news || []).length;
  if (!polls.length && !other) return null;
  return {n: polls.length, other, newest: polls.slice(0, 3).map(x => ({pollster: x.pollster || "", start: x.start || "", end: x.end || "", n: x.n ?? null, pop: x.pop || "", moe: x.moe ?? null, shares: x.shares || {}, url: x.url || ""}))};
}

/* ================================ L: the links a view may use ================================ */
const ENTRIES = ["count", "counties", "splits", "forecast", "forecast/how", "forecast/track", "forecast/runs", "polls", "coverage", "coverage/calls", "coverage/said",
  "coverage/news", "list", "primaries", "past", "wlh", "ads", "sources"];
const METHOD = ["method/labels", "method/calls", "method/forecasts", "method/polls", "method/sources"];
function has(S, path){
  if (!S) return false;
  const F = S.forecast, C = S.coverage;
  switch (path) {
    case "count": return !!S.count;
    case "counties": return !!(S.counties && (S.counties.top || []).length);
    case "splits": return !!S.splits;
    case "forecast": return !!F;
    case "forecast/how": return !!F;
    case "forecast/track": return !!(F && F.track);
    case "forecast/runs": return !!(F && (F.hist || []).length);
    case "polls": return !!(S.polls || (M.part && M.part.fill && M.part.fill.hasPolls && M.part.fill.hasPolls()));
    case "coverage": return !!C;
    case "coverage/calls": return !!(C && (C.calls || []).length);
    case "coverage/said": return !!(C && (C.said || []).length);
    case "coverage/news": return !!(C && Object.values(C.news || {}).some(t => t.n));
    case "list": return true;
    case "primaries": return !!S.primaries;
    case "past": return !!S.past;
    case "wlh": return !!S.wlh;
    case "ads": return !!S.ads;
    case "sources": return !!(M.part && M.part.fill && M.part.fill.hasSources && M.part.fill.hasSources());
    default: return METHOD.includes(path);
  }
}
function makeL(S){
  const id = S.id, p = P(), base = "#race=" + id, info = M.info || {};
  const L = {
    nb: (path, text, o = {}) => has(S, path) ? `<a class="nbl${o.cls ? " " + esc(o.cls) : ""}" href="${base}&nb=${esc(path)}" data-nbk="${esc(path)}"${o.anchor ? ` data-anchor="${esc(o.anchor)}"` : ""}><span class="nbl-i" aria-hidden="true"></span>${text}</a>` : `<span class="nbl-none">${text}</span>`,
    has: path => has(S, path),
    full: section => base + "&view=full" + (section ? "&go=" + encodeURIComponent(section) : ""),
    hasFull: section => { try { return !!(p && p.fullSection && p.fullSection(section)); } catch (e) { return false; } },
    view: vid => base + "&view=" + encodeURIComponent(vid),
    chart: () => { try { return p.chart && p.chart.has(id) ? base + "&chart=open" : ""; } catch (e) { return ""; } },
    night: () => { try { return (info.night && info.night(id)) || ""; } catch (e) { return ""; } },
    past: () => { try { return (typeof info.past === "function" ? info.past(id) : info.past) || ""; } catch (e) { return ""; } },
    tab: name => base + "&view=full&tab=" + encodeURIComponent(name)
  };
  return L;
}

/* ================================ the notebook ================================ */
const NB = {el: null, open: null, close: null, path: "", pushed: false, from: null, anchor: "", inerted: []};
const PINS = "tca.nb.pins.v1", NOTES = "tca.nb.notes.v1", SEEN = "tca.nb.crossed";
const KIND = {c: "Conceded", v: "Declared victory", s: "Statement", w: "Withdrew", a: "Accepted the result"}, MEDIUM = {t: "text", v: "video", p: "a post", a: "audio"};
const tag = (t, k) => `<span class="nbtag" data-k="${esc(k || t)}">${esc(T(t))}</span>`;
const nbt = (caption, head, rows, foot) => `<div class="nbt-w" tabindex="0" role="region" aria-label="${esc(caption)}"><table class="nbt"><caption>${esc(caption)}</caption><thead><tr>${head}</tr></thead><tbody>${rows}</tbody>${foot ? `<tfoot>${foot}</tfoot>` : ""}</table></div>`;
const ext = (u, text) => /^https?:\/\//i.test(String(u || "")) ? `<a href="${esc(u)}" target="_blank" rel="noopener noreferrer">${text}</a>` : text;
const B = s => `<b>${s}</b>`;
const seatsWord = S => S.seats > 1 ? T("the {n} with the most votes", {n: S.seats}) : "";
function entryKey(path){ return METHOD.includes(path) ? path : `${M.race}|${path}`; }
function longPath(path){ const S = M.S || {}; return METHOD.includes(path) ? path : `ballot/${String(S.st || "").toLowerCase()}/${String(S.id || "").toLowerCase()}/${path}`; }

/* the race's entries: each {t, tags, lede, body (HTML, or a Promise of it, or a function filling a box), src, cant, rel, site} */
function entries(S, L){
  const E = {}, p = P(), fill = (M.part && M.part.fill) || {}, office = S.source && S.source.office || T("the state's election office"), srcPage = S.source && S.source.page || "";
  const C = S.count, F = S.forecast, V = S.coverage, K = S.counties;
  const partyCol = S.partisan;
  const entry = (path, t, o) => { E[path] = Object.assign({t}, o); };
  const reported = C ? (C.final ? T("As certified") : T("As reported, not final")) : "";
  const asOf = C ? when(C.at, S.st) : "";
  const srcLabel = esc(S.source && S.source.label || office);
  const srcCount = [[srcLabel, srcPage, C ? T("read by this site; this reading {when}", {when: asOf}) : ""]];
  const siteNight = L.night() ? [[T("This race on Election Night"), L.night()]] : [];
  const siteFull = sec => [[T("The full page of this race"), L.full(sec)]];
  const nm = n => `<span translate="no">${esc(n)}</span>`;
  /* ---- the count */
  if (C) {
    const cs = C.cands, lead = cs[0], second = cs[1], rep = C.reporting;
    const repWords = rep ? T("{a} of {b} precincts reporting", {a: num(rep[0]), b: num(rep[1])}) : (C.status === "done" ? T("every unit reporting") : T("the count under way"));
    let lede;
    if (!C.total) lede = T("As reported by {office}: no votes posted yet for this race ({rep}).", {office: esc(office), rep: repWords});
    else if (S.kind === "retention" || cs.length === 1) lede = T("As reported by {office}: {name} {votes} votes ({share}), with {rep}.", {office: esc(office), name: nm(lead.n), votes: num(lead.votes), share: pct(lead.share), rep: repWords});
    else if (S.seats > 1) lede = T("As reported by {office}, {rep}. Voters choose {n}; the {n} with the most votes so far: {names}.", {office: esc(office), rep: repWords, n: S.seats, names: andList(cs.filter(c => !c.wi).slice(0, S.seats).map(c => nm(c.n)))});
    else lede = T("As reported by {office}: {a} {av} votes ({ap}), {b} {bv} ({bp}), with {rep}.", {office: esc(office), a: nm(lead.n), av: num(lead.votes), ap: pct(lead.share), b: nm(second.n), bv: num(second.votes), bp: pct(second.share), rep: repWords});
    const rows = cs.map(c => `<tr><th scope="row">${partyCol && c.code ? `<i class="nbdot" style="background:${partyVar(c.code) || "transparent"}" aria-hidden="true"></i>` : ""}${nm(c.n)}</th>${partyCol ? `<td>${esc(c.party)}</td>` : ""}<td class="n">${num(c.votes)}</td><td class="n">${pct(c.share, 2)}</td></tr>`).join("");
    const head = `<th scope="col">${esc(S.kind === "retention" ? T("Choice") : T("Candidate"))}</th>${partyCol ? `<th scope="col">${esc(T("Party"))}</th>` : ""}<th scope="col" class="n">${esc(T("Votes"))}</th><th scope="col" class="n">${esc(T("Share"))}</th>`;
    const foot = `<tr><th scope="row">${esc(T("All"))}</th>${partyCol ? "<td></td>" : ""}<td class="n">${num(C.total)}</td><td class="n">100%</td></tr>`;
    const gap = C.total && cs.length > 1 ? `<p>${T("The gap between the first two is {v} votes, or {pts} points of the vote.", {v: num(lead.votes - second.votes), pts: (lead.share - second.share).toFixed(1)})}</p>` : "";
    const cgap = C.total - (C.county_sum == null ? C.total : C.county_sum);
    const agree = C.county_sum == null || !K ? "" : cgap === 0 ? `<p>${T("The county figures in the same reading add up to the statewide total exactly.")}</p>`
      : `<p>${T("The county figures in the same reading add up to {sum} votes, {diff} {more} than the total posted for the race. This site shows each as the office posts it and adjusts neither.", {sum: num(C.county_sum), diff: num(Math.abs(cgap)), more: cgap > 0 ? T("fewer") : T("more")})}</p>`;
    entry("count", T("The count"), {tags: [T("Official count"), reported], lede,
      body: nbt(T("Votes for {what}, as reported {when}", {what: stripTags(S.title || S.office), when: asOf}), head, rows, foot) + gap + agree
        + (C.final ? "" : `<p>${T("The result is final when the state certifies it; until then these figures can change. The Civic Archive does not call races.")}</p>`),
      src: srcCount, cant: [T("It is not final until the state certifies it: counties still check every ballot, and the figures can change."), T("It cannot show how any one person voted, or why.")],
      rel: ["counties", "coverage/calls", "method/labels"], site: siteNight});
  }
  /* ---- county by county */
  if (K && (K.top || []).length) {
    const cs = C ? C.cands.filter(c => !c.wi).slice(0, 2) : [], wonl = Object.entries(K.won || {}).sort((a, b) => b[1] - a[1]).map(([n, k]) => `${nm(n)} ${num(k)}`).join("; ");
    const rows = K.top.map(c => `<tr><th scope="row">${esc(c.name)}</th><td class="n">${num(c.total)}</td>${cs.map(x => `<td class="n">${pct(c.shares[x.n] == null ? 0 : c.shares[x.n])}</td>`).join("")}<td>${nm(c.lead)}${c.done ? "" : ` <small>${esc(T("still counting"))}</small>`}</td></tr>`).join("");
    const head = `<th scope="col">${esc(T("County"))}</th><th scope="col" class="n">${esc(T("Votes"))}</th>${cs.map(x => `<th scope="col" class="n">${esc(last(x.n))}</th>`).join("")}<th scope="col">${esc(T("Most votes"))}</th>`;
    entry("counties", T("County by county"), {tags: [T("Official count"), reported],
      lede: K.n === 1 ? T("The count comes from one county.") : T("{n} counties reported. Counties where each candidate had the most votes: {won}.", {n: num(K.n), won: wonl}),
      body: nbt(T("The {n} counties with the most votes cast in this race", {n: K.top.length}), head, rows)
        + (K.n > 1 ? `<p>${T("A county with more votes is not a county that matters more: every vote counts the same. Counties are listed by size because that is where most of the votes are.")}</p>` : "")
        + (K.all_done ? "" : `<p>${T("Some counties are still counting.")}</p>`),
      src: [[srcLabel, srcPage, T("each county's figures, from the same file as the statewide count")]],
      cant: [T("Which counties a candidate led says nothing about how many votes they led by; the whole count decides."), T("A county's figures cannot show any one ballot.")],
      rel: ["count", "splits"], site: siteNight});
  }
  /* ---- blank votes and splits (the kit's own body) */
  if (S.splits && fill.splits) entry("splits", T("Votes left blank and split results"), {tags: [T("Analysis")],
    lede: T("How many fewer votes this race had than the race with the most votes in each county, and the counties that chose different parties for different races, worked out from the same county figures."),
    mount: box => fill.splits(box), cant: [T("County totals cannot show any one ballot."), T("Nothing here says that anyone split a ticket.")], rel: ["counties", "method/labels"]});
  /* ---- the forecast */
  if (F) {
    const top = F.top || [], first = top[0], shareOf = n => C ? (C.cands.find(c => c.n === n) || {}).share : null;
    const rows = top.map(c => `<tr><th scope="row">${nm(c.n)}</th><td class="n">${esc(chance(c.ch))}</td><td class="n">${pct(c.md)}</td><td class="n">${pct(c.l80)} ${esc(T("to"))} ${pct(c.h80)}</td><td class="n">${pct(c.l95)} ${esc(T("to"))} ${pct(c.h95)}</td>${C ? `<td class="n">${shareOf(c.n) == null ? "&ndash;" : pct(shareOf(c.n))}</td>` : ""}</tr>`).join("");
    const head = `<th scope="col">${esc(T("Candidate"))}</th><th scope="col" class="n">${esc(T("Chance"))}</th><th scope="col" class="n">${esc(T("Middle"))}</th><th scope="col" class="n">${esc(T("80 in 100"))}</th><th scope="col" class="n">${esc(T("95 in 100"))}</th>${C ? `<th scope="col" class="n">${esc(T("The count"))}</th>` : ""}`;
    const rest = (F.rest || []).length ? `<p>${T("Also on the ballot: {list}.", {list: (F.rest || []).map(c => T("{name}, likely {lo} to {hi}", {name: nm(c.n), lo: pct(c.l80), hi: pct(c.h80)})).join("; ")})}</p>` : "";
    const fs = first ? shareOf(first.n) : null;
    const verdict = first && fs != null ? `<p>${T("{name}'s share in the count, {share}, is {where} the 80-in-100 range the last run gave ({lo} to {hi}).", {name: nm(first.n), share: pct(fs), where: fs >= first.l80 && fs <= first.h80 ? T("inside") : T("outside"), lo: pct(first.l80), hi: pct(first.h80)})} ${T("A result outside the range is a miss, counted in the track record, not explained away.")}</p>` : "";
    const lede = first ? T("The last run before Election Day, {when}, gave {name} {chance} chance of the most votes, likely {lo} to {hi} of the vote.", {when: day(F.at, S.st), name: nm(first.n), chance: esc(chance(first.ch)), lo: pct(first.l80), hi: pct(first.h80)}) : T("A forecast was made for this race.");
    entry("forecast", T("The forecast, worked out"), {tags: [T("Analysis")], lede,
      body: nbt(T("The last run, {when}: each candidate's chance and likely share", {when: day(F.at, S.st)}), head, rows) + rest + verdict
        + (F.env ? `<p><b>${esc(T("In the model's own words:"))}</b> <span lang="en">${esc(F.env)}</span></p>` : "")
        + `<p>${T("The model ran {n} simulated elections; the ranges hold 80 and 95 in every 100 of them. A forecast is Analysis: an estimate, never a result and never a call.", {n: num(F.draws || 0)})}</p>`,
      src: [[T("This site's forecast model, version {v}", {v: esc(F.model || "")}), L.chart() || "", T("every run is kept and can be made again exactly")],
            [T("Polls by members of the American Association for Public Opinion Research's Transparency Initiative"), "https://aapor.org/standards-and-ethics/transparency-initiative/", T("the only polls the model counts")]],
      cant: [T("A forecast is not a result: the official count decides."), first ? T("A chance of {c} is not a promise; a favourite can lose.", {c: esc(chance(first.ch))}) : ""].filter(Boolean),
      rel: ["forecast/how", "forecast/track", "forecast/runs", "count"], site: L.chart() ? [[T("The race's chart, with every run"), L.chart()]] : []});
    entry("forecast/how", T("How this forecast is worked out"), {tags: [T("Analysis")],
      lede: T("A computer model's estimate from past official results and polls by members of the Transparency Initiative, labelled Analysis wherever it appears."),
      body: `<p>${T("Before Election Day the model starts from how the place voted in past official elections, moves that by the year's mood from members' polls, and adds who holds the seat. Census figures and campaign money are not used. Thousands of simulated elections give each candidate a chance of coming first and a likely range for their share of the vote: the middle 80 percent of the simulations, so about one race in five lands outside it.")}</p>`
        + `<p>${T("Chances are never 0 or 100 before the count is certified. No forecast is made for a race with one name for each seat. Every run is kept with its method version, the fingerprints of what went into it and its random seed, so it can be made again exactly.")}</p>`
        + (F.env ? `<p><b>${esc(T("For this race, in the model's own words:"))}</b> <span lang="en">${esc(F.env)}</span></p>` : ""),
      rel: ["forecast", "forecast/track", "method/forecasts"]});
    if (F.track) { const t = F.track;
      entry("forecast/track", T("The forecast's track record"), {tags: [T("Analysis")], lede: trackSentence(t, S),
        body: `<p>${T("A track record is how the same model would have done on elections already decided. It is the best guide to how far to trust a range, and it is shown wherever a forecast is.")}</p>`
          + (t.thin ? `<p>${T("That is a thin record: few past races of this kind were available to test on.")}</p>` : ""), rel: ["forecast", "forecast/how"]}); }
    if ((F.hist || []).length) {
      const names = top.map(c => c.n);
      const rows = F.hist.map(h => `<tr><th scope="row">${esc(when(h.at, S.st))}</th>${names.map(n => h.c[n] ? `<td class="n">${pct(h.c[n][0])} <span class="nbm">(${pct(h.c[n][1])} ${esc(T("to"))} ${pct(h.c[n][2])}; ${esc(chance(h.c[n][3]))})</span></td>` : "<td></td>").join("")}</tr>`).join("");
      entry("forecast/runs", T("Every run, in order"), {tags: [T("Analysis")], lede: T("How the estimate moved, run by run: the middle of each candidate's likely share, the 80-in-100 range and the chance."),
        body: nbt(T("Every run of the forecast for this race"), `<th scope="col">${esc(T("Run"))}</th>${names.map(n => `<th scope="col" class="n">${nm(n)}</th>`).join("")}`, rows), rel: ["forecast", "forecast/track"]}); }
  }
  /* ---- polls: the full page's own body */
  if (S.polls || (fill.hasPolls && fill.hasPolls())) entry("polls", T("Polls"), {tags: [T("Measured opinion")],
    lede: S.polls && S.polls.n ? (S.polls.n === 1 ? T("One poll counted, by a member of the Transparency Initiative and checked against its own release{o}. A poll measures opinion when it was taken, not a forecast.", {o: otherPolls(S.polls.other)})
        : T("{n} polls counted, each by a member of the Transparency Initiative and checked against its own release{o}. A poll measures opinion when it was taken, not a forecast.", {n: S.polls.n, o: otherPolls(S.polls.other)}))
      : T("We count only polls from members of the American Association for Public Opinion Research's Transparency Initiative. None has published a poll of this race that we could check."),
    body: () => (fill.polls ? fill.polls() : "") || `<p>${T("The full page's Polls tab has what there is.")}</p>`, rel: ["method/polls", "forecast"], site: L.hasFull("polls") ? siteFull("polls") : []});
  /* ---- coverage: the Coverage file through the page's own script, and its parts in the site's words */
  if (V) {
    const n = V.n || [0, 0, 0, 0];
    entry("coverage", T("Coverage"), {tags: [T("Links only")],
      lede: T("How news organizations reported this race, who called it, and what the candidates said after the election: {s} stories, {c} calls, {t} statements, {p} official posts, each a link to its own page. The Civic Archive does not call races.", {s: num(n[0]), c: num(n[1]), t: num(n[2]), p: num(n[3])}),
      mount: fill.coverage ? box => fill.coverage(box) : null, body: fill.coverage ? null : `<p>${T("The full page's Coverage tab lists every link.")}</p>`,
      src: [[T("Each outlet's and each campaign's own page or account"), "", V.checked ? T("links checked {d}", {d: day(V.checked)}) : ""]],
      cant: [T("Nothing is copied: the words are theirs, behind the links."), T("A candidate with no statement listed is not mentioned.")], rel: ["coverage/calls", "coverage/said", "coverage/news", "method/calls"],
      site: L.hasFull("coverage") ? siteFull("coverage") : []});
    if ((V.calls || []).length) entry("coverage/calls", T("Who called it"), {tags: [T("Links only")],
      lede: T("{n} news organizations called this race. A call is a news organization's judgment made before every ballot is counted; the result is final when the state certifies it. The Civic Archive does not call races.", {n: num(V.calls.length)}),
      body: `<ul class="nbl-list">${V.calls.map(c => `<li>${B(esc(c.o))} ${T("called it for {name}", {name: nm(c.n)})}${c.t ? ` ${esc(T("on"))} ${esc(when(c.t, S.st))}` : ""}${c.by && c.by !== c.o ? `, ${T("as reported by {by}", {by: esc(c.by)})}` : ""}${c.u ? ` (${ext(c.u, esc(T("the report")))})` : ""}</li>`).join("")}</ul>`,
      rel: ["coverage", "method/calls", "count"]});
    if ((V.said || []).length) entry("coverage/said", T("What the candidates said"), {tags: [T("Links only")],
      lede: T("{n} candidates made statements after the election, each linked where it was published.", {n: num(V.said.length)}),
      body: `<ul class="nbl-list">${V.said.map(s => `<li>${B(nm(s.n))}: ${s.s.map(x => `${esc(T(KIND[x.k] || "Statement"))} (${esc(T(MEDIUM[x.m] || "text"))}${x.d ? `, ${esc(x.d.length > 10 ? when(x.d, S.st) : day(x.d))}` : ""}${x.u ? `, ${ext(x.u, esc(x.by || T("link")))}` : x.by ? `, ${esc(x.by)}` : ""})`).join("; ")}</li>`).join("")}</ul>`,
      cant: [T("A candidate with no statement listed is not mentioned."), T("Nothing is copied beyond the kind of statement and where it was published.")], rel: ["coverage", "coverage/calls"]});
    const tiers = Object.entries(V.news || {}).filter(([, t]) => t.n);
    if (tiers.length) entry("coverage/news", T("News coverage"), {tags: [T("Links only")],
      lede: T("{list} stories, each linked under its outlet's own headline.", {list: tiers.map(([k, t]) => `${esc(T({national: "national", state: "state", local: "local"}[k] || k))} ${num(t.n)}`).join(", ")}),
      body: tiers.map(([k, t]) => `<h3>${esc(T({national: "National outlets", state: "State outlets", local: "Local outlets"}[k] || k))}</h3><ul class="nbl-list">${t.top.map(x => `<li>${ext(x.u, `<span lang="en">${esc(x.h)}</span>`)}<small>${esc(x.o)}${x.t ? ` &middot; ${esc(x.t.length > 10 ? when(x.t, S.st) : day(x.t))}` : ""}</small></li>`).join("")}${t.n > t.top.length ? `<li><small>${T("and {n} more on the full page's Coverage tab", {n: num(t.n - t.top.length)})}</small></li>` : ""}</ul>`).join(""),
      cant: [T("A headline is the outlet's own words; nothing is copied beyond it.")], rel: ["coverage"], site: L.hasFull("coverage") ? siteFull("coverage") : []});
  }
  /* ---- who is on the ballot, as filed */
  {
    const g = S.list || [], ls = S.list_source || {};
    const li = g.map(c => `<li><b translate="no">${esc(c.n)}</b>${partyCol && c.party ? `, <span translate="no">${esc(c.party)}</span>` : ""}${c.inc ? ` &middot; ${esc(T("holds the office today"))}` : ""}${c.wi ? ` &middot; ${esc(T("declared write-in: the name is not printed on the ballot"))}` : ""}${c.out ? ` &middot; <span lang="en">${esc(c.out)}</span>` : ""}${c.order != null ? ` <small>${esc(T("ballot order {n}", {n: c.order}))}</small>` : ""}</li>`).join("");
    const lede = S.kind === "none" ? (S.gap ? T("No candidate for this race is on the list loaded here: {why}.", {why: esc(S.gap)}) : T("No candidate for this race is on the official list."))
      : S.kind === "retention" ? T("A yes-or-no vote on whether {name} stays in office.", {name: nm(g[0] ? g[0].n : "")})
      : S.kind === "unopposed" ? T("{n} names, unopposed: no one runs against them.", {n: g.length})
      : S.seats > 1 ? T("{n} candidates for {s} seats; the {s} with the most votes are elected.", {n: g.length, s: S.seats}) : T("{n} candidates printed on the official list.", {n: g.length});
    entry("list", T("Who is on the ballot"), {tags: [T("Official record")], lede,
      body: (li ? `<ul class="nbl-list">${li}</ul>` : "") + `<p>${T("The names are as the official list prints them{np}. Order on the ballot is the list's own where it gives one.", {np: partyCol ? "" : T("; a nonpartisan office: no party is printed beside the names")})}</p>`,
      src: ls.agency || ls.title ? [[`${esc(ls.agency || "")}${ls.agency && ls.title ? ": " : ""}${esc(ls.title || "")}`, "", T("the official list of candidates on the ballot")]] : [],
      rel: ["count", "primaries", "sources"], site: L.hasFull("arena") ? [[T("The candidates' cards on the full page"), L.full("arena")]] : []});
  }
  /* ---- the rest: the full page's own sections */
  if (S.primaries && fill.primaries) entry("primaries", T("How they got here"), {tags: [T("Official record")], lede: T("The primaries whose certified results are on record here, and who advanced from each."),
    body: () => fill.primaries() || "", rel: ["list"], site: L.hasFull("primaries") ? siteFull("primaries") : []});
  if (S.past && fill.past) entry("past", T("This seat before"), {tags: [T("Official record")], lede: T("The general elections of 2020, 2022 and 2024 for the same seat, from the official results, each contest with its source."),
    body: () => fill.past(), cant: [T("Where a district's lines were different then, the figures are for the seat as it was drawn then.")], rel: ["count"], site: (L.past() ? [[T("Past results, place by place"), L.past()]] : []).concat(L.hasFull("past") ? siteFull("past") : [])});
  if (S.wlh && fill.wlh) entry("wlh", T("Who lives here"), {tags: [T("Official record")], lede: T("The Census Bureau's figures for the place that votes in this race: the 2020 count and the American Community Survey's estimates, with their margins."),
    body: () => fill.wlh(), cant: [T("Figures about a place say nothing about any one person in it, or about how anyone voted.")], rel: ["count"], site: L.hasFull("wlh") ? siteFull("wlh") : []});
  if (S.ads && fill.ads) entry("ads", T("Ads and the money behind them"), {tags: [T("Official record"), T("Links only")], lede: T("What each campaign reported spending on ads, by kind, what others spent for and against them, and the ads themselves where Google's public ad library holds them. Nothing is copied."),
    body: () => fill.ads() || "", rel: ["list", "sources"], site: L.hasFull("ads") ? siteFull("ads") : []});
  if (fill.hasSources && fill.hasSources()) entry("sources", T("Where this comes from"), {tags: [T("Official record")], lede: T("Every source this race's page reads, kind by kind, each named with its address and the date it was read."),
    body: () => fill.sources() || "", rel: ["method/sources", "method/labels"], site: L.hasFull("sources") ? siteFull("sources") : []});
  /* ---- method, in plain words (the Method page and the questions page say the same) */
  entry("method/labels", T("What the labels mean"), {tags: [T("How we work")], lede: T("Every figure carries a label saying what kind of fact it is."),
    body: `<dl class="nbdl"><dt>${esc(T("Official record"))}</dt><dd>${esc(T("Copied from a government's own record, unchanged."))}</dd><dt>${esc(T("Official count"))}</dt><dd>${esc(T("A government's count of votes. Until it is certified it is also marked:"))}</dd>
<dt>${esc(T("As reported, not final"))}</dt><dd>${esc(T("The latest figures the state has posted; they can still change."))}</dd><dt>${esc(T("As certified"))}</dt><dd>${esc(T("The result the state certified: final."))}</dd>
<dt>${esc(T("Analysis"))}</dt><dd>${esc(T("Worked out by this site from official figures by a stated rule (a forecast, a comparison). The working is always shown, and it never replaces the record."))}</dd><dt>${esc(T("Links only"))}</dt><dd>${esc(T("Other people's words, linked and never copied."))}</dd></dl>`,
    rel: ["method/calls", "method/sources"]});
  entry("method/calls", T("Why this site never calls a race"), {tags: [T("How we work")], lede: T("News organizations call races; states decide them. This site shows the count, and the calls as links."),
    body: `<p>${esc(T("A call is a judgment made before every ballot is counted. The site reports who called a race and when, as links to their own pages, and marks a result final only when the state certifies it. It never says a race is projected, called or won, and \"Elected\" appears only once the result is certified."))}</p>`, rel: ["method/labels", "coverage/calls"]});
  entry("method/forecasts", T("How the forecasts work"), {tags: [T("How we work"), T("Analysis")], lede: T("A forecast is a computer model's estimate, labelled Analysis wherever it appears; the official count decides."),
    body: `<p>${esc(T("Before Election Day the model starts from how each place voted in past official elections, moves that by the year's mood from polls by members of the American Association for Public Opinion Research's Transparency Initiative only, and adds who holds the seat. Census figures and campaign money are not used. Thousands of simulated elections give each candidate a chance of coming first and a likely range for their share of the vote: the middle 80 percent of the simulations, so about one race in five lands outside it."))}</p>
<p>${esc(T("Chances are never 0 or 100 before the count is certified. No forecast is made for a race with one name for each seat. Every run is kept with its method version, the fingerprints of its inputs and its random seed, so it can be made again exactly, and the track record shows how the same model did on past elections."))}</p>`, rel: ["method/labels", "forecast"]});
  entry("method/polls", T("Which polls count"), {tags: [T("How we work")], lede: T("We count only polls from members of the American Association for Public Opinion Research's Transparency Initiative, each checked against the pollster's own release."),
    body: `<p>${esc(T("The latest poll from each of up to five members counts, and our average takes the ten most recent, with the arithmetic shown. Other published polls are shown apart, checked the same way, and never averaged. A poll is a measure of opinion when it was taken, with a margin of error, not a forecast."))}</p>`, rel: ["polls", "method/forecasts"]});
  entry("method/sources", T("Where the facts come from"), {tags: [T("How we work")], lede: T("Official sources first, each named with its address and the date it was read."),
    body: `<p>${esc(T("Who is running comes only from each state's official candidate list. Counts come from each state's own election office, with the time on every number. Bills and votes come from Congress's and the states' records; campaign money from the Federal Election Commission and each state's agency. A secondary source is used only where no official one exists, and it is always labelled."))}</p>`, rel: ["method/labels", "sources"]});
  return E;
}
const otherPolls = k => !k ? "" : k === 1 ? T("; one other published poll is shown apart and never averaged") : T("; {k} other published polls are shown apart and never averaged", {k});
function trackSentence(t, S){
  const what = {mnstatewide: T("{state}'s statewide races of 2022 and 2024", {state: S.state}), mnusrep: T("{state}'s U.S. House races of 2022 and 2024", {state: S.state}),
    ussen: T("the U.S. Senate races of 2022 and 2024 in every state but Minnesota"), usrep: T("the 2024 U.S. House races of the states whose lines did not change in 2024"),
    governor: T("the governors' races of 2022 and 2024")}[t.what] || T("the other statewide offices of 2022 and 2024");
  const inside = t.unit === "cand" ? T("the actual vote fell inside its 80 percent range for {h80} of {n} candidates and inside its 95 percent range for {h95}", {h80: num(t.h80), n: num(t.n), h95: num(t.h95)})
    : T("the actual Democratic share fell inside its 80 percent range in {h80} of {n} races and inside its 95 percent range in {h95}", {h80: num(t.h80), n: num(t.n), h95: num(t.h95)});
  return T("Tested on {what} ({races} races), the candidate it favoured won {fav} of {races}; {inside}; its vote shares were off by {mae} points on average.{thin}", {what, races: num(t.races), fav: num(t.fav), inside, mae: t.mae, thin: t.thin ? " " + T("That is a thin record.") : ""});
}

/* the rail: the site's zones, this state and this race stacked under On The Ballot */
function zones(S, L){
  const info = M.info || {}, st = String(S.st || ""), lc = st.toLowerCase();
  const raceEntries = ENTRIES.filter(pth => has(S, pth));
  const statePage = info.statePage || (lc ? `../${lc}/` : "");
  return [
    {id: "ballot", t: T("On The Ballot"), links: [["../", T("Every level")], ["../us/", T("Congress")], ["../states/", T("Every state")], ["../forecasts/", T("Forecasts")], ["../faq/", T("Questions about voting")]],
     kids: [{t: S.state || st, href: statePage, kids: [{t: S.title, href: "#race=" + S.id, entries: raceEntries}]}]},
    {id: "night", t: T("Election Night"), links: [["../../night/", T("Election Night")], ["../../night/us/", T("The country")]].concat(info.nightState ? [[info.nightState, S.state]] : [],
      [["../../night/feed/", T("The feed")], ["../../night/forecasts/", T("Forecasts")], ["../../night/past/", T("Past results")]])},
    {id: "forecasts", t: T("Forecasts"), links: [["../forecasts/", T("Every race with a forecast")], ["../../night/forecasts/record/", T("The forecast record")]]},
    {id: "past", t: T("Past results"), links: [["../../night/past/", T("Past results")]].concat(L.past() ? [[L.past(), T("{state}, 2024", {state: S.state})]] : [])},
    {id: "record", t: T("The record"), links: [["../../us/", T("Congress")]].concat(info.rec ? [[info.rec, T("{state}'s Legislature", {state: S.state})]] : [])},
    {id: "method", t: T("Method"), links: [["../../method/", T("How we work")]], entries: METHOD},
    {id: "access", t: T("Reading & access"), links: [["../../access/", T("Reading & access")]]}
  ];
}

/* the panel */
function panel(){
  if (NB.el) return NB.el;
  const el = D.createElement("div");
  el.className = "nbk"; el.id = "tca-nbk"; el.setAttribute("role", "dialog"); el.setAttribute("aria-modal", "true"); el.setAttribute("aria-label", T("Notebook")); el.hidden = true;
  el.innerHTML = `<div class="nbk-top"><button type="button" class="nbk-back"><span aria-hidden="true">&larr;</span> <span class="nbk-backt">${esc(T("Back to the race"))}</span></button>
<p class="nbk-kick">${esc(T("Notebook"))}</p><button type="button" class="nbk-x" aria-label="${esc(T("Close the notebook"))}">&times;</button></div>
<div class="nbk-grid">
<button class="nbk-open" type="button" aria-controls="nbk-rail" aria-expanded="false"><span aria-hidden="true">&#9776;</span> ${esc(T("Contents"))}</button>
<aside class="nbk-rail" id="nbk-rail" aria-label="${esc(T("Notebook contents"))}"><div class="nbk-railin">
<div class="nbk-railtop"><label class="nbk-find"><span class="nbk-vh">${esc(T("Find a page"))}</span><input type="search" placeholder="${esc(T("Find a page"))}" autocomplete="off"></label>
<button class="nbk-close" type="button" aria-label="${esc(T("Close the contents"))}">&times;</button></div>
<div class="nbk-pins" hidden><p class="nbr-h">${esc(T("Pinned"))}</p><ul></ul></div>
<ul class="nbr"></ul><p class="nbk-none" hidden>${esc(T("No page matches."))}</p></div></aside>
<main class="nbk-page" id="nbk-page"><div class="nbk-art"></div>
<nav class="nbk-pn" aria-label="${esc(T("Previous and next page"))}"><a class="nbk-prev" href="#"></a><a class="nbk-next" href="#"></a></nav>
<div class="nbk-tools"><button type="button" class="nbk-pin" aria-pressed="false">${esc(T("Pin this page"))}</button></div></main>
<aside class="nbk-toc" aria-label="${esc(T("On this page"))}"><p class="nbr-h">${esc(T("On this page"))}</p><ul></ul></aside>
</div>`;
  D.body.appendChild(el);
  NB.el = el;
  $(".nbk-x", el).addEventListener("click", () => NB.close());
  $(".nbk-back", el).addEventListener("click", () => NB.close());
  el.addEventListener("keydown", e => { if (e.key === "Escape") { e.preventDefault(); NB.close(); } });
  /* the rail's groups */
  el.addEventListener("click", e => {
    const g = e.target.closest(".nbr-g"); if (g) { g.setAttribute("aria-expanded", g.getAttribute("aria-expanded") === "true" ? "false" : "true"); return; }
    const a = e.target.closest("a[data-p]"); if (a) { e.preventDefault(); NB.go(a.dataset.p); closeRail(false); return; }
    const t = e.target.closest(".nbk-toc a[data-to]"); if (t) { e.preventDefault(); const h = D.getElementById(t.dataset.to); if (h) { h.scrollIntoView({block: "start"}); h.tabIndex = -1; h.focus({preventScroll: true}); } return; }
    if (e.target.closest(".nbk-pin")) { togglePin(); return; }
    if (e.target.closest(".nbk-open")) { openRail(); return; }
    if (e.target.closest(".nbk-close")) { closeRail(true); return; }
    const l = e.target.closest("a[href]"); if (l && !l.dataset.p && !l.dataset.nbk && l.getAttribute("href").startsWith("#race=") && !l.target) { /* a link back to the race page itself */ e.preventDefault(); NB.close(); }
  });
  $(".nbk-find input", el).addEventListener("input", find);
  return el;
}
let scrim = null;
function openRail(){ const el = NB.el, rail = $(".nbk-rail", el); rail.classList.add("is-open"); $(".nbk-open", el).setAttribute("aria-expanded", "true");
  scrim = D.createElement("div"); scrim.className = "nbk-scrim"; scrim.addEventListener("click", () => closeRail(true)); el.appendChild(scrim); ($(".nbr-e[aria-current]", el) || $(".nbk-find input", el)).focus(); }
function closeRail(ret){ const el = NB.el; if (!el) return; const rail = $(".nbk-rail", el); if (!rail.classList.contains("is-open")) return; rail.classList.remove("is-open"); $(".nbk-open", el).setAttribute("aria-expanded", "false");
  if (scrim) { scrim.remove(); scrim = null; } if (ret) $(".nbk-open", el).focus(); }
function find(){
  const el = NB.el, q = $(".nbk-find input", el).value.trim().toLowerCase(); let hits = 0;
  $$(".nbr-e", el).forEach(l => { const ok = !q || l.textContent.toLowerCase().includes(q); l.closest("li").hidden = !ok; if (ok) hits++; });
  $$(".nbr li", el).forEach(li => { if (li.querySelector(":scope > .nbr-g")) li.hidden = q ? !$$(".nbr-e", li).some(x => !x.closest("li").hidden) : false; });
  if (q) $$(".nbr-g", el).forEach(b => b.setAttribute("aria-expanded", "true")); else expandTo(NB.path);
  $(".nbk-none", el).hidden = !q || hits > 0;
}
function railHTML(S, L, E){
  const Z = zones(S, L);
  const link = (href, text, p) => `<li><a class="nbr-e${p ? "" : " is-site"}" href="${esc(href)}"${p ? ` data-p="${esc(p)}"` : ""}>${esc(text)}${p ? "" : `<span class="nbr-o" aria-hidden="true">&nearr;</span>`}</a></li>`;
  const tree = (node, depth) => {
    const links = (node.links || []).map(([h, t]) => link(h, t)).join("");
    const ents = (node.entries || []).filter(pth => E[pth]).map(pth => `<li><a class="nbr-e" href="#race=${esc(S.id)}&nb=${esc(pth)}" data-p="${esc(pth)}">${E[pth].t}</a></li>`).join("");
    const kids = (node.kids || []).map(k => `<li><button class="nbr-g" type="button" aria-expanded="true"><span class="nbr-c" aria-hidden="true"></span>${esc(k.t)}</button><ul class="nbr-l" data-lvl="${depth + 1}">${k.href ? link(k.href, T("The page itself")) : ""}${tree(k, depth + 1)}</ul></li>`).join("");
    return links + ents + kids;
  };
  return Z.map((z, i) => `<li class="nbr-z" data-z="${esc(z.id)}" style="--zi:${i}"><button class="nbr-g nbr-zb" type="button" aria-expanded="${z.id === "ballot" ? "true" : "false"}"><span class="nbr-tab" aria-hidden="true"></span><span class="nbr-c" aria-hidden="true"></span>${esc(z.t)}</button><ul class="nbr-l" data-lvl="1">${tree(z, 1)}</ul></li>`).join("");
}
function expandTo(path){
  const el = NB.el; if (!el) return;
  const cur = $(`.nbr-e[data-p="${String(path).replace(/["\\]/g, "")}"]`, el);
  $$(".nbr-e", el).forEach(l => { if (l.dataset.p === path) l.setAttribute("aria-current", "page"); else l.removeAttribute("aria-current"); });
  if (cur) { let n = cur.parentElement; while (n && n !== el) { if (n.classList && n.classList.contains("nbr-l") && n.previousElementSibling && n.previousElementSibling.classList.contains("nbr-g")) n.previousElementSibling.setAttribute("aria-expanded", "true"); n = n.parentElement; } }
}
function pinsDraw(E){
  const el = NB.el, box = $(".nbk-pins", el), listP = kept.get(PINS, []).filter(x => x && x.k);
  box.hidden = !listP.length;
  $("ul", box).innerHTML = listP.map(x => { const mine = x.k.startsWith(M.race + "|") || METHOD.includes(x.k); const pth = METHOD.includes(x.k) ? x.k : x.k.split("|")[1];
    return mine && E[pth] ? `<li><a href="#race=${esc(M.race)}&nb=${esc(pth)}" data-p="${esc(pth)}">${E[pth].t}</a></li>` : `<li><a href="${esc(x.h || "#")}">${esc(x.t || x.k)}<span class="nbr-o" aria-hidden="true">&nearr;</span></a></li>`; }).join("");
  const b = $(".nbk-pin", el), on = listP.some(x => x.k === entryKey(NB.path));
  b.setAttribute("aria-pressed", on ? "true" : "false"); b.textContent = on ? T("Pinned: tap to unpin") : T("Pin this page");
}
function togglePin(){
  const E = NB.E || {}, k = entryKey(NB.path), listP = kept.get(PINS, []).filter(x => x && x.k), i = listP.findIndex(x => x.k === k);
  if (i >= 0) listP.splice(i, 1); else listP.unshift({k, t: (E[NB.path] || {}).t ? stripTags((E[NB.path] || {}).t) : NB.path, h: location.pathname + "#race=" + M.race + "&nb=" + NB.path});
  kept.set(PINS, listP.slice(0, 30)); pinsDraw(E);
}
const stripTags = s => String(s).replace(/<[^>]*>/g, "");
function tocDraw(art){
  const el = NB.el, ul = $(".nbk-toc ul", el); ul.innerHTML = "";
  const hs = $$("h3", art).filter(h => !h.closest(".nbe-mine"));
  hs.forEach((h, i) => { if (!h.id) h.id = "nbk-s" + i; const li = D.createElement("li"); li.innerHTML = `<a href="#" data-to="${esc(h.id)}">${esc(h.textContent)}</a>`; ul.appendChild(li); });
  $(".nbk-toc", el).hidden = !hs.length;
}
function prevNext(order, path, E){
  const el = NB.el, i = order.indexOf(path), p = order[i - 1], n = order[i + 1], pa = $(".nbk-prev", el), na = $(".nbk-next", el);
  pa.hidden = !p; na.hidden = !n;
  if (p) { pa.href = `#race=${M.race}&nb=${p}`; pa.dataset.p = p; pa.innerHTML = `<small>${esc(T("Previous"))}</small>${E[p].t}`; }
  if (n) { na.href = `#race=${M.race}&nb=${n}`; na.dataset.p = n; na.innerHTML = `<small>${esc(T("Next"))}</small>${E[n].t}`; }
}
/* one entry as an article; the body comes in as HTML, as a Promise of HTML, or by filling a box */
function articleHTML(path, e, S, E, withNote){
  const crumb = METHOD.includes(path) ? [T("Method")] : [T("On The Ballot"), S.state, stripTags(S.title)];
  const tags = (e.tags || []).filter(Boolean).map(t => tag(t)).join("");
  const src = (e.src || []).filter(x => x && (x[0] || x[1])).length ? `<h3 id="nbk-src">${esc(T("Where it comes from"))}</h3><ul class="nbsrc">${e.src.filter(x => x && (x[0] || x[1])).map(([n, u, w]) => `<li>${u ? (String(u).startsWith("#") ? `<a href="${esc(u)}">${n}</a>` : ext(u, n)) : n}${w ? `<span>${w}</span>` : ""}</li>`).join("")}</ul>` : "";
  const cant = (e.cant || []).length ? `<h3 id="nbk-cant">${esc(T("What it cannot tell you"))}</h3><ul class="nbcant">${e.cant.map(c => `<li>${c}</li>`).join("")}</ul>` : "";
  const rel = (e.rel || []).filter(r => E[r]);
  const relH = rel.length ? `<h3 id="nbk-rel">${esc(T("Related pages"))}</h3><ul class="nbrel">${rel.map(r => `<li><a href="#race=${esc(S.id)}&nb=${esc(r)}" data-p="${esc(r)}">${E[r].t}</a></li>`).join("")}</ul>` : "";
  const site = (e.site || []).filter(x => x && x[1]).length ? `<h3 id="nbk-site">${esc(T("On the site"))}</h3><ul class="nbrel">${e.site.filter(x => x && x[1]).map(([n, u]) => `<li><a href="${esc(u)}">${n}</a></li>`).join("")}</ul>` : "";
  const note = withNote ? `<div class="nbe-mine"><h3>${esc(T("Your margin note"))}</h3><p class="nbe-small">${esc(T("Kept on this device only; nothing is sent."))}</p><textarea class="nbe-note" rows="3" aria-label="${esc(T("Your margin note for this page"))}" data-k="${esc(entryKey(path))}"></textarea></div>` : "";
  return `<article class="nbe" data-p="${esc(path)}" aria-labelledby="nbk-h"><p class="nbe-crumb">${crumb.map(esc).join(' <span aria-hidden="true">&rsaquo;</span> ')}</p><h2 id="nbk-h" tabindex="-1">${e.t}</h2><div class="nbe-tags">${tags}</div>
<div class="nbe-short"><span class="nbe-k">${esc(T("The short of it"))}</span><p>${e.lede || ""}</p></div>
<div class="nbe-body" data-body><p class="nbk-wait">${esc(T("Loading…"))}</p></div>${src}${cant}${relH}${site}${note}</article>`;
}
function bodyInto(box, e){
  const fail = () => { box.innerHTML = `<p class="fnote">${esc(T("This could not be loaded just now. Check your connection, then open the page again."))}</p>`; };
  try {
    if (e.mount) { box.innerHTML = `<p class="nbk-wait">${esc(T("Loading…"))}</p>`; return Promise.resolve(e.mount(box)).then(() => box.innerHTML, fail); }
    const b = typeof e.body === "function" ? e.body() : e.body;
    return Promise.resolve(b).then(h => { box.innerHTML = h || `<p class="fnote">${esc(T("Nothing more to show here."))}</p>`; return box.innerHTML; }, fail);
  } catch (x) { fail(); return Promise.resolve(""); }
}
NB.open = function(path, o = {}){
  if (!M.S) { if (M.ready) M.ready.then(() => NB.open(path, o)); return; }
  const S = M.S, L = M.L, E = NB.E = entries(S, L);
  if (!E[path]) path = E.count ? "count" : "list";
  const el = panel(), first = el.hidden;
  if (first) {
    NB.from = o.from || D.activeElement; NB.anchor = o.anchor || "";
    el.hidden = false; el.classList.toggle("is-in", !calm()); H.classList.add("nbk-on");
    NB.inerted = []; try { for (const c of Array.from(D.body.children)) if (c !== el && !c.hasAttribute("inert") && c.tagName !== "SCRIPT" && c.tagName !== "STYLE") { c.setAttribute("inert", ""); NB.inerted.push(c); } } catch (e) {}
    $(".nbr", el).innerHTML = railHTML(S, L, E);
    if (!W.__nbTitle) W.__nbTitle = D.title;
  }
  if (o.push) { setParam("nb", path, true, {nb: path}); NB.pushed = true; }
  else if (o.push === false && param(hashOf(), "nb") !== path) setParam("nb", path, false);
  NB.draw(path, E, S, first);
};
NB.go = function(path){ if (!NB.el || NB.el.hidden) return NB.open(path, {push: true}); setParam("nb", path, false, history.state); NB.draw(path, NB.E, M.S, false); };
NB.draw = function(path, E, S, first){
  const el = NB.el; NB.path = path;
  const art = $(".nbk-art", el); art.innerHTML = articleHTML(path, E[path], S, E, true);
  const a = $(".nbe", art); if (!calm()) { a.classList.add("is-in"); }
  bodyInto($("[data-body]", art), E[path]).then(() => { tocDraw(a); try { const p = P(); if (p && p.dom) p.dom(a); } catch (e) {} });
  const order = ENTRIES.filter(pth => E[pth]).concat(METHOD);
  prevNext(order, path, E); pinsDraw(E); expandTo(path); tocDraw(a);
  const ta = $(".nbe-note", art); const notes = kept.get(NOTES, {}); ta.value = notes[entryKey(path)] || "";
  let tm = 0; ta.addEventListener("input", () => { clearTimeout(tm); tm = setTimeout(() => { const n = kept.get(NOTES, {}); if (ta.value.trim()) n[entryKey(path)] = ta.value.slice(0, 4000); else delete n[entryKey(path)]; kept.set(NOTES, n); }, 300); });
  D.title = stripTags(E[path].t) + " · " + (W.__nbTitle || D.title);
  $(".nbk-page", el).scrollTop = 0; el.scrollTop = 0;
  if (!first || !NB.crossing) { try { $("#nbk-h", art).focus({preventScroll: true}); } catch (e) {} }
};
NB.close = function(o = {}){
  const el = NB.el; if (!el || el.hidden) return;
  closeRail(false);
  el.hidden = true; el.classList.remove("is-in"); H.classList.remove("nbk-on");
  for (const c of NB.inerted) { try { c.removeAttribute("inert"); } catch (e) {} } NB.inerted = [];
  if (W.__nbTitle) D.title = W.__nbTitle;
  if (!o.fromHistory) { if (NB.pushed && history.state && history.state.nb) { NB.pushed = false; history.back(); } else setParam("nb", null, false); }
  NB.pushed = false;
  const back = NB.anchor ? D.getElementById(NB.anchor) : null, f = (back && back.isConnected) ? back : (NB.from && NB.from.isConnected ? NB.from : null);
  if (f) { try { if (!f.matches("a,button,input,textarea,select,[tabindex]")) f.tabIndex = -1; f.focus({preventScroll: true}); if (back) back.scrollIntoView({block: "center", behavior: calm() ? "auto" : "smooth"}); } catch (e) {} }
  /* a view that knows how to bring the reader's row back (reveal(root, anchor)) does so */
  try { const def = REG.get(M.view), root = M.host && M.host.firstElementChild; if (def && typeof def.reveal === "function" && root && NB.anchor) def.reveal(root, NB.anchor); } catch (e) {}
  NB.from = null; NB.anchor = "";
};
/* VIEWS.entry(path): the entry's HTML (no margin note), for a view that shows notes beside itself */
function entryHTML(path){
  if (!M.S) return (M.ready || Promise.resolve()).then(() => M.S ? entryHTML(path) : "");
  const E = entries(M.S, M.L); if (!E[path]) return Promise.resolve("");
  const tmp = D.createElement("div"); tmp.innerHTML = articleHTML(path, E[path], M.S, E, false);
  return bodyInto($("[data-body]", tmp), E[path]).then(() => tmp.innerHTML);
}

/* ================================ the crossing into the notebook ================================ */
const GATE = {p: null};
function gateLoad(){
  const p = P(); if (!p || !p.gate) return Promise.resolve(null);
  if (!GATE.p) GATE.p = import(new URL(p.gate, location.href).href).then(() => W.__nbGate || null).catch(() => null);
  return GATE.p;
}
function canCross(){
  if (calm()) return false;
  try { if (navigator.connection && navigator.connection.saveData) return false; } catch (e) {}
  try { const c = D.createElement("canvas"); const g = W.WebGL2RenderingContext ? c.getContext("webgl2") : null; if (!g) return false; const x = g.getExtension("WEBGL_lose_context"); if (x) x.loseContext(); } catch (e) { return false; }
  return true;
}
const seen = () => { try { return !!sessionStorage.getItem(SEEN); } catch (e) { return false; } };
function warm(){ if (!seen() && canCross()) gateLoad().then(g => { try { if (g && g.warm) g.warm(); } catch (e) {} }); }
/* a notebook link followed: the panel opens under the scene the first time this visit (the scene's own files are fetched on the first hover) */
function follow(path, a){
  const title = stripTags(((NB.E || (M.S ? entries(M.S, M.L) : {}))[path] || {}).t || T("Notebook"));
  const o = {push: true, from: a, anchor: a && a.dataset.anchor || ""};
  const p = P();
  if (seen() || !p || !p.gate || !canCross()) { NB.open(path, o); return; }
  NB.crossing = true;
  NB.open(path, o);
  soft(gateLoad(), 2500).then(g => {
    if (!g || !NB.el || NB.el.hidden) { NB.crossing = false; try { $("#nbk-h", NB.el).focus({preventScroll: true}); } catch (e) {} return; }
    return Promise.resolve(g.play({path: longPath(path), title, force: false})).catch(() => null).then(() => { NB.crossing = false; try { if (NB.el && !NB.el.hidden) $("#nbk-h", NB.el).focus({preventScroll: true}); } catch (e) {} });
  });
}

/* ================================ the page's events ================================ */
D.addEventListener("click", e => {
  if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
  const b = e.target.closest("#vwbar .vwbtn"); if (b) { choose(b.dataset.view, {push: false}); return; }
  const a = e.target.closest("a[href]"); if (!a) return;
  if (a.dataset.nbk) { e.preventDefault(); follow(a.dataset.nbk, a); return; }
  const href = a.getAttribute("href") || "";
  if (!href.startsWith("#race=") || raceOf(href.slice(1)) !== M.race) return;
  const v = param(href.slice(1), "view"), go = param(href.slice(1), "go"), tab = param(href.slice(1), "tab");
  if (v && !go && !tab && !param(href.slice(1), "nb") && !param(href.slice(1), "chart")) { e.preventDefault(); choose(decodeURIComponent(v), {push: true}); }
});
D.addEventListener("pointerover", e => { const a = e.target.closest ? e.target.closest("a[data-nbk]") : null; if (a) warm(); }, {passive: true, capture: true});
D.addEventListener("focusin", e => { const a = e.target.closest ? e.target.closest("a[data-nbk]") : null; if (a) warm(); }, {capture: true});
let lastHash = location.href;
function onAddress(){
  if (location.href === lastHash) return; lastHash = location.href;
  const h = hashOf();
  if (!M.host || !M.host.isConnected || raceOf(h) !== M.race) { if (NB.el && !NB.el.hidden) NB.close({fromHistory: true}); return; }      /* another page: the page's own router draws it, and racePage mounts again; the notebook goes with the race */
  const nb = param(h, "nb");
  if (nb) { if (!NB.el || NB.el.hidden || NB.path !== nb) NB.open(nb, {push: false}); } else if (NB.el && !NB.el.hidden) NB.close({fromHistory: true});
  const want = wanted(); if (want !== M.view) show(want);
  const go = param(h, "go"); if (go && M.S) goFull(decodeURIComponent(go));
}
addEventListener("hashchange", onAddress);
addEventListener("popstate", onAddress);
addEventListener("pageshow", e => { if (e.persisted && NB.el && !NB.el.hidden && !param(hashOf(), "nb")) NB.close({fromHistory: true}); });

W.VIEWS = {add, T, esc, num, pct, when, day, chance, partyVar, calm, level, entry: entryHTML, mount, show: id => choose(id, {push: false}), current: () => M.view, S: () => M.S,
  ready: () => M.ready || Promise.resolve(), notebook: {open: (path, o) => NB.open(path, Object.assign({push: true}, o || {})), close: () => NB.close(), path: () => NB.el && !NB.el.hidden ? NB.path : ""}, views: list, v: 1};
if (D.readyState === "loading") D.addEventListener("DOMContentLoaded", () => mount(), {once: true}); else mount();
})();

/* ======== front ======== */
/* The Front Page: a race read like a newspaper (view "front", the default way every race page is read).

   Ported from the sandbox layout (sandbox_src/layouts/front.py, John, 2026-11-10) to a renderer that draws ANY race in the
   reader's browser from S (views_src/SPEC.md, version 1): a headline, a standfirst, the big figures as a typographic
   lead, "In brief", and short sections in plain words, each claim carrying a small numbered mark whose note (in the right
   margin on a wide page, under the paragraph on a phone) previews the notebook entry and opens it. A "how much to read"
   control (the gist, the story, everything) starts where the reader's level says and remembers the reader's own choice.

   The words are written by rules that stay true for every kind of race: before any count (the list as filed, the holder,
   polls, a forecast), while counting, with every precinct reporting, as certified; several seats; nonpartisan offices;
   retention votes; unopposed races; a race with no candidate. "Leads" only from reported figures; never "won" or
   "projected"; calls only from coverage, linked, with "The Civic Archive does not call races."; a forecast labelled
   Analysis with its 80 percent range and its track record. Every sentence goes through VIEWS.T. */
(function () {
  "use strict";
  if (typeof VIEWS === "undefined" || !VIEWS || typeof VIEWS.add !== "function") return;

  /* ---------- the core's helpers, each with a plain fallback so a missing one never prints "undefined" ---------- */
  const has = (o, k) => o && typeof o[k] === "function";
  const esc = s => has(VIEWS, "esc") ? VIEWS.esc(s == null ? "" : s) :
    String(s == null ? "" : s).replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"})[c]);
  const num = n => has(VIEWS, "num") ? VIEWS.num(n) : String(Math.round(+n || 0)).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  const pct = (x, d) => has(VIEWS, "pct") ? VIEWS.pct(x, d == null ? 1 : d) : (+x || 0).toFixed(d == null ? 1 : d) + "%";
  let ST = "";                                    /* the race's state, for times in its own zone */
  const when = iso => iso ? (has(VIEWS, "when") ? VIEWS.when(iso, ST) : String(iso)) : "";
  const day = iso => iso ? (has(VIEWS, "day") ? VIEWS.day(iso, ST) : String(iso).slice(0, 10)) : "";
  const chance = p => has(VIEWS, "chance") ? VIEWS.chance(p) : (p > .99 ? "more than 99 in 100" : p < .01 ? "less than 1 in 100" : "about " + Math.round(100 * p) + " in 100");
  const calm = () => { try { return has(VIEWS, "calm") ? !!VIEWS.calm() : true; } catch (e) { return true; } };
  const pts = x => (Math.round(x * 10) / 10).toFixed(1);

  /* every sentence goes through the language layer. Its values are text (names, offices, figures already written as
     words); the HTML around a sentence is added here. The layer may escape what it returns (the page's TH does) or not
     (a plain {key} substitution): one probe says which, and the sentence is made HTML-safe either way. */
  let TESC = null;
  function tx(msg, vars) {
    if (TESC === null) { try { TESC = /&lt;/.test(String(VIEWS.T("{x}", {x: "<"}))); } catch (e) { TESC = false; } }
    let out;
    try { out = String(VIEWS.T(msg, vars || {})); } catch (e) { out = String(msg).replace(/\{(\w+)\}/g, (m, k) => vars && vars[k] != null ? String(vars[k]) : m); }
    return TESC ? out : esc(out);
  }
  /* the colour for a party code: the page's own variable, or "" for none (a nonpartisan office never gets one) */
  function partyColour(code) {
    if (!code || !has(VIEWS, "partyVar")) return "";
    let v = ""; try { v = String(VIEWS.partyVar(code) || ""); } catch (e) { v = ""; }
    if (!v) return "";
    const m = /^(?:var\()?(--p[A-Za-z])\)?$/.exec(v);
    if (m) return "var(" + m[1] + "," + (PARTY_FALLBACK[m[1]] || "#646B76") + ")";
    return v;
  }
  const PARTY_FALLBACK = {"--pD": "#2E5BE6", "--pR": "#D8453A", "--pL": "#B07C00", "--pG": "#2F8F4E", "--pI": "#6E62A8", "--pO": "#646B76", "--pW": "#7C828C"};
  /* an agency's name mid-sentence: "the North Carolina State Board of Elections" (the record writes some with "the" and some without) */
  const theA = s => (/^the\s/i.test(String(s || "")) ? String(s) : "the " + String(s || "")).replace(/^the\s+the\s/i, "the ");
  const sameA = (a, b) => String(a || "").replace(/^the\s+/i, "").toLowerCase() === String(b || "").replace(/^the\s+/i, "").toLowerCase();
  const NEUTRAL = ["var(--fp-oth)", "var(--fp-oth2)", "var(--fp-oth3)", "var(--fp-oth4)"];
  const SMALL = ["no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"];
  const wn = n => (n >= 0 && n <= 10) ? tx(SMALL[n]) : num(n);           // a small count in words, as a newspaper writes it
  const cap = s => s ? s.charAt(0).toUpperCase() + s.slice(1) : s;
  const GONE = /withdr|disqualif|remov|died|deceased|declin|ineligib|dropped/i;   // an "out" note that means no longer running
  const YESNO = /^(yes|no|s[ií]|non?)(?![a-z])/i;      /* a retention count's rows: "Yes", "No", "Yes - retain" */
  const SUFFIX = /^(jr\.?|sr\.?|ii|iii|iv|v|esq\.?|ph\.?d\.?|m\.?d\.?)$/i;
  const andList = items => items.length < 2 ? (items[0] || "") : items.slice(0, -1).join(", ") + " " + tx("and") + " " + items[items.length - 1];

  /* ---------- what the race is: every rule below reads this, never S directly ---------- */
  function facts(S) {
    ST = S.st || "";
    const F = {S};
    F.kind = S.kind || "contest";
    F.seats = Math.max(1, Math.floor(+S.seats) || 1);
    F.partisan = !!S.partisan;
    F.special = !!S.special;
    F.office = S.office || S.title || "";
    F.level = S.level || "";
    F.title = S.title || S.office || "";
    F.place = S.place || S.state || "";
    F.state = S.state || "";
    F.date = S.date || "";
    F.agency = (S.list_source && S.list_source.agency) || "";
    F.listTitle = (S.list_source && S.list_source.title) || "";
    F.src = S.source || {};
    F.who = F.src.office || F.agency || "";
    F.list = Array.isArray(S.list) ? S.list.filter(c => c && c.n) : [];
    F.gone = F.list.filter(c => c.out && GONE.test(String(c.out)));
    F.names = F.list.filter(c => !(c.out && GONE.test(String(c.out))));      // on the ballot now
    F.K = F.names.length;
    const C = S.count && typeof S.count === "object" ? S.count : null;
    F.C = C;
    F.cands = C && Array.isArray(C.cands) ? C.cands.filter(c => c && c.n).slice().sort((a, b) => (+b.votes || 0) - (+a.votes || 0)) : [];
    F.rep = C && Array.isArray(C.reporting) && C.reporting.length >= 2 && +C.reporting[1] > 0 ? [+C.reporting[0] || 0, +C.reporting[1]] : null;
    const summed = F.cands.reduce((s, c) => s + (+c.votes || 0), 0);
    F.total = C ? (+C.total > 0 ? +C.total : summed) : 0;
    F.counted = !!C && F.total > 0 && F.cands.length > 0;
    F.full = !!C && (F.rep ? F.rep[0] >= F.rep[1] : C.status === "done");
    F.final = !!C && !!C.final;
    F.phase = !C ? "before" : !F.counted ? "zero" : F.final ? "final" : F.full ? "full" : "counting";
    F.at = C ? when(C.at) : "";
    F.yesno = F.kind === "retention" && F.cands.length >= 2 && F.cands.every(c => YESNO.test(String(c.n).trim()));
    F.holder = S.holder && S.holder.n ? S.holder : null;
    F.holderOn = !!F.holder && (!!F.holder.running || F.names.some(c => same(c.n, F.holder.n)) );
    /* names: the family name in headlines, the whole name where two share it */
    const all = F.list.map(c => c.n).concat(F.cands.map(c => c.n));
    const seen = {};
    all.forEach(n => { seen[family(n)] = seen[family(n)] || new Set(); seen[family(n)].add(n); });
    F.short = n => { if (!n) return ""; if (YESNO.test(String(n).trim())) return cap(String(n).trim()); const f = family(n); return seen[f] && seen[f].size > 1 ? n : f; };
    /* party words and colours per name: the count's row first, then the list's */
    const byName = {};
    F.list.forEach(c => { byName[c.n] = {party: F.partisan ? (c.party || "") : "", code: F.partisan ? (c.code || "") : ""}; });
    F.cands.forEach(c => { byName[c.n] = {party: F.partisan ? (c.party || (byName[c.n] || {}).party || "") : "", code: F.partisan ? (c.code || (byName[c.n] || {}).code || "") : ""}; });
    F.party = n => (byName[n] || {}).party || "";
    const tints = {};
    let k = 0;
    const order = F.cands.map(c => c.n).concat(F.list.map(c => c.n)).filter((n, i, a) => a.indexOf(n) === i);
    order.forEach(n => {
      const col = F.partisan ? partyColour((byName[n] || {}).code) : "";
      tints[n] = col || NEUTRAL[k++ % NEUTRAL.length];
    });
    if (F.yesno) F.cands.forEach(c => { tints[c.n] = /^(yes|s[ií])(?![a-z])/i.test(c.n.trim()) ? "var(--fp-yes)" : "var(--fp-no)"; });
    F.tint = n => tints[n] || NEUTRAL[0];
    /* the first two, and the seats' worth, of the count */
    F.lead = F.cands[0] || null;
    F.second = F.cands[1] || null;
    F.margin = F.lead && F.second ? (+F.lead.share || 0) - (+F.second.share || 0) : 0;
    F.gapv = F.lead && F.second ? (+F.lead.votes || 0) - (+F.second.votes || 0) : 0;
    F.tie = !!(F.lead && F.second && (+F.lead.votes || 0) === (+F.second.votes || 0));
    F.top = F.cands.slice(0, F.seats);
    F.next = F.cands[F.seats] || null;
    /* the other blocks, only when they carry something */
    const K = S.counties;
    F.counties = K && Array.isArray(K.top) && K.top.length ? K : null;
    const FC = S.forecast;
    F.fc = FC && Array.isArray(FC.top) && FC.top.length && F.kind !== "unopposed" ? FC : null;
    F.fcBy = {};
    if (F.fc) FC.top.forEach(c => { if (c && c.n) F.fcBy[c.n] = c; });
    F.fcFav = F.fc ? FC.top.slice().sort((a, b) => (+b.ch || 0) - (+a.ch || 0))[0] : null;
    F.track = F.fc && FC.track && typeof FC.track === "object" ? FC.track : null;
    F.hist = F.fc && Array.isArray(FC.hist) ? FC.hist.filter(h => h && h.c) : [];
    const P = S.polls;
    F.polls = P && (Array.isArray(P.newest) && P.newest.length || +P.n > 0) ? P : null;
    const V = S.coverage;
    F.cov = V && typeof V === "object" ? V : null;
    F.calls = F.cov && Array.isArray(V.calls) ? V.calls.filter(c => c && c.o && c.n).slice().sort((a, b) => String(a.t || "").localeCompare(String(b.t || ""))) : [];
    F.said = F.cov && Array.isArray(V.said) ? V.said.filter(s => s && s.n && Array.isArray(s.s) && s.s.length) : [];
    F.news = F.cov && V.news && typeof V.news === "object" ? V.news : {};
    F.nn = F.cov && Array.isArray(V.n) ? V.n : [0, 0, 0, 0];
    F.stories = +F.nn[0] || Object.keys(F.news).reduce((s, t) => s + (+(F.news[t] || {}).n || 0), 0);
    F.flags = {splits: !!S.splits, past: !!S.past, wlh: !!S.wlh, ads: !!S.ads, primaries: !!S.primaries};
    F.read = S.read ? day(S.read) : "";
    F.past = (() => { if (!F.date) return false; const d = new Date(F.date + "T23:59:59"); return !isNaN(d) && d < new Date(); })();
    return F;
  }
  function family(n) {
    const w = String(n || "").replace(/[,]/g, " ").trim().split(/\s+/).filter(Boolean);
    while (w.length > 1 && SUFFIX.test(w[w.length - 1])) w.pop();
    return w[w.length - 1] || String(n || "");
  }
  function same(a, b) { return String(a || "").toLowerCase().replace(/[^a-z]/g, "") === String(b || "").toLowerCase().replace(/[^a-z]/g, ""); }

  /* ---------- how far the count has come, as words ---------- */
  function progress(F) {
    if (F.phase === "final") return tx("as certified");
    if (F.full) return tx("with every precinct reporting");
    if (F.rep) return tx("with {x} of {y} precincts reporting", {x: num(F.rep[0]), y: num(F.rep[1])});
    return tx("as the count stands");
  }
  function marginWords(F, bare) {
    if (F.tie) return "";
    if (bare) return F.margin < 1 ? tx("{v} votes", {v: num(F.gapv)}) : tx("{m} points", {m: pts(F.margin)});
    return F.margin < 1 ? tx("by {v} votes", {v: num(F.gapv)}) : tx("by {m} points", {m: pts(F.margin)});
  }
  /* "seat" for a legislature, a board or a council; "office" for a judge, a prosecutor, a statewide or county officer */
  function seatWord(F) {
    const lv = F.level || "";
    if (lv === "court" || lv === "statewide") return tx("office");
    if (lv === "county" && !/commission|board|council|supervisor/i.test(F.office)) return tx("office");
    return tx("seat");
  }
  function partyOf(F, n) { const p = F.party(n); return p ? tx("{name}, the {party} candidate,", {name: n, party: p}) : esc(n) + ","; }
  function callsShort(F) {
    const by = {};
    F.calls.forEach(c => { (by[c.n] = by[c.n] || []).push(c); });
    return Object.keys(by).map(n => {
      const cs = by[n];
      return tx("{outlets} called the race for {name} on {day}", {outlets: andList(cs.map(c => c.o)), name: F.short(n), day: day(cs[0].t)});
    }).join("; ");
  }

  /* ---------- the kicker, the headline, the standfirst and the brief: one set of rules for every race ---------- */
  function words(F) {
    const W = {kicker: "", h1: "", stand: [], brief: []};
    const sh = F.short, N = F.seats, K = F.K;
    const seatsOf = tx("the {n} seats", {n: wn(N)});
    const list = F.names.map(c => F.partisan && F.party(c.n) ? tx("{name} ({party})", {name: c.n, party: F.party(c.n)}) : esc(c.n));
    /* the kicker names the phase */
    W.kicker = F.phase === "before" ? (F.past ? tx("No count on file here yet") : tx("Before Election Day")) :
      F.phase === "zero" ? tx("Counting has not started") : F.phase === "counting" ? tx("The count, as reported") :
      F.phase === "full" ? tx("Every precinct reporting, not final") : tx("As certified");
    if (F.special) W.kicker += " · " + tx("Special election");
    if (F.phase === "before" || F.phase === "zero") {
      /* ---- the list as filed */
      if (F.kind === "none" || K === 0) {
        W.h1 = tx("No candidate on the ballot for {office}", {office: F.office});
        W.stand.push(tx("The official list from {agency} names no one for this office in {place}.", {agency: theA(F.agency || F.who), place: F.place}));
        if (F.gone.length) W.stand.push(tx("{names} {verb} no longer on it: {notes}.", {names: andList(F.gone.map(c => c.n)), verb: F.gone.length > 1 ? tx("are") : tx("is"), notes: andList(F.gone.map(c => String(c.out)))}));
        W.stand.push(tx("What happens to an office no one filed for is for the state and the county to say; this page shows the list as published."));
      } else if (F.kind === "retention") {
        const n = F.names[0].n;
        W.h1 = tx("Yes or no: a vote on keeping {name} in office", {name: n});
        W.stand.push(tx("{name} is the only name. The ballot asks whether they should be retained as {office}, and voters mark yes or no.", {name: n, office: F.office}));
      } else if (F.kind === "unopposed" || K === 1) {
        if (K === 1) {
          W.h1 = tx("{name} is unopposed for {office}", {name: sh(F.names[0].n), office: F.office});
          W.stand.push(tx("The official list from {agency} carries one name for this office: {full}{party}.", {agency: theA(F.agency || F.who), full: F.names[0].n, party: F.party(F.names[0].n) ? ", " + F.party(F.names[0].n) : ""}));
        } else {
          W.h1 = tx("Unopposed: {names} for {seats} on {office}", {names: andList(F.names.map(c => sh(c.n))), seats: seatsOf, office: F.office});
          W.stand.push(tx("The official list from {agency} carries {k} names for {n} seats, so no one on it has an opponent: {list}.", {agency: theA(F.agency || F.who), k: wn(K), n: wn(N), list: andList(list)}));
        }
        if (F.names[0].out && !GONE.test(String(F.names[0].out))) W.stand.push(tx("The list marks the name “{note}”.", {note: String(F.names[0].out)}));
      } else if (N > 1) {
        W.h1 = tx("{k} names on the ballot for {n} seats: {office}", {k: cap(wn(K)), n: wn(N), office: F.office});
        W.stand.push(tx("Voters choose up to {n}; the {n} with the most votes take the seats. In the order the list gives them: {list}.", {n: wn(N), list: andList(list)}));
      } else if (F.holder && F.holderOn) {
        const k = K - 1;
        W.h1 = k === 1 ? tx("{name}, who holds the {seat}, faces one challenger", {name: sh(F.holder.n), seat: seatWord(F)}) :
          tx("{name}, who holds the {seat}, faces {k} challengers", {name: sh(F.holder.n), k: wn(k), seat: seatWord(F)});
        W.stand.push(tx("{k} names are on the official list from {agency}, in this order: {list}.", {k: cap(wn(K)), agency: theA(F.agency || F.who), list: andList(list)}));
        W.saidHolder = true;
      } else if (F.holder) {
        W.h1 = seatWord(F) === tx("seat") ? tx("An open seat: {k} names on the ballot for {office}", {k: wn(K), office: F.office}) : tx("An open office: {k} names on the ballot for {office}", {k: wn(K), office: F.office});
        W.stand.push(tx("{holder}{party}, who holds the {seat} today, is not on the ballot. The official list from {agency}, in its order: {list}.", {holder: F.holder.n, party: F.partisan && F.holder.party ? ", " + F.holder.party : "", seat: seatWord(F), agency: theA(F.agency || F.who), list: andList(list)}));
      } else {
        W.h1 = tx("{k} names on the ballot for {office}", {k: cap(wn(K)), office: F.office});
        W.stand.push(tx("The official list from {agency}, in its order: {list}.", {agency: theA(F.agency || F.who), list: andList(list)}));
      }
      if (F.holder && F.holderOn && F.kind !== "none" && !(N === 1 && F.kind === "contest" && K > 1)) W.stand.push(tx("{holder} holds the {seat} today.", {holder: F.holder.n, seat: seatWord(F)}));
      if (F.gone.length && !(F.kind === "none" || K === 0)) W.stand.push(tx("Also on the list, marked “{note}”: {names}.", {note: String(F.gone[0].out), names: andList(F.gone.map(c => c.n))}));
      if (F.phase === "zero") W.stand.push(tx("As of {at}, {who} had reported no votes.", {at: F.at, who: F.who}));
      else if (F.date) W.stand.push(F.past ? tx("Election Day was {date}; no count has been read for this race yet.", {date: day(F.date)}) : tx("Election Day is {date}.", {date: day(F.date)}));
    } else {
      /* ---- a count */
      const prog = progress(F);
      const L = F.lead, S2 = F.second;
      const certified = F.phase === "final";
      if (F.yesno) {
        const yes = F.cands.find(c => /^(yes|s[ií])(?![a-z])/i.test(c.n.trim())) || L, no = F.cands.find(c => c !== yes) || S2;
        const name = F.names[0] ? F.names[0].n : F.title, short = F.names[0] ? sh(F.names[0].n) : F.title;
        const ahead = (+yes.votes || 0) >= (+no.votes || 0) ? tx("Yes") : tx("No");
        W.h1 = certified ? tx("Certified: {yes} voted yes on keeping {name} in office", {yes: pct(yes.share), name: short})
          : F.tie ? tx("Yes and no are tied on keeping {name} in office, {prog}", {name: short, prog})
          : tx("{ahead} leads on keeping {name} in office, {y} to {n}, {prog}", {ahead, name: short, y: pct(yes.share), n: pct(no.share), prog});
        W.stand.push(tx("{as} {who}: {yv} yes votes ({ys}) and {nv} no votes ({ns}) on whether {name} should be retained as {office}.", {as: certified ? tx("As certified by") : tx("As reported by"), who: F.who, yv: num(yes.votes), ys: pct(yes.share), nv: num(no.votes), ns: pct(no.share), name, office: F.office}));
      } else if (!L) {
        W.h1 = tx("{v} votes reported for {office}, {prog}", {v: num(F.total), office: F.office, prog});
        W.stand.push(tx("{as} {who}: {v} votes in this race.", {as: certified ? tx("As certified by") : tx("As reported by"), who: F.who, v: num(F.total)}));
      } else if (F.kind === "unopposed" || (F.cands.length === 1 && N === 1)) {
        W.h1 = certified ? tx("Certified: {v} votes for {name}, who had no opponent", {v: num(L.votes), name: sh(L.n)})
          : tx("Unopposed, {name} has {v} votes {prog}", {name: sh(L.n), v: num(L.votes), prog});
        W.stand.push(tx("{as} {who}: {name}, with no opponent on the ballot, has {v} votes ({s} of those cast in this race).", {as: certified ? tx("As certified by") : tx("As reported by"), who: F.who, name: L.n, v: num(L.votes), s: pct(L.share)}));
      } else if (N > 1) {
        const tops = andList(F.top.map(c => sh(c.n)));
        W.h1 = certified ? tx("{names} had the most votes for {seats}, as certified", {names: tops, seats: seatsOf})
          : F.top.length < N ? tx("{names} have the votes so far for {seats}, {prog}", {names: tops, seats: seatsOf, prog})
          : tx("{names} lead for {seats} {prog}", {names: tops, seats: seatsOf, prog});
        const rows = F.top.map(c => tx("{name}, {v} votes ({s})", {name: c.n, v: num(c.votes), s: pct(c.share)}));
        W.stand.push(tx("{as} {who}: the {n} with the most votes take the seats, and so far those are {rows}.", {as: certified ? tx("As certified by") : tx("As reported by"), who: F.who, n: wn(N), rows: andList(rows)}));
        if (F.next) W.stand.push(tx("Next, {name} with {v} ({s}), {gap} votes behind the last of them.", {name: F.next.n, v: num(F.next.votes), s: pct(F.next.share), gap: num((+F.top[F.top.length - 1].votes || 0) - (+F.next.votes || 0))}));
      } else {
        const mw = marginWords(F);
        W.h1 = F.tie ? tx("{a} and {b} are tied at {v} votes each, {prog}", {a: sh(L.n), b: sh(S2.n), v: num(L.votes), prog})
          : certified ? tx("{name} finished {m} ahead in the certified count", {name: sh(L.n), m: marginWords(F, true)})
          : tx("{name} leads {m} {prog}", {name: sh(L.n), m: mw, prog});
        W.stand.push(F.tie ? tx("{as} {who}: {lead} has {v1} votes ({s1}), the same number as {second}: a tie as the count stands.", {as: certified ? tx("As certified by") : tx("As reported by"), who: F.who, lead: partyOf(F, L.n), v1: num(L.votes), s1: pct(L.share), second: S2.n})
          : tx("{as} {who}: {lead} has {v1} votes ({s1}) to {second}’s {v2} ({s2}), a gap of {gap} votes.", {as: certified ? tx("As certified by") : tx("As reported by"), who: F.who, lead: partyOf(F, L.n), v1: num(L.votes), s1: pct(L.share), second: S2.n, v2: num(S2.votes), s2: pct(S2.share), gap: num(F.gapv)}));
      }
      const cs = callsShort(F);
      if (cs) W.stand.push(cs + ".");
      W.stand.push(certified ? tx("The result is final.") : tx("The count is not final until {state} certifies it.", {state: F.state || F.place}));
    }
    /* ---- in brief: the 30-second edition */
    if (F.phase === "before" || F.phase === "zero") {
      W.brief.push(W.h1 + ".");
      if (F.holder && !W.saidHolder) W.brief.push(F.holderOn ? tx("{holder} holds the {seat} today and is on the ballot.", {holder: F.holder.n, seat: seatWord(F)}) : tx("{holder} holds the {seat} today and is not on the ballot.", {holder: F.holder.n, seat: seatWord(F)}));
      if (F.polls && F.polls.newest && F.polls.newest[0]) {
        const p = F.polls.newest[0], sh2 = Object.keys(p.shares || {}).sort((a, b) => (p.shares[b] || 0) - (p.shares[a] || 0)).slice(0, 2);
        if (sh2.length) W.brief.push(tx("The newest poll we count, by {pollster} ({dates}), had {parts}. A poll measures opinion when it was taken.", {pollster: p.pollster || "", dates: pollDates(p), parts: andList(sh2.map(n => tx("{name} at {s}", {name: sh(n), s: pct(p.shares[n], 0)})))}));
      }
      if (F.fcFav) { const f = F.fcFav; W.brief.push(tx("Analysis: the site’s model gives {name} {ch}; its likely range for their share is {lo} to {hi}.", {name: sh(f.n), ch: chance(+f.ch || 0), lo: pct(f.l80), hi: pct(f.h80)})); }
      if (F.date) W.brief.push(F.past ? tx("Election Day was {date}.", {date: day(F.date)}) : tx("Election Day: {date}.", {date: day(F.date)}));
    } else {
      if (F.yesno || !F.lead) W.brief.push(W.h1 + ".");
      else if (F.kind === "unopposed" || (F.cands.length === 1 && N === 1)) W.brief.push(tx("{name}, unopposed, has {v} votes {prog}.", {name: sh(F.lead.n), v: num(F.lead.votes), prog: progress(F)}));
      else if (N > 1) W.brief.push(W.h1 + ".");
      else W.brief.push(F.tie ? W.h1 + "." : F.phase === "final" ? tx("{a} finished ahead of {b}, {s1} to {s2}, as certified.", {a: sh(F.lead.n), b: sh(F.second.n), s1: pct(F.lead.share), s2: pct(F.second.share)})
        : tx("{a} leads {b} {s1} to {s2} {prog}.", {a: sh(F.lead.n), b: sh(F.second.n), s1: pct(F.lead.share), s2: pct(F.second.share), prog: progress(F)}));
      if (F.cov) W.brief.push((callsShort(F) ? callsShort(F) + ". " : tx("No news organization’s call is on record.") + " ") + tx("The Civic Archive does not call races."));
      const f = F.lead && F.fcBy[F.lead.n];
      if (f) W.brief.push(F.full ? tx("The forecast gave {name} {ch}; their share came in {verdict}.", {name: sh(F.lead.n), ch: chance(+f.ch || 0), verdict: verdict(f, +F.lead.share || 0)})
        : tx("The forecast gave {name} {ch}; their share so far is {verdict}.", {name: sh(F.lead.n), ch: chance(+f.ch || 0), verdict: verdict(f, +F.lead.share || 0)}));
      W.brief.push(F.phase === "final" ? tx("The count is certified: the result is final.") : tx("Not final until {state} certifies the count.", {state: F.state || F.place}));
    }
    return W;
  }
  function verdict(f, share) {
    if (!f) return "";
    if (f.l80 <= share && share <= f.h80) return tx("inside the likely range");
    if (f.l95 <= share && share <= f.h95) return share > f.h80 ? tx("inside the wider range, above the likely one") : tx("inside the wider range, below the likely one");
    return share > f.h95 ? tx("above even the wider range: a miss") : tx("below even the wider range: a miss");
  }
  function pollDates(p) {
    let a = day(p.start); const b = day(p.end);
    if (a && b && a !== b) { const ya = /,\s*(\d{4})$/.exec(a), yb = /,\s*(\d{4})$/.exec(b); if (ya && yb && ya[1] === yb[1]) a = a.slice(0, ya.index); return tx("{a} to {b}", {a, b}); }
    return b || a || "";
  }

  /* ---------- the notes: a numbered mark in the text, the note beside it (or under it on a phone) ---------- */
  function noteWords(path, F) {
    const sh = F.short, L = F.lead, S2 = F.second;
    switch (path) {
      case "count": return [tx("The count: {title}", {title: F.title}), L && S2 ? tx("As reported by {who}: {a} {va} ({sa}), {b} {vb} ({sb}), {prog}.", {who: F.who, a: L.n, va: num(L.votes), sa: pct(L.share), b: S2.n, vb: num(S2.votes), sb: pct(S2.share), prog: progress(F)}) : L ? tx("As reported by {who}: {a} {va} ({sa}), {prog}.", {who: F.who, a: L.n, va: num(L.votes), sa: pct(L.share), prog: progress(F)}) : tx("Every figure of the count, as {who} posts it.", {who: F.who})];
      case "list": return [tx("Who is on the ballot"), F.K > 1 ? tx("{k} names on the official list from {agency}, in the order it gives them.", {k: num(F.K), agency: theA(F.agency || F.who)}) : F.K === 1 ? tx("One name on the official list from {agency}.", {agency: theA(F.agency || F.who)}) : tx("The official list from {agency} carries no name for this office.", {agency: theA(F.agency || F.who)})];
      case "counties": { const won = F.counties ? Object.keys(F.counties.won || {}).sort((a, b) => F.counties.won[b] - F.counties.won[a]).map(n => tx("{name} {k}", {name: sh(n), k: num(F.counties.won[n])})) : [];
        return [tx("County by county"), tx("{n} counties reported.", {n: num(F.counties ? F.counties.n : 0)}) + (won.length ? " " + tx("Most votes in a county: {won}.", {won: won.join("; ")}) : "")]; }
      case "splits": return [tx("Votes left blank and split results"), tx("How many fewer votes this race drew than the top race in each county, and the counties that chose different parties for different races. Worked out from the same county figures.")];
      case "forecast": { const f = F.fcFav; return [tx("The forecast, worked out"), f ? tx("The model’s last run gives {name} {ch}, likely {lo} to {hi} of the vote.", {name: f.n, ch: chance(+f.ch || 0), lo: pct(f.l80), hi: pct(f.h80)}) : ""]; }
      case "forecast/track": return [tx("The forecast’s track record"), trackWords(F)];
      case "forecast/how": return [tx("How the forecast is worked out"), tx("A computer model’s estimate from past election results and polls by members of AAPOR’s Transparency Initiative; every run is kept and can be made again exactly.")];
      case "forecast/runs": return [tx("Every run of the model"), F.hist.length ? tx("{n} runs, from {a} to {b}.", {n: num(F.hist.length), a: day(F.hist[0].at), b: day(F.hist[F.hist.length - 1].at)}) : ""];
      case "polls": return [tx("The polls"), F.polls ? tx("{n} polls by members of AAPOR’s Transparency Initiative are counted; {o} other published polls are shown apart.", {n: num(+F.polls.n || 0), o: num(+F.polls.other || 0)}) : ""];
      case "method/polls": return [tx("Which polls we count"), tx("We count only polls from members of the American Association for Public Opinion Research’s Transparency Initiative.")];
      case "coverage/calls": return [tx("Who called it"), F.calls.length ? callsShort(F) + "." : tx("No news organization’s call is on record.")];
      case "coverage/said": return [tx("What the candidates said"), F.said.length ? tx("Statements by {names}, each linked to its own page; nothing is copied.", {names: andList(F.said.map(s => s.n))}) : tx("No statement by a candidate is on record.")];
      case "coverage/news": return [tx("News coverage"), tx("{n} stories, each linked under its outlet’s own headline.", {n: num(F.stories)})];
      case "coverage": return [tx("Coverage"), tx("Who called it, what the candidates said and the news, as links.")];
      case "method/calls": return [tx("Why this site never calls a race"), tx("News organizations call races; states decide them. This site shows the count, and the calls as links.")];
      case "method/labels": return [tx("What the labels mean"), tx("Every figure carries a label saying what kind of fact it is.")];
      case "method/sources": return [tx("Where the facts come from"), tx("Official sources first, each named with its address and the date it was read.")];
      case "method/forecasts": return [tx("How forecasts are made"), tx("The model, its inputs and its ranges, step by step.")];
      case "past": return [tx("This seat before"), tx("How this seat voted in earlier elections, from the official results.")];
      case "wlh": return [tx("Who lives here"), tx("Who lives in {place}, from the Census Bureau’s figures.", {place: F.place})];
      case "primaries": return [tx("The primaries"), tx("How the names reached the November ballot.")];
      case "ads": return [tx("Ads"), tx("Spending on ads for and against, from official filings, with links to the ad libraries.")];
      case "sources": return [tx("Sources"), tx("Every source behind this page, with its address and the date it was read.")];
    }
    return [tx("In the notebook"), ""];
  }
  function trackWords(F) {
    const t = F.track; if (!t) return "";
    const what = {mnstatewide: tx("{state}’s statewide races of 2022 and 2024", {state: F.state}), mnusrep: tx("{state}’s U.S. House races of 2022 and 2024", {state: F.state}),
      ussen: tx("the U.S. Senate races of 2022 and 2024 in every state but Minnesota"), usrep: tx("the 2024 U.S. House races of the states whose lines did not change in 2024"),
      governor: tx("the governors’ races of 2022 and 2024")}[t.what] || tx("the other statewide offices of 2022 and 2024");
    const races = +t.races || 0, n = +t.n || races;
    const unit = t.unit === "cand" ? tx("the actual vote fell inside its 80 percent range for {h80} of {n} candidates and inside its 95 percent range for {h95}", {h80: num(+t.h80 || 0), n: num(n), h95: num(+t.h95 || 0)})
      : tx("the actual Democratic share fell inside its 80 percent range in {h80} of {n} races and inside its 95 percent range in {h95}", {h80: num(+t.h80 || 0), n: num(n), h95: num(+t.h95 || 0)});
    return tx("Its track record. Tested on {what} ({races}), the candidate it favoured won {fav} of {n}; {unit}; its vote shares were off by {mae} points on average.", {
      what, races: races === 1 ? tx("1 race") : tx("{n} races", {n: num(races)}), fav: num(+t.fav || 0), n: num(races), unit, mae: String(t.mae == null ? "" : t.mae)}) + (t.thin ? " " + tx("That is a thin record.") : "");
  }

  /* ---------- render: the page as a string ---------- */
  function render(S, L) {
    const F = facts(S), W = words(F);
    const sh = F.short, N = F.seats;
    const canNb = p => { try { return !!(L && typeof L.has === "function" && L.has(p) && typeof L.nb === "function"); } catch (e) { return false; } };
    const notes = {n: 0, pending: [], rows: 0};
    const ref = path => {
      if (!canNb(path)) return "";
      notes.n += 1; const i = notes.n; notes.pending.push([i, path]);
      return `<button type="button" class="fp-ref" id="fp-m${i}" aria-controls="fp-n${i}" aria-describedby="fp-n${i}-t"><span class="fp-sr">${tx("Note")} </span>${i}</button>`;
    };
    const row = (inner, o) => {
      o = o || {}; notes.rows += 1; const rid = "fp-r" + notes.rows;
      let margin = "";
      if (notes.pending.length) {
        margin = `<div class="fp-margin">` + notes.pending.map(([i, path]) => {
          const [t, lede] = noteWords(path, F);
          let link = ""; try { link = L.nb(path, tx("Open in the notebook"), {anchor: rid, cls: "nbl fp-nbl"}) || ""; } catch (e) { link = ""; }
          return `<aside class="fp-note" id="fp-n${i}" tabindex="-1" aria-labelledby="fp-n${i}-t"><p class="fp-note-t" id="fp-n${i}-t"><span class="fp-note-n" aria-hidden="true">${i}</span>${t}</p>${lede ? `<p class="fp-note-l">${lede}</p>` : ""}${link}</aside>`;
        }).join("") + `</div>`;
        notes.pending = [];
      }
      return `<div class="fp-row${o.cls ? " " + o.cls : ""}" id="${rid}"${o.tier ? ` data-fp-min="${o.tier}"` : ""}>${inner}${margin}</div>`;
    };
    const tag = (k, text) => `<span class="fp-tag" data-k="${k}">${text}</span>`;
    const tagCount = () => F.phase === "final" ? tag("official", tx("Certified count")) : tag("official", tx("Official count")) + tag("reported", tx("As reported, not final"));
    const sections = [];   // [id, title] for the jump strip
    const sec = (id, title, tags, body, tier) => {
      sections.push([id, title]);
      return `<section class="fp-sec" id="fp-s-${id}" data-fp-min="${tier || 2}" aria-labelledby="fp-s-${id}-h"><header class="fp-sech"><h2 id="fp-s-${id}-h" tabindex="-1">${title}</h2>${tags}</header>${body}</section>`;
    };
    const sw = n => `<span class="fp-sw" style="--fp-c:${F.tint(n)}" aria-hidden="true"></span>`;
    const partyLine = n => { const p = F.party(n); return p ? `<p class="fp-cp">${esc(p)}</p>` : ""; };
    /* the list's own order number where the list gives any (a write-in has none and shows none); a plain count otherwise */
    const anyOrder = F.list.some(c => c.order != null);
    const orderNo = (c, i) => anyOrder ? (c.order != null ? num(c.order) : "") : String(i + 1);
    const markOf = c => {
      const m = [];
      if (c.inc || (F.holder && same(c.n, F.holder.n))) m.push(seatWord(F) === tx("seat") ? tx("holds the seat") : tx("holds the office"));
      if (c.wi) m.push(tx("write-in"));
      if (c.out) m.push(esc(String(c.out)));
      return m.length ? `<span class="fp-mark">${m.join(" · ")}</span>` : "";
    };

    /* ---- the masthead */
    const dateline = [`<b>${esc(F.state || F.place)}</b>`, `<span>${esc(F.title)}</span>`];
    if (F.counted) dateline.push(`<span>${F.phase === "final" ? tx("Certified count") : tx("Count as reported {at}", {at: F.at})}</span>`);
    else if (F.date) dateline.push(`<span>${tx("Election Day {date}", {date: day(F.date)})}</span>`);
    const masthead = `<div class="fp-top"><p class="fp-kick">${W.kicker}</p>
<div class="fp-mast"><div><p class="fp-plate">${tx("The Front Page")}</p><p class="fp-date">${dateline.join("")}</p></div>
<div class="fp-lenbox"><fieldset class="fp-len"><legend>${tx("How much to read")}</legend>
<label><input type="radio" name="fp-len" value="1"><span>${tx("The gist")}<small data-w="1"></small></span></label>
<label><input type="radio" name="fp-len" value="2"><span>${tx("The story")}<small data-w="2"></small></span></label>
<label><input type="radio" name="fp-len" value="3"><span>${tx("Everything")}<small data-w="3"></small></span></label>
</fieldset><p class="fp-lenhint" aria-live="polite"></p></div></div></div>`;

    /* ---- the lead figure */
    const legendBits = () => {
      const b = [];
      if (F.rep) b.push(`<span>${F.full ? tx("every precinct reporting") : tx("{x} of {y} precincts reporting", {x: num(F.rep[0]), y: num(F.rep[1])})}</span>`);
      if (F.counted) b.push(`<span>${tx("{v} votes in all", {v: num(F.total)})}</span>`);
      b.push(F.phase === "final" ? tag("official", tx("As certified")) : tag("reported", tx("As reported, not final")));
      return b.join("");
    };
    const barOf = cands => {
      const label = tx("Share of the vote: {parts}", {parts: cands.map(c => tx("{name} {s}", {name: c.n, s: pct(c.share)})).join(", ")});
      return `<div class="fp-bar" role="img" aria-label="${label}">${cands.map(c => `<span style="flex-basis:${(+c.share || 0).toFixed(2)}%;--fp-c:${F.tint(c.n)}"></span>`).join("")}</div>`;
    };
    const big = (c, cls) => `<div class="fp-cand${cls || ""}" style="--fp-c:${F.tint(c.n)}"><p class="fp-cn">${sw(c.n)}${esc(c.n)}</p>${partyLine(c.n)}
<p class="fp-big"><span class="fp-num" data-v="${+c.share || 0}" data-f="p">${pct(c.share)}</span></p><p class="fp-votes"><span class="fp-num" data-v="${+c.votes || 0}" data-f="i">${num(c.votes)}</span> ${tx("votes")}</p></div>`;
    let lead = "";
    if (F.counted && F.lead && (F.yesno || (N === 1 && F.second && F.kind !== "unopposed"))) {
      const a = F.yesno ? (F.cands.find(c => /^(yes|s[ií])(?![a-z])/i.test(c.n.trim())) || F.lead) : F.lead;
      const b = F.yesno ? F.cands.find(c => c !== a) : F.second;
      const others = F.cands.filter(c => c !== a && c !== b);
      const m = Math.abs((+a.share || 0) - (+b.share || 0)), gv = Math.abs((+a.votes || 0) - (+b.votes || 0));
      lead = `<figure class="fp-lead" aria-labelledby="fp-lead-cap"><div class="fp-tally">${big(a)}
<div class="fp-gapb"><p class="fp-gapn"><span class="fp-num" data-v="${m.toFixed(2)}" data-f="d">${pts(m)}</span></p><p class="fp-gapl">${F.tie ? tx("tied") : tx("points apart")}</p><p class="fp-gapv">${tx("{v} votes", {v: num(gv)})}</p></div>${big(b, " is-second")}</div>
${barOf(F.yesno ? [a, b] : F.cands)}<figcaption id="fp-lead-cap" class="fp-leg">${others.map(c => `<span><i style="--fp-c:${F.tint(c.n)}" aria-hidden="true"></i>${tx("{name}{party}: {v} votes ({s})", {name: c.n, party: F.party(c.n) ? ", " + F.party(c.n) : "", v: num(c.votes), s: pct(c.share)})}</span>`).join("")}${legendBits()}</figcaption></figure>`;
    } else if (F.counted && F.lead && N > 1) {
      const shown = F.cands.length <= 6 ? F.cands : F.cands.slice(0, N + 2);
      const rows = shown.map((c, i) => `<li class="fp-srow${i < N ? " is-in" : ""}" style="--fp-c:${F.tint(c.n)}"><span class="fp-sn">${sw(c.n)}${esc(c.n)}${F.party(c.n) ? `<small>${esc(F.party(c.n))}</small>` : ""}</span><span class="fp-ss"><span class="fp-num" data-v="${+c.share || 0}" data-f="p">${pct(c.share)}</span></span><span class="fp-sv">${tx("{v} votes", {v: num(c.votes)})}</span></li>` + (i === N - 1 && shown.length > N ? `<li class="fp-seatline" aria-hidden="true"><span>${tx("the {n} seats", {n: wn(N)})}</span></li>` : "")).join("");
      lead = `<figure class="fp-lead" aria-labelledby="fp-lead-cap"><ol class="fp-seats" aria-label="${tx("The count, largest first; the {n} with the most votes take the seats", {n: wn(N)})}">${rows}</ol>${shown.length < F.cands.length ? `<p class="fp-cap">${tx("and {k} more, listed under The count", {k: num(F.cands.length - shown.length)})}</p>` : ""}
${barOf(F.cands)}<figcaption id="fp-lead-cap" class="fp-leg">${legendBits()}</figcaption></figure>`;
    } else if (F.counted && F.lead) {
      lead = `<figure class="fp-lead" aria-labelledby="fp-lead-cap"><div class="fp-tally is-one">${big(F.lead)}<div class="fp-onebox"><p class="fp-gapl">${F.kind === "unopposed" ? tx("no opponent on the ballot") : tx("the only name counted")}</p></div></div>
${barOf(F.cands)}<figcaption id="fp-lead-cap" class="fp-leg">${legendBits()}</figcaption></figure>`;
    } else if (F.counted) {
      lead = `<figure class="fp-lead" aria-labelledby="fp-lead-cap"><div class="fp-tally is-one"><div class="fp-cand"><p class="fp-big">${num(F.total)}</p><p class="fp-votes">${tx("votes in this race")}</p></div></div><figcaption id="fp-lead-cap" class="fp-leg">${legendBits()}</figcaption></figure>`;
    } else {
      /* before a count: the field, as filed */
      let cards;
      if (F.kind === "retention" && F.names[0]) {
        cards = `<li class="fp-fc is-wide"><span class="fp-fn">${esc(F.names[0].n)}</span><span class="fp-fq">${tx("Shall {name} be retained in office?", {name: F.names[0].n})}</span><span class="fp-ovals"><span><i aria-hidden="true"></i>${tx("Yes")}</span><span><i aria-hidden="true"></i>${tx("No")}</span></span></li>`;
      } else if (!F.names.length) {
        cards = `<li class="fp-fc is-wide is-empty"><span class="fp-fn">${tx("No candidate")}</span><span class="fp-fq">${tx("The official list carries no name for this office.")}</span></li>`;
      } else {
        cards = F.names.map((c, i) => `<li class="fp-fc" style="--fp-c:${F.tint(c.n)}"><span class="fp-fo" aria-hidden="true">${orderNo(c, i)}</span><span class="fp-fn">${F.partisan ? sw(c.n) : ""}${esc(c.n)}</span>${F.party(c.n) ? `<span class="fp-fp">${esc(F.party(c.n))}</span>` : ""}${markOf(c)}</li>`).join("");
      }
      const bits = [];
      if (F.names.length) bits.push(`<span>${N > 1 ? tx("vote for up to {n}", {n: wn(N)}) : F.kind === "retention" ? tx("yes or no") : tx("vote for one")}</span>`);
      if (F.phase === "zero" && F.rep) bits.push(`<span>${tx("{x} of {y} precincts reporting", {x: num(F.rep[0]), y: num(F.rep[1])})}</span>`);
      bits.push(tag("official", tx("Official list")));
      lead = `<figure class="fp-lead fp-field" aria-labelledby="fp-lead-cap"><ol class="fp-fcs" aria-label="${tx("The ballot, as the official list gives it")}">${cards}</ol><figcaption id="fp-lead-cap" class="fp-leg">${bits.join("")}</figcaption></figure>`;
    }

    /* ---- in brief */
    const brief = `<aside class="fp-brief" aria-labelledby="fp-brief-h"><h2 id="fp-brief-h">${tx("In brief")}</h2><ul>${W.brief.map(b => `<li>${b}</li>`).join("")}</ul></aside>`;

    /* ---- sections */
    const parts = [];
    const others = F.cands.length > 2 ? F.cands.slice(N === 1 ? 2 : N + 1) : [];
    if (F.counted) {
      let p1;
      const L1 = F.lead, S2 = F.second;
      if (F.yesno) {
        const a = F.cands.find(c => /^(yes|s[ií])(?![a-z])/i.test(c.n.trim())) || L1, b = F.cands.find(c => c !== a) || S2;
        p1 = tx("{prog}, {yv} votes ({ys}) say yes to keeping {name} in office as {office} and {nv} ({ns}) say no, of the {t} cast on the question.", {prog: cap(progress(F)), yv: num(a.votes), ys: pct(a.share), name: F.names[0] ? F.names[0].n : F.title, office: F.office, nv: num(b.votes), ns: pct(b.share), t: num(F.total)});
      } else if (N > 1) {
        p1 = tx("{prog}, the {n} with the most votes are {rows}, of the {t} cast in this race.", {prog: cap(progress(F)), n: wn(N), rows: andList(F.top.map(c => tx("{name}{party} with {v} ({s})", {name: c.n, party: F.party(c.n) ? ", " + F.party(c.n) + "," : "", v: num(c.votes), s: pct(c.share)}))), t: num(F.total)});
        if (F.next) p1 += " " + tx("Next comes {name} with {v} ({s}), {gap} votes behind the last of them.", {name: F.next.n, v: num(F.next.votes), s: pct(F.next.share), gap: num((+F.top[F.top.length - 1].votes || 0) - (+F.next.votes || 0))});
      } else if (S2 && F.kind !== "unopposed") {
        p1 = tx("{prog}, {lead} has {v1} votes: {s1} of the {t} cast in this race. {second} has {v2}, or {s2}.", {prog: cap(progress(F)), lead: partyOf(F, L1.n), v1: num(L1.votes), s1: pct(L1.share), t: num(F.total), second: partyOf(F, S2.n), v2: num(S2.votes), s2: pct(S2.share)})
          + " " + (F.tie ? tx("They are tied.") : tx("The gap between them is {gap} votes, {m} points of the vote.", {gap: num(F.gapv), m: pts(F.margin)}));
      } else {
        p1 = tx("{prog}, {lead} has {v1} votes, {s1} of the {t} cast in this race.", {prog: cap(progress(F)), lead: partyOf(F, L1.n), v1: num(L1.votes), s1: pct(L1.share), t: num(F.total)});
      }
      let p2 = F.K ? (N > 1 ? tx("{k} names were printed on the ballot for these {n} seats.", {k: cap(wn(F.K)), n: wn(N)}) : F.yesno ? tx("One name was printed on the ballot, with a yes-or-no question.") : tx("{k} names were printed on the ballot for this seat.", {k: cap(wn(F.K))})) : "";
      if (others.length && !F.yesno) p2 += " " + tx("The other {k}: {list}.", {k: wn(others.length), list: others.map(c => tx("{name}{party}, {v} ({s})", {name: c.n, party: F.party(c.n) ? ", " + F.party(c.n) : "", v: num(c.votes), s: pct(c.share)})).join("; ")});
      if (F.gone.length) p2 += " " + tx("The list marks {names} “{note}”.", {names: andList(F.gone.map(c => c.n)), note: String(F.gone[0].out)});
      let p3 = "";
      if (F.C.county_sum != null && +F.C.county_sum > 0) {
        const g = F.total - (+F.C.county_sum);
        p3 = g === 0 ? tx("The county figures in the same reading add up to the total exactly.") : tx("The county figures in the same reading add up to {sum} votes, {d} {fm} than the total; the site shows each as the office posts it and adjusts neither.", {sum: num(F.C.county_sum), d: num(Math.abs(g)), fm: g > 0 ? tx("fewer") : tx("more")});
      }
      if (F.phase !== "final") p3 += (p3 ? " " : "") + tx("Until the result is certified, every figure on this page can still change.");
      const table = F.cands.length > 2 || N > 1 ? `<div class="fp-tw" tabindex="0"><table class="fp-t"><caption>${tx("Every name in the count, largest first")}</caption><thead><tr><th scope="col">${tx("Name")}</th>${F.partisan ? `<th scope="col">${tx("Party")}</th>` : ""}<th scope="col" class="n">${tx("Votes")}</th><th scope="col" class="n">${tx("Share")}</th></tr></thead><tbody>${F.cands.map(c => `<tr><th scope="row">${esc(c.n)}</th>${F.partisan ? `<td>${esc(F.party(c.n))}</td>` : ""}<td class="n">${num(c.votes)}</td><td class="n">${pct(c.share)}</td></tr>`).join("")}</tbody><tfoot><tr><th scope="row">${tx("All")}</th>${F.partisan ? "<td></td>" : ""}<td class="n">${num(F.total)}</td><td class="n">100%</td></tr></tfoot></table></div>` : "";
      parts.push(sec("count", tx("The count"), tagCount(),
        row(`<p class="fp-drop">${p1}${ref("count")}</p>`) + (p2 ? row(`<p>${p2}${ref("list")}</p>`) : "") + (p3 ? row(`<p>${p3}</p>`, {tier: 3}) : "") + (table ? row(table, {tier: 3}) : "")));
    } else {
      /* the list as filed, the main section before a count */
      const lrows = F.list.map((c, i) => `<tr${c.out && GONE.test(String(c.out)) ? ' class="is-gone"' : ""}><td class="n">${orderNo(c, i)}</td><th scope="row">${esc(c.n)}</th>${F.partisan ? `<td>${esc(F.party(c.n))}</td>` : ""}<td>${markOf(c)}</td></tr>`).join("");
      const ltable = F.list.length ? `<div class="fp-tw" tabindex="0"><table class="fp-t"><caption>${tx("The official list, in its order")}</caption><thead><tr><th scope="col" class="n">#</th><th scope="col">${tx("Name")}</th>${F.partisan ? `<th scope="col">${tx("Party")}</th>` : ""}<th scope="col">${tx("Notes")}</th></tr></thead><tbody>${lrows}</tbody></table></div>` : "";
      let lp = F.K ? (N > 1 ? tx("{k} names are on the official list for these {n} seats; voters choose up to {n}, and the {n} with the most votes take them.", {k: cap(wn(F.K)), n: wn(N)}) : F.kind === "retention" ? tx("One name is on the official list, with a yes-or-no question: whether {name} should be retained as {office}.", {name: F.names[0].n, office: F.office}) : tx("{k} names are on the official list for this seat.", {k: cap(wn(F.K))})) : tx("The official list carries no name for this office.");
      lp += " " + (F.listTitle ? tx("The list is {agency}’s “{title}”; names are as it prints them.", {agency: theA(F.agency || F.who), title: F.listTitle}) : tx("The list is {agency}’s; names are as it prints them.", {agency: theA(F.agency || F.who)}));
      if (!F.partisan && F.K) lp += " " + tx("This is a nonpartisan office: no party is printed beside a name.");
      const hp = F.holder ? (F.holderOn ? tx("{holder}{party} holds the {seat} today and is on the ballot.", {holder: F.holder.n, party: F.partisan && F.holder.party ? ", " + F.holder.party + "," : "", seat: seatWord(F)}) : tx("{holder}{party} holds the {seat} today and is not on the ballot.", {holder: F.holder.n, party: F.partisan && F.holder.party ? ", " + F.holder.party + "," : "", seat: seatWord(F)})) : "";
      const wi = F.names.filter(c => c.wi);
      const wp = wi.length ? tx("{names}: a declared write-in, whose name is not printed on the ballot but whose votes are counted when written in.", {names: andList(wi.map(c => c.n))}) : "";
      parts.push(sec("list", tx("Who is on the ballot"), tag("official", tx("Official list")),
        row(`<p class="fp-drop">${lp}${ref("list")}</p>`) + (hp ? row(`<p>${hp}</p>`) : "") + (wp ? row(`<p>${wp}</p>`, {tier: 3}) : "") + (ltable ? row(ltable, {tier: F.K > 2 ? 2 : 3}) : "")
        + (F.flags.primaries && canNb("primaries") ? row(`<p>${tx("How these names reached the ballot is in the notebook.")}${ref("primaries")}</p>`, {tier: 3}) : "")));
    }

    /* ---- where the votes came from */
    if (F.counted && F.counties && F.lead) {
      const K = F.counties, topc = K.top, topSum = topc.reduce((s, c) => s + (+c.total || 0), 0);
      const won = Object.keys(K.won || {}).sort((a, b) => K.won[b] - K.won[a]);
      const leadTop = topc.filter(c => c.lead === F.lead.n).length;
      const segs = topc.map(c => { const w = topSum ? 100 * (+c.total || 0) / topSum : 0; const short = esc(String(c.name || "").replace(/ (County|Parish)$/, ""));
        return `<span${w >= 11 && w < 18 ? ' class="is-mid"' : ""} style="flex-basis:${w.toFixed(2)}%;--fp-c:${F.tint(c.lead)}">${w >= 11 ? `<b>${short}</b>` : ""}</span>`; }).join("");
      const stripLabel = tx("The {k} counties with the most votes, each sized by its votes and shaded by the name with the most there: {list}", {k: num(topc.length), list: topc.map(c => tx("{county} {v}, {name} {s}", {county: c.name, v: num(c.total), name: sh(c.lead), s: pct((c.shares || {})[c.lead] || 0)})).join("; ")});
      const clist = topc.map(c => `<li><span><i style="--fp-c:${F.tint(c.lead)}" aria-hidden="true"></i>${esc(c.name)}</span><span>${num(c.total)} · ${esc(sh(c.lead))} ${pct((c.shares || {})[c.lead] || 0)}${c.done === false ? `<small> · ${tx("still counting")}</small>` : ""}</span></li>`).join("");
      const three = topc.slice(0, 3).map(c => tx("{county} ({v} votes; {name} {s})", {county: c.name, v: num(c.total), name: sh(c.lead), s: pct((c.shares || {})[c.lead] || 0)})).join("; ");
      const p1 = tx("{n} counties reported.", {n: num(K.n || topc.length)}) + (won.length ? " " + tx("The name with the most votes in a county: {won}.", {won: won.map(n => tx("{name} in {k}", {name: sh(n), k: num(K.won[n])})).join("; ")}) : "")
        + " " + tx("A map of counties and the whole count can look different because counties differ so much in size: the {k} counties with the most votes cast {sum} of the {t} votes, {share}, and {name} had the most votes in {w} of those {k}.", {k: num(topc.length), sum: num(topSum), t: num(F.total), share: pct(F.total ? 100 * topSum / F.total : 0), name: sh(F.lead.n), w: num(leadTop)})
        + (K.all_done === false ? " " + tx("Some counties are still counting.") : "");
      parts.push(sec("counties", tx("Where the votes came from"), tagCount(),
        row(`<p>${p1}${ref("counties")}</p>`)
        + row(`<figure class="fp-csf"><div class="fp-cs" role="img" aria-label="${stripLabel}">${segs}</div><figcaption class="fp-cap">${tx("The {k} counties with the most votes, each as wide as its share of their votes and shaded by the name with the most votes there. Every vote counts the same in this race; the biggest counties are shown because that is where most of the votes are.", {k: num(topc.length)})}</figcaption></figure>`)
        + row(`<p>${tx("The three biggest: {three}.", {three})}</p>`)
        + row(`<ul class="fp-clist" aria-label="${tx("The {k} counties with the most votes: votes cast, and the share of the name with the most", {k: num(topc.length)})}">${clist}</ul>`, {tier: 3})
        + row(`<p>${tx("Which counties a name led says nothing about the margin: the whole count decides.")}${F.flags.splits ? " " + tx("How many fewer votes the races below this one drew in each county, and which counties chose different parties for different races, are worked out from the same county figures.") + ref("splits") : ""}</p>`, {tier: 3})));
    }

    /* ---- the forecast (Analysis) */
    if (F.fc) {
      const FC = F.fc, top = FC.top.slice().sort((a, b) => (+b.ch || 0) - (+a.ch || 0)), fav = top[0], sec2 = top[1];
      const after = F.counted && !!F.lead;
      const share = n => { const c = F.cands.find(x => x.n === n); return c ? +c.share || 0 : null; };
      const vals = top.slice(0, 2).map(c => [+c.l95 || 0, +c.h95 || 0, after && share(c.n) != null ? share(c.n) : null]).flat().filter(v => v != null);
      let lo = Math.floor(Math.min.apply(null, vals) / 5) * 5, hi = Math.ceil(Math.max.apply(null, vals) / 5) * 5;
      if (!isFinite(lo) || !isFinite(hi)) { lo = 0; hi = 100; }
      const span = (hi - lo) || 1, x = v => 100 * (v - lo) / span;
      const ticks = []; for (let v = lo; v <= hi; v += 5) ticks.push(v);
      const rrow = c => { const a = after ? share(c.n) : null; const xa = a == null ? null : x(a);
        return `<div class="fp-rrow" style="--fp-c:${F.tint(c.n)}"><p class="fp-rname">${sw(c.n)}${esc(c.n)}<span class="fp-rch">${chance(+c.ch || 0)}</span></p><div class="fp-track"><div class="fp-grid" aria-hidden="true">${ticks.map(v => `<i style="left:${x(v).toFixed(2)}%"></i>`).join("")}</div>
<i class="fp-b95" style="left:${x(+c.l95 || 0).toFixed(2)}%;width:${(x(+c.h95 || 0) - x(+c.l95 || 0)).toFixed(2)}%"></i><i class="fp-b80" style="left:${x(+c.l80 || 0).toFixed(2)}%;width:${(x(+c.h80 || 0) - x(+c.l80 || 0)).toFixed(2)}%"></i><i class="fp-md" style="left:${x(+c.md || 0).toFixed(2)}%"></i>${xa == null ? "" : `<i class="fp-act" style="left:${xa.toFixed(2)}%"></i><span class="fp-actl${xa > 82 ? " is-right" : xa < 12 ? " is-left" : ""}" style="left:${xa.toFixed(2)}%">${tx("Count {s}", {s: pct(a)})}</span>`}</div></div>`; };
      const rngLabel = top.slice(0, 2).map(c => tx("{name}: likely {l80} to {h80}, wider range {l95} to {h95}, middle {md}", {name: c.n, l80: pct(c.l80), h80: pct(c.h80), l95: pct(c.l95), h95: pct(c.h95), md: pct(c.md)}) + (after && share(c.n) != null ? ", " + tx("the count {s}", {s: pct(share(c.n))}) : "")).join("; ");
      const rng = `<figure class="fp-rngf"><div class="fp-rng" role="img" aria-label="${after ? tx("The forecast against the count.") : tx("The forecast’s ranges.")} ${rngLabel}">${top.slice(0, 2).map(rrow).join("")}<div class="fp-axis" aria-hidden="true">${ticks.map((v, i) => `<span class="${i === 0 ? "is-first" : i === ticks.length - 1 ? "is-last" : ""}" style="left:${x(v).toFixed(2)}%">${v}%</span>`).join("")}</div></div>
<p class="fp-rleg"><span><i class="k95"></i>${tx("95 in 100 runs")}</span><span><i class="k80"></i>${tx("80 in 100 (likely)")}</span><span><i class="kmd"></i>${tx("the middle estimate")}</span>${after ? `<span><i class="kact"></i>${tx("the count")}</span>` : ""}</p>
<figcaption class="fp-cap">${after ? tx("Each name’s share of the vote, as the model’s last run saw it, with the count laid over it.") : tx("Each name’s share of the vote as the model’s latest run sees it: the likely range, the wider range and the middle estimate.")}</figcaption></figure>`;
      const p1 = (after ? tx("The site’s model ran for the last time before Election Day on {day}.", {day: day(FC.at)}) : tx("The site’s model last ran on {day}.", {day: day(FC.at)}))
        + " " + (sec2 ? tx("It {gives} {a} a chance of {ca} and {b} {cb}.", {gives: after ? tx("gave") : tx("gives"), a: fav.n, ca: chance(+fav.ch || 0), b: sec2.n, cb: chance(+sec2.ch || 0)}) : tx("It {gives} {a} a chance of {ca}.", {gives: after ? tx("gave") : tx("gives"), a: fav.n, ca: chance(+fav.ch || 0)}))
        + " " + tx("It {puts} {name}’s likely share of the vote between {l80} and {h80}, and in 95 of every 100 of its {draws} simulated elections between {l95} and {h95}.", {puts: after ? tx("put") : tx("puts"), name: sh(fav.n), l80: pct(fav.l80), h80: pct(fav.h80), draws: num(+FC.draws || 0), l95: pct(fav.l95), h95: pct(fav.h95)})
        + " " + tx("A forecast is an estimate, labelled Analysis: the official count decides.");
      let p2 = "";
      if (after) {
        const fl = F.fcBy[F.lead.n], f2 = F.second && F.fcBy[F.second.n];
        if (fl) p2 = (F.full ? tx("The count has {name} at {s}: {v}.", {name: sh(F.lead.n), s: pct(F.lead.share), v: verdict(fl, +F.lead.share || 0)}) : tx("So far the count has {name} at {s}: {v}.", {name: sh(F.lead.n), s: pct(F.lead.share), v: verdict(fl, +F.lead.share || 0)})) + (f2 ? " " + tx("{name} is at {s}: {v}.", {name: sh(F.second.n), s: pct(F.second.share), v: verdict(f2, +F.second.share || 0)}) : "")
          + " " + (fav.n === F.lead.n ? tx("The model had {name} as the favourite; on their share it was off by {d} points.", {name: sh(F.lead.n), d: pts(Math.abs((+F.lead.share || 0) - (+fl.md || 0)))}) : tx("The model had {fav} as the favourite, and the count has {name} ahead: on {name}’s share it was off by {d} points.", {fav: sh(fav.n), name: sh(F.lead.n), d: pts(Math.abs((+F.lead.share || 0) - (+fl.md || 0)))}))
          + " " + tx("A miss is not explained away: it goes into the model’s track record, which is shown wherever a forecast is.");
      }
      let runs = "";
      if (F.hist.length >= 2) {
        const names = top.slice(0, 2).map(c => c.n).filter(n => F.hist.some(h => h.c[n])), n = F.hist.length, Wd = 640, Hh = 180;
        const px = i => 20 + (Wd - 40) * i / (n - 1), py = v => (Hh - 10) - (Hh - 20) * (v - lo) / span;
        const shapes = names.map(name => { const p = F.hist.map((h, i) => [i, h.c[name]]).filter(q => Array.isArray(q[1]) && q[1].length >= 3); if (p.length < 2) return "";
          return `<g style="--fp-c:${F.tint(name)}"><polygon class="fp-rb" points="${p.map(q => px(q[0]).toFixed(1) + "," + py(q[1][1]).toFixed(1)).join(" ")} ${p.slice().reverse().map(q => px(q[0]).toFixed(1) + "," + py(q[1][2]).toFixed(1)).join(" ")}"/><polyline class="fp-rl" points="${p.map(q => px(q[0]).toFixed(1) + "," + py(q[1][0]).toFixed(1)).join(" ")}"/>${p.map(q => `<line class="fp-rt" x1="${px(q[0]).toFixed(1)}" x2="${px(q[0]).toFixed(1)}" y1="${(py(q[1][0]) - 5).toFixed(1)}" y2="${(py(q[1][0]) + 5).toFixed(1)}"/>`).join("")}</g>`; }).join("");
        const first = F.hist[0], last = F.hist[n - 1];
        const moved = names.map(name => first.c[name] && last.c[name] ? tx("{name}’s middle estimate moved from {a} on {da} to {b} on {db}", {name: name, a: pct(first.c[name][0]), da: day(first.at), b: pct(last.c[name][0]), db: day(last.at)}) : "").filter(Boolean).join("; ");
        if (shapes) runs = `<figure class="fp-runf"><div class="fp-run"><div class="fp-ylab" aria-hidden="true">${ticks.map(v => `<span style="top:${(100 * (1 - (v - lo) / span)).toFixed(2)}%">${v}%</span>`).join("")}</div><svg viewBox="0 0 ${Wd} ${Hh}" preserveAspectRatio="none" role="img" aria-label="${tx("{moved}, across {n} runs.", {moved, n: num(n)})}">${ticks.map(v => `<line class="fp-rg" x1="0" x2="${Wd}" y1="${py(v).toFixed(1)}" y2="${py(v).toFixed(1)}"/>`).join("")}${shapes}</svg></div><p class="fp-runx" aria-hidden="true"><span>${day(first.at)}</span><span>${tx("{n} runs", {n: num(n)})}</span><span>${day(last.at)}</span></p><figcaption class="fp-cap">${tx("How the estimate moved, run by run: the line is each name’s middle estimate, the band the range that held 80 in 100 runs.")}</figcaption></figure>`;
      }
      parts.push(sec("forecast", after ? tx("What the forecast said") : tx("What the forecast says"), tag("analysis", tx("Analysis")),
        row(`<p>${p1}${ref("forecast")}</p>`) + row(rng) + (p2 ? row(`<p>${p2}</p>`) : "")
        + (F.track ? row(`<p>${trackWords(F)}${ref("forecast/track")}${ref("forecast/how")}</p>`) : row(`<p>${tx("No track record is on file for this kind of race yet.")}${ref("forecast/how")}</p>`))
        + (runs ? row(runs, {tier: 3}) : "") + (runs && canNb("forecast/runs") ? row(`<p>${tx("Every run, with what went into it, is in the notebook.")}${ref("forecast/runs")}</p>`, {tier: 3}) : "")
        + (FC.env ? row(`<blockquote class="fp-env"><p class="fp-envk">${tx("In the model’s own words")}</p><p>${esc(FC.env)}</p></blockquote>`, {tier: 3}) : "")));
    }

    /* ---- the polls */
    if (F.polls) {
      const P = F.polls, newest = Array.isArray(P.newest) ? P.newest.filter(p => p && p.pollster) : [];
      const after = F.counted;
      const p1 = tx("{n} polls by members of the American Association for Public Opinion Research’s Transparency Initiative are counted for this race{other}.", {n: cap(wn(+P.n || 0)), other: +P.other > 0 ? tx("; {o} other published polls are shown apart and not counted", {o: wn(+P.other)}) : ""})
        + " " + tx("We count only polls from members of the American Association for Public Opinion Research’s Transparency Initiative.") + " " + tx("A poll measures opinion when it was taken, not a forecast.");
      const trows = newest.map(p => { const names = Object.keys(p.shares || {}).sort((a, b) => (p.shares[b] || 0) - (p.shares[a] || 0));
        return `<tr><th scope="row">${p.url ? `<a href="${esc(p.url)}" rel="noopener" target="_blank">${esc(p.pollster)}</a>` : esc(p.pollster)}</th><td>${esc(pollDates(p))}</td><td>${[p.n ? tx("{n} {pop}", {n: num(p.n), pop: p.pop || tx("people")}) : (p.pop ? esc(p.pop) : ""), p.moe != null ? "±" + esc(String(p.moe)) : ""].filter(Boolean).join(", ")}</td><td>${names.map(n => `<span class="fp-ps"><i style="--fp-c:${F.tint(n)}" aria-hidden="true"></i>${esc(sh(n))} ${pct(p.shares[n], 0)}</span>`).join(" ")}</td></tr>`; }).join("");
      const table = newest.length ? `<div class="fp-tw" tabindex="0"><table class="fp-t"><caption>${tx("The newest polls we count")}</caption><thead><tr><th scope="col">${tx("Pollster")}</th><th scope="col">${tx("Dates")}</th><th scope="col">${tx("Sample")}</th><th scope="col">${tx("Shares")}</th></tr></thead><tbody>${trows}</tbody></table></div>` : "";
      const more = L && typeof L.hasFull === "function" && L.hasFull("polls") ? `<p><a class="fp-btn is-quiet" href="${esc(L.full("polls"))}">${tx("Every poll, on the full page")}</a></p>` : "";
      parts.push(sec("polls", after ? tx("What the polls said") : tx("What the polls say"), tag("links", tx("Polls")),
        row(`<p>${p1}${ref("polls")}${ref("method/polls")}</p>`) + (table ? row(table, {tier: after ? 3 : 2}) : "") + (more ? row(more, {tier: 3}) : ""), after ? 3 : 2));
    }

    /* ---- who called it, what the candidates said, the news (links only) */
    if (F.cov && (F.calls.length || F.said.length || F.stories)) {
      const callSents = F.calls.map(c => `<strong>${esc(c.o)}</strong> ${tx("called it for {name} at {when}", {name: sh(c.n), when: when(c.t)})}${c.u ? ` (<a href="${esc(c.u)}" rel="noopener" target="_blank">${tx("the report")}</a>)` : ""}`);
      const VERB = {c: tx("conceded"), v: tx("declared victory"), s: tx("made a statement")}, MED = {t: tx("text"), v: tx("video"), p: tx("a post")};
      const saidSents = F.said.map(s => { const ks = new Set(s.s.map(x => x.k)); const k = ks.size === 1 ? s.s[0].k : "s";
        const links = s.s.filter(x => x.u).map(x => `<a href="${esc(x.u)}" rel="noopener" target="_blank">${esc(x.by || tx("link"))}</a>, ${MED[x.m] || MED.t}, ${esc(day(x.d))}`).join("; ");
        return `<strong>${esc(s.n)}</strong> ${VERB[k] || VERB.s}${links ? ` (${links})` : ""}`; });
      const tiers = Object.keys(F.news), TW = {national: tx("national"), state: tx("from state outlets"), local: tx("local")};
      const heads = [];
      tiers.forEach(t => ((F.news[t] || {}).top || []).slice(0, t === "national" ? 3 : 2).forEach(h => { if (h && h.u && h.h) heads.push(`<li><a href="${esc(h.u)}" rel="noopener" target="_blank">${esc(h.h)}</a><span>${esc(h.o || "")}${h.t ? ", " + esc(day(h.t)) : ""}</span></li>`); }));
      const callsP = (F.counted || F.calls.length) ? `<p>${F.calls.length ? callSents.join("; ") + "." : tx("No news organization’s call is on record.")} ${tx("A call is a news organization’s judgment, made before every ballot is counted. The Civic Archive does not call races; it shows the count, and the calls as links.")}${ref("coverage/calls")}${ref("method/calls")}</p>` : "";
      const saidP = (F.said.length || F.counted) ? `<p>${F.said.length ? saidSents.join(". ") + "." : tx("No statement by a candidate is on record.")} ${tx("Their words are their own: nothing is copied here, and the links go to their statements and the reports that carried them.")}${ref("coverage/said")}</p>` : "";
      const newsP = F.stories ? `<p>${tx("{n} news stories are linked on the race’s Coverage tab{tiers}.", {n: num(F.stories), tiers: tiers.length ? ": " + tiers.map(t => tx("{n} {kind}", {n: num(+(F.news[t] || {}).n || 0), kind: TW[t] || t})).join(", ") : ""})}${heads.length ? " " + tx("A few of their headlines, in the outlets’ own words:") : ""}${ref("coverage/news")}</p>` : "";
      const title = F.calls.length || F.said.length ? tx("Who called it, and what the candidates said") : tx("In the news");
      parts.push(sec("coverage", title, tag("links", tx("Links only")),
        (callsP ? row(callsP) : "") + (saidP ? row(saidP) : "") + (newsP ? row(newsP, {tier: F.calls.length || F.said.length ? 3 : 2}) : "") + (heads.length ? row(`<ul class="fp-heads">${heads.join("")}</ul>`, {tier: F.calls.length || F.said.length ? 3 : 2}) : "")));
    }

    /* ---- before it is final, or what comes next */
    const labelsP = `<p>${tx("Every figure on this page carries a label saying what kind of fact it is.")} ${tag("official", tx("Official count"))} ${tx("is the office’s own figure,")} ${tag("reported", tx("As reported, not final"))} ${tx("until certified;")} ${tag("analysis", tx("Analysis"))} ${tx("is worked out by this site from official figures, with the working shown;")} ${tag("links", tx("Links only"))} ${tx("is other people’s words, linked and never copied.")}${ref("method/labels")}${ref("method/sources")}</p>`;
    if (F.counted && F.phase !== "final") {
      parts.push(sec("final", tx("Before it is final"), tag("how", tx("How it works")),
        row(`<p>${tx("Election night figures are a first count. Counties still check every ballot and add the ones that could not be counted on the night (the canvass); then the result is certified, and only then does this site mark a figure “as certified”. A close race can be recounted under state law. A concession is a custom, not a legal step: it ends no count.")}</p>`) + row(labelsP, {tier: 3})));
    } else if (F.phase === "final") {
      parts.push(sec("final", tx("The result is final"), tag("how", tx("How it works")),
        row(`<p>${tx("The count has been certified by {who}. A certified count is the official result; this site shows it as certified and marks it so.", {who: F.who})}</p>`) + row(labelsP, {tier: 3})));
    } else {
      parts.push(sec("final", tx("What comes next"), tag("how", tx("How it works")),
        row(`<p>${(F.date ? (F.past ? tx("Election Day was {date}.", {date: day(F.date)}) : tx("Election Day is {date}.", {date: day(F.date)})) + " " : "") + tx("{who} posts the count as it comes in; this page will show it as reported, not final, and mark a figure final only when it is certified.", {who: cap(F.who)})}</p>`) + row(labelsP, {tier: 3})));
    }

    /* ---- go deeper */
    const links = [];
    const safe = f => { try { return f() || ""; } catch (e) { return ""; } };
    if (canNb("sources")) links.push(safe(() => L.nb("sources", tx("Open the notebook"), {anchor: "fp-top", cls: "nbl fp-btn"})));
    else if (canNb("list")) links.push(safe(() => L.nb("list", tx("Open the notebook"), {anchor: "fp-top", cls: "nbl fp-btn"})));
    const fullHref = L && typeof L.full === "function" ? safe(() => L.full("tabs")) : "";
    if (fullHref) links.push(`<a class="fp-btn is-quiet" href="${esc(fullHref)}">${tx("The full page")}</a>`);
    const chart = L && typeof L.chart === "function" ? safe(() => L.chart()) : "";
    if (chart) links.push(`<a class="fp-btn is-quiet" href="${esc(chart)}">${tx("Polls and forecast chart")}</a>`);
    const night = L && typeof L.night === "function" ? safe(() => L.night()) : "";
    if (night) links.push(`<a class="fp-btn is-quiet" href="${esc(night)}">${tx("This race on Election Night")}</a>`);
    const past = L && typeof L.past === "function" ? safe(() => L.past()) : "";
    if (past) links.push(`<a class="fp-btn is-quiet" href="${esc(past)}">${tx("Past results in {state}", {state: F.state || F.place})}</a>`);
    const covHref = F.cov && L && typeof L.tab === "function" ? safe(() => L.tab("coverage")) : "";
    if (covHref) links.push(`<a class="fp-btn is-quiet" href="${esc(covHref)}">${tx("The Coverage tab")}</a>`);
    const fine = [];
    if (F.read) fine.push(tx("Figures read from the site’s own pages on {day}", {day: F.read}));
    if (F.counted) fine.push(F.phase === "final" ? tx("the count as certified") : tx("the count as reported {at}", {at: F.at}));
    if (F.fc && F.fc.model) fine.push(tx("forecast model {m}", {m: String(F.fc.model)}));
    if (F.cov && F.cov.checked) fine.push(tx("coverage links checked {day}", {day: day(F.cov.checked)}));
    if (F.src.page && F.src.label) fine.push(`<a href="${esc(F.src.page)}" rel="noopener" target="_blank">${esc(F.src.label)}</a>`);
    const deeper = `<nav class="fp-deep" aria-label="${tx("Go deeper")}"><p class="fp-deepk">${tx("Go deeper")}</p><p>${tx("The notebook holds the sources, the full tables and what each figure cannot tell you: one page per topic. The marks on this page open the exact page.")}</p>${links.length ? `<div class="fp-deepl">${links.join("")}</div>` : ""}${fine.length ? `<p class="fp-fine">${fine.join("; ")}.</p>` : ""}</nav>`;

    /* ---- the byline: what the page is written from */
    const by = [`<span>${tx("From the record:")}</span>`];
    if (F.counted && sameA(F.agency || F.who, F.who)) by.push(`<span>${tx("the count and the list, {who}", {who: F.who})}</span>`);
    else { if (F.counted) by.push(`<span>${tx("the count, {who}", {who: F.who})}</span>`); by.push(`<span>${tx("the list, {agency}", {agency: theA(F.agency || F.who)})}</span>`); }
    if (F.fc) by.push(`<span>${tx("the forecast, the site’s own model (Analysis)")}</span>`);
    if (F.polls) by.push(`<span>${tx("the polls, each pollster’s own release")}</span>`);
    if (F.cov) by.push(`<span>${tx("the calls and statements, the race’s Coverage file (links only)")}</span>`);

    /* ---- the jump strip: the sections present */
    /* drawn twice, one shown at a time: a numbered list in the margin beside the standfirst on a wide page, and a strip of
       chips that stays under the top bar on a narrow one (a sticky element holds only inside its parent, so the strip is
       a child of the article itself) */
    const jumpList = sections.map(([id, t]) => `<li><button type="button" class="fp-jump" data-to="fp-s-${id}">${t}</button></li>`).join("");
    const inside = `<nav class="fp-inside" aria-label="${tx("Inside this edition")}"><p>${tx("Inside")}</p><ol>${jumpList}</ol></nav>`;
    const strip = `<nav class="fp-inside fp-strip" aria-label="${tx("Inside this edition")}" data-fp-min="2"><ol>${jumpList}</ol></nav>`;

    const article = `<article class="fp-art" id="fp-top" aria-labelledby="fp-h1"><header class="fp-head"><h1 class="fp-h1" id="fp-h1">${W.h1}</h1>
${row(`<p class="fp-stand">${W.stand.join(" ")}</p><div class="fp-margin fp-margin-nav" data-fp-min="2">${inside}</div>`, {cls: "fp-standrow"})}
<p class="fp-by" data-fp-min="2">${by.join("")}</p></header>${strip}${lead}${brief}${parts.join("")}
<div class="fp-readon"><button type="button" class="fp-btn is-quiet fp-more" data-to="2"></button></div>${deeper}</article>`;
    return `<div class="fp" data-fp-root data-fp-len="2"><div class="fp-prog" aria-hidden="true"><i></i></div>${masthead}${article}</div>`;
  }

  /* ---------- wire: the controls, each listener removed by the cleanup ---------- */
  const KEY = "tca.view.front.v1";
  const store = {
    get() { try { const j = JSON.parse(localStorage.getItem(KEY) || "null"); return j && typeof j === "object" ? j : {}; } catch (e) { return {}; } },
    set(o) { try { localStorage.setItem(KEY, JSON.stringify(Object.assign(store.get(), o))); } catch (e) { /* this visit only */ } }
  };
  const SKIP = new Set(["fp-note", "fp-ref", "fp-len", "fp-lenhint", "fp-inside", "fp-prog", "fp-rleg", "fp-readon", "fp-sr", "fp-mark"]);
  function countWords(root) {
    const buck = {1: 0, 2: 0, 3: 0};
    (function walk(el, tier, skip) {
      for (const n of el.childNodes) {
        if (n.nodeType === 3) { if (!skip) buck[tier] += (n.data.match(/\S+/g) || []).length; continue; }
        if (n.nodeType !== 1) continue;
        const tag = n.localName; if (tag === "style" || tag === "script" || tag === "svg") continue;
        let t = tier; const v = +(n.getAttribute("data-fp-min") || 0); if (v > t) t = Math.min(3, v);
        let s = skip; if (!s) for (const c of n.classList) if (SKIP.has(c)) { s = true; break; }
        walk(n, t, s);
      }
    })(root, 1, false);
    return buck;
  }
  function reading(words) {   // [short, long]: "1 min", "about 1 minute", at 230 words a minute
    const secs = words / 230 * 60;
    if (secs < 45) { const s = Math.max(5, Math.round(secs / 5) * 5); return [tx("{s} sec", {s: String(s)}), tx("about {s} seconds", {s: String(s)})]; }
    const m = Math.max(1, Math.round(secs / 60));
    return [tx("{m} min", {m: String(m)}), m === 1 ? tx("about 1 minute") : tx("about {m} minutes", {m: String(m)})];
  }
  function levelStart() {
    let lv = 0;
    try { lv = has(VIEWS, "level") ? +VIEWS.level() || 0 : 0; } catch (e) { lv = 0; }
    if (!lv) lv = +(document.documentElement.getAttribute("data-level") || 0);
    return lv >= 4 ? "3" : lv === 3 ? "2" : lv >= 1 ? "1" : "2";
  }

  function wire(root, S, L) {
    const fp = root.querySelector("[data-fp-root]"); if (!fp) return () => {};
    const $ = (s, el) => (el || fp).querySelector(s), $$ = (s, el) => Array.from((el || fp).querySelectorAll(s));
    const offs = [];
    const on = (el, ev, fn, o) => { el.addEventListener(ev, fn, o); offs.push(() => el.removeEventListener(ev, fn, o)); };
    const timers = new Set();
    const later = (fn, ms) => { const id = setTimeout(() => { timers.delete(id); fn(); }, ms); timers.add(id); return id; };
    const raf = fn => requestAnimationFrame(fn);
    const motion = () => !calm();
    fp.classList.toggle("is-motion", motion());
    const art = $(".fp-art");
    const wide = () => root.clientWidth >= 1040;

    /* ---- how much to read: the words counted from the page itself, the start from the reader's level */
    const buck = countWords(art || fp);
    const cum = {1: buck[1], 2: buck[1] + buck[2], 3: buck[1] + buck[2] + buck[3]};
    const NAMES = {1: tx("the gist"), 2: tx("the story"), 3: tx("everything")};
    const HINT = {}, WORDS = {}, MORE = {};
    [1, 2, 3].forEach(k => { const r = reading(cum[k]); HINT[k] = tx("Showing {name}: {time} to read, about {w} words.", {name: NAMES[k], time: r[1], w: num(cum[k])}); WORDS[k] = r[0]; });
    MORE[1] = tx("Read on: the story ({time})", {time: reading(cum[2])[1]}); MORE[2] = tx("Read everything ({time} in all)", {time: reading(cum[3])[1]});
    const radios = $$(".fp-len input"), hint = $(".fp-lenhint"), more = $(".fp-more");
    $$(".fp-len small").forEach(s => { s.textContent = WORDS[s.dataset.w] || ""; });
    let leaving = 0;
    function setLen(v, save, animate) {
      v = String(v); if (!HINT[v]) v = "2";
      const was = fp.dataset.fpLen;
      const apply = () => {
        fp.dataset.fpLen = v;
        if (animate && motion() && +v > +was) {
          const fresh = $$("[data-fp-min]").filter(el => +el.getAttribute("data-fp-min") > +was && +el.getAttribute("data-fp-min") <= +v && !el.classList.contains("fp-margin"));
          fresh.forEach((el, i) => { el.classList.add("fp-enter"); el.style.animationDelay = Math.min(i * 40, 360) + "ms"; later(() => { el.classList.remove("fp-enter"); el.style.animationDelay = ""; }, 700); });
        }
        raf(layNotes); raf(spy);
      };
      if (animate && motion() && +v < +was) {
        const going = $$("[data-fp-min]").filter(el => +el.getAttribute("data-fp-min") > +v && el.getClientRects().length);
        going.forEach(el => el.classList.add("fp-leave"));
        const id = ++leaving;
        later(() => { if (id !== leaving) return; going.forEach(el => el.classList.remove("fp-leave")); apply(); }, 190);
      } else apply();
      radios.forEach(r => { r.checked = r.value === v; });
      if (hint) hint.textContent = HINT[v];
      if (more) { more.dataset.to = String(Math.min(3, +v + 1)); more.textContent = MORE[v] || ""; }
      if (save) store.set({len: v});
    }
    radios.forEach(r => on(r, "change", () => setLen(r.value, true, true)));
    if (more) on(more, "click", () => {
      const to = more.dataset.to, was = fp.dataset.fpLen;
      const first = $$(`[data-fp-min="${to}"]`).find(el => !el.classList.contains("fp-margin"));
      setLen(to, true, true);
      if (first && +was < +to) later(() => { first.setAttribute("tabindex", "-1"); first.focus({preventScroll: true}); first.scrollIntoView({block: "start", behavior: motion() ? "smooth" : "auto"}); flash(first.classList.contains("fp-row") ? first : first.closest(".fp-row") || first); }, motion() ? 60 : 0);
    });
    function flash(el) { if (!el) return; el.classList.add("is-back"); later(() => el.classList.remove("is-back"), 2600); }

    /* ---- the margin notes take no room of their own on a wide page: keep each below the one before it */
    const margins = $$(".fp-margin:not(.fp-margin-nav)");
    function layNotes() {
      margins.forEach(m => { m.style.marginTop = ""; });
      if (art) art.style.paddingBottom = "";
      fp.classList.toggle("is-wide", wide());
      if (!wide()) return;
      let bottom = -1e9, deepest = 0;
      margins.forEach(m => {
        if (!m.getClientRects().length) return;
        let r = m.getBoundingClientRect(); const top = r.top + scrollY;
        if (top < bottom + 16) m.style.marginTop = Math.round(bottom + 16 - top) + "px";
        r = m.getBoundingClientRect(); bottom = r.bottom + scrollY; if (bottom > deepest) deepest = bottom;
      });
      if (art) { const ab = art.getBoundingClientRect().bottom + scrollY; if (deepest > ab) art.style.paddingBottom = Math.round(deepest - ab + 8) + "px"; }
    }
    const marks = $$(".fp-ref");
    const noteOf = m => fp.querySelector("#" + m.getAttribute("aria-controls"));
    function mode() {
      marks.forEach(m => { const n = noteOf(m); if (!n) return;
        if (wide()) { m.removeAttribute("aria-expanded"); n.classList.remove("is-open"); } else m.setAttribute("aria-expanded", n.classList.contains("is-open") ? "true" : "false"); });
      layNotes();
    }
    let ro = null;
    if (typeof ResizeObserver === "function") { ro = new ResizeObserver(() => { clearTimeout(rt); rt = setTimeout(mode, 80); }); ro.observe(root); }
    let rt = 0;
    on(window, "resize", () => { clearTimeout(rt); rt = setTimeout(mode, 120); });
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(() => { if (fp.isConnected) layNotes(); });
    later(layNotes, 700);
    marks.forEach(m => {
      const n = noteOf(m); if (!n) return;
      const hot = o => { n.classList.toggle("is-hot", o); m.classList.toggle("is-hot", o); };
      on(m, "click", () => {
        if (wide()) { hot(true); n.focus({preventScroll: false}); later(() => hot(false), 1800); return; }
        const open = !n.classList.contains("is-open");
        n.classList.toggle("is-open", open); m.setAttribute("aria-expanded", open ? "true" : "false");
        if (open) n.focus({preventScroll: true});
      });
      on(m, "mouseenter", () => hot(true)); on(m, "mouseleave", () => hot(false));
      on(m, "focus", () => hot(true)); on(m, "blur", () => hot(false));
      on(n, "mouseenter", () => hot(true)); on(n, "mouseleave", () => hot(false));
      on(n, "keydown", e => { if (e.key === "Escape" && !wide() && n.classList.contains("is-open")) { n.classList.remove("is-open"); m.setAttribute("aria-expanded", "false"); m.focus(); e.stopPropagation(); } });
    });

    /* ---- the jump strip: to a section, by button, never by the page's address; the current one marked */
    const jumps = $$(".fp-jump");
    jumps.forEach(b => on(b, "click", () => {
      const sec = fp.querySelector("#" + b.dataset.to); if (!sec) return;
      const need = +(sec.getAttribute("data-fp-min") || 1);
      if (need > +fp.dataset.fpLen) setLen(String(need), true, false);
      raf(() => { sec.scrollIntoView({block: "start", behavior: motion() ? "smooth" : "auto"}); const h = sec.querySelector("h2"); if (h) h.focus({preventScroll: true}); });
    }));
    let io = null;
    function spy() {
      jumps.forEach(b => { const sec = fp.querySelector("#" + b.dataset.to); b.parentElement.hidden = !sec || !sec.getClientRects().length; });
    }
    if (typeof IntersectionObserver === "function" && jumps.length) {
      const seen = new Map();
      io = new IntersectionObserver(es => {
        es.forEach(e => seen.set(e.target.id, e.isIntersecting ? e.boundingClientRect.top : null));
        let best = null, bt = Infinity;
        seen.forEach((top, id) => { if (top != null && Math.abs(top) < bt) { bt = Math.abs(top); best = id; } });
        jumps.forEach(b => { if (best && b.dataset.to === best) b.setAttribute("aria-current", "true"); else b.removeAttribute("aria-current"); });
      }, {rootMargin: "-20% 0px -60% 0px", threshold: [0, .1]});
      $$(".fp-sec").forEach(s => io.observe(s));
    }
    spy();

    /* ---- the lead: the bar wipes in and the big figures count up, once, with motion on */
    const fmt = (v, f) => f === "p" ? pct(v) : f === "d" ? pts(v) : num(v);
    if (motion()) {
      const bar = $(".fp-bar"); if (bar) bar.classList.add("is-anim");
      const nums = $$(".fp-num");
      nums.forEach(el => { el.dataset.t = el.textContent; });
      if (nums.length) {
        const t0 = performance.now(), D = 1150, ease = t => 1 - Math.pow(1 - t, 3);
        const step = now => { if (!fp.isConnected) return; const t = Math.min(1, (now - t0) / D), e = ease(t);
          nums.forEach(el => { el.textContent = t < 1 ? fmt(+el.dataset.v * e, el.dataset.f) : el.dataset.t; });
          if (t < 1) raf(step); };
        raf(step);
      }
    }

    /* ---- how far along the story the reader is */
    const prog = $(".fp-prog i");
    let pending = false;
    function paint() {
      pending = false; if (!prog || !art) return;
      const r = art.getBoundingClientRect(), total = r.height - innerHeight;
      prog.style.transform = "scaleX(" + (total > 0 ? Math.min(1, Math.max(0, -r.top / total)) : 1).toFixed(4) + ")";
    }
    on(window, "scroll", () => { if (!pending) { pending = true; raf(paint); } }, {passive: true});
    on(window, "resize", paint);
    paint();

    /* ---- back from the notebook (or any link to a row): shown even when the chosen length hides it */
    function reveal(id) {
      const el = id && fp.querySelector("#" + String(id).replace(/[^\w-]/g, "")); if (!el) return false;
      let need = 1;
      for (let n = el; n && n !== fp; n = n.parentElement) { const v = +(n.getAttribute("data-fp-min") || 0); if (v > need) need = v; }
      if (need > +fp.dataset.fpLen) setLen(String(need), false, false);
      const r = el.closest(".fp-row"); flash(r || el);
      raf(() => el.scrollIntoView({block: r ? "center" : "start", behavior: motion() ? "smooth" : "auto"}));
      return true;
    }
    on(root, "vw:reveal", e => { if (e && e.detail && e.detail.id) reveal(e.detail.id); });
    root.fpReveal = reveal;
    /* a notebook link remembers its row; when the notebook closes (the &nb= part leaves the address) the row is shown
       again even if the chosen length hides it, so the core's focus on it lands */
    let lastAnchor = "", wasNb = /[&#]nb=/.test(location.hash);
    on(root, "click", e => { const a = e.target && e.target.closest && e.target.closest("a[data-anchor]"); if (a && fp.contains(a)) lastAnchor = a.getAttribute("data-anchor") || ""; });
    const onHash = () => { const isNb = /[&#]nb=/.test(location.hash); if (wasNb && !isNb && lastAnchor) { const id = lastAnchor; lastAnchor = ""; reveal(id); } wasNb = isNb; };
    on(window, "hashchange", onHash); on(window, "popstate", onHash);

    setLen(store.get().len || levelStart(), false, false);
    mode();

    return () => {
      offs.forEach(f => f()); timers.forEach(id => clearTimeout(id)); timers.clear(); clearTimeout(rt);
      if (ro) ro.disconnect(); if (io) io.disconnect(); delete root.fpReveal;
    };
  }

  VIEWS.add({
    id: "front", label: "The Front Page", order: 1,
    render, wire,
    reveal(root, id) { return typeof root.fpReveal === "function" ? root.fpReveal(id) : false; }
  });
})();

/* ======== cards ======== */
/* One card at a time (view "cards"): the race as a deck of large cards, one question each, every card turning over to
   "How we know" with links into the notebook. Ported from the sandbox example (sandbox_src/layouts/cards.py) and made to
   render any race from S (views_src/SPEC.md, version 1). The deck is chosen from what S carries: before a count the list
   comes first; during and after a count the count leads; a retention vote, an unopposed race, several seats and a race
   with no candidate each get their own words. A short deck is fine; an empty card never is.
   Registered with VIEWS.add; nothing here touches anything outside the root the core hands to wire(). */
(() => {
  "use strict";
  if (typeof VIEWS === "undefined" || !VIEWS || typeof VIEWS.add !== "function") return;
  const V = VIEWS;
  const T = (s, v) => String(V.T(s, v || {}));
  const esc = s => V.esc(s == null ? "" : String(s));
  const num = n => V.num(Math.round(+n || 0));
  const pct = (x, d) => V.pct(+x || 0, d == null ? 1 : d);
  const p1 = x => String(pct(x, 1)).replace(/\s*%\s*$/, "");      /* the figure alone, for a number that counts up */
  const ID = "vw-cd";
  const KIND = {c: "Conceded", v: "Declared victory", s: "Statement"};
  const MEDIUM = {t: "text", v: "video", p: "a post"};
  const PARTICLE = /^(de|del|della|der|di|da|du|la|le|van|von|st\.?|mac|mc|bin|al|el|ter|ten|op|af)$/i;
  const SUFFIX = /^(jr\.?|sr\.?|ii|iii|iv|v)$/i;
  const TURN = '<svg viewBox="0 0 20 20" aria-hidden="true" focusable="false"><path d="M4 10a6 6 0 0 1 10.4-4.1L16 7.5M16 3.5v4h-4" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/><path d="M16 10a6 6 0 0 1-10.4 4.1L4 12.5M4 16.5v-4h4" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  const ARROW_L = '<svg viewBox="0 0 20 20" aria-hidden="true" focusable="false"><path d="M12.5 4 6.5 10l6 6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  const ARROW_R = '<svg viewBox="0 0 20 20" aria-hidden="true" focusable="false"><path d="m7.5 4 6 6-6 6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>';

  /* ---------- small helpers ---------- */
  const addr = v => (typeof v === "string" ? (v[0] === "<" ? (v.match(/href="([^"]*)"/) || [0, ""])[1] : v) : "");
  const last = n => {      /* the family name, keeping a particle (de la Cruz) and dropping a suffix (Jr.) */
    const p = String(n || "").trim().split(/\s+/).filter(Boolean);
    while (p.length > 1 && SUFFIX.test(p[p.length - 1])) p.pop();
    if (!p.length) return "";
    let i = p.length - 1;
    while (i > 0 && PARTICLE.test(p[i - 1])) i--;
    return p.slice(i).join(" ");
  };
  const monDay = iso => {      /* "October 8" from a date, "October 8, 2026" when the day function gives no year to drop */
    if (!iso) return "";
    const d = String(V.day(iso) || "");
    return d.replace(/,\s*\d{4}$/, "");
  };
  const pv = (partisan, code) => {      /* the page's colour variable for a party, "" on a nonpartisan office or an unknown code */
    if (!partisan || !code) return "";
    let v = "";
    try { v = V.partyVar(String(code)) || V.partyVar(String(code)[0]) || ""; } catch (e) { v = ""; }
    v = String(v || "");
    return v ? (v.startsWith("--") ? `var(${v})` : v) : "";
  };
  const nUp = (text, raw, d) => `<span class="cd-n" data-n="${esc(raw)}" data-d="${d || 0}" data-t="${esc(text)}">${esc(text)}</span>`;
  const ext = (url, text) => (url ? `<a href="${esc(url)}" rel="noopener" target="_blank">${text}</a>` : text);
  const tag = (k, t) => `<span class="cd-tag" data-k="${k}">${t}</span>`;
  const tags = list => (list.length ? `<div class="cd-tags">${list.join("")}</div>` : "");
  const row = (name, sub, val, subval, share, col) =>
    `<li class="cd-row${col ? "" : " np"}"${col ? ` style="--pc:${col}"` : ""}><span class="band" aria-hidden="true"></span>` +
    `<span class="who">${name}${sub ? ` <span>${sub}</span>` : ""}</span><span class="val">${val}${subval ? `<span>${subval}</span>` : ""}</span>` +
    `<span class="bar" aria-hidden="true"><i style="--w:${Math.max(0, Math.min(100, +share || 0)).toFixed(2)}%"></i></span></li>`;
  const cant = items => (items.length ? `<ul class="cd-cant">${items.map(x => `<li>${x}</li>`).join("")}</ul>` : "");
  const links = items => { const xs = items.filter(Boolean); return xs.length ? `<div class="cd-links">${xs.join("")}</div>` : ""; };
  const reporting = C => (Array.isArray(C.reporting) && C.reporting.length === 2 && +C.reporting[1] > 0 ? [+C.reporting[0] || 0, +C.reporting[1]] : null);
  const yesNo = cands => {      /* a retention count: one row named yes, one named no */
    const y = cands.find(c => /^yes$/i.test(String(c.n || "").trim())), n = cands.find(c => /^no$/i.test(String(c.n || "").trim()));
    return y && n ? {yes: y, no: n} : null;
  };
  const reportedBy = (office, when, final) => {
    if (final) return office ? T("Certified by {office}.", {office: esc(office)}) : T("A certified count.");
    if (office && when) return T("As reported by {office} on {when}; not final.", {office: esc(office), when: esc(when)});
    if (office) return T("As reported by {office}; not final.", {office: esc(office)});
    if (when) return T("As reported on {when}; not final.", {when: esc(when)});
    return T("As reported; not final.");
  };
  const countTags = final => [tag("official", T("Official count")), final ? tag("final", T("As certified")) : tag("reported", T("As reported, not final"))];
  const joinList = parts => {      /* "A, B and C" */
    if (parts.length <= 1) return parts.join("");
    if (parts.length === 2) return T("{a} and {b}", {a: parts[0], b: parts[1]});
    return T("{list} and {last}", {list: parts.slice(0, -1).join(", "), last: parts[parts.length - 1]});
  };

  /* ---------- the deck ---------- */
  function build(S, L) {
    const kind = S.kind || "contest";
    const seats = Math.max(1, Math.round(+S.seats) || 1);
    const partisan = !!S.partisan;
    const list = Array.isArray(S.list) ? S.list.filter(x => x && x.n) : [];
    const C = S.count && Array.isArray(S.count.cands) && S.count.cands.filter(x => x && x.n).length && +S.count.total > 0 ? S.count : null;
    const K = C && S.counties && Array.isArray(S.counties.top) && S.counties.top.length ? S.counties : null;
    const F = S.forecast && Array.isArray(S.forecast.top) && S.forecast.top.length && kind !== "unopposed" && kind !== "none" ? S.forecast : null;
    const P = S.polls && Array.isArray(S.polls.newest) && S.polls.newest.length ? S.polls : null;
    const X = S.coverage && typeof S.coverage === "object" ? S.coverage : null;
    const calls = X && Array.isArray(X.calls) ? X.calls.filter(c => c && c.o && c.n).slice().sort((a, b) => String(a.t || "").localeCompare(String(b.t || ""))) : [];
    const said = X && Array.isArray(X.said) ? X.said.filter(s => s && s.n && Array.isArray(s.s) && s.s.length) : [];
    const news = X && X.news && typeof X.news === "object" ? X.news : null;
    const tiers = news ? ["national", "state", "local"].filter(k => news[k] && (+news[k].n > 0 || (Array.isArray(news[k].top) && news[k].top.length))) : [];
    const newsN = tiers.reduce((a, k) => a + Math.max(+news[k].n || 0, (news[k].top || []).length), 0);
    const office = S.source && S.source.office ? String(S.source.office) : "";
    const nb = (path, text, anchor) => { try { return L.has(path) ? String(L.nb(path, text, {anchor})) : ""; } catch (e) { return ""; } };
    const c = {S, L, kind, seats, partisan, list, C, K, F, P, X, calls, said, news, tiers, newsN, office, nb};
    const cards = [];
    if (C) { cards.push(leadCard(c)); if (C.cands.length >= 2) cards.push(marginCard(c)); }
    if (K) cards.push(countiesCard(c));
    if (F) cards.push(forecastCard(c));
    if (P) cards.push(pollsCard(c));
    if (calls.length || said.length) cards.push(calledCard(c));
    if (newsN) cards.push(newsCard(c));
    const lc = listCard(c);
    if (C) cards.push(lc); else cards.unshift(lc);
    cards.push(stepsCard(c));
    cards.push(nextCard(c, cards.length + 1));
    return cards;
  }

  /* ---- who is ahead */
  function leadCard(c) {
    const {C, seats, partisan, kind, office, nb, L, list} = c;
    const cands = C.cands.filter(x => x && x.n), lead = cands[0], second = cands[1] || null;
    const rep = reporting(C), allIn = !!rep && rep[0] >= rep[1], final = !!C.final;
    const when = C.at ? String(V.when(C.at)) : "";
    const yn = yesNo(cands);
    const reported = reportedBy(office, when, final);
    const name = esc(lead.n);
    let q, fact, say;
    if (yn) {
      const who = list.length ? esc(list[0].n) : "";
      q = who ? T("Is {name} keeping the office?", {name: who}) : T("Yes or no?");
      fact = `<p class="cd-fact">${nUp(p1(yn.yes.share), yn.yes.share, 1)}<span class="u">%</span> ${T("yes")}<small>${T("{yes} votes yes, {no} votes no", {yes: num(yn.yes.votes), no: num(yn.no.votes)})}</small></p>`;
      const v = {yes: pct(yn.yes.share), no: pct(yn.no.share), name: who};
      say = `<p class="cd-say">${who ? T("{yes} of the votes say yes to {name} keeping the office and {no} say no.", v) : T("{yes} of the votes say yes and {no} say no.", v)} ${reported}</p>`;
    } else if (seats > 1) {
      q = T("Who is ahead for the {seats} seats?", {seats: num(seats)});
      fact = `<p class="cd-fact">${name}<small>${partisan && lead.party ? `${esc(lead.party)} &middot; ` : ""}${T("{share} of the vote", {share: pct(lead.share)})}</small></p>`;
      const names = joinList(cands.slice(0, seats).map(x => `<b>${esc(x.n)}</b>`));
      const nxt = cands[seats] ? " " + T("Next is {name} with {share}.", {name: esc(cands[seats].n), share: pct(cands[seats].share)}) : "";
      say = `<p class="cd-say">${final ? T("The {seats} with the most votes, as certified: {names}.", {seats: num(seats), names})
                                    : T("The {seats} with the most votes as reported: {names}.", {seats: num(seats), names})}${nxt} ${reported}</p>`;
    } else {
      q = T("Who is ahead in the count?");
      fact = `<p class="cd-fact">${name}<small>${partisan && lead.party ? `${esc(lead.party)} &middot; ` : ""}${nUp(p1(lead.share), lead.share, 1)}% ${T("of the vote")}</small></p>`;
      const v = {name: `<b>${name}</b>`, v1: num(lead.votes), second: second ? esc(second.n) : "", v2: second ? num(second.votes) : "", in: rep ? num(rep[0]) : "", of: rep ? num(rep[1]) : ""};
      let s;
      if (kind === "unopposed") s = T("No one ran against {name}: {v1} votes were reported.", v);
      else if (final) s = second ? T("{name} had the most votes, as certified: {v1} votes to {second}’s {v2}.", v) : T("{name} had the most votes, as certified: {v1} votes.", v);
      else {
        const lw = allIn ? T("{name} is ahead with every one of the {of} precincts reporting", v)
                 : rep ? T("{name} leads the count with {in} of {of} precincts reporting", v) : T("{name} leads the count", v);
        s = second ? T("{lead}: {v1} votes to {second}’s {v2}.", {lead: lw, v1: v.v1, second: v.second, v2: v.v2}) : T("{lead}: {v1} votes.", {lead: lw, v1: v.v1});
      }
      say = `<p class="cd-say">${s} ${reported}</p>`;
    }
    const rows = cands.map(x => row(esc(x.n), partisan ? esc(x.party || "") : "", pct(x.share, 2), T("{votes} votes", {votes: num(x.votes)}), x.share, pv(partisan, x.code))).join("");
    const front = `${fact}${say}<ol class="cd-rows" aria-label="${esc(T("Every line of the count: votes and share"))}">${rows}</ol>`;
    const src = c.S.source || {};
    const srcText = esc(src.label || office || T("the election office"));
    const back = `<h3 class="cd-bh" tabindex="-1">${final ? T("The certified figures") : T("The official figures, as posted")}</h3>
<p>${T("The count comes from {src}.", {src: ext(src.page, srcText)})} ${when ? T("This reading is from {when}.", {when: esc(when)}) : ""} ${rep ? T("{in} of {of} precincts had reported.", {in: num(rep[0]), of: num(rep[1])}) : ""}</p>
<p>${final ? T("It is certified: the result is final.")
           : T("It is <strong>as reported, not final</strong>: the election office checks every ballot (the canvass) and certifies the result later. This site marks a figure “as certified” only then.")}</p>
${cant([T("It cannot show how any one person voted, or why."), T("This site never says anyone won; the certified result decides.")])}
${links([nb("count", T("The full count"), `${ID}-c1`), nb("method/labels", T("What the labels mean"), `${ID}-c1`), addr(L.night()) ? `<a href="${esc(addr(L.night()))}">${T("This race on Election Night")}</a>` : ""])}`;
    return {q, tags: countTags(final), front, back, link: nb("count", T("The full count"))};
  }

  /* ---- by how much */
  function marginCard(c) {
    const {C, seats, partisan, nb} = c;
    const cands = C.cands.filter(x => x && x.n);
    const lastSeat = seats > 1 && cands.length > seats;
    const a = lastSeat ? cands[seats - 1] : cands[0], b = lastSeat ? cands[seats] : cands[1];
    const margin = Math.max(0, (+a.share || 0) - (+b.share || 0)), gap = Math.max(0, (+a.votes || 0) - (+b.votes || 0));
    const total = +C.total || 0, final = !!C.final;
    const yn = yesNo(cands);
    const q = lastSeat ? T("How close is the last seat?") : T("By how much?");
    const an = esc(a.n), bn = esc(b.n);
    const fact = `<p class="cd-fact">${nUp(p1(margin), Math.round(margin * 100) / 100, 1)} <span class="u">${T("points")}</span><small>${yn ? T("{gap} more votes yes than no, out of {total} cast", {gap: num(gap), total: num(total)}) : T("{gap} more votes than {name}, out of {total} cast", {gap: num(gap), name: bn, total: num(total)})}</small></p>`;
    let s;
    if (yn) s = T("Yes has {a} of the vote and no {b}. The gap is {m} points of all votes cast, or {gap} votes.", {a: pct(a.share), b: pct(b.share), m: p1(margin), gap: num(gap)});
    else if (lastSeat) s = T("{a} holds the last of the {seats} seats as reported, with {sa} of the vote; {b} is next with {sb}. The gap is {m} points, or {gap} votes.", {a: an, seats: num(seats), sa: pct(a.share), b: bn, sb: pct(b.share), m: p1(margin), gap: num(gap)});
    else s = T("{a} has {sa} of the vote and {b} {sb}. The gap is {m} points of all votes cast, or {gap} votes.", {a: an, sa: pct(a.share), b: bn, sb: pct(b.share), m: p1(margin), gap: num(gap)});
    const pair = [a, b].map(x => row(esc(x.n), "", pct(x.share), "", x.share, pv(partisan, x.code))).join("");
    const front = `${fact}<p class="cd-say">${s}</p>
<div class="cd-gapbox" aria-hidden="true"><ol class="cd-rows">${pair}</ol><p class="lbl"><span>0%</span><b>${T("the gap: {m} points", {m: p1(margin)})}</b><span>100%</span></p></div>`;
    const cs = +C.county_sum;
    let agree = "";
    if (cs > 0 && total > 0) {
      const diff = total - cs;
      agree = diff === 0 ? T("The county figures in the same reading add up to the overall total exactly.")
            : T("The county figures in the same reading add up to {sum} votes, {diff} {more} than the overall total; this site shows each as posted and adjusts neither.", {sum: num(cs), diff: num(Math.abs(diff)), more: diff > 0 ? T("fewer") : T("more")});
    }
    const back = `<h3 class="cd-bh" tabindex="-1">${T("The arithmetic")}</h3>
<p>${T("A margin in points is the gap between two shares of <em>all</em> votes cast, every other line included: {sa} minus {sb} is {m} points. In votes: {va} minus {vb} is {gap}.", {sa: pct(a.share, 2), sb: pct(b.share, 2), m: p1(margin), va: num(a.votes), vb: num(b.votes), gap: num(gap)})}</p>
${agree ? `<p>${agree}</p>` : ""}
${cant(final ? [T("A certified margin can still be recounted where state law allows it.")] : [T("The figures can still change until the result is certified.")])}
${links([nb("count", T("The full count"), `${ID}-m`), nb("method/labels", T("What the labels mean"), `${ID}-m`)])}`;
    return {q, tags: countTags(final), front, back, link: nb("count", T("The full count"))};
  }

  /* ---- where the votes came from */
  function countiesCard(c) {
    const {C, K, partisan, nb, L} = c;
    const cands = C.cands.filter(x => x && x.n), lead = cands[0], second = cands[1] || null;
    const top = K.top.filter(x => x && x.name && +x.total > 0);
    const ntop = top.length, topVotes = top.reduce((a, x) => a + (+x.total || 0), 0);
    const den = +C.county_sum || +C.total || 0;
    const share = den ? 100 * topVotes / den : 0;
    const won = K.won && typeof K.won === "object" ? Object.entries(K.won).filter(([n, v]) => n && +v > 0).sort((p, q) => q[1] - p[1]) : [];
    const nK = Math.max(+K.n || 0, won.reduce((a, x) => a + +x[1], 0), ntop);
    const counties = T("counties");
    const fact = den
      ? `<p class="cd-fact">${nUp(share.toFixed(0), Math.round(share * 10) / 10, 0)}<span class="u">%</span><small>${T("of all votes came from the {ntop} largest of the {n} counties in this race", {ntop: num(ntop), n: num(nK)})}</small></p>`
      : `<p class="cd-fact">${nUp(num(nK), nK, 0)}<small>${T("counties in this race, the largest listed below")}</small></p>`;
    let s = "";
    if (won.length) {
      const first = T("{name} had the most votes in {k} of {n} counties", {name: esc(won[0][0]), k: num(won[0][1]), n: num(nK)});
      const rest = won.slice(1).map(([n, v]) => T("{name} in {k}", {name: esc(n), k: num(v)})).join(", ");
      const both = rest ? `${first}, ${rest}` : first;
      s = won[0][0] !== lead.n
        ? T("{both}; the overall count went the other way, because every vote counts the same and most are cast in a few large counties.", {both})
        : T("{both}, and leads the overall count too. Every vote counts the same, and most votes are cast in a few large counties.", {both});
    } else s = T("The counties with the most votes cast are listed below, with the share of the line that led in each.");
    const cl = pv(partisan, lead.code), cs = second ? pv(partisan, second.code) : "";
    const rows = top.slice(0, 5).map(x => {
      const sh = x.shares && typeof x.shares === "object" ? x.shares : {};
      const s1 = +sh[lead.n] || 0, s2 = second ? (+sh[second.n] || 0) : 0;
      const ld = x.lead && sh[x.lead] != null ? x.lead : (second && s2 > s1 ? second.n : lead.n);
      const lds = +sh[ld] || 0;
      const nm = esc(String(x.name).replace(/\s+County$/i, ""));
      return `<li><span class="nm">${nm} <span>${num(x.total)}${x.done === false ? ` &middot; ${T("still counting")}` : ""}</span></span>` +
        `<span class="bar" aria-hidden="true"><i style="${cl ? `--pc:${cl};` : ""}width:${s1.toFixed(1)}%"></i>${second ? `<i style="${cs ? `--pc:${cs};` : ""}width:${s2.toFixed(1)}%"></i>` : ""}</span>` +
        `<span class="ld">${pct(lds)} <span>${esc(last(ld))}</span></span></li>`;
    }).join("");
    const key = `<p class="cd-key" aria-hidden="true"><span><i${cl ? ` style="--pc:${cl}"` : ""}></i>${esc(last(lead.n))}</span>${second ? `<span><i${cs ? ` style="--pc:${cs}"` : ""}></i>${esc(last(second.n))}</span>` : ""}<span>${T("Votes cast after each county’s name")}</span></p>`;
    const front = `${fact}<p class="cd-say">${s}</p>
<ol class="cd-cty" aria-label="${esc(T("The counties with the most votes: votes cast, and the share of the line with the most"))}">${rows}</ol>${key}`;
    const back = `<h3 class="cd-bh" tabindex="-1">${T("Worked out from the county figures")}</h3>
<p>${den ? T("The {ntop} counties with the most votes cast {top} of the {den} votes in the county figures: {share}.", {ntop: num(ntop), top: num(topVotes), den: num(den), share: pct(share)}) : ""}
${won.length ? T("“Most votes in a county” is a plain comparison of that county’s own figures: {list}.", {list: won.map(([n, v]) => `${esc(n)} ${num(v)}`).join("; ")}) : ""}
${T("The percentage is <strong>Analysis</strong>, this site’s arithmetic over official figures; the county figures themselves are the office’s.")}</p>
${K.all_done === false ? `<p>${T("Not every county had finished counting in this reading.")}</p>` : ""}
${cant([T("Which counties a line led says nothing about the margin; the whole count decides."), T("A county’s figures cannot show any one ballot.")])}
${links([nb("counties", T("County by county"), `${ID}-k`), nb("splits", T("Blank votes and split results"), `${ID}-k`), addr(L.night()) ? `<a href="${esc(addr(L.night()))}">${T("The county map on Election Night")}</a>` : ""])}`;
    return {q: T("Where did the votes come from?"), tags: [tag("official", T("Official count")), tag("analysis", T("Analysis"))], front, back, link: nb("counties", T("County by county"))};
  }

  /* ---- the forecast */
  function forecastCard(c) {
    const {S, C, F, nb, L} = c;
    const top = F.top.filter(x => x && x.n).slice().sort((a, b) => (+b.ch || 0) - (+a.ch || 0));
    const fav = top[0], other = top[1] || null;
    const ch = +fav.ch || 0;
    const chance = String(V.chance(ch));
    const m = /\d+/.exec(chance);
    const chanceHtml = m ? esc(chance.slice(0, m.index)) + nUp(m[0], +m[0], 0) + esc(chance.slice(m.index + m[0].length)) : esc(chance);
    const l80 = +fav.l80 || 0, h80 = +fav.h80 || 0, l95 = +fav.l95 || 0, h95 = +fav.h95 || 0, md = +fav.md || 0;
    const before = F.at && S.date ? String(F.at).slice(0, 10) < String(S.date) : false;
    const runDay = F.at ? monDay(F.at) : "";
    const whenRun = before ? T("in its last run before Election Day{day}", {day: runDay ? ` (${esc(runDay)})` : ""}) : T("in its latest run{day}", {day: runDay ? ` (${esc(runDay)})` : ""});
    const fn = esc(fav.n), fl = esc(last(fav.n));
    const cnt = C ? C.cands.find(x => x && x.n === fav.n) : null;
    const share = cnt ? +cnt.share || 0 : null;
    const fact = `<p class="cd-fact">${chanceHtml}<small>${T("the model’s chance for {name}, {when}", {name: fn, when: whenRun})}</small></p>`;
    let s;
    if (share != null) {
      const in80 = l80 <= share && share <= h80, in95 = l95 <= share && share <= h95;
      const where = in80 ? T("inside the likely range.")
                  : in95 ? T("{side} the likely range, though inside the wider one.", {side: share > h80 ? T("above") : T("below")})
                  : T("{side} even the wider range. That is a miss, and it counts in the track record.", {side: share > h95 ? T("above") : T("below")});
      s = T("It expected {name} to take {l} to {h} of the vote, {md} in the middle. The count has {name} at <b>{share}</b>, {where}", {name: fl, l: pct(l80), h: pct(h80), md: pct(md), share: pct(share), where});
    } else {
      s = T("It expects {name} to take {l} to {h} of the vote, {md} in the middle.", {name: fl, l: pct(l80), h: pct(h80), md: pct(md)});
      if (other) s += " " + T("{name}’s chance is {chance}.", {name: esc(other.n), chance: esc(String(V.chance(+other.ch || 0)))});
    }
    const lo = Math.min(l95, share == null ? l95 : share) - 3, hi = Math.max(h95, share == null ? h95 : share) + 3, span = (hi - lo) || 1;
    const pos = v => 100 * (v - lo) / span, px = v => `${pos(v).toFixed(2)}%`, wd = (a, b) => `${(100 * (b - a) / span).toFixed(2)}%`;
    const tcls = share == null ? "" : "lb t" + (pos(share) > 72 ? " r" : pos(share) < 28 ? " l" : "");
    const range = `<div class="cd-range" aria-hidden="true">
${share == null ? "" : `<span class="${tcls}" style="left:${px(share)}">${T("the count {share}", {share: pct(share)})}</span>`}
<span class="ax"></span><span class="b95" style="left:${px(l95)};width:${wd(l95, h95)}"></span><span class="b80" style="left:${px(l80)};width:${wd(l80, h80)}"></span><span class="md" style="left:${px(md)}"></span>
${share == null ? "" : `<span class="ct" style="left:${px(share)}"></span>`}
<span class="lb d" style="left:${px(l95)}">${pct(l95)}</span><span class="lb d" style="left:${px(md)}">${pct(md)}</span><span class="lb d" style="left:${px(h95)}">${pct(h95)}</span></div>
<p class="cd-rkey" aria-hidden="true"><span><i class="k80"></i>${T("80 in 100")}</span><span><i class="k95"></i>${T("95 in 100")}</span><span><i class="kmd"></i>${T("middle")}</span>${share == null ? "" : `<span><i class="kct"></i>${T("the count")}</span>`}</p>`;
    const tr = F.track && typeof F.track === "object" ? F.track : null;
    let track;
    if (tr && +tr.races > 0) {
      track = T("Track record: in {races} earlier races of this kind, the favourite had the most votes in {fav}; the result fell inside the 80-in-100 range {h80} times and inside the 95-in-100 range {h95} times; shares were off by {mae} points on average.",
                {races: num(tr.races), fav: num(tr.fav), h80: num(tr.h80), h95: num(tr.h95), mae: esc(String(tr.mae == null ? "" : tr.mae))});
      if (tr.thin) track += " " + T("That record is thin: few races to test on.");
    } else track = T("Its track record is not on file for this race.");
    const front = `${fact}<p class="cd-say">${s}</p>${range}
<p class="cd-fine">${T("Analysis, not a result. Range for {name}: {l80} to {h80} in 80 of 100 simulated elections, {l95} to {h95} in 95 of 100.", {name: fl, l80: pct(l80), h80: pct(h80), l95: pct(l95), h95: pct(h95)})} ${track}</p>`;
    const hist = Array.isArray(F.hist) ? F.hist.filter(h => h && h.at) : [];
    const runs = hist.length > 1 ? T(", run {k} times from {a} to {b}", {k: num(hist.length), a: esc(monDay(hist[0].at)), b: esc(monDay(hist[hist.length - 1].at))}) : "";
    const draws = +F.draws > 0 ? T(", {draws} simulated elections", {draws: num(F.draws)}) : "";
    const back = `<h3 class="cd-bh" tabindex="-1">${share == null ? T("A model’s estimate, and how to read it") : T("A model’s estimate, and its miss or its hit")}</h3>
<p>${T("The forecast is <strong>Analysis</strong>: a computer model’s estimate from past results and polls by members of AAPOR’s Transparency Initiative{draws}{runs}.", {draws, runs})}
${share == null ? "" : T("The count’s {share} for {name} is {io} its 95-in-100 range ({l} to {h}){miss}.", {share: pct(share), name: fl, io: (l95 <= share && share <= h95) ? T("inside") : T("outside"), l: pct(l95), h: pct(h95), miss: (l95 <= share && share <= h95) ? "" : T(": a miss, counted in the track record and not explained away")})}</p>
<p>${track}</p>
${F.env ? `<p>${T("In the model’s own words: {env}", {env: esc(F.env)})}</p>` : ""}
${cant([T("A forecast is not a result: the official count decides."), T("A chance of {chance} is not a promise.", {chance: esc(chance)})])}
${links([nb("forecast", T("The forecast, worked out"), `${ID}-f`), nb("forecast/how", T("How the model works"), `${ID}-f`), nb("forecast/track", T("Its track record"), `${ID}-f`), nb("forecast/runs", T("Every run"), `${ID}-f`),
         addr(L.chart()) ? `<a href="${esc(addr(L.chart()))}">${T("The chart, every run")}</a>` : ""])}`;
    return {q: share == null ? T("What does the forecast say?") : T("What did the forecast say beforehand?"), tags: [tag("analysis", T("Analysis"))], front, back, link: nb("forecast", T("The forecast, worked out"))};
  }

  /* ---- the polls */
  function pollsCard(c) {
    const {C, P, partisan, nb, L} = c;
    const polls = P.newest.filter(p => p && p.pollster);
    const n = Math.max(+P.n || 0, polls.length), other = +P.other || 0;
    const first = polls[0];
    const topTwo = p => Object.entries(p.shares && typeof p.shares === "object" ? p.shares : {}).filter(([k, v]) => k && v != null).sort((a, b) => b[1] - a[1]).slice(0, 2);
    const dates = p => (p.start && p.end ? T("{a} to {b}", {a: esc(monDay(p.start)), b: esc(monDay(p.end))}) : esc(monDay(p.end || p.start)));
    const sample = p => [p.n ? T("{n} {pop}", {n: num(p.n), pop: esc(p.pop || T("people"))}) : (p.pop ? esc(p.pop) : ""), p.moe != null && p.moe !== "" ? T("margin ±{moe} points", {moe: esc(String(p.moe))}) : ""].filter(Boolean).join("; ");
    const fact = `<p class="cd-fact">${nUp(num(n), n, 0)} <span class="u">${n === 1 ? T("poll") : T("polls")}</span><small>${T("counted, by members of the AAPOR Transparency Initiative")}${other ? `; ${T("{other} more shown apart, not counted", {other: num(other)})}` : ""}</small></p>`;
    const tt = topTwo(first);
    const lines = tt.map(([k, v]) => T("{name} {share}", {name: esc(k), share: pct(v)})).join(", ");
    const pv2 = {pollster: esc(first.pollster), dates: dates(first), sample: sample(first) ? `; ${sample(first)}` : "", lines};
    const s = lines ? T("The newest, by {pollster} ({dates}{sample}): {lines}. A poll measures opinion when it was taken; it is not a forecast.", pv2)
                    : T("The newest is by {pollster} ({dates}{sample}). A poll measures opinion when it was taken; it is not a forecast.", pv2);
    const col = name => { const x = C ? C.cands.find(y => y && y.n === name) : null; const l = c.list.find(y => y.n === name); return pv(partisan, (x && x.code) || (l && l.code) || ""); };
    const rows = polls.slice(0, 3).map(p => {
      const pair = topTwo(p);
      const bars = pair.map(([k, v]) => `<span class="pb"${col(k) ? ` style="--pc:${col(k)}"` : ""}><i style="--w:${Math.max(0, Math.min(100, +v || 0)).toFixed(1)}%"></i><b>${esc(last(k))} ${pct(v)}</b></span>`).join("");
      return `<li><span class="nm">${esc(p.pollster)} <span>${dates(p)}${p.url ? ` &middot; ${ext(p.url, T("the release"))}` : ""}</span></span><span class="pbs" aria-hidden="true">${bars}</span></li>`;
    }).join("");
    const front = `${fact}<p class="cd-say">${s}</p><ol class="cd-polls" aria-label="${esc(T("The newest polls: pollster, dates, and the two largest shares"))}">${rows}</ol>`;
    const back = `<h3 class="cd-bh" tabindex="-1">${T("Which polls are counted")}</h3>
<p>${T("We count only polls from members of the American Association for Public Opinion Research’s Transparency Initiative.")} ${other ? T("{other} published polls by others are shown apart and never averaged.", {other: num(other)}) : ""} ${T("Each poll is checked against the pollster’s own release, linked here.")}</p>
${cant([T("A margin of error covers sampling alone, not every way a poll can miss."), T("A poll is opinion when it was taken, not a count.")])}
${links([nb("polls", T("Every poll"), `${ID}-p`), nb("method/polls", T("How polls are chosen"), `${ID}-p`), L.hasFull && L.hasFull("polls") ? `<a href="${esc(addr(L.full("polls")))}">${T("The polls on the full page")}</a>` : ""])}`;
    return {q: C ? T("What did the polls say?") : T("What do the polls say?"), tags: [tag("polls", T("Polls, as published"))], front, back, link: nb("polls", T("Every poll"))};
  }

  /* ---- who called it, what the candidates said */
  function calledCard(c) {
    const {X, calls, said, nb, L} = c;
    const q = calls.length && said.length ? T("Who called it, and what did the candidates say?") : calls.length ? T("Who called it?") : T("What did the candidates say?");
    let fact, s;
    if (calls.length) {
      const f0 = calls[0];
      fact = `<p class="cd-fact">${nUp(num(calls.length), calls.length, 0)} <span class="u">${calls.length === 1 ? T("call") : T("calls")}</span><small>${T("the first by {outlet}, for {name}{when}", {outlet: esc(f0.o), name: esc(f0.n), when: f0.t ? `, ${esc(String(V.when(f0.t)))}` : ""})}</small></p>`;
      const names = joinList([...new Set(calls.map(x => x.n))].map(esc));
      const each = calls.map(x => T("{outlet}{when}{by}", {outlet: esc(x.o), when: x.t ? ` ${T("at {time}", {time: esc(String(V.when(x.t)))})}` : "", by: x.by && x.by !== x.o ? ` (${T("as reported by {by}", {by: esc(x.by)})})` : ""})).join(", ");
      s = T("{k} news organizations called it for <b>{names}</b>: {each}. The Civic Archive does not call races; the certified count decides.", {k: num(calls.length), names, each});
    } else {
      fact = `<p class="cd-fact">${T("No call listed")}<small>${T("no news organization on file has called this race")}</small></p>`;
      s = T("The Civic Archive does not call races; the certified count decides.");
    }
    const callRows = calls.map(x => `<li><span class="t">${x.t ? esc(String(V.when(x.t))) : esc(x.o)}</span><span class="w">${x.t ? `${esc(x.o)}, ` : ""}${T("for {name}", {name: esc(x.n)})}${x.u ? ` &middot; ${ext(x.u, T("the report"))}` : ""}</span></li>`).join("");
    const saidRows = said.map(sd => {
      const parts = sd.s.filter(Boolean).map(x => {
        const kind = T(KIND[x.k] || "Statement"), medium = T(MEDIUM[x.m] || "text");
        const inner = [medium, x.d ? esc(monDay(x.d)) : "", x.u ? ext(x.u, esc(x.by || T("link"))) : (x.by ? esc(x.by) : "")].filter(Boolean).join(", ");
        return `${kind} (${inner})`;
      });
      return `<li><span class="t">${esc(last(sd.n))}</span><span class="w">${parts.join("; ")}</span></li>`;
    }).join("");
    const front = `${fact}<p class="cd-say">${s}</p>
${calls.length ? `<p class="cd-h">${T("Who called it")}</p><ul class="cd-list">${callRows}</ul>` : ""}
${said.length ? `<p class="cd-h">${T("What the candidates said: their words, linked")}</p><ul class="cd-list">${saidRows}</ul>` : ""}`;
    const nn = Array.isArray(X.n) ? X.n : [];
    const back = `<h3 class="cd-bh" tabindex="-1">${T("Links only: nothing is copied")}</h3>
<p>${T("A call is a news organization’s judgment, made before every ballot is counted; this site records who called the race and when, and marks a result final only when it is certified. Each statement is the candidate’s own, behind a link to the outlet or account that carried it.")}${X.checked ? ` ${T("Links were checked on {day}.", {day: esc(String(V.day(X.checked)))})}` : ""}</p>
${nn[0] > 0 ? `<p>${T("{n} news stories are linked under their outlets’ own headlines on the race page’s Coverage tab.", {n: num(nn[0])})}</p>` : ""}
${cant([T("A candidate with no statement listed is not mentioned."), T("A call is not a result.")])}
${links([nb("coverage", T("Coverage: calls and statements"), `${ID}-v`), nb("coverage/calls", T("Every call"), `${ID}-v`), nb("coverage/said", T("What each candidate said"), `${ID}-v`), nb("method/calls", T("Why this site never calls a race"), `${ID}-v`),
         addr(L.tab("coverage")) ? `<a href="${esc(addr(L.tab("coverage")))}">${T("The Coverage tab")}</a>` : ""])}`;
    return {q, tags: [tag("links", T("Links only"))], front, back, link: nb("coverage", T("Coverage, in the notebook"))};
  }

  /* ---- in the news */
  function newsCard(c) {
    const {news, tiers, newsN, nb, L} = c;
    const label = {national: T("National"), state: T("State"), local: T("Local")};
    const counts = tiers.map(k => T("{n} {tier}", {n: num(Math.max(+news[k].n || 0, (news[k].top || []).length)), tier: label[k].toLowerCase()})).join(", ");
    const fact = `<p class="cd-fact">${nUp(num(newsN), newsN, 0)} <span class="u">${newsN === 1 ? T("story") : T("stories")}</span><small>${counts}</small></p>`;
    const s = T("Each headline below is the outlet’s own, linked; nothing is copied beyond it. A headline can say more than the count does.");
    const blocks = tiers.map(k => {
      const items = (news[k].top || []).filter(x => x && x.h && x.o).slice(0, 2);
      if (!items.length) return "";
      return `<p class="cd-h">${label[k]}</p><ul class="cd-list cd-news">${items.map(x => `<li><span class="t">${esc(x.o)}</span><span class="w">${ext(x.u, esc(x.h))}${x.t ? ` <span class="d">${esc(monDay(x.t))}</span>` : ""}</span></li>`).join("")}</ul>`;
    }).join("");
    const front = `${fact}<p class="cd-say">${s}</p>${blocks}`;
    const back = `<h3 class="cd-bh" tabindex="-1">${T("The outlets’ words")}</h3>
<p>${T("Headlines are the outlets’ own words, not this site’s; each story opens on its own page. Stories are grouped by whether the outlet reports nationally, for the state, or for a place in it.")}</p>
${cant([T("A headline can say “wins” before a result is certified; this site’s own words do not."), T("The stories listed are a reading of the coverage, not all of it.")])}
${links([nb("coverage/news", T("Every story listed"), `${ID}-n`), nb("coverage", T("Coverage, in the notebook"), `${ID}-n`), addr(L.tab("coverage")) ? `<a href="${esc(addr(L.tab("coverage")))}">${T("The Coverage tab")}</a>` : ""])}`;
    return {q: T("What is the news saying?"), tags: [tag("links", T("Links only"))], front, back, link: nb("coverage/news", T("Every story listed"))};
  }

  /* ---- who is on the ballot */
  function listCard(c) {
    const {S, C, kind, seats, partisan, list, nb, L} = c;
    const ls = S.list_source && typeof S.list_source === "object" ? S.list_source : {};
    const agency = esc(ls.agency || ""), ltitle = esc(ls.title || "");
    const office = esc(S.office || ""), place = esc(S.place || "");
    const where = office && place ? T("{office} in {place}", {office, place}) : office || place;
    let q, fact, s;
    const special = S.special ? ` ${T("This is a special election.")}` : "";
    if (kind === "none" || !list.length) {
      q = T("Is anyone on the list?");
      fact = `<p class="cd-fact">${T("No one")}<small>${T("the official list names no candidate for this office")}</small></p>`;
      s = T("{where}: the official list carries no candidate.{special} The ballot a voter gets comes from the county; it is the authority for what is printed.", {where: where || T("This office"), special});
    } else if (kind === "retention") {
      q = T("Who is the vote about?");
      const n0 = esc(list[0].n);
      fact = `<p class="cd-fact">${n0}<small>${T("a yes-or-no vote on keeping the office")}</small></p>`;
      s = T("{where}: voters answer yes or no to {name} keeping the office. No one runs against them.{special}", {where: where || T("This vote"), name: n0, special});
    } else if (kind === "unopposed") {
      q = C ? T("Who was on the ballot?") : T("Who is on the ballot?");
      const names = joinList(list.map(x => `<b>${esc(x.n)}</b>`));
      fact = `<p class="cd-fact">${esc(list[0].n)}${list.length > 1 ? `<small>${T("and {k} more, all unopposed", {k: num(list.length - 1)})}</small>` : `<small>${T("no one runs against them")}</small>`}</p>`;
      s = T("{where}: {names}, with no one running against them.{special}", {where: where || T("This office"), names, special});
    } else {
      q = C ? T("Who was on the ballot?") : T("Who is on the ballot?");
      fact = `<p class="cd-fact">${nUp(num(list.length), list.length, 0)} <span class="u">${list.length === 1 ? T("name") : T("names")}</span><small>${T("on the official list, in its order")}${seats > 1 ? `; ${T("vote for {seats}", {seats: num(seats)})}` : ""}</small></p>`;
      s = where ? T("{where}.{special}", {where, special}) : "";
      if (seats > 1) s += " " + T("The {seats} with the most votes take the seats.", {seats: num(seats)});
      if (!partisan) s += " " + T("No party is printed beside the names: this is a nonpartisan office.");
    }
    const h = S.holder && typeof S.holder === "object" && S.holder.n ? S.holder : null;
    if (h && kind !== "none") {
      const hp = partisan && h.party ? ` (${esc(h.party)})` : "";
      s += " " + (h.running ? T("{name}{party} holds the seat today and is on the list.", {name: esc(h.n), party: hp}) : T("{name}{party} holds the seat today and is not running.", {name: esc(h.n), party: hp}));
    }
    const rows = list.map(x => {
      const marks = [x.inc ? T("serves in this seat today") : "", x.wi ? T("write-in") : "", x.out ? esc(String(x.out)) : ""].filter(Boolean).join(" &middot; ");
      const sub = [partisan && x.party ? esc(x.party) : "", marks].filter(Boolean).join(" &middot; ");
      return `<li class="cd-row cd-name${pv(partisan, x.code) ? "" : " np"}"${pv(partisan, x.code) ? ` style="--pc:${pv(partisan, x.code)}"` : ""}><span class="band" aria-hidden="true"></span><span class="who">${esc(x.n)}${sub ? ` <span>${sub}</span>` : ""}</span><span class="val">${x.order != null && x.order !== "" ? `<span class="ord">${esc(String(x.order))}</span>` : ""}</span></li>`;
    }).join("");
    const front = `${fact}<p class="cd-say">${s}</p>${rows ? `<ol class="cd-rows cd-names" aria-label="${esc(T("The official list, in its order"))}">${rows}</ol>` : ""}`;
    const back = `<h3 class="cd-bh" tabindex="-1">${T("The official list")}</h3>
<p>${agency ? T("The names are as {agency} lists them{title}.", {agency, title: ltitle ? ` (${ltitle})` : ""}) : T("The names are as the official list gives them.")} ${partisan ? T("A party is printed beside each name.") : T("No party is printed: this is a nonpartisan office.")}${seats > 1 ? ` ${T("Voters choose up to {seats}.", {seats: num(seats)})}` : ""}</p>
${cant([T("The list is as filed; a withdrawal after printing may not show."), T("The county’s printed ballot is the authority for what a voter sees.")])}
${links([nb("list", T("The list, with its source"), `${ID}-l`), nb("primaries", T("The primaries"), `${ID}-l`), nb("method/sources", T("Where the facts come from"), `${ID}-l`),
         L.hasFull && L.hasFull("arena") ? `<a href="${esc(addr(L.full("arena")))}">${T("The candidates on the full page")}</a>` : ""])}`;
    return {q, tags: [tag("record", T("Official record"))], front, back, link: nb("list", T("The list, with its source"))};
  }

  /* ---- what happens before it is final */
  function stepsCard(c) {
    const {S, C, office, nb} = c;
    const final = !!(C && C.final);
    const now = !C ? 0 : final ? 3 : 1;
    const rep = C ? reporting(C) : null;
    const day = S.date ? esc(String(V.day(S.date))) : "";
    const when = C && C.at ? esc(String(V.when(C.at))) : "";
    let fact;
    if (!C) fact = `<p class="cd-fact">${T("Not counted yet")}<small>${day ? T("votes are counted after the polls close on Election Day, {day}", {day}) : T("votes are counted after the polls close on Election Day")}</small></p>`;
    else if (final) fact = `<p class="cd-fact">${T("Certified")}<small>${T("the result is final; the figures on these cards are the certified count")}</small></p>`;
    else fact = `<p class="cd-fact">${T("Not final yet")}<small>${when ? T("the count on these cards is the first count, as reported {when}", {when}) : T("the count on these cards is the first count, as reported")}</small></p>`;
    const s = !C ? T("Election night figures are a first count. The result is final when the election office certifies it, after each county has checked its ballots.")
            : final ? T("The count went through every step below. A certified result can still be recounted or challenged where state law allows it.")
            : T("Election night figures are a first count. The result is final when the election office certifies it, after each county has checked its ballots. Until then the figures can change.");
    const first = C ? (rep ? (rep[0] >= rep[1] ? T("In this race every precinct has reported.") : T("In this race {in} of {of} precincts have reported.", {in: num(rep[0]), of: num(rep[1])})) : "") : "";
    const steps = [
      [T("Election Day"), day ? T("{day}. Polls close and the count begins.", {day}) : T("Polls close and the count begins.")],
      [T("The first count"), `${T("Precincts report as they count; the office posts running totals. Some mailed and provisional ballots are counted after Election Day.")} ${first}`.trim()],
      [T("The canvass"), T("Each election board checks its count, adds the ballots that could not be counted on the night, and approves its results.")],
      [T("Certification"), office ? T("{office} certifies the result. This site marks a figure “as certified” only then.", {office: esc(office.charAt(0).toUpperCase() + office.slice(1))}) : T("The election office certifies the result. This site marks a figure “as certified” only then.")],
      [T("Recounts and challenges"), T("A close race can be recounted under state law, and candidates can go to court. A concession is a custom, not a legal step: it ends no count.")]
    ];
    const ol = `<ol class="cd-steps">${steps.map(([b, w], i) => `<li${i === now ? ' class="now"' : ""}><b>${b}${i === now ? `<span class="nowtag">${C ? T("these cards") : T("next")}</span>` : ""}</b><span>${w}</span></li>`).join("")}</ol>`;
    const front = `${fact}<p class="cd-say">${s}</p>${ol}`;
    const back = `<h3 class="cd-bh" tabindex="-1">${T("How it works, in every state")}</h3>
<p>${T("These are the steps a count goes through everywhere; each state sets its own dates and rules, and this card repeats none of them. The marked step is where the figures on these cards come from; this site does not say which later step a county has reached.")}</p>
${cant([T("It gives no dates beyond Election Day’s."), T("It says nothing about whether any count will be challenged.")])}
${links([nb("method/labels", T("What the labels mean"), `${ID}-s`), nb("count", T("The full count"), `${ID}-s`), nb("method/calls", T("Why this site never calls a race"), `${ID}-s`)])}`;
    return {q: C ? (final ? T("Is it final?") : T("What happens before it is final?")) : T("What happens next?"), tags: [tag("how", T("How it works"))], front, back, link: nb("method/labels", T("What the labels mean"))};
  }

  /* ---- where next */
  function nextCard(c, n) {
    const {S, L, C, X, nb} = c;
    const item = (href, kicker, text) => (href ? `<li><a href="${esc(href)}"><span>${kicker}</span><b>${text}</b></a></li>` : "");
    const nbHref = path => { try { return L.has(path) ? addr(String(L.nb(path, "x", {}))) : ""; } catch (e) { return ""; } };
    const items = [
      item(L.hasFull && L.hasFull("tabs") ? addr(L.full("tabs")) : "", T("On The Ballot"), T("The full page")),
      item(addr(L.night()), T("Election Night"), T("The count and the county map")),
      item(addr(L.chart()), T("Forecasts"), T("The chart, every run")),
      item(X ? addr(L.tab("coverage")) : "", T("Coverage"), T("Calls, statements, news")),
      item(addr(L.past()), T("Past results"), T("This seat before")),
      item(nbHref(C ? "count" : "list"), T("The notebook"), C ? T("The count, with sources") : T("The list, with its source")),
      item(nbHref("method/labels"), T("The notebook"), T("What the labels mean")),
      item(addr(L.view("front")), T("Another way to read it"), T("The Front Page")),
      item(addr(L.view("split")), T("Another way to read it"), T("Workbench")),
      item(addr(L.view("timeline")), T("Another way to read it"), T("The story so far"))
    ].filter(Boolean);
    const front = `<p class="cd-fact">${T("Where next?")}<small>${T("the same race, in full, on the site and in the notebook")}</small></p>
<p class="cd-say">${T("{n} cards hold the short of it. Everything behind them is one tap away.", {n: num(n)})}</p>
${items.length ? `<ul class="cd-ways">${items.join("")}</ul>` : ""}`;
    const back = `<h3 class="cd-bh" tabindex="-1">${T("About these cards")}</h3>
<p>${S.read ? T("The figures were read from this site’s own records on {day}: the official list, the count, the forecast, the polls and the coverage, whichever this race has. Nothing is typed in.", {day: esc(String(V.day(S.read)))})
            : T("The figures come from this site’s own records: the official list, the count, the forecast, the polls and the coverage, whichever this race has. Nothing is typed in.")}</p>
${links([nb("method/sources", T("Where the facts come from"), `${ID}-w`), nb("method/labels", T("What the labels mean"), `${ID}-w`)])}`;
    return {q: T("Where next?"), tags: [], front, back, link: nb("method/sources", T("Where the facts come from")), again: true};
  }

  /* ---------- the page ---------- */
  function render(S, L) {
    const cards = build(S, L);
    const n = cards.length;
    const kick = [esc(S.office || ""), esc(S.place || ""), S.date ? esc(String(V.day(S.date))) : "", S.special ? T("Special election") : ""].filter(Boolean).join(" &middot; ");
    const titleText = String(S.title || [S.office, S.place].filter(Boolean).join(", ") || T("This race"));
    const title = esc(titleText);
    const deckLabel = esc(T("{title}, one card at a time", {title: titleText}));
    const items = cards.map((cd, i0) => {
      const i = i0 + 1;
      const again = cd.again ? `<button type="button" class="cd-again">${T("Start the cards again")}</button>` : "";
      return `<li class="cd-card" id="${ID}-c${i}" tabindex="-1">
<div class="cd-flip">
<section class="cd-face cd-front" aria-labelledby="${ID}-c${i}-q">
<div class="cd-main"><div class="cd-top"><h3 class="cd-q" id="${ID}-c${i}-q"><span class="cd-no" aria-hidden="true">${i}</span><span class="cd-sr">${T("Card {i} of {n}.", {i, n})} </span><span class="cd-qt">${cd.q}</span></h3>${tags(cd.tags)}</div>
${cd.front}</div>
<div class="cd-foot">${cd.link || ""}${again}<button type="button" class="cd-turn" aria-label="${esc(T("Turn the card over: how we know"))}">${TURN}${T("How we know")}</button></div>
</section>
<section class="cd-face cd-back" aria-label="${esc(T("Card {i}, the back: how we know", {i}))}">
<div class="cd-main"><p class="cd-q"><span class="cd-no" aria-hidden="true">${i}</span><span class="cd-qt">${T("How we know")}</span></p>
${cd.back}</div>
<div class="cd-foot"><span class="cd-src">${T("Card {i} of {n}", {i, n})}</span><button type="button" class="cd-turn" aria-label="${esc(T("Turn the card back to the front"))}">${TURN}${T("Back to the card")}</button></div>
</section>
</div></li>`;
    }).join("");
    const segs = cards.map((cd, i0) => {
      const i = i0 + 1;
      return `<button type="button" class="cd-seg" role="tab" id="${ID}-s${i}" aria-controls="${ID}-c${i}" aria-selected="${i === 1 ? "true" : "false"}" tabindex="${i === 1 ? 0 : -1}" title="${i}. ${esc(cd.q.replace(/<[^>]+>/g, ""))}"><span class="cd-sr">${T("Card {i}: {q}", {i, q: cd.q})}</span><i aria-hidden="true"><b></b></i></button>`;
    }).join("");
    return `<div class="cd" data-cd>
<header class="cd-head">${kick ? `<p class="cd-kick">${kick}</p>` : ""}
<h2 class="cd-title">${T("One card at a time")}</h2>
<p class="cd-lede">${T("{n} cards, one question each. Swipe or drag, use the arrows, or press <kbd>←</kbd> and <kbd>→</kbd>. Turn any card over for how we know.", {n: num(n)})}</p></header>
<section class="cd-deck" aria-roledescription="carousel" aria-label="${deckLabel}">
<div class="cd-tools"><p class="cd-where"><strong>${T("Card {i} of {n}", {i: 1, n})}</strong><span class="cd-wq">${cards[0].q}</span></p>
<button type="button" class="cd-sw" aria-pressed="false"><span class="sw-k" aria-hidden="true"></span>${T("Show all cards as a list")}</button></div>
<div class="cd-stage"><ol class="cd-track">${items}</ol></div>
<div class="cd-nav"><button type="button" class="cd-arr cd-prev" aria-label="${esc(T("Previous card"))}" aria-disabled="true">${ARROW_L}</button>
<div class="cd-rail" role="tablist" aria-label="${esc(T("Pick a card"))}">${segs}</div>
<button type="button" class="cd-arr cd-next" aria-label="${esc(T("Next card"))}" aria-disabled="${n > 1 ? "false" : "true"}">${ARROW_R}</button></div>
<p class="cd-sr cd-live" aria-live="polite" aria-atomic="true"></p>
</section></div>`;
  }

  /* ---------- the deck's behaviour: drag with inertia and a settle, the rail, the keys, the flip ---------- */
  function wire(root, S, L) {
    const $ = (s, el = root) => el.querySelector(s), $$ = (s, el = root) => Array.from(el.querySelectorAll(s));
    const html = document.documentElement;
    const cd = $(".cd"), deckEl = $(".cd-deck"), stage = $(".cd-stage"), track = $(".cd-track"), cards = $$(".cd-card");
    const segs = $$(".cd-seg"), prev = $(".cd-prev"), next = $(".cd-next"), where = $(".cd-where"), sw = $(".cd-sw"), live = $(".cd-live");
    const N = cards.length;
    if (!cd || !stage || !track || !N) return () => {};
    const offs = [];
    const on = (el, ev, fn, opt) => { el.addEventListener(ev, fn, opt); offs.push(() => el.removeEventListener(ev, fn, opt)); };
    const store = {
      get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
      set(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* kept for this visit only */ } },
      sget(k) { try { return sessionStorage.getItem(k); } catch (e) { return null; } },
      sset(k, v) { try { sessionStorage.setItem(k, v); } catch (e) { /* fine */ } }
    };
    const readJSON = s => { try { const j = JSON.parse(s || "null"); return j && typeof j === "object" ? j : {}; } catch (e) { return {}; } };
    const LIST = "tca.view.cards.v1", AT = "tca.view.cards.at", rid = String(S.id || "race");
    const reduce = window.matchMedia ? matchMedia("(prefers-reduced-motion: reduce)") : null;
    const motion = () => {
      try { if (V.calm()) return false; } catch (e) { return false; }
      return html.getAttribute("data-motion") === "full" && html.getAttribute("data-calm") !== "on" && !html.classList.contains("calm") && !(reduce && reduce.matches);
    };
    const question = i => { const q = cards[i].querySelector(".cd-q .cd-qt"); return q ? q.textContent : ""; };
    let cur = 0, deck = true, first = true, suppressClick = false, raf = 0, pos = 0;

    /* each card's two faces: the hidden one is inert and hidden from assistive technology */
    function faces(card) {
      const f = card.querySelector(".cd-front"), b = card.querySelector(".cd-back"), back = card.classList.contains("is-back");
      const hide = (el, hidden) => { if (!el) return; el.inert = hidden; if (hidden) el.setAttribute("aria-hidden", "true"); else el.removeAttribute("aria-hidden"); };
      hide(f, deck && back); hide(b, deck && !back);
    }
    /* the 3D turn is drawn only when the page's motion settings allow it, and then by this script alone */
    function sync3d() {
      const m = motion();
      cd.classList.toggle("cd-3d", m);
      cards.forEach(c => {
        const fl = c.querySelector(".cd-flip");
        if (!fl) return;
        fl.classList.remove("is-turning");
        fl.style.transform = m && deck ? `rotateY(${c.classList.contains("is-back") ? 180 : 0}deg)` : "";
      });
    }
    const xFor = i => { const c = cards[i]; return (stage.clientWidth - c.offsetWidth) / 2 - c.offsetLeft; };
    function setX(x) { pos = x; track.style.transform = deck ? `translate3d(${Math.round(x * 100) / 100}px,0,0)` : ""; }
    function cancelAnim() { if (raf) { cancelAnimationFrame(raf); raf = 0; } }
    /* a spring carries the deck to the card: the flick's speed goes in, and the card settles with a touch of give */
    function settle(i, v0) {
      cancelAnim();
      if (!deck) { setX(0); return; }
      if (!motion()) { setX(xFor(i)); return; }
      let x = pos, v = (v0 || 0) * 1000, lastT = performance.now();
      const k = 170, damp = 2 * Math.sqrt(k) * 0.82;
      const step = now => {
        const dt = Math.min(0.034, Math.max(0.001, (now - lastT) / 1000));
        lastT = now;
        const target = xFor(i);
        v += (-k * (x - target) - damp * v) * dt;
        x += v * dt;
        if (Math.abs(x - target) < 0.4 && Math.abs(v) < 12) { setX(target); raf = 0; return; }
        setX(x);
        raf = requestAnimationFrame(step);
      };
      raf = requestAnimationFrame(step);
    }
    function place() { if (!deck) { track.style.transform = ""; track.style.height = ""; return; } cancelAnim(); setX(xFor(cur)); fit(); }
    /* the stage is as tall as the face it shows */
    function fit() {
      if (!deck) return;
      const c = cards[cur], f = c.querySelector(c.classList.contains("is-back") ? ".cd-back" : ".cd-front");
      const h = f ? f.offsetHeight : 0;
      if (h && track.style.height !== h + "px") track.style.height = h + "px";
    }
    /* numbers count up the first time a card is seen, only with motion on */
    function countUp(card) {
      card.querySelectorAll(".cd-n[data-n]").forEach(el => {
        if (el.dataset.done) return;
        el.dataset.done = "1";
        if (!motion()) return;
        const end = parseFloat(el.dataset.n), d = +el.dataset.d || 0, t0 = performance.now(), dur = 950;
        if (!isFinite(end)) return;
        const fmt = v => v.toLocaleString("en-US", {minimumFractionDigits: d, maximumFractionDigits: d});
        const step = now => {
          const p = Math.min(1, (now - t0) / dur), e = 1 - Math.pow(1 - p, 3);
          el.textContent = p < 1 ? fmt(end * e) : el.dataset.t;
          if (p < 1) requestAnimationFrame(step);
        };
        el.textContent = fmt(0);
        requestAnimationFrame(step);
      });
    }
    function apply() {
      cards.forEach((c, i) => {
        const isOn = i === cur;
        c.classList.toggle("is-on", isOn);
        if (deck) {
          c.setAttribute("role", "tabpanel");
          c.setAttribute("aria-roledescription", T("card"));
          c.setAttribute("aria-labelledby", `${ID}-c${i + 1}-q`);
          c.inert = !isOn;
          if (isOn) c.removeAttribute("aria-hidden"); else c.setAttribute("aria-hidden", "true");
        } else {
          c.removeAttribute("role"); c.removeAttribute("aria-roledescription"); c.removeAttribute("aria-labelledby");
          c.inert = false; c.removeAttribute("aria-hidden");
        }
        faces(c);
      });
      segs.forEach((s, i) => {
        s.setAttribute("aria-selected", i === cur ? "true" : "false");
        s.tabIndex = i === cur ? 0 : -1;
        if (i === cur) s.classList.add("seen");
      });
      if (prev) prev.setAttribute("aria-disabled", cur === 0 ? "true" : "false");
      if (next) next.setAttribute("aria-disabled", cur === N - 1 ? "true" : "false");
      if (where) { const st = where.querySelector("strong"), wq = where.querySelector(".cd-wq"); if (st) st.textContent = T("Card {i} of {n}", {i: cur + 1, n: N}); if (wq) wq.textContent = question(cur); }
      if (deck) countUp(cards[cur]);
      const at = readJSON(store.sget(AT)); at[rid] = cur; store.sset(AT, JSON.stringify(at));
    }
    function go(i, opts = {}) {
      i = Math.max(0, Math.min(N - 1, i));
      if (i === cur) { settle(cur, opts.v || 0); return; }
      const was = document.activeElement, insideOld = was && cards[cur].contains(was);
      cur = i;
      apply();
      fit();
      settle(cur, opts.v || 0);
      if (opts.focusSeg) segs[cur].focus({preventScroll: true});
      else if (insideOld || opts.focusCard) cards[cur].focus({preventScroll: true});
      else if (live) live.textContent = T("Card {i} of {n}: {q}", {i: cur + 1, n: N, q: question(cur)});
    }
    function flip(card, toBack) {
      const back = toBack === undefined ? !card.classList.contains("is-back") : toBack;
      card.classList.toggle("is-back", back);
      const fl = card.querySelector(".cd-flip");
      if (fl) {
        if (motion() && deck) {
          fl.classList.add("is-turning");
          card.classList.remove("is-lifting"); void card.offsetWidth; card.classList.add("is-lifting");
          fl.style.transform = `rotateY(${back ? 180 : 0}deg)`;
        } else { fl.classList.remove("is-turning"); fl.style.transform = ""; }
      }
      faces(card);
      fit();
      const target = back ? card.querySelector(".cd-bh") : card.querySelector(".cd-q");
      if (target) { target.tabIndex = -1; target.focus({preventScroll: true}); }
    }
    function setView(list, opts = {}) {
      deck = !list;
      cd.classList.toggle("is-deck", deck);
      if (sw) sw.setAttribute("aria-pressed", list ? "true" : "false");
      const rail = $(".cd-rail"); if (rail) rail.hidden = !deck;
      if (!deck) cards.forEach(c => c.classList.remove("is-back"));
      sync3d();
      apply();
      place();
      if (!opts.silent) store.set(LIST, JSON.stringify({list: !!list}));
      if (!first && !deck) cards[cur].scrollIntoView({block: "start"});
    }

    /* buttons, the rail, the turn */
    if (prev) on(prev, "click", () => go(cur - 1));
    if (next) on(next, "click", () => go(cur + 1));
    segs.forEach((s, i) => on(s, "click", () => go(i, {focusSeg: true})));
    if (sw) on(sw, "click", () => setView(deck));
    on(root, "click", e => {
      const t = e.target.closest(".cd-turn, .cd-again");
      if (!t || !root.contains(t)) return;
      if (t.classList.contains("cd-again")) { go(0, {focusCard: true}); if (deckEl) deckEl.scrollIntoView({block: "start"}); return; }
      flip(t.closest(".cd-card"));
    });
    on(root, "transitionend", e => { if (e.target && e.target.classList && e.target.classList.contains("cd-flip")) e.target.classList.remove("is-turning"); });
    on(root, "animationend", e => { if (e.target && e.target.classList && e.target.classList.contains("cd-card")) e.target.classList.remove("is-lifting"); });

    /* keys: arrows move, Home and End jump, Escape turns a card back */
    on(window, "keydown", e => {
      if (!deck || e.altKey || e.ctrlKey || e.metaKey) return;
      const a = document.activeElement;
      const inside = a && root.contains(a), bodyish = !a || a === document.body || a === html;
      if (!(inside || bodyish)) return;
      if (a && /^(INPUT|TEXTAREA|SELECT)$/.test(a.tagName)) return;
      if (a && a.isContentEditable) return;
      const onSeg = !!(a && a.classList && a.classList.contains("cd-seg"));
      if (e.key === "ArrowRight") { e.preventDefault(); go(cur + 1, {focusSeg: onSeg}); }
      else if (e.key === "ArrowLeft") { e.preventDefault(); go(cur - 1, {focusSeg: onSeg}); }
      else if (e.key === "Home" && inside) { e.preventDefault(); go(0, {focusSeg: onSeg}); }
      else if (e.key === "End" && inside) { e.preventDefault(); go(N - 1, {focusSeg: onSeg}); }
      else if (e.key === "Escape" && inside) { const c = cards[cur]; if (c.classList.contains("is-back")) { e.preventDefault(); flip(c, false); } }
    });

    /* swipe and drag: listeners on the window while a drag lasts, never pointer capture */
    let drag = null;
    const samples = [];
    function endDrag() {
      if (!drag) return;
      drag = null;
      cd.classList.remove("is-dragging");
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
      window.removeEventListener("pointercancel", onCancel);
    }
    function onMove(e) {
      if (!drag || e.pointerId !== drag.id) return;
      const dx = e.clientX - drag.x0, dy = e.clientY - drag.y0;
      if (!drag.moved) {
        if (Math.abs(dx) < 8 && Math.abs(dy) < 8) return;
        if (Math.abs(dy) > Math.abs(dx)) { endDrag(); return; }
        drag.moved = true;
        cd.classList.add("is-dragging");
        cancelAnim();
      }
      drag.dx = dx;
      samples.push([performance.now(), dx]);
      while (samples.length > 6) samples.shift();
      if (motion()) {
        const past = (cur === 0 && dx > 0) || (cur === N - 1 && dx < 0);      /* give at the ends, then a pull back */
        setX(xFor(cur) + (past ? dx * 0.32 : dx));
      }
    }
    function onUp(e) {
      if (!drag || e.pointerId !== drag.id) return;
      const d = drag;
      endDrag();
      if (d.moved) {
        suppressClick = true;
        setTimeout(() => { suppressClick = false; }, 0);
        let v = 0;
        if (samples.length > 1) {
          const a = samples[0], b = samples[samples.length - 1], dt = b[0] - a[0];
          if (dt >= 20) v = Math.max(-3, Math.min(3, (b[1] - a[1]) / dt));      /* px per ms; too short a window says nothing */
        }
        samples.length = 0;
        const need = Math.min(90, stage.clientWidth * 0.18), flick = Math.abs(d.dx) > 24 && Math.abs(v) > 0.45;
        if (d.dx < -need || (flick && v < 0)) go(cur + 1, {v});
        else if (d.dx > need || (flick && v > 0)) go(cur - 1, {v});
        else settle(cur, v);
        return;
      }
      samples.length = 0;
      /* a plain tap beside the card: the neighbour that peeks there */
      const t = e.target && e.target.closest ? e.target : null;
      if (t && t.closest("a, button, input, textarea, select")) return;
      const r = cards[cur].getBoundingClientRect();
      if (e.clientX < r.left) go(cur - 1); else if (e.clientX > r.right) go(cur + 1);
    }
    function onCancel(e) { if (drag && e.pointerId === drag.id) { endDrag(); samples.length = 0; settle(cur, 0); } }
    on(stage, "pointerdown", e => {
      if (!deck || e.button !== 0 || drag) return;
      drag = {id: e.pointerId, x0: e.clientX, y0: e.clientY, dx: 0, moved: false};
      samples.length = 0;
      window.addEventListener("pointermove", onMove);
      window.addEventListener("pointerup", onUp);
      window.addEventListener("pointercancel", onCancel);
    });
    offs.push(endDrag);
    on(stage, "click", e => { if (suppressClick) { e.preventDefault(); e.stopPropagation(); } }, true);
    on(stage, "dragstart", e => e.preventDefault());

    /* the card leans a little toward a mouse pointer, as a card held in the hand would */
    function tilt(e) {
      if (!deck || drag || e.pointerType !== "mouse" || !motion()) return;
      const c = cards[cur], fl = c.querySelector(".cd-flip");
      if (!fl || fl.classList.contains("is-turning")) return;
      const r = c.getBoundingClientRect();
      if (!r.width || !r.height) return;
      const inside = e.clientX >= r.left && e.clientX <= r.right && e.clientY >= r.top && e.clientY <= r.bottom;
      const rx = inside ? Math.max(-1, Math.min(1, (e.clientX - (r.left + r.width / 2)) / (r.width / 2))) : 0;
      const ry = inside ? Math.max(-1, Math.min(1, (e.clientY - (r.top + r.height / 2)) / (r.height / 2))) : 0;
      const back = c.classList.contains("is-back") ? 180 : 0;
      fl.style.transform = `rotateX(${(-ry * 2.2).toFixed(2)}deg) rotateY(${(rx * 3 + back).toFixed(2)}deg)`;
    }
    on(stage, "pointermove", tilt);
    on(stage, "pointerleave", () => { const fl = cards[cur].querySelector(".cd-flip"); if (fl && motion() && !fl.classList.contains("is-turning")) fl.style.transform = `rotateY(${cards[cur].classList.contains("is-back") ? 180 : 0}deg)`; });

    /* the window and the settings */
    let rt = 0;
    on(window, "resize", () => { clearTimeout(rt); rt = setTimeout(() => place(), 60); });
    const observers = [];
    if (window.ResizeObserver) {
      const ro1 = new ResizeObserver(() => place()); ro1.observe(stage); observers.push(ro1);
      const ro2 = new ResizeObserver(() => fit()); $$(".cd-face").forEach(f => ro2.observe(f)); observers.push(ro2);
    }
    const mo = new MutationObserver(() => { sync3d(); place(); });
    mo.observe(html, {attributes: true, attributeFilter: ["data-motion", "data-calm", "data-scale", "data-face", "data-space", "class"]});
    observers.push(mo);
    if (reduce) { const onR = () => { sync3d(); place(); }; if (reduce.addEventListener) { reduce.addEventListener("change", onR); offs.push(() => reduce.removeEventListener("change", onR)); } }
    let gone = false;
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(() => { if (!gone) place(); });

    /* start: where you were in this visit, else the first card; nothing slides on the first frame */
    cd.classList.add("no-anim");
    const saved = readJSON(store.sget(AT))[rid];
    cur = Number.isInteger(saved) && saved >= 0 && saved < N ? saved : 0;
    setView(!!readJSON(store.get(LIST)).list, {silent: true});
    segs.forEach((s, i) => { if (i < cur) s.classList.add("seen"); });
    place();
    requestAnimationFrame(() => { if (gone) return; place(); requestAnimationFrame(() => { if (!gone) cd.classList.remove("no-anim"); }); });
    first = false;

    return () => {
      gone = true;
      cancelAnim();
      clearTimeout(rt);
      observers.forEach(o => { try { o.disconnect(); } catch (e) { /* gone already */ } });
      offs.forEach(f => { try { f(); } catch (e) { /* gone already */ } });
    };
  }

  VIEWS.add({id: "cards", label: "One card at a time", order: 2, render, wire});
})();

/* ======== split ======== */
/* The Workbench (view id "split", order 3): the sandbox's "Workbench with a notes pane" (sandbox_src/layouts/split.py,
   John's pick of 2026-11-11), as a renderer for every race page under views_src/SPEC.md.

   An app-like page: a slim rail of ways around the race, a workspace of tiles, tabs and tables, and a notes pane that
   shows a notebook entry beside the workspace (a sheet from the bottom on a phone). Every figure is a link to its
   notebook entry; with the page wired, a plain click opens that entry in the pane instead (a modifier key still opens the
   notebook itself, and so does the pane's own "Open in the notebook" link). The pane's content comes from
   VIEWS.entry(path); its links are the core's and open the full notebook.

   What is drawn is chosen from what S carries: tiles for before, during and after a count; one seat or several; partisan
   or not; a retention vote; an unopposed race; a race with no candidate. Nothing is fetched, nothing is written to the
   address, and no global but VIEWS is read. Interactivity: sortable tables, a county table filtered by name and by who
   led, tiles that light the rows they explain, a pane resized by drag or keys on a computer and swiped down on a phone,
   and keyboard shortcuts listed in the pane. Drags listen on window and are removed on cleanup; no setPointerCapture. */
(function () {
"use strict";
if (typeof VIEWS !== "object" || !VIEWS || typeof VIEWS.add !== "function") return;
const V = VIEWS;
const T = (s, vars) => { try { const r = V.T(s, vars); return r == null ? s : String(r); } catch (e) { return s; } };
const esc = s => { try { return V.esc(s == null ? "" : String(s)); } catch (e) { return String(s == null ? "" : s).replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"})[c]); } };
const num = n => { try { return V.num(n); } catch (e) { return String(n); } };
const pctS = (x, d) => { try { return V.pct(x, d == null ? 1 : d); } catch (e) { return (+x).toFixed(d == null ? 1 : d) + "%"; } };
const pctN = (x, d) => pctS(x, d).replace(/\s*%\s*$/, "");          /* the number alone, for the tiles' large type */
const when = iso => { try { return iso ? V.when(iso) : ""; } catch (e) { return ""; } };
const day = iso => { try { return iso ? V.day(iso) : ""; } catch (e) { return ""; } };
const chance = p => { try { return V.chance(p); } catch (e) { return ""; } };
const calm = () => { try { return !!V.calm(); } catch (e) { return true; } };
const arr = x => (Array.isArray(x) ? x : []);
const isNum = x => typeof x === "number" && isFinite(x);
const KEY = "tca.view.split.v1", ID = "vwsp";
const ENTRY = {count: "count", counties: "counties", forecast: "forecast", polls: "polls", coverage: "coverage", list: "list"};
const KIND = {c: "Conceded", v: "Declared victory", s: "Statement"};
const MEDIUM = {t: "text", v: "video", p: "a post"};
const TRACK_WHAT = {ussen: "U.S. Senate races", ushouse: "U.S. House races", gov: "races for governor"};
const SUFFIX = /^(jr\.?|sr\.?|ii|iii|iv|v)$/i;
const sur = n => { const w = String(n || "").trim().split(/\s+/); if (w.length > 1 && SUFFIX.test(w[w.length - 1])) w.pop(); return w[w.length - 1] || ""; };
const ICON = {
  nb: '<path d="M6 3.5h11a1.5 1.5 0 0 1 1.5 1.5v14a1.5 1.5 0 0 1-1.5 1.5H6z"/><path d="M6 3.5v17M9.5 8h5M9.5 11.5h5"/>',
  night: '<path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5z"/>',
  past: '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3.2 2"/>',
  chart: '<path d="M3 16.5l5-6 4 3 6-8.5"/><path d="M3 21h18"/>',
  full: '<path d="M4 5h16v14H4z"/><path d="M4 10h16M9 10v9"/>',
  keys: '<path d="M3 7h18v10H3z"/><path d="M6 10h1M9 10h1M12 10h1M15 10h1M18 10h0M7 14h10"/>'
};

/* ---------- the party colour: a CSS variable beside a party's candidate, a neutral tone on a nonpartisan office ---------- */
function partyVar(code, partisan) {
  if (!partisan || !code) return "";
  let v = "";
  try { v = String(V.partyVar(code) || ""); } catch (e) { v = ""; }
  if (!v) return "";
  if (/^--/.test(v)) return "var(" + v + ")";
  return v;
}
const NEUTRAL = ["var(--sp-n1)", "var(--sp-n2)", "var(--sp-n3)", "var(--sp-n4)", "var(--sp-n5)", "var(--sp-n6)"];
/* one style attribute: the party colour (if any) and whatever else the element needs */
const pcStyle = (p, extra) => { const s = (p && p.pc ? "--pc:" + esc(p.pc) + ";" : "") + (extra || ""); return s ? ' style="' + s + '"' : ""; };
/* a party code for a party's name, where S gives only the name (the seat's holder) */
const PARTY_CODE = [[/^democratic|^dfl\b|farmer-labor|^democrat/i, "D"], [/^republican/i, "R"], [/^libertarian/i, "L"], [/^green/i, "G"], [/^independent|^independence/i, "I"]];
function codeOfParty(name) { const n = String(name || ""); for (let i = 0; i < PARTY_CODE.length; i++) if (PARTY_CODE[i][0].test(n)) return PARTY_CODE[i][1]; return ""; }

/* ---------- the notebook link behind a figure: the core's own address for that entry ---------- */
function nbHref(L, path) {
  if (!path || !L || typeof L.nb !== "function") return "";
  try { if (typeof L.has === "function" && !L.has(path)) return ""; } catch (e) { return ""; }
  let s = "";
  try { s = String(L.nb(path, "x") || ""); } catch (e) { return ""; }
  const m = /href\s*=\s*"([^"]*)"/i.exec(s) || /href\s*=\s*'([^']*)'/i.exec(s);
  return m ? m[1] : "";
}
function nbLink(L, path, text, cls) {
  if (!path || !L || typeof L.nb !== "function") return "";
  try { if (typeof L.has === "function" && !L.has(path)) return ""; } catch (e) { return ""; }
  try { return String(L.nb(path, text, {cls: cls || "sp-nbl"}) || ""); } catch (e) { return ""; }
}
/* a link the core describes either as HTML or as an address */
function anyLink(res, text, cls) {
  if (!res) return "";
  const s = String(res);
  if (/^\s*</.test(s)) return s;
  return '<a class="' + esc(cls || "") + '" href="' + esc(s) + '">' + text + '</a>';
}
const addr = (L, k) => { try { return L && typeof L[k] === "function" ? String(L[k]() || "") : ""; } catch (e) { return ""; } };

/* ---------- the model: what S carries, read once ---------- */
function model(S, L) {
  const M = {S: S, L: L};
  M.seats = Math.max(1, Math.round(+S.seats) || 1);
  M.partisan = !!S.partisan;
  M.kind = S.kind === "retention" || S.kind === "unopposed" || S.kind === "none" ? S.kind : "contest";
  M.list = arr(S.list).filter(r => r && r.n);
  M.count = S.count && arr(S.count.cands).length ? S.count : null;
  M.counties = S.counties && arr(S.counties.top).length ? S.counties : null;
  M.forecast = M.kind !== "unopposed" && S.forecast && arr(S.forecast.top).length ? S.forecast : null;
  M.polls = S.polls && arr(S.polls.newest).length ? S.polls : null;
  M.coverage = S.coverage && typeof S.coverage === "object" ? S.coverage : null;
  M.office = S.source && S.source.office ? String(S.source.office) : "";
  M.srcPage = S.source && S.source.page ? String(S.source.page) : "";
  M.srcLabel = S.source && (S.source.label || S.source.office) ? String(S.source.label || S.source.office) : "";
  M.final = !!(M.count && M.count.final);
  M.rep = M.count && arr(M.count.reporting).length === 2 && isNum(+M.count.reporting[0]) && isNum(+M.count.reporting[1]) ? [+M.count.reporting[0], +M.count.reporting[1]] : null;
  M.allIn = !!(M.rep && M.rep[1] > 0 && M.rep[0] >= M.rep[1]);
  /* the people: everyone in the count (largest first), then anyone on the list who is not in it */
  M.people = []; M.byName = Object.create(null);
  let ni = 0;
  const add = (n, party, code, src) => {
    const p = {id: "c" + M.people.length, n: String(n), party: party ? String(party) : "", code: code ? String(code) : "", pc: "", votes: null, share: null, list: null, count: null};
    p.pc = partyVar(p.code, M.partisan);
    if (!p.pc && !M.partisan) p.pc = NEUTRAL[ni++ % NEUTRAL.length];
    M.people.push(p); M.byName[p.n] = p; return p;
  };
  arr(M.count && M.count.cands).forEach(c => {
    if (!c || !c.n) return;
    const p = M.byName[c.n] || add(c.n, c.party, c.code);
    p.count = c; p.votes = isNum(+c.votes) ? +c.votes : null; p.share = isNum(+c.share) ? +c.share : null;
  });
  M.list.forEach(r => {
    const p = M.byName[r.n] || add(r.n, r.party, r.code);
    if (!p.list) p.list = r;
    if (!p.party && r.party) { p.party = String(r.party); }
    if (!p.pc && M.partisan && r.code) p.pc = partyVar(r.code, true);
  });
  arr(M.forecast && M.forecast.top).forEach(c => { if (c && c.n && !M.byName[c.n]) add(c.n, "", ""); });
  M.cands = M.people.filter(p => p.count);                                  /* in the count's order, largest first */
  M.lead = M.cands[0] || null; M.second = M.cands[1] || null;
  M.seatLast = M.cands[M.seats - 1] || null; M.seatNext = M.cands[M.seats] || null;
  M.fcTop = {}; arr(M.forecast && M.forecast.top).forEach(c => { if (c && c.n) M.fcTop[c.n] = c; });
  M.fcNames = Object.keys(M.fcTop);
  M.fcLead = M.forecast ? (M.lead && M.fcTop[M.lead.n] ? M.lead : (M.byName[M.fcNames[0]] || null)) : null;
  M.won = M.counties && M.counties.won && typeof M.counties.won === "object"
    ? Object.keys(M.counties.won).map(n => [n, +M.counties.won[n] || 0]).filter(x => x[1] > 0).sort((a, b) => b[1] - a[1]) : [];
  M.calls = arr(M.coverage && M.coverage.calls).filter(c => c && c.o && c.n);
  M.said = arr(M.coverage && M.coverage.said).filter(x => x && x.n && arr(x.s).length);
  M.news = M.coverage && M.coverage.news && typeof M.coverage.news === "object" ? M.coverage.news : {};
  M.nStories = M.coverage && arr(M.coverage.n).length ? (+M.coverage.n[0] || 0) : Object.keys(M.news).reduce((a, k) => a + (+(M.news[k] && M.news[k].n) || 0), 0);
  M.tabs = [];
  if (M.count) M.tabs.push("count");
  if (M.count && M.counties) M.tabs.push("counties");
  if (!M.count) M.tabs.push("list");
  if (M.forecast) M.tabs.push("forecast");
  if (M.polls) M.tabs.push("polls");
  if (M.coverage) M.tabs.push("coverage");
  if (M.count) M.tabs.push("list");
  M.href = Object.create(null);
  ["count", "counties", "splits", "forecast", "forecast/how", "forecast/track", "forecast/runs", "polls", "coverage", "coverage/calls", "coverage/said", "coverage/news", "list", "method/labels", "method/calls", "method/polls", "method/forecasts"].forEach(p => { M.href[p] = nbHref(L, p); });
  return M;
}

/* ---------- pieces ---------- */
const mark = () => '<span class="sp-k-i" aria-hidden="true"></span>';
/* a figure: a link to its notebook entry, opened in the pane when the page is wired; a plain tile when S carries no such entry */
function fig(M, path, id, inner, o) {
  o = o || {};
  const href = M.href[path] || "";
  const cls = "sp-k" + (o.cls ? " " + o.cls : "") + (href ? "" : " is-plain");
  const hi = o.hi ? ' data-hi="' + esc(o.hi) + '"' : "";
  const st = o.pc ? ' style="--pc:' + esc(o.pc) + '"' : "";
  const extra = (o.extra || "") + hi + st;
  if (!href) return '<div class="' + cls + '" id="' + ID + "-" + esc(id) + '"' + extra + '>' + inner + '</div>';
  return '<a class="' + cls + '" id="' + ID + "-" + esc(id) + '" href="' + href + '" data-sp-nb="' + esc(path) + '" aria-describedby="' + ID + '-hint"' + extra + '>' + inner + mark() + '</a>';
}
function cell(M, path, text, cls) {
  const href = M.href[path] || "";
  if (!href) return text;
  return '<a class="' + (cls || "sp-cell") + '" href="' + href + '" data-sp-nb="' + esc(path) + '">' + text + '</a>';
}
const chip = (text, cls) => '<span class="sp-chip' + (cls ? " " + cls : "") + '">' + text + '</span>';
const ext = (u, text) => (u ? '<a href="' + esc(u) + '" rel="noopener" target="_blank">' + text + '<span class="sp-sr"> ' + esc(T("(opens their site)")) + '</span></a>' : text);
const tileV = (big, small) => '<span class="sp-k-v">' + big + (small ? '<small>' + small + '</small>' : "") + '</span>';
const tileL = (label, em) => '<span class="sp-k-l">' + label + (em ? '<em>' + em + '</em>' : "") + '</span>';
const tileS = s => '<span class="sp-k-s">' + s + '</span>';
const badge = s => '<span class="sp-k-b">' + s + '</span>';
const partyOf = (M, p) => (M.partisan && p && p.party ? esc(p.party) : "");
const dot = p => '<span class="sp-dot-p" aria-hidden="true"' + pcStyle(p) + '></span>';
const gapWords = M => (M.seats > 1 ? T("seat {n} to the next", {n: num(M.seats)}) : T("first to second"));
function bandWhere(c, s) {
  if (c.l80 <= s && s <= c.h80) return [T("inside the 80-in-100 range"), "in"];
  if (c.l95 <= s && s <= c.h95) return [T("inside the 95-in-100 range, outside the 80"), "near"];
  return [(s > c.h95 ? T("above the 95-in-100 range ({lo} to {hi}): a miss", {lo: pctS(c.l95), hi: pctS(c.h95)}) : T("below the 95-in-100 range ({lo} to {hi}): a miss", {lo: pctS(c.l95), hi: pctS(c.h95)})), "miss"];
}
function trackWords(tr) {
  if (!tr || !isNum(+tr.n) && !isNum(+tr.races)) return "";
  const n = +tr.n || +tr.races || 0;
  if (!n) return "";
  const what = TRACK_WHAT[tr.what] || T("races of this kind");
  let s = T("Its track record: tested on {n} earlier {what}, the leader by its middle estimate finished first in {fav}; the result fell inside the 80-in-100 range in {h80} and inside the 95-in-100 range in {h95}; vote shares were off by {mae} points on average.",
    {n: num(n), what: what, fav: num(+tr.fav || 0), h80: num(+tr.h80 || 0), h95: num(+tr.h95 || 0), mae: isNum(+tr.mae) ? String(+tr.mae) : "?"});
  if (tr.thin) s += " " + T("That record is thin: read the range, not the middle.");
  return s;
}
function dayShort(iso) {
  /* the run's day for the chart's axis: the date words without a year, where the words carry one */
  const d = day(iso);
  return d.replace(/,?\s*\d{4}\s*$/, "") || d;
}

/* ---------- the tiles ---------- */
function tiles(M) {
  const t = [];
  const C = M.count;
  if (C) {
    const show = Math.min(M.cands.length, M.seats + 1, 4);
    for (let i = 0; i < show; i++) {
      const p = M.cands[i];
      let b = "";
      const tied = i === M.seats && M.seatLast && p.votes === M.seatLast.votes;
      if (i < M.seats && !tied) b = badge(M.final ? (M.seats > 1 ? T("Among the {n} with the most votes", {n: num(M.seats)}) : T("Had the most votes")) : (M.seats > 1 ? T("Among the {n} leading", {n: num(M.seats)}) : T("Leads the count")));
      else if (i === M.seats && !tied && M.kind !== "retention") b = badge(T("Next"));
      const share = p.share == null ? "" : tileV(esc(pctN(p.share)), "%");
      const votes = p.votes == null ? "" : tileS(T("{n} votes", {n: num(p.votes)}));
      t.push(fig(M, "count", "k-" + p.id, tileL(esc(p.n), partyOf(M, p) || (M.kind === "retention" && M.list[0] ? esc(T("on keeping {name}", {name: sur(M.list[0].n)})) : "")) + share + votes + b,
        {cls: "sp-k-c", hi: p.id, pc: p.pc, extra: ' data-cand="' + p.id + '"'}));
    }
    if (M.seatLast && M.seatNext && M.seatLast.share != null && M.seatNext.share != null) {
      const gp = M.seatLast.share - M.seatNext.share, gv = (M.seatLast.votes || 0) - (M.seatNext.votes || 0);
      t.push(fig(M, "count", "k-gap", tileL(esc(T("The gap")), esc(gapWords(M))) + tileV(esc(pctN(gp)), " " + esc(T("pts")))
        + tileS(esc(T("{n} votes between {a} and {b}", {n: num(Math.abs(gv)), a: esc(sur(M.seatLast.n)), b: esc(sur(M.seatNext.n))}))), {hi: M.seatLast.id + " " + M.seatNext.id}));
    }
    if (M.rep) {
      const sub = M.final ? T("Certified: the result is final.") : (M.allIn ? T("Every precinct has reported. The result is final when it is certified.") : T("Counting continues. The result is final when it is certified."));
      t.push(fig(M, "count", "k-prec", tileL(esc(T("Precincts reporting")), esc(M.final ? T("as certified") : T("as reported, not final")))
        + tileV(esc(num(M.rep[0])), " " + esc(T("of {n}", {n: num(M.rep[1])}))) + tileS(esc(sub)), {hi: "total"}));
    } else if (isNum(+C.total)) {
      t.push(fig(M, "count", "k-total", tileL(esc(T("Votes counted")), esc(M.final ? T("as certified") : T("as reported, not final")))
        + tileV(esc(num(+C.total)), "") + tileS(esc(M.final ? T("Certified: the result is final.") : T("The result is final when it is certified."))), {hi: "total"}));
    }
    if (M.won.length) {
      const v = M.won.map(([n, k]) => { const p = M.byName[n]; return '<span class="sp-w"' + pcStyle(p) + ' data-cand="' + (p ? p.id : "") + '">' + esc(num(k)) + '</span>'; }).join(' <small>·</small> ');
      const s = M.won.map(([n, k]) => esc(sur(n)) + " " + esc(num(k))).join("; ");
      t.push(fig(M, "counties", "k-won", tileL(esc(T("Counties with the most votes")), esc(T("of {n} reporting", {n: num(+M.counties.n || M.counties.top.length)})))
        + tileV(v, "") + tileS(s + ". " + esc(T("A county with more votes is not a county that counts more: every vote counts the same."))), {hi: "lead"}));
    }
    if (M.forecast && M.lead && M.fcTop[M.lead.n] && M.lead.share != null) {
      const fw = M.fcTop[M.lead.n], s = M.lead.share, w = bandWhere(fw, s);
      const vals = [];
      M.fcNames.forEach(n => { const c = M.fcTop[n]; vals.push(+c.l95, +c.h95); const p = M.byName[n]; if (p && p.share != null) vals.push(p.share); });
      const lo = Math.floor((Math.min.apply(null, vals) - 2) / 5) * 5, hi = Math.ceil((Math.max.apply(null, vals) + 2) / 5) * 5;
      const xp = v => ((v - lo) / Math.max(1, hi - lo) * 100).toFixed(2);
      const mini = '<span class="sp-mini" aria-hidden="true"' + pcStyle(M.lead) + '><i class="r95" style="left:' + xp(fw.l95) + '%;width:' + (xp(fw.h95) - xp(fw.l95)).toFixed(2) + '%"></i><i class="r80" style="left:' + xp(fw.l80) + '%;width:' + (xp(fw.h80) - xp(fw.l80)).toFixed(2) + '%"></i><i class="ct" style="left:' + xp(s) + '%"></i></span>';
      t.push(fig(M, "forecast", "k-fc", tileL(esc(T("Forecast against the count")), esc(T("Analysis")))
        + '<span class="sp-k-v">' + esc(pctN(fw.md)) + '<small>% → </small>' + esc(pctN(s)) + '<small>%</small></span>' + mini
        + tileS(esc(T("{name}’s count fell {where}. 80 in 100 runs: {lo} to {hi}; chance {c}.", {name: sur(M.lead.n), where: w[0], lo: pctS(fw.l80), hi: pctS(fw.h80), c: chance(fw.ch)}))), {hi: M.lead.id, extra: ' data-fit="' + w[1] + '"'}));
    }
  } else {
    /* before any count: the list, the seat, the day, and what else is on file */
    const n = M.list.length;
    let big = esc(num(n)), small = n === 1 ? esc(T("name")) : esc(T("names")), sub = "", b = "";
    if (M.kind === "none" || n === 0) { big = esc(T("None")); small = ""; sub = T("The official list carries no candidate for this office."); }
    else if (M.kind === "retention") { big = esc(T("Yes or no")); small = ""; sub = T("A yes-or-no vote on {name}.", {name: M.list[0].n}); }
    else if (M.kind === "unopposed") { b = badge(T("Unopposed")); sub = n === 1 ? T("No one runs against {name}.", {name: M.list[0].n}) : T("No one runs against the names on the list."); }
    else sub = M.seats > 1 ? T("Vote for {n}: the {n} with the most votes are elected.", {n: num(M.seats)}) : T("In the order of the official list.");
    t.push(fig(M, "list", "k-list", tileL(esc(T("On the ballot")), esc(M.partisan ? T("as filed") : T("nonpartisan office"))) + tileV(big, small ? " " + small : "") + tileS(esc(sub)) + b, {hi: "list"}));
    if (S_holder(M)) {
      const h = M.S.holder, hp = M.byName[h.n] || null;
      t.push(fig(M, "list", "k-holder", tileL(esc(T("Holds the seat today")), partyOf(M, {party: h.party}))
        + '<span class="sp-k-v is-text">' + esc(h.n) + '</span>' + tileS(esc(h.running === true ? T("On the ballot for it.") : h.running === false ? T("Not on the ballot for it.") : T("Where the record says."))),
        {hi: hp ? hp.id : "", pc: M.partisan && hp && hp.pc ? hp.pc : (M.partisan ? partyVar(codeOfParty(h.party), true) : "")}));
    }
    if (M.S.date) {
      const soon = M.S.read && String(M.S.read) < String(M.S.date);
      t.push(fig(M, "list", "k-day", tileL(esc(T("Election day")), "") + '<span class="sp-k-v is-text">' + esc(day(M.S.date)) + '</span>'
        + tileS(esc(soon ? T("Voting is on that day; no count is on file yet.") : T("No count is on file here yet."))), {}));
    }
    if (M.forecast && M.fcLead && M.fcTop[M.fcLead.n]) {
      const c = M.fcTop[M.fcLead.n];
      t.push(fig(M, "forecast", "k-fc", tileL(esc(T("Forecast")), esc(T("Analysis"))) + tileV(esc(pctN(c.md)), "% " + esc(T("middle")))
        + tileS(esc(T("{name}: {chance} chance; 80 in 100 runs fall between {lo} and {hi}.", {name: sur(M.fcLead.n), chance: chance(c.ch), lo: pctS(c.l80), hi: pctS(c.h80)}))), {hi: M.fcLead.id, pc: M.fcLead.pc}));
    }
    if (M.polls) {
      const p = M.polls.newest[0], sh = p.shares && typeof p.shares === "object" ? Object.keys(p.shares).map(n => [n, +p.shares[n]]).sort((a, b) => b[1] - a[1]) : [];
      const top = sh[0] ? M.byName[sh[0][0]] : null;
      t.push(fig(M, "polls", "k-poll", tileL(esc(T("Newest poll")), esc(String(p.pollster || "")))
        + (sh[0] ? tileV(esc(pctN(sh[0][1])), "% " + esc(sur(sh[0][0]))) : "")
        + tileS(esc(sh.slice(0, 3).map(x => sur(x[0]) + " " + pctS(x[1])).join(", ") + (p.end ? "; " + day(p.end) : "") + ". ") + esc(T("Opinion when it was taken, not a forecast."))), {hi: top ? top.id : "", pc: top ? top.pc : ""}));
    }
  }
  if (M.coverage) {
    const byName = {};
    M.calls.forEach(c => { (byName[c.n] = byName[c.n] || []).push(c); });
    const forWho = Object.keys(byName).map(n => T("for {name}: {list}", {name: n, list: byName[n].map(c => c.o + " " + when(c.t)).join(", ")})).join("; ");
    t.push(fig(M, "coverage/calls", "k-calls", tileL(esc(T("Calls by news organizations")), esc(T("links only"))) + tileV(esc(num(M.calls.length)), "")
      + tileS(esc((M.calls.length ? forWho + ". " : T("None linked yet.") + " ") + T("The Civic Archive does not call races."))), {hi: M.calls.map(c => (M.byName[c.n] || {}).id).filter(Boolean).join(" ")}));
    const saidS = M.said.map(x => sur(x.n) + ": " + Array.from(new Set(arr(x.s).map(y => T(KIND[y.k] || "Statement").toLowerCase()))).join(", ")).join(" · ");
    t.push(fig(M, "coverage/said", "k-said", tileL(esc(T("Candidates’ statements")), esc(T("links only"))) + tileV(esc(num(M.said.length)), "")
      + tileS(esc((M.said.length ? saidS + ". " : T("None linked yet.") + " ") + T("Their words, behind the links."))), {hi: M.said.map(x => (M.byName[x.n] || {}).id).filter(Boolean).join(" ")}));
    if (!C) t.push(fig(M, "coverage/news", "k-news", tileL(esc(T("News stories linked")), esc(T("links only"))) + tileV(esc(num(M.nStories)), "")
      + tileS(esc(T("Each under its outlet’s own headline; nothing is copied."))), {}));
  }
  return t.join("");
}
const S_holder = M => !!(M.S.holder && typeof M.S.holder === "object" && M.S.holder.n);

/* ---------- the Count tab ---------- */
function countPanel(M) {
  const C = M.count, cands = M.cands;
  const seg = cands.map(p => '<i' + pcStyle(p, "flex:" + Math.max(0.01, p.share || 0)) + ' data-cand="' + p.id + '">' + ((p.share || 0) >= 12 ? "<b>" + esc(sur(p.n)) + " " + esc(pctS(p.share)) + "</b>" : "") + '</i>').join("");
  const label = cands.map(p => p.n + " " + pctS(p.share == null ? 0 : p.share)).join(", ");
  const rows = cands.map((p, i) => '<tr data-cand="' + p.id + '"><th scope="row">' + cell(M, "count", esc(p.n)) + (p.list && p.list.inc ? ' <span class="sp-tag">' + esc(T("holds the seat")) + '</span>' : "") + '</th>'
    + (M.partisan ? '<td>' + dot(p) + esc(p.party) + '</td>' : "")
    + '<td class="n">' + (p.votes == null ? "" : esc(num(p.votes))) + '</td><td class="n">' + (p.share == null ? "" : esc(pctS(p.share, 2))) + '</td>'
    + '<td class="bar"><span class="sp-hbar"' + pcStyle(p) + '><i style="width:' + Math.min(100, Math.max(0, p.share || 0)).toFixed(2) + '%"></i></span></td></tr>').join("");
  let agree = "";
  if (isNum(+C.total) && isNum(+C.county_sum)) {
    const d = +C.total - +C.county_sum;
    agree = d === 0 ? T("The county figures in the same reading add up to the total exactly.")
      : T("The county figures in the same reading add up to {sum} votes, {d} {fm} than the total. The site shows each as it is posted and adjusts neither.", {sum: num(+C.county_sum), d: num(Math.abs(d)), fm: d > 0 ? T("fewer") : T("more")});
  }
  const seatsLine = M.seats > 1 ? '<p class="sp-fine">' + esc(T("Voters chose up to {n}; the {n} with the most votes are elected.", {n: num(M.seats)})) + '</p>' : "";
  const retLine = M.kind === "retention" && M.list[0] ? '<p class="sp-fine">' + esc(T("A yes-or-no vote on {name}.", {name: M.list[0].n})) + '</p>' : "";
  const reported = M.final
    ? T("Certified figures, read {when}", {when: when(C.at)})
    : T("As reported {when}{by}", {when: when(C.at), by: M.office ? T(", by {office}", {office: M.office}) : ""});
  return '<div class="sp-row"><h3>' + esc(T("Share of the vote")) + '</h3>' + nbLink(M.L, "method/labels", esc(T("What the labels mean"))) + '</div>'
    + seatsLine + retLine
    + '<div class="sp-shares" role="img" aria-label="' + esc(T("Share of the vote: {list}", {list: label})) + '">' + seg + '</div>'
    + '<div class="sp-tw" role="region" aria-label="' + esc(T("Votes, {title}", {title: M.S.title || M.S.office || ""})) + '" tabindex="0"><table class="sp-t">'
    + '<thead><tr><th scope="col">' + esc(T("Candidate")) + '</th>' + (M.partisan ? '<th scope="col">' + esc(T("Party")) + '</th>' : "") + '<th scope="col" class="n">' + esc(T("Votes")) + '</th><th scope="col" class="n">' + esc(T("Share")) + '</th><th scope="col" class="bar"><span class="sp-sr">' + esc(T("Share, as a bar")) + '</span></th></tr></thead>'
    + '<tbody>' + rows + '</tbody>'
    + (isNum(+C.total) ? '<tfoot><tr data-row="total"><th scope="row">' + esc(T("All candidates")) + '</th>' + (M.partisan ? "<td></td>" : "") + '<td class="n">' + esc(num(+C.total)) + '</td><td class="n">100%</td><td></td></tr></tfoot>' : "")
    + '</table></div>'
    + '<p class="sp-fine">' + (agree ? cell(M, "count", esc(agree), "sp-inl") + " " : "") + esc(reported) + (M.srcPage ? " (" + ext(M.srcPage, esc(M.srcLabel)) + ")" : "") + '.'
    + (M.S.splits ? " " + nbLink(M.L, "splits", esc(T("Votes left blank and split results"))) : "") + '</p>';
}

/* ---------- the Counties tab ---------- */
function countiesPanel(M) {
  const K = M.counties, top = K.top.filter(c => c && c.name);
  const cols = M.cands.slice(0, 5);
  const chips = M.won.map(([n]) => { const p = M.byName[n]; return '<button type="button" class="sp-chipbtn"' + pcStyle(p) + ' data-lead="' + esc(n) + '" aria-pressed="false">' + dot(p) + esc(T("Led by {name}", {name: sur(n)})) + '</button>'; }).join("");
  const heads = cols.map(p => '<th scope="col" class="n" aria-sort="none" data-cand="' + p.id + '"><button type="button" class="sp-sort" data-key="' + p.id + '">' + esc(sur(p.n)) + '</button></th>').join("");
  const showDone = !K.all_done;
  const rows = top.map((ct, i) => {
    const lp = ct.lead ? M.byName[ct.lead] : null, sh = ct.shares && typeof ct.shares === "object" ? ct.shares : {};
    const data = cols.map(p => ' data-' + p.id + '="' + (isNum(+sh[p.n]) ? +sh[p.n] : 0) + '"').join("");
    const cells = cols.map(p => '<td class="n" data-cand="' + p.id + '">' + (isNum(+sh[p.n]) ? esc(pctS(+sh[p.n])) : "") + '</td>').join("");
    const two = M.cands.slice(0, 2).map(p => '<i' + pcStyle(p, "width:" + (isNum(+sh[p.n]) ? Math.min(100, +sh[p.n]).toFixed(1) : 0) + "%") + '></i>').join("");
    const fips = String(ct.fips || i);
    return '<tr data-lead="' + esc(ct.lead || "") + '" data-name="' + esc(String(ct.name).toLowerCase()) + '" data-total="' + (+ct.total || 0) + '" data-done="' + (ct.done ? 1 : 0) + '"' + data + '>'
      + '<th scope="row">' + cell(M, "counties", esc(ct.name)) + '</th><td class="n">' + (isNum(+ct.total) ? esc(num(+ct.total)) : "") + '</td>' + cells
      + '<td>' + (ct.lead ? '<span class="sp-leadn"' + pcStyle(lp) + ' data-cand="' + (lp ? lp.id : "") + '">' + dot(lp) + esc(sur(ct.lead)) + '</span>' : "") + '<span class="sp-split" aria-hidden="true">' + two + '</span></td>'
      + (showDone ? '<td>' + esc(ct.done ? T("every precinct in") : T("still counting")) + '</td>' : "") + '</tr>';
  }).join("");
  const wonS = M.won.map(([n, k]) => sur(n) + " " + num(k)).join("; ");
  return '<div class="sp-row"><h3>' + esc(T("The {n} counties with the most votes cast", {n: num(top.length)})) + '</h3>' + nbLink(M.L, "counties", esc(T("Every county"))) + '</div>'
    + '<div class="sp-filters"><label class="sp-find"><span class="sp-sr">' + esc(T("Filter counties by name")) + '</span><input type="search" class="sp-cfilter" placeholder="' + esc(T("Filter by name")) + '" autocomplete="off"></label>'
    + (chips ? '<div class="sp-chipset" role="group" aria-label="' + esc(T("Show counties led by")) + '"><button type="button" class="sp-chipbtn" data-lead="" aria-pressed="true">' + esc(T("All")) + '</button>' + chips + '</div>' : "")
    + '<p class="sp-tstat" aria-live="polite">' + esc(T("Showing {n} of {m} counties", {n: num(top.length), m: num(top.length)})) + '</p></div>'
    + '<div class="sp-tw" role="region" aria-label="' + esc(T("The largest counties, county by county")) + '" tabindex="0"><table class="sp-t sp-ct">'
    + '<thead><tr><th scope="col" aria-sort="none"><button type="button" class="sp-sort" data-key="name">' + esc(T("County")) + '</button></th>'
    + '<th scope="col" class="n" aria-sort="descending"><button type="button" class="sp-sort" data-key="total">' + esc(T("Votes")) + '</button></th>' + heads
    + '<th scope="col" aria-sort="none" data-row="lead"><button type="button" class="sp-sort" data-key="lead">' + esc(T("Most votes")) + '</button></th>'
    + (showDone ? '<th scope="col" aria-sort="none"><button type="button" class="sp-sort" data-key="done">' + esc(T("Counting")) + '</button></th>' : "") + '</tr></thead>'
    + '<tbody>' + rows + '</tbody></table></div>'
    + '<p class="sp-fine">' + (wonS ? cell(M, "counties", esc(T("Counties where each candidate had the most votes: {list}, of {n} reporting.", {list: wonS, n: num(+K.n || top.length)})), "sp-inl") + " " : "")
    + esc(T("A county with more votes is not a county that counts more: every vote counts the same. Shares are of each county’s votes in this race.")) + (M.S.splits ? " " + nbLink(M.L, "splits", esc(T("Votes left blank and split results"))) : "") + '</p>';
}

/* ---------- the Forecast tab ---------- */
function forecastPanel(M) {
  const F = M.forecast, hasCount = !!M.count;
  const vals = [];
  M.fcNames.forEach(n => { const c = M.fcTop[n]; vals.push(+c.l95, +c.h95); const p = M.byName[n]; if (p && p.share != null) vals.push(p.share); });
  const lo = Math.floor((Math.min.apply(null, vals) - 2) / 5) * 5, hi = Math.ceil((Math.max.apply(null, vals) + 2) / 5) * 5, span = Math.max(1, hi - lo);
  const xp = v => ((v - lo) / span * 100), x = v => ((v - lo) / span * 1000).toFixed(1);
  const ticks = []; for (let t = lo; t <= hi; t += 5) ticks.push(t);
  const axis = ticks.map(t => '<span class="' + (t === ticks[0] ? "at-l" : t === ticks[ticks.length - 1] ? "at-r" : "") + '" style="left:' + xp(t).toFixed(2) + '%">' + t + '%</span>').join("");
  const ref = lo < 50 && 50 < hi ? '<i class="sp-ref" style="left:' + xp(50).toFixed(2) + '%" aria-hidden="true"></i>' : "";
  const rows = M.fcNames.map((n, j) => {
    const c = M.fcTop[n], p = M.byName[n]; if (!p) return "";
    const s = p.share, w = s == null ? null : bandWhere(c, s);
    const side = s == null ? "" : (xp(s) > 72 ? " at-r" : xp(s) < 14 ? " at-l" : "");
    const aria = T("{name}: the model’s middle estimate {md}; 80-in-100 range {l80} to {h80}; 95-in-100 range {l95} to {h95}", {name: n, md: pctS(c.md), l80: pctS(c.l80), h80: pctS(c.h80), l95: pctS(c.l95), h95: pctS(c.h95)})
      + (w ? "; " + T("the count has {s}, {where}.", {s: pctS(s), where: w[0]}) : ".");
    return '<div class="sp-band-row" data-cand="' + p.id + '"' + pcStyle(p) + '>'
      + cell(M, "forecast", esc(n) + '<em>' + (partyOf(M, p) ? partyOf(M, p) + " · " : "") + esc(T("chance {c}", {c: chance(c.ch)})) + '</em>', "sp-band-name")
      + '<div class="sp-band-plot" role="img" aria-label="' + esc(aria) + '">' + ref + '<svg viewBox="0 0 1000 44" preserveAspectRatio="none" aria-hidden="true" focusable="false">'
      + '<rect class="b95" x="' + x(c.l95) + '" y="11" width="' + (x(c.h95) - x(c.l95)).toFixed(1) + '" height="22"/><rect class="b80" x="' + x(c.l80) + '" y="11" width="' + (x(c.h80) - x(c.l80)).toFixed(1) + '" height="22"/>'
      + '<line class="bmd" x1="' + x(c.md) + '" x2="' + x(c.md) + '" y1="5" y2="39" vector-effect="non-scaling-stroke"/>'
      + (s == null ? "" : '<line class="bct" x1="' + x(s) + '" x2="' + x(s) + '" y1="0" y2="44" vector-effect="non-scaling-stroke"/>') + '</svg>'
      + (s == null ? "" : '<span class="sp-band-ct' + side + '" style="left:' + xp(s).toFixed(2) + '%">' + esc(T("Count {s}", {s: pctS(s)})) + '</span>') + '</div>'
      + '<p class="sp-band-figs">' + esc(T("Middle {md} · 80 in 100: {l80} to {h80} · 95 in 100: {l95} to {h95}", {md: pctS(c.md), l80: pctS(c.l80), h80: pctS(c.h80), l95: pctS(c.l95), h95: pctS(c.h95)})) + (w ? " · " + esc(T("count {where}", {where: w[0]})) : "") + '</p></div>';
  }).join("");
  const rest = arr(F.rest).filter(r => r && r.n && isNum(+r.md));
  const restP = rest.length ? '<p class="sp-fine">' + esc(T("Others, by the same run: {list}.", {list: rest.map(r => T("{name} middle {md} ({lo} to {hi})", {name: r.n, md: pctS(r.md), lo: pctS(r.l80), hi: pctS(r.h80)})).join("; ")})) + '</p>' : "";
  /* run by run */
  let runs = "", runsTable = "";
  const hist = arr(F.hist).filter(h => h && h.at && h.c && typeof h.c === "object");
  if (hist.length >= 2) {
    const ts = iso => { const t = Date.parse(iso); return isNum(t) ? t : 0; };
    const t0 = ts(hist[0].at), t1 = ts(hist[hist.length - 1].at), tspan = Math.max(1, t1 - t0);
    const xs = hist.map(h => (ts(h.at) - t0) / tspan * 100);
    const yv = [];
    hist.forEach(h => M.fcNames.forEach(n => { const v = arr(h.c[n]); if (v.length >= 3) yv.push(+v[1], +v[2]); }));
    M.fcNames.forEach(n => { const p = M.byName[n]; if (p && p.share != null) yv.push(p.share); });
    if (yv.length) {
      const ylo = Math.floor((Math.min.apply(null, yv) - 1) / 5) * 5, yhi = Math.ceil((Math.max.apply(null, yv) + 1) / 5) * 5, yspan = Math.max(1, yhi - ylo);
      const yp = v => (yhi - v) / yspan * 100;
      const paths = [], dots = [], legend = [];
      M.fcNames.forEach(n => {
        const p = M.byName[n]; if (!p) return;
        const pts = []; hist.forEach((h, i) => { const v = arr(h.c[n]); if (v.length >= 3) pts.push([xs[i], v, i]); });
        if (!pts.length) return;
        const topE = pts.map(q => (q[0] * 10).toFixed(1) + "," + (yp(+q[1][2]) * 10).toFixed(1)).join(" ");
        const botE = pts.slice().reverse().map(q => (q[0] * 10).toFixed(1) + "," + (yp(+q[1][1]) * 10).toFixed(1)).join(" ");
        const mid = pts.map(q => (q[0] * 10).toFixed(1) + "," + (yp(+q[1][0]) * 10).toFixed(1)).join(" ");
        const st = p.pc ? ' style="--pc:' + esc(p.pc) + '"' : "";
        paths.push('<polygon class="r80"' + st + ' points="' + topE + " " + botE + '"/><polyline class="rmd"' + st + ' points="' + mid + '" vector-effect="non-scaling-stroke"/>');
        if (p.share != null) paths.push('<line class="rct" x1="0" x2="1000" y1="' + (yp(p.share) * 10).toFixed(1) + '" y2="' + (yp(p.share) * 10).toFixed(1) + '" vector-effect="non-scaling-stroke"/>');
        pts.forEach(q => {
          const v = q[1];
          const lab = T("Run of {day}: {name} middle {md}, 80 in 100 {lo} to {hi}{ch}", {day: day(hist[q[2]].at), name: n, md: pctS(+v[0]), lo: pctS(+v[1]), hi: pctS(+v[2]), ch: v.length > 3 ? T(", chance {c}", {c: chance(+v[3])}) : ""});
          const href = M.href["forecast/runs"] || M.href.forecast || "";
          dots.push((href ? '<a class="sp-dot" href="' + href + '" data-sp-nb="' + (M.href["forecast/runs"] ? "forecast/runs" : "forecast") + '"' : '<span class="sp-dot"') + ' data-cand="' + p.id + '"' + pcStyle(p, "left:" + q[0].toFixed(2) + "%;top:" + yp(+v[0]).toFixed(2) + "%") + ' aria-label="' + esc(lab) + '" title="' + esc(lab) + '">' + (href ? "</a>" : "</span>"));
        });
        legend.push('<span' + st + '><i class="lg-band"></i><i class="lg-line"></i>' + esc(T("{name}: likely range and middle", {name: sur(n)})) + '</span>');
      });
      if (hasCount) legend.push('<span><i class="lg-ct"></i>' + esc(T("the count")) + '</span>');
      const yl = [yhi, ylo].concat(ylo < 50 && 50 < yhi ? [50] : []).sort((a, b) => b - a).map(v => '<span style="top:' + yp(v).toFixed(2) + '%">' + v + '%</span>').join("");
      const xl = []; let lastX = -100;
      hist.forEach((h, i) => {
        const last = i === hist.length - 1;
        if (i === 0 || last || xs[i] - lastX > 18) {
          if (!last && i !== 0 && 100 - xs[i] < 14) return;
          xl.push('<span class="' + (i === 0 ? "at-l" : last ? "at-r" : "") + '" style="left:' + xs[i].toFixed(2) + '%">' + esc(dayShort(h.at)) + '</span>'); lastX = xs[i];
        }
      });
      const hrows = hist.map(h => '<tr><th scope="row">' + esc(day(h.at)) + '</th>' + M.fcNames.map(n => { const v = arr(h.c[n]); return v.length >= 3 ? '<td class="n">' + esc(pctS(+v[0])) + ' <span class="sp-m">(' + esc(pctS(+v[1])) + ' ' + esc(T("to")) + ' ' + esc(pctS(+v[2])) + ')</span></td>' : "<td></td>"; }).join("") + '</tr>').join("");
      runs = '<div class="sp-row"><h3>' + esc(T("How the estimate moved, run by run")) + '</h3></div>'
        + '<div class="sp-runs"><div class="sp-runs-y" aria-hidden="true">' + yl + '</div>'
        + '<div class="sp-runs-plot" role="img" aria-label="' + esc(T("Each run’s middle estimate and 80-in-100 range for {names}, {from} to {to}{ct}. The figures are in the table below.", {names: M.fcNames.join(T(" and ")), from: dayShort(hist[0].at), to: dayShort(hist[hist.length - 1].at), ct: hasCount ? T(", against the count") : ""})) + '">'
        + '<svg viewBox="0 0 1000 1000" preserveAspectRatio="none" aria-hidden="true" focusable="false">' + paths.join("") + '</svg>' + dots.join("") + '</div>'
        + '<div class="sp-runs-x" aria-hidden="true">' + xl.join("") + '</div></div>'
        + '<p class="sp-legend" aria-hidden="true">' + legend.join("") + '</p>';
      runsTable = '<details class="sp-more"><summary>' + esc(T("The runs, as a table")) + '</summary><div class="sp-tw" role="region" aria-label="' + esc(T("Every run of the forecast")) + '" tabindex="0"><table class="sp-t"><thead><tr><th scope="col">' + esc(T("Run")) + '</th>'
        + M.fcNames.map(n => '<th scope="col" class="n">' + esc(n) + '</th>').join("") + '</tr></thead><tbody>' + hrows + '</tbody></table></div></details>';
    }
  }
  const track = trackWords(F.track);
  const intro = hasCount
    ? T("The model’s last run, {day}, from {n} simulated elections. The lighter band holds 95 in 100 of them, the darker 80 in 100; the dashed line is the middle estimate and the dark line is the count as reported. A count outside the band is a miss, counted in the track record.", {day: day(F.at), n: num(+F.draws || 0)})
    : T("The model’s last run, {day}, from {n} simulated elections. The lighter band holds 95 in 100 of them, the darker 80 in 100; the dashed line is the middle estimate. A forecast is not a result.", {day: day(F.at), n: num(+F.draws || 0)});
  return '<div class="sp-row"><h3>' + esc(hasCount ? T("The last run against the count") : T("The last run")) + '</h3>' + chip(esc(T("Analysis")), "analysis") + nbLink(M.L, "forecast/how", esc(T("How the forecast works"))) + '</div>'
    + '<p class="sp-fine">' + esc(intro) + '</p>'
    + (F.env ? '<p class="sp-fine">' + esc(String(F.env)) + '</p>' : "")
    + '<div class="sp-band">' + rows + '<div class="sp-band-axis" aria-hidden="true">' + axis + '</div></div>' + restP + runs + runsTable
    + '<p class="sp-fine">' + (track ? cell(M, "forecast/track", esc(track), "sp-inl") + " " : "") + esc(T("A forecast is not a result: the official count decides.")) + " " + nbLink(M.L, "forecast", esc(T("The forecast, worked out"))) + '</p>';
}

/* ---------- the Polls tab ---------- */
function pollsPanel(M) {
  const P = M.polls, polls = P.newest.filter(p => p && p.pollster);
  const names = [];
  M.people.forEach(p => { if (polls.some(q => q.shares && typeof q.shares === "object" && isNum(+q.shares[p.n]))) names.push(p); });
  polls.forEach(q => { Object.keys(q.shares && typeof q.shares === "object" ? q.shares : {}).forEach(n => { if (!M.byName[n] && !names.some(x => x.n === n)) names.push({id: "", n: n, pc: ""}); }); });
  const cols = names.slice(0, 5);
  const rows = polls.map(q => '<tr><th scope="row">' + ext(q.url, esc(String(q.pollster))) + '</th><td>' + esc((q.start && q.end ? T("{a} to {b}", {a: day(q.start), b: day(q.end)}) : day(q.end || q.start || ""))) + '</td>'
    + '<td>' + esc((isNum(+q.n) && q.n ? num(+q.n) + " " : "") + (q.pop || "")) + '</td><td class="n">' + (isNum(+q.moe) ? "±" + esc(String(+q.moe)) : "") + '</td>'
    + cols.map(p => '<td class="n"' + (p.id ? ' data-cand="' + p.id + '"' : "") + '>' + (q.shares && isNum(+q.shares[p.n]) ? esc(pctS(+q.shares[p.n])) : "") + '</td>').join("") + '</tr>').join("");
  const counted = isNum(+P.n) ? T("{n} polls counted", {n: num(+P.n)}) : "";
  const other = isNum(+P.other) && +P.other > 0 ? T("{n} shown apart", {n: num(+P.other)}) : "";
  return '<div class="sp-row"><h3>' + esc(T("The newest polls")) + '</h3>' + (counted ? chip(esc(counted + (other ? "; " + other : ""))) : "") + nbLink(M.L, "polls", esc(T("Every poll"))) + '</div>'
    + '<div class="sp-tw" role="region" aria-label="' + esc(T("The newest polls")) + '" tabindex="0"><table class="sp-t"><thead><tr><th scope="col">' + esc(T("Pollster")) + '</th><th scope="col">' + esc(T("Dates")) + '</th><th scope="col">' + esc(T("Sample")) + '</th><th scope="col" class="n">' + esc(T("Error")) + '</th>'
    + cols.map(p => '<th scope="col" class="n"' + (p.id ? ' data-cand="' + p.id + '"' : "") + '>' + esc(sur(p.n)) + '</th>').join("") + '</tr></thead><tbody>' + rows + '</tbody></table></div>'
    + '<p class="sp-fine">' + esc(T("A poll measures opinion when it was taken, not a forecast. We count only polls from members of the American Association for Public Opinion Research’s Transparency Initiative.")) + " " + nbLink(M.L, "method/polls", esc(T("How polls are chosen"))) + '</p>';
}

/* ---------- the Coverage tab ---------- */
function coveragePanel(M) {
  const V2 = M.coverage;
  const callLi = M.calls.map(c => '<li><b>' + esc(c.o) + '</b> ' + esc(T("called it for {name}, {when}", {name: c.n, when: when(c.t)})) + (c.by && c.by !== c.o ? esc(T(", as reported by {by}", {by: c.by})) : "") + (c.u ? " " + ext(c.u, esc(T("the report"))) : "") + '</li>').join("") || '<li>' + esc(T("No call is linked yet.")) + '</li>';
  const saidLi = M.said.map(x => '<li><b>' + esc(x.n) + '</b>: ' + arr(x.s).map(y => esc(T(KIND[y.k] || "Statement")) + " (" + esc(T(MEDIUM[y.m] || "text")) + (y.d ? ", " + esc(day(y.d)) : "") + (y.u ? ", " + ext(y.u, esc(y.by || T("link"))) : "") + ")").join("; ") + '</li>').join("") || '<li>' + esc(T("No statement is linked yet.")) + '</li>';
  const tierName = {national: T("National"), state: T("State"), local: T("Local")};
  const news = Object.keys(M.news).map(t => {
    const v = M.news[t] || {}, n = +v.n || 0;
    if (!n && !arr(v.top).length) return "";
    return '<li><b>' + esc(tierName[t] || t) + '</b>: ' + esc(n === 1 ? T("1 story") : T("{n} stories", {n: num(n)})) + '<ul class="sp-heads">' + arr(v.top).filter(x => x && x.u && x.h).map(x => '<li>' + ext(x.u, esc(x.o || "") + (x.o ? ": " : "") + esc(x.h)) + '</li>').join("") + '</ul></li>';
  }).join("") || '<li>' + esc(T("No story is linked yet.")) + '</li>';
  const nc = M.calls.length, ns = M.said.length, nn = M.nStories;
  return '<div class="sp-row"><h3>' + esc(T("Who called it, and what the candidates said")) + '</h3>' + chip(esc(T("Links only")), "links") + nbLink(M.L, "coverage", esc(T("The coverage page"))) + '</div>'
    + '<div class="sp-cols">'
    + '<section class="sp-col"><h4>' + cell(M, "coverage/calls", esc(nc === 1 ? T("1 call") : T("{n} calls", {n: num(nc)})), "sp-inl") + '</h4><ul class="sp-list">' + callLi + '</ul>'
    + '<p class="sp-fine">' + esc(T("A call is a news organization’s judgment from its own count. The Civic Archive does not call races; the result is final when it is certified.")) + " " + nbLink(M.L, "method/calls", esc(T("Why this site never calls a race"))) + '</p></section>'
    + '<section class="sp-col"><h4>' + cell(M, "coverage/said", esc(ns === 1 ? T("1 candidate made statements") : T("{n} candidates made statements", {n: num(ns)})), "sp-inl") + '</h4><ul class="sp-list">' + saidLi + '</ul>'
    + '<p class="sp-fine">' + esc(T("Nothing is copied: the words are theirs, behind the links. A candidate with no statement listed is not mentioned.")) + '</p></section>'
    + '<section class="sp-col"><h4>' + cell(M, "coverage/news", esc(nn === 1 ? T("1 news story linked") : T("{n} news stories linked", {n: num(nn)})), "sp-inl") + '</h4><ul class="sp-list">' + news + '</ul>'
    + '<p class="sp-fine">' + esc(T("Each story under its outlet’s own headline.")) + (V2.checked ? " " + esc(T("Links checked {day}.", {day: day(V2.checked)})) : "") + '</p></section></div>';
}

/* ---------- the List tab: who is on the ballot, as filed ---------- */
function listPanel(M) {
  const L = M.L, src = M.S.list_source && typeof M.S.list_source === "object" ? M.S.list_source : {};
  let lede = "";
  if (M.kind === "none" || !M.list.length) lede = T("The official list carries no candidate for this office.");
  else if (M.kind === "retention") lede = T("A yes-or-no vote on {name}: the question is whether to keep them in office.", {name: M.list[0].n});
  else if (M.kind === "unopposed") lede = M.list.length === 1 ? T("No one runs against {name}.", {name: M.list[0].n}) : T("No one runs against the names on the list.");
  else if (M.seats > 1) lede = T("Vote for {n}: the {n} with the most votes are elected.", {n: num(M.seats)});
  else lede = T("In the order of the official list.");
  const rows = M.list.map((r, i) => {
    const p = M.byName[r.n], notes = [];
    if (r.inc) notes.push(T("holds the seat today"));
    if (r.wi) notes.push(T("write-in"));
    if (r.out) notes.push(String(r.out));
    return '<tr' + (p ? ' data-cand="' + p.id + '"' : "") + '><td class="n">' + (isNum(+r.order) && r.order != null ? esc(num(+r.order)) : "") + '</td><th scope="row">' + cell(M, "list", esc(r.n)) + '</th>'
      + (M.partisan ? '<td>' + dot(p) + esc(r.party || "") + '</td>' : "") + '<td>' + esc(notes.join("; ")) + '</td></tr>';
  }).join("");
  const table = M.list.length ? '<div class="sp-tw" role="region" aria-label="' + esc(T("On the ballot, as filed")) + '" tabindex="0"><table class="sp-t sp-lt"><thead><tr><th scope="col" class="n">' + esc(T("Order")) + '</th><th scope="col">' + esc(T("Name, as filed")) + '</th>' + (M.partisan ? '<th scope="col">' + esc(T("Party")) + '</th>' : "") + '<th scope="col">' + esc(T("Notes")) + '</th></tr></thead><tbody>' + rows + '</tbody></table></div>' : "";
  const holder = S_holder(M) ? '<p class="sp-fine">' + esc(T("Holds the seat today: {name}{party}, {run}.", {name: M.S.holder.n, party: M.partisan && M.S.holder.party ? " (" + M.S.holder.party + ")" : "", run: M.S.holder.running === true ? T("on the ballot for it") : M.S.holder.running === false ? T("not on the ballot for it") : T("where the record says")})) + '</p>' : "";
  const srcLine = src.agency || src.title ? '<p class="sp-fine">' + esc(T("The list: {title}{agency}.", {title: src.title || T("the official list"), agency: src.agency ? T(", {agency}", {agency: src.agency}) : ""})) + " " + nbLink(L, "list", esc(T("The list and its source"))) + '</p>' : "";
  const facts = [];
  if (!M.partisan) facts.push(T("Nonpartisan office: no party is printed beside the names."));
  if (M.S.special) facts.push(T("A special election."));
  if (M.S.date) facts.push(T("Election day: {day}.", {day: day(M.S.date)}));
  return '<div class="sp-row"><h3>' + esc(T("On the ballot")) + '</h3>' + nbLink(L, "list", esc(T("The list and its source"))) + '</div>'
    + '<p class="sp-fine">' + esc(lede) + (facts.length ? " " + esc(facts.join(" ")) : "") + '</p>' + table + holder + srcLine
    + (M.S.primaries && L && typeof L.hasFull === "function" && L.hasFull("primaries") ? '<p class="sp-fine">' + anyLink(L.full("primaries"), esc(T("The primaries, on the full page")), "sp-nbl") + '</p>' : "");
}

/* ---------- the page ---------- */
const TAB_WORDS = {count: "Count", counties: "Counties", forecast: "Forecast", polls: "Polls", coverage: "Coverage", list: "On the ballot"};
function panelFor(M, k) {
  switch (k) {
    case "count": return countPanel(M);
    case "counties": return countiesPanel(M);
    case "forecast": return forecastPanel(M);
    case "polls": return pollsPanel(M);
    case "coverage": return coveragePanel(M);
    default: return listPanel(M);
  }
}
function railItem(k, text, href, cur) {
  if (!href) return "";
  return '<a href="' + esc(href) + '"' + (cur ? ' aria-current="location"' : "") + '><svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">' + ICON[k] + '</svg><span>' + text + '</span></a>';
}
function chipsTop(M) {
  const c = [];
  if (M.count) {
    c.push(chip(esc(T("Official count")), "official"));
    c.push(M.final ? chip(esc(T("Certified")), "official") : chip(esc(T("As reported, not final")), "notfinal"));
    if (M.rep) c.push(chip(esc(T("{a} of {b} precincts", {a: num(M.rep[0]), b: num(M.rep[1])}))));
    if (M.count.at) c.push(chip(esc(T("Read {when}", {when: when(M.count.at)}))));
  } else {
    c.push(chip(esc(T("No count on file yet")), "notfinal"));
    c.push(chip(esc(M.kind === "none" ? T("No candidate listed") : M.list.length === 1 ? T("1 name on the ballot") : T("{n} names on the ballot", {n: num(M.list.length)}))));
  }
  if (M.seats > 1) c.push(chip(esc(T("Vote for {n}", {n: num(M.seats)}))));
  if (!M.partisan) c.push(chip(esc(T("Nonpartisan office"))));
  if (M.kind === "retention") c.push(chip(esc(T("Retention vote"))));
  if (M.kind === "unopposed") c.push(chip(esc(T("Unopposed"))));
  if (M.S.special) c.push(chip(esc(T("Special election"))));
  return c.join("");
}
function render(S, L) {
  if (!S || typeof S !== "object") return "";
  const M = model(S, L);
  const tabs = M.tabs, one = tabs.length < 2;
  const tablist = tabs.map((k, i) => '<button type="button" class="sp-tab" role="tab" id="' + ID + '-t-' + k + '" aria-controls="' + ID + '-p-' + k + '" aria-selected="' + (i === 0 ? "true" : "false") + '" tabindex="' + (i === 0 ? 0 : -1) + '" data-tab="' + k + '">' + esc(T(TAB_WORDS[k])) + (i < 9 ? '<kbd aria-hidden="true">' + (i + 1) + '</kbd>' : "") + '</button>').join("");
  const sections = tabs.map((k, i) => '<section class="sp-panel' + (i === 0 ? " is-on" : "") + '" role="' + (one ? "region" : "tabpanel") + '" id="' + ID + '-p-' + k + '" aria-labelledby="' + ID + '-t-' + k + '" data-panel="' + k + '" tabindex="0">' + panelFor(M, k) + '</section>').join("");
  const night = addr(L, "night"), past = addr(L, "past"), chart = addr(L, "chart");
  const full = L && typeof L.full === "function" ? (() => { try { return L.full("tabs"); } catch (e) { return ""; } })() : "";
  const fullHref = full ? (/^\s*</.test(String(full)) ? ((/href\s*=\s*"([^"]*)"/i.exec(String(full)) || [])[1] || "") : String(full)) : "";
  const rail = '<button type="button" class="sp-rail-nb" aria-expanded="false" aria-controls="' + ID + '-pane"><svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">' + ICON.nb + '</svg><span>' + esc(T("The notebook")) + '</span></button>'
    + railItem("night", esc(T("Election Night")), night) + railItem("past", esc(T("Past results")), past) + railItem("chart", esc(T("The chart")), chart) + railItem("full", esc(T("The full page")), fullHref)
    + '<span class="sp-rail-sp"></span><button type="button" class="sp-rail-keys" aria-controls="' + ID + '-pane"><svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">' + ICON.keys + '</svg><span>' + esc(T("Shortcuts")) + '</span></button>';
  const crumb = [esc(S.state || ""), esc(S.place && S.place !== S.state ? S.place : ""), esc(S.office || "")].filter(Boolean).join(' <span aria-hidden="true">›</span> ');
  const tools = '<button type="button" class="sp-btn sp-notes" aria-expanded="false" aria-controls="' + ID + '-pane"><span class="sp-nbi" aria-hidden="true"></span>' + esc(T("Notes pane")) + ' <kbd aria-hidden="true">n</kbd></button>'
    + '<button type="button" class="sp-btn sp-helpb" aria-controls="' + ID + '-pane">' + esc(T("Shortcuts")) + ' <kbd aria-hidden="true">?</kbd></button>'
    + (night ? '<a class="sp-btn sp-site" href="' + esc(night) + '">' + esc(T("On Election Night")) + '</a>' : "")
    + (fullHref ? '<a class="sp-btn sp-site" href="' + esc(fullHref) + '">' + esc(T("The full page")) + '</a>' : "");
  return '<div class="sp" data-sp-root data-kind="' + esc(M.kind) + '">'
    + '<p id="' + ID + '-hint" class="sp-sr">' + esc(T("Opens this figure’s notebook entry beside the workspace.")) + '</p>'
    + '<p class="sp-sr sp-live" aria-live="polite"></p>'
    + '<div class="sp-app"><div class="sp-railw"><nav class="sp-rail" aria-label="' + esc(T("Around this race")) + '">' + rail + '</nav></div>'
    + '<div class="sp-main"><div class="sp-bar"><div class="sp-bar-l"><p class="sp-crumb">' + crumb + '</p><h2 class="sp-title">' + esc(S.title || ((S.state ? S.state + ": " : "") + (S.office || ""))) + '</h2><div class="sp-chips">' + chipsTop(M) + '</div></div>'
    + '<div class="sp-tools">' + tools + '</div></div>'
    + '<p class="sp-hintline"><span class="sp-nbi" aria-hidden="true"></span>' + esc(T("Press any figure for its notebook entry: where it comes from, how it was worked out, what it cannot tell you.")) + '</p>'
    + '<div class="sp-kpis">' + tiles(M) + '</div>'
    + (one ? "" : '<div class="sp-tabs" role="tablist" aria-label="' + esc(T("Parts of this race")) + '">' + tablist + '</div>')
    + sections + '</div>'
    + '<aside class="sp-pane" id="' + ID + '-pane" role="complementary" aria-label="' + esc(T("Notebook pane")) + '" hidden>'
    + '<div class="sp-grip" role="separator" aria-orientation="vertical" aria-label="' + esc(T("Resize the notes pane")) + '" aria-valuemin="320" aria-valuemax="780" aria-valuenow="420" tabindex="0"></div>'
    + '<div class="sp-sheet"><div class="sp-grab" aria-hidden="true"><i></i></div>'
    + '<header class="sp-pane-h"><div class="sp-pane-t"><p class="sp-pane-k">' + esc(T("Notebook")) + '</p><button type="button" class="sp-pane-x" aria-label="' + esc(T("Close the notes pane")) + '">×</button></div>'
    + '<div class="sp-pane-acts"><span class="sp-pane-openw"></span><button type="button" class="sp-btn sp-pane-copy">' + esc(T("Copy link")) + '</button><p class="sp-pane-msg" hidden></p></div></header>'
    + '<div class="sp-pane-b" tabindex="-1"></div></div></aside>'
    + '<div class="sp-scrim" hidden></div></div></div>';
}

/* ---------- the shortcuts, listed in the pane ---------- */
function shortcutsHTML(M) {
  const rows = [];
  if (M.tabs.length > 1) rows.push(["1–" + Math.min(9, M.tabs.length), M.tabs.map(k => T(TAB_WORDS[k])).join(", ")]);
  rows.push(["n", T("Open or close the notes pane")], ["Esc", T("Close the pane")], ["j k", T("Next or previous figure")], ["Enter", T("Open the figure you are on")]);
  if (M.counties) rows.push(["/", T("Filter the counties")]);
  rows.push(["[ ]", T("Narrower or wider pane (drag its edge too)")], ["o", T("Open the pane’s entry in the notebook itself")], ["?", T("This list")]);
  return '<article class="sp-keys"><h2 class="sp-keys-h" tabindex="-1">' + esc(T("Keyboard shortcuts")) + '</h2><p class="sp-fine">' + esc(T("They work anywhere on this page except while you type in a box.")) + '</p><dl>'
    + rows.map(r => '<dt>' + r[0].split(" ").map(k => '<kbd>' + esc(k) + '</kbd>').join(" ") + '</dt><dd>' + esc(r[1]) + '</dd>').join("") + '</dl>'
    + '<p class="sp-fine">' + esc(T("On a phone, the pane is a sheet: drag its handle down to close it, up for a taller sheet.")) + '</p></article>';
}

/* ---------- wiring ---------- */
function wire(root, S, L) {
  if (!root || !S) return () => {};
  const M = model(S, L);
  const sp = root.querySelector("[data-sp-root]"); if (!sp) return () => {};
  sp.setAttribute("data-js", "1");
  const $ = (s, el) => (el || sp).querySelector(s), $$ = (s, el) => Array.prototype.slice.call((el || sp).querySelectorAll(s));
  const app = $(".sp-app"), pane = $(".sp-pane"), paneBody = $(".sp-pane-b"), live = $(".sp-live"), scrim = $(".sp-scrim");
  const btnNotes = $(".sp-notes"), btnHelp = $(".sp-helpb"), railNb = $(".sp-rail-nb"), railKeys = $(".sp-rail-keys"), grip = $(".sp-grip"), grab = $(".sp-grab"), paneHead = $(".sp-pane-h");
  const openW = $(".sp-pane-openw"), msg = $(".sp-pane-msg"), copyBtn = $(".sp-pane-copy"), closeBtn = $(".sp-pane-x");
  const store = {
    get() { try { return JSON.parse(localStorage.getItem(KEY) || "{}") || {}; } catch (e) { return {}; } },
    set(patch) { try { localStorage.setItem(KEY, JSON.stringify(Object.assign(store.get(), patch))); } catch (e) { /* kept for this visit only */ } }
  };
  const phone = () => { try { return window.matchMedia("(max-width: 820px)").matches; } catch (e) { return false; } };
  const motion = () => !calm();
  let sayT = 0;
  const say = t => { if (!live) return; live.textContent = ""; clearTimeout(sayT); sayT = setTimeout(() => { live.textContent = t; }, 40); };
  const cur = {tab: M.tabs[0] || "list", nb: null, kind: null};
  const offs = [];                                                          /* every listener, removed on cleanup */
  const on = (el, ev, fn, opt) => { if (!el) return; el.addEventListener(ev, fn, opt); offs.push(() => el.removeEventListener(ev, fn, opt)); };

  /* tabs */
  const tabs = $$(".sp-tab"), panels = $$(".sp-panel");
  function showTab(id, focus) {
    if (M.tabs.indexOf(id) < 0) id = M.tabs[0];
    cur.tab = id;
    tabs.forEach(t => { const onIt = t.dataset.tab === id; t.setAttribute("aria-selected", onIt ? "true" : "false"); t.tabIndex = onIt ? 0 : -1; if (onIt && focus) t.focus(); });
    panels.forEach(p => p.classList.toggle("is-on", p.dataset.panel === id));
  }
  tabs.forEach((t, i) => {
    on(t, "click", () => showTab(t.dataset.tab, false));
    on(t, "keydown", e => {
      const n = tabs.length; let j = null;
      if (e.key === "ArrowRight") j = (i + 1) % n; else if (e.key === "ArrowLeft") j = (i - 1 + n) % n; else if (e.key === "Home") j = 0; else if (e.key === "End") j = n - 1;
      if (j === null) return;
      e.preventDefault(); showTab(tabs[j].dataset.tab, true);
    });
  });
  showTab(cur.tab, false);

  /* the pane: a column beside the workspace, a sheet from the bottom on a phone */
  let opener = null, seq = 0, swipeOff = null;
  function setMode() {
    if (phone()) { pane.setAttribute("role", "dialog"); pane.setAttribute("aria-modal", "true"); scrim.hidden = pane.hidden; }
    else { pane.setAttribute("role", "complementary"); pane.removeAttribute("aria-modal"); scrim.hidden = true; }
  }
  function openPane(from) {
    const was = !pane.hidden;
    if (!was) opener = from || (sp.contains(document.activeElement) ? document.activeElement : btnNotes);
    pane.hidden = false; app.setAttribute("data-pane", "open");
    [btnNotes, railNb].forEach(b => b && b.setAttribute("aria-expanded", "true"));
    setMode();
    if (!was && motion()) { pane.classList.add("is-in"); pane.addEventListener("animationend", () => pane.classList.remove("is-in"), {once: true}); }
    return was;
  }
  function setOpenLink(path) {
    openW.innerHTML = path ? nbLink(L, path, esc(T("Open in the notebook")), "sp-pane-open") : "";
    copyBtn.hidden = !path;
  }
  function wrapTables(el) {
    $$("table", el).forEach(t => {
      if (t.closest(".sp-tw") || (t.parentElement && /auto|scroll/.test(getComputedStyle(t.parentElement).overflowX))) return;
      const w = document.createElement("div"); w.className = "sp-tw"; w.tabIndex = 0; w.setAttribute("role", "region");
      const cap = t.querySelector("caption"); w.setAttribute("aria-label", cap ? cap.textContent : T("Table"));
      t.parentNode.insertBefore(w, t); w.appendChild(t);
    });
  }
  function landed(title) {
    const h = paneBody.querySelector("h1, h2, h3, .sp-keys-h");
    if (h) { h.tabIndex = -1; if (!h.id) h.id = ID + "-pane-title"; pane.setAttribute("aria-labelledby", h.id); pane.removeAttribute("aria-label"); }
    else { pane.removeAttribute("aria-labelledby"); pane.setAttribute("aria-label", T("Notebook pane")); }
    paneBody.scrollTop = 0;
    (h || paneBody).focus({preventScroll: true});
    say(T("Notebook: {t}", {t: title || (h ? h.textContent : "")}));
  }
  async function openNb(path, from) {
    openPane(from);
    const my = ++seq;
    cur.nb = path; cur.kind = "nb";
    setOpenLink(path);
    paneBody.innerHTML = '<p class="sp-pane-wait">' + esc(T("Loading the notebook…")) + '</p>';
    let html = "", fail = false;
    try { html = await V.entry(path); } catch (e) { fail = true; }
    if (my !== seq) return;
    if (fail || !html) {
      paneBody.innerHTML = '<p class="sp-pane-wait">' + esc(fail ? T("The notebook could not be loaded here.") : T("There is no notebook entry at that address.")) + " " + nbLink(L, path, esc(T("Open the notebook")), "sp-nbl") + '</p>';
      paneBody.focus({preventScroll: true});
      say(fail ? T("The notebook could not be loaded") : T("No notebook entry at that address"));
      return;
    }
    if (html && typeof html === "object" && html.nodeType) { paneBody.innerHTML = ""; paneBody.appendChild(html); }
    else paneBody.innerHTML = String(html);
    wrapTables(paneBody);
    landed("");
  }
  function openKeys(from) {
    openPane(from); seq++;
    cur.nb = null; cur.kind = "keys";
    setOpenLink("");
    paneBody.innerHTML = shortcutsHTML(M);
    landed(T("Keyboard shortcuts"));
  }
  function closePane() {
    if (pane.hidden) return;
    pane.hidden = true; app.removeAttribute("data-pane");
    pane.style.transform = ""; scrim.hidden = true;
    [btnNotes, railNb].forEach(b => b && b.setAttribute("aria-expanded", "false"));
    cur.nb = null; cur.kind = null;
    const back = opener && opener.isConnected ? opener : btnNotes;
    opener = null;
    if (back && typeof back.focus === "function") back.focus();
    say(T("Notes pane closed"));
  }
  const entryOfTab = () => ENTRY[cur.tab] && M.href[ENTRY[cur.tab]] ? ENTRY[cur.tab] : (M.href.list ? "list" : (M.href.count ? "count" : ""));
  function toggleNotes(from) {
    if (!pane.hidden && cur.kind === "nb") return closePane();
    const p = entryOfTab();
    if (p) openNb(p, from); else openKeys(from);
  }
  /* every figure: a link to its notebook entry, opened here instead (plain clicks only; a modifier key opens the notebook itself) */
  on(sp, "click", e => {
    const a = e.target && e.target.closest ? e.target.closest("a[data-sp-nb]") : null;
    if (!a || !sp.contains(a) || e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    e.preventDefault(); e.stopPropagation();
    openNb(a.getAttribute("data-sp-nb"), pane.contains(a) ? null : a);
  }, true);
  on(btnNotes, "click", () => toggleNotes(btnNotes));
  on(railNb, "click", () => toggleNotes(railNb));
  on(btnHelp, "click", () => (cur.kind === "keys" && !pane.hidden ? closePane() : openKeys(btnHelp)));
  on(railKeys, "click", () => (cur.kind === "keys" && !pane.hidden ? closePane() : openKeys(railKeys)));
  on(closeBtn, "click", closePane);
  on(scrim, "click", closePane);
  let noteT = 0;
  function note(t) { msg.textContent = t; msg.hidden = false; say(t); clearTimeout(noteT); noteT = setTimeout(() => { msg.hidden = true; }, 2600); }
  on(copyBtn, "click", async () => {
    const a = openW.querySelector("a[href]");
    if (!a) return;
    let href = a.getAttribute("href") || "";
    try { href = new URL(href, location.href).href; } catch (e) { /* as written */ }
    try { await navigator.clipboard.writeText(href); note(T("Link copied: it opens the notebook at this entry")); }
    catch (e) { note(T("Could not copy here; the Open in the notebook link holds the address")); }
  });
  let mql = null;
  try { mql = window.matchMedia("(max-width: 820px)"); } catch (e) { mql = null; }
  const onMq = () => { if (!pane.hidden) setMode(); };
  if (mql) { try { mql.addEventListener("change", onMq); offs.push(() => mql.removeEventListener("change", onMq)); } catch (e) { /* older browsers */ } }
  /* focus stays in the sheet while it is a dialog */
  on(pane, "keydown", e => {
    if (e.key !== "Tab" || !phone()) return;
    const f = $$("a[href],button:not([disabled]),input,[tabindex]:not([tabindex='-1'])", pane).filter(el => el.offsetParent !== null);
    if (!f.length) return;
    const a = document.activeElement, first = f[0], last = f[f.length - 1];
    if (e.shiftKey && (a === first || f.indexOf(a) < 0)) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && a === last) { e.preventDefault(); first.focus(); }
  });

  /* keys: only while nothing outside this view holds the keyboard */
  const filterIn = $(".sp-cfilter");
  function figs() { return $$("a[data-sp-nb]", app).filter(a => !pane.contains(a) && a.offsetParent !== null); }
  function moveFig(d) {
    const list = figs(); if (!list.length) return;
    const i = list.indexOf(document.activeElement);
    const j = i < 0 ? (d > 0 ? 0 : list.length - 1) : (i + d + list.length) % list.length;
    list[j].focus(); list[j].scrollIntoView({block: "nearest"});
  }
  const mine = () => { const a = document.activeElement; return !a || a === document.body || a === document.documentElement || sp.contains(a); };
  on(window, "keydown", e => {
    if (e.key === "Escape") { if (!pane.hidden && (mine() || pane.contains(document.activeElement))) { e.preventDefault(); closePane(); } return; }
    if (e.defaultPrevented || e.metaKey || e.ctrlKey || e.altKey || !mine()) return;
    const t = e.target, tag = t && t.tagName;
    if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || (t && t.isContentEditable)) return;
    if (document.querySelector("dialog[open]")) return;
    const k = e.key;
    if (k === "?") { e.preventDefault(); if (cur.kind === "keys" && !pane.hidden) closePane(); else openKeys(null); return; }
    if (/^[1-9]$/.test(k) && M.tabs.length > 1 && M.tabs[+k - 1]) { e.preventDefault(); showTab(M.tabs[+k - 1], true); return; }
    if (k === "n") { e.preventDefault(); toggleNotes(null); return; }
    if (k === "j" || k === "k") { e.preventDefault(); moveFig(k === "j" ? 1 : -1); return; }
    if (k === "/" && filterIn) { e.preventDefault(); showTab("counties", false); filterIn.focus(); return; }
    if ((k === "[" || k === "]") && !pane.hidden && !phone()) { e.preventDefault(); save(setW(curW() + (k === "]" ? 40 : -40))); return; }
    if (k === "o" && !pane.hidden) { const a = openW.querySelector("a[href]"); if (a) { e.preventDefault(); a.click(); } }
  });

  /* hover or focus one figure: the rows it explains light up everywhere */
  let hiIds = [];
  function paint(ids, onIt) {
    ids.forEach(id => {
      const sel = CSS && CSS.escape ? CSS.escape(id) : id.replace(/["\\]/g, "");
      $$('[data-cand="' + sel + '"],[data-row="' + sel + '"]', app).forEach(el => el.classList.toggle("is-hi", onIt));
      if (id.charAt(0) === "c") { const p = M.people.find(x => x.id === id); if (p) $$('tr[data-lead]', app).forEach(tr => { if (tr.getAttribute("data-lead") === p.n) tr.classList.toggle("is-hi", onIt); }); }
    });
  }
  function hiFrom(target) {
    const c = target && target.closest ? target.closest("[data-hi],[data-cand],tr[data-lead]") : null;
    let ids = [];
    if (c && app.contains(c) && !pane.contains(c)) {
      if (c.hasAttribute("data-hi")) ids = c.getAttribute("data-hi").split(/\s+/).filter(Boolean);
      else if (c.hasAttribute("data-cand")) ids = [c.getAttribute("data-cand")].filter(Boolean);
      else if (c.hasAttribute("data-lead")) { const p = M.byName[c.getAttribute("data-lead")]; if (p) ids = [p.id]; }
    }
    if (ids.join(" ") === hiIds.join(" ")) return;
    if (hiIds.length) paint(hiIds, false);
    hiIds = ids;
    if (ids.length) paint(ids, true);
  }
  on(app, "mouseover", e => hiFrom(e.target));
  on(app, "mouseleave", () => hiFrom(null));
  on(app, "focusin", e => hiFrom(e.target));
  on(app, "focusout", e => { if (!e.relatedTarget || !app.contains(e.relatedTarget)) hiFrom(null); });

  /* the counties table: sort and filter */
  const tbl = $(".sp-ct"), tb = tbl ? tbl.tBodies[0] : null, rows = tb ? Array.prototype.slice.call(tb.rows) : [];
  const stat = $(".sp-tstat"), chips = $$(".sp-chipbtn");
  const STR = {name: 1, lead: 1};
  let sortKey = "total", sortDir = -1, leadF = "";
  function applySort() {
    if (!tb) return;
    rows.sort((a, b) => STR[sortKey] ? sortDir * (a.dataset[sortKey] || "").localeCompare(b.dataset[sortKey] || "") : sortDir * ((parseFloat(a.dataset[sortKey]) || 0) - (parseFloat(b.dataset[sortKey]) || 0)));
    rows.forEach(r => tb.appendChild(r));
    $$("th[aria-sort]", tbl).forEach(th => th.setAttribute("aria-sort", "none"));
    const b = $('.sp-sort[data-key="' + sortKey + '"]', tbl); if (b) b.closest("th").setAttribute("aria-sort", sortDir < 0 ? "descending" : "ascending");
  }
  function applyFilter() {
    if (!tb) return;
    const q = (filterIn && filterIn.value || "").trim().toLowerCase(); let n = 0;
    rows.forEach(r => { const ok = (!q || (r.dataset.name || "").indexOf(q) >= 0) && (!leadF || r.dataset.lead === leadF); r.hidden = !ok; if (ok) n++; });
    if (stat) stat.textContent = T("Showing {n} of {m} counties", {n: num(n), m: num(rows.length)}) + (n ? "" : T(": no county matches"));
  }
  $$(".sp-sort", tbl).forEach(b => on(b, "click", () => {
    const k = b.dataset.key;
    if (k === sortKey) sortDir = -sortDir; else { sortKey = k; sortDir = STR[k] ? 1 : -1; }
    applySort();
    say(T("Sorted by {col}, {how}", {col: b.textContent.trim(), how: STR[k] ? (sortDir > 0 ? T("A to Z") : T("Z to A")) : (sortDir < 0 ? T("largest first") : T("smallest first"))}));
  }));
  on(filterIn, "input", applyFilter);
  chips.forEach(c => on(c, "click", () => { leadF = c.dataset.lead || ""; chips.forEach(x => x.setAttribute("aria-pressed", x === c ? "true" : "false")); applyFilter(); }));

  /* the pane's width, dragged or by keys, remembered on this device */
  const W0 = 420;
  function bounds() { const W = app.getBoundingClientRect().width || 1200; return [320, Math.max(320, Math.min(780, Math.round(W * 0.6)))]; }
  function curW() { return parseInt(app.style.getPropertyValue("--pane-w"), 10) || W0; }
  function setW(w) {
    const b = bounds(); w = Math.max(b[0], Math.min(b[1], Math.round(w)));
    app.style.setProperty("--pane-w", w + "px");
    grip.setAttribute("aria-valuemin", b[0]); grip.setAttribute("aria-valuemax", b[1]); grip.setAttribute("aria-valuenow", w); grip.setAttribute("aria-valuetext", T("{w} pixels wide", {w: num(w)}));
    return w;
  }
  function save(w) { store.set({w: w}); }
  let dragOff = null;
  const endDrag = () => { if (dragOff) { dragOff(); dragOff = null; } };
  on(grip, "pointerdown", e => {
    if (phone()) return;
    e.preventDefault(); endDrag();
    const x0 = e.clientX, w0 = curW();
    app.classList.add("is-resizing");
    const mv = ev => setW(w0 + (x0 - ev.clientX));
    const up = () => { endDrag(); app.classList.remove("is-resizing"); save(curW()); };
    window.addEventListener("pointermove", mv); window.addEventListener("pointerup", up); window.addEventListener("pointercancel", up);
    dragOff = () => { window.removeEventListener("pointermove", mv); window.removeEventListener("pointerup", up); window.removeEventListener("pointercancel", up); };
  });
  on(grip, "keydown", e => {
    const b = bounds(); let w = null;
    if (e.key === "ArrowLeft") w = curW() + 24; else if (e.key === "ArrowRight") w = curW() - 24; else if (e.key === "Home") w = b[0]; else if (e.key === "End") w = b[1];
    if (w === null) return; e.preventDefault(); save(setW(w));
  });
  on(grip, "dblclick", () => save(setW(W0)));

  /* the sheet on a phone: drag the handle down to close, up for a taller sheet */
  function startSwipe(e) {
    if (!phone() || pane.hidden || (e.target.closest && e.target.closest("a,button,input"))) return;
    e.preventDefault(); if (swipeOff) swipeOff();
    const y0 = e.clientY, t0 = (window.performance ? performance.now() : Date.now()); let dy = 0;
    pane.classList.add("is-dragging");
    const mv = ev => { dy = ev.clientY - y0; pane.style.transform = dy > 0 ? "translateY(" + dy + "px)" : "translateY(" + (Math.max(dy, -60) / 4) + "px)"; };
    const up = () => {
      swipeOff(); swipeOff = null;
      pane.classList.remove("is-dragging"); pane.style.transform = "";
      const v = dy / Math.max(1, (window.performance ? performance.now() : Date.now()) - t0);
      if (dy > 120 || (dy > 30 && v > 0.6)) closePane();
      else if (dy < -50) { pane.setAttribute("data-sheet", "tall"); store.set({tall: true}); }
    };
    window.addEventListener("pointermove", mv); window.addEventListener("pointerup", up); window.addEventListener("pointercancel", up);
    swipeOff = () => { window.removeEventListener("pointermove", mv); window.removeEventListener("pointerup", up); window.removeEventListener("pointercancel", up); };
  }
  on(grab, "pointerdown", startSwipe);
  on(paneHead, "pointerdown", startSwipe);

  /* start */
  const s0 = store.get();
  setW(isNum(+s0.w) && s0.w ? +s0.w : W0);
  if (s0.tall) pane.setAttribute("data-sheet", "tall");
  applyFilter();

  return () => {
    endDrag(); if (swipeOff) { swipeOff(); swipeOff = null; }
    clearTimeout(sayT); clearTimeout(noteT);
    offs.splice(0).forEach(f => { try { f(); } catch (e) { /* already gone */ } });
  };
}

V.add({id: "split", label: "Workbench", order: 3, render: render, wire: wire});
})();

/* ======== timeline ======== */
/* The story so far (view "timeline", views_src/SPEC.md): a race as a dated line, from the official list to the result,
   with a scrubber that walks the forecast runs to the count.

   Ported from the sandbox example (sandbox_src/layouts/timeline.py), which rendered one race in Python at build time;
   this renders any race in the browser from S (version 1). The events are chosen from what S carries: the official list
   and the primaries (undated: the record gives no dates), the newest polls by the day their fieldwork ended, every
   forecast run, Election Day, the latest reading of the count (certified or "as reported, not final"), the calls and
   statements and stories in the coverage, and the steps still to come. Before any count the line ends at the day the
   figures were read and looks ahead to Election Day.

   No time-zone rule lives here: a stamp's calendar day in the state's own zone is found by matching VIEWS.day's words,
   and positions on the axis are plain milliseconds (a date alone sits at noon UTC, inside that day in every US zone, and
   positions are kept in the order the events are listed).

   Owned by this file and timeline.css alone; nothing outside the root it is given is touched. */
(function () {
  "use strict";
  var V = typeof VIEWS !== "undefined" ? VIEWS : null;
  if (!V || typeof V.add !== "function") return;

  var DAY = 864e5;
  var T = function (s, v) { return V.T(s, v || {}); };
  var esc = function (s) { return V.esc(s == null ? "" : String(s)); };
  /* T with every string variable escaped: for sentences that become HTML */
  var E = function (s, v) {
    var o = {}, k;
    for (k in (v || {})) o[k] = typeof v[k] === "string" ? esc(v[k]) : v[k];
    return T(s, o);
  };
  var num = function (n) { return V.num(n == null ? 0 : n); };
  var pct = function (x, d) { return V.pct(x == null ? 0 : x, d == null ? 1 : d); };
  var chance = function (p) { return V.chance(p); };
  var dayW = function (iso) { return iso ? V.day(iso) : ""; };
  var whenW = function (iso) { return iso ? V.when(iso) : ""; };

  /* ---------- dates: the calendar day in the state's own zone, by VIEWS.day's own words ---------- */
  var isDate = function (s) { return typeof s === "string" && /^\d{4}-\d{2}-\d{2}/.test(s); };
  var utcOf = function (key) { return Date.UTC(+key.slice(0, 4), +key.slice(5, 7) - 1, +key.slice(8, 10)); };
  var keyOf = function (ms) { return new Date(ms).toISOString().slice(0, 10); };
  var shift = function (key, n) { return keyOf(utcOf(key) + n * DAY); };
  var norm = function (s) { return String(s || "").replace(/\d{4}/g, "").replace(/[\s,.]+/g, " ").trim().toLowerCase(); };
  function localKey(iso) {
    if (!isDate(iso)) return "";
    if (iso.length <= 10) return iso.slice(0, 10);
    var utc = iso.slice(0, 10), w = norm(dayW(iso)), ks = [utc, shift(utc, -1), shift(utc, 1)], i;
    if (!w) return utc;
    for (i = 0; i < ks.length; i++) if (norm(dayW(ks[i])) === w) return ks[i];
    return utc;
  }
  function rawPos(iso) {
    if (!isDate(iso)) return NaN;
    if (iso.length <= 10) return utcOf(iso) + DAY / 2;
    var t = Date.parse(iso);
    return isNaN(t) ? utcOf(iso.slice(0, 10)) + DAY / 2 : t;
  }
  var hasTime = function (iso) { return isDate(iso) && iso.length > 10; };
  var WD = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
  var weekday = function (key) { return T(WD[new Date(utcOf(key)).getUTCDay()]); };
  var longDay = function (key) { return T("{weekday}, {date}", {weekday: weekday(key), date: dayW(key)}); };
  function rel(key, ed) {
    if (!ed) return "";
    var n = Math.round((utcOf(key) - utcOf(ed)) / DAY);
    if (n === 0) return T("Election Day");
    if (n === 1) return T("the day after Election Day");
    if (n === -1) return T("the day before Election Day");
    return n < 0 ? T("{n} days before Election Day", {n: -n}) : T("{n} days after Election Day", {n: n});
  }
  var timeW = function (iso) {
    /* the time of day alone: VIEWS.when gives "November 10, 9:04 p.m. ET"; the day's words are cut off the front */
    var w = whenW(iso), d = dayW(iso);
    if (d && w.indexOf(d) === 0) w = w.slice(d.length).replace(/^[\s,]+/, "");
    return w;
  };

  /* ---------- small words ---------- */
  function joinNames(list) {
    var a = list.slice();
    if (!a.length) return "";
    if (a.length === 1) return a[0];
    if (a.length === 2) return T("{a} and {b}", {a: a[0], b: a[1]});
    return T("{list} and {last}", {list: a.slice(0, -1).join(", "), last: a[a.length - 1]});
  }
  var one = function (n, single, many, vars) { var v = vars || {}; v.n = num(n); return n === 1 ? T(single, v) : T(many, v); };
  var ext = function (url, text) {
    return url ? '<a class="tl-xl" href="' + esc(url) + '" rel="noopener" target="_blank">' + text +
      '<span class="tl-ext" aria-hidden="true">&#8599;</span><span class="tl-sr"> ' + esc(T("(opens in a new tab)")) + "</span></a>" : "";
  };
  var KIND = {c: "Conceded", v: "Declared victory", s: "Statement"};
  var MEDIUM = {t: "in text", v: "on video", p: "in a post"};
  var TIER = {national: "National news", state: "State news", local: "Local news"};
  var slug = function (s) { return String(s || "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") || "x"; };

  /* ---------- the model: every event, its words, its place on the line ---------- */
  var cache = typeof WeakMap === "function" ? new WeakMap() : null;

  function model(S, L) {
    var kind = S.kind || "contest", seats = S.seats || 1, partisan = !!S.partisan;
    var ED = isDate(S.date) ? S.date.slice(0, 10) : "";
    var READ = isDate(S.read) ? S.read.slice(0, 10) : keyOf(Date.now());
    var C = S.count && S.count.cands && S.count.cands.length ? S.count : null;
    var F = kind === "contest" && S.forecast && S.forecast.top && S.forecast.top.length ? S.forecast : null;   /* never for an unopposed race */
    var P = S.polls && S.polls.newest && S.polls.newest.length ? S.polls : null;
    var CV = S.coverage || null;
    var calls = CV && CV.calls ? CV.calls.filter(function (c) { return c && c.o; }) : [];
    var said = [];
    (CV && CV.said ? CV.said : []).forEach(function (s) { (s.s || []).forEach(function (x) { said.push({n: s.n, x: x}); }); });
    var news = [];
    if (CV && CV.news) Object.keys(CV.news).forEach(function (tier) {
      ((CV.news[tier] || {}).top || []).forEach(function (x) { if (x && x.h) news.push({tier: tier, x: x}); });
    });
    var lead = C ? C.cands[0] : null, second = C && C.cands.length > 1 ? C.cands[1] : null;
    var office = S.source && S.source.office ? S.source.office : "";
    var tops = C ? C.cands.slice(0, Math.max(1, seats)) : [];

    var has = function (p) { try { return !!(L && L.has && L.has(p)); } catch (e) { return false; } };
    var nb = function (p, text, eid) {
      if (!has(p)) return "";
      try { return L.nb(p, esc(T(text)), {anchor: "vwtl-" + eid}); } catch (e) { return ""; }
    };
    var full = function (sec, text) {
      var ok = false; try { ok = !!(L && L.hasFull && L.hasFull(sec)); } catch (e) { ok = false; }
      if (!ok) return "";
      var h = ""; try { h = L.full(sec); } catch (e) { h = ""; }
      return h ? '<a class="tl-fl" href="' + esc(h) + '">' + esc(T(text)) + "</a>" : "";
    };
    var sw = function (code) {
      if (!partisan || !code) return "";
      var v = ""; try { v = V.partyVar(code) || ""; } catch (e) { v = ""; }
      return v ? '<span class="tl-sw" style="background:var(' + esc(v) + ')" aria-hidden="true"></span>' : "";
    };
    var partyW = function (c) { return partisan && c && c.party ? c.party : ""; };
    var nameP = function (c) { return esc(c.n) + (partyW(c) ? ' <span class="tl-pty">(' + esc(partyW(c)) + ")</span>" : ""); };

    /* the chart's subject: the count's leader when the forecast followed them, else the forecast's favourite */
    var subj = null, subjTop = null;
    if (F) {
      var seen = {};
      (F.hist || []).forEach(function (h) { Object.keys(h.c || {}).forEach(function (n) { seen[n] = 1; }); });
      F.top.forEach(function (c) { seen[c.n] = 1; });
      subj = lead && seen[lead.n] ? lead.n : F.top[0].n;
      F.top.forEach(function (c) { if (c.n === subj) subjTop = c; });
    }
    var other = null;   /* the second name in the subject's story */
    if (F) F.top.forEach(function (c) { if (!other && c.n !== subj) other = c; });
    if (!other && second && second.n !== subj) other = {n: second.n};

    var track = "";
    if (F && F.track && F.track.n) {
      var tr = F.track;
      track = T("Track record: of {n} past races of this kind, the favourite had the most votes in {fav}; the result fell inside the 80-in-100 range in {h80} and inside the 95-in-100 range in {h95}; shares were off by {mae} points on average.",
        {n: num(tr.n), fav: num(tr.fav || 0), h80: num(tr.h80 || 0), h95: num(tr.h95 || 0), mae: tr.mae == null ? "?" : String(tr.mae)});
      if (tr.thin) track += " " + T("A thin record: few past races to test on.");
    }

    var EV = [];
    var add = function (e) { EV.push(e); return e; };

    /* ---- the official list (undated: the record gives no filing date) */
    var listRows = (S.list || []).map(function (c, i) {
      var notes = [];
      if (c.inc) notes.push(T("in office now"));
      if (c.wi) notes.push(T("write-in"));
      if (c.out) notes.push(esc(c.out));
      return "<tr><td class=\"tl-n\">" + (c.order == null ? "" : esc(String(c.order))) + "</td><th scope=\"row\">" + sw(c.code) + esc(c.n) + "</th>" +
        (partisan ? "<td>" + esc(c.party || "") + "</td>" : "") + "<td>" + notes.join(", ") + "</td></tr>";
    }).join("");
    var listTable = (S.list || []).length ? '<div class="tl-scroll"><table class="tl-table"><caption class="tl-sr">' + esc(T("The official list")) + "</caption><thead><tr><th scope=\"col\">" +
      esc(T("Order")) + '</th><th scope="col">' + esc(T("Name as filed")) + "</th>" + (partisan ? '<th scope="col">' + esc(T("Party")) + "</th>" : "") +
      '<th scope="col">' + esc(T("Notes")) + "</th></tr></thead><tbody>" + listRows + "</tbody></table></div>" : "";
    var names = (S.list || []).map(function (c) { return c.n; });
    var holderW = "";
    if (S.holder && S.holder.n) {
      holderW = S.holder.running ? E("{name} holds the seat today and is on the list.", {name: S.holder.n}) : E("{name} holds the seat today and is not on the list.", {name: S.holder.n});
      if (partisan && S.holder.party) holderW = S.holder.running ? E("{name} ({party}) holds the seat today and is on the list.", {name: S.holder.n, party: S.holder.party}) : E("{name} ({party}) holds the seat today and is not on the list.", {name: S.holder.n, party: S.holder.party});
    }
    var srcW = S.list_source && S.list_source.agency ? E("From {agency}: {title}.", {agency: S.list_source.agency, title: S.list_source.title || T("the official list")}) : "";
    var listHead, listText, listLabel = T("The official list");
    if (kind === "none" || !names.length) {
      listHead = T("No candidate is on the list for this office");
      listText = T("The official list carries no name for this office.") + (holderW ? " " + holderW : "");
    } else if (kind === "retention") {
      listHead = E("{name}: shall they be kept in office?", {name: names[0]});
      listText = T("A yes-or-no vote about one person. No one runs against them.") + (holderW ? " " + holderW : "");
    } else if (kind === "unopposed") {
      listHead = seats > 1 ? E("{names}, unopposed", {names: joinNames(names)}) : E("{name}, unopposed", {name: names[0]});
      listText = T("No one runs against the names on the list.") + (holderW ? " " + holderW : "");
    } else {
      listHead = seats > 1 ? E("{k} names for {seats} seats", {k: num(names.length), seats: num(seats)}) : one(names.length, "One name on the ballot", "{n} names on the ballot");
      listText = (seats > 1 ? E("The {seats} with the most votes take the seats.", {seats: num(seats)}) : T("The one with the most votes takes the seat.")) +
        (partisan ? "" : " " + T("A nonpartisan office: no party is printed beside the names.")) + (S.special ? " " + T("A special election.") : "") + (holderW ? " " + holderW : "");
    }
    add({id: "list", kind: "list", iso: "", key: "", label: listLabel, tag: T("Official record"), tagk: "official", head: listHead, text: listText + (srcW ? " " + srcW : ""),
      more: listTable, links: [nb("list", "Who is on the ballot, as filed", "list"), full("arena", "The candidates on the full page")],
      ro: "", sr: T("The official list.")});
    if (S.primaries) add({id: "primaries", kind: "primary", iso: "", key: "", label: T("The primaries"), tag: T("Official record"), tagk: "official",
      head: T("The primaries that chose the names on this list"), text: T("The full page shows each primary and its certified votes; the record here gives no dates."),
      more: "", links: [nb("primaries", "The primaries", "primaries"), full("primaries", "The primaries on the full page")], ro: "", sr: T("The primaries.")});

    /* ---- polls, by the day their fieldwork ended */
    if (P) P.newest.forEach(function (p, i) {
      var iso = isDate(p.end) ? p.end : (isDate(p.start) ? p.start : "");
      var sh = Object.keys(p.shares || {}).map(function (n) { return {n: n, v: p.shares[n]}; }).sort(function (a, b) { return b.v - a.v; });
      var top2 = sh.slice(0, 2).map(function (c) { return E("{name} {share}", {name: c.n, share: pct(c.v)}); }).join(", ");
      var eid = "poll-" + (i + 1);
      var span = isDate(p.start) && isDate(p.end) ? E("taken {a} to {b}", {a: dayW(p.start), b: dayW(p.end)}) : (iso ? E("ended {a}", {a: dayW(iso)}) : "");
      var who = [p.n ? E("{n} {pop}", {n: num(p.n), pop: p.pop || T("people")}) : (p.pop ? esc(p.pop) : ""), p.moe != null ? E("margin of error {moe} points", {moe: String(p.moe)}) : ""].filter(Boolean).join(", ");
      var rows = sh.map(function (c) { return '<tr><th scope="row">' + esc(c.n) + '</th><td class="tl-n">' + esc(pct(c.v)) + "</td></tr>"; }).join("");
      add({id: eid, kind: "poll", iso: iso, key: localKey(iso), label: T("A poll"), tag: T("Opinion when taken"), tagk: "poll",
        head: top2 ? E("{pollster}: {top}", {pollster: p.pollster || T("A poll"), top: top2}) : esc(p.pollster || T("A poll")),
        text: [span, who].filter(Boolean).join("; ") + (span || who ? ". " : "") + T("A poll measures opinion when it was taken, not a forecast."),
        more: (rows ? '<table class="tl-table tl-table-s"><caption class="tl-sr">' + esc(T("This poll")) + "</caption><tbody>" + rows + "</tbody></table>" : "") +
          "<p>" + esc(T("We count only polls from members of the American Association for Public Opinion Research’s Transparency Initiative.")) + "</p>",
        links: [ext(p.url, esc(T("The pollster’s release"))), nb("polls", "Every poll counted", eid), full("polls", "Polls on the full page")],
        ro: "<strong>" + E("A poll, {pollster}.", {pollster: p.pollster || ""}) + "</strong> " + top2 + ". " + esc(T("Opinion when it was taken, not a forecast.")),
        sr: T("A poll by {pollster}: {top}.", {pollster: p.pollster || "", top: sh.slice(0, 2).map(function (c) { return c.n + " " + pct(c.v); }).join(", ")})});
    });

    /* ---- the forecast, run by run, for the chart's subject */
    var runs = [];
    if (F) {
      var hist = (F.hist || []).filter(function (h) { return h && isDate(h.at) && h.c && h.c[subj]; }).sort(function (a, b) { return rawPos(a.at) - rawPos(b.at); });
      hist.forEach(function (h, i) {
        var a = h.c[subj], b = other ? h.c[other.n] : null, last = i === hist.length - 1, prev = i ? hist[i - 1].c[subj] : null, eid = "fc-" + (i + 1);
        var move = "";
        if (prev) {
          var dlt = Math.round((a[0] - prev[0]) * 10) / 10;
          move = dlt === 0 ? T("Middle unchanged from the run before.") : (dlt > 0 ? T("Middle up {d} points from the run before.", {d: String(Math.abs(dlt))}) : T("Middle down {d} points from the run before.", {d: String(Math.abs(dlt))}));
        }
        var head = E("{name} at {md}, likely {l} to {h}", {name: subj, md: pct(a[0]), l: pct(a[1]), h: pct(a[2])});
        var text = (a[3] != null ? E("Chance of the most votes {ch}. ", {ch: chance(a[3])}) : "") + (b ? E("{name} {md} ({l} to {h}). ", {name: other.n, md: pct(b[0]), l: pct(b[1]), h: pct(b[2])}) : "") + move;
        var label = last ? T("Forecast run {i} of {n}, the last", {i: num(i + 1), n: num(hist.length)}) : T("Forecast run {i} of {n}", {i: num(i + 1), n: num(hist.length)});
        var rows = Object.keys(h.c).map(function (n) { return {n: n, v: h.c[n]}; }).sort(function (x, y) { return y.v[0] - x.v[0]; }).map(function (c) {
          return '<tr><th scope="row">' + esc(c.n) + '</th><td class="tl-n">' + esc(pct(c.v[0])) + '</td><td class="tl-n">' + esc(pct(c.v[1]) + " – " + pct(c.v[2])) + '</td><td class="tl-n">' + (c.v[3] == null ? "" : esc(chance(c.v[3]))) + "</td></tr>";
        }).join("");
        var more = '<div class="tl-scroll"><table class="tl-table"><caption class="tl-sr">' + esc(T("This run")) + '</caption><thead><tr><th scope="col">' + esc(T("Name")) + '</th><th scope="col">' + esc(T("Middle")) +
          '</th><th scope="col">' + esc(T("80 in 100")) + '</th><th scope="col">' + esc(T("Chance of the most votes")) + "</th></tr></thead><tbody>" + rows + "</tbody></table></div>" +
          (track ? "<p>" + esc(track) + "</p>" : "") + (last && F.env ? "<p>" + esc(T("In the model’s own words:")) + " " + esc(F.env) + "</p>" : "") +
          "<p>" + esc(T("Analysis: a forecast is this site’s own estimate, never a result, and never says 0 or 100 percent.")) + "</p>";
        var chartHref = ""; try { chartHref = L && L.chart ? (L.chart() || "") : ""; } catch (e) { chartHref = ""; }
        runs.push({id: eid, at: h.at, md: a[0], l: a[1], h: a[2], ch: a[3], i: i + 1,
          stand: E("The forecast stands at {md} for {name}, likely {l} to {h} (run {i} of {n}).", {md: pct(a[0]), name: subj, l: pct(a[1]), h: pct(a[2]), i: num(i + 1), n: num(hist.length)})});
        add({id: eid, kind: "fc", iso: h.at, key: localKey(h.at), label: label, tag: T("Analysis"), tagk: "analysis", head: head, text: text, more: more,
          links: [nb("forecast/runs", "Every run", eid), nb("forecast/how", "How the forecast is worked out", eid), nb("forecast/track", "Its track record", eid),
            chartHref ? '<a class="tl-fl" href="' + esc(chartHref) + '">' + esc(T("The race’s chart")) + "</a>" : ""],
          ro: "<strong>" + esc(label) + ".</strong> " + head + ". " + text, sr: T("{label}: {name} at {md}, likely {l} to {h}.", {label: label, name: subj, md: pct(a[0]), l: pct(a[1]), h: pct(a[2])})});
      });
    }
    var lastRun = runs.length ? runs[runs.length - 1] : null;

    /* ---- Election Day */
    var ahead = !C && ED && READ < ED;
    if (ED) {
      var edText = ahead ? E("Election Day in {place} is {date}. The count begins when the polls close; figures are the election office’s own, as reported, not final, until certified.", {place: S.place || S.state || "", date: longDay(ED)})
        : (lastRun ? E("The model’s last run stood at {md} for {name}, likely {l} to {h}. ", {md: pct(lastRun.md), name: subj, l: pct(lastRun.l), h: pct(lastRun.h)}) : "") +
          T("What follows is the count, then any calls by news organizations, then the steps that make it final.");
      add({id: "eday", kind: "eday", iso: ED, key: ED, label: T("Election Day"), tag: "", tagk: "", head: E("Election Day in {place}", {place: S.place || S.state || ""}), text: edText,
        more: "<p>" + esc(T("On the night: the count as the election office reports it, never final; calls by news organizations, shown as links only; certification later, by the state.")) + "</p>",
        links: [nb("method/labels", "What the labels mean", "eday"), nb("method/calls", "Why this site never calls a race", "eday")],
        ro: "<strong>" + esc(T("Election Day.")) + "</strong> " + esc(ahead ? T("Still ahead.") : runs.length ? T("The forecast is finished; the count begins. Figures from now on are the election office’s own, as reported, not final.") : T("The count begins. Figures from now on are the election office’s own, as reported, not final.")),
        sr: T("Election Day.")});
    }

    /* ---- the latest reading of the count */
    var cs = C && subj ? C.cands.filter(function (c) { return c.n === subj; })[0] : null;
    var fw = subjTop;
    var vs = "";
    if (C && cs && fw && fw.l80 != null && fw.h80 != null) {
      if (fw.l80 <= cs.share && cs.share <= fw.h80) vs = E("inside the forecast’s 80-in-100 range ({l} to {h})", {l: pct(fw.l80), h: pct(fw.h80)});
      else {
        var over = cs.share - (cs.share > fw.h80 ? fw.h80 : fw.l80);
        vs = over > 0 ? E("{d} points above the forecast’s 80-in-100 range ({l} to {h})", {d: String(Math.abs(Math.round(over * 10) / 10)), l: pct(fw.l80), h: pct(fw.h80)})
          : E("{d} points below the forecast’s 80-in-100 range ({l} to {h})", {d: String(Math.abs(Math.round(over * 10) / 10)), l: pct(fw.l80), h: pct(fw.h80)});
        if (fw.l95 != null && fw.h95 != null && !(fw.l95 <= cs.share && cs.share <= fw.h95)) vs += E(", and outside its 95-in-100 range too ({l} to {h}): a miss, counted in the model’s track record", {l: pct(fw.l95), h: pct(fw.h95)});
      }
    }
    var countEv = null;
    if (C) {
      var rep = C.reporting && C.reporting.length === 2 ? C.reporting : null;
      var final = !!C.final;
      var cands = C.cands.map(function (c) { return E("{name} {votes} ({share})", {name: c.n, votes: num(c.votes), share: pct(c.share)}); }).join("; ");
      var head;
      if (kind === "retention") head = C.cands.map(function (c) { return E("{name} {share}", {name: c.n, share: pct(c.share)}); }).join(", ");
      else if (seats > 1) head = E("The {seats} with the most votes so far: {names}", {seats: num(seats), names: joinNames(tops.map(function (c) { return esc(c.n); }))});
      else if (second) head = E("{name} leads the count, {a} to {b}", {name: lead.n, a: pct(lead.share), b: pct(second.share)});
      else head = E("{name}: {votes} votes ({share})", {name: lead.n, votes: num(lead.votes), share: pct(lead.share)});
      if (final && kind !== "retention") head = seats > 1 ? E("Certified: the {seats} with the most votes were {names}", {seats: num(seats), names: joinNames(tops.map(function (c) { return esc(c.n); }))})
        : E("Certified: {name} had the most votes, {a}", {name: lead.n, a: pct(lead.share)}) + (second ? E(" to {b}", {b: pct(second.share)}) : "");
      var won = S.counties && S.counties.won ? Object.keys(S.counties.won).sort(function (a, b) { return S.counties.won[b] - S.counties.won[a]; }).map(function (n) { return esc(n) + " " + num(S.counties.won[n]); }).join(", ") : "";
      var text = cands + ". " + (rep ? E("{a} of {b} precincts reporting; ", {a: num(rep[0]), b: num(rep[1])}) : "") + E("{t} votes in all.", {t: num(C.total)}) +
        (won && S.counties.n ? " " + E("Of {n} counties, where each had the most votes: {won}.", {n: num(S.counties.n), won: won}) : "") +
        (vs ? " " + E("{name}’s share is {vs}.", {name: subj, vs: vs}) : "") + (final ? "" : " " + T("Not final until certified."));
      var crow = C.cands.map(function (c) { return '<tr><th scope="row">' + sw(c.code) + esc(c.n) + "</th>" + (partisan ? "<td>" + esc(c.party || "") + "</td>" : "") + '<td class="tl-n">' + esc(num(c.votes)) + '</td><td class="tl-n">' + esc(pct(c.share)) + "</td></tr>"; }).join("");
      var more = '<div class="tl-scroll"><table class="tl-table"><caption class="tl-sr">' + esc(T("The count")) + '</caption><thead><tr><th scope="col">' + esc(T("Name")) + "</th>" + (partisan ? '<th scope="col">' + esc(T("Party")) + "</th>" : "") +
        '<th scope="col">' + esc(T("Votes")) + '</th><th scope="col">' + esc(T("Share")) + "</th></tr></thead><tbody>" + crow + "</tbody></table></div>";
      if (S.counties && S.counties.top && S.counties.top.length) {
        var krow = S.counties.top.map(function (k) { return '<tr><th scope="row">' + esc(k.name) + '</th><td class="tl-n">' + esc(num(k.total)) + "</td><td>" + esc(k.lead || "") + "</td><td>" + esc(k.done ? T("every precinct in") : T("still counting")) + "</td></tr>"; }).join("");
        more += '<div class="tl-scroll"><table class="tl-table"><caption>' + esc(T("The {n} counties with the most votes cast", {n: num(S.counties.top.length)})) + '</caption><thead><tr><th scope="col">' + esc(T("County")) + '</th><th scope="col">' + esc(T("Votes")) + '</th><th scope="col">' + esc(T("Most votes")) + '</th><th scope="col">' + esc(T("Reporting")) + "</th></tr></thead><tbody>" + krow + "</tbody></table></div>";
      }
      more += "<p>" + esc(final ? T("Certified: the official result.") : T("As reported, not final: the figures can change until the state certifies them.")) + "</p>";
      var src = S.source && S.source.page ? ext(S.source.page, esc(S.source.label || office || T("The election office’s results"))) : "";
      var nightHref = ""; try { nightHref = L && L.night ? (L.night() || "") : ""; } catch (e) { nightHref = ""; }
      var stampW = whenW(C.at) || dayW(C.at);
      countEv = add({id: "count", kind: "count", iso: C.at, key: localKey(C.at), label: final ? T("The count, certified") : T("The count, latest reading"),
        tag: final ? T("Official count") : T("As reported, not final"), tagk: final ? "official" : "reported", head: head, text: text, more: more,
        links: [nb("count", "The count", "count"), nb("counties", "County by county", "count"), F ? nb("forecast", "Against the forecast", "count") : "", src,
          nightHref ? '<a class="tl-fl" href="' + esc(nightHref) + '">' + esc(T("This race on Election Night")) + "</a>" : ""],
        ro: "<strong>" + (final ? E("The count, certified by {office}, {when}.", {office: office || T("the election office"), when: stampW}) : E("The count, as reported by {office}, {when}, not final.", {office: office || T("the election office"), when: stampW})) + "</strong> " + head + ". " +
          (rep ? E("{a} of {b} precincts reporting. ", {a: num(rep[0]), b: num(rep[1])}) : "") + (vs ? E("{name}’s share is {vs}.", {name: subj, vs: vs}) : ""),
        sr: final ? T("The count, certified: {head}.", {head: head.replace(/<[^>]+>/g, "")}) : T("The count, as reported, not final: {head}.", {head: head.replace(/<[^>]+>/g, "")})});
    }

    /* ---- the coverage: calls, statements, stories (links only) */
    calls.forEach(function (c, i) {
      var eid = "call-" + (i + 1), by = c.by && c.by !== c.o ? E(", as reported by {by}", {by: c.by}) : "";
      var head = E("{outlet} called it for {name}", {outlet: c.o, name: c.n || ""});
      add({id: eid, kind: "call", iso: isDate(c.t) ? c.t : "", key: localKey(c.t), label: T("A call"), tag: T("Links only"), tagk: "links", head: head,
        text: E("A call is a news organization’s judgment{by}. The Civic Archive does not call races; the result is final when the state certifies it.", {by: by}),
        more: "", links: [ext(c.u, E("The report at {outlet}", {outlet: c.o})), nb("coverage/calls", "Who called it", eid), nb("method/calls", "Why this site never calls a race", eid)],
        ro: "<strong>" + esc(T("A call.")) + "</strong> " + head + by + ". " + esc(T("The Civic Archive does not call races.")),
        sr: T("{outlet} called it for {name}. The Civic Archive does not call races.", {outlet: c.o, name: c.n || ""})});
    });
    said.forEach(function (s, j) {
      var x = s.x, eid = "said-" + slug(s.n) + "-" + (j + 1), k = T(KIND[x.k] || "Statement"), med = T(MEDIUM[x.m] || "in text");
      var via = x.by || T("the link");
      add({id: eid, kind: "said", iso: isDate(x.d) ? x.d : "", key: localKey(x.d), label: k, tag: T("Links only"), tagk: "links",
        head: E("{name}: {kind}, {medium}", {name: s.n, kind: k.toLowerCase(), medium: med}),
        text: T("Their own words, behind the link; nothing is copied here."), more: "",
        links: [ext(x.u, esc(via)), nb("coverage/said", "What the candidates said", eid)],
        ro: "<strong>" + esc(k) + ".</strong> " + E("{name}, {medium}, via {via}.", {name: s.n, medium: med, via: via}),
        sr: T("{name}: {kind}, via {via}.", {name: s.n, kind: k.toLowerCase(), via: via})});
    });
    news.forEach(function (s, j) {
      /* the headline is the link to the story itself; it is the outlet's own words, and nothing more is copied */
      var x = s.x, eid = "news-" + (j + 1), tier = T(TIER[s.tier] || "News"), hl = x.u ? ext(x.u, esc(x.h)) : esc(x.h);
      add({id: eid, kind: "news", iso: isDate(x.t) ? x.t : "", key: localKey(x.t), label: tier, tag: T("Links only"), tagk: "links",
        head: hl, text: E("{outlet}. The headline is the outlet’s own; nothing more is copied.", {outlet: x.o || ""}), more: "",
        links: [nb("coverage/news", "News coverage", eid)],
        ro: "<strong>" + esc(tier) + ".</strong> " + E("{outlet}: ", {outlet: x.o || ""}) + "“" + hl + "”",
        sr: T("{tier}, {outlet}: {h}", {tier: tier, outlet: x.o || "", h: x.h}), tip: T("{tier}, {outlet}", {tier: tier, outlet: x.o || ""})});
    });

    /* ---- still to come: no dates, because the record has none */
    var NEXT = [];
    if (!(C && C.final)) {
      if (!C) NEXT.push(["next-count", "The count", "The election office reports the count as it goes; this site shows it as reported, not final."]);
      NEXT.push(["next-canvass", "The canvass", "Each local election board checks its count, adds the ballots that could not be counted on the night, and approves its results."]);
      NEXT.push(["next-certify", "Certification", "The state certifies the result. This site marks figures “as certified” only then."]);
      if (C) NEXT.push(["next-recount", "A recount or a challenge, if there is one", "A close race can be recounted under state law, and candidates can go to court. A concession is a custom, not a legal step: it ends no count."]);
    }
    NEXT.forEach(function (n) {
      add({id: n[0], kind: "next", iso: "", key: "", label: T("Still to come"), tag: T("How it works"), tagk: "how", head: T(n[1]), text: T(n[2]), more: "",
        links: [nb("method/labels", "What the labels mean", n[0])], ro: "", sr: T(n[1])});
    });

    /* ---- order: the undated start, then by the state's own calendar day (Election Day first in its day, then timed events, then those with no time), then the steps to come */
    var KO = {eday: 0, poll: 1, fc: 1, count: 2, call: 3, said: 4, news: 5};
    var rank = function (e) { return e.kind === "eday" ? 0 : hasTime(e.iso) ? 1 : 2; };
    var START = {list: 1, primary: 1};
    var start = EV.filter(function (e) { return !e.key && START[e.kind]; });
    var undated = EV.filter(function (e) { return !e.key && !START[e.kind] && e.kind !== "next"; });   /* a poll, call, statement or story the record leaves undated */
    var next = EV.filter(function (e) { return e.kind === "next"; });
    var dated = EV.filter(function (e) { return !!e.key; });
    dated.forEach(function (e, i) { e.i0 = i; });
    dated.sort(function (a, b) {
      return a.key < b.key ? -1 : a.key > b.key ? 1 : (rank(a) - rank(b)) || (rawPos(a.iso) - rawPos(b.iso)) || ((KO[a.kind] || 9) - (KO[b.kind] || 9)) || (a.i0 - b.i0);
    });
    var prev = -Infinity;
    dated.forEach(function (e) { var p = rawPos(e.iso); if (!(p > prev)) p = prev + 1000; e.pos = p; prev = p; });

    /* the line's ends: the count's reading, or the day the figures were read (what is dated later is still ahead) */
    var readPos = rawPos(READ), TC, T0;
    if (C) TC = Math.max.apply(null, dated.map(function (e) { return e.pos; }));
    else {
      var past = dated.filter(function (e) { return e.key <= READ; });
      TC = Math.max.apply(null, [readPos].concat(past.map(function (e) { return e.pos; })));
    }
    var firstPos = dated.length ? Math.min.apply(null, dated.map(function (e) { return e.pos; })) : TC - DAY;
    T0 = Math.min(firstPos, TC - DAY);
    if (!(T0 < TC)) T0 = TC - DAY;
    dated.forEach(function (e) { e.ahead = e.pos > TC; });
    var edPos = ED ? (dated.filter(function (e) { return e.kind === "eday"; })[0] || {pos: rawPos(ED)}).pos : NaN;
    /* the read day as a mark on the line when nothing has been counted */
    var todayEv = null;
    if (!C) {
      todayEv = {id: "today", kind: "today", iso: READ, key: READ, pos: TC, label: T("As of"), head: E("As of {date}, the day these figures were read", {date: longDay(READ)}), text: "", more: "", links: [], ro: "", sr: T("As of {date}.", {date: dayW(READ)})};
      dated.push(todayEv);
      dated.sort(function (a, b) { return a.pos - b.pos || ((a.kind === "today") - (b.kind === "today")); });
    }
    var order = start.concat(dated, undated, next);

    /* ---- the days, in order */
    var days = [];
    order.forEach(function (e) {
      var k = e.key ? e.key : (e.kind === "next" ? "next" : START[e.kind] ? "start" : "undated");
      if (!days.length || days[days.length - 1].k !== k) days.push({k: k, key: e.key, ev: []});
      days[days.length - 1].ev.push(e);
    });
    runs.forEach(function (r) { var e = dated.filter(function (x) { return x.id === r.id; })[0]; r.pos = e ? e.pos : rawPos(r.at); });

    return {S: S, L: L, kind: kind, seats: seats, partisan: partisan, ED: ED, READ: READ, C: C, F: F, P: P, calls: calls, said: said, news: news, lead: lead, second: second, tops: tops,
      subj: subj, subjTop: subjTop, other: other, cs: cs, track: track, runs: runs, lastRun: lastRun, ahead: ahead, countEv: countEv, todayEv: todayEv,
      EV: order, dated: dated, days: days, T0: T0, TC: TC, edPos: edPos, office: office, nb: nb, full: full, sw: sw, nameP: nameP, has: has};
  }

  function getModel(S, L) {
    var M = cache ? cache.get(S) : null;
    if (!M) { M = model(S, L); if (cache) cache.set(S, M); }
    return M;
  }

  /* ---------- the chart (viewBox 640 by 280 with a forecast, 640 by 120 without) ---------- */
  var f1 = function (v) { return (Math.round(v * 10) / 10).toString(); };
  function chart(M) {
    var runs = M.runs, hasRuns = runs.length > 0;
    var W = 640, HG = hasRuns ? 280 : 120, X0 = 46, X1 = 626, Y0 = 18, Y1 = hasRuns ? 234 : 74;
    var XA = M.T0 - DAY, XB = (M.C ? M.TC : Math.max(M.TC, isNaN(M.edPos) ? M.TC : M.edPos)) + DAY;
    if (!(XB > XA)) XB = XA + DAY;
    var X = function (t) { return X0 + (t - XA) / (XB - XA) * (X1 - X0); };
    var cs = M.cs;
    var ymin = 0, ymax = 100, Y = function (v) { return Y1 - (v - ymin) / (ymax - ymin) * (Y1 - Y0); };
    var body = "", yticks = "", title, desc;
    if (hasRuns) {
      var lows = runs.map(function (r) { return r.l; }), highs = runs.map(function (r) { return r.h; });
      if (cs) { lows.push(cs.share); highs.push(cs.share); }
      ymin = Math.floor((Math.min.apply(null, lows) - 1) / 5) * 5;
      ymax = Math.ceil((Math.max.apply(null, highs) + 1) / 5) * 5;
      if (ymin < 0) ymin = 0;
      if (ymax > 100) ymax = 100;
      if (ymax - ymin < 10) ymax = ymin + 10;
      var endX = X(isNaN(M.edPos) ? M.TC : Math.min(M.edPos, M.TC));
      /* the steps: each run's figures hold until the next run; the last holds to Election Day (or to the read day before one) */
      var xs = runs.map(function (r) { return X(r.pos); }).concat([Math.max(endX, X(runs[runs.length - 1].pos))]);
      var steps = function (vals) {
        var pts = [[xs[0], Y(vals[0])]], i;
        for (i = 1; i < vals.length; i++) pts.push([xs[i], Y(vals[i - 1])], [xs[i], Y(vals[i])]);
        pts.push([xs[vals.length], Y(vals[vals.length - 1])]);
        return pts;
      };
      var P = function (pts) { return pts.map(function (p) { return f1(p[0]) + "," + f1(p[1]); }).join(" L"); };
      var top = steps(highs.slice(0, runs.length)), bot = steps(lows.slice(0, runs.length));
      var band = "M" + P(top) + " L" + P(bot.slice().reverse()) + " Z", mid = "M" + P(steps(runs.map(function (r) { return r.md; })));
      var dots = runs.map(function (r) {
        return '<circle class="tl-dot" data-t="' + r.pos + '" cx="' + f1(X(r.pos)) + '" cy="' + f1(Y(r.md)) + '" r="4.5"><title>' + esc(T("Run {i}: middle {md}, likely {l} to {h}", {i: num(r.i), md: pct(r.md), l: pct(r.l), h: pct(r.h)})) + "</title></circle>";
      }).join("");
      var v;
      for (v = ymin; v <= ymax; v += 5) yticks += '<g class="tl-yt' + (v === 50 ? " is-half" : "") + '"><line x1="' + X0 + '" x2="' + X1 + '" y1="' + f1(Y(v)) + '" y2="' + f1(Y(v)) + '"/><text x="' + (X0 - 8) + '" y="' + f1(Y(v) + 4) + '">' + v + "%</text></g>";
      body += '<g clip-path="url(#vwtl-clip)"><path class="tl-band" d="' + band + '"/><path class="tl-mid" d="' + mid + '"/>';
      if (cs && M.countEv) {
        var cx = X(M.countEv.pos), cy = Y(cs.share), edx = isNaN(M.edPos) ? cx : X(M.edPos);
        body += '<line class="tl-cref" x1="' + X0 + '" x2="' + f1(edx) + '" y1="' + f1(cy) + '" y2="' + f1(cy) + '"/><line class="tl-cline" x1="' + f1(edx) + '" x2="' + f1(cx) + '" y1="' + f1(cy) + '" y2="' + f1(cy) + '"/>';
        var lr = M.lastRun;
        if (lr && (cs.share > lr.h || cs.share < lr.l)) {
          var hy = Y(cs.share > lr.h ? lr.h : lr.l), over = Math.abs(cs.share - (cs.share > lr.h ? lr.h : lr.l)), mx = edx - 12;
          body += '<g class="tl-miss"><line x1="' + f1(mx) + '" x2="' + f1(mx) + '" y1="' + f1(hy) + '" y2="' + f1(cy) + '"/><line x1="' + f1(mx - 4) + '" x2="' + f1(mx + 4) + '" y1="' + f1(hy) + '" y2="' + f1(hy) + '"/><line x1="' + f1(mx - 4) + '" x2="' + f1(mx + 4) + '" y1="' + f1(cy) + '" y2="' + f1(cy) + '"/><text x="' + f1(mx - 8) + '" y="' + f1((hy + cy) / 2 + 4) + '">' +
            esc(cs.share > lr.h ? T("{d} points above the range", {d: f1(over)}) : T("{d} points below the range", {d: f1(over)})) + "</text></g>";
        }
        body += '</g><g class="tl-dots">' + dots + '</g><g class="tl-cdot" data-t="' + M.countEv.pos + '"><circle cx="' + f1(cx) + '" cy="' + f1(cy) + '" r="5.5"/><text x="' + f1(edx + 7) + '" y="' + f1(cy + 17) + '">' + esc(T("The count {share}", {share: pct(cs.share)})) + "</text></g>";
      } else body += '</g><g class="tl-dots">' + dots + "</g>";
      title = T("The forecast for {name}, run by run{count}", {name: M.subj, count: cs ? T(", and the count") : ""});
      desc = T("Middle and 80-in-100 range from {n} runs, {a} to {b} at the middle{count}.", {n: num(runs.length), a: pct(runs[0].md), b: pct(runs[runs.length - 1].md), count: cs ? T("; the count as reported, {share}", {share: pct(cs.share)}) : ""});
    } else {
      /* no forecast: the events alone on a line */
      var ticks = M.dated.filter(function (e) { return e.kind !== "today"; }).map(function (e) {
        return '<circle class="tl-tick" data-kind="' + e.kind + '" data-t="' + e.pos + '" cx="' + f1(X(e.pos)) + '" cy="' + Y1 + '" r="' + (e.kind === "count" ? 6 : 4.5) + '"><title>' + esc(e.tip || e.sr) + "</title></circle>";
      }).join("");
      body += '<g class="tl-ticks">' + ticks + "</g>";
      title = T("The events on one line");
      desc = T("{n} dated events, from {a} to {b}.", {n: num(M.dated.length), a: dayW(M.dated.length ? M.dated[0].key : M.READ), b: dayW(M.dated.length ? M.dated[M.dated.length - 1].key : M.READ)});
    }
    /* x ticks: the first day and the last (the count's reading, or the day the figures were read) first, then each first of a
       month where there is room; Election Day is named above the line. A label is about 9 units a letter on a phone */
    var xt = [], seenK = {};
    var pushT = function (t, label) {
      var x = X(t), w = 9 * String(label).length;
      if (x < X0 - 1 || x > X1 + 1) return;
      if (xt.some(function (q) { return Math.abs(q[0] - x) < (w + q[2]) / 2 + 6; })) return;
      xt.push([x, label, w]);
    };
    if (M.dated.length) pushT(M.dated[0].pos, dayW(M.dated[0].key));
    pushT(M.TC, dayW(M.C ? M.countEv.key : M.READ));
    var d = keyOf(XA), stop = keyOf(XB);
    while (d <= stop) { if (d.slice(8) === "01" && !seenK[d]) { seenK[d] = 1; pushT(utcOf(d) + DAY / 2, dayW(d)); } d = shift(d, 1); }
    xt.sort(function (a, b) { return a[0] - b[0]; });
    var xticks = xt.map(function (q) { return '<text class="tl-xt" x="' + f1(q[0]) + '" y="' + (Y1 + 30) + '">' + esc(q[1]) + "</text>"; }).join("");
    var ed = "";
    if (!isNaN(M.edPos)) ed = '<g class="tl-ed' + (M.ahead ? " is-ahead" : "") + '"><line x1="' + f1(X(M.edPos)) + '" x2="' + f1(X(M.edPos)) + '" y1="' + (Y0 - 6) + '" y2="' + Y1 + '"/><text x="' + f1(X(M.edPos)) + '" y="' + (Y0 - 9) + '">' + esc(T("Election Day")) + "</text></g>";
    var nowx = X(M.TC);
    return {X: X, X0: X0, X1: X1, W: W, XA: XA, XB: XB, html:
      '<svg class="tl-svg" viewBox="0 0 ' + W + " " + HG + '" role="img" aria-labelledby="vwtl-svg-t vwtl-svg-d" focusable="false">' +
      '<title id="vwtl-svg-t">' + esc(title) + '</title><desc id="vwtl-svg-d">' + esc(desc) + "</desc>" +
      '<defs><clipPath id="vwtl-clip"><rect id="vwtl-cliprect" x="' + X0 + '" y="0" width="' + f1(nowx - X0) + '" height="' + HG + '"/></clipPath></defs>' +
      '<g class="tl-grid">' + yticks + "</g>" + ed + body +
      '<g class="tl-xa"><line x1="' + X0 + '" x2="' + X1 + '" y1="' + Y1 + '" y2="' + Y1 + '"/>' + xticks + "</g>" +
      '<line class="tl-ghost is-off" x1="' + X0 + '" x2="' + X0 + '" y1="' + Y0 + '" y2="' + Y1 + '"/>' +
      '<g class="tl-nowm"><line x1="' + f1(nowx) + '" x2="' + f1(nowx) + '" y1="' + (Y0 - 4) + '" y2="' + (Y1 + 4) + '"/><path d="M' + f1(nowx - 6) + "," + (Y1 + 12) + " L" + f1(nowx + 6) + "," + (Y1 + 12) + " L" + f1(nowx) + "," + (Y1 + 4) + ' Z"/></g></svg>'};
  }

  /* ---------- the page ---------- */
  function tagHtml(e) { return e.tag ? '<span class="tl-tag" data-k="' + esc(e.tagk) + '">' + esc(e.tag) + "</span>" : ""; }

  function eventHtml(M, e) {
    var id = "vwtl-" + e.id, whenH;
    if (e.kind === "next" || e.kind === "list" || e.kind === "primary" || !e.key) whenH = '<p class="tl-at tl-nodate">' + esc(T("no date in the record")) + "</p>";
    else if (e.kind === "today") whenH = '<p class="tl-at tl-nodate">' + esc(T("today")) + "</p>";
    else {
      var tw = e.kind === "eday" ? T("all day") : (hasTime(e.iso) ? timeW(e.iso).replace(/\s+ET$/, "") : T("time not given"));
      whenH = '<button type="button" class="tl-at" aria-describedby="' + id + '-h"><time datetime="' + esc(e.iso) + '">' + esc(tw) + '</time><span class="tl-sr"> ' + esc(e.kind === "eday" ? T("Set the chart to Election Day") : T("Set the chart to this moment")) + "</span></button>";
    }
    if (e.kind === "today") return '<li class="tl-ev tl-today" id="' + id + '" data-kind="today" data-t="' + e.pos + '">' + whenH + '<p class="tl-tdy">' + e.head + "</p></li>";
    var links = e.links.filter(Boolean).map(function (a) { return '<span class="tl-l">' + a + "</span>"; }).join(" ");
    var more = e.more ? '<div class="tl-more" id="' + id + '-m" hidden>' + e.more + "</div>" : "";
    var headIn = e.more ? '<button type="button" class="tl-x" aria-expanded="false" aria-controls="' + id + '-m"><span class="tl-xc" aria-hidden="true"></span>' + e.head + "</button>" : e.head;
    return '<li class="tl-ev" id="' + id + '" data-kind="' + e.kind + '"' + (e.pos ? ' data-t="' + e.pos + '"' : "") + (e.ahead ? ' data-when="ahead"' : "") + ">" + whenH +
      '<div class="tl-card"><p class="tl-k"><span class="tl-lab">' + esc(e.label) + "</span>" + tagHtml(e) + "</p>" +
      '<h4 class="tl-h" id="' + id + '-h">' + headIn + "</h4>" + (e.text ? '<p class="tl-p">' + e.text + "</p>" : "") + more + (links ? '<p class="tl-links">' + links + "</p>" : "") + "</div></li>";
  }

  function render(S, L) {
    var M = getModel(S, L), C = M.C, F = M.F, P = M.P;
    var parts = [T("the official list")];
    if (S.primaries) parts.push(T("the primaries"));
    if (P) parts.push((P.n || 0) > P.newest.length ? T("the {k} newest of {n} polls", {k: num(P.newest.length), n: num(P.n)}) : one(P.newest.length, "one poll", "{n} polls"));
    if (M.runs.length) parts.push(one(M.runs.length, "one forecast run", "{n} forecast runs"));
    if (M.ED) parts.push(T("Election Day"));
    if (C) parts.push(C.final ? T("the certified count") : T("the count as it stands"));
    if (M.calls.length) parts.push(one(M.calls.length, "one call by a news organization", "{n} calls by news organizations"));
    if (M.said.length) parts.push(one(M.said.length, "one statement by a candidate", "{n} statements by the candidates"));
    if (M.news.length) parts.push(one(M.news.length, "one news story", "{n} news stories"));
    if (!(C && C.final)) parts.push(M.ahead ? T("what is still ahead") : T("the steps still to come before the result is final"));
    var lede = E("{title}. In the order it happened: {parts}. Each step opens in place; its detail is in the notebook.", {title: S.title || S.office || "", parts: parts.join(", ")});

    /* where it stands: up to three tiles, from what there is */
    var tiles = [];
    if (C) {
      var rep = C.reporting && C.reporting.length === 2 ? C.reporting : null, rows;
      if (M.kind === "retention") rows = C.cands.map(function (c, i) { return '<p class="tl-tv' + (i ? " tl-tv2" : "") + '">' + esc(c.n) + " <b>" + esc(pct(c.share)) + "</b></p>"; }).join("");
      else rows = C.cands.slice(0, Math.max(2, M.seats)).map(function (c, i) { return '<p class="tl-tv' + (i >= M.seats ? " tl-tv2" : "") + '">' + M.sw(c.code) + esc(c.n) + " <b>" + esc(pct(c.share)) + "</b></p>"; }).join("");
      tiles.push('<article class="tl-tile"><p class="tl-tk"><span class="tl-tag" data-k="' + (C.final ? "official" : "reported") + '">' + esc(C.final ? T("Official count") : T("As reported, not final")) + "</span></p>" + rows +
        '<p class="tl-ts">' + (rep ? E("{a} of {b} precincts, ", {a: num(rep[0]), b: num(rep[1])}) : "") + E("read {when}.", {when: whenW(C.at) || dayW(C.at)}) + (M.seats > 1 ? " " + E("The {seats} with the most votes take the seats.", {seats: num(M.seats)}) : "") + " " + M.nb("count", "The count", "count") + "</p></article>");
    } else if (M.ED) {
      tiles.push('<article class="tl-tile"><p class="tl-tk"><span class="tl-tag" data-k="how">' + esc(T("Election Day")) + '</span></p><p class="tl-tv">' + esc(longDay(M.ED)) + '</p><p class="tl-ts">' +
        esc(M.ahead ? T("Still ahead. The count will show here as the election office reports it.") : T("No reading of the count is on record here yet.")) + "</p></article>");
    }
    if (F && M.subjTop) {
      var fw = M.subjTop;
      tiles.push('<article class="tl-tile"><p class="tl-tk"><span class="tl-tag" data-k="analysis">' + esc(T("Analysis")) + '</span></p><p class="tl-tv">' + esc(T("The last forecast:")) + " <b>" + esc(pct(fw.md)) + '</b></p><p class="tl-ts">' +
        E("for {name}, likely {l} to {h}; chance of the most votes {ch}.", {name: M.subj, l: pct(fw.l80), h: pct(fw.h80), ch: chance(fw.ch)}) + (M.track ? " " + esc(M.track) : "") + " " + M.nb("forecast", "The forecast, worked out", "fc-" + M.runs.length) + "</p></article>");
    } else {
      var lh = M.kind === "retention" ? T("A yes-or-no vote") : M.kind === "unopposed" ? T("Unopposed") : M.kind === "none" ? T("No candidate listed") : (M.seats > 1 ? T("{k} names, {seats} seats", {k: num((S.list || []).length), seats: num(M.seats)}) : one((S.list || []).length, "One name on the ballot", "{n} names on the ballot"));
      tiles.push('<article class="tl-tile"><p class="tl-tk"><span class="tl-tag" data-k="official">' + esc(T("Official record")) + '</span></p><p class="tl-tv">' + esc(lh) + '</p><p class="tl-ts">' +
        (S.list_source && S.list_source.agency ? E("From {agency}.", {agency: S.list_source.agency}) : "") + " " + M.nb("list", "Who is on the ballot", "list") + "</p></article>");
    }
    if (M.calls.length) {
      var first = M.calls.slice().sort(function (a, b) { return rawPos(a.t) - rawPos(b.t); })[0];
      tiles.push('<article class="tl-tile"><p class="tl-tk"><span class="tl-tag" data-k="links">' + esc(T("Links only")) + '</span></p><p class="tl-tv">' + E("Called by <b>{n}</b> news organizations", {n: num(M.calls.length)}) + '</p><p class="tl-ts">' +
        esc(joinNames(M.calls.map(function (c) { return c.o; }))) + (first && isDate(first.t) ? E(", the first {when}", {when: whenW(first.t) || dayW(first.t)}) : "") + ". " + esc(T("The Civic Archive does not call races.")) + " " + M.nb("coverage/calls", "Who called it", "call-1") + "</p></article>");
    } else if (P) {
      tiles.push('<article class="tl-tile"><p class="tl-tk"><span class="tl-tag" data-k="poll">' + esc(T("Opinion when taken")) + '</span></p><p class="tl-tv">' + one(P.n || P.newest.length, "One poll counted", "{n} polls counted") + '</p><p class="tl-ts">' +
        esc(T("We count only polls from members of the American Association for Public Opinion Research’s Transparency Initiative.")) + (P.other ? " " + esc(one(P.other, "One other is shown apart.", "{n} others are shown apart.")) : "") + " " + M.nb("polls", "The polls", "poll-1") + "</p></article>");
    }

    var ch = chart(M);
    var legend = M.runs.length ? '<p class="tl-legend"><span><i class="tl-lg tl-lg-band"></i>' + esc(T("80 in 100 range")) + '</span><span><i class="tl-lg tl-lg-mid"></i>' + esc(T("Middle")) + "</span>" +
      (M.cs ? '<span><i class="tl-lg tl-lg-count"></i>' + esc(T("The count")) + "</span>" : "") + '<span><i class="tl-lg tl-lg-now"></i>' + esc(T("Now marker")) + "</span></p>"
      : '<p class="tl-legend"><span><i class="tl-lg tl-lg-dot"></i>' + esc(T("An event")) + '</span><span><i class="tl-lg tl-lg-now"></i>' + esc(T("Now marker")) + "</span></p>";
    var chartH = M.runs.length ? (M.cs ? T("Expectation meets result") : T("What the forecast expected")) : T("On one line");
    var chartP = M.runs.length ? (M.cs ? E("The forecast’s middle and 80-in-100 range for {name}, run by run, and then the count. Move the marker to watch one meet the other.", {name: M.subj})
      : E("The forecast’s middle and 80-in-100 range for {name}, run by run, up to the day these figures were read. Analysis, never a result.", {name: M.subj}))
      : T("Every dated step on one line. Move the marker to read the story to that moment.");
    var KINDS = [["poll", "Polls"], ["fc", "Forecast"], ["count", "Count"], ["call", "Calls"], ["said", "Statements"], ["news", "News"], ["next", "Still to come"]];
    var present = {};
    M.EV.forEach(function (e) { present[e.kind] = 1; });
    var chips = KINDS.filter(function (k) { return present[k[0]]; }).map(function (k) {
      return '<button type="button" class="tl-chip" data-f="' + k[0] + '" aria-pressed="true"><i class="tl-ck" data-kind="' + k[0] + '"></i>' + esc(T(k[1])) + "</button>";
    }).join("");
    var dayHtml = M.days.map(function (d) {
      var hd, lab;
      if (d.k === "start") { lab = T("At the start"); hd = '<h3 class="tl-dh"><span class="tl-dn">' + esc(lab) + '</span><span class="tl-dr">' + esc(T("no dates: the record gives none")) + "</span></h3>"; }
      else if (d.k === "undated") { lab = T("Date not in the record"); hd = '<h3 class="tl-dh"><span class="tl-dn">' + esc(lab) + "</span></h3>"; }
      else if (d.k === "next") { lab = T("Still to come"); hd = '<h3 class="tl-dh"><span class="tl-dn">' + esc(lab) + '</span><span class="tl-dr">' + esc(T("no dates: the record has none yet")) + "</span></h3>"; }
      else { lab = longDay(d.key); hd = '<h3 class="tl-dh"><span class="tl-dn">' + esc(lab) + "</span>" + (M.ED ? '<span class="tl-dr">' + esc(rel(d.key, M.ED)) + "</span>" : "") + "</h3>"; }
      return '<section class="tl-day' + (d.k === "next" ? " is-next" : "") + (d.key && d.key === M.ED ? " is-eday" : "") + '" data-day="' + esc(d.k) + '" aria-label="' + esc(lab) + '">' + hd + '<ol class="tl-list">' + d.ev.map(function (e) { return eventHtml(M, e); }).join("") + "</ol></section>";
    }).join("");
    var foot = E("Figures as read from this site’s own pages on {date}.", {date: dayW(M.READ)}) + " " +
      (C ? (C.final ? E("The count comes from {office}, certified.", {office: M.office || T("the election office")}) : E("The count comes from {office}, as reported {when}, not final.", {office: M.office || T("the election office"), when: whenW(C.at) || dayW(C.at)})) + " " : "") +
      (F ? esc(T("Forecasts are this site’s own analysis and never say 0 or 100 percent.")) + " " : "") +
      (M.calls.length ? esc(T("Calls are news organizations’ judgments; The Civic Archive does not call races.")) + " " : "") +
      [M.nb("sources", "Where the facts come from", "foot"), M.nb("method/labels", "What the labels mean", "foot")].filter(Boolean).join(" &middot; ");

    return '<div class="tl" data-tl>' +
      '<header class="tl-head"><h2 class="tl-t" id="vwtl-t">' + esc(T("The story so far")) + '</h2><p class="tl-lede">' + lede + "</p></header>" +
      '<section class="tl-stand" aria-labelledby="vwtl-stand-h"><h3 id="vwtl-stand-h" class="tl-sr">' + esc(T("Where it stands")) + '</h3><div class="tl-tiles">' + tiles.join("") + "</div></section>" +
      '<div class="tl-grid">' +
      '<section class="tl-panel" aria-labelledby="vwtl-chart-h"><h3 id="vwtl-chart-h">' + esc(chartH) + '</h3><p class="tl-ph">' + chartP + "</p>" +
      '<div class="tl-chart" id="vwtl-chart">' + ch.html + "</div>" + legend +
      '<div class="tl-ctl"><label class="tl-rl" for="vwtl-range">' + esc(T("Move through the story")) + ' <span class="tl-rh">' + esc(T("(left and right arrows step between events)")) + "</span></label>" +
      '<input type="range" id="vwtl-range" min="0" max="1000" value="1000" step="1" aria-valuetext="">' +
      '<div class="tl-btns"><button type="button" class="tl-b" id="vwtl-prev">&larr; ' + esc(T("Earlier")) + "</button>" +
      '<button type="button" class="tl-b tl-play" id="vwtl-play" aria-pressed="false" hidden>&#9654; ' + esc(T("Play the story")) + "</button>" +
      '<button type="button" class="tl-b" id="vwtl-next">' + esc(T("Later")) + " &rarr;</button></div></div>" +
      '<div class="tl-ro" id="vwtl-ro"><p class="tl-ro-when" id="vwtl-ro-when"></p><div class="tl-ro-body" id="vwtl-ro-body"></div></div>' +
      '<p class="tl-sr" aria-live="polite" id="vwtl-live"></p>' +
      (chips ? '<div class="tl-filters"><p class="tl-fh" id="vwtl-fh">' + esc(T("Show")) + '</p><div class="tl-chips" role="group" aria-labelledby="vwtl-fh">' + chips + '</div><p class="tl-fn">' + esc(T("The list and Election Day always show.")) + ' <span id="vwtl-fcount"></span></p></div>' : "") +
      "</section>" +
      '<section class="tl-story" aria-labelledby="vwtl-story-h"><h3 id="vwtl-story-h">' + esc(T("In the order it happened")) + '</h3><p class="tl-sh">' + esc(T("Tap a time to set the chart to that moment; up and down arrows move between events. A heading opens its step in place.")) + "</p>" +
      '<div class="tl-days" id="vwtl-days">' + dayHtml + "</div></section></div>" +
      '<footer class="tl-foot"><p class="tl-small">' + foot + "</p></footer></div>";
  }

  /* ---------- behaviour ---------- */
  function wire(root, S, L) {
    var M = getModel(S, L);
    var $ = function (s, el) { return (el || root).querySelector(s); }, $$ = function (s, el) { return Array.prototype.slice.call((el || root).querySelectorAll(s)); };
    var range = $("#vwtl-range"), chartEl = $("#vwtl-chart"), svg = $(".tl-svg"), clip = $("#vwtl-cliprect"), nowm = $(".tl-nowm", svg), ghost = $(".tl-ghost", svg);
    var whenEl = $("#vwtl-ro-when"), bodyEl = $("#vwtl-ro-body"), live = $("#vwtl-live"), prev = $("#vwtl-prev"), next = $("#vwtl-next"), play = $("#vwtl-play"), daysEl = $("#vwtl-days");
    if (!range || !svg || !daysEl) return function () {};
    var ch = chart(M);
    var X = ch.X;
    var evs = $$(".tl-ev"), byId = {};
    evs.forEach(function (el) { byId[el.id] = el; });
    var RO = {};
    M.EV.forEach(function (e) { RO[e.id] = e; });
    var timed = M.dated.filter(function (e) { return e.kind !== "today" && !e.ahead; }).slice().sort(function (a, b) { return a.pos - b.pos; });
    var now = M.TC, current = null, liveTimer = 0, playing = 0, dragging = false, winL = [];
    var clamp = function (t) { return Math.max(M.T0, Math.min(M.TC, t)); };
    var motion = function () { try { return !V.calm(); } catch (e) { return false; } };
    if (play && motion() && timed.length) play.hidden = false;

    var latest = function (t) { var k = null, i; for (i = 0; i < timed.length; i++) { if (timed[i].pos <= t) k = timed[i]; else break; } return k; };
    var latestRun = function (t) { var k = null, i; for (i = 0; i < M.runs.length; i++) { if (M.runs[i].pos <= t) k = M.runs[i]; else break; } return k; };
    var visible = function () { return timed.filter(function (e) { var el = byId["vwtl-" + e.id]; return el && !el.hidden; }); };

    function dayAt(t, shown) {
      /* the marker's calendar day: the shown event's own when the marker sits on it, else the day the line's position falls in */
      if (shown && Math.abs(shown.pos - t) < 1000) return shown.key;
      if (M.todayEv && Math.abs(M.todayEv.pos - t) < 1000) return M.READ;
      return localKey(new Date(t).toISOString()) || M.READ;
    }
    function stampOf(t, shown) {
      /* the day and time of the marker: the shown event's own words when the marker sits on it, else the day alone */
      if (shown && Math.abs(shown.pos - t) < 1000) {
        if (shown.kind === "eday") return longDay(shown.key);
        if (!hasTime(shown.iso)) return T("{day}, time not given", {day: longDay(shown.key)});
        return T("{day}, {time}", {day: longDay(shown.key), time: timeW(shown.iso)});
      }
      return longDay(dayAt(t, shown));
    }

    function setNow(t, o) {
      o = o || {};
      now = clamp(t);
      var x = X(now);
      if (clip) clip.setAttribute("width", Math.max(0, x - ch.X0));
      var ln = nowm.querySelector("line"), pa = nowm.querySelector("path");
      ln.setAttribute("x1", x); ln.setAttribute("x2", x);
      pa.setAttribute("transform", "translate(" + (x - X(M.TC)) + ",0)");
      $$(".tl-dot, .tl-cdot, .tl-tick", svg).forEach(function (el) { el.classList.toggle("is-ahead", +el.getAttribute("data-t") > now); });
      var miss = $(".tl-miss", svg), cdot = $(".tl-cdot", svg), cref = $(".tl-cref", svg);
      if (miss && cdot) miss.classList.toggle("is-ahead", +cdot.getAttribute("data-t") > now);
      if (cref) cref.classList.toggle("is-ahead", isNaN(M.edPos) || now < M.edPos);
      var at = latest(now), pick = o.pick ? RO[o.pick] : null;
      var shown = pick && at && pick.pos === at.pos ? pick : at;
      var stamp = stampOf(now, shown), relW = M.ED && shown ? rel(dayAt(now, shown), M.ED) : "";
      whenEl.textContent = stamp + (relW ? " · " + relW : "");
      var html = "";
      if (!shown) html = "<p>" + esc(T("Before the first dated step. Nothing on this line has happened yet.")) + "</p>";
      else {
        html = "<p>" + shown.ro + "</p>";
        var r = latestRun(now);
        if (r && shown.kind !== "fc" && (isNaN(M.edPos) || now < M.edPos)) html += '<p class="tl-stand">' + r.stand + "</p>";
        if (M.countEv && !isNaN(M.edPos) && now >= M.edPos && now < M.countEv.pos && shown.kind !== "count") html += '<p class="tl-stand">' + esc(T("This page keeps one reading of the count, the latest; earlier figures are not kept here.")) + "</p>";
        if (M.countEv && now >= M.countEv.pos && shown.kind !== "count") html += '<p class="tl-stand">' + M.countEv.ro + "</p>";
        if (!M.C && Math.abs(now - M.TC) < 1000) {
          var left = M.ahead ? Math.round((utcOf(M.ED) - utcOf(M.READ)) / DAY) : 0;
          html += '<p class="tl-stand">' + (M.ahead ? (left === 1 ? E("As of {date}. Election Day is tomorrow.", {date: dayW(M.READ)}) : E("As of {date}. Election Day is {n} days away.", {date: dayW(M.READ), n: num(left)})) : E("As of {date}, the day these figures were read.", {date: dayW(M.READ)})) + "</p>";
        }
      }
      bodyEl.innerHTML = html;
      evs.forEach(function (el) {
        var et = el.getAttribute("data-t");
        if (et && el.getAttribute("data-kind") !== "today") el.setAttribute("data-when", +et <= now ? "past" : "ahead");
        if (shown && el.id === "vwtl-" + shown.id) el.setAttribute("aria-current", "true"); else el.removeAttribute("aria-current");
      });
      current = shown ? shown.id : null;
      if (!o.fromRange) range.value = Math.round((now - M.T0) / (M.TC - M.T0) * 1000);
      var srw = stamp + (shown ? ": " + shown.sr : "");
      range.setAttribute("aria-valuetext", srw);
      clearTimeout(liveTimer);
      liveTimer = setTimeout(function () { live.textContent = srw; }, 500);
    }

    function pickEvent(id, o) {
      o = o || {};
      var e = RO[id], el = byId["vwtl-" + id];
      if (!e || !e.pos || e.ahead) return;
      setNow(e.pos, {pick: id});
      if (o.scroll && el) {
        var r = el.getBoundingClientRect(), top = 110;
        if (r.top < top || r.bottom > (root.ownerDocument.defaultView || window).innerHeight) el.scrollIntoView({block: "center", behavior: "auto"});
      }
      if (o.focus && el) { var b = el.querySelector(".tl-at"); if (b && b.focus) b.focus({preventScroll: true}); }
    }

    function step(dir) {
      var list = visible(), k = -1, i;
      if (!list.length) return;
      if (dir > 0) { for (i = 0; i < list.length; i++) if (list[i].pos > now + 1) { k = i; break; } if (k < 0) { setNow(M.TC); return; } }
      else { for (i = list.length - 1; i >= 0; i--) if (list[i].pos < now - 1) { k = i; break; } if (k < 0) { setNow(M.T0); return; } }
      pickEvent(list[k].id);
    }

    function stop() {
      if (playing) { cancelAnimationFrame(playing); playing = 0; }
      if (play) { play.setAttribute("aria-pressed", "false"); play.innerHTML = "&#9654; " + esc(T("Play the story")); }
    }
    function start() {
      if (!motion()) return;
      var from = now >= M.TC - 1 ? M.T0 : now, span = M.TC - M.T0, ms = 12000 * (M.TC - from) / span, t0 = 0;
      play.setAttribute("aria-pressed", "true"); play.innerHTML = "&#10074;&#10074; " + esc(T("Pause"));
      var tick = function (ts) {
        if (!t0) t0 = ts;
        var p = Math.min(1, (ts - t0) / ms);
        setNow(from + p * (M.TC - from));
        if (p < 1) playing = requestAnimationFrame(tick); else { playing = 0; stop(); setNow(M.TC); }
      };
      playing = requestAnimationFrame(tick);
    }

    /* the range: continuous by drag, event by event by the arrow keys */
    var onInput = function () { stop(); setNow(M.T0 + range.value / 1000 * (M.TC - M.T0), {fromRange: true}); };
    var onKey = function (e) {
      var k = e.key;
      if (k === "ArrowRight" || k === "ArrowUp") { e.preventDefault(); stop(); step(1); }
      else if (k === "ArrowLeft" || k === "ArrowDown") { e.preventDefault(); stop(); step(-1); }
      else if (k === "Home") { e.preventDefault(); stop(); setNow(M.T0); }
      else if (k === "End") { e.preventDefault(); stop(); setNow(M.TC); }
    };
    range.addEventListener("input", onInput);
    range.addEventListener("keydown", onKey);
    if (prev) prev.addEventListener("click", function () { stop(); step(-1); });
    if (next) next.addEventListener("click", function () { stop(); step(1); });
    if (play) play.addEventListener("click", function () { if (playing) stop(); else start(); });

    /* drag on the chart itself: listeners on the window, never pointer capture, removed when the drag ends and in cleanup */
    var win = root.ownerDocument.defaultView || window;
    var tAt = function (cx) { var r = svg.getBoundingClientRect(), k = r.width / ch.W; return ch.XA + ((cx - r.left) / k - ch.X0) / (ch.X1 - ch.X0) * (ch.XB - ch.XA); };
    var onMove = function (e) { if (dragging) setNow(tAt(e.clientX)); };
    var onUp = function () { if (!dragging) return; dragging = false; chartEl.classList.remove("is-drag"); unwin(); };
    var winOn = function (n, fn) { win.addEventListener(n, fn); winL.push([n, fn]); };
    var unwin = function () { winL.forEach(function (p) { win.removeEventListener(p[0], p[1]); }); winL = []; };
    var onDown = function (e) {
      if (e.button !== 0) return;
      stop(); dragging = true; chartEl.classList.add("is-drag");
      setNow(tAt(e.clientX));
      winOn("pointermove", onMove); winOn("pointerup", onUp); winOn("pointercancel", onUp);
    };
    chartEl.addEventListener("pointerdown", onDown);

    /* the events: a tap on a time sets the chart; a card too; a heading opens its step in place; up and down arrows move between events */
    var buttons = function () { return $$(".tl-ev:not([hidden]) .tl-at:not(.tl-nodate)"); };
    root.addEventListener("click", function (e) {
      var x = e.target.closest ? e.target.closest(".tl-x") : null;
      if (x && root.contains(x)) {
        var open = x.getAttribute("aria-expanded") === "true", m = $("#" + x.getAttribute("aria-controls"));
        x.setAttribute("aria-expanded", open ? "false" : "true");
        if (m) m.hidden = open;
        return;
      }
      var b = e.target.closest ? e.target.closest(".tl-at") : null;
      if (b && !b.classList.contains("tl-nodate")) { var ev = b.closest(".tl-ev"); if (ev) { stop(); pickEvent(ev.id.replace(/^vwtl-/, ""), {focus: true}); } return; }
      var card = e.target.closest ? e.target.closest(".tl-card") : null;
      if (card && !e.target.closest("a, button, table, .tl-more")) { var ev2 = card.closest(".tl-ev"); if (ev2 && ev2.getAttribute("data-t")) { stop(); pickEvent(ev2.id.replace(/^vwtl-/, "")); } }
    });
    daysEl.addEventListener("keydown", function (e) {
      if (!e.target.classList || !e.target.classList.contains("tl-at")) return;
      var list = buttons(), i = list.indexOf(e.target), j = -1;
      if (e.key === "ArrowDown" || e.key === "ArrowRight") j = Math.min(list.length - 1, i + 1);
      else if (e.key === "ArrowUp" || e.key === "ArrowLeft") j = Math.max(0, i - 1);
      else if (e.key === "Home") j = 0; else if (e.key === "End") j = list.length - 1;
      if (j < 0 || j === i) return;
      e.preventDefault(); stop();
      var ev = list[j].closest(".tl-ev");
      pickEvent(ev.id.replace(/^vwtl-/, ""), {focus: true, scroll: true});
    });

    /* a ghost marker on the chart while an event is under the pointer or has the keyboard's focus */
    var showGhost = function (ev) {
      if (!ev || !ev.getAttribute("data-t") || !ghost) { if (ghost) ghost.classList.add("is-off"); return; }
      var x = X(clamp(+ev.getAttribute("data-t")));
      ghost.setAttribute("x1", x); ghost.setAttribute("x2", x); ghost.classList.remove("is-off");
    };
    daysEl.addEventListener("pointerover", function (e) { showGhost(e.target.closest ? e.target.closest(".tl-ev") : null); });
    daysEl.addEventListener("pointerout", function (e) { var ev = e.target.closest ? e.target.closest(".tl-ev") : null; if (ev && !(e.relatedTarget && ev.contains(e.relatedTarget))) showGhost(null); });
    daysEl.addEventListener("focusin", function (e) { showGhost(e.target.closest ? e.target.closest(".tl-ev") : null); });
    daysEl.addEventListener("focusout", function (e) { if (!(e.relatedTarget && daysEl.contains(e.relatedTarget))) showGhost(null); });

    /* filters: the list and Election Day always show; a day with nothing left to show is hidden */
    var chips = $$(".tl-chip"), fcount = $("#vwtl-fcount");
    function filter() {
      var on = {};
      chips.forEach(function (c) { if (c.getAttribute("aria-pressed") === "true") on[c.getAttribute("data-f")] = 1; });
      var shown = 0, all = 0;
      evs.forEach(function (el) {
        var k = el.getAttribute("data-kind"), always = k === "eday" || k === "list" || k === "primary" || k === "today";
        var ok = always || on[k];
        el.hidden = !ok;
        if (!always) { all++; if (ok) shown++; }
      });
      $$(".tl-day").forEach(function (d) { d.hidden = !d.querySelector(".tl-ev:not([hidden])"); });
      if (fcount) fcount.textContent = all < 2 ? "" : shown === all ? T("Showing all {n} steps.", {n: num(all)}) : T("Showing {k} of {n} steps.", {k: num(shown), n: num(all)});
    }
    chips.forEach(function (c) { c.addEventListener("click", function () { c.setAttribute("aria-pressed", c.getAttribute("aria-pressed") === "true" ? "false" : "true"); filter(); }); });
    if (chips.length) filter();

    setNow(M.TC);
    return function cleanup() {
      stop();
      clearTimeout(liveTimer);
      dragging = false;
      unwin();
    };
  }

  V.add({id: "timeline", label: "The story so far", order: 4, render: render, wire: wire});
})();
