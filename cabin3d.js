import * as THREE from "./vendor/three.module.min.js";
import {GLTFLoader} from "./vendor/jsm/loaders/GLTFLoader.js";
import {RoomEnvironment} from "./vendor/jsm/environments/RoomEnvironment.js";

/* ---------- the room's measurements: x across, z toward the glass wall (-z), y up ---------- */
const W = 10.4, D = 9.0, HX = W / 2, HZ = D / 2;      // inside the log faces
const HE = 4.2, HR = 7.0;                             // the eave (top of the side walls) and the ridge
const LOG_R = 0.17, COURSE = 0.325, TEXW = 1.05;      // a wall log, one course, and the pine texture's real width in metres
const WIN = {x0: -3.05, x1: 3.05, y0: 0.68, head: 0.42, mull: [-1.02, 1.02], trans: [2.75, 4.35, 5.95]};      // the gable window: posts, sill, header space, mullions, transoms
const DOOR = {x0: 2.0, x1: 2.95, h: 2.15};            // the glazed door out to the deck, inside the window wall
const EYE = 1.62, RADIUS = 0.33;
const SIT = {sofa: 1.17, armchair: 1.2, rocker: 1.15};      // eyes above the floor, seated
const TINT_BACK = new THREE.Color("#ffe3a6");      // the light round the door that leads back
const LOFT_Z = HZ - 2.2, LOFT_Y = 3.0, LOFT_X = 3.9;      // the loft over the back of the room, and how far across it has head room
const STAIR = {x: -3.6, w: 0.9, run: 2.6}; STAIR.z0 = LOFT_Z - STAIR.run;      // the stair climbs toward the back, a step in from the left wall
const FIRE = {z: 1.2, w: 2.7, depth: 0.75, open: [0.55, 1.75], top: 1.3, hearth: 0.42};      // the fireplace on the right-hand wall
const slopeY = x => HE + (HR - HE) * (1 - Math.abs(x) / HX);          // the roof's underside above x
const xMax = y => y <= HE ? HX : HX * (HR - y) / (HR - HE);          // how far a gable log reaches at height y
const GLASS_Z = -HZ + LOG_R - 0.02;                                   // the plane of the glass

const PHONE_SKIP = ["book_encyclopedia_set_01", "potted_plant_02", "wooden_bowl_01", "hatchet", "wicker_basket_01"];      // the small things a phone's budget leaves out (the page's builder counts the same)

/* ---------- the seats (John, 2026-10-11): where a visitor can sit, with a sentence for the page ---------- */
export const SEATS = [
  {id: "sofa", name: "The leather sofa", where: "Facing the fire across the rug, the glass wall and the mountains at your left"},
  {id: "armchair", name: "The armchair by the fire", where: "A bergère at the hearth's side, the fire at your right hand"},
  {id: "rocker", name: "The rocking chair", where: "By the glass, rocking gently, the mountains beside you and the whole room ahead"},
  {id: "loft", name: "The loft railing", where: "Up the stair, standing at the rail, looking down over the room to the glass and the peaks"},
];

/* ---------- time of day, season and weather, from the visitor's own device ---------- */
export function whenNow(d = new Date()){ const h = d.getHours() + d.getMinutes() / 60; return h < 5.5 ? "night" : h < 11 ? "morning" : h < 17 ? "afternoon" : h < 20.25 ? "dusk" : "night"; }
export function seasonNow(d = new Date()){ return ["winter", "winter", "spring", "spring", "spring", "summer", "summer", "summer", "autumn", "autumn", "autumn", "winter"][d.getMonth()]; }
/* the mountains' afternoon showers: in spring and summer, one afternoon or dusk in three (by the day, so it holds all day) */
export function weatherNow(when, season, d = new Date()){
  if (!(season === "spring" || season === "summer") || !(when === "afternoon" || when === "dusk")) return "clear";
  const day = Math.floor((d.getTime() - d.getTimezoneOffset() * 60000) / 86400000);
  return ((Math.imul(day, 2654435761) >>> 0) % 3) === 0 ? "rain" : "clear";
}
/* the light of each hour: where the sun is (a direction from the room toward it; the glass is at -z), its colour and
   strength, the sky's light, how much the surroundings reflect, which lamps are lit, how bright the fire burns, how the
   photograph outside is graded, how strong the shafts through the glass are, and the lens's exposure */
const HOURS = {
  morning:   {sun: [-0.62, 0.36, -1.0], sunCol: "#ffdcb0", sunI: 5.2, hemi: ["#c9dcff", "#6b5040", 1.4], env: 0.9, expo: 1.35, sat: 0.97, lamps: 0, fire: 7, poster: 1.0,
              view: {gain: 1.18, tint: [1.04, 1.0, 0.95]}, shaft: 1.0, haze: 0.75, sky: ["#88b4e8", "#e9f0f8"], wind: 0.35},
  afternoon: {sun: [0.7, 0.9, -1.0], sunCol: "#fff6ea", sunI: 6.2, hemi: ["#dbe8ff", "#7a6050", 3.2], env: 1.25, expo: 1.4, sat: 0.97, lamps: 0, fire: 5, poster: 1.0,      // the sun is behind the fireplace wall then: the sky's own light carries the room, the chimney breast with it
              view: {gain: 1.25, tint: [1, 1, 1]}, shaft: 0.5, haze: 0.7, sky: ["#5d9be0", "#dfeaf6"], wind: 0.45},
  dusk:      {sun: [0.85, 0.11, -1.0], sunCol: "#ff9a4c", sunI: 2.4, hemi: ["#a08cc0", "#4a3222", 0.7], env: 0.5, expo: 0.78, sat: 0.86, lamps: 1, fire: 7, poster: 1.25,
              view: {gain: 1.0, tint: [1.0, 0.86, 0.82]}, shaft: 0.75, haze: 0.4, sky: ["#3a3f7a", "#f0a070"], wind: 0.6},
  night:     {sun: [-0.35, 0.65, -1.0], sunCol: "#8fa6ff", sunI: 0.25, hemi: ["#1c2638", "#1a120a", 0.16], env: 0.2, expo: 0.7, sat: 0.82, lamps: 1, fire: 7.5, poster: 1.5,
              view: {gain: 0.42, tint: [0.55, 0.66, 1.0], night: 1}, shaft: 0, haze: 0, sky: ["#050a18", "#15203c"], wind: 0.7},
};
/* The lens's exposure at dusk and at night is held down (a room lit by one fire and two lamps photographs as pools of light
   in darkness: the far walls and the roof fall to about a third of the lit hearth), its colour is held back a little then
   (every light in the room is warm after dark, and a film's night is cooler than its day), and the fire burns lower than it
   first did, so the pine stays honey-coloured rather than going red. */
/* the season bends the sun lower in winter and higher in summer, and sets the wind */
const SEASONS = {winter: {sunY: 0.62, wind: 1.3, snow: 1}, spring: {sunY: 0.95, wind: 1.1, snow: 0}, summer: {sunY: 1.25, wind: 0.8, snow: 0}, autumn: {sunY: 0.85, wind: 1.15, snow: 0}};
/* the wind: gusts as a sum of slow waves, the same for the sound, the curtains, the flames and the snow (0 calm to 1 a strong gust) */
export function gust(t, level = 1){ const g = 0.5 + 0.5 * Math.sin(t * 0.21) * Math.sin(t * 0.073 + 1.0) + 0.25 * Math.sin(t * 0.47 + 2.1) * Math.sin(t * 0.031); return Math.max(0, Math.min(1, (g - 0.25) * 1.3)) * level; }

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
/* hi: the 2k set (tex2k/) for the logs, the stone and the floor, the surfaces seen closest; everything else, and every
   phone, takes the 1k set (tex/) */
function materials(base, manager, aniso, redraw, hi){
  const loader = new THREE.TextureLoader(manager);
  const M = {};
  /* each material starts as a plain colour and takes its maps together once they have all arrived (one shader rebuild) */
  function pbr(name, o = {}){
    const m = std({color: o.color || "#ffffff", roughness: o.roughness == null ? 1 : o.roughness});
    const rep = o.repeat || [1, 1], want = o.maps || ["diff", "nor", "arm"], got = {}; let left = want.length;
    const folder = (hi && o.hi) ? "tex2k/" : "tex/";
    const done = () => { if (--left) return;
      if (got.diff) m.map = got.diff; if (got.nor) m.normalMap = got.nor; if (got.arm) { m.aoMap = got.arm; if (o.roughMap !== false) { m.roughnessMap = got.arm; m.metalnessMap = got.arm; } } if (got.rough) m.roughnessMap = got.rough;
      m.roughness = m.roughnessMap ? 1 : (o.roughness == null ? 1 : o.roughness); m.normalScale.set(o.normal == null ? 1 : o.normal, o.normal == null ? 1 : o.normal); m.aoMapIntensity = o.ao == null ? 1 : o.ao; m.needsUpdate = true; redraw(); };
    for (const suffix of want) loader.load(`${base}${folder}${name}_${suffix}.jpg`, t => { t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(rep[0], rep[1]); t.anisotropy = aniso; t.channel = 0; if (suffix === "diff") t.colorSpace = THREE.SRGBColorSpace; got[suffix] = t; done(); }, undefined, () => done());
    return m;
  }
  M.logs = pbr("logs", {color: "#cdbda9", repeat: [1, 1], normal: 0.9, roughMap: false, roughness: 0.72, hi: true});      // the uv of every log is scaled to real size; matte, and less orange than the varnished board it was photographed from
  M.floor = pbr("floor", {color: "#6e4b2d", repeat: [W / 2, D / 2], normal: 0.8, hi: true});       // the texture is 2 m across
  M.boards = pbr("boards", {color: "#b89f88", repeat: [1, 1], normal: 0.6, roughMap: false, roughness: 0.8});      // scaled per piece
  M.stone = pbr("stone", {color: "#a9a297", repeat: [1, 1], normal: 1.0, hi: true});                 // scaled per piece (2 m); fieldstone's own albedo, so the breast holds the sky's light in the afternoon, when no sun reaches it
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
  M.steel = std({color: "#26231f", roughness: 0.4, metalness: 0.7});
  M.brass = std({color: "#b8894a", roughness: 0.35, metalness: 0.9});
  M.soot = new THREE.MeshBasicMaterial({color: "#140c08"});      // the inside of the firebox: soot takes no light worth drawing
  M.mortar = std({color: "#9a938a", roughness: 1});
  M.cream = std({color: "#efe6d2", roughness: 0.9});
  M.linen = std({map: linenTexture(), color: "#d8ccb6", roughness: 1, side: THREE.DoubleSide});
  return M;
}

/* ---------- small pictures the room draws for itself ---------- */
/* linen for the curtains: an oatmeal weave with a faint rust stripe */
function linenTexture(){ return canvasTex(512, 512, (c, w, h) => { c.fillStyle = "#d9cdb4"; c.fillRect(0, 0, w, h); const r = rng(21);
  for (let i = 0; i < 9000; i++) { c.fillStyle = `rgba(${r() < 0.5 ? "90,70,50" : "255,250,240"},${0.05 + r() * 0.1})`; c.fillRect(r() * w, r() * h, 1 + r() * 2, 1 + r() * 4); }
  c.fillStyle = "rgba(150,70,40,0.25)"; for (const x of [96, 112, 400, 416]) c.fillRect(x, 0, 6, h);
  c.fillStyle = "rgba(60,50,40,0.08)"; for (let y = 0; y < h; y += 3) c.fillRect(0, y, w, 1); }, true); }
/* a soft puff for smoke */
function smokeTexture(){ return canvasTex(128, 128, (c, w, h) => { c.clearRect(0, 0, w, h); const r = rng(8); for (let i = 0; i < 14; i++) { const x = w / 2 + (r() - 0.5) * 40, y = h / 2 + (r() - 0.5) * 40, rad = 18 + r() * 26;
  const g = c.createRadialGradient(x, y, 0, x, y, rad); g.addColorStop(0, "rgba(255,255,255,0.22)"); g.addColorStop(1, "rgba(255,255,255,0)"); c.fillStyle = g; c.fillRect(0, 0, w, h); } }); }
/* rain running down the glass: streaks and drops as a normal map, scrolled downward */
function rainNormalTexture(){ return canvasTex(512, 1024, (c, w, h) => { c.fillStyle = "rgb(128,128,255)"; c.fillRect(0, 0, w, h); const r = rng(44);
  const bump = (x, y, rx, ry) => { const g = c.createRadialGradient(x, y, 0, x, y, Math.max(rx, ry)); g.addColorStop(0, "rgba(128,128,255,0)"); g.addColorStop(0.55, "rgba(128,128,255,0)"); g.addColorStop(1, "rgba(128,128,255,0)"); c.save(); c.translate(x, y); c.scale(rx / Math.max(rx, ry), ry / Math.max(rx, ry));
    const gl = c.createLinearGradient(-Math.max(rx, ry), 0, Math.max(rx, ry), 0); gl.addColorStop(0, "rgba(60,128,255,0.9)"); gl.addColorStop(0.5, "rgba(128,128,255,0)"); gl.addColorStop(1, "rgba(196,128,255,0.9)"); c.fillStyle = gl; c.beginPath(); c.arc(0, 0, Math.max(rx, ry), 0, 7); c.fill();
    const gv = c.createLinearGradient(0, -Math.max(rx, ry), 0, Math.max(rx, ry)); gv.addColorStop(0, "rgba(128,196,255,0.7)"); gv.addColorStop(0.5, "rgba(128,128,255,0)"); gv.addColorStop(1, "rgba(128,60,255,0.7)"); c.fillStyle = gv; c.beginPath(); c.arc(0, 0, Math.max(rx, ry), 0, 7); c.fill(); c.restore(); };
  for (let i = 0; i < 70; i++) { const x = r() * w, y0 = r() * h, len = 60 + r() * 400; for (let y = y0; y < y0 + len; y += 6) bump(x + Math.sin(y * 0.05 + i) * 2, y % h, 2.2, 4); bump(x, (y0 + len) % h, 4, 5); }
  for (let i = 0; i < 260; i++) bump(r() * w, r() * h, 1.5 + r() * 3, 1.5 + r() * 3.5); }, true); }
/* the clock's hands: dark blued steel */
function clockHands(parent, M){
  const g = new THREE.Group(); parent.add(g);
  const hand = (len, wid, thick, dz) => { const geo = new THREE.BoxGeometry(wid, len, thick); geo.translate(0, len / 2 - 0.006, 0); const m = new THREE.Mesh(geo, M.steel); m.position.z = dz; g.add(m); return m; };
  const hour = hand(0.042, 0.0045, 0.0012, 0), minute = hand(0.062, 0.0035, 0.0012, 0.0018), second = hand(0.066, 0.0012, 0.0008, 0.0034);
  const pin = new THREE.Mesh(new THREE.CylinderGeometry(0.003, 0.003, 0.006, 10), M.brass); pin.rotation.x = Math.PI / 2; pin.position.z = 0.002; g.add(pin);
  return {group: g, set(d){ const s = d.getSeconds() + d.getMilliseconds() / 1000, m = d.getMinutes() + s / 60, h = (d.getHours() % 12) + m / 60;
    hour.rotation.z = -h / 12 * Math.PI * 2; minute.rotation.z = -m / 60 * Math.PI * 2; second.rotation.z = -Math.floor(s) / 60 * Math.PI * 2; }};
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

/* ---------- the fire: flames in a shader on crossed planes, sparks, coals, smoke, and the light that flickers ---------- */
const FLAME_VERT = "varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }";
const FLAME_FRAG = `
uniform float uT; uniform float uGain; uniform float uLean; varying vec2 vUv;
float hash(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float noise(vec2 p){ vec2 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f); return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), f.x), mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), f.x), f.y); }
float fbm(vec2 p){ float v = 0.0, a = 0.5; for (int i = 0; i < 5; i++) { v += a * noise(p); p *= 2.03; a *= 0.5; } return v; }
void main(){
  vec2 uv = vUv;
  float n = fbm(vec2(uv.x * 3.0 + uT * 0.3, uv.y * 3.5 - uT * 2.2));
  float n2 = fbm(vec2(uv.x * 7.0 - uT * 0.5, uv.y * 6.0 - uT * 3.1));
  float x = (uv.x - 0.5) * 2.0 + (n - 0.5) * 0.5 * uv.y + uLean * uv.y * uv.y;
  float width = 1.0 - uv.y * 0.78;
  float body = 1.0 - smoothstep(0.0, 1.0, abs(x) / max(width, 0.04));
  float tall = 1.0 - smoothstep(0.3, 1.0, uv.y + (n - 0.5) * 0.7);
  float a = clamp((body * tall * (0.5 + 0.95 * n + 0.35 * n2) - 0.22) * 1.7, 0.0, 1.0);
  float heat = clamp(a * (1.5 - uv.y * 1.2), 0.0, 1.0);
  vec3 col = mix(vec3(1.0, 0.22, 0.02), vec3(1.0, 0.62, 0.12), heat);
  col = mix(col, vec3(1.0, 0.93, 0.66), pow(heat, 3.0) * (1.0 - uv.y * 0.6));
  gl_FragColor = vec4(col * a * uGain * 2.2, a);
}`;
function fireplaceFire(parent, x, y, z, still){
  const g = new THREE.Group(); g.position.set(x, y, z); parent.add(g);
  const flames = [], r = rng(77);
  /* several tongues of flame, each its own size and place over the logs, each flickering to its own clock */
  const tongues = [[0.62, 0.9, 0, 0, 0, 0], [0.46, 0.7, 0.14, 0.1, 1.0, 2.3], [0.42, 0.62, -0.17, -0.08, 2.1, 4.1], [0.34, 0.5, 0.04, -0.2, 0.5, 6.5], [0.5, 0.78, -0.05, 0.13, 1.6, 8.2], [0.3, 0.42, 0.18, -0.16, 0.8, 3.3]];
  for (const [w, h, dx, dz, ry, off] of tongues) { const mat = new THREE.ShaderMaterial({uniforms: {uT: {value: off}, uGain: {value: 1.1}, uLean: {value: 0}}, vertexShader: FLAME_VERT, fragmentShader: FLAME_FRAG, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide});
    const f = new THREE.Mesh(new THREE.PlaneGeometry(w, h), mat); f.position.set(dx, h / 2 + 0.1, dz); f.rotation.y = ry; f.userData.off = off; f.userData.h = h; g.add(f); flames.push(f); }
  /* sparks: a steady few rising, and a shower when a log settles */
  const n = 90, pos = new Float32Array(n * 3), seeds = [];
  for (let i = 0; i < n; i++) { seeds.push([r(), r(), r(), r()]); pos[i * 3] = (r() - 0.5) * 0.5; pos[i * 3 + 1] = r() * 0.9; pos[i * 3 + 2] = (r() - 0.5) * 0.4; }
  const sparks = new THREE.BufferGeometry(); sparks.setAttribute("position", new THREE.BufferAttribute(pos, 3));
  const points = new THREE.Points(sparks, new THREE.PointsMaterial({map: sparkTexture(), size: 0.035, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, color: "#ffb060"})); g.add(points);
  const coalM = std({color: "#0e0603", emissive: "#ff3000", emissiveIntensity: 0.55, roughness: 1});
  for (let i = 0; i < 11; i++) { const c = new THREE.Mesh(new THREE.DodecahedronGeometry(0.04 + r() * 0.03, 0), coalM); c.position.set((r() - 0.5) * 0.52, 0.0, (r() - 0.5) * 0.38); c.scale.y = 0.5; c.rotation.set(r() * 3, r() * 3, 0); g.add(c); }
  const bed = new THREE.Mesh(new THREE.PlaneGeometry(0.72, 0.52), new THREE.MeshBasicMaterial({map: sparkTexture(), color: "#ff5a14", transparent: true, opacity: 0.55, blending: THREE.AdditiveBlending, depthWrite: false})); bed.rotation.x = -Math.PI / 2; bed.position.y = 0.04; g.add(bed);      // the hot bed under the logs
  /* smoke: soft puffs that rise from the logs up into the throat of the chimney */
  const smokeM = new THREE.SpriteMaterial({map: smokeTexture(), color: "#8a7a6a", transparent: true, opacity: 0.35, depthWrite: false}), puffs = [];
  for (let i = 0; i < 10; i++) { const s = new THREE.Sprite(smokeM.clone()); s.userData.life = r(); s.userData.seed = r(); s.scale.setScalar(0.25); g.add(s); puffs.push(s); }
  let burstAt = -10, lean = 0;
  return {group: g, flames, points, coalM,
    burst(){ burstAt = -1; },
    /* each frame: t the clock, k the flicker (about 0.7 to 1.1), wind the gust (the flames lean and stretch with a draught) */
    tick(t, k, wind = 0){
      if (burstAt === -1) burstAt = t;
      lean += ((wind - 0.3) * 0.5 - lean) * 0.05;
      for (const f of flames) { const u = f.material.uniforms; u.uT.value = t * (0.9 + 0.2 * Math.sin(f.userData.off)) + f.userData.off; u.uGain.value = 0.85 + 0.45 * k; u.uLean.value = lean * 0.4 * Math.cos(f.rotation.y); f.scale.y = (0.9 + 0.2 * Math.sin(t * 5.1 + f.userData.off) * (k - 0.6)) * (1 + 0.25 * wind); f.position.y = f.userData.h / 2 * f.scale.y + 0.1; }
      coalM.emissiveIntensity = 0.7 + 0.8 * k; bed.material.opacity = 0.35 + 0.3 * k;
      const shower = Math.max(0, 1 - (t - burstAt) / 1.6);
      const p = points.geometry.attributes.position; for (let i = 0; i < n; i++) { const s = seeds[i]; let life, x, y, z;
        if (i < 36) { life = ((t * (0.35 + s[0] * 0.5) + s[1]) % 1); x = (s[2] - 0.5) * 0.45 + Math.sin(t * 2 + i) * 0.03 * life + lean * 0.3 * life * life; y = 0.2 + life * 0.95; z = (s[0] - 0.5) * 0.36; }
        else if (shower > 0) { const age = (t - burstAt) * (0.6 + s[0] * 0.8); life = Math.min(1, age / 1.4); x = (s[2] - 0.5) * 0.3 + (s[1] - 0.5) * 1.6 * life; y = 0.15 + age * (1.2 + s[3] * 1.4) - age * age * 1.1; z = (s[0] - 0.5) * 0.3 + (s[3] - 0.5) * 0.4 * life; if (y < 0.05) y = -5; }
        else { x = 0; y = -5; z = 0; }
        p.setXYZ(i, x, y, z); } p.needsUpdate = true;
      points.material.size = 0.03 + 0.012 * shower;
      for (const s of puffs) { const u = ((t * 0.16 * (0.7 + s.userData.seed * 0.6) + s.userData.life) % 1); s.position.set((s.userData.seed - 0.5) * 0.3 + Math.sin(t * 0.7 + s.userData.seed * 9) * 0.06 * u + lean * 0.2 * u, 0.35 + u * 0.75, (s.userData.life - 0.5) * 0.2); s.scale.setScalar(0.18 + u * 0.42); s.material.opacity = 0.28 * Math.sin(u * Math.PI) * (0.6 + 0.4 * k); }
    } };
}

/* ---------- the view: a photograph of the Rockies outside, graded for the hour, greyed when it rains ---------- */
const VIEW_VERT = "varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }";
/* The photograph is shown at the angle a real lens sees (about 65 degrees across), with its horizon at the visitor's
   eye level, on a far wider surface: beyond its sides it mirrors, above its top the sky carries on, below its foot the
   ground darkens. At night the sky parts of the photograph are strewn with stars. In rain a veil of cloud lies over it. */
const VIEW_FRAG = `
uniform sampler2D uMap; uniform float uHas; uniform vec3 uTint; uniform float uGain; uniform vec3 uSkyTop; uniform vec3 uSkyLow; uniform vec2 uScale; uniform float uHz; uniform float uNight; uniform float uRain; uniform float uT; varying vec2 vUv;
float hash(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float vnoise(vec2 p){ vec2 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f); return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), f.x), mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), f.x), f.y); }
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
  if (uRain > 0.0) { float l = dot(c, vec3(0.3, 0.59, 0.11)); vec3 grey = mix(c, vec3(l), 0.4 * uRain) * (1.0 - 0.28 * uRain);
    float cloud = smoothstep(0.55, 1.1, p.y + 0.2 * vnoise(vec2(p.x * 4.0 + uT * 0.01, p.y * 3.0)) - 0.1);
    grey = mix(grey, vec3(0.6, 0.62, 0.66) * (0.7 + 0.3 * vnoise(vec2(p.x * 9.0 - uT * 0.02, p.y * 6.0))), cloud * 0.8 * uRain);
    float mist = smoothstep(0.1, 0.5, p.y) * (1.0 - smoothstep(0.5, 0.9, p.y)); grey = mix(grey, vec3(0.6, 0.62, 0.66), mist * 0.25 * uRain);
    c = grey; }
  gl_FragColor = vec4(mix(sky, c, uHas), 1.0);
}`;
function buildView(scene){
  const PW = 300, PH = 160, DIST = 75, LENS = 95;      // the surface, how far off it stands, and the width the photograph takes on it (about 65 degrees)
  const geo = new THREE.PlaneGeometry(PW, PH);
  const mat = new THREE.ShaderMaterial({uniforms: {uMap: {value: null}, uHas: {value: 0}, uTint: {value: new THREE.Vector3(1, 1, 1)}, uGain: {value: 1}, uSkyTop: {value: new THREE.Color("#5d9be0")}, uSkyLow: {value: new THREE.Color("#dfeaf6")},
    uScale: {value: new THREE.Vector2(PW / LENS, PH / (LENS / 1.5))}, uHz: {value: 0.55}, uNight: {value: 0}, uRain: {value: 0}, uT: {value: 0}}, vertexShader: VIEW_VERT, fragmentShader: VIEW_FRAG, depthWrite: true});
  const m = new THREE.Mesh(geo, mat); m.position.set(0, EYE, -HZ - DIST); scene.add(m);
  return {mesh: m, mat, place(horizon, aspect){ mat.uniforms.uScale.value.set(PW / LENS, PH / (LENS / (aspect || 1.5))); mat.uniforms.uHz.value = horizon; }};
}

/* ---------- weather outside the glass: snow in winter, rain when it rains ---------- */
function weatherOutside(scene){
  const r = rng(13);
  /* snow: soft flakes drifting down between the glass and the deck's rail, and beyond it */
  const NS = 900, sp = new Float32Array(NS * 3), ss = [];
  for (let i = 0; i < NS; i++) { sp[i * 3] = (r() - 0.5) * 16; sp[i * 3 + 1] = r() * 8; sp[i * 3 + 2] = -HZ - 0.3 - r() * 7; ss.push([r(), r()]); }
  const sg = new THREE.BufferGeometry(); sg.setAttribute("position", new THREE.BufferAttribute(sp, 3));
  const snow = new THREE.Points(sg, new THREE.PointsMaterial({map: haloTexture(), color: "#f4f6ff", size: 0.09, transparent: true, opacity: 0.85, depthWrite: false, sizeAttenuation: true})); snow.visible = false; snow.frustumCulled = false; scene.add(snow);
  /* rain: short streaks falling fast */
  const NR = 700, rp = new Float32Array(NR * 6), rs = [];
  for (let i = 0; i < NR; i++) { const x = (r() - 0.5) * 16, y = r() * 8, z = -HZ - 0.3 - r() * 7; rp.set([x, y, z, x + 0.02, y - 0.35, z], i * 6); rs.push([r(), r()]); }
  const rg = new THREE.BufferGeometry(); rg.setAttribute("position", new THREE.BufferAttribute(rp, 3));
  const rain = new THREE.LineSegments(rg, new THREE.LineBasicMaterial({color: "#b8c2cc", transparent: true, opacity: 0.32, depthWrite: false})); rain.visible = false; rain.frustumCulled = false; scene.add(rain);
  return {snow, rain,
    tick(dt, t, wind, snowing, raining){
      snow.visible = snowing; rain.visible = raining;
      if (snowing) { const p = snow.geometry.attributes.position; for (let i = 0; i < NS; i++) { let y = p.getY(i) - dt * (0.45 + ss[i][0] * 0.35); let x = p.getX(i) + dt * (0.25 * wind + Math.sin(t * 0.9 + ss[i][1] * 9) * 0.12); if (y < 0) { y = 8; x = (ss[i][1] - 0.5) * 16; } if (x > 8) x -= 16; p.setXY(i, x, y); } p.needsUpdate = true; }
      if (raining) { const p = rain.geometry.attributes.position; for (let i = 0; i < NR; i++) { const k = i * 2; let y = p.getY(k) - dt * (6 + rs[i][0] * 2.5); let x = p.getX(k) + dt * 0.8 * wind; if (y < 0) { y = 8 + rs[i][1] * 2; x = (rs[i][1] - 0.5) * 16; } p.setXYZ(k, x, y, p.getZ(k)); p.setXYZ(k + 1, x + 0.03 * wind, y - 0.35, p.getZ(k)); } p.needsUpdate = true; }
    } };
}

/* ---------- the room ---------- */
function buildRoom(scene, M, opts, ctx){
  const g = new THREE.Group(); scene.add(g);
  const blocks = ctx.blocks, lights = {lamps: [], posterLights: []};
  /* the floor */
  const floor = mesh(new THREE.PlaneGeometry(W, D), M.floor, 0, 0, 0, g); floor.rotation.x = -Math.PI / 2; floor.castShadow = false;
  /* dark backing in the plane of each wall's log centres: it shows only in the creases between logs, as the shadow there */
  const back = (w, h, x, y, z, ry) => { const m = mesh(new THREE.PlaneGeometry(w, h), M.backing, x, y, z, g, false); m.rotation.y = ry; m.receiveShadow = true; return m; };
  back(D + 0.6, HE + 0.4, -HX, (HE + 0.4) / 2, 0, Math.PI / 2); back(D + 0.6, HE + 0.4, HX, (HE + 0.4) / 2, 0, -Math.PI / 2);
  back(HX - WIN.x1 - 0.12, HR, (WIN.x1 + 0.12 + HX) / 2, HR / 2, -HZ, 0); back(HX - WIN.x1 - 0.12, HR, -(WIN.x1 + 0.12 + HX) / 2, HR / 2, -HZ, 0); back(DOOR.x0 - WIN.x0 + 0.15, WIN.y0 - 0.06, (WIN.x0 - 0.15 + DOOR.x0) / 2, (WIN.y0 - 0.06) / 2, -HZ, 0);
  back(HX - 1.05, HR, (HX - 1.05) / 2 - 1.05 + 0, HR / 2, HZ, Math.PI); back(HX - 2.35, HR, -(HX + 2.35) / 2, HR / 2, HZ, Math.PI); back(1.5, HR - 2.2, -1.7, (HR + 2.2) / 2, HZ, Math.PI);
  /* the log walls: the walls along x and the walls along z interlock, half a course apart, and their ends stand proud of the corners */
  const courses = []; for (let k = 0; k < 40; k++) courses.push(LOG_R + k * COURSE);
  for (const y of courses) { if (y + LOG_R > HE + 0.14) break; logAt(D + 0.6, LOG_R, M.logs, -HX, y + COURSE / 2, 0, "z", g); logAt(D + 0.6, LOG_R, M.logs, HX, y + COURSE / 2, 0, "z", g); }
  const segments = (y, z, gaps) => {      // one course of a gable wall at height y, with openings cut out
    const xm = xMax(y) + (y <= HE ? 0.3 : -0.02); if (xm < 0.3) return;
    let from = -xm; const cuts = gaps.filter(c => y > c[2] && y - LOG_R < c[3]).sort((a, b) => a[0] - b[0]);
    for (const c of cuts) { if (c[0] - from > 0.12) logAt(c[0] - from, LOG_R, M.logs, (from + c[0]) / 2, y, z, "x", g); from = Math.max(from, c[1]); }
    if (xm - from > 0.12) logAt(xm - from, LOG_R, M.logs, (from + xm) / 2, y, z, "x", g);
  };
  const winCut = [WIN.x0 - 0.08, WIN.x1 + 0.08, WIN.y0 - LOG_R, 99], deckCut = [DOOR.x0 - 0.1, DOOR.x1 + 0.1, -1, DOOR.h + 0.12], doorCut = [-2.35, -1.05, -1, 2.2];
  for (const y of courses) { if (y - LOG_R > HR - 0.25) break; segments(y, -HZ, [winCut, deckCut]); segments(y, HZ, [doorCut]); }
  /* a solid wall's worth of shadow just outside each log wall the sun can reach: the logs overlap by only a sliver at each
     course, and the sun's shadow map would otherwise leak a thread of light through every seam. A sheet that draws nothing
     and casts a shadow (the glass and the door stay open to the sun) */
  const shieldM = new THREE.MeshBasicMaterial({colorWrite: false, depthWrite: false, side: THREE.DoubleSide});
  const shield = (w, h, x, y, z, ry = 0) => { const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, 0.04), shieldM); m.position.set(x, y, z); m.rotation.y = ry; m.castShadow = true; g.add(m); };
  for (const s of [-1, 1]) shield(D + 0.6, HE + 0.4, s * (HX + LOG_R + 0.04), (HE + 0.4) / 2, 0, Math.PI / 2);
  for (const s of [-1, 1]) shield(HX + 0.3 - WIN.x1 - 0.1, HE + 0.4, s * (WIN.x1 + 0.1 + HX + 0.3) / 2, (HE + 0.4) / 2, -HZ - LOG_R - 0.04);
  shield(DOOR.x0 - 0.1 - (WIN.x0 - 0.1), WIN.y0 - 0.12, (WIN.x0 - 0.1 + DOOR.x0 - 0.1) / 2, (WIN.y0 - 0.12) / 2, -HZ - LOG_R - 0.04);
  /* the roof: boards on the underside, a ridge log, purlins, rafters of round logs, and two log trusses */
  const a = Math.atan2(HR - HE, HX), L = Math.hypot(HX, HR - HE);
  for (const s of [-1, 1]) { const pg = new THREE.PlaneGeometry(D + 0.6, L), uv = pg.attributes.uv; for (let i = 0; i < uv.count; i++) uv.setXY(i, uv.getX(i) * (D + 0.6) / 1.5, uv.getY(i) * L / 1.5);
    const m = mesh(pg, M.boards, s * HX / 2, (HE + HR) / 2, 0, g); m.castShadow = false; m.lookAt(m.position.clone().add(V3(-s * Math.sin(a), -Math.cos(a), 0))); }
  logAt(D + 0.8, 0.19, M.logs, 0, HR - 0.38, 0, "z", g);
  for (const s of [-1, 1]) logAt(D + 0.8, 0.14, M.logs, s * 2.6, slopeY(2.6) - 0.46, 0, "z", g);
  for (let z = -HZ + 0.25; z < HZ; z += 1.25) for (const s of [-1, 1]) logBetween(V3(s * (HX + 0.3), HE - 0.32, z), V3(s * 0.12, HR - 0.32, z), 0.12, M.logs, g, 12);
  for (const z of [-1.5, 2.3]) { logAt(W + 0.6, 0.17, M.logs, 0, HE - 0.12, z, "x", g); logBetween(V3(0, HE - 0.12, z), V3(0, HR - 0.5, z), 0.14, M.logs, g, 12);
    for (const s of [-1, 1]) logBetween(V3(s * 1.5, HE - 0.05, z), V3(s * 2.6, slopeY(2.6) - 0.6, z), 0.11, M.logs, g, 12); }
  /* the gable window wall: frame, mullions, transoms, sill, the header log, and one sheet of glass shaped to the roof */
  const top = x => slopeY(x) - 0.05, wy0 = WIN.y0, gz = GLASS_Z;
  const post = (x) => box(0.14, top(x) - wy0, 0.2, M.dark, x, (top(x) + wy0) / 2, gz, g);
  post(WIN.x0); post(WIN.x1); for (const x of WIN.mull) box(0.08, top(x) - wy0, 0.12, M.dark, x, (top(x) + wy0) / 2, gz, g);
  for (const y of WIN.trans) { const xr = Math.min(WIN.x1, xMax(y + 0.05) - 0.02); box(2 * xr, 0.08, 0.12, M.dark, 0, y, gz, g); }
  box(DOOR.x0 - 0.05 - (WIN.x0 - 0.25), 0.1, 0.46, M.dark, (WIN.x0 - 0.25 + DOOR.x0 - 0.05) / 2, wy0 - 0.05, -HZ + LOG_R + 0.08, g);      // the sill, up to the door
  box(WIN.x1 + 0.25 - (DOOR.x1 + 0.05), 0.1, 0.46, M.dark, (DOOR.x1 + 0.05 + WIN.x1 + 0.25) / 2, wy0 - 0.05, -HZ + LOG_R + 0.08, g);
  for (const s of [-1, 1]) logBetween(V3(s * (WIN.x1 + 0.1), slopeY(WIN.x1) - WIN.head + 0.12, -HZ + LOG_R), V3(s * 0.02, slopeY(0) - WIN.head + 0.12, -HZ + LOG_R), 0.1, M.logs, g, 10);      // the header, following the roof
  const shape = new THREE.Shape(); shape.moveTo(WIN.x0, 0.02); shape.lineTo(WIN.x1, 0.02); shape.lineTo(WIN.x1, top(WIN.x1)); shape.lineTo(0, top(0)); shape.lineTo(WIN.x0, top(WIN.x0)); shape.closePath();
  const glassM = new THREE.MeshPhysicalMaterial({color: "#ffffff", transparent: true, opacity: 0.09, roughness: 0.03, metalness: 0, envMapIntensity: 1.5, depthWrite: false, side: THREE.DoubleSide});
  const glass = new THREE.Mesh(new THREE.ShapeGeometry(shape), glassM); glass.position.z = gz; g.add(glass);
  /* rain on the glass: a second, wetter sheet that shows only when it rains, its streaks running down */
  const rainN = rainNormalTexture(); rainN.repeat.set(3, 2.2);
  const wetM = new THREE.MeshPhysicalMaterial({color: "#ffffff", transparent: true, opacity: 0.16, roughness: 0.12, metalness: 0, envMapIntensity: 2.2, normalMap: rainN, normalScale: new THREE.Vector2(1.4, 1.4), depthWrite: false, side: THREE.DoubleSide});
  const wet = new THREE.Mesh(glass.geometry, wetM); wet.position.z = gz + 0.004; wet.visible = false; g.add(wet);
  /* the door out to the deck (John, 2026-10-11): a glazed door at the right of the glass wall, in a dark frame, with a brass lever */
  const dg = new THREE.Group(); g.add(dg); const dmx = (DOOR.x0 + DOOR.x1) / 2;
  for (const x of [DOOR.x0, DOOR.x1]) box(0.09, DOOR.h + 0.05, 0.16, M.dark, x, (DOOR.h + 0.05) / 2, gz + 0.02, dg);
  box(DOOR.x1 - DOOR.x0, 0.1, 0.16, M.dark, dmx, DOOR.h, gz + 0.02, dg); box(DOOR.x1 - DOOR.x0, 0.07, 0.12, M.dark, dmx, 1.02, gz + 0.03, dg);
  box(DOOR.x1 - DOOR.x0, 0.36, 0.1, M.dark, dmx, 0.2, gz + 0.03, dg); box(DOOR.x1 - DOOR.x0 + 0.2, 0.05, 0.3, M.dark, dmx, 0.025, -HZ + LOG_R + 0.02, dg);
  const lever = box(0.12, 0.022, 0.022, M.brass, DOOR.x0 + 0.13, 1.0, gz + 0.11, dg); mesh(new THREE.CylinderGeometry(0.014, 0.014, 0.08, 10), M.brass, DOOR.x0 + 0.08, 1.0, gz + 0.08, dg).rotation.x = Math.PI / 2;
  const deckHalo = new THREE.Mesh(new THREE.PlaneGeometry(2.2, 3.2), new THREE.MeshBasicMaterial({map: haloTexture(), color: "#ffe2a8", transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false})); deckHalo.position.set(dmx, 1.1, gz + 0.06); dg.add(deckHalo);
  const deckHit = new THREE.Mesh(new THREE.PlaneGeometry(DOOR.x1 - DOOR.x0, DOOR.h), new THREE.MeshBasicMaterial({transparent: true, opacity: 0, depthWrite: false, side: THREE.DoubleSide})); deckHit.position.set(dmx, DOOR.h / 2, gz + 0.05); dg.add(deckHit);
  const deckDoor = {hit: deckHit, halo: deckHalo, lever, x: dmx, wallZ: -HZ, stand: V3(dmx, EYE, -HZ + 1.45), heat: 0};
  /* the deck outside, with a log railing; snow on it in winter */
  const deck = sizedBox(9.0, 0.08, 2.8, M.deck, 0, -0.06, -HZ - 1.4 - LOG_R, g, 1.5); deck.castShadow = false;
  const deckSnow = mesh(new THREE.PlaneGeometry(9.0, 2.8), std({color: "#eef0f4", roughness: 0.95}), 0, -0.005, -HZ - 1.4 - LOG_R, g, false); deckSnow.rotation.x = -Math.PI / 2; deckSnow.receiveShadow = true; deckSnow.visible = false;
  for (let x = -4.4; x <= 4.41; x += 1.1) logAt(1.05, 0.065, M.logs, x, 0.45, -HZ - 2.75 - LOG_R, "y", g, 10);
  logAt(9.0, 0.06, M.logs, 0, 1.0, -HZ - 2.75 - LOG_R, "x", g, 10); logAt(9.0, 0.045, M.logs, 0, 0.5, -HZ - 2.75 - LOG_R, "x", g, 8);
  for (let x = -4.3; x <= 4.31; x += 0.16) logAt(0.5, 0.022, M.logs, x, 0.75, -HZ - 2.75 - LOG_R, "y", g, 7);
  for (const s of [-1, 1]) { logAt(2.7, 0.06, M.logs, s * 4.5, 1.0, -HZ - 1.4 - LOG_R, "z", g, 10); for (let z = 0.2; z < 2.7; z += 0.16) logAt(0.5, 0.022, M.logs, s * 4.5, 0.75, -HZ - z - LOG_R, "y", g, 7); }
  /* the curtains: linen panels either side of the lower glass, on a brass rod under the first transom, stirring in a draught */
  const curtains = [], curtainU = {uT: {value: 0}, uAmp: {value: 0}};
  mesh(new THREE.CylinderGeometry(0.014, 0.014, WIN.x1 - WIN.x0 - 0.2, 10), M.brass, 0, WIN.trans[0] - 0.05, gz + 0.14, g, false).rotation.z = Math.PI / 2;
  for (const [cx0, cx1] of [[WIN.x0 + 0.12, WIN.x0 + 0.92], [DOOR.x0 - 0.86, DOOR.x0 - 0.06]]) {
    const w = cx1 - cx0, h = WIN.trans[0] - 0.08 - 0.12, geo = new THREE.PlaneGeometry(w, h, 14, 30), pos = geo.attributes.position, uv = geo.attributes.uv;
    for (let i = 0; i < pos.count; i++) { const u = uv.getX(i); pos.setZ(i, 0.045 * Math.sin(u * Math.PI * 2 * 4.5) * (0.7 + 0.3 * (1 - uv.getY(i)))); uv.setXY(i, u * 1.6, uv.getY(i) * 3.2); }      // gathered into folds, the weave at its real size
    geo.computeVertexNormals();
    const cm = M.linen.clone(); cm.onBeforeCompile = sh => { sh.uniforms.uT = curtainU.uT; sh.uniforms.uAmp = curtainU.uAmp;
      sh.vertexShader = "uniform float uT, uAmp;\n" + sh.vertexShader.replace("#include <begin_vertex>", "#include <begin_vertex>\n float fy = 1.0 - uv.y / 3.2; float sw = 0.5 * sin(uT * 1.1 + uv.x * 3.7) + 0.5 * sin(uT * 0.63 + uv.y * 1.3); transformed.z += uAmp * fy * fy * sw * 0.14; transformed.x += uAmp * fy * 0.025 * sin(uT * 0.8 + uv.y);"); };
    const c = mesh(geo, cm, (cx0 + cx1) / 2, 0.12 + h / 2, gz + 0.16, g); c.castShadow = true; curtains.push(c);
  }
  /* the door in the back wall, under the loft */
  const door = sizedBox(1.28, 2.14, 0.07, M.boards, -1.7, 1.07, HZ - LOG_R + 0.02, g, 1.5);      /* flat in its frame */
  box(1.32, 0.12, 0.16, M.dark, -1.7, 2.18, HZ - LOG_R, g); box(0.11, 2.24, 0.16, M.dark, -2.36, 1.12, HZ - LOG_R, g); box(0.11, 2.24, 0.16, M.dark, -1.04, 1.12, HZ - LOG_R, g);
  mesh(new THREE.SphereGeometry(0.035, 12, 8), M.brass, -1.32, 1.0, HZ - LOG_R - 0.06, g);
  for (const yy of [0.6, 1.5]) box(1.0, 0.08, 0.03, M.dark, -1.7, yy, HZ - LOG_R - 0.04, g);
  /* the way back (John, 2026-10-02): when the visitor came here from a page of the site, light shows round this door, and it leads back there */
  const DOOR_X = -1.7, dz = HZ - LOG_R - 0.03, bg = new THREE.Group(); bg.visible = !!opts.back; g.add(bg);
  const seamM = new THREE.MeshBasicMaterial({color: "#ffe3a6"});
  for (const sx of [-0.59, 0.59]) { const m = new THREE.Mesh(new THREE.BoxGeometry(0.045, 2.1, 0.02), seamM); m.position.set(DOOR_X + sx, 1.06, dz); bg.add(m); }
  { const m = new THREE.Mesh(new THREE.BoxGeometry(1.21, 0.045, 0.02), seamM); m.position.set(DOOR_X, 2.1, dz); bg.add(m); const m2 = new THREE.Mesh(new THREE.BoxGeometry(1.21, 0.022, 0.02), seamM); m2.position.set(DOOR_X, 0.012, dz); bg.add(m2); }
  const doorHalo = new THREE.Mesh(new THREE.PlaneGeometry(3.3, 3.9), new THREE.MeshBasicMaterial({map: haloTexture(), color: "#ffd9a0", transparent: true, opacity: 0.3, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide}));
  doorHalo.position.set(DOOR_X, 1.15, dz - 0.09); doorHalo.rotation.y = Math.PI; bg.add(doorHalo);
  const doorLight = new THREE.PointLight("#ffd9a0", 0, 5, 1.8); doorLight.position.set(DOOR_X, 1.4, dz - 0.7); bg.add(doorLight);
  const doorHit = new THREE.Mesh(new THREE.PlaneGeometry(1.45, 2.3), new THREE.MeshBasicMaterial({transparent: true, opacity: 0, depthWrite: false, side: THREE.DoubleSide})); doorHit.position.set(DOOR_X, 1.15, dz - 0.1); bg.add(doorHit);
  const backDoor = {on: !!opts.back, group: bg, hit: doorHit, halo: doorHalo, light: doorLight, seam: seamM, x: DOOR_X, wallZ: HZ, stand: V3(DOOR_X, EYE, HZ - 1.55), heat: 0};
  /* the loft over the back of the room: joists, boards, a header log on two posts, a log railing with an opening for the stair */
  const loftD = HZ - LOFT_Z;
  sizedBox(W, 0.08, loftD, M.boards, 0, LOFT_Y - 0.04, (LOFT_Z + HZ) / 2, g, 1.5);
  logAt(W + 0.3, 0.17, M.logs, 0, LOFT_Y - 0.25, LOFT_Z, "x", g);
  for (let x = -HX + 1.0; x < HX; x += 1.3) logAt(loftD - 0.1, 0.1, M.logs, x, LOFT_Y - 0.16, (LOFT_Z + HZ) / 2 + 0.05, "z", g, 10);
  for (const x of [-3.4, 3.4]) { logAt(LOFT_Y - 0.4, 0.16, M.logs, x, (LOFT_Y - 0.4) / 2, LOFT_Z, "y", g); blocks.push([x - 0.2, x + 0.2, LOFT_Z - 0.2, LOFT_Z + 0.2]); }
  const gap0 = STAIR.x - STAIR.w / 2, gap1 = STAIR.x + STAIR.w / 2;
  for (let x = -HX + 0.45; x < HX; x += 1.3) if (x < gap0 - 0.05 || x > gap1 + 0.05) logAt(1.0, 0.065, M.logs, x, LOFT_Y + 0.5, LOFT_Z, "y", g, 10);
  for (const x of [gap0, gap1]) logAt(1.0, 0.065, M.logs, x, LOFT_Y + 0.5, LOFT_Z, "y", g, 10);
  logAt(gap0 + HX, 0.065, M.logs, (-HX + gap0) / 2, LOFT_Y + 0.98, LOFT_Z, "x", g, 10); logAt(HX - gap1, 0.065, M.logs, (gap1 + HX) / 2, LOFT_Y + 0.98, LOFT_Z, "x", g, 10);
  for (let x = -HX + 0.3; x < HX; x += 0.15) if (x < gap0 - 0.04 || x > gap1 + 0.04) logAt(0.92, 0.024, M.logs, x, LOFT_Y + 0.5, LOFT_Z, "y", g, 7);
  /* the stair: a steep flight of plank treads on log stringers, a rail each side, climbing toward the back to the loft's edge */
  const steps = 11, z0 = STAIR.z0, run = STAIR.run;
  for (let i = 1; i <= steps; i++) sizedBox(STAIR.w, 0.09, 0.3, M.boards, STAIR.x, i * LOFT_Y / (steps + 1), z0 + i * run / steps, g, 1.5);
  for (const s of [-1, 1]) { logBetween(V3(STAIR.x + s * 0.47, 0.05, z0 - 0.1), V3(STAIR.x + s * 0.47, LOFT_Y - 0.1, LOFT_Z), 0.07, M.logs, g, 10);
    for (let i = 0; i <= 3; i++) logAt(1.0, 0.04, M.logs, STAIR.x + s * 0.5, 0.5 + i * LOFT_Y / 4 + 0.4, z0 + 0.3 + i * run / 4, "y", g, 8);
    logBetween(V3(STAIR.x + s * 0.5, 1.0, z0 - 0.05), V3(STAIR.x + s * 0.5, LOFT_Y + 0.95, LOFT_Z), 0.05, M.logs, g, 8); }
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
  for (const z of [fz - 0.3, fz + 0.3]) { box(0.5, 0.04, 0.04, M.iron, ox + 0.3, oy0 + 0.12, z, fb); box(0.04, 0.22, 0.04, M.iron, ox + 0.08, oy0 + 0.11, z, fb); }
  for (let i = 0; i < 3; i++) { const l = logAt(0.62, 0.085, M.bark, ox + 0.32, oy0 + 0.2 + (i === 2 ? 0.15 : 0), fz + (i === 2 ? 0.05 : (i - 1) * 0.22), "z", fb, 10); l.rotation.z = (i - 1) * 0.08; }
  const fire = fireplaceFire(fb, ox + 0.34, oy0 + 0.1, fz, opts.still);
  const fireLight = new THREE.PointLight("#ff9448", 8, 16, 2); fireLight.position.set(ox - 0.3, oy0 + 0.6, fz); g.add(fireLight);      // a wood fire's own colour, about 1,900 kelvin, no redder
  if (!opts.lite) { fireLight.castShadow = true; fireLight.shadow.mapSize.set(512, 512); fireLight.shadow.bias = -0.004; fireLight.shadow.camera.near = 0.2; fireLight.shadow.camera.far = 14; }
  const hearthGlow = new THREE.PointLight("#ff9a50", 0, 7, 2); hearthGlow.position.set(ox - 0.9, 0.5, fz); g.add(hearthGlow);      // the fire's light off the hearth stone, thrown back into the room
  logAt(FIRE.w + 0.3, 0.13, M.logs, ox - 0.1, 1.68, fz, "z", g);      // the mantel
  for (const z of [fz - 1.0, fz + 1.0]) logBetween(V3(ox + 0.1, 1.3, z), V3(ox - 0.14, 1.56, z), 0.07, M.logs, g, 10);
  blocks.push([ox - 0.7, HX, fz - FIRE.w / 2 - 0.3, fz + FIRE.w / 2 + 0.3]);
  /* firewood stacked along the wall past the hearth, and a few things on the mantel */
  const wr = rng(5); for (let row = 0; row < 4; row++) for (let i = 0; i < 5 - (row % 2); i++) { const l = logAt(0.46 + wr() * 0.06, 0.07 + wr() * 0.015, M.bark, fx - 0.38 + (wr() - 0.5) * 0.04, 0.075 + row * 0.135, fz + FIRE.w / 2 + 0.95 + i * 0.155 + (row % 2) * 0.08, "x", g, 10); l.rotation.y = (wr() - 0.5) * 0.08; }
  blocks.push([fx - 0.8, HX, fz + FIRE.w / 2 + 0.7, fz + FIRE.w / 2 + 1.9]);
  const MANTEL_Y = 1.68 + 0.13;
  const candle = mesh(new THREE.CylinderGeometry(0.022, 0.025, 0.2, 12), M.cream, ox - 0.1, MANTEL_Y + 0.1, fz - 1.05, g); mesh(new THREE.CylinderGeometry(0.05, 0.035, 0.03, 16), M.brass, ox - 0.1, MANTEL_Y + 0.015, fz - 1.05, g);
  const flameM = std({color: "#ffd080", emissive: "#ffb040", emissiveIntensity: 0}); const candleFlame = mesh(new THREE.SphereGeometry(0.012, 8, 8), flameM, ox - 0.1, MANTEL_Y + 0.215, fz - 1.05, g, false); candleFlame.scale.y = 1.8;
  /* the rug, with its fringe, in front of the fire */
  const RUG = {x: 2.4, z: fz - 0.1, w: 3.8, d: 2.8};
  const rugTop = std({color: "#7a1d18", roughness: 1}), rugSide = std({color: "#5a1612", roughness: 1});
  const rug = new THREE.Mesh(new THREE.BoxGeometry(RUG.w, 0.018, RUG.d), [rugSide, rugSide, rugTop, rugSide, rugSide, rugSide]); rug.position.set(RUG.x, 0.009, RUG.z); rug.receiveShadow = true; g.add(rug);
  M.onRug = () => { if (!M.rugBump.diff) return; const c = rugCanvas(M.rugBump.diff.image); const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 8; rugTop.map = t; rugTop.color.set("#d6cac4");
    if (M.rugBump.nor) { rugTop.normalMap = M.rugBump.nor; rugTop.normalScale.set(0.9, 0.9); } if (M.rugBump.rough) rugTop.roughnessMap = M.rugBump.rough; rugTop.needsUpdate = true; ctx.redraw(); };
  if (M.rugBump.diff) M.onRug();
  const fringeT = canvasTex(256, 64, (c, w, h) => { c.clearRect(0, 0, w, h); for (let i = 0; i < w; i += 3) { c.fillStyle = `rgba(236,226,206,${0.6 + Math.random() * 0.4})`; c.fillRect(i, 0, 1.4, h * (0.75 + Math.random() * 0.25)); } });
  for (const s of [-1, 1]) { const f = new THREE.Mesh(new THREE.PlaneGeometry(0.09, RUG.d - 0.1), new THREE.MeshStandardMaterial({map: fringeT, transparent: true, alphaTest: 0.3, roughness: 1, side: THREE.DoubleSide})); f.rotation.x = -Math.PI / 2; f.rotation.z = s > 0 ? -Math.PI / 2 : Math.PI / 2; f.position.set(RUG.x + s * (RUG.w / 2 + 0.045), 0.004, RUG.z); f.receiveShadow = true; g.add(f); }
  /* the two posters, on the log wall either side of the glass: paper that needs no light, a frame, a brass picture light, a halo */
  const halo = haloTexture();
  const posters = (opts.posters || []).slice(0, 2).map((p, i) => { const pg = new THREE.Group(), x = (i ? 1 : -1) * (WIN.x1 + 0.7), pw = 1.12, ph = 1.68, tint = p.look === "record" ? "#ffd27a" : "#9cc4ff";
    const paper = new THREE.Mesh(new THREE.PlaneGeometry(pw, ph), new THREE.MeshBasicMaterial({map: posterTexture(p)})); paper.position.z = 0.045; pg.add(paper);
    const fr = std({color: "#2e1d10", roughness: 0.5});
    box(pw + 0.12, 0.06, 0.05, fr, 0, ph / 2 + 0.03, 0.03, pg); box(pw + 0.12, 0.06, 0.05, fr, 0, -ph / 2 - 0.03, 0.03, pg); box(0.06, ph, 0.05, fr, -pw / 2 - 0.03, 0, 0.03, pg); box(0.06, ph, 0.05, fr, pw / 2 + 0.03, 0, 0.03, pg);
    box(pw + 0.04, ph + 0.04, 0.02, std({color: "#111", roughness: 0.9}), 0, 0, 0.02, pg);
    const glow = new THREE.Mesh(new THREE.PlaneGeometry(pw * 2.4, ph * 1.9), new THREE.MeshBasicMaterial({map: halo, color: tint, transparent: true, opacity: 0.35, blending: THREE.AdditiveBlending, depthWrite: false})); glow.position.z = 0.012; pg.add(glow);
    box(0.42, 0.045, 0.1, M.brass, 0, ph / 2 + 0.26, 0.2, pg); box(0.02, 0.02, 0.2, M.brass, 0, ph / 2 + 0.27, 0.1, pg);
    const tube = mesh(new THREE.CylinderGeometry(0.012, 0.012, 0.36, 10), std({color: "#fff2d0", emissive: "#ffe0a0", emissiveIntensity: 2.5, roughness: 0.4}), 0, ph / 2 + 0.225, 0.2, pg, false); tube.rotation.z = Math.PI / 2;
    const spot = new THREE.SpotLight(tint, 0, 5, 0.62, 0.7, 1.6); spot.position.set(0, ph / 2 + 0.22, 0.24); spot.target.position.set(0, -0.2, 0.05); pg.add(spot); pg.add(spot.target);
    const light = new THREE.PointLight(tint, 0, 4, 1.8); light.position.set(0, 0.1, 0.5); pg.add(light);
    pg.position.set(x, 1.72, -HZ + LOG_R + 0.012); g.add(pg); lights.posterLights.push(spot, light);
    return {group: pg, paper, glow, light, spot, tube, url: p.url, x, wallZ: -HZ, stand: V3(x * 0.84, EYE, -HZ + 2.0), heat: 0}; });
  /* lamps: a tall side table's worth of warm light at each end of the sofa (the tables are models; the lamps are built here) */
  const lamp = (x, y, z) => { const lg = new THREE.Group(); lg.position.set(x, y, z); g.add(lg);
    mesh(new THREE.CylinderGeometry(0.075, 0.1, 0.05, 20), M.iron, 0, 0.025, 0, lg); mesh(new THREE.CylinderGeometry(0.035, 0.05, 0.3, 14), std({color: "#2a1a10", roughness: 0.5}), 0, 0.2, 0, lg); mesh(new THREE.CylinderGeometry(0.012, 0.012, 0.22, 8), M.brass, 0, 0.46, 0, lg);
    const shadeM = std({color: "#e9dcc0", roughness: 0.95, side: THREE.DoubleSide, emissive: "#ffd9a0", emissiveIntensity: 0}); mesh(new THREE.CylinderGeometry(0.12, 0.19, 0.27, 28, 1, true), shadeM, 0, 0.6, 0, lg, false);
    const bulbM = std({color: "#fff8e8", emissive: "#fff0c0", emissiveIntensity: 0}); mesh(new THREE.SphereGeometry(0.03, 12, 10), bulbM, 0, 0.58, 0, lg, false);
    const pl = new THREE.PointLight("#ffd9a0", 0, 9, 2); pl.position.set(0, 0.62, 0); lg.add(pl); lights.lamps.push({pl, shadeM, bulbM}); return lg; };
  return {group: g, floor, glassM, wet, rainN, fire, fireLight, hearthGlow, posters, door: backDoor, deckDoor, lamp, lights, candleFlame: flameM, curtains, curtainU, deckSnow, RUG, fz, ox, MANTEL_Y};
}

/* ---------- the lens: everything is drawn into a high-range picture with depth, and the screen gets it through this ---------- */
/* As the reading room and the polling place do (John, 2026-10-11, "real lens behaviour"): a soft bloom off the fire, the
   lamps and the glass; depth of field, the focus racking toward what the eye is on; the shafts of daylight through the
   glass, each sample along the eye's ray asking where the sun's ray that reaches it came through the glass (inside the
   frame, clear of the posts, mullions and transoms, and under the header), summed as an exact line integral through the
   lit air and cut off where the room's depth says the air ends; a filmic tone curve; a quiet grade (blacks lifted a touch,
   the midtones warm); the lens's own fall-off toward the edges and the colours focusing a hair apart there; a very fine
   grain that changes every frame. A lean device skips the depth of field and the multisampling and takes fewer samples. */
const FS_VERT = "varying vec2 vUv; void main(){ vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }";
const NOISE_GLSL = `
  float hash12(vec2 p){ vec3 p3 = fract(vec3(p.xyx) * 0.1031); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.x + p3.y) * p3.z); }
  float vnoise(vec2 p){ vec2 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash12(i), hash12(i + vec2(1.0, 0.0)), f.x), mix(hash12(i + vec2(0.0, 1.0)), hash12(i + vec2(1.0, 1.0)), f.x), f.y); }`;
/* is the air at P lit by the sun through the glass? The sun's ray reaching P entered the glass plane at Q = P - L k. */
const SHAFT_GLSL = `
  uniform vec3 uSunL; uniform vec4 uWin; uniform vec2 uTop; uniform vec3 uDoorW; uniform float uShaft, uHaze, uTime;
  float glassLit(vec3 P, out float k){
    k = (P.z - uWin.w) / uSunL.z; if (k < 0.0) return 0.0;
    vec3 Q = P - uSunL * k;
    float top = uTop.x - uTop.y * abs(Q.x) - 0.5;
    float inWin = step(uWin.x, Q.x) * step(Q.x, uWin.y) * step(uWin.z, Q.y) * step(Q.y, top);
    float inDoor = step(uDoorW.x, Q.x) * step(Q.x, uDoorW.y) * step(0.08, Q.y) * step(Q.y, uDoorW.z);
    float lit = max(inWin, inDoor);
    float mx = min(abs(Q.x - 1.02), abs(Q.x + 1.02)); lit *= 1.0 - 0.9 * (1.0 - smoothstep(0.035, 0.06, mx));
    float my = min(min(abs(Q.y - 2.75), abs(Q.y - 4.35)), abs(Q.y - 5.95)); lit *= 1.0 - 0.9 * (1.0 - smoothstep(0.035, 0.06, my));
    lit *= 1.0 - 0.9 * (1.0 - smoothstep(0.03, 0.055, abs(Q.x - uDoorW.x))) * step(Q.y, uDoorW.z);
    return lit;
  }`;
class Lens {
  constructor(renderer, lean, opts = {}){
    this.r = renderer; this.lean = lean; this.dof = !lean && opts.dof !== false;
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute([-1, -1, 0, 3, -1, 0, -1, 3, 0], 3));
    g.setAttribute("uv", new THREE.Float32BufferAttribute([0, 0, 2, 0, 0, 2], 2));
    this.quad = new THREE.Mesh(g, null); this.quad.frustumCulled = false;
    this.qs = new THREE.Scene(); this.qs.add(this.quad); this.qc = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
    const caps = renderer.capabilities, ext = renderer.extensions;
    this.hdr = !!(ext.has("EXT_color_buffer_float") || ext.has("EXT_color_buffer_half_float"));
    this.type = this.hdr ? THREE.HalfFloatType : THREE.UnsignedByteType;
    this.samples = lean ? 0 : Math.min(4, caps.maxSamples || 0);
    const mat = (frag, uniforms, defines) => new THREE.ShaderMaterial({uniforms, vertexShader: FS_VERT, fragmentShader: frag, defines: defines || {}, depthTest: false, depthWrite: false});
    const T = "uniform sampler2D tex; uniform vec2 texel; varying vec2 vUv;";
    this.mBright = mat(`${T} uniform float thr, knee;
      void main(){ vec3 c = 0.25 * (texture2D(tex, vUv + texel * vec2(-0.5, -0.5)).rgb + texture2D(tex, vUv + texel * vec2(0.5, -0.5)).rgb + texture2D(tex, vUv + texel * vec2(-0.5, 0.5)).rgb + texture2D(tex, vUv + texel * vec2(0.5, 0.5)).rgb);
        float l = dot(c, vec3(0.2126, 0.7152, 0.0722)); float s = clamp(l - thr + knee, 0.0, 2.0 * knee); s = s * s / (4.0 * knee + 1e-4);
        float w = max(l - thr, s) / max(l, 1e-4); gl_FragColor = vec4(c * w, 1.0); }`,
      {tex: {value: null}, texel: {value: new THREE.Vector2()}, thr: {value: 1.0}, knee: {value: 0.25}});
    this.mDown = mat(`${T} void main(){ vec2 h = texel * 0.5;
        vec3 c = texture2D(tex, vUv).rgb * 4.0 + texture2D(tex, vUv - h).rgb + texture2D(tex, vUv + h).rgb + texture2D(tex, vUv + vec2(h.x, -h.y)).rgb + texture2D(tex, vUv - vec2(h.x, -h.y)).rgb;
        gl_FragColor = vec4(c / 8.0, 1.0); }`, {tex: {value: null}, texel: {value: new THREE.Vector2()}});
    this.mUp = mat(`${T} uniform sampler2D add; void main(){ vec2 h = texel;
        vec3 c = texture2D(tex, vUv + vec2(-h.x * 2.0, 0.0)).rgb + texture2D(tex, vUv + vec2(-h.x, h.y)).rgb * 2.0 + texture2D(tex, vUv + vec2(0.0, h.y * 2.0)).rgb + texture2D(tex, vUv + vec2(h.x, h.y)).rgb * 2.0
          + texture2D(tex, vUv + vec2(h.x * 2.0, 0.0)).rgb + texture2D(tex, vUv + vec2(h.x, -h.y)).rgb * 2.0 + texture2D(tex, vUv + vec2(0.0, -h.y * 2.0)).rgb + texture2D(tex, vUv + vec2(-h.x, -h.y)).rgb * 2.0;
        gl_FragColor = vec4(c / 12.0 + texture2D(add, vUv).rgb, 1.0); }`, {tex: {value: null}, add: {value: null}, texel: {value: new THREE.Vector2()}});
    /* depth of field: a gather along one axis, its reach the circle of confusion at this pixel, each tap counting only as
       far as its own circle reaches (so a sharp thing never smears over a soft one) */
    this.mDof = mat(`${T} uniform sampler2D depth; uniform vec2 dir; uniform float near, far, focus, aper, maxC;
      float lin(float d){ float z = d * 2.0 - 1.0; return 2.0 * near * far / (far + near - z * (far - near)); }
      float coc(float z){ return clamp(aper * abs(z - focus) / max(z, 0.02), 0.0, 1.0) * maxC; }
      void main(){ float c0 = coc(lin(texture2D(depth, vUv).x)); vec3 acc = vec3(0.0); float ws = 0.0;
        if (c0 < 0.7) { gl_FragColor = vec4(texture2D(tex, vUv).rgb, 1.0); return; }
        for (int i = -7; i <= 7; i++) { float fi = float(i); float dist = abs(fi) * c0 / 7.0; vec2 uv = vUv + dir * fi * c0 / 7.0;
          float ct = coc(lin(texture2D(depth, uv).x)); float w = exp(-fi * fi / 24.0) * (i == 0 ? 1.0 : clamp(ct / max(dist, 1e-3), 0.0, 1.0));
          acc += texture2D(tex, uv).rgb * w; ws += w; }
        gl_FragColor = vec4(acc / ws, 1.0); }`,
      {tex: {value: null}, texel: {value: new THREE.Vector2()}, depth: {value: null}, dir: {value: new THREE.Vector2()}, near: {value: 0.03}, far: {value: 200}, focus: {value: 8}, aper: {value: 0}, maxC: {value: 10}});
    this.mFinal = mat(`${T} uniform sampler2D bloom, depth; uniform float expo, bloomK, grain, vig, ca, veilA, lift, warm, sat, frame, near, far;
      uniform vec3 veil, camPos; uniform mat4 invProj, camWorld;
      ${NOISE_GLSL}${SHAFT_GLSL}
      vec3 aces(vec3 x){ return clamp((x * (2.51 * x + 0.03)) / (x * (2.43 * x + 0.59) + 0.14), 0.0, 1.0); }
      void main(){
        vec2 q = vUv - 0.5; float r2 = dot(q, q); vec2 off = q * ca * (0.4 + r2);
        vec3 col = vec3(texture2D(tex, vUv + off).r, texture2D(tex, vUv).g, texture2D(tex, vUv - off).b);
        if (uShaft > 0.0) {
          float d = texture2D(depth, vUv).x;
          vec4 v = invProj * vec4(vUv * 2.0 - 1.0, d * 2.0 - 1.0, 1.0); v /= v.w; vec3 P = (camWorld * v).xyz;
          vec3 ray = P - camPos; float tS = min(length(ray), 30.0); vec3 rd = ray / max(length(ray), 1e-4);
          float jit = hash12(gl_FragCoord.xy + vec2(frame * 3.1, frame * 7.7)); float dt = tS / float(SHAFT_N); float acc = 0.0;
          for (int i = 0; i < SHAFT_N; i++) { float t = (float(i) + jit) * dt; vec3 S = camPos + rd * t; float k;
            float lit = glassLit(S, k); if (lit <= 0.0) continue;
            float wisp = 0.4 + 0.6 * vnoise(vec2(S.x * 0.7 + S.y * 0.5 + uTime * 0.03, S.z * 0.6 - uTime * 0.02 + k * 0.35));
            acc += lit * exp(-k * 0.3) * wisp * dt; }
          col += vec3(1.0, 0.92, 0.78) * acc * 0.085 * uShaft * uHaze;
        }
        col += texture2D(bloom, vUv).rgb * bloomK;
        col *= expo;
        col = aces(col);
        float l = dot(col, vec3(0.2126, 0.7152, 0.0722));
        col = mix(vec3(l), col, sat);
        col *= mix(vec3(1.0), vec3(1.04, 1.0, 0.95), warm * (1.0 - abs(l - 0.5) * 1.4));
        col = col * (1.0 - lift) + lift * vec3(0.98, 0.95, 0.9);
        col *= 1.0 - vig * smoothstep(0.12, 0.95, r2 * 2.0);
        float gn = hash12(floor(gl_FragCoord.xy / 1.5) + vec2(frame * 7.13, frame * 3.71)) - 0.5;
        col += gn * grain * (0.55 - 0.4 * l);
        col = mix(col, veil, veilA);
        gl_FragColor = vec4(col, 1.0);
        #include <colorspace_fragment>
      }`,
      {tex: {value: null}, texel: {value: new THREE.Vector2()}, bloom: {value: null}, depth: {value: null}, expo: {value: 1.0}, bloomK: {value: 0.22}, grain: {value: 0.024}, vig: {value: 0.3}, ca: {value: 0.0025},
       veilA: {value: 0}, veil: {value: new THREE.Color(0, 0, 0)}, lift: {value: 0.016}, warm: {value: 0.3}, sat: {value: 0.97}, frame: {value: 0}, near: {value: 0.03}, far: {value: 200},
       camPos: {value: V3()}, invProj: {value: new THREE.Matrix4()}, camWorld: {value: new THREE.Matrix4()},
       uSunL: {value: V3(0, -0.5, 1)}, uWin: {value: new THREE.Vector4(WIN.x0, WIN.x1, WIN.y0, GLASS_Z)}, uTop: {value: new THREE.Vector2(HR - 0.05, (HR - HE) / HX)}, uDoorW: {value: V3(DOOR.x0, DOOR.x1, DOOR.h)},
       uShaft: {value: 0}, uHaze: {value: 1}, uTime: {value: 0}}, {SHAFT_N: lean ? 10 : 22});
    this.rts = null; this.w = this.h = 0; this.frame = 0;
  }
  size(w, h){
    if (this.rts && this.w === w && this.h === h) return;
    this.w = w; this.h = h;
    if (this.rts) for (const k in this.rts) this.rts[k].dispose();
    const mk = (sw, sh, o = {}) => new THREE.WebGLRenderTarget(Math.max(1, Math.round(sw)), Math.max(1, Math.round(sh)), Object.assign({type: this.type, minFilter: THREE.LinearFilter, magFilter: THREE.LinearFilter, depthBuffer: false, generateMipmaps: false}, o));
    const depth = new THREE.DepthTexture(w, h, THREE.UnsignedIntType);
    this.rts = {scene: mk(w, h, {depthBuffer: true, depthTexture: depth, samples: this.samples}),
                b1: mk(w / 2, h / 2), b2: mk(w / 4, h / 4), b3: mk(w / 8, h / 8), b4: mk(w / 16, h / 16), u3: mk(w / 8, h / 8), u2: mk(w / 4, h / 4), u1: mk(w / 2, h / 2)};
    if (this.dof) { this.rts.d1 = mk(w, h); this.rts.d2 = mk(w, h); }
  }
  pass(m, from, to, add){
    m.uniforms.tex.value = from.texture; m.uniforms.texel.value.set(1 / from.width, 1 / from.height);
    if (add !== undefined) m.uniforms.add.value = add ? add.texture : null;
    this.quad.material = m; this.r.setRenderTarget(to); this.r.render(this.qs, this.qc);
  }
  /* draw: scene and camera into the lens, then to the canvas. P: {focus, aper, expo, time, shaft, haze, sunL, veil, veilA} */
  render(scene, cam, P = {}){
    const R = this.rts, r = this.r;
    r.setRenderTarget(R.scene); r.render(scene, cam);
    r.setRenderTarget(null);
    this.pass(this.mBright, R.scene, R.b1); this.pass(this.mDown, R.b1, R.b2); this.pass(this.mDown, R.b2, R.b3); this.pass(this.mDown, R.b3, R.b4);
    this.pass(this.mUp, R.b4, R.u3, R.b3); this.pass(this.mUp, R.u3, R.u2, R.b2); this.pass(this.mUp, R.u2, R.u1, R.b1);
    let src = R.scene;
    if (this.dof && (P.aper || 0) > 0.001) {
      const u = this.mDof.uniforms; u.depth.value = R.scene.depthTexture; u.near.value = cam.near; u.far.value = cam.far; u.focus.value = P.focus || 1; u.aper.value = P.aper; u.maxC.value = Math.max(3, this.w / 110);
      u.dir.value.set(1 / this.w, 0); this.pass(this.mDof, R.scene, R.d1);
      u.dir.value.set(0, 1 / this.h); this.pass(this.mDof, R.d1, R.d2);
      src = R.d2;
    }
    const f = this.mFinal.uniforms;
    f.bloom.value = R.u1.texture; f.depth.value = R.scene.depthTexture; f.near.value = cam.near; f.far.value = cam.far;
    f.expo.value = P.expo ?? 1; f.veilA.value = P.veilA || 0; if (P.veil) f.veil.value.copy(P.veil);
    f.frame.value = (this.frame = (this.frame + 1) % 1000); f.uTime.value = P.time || 0;
    f.camPos.value.copy(cam.position); f.invProj.value.copy(cam.projectionMatrixInverse); f.camWorld.value.copy(cam.matrixWorld);
    f.grain.value = P.grain ?? (this.lean ? 0.018 : 0.024); f.uShaft.value = P.shaft || 0; f.uHaze.value = P.haze ?? 1; if (P.sunL) f.uSunL.value.copy(P.sunL);
    f.bloomK.value = P.bloomK ?? 0.22; f.sat.value = P.sat ?? 0.97;
    this.pass(this.mFinal, src, null);
  }
  dispose(){ if (this.rts) for (const k in this.rts) this.rts[k].dispose(); for (const m of [this.mBright, this.mDown, this.mUp, this.mDof, this.mFinal]) m.dispose(); this.quad.geometry.dispose(); }
}

/* ---------- the dust: motes in the air, brightest where a shaft crosses them ---------- */
/* Seeded inside the shafts (a point on the glass, carried along the sun's ray into the room) and a few everywhere; each
   drifts on its own slow path. Lit by the same test as the lens. Re-seeded when the sun moves. */
function dustPoints(lean, U){
  const N = lean ? 500 : 1800, pos = new Float32Array(N * 3), rnd = new Float32Array(N * 3), R = rng(31);
  for (let i = 0; i < N; i++) rnd.set([R(), R(), R()], i * 3);
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3)); g.setAttribute("aRnd", new THREE.Float32BufferAttribute(rnd, 3));
  const m = new THREE.ShaderMaterial({
    uniforms: {uTime: U.uTime, uSize: {value: lean ? 60 : 92}, uDpr: {value: 1}, uSunL: U.uSunL, uWin: U.uWin, uTop: U.uTop, uDoorW: U.uDoorW, uShaft: U.uShaft, uHaze: U.uHaze, uWind: {value: 0}},
    vertexShader: `attribute vec3 aRnd; uniform float uSize, uDpr, uWind; varying float vI;
      ${SHAFT_GLSL}
      void main(){
        float t = uTime * (0.6 + aRnd.z);
        vec3 p = position + vec3(sin(t * 0.21 + aRnd.x * 6.283) * 0.25 + uWind * 0.1, sin(t * 0.17 + aRnd.y * 6.283) * 0.12 - mod(uTime * 0.014 * (0.5 + aRnd.x), 1.2), cos(t * 0.19 + aRnd.z * 6.283) * 0.25);
        float k; float lit = 0.002 + glassLit(p, k) * exp(-k * 0.12) * 0.55 * uShaft * uHaze;      // a mote shows only where a shaft crosses it
        vec4 mv = modelViewMatrix * vec4(p, 1.0); float dist = max(0.3, -mv.z);
        gl_PointSize = clamp(uSize * uDpr / dist, 1.2 * uDpr, 6.0 * uDpr);
        vI = lit * (0.5 + 0.5 * sin(t * 1.3 + aRnd.y * 9.0)) * clamp(2.2 / dist, 0.15, 1.0);
        gl_Position = projectionMatrix * mv;
      }`,
    fragmentShader: `varying float vI; void main(){ vec2 q = gl_PointCoord - 0.5; float a = smoothstep(0.5, 0.1, length(q)); gl_FragColor = vec4(vec3(1.0, 0.94, 0.82) * vI * a, 1.0); }`,
    transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, depthTest: true});
  const pts = new THREE.Points(g, m); pts.frustumCulled = false; pts.renderOrder = 5;
  /* where the motes start, for a sun direction L (the way the light travels) */
  pts.seed = (L) => { const p = g.attributes.position, R2 = rng(57);
    for (let i = 0; i < N; i++) { let x, y, z;
      if (L && L.z > 0.2 && R2() < 0.78) { const qx = WIN.x0 + R2() * (WIN.x1 - WIN.x0), qy = WIN.y0 + R2() * (slopeY(qx) - 0.6 - WIN.y0), kmax = Math.min(14, qy / Math.max(0.05, -L.y), (HZ - GLASS_Z - 0.3) / L.z), k = R2() * kmax;
        x = qx + L.x * k; y = qy + L.y * k; z = GLASS_Z + L.z * k; if (Math.abs(x) > HX - 0.3) { x = (R2() - 0.5) * 9; } }
      else { x = (R2() - 0.5) * 9.6; y = 0.2 + Math.pow(R2(), 1.4) * 5.5; z = (R2() - 0.5) * 8.2; }
      p.setXYZ(i, x, y, z); } p.needsUpdate = true; };
  return pts;
}

/* ---------- the sound of the room: off until the visitor turns it on, made here from no recording ---------- */
/* Each sound sits where its thing is (a panner at the hearth, the mantel, the glass, the chimney, the roof), so turning
   the head turns the sound. The fire: a low roar from brown noise, a hiss, and crackles scheduled a few a second with a
   louder pop now and then; a log settling: a thud and a shower of crackles (the scene throws sparks with it). The clock
   on the mantel: a tick and a tock each second, on the device's own clock. The wind: pink noise through a swept band at
   the glass, rising with the gusts, and a low rush in the chimney. Rain, when it rains: a bed of fine noise on the roof
   with drips. The visitor's own steps on boards, rug or stair; the leather when they sit; the rocker's creak. */
class CabinSound {
  constructor(points){ this.P = points; this.ctx = null; this.on = false; this.dead = false; this.timers = {crackle: 0, pop: 0, settle: 0, tick: 0, drip: 0}; this.R = rng(4242); this.level = {wind: 0.5, rain: 0, fire: 1}; this.onSettle = null; this.side = false; }
  mk(){
    const AC = window.AudioContext || window.webkitAudioContext; if (!AC) return false;
    const c = this.ctx = new AC(), sr = c.sampleRate, R = this.R;
    this.master = c.createGain(); this.master.gain.value = 0; this.master.connect(c.destination);
    /* the room's own echo: a wooden room, warm and short, a few early slaps off the logs */
    const L = Math.floor(sr * 1.4), ir = c.createBuffer(2, L, sr);
    for (let ch = 0; ch < 2; ch++) { const d = ir.getChannelData(ch), r2 = rng(ch + 9); let lp = 0;
      for (let i = 0; i < L; i++) { const t = i / sr, w = r2() * 2 - 1; lp += (w - lp) * (0.5 - 0.35 * Math.min(1, t)); d[i] = lp * Math.exp(-t * 4.2) * (t < 0.008 ? 0 : 1) * 0.6; }
      for (const [at, gn] of [[0.014, 0.5], [0.027, 0.35], [0.041, 0.3], [0.066, 0.2]]) { const i = Math.floor((at + ch * 0.002) * sr); if (i < L) d[i] += gn * (r2() > 0.5 ? 1 : -1); } }
    this.verb = c.createConvolver(); this.verb.buffer = ir; this.verbIn = c.createGain(); this.verbIn.gain.value = 0.32; this.verbIn.connect(this.verb); this.verb.connect(this.master);
    /* noise to build on: white, pink and brown */
    const N = sr * 4, mkb = f => { const b = c.createBuffer(1, N, sr), d = b.getChannelData(0); f(d); return b; };
    this.white = mkb(d => { for (let i = 0; i < N; i++) d[i] = R() * 2 - 1; });
    this.pink = mkb(d => { let b0 = 0, b1 = 0, b2 = 0; for (let i = 0; i < N; i++) { const w = R() * 2 - 1; b0 = 0.99765 * b0 + w * 0.099; b1 = 0.963 * b1 + w * 0.2965; b2 = 0.57 * b2 + w * 1.0526; d[i] = (b0 + b1 + b2 + w * 0.1848) * 0.12; } });
    this.brown = mkb(d => { let b = 0; for (let i = 0; i < N; i++) { const w = R() * 2 - 1; b = (b + 0.02 * w) / 1.02; d[i] = b * 3.5; } });
    const loop = (buf, gain, filt, rate = 1) => { const s = c.createBufferSource(); s.buffer = buf; s.loop = true; s.playbackRate.value = rate; s.loopStart = R() * 2; let n = s; for (const f of filt) { n.connect(f); n = f; } const g = c.createGain(); g.gain.value = gain; n.connect(g); s.start(); return g; };
    const bq = (type, f, q = 1, gain = 0) => { const b = c.createBiquadFilter(); b.type = type; b.frequency.value = f; b.Q.value = q; b.gain.value = gain; return b; };
    this.bq = bq;
    /* the fire, at the hearth: the roar, its body in the middle of the range (what small speakers can carry), the hiss */
    this.fireP = this.panner(this.P.fire, 1.4, 0.5);
    this.roar = loop(this.brown, 0.0, [bq("lowpass", 170, 0.8), bq("peaking", 70, 1.5, 4)]); this.roar.connect(this.fireP);
    this.body = loop(this.pink, 0.0, [bq("bandpass", 520, 0.6), bq("lowpass", 1400, 0.7)], 0.9); this.body.connect(this.fireP);
    this.hiss = loop(this.pink, 0.0, [bq("bandpass", 2800, 0.5), bq("highpass", 1200, 0.7)], 1.3); this.hiss.connect(this.fireP);
    /* the wind at the glass and in the chimney */
    this.glassP = this.panner(this.P.glass, 3.5, 0.3); this.chimP = this.panner(this.P.chimney, 2.5, 0.4);
    this.windF = bq("bandpass", 420, 0.6); this.wind = loop(this.pink, 0.0, [this.windF, bq("lowpass", 1800, 0.5)]); this.wind.connect(this.glassP);
    this.whistle = loop(this.pink, 0.0, [bq("bandpass", 1150, 6)]); this.whistle.connect(this.glassP);
    this.chim = loop(this.brown, 0.0, [bq("lowpass", 95, 0.9)]); this.chim.connect(this.chimP);
    /* rain on the roof */
    this.roofP = this.panner(this.P.roof, 4.0, 0.3);
    this.rain = loop(this.white, 0.0, [bq("bandpass", 2600, 0.35), bq("highpass", 900, 0.6)]); this.rain.connect(this.roofP);
    this.rainLow = loop(this.pink, 0.0, [bq("lowpass", 500, 0.6)]); this.rainLow.connect(this.roofP);
    /* the clock on the mantel */
    this.clockP = this.panner(this.P.clock, 0.9, 0.35);
    /* the visitor's own sounds: under them, a little into the echo */
    this.me = c.createStereoPanner ? c.createStereoPanner() : c.createGain(); this.me.connect(this.master); const ms = c.createGain(); ms.gain.value = 0.35; this.me.connect(ms); ms.connect(this.verbIn);
    return true;
  }
  panner(p, ref, send){
    const c = this.ctx, pn = c.createPanner(); pn.panningModel = "HRTF"; pn.distanceModel = "inverse"; pn.refDistance = ref; pn.rolloffFactor = 1.1; pn.maxDistance = 60;
    if (pn.positionX) { pn.positionX.value = p[0]; pn.positionY.value = p[1]; pn.positionZ.value = p[2]; } else pn.setPosition(p[0], p[1], p[2]);
    pn.connect(this.master); const s = c.createGain(); s.gain.value = send; pn.connect(s); s.connect(this.verbIn); return pn;
  }
  burst(dest, when, dur, gain, filt, buf){
    const c = this.ctx, s = c.createBufferSource(); s.buffer = buf || this.white; s.loop = true; s.loopStart = this.R() * 3; let n = s; for (const f of filt) { n.connect(f); n = f; }
    const g = c.createGain(); g.gain.setValueAtTime(0, when); g.gain.linearRampToValueAtTime(gain, when + 0.003); g.gain.exponentialRampToValueAtTime(0.0004, when + dur); n.connect(g); g.connect(dest); s.start(when); s.stop(when + dur + 0.05);
  }
  tone(dest, when, f0, f1, dur, gain, type = "sine"){
    const c = this.ctx, o = c.createOscillator(); o.type = type; o.frequency.setValueAtTime(f0, when); o.frequency.exponentialRampToValueAtTime(Math.max(1, f1), when + dur);
    const g = c.createGain(); g.gain.setValueAtTime(0, when); g.gain.linearRampToValueAtTime(gain, when + 0.003); g.gain.exponentialRampToValueAtTime(0.0004, when + dur); o.connect(g); g.connect(dest); o.start(when); o.stop(when + dur + 0.05);
  }
  start(){
    if (this.dead) return false;
    if (!this.ctx) { try { if (!this.mk()) return false; } catch (e) { this.dead = true; return false; } }
    if (this.ctx.state === "suspended") this.ctx.resume().catch(() => {});
    this.on = true; const t = this.ctx.currentTime; this.master.gain.cancelScheduledValues(t); this.master.gain.setValueAtTime(this.master.gain.value, t); this.master.gain.linearRampToValueAtTime(0.9, t + 1.4);
    this.timers.crackle = t + 0.2; this.timers.pop = t + 1 + this.R() * 4; this.timers.settle = t + 25 + this.R() * 50; this.timers.drip = t + 0.5;
    this.timers.tick = t + ((1000 - Date.now() % 1000) / 1000);      // the first tick on the next whole second of the device's clock
    return true;
  }
  stop(){ if (!this.ctx || !this.on) return; this.on = false; const t = this.ctx.currentTime; this.master.gain.cancelScheduledValues(t); this.master.gain.setValueAtTime(this.master.gain.value, t); this.master.gain.linearRampToValueAtTime(0, t + 0.5);
    setTimeout(() => { if (!this.on && this.ctx && this.ctx.state === "running") this.ctx.suspend().catch(() => {}); }, 700); }
  close(){ if (this.ctx) { try { this.ctx.close(); } catch (e) {} this.ctx = null; } this.on = false; }
  pause(){ if (this.ctx && this.ctx.state === "running") this.ctx.suspend().catch(() => {}); }
  resume(){ if (this.ctx && this.on && this.ctx.state === "suspended") this.ctx.resume().catch(() => {}); }
  /* what the hour, the season and the weather set: the wind's level, rain or not, the fire's strength */
  setLevels(wind, rain, fire){ this.level = {wind, rain, fire}; }
  /* each frame: the listener where the eyes are, the beds following the fire's flicker and the wind's gusts, the
     scheduled sounds a little ahead of time. flick: the fire's flicker (about 0.7 to 1.1); g: the gust (0 to 1) */
  update(cam, flick, g){
    if (!this.ctx || !this.on) return;
    const c = this.ctx, L = c.listener, p = cam.position, f = V3(0, 0, -1).applyQuaternion(cam.quaternion), u = V3(0, 1, 0).applyQuaternion(cam.quaternion), t = c.currentTime, R = this.R, lv = this.level;
    if (L.positionX) { L.positionX.value = p.x; L.positionY.value = p.y; L.positionZ.value = p.z; L.forwardX.value = f.x; L.forwardY.value = f.y; L.forwardZ.value = f.z; L.upX.value = u.x; L.upY.value = u.y; L.upZ.value = u.z; }
    else { L.setPosition(p.x, p.y, p.z); L.setOrientation(f.x, f.y, f.z, u.x, u.y, u.z); }
    const k = 0.05;
    this.roar.gain.setTargetAtTime(0.22 * lv.fire * (0.75 + 0.35 * flick), t, k); this.body.gain.setTargetAtTime(0.5 * lv.fire * (0.7 + 0.4 * flick), t, k); this.hiss.gain.setTargetAtTime(0.08 * lv.fire * (0.6 + 0.6 * flick), t, k);      // the pink bed is an eighth of the brown's amplitude, so its gains run higher
    const w = lv.wind * (0.25 + 0.75 * g);
    this.wind.gain.setTargetAtTime(0.11 * w, t, 0.12); this.windF.frequency.setTargetAtTime(330 + 420 * g, t, 0.3); this.whistle.gain.setTargetAtTime(0.012 * Math.max(0, g - 0.55) * lv.wind, t, 0.2); this.chim.gain.setTargetAtTime(0.4 * w, t, 0.2);
    this.rain.gain.setTargetAtTime(0.075 * lv.rain * (0.8 + 0.3 * g), t, 0.4); this.rainLow.gain.setTargetAtTime(0.14 * lv.rain, t, 0.4);
    while (this.timers.crackle < t + 0.3) {      /* the fire's crackle: small, bright, close together when the fire is up */
      const at = this.timers.crackle; this.burst(this.fireP, at, 0.006 + R() * 0.014, (0.09 + R() * 0.26) * lv.fire, [this.bq("highpass", 1800 + R() * 2500, 1), this.bq("bandpass", 3000 + R() * 3000, 2)]);
      this.timers.crackle = at + (0.05 + R() * 0.35) / (0.6 + 0.5 * flick); }
    while (this.timers.pop < t + 0.3) {      /* a pop: a sharp burst with a low knock under it */
      const at = this.timers.pop; this.burst(this.fireP, at, 0.03, 0.4 * lv.fire, [this.bq("bandpass", 1500 + R() * 1500, 1.5)]); this.tone(this.fireP, at, 160, 60, 0.06, 0.12 * lv.fire);
      this.timers.pop = at + 1.5 + R() * 6; }
    while (this.timers.settle < t + 0.3) {      /* a log settling: a thud, a shower of crackles, a flare in the roar */
      const at = this.timers.settle; this.tone(this.fireP, at, 75, 38, 0.38, 0.5 * lv.fire); this.burst(this.fireP, at, 0.25, 0.22 * lv.fire, [this.bq("lowpass", 400, 0.8)]);
      for (let i = 0; i < 26; i++) { const dt = R() * R() * 1.4; this.burst(this.fireP, at + 0.02 + dt, 0.006 + R() * 0.012, (0.08 + R() * 0.2) * (1 - dt / 1.6) * lv.fire, [this.bq("highpass", 2000 + R() * 3000, 1)]); }
      this.roar.gain.setTargetAtTime(0.42 * lv.fire, at, 0.05); if (this.onSettle) setTimeout(() => this.onSettle && this.onSettle(), Math.max(0, (at - t) * 1000));
      this.timers.settle = at + 40 + R() * 80; }
    while (this.timers.tick < t + 0.3) {      /* the clock: tick on the second, tock on the half */
      const at = this.timers.tick, tock = this.side = !this.side; this.burst(this.clockP, at, 0.014, tock ? 0.05 : 0.07, [this.bq("bandpass", tock ? 2300 : 3100, 7)]); this.tone(this.clockP, at, tock ? 1900 : 2600, tock ? 1500 : 2100, 0.018, 0.02);
      this.timers.tick = at + 0.5; }
    if (lv.rain > 0) while (this.timers.drip < t + 0.3) {      /* drips off the eaves and onto the deck boards */
      const at = this.timers.drip, to = R() < 0.6 ? this.roofP : this.glassP; this.tone(to, at, 1500 + R() * 1600, 900 + R() * 400, 0.045, 0.035 * lv.rain); this.burst(to, at, 0.02, 0.03 * lv.rain, [this.bq("bandpass", 2400 + R() * 2000, 3)]);
      this.timers.drip = at + 0.12 + R() * 0.7; }
    else this.timers.drip = t + 0.5;
  }
  /* one step of the visitor's own: on the boards, on the rug, on the stair */
  step(kind, speed = 1){ if (!this.ctx || !this.on) return; const c = this.ctx, t = c.currentTime, k = Math.max(0.3, Math.min(1, speed)), R = this.R; if (this.me.pan) this.me.pan.value = (this.side = !this.side) ? 0.16 : -0.16;
    if (kind === "rug") { this.burst(this.me, t, 0.07, 0.09 * k, [this.bq("lowpass", 700, 0.8)]); this.tone(this.me, t, 110, 60, 0.06, 0.05 * k); }
    else if (kind === "stair") { this.burst(this.me, t, 0.09, 0.16 * k, [this.bq("bandpass", 420 + R() * 120, 2)]); this.tone(this.me, t, 170, 80, 0.1, 0.12 * k, "triangle"); this.burst(this.me, t + 0.04, 0.03, 0.05 * k, [this.bq("highpass", 2200, 1)]); }
    else { this.burst(this.me, t, 0.06, 0.14 * k, [this.bq("bandpass", 600 + R() * 300, 1.2)]); this.tone(this.me, t, 140, 70, 0.07, 0.1 * k); this.burst(this.me, t + 0.03, 0.025, 0.05 * k, [this.bq("highpass", 2500, 1)]); } }
  /* sitting down: leather gives and creaks; the rocker's wood; the loft's rail is only a hand on wood */
  sit(kind){ if (!this.ctx || !this.on) return; const c = this.ctx, t = c.currentTime;
    if (kind === "sofa" || kind === "armchair") { this.burst(this.me, t, 0.3, 0.12, [this.bq("lowpass", 320, 0.7)]); this.tone(this.me, t + 0.08, 95, 150, 0.32, 0.03, "sawtooth"); this.burst(this.me, t + 0.1, 0.25, 0.05, [this.bq("bandpass", 1100, 4)]); }
    else if (kind === "rocker") { this.burst(this.me, t, 0.12, 0.12, [this.bq("bandpass", 500, 3)]); this.tone(this.me, t + 0.05, 130, 180, 0.22, 0.03, "sawtooth"); }
    else { this.burst(this.me, t, 0.05, 0.08, [this.bq("bandpass", 900, 2)]); } }
  /* the rocker's creak at the end of each rock */
  creak(){ if (!this.ctx || !this.on) return; const t = this.ctx.currentTime, R = this.R; this.tone(this.me, t, 160 + R() * 60, 230 + R() * 60, 0.26, 0.016, "sawtooth"); this.burst(this.me, t, 0.05, 0.03, [this.bq("bandpass", 700, 3)]); }
}

/* ---------- where a visitor may stand: the floor's rules ---------- */
function makeFree(blocks){
  return (x, z) => { const inX = HX - LOG_R - RADIUS, inZ = HZ - LOG_R - RADIUS; if (x < -inX || x > inX || z < -inZ || z > inZ) return false;
    return !blocks.some(b => x > b[0] - RADIUS && x < b[1] + RADIUS && z > b[2] - RADIUS && z < b[3] + RADIUS); };
}
const rampY = z => Math.max(0, Math.min(1, (z - STAIR.z0) / STAIR.run)) * LOFT_Y;
/* where a step would land, given the level the visitor is on (ground, the stair's ramp, the loft): {level, y}, or null
   when the step is blocked by a wall, a chair, the stair's rails, the loft's railing or the roof's low edge */
function makeLevels(free){
  const inX = HX - LOG_R - RADIUS, inZ = HZ - LOG_R - RADIUS;
  return (x, z, level) => {
    if (x < -inX || x > inX || z < -inZ || z > inZ) return null;
    const dx = Math.abs(x - STAIR.x), onRamp = dx < STAIR.w / 2 - 0.12;
    if (level === "loft") {
      if (z < LOFT_Z + 0.35) return (onRamp && z > LOFT_Z - 0.35) ? {level: "ramp", y: rampY(z)} : null;
      return Math.abs(x) > LOFT_X ? null : {level: "loft", y: LOFT_Y};
    }
    if (level === "ramp") {
      if (!onRamp) return null;
      if (z > LOFT_Z + 0.35) return {level: "loft", y: LOFT_Y};
      if (z < STAIR.z0 - 0.35) return {level: "ground", y: 0};
      return {level: "ramp", y: rampY(z)};
    }
    if (onRamp && z > STAIR.z0 - 0.35 && z < LOFT_Z + 0.6) return z < STAIR.z0 + 0.45 ? {level: "ramp", y: rampY(z)} : null;      // the foot of the stair climbs; under it is blocked
    if (!onRamp && dx < STAIR.w / 2 + 0.28 && z > STAIR.z0 - 0.15 && z < LOFT_Z + 0.3) return null;      // the stair's rails and stringers
    return free(x, z) ? {level: "ground", y: 0} : null;
  };
}

/* ---------- the room, running ---------- */
export function start(canvas, opts = {}){
  const still = !!opts.still;
  const lite = opts.lite != null ? !!opts.lite : (matchMedia("(pointer: coarse)").matches || (navigator.hardwareConcurrency || 8) <= 4 || !!(navigator.deviceMemory && navigator.deviceMemory < 4));
  let renderer;
  try { renderer = new THREE.WebGLRenderer({canvas, antialias: false, powerPreference: lite ? "low-power" : "high-performance", preserveDrawingBuffer: !!opts.keep}); } catch (e) { return null; }
  if (!renderer.capabilities.isWebGL2) { renderer.dispose(); return null; }
  renderer.outputColorSpace = THREE.SRGBColorSpace; renderer.toneMapping = THREE.NoToneMapping;      // the lens does the tone mapping
  renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  const ANISO = Math.min(8, renderer.capabilities.getMaxAnisotropy());
  const hi = opts.hi != null ? !!opts.hi : (!lite && renderer.capabilities.maxTextureSize >= 8192);
  const base = opts.assets || "cabin_assets/";
  const lens = new Lens(renderer, lite), U = lens.mFinal.uniforms;
  const ac = new AbortController(), on = (el, ev, fn, o) => el.addEventListener(ev, fn, Object.assign({signal: ac.signal}, o || {}));
  /* the visitor and the clock, declared first: files that arrive early redraw the room through kick() */
  const me = {x: 0, y: 0, z: 0, yaw: 0, pitch: 0, level: "ground", mode: "seated", seat: "sofa", eye: EYE, bob: 0, phase: 0, vx: 0, vz: 0};
  let hover = -1, raf = 0, last = 0, clock = 0, dead = false, going = null, walkTo = null, ready = false, moved = false, rising = null, cut = null, veilA = 0, focus = 4, drawn = 0, stillOn = still, doorCool = 0;
  const scene = new THREE.Scene(), camera = new THREE.PerspectiveCamera(62, 1, 0.05, 400);
  camera.rotation.order = "YXZ";
  scene.background = new THREE.Color("#120d0a");
  const pm = new THREE.PMREMGenerator(renderer); let envRT = pm.fromScene(new RoomEnvironment(), 0.04); scene.environment = envRT.texture;
  const hemi = new THREE.HemisphereLight("#dbe8ff", "#7a5a3c", 0.8), sun = new THREE.DirectionalLight("#fff2dc", 3); scene.add(hemi, sun, sun.target);
  sun.castShadow = true; sun.shadow.mapSize.set(lite ? 1024 : 2048, lite ? 1024 : 2048); sun.shadow.bias = -0.0006; sun.shadow.normalBias = 0.03;
  Object.assign(sun.shadow.camera, {left: -9, right: 9, top: 9, bottom: -9, near: 1, far: 120}); sun.target.position.set(0, 1.2, -1.5);
  /* files arriving: the page is told, and the room is redrawn as each one lands */
  const manager = new THREE.LoadingManager(); let loaded = false;
  manager.onProgress = (url, done, all) => { opts.onProgress && opts.onProgress(done, all); kick(); };
  manager.onLoad = () => { loaded = true; kick(); };
  const blocks = [], free = makeFree(blocks), levelAt = makeLevels(free), ctx = {blocks, redraw: () => kick()};
  const M = materials(base, manager, ANISO, ctx.redraw, hi);
  const R = buildRoom(scene, M, {posters: opts.posters, back: opts.back, still, lite}, ctx), VIEW = buildView(scene), WX = weatherOutside(scene);
  const dust = dustPoints(lite, U); scene.add(dust);
  let S = HOURS.afternoon, when = "afternoon", season = "summer", weather = "clear"; const sunL = V3(0, -0.4, 1);
  /* the sound, where its things are */
  const sound = new CabinSound({fire: [R.ox, FIRE.hearth + 0.5, R.fz], clock: [R.ox - 0.1, R.MANTEL_Y + 0.12, R.fz - 0.5], glass: [0, 2.6, GLASS_Z], chimney: [HX - 0.5, 4.5, R.fz], roof: [0, HR - 0.4, 0]});
  sound.onSettle = () => { R.fire.burst(); kick(); };
  /* the room's own light, taken from where the visitor is: a cube picture of the room, folded for the materials */
  const cubeRT = new THREE.WebGLCubeRenderTarget(lite ? 128 : 256, {type: lens.hdr ? THREE.HalfFloatType : THREE.UnsignedByteType, generateMipmaps: false});
  const cubeCam = new THREE.CubeCamera(0.12, 90, cubeRT), probedAt = V3(1e9, 0, 0);
  function probe(force){
    const p = V3(me.x, me.y + me.eye, me.z); if (!force && p.distanceTo(probedAt) < 2.5) return; probedAt.copy(p);
    const hidden = [dust, WX.snow, WX.rain, R.fire.points], vis = hidden.map(o => o.visible); hidden.forEach(o => { o.visible = false; });
    cubeCam.position.copy(p); cubeCam.update(renderer, scene);
    const old = envRT; envRT = pm.fromCubemap(cubeRT.texture); scene.environment = envRT.texture; if (old) old.dispose();
    hidden.forEach((o, i) => { o.visible = vis[i]; });
  }
  /* the furniture: CC0 models from Poly Haven, each in a pivot at its place on the floor, blocking the floor it stands on */
  const gltf = new GLTFLoader(manager).setPath(base + "models/");
  const placed = {};
  function model(id, at){
    if (lite && PHONE_SKIP.includes(id)) return;      // the small things a phone's budget leaves out
    gltf.load(`${id}/${id}${lite ? "_lite" : "_1k"}.gltf`, g => { const o = g.scene, pivot = new THREE.Group(); o.scale.setScalar(at.scale || 1); o.updateMatrixWorld(true);
      const bb = new THREE.Box3().setFromObject(o); o.position.set(-(bb.min.x + bb.max.x) / 2, -bb.min.y, -(bb.min.z + bb.max.z) / 2); pivot.add(o);
      pivot.position.set(at.x, at.y || 0, at.z); pivot.rotation.y = at.ry || 0;
      o.traverse(n => { if (n.isMesh) { n.castShadow = true; n.receiveShadow = true; const ms = Array.isArray(n.material) ? n.material : [n.material]; for (const m of ms) { if (at.tint && m.color) m.color.multiply(new THREE.Color(at.tint)); if (at.flat && m.map) { m.map = null; m.color.set(at.flat); m.needsUpdate = true; } if (at.rough != null) m.roughness = at.rough; } } });
      R.group.add(pivot); pivot.updateMatrixWorld(true); const wb = new THREE.Box3().setFromObject(pivot);
      if (at.block !== false && wb.min.y < 1.2) blocks.push([wb.min.x, wb.max.x, wb.min.z, wb.max.z]);
      placed[id] = placed[id] || []; placed[id].push({pivot, obj: o, box: wb}); at.then && at.then(pivot, wb, o); kick(); }, undefined, () => { placed[id] = placed[id] || null; });
  }
  const fz = R.fz, rug = R.RUG; let rocker = null, hands = null, lantern = null;
  model("sofa_02", {x: rug.x - 1.55, z: rug.z, ry: Math.PI / 2, flat: "#4e2c17", rough: 0.55,
    then: (o, wb) => { model("throw_pillows_01", {x: wb.min.x + 0.42, y: (wb.max.y - wb.min.y) * 0.42, z: wb.max.z - 0.55, ry: Math.PI / 2 - 0.3, block: false});
      R.lamp(rug.x - 1.55, 0, wb.min.z - 0.55); R.lamp(rug.x - 1.55, 0, wb.max.z + 0.55);
      model("side_table_tall_01", {x: rug.x - 1.55, z: wb.min.z - 0.55, then: (t, tb) => { R.lights.lamps[0] && (R.lights.lamps[0].pl.parent.position.y = tb.max.y); }});
      model("side_table_tall_01", {x: rug.x - 1.55, z: wb.max.z + 0.55, then: (t, tb) => { R.lights.lamps[1] && (R.lights.lamps[1].pl.parent.position.y = tb.max.y); }}); }});
  model("small_wooden_table_01", {x: rug.x + 0.1, z: rug.z, ry: Math.PI / 2, tint: "#c9a27a",
    then: (o, wb) => { const y = wb.max.y; model("wooden_bowl_01", {x: rug.x - 0.18, y, z: rug.z + 0.1, ry: 0.3, block: false, scale: 0.85});
      mesh(new THREE.CylinderGeometry(0.04, 0.035, 0.09, 18), std({color: "#e9e4d6", roughness: 0.35}), rug.x + 0.1 + 0.3, y + 0.045, rug.z - 0.3, R.group); mesh(new THREE.TorusGeometry(0.03, 0.007, 8, 16), std({color: "#e9e4d6", roughness: 0.35}), rug.x + 0.1 + 0.35, y + 0.05, rug.z - 0.3, R.group).rotation.y = Math.PI / 2;
      mesh(new THREE.CylinderGeometry(0.11, 0.09, 0.05, 20), std({color: "#4a3a2a", roughness: 0.6}), rug.x + 0.1 + 0.25, y + 0.025, rug.z + 0.35, R.group); kick(); }});
  model("ArmChair_01", {x: 3.0, z: -0.6, ry: 0.69, tint: "#d8b48e"});
  model("ArmChair_01", {x: 3.0, z: 2.9, ry: 2.42, tint: "#d8b48e",
    then: (o, wb) => { const b = sizedBox(0.52, 0.03, 0.4, M.plaid, wb.min.x + 0.22, wb.min.y + (wb.max.y - wb.min.y) * 0.62, 2.9 + 0.15, R.group, 0.6); b.rotation.y = 2.42; b.rotation.z = -0.08; }});
  model("Rockingchair_01", {x: -3.3, z: -2.3, ry: 1.03, then: (p, wb, o) => { const rock = new THREE.Group(); p.remove(o); rock.add(o); p.add(rock); rocker = {pivot: p, rock, obj: o}; }});
  model("antique_ceramic_vase_01", {x: R.ox - 0.1, y: R.MANTEL_Y, z: fz + 0.25, scale: 0.75, block: false});
  model("mantel_clock_01", {x: R.ox - 0.08, y: R.MANTEL_Y, z: fz - 0.5, ry: -Math.PI / 2, scale: 1.25, block: false, then: (p, wb, o) => {
    let glass = null; o.traverse(n => { if (n.isMesh && /glass/i.test(n.name)) glass = n; });      // the hands sit just behind the glass, at the face's centre
    if (!glass) return; glass.geometry.computeBoundingBox(); const gb = glass.geometry.boundingBox, c = gb.getCenter(V3()); glass.localToWorld(c); o.worldToLocal(c);
    hands = clockHands(o, M); hands.group.position.set(c.x, c.y, gb.max.z + glass.position.z - 0.006); hands.set(new Date()); }});
  model("book_encyclopedia_set_01", {x: R.ox - 0.08, y: R.MANTEL_Y, z: fz + 0.85, ry: -Math.PI / 2, block: false});
  model("Lantern_01", {x: R.ox - 0.3, y: FIRE.hearth + 0.06, z: fz - 1.2, ry: 0.5, block: false, then: (p, wb) => {
    const l = new THREE.PointLight("#ffb257", 0, 4, 2); l.position.set((wb.min.x + wb.max.x) / 2, wb.min.y + (wb.max.y - wb.min.y) * 0.45, (wb.min.z + wb.max.z) / 2); R.group.add(l);
    const fm = std({color: "#ffd080", emissive: "#ffb040", emissiveIntensity: 0}); const fl = mesh(new THREE.SphereGeometry(0.01, 8, 8), fm, l.position.x, l.position.y - 0.02, l.position.z, R.group, false); fl.scale.y = 1.8; lantern = {light: l, flame: fm}; }});
  model("wicker_basket_01", {x: HX - 0.62, z: fz + FIRE.w / 2 + 0.55, ry: 0.25, then: (p, wb) => { const r = rng(3);
    for (let i = 0; i < 4; i++) { const l = logAt(0.42, 0.055 + r() * 0.015, M.bark, (wb.min.x + wb.max.x) / 2, wb.min.y + 0.1 + i * 0.05, (wb.min.z + wb.max.z) / 2 + (i - 1.5) * 0.085, "x", R.group, 9); l.rotation.y = (r() - 0.5) * 0.3; } }});
  model("hatchet", {x: HX - 0.38, y: 0.075 + 4 * 0.135, z: fz + FIRE.w / 2 + 1.3, ry: 0.35, block: false});
  model("potted_plant_02", {x: -3.95, z: -3.55});
  model("lantern_chandelier_01", {x: rug.x - 0.2, y: 0, z: rug.z, block: false, scale: 1.1, then: (p, wb) => {
    p.position.y += 2.7 - wb.min.y; p.updateMatrixWorld(true); const b2 = new THREE.Box3().setFromObject(p);      // it hangs just above head height, on a chain from the ridge
    mesh(new THREE.CylinderGeometry(0.012, 0.012, HR - 0.45 - b2.max.y, 8), M.iron, rug.x - 0.2, (HR - 0.45 + b2.max.y) / 2, rug.z, R.group, false);
    const pl = new THREE.PointLight("#ffcf8a", 0, 18, 2); pl.position.set(rug.x - 0.2, (b2.min.y + b2.max.y) / 2, rug.z); R.group.add(pl);      // the room's main light at night: it reaches the floor by the glass
    const bulbM = std({color: "#fff6e0", emissive: "#ffe6b0", emissiveIntensity: 0}); mesh(new THREE.SphereGeometry(0.035, 12, 10), bulbM, rug.x - 0.2, (b2.min.y + b2.max.y) / 2, rug.z, R.group, false);
    R.lights.lamps.push({pl, shadeM: null, bulbM, chandelier: true}); applyHour(); }});

  /* ---- the seats ---- */
  const yawOf = (fx, fz2) => Math.atan2(-fx, -fz2);
  const seats = {
    sofa: {x: 0.98, z: rug.z, yaw: -Math.PI / 2, pitch: -0.03, level: "ground", eye: SIT.sofa, up: [1.75, rug.z], kind: "sofa"},
    armchair: {x: 3.04, z: -0.55, yaw: yawOf(0.64, 0.77), pitch: -0.02, level: "ground", eye: SIT.armchair, up: [3.42, -0.06], kind: "armchair"},
    rocker: {x: -3.38, z: -2.35, yaw: yawOf(0.86, 0.51), pitch: -0.02, level: "ground", eye: SIT.rocker, up: [-2.72, -1.92], kind: "rocker"},
    loft: {x: 1.1, z: LOFT_Z + 0.9, yaw: -0.3, pitch: -0.14, level: "loft", eye: EYE, up: [1.1, LOFT_Z + 0.9], kind: "loft", standing: true},      // a step back from the rail, turned a little toward the hearth and the lamps, so the lit middle of the room is in view and the rail's top log sits at the frame's foot
  };
  const floorOf = level => level === "loft" ? LOFT_Y : 0;
  function place(id){ const s = seats[id]; me.x = s.x; me.z = s.z; me.yaw = s.yaw; me.pitch = s.pitch; me.level = s.level; me.y = floorOf(s.level); me.seat = id; me.mode = "seated"; me.eye = s.eye; me.vx = me.vz = 0; walkTo = null; }
  place(SEATS.some(s => s.id === opts.seat) ? opts.seat : "sofa");
  const tNow = () => clock;
  const cutTo = fn => { if (cut) return; if (stillOn) { fn(); return; } cut = {t: clock, fn}; kick(); };
  const nearestSeat = () => { let best = "sofa", bd = 1e9; for (const id in seats) { const s = seats[id]; if (s.level !== me.level) continue; const d = Math.hypot(me.x - s.up[0], me.z - s.up[1]); if (d < bd) { bd = d; best = id; } } return best; };
  function standUp(){
    if (me.mode !== "seated" || rising || going) return;
    const s = seats[me.seat];
    if (s.standing) { me.mode = "walking"; told(); opts.onMove && opts.onMove(state()); kick(); return; }
    if (stillOn) { me.x = s.up[0]; me.z = s.up[1]; me.eye = EYE; me.pitch = Math.max(-0.3, Math.min(0.3, me.pitch * 0.6)); me.mode = "walking"; probe(true); opts.onMove && opts.onMove(state()); kick(); return; }
    rising = {t: clock, from: [me.x, me.z, me.eye], to: [s.up[0], s.up[1], EYE], dir: 1, pitch0: me.pitch, pitch1: Math.max(-0.3, Math.min(0.3, me.pitch * 0.6))};
    me.mode = "walking"; told(); opts.onMove && opts.onMove(state()); kick();
  }
  function sitDown(id){
    if (going || rising) return;
    const want = id && seats[id] ? id : nearestSeat(), s = seats[want];
    if (me.mode === "walking" && me.level === s.level && Math.hypot(me.x - s.up[0], me.z - s.up[1]) < 1.6) {      // close by: sit down, no cut
      if (stillOn || s.standing) { place(want); sound.sit(s.kind); probe(true); opts.onMove && opts.onMove(state()); kick(); return; }
      rising = {t: clock, from: [me.x, me.z, me.eye], to: [s.x, s.z, s.eye], dir: -1, pitch0: me.pitch, pitch1: s.pitch, seat: want, yaw0: me.yaw, yaw1: s.yaw}; me.seat = want; walkTo = null; kick(); return;
    }
    cutTo(() => { place(want); sound.sit(s.kind); probe(true); opts.onMove && opts.onMove(state()); });
  }

  /* ---- the hour, the season and the weather ---- */
  const viewLoader = new THREE.TextureLoader(), viewCache = {}; let shown = null;
  function pickView(hour, seas){ const list = (opts.views || {})[hour] || []; if (!list.length) return null; return list.find(v => v.season === seas) || list.find(v => v.season === "any") || list[0]; }
  function showView(hour, seas){
    const v = pickView(hour, seas); const u = VIEW.mat.uniforms; u.uSkyTop.value.set(S.sky[0]); u.uSkyLow.value.set(S.sky[1]); u.uTint.value.set(...S.view.tint); u.uGain.value = S.view.gain; u.uNight.value = S.view.night || 0; u.uRain.value = weather === "rain" ? 1 : 0;
    if (!v) { u.uHas.value = 0; shown = null; opts.onView && opts.onView(null); return; }
    const apply = t => { if (shown !== v) return; u.uMap.value = t; u.uHas.value = 1; VIEW.place(v.horizon == null ? 0.55 : v.horizon, (v.w && v.h) ? v.w / v.h : 1.5); kick(); };
    shown = v; opts.onView && opts.onView({caption: v.caption, credit: v.credit, season: v.season, shown: v.season === seas || v.season === "any", hour, wanted: seas, weather});
    if (viewCache[v.file]) apply(viewCache[v.file]); else viewLoader.load(base + "view/" + v.file, t => { t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = ANISO; t.wrapS = THREE.MirroredRepeatWrapping; t.wrapT = THREE.ClampToEdgeWrapping; t.minFilter = THREE.LinearMipmapLinearFilter; viewCache[v.file] = t; apply(t); }, undefined, () => { u.uHas.value = 0; });
  }
  function applyHour(){
    const s = S, rain = weather === "rain", se = SEASONS[season] || SEASONS.summer;
    hemi.color.set(s.hemi[0]); hemi.groundColor.set(s.hemi[1]); hemi.intensity = s.hemi[2] * (rain ? 1.35 : 1);
    sun.color.set(rain ? "#dfe6ee" : s.sunCol); sun.intensity = s.sunI * (rain ? 0.28 : 1);
    sunL.set(-s.sun[0], -s.sun[1] * se.sunY, -s.sun[2]).normalize();      // the way the light travels, into the room
    sun.position.copy(sunL).multiplyScalar(-40).add(sun.target.position);
    scene.environmentIntensity = s.env * (rain ? 0.8 : 1);
    const lamps = rain ? Math.max(0.7, s.lamps) : s.lamps;
    for (const l of R.lights.lamps) { l.pl.intensity = (l.chandelier ? 28 : 16) * lamps; if (l.shadeM) l.shadeM.emissiveIntensity = 1.3 * lamps; l.bulbM.emissiveIntensity = 4 * lamps; }
    R.candleFlame.emissiveIntensity = 3 * lamps; if (lantern) { lantern.light.intensity = 2.2 * lamps; lantern.flame.emissiveIntensity = 3 * lamps; }
    R.glassM.opacity = lamps ? 0.16 : 0.09; R.wet.visible = rain; R.deckSnow.visible = season === "winter";
    U.uShaft.value = rain ? 0 : s.shaft; U.uHaze.value = s.haze; dust.seed(rain || !s.shaft ? null : sunL); dust.visible = !!s.shaft && !rain;
    sound.setLevels(s.wind * se.wind, rain ? 1 : 0, 1);
  }
  function setWhen(w, se, we){ when = HOURS[w] ? w : whenNow(); season = SEASONS[se] ? se : seasonNow(); S = HOURS[when]; weather = we === "rain" || we === "clear" ? we : weatherNow(when, season); applyHour(); showView(when, season); if (ready) { draw(); probe(true); } kick(); }

  /* ---- drawing ---- */
  function size(w, h){
    w = w || canvas.clientWidth || 960; h = h || canvas.clientHeight || 600;
    const ratio = lite ? Math.min(1.5, devicePixelRatio || 1, Math.sqrt(1.15e6 / (w * h))) : Math.min(2, devicePixelRatio || 1, Math.sqrt(3.6e6 / (w * h)));
    renderer.setPixelRatio(ratio); renderer.setSize(w, h, false); const v = new THREE.Vector2(); renderer.getDrawingBufferSize(v); lens.size(v.x, v.y); dust.material.uniforms.uDpr.value = ratio;
    camera.aspect = w / h; const hf = 80 * Math.PI / 180;      // a wide lens, wider still on a tall, narrow screen
    camera.fov = Math.max(54, Math.min(camera.aspect < 0.8 ? 92 : 84, 2 * Math.atan(Math.tan(hf / 2) / camera.aspect) * 180 / Math.PI)); camera.updateProjectionMatrix();
  }
  size();

  /* ---- moving and looking ---- */
  const held = new Set(), KEYS = {ArrowLeft: "left", ArrowRight: "right", ArrowUp: "fwd", ArrowDown: "back", w: "fwd", W: "fwd", s: "back", S: "back", a: "strafeL", A: "strafeL", d: "strafeR", D: "strafeR", q: "left", Q: "left", e: "right", E: "right"};
  const told = () => { if (!moved) { moved = true; opts.onMove && opts.onMove(state()); } };
  const input = k => { opts.onInput && opts.onInput(k); };
  on(window, "keydown", e => { const k = KEYS[e.key]; if (!k || e.altKey || e.ctrlKey || e.metaKey || (opts.keysOK && !opts.keysOK(e))) return;
    const t = e.target; if (t && /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName)) return;
    if (me.mode === "seated" && (k === "strafeL" || k === "strafeR")) return;
    e.preventDefault(); input("key"); walkTo = null;
    if (stillOn && me.mode === "seated") { turnBy(k === "left" ? 0.1 : k === "right" ? -0.1 : 0, k === "fwd" ? 0.06 : k === "back" ? -0.06 : 0); kick(); return; }
    held.add(k); kick(); });
  on(window, "keyup", e => { const k = KEYS[e.key]; if (k) held.delete(k); kick(); });
  on(window, "blur", () => { held.clear(); stick.on = false; stick.x = stick.y = 0; endDrag(); });
  const ray = new THREE.Raycaster(), ndc = new THREE.Vector2();
  function pick(ev){
    const b = canvas.getBoundingClientRect(); ndc.set(((ev.clientX - b.left) / b.width) * 2 - 1, -((ev.clientY - b.top) / b.height) * 2 + 1); ray.setFromCamera(ndc, camera);
    const hit = ray.intersectObjects(R.posters.map(p => p.paper), false)[0]; if (hit) return {door: R.posters.findIndex(p => p.paper === hit.object)};
    if (R.door.on && ray.intersectObject(R.door.hit, false)[0]) return {door: 2};      /* the way back: the page's third sign */
    if (ray.intersectObject(R.deckDoor.hit, false)[0]) return {door: 3};
    const f = ray.intersectObject(R.floor, false)[0]; return f ? {floor: f.point} : {};
  }
  let drag = null; const inertia = {y: 0, p: 0}, stick = {x: 0, y: 0, on: false};
  const kdeg = () => (camera.fov * Math.PI / 180) / Math.max(1, canvas.clientHeight || 600);
  const turnBy = (dy, dp) => { me.yaw += dy; me.pitch = Math.max(-1.2, Math.min(1.2, me.pitch + dp)); };
  const onStickEl = e => stick.on && e.target && e.target.closest && e.target.closest("[data-stick]");
  on(canvas, "pointerdown", e => { if (going || drag || (e.pointerType === "mouse" && e.button !== 0) || onStickEl(e)) return; drag = {id: e.pointerId, x: e.clientX, y: e.clientY, x0: e.clientX, y0: e.clientY, s: [], moved: false}; inertia.y = inertia.p = 0; canvas.classList.add("dragging"); });
  on(window, "pointermove", e => {
    if (drag && e.pointerId === drag.id) { const kk = kdeg(), dy = -(e.clientX - drag.x) * kk, dp = -(e.clientY - drag.y) * kk; drag.x = e.clientX; drag.y = e.clientY;
      if (!drag.moved && Math.hypot(e.clientX - drag.x0, e.clientY - drag.y0) > 6) { drag.moved = true; input("drag"); told(); }
      if (drag.moved) { turnBy(dy, dp); drag.s.push([performance.now(), dy, dp]); if (drag.s.length > 8) drag.s.shift(); kick(); } return; }
    if (e.target !== canvas || going) return;
    const p = pick(e), h = p.door != null ? p.door : -1; if (h !== hover) { hover = h; canvas.style.cursor = h >= 0 ? "pointer" : "grab"; opts.onHover && opts.onHover(h); kick(); }
  }, {passive: true});
  const endDrag = e => {
    if (!drag || (e && e.pointerId != null && e.pointerId !== drag.id)) return;
    const d = drag; drag = null; canvas.classList.remove("dragging");
    const now = performance.now(), sm = d.s.filter(q => now - q[0] < 90);
    if (!stillOn && d.moved && sm.length >= 2) { const span = Math.max(0.03, (now - sm[0][0]) / 1000); inertia.y = Math.max(-4, Math.min(4, sm.reduce((a, q) => a + q[1], 0) / span)); inertia.p = Math.max(-3, Math.min(3, sm.reduce((a, q) => a + q[2], 0) / span)); }
    if (!d.moved && e && e.target === canvas && !going) { const p = pick(e); input("tap");
      if (p.door === 2) goBack(); else if (p.door === 3) goDeck(); else if (p.door != null) go(p.door); else if (p.floor && me.mode === "walking" && me.level === "ground") { walkTo = nearestFree(p.floor.x, p.floor.z); told(); } }
    kick();
  };
  on(window, "pointerup", endDrag); on(window, "pointercancel", endDrag);
  canvas.style.touchAction = "none"; canvas.style.cursor = "grab";
  /* a phone's thumb control: the page gives an element; a finger on it walks the way the visitor looks, and sideways */
  const stickEl = opts.stick || null;
  if (stickEl) { let sid = null; const rect = () => stickEl.getBoundingClientRect();
    const set = e => { const r = rect(), cx = r.left + r.width / 2, cy = r.top + r.height / 2, rad = Math.max(20, r.width / 2); stick.x = Math.max(-1, Math.min(1, (e.clientX - cx) / rad)); stick.y = Math.max(-1, Math.min(1, -(e.clientY - cy) / rad)); opts.onStick && opts.onStick(stick.x, stick.y); };
    on(stickEl, "pointerdown", e => { if (me.mode !== "walking") return; sid = e.pointerId; stick.on = true; set(e); e.preventDefault(); input("stick"); told(); walkTo = null; kick(); });
    on(window, "pointermove", e => { if (stick.on && e.pointerId === sid) set(e); }, {passive: true});
    const off = e => { if (stick.on && (!e || e.pointerId === sid)) { stick.on = false; stick.x = stick.y = 0; opts.onStick && opts.onStick(0, 0); kick(); } };
    on(window, "pointerup", off); on(window, "pointercancel", off); }
  function nearestFree(x, z){ const inX = HX - LOG_R - RADIUS, inZ = HZ - LOG_R - RADIUS; x = Math.max(-inX, Math.min(inX, x)); z = Math.max(-inZ, Math.min(inZ, z));
    const ok = (px, pz) => { const l = levelAt(px, pz, "ground"); return l && l.level === "ground"; };
    if (ok(x, z)) return {x, z}; for (let r = 0.2; r < 2.6; r += 0.2) for (let a = 0; a < 12; a++) { const nx = x + Math.cos(a * Math.PI / 6) * r, nz = z + Math.sin(a * Math.PI / 6) * r; if (ok(nx, nz)) return {x: nx, z: nz}; } return null; }
  const turn = (to, k) => { let d = to - me.yaw; d = Math.atan2(Math.sin(d), Math.cos(d)); me.yaw += d * k; return Math.abs(d); };
  function go(i){ const p = R.posters[i]; if (!p || going) return; told(); if (stillOn) { opts.onLeave && opts.onLeave(p.url, i); return; } going = {i, t: 0, from: {x: me.x, z: me.z, yaw: me.yaw, pitch: me.pitch, eye: me.eye}, left: false}; walkTo = null; kick(); }
  function goBack(){ if (!R.door.on || going) return; told(); if (stillOn) { opts.onBack && opts.onBack(); return; } going = {i: 2, t: 0, from: {x: me.x, z: me.z, yaw: me.yaw, pitch: me.pitch, eye: me.eye}, left: false}; walkTo = null; kick(); }
  function goDeck(){ if (going) return; told(); if (stillOn) { opts.onDeck && opts.onDeck(); return; } going = {i: 3, t: 0, from: {x: me.x, z: me.z, yaw: me.yaw, pitch: me.pitch, eye: me.eye}, left: false}; walkTo = null; kick(); }
  function look(i){ const p = i === 2 ? (R.door.on ? R.door : null) : i === 3 ? R.deckDoor : R.posters[i]; if (!p || going) return; me.yaw = yawOf(p.x - me.x, p.wallZ - me.z); me.pitch = 0; kick(); }
  const doorOf = i => i === 2 ? R.door : i === 3 ? R.deckDoor : R.posters[i];
  /* a step on foot: the floor's rules, tried whole and then along each axis, so the visitor slides along what they meet */
  function tryMove(dx, dz){
    let l = levelAt(me.x + dx, me.z + dz, me.level); if (l) { me.x += dx; me.z += dz; me.level = l.level; me.y = l.y; return true; }
    let went = false; if (dx) { l = levelAt(me.x + dx, me.z, me.level); if (l) { me.x += dx; me.level = l.level; me.y = l.y; went = true; } }
    if (dz) { l = levelAt(me.x, me.z + dz, me.level); if (l) { me.z += dz; me.level = l.level; me.y = l.y; went = true; } }
    return went;
  }
  function step(dt){
    clock += dt;
    if (going) { const p = doorOf(going.i), g = going; g.t += dt / 1.7; const e = g.t >= 1 ? 1 : 1 - Math.pow(1 - g.t, 3);
      me.x = g.from.x + (p.stand.x - g.from.x) * e; me.z = g.from.z + (p.stand.z - g.from.z) * e; me.eye = g.from.eye + (EYE - g.from.eye) * e; me.y = floorOf(me.level) * (1 - e);
      const want = yawOf(p.x - me.x, p.wallZ - me.z); let d = want - g.from.yaw; d = Math.atan2(Math.sin(d), Math.cos(d)); me.yaw = g.from.yaw + d * e; me.pitch = g.from.pitch * (1 - e);
      p.heat = Math.min(1, p.heat + dt * 2);
      if (g.t >= 1 && !g.left) { g.left = true; if (g.i === 2) opts.onBack && opts.onBack(); else if (g.i === 3) opts.onDeck && opts.onDeck(); else opts.onLeave && opts.onLeave(p.url, g.i); }
      if (g.t > 1.8) { going = null; me.mode = "walking"; me.eye = EYE; p.heat = 0; doorCool = clock + 4; }      /* the page has left by now; if it is still here (the Back button, a page that stayed), the visitor is free again */
      return true; }
    let busy = !!drag || !!rising || !!cut;
    if (rising) { const u = Math.min(1, (clock - rising.t) / 1.25), e = u < 0.5 ? 4 * u * u * u : 1 - Math.pow(-2 * u + 2, 3) / 2;
      me.x = rising.from[0] + (rising.to[0] - rising.from[0]) * e; me.z = rising.from[1] + (rising.to[1] - rising.from[1]) * e; me.eye = rising.from[2] + (rising.to[2] - rising.from[2]) * e + Math.sin(u * Math.PI) * 0.03 * rising.dir; me.pitch = rising.pitch0 + (rising.pitch1 - rising.pitch0) * e;
      if (rising.dir < 0) { let d = rising.yaw1 - rising.yaw0; d = Math.atan2(Math.sin(d), Math.cos(d)); me.yaw = rising.yaw0 + d * e; }
      if (u >= 1) { const r = rising; rising = null; if (r.dir < 0) { place(r.seat); sound.sit(seats[r.seat].kind); } probe(true); opts.onMove && opts.onMove(state()); }
      return true; }
    const sp = (a, b) => held.has(a) ? 1 : held.has(b) ? -1 : 0;
    if (me.mode === "seated") { if (held.size) { turnBy(sp("left", "right") * 1.1 * dt, sp("fwd", "back") * 0.7 * dt); busy = true; } }
    else {
      const rot = sp("left", "right"), fwd = sp("fwd", "back") + (stick.on ? stick.y : 0), side = sp("strafeR", "strafeL") + (stick.on ? stick.x : 0);
      if (rot) { me.yaw += rot * 1.9 * dt; busy = true; }
      let wx = 0, wz = 0;
      if (fwd || side) { const s = Math.sin(me.yaw), c = Math.cos(me.yaw), n = Math.max(1, Math.hypot(fwd, side)); wx = (-s * fwd + c * side) / n; wz = (-c * fwd - s * side) / n; }
      else if (walkTo) { const dx = walkTo.x - me.x, dz = walkTo.z - me.z, dist = Math.hypot(dx, dz); if (dist < 0.08) walkTo = null; else { wx = dx / dist; wz = dz / dist; turn(Math.atan2(-wx, -wz), Math.min(1, dt * 3)); } }
      const speed = me.level === "ramp" ? 1.1 : 2.0;
      me.vx += (wx * speed - me.vx) * (1 - Math.exp(-dt / 0.16)); me.vz += (wz * speed - me.vz) * (1 - Math.exp(-dt / 0.16));
      const v = Math.hypot(me.vx, me.vz);
      if (v > 0.02) { const went = tryMove(me.vx * dt, me.vz * dt); if (!went) { me.vx *= 0.4; me.vz *= 0.4; walkTo = null; }
        const ph0 = me.phase; me.phase += dt * v * 0.9; if (Math.floor(me.phase) !== Math.floor(ph0)) sound.step(me.level === "ramp" ? "stair" : (Math.abs(me.x - rug.x) < rug.w / 2 && Math.abs(me.z - rug.z) < rug.d / 2 ? "rug" : "wood"), v / 2);
        me.bob = Math.min(1, v / 2); busy = true; probe(false);
        if (went && clock > doorCool && R.door.on && me.z > HZ - 1.25 && Math.abs(me.x - R.door.x) < 0.55 && Math.cos(me.yaw) < -0.5) { goBack(); return true; }      /* walked up to the glowing door, facing it */
        if (went && clock > doorCool && me.level === "ground" && me.z < -HZ + 1.25 && Math.abs(me.x - R.deckDoor.x) < 0.5 && Math.cos(me.yaw) > 0.5) { goDeck(); return true; } }
      else { me.vx = me.vz = 0; me.bob *= Math.exp(-dt / 0.3); }
    }
    if (!drag && (Math.abs(inertia.y) > 0.01 || Math.abs(inertia.p) > 0.01)) { turnBy(inertia.y * dt, inertia.p * dt); const q = Math.exp(-dt / 0.32); inertia.y *= q; inertia.p *= q; busy = true; } else if (!drag) inertia.y = inertia.p = 0;
    { const want = hover === 2 ? 1 : 0, dr = R.door; if (dr.on && dr.heat !== want) { dr.heat += Math.sign(want - dr.heat) * Math.min(Math.abs(want - dr.heat), dt * 4); busy = true; } }
    { const want = hover === 3 ? 1 : 0, dd = R.deckDoor; if (dd.heat !== want) { dd.heat += Math.sign(want - dd.heat) * Math.min(Math.abs(want - dd.heat), dt * 4); busy = true; } }
    R.posters.forEach((p, i) => { const want = i === hover ? 1 : 0; if (p.heat !== want) { p.heat += Math.sign(want - p.heat) * Math.min(Math.abs(want - p.heat), dt * 4); busy = true; } });
    return busy;
  }
  /* what the eye is on: the distance to the nearest thing in the middle of the view, for the focus */
  let focusAt = 0;
  function refocus(){ if (clock - focusAt < 0.15) return; focusAt = clock; ray.setFromCamera(ndc.set(0, 0), camera); const hit = ray.intersectObject(R.group, true)[0]; const want = hit ? Math.max(0.4, Math.min(40, hit.distance)) : 12; focus += (want - focus) * 0.35; }
  function draw(){
    const f = stillOn ? 0 : 1, t = stillOn ? 2.7 : clock, g = gust(t, (SEASONS[season] || SEASONS.summer).wind * S.wind);
    let ey = me.y + me.eye + (stillOn ? 0 : (me.mode === "seated" ? 0.004 * Math.sin(t * 1.35) : 0.006 * Math.sin(t * 1.35) + me.bob * 0.022 * Math.sin(me.phase * Math.PI * 2))), yaw = me.yaw, pitch = me.pitch, roll = 0, ex = me.x, ez = me.z;
    if (!stillOn) { yaw += 0.0012 * Math.sin(t * 0.53 + 1.3) + 0.0004 * Math.sin(t * 1.71); pitch += 0.001 * Math.sin(t * 0.47) + 0.0003 * Math.sin(t * 1.45); roll += 0.0009 * Math.sin(t * 0.33) + me.bob * 0.006 * Math.sin(me.phase * Math.PI); }
    if (rocker && !stillOn) { const seated = me.mode === "seated" && me.seat === "rocker", amp = seated ? 0.07 : 0.0, ang = amp * Math.sin(t * 1.25); rocker.rock.rotation.x += (ang - rocker.rock.rotation.x) * 0.1;
      if (seated) { ez += Math.sin(rocker.rock.rotation.x) * 1.05 * Math.cos(me.yaw); ex += -Math.sin(rocker.rock.rotation.x) * 1.05 * Math.sin(me.yaw); pitch += rocker.rock.rotation.x * 0.9; ey += 0.012 * Math.cos(t * 2.5); if (Math.abs(ang) > amp * 0.985 && !rocker.creaked) { rocker.creaked = true; sound.creak(); } if (Math.abs(ang) < amp * 0.5) rocker.creaked = false; } }
    camera.position.set(ex, ey, ez); camera.rotation.set(pitch, yaw, roll);
    const fl = 0.86 + f * (0.09 * Math.sin(t * 11.3) + 0.06 * Math.sin(t * 23.1 + 1.3) + 0.05 * Math.sin(t * 5.7)) + f * 0.08 * g;
    R.fireLight.intensity = S.fire * fl; R.fireLight.position.x = R.ox - 0.3 + f * 0.03 * Math.sin(t * 7.1); R.hearthGlow.intensity = S.fire * 0.35 * fl; R.fire.tick(t, fl, g);
    VIEW.mat.uniforms.uT.value = t; U.uTime.value = t; dust.material.uniforms.uWind.value = g;
    R.curtainU.uT.value = t; R.curtainU.uAmp.value = f * (0.15 + 0.85 * g);
    if (lantern) lantern.light.intensity = 2.2 * S.lamps * (0.9 + f * 0.1 * Math.sin(t * 9.3 + Math.sin(t * 3.1)));
    if (hands) hands.set(new Date());
    if (R.wet.visible) { R.rainN.offset.y -= f * 0.0009 * (1 + g); }
    WX.tick(f ? Math.min(0.05, clock - drawn) : 0, t, g, season === "winter" && !stillOn, weather === "rain" && !stillOn);
    R.posters.forEach((p, i) => { const pulse = 0.5 + 0.5 * Math.sin(t * 1.7 + i * Math.PI) * f, k = 0.55 + 0.45 * pulse + p.heat * 0.9;
      p.glow.material.opacity = Math.min(1, 0.22 + 0.3 * k) * (0.6 + 0.4 * S.poster); p.glow.scale.setScalar(1 + 0.05 * pulse + 0.1 * p.heat); p.spot.intensity = 6 * S.poster * (0.8 + 0.3 * k); p.light.intensity = 0.8 * S.poster * k; p.tube.material.emissiveIntensity = 2 + 1.5 * k; p.group.scale.setScalar(1 + 0.02 * p.heat); });
    if (R.door.on) { const dr = R.door, pulse = 0.5 + 0.5 * Math.sin(t * 1.4 + 1) * f, k = 0.6 + 0.4 * pulse + dr.heat * 0.9; dr.halo.material.opacity = Math.min(0.6, 0.14 + 0.18 * k); dr.light.intensity = 3.2 * k; dr.seam.color.setScalar(1).multiply(TINT_BACK).multiplyScalar(0.75 + 0.35 * k); }
    { const dd = R.deckDoor; dd.halo.material.opacity = 0.45 * dd.heat; dd.lever.scale.setScalar(1 + 0.15 * dd.heat); }
    if (cut) { const u = clock - cut.t; if (u < 0.32) veilA = u / 0.32; else if (cut.fn) { cut.fn(); cut.fn = null; veilA = 1; } else veilA = Math.max(0, 1 - (u - 0.4) / 0.6); if (u > 1.0) cut = null; } else veilA = 0;
    refocus();
    lens.render(scene, camera, {focus, aper: lite ? 0 : (me.mode === "seated" ? 0.13 : 0.1), expo: S.expo, sat: S.sat, time: t, shaft: U.uShaft.value, haze: S.haze, sunL, veilA, veil: VEIL, bloomK: 0.2 + 0.08 * S.lamps});
    sound.update(camera, fl, g);
    drawn = clock;
  }
  const VEIL = new THREE.Color("#0b0907");
  function frame(now){
    raf = 0; if (dead) return; const dt = Math.min(0.05, last ? (now - last) / 1000 : 0.016); last = now;
    const busy = step(dt); draw();
    if (!stillOn || busy || held.size || stick.on) kick(); else last = 0;      // with motion off the room is drawn only when something changes
  }
  function kick(){ if (!raf && !dead && !document.hidden) raf = requestAnimationFrame(frame); }
  const onVis = () => { last = 0; if (document.hidden) sound.pause(); else sound.resume(); kick(); }, onSize = () => { size(); kick(); };
  on(document, "visibilitychange", onVis); on(window, "resize", onSize); if (window.visibilityState === undefined) { /* nothing */ }
  on(window, "pagehide", e => { if (e.persisted) sound.pause(); });
  on(canvas, "webglcontextlost", e => { e.preventDefault(); opts.onLost && opts.onLost(); });
  setWhen(opts.when || whenNow(), opts.season || seasonNow(), opts.weather);
  /* ready: every file in (or given up on), the room's light taken from the seat, the first frame drawn */
  const readyCheck = () => { if (ready || dead) return; if (!loaded) { setTimeout(readyCheck, 150); return; } applyHour(); draw(); probe(true); draw(); ready = true; opts.onReady && opts.onReady({state: state(), seats: SEATS, hi, lite}); kick(); };
  setTimeout(readyCheck, 50);
  const state = () => ({seat: me.mode === "seated" ? me.seat : null, mode: me.mode, near: me.mode === "walking" ? nearestSeat() : me.seat, level: me.level, when, season, weather, pos: [+me.x.toFixed(2), +me.y.toFixed(2), +me.z.toFixed(2)]});
  const facing = () => ({yaw: me.yaw, pitch: me.pitch});

  return {
    go, look, goBack, goDeck, setWhen, facing, state, seats: SEATS,
    seat(id){ if (!seats[id] || going) return; if (me.mode === "seated" && me.seat === id && !rising) return; sitDown(id); },
    stand: standUp, sit(){ sitDown(null); }, sitting: () => me.mode === "seated",
    setStill(v){ stillOn = !!v; inertia.y = inertia.p = 0; held.clear(); if (stillOn) { R.fire.tick(2.7, 0.9, 0); } kick(); },
    setSound(v){ if (v) { if (!sound.start()) return false; } else sound.stop(); return true; }, soundOn: () => sound.on,
    stick(x, y){ stick.on = !!(x || y); stick.x = x || 0; stick.y = y || 0; kick(); },
    get ready(){ return ready; }, get hi(){ return hi; }, get lite(){ return lite; },
    /* one frame as a picture: view = {seat} or {x, z, yaw, pitch, level, mode} places the visitor; t the moment */
    still(w = 960, h = 600, view = {}){ const keep = Object.assign({}, me), kc = clock; if (view.seat && seats[view.seat]) place(view.seat); const v = Object.assign({}, view); delete v.seat; delete v.noLens; Object.assign(me, v); if (view.level && view.y == null) me.y = floorOf(view.level); if (view.t != null) clock = view.t;
      renderer.setPixelRatio(1); renderer.setSize(w, h, false); lens.size(w, h); camera.aspect = w / h; camera.updateProjectionMatrix(); probe(true);
      if (view.noLens) { camera.position.set(me.x, me.y + me.eye, me.z); camera.rotation.set(me.pitch, me.yaw, 0); renderer.setRenderTarget(null); renderer.render(scene, camera); } else { draw(); draw(); }
      window.__cam = {pos: camera.position.toArray().map(x => +x.toFixed(2)), rot: [camera.rotation.x, camera.rotation.y].map(x => +x.toFixed(2)), fov: +camera.fov.toFixed(1), eye: me.eye, y: me.y, focus: +focus.toFixed(2), shaft: U.uShaft.value, sunL: sunL.toArray().map(x => +x.toFixed(2))};
      const url = canvas.toDataURL("image/jpeg", 0.88);
      if (view.keep) { delete me.keep; going = null; walkTo = null; rising = null; doorCool = clock + 4; size(); kick(); return url; }      /* keep: the visitor stays where the picture put them */
      Object.assign(me, keep); clock = kc; size(); kick(); return url; },
    bench(n = 30){ const gl = renderer.getContext(); draw(); gl.finish(); const t0 = performance.now(); for (let i = 0; i < n; i++) { clock += 0.016; draw(); } gl.finish(); return (performance.now() - t0) / n; },
    loaded(){ return placed; },
    where(){ return {x: me.x, y: me.y, z: me.z, yaw: me.yaw, pitch: me.pitch, level: me.level, mode: me.mode, seat: me.seat}; },
    get scene(){ return scene; }, get lights(){ return {hemi, sun, fire: R.fireLight}; },      /* for checking a frame where frames are not being drawn */
    dispose(){ dead = true; cancelAnimationFrame(raf); ac.abort(); sound.close(); lens.dispose(); cubeRT.dispose(); if (envRT) envRT.dispose(); pm.dispose(); renderer.dispose(); },
  };
}
