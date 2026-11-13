/* The Civic Archive: Election Night's alerts, a banner across the top of every page (John, 2026-10-30).
   The updater writes the alerts as the night goes on (polls closed in a state, a state's first results, the night's model
   passing 95% for a candidate, a new leader in the model, an early read at 99% or more with a quarter of the expected vote
   counted, "projected" at 99% or more with half counted, a projection that no longer holds), so every reader sees the same
   events with the same times; this module only shows them. A full projection takes a stronger look than the rest.
   - The words (John, 2026-11-02): a short title with an emoji, then a sentence; lively, and every fact as it stands. The
     emoji is decorative: what is read aloud is the words alone.
   - It asks for nothing outside the night's window: from 4 p.m. Central on Tuesday, November 3, to noon Central on Thursday,
     November 5, 2026, by this device's clock (and on an Election Night page opened with #rehearsal in its address, which
     reads the rehearsal folder). Outside it, it does nothing at all, except for an alert shared by its link (below).
   - Inside it: this site's own live figures, /night-live/alerts.json, every two minutes while the page is visible, never
     while it is hidden; nothing from any other server; nothing is sent.
   - The banner: the newest alert's words, its time on this device's clock and a link to the race or state on Election
     Night's pages; the alerts of the last half hour take turns (Pause stops them; pointing at the banner or moving the
     keyboard into it holds them too); "See all alerts" lists the whole night (alerts-all.json, read when the list opens),
     newest first, with a state filter, "Projections only", and a Share button on each; the close button hides the banner
     on this device until a newer alert comes (kept in this browser only).
   - Sharing (John, 2026-11-02): an alert's link is its race's address with ?alert=<its number>. A page opened with it reads
     the whole night's file (any time from the window's opening, with no end, so a shared link keeps working) and shows that
     alert in a card; the number is then taken out of the address, so a reload does not open it again.
   - Notify me (John, 2026-11-02): notifications on this device, from this page, while the site or app is open; the
     browser is asked for permission only when the reader presses the button. Settings and the alerts already seen are kept
     in this browser (tca.alerts.notify.v1); nothing leaves the device. Switching on marks every alert already out as seen,
     so nobody gets a burst; a look brings at most five at once, and only alerts of the last half hour.
   - Motion off, Calm and reduced motion: a plain swap, nothing slides. A new alert is announced once, politely; never a
     sound.
   The build copies it into shell/ under a hashed name, writes in where the live figures are and names its stylesheet. */
import {t, date, num, tagLang} from "./i18n.d705614426.js";

const LIVE = "night-live/";      /* from the copy's root to the live figures, written by the build */
const CSS = "./alerts.88b07a5981.css";
const D = document, H = D.documentElement, ROOT = new URL("../", import.meta.url);
const START = Date.UTC(2026, 10, 3, 22, 0), END = Date.UTC(2026, 10, 5, 18, 0);      /* 4 p.m. CST Nov 3 to noon CST Nov 5 */
const FIRST = Date.UTC(2026, 10, 3, 23, 0);      /* the first polls close (Indiana and Kentucky, 6 p.m. Eastern): named by the notice before the first alert */
const EVERY = 120000, TURN = 8000, RECENT = 30 * 60000, MAX_TURN = 5, NOTE_MAX = 5, SEEN_MAX = 1500;
const KINDS = ["pc", "first", "p95", "lead", "early", "proj", "unproj"];
const PROJ = ["proj", "early", "unproj"];      /* "Projections only": projected, early reads, and a projection taken back */
const EMOJI = {pc: "\u{1F5F3}️", first: "\u{1F4CA}", p95: "\u{1F4C8}", lead: "\u{1F504}", early: "⚡", proj: "\u{1F4E3}", unproj: "\u{1F62E}"};
const BELL = "\u{1F514}";
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
const fileURL = (name = "alerts.json") => new URL(LIVE + (reh ? "rehearsal/" : "") + name, ROOT).href;
const HID = "tca.alerts.v1" + (reh ? ".reh" : ""), SAID = "tca.alerts.said" + (reh ? ".reh" : "");
const reducedOS = (() => { try { return matchMedia("(prefers-reduced-motion: reduce)"); } catch (e) { return {matches: false}; } })();
const still = () => reducedOS.matches || H.getAttribute("data-motion") === "reduced" || H.getAttribute("data-calm") === "on" ||
  H.classList.contains("calm") || ls.get("motion") === "off";

/* an alert shared by its link: its number is read once, then taken out of the address (a reload does not reopen it) */
const asked = (() => {
  let q; try { q = new URLSearchParams(location.search); } catch (e) { return null; }
  if (!q.has("alert")) return null;
  const v = q.get("alert") || "";
  try { const x = new URL(location.href); x.searchParams.delete("alert"); history.replaceState(history.state, "", x.pathname + x.search + x.hash); } catch (e) {}
  return /^\d{1,9}$/.test(v) ? +v : -1;
})();

/* ---------- the words: the same title and sentence the updater prints (election/alerts.py, texts()) ---------- */
function pct(p) { return p === ">99" ? t("more than 99%") : p === "<1" ? t("less than 1%") : t("{p}%", {p: num(+p)}); }
function share(sc) {
  const x = +sc;
  if (!isFinite(x)) return t("some");
  if (x >= 0.995) return t("nearly all");
  if (x * 100 < 0.5) return t("less than 1%");
  return t("{p}%", {p: num(Math.round(x * 100))});
}
const nth = n => { const v = n % 100; return n + (v >= 10 && v <= 20 ? "th" : ({1: "st", 2: "nd", 3: "rd"})[n % 10] || "th"); };
/* a race's name as a person says it, from its state and office title */
function raceName(e) {
  const state = e.sn || e.s || "", o = String(e.o || "").trim();
  const m = /^U\.S\. Representative, District (\d+)/.exec(o);
  if (m && +m[1]) return t("{state}'s {nth} District", {state, nth: nth(+m[1])});
  if (/^U\.S\. Representative/.test(o)) return t("{state}'s at-large House seat", {state});
  if (/^U\.S\. Senator/.test(o)) return /special/i.test(o) ? t("the {state} Senate special", {state}) : t("the {state} Senate race", {state});
  if (/^Governor\b/.test(o)) return t("the {state} governor's race", {state});
  return o ? t("the {state} {office} race", {state, office: o}) : state;
}
/* [title, sentence], without the emoji */
export function texts(e) {
  const race = raceName(e);
  const v = {state: e.sn || e.s || "", race, Race: race.charAt(0).toUpperCase() + race.slice(1), name: e.c || "", other: e.w || "",
    chance: pct(e.p), share: share(e.sc)};
  switch (e.k) {
    case "pc": return [e.m ? t("Polls are closed in most of {state}!", v) : t("Polls are closed in {state}!", v),
      t("The count starts now. Watch the numbers come in as the state posts them.")];
    case "first": return [t("{state}'s first numbers just landed", v),
      t("Fresh from the state's election office. It's early, so expect some big swings as the count goes on.")];
    case "p95": return [t("{name} pulling ahead in {race}", v),
      t("Our model now gives {name} a {chance} chance, with {share} of the expected vote counted. Not final yet.", v)];
    case "lead": return [t("Lead change in {race}!", v),
      t("Our model now favors {name} over {other}, with a {chance} chance and {share} of the vote counted. Not final yet.", v)];
    case "early": return [t("Early read: {name} likely to win {race}", v),
      t("Only {share} of the vote is in, and our model already gives {name} a better than 99% chance. Still, it ain't over till it's over!", v)];
    case "proj": return [t("{name} projected to win {race}!", v),
      t("With {share} of the vote counted, our model gives {name} a better than 99% chance. The official results are still to come.", v)];
    case "unproj":
      /* under half now: the count has turned the other way, not merely tightened */
      if (e.p === "<1" || (e.p !== ">99" && +e.p < 50)) return [t("Big swing in {race}!", v), e.e
        ? t("Our early projection for {name} is off. With {share} counted, {name}'s chance has dropped to {chance}. The count has turned the other way.", v)
        : t("Our projection for {name} is off. With {share} counted, {name}'s chance has dropped to {chance}. The count has turned the other way.", v)];
      return [t("{Race} just got interesting again", v), e.e
      ? t("Our early projection for {name} is off. With {share} counted, {name}'s chance has slipped to {chance}. This one's a real contest again.", v)
      : t("Our projection for {name} is off. With {share} counted, {name}'s chance has slipped to {chance}. This one's a real contest again.", v)];
  }
  return ["", ""];
}
const join = (a, b) => a + (/[.!?]$/.test(a) ? " " : ". ") + b;
/* the words alone (what is read aloud) */
export function words(e) { const [a, b] = texts(e); return a ? join(a, b) : ""; }
const when = (s, how) => { const d = new Date(s); if (isNaN(d)) return "";
  return date(d, how === 2 ? {weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit", timeZoneName: "short"}
    : how ? {weekday: "short", hour: "numeric", minute: "2-digit", timeZoneName: "short"} : {hour: "numeric", minute: "2-digit", timeZoneName: "short"}); };
const href = e => (typeof e.u === "string" && SAFE.test(e.u) ? new URL(e.u, ROOT).href : "");
/* an alert's own link: its race's address with ?alert=<its number> and nothing else (on this computer, a rehearsal check
   keeps its ?alerts=rehearsal so the link opens the same file) */
function link(e) {
  const x = new URL(href(e) || new URL("night/", ROOT).href);
  x.search = "?" + (test ? "alerts=" + encodeURIComponent(test) + "&" : "") + "alert=" + e.n;
  return x.href;
}
const esc = s => String(s).replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"})[c]);
const SHARE_SVG = '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><path d="M8.6 13.5l6.8 4M15.4 6.5l-6.8 4"/></svg>';
/* the site's own Share (shell_src/share.js reads these attributes): the alert's title and sentence, and its link */
function shareBtn(e) {
  const [a, b] = texts(e);
  return `<button type="button" class="tca-share tca-aldlg-sh" data-share aria-haspopup="dialog" data-share-url="${esc(link(e))}" data-share-title="${esc(a)}"`
    + ` data-share-text="${esc(EMOJI[e.k] + " " + join(a, b))}">${SHARE_SVG}<span>${esc(t("Share"))}</span></button>`;
}
/* inviting someone to the alerts (John, 2026-11-03): the link opens Election Night with Notify me already open */
function inviteBtn() {
  return `<button type="button" class="tca-share tca-aldlg-sh" data-share aria-haspopup="dialog" data-share-url="${esc(new URL("night/?notify=1", ROOT).href)}"`
    + ` data-share-title="${esc(t("Election Night alerts from The Civic Archive"))}" data-share-text="${esc(BELL + " " + t("Get Election Night alerts on your phone or computer from The Civic Archive: polls closing, first results, lead changes and projections, as each state reports them."))}">`
    + `${SHARE_SVG}<span>${esc(t("Share the alerts"))}</span></button>`;
}
/* sharing the live list itself (John, 2026-11-03): the link opens Election Night with the list open, on one state when one
   is picked in its State filter (?feed=SC, or ?feed=all) */
function feedShare() {
  const st = flt.st, name = st ? ((source().find(e => e.s === st) || {}).sn || st) : "";
  return {url: new URL("night/?feed=" + (st || "all"), ROOT).href,
    title: st ? t("Election Night live alerts: {state}", {state: name}) : t("Election Night live alerts"),
    text: "\u{1F4E3} " + (st ? t("Follow {state}'s Election Night alerts live on The Civic Archive: polls closing, first results, lead changes and projections, as the state reports them.", {state: name})
      : t("Follow Election Night's alerts live on The Civic Archive: polls closing, first results, lead changes and projections, as each state reports them."))};
}
function feedBtn() {
  const o = feedShare();
  return `<button type="button" class="tca-share tca-aldlg-sh" data-share data-alfeed aria-haspopup="dialog" data-share-url="${esc(o.url)}" data-share-title="${esc(o.title)}"`
    + ` data-share-text="${esc(o.text)}">${SHARE_SVG}<span>${esc(t("Share the live alerts"))}</span></button>`;
}
function syncFeed() {
  const b = dlg && dlg.querySelector("[data-alfeed]"); if (!b) return;
  const o = feedShare();
  b.setAttribute("data-share-url", o.url); b.setAttribute("data-share-title", o.title); b.setAttribute("data-share-text", o.text);
}
const openWords = e => (e.k === "pc" || e.k === "first") ? t("Open the state") : t("Open the race");

/* ---------- the stylesheet, fetched only when something is shown; the banner waits for it (three seconds at most) ---------- */
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

/* ---------- notifications on this device ---------- */
const NKEY = "tca.alerts.notify.v1", SEENK = reh ? "seenReh" : "seen";
const canNotify = () => { try { return "Notification" in window && window.isSecureContext !== false; } catch (e) { return false; } };
/* an iPhone or iPad browser shows notifications only from the site added to the Home Screen: the button stays, to say so */
const apple = () => /iPhone|iPad|iPod/.test(navigator.userAgent || "") || (/Macintosh/.test(navigator.userAgent || "") && navigator.maxTouchPoints > 1);
const offerNotify = () => canNotify() || apple();
const perm = () => { try { return Notification.permission; } catch (e) { return "denied"; } };
/* switched on and allowed here: the page then keeps looking for new alerts while it is in the background */
const noting = () => canNotify() && nget().on && perm() === "granted";
function nget() {
  let s = null; try { s = JSON.parse(ls.get(NKEY) || "null"); } catch (e) {}
  s = s && typeof s === "object" ? s : {};
  const list = a => Array.isArray(a) ? a.filter(x => typeof x === "string").slice(-SEEN_MAX) : [];
  return {on: s.on === true, send: s.send === "all" ? "all" : "proj", pick: s.pick === true,
    states: Array.isArray(s.states) ? s.states.filter(c => typeof c === "string" && /^[A-Z]{2}$/.test(c)) : [], seen: list(s.seen), seenReh: list(s.seenReh)};
}
const nput = s => ls.set(NKEY, JSON.stringify(s));
const key = e => (typeof e.id === "string" && e.id ? e.id : "n:" + e.n);
const wants = (s, e) => (s.send === "all" || PROJ.includes(e.k)) && (!s.pick || !s.states.length || s.states.includes(e.s));
function markSeen(s, list) {
  const have = new Set(s[SEENK]);
  for (const e of list) if (!have.has(key(e))) { have.add(key(e)); s[SEENK].push(key(e)); }
  s[SEENK] = s[SEENK].slice(-SEEN_MAX);
}
/* each alert not seen before on this device: kept as seen; shown when it matches the settings and is from the last half hour */
function notifyNew(list) {
  if (!canNotify()) return;
  const s = nget();
  if (!s.on) return;
  const had = new Set(s[SEENK]), fresh = list.filter(e => !had.has(key(e)));
  if (!fresh.length) return;
  markSeen(s, fresh); nput(s);
  if (perm() !== "granted") return;
  const now = Date.now();
  fresh.filter(e => wants(s, e) && now - Date.parse(e.t) <= RECENT).sort((a, b) => a.n - b.n).slice(-NOTE_MAX).forEach(note);
}
async function note(e) {
  const [a, b] = texts(e), url = href(e) || new URL("night/", ROOT).href;
  const o = {body: b, icon: new URL("icon-192.png", ROOT).href, tag: "tca-alert-" + (e.r || e.s || e.n), renotify: true,
    timestamp: Date.parse(e.t) || Date.now(), data: {url}};
  const title = EMOJI[e.k] + " " + a;
  let reg = null;
  try { if ("serviceWorker" in navigator) reg = await navigator.serviceWorker.getRegistration(ROOT.href); } catch (err) {}
  if (reg && reg.showNotification) { try { await reg.showNotification(title, o); return; } catch (err) {} }
  try {
    const n = new Notification(title, o);
    n.onclick = ev => { try { ev.preventDefault(); focus(); } catch (x) {} n.close(); location.assign(url); };
  } catch (err) {}
}
/* the browser's question, asked only from a press of Notify me or of the switch (old browsers answer by callback) */
const ask = () => new Promise(res => {
  let done = false; const fin = r => { if (!done) { done = true; res(r || perm()); } };
  try { const p = Notification.requestPermission(fin); if (p && p.then) p.then(fin, () => fin()); } catch (e) { fin(); }
});
function turnOn() {
  const s = nget(); s.on = true;
  markSeen(s, all.concat(full || []));      /* everything already out counts as seen: no burst */
  nput(s); bell();
}
function bell() {
  if (!box) return;
  const b = box.querySelector('[data-al="notify"]'); if (!b) return;
  const on = nget().on && perm() === "granted";
  b.querySelector(".tca-al-bt").textContent = on ? t("Notifications on") : t("Notify me");
  b.setAttribute("aria-label", on ? t("Notifications on: change them") : t("Notify me"));
}
async function notifyPress(from) {
  if (canNotify() && perm() === "default" && (await ask()) === "granted") turnOn();
  openDlg("notify", from);
}

/* ---------- the banner ---------- */
let box = null, msg = null, pauseBtn = null, liveEl = null, dlg = null, dlgFrom = null, view = "all", one = null, full = null, fullAt = 0;
let all = [], turn = [], at = 0, paused = false, held = false, turnT = 0, pollT = 0, last = 0, top = 0, rehLabel = null, isReh = false;
const flt = {st: "", proj: false};
const X = '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M6 6l12 12M18 6L6 18"/></svg>';
const MOON = '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M20.5 14.2A8.5 8.5 0 1 1 9.8 3.5a6.6 6.6 0 0 0 10.7 10.7z"/></svg>';

function build() {
  box = D.createElement("div");      /* a div with the region role: the pages' own rules for <section> never reach it */
  box.className = "tca-al"; box.setAttribute("role", "region"); box.setAttribute("aria-label", t("Election Night alerts"));
  box.innerHTML = `<div class="tca-al-in"><span class="tca-al-tag">${MOON}<span></span></span><p class="tca-al-msg"></p>
<div class="tca-al-tools"><button type="button" class="tca-al-b" data-al="pause" hidden></button>${offerNotify() ? `<button type="button" class="tca-al-b" data-al="notify" aria-haspopup="dialog"><span class="tca-al-e" aria-hidden="true">${BELL}</span><span class="tca-al-bt"></span></button>` : ""}<button type="button" class="tca-al-b" data-al="all" aria-haspopup="dialog"></button>
<button type="button" class="tca-al-x" data-al="close">${X}</button></div></div><div class="tca-al-sr" role="status" aria-live="polite"></div>`;
  tagLang(box);
  msg = box.querySelector(".tca-al-msg"); pauseBtn = box.querySelector('[data-al="pause"]'); liveEl = box.querySelector(".tca-al-sr");
  box.querySelector('[data-al="all"]').textContent = t("See all alerts");
  const x = box.querySelector('[data-al="close"]');
  x.setAttribute("aria-label", t("Hide the alerts until a new one comes")); x.title = t("Hide the alerts until a new one comes");
  pauseBtn.addEventListener("click", () => { paused = !paused; pauseBtn.textContent = paused ? t("Resume") : t("Pause"); spin(); });
  box.querySelector('[data-al="all"]').addEventListener("click", e => openDlg("all", e.currentTarget));
  const nb = box.querySelector('[data-al="notify"]');
  if (nb) nb.addEventListener("click", e => notifyPress(e.currentTarget));
  x.addEventListener("click", hide);
  box.addEventListener("pointerenter", () => { held = true; });
  box.addEventListener("pointerleave", () => { held = false; spin(); });
  box.addEventListener("focusin", () => { held = true; });
  box.addEventListener("focusout", e => { if (!box.contains(e.relatedTarget)) { held = false; spin(); } });
  bell();
  /* just above the page's own top bar, under any note the page puts first; else at the very top, after a skip link */
  const bar = D.querySelector("header.tca-top, header.top") || D.querySelector("body > header");
  if (bar && bar.parentNode) bar.parentNode.insertBefore(box, bar);
  else { const f = D.body.firstElementChild; if (f && f.matches('a[href^="#"]')) f.after(box); else D.body.prepend(box); }
  dispatchEvent(new Event("resize"));      /* the top bar and the panels measure where they now stand */
}
function show(i, slide) {
  const e = turn[i]; if (!e || !box) return;
  at = i;
  const u = href(e), [a, b] = texts(e);
  msg.textContent = "";
  const tm = D.createElement("time"); tm.dateTime = e.t; tm.textContent = when(e.t);
  const w = D.createElement(u ? "a" : "span"); if (u) w.href = u;
  w.innerHTML = `<span class="tca-al-e" aria-hidden="true">${EMOJI[e.k] || ""}</span><b>${esc(a)}</b> ${esc(b)}`;
  msg.append(tm, " ", w);
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

/* ---------- the window over the page: every alert, one shared alert, or Notify me ---------- */
function ensureDlg() {
  if (dlg) return;
  dlg = D.createElement("dialog");
  dlg.className = "tca-aldlg"; dlg.setAttribute("aria-labelledby", "tca-aldlg-h");
  tagLang(dlg);
  dlg.addEventListener("click", e => {
    if (e.target === dlg) { dlg.close(); return; }      /* a click on the dimmed page around it */
    const b = e.target.closest("[data-ald]"); if (!b || !dlg.contains(b)) return;
    const a = b.getAttribute("data-ald");
    if (a === "close") dlg.close();
    else if (a === "all") openDlg("all");
    else if (a === "notify") notifyPress();
    else if (a === "open") dlg.close();      /* the link goes on to the race; on the race's own page the page is simply shown */
  });
  dlg.addEventListener("change", onChange);
  /* Escape closes the window and goes no further, so the page's own Escape (a map letting go, a menu) does not move the
     focus; with a Share menu open inside it, Escape closes only that menu (share.js) */
  dlg.addEventListener("keydown", e => {
    if (e.key !== "Escape") return;
    e.preventDefault();
    if (dlg.querySelector(".tca-sharebox:not([hidden])")) return;
    e.stopPropagation(); dlg.close();
  });
  dlg.addEventListener("cancel", e => { if (dlg.querySelector(".tca-sharebox:not([hidden])")) e.preventDefault(); });
  dlg.addEventListener("close", () => { if (dlgFrom && dlgFrom.isConnected) { try { dlgFrom.focus({preventScroll: true}); } catch (e) {} } dlgFrom = null; spin(); });
  D.body.append(dlg);
}
function openDlg(v, from, arg) {
  ensureDlg();
  if (!dlg.open) dlgFrom = from || D.activeElement;
  view = v; if (v === "one") one = arg;
  render();
  if (!dlg.open) { if (typeof dlg.showModal === "function") { try { dlg.showModal(); } catch (e) { dlg.setAttribute("open", ""); } } else dlg.setAttribute("open", ""); }
  const h = dlg.querySelector("h2"); h.tabIndex = -1; try { h.focus({preventScroll: true}); } catch (e) {}
  if (v === "all") loadAll().then(() => { if (dlg.open && view === "all") { fillOptions(); list(); syncFeed(); } });
}
const head = (title, emoji) => `<button type="button" class="tca-aldlg-x" data-ald="close" aria-label="${esc(t("Close"))}">${X}</button>
<h2 id="tca-aldlg-h">${emoji ? `<span class="tca-aldlg-e" aria-hidden="true">${emoji}</span>` : ""}${esc(title)}</h2>
${isReh && !emoji ? `<p class="tca-aldlg-reh">${esc(rehLabel ? t("Rehearsal: replayed figures from {label}. Not 2026 results.", {label: rehLabel}) : t("Rehearsal: replayed figures. Not 2026 results."))}</p>` : ""}`;
const NOTE = () => t("Results are as each state's election office reports them, not final until certified. Chances and projections come from our computer model, an estimate: the official count decides.");
function render() {
  const nb = offerNotify() ? `<button type="button" class="tca-aldlg-b" data-ald="notify"><span class="tca-aldlg-e" aria-hidden="true">${BELL}</span>${esc(nget().on && perm() === "granted" ? t("Notifications on") : t("Notify me"))}</button>` : "";
  if (view === "one") {
    const e = one, u = e && href(e), [a, b] = e ? texts(e) : ["", ""];
    dlg.innerHTML = `<div class="tca-aldlg-in scroll">${head(t("Election Night alert"))}`
      + (e ? `<article class="tca-aldlg-card" data-kind="${e.k}"><time datetime="${esc(e.t)}">${esc(when(e.t, 2))}</time>
<p class="tca-aldlg-t"><span class="tca-aldlg-e" aria-hidden="true">${EMOJI[e.k]}</span>${esc(a)}</p><p class="tca-aldlg-s">${esc(b)}</p></article>
<p class="tca-aldlg-note">${esc(NOTE())}</p>
<p class="tca-aldlg-acts">${u ? `<a class="tca-aldlg-go" href="${esc(u)}" data-ald="open">${esc(openWords(e))}</a>` : ""}<button type="button" class="tca-aldlg-b" data-ald="all">${esc(t("See all alerts"))}</button>${shareBtn(e)}</p>`
        : `<p class="tca-aldlg-miss">${esc(t("That alert is not in the night's list on this site. The link may be mistyped, or the alerts may not be posted yet."))}</p>
<p class="tca-aldlg-acts">${(full || all).length ? `<button type="button" class="tca-aldlg-b" data-ald="all">${esc(t("See all alerts"))}</button>` : ""}<button type="button" class="tca-aldlg-b" data-ald="close">${esc(t("Close"))}</button></p>`)
      + `</div>`;
    return;
  }
  if (view === "notify") { dlg.innerHTML = notifyHTML(); return; }
  dlg.innerHTML = `<div class="tca-aldlg-in">${head(t("Election Night alerts"))}
<p class="tca-aldlg-note">${esc(t("Newest first, at the time on this device."))} ${esc(NOTE())}</p>
<div class="tca-aldlg-bar"><label class="tca-aldlg-f"><span>${esc(t("State"))}</span><select data-alf="st"></select></label>
<label class="tca-aldlg-c"><input type="checkbox" data-alf="proj"${flt.proj ? " checked" : ""}><span>${esc(t("Projections only"))}</span></label>${nb}${feedBtn()}</div>
<p class="tca-aldlg-count" role="status"></p><ol></ol></div>`;
  fillOptions(); list();
}
const source = () => full || all;
function fillOptions() {
  const sel = dlg && dlg.querySelector('select[data-alf="st"]'); if (!sel) return;
  const n = {}, nm = {};
  for (const e of source()) if (e.s) { n[e.s] = (n[e.s] || 0) + 1; nm[e.s] = e.sn || e.s; }
  if (flt.st && !n[flt.st] && source().length) flt.st = "";      /* kept until the list has loaded (a shared link's state) */
  sel.innerHTML = `<option value="">${esc(t("All states"))}</option>` + Object.keys(n).sort((a, b) => nm[a].localeCompare(nm[b]))
    .map(c => `<option value="${c}"${c === flt.st ? " selected" : ""}>${esc(nm[c])} (${num(n[c])})</option>`).join("");
}
function list() {
  const ol = dlg && dlg.querySelector("ol"); if (!ol) return;
  const src = source(), shown = src.filter(e => (!flt.st || e.s === flt.st) && (!flt.proj || PROJ.includes(e.k)));
  ol.innerHTML = shown.map(e => {
    const u = href(e), [a, b] = texts(e);
    return `<li data-kind="${e.k}"><time datetime="${esc(e.t)}">${esc(when(e.t, 1))}</time>`
      + `<p class="tca-aldlg-t"><span class="tca-aldlg-e" aria-hidden="true">${EMOJI[e.k]}</span>${esc(a)}</p><p class="tca-aldlg-s">${esc(b)}</p>`
      + `<p class="tca-aldlg-acts">${u ? `<a href="${esc(u)}" data-ald="open">${esc(openWords(e))}</a>` : ""}${shareBtn(e)}</p></li>`;
  }).join("");
  const c = dlg.querySelector(".tca-aldlg-count");
  if (c) c.textContent = !src.length ? t("No alerts yet.") : shown.length === src.length ? "" : !shown.length ? t("No alert fits these choices.")
    : t("Showing {n} of {total} alerts.", {n: num(shown.length), total: num(src.length)});
}
const STATES = ("AL Alabama|AK Alaska|AZ Arizona|AR Arkansas|CA California|CO Colorado|CT Connecticut|DE Delaware|DC District of Columbia|FL Florida|"
  + "GA Georgia|HI Hawaii|ID Idaho|IL Illinois|IN Indiana|IA Iowa|KS Kansas|KY Kentucky|LA Louisiana|ME Maine|MD Maryland|MA Massachusetts|MI Michigan|"
  + "MN Minnesota|MS Mississippi|MO Missouri|MT Montana|NE Nebraska|NV Nevada|NH New Hampshire|NJ New Jersey|NM New Mexico|NY New York|NC North Carolina|"
  + "ND North Dakota|OH Ohio|OK Oklahoma|OR Oregon|PA Pennsylvania|RI Rhode Island|SC South Carolina|SD South Dakota|TN Tennessee|TX Texas|UT Utah|"
  + "VT Vermont|VA Virginia|WA Washington|WV West Virginia|WI Wisconsin|WY Wyoming").split("|").map(x => [x.slice(0, 2), x.slice(3)]);
function notifyHTML() {
  const s = nget(), p = canNotify() ? perm() : "none", on = s.on && p === "granted";
  const r = (name, val, cur, label, hint) => `<label class="tca-aldlg-r"><input type="radio" name="${name}" value="${val}" data-aln="${name}"${val === cur ? " checked" : ""}><span>${esc(label)}${hint ? `<small>${esc(hint)}</small>` : ""}</span></label>`;
  return `<div class="tca-aldlg-in scroll">${head(t("Notify me"), BELL)}
<p class="tca-aldlg-note">${esc(t("For now, alerts come through while the site or app is open, even in the background on a computer or Android phone. Nothing about you leaves your device. You can turn this off here or in your browser settings."))}</p>
${p === "denied" ? `<p class="tca-aldlg-warn">${esc(t("This browser is blocking notifications from this site, so the switch stays off. To allow them, open this site's settings in your browser (in most browsers, the icon just left of the address), set Notifications to Allow, then reload this page."))}</p>` : ""}
${p === "none" ? `<p class="tca-aldlg-warn">${esc(t("This browser cannot show notifications from a web page. On an iPhone or iPad, add the site to your Home Screen first (Get the app), then open it from there."))}</p>` : ""}
<label class="tca-aldlg-sw"><input type="checkbox" role="switch" data-aln="on"${on ? " checked" : ""}${p === "denied" || p === "none" ? " disabled" : ""}><span>${esc(t("On for this device"))}</span></label>
<fieldset class="tca-aldlg-fs"><legend>${esc(t("Send me"))}</legend>
${r("tca-aln-send", "proj", s.send, t("Projections only"), t("Projected, early reads, and a projection that no longer holds."))}
${r("tca-aln-send", "all", s.send, t("Every alert"), t("Also polls closing, first numbers, a candidate pulling ahead and lead changes."))}</fieldset>
<fieldset class="tca-aldlg-fs"><legend>${esc(t("States"))}</legend>
${r("tca-aln-st", "all", s.pick ? "pick" : "all", t("All states"))}${r("tca-aln-st", "pick", s.pick ? "pick" : "all", t("Only the states I pick"))}
<div class="tca-aldlg-states" role="group" aria-label="${esc(t("States to notify me about"))}"${s.pick ? "" : " hidden"}>${STATES.map(([c, n]) =>
    `<label><input type="checkbox" value="${c}" data-aln="state"${s.states.includes(c) ? " checked" : ""}><span>${esc(n)}</span></label>`).join("")}</div>
${s.pick && !s.states.length ? `<p class="tca-aldlg-count">${esc(t("No state picked yet: every state for now."))}</p>` : ""}</fieldset>
<p class="tca-aldlg-acts"><button type="button" class="tca-aldlg-b" data-ald="all">${esc(t("See all alerts"))}</button>${inviteBtn()}<button type="button" class="tca-aldlg-b" data-ald="close">${esc(t("Done"))}</button></p></div>`;
}
async function onChange(ev) {
  const el = ev.target, f = el.getAttribute("data-alf"), n = el.getAttribute("data-aln");
  if (f === "st") { flt.st = el.value; list(); syncFeed(); return; }
  if (f === "proj") { flt.proj = el.checked; list(); return; }
  if (!n) return;
  const s = nget();
  if (n === "on") {
    if (!el.checked) { s.on = false; nput(s); bell(); return; }
    if (perm() === "default") await ask();
    if (perm() === "granted") turnOn();
    else { s.on = false; nput(s); }
    bell(); rerender(el);
    return;
  }
  if (n === "tca-aln-send") s.send = el.value === "all" ? "all" : "proj";
  else if (n === "tca-aln-st") s.pick = el.value === "pick";
  else if (n === "state") s.states = [...dlg.querySelectorAll('input[data-aln="state"]:checked')].map(x => x.value);
  nput(s);
  if (n === "tca-aln-st" || n === "state") rerender(el);
}
/* the panel drawn again after a change that shows or hides part of it, with the focus kept on the control just used */
function rerender(el) {
  const sel = el.type === "checkbox" && el.value && el.getAttribute("data-aln") === "state" ? `input[data-aln="state"][value="${el.value}"]`
    : el.type === "radio" ? `input[name="${el.name}"][value="${el.value}"]` : `input[data-aln="${el.getAttribute("data-aln")}"]`;
  const box2 = dlg.querySelector(".tca-aldlg-in"), y = box2 ? box2.scrollTop : 0;
  render();
  const b2 = dlg.querySelector(".tca-aldlg-in"); if (b2) b2.scrollTop = y;
  const f = dlg.querySelector(sel); if (f) { try { f.focus({preventScroll: true}); } catch (e) {} }
}

/* ---------- the files ---------- */
const valid = e => e && typeof e === "object" && KINDS.includes(e.k) && typeof e.t === "string" && !isNaN(Date.parse(e.t)) && Number.isFinite(e.n);
const sorted = doc => doc.a.filter(valid).sort((a, b) => (Date.parse(b.t) - Date.parse(a.t)) || (b.n - a.n));
const ok = doc => doc && doc.v === 1 && Array.isArray(doc.a);
const getJSON = url => fetch(url, {cache: "no-store", credentials: "same-origin"}).then(r => (r.ok ? r.json() : null)).catch(() => null);
/* the whole night's list, read when the list opens (once in two minutes at most), else the newest alerts' file */
function loadAll() {
  if (full && Date.now() - fullAt < EVERY) return Promise.resolve(full);
  return getJSON(fileURL("alerts-all.json")).then(doc => (ok(doc) ? doc : getJSON(fileURL()))).then(doc => {
    if (!ok(doc)) return full;
    full = sorted(doc); fullAt = Date.now();
    if (doc.rehearsal) { isReh = true; rehLabel = typeof doc.label === "string" ? doc.label : rehLabel; }
    return full;
  });
}
/* before the night's first alert (John, 2026-11-03): a notice that alerts start when the polls close, with Notify me */
function waiting() {
  if (forced || Date.now() > FIRST + 6 * 3600e3) { remove(); return; }      /* long after the first closing, an empty file says nothing */
  if (ls.get(HID) !== null) return;      /* the reader hid it; the night's first alert brings the banner back */
  if (!box) build();
  delete box.dataset.n; box.dataset.kind = "wait";
  pauseBtn.hidden = true; paused = false;
  const ab = box.querySelector('[data-al="all"]'); if (ab) ab.hidden = true;
  box.querySelector(".tca-al-tag > span").textContent = t("Election Night");
  box.classList.remove("glow", "slide", "reh");
  msg.textContent = "";
  const w = D.createElement("span");
  w.innerHTML = `<span class="tca-al-e" aria-hidden="true">${EMOJI.pc}</span><b>${esc(t("Alerts start when the polls close."))}</b> `
    + esc(Date.now() < FIRST ? t("The first polls close at {time}.", {time: when(new Date(FIRST).toISOString())}) : t("The first ones are on their way."))
    + (offerNotify() ? " " + esc(t("Choose Notify me to get them on this device.")) : "");
  msg.append(w);
  bell();
}
function take(doc) {
  if (!ok(doc) || !doc.a.some(valid)) { if (!all.length) waiting(); return; }
  all = sorted(doc);
  isReh = !!doc.rehearsal; rehLabel = isReh && typeof doc.label === "string" ? doc.label : null;
  notifyNew(all);
  const newTop = all.reduce((m, e) => Math.max(m, e.n), 0);
  let hid = 0;
  try { hid = +(JSON.parse(ls.get(HID) || "{}").n) || 0; } catch (e) {}
  const said = +(ss.get(SAID) || 0);
  const fresh = newTop > top;
  top = Math.max(top, newTop);
  if (!all.length || newTop <= hid) { remove(); return; }
  const lead = Date.parse(all[0].t);
  turn = all.filter(e => lead - Date.parse(e.t) <= RECENT).slice(0, MAX_TURN);
  const was = box ? turn.findIndex(e => box.dataset.n === String(e.n)) : -1;
  if (!box) build();
  const ab = box.querySelector('[data-al="all"]'); if (ab) ab.hidden = false;      /* shown again after the notice before the first alert */
  if (isReh) box.querySelector(".tca-al-tag").title = rehLabel ? t("Rehearsal: replayed figures from {label}. Not 2026 results.", {label: rehLabel}) : t("Rehearsal: replayed figures. Not 2026 results.");
  box.classList.toggle("reh", isReh);
  pauseBtn.hidden = turn.length < 2;
  if (pauseBtn.hidden) paused = false;
  pauseBtn.textContent = paused ? t("Resume") : t("Pause");
  bell();
  show(fresh || was < 0 ? 0 : was, fresh && !!box.dataset.n);
  spin();
  /* a new alert is said once, politely, in this tab; nothing on the first look (the banner is there to be read). The list
     open over the page is never redrawn under the reader: the next look at it brings the new ones */
  if (said && newTop > said) {
    const nw = all.filter(e => e.n > said).sort((a, b) => b.n - a.n)[0];
    if (nw) say(words(nw));
  }
  if (newTop > said) ss.set(SAID, String(newTop));
}
function look() {
  clearTimeout(pollT);
  if (!inWindow()) { remove(); return; }
  /* not while hidden, unless this device asked for notifications: then the looks go on in the background (the browser may
     space them out, and a phone may put the app to sleep after a while) */
  if (D.visibilityState === "hidden" && !noting()) return;
  last = Date.now();
  getJSON(fileURL()).then(doc => css().then(() => take(doc)));
  pollT = setTimeout(look, EVERY);
}
function seen() {
  if (D.visibilityState === "hidden") { if (!noting()) clearTimeout(pollT); return; }
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
/* a shared alert: from the window's opening on, with no end (nothing is posted before it) */
function shared() {
  if (asked === null || (!forced && Date.now() < START)) return;
  css().then(loadAll).then(src => {
    const e = asked > 0 ? (src || []).find(x => x.n === asked) || all.find(x => x.n === asked) : null;
    openDlg("one", null, e || null);
  });
}
/* "Get alerts on this device" anywhere on a page (data-tca-notify), and a shared invitation (?notify=1, read once and taken
   out of the address) that opens Notify me; the browser's question waits for the reader's own press inside it */
const askedNotify = (() => {
  let q; try { q = new URLSearchParams(location.search); } catch (e) { return false; }
  if (!q.has("notify")) return false;
  try { const x = new URL(location.href); x.searchParams.delete("notify"); history.replaceState(history.state, "", x.pathname + x.search + x.hash); } catch (e) {}
  return true;
})();
D.addEventListener("click", e => {
  const b = e.target.closest && e.target.closest("[data-tca-notify]"); if (!b) return;
  e.preventDefault(); css(); notifyPress(b);      /* at once, inside the click: some browsers ask only from the press itself */
});
const askedFeed = (() => {
  let q; try { q = new URLSearchParams(location.search); } catch (e) { return null; }
  if (!q.has("feed")) return null;
  const v = (q.get("feed") || "").toUpperCase();
  try { const x = new URL(location.href); x.searchParams.delete("feed"); history.replaceState(history.state, "", x.pathname + x.search + x.hash); } catch (e) {}
  return /^[A-Z]{2}$/.test(v) ? v : "";
})();
function boot() {
  start(); shared();
  if (askedNotify && asked === null) css().then(() => openDlg("notify"));
  else if (askedFeed !== null && asked === null && (forced || Date.now() >= START)) { flt.st = askedFeed; css().then(() => openDlg("all")); }
}
if (D.readyState === "loading") D.addEventListener("DOMContentLoaded", boot, {once: true}); else boot();
