/* The Civic Archive: Election Night's alerts, a banner across the top of every page (John, 2026-10-30).
   The updater writes the alerts as the night goes on (polls closed in a state, a state's first results, the night's model
   passing 95% for a candidate, a new leader in the model, an early projection at 99% or more with a quarter of the expected
   vote counted, "projected" at 99% or more with half counted, a projection that no longer holds), so every reader sees the
   same events with the same times; this module only shows them. A full projection takes a stronger look than the rest.
   - It asks for nothing outside the night's window: from 4 p.m. Central on Tuesday, November 3, to noon Central on Thursday,
     November 5, 2026, by this device's clock (and on an Election Night page opened with #rehearsal in its address, which
     reads the rehearsal folder). Outside it, it does nothing at all.
   - Inside it: this site's own live figures, /night-live/alerts.json, every two minutes while the page is visible, never
     while it is hidden; nothing from any other server; nothing is sent.
   - The banner: the newest alert's words, its time on this device's clock and a link to the race or state on Election
     Night's pages; the alerts of the last half hour take turns (Pause stops them; pointing at the banner or moving the
     keyboard into it holds them too); "See all alerts" lists every one, newest first; the close button hides the banner on
     this device until a newer alert comes (kept in this browser only).
   - Motion off, Calm and reduced motion: a plain swap, nothing slides. A new alert is announced once, politely; never a
     sound.
   The build copies it into shell/ under a hashed name, writes in where the live figures are and names its stylesheet. */
import {t, date, num, tagLang} from "./i18n.d705614426.js";

const LIVE = "night-live/";      /* from the copy's root to the live figures, written by the build */
const CSS = "./alerts.4615a32b76.css";
const D = document, H = D.documentElement, ROOT = new URL("../", import.meta.url);
const START = Date.UTC(2026, 10, 3, 22, 0), END = Date.UTC(2026, 10, 5, 18, 0);      /* 4 p.m. CST Nov 3 to noon CST Nov 5 */
const EVERY = 120000, TURN = 8000, RECENT = 30 * 60000, MAX_TURN = 5;
const KINDS = ["pc", "first", "p95", "lead", "early", "proj", "unproj"];
const SAFE = /^night\/[a-z]{2,8}\/(#(state=[A-Z]{2}|race=[A-Za-z0-9-]+))?$/;
const ls = {get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }, set(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }};
const ss = {get(k) { try { return sessionStorage.getItem(k); } catch (e) { return null; } }, set(k, v) { try { sessionStorage.setItem(k, v); } catch (e) {} }};
const rel = (() => { const p = location.pathname, r = ROOT.pathname; return p.startsWith(r) ? decodeURIComponent(p.slice(r.length)) : ""; })();
const onNight = /^night(\/|$)/.test(rel);
/* a check on this computer only (the preview server): ?alerts=rehearsal or ?alerts=live shows the banner outside the window */
const loopback = /^(127\.0\.0\.1|localhost|\[::1\])$/.test(location.hostname);
const test = loopback ? (new URLSearchParams(location.search).get("alerts") || "") : "";
let reh = test === "rehearsal";
if (!reh && onNight) reh = /^#rehearsal\b/.test(location.hash) || ss.get("night:rehearsal") === "1";
const forced = reh || test === "live";
const inWindow = () => forced || (Date.now() >= START && Date.now() < END);
const fileURL = () => new URL(LIVE + (reh ? "rehearsal/" : "") + "alerts.json", ROOT).href;
const HID = "tca.alerts.v1" + (reh ? ".reh" : ""), SAID = "tca.alerts.said" + (reh ? ".reh" : "");
const reducedOS = (() => { try { return matchMedia("(prefers-reduced-motion: reduce)"); } catch (e) { return {matches: false}; } })();
const still = () => reducedOS.matches || H.getAttribute("data-motion") === "reduced" || H.getAttribute("data-calm") === "on" ||
  H.classList.contains("calm") || ls.get("motion") === "off";

/* ---------- the words: the same sentences the updater prints ---------- */
function pct(p) { return p === ">99" ? t("more than 99%") : p === "<1" ? t("less than 1%") : t("{p}%", {p: num(+p)}); }
function share(sc) {
  const x = +sc;
  if (!isFinite(x)) return t("some");
  if (x >= 0.995) return t("nearly all");
  if (x * 100 < 0.5) return t("less than 1%");
  return t("{p}%", {p: num(Math.round(x * 100))});
}
export function words(e) {
  const v = {state: e.sn || e.s || "", office: e.o || "", name: e.c || "", other: e.w || "", chance: pct(e.p), share: share(e.sc)};
  switch (e.k) {
    case "pc": return e.m ? t("Polls have closed in most of {state}.", v) : t("Polls have closed in {state}.", v);
    case "first": return t("The first results from {state} are in, as the state's election office reports them. Not final.", v);
    case "p95": return t("{name}'s chance in the race for {office} in {state} has passed 95% (Analysis: the model gives {chance} with {share} of the expected vote counted; as reported, not final).", v);
    case "lead": return t("The model now favours {name} over {other} in the race for {office} in {state} (Analysis: {chance} with {share} of the expected vote counted; as reported, not final).", v);
    case "early": return t("Early projection: {name} is likely to win the race for {office} in {state} (Analysis: the model gives 99%+ with {share} of the expected vote counted; as reported, not final).", v);
    case "proj": return t("{name} is projected to win the race for {office} in {state} (Analysis: the model gives 99%+ with {share} of the expected vote counted; as reported, not final).", v);
    case "unproj": return e.e
      ? t("The early projection that {name} would win the race for {office} in {state} no longer holds (Analysis: the model now gives {chance} with {share} of the expected vote counted; as reported, not final).", v)
      : t("The projection that {name} would win the race for {office} in {state} no longer holds (Analysis: the model now gives {chance} with {share} of the expected vote counted; as reported, not final).", v);
  }
  return "";
}
const when = (s, day) => { const d = new Date(s); if (isNaN(d)) return "";
  return date(d, day ? {weekday: "short", hour: "numeric", minute: "2-digit", timeZoneName: "short"} : {hour: "numeric", minute: "2-digit", timeZoneName: "short"}); };
const href = e => (typeof e.u === "string" && SAFE.test(e.u) ? new URL(e.u, ROOT).href : "");

/* ---------- the stylesheet, fetched only inside the window; the banner waits for it (three seconds at most) ---------- */
let cssReady = null;
function css() {
  if (cssReady) return cssReady;
  cssReady = new Promise(done => {
    const l = D.createElement("link");
    l.rel = "stylesheet"; l.href = new URL(CSS, import.meta.url).href; l.setAttribute("data-tca-alerts-css", "");
    l.onload = l.onerror = () => done();
    setTimeout(done, 3000);
    D.head.append(l);
  });
  return cssReady;
}

/* ---------- the banner ---------- */
let box = null, msg = null, pauseBtn = null, liveEl = null, dlg = null, dlgFrom = null;
let all = [], turn = [], at = 0, paused = false, held = false, turnT = 0, pollT = 0, last = 0, top = 0, rehLabel = null, isReh = false;
const X = '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M6 6l12 12M18 6L6 18"/></svg>';
const MOON = '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M20.5 14.2A8.5 8.5 0 1 1 9.8 3.5a6.6 6.6 0 0 0 10.7 10.7z"/></svg>';

function build() {
  box = D.createElement("div");      /* a div with the region role: the pages' own rules for <section> never reach it */
  box.className = "tca-al"; box.setAttribute("role", "region"); box.setAttribute("aria-label", t("Election Night alerts"));
  box.innerHTML = `<div class="tca-al-in"><span class="tca-al-tag">${MOON}<span></span></span><p class="tca-al-msg"></p>
<div class="tca-al-tools"><button type="button" class="tca-al-b" data-al="pause" hidden></button><button type="button" class="tca-al-b" data-al="all" aria-haspopup="dialog"></button>
<button type="button" class="tca-al-x" data-al="close">${X}</button></div></div><div class="tca-al-sr" role="status" aria-live="polite"></div>`;
  tagLang(box);
  msg = box.querySelector(".tca-al-msg"); pauseBtn = box.querySelector('[data-al="pause"]'); liveEl = box.querySelector(".tca-al-sr");
  box.querySelector('[data-al="all"]').textContent = t("See all alerts");
  const x = box.querySelector('[data-al="close"]');
  x.setAttribute("aria-label", t("Hide the alerts until a new one comes")); x.title = t("Hide the alerts until a new one comes");
  pauseBtn.addEventListener("click", () => { paused = !paused; pauseBtn.textContent = paused ? t("Resume") : t("Pause"); spin(); });
  box.querySelector('[data-al="all"]').addEventListener("click", e => openAll(e.currentTarget));
  x.addEventListener("click", hide);
  box.addEventListener("pointerenter", () => { held = true; });
  box.addEventListener("pointerleave", () => { held = false; spin(); });
  box.addEventListener("focusin", () => { held = true; });
  box.addEventListener("focusout", e => { if (!box.contains(e.relatedTarget)) { held = false; spin(); } });
  /* just above the page's own top bar, under any note the page puts first; else at the very top, after a skip link */
  const bar = D.querySelector("header.tca-top, header.top") || D.querySelector("body > header");
  if (bar && bar.parentNode) bar.parentNode.insertBefore(box, bar);
  else { const f = D.body.firstElementChild; if (f && f.matches('a[href^="#"]')) f.after(box); else D.body.prepend(box); }
  dispatchEvent(new Event("resize"));      /* the top bar and the panels measure where they now stand */
}
function show(i, slide) {
  const e = turn[i]; if (!e || !box) return;
  at = i;
  const u = href(e), w = words(e);
  msg.textContent = "";
  const tm = D.createElement("time"); tm.dateTime = e.t; tm.textContent = when(e.t);
  const a = D.createElement(u ? "a" : "span"); if (u) a.href = u; a.textContent = w;
  msg.append(tm, " ", a);
  box.dataset.kind = e.k; box.dataset.n = String(e.n);
  /* a full projection (half the expected vote counted, 99% or more) takes the stronger look: a brass band, "Projected" on
     its label, larger type, and one sweep of light across it with motion on; every other alert, the plain band */
  const proj = e.k === "proj";
  box.querySelector(".tca-al-tag > span").textContent = proj ? (isReh ? t("Rehearsal: projected") : t("Projected")) : (isReh ? t("Rehearsal") : t("Election Night"));
  box.classList.remove("glow");
  if (proj && !still()) { void box.offsetWidth; box.classList.add("glow"); }
  if (slide && !still()) { box.classList.remove("slide"); void box.offsetWidth; box.classList.add("slide"); }
  else box.classList.remove("slide");
}
function spin() {
  clearTimeout(turnT);
  if (!box || turn.length < 2 || paused) return;
  turnT = setTimeout(() => {
    if (!held && !paused && D.visibilityState !== "hidden" && !(dlg && dlg.open)) show((at + 1) % turn.length, true);
    spin();
  }, TURN);
}
function remove() {
  clearTimeout(turnT);
  if (box) { box.remove(); box = null; dispatchEvent(new Event("resize")); }
}
function hide() {
  ls.set(HID, JSON.stringify({n: top}));
  const next = D.querySelector("header.tca-top a, header.tca-top button, header.top a, header.top button");
  remove();
  if (next) { try { next.focus({preventScroll: true}); } catch (e) {} }
}
function say(text) { if (!liveEl || !text) return; liveEl.textContent = ""; setTimeout(() => { if (liveEl) liveEl.textContent = text; }, 80); }

/* ---------- every alert, newest first ---------- */
function openAll(from) {
  if (!dlg) {
    dlg = D.createElement("dialog");
    dlg.className = "tca-aldlg"; dlg.setAttribute("aria-labelledby", "tca-aldlg-h");
    tagLang(dlg);
    dlg.addEventListener("click", e => { if (e.target === dlg) dlg.close(); });      /* a click on the dimmed page around it */
    /* Escape closes the list and goes no further, so the page's own Escape (a map letting go, a menu) does not move the focus */
    dlg.addEventListener("keydown", e => { if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); dlg.close(); } });
    dlg.addEventListener("close", () => { if (dlgFrom && dlgFrom.isConnected) { try { dlgFrom.focus({preventScroll: true}); } catch (e) {} } dlgFrom = null; spin(); });
    D.body.append(dlg);
  }
  dlgFrom = from || D.activeElement;
  const items = all.map(e => {
    const u = href(e);
    return `<li data-kind="${e.k}"><time datetime="${esc(e.t)}">${esc(when(e.t, true))}</time>${e.k === "proj" ? `<b class="tca-aldlg-k">${esc(t("Projected"))}</b> ` : ""}${u ? `<a href="${esc(u)}">${esc(words(e))}</a>` : `<span>${esc(words(e))}</span>`}</li>`;
  }).join("");
  dlg.innerHTML = `<div class="tca-aldlg-in"><button type="button" class="tca-aldlg-x" aria-label="${esc(t("Close"))}">${X}</button>
<h2 id="tca-aldlg-h">${esc(t("Election Night alerts"))}</h2>
${isReh ? `<p class="tca-aldlg-reh">${esc(rehLabel ? t("Rehearsal: replayed figures from {label}. Not 2026 results.", {label: rehLabel}) : t("Rehearsal: replayed figures. Not 2026 results."))}</p>` : ""}
<p class="tca-aldlg-note">${esc(t("Newest first, at the time on this device. Results are as each state's election office reports them, not final until certified. Alerts marked Analysis are a computer model's estimates: the official count decides."))}</p>
<ol>${items}</ol></div>`;
  dlg.querySelector(".tca-aldlg-x").addEventListener("click", () => dlg.close());
  if (typeof dlg.showModal === "function") { try { dlg.showModal(); } catch (e) { dlg.setAttribute("open", ""); } } else dlg.setAttribute("open", "");
  const h = dlg.querySelector("h2"); h.tabIndex = -1; try { h.focus({preventScroll: true}); } catch (e) {}
}
const esc = s => String(s).replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"})[c]);

/* ---------- the file ---------- */
const valid = e => e && typeof e === "object" && KINDS.includes(e.k) && typeof e.t === "string" && !isNaN(Date.parse(e.t)) && Number.isFinite(e.n);
function take(doc) {
  if (!doc || doc.v !== 1 || !Array.isArray(doc.a)) return;
  all = doc.a.filter(valid).sort((a, b) => (Date.parse(b.t) - Date.parse(a.t)) || (b.n - a.n));
  isReh = !!doc.rehearsal; rehLabel = isReh && typeof doc.label === "string" ? doc.label : null;
  const newTop = all.reduce((m, e) => Math.max(m, e.n), 0);
  let hid = 0;
  try { hid = +(JSON.parse(ls.get(HID) || "{}").n) || 0; } catch (e) {}
  const said = +(ss.get(SAID) || 0);
  if (dlg && dlg.open) return;      /* the list being read is not redrawn under the reader; the next look brings it */
  const fresh = newTop > top;
  top = Math.max(top, newTop);
  if (!all.length || newTop <= hid) { remove(); return; }
  const lead = Date.parse(all[0].t);
  turn = all.filter(e => lead - Date.parse(e.t) <= RECENT).slice(0, MAX_TURN);
  const was = box ? turn.findIndex(e => box.dataset.n === String(e.n)) : -1;
  if (!box) build();
  if (isReh) box.querySelector(".tca-al-tag").title = rehLabel ? t("Rehearsal: replayed figures from {label}. Not 2026 results.", {label: rehLabel}) : t("Rehearsal: replayed figures. Not 2026 results.");
  box.classList.toggle("reh", isReh);
  pauseBtn.hidden = turn.length < 2;
  if (pauseBtn.hidden) paused = false;
  pauseBtn.textContent = paused ? t("Resume") : t("Pause");
  show(fresh || was < 0 ? 0 : was, fresh && !!box.dataset.n);
  spin();
  /* a new alert is said once, politely, in this tab; nothing on the first look (the banner is there to be read) */
  if (said && newTop > said) {
    const nw = all.filter(e => e.n > said).sort((a, b) => b.n - a.n)[0];
    if (nw) say(words(nw));
  }
  if (newTop > said) ss.set(SAID, String(newTop));
}
function look() {
  clearTimeout(pollT);
  if (!inWindow()) { remove(); return; }
  if (D.visibilityState === "hidden") return;      /* never while hidden: a look waits until the page is seen again */
  last = Date.now();
  fetch(fileURL(), {cache: "no-store", credentials: "same-origin"})
    .then(r => (r.ok ? r.json() : null)).then(doc => css().then(() => take(doc))).catch(() => {});
  pollT = setTimeout(look, EVERY);
}
function seen() {
  if (D.visibilityState === "hidden") { clearTimeout(pollT); return; }
  if (!inWindow()) { remove(); return; }
  clearTimeout(pollT);
  pollT = setTimeout(look, Math.max(0, last + EVERY - Date.now()));
}
function start() {
  if (!inWindow()) {
    const wait = START - Date.now();
    if (wait > 0 && wait < 864e5) setTimeout(start, wait + 1000);      /* the window opens while the page is open */
    return;
  }
  css();
  D.addEventListener("visibilitychange", seen);
  look();
}
if (D.readyState === "loading") D.addEventListener("DOMContentLoaded", start, {once: true}); else start();
