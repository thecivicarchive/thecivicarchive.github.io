/* The Civic Archive: the shell's behaviour (Shell Spec v1.3, sections 0 to 9).
   Reading & access settings and the eight presets; the top bar, its menus (opened by a click, never by hover), the menu
   sheet on phones; Help, a panel that never traps the reader; the five icons' moves; the edge fade; the companion,
   whose dock is fetched only after the page is drawn and never when the companion is off.
   Every setting is kept in this browser only (localStorage, each read and write guarded). Nothing is sent anywhere. */
import { fillIcons } from "./icons.5d0bf73479.js";

const D = document, H = D.documentElement;
const $ = (s, el = D) => el.querySelector(s), $$ = (s, el = D) => [...el.querySelectorAll(s)];
const KEY = "tca.a11y.v1", SKIN = "tca.companion.skin";
const AXES = {
  depth: ["standard", "detailed", "focus"], lang: ["standard", "plain"], face: ["standard", "dyslexia", "hyperlegible"],
  scale: ["100", "115", "130", "150", "200"], space: ["standard", "generous"], contrast: ["standard", "high", "dark"],
  palette: ["standard", "deut", "prot", "trit", "mono"], motion: ["full", "reduced"], calm: ["off", "on"],
  reveal: ["full", "subtle", "off"], companion: ["on", "still", "off"]
};
const DEF = Object.fromEntries(Object.entries(AXES).map(([k, v]) => [k, v[0]]));
/* the eight presets (Shell Spec section 2, with the fade and companion updates of sections 7.2 and 9) */
const PRESETS = {
  adhd: {depth: "detailed", space: "generous", motion: "reduced", reveal: "subtle", companion: "still"},
  focus: {depth: "focus", motion: "reduced", reveal: "subtle", companion: "off"},
  dyslexia: {face: "dyslexia", space: "generous", lang: "plain", scale: "115", reveal: "subtle"},
  lowvision: {face: "hyperlegible", scale: "150", contrast: "high", space: "generous", reveal: "off", companion: "still"},
  colour: {palette: "deut"},
  screenreader: {motion: "reduced", space: "generous", reveal: "off", companion: "off"},
  plain: {lang: "plain"},
  calm: {calm: "on", motion: "reduced", palette: "mono", reveal: "subtle", companion: "still"}
};
const COMPANIONS = [{"id":"penguin","name":"Adélie penguin","latin":"Pygoscelis adeliae","rests":"floor","default":true,"file":"penguin.fc3508c0ff.js"},{"id":"chickadee","name":"Black-capped chickadee","latin":"Poecile atricapillus","rests":"perch","default":false,"file":"chickadee.f33156ba46.js"},{"id":"retriever","name":"Golden retriever","latin":"Canis familiaris","rests":"floor","default":false,"file":"retriever.1a310d8f2a.js"},{"id":"cat","name":"Tabby cat","latin":"Felis catus","rests":"floor","default":false,"file":"cat.455ca7cef4.js"},{"id":"squirrel","name":"Eastern gray squirrel","latin":"Sciurus carolinensis","rests":"floor","default":false,"file":"squirrel.72f0cacf7a.js"},{"id":"chipmunk","name":"Eastern chipmunk","latin":"Tamias striatus","rests":"floor","default":false,"file":"chipmunk.d1037c6838.js"},{"id":"snail","name":"Garden snail","latin":"Cornu aspersum","rests":"floor","default":false,"file":"snail.e7acf3fb32.js"}];      /* written in by the build: each companion, its file and whether it is ready */

const store = {
  get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
  set(k, v) { try { localStorage.setItem(k, v); return true; } catch (e) { return false; } }
};
const media = q => { try { return matchMedia(q); } catch (e) { return {matches: false, addEventListener() {}}; } };
const reducedOS = media("(prefers-reduced-motion: reduce)"), forced = media("(forced-colors: active)"), fine = media("(hover: hover) and (pointer: fine)"), phone = media("(max-width: 700px)");

export function axes() { const o = {}; for (const k in AXES) { const v = H.getAttribute("data-" + k); o[k] = AXES[k].includes(v) ? v : DEF[k]; } return o; }
/* the presets the reader turned on themselves; a preset stays on only while its settings still hold */
const chosen = new Set((() => { try { const s = JSON.parse(store.get(KEY) || "null"); return s && Array.isArray(s.presets) ? s.presets.filter(p => p in PRESETS) : []; } catch (e) { return []; } })());
export function motionOK() { const a = axes(); return a.motion === "full" && a.calm === "off" && !reducedOS.matches; }

/* ---------- the live region: every change of setting is said out loud ---------- */
const live = () => $("#tca-live");
let sayT = 0;
function say(text) { const el = live(); if (!el || !text) return; clearTimeout(sayT); el.textContent = ""; sayT = setTimeout(() => { el.textContent = text; }, 60); }

/* the words a reader sees for a setting and its value, read from the controls themselves, so they are written once */
function axisWords(k, v) {
  const box = $(`.tca-seg[data-axis="${k}"]`);
  const legend = box ? box.querySelector("legend").textContent.trim() : k;
  const input = box ? box.querySelector(`input[value="${CSS.escape(v)}"]`) : null;
  const label = input ? input.closest("label").querySelector("span").firstChild.textContent.trim() : v;
  return `${legend}: ${label}`;
}

/* ---------- apply: write the axes, keep them, keep the rest of the site in step, tell everyone ---------- */
export function apply(next, words) {
  const prev = axes(), out = {...prev};
  for (const [k, v] of Object.entries(next || {})) if (AXES[k] && AXES[k].includes(String(v))) out[k] = String(v);
  for (const k in out) H.setAttribute("data-" + k, out[k]);
  const dropped = [];
  for (const id of [...chosen]) if (!presetOn(id, out)) { chosen.delete(id); dropped.push(id); }      // a setting changed by hand turns its preset off
  store.set(KEY, JSON.stringify({...out, presets: [...chosen]}));
  if (out.contrast !== prev.contrast) store.set("theme", out.contrast === "dark" ? "dark" : "light");      // the record and ballot pages' own switch
  if (out.motion !== prev.motion) store.set("motion", out.motion === "full" ? "on" : "off");
  setPerch();
  sync();
  H.dispatchEvent(new CustomEvent("tca:axes", {detail: {prev, now: out}}));
  if (words !== false) {
    const changed = Object.keys(out).filter(k => out[k] !== prev[k]);
    const off = dropped.map(id => `${presetName(id)} preset off.`).join(" ");
    say([words || "", changed.length ? changed.map(k => axisWords(k, out[k])).join(". ") + "." : "", off].filter(Boolean).join(" "));
  }
}
/* Presets combine. Where two ask for different things on one setting, the gentler choice wins: the larger text, the more
   space, less motion, less fade, the quieter companion, plain words, Calm. On the settings with no gentler side (the
   typeface, the amount of detail, the contrast, the chart colours) the preset chosen last wins. A preset stays on while
   every one of its settings is what the presets together ask for; changing one of them by hand turns it off. */
const GENTLER = {scale: AXES.scale, space: AXES.space, motion: AXES.motion, reveal: AXES.reveal, companion: AXES.companion, lang: AXES.lang, calm: AXES.calm};
const COLOUR = ["deut", "prot", "trit"];
function presetName(id) { const b = $(`[data-preset="${id}"] b`); return b ? b.textContent.trim() : id; }
function presetVals(id, a) { return id === "colour" ? {palette: COLOUR.includes(a.palette) ? a.palette : "deut"} : PRESETS[id]; }
function merged(ids, a) {      // what the presets in ids ask for together, in the order they were chosen
  const out = {};
  for (const id of ids) for (const [k, v] of Object.entries(presetVals(id, a))) {
    if (!(k in out)) { out[k] = v; continue; }
    const order = GENTLER[k];
    out[k] = order ? (order.indexOf(v) > order.indexOf(out[k]) ? v : out[k]) : v;
  }
  return out;
}
function presetOn(id, a = axes()) {
  if (!chosen.has(id)) return false;
  const want = merged([...chosen], a);
  return Object.keys(presetVals(id, a)).every(k => a[k] === want[k]);
}
function togglePreset(id, name) {
  const a = axes();
  if (presetOn(id, a)) {      // off: each of its settings goes to what the presets still on ask for, or else back to the default
    chosen.delete(id);
    const want = merged([...chosen], a), back = {};
    for (const k of Object.keys(presetVals(id, a))) back[k] = k in want ? want[k] : DEF[k];
    apply(back, `${name} off.`);
  } else {
    chosen.delete(id); chosen.add(id);
    const want = merged([...chosen], a), on = {};
    for (const pid of chosen) for (const k of Object.keys(presetVals(pid, a))) on[k] = want[k];
    apply(on, `${name} on.`);
  }
}

/* ---------- the controls show the settings as they are ---------- */
function sync() {
  const a = axes();
  for (const box of $$(".tca-seg[data-axis]")) for (const r of $$("input[type=radio]", box)) r.checked = r.value === a[box.dataset.axis];
  for (const b of $$("[data-preset]")) b.setAttribute("aria-pressed", presetOn(b.dataset.preset, a) ? "true" : "false");
  const m = $("#tca-motion");      // the switch says what is happening: a device that asks for less motion is always obeyed
  if (m) { m.setAttribute("aria-pressed", a.motion === "full" && !reducedOS.matches ? "true" : "false");
    if (reducedOS.matches) m.setAttribute("title", "Your device asks for less motion, so nothing moves."); else m.removeAttribute("title"); }
  const s = currentSkin();
  for (const b of $$("[data-skin]")) b.setAttribute("aria-pressed", s && b.dataset.skin === s.id ? "true" : "false");
}

/* ---------- panels: Help and Reading & access. Non-modal: the page stays usable, Esc or a tap outside closes ---------- */
let openPanel = null, opener = null;
function triggers(id) { return $$(`[aria-controls="${id}"]`); }
function showPanel(panel, from) {
  if (panel.classList.contains("inline")) { if (openPanel) hidePanel(openPanel, false); panel.scrollIntoView({block: "start"}); const h = $("h2", panel); if (h) h.focus({preventScroll: true}); return; }
  if (openPanel && openPanel !== panel) {      // one panel opened from inside another: Esc later returns to what opened the first
    const first = opener, inside = from && openPanel.contains(from);
    hidePanel(openPanel, false);
    if (inside) from = first;
  }
  closeMegas(false); setSheet(false, false);
  panel.hidden = false; openPanel = panel; opener = from || D.activeElement;
  for (const t of triggers(panel.id)) t.setAttribute("aria-expanded", "true");
  sync();
  const h = $("h2", panel); if (h) h.focus({preventScroll: true});
  drawIn(panel);
  if (panel.id === "tca-help") H.dispatchEvent(new CustomEvent("tca:help", {detail: {open: true}}));
}
function hidePanel(panel, restore = true) {
  if (!panel || panel.hidden) return;
  panel.hidden = true;
  for (const t of triggers(panel.id)) t.setAttribute("aria-expanded", "false");
  if (openPanel === panel) openPanel = null;
  if (panel.id === "tca-help") H.dispatchEvent(new CustomEvent("tca:help", {detail: {open: false}}));
  if (restore && opener && D.contains(opener)) opener.focus();
  opener = null;
}
export function togglePanel(id, from, forceOpen) {
  const p = D.getElementById(id); if (!p) return;
  if (!p.hidden && !p.classList.contains("inline") && !forceOpen) hidePanel(p); else showPanel(p, from);
}
export function helpIsOpen() { const p = D.getElementById("tca-help"); return !!p && !p.hidden; }

/* ---------- the mega-menus: a click opens, Esc or a click elsewhere closes ---------- */
function megaButtons() { return $$(".tca-nav button[aria-controls]"); }
function menuMark() {      // a perched companion steps aside while a menu covers its branch
  const open = megaButtons().some(b => b.getAttribute("aria-expanded") === "true") || ($("#tca-burger") && $("#tca-burger").getAttribute("aria-expanded") === "true");
  H.setAttribute("data-menu", open ? "open" : "closed");
}
function closeMegas(restore) {
  for (const b of megaButtons()) {
    if (b.getAttribute("aria-expanded") !== "true") continue;
    b.setAttribute("aria-expanded", "false");
    const m = D.getElementById(b.getAttribute("aria-controls")); if (m) m.hidden = true;
    if (restore) b.focus();
  }
  menuMark();
}
function toggleMega(b) {
  const on = b.getAttribute("aria-expanded") !== "true";
  closeMegas(false);
  if (openPanel) hidePanel(openPanel, false);
  if (!on) return;
  const m = D.getElementById(b.getAttribute("aria-controls")); if (!m) return;
  b.setAttribute("aria-expanded", "true"); m.hidden = false; drawIn(m); menuMark();
}

/* ---------- the menu sheet (phones): the burger folds into an X; the rest of the page is inert while it is open ---------- */
let orient = null;
function setSheet(on, restore = true) {
  const b = $("#tca-burger"), s = $("#tca-sheet"); if (!b || !s) return;
  if (on === (b.getAttribute("aria-expanded") === "true")) return;
  b.setAttribute("aria-expanded", on ? "true" : "false");
  b.setAttribute("aria-label", on ? "Close the menu" : "Menu");
  s.hidden = !on;
  for (const el of [$("main"), $(".tca-foot"), $(".tca-tabs"), $(".tca-dock"), $(".tca-bubble")]) if (el) el.inert = on;
  menuMark();
  if (on) { if (openPanel) hidePanel(openPanel, false); drawIn(s, true); tiltOn(s); }
  else { tiltOff(); if (restore) b.focus(); }
}
/* the menu's tiles catch the light as the phone tilts, where the browser allows it without asking; it never asks */
function tiltOn(scope) {
  if (!motionOK() || orient || typeof DeviceOrientationEvent === "undefined" || typeof DeviceOrientationEvent.requestPermission === "function") return;
  orient = e => {
    if (e.gamma == null) return;
    const x = Math.max(0, Math.min(100, 50 + e.gamma * 1.4)), y = Math.max(0, Math.min(100, 30 + (e.beta - 45) * 1.2));
    for (const i of $$(".tca-ico", scope)) { i.style.setProperty("--hx", x + "%"); i.style.setProperty("--hy", y + "%"); }
  };
  addEventListener("deviceorientation", orient);
}
function tiltOff() { if (orient) { removeEventListener("deviceorientation", orient); orient = null; } }

/* ---------- the five icons: draw-in, the signature move, the tilt toward the pointer, a tick of haptics ---------- */
function play(ico) {
  if (!ico || !motionOK()) return;
  ico.classList.remove("sig"); void ico.offsetWidth; ico.classList.add("sig");
  clearTimeout(ico._sig); ico._sig = setTimeout(() => ico.classList.remove("sig"), 1700);
}
function drawIn(scope, rows) {
  if (!motionOK()) return;
  $$(".tca-ico", scope).forEach((ico, i) => {
    ico.style.setProperty("--row", rows ? String(i) : "0");
    ico.classList.remove("draw"); void ico.offsetWidth; ico.classList.add("draw");
    clearTimeout(ico._draw); ico._draw = setTimeout(() => ico.classList.remove("draw"), 1400 + i * 90);
  });
}
const haptic = () => { try { if (motionOK() && navigator.vibrate) navigator.vibrate(8); } catch (e) {} };
let lastPointer = "mouse";
addEventListener("pointerdown", e => { lastPointer = e.pointerType || "mouse"; }, {capture: true, passive: true});
function wireIcons(scope = D) {
  for (const host of $$("a, button, .tca-door", scope)) {
    const ico = host.classList.contains("tca-door") ? $(".tca-ico", host) : (host.closest(".tca-door") ? null : $(".tca-ico", host));
    if (!ico || host._tcaIco) continue;
    host._tcaIco = true;
    host.addEventListener("pointerenter", e => { if (e.pointerType === "mouse" && fine.matches) play(ico); });
    host.addEventListener("focusin", e => { try { if (e.target.matches(":focus-visible")) play(ico); } catch (x) {} });
    host.addEventListener("pointerdown", e => { if (e.pointerType !== "mouse") { play(ico); haptic(); } });
    if (host.classList.contains("tca-door")) {      // the tile leans toward the pointer and a highlight follows it
      host.addEventListener("pointermove", e => {
        if (e.pointerType !== "mouse" || !fine.matches || !motionOK()) return;
        const r = host.getBoundingClientRect(), x = (e.clientX - r.left) / r.width, y = (e.clientY - r.top) / r.height;
        ico.style.setProperty("--ry", ((x - .5) * 18).toFixed(1) + "deg"); ico.style.setProperty("--rx", ((.5 - y) * 14).toFixed(1) + "deg");
        ico.style.setProperty("--hx", (x * 100).toFixed(0) + "%"); ico.style.setProperty("--hy", (y * 100).toFixed(0) + "%");
      });
      host.addEventListener("pointerleave", () => { for (const p of ["--rx", "--ry", "--hx", "--hy"]) ico.style.removeProperty(p); });
    }
  }
}
/* a menu row holds the sheet open a moment after a tap, so its icon can answer before the page moves */
function holdRows(scope) {
  for (const a of $$(".tca-rows a", scope)) a.addEventListener("click", e => {
    if (e.button || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || lastPointer === "mouse" || !motionOK()) return;
    e.preventDefault(); const go = a.href; setTimeout(() => { location.href = go; }, parseInt(getComputedStyle(H).getPropertyValue("--hold"), 10) || 240);
  });
}
/* the doors draw themselves in the first time they come into view */
function firstSight() {
  if (!("IntersectionObserver" in window)) return;
  const io = new IntersectionObserver(es => { for (const e of es) if (e.isIntersecting) { io.unobserve(e.target); drawIn(e.target); } }, {threshold: .35});
  for (const d of $$(".tca-door")) io.observe(d);
}

/* ---------- the edge fade: position-driven, tagged by a list of selectors, with its gates and its guard ---------- */
const SD = !!(window.CSS && CSS.supports && CSS.supports("animation-timeline: view()"));
const FADE = [".tca-door", ".tca-col", ".tca-vow", ".tca-chart", ".tca-toc", ".tca-sec > .tca-wrap > header", ".tca-doc > h2", ".tca-doc > h3", ".tca-doc > p",
              ".tca-doc > ul", ".tca-doc > ol", ".tca-doc > table", ".tca-doc > .status", ".tca-doc > .formula", ".tca-foot .grid > div"];
let fadeIO = null;
function fadeGated() { const a = axes(); return a.motion === "reduced" || a.reveal === "off" || a.contrast === "high" || reducedOS.matches || forced.matches; }
function nestedScroller(el) {      // overflow hidden, auto or scroll makes a scroll container and view() would bind to it
  for (let a = el.parentElement; a && a !== D.body && a !== H; a = a.parentElement) {
    const s = getComputedStyle(a);
    if (/(hidden|auto|scroll)/.test(s.overflowX + " " + s.overflowY)) return a;
  }
  return null;
}
function untag() { for (const el of $$(".tca-reveal")) el.classList.remove("tca-reveal", "rv-a", "rv-b", "rv-c", "in"); if (fadeIO) { fadeIO.disconnect(); fadeIO = null; } }
function tag() {
  untag();
  H.classList.toggle("tca-sd", SD); H.classList.toggle("tca-io", !SD);
  if (fadeGated()) return;
  const V = innerHeight, top = 62, bottom = phone.matches ? 68 : 0, maxScroll = Math.max(0, H.scrollHeight - V), seen = new Set();
  let n = 0;
  for (const sel of FADE) for (const el of $$(sel)) {
    if (seen.has(el) || el.closest(".tca-reveal") || el.closest(".tca-hero") || el.offsetParent === null) continue;
    const sc = nestedScroller(el);
    if (sc) { console.warn("Edge fade: skipped a block inside a scroll container (use overflow: clip there)", el, "inside", sc); continue; }
    const r = el.getBoundingClientRect(), h = r.height;
    if (!h || h > V * .8) continue;                                 // a tall block would spend too long mid-fade
    const docTop = r.top + scrollY, span = (V - top - bottom) + h;
    const p = s => ((V - bottom) - (docTop - s)) / span;
    if (p(maxScroll) < .16 || p(0) > .84) continue;                // it could never reach the clear band
    el.classList.add("tca-reveal", ["rv-a", "rv-b", "rv-c"][n++ % 3]); seen.add(el);
  }
  if (!SD && "IntersectionObserver" in window) {      // one way only: in, once
    fadeIO = new IntersectionObserver(es => { for (const e of es) if (e.isIntersecting) { e.target.classList.add("in"); fadeIO.unobserve(e.target); } }, {rootMargin: "0px 0px -10% 0px"});
    for (const el of seen) fadeIO.observe(el);
  }
}
let tagT = 0;
const retag = () => { clearTimeout(tagT); tagT = setTimeout(tag, 160); };

/* ---------- small things: words explained in place, the chart's table, the days to Election Day ---------- */
function wireTerms() {
  for (const t of $$(".tca-term")) t.addEventListener("click", () => {
    const d = D.getElementById(t.getAttribute("aria-controls")); if (!d) return;
    const on = t.getAttribute("aria-expanded") !== "true"; t.setAttribute("aria-expanded", on ? "true" : "false"); d.hidden = !on;
  });
}
function wireTables() {
  for (const b of $$("[data-tca-table]")) b.addEventListener("click", () => {
    const fig = b.closest("figure"), tbl = D.getElementById(b.getAttribute("aria-controls")), vis = fig && $(".tca-visual", fig);
    const on = b.getAttribute("aria-expanded") !== "true";
    b.setAttribute("aria-expanded", on ? "true" : "false"); b.textContent = on ? "View as chart" : "View as table";
    if (tbl) tbl.hidden = !on; if (vis) vis.hidden = on;
    say(on ? "Showing the table." : "Showing the chart.");
    retag();
  });
}
function countDays() {
  for (const el of $$("[data-tca-days]")) {
    const [y, m, d] = el.dataset.tcaDays.split("-").map(Number); if (!y) continue;
    const now = new Date(), n = Math.round((new Date(y, m - 1, d) - new Date(now.getFullYear(), now.getMonth(), now.getDate())) / 864e5);
    el.textContent = n > 1 ? `, ${n} days from today` : n === 1 ? ", tomorrow" : n === 0 ? ", today" : "";
  }
}
function wirePick() {
  for (const f of $$("form.tca-pick")) f.addEventListener("submit", e => {
    e.preventDefault(); const s = $("select", f); if (s && s.value) location.href = s.value;
  });
}
/* "Take a break": the page keeps its own address for the cabin, which then offers the way back (this tab only) */
function wireBreak() {
  for (const a of $$("[data-tca-break]")) {
    const keep = () => { try { const h = $("h1"); sessionStorage.setItem("break", JSON.stringify({u: location.href, t: ((h && h.textContent) || D.title).replace(/\s+/g, " ").trim().slice(0, 120)})); } catch (e) {} };
    a.addEventListener("click", keep); a.addEventListener("auxclick", keep);
  }
}

/* ---------- the companion: optional; fetched after first paint; never when off; a plain Help bubble if it cannot draw ---------- */
let dock = null, docking = null, bubbleOn = false, dockFailed = false;
function currentSkin() {
  const want = store.get(SKIN), ready = COMPANIONS.filter(c => c.file);
  return ready.find(c => c.id === want) || ready.find(c => c.default) || ready[0] || null;
}
function setPerch() {
  const c = currentSkin(), a = axes();
  H.setAttribute("data-perch", a.companion !== "off" && c && c.rests === "perch" && !dockFailed && !bubbleOn ? "on" : "off");
  refit();      // a perched companion takes room at the right of the bar
}
function bubble(on) {
  let b = $(".tca-bubble");
  if (on && !b) {
    b = D.createElement("button"); b.type = "button"; b.className = "tca-bubble"; b.setAttribute("aria-label", "Open help");
    b.setAttribute("aria-controls", "tca-help"); b.setAttribute("aria-expanded", helpIsOpen() ? "true" : "false");
    b.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M4 5.5h16v10.5H10l-4.5 3.5V16H4z"/><path d="M9.2 9.4a2.8 2.8 0 0 1 5.5.6c0 1.6-2.2 1.9-2.2 3.2"/><path d="M12.5 15.6v.01"/></svg>';
    b.addEventListener("click", () => togglePanel("tca-help", b));
    D.body.append(b);
  } else if (!on && b) b.remove();
  bubbleOn = !!on; setPerch();
}
function companion() {
  const a = axes(), c = currentSkin();
  if (a.companion === "off") { if (dock) { dock.stop(); dock = null; } bubble(false); return; }
  if (!c || dockFailed) { if (dock) { dock.stop(); dock = null; } bubble(true); return; }
  const opts = {skin: c, still: !motionOK() || a.companion === "still", lean: H.getAttribute("data-lean") === "on"};
  if (dock) { dock.set(opts); bubble(false); return; }
  if (docking) return;
  docking = import("./dock.e03acfc940.js").then(m => m.start({
    ...opts, registry: COMPANIONS, base: new URL("./", import.meta.url).href,
    openHelp: from => togglePanel("tca-help", from, true), helpOpen: helpIsOpen,
    fail: why => { dockFailed = true; dock = null; console.warn("Companion: showing the plain Help bubble instead.", why || ""); bubble(true); }
  })).then(d => {
    if (!d) return;
    dock = d; bubble(false);
    if (axes().companion === "off") { dock.stop(); dock = null; }      // switched off while it was on its way
  }).catch(e => { dockFailed = true; console.warn("Companion: could not load; showing the plain Help bubble.", e); bubble(true); })
    .finally(() => { docking = null; });
}
function afterFirstPaint(fn) {
  const go = () => (window.requestIdleCallback ? requestIdleCallback(() => fn(), {timeout: 3000}) : setTimeout(fn, 400));
  if (D.readyState === "complete") requestAnimationFrame(() => requestAnimationFrame(go)); else addEventListener("load", () => requestAnimationFrame(go), {once: true});
}
function pickSkin(id) {
  const c = COMPANIONS.find(x => x.id === id); if (!c) return;
  if (!c.file) { say(`${c.name} is not ready yet.`); return; }
  store.set(SKIN, id); dockFailed = false; setPerch(); sync();
  if (axes().companion === "off") apply({companion: "on"}, `${c.name} chosen.`); else { say(`${c.name} chosen.`); companion(); }
}

/* ---------- the top bar folds one step at a time until nothing in it overlaps: text size, typeface and a perched
   companion all change what fits, so it is measured, not guessed from the window's width ---------- */
const FIT_WIDE = ["", "motion", "motion wm", "motion wm tight", "motion wm tight help", "motion wm tight help access",
                  "burger motion help access", "burger motion help access wm", "burger icons motion help access wm"];
const FIT_PHONE = ["", "wm"];
function crowded(bar) {
  if (bar.scrollWidth > bar.clientWidth + 1) return true;
  const nav = $(".tca-nav", bar), ul = nav && nav.firstElementChild;
  if (nav && ul && nav.offsetParent !== null && ul.scrollWidth > nav.clientWidth + 1) return true;
  const brand = $(".tca-brand", bar), tools = $(".tca-tools", bar);
  if (brand && tools) {
    const a = brand.getBoundingClientRect(), b = tools.getBoundingClientRect();
    if (a.right > b.left + 1) return true;
    if (nav && nav.offsetParent !== null) { const n = ul.getBoundingClientRect(); if (n.left < a.right - 1 || n.right > b.left + 1) return true; }
  }
  return false;
}
function fitBar() {
  const bar = $(".tca-bar"); if (!bar) return;
  const steps = phone.matches ? FIT_PHONE : FIT_WIDE;
  let i = 0;
  bar.setAttribute("data-fit", steps[0]);
  while (i < steps.length - 1 && crowded(bar)) bar.setAttribute("data-fit", steps[++i]);
  if (!steps[i].includes("burger") && !phone.matches) setSheet(false, false);      // the menu sheet belongs to the folded bar
  lastBar = -1; barBottom();
}
let fitT = 0;
const refit = () => { clearTimeout(fitT); fitT = setTimeout(fitBar, 16); };

/* ---------- where the top bar ends: the panels, the phone menu and a perched companion sit just below it, even while
   a note above the bar (the draft note) is still on screen ---------- */
let lastBar = -1;
function barBottom() {
  const bar = $(".tca-top"); if (!bar) return;
  const b = Math.max(0, Math.round(bar.getBoundingClientRect().bottom));
  if (b !== lastBar) { lastBar = b; H.style.setProperty("--bar-bottom", b + "px"); }
}

/* ---------- wiring ---------- */
function wire() {
  fillIcons(D);
  fitBar();
  addEventListener("scroll", barBottom, {passive: true});
  addEventListener("resize", () => { barBottom(); refit(); });
  if (D.fonts && D.fonts.ready) D.fonts.ready.then(refit);
  try { D.fonts.addEventListener("loadingdone", refit); } catch (e) {}      // a typeface chosen later arrives later
  H.addEventListener("tca:axes", refit);
  for (const b of $$("[data-tca-open]")) {
    b.addEventListener("click", () => togglePanel(b.getAttribute("aria-controls"), b));
    const target = D.getElementById(b.getAttribute("aria-controls"));
    if (target && target.classList.contains("inline")) b.removeAttribute("aria-expanded");      // on the Access page the settings are on the page itself: nothing opens
  }
  for (const x of $$(".tca-panel .x")) x.addEventListener("click", () => hidePanel(x.closest(".tca-panel")));
  for (const box of $$(".tca-seg[data-axis]")) box.addEventListener("change", e => { if (e.target.matches("input[type=radio]")) apply({[box.dataset.axis]: e.target.value}); });
  for (const b of $$("[data-preset]")) b.addEventListener("click", () => togglePreset(b.dataset.preset, b.querySelector("b").textContent.trim()));
  for (const b of $$("[data-tca-reset]")) b.addEventListener("click", () => { chosen.clear(); apply({...DEF}, "Every setting is back to its default."); });
  for (const b of $$("[data-skin]")) b.addEventListener("click", () => pickSkin(b.dataset.skin));
  const m = $("#tca-motion");
  if (m) m.addEventListener("click", () => {
    if (reducedOS.matches) { say("Your device asks for less motion, so nothing on this site moves. That is set in the device's own settings."); return; }
    apply({motion: axes().motion === "full" ? "reduced" : "full"});
  });
  for (const b of megaButtons()) b.addEventListener("click", () => toggleMega(b));
  const burger = $("#tca-burger");
  if (burger) burger.addEventListener("click", () => setSheet(burger.getAttribute("aria-expanded") !== "true"));
  D.addEventListener("keydown", e => {
    if (e.key !== "Escape") return;
    if (megaButtons().some(b => b.getAttribute("aria-expanded") === "true")) { closeMegas(true); e.preventDefault(); return; }
    if ($("#tca-burger") && $("#tca-burger").getAttribute("aria-expanded") === "true") { setSheet(false); e.preventDefault(); return; }
    if (openPanel) { hidePanel(openPanel); e.preventDefault(); }
  });
  D.addEventListener("pointerdown", e => {      // a tap outside closes a panel or a menu
    const t = e.target;
    if (openPanel && !openPanel.contains(t) && !t.closest(`[aria-controls="${openPanel.id}"]`) && !t.closest(".tca-dock")) hidePanel(openPanel, false);
    if (!t.closest(".tca-mega") && !t.closest(".tca-nav")) closeMegas(false);
  });
  D.addEventListener("focusin", e => {      // keyboard focus leaving an open menu closes it
    const open = megaButtons().find(b => b.getAttribute("aria-expanded") === "true"); if (!open) return;
    const menu = D.getElementById(open.getAttribute("aria-controls"));
    if (!menu.contains(e.target) && e.target !== open) closeMegas(false);
  });
  addEventListener("pageshow", e => { if (e.persisted) { closeMegas(false); setSheet(false, false); if (openPanel) hidePanel(openPanel, false); } });
  wireIcons(); holdRows(D); firstSight(); wireTerms(); wireTables(); countDays(); wirePick(); wireBreak();
  sync();
  /* the fade: tag once laid out, again on resize, on any change of setting and when the fonts arrive */
  tag(); addEventListener("resize", retag); addEventListener("load", retag);
  if (D.fonts && D.fonts.ready) D.fonts.ready.then(retag);
  H.addEventListener("tca:axes", () => { retag(); companion(); });
  reducedOS.addEventListener && reducedOS.addEventListener("change", () => { retag(); companion(); sync(); });
  /* the companion hops when the reader jumps to another part of the page */
  addEventListener("hashchange", () => { if (dock && dock.cue) dock.cue("notice"); });
  afterFirstPaint(companion);
}
if (D.readyState === "loading") D.addEventListener("DOMContentLoaded", wire, {once: true}); else wire();
