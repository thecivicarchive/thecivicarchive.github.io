/* The Civic Archive: the way into Election Night (John, 2026-10-10). The first time in a visit that a reader heads into
   Election Night, by any way in (the switch near the top of the home page, the top bar's link, the phone's Results tab,
   the page guide's links, the Election Night door), they step outside: ten seconds on the cabin's deck under the night
   sky. The scene is fetched only on the first hover, focus or tap of a way in, and only while this visit has not seen it.
   Later in the same visit, a quick fade, with nothing to skip and nothing said (the page it opens speaks for itself).
   A click, a tap or any key skips at once, and a Skip button can be reached by keyboard. Beside it, "Stay and watch the
   sky" (John, 2026-10-11) keeps the reader on the deck instead: Election Night's own page for it, the view carried over,
   as long as they like. Tab moves between the two buttons; any other key skips. The browser keeps its own keys: a chord
   with Ctrl, Alt or Cmd (Back, Reload, closing the tab, zooming), the function keys and a modifier key alone do not skip.
   With motion off, Calm or the device's own reduced motion: one still picture and a plain fade (it waits while the reader
   reaches for Stay). With no WebGL2, or files that take longer than 2.5 seconds: a fade, and the next way in tries again;
   a device that cannot draw it at all is never sent the scene. A device set to save data is never sent the scene (a quick
   fade); a lean one (little memory, few cores) gets it drawn lighter. Going Back while it plays stops it for good: Forward
   brings back the page as it was. The links stay plain links, so without script they simply go. Nothing is sent anywhere.
   Pages on the whole shell and pages that keep their own top bar (through the rider) both load this. */

const CROSSING = "../nightsky/crossing.abac3c9bab.js";
const D = document, H = D.documentElement;
const ROOT = new URL("../", import.meta.url), NIGHT = new URL("night/", ROOT), DECK = new URL("sky/", NIGHT);
const SEEN = "tca.night.crossed", ARRIVE = "tca.night.arrive", WAIT = 2500;
const session = {get: k => { try { return sessionStorage.getItem(k); } catch (e) { return null; } },
                 set: (k, v) => { try { sessionStorage.setItem(k, v); } catch (e) {} }};
const kept = k => { try { return localStorage.getItem(k); } catch (e) { return null; } };
/* what became of a crossing (played, skipped, stayed, a quick fade), said as a small event on the page; only the visit
   counting listens, and only when a counting service is configured and the reader's switch is on */
const tally = what => { try { D.dispatchEvent(new CustomEvent("tca:count", {detail: {event: "scene/night/" + what}})); } catch (e) {} };

const inside = () => location.pathname.startsWith(NIGHT.pathname);
/* a link to Election Night's home, on this site, opened in this tab */
function intoNight(a) {
  if (!a || !a.getAttribute("href") || (a.target && a.target !== "_self") || a.hasAttribute("download")) return false;
  let u;
  try { u = new URL(a.href, location.href); } catch (e) { return false; }
  return u.origin === location.origin && (u.pathname === NIGHT.pathname || u.pathname === NIGHT.pathname + "index.html");
}
const linkOf = e => { const t = e.target; return t && t.closest ? t.closest("a[href]") : null; };
/* no motion: the device asks for less, Motion is off on this page or the last, or Calm is on */
export function stillNow() {
  try { if (matchMedia("(prefers-reduced-motion: reduce)").matches) return true; } catch (e) {}
  if (H.getAttribute("data-motion") === "reduced" || H.getAttribute("data-calm") === "on" || H.classList.contains("calm")) return true;
  let s = null;
  try { s = JSON.parse(kept("tca.a11y.v1") || "null"); } catch (e) {}
  if (s && s.calm === "on") return true;
  const m = kept("motion");
  if (m === "off") return true;
  return m !== "on" && !!s && s.motion === "reduced";
}

/* a reader who asked their device to save data is never sent the scene (about two and a half megabytes): a quick fade */
function saveData() { try { const c = navigator.connection; return !!(c && c.saveData); } catch (e) { return false; } }
/* a lean device (little memory or few cores) gets the light version: the same scene, drawn with fewer pixels. Pages on
   the whole shell say so on <html>; pages that keep their own top bar do not, so the device is asked as the shell asks */
function lean() {
  const v = H.getAttribute("data-lean");
  if (v) return v === "on";
  try { const n = navigator; return !!((n.deviceMemory && n.deviceMemory < 4) || (n.hardwareConcurrency && n.hardwareConcurrency <= 4)); } catch (e) { return false; }
}
/* can this device draw the night at all (WebGL2)? Asked once; the context asked with is let go at once. A device that
   cannot is never sent the scene, which it could never draw: the way in is a fade */
let can = null;
function can3d() {
  if (can === null) {
    try {
      const g = window.WebGL2RenderingContext ? D.createElement("canvas").getContext("webgl2") : null;
      can = !!g;
      if (g) { const x = g.getExtension("WEBGL_lose_context"); if (x) x.loseContext(); }
    } catch (e) { can = false; }
  }
  return can;
}
/* the keys the browser keeps for itself pass through: a chord with Ctrl, Alt or Cmd, the function keys, the browser's and
   the media keys, and a modifier key alone */
const OWN = /^(?:F\d{1,2}|Browser\w*|AudioVolume\w*|Media\w*|Launch\w*|Shift|Control|Alt|AltGraph|Meta|CapsLock|Fn|FnLock|OS|NumLock|ScrollLock|Hyper|Super)$/;
const passes = e => e.ctrlKey || e.altKey || e.metaKey || OWN.test(e.key || "");

let mod = null;
const load = () => saveData() || !can3d() ? Promise.resolve(null) : mod || (mod = (CROSSING ? import(CROSSING) : Promise.reject(new Error("no crossing")))
  .then(m => { m.prepare().catch(() => {}); return m; }).catch(() => null));

/* the veil the night is drawn on: night black, with Skip, Stay and watch the sky, and a sentence for screen readers. For
   a quick fade it is only the colour: nothing to skip, nothing to say */
const MOON = '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><circle cx="11" cy="13" r="7.2" fill="currentColor" opacity=".16"/>'
  + '<path fill="currentColor" d="M11 5.8A7.2 7.2 0 1 0 17.65 15.77A6 6 0 0 1 11 5.8z"/><path d="M19.6 2.9v3.2M18 4.5h3.2" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/></svg>';
let style = null;
function veil(quick) {
  if (!style) {
    style = D.createElement("style");
    style.textContent = ".tca-nv{position:fixed;inset:0;z-index:2147483000;background:#010203;opacity:0;transition:opacity .35s ease;overflow:hidden;cursor:pointer}"
      + ".tca-nv.on{opacity:1}.tca-nv.quick{cursor:default}"
      + ".tca-nv-bar{position:absolute;left:16px;right:16px;bottom:calc(16px + env(safe-area-inset-bottom));z-index:2;display:flex;flex-wrap:wrap;justify-content:flex-end;align-items:center;gap:10px;pointer-events:none}"
      + ".tca-nv-bar button{pointer-events:auto;min-height:44px;border-radius:999px;font:650 15px/1 system-ui,-apple-system,'Segoe UI',sans-serif;letter-spacing:.02em;cursor:pointer;"
      + "-webkit-backdrop-filter:blur(6px);backdrop-filter:blur(6px);color:#F3E8D3}"
      + ".tca-nv-skip{min-width:88px;padding:0 20px;border:1px solid rgba(243,232,211,.5);background:rgba(8,10,14,.5)}"
      + ".tca-nv-skip:hover{border-color:#C9944A;background:rgba(20,16,10,.7)}"
      + ".tca-nv-bar button:focus-visible{outline:3px solid #C9944A;outline-offset:3px}"
      + ".tca-nv-skip small{display:block;font-size:11px;font-weight:500;opacity:.75;margin-top:3px}"
      + ".tca-nv-stay{display:inline-flex;align-items:center;gap:9px;padding:0 20px 0 12px;border:1.5px solid rgba(201,148,74,.9);background:rgba(10,12,18,.62);"
      + "box-shadow:0 0 16px 1px rgba(201,148,74,.3);transition:box-shadow .3s ease,background .3s ease}"
      + ".tca-nv-stay svg{width:24px;height:24px;flex:none;color:#F4EBD4}"
      + ".tca-nv-stay:hover{background:rgba(24,19,12,.8);box-shadow:0 0 26px 4px rgba(201,148,74,.45)}"
      + ".tca-nv-say{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}"
      + "@media (max-width:360px){.tca-nv-bar button{font-size:14px}.tca-nv-stay{padding:0 14px 0 9px;gap:7px}.tca-nv-skip{min-width:76px;padding:0 14px}}"
      + "@media (forced-colors:active){.tca-nv-bar button{border:2px solid ButtonText;background:ButtonFace;color:ButtonText;box-shadow:none}}"
      + "@media (prefers-reduced-motion: reduce){.tca-nv{transition-duration:.25s}.tca-nv-stay{transition:none}}";
    D.head.append(style);
  }
  const h = D.createElement("div");
  h.className = "tca-nv";
  const show = () => h.classList.add("on");
  if (quick) {
    h.classList.add("quick"); h.setAttribute("aria-hidden", "true");
    D.body.append(h); requestAnimationFrame(show); setTimeout(show, 60);
    return {h, skip: null, stay: null};
  }
  h.setAttribute("role", "dialog"); h.setAttribute("aria-modal", "true"); h.setAttribute("aria-label", "On the way to Election Night");
  const bar = D.createElement("div");
  bar.className = "tca-nv-bar";
  const stay = D.createElement("button");
  stay.type = "button"; stay.className = "tca-nv-stay"; stay.setAttribute("data-stay", "");
  stay.innerHTML = MOON + "<span>Stay and watch the sky</span>";
  const skip = D.createElement("button");
  skip.type = "button"; skip.className = "tca-nv-skip";
  skip.innerHTML = "Skip<small>or press any key</small>";
  bar.append(stay, skip);
  const say = D.createElement("p");
  say.className = "tca-nv-say"; say.setAttribute("aria-live", "polite");
  h.append(bar, say);
  D.body.append(h);
  requestAnimationFrame(show); setTimeout(show, 60);      /* a window that draws no frames still shows it */
  try { skip.focus({preventScroll: true}); } catch (e) { skip.focus(); }
  setTimeout(() => { say.textContent = "Stepping outside on the way to Election Night. Press any key to skip, or choose Stay and watch the sky to stay out on the deck."; }, 120);
  return {h, skip, stay};
}

/* gen counts the crossings begun here and the returns to this page by Back or Forward: a crossing whose number is no longer
   the latest does nothing more */
let busy = false, gen = 0, ending = null;
function go(url, how) { session.set(ARRIVE, how); location.href = url; }
function cross(url) {
  if (busy) return;
  busy = true;
  const my = ++gen, live = () => my === gen;
  const first = !session.get(SEEN), quick = !first || saveData();
  const V = veil(quick), host = V.h;
  /* later in the same visit, or for a reader saving data: a quick fade */
  if (quick) { tally("quick"); setTimeout(() => { if (live()) go(url, "quick"); }, 380); return; }
  /* the visit's one crossing counts as seen once it plays, or once the reader skips it or stays; a fade for slow files or
     a device that cannot draw it leaves it for the next way in */
  let phase = "loading", ctl = null, over = false;
  const leave = () => { phase = "gone"; removeEventListener("keydown", onKey, true); };
  const fade = how => { if (phase !== "loading") return; leave(); tally("faded"); setTimeout(() => { if (live()) go(url, how); }, 380); };
  const skipNow = () => {
    if (phase === "playing") { leave(); tally("skipped"); ctl.skip(); return; }
    if (phase !== "loading") return;
    leave(); tally("skipped"); session.set(SEEN, "1"); go(url, "skip");
  };
  const stayNow = () => {
    if (phase === "playing" && ctl.stay) { leave(); tally("stayed"); ctl.stay(); return; }
    if (phase !== "loading") return;
    leave(); tally("stayed"); session.set(SEEN, "1"); location.href = DECK.href;      /* the night was not drawn yet: the deck's own page draws it */
  };
  /* the keyboard, for the whole crossing: Tab moves between the two buttons, Enter or Space on Stay stays, the browser's
     own keys pass through, and any other key skips */
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
  /* the Stay button keeps its own presses: the veil's own "anywhere skips" never sees them */
  V.stay.addEventListener("pointerdown", e => e.stopPropagation());
  V.stay.addEventListener("click", e => { e.stopPropagation(); stayNow(); });
  V.stay.addEventListener("pointerenter", () => { over = true; });
  V.stay.addEventListener("pointerleave", () => { over = false; });
  host.addEventListener("pointerdown", e => { if (e.button === 0 || e.pointerType !== "mouse") skipNow(); });
  host.addEventListener("click", skipNow);
  const timer = setTimeout(() => fade("quick"), WAIT);      /* slow files: a fade, never a wait */
  ending = () => { clearTimeout(timer); leave(); };      /* gone Back: this crossing ends here */
  load().then(m => m ? m.prepare().then(A => ({m, A})) : null).then(r => {
    if (phase !== "loading" || !live()) return;
    clearTimeout(timer);
    if (!r) { fade("quick"); return; }
    let ok = null;
    try {
      ok = r.m.run(url, {host, assets: r.A, still: stillNow(), lean: lean(), keys: false, stay: DECK.href,
        hold: () => over || D.activeElement === V.stay,
        fade: () => { const c = host.querySelector("canvas"); if (c) { c.style.transition = "opacity .4s ease"; c.style.opacity = 0; } }});
    } catch (e) { ok = null; }
    if (ok) { ctl = typeof ok === "object" ? ok : {skip: () => go(url, "skip"), stay: null}; phase = "playing"; session.set(SEEN, "1"); tally("played"); }
    else fade("quick");      /* no WebGL here: a fade */
  }).catch(() => fade("quick"));
}

function wire() {
  if (inside()) return;      /* already in Election Night */
  const warm = e => { const a = linkOf(e); if (a && intoNight(a) && !session.get(SEEN)) load(); };
  D.addEventListener("pointerover", warm, {capture: true, passive: true});
  D.addEventListener("focusin", warm, {capture: true});
  D.addEventListener("pointerdown", warm, {capture: true, passive: true});
  D.addEventListener("touchstart", warm, {capture: true, passive: true});
  D.addEventListener("click", e => {
    if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    const a = linkOf(e);
    if (!a || !intoNight(a)) return;
    e.preventDefault(); e.stopImmediatePropagation();
    cross(a.href);
  }, true);
  /* back from Election Night, or Forward again after going Back while the night played or loaded: the page, not the
     night, and nothing goes on to Election Night (this comes before any timer the page had waiting) */
  addEventListener("pageshow", e => {
    if (!e.persisted) return;
    gen++; if (ending) { ending(); ending = null; }
    busy = false;
    for (const v of D.querySelectorAll(".tca-nv")) v.remove();
  });
}
if (D.readyState === "loading") D.addEventListener("DOMContentLoaded", wire, {once: true}); else wire();

/* for checking: what the crossing works out about tonight's sky, and a still frame (the page is not changed) */
window.__night = {
  load, stillNow, can3d, seen: () => !!session.get(SEEN), forget: () => { try { sessionStorage.removeItem(SEEN); } catch (e) {} },
  facts: o => load().then(m => m && m.facts(o)), still: (t, w, h, o) => load().then(m => m && m.still(t, w, h, o))
};
