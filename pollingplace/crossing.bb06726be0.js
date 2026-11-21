/*
 The polling place: the way into On The Ballot, and a place to sit in (John, 2026-10-11: "a real polling place"; then
 "a space big enough and detailed enough to feel like a set piece from a blockbuster movie ... as if you are literally
 there ... when someone can just enter, sit in a space and enjoy it").

 A school gymnasium on the evening the town votes there. The last half hour of sun comes low through the high west
 windows in long amber shafts, dust turning in them, and lands high on the east wall over the bleachers; the hall's lamps
 are on below. A maple floor with its court lines under a gloss finish that mirrors the room, painted block walls, the
 bleachers pulled out, a basketball hoop, the clock and the dark scoreboard. Flags stand by the check-in table with its
 poll books and beside the ballot scanner; a row of voting booths stands ready; "VOTE HERE" signs show the way. Nobody
 else is there.

 The crossing (ten seconds): you carry your ballot (a generic one: no names, no parties) across the floor to the scanner
 on its ballot box, raise it, feed it into the slot; the rollers take it, the small screen reads it, ticks its count up
 by one and says "Your ballot was counted". Then the room fades into On The Ballot. Your hand is never drawn: the ballot
 rises from where a hand would hold it, and the head moves a little with the pointer.

 The place (as long as you like): you sit where you chose (the bleachers, inside a voting booth, at the check-in table,
 the judge's chair by the scanner, or just inside the doors), look around by dragging, by touch or with the arrow keys,
 get up and walk the gym (the walking keys on a computer, a thumb control on a phone; never through a wall or a chair),
 and sit again. Its sound (the gym's hum and its echo, the clock, the scanner's fan, a flag's rope against its pole
 outside, a door far off, your own steps) is made on the device with Web Audio and stays off until the reader turns it
 on. The sun sinks as the real one would, so the room changes slowly while you sit. Nothing about the reader is used or sent.

 What it is drawn from: the floor from "Wood Floor 047", the walls' paint from "Painted Plaster 017" and the cloth's
 weave from "Fabric 036" (ambientCG, CC0); the chairs from Poly Haven's "School Chair 01" (Ethan Place), the clock from
 its "Wall Clock" (PierreB3D), and in the place also its "Metal Trash Can" (GurJas Studios), "Clipboard"
 (ProgrammerOnCoffee), "Binder Notebook" (DaDrood) and "Plastic Broom" (L), all CC0, and the sky outside the windows
 from its "Qwantani Dusk 2" (pure sky, CC0); the rest is drawn here. Every maker's mark on a model was painted out.

 Uses three.js (MIT licence), kept with the site.
   prepare()               fetch the crossing's files (on the first hover, focus or tap of a way into On The Ballot),
                           then, while the reader decides, set the room up and have the graphics card ready it
                           (prepare({warm: false}) only fetches)
   loadMore(urls)          the place's own files on top of them (the materials at 2K, the sky, the models), by address
   supported()             can this device draw it
   run(url, opts)          play the crossing over the page, then go to url; false when it cannot be drawn, else {skip, stay}
                           opts.host  the element to draw into; opts.assets  what prepare() gave; opts.still  one still
                           picture, then a fade; opts.lean  the light version; opts.fade  called just before a still
                           picture fades; opts.from, opts.to  the colours it fades in from and out to; opts.arrive  the
                           sessionStorage key that tells the next page how it was reached; opts.go(how)  called at the end
                           instead of going to url ("full", "skip", "still" or "quick"); opts.stay  the place's own page:
                           the view is handed over (this tab only) and the reader goes there instead; opts.hold()  true
                           while the reader reaches for Stay (the end waits a little); opts.keys false  the caller keeps
                           the keyboard
   watch(canvas, opts)     the place: a controller for the page (seats, walking, looking, sound, motion), or null
   still(t, w, h, opts)    one frame as a JPEG data URL (opts.png: a PNG), for checking a scene where frames are not drawn
                           (a Promise); opts.watch with opts.seat (and opts.look, opts.walkTo) draws the place instead
   facts()                 what the scene shows (a Promise)
*/
import * as THREE from "../vendor/three.module.min.js";
import {GLTFLoader} from "../vendor/jsm/loaders/GLTFLoader.js";
import {mergeGeometries} from "../vendor/jsm/utils/BufferGeometryUtils.js";

const FILES = {"floor_diff":"floor_diff.95b6352193.jpg","floor_nor":"floor_nor.684558a8ac.jpg","floor_rough":"floor_rough.7c31823f1a.jpg","wall_diff":"wall_diff.a80aa74ca9.jpg","wall_nor":"wall_nor.fc379d6b0f.jpg","fabric_nor":"fabric_nor.04de059785.jpg","chair":"chair.b0029299b8.glb","clock":"clock.cb96f0948b.glb"};
const asset = k => FILES[k] ? new URL(FILES[k], import.meta.url).href : null;
const DUR = 10.0, STILL_T = 8.75, PAGE = "#F5F5F2";
const D2R = Math.PI / 180;
const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
const seg = (t, a, b) => clamp((t - a) / (b - a));
const smooth = x => x * x * (3 - 2 * x);
const inOut = x => x < .5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2;
const mix = (a, b, t) => a + (b - a) * t;
const V3 = (x = 0, y = 0, z = 0) => new THREE.Vector3(x, y, z);
function rng(seed){ let a = seed >>> 0; return () => { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
const pt = {x: 0, y: 0, sx: 0, sy: 0};      // the pointer, -1 to 1 across the window; sx, sy follow it slowly, as a head does
addEventListener("pointermove", e => { pt.x = e.clientX / innerWidth * 2 - 1; pt.y = e.clientY / innerHeight * 2 - 1; }, {passive: true});
/* the look: exposure and tone, the lamps' and the sun's strength, the lens (glow, grain, depth of field), the air (the
   shafts' density, the dust) and the grade; a check may try other values through opts.look */
const LOOK0 = {exposure: 0.92, tone: "ACESFilmicToneMapping", lens: 26, spot: 44, point: 9, hemi: 0.28, env: 0.9, sun: 6.8, sky: 16.0, glow: 0.2, grain: 0.011,
               coat: 0.9, cc: 0.1, lod: 1.0, paint: [222, 215, 198], shaft: 0.06, dust: 0.55, ao: 0.7, dof: 0.0055, grade: 1.0, vignette: 0.3, ca: 1.0};
/* the sun: how high it stands as the scene opens (degrees), and how it sinks while the reader sits (degrees a minute of
   the place's own clock); the clock on the wall as the scene opens */
const SUN = {alt0: 4.2, sink: 0.17, az: -42, hour: 16, minute: 40};

/* ================================ the files, and the room made ready while the reader decides ================================ */
let loading = null, ready = null, warm = null, warming = false, playing = false;
const STATS = {frames: 0, slow: 0, worst: 0, wait: 0};      // how the last playing went, for checking (facts() reports it)
function image(url){ return new Promise((ok, no) => { const im = new Image(); im.decoding = "async"; im.onload = () => ok(im); im.onerror = () => no(new Error("could not load " + url)); im.src = url; }); }
const model = url => url ? new GLTFLoader().loadAsync(url).then(g => g.scene).catch(() => null) : Promise.resolve(null);
export function prepare(o = {}){
  if (!loading) {
    const img = k => asset(k) ? image(asset(k)).catch(() => null) : Promise.resolve(null);
    loading = Promise.all([img("floor_diff"), img("floor_nor"), img("floor_rough"), img("wall_diff"), img("wall_nor"), img("fabric_nor"), model(asset("chair")), model(asset("clock"))])
      .then(([fd, fn, fr, wd, wn, cn, chair, clock]) => (ready = {floor: [fd, fn, fr], wall: [wd, wn], cloth: cn, chair, clock}));
    loading.catch(() => { loading = null; });
  }
  /* the room is made ready once, while the reader decides; it is let go after a minute unused (a later call makes it again) */
  if (o.warm !== false && !warm && !warming && !playing) {
    warming = true;
    loading.then(A => setTimeout(() => {
      warming = false; if (warm || playing) return;
      try { if (!supported()) return; const st = stage(A, innerWidth, innerHeight, {lean: leanNow()}); warm = st;
        st.timer = setTimeout(() => { if (warm === st) { warm = null; drop(st); } }, 60000); } catch (e) { warm = null; }
    }, 30), () => { warming = false; });
  }
  return loading;
}
/* the place's own files, by address (the page gives them): floor and wall at 2K, the sky, the models; a missing one is
   simply not used */
export function loadMore(urls = {}){
  const img = u => u ? image(u).catch(() => null) : Promise.resolve(null);
  return Promise.all([img(urls.floor_diff), img(urls.floor_nor), img(urls.floor_rough), img(urls.wall_diff), img(urls.wall_nor), img(urls.sky),
                      model(urls.bin), model(urls.clipboard), model(urls.binder), model(urls.broom)])
    .then(([fd, fn, fr, wd, wn, sky, bin, clipboard, binder, broom]) => ({floor: fd || fn || fr ? [fd, fn, fr] : null, wall: wd || wn ? [wd, wn] : null, sky, bin, clipboard, binder, broom}));
}
let can = null;
export function supported(){      /* asked once; the context asked with is let go at once */
  if (can === null) { try { const c = document.createElement("canvas"), g = window.WebGL2RenderingContext && c.getContext("webgl2"); can = !!g;
    if (g) { const x = g.getExtension("WEBGL_lose_context"); if (x) x.loseContext(); } } catch (e) { can = false; } }
  return can;
}
/* the way in decides lean or not as this does: the page says so, or the device has little memory or few cores */
function leanNow(){
  const v = document.documentElement.getAttribute("data-lean"); if (v) return v === "on";
  try { const n = navigator; return !!((n.deviceMemory && n.deviceMemory < 4) || (n.hardwareConcurrency && n.hardwareConcurrency <= 4)); } catch (e) { return false; }
}

/* ================================ helpers ================================ */
function texOf(img, srgb, aniso = 8){
  if (!img) return null;
  const t = new THREE.Texture(img); t.needsUpdate = true; if (srgb) t.colorSpace = THREE.SRGBColorSpace;
  t.wrapS = t.wrapT = THREE.RepeatWrapping; t.anisotropy = aniso; return t;
}
function canvasTex(w, h, draw, o = {}){
  const c = document.createElement("canvas"); c.width = w; c.height = h; draw(c.getContext("2d"), w, h);
  const t = new THREE.CanvasTexture(c); if (o.srgb !== false) t.colorSpace = THREE.SRGBColorSpace;
  if (o.repeat) t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.anisotropy = o.aniso || 8; return t;
}
function pixels(img, w, h){
  const c = document.createElement("canvas"); c.width = w; c.height = h; const g = c.getContext("2d", {willReadFrequently: true});
  g.drawImage(img, 0, 0, w, h); return g.getImageData(0, 0, w, h).data;
}
const SANS = '"Helvetica Neue", Arial, "Segoe UI", system-ui, sans-serif';
function say(g, s, x, y, font, color, align = "center", base = "middle"){ g.font = font; g.fillStyle = color; g.textAlign = align; g.textBaseline = base; g.fillText(s, x, y); }
function rrect(g, x, y, w, h, r){ g.beginPath(); g.moveTo(x + r, y); g.arcTo(x + w, y, x + w, y + h, r); g.arcTo(x + w, y + h, x, y + h, r); g.arcTo(x, y + h, x, y, r); g.arcTo(x, y, x + w, y, r); g.closePath(); }
function star(g, x, y, r){ g.beginPath(); for (let i = 0; i < 10; i++) { const a = -Math.PI / 2 + i * Math.PI / 5, q = i % 2 ? r * .382 : r; g.lineTo(x + q * Math.cos(a), y + q * Math.sin(a)); } g.closePath(); g.fill(); }
/* the flag of the United States in its own colours, drawn into (x, y, w, h); the union is 7/13 of the hoist by two fifths of the fly */
function usFlag(g, x, y, w, h){
  for (let i = 0; i < 13; i++) { g.fillStyle = i % 2 ? "#FFFFFF" : "#B22234"; g.fillRect(x, y + i * h / 13, w, h / 13 + 0.6); }
  const cw = w * 0.4, ch = h * 7 / 13; g.fillStyle = "#3C3B6E"; g.fillRect(x, y, cw, ch); g.fillStyle = "#FFFFFF";
  for (let r = 0; r < 9; r++) for (let c = 0; c < (r % 2 ? 5 : 6); c++) star(g, x + cw * ((r % 2 ? 2 : 1) + c * 2) / 12, y + ch * (r + 1) / 10, h * 0.0308);
}
/* wear: a faint, uneven tone laid over a printed thing (paper handled, paint rubbed), from a seeded noise */
function wear(g, w, h, seed, k = 0.08){
  const r = rng(seed); g.save(); g.globalAlpha = k;
  for (let i = 0; i < 260; i++) { const x = r() * w, y = r() * h, rad = (0.05 + r() * 0.25) * Math.max(w, h); const gr = g.createRadialGradient(x, y, 0, x, y, rad);
    const dark = r() < 0.55; gr.addColorStop(0, dark ? "rgba(40,30,20,1)" : "rgba(255,250,240,1)"); gr.addColorStop(1, "rgba(0,0,0,0)"); g.fillStyle = gr; g.fillRect(x - rad, y - rad, 2 * rad, 2 * rad); }
  g.restore();
}
/* a box with rounded edges and corners (as three.js's RoundedBoxGeometry builds one) */
function roundBox(w, h, d, r, s = 3){
  const n = s * 2 + 1, g = new THREE.BoxGeometry(1, 1, 1, n, n, n), p = g.attributes.position, nm = g.attributes.normal, half = 0.5 / n;
  r = Math.min(r, w / 2, h / 2, d / 2); const bx = w / 2 - r, by = h / 2 - r, bz = d / 2 - r, v = V3();
  for (let i = 0; i < p.count; i++) {
    v.set(p.getX(i), p.getY(i), p.getZ(i)); const sx = Math.sign(v.x), sy = Math.sign(v.y), sz = Math.sign(v.z);
    v.x -= sx * half; v.y -= sy * half; v.z -= sz * half; v.normalize();
    p.setXYZ(i, bx * sx + v.x * r, by * sy + v.y * r, bz * sz + v.z * r); nm.setXYZ(i, v.x, v.y, v.z);
  }
  return g;
}
/* static meshes are merged, one draw per material */
class Batches {
  constructor(){ this.m = new Map(); }
  add(mesh){ mesh.updateWorldMatrix(true, false); const k = mesh.material; if (!this.m.has(k)) this.m.set(k, []);
    const g = mesh.geometry.clone(); g.applyMatrix4(mesh.matrixWorld);
    for (const a of Object.keys(g.attributes)) if (!["position", "normal", "uv"].includes(a)) g.deleteAttribute(a);
    if (!g.attributes.uv) g.setAttribute("uv", new THREE.Float32BufferAttribute(new Float32Array(g.attributes.position.count * 2), 2));
    this.m.get(k).push(g); }
  bake(root){ root.updateMatrixWorld(true); const done = []; root.traverse(o => { if (o.isMesh && !o.userData.keep) { this.add(o); done.push(o); } }); for (const o of done) o.parent.remove(o); }
  build(parent){
    for (const [mat, list] of this.m) {
      const all = list.every(g => g.index) ? list : list.map(g => g.index ? g.toNonIndexed() : g);
      const g = mergeGeometries(all, false); if (!g) continue;
      const mesh = new THREE.Mesh(g, mat); mesh.castShadow = !mat.userData.noCast; mesh.receiveShadow = true;
      mesh.matrixAutoUpdate = false; parent.add(mesh);
    }
    this.m.clear();
  }
}
function part(parent, geo, mat, x = 0, y = 0, z = 0, rx = 0, ry = 0, rz = 0){
  const m = new THREE.Mesh(geo, mat); m.position.set(x, y, z); m.rotation.set(rx, ry, rz); m.castShadow = m.receiveShadow = true; parent.add(m); return m;
}
const BOX = (w, h, d) => new THREE.BoxGeometry(w, h, d);
const CYL = (r0, r1, h, n = 16, open = false) => new THREE.CylinderGeometry(r0, r1, h, n, 1, open);
function tube(parent, mat, a, b, r, n = 8){      // a round bar from a to b
  const d = b.clone().sub(a), m = new THREE.Mesh(CYL(r, r, d.length(), n), mat);
  m.position.copy(a).add(b).multiplyScalar(0.5); m.quaternion.setFromUnitVectors(V3(0, 1, 0), d.normalize()); parent.add(m); return m;
}
/* a model from the files, placed; its materials get the room's light, and a scale if it needs one */
function placeModel(scene, src, x, y, z, ry = 0, scale = 1, shadow = true){
  if (!src) return null;
  const m = src.clone(true); m.position.set(x, y, z); m.rotation.y = ry; m.scale.setScalar(scale);
  m.traverse(o => { if (o.isMesh) { o.castShadow = shadow; o.receiveShadow = true; if (o.material && o.material.map) o.material.map.anisotropy = 8; } });
  scene.add(m); return m;
}

/* ================================ the room ================================ */
const RX = 9.6, ZF = -12.2, ZB = 14.0, HC = 8.4;      // the gym's half width, its far and back walls, the roof deck's height (metres)
const WIN = {y0: 4.05, y1: 6.25, w: 3.1, z: [-8.6, -4.3, 0, 4.3, 8.6]};      // the high windows in the west wall
const WINF = {y0: 6.45, y1: 7.6, w: 2.6, x: [-6.4, -2.2, 2.2, 6.4]};      // and a row high in the far wall
const COURT = {base: -10.6, side: 7.62, mid: 3.73, ft: -4.81, basket: -9.0, board: -9.38, lane: 2.44, r3: 6.02, rc: 1.83, line: 0.051};
const SCAN = {x: 0, z: -2.75, front: -2.47, slotY: 0.926};
const SLOT = V3(SCAN.x, SCAN.slotY, SCAN.front + 0.001), FEED = V3(0, -Math.sin(6 * D2R), -Math.cos(6 * D2R));      // the slot's mouth, and the way a ballot goes in
const SCREEN = V3(0, 1.071, -2.587);      // the middle of the scanner's screen
const BOOTHS = [2.15, 1.2, 0.25, -0.7, -1.65].map(z => ({x: 2.55, z}));
const TABLE = {x: -2.35, z: 1.35};
const FLAGS = [[-1.36, -3.08, 0.22, 3], [-3.4, -0.15, 0.55, 7]];
const SIGN = {x: 1.3, z: 1.1, r: -0.25};
const JUDGE = {x: 1.75, z: -4.25};
const BLEACH = {z0: -7.6, z1: 8.4, rows: 6, tread: 0.76, rise: 0.285, seat: 0.42};      // the bleachers, pulled out along the east wall
const bleachFront = i => RX - BLEACH.tread * (BLEACH.rows - i);      // the front edge of row i's footboard (row 0 at the floor)
const DOORB = {x: -1.3};      // the doors you came in by, in the back wall
/* where a reader can sit (John, 2026-10-11): the eye's place, which way it faces, and where you stand when you get up */
export const SEATS = [
  {id: "bleachers", name: "The bleachers", where: "the third row of the bleachers, across the floor from the booths",
   eye: [bleachFront(2) + BLEACH.tread - 0.15, 2 * BLEACH.rise + BLEACH.seat + 0.78, 0.9], yaw: 90, pitch: -6, stand: [bleachFront(0) - 0.55, 0, 0.9], sat: "bench"},
  {id: "booth", name: "A voting booth", where: "standing inside the middle voting booth, your ballot on its shelf",
   eye: [BOOTHS[2].x + 0.42, 1.62, BOOTHS[2].z], yaw: 90, pitch: -44, stand: [BOOTHS[2].x + 0.62, 0, BOOTHS[2].z], standing: true, sat: ""},
  {id: "table", name: "The check-in table", where: "a poll worker's chair behind the check-in table, the poll books in front of you",
   eye: [TABLE.x - 0.66, 1.22, TABLE.z - 0.45], yaw: -90, pitch: -8, stand: [TABLE.x - 1.25, 0, TABLE.z - 0.45], sat: "chair"},
  {id: "judge", name: "The chair by the scanner", where: "the election judge's chair beside the ballot scanner, facing the doors",
   eye: [JUDGE.x + 0.02, 1.22, JUDGE.z + 0.02], yaw: 160, pitch: -4, stand: [JUDGE.x + 0.55, 0, JUDGE.z + 0.45], sat: "chair"},
  {id: "doors", name: "Just inside the doors", where: "standing just inside the doors, the whole gym in front of you",
   eye: [0.36, 1.62, 6.2], yaw: 0, pitch: -3, stand: [0.36, 0, 6.2], standing: true, sat: ""}
];

/* the painted concrete block: 400 by 200 mm blocks in running bond with concave joints, the paint's own texture from a
   photograph; 2.4 m of wall in one tile */
function blockWall(wallImgs, N, paint){
  const S = 2.4, BW = N / 6, BH = N / 12, J = 0.0095 * N / S, M = Math.min(N, 1024);
  const wd = wallImgs[0] ? pixels(wallImgs[0], M, M) : null, wn = wallImgs[1] ? pixels(wallImgs[1], M, M) : null;
  const R = rng(11), tone = Array.from({length: 72}, () => 0.975 + 0.045 * R());
  let mean = 0; if (wd) { for (let i = 0; i < M * M; i++) mean += wd[i * 4] + wd[i * 4 + 1] + wd[i * 4 + 2]; mean /= M * M * 3; }
  const H = new Float32Array(N * N), id = new Uint8Array(N * N);
  const prof = d => { const k = d / (J * 0.5 + 1.2); return k >= 1 ? 0 : -Math.cos(k * Math.PI / 2); };
  for (let y = 0; y < N; y++) {
    const row = Math.floor(y / BH), yy = y + 0.5 - row * BH, dy = Math.min(yy, BH - yy), off = (row % 2) * BW / 2;
    for (let x = 0; x < N; x++) {
      const xs = (x + 0.5 + off) % N, col = Math.floor(xs / BW), xx = xs - col * BW, dx = Math.min(xx, BW - xx);
      H[y * N + x] = Math.min(prof(dx), prof(dy)); id[y * N + x] = (row * 6 + col) % 72;
    }
  }
  const cc = document.createElement("canvas"); cc.width = cc.height = N; const cg = cc.getContext("2d"), C = cg.createImageData(N, N);
  const nc = document.createElement("canvas"); nc.width = nc.height = N; const ng = nc.getContext("2d"), NN = ng.createImageData(N, N);
  const base = paint, depth = 1.4, sc = M / N;      // the paint, a warm off-white; the joints' depth, in pixels
  const R2 = rng(23); const scuff = new Float32Array(N);      /* a rubbed band low on the wall, where chairs and balls have been */
  for (let x = 0; x < N; x++) scuff[x] = R2();
  for (let y = 0; y < N; y++) for (let x = 0; x < N; x++) {
    const i = y * N + x, h = H[i], q = (((y * sc) | 0) * M + ((x * sc) | 0)) * 4;
    const hx = H[y * N + (x + 1) % N] - H[y * N + (x + N - 1) % N], hy = H[((y + 1) % N) * N + x] - H[((y + N - 1) % N) * N + x];
    let lum = 1; if (wd) lum = 1 + ((wd[q] + wd[q + 1] + wd[q + 2]) / 3 / mean - 1) * 0.5;
    const k = tone[id[i]] * lum * (1 + 0.2 * h);
    C.data[i * 4] = clamp(base[0] * k, 0, 255); C.data[i * 4 + 1] = clamp(base[1] * k, 0, 255); C.data[i * 4 + 2] = clamp(base[2] * k, 0, 255); C.data[i * 4 + 3] = 255;
    let nx = -hx * depth * 0.5, ny = hy * depth * 0.5;
    if (wn) { nx += (wn[q] / 127.5 - 1) * 0.8; ny += (wn[q + 1] / 127.5 - 1) * 0.8; }
    const l = Math.hypot(nx, ny, 1);
    NN.data[i * 4] = (nx / l * 0.5 + 0.5) * 255; NN.data[i * 4 + 1] = (ny / l * 0.5 + 0.5) * 255; NN.data[i * 4 + 2] = (1 / l * 0.5 + 0.5) * 255; NN.data[i * 4 + 3] = 255;
  }
  cg.putImageData(C, 0, 0); ng.putImageData(NN, 0, 0);
  const map = new THREE.CanvasTexture(cc), nor = new THREE.CanvasTexture(nc);
  map.colorSpace = THREE.SRGBColorSpace;
  for (const t of [map, nor]) { t.wrapS = t.wrapT = THREE.RepeatWrapping; t.anisotropy = 8; }
  return {map, nor};
}
/* a rectangle of wall in the plane of `wall` (origin o, along u, facing n), from a0 to a1 along it and y0 to y1 up,
   with its texture laid in metres so the courses run on from piece to piece */
function wallRect(B, mat, wall, a0, a1, y0, y1, tile = 2.4){
  const w = a1 - a0, h = y1 - y0, g = new THREE.PlaneGeometry(w, h), uv = g.attributes.uv;
  for (let i = 0; i < uv.count; i++) uv.setXY(i, (a0 + uv.getX(i) * w) / tile, (y0 + uv.getY(i) * h) / tile);
  const m = new THREE.Mesh(g, mat), basis = new THREE.Matrix4().makeBasis(wall.u, V3(0, 1, 0), wall.n);
  m.quaternion.setFromRotationMatrix(basis); m.position.copy(wall.o).addScaledVector(wall.u, (a0 + a1) / 2).addScaledVector(V3(0, 1, 0), (y0 + y1) / 2);
  B.add(m); return m;
}
const QUAD_VERT = "varying vec2 vUv; void main(){ vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }";
/* the sun's direction (the way its light travels) for an altitude in degrees: from the south-west, so its light crosses the
   gym from the west windows to the far wall (az: degrees toward the far wall, negative z) */
function sunDir(alt){ const a = alt * D2R, z = SUN.az * D2R; return V3(Math.cos(a) * Math.cos(z), -Math.sin(a), Math.cos(a) * Math.sin(z)).normalize(); }
/* the sun's colour and strength as it sinks: amber, then red, then gone a little after it touches the horizon */
function sunLight(alt){
  const k = smooth(seg(alt, -0.6, 2.5)), red = 1 - smooth(seg(alt, 0.8, 5.0));
  return {k, color: new THREE.Color(1.0, mix(0.55, 0.36, red), mix(0.22, 0.10, red))};
}
/* the sky's brightness as the sun goes: full while it is up, falling through the blue hour */
const skyK = alt => mix(0.22, 1.0, smooth(seg(alt, -8, 1.5)));

/* ================================ the scene ================================ */
function build(renderer, A, opts = {}){
  const LOOK = Object.assign({}, LOOK0, opts.look || {});      // a check may try other values
  const lean = !!opts.lean, ST = {still: !!opts.still}, more = opts.more || {}, place = !!opts.watch;
  renderer.toneMappingExposure = LOOK.exposure; if (LOOK.tone) renderer.toneMapping = THREE[LOOK.tone];
  const scene = new THREE.Scene(); scene.background = new THREE.Color("#0b0b0c");
  const cam = new THREE.PerspectiveCamera(50, 1.6, 0.03, 90); scene.add(cam);
  let aspect = 1.6;
  const B = new Batches(), dyn = new THREE.Group(); scene.add(dyn);
  const aniso = Math.min(16, renderer.capabilities.getMaxAnisotropy());
  const obstacles = [];      // what a walking reader cannot pass through: {x, z, w, d, r} boxes (r: turned by r about y) and {x, z, rad} posts
  const block = (x, z, w, d, r = 0) => obstacles.push({x, z, w, d, r});
  const post = (x, z, rad) => obstacles.push({x, z, rad});

  /* ---------- materials (few kinds, so the graphics card has few programs to make) ---------- */
  const std = o => new THREE.MeshStandardMaterial(o);
  const wallT = blockWall(more.wall || A.wall, lean ? 512 : (more.wall ? 2048 : 1024), LOOK.paint);
  const wallMat = std({map: wallT.map, normalMap: wallT.nor, normalScale: new THREE.Vector2(0.9, 0.9), roughness: 0.62});
  const bandMat = std({color: "#3E6A55", map: wallT.map, normalMap: wallT.nor, normalScale: new THREE.Vector2(0.9, 0.9), roughness: 0.5});
  /* the lamps hang low and point down: the walls get less of their light toward the roof, and the corner at the floor less again */
  const wallFall = sh => {
    sh.vertexShader = sh.vertexShader.replace("#include <common>", "#include <common>\nvarying float vWy;").replace("#include <fog_vertex>", "#include <fog_vertex>\nvWy = (modelMatrix * vec4(transformed, 1.0)).y;");
    sh.fragmentShader = sh.fragmentShader.replace("#include <common>", "#include <common>\nvarying float vWy;").replace("#include <aomap_fragment>",
      "#include <aomap_fragment>\n{ float k = mix(1.0, 0.55, smoothstep(2.6, 8.2, vWy)) * mix(0.8, 1.0, smoothstep(0.0, 1.0, vWy)); reflectedLight.indirectDiffuse *= k; reflectedLight.indirectSpecular *= k; }");
  };
  for (const m of [wallMat, bandMat]) { m.onBeforeCompile = wallFall; m.customProgramCacheKey = () => "polling-wall"; }
  const baseMat = std({color: "#1B1C1D", roughness: 0.55});
  const deckMat = std({color: "#A3A39D", roughness: 0.7});
  /* metals get a little unevenness, from a small noise: no surface is one flat tone */
  const metalNoise = canvasTex(256, 256, (g, w, h) => { const r = rng(5); g.fillStyle = "#808080"; g.fillRect(0, 0, w, h);
    for (let i = 0; i < 2600; i++) { const v = 100 + (r() * 80) | 0; g.fillStyle = `rgba(${v},${v},${v},0.5)`; g.fillRect(r() * w, r() * h, 1 + r() * 10, 1 + r() * 3); } }, {srgb: false, repeat: true});
  const steelMat = std({color: "#B9BAB4", roughness: 0.55, metalness: 0.35, roughnessMap: metalNoise});
  const darkSteel = std({color: "#34383C", roughness: 0.5, metalness: 0.5, roughnessMap: metalNoise});
  const alu = std({color: "#C7CBCF", roughness: 0.32, metalness: 0.9, roughnessMap: metalNoise});
  const bronze = std({color: "#2C2721", roughness: 0.45, metalness: 0.6});
  const duct = std({color: "#AEB3B7", roughness: 0.38, metalness: 0.85, roughnessMap: metalNoise});
  const lensMat = new THREE.MeshBasicMaterial({color: new THREE.Color(1.0, 0.93, 0.80).multiplyScalar(LOOK.lens)}); lensMat.userData.noCast = true;
  const floorImgs = more.floor || A.floor;
  const maple = floorImgs[0] ? texOf(floorImgs[0], true, aniso) : null;
  const padMat = std({color: "#203A2E", roughness: 0.42});
  const clothNor = A.cloth ? texOf(A.cloth, false, aniso) : null;
  const paper = std({color: "#F6F5F0", roughness: 0.92});
  const white = std({color: "#EEEEEA", roughness: 0.55});
  const ink = std({color: "#151617", roughness: 0.6});
  const glassMat = std({color: "#9EB0B6", roughness: 0.04, metalness: 0.1, transparent: true, opacity: 0.16, envMapIntensity: 1.5, depthWrite: false});
  glassMat.userData.noCast = true;
  const basic = (c, k = 1) => new THREE.MeshBasicMaterial({color: new THREE.Color(c).multiplyScalar(k)});

  /* ---------- the floor: maple strips under a gloss finish, with the court painted on ---------- */
  const FU = {uRefl: {value: null}, uTexMat: {value: new THREE.Matrix4()}, uReflOn: {value: 0}, uReflTexel: {value: new THREE.Vector2(1 / 640, 1 / 360)}, uLod: {value: LOOK.lod},
              uAO: {value: null}, uAOBox: {value: new THREE.Vector4(-6, -6, 12, 12.5)}};
  const floorMat = new THREE.MeshPhysicalMaterial({color: "#F2DDBD", roughness: 0.62, clearcoat: LOOK.coat, clearcoatRoughness: LOOK.cc, envMapIntensity: 0.6});
  if (floorImgs[0]) floorMat.map = texOf(floorImgs[0], true, aniso);
  if (floorImgs[1]) { floorMat.normalMap = texOf(floorImgs[1], false, aniso); floorMat.normalScale.set(0.5, 0.5); }
  if (floorImgs[2]) { floorMat.roughnessMap = texOf(floorImgs[2], false, aniso); floorMat.roughness = 1.15; }
  const C = COURT, f2 = x => x.toFixed(3);
  floorMat.onBeforeCompile = sh => {
    Object.assign(sh.uniforms, FU);
    sh.vertexShader = sh.vertexShader.replace("#include <common>", "#include <common>\nuniform mat4 uTexMat;\nvarying vec4 vMir;\nvarying vec3 vWp;")
      .replace("#include <fog_vertex>", "#include <fog_vertex>\n{ vec4 wq = modelMatrix * vec4(transformed, 1.0); vWp = wq.xyz; vMir = uTexMat * wq; }");
    sh.fragmentShader = sh.fragmentShader.replace("#include <common>", `#include <common>
      uniform sampler2D uRefl, uAO; uniform float uReflOn, uLod; uniform vec2 uReflTexel; uniform vec4 uAOBox;
      varying vec4 vMir; varying vec3 vWp;
      float lineK(float d, float w){ float f = max(fwidth(d), 1e-4) * 0.8; return 1.0 - smoothstep(w * 0.5 - f, w * 0.5 + f, abs(d)); }`)
      .replace("#include <map_fragment>", `#include <map_fragment>
      {
        vec2 p = vWp.xz; float W = ${f2(C.line)}, hw = W * 0.5;
        float inX = step(abs(p.x), ${f2(C.side)}), L = 0.0;
        L = max(L, lineK(abs(p.x) - ${f2(C.side)} + hw, W) * step(${f2(C.base)}, p.y));
        L = max(L, lineK(p.y - (${f2(C.base)} + hw), W) * inX);
        L = max(L, lineK(p.y - ${f2(C.mid)}, W) * inX);
        L = max(L, lineK(length(p - vec2(0.0, ${f2(C.mid)})) - ${f2(C.rc)} + hw, W));
        float inLane = step(${f2(C.base)}, p.y) * step(p.y, ${f2(C.ft)});
        L = max(L, lineK(abs(p.x) - ${f2(C.lane)} + hw, W) * inLane);
        L = max(L, lineK(p.y - ${f2(C.ft)}, W) * step(abs(p.x), ${f2(C.lane)}));
        L = max(L, lineK(length(p - vec2(0.0, ${f2(C.ft)})) - ${f2(C.rc)} + hw, W) * step(${f2(C.ft)}, p.y));
        L = max(L, lineK(length(p - vec2(0.0, ${f2(C.basket)})) - ${f2(C.r3)} + hw, W) * step(${f2(C.basket)}, p.y));
        L = max(L, lineK(abs(p.x) - ${f2(C.r3)} + hw, W) * step(p.y, ${f2(C.basket)}) * step(${f2(C.base)}, p.y));
        for (int i = 0; i < 4; i++) { float zc = ${f2(C.base + 2.13)} + float(i) * 0.91; L = max(L, step(abs(p.y - zc), 0.025) * step(abs(abs(p.x) - ${f2(C.lane + 0.1)}), 0.1)); }
        float lane = step(abs(p.x), ${f2(C.lane - C.line)}) * step(${f2(C.base + C.line)}, p.y) * step(p.y, ${f2(C.ft - C.line / 2)});
        float centre = step(length(p - vec2(0.0, ${f2(C.mid)})), ${f2(C.rc - C.line)});
        float wood = dot(diffuseColor.rgb, vec3(0.3333));
        vec3 stain = vec3(0.075, 0.175, 0.105) * (0.4 + 1.2 * wood);      /* a green stain, the grain showing through */
        diffuseColor.rgb = mix(diffuseColor.rgb, stain, max(lane, centre) * 0.8);
        diffuseColor.rgb = mix(diffuseColor.rgb, vec3(0.010, 0.010, 0.011), L * 0.92);
        float sc = 0.0; vec2 ci = floor(p / 0.7);      /* the black scuffs rubber soles leave, here and there */
        for (int j = -1; j <= 1; j++) for (int i = -1; i <= 1; i++) {
          vec2 c = ci + vec2(float(i), float(j)); float h = fract(sin(dot(c, vec2(127.1, 311.7))) * 43758.5453);
          if (h < 0.3) { vec2 q = p - (c + vec2(fract(h * 13.7), fract(h * 71.3))) * 0.7; float a = h * 62.8; vec2 dir = vec2(cos(a), sin(a));
            float al = dot(q, dir), ac = dot(q, vec2(-dir.y, dir.x)), len = 0.05 + 0.13 * fract(h * 7.1); ac -= 1.6 * al * al;
            float d = length(vec2(max(abs(al) - len, 0.0), ac)); sc = max(sc, (1.0 - smoothstep(0.003, 0.011, d)) * (0.3 + 0.5 * fract(h * 3.3))); }
        }
        diffuseColor.rgb *= 1.0 - 0.3 * sc;
        /* the finish is worn where feet go most: a paler, duller track from the doors to the booths and the table */
        float track = smoothstep(2.2, 0.0, abs(p.x - 0.3 - 0.9 * smoothstep(-3.0, 4.0, p.y))) * smoothstep(-6.0, 2.0, p.y) * 0.5
                    + smoothstep(1.6, 0.0, length(p - vec2(0.0, -2.0))) * 0.4;
        diffuseColor.rgb = mix(diffuseColor.rgb, diffuseColor.rgb * vec3(0.97, 0.96, 0.95) + 0.02, track * 0.5);
      }`)
      .replace("#include <lights_fragment_maps>", `#include <lights_fragment_maps>
      #ifdef USE_CLEARCOAT
      if (uReflOn > 0.5) {      /* the finish mirrors the room: what the mirrored camera saw, softened a little */
        vec2 muv = vMir.xy / vMir.w;
        vec3 nf = normalize((viewMatrix * vec4(0.0, 1.0, 0.0, 0.0)).xyz);
        muv += (normal.xy - nf.xy) * 0.035;
        vec3 acc = vec3(0.0), str = vec3(0.0); float ws = 0.0, ss = 0.0;
        for (int i = -2; i <= 2; i++) { float fi = float(i), wt = exp(-fi * fi / 3.0);
          acc += textureLod(uRefl, muv + vec2(0.0, fi * uReflTexel.y * 1.5), uLod).rgb * wt; ws += wt; }
        for (int i = -4; i <= 4; i++) { float fi = float(i), wt = exp(-fi * fi / 9.0);      /* the finish draws bright things out into streaks toward you */
          str += textureLod(uRefl, muv + vec2(0.0, fi * uReflTexel.y * 7.0), uLod + 1.5).rgb * wt; ss += wt; }
        str /= ss;
        float hot = smoothstep(0.3, 2.0, max(str.r, max(str.g, str.b)));
        clearcoatRadiance = mix(acc / ws, str, mix(0.45, 0.9, hot));
      } else clearcoatRadiance = min(clearcoatRadiance, vec3(0.9));      /* without the mirror, the room's light from its middle: no lamp spots where no lamp is */
      clearcoatRadiance /= 1.0 + 0.06 * max(clearcoatRadiance.r, max(clearcoatRadiance.g, clearcoatRadiance.b));      /* a lamp's image spreads in the finish rather than burning through it */
      #endif`)
      .replace("#include <aomap_fragment>", `#include <aomap_fragment>
      {
        vec2 auv = (vWp.xz - uAOBox.xy) / uAOBox.zw;
        float fao = (auv.x > 0.0 && auv.x < 1.0 && auv.y > 0.0 && auv.y < 1.0) ? texture2D(uAO, auv).r : 1.0;
        float pool = 0.0;      /* the lamps' pools of light: each lamp's beam falls off away from beneath it */
        for (int i = 0; i < 15; i++) { vec2 f = vec2(float(i / 5) * 5.2 - 5.2, float(i - (i / 5) * 5) * 4.9 - 9.8), d = vWp.xz - f; float q = 47.6 / (47.6 + dot(d, d)); pool += q * q * q; }
        fao *= mix(1.0, pool / 2.2, 0.75);
        reflectedLight.indirectDiffuse *= fao; reflectedLight.indirectSpecular *= fao;
        #ifdef USE_CLEARCOAT
        clearcoatSpecularIndirect *= mix(1.0, fao, 0.35);
        #endif
      }`);
  };
  floorMat.customProgramCacheKey = () => "polling-floor";
  const fg = new THREE.PlaneGeometry(2 * RX, ZB - ZF); fg.rotateX(-Math.PI / 2); fg.translate(0, 0, (ZF + ZB) / 2);
  { const p = fg.attributes.position, uv = fg.attributes.uv; for (let i = 0; i < p.count; i++) uv.setXY(i, p.getZ(i) / 2.4, p.getX(i) / 0.98); }      // strips run the length of the court
  const floor = new THREE.Mesh(fg, floorMat); floor.receiveShadow = true; scene.add(floor);

  /* ---------- the walls ---------- */
  const WALLS = {far: {o: V3(0, 0, ZF), u: V3(1, 0, 0), n: V3(0, 0, 1)}, left: {o: V3(-RX, 0, 0), u: V3(0, 0, -1), n: V3(1, 0, 0)},
                 right: {o: V3(RX, 0, 0), u: V3(0, 0, 1), n: V3(-1, 0, 0)}, back: {o: V3(0, 0, ZB), u: V3(-1, 0, 0), n: V3(0, 0, -1)}};
  /* a wall with a row of high windows: the wall in pieces around them, and each window's reveal (the wall is 30 cm
     thick), its bronze frame and its glass */
  const metric = (w, h) => { const g = new THREE.PlaneGeometry(w, h), uv = g.attributes.uv; for (let i = 0; i < uv.count; i++) uv.setXY(i, uv.getX(i) * w / 2.4, uv.getY(i) * h / 2.4); return g; };
  const windows = [];      // each window's centre, its frame, for the sun's shafts
  const windowed = (wall, a0, a1, cs, w, y0, y1, keepList) => {
    const hw = w / 2, a = cs.slice().sort((p, q) => p - q), T = 0.3, hh = y1 - y0, ym = (y0 + y1) / 2;
    wallRect(B, wallMat, wall, a0, a1, 0, y0); wallRect(B, wallMat, wall, a0, a1, y1, HC);
    let prev = a0; for (const c of a) { wallRect(B, wallMat, wall, prev, c - hw, y0, y1); prev = c + hw; } wallRect(B, wallMat, wall, prev, a1, y0, y1);
    for (const c of a) {
      const g = new THREE.Group(); g.position.copy(wall.o).addScaledVector(wall.u, c); g.quaternion.setFromRotationMatrix(new THREE.Matrix4().makeBasis(wall.u, V3(0, 1, 0), wall.n)); scene.add(g);
      part(g, metric(w, T), wallMat, 0, y0, -T / 2, -Math.PI / 2, 0, 0);      // the sill
      part(g, metric(w, T), wallMat, 0, y1, -T / 2, Math.PI / 2, 0, 0);      // the head
      part(g, metric(T, hh), wallMat, -hw, ym, -T / 2, 0, Math.PI / 2, 0); part(g, metric(T, hh), wallMat, hw, ym, -T / 2, 0, -Math.PI / 2, 0);
      const fz = -T + 0.06;
      for (const xx of [-hw + 0.03, -hw / 3, hw / 3, hw - 0.03]) part(g, BOX(0.06, hh, 0.07), bronze, xx, ym, fz);
      for (const yy of [y0 + 0.03, y0 + hh * 0.45, y1 - 0.03]) part(g, BOX(w, 0.06, 0.07), bronze, 0, yy, fz);
      const gl = part(g, new THREE.PlaneGeometry(w, hh), glassMat, 0, ym, fz - 0.005); gl.userData.keep = true; gl.castShadow = false;
      if (keepList) keepList.push({centre: wall.o.clone().addScaledVector(wall.u, c).add(V3(0, ym, 0)).addScaledVector(wall.n, fz), u: wall.u.clone(), w, h: hh});
      B.bake(g);
    }
  };
  windowed(WALLS.left, -ZB, -ZF, WIN.z.map(z => -z), WIN.w, WIN.y0, WIN.y1, windows);
  windowed(WALLS.far, -RX, RX, WINF.x, WINF.w, WINF.y0, WINF.y1, null);
  wallRect(B, wallMat, WALLS.right, ZF, ZB, 0, HC); wallRect(B, wallMat, WALLS.back, -RX, RX, 0, HC);
  /* the dusk outside: a photographed sky where the place has one, laid by direction so it stays far away as you move;
     else a sky worked out by direction. Either darkens through the blue hour as the sun goes */
  const skyTex = more.sky ? texOf(more.sky, true, 4) : null;
  if (skyTex) { skyTex.wrapS = THREE.RepeatWrapping; skyTex.wrapT = THREE.ClampToEdgeWrapping; }
  const SKY_U = (opts.skySunU != null ? opts.skySunU : 0.6104);      // where the sun sits around the photographed sky
  const skyMat = new THREE.ShaderMaterial({uniforms: {uK: {value: LOOK.sky}, uDusk: {value: 1.0}, tSky: {value: skyTex}, uSunAz: {value: SUN.az * D2R}, uSunU: {value: SKY_U}},
    vertexShader: "varying vec3 vWp; void main(){ vec4 w = modelMatrix * vec4(position, 1.0); vWp = w.xyz; gl_Position = projectionMatrix * viewMatrix * w; }",
    fragmentShader: `uniform float uK, uDusk, uSunAz, uSunU; uniform sampler2D tSky; varying vec3 vWp;
      float h2(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
      float n2(vec2 p){ vec2 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f); return mix(mix(h2(i), h2(i + vec2(1, 0)), f.x), mix(h2(i + vec2(0, 1)), h2(i + vec2(1, 1)), f.x), f.y); }
      void main(){
        vec3 d = normalize(vWp - cameraPosition); float el = asin(clamp(d.y, -1.0, 1.0)), az = atan(d.z, -d.x);
        vec3 c;
        #ifdef HAS_SKY
          /* the picture turned so its sun stands where the scene's does, low in the west */
          float u = uSunU + (az - uSunAz) / 6.2831853, v = 0.5 - el / 3.14159265;
          c = texture2D(tSky, vec2(u, clamp(v, 0.002, 0.52))).rgb;
          c = pow(c, vec3(2.2));      /* back to light */
          c = mix(c, c * vec3(0.55, 0.62, 1.0), (1.0 - uDusk) * 0.6);      /* the blue hour deepens */
          c *= mix(0.08, 1.0, uDusk) * 0.55;
        #else
          vec3 zen = vec3(0.0045, 0.0105, 0.040), mid = vec3(0.0120, 0.0250, 0.075), low = vec3(0.040, 0.046, 0.085);
          c = mix(low, mid, smoothstep(0.0, 0.35, el)); c = mix(c, zen, smoothstep(0.35, 1.2, el));
          c += vec3(0.10, 0.045, 0.025) * exp(-max(el, 0.0) * 7.0) * (0.6 + 0.4 * cos(az * 0.8)) * mix(0.2, 1.0, uDusk);
          vec2 q = vec2(az * 3.0, el * 9.0); float cl = n2(q * 1.7) * 0.6 + n2(q * 4.1) * 0.3 + n2(q * 9.3) * 0.1;
          float cloud = smoothstep(0.58, 0.8, cl) * smoothstep(0.05, 0.25, el) * (1.0 - smoothstep(0.7, 1.0, el));
          c = mix(c, vec3(0.020, 0.024, 0.048) + vec3(0.03, 0.012, 0.012) * (1.0 - smoothstep(0.1, 0.5, el)), cloud * 0.7);
          c *= mix(0.25, 1.0, uDusk) * 1.1;
        #endif
        gl_FragColor = vec4(c * uK, 1.0);
      }`});
  if (skyTex) skyMat.defines = {HAS_SKY: 1};
  { const s = new THREE.Mesh(new THREE.PlaneGeometry(ZB - ZF, 7), skyMat); s.position.set(-RX - 1.4, (WIN.y0 + WIN.y1) / 2, (ZF + ZB) / 2); s.rotation.y = Math.PI / 2; scene.add(s);
    const f = new THREE.Mesh(new THREE.PlaneGeometry(2 * RX + 4, 6), skyMat); f.position.set(0, 7, ZF - 1.4); scene.add(f); }

  /* the painted band, the rubber base, the pads under the hoop */
  for (const k of ["far", "right", "back", "left"]) {
    const w = WALLS[k], ext = k === "far" || k === "back" ? [-RX, RX] : [k === "left" ? -ZB : ZF, k === "left" ? -ZF : ZB];
    wallRect(B, bandMat, {o: w.o.clone().addScaledVector(w.n, 0.004), u: w.u, n: w.n}, ext[0], ext[1], 2.3, 2.52);
    wallRect(B, baseMat, {o: w.o.clone().addScaledVector(w.n, 0.006), u: w.u, n: w.n}, ext[0], ext[1], 0, 0.1, 1);
  }
  { const pg = new THREE.Group();
    for (let i = 0; i < 6; i++) part(pg, roundBox(1.2, 1.9, 0.06, 0.012, 2), padMat, -3.6 + 0.6 + i * 1.2, 0.95 + 0.004, ZF + 0.031);
    B.bake(pg); }

  /* ---------- the roof: steel joists across the gym, the deck above them, a duct, the lights ---------- */
  { const deck = new THREE.Mesh(new THREE.PlaneGeometry(2 * RX, ZB - ZF), deckMat); deck.rotation.x = Math.PI / 2; deck.position.set(0, HC, (ZF + ZB) / 2);
    deck.receiveShadow = true; B.add(deck);
    const jg = new THREE.Group();
    for (let z = ZF + 1.0; z < ZB - 0.5; z += 1.8) {
      part(jg, BOX(2 * RX, 0.07, 0.11), steelMat, 0, HC - 0.06, z); part(jg, BOX(2 * RX - 0.8, 0.06, 0.1), steelMat, 0, HC - 0.86, z);
      for (let x = -RX + 0.4, k = 0; x < RX - 0.5; x += 0.8, k++) {
        const a = V3(x, k % 2 ? HC - 0.86 : HC - 0.09, z), b = V3(x + 0.8, k % 2 ? HC - 0.09 : HC - 0.86, z);
        const d = b.clone().sub(a), m = new THREE.Mesh(BOX(0.028, d.length(), 0.028), steelMat); m.position.copy(a).add(b).multiplyScalar(0.5);
        m.quaternion.setFromUnitVectors(V3(0, 1, 0), d.normalize()); jg.add(m);
      }
      for (let x = -RX + 0.3; x < RX; x += 0.9) part(jg, BOX(0.006, 0.05, 1.8), steelMat, x, HC - 0.025, z + 0.9);      // the deck's ribs
    }
    for (let x = -RX + 2.4; x < RX - 1; x += 4.8) part(jg, BOX(0.05, 0.05, ZB - ZF), steelMat, x, HC - 0.88, (ZF + ZB) / 2);      // bridging
    B.bake(jg);
    const dg = new THREE.Group();
    part(dg, CYL(0.36, 0.36, ZB - ZF, 28, false), duct, 4.6, HC - 1.35, (ZF + ZB) / 2, Math.PI / 2, 0, 0);
    for (let z = ZF + 1.4; z < ZB; z += 3.0) { part(dg, new THREE.TorusGeometry(0.362, 0.012, 6, 28), duct, 4.6, HC - 1.35, z); part(dg, CYL(0.008, 0.008, 0.95, 6), darkSteel, 4.6, HC - 0.5, z); }
    for (let z = ZF + 2.9; z < ZB; z += 6.0) part(dg, BOX(0.5, 0.12, 0.4), duct, 4.6, HC - 1.77, z);      // the vents that stir the flags
    B.bake(dg);
  }
  const FIX = []; for (const x of [-5.2, 0, 5.2]) for (const z of [-9.8, -4.9, 0, 4.9, 9.8]) FIX.push([x, z]);
  { const lg = new THREE.Group();
    for (const [x, z] of FIX) {
      part(lg, CYL(0.17, 0.25, 0.3, 28), alu, x, 7.05, z); part(lg, CYL(0.11, 0.17, 0.12, 20), darkSteel, x, 7.26, z);
      part(lg, CYL(0.012, 0.012, HC - 0.86 - 7.3, 6), darkSteel, x, (HC - 0.86 + 7.3) / 2, z);
      part(lg, new THREE.CircleGeometry(0.235, 28), lensMat, x, 6.896, z, Math.PI / 2, 0, 0);
    }
    B.bake(lg);
  }

  /* ---------- the bleachers, pulled out along the east wall: six telescoping rows of maple planks on a steel frame ---------- */
  { const bg = new THREE.Group(), z0 = BLEACH.z0, z1 = BLEACH.z1, len = z1 - z0, zc = (z0 + z1) / 2;
    const board = std({color: "#E2C79F", map: maple, roughness: 0.42});
    const setUV = (m, L, Hh, off) => { const uv = m.geometry.attributes.uv; for (let k = 0; k < uv.count; k++) uv.setXY(k, uv.getX(k) * L / 2.4 + off, uv.getY(k) * Hh / 2.4 + off * 0.7); };
    for (let i = 0; i < BLEACH.rows; i++) {
      const xf = bleachFront(i), yd = i * BLEACH.rise, ys = yd + BLEACH.seat;
      const tread = part(bg, BOX(BLEACH.tread - 0.02, 0.035, len), board, xf + BLEACH.tread / 2, yd + 0.0175 + (i ? 0 : 0.0), zc); setUV(tread, len, 0.76, i * 0.31);      // the footboard
      if (i > 0) part(bg, BOX(0.02, BLEACH.rise, len), darkSteel, xf + 0.01, yd - BLEACH.rise / 2, zc);      // the riser below it
      const seat = part(bg, BOX(0.26, 0.045, len), board, xf + BLEACH.tread - 0.14, ys, zc); setUV(seat, len, 0.26, i * 0.17 + 0.5);      // the seat plank
      part(bg, BOX(0.02, 0.3, len), darkSteel, xf + BLEACH.tread - 0.27, ys - 0.17, zc);      // the seat's front skirt
      for (let z = z0 + 0.5; z < z1; z += 2.0) { part(bg, BOX(0.03, ys - yd - 0.02, 0.03), darkSteel, xf + BLEACH.tread - 0.12, (yd + ys) / 2, z); }      // seat supports
      for (let z = z0 + 0.8; z < z1; z += 3.2) part(bg, BOX(0.04, yd + 0.01, 0.06), darkSteel, xf + 0.06, yd / 2, z);      // the frame's legs under the treads
    }
    const backH = (BLEACH.rows - 1) * BLEACH.rise + BLEACH.seat + 0.45, backM = std({color: "#A7A39A", roughness: 0.6, metalness: 0.15, roughnessMap: metalNoise});
    part(bg, BOX(0.03, backH, len), backM, RX - 0.04, backH / 2, zc);      // the closed back against the wall
    for (const z of [z0, z1]) {      /* a sloped handrail at each end, on three posts */
      const a = V3(bleachFront(0) + 0.1, 1.0, z), b = V3(RX - 0.12, backH - 0.1, z); tube(bg, alu, a, b, 0.02, 8);
      for (const i of [0, 3, 5]) { const xf = bleachFront(i) + 0.1, yt = mix(a.y, b.y, (xf - a.x) / (b.x - a.x)); part(bg, BOX(0.03, yt - i * BLEACH.rise, 0.03), alu, xf, (yt + i * BLEACH.rise) / 2, z); }
    }
    B.bake(bg);
    block((RX + bleachFront(0)) / 2, zc, RX - bleachFront(0), len);
  }

  /* ---------- the far wall: the hoop on its frame, the doors to the hall, the clock, the scoreboard, a banner ---------- */
  { const hg = new THREE.Group(), bz = COURT.board; scene.add(hg);
    const board = new THREE.Group(); board.position.set(0, 3.435, bz - 0.007); hg.add(board);
    const bglass = part(board, BOX(1.83, 1.07, 0.0127), glassMat, 0, 0, 0); bglass.userData.keep = true; bglass.castShadow = false;
    const lineM = std({color: "#F2F2EE", roughness: 0.5});
    for (const [w, h, x, y] of [[1.79, 0.05, 0, 0.51], [1.79, 0.05, 0, -0.51], [0.05, 1.07, 0.89, 0], [0.05, 1.07, -0.89, 0],
                                 [0.61, 0.05, 0, -0.33 + 0.457], [0.61, 0.05, 0, -0.33], [0.05, 0.457, 0.28, -0.33 + 0.2285], [0.05, 0.457, -0.28, -0.33 + 0.2285]])
      part(board, BOX(w, h, 0.002), lineM, x, y, 0.0075);
    for (const [w, h, x, y] of [[1.87, 0.04, 0, 0.555], [1.87, 0.04, 0, -0.555], [0.04, 1.07, 0.935, 0], [0.04, 1.07, -0.935, 0]]) part(board, BOX(w, h, 0.03), alu, x, y, 0);
    part(board, roundBox(1.9, 0.07, 0.07, 0.02, 2), padMat, 0, -0.57, 0);
    const rim = std({color: "#D2561F", roughness: 0.42, metalness: 0.4});
    part(hg, new THREE.TorusGeometry(0.2286, 0.0095, 8, 44), rim, 0, 3.05, COURT.basket, Math.PI / 2, 0, 0);
    part(hg, BOX(0.12, 0.05, 0.16), rim, 0, 3.03, bz + 0.08);
    const net = canvasTex(256, 128, (g, w, h) => { g.strokeStyle = "rgba(255,255,255,0.95)"; g.lineWidth = 3;
      for (let i = -8; i < 16; i++) { g.beginPath(); g.moveTo(i * w / 12, 0); g.lineTo(i * w / 12 + w / 2, h); g.stroke(); g.beginPath(); g.moveTo(i * w / 12 + w / 2, 0); g.lineTo(i * w / 12, h); g.stroke(); } }, {repeat: true});
    net.repeat.set(2, 1);
    const netMat = std({map: net, alphaTest: 0.45, side: THREE.DoubleSide, roughness: 0.9, color: "#F4F4F0"});
    const nm = part(dyn, CYL(0.225, 0.15, 0.42, 24, true), netMat, 0, 3.05 - 0.21, COURT.basket); nm.castShadow = false;
    const frame = new THREE.Group(); hg.add(frame);
    for (const x of [-0.55, 0.55]) for (const y of [3.25, 4.45]) tube(frame, darkSteel, V3(x, y, bz - 0.05), V3(x * 0.8, y, ZF + 0.05), 0.04);
    for (const x of [-0.55, 0.55]) { tube(frame, darkSteel, V3(x, 3.25, bz - 0.05), V3(x, 4.45, bz - 0.05), 0.035); tube(frame, darkSteel, V3(x, 3.25, bz - 0.05), V3(x * 0.8, 4.45, ZF + 0.05), 0.03); }
    tube(frame, darkSteel, V3(-0.55, 4.45, bz - 0.05), V3(0.55, 4.45, bz - 0.05), 0.035);
    part(frame, BOX(1.25, 1.3, 0.03), steelMat, 0, 3.85, ZF + 0.02);
    B.bake(hg);
  }
  const doorX = -6.9;
  const printed = (map, k = 1) => new THREE.MeshBasicMaterial({map, color: new THREE.Color(k, k, k)});
  const exitTex = canvasTex(256, 112, (g, w, h) => { g.fillStyle = "#F2F2EE"; g.fillRect(0, 0, w, h); say(g, "EXIT", w / 2, h / 2 + 4, `900 74px ${SANS}`, "#14A44A"); });
  /* a pair of steel doors with push bars and small wired-glass lights, an exit sign over them: to the hall in the far
     wall, and the ones you came in by in the back wall */
  const doorMat = std({color: "#5B675F", roughness: 0.45, metalness: 0.25, roughnessMap: metalNoise});
  const doorGlass = std({color: "#0E1418", roughness: 0.08, metalness: 0.3});
  const doors = (wall, a, flip) => {
    const g = new THREE.Group(); g.position.copy(wall.o).addScaledVector(wall.u, a); g.quaternion.setFromRotationMatrix(new THREE.Matrix4().makeBasis(wall.u, V3(0, 1, 0), wall.n)); scene.add(g);
    part(g, BOX(2.0, 2.4, 0.06), darkSteel, 0, 1.2, 0.03);
    for (const s of [-1, 1]) {
      part(g, BOX(0.9, 2.2, 0.05), doorMat, s * 0.46, 1.1, 0.07);
      part(g, BOX(0.62, 0.05, 0.05), alu, s * 0.46, 1.0, 0.12);      // the push bar
      part(g, BOX(0.03, 0.05, 0.06), alu, s * 0.46 + s * 0.27, 1.0, 0.1); part(g, BOX(0.03, 0.05, 0.06), alu, s * 0.46 - s * 0.27, 1.0, 0.1);
      part(g, BOX(0.12, 0.7, 0.01), doorGlass, s * 0.68, 1.6, 0.1);
      part(g, BOX(0.01, 0.74, 0.012), alu, s * 0.68 + 0.065, 1.6, 0.1); part(g, BOX(0.01, 0.74, 0.012), alu, s * 0.68 - 0.065, 1.6, 0.1);
      for (const y of [0.35, 1.35]) part(g, BOX(0.03, 0.09, 0.02), alu, s * 0.91, y + 0.4, 0.09);      // hinges
      part(g, BOX(0.88, 0.25, 0.012), alu, s * 0.46, 0.14, 0.098);      // the kick plate
    }
    part(g, BOX(0.36, 0.16, 0.06), white, 0, 2.62, 0.035);
    part(g, new THREE.PlaneGeometry(0.34, 0.145), printed(exitTex, 2.2), 0, 2.62, 0.066).castShadow = false;
    B.bake(g);
    const c = g.position; block(c.x, c.z, Math.abs(wall.u.x) * 2.0 + Math.abs(wall.n.x) * 0.3, Math.abs(wall.u.z) * 2.0 + Math.abs(wall.n.z) * 0.3);
  };
  doors(WALLS.far, doorX, false);
  doors(WALLS.back, -DOORB.x, true);
  { /* the scoreboard, off but for its clock */
    const sb = canvasTex(1024, 448, (g, w, h) => {
      g.fillStyle = "#0B0C0D"; g.fillRect(0, 0, w, h); g.strokeStyle = "#2A2D30"; g.lineWidth = 10; g.strokeRect(5, 5, w - 10, h - 10);
      say(g, "HOME", 200, 70, `800 58px ${SANS}`, "#E9E9E4"); say(g, "GUEST", 824, 70, `800 58px ${SANS}`, "#E9E9E4"); say(g, "PERIOD", 512, 300, `700 34px ${SANS}`, "#E9E9E4");
      for (const x of [200, 824]) say(g, "00", x, 220, `700 150px "Courier New", monospace`, "#2A1E10");
      say(g, `${SUN.hour - 12}:${String(SUN.minute).padStart(2, "0")}`, 512, 150, `700 130px "Courier New", monospace`, "#FFB13B"); say(g, "-", 512, 380, `700 70px "Courier New", monospace`, "#2A1E10");
    });
    part(scene, BOX(2.6, 1.14, 0.1), darkSteel, 5.3, 5.5, ZF + 0.06);
    part(scene, new THREE.PlaneGeometry(2.5, 1.09), printed(sb, 1.4), 5.3, 5.5, ZF + 0.111).castShadow = false;
    const ban = canvasTex(1400, 440, (g, w, h) => {
      g.fillStyle = "#F7F6F1"; g.fillRect(0, 0, w, h); g.strokeStyle = "#1A1C1E"; g.lineWidth = 14; g.strokeRect(22, 22, w - 44, h - 44);
      usFlag(g, 70, 90, 300, 158); say(g, "VOTE HERE", 880, 175, `900 150px ${SANS}`, "#16181A");
      say(g, "POLLING PLACE", 880, 318, `700 60px ${SANS}`, "#2A2D30"); g.fillStyle = "#16181A";
      g.beginPath(); g.moveTo(90, 320); g.lineTo(290, 320); g.lineTo(290, 290); g.lineTo(350, 340); g.lineTo(290, 390); g.lineTo(290, 360); g.lineTo(90, 360); g.closePath(); g.fill();
      wear(g, w, h, 31, 0.035);
    });
    part(scene, new THREE.PlaneGeometry(3.0, 0.94), std({map: ban, roughness: 0.7}), 4.6, 3.05, ZF + 0.03).castShadow = false;
  }
  /* the clock, caged as gym clocks are */
  const hands = [];
  if (A.clock) {
    const c = A.clock.clone(true); c.scale.setScalar(1.3); c.position.set(-3.9, 5.55, ZF + 0.02); scene.add(c);
    c.traverse(o => { if (o.isMesh) { o.castShadow = false; o.receiveShadow = true; if (o.material && o.material.transparent) o.material = glassMat; } });
    const want = {wall_clock_hours_hand: (SUN.hour - 12 + SUN.minute / 60) * 30, wall_clock_minute_hand: SUN.minute * 6 + 0.3, wall_clock_second_hand: 17 * 6};
    c.traverse(o => { const k = want[o.name] != null ? o.name : (o.parent && want[o.parent.name] != null ? o.parent.name : null); if (!k || !o.isMesh) return;
      const g = o.geometry; g.computeBoundingBox(); const b = g.boundingBox;
      const rest = [[b.max.y, 0], [b.max.x, 90], [-b.min.y, 180], [-b.min.x, 270]].sort((p, q) => q[0] - p[0])[0][1];
      const node = o.name === k ? o : o.parent; node.rotation.z = -(want[k] - rest) * D2R; hands.push({node, rest, k, base: want[k]}); });
    const cage = new THREE.Group(); cage.position.copy(c.position);
    for (let i = -4; i <= 4; i++) { tube(cage, darkSteel, V3(i * 0.06, -0.27, 0.12), V3(i * 0.06, 0.27, 0.12), 0.003, 4); tube(cage, darkSteel, V3(-0.27, i * 0.06, 0.12), V3(0.27, i * 0.06, 0.12), 0.003, 4); }
    for (const [x, y] of [[-0.27, -0.27], [0.27, -0.27], [0.27, 0.27], [-0.27, 0.27]]) tube(cage, darkSteel, V3(x, y, 0.0), V3(x, y, 0.12), 0.005, 4);
    B.bake(cage);
  }
  const CLOCK_AT = V3(-3.9, 5.55, ZF + 0.1);

  /* ---------- the polling place ---------- */
  /* the booths: five standing booths in a row, their open sides to the bleachers, "VOTE" on their screens */
  const boothPrint = canvasTex(512, 512, (g, w, h) => {
    g.fillStyle = "#F0F0EC"; g.fillRect(0, 0, w, h); usFlag(g, w / 2 - 70, 70, 140, 74);
    say(g, "VOTE", w / 2, 260, `900 170px ${SANS}`, "#1A1D1F"); g.fillStyle = "#1A1D1F"; g.fillRect(70, 360, w - 140, 10);
    say(g, "Please vote in private", w / 2, 410, `600 30px ${SANS}`, "#2B2E31"); wear(g, w, h, 41, 0.022);
  });
  const printMat = std({map: boothPrint, roughness: 0.62});
  const panelMat = std({color: "#F0F0EC", roughness: 0.62});
  const shelfMat = std({color: "#CFD0CB", roughness: 0.72});
  const footMat = std({color: "#1A1A1A", roughness: 0.7});
  /* the ballot's face: a generic one (no names, no parties, no real contests), marked */
  const BWd = 0.216, BHt = 0.279;
  const ballotFace = canvasTex(1080, 1395, (g, w, h) => {
    g.fillStyle = "#FBFBF7"; g.fillRect(0, 0, w, h); g.fillStyle = "#121314";
    for (let y = 70; y < h - 50; y += 38) { g.fillRect(16, y, 30, 12); g.fillRect(w - 46, y, 30, 12); }      // the timing marks a scanner reads by
    g.fillRect(80, 46, w - 160, 120); say(g, "OFFICIAL BALLOT", w / 2, 92, `800 56px ${SANS}`, "#FFFFFF"); say(g, "GENERAL ELECTION  ·  NOVEMBER 3, 2026", w / 2, 140, `600 27px ${SANS}`, "#D4D6D8");
    g.strokeStyle = "#121314"; g.lineWidth = 3; g.strokeRect(80, 190, w - 160, 92);
    say(g, "To vote, fill in the oval completely next to your choice.", w / 2, 222, `italic 500 27px ${SANS}`, "#26292C");
    say(g, "Use a black or blue pen.  If you make a mistake, ask for a new ballot.", w / 2, 256, `500 22px ${SANS}`, "#45494D");
    const colW = (w - 200) / 2;
    const contest = (x, y, n, pick, k) => {
      g.fillStyle = "#2A2D30"; g.fillRect(x, y, colW - 10, 46); g.fillStyle = "#BFC3C7"; g.fillRect(x + 20, y + 16, 160 + (k * 47) % 120, 14);
      say(g, "Vote for one", x + 20, y + 70, `italic 500 21px ${SANS}`, "#45494D", "left"); y += 106;
      for (let i = 0; i < n; i++, y += 62) {
        g.beginPath(); g.ellipse(x + 42, y, 26, 15, 0, 0, 7); g.lineWidth = 4; g.strokeStyle = "#121314"; g.stroke();
        if (i === pick) { g.fillStyle = "#0E0F10"; g.beginPath(); g.ellipse(x + 42, y, 23, 13, 0.04, 0, 7); g.fill(); }
        g.fillStyle = "#C9CDD1"; g.fillRect(x + 90, y - 10, 190 + ((k * 31 + i * 67) % 150), 20);
      }
      g.fillStyle = "#D7DADD"; g.fillRect(x + 90, y - 10, 120, 3); return y + 26;
    };
    let y1 = 320, y2 = 320;
    y1 = contest(100, y1, 3, 1, 1); y1 = contest(100, y1, 2, 0, 2); y1 = contest(100, y1, 4, 2, 3);
    y2 = contest(110 + colW, y2, 2, 1, 4); y2 = contest(110 + colW, y2, 3, 0, 5); y2 = contest(110 + colW, y2, 2, 1, 6);
    say(g, "Turn the ballot over: no contests on the back", w / 2, h - 60, `500 21px ${SANS}`, "#6A6E72");
    wear(g, w, h, 17, 0.035);
  });
  const ballotMat = std({map: ballotFace, roughness: 0.86, side: THREE.DoubleSide});
  if (clothNor) { ballotMat.normalMap = clothNor; ballotMat.normalScale.set(0.05, 0.05); }
  const pen = (parent, x, y, z, r) => { part(parent, CYL(0.0045, 0.0045, 0.14, 8), ink, x, y, z, 0, r, Math.PI / 2); part(parent, CYL(0.0046, 0.0046, 0.02, 8), alu, x + 0.065 * Math.cos(r), y, z - 0.065 * Math.sin(r), 0, r, Math.PI / 2); };
  for (let i = 0; i < BOOTHS.length; i++) {
    const b = BOOTHS[i], g = new THREE.Group(); g.position.set(b.x, 0, b.z);
    for (const [x, z] of [[-0.21, -0.28], [0.21, -0.28], [-0.21, 0.28], [0.21, 0.28]]) { part(g, CYL(0.0125, 0.0125, 1.0, 10), alu, x, 0.5, z); part(g, CYL(0.02, 0.022, 0.025, 10), footMat, x, 0.0125, z); }
    for (const z of [-0.28, 0.28]) part(g, BOX(0.42, 0.018, 0.018), alu, 0, 0.32, z);
    part(g, BOX(0.47, 0.022, 0.62), shelfMat, 0, 1.0, 0);
    part(g, BOX(0.006, 0.6, 0.62), panelMat, -0.232, 1.31, 0);
    for (const s of [-1, 1]) part(g, BOX(0.47, 0.6, 0.006), panelMat, 0, 1.31, s * 0.307);
    part(g, new THREE.PlaneGeometry(0.46, 0.46), printMat, -0.2355, 1.31, 0, 0, -Math.PI / 2, 0);
    part(g, new THREE.PlaneGeometry(0.46, 0.46), printMat, -0.2285, 1.31, 0, 0, Math.PI / 2, 0);      // and inside, where a voter standing in it sees it
    for (const s of [-1, 1]) part(g, new THREE.PlaneGeometry(0.36, 0.36), printMat, -0.02, 1.33, s * 0.3105, 0, s > 0 ? 0 : Math.PI, 0);
    /* on the shelf: a blank ballot in the middle booth (the one a reader can stand in), a privacy sleeve in the others, and a pen on its cord */
    if (i === 2) { const bl = part(g, new THREE.PlaneGeometry(BWd, BHt), ballotMat, 0.01, 1.0125, 0.02, -Math.PI / 2, 0, 0.06); bl.castShadow = false; }
    else part(g, BOX(0.24, 0.004, 0.31), std({color: "#26392F", roughness: 0.6}), 0.03, 1.014, 0.02, 0, 0.1 * (i - 2), 0);
    pen(g, 0.1, 1.016, -0.2 + 0.03 * i, 0.4 + 0.3 * i);
    tube(g, ink, V3(0.08, 1.016, -0.2), V3(-0.2, 1.05, -0.29), 0.0012, 4);      // the cord
    B.bake(g);
    block(b.x, b.z, 0.5, 0.64);
  }
  /* the chairs face away from their backs (worked out from the model, which way it was made facing) */
  let chairFacing = 0;
  if (A.chair) { let hi = 0, zc = 0, n = 0;
    A.chair.traverse(o => { if (!o.isMesh) return; const p = o.geometry.attributes.position; for (let i = 0; i < p.count; i += 3) hi = Math.max(hi, p.getY(i)); });
    A.chair.traverse(o => { if (!o.isMesh) return; const p = o.geometry.attributes.position; for (let i = 0; i < p.count; i += 3) if (p.getY(i) > hi * 0.8) { zc += p.getZ(i); n++; } });
    chairFacing = (n && zc / n < 0) ? 0 : Math.PI; }
  const chairAt = (x, z, ry) => { if (!A.chair) return; const ch = placeModel(scene, A.chair, x, 0, z, chairFacing + ry); if (ch) post(x, z, 0.26); return ch; };
  /* the check-in table: a folding table, poll books, a sign, pens, privacy sleeves, a roll of "I VOTED" stickers; two chairs behind it */
  { const g = new THREE.Group(); g.position.set(TABLE.x, 0, TABLE.z);
    /* the top: a folding table's laminate, a fine grey speckle in an off-white, a few scuffs and a scratch or two, duller
       where it is worn; one tile is 0.6 m */
    const lam = canvasTex(512, 512, (c, w, h) => { c.fillStyle = "#D9D7D0"; c.fillRect(0, 0, w, h); const r = rng(71);
      for (let i = 0; i < 26000; i++) { const v = 150 + (r() * 80) | 0; c.fillStyle = `rgba(${v},${v - 4},${v - 10},${0.35 + r() * 0.4})`; c.fillRect(r() * w, r() * h, 1 + (r() < 0.2 ? 1 : 0), 1); }
      c.strokeStyle = "rgba(90,86,80,0.22)"; for (let i = 0; i < 9; i++) { const x = 60 + r() * (w - 120), y = 60 + r() * (h - 120), L = 20 + r() * 50, a = r() * 6.28; c.lineWidth = 0.6 + r() * 0.8;
        c.beginPath(); c.moveTo(x, y); c.lineTo(x + Math.cos(a) * L, y + Math.sin(a) * L); c.stroke(); } }, {repeat: true});
    const lamR = canvasTex(256, 256, (c, w, h) => { c.fillStyle = "#8c8c8c"; c.fillRect(0, 0, w, h); const r = rng(72);
      for (let i = 0; i < 40; i++) { const x = r() * w, y = r() * h, rad = 10 + r() * 60, gr = c.createRadialGradient(x, y, 0, x, y, rad);
        gr.addColorStop(0, `rgba(${r() < 0.5 ? 120 : 175},${r() < 0.5 ? 120 : 175},${r() < 0.5 ? 120 : 175},0.5)`); gr.addColorStop(1, "rgba(0,0,0,0)"); c.fillStyle = gr; c.fillRect(x - rad, y - rad, 2 * rad, 2 * rad); } }, {srgb: false, repeat: true});
    const top = std({map: lam, roughness: 0.62, roughnessMap: lamR});
    const topGeo = roundBox(0.76, 0.045, 1.83, 0.015, 2); { const uv = topGeo.attributes.uv, p = topGeo.attributes.position; for (let i = 0; i < uv.count; i++) uv.setXY(i, p.getX(i) / 0.6, p.getZ(i) / 0.6); }
    part(g, topGeo, top, 0, 0.7375, 0);
    for (const z of [-0.78, 0.78]) { for (const x of [-0.3, 0.3]) part(g, CYL(0.013, 0.013, 0.715, 10), steelMat, x, 0.3575, z); part(g, BOX(0.62, 0.025, 0.025), steelMat, 0, 0.06, z); part(g, BOX(0.62, 0.02, 0.02), steelMat, 0, 0.66, z); }
    tube(g, steelMat, V3(0, 0.66, -0.78), V3(0, 0.66, 0.78), 0.012);
    const pageTex = canvasTex(512, 640, (c, w, h) => { c.fillStyle = "#FBFAF5"; c.fillRect(0, 0, w, h); c.fillStyle = "#3A3D40"; c.fillRect(30, 26, w - 60, 34);
      for (let y = 90, k = 0; y < h - 30; y += 30, k++) { c.fillStyle = "#C3C6C9"; c.fillRect(40, y, 120 + ((k * 53) % 90), 12); c.fillRect(220, y, 70 + ((k * 37) % 50), 12);
        c.fillStyle = "#9AA0A5"; c.fillRect(320, y + 12, 160, 2); if (k % 3 !== 1 && k < 9) { c.strokeStyle = "#20283A"; c.lineWidth = 2; c.beginPath(); c.moveTo(326, y + 10); for (let i = 0; i < 9; i++) c.lineTo(330 + i * 14, y + 4 + Math.sin(i * 1.7 + k) * 6); c.stroke(); } } });
    const pageMat = std({map: pageTex, roughness: 0.9});
    const cover = std({color: "#203329", roughness: 0.55}), cover2 = std({color: "#1D1F22", roughness: 0.5});
    const book = (x, z, open, cm) => { const b = new THREE.Group(); b.position.set(x, 0.76, z); g.add(b);
      if (open) { for (const s of [-1, 1]) { part(b, BOX(0.25, 0.006, 0.31), cm, 0, 0.003, s * 0.13); part(b, BOX(0.23, 0.014, 0.29), pageMat, 0, 0.012, s * 0.128); }
        part(b, BOX(0.25, 0.02, 0.03), cm, 0, 0.01, 0); }
      else { part(b, BOX(0.25, 0.006, 0.31), cm, 0, 0.003, 0); part(b, BOX(0.24, 0.04, 0.3), paper, 0, 0.025, 0); part(b, BOX(0.25, 0.006, 0.31), cm, 0, 0.048, 0); part(b, BOX(0.25, 0.052, 0.02), cm, -0.115, 0.026, 0); }
      return b; };
    if (!more.binder) { book(0.06, -0.42, true, cover).rotation.y = 0.04; book(0.05, 0.42, true, cover2).rotation.y = -0.05; }
    book(-0.2, 0.0, false, cover).rotation.y = 0.2;
    const tent = canvasTex(512, 170, (c, w, h) => { c.fillStyle = "#FFFFFF"; c.fillRect(0, 0, w, h); c.fillStyle = "#1A1C1E"; c.fillRect(0, 0, w, 10); c.fillRect(0, h - 10, w, 10);
      say(c, "CHECK IN HERE", w / 2, h / 2 + 2, `900 62px ${SANS}`, "#1A1C1E"); });
    const tg = new THREE.Group(); tg.position.set(0.3, 0.76, 0.0); tg.rotation.y = Math.PI / 2; g.add(tg);
    const tentM = std({map: tent, roughness: 0.7});
    for (const s of [-1, 1]) part(tg, new THREE.PlaneGeometry(0.34, 0.11), s > 0 ? tentM : white, 0, 0.053, s * 0.017, s * -0.32, s > 0 ? 0 : Math.PI, 0);
    for (const [x, z, r] of [[0.22, -0.2, 0.3], [0.24, 0.22, -0.5], [0.18, -0.62, 1.2]]) pen(g, x, 0.7645, z, r);
    const sleeve = std({color: "#26392F", roughness: 0.6});
    for (let i = 0; i < 6; i++) part(g, BOX(0.24, 0.004, 0.31), sleeve, -0.18 + (i % 2) * 0.004, 0.762 + i * 0.0045, 0.62 + (i % 3) * 0.003, 0, 0.02 * (i % 3), 0);
    /* a roll of "I VOTED" stickers, and a few peeled off and left on the table */
    const stickerTex = canvasTex(256, 128, (c, w, h) => { c.fillStyle = "#F4F4F0"; c.fillRect(0, 0, w, h);
      for (let i = 0; i < 2; i++) { c.fillStyle = "#B22234"; c.beginPath(); c.ellipse(64 + i * 128, 64, 58, 36, 0, 0, 7); c.fill(); say(c, "I VOTED", 64 + i * 128, 66, `900 26px ${SANS}`, "#FFFFFF"); } }, {repeat: true});
    stickerTex.repeat.set(12, 1);
    const roll = std({map: stickerTex, roughness: 0.75});
    part(g, CYL(0.045, 0.045, 0.034, 24, true), roll, 0.25, 0.777, 0.65, Math.PI / 2, 0, 0); part(g, CYL(0.044, 0.044, 0.032, 24), white, 0.25, 0.777, 0.65, Math.PI / 2, 0, 0);
    const one = canvasTex(128, 80, (c, w, h) => { c.fillStyle = "#B22234"; c.beginPath(); c.ellipse(64, 40, 58, 36, 0, 0, 7); c.fill(); say(c, "I VOTED", 64, 42, `900 26px ${SANS}`, "#FFFFFF"); });
    const oneM = std({map: one, roughness: 0.7, alphaTest: 0.5, transparent: true});
    for (const [x, z, r] of [[0.1, 0.5, 0.4], [-0.05, 0.56, -0.9], [0.18, 0.4, 2.1]]) part(g, new THREE.PlaneGeometry(0.046, 0.029), oneM, x, 0.7605, z, -Math.PI / 2, 0, r).castShadow = false;
    B.bake(g);
    block(TABLE.x, TABLE.z, 0.8, 1.86);
    chairAt(TABLE.x - 0.72, TABLE.z - 0.45, Math.PI / 2 + 0.08); chairAt(TABLE.x - 0.72, TABLE.z + 0.48, Math.PI / 2 - 0.12);
    /* the place's own models on the table: the poll books as real binders, a clipboard with the day's sheet */
    if (more.binder) {
      const b1 = placeModel(scene, more.binder, TABLE.x + 0.03, 0.76, TABLE.z - 0.42, Math.PI / 2 + 0.05, 0.62);
      const b2 = placeModel(scene, more.binder, TABLE.x + 0.03, 0.76, TABLE.z + 0.42, Math.PI / 2 - 0.06, 0.62);
      for (const b of [b1, b2]) if (b) b.traverse(o => { if (o.isMesh && /closed/.test(o.name)) o.visible = false; });      // the open one
    }
    if (more.clipboard) placeModel(scene, more.clipboard, TABLE.x - 0.12, 0.761, TABLE.z + 0.05, Math.PI / 2 - 0.25, 1.0);
  }
  /* the flags: an indoor flag on an oak pole, gold fringe and tassels, standing in its base */
  const cloths = [];      /* the flags stir a little in the air the vents move */
  const flagTex = canvasTex(1520, 910, (g, w, h) => { usFlag(g, 0, 0, w, h); g.fillStyle = "#C9A043"; g.fillRect(w - 26, 0, 26, h); g.fillRect(0, h - 22, w, 22);
    g.fillStyle = "rgba(90,60,10,.35)"; for (let x = w - 26; x < w; x += 4) g.fillRect(x, 0, 1, h); for (let x = 0; x < w; x += 4) g.fillRect(x, h - 22, 1, 22); });
  const flagMat = std({map: flagTex, roughness: 0.82, side: THREE.DoubleSide});
  if (clothNor) { const n = clothNor.clone(); n.needsUpdate = true; n.repeat.set(7, 4); flagMat.normalMap = n; flagMat.normalScale.set(0.6, 0.6); }
  const oak = std({color: "#6E4B2C", roughness: 0.45}), gold = std({color: "#C9A24A", roughness: 0.28, metalness: 1.0});
  for (const [x, z, face, seed] of FLAGS) {
    const g = new THREE.Group(); g.position.set(x, 0, z); g.rotation.y = face; scene.add(g);
    const st = new THREE.Group(); g.add(st);
    part(st, CYL(0.14, 0.17, 0.035, 28), gold, 0, 0.0175, 0); part(st, new THREE.SphereGeometry(0.07, 20, 10, 0, Math.PI * 2, 0, Math.PI / 2), gold, 0, 0.035, 0);
    part(st, CYL(0.016, 0.016, 2.42, 12), oak, 0, 1.24, 0); part(st, CYL(0.019, 0.019, 0.05, 12), gold, 0, 1.24, 0);
    part(st, CYL(0.01, 0.014, 0.06, 10), gold, 0, 2.48, 0); part(st, new THREE.SphereGeometry(0.042, 20, 14), gold, 0, 2.54, 0);
    const cord = std({color: "#C8A24C", roughness: 0.55, metalness: 0.3});
    for (const s of [-1, 1]) { const top = V3(s * 0.012, 2.42, 0.01), bot = V3(s * 0.05, 1.86 + s * 0.05, 0.03 + s * 0.01); tube(st, cord, top, bot, 0.004, 5);
      part(st, CYL(0.006, 0.026, 0.11, 10), cord, bot.x, bot.y - 0.06, bot.z); }
    B.bake(st);
    post(x, z, 0.24);
    /* the cloth hangs from the pole's sleeve: the fly drops and falls in folds */
    const Wd = 1.52, Hh = 0.91, geo = new THREE.PlaneGeometry(Wd, Hh, 56, 26), p = geo.attributes.position, uv = geo.attributes.uv, r = rng(seed);
    const ph = [r() * 6, r() * 6, r() * 6];
    for (let i = 0; i < p.count; i++) {
      const u = uv.getX(i), v = 1 - uv.getY(i);
      const out = 0.26 * (1 - Math.pow(1 - u, 1.8)) + 0.05 * v * u, drop = 0.95 * Math.pow(u, 1.25) + v * Hh * (1 - 0.06 * u);
      const amp = 0.015 + 0.085 * Math.pow(u, 0.8), f = amp * Math.sin(u * Math.PI * 2 * 2.9 + v * 1.1 + ph[0]) + 0.03 * u * u * Math.sin(u * 23.0 + v * 2.2 + ph[1]) + 0.014 * Math.sin(v * 5.0 + ph[2]) * u;
      p.setXYZ(i, out + 0.016, 2.4 - 0.02 - drop, f);
    }
    geo.computeVertexNormals();
    const cloth = new THREE.Mesh(geo, flagMat); cloth.castShadow = cloth.receiveShadow = true; g.add(cloth);
    cloths.push({geo, base: Float32Array.from(p.array), seed: ph[0]});
  }
  /* the A-frame sign at the way in */
  { const g = new THREE.Group(); g.position.set(SIGN.x, 0, SIGN.z); g.rotation.y = SIGN.r;
    const face = canvasTex(600, 900, (c, w, h) => { c.fillStyle = "#FAFAF6"; c.fillRect(0, 0, w, h); c.strokeStyle = "#16181A"; c.lineWidth = 16; c.strokeRect(24, 24, w - 48, h - 48);
      usFlag(c, w / 2 - 110, 70, 220, 116); say(c, "VOTE", w / 2, 330, `900 168px ${SANS}`, "#16181A"); say(c, "HERE", w / 2, 500, `900 168px ${SANS}`, "#16181A");
      c.fillStyle = "#16181A"; c.beginPath(); c.moveTo(150, 650); c.lineTo(370, 650); c.lineTo(370, 600); c.lineTo(470, 690); c.lineTo(370, 780); c.lineTo(370, 730); c.lineTo(150, 730); c.closePath(); c.fill(); wear(c, w, h, 53, 0.035); });
    const fm = std({map: face, roughness: 0.6}), frameM = std({color: "#1E1F21", roughness: 0.5});
    for (const s of [-1, 1]) {
      const pg = new THREE.Group(); pg.position.set(0, 0.92, 0); pg.rotation.x = -s * 0.2; g.add(pg);
      part(pg, BOX(0.62, 0.92, 0.012), frameM, 0, -0.46, s * 0.008);
      part(pg, new THREE.PlaneGeometry(0.58, 0.87), s > 0 ? fm : white, 0, -0.46, s * 0.0145, 0, s > 0 ? 0 : Math.PI, 0);
    }
    B.bake(g);
    block(SIGN.x, SIGN.z, 0.66, 0.44, SIGN.r);
  }

  /* ---------- what else a gym holds on the day: the judge's chair by the scanner, the scanner's cord taped down across
     the floor to the wall, a rack of basketballs, a bin by the doors, a broom in the corner, a drinking fountain ---------- */
  { const g = new THREE.Group();
    const cordM = std({color: "#141516", roughness: 0.6}), tape = std({color: "#5E6062", roughness: 0.85});
    const cz = -3.4;
    tube(g, cordM, V3(-0.18, 0.5, SCAN.z - 0.29), V3(-0.18, 0.006, SCAN.z - 0.3), 0.006, 6); tube(g, cordM, V3(-0.18, 0.006, SCAN.z - 0.3), V3(-0.18, 0.006, cz), 0.006, 6);
    tube(g, cordM, V3(-0.18, 0.006, cz), V3(-RX + 0.08, 0.006, cz), 0.006, 6);
    for (let x = -0.9; x > -RX + 0.5; x -= 1.3) part(g, BOX(0.16, 0.002, 0.06), tape, x, 0.012, cz);
    tube(g, cordM, V3(-RX + 0.08, 0.006, cz), V3(-RX + 0.08, 0.4, cz), 0.006, 6); part(g, BOX(0.02, 0.11, 0.07), white, -RX + 0.01, 0.42, cz);
    const ball = canvasTex(512, 256, (c, w, h) => { c.fillStyle = "#B8561F"; c.fillRect(0, 0, w, h); const r = rng(9);
      for (let i = 0; i < 9000; i++) { c.fillStyle = r() < 0.5 ? "rgba(70,25,5,.18)" : "rgba(255,170,110,.12)"; c.fillRect(r() * w, r() * h, 2, 2); }
      c.strokeStyle = "#1B1410"; c.lineWidth = 5; for (const x of [0, w / 4, w / 2, 3 * w / 4]) { c.beginPath(); c.moveTo(x, 0); c.lineTo(x, h); c.stroke(); }
      c.beginPath(); c.moveTo(0, h / 2); c.lineTo(w, h / 2); c.stroke(); });
    const ballM = std({map: ball, roughness: 0.75});
    const rack = new THREE.Group(); rack.position.set(bleachFront(0) - 0.9, 0, -9.6); rack.rotation.y = -Math.PI / 2; g.add(rack);
    for (const [x, z] of [[-0.55, -0.2], [0.55, -0.2], [-0.55, 0.2], [0.55, 0.2]]) tube(rack, steelMat, V3(x, 0.05, z), V3(x, 1.02, z), 0.014);
    for (const y of [0.42, 0.95]) for (const z of [-0.2, 0.2]) tube(rack, steelMat, V3(-0.58, y, z), V3(0.58, y, z), 0.012);
    for (const y of [0.42, 0.95]) for (let i = 0; i < 4; i++) part(rack, new THREE.SphereGeometry(0.12, 24, 16), ballM, -0.39 + i * 0.26, y + 0.1, 0, 0.3 * i, 0.7 * i, 0.1);
    block(rack.position.x, rack.position.z, 0.5, 1.3);
    part(g, new THREE.SphereGeometry(0.12, 24, 16), ballM, bleachFront(0) - 1.5, 0.12, -8.9, 0.4, 1.2, 0); post(bleachFront(0) - 1.5, -8.9, 0.14);
    if (!more.bin) { const bin = std({color: "#5E6164", roughness: 0.6});
      part(g, CYL(0.25, 0.22, 0.78, 24), bin, -5.55, 0.39, ZF + 0.42);
      part(g, new THREE.TorusGeometry(0.25, 0.012, 6, 28), std({color: "#1E1F21", roughness: 0.7}), -5.55, 0.78, ZF + 0.42, Math.PI / 2, 0, 0); }
    post(-5.55, ZF + 0.42, 0.3);
    part(g, roundBox(0.32, 0.36, 0.45, 0.03, 2), alu, -RX + 0.23, 0.82, -6.2); part(g, BOX(0.36, 0.5, 0.4), steelMat, -RX + 0.21, 0.4, -6.2); block(-RX + 0.22, -6.2, 0.44, 0.5);
    B.bake(g);
    chairAt(JUDGE.x, JUDGE.z, -0.35 + Math.PI);      // the judge's chair faces the doors, the way voters come
  }
  if (more.bin) placeModel(scene, more.bin, -5.55, 0, ZF + 0.46, 0.4, 0.78);
  if (more.broom) { placeModel(scene, more.broom, -RX + 0.3, 0.0, ZF + 0.9, 0.0, 1.0).rotation.z = -0.1; post(-RX + 0.3, ZF + 0.9, 0.25); }
  /* a few folded chairs leant against the back wall, the ones the day did not need */
  if (A.chair) for (let i = 0; i < 3; i++) { const ch = placeModel(scene, A.chair, 5.2 + i * 0.55, 0, ZB - 0.42, chairFacing + Math.PI + 0.05 * i); if (ch) post(5.2 + i * 0.55, ZB - 0.42, 0.28); }

  /* ---------- the scanner on its ballot box ---------- */
  const scanner = new THREE.Group(); scanner.position.set(SCAN.x, 0, SCAN.z); scene.add(scanner);
  const charcoal = std({color: "#2B2E31", roughness: 0.66}), shellM = std({color: "#C8CBCD", roughness: 0.38, roughnessMap: metalNoise}), fascia = std({color: "#232628", roughness: 0.42});
  part(scanner, roundBox(0.62, 0.8, 0.56, 0.018, 3), charcoal, 0, 0.415, 0);
  for (const [x, z] of [[-0.27, -0.24], [0.27, -0.24], [-0.27, 0.24], [0.27, 0.24]]) part(scanner, CYL(0.022, 0.022, 0.015, 12), footMat, x, 0.0075, z);
  const boxFace = canvasTex(620, 800, (g, w, h) => { g.fillStyle = "#2B2E31"; g.fillRect(0, 0, w, h); g.strokeStyle = "#17191B"; g.lineWidth = 6; rrect(g, 40, 40, w - 80, h - 80, 14); g.stroke();
    g.fillStyle = "#E8E8E3"; rrect(g, 150, 150, w - 300, 90, 8); g.fill(); say(g, "BALLOT BOX", w / 2, 197, `800 44px ${SANS}`, "#1B1D1F");
    g.fillStyle = "#3A3E42"; rrect(g, w - 120, h / 2 - 40, 34, 80, 8); g.fill(); wear(g, w, h, 61, 0.008); });
  part(scanner, new THREE.PlaneGeometry(0.6, 0.78), std({map: boxFace, roughness: 0.46, roughnessMap: metalNoise}), 0, 0.415, 0.2812).castShadow = false;
  part(scanner, CYL(0.012, 0.012, 0.012, 14), alu, 0.21, 0.43, 0.287, Math.PI / 2, 0, 0);
  /* the scanner itself: a grey shell, a dark front with the slot, the screen angled up toward the voter */
  part(scanner, roundBox(0.6, 0.19, 0.52, 0.03, 3), shellM, 0, 0.915, -0.01);
  part(scanner, roundBox(0.58, 0.12, 0.03, 0.01, 2), fascia, 0, 0.915, SCAN.front - SCAN.z - 0.012);
  part(scanner, BOX(0.31, 0.011, 0.004), basic("#020202"), 0, SCAN.slotY, SCAN.front - SCAN.z + 0.002).castShadow = false;
  const tray = part(scanner, BOX(0.36, 0.007, 0.075), fascia, 0, SCAN.slotY - 0.012, SCAN.front - SCAN.z + 0.034); tray.rotation.x = 6 * D2R;
  const label = canvasTex(512, 64, (g, w, h) => { g.fillStyle = "#232628"; g.fillRect(0, 0, w, h); say(g, "INSERT BALLOT", w / 2, h / 2 + 2, `700 34px ${SANS}`, "#E1E3E0");
    g.fillStyle = "#E1E3E0"; for (const x of [70, w - 70]) { g.beginPath(); g.moveTo(x - 12, 22); g.lineTo(x + 12, 22); g.lineTo(x, 44); g.closePath(); g.fill(); } });
  part(scanner, new THREE.PlaneGeometry(0.24, 0.03), std({map: label, roughness: 0.5}), 0, SCAN.slotY + 0.032, SCAN.front - SCAN.z + 0.004).castShadow = false;
  const ledMat = std({color: "#2A2A22", emissive: new THREE.Color("#FFB02E"), emissiveIntensity: 0.0});
  part(scanner, BOX(0.022, 0.008, 0.004), ledMat, 0.21, SCAN.slotY, SCAN.front - SCAN.z + 0.002).castShadow = false;
  const head = new THREE.Group(); head.position.set(0, 1.0, SCREEN.z - SCAN.z + 0.02); head.rotation.x = -0.62; scanner.add(head);
  part(head, roundBox(0.27, 0.19, 0.045, 0.012, 2), fascia, 0, 0.07, 0);
  part(scanner, BOX(0.14, 0.04, 0.05), shellM, 0, 1.02, 0.11);      // the screen's neck, behind it
  const scr = document.createElement("canvas"); scr.width = 640; scr.height = 400;
  const screenTex = new THREE.CanvasTexture(scr); screenTex.colorSpace = THREE.SRGBColorSpace; screenTex.anisotropy = 8;
  part(head, new THREE.PlaneGeometry(0.224, 0.14), printed(screenTex, 1.3), 0, 0.07, 0.0232).castShadow = false;
  const cover = part(head, new THREE.PlaneGeometry(0.25, 0.165), std({color: "#000000", roughness: 0.32, transparent: true, opacity: 0.1, depthWrite: false}), 0, 0.07, 0.0237); cover.castShadow = false;      // an anti-glare cover
  block(SCAN.x, SCAN.z, 0.66, 0.6);
  const sg = scr.getContext("2d");
  let shown = "";
  const BEFORE = 1247;
  let countedUntil = 0;      // the place: the screen says the ballot was counted until this second of the place's clock
  function drawScreen(state, p, roll){
    const key = state + ":" + Math.round(p * 40) + ":" + Math.round(roll * 24); if (key === shown) return; shown = key;
    const g = sg, W = 640, Hh = 400, cx = W / 2;
    g.fillStyle = "#121A17"; g.fillRect(0, 0, W, Hh); g.fillStyle = "#0B110F"; g.fillRect(0, 0, W, 54);
    say(g, "General Election  ·  November 3, 2026", cx, 28, `600 24px ${SANS}`, "#C9D2CD");
    if (state === 0) {
      say(g, "Insert your ballot", cx, 150, `700 54px ${SANS}`, "#FFFFFF");
      g.fillStyle = "#8FD0A8"; g.beginPath(); g.moveTo(cx - 32, 210); g.lineTo(cx + 32, 210); g.lineTo(cx, 255); g.closePath(); g.fill();
    } else if (state === 1) {
      say(g, "Reading your ballot…", cx, 150, `700 48px ${SANS}`, "#FFFFFF");
      g.fillStyle = "#27342F"; rrect(g, 120, 212, 400, 24, 12); g.fill(); g.fillStyle = "#3FB673"; rrect(g, 120, 212, Math.max(24, 400 * p), 24, 12); g.fill();
    } else {
      const k = Math.min(1, p * 3); g.save(); g.translate(cx, 128); g.scale(0.6 + 0.4 * k, 0.6 + 0.4 * k);
      g.fillStyle = "#2E9D5B"; g.beginPath(); g.arc(0, 0, 54, 0, 7); g.fill();
      g.strokeStyle = "#FFFFFF"; g.lineWidth = 13; g.lineCap = g.lineJoin = "round"; g.beginPath(); g.moveTo(-25, 2); g.lineTo(-6, 22); g.lineTo(27, -20); g.stroke(); g.restore();
      say(g, "Your ballot was counted", cx, 236, `700 46px ${SANS}`, "#FFFFFF");
      say(g, "Thank you for voting", cx, 286, `500 30px ${SANS}`, "#B8D7C4");
    }
    /* the count: the screen redraws it, one more, the moment the ballot is counted (a screen's quick change, not a rolling
       counter's) */
    g.fillStyle = "#0B110F"; g.fillRect(0, 330, W, 70);
    say(g, "Ballots cast", 196, 366, `600 26px ${SANS}`, "#9FB2A8", "left");
    g.font = `700 34px ${SANS}`; g.textAlign = "left"; g.textBaseline = "middle"; g.fillStyle = "#FFFFFF";
    const a = BEFORE.toLocaleString("en-US"), b = (BEFORE + 1).toLocaleString("en-US"), x0 = 372, stem = a.slice(0, -1), wStem = g.measureText(stem).width;
    g.fillText(stem, x0, 366);
    g.globalAlpha = 1 - roll; g.fillText(a.slice(-1), x0 + wStem, 366);
    g.globalAlpha = roll; g.fillText(b.slice(-1), x0 + wStem, 366); g.globalAlpha = 1;
    screenTex.needsUpdate = true;
  }
  drawScreen(place ? 2 : 0, place ? 1 : 0, place ? 1 : 0);

  /* ---------- the ballot in hand, for the crossing ---------- */
  const bGeo = new THREE.PlaneGeometry(BWd, BHt, 10, 14), flat = Float32Array.from(bGeo.attributes.position.array);
  const ballot = new THREE.Mesh(bGeo, ballotMat); ballot.castShadow = ballot.receiveShadow = true; ballot.visible = !place; dyn.add(ballot);
  const bend = (curl, droop) => {      // paper held at its foot bows a little across and sags toward its free end
    const p = bGeo.attributes.position;
    for (let i = 0; i < p.count; i++) { const x = flat[i * 3], y = flat[i * 3 + 1]; p.setZ(i, -0.006 * curl * (x / (BWd / 2)) ** 2 - 0.022 * droop * Math.max(0, (y + BHt / 2) / BHt) ** 2.2); }
    p.needsUpdate = true; bGeo.computeVertexNormals();
  };

  /* ---------- light: the hall's lamps over the polling place, the sun through the west windows, and the room itself (worked out below) ---------- */
  scene.add(new THREE.HemisphereLight("#E9ECF8", "#6E5E4C", LOOK.hemi));
  const spot = (x, z, tx, tz, k, shadow) => {
    const s = new THREE.SpotLight("#FFE9CF", LOOK.spot * k, 16, 0.95, 1.0, 2.0); s.position.set(x, 6.9, z); s.target.position.set(tx, 0, tz);
    if (shadow) { s.castShadow = true; s.shadow.mapSize.setScalar(lean ? 512 : 2048); s.shadow.bias = -0.00025; s.shadow.normalBias = 0.02; s.shadow.camera.near = 2.5; s.shadow.camera.far = 12; s.shadow.intensity = 0.85; }
    scene.add(s, s.target); return s;
  };
  spot(0, 0, 0.3, -1.6, 1.0, true);
  spot(-5.2, 0, -2.6, 1.6, 0.95, !lean);
  spot(5.2, 0, 2.4, 0.6, 0.85, !lean);
  if (!lean) {      /* the rest of the hall: the lamps over the far court and the doors, without shadows */
    for (const [x, z] of [[-5.2, -9.8], [5.2, -9.8], [0, -4.9], [-5.2, 4.9], [5.2, 4.9], [0, 9.8]]) { const p = new THREE.PointLight("#FFE9CF", LOOK.point, 13, 1.8); p.position.set(x, 6.85, z); scene.add(p); }
  }
  /* the sun: a directional light whose shadow covers the windows' light where it lands, moved as the sun sinks */
  const sun = new THREE.DirectionalLight("#FFC27A", 0); sun.castShadow = !opts.noSunShadow;
  sun.shadow.mapSize.setScalar(lean ? 1024 : 2048); sun.shadow.bias = -0.0004; sun.shadow.normalBias = 0.03; sun.shadow.camera.near = 0.5; sun.shadow.camera.far = 48;
  sun.shadow.camera.left = -13; sun.shadow.camera.right = 13; sun.shadow.camera.top = 3.6; sun.shadow.camera.bottom = -3.6; sun.shadow.camera.updateProjectionMatrix();
  scene.add(sun, sun.target);
  const WINC = V3(-RX - 0.24, (WIN.y0 + WIN.y1) / 2, 0);      // the middle of the row of west windows
  let sunAlt = SUN.alt0, sunD = sunDir(sunAlt), sunCol = sunLight(sunAlt);
  const setSun = alt => {
    sunAlt = alt; sunD = sunDir(alt); sunCol = sunLight(alt);
    const T = WINC.clone().addScaledVector(sunD, 12); sun.target.position.copy(T); sun.position.copy(T).addScaledVector(sunD, -24);
    sun.color.copy(sunCol.color); sun.intensity = LOOK.sun * sunCol.k;
    skyMat.uniforms.uDusk.value = skyK(alt);
  };
  setSun(sunAlt);

  /* the floor's contact shadows: where a leg, a foot or a box meets the boards the room's light cannot reach */
  FU.uAO.value = canvasTex(1024, 1024, (g, W, H) => {
    g.fillStyle = "#fff"; g.fillRect(0, 0, W, H);
    const bx = FU.uAOBox.value, P = (x, z) => [(x - bx.x) / bx.z * W, (1 - (z - bx.y) / bx.w) * H], s = W / bx.z;
    const blob = (x, z, r, a) => { const [px, py] = P(x, z), gr = g.createRadialGradient(px, py, 0, px, py, r * s); gr.addColorStop(0, `rgba(0,0,0,${a})`); gr.addColorStop(1, "rgba(0,0,0,0)"); g.fillStyle = gr; g.fillRect(px - r * s, py - r * s, 2 * r * s, 2 * r * s); };
    const rect = (x, z, w, d, r, a, rot = 0) => { for (let k = 0; k < 6; k++) { const e = r * (1 - k / 6); g.save(); const [px, py] = P(x, z); g.translate(px, py); g.rotate(-rot); g.fillStyle = `rgba(0,0,0,${a / 6})`;
      rrect(g, (-w / 2 - e) * s, (-d / 2 - e) * s, (w + 2 * e) * s, (d + 2 * e) * s, Math.max(1, e * s)); g.fill(); g.restore(); } };
    for (const b of BOOTHS) { rect(b.x, b.z, 0.47, 0.62, 0.35, 0.28); for (const [x, z] of [[-0.21, -0.28], [0.21, -0.28], [-0.21, 0.28], [0.21, 0.28]]) blob(b.x + x, b.z + z, 0.07, 0.55); }
    rect(TABLE.x, TABLE.z, 0.76, 1.83, 0.4, 0.3); for (const z of [-0.78, 0.78]) for (const x of [-0.3, 0.3]) blob(TABLE.x + x, TABLE.z + z, 0.07, 0.5);
    for (const dz of [-0.45, 0.48]) rect(TABLE.x - 0.72, TABLE.z + dz, 0.5, 0.55, 0.15, 0.35);
    rect(SCAN.x, SCAN.z, 0.62, 0.56, 0.22, 0.85); rect(JUDGE.x, JUDGE.z, 0.5, 0.55, 0.15, 0.35, 0.35);
    for (const [x, z] of FLAGS) blob(x, z, 0.3, 0.55);
    rect(SIGN.x, SIGN.z, 0.62, 0.42, 0.2, 0.4, SIGN.r);
    rect((bleachFront(0) + 6) / 2, 0.4, 6 - bleachFront(0), 16, 0.5, 0.5);
  }, {srgb: false});

  B.build(scene);

  /* ---------- the air: the sun's shafts through the west windows, with dust turning in them ---------- */
  const fx = new THREE.Scene();      // drawn after the room, over it, with the room's depth to stop at what it meets
  const DU = {tDepth: {value: null}, uRes: {value: new THREE.Vector2(2, 2)}, uProj: {value: new THREE.Vector2(1, 1)}, uCamFwd: {value: V3(0, 0, -1)},
              uColor: {value: new THREE.Color()}, uDensity: {value: LOOK.shaft}, uTime: {value: 0}, uDust: {value: LOOK.dust}};
  const shaftMat = new THREE.ShaderMaterial({uniforms: Object.assign({uO: {value: V3()}, uU: {value: V3()}, uV: {value: V3()}, uN: {value: V3()}, uHalf: {value: new THREE.Vector2(1, 1)}, uLen: {value: 24}}, DU),
    side: THREE.BackSide, depthTest: false, depthWrite: false, transparent: true, blending: THREE.AdditiveBlending,
    vertexShader: "varying vec3 vWp; void main(){ vec4 w = modelMatrix * vec4(position, 1.0); vWp = w.xyz; gl_Position = projectionMatrix * viewMatrix * w; }",
    fragmentShader: `uniform sampler2D tDepth; uniform vec2 uRes, uProj, uHalf; uniform vec3 uCamFwd, uColor, uO, uU, uV, uN; uniform float uDensity, uTime, uLen;
      varying vec3 vWp;
      float h3(vec3 p){ return fract(sin(dot(p, vec3(127.1, 311.7, 74.7))) * 43758.5453); }
      float n3(vec3 p){ vec3 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f);
        return mix(mix(mix(h3(i), h3(i + vec3(1, 0, 0)), f.x), mix(h3(i + vec3(0, 1, 0)), h3(i + vec3(1, 1, 0)), f.x), f.y),
                   mix(mix(h3(i + vec3(0, 0, 1)), h3(i + vec3(1, 0, 1)), f.x), mix(h3(i + vec3(0, 1, 1)), h3(i + vec3(1, 1, 1)), f.x), f.y), f.z); }
      float bar(float x, float c, float w){ return 1.0 - smoothstep(w, w + 0.02, abs(x - c)); }
      void main(){
        vec3 cp = cameraPosition, dir = normalize(vWp - cp);
        vec3 rel = cp - uO; vec3 p = vec3(dot(rel, uU), dot(rel, uV), dot(rel, uN)); vec3 r = vec3(dot(dir, uU), dot(dir, uV), dot(dir, uN));
        vec3 lo = vec3(-uHalf, 0.0), hi = vec3(uHalf, uLen);
        vec3 inv = 1.0 / (abs(r) + 1e-6) * sign(r + 1e-7);
        vec3 ta = (lo - p) * inv, tb = (hi - p) * inv, tmin = min(ta, tb), tmax = max(ta, tb);
        float t0 = max(max(tmin.x, tmin.y), max(tmin.z, 0.0)), t1 = min(min(tmax.x, tmax.y), tmax.z);
        vec2 uv = gl_FragCoord.xy / uRes; float dz = texture2D(tDepth, uv).r;      /* the room: how far along the view axis it stands here */
        float tScene = dz / max(dot(dir, uCamFwd), 0.05); t1 = min(t1, tScene);
        if (t1 <= t0) discard;
        float acc = 0.0; const int N = 12; float dt = (t1 - t0) / float(N);
        float phase = 0.6 + 1.2 * pow(max(-dot(dir, uN), 0.0), 3.0);      /* dust scatters most toward you when you look toward the window */
        for (int i = 0; i < N; i++) {
          float t = t0 + (float(i) + 0.5) * dt; vec3 q = p + r * t;
          float eu = 1.0 - smoothstep(uHalf.x - 0.35, uHalf.x, abs(q.x)), ev = 1.0 - smoothstep(uHalf.y - 0.3, uHalf.y, abs(q.y));
          float mull = 1.0 - 0.85 * max(max(bar(q.x, -uHalf.x / 3.0, 0.03), bar(q.x, uHalf.x / 3.0, 0.03)), bar(q.y, -uHalf.y * 0.1, 0.03));      /* the frame's bars */
          vec3 wq = uO + uU * q.x + uV * q.y + uN * q.z;
          float nz = 0.7 + 0.8 * n3(wq * 0.5 + vec3(uTime * 0.02, -uTime * 0.035, uTime * 0.01)) * n3(wq * 1.6 - vec3(uTime * 0.04, uTime * 0.02, 0.0));
          acc += eu * ev * mull * nz * dt;
        }
        float lit = 1.0 - exp(-acc * uDensity);      /* the air only ever gets so bright: a beam seen along its length does not burn out */
        gl_FragColor = vec4(uColor * lit * phase, 1.0);
      }`});
  const shafts = [];
  for (const w of windows) {
    const m = shaftMat.clone(); m.uniforms = Object.assign({}, m.uniforms, {tDepth: DU.tDepth, uRes: DU.uRes, uProj: DU.uProj, uCamFwd: DU.uCamFwd, uColor: DU.uColor, uDensity: DU.uDensity, uTime: DU.uTime});
    m.uniforms.uO = {value: w.centre.clone()}; m.uniforms.uU = {value: V3()}; m.uniforms.uV = {value: V3()}; m.uniforms.uN = {value: V3()}; m.uniforms.uHalf = {value: new THREE.Vector2(w.w / 2, w.h / 2)}; m.uniforms.uLen = {value: 26};
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1), m); mesh.frustumCulled = false; mesh.visible = !lean; fx.add(mesh);
    shafts.push({mesh, w});
  }
  /* the motes: points drifting inside each shaft, lit where the beam is */
  const motes = [];
  { const per = lean ? 120 : 360, R = rng(77);
    const moteMat = new THREE.ShaderMaterial({uniforms: Object.assign({uO: {value: V3()}, uU: {value: V3()}, uV: {value: V3()}, uN: {value: V3()}, uHalf: {value: new THREE.Vector2(1, 1)}, uSize: {value: 300}}, DU),
      transparent: true, depthWrite: false, depthTest: true, blending: THREE.AdditiveBlending,
      vertexShader: `attribute vec4 seed; uniform vec3 uO, uU, uV, uN; uniform vec2 uHalf; uniform float uTime, uSize; varying float vK;
        void main(){
          float s = seed.w, t = uTime;
          float lu = seed.x * uHalf.x + 0.12 * sin(t * 0.21 + s * 6.0) + 0.05 * sin(t * 0.9 + s * 11.0);
          float lv = seed.y * uHalf.y + 0.09 * sin(t * 0.17 + s * 9.0) - 0.01 * t * fract(s * 3.1);
          float ln = mod(seed.z * 24.0 + t * (0.05 + 0.1 * fract(s * 5.3)), 24.0);
          float eu = 1.0 - smoothstep(uHalf.x - 0.4, uHalf.x, abs(lu)), ev = 1.0 - smoothstep(uHalf.y - 0.35, uHalf.y, abs(lv));
          vec3 w = uO + uU * lu + uV * lv + uN * ln;
          vec4 mv = viewMatrix * vec4(w, 1.0); gl_Position = projectionMatrix * mv;
          float tw = 0.35 + 0.65 * pow(0.5 + 0.5 * sin(t * (1.5 + 2.0 * fract(s * 7.7)) + s * 20.0), 3.0);
          vK = eu * ev * tw * (0.5 + 0.5 * fract(s * 13.0));
          gl_PointSize = clamp(uSize * (0.6 + 0.8 * fract(s * 2.3)) / max(-mv.z, 0.5), 1.0, 5.0);
        }`,
      fragmentShader: `uniform vec3 uColor; uniform float uDust; varying float vK; void main(){ vec2 c = gl_PointCoord - 0.5; float d = dot(c, c) * 4.0; if (d > 1.0) discard;
        float a = (1.0 - d) * (1.0 - d); gl_FragColor = vec4(uColor * a * vK * uDust * 0.09, 1.0); }`});
    for (const sh of shafts) {
      const g = new THREE.BufferGeometry(), pos = new Float32Array(per * 3), sd = new Float32Array(per * 4);
      for (let i = 0; i < per; i++) { sd[i * 4] = R() * 2 - 1; sd[i * 4 + 1] = R() * 2 - 1; sd[i * 4 + 2] = R(); sd[i * 4 + 3] = R(); }
      g.setAttribute("position", new THREE.BufferAttribute(pos, 3)); g.setAttribute("seed", new THREE.BufferAttribute(sd, 4));
      const m = moteMat.clone(); m.uniforms = Object.assign({}, m.uniforms, {uColor: DU.uColor, uTime: DU.uTime, uDust: DU.uDust});
      m.uniforms.uO = sh.mesh.material.uniforms.uO; m.uniforms.uU = sh.mesh.material.uniforms.uU; m.uniforms.uV = sh.mesh.material.uniforms.uV; m.uniforms.uN = sh.mesh.material.uniforms.uN; m.uniforms.uHalf = sh.mesh.material.uniforms.uHalf;
      m.uniforms.uSize = {value: 300};
      const pts = new THREE.Points(g, m); pts.frustumCulled = false; fx.add(pts); motes.push({pts, m});
    }
  }
  const placeShafts = () => {      /* each shaft is the window's rectangle pushed along the sun's way, as far as the room */
    const up = V3(0, 1, 0), k = sunCol.k;
    for (const {mesh, w} of shafts) {
      const u = mesh.material.uniforms; const N = sunD.clone(), U = up.clone().cross(N).normalize(), V = N.clone().cross(U).normalize();
      u.uU.value.copy(U); u.uV.value.copy(V); u.uN.value.copy(N);
      const L = u.uLen.value;
      mesh.matrixAutoUpdate = false; mesh.matrix.makeBasis(U.clone().multiplyScalar(w.w), V.clone().multiplyScalar(w.h), N.clone().multiplyScalar(L)).setPosition(w.centre.clone().addScaledVector(N, L / 2));
    }
    DU.uColor.value.copy(sunCol.color).multiplyScalar(k * 2.3);
    const show = k > 0.01 && !lean; for (const {mesh} of shafts) mesh.visible = show; for (const {pts} of motes) pts.visible = k > 0.01;
  };
  placeShafts();

  /* ---------- the walk, the look, the hand (the crossing) ---------- */
  const P0 = V3(0.36, 0, 4.55), P1 = V3(0.05, 0, -1.6), PATH = P1.clone().sub(P0), LEN = PATH.length(), HEAD = Math.atan2(-PATH.x, -PATH.z);
  const WALK = {t0: 0.4, t1: 6.0, ta: 1.0, td: 1.5};
  const vc = 1 / (WALK.t1 - WALK.t0 - WALK.ta / 2 - WALK.td / 2);      // the cruising pace, as a share of the way each second
  const walkS = t => {      // how far along the way, 0 to 1, with a smooth start and stop
    const u = t - WALK.t0, T = WALK.t1 - WALK.t0; if (u <= 0) return 0; if (u >= T) return 1;
    if (u < WALK.ta) { const x = u / WALK.ta; return vc * WALK.ta * (x * x * x - x * x * x * x / 2); }
    if (u < T - WALK.td) return vc * (WALK.ta / 2 + (u - WALK.ta));
    const x = (T - u) / WALK.td; return 1 - vc * WALK.td * (x * x * x - x * x * x * x / 2);
  };
  const KEYS = [[0, 11, 1.5], [1.1, 7, 3], [2.1, 16, -4], [3.2, -22, -1], [4.2, -2, -9], [4.9, 0, -15]];      // where the eyes go: time, turn (left +), tilt (up +), in degrees
  /* a window narrower than a wide screen (a phone held upright, most of all) sees less to either side, so the eyes turn
     further: to the check-in table on the left as you come in, across the gym to the row of booths on the right, then to
     the scanner */
  const KEYS_TALL = [[0, 29, -9], [1.0, 31, -11], [2.4, -30, -6], [3.0, -33, -5], [4.2, -2, -9], [4.9, 0, -15]];
  const keyed = (t, k = KEYS) => {      // Catmull-Rom through the keys
    if (t <= k[0][0]) return [k[0][1], k[0][2]]; if (t >= k[k.length - 1][0]) return [k[k.length - 1][1], k[k.length - 1][2]];
    let i = 0; while (t > k[i + 1][0]) i++;
    const p0 = k[Math.max(0, i - 1)], p1 = k[i], p2 = k[i + 1], p3 = k[Math.min(k.length - 1, i + 2)], s = (t - p1[0]) / (p2[0] - p1[0]);
    const cr = (a, b, c, d) => 0.5 * ((2 * b) + (-a + c) * s + (2 * a - 5 * b + 4 * c - d) * s * s + (-a + 3 * b - 3 * c + d) * s * s * s);
    return [cr(p0[1], p1[1], p2[1], p3[1]), cr(p0[2], p1[2], p2[2], p3[2])];
  };
  const aim = (from, to) => { const d = to.clone().sub(from); return [Math.atan2(-d.x, -d.z) / D2R, Math.atan2(d.y, Math.hypot(d.x, d.z)) / D2R]; };
  const FEED_LOOK = SCREEN.clone().add(V3(0, 0.12, 0));
  const eye = V3(), tmpE = new THREE.Euler(0, 0, 0, "YXZ");
  const vfovOf = a => a >= 1 ? 50 : Math.min(74, 2 * Math.atan(Math.tan(25 * D2R) / Math.pow(a, 0.62)) / D2R);
  const halfW = a => Math.atan(Math.tan(vfovOf(a) / 2 * D2R) * a) / D2R;      // half the view's width, in degrees
  const WIDE = halfW(16 / 9), TALL = halfW(375 / 812), tallness = a => clamp((WIDE - halfW(a)) / (WIDE - TALL));
  const STILL_LOOK = SCREEN.clone().add(V3(0, 0.3, 0));
  let focusNow = 0;      // the lens's focus for the crossing (metres); 0 means the place's own autofocus
  const focusPlan = {up: 0, slot: 0, screen: 0};      // how far the lens has pulled from the gym to the ballot, the slot, the screen
  const pose = (t, out) => {
    if (ST.still) {      /* the one still picture: standing at the scanner as it says the ballot was counted, the gym beyond it */
      eye.copy(P1); eye.y = 1.62; const [yw, pc] = aim(eye, STILL_LOOK);
      out.position.copy(eye); tmpE.set(pc * D2R, yw * D2R, 0, "YXZ"); out.quaternion.setFromEuler(tmpE); out.fov = vfovOf(aspect); out.updateProjectionMatrix(); focusNow = 1.1; return;
    }
    const s = walkS(t), sp = (walkS(t + 0.03) - walkS(t - 0.03)) / 0.06 / vc;      // speed, as a share of the cruise
    eye.copy(P0).addScaledVector(PATH, s); eye.x += 0.12 * Math.sin(Math.PI * s);
    const step = s * LEN / 0.72;      // a step every 72 cm
    eye.y = 1.625 + (0.009 * Math.cos(2 * Math.PI * step) - 0.004) * sp;
    eye.x += 0.008 * Math.sin(Math.PI * step) * sp;
    /* leaning over the machine to feed it, then in toward the screen */
    const over = smooth(seg(t, 5.7, 6.4)) * (1 - smooth(seg(t, 7.2, 7.9))), leanIn = inOut(seg(t, 7.75, 9.2));
    eye.y -= 0.05 * over + 0.08 * leanIn; eye.z -= 0.07 * over + 0.3 * leanIn;
    let [yaw, pitch] = keyed(t);
    const tw = tallness(aspect); if (tw > 0) { const [y2, p2] = keyed(t, KEYS_TALL); yaw = mix(yaw, y2, tw); pitch = mix(pitch, p2, tw); }
    const fl = aim(eye, FEED_LOOK), sc = aim(eye, SCREEN);
    const wf = smooth(seg(t, 4.6, 5.9)), ws = smooth(seg(t, 6.95, 7.8));
    yaw = mix(yaw, fl[0], wf); pitch = mix(pitch, fl[1], wf); yaw = mix(yaw, sc[0], ws); pitch = mix(pitch, sc[1], ws);
    pitch += 0.25 * Math.sin(t * 1.3 + 0.4) + 0.12 * Math.sin(t * 0.53);      // breathing
    yaw += 0.2 * Math.sin(t * 0.41 + 1.1);
    { const k = 1 - 0.6 * smooth(seg(t, 5.5, 6.5)); yaw -= pt.sx * 3.0 * k; pitch -= pt.sy * 2.0 * k; }
    out.position.copy(eye);
    tmpE.set(pitch * D2R, yaw * D2R, 0.004 * Math.sin(Math.PI * step) * sp + 0.002 * Math.sin(t * 0.7), "YXZ"); out.quaternion.setFromEuler(tmpE);
    out.fov = vfovOf(aspect) - 8 * leanIn * (aspect >= 1 ? 1 : 0.6); out.updateProjectionMatrix();
    /* the lens: deep focus across the gym; a pull to the ballot as it comes up, to the slot, then to the screen */
    const up = smooth(seg(t, 4.4, 5.4)), toSlot = smooth(seg(t, 6.3, 6.7)), toScreen = smooth(seg(t, 7.6, 8.2));
    focusPlan.up = up; focusPlan.slot = toSlot; focusPlan.screen = toScreen;
  };
  /* the ballot: carried low at the right, raised to be seen, carried to the slot, pushed in, taken by the rollers */
  const body = new THREE.Object3D(), handPos = V3(), handQ = new THREE.Quaternion(), slotQ = new THREE.Quaternion().setFromEuler(new THREE.Euler(-Math.PI / 2 - 6 * D2R, 0, 0));
  const at = s => SLOT.clone().addScaledVector(FEED, s - BHt / 2);      // the ballot's middle when its leading edge is s past the slot's mouth
  const CARRY = {p: V3(0.19, -0.68, -0.3), r: new THREE.Euler(-0.35, 0.25, -0.2)}, SHOW = {p: V3(0.04, -0.3, -0.45), r: new THREE.Euler(-39 * D2R, -0.05, 0.03)};
  const qa = new THREE.Quaternion(), qb = new THREE.Quaternion(), pa = V3(), pb = V3();
  const placeBallot = (t, eyeNow) => {
    const still = ST.still ? 1 : 0;
    body.position.copy(eyeNow); body.rotation.set(0, HEAD, 0); body.updateMatrixWorld();
    const up = smooth(seg(t, 4.3, 5.55));
    pa.copy(CARRY.p).lerp(SHOW.p, up); pa.x += pt.sx * 0.03 * up * (1 - still);
    qa.setFromEuler(CARRY.r).slerp(qb.setFromEuler(SHOW.r), up);
    const sway = 0.003 * (1 - seg(t, 6.6, 6.8)) * (1 - still);
    pa.x += Math.sin(t * 7.1) * sway; pa.y += Math.sin(t * 8.9 + 1) * sway * 0.8; pa.z += Math.sin(t * 5.3 + 2) * sway * 0.5;
    handPos.copy(pa).applyMatrix4(body.matrixWorld); handQ.copy(body.quaternion).multiply(qa);
    /* to the slot: a gentle arc, squaring it to the slot */
    const go = inOut(seg(t, 5.6, 6.45));
    let s = -0.03;
    s += 0.035 * inOut(seg(t, 6.45, 6.72));      // you push it in
    s += 0.006 * smooth(seg(t, 6.72, 6.8));      // the rollers catch it
    s += (BHt + 0.02 - 0.011) * inOut(seg(t, 6.8, 7.3));      // and draw it through
    pb.copy(at(s)); pb.y += 0.05 * Math.sin(Math.PI * go) * (1 - go);
    if (t > 6.8 && t < 7.3) pb.y += Math.sin(t * 97) * 0.0006;
    ballot.position.copy(handPos).lerp(pb, go); ballot.quaternion.copy(handQ).slerp(slotQ, go);
    ballot.visible = s < BHt + 0.005 || go < 1;
    bend(1 - 0.7 * seg(t, 6.2, 6.7), 1 - 0.8 * seg(t, 5.8, 6.5));
  };
  /* the machine */
  const machine = t => {
    let state = 0, p = 0, roll = 0;
    if (t >= 6.78) { state = 1; p = seg(t, 6.78, 7.75); }
    if (t >= 7.8) { state = 2; p = seg(t, 7.8, 8.2); roll = seg(t, 7.86, 7.98); }
    drawScreen(state, p, roll);
    if (state === 1) { ledMat.emissive.set("#FFB02E"); ledMat.emissiveIntensity = Math.sin(t * 26) > 0 ? 3.0 : 0.4; }
    else { ledMat.emissive.set("#35E16A"); ledMat.emissiveIntensity = state === 2 ? 3.2 : 0.9; }
  };
  /* what moves whether you walk or sit: the flags in the vents' air (in gusts), the clock's second hand, the LED breathing */
  const alive = (t, gust) => {
    for (const h of hands) { if (h.k === "wall_clock_second_hand") h.node.rotation.z = -((17 + t) * 6 - h.rest) * D2R; }
    if (!ST.still) for (const c of cloths) {
      const p = c.geo.attributes.position, uv = c.geo.attributes.uv, b = c.base, g = 0.6 + 0.8 * gust;
      for (let i = 0; i < p.count; i++) { const u = uv.getX(i), v = 1 - uv.getY(i);
        p.setZ(i, b[i * 3 + 2] + g * (0.014 * u * Math.sin(t * 1.3 + u * 5.0 + v * 1.5 + c.seed) + 0.006 * u * Math.sin(t * 2.3 + u * 9.0 + c.seed * 2.0))); }
      p.needsUpdate = true; c.geo.computeVertexNormals();
    }
    DU.uTime.value = t;
  };

  /* ---------- the place's own camera: a pose, turned by the reader, walked, seated ---------- */
  const PZ = {x: 0.36, y: 1.62, z: 6.2, yaw: 0, pitch: -3, fovK: 1};
  const idle = {t: 0};
  const applyPose = (t, out, bob = 0, roll = 0) => {
    out.position.set(PZ.x + 0.006 * Math.sin(t * 0.7) * (1 - ST.still), PZ.y + bob + 0.004 * Math.sin(t * 1.1) * (1 - ST.still), PZ.z);
    const pitch = PZ.pitch + (ST.still ? 0 : 0.18 * Math.sin(t * 1.3 + 0.4) + 0.08 * Math.sin(t * 0.53)), yaw = PZ.yaw + (ST.still ? 0 : 0.12 * Math.sin(t * 0.41 + 1.1));
    tmpE.set(pitch * D2R, yaw * D2R, roll, "YXZ"); out.quaternion.setFromEuler(tmpE);
    out.fov = (aspect >= 1 ? 46 : vfovOf(aspect) - 2) * PZ.fovK; out.updateProjectionMatrix();
  };
  /* a reader walking cannot pass a wall, the bleachers, a booth, the table, the scanner, a flag or a chair */
  const RAD = 0.34;
  const collide = (x, z) => {
    x = clamp(x, -RX + 0.45, RX - 0.45); z = clamp(z, ZF + 0.5, ZB - 0.5);
    for (let pass = 0; pass < 3; pass++) for (const o of obstacles) {
      if (o.rad != null) { const dx = x - o.x, dz = z - o.z, d = Math.hypot(dx, dz), m = o.rad + RAD; if (d < m) { const k = d > 1e-4 ? m / d : 1; x = o.x + dx * k; z = o.z + dz * k; if (d <= 1e-4) x += m; } continue; }
      const c = Math.cos(o.r || 0), s = Math.sin(o.r || 0), dx = x - o.x, dz = z - o.z, lx = dx * c - dz * s, lz = dx * s + dz * c;      // into the box's own frame
      const hw = o.w / 2 + RAD, hd = o.d / 2 + RAD;
      if (Math.abs(lx) < hw && Math.abs(lz) < hd) {
        const px = hw - Math.abs(lx), pz = hd - Math.abs(lz); let nx = 0, nz = 0;
        if (px < pz) nx = Math.sign(lx || 1) * px; else nz = Math.sign(lz || 1) * pz;
        x += nx * c + nz * s; z += -nx * s + nz * c;
      }
    }
    return [x, z];
  };

  /* ---------- drawing: the room into a float buffer (once more, mirrored, for the floor's finish), the air over it, then the lens ---------- */
  const samples = opts.samples != null ? opts.samples : (lean ? 0 : 4);
  const rtMain = new THREE.WebGLRenderTarget(2, 2, {type: THREE.HalfFloatType, samples, depthTexture: new THREE.DepthTexture(2, 2, THREE.UnsignedIntType)});
  const rtGlow = new THREE.WebGLRenderTarget(2, 2, {type: THREE.HalfFloatType, generateMipmaps: true, minFilter: THREE.LinearMipmapLinearFilter});
  const rtDepth = new THREE.WebGLRenderTarget(2, 2, {type: THREE.HalfFloatType, minFilter: THREE.NearestFilter, magFilter: THREE.NearestFilter});
  const rtAO = new THREE.WebGLRenderTarget(2, 2, {}), rtAO2 = new THREE.WebGLRenderTarget(2, 2, {});
  const rtDof = new THREE.WebGLRenderTarget(2, 2, {type: THREE.HalfFloatType});
  const rtFocus = [new THREE.WebGLRenderTarget(1, 1, {type: THREE.HalfFloatType, minFilter: THREE.NearestFilter, magFilter: THREE.NearestFilter}), new THREE.WebGLRenderTarget(1, 1, {type: THREE.HalfFloatType, minFilter: THREE.NearestFilter, magFilter: THREE.NearestFilter})];
  let focusPing = 0;
  const qScene = new THREE.Scene(), qCam = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1), quad = new THREE.Mesh(new THREE.PlaneGeometry(2, 2)); quad.frustumCulled = false; qScene.add(quad);
  const qmat = (uniforms, frag, defines) => new THREE.ShaderMaterial({uniforms, vertexShader: QUAD_VERT, fragmentShader: frag, depthTest: false, depthWrite: false, defines: defines || {}});
  const PRJ = {uNear: {value: cam.near}, uFar: {value: cam.far}, uProj: {value: new THREE.Vector2(1, 1)}, uRes: {value: new THREE.Vector2(2, 2)}, uHalfRes: {value: new THREE.Vector2(1, 1)}};
  /* the room's distance along the view axis at every pixel, half size, read by the air, the shading of corners and the lens */
  const depthMat = qmat({tD: {value: rtMain.depthTexture}, uNear: PRJ.uNear, uFar: PRJ.uFar},
    `#include <packing>
     uniform sampler2D tD; uniform float uNear, uFar; varying vec2 vUv;
     void main(){ float d = texture2D(tD, vUv).r; float z = -perspectiveDepthToViewZ(d, uNear, uFar); gl_FragColor = vec4(z, z, z, 1.0); }`);
  /* corners and contacts darken: a screen-space look around each point for what stands near it */
  const aoMat = qmat({tDepth: {value: rtDepth.texture}, uProj: PRJ.uProj, uHalfRes: PRJ.uHalfRes, uP: {value: new THREE.Matrix4()}},
    `uniform sampler2D tDepth; uniform vec2 uProj, uHalfRes; uniform mat4 uP; varying vec2 vUv;
     vec3 posAt(vec2 uv){ float z = texture2D(tDepth, uv).r; return vec3((uv * 2.0 - 1.0) * uProj * z, -z); }
     float h2(vec2 p){ return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453); }
     void main(){
       vec3 P = posAt(vUv); if (-P.z > 40.0) { gl_FragColor = vec4(1.0); return; }
       vec3 dx = dFdx(P), dy = dFdy(P); vec3 n = normalize(cross(dx, dy)); if (dot(n, -P) < 0.0) n = -n;
       float a = h2(gl_FragCoord.xy) * 6.2831853; vec3 rv = vec3(cos(a), sin(a), 0.0);
       vec3 t = normalize(rv - n * dot(rv, n)), b = cross(n, t);
       const int N = 12; float occ = 0.0; float R = 0.55;
       for (int i = 0; i < N; i++) {
         float fi = float(i); float r = (fi + 0.5) / float(N); float ang = fi * 2.399963 + a;      /* a spiral over the hemisphere */
         vec3 k = vec3(cos(ang) * sqrt(r), sin(ang) * sqrt(r), 0.35 + 0.65 * (1.0 - r)); k = normalize(k) * mix(0.15, 1.0, r * r);
         vec3 S = P + (t * k.x + b * k.y + n * k.z) * R;
         vec4 c = uP * vec4(S, 1.0); vec2 suv = c.xy / c.w * 0.5 + 0.5;
         if (suv.x < 0.0 || suv.x > 1.0 || suv.y < 0.0 || suv.y > 1.0) continue;
         float sz = texture2D(tDepth, suv).r;
         float dz = (-S.z) - sz;      /* how far the room's surface stands in front of the sample point */
         occ += (dz > 0.03 ? 1.0 : 0.0) * smoothstep(R * 1.6, 0.0, dz - R * 0.2);
       }
       gl_FragColor = vec4(vec3(1.0 - occ / float(N)), 1.0);
     }`);
  const aoBlurMat = qmat({tAO: {value: rtAO.texture}, tDepth: {value: rtDepth.texture}, uHalfRes: PRJ.uHalfRes},
    `uniform sampler2D tAO, tDepth; uniform vec2 uHalfRes; varying vec2 vUv;
     void main(){ float z0 = texture2D(tDepth, vUv).r; float acc = 0.0, ws = 0.0;
       for (int j = -2; j <= 2; j++) for (int i = -2; i <= 2; i++) { vec2 o = vec2(float(i), float(j)) / uHalfRes; float z = texture2D(tDepth, vUv + o).r;
         float w = exp(-abs(z - z0) * 8.0); acc += texture2D(tAO, vUv + o).r * w; ws += w; }
       gl_FragColor = vec4(vec3(acc / ws), 1.0); }`);
  /* the lens's focus: where the middle of the view stands, settling over a moment (a 1 by 1 picture that remembers) */
  const focusMat = qmat({tDepth: {value: rtDepth.texture}, tPrev: {value: null}, uFocus: {value: 0}, uK: {value: 0.08}},
    `uniform sampler2D tDepth, tPrev; uniform float uFocus, uK; varying vec2 vUv;
     void main(){ float d = 0.0; for (int j = -1; j <= 1; j++) for (int i = -1; i <= 1; i++) d += texture2D(tDepth, vec2(0.5, 0.52) + vec2(float(i), float(j)) * 0.01).r; d /= 9.0;
       float prev = texture2D(tPrev, vec2(0.5)).r; float want = uFocus > 0.0 ? uFocus : clamp(d, 0.3, 30.0);
       float f = prev > 0.0 ? mix(prev, want, uK) : want; gl_FragColor = vec4(f, f, f, 1.0); }`);
  /* the picture softened where it is out of focus, half size: each pixel gathers around itself as far as its own circle of confusion */
  const dofMat = qmat({tSrc: {value: rtMain.texture}, tDepth: {value: rtDepth.texture}, tFocus: {value: null}, uAper: {value: LOOK.dof}, uHalfRes: PRJ.uHalfRes, uRes: PRJ.uRes},
    `uniform sampler2D tSrc, tDepth, tFocus; uniform float uAper; uniform vec2 uHalfRes, uRes; varying vec2 vUv;
     float cocOf(float d, float f){ return clamp(uAper * abs(1.0 / f - 1.0 / d) * uRes.y, 0.0, 16.0); }
     void main(){
       float f = texture2D(tFocus, vec2(0.5)).r; float d0 = texture2D(tDepth, vUv).r; float c0 = cocOf(d0, f);
       vec3 acc = texture2D(tSrc, vUv).rgb; float ws = 1.0; float rad = c0 * 0.5;      /* in half-size pixels */
       if (rad > 0.4) {
         for (int i = 0; i < 20; i++) { float fi = float(i) + 0.5; float r = sqrt(fi / 20.0) * rad; float ang = fi * 2.399963;
           vec2 o = vec2(cos(ang), sin(ang)) * r / uHalfRes; vec2 suv = vUv + o;
           float ds = texture2D(tDepth, suv).r; float cs = cocOf(ds, f) * 0.5;
           float w = cs >= r * 0.85 ? 1.0 : 0.2;      /* a sharp thing behind does not bleed into a soft thing in front */
           acc += texture2D(tSrc, suv).rgb * w; ws += w; }
       }
       gl_FragColor = vec4(acc / ws, c0 / 16.0);
     }`);
  const brightMat = qmat({tSrc: {value: rtMain.texture}},
    "uniform sampler2D tSrc; varying vec2 vUv; void main(){ vec3 c = texture2D(tSrc, vUv).rgb; if (any(isnan(c)) || any(isinf(c))) c = vec3(0.0); c = min(c, vec3(60.0)); float l = max(c.r, max(c.g, c.b)); gl_FragColor = vec4(c * smoothstep(1.5, 4.5, l), 1.0); }");
  const outMat = qmat({tSrc: {value: rtMain.texture}, tGlow: {value: rtGlow.texture}, tAO: {value: rtAO2.texture}, tDof: {value: rtDof.texture}, tDepth: {value: rtDepth.texture}, tFocus: {value: null},
                       uGlow: {value: lean ? 0 : LOOK.glow}, uT: {value: 0}, uGrain: {value: LOOK.grain}, uAO: {value: lean ? 0 : LOOK.ao}, uDof: {value: lean ? 0 : 1}, uAper: {value: LOOK.dof}, uRes: PRJ.uRes,
                       uGrade: {value: LOOK.grade}, uVig: {value: LOOK.vignette}, uCA: {value: lean ? 0 : LOOK.ca}},
    `uniform sampler2D tSrc, tGlow, tAO, tDof, tDepth, tFocus; uniform float uGlow, uT, uGrain, uAO, uDof, uAper, uGrade, uVig, uCA; uniform vec2 uRes; varying vec2 vUv;
     float h1(vec2 p){ return fract(sin(dot(p, vec2(12.9898, 78.233)) + uT) * 43758.5453); }
     void main(){
       vec2 q = vUv - 0.5; float asp = uRes.x / uRes.y;
       vec2 ca = q * uCA * 0.0022;      /* the lens's colour fringe, strongest at the edges */
       vec3 c = vec3(texture2D(tSrc, vUv + ca).r, texture2D(tSrc, vUv).g, texture2D(tSrc, vUv - ca).b);
       if (uDof > 0.5) {
         float f = texture2D(tFocus, vec2(0.5)).r; float d = texture2D(tDepth, vUv).r;
         float coc = clamp(uAper * abs(1.0 / f - 1.0 / d) * uRes.y, 0.0, 16.0);
         vec4 soft = texture2D(tDof, vUv); float k = smoothstep(0.7, 2.6, max(coc, soft.a * 16.0 * 0.9));
         c = mix(c, soft.rgb, k);
       }
       if (uAO > 0.0) { float ao = texture2D(tAO, vUv).r; c *= mix(1.0, pow(ao, 1.4), uAO); }
       if (uGlow > 0.0) c += (textureLod(tGlow, vUv, 1.0).rgb * 0.30 + textureLod(tGlow, vUv, 2.5).rgb * 0.30 + textureLod(tGlow, vUv, 4.0).rgb * 0.25 + textureLod(tGlow, vUv, 5.5).rgb * 0.25) * uGlow;
       gl_FragColor = vec4(c, 1.0);
       #include <tonemapping_fragment>
       #include <colorspace_fragment>
       vec3 g = gl_FragColor.rgb; float lum = dot(g, vec3(0.2126, 0.7152, 0.0722));
       /* the grade: a little lift in the shadows toward the blue of the windows, warmth in the lights, a touch more colour */
       vec3 lifted = g * 0.985 + vec3(0.010, 0.012, 0.020) * (1.0 - lum);
       lifted *= mix(vec3(1.0), vec3(1.012, 1.0, 0.978), smoothstep(0.5, 1.0, lum));
       lifted = mix(vec3(lum), lifted, 1.07);
       g = mix(g, lifted, uGrade);
       g *= 1.0 - uVig * pow(length(q * vec2(asp, 1.0)) * 1.15, 2.3);
       gl_FragColor.rgb = g + (h1(gl_FragCoord.xy) + h1(gl_FragCoord.xy + 17.0) - 1.0) * uGrain * (0.6 + 0.6 * (1.0 - lum));
     }`);
  let refl = null;
  if (!lean) {
    const rt = new THREE.WebGLRenderTarget(2, 2, {type: THREE.HalfFloatType, generateMipmaps: true, minFilter: THREE.LinearMipmapLinearFilter, magFilter: THREE.LinearFilter});
    const vcam = new THREE.PerspectiveCamera(), n = V3(0, 1, 0), o = V3(0, 0, 0), plane = new THREE.Plane(), clip = new THREE.Vector4(), q = new THREE.Vector4();
    const cp = V3(), view = V3(), look = V3(), target = V3(), rot = new THREE.Matrix4();
    refl = {rt, update(camera){      /* the mirrored camera, with an oblique near plane at the floor (as three.js's Reflector does) */
      cp.setFromMatrixPosition(camera.matrixWorld); view.subVectors(o, cp); if (view.dot(n) > 0) return;
      view.reflect(n).negate().add(o); rot.extractRotation(camera.matrixWorld);
      look.set(0, 0, -1).applyMatrix4(rot).add(cp); target.subVectors(o, look).reflect(n).negate().add(o);
      vcam.position.copy(view); vcam.up.set(0, 1, 0).applyMatrix4(rot).reflect(n); vcam.lookAt(target);
      vcam.near = camera.near; vcam.far = camera.far; vcam.updateMatrixWorld(); vcam.projectionMatrix.copy(camera.projectionMatrix);
      FU.uTexMat.value.set(0.5, 0, 0, 0.5, 0, 0.5, 0, 0.5, 0, 0, 0.5, 0.5, 0, 0, 0, 1).multiply(vcam.projectionMatrix).multiply(vcam.matrixWorldInverse);
      plane.setFromNormalAndCoplanarPoint(n, o).applyMatrix4(vcam.matrixWorldInverse);
      clip.set(plane.normal.x, plane.normal.y, plane.normal.z, plane.constant);
      const e = vcam.projectionMatrix.elements;
      q.x = (Math.sign(clip.x) + e[8]) / e[0]; q.y = (Math.sign(clip.y) + e[9]) / e[5]; q.z = -1; q.w = (1 + e[10]) / e[14];
      clip.multiplyScalar(2 / clip.dot(q)); e[2] = clip.x; e[6] = clip.y; e[10] = clip.z + 1 - 0.003; e[14] = clip.w;
      floor.visible = false; renderer.setRenderTarget(rt); renderer.render(scene, vcam); floor.visible = true;
      FU.uRefl.value = rt.texture; FU.uReflOn.value = 1;
    }};
  }
  const size = (w, h) => {      // w, h in CSS pixels; the buffers follow the drawing buffer
    aspect = w / h; cam.aspect = aspect; cam.updateProjectionMatrix();
    const v = renderer.getDrawingBufferSize(new THREE.Vector2()), W = Math.max(2, v.x), H = Math.max(2, v.y), hw = Math.max(2, W >> 1), hh = Math.max(2, H >> 1);
    rtMain.setSize(W, H); rtGlow.setSize(hw, hh); rtDepth.setSize(hw, hh); rtAO.setSize(hw, hh); rtAO2.setSize(hw, hh); rtDof.setSize(hw, hh);
    PRJ.uRes.value.set(W, H); PRJ.uHalfRes.value.set(hw, hh); DU.uRes.value.set(hw, hh);
    if (refl) { refl.rt.setSize(hw, hh); FU.uReflTexel.value.set(2 / W, 2 / H); }
  };
  const camFwd = V3();
  const render = t => {
    renderer.shadowMap.needsUpdate = true;
    cam.updateMatrixWorld(); camFwd.set(0, 0, -1).applyQuaternion(cam.quaternion); DU.uCamFwd.value.copy(camFwd);
    const th = Math.tan(cam.fov / 2 * D2R); PRJ.uProj.value.set(th * cam.aspect, th); PRJ.uNear.value = cam.near; PRJ.uFar.value = cam.far;
    if (refl) refl.update(cam);
    renderer.setRenderTarget(rtMain); renderer.render(scene, cam); calls = renderer.info.render.calls;
    /* the room's depth, half size; then the sun's air over the room, stopped by what it meets */
    quad.material = depthMat; renderer.setRenderTarget(rtDepth); renderer.render(qScene, qCam);
    DU.tDepth.value = rtDepth.texture;
    if (sunCol.k > 0.01 && !ST.noFx) { placeShafts(); renderer.setRenderTarget(rtMain); renderer.autoClear = false; renderer.render(fx, cam); renderer.autoClear = true; }
    if (!lean) {
      aoMat.uniforms.uP.value.copy(cam.projectionMatrix); quad.material = aoMat; renderer.setRenderTarget(rtAO); renderer.render(qScene, qCam);
      quad.material = aoBlurMat; renderer.setRenderTarget(rtAO2); renderer.render(qScene, qCam);
      const prev = rtFocus[focusPing], next = rtFocus[1 - focusPing]; focusPing = 1 - focusPing;
      focusMat.uniforms.tPrev.value = prev.texture; focusMat.uniforms.uFocus.value = focusNow; focusMat.uniforms.uK.value = focusNow > 0 ? 1.0 : 0.08;
      quad.material = focusMat; renderer.setRenderTarget(next); renderer.render(qScene, qCam);
      dofMat.uniforms.tFocus.value = next.texture; outMat.uniforms.tFocus.value = next.texture;
      quad.material = dofMat; renderer.setRenderTarget(rtDof); renderer.render(qScene, qCam);
      quad.material = brightMat; renderer.setRenderTarget(rtGlow); renderer.render(qScene, qCam);
    }
    quad.material = outMat; outMat.uniforms.uT.value = (t * 60 | 0) % 97; renderer.setRenderTarget(null); renderer.render(qScene, qCam);
  };
  /* the crossing's frame */
  const frame = t => {
    pose(t, cam); cam.updateMatrixWorld();
    placeBallot(t, cam.position.clone());
    if (!ST.still) {      /* the lens: deep focus across the gym; a pull to the ballot as it comes up, to the slot, then to the screen */
      const dBallot = ballot.visible ? Math.max(0.3, ballot.position.distanceTo(cam.position)) : 0.7, dScreen = Math.max(0.3, SCREEN.distanceTo(cam.position));
      focusNow = mix(mix(9.0, dBallot, focusPlan.up), dScreen, Math.max(focusPlan.slot * 0.5, focusPlan.screen));
    }
    machine(t);
    alive(t, 0.5 + 0.5 * Math.sin(t * 0.3));
    return ST.still ? 0 : Math.max(1 - smooth(seg(t, 0.05, 1.0)), smooth(seg(t, DUR - 0.8, DUR)));      // how much of the page's colour lies over the room
  };
  /* the place's frame: the pose the page keeps, the sun where the place's clock has it, the room alive */
  const frameWatch = (t, minutes, bob, roll) => {
    focusNow = 0;      /* the lens focuses on what the middle of the view rests on */
    const alt = SUN.alt0 - SUN.sink * minutes; if (Math.abs(alt - sunAlt) > 0.004) setSun(alt);
    applyPose(t, cam, bob, roll); cam.updateMatrixWorld();
    /* the scanner: your ballot just counted, for a few seconds after the way in; then it waits for the next, its count kept */
    const counted = t < countedUntil; drawScreen(counted ? 2 : 0, counted ? 1 : 0, 1);
    ledMat.emissive.set("#35E16A"); ledMat.emissiveIntensity = 1.4 + 0.9 * Math.sin(t * 1.1);
    alive(t, 0.5 + 0.5 * Math.sin(t * 0.21) * Math.sin(t * 0.07 + 1.0));
  };

  /* ---------- made ready on the graphics card: every program once, then the light worked out ---------- */
  renderer.shadowMap.autoUpdate = false;
  let env = null;
  const gpu = async () => {
    const pm = new THREE.PMREMGenerator(renderer);
    const ph = new THREE.Scene(); ph.background = new THREE.Color(0.25, 0.24, 0.22);
    env = pm.fromScene(ph, 0, 0.1, 10); scene.environment = env.texture; scene.environmentIntensity = LOOK.env;      // a stand-in of the same size, so no program is made twice
    frame(0);
    renderer.setRenderTarget(rtMain); const p1 = renderer.compileAsync(scene, cam); const p4 = renderer.compileAsync(fx, cam);
    const ps = [];
    for (const m of [depthMat, aoMat, aoBlurMat, focusMat, dofMat, brightMat, outMat]) { quad.material = m; renderer.setRenderTarget(rtGlow); ps.push(renderer.compileAsync(qScene, qCam)); }
    renderer.setRenderTarget(null);
    await Promise.all([p1, p4, ...ps]);
    /* the room seen from its middle, twice, so its light bounces once; the sun's shafts are not in it */
    const hide = [ballot, ...hands.map(h => h.node)];
    const capture = () => { for (const o of hide) o.visible = false; scene.position.set(0, -3.2, 0.5); scene.updateMatrixWorld(true);
      renderer.shadowMap.needsUpdate = true; const rt = pm.fromScene(scene, 0, 0.1, 60); scene.position.set(0, 0, 0); scene.updateMatrixWorld(true); for (const o of hide) o.visible = !place || o !== ballot; return rt; };
    for (let k = 0; k < (lean ? 1 : 2); k++) { const e = capture(); env.dispose(); env = e; scene.environment = env.texture; }
    pm.dispose();
    for (const rt of rtFocus) { renderer.setRenderTarget(rt); renderer.clear(); }
    renderer.setRenderTarget(null);
  };
  const dispose = () => { scene.traverse(o => { if (o.geometry) o.geometry.dispose(); }); fx.traverse(o => { if (o.geometry) o.geometry.dispose(); });
    for (const m of [floorMat, wallMat, flagMat, outMat, brightMat, depthMat, aoMat, aoBlurMat, focusMat, dofMat, shaftMat, skyMat]) m.dispose();
    if (env) env.dispose(); for (const rt of [rtMain, rtGlow, rtDepth, rtAO, rtAO2, rtDof, ...rtFocus]) rt.dispose(); if (refl) refl.rt.dispose(); };
  let calls = 0;
  const info = () => { const px = new Uint16Array(4); let f = null; try { renderer.readRenderTargetPixels(rtFocus[focusPing], 0, 0, 1, 1, px); f = px[0]; } catch (e) { f = String(e.message).slice(0, 60); }
    return {calls, programs: renderer.info.programs ? renderer.info.programs.length : 0, buffer: renderer.getDrawingBufferSize(new THREE.Vector2()).toArray(), sunAlt: +sunAlt.toFixed(2), focusNow: +focusNow.toFixed(3), focusHalf: f,
            sun: {pos: sun.position.toArray().map(v => +v.toFixed(2)), target: sun.target.position.toArray().map(v => +v.toFixed(2)), intensity: sun.intensity, shadow: sun.castShadow}}; };
  /* the view the crossing hands to the place: where the eyes are and which way they look */
  const handoff = t => { pose(t, cam); const e = new THREE.Euler().setFromQuaternion(cam.quaternion, "YXZ"); return {at: Date.now(), x: +cam.position.x.toFixed(3), y: +cam.position.y.toFixed(3), z: +cam.position.z.toFixed(3), yaw: +(e.y / D2R).toFixed(2), pitch: +(e.x / D2R).toFixed(2), t: +t.toFixed(2)}; };
  const facts = {place: "a school gymnasium used as a polling place, in the last half hour of sun on Election Day", clock: `${SUN.hour - 12}:${String(SUN.minute).padStart(2, "0")} p.m.`, count: [BEFORE, BEFORE + 1],
                 sun: {alt0: SUN.alt0, sinks: SUN.sink}, seats: SEATS.map(s => ({id: s.id, name: s.name, where: s.where})), points: {clock: CLOCK_AT.toArray(), scanner: SCREEN.toArray(), doors: [doorX, 1.2, ZF], halyard: [-RX - 3, 5.5, -2], backDoors: [DOORB.x, 1.2, ZB]}};
  return {scene, fx, cam, frame, frameWatch, render, size, dispose, info, gpu, handoff, facts, PZ, collide, setSun, set still(v){ ST.still = !!v; }, get still(){ return ST.still; },
          set focus(v){ focusNow = v; }, get sunAlt(){ return sunAlt; }, set countedUntil(v){ countedUntil = v; }, obstacles};
}

function setup(renderer, w, h, ratio){
  renderer.setPixelRatio(ratio); renderer.setSize(w, h, false);
  renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.toneMapping = THREE[LOOK0.tone]; renderer.toneMappingExposure = LOOK0.exposure; renderer.outputColorSpace = THREE.SRGBColorSpace;
}
/* a renderer and the room for a window of w by h, being made ready (stage.ready) */
function stage(A, w, h, o = {}){
  const lean = !!o.lean, small = Math.min(w, h) < 600;
  const renderer = new THREE.WebGLRenderer({antialias: false, powerPreference: "high-performance", preserveDrawingBuffer: !!o.keep, canvas: o.canvas});
  const ext = renderer.extensions;      /* the room is drawn in light brighter than white, which needs float buffers; without them, no room */
  if (!ext.has("EXT_color_buffer_float") && !ext.has("EXT_color_buffer_half_float")) { renderer.dispose(); renderer.forceContextLoss(); throw new Error("no float buffers"); }
  const cap = lean ? 1.0e6 : small ? 1.6e6 : 2.6e6;
  setup(renderer, w, h, o.ratio || Math.min(2, devicePixelRatio || 1, Math.sqrt(cap / (w * h))));
  const S = build(renderer, A, {lean, still: o.still, samples: lean || small ? 2 : 4, look: o.look, more: o.more, watch: o.watch, skySunU: o.skySunU, noSunShadow: o.noSunShadow});
  S.size(w, h);
  const st = {renderer, S, lean, w, h};
  st.ready = S.gpu();
  st.ready.catch(() => { st.dead = true; });
  return st;
}
function drop(st){ try { st.S.dispose(); st.renderer.dispose(); st.renderer.forceContextLoss(); } catch (e) {} }

/* ================================ the sound of the place (off until the reader turns it on) ================================ */
/* Everything here is made on the device with Web Audio: no recordings. The gym's hum (the air handling, the lamps) with
   its long echo, the clock on the far wall, the scanner's fan, a flag's rope tapping its pole outside the west windows,
   a door far off in the hall now and then, and the reader's own steps on the maple. Each sound sits where its thing is,
   so turning the head turns the sound. */
function gymSound(points){
  let ctx = null, master = null, verb = null, verbIn = null, noise = null, pink = null, on = false, dead = false;
  const timers = {clock: 0, tap: 0, door: 0, fan: 0, gust: 0}, R = rng(4242);
  const mk = () => {
    const AC = window.AudioContext || window.webkitAudioContext; if (!AC) return false;
    ctx = new AC(); master = ctx.createGain(); master.gain.value = 0; master.connect(ctx.destination);
    /* the echo of a hard, high room: a long tail that falls away over about three seconds, with a few early slaps */
    const sr = ctx.sampleRate, L = Math.floor(sr * 3.2), ir = ctx.createBuffer(2, L, sr);
    for (let ch = 0; ch < 2; ch++) { const d = ir.getChannelData(ch); let r2 = rng(ch + 9);
      for (let i = 0; i < L; i++) { const t = i / sr; d[i] = (r2() * 2 - 1) * Math.exp(-t * 2.1) * (t < 0.012 ? 0 : 1) * 0.5; }
      for (const [at, g] of [[0.021, 0.5], [0.034, 0.4], [0.052, 0.3], [0.081, 0.25], [0.117, 0.2]]) { const i = Math.floor((at + ch * 0.003) * sr); if (i < L) d[i] += g * (r2() > 0.5 ? 1 : -1); } }
    verb = ctx.createConvolver(); verb.buffer = ir; verbIn = ctx.createGain(); verbIn.gain.value = 0.42; verbIn.connect(verb); verb.connect(master);
    /* noise to build on: white, and pink */
    const N = sr * 4, nb = ctx.createBuffer(1, N, sr), nd = nb.getChannelData(0); for (let i = 0; i < N; i++) nd[i] = R() * 2 - 1;
    const pb = ctx.createBuffer(1, N, sr), pd = pb.getChannelData(0); let b0 = 0, b1 = 0, b2 = 0; for (let i = 0; i < N; i++) { const w = R() * 2 - 1; b0 = 0.99765 * b0 + w * 0.099; b1 = 0.963 * b1 + w * 0.2965; b2 = 0.57 * b2 + w * 1.0526; pd[i] = (b0 + b1 + b2 + w * 0.1848) * 0.12; }
    noise = nb; pink = pb;
    const loop = (buf, gain, filt) => { const s = ctx.createBufferSource(); s.buffer = buf; s.loop = true; let n = s; for (const f of filt) { n.connect(f); n = f; } const g = ctx.createGain(); g.gain.value = gain; n.connect(g); s.start(); return g; };
    const bq = (type, f, q = 1, gain = 0) => { const b = ctx.createBiquadFilter(); b.type = type; b.frequency.value = f; b.Q.value = q; b.gain.value = gain; return b; };
    /* the air handling: a low rush, and the lamps' faint buzz; both everywhere, a little into the echo */
    const air = loop(pink, 0.5, [bq("lowpass", 240, 0.7), bq("peaking", 95, 2.5, 6)]); air.connect(master); const airSend = ctx.createGain(); airSend.gain.value = 0.3; air.connect(airSend); airSend.connect(verbIn);
    const hiss = loop(pink, 0.035, [bq("bandpass", 1600, 0.4)]); hiss.connect(master);
    const buzz = ctx.createOscillator(); buzz.type = "triangle"; buzz.frequency.value = 120; const bg = ctx.createGain(); bg.gain.value = 0.006; buzz.connect(bq("highpass", 100, 1)).connect(bg); bg.connect(master); buzz.start();
    const buzz2 = ctx.createOscillator(); buzz2.type = "sine"; buzz2.frequency.value = 240; const bg2 = ctx.createGain(); bg2.gain.value = 0.004; buzz2.connect(bg2); bg2.connect(master); buzz2.start();
    /* the scanner's fan, where it stands */
    const fanP = panner(points.scanner, 1.2); const fan = loop(pink, 0.09, [bq("bandpass", 420, 1.2), bq("lowpass", 1200, 0.7)]); fan.connect(fanP);
    S.fanBase = fan; S.fanP = fanP;
    /* the line in the hall beyond the far doors: a murmur of voices, muffled by the doors, swelling and falling as talk does;
       band-limited noise shaped by slow, uneven envelopes, so no word is ever in it */
    const hallP = panner(points.doors, 2.2);
    const murmur = loop(pink, 0.0, [bq("bandpass", 520, 0.9), bq("lowpass", 900, 0.8), bq("highpass", 260, 0.7)]); murmur.connect(hallP);
    S.murmur = murmur;
    const lfo = (f, depth) => { const o = ctx.createOscillator(); o.type = "sine"; o.frequency.value = f; const g = ctx.createGain(); g.gain.value = depth; o.connect(g); o.start(); return g; };
    for (const [f, d] of [[0.11, 0.028], [0.37, 0.02], [0.9, 0.012], [2.3, 0.008]]) lfo(f, d).connect(murmur.gain);
    murmur.gain.value = 0.075;
    return true;
  };
  function panner(p, ref = 1.5){
    const pn = ctx.createPanner(); pn.panningModel = "HRTF"; pn.distanceModel = "inverse"; pn.refDistance = ref; pn.rolloffFactor = 1.1; pn.maxDistance = 60;
    if (pn.positionX) { pn.positionX.value = p[0]; pn.positionY.value = p[1]; pn.positionZ.value = p[2]; } else pn.setPosition(p[0], p[1], p[2]);
    pn.connect(master); const send = ctx.createGain(); send.gain.value = 0.55; pn.connect(send); send.connect(verbIn); return pn;
  }
  const burst = (dest, when, dur, gain, filt, buf = noise) => {
    const s = ctx.createBufferSource(); s.buffer = buf; s.loop = true; s.loopStart = R() * 3; let n = s; for (const f of filt) { n.connect(f); n = f; }
    const g = ctx.createGain(); g.gain.setValueAtTime(0, when); g.gain.linearRampToValueAtTime(gain, when + 0.004); g.gain.exponentialRampToValueAtTime(0.0005, when + dur); n.connect(g); g.connect(dest); s.start(when); s.stop(when + dur + 0.05);
  };
  const tone = (dest, when, f0, f1, dur, gain, type = "sine") => {
    const o = ctx.createOscillator(); o.type = type; o.frequency.setValueAtTime(f0, when); o.frequency.exponentialRampToValueAtTime(Math.max(1, f1), when + dur);
    const g = ctx.createGain(); g.gain.setValueAtTime(0, when); g.gain.linearRampToValueAtTime(gain, when + 0.003); g.gain.exponentialRampToValueAtTime(0.0005, when + dur); o.connect(g); g.connect(dest); o.start(when); o.stop(when + dur + 0.05);
  };
  const bq2 = (type, f, q = 1) => { const b = ctx.createBiquadFilter(); b.type = type; b.frequency.value = f; b.Q.value = q; return b; };
  const S = {
    get on(){ return on; },
    start(){ if (dead) return false; if (!ctx) { try { if (!mk()) return false; } catch (e) { dead = true; return false; } S.clockP = panner(points.clock, 1.0); S.doorP = panner(points.doors, 2.0); S.tapP = panner(points.halyard, 2.5); S.stepL = ctx.createStereoPanner(); S.stepL.connect(master); const ss = ctx.createGain(); ss.gain.value = 0.5; S.stepL.connect(ss); ss.connect(verbIn); }
      if (ctx.state === "suspended") ctx.resume().catch(() => {});
      on = true; const t = ctx.currentTime; master.gain.cancelScheduledValues(t); master.gain.setValueAtTime(master.gain.value, t); master.gain.linearRampToValueAtTime(1, t + 1.2);
      timers.clock = t + 0.5; timers.tap = t + 2 + R() * 4; timers.door = t + 25 + R() * 60; timers.gust = t; return true; },
    stop(){ if (!ctx || !on) return; on = false; const t = ctx.currentTime; master.gain.cancelScheduledValues(t); master.gain.setValueAtTime(master.gain.value, t); master.gain.linearRampToValueAtTime(0, t + 0.5);
      setTimeout(() => { if (!on && ctx && ctx.state === "running") ctx.suspend().catch(() => {}); }, 700); },
    close(){ if (ctx) { try { ctx.close(); } catch (e) {} ctx = null; } on = false; },
    /* each frame: the listener where the eyes are; the scheduled sounds a little ahead of time */
    update(cam, gust){
      if (!ctx || !on) return;
      const L = ctx.listener, p = cam.position, f = V3(0, 0, -1).applyQuaternion(cam.quaternion), u = V3(0, 1, 0).applyQuaternion(cam.quaternion);
      if (L.positionX) { L.positionX.value = p.x; L.positionY.value = p.y; L.positionZ.value = p.z; L.forwardX.value = f.x; L.forwardY.value = f.y; L.forwardZ.value = f.z; L.upX.value = u.x; L.upY.value = u.y; L.upZ.value = u.z; }
      else { L.setPosition(p.x, p.y, p.z); L.setOrientation(f.x, f.y, f.z, u.x, u.y, u.z); }
      const t = ctx.currentTime;
      while (timers.clock < t + 0.4) {      /* the clock: a dry tick each second, a little duller every other one */
        const w = timers.clock, odd = Math.round(w) % 2; burst(S.clockP, w, 0.018, odd ? 0.09 : 0.12, [bq2("bandpass", odd ? 2400 : 3100, 6)]); timers.clock += 1.0; }
      while (timers.tap < t + 0.4) {      /* the halyard outside: one tap, sometimes two or three, in the wind's gusts */
        const w = timers.tap, n = R() < 0.5 ? 1 : R() < 0.6 ? 2 : 3;
        for (let i = 0; i < n; i++) { const at = w + i * (0.09 + R() * 0.11); tone(S.tapP, at, 1900 + R() * 300, 1700, 0.11, 0.05); tone(S.tapP, at, 3300 + R() * 400, 3000, 0.07, 0.025); burst(S.tapP, at, 0.012, 0.05, [bq2("highpass", 1800, 1)]); }
        timers.tap = w + 2.5 + R() * 7 * (1.3 - gust); }
      while (timers.door < t + 0.4) {      /* a door far off in the hall: a muffled thud, the latch after it */
        const w = timers.door; burst(S.doorP, w, 0.16, 0.5, [bq2("lowpass", 220, 0.8)]); tone(S.doorP, w, 140, 60, 0.18, 0.25); burst(S.doorP, w + 0.19 + R() * 0.08, 0.05, 0.18, [bq2("bandpass", 1500, 2)]);
        timers.door = w + 40 + R() * 110; }
    },
    step(speed){ if (!ctx || !on) return; const t = ctx.currentTime, k = clamp(speed, 0.2, 1.0); S.stepL.pan.value = (S.stepSide = !S.stepSide) ? 0.18 : -0.18;
      burst(S.stepL, t, 0.07, 0.16 * k, [bq2("bandpass", 650 + R() * 250, 1.2)]); tone(S.stepL, t, 130, 70, 0.07, 0.1 * k); burst(S.stepL, t + 0.03, 0.03, 0.05 * k, [bq2("highpass", 2500, 1)]); },
    sit(kind){ if (!ctx || !on) return; const t = ctx.currentTime; if (kind === "bench") { burst(S.stepL, t, 0.12, 0.12, [bq2("bandpass", 380, 4)]); tone(S.stepL, t + 0.05, 220, 180, 0.14, 0.05, "triangle"); }
      else if (kind === "chair") { burst(S.stepL, t, 0.09, 0.14, [bq2("bandpass", 900, 2)]); burst(S.stepL, t + 0.11, 0.06, 0.08, [bq2("bandpass", 600, 2)]); } }
  };
  return S;
}

/* ================================ playing it over the page ================================ */
export function run(url, opts = {}){
  const A = opts.assets || ready;
  if (!A || !supported()) return false;
  const lean = !!opts.lean, w = innerWidth, h = innerHeight;
  playing = true;
  let st = warm; warm = null; if (st) clearTimeout(st.timer);
  if (st && (st.dead || st.lean !== lean)) { drop(st); st = null; }
  if (!st) { try { st = stage(A, w, h, {lean}); } catch (e) { return false; } }
  else if (st.w !== w || st.h !== h) { st.renderer.setSize(w, h, false); st.S.size(w, h); st.w = w; st.h = h; }
  const {renderer, S} = st; S.still = !!opts.still;
  const host = opts.host || document.body.appendChild(document.createElement("div"));
  const cv = renderer.domElement; cv.setAttribute("aria-hidden", "true"); cv.style.cssText = "position:absolute;inset:0;display:block;width:100%;height:100%";
  const lens = document.createElement("div"), fade = document.createElement("div");
  lens.style.cssText = "position:absolute;inset:0;pointer-events:none;background:radial-gradient(125% 100% at 50% 45%,transparent 66%,rgba(0,0,0,.18))";
  /* the page's own colour, laid over the room as it opens and as it closes, so the way in and the way out are seamless */
  fade.style.cssText = `position:absolute;inset:0;pointer-events:none;background:${opts.from || PAGE};opacity:1`;
  host.prepend(cv, lens, fade);
  const KEY = opts.arrive || "tca.ballot.arrive";
  let gone = false, dead = false, t0 = 0, raf = 0, started = false, tNow = 0, tEnd = DUR;
  const timers = [], later = (f, ms) => { timers.push(setTimeout(f, ms)); };
  const stop = () => { gone = true; cancelAnimationFrame(raf); for (const id of timers) clearTimeout(id); };
  const go = how => { if (gone) return; stop();
    if (opts.go) { try { opts.go(how); } catch (e) {} return; }
    try { sessionStorage.setItem(KEY, how); } catch (e) {} location.href = url; };
  const skip = () => go("skip");
  /* Stay here: the place's own page, the view handed over (this tab only) */
  const stay = () => {
    if (gone || !opts.stay) return; stop();
    try { sessionStorage.setItem("tca.ballot.stay", JSON.stringify(S.handoff(opts.still ? STILL_T : tNow))); } catch (e) {}
    cv.style.transition = "opacity .3s ease"; cv.style.opacity = 0;
    setTimeout(() => { if (!dead) location.href = opts.stay; }, 300);
  };
  const holding = () => { try { return !!(opts.hold && opts.hold()); } catch (e) { return false; } };
  const onStay = e => !!(e.target && e.target.closest && e.target.closest("[data-stay]"));
  const ac = new AbortController(), signal = ac.signal;
  host.addEventListener("pointerdown", e => { if (onStay(e)) return; if (e.button === 0 || e.pointerType !== "mouse") skip(); });
  host.addEventListener("click", e => { if (!onStay(e)) skip(); });      /* the Skip button, however it is pressed */
  if (opts.keys !== false) addEventListener("keydown", e => { if (!quietKey(e)) { e.preventDefault(); skip(); } }, {capture: true, signal});
  addEventListener("resize", () => { const ww = innerWidth, hh = innerHeight; renderer.setSize(ww, hh, false); S.size(ww, hh); }, {signal});
  /* Back while it plays keeps this page in the browser's memory with its clocks stopped: when it comes back, the room is
     gone and nothing goes on to On The Ballot by itself */
  addEventListener("pagehide", e => { if (e.persisted) stop(); }, {signal});
  addEventListener("pageshow", e => { if (e.persisted) { stop(); dead = true; ac.abort(); host.remove(); drop(st); playing = false; } }, {signal});      /* back from On The Ballot: the page, not the room */
  const begin = () => {
    if (gone || started) return; started = true;
    if (opts.still) {      // motion off, Calm, or reduced motion: one still picture, then a plain fade (it waits while the reader reaches for Stay)
      S.frame(STILL_T); S.render(STILL_T); fade.style.transition = "opacity .5s ease"; fade.style.opacity = 0;
      const begun = performance.now();
      const end = () => { if (gone) return; if (holding() && performance.now() - begun < 9000) { later(end, 250); return; }
        if (opts.fade) opts.fade(); fade.style.background = opts.to || PAGE; fade.style.opacity = 1; later(() => go("still"), 520); };
      later(end, 2200);
      return;
    }
    let last = 0; STATS.frames = STATS.slow = STATS.worst = 0;
    const tick = now => {
      if (gone) return;
      if (!t0) t0 = now;
      if (last) { const dt = now - last; STATS.frames++; if (dt > 25) STATS.slow++; STATS.worst = Math.max(STATS.worst, Math.round(dt)); } last = now;
      const t = (now - t0) / 1000;
      if (holding() && t > tEnd - 1.4 && tEnd < DUR + 6) tEnd = Math.min(DUR + 6, t + 1.4);      // reaching for Stay: the room waits a little
      tNow = Math.min(t, tEnd);
      pt.sx += (pt.x - pt.sx) * 0.05; pt.sy += (pt.y - pt.sy) * 0.05;
      const tf = Math.min(tNow, DUR), v = S.frame(tf); S.render(tf);
      fade.style.opacity = (tEnd > DUR && tNow > DUR - 0.8 ? Math.max(0, v - (tEnd - DUR) * 0 ) : v).toFixed(3); if (tf > DUR / 2 && !fade.dataset.out) { fade.dataset.out = "1"; fade.style.background = opts.to || PAGE; }
      if (t < tEnd) raf = requestAnimationFrame(tick); else go("full");
    };
    raf = requestAnimationFrame(tick);
    const guard = () => { if (gone) return; if (performance.now() - (t0 || performance.now()) < (tEnd + 1.8) * 1000) { later(guard, 400); return; } go("full"); };
    later(guard, DUR * 1000 + 1800);      // a window that is not drawing frames still gets there
  };
  const asked = performance.now();
  st.ready.then(() => { STATS.wait = Math.round(performance.now() - asked); begin(); }, () => go("quick"));
  later(() => { if (!started) go("quick"); }, 4500);      // a device that cannot make the room ready in time: straight there
  return {skip, stay};
}
/* keys that skip nothing: a modifier, a lock or a screen reader's own key pressed alone (Ctrl also stops speech), and any
   key pressed with Ctrl, Alt or the command key, which belongs to the browser */
const QUIET = ["Shift", "Control", "Alt", "AltGraph", "Meta", "OS", "Super", "Hyper", "Fn", "FnLock", "CapsLock", "NumLock", "ScrollLock", "Insert", "Unidentified", "Process", "Tab"];
function quietKey(e){ return e.ctrlKey || e.metaKey || e.altKey || QUIET.includes(e.key); }

/* ================================ the place: sit, look, get up and walk ================================ */
/* The place's own page (John, 2026-10-11): the reader sits where they chose and stays as long as they like. Drag, touch or
   the arrow keys look around (no pointer capture: the listeners sit on the window and all go with stop()). "Get up" stands
   them next to the seat; W A S D, the arrow keys or a thumb control on a phone walk them, never through a wall, the
   bleachers, a booth, a table or a chair; "Sit" puts them back in a seat. Sound is off until the page's button turns it
   on. With motion off it is one still picture that still turns with a drag or a key, and the sun holds. A lean device
   draws fewer pixels, no depth of field and no shafts. The sun sinks on the place's own clock. */
export function watch(canvas, opts = {}){
  if (!canvas || !opts.assets || !supported()) return null;
  const lean = !!opts.lean, ac = new AbortController(), on = (el, ev, fn, o) => el.addEventListener(ev, fn, Object.assign({signal: ac.signal}, o || {}));
  const dims = () => { const r = canvas.getBoundingClientRect(); return [Math.max(1, Math.round(r.width || innerWidth)), Math.max(1, Math.round(r.height || innerHeight))]; };
  let [w, h] = dims();
  let st;
  try { st = stage(opts.assets, w, h, {lean, still: !!opts.still, canvas, more: opts.more, watch: true, skySunU: opts.skySunU, look: opts.look, keep: !!opts.keep}); }
  catch (e) { console.warn("The polling place could not be drawn:", e); return null; }
  const {renderer, S} = st, PZ = S.PZ;
  let still = !!opts.still, alive = true, raf = 0, t0 = performance.now(), last = t0, settleT = 0, minutes = 0, ready = false, lost = false;
  const tNow = () => (performance.now() - t0) / 1000;
  const sound = gymSound(S.facts.points);
  /* where the reader is: a seat, or on their feet; a move between the two eases over a moment */
  let seat = null, mode = "seat", move = null, bobPhase = 0, bob = 0, speedK = 0;
  const vel = {x: 0, z: 0}, held = new Set(), stick = {x: 0, y: 0, on: false};
  const seatOf = id => SEATS.find(s => s.id === id) || null;
  const toPose = (x, y, z, yaw, pitch) => { PZ.x = x; PZ.y = y; PZ.z = z; PZ.yaw = yaw; PZ.pitch = pitch; };
  const ease = (to, secs, done) => { move = {from: {x: PZ.x, y: PZ.y, z: PZ.z, yaw: PZ.yaw, pitch: PZ.pitch}, to, t: 0, secs, done}; poke(); };
  const sit = (id, instant) => {
    const s = seatOf(id); if (!s) return false;
    seat = s; mode = "seat"; vel.x = vel.z = 0;
    const to = {x: s.eye[0], y: s.eye[1], z: s.eye[2], yaw: s.yaw, pitch: s.pitch};
    if (instant || still) { toPose(to.x, to.y, to.z, to.yaw, to.pitch); move = null; } else ease(to, 1.1, () => sound.sit(s.sat));
    if (opts.onSeat) opts.onSeat(s, mode); poke(); return true;
  };
  const stand = () => {
    if (mode === "walk") return;
    const s = seat || SEATS[4], to = {x: s.stand[0], y: 1.62, z: s.stand[2], yaw: PZ.yaw, pitch: Math.max(PZ.pitch, -6)};
    mode = "walk"; if (still) { toPose(to.x, to.y, to.z, to.yaw, to.pitch); } else ease(to, s.standing ? 0.5 : 1.0, null);
    if (opts.onSeat) opts.onSeat(seat, mode); poke();
  };
  /* looking around: drag (a mouse, a finger, a pen), with a little glide after a quick drag; the arrow keys turn */
  const k = () => S.cam.fov / Math.max(1, h);      // degrees per pixel at the middle: the room follows the finger
  let drag = null; const inertia = {y: 0, p: 0};
  const turnBy = (dy, dp) => { PZ.yaw += dy; PZ.pitch = clamp(PZ.pitch + dp, -70, 55); };
  const said = () => { clearTimeout(settleT); settleT = setTimeout(() => { if (opts.onLook) opts.onLook(facing()); }, 650); };
  const facing = () => ({yaw: ((PZ.yaw % 360) + 360) % 360, pitch: PZ.pitch, mode, seat: seat ? seat.id : null, x: PZ.x, z: PZ.z});
  const onStick = e => stick.on && e.target && e.target.closest && e.target.closest("[data-stick]");
  on(canvas, "pointerdown", e => {
    if (drag || (e.pointerType === "mouse" && e.button !== 0) || onStick(e)) return;
    drag = {id: e.pointerId, x: e.clientX, y: e.clientY, s: []}; inertia.y = inertia.p = 0;
    canvas.classList.add("dragging"); if (opts.onInput) opts.onInput("drag"); poke();
  });
  on(window, "pointermove", e => {
    if (!drag || e.pointerId !== drag.id) return;
    const kk = k(), dy = -(e.clientX - drag.x) * kk, dp = -(e.clientY - drag.y) * kk;
    drag.x = e.clientX; drag.y = e.clientY; turnBy(dy, dp);
    drag.s.push([performance.now(), dy, dp]); if (drag.s.length > 8) drag.s.shift();
    poke();
  }, {passive: true});
  const endDrag = e => {
    if (!drag || (e && e.pointerId != null && e.pointerId !== drag.id)) return;
    const now = performance.now(), s = drag.s.filter(q => now - q[0] < 90);
    if (!still && s.length >= 2) { const span = Math.max(0.03, (now - s[0][0]) / 1000); inertia.y = clamp(s.reduce((a, q) => a + q[1], 0) / span, -200, 200); inertia.p = clamp(s.reduce((a, q) => a + q[2], 0) / span, -140, 140); }
    drag = null; canvas.classList.remove("dragging"); poke(); said();
  };
  on(window, "pointerup", endDrag); on(window, "pointercancel", endDrag);
  on(window, "blur", () => { endDrag(); held.clear(); });
  /* the keys: the arrows turn (and, on your feet, the up and down arrows walk); W A S D walk; the page may keep some keys */
  const TURN = {ArrowLeft: [-1, 0], ArrowRight: [1, 0]};
  const WALKK = {KeyW: [0, 1], KeyS: [0, -1], KeyA: [-1, 0], KeyD: [1, 0], ArrowUp: [0, 1], ArrowDown: [0, -1]};
  on(window, "keydown", e => {
    if (e.altKey || e.ctrlKey || e.metaKey || (opts.keysOK && !opts.keysOK(e))) return;
    const c = e.code || "", key = e.key;
    const turn = TURN[key] || (mode === "seat" && key === "ArrowUp" ? [0, 1] : mode === "seat" && key === "ArrowDown" ? [0, -1] : null);
    if (turn) { e.preventDefault(); inertia.y = inertia.p = 0; if (opts.onInput) opts.onInput("key"); if (still) { turnBy(turn[0] * 6, turn[1] * 4); poke(); said(); return; } held.add("T" + key); poke(); return; }
    if (mode === "walk" && WALKK[c]) { e.preventDefault(); if (opts.onInput) opts.onInput("key"); held.add(c); poke(); }
  });
  on(window, "keyup", e => { const c = e.code || ""; if (held.delete("T" + e.key) || held.delete(c)) { poke(); said(); } });
  /* a phone's thumb control: the page gives an element; a finger on it walks */
  const stickEl = opts.stick || null;
  if (stickEl) {
    let sid = null; const rect = () => stickEl.getBoundingClientRect();
    const set = e => { const r = rect(), cx = r.left + r.width / 2, cy = r.top + r.height / 2, rad = Math.max(20, r.width / 2); stick.x = clamp((e.clientX - cx) / rad, -1, 1); stick.y = clamp(-(e.clientY - cy) / rad, -1, 1); if (opts.onStick) opts.onStick(stick.x, stick.y); };
    on(stickEl, "pointerdown", e => { if (mode !== "walk") return; sid = e.pointerId; stick.on = true; set(e); e.preventDefault(); if (opts.onInput) opts.onInput("stick"); poke(); });
    on(window, "pointermove", e => { if (stick.on && e.pointerId === sid) set(e); }, {passive: true});
    const off = e => { if (stick.on && (!e || e.pointerId === sid)) { stick.on = false; stick.x = stick.y = 0; if (opts.onStick) opts.onStick(0, 0); poke(); } };
    on(window, "pointerup", off); on(window, "pointercancel", off);
  }
  /* each frame: the move, the turn, the walk with its bob and steps, the sun on the place's clock */
  const stepFrame = dt => {
    let moving = !!drag;
    if (move) { move.t += dt; const u = inOut(clamp(move.t / move.secs)); const a = move.from, b = move.to;
      toPose(mix(a.x, b.x, u), mix(a.y, b.y, u) + 0.02 * Math.sin(Math.PI * u) * (b.y < a.y ? 1 : -1), mix(a.z, b.z, u), mix(a.yaw, b.yaw, u), mix(a.pitch, b.pitch, u));
      if (move.t >= move.secs) { const d = move.done; move = null; if (d) d(); } moving = true; }
    let tx = 0, ty = 0;
    for (const key of held) { if (key[0] === "T") { const t = TURN[key.slice(1)]; if (t) { tx += t[0]; } else if (key === "TArrowUp") ty += 1; else if (key === "TArrowDown") ty -= 1; } }
    if (tx || ty) { turnBy(tx * 55 * dt, ty * 36 * dt); moving = true; }
    if (!drag && (Math.abs(inertia.y) > 0.6 || Math.abs(inertia.p) > 0.6)) {
      turnBy(inertia.y * dt, inertia.p * dt); const q = Math.exp(-dt / 0.3); inertia.y *= q; inertia.p *= q; moving = true;
      if (Math.abs(inertia.y) <= 0.6 && Math.abs(inertia.p) <= 0.6) said();
    } else if (!drag) inertia.y = inertia.p = 0;
    /* walking: the wish, eased into a pace of about 1.3 metres a second, stopped by what is in the way */
    let wx = 0, wz = 0;
    if (mode === "walk" && !move) {
      for (const c of held) { const d = WALKK[c]; if (d) { wx += d[0]; wz += d[1]; } }
      if (stick.on) { wx += stick.x; wz += stick.y; }
      const n = Math.hypot(wx, wz); if (n > 1) { wx /= n; wz /= n; }
    }
    const yaw = PZ.yaw * D2R, fwdX = -Math.sin(yaw), fwdZ = -Math.cos(yaw), rightX = Math.cos(yaw), rightZ = -Math.sin(yaw);
    const want = {x: (fwdX * wz + rightX * wx) * 1.3, z: (fwdZ * wz + rightZ * wx) * 1.3};
    const accel = (wx || wz) ? 5.5 : 7.5;
    vel.x += (want.x - vel.x) * clamp(accel * dt); vel.z += (want.z - vel.z) * clamp(accel * dt);
    const sp = Math.hypot(vel.x, vel.z);
    if (sp > 0.01) {
      const [nx, nz] = S.collide(PZ.x + vel.x * dt, PZ.z + vel.z * dt);
      const really = Math.hypot(nx - PZ.x, nz - PZ.z) / Math.max(dt, 1e-3);
      PZ.x = nx; PZ.z = nz; moving = true;
      const before = bobPhase; bobPhase += really * dt / 0.68;      /* a step every 68 centimetres */
      if (Math.floor(bobPhase) !== Math.floor(before) && really > 0.25) sound.step(really / 1.3);
      speedK += (clamp(really / 1.3) - speedK) * clamp(6 * dt);
    } else speedK += (0 - speedK) * clamp(6 * dt);
    bob = speedK * (0.014 * Math.cos(2 * Math.PI * bobPhase) - 0.006);
    return {moving, roll: speedK * 0.004 * Math.sin(Math.PI * bobPhase)};
  };
  const gust = t => 0.5 + 0.5 * Math.sin(t * 0.21) * Math.sin(t * 0.07 + 1.0);
  const draw = (t, m) => { S.frameWatch(t, still ? 0 : minutes, bob, m ? m.roll : 0); S.render(t); };
  const tick = now => {
    raf = 0; if (!alive) return;
    const dt = Math.min(0.1, Math.max(0, (now - last) / 1000)); last = now;
    if (!still) minutes += dt / 60;
    const m = stepFrame(dt), t = (now - t0) / 1000;
    draw(t, m); sound.update(S.cam, gust(t));
    if (still && !m.moving && !move) return;      // a still picture is drawn again only when the reader turns it
    raf = requestAnimationFrame(tick);
  };
  const poke = () => { if (!raf && alive) raf = requestAnimationFrame(tick); };
  /* the view the crossing handed over: standing where it stood, looking where it looked (if it is fresh); else the seat asked for */
  const f = opts.from;
  if (f && isFinite(f.x) && isFinite(f.z) && isFinite(f.yaw) && isFinite(f.pitch)) { const [x, z] = S.collide(f.x, f.z); toPose(x, 1.62, z, f.yaw, clamp(f.pitch, -60, 40)); mode = "walk"; seat = null; S.countedUntil = 7; }
  else sit(opts.seat || SEATS[0].id, true);
  const resize = () => { [w, h] = dims(); const small = Math.min(w, h) < 600, cap = lean ? 1.0e6 : small ? 1.6e6 : 2.6e6; renderer.setPixelRatio(Math.min(2, devicePixelRatio || 1, Math.sqrt(cap / (w * h)))); renderer.setSize(w, h, false); S.size(w, h); poke(); };
  on(window, "resize", resize); if (window.visualViewport) on(window.visualViewport, "resize", resize);
  on(canvas, "webglcontextlost", e => { e.preventDefault(); lost = true; ctl.stop(); if (opts.onLost) opts.onLost(); });
  on(window, "pagehide", e => { if (e.persisted) { alive = false; if (raf) cancelAnimationFrame(raf); raf = 0; } else ctl.stop(); });
  on(window, "pageshow", e => { if (e.persisted && !alive && !lost) { alive = true; last = performance.now(); poke(); } });
  st.ready.then(() => { if (!alive) return; ready = true; last = performance.now(); draw(tNow(), null); if (opts.onReady) opts.onReady(S.facts); poke(); }, e => { if (opts.onLost) opts.onLost(e); });
  const ctl = {
    stop(){ if (!ac.signal.aborted) { alive = false; if (raf) cancelAnimationFrame(raf); raf = 0; clearTimeout(settleT); ac.abort(); sound.close(); drop(st); } },
    setStill(v){ still = !!v; S.still = still; inertia.y = inertia.p = 0; held.clear(); poke(); },
    sit, stand, seats: SEATS, seatOf,
    get mode(){ return mode; }, get seat(){ return seat; },
    look(yaw, pitch){ PZ.yaw = yaw; PZ.pitch = pitch; poke(); },
    facing, facts: S.facts, get t(){ return tNow(); }, get minutes(){ return minutes; }, set minutes(v){ minutes = v; poke(); },
    sound: {on: () => sound.start(), off: () => sound.stop(), get isOn(){ return sound.on; }},
    get ready(){ return ready; }, redraw: () => poke(), scene: S.scene, info: () => S.info()
  };
  return ctl;
}

export async function still(t = 6, w = 960, h = 540, opts = {}){
  const A = await prepare({warm: false});
  if (opts.pt) { pt.x = pt.sx = opts.pt.x; pt.y = pt.sy = opts.pt.y; } else { pt.x = pt.sx = pt.y = pt.sy = 0; }
  const more = opts.more ? await loadMore(opts.more) : null;
  const t1 = performance.now();
  const st = stage(A, w, h, {lean: !!opts.lean, still: !!opts.still, keep: true, ratio: 1, look: opts.look, more, watch: !!opts.watch, skySunU: opts.skySunU, noSunShadow: opts.noSunShadow});
  await st.ready;
  const t2 = performance.now();
  let v = 0;
  if (opts.watch) {      /* the place: from a seat (opts.seat), on your feet at opts.at [x, z] looking opts.look {yaw, pitch}, after opts.minutes of the place's clock */
    const s = SEATS.find(q => q.id === opts.seat) || SEATS[0], PZ = st.S.PZ;
    if (opts.at) { PZ.x = opts.at[0]; PZ.z = opts.at[1]; PZ.y = 1.62; } else { PZ.x = s.eye[0]; PZ.y = s.eye[1]; PZ.z = s.eye[2]; }
    PZ.yaw = opts.yaw != null ? opts.yaw : s.yaw; PZ.pitch = opts.pitch != null ? opts.pitch : s.pitch;
    const mins = opts.minutes || 0;
    for (let i = 0; i < 3; i++) { st.S.frameWatch(t, mins, 0, 0); st.S.render(t); }      /* the lens settles on its focus over a few frames */
  } else { v = st.S.frame(t); st.S.render(t); }
  const t3 = performance.now(), info = Object.assign(st.S.info(), {ready: Math.round(t2 - t1), draw: Math.round(t3 - t2)});
  /* what a reader sees: the frame, and the page's colour over it as much as the fade has it (opts.raw: the frame alone) */
  const out = document.createElement("canvas"); out.width = w; out.height = h; const g = out.getContext("2d");
  g.drawImage(st.renderer.domElement, 0, 0, w, h);
  if (!opts.raw && !opts.watch) {
    const grd = g.createRadialGradient(w / 2, h * 0.45, 0, w / 2, h * 0.45, Math.hypot(w, h) * 0.6); grd.addColorStop(0.66, "rgba(0,0,0,0)"); grd.addColorStop(1, "rgba(0,0,0,.18)");
    g.fillStyle = grd; g.fillRect(0, 0, w, h);
    if (v > 0) { g.globalAlpha = v; g.fillStyle = t > DUR / 2 ? (opts.to || PAGE) : (opts.from || PAGE); g.fillRect(0, 0, w, h); g.globalAlpha = 1; }
  }
  const url = out.toDataURL(opts.png ? "image/png" : "image/jpeg", 0.9);
  drop(st);
  return {url, veil: v, info};
}
export async function facts(){
  await prepare({warm: false});
  return {duration: DUR, still: STILL_T, place: "a school gymnasium used as a polling place, in the last half hour of sun on Election Day", clock: `${SUN.hour - 12}:${String(SUN.minute).padStart(2, "0")} p.m.`, count: [1247, 1248],
          sun: SUN, seats: SEATS.map(s => ({id: s.id, name: s.name, where: s.where})), files: Object.keys(FILES), ready: !!ready, stats: Object.assign({}, STATS)};
}
