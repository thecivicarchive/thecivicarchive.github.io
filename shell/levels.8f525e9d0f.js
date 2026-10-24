/* The Civic Archive: Meet me where I am (John, 2026-10-19: "I like how that meet stuff looks and feels ... I actually think
   this would be good everywhere else"; his goal, that people "can shift focus to ensure that they have accessibility based on
   how they want to be met").
   Two settings, kept with the other reading settings in tca.a11y.v1 and written on <html> before the first frame (by the
   small script in the head of every page):
   - level, 1 Beginner, 2 Easy, 3 Medium (the site as it always was, and the start), 4 Hard, 5 Advanced, 6 Archivist;
   - focus, what the reader came for: none, ballot, reps, congress, state, results.
   The pages say what each level shows with four marks (the contract every page builder follows):
   - data-lv="N": shown only at level N or higher (the stylesheets hide it below);
   - data-lv-max="N": shown only at level N or lower (a short plain line standing in for something hidden there);
   - <details data-open-lv="N">: opened here when the level becomes N or higher, and when one is added to the page at that
     level; below N it is left as built; a reader's own toggle stands until the level changes again;
   - <button class="tca-lv-more" data-lv-more="N">: shown below level N; a click raises the level to N on every page.
   The facts never change between levels, only how much shows at once. This module draws the chooser (in Reading & access,
   on the Access page, and in the compact panel on pages with their own top bar) and the one card on a first visit, and does
   the opening and the raising. It sends nothing anywhere. */
import {t, tHTML, N_, choices, setLanguage, lang as LANG, tagLang} from "./i18n.d705614426.js";      /* the language layer: the chooser's words, and its language row */
const D = document, H = D.documentElement;
const ROOT = new URL("../", import.meta.url);
const store = {
  get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }
};
const esc = s => String(s).replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"})[c]);

export const LEVELS = [
  {n: N_("Beginner"), s: N_("Just the basics"), hint: N_("Plain words and the one thing to do: who, what and when. Tables of numbers and research tools are put away.")},
  {n: N_("Easy"), s: N_("A little more"), hint: N_("Adds the cards for each person and race, and one dated poll or vote line.")},
  {n: N_("Medium"), s: N_("The usual"), hint: N_("The site as it has always been: the tables and the details, each closed until you open it.")},
  {n: N_("Hard"), s: N_("Folds open"), hint: N_("Opens the folded parts of a page, where it has them: polls, money and ads, past results. A page with nothing folded looks as it does at Medium.")},
  {n: N_("Advanced"), s: N_("Research"), hint: N_("Opens every source and method, with the downloads of each figure.")},
  {n: N_("Archivist"), s: N_("All of it"), hint: N_("Adds, where a page has them, the records behind it: the data files it reads and when they were checked.")}
];
export const FOCUS = [["none", N_("A bit of everything")], ["ballot", N_("My ballot")], ["reps", N_("My representatives")], ["congress", N_("Congress")],
  ["state", N_("My state")], ["results", N_("Election Night results")]];
/* the states whose own pages are written (record, ballot), and where the ballot's chooser is: filled in by the build */
const PLACES = {"st":["ak","al","ar","az","ca","co","ct","de","fl","ga","hi","ia","id","il","in","ks","ky","la","ma","md","me","mi","mn","mo","ms","mt","nc","nd","ne","nh","nj","nm","nv","ny","oh","ok","or","pa","ri","sc","sd","tn","tx","ut","va","vt","wa","wi","wv","wy"],"ballot":["ak","al","ar","az","ca","co","ct","de","fl","ga","hi","ia","id","il","in","ks","ky","la","ma","md","me","mi","mn","mo","ms","mt","nc","nd","ne","nh","nj","nm","nv","ny","oh","ok","or","pa","ri","sc","sd","tn","tx","ut","va","vt","wa","wi","wv","wy"],"ballotRoot":"ballot/states/"};
/* where "Go to" leads for each focus, from the site's root; "state" and "ballot" lead to the reader's own state when this
   device knows it (the "state" the record pages keep) and that state's page is written; else to the chooser. The home
   page's own ballot link is worked out the same way, so both lead to one address. */
export function goFor(f) {
  const st = (store.get("state") || "").toLowerCase(), has = (k) => /^[a-z]{2}$/.test(st) && (PLACES[k] || []).includes(st);
  /* each with the whole sentence of its link, so a language can put the words in its own order */
  return {ballot: has("ballot") ? ["ballot/" + st + "/", N_("Go to your ballot")] : [PLACES.ballotRoot || "ballot/", N_("Go to On The Ballot")],
    reps: ["#officials", N_("Go to who represents you")], congress: ["us/", N_("Go to Plain Congress")],
    state: has("st") ? [st + "/", N_("Go to your state")] : ["rooms.html#states", N_("Go to the state legislatures")], results: ["night/", N_("Go to Election Night")]}[f] || null;
}
export function levelNow() { const v = +H.getAttribute("data-level"); return v >= 1 && v <= 6 ? v : 3; }
export function focusNow() { const v = H.getAttribute("data-focus"); return FOCUS.some(f => f[0] === v) ? v : "none"; }
export function levelWords(k, v) {
  if (k === "level") { const l = LEVELS[+v - 1]; return l ? t("Level: {level}", {level: t(l.n)}) : t("Level"); }
  const f = FOCUS.find(x => x[0] === v); return t("Here for: {focus}", {focus: f ? t(f[1]) : v});
}

/* ---------- folds that open with the level ---------- */
const built = new WeakMap();
function fold(d, lv, changed) {
  if (!built.has(d)) built.set(d, d.open);
  const n = +d.getAttribute("data-open-lv"); if (!(n >= 1 && n <= 6)) return;
  const want = lv >= n ? true : (changed ? built.get(d) : d.open);
  if (d.open !== want) d.open = want;
}
function folds(scope, lv, changed) {
  if (scope.nodeType !== 1) return;
  if (scope.matches("details[data-open-lv]")) fold(scope, lv, changed);
  if (scope.firstElementChild) for (const d of scope.querySelectorAll("details[data-open-lv]")) fold(d, lv, changed);
}

/* ---------- the chooser: how much, and what for (and, where asked, the four main reading choices) ---------- */
const btn = (html, on, attrs = "") => `<button type="button" aria-pressed="${on ? "true" : "false"}"${attrs}>${html}</button>`;
let uid = 0;
export function chooser(box, {apply, axes, reading = false, access = false}) {
  const id = "tca-mm" + (++uid);
  box.classList.add("tca-mm", "tca-lvx");
  /* drawn once; a change of setting (here or anywhere) updates it in place, so a slider being dragged is never replaced */
  const sizes = [["100", N_("Standard text")], ["115", N_("Larger text")], ["130", N_("Larger still")], ["150", N_("Largest text")]];
  /* the languages a reader can choose (the language layer), each written in its own language; shown once there is a choice */
  const langs = choices();
  const langRow = langs.length > 1 ? `<div class="mm-chips" role="group" aria-label="${esc(t("Language"))}">${langs.map(l => btn(esc(l.name), l.code === LANG, ` data-lang-set="${esc(l.code)}" lang="${esc(l.html)}"`)).join("")}</div>` : "";
  tagLang(box);
  box.innerHTML = `<div class="mm-row"><p class="mm-lab" id="${id}-l">${esc(t("How much do you want to see?"))}</p>
<div class="mm-levels" role="group" aria-labelledby="${id}-l">${LEVELS.map((l, i) => btn(`${esc(t(l.n))}<span>${esc(t(l.s))}</span>`, false, ` data-lv-set="${i + 1}"`)).join("")}</div>
<input type="range" min="1" max="6" step="1" value="3" data-lv-range aria-label="${esc(t("Level, from Beginner to Archivist"))}">
<p class="mm-hint" data-lv-hint></p></div>
<div class="mm-row"><p class="mm-lab" id="${id}-f">${esc(t("What are you here for?"))}</p>
<div class="mm-chips" role="group" aria-labelledby="${id}-f">${FOCUS.map(([k, w]) => btn(esc(t(w)), false, ` data-focus-set="${k}"`)).join("")}</div>
<p class="mm-go" data-lv-go hidden></p></div>` + (reading || langRow ? `<div class="mm-row"><p class="mm-lab">${esc(t("How should it read?"))}</p>${langRow}` + (reading ? `
<div class="mm-chips" role="group" aria-label="${esc(t("Text size"))}">${sizes.map(([v, w]) => btn(esc(t(w)), false, ` data-ax="scale" data-v="${v}"`)).join("")}</div>
<div class="mm-chips" role="group" aria-label="${esc(t("Typeface, contrast and motion"))}">${btn(esc(t("Easier-to-read typeface")), false, ' data-ax="face" data-v="hyperlegible" data-off="standard"')}${btn(esc(t("Higher contrast")), false, ' data-ax="contrast" data-v="high" data-off="standard"')}${btn(esc(t("Calm motion")), false, ' data-ax="calm" data-v="on" data-off="off"')}</div>
${access ? `<p class="mm-small">${tHTML("These are the site\u2019s own reading settings, so they carry from page to page. <0>Reading and access</0> has the rest.", {0: w => `<a href="${esc(new URL("access/", ROOT).href)}">${w}</a>`})}</p>` : ""}` : "") + `</div>` : "")
    + `<ul class="mm-promise"><li>${esc(t("Same facts at every level"))}</li><li>${esc(t("\u201cShow more\u201d always works"))}</li><li>${esc(t("Kept on this device only"))}</li></ul>`;
  const range = box.querySelector("[data-lv-range]"), hint = box.querySelector("[data-lv-hint]"), goP = box.querySelector("[data-lv-go]");
  function draw() {
    const a = axes(), lv = levelNow(), f = focusNow(), go = goFor(f), L = LEVELS[lv - 1];
    for (const b of box.querySelectorAll("[data-lv-set]")) b.setAttribute("aria-pressed", +b.dataset.lvSet === lv ? "true" : "false");
    for (const b of box.querySelectorAll("[data-focus-set]")) b.setAttribute("aria-pressed", b.dataset.focusSet === f ? "true" : "false");
    for (const b of box.querySelectorAll("[data-ax]")) b.setAttribute("aria-pressed", (a[b.dataset.ax] || (b.dataset.ax === "scale" ? "100" : "")) === b.dataset.v ? "true" : "false");
    if (+range.value !== lv) range.value = String(lv);
    range.setAttribute("aria-valuetext", t(L.n));
    hint.innerHTML = tHTML("<0>{level}:</0> {hint}", {level: t(L.n), hint: t(L.hint), 0: w => `<b>${w}</b>`});
    goP.hidden = !go;
    goP.innerHTML = go ? `<a href="${esc(new URL(go[0], ROOT).href)}">${esc(t(go[1]))}</a>` : "";
  }
  box.addEventListener("click", e => {
    const b = e.target.closest("button"); if (!b || !box.contains(b)) return;
    if (b.dataset.langSet) { if (b.dataset.langSet !== LANG) setLanguage(b.dataset.langSet); }
    else if (b.dataset.lvSet) apply({level: b.dataset.lvSet});
    else if (b.dataset.focusSet) apply({focus: b.dataset.focusSet});
    else if (b.dataset.ax) { const a = axes(), k = b.dataset.ax; apply({[k]: k === "scale" ? b.dataset.v : (a[k] === b.dataset.v ? b.dataset.off : b.dataset.v)}); }
  });
  box.addEventListener("input", e => { if (e.target.matches("[data-lv-range]")) apply({level: String(e.target.value)}); });
  H.addEventListener("tca:axes", draw);
  draw();
  return draw;
}

/* ---------- the one card, on a first visit ---------- */
const CARD = "tca.levels.card.v1";
const APPKEY = "tca.app.v1:" + ROOT.pathname;
const json = k => { try { const v = JSON.parse(store.get(k) || "null"); return v && typeof v === "object" ? v : {}; } catch (e) { return {}; } };
const rel = () => { const p = location.pathname, r = ROOT.pathname; return p.startsWith(r) ? decodeURIComponent(p.slice(r.length)) : ""; };
/* pages that carry the chooser themselves, and the places to sit, never show the card */
const NOCARD = /^(access\/|meet\/|app\/|night\/sky\/|ballot\/polling-place\/|reading-room\/|ballot\/kept\/|cabin\.html)/;
function appNoteThisVisit() {
  const s = json(APPKEY);
  if (s.note === 1 && s.nv === s.n) return true;      // the app's note was shown in this visit
  if (!(s.n >= 2) || s.note) return false;
  const app = window.__tcaApp;      // its note is due: it comes in this visit, so the card waits for another
  try { return app ? !app.standalone() && !s.inst && app.canInstall() : true; } catch (e) { return true; }
}
function busy() {
  if (H.hasAttribute("data-arrive")) return true;
  for (const el of D.querySelectorAll('dialog[open],[aria-modal="true"],.tca-sv,.tca-nv,.tca-panel:not([hidden]):not(.inline),.tca-rp:not([hidden]),.tca-mmpanel:not([hidden]),.tca-appnote,.tca-lo,#tca-app:not([hidden]),[role="dialog"]:not([hidden])'))
    if (el.getClientRects().length && getComputedStyle(el).visibility !== "hidden") return true;
  /* Election Day's "polls are still open" notice comes first: the card waits while one is on the screen */
  for (const el of D.querySelectorAll(".pollsopen,#nh-open,.nh-notice")) {
    const r = el.getBoundingClientRect();
    if (r.height && r.bottom > 0 && r.top < innerHeight) return true;
  }
  return false;
}
/* a browser that keeps nothing (storage blocked) would show the card on every page: there it is never shown */
let keeps = null;
function keepsThings() {
  if (keeps === null) {
    const k = "tca.levels.t";
    try { localStorage.setItem(k, "1"); keeps = localStorage.getItem(k) === "1"; localStorage.removeItem(k); } catch (e) { keeps = false; }
  }
  return keeps;
}
let card = null, cardT = 0;
export function firstCard({apply, motionOn, say}) {
  if (!keepsThings() || json(CARD).shown || NOCARD.test(rel())) return;
  let tries = 0;
  const iv = setInterval(() => {
    if (++tries > 60 || json(CARD).shown) { clearInterval(iv); return; }
    if (D.visibilityState !== "visible" || busy() || appNoteThisVisit()) return;
    clearInterval(iv); show();
  }, 1500);
  function show() {
    const lv = levelNow();
    card = D.createElement("aside");
    card.className = "tca-lvcard tca-lvx" + (motionOn() ? " rise" : "");
    card.setAttribute("aria-labelledby", "tca-lvcard-h");
    tagLang(card);
    card.innerHTML = `<div class="hd"><p id="tca-lvcard-h"><b>${esc(t("How much do you want to see?"))}</b> <span>${esc(t("Pick a level. Change it any time under Reading & access."))}</span></p>
<button type="button" class="no" data-no>${esc(t("Not now"))}</button></div>
<div class="tca-lvgrid" role="group" aria-labelledby="tca-lvcard-h">${LEVELS.map((l, i) => btn(`${esc(t(l.n))}<small>${esc(t(l.s))}</small>`, lv === i + 1, ` data-lv-set="${i + 1}"`)).join("")}</div>`;
    card.addEventListener("click", e => {
      const b = e.target.closest("button"); if (!b) return;
      if (b.dataset.lvSet) { apply({level: b.dataset.lvSet}); close("level"); }
      else if (b.hasAttribute("data-no")) close("no");
    });
    card.addEventListener("keydown", e => { if (e.key === "Escape") { e.preventDefault(); close("no"); } });
    D.body.append(card);
    const s = json(APPKEY);
    store.set(CARD, JSON.stringify({shown: 1, n: s.n || 1, at: Date.now()}));      // shown: never again, on any page, closed or not
    cardT = setInterval(() => { if (card) { card.hidden = busy(); clear(); } }, 700);
    clear();
  }
  function close(how) {
    const s = json(CARD); s.done = how; store.set(CARD, JSON.stringify(s));
    clearInterval(cardT);
    const had = card && card.contains(D.activeElement);
    if (card) { card.remove(); card = null; }
    if (had) { const m = D.querySelector('[aria-controls="tca-access"],[aria-controls="tca-meet"]'); if (m) try { m.focus({preventScroll: true}); } catch (e) {} }
    if (how === "no" && say) say(t("Closed. Reading and access, at the top, has the levels whenever you want them."));
  }
}
/* it never covers the companion or its Help button */
function clear() {
  if (!card || card.hidden) return;
  card.style.removeProperty("bottom");
  const n = card.getBoundingClientRect();
  for (const el of D.querySelectorAll(".tca-dock,.tca-bubble,.tca-mmbtn.float:not(.away)")) {
    const r = el.getBoundingClientRect();
    if (!r.width || r.left >= n.right || r.right <= n.left || r.top >= n.bottom || r.bottom <= n.top) continue;
    card.style.bottom = Math.max(8, Math.round(innerHeight - r.top + 8)) + "px";
  }
}

/* the level an element needs to be shown (its own mark and every enclosing one); 0 when raising the level would not show it */
function needs(el) {
  let n = 0;
  for (let x = el; x && x.nodeType === 1; x = x.parentElement) {
    const v = +x.getAttribute("data-lv"); if (v >= 1 && v <= 6) n = Math.max(n, v);
    const m = +x.getAttribute("data-lv-max"); if (m >= 1 && m <= 6 && m < Math.max(n, levelNow())) return 0;
  }
  return n;
}

/* ---------- the wiring every page shares ---------- */
export function startLevels({apply, say}) {
  /* the preview page kept its own choice (tca.meet.v1) before these were the site's settings: carried over once */
  try {
    const old = json("tca.meet.v1"), a = json("tca.a11y.v1");
    if (old.level && !old.moved) {
      const next = {};
      if (!a.level && old.level >= 1 && old.level <= 6) next.level = String(old.level);
      if (!a.focus && FOCUS.some(f => f[0] === old.focus)) next.focus = old.focus;
      if (Object.keys(next).length) apply(next, false);
      old.moved = 1; store.set("tca.meet.v1", JSON.stringify(old));
    }
  } catch (e) {}
  /* "Show more": up to that level, everywhere; the focus goes to what has just appeared after the button (or to the part
     the button names, data-lv-target="<id>"). Only the button itself counts: a tap beside it, in its row, does nothing. */
  D.addEventListener("click", e => {
    const b = e.target.closest && e.target.closest("button[data-lv-more],.tca-lv-more[data-lv-more]"); if (!b) return;
    const n = +b.getAttribute("data-lv-more"); if (!(n >= 2 && n <= 6)) return;
    e.preventDefault();
    if (levelNow() >= n) return;
    const near = [], hid = [...D.querySelectorAll("[data-lv]")].filter(x => !x.getClientRects().length);
    for (let x = b.nextElementSibling; x; x = x.nextElementSibling) near.push(x);
    for (let x = b.previousElementSibling; x; x = x.previousElementSibling) near.push(x);
    apply({level: String(n)}, t("Showing more."));
    /* the part the button names; else the first part that has just appeared after it (its heading, where it has one); else
       what stands beside the button */
    const after = x => !!(b.compareDocumentPosition(x) & Node.DOCUMENT_POSITION_FOLLOWING);
    const named = b.getAttribute("data-lv-target") && D.getElementById(b.getAttribute("data-lv-target"));
    const shown = (named && named.getClientRects().length) ? named : hid.find(x => after(x) && x.getClientRects().length);
    let to = shown ? (shown.querySelector("h2,h3,h4") || shown) : near.find(x => x.getClientRects().length && !x.matches("script,style,template"));
    if (!to && b.parentElement && b.parentElement.getClientRects().length) to = b.parentElement;
    if (to) {
      if (!to.matches("a[href],button,input,select,textarea,summary,[tabindex]")) { to.setAttribute("tabindex", "-1"); to.addEventListener("blur", () => to.removeAttribute("tabindex"), {once: true}); }
      try { to.focus({preventScroll: true}); } catch (x) {}
    }
  });
  /* a link to a part of this page that the level puts away raises the level just enough to show it, then goes there as
     usual (the top bars' Map, Leaderboard and the like). Routes that are not the id of an element are left to the page. */
  D.addEventListener("click", e => {
    if (e.defaultPrevented || e.button || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    const a = e.target.closest && e.target.closest("a[href]"); if (!a) return;
    const href = a.getAttribute("href") || ""; if (href.length < 2) return;
    let u; try { u = new URL(a.href, location.href); } catch (x) { return; }
    if (!u.hash || u.origin !== location.origin || u.pathname !== location.pathname) return;
    let id; try { id = decodeURIComponent(u.hash.slice(1)); } catch (x) { return; }
    const el = /^[\w-]+$/.test(id) ? D.getElementById(id) : null; if (!el) return;
    const n = needs(el), now = levelNow();
    if (n > now) apply({level: String(n)}, t("Showing more."));
  }, true);
  /* folds: as the page is drawn, as routes add to it, and whenever the level changes */
  let lv = levelNow();
  folds(D.body, lv, false);
  new MutationObserver(ms => {
    const now = levelNow();
    for (const m of ms) for (const nd of m.addedNodes) if (nd.nodeType === 1) folds(nd, now, false);
  }).observe(D.body, {childList: true, subtree: true});
  H.addEventListener("tca:axes", () => { const now = levelNow(); if (now !== lv) { lv = now; folds(D.body, now, true); } });
  const css = D.createElement("link");
  css.rel = "stylesheet"; css.href = new URL("./levels.df00c9b173.css", import.meta.url).href;
  D.head.append(css);
}
