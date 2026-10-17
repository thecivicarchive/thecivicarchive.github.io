/* The Civic Archive: the ways into On The Ballot and into the record (John, 2026-10-11). Made like the night sky on the
   way into Election Night. The first time in a visit that a reader heads into On The Ballot from outside it, by any way in
   (the home page's doors, the top bar and its menus, the phone's tab bar, the page guide's links, the ring of cards'
   switch), they walk into a polling place in a school gym at dusk and feed a ballot into the scanner: ten seconds. The
   first time they head into the record (the federal side, a state's record pages, or the ring of cards) from outside it,
   they stand at a desk under the dome of the Library of Congress's Main Reading Room as a bound volume of the record opens:
   ten seconds. Later in the same visit, a quick fade into that space, with nothing to skip and nothing said (the page it
   opens speaks for itself).
   A click, a tap or any key skips at once, and a Skip button can be reached by keyboard. The browser keeps its own keys:
   a chord with Ctrl, Alt or Cmd (Back, Reload, closing the tab, zooming), the function keys and a modifier key alone do not
   skip. With motion off, Calm or the device's own reduced motion: one still picture and a plain fade. With no WebGL2 (or,
   for the polling place, no way to draw in light brighter than white), or files that take longer than 2.5 seconds: a fade,
   and the next way in tries again; a device that cannot draw a scene at all is never sent it. A device set to save data is
   never sent a scene (a quick fade); a lean one (little memory, few cores) gets it drawn lighter. Each scene is fetched only
   on the first hover, focus or tap of a way into its space, and only while this visit has not seen it. Going Back while a
   scene loads stops it for good: Forward brings back the page as it was. The links stay plain links, so without script
   they simply go. Nothing is sent anywhere.
   The two doors' own switches keep their charge and fireworks; their click hands the way in to this (window.__tcaGate).
   Pages on the whole shell and pages that keep their own top bar (through the rider) both load this. */

const D = document, H = D.documentElement;
const ROOT = new URL("../", import.meta.url);
const WAIT = 2500;
/* stay: the space's place to sit, from the site's root ("" when it is not built). "Stay here", beside Skip on the visit's
   first full crossing (John, 2026-10-11, as "Stay and watch the sky" on the way into Election Night), hands the view over
   to it: the reader goes on sitting or standing where the crossing left them, as long as they like */
const SPACES = {
  ballot: {crossing: "../pollingplace/crossing.bb06726be0.js", stay: "ballot/polling-place/", seen: "tca.ballot.crossed", arrive: "tca.ballot.arrive", label: "On the way to On The Ballot", float: true,
           say: "Walking into a polling place on the way to On The Ballot. Press any key to skip.", sayStay: " Or choose Stay here to sit in the polling place.",
           stayWhat: "sit in the polling place", light: "#F5F5F2", dark: "#0B0D11"},
  record: {crossing: "../recordroom/crossing.900bf0eae8.js", stay: "reading-room/", seen: "tca.record.crossed", arrive: "tca.record.arrive", label: "On the way to the record",
           say: "Stepping into a reading room on the way to the record. Press any key to skip.", sayStay: " Or choose Stay here to sit in the reading room.",
           stayWhat: "sit in the reading room", light: "#F5F5F2", dark: "#0F1114", start: "#0d0a07"}
};
const stayURL = s => SPACES[s].stay ? new URL(SPACES[s].stay, ROOT).href : "";
const session = {get: k => { try { return sessionStorage.getItem(k); } catch (e) { return null; } },
                 set: (k, v) => { try { sessionStorage.setItem(k, v); } catch (e) {} }};
const kept = k => { try { return localStorage.getItem(k); } catch (e) { return null; } };
/* what became of a crossing (played, skipped, a quick fade), said as a small event on the page; only the visit counting
   listens, and only when a counting service is configured and the reader's switch is on */
const tally = (s, what) => { try { D.dispatchEvent(new CustomEvent("tca:count", {detail: {event: "scene/" + s + "/" + what}})); } catch (e) {} };

/* which space an address on this site belongs to: On The Ballot (ballot/, the polling place in it), the record (us/, a
   state's two-letter folder, the ring of cards, the reading room), or none (the home page, Method, Access, Election Night, the cabin). Only pages count, never a file. */
function spaceOf(u) {
  if (u.origin !== location.origin || !u.pathname.startsWith(ROOT.pathname)) return null;
  const rel = decodeURIComponent(u.pathname.slice(ROOT.pathname.length));
  if (/^ballot(\/|$)/.test(rel)) return "ballot";
  if (rel === "rooms.html" || /^reading-room(\/|$)/.test(rel)) return "record";      /* the reading room is the record's place to sit */
  const m = /^([a-z]{2})(\/|$)/.exec(rel);
  if (m && m[1] !== "og") return "record";
  return null;
}
const isPage = u => /(\/|\.html)$/.test(u.pathname);
const here = () => spaceOf(new URL(location.href));
/* the space a link leads into from outside it, on this site, opened in this tab; or null */
function into(href) {
  let u;
  try { u = new URL(href, location.href); } catch (e) { return null; }
  if (!isPage(u)) return null;
  const s = spaceOf(u);
  return s && s !== here() && SPACES[s].crossing ? s : null;
}
function linkInto(a) {
  if (!a || !a.getAttribute("href") || (a.target && a.target !== "_self") || a.hasAttribute("download")) return null;
  return into(a.href);
}
const linkOf = e => { const t = e.target; return t && t.closest ? t.closest("a[href]") : null; };

/* no motion: the device asks for less, Motion is off on this page or the last, or Calm is on */
function stillNow() {
  try { if (matchMedia("(prefers-reduced-motion: reduce)").matches) return true; } catch (e) {}
  if (H.getAttribute("data-motion") === "reduced" || H.getAttribute("data-calm") === "on" || H.classList.contains("calm")) return true;
  let s = null;
  try { s = JSON.parse(kept("tca.a11y.v1") || "null"); } catch (e) {}
  if (s && s.calm === "on") return true;
  const m = kept("motion");
  if (m === "off") return true;
  return m !== "on" && !!s && s.motion === "reduced";
}
function saveData() { try { const c = navigator.connection; return !!(c && c.saveData); } catch (e) { return false; } }
function lean() {
  const v = H.getAttribute("data-lean");
  if (v) return v === "on";
  try { const n = navigator; return !!((n.deviceMemory && n.deviceMemory < 4) || (n.hardwareConcurrency && n.hardwareConcurrency <= 4)); } catch (e) { return false; }
}
/* can this device draw a scene at all: WebGL2, and for the polling place light brighter than white (float buffers), as the
   scenes themselves ask. Asked once; the context asked with is let go at once. A device that cannot is never sent the
   scene, which it could never draw: the way in is a fade */
let can = null;
function can3d(needFloat) {
  if (can === null) {
    can = {gl2: false, float: false};
    try {
      const g = window.WebGL2RenderingContext ? D.createElement("canvas").getContext("webgl2") : null;
      if (g) {
        can = {gl2: true, float: !!(g.getExtension("EXT_color_buffer_float") || g.getExtension("EXT_color_buffer_half_float"))};
        const x = g.getExtension("WEBGL_lose_context"); if (x) x.loseContext();
      }
    } catch (e) { can = {gl2: false, float: false}; }
  }
  return can.gl2 && (!needFloat || can.float);
}
/* the keys the browser keeps for itself pass through: a chord with Ctrl, Alt or Cmd, the function keys, the browser's and
   the media keys, and a modifier key alone */
const OWN = /^(?:F\d{1,2}|Browser\w*|AudioVolume\w*|Media\w*|Launch\w*|Shift|Control|Alt|AltGraph|Meta|CapsLock|Fn|FnLock|OS|NumLock|ScrollLock|Hyper|Super)$/;
const passes = e => e.ctrlKey || e.altKey || e.metaKey || OWN.test(e.key || "");
/* the colour the space's pages open in: light unless the reader chose dark there */
const toColour = s => kept("theme") === "dark" ? SPACES[s].dark : SPACES[s].light;
/* this page's own colour, so the veil rises out of it */
function pageColour() {
  try {
    for (const el of [D.body, H]) {
      const c = getComputedStyle(el).backgroundColor;
      if (c && c !== "transparent" && !/rgba\([^)]*,\s*0\)$/.test(c)) return c;
    }
  } catch (e) {}
  return "#F5F5F2";
}

const mods = {};
function load(s) {
  if (saveData() || !SPACES[s] || !SPACES[s].crossing || !can3d(SPACES[s].float)) return Promise.resolve(null);
  return mods[s] || (mods[s] = import(new URL(SPACES[s].crossing, import.meta.url).href)
    .then(m => { warmUp(m, s); return m; }).catch(() => { delete mods[s]; return null; }));
}
const warmUp = (m, s) => { try { (s === "record" ? m.prepare({lean: lean()}) : m.prepare()).catch(() => {}); } catch (e) {} };
const prepared = (m, s) => s === "record" ? m.prepare({lean: lean()}) : m.prepare();

/* the veil the scene is drawn on, with Skip and a sentence for screen readers; for a quick fade only the colour */
let style = null;
function veil(s, bg, quick) {
  if (!style) {
    style = D.createElement("style");
    style.textContent = ".tca-sv{position:fixed;inset:0;z-index:2147483000;opacity:0;transition:opacity .35s ease,background-color .4s ease;overflow:hidden;cursor:pointer}"
      + ".tca-sv.on{opacity:1}.tca-sv.quick{cursor:default}"
      + ".tca-sv-bar{position:absolute;left:16px;right:16px;bottom:calc(16px + env(safe-area-inset-bottom));z-index:2;display:flex;flex-wrap:wrap;justify-content:flex-end;align-items:center;gap:10px;pointer-events:none}"
      + ".tca-sv-bar button{pointer-events:auto;min-height:44px;border-radius:999px;font:650 15px/1 system-ui,-apple-system,'Segoe UI',sans-serif;letter-spacing:.02em;cursor:pointer;color:#F3E8D3;"
      + "-webkit-backdrop-filter:blur(6px);backdrop-filter:blur(6px)}"
      + ".tca-sv-skip{min-width:88px;padding:0 20px;border:1px solid rgba(243,232,211,.55);background:rgba(8,10,14,.55)}"
      + ".tca-sv-skip:hover{border-color:#C9944A;background:rgba(20,16,10,.72)}"
      + ".tca-sv-bar button:focus-visible{outline:3px solid #C9944A;outline-offset:3px}"
      + ".tca-sv-bar small{display:block;font-size:11px;font-weight:500;opacity:.75;margin-top:3px}"
      + ".tca-sv-stay{display:inline-flex;align-items:center;gap:9px;padding:0 20px 0 12px;text-align:left;border:1.5px solid rgba(201,148,74,.9);background:rgba(10,12,18,.62);"
      + "box-shadow:0 0 16px 1px rgba(201,148,74,.3);transition:box-shadow .3s ease,background .3s ease}"
      + ".tca-sv-stay svg{width:24px;height:24px;flex:none;color:#F4EBD4;fill:none;stroke:currentColor;stroke-width:1.6;stroke-linecap:round;stroke-linejoin:round}"
      + ".tca-sv-stay:hover{background:rgba(24,19,12,.8);box-shadow:0 0 26px 4px rgba(201,148,74,.45)}"
      + ".tca-sv-say{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}"
      + "@media (max-width:360px){.tca-sv-bar button{font-size:14px}.tca-sv-stay{padding:0 14px 0 9px;gap:7px}.tca-sv-skip{min-width:76px;padding:0 14px}}"
      + "@media (forced-colors:active){.tca-sv-bar button{border:2px solid ButtonText;background:ButtonFace;color:ButtonText;box-shadow:none}}"
      + "@media (prefers-reduced-motion: reduce){.tca-sv{transition-duration:.25s}.tca-sv-stay{transition:none}}";
    D.head.append(style);
  }
  const h = D.createElement("div");
  h.className = "tca-sv"; h.style.background = bg;
  const show = () => h.classList.add("on");
  if (quick) {
    h.classList.add("quick"); h.setAttribute("aria-hidden", "true");
    D.body.append(h); requestAnimationFrame(show); setTimeout(show, 60);
    return {h, bar: null, skip: null, stay: null};
  }
  h.setAttribute("role", "dialog"); h.setAttribute("aria-modal", "true"); h.setAttribute("aria-label", SPACES[s].label);
  const bar = D.createElement("div");
  bar.className = "tca-sv-bar";
  let stay = null;
  if (stayURL(s)) {
    stay = D.createElement("button");
    stay.type = "button"; stay.className = "tca-sv-stay"; stay.setAttribute("data-stay", "");
    stay.innerHTML = SEAT + `<span>Stay here<small>${SPACES[s].stayWhat}</small></span>`;
    bar.append(stay);
  }
  const skip = D.createElement("button");
  skip.type = "button"; skip.className = "tca-sv-skip";
  skip.innerHTML = "Skip<small>or press any key</small>";
  bar.append(skip);
  const say = D.createElement("p");
  say.className = "tca-sv-say"; say.setAttribute("aria-live", "polite");
  h.append(bar, say);
  D.body.append(h);
  requestAnimationFrame(show); setTimeout(show, 60);      /* a window that draws no frames still shows it */
  try { skip.focus({preventScroll: true}); } catch (e) { skip.focus(); }
  setTimeout(() => { say.textContent = SPACES[s].say + (stay ? SPACES[s].sayStay : ""); }, 120);
  return {h, bar, skip, stay};
}
/* a chair, for Stay here */
const SEAT = '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M7 3.5h10l-1 8.5H8z"/><path d="M5.5 12h13v3h-13z"/><path d="M7 15v5.5M17 15v5.5"/></svg>';

/* gen counts the crossings begun here and the returns to this page by Back or Forward: a crossing whose number is no longer
   the latest does nothing more */
let busy = false, gen = 0, ending = null;
function go(s, url, how) { session.set(SPACES[s].arrive, how); location.href = url; }
function cross(s, url) {
  if (busy) return;
  busy = true;
  const my = ++gen, live = () => my === gen;
  const S = SPACES[s], to = toColour(s);
  const first = !session.get(S.seen), quick = !first || saveData();
  /* later in the same visit, or for a reader saving data: a quick fade into the space's own colour */
  if (quick) { tally(s, "quick"); veil(s, to, true); setTimeout(() => { if (live()) go(s, url, "quick"); }, 380); return; }
  const from = pageColour(), V = veil(s, S.start || from), host = V.h;
  /* the visit's one crossing counts as seen once it plays, or once the reader skips it; a fade for slow files or a device
     that cannot draw it leaves it for the next way in */
  let phase = "loading", ctl = null, over = false;
  const place = stayURL(s);
  const leave = () => { phase = "gone"; removeEventListener("keydown", onKey, true); };
  const fade = how => { if (phase !== "loading") return; leave(); tally(s, "faded"); host.style.background = to; setTimeout(() => { if (live()) go(s, url, how); }, 420); };
  const skipNow = () => {
    if (phase === "playing") { leave(); tally(s, "skipped"); ctl.skip(); return; }
    if (phase !== "loading") return;
    leave(); tally(s, "skipped"); session.set(S.seen, "1"); go(s, url, "skip");
  };
  /* Stay here: once the scene plays, it hands its view over to the place (this tab only) and goes there; before it is
     drawn, the place's own page draws the room */
  const stayNow = () => {
    if (!place) return;
    if (phase === "playing" && ctl.stay) { leave(); tally(s, "stayed"); ctl.stay(); return; }
    if (phase !== "loading" && phase !== "playing") return;
    leave(); tally(s, "stayed"); session.set(S.seen, "1"); location.href = place;
  };
  /* the keyboard, for the whole crossing (the scene is told not to listen): Tab moves between the buttons, Enter or Space
     on Stay here stays, the browser's own keys pass through, and any other key skips */
  function onKey(e) {
    if (phase === "gone" || passes(e)) return;
    if (e.key === "Tab") {
      const order = [V.stay, V.skip].filter(Boolean), i = order.indexOf(D.activeElement);
      e.preventDefault();
      const next = order[(i + (e.shiftKey ? order.length - 1 : 1)) % order.length] || order[0];
      try { next.focus({preventScroll: true}); } catch (x) { next.focus(); }
      return;
    }
    if (V.stay && D.activeElement === V.stay && (e.key === "Enter" || e.key === " " || e.key === "Spacebar")) { e.preventDefault(); stayNow(); return; }
    e.preventDefault(); skipNow();
  }
  addEventListener("keydown", onKey, true);
  /* Stay here keeps its own presses: the veil's "anywhere skips" never sees them */
  if (V.stay) {
    V.stay.addEventListener("pointerdown", e => e.stopPropagation());
    V.stay.addEventListener("click", e => { e.stopPropagation(); stayNow(); });
    V.stay.addEventListener("pointerenter", () => { over = true; });
    V.stay.addEventListener("pointerleave", () => { over = false; });
  }
  host.addEventListener("pointerdown", e => { if (e.target && e.target.closest && e.target.closest("[data-stay]")) return; if (e.button === 0 || e.pointerType !== "mouse") skipNow(); });
  host.addEventListener("click", e => { if (e.target && e.target.closest && e.target.closest("[data-stay]")) return; skipNow(); });
  const timer = setTimeout(() => fade("quick"), WAIT);      /* slow files: a fade, never a wait */
  ending = () => { clearTimeout(timer); leave(); };      /* gone Back: this crossing ends here */
  /* a still picture's end: the room gives way to the space's own colour */
  const out = () => { host.style.background = to; for (const el of host.children) if (el !== V.bar) { el.style.transition = "opacity .4s ease"; el.style.opacity = 0; } };
  load(s).then(m => m ? prepared(m, s).then(A => ({m, A})) : null).then(r => {
    if (phase !== "loading" || !live()) return;
    clearTimeout(timer);
    if (!r) { fade("quick"); return; }
    let ok = false;
    try {
      const still = stillNow(), lite = lean();
      /* the gate keeps the keys (keys: false); stay and hold only when the place is built */
      const both = {host, assets: r.A, still, lean: lite, fade: out, keys: false};
      if (place) Object.assign(both, {stay: place, hold: () => over || D.activeElement === V.stay});
      ok = s === "record"
        ? r.m.run(url, Object.assign(both, {start: S.start, end: to}))
        : r.m.run(url, Object.assign(both, {from, to, arrive: S.arrive, go: how => { if (live()) go(s, url, how); }}));
    } catch (e) { ok = false; }
    if (ok) { ctl = typeof ok === "object" ? ok : {skip: () => go(s, url, "skip"), stay: null}; phase = "playing"; session.set(S.seen, "1"); tally(s, "played"); }
    else fade("quick");      /* no WebGL here: a fade */
  }).catch(() => fade("quick"));
}

function wire() {
  const warm = e => { const a = linkOf(e), s = a && linkInto(a); if (s && !session.get(SPACES[s].seen)) load(s); };
  D.addEventListener("pointerover", warm, {capture: true, passive: true});
  D.addEventListener("focusin", warm, {capture: true});
  D.addEventListener("pointerdown", warm, {capture: true, passive: true});
  D.addEventListener("touchstart", warm, {capture: true, passive: true});
  D.addEventListener("click", e => {
    if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    const a = linkOf(e);
    if (!a || a.hasAttribute("data-gate-own")) return;      /* a door's switch keeps its fireworks and hands over itself */
    const s = linkInto(a);
    if (!s) return;
    e.preventDefault(); e.stopImmediatePropagation();
    cross(s, a.href);
  }, true);
  /* back from the other side, or Forward again after going Back while a scene loaded: the page, not the scene, and
     nothing goes on into the space (this comes before any timer the page had waiting) */
  addEventListener("pageshow", e => {
    if (!e.persisted) return;
    gen++; if (ending) { ending(); ending = null; }
    busy = false;
    for (const v of D.querySelectorAll(".tca-sv")) v.remove();
  });
}
if (D.readyState === "loading") D.addEventListener("DOMContentLoaded", wire, {once: true}); else wire();
/* how the reader arrived is read by the page they land on as its own script starts (the two doors fade in softly); by
   now that has happened, and a mark left over would mislead a later page */
for (const s in SPACES) { try { sessionStorage.removeItem(SPACES[s].arrive); } catch (e) {} }

/* for a door's own switch: start the way into the space url leads to, if it leads into one from outside; false if not
   (the door then goes its own way). warm(url) fetches the scene ahead. */
window.__tcaGate = {
  warm: url => { const s = into(url); if (s && !session.get(SPACES[s].seen)) load(s); },
  cross: url => { const s = into(url); if (!s) return false; cross(s, new URL(url, location.href).href); return true; }
};
/* for checking: a still frame of either scene (the page is not changed), and the visit's first-time marks */
window.__spaces = {
  load, stillNow, into, can3d, seen: s => !!session.get(SPACES[s].seen), forget: s => { try { sessionStorage.removeItem(SPACES[s].seen); } catch (e) {} },
  still: (s, t, w, h, o) => load(s).then(m => m && prepared(m, s).then(() => m.still(t, w, h, o)))
};
