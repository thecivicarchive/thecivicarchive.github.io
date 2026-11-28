/* The Civic Archive: the language layer (2026-10-23; memory translations; the plan in research/translations_groundwork_2026-10-20.md).
   The site is written in English, and English readers fetch nothing from here: every message stays in the code as its own
   default. A reader who chooses another language (the "How should it read?" row of Meet me where I am; never switched
   by itself: a phone or browser set to an offered language is offered it once, in a small note) gets that language's
   checked translations, fetched from shell/lang/ and kept by the app's worker:
   - t("English", {values}) and tHTML("A <0>link</0> inside", {0: s => `<a ...>${s}</a>`}) give a message in the reader's
     language, or the English where it is not translated yet. Values fill {name}; plurals and choices are written
     {n, plural, one {# page} other {# pages}} and {k, select, a {...} other {...}}; numbers and dates go through Intl.
   - the shell's builders mark the words they write (data-t, data-tv, data-ta; i18n_mark.py says how), and translate()
     puts the reader's language in place, reusing the page's own elements: a translation can never add HTML or an address.
   - the page waits, hidden, until its words are in place: at most 2.5 seconds, then it shows whatever has arrived. The
     head script hides it only for a reader with another language, and shows it again by itself if nothing here runs.
   - with another language on: a line under the top bar says who translated it and leads back to English; Help's plain
     answers say the state's election office has the final word.
   The language is kept with the other reading settings (language in tca.a11y.v1, data-language on <html>), never counted,
   and never reset by "Put everything back" or a preset. Names and the words printed on a ballot are never translated;
   an office's title is translated with its official English title beside it (John, 2026-10-20). Nothing is sent
   anywhere. */
const D = document, H = D.documentElement;
const LANGS = [{"code":"en","name":"English","html":"en","locale":"en-US","dir":"ltr","status":"offered"}];      /* written by the build from i18n/languages.json: the languages this copy can show */
const FILES = {};      /* written by the build: each language's checked translations, by bundle, named by a hash of their contents */
const KEY = "tca.a11y.v1", OFFER = "tca.lang.offer.v1", TEST = "tca.i18n.test", SCROLL = "tca.i18n.scroll", WAIT = 2500;
const store = {get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }, set(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }};
const saved = () => { try { const s = JSON.parse(store.get(KEY) || "null"); return s && typeof s === "object" ? s : {}; } catch (e) { return {}; } };
const esc = s => String(s).replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"})[c]);
const EN = LANGS.find(l => l.code === "en") || {code: "en", name: "English", html: "en", locale: "en-US", dir: "ltr", status: "offered"};
/* the reader's language: from <html> (the head script reads the setting), or the setting itself on a page without one */
export const L = (() => { const c = H.getAttribute("data-language") || saved().language; return LANGS.find(l => l.code === c) || EN; })();
export const lang = L.code;
const isEn = lang === "en";
export const N_ = s => s;      /* marks a message written in a table, to be passed to t() where it is shown */

/* ---------- the key: FNV-1a over the message's UTF-16 code units, 7 base-36 characters (i18n_mark.key is the same) ---------- */
export function key(msg, ctx) {
  const s = ctx ? ctx + "\u0004" + msg : msg;
  let h = 0x811c9dc5;
  for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 0x01000193) >>> 0; }
  return h.toString(36).padStart(7, "0");
}

/* ---------- the translations: one map, filled bundle by bundle ---------- */
const dict = new Map(), have = new Set(), pending = {};
export const misses = new Set();      /* for testing: the messages shown in English because no translation was there */
const fileURL = (b, hashed) => { const f = hashed ? (FILES[lang] || {})[b] : `${lang}.${b}.json`; return f ? new URL("lang/" + f, import.meta.url).href : ""; };
const getJSON = u => u ? fetch(u, {credentials: "same-origin"}).then(r => (r.ok ? r.json() : null)).catch(() => null) : Promise.resolve(null);
export function need(b) {
  if (isEn || have.has(b)) return Promise.resolve(true);
  if (!pending[b]) {
    const early = window.__tcaLP && window.__tcaLP[b];      /* the head script asked for it before the page was drawn */
    pending[b] = (early || getJSON(fileURL(b, true))).then(j => j || getJSON(fileURL(b, false))).then(j => {
      if (j && typeof j === "object") for (const k in j) if (typeof j[k] === "string") dict.set(k, j[k]);
      have.add(b);
      return !!j;
    });
  }
  return pending[b];
}
export const has = b => isEn || have.has(b);
function lookup(msg, ctx) {
  if (isEn) return msg;
  const tr = dict.get(key(msg, ctx));
  if (tr == null) { misses.add(msg); return msg; }
  return tr;
}

/* ---------- numbers, dates, lists, plurals ---------- */
const NF = {}, PR = {};
export function num(n, o) { const k = JSON.stringify(o || {}); try { return (NF[k] || (NF[k] = new Intl.NumberFormat(L.locale, o))).format(n); } catch (e) { return String(n); } }
/* a date with no time ("2026-11-03") is the same day everywhere: it is read and written in UTC */
export function date(d, o = {dateStyle: "long"}) {
  let x = d;
  if (typeof d === "string") { const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(d); x = m ? new Date(Date.UTC(+m[1], +m[2] - 1, +m[3])) : new Date(d); if (m) o = {timeZone: "UTC", ...o}; }
  try { return new Intl.DateTimeFormat(L.locale, o).format(x); } catch (e) { return String(d); }
}
export function list(items, type = "conjunction") { try { return new Intl.ListFormat(L.locale, {style: "long", type}).format(items); } catch (e) { return items.join(", "); } }
function rule(n, ord) { const k = ord ? "o" : "c"; try { return (PR[k] || (PR[k] = new Intl.PluralRules(L.locale, {type: ord ? "ordinal" : "cardinal"}))).select(n); } catch (e) { return n === 1 ? "one" : "other"; } }

/* ---------- messages: the subset of ICU MessageFormat the builders and the check read too ---------- */
const AST = new Map();
function parse(msg) {
  let r = AST.get(msg);
  if (r) return r;
  let i = 0;
  const ws = () => { while (i < msg.length && /\s/.test(msg[i])) i++; };
  const word = () => { const m = /^[^\s,{}]+/.exec(msg.slice(i)); if (!m) throw 0; i += m[0].length; return m[0]; };
  function nodes(pl) {
    const out = []; let buf = "";
    while (i < msg.length) {
      const c = msg[i];
      if (c === "{") { if (buf) { out.push(buf); buf = ""; } out.push(arg(pl)); continue; }
      if (c === "}") break;
      if (c === "#" && pl) { if (buf) { out.push(buf); buf = ""; } out.push({h: 1}); i++; continue; }
      buf += c; i++;
    }
    if (buf) out.push(buf);
    return out;
  }
  function arg(pl) {
    i++; ws(); const v = word(); ws();
    if (msg[i] === "}") { i++; return {v}; }
    if (msg[i] !== ",") throw 0;
    i++; ws(); const k = word(); ws();
    if (msg[i] === "}") { i++; return {v}; }
    if (msg[i] !== ",") throw 0;
    i++; const c = {};
    for (;;) {
      ws(); if (msg[i] === "}") { i++; break; }
      const s = word(); ws(); if (msg[i] !== "{") throw 0;
      i++; c[s] = nodes(pl || k === "plural" || k === "selectordinal"); if (msg[i] !== "}") throw 0; i++;
    }
    return {v, k, c};
  }
  try { r = nodes(false); if (i < msg.length) r = [msg]; } catch (e) { r = [msg]; }
  AST.set(msg, r);
  return r;
}
/* the message with its choices made: text, and each value kept apart ({val}) to be escaped or not by the caller */
function choose(ns, vals, out, n) {
  for (const x of ns) {
    if (typeof x === "string") out.push(x);
    else if (x.h) out.push(num(n));
    else if (!x.k) out.push({val: vals[x.v]});
    else if (x.k === "plural" || x.k === "selectordinal") { const v = Number(vals[x.v]); choose(x.c["=" + v] || x.c[rule(v, x.k === "selectordinal")] || x.c.other || [], vals, out, v); }
    else choose(x.c[String(vals[x.v])] || x.c.other || [], vals, out, n);
  }
  return out;
}
/* a value as text: a number through Intl; raw(html) only inside tHTML */
export const raw = h => ({html: String(h)});
function valText(v, html) {
  if (v && typeof v === "object" && "html" in v) return html ? v.html : v.html.replace(/<[^>]*>/g, "");
  const s = typeof v === "number" ? num(v) : v == null ? "" : String(v);
  return html ? esc(s) : s;
}
const TAG = /<(\/?)(\d+)(\/?)>/g;
export function t(msg, vals = {}, ctx) {
  return choose(parse(lookup(msg, ctx)), vals, []).map(p => (typeof p === "string" ? p.replace(TAG, "") : valText(p.val, false))).join("");
}
/* HTML: the words escaped, values escaped (unless raw()), and each numbered tag given by the caller: a function of the
   HTML inside it, or a string for <n/>. A translation whose tags do not fit the English falls back to the English. */
export function tHTML(msg, vals = {}, ctx) {
  const tr = lookup(msg, ctx);
  return htmlOf(tr, vals) ?? htmlOf(msg, vals) ?? esc(msg);
}
function htmlOf(msg, vals) {
  const stack = [{i: -1, out: ""}];
  for (const p of choose(parse(msg), vals, [])) {
    if (typeof p !== "string") { stack[stack.length - 1].out += valText(p.val, true); continue; }
    let last = 0;
    for (const m of p.matchAll(TAG)) {
      stack[stack.length - 1].out += esc(p.slice(last, m.index)); last = m.index + m[0].length;
      const i = +m[2], f = vals[i];
      if (m[3]) { stack[stack.length - 1].out += typeof f === "function" ? f("") : (f == null ? "" : String(f)); continue; }
      if (!m[1]) { stack.push({i, out: ""}); continue; }
      const top = stack.pop();
      if (!top || top.i !== i || !stack.length) return null;
      stack[stack.length - 1].out += typeof f === "function" ? f(top.out) : top.out;
    }
    stack[stack.length - 1].out += esc(p.slice(last));
  }
  return stack.length === 1 ? stack[0].out : null;
}

/* ---------- the words the builders marked: put in place, reusing the page's own elements ---------- */
const IGNORE = new Set(["script", "style", "template", "noscript"]);
const TEXTLESS = new Set([...IGNORE, "svg", "math"]);
const OPAQUE = new Set(["br", "img", "input", "svg", "select", "textarea", "canvas", "time", "data", "code", "math", "video", "audio",
  "iframe", "object", "picture", "wbr", "meter", "progress"]);
function letters(n) {
  for (const c of n.childNodes) {
    if (c.nodeType === 3 && /\p{L}/u.test(c.data)) return true;
    if (c.nodeType === 1 && !TEXTLESS.has(c.localName) && letters(c)) return true;
  }
  return false;
}
const opaque = e => OPAQUE.has(e.localName) || e.getAttribute("translate") === "no" || e.hasAttribute("data-t") || e.classList.contains("tca-ico") || !letters(e);
/* the numbered pieces of a marked element, in the order the builder numbered them */
function slots(el) {
  const out = [];
  (function rec(n) { for (const c of n.childNodes) if (c.nodeType === 1 && !IGNORE.has(c.localName)) { out.push(c); if (!opaque(c)) rec(c); } })(el);
  return out;
}
/* a value from the page: a figure written the English way ("8,467") is written the reader's way */
function figure(v) { if (typeof v === "string" && /^\d{1,3}(,\d{3})+(\.\d+)?$/.test(v)) return num(Number(v.replace(/,/g, ""))); return valText(v, false); }
/* a date or a number kept whole is written the reader's way; a <time> may say how in data-tf (Intl's options as JSON: the
   ballot pages' {"weekday":"long","month":"long","day":"numeric"}), else the whole date */
function redo(slot) {
  let tf;
  try { tf = JSON.parse(slot.getAttribute("data-tf") || "null"); } catch (e) { tf = null; }
  if (slot.localName === "time" && /^\d{4}-\d{2}-\d{2}$/.test(slot.getAttribute("datetime") || "")) slot.textContent = date(slot.getAttribute("datetime"), tf && typeof tf === "object" ? tf : undefined);
  else if (slot.localName === "data" && slot.hasAttribute("value") && isFinite(+slot.getAttribute("value"))) slot.textContent = num(+slot.getAttribute("value"));
}
function unwrapWords(el) { for (const w of [...el.querySelectorAll("span.w")]) w.replaceWith(D.createTextNode(w.textContent)); el.normalize(); }
function splitWords(el) {
  let i = 0;
  (function rec(n) {
    for (const c of [...n.childNodes]) {
      if (c.nodeType === 1) { rec(c); continue; }
      if (c.nodeType !== 3) continue;
      const frag = D.createDocumentFragment();
      for (const part of c.data.split(/(\s+)/)) {
        if (!part) continue;
        if (/^\s+$/.test(part)) { frag.append(part); continue; }
        const s = D.createElement("span"); s.className = "w"; s.style.setProperty("--i", String(i++)); s.textContent = part; frag.append(s);
      }
      c.replaceWith(frag);
    }
  })(el);
}
function rebuild(el, tr, vals) {
  if (el.hasAttribute("data-t-words")) unwrapWords(el);
  const S = slots(el), pieces = choose(parse(tr), vals, []);
  /* the tags must fit the English: every piece once, a piece kept whole as <n/>, the rest opened and closed in order */
  const toks = [];
  for (const p of pieces) {
    if (typeof p !== "string") { toks.push({v: figure(p.val)}); continue; }
    let last = 0;
    for (const m of p.matchAll(TAG)) { if (m.index > last) toks.push({s: p.slice(last, m.index)}); toks.push({i: +m[2], close: !!m[1], self: !!m[3]}); last = m.index + m[0].length; }
    if (last < p.length) toks.push({s: p.slice(last)});
  }
  const seen = new Set(), open = [];
  for (const k of toks) {
    if (!("i" in k)) continue;
    const s = S[k.i]; if (!s) return false;
    if (k.self) { if (!opaque(s) || seen.has(k.i)) return false; seen.add(k.i); }
    else if (!k.close) { if (opaque(s) || seen.has(k.i)) return false; seen.add(k.i); open.push(k.i); }
    else if (open.pop() !== k.i) return false;
  }
  if (open.length || seen.size !== S.length) return false;
  /* the elements are kept (their listeners, addresses and styles); only their words change */
  for (const n of [el, ...S.filter(s => !opaque(s))]) while (n.firstChild) n.firstChild.remove();
  const stack = [el];
  for (const k of toks) {
    const top = stack[stack.length - 1];
    if ("s" in k) top.append(k.s);
    else if ("v" in k) top.append(k.v);
    else if (k.self) { redo(S[k.i]); top.append(S[k.i]); }
    else if (!k.close) { top.append(S[k.i]); stack.push(S[k.i]); }
    else stack.pop();
  }
  if (el.hasAttribute("data-t-words")) splitWords(el);
  return true;
}
const PAGE_FULL = H.hasAttribute("data-i18n-full");
let missed = 0;
function translateEl(el) {
  const k = el.getAttribute("data-t"), tr = dict.get(k);
  let vals = {};
  try { vals = JSON.parse(el.getAttribute("data-tv") || "{}"); } catch (e) {}
  if (tr == null) { missed++; el.setAttribute("data-t-miss", ""); return; }
  if (el.localName === "title") {
    if (!H.dataset.titleEn) H.dataset.titleEn = D.title;      /* the visit counter keeps the English title */
    D.title = choose(parse(tr), vals, []).map(p => (typeof p === "string" ? p.replace(TAG, "") : figure(p.val))).join("");
  } else if (!rebuild(el, tr, vals)) { missed++; el.setAttribute("data-t-miss", ""); return; }
  el.removeAttribute("data-t-miss");
  el.setAttribute("data-t-done", "");
  if (!PAGE_FULL) el.lang = L.html;
}
export function translate(root = D) {
  if (isEn) return;
  for (const el of root.querySelectorAll("[data-t]:not([data-t-done])")) translateEl(el);
  for (const el of root.querySelectorAll("[data-ta]:not([data-ta-done])")) {
    let all = true;
    for (const pair of el.getAttribute("data-ta").split(";")) {
      const [a, k] = pair.split(":"), tr = dict.get(k);
      if (a && tr != null) el.setAttribute(a, tr); else all = false;
    }
    if (all) el.setAttribute("data-ta-done", "");
  }
}
/* a part the shell draws itself (a panel, a card, a veil) says its language when the page around it is English */
export function tagLang(el) { if (el && !isEn && H.lang !== L.html) el.lang = L.html; return el; }

/* ---------- the languages a reader can choose, and choosing one ---------- */
export function choices() {
  const test = store.get(TEST) === "1";
  return LANGS.filter(l => l.status === "offered" || l.code === lang || (test && l.status === "test"));
}
/* kept with the reading settings; the page is drawn again in the new language, at the same place */
export function setLanguage(code) {
  const s = saved(); s.language = code; store.set(KEY, JSON.stringify(s));
  try { sessionStorage.setItem(SCROLL, JSON.stringify({p: location.pathname + location.search, y: Math.round(scrollY)})); } catch (e) {}
  location.reload();
}

/* ---------- the line under the top bar, and Help's note ---------- */
let style = null;
function css() {
  if (style) return;
  style = D.createElement("style");
  style.textContent = ".tca-xl{margin:0;padding:6px max(16px,env(safe-area-inset-left));text-align:center;font:500 .875rem/1.45 var(--font-ui,system-ui,-apple-system,'Segoe UI',sans-serif);background:var(--draft-bg,#F1E9D8);color:var(--draft-ink,#3A2E1C);overflow-wrap:anywhere}"
    + ".tca-xl button{font:inherit;font-weight:700;color:inherit;background:none;border:0;margin:0;padding:0 4px;min-height:32px;text-decoration:underline;text-underline-offset:2px;cursor:pointer}"
    + ".tca-xl button:focus-visible,.tca-lo button:focus-visible{outline:3px solid #A8762E;outline-offset:2px}"
    + ".tca-lo{position:fixed;z-index:58;top:calc(var(--bar-bottom,64px) + 10px);left:50%;transform:translateX(-50%);display:flex;align-items:center;gap:6px;max-width:calc(100vw - 24px);padding:6px;border-radius:999px;"
    + "background:#FBF7EE;color:#1E2A2C;border:1px solid rgba(30,42,44,.22);box-shadow:0 8px 28px rgba(0,0,0,.18);font:650 1rem/1.25 var(--font-ui,system-ui,-apple-system,'Segoe UI',sans-serif)}"
    + ".tca-lo button{min-height:44px;border-radius:999px;cursor:pointer;font:inherit;margin:0}"
    + ".tca-lo .go{padding:0 18px;background:#2F6B5E;color:#fff;border:0}"
    + ".tca-lo .no{width:44px;flex:none;background:transparent;border:1px solid rgba(30,42,44,.3);color:inherit;font-size:1.25rem}"
    + ":root:is([data-contrast=\"dark\"],[data-theme=\"dark\"]) .tca-lo{background:#1B2326;color:#EFE8DA;border-color:rgba(255,255,255,.25)}"
    + ":root:is([data-contrast=\"dark\"],[data-theme=\"dark\"]) .tca-lo .no{border-color:rgba(255,255,255,.35)}"
    + "@media (forced-colors:active){.tca-lo,.tca-lo button{border:2px solid ButtonText;background:ButtonFace;color:ButtonText}}";
  D.head.append(style);
}
function label() {
  if (isEn || D.querySelector(".tca-xl") || QUIET.test(location.pathname)) return;      /* the places to sit and the kept ballot keep their own screens */
  css();
  const p = D.createElement("p");
  p.className = "tca-xl"; p.lang = L.html; p.setAttribute("data-tca-xl", "");
  const words = L.label || t("Translated by Claude, an AI model. Not yet reviewed by a person.");
  p.innerHTML = `<span>${esc(words)}</span> <button type="button" lang="${esc(dict.has(key("View in English")) ? L.html : "en")}">${esc(t("View in English"))}</button>`;
  p.querySelector("button").addEventListener("click", () => setLanguage("en"));
  const bar = D.querySelector("header.tca-top") || D.querySelector("header.top") || D.querySelector("body > header");
  if (bar) bar.after(p); else D.body.prepend(p);
}
/* Help's plain answers, on the pages that carry them, begin with what a translation is and is not */
function helpNote() {
  if (isEn) return;
  for (const faq of D.querySelectorAll(".tca-faq")) {
    if (faq.querySelector("[data-tca-xl-faq]")) continue;
    const d = D.createElement("details");
    d.setAttribute("data-tca-xl-faq", ""); tagLang(d);
    d.innerHTML = `<summary>${esc(t("About this translation"))}</summary><div class="a"><p>${esc(t("This page was translated by Claude, an AI model, and no person has checked the translation yet. Names and the words printed on your ballot are kept as the record gives them, in English; an office's title is translated, with its official English title beside it. Where a translation and an official record differ, the record is right, and your state's election office has the final word on voting."))}</p></div>`;
    faq.prepend(d);
  }
}

/* ---------- the offer, once, to a reader whose phone or browser is set to a language the site offers ---------- */
const QUIET = /\/(night\/sky|ballot\/polling-place|reading-room|ballot\/kept)\/|\/cabin\.html$/;
function fromBrowser() {
  for (const tag of (navigator.languages && navigator.languages.length ? navigator.languages : [navigator.language || ""])) {
    const p = String(tag).toLowerCase().split("-")[0];
    if (p === "en") return null;      /* English comes first on this device: nothing to offer */
    const l = LANGS.find(x => x.status === "offered" && x.code !== "en" && x.code.split("-")[0] === p);
    if (l) return l;
  }
  return null;
}
export function offer(force) {
  if (D.querySelector(".tca-lo")) return;
  let l;
  if (force) l = LANGS.find(x => x.code === force);
  else {
    if (!isEn || "language" in saved() || store.get(OFFER) || QUIET.test(location.pathname)) return;
    l = fromBrowser();
  }
  if (!l || l.code === "en") return;
  css();
  const ask = l.offer || t("Read this in {language}?", {language: l.name});
  const no = l.offer_no || "No thanks";
  const a = D.createElement("aside");
  a.className = "tca-lo"; a.lang = l.offer ? l.html : "en"; a.setAttribute("aria-label", ask);
  a.innerHTML = `<button type="button" class="go">${esc(ask)}</button><button type="button" class="no" aria-label="${esc(no)}"${l.offer_no ? "" : ' lang="en"'}>&times;</button>`;
  const done = how => { store.set(OFFER, JSON.stringify({[how]: l.code, at: Date.now()})); a.remove(); };
  a.querySelector(".go").addEventListener("click", () => { done("yes"); setLanguage(l.code); });
  a.querySelector(".no").addEventListener("click", () => done("no"));
  a.addEventListener("keydown", e => { if (e.key === "Escape") { e.preventDefault(); done("no"); } });
  D.body.append(a);
}

/* ---------- the start: English is ready at once; another language once its words are here (2.5 seconds at most) ---------- */
let finished = false, readyFn = null;
export const ready = isEn ? Promise.resolve() : new Promise(r => { readyFn = r; });
window.__tcaReady = ready;
function finish() {
  if (finished) return;
  finished = true;
  translate(D);
  if (L.dir) H.dir = L.dir;
  if (PAGE_FULL && !missed) {      /* every word of this page is in the reader's language: the page says so */
    H.lang = L.html;
    for (const el of D.querySelectorAll("[translate=no],[data-t-miss]")) if (!el.closest("[lang]:not(html)")) el.lang = "en";
  }
  label();
  H.classList.remove("tca-i18n-wait");
  try {
    const s = JSON.parse(sessionStorage.getItem(SCROLL) || "null");
    sessionStorage.removeItem(SCROLL);
    if (s && s.p === location.pathname + location.search && s.y > 0) requestAnimationFrame(() => scrollTo(0, s.y));
  } catch (e) {}
  readyFn();
}
const onDOM = fn => (D.readyState === "loading" ? D.addEventListener("DOMContentLoaded", fn, {once: true}) : fn());
if (isEn) {
  H.classList.remove("tca-i18n-wait");
  onDOM(() => setTimeout(() => offer(), 900));
} else {
  const bundles = ["core", ...(H.getAttribute("data-i18n") || "").split(/\s+/).filter(Boolean)];
  const all = Promise.all(bundles.map(need));
  Promise.race([all, new Promise(r => setTimeout(r, WAIT))]).then(() => onDOM(finish));
  all.then(() => onDOM(() => { if (finished) translate(D); helpNote(); }));      /* words that came after the wait */
  if (bundles.length) need("guide");      /* Help's guide, ahead of the first time Help is opened */
}

/* for testing and for page scripts that write words of their own (window.__tcaI18n.t) */
window.__tcaI18n = {t, tHTML, raw, key, need, ready, lang, L, num, date, list, translate, tagLang, offer, misses, setLanguage, choices,
  test: on => { store.set(TEST, on === false ? "0" : "1"); }};
