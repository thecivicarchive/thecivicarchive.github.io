/* The Civic Archive: the companion's dock (Shell Spec section 9; the clip list of the Companion Field Guide).
   Fetched only after the page has been drawn, and only when the companion is On or Still. It draws the chosen animal
   with the site's own copy of three.js and the companions' realism kit (companions/kit.js: physical materials, fur and
   feather shells, wet eyes, skinned rigs, springs, a lit stage), about 30 frames a second (24 and one pixel per pixel
   on a lean device), and nothing at all while the tab is hidden. Still and reduced motion draw one frame. If WebGL or a
   file fails, it hands back to the shell, which shows a plain Help bubble instead.
   The animal pops off the page: its canvas is wider and taller than the dock and reaches below it, so it can lean, hop
   and flap beyond its box, while the button underneath keeps the documented size (84 by 96 on phones, 96 by 108 on
   desktop) and is the only thing that takes a tap. A soft shadow falls on the page under its feet; the camera swings a
   little with the pointer, so it reads as a thing standing in front of the page.
   Its only job is opening Help: a click, a tap or Enter plays "react" and opens it; "talk" loops while Help is open;
   hovering with a mouse, or reaching it with the keyboard, plays "dance" when motion is on. It never speaks on its own.
   The drawing is hidden from screen readers; the control is a real button named "Open help".
   Each companion is a module: { id, name, latin, rests, build(THREE, kit) -> rig, update(rig, dt, state),
   play(rig, clip) -> seconds, rest(rig) }, with rig.root one unit to the animal's body height, facing the reader, feet
   at zero. Quality tiers: 0 lean, 1 a mid phone, 2 full; the dock picks one from the device and steps down once if the
   frames fall behind. */

let THREE = null, KIT = null, ROOM = null;
const BRANCH = '<svg class="branch" viewBox="0 0 110 22" preserveAspectRatio="none" aria-hidden="true" focusable="false"><path d="M2 15C30 13 58 12.5 108 11" stroke-width="4.2"/><path d="M38 13.4c5-4.6 9-6.2 14-7.2" stroke-width="2"/><path d="M74 12.2c3 2.6 6.4 4 11 4.6" stroke-width="1.8"/></svg>';
/* the canvas around the dock: this much wider and taller than the button, reaching this far below it (shell.css agrees) */
const OVER_W = 2.1, OVER_H = 1.56, OVER_PAD = 0.14;

function detectTier(lean) {
  if (lean) return 0;
  let t = 2;
  try {
    const nav = navigator;
    if (matchMedia("(pointer: coarse)").matches) t = 1;
    if (nav.deviceMemory && nav.deviceMemory < 4) t = Math.min(t, 1);
    if (nav.hardwareConcurrency && nav.hardwareConcurrency <= 4) t = Math.min(t, 1);
    if (nav.deviceMemory && nav.deviceMemory <= 2) t = 0;
    if (nav.connection && nav.connection.saveData) t = Math.min(t, 1);
  } catch (e) {}
  return t;
}

export async function start(o) {
  const el = document.createElement("div"), btn = document.createElement("button"), canvas = document.createElement("canvas"), shade = document.createElement("div");
  el.className = "tca-dock"; el.dataset.rest = o.skin.rests === "perch" ? "perch" : "floor";
  btn.type = "button"; btn.className = "tca-dockbtn"; btn.setAttribute("aria-label", "Open help");
  btn.setAttribute("aria-controls", "tca-help"); btn.setAttribute("aria-expanded", o.helpOpen() ? "true" : "false");
  canvas.className = "tca-dockart"; canvas.setAttribute("aria-hidden", "true");
  shade.className = "tca-dockshade"; shade.setAttribute("aria-hidden", "true");
  if (el.dataset.rest === "perch") el.insertAdjacentHTML("afterbegin", BRANCH);
  el.append(shade, canvas, btn);
  document.body.append(el);
  /* everything the clean-up touches is declared first, so a failure at any step can clean up */
  let stopped = false, raf = 0, renderer = null, stage = null, kit = null, mod = null, rig = null;
  let onMove = null, onKey = null, onScroll = null, onHelp = null, onVis = null, onResize = null;
  const fail = why => { teardown(); o.fail(why); return null; };

  try { THREE = THREE || await import(new URL("../vendor/three.module.min.js", import.meta.url).href); }
  catch (e) { return fail("three.js did not load"); }
  try {
    const [k, r] = await Promise.all([KIT || import(new URL("./companions/kit.js", import.meta.url).href), ROOM || import(new URL("../vendor/jsm/environments/RoomEnvironment.js", import.meta.url).href)]);
    KIT = k; ROOM = r;
  } catch (e) { return fail("the companions' kit did not load"); }
  let skin = o.skin, still = !!o.still, lean = !!o.lean, busyUntil = 0, helpOpen = !!o.helpOpen();
  let tier = o.tier != null ? o.tier : detectTier(lean);
  try {
    renderer = new THREE.WebGLRenderer({canvas, alpha: true, antialias: tier > 0, powerPreference: "low-power", premultipliedAlpha: true});
    if (!renderer.getContext()) throw new Error("no context");
  } catch (e) { return fail("WebGL is not available"); }
  renderer.setClearColor(0x000000, 0);
  try {
    kit = KIT.createKit(THREE, {RoomEnvironment: ROOM.RoomEnvironment, gltf: () => import(new URL("../vendor/jsm/loaders/GLTFLoader.js", import.meta.url).href)},
                        {tier, base: new URL("companions/", o.base).href});
    stage = kit.stage(renderer, {tier});
  } catch (e) { return fail("the stage could not be set"); }
  const scene = stage.scene;
  const state = {t: 0, pointer: null, motion: still ? "still" : "on", helpOpen, scrolling: false, idleFor: 0};

  async function load(c) {
    let m;
    try { m = (await import(new URL("companions/" + c.file, o.base).href)).default; } catch (e) { return false; }
    if (!m || typeof m.build !== "function") return false;
    let r;
    try { r = m.build(THREE, kit); if (r && typeof r.then === "function") r = await r; } catch (e) { console.warn("Companion: build failed", e); return false; }
    if (!r || !r.root) return false;
    if (rig) { scene.remove(rig.root); dispose(rig); }
    mod = m; rig = r; skin = c;
    scene.add(rig.root);
    el.dataset.rest = c.rests === "perch" ? "perch" : "floor";
    const hasBranch = !!el.querySelector(".branch");
    if (el.dataset.rest === "perch" && !hasBranch) el.insertAdjacentHTML("afterbegin", BRANCH);
    if (el.dataset.rest !== "perch" && hasBranch) el.querySelector(".branch").remove();
    document.documentElement.setAttribute("data-dock", el.dataset.rest);      // Help opens clear of the companion, so it can be seen talking
    stage.contact.visible = el.dataset.rest !== "perch" && !rig.shadow;      // a companion that casts its own shadow keeps it
    shade.style.opacity = el.dataset.rest === "perch" ? "0" : "";
    try { mod.rest(rig); } catch (e) {}
    frame(); tone();
    try { renderer.compile(scene, stage.camera); } catch (e) {}      // the shaders are made now, not on the first frame of the walk in
    return true;
  }
  /* framing: the box the companion asks to keep in view (rig.frame), or its measured size with room for a hop, fills the
     dock's own rectangle; the canvas around it is wider and taller, so the animal can lean out of its box */
  let ppu = 100, frameBox = null;
  function frame() {
    const W = Math.max(1, canvas.clientWidth), H = Math.max(1, canvas.clientHeight), dW = Math.max(1, el.clientWidth), dH = Math.max(1, el.clientHeight);
    renderer.setPixelRatio(Math.min(kit.caps().dpr, window.devicePixelRatio || 1));
    renderer.setSize(W, H, false);
    let f = rig.frame;
    if (!(f && f.x && f.y)) {
      const box = new THREE.Box3().setFromObject(rig.root), size = new THREE.Vector3(); box.getSize(size);
      f = {x: [box.min.x, box.max.x], y: [Math.min(0, box.min.y), box.max.y + size.y * 0.3]};
    }
    frameBox = f;
    const v = stage.frame(f, {W, H, dockW: dW, dockH: dH, pad: OVER_PAD * dH, perch: el.dataset.rest === "perch"}, rig.fov);
    ppu = H / v.V;
  }
  function play(clip) {
    if (!mod || still || stopped) return 0;
    let s = 0; try { s = +mod.play(rig, clip) || 0; } catch (e) { s = 0; }
    busyUntil = state.t + s; wake(); return s;
  }

  /* ---------- the loop: about 30 a second, 24 on a lean device, never while hidden ---------- */
  let last = 0, lastDraw = 0, lastDrawn = 0, owed = 0;
  const step = () => 1000 / kit.caps().fps;
  const covered = () => {      // behind an open menu (a perched bird under a mega-menu, anyone under the phone menu): nothing to draw
    const H = document.documentElement;
    if (H.getAttribute("data-menu") !== "open") return false;
    const b = document.getElementById("tca-burger");
    return el.dataset.rest === "perch" || (b && b.getAttribute("aria-expanded") === "true");
  };
  /* on a dark page the rim light grows, so dark fur and feathers keep an edge; the old self-lit parts get the same */
  function tone() {
    if (!rig) return;
    const dark = document.documentElement.getAttribute("data-contrast") === "dark";
    stage.setDark(dark);
    rig.root.traverse(x => {
      const ms = Array.isArray(x.material) ? x.material : (x.material ? [x.material] : []);
      for (const m of ms) if (m.uniforms && m.uniforms.uRim) {
        if (m.userData.rim0 == null) m.userData.rim0 = m.uniforms.uRim.value;
        m.uniforms.uRim.value = m.userData.rim0 + (dark ? 0.6 : 0);
      }
    });
  }
  /* the pointer parallax: the camera swings a little toward where the pointer is on the page, and settles back */
  const par = {x: 0, y: 0, tx: 0, ty: 0};
  function parallax(dt) {
    if (!still && fine.matches && pagePointer) { par.tx = pagePointer.x; par.ty = pagePointer.y; } else { par.tx = 0; par.ty = 0; }
    const k = 1 - Math.exp(-dt * 3.2);
    par.x += (par.tx - par.x) * k; par.y += (par.ty - par.y) * k;
    stage.look(par.x * 0.075, par.y * 0.03);
  }
  /* the shadow on the page under the animal: it follows the body and lifts off during a hop */
  let shadeT = "", shadeO = "";
  function placeShade() {
    if (!rig || el.dataset.rest === "perch") return;
    const m = rig.j && rig.j.mover ? rig.j.mover.position : null, cx = frameBox ? (frameBox.x[0] + frameBox.x[1]) / 2 : 0;
    const x = m ? m.x : 0, lift = m ? Math.max(0, m.y) : 0, k = 1 / (1 + 3 * lift);
    const t = `translate(calc(-50% + ${((x - cx) * ppu + par.x * -4).toFixed(1)}px), ${(-lift * ppu * 0.15).toFixed(1)}px) scale(${k.toFixed(3)})`;
    const op = (k * k * (stage.dark ? 0.55 : 0.9)).toFixed(3);
    if (t !== shadeT) { shade.style.transform = t; shadeT = t; }
    if (op !== shadeO) { shade.style.opacity = op; shadeO = op; }
    if (stage.contact.visible) { stage.contact.position.x = x; stage.contact.position.z = m ? m.z : 0; stage.contact.material.opacity = k * k; }
  }
  /* the governor: if the frames keep falling behind for a while, one tier down (never up again this page) */
  let gFrames = 0, gSlow = 0, gLast = 0, gSince = performance.now() + 3000, gDrawMs = 0;
  function govern(now) {
    if (now < gSince) { gLast = now; return; }
    if (gLast) { const iv = now - gLast; gFrames++; if (iv > 26 || gDrawMs > 12) gSlow++; }
    gLast = now;
    if (gFrames >= 120) {
      if (gSlow / gFrames > 0.5 && kit.tier > 0) {
        const t = kit.setTier(kit.tier - 1);
        stage.setTier(t); if (rig) rig.shells && rig.shells(); frame();
        gSince = now + 6000;
      }
      gFrames = 0; gSlow = 0;
    }
  }
  function draw(dt) {
    if (!rig || !mod) return;      // a pointer moved while the companion was still on its way
    const t0 = performance.now();
    state.t += dt; state.helpOpen = helpOpen; state.motion = still ? "still" : "on";
    state.idleFor = (performance.now() - lastActive) / 1000;
    if (helpOpen && !still && state.t >= busyUntil) busyUntil = state.t + (play("talk") || 3);      // "talk" loops while Help is open
    try { mod.update(rig, dt, state); } catch (e) {}
    parallax(dt);
    placeShade();
    stage.render(rig.root);
    gDrawMs = performance.now() - t0;
  }
  function loop(now) {
    raf = 0;
    if (stopped || still || document.hidden) return;
    if (!last) last = now;
    /* time owed is carried over, so 30 a second is every other frame of a 60 Hz screen and 24 is two, then three */
    owed += lastDraw ? now - lastDraw : step(); lastDraw = now;
    if (owed >= step() - 2) {
      const dt = Math.min(0.1, (lastDrawn ? now - lastDrawn : step()) / 1000);
      owed = Math.max(0, Math.min(owed - step(), step())); lastDrawn = now;
      if (!covered()) draw(dt);
    }
    govern(now);
    raf = requestAnimationFrame(loop);
  }
  function wake() { if (!raf && !still && !stopped && rig && !document.hidden) { lastDraw = 0; lastDrawn = 0; owed = 0; raf = requestAnimationFrame(loop); } }
  function poster() {      // Still and reduced motion: the rest pose, drawn once
    if (!mod) return;
    try { mod.rest(rig); mod.update(rig, 0, {...state, motion: "still", pointer: null}); } catch (e) {}
    par.x = par.y = 0; stage.look(0, 0); placeShade();
    stage.render(rig.root);
  }

  /* ---------- what the reader does ---------- */
  let lastActive = performance.now(), pointerT = 0, scrollT = 0, pagePointer = null;
  const fine = matchMedia("(hover: hover) and (pointer: fine)");
  onMove = e => {
    lastActive = performance.now();
    const r = canvas.getBoundingClientRect(); if (!r.width) return;
    const x = ((e.clientX - r.left) / r.width) * 2 - 1, y = 1 - ((e.clientY - r.top) / r.height) * 2;
    state.pointer = {x: Math.max(-1, Math.min(1, x)), y: Math.max(-1, Math.min(1, y))};      // -1..1 across the canvas, up is +1
    pagePointer = {x: Math.max(-1, Math.min(1, (e.clientX / Math.max(1, innerWidth)) * 2 - 1)), y: Math.max(-1, Math.min(1, (e.clientY / Math.max(1, innerHeight)) * 2 - 1))};
    clearTimeout(pointerT); pointerT = setTimeout(() => { state.pointer = null; pagePointer = null; wake(); }, 2600);
    wake();
  };
  onKey = () => { lastActive = performance.now(); };
  onScroll = () => {
    if (still) return;      // with motion reduced or the companion Still, it stays put rather than jumping aside and back
    state.scrolling = true; el.classList.add("ducked");
    clearTimeout(scrollT); scrollT = setTimeout(() => { state.scrolling = false; el.classList.remove("ducked"); }, 380);
  };
  onHelp = e => {
    helpOpen = !!(e.detail && e.detail.open); btn.setAttribute("aria-expanded", helpOpen ? "true" : "false");
    if (helpOpen) wake();      // "talk" starts once the clip under way (a tap's "react") has finished
  };
  onVis = () => { if (!document.hidden) wake(); };
  onResize = () => { if (rig) { frame(); if (still) poster(); } };
  addEventListener("pointermove", onMove, {passive: true});
  addEventListener("keydown", onKey, {passive: true});
  addEventListener("scroll", onScroll, {passive: true});
  addEventListener("resize", onResize);
  document.documentElement.addEventListener("tca:help", onHelp);
  document.addEventListener("visibilitychange", onVis);
  btn.addEventListener("pointerenter", e => { if (e.pointerType === "mouse" && fine.matches) play("dance"); });
  btn.addEventListener("focus", () => { let kb = false; try { kb = btn.matches(":focus-visible"); } catch (x) {} if (kb) play("dance"); });
  btn.addEventListener("click", () => { play("react"); o.openHelp(btn); });

  function teardown() {      // safe at any point, even before the listeners below exist (a WebGL or file failure)
    stopped = true; el.remove(); document.documentElement.removeAttribute("data-dock");
    try { if (raf) cancelAnimationFrame(raf); raf = 0; } catch (e) {}
    try {
      removeEventListener("pointermove", onMove); removeEventListener("keydown", onKey); removeEventListener("scroll", onScroll); removeEventListener("resize", onResize);
      document.documentElement.removeEventListener("tca:help", onHelp); document.removeEventListener("visibilitychange", onVis);
    } catch (e) {}
    try { if (rig) { scene.remove(rig.root); dispose(rig); rig = null; } } catch (e) {}
    try { if (stage) stage.dispose(); } catch (e) {}
    try { if (renderer) { renderer.dispose(); renderer.forceContextLoss(); } } catch (e) {}
    try { delete window.__companion; } catch (e) {}
  }

  if (!(await load(skin))) return fail("the companion's file did not load");
  if (still) poster(); else { play("arrive"); wake(); }      // it arrives once per page load
  /* a read-only look at what the companion is doing, for checking the page (nothing about the reader is in it) */
  window.__companion = () => ({skin: skin.id, rest: el.dataset.rest, still, helpOpen, ducked: el.classList.contains("ducked"), tier: kit.tier,
                               clip: rig && rig.cur && !rig.cur.done ? rig.cur.name : null, drawing: !!raf, drawMs: Math.round(gDrawMs * 100) / 100});

  return {
    async set(n) {
      if (stopped) return;
      if (!!n.lean !== lean) { lean = !!n.lean; const t = Math.min(kit.tier, detectTier(lean)); if (t !== kit.tier) { kit.setTier(t); stage.setTier(t); if (rig) rig.shells && rig.shells(); } }
      if (n.skin && n.skin.id !== skin.id) {
        if (!(await load(n.skin))) { fail("the companion's file did not load"); return; }
        if (!still && !n.still) play("arrive");
      }
      tone(); if (rig) frame();
      if (!!n.still !== still) { still = !!n.still; if (still) { if (raf) cancelAnimationFrame(raf); raf = 0; el.classList.remove("ducked"); state.scrolling = false; poster(); } else { busyUntil = 0; wake(); } }
      else if (still) poster();
    },
    cue(clip) { if (!helpOpen) play(clip); },
    stop: teardown
  };
}

function dispose(rig) {
  try { if (rig.dispose) rig.dispose(); } catch (e) {}
  rig.root.traverse(x => {
    if (x.geometry) x.geometry.dispose();
    const mats = Array.isArray(x.material) ? x.material : (x.material ? [x.material] : []);
    for (const m of mats) { for (const k in m) { const v = m[k]; if (v && v.isTexture) v.dispose(); } m.dispose(); }
  });
}
