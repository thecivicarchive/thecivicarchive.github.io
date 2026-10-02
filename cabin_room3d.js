/*
 cabin_room3d.js - the cabin: the room a visitor lands in (John, 2026-10-01). A log great room in the Rockies, seen in
 the first person and walked through: round-log walls and rafters under a vaulted roof, a gable wall of windows on the
 mountains, a stacked-stone fireplace with a fire burning, leather and upholstered seating on a red rug, lamps, a
 wrought-iron chandelier, a loft with a log railing. Two posters hang either side of the windows and glow: they are the
 doors to the site's two spaces (On The Ballot; Legislation & Legislatures).

 The room says nothing about anyone: it holds no record and no claim, only the two doors. Each poster is also an
 ordinary link on the page, so the room is never the only way in.

 Second version (2026-10-01): photographed materials (CC0, Poly Haven and ambientCG: colour, normal and roughness maps),
 CC0 furniture models from Poly Haven, and public-domain National Park Service photographs of the Rockies outside the
 windows, graded for the hour. Everything is kept with the site under cabin_assets/ (see credits.json there); nothing is
 fetched from anyone else's server. The first frame is drawn at once with plain colours; textures, models and the view
 arrive behind it and the page shows a quiet loading note until they have.

 Uses three.js r169 (MIT licence, vendor/three.module.min.js) and its add-ons from the same release (vendor/jsm/:
 GLTFLoader, EffectComposer, UnrealBloomPass, OutputPass, RoomEnvironment). build_cabin.py copies this file beside the
 page as cabin3d.js and the vendor files and assets next to it.

   start(canvas, opts) -> {go(i), look(i), goBack(), still(w, h, view), bench(n), setWhen(when, season), dispose()}
     opts.posters    [{url, kicker, head, sub, cta, foot, look}]   two of them
     opts.assets     where cabin_assets/ is, seen from the page (default "cabin_assets/")
     opts.views      {hour: [{file, season, horizon, caption, credit}]}  the photographs outside, by hour
     opts.when       "morning" | "afternoon" | "dusk" | "night"    (default: by the device's clock)
     opts.season     "winter" | "spring" | "summer" | "autumn"     (default: by the device's calendar)
     opts.calm       true = no flicker, no head bob, no walk-up: things happen at once
     opts.lite       true = the lighter path (phones): no bloom, smaller shadows, no shadows from the fire
     opts.onHover(i)       a poster is under the pointer (-1: none)
     opts.onLeave(url)     a poster was chosen and the visitor has walked up to it
     opts.back       true = the plank door behind the visitor glows and is a way back to the page they came from
     opts.onBack()         that door was chosen (clicked, or walked up to) and the visitor has reached it; onHover gives it as 2
     opts.onMove()         the visitor moved or looked for the first time
     opts.onProgress(done, total)   files arriving;  opts.onReady()  everything is in
     opts.onView(info)     which photograph is outside: {caption, credit, season, shown, hour}
   still() draws one frame to a JPEG data URL, for checking the room where frames are not being drawn.
   bench(n) draws n frames back to back and returns the milliseconds each one took.
*/
import * as THREE from "./vendor/three.module.min.js";
import {GLTFLoader} from "./vendor/jsm/loaders/GLTFLoader.js";
import {EffectComposer} from "./vendor/jsm/postprocessing/EffectComposer.js";
import {RenderPass} from "./vendor/jsm/postprocessing/RenderPass.js";
import {UnrealBloomPass} from "./vendor/jsm/postprocessing/UnrealBloomPass.js";
import {OutputPass} from "./vendor/jsm/postprocessing/OutputPass.js";
import {RoomEnvironment} from "./vendor/jsm/environments/RoomEnvironment.js";

/* ---------- the room's measurements: x across, z toward the window wall (-z), y up ---------- */
const W = 10.4, D = 9.0, HX = W / 2, HZ = D / 2;      // inside the log faces
const HE = 3.6, HR = 6.6;                             // the eave (top of the side walls) and the ridge
const LOG_R = 0.17, COURSE = 0.325, TEXW = 1.05;      // a wall log, one course, and the pine texture's real width in metres
const WIN = {x0: -3.05, x1: 3.05, y0: 0.68, head: 0.42};      // the gable window: posts, sill, and the header space under the roof
const EYE = 1.62, RADIUS = 0.33;
const TINT_BACK = new THREE.Color("#ffe3a6");      // the light round the door that leads back
const LOFT_Z = HZ - 2.2, LOFT_Y = 3.0;                // the loft over the back of the room
const FIRE = {z: 1.2, w: 2.7, depth: 0.75, open: [0.55, 1.75], top: 1.3, hearth: 0.42};      // the fireplace on the right-hand wall
const slopeY = x => HE + (HR - HE) * (1 - Math.abs(x) / HX);          // the roof's underside above x
const xMax = y => y <= HE ? HX : HX * (HR - y) / (HR - HE);          // how far a gable log reaches at height y

/* ---------- time of day and season, from the visitor's own device ---------- */
export function whenNow(d = new Date()){ const h = d.getHours() + d.getMinutes() / 60; return h < 5.5 ? "night" : h < 11 ? "morning" : h < 17 ? "afternoon" : h < 20.25 ? "dusk" : "night"; }
export function seasonNow(d = new Date()){ return ["winter", "winter", "spring", "spring", "spring", "summer", "summer", "summer", "autumn", "autumn", "autumn", "winter"][d.getMonth()]; }
/* the light of each hour: where the sun is (a direction, toward the windows at -z), its colour and strength, the sky's
   light, how much the surroundings reflect, which lamps are lit, how bright the fire burns, and how the photograph
   outside is graded */
const HOURS = {
  morning:   {sun: [-0.62, 0.36, -1.0], sunCol: "#ffdcb0", sunI: 4.6, hemi: ["#c9dcff", "#6b5040", 1.0], env: 0.65, expo: 1.0, lamps: 0, fire: 7, poster: 1.0,
              view: {gain: 1.18, tint: [1.04, 1.0, 0.95]}, motes: 1, sky: ["#88b4e8", "#e9f0f8"]},
  afternoon: {sun: [0.7, 0.9, -1.0], sunCol: "#fff6ea", sunI: 6.0, hemi: ["#dbe8ff", "#7a6050", 1.3], env: 0.8, expo: 1.0, lamps: 0, fire: 5, poster: 1.0,
              view: {gain: 1.25, tint: [1, 1, 1]}, motes: 1, sky: ["#5d9be0", "#dfeaf6"]},
  dusk:      {sun: [0.85, 0.11, -1.0], sunCol: "#ff9a4c", sunI: 2.2, hemi: ["#a08cc0", "#4a3222", 0.45], env: 0.35, expo: 1.0, lamps: 1, fire: 11, poster: 1.25,
              view: {gain: 1.0, tint: [1.0, 0.86, 0.82]}, motes: 0.4, sky: ["#3a3f7a", "#f0a070"]},
  night:     {sun: [-0.35, 0.65, -1.0], sunCol: "#8fa6ff", sunI: 0.22, hemi: ["#1c2638", "#1a120a", 0.1], env: 0.1, expo: 1.0, lamps: 1, fire: 13, poster: 1.5,
              view: {gain: 0.42, tint: [0.55, 0.66, 1.0], night: 1}, motes: 0, sky: ["#050a18", "#15203c"]},
};

/* ---------- small tools ---------- */
function rng(seed){ let a = seed >>> 0; return () => { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
const V3 = (x = 0, y = 0, z = 0) => new THREE.Vector3(x, y, z);
const UP = V3(0, 1, 0);
function canvasTex(w, h, draw, repeat){
  const c = document.createElement("canvas"); c.width = w; c.height = h; draw(c.getContext("2d"), w, h);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 4;
  if (repeat) { t.wrapS = t.wrapT = THREE.RepeatWrapping; }
  return t;
}
const std = (o) => new THREE.MeshStandardMaterial(Object.assign({roughness: 0.9, metalness: 0}, o));
function mesh(geo, mat, x, y, z, parent, shadow = true){ const m = new THREE.Mesh(geo, mat); m.position.set(x, y, z); m.castShadow = m.receiveShadow = shadow; parent.add(m); return m; }
function box(w, h, d, mat, x, y, z, parent, shadow = true){ return mesh(new THREE.BoxGeometry(w, h, d), mat, x, y, z, parent, shadow); }
/* a box whose texture keeps its real size on every face: one material, the faces' uv scaled by the face's own size */
function sizedBox(w, h, d, mat, x, y, z, parent, texSize = 2.0, shadow = true){
  const g = new THREE.BoxGeometry(w, h, d), uv = g.attributes.uv, faces = [[d, h], [d, h], [w, d], [w, d], [w, h], [w, h]];
  for (let f = 0; f < 6; f++) for (let i = 4 * f; i < 4 * f + 4; i++) uv.setXY(i, uv.getX(i) * faces[f][0] / texSize, uv.getY(i) * faces[f][1] / texSize);
  return mesh(g, mat, x, y, z, parent, shadow);
}
/* a block of stonework whose texture is laid out in room coordinates, so neighbouring blocks join without a seam */
function stoneBlock(x0, x1, y0, y1, z0, z1, mat, parent, tex = 2.0){
  const w = x1 - x0, h = y1 - y0, d = z1 - z0, g = new THREE.BoxGeometry(w, h, d), uv = g.attributes.uv, pos = g.attributes.position, cx = (x0 + x1) / 2, cy = (y0 + y1) / 2, cz = (z0 + z1) / 2;
  for (let i = 0; i < pos.count; i++) { const f = Math.floor(i / 4), X = pos.getX(i) + cx, Y = pos.getY(i) + cy, Z = pos.getZ(i) + cz;
    if (f < 2) uv.setXY(i, Z / tex, Y / tex); else if (f < 4) uv.setXY(i, X / tex, Z / tex); else uv.setXY(i, X / tex, Y / tex); }
  return mesh(g, mat, cx, cy, cz, parent);
}
/* a log: a cylinder whose bark texture keeps its real size along it, with a different offset for every log so the knots differ */
const logR = rng(31);
function logGeo(len, r, seg = 16){
  const g = new THREE.CylinderGeometry(r, r, len, seg, 1, false), uv = g.attributes.uv, around = 2 * Math.PI * r / TEXW, k = len / TEXW, ou = logR(), ov = logR();
  for (let i = 0; i < uv.count; i++) uv.setXY(i, uv.getY(i) * k + ov, uv.getX(i) * around + ou);      // grain runs along the log
  return g;
}
function logAt(len, r, mat, x, y, z, along, parent, seg){ const m = new THREE.Mesh(logGeo(len, r, seg), mat); m.position.set(x, y, z); if (along === "x") m.rotation.z = Math.PI / 2; else if (along === "z") m.rotation.x = Math.PI / 2; m.castShadow = m.receiveShadow = true; parent.add(m); return m; }
function logBetween(a, b, r, mat, parent, seg){ const dir = b.clone().sub(a), len = dir.length(), m = new THREE.Mesh(logGeo(len, r, seg), mat); m.position.copy(a).add(b).multiplyScalar(0.5); m.quaternion.setFromUnitVectors(UP, dir.normalize()); m.castShadow = m.receiveShadow = true; parent.add(m); return m; }
function wrap(ctx, text, x, y, maxW, lineH, align = "left"){
  const words = String(text).split(/\s+/); let line = "", yy = y; ctx.textAlign = align;
  for (const w of words) { const t = line ? line + " " + w : w; if (ctx.measureText(t).width > maxW && line) { ctx.fillText(line, x, yy); line = w; yy += lineH; } else line = t; }
  if (line) ctx.fillText(line, x, yy);
  return yy + lineH;
}

/* ---------- photographed materials: colour, normal and packed AO/roughness maps, applied as they arrive ---------- */
function materials(base, manager, aniso, redraw){
  const loader = new THREE.TextureLoader(manager);
  const M = {};
  /* each material starts as a plain colour and takes its maps together once they have all arrived (one shader rebuild) */
  function pbr(name, o = {}){
    const m = std({color: o.color || "#ffffff", roughness: o.roughness == null ? 1 : o.roughness});
    const rep = o.repeat || [1, 1], want = o.maps || ["diff", "nor", "arm"], got = {}; let left = want.length;
    const done = () => { if (--left) return;
      if (got.diff) m.map = got.diff; if (got.nor) m.normalMap = got.nor; if (got.arm) { m.aoMap = got.arm; if (o.roughMap !== false) { m.roughnessMap = got.arm; m.metalnessMap = got.arm; } } if (got.rough) m.roughnessMap = got.rough;
      m.roughness = m.roughnessMap ? 1 : (o.roughness == null ? 1 : o.roughness); m.normalScale.set(o.normal == null ? 1 : o.normal, o.normal == null ? 1 : o.normal); m.needsUpdate = true; redraw(); };
    for (const suffix of want) loader.load(`${base}tex/${name}_${suffix}.jpg`, t => { t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(rep[0], rep[1]); t.anisotropy = aniso; t.channel = 0; if (suffix === "diff") t.colorSpace = THREE.SRGBColorSpace; got[suffix] = t; done(); }, undefined, () => done());
    return m;
  }
  M.logs = pbr("logs", {color: "#cdbda9", repeat: [1, 1], normal: 0.9, roughMap: false, roughness: 0.74});      // the uv of every log is scaled to real size; matte, and less orange than the varnished board it was photographed from
  M.floor = pbr("floor", {color: "#6e4b2d", repeat: [W / 2, D / 2], normal: 0.8});       // the texture is 2 m across
  M.boards = pbr("boards", {color: "#b89f88", repeat: [1, 1], normal: 0.6, roughMap: false, roughness: 0.8});      // scaled per piece
  M.stone = pbr("stone", {color: "#6f6a62", repeat: [1, 1], normal: 1.0});                 // scaled per piece (2 m)
  M.bark = pbr("bark", {color: "#4a3a2c", repeat: [1, 1], normal: 1.0});
  M.deck = pbr("deck", {color: "#7a7268", repeat: [1, 1], normal: 0.8});
  M.leather = pbr("leather", {color: "#5a3a22", repeat: [2, 2], normal: 0.7});
  M.plaid = pbr("plaid", {color: "#ffffff", repeat: [1.5, 1.5], normal: 0.6});
  M.rugBump = {nor: null, rough: null, diff: null};
  loader.load(`${base}tex/rug_nor.jpg`, t => { t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(6, 4.4); t.anisotropy = aniso; M.rugBump.nor = t; M.onRug && M.onRug(); });
  loader.load(`${base}tex/rug_rough.jpg`, t => { t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(6, 4.4); M.rugBump.rough = t; M.onRug && M.onRug(); });
  loader.load(`${base}tex/rug_diff.jpg`, t => { M.rugBump.diff = t; M.onRug && M.onRug(); });
  M.dark = std({color: "#3a2616", roughness: 0.55});                 // stained trim: window frames, door frame
  M.backing = std({color: "#17110c", roughness: 1});
  M.iron = std({color: "#1c1917", roughness: 0.55, metalness: 0.85});
  M.brass = std({color: "#b8894a", roughness: 0.35, metalness: 0.9});
  M.soot = new THREE.MeshBasicMaterial({color: "#140c08"});      // the inside of the firebox: soot takes no light worth drawing
  M.mortar = std({color: "#9a938a", roughness: 1});
  M.cream = std({color: "#efe6d2", roughness: 0.9});
  return M;
}

/* ---------- the posters: printed paper, drawn large. look "ballot" is cream with red and blue; "record" is deep green with gold ---------- */
function posterTexture(p){
  return canvasTex(768, 1152, (c, w, h) => {
    const ballot = p.look !== "record", ink = ballot ? "#16233f" : "#f4ead2", accent = ballot ? "#c0392b" : "#e2b34a", paper = ballot ? "#f7f0e1" : "#17352c";
    c.fillStyle = paper; c.fillRect(0, 0, w, h);
    const r = rng(ballot ? 3 : 5); for (let i = 0; i < 900; i++) { c.fillStyle = `rgba(${ballot ? "120,90,40" : "255,255,255"},${r() * 0.035})`; c.fillRect(r() * w, r() * h, 2 + r() * 3, 1 + r() * 2); }
    c.strokeStyle = accent; c.lineWidth = 10; c.strokeRect(26, 26, w - 52, h - 52); c.lineWidth = 2; c.strokeRect(44, 44, w - 88, h - 88);
    if (ballot) { c.fillStyle = "#1f3a6e"; c.fillRect(44, 44, w - 88, 150); c.fillStyle = "#fff"; for (let i = 0; i < 9; i++) star(c, 96 + i * 72, 100, 15); }
    else { c.fillStyle = accent; c.fillRect(44, 44, w - 88, 8); }
    c.fillStyle = ballot ? "#fff" : accent; c.font = "700 34px 'Trebuchet MS', 'Segoe UI', system-ui, sans-serif"; c.textAlign = "center"; c.textBaseline = "middle";
    spaced(c, p.kicker.toUpperCase(), w / 2, ballot ? 158 : 112, 5);
    if (ballot) { const y0 = 222; c.strokeStyle = ink; c.fillStyle = "#fff"; c.lineWidth = 6; c.beginPath(); c.roundRect(w / 2 - 180, y0, 360, 228, 10); c.fill(); c.stroke();
      for (let i = 0; i < 4; i++) { const yy = y0 + 39 + i * 50; c.lineWidth = 5; c.strokeStyle = ink; c.beginPath(); c.ellipse(w / 2 - 128, yy, 21, 13, 0, 0, 7); if (i === 1) { c.fillStyle = accent; c.fill(); } c.stroke(); c.fillStyle = i === 1 ? ink : "#9aa3b5"; c.fillRect(w / 2 - 88, yy - 8, i === 1 ? 236 : 180 + (i % 2) * 36, 16); } }
    else dome(c, w / 2, 452, accent);
    const bw = 400, bh = 84, bx = w / 2 - bw / 2, by = h - 204, top = ballot ? 548 : 562;
    c.textBaseline = "alphabetic"; let size = 80, lines = 9, lh = 0;
    const count = (text, maxW) => { let n = 1, line = ""; for (const wd of text.split(/\s+/)) { const t = line ? line + " " + wd : wd; if (c.measureText(t).width > maxW && line) { n++; line = wd; } else line = t; } return n; };
    for (; size > 44; size -= 4) { c.font = `700 ${size}px Georgia, 'Times New Roman', serif`; lh = Math.round(size * 1.08); lines = count(p.head, w - 150); c.font = "400 32px 'Trebuchet MS', 'Segoe UI', system-ui, sans-serif"; const subLines = count(p.sub, w - 190); if (top + lines * lh + 30 + subLines * 42 < by - 18) break; }
    c.fillStyle = ink; c.font = `700 ${size}px Georgia, 'Times New Roman', serif`; let y = wrap(c, p.head, w / 2, top + size * 0.82, w - 150, lh, "center") - size * 0.82;
    c.fillStyle = accent; c.fillRect(w / 2 - 60, y + 2, 120, 6);
    c.fillStyle = ink; c.globalAlpha = 0.92; c.font = "400 32px 'Trebuchet MS', 'Segoe UI', system-ui, sans-serif"; wrap(c, p.sub, w / 2, y + 54, w - 190, 42, "center"); c.globalAlpha = 1;
    c.fillStyle = accent; c.beginPath(); c.roundRect(bx, by, bw, bh, 42); c.fill();
    c.fillStyle = ballot ? "#fff" : "#17352c"; c.font = "700 40px 'Trebuchet MS', 'Segoe UI', system-ui, sans-serif"; c.textBaseline = "middle"; c.fillText(p.cta + "  ›", w / 2, by + bh / 2 + 2);
    c.fillStyle = ink; c.globalAlpha = 0.7; c.font = "400 25px 'Trebuchet MS', 'Segoe UI', system-ui, sans-serif"; spaced(c, (p.foot || "").toUpperCase(), w / 2, h - 82, 3); c.globalAlpha = 1;
  });
}
function star(c, x, y, r){ c.beginPath(); for (let i = 0; i < 10; i++) { const a = -Math.PI / 2 + i * Math.PI / 5, rr = i % 2 ? r * 0.42 : r; c.lineTo(x + Math.cos(a) * rr, y + Math.sin(a) * rr); } c.closePath(); c.fill(); }
function spaced(c, text, x, y, gap){ const ws = [...text].map(ch => c.measureText(ch).width + gap), total = ws.reduce((a, b) => a + b, 0) - gap; let xx = x - total / 2; const al = c.textAlign; c.textAlign = "left"; [...text].forEach((ch, i) => { c.fillText(ch, xx, y); xx += ws[i]; }); c.textAlign = al; }
function dome(c, x, y, col){
  c.strokeStyle = col; c.fillStyle = col; c.lineWidth = 6; c.lineJoin = "round";
  c.fillRect(x - 230, y, 460, 12); c.fillRect(x - 200, y - 18, 400, 12);
  for (let i = 0; i < 8; i++) c.fillRect(x - 172 + i * 47, y - 118, 16, 100);
  c.fillRect(x - 196, y - 134, 392, 14); c.beginPath(); c.moveTo(x - 206, y - 134); c.lineTo(x, y - 190); c.lineTo(x + 206, y - 134); c.closePath(); c.stroke();
  c.strokeRect(x - 86, y - 246, 172, 56); for (let i = 0; i < 6; i++) c.fillRect(x - 70 + i * 26, y - 238, 8, 42);
  c.beginPath(); c.arc(x, y - 248, 92, Math.PI, 0); c.stroke(); c.beginPath(); c.moveTo(x - 92, y - 248); c.lineTo(x + 92, y - 248); c.stroke();
  c.strokeRect(x - 16, y - 372, 32, 34); c.beginPath(); c.moveTo(x, y - 372); c.lineTo(x, y - 408); c.stroke(); c.beginPath(); c.arc(x, y - 414, 7, 0, 7); c.fill();
}
function haloTexture(){ return canvasTex(256, 256, (c, w, h) => { const g = c.createRadialGradient(w / 2, h / 2, 8, w / 2, h / 2, w / 2); g.addColorStop(0, "rgba(255,255,255,1)"); g.addColorStop(0.35, "rgba(255,255,255,.45)"); g.addColorStop(1, "rgba(255,255,255,0)"); c.fillStyle = g; c.fillRect(0, 0, w, h); }); }
function sparkTexture(){ return canvasTex(64, 64, (c, w, h) => { const g = c.createRadialGradient(w / 2, h / 2, 1, w / 2, h / 2, w / 2); g.addColorStop(0, "rgba(255,255,255,1)"); g.addColorStop(0.3, "rgba(255,200,120,.8)"); g.addColorStop(1, "rgba(255,120,40,0)"); c.fillStyle = g; c.fillRect(0, 0, w, h); }); }

/* ---------- the rug: a woven design in the Persian manner, over the real weave of a photographed carpet ---------- */
function rugCanvas(fibre){
  const w = 1536, h = 1024, c = document.createElement("canvas"); c.width = w; c.height = h; const x = c.getContext("2d");
  const red = "#7a1d18", navy = "#1c2946", cream = "#e6d9bf", gold = "#c3923a", rust = "#a9472b", sage = "#5b6b4a";
  x.fillStyle = navy; x.fillRect(0, 0, w, h);
  const B = 128; x.fillStyle = red; x.fillRect(B, B, w - 2 * B, h - 2 * B);
  const ring = (inset, width, col) => { x.strokeStyle = col; x.lineWidth = width; x.strokeRect(inset, inset, w - 2 * inset, h - 2 * inset); };
  ring(22, 6, cream); ring(40, 3, gold); ring(B - 4, 8, cream); ring(B + 10, 4, gold); ring(B + 40, 3, cream);
  const leaf = (cx, cy, len, ang, col) => { x.save(); x.translate(cx, cy); x.rotate(ang); x.fillStyle = col; x.beginPath(); x.moveTo(0, 0); for (let i = 0; i <= 8; i++) { const t = i / 8; x.lineTo(len * t, -len * 0.22 * Math.sin(t * Math.PI) * (i % 2 ? 1.25 : 0.8)); } for (let i = 8; i >= 0; i--) { const t = i / 8; x.lineTo(len * t, len * 0.22 * Math.sin(t * Math.PI) * (i % 2 ? 1.25 : 0.8)); } x.closePath(); x.fill(); x.restore(); };
  const rosette = (cx, cy, r, col, col2) => { x.fillStyle = col; star8(x, cx, cy, r); x.fillStyle = col2; star8(x, cx, cy, r * 0.5); x.fillStyle = col; x.beginPath(); x.arc(cx, cy, r * 0.18, 0, 7); x.fill(); };
  const lozenge = (cx, cy, rx, ry, col) => { x.fillStyle = col; x.beginPath(); x.moveTo(cx, cy - ry); x.lineTo(cx + rx, cy); x.lineTo(cx, cy + ry); x.lineTo(cx - rx, cy); x.closePath(); x.fill(); };
  /* the border: rosettes with leaves between, all round */
  const step = 96, by = B / 2 + 8;
  for (let px = B + step / 2; px < w - B; px += step) for (const yy of [by, h - by]) { rosette(px, yy, 26, cream, rust); leaf(px + step / 2, yy, 30, Math.PI / 2 + 0.5, gold); leaf(px + step / 2, yy, 30, -Math.PI / 2 - 0.5, gold); }
  for (let py = B + step / 2; py < h - B; py += step) for (const xx of [by, w - by]) { rosette(xx, py, 26, cream, rust); leaf(xx, py + step / 2, 30, 0.5, gold); leaf(xx, py + step / 2, 30, Math.PI - 0.5, gold); }
  /* the field: a lattice of small flowers and serrated leaves */
  const fx0 = B + 60, fx1 = w - B - 60, fy0 = B + 60, fy1 = h - B - 60, cell = 118;
  for (let row = 0, yy = fy0 + cell / 2; yy < fy1; yy += cell, row++) for (let xx = fx0 + cell / 2 + (row % 2) * cell / 2; xx < fx1; xx += cell) {
    const dx = Math.abs(xx - w / 2) / 330, dy = Math.abs(yy - h / 2) / 230; if (dx * dx + dy * dy < 1) continue;      // leave room for the medallion
    lozenge(xx, yy, 22, 30, navy); lozenge(xx, yy, 11, 15, cream); for (let k = 0; k < 4; k++) leaf(xx, yy, 40, k * Math.PI / 2 + Math.PI / 4, k % 2 ? sage : gold); rosette(xx, yy, 6, cream, gold); }
  /* the medallion: a lozenge within a lozenge, pendants at both ends, a star at the heart */
  lozenge(w / 2, h / 2, 330, 230, navy); lozenge(w / 2, h / 2, 296, 204, cream); lozenge(w / 2, h / 2, 272, 186, red); lozenge(w / 2, h / 2, 190, 128, navy); lozenge(w / 2, h / 2, 170, 112, gold); lozenge(w / 2, h / 2, 120, 80, red);
  for (let k = 0; k < 8; k++) leaf(w / 2, h / 2, 110, k * Math.PI / 4, k % 2 ? cream : gold); rosette(w / 2, h / 2, 46, navy, cream);
  for (const s of [-1, 1]) { lozenge(w / 2 + s * 400, h / 2, 54, 72, navy); lozenge(w / 2 + s * 400, h / 2, 34, 48, cream); rosette(w / 2 + s * 400, h / 2, 12, red, gold); x.strokeStyle = navy; x.lineWidth = 6; x.beginPath(); x.moveTo(w / 2 + s * 330, h / 2); x.lineTo(w / 2 + s * 346, h / 2); x.stroke(); }
  /* corner spandrels */
  for (const [cx, cy] of [[fx0 - 30, fy0 - 30], [fx1 + 30, fy0 - 30], [fx0 - 30, fy1 + 30], [fx1 + 30, fy1 + 30]]) { x.fillStyle = navy; x.beginPath(); x.arc(cx, cy, 190, 0, 7); x.fill(); x.fillStyle = cream; x.beginPath(); x.arc(cx, cy, 170, 0, 7); x.fill(); x.fillStyle = navy; x.beginPath(); x.arc(cx, cy, 160, 0, 7); x.fill(); for (let k = 0; k < 6; k++) leaf(cx, cy, 130, k * Math.PI / 3, k % 2 ? gold : rust); rosette(cx, cy, 40, cream, red); }
  x.fillStyle = red; x.fillRect(0, 0, w, B - 8); x.fillRect(0, h - B + 8, w, B - 8); x.fillRect(0, 0, B - 8, h); x.fillRect(w - B + 8, 0, B - 8, h);      // the spandrels stop at the border
  x.fillStyle = navy; x.fillRect(0, 0, w, B - 8); x.fillRect(0, h - B + 8, w, B - 8); x.fillRect(0, 0, B - 8, h); x.fillRect(w - B + 8, 0, B - 8, h);
  for (let px = B + step / 2; px < w - B; px += step) for (const yy of [by, h - by]) { rosette(px, yy, 26, cream, rust); leaf(px + step / 2, yy, 30, Math.PI / 2 + 0.5, gold); leaf(px + step / 2, yy, 30, -Math.PI / 2 - 0.5, gold); }
  for (let py = B + step / 2; py < h - B; py += step) for (const xx of [by, w - by]) { rosette(xx, py, 26, cream, rust); leaf(xx, py + step / 2, 30, 0.5, gold); leaf(xx, py + step / 2, 30, Math.PI - 0.5, gold); }
  ring(22, 6, cream); ring(40, 3, gold); ring(B - 4, 8, cream);
  /* the weave: the photographed carpet, as light and shade over the design */
  if (fibre && fibre.width) { const f = document.createElement("canvas"); f.width = fibre.width; f.height = fibre.height; const fc = f.getContext("2d"); fc.drawImage(fibre, 0, 0);
    try { const img = fc.getImageData(0, 0, f.width, f.height), d = img.data; for (let i = 0; i < d.length; i += 4) { const l = 0.3 * d[i] + 0.59 * d[i + 1] + 0.11 * d[i + 2]; d[i] = d[i + 1] = d[i + 2] = Math.max(0, Math.min(255, 128 + (l - 150) * 1.4)); } fc.putImageData(img, 0, 0);
      x.globalCompositeOperation = "overlay"; const pat = x.createPattern(f, "repeat"); x.save(); const s = 256 / f.width; x.scale(s, s); x.fillStyle = pat; x.fillRect(0, 0, w / s, h / s); x.restore(); x.globalCompositeOperation = "source-over"; } catch (e) { /* a weave that cannot be read leaves the design flat */ } }
  return c;
}
function star8(x, cx, cy, r){ x.beginPath(); for (let i = 0; i < 16; i++) { const a = i * Math.PI / 8, rr = i % 2 ? r * 0.55 : r; x.lineTo(cx + Math.cos(a) * rr, cy + Math.sin(a) * rr); } x.closePath(); x.fill(); }

/* ---------- the fire: flames in a shader on crossed planes, embers, coals, and the light that flickers ---------- */
const FLAME_VERT = "varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }";
const FLAME_FRAG = `
uniform float uT; uniform float uGain; varying vec2 vUv;
float hash(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float noise(vec2 p){ vec2 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f); return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), f.x), mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), f.x), f.y); }
float fbm(vec2 p){ float v = 0.0, a = 0.5; for (int i = 0; i < 5; i++) { v += a * noise(p); p *= 2.03; a *= 0.5; } return v; }
void main(){
  vec2 uv = vUv;
  float n = fbm(vec2(uv.x * 3.0 + uT * 0.3, uv.y * 3.5 - uT * 2.2));
  float n2 = fbm(vec2(uv.x * 7.0 - uT * 0.5, uv.y * 6.0 - uT * 3.1));
  float x = (uv.x - 0.5) * 2.0 + (n - 0.5) * 0.5 * uv.y;
  float width = 1.0 - uv.y * 0.78;
  float body = 1.0 - smoothstep(0.0, 1.0, abs(x) / max(width, 0.04));
  float tall = 1.0 - smoothstep(0.3, 1.0, uv.y + (n - 0.5) * 0.7);
  float a = clamp((body * tall * (0.5 + 0.95 * n + 0.35 * n2) - 0.22) * 1.7, 0.0, 1.0);
  float heat = clamp(a * (1.5 - uv.y * 1.2), 0.0, 1.0);
  vec3 col = mix(vec3(1.0, 0.22, 0.02), vec3(1.0, 0.62, 0.12), heat);
  col = mix(col, vec3(1.0, 0.93, 0.66), pow(heat, 3.0) * (1.0 - uv.y * 0.6));
  gl_FragColor = vec4(col * a * uGain, a);
}`;
function fireplaceFire(parent, x, y, z, calm){
  const g = new THREE.Group(); g.position.set(x, y, z); parent.add(g);
  const mats = [], flames = [];
  /* several tongues of flame, each its own size and place over the logs, each flickering to its own clock */
  const tongues = [[0.62, 0.9, 0, 0, 0, 0], [0.46, 0.7, 0.14, 0.1, 1.0, 2.3], [0.42, 0.62, -0.17, -0.08, 2.1, 4.1], [0.34, 0.5, 0.04, -0.2, 0.5, 6.5], [0.5, 0.78, -0.05, 0.13, 1.6, 8.2]];
  for (const [w, h, dx, dz, ry, off] of tongues) { const mat = new THREE.ShaderMaterial({uniforms: {uT: {value: off}, uGain: {value: 1.1}}, vertexShader: FLAME_VERT, fragmentShader: FLAME_FRAG, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide});
    const f = new THREE.Mesh(new THREE.PlaneGeometry(w, h), mat); f.position.set(dx, h / 2 + 0.1, dz); f.rotation.y = ry; f.userData.off = off; g.add(f); flames.push(f); mats.push(mat); }
  const sparks = new THREE.BufferGeometry(), n = 36, pos = new Float32Array(n * 3), seeds = []; const r = rng(77);
  for (let i = 0; i < n; i++) { seeds.push([r(), r(), r()]); pos[i * 3] = (r() - 0.5) * 0.5; pos[i * 3 + 1] = r() * 0.9; pos[i * 3 + 2] = (r() - 0.5) * 0.4; }
  sparks.setAttribute("position", new THREE.BufferAttribute(pos, 3));
  const points = new THREE.Points(sparks, new THREE.PointsMaterial({map: sparkTexture(), size: 0.035, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, color: "#ffb060"})); g.add(points);
  const coalM = std({color: "#0e0603", emissive: "#ff3000", emissiveIntensity: 0.55, roughness: 1});
  const coals = []; for (let i = 0; i < 9; i++) { const c = new THREE.Mesh(new THREE.DodecahedronGeometry(0.04 + r() * 0.03, 0), coalM); c.position.set((r() - 0.5) * 0.5, 0.0, (r() - 0.5) * 0.36); c.scale.y = 0.5; c.rotation.set(r() * 3, r() * 3, 0); g.add(c); coals.push(c); }
  const bed = new THREE.Mesh(new THREE.PlaneGeometry(0.7, 0.5), new THREE.MeshBasicMaterial({map: sparkTexture(), color: "#ff5a14", transparent: true, opacity: 0.55, blending: THREE.AdditiveBlending, depthWrite: false})); bed.rotation.x = -Math.PI / 2; bed.position.y = 0.04; g.add(bed);      // the hot bed under the logs
  return {group: g, mats, flames, points, seeds, coalM, calm,
    tick(t, k){ for (const f of flames) { f.material.uniforms.uT.value = t * (0.9 + 0.2 * Math.sin(f.userData.off)) + f.userData.off; f.material.uniforms.uGain.value = 0.85 + 0.45 * k; f.scale.y = 0.9 + 0.2 * Math.sin(t * 5.1 + f.userData.off) * (k - 0.6); } coalM.emissiveIntensity = 0.7 + 0.8 * k;
      bed.material.opacity = 0.35 + 0.3 * k;
      const p = points.geometry.attributes.position; for (let i = 0; i < n; i++) { const s = seeds[i], life = ((t * (0.35 + s[0] * 0.5) + s[1]) % 1); p.setXYZ(i, (s[2] - 0.5) * 0.45 + Math.sin(t * 2 + i) * 0.03 * life, 0.2 + life * 0.95, (s[0] - 0.5) * 0.36); } p.needsUpdate = true; } };
}

/* ---------- the view: a photograph of the Rockies outside, graded for the hour ---------- */
const VIEW_VERT = "varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }";
/* The photograph is shown at the angle a real lens sees (about 65 degrees across), with its horizon at the visitor's
   eye level, on a far wider surface: beyond its sides it mirrors, above its top the sky carries on, below its foot the
   ground darkens. At night the sky parts of the photograph are strewn with stars. */
const VIEW_FRAG = `
uniform sampler2D uMap; uniform float uHas; uniform vec3 uTint; uniform float uGain; uniform vec3 uSkyTop; uniform vec3 uSkyLow; uniform vec2 uScale; uniform float uHz; uniform float uNight; uniform float uT; varying vec2 vUv;
float hash(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
void main(){
  vec2 p = vec2((vUv.x - 0.5) * uScale.x + 0.5, (vUv.y - 0.5) * uScale.y + (1.0 - uHz));
  vec3 sky = mix(uSkyLow, uSkyTop, smoothstep(0.5, 1.0, vUv.y));
  vec3 raw = texture2D(uMap, vec2(p.x, clamp(p.y, 0.0, 1.0))).rgb;
  float above = smoothstep(1.0, 1.45, p.y), below = smoothstep(0.0, -0.5, p.y);
  vec3 c = mix(raw, uSkyTop, above); c = mix(c, uSkyLow * 0.3, below);
  c = c * uTint * uGain;
  if (uNight > 0.0) { float lum = dot(raw, vec3(0.3, 0.59, 0.11)); vec2 grid = vec2(1500.0, 900.0); vec2 cell = floor(p * grid); float h = hash(cell); float d = length(fract(p * grid) - 0.5);
    float star = step(0.9962, h) * smoothstep(0.42, 0.62, lum) * smoothstep(0.5, 0.12, d) * (0.55 + 0.45 * sin(uT * (0.8 + h * 2.5) + h * 40.0)) * (1.0 - above);
    c += vec3(0.9, 0.93, 1.0) * star * uNight; }
  gl_FragColor = vec4(mix(sky, c, uHas), 1.0);
}`;

/* ---------- the room ---------- */
function buildRoom(scene, M, opts, ctx){
  const g = new THREE.Group(); scene.add(g);
  const blocks = ctx.blocks, lights = {lamps: [], posterLights: []}, mats = [];
  /* the floor */
  const floor = mesh(new THREE.PlaneGeometry(W, D), M.floor, 0, 0, 0, g); floor.rotation.x = -Math.PI / 2; floor.castShadow = false;
  /* dark backing in the plane of each wall's log centres: it shows only in the creases between logs, as the shadow there */
  const back = (w, h, x, y, z, ry) => { const m = mesh(new THREE.PlaneGeometry(w, h), M.backing, x, y, z, g, false); m.rotation.y = ry; m.receiveShadow = true; return m; };
  back(D + 0.6, HE + 0.4, -HX, (HE + 0.4) / 2, 0, Math.PI / 2); back(D + 0.6, HE + 0.4, HX, (HE + 0.4) / 2, 0, -Math.PI / 2);
  back(HX - WIN.x1 - 0.12, HR, (WIN.x1 + 0.12 + HX) / 2, HR / 2, -HZ, 0); back(HX - WIN.x1 - 0.12, HR, -(WIN.x1 + 0.12 + HX) / 2, HR / 2, -HZ, 0); back(WIN.x1 - WIN.x0 + 0.3, WIN.y0 - 0.06, 0, (WIN.y0 - 0.06) / 2, -HZ, 0);
  back(HX - 1.05, HR, (HX - 1.05) / 2 - 1.05 + 0, HR / 2, HZ, Math.PI); back(HX - 2.35, HR, -(HX + 2.35) / 2, HR / 2, HZ, Math.PI); back(1.5, HR - 2.2, -1.7, (HR + 2.2) / 2, HZ, Math.PI);
  /* the log walls: the walls along x and the walls along z interlock, half a course apart, and their ends stand proud of the corners */
  const courses = []; for (let k = 0; k < 40; k++) courses.push(LOG_R + k * COURSE);
  for (const y of courses) { if (y + LOG_R > HE + 0.14) break; logAt(D + 0.6, LOG_R, M.logs, -HX, y + COURSE / 2, 0, "z", g); logAt(D + 0.6, LOG_R, M.logs, HX, y + COURSE / 2, 0, "z", g); }
  const segments = (y, z, gaps) => {      // one course of a gable wall at height y, with openings cut out
    const xm = xMax(y) + (y <= HE ? 0.3 : -0.02); if (xm < 0.3) return;
    let from = -xm; const cuts = gaps.filter(c => y > c[2] && y - LOG_R < c[3]).sort((a, b) => a[0] - b[0]);
    for (const c of cuts) { if (c[0] - from > 0.12) logAt(c[0] - from, LOG_R, M.logs, (from + c[0]) / 2, y, z, "x", g); from = c[1]; }
    if (xm - from > 0.12) logAt(xm - from, LOG_R, M.logs, (from + xm) / 2, y, z, "x", g);
  };
  const winCut = [WIN.x0 - 0.08, WIN.x1 + 0.08, WIN.y0 - LOG_R, 99], doorCut = [-2.35, -1.05, -1, 2.2];
  for (const y of courses) { if (y - LOG_R > HR - 0.25) break; segments(y, -HZ, [winCut]); segments(y, HZ, [doorCut]); }
  /* the roof: boards on the underside, a ridge log, purlins, rafters of round logs, and two log trusses */
  const a = Math.atan2(HR - HE, HX), L = Math.hypot(HX, HR - HE);
  for (const s of [-1, 1]) { const pg = new THREE.PlaneGeometry(D + 0.6, L), uv = pg.attributes.uv; for (let i = 0; i < uv.count; i++) uv.setXY(i, uv.getX(i) * (D + 0.6) / 1.5, uv.getY(i) * L / 1.5);
    const m = mesh(pg, M.boards, s * HX / 2, (HE + HR) / 2, 0, g); m.castShadow = false; m.lookAt(m.position.clone().add(V3(-s * Math.sin(a), -Math.cos(a), 0))); }
  logAt(D + 0.8, 0.19, M.logs, 0, HR - 0.38, 0, "z", g);
  for (const s of [-1, 1]) logAt(D + 0.8, 0.14, M.logs, s * 2.6, slopeY(2.6) - 0.46, 0, "z", g);
  for (let z = -HZ + 0.25; z < HZ; z += 1.25) for (const s of [-1, 1]) logBetween(V3(s * (HX + 0.3), HE - 0.32 + 0.3 * Math.tan(a) * 0, z), V3(s * 0.12, HR - 0.32, z), 0.12, M.logs, g, 12);
  for (const z of [-1.5, 2.3]) { logAt(W + 0.6, 0.17, M.logs, 0, HE - 0.12, z, "x", g); logBetween(V3(0, HE - 0.12, z), V3(0, HR - 0.5, z), 0.14, M.logs, g, 12);
    for (const s of [-1, 1]) logBetween(V3(s * 1.5, HE - 0.05, z), V3(s * 2.6, slopeY(2.6) - 0.6, z), 0.11, M.logs, g, 12); }
  /* the gable window wall: frame, mullions, sill, and one sheet of glass shaped to the roof */
  const top = x => slopeY(x) - 0.05, wy0 = WIN.y0;      // the glass rises to the roof; a header log crosses it lower down, as in the reference rooms
  const post = (x) => box(0.14, top(x) - wy0, 0.2, M.dark, x, (top(x) + wy0) / 2, -HZ + LOG_R - 0.02, g);
  post(WIN.x0); post(WIN.x1); for (const x of [-1.02, 1.02]) box(0.08, top(x) - wy0, 0.12, M.dark, x, (top(x) + wy0) / 2, -HZ + LOG_R - 0.02, g);
  for (const y of [2.75, 4.35]) { const xr = Math.min(WIN.x1, xMax(y + 0.05) - 0.02); box(2 * xr, 0.08, 0.12, M.dark, 0, y, -HZ + LOG_R - 0.02, g); }
  box(WIN.x1 - WIN.x0 + 0.5, 0.1, 0.46, M.dark, 0, wy0 - 0.05, -HZ + LOG_R + 0.08, g);      // the sill
  for (const s of [-1, 1]) logBetween(V3(s * (WIN.x1 + 0.1), slopeY(WIN.x1) - WIN.head + 0.12, -HZ + LOG_R), V3(s * 0.02, slopeY(0) - WIN.head + 0.12, -HZ + LOG_R), 0.1, M.logs, g, 10);      // the header, following the roof
  const shape = new THREE.Shape(); shape.moveTo(WIN.x0, wy0); shape.lineTo(WIN.x1, wy0); shape.lineTo(WIN.x1, top(WIN.x1)); shape.lineTo(0, top(0)); shape.lineTo(WIN.x0, top(WIN.x0)); shape.closePath();
  const glassM = new THREE.MeshPhysicalMaterial({color: "#ffffff", transparent: true, opacity: 0.09, roughness: 0.03, metalness: 0, envMapIntensity: 1.5, depthWrite: false, side: THREE.DoubleSide});
  const glass = new THREE.Mesh(new THREE.ShapeGeometry(shape), glassM); glass.position.z = -HZ + LOG_R - 0.02; g.add(glass);
  /* the deck outside, with a log railing */
  const deck = sizedBox(9.0, 0.08, 2.8, M.deck, 0, -0.06, -HZ - 1.4 - LOG_R, g, 1.5); deck.castShadow = false;
  for (let x = -4.4; x <= 4.41; x += 1.1) logAt(1.05, 0.065, M.logs, x, 0.45, -HZ - 2.75 - LOG_R, "y", g, 10);
  logAt(9.0, 0.06, M.logs, 0, 1.0, -HZ - 2.75 - LOG_R, "x", g, 10); logAt(9.0, 0.045, M.logs, 0, 0.5, -HZ - 2.75 - LOG_R, "x", g, 8);
  for (let x = -4.3; x <= 4.31; x += 0.16) logAt(0.5, 0.022, M.logs, x, 0.75, -HZ - 2.75 - LOG_R, "y", g, 7);
  for (const s of [-1, 1]) { logAt(2.7, 0.06, M.logs, s * 4.5, 1.0, -HZ - 1.4 - LOG_R, "z", g, 10); for (let z = 0.2; z < 2.7; z += 0.16) logAt(0.5, 0.022, M.logs, s * 4.5, 0.75, -HZ - z - LOG_R, "y", g, 7); }
  /* the door in the back wall, under the loft */
  const door = sizedBox(1.28, 2.14, 0.07, M.boards, -1.7, 1.07, HZ - LOG_R + 0.02, g, 1.5);      /* flat in its frame (it once stood edge-on, turned a quarter) */
  box(1.32, 0.12, 0.16, M.dark, -1.7, 2.18, HZ - LOG_R, g); box(0.11, 2.24, 0.16, M.dark, -2.36, 1.12, HZ - LOG_R, g); box(0.11, 2.24, 0.16, M.dark, -1.04, 1.12, HZ - LOG_R, g);
  mesh(new THREE.SphereGeometry(0.035, 12, 8), M.brass, -1.32, 1.0, HZ - LOG_R - 0.06, g);
  for (const yy of [0.6, 1.5]) box(1.0, 0.08, 0.03, M.dark, -1.7, yy, HZ - LOG_R - 0.04, g);
  /* the way back (John, 2026-10-02): when the visitor came here from a page of the site, light shows round this door, and it leads back there */
  const DOOR_X = -1.7, dz = HZ - LOG_R - 0.03, dg = new THREE.Group(); dg.visible = !!opts.back; g.add(dg);
  const seamM = new THREE.MeshBasicMaterial({color: "#ffe3a6"});
  for (const sx of [-0.59, 0.59]) { const m = new THREE.Mesh(new THREE.BoxGeometry(0.045, 2.1, 0.02), seamM); m.position.set(DOOR_X + sx, 1.06, dz); dg.add(m); }
  { const m = new THREE.Mesh(new THREE.BoxGeometry(1.21, 0.045, 0.02), seamM); m.position.set(DOOR_X, 2.1, dz); dg.add(m); const m2 = new THREE.Mesh(new THREE.BoxGeometry(1.21, 0.022, 0.02), seamM); m2.position.set(DOOR_X, 0.012, dz); dg.add(m2); }
  const doorHalo = new THREE.Mesh(new THREE.PlaneGeometry(3.3, 3.9), new THREE.MeshBasicMaterial({map: haloTexture(), color: "#ffd9a0", transparent: true, opacity: 0.3, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide}));
  doorHalo.position.set(DOOR_X, 1.15, dz - 0.09); doorHalo.rotation.y = Math.PI; dg.add(doorHalo);
  const doorLight = new THREE.PointLight("#ffd9a0", 0, 5, 1.8); doorLight.position.set(DOOR_X, 1.4, dz - 0.7); dg.add(doorLight);
  const doorHit = new THREE.Mesh(new THREE.PlaneGeometry(1.45, 2.3), new THREE.MeshBasicMaterial({transparent: true, opacity: 0, depthWrite: false, side: THREE.DoubleSide})); doorHit.position.set(DOOR_X, 1.15, dz - 0.1); dg.add(doorHit);
  const backDoor = {on: !!opts.back, group: dg, hit: doorHit, halo: doorHalo, light: doorLight, seam: seamM, x: DOOR_X, wallZ: HZ, stand: V3(DOOR_X, EYE, HZ - 1.55), heat: 0};
  /* the loft over the back of the room: joists, boards, a header log on two posts, a log railing and a steep log stair */
  const loftD = HZ - LOFT_Z;
  const loft = sizedBox(W, 0.08, loftD, M.boards, 0, LOFT_Y - 0.04, (LOFT_Z + HZ) / 2, g, 1.5);
  logAt(W + 0.3, 0.17, M.logs, 0, LOFT_Y - 0.25, LOFT_Z, "x", g);
  for (let x = -HX + 1.0; x < HX; x += 1.3) logAt(loftD - 0.1, 0.1, M.logs, x, LOFT_Y - 0.16, (LOFT_Z + HZ) / 2 + 0.05, "z", g, 10);
  for (const x of [-3.4, 3.4]) { logAt(LOFT_Y - 0.4, 0.16, M.logs, x, (LOFT_Y - 0.4) / 2, LOFT_Z, "y", g); blocks.push([x - 0.2, x + 0.2, LOFT_Z - 0.2, LOFT_Z + 0.2]); }
  for (let x = -HX + 0.45; x < HX; x += 1.3) logAt(1.0, 0.065, M.logs, x, LOFT_Y + 0.5, LOFT_Z, "y", g, 10);
  logAt(W, 0.065, M.logs, 0, LOFT_Y + 0.98, LOFT_Z, "x", g, 10);
  for (let x = -HX + 0.3; x < HX; x += 0.15) logAt(0.92, 0.024, M.logs, x, LOFT_Y + 0.5, LOFT_Z, "y", g, 7);
  const stairX = -HX + 0.55, steps = 11, run = 2.6, z0 = LOFT_Z - run;      // the stair climbs toward the back along the left wall
  for (let i = 1; i <= steps; i++) sizedBox(0.9, 0.09, 0.3, M.boards, stairX, i * LOFT_Y / (steps + 1), z0 + i * run / steps, g, 1.5);
  for (const s of [-1, 1]) logBetween(V3(stairX + s * 0.47, 0.05, z0 - 0.1), V3(stairX + s * 0.47, LOFT_Y - 0.1, LOFT_Z), 0.07, M.logs, g, 10);
  for (let i = 0; i <= 3; i++) logAt(1.0, 0.04, M.logs, stairX + 0.5, 0.5 + i * LOFT_Y / 4 + 0.4, z0 + 0.3 + i * run / 4, "y", g, 8);
  logBetween(V3(stairX + 0.5, 1.0, z0 - 0.05), V3(stairX + 0.5, LOFT_Y + 0.95, LOFT_Z), 0.05, M.logs, g, 8);
  blocks.push([-HX, stairX + 0.6, z0 - 0.2, HZ]);
  /* the fireplace on the right-hand wall: a stacked-stone chimney breast floor to roof with the firebox cut into it, a raised hearth, a half-log mantel */
  const fx = HX - LOG_R, fz = FIRE.z, fh = slopeY(HX - 0.4) + 0.3;
  const ox = fx - FIRE.depth, oz0 = fz - 0.62, oz1 = fz + 0.62, oy0 = FIRE.hearth, oy1 = FIRE.top, fd = 0.62;      // the firebox: a dark room inside the stone
  stoneBlock(ox, fx, 0, fh, fz - FIRE.w / 2, oz0, M.stone, g); stoneBlock(ox, fx, 0, fh, oz1, fz + FIRE.w / 2, M.stone, g);
  stoneBlock(ox, fx, oy1, fh, oz0, oz1, M.stone, g); stoneBlock(ox + fd, fx, 0, oy1, oz0, oz1, M.stone, g); stoneBlock(ox, fx, 0, oy0, oz0, oz1, M.stone, g);
  stoneBlock(ox - 0.62, ox, 0, FIRE.hearth, fz - FIRE.w / 2 - 0.15, fz + FIRE.w / 2 + 0.15, M.stone, g);
  stoneBlock(ox - 0.66, ox + 0.02, FIRE.hearth, FIRE.hearth + 0.06, fz - FIRE.w / 2 - 0.2, fz + FIRE.w / 2 + 0.2, M.stone, g);
  const fb = new THREE.Group(); g.add(fb);
  box(0.02, oy1 - oy0, oz1 - oz0, M.soot, ox + fd - 0.02, (oy0 + oy1) / 2, fz, fb, false);
  box(fd, oy1 - oy0, 0.02, M.soot, ox + fd / 2, (oy0 + oy1) / 2, oz0 + 0.012, fb, false); box(fd, oy1 - oy0, 0.02, M.soot, ox + fd / 2, (oy0 + oy1) / 2, oz1 - 0.012, fb, false);
  box(fd, 0.02, oz1 - oz0, M.soot, ox + fd / 2, oy1 - 0.012, fz, fb, false); box(fd, 0.02, oz1 - oz0, M.soot, ox + fd / 2, oy0 + 0.012, fz, fb, false);
  const andirons = M.iron; for (const z of [fz - 0.3, fz + 0.3]) { box(0.5, 0.04, 0.04, andirons, ox + 0.3, oy0 + 0.12, z, fb); box(0.04, 0.22, 0.04, andirons, ox + 0.08, oy0 + 0.11, z, fb); }
  for (let i = 0; i < 3; i++) { const l = logAt(0.62, 0.085, M.bark, ox + 0.32, oy0 + 0.2 + (i === 2 ? 0.15 : 0), fz + (i === 2 ? 0.05 : (i - 1) * 0.22), "z", fb, 10); l.rotation.z = (i - 1) * 0.08; }
  const fire = fireplaceFire(fb, ox + 0.34, oy0 + 0.1, fz, opts.calm);
  const fireLight = new THREE.PointLight("#ff7a2c", 8, 16, 2); fireLight.position.set(ox - 0.3, oy0 + 0.6, fz); g.add(fireLight);
  if (!opts.lite) { fireLight.castShadow = true; fireLight.shadow.mapSize.set(512, 512); fireLight.shadow.bias = -0.004; fireLight.shadow.camera.near = 0.2; fireLight.shadow.camera.far = 14; }
  logAt(FIRE.w + 0.3, 0.13, M.logs, ox - 0.1, 1.68, fz, "z", g);      // the mantel
  for (const z of [fz - 1.0, fz + 1.0]) logBetween(V3(ox + 0.1, 1.3, z), V3(ox - 0.14, 1.56, z), 0.07, M.logs, g, 10);
  blocks.push([ox - 0.7, HX, fz - FIRE.w / 2 - 0.3, fz + FIRE.w / 2 + 0.3]);
  /* firewood stacked by the hearth, and a few things on the mantel */
  const wr = rng(5); for (let row = 0; row < 4; row++) for (let i = 0; i < 5 - (row % 2); i++) { const l = logAt(0.46 + wr() * 0.06, 0.07 + wr() * 0.015, M.bark, fx - 0.38 + (wr() - 0.5) * 0.04, 0.075 + row * 0.135, fz + FIRE.w / 2 + 0.55 + i * 0.155 + (row % 2) * 0.08, "x", g, 10); l.rotation.y = (wr() - 0.5) * 0.08; }
  blocks.push([fx - 0.8, HX, fz + FIRE.w / 2 + 0.3, fz + FIRE.w / 2 + 1.5]);
  const bookM = [std({color: "#4a2a1c", roughness: 0.75}), std({color: "#223a5a", roughness: 0.75}), std({color: "#6a5a3a", roughness: 0.75})];
  box(0.22, 0.05, 0.3, bookM[0], ox - 0.1, 1.68 + 0.13 + 0.025, fz - 0.9, g); box(0.2, 0.045, 0.27, bookM[1], ox - 0.1, 1.68 + 0.13 + 0.072, fz - 0.9, g);
  const candle = mesh(new THREE.CylinderGeometry(0.022, 0.025, 0.2, 12), M.cream, ox - 0.1, 1.68 + 0.13 + 0.1, fz + 0.95, g); mesh(new THREE.CylinderGeometry(0.05, 0.035, 0.03, 16), M.brass, ox - 0.1, 1.68 + 0.13 + 0.015, fz + 0.95, g);
  const flameM = std({color: "#ffd080", emissive: "#ffb040", emissiveIntensity: 0}); const candleFlame = mesh(new THREE.SphereGeometry(0.012, 8, 8), flameM, ox - 0.1, 1.68 + 0.13 + 0.215, fz + 0.95, g, false); candleFlame.scale.y = 1.8;
  /* the rug, with its fringe, in front of the fire */
  const RUG = {x: 2.4, z: fz - 0.1, w: 3.8, d: 2.8};
  const rugTop = std({color: "#7a1d18", roughness: 1}), rugSide = std({color: "#5a1612", roughness: 1});
  const rug = new THREE.Mesh(new THREE.BoxGeometry(RUG.w, 0.018, RUG.d), [rugSide, rugSide, rugTop, rugSide, rugSide, rugSide]); rug.position.set(RUG.x, 0.009, RUG.z); rug.receiveShadow = true; g.add(rug);
  M.onRug = () => { if (!M.rugBump.diff) return; const c = rugCanvas(M.rugBump.diff.image); const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 8; rugTop.map = t; rugTop.color.set("#d6cac4");
    if (M.rugBump.nor) { rugTop.normalMap = M.rugBump.nor; rugTop.normalScale.set(0.9, 0.9); } if (M.rugBump.rough) rugTop.roughnessMap = M.rugBump.rough; rugTop.needsUpdate = true; ctx.redraw(); };
  if (M.rugBump.diff) M.onRug();
  const fringeT = canvasTex(256, 64, (c, w, h) => { c.clearRect(0, 0, w, h); for (let i = 0; i < w; i += 3) { c.fillStyle = `rgba(236,226,206,${0.6 + Math.random() * 0.4})`; c.fillRect(i, 0, 1.4, h * (0.75 + Math.random() * 0.25)); } });
  for (const s of [-1, 1]) { const f = new THREE.Mesh(new THREE.PlaneGeometry(0.09, RUG.d - 0.1), new THREE.MeshStandardMaterial({map: fringeT, transparent: true, alphaTest: 0.3, roughness: 1, side: THREE.DoubleSide})); f.rotation.x = -Math.PI / 2; f.rotation.z = s > 0 ? -Math.PI / 2 : Math.PI / 2; f.position.set(RUG.x + s * (RUG.w / 2 + 0.045), 0.004, RUG.z); f.receiveShadow = true; g.add(f); }
  /* the two posters, on the log wall either side of the windows: paper that needs no light, a frame, a brass picture light, a halo */
  const halo = haloTexture();
  const posters = (opts.posters || []).slice(0, 2).map((p, i) => { const pg = new THREE.Group(), x = (i ? 1 : -1) * (WIN.x1 + 0.7), pw = 1.12, ph = 1.68, tint = p.look === "record" ? "#ffd27a" : "#9cc4ff";      // close to the window, so a phone's narrower view holds both
    const paper = new THREE.Mesh(new THREE.PlaneGeometry(pw, ph), new THREE.MeshBasicMaterial({map: posterTexture(p)})); paper.position.z = 0.045; pg.add(paper);
    const fr = std({color: "#2e1d10", roughness: 0.5});
    box(pw + 0.12, 0.06, 0.05, fr, 0, ph / 2 + 0.03, 0.03, pg); box(pw + 0.12, 0.06, 0.05, fr, 0, -ph / 2 - 0.03, 0.03, pg); box(0.06, ph, 0.05, fr, -pw / 2 - 0.03, 0, 0.03, pg); box(0.06, ph, 0.05, fr, pw / 2 + 0.03, 0, 0.03, pg);
    box(pw + 0.04, ph + 0.04, 0.02, std({color: "#111", roughness: 0.9}), 0, 0, 0.02, pg);
    const glow = new THREE.Mesh(new THREE.PlaneGeometry(pw * 2.4, ph * 1.9), new THREE.MeshBasicMaterial({map: halo, color: tint, transparent: true, opacity: 0.35, blending: THREE.AdditiveBlending, depthWrite: false})); glow.position.z = 0.012; pg.add(glow);
    /* the picture light: a brass hood on an arm, and the pool of light it throws down the wall */
    box(0.42, 0.045, 0.1, M.brass, 0, ph / 2 + 0.26, 0.2, pg); box(0.02, 0.02, 0.2, M.brass, 0, ph / 2 + 0.27, 0.1, pg);
    const tube = mesh(new THREE.CylinderGeometry(0.012, 0.012, 0.36, 10), std({color: "#fff2d0", emissive: "#ffe0a0", emissiveIntensity: 2.5, roughness: 0.4}), 0, ph / 2 + 0.225, 0.2, pg, false); tube.rotation.z = Math.PI / 2;
    const spot = new THREE.SpotLight(tint, 0, 5, 0.62, 0.7, 1.6); spot.position.set(0, ph / 2 + 0.22, 0.24); spot.target.position.set(0, -0.2, 0.05); pg.add(spot); pg.add(spot.target);
    const light = new THREE.PointLight(tint, 0, 4, 1.8); light.position.set(0, 0.1, 0.5); pg.add(light);
    pg.position.set(x, 1.72, -HZ + LOG_R + 0.012); g.add(pg); lights.posterLights.push(spot, light);
    return {group: pg, paper, glow, light, spot, tube, url: p.url, x, wallZ: -HZ, stand: V3(x * 0.84, EYE, -HZ + 2.0), heat: 0}; });
  /* lamps: a tall side table's worth of warm light at each end of the sofa (the tables are models; the lamps are built here) */
  const lamp = (x, y, z) => { const lg = new THREE.Group(); lg.position.set(x, y, z); g.add(lg);
    mesh(new THREE.CylinderGeometry(0.075, 0.1, 0.05, 20), M.iron, 0, 0.025, 0, lg); mesh(new THREE.CylinderGeometry(0.035, 0.05, 0.3, 14), std({color: "#2a1a10", roughness: 0.5}), 0, 0.2, 0, lg); mesh(new THREE.CylinderGeometry(0.012, 0.012, 0.22, 8), M.brass, 0, 0.46, 0, lg);
    const shadeM = std({color: "#e9dcc0", roughness: 0.95, side: THREE.DoubleSide, emissive: "#ffd9a0", emissiveIntensity: 0}); const shade = mesh(new THREE.CylinderGeometry(0.12, 0.19, 0.27, 28, 1, true), shadeM, 0, 0.6, 0, lg, false);
    const bulbM = std({color: "#fff8e8", emissive: "#fff0c0", emissiveIntensity: 0}); mesh(new THREE.SphereGeometry(0.03, 12, 10), bulbM, 0, 0.58, 0, lg, false);
    const pl = new THREE.PointLight("#ffd9a0", 0, 9, 2); pl.position.set(0, 0.62, 0); lg.add(pl); lights.lamps.push({pl, shadeM, bulbM}); return lg; };
  /* dust in the light from the windows */
  const mr = rng(9), mp = new Float32Array(160 * 3); for (let i = 0; i < 160; i++) { mp[i * 3] = (mr() - 0.5) * 5.6; mp[i * 3 + 1] = 0.3 + mr() * 3.6; mp[i * 3 + 2] = -HZ + 0.6 + mr() * 2.8; }
  const motesG = new THREE.BufferGeometry(); motesG.setAttribute("position", new THREE.BufferAttribute(mp, 3));
  const motes = new THREE.Points(motesG, new THREE.PointsMaterial({color: "#fff6e0", size: 0.007, transparent: true, opacity: 0.22, depthWrite: false})); g.add(motes);
  return {group: g, floor, glassM, fire, fireLight, posters, door: backDoor, lamp, lights, candleFlame: flameM, motes, RUG, fz, ox, loft};
}

/* ---------- outside: the photograph, the sky behind it, and nothing else that would spoil it ---------- */
function buildView(scene){
  const PW = 300, PH = 160, DIST = 75, LENS = 95;      // the surface, how far off it stands, and the width the photograph takes on it (about 65 degrees)
  const geo = new THREE.PlaneGeometry(PW, PH);
  const mat = new THREE.ShaderMaterial({uniforms: {uMap: {value: null}, uHas: {value: 0}, uTint: {value: new THREE.Vector3(1, 1, 1)}, uGain: {value: 1}, uSkyTop: {value: new THREE.Color("#5d9be0")}, uSkyLow: {value: new THREE.Color("#dfeaf6")},
    uScale: {value: new THREE.Vector2(PW / LENS, PH / (LENS / 1.5))}, uHz: {value: 0.55}, uNight: {value: 0}, uT: {value: 0}}, vertexShader: VIEW_VERT, fragmentShader: VIEW_FRAG, depthWrite: true});
  const m = new THREE.Mesh(geo, mat); m.position.set(0, EYE, -HZ - DIST); scene.add(m);
  return {mesh: m, mat, place(horizon, aspect){ mat.uniforms.uScale.value.set(PW / LENS, PH / (LENS / (aspect || 1.5))); mat.uniforms.uHz.value = horizon; }};
}

/* ---------- where a visitor cannot stand ---------- */
function makeFree(blocks){
  return (x, z) => { const inX = HX - LOG_R - RADIUS, inZ = HZ - LOG_R - RADIUS; if (x < -inX || x > inX || z < -inZ || z > inZ) return false;
    return !blocks.some(b => x > b[0] - RADIUS && x < b[1] + RADIUS && z > b[2] - RADIUS && z < b[3] + RADIUS); };
}

/* ---------- the room, running ---------- */
export function start(canvas, opts = {}){
  const calm = !!opts.calm, lite = opts.lite != null ? !!opts.lite : (matchMedia("(pointer: coarse)").matches || (navigator.hardwareConcurrency || 8) <= 4);
  let renderer;
  try { renderer = new THREE.WebGLRenderer({canvas, antialias: true, powerPreference: "high-performance"}); } catch (e) { return null; }
  renderer.toneMapping = THREE.NeutralToneMapping; renderer.toneMappingExposure = 1.0; renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  const ANISO = Math.min(8, renderer.capabilities.getMaxAnisotropy());
  const base = opts.assets || "cabin_assets/";
  /* the visitor and the clock, declared first: files that arrive early redraw the room through kick() */
  const me = {x: -0.9, z: 2.1, yaw: -0.12, pitch: 0.03, bob: 0};      // just in front of the loft, facing the windows and both posters
  let walkTo = null, going = null, moved = false, hover = -1, raf = 0, last = 0, clock = 0, dead = false, composer = null, bloom = null;
  const scene = new THREE.Scene(), camera = new THREE.PerspectiveCamera(62, 1, 0.05, 400);
  camera.rotation.order = "YXZ";
  scene.background = new THREE.Color("#120d0a");
  const pm = new THREE.PMREMGenerator(renderer); scene.environment = pm.fromScene(new RoomEnvironment(), 0.04).texture; pm.dispose();
  const hemi = new THREE.HemisphereLight("#dbe8ff", "#7a5a3c", 0.8), sun = new THREE.DirectionalLight("#fff2dc", 3); scene.add(hemi, sun, sun.target);
  sun.castShadow = true; sun.shadow.mapSize.set(lite ? 1024 : 2048, lite ? 1024 : 2048); sun.shadow.bias = -0.0006; sun.shadow.normalBias = 0.03;
  Object.assign(sun.shadow.camera, {left: -9, right: 9, top: 9, bottom: -9, near: 1, far: 120}); sun.target.position.set(0, 1.2, -1.5);
  /* files arriving: the page is told, and the room is redrawn as each one lands */
  const manager = new THREE.LoadingManager(); let total = 0;
  manager.onProgress = (url, done, all) => { total = all; opts.onProgress && opts.onProgress(done, all); kick(); };
  manager.onLoad = () => { opts.onReady && opts.onReady(); kick(); };
  const blocks = [], free = makeFree(blocks), ctx = {blocks, redraw: () => kick()};
  const M = materials(base, manager, ANISO, ctx.redraw);
  let R = buildRoom(scene, M, opts, ctx), VIEW = buildView(scene), S = HOURS.afternoon, when = "afternoon", season = "summer";
  /* the furniture: CC0 models from Poly Haven, placed on the floor; each one blocks the floor it stands on */
  const gltf = new GLTFLoader(manager).setPath(base + "models/");
  const placed = {};
  function model(id, file, at){
    gltf.load(`${id}/${file}`, g => { const o = g.scene; o.rotation.y = at.ry || 0; o.scale.setScalar(at.scale || 1); o.updateMatrixWorld(true);
      const bb = new THREE.Box3().setFromObject(o); o.position.set(at.x - (bb.min.x + bb.max.x) / 2 * 0 , -bb.min.y + (at.y || 0), at.z);
      if (at.center !== false) { o.position.x -= (bb.min.x + bb.max.x) / 2; o.position.z -= (bb.min.z + bb.max.z) / 2; }
      o.traverse(n => { if (n.isMesh) { n.castShadow = true; n.receiveShadow = true; const ms = Array.isArray(n.material) ? n.material : [n.material]; for (const m of ms) { if (at.tint && m.color) m.color.multiply(new THREE.Color(at.tint)); if (at.flat && m.map) { m.map = null; m.color.set(at.flat); m.needsUpdate = true; } if (at.rough != null) m.roughness = at.rough; } } });
      R.group.add(o); o.updateMatrixWorld(true); const wb = new THREE.Box3().setFromObject(o);
      if (at.block !== false && wb.min.y < 1.2) blocks.push([wb.min.x, wb.max.x, wb.min.z, wb.max.z]);
      placed[id] = {obj: o, box: wb}; at.then && at.then(o, wb); kick(); }, undefined, () => { placed[id] = null; });
  }
  const fz = R.fz, rug = R.RUG;
  model("sofa_02", "sofa_02_1k.gltf", {x: rug.x - 1.55, z: rug.z, ry: Math.PI / 2, flat: "#4e2c17", rough: 0.55,
    then: (o, wb) => { model("throw_pillows_01", "throw_pillows_01_1k.gltf", {x: wb.min.x + 0.42, y: (wb.max.y - wb.min.y) * 0.42, z: wb.max.z - 0.55, ry: Math.PI / 2 - 0.3, block: false});
      R.lamp(rug.x - 1.55, 0, wb.min.z - 0.55).userData.table = true; R.lamp(rug.x - 1.55, 0, wb.max.z + 0.55);
      model("side_table_tall_01", "side_table_tall_01_1k.gltf", {x: rug.x - 1.55, z: wb.min.z - 0.55, then: (t, tb) => { R.lights.lamps[0] && (R.lights.lamps[0].pl.parent.position.y = tb.max.y); }});
      model("side_table_tall_01", "side_table_tall_01_1k.gltf", {x: rug.x - 1.55, z: wb.max.z + 0.55, then: (t, tb) => { R.lights.lamps[1] && (R.lights.lamps[1].pl.parent.position.y = tb.max.y); }}); }});
  model("small_wooden_table_01", "small_wooden_table_01_1k.gltf", {x: rug.x + 0.1, z: rug.z, ry: Math.PI / 2, tint: "#c9a27a",
    then: (o, wb) => { const y = wb.max.y; const bm = std({color: "#5a2e1e", roughness: 0.7}), bm2 = std({color: "#2c3f5e", roughness: 0.7});
      box(0.24, 0.045, 0.32, bm, rug.x + 0.1 - 0.25, y + 0.023, rug.z + 0.15, R.group); box(0.21, 0.04, 0.29, bm2, rug.x + 0.1 - 0.23, y + 0.065, rug.z + 0.13, R.group).rotation.y = 0.12;
      mesh(new THREE.CylinderGeometry(0.04, 0.035, 0.09, 18), std({color: "#e9e4d6", roughness: 0.35}), rug.x + 0.1 + 0.3, y + 0.045, rug.z - 0.3, R.group); mesh(new THREE.TorusGeometry(0.03, 0.007, 8, 16), std({color: "#e9e4d6", roughness: 0.35}), rug.x + 0.1 + 0.35, y + 0.05, rug.z - 0.3, R.group).rotation.y = Math.PI / 2;
      mesh(new THREE.CylinderGeometry(0.11, 0.09, 0.05, 20), std({color: "#4a3a2a", roughness: 0.6}), rug.x + 0.1 + 0.25, y + 0.025, rug.z + 0.35, R.group); kick(); }});
  model("ArmChair_01", "ArmChair_01_1k.gltf", {x: rug.x + 0.5, z: rug.z - 1.85, ry: 0.42, tint: "#d8b48e"});
  model("ArmChair_01", "ArmChair_01_1k.gltf", {x: rug.x + 0.5, z: rug.z + 1.85, ry: Math.PI - 0.42, tint: "#d8b48e",
    then: (o, wb) => { const b = sizedBox(0.52, 0.03, 0.4, M.plaid, wb.max.x - 0.2, wb.min.y + (wb.max.y - wb.min.y) * 0.62, rug.z + 1.85 + 0.2, R.group, 0.6); b.rotation.y = -0.42; b.rotation.z = -0.08; }});
  model("Rockingchair_01", "Rockingchair_01_1k.gltf", {x: -3.4, z: -2.6, ry: -0.75});
  model("antique_ceramic_vase_01", "antique_ceramic_vase_01_1k.gltf", {x: R.ox - 0.1, y: 1.68 + 0.13, z: fz + 0.2, scale: 0.75, block: false});
  model("lantern_chandelier_01", "lantern_chandelier_01_1k.gltf", {x: rug.x - 0.2, y: 0, z: rug.z, block: false, scale: 1.1, then: (o, wb) => {
    o.position.y += 2.6 - wb.min.y; o.updateMatrixWorld(true); const b2 = new THREE.Box3().setFromObject(o);      // it hangs just above head height, on a chain from the ridge
    mesh(new THREE.CylinderGeometry(0.012, 0.012, HR - 0.45 - b2.max.y, 8), M.iron, rug.x - 0.2, (HR - 0.45 + b2.max.y) / 2, rug.z, R.group, false);
    const pl = new THREE.PointLight("#ffcf8a", 0, 14, 2); pl.position.set(rug.x - 0.2, (b2.min.y + b2.max.y) / 2, rug.z); R.group.add(pl);
    const bulbM = std({color: "#fff6e0", emissive: "#ffe6b0", emissiveIntensity: 0}); mesh(new THREE.SphereGeometry(0.035, 12, 10), bulbM, rug.x - 0.2, (b2.min.y + b2.max.y) / 2, rug.z, R.group, false);
    R.lights.lamps.push({pl, shadeM: null, bulbM, chandelier: true}); applyHour(); }});

  /* ---- the hour and the season ---- */
  const viewLoader = new THREE.TextureLoader(), viewCache = {}; let shown = null;
  function pickView(hour, seas){ const list = (opts.views || {})[hour] || []; if (!list.length) return null; return list.find(v => v.season === seas) || list.find(v => v.season === "any") || list[0]; }
  function showView(hour, seas){
    const v = pickView(hour, seas); const u = VIEW.mat.uniforms; u.uSkyTop.value.set(S.sky[0]); u.uSkyLow.value.set(S.sky[1]); u.uTint.value.set(...S.view.tint); u.uGain.value = S.view.gain; u.uNight.value = S.view.night || 0;
    if (!v) { u.uHas.value = 0; shown = null; opts.onView && opts.onView(null); return; }
    const apply = t => { if (shown !== v) return; u.uMap.value = t; u.uHas.value = 1; VIEW.place(v.horizon == null ? 0.55 : v.horizon, (v.w && v.h) ? v.w / v.h : 1.5); kick(); };
    shown = v; opts.onView && opts.onView({caption: v.caption, credit: v.credit, season: v.season, shown: v.season === seas || v.season === "any", hour, wanted: seas});
    if (viewCache[v.file]) apply(viewCache[v.file]); else viewLoader.load(base + "view/" + v.file, t => { t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = ANISO; t.wrapS = THREE.MirroredRepeatWrapping; t.wrapT = THREE.ClampToEdgeWrapping; t.minFilter = THREE.LinearMipmapLinearFilter; viewCache[v.file] = t; apply(t); }, undefined, () => { u.uHas.value = 0; });
  }
  function applyHour(){
    const s = S; renderer.toneMappingExposure = s.expo; hemi.color.set(s.hemi[0]); hemi.groundColor.set(s.hemi[1]); hemi.intensity = s.hemi[2];
    sun.color.set(s.sunCol); sun.intensity = s.sunI; sun.position.set(s.sun[0] * 40, s.sun[1] * 40, s.sun[2] * 40).add(sun.target.position);
    scene.environmentIntensity = s.env;
    for (const l of R.lights.lamps) { l.pl.intensity = (l.chandelier ? 26 : 16) * s.lamps; if (l.shadeM) l.shadeM.emissiveIntensity = 1.3 * s.lamps; l.bulbM.emissiveIntensity = 4 * s.lamps; }
    R.candleFlame.emissiveIntensity = 3 * s.lamps;
    R.motes.visible = s.motes > 0; R.motes.material.opacity = 0.5 * s.motes;
    R.glassM.opacity = s.lamps ? 0.16 : 0.09;
  }
  function setWhen(w, se){ when = HOURS[w] ? w : whenNow(); season = se || season; S = HOURS[when]; applyHour(); showView(when, season); draw(); kick(); }

  /* ---- drawing: through the composer for bloom on the ordinary path, straight to the canvas on the light one ---- */
  if (!lite) { composer = new EffectComposer(renderer); composer.addPass(new RenderPass(scene, camera)); bloom = new UnrealBloomPass(new THREE.Vector2(960, 600), 0.42, 0.55, 0.92); composer.addPass(bloom); composer.addPass(new OutputPass()); }
  function size(w, h){
    const ratio = Math.min(devicePixelRatio || 1, lite ? 1 : 1.5); w = w || canvas.clientWidth || 960; h = h || canvas.clientHeight || 600;
    renderer.setPixelRatio(ratio); renderer.setSize(w, h, false); if (composer) { composer.setPixelRatio(ratio); composer.setSize(w, h); }
    camera.aspect = w / h; const hf = 84 * Math.PI / 180;      // keep both posters in view on a tall, narrow screen
    camera.fov = Math.max(56, Math.min(camera.aspect < 0.8 ? 92 : 86, 2 * Math.atan(Math.tan(hf / 2) / camera.aspect) * 180 / Math.PI)); camera.updateProjectionMatrix();
  }
  size();
  if (camera.aspect < 0.8) { me.x = 0; me.z = 3.8; me.yaw = 0; }      // a phone held upright starts further back, under the loft's edge, so both posters fit its view

  /* ---- moving and looking ---- */
  const keys = new Set(), MOVE = new Set(["w", "a", "s", "d", "arrowup", "arrowdown", "arrowleft", "arrowright"]);
  const told = () => { if (!moved) { moved = true; opts.onMove && opts.onMove(); } };
  const onKey = e => { const k = e.key.toLowerCase(); if (!MOVE.has(k) || e.ctrlKey || e.metaKey || e.altKey) return; const t = e.target; if (t && t !== document.body && t !== canvas && /^(INPUT|TEXTAREA|SELECT|BUTTON|A)$/.test(t.tagName) && !/^arrow/.test(k)) return;
    if (t && /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName)) return;
    if (e.type === "keydown") { keys.add(k); walkTo = null; told(); kick(); e.preventDefault(); } else keys.delete(k); };
  addEventListener("keydown", onKey); addEventListener("keyup", onKey); const onBlur = () => keys.clear(); addEventListener("blur", onBlur);

  const ray = new THREE.Raycaster(), ndc = new THREE.Vector2();
  function pick(ev){
    const b = canvas.getBoundingClientRect(); ndc.set(((ev.clientX - b.left) / b.width) * 2 - 1, -((ev.clientY - b.top) / b.height) * 2 + 1); ray.setFromCamera(ndc, camera);
    const hit = ray.intersectObjects(R.posters.map(p => p.paper), false)[0]; if (hit) return {poster: R.posters.findIndex(p => p.paper === hit.object)};
    if (R.door.on && ray.intersectObject(R.door.hit, false)[0]) return {poster: 2};      /* the way back: the page's third sign */
    const f = ray.intersectObject(R.floor, false)[0]; return f ? {floor: f.point} : {};
  }
  let down = null;      // no pointer capture: the listeners for the drag sit on the window (a captured pointer once made the door's cards unclickable)
  const onDown = ev => { if (going) return; down = {x: ev.clientX, y: ev.clientY, drag: false, id: ev.pointerId}; };
  const onMoveP = ev => {
    if (down && ev.pointerId === down.id) { const dx = ev.clientX - down.x, dy = ev.clientY - down.y;
      if (!down.drag && Math.hypot(dx, dy) > 6) down.drag = true;
      if (down.drag && ev.pointerType !== "touch") { me.yaw += (ev.movementX || 0) * 0.0042; me.pitch = Math.max(-0.7, Math.min(0.75, me.pitch + (ev.movementY || 0) * 0.0032)); told(); kick(); }
      return; }
    if (ev.target !== canvas || going) return;
    const p = pick(ev), h = p.poster != null ? p.poster : -1; if (h !== hover) { hover = h; canvas.style.cursor = h >= 0 ? "pointer" : "grab"; opts.onHover && opts.onHover(h); kick(); }
  };
  const onUp = ev => { if (!down || ev.pointerId !== down.id) return; const d = down; down = null; if (d.drag || going || ev.target !== canvas) return;
    const p = pick(ev); if (p.poster === 2) goBack(); else if (p.poster != null) go(p.poster); else if (p.floor) { walkTo = nearestFree(p.floor.x, p.floor.z); told(); kick(); } };
  canvas.addEventListener("pointerdown", onDown); addEventListener("pointermove", onMoveP); addEventListener("pointerup", onUp); addEventListener("pointercancel", onUp);
  canvas.style.touchAction = "none"; canvas.style.cursor = "grab";
  let lastTouch = null;      // a finger gives no movementX in some browsers: work the turn out from positions
  const onTouch = ev => { const t = ev.touches[0]; if (!t) { lastTouch = null; return; } if (lastTouch && down && down.drag) { me.yaw += (t.clientX - lastTouch.x) * 0.0046; me.pitch = Math.max(-0.7, Math.min(0.75, me.pitch + (t.clientY - lastTouch.y) * 0.0034)); kick(); } lastTouch = {x: t.clientX, y: t.clientY}; };
  canvas.addEventListener("touchmove", onTouch, {passive: true}); canvas.addEventListener("touchend", () => { lastTouch = null; }, {passive: true});

  function nearestFree(x, z){ const inX = HX - LOG_R - RADIUS, inZ = HZ - LOG_R - RADIUS; x = Math.max(-inX, Math.min(inX, x)); z = Math.max(-inZ, Math.min(inZ, z));
    if (free(x, z)) return {x, z}; for (let r = 0.2; r < 2.6; r += 0.2) for (let a = 0; a < 12; a++) { const nx = x + Math.cos(a * Math.PI / 6) * r, nz = z + Math.sin(a * Math.PI / 6) * r; if (free(nx, nz)) return {x: nx, z: nz}; } return {x: me.x, z: me.z}; }
  const yawTo = (x, z) => Math.atan2(-(x - me.x), -(z - me.z));
  const turn = (to, k) => { let d = to - me.yaw; d = Math.atan2(Math.sin(d), Math.cos(d)); me.yaw += d * k; return Math.abs(d); };

  function go(i){      // walk up to a poster, then leave through it
    const p = R.posters[i]; if (!p || going) return; told();
    if (calm) { opts.onLeave && opts.onLeave(p.url, i); return; }
    going = {i, t: 0, from: {x: me.x, z: me.z, yaw: me.yaw, pitch: me.pitch}, left: false}; walkTo = null; kick();
  }
  function goBack(){      // walk up to the door behind the visitor, then leave through it to the page they came from
    if (!R.door.on || going) return; told();
    if (calm) { opts.onBack && opts.onBack(); return; }
    going = {i: 2, t: 0, from: {x: me.x, z: me.z, yaw: me.yaw, pitch: me.pitch}, left: false}; walkTo = null; kick();
  }
  function look(i){ const p = i === 2 ? (R.door.on ? R.door : null) : R.posters[i]; if (!p || going) return; me.yaw = yawTo(p.x, p.wallZ); me.pitch = 0; kick(); }

  function step(dt){
    clock += dt;
    if (going) { const p = going.i === 2 ? R.door : R.posters[going.i], g = going; g.t += dt / 1.6; const e = g.t >= 1 ? 1 : 1 - Math.pow(1 - g.t, 3);
      me.x = g.from.x + (p.stand.x - g.from.x) * e; me.z = g.from.z + (p.stand.z - g.from.z) * e; const want = Math.atan2(-(p.x - me.x), -(p.wallZ - me.z)); let d = want - g.from.yaw; d = Math.atan2(Math.sin(d), Math.cos(d)); me.yaw = g.from.yaw + d * e; me.pitch = g.from.pitch * (1 - e);
      p.heat = Math.min(1, p.heat + dt * 2);
      if (g.t >= 1 && !g.left) { g.left = true; if (g.i === 2) opts.onBack && opts.onBack(); else opts.onLeave && opts.onLeave(p.url, g.i); }
      return true; }
    let fwd = 0, side = 0, rot = 0;
    if (keys.has("w") || keys.has("arrowup")) fwd += 1; if (keys.has("s") || keys.has("arrowdown")) fwd -= 1;
    if (keys.has("a")) side -= 1; if (keys.has("d")) side += 1; if (keys.has("arrowleft")) rot += 1; if (keys.has("arrowright")) rot -= 1;
    me.yaw += rot * 1.9 * dt;
    let vx = 0, vz = 0, busy = !!(fwd || side || rot);
    if (fwd || side) { const s = Math.sin(me.yaw), c = Math.cos(me.yaw), n = Math.hypot(fwd, side) || 1; vx = (-s * fwd + c * side) / n; vz = (-c * fwd - s * side) / n; }
    else if (walkTo) { const dx = walkTo.x - me.x, dz = walkTo.z - me.z, dist = Math.hypot(dx, dz); if (dist < 0.06) walkTo = null; else { vx = dx / dist; vz = dz / dist; turn(Math.atan2(-vx, -vz), Math.min(1, dt * 3)); busy = true; } }
    if (vx || vz) { const sp = 2.2 * dt, nx = me.x + vx * sp, nz = me.z + vz * sp; let went = false;
      if (free(nx, me.z)) { me.x = nx; went = true; } if (free(me.x, nz)) { me.z = nz; went = true; }
      if (went) me.bob += dt * 9; else walkTo = null;
      if (went && R.door.on && me.z > HZ - 1.25 && Math.abs(me.x - R.door.x) < 0.55 && Math.cos(me.yaw) < -0.5) { goBack(); return true; } }      /* walked up to the glowing door, facing it */
    { const want = hover === 2 ? 1 : 0, dr = R.door; if (dr.on && dr.heat !== want) { dr.heat += Math.sign(want - dr.heat) * Math.min(Math.abs(want - dr.heat), dt * 4); busy = true; } }
    R.posters.forEach((p, i) => { const want = i === hover ? 1 : 0; if (p.heat !== want) { p.heat += Math.sign(want - p.heat) * Math.min(Math.abs(want - p.heat), dt * 4); busy = true; } });
    return busy;
  }
  function draw(){
    const f = calm ? 0 : 1, t = clock;
    camera.position.set(me.x, EYE + (calm ? 0 : Math.sin(me.bob) * 0.022), me.z); camera.rotation.set(me.pitch, me.yaw, 0);
    const fl = 0.86 + f * (0.09 * Math.sin(t * 11.3) + 0.06 * Math.sin(t * 23.1 + 1.3) + 0.05 * Math.sin(t * 5.7));
    R.fireLight.intensity = S.fire * fl; R.fireLight.position.x = R.ox - 0.3 + f * 0.03 * Math.sin(t * 7.1); R.fire.tick(f ? t : 2.7, fl); VIEW.mat.uniforms.uT.value = t;
    R.posters.forEach((p, i) => { const pulse = 0.5 + 0.5 * Math.sin(t * 1.7 + i * Math.PI) * f, k = 0.55 + 0.45 * pulse + p.heat * 0.9;
      p.glow.material.opacity = Math.min(1, 0.22 + 0.3 * k) * (0.6 + 0.4 * S.poster); p.glow.scale.setScalar(1 + 0.05 * pulse + 0.1 * p.heat); p.spot.intensity = 6 * S.poster * (0.8 + 0.3 * k); p.light.intensity = 0.8 * S.poster * k; p.tube.material.emissiveIntensity = 2 + 1.5 * k; p.group.scale.setScalar(1 + 0.02 * p.heat); });
    if (R.door.on) { const dr = R.door, pulse = 0.5 + 0.5 * Math.sin(t * 1.4 + 1) * f, k = 0.6 + 0.4 * pulse + dr.heat * 0.9; dr.halo.material.opacity = Math.min(0.6, 0.14 + 0.18 * k); dr.light.intensity = 3.2 * k; dr.seam.color.setScalar(1).multiply(TINT_BACK).multiplyScalar(0.75 + 0.35 * k); }
    if (!calm && S.motes > 0) { const p = R.motes.geometry.attributes.position; for (let i = 0; i < p.count; i += 3) p.setY(i, 0.3 + ((p.getY(i) - 0.3 + 0.012) % 3.6)); p.needsUpdate = true; }
    if (composer) composer.render(); else renderer.render(scene, camera);
  }
  function frame(now){
    raf = 0; if (dead) return; const dt = Math.min(0.05, last ? (now - last) / 1000 : 0.016); last = now;
    const busy = step(dt); draw();
    if (!calm || busy || keys.size) kick(); else last = 0;      // with motion off the room is drawn only when something changes
  }
  function kick(){ if (!raf && !dead && !document.hidden) raf = requestAnimationFrame(frame); }
  const onVis = () => { last = 0; kick(); }, onSize = () => { size(); if (calm) draw(); kick(); };
  document.addEventListener("visibilitychange", onVis); addEventListener("resize", onSize);
  setWhen(opts.when || whenNow(), opts.season || seasonNow());

  return {
    go, look, goBack, setWhen,
    /* one frame as a picture: view = {x, z, yaw, pitch, t} places the visitor and the moment */
    still(w = 960, h = 600, view = {}){ const keep = Object.assign({}, me), kc = clock; Object.assign(me, view); if (view.t != null) clock = view.t;
      renderer.setPixelRatio(1); renderer.setSize(w, h, false); if (composer) { composer.setPixelRatio(1); composer.setSize(w, h); } camera.aspect = w / h; camera.updateProjectionMatrix(); draw(); const url = canvas.toDataURL("image/jpeg", 0.86);
      Object.assign(me, keep); clock = kc; size(); draw(); return url; },
    bench(n = 30){ const gl = renderer.getContext(); draw(); gl.finish(); const t0 = performance.now(); for (let i = 0; i < n; i++) { clock += 0.016; draw(); } gl.finish(); return (performance.now() - t0) / n; },
    loaded(){ return placed; },
    where(){ return {x: me.x, z: me.z, yaw: me.yaw, pitch: me.pitch}; },
    dispose(){ dead = true; cancelAnimationFrame(raf); removeEventListener("keydown", onKey); removeEventListener("keyup", onKey); removeEventListener("blur", onBlur); removeEventListener("pointermove", onMoveP); removeEventListener("pointerup", onUp); removeEventListener("pointercancel", onUp); removeEventListener("resize", onSize); document.removeEventListener("visibilitychange", onVis); renderer.dispose(); },
  };
}
