/* The Civic Archive: the companion rides along (John, 2026-10-04). The record and ballot pages still carry their own top
   bar; this small module brings the companion and the page guide onto them until the whole shell is on every page.
   It reads the same choices the home page keeps on this device (tca.a11y.v1: the companion On, Still or Off, and motion;
   tca.companion.skin: which animal), honours the page's own Motion switch and the device's reduced motion, and opens
   the same Help: what this page is, how to use it, where to go next, and the whole site. Every companion opens the same
   guide; with the companion Off, a plain Help button opens it. Nothing is sent anywhere.
   build_shell.py copies it into shell/ under a hashed name and puts a small rider.js beside it that imports that name, so
   a page only ever names shell/rider.js. */
import {guideFor, guideHTML, AROUND} from "./guide.5f8cc936f8.js";

const COMPANIONS = [{"id":"penguin","name":"Adélie penguin","latin":"Pygoscelis adeliae","rests":"floor","default":true,"file":"penguin.fc3508c0ff.js"},{"id":"chickadee","name":"Black-capped chickadee","latin":"Poecile atricapillus","rests":"perch","default":false,"file":"chickadee.f33156ba46.js"},{"id":"retriever","name":"Golden retriever","latin":"Canis familiaris","rests":"floor","default":false,"file":"retriever.1a310d8f2a.js"},{"id":"cat","name":"Tabby cat","latin":"Felis catus","rests":"floor","default":false,"file":"cat.455ca7cef4.js"},{"id":"squirrel","name":"Eastern gray squirrel","latin":"Sciurus carolinensis","rests":"floor","default":false,"file":"squirrel.72f0cacf7a.js"},{"id":"chipmunk","name":"Eastern chipmunk","latin":"Tamias striatus","rests":"floor","default":false,"file":"chipmunk.d1037c6838.js"},{"id":"snail","name":"Garden snail","latin":"Cornu aspersum","rests":"floor","default":false,"file":"snail.e7acf3fb32.js"}];
const KEY = "tca.a11y.v1", SKIN = "tca.companion.skin", D = document, H = D.documentElement;
const store = {get: k => { try { return localStorage.getItem(k); } catch (e) { return null; } },
               set: (k, v) => { try { localStorage.setItem(k, v); } catch (e) {} }};
const SHELL = new URL("./", import.meta.url), ROOT = new URL("../", import.meta.url);
const rel = () => { const p = location.pathname, r = ROOT.pathname; return p.startsWith(r) ? decodeURIComponent(p.slice(r.length)) : ""; };
const up = () => { const d = rel().split("/").length - 1; return d > 0 ? "../".repeat(d) : "./"; };
const reducedOS = matchMedia("(prefers-reduced-motion: reduce)");
const esc = s => String(s).replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"})[c]);

function saved() { try { const s = JSON.parse(store.get(KEY) || "null"); return s && typeof s === "object" ? s : {}; } catch (e) { return {}; } }
function companionAxis() { const v = saved().companion; return ["on", "still", "off"].includes(v) ? v : "on"; }
function setCompanionAxis(v) { const s = saved(); s.companion = v; store.set(KEY, JSON.stringify(s)); }
function motionOn() {
  if (reducedOS.matches || H.classList.contains("calm")) return false;      // the page's own Motion switch puts "calm" on <html>
  const m = store.get("motion"), s = saved();
  if (m === "off") return false;
  if (m === "on") return true;
  return s.motion !== "reduced" && s.calm !== "on";
}
function skinNow() {
  const want = store.get(SKIN), ready = COMPANIONS.filter(c => c.file);
  return ready.find(c => c.id === want) || ready.find(c => c.default) || ready[0] || null;
}
function lean() {
  const n = navigator, c = n.connection || {};
  try { return !!((n.deviceMemory && n.deviceMemory < 4) || (n.hardwareConcurrency && n.hardwareConcurrency <= 4) || c.saveData); } catch (e) { return false; }
}

const X = '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M6 6l12 12M18 6L6 18"/></svg>';
const BUBBLE = '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M4 5.5h16v10.5H10l-4.5 3.5V16H4z"/><path d="M9.2 9.4a2.8 2.8 0 0 1 5.5.6c0 1.6-2.2 1.9-2.2 3.2"/><path d="M12.5 15.6v.01"/></svg>';

let panel = null, guideBox = null, opener = null, dock = null, docking = null, bubbleEl = null, failed = false;

function buildPanel() {
  panel = D.createElement("section");
  panel.className = "tca-rp"; panel.id = "tca-help"; panel.hidden = true;
  panel.setAttribute("role", "dialog"); panel.setAttribute("aria-modal", "false"); panel.setAttribute("aria-labelledby", "tca-rp-h");
  const root = up();
  const around = AROUND.map(([l, u, s]) => `<li><a href="${esc(root + u)}"><b>${esc(l)}</b><small>${esc(s)}</small></a></li>`).join("");
  const radios = [["on", "On"], ["still", "Still"], ["off", "Off"]].map(([v, t]) =>
    `<label><input type="radio" name="tca-rp-comp" value="${v}"><span>${t}</span></label>`).join("");
  const picks = COMPANIONS.map(c => `<li><button type="button" data-skin="${esc(c.id)}" aria-pressed="false"${c.file ? "" : " disabled"}><b>${esc(c.name)}</b><i>${esc(c.latin)}</i></button></li>`).join("");
  panel.innerHTML = `<button class="x" type="button" aria-label="Close help">${X}</button>
<h2 id="tca-rp-h" tabindex="-1">Help</h2>
<h3>On this page</h3><div class="tca-guide"></div>
<h3>Around the site</h3><ul class="tca-rp-around">${around}</ul>
<p class="tca-rp-note">Text size, type, contrast and more are on the <a href="${esc(root)}access/">Access</a> page.</p>
<h3>Your companion</h3>
<p class="tca-rp-note">It is here to open this guide. Every companion gives the same help. It never speaks on its own, and screen readers pass over it.</p>
<fieldset class="tca-rp-seg"><legend>Companion</legend><div class="opts">${radios}</div><span class="hint">Still draws it once. Off never loads it.</span></fieldset>
<ul class="tca-rp-picks" aria-label="Choose a companion">${picks}</ul>`;
  D.body.append(panel);
  guideBox = panel.querySelector(".tca-guide");
  panel.querySelector(".x").addEventListener("click", () => toggle(false));
  for (const r of panel.querySelectorAll('input[name="tca-rp-comp"]')) r.addEventListener("change", () => { setCompanionAxis(r.value); companion(); sync(); });
  for (const b of panel.querySelectorAll("[data-skin]")) b.addEventListener("click", () => {
    store.set(SKIN, b.dataset.skin);
    if (companionAxis() === "off") setCompanionAxis("on");
    failed = false; companion(); sync();
  });
  fill(); sync();
}
function fill() { if (guideBox) guideBox.innerHTML = guideHTML(guideFor(rel(), location.hash), up()); }
function sync() {
  if (!panel) return;
  const a = companionAxis(), s = skinNow();
  for (const r of panel.querySelectorAll('input[name="tca-rp-comp"]')) r.checked = r.value === a;
  for (const b of panel.querySelectorAll("[data-skin]")) b.setAttribute("aria-pressed", s && b.dataset.skin === s.id ? "true" : "false");
}
function isOpen() { return !!panel && !panel.hidden; }
function toggle(open, from, restore = true) {
  if (!panel) buildPanel();
  open = open == null ? panel.hidden : open;
  if (open === !panel.hidden) return;
  if (open) {
    opener = from || D.activeElement; fill(); sync(); place();
    panel.hidden = false;
    const h = panel.querySelector("h2"); try { h.focus({preventScroll: true}); } catch (e) { h.focus(); }
  } else {
    panel.hidden = true;
    if (restore && opener && opener.isConnected) { try { opener.focus({preventScroll: true}); } catch (e) {} }
  }
  for (const b of D.querySelectorAll('[aria-controls="tca-help"]')) b.setAttribute("aria-expanded", open ? "true" : "false");
  H.dispatchEvent(new CustomEvent("tca:help", {detail: {open}}));
}

/* ---------- where the companion stands: clear of the page's own bar at the top and anything fixed in the corner ---------- */
function place() {
  const bar = D.querySelector("header.top") || D.querySelector("header");
  let edge = 0;
  if (bar) { const r = bar.getBoundingClientRect(); const st = getComputedStyle(bar); if (st.position === "fixed" || st.position === "sticky") edge = Math.max(0, r.bottom); }
  let lift = 0;
  for (const el of D.querySelectorAll("body *")) {
    if (el === panel || el.closest(".tca-dock,.tca-bubble,.tca-rp") || el === bar || (bar && bar.contains(el))) continue;
    const st = getComputedStyle(el);
    if (st.position !== "fixed" || st.visibility === "hidden" || st.display === "none") continue;
    const r = el.getBoundingClientRect();
    if (!r.width || !r.height || r.height > innerHeight * 0.5) continue;
    if (r.right > innerWidth - 130 && r.top > innerHeight - 150) lift = Math.max(lift, innerHeight - r.top + 6);
  }
  for (const el of [D.querySelector(".tca-dock"), bubbleEl, panel]) {
    if (!el) continue;
    el.style.setProperty("--bar-bottom", edge + "px");
    el.style.setProperty("--tab-h", lift + "px");
  }
}
let placeT = 0;
const placeSoon = () => { if (!placeT) placeT = requestAnimationFrame(() => { placeT = 0; place(); }); };

/* ---------- the companion: optional; never loaded when Off; a plain Help button if it cannot draw ---------- */
function bubble(on) {
  if (on && !bubbleEl) {
    bubbleEl = D.createElement("button");
    bubbleEl.type = "button"; bubbleEl.className = "tca-bubble"; bubbleEl.innerHTML = BUBBLE;
    bubbleEl.setAttribute("aria-label", "Open help"); bubbleEl.setAttribute("aria-controls", "tca-help"); bubbleEl.setAttribute("aria-expanded", isOpen() ? "true" : "false");
    bubbleEl.addEventListener("click", () => toggle(null, bubbleEl));
    D.body.append(bubbleEl); place();
  } else if (!on && bubbleEl) { bubbleEl.remove(); bubbleEl = null; }
}
function companion() {
  const a = companionAxis(), c = skinNow();
  if (a === "off") { if (dock) { dock.stop(); dock = null; } bubble(true); return; }
  if (!c || failed) { if (dock) { dock.stop(); dock = null; } bubble(true); return; }
  const opts = {skin: c, still: !motionOn() || a === "still", lean: lean()};
  if (dock) { dock.set(opts); bubble(false); return; }
  if (docking) return;
  docking = import("./dock.e03acfc940.js").then(m => m.start({
    ...opts, registry: COMPANIONS, base: SHELL.href,
    openHelp: from => toggle(true, from), helpOpen: isOpen,
    fail: why => { failed = true; dock = null; console.warn("Companion: showing the plain Help button instead.", why || ""); bubble(true); }
  })).then(d => {
    if (!d) return;
    dock = d; bubble(false); place();
    if (companionAxis() === "off") { dock.stop(); dock = null; bubble(true); }
  }).catch(e => { failed = true; console.warn("Companion: could not load; showing the plain Help button.", e); bubble(true); })
    .finally(() => { docking = null; });
}

function start() {
  const css = D.createElement("link");
  css.rel = "stylesheet"; css.href = new URL("./rider.56cc86c2d8.css", import.meta.url).href;
  D.head.append(css);
  addEventListener("hashchange", () => { fill(); if (dock && dock.cue) dock.cue("notice"); });
  addEventListener("resize", placeSoon);
  addEventListener("scroll", placeSoon, {passive: true});
  addEventListener("keydown", e => { if (e.key === "Escape" && isOpen()) { e.preventDefault(); toggle(false); } });
  D.addEventListener("pointerdown", e => {
    if (!isOpen()) return;
    const t = e.target;
    if (!panel.contains(t) && !t.closest(".tca-dock,.tca-bubble")) toggle(false, null, false);      // a click elsewhere keeps its own focus
  }, true);
  addEventListener("storage", e => { if (e.key === KEY || e.key === SKIN || e.key === "motion") { companion(); sync(); } });
  new MutationObserver(() => { if (dock) companion(); }).observe(H, {attributes: true, attributeFilter: ["class"]});
  reducedOS.addEventListener && reducedOS.addEventListener("change", () => companion());
  /* the companion comes after the page has been drawn, so it never slows the page itself */
  const go = () => { place(); companion(); };
  if ("requestIdleCallback" in window) requestIdleCallback(go, {timeout: 1500}); else setTimeout(go, 400);
}

if (D.readyState === "loading") D.addEventListener("DOMContentLoaded", start); else start();
