/*
 Into the notebook (sandbox, John 2026-11-10: "push the bounds ... between page scenery ... much closer to photo
 realistic"). The short crossing that plays the first time in a visit that a reader follows a notebook link from one of
 the layout pages: in the warm light of a reading room a leather-bound notebook lies on a wooden desk; your eyes settle
 over it; the cover opens, a few leaves turn, and the page you asked for lies flat, filling your view; then the browser
 goes to it. About three and a half seconds.

 How it is made. Everything near is built here in its real size (a notebook 148 by 210 millimetres, 18 millimetres of
 pages, boards 2.6 thick, brass corners, a satin ribbon) and lit as a photograph would be: physically based materials
 with photographed colour, normal and roughness maps (CC0: Poly Haven's brown leather and varnished table, ambientCG's
 paper; credits.json names each), reflections and fill light from a photographed room (Poly Haven's "Combination Room",
 an HDR panorama, prefiltered on the device), a warm desk lamp and a cool window as the two lights with soft shadows,
 and the room behind glimpsed out of focus. The cover and every leaf are real geometry: each leaf is a bent sheet whose
 shape is worked out every frame (the fold leads, the free edge trails, the corners curl a little) and which comes to
 rest in the gutter's valley on either side. The screen gets it through a lens: a high-range picture with depth, a soft
 bloom, depth of field with the focus racking from the cover to the page, a filmic curve, a quiet warm grade, the lens's
 own fall-off at the edges, a very fine grain, and the veil it fades in from and out to.

 Uses three.js (MIT), copied beside this file as three.module.min.js. Nothing loads from another server.
   prepare(opts)        fetch the files (on the first hover, focus or tap of a notebook link); opts.lean: the phone set
   supported()          can this device draw it (WebGL2)
   run(url, opts)       play it over the page, then go to url; false when it cannot be drawn. Returns {skip}.
                        opts.host  the element to draw into (the gate's veil); opts.assets  what prepare() returned;
                        opts.still  one still picture, then a fade; opts.lean  the light version; opts.start, opts.end
                        the colours it fades in from and out to; opts.title  the page's heading (the link's words);
                        opts.path  the notebook path (for the zones' pages); opts.keys false  the caller listens for keys;
                        opts.onEnd(how)  instead of going anywhere (the demo page); opts.fade  called before a still's fade
   still(t, w, h, opts) one frame as a JPEG data URL (opts.png for PNG), for checking the scene where frames are not drawn
   DUR, STILL_T         the crossing's length and the moment the still picture shows, in seconds
*/
import * as THREE from "./three.module.min.js";

const FILE = p => new URL(p, import.meta.url).href;
export const DUR = 3.6;
export const STILL_T = 3.05;
const D2R = Math.PI / 180;
const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
const seg = (t, a, b) => clamp((t - a) / (b - a));
const smooth = x => x * x * (3 - 2 * x);
const inOut = x => x < .5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2;
const outCubic = x => 1 - Math.pow(1 - x, 3);
const mix = (a, b, t) => a + (b - a) * t;
const V3 = (x = 0, y = 0, z = 0) => new THREE.Vector3(x, y, z);
function rng(seed){ let a = seed >>> 0; return () => { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
const pt = {x: 0, y: 0, sx: 0, sy: 0};      // the pointer, -1 to 1 across the window; sx, sy follow it slowly, as a head does
addEventListener("pointermove", e => { pt.x = e.clientX / innerWidth * 2 - 1; pt.y = e.clientY / innerHeight * 2 - 1; }, {passive: true});

/* ================================ the notebook's measurements (metres) ================================ */
const NB = {
  W: 0.148, H: 0.210, b: 0.0026, r: 0.0075,     // the boards: width, height, thickness, the corners' radius
  Wp: 0.144, Hp: 0.204, Tp: 0.0175,             // the block of pages
  s: 0.021,                                     // the spine's width, lying flat
  leaf: 0.00012,                                // one leaf's thickness
  gut: 0.0042,                                  // the valley's floor, over the desk, when it lies open
  nL: 3                                         // the leaves that turn after the cover
};
NB.yTop = NB.b + NB.Tp;                         // the block's top when closed
NB.T2 = NB.yTop + (NB.nL + 1) * NB.leaf;        // where the front board rests when closed
NB.inset = 0.001;                               // the block sits this far in from the boards' spine edge

/* the zones of the notebook, by the first part of a path, for the leaves that turn on the way to the page */
const ZONES = {start: "Start here", ballot: "On The Ballot", night: "Election Night", forecasts: "Forecasts", record: "The Record",
               past: "Past results", method: "How we work", access: "Reading & access"};
const ZONE_ORDER = ["ballot", "night", "forecasts", "record", "past", "method", "access"];

/* ================================ fetching ================================ */
let flips = null, loading = null, loadingLean = null;
function image(url){ return new Promise((ok, no) => { const im = new Image(); im.decoding = "async"; im.onload = () => ok(im); im.onerror = () => no(new Error("could not load " + url)); im.src = url; }); }
function autoLean(){
  const v = document.documentElement.getAttribute("data-lean");
  if (v) return v === "on";
  try { const n = navigator; return !!((n.deviceMemory && n.deviceMemory < 4) || (n.hardwareConcurrency && n.hardwareConcurrency <= 4)); } catch (e) { return false; }
}
/* can this browser decode a picture off the page's thread already turned over (as the GPU wants it)? tried once */
function flipsBitmaps(){
  return flips || (flips = (async () => {
    try {
      const c = document.createElement("canvas"); c.width = 1; c.height = 2; const g = c.getContext("2d");
      g.fillStyle = "#f00"; g.fillRect(0, 0, 1, 1); g.fillStyle = "#00f"; g.fillRect(0, 1, 1, 1);
      const b = await createImageBitmap(c, {imageOrientation: "flipY"});
      const d = document.createElement("canvas"); d.width = 1; d.height = 2; const h = d.getContext("2d", {willReadFrequently: true});
      h.drawImage(b, 0, 0); const px = h.getImageData(0, 0, 1, 1).data; if (b.close) b.close();
      return px[2] > 200 && px[0] < 60;
    } catch (e) { return false; }
  })());
}
async function photo(url){
  if (window.createImageBitmap && await flipsBitmaps()) {
    try { const r = await fetch(url); if (!r.ok) throw new Error(url); const b = await r.blob(); return await createImageBitmap(b, {imageOrientation: "flipY", premultiplyAlpha: "none", colorSpaceConversion: "none"}); } catch (e) {}
  }
  return image(url);
}
/* a Radiance picture (RGBE, written flat by the build) into floating-point texels */
async function loadHDR(url){
  const r = await fetch(url); if (!r.ok) throw new Error("could not load " + url);
  const buf = new Uint8Array(await r.arrayBuffer());
  let i = 0, line = "", w = 0, h = 0, lines = 0;
  const next = () => { let s = ""; while (i < buf.length && buf[i] !== 10) s += String.fromCharCode(buf[i++]); i++; return s; };
  for (;;) { line = next(); lines++; if (line === "") break; if (lines > 40) throw new Error("bad hdr"); }
  const res = /^-Y (\d+) \+X (\d+)$/.exec(next()); if (!res) throw new Error("bad hdr size");
  h = +res[1]; w = +res[2];
  const data = new Float32Array(w * h * 4);
  for (let y = 0; y < h; y++) {
    const row = (h - 1 - y) * w * 4;      // the file's first scanline is the top; the texture's first row is the bottom
    for (let x = 0; x < w; x++) {
      const e = buf[i + 3], f = e ? Math.pow(2, e - 136) : 0, o = row + x * 4;
      data[o] = buf[i] * f; data[o + 1] = buf[i + 1] * f; data[o + 2] = buf[i + 2] * f; data[o + 3] = 1; i += 4;
    }
  }
  const t = new THREE.DataTexture(data, w, h, THREE.RGBAFormat, THREE.FloatType);
  t.mapping = THREE.EquirectangularReflectionMapping; t.colorSpace = THREE.LinearSRGBColorSpace; t.minFilter = THREE.LinearFilter; t.magFilter = THREE.LinearFilter;
  t.generateMipmaps = false; t.needsUpdate = true;
  return t;
}
const breathe = () => new Promise(r => setTimeout(r, 0));
async function fonts(){
  try {
    if (!document.fonts || !document.fonts.load) return false;
    const wait = Promise.all([document.fonts.load('40px "Instrument Serif"'), document.fonts.load('italic 40px "Instrument Serif"')]);
    await Promise.race([wait, new Promise(r => setTimeout(r, 700))]);
    return document.fonts.check('40px "Instrument Serif"');
  } catch (e) { return false; }
}
async function loadSet(lean){
  const q = lean ? "_s" : "";
  const [leatherD, leatherN, leatherR, woodD, woodN, woodR, paperD, paperN, paperR, env, serif] = await Promise.all([
    photo(FILE(`leather_diff${q}.jpg`)), photo(FILE(`leather_nor${q}.jpg`)), photo(FILE(`leather_rough${q}.jpg`)),
    photo(FILE(`wood_diff${q}.jpg`)), photo(FILE(`wood_nor${q}.jpg`)), photo(FILE(`wood_rough${q}.jpg`)),
    photo(FILE(`paper_diff${q}.jpg`)), photo(FILE(`paper_nor${q}.jpg`)), photo(FILE("paper_rough.jpg")),
    loadHDR(FILE(lean ? "env_s.hdr" : "env.hdr")), fonts()]);
  return {lean, leather: [leatherD, leatherN, leatherR], wood: [woodD, woodN, woodR], paper: [paperD, paperN, paperR], env, serif};
}
export function prepare(opts = {}){
  const lean = opts.lean != null ? !!opts.lean : autoLean();
  if (loading && loadingLean === lean) return loading;
  loadingLean = lean;
  loading = loadSet(lean);
  loading.catch(() => { loading = null; });
  return loading;
}
export function supported(){
  try { const c = document.createElement("canvas"); return !!(window.WebGL2RenderingContext && c.getContext("webgl2")); } catch (e) { return false; }
}

/* ================================ pictures drawn here ================================ */
function drawn(w, h, draw){ const c = document.createElement("canvas"); c.width = w; c.height = h; draw(c.getContext("2d"), w, h); return c; }
function ctex(c, srgb = true, aniso = 8){ const t = new THREE.CanvasTexture(c); if (srgb) t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = aniso; return t; }
function texOf(img, srgb, repeat, aniso = 8){
  if (!img) return null;
  const t = new THREE.Texture(img); t.needsUpdate = true; if (srgb) t.colorSpace = THREE.SRGBColorSpace;
  if (typeof ImageBitmap !== "undefined" && img instanceof ImageBitmap) t.flipY = false;      // decoded already turned over
  if (repeat) t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.anisotropy = aniso; return t;
}
/* a decoded picture may be an ImageBitmap already turned over: drawn on a canvas it must be turned back */
function tile(g, img, w, h, scale, flipped){
  const iw = img.width, ih = img.height, tw = Math.round(iw * scale), th = Math.round(ih * scale);
  for (let y = 0; y < h; y += th) for (let x = 0; x < w; x += tw) {
    if (flipped) { g.save(); g.translate(x, y + th); g.scale(1, -1); g.drawImage(img, 0, 0, tw, th); g.restore(); }
    else g.drawImage(img, x, y, tw, th);
  }
}
const isBitmap = img => typeof ImageBitmap !== "undefined" && img instanceof ImageBitmap;
const SERIF = s => `${s ? '"Instrument Serif", ' : ""}Georgia, "Times New Roman", "Noto Serif", serif`;
const SANS = `"Instrument Sans", "Segoe UI", system-ui, -apple-system, sans-serif`;
const INK = "#1f1a17", INK2 = "#2c2521", RULE = "rgba(90, 120, 150, 0.36)", MARGIN = "rgba(190, 80, 70, 0.45)";

/* one page face, w by h pixels for a page Wp by Hp: cream paper over the photographed fibre, faint ruled lines and a
   margin, the words, and a ghost of the next face through the paper. o: {kind, title, zone, items, ghost, serif} */
function drawPage(g, w, h, A, o){
  const k = w / 1024, flipped = isBitmap(A.paper[0]);
  g.fillStyle = "#f3ead6"; g.fillRect(0, 0, w, h);
  g.save(); g.globalCompositeOperation = "multiply"; g.globalAlpha = 0.9; tile(g, A.paper[0], w, h, (w / A.paper[0].width) * 1.0, flipped); g.restore();
  g.save(); g.globalCompositeOperation = "multiply"; g.fillStyle = "#f7efe0"; g.fillRect(0, 0, w, h); g.restore();      // the cream
  /* a little unevenness in the paper's colour, as sheets have */
  const R = rng(7 + (o.seed || 0));
  for (let i = 0; i < 14; i++) { const x = R() * w, y = R() * h, r = (0.25 + R() * 0.3) * w;
    const gr = g.createRadialGradient(x, y, 0, x, y, r); gr.addColorStop(0, `rgba(120, 90, 60, ${0.018 + R() * 0.02})`); gr.addColorStop(1, "rgba(120,90,60,0)"); g.fillStyle = gr; g.fillRect(0, 0, w, h); }
  const serif = SERIF(o.serif), left = o.left;
  const mx = (left ? 60 : 118) * k, mx2 = (left ? 118 : 60) * k;      // the inner margin is wider than the outer
  if (o.kind !== "title" && o.kind !== "blank") {
    /* ruled lines 8 mm apart (40 px at this scale), a margin rule, and holes' shadows not: a bound notebook */
    g.strokeStyle = RULE; g.lineWidth = Math.max(1, 1.3 * k);
    const y0 = 215 * k, step = 40 * k;
    for (let y = y0; y < h - 70 * k; y += step) { g.beginPath(); g.moveTo(mx, y + 0.5); g.lineTo(w - mx2, y + 0.5); g.stroke(); }
    g.strokeStyle = MARGIN; g.lineWidth = Math.max(1, 1.6 * k); g.beginPath(); g.moveTo(mx + 86 * k, 150 * k); g.lineTo(mx + 86 * k, h - 60 * k); g.stroke();
  }
  g.fillStyle = INK; g.textBaseline = "alphabetic";
  const text = (s, x, y, font, color = INK, align = "left") => { g.font = font; g.fillStyle = color; g.textAlign = align; g.fillText(s, x, y); };
  const fit = (s, maxW, font) => { g.font = font; while (s.length > 8 && g.measureText(s).width > maxW) s = s.replace(/\s+\S*$/, "") + "…"; return s; };
  if (o.kind === "title") {
    text("THE NOTEBOOK", w / 2, 520 * k, `${58 * k}px ${serif}`, INK, "center");
    g.save(); g.font = `${58 * k}px ${serif}`; const tw = g.measureText("THE NOTEBOOK").width; g.strokeStyle = "rgba(47,107,94,.85)"; g.lineWidth = 2.2 * k;
    g.beginPath(); g.moveTo(w / 2 - tw / 2, 548 * k); g.lineTo(w / 2 + tw / 2, 548 * k); g.stroke(); g.restore();
    text("The Civic Archive", w / 2, 610 * k, `italic ${34 * k}px ${serif}`, INK2, "center");
    text("Where the details live", w / 2, 700 * k, `${26 * k}px ${serif}`, INK2, "center");
    text("sources · working · what a figure cannot tell you", w / 2, 742 * k, `${20 * k}px ${serif}`, "#6a5f58", "center");
  } else if (o.kind === "contents") {
    text("Contents", mx, 150 * k, `${54 * k}px ${serif}`);
    let y = 215 * k + 40 * k * 1.5;
    for (const z of o.items) {
      text(z, mx + 100 * k, y - 10 * k, `${30 * k}px ${serif}`, INK);
      y += 80 * k;
    }
    text("Each page: the short of it, the figures, where they come from,", mx + 100 * k, h - 190 * k, `italic ${21 * k}px ${serif}`, INK2);
    text("what they cannot tell you, related pages and the way back.", mx + 100 * k, h - 160 * k, `italic ${21 * k}px ${serif}`, INK2);
  } else if (o.kind === "zone") {
    text(o.zone, mx, 150 * k, `${54 * k}px ${serif}`);
    text("the notebook's pages for this space", mx + 100 * k, 215 * k + 30 * k, `italic ${22 * k}px ${serif}`, INK2);
    /* a few entries' shapes, as a reader's own index: short rules of differing length, no words invented */
    const R2 = rng(11 + o.zone.length);
    let y = 215 * k + 40 * k * 3;
    for (let i = 0; i < 6; i++) { g.strokeStyle = "rgba(60,50,45,.55)"; g.lineWidth = 2.4 * k; g.beginPath(); g.moveTo(mx + 100 * k, y - 12 * k); g.lineTo(mx + 100 * k + (180 + R2() * 320) * k, y - 12 * k); g.stroke(); y += 80 * k; }
  } else if (o.kind === "page") {
    const title = fit(o.title || "The Notebook", w - mx - mx2, `${52 * k}px ${serif}`);
    text(title, mx, 158 * k, `${52 * k}px ${serif}`);
    if (o.zone) text(o.zone, mx, 100 * k, `${24 * k}px ${SANS}`, "#2F6B5E");
    const heads = ["The short of it", "Where it comes from", "What it cannot tell you", "Related pages"];
    let y = 215 * k + 40 * k;
    for (const hd of heads) { text(hd, mx + 100 * k, y - 10 * k, `italic ${31 * k}px ${serif}`, INK2); y += 40 * k * 5; }
  }
  /* the next face shows faintly through the sheet (mirrored, since it is on the other side) */
  if (o.ghost) { g.save(); g.globalAlpha = 0.055; g.translate(w, 0); g.scale(-1, 1); g.drawImage(o.ghost, 0, 0, w, h); g.restore(); }
}
function pageCanvas(A, o, lean){ const w = lean ? 512 : 1024; return drawn(w, Math.round(w * NB.Hp / NB.Wp), (g, W, H) => drawPage(g, W, H, A, o)); }
/* the endpapers: cream with a small printed lattice in the site's own verdigris */
function endpaperCanvas(A, lean){
  const w = lean ? 512 : 1024; return drawn(w, Math.round(w * NB.H / NB.W), (g, W, H) => {
    g.fillStyle = "#e4d4b4"; g.fillRect(0, 0, W, H);
    g.save(); g.globalCompositeOperation = "multiply"; g.globalAlpha = 0.8; tile(g, A.paper[0], W, H, W / A.paper[0].width, isBitmap(A.paper[0])); g.restore();
    const st = 46 * W / 1024; g.strokeStyle = "rgba(47,107,94,.34)"; g.lineWidth = 1.1 * W / 1024;
    for (let y = -st; y < H + st; y += st) for (let x = -st; x < W + st; x += st) { g.beginPath(); g.moveTo(x, y + st / 2); g.lineTo(x + st / 2, y); g.lineTo(x + st, y + st / 2); g.lineTo(x + st / 2, y + st); g.closePath(); g.stroke(); }
    g.fillStyle = "rgba(47,107,94,.5)"; for (let y = 0; y < H + st; y += st) for (let x = 0; x < W + st; x += st) { g.beginPath(); g.arc(x, y, 2.2 * W / 1024, 0, 7); g.fill(); }
  });
}
/* the page block's edges: the leaves' edges as fine lines */
function edgesCanvas(lean){
  const w = lean ? 512 : 1024, h = lean ? 96 : 192; return drawn(w, h, (g, W, H) => {
    g.fillStyle = "#ecdfc6"; g.fillRect(0, 0, W, H); const R = rng(3);
    for (let y = 0; y < H; y += 1.6) { g.fillStyle = `rgba(${150 + R() * 40 | 0}, ${120 + R() * 40 | 0}, ${80 + R() * 40 | 0}, ${0.16 + R() * 0.22})`; g.fillRect(0, y, W, 0.8); }
  });
}
/* the leather of a board: the photographed hide (its grain scaled to a binding's finer grain), tinted a deep oxblood brown,
   and on the front the title in brass foil: colour, roughness and normal pictures that agree with each other */
function coverCanvases(A, lean, front){
  const w = lean ? 512 : 1024, h = Math.round(w * NB.H / NB.W), scale = (w / A.leather[0].width) * 1.45, flipped = isBitmap(A.leather[0]);
  const map = drawn(w, h, (g, W, H) => {
    tile(g, A.leather[0], W, H, scale, flipped);
    g.save(); g.globalCompositeOperation = "multiply"; g.fillStyle = "#a86f4e"; g.fillRect(0, 0, W, H); g.restore();
    /* the edges a little darker, as handled leather is */
    const v = g.createRadialGradient(W / 2, H / 2, W * 0.4, W / 2, H / 2, W * 1.0); v.addColorStop(0, "rgba(0,0,0,0)"); v.addColorStop(1, "rgba(20,8,4,.22)"); g.fillStyle = v; g.fillRect(0, 0, W, H);
  });
  const foil = front ? drawn(w, h, (g, W, H) => {      // the title as a mask
    const k = W / 1024, serif = SERIF(A.serif);
    g.fillStyle = "#fff"; g.textAlign = "center"; g.textBaseline = "alphabetic";
    g.font = `${74 * k}px ${serif}`; g.fillText("NOTEBOOK", W / 2, 560 * k);
    g.font = `italic ${34 * k}px ${serif}`; g.fillText("The Civic Archive", W / 2, 630 * k);
    g.fillRect(W / 2 - 170 * k, 470 * k, 340 * k, 2.5 * k); g.fillRect(W / 2 - 170 * k, 668 * k, 340 * k, 2.5 * k);
    g.fillRect(W / 2 - 120 * k, 478 * k, 240 * k, 1.5 * k); g.fillRect(W / 2 - 120 * k, 676 * k, 240 * k, 1.5 * k);
  }) : null;
  if (foil) {
    const g = map.getContext("2d");
    g.save(); g.globalCompositeOperation = "source-over"; g.drawImage(brassFoil(foil, w, h), 0, 0); g.restore();
  }
  const rough = drawn(w, h, (g, W, H) => {
    tile(g, A.leather[2], W, H, scale, isBitmap(A.leather[2]));
    g.save(); g.globalCompositeOperation = "multiply"; g.fillStyle = "#d9d9d9"; g.fillRect(0, 0, W, H); g.restore();      // a touch more polish than the upholstery
    if (foil) { g.save(); g.globalCompositeOperation = "destination-out"; g.drawImage(foil, 0, 0); g.restore(); g.save(); g.globalCompositeOperation = "destination-over"; g.fillStyle = "#4a4a4a"; g.fillRect(0, 0, W, H); g.restore(); }
  });
  const normal = drawn(w, h, (g, W, H) => { tile(g, A.leather[1], W, H, scale, isBitmap(A.leather[1])); });
  if (foil) deboss(normal, foil);
  return {map, rough, normal};
}
/* the foil: brass, a little brighter where the light would catch its edge */
function brassFoil(mask, w, h){
  return drawn(w, h, (g, W, H) => {
    g.drawImage(mask, 0, 0);
    g.globalCompositeOperation = "source-in";
    const gr = g.createLinearGradient(0, 0, W, H); gr.addColorStop(0, "#e2bd6a"); gr.addColorStop(0.5, "#c89a45"); gr.addColorStop(1, "#dcb45e"); g.fillStyle = gr; g.fillRect(0, 0, W, H);
  });
}
/* press the title into the leather: the normal map tilted at the letters' edges */
function deboss(normal, mask){
  const w = normal.width, h = normal.height, gm = mask.getContext("2d", {willReadFrequently: true}), gn = normal.getContext("2d", {willReadFrequently: true});
  const y0 = Math.max(0, Math.floor(h * 0.40)), y1 = Math.min(h, Math.ceil(h * 0.68)), hh = y1 - y0;
  const m = gm.getImageData(0, y0, w, hh).data, n = gn.getImageData(0, y0, w, hh), d = n.data, k = 1.6;
  const at = (x, y) => m[((clamp(y, 0, hh - 1) * w) + clamp(x, 0, w - 1)) * 4] / 255;
  for (let y = 0; y < hh; y++) for (let x = 0; x < w; x++) {
    const gx = (at(x + 1, y) - at(x - 1, y)) + 0.5 * (at(x + 2, y) - at(x - 2, y)), gy = (at(x, y + 1) - at(x, y - 1)) + 0.5 * (at(x, y + 2) - at(x, y - 2));
    if (!gx && !gy) continue;
    const o = (y * w + x) * 4;
    let nx = (d[o] / 255) * 2 - 1 + gx * k, ny = (d[o + 1] / 255) * 2 - 1 - gy * k, nz = (d[o + 2] / 255) * 2 - 1;
    const l = Math.hypot(nx, ny, nz) || 1; nx /= l; ny /= l; nz /= l;
    d[o] = (nx * 0.5 + 0.5) * 255; d[o + 1] = (ny * 0.5 + 0.5) * 255; d[o + 2] = (nz * 0.5 + 0.5) * 255;
  }
  gn.putImageData(n, 0, y0);
}
/* a soft dark print under a thing resting on the desk */
function shadowCanvas(){
  return drawn(256, 256, (g, W, H) => {
    const gr = g.createRadialGradient(W / 2, H / 2, W * 0.3, W / 2, H / 2, W * 0.5); gr.addColorStop(0, "rgba(0,0,0,1)"); gr.addColorStop(1, "rgba(0,0,0,0)");
    g.fillStyle = gr; g.fillRect(0, 0, W, H);
  });
}
/* shelves of books for the wall behind, seen only out of focus */
function spinesCanvas(lean){
  const w = lean ? 1024 : 2048, h = w / 2; return drawn(w, h, (g, W, H) => {
    g.fillStyle = "#3a2a1e"; g.fillRect(0, 0, W, H); const R = rng(41), rows = 6, rh = H / rows;
    const hues = ["#6b2f27", "#2f4a3f", "#3f3a63", "#7a5a2c", "#5a2a2a", "#2a3b55", "#6e5a3d", "#4b3a2b", "#8a6a35", "#3c2f2b", "#5e6a4a", "#703a3a"];
    for (let r = 0; r < rows; r++) {
      const y1 = (r + 1) * rh - rh * 0.09;      // the shelf
      let x = 0;
      while (x < W) { const bw = (14 + R() * 30) * W / 2048, bh = rh * (0.62 + R() * 0.28), c = hues[R() * hues.length | 0];
        g.fillStyle = c; g.fillRect(x, y1 - bh, bw - 2, bh);
        g.fillStyle = "rgba(255,230,180,.28)"; g.fillRect(x + bw * 0.25, y1 - bh * 0.72, bw * 0.5, 2); g.fillRect(x + bw * 0.25, y1 - bh * 0.3, bw * 0.5, 2);
        g.fillStyle = "rgba(0,0,0,.25)"; g.fillRect(x + bw - 4, y1 - bh, 3, bh); x += bw; }
      g.fillStyle = "#4a3626"; g.fillRect(0, y1, W, rh * 0.09);
      g.fillStyle = "rgba(0,0,0,.35)"; g.fillRect(0, y1 - 6, W, 6);
    }
  });
}

/* ================================ geometry ================================ */
/* a board with rounded corners: top, bottom and a side band, with uvs (top and bottom: x/W, z/H; the band: along it). Its
   origin is its spine edge's middle: x from 0 to W, z from -H/2 to H/2, y from 0 to b */
function outline(W, H, r, n = 6){
  const pts = [];      // anticlockwise seen from above (x right, z toward the viewer): start at the spine's near end
  const corner = (cx, cz, a0) => { for (let i = 0; i <= n; i++) { const a = a0 + (i / n) * Math.PI / 2; pts.push([cx + r * Math.cos(a), cz + r * Math.sin(a)]); } };
  pts.push([0, H / 2]); pts.push([0, -H / 2]);
  corner(W - r, -H / 2 + r, -Math.PI / 2); corner(W - r, H / 2 - r, 0);
  return pts;
}
function boardGeometry(W, H, b, r){
  const o = outline(W, H, r), pos = [], nrm = [], uv = [], idx = [], groups = [];
  const cap = (y, up) => {
    const base = pos.length / 3;
    pos.push(W / 2, y, 0); nrm.push(0, up, 0); uv.push(0.5, 0.5);
    for (const [x, z] of o) { pos.push(x, y, z); nrm.push(0, up, 0); uv.push(x / W, 1 - (z + H / 2) / H); }
    const start = idx.length;
    for (let i = 0; i < o.length; i++) { const a = base + 1 + i, c = base + 1 + (i + 1) % o.length; if (up > 0) idx.push(base, c, a); else idx.push(base, a, c); }
    return [start, idx.length - start];
  };
  const [t0, tn] = cap(b, 1); groups.push({start: t0, count: tn, materialIndex: 0});
  const [b0, bn] = cap(0, -1); groups.push({start: b0, count: bn, materialIndex: 1});
  const base = pos.length / 3, s0 = idx.length; let along = 0;
  for (let i = 0; i <= o.length; i++) {
    const [x, z] = o[i % o.length], [px, pz] = o[(i + 1) % o.length], [qx, qz] = o[(i - 1 + o.length) % o.length];
    const tx = px - qx, tz = pz - qz, l = Math.hypot(tx, tz) || 1, nx = tz / l, nz = -tx / l;      // outward
    if (i > 0) { const [ax, az] = o[(i - 1) % o.length]; along += Math.hypot(x - ax, z - az); }
    pos.push(x, 0, z, x, b, z); nrm.push(nx, 0, nz, nx, 0, nz); uv.push(along / (2 * (W + H)) * 8, 0, along / (2 * (W + H)) * 8, 1);
  }
  for (let i = 0; i < o.length; i++) { const a = base + i * 2, c = base + (i + 1) * 2; idx.push(a, a + 1, c, c, a + 1, c + 1); }
  groups.push({start: s0, count: idx.length - s0, materialIndex: 2});
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3)); g.setAttribute("normal", new THREE.Float32BufferAttribute(nrm, 3)); g.setAttribute("uv", new THREE.Float32BufferAttribute(uv, 2));
  g.setIndex(idx); for (const gr of groups) g.addGroup(gr.start, gr.count, gr.materialIndex);
  return g;
}
/* a brass corner on a board's outer corner at z = side * H/2: a plate above and below and a band round the edge */
function cornerGeometry(W, H, b, r, side, leg = 0.014, th = 0.0005){
  const o = outline(W, H, r, 8).filter(([x, z]) => x > W - leg - 1e-6 && (side > 0 ? z > H / 2 - leg - 1e-6 : z < -H / 2 + leg + 1e-6));
  // the corner's arc in order: from the long edge's point to the short edge's point
  const pts = [side > 0 ? [W, H / 2 - leg] : [W - leg, -H / 2], ...o.filter(([x, z]) => Math.abs(x - W) > 1e-6 || Math.abs(Math.abs(z) - H / 2) > 1e-6), side > 0 ? [W - leg, H / 2] : [W, -H / 2 + leg]];
  const inner = [W - leg, side > 0 ? H / 2 - leg : -H / 2 + leg];
  const pos = [], nrm = [], uv = [], idx = [];
  const plate = (y, up) => {
    const base = pos.length / 3;
    pos.push(inner[0], y, inner[1]); nrm.push(0, up, 0); uv.push(0.5, 0.5);
    for (const [x, z] of pts) { pos.push(x, y, z); nrm.push(0, up, 0); uv.push(x / W, z / H); }
    for (let i = 0; i + 1 < pts.length; i++) { const a = base + 1 + i, c = a + 1; if (up > 0) idx.push(base, c, a); else idx.push(base, a, c); }
  };
  plate(b + th, 1); plate(-th, -1);
  const base = pos.length / 3;
  for (let i = 0; i < pts.length; i++) {
    const [x, z] = pts[i], [px, pz] = pts[Math.min(i + 1, pts.length - 1)], [qx, qz] = pts[Math.max(i - 1, 0)];
    const tx = px - qx, tz = pz - qz, l = Math.hypot(tx, tz) || 1, nx = tz / l, nz = -tx / l;
    pos.push(x + nx * th, -th, z + nz * th, x + nx * th, b + th, z + nz * th); nrm.push(nx, 0, nz, nx, 0, nz); uv.push(i / pts.length, 0, i / pts.length, 1);
  }
  for (let i = 0; i + 1 < pts.length; i++) { const a = base + i * 2, c = base + (i + 1) * 2; idx.push(a, a + 1, c, c, a + 1, c + 1); }
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3)); g.setAttribute("normal", new THREE.Float32BufferAttribute(nrm, 3)); g.setAttribute("uv", new THREE.Float32BufferAttribute(uv, 2));
  g.setIndex(idx); return g;
}
/* a strip along a curve (a ribbon, the spine's leather): n segments, width w across, with uvs */
function stripGeometry(n, m = 1){ const g = new THREE.PlaneGeometry(1, 1, n, m); g.attributes.position.setUsage(THREE.DynamicDrawUsage); return g; }
function layStrip(geo, n, m, pointAt, widthAt, across){
  const p = geo.attributes.position;
  for (let i = 0; i <= n; i++) {
    const u = i / n, P = pointAt(u), wdt = widthAt(u);
    for (let j = 0; j <= m; j++) { const v = j / m - 0.5, k = j * (n + 1) + i; p.setXYZ(k, P.x + across.x * v * wdt, P.y + across.y * v * wdt, P.z + across.z * v * wdt); }
  }
  p.needsUpdate = true; geo.computeVertexNormals();
}

/* ================================ the scene ================================ */
function build(renderer, aspect, A, opts = {}){
  const lean = !!A.lean, STILL = !!opts.still;
  const scene = new THREE.Scene();
  const cam = new THREE.PerspectiveCamera(36, aspect, 0.03, 40);
  const aniso = Math.min(16, renderer.capabilities.getMaxAnisotropy ? renderer.capabilities.getMaxAnisotropy() : 8);
  const marks = [["start", performance.now()]], mark = s => marks.push([s, performance.now()]);

  /* ---------- the room's light: the photographed room, prefiltered, for reflections and fill, and seen behind ---------- */
  const pmrem = new THREE.PMREMGenerator(renderer); pmrem.compileEquirectangularShader();
  const envRT = pmrem.fromEquirectangular(A.env); pmrem.dispose();
  scene.environment = envRT.texture; scene.background = envRT.texture;
  scene.environmentRotation.set(0, 95 * D2R, 0); scene.backgroundRotation.set(0, 95 * D2R, 0);
  scene.backgroundBlurriness = lean ? 0.35 : 0.28; scene.backgroundIntensity = 0.75; scene.environmentIntensity = 0.5;
  mark("env");

  /* ---------- lights: the desk lamp (warm, from the right and behind), the window (cool, from the left) ---------- */
  const lamp = new THREE.SpotLight(0xffe1ba, 1.5, 0, 54 * D2R, 0.8, 2);
  lamp.position.set(0.375, 0.325, -0.23); lamp.target.position.set(0.05, 0.0, 0.02); scene.add(lamp, lamp.target);
  lamp.castShadow = true; lamp.shadow.mapSize.set(lean ? 1024 : 2048, lean ? 1024 : 2048); lamp.shadow.camera.near = 0.08; lamp.shadow.camera.far = 2.5;
  lamp.shadow.bias = -0.00012; lamp.shadow.normalBias = 0.0012; lamp.shadow.radius = 3;
  const LAMP = lamp.intensity;
  const win = new THREE.DirectionalLight(0xdbe6ff, 1.15);
  win.position.set(-1.1, 1.5, -0.55); win.target.position.set(0.05, 0, 0); scene.add(win, win.target);
  win.castShadow = true; win.shadow.mapSize.set(lean ? 1024 : 2048, lean ? 1024 : 2048);
  Object.assign(win.shadow.camera, {left: -0.5, right: 0.5, top: 0.5, bottom: -0.5, near: 0.3, far: 5}); win.shadow.bias = -0.0002; win.shadow.normalBias = 0.002; win.shadow.radius = 5;
  scene.add(new THREE.HemisphereLight(0xfff1dc, 0x3a2b20, 0.09));

  /* ---------- materials ---------- */
  const mats = [];
  const M = (m) => { mats.push(m); return m; };
  const leatherTex = {front: coverCanvases(A, lean, true), back: coverCanvases(A, lean, false)};
  const leatherMat = (c) => M(new THREE.MeshPhysicalMaterial({map: ctex(c.map, true, aniso), roughnessMap: ctex(c.rough, false, aniso), normalMap: ctex(c.normal, false, aniso), normalScale: new THREE.Vector2(0.9, 0.9),
    roughness: 1, metalness: 0, sheen: 0.18, sheenRoughness: 0.75, sheenColor: new THREE.Color(0xc9a070), clearcoat: 0.10, clearcoatRoughness: 0.55, envMapIntensity: 0.9}));
  const plainLeather = M(new THREE.MeshPhysicalMaterial({map: texOf(A.leather[0], true, true, aniso), normalMap: texOf(A.leather[1], false, true, aniso), roughnessMap: texOf(A.leather[2], false, true, aniso),
    color: new THREE.Color(0xa86f4e), roughness: 0.95, sheen: 0.15, sheenRoughness: 0.8, sheenColor: new THREE.Color(0xc9a070), envMapIntensity: 0.9, side: THREE.DoubleSide}));
  for (const t of [plainLeather.map, plainLeather.normalMap, plainLeather.roughnessMap]) t.repeat.set(5, 5);
  const endMat = M(new THREE.MeshStandardMaterial({map: ctex(endpaperCanvas(A, lean), true, aniso), roughness: 0.92, envMapIntensity: 0.35}));
  const edgeMat = M(new THREE.MeshStandardMaterial({map: ctex(edgesCanvas(lean), true, aniso), roughness: 0.96, envMapIntensity: 0.4}));
  const brass = M(new THREE.MeshPhysicalMaterial({color: 0xd2ab5e, metalness: 1, roughness: 0.32, envMapIntensity: 1.3, clearcoat: 0.2, clearcoatRoughness: 0.3}));
  const brassDull = M(new THREE.MeshPhysicalMaterial({color: 0xb08a4c, metalness: 1, roughness: 0.42, envMapIntensity: 1.1}));
  const paperN = texOf(A.paper[1], false, true, aniso), paperR = texOf(A.paper[2], false, true, aniso);
  paperN.repeat.set(1.25, 1.25 * NB.Hp / NB.Wp); paperR.repeat.copy(paperN.repeat);
  const paperMat = (c, back) => { const m = M(new THREE.MeshPhysicalMaterial({map: ctex(c, true, aniso), normalMap: paperN, normalScale: new THREE.Vector2(0.7, 0.7), roughnessMap: paperR, roughness: 1,
    sheen: 0.35, sheenRoughness: 0.85, sheenColor: new THREE.Color(0xfff4e2), envMapIntensity: 0.4, side: back ? THREE.BackSide : THREE.FrontSide}));
    if (back) { m.map.wrapS = THREE.RepeatWrapping; m.map.repeat.x = -1; m.map.offset.x = 1; } return m; };
  const woodMat = M(new THREE.MeshPhysicalMaterial({map: texOf(A.wood[0], true, true, aniso), normalMap: texOf(A.wood[1], false, true, aniso), roughnessMap: texOf(A.wood[2], false, true, aniso), roughness: 1,
    normalScale: new THREE.Vector2(0.7, 0.7), clearcoat: 0.22, clearcoatRoughness: 0.5, envMapIntensity: 1.0, color: new THREE.Color(0xd8c3a8)}));
  for (const t of [woodMat.map, woodMat.normalMap, woodMat.roughnessMap]) t.repeat.set(1.9, 3.8);      // the desks are turned so the grain runs their length
  const ribbonMat = M(new THREE.MeshPhysicalMaterial({color: 0x33655a, roughness: 0.5, sheen: 1.0, sheenRoughness: 0.35, sheenColor: new THREE.Color(0x9fd8c7), envMapIntensity: 0.8, side: THREE.DoubleSide}));
  const lacquer = M(new THREE.MeshPhysicalMaterial({color: 0x0c0b0d, roughness: 0.2, clearcoat: 1, clearcoatRoughness: 0.06, envMapIntensity: 1.2}));
  const shadowMat = M(new THREE.MeshBasicMaterial({map: ctex(shadowCanvas(), false), transparent: true, opacity: 0.55, depthWrite: false, color: 0x1a120c}));
  mark("materials");

  /* ---------- the desk, and the room behind it ---------- */
  const desk = new THREE.Mesh(new THREE.BoxGeometry(0.95, 0.035, 1.9), woodMat); desk.position.set(0.25, -0.0175, -0.12); desk.rotation.y = Math.PI / 2; desk.receiveShadow = true; scene.add(desk);
  const deskFar = new THREE.Mesh(new THREE.BoxGeometry(0.9, 0.035, 2.4), woodMat); deskFar.position.set(0.3, -0.0175, -1.75); deskFar.rotation.y = Math.PI / 2; scene.add(deskFar);
  const floor = new THREE.Mesh(new THREE.PlaneGeometry(12, 12), M(new THREE.MeshStandardMaterial({color: 0x4a3a2e, roughness: 1}))); floor.rotation.x = -Math.PI / 2; floor.position.y = -0.76; scene.add(floor);
  const shelves = new THREE.Mesh(new THREE.PlaneGeometry(7, 3.5), M(new THREE.MeshStandardMaterial({map: ctex(spinesCanvas(lean), true, 4), roughness: 0.85}))); shelves.position.set(0.4, 0.95, -3.1); scene.add(shelves);
  /* a lamp on each desk: a brass base and stem, a hooded shade, a glowing bulb under it */
  const bulbMat = M(new THREE.MeshBasicMaterial({color: new THREE.Color(1.0, 0.86, 0.62).multiplyScalar(5.0)}));
  const hoodIn = M(new THREE.MeshStandardMaterial({color: 0xf2e2c4, roughness: 0.7, emissive: new THREE.Color(1.0, 0.72, 0.42), emissiveIntensity: 1.2, side: THREE.BackSide}));
  function lampAt(x, z, yaw, big){
    const g = new THREE.Group(); g.position.set(x, 0, z); g.rotation.y = yaw;
    const base = new THREE.Mesh(new THREE.CylinderGeometry(0.07, 0.078, 0.016, 40), brass); base.position.y = 0.008; base.castShadow = true;
    const stem = new THREE.Mesh(new THREE.CylinderGeometry(0.007, 0.009, 0.31, 20), brass); stem.position.y = 0.17;
    const arm = new THREE.Mesh(new THREE.CylinderGeometry(0.005, 0.005, 0.16, 12), brass); arm.rotation.z = Math.PI / 2; arm.position.set(-0.07, 0.325, 0);
    const hood = new THREE.Mesh(new THREE.CylinderGeometry(0.052, 0.052, 0.24, 36, 1, true, 0, Math.PI), brass); hood.rotation.z = Math.PI / 2; hood.position.set(-0.15, 0.33, 0);
    const hoodI = new THREE.Mesh(hood.geometry, hoodIn); hoodI.rotation.copy(hood.rotation); hoodI.position.copy(hood.position);
    const bulb = new THREE.Mesh(new THREE.CapsuleGeometry(0.011, 0.05, 6, 16), bulbMat); bulb.rotation.z = Math.PI / 2; bulb.position.set(-0.15, 0.318, 0);
    g.add(base, stem, arm, hood, hoodI, bulb);
    if (big) { const pl = new THREE.PointLight(0xffd2a0, 0.5, 4, 2); pl.position.set(-0.15, 0.3, 0); g.add(pl); }      // the far lamps warm the shelves
    scene.add(g); return g;
  }
  lampAt(0.52, -0.27, 15 * D2R); lampAt(0.9, -1.75, -35 * D2R, true); lampAt(-0.7, -1.75, 25 * D2R, true);
  /* a fountain pen, capped, lying beside the notebook */
  {
    const g = new THREE.Group(); g.position.set(0.215, 0.0062, 0.05); g.rotation.y = -28 * D2R; g.rotation.z = Math.PI / 2;
    const barrel = new THREE.Mesh(new THREE.CapsuleGeometry(0.0058, 0.125, 8, 24), lacquer); barrel.castShadow = true;
    const band = new THREE.Mesh(new THREE.CylinderGeometry(0.0061, 0.0061, 0.004, 24), brass); band.position.y = 0.012;
    const band2 = new THREE.Mesh(new THREE.CylinderGeometry(0.006, 0.006, 0.002, 24), brass); band2.position.y = -0.058;
    const clip = new THREE.Mesh(new THREE.BoxGeometry(0.0022, 0.04, 0.0012), brass); clip.position.set(0, 0.04, -0.0066);
    g.add(barrel, band, band2, clip); scene.add(g);
  }
  const penShadow = new THREE.Mesh(new THREE.PlaneGeometry(0.19, 0.05), shadowMat); penShadow.rotation.x = -Math.PI / 2; penShadow.rotation.z = 28 * D2R; penShadow.position.set(0.215, 0.0004, 0.05); penShadow.scale.set(1, 1, 1); scene.add(penShadow);
  mark("room");

  /* ---------- the notebook ---------- */
  const book = new THREE.Group(); scene.add(book);
  const {W, H, b, r, Wp, Hp, Tp, s, leaf, nL} = NB;
  /* the boards */
  const backBoard = new THREE.Mesh(boardGeometry(W, H, b, r), [endMat, leatherMat(leatherTex.back), plainLeather]); backBoard.castShadow = backBoard.receiveShadow = true; book.add(backBoard);
  const frontBoard = new THREE.Group(); book.add(frontBoard);
  const frontMesh = new THREE.Mesh(boardGeometry(W, H, b, r), [leatherMat(leatherTex.front), endMat, plainLeather]); frontMesh.castShadow = frontMesh.receiveShadow = true;
  frontBoard.add(frontMesh);
  /* the board's local frame: its spine edge along z at the origin, its width along +x, its leather side up (+y); the
     group turns and moves it. Closed it lies leather up on top of the block; open it lies leather down on the desk */
  const corners = [];
  for (const side of [-1, 1]) {
    const cF = new THREE.Mesh(cornerGeometry(W, H, b, r, side), brassDull); frontMesh.add(cF); cF.castShadow = true;
    const cB = new THREE.Mesh(cornerGeometry(W, H, b, r, side), brassDull); backBoard.add(cB); cB.castShadow = true; corners.push(cF, cB);
  }
  /* the spine: a flexible leather strip from the back board's edge to the front board's, rounded when closed, flat when open */
  const spineN = 20, spineGeo = stripGeometry(spineN, 1);
  const spine = new THREE.Mesh(spineGeo, plainLeather); spine.castShadow = true; book.add(spine);
  /* the block of pages: a box whose top takes the page on top, and whose top near the spine sinks into the valley */
  const blockGeo = new THREE.BoxGeometry(Wp, Tp, Hp, 64, 1, 1); blockGeo.translate(NB.inset + Wp / 2, b + Tp / 2, 0);
  const blockFlat = Float32Array.from(blockGeo.attributes.position.array);
  blockGeo.attributes.position.setUsage(THREE.DynamicDrawUsage);
  /* the pages' words, by face: the fly-leaf's front (the title), its back (contents), the leaves of the zones on the way
     to this page's zone, and the page itself on top of the block */
  const zone = (opts.path || "").split("/")[0], zi = Math.max(0, ZONE_ORDER.indexOf(zone)), zones = [];
  for (let i = 0; i < 2 * nL - 2; i++) zones.push(ZONES[ZONE_ORDER[(zi - (2 * nL - 2) + i + ZONE_ORDER.length * 2) % ZONE_ORDER.length]]);
  const faces = [];
  const pageTex = [];
  const final = pageCanvas(A, {kind: "page", title: opts.title || "", zone: ZONES[zone] || "", serif: A.serif, seed: 9}, lean);
  const specs = [{kind: "title", serif: A.serif}, {kind: "contents", items: ZONE_ORDER.map(z => ZONES[z]), serif: A.serif, left: true}];
  for (let i = 0; i < 2 * nL - 2; i++) specs.push({kind: "zone", zone: zones[i], serif: A.serif, left: i % 2 === 1, seed: i});
  /* each leaf's two faces: the back is drawn first, so the front can carry the back's ghost; the back carries the front's
     words as a ghost drawn afterwards */
  for (let k = 0; k < nL; k++) {
    faces[2 * k + 1] = pageCanvas(A, specs[2 * k + 1], lean);
    faces[2 * k] = pageCanvas(A, Object.assign({ghost: faces[2 * k + 1]}, specs[2 * k]), lean);
    const g = faces[2 * k + 1].getContext("2d"), w = faces[2 * k + 1].width, h = faces[2 * k + 1].height;
    g.save(); g.globalAlpha = 0.055; g.translate(w, 0); g.scale(-1, 1); g.drawImage(faces[2 * k], 0, 0, w, h); g.restore();
  }
  for (const c of faces) pageTex.push(c);
  const block = new THREE.Mesh(blockGeo, [edgeMat, edgeMat, paperMat(final, false), edgeMat, edgeMat, edgeMat]); block.castShadow = block.receiveShadow = true; book.add(block);
  /* the leaves that turn: a sheet each, bent every frame, with its two faces */
  const nx = lean ? 36 : 60, nz = lean ? 6 : 10, leaves = [];
  for (let k = 0; k < nL; k++) {
    const geo = new THREE.PlaneGeometry(Wp, Hp, nx, nz); geo.attributes.position.setUsage(THREE.DynamicDrawUsage);
    const front = new THREE.Mesh(geo, paperMat(faces[2 * k], false)), back = new THREE.Mesh(geo, paperMat(faces[2 * k + 1], true));
    front.castShadow = true; front.receiveShadow = back.receiveShadow = true; front.frustumCulled = back.frustumCulled = false;
    const g = new THREE.Group(); g.add(front, back); book.add(g);
    leaves.push({geo, k, flat: null});
  }
  /* the ribbon: satin, glued in at the spine's head, lying along the valley under the leaves and out over the tail edge */
  const ribN = 28, ribGeo = stripGeometry(ribN, 1), ribbon = new THREE.Mesh(ribGeo, ribbonMat); ribbon.castShadow = true; book.add(ribbon);
  const ribPath = new THREE.CatmullRomCurve3([V3(0.012, b + 0.0012, -Hp / 2 + 0.03), V3(0.03, b + 0.0012, Hp / 2 - 0.02), V3(0.042, 0.0012, Hp / 2 + 0.025), V3(0.062, 0.0007, Hp / 2 + 0.055), V3(0.088, 0.0005, Hp / 2 + 0.078)]);
  layStrip(ribGeo, ribN, 1, u => ribPath.getPoint(u), () => 0.008, V3(1, 0, 0));
  /* the notebook's own soft shadow on the desk, and the open cover's */
  const bookShadow = new THREE.Mesh(new THREE.PlaneGeometry(W + 0.05, H + 0.05), shadowMat.clone()); bookShadow.rotation.x = -Math.PI / 2; bookShadow.position.set(W / 2, 0.0003, 0); bookShadow.material.opacity = 0.6; book.add(bookShadow);
  const coverShadow = new THREE.Mesh(new THREE.PlaneGeometry(W + 0.05, H + 0.05), shadowMat.clone()); coverShadow.rotation.x = -Math.PI / 2; coverShadow.position.set(-s - W / 2, 0.00025, 0); coverShadow.material.opacity = 0; book.add(coverShadow);
  mats.push(bookShadow.material, coverShadow.material);
  mark("book");

  /* ---------- the book's shape at each moment ---------- */
  /* the right block's top: rises from the valley's floor at the root to the block's full height over wR; the left: from the
     root down to the open board over wL. S eases each */
  const wR = 0.036, wL = 0.03, dS = x => { x = clamp(x); return 6 * x * (1 - x); };
  const state = {open: 0, root: V3(NB.inset, NB.yTop, 0), gut: NB.yTop, kR: 1, kL: 1, restR: [[0, 0], [wR, 0]]};
  /* the slopes are of the sheet's own length, so each is scaled (kR, kL) until the sheet's rise comes out exact */
  const slopeRight = s => Math.atan(state.kR * (NB.yTop - state.gut) * dS(s / wR) / wR);
  const slopeLeft = s => Math.atan(state.kL * (b - state.gut) * dS(s / wL) / wL);      // negative: going down away from the root
  const integ = (fn, w, n = 48) => { let x = 0, y = 0; const out = [[0, 0]]; for (let i = 1; i <= n; i++) { const a = fn((i - 0.5) / n * w); x += Math.cos(a) * w / n; y += Math.sin(a) * w / n; out.push([x, y]); } return out; };
  const settle = () => {
    state.kR = state.kL = 1;
    const want = NB.yTop - state.gut, wantL = b - state.gut;
    let c = integ(slopeRight, wR);
    for (let i = 0; i < 8 && Math.abs(want) > 1e-7; i++) {      // the scale converges in a few steps (the relation is not linear)
      const rise = c[c.length - 1][1]; if (Math.abs(rise) < 1e-9 || Math.abs(rise - want) < 1e-6) break;
      state.kR *= want / rise; c = integ(slopeRight, wR);
    }
    state.restR = c;
    for (let i = 0; i < 8 && Math.abs(wantL) > 1e-7; i++) {
      const d = integ(slopeLeft, wL), drop = d[d.length - 1][1]; if (Math.abs(drop) < 1e-9 || Math.abs(drop - wantL) < 1e-6) break;
      state.kL *= wantL / drop;
    }
  };
  /* the block's top at a distance x from the root: the top sheet's own resting curve, so a sheet lies on it exactly */
  const yRight = x => {
    const c = state.restR, last = c[c.length - 1];
    if (x >= last[0]) return NB.yTop;
    if (x <= 0) return state.gut;
    let i = 1; while (i < c.length - 1 && c[i][0] < x) i++;
    const [x0, y0] = c[i - 1], [x1, y1] = c[i];
    return state.gut + mix(y0, y1, (x - x0) / Math.max(1e-9, x1 - x0));
  };
  const shapeBlock = () => {
    const p = blockGeo.attributes.position;
    for (let i = 0; i < p.count; i++) { const x = blockFlat[i * 3], y = blockFlat[i * 3 + 1];
      if (y > b + Tp * 0.75) p.setY(i, Math.min(NB.yTop, yRight(x - state.root.x))); }
    p.needsUpdate = true; blockGeo.computeVertexNormals();
  };
  /* a leaf turned by u (0 lying on the right, 1 lying on the left): along its width the fold's angle leads and the free edge
     trails; it keeps the resting profile of whichever side it is nearer; across its height the corners curl a little */
  const tmpN = new THREE.Vector2();
  const shapeLeaf = (L, u, k) => {
    const p = L.geo.attributes.position, lift = mix((nL - k) * leaf + 0.00015, (k + 1) * leaf + 0.00015, smooth(u));
    const curlA = 0.0012 * (1 - 0.6 * Math.sin(Math.PI * u)), lag = 0.30, wave = Math.sin(Math.PI * u);
    let x = state.root.x, y = state.root.y + lift;
    for (let i = 0; i <= nx; i++) {
      const sN = i / nx, sM = sN * Wp;
      let a;
      {
        const g = Math.pow(sN, 0.62), ul = clamp((u - lag * g) / (1 - lag * g)), th = Math.PI * smooth(ul);
        const belly = -0.55 * wave * Math.sin(Math.PI * sN) * (1 - sN) ;      // the sheet bows a little as it goes over
        a = th + slopeRight(sM) * (1 + Math.cos(th)) / 2 - slopeLeft(sM) * (1 - Math.cos(th)) / 2 + belly * Math.sin(th);
      }
      if (i > 0) { x += Math.cos(a) * Wp / nx; y += Math.sin(a) * Wp / nx; }
      tmpN.set(-Math.sin(a), Math.cos(a));
      const curl = curlA * sN * sN;
      for (let j = 0; j <= nz; j++) {
        const zN = j / nz - 0.5, z = zN * Hp, c = curl * (zN * zN * 4), idx = j * (nx + 1) + i;
        p.setXYZ(idx, x + tmpN.x * c, y + tmpN.y * c, z);
      }
    }
    p.needsUpdate = true; L.geo.computeVertexNormals();
  };
  const tmpQ = new THREE.Quaternion(), tmpV = V3(), P0 = V3(), P1 = V3(), P2 = V3(), P3 = V3();
  /* the front board and the spine as the cover opens (c from 0 closed to 1 open) */
  const placeCover = (c) => {
    const th = Math.PI * c, c1 = (1 - Math.cos(th)) / 2;
    /* its spine edge swings from the top of the closed block down to the desk, the spine's width to the left */
    frontBoard.position.set(-s * c1, mix(NB.T2, b, c1), 0);
    frontBoard.rotation.set(0, 0, th);
    /* the spine strip: a curve from the back board's edge to the front board's hinge */
    const R = (NB.T2 + b) / 2;
    P0.set(0, 0.0007, 0); P3.set(frontBoard.position.x, mix(NB.T2 + b, 0.0007, c1), 0);
    P1.set(mix(-1.3 * R, -s / 3, c), mix(0.0007, 0.0012, c), 0); P2.set(mix(-1.3 * R, -2 * s / 3, c), mix(2 * R, 0.0012, c), 0);
    const bez = new THREE.CubicBezierCurve3(P0, P1, P2, P3);
    layStrip(spineGeo, spineN, 1, u => bez.getPoint(u), () => H + 0.004, V3(0, 0, 1));
    coverShadow.material.opacity = 0.5 * seg(c, 0.55, 1);
  };
  const placeBook = (t) => {
    const open = STILL ? 1 : inOut(seg(t, 0.55, 1.35));
    state.open = open; state.gut = mix(NB.yTop, NB.gut, open); state.root.set(mix(NB.inset, -s + 0.004, open), state.gut, 0);
    settle(); placeCover(open); shapeBlock();
    for (let k = 0; k < nL; k++) { const t0 = 1.18 + k * 0.36, u = STILL ? 1 : smooth(seg(t, t0, t0 + 0.62)); shapeLeaf(leaves[k], u, k); }
  };

  /* ---------- the eye: where it is and where it looks, second by second ---------- */
  /* on a tall screen the view is pulled back so the notebook still fits */
  let fit = 1; const refit = (asp) => { fit = asp < 1 ? Math.min(1.9, Math.pow(1 / asp, 0.72)) : 1; };
  refit(aspect);
  const poses = [      // t, eye, look-at, zoom
    [0.00, [0.17, 0.57, 0.80], [0.03, 0.10, -0.32], 1.0],
    [0.85, [0.11, 0.47, 0.50], [0.03, 0.05, -0.12], 1.0],
    [1.70, [0.09, 0.41, 0.29], [0.03, 0.02, -0.035], 1.0],
    [2.60, [0.085, 0.36, 0.11], [0.065, 0.01, 0.0], 1.0],
    [3.25, [0.0825, 0.335, 0.015], [0.0745, 0.0, 0.0], 1.0],
    [DUR, [0.0825, 0.335, 0.015], [0.0745, 0.0, 0.0], 1.0]
  ];
  const eyeAt = (t) => {
    /* a smooth path through the poses: a Catmull-Rom over the eye and the look-at */
    let i = 0; while (i < poses.length - 2 && t > poses[i + 1][0]) i++;
    const [t0, e0, l0] = poses[i], [t1, e1, l1] = poses[i + 1], u = inOut(seg(t, t0, t1));
    const E = V3(...e0).lerp(V3(...e1), u), L = V3(...l0).lerp(V3(...l1), u);
    /* the final descent over the page keeps the page filling the view on any screen */
    const last = poses[poses.length - 2];
    if (t > last[0] - 0.9) { const k = seg(t, last[0] - 0.9, last[0]); E.y = mix(E.y, 0.335 * heightFit(), smooth(k)); }
    return {E, L};
  };
  /* the height over the page that fills the view with it: the page's height on a wide screen, its width on a tall one */
  const heightFit = () => { const v = Math.tan(cam.fov / 2 * D2R), hv = v * cam.aspect; return Math.max(Hp * 0.49 / v, Wp * 0.53 / hv) / 0.335; };
  const handheld = (t) => V3(Math.sin(t * 1.31) * 0.0022 + Math.sin(t * 2.9 + 1) * 0.001, Math.sin(t * 1.7 + 2) * 0.0018, Math.sin(t * 1.1 + 4) * 0.0015);
  const poseAt = (t) => {
    const {E, L} = eyeAt(t);
    const hh = STILL ? V3() : handheld(t), ease = 1 - 0.75 * seg(t, 2.4, 3.2);
    E.add(hh.clone().multiplyScalar(ease)); L.add(hh.clone().multiplyScalar(0.3 * ease));
    E.x += pt.sx * 0.012 * ease; E.z += pt.sy * 0.008 * ease;
    /* pulled back on a tall screen, along the line of sight */
    if (fit > 1) { const d = E.clone().sub(L); E.copy(L).addScaledVector(d, mix(fit, 1, smooth(seg(t, 2.3, 3.0)))); }
    return {E, L};
  };
  /* the lens: the focus on the notebook (the cover, then the turning leaves, then the page), the field shallow */
  const lensAt = (t) => {
    const {E} = poseAt(t), target = t < 1.1 ? V3(0.075, NB.T2, -0.02) : t < 2.5 ? V3(0.02, 0.05, 0) : V3(0.075, 0.004, 0);
    const d = E.distanceTo(target);
    return {focus: d, aper: lean ? 0 : mix(1.1, 0.6, seg(t, 2.3, 3.2))};      // a wide aperture: the room behind goes soft as a lens at f/2 would have it
  };
  const startCol = new THREE.Color(opts.start || "#F5F5F2"), endCol = new THREE.Color(opts.end || "#F5F5F2");
  const lensP = {focus: 0.5, aper: 0, veil: new THREE.Color(0, 0, 0), veilA: 0, time: 0, expo: 0.82};
  const live = (t) => { lamp.intensity = LAMP * (1 + 0.012 * Math.sin(t * 11.3) + 0.005 * Math.sin(t * 41.0)); lensP.time = t; };
  const fwd = V3();
  const frame = (t) => {
    const {E, L} = poseAt(t);
    /* looking down at the page, "up" on the screen is the page's head (away from you), so the page never rolls */
    fwd.copy(L).sub(E).normalize();
    const k = smooth(seg(-fwd.y, 0.80, 0.985));
    cam.position.copy(E); cam.up.set(0, 1 - k, -k).normalize(); cam.lookAt(L);
    placeBook(t); live(t);
    const Lz = lensAt(t); lensP.focus = Lz.focus; lensP.aper = Lz.aper;
    const vin = STILL ? 0 : 1 - smooth(seg(t, 0.0, 0.5)), vout = STILL ? 0 : smooth(seg(t, DUR - 0.42, DUR - 0.05));
    if (vout > 0) { lensP.veil.copy(endCol); lensP.veilA = vout; } else { lensP.veil.copy(startCol); lensP.veilA = vin; }
    return lensP.veilA;
  };
  const resize = (asp) => { cam.aspect = asp; cam.updateProjectionMatrix(); refit(asp); };
  const gpu = async (still) => { try { await renderer.compileAsync(scene, cam); } catch (e) { try { renderer.compile(scene, cam); } catch (x) {} } mark("compiled"); };
  const dispose = () => {
    scene.traverse(o => { if (o.geometry) o.geometry.dispose(); });
    for (const m of mats) { for (const k of ["map", "normalMap", "roughnessMap"]) if (m[k] && m[k].dispose) m[k].dispose(); m.dispose(); }
    envRT.dispose(); lamp.shadow.dispose(); win.shadow.dispose();
  };
  return {scene, cam, frame, lensP, resize, gpu, dispose, marks, book};
}

/* ================================ the lens ================================ */
/* The picture reaches the screen through a lens: drawn first into a high-range picture with its depth; a soft bloom off
   the lamp and the brass; depth of field (a gather along each axis, its reach the circle of confusion at each pixel, each
   tap counting only as far as its own circle reaches); a filmic curve; a quiet warm grade; the lens's own fall-off at the
   edges and the colours focusing a hair apart there; a very fine grain that changes every frame; and the veil. */
const FS_VERT = "varying vec2 vUv; void main(){ vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }";
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
    this.samples = Math.min(lean ? 2 : 4, caps.maxSamples || 0);
    const mat = (frag, uniforms) => new THREE.ShaderMaterial({uniforms, vertexShader: FS_VERT, fragmentShader: frag, depthTest: false, depthWrite: false});
    const T = "uniform sampler2D tex; uniform vec2 texel; varying vec2 vUv;";
    this.mBright = mat(`${T} uniform float thr, knee;
      void main(){ vec3 c = 0.25 * (texture2D(tex, vUv + texel * vec2(-0.5, -0.5)).rgb + texture2D(tex, vUv + texel * vec2(0.5, -0.5)).rgb + texture2D(tex, vUv + texel * vec2(-0.5, 0.5)).rgb + texture2D(tex, vUv + texel * vec2(0.5, 0.5)).rgb);
        float l = dot(c, vec3(0.2126, 0.7152, 0.0722)); float s = clamp(l - thr + knee, 0.0, 2.0 * knee); s = s * s / (4.0 * knee + 1e-4);
        float w = max(l - thr, s) / max(l, 1e-4); gl_FragColor = vec4(c * w, 1.0); }`,
      {tex: {value: null}, texel: {value: new THREE.Vector2()}, thr: {value: 1.0}, knee: {value: 0.3}});
    this.mDown = mat(`${T} void main(){ vec2 h = texel * 0.5;
        vec3 c = texture2D(tex, vUv).rgb * 4.0 + texture2D(tex, vUv - h).rgb + texture2D(tex, vUv + h).rgb + texture2D(tex, vUv + vec2(h.x, -h.y)).rgb + texture2D(tex, vUv - vec2(h.x, -h.y)).rgb;
        gl_FragColor = vec4(c / 8.0, 1.0); }`, {tex: {value: null}, texel: {value: new THREE.Vector2()}});
    this.mUp = mat(`${T} uniform sampler2D add; void main(){ vec2 h = texel;
        vec3 c = texture2D(tex, vUv + vec2(-h.x * 2.0, 0.0)).rgb + texture2D(tex, vUv + vec2(-h.x, h.y)).rgb * 2.0 + texture2D(tex, vUv + vec2(0.0, h.y * 2.0)).rgb + texture2D(tex, vUv + vec2(h.x, h.y)).rgb * 2.0
          + texture2D(tex, vUv + vec2(h.x * 2.0, 0.0)).rgb + texture2D(tex, vUv + vec2(h.x, -h.y)).rgb * 2.0 + texture2D(tex, vUv + vec2(0.0, -h.y * 2.0)).rgb + texture2D(tex, vUv + vec2(-h.x, -h.y)).rgb * 2.0;
        gl_FragColor = vec4(c / 12.0 + texture2D(add, vUv).rgb, 1.0); }`, {tex: {value: null}, add: {value: null}, texel: {value: new THREE.Vector2()}});
    this.mDof = mat(`${T} uniform sampler2D depth; uniform vec2 dir; uniform float near, far, focus, aper, maxC;
      float lin(float d){ float z = d * 2.0 - 1.0; return 2.0 * near * far / (far + near - z * (far - near)); }
      float coc(float z){ return clamp(aper * abs(z - focus) / max(z, 0.02), 0.0, 1.0) * maxC; }
      void main(){ float c0 = coc(lin(texture2D(depth, vUv).x)); vec3 acc = vec3(0.0); float ws = 0.0;
        if (c0 < 0.7) { gl_FragColor = vec4(texture2D(tex, vUv).rgb, 1.0); return; }
        for (int i = -8; i <= 8; i++) { float fi = float(i); float dist = abs(fi) * c0 / 8.0; vec2 uv = vUv + dir * fi * c0 / 8.0;
          float ct = coc(lin(texture2D(depth, uv).x)); float w = exp(-fi * fi / 30.0) * (i == 0 ? 1.0 : clamp(ct / max(dist, 1e-3), 0.0, 1.0));
          acc += texture2D(tex, uv).rgb * w; ws += w; }
        gl_FragColor = vec4(acc / ws, 1.0); }`,
      {tex: {value: null}, texel: {value: new THREE.Vector2()}, depth: {value: null}, dir: {value: new THREE.Vector2()}, near: {value: 0.03}, far: {value: 40}, focus: {value: 0.5}, aper: {value: 0}, maxC: {value: 10}});
    this.mFinal = mat(`${T} uniform sampler2D bloom; uniform float expo, bloomK, grain, vig, ca, veilA, lift, warm, sat, frame; uniform vec3 veil;
      float hash12(vec2 p){ vec3 p3 = fract(vec3(p.xyx) * 0.1031); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.x + p3.y) * p3.z); }
      vec3 aces(vec3 x){ return clamp((x * (2.51 * x + 0.03)) / (x * (2.43 * x + 0.59) + 0.14), 0.0, 1.0); }
      void main(){
        vec2 q = vUv - 0.5; float r2 = dot(q, q); vec2 off = q * ca * (0.4 + r2);
        vec3 col = vec3(texture2D(tex, vUv + off).r, texture2D(tex, vUv).g, texture2D(tex, vUv - off).b);
        col += texture2D(bloom, vUv).rgb * bloomK;
        col *= expo;
        col = aces(col);
        float l = dot(col, vec3(0.2126, 0.7152, 0.0722));
        col = mix(vec3(l), col, sat);
        col *= mix(vec3(1.0), vec3(1.03, 1.0, 0.96), warm * (1.0 - abs(l - 0.5) * 1.4));
        col = col * (1.0 - lift) + lift * vec3(0.98, 0.96, 1.0);
        col *= 1.0 - vig * smoothstep(0.12, 0.95, r2 * 2.0);
        float gn = hash12(floor(gl_FragCoord.xy / 1.5) + vec2(frame * 7.13, frame * 3.71)) - 0.5;
        col += gn * grain * (1.0 - 0.75 * l);
        col = mix(col, veil, veilA);
        gl_FragColor = vec4(col, 1.0);
        #include <colorspace_fragment>
      }`,
      {tex: {value: null}, texel: {value: new THREE.Vector2()}, bloom: {value: null}, expo: {value: 1.0}, bloomK: {value: 0.22}, grain: {value: 0.02}, vig: {value: 0.26}, ca: {value: 0.0022},
       veilA: {value: 0}, veil: {value: new THREE.Color(0, 0, 0)}, lift: {value: 0.012}, warm: {value: 0.55}, sat: {value: 1.03}, frame: {value: 0}});
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
  render(scene, cam, P = {}){
    const R = this.rts, r = this.r;
    r.setRenderTarget(R.scene); r.render(scene, cam);
    r.setRenderTarget(null);
    this.pass(this.mBright, R.scene, R.b1); this.pass(this.mDown, R.b1, R.b2); this.pass(this.mDown, R.b2, R.b3); this.pass(this.mDown, R.b3, R.b4);
    this.pass(this.mUp, R.b4, R.u3, R.b3); this.pass(this.mUp, R.u3, R.u2, R.b2); this.pass(this.mUp, R.u2, R.u1, R.b1);
    let src = R.scene;
    if (this.dof && (P.aper || 0) > 0.001) {
      const u = this.mDof.uniforms; u.depth.value = R.scene.depthTexture; u.near.value = cam.near; u.far.value = cam.far; u.focus.value = P.focus || 1; u.aper.value = P.aper; u.maxC.value = Math.max(3, this.w / 60);
      u.dir.value.set(1 / this.w, 0); this.pass(this.mDof, R.scene, R.d1);
      u.dir.value.set(0, 1 / this.h); this.pass(this.mDof, R.d1, R.d2);
      src = R.d2;
    }
    const f = this.mFinal.uniforms;
    f.bloom.value = R.u1.texture; f.expo.value = P.expo ?? 1; f.veilA.value = P.veilA || 0; if (P.veil) f.veil.value.copy(P.veil);
    f.frame.value = (this.frame = (this.frame + 1) % 1000); f.grain.value = this.lean ? 0.012 : 0.014;
    this.pass(this.mFinal, src, null);
  }
  dispose(){ if (this.rts) for (const k in this.rts) this.rts[k].dispose(); for (const m of [this.mBright, this.mDown, this.mUp, this.mDof, this.mFinal]) m.dispose(); this.quad.geometry.dispose(); }
}
function setup(renderer, w, h, ratio){
  renderer.setPixelRatio(ratio); renderer.setSize(w, h, false);
  renderer.outputColorSpace = THREE.SRGBColorSpace; renderer.toneMapping = THREE.NoToneMapping; renderer.toneMappingExposure = 1.0;      // the lens does the tone mapping
  renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
}
function lensFor(renderer, lean, opts){ const L = new Lens(renderer, lean, opts), v = new THREE.Vector2(); renderer.getDrawingBufferSize(v); L.size(v.x, v.y); return L; }
const pixelRatio = (w, h, lean) => lean ? Math.min(1.5, devicePixelRatio || 1, Math.sqrt(1.2e6 / (w * h))) : Math.min(2, devicePixelRatio || 1, Math.sqrt(4.2e6 / (w * h)));

/* ================================ playing it over the page ================================ */
export function run(url, opts = {}){
  if (!supported() || !opts.assets) return false;
  let renderer;
  try { renderer = new THREE.WebGLRenderer({antialias: false, powerPreference: "high-performance"}); } catch (e) { return false; }
  const host = opts.host || document.body.appendChild(document.createElement("div"));
  const w = innerWidth, h = innerHeight, lean = !!(opts.lean || opts.assets.lean);
  setup(renderer, w, h, pixelRatio(w, h, lean));
  let S, lens;
  try { S = build(renderer, w / h, opts.assets, {still: !!opts.still, start: opts.start, end: opts.end, title: opts.title, path: opts.path}); lens = lensFor(renderer, lean); }
  catch (e) { renderer.dispose(); return false; }
  const cv = renderer.domElement; cv.setAttribute("aria-hidden", "true"); cv.style.cssText = "position:absolute;inset:0;display:block;width:100%;height:100%;opacity:0;transition:opacity .4s ease";
  host.prepend(cv);
  let gone = false, dead = false, t0 = 0, raf = 0;
  const begun = performance.now(), timers = [], later = (f, ms) => { timers.push(setTimeout(f, ms)); };
  const stop = () => { gone = true; cancelAnimationFrame(raf); for (const id of timers) clearTimeout(id); };
  const tidy = () => { try { ac.abort(); S.dispose(); lens.dispose(); renderer.dispose(); renderer.forceContextLoss(); } catch (e) {} };
  const go = (how) => { if (gone) return; stop(); if (opts.onEnd) { cv.style.transition = "opacity .3s ease"; cv.style.opacity = 0; setTimeout(() => { tidy(); cv.remove(); }, 340); opts.onEnd(how); } else location.href = url; };
  const skip = () => go("skip");
  const ac = new AbortController(), signal = ac.signal;
  host.addEventListener("pointerdown", e => { if (e.button === 0 || e.pointerType !== "mouse") skip(); }, {signal});
  host.addEventListener("click", skip, {signal});
  if (opts.keys !== false) addEventListener("keydown", e => { if (!quietKey(e)) { e.preventDefault(); skip(); } }, {capture: true, signal});
  addEventListener("resize", () => { if (gone) return; renderer.setSize(innerWidth, innerHeight, false); S.resize(innerWidth / innerHeight); const v = new THREE.Vector2(); renderer.getDrawingBufferSize(v); lens.size(v.x, v.y); }, {signal});
  /* Back while it plays keeps this page in the browser's memory with its clocks stopped: when it comes back, the scene is
     gone and nothing goes on to the notebook by itself */
  addEventListener("pagehide", e => { if (e.persisted) stop(); }, {signal});
  addEventListener("pageshow", e => { if (e.persisted) { stop(); dead = true; tidy(); cv.remove(); } }, {signal});
  const draw = t => { S.frame(t); lens.render(S.scene, S.cam, S.lensP); };
  let started = false;
  const tick = now => {
    if (gone) return;
    if (!t0) t0 = now;
    const t = Math.min(DUR, (now - t0) / 1000);
    pt.sx += (pt.x - pt.sx) * 0.05; pt.sy += (pt.y - pt.sy) * 0.05;
    draw(t);
    if (t < DUR) raf = requestAnimationFrame(tick); else go("full");
  };
  const start = () => {
    if (started || gone || dead) return;
    started = true;
    if (opts.still) {      // motion off, Calm, or reduced motion: one still picture, then a plain fade
      draw(STILL_T); cv.style.transition = "none"; cv.style.opacity = 1;
      later(() => { if (gone) return; if (opts.fade) opts.fade(); later(() => go("still"), 420); }, 1500);
      return;
    }
    draw(0);
    requestAnimationFrame(() => { cv.style.opacity = 1; });
    raf = requestAnimationFrame(tick);
    const guard = () => { if (gone) return; if (performance.now() - begun < (DUR + 1.8) * 1000) { later(guard, 400); return; } go("full"); };
    later(guard, DUR * 1000 + 1800);      // a window that is not drawing frames still gets there
  };
  S.gpu().then(start, start);
  later(start, 2500);      // never kept waiting
  return {skip};
}
const QUIET = ["Shift", "Control", "Alt", "AltGraph", "Meta", "OS", "Super", "Hyper", "Fn", "FnLock", "CapsLock", "NumLock", "ScrollLock", "Insert", "Unidentified", "Process"];
function quietKey(e){ return e.ctrlKey || e.metaKey || e.altKey || QUIET.includes(e.key) || /^F\d{1,2}$/.test(e.key || ""); }

/* ================================ a still, for checking ================================ */
export async function still(t = STILL_T, w = 960, h = 540, opts = {}){
  const A = await prepare(opts);
  if (opts.pt) { pt.x = pt.sx = opts.pt.x; pt.y = pt.sy = opts.pt.y; }
  const renderer = new THREE.WebGLRenderer({antialias: false, preserveDrawingBuffer: true});
  setup(renderer, w, h, opts.ratio || 1);
  const lean = !!(opts.lean || A.lean);
  const S = build(renderer, w / h, A, Object.assign({}, opts, {still: !!opts.still}));
  const lens = lensFor(renderer, lean, {dof: opts.dof});
  await S.gpu();
  const v = S.frame(t);
  if (opts.inspect) opts.inspect(S, THREE, lens);
  const t1 = performance.now();
  if (opts.noLens) renderer.render(S.scene, S.cam); else lens.render(S.scene, S.cam, S.lensP);
  const gl = renderer.getContext(); gl.readPixels(0, 0, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, new Uint8Array(4));
  const t2 = performance.now(), url = renderer.domElement.toDataURL(opts.png ? "image/png" : "image/jpeg", opts.q || 0.9);
  const m = S.marks, times = m.slice(1).map((x, i) => x[0] + " " + Math.round(x[1] - m[i][1])).join(", ") + ", frame " + Math.round(t2 - t1);
  const info = {focus: +S.lensP.focus.toFixed(3), aper: S.lensP.aper, hdr: lens.hdr, samples: lens.samples, lean, serif: !!A.serif, size: [renderer.domElement.width, renderer.domElement.height]};
  S.dispose(); lens.dispose(); renderer.dispose(); renderer.forceContextLoss();
  return {url, veil: v, times, info};
}
