/* The way into the notebook (sandbox, John 2026-11-10). Made like the site's other gates (shell_src/spacegate.js): the
   first time in a visit that a reader follows a notebook link (a.nbl or a[data-nb], leading into ../notebook/#...) the
   page gives way to a reading room where a leather notebook on the desk opens to the page they asked for, about three and
   a half seconds, and then the browser goes there. Later in the same visit, a quick fade. A click, a tap or any key skips
   at once, and a Skip button can be reached by keyboard; the browser's own keys (a chord with Ctrl, Alt or Cmd, the
   function keys, a modifier alone) pass through. With Motion not on full, Calm on, or the device's own reduced motion: one
   still picture and a plain fade. A device set to save data, one with no WebGL2, or files that take longer than 2.5
   seconds: a plain fade (and the next way in tries again). Going Back while it loads or plays stops it for good; Forward
   brings the page back as it was. Ctrl, Cmd, Shift and middle clicks, and links opening new tabs, are left alone. The
   links stay plain links: if anything here fails, the browser simply goes. Nothing is sent anywhere, and nothing loads
   from another server. While it plays the page's content is marked inert behind the scene, which has a name for assistive
   technology.
   window.__nbGate: play(opts) runs the scene in place and resolves with how it ended (the demo page); cross(href, {force})
   starts the way to href; warm() fetches the scene ahead; seen(), forget(); still(t, w, h, opts) draws one frame. */
const D = document, H = D.documentElement;
const SEEN = "tca.nb.crossed", WAIT = 2500, LABEL = "On the way to the notebook";
const SAY = "Opening the notebook on the way to the page. Press any key to skip.";
const session = {get: k => { try { return sessionStorage.getItem(k); } catch (e) { return null; } },
                 set: (k, v) => { try { sessionStorage.setItem(k, v); } catch (e) {} },
                 del: k => { try { sessionStorage.removeItem(k); } catch (e) {} }};
const kept = k => { try { return localStorage.getItem(k); } catch (e) { return null; } };

/* no motion: the device asks for less, Motion is not on full, or Calm is on */
function stillNow() {
  try { if (matchMedia("(prefers-reduced-motion: reduce)").matches) return true; } catch (e) {}
  const m = H.getAttribute("data-motion");
  if (m && m !== "full") return true;
  if (H.getAttribute("data-calm") === "on" || H.classList.contains("calm")) return true;
  let s = null;
  try { s = JSON.parse(kept("tca.a11y.v1") || "null"); } catch (e) {}
  if (s && (s.calm === "on" || (s.motion && s.motion !== "full"))) return true;
  return kept("motion") === "off";
}
function saveData() { try { const c = navigator.connection; return !!(c && c.saveData); } catch (e) { return false; } }
function lean() {
  const v = H.getAttribute("data-lean");
  if (v) return v === "on";
  try { const n = navigator; return !!((n.deviceMemory && n.deviceMemory < 4) || (n.hardwareConcurrency && n.hardwareConcurrency <= 4)); } catch (e) { return false; }
}
let can = null;
function can3d() {
  if (can === null) {
    can = false;
    try {
      const g = window.WebGL2RenderingContext ? D.createElement("canvas").getContext("webgl2") : null;
      if (g) { can = true; const x = g.getExtension("WEBGL_lose_context"); if (x) x.loseContext(); }
    } catch (e) { can = false; }
  }
  return can;
}
const OWN = /^(?:F\d{1,2}|Browser\w*|AudioVolume\w*|Media\w*|Launch\w*|Shift|Control|Alt|AltGraph|Meta|CapsLock|Fn|FnLock|OS|NumLock|ScrollLock|Hyper|Super)$/;
const passes = e => e.ctrlKey || e.altKey || e.metaKey || OWN.test(e.key || "");
function pageColour() {
  try {
    for (const el of [D.body, H]) {
      const c = getComputedStyle(el).backgroundColor;
      if (c && c !== "transparent" && !/rgba\([^)]*,\s*0\)$/.test(c)) return c;
    }
  } catch (e) {}
  return "#F5F5F2";
}

/* a notebook link: a.nbl or a[data-nb], leading to a notebook page (../notebook/#...) on this site in this tab, from
   another page; or null */
function notebookLink(a) {
  if (!a || !a.getAttribute("href") || (a.target && a.target !== "_self") || a.hasAttribute("download")) return null;
  if (!(a.classList.contains("nbl") || a.hasAttribute("data-nb"))) return null;
  let u;
  try { u = new URL(a.href, location.href); } catch (e) { return null; }
  if (u.origin !== location.origin || !/\/notebook\/(index\.html)?$/.test(u.pathname) || u.pathname === location.pathname) return null;
  const path = a.getAttribute("data-nb") || decodeURIComponent(u.hash.replace(/^#/, "")).split("&")[0];
  return {href: u.href, path, title: (a.textContent || "").replace(/\s+/g, " ").trim()};
}
const linkOf = e => { const t = e.target; return t && t.closest ? t.closest("a[href]") : null; };

let mod = null, assets = null;
function load() {
  if (saveData() || !can3d()) return Promise.resolve(null);
  if (!mod) {
    mod = import(new URL("./notebook3d.js", import.meta.url).href).then(m => { try { assets = m.prepare({lean: lean()}); assets.catch(() => { assets = null; }); } catch (e) {} return m; })
      .catch(() => { mod = null; return null; });
  }
  return mod;
}
const prepared = m => assets || (assets = m.prepare({lean: lean()}));

/* the veil the scene is drawn on, with Skip and a sentence for screen readers; for a quick fade only the colour */
let style = null;
function veil(bg, quick) {
  if (!style) {
    style = D.createElement("style");
    style.textContent = ".tca-nbv{position:fixed;inset:0;z-index:2147483000;opacity:0;transition:opacity .32s ease,background-color .4s ease;overflow:hidden;cursor:pointer}"
      + ".tca-nbv.on{opacity:1}.tca-nbv.quick{cursor:default}"
      + ".tca-nbv-bar{position:absolute;left:16px;right:16px;bottom:calc(16px + env(safe-area-inset-bottom));z-index:2;display:flex;justify-content:flex-end;align-items:center;gap:10px;pointer-events:none}"
      + ".tca-nbv-bar button{pointer-events:auto;min-height:44px;min-width:88px;padding:0 20px;border-radius:999px;font:650 15px/1 system-ui,-apple-system,'Segoe UI',sans-serif;letter-spacing:.02em;cursor:pointer;color:#F3E8D3;"
      + "border:1px solid rgba(243,232,211,.55);background:rgba(8,10,14,.55);-webkit-backdrop-filter:blur(6px);backdrop-filter:blur(6px)}"
      + ".tca-nbv-bar button:hover{border-color:#C9944A;background:rgba(20,16,10,.72)}.tca-nbv-bar button:focus-visible{outline:3px solid #C9944A;outline-offset:3px}"
      + ".tca-nbv-bar small{display:block;font-size:11px;font-weight:500;opacity:.75;margin-top:3px}"
      + ".tca-nbv-say{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}"
      + "@media (forced-colors:active){.tca-nbv-bar button{border:2px solid ButtonText;background:ButtonFace;color:ButtonText}}"
      + "@media (prefers-reduced-motion: reduce){.tca-nbv{transition-duration:.25s}}";
    D.head.append(style);
  }
  const h = D.createElement("div");
  h.className = "tca-nbv"; h.style.background = bg;
  const show = () => h.classList.add("on");
  if (quick) {
    h.classList.add("quick"); h.setAttribute("aria-hidden", "true");
    D.body.append(h); requestAnimationFrame(show); setTimeout(show, 60);
    return {h, skip: null};
  }
  h.setAttribute("role", "dialog"); h.setAttribute("aria-modal", "true"); h.setAttribute("aria-label", LABEL);
  const bar = D.createElement("div"); bar.className = "tca-nbv-bar";
  const skip = D.createElement("button"); skip.type = "button"; skip.innerHTML = "Skip<small>or press any key</small>";
  bar.append(skip);
  const say = D.createElement("p"); say.className = "tca-nbv-say"; say.setAttribute("aria-live", "polite");
  h.append(bar, say);
  D.body.append(h);
  requestAnimationFrame(show); setTimeout(show, 60);
  try { skip.focus({preventScroll: true}); } catch (e) { skip.focus(); }
  setTimeout(() => { say.textContent = SAY; }, 120);
  return {h, skip};
}
/* the page behind the scene is marked inert while it plays, and given back after */
let inerted = [];
function shut(host) {
  inerted = [];
  try { for (const el of Array.from(D.body.children)) if (el !== host && !el.hasAttribute("inert") && el.tagName !== "SCRIPT" && el.tagName !== "STYLE") { el.setAttribute("inert", ""); inerted.push(el); } } catch (e) {}
}
function reopen() { for (const el of inerted) { try { el.removeAttribute("inert"); } catch (e) {} } inerted = []; }

/* gen counts the crossings begun here and the returns to this page by Back or Forward: a crossing whose number is no
   longer the latest does nothing more */
let busy = false, gen = 0, ending = null;
function go(url) { location.href = url; }
/* L: {href, path, title}; opts.force plays the full scene even when this visit has seen it; opts.demo plays it in
   place and resolves instead of going. Resolves with how it ended: played, skipped, still, quick, faded */
function cross(L, opts = {}) {
  return new Promise(resolve => {
    if (busy) { resolve("busy"); return; }
    busy = true;
    const my = ++gen, live = () => my === gen;
    const first = opts.force || !session.get(SEEN), quick = !first || saveData() || !can3d();
    const from = pageColour(), to = from;
    const leaveFor = (how) => { if (!live()) return; if (opts.demo) { busy = false; resolve(how); } else go(L.href); };
    /* later in the same visit, or for a reader saving data, or a device that cannot draw it: a quick fade */
    if (quick) {
      const V = veil(to, true);
      setTimeout(() => { if (opts.demo) { V.h.classList.remove("on"); setTimeout(() => V.h.remove(), 360); } leaveFor("quick"); }, 380);
      return;
    }
    const V = veil(from, false), host = V.h;
    shut(host);
    let phase = "loading", ctl = null;
    const leave = () => { phase = "gone"; removeEventListener("keydown", onKey, true); };
    const done = (how) => { if (opts.demo) { reopen(); host.classList.remove("on"); setTimeout(() => host.remove(), 380); } leaveFor(how); };
    const fade = how => { if (phase !== "loading") return; leave(); host.style.background = to; setTimeout(() => done(how), 420); };
    const skipNow = () => {
      if (phase === "playing") { leave(); if (ctl && ctl.skip) ctl.skip(); else done("skipped"); return; }
      if (phase !== "loading") return;
      leave(); session.set(SEEN, "1"); done("skipped");
    };
    function onKey(e) {
      if (phase === "gone" || passes(e)) return;
      if (e.key === "Tab") { e.preventDefault(); try { V.skip.focus({preventScroll: true}); } catch (x) {} return; }
      e.preventDefault(); skipNow();
    }
    addEventListener("keydown", onKey, true);
    host.addEventListener("pointerdown", e => { if (e.button === 0 || e.pointerType !== "mouse") skipNow(); });
    host.addEventListener("click", skipNow);
    const timer = setTimeout(() => fade("faded"), WAIT);      /* slow files: a fade, never a wait */
    ending = () => { clearTimeout(timer); leave(); reopen(); };
    const out = () => { host.style.background = to; };
    load().then(m => m ? prepared(m).then(A => ({m, A})) : null).then(r => {
      if (phase !== "loading" || !live()) return;
      clearTimeout(timer);
      if (!r) { fade("faded"); return; }
      let ok = false;
      try {
        ok = r.m.run(L.href, {host, assets: r.A, still: stillNow(), lean: lean(), start: from, end: to, title: L.title, path: L.path, keys: false, fade: out,
                              onEnd: opts.demo ? (how => { leave(); done(how === "full" ? "played" : how); }) : undefined});
      } catch (e) { ok = false; }
      if (ok) { ctl = typeof ok === "object" ? ok : {skip: () => done("skipped")}; phase = "playing"; session.set(SEEN, "1"); }
      else fade("faded");
    }).catch(() => fade("faded"));
  });
}

function wire() {
  const warm = e => { const a = linkOf(e), L = a && notebookLink(a); if (L && !session.get(SEEN)) load(); };
  D.addEventListener("pointerover", warm, {capture: true, passive: true});
  D.addEventListener("focusin", warm, {capture: true});
  D.addEventListener("pointerdown", warm, {capture: true, passive: true});
  D.addEventListener("touchstart", warm, {capture: true, passive: true});
  D.addEventListener("click", e => {
    if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    const a = linkOf(e);
    if (!a) return;
    let L = null;
    try { L = notebookLink(a); } catch (x) { L = null; }
    if (!L) return;
    e.preventDefault(); e.stopImmediatePropagation();
    try { cross(L).catch(() => go(L.href)); } catch (x) { go(L.href); }
  }, true);
  /* back from the notebook, or Forward again after going Back while the scene loaded: the page, not the scene */
  addEventListener("pageshow", e => {
    if (!e.persisted) return;
    gen++; if (ending) { ending(); ending = null; }
    busy = false; reopen();
    for (const v of D.querySelectorAll(".tca-nbv")) v.remove();
  });
}
if (D.readyState === "loading") D.addEventListener("DOMContentLoaded", wire, {once: true}); else wire();

window.__nbGate = {
  play: (opts = {}) => cross({href: location.href, path: opts.path || "start", title: opts.title || "The Notebook"}, Object.assign({demo: true, force: true}, opts)),
  cross: (href, opts = {}) => { const a = D.createElement("a"); a.href = href; a.className = "nbl"; const L = notebookLink(a) || {href: a.href, path: "", title: ""}; return cross(L, opts); },
  warm: () => load(),
  seen: () => !!session.get(SEEN),
  forget: () => session.del(SEEN),
  can: () => ({webgl2: can3d(), saveData: saveData(), still: stillNow(), lean: lean()}),
  still: (t, w, h, o) => load().then(m => m && prepared(m).then(() => m.still(t, w, h, Object.assign({lean: lean()}, o || {}))))
};
