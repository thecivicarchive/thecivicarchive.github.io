/* The Civic Archive: the companion rides along (John, 2026-10-04). The record and ballot pages still carry their own top
   bar; this small module brings the companion and the page guide onto them until the whole shell is on every page.
   It reads the same choices the home page keeps on this device (tca.a11y.v1: the companion On, Still or Off, and motion;
   tca.companion.skin: which animal), honours the page's own Motion switch and the device's reduced motion, and opens
   the same Help: what this page is, how to use it, where to go next, and the whole site. Every companion opens the same
   guide; with the companion Off, a plain Help button opens it. Nothing is sent anywhere.
   The build copies it into shell/ under a hashed name and puts a small rider.js beside it that imports that name, so
   a page only ever names shell/rider.js. */
import {t, tHTML, N_, need, has, ready, lang as LANG, tagLang} from "./i18n.d705614426.js";      /* the language layer: the rider's words in the reader's language */
import {guideFor, guideHTML, AROUND, LEVELS_LINE, SHARE_LINE} from "./guide.6a1e90f0b4.js";
import {startLevels, chooser, firstCard, levelWords} from "./levels.8f525e9d0f.js";      /* Meet me where I am: how much each page shows, and what for */
import("./nightgate.3109dbc9b1.js").catch(() => {});      /* every way into Election Night: the night sky on the way in (a plain link if this cannot load) */
import("./spacegate.107465086f.js").catch(() => {});      /* every way into On The Ballot and the record: the polling place and the reading room on the way in */
import("./app.9ad954b356.js").catch(() => {});      /* the site as an app: "Get the app" beside the page's own Motion button, the worker, the second-visit note */
import("./share.d8fe07329b.js").catch(() => {});      /* sharing: every [data-share] button, the phone's own share sheet or a small menu of places */
/* counting visits: named here by the build only when a counting service is configured; empty, nothing is loaded or sent.
   With it, Help carries the two switches too, and a link to what is counted. */
const COUNT = "";
if (COUNT) import(COUNT).catch(() => {});

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
  const around = AROUND.map(([l, u, s]) => `<li><a href="${esc(root + u)}"><b>${esc(t(l))}</b><small>${esc(t(s))}</small></a></li>`).join("");
  const radios = [["on", N_("On")], ["still", N_("Still")], ["off", N_("Off")]].map(([v, w]) =>
    `<label><input type="radio" name="tca-rp-comp" value="${v}"><span>${esc(t(w))}</span></label>`).join("");
  const picks = COMPANIONS.map(c => `<li><button type="button" data-skin="${esc(c.id)}" aria-pressed="false"${c.file ? "" : " disabled"}><b>${esc(t(c.name))}</b><i translate="no">${esc(c.latin)}</i></button></li>`).join("");
  tagLang(panel);
  panel.innerHTML = `<button class="x" type="button" aria-label="${esc(t("Close help"))}">${X}</button>
<h2 id="tca-rp-h" tabindex="-1">${esc(t("Help"))}</h2>
<p class="tca-rp-mm"><button type="button" data-tca-open-meet aria-controls="tca-meet" aria-expanded="false" aria-haspopup="dialog">${SLIDERS}<span>${esc(t("Reading & access"))}<small>${esc(t("How much you see, text size, contrast"))}</small></span></button></p>
<h3>${esc(t("On this page"))}</h3><div class="tca-guide"></div>
<h3>${esc(t("Around the site"))}</h3><ul class="tca-rp-around">${around}</ul>
<p class="tca-rp-note">${esc(t(LEVELS_LINE))} ${tHTML("Every setting is on the <0>Access</0> page.", {0: w => `<a href="${esc(root)}access/">${w}</a>`})}</p>
<p class="tca-rp-note">${esc(t(SHARE_LINE))}</p>
<h3>${esc(t("The app"))}</h3><div data-tca-app-help><p class="tca-rp-note">${tHTML("<0>Get the app</0>: this site on your phone or computer.", {0: w => `<a href="${esc(root)}app/">${w}</a>`})}</p></div>
${COUNT ? `<h3>${esc(t("Counting visits"))}</h3><div data-tca-count-switches></div>` : ""}
<h3>${esc(t("Your companion"))}</h3>
<p class="tca-rp-note">${esc(t("It is here to open this guide. Every companion gives the same help. It never speaks on its own, and screen readers pass over it."))}</p>
<fieldset class="tca-rp-seg"><legend>${esc(t("Companion"))}</legend><div class="opts">${radios}</div><span class="hint">${esc(t("Still draws it once. Off never loads it."))}</span></fieldset>
<ul class="tca-rp-picks" aria-label="${esc(t("Choose a companion"))}">${picks}</ul>`;
  D.body.append(panel);
  if (COUNT && window.__tcaCount) window.__tcaCount.fill(panel);      /* the counting switches (drawn by the counting script) */
  guideBox = panel.querySelector(".tca-guide");
  panel.querySelector(".x").addEventListener("click", () => toggle(false));
  panel.querySelector("[data-tca-open-meet]").addEventListener("click", () => { const from = opener && opener.isConnected ? opener : null; meetPanel(true, from); });
  for (const r of panel.querySelectorAll('input[name="tca-rp-comp"]')) r.addEventListener("change", () => { setCompanionAxis(r.value); companion(); sync(); });
  for (const b of panel.querySelectorAll("[data-skin]")) b.addEventListener("click", () => {
    store.set(SKIN, b.dataset.skin);
    if (companionAxis() === "off") setCompanionAxis("on");
    failed = false; companion(); sync();
  });
  fill(); sync();
  H.dispatchEvent(new CustomEvent("tca:help", {detail: {open: false, built: true}}));      /* the app's part of Help fills itself in */
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
  /* in another language, Help is first drawn once the guide's words are here (they come in their own file) */
  if (!panel && !has("guide")) { need("guide").then(() => toggle(open, from, restore)); return; }
  if (!panel) buildPanel();
  open = open == null ? panel.hidden : open;
  if (open === !panel.hidden) return;
  if (open) {
    if (mm && !mm.hidden) meetPanel(false);      /* one panel at a time */
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

/* ---------- where the companion stands: clear of the page's own bar at the top and anything fixed in the corner ----------
   The page's own fixed boxes (a bottom tab bar, a version label, a "to the top" button) are found once, and again when the
   window changes width or the page adds to itself; on scroll only their rectangles are measured. */
const OURS = ".tca-dock,.tca-bubble,.tca-rp,.tca-mmpanel,.tca-lvcard,.tca-appnote,.tca-mmbtn,.tca-sr-rider";
let fixedEls = null;
function barEl() { return D.querySelector("header.top") || D.querySelector("header"); }
function fixedIn(root, bar, out) {
  const all = root.nodeType === 1 ? [root, ...root.querySelectorAll("*")] : [];
  for (const el of all) {
    if (el.closest(OURS) || (bar && (el === bar || bar.contains(el)))) continue;
    if (getComputedStyle(el).position === "fixed") out.push(el);
  }
  return out;
}
function scanFixed() { fixedEls = D.body ? fixedIn(D.body, barEl(), []) : []; }
let addT = 0, added = [];
function noteAdded(ms) {
  for (const m of ms) for (const nd of m.addedNodes) if (nd.nodeType === 1 && !nd.closest(OURS)) added.push(nd);
  if (added.length && !addT) addT = setTimeout(() => {
    addT = 0; const bar = barEl(), list = added; added = [];
    if (fixedEls) { fixedEls = fixedEls.filter(el => el.isConnected); for (const nd of list) if (nd.isConnected) fixedIn(nd, bar, fixedEls); }
    placeSoon();
  }, 250);
}
function place() {
  const bar = barEl();
  if (!fixedEls) scanFixed();
  let edge = 0;
  if (bar) { const r = bar.getBoundingClientRect(); const st = getComputedStyle(bar); if (st.position === "fixed" || st.position === "sticky") edge = Math.max(0, r.bottom); }
  let lift = 0, left = 0;
  for (const el of fixedEls) {
    if (!el.isConnected) continue;
    const r = el.getBoundingClientRect();
    if (!r.width || !r.height || r.height > innerHeight * 0.5 || r.top <= innerHeight - 150) continue;
    if (getComputedStyle(el).visibility === "hidden") continue;
    if (r.right > innerWidth - 130) lift = Math.max(lift, innerHeight - r.top + 6);
    if (r.left < 80) left = Math.max(left, innerHeight - r.top + 6);
  }
  for (const el of [D.querySelector(".tca-dock"), bubbleEl, panel]) {
    if (!el) continue;
    el.style.setProperty("--bar-bottom", edge + "px");
    el.style.setProperty("--tab-h", lift + "px");
  }
  /* the first-visit card sits just above a bottom bar on the left */
  const card = D.querySelector(".tca-lvcard"); if (card) card.style.setProperty("--tab-h", left + "px");
  if (mmBtn && mmBtn.classList.contains("float")) {
    mmBtn.style.setProperty("--tab-h", left + "px");
    /* in the corner only once the reader has scrolled past the opening screen (or while its panel is open, or it has the
       keyboard's focus); at the top Help carries the same button */
    const away = scrollY < innerHeight * 0.75 && !(mm && !mm.hidden);
    if (mmBtn.classList.contains("away") !== away) mmBtn.classList.toggle("away", away);
  }
}
let placeT = 0;
const placeSoon = () => { if (!placeT) placeT = requestAnimationFrame(() => { placeT = 0; place(); }); };

/* ---------- the companion: optional; never loaded when Off; a plain Help button if it cannot draw ---------- */
function bubble(on) {
  if (on && !bubbleEl) {
    bubbleEl = D.createElement("button");
    bubbleEl.type = "button"; bubbleEl.className = "tca-bubble"; bubbleEl.innerHTML = BUBBLE;
    bubbleEl.setAttribute("aria-label", t("Open help")); bubbleEl.setAttribute("aria-controls", "tca-help"); bubbleEl.setAttribute("aria-expanded", isOpen() ? "true" : "false");
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

/* ---------- Meet me where I am, and the reading settings, on pages that keep their own top bar ----------
   The head script the build puts on these pages has already written the reader's choices onto <html> (level, focus, text
   size, typeface, spacing, contrast, Calm, motion), before the first frame. Here they change: the same record as the
   shell's (tca.a11y.v1), the older theme and motion switches kept in step, and the page told (tca:axes). */
const AX = {face: ["standard", "dyslexia", "hyperlegible"], scale: ["100", "115", "130", "150", "200"], space: ["standard", "generous"],
  contrast: ["standard", "high", "dark"], motion: ["full", "reduced"], calm: ["off", "on"], level: ["3", "1", "2", "4", "5", "6"],
  focus: ["none", "ballot", "reps", "congress", "state", "results"], language: ["en"]};
/* what is said aloud when a setting changes: one whole sentence for each value, so a language can word each its own way */
const SAID = {face: {standard: N_("Typeface: standard"), dyslexia: N_("Typeface: Lexend"), hyperlegible: N_("Typeface: Atkinson Hyperlegible")},
  contrast: {standard: N_("Contrast: standard"), high: N_("Contrast: high"), dark: N_("Contrast: dark")}, calm: {off: N_("Calm: off"), on: N_("Calm: on")},
  space: {standard: N_("Spacing: standard"), generous: N_("Spacing: generous")}, motion: {full: N_("Motion: on"), reduced: N_("Motion: reduced")}};
const WORDS = {scale: v => t("Text size: {v} percent", {v: +v})};
for (const k in SAID) WORDS[k] = v => t(SAID[k][v] || v);
function riderAxes() {
  const o = {}, s = saved();
  for (const k in AX) { const v = H.getAttribute("data-" + k); o[k] = AX[k].includes(v) ? v : (AX[k].includes(String(s[k])) ? String(s[k]) : AX[k][0]); }
  return o;
}
let liveEl = null, sayT = 0;
function say(t) {
  if (!t) return;
  if (!liveEl) { liveEl = D.createElement("div"); liveEl.className = "tca-sr-rider"; liveEl.setAttribute("role", "status"); liveEl.setAttribute("aria-live", "polite"); D.body.append(liveEl); }
  clearTimeout(sayT); liveEl.textContent = ""; sayT = setTimeout(() => { liveEl.textContent = t; }, 60);
}
function riderApply(next, words) {
  const prev = riderAxes(), out = {...prev};
  for (const [k, v] of Object.entries(next || {})) if (AX[k] && AX[k].includes(String(v))) out[k] = String(v);
  for (const k in out) H.setAttribute("data-" + k, out[k]);
  store.set(KEY, JSON.stringify({...saved(), ...out}));
  if (out.contrast !== prev.contrast) {      // the pages' own light and dark switch follows; high contrast is drawn on light
    store.set("theme", out.contrast === "dark" ? "dark" : "light");
    H.dataset.theme = out.contrast === "dark" ? "dark" : "light";
    H.removeAttribute("data-tca-own");      // a page that wrote its own contrast (Election Night's) now shows the reader's
  }
  if (out.motion !== prev.motion || out.calm !== prev.calm) {      // the page's own Motion switch follows too
    const on = out.motion === "full" && out.calm === "off";
    store.set("motion", on ? "on" : "off");
    H.classList.toggle("calm", !on || reducedOS.matches);
    const m = D.getElementById("motion"); if (m) m.setAttribute("aria-pressed", on && !reducedOS.matches ? "true" : "false");
  }
  if (out.scale !== prev.scale && window.__tcaFs) window.__tcaFs(+out.scale / 100);
  H.dispatchEvent(new CustomEvent("tca:axes", {detail: {prev, now: out}}));
  if (words !== false) {
    const changed = Object.keys(out).filter(k => out[k] !== prev[k]);
    const told = changed.map(k => (k === "level" || k === "focus") ? levelWords(k, out[k]) : WORDS[k] ? WORDS[k](out[k]) : "").filter(Boolean);
    say([words || "", told.length ? told.join(". ") + "." : ""].filter(Boolean).join(" "));
  }
  placeSoon();
}

/* the button beside the page's own Motion button (as "Get the app" is placed), and the compact panel it opens */
const SLIDERS = '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M4 7h9M17 7h3M4 17h3M11 17h9"/><path d="M15 4.6a2.4 2.4 0 1 1 0 4.8a2.4 2.4 0 1 1 0-4.8zM9 14.6a2.4 2.4 0 1 1 0 4.8a2.4 2.4 0 1 1 0-4.8z"/></svg>';
let mm = null, mmBtn = null, mmFrom = null, mmCls = "", mmT = 0;
/* how far the page or its top bar runs past the screen's edge */
function overBy() {
  const bar = D.querySelector("header.top"); let n = Math.max(0, H.scrollWidth - H.clientWidth);
  if (bar) for (const el of [bar, ...bar.children]) n = Math.max(n, el.scrollWidth - el.clientWidth);
  return n;
}
function meetButton() {
  const bar = D.querySelector("header.top"), motion = bar && bar.querySelector("#motion");
  if (!bar || !motion || D.querySelector("[data-tca-meet-btn]")) return;
  mmCls = [...motion.classList].filter(c => !/^(on|off|active|pressed)$/.test(c)).join(" ");
  mmBtn = D.createElement("button");
  mmBtn.type = "button"; mmBtn.setAttribute("data-tca-meet-btn", "");
  mmBtn.setAttribute("aria-controls", "tca-meet"); mmBtn.setAttribute("aria-expanded", "false"); mmBtn.setAttribute("aria-haspopup", "dialog");
  mmBtn.innerHTML = `${SLIDERS}<span class="tca-mm-lab">${esc(t("Reading & access"))}</span>`;
  tagLang(mmBtn);
  mmBtn.addEventListener("click", () => meetPanel(null, mmBtn));
  seat(true);
  /* phones fire resize when the address bar slides; only a change of width can change the bar's room */
  let w = innerWidth;
  addEventListener("resize", () => { if (innerWidth === w) return; w = innerWidth; clearTimeout(mmT); mmT = setTimeout(seat, 150); });
  if (D.fonts && D.fonts.ready) D.fonts.ready.then(() => seat());
  addEventListener("load", () => seat(), {once: true});
}
/* Beside the page's own Motion button, where the bar has room for it; where it has none (a phone, on the pages whose bar
   is full: it would run off the screen or fold the bar onto another line), it waits in the bottom left corner instead,
   shown there once the reader scrolls past the opening screen (Help carries the same button at the top). In the reading
   order it comes straight after the top bar either way. Measured, not guessed, like "Get the app"; it is moved only when its
   place changes, and keeps the keyboard's focus if it had it. */
function seat(first) {
  const bar = D.querySelector("header.top"), motion = bar && bar.querySelector("#motion");
  if (!mmBtn || !motion) return;
  const had = D.activeElement === mmBtn, wasFloat = mmBtn.classList.contains("float"), wasAway = mmBtn.classList.contains("away");
  const inBar = mmBtn.isConnected && !wasFloat;
  const app = D.querySelector(".tca-appbtn"), appOn = !!app && !app.hidden;      // this button comes first; "Get the app" is also in Help
  if (app) app.hidden = true;
  let base, tall;
  if (inBar) {      /* measured without it where it stands, so it is not moved when it still fits */
    mmBtn.style.display = "none"; base = overBy(); tall = bar.getBoundingClientRect().height; mmBtn.style.display = "";
  } else {
    base = overBy(); tall = bar.getBoundingClientRect().height;
    mmBtn.className = mmCls + " tca-mmbtn"; motion.before(mmBtn);
  }
  const float = overBy() > base + 1 || bar.getBoundingClientRect().height > tall + 1;      /* it would push the bar wider, or onto another line */
  if (float) { mmBtn.className = "tca-mmbtn float" + (wasFloat ? (wasAway ? " away" : "") : " away"); bar.after(mmBtn); }
  if (app) app.hidden = !appOn;
  if (had && D.activeElement !== mmBtn) { try { mmBtn.focus({preventScroll: true}); } catch (e) {} }
  if (first || float !== wasFloat) dispatchEvent(new CustomEvent("tca:seat"));      // "Get the app" measures its own room again
  placeSoon();
}
function meetPanel(open, from) {
  if (!mm) {
    mm = D.createElement("section");
    mm.className = "tca-mmpanel tca-lvx"; mm.id = "tca-meet"; mm.hidden = true;
    mm.setAttribute("role", "dialog"); mm.setAttribute("aria-modal", "false"); mm.setAttribute("aria-labelledby", "tca-meet-h");
    tagLang(mm);
    mm.innerHTML = `<button class="x" type="button" aria-label="${esc(t("Close"))}">${X}</button><h2 id="tca-meet-h" tabindex="-1">${esc(t("Meet me where I am"))}</h2>
<p class="lead">${esc(t("Choose how much you want to see, what you came for, and how the page should read. The facts stay the same at every level."))}</p><div data-mm></div>`;
    D.body.append(mm);
    chooser(mm.querySelector("[data-mm]"), {apply: riderApply, axes: riderAxes, reading: true, access: true});
    mm.querySelector(".x").addEventListener("click", () => meetPanel(false));
  }
  open = open == null ? mm.hidden : open;
  if (open === !mm.hidden) return;
  if (open) {
    if (isOpen()) toggle(false, null, false);
    mmFrom = from || D.activeElement;
    const bar = D.querySelector("header.top");
    mm.style.setProperty("--bar-bottom", (bar ? Math.max(0, Math.round(bar.getBoundingClientRect().bottom)) : 64) + "px");
    mm.hidden = false;
    const h = mm.querySelector("h2"); try { h.focus({preventScroll: true}); } catch (e) { h.focus(); }
  } else {
    mm.hidden = true;
    if (mmFrom && mmFrom.isConnected) { try { mmFrom.focus({preventScroll: true}); } catch (e) {} }
    mmFrom = null;
  }
  for (const b of D.querySelectorAll('[aria-controls="tca-meet"]')) b.setAttribute("aria-expanded", open ? "true" : "false");
  placeSoon();
}
/* The page's own light and dark switch (its moon) and the reading settings stay one: dark makes the contrast "dark"; light
   makes it "standard", unless the reader chose high contrast, which is drawn on the light page. High contrast and the
   dark page are never both on: pressing the moon under high contrast is a choice of dark. */
function followTheme() {
  /* a page drawn dark by design, with no light look of its own (the places to sit: <meta name="color-scheme" content="dark">),
     is not the reader pressing the moon: its dark is never taken for their choice, or one visit would turn the whole site dark */
  if (D.querySelector('meta[name="color-scheme"][content="dark"]')) return;
  const t = H.getAttribute("data-theme"), c = H.getAttribute("data-contrast");
  if (t === "dark" && c !== "dark") riderApply({contrast: "dark"}, false);
  else if (t !== "dark" && c === "dark") riderApply({contrast: "standard"}, false);
}

function start() {
  if (!D.querySelector("link[data-tca-rider-css]")) {      /* the head normally names it already, so it is there before the first frame */
    const css = D.createElement("link");
    css.rel = "stylesheet"; css.href = new URL("./rider.f12dac683e.css", import.meta.url).href;
    D.head.append(css);
  }
  if (window.__tcaFs) window.__tcaFs();      /* text size: style sheets that came after the head (in the body) are read too */
  /* a page's own script may have put its stored dark theme back after the head script drew high contrast on light: the
     reader's high contrast wins, as the head script meant; from here on the page's moon and the settings move together */
  if (H.getAttribute("data-contrast") === "high" && H.getAttribute("data-theme") === "dark" && !H.hasAttribute("data-tca-own")) {
    H.setAttribute("data-theme", "light"); store.set("theme", "light");
  }
  followTheme();
  new MutationObserver(followTheme).observe(H, {attributes: true, attributeFilter: ["data-theme"]});
  startLevels({apply: riderApply, say});
  meetButton();
  firstCard({apply: riderApply, motionOn, say});
  addEventListener("keydown", e => { if (e.key === "Escape" && mm && !mm.hidden) { e.preventDefault(); meetPanel(false); } });
  D.addEventListener("pointerdown", e => { if (mm && !mm.hidden && !mm.contains(e.target) && !e.target.closest('[aria-controls="tca-meet"]')) { mmFrom = null; meetPanel(false); } }, true);
  addEventListener("hashchange", () => { fill(); if (dock && dock.cue) dock.cue("notice"); placeSoon(); });
  let fw = innerWidth;
  addEventListener("resize", () => { if (innerWidth !== fw) { fw = innerWidth; fixedEls = null; } placeSoon(); });
  new MutationObserver(noteAdded).observe(D.body, {childList: true, subtree: true});
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

/* in another language, the rider starts once its words are here (2.5 seconds at most), so everything it draws is drawn in it */
const go = () => { if (D.readyState === "loading") D.addEventListener("DOMContentLoaded", start); else start(); };
if (LANG === "en") go(); else ready.then(go);
