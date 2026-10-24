/* The Civic Archive as an app (John, 2026-10-17: "download an App version ... to their phone, tablet, PC ... and provide
   that capability directly within the website too"). His answers: installed from the website itself (free, no app store,
   no account, it updates itself); "Get the app" in the top bar of every page until the reader has it, then only in Help;
   the pages already opened and a kept ballot work with no connection; one gentle note on a reader's second visit, closed
   for good with one tap, once per device.
   This module, loaded by the shell's script, by the rider and on the cabin:
   - registers the copy's worker (<root>sw.js), which keeps the pages a reader opens for use with no connection;
   - puts "Get the app" in the top bar (the shell's pages draw it; on the others it is added beside the page's own Motion
     button) and opens a small panel: the browser's own install prompt where there is one, the steps in words elsewhere;
   - gives Help its part about the app;
   - shows the second-visit note.
   What it keeps, in this browser only (tca.app.v1:<the copy's root>, so the draft at /dev/ and the live site at / each keep
   their own): how many visits, when the last one was, whether the note has been shown or closed, and whether the app was
   installed here. Nothing is sent anywhere by this code. Installing sends nothing to The Civic Archive; on Android, the
   browser's maker (Google, for Chrome) builds the app from the site's public manifest. */
import {t, tHTML, N_, raw, num, tagLang, lang as LANG} from "./i18n.d705614426.js";      /* the language layer: the app's words in the reader's language */
const D = document, H = D.documentElement;
const ROOT = new URL("../", import.meta.url);
const KEY = "tca.app.v1:" + ROOT.pathname, SEEN = "tca.app.seen:" + ROOT.pathname, GAP = 30 * 60e3;
const store = {
  get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }
};
const mq = q => { try { return matchMedia(q); } catch (e) { return {matches: false, addEventListener() {}}; } };
const reducedOS = mq("(prefers-reduced-motion: reduce)");
const esc = s => String(s).replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"})[c]);
function state() { try { const s = JSON.parse(store.get(KEY) || "null"); return s && typeof s === "object" ? s : {v: 1}; } catch (e) { return {v: 1}; } }
function save(s) { s.v = 1; store.set(KEY, JSON.stringify(s)); }
const rel = () => { const p = location.pathname, r = ROOT.pathname; return p.startsWith(r) ? decodeURIComponent(p.slice(r.length)) : ""; };

/* ---------- where the reader is: as the app, or which browser and device ---------- */
export function standalone() {
  return ["standalone", "fullscreen", "minimal-ui", "window-controls-overlay"].some(m => mq(`(display-mode: ${m})`).matches) || navigator.standalone === true;
}
/* the kind of browser, from its own description of itself; only the steps shown depend on it */
export function kindFor(ua, touch) {
  ua = ua || "";
  const ios = /iPhone|iPad|iPod/.test(ua) || (/Macintosh/.test(ua) && touch > 1);
  if (/FBAN|FBAV|FB_IAB|Instagram|Line\/|Snapchat|LinkedInApp|TikTok|musical_ly|Pinterest|GSA\/|; wv\)/.test(ua)) return "inapp";
  if (ios) return "ios";
  const edge = /Edg(e|A)?\//.test(ua), opera = /OPR\/|Opera/.test(ua), samsung = /SamsungBrowser/.test(ua), firefox = /Firefox\//.test(ua);
  const chrome = /Chrome\/|Chromium\//.test(ua) && !edge && !opera && !samsung;
  if (/Android/.test(ua)) return samsung ? "android-samsung" : firefox ? "android-firefox" : chrome && !/Version\/\d/.test(ua) ? "android-chrome" : "android-other";
  if (firefox) return "desktop-firefox";
  if (edge) return "desktop-edge";
  if (chrome) return "desktop-chrome";
  if (opera) return "desktop-other";
  if (/Macintosh/.test(ua) && /Safari\//.test(ua) && /Version\/(\d+)/.test(ua)) return +ua.match(/Version\/(\d+)/)[1] >= 17 ? "mac-safari" : "mac-safari-old";
  return "other";
}
const NO_INSTALL = new Set(["inapp", "desktop-firefox", "mac-safari-old"]);
let deferred = null;      // the browser's own install prompt, held until the reader asks for it
let KIND = kindFor(navigator.userAgent, navigator.maxTouchPoints || 0);
export function canInstall(kind = KIND) { return !!deferred || (!NO_INSTALL.has(kind) && (window.isSecureContext !== false)); }
function installed() { return standalone() || !!state().inst; }

/* ---------- the pictures in the steps: drawn here, nothing fetched ---------- */
const SVG = {
  app: '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><rect x="6.5" y="2.5" width="11" height="19" rx="2.4"/><path d="M12 6.8v7.2M9.1 11.3 12 14.2l2.9-2.9"/><path d="M10.4 18.3h3.2"/></svg>',
  share: '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M8.5 9.5H6.5v11h11v-11h-2"/><path d="M12 14.5V3.2M8.6 6.4 12 3l3.4 3.4"/></svg>',
  add: '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><rect x="4" y="4" width="16" height="16" rx="3.4"/><path d="M12 8.2v7.6M8.2 12h7.6"/></svg>',
  dots: '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M12 5.5v.01M12 12v.01M12 18.5v.01" stroke-width="3"/></svg>',
  hdots: '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M5.5 12h.01M12 12h.01M18.5 12h.01" stroke-width="3"/></svg>',
  lines: '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M5 7h14M5 12h14M5 17h14"/></svg>',
  install: '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><rect x="3" y="4.5" width="18" height="12" rx="1.8"/><path d="M8.5 20h7M12 7.5v6M9.4 11 12 13.6 14.6 11"/></svg>',
  x: '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M6 6l12 12M18 6L6 18"/></svg>'
};
const ico = (k, label) => `<span class="tca-app-ico" role="img" aria-label="${esc(t(label))}">${SVG[k]}</span>`;
/* the pictures a step names, each with the words a screen reader says for it */
const I = {share: ["share", N_("the Share button")], more: ["hdots", N_("the More button, three dots")], add: ["add", N_("the Add to Home Screen button")],
  dots: ["dots", N_("the menu button, three dots")], lines: ["lines", N_("the menu button, three lines")],
  install: ["install", N_("the install button, a screen with an arrow")], appbtn: ["install", N_("the app button")], hdots: ["hdots", N_("the menu button, three dots")]};
const icons = () => Object.fromEntries(Object.entries(I).map(([k, [svg, label]]) => [k, raw(ico(svg, label))]));

/* the steps for each kind of browser, in words, with the buttons drawn as the browser draws them ({share} and the like) */
const STEPS = {
  ios: [N_("Tap Share {share}. In Safari on an iPhone, if you do not see it, tap the More button {more} beside the address first; on an iPad it is at the top. In Chrome it is at the top right."),
        N_("Scroll down the list and tap Add to Home Screen {add}."),
        N_("Tap Add. The Civic Archive is now on your Home Screen.")],
  "mac-safari": [N_("In the menu bar at the top of the screen, choose File, then Add to Dock."), N_("Click Add. It opens from your Dock like any app.")],
  "android-chrome": [N_("Tap the menu {dots} at the top right."), N_("Tap Add to Home screen, then Install. (Some versions say Install app.)"), N_("It opens from your Home screen like any app.")],
  "android-samsung": [N_("Tap the menu {lines} at the bottom right."), N_("Tap Add page to, then Home screen."), N_("It opens from your Home screen like any app.")],
  "android-firefox": [N_("Tap the menu {dots}."), N_("Tap Add to Home screen. (Some versions say Install.)"), N_("It opens from your Home screen like any app.")],
  "android-other": [N_("Open your browser\u2019s menu and look for Install or Add to Home screen."), N_("If it has neither, open this site in Chrome or Samsung Internet and try there.")],
  "desktop-chrome": [N_("Click the install button {install} at the right end of the address bar."),
                     N_("No button there? Open the menu {dots}, then Cast, save and share, then Install page as app."), N_("Click Install. It opens in its own window, from your Start menu, Dock or app list.")],
  "desktop-edge": [N_("Click the app button {appbtn} at the right end of the address bar."),
                   N_("No button there? Open the menu {hdots}, then Apps, then Install this site as an app."), N_("Click Install. It opens in its own window, from your Start menu or app list.")],
  "desktop-other": [N_("Look in your browser\u2019s menu for Install or Install app."), N_("If there is none, open this site in Chrome or Edge, which can install it.")],
  other: [N_("Look in your browser\u2019s menu for Install, or Add to Home Screen."), N_("Chrome, Edge, Samsung Internet, and Safari on an iPhone, an iPad or a Mac can all install it.")]
};
const CANNOT = {
  "desktop-firefox": N_("Firefox on a computer does not install sites as apps the way other browsers do (newer versions on Windows can pin a site to the taskbar). To get the app on this computer, open this site in Chrome or Edge, or in Safari on a Mac. On a phone, every main browser can."),
  "mac-safari-old": N_("This version of Safari cannot add sites to the Dock. Safari 17 or later can (macOS Sonoma or later), and so can Chrome and Edge."),
  inapp: N_("You are reading this inside another app, whose browser cannot install it. Open this page in Safari on an iPhone or iPad, or in Chrome on Android, then tap Get the app there.")
};
const REMOVE = {
  ios: N_("To remove it, touch and hold its icon on your Home Screen, then tap Remove App."),
  android: N_("To remove it, touch and hold its icon, then tap Uninstall or Remove."),
  mac: N_("To remove it, drag it out of the Dock, then delete it from the Applications folder in your home folder."),
  desktop: N_("To remove it, open the app, then its menu (the three dots at the top), then Uninstall.")
};
function removeWords() {
  const ua = navigator.userAgent;
  return t(/iPhone|iPad|iPod/.test(ua) || (/Macintosh/.test(ua) && navigator.maxTouchPoints > 1) ? REMOVE.ios : /Android/.test(ua) ? REMOVE.android
    : KIND === "mac-safari" ? REMOVE.mac : REMOVE.desktop);
}
const OFFLINE_WORDS = N_("Pages you have opened, and a ballot you kept, still work with no connection. Anything new needs one.");
const PRIVACY_WORDS = N_("Installing sends nothing to The Civic Archive. On Android, your browser\u2019s maker (Google, for Chrome) builds the app from this site\u2019s public description of itself. The app is this website, kept on your device.");

/* the panel's middle: what to do here */
export function how(kind = KIND, prompt = !!deferred) {
  if (standalone()) return `<p class="lead">${esc(t("You are using the app. It updates itself whenever you are online."))}</p><p>${esc(removeWords())}</p>`;
  if (prompt) return `<p class="lead">${esc(t("Your browser can install it in one step."))}</p><p><button type="button" class="tca-app-go" data-tca-app-install>${SVG.app}${esc(t("Install The Civic Archive"))}</button></p>
<p class="tca-app-fine">${esc(t("Your browser asks you to confirm. Nothing is downloaded from an app store."))}</p>`;
  if (CANNOT[kind]) return `<p class="lead">${esc(t(CANNOT[kind]))}</p>`;
  if (window.isSecureContext === false) return `<p class="lead">${esc(t("Installing needs the site\u2019s secure address, which begins with https."))}</p>`;
  const s = STEPS[kind] || STEPS.other, pics = icons();
  return `<ol>${s.map(x => `<li>${tHTML(x, pics)}</li>`).join("")}</ol>`;
}

/* ---------- the panel ---------- */
let panel = null, opener = null, btn = null;
function panelHTML() {
  return `<button class="x" type="button" aria-label="${esc(t("Close"))}">${SVG.x}</button>
<h2 id="tca-app-h" tabindex="-1">${esc(t("Get the app"))}</h2>
<p class="lead">${esc(t("Keep The Civic Archive on your phone, tablet or computer. It is free: no app store, no account, and it updates itself."))}</p>
<div data-tca-app-how>${how()}</div>
<h3>${esc(t("With no connection"))}</h3><p>${esc(t(OFFLINE_WORDS))}</p>
<h3>${esc(t("Your privacy"))}</h3><p>${esc(t(PRIVACY_WORDS))}</p>
<p><a href="${esc(new URL("app/", ROOT).href)}">${esc(t("More about the app"))}</a></p>
<p class="tca-app-said" data-tca-app-said role="status" aria-live="polite"></p>`;
}
function buildPanel() {
  panel = D.createElement("section");
  panel.className = "tca-apppanel"; panel.id = "tca-app"; panel.hidden = true; tagLang(panel);
  panel.setAttribute("role", "dialog"); panel.setAttribute("aria-modal", "false"); panel.setAttribute("aria-labelledby", "tca-app-h");
  panel.innerHTML = panelHTML();
  D.body.append(panel);
  panel.querySelector(".x").addEventListener("click", () => openPanel(false));
  panel.addEventListener("click", e => { if (e.target.closest("[data-tca-app-install]")) install(); });
}
function refreshPanel() {
  if (!panel) return;
  const box = panel.querySelector("[data-tca-app-how]");
  if (box) box.innerHTML = how();
}
function barEdge() {
  const bar = D.querySelector(".tca-top") || D.querySelector("header.top");
  if (!bar) return 0;
  const r = bar.getBoundingClientRect();
  return Math.max(0, Math.round(r.bottom));
}
export function openPanel(open, from) {
  if (!panel) buildPanel();
  open = open == null ? panel.hidden : open;
  if (open === !panel.hidden) return;
  if (open) {
    const help = from && from.closest && from.closest("#tca-help");
    if (help) {      /* opened from inside Help: Help closes, and focus will come back to the bar's own button */
      const x = help.querySelector(".x"); if (x) x.click();
      from = (btn && !btn.hidden && btn) || D.querySelector('.tca-tools [aria-controls="tca-help"]') || D.querySelector(".tca-dockbtn,.tca-bubble") || null;
    }
    opener = from || D.activeElement;
    refreshPanel();
    panel.querySelector("[data-tca-app-said]").textContent = "";
    panel.style.setProperty("--bar-bottom", barEdge() + "px");
    panel.hidden = false;
    const h = panel.querySelector("h2"); try { h.focus({preventScroll: true}); } catch (e) { h.focus(); }
  } else {
    panel.hidden = true;
    if (opener && opener.isConnected) { try { opener.focus({preventScroll: true}); } catch (e) {} }
    opener = null;
  }
  for (const b of D.querySelectorAll('[aria-controls="tca-app"]')) b.setAttribute("aria-expanded", open ? "true" : "false");
}
async function install() {
  const said = panel && panel.querySelector("[data-tca-app-said]");
  if (!deferred) { refreshPanel(); return; }
  const p = deferred; deferred = null;
  try {
    await p.prompt();
    const r = await p.userChoice;
    if (said) said.textContent = r && r.outcome === "accepted" ? t("Installed. Open it from your Home screen, Start menu, Dock or app list.") : t("Not installed. You can install it later from this button.");
  } catch (e) { if (said) said.textContent = t("Your browser did not open its install prompt. The steps below work too."); }
  refreshPanel();
}

/* ---------- the button in the top bar ---------- */
function makeButton(cls) {
  const b = D.createElement("button");
  b.type = "button"; b.className = cls; b.setAttribute("data-tca-app", "");
  b.setAttribute("aria-controls", "tca-app"); b.setAttribute("aria-expanded", "false"); b.setAttribute("aria-haspopup", "dialog");
  return b;
}
function placeButton() {
  /* the shell's pages draw it as a link to the app page (it works with no script); here it becomes a real button */
  const link = D.querySelector(".tca-top a[data-tca-app]");
  if (link) {
    btn = makeButton(link.className);
    btn.innerHTML = link.innerHTML;
    link.replaceWith(btn);
  } else {
    /* the pages with their own top bar: beside their own Motion button, wearing its class so it matches the bar */
    const bar = D.querySelector("header.top");
    const motion = bar && bar.querySelector("#motion");
    if (!bar || !motion || bar.querySelector("[data-tca-app]")) return;
    const cls = [...motion.classList].filter(c => !/^(on|off|active|pressed)$/.test(c)).join(" ");
    btn = makeButton(cls + " tca-appbtn");
    btn.innerHTML = `${SVG.app}<span class="tca-app-lab">${esc(t("Get the app"))}</span>`;
    tagLang(btn);
    const brk = bar.querySelector(".tbreak");
    if (brk && brk.parentElement === motion.parentElement) brk.after(btn); else motion.before(btn);
  }
  btn.addEventListener("click", () => openPanel(null, btn));
  roomCheck();
  if (btn.classList.contains("tca-appbtn")) {
    addEventListener("resize", () => { clearTimeout(roomT); roomT = setTimeout(roomCheck, 150); });
    if (D.fonts && D.fonts.ready) D.fonts.ready.then(roomCheck);
    addEventListener("load", roomCheck, {once: true});
    addEventListener("tca:seat", roomCheck);      // the reading button beside it has just taken its place
  }
  showButton();
}
function showButton() {
  const on = !installed() && canInstall();      // where this browser cannot install it, the offer stays in Help only
  if (on) H.removeAttribute("data-app"); else H.setAttribute("data-app", standalone() ? "app" : "installed");
  if (btn) btn.hidden = !on || noRoom;
  dispatchEvent(new Event("resize"));      // the bar measures itself again, so nothing in it overlaps
}
/* A page with its own top bar may have no room left for it on a narrow phone (the record pages hold six buttons there).
   It is measured, not guessed: where the button would push the bar wider than the screen, it stays out of the bar on that
   width, and "Get the app" is in Help (the companion's button), as it always is; a wider screen or turning the phone
   brings it back. */
let noRoom = false, roomT = 0;
function over() {
  const bar = D.querySelector("header.top"); if (!bar) return 0;
  let n = Math.max(0, D.documentElement.scrollWidth - D.documentElement.clientWidth);
  for (const el of [bar, ...bar.children]) n = Math.max(n, el.scrollWidth - el.clientWidth);
  return n;
}
function roomCheck() {
  if (!btn || !btn.classList.contains("tca-appbtn") || installed() || !canInstall()) return;
  btn.hidden = true;
  const base = over(), bar = D.querySelector("header.top"), tall = bar ? bar.getBoundingClientRect().height : 0;
  btn.hidden = false;
  noRoom = over() > base + 1 || (!!bar && bar.getBoundingClientRect().height > tall + 1);      // nor fold the bar onto another line
  btn.hidden = noRoom;
}

/* ---------- Help's part about the app (the shell's Help, and the rider's) ---------- */
export function helpHTML() {
  const more = `<a href="${esc(new URL("app/", ROOT).href)}">${esc(t("More about the app"))}</a>`;
  if (standalone()) return `<p>${esc(t("You are using the app. It is this website kept on this device, and it updates itself whenever you are online."))}</p><p>${esc(removeWords())}</p><p>${more}</p>`;
  if (state().inst) return `<p>${esc(t("The app is on this device. Open it from your Home screen, Start menu, Dock or app list."))}</p><p>${more}</p>`;
  return `<p>${esc(t("Keep The Civic Archive on your phone or computer as an app. It is free, and it works with no connection for the pages you have opened."))}</p>
<div class="row"><button type="button" class="go" data-tca-app-open aria-controls="tca-app" aria-expanded="false" aria-haspopup="dialog">${SVG.app}${esc(t("Get the app"))}</button>${more}</div>`;
}
function fillHelp() {
  for (const box of D.querySelectorAll("[data-tca-app-help]")) {
    box.classList.add("tca-apphelp");
    box.innerHTML = helpHTML();
  }
  /* the app page says where this device stands */
  for (const el of D.querySelectorAll("[data-tca-app-state]"))
    el.textContent = standalone() ? t("You are using the app now.") : state().inst ? t("The app is on this device.") : "";
}
/* any "Get the app" button on a page (Help's, the app page's) opens the panel; the app page can also show and clear what is kept */
function onClick(e) {
  const b = e.target.closest("[data-tca-app-open],[data-tca-app-forget]");
  if (!b) return;
  if (b.hasAttribute("data-tca-app-open")) { e.preventDefault(); openPanel(true, b); return; }
  e.preventDefault();
  ask({tca: "forget"}).then(r => {
    const say = w => { const s = D.querySelector("[data-tca-app-kept]"); if (s) s.textContent = w; };
    if (r && r.ok) say(t("Cleared. The pages and files kept for use with no connection are gone; pages you open from here on are kept again. A ballot you kept stays until you press Forget this ballot on its own page."));
    else say(t("Nothing was cleared: this browser did not answer. To clear everything, clear this site\u2019s data in your browser\u2019s settings."));
  });
}
function ask(msg) {
  return new Promise(ok => {
    try {
      if (!("serviceWorker" in navigator)) return ok(null);
      navigator.serviceWorker.getRegistration(ROOT.href).then(reg => {
        const w = reg && (reg.active || reg.waiting || reg.installing);
        if (!w || !reg.scope || new URL(reg.scope).pathname !== ROOT.pathname) return ok(null);
        const ch = new MessageChannel();
        ch.port1.onmessage = e => ok(e.data);
        w.postMessage(msg, [ch.port2]);
        setTimeout(() => ok(null), 3000);
      }, () => ok(null));
    } catch (e) { ok(null); }
  });
}
function kept() {
  const el = D.querySelector("[data-tca-app-kept]");
  if (!el) return;
  ask({tca: "stats"}).then(r => {
    if (!r) { el.textContent = t("Nothing is kept on this device yet."); return; }
    const d = r.bytes < 1e7 ? 1 : 0, mb = num(Number((r.bytes / 1e6).toFixed(d)), {minimumFractionDigits: d, maximumFractionDigits: d});
    const us = r.us ? t("The Congress pages keep {n, plural, one {# more file} other {# more files}} of their own (bills, votes, portraits), apart from that.", {n: r.us}) : "";
    el.textContent = [r.pages || r.files ? t("Kept on this device now: {pages, plural, one {# page} other {# pages}} and {files, plural, one {# small file} other {# small files}}, {mb} MB of about {budget} MB.",
      {pages: r.pages, files: r.files, mb, budget: Math.round(r.budget / 1e6)}) : t("Nothing is kept on this device yet."), us].filter(Boolean).join(" ");
  });
}

/* ---------- the one note, on a reader's second visit ---------- */
const SITS = /^(night\/sky\/|ballot\/polling-place\/|reading-room\/|cabin\.html|app\/)/;
function busy() {
  if (H.hasAttribute("data-arrive")) return true;      // Election Night's arrival is playing
  const open = D.querySelectorAll('dialog[open],[aria-modal="true"],.tca-sv,.tca-nv,.tca-panel:not([hidden]):not(.inline),.tca-rp:not([hidden]),#tca-app:not([hidden]),.tca-lo,[role="dialog"]:not([hidden])');
  for (const el of open) { if (el.getClientRects().length && getComputedStyle(el).visibility !== "hidden") return true; }
  return false;
}
function motionOn() {
  if (reducedOS.matches || H.getAttribute("data-motion") === "reduced" || H.getAttribute("data-calm") === "on" || H.classList.contains("calm")) return false;
  return store.get("motion") !== "off";
}
let noteEl = null, noteTimer = 0, noteFrom = null;
function noteDue() {
  const s = state();
  if (!s.n || s.n < 2 || s.note) return false;      // shown once already (on one page only), or closed: never again
  /* never in the same visit as the card that offers the levels (Meet me where I am, levels.js) */
  try { const c = JSON.parse(store.get("tca.levels.card.v1") || "null"); if (c && c.shown && (c.n === s.n || !c.done && Date.now() - (c.at || 0) < GAP)) return false; } catch (e) {}
  return !installed() && canInstall() && !SITS.test(rel());
}
function closeNote(why) {
  const s = state(); s.note = 2; s.how = why; save(s);
  clearInterval(noteTimer);
  const back = noteFrom, had = noteEl && noteEl.contains(D.activeElement);
  if (noteEl) { noteEl.remove(); noteEl = null; }
  if (why === "get") {      /* focus comes back to the bar's button, or where that is hidden, to Help's (the companion's) */
    const to = (btn && !btn.hidden && btn) || D.querySelector('.tca-tools [aria-controls="tca-help"]') || D.querySelector(".tca-dockbtn,.tca-bubble") || null;
    openPanel(true, to); return;
  }
  if (had && back && back.isConnected) { try { back.focus({preventScroll: true}); } catch (e) {} }
}
function showNote() {
  if (noteEl || !noteDue()) return;
  noteEl = D.createElement("aside");
  noteEl.className = "tca-appnote" + (motionOn() ? " rise" : "");
  noteEl.setAttribute("aria-label", t("The Civic Archive as an app"));
  tagLang(noteEl);
  noteEl.innerHTML = `<p role="status">${esc(t("The Civic Archive is also an app you can keep on your phone or computer."))}</p>
<div class="row"><button type="button" class="go" data-get>${SVG.app}${esc(t("Get the app"))}</button><button type="button" class="no" data-no>${esc(t("No thanks"))}</button></div>`;
  noteEl.querySelector("[data-get]").addEventListener("click", () => closeNote("get"));
  noteEl.querySelector("[data-no]").addEventListener("click", () => closeNote("no"));
  noteEl.addEventListener("focusin", e => { if (!noteFrom && e.relatedTarget && !noteEl.contains(e.relatedTarget)) noteFrom = e.relatedTarget; });
  D.body.append(noteEl);
  const s = state(); s.note = 1; s.nv = s.n; save(s);      // shown: it is not shown again on another page, closed or not
  /* never over a dialog, a panel or a scene on the way in: it steps away while one is open */
  noteTimer = setInterval(() => { if (noteEl) { noteEl.hidden = busy(); clear(); } }, 700);
  clear();
}
/* it never covers the companion or its Help button, wherever the page has lifted them */
function clear() {
  if (!noteEl || noteEl.hidden) return;
  noteEl.style.removeProperty("bottom");
  const n = noteEl.getBoundingClientRect();
  for (const el of D.querySelectorAll(".tca-dock,.tca-bubble")) {
    const r = el.getBoundingClientRect();
    if (!r.width || r.left >= n.right || r.right <= n.left || r.top >= n.bottom || r.bottom <= n.top) continue;
    noteEl.style.bottom = Math.max(8, Math.round(innerHeight - r.top + 8)) + "px";
  }
}
function noteLater() {
  if (!noteDue()) return;
  let tries = 0;
  const t = setInterval(() => {
    if (++tries > 120 || !noteDue()) { clearInterval(t); return; }
    if (D.visibilityState === "visible" && !busy()) { clearInterval(t); showNote(); }
  }, 1500);
}

/* ---------- a visit is a new browser session after half an hour away; counted on this device only ---------- */
function countVisit() {
  const s = state(), now = Date.now();
  let fresh = false;
  try { fresh = !sessionStorage.getItem(SEEN); sessionStorage.setItem(SEEN, "1"); } catch (e) { fresh = !s.n; }
  if (!s.n) s.n = 1;
  else if (fresh && now - (s.last || 0) > GAP) s.n += 1;
  s.last = now;
  save(s);
}
/* "when the last one was" means the last time a page was in use, not only when one loaded: a reader who stays on one page for
   an hour and then opens a link in a new tab is still on the same visit */
function stamp() { const s = state(); if (s.n) { s.last = Date.now(); save(s); } }

/* ---------- the worker: the whole copy, scoped to its root ---------- */
function register() {
  if (!("serviceWorker" in navigator) || window.isSecureContext === false) return;
  const go = () => navigator.serviceWorker.register(new URL("sw.js", ROOT).href, {scope: ROOT.pathname}).catch(() => {});
  if (D.readyState === "complete") go(); else addEventListener("load", go, {once: true});
}

/* ---------- wiring ---------- */
addEventListener("beforeinstallprompt", e => {
  e.preventDefault();      // no browser bar of its own: the reader asks for it with "Get the app"
  deferred = e;
  const s = state(); if (s.inst) { delete s.inst; save(s); }      // a browser that offers to install it does not have it
  showButton(); refreshPanel(); fillHelp();
});
addEventListener("appinstalled", () => {
  deferred = null;
  const s = state(); s.inst = 1; if (s.note !== 2 && s.note) s.note = 2; save(s);
  showButton(); fillHelp();
  if (noteEl) closeNote("no");
  if (panel && !panel.hidden) { refreshPanel(); const said = panel.querySelector("[data-tca-app-said]"); if (said) said.textContent = t("Installed. Open it from your Home screen, Start menu, Dock or app list."); }
});
function start() {
  countVisit();
  setInterval(() => { if (D.visibilityState === "visible") stamp(); }, 5 * 60e3);
  D.addEventListener("visibilitychange", stamp);
  addEventListener("pagehide", stamp);
  if (standalone()) { const s = state(); if (!s.inst) { s.inst = 1; save(s); } }
  placeButton();
  fillHelp();
  D.addEventListener("click", onClick);
  if (D.querySelector("[data-tca-app-kept]")) { if (D.readyState === "complete") setTimeout(kept, 600); else addEventListener("load", () => setTimeout(kept, 600), {once: true}); }
  H.addEventListener("tca:help", e => { const d = e.detail || {}; if (d.open || d.built) fillHelp(); if (d.open && panel && !panel.hidden) { opener = null; openPanel(false); } });
  D.addEventListener("keydown", e => {
    if (e.key !== "Escape" || e.defaultPrevented) return;
    if (panel && !panel.hidden) { e.preventDefault(); openPanel(false); return; }
    if (noteEl && !noteEl.hidden && noteEl.contains(D.activeElement)) { e.preventDefault(); closeNote("no"); }      // only from inside the note
  });
  D.addEventListener("pointerdown", e => {
    if (!panel || panel.hidden) return;
    const t = e.target;
    if (!panel.contains(t) && !t.closest('[aria-controls="tca-app"],.tca-appnote')) { opener = null; openPanel(false); }
  }, true);
  for (const m of ["standalone", "fullscreen", "minimal-ui"]) mq(`(display-mode: ${m})`).addEventListener("change", () => { showButton(); fillHelp(); });
  if (navigator.getInstalledRelatedApps && !standalone()) navigator.getInstalledRelatedApps().then(list => {
    if (list && list.length) { const s = state(); s.inst = 1; save(s); showButton(); fillHelp(); }
  }).catch(() => {});
  register();
  setTimeout(noteLater, 4000);
}
/* for the page's own tests and for the app page: what the panel would say in another browser */
window.__tcaApp = {kindFor, how: (k, p) => how(k, !!p), open: () => openPanel(true, btn), setKind: k => { KIND = k; refreshPanel(); }, state, standalone,
  canInstall, showNote: () => { noteEl && noteEl.remove(); noteEl = null; showNote(); }, helpHTML};
if (D.readyState === "loading") D.addEventListener("DOMContentLoaded", start, {once: true}); else start();
const css = D.createElement("link");
css.rel = "stylesheet"; css.href = new URL("./app.33113652a3.css", import.meta.url).href;
D.head.append(css);
