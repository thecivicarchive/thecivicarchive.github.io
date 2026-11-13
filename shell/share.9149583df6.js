/* The Civic Archive: sharing (John, 2026-10-21: "make basically any component, area, etc. within the site shareable so
   someone could be in an area and then they could have the ability to share it with friends via ... text, email, Facebook,
   LinkedIn, and other platforms").
   His answers: on a phone, the phone's own share sheet (it reaches every app the phone has); on a computer, a small menu:
   Copy link, E-mail, Facebook, LinkedIn, X, Bluesky, WhatsApp and Reddit (and Text, on a phone, when its own sheet is not
   there); the ready-made words are just the facts; sharing a reader's own ballot first says, in plain words, that the link
   shows roughly where they vote.

   THE CONTRACT every page builder follows:
   - any element with the attribute data-share is a Share button. Its other attributes:
       data-share-url    the absolute address to share (without it: this page's address, with its # route);
       data-share-title  a short title (without it: the page's title);
       data-share-text   the ready-made message, facts only (without it: the page's description, else the title);
       data-share-warn   optional: a sentence shown first, with "Share anyway" and "Cancel".
   - script can open the same thing with window.tcaShare({url, title, text, warn}, anchorElement).
   - class="tca-share" is the standard button (a share icon and the word Share), styled in share.css.
   - the federal page's own older buttons (class "sharebtn") are left to that page's own code until it moves to this one.
   One listener on the document handles every button, so buttons drawn later need nothing more.

   What it sends: nothing. Every place in the menu is a plain link that opens only when the reader picks it, in a new tab
   with no referrer (rel="noopener noreferrer"); no button, widget or script from those services is ever loaded. The service
   the reader picks then sees the link and the words. Copy link uses this device's clipboard. A part of an address that
   looks like a place on the map (coordinates, or an address field) is never put into a shared link.
   The menu's words come in the reader's language (the language layer, shell_src/i18n.js: t(), the shell's own words, read into
   its core bundle); the services' names are names, and the ready-made words a page wrote stay as the page wrote them. */
import {t} from "./i18n.d705614426.js";
const D = document, H = D.documentElement;
const esc = s => String(s == null ? "" : s).replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"})[c]);
const mq = q => { try { return matchMedia(q).matches; } catch (e) { return false; } };
const UA = navigator.userAgent || "";
/* a phone or a tablet: a touch screen as the main pointer, or a phone's own description of itself */
const isPhone = () => /Android|iPhone|iPad|iPod/.test(UA) || (/Macintosh/.test(UA) && navigator.maxTouchPoints > 1) || (mq("(pointer: coarse)") && navigator.maxTouchPoints > 0);

const ICON = {
  share: '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><path d="M8.6 13.5l6.8 4M15.4 6.5l-6.8 4"/></svg>',
  link: '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M10 13.5a4.2 4.2 0 0 0 6 .4l3-3a4.2 4.2 0 0 0-6-6l-1.6 1.6"/><path d="M14 10.5a4.2 4.2 0 0 0-6-.4l-3 3a4.2 4.2 0 0 0 6 6l1.6-1.6"/></svg>',
  text: '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M4.5 5.5h15v10h-8.5l-4.5 3.8v-3.8h-2z"/></svg>',
  mail: '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><rect x="3.5" y="5.5" width="17" height="13" rx="1.8"/><path d="M4 7l8 6 8-6"/></svg>',
  out: '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M13.5 4.5h6v6M19.5 4.5l-8 8"/><path d="M17.5 13.5v5a1 1 0 0 1-1 1h-11a1 1 0 0 1-1-1v-11a1 1 0 0 1 1-1h5"/></svg>',
  x: '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M6 6l12 12M18 6L6 18"/></svg>'
};
export const SHARE_ICON = ICON.share;
/* the standard button, for script that draws one (a page written ahead of time carries the same markup) */
export function shareButton({url, title, text, warn, label = t("Share"), cls = ""} = {}) {
  const a = (k, v) => v ? ` data-share-${k}="${esc(v)}"` : "";
  return `<button type="button" class="tca-share${cls ? " " + esc(cls) : ""}" data-share${a("url", url)}${a("title", title)}${a("text", text)}${a("warn", warn)}>${ICON.share}<span>${esc(label)}</span></button>`;
}

/* ---------- what is shared ---------- */
const PLACE_KEYS = /^(lat|lon|lng|long|latitude|longitude|ll|latlng|latlon|coords?|geo|pin|loc|location|addr|address|street|zip|postcode)$/i;
const PAIR = /-?\d{1,3}\.\d{3,}\s*(,|%2C)\s*-?\d{1,3}\.\d{3,}/i;
/* the address, made absolute, http(s) only, with any part that could say where someone is taken out */
export function clean(u) {
  let x;
  try { x = new URL(u || location.href, location.href); } catch (e) { x = new URL(location.href); }
  if (!/^https?:$/.test(x.protocol)) x = new URL(location.href);
  for (const k of [...x.searchParams.keys()]) if (PLACE_KEYS.test(k) || PAIR.test(x.searchParams.get(k) || "")) x.searchParams.delete(k);
  if (x.hash) {
    const parts = x.hash.slice(1).split("&").filter(p => { const k = p.split("=")[0]; return !PLACE_KEYS.test(k) && !PAIR.test(p); });
    x.hash = parts.length ? "#" + parts.join("&") : "";
  }
  return x.href;
}
const meta = n => { const m = D.querySelector(`meta[name="${n}"],meta[property="${n}"]`); return m ? m.content : ""; };
function fromEl(el) {
  const g = k => el.getAttribute("data-share-" + k) || "";
  return {url: g("url"), title: g("title"), text: g("text"), warn: g("warn")};
}
function norm(o) {
  o = o || {};
  const url = clean(o.url);
  const title = String(o.title || meta("og:title") || D.title || "The Civic Archive").trim();
  const text = String(o.text || meta("description") || meta("og:description") || title).trim();
  return {url, title, text, warn: String(o.warn || "").trim()};
}
const cut = (s, n) => s.length <= n ? s : s.slice(0, Math.max(0, n - 1)).replace(/\s+\S*$/, "") + "…";
/* every place, as a plain link; Text only on a phone */
export function places(o, phone = isPhone()) {
  const u = encodeURIComponent(o.url), tt = encodeURIComponent(o.text), tu = encodeURIComponent(o.text + " " + o.url);
  const list = [];
  if (phone) list.push(["text", t("Text message"), "sms:?&body=" + tu, ICON.text, false]);
  list.push(["email", t("E-mail"), "mailto:?subject=" + encodeURIComponent(o.title) + "&body=" + encodeURIComponent(o.text + "\n\n" + o.url), ICON.mail, false]);
  list.push(["facebook", "Facebook", "https://www.facebook.com/sharer/sharer.php?u=" + u, ICON.out, true]);
  list.push(["linkedin", "LinkedIn", "https://www.linkedin.com/sharing/share-offsite/?url=" + u, ICON.out, true]);
  list.push(["x", "X", "https://twitter.com/intent/tweet?text=" + tt + "&url=" + u, ICON.out, true]);
  /* Bluesky's posts hold 300 characters, the link included */
  list.push(["bluesky", "Bluesky", "https://bsky.app/intent/compose?text=" + encodeURIComponent(cut(o.text, Math.max(40, 299 - o.url.length)) + " " + o.url), ICON.out, true]);
  list.push(["whatsapp", "WhatsApp", "https://wa.me/?text=" + tu, ICON.out, true]);
  list.push(["reddit", "Reddit", "https://www.reddit.com/submit?url=" + u + "&title=" + encodeURIComponent(cut(o.title, 300)), ICON.out, true]);
  return list;
}

/* ---------- what is said aloud, and shown for a moment ---------- */
let sayEl = null, sayT = 0;
function say(msg) {
  if (!sayEl) {
    sayEl = D.createElement("div"); sayEl.className = "tca-sharesay"; sayEl.setAttribute("role", "status"); sayEl.setAttribute("aria-live", "polite");
    D.body.append(sayEl);
  }
  const host = hostOf(opener || D.activeElement);
  if (sayEl.parentNode !== host) host.append(sayEl);
  clearTimeout(sayT);
  sayEl.textContent = ""; sayEl.classList.remove("on");
  setTimeout(() => { sayEl.textContent = msg; sayEl.classList.add("on"); }, 60);
  sayT = setTimeout(() => sayEl.classList.remove("on"), 2600);
}

/* ---------- the menu ---------- */
let box = null, opener = null, cur = null, tracking = 0, uid = 0;
function close(back = true) {
  if (!box || box.hidden) return;
  box.hidden = true; box.innerHTML = "";
  removeEventListener("scroll", place, true); removeEventListener("resize", onResize);
  const o = opener; opener = null; cur = null;
  if (o) o.setAttribute("aria-expanded", "false");
  if (back && o && o.isConnected) { try { o.focus({preventScroll: true}); } catch (e) {} }
}
addEventListener("hashchange", () => close(false));      /* a page that changes route in place: the open menu belonged to the last item */
function onResize() { place(); }
function make() {
  box = D.createElement("div"); box.className = "tca-sharebox"; box.hidden = true;
  box.setAttribute("role", "dialog"); box.setAttribute("aria-modal", "false");
  D.body.append(box);
  box.addEventListener("keydown", onKey);
  box.addEventListener("focusout", e => { if (!box.hidden && e.relatedTarget && !box.contains(e.relatedTarget) && e.relatedTarget !== opener) close(false); });
  box.addEventListener("click", onBoxClick);
  D.addEventListener("pointerdown", e => { if (box && !box.hidden && !box.contains(e.target) && !(opener && opener.contains(e.target))) close(false); }, true);
  D.addEventListener("keydown", e => { if (e.key === "Escape" && box && !box.hidden && !box.contains(e.target)) close(true); });
}
const items = () => box ? [...box.querySelectorAll('[role="menuitem"]')] : [];
function onKey(e) {
  if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); close(true); return; }
  const its = items(), i = its.indexOf(D.activeElement);
  if (i < 0 || !["ArrowDown", "ArrowUp", "Home", "End", "ArrowRight", "ArrowLeft"].includes(e.key)) return;
  e.preventDefault(); e.stopPropagation();      /* the places to sit turn the view with the arrow keys: not while the menu has them */
  const n = its.length, j = e.key === "Home" ? 0 : e.key === "End" ? n - 1 : (e.key === "ArrowDown" || e.key === "ArrowRight") ? (i + 1) % n : (i - 1 + n) % n;
  its[j].focus();
}
function onBoxClick(e) {
  const b = e.target.closest("button,a"); if (!b || !box.contains(b)) return;
  if (b.matches(".x,[data-sh-cancel]")) { close(true); return; }
  if (b.matches("[data-sh-go]")) { const o = cur; if (isPhone() && native(o, opener)) return; menu(o); return; }
  if (b.matches(".tca-share-copy")) { copy(cur.url); return; }
  if (b.matches("a[href]")) setTimeout(() => close(false), 0);      /* the link opens; the menu goes */
}
/* where the box sits: under (or over) its button on a computer; a sheet along the bottom on a narrow screen */
function place() {
  if (!box || box.hidden) return;
  if (tracking) return;
  tracking = requestAnimationFrame(() => {
    tracking = 0;
    const vw = innerWidth, vh = innerHeight, narrow = vw <= 560 || !opener || !opener.isConnected;
    box.classList.toggle("sheet", narrow);
    if (narrow) { box.style.left = box.style.top = box.style.right = box.style.bottom = box.style.maxHeight = ""; return; }
    /* below the button when it fits, else above it when that fits, else on the roomier side, scrolling inside */
    box.style.maxHeight = "";
    const r = opener.getBoundingClientRect(), w = box.offsetWidth, h = box.offsetHeight;
    const left = Math.min(Math.max(8, r.left), vw - w - 8);
    const below = vh - r.bottom - 14, above = r.top - 14;
    let top;
    if (h <= below) top = r.bottom + 6;
    else if (h <= above) top = r.top - h - 6;
    else if (below >= above) { top = r.bottom + 6; box.style.maxHeight = Math.max(160, below) + "px"; }
    else { const m = Math.max(160, above); box.style.maxHeight = m + "px"; top = r.top - Math.min(h, m) - 6; }
    top = Math.min(Math.max(8, top), Math.max(8, vh - Math.min(h, box.offsetHeight) - 8));
    box.style.left = Math.round(left) + "px"; box.style.top = Math.round(top) + "px"; box.style.right = box.style.bottom = "";
  });
}
/* a Share button inside a modal dialog (a race's chart pop-out) gets its menu inside that dialog, where it can be seen and reached;
   any other, on the page itself */
const hostOf = el => (el && el.closest && el.closest("dialog[open]")) || D.body;
function show(html, label, focusSel) {
  if (!box) make();
  const host = hostOf(opener);
  if (box.parentNode !== host) host.append(box);
  box.innerHTML = html;
  box.setAttribute("aria-labelledby", label);
  box.hidden = false;
  if (opener) opener.setAttribute("aria-expanded", "true");
  addEventListener("scroll", place, true); addEventListener("resize", onResize);
  tracking = 0; place();
  const f = box.querySelector(focusSel);
  if (f) { try { f.focus({preventScroll: true}); } catch (e) {} }
}
function head(id, title, sub) {
  return `<button class="x" type="button" aria-label="${esc(t("Close"))}">${ICON.x}</button><p class="tca-sh-h" id="${id}" tabindex="-1">${esc(title)}</p>`
    + (sub ? `<p class="tca-sh-what">${esc(sub)}</p>` : "");
}
function menu(o) {
  const id = "tca-sh-" + (++uid), ext = `<span class="tca-sh-sr"> ${esc(t("(opens in a new tab)"))}</span>`;
  const links = places(o).map(([k, label, href, ic, away]) =>
    `<li role="none"><a role="menuitem" class="tca-sh-item" data-place="${k}" href="${esc(href)}"${away ? ' target="_blank" rel="noopener noreferrer"' : ""}>${ic}<span>${esc(label)}</span>${away ? ext : ""}</a></li>`).join("");
  show(head(id, t("Share"), o.title)
    + `<ul class="tca-sh-list" role="menu" aria-labelledby="${id}"><li role="none"><button type="button" role="menuitem" class="tca-sh-item tca-share-copy">${ICON.link}<span>${esc(t("Copy link"))}</span></button></li>${links}</ul>`
    + `<p class="tca-sh-fine">${esc(t("Nothing is sent until you pick one. The place you pick then sees the link."))}</p>`, id, ".tca-share-copy");
}
function warnFirst(o) {
  const id = "tca-sh-" + (++uid);
  show(head(id, t("Before you share")) + `<p class="tca-sh-warn" id="${id}-w">${esc(o.warn)}</p>`
    + `<p class="tca-sh-row"><button type="button" class="tca-sh-go" data-sh-go>${esc(t("Share anyway"))}</button><button type="button" class="tca-sh-no" data-sh-cancel>${esc(t("Cancel"))}</button></p>`, id, ".tca-sh-h");
  box.setAttribute("aria-describedby", id + "-w");
}
/* the phone's own share sheet. A reader who closes it has chosen not to share; if it cannot open, the menu opens instead */
function native(o, anchor) {
  const data = {title: o.title, text: o.text, url: o.url};
  if (!navigator.share) return false;
  try { if (navigator.canShare && !navigator.canShare(data)) return false; } catch (e) { return false; }
  close(false);
  let p;
  try { p = navigator.share(data); } catch (e) { opener = anchor; cur = o; menu(o); return true; }
  if (p && p.catch) p.catch(err => { if (!err || err.name !== "AbortError") { opener = anchor; cur = o; menu(o); } });
  return true;
}
function copyFallback(url) {
  const ta = D.createElement("textarea");
  ta.value = url; ta.setAttribute("readonly", ""); ta.style.cssText = "position:fixed;left:-9999px;top:0;opacity:0";
  D.body.append(ta); ta.select();
  let ok = false; try { ok = D.execCommand("copy"); } catch (e) { ok = false; }
  ta.remove();
  return ok;
}
function copy(url) {
  const done = () => { close(true); say(t("Link copied")); };
  const manual = () => {
    if (copyFallback(url)) { done(); return; }
    const id = "tca-sh-" + (++uid);
    show(head(id, t("Copy this link")) + `<p class="tca-sh-what">${esc(t("This browser would not copy it. Select the link and copy it yourself."))}</p>`
      + `<input class="tca-sh-url" type="text" readonly value="${esc(url)}" aria-label="${esc(t("The link"))}">`, id, ".tca-sh-url");
    const inp = box.querySelector(".tca-sh-url"); if (inp) inp.select();
  };
  try {
    if (navigator.clipboard && window.isSecureContext !== false) navigator.clipboard.writeText(url).then(done, manual);
    else manual();
  } catch (e) { manual(); }
}

/* ---------- the way in ---------- */
export function share(o, anchor) {
  o = norm(o);
  if (box && !box.hidden && anchor && anchor === opener) { close(true); return; }
  close(false);
  opener = anchor && anchor.nodeType === 1 ? anchor : null; cur = o;
  if (opener) { opener.setAttribute("aria-haspopup", "dialog"); }
  if (o.warn) { warnFirst(o); return; }
  if (isPhone() && native(o, opener)) return;
  menu(o);
}
function onClick(e) {
  if (e.defaultPrevented || e.button) return;
  const el = e.target.closest && e.target.closest("[data-share]");
  if (!el || el.matches(".sharebtn") || el.closest(".tca-sharebox")) return;      /* the federal page's own older buttons keep their own code */
  if (el.matches("[disabled],[aria-disabled='true']")) return;
  e.preventDefault();
  share(fromEl(el), el);
}
if (!window.__tcaShareOn) {
  window.__tcaShareOn = true;
  window.tcaShare = (o, anchor) => share(o, anchor);
  D.addEventListener("click", onClick);
  for (const el of D.querySelectorAll("[data-share]:not(.sharebtn)")) if (!el.hasAttribute("aria-haspopup")) el.setAttribute("aria-haspopup", "dialog");
  /* the stylesheet travels inside the shell's and the rider's own (so a button is drawn right from the first frame); a page
     with neither (the cabin) takes it from here */
  let has = false;
  try { has = getComputedStyle(H).getPropertyValue("--tca-share").trim() === "1"; } catch (e) {}
  if (!has) { const css = D.createElement("link"); css.rel = "stylesheet"; css.href = new URL("./share.1b1ceabafe.css", import.meta.url).href; D.head.append(css); }
}
